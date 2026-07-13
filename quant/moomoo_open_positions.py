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
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from broker_execution_ledger import (
        DEFAULT_LEDGER_DIR as DEFAULT_BROKER_LEDGER_DIR,
        account_key as broker_account_key,
        json_safe,
        persist_broker_execution_capture,
        utc_now_iso,
        write_broker_ledger_health,
    )
    from data_paths import atomic_write_text
except ImportError:  # pragma: no cover - package-style imports
    from quant.broker_execution_ledger import (
        DEFAULT_LEDGER_DIR as DEFAULT_BROKER_LEDGER_DIR,
        account_key as broker_account_key,
        json_safe,
        persist_broker_execution_capture,
        utc_now_iso,
        write_broker_ledger_health,
    )
    from quant.data_paths import atomic_write_text

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
CASHFLOW_LOOKBACK_DAYS = 7  # per-clearing-date endpoint; stays below 20/30s limit
ORDER_FEE_BATCH_SIZE = 400  # documented SDK request maximum
ORDER_FEE_REQUESTS_PER_WINDOW = 9  # stay below 10 requests / 30 seconds
ORDER_FEE_WINDOW_SECONDS = 30.0

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
def reconstruct_entry_dates(
    fills: list[dict[str, Any]],
    current_qty_by_ticker: dict[str, float] | None = None,
) -> dict[str, str]:
    """Earliest buy date of each ticker's currently-open long lot.

    Walk fills oldest->newest tracking a running signed share count per ticker.
    When the running count rises from <= 0 to > 0 we start a new lot and record
    its date; when it returns to <= 0 the lot is closed. The entry date of the
    still-open lot is returned. Robust to partial adds (keeps the lot-open date,
    not the latest add).
    """
    rows = [r for r in fills if r.get("ticker") and r.get("date")]
    if current_qty_by_ticker:
        out: dict[str, str] = {}
        by_ticker: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            by_ticker.setdefault(_strip_market(row["ticker"]), []).append(row)
        for raw_ticker, current_qty in current_qty_by_ticker.items():
            ticker = _strip_market(raw_ticker)
            remaining = float(current_qty or 0.0)
            if remaining <= 0:
                continue
            ticker_rows = sorted(by_ticker.get(ticker, []), key=_fill_event_key, reverse=True)
            entry_date = None
            for row in ticker_rows:
                side = str(row.get("side") or "").upper()
                qty = abs(float(row.get("qty") or 0.0))
                if qty <= 0:
                    continue
                if side in ("BUY", "BUY_BACK", "BUYBACK"):
                    remaining -= qty
                    entry_date = str(row["date"])[:10]
                    if remaining <= 1e-9:
                        out[ticker] = entry_date
                        break
                else:
                    # Rewinding a sale restores the shares that existed before it.
                    remaining += qty
        return out
    rows.sort(key=lambda r: (_fill_event_key(r), str(r.get("ticker"))))
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


def _fill_event_key(row: dict[str, Any]) -> tuple[str, str, str]:
    """Full broker time first; IDs make same-timestamp ordering deterministic."""
    return (
        str(row.get("create_time") or row.get("timestamp") or row.get("date") or ""),
        str(row.get("deal_id") or ""),
        str(row.get("order_id") or ""),
    )


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
    cashflow_lookback_days: int = CASHFLOW_LOOKBACK_DAYS,
) -> dict[str, Any] | None:
    """Pull one broker collection for positions plus the execution ledger.

    Each interface has an independent status in ``broker_execution.queries``;
    an account/fill/fee failure is never represented as a successful empty
    result.  ``None`` is reserved for a gateway/SDK/context failure before a
    collection can be attempted.
    """
    if not _opend_reachable(host, port):
        print(f"[moomoo_open_positions] OpenD not reachable at {host}:{port} -> fallback.")
        return None
    appdata_env = _redirect_moomoo_sdk_appdata()
    try:
        import moomoo as moomoo_sdk
        from moomoo import (
            OpenSecTradeContext, TrdMarket, TrdEnv, SecurityFirm, Currency, RET_OK,
        )
    except ImportError as exc:  # pragma: no cover
        print(f"[moomoo_open_positions] moomoo SDK unavailable: {exc}")
        return None
    finally:
        _restore_moomoo_sdk_appdata(appdata_env)

    firm = getattr(SecurityFirm, str(security_firm), SecurityFirm.FUTUSG)
    collection_started = utc_now_iso()
    collection_id = (
        "moomoo-"
        + collection_started.replace("-", "").replace(":", "").replace(".", "")
        + "-"
        + uuid.uuid4().hex[:12]
    )
    account_scope = broker_account_key(
        security_firm=str(security_firm),
        trade_environment="REAL",
        acc_id=acc_id,
    )
    try:
        version_path = Path(moomoo_sdk.__file__).with_name("VERSION.txt")
        sdk_version = version_path.read_text(encoding="utf-8").strip()
    except (AttributeError, OSError):
        sdk_version = "unknown"

    try:
        ctx = OpenSecTradeContext(
            filter_trdmarket=TrdMarket.NONE, host=host, port=port, security_firm=firm
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[moomoo_open_positions] trade context unavailable: {exc}")
        return None

    queries: dict[str, dict[str, Any]] = {}

    def sanitize_error(value: Any) -> str:
        return str(value).replace(str(acc_id), "<account_id>")[:500]

    def query_records(name: str, call) -> list[dict[str, Any]]:
        observed_at = utc_now_iso()
        try:
            ret, data = call()
        except Exception as exc:  # noqa: BLE001
            queries[name] = {
                "status": "error",
                "row_count": 0,
                "observed_at_utc": observed_at,
                "error": sanitize_error(exc),
            }
            return []
        if ret != RET_OK:
            queries[name] = {
                "status": "error",
                "row_count": 0,
                "observed_at_utc": observed_at,
                "error": sanitize_error(data),
            }
            return []
        records = json_safe(data.to_dict("records")) if hasattr(data, "to_dict") else []
        records = records if isinstance(records, list) else []
        queries[name] = {
            "status": "ok",
            "row_count": len(records),
            "observed_at_utc": observed_at,
            "error": None,
        }
        return [row for row in records if isinstance(row, dict)]

    def dedupe_by_id(rows: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
        keyed: dict[str, dict[str, Any]] = {}
        fallback: dict[str, dict[str, Any]] = {}
        for row in rows:
            value = row.get(field)
            key = str(value).strip() if value not in (None, "", "N/A") else ""
            if key:
                keyed[key] = row  # later current-state rows supersede history duplicates
            else:
                canonical = json.dumps(row, ensure_ascii=True, sort_keys=True, default=str)
                fallback[canonical] = row
        return list(keyed.values()) + list(fallback.values())

    def dedupe_versions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        unique: dict[str, dict[str, Any]] = {}
        for row in rows:
            canonical = json.dumps(row, ensure_ascii=True, sort_keys=True, default=str)
            unique[canonical] = row
        return list(unique.values())

    try:
        positions = query_records(
            "positions",
            lambda: ctx.position_list_query(
                trd_env=TrdEnv.REAL, acc_id=acc_id, refresh_cache=True
            ),
        )
        accounts = query_records(
            "account",
            lambda: ctx.accinfo_query(
                trd_env=TrdEnv.REAL,
                acc_id=acc_id,
                refresh_cache=True,
                currency=Currency.USD,
            ),
        )
        if queries["account"]["status"] == "ok" and not accounts:
            queries["account"]["status"] = "error_empty_response"
            queries["account"]["error"] = "accinfo_query returned zero rows"
        account: dict[str, Any] = {}
        if accounts:
            rec = accounts[0]
            account = {
                "total_assets": rec.get("total_assets"),
                "cash": rec.get("cash"),
                "market_val": rec.get("market_val"),
            }

        start = (datetime.now(timezone.utc).date() - timedelta(days=fills_lookback_days)).isoformat()
        end = datetime.now(timezone.utc).date().isoformat()
        history_deals = query_records(
            "history_deals",
            lambda: ctx.history_deal_list_query(
                trd_env=TrdEnv.REAL, acc_id=acc_id, start=start, end=end
            ),
        )
        current_deals = query_records(
            "current_deals",
            lambda: ctx.deal_list_query(
                trd_env=TrdEnv.REAL, acc_id=acc_id, refresh_cache=True
            ),
        )
        # Deal status can later become CHANGED or CANCELLED. Preserve distinct
        # broker versions; the ledger's economic projection selects the latest
        # version and excludes cancelled/unknown rows.
        deals = dedupe_versions(history_deals + current_deals)
        latest_deal_by_id: dict[str, dict[str, Any]] = {}
        fallback_deals: list[dict[str, Any]] = []
        for row in deals:
            deal_id = row.get("deal_id")
            if deal_id not in (None, "", "N/A"):
                latest_deal_by_id[str(deal_id)] = row
            else:
                fallback_deals.append(row)
        effective_deals = [
            row
            for row in list(latest_deal_by_id.values()) + fallback_deals
            if str(row.get("status") or "").upper() in {"OK", "CHANGED"}
        ]
        effective_deals.sort(
            key=lambda row: (
                str(row.get("create_time") or ""),
                str(row.get("deal_id") or ""),
            )
        )

        history_orders = query_records(
            "history_orders",
            lambda: ctx.history_order_list_query(
                trd_env=TrdEnv.REAL, acc_id=acc_id, start=start, end=end
            ),
        )
        current_orders = query_records(
            "current_orders",
            lambda: ctx.order_list_query(
                trd_env=TrdEnv.REAL, acc_id=acc_id, refresh_cache=True
            ),
        )
        orders = dedupe_versions(history_orders + current_orders)
        orders.sort(
            key=lambda row: (
                str(row.get("create_time") or ""),
                str(row.get("updated_time") or ""),
                str(row.get("order_id") or ""),
            )
        )

        order_ids = sorted(
            {
                str(row.get("order_id"))
                for row in orders
                if row.get("order_id") not in (None, "", "N/A")
            }
        )
        fee_rows: list[dict[str, Any]] = []
        fee_errors: list[str] = []
        fee_observed_at = utc_now_iso()
        if not order_ids:
            queries["order_fees"] = {
                "status": "skipped",
                "row_count": 0,
                "observed_at_utc": fee_observed_at,
                "error": None,
            }
        else:
            fee_window_started = time.monotonic()
            fee_requests_in_window = 0
            for offset in range(0, len(order_ids), ORDER_FEE_BATCH_SIZE):
                if fee_requests_in_window >= ORDER_FEE_REQUESTS_PER_WINDOW:
                    remaining = ORDER_FEE_WINDOW_SECONDS - (
                        time.monotonic() - fee_window_started
                    )
                    if remaining > 0:
                        time.sleep(remaining)
                    fee_window_started = time.monotonic()
                    fee_requests_in_window = 0
                batch = order_ids[offset : offset + ORDER_FEE_BATCH_SIZE]
                try:
                    ret, data = ctx.order_fee_query(
                        order_id_list=batch, trd_env=TrdEnv.REAL, acc_id=acc_id
                    )
                    fee_requests_in_window += 1
                except Exception as exc:  # noqa: BLE001
                    fee_requests_in_window += 1
                    fee_errors.append(sanitize_error(exc))
                    continue
                if ret != RET_OK:
                    fee_errors.append(sanitize_error(data))
                    continue
                rows = json_safe(data.to_dict("records")) if hasattr(data, "to_dict") else []
                if isinstance(rows, list):
                    fee_rows.extend(row for row in rows if isinstance(row, dict))
            fee_rows = dedupe_versions(fee_rows)
            queries["order_fees"] = {
                "status": "partial" if fee_errors else "ok",
                "row_count": len(fee_rows),
                "observed_at_utc": fee_observed_at,
                "error": "; ".join(fee_errors)[:500] if fee_errors else None,
            }

        # Securities accounts require one request per clearing date.  Seven
        # calendar dates cover normal daily gaps while staying safely below the
        # endpoint's 20 requests / 30 seconds limit.
        cashflow_rows: list[dict[str, Any]] = []
        cashflow_errors: list[str] = []
        cashflow_observed_at = utc_now_iso()
        lookback = max(1, min(int(cashflow_lookback_days), 19))
        today = datetime.now(timezone.utc).date()
        for days_ago in range(lookback):
            clearing_date = (today - timedelta(days=days_ago)).isoformat()
            try:
                ret, data = ctx.get_acc_cash_flow(
                    clearing_date=clearing_date,
                    trd_env=TrdEnv.REAL,
                    acc_id=acc_id,
                )
            except Exception as exc:  # noqa: BLE001
                cashflow_errors.append(f"{clearing_date}: {sanitize_error(exc)}")
                continue
            if ret != RET_OK:
                cashflow_errors.append(f"{clearing_date}: {sanitize_error(data)}")
                continue
            rows = json_safe(data.to_dict("records")) if hasattr(data, "to_dict") else []
            if isinstance(rows, list):
                cashflow_rows.extend(row for row in rows if isinstance(row, dict))
        cashflow_rows = dedupe_by_id(cashflow_rows, "cashflow_id")
        queries["cashflows"] = {
            "status": "partial" if cashflow_errors else "ok",
            "row_count": len(cashflow_rows),
            "observed_at_utc": cashflow_observed_at,
            "error": "; ".join(cashflow_errors)[:500] if cashflow_errors else None,
        }

        fills = [
            {
                "ticker": rec.get("code"),
                "side": rec.get("trd_side"),
                "qty": rec.get("qty"),
                "price": rec.get("price"),
                "date": str(rec.get("create_time") or "")[:10],
                "create_time": rec.get("create_time"),
                "deal_id": str(rec.get("deal_id")) if rec.get("deal_id") is not None else None,
                "order_id": str(rec.get("order_id")) if rec.get("order_id") is not None else None,
                "deal_market": rec.get("deal_market"),
                "status": rec.get("status"),
            }
            for rec in effective_deals
        ]
        completed_at = utc_now_iso()
        execution_capture = {
            "collection_id": collection_id,
            "collection_started_at_utc": collection_started,
            "collection_completed_at_utc": completed_at,
            "account_key": account_scope,
            "security_firm": str(security_firm),
            "trade_environment": "REAL",
            "sdk_version": sdk_version,
            "history_start": start,
            "history_end": end,
            "cashflow_lookback_days": lookback,
            "queries": queries,
            "deals": deals,
            "orders": orders,
            "order_fees": fee_rows,
            "cashflows": cashflow_rows,
            "accounts": accounts,
            "positions": positions,
        }
        return {
            "positions": positions,
            "positions_query_ok": queries["positions"]["status"] == "ok",
            "account_query_ok": (
                queries["account"]["status"] == "ok" and bool(accounts)
            ),
            "account": account,
            "fills": fills,
            "broker_execution": execution_capture,
        }
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
    broker_ledger_dir: Path | str = DEFAULT_BROKER_LEDGER_DIR,
    persist_execution_ledger: bool | None = None,
) -> dict[str, Any]:
    """Build and write holdings, persisting live execution facts on daily runs.

    Preview and injected-state calls are side-effect free by default.  The
    normal ``run.py`` path calls this with ``preview=False`` and no injected
    state, which enables the ledger in the same broker collection.
    """
    prior_payload = read_json(out_path, None)
    fetched_live = state is None
    state = state if state is not None else fetch_moomoo_state()
    if state is None:
        print("[moomoo_open_positions] moomoo unavailable -> keeping existing file (fallback).")
        return {
            "status": "fallback_existing",
            "wrote": None,
            "untagged": [],
            "broker_execution_ledger": None,
        }

    if persist_execution_ledger is None:
        persist_execution_ledger = (
            fetched_live
            and not preview
            and not bool(os.environ.get("GINGER_SKIP_BROKER_EXECUTION_LEDGER"))
        )
    broker_ledger_result = None
    execution_capture = state.get("broker_execution")
    if persist_execution_ledger and execution_capture:
        try:
            broker_ledger_result = persist_broker_execution_capture(
                execution_capture,
                ledger_dir=broker_ledger_dir,
            )
            print(
                "[moomoo_open_positions] broker execution ledger "
                f"status={broker_ledger_result.get('status')} "
                f"fills+={broker_ledger_result['ledgers']['fills']['rows_appended']} "
                f"orders+={broker_ledger_result['ledgers']['orders']['rows_appended']} "
                f"fees+={broker_ledger_result['ledgers']['order_fees']['rows_appended']}"
            )
        except Exception as exc:  # noqa: BLE001
            # Holdings are the live risk boundary.  Do not silently retain stale
            # holdings merely because the measurement ledger needs repair;
            # persist a separate health alert and continue with the fresh broker
            # position snapshot.
            try:
                health = write_broker_ledger_health(
                    execution_capture,
                    ledger_dir=broker_ledger_dir,
                    status="failed",
                    error=exc,
                )
            except Exception as health_exc:  # noqa: BLE001
                health = {
                    "status": "failed_health_alert_write",
                    "error": str(health_exc)[:500],
                }
            broker_ledger_result = {
                "status": "failed",
                "collection_id": execution_capture.get("collection_id"),
                "state_path": None,
                "error_type": type(exc).__name__,
                "error": str(exc)[:1000],
                "health": health,
            }
            print(
                "[moomoo_open_positions] WARNING broker execution ledger failed; "
                f"fresh holdings will still be written: {type(exc).__name__}: {exc}"
            )

    positions_query_ok = state.get("positions_query_ok")
    if positions_query_ok is None:
        positions_query_ok = "positions" in state
    if not positions_query_ok:
        print(
            "[moomoo_open_positions] position query failed -> keeping existing file "
            "(execution query statuses remain in the broker ledger)."
        )
        return {
            "status": "fallback_existing",
            "wrote": None,
            "untagged": [],
            "broker_execution_ledger": broker_ledger_result,
        }

    # A successful empty list is an authoritative flat account.  Treating it
    # as gateway failure would retain phantom holdings after the final close.
    positions = state.get("positions") or []
    tickers = sorted({_strip_market(p.get("code") or "") for p in positions if p.get("code")})
    current_qty_by_ticker = {
        _strip_market(pos.get("code") or pos.get("ticker") or ""): float(
            pos.get("qty") or pos.get("shares") or 0.0
        )
        for pos in positions
    }
    entry_dates = reconstruct_entry_dates(
        state.get("fills") or [],
        current_qty_by_ticker=current_qty_by_ticker,
    )
    atr_by_ticker = _atr_by_ticker(tickers)
    tag_map = load_tag_map(tag_map_path)
    account_query_ok = state.get("account_query_ok")
    if account_query_ok is None:
        account_query_ok = bool(state.get("account"))
    if account_query_ok:
        account_for_payload = state.get("account") or {}
        account_snapshot_status = "current_broker_account"
    else:
        account_for_payload = {
            "total_assets": (
                prior_payload.get("portfolio_value_usd")
                if isinstance(prior_payload, dict)
                else None
            ),
            "cash": (
                prior_payload.get("cash_usd")
                if isinstance(prior_payload, dict)
                else None
            ),
            "market_val": None,
        }
        account_snapshot_status = (
            "stale_prior_account_values"
            if account_for_payload.get("total_assets") is not None
            or account_for_payload.get("cash") is not None
            else "missing_account_values_no_prior"
        )
    payload, untagged = build_payload(
        positions, account_for_payload,
        entry_dates=entry_dates, atr_by_ticker=atr_by_ticker,
        tag_map=tag_map, prior_payload=prior_payload,
    )
    payload["account_snapshot_status"] = account_snapshot_status
    payload["account_values_as_of"] = (
        payload.get("as_of")
        if account_query_ok
        else (
            prior_payload.get("as_of") if isinstance(prior_payload, dict) else None
        )
    )
    if not account_query_ok:
        print(
            "[moomoo_open_positions] WARNING accinfo unavailable; fresh positions "
            f"will use {account_snapshot_status} as_of={payload.get('account_values_as_of')}"
        )
    payload["broker_execution_ledger"] = (
        {
            "status": broker_ledger_result.get("status"),
            "collection_id": broker_ledger_result.get("collection_id"),
            "state_path": broker_ledger_result.get("state_path"),
            "production_impact": "measurement_only",
        }
        if broker_ledger_result
        else {
            "status": "preview_or_injected_state_not_persisted",
            "collection_id": (
                execution_capture.get("collection_id") if execution_capture else None
            ),
            "state_path": None,
            "production_impact": "measurement_only",
        }
    )

    target = Path(DEFAULT_PREVIEW_PATH if preview else out_path)
    atomic_write_text(json.dumps(payload, indent=4, sort_keys=False) + "\n", target)
    n = sum(len(payload.get(s) or []) for s in ("core_positions", "positions", "observations"))
    print(f"[moomoo_open_positions] wrote {n} positions -> {target} "
          f"(preview={preview}, untagged={untagged})")
    return {
        "status": "written",
        "wrote": str(target),
        "untagged": untagged,
        "payload": payload,
        "broker_execution_ledger": broker_ledger_result,
        "account_snapshot_status": account_snapshot_status,
        "account_values_as_of": payload.get("account_values_as_of"),
    }


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
