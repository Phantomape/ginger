"""Generate operator_inputs/open_positions.json from the moomoo account.

moomoo is the authoritative source for what is actually held (ticker, qty,
average cost, market value, account cash). The operator no longer hand-maintains
those fields; they only maintain a small tag map
(``operator_inputs/position_tags.json``) that classifies each ticker by
``type`` (core / sleeve / legacy) and the specific ``sleeve`` name. Everything
else is derived:

- account cash / portfolio value: ``accinfo_query(currency=USD)`` (the FUTUSG
  account reports HKD by default, so USD must be requested explicitly);
- ``entry_date``: reconstructed from up to ~2 years of fills (the open lot's
  first buy), falling back to the prior file when older than the fills window;
- ``target_price`` / ``stop_price``: auto-computed via the existing
  ``position_manager`` convention (profit target + ATR(14) volatility stop),
  overridable per ticker in the tag map.

The result is written in the three-section schema
(``core_positions`` / ``positions`` / ``observations``) that
``quant/open_position_schema.py`` and all downstream consumers already read, so
this is a drop-in source swap with no consumer changes.

This module performs no order placement and changes no trade settings. No
JavaScript is used.
"""

from __future__ import annotations

import json
import os
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_PATH = REPO_ROOT / "operator_inputs" / "open_positions.json"
DEFAULT_PREVIEW_PATH = REPO_ROOT / "operator_inputs" / "open_positions.moomoo_preview.json"
DEFAULT_TAG_MAP_PATH = REPO_ROOT / "operator_inputs" / "position_tags.json"

DEFAULT_ACCOUNT_ID = int(os.environ.get("FUTU_ACC_ID", "283726803957104546"))
DEFAULT_SECURITY_FIRM = os.environ.get("FUTU_SECURITY_FIRM", "FUTUSG")
DEFAULT_HOST = os.environ.get("FUTU_OPEND_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.environ.get("FUTU_OPEND_PORT", "11111"))
DEFAULT_SDK_APPDATA = REPO_ROOT / "data" / "runtime" / "moomoo_sdk_appdata"
FILLS_LOOKBACK_DAYS = 730  # ~2 years for entry-date reconstruction

# type -> (section, slot_policy, default sleeve)
TYPE_TO_SECTION = {
    "core": ("core_positions", "consumes_core_slot", "core_strategy"),
    "sleeve": ("positions", "no_core_slot", "paper"),
    "legacy": ("observations", "no_core_slot", "legacy"),
}
DEFAULT_TYPE = "sleeve"  # untagged holdings: visible, do NOT consume a core slot


def _utc_today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _strip_market(code: str) -> str:
    """``US.NVDA`` -> ``NVDA``; leave bare codes untouched."""
    return str(code or "").split(".", 1)[-1].upper().strip()


def read_json(path: Path, default: Any = None) -> Any:
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


# --------------------------------------------------------------------------
# Pure transforms (unit-tested).
# --------------------------------------------------------------------------
def reconstruct_entry_dates(fills: list[dict[str, Any]]) -> dict[str, str]:
    """Earliest buy date of each ticker's currently-open long lot.

    Walk fills oldest->newest tracking a running signed share count per ticker.
    When the running count rises from <= 0 to > 0 we start a new lot and record
    its date; when it returns to <= 0 the lot is closed. The entry date of the
    still-open lot is returned. Robust to partial adds (keeps the lot-open date,
    not the latest add).
    """
    rows = [r for r in fills if r.get("ticker") and r.get("date")]
    rows.sort(key=lambda r: (str(r["date"]), str(r.get("ticker"))))
    running: dict[str, float] = {}
    lot_open_date: dict[str, str] = {}
    for r in rows:
        ticker = _strip_market(r["ticker"])
        side = str(r.get("side") or "").upper()
        qty = abs(float(r.get("qty") or 0.0))
        if qty <= 0:
            continue
        signed = qty if side in ("BUY", "BUY_BACK", "BUYBACK") else -qty
        prev = running.get(ticker, 0.0)
        new = prev + signed
        if prev <= 0 < new:
            lot_open_date[ticker] = str(r["date"])[:10]
        running[ticker] = new
        if new <= 0:
            lot_open_date.pop(ticker, None)
    return {t: d for t, d in lot_open_date.items() if running.get(t, 0.0) > 0}


def compute_target_stop(
    avg_cost: float | None,
    current_price: float | None,
    atr: float | None,
) -> tuple[float | None, float | None]:
    """Auto target/stop via the shared position_manager convention.

    target_price = fixed profit target; stop_price = ATR(14) volatility stop
    (current-price referenced so it stays meaningful for winners), falling back
    to the hard percentage stop when ATR is unavailable.
    """
    if not avg_cost or avg_cost <= 0:
        return (None, None)
    try:
        from position_manager import compute_exit_levels
    except ImportError:  # pragma: no cover
        from quant.position_manager import compute_exit_levels
    levels = compute_exit_levels(avg_cost, atr=atr, current_price=current_price)
    target = levels.get("profit_target_price")
    stop = levels.get("atr_stop_price") or levels.get("hard_stop_price")
    return (target, stop)


def load_tag_map(path: Path | str = DEFAULT_TAG_MAP_PATH) -> dict[str, dict[str, Any]]:
    raw = read_json(path, {}) or {}
    tags = raw.get("tags", raw) if isinstance(raw, dict) else {}
    out: dict[str, dict[str, Any]] = {}
    for ticker, meta in (tags or {}).items():
        key = _strip_market(ticker)
        if isinstance(meta, str):
            out[key] = {"type": meta}
        elif isinstance(meta, dict):
            out[key] = dict(meta)
    return out


def _prior_rows_by_ticker(prior_payload: dict | None) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not isinstance(prior_payload, dict):
        return out
    for section in ("core_positions", "positions", "observations"):
        for row in prior_payload.get(section) or []:
            if isinstance(row, dict) and row.get("ticker"):
                out.setdefault(_strip_market(row["ticker"]), row)
    return out


def build_payload(
    positions: list[dict[str, Any]],
    account: dict[str, Any],
    *,
    entry_dates: dict[str, str],
    atr_by_ticker: dict[str, float | None],
    tag_map: dict[str, dict[str, Any]],
    prior_payload: dict | None = None,
    as_of: str | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Build the three-section open_positions payload. Returns (payload, untagged)."""
    as_of = as_of or _utc_today()
    prior = _prior_rows_by_ticker(prior_payload)
    sections: dict[str, list[dict]] = {"core_positions": [], "positions": [], "observations": []}
    untagged: list[str] = []

    for pos in positions:
        ticker = _strip_market(pos.get("code") or pos.get("ticker") or "")
        if not ticker:
            continue
        qty = float(pos.get("qty") or pos.get("shares") or 0.0)
        if qty <= 0:
            continue  # only currently-held long lots
        avg_cost = pos.get("average_cost")
        if avg_cost is None:
            avg_cost = pos.get("avg_cost")
        avg_cost = float(avg_cost) if avg_cost is not None else None
        current_price = pos.get("nominal_price") or pos.get("current_price")
        current_price = float(current_price) if current_price else None
        side = str(pos.get("position_side") or pos.get("direction") or "LONG").upper()
        direction = "short" if side.startswith("SHORT") else "long"

        tag = tag_map.get(ticker, {})
        ptype = str(tag.get("type") or "").lower()
        if ptype not in TYPE_TO_SECTION:
            ptype = DEFAULT_TYPE
            untagged.append(ticker)
        section, slot_policy, default_sleeve = TYPE_TO_SECTION[ptype]
        sleeve = tag.get("sleeve") or default_sleeve

        prior_row = prior.get(ticker, {})
        entry_date = entry_dates.get(ticker) or prior_row.get("entry_date")

        # target/stop: tag override -> auto-compute -> prior file.
        target = tag.get("target_price")
        stop = tag.get("stop_price")
        if target is None or stop is None:
            auto_target, auto_stop = compute_target_stop(
                avg_cost, current_price, atr_by_ticker.get(ticker)
            )
            target = target if target is not None else (auto_target if auto_target is not None else prior_row.get("target_price"))
            stop = stop if stop is not None else (auto_stop if auto_stop is not None else prior_row.get("stop_price"))

        row = {
            "ticker": ticker,
            "direction": direction,
            "shares": qty,
            "avg_cost": round(avg_cost, 4) if avg_cost is not None else None,
            "entry_date": entry_date,
            "target_price": round(target, 2) if isinstance(target, (int, float)) else target,
            "stop_price": round(stop, 2) if isinstance(stop, (int, float)) else stop,
            "opened_by_strategy": tag.get("opened_by_strategy") or prior_row.get("opened_by_strategy") or ptype,
            "sleeve": sleeve,
            "slot_policy": tag.get("slot_policy") or slot_policy,
            "risk_notes": tag.get("risk_notes") or prior_row.get("risk_notes") or "",
            "source": "moomoo",
            "market_val": pos.get("market_val"),
            "unrealized_pl": pos.get("unrealized_pl"),
            "position_id": pos.get("position_id"),
        }
        sections[section].append(row)

    for section in sections:
        sections[section].sort(key=lambda r: r["ticker"])

    payload = {
        "as_of": as_of,
        "account": f"moomoo_{str(DEFAULT_SECURITY_FIRM).lower()}",
        "source": "moomoo_open_positions",
        "portfolio_value_usd": account.get("total_assets"),
        "cash_usd": account.get("cash"),
        "currency": "USD",
        "untagged_tickers": sorted(set(untagged)),
        **sections,
    }
    return payload, sorted(set(untagged))


# --------------------------------------------------------------------------
# moomoo I/O (thin; not unit-tested — exercised via preview run).
# --------------------------------------------------------------------------
def _opend_reachable(host: str, port: int, timeout: float = 2.0) -> bool:
    """Fast TCP probe so a down OpenD fails fast instead of retrying forever.

    The moomoo SDK retries ``connect`` in an indefinite loop when OpenD is not
    listening (each attempt ~8s), which would hang the daily run rather than
    let the caller fall back to the existing file. A short connect probe lets us
    bail in seconds when the gateway is offline.
    """
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _redirect_moomoo_sdk_appdata() -> str | None:
    """Point the moomoo SDK log file at a repo-local directory during import.

    The SDK creates ``%APPDATA%/com.moomoo.OpenD/Log/py_YYYY_MM_DD.log`` at
    import time. On Windows that file can be held open by another Python
    process, which prevents a fresh daily run from importing the SDK even when
    OpenD itself is reachable. Redirect only for the import; the file handler
    keeps the repo-local path after the environment is restored.
    """
    if os.environ.get("GINGER_MOOMOO_USE_SYSTEM_APPDATA"):
        return None
    target = Path(os.environ.get("GINGER_MOOMOO_SDK_APPDATA") or DEFAULT_SDK_APPDATA)
    target.mkdir(parents=True, exist_ok=True)
    previous = os.environ.get("APPDATA")
    os.environ["APPDATA"] = str(target)
    return previous


def _restore_moomoo_sdk_appdata(previous: str | None) -> None:
    if previous is None:
        os.environ.pop("APPDATA", None)
        return
    os.environ["APPDATA"] = previous


def fetch_moomoo_state(
    *,
    acc_id: int = DEFAULT_ACCOUNT_ID,
    security_firm: str = DEFAULT_SECURITY_FIRM,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    fills_lookback_days: int = FILLS_LOOKBACK_DAYS,
) -> dict[str, Any] | None:
    """Pull positions, USD account info, and ~2y of fills. None on failure."""
    if not _opend_reachable(host, port):
        print(f"[moomoo_open_positions] OpenD not reachable at {host}:{port} -> fallback.")
        return None
    appdata_env = _redirect_moomoo_sdk_appdata()
    try:
        from moomoo import (
            OpenSecTradeContext, TrdMarket, TrdEnv, SecurityFirm, Currency, RET_OK,
        )
    except ImportError as exc:  # pragma: no cover
        print(f"[moomoo_open_positions] moomoo SDK unavailable: {exc}")
        return None
    finally:
        _restore_moomoo_sdk_appdata(appdata_env)

    firm = getattr(SecurityFirm, str(security_firm), SecurityFirm.FUTUSG)
    ctx = OpenSecTradeContext(
        filter_trdmarket=TrdMarket.NONE, host=host, port=port, security_firm=firm
    )
    try:
        ret, posdf = ctx.position_list_query(trd_env=TrdEnv.REAL, acc_id=acc_id, refresh_cache=True)
        if ret != RET_OK:
            print(f"[moomoo_open_positions] position query failed: {posdf}")
            return None
        positions = posdf.to_dict("records")

        ret, accdf = ctx.accinfo_query(
            trd_env=TrdEnv.REAL, acc_id=acc_id, refresh_cache=True, currency=Currency.USD
        )
        account = {}
        if ret == RET_OK and len(accdf):
            account = {
                "total_assets": float(accdf["total_assets"][0]),
                "cash": float(accdf["cash"][0]),
                "market_val": float(accdf["market_val"][0]),
            }

        start = (datetime.now(timezone.utc).date() - timedelta(days=fills_lookback_days)).isoformat()
        end = datetime.now(timezone.utc).date().isoformat()
        ret, filldf = ctx.history_deal_list_query(
            trd_env=TrdEnv.REAL, acc_id=acc_id, start=start, end=end
        )
        fills: list[dict[str, Any]] = []
        if ret == RET_OK and len(filldf):
            for rec in filldf.to_dict("records"):
                fills.append({
                    "ticker": rec.get("code"),
                    "side": rec.get("trd_side"),
                    "qty": rec.get("qty"),
                    "date": str(rec.get("create_time") or "")[:10],
                })
        return {"positions": positions, "account": account, "fills": fills}
    finally:
        ctx.close()


def _atr_by_ticker(tickers: list[str]) -> dict[str, float | None]:
    """ATR(14) per ticker from the (overlay) warehouse; {} if unavailable."""
    out: dict[str, float | None] = {}
    try:
        from ohlcv_warehouse import DEFAULT_WAREHOUSE_PATH, load_warehouse_ohlcv_frames
        from position_manager import compute_atr
    except ImportError:  # pragma: no cover
        from quant.ohlcv_warehouse import DEFAULT_WAREHOUSE_PATH, load_warehouse_ohlcv_frames
        from quant.position_manager import compute_atr
    try:
        start = (datetime.now(timezone.utc).date() - timedelta(days=120)).isoformat()
        end = datetime.now(timezone.utc).date().isoformat()
        frames = load_warehouse_ohlcv_frames(str(DEFAULT_WAREHOUSE_PATH), tickers, start, end)
        for t in tickers:
            frame = frames.get(t)
            out[t] = compute_atr(frame) if frame is not None and not frame.empty else None
    except Exception as exc:  # noqa: BLE001
        print(f"[moomoo_open_positions] ATR load failed (target/stop will fall back): {exc}")
    return out


def generate(
    *,
    out_path: Path | str = DEFAULT_OUT_PATH,
    tag_map_path: Path | str = DEFAULT_TAG_MAP_PATH,
    preview: bool = True,
    state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build and write the payload. Falls back to the prior file if moomoo fails."""
    prior_payload = read_json(out_path, None)
    state = state if state is not None else fetch_moomoo_state()
    if not state or not state.get("positions"):
        print("[moomoo_open_positions] moomoo unavailable/empty -> keeping existing file (fallback).")
        return {"status": "fallback_existing", "wrote": None, "untagged": []}

    positions = state["positions"]
    tickers = sorted({_strip_market(p.get("code") or "") for p in positions if p.get("code")})
    entry_dates = reconstruct_entry_dates(state.get("fills") or [])
    atr_by_ticker = _atr_by_ticker(tickers)
    tag_map = load_tag_map(tag_map_path)
    payload, untagged = build_payload(
        positions, state.get("account") or {},
        entry_dates=entry_dates, atr_by_ticker=atr_by_ticker,
        tag_map=tag_map, prior_payload=prior_payload,
    )

    target = Path(DEFAULT_PREVIEW_PATH if preview else out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=4, sort_keys=False) + "\n", encoding="utf-8")
    n = sum(len(payload.get(s) or []) for s in ("core_positions", "positions", "observations"))
    print(f"[moomoo_open_positions] wrote {n} positions -> {target} "
          f"(preview={preview}, untagged={untagged})")
    return {"status": "written", "wrote": str(target), "untagged": untagged, "payload": payload}


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Generate open_positions.json from moomoo.")
    ap.add_argument("--write", action="store_true", help="Overwrite the real file (default: preview only).")
    ap.add_argument("--out", default=str(DEFAULT_OUT_PATH))
    ap.add_argument("--tag-map", default=str(DEFAULT_TAG_MAP_PATH))
    args = ap.parse_args()
    result = generate(out_path=args.out, tag_map_path=args.tag_map, preview=not args.write)
    print(json.dumps({k: v for k, v in result.items() if k != "payload"}, indent=2, default=str))


if __name__ == "__main__":
    main()
