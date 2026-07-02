"""Default-off Moomoo daily main capital-flow accumulation paper sleeve.

Shared helper for exp-20260702-019. It materializes the Moomoo
``get_capital_flow(period_type=DAY)`` historical daily net main-flow archive as
a versioned local surface, and exposes ONE candidate rule used by BOTH the
historical replay and the daily default-off snapshot:

    signal day T admits ticker X when the (X, T) flow row exists with
    ``main_in_flow > 0``, the standard liquidity guards pass (close >= $10,
    20d avg dollar volume >= $50M), and 20d SPY-relative return is
    non-negative; candidates rank by main_in_flow / adv20 (main-flow ratio),
    top-1 per day, next-open paper entry, 10-trading-day close exit.

The sleeve emits candidates, paper ledger state, and attribution metadata
only; it never emits live orders and never changes core signal generation,
ranking, sizing, exits, LLM, or news behavior (``trade_enabled=False``).

Source boundary (recorded, not worked around): the vendor keeps a rolling
~1-year history, so ``old_thin`` (2024-10-02..2025-04-22) cannot be replayed
and ``mid_weak`` is only covered from the archive's earliest date
(2025-07-02 at first materialization). The rolling window erodes daily; the
archive preserves rows the vendor will drop.
"""

from __future__ import annotations

import json
import math
import sys
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_QUANT_DIR = Path(__file__).resolve().parent
if str(_QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(_QUANT_DIR))

try:
    from constants import ROUND_TRIP_COST_PCT
    from data_paths import atomic_write_text, data_artifact_path
    from fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage
    from volume_breadth_breakout_paper_sleeve import (
        _close_return,
        _date10,
        _exact_asof_price_maps,
        _float_or_none,
        _index_on_date,
        _money,
        _normalise_ohlcv_rows,
        _pnl,
        _return_pct,
        _safe,
        _single_ticker_positive_share,
        _top5_positive_share,
    )
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant.constants import ROUND_TRIP_COST_PCT
    from quant.data_paths import atomic_write_text, data_artifact_path
    from quant.fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage
    from quant.volume_breadth_breakout_paper_sleeve import (
        _close_return,
        _date10,
        _exact_asof_price_maps,
        _float_or_none,
        _index_on_date,
        _money,
        _normalise_ohlcv_rows,
        _pnl,
        _return_pct,
        _safe,
        _single_ticker_positive_share,
        _top5_positive_share,
    )


SLEEVE_NAME = "MOOMOO_CAPITAL_FLOW_ACCUMULATION_PAPER"
RULE_VERSION = "moomoo_capital_flow_day_main_inflow_top1_v1"
SOURCE_RULE_VERSION = "moomoo_get_capital_flow_day_archive_v1"
STATE_SCHEMA_VERSION = 1

MOOMOO_HOST = "127.0.0.1"
MOOMOO_PORT = 11111
# Historical quote endpoints share a request quota; keep a polite pacing gap.
FETCH_PACING_SECONDS = 1.1

DEFAULT_ROWS_PATH = data_artifact_path("moomoo_capital_flow_day_rows")
DEFAULT_MANIFEST_PATH = data_artifact_path("moomoo_capital_flow_day_manifest")
DEFAULT_STATE_PATH = data_artifact_path("moomoo_capital_flow_paper_state")
DEFAULT_SNAPSHOT_LOG_PATH = data_artifact_path("moomoo_capital_flow_paper_snapshots")

EXCLUDED_TICKERS = {
    "GLD",
    "IAU",
    "IEF",
    "IWM",
    "QQQ",
    "SLV",
    "SPY",
    "TLT",
    "UUP",
    "USO",
    "XLE",
    "XLP",
    "XLU",
    "XLV",
}

DEFAULT_CONFIG = {
    "enabled": False,
    "paper_enabled": True,
    "trade_enabled": False,
    "paper_notional_usd": 4_000.0,
    "relative_strength_days": 20,
    "dollar_volume_days": 20,
    "min_close": 10.0,
    "min_avg_dollar_volume_20": 50_000_000.0,
    "min_main_in_flow": 0.0,
    "min_ret20_excess_spy": 0.0,
    "daily_entry_slots": 1,
    "max_active_positions": 5,
    "hold_days": 10,
    "same_ticker_cooldown_days": 10,
    "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
    "max_archive_staleness_days": 3,
    "allow_network_fetch": True,
    "block_same_day_core_overlap": True,
    "forward_gate_min_closed_trades": 20,
    "forward_gate_positive_net_pnl": True,
    "forward_gate_min_win_rate": 0.50,
    "forward_gate_max_single_ticker_positive_share": 0.40,
    "forward_gate_max_top5_positive_share": 0.70,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Archive: fetch / load / save / refresh
# ---------------------------------------------------------------------------


def _flow_row_key(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("ticker") or "").upper(), str(row.get("flow_date") or ""))


def normalise_flow_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").upper().strip()
        flow_date = _date10(row.get("flow_date") or row.get("capital_flow_item_time"))
        main_in_flow = _float_or_none(row.get("main_in_flow"))
        if not ticker or not flow_date or main_in_flow is None:
            continue
        out.append(
            {
                "ticker": ticker,
                "flow_date": flow_date,
                "in_flow": _float_or_none(row.get("in_flow")),
                "main_in_flow": main_in_flow,
                "super_in_flow": _float_or_none(row.get("super_in_flow")),
                "big_in_flow": _float_or_none(row.get("big_in_flow")),
                "mid_in_flow": _float_or_none(row.get("mid_in_flow")),
                "sml_in_flow": _float_or_none(row.get("sml_in_flow")),
                "last_valid_time": row.get("last_valid_time"),
                "fetched_at": row.get("fetched_at"),
                "source": row.get("source") or "moomoo_get_capital_flow_day",
            }
        )
    out.sort(key=_flow_row_key)
    return out


def load_moomoo_capital_flow_rows(
    path: Path | str = DEFAULT_ROWS_PATH,
) -> list[dict[str, Any]]:
    rows_path = Path(path)
    if not rows_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with rows_path.open("r", encoding="utf-8-sig") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    except OSError:
        return []
    return normalise_flow_rows(rows)


def save_moomoo_capital_flow_archive(
    *,
    rows: list[dict[str, Any]],
    rows_path: Path | str = DEFAULT_ROWS_PATH,
    manifest_path: Path | str = DEFAULT_MANIFEST_PATH,
    fetch_log: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rows = normalise_flow_rows(rows)
    lines = "".join(json.dumps(_safe(row), sort_keys=True) + "\n" for row in rows)
    atomic_write_text(lines, Path(rows_path))
    dates = [row["flow_date"] for row in rows]
    manifest = {
        "schema_version": STATE_SCHEMA_VERSION,
        "source": "moomoo OpenAPI OpenQuoteContext.get_capital_flow",
        "endpoint": "get_capital_flow(period_type=DAY, start, end)",
        "rule_version": SOURCE_RULE_VERSION,
        "updated_at": utc_now_iso(),
        "row_count": len(rows),
        "ticker_count": len({row["ticker"] for row in rows}),
        "earliest_flow_date": min(dates) if dates else None,
        "latest_flow_date": max(dates) if dates else None,
        "pit_boundary": (
            "Rows fetched after their flow dates carry fetched_at as the honest "
            "vendor_asof; the vendor keeps a rolling ~1-year history, so dates "
            "before the first materialization (2026-07-02 run: earliest "
            "2025-07-02) are unrecoverable. Daily refreshes append same-day "
            "rows, which are PIT for forward use."
        ),
        "fetch_log_tail": (fetch_log or [])[-20:],
    }
    atomic_write_text(
        json.dumps(_safe(manifest), indent=2, sort_keys=True) + "\n",
        Path(manifest_path),
    )
    return manifest


def fetch_moomoo_capital_flow_day_rows(
    *,
    tickers: list[str] | set[str],
    start: str,
    end: str,
    host: str = MOOMOO_HOST,
    port: int = MOOMOO_PORT,
    pacing_seconds: float = FETCH_PACING_SECONDS,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Fetch DAY capital-flow rows for ``tickers`` from a live OpenD.

    Returns ``(rows, fetch_log)``. Failures are recorded per ticker in the
    fetch log; a dead OpenD yields no rows and a single connection error entry.
    """
    fetch_log: list[dict[str, Any]] = []
    try:
        from moomoo import OpenQuoteContext, PeriodType, RET_OK  # type: ignore
    except Exception as exc:  # noqa: BLE001 - SDK absence is a data status
        return [], [{"error": f"moomoo_sdk_unavailable: {type(exc).__name__}: {exc}"}]

    try:
        ctx = OpenQuoteContext(host=host, port=port)
    except Exception as exc:  # noqa: BLE001 - OpenD absence is a data status
        return [], [{"error": f"opend_unavailable: {type(exc).__name__}: {exc}"}]

    fetched_at = utc_now_iso()
    rows: list[dict[str, Any]] = []
    try:
        period_type = getattr(PeriodType, "DAY", "DAY")
        for raw_ticker in sorted({str(t).upper() for t in tickers if t}):
            code = raw_ticker if "." in raw_ticker else f"US.{raw_ticker}"
            entry: dict[str, Any] = {"ticker": raw_ticker, "code": code, "row_count": 0}
            try:
                ret, data = ctx.get_capital_flow(
                    code, period_type=period_type, start=start, end=end
                )
                if ret != RET_OK:
                    entry["error"] = str(data)
                else:
                    records = data.to_dict("records") if hasattr(data, "to_dict") else []
                    for record in records:
                        flow_date = _date10(record.get("capital_flow_item_time"))
                        if not flow_date:
                            continue
                        rows.append(
                            {
                                "ticker": raw_ticker,
                                "flow_date": flow_date,
                                "in_flow": _float_or_none(record.get("in_flow")),
                                "main_in_flow": _float_or_none(record.get("main_in_flow")),
                                "super_in_flow": _float_or_none(record.get("super_in_flow")),
                                "big_in_flow": _float_or_none(record.get("big_in_flow")),
                                "mid_in_flow": _float_or_none(record.get("mid_in_flow")),
                                "sml_in_flow": _float_or_none(record.get("sml_in_flow")),
                                "last_valid_time": str(record.get("last_valid_time") or ""),
                                "fetched_at": fetched_at,
                                "source": "moomoo_get_capital_flow_day",
                            }
                        )
                    entry["row_count"] = len(records)
            except Exception as exc:  # noqa: BLE001 - per-ticker fault isolation
                entry["error"] = f"{type(exc).__name__}: {exc}"
            fetch_log.append(entry)
            time.sleep(max(0.0, pacing_seconds))
    finally:
        try:
            ctx.close()
        except Exception:  # noqa: BLE001
            pass
    return normalise_flow_rows(rows), fetch_log


def refresh_moomoo_capital_flow_archive(
    *,
    existing_rows: list[dict[str, Any]],
    tickers: list[str] | set[str],
    as_of: str,
    max_staleness_days: int = 3,
    fetch_fn=None,
    save: bool = True,
    rows_path: Path | str = DEFAULT_ROWS_PATH,
    manifest_path: Path | str = DEFAULT_MANIFEST_PATH,
) -> tuple[list[dict[str, Any]], str, list[dict[str, Any]]]:
    """Merge newly published flow rows into the archive when it is stale.

    Existing rows are never dropped (the vendor's rolling window forgets, the
    archive must not). Fetch failures keep the stale archive.
    """
    fetch = fetch_fn or fetch_moomoo_capital_flow_day_rows
    existing = normalise_flow_rows(existing_rows or [])
    as_of_date = _date10(as_of)
    if not as_of_date:
        return existing, "invalid_as_of_date", []

    if existing:
        newest = max(row["flow_date"] for row in existing)
        try:
            staleness = (
                datetime.strptime(as_of_date, "%Y-%m-%d")
                - datetime.strptime(newest, "%Y-%m-%d")
            ).days
        except ValueError:
            staleness = max_staleness_days + 1
        if staleness <= int(max_staleness_days):
            return existing, "local_archive_fresh", []
        fetch_start = newest
    else:
        # First materialization: pull the vendor's full rolling window.
        fetch_start = "2024-01-01"

    new_rows, fetch_log = fetch(tickers=tickers, start=fetch_start, end=as_of_date)
    if not new_rows:
        status = "local_archive_stale_refresh_empty" if existing else "network_fetch_empty"
        return existing, status, fetch_log

    merged = {_flow_row_key(row): row for row in existing}
    added = 0
    for row in new_rows:
        key = _flow_row_key(row)
        if key not in merged:
            added += 1
            merged[key] = row
        # Never overwrite an earlier-fetched row: the first observation is the
        # most PIT-faithful one we have.
    rows = normalise_flow_rows(list(merged.values()))
    if save:
        save_moomoo_capital_flow_archive(
            rows=rows, rows_path=rows_path, manifest_path=manifest_path, fetch_log=fetch_log
        )
    status = "local_archive_refreshed" if added else "local_archive_refresh_no_new_rows"
    if not existing:
        status = "network_fetch"
    return rows, status, fetch_log


def flow_rows_by_ticker(rows: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    """Index rows as ticker -> flow_date -> row."""
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for row in normalise_flow_rows(rows):
        out.setdefault(row["ticker"], {})[row["flow_date"]] = row
    return out


# ---------------------------------------------------------------------------
# Shared candidate rule (used by daily snapshot AND historical replay)
# ---------------------------------------------------------------------------


def _avg_dollar_volume(rows: list[dict[str, Any]], idx: int, days: int) -> float | None:
    if idx < days:
        return None
    values: list[float] = []
    for row in rows[idx - days:idx]:
        close = _float_or_none(row.get("close"))
        volume = _float_or_none(row.get("volume"))
        if close is None or volume is None or close <= 0 or volume <= 0:
            continue
        values.append(close * volume)
    if len(values) < days:
        return None
    return sum(values) / len(values)


def _inc(counter: dict[str, int], key: str) -> None:
    counter[key] = counter.get(key, 0) + 1


def build_moomoo_capital_flow_candidates(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    flow_by_ticker: dict[str, dict[str, dict[str, Any]]],
    tickers: list[str],
    as_of: str,
    same_day_core_tickers: set[str],
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """The ONE fixed candidate rule for this sleeve (rule_version above)."""
    config = _config(config)
    rejects: dict[str, int] = {}
    spy_rows = rows_by_ticker.get("SPY") or []
    spy_idx = _index_on_date(spy_rows, as_of)
    if spy_idx is None:
        return [], {"missing_spy_asof": len(tickers)}
    rs_days = int(config["relative_strength_days"])
    dv_days = int(config["dollar_volume_days"])
    min_idx = max(rs_days, dv_days)
    candidates: list[dict[str, Any]] = []
    for ticker in tickers:
        ticker = str(ticker).upper()
        if ticker in EXCLUDED_TICKERS:
            _inc(rejects, "excluded_ticker")
            continue
        flow = (flow_by_ticker.get(ticker) or {}).get(as_of)
        if flow is None:
            _inc(rejects, "missing_flow_row_asof")
            continue
        main_in_flow = _float_or_none(flow.get("main_in_flow"))
        if main_in_flow is None or main_in_flow <= float(config["min_main_in_flow"]):
            _inc(rejects, "main_in_flow_not_positive")
            continue

        rows = rows_by_ticker.get(ticker) or []
        idx = _index_on_date(rows, as_of)
        if idx is None or idx < min_idx or spy_idx < rs_days:
            _inc(rejects, "insufficient_history")
            continue
        close = _float_or_none(rows[idx].get("close"))
        if close is None or close < float(config["min_close"]):
            _inc(rejects, "price_below_threshold")
            continue
        avg_dollar_volume = _avg_dollar_volume(rows, idx, dv_days)
        if avg_dollar_volume is None or avg_dollar_volume < float(
            config["min_avg_dollar_volume_20"]
        ):
            _inc(rejects, "avg_dollar_volume_below_threshold")
            continue
        ret20 = _close_return(rows, idx - rs_days, idx)
        spy_ret20 = _close_return(spy_rows, spy_idx - rs_days, spy_idx)
        if ret20 is None or spy_ret20 is None:
            _inc(rejects, "missing_relative_strength")
            continue
        ret20_excess_spy = ret20 - spy_ret20
        if ret20_excess_spy < float(config["min_ret20_excess_spy"]):
            _inc(rejects, "ret20_excess_spy_below_threshold")
            continue

        same_ticker_core_overlap = ticker in same_day_core_tickers
        if config.get("block_same_day_core_overlap", True) and same_ticker_core_overlap:
            _inc(rejects, "same_ticker_core_overlap")
            continue

        main_flow_ratio = main_in_flow / avg_dollar_volume
        candidates.append(
            {
                "sleeve": SLEEVE_NAME,
                "ticker": ticker,
                "date": as_of,
                "signal_date": as_of,
                "strategy": "moomoo_capital_flow_accumulation_candidate_pool",
                "rule_version": RULE_VERSION,
                "source_rule_version": SOURCE_RULE_VERSION,
                "score": round(main_flow_ratio, 10),
                "main_flow_ratio": round(main_flow_ratio, 10),
                "main_in_flow": round(main_in_flow, 2),
                "in_flow": _float_or_none(flow.get("in_flow")),
                "super_in_flow": _float_or_none(flow.get("super_in_flow")),
                "big_in_flow": _float_or_none(flow.get("big_in_flow")),
                "flow_fetched_at": flow.get("fetched_at"),
                "close": round(close, 4),
                "avg_dollar_volume_20": round(avg_dollar_volume, 2),
                "ret20": round(ret20, 6),
                "spy_ret20": round(spy_ret20, 6),
                "ret20_excess_spy": round(ret20_excess_spy, 6),
                "same_ticker_core_overlap": same_ticker_core_overlap,
                "known_at": (
                    "after_signal_date_close_with_same_day_vendor_flow_before_"
                    "next_open_paper_entry"
                ),
                "intended_notional": float(config["paper_notional_usd"]),
                "trade_enabled": False,
                "alters_orders": False,
            }
        )
    candidates.sort(
        key=lambda row: (
            -float(row["score"]),
            -float(row["main_in_flow"]),
            row["ticker"],
        )
    )
    return candidates, rejects


# ---------------------------------------------------------------------------
# Historical replay (same rule, frozen windows)
# ---------------------------------------------------------------------------


def replay_moomoo_capital_flow_paper_trades(
    *,
    ohlcv_by_ticker: dict[str, Any],
    flow_rows: list[dict[str, Any]],
    start: str,
    end: str,
    config: dict[str, Any] | None = None,
    tickers: list[str] | None = None,
) -> dict[str, Any]:
    """Replay the sleeve rule over ``[start, end]`` and return settled trades.

    Entry is next-session open (with entry fill slippage); exit is the close of
    the ``hold_days``-th trading day after entry (with sell slippage); trades
    whose exit falls outside the window are reported as unsettled, not scored.
    """
    cfg = _config(config)
    rows_by_ticker = {
        str(ticker).upper(): _normalise_ohlcv_rows(rows)
        for ticker, rows in (ohlcv_by_ticker or {}).items()
    }
    spy_rows = rows_by_ticker.get("SPY") or []
    dates = [
        str(row.get("date"))
        for row in spy_rows
        if start <= str(row.get("date")) <= end
    ]
    flow_index = flow_rows_by_ticker(flow_rows)
    universe = sorted(
        tickers
        if tickers is not None
        else [t for t in rows_by_ticker if t not in EXCLUDED_TICKERS and t != "SPY"]
    )
    date_pos = { str(row.get("date")): i for i, row in enumerate(spy_rows) }

    trades: list[dict[str, Any]] = []
    unsettled: list[dict[str, Any]] = []
    reject_totals: dict[str, int] = {}
    daily_candidate_counts: dict[str, int] = {}
    next_allowed_pos_by_ticker: dict[str, int] = {}
    hold_days = int(cfg["hold_days"])
    cooldown = int(cfg["same_ticker_cooldown_days"])

    for as_of in dates:
        candidates, rejects = build_moomoo_capital_flow_candidates(
            rows_by_ticker=rows_by_ticker,
            flow_by_ticker=flow_index,
            tickers=universe,
            as_of=as_of,
            same_day_core_tickers=set(),
            config=cfg,
        )
        for key, value in rejects.items():
            reject_totals[key] = reject_totals.get(key, 0) + value
        if candidates:
            daily_candidate_counts[as_of] = len(candidates)
        pos = date_pos.get(as_of)
        if pos is None:
            continue
        used_today = 0
        for candidate in candidates:
            if used_today >= int(cfg["daily_entry_slots"]):
                break
            ticker = candidate["ticker"]
            if pos < next_allowed_pos_by_ticker.get(ticker, -1):
                reject_totals["same_ticker_cooldown"] = (
                    reject_totals.get("same_ticker_cooldown", 0) + 1
                )
                continue
            ticker_rows = rows_by_ticker.get(ticker) or []
            signal_idx = _index_on_date(ticker_rows, as_of)
            if signal_idx is None:
                continue
            entry_idx = signal_idx + 1
            exit_idx = entry_idx + hold_days
            if entry_idx >= len(ticker_rows):
                unsettled.append({**candidate, "unsettled_reason": "no_next_open_inside_window"})
                continue
            entry_row = ticker_rows[entry_idx]
            entry_date = str(entry_row.get("date"))
            if entry_date > end:
                unsettled.append({**candidate, "unsettled_reason": "entry_outside_window"})
                continue
            open_price = _float_or_none(entry_row.get("open"))
            if open_price is None or open_price <= 0:
                unsettled.append({**candidate, "unsettled_reason": "missing_next_open"})
                continue
            if exit_idx >= len(ticker_rows):
                unsettled.append({**candidate, "unsettled_reason": "exit_outside_window"})
                next_allowed_pos_by_ticker[ticker] = pos + cooldown
                used_today += 1
                continue
            exit_row = ticker_rows[exit_idx]
            exit_date = str(exit_row.get("date"))
            if exit_date > end:
                unsettled.append({**candidate, "unsettled_reason": "exit_outside_window"})
                next_allowed_pos_by_ticker[ticker] = pos + cooldown
                used_today += 1
                continue
            close_price = _float_or_none(exit_row.get("close"))
            if close_price is None or close_price <= 0:
                unsettled.append({**candidate, "unsettled_reason": "missing_exit_close"})
                next_allowed_pos_by_ticker[ticker] = pos + cooldown
                used_today += 1
                continue
            entry_price = apply_entry_fill(open_price)
            exit_price = apply_slippage(close_price, SLIPPAGE_BPS_TARGET, "sell")
            notional = float(cfg["paper_notional_usd"])
            pnl = _pnl(entry_price, exit_price, notional, float(cfg["round_trip_cost_pct"]))
            trades.append(
                {
                    "source": SLEEVE_NAME,
                    "source_rule_version": RULE_VERSION,
                    "ticker": ticker,
                    "date": as_of,
                    "signal_date": as_of,
                    "entry_date": entry_date,
                    "exit_date": exit_date,
                    "entry_price": round(entry_price, 4),
                    "exit_price": round(exit_price, 4),
                    "hold_days": hold_days,
                    "paper_notional_usd": notional,
                    "pnl": round(pnl, 2) if pnl is not None else None,
                    "pnl_pct_net": _return_pct(
                        entry_price, exit_price, float(cfg["round_trip_cost_pct"])
                    ),
                    "main_flow_ratio": candidate["main_flow_ratio"],
                    "main_in_flow": candidate["main_in_flow"],
                    "ret20_excess_spy": candidate["ret20_excess_spy"],
                    "avg_dollar_volume_20": candidate["avg_dollar_volume_20"],
                    "rank_policy": (
                        "top1 per signal date by main_flow_ratio, then main_in_flow, "
                        "then ticker"
                    ),
                    "trade_enabled": False,
                }
            )
            next_allowed_pos_by_ticker[ticker] = pos + cooldown
            used_today += 1

    return {
        "rule_version": RULE_VERSION,
        "start": start,
        "end": end,
        "trades": trades,
        "unsettled": unsettled,
        "reject_totals": dict(sorted(reject_totals.items())),
        "signal_dates_with_candidates": len(daily_candidate_counts),
        "max_daily_candidate_count": (
            max(daily_candidate_counts.values()) if daily_candidate_counts else 0
        ),
        "flow_coverage": {
            "first_flow_date_in_window": min(
                (
                    d
                    for by_date in flow_index.values()
                    for d in by_date
                    if start <= d <= end
                ),
                default=None,
            ),
            "last_flow_date_in_window": max(
                (
                    d
                    for by_date in flow_index.values()
                    for d in by_date
                    if start <= d <= end
                ),
                default=None,
            ),
        },
    }


# ---------------------------------------------------------------------------
# Daily default-off snapshot (state machine mirrors the replay semantics)
# ---------------------------------------------------------------------------


def empty_moomoo_capital_flow_paper_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "updated_at": None,
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "skipped_entries": [],
    }


def load_moomoo_capital_flow_paper_state(
    path: Path | str = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_moomoo_capital_flow_paper_state()
    try:
        with state_path.open("r", encoding="utf-8-sig") as handle:
            payload = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return empty_moomoo_capital_flow_paper_state()
    state = empty_moomoo_capital_flow_paper_state()
    if isinstance(payload, dict):
        state.update(payload)
    _normalise_state(state)
    return state


def save_moomoo_capital_flow_paper_state(
    state: dict[str, Any],
    path: Path | str = DEFAULT_STATE_PATH,
) -> None:
    state["updated_at"] = utc_now_iso()
    atomic_write_text(
        json.dumps(_safe(state), indent=2, sort_keys=True) + "\n", Path(path)
    )


def append_moomoo_capital_flow_paper_snapshot(
    snapshot: dict[str, Any],
    path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_safe(snapshot), sort_keys=True) + "\n")


def empty_moomoo_capital_flow_paper_sleeve_snapshot(
    as_of: str, reason: str
) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "asof_date": _date10(as_of),
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": False,
        "trade_enabled": False,
        "candidate_count": 0,
        "raw_candidate_count": 0,
        "rejected_candidate_count": 0,
        "new_pending_count": 0,
        "filled_count": 0,
        "closed_count_today": 0,
        "pending_count": 0,
        "open_position_count": 0,
        "closed_position_count": 0,
        "realized_pnl_to_date": 0.0,
        "unrealized_pnl": 0.0,
        "data_source": {"status": reason, "flow_row_count": 0},
        "candidate_universe": {"status": reason, "ticker_count": 0},
        "forward_paper_gate": {"passed": False, "status": "blocked", "reasons": [reason]},
        "production_impact": _production_impact(),
        "error": reason,
    }


def build_moomoo_capital_flow_paper_sleeve_snapshot(
    *,
    as_of: str,
    ohlcv_by_ticker: dict[str, Any] | None = None,
    candidate_universe: dict[str, Any] | list[str] | None = None,
    flow_rows: list[dict[str, Any]] | None = None,
    same_day_core_tickers: set[str] | list[str] | None = None,
    open_prices: dict[str, Any] | None = None,
    current_prices: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    persist: bool = True,
    state_path: Path | str = DEFAULT_STATE_PATH,
    snapshot_log_path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> dict[str, Any]:
    cfg = _config(config)
    as_of_date = _date10(as_of)
    try:
        from us_market_calendar import is_us_equity_session
    except ImportError:  # pragma: no cover - package-style imports in tests
        from quant.us_market_calendar import is_us_equity_session

    if not is_us_equity_session(as_of_date):
        return empty_moomoo_capital_flow_paper_sleeve_snapshot(
            as_of_date, "non_us_equity_session"
        )
    rows_by_ticker = {
        str(ticker).upper(): _normalise_ohlcv_rows(rows)
        for ticker, rows in (ohlcv_by_ticker or {}).items()
    }
    if not rows_by_ticker:
        return empty_moomoo_capital_flow_paper_sleeve_snapshot(as_of_date, "missing_ohlcv")
    if _index_on_date(rows_by_ticker.get("SPY") or [], as_of_date) is None:
        return empty_moomoo_capital_flow_paper_sleeve_snapshot(as_of_date, "missing_spy_asof")

    universe = _normalise_candidate_universe(candidate_universe, rows_by_ticker)
    candidate_tickers = {
        ticker
        for ticker in set(universe.get("tickers") or [])
        if ticker in rows_by_ticker and ticker not in EXCLUDED_TICKERS
    }

    flow_source_status = "provided"
    fetch_log: list[dict[str, Any]] = []
    if flow_rows is None:
        flow_rows = load_moomoo_capital_flow_rows()
        flow_source_status = "local_archive" if flow_rows else "missing_local_archive"
        if cfg.get("allow_network_fetch", True):
            flow_rows, flow_source_status, fetch_log = refresh_moomoo_capital_flow_archive(
                existing_rows=flow_rows,
                tickers=candidate_tickers,
                as_of=as_of_date,
                max_staleness_days=int(cfg["max_archive_staleness_days"]),
            )
    flow_rows = normalise_flow_rows(flow_rows or [])
    if not flow_rows:
        # An empty archive must not freeze the paper ledger: open positions and
        # pending fills still advance; today just produces zero candidates.
        flow_source_status = f"{flow_source_status}_empty"

    working_state = deepcopy(
        state if state is not None else load_moomoo_capital_flow_paper_state(state_path)
    )
    _normalise_state(working_state)

    current, opens = _exact_asof_price_maps(
        rows_by_ticker,
        as_of=as_of_date,
        current_prices=current_prices,
        open_prices=open_prices,
    )
    closed_today = _advance_open_positions(
        working_state, as_of=as_of_date, current_prices=current, config=cfg
    )
    filled_today, skipped_today = _fill_pending_entries(
        working_state,
        as_of=as_of_date,
        open_prices=opens,
        current_prices=current,
        config=cfg,
    )

    core_tickers = {str(t).upper() for t in (same_day_core_tickers or []) if t}
    candidates, reject_counts = build_moomoo_capital_flow_candidates(
        rows_by_ticker=rows_by_ticker,
        flow_by_ticker=flow_rows_by_ticker(flow_rows),
        tickers=sorted(candidate_tickers),
        as_of=as_of_date,
        same_day_core_tickers=core_tickers,
        config=cfg,
    )

    open_positions = working_state.get("open_positions") or []
    existing_open_tickers = {str(row.get("ticker") or "").upper() for row in open_positions}
    pending_entries = working_state.get("pending_entries") or []
    existing_decision_ids = {str(row.get("decision_id") or "") for row in pending_entries}
    pending_tickers = {str(row.get("ticker") or "").upper() for row in pending_entries}
    # Same-day idempotency (exp-20260701-004): pending entries already created
    # for this as_of consume today's entry slots on a re-run.
    pending_for_asof = sum(
        1 for row in pending_entries if str(row.get("created_asof") or "") == as_of_date
    )
    slots_left = max(0, int(cfg["daily_entry_slots"]) - pending_for_asof)
    room = max(0, int(cfg["max_active_positions"]) - len(open_positions))

    new_pending: list[dict[str, Any]] = []
    for candidate in candidates:
        if slots_left <= 0 or room <= 0:
            break
        ticker = str(candidate.get("ticker") or "").upper()
        decision_id = f"{SLEEVE_NAME}:{RULE_VERSION}:{as_of_date}:{ticker}"
        if decision_id in existing_decision_ids:
            _inc(reject_counts, "duplicate_same_day_decision")
            continue
        if ticker in existing_open_tickers or ticker in pending_tickers:
            _inc(reject_counts, "already_open_or_pending")
            continue
        entry = {
            "decision_id": decision_id,
            "sleeve": SLEEVE_NAME,
            "ticker": ticker,
            "created_asof": as_of_date,
            "status": "pending_next_open",
            "notional": float(candidate.get("intended_notional") or cfg["paper_notional_usd"]),
            "candidate": deepcopy(candidate),
            "trade_enabled": False,
            "alters_orders": False,
        }
        working_state["pending_entries"].append(entry)
        new_pending.append(entry)
        existing_decision_ids.add(decision_id)
        pending_tickers.add(ticker)
        slots_left -= 1
        room -= 1

    closed = working_state.get("closed_positions") or []
    open_positions = working_state.get("open_positions") or []
    gate = _forward_paper_gate(closed, cfg)

    snapshot = {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "asof_date": as_of_date,
        "generated_at": utc_now_iso(),
        "enabled": bool(cfg["paper_enabled"]),
        "paper_enabled": bool(cfg["paper_enabled"]),
        "trade_enabled": False,
        "candidate_count": len(candidates[: int(cfg["daily_entry_slots"])]),
        "raw_candidate_count": len(candidates),
        "rejected_candidate_count": sum(reject_counts.values()),
        "new_pending_count": len(new_pending),
        "filled_count": len(filled_today),
        "closed_count_today": len(closed_today),
        "pending_count": len(working_state.get("pending_entries") or []),
        "open_position_count": len(open_positions),
        "closed_position_count": len(closed),
        "realized_pnl_to_date": round(sum(_money(row.get("pnl")) for row in closed), 2),
        "unrealized_pnl": round(
            sum(_money(row.get("unrealized_pnl")) for row in open_positions), 2
        ),
        "data_source": {
            "status": "ok",
            "flow_status": flow_source_status,
            "flow_row_count": len(flow_rows),
            "flow_fetch_log_count": len(fetch_log),
            "covered_ticker_count": len(candidate_tickers),
        },
        "candidate_universe": {
            "status": universe.get("status"),
            "ticker_count": len(candidate_tickers),
            "tickers_sample": sorted(candidate_tickers)[:25],
        },
        "candidate_reject_counts": dict(sorted(reject_counts.items())),
        "candidates": _safe(candidates[: int(cfg["daily_entry_slots"])]),
        "new_pending_entries": _safe(new_pending),
        "filled_entries_today": _safe(filled_today),
        "skipped_entries_today": _safe(skipped_today),
        "closed_positions_today": _safe(closed_today),
        "open_positions": _safe(open_positions),
        "pending_entries": _safe(working_state.get("pending_entries") or []),
        "forward_paper_gate": gate,
        "production_impact": _production_impact(),
    }

    if persist:
        save_moomoo_capital_flow_paper_state(working_state, state_path)
        append_moomoo_capital_flow_paper_snapshot(snapshot, snapshot_log_path)
    return snapshot


def prep_and_build_moomoo_capital_flow_paper_sleeve_snapshot(
    *,
    as_of: str,
    ohlcv_dict: dict,
    spy_ohlcv=None,
    same_day_core_tickers=None,
    open_prices=None,
    current_prices=None,
):
    ohlcv = dict(ohlcv_dict)
    if spy_ohlcv is not None:
        ohlcv["SPY"] = spy_ohlcv
    candidate_universe = {
        "status": "daily_data_universe",
        "tickers": sorted(
            t
            for t, f in ohlcv.items()
            if f is not None and str(t).upper() != "SPY"
        ),
    }
    return build_moomoo_capital_flow_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=ohlcv,
        candidate_universe=candidate_universe,
        same_day_core_tickers=same_day_core_tickers,
        open_prices=open_prices,
        current_prices=current_prices,
    )


def _advance_open_positions(
    state: dict[str, Any],
    *,
    as_of: str,
    current_prices: dict[str, float],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    still_open: list[dict[str, Any]] = []
    closed_today: list[dict[str, Any]] = []
    for position in state.get("open_positions") or []:
        if not isinstance(position, dict):
            continue
        ticker = str(position.get("ticker") or "").upper()
        current_price = current_prices.get(ticker)
        if current_price is None:
            still_open.append(position)
            continue
        observed_days = int(position.get("observed_trading_days") or 0) + 1
        position["observed_trading_days"] = observed_days
        exit_mark = apply_slippage(current_price, SLIPPAGE_BPS_TARGET, "sell")
        position["last_price"] = current_price
        position["last_price_asof"] = as_of
        position["unrealized_pnl"] = _pnl(
            position.get("entry_price"),
            exit_mark,
            position.get("notional"),
            float(config["round_trip_cost_pct"]),
        )
        if observed_days >= int(config["hold_days"]):
            closed = deepcopy(position)
            closed.update(
                {
                    "status": "closed",
                    "exit_date": as_of,
                    "exit_price": exit_mark,
                    "exit_reason": "max_hold_days",
                    "pnl": _pnl(
                        position.get("entry_price"),
                        exit_mark,
                        position.get("notional"),
                        float(config["round_trip_cost_pct"]),
                    ),
                    "return_pct_net": _return_pct(
                        position.get("entry_price"),
                        exit_mark,
                        float(config["round_trip_cost_pct"]),
                    ),
                    "trade_enabled": False,
                }
            )
            closed_today.append(closed)
            state["closed_positions"].append(closed)
        else:
            still_open.append(position)
    state["open_positions"] = still_open
    return closed_today


def _fill_pending_entries(
    state: dict[str, Any],
    *,
    as_of: str,
    open_prices: dict[str, float],
    current_prices: dict[str, float],
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    still_pending: list[dict[str, Any]] = []
    filled: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for entry in sorted(
        state.get("pending_entries") or [],
        key=lambda row: (str(row.get("created_asof") or ""), str(row.get("ticker") or "")),
    ):
        if not isinstance(entry, dict):
            continue
        ticker = str(entry.get("ticker") or "").upper()
        if str(entry.get("created_asof") or "") >= as_of:
            still_pending.append(entry)
            continue
        open_price = open_prices.get(ticker)
        if open_price is None:
            skipped_entry = deepcopy(entry)
            skipped_entry.update(
                {
                    "status": "skipped_missing_next_open",
                    "skipped_asof": as_of,
                    "trade_enabled": False,
                }
            )
            skipped.append(skipped_entry)
            state["skipped_entries"].append(skipped_entry)
            continue
        entry_price = apply_entry_fill(open_price)
        notional = _float_or_none(entry.get("notional")) or float(
            config["paper_notional_usd"]
        )
        candidate = entry.get("candidate") or {}
        position = {
            "decision_id": entry.get("decision_id"),
            "sleeve": SLEEVE_NAME,
            "ticker": ticker,
            "strategy": "moomoo_capital_flow_accumulation_candidate_pool",
            "entry_date": as_of,
            "entry_price": entry_price,
            "decision_close_price": candidate.get("close"),
            "notional": notional,
            "shares": round(notional / entry_price, 6) if entry_price else None,
            "observed_trading_days": 0,
            "hold_days": int(config["hold_days"]),
            "last_price": current_prices.get(ticker),
            "status": "open",
            "candidate": deepcopy(candidate),
            "trade_enabled": False,
        }
        if current_prices.get(ticker) and entry_price:
            position["unrealized_pnl"] = _pnl(
                entry_price,
                apply_slippage(current_prices[ticker], SLIPPAGE_BPS_TARGET, "sell"),
                position["notional"],
                float(config["round_trip_cost_pct"]),
            )
        filled.append(position)
        state["open_positions"].append(position)
    state["pending_entries"] = still_pending
    return filled, skipped


def _forward_paper_gate(
    closed_positions: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    realized = round(sum(_money(row.get("pnl")) for row in closed_positions), 2)
    wins = sum(1 for row in closed_positions if _money(row.get("pnl")) > 0)
    win_rate = round(wins / len(closed_positions), 4) if closed_positions else None
    single_share = _single_ticker_positive_share(closed_positions)
    top5_share = _top5_positive_share(closed_positions)
    checks = {
        "min_closed_trades": len(closed_positions)
        >= int(config["forward_gate_min_closed_trades"]),
        "positive_net_pnl": realized > 0
        if config.get("forward_gate_positive_net_pnl", True)
        else True,
        "min_win_rate": win_rate is not None
        and win_rate >= float(config["forward_gate_min_win_rate"]),
        "max_single_ticker_positive_share": single_share is not None
        and single_share <= float(config["forward_gate_max_single_ticker_positive_share"]),
        "max_top5_positive_share": top5_share is not None
        and top5_share <= float(config["forward_gate_max_top5_positive_share"]),
    }
    reasons = [name for name, passed in checks.items() if not passed]
    return {
        "passed": not reasons,
        "status": "passed" if not reasons else "blocked",
        "reasons": reasons,
        "checks": checks,
        "metrics": {
            "closed_trades": len(closed_positions),
            "realized_pnl": realized,
            "win_rate": win_rate,
            "single_ticker_positive_share": single_share,
            "top5_positive_share": top5_share,
        },
        "trade_enabled_after_gate": False,
    }


def _normalise_candidate_universe(
    value: dict[str, Any] | list[str] | None,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    if isinstance(value, list):
        return {
            "status": "provided",
            "tickers": sorted({str(item).upper() for item in value if item}),
        }
    if isinstance(value, dict):
        tickers = {str(item).upper() for item in value.get("tickers") or [] if item}
        return {"status": value.get("status") or "provided", "tickers": sorted(tickers)}
    return {
        "status": "default_rows_by_ticker",
        "tickers": sorted(
            ticker for ticker in rows_by_ticker if ticker not in EXCLUDED_TICKERS
        ),
    }


def _normalise_state(state: dict[str, Any]) -> None:
    state.setdefault("schema_version", STATE_SCHEMA_VERSION)
    state.setdefault("sleeve", SLEEVE_NAME)
    state.setdefault("pending_entries", [])
    state.setdefault("open_positions", [])
    state.setdefault("closed_positions", [])
    state.setdefault("skipped_entries", [])


def _config(config: dict[str, Any] | None) -> dict[str, Any]:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    cfg["enabled"] = False
    cfg["trade_enabled"] = False
    return cfg


def _production_impact() -> dict[str, Any]:
    return {
        "shared_policy_changed": True,
        "backtester_adapter_changed": False,
        "run_adapter_changed": True,
        "replay_only": False,
        "default_off_paper_only": True,
        "production_orders_changed": False,
        "production_watchlist_changed": False,
        "trade_enabled": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "parity_rule": "shared_moomoo_capital_flow_paper_adapter_v1",
    }
