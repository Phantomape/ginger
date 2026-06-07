"""Default-off broad-universe PEAD paper sleeve.

exp-20260604-021: PEAD_BROAD_UNIVERSE_PAPER (original design, ~80-90 tickers)
exp-20260607-003: PEAD_BROAD_500_TICKER_EARNINGS_EXPANSION
  - Earnings snapshot expanded from ~44 to ~500 S&P 500 adjacent tickers
    via quant/fetch_broad_earnings_snapshot.py (run daily after run.py)
  - OHLCV for the ~500 tickers loaded from warehouse in run.py
  - Sleeve code unchanged; expansion is purely data-layer (snapshot + OHLCV)
  - Expected: ~60-80 PEAD events/quarter → Gate 5 in ~10 weeks

Design intent:
Surfaces forward earnings-drift candidates from a wider universe
(~500 S&P 500 adjacent tickers via warehouse OHLCV + broad earnings snapshot)
without the MA50/RS20/close-location/pre-event-underpricing filters that narrow
the existing POST_EARNINGS_UNDERPRICED_DRIFT_PAPER sleeve to an
already-trending subpopulation.

Single causal variable being tested:
broad_universe_eps_surprise_only_pead_no_rs_ma50_prefilters

Trigger conditions, all required:
- EPS surprise, latest quarter, >= 5%
- Price >= $5 on event_confirmed_date
- Avg daily dollar volume, 20d, >= $10M on event_confirmed_date
- Earnings-day gap <= 5%: abs(open / prev_close - 1) <= PEAD_MAX_EARNINGS_DAY_GAP_PCT

Gap threshold rationale (2026-06-06):
5% was chosen (over the original 3%) because this universe includes large-cap tech
stocks (GOOG, MSFT, AMZN, META) that routinely gap 5-8% on earnings day. At 3%
roughly 60-70% of qualifying surprise events would be filtered out before any PEAD
observation begins, leaving sample counts too thin to reach Gate 5 (30+ closed trades)
within a reasonable time window. 5% retains moderate-gap events while still excluding
the largest-gap cases (≥5%) where the market has already fully priced the surprise
into the open and PEAD drift is unlikely. This threshold is sleeve-local and does not
affect the existing POST_EARNINGS_UNDERPRICED_DRIFT_PAPER sleeve.

Entry / hold:
- Candidate surfaced on event_confirmed_date with offset = 0
- Fill at next open, T+1 after confirmation date
- Hold 10 trading days, then exit at close

Paper-only:
trade_enabled is always False. This sleeve runs forward observations only
and never emits live orders. Gate 5, with 30+ closed forward trades, positive
net PnL, concentration check, and kill switch, must pass before any live
activation experiment is started.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_QUANT_DIR = Path(__file__).resolve().parent
if str(_QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(_QUANT_DIR))

try:
    from constants import ROUND_TRIP_COST_PCT
    from data_paths import data_artifact_path
    from fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage
    from volume_breadth_breakout_paper_sleeve import (
        _close_return,
        _date10,
        _exact_asof_price_maps,
        _float_or_none,
        _index_on_date,
        _money,
        _normalise_candidate_universe,
        _normalise_ohlcv_rows,
        _pnl,
        _positive_float,
        _return_pct,
        _round,
        _safe,
        _single_ticker_positive_share,
        _top5_positive_share,
    )
    from post_earnings_underpriced_drift_paper_sleeve import (
        load_earnings_snapshot_index,
        _earnings_date_count,
        _event_is_confirmed,
        _row_index,
        _surprise_context,
        _surprise_tail,
        _trading_dates,
    )
except ImportError:
    from quant.constants import ROUND_TRIP_COST_PCT
    from quant.data_paths import data_artifact_path
    from quant.fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage
    from quant.volume_breadth_breakout_paper_sleeve import (
        _close_return,
        _date10,
        _exact_asof_price_maps,
        _float_or_none,
        _index_on_date,
        _money,
        _normalise_candidate_universe,
        _normalise_ohlcv_rows,
        _pnl,
        _positive_float,
        _return_pct,
        _round,
        _safe,
        _single_ticker_positive_share,
        _top5_positive_share,
    )
    from quant.post_earnings_underpriced_drift_paper_sleeve import (
        load_earnings_snapshot_index,
        _earnings_date_count,
        _event_is_confirmed,
        _row_index,
        _surprise_context,
        _surprise_tail,
        _trading_dates,
    )


SLEEVE_NAME = "PEAD_BROAD_UNIVERSE_PAPER"
RULE_VERSION = "pead_broad_universe_paper_sleeve_v1"
STATE_SCHEMA_VERSION = 1

DEFAULT_STATE_PATH = data_artifact_path("pead_broad_universe_paper_state")
DEFAULT_SNAPSHOT_LOG_PATH = data_artifact_path("pead_broad_universe_paper_snapshots")

# Gap-cancel threshold for this sleeve (sleeve-local, does not affect any other strategy).
# Set to 5% (not the 3% in the original design sketch) because large-cap tech stocks in
# this universe routinely gap 5-8% on earnings day; at 3% roughly 60-70% of qualifying
# EPS-surprise events would be discarded, starving Gate 5 sample accumulation.
# Rationale recorded in experiments/tickets/exp-20260604-021.json (2026-06-06).
PEAD_MAX_EARNINGS_DAY_GAP_PCT: float = 0.05

EXCLUDED_TICKERS = {
    "ARKX",
    "GLD",
    "IAU",
    "IEF",
    "IWM",
    "QQQ",
    "SLV",
    "SPY",
    "TLT",
    "UFO",
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
    # Trigger: EPS surprise
    "min_latest_surprise_pct": 5.0,
    "min_avg_historical_surprise_pct": 0.0,
    "min_positive_surprise_count": 1,
    "min_surprise_history_count": 1,
    # Event confirmation window (reuse existing snapshot-transition logic)
    "min_reset_dte": 20,
    "max_pre_reset_dte": 7,
    # Offset: 0 = signal on event_confirmed_date, fill at next open (T+1)
    "recent_signal_days_min": 0,
    "recent_signal_days_max": 0,
    # Liquidity filters
    "avg_dollar_volume_days": 20,
    "min_avg_dollar_volume_20d": 10_000_000.0,   # $10M
    # Price filter
    "min_price": 5.0,
    # Gap-cancel: skip if earnings-day gap > this threshold.
    # Uses PEAD_MAX_EARNINGS_DAY_GAP_PCT (5%) — sleeve-local, not a global constant.
    # See PEAD_MAX_EARNINGS_DAY_GAP_PCT docstring and ticket exp-20260604-021 for rationale.
    "max_earnings_day_gap_pct": PEAD_MAX_EARNINGS_DAY_GAP_PCT,
    # Position management
    "paper_notional_usd": 10_000.0,
    "daily_entry_slots": 3,
    "max_active_positions": 10,
    "hold_days": 10,
    "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
    # Forward gate thresholds (Gate 5)
    "forward_gate_min_closed_trades": 30,
    "forward_gate_positive_net_pnl": True,
    "forward_gate_min_win_rate": 0.45,
    "forward_gate_max_single_ticker_positive_share": 0.50,
    "forward_gate_max_top5_positive_share": 0.60,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def empty_pead_broad_universe_paper_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "updated_at": None,
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "skipped_entries": [],
    }


def load_pead_broad_universe_paper_state(
    path: Path | str = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_pead_broad_universe_paper_state()
    with state_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    state = empty_pead_broad_universe_paper_state()
    if isinstance(payload, dict):
        state.update(payload)
    _normalise_state(state)
    return state


def save_pead_broad_universe_paper_state(
    state: dict[str, Any],
    path: Path | str = DEFAULT_STATE_PATH,
) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now_iso()
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(_safe(state), handle, indent=2, sort_keys=True)
        handle.write("\n")


def append_pead_broad_universe_paper_snapshot(
    snapshot: dict[str, Any],
    path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_safe(snapshot), sort_keys=True) + "\n")


def empty_pead_broad_universe_paper_sleeve_snapshot(
    as_of: str,
    reason: str,
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
        "candidate_reject_counts": {},
        "forward_paper_gate": {"passed": False, "status": "blocked", "reasons": [reason]},
        "production_impact": _production_impact(),
        "error": reason,
    }


def build_pead_broad_universe_paper_sleeve_snapshot(
    *,
    as_of: str,
    ohlcv_by_ticker: dict[str, Any] | None = None,
    candidate_universe: dict[str, Any] | list[str] | None = None,
    earnings_index: dict[str, list[tuple[str, dict[str, Any]]]] | None = None,
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
    rows_by_ticker = {
        str(ticker).upper(): _normalise_ohlcv_rows(rows)
        for ticker, rows in (ohlcv_by_ticker or {}).items()
    }
    if not rows_by_ticker:
        return empty_pead_broad_universe_paper_sleeve_snapshot(as_of_date, "missing_ohlcv")

    earnings_rows = (
        earnings_index
        if earnings_index is not None
        else load_earnings_snapshot_index()
    )
    if not earnings_rows:
        return empty_pead_broad_universe_paper_sleeve_snapshot(
            as_of_date, "missing_earnings_snapshots"
        )

    working_state = deepcopy(
        state
        if state is not None
        else load_pead_broad_universe_paper_state(state_path)
    )
    _normalise_state(working_state)

    current, opens = _exact_asof_price_maps(
        rows_by_ticker,
        as_of=as_of_date,
        current_prices=current_prices,
        open_prices=open_prices,
    )
    benchmark_ready = _index_on_date(rows_by_ticker.get("SPY") or [], as_of_date) is not None

    closed_today: list[dict[str, Any]] = []
    filled_today: list[dict[str, Any]] = []
    skipped_today: list[dict[str, Any]] = []
    if benchmark_ready:
        closed_today = _advance_open_positions(
            working_state,
            as_of=as_of_date,
            current_prices=current,
            config=cfg,
        )
        filled_today, skipped_today = _fill_pending_entries(
            working_state,
            as_of=as_of_date,
            open_prices=opens,
            current_prices=current,
            config=cfg,
        )

    active_tickers = {
        str(row.get("ticker") or "").upper()
        for row in working_state.get("open_positions") or []
        if isinstance(row, dict)
    }
    pending_tickers = {
        str(row.get("ticker") or "").upper()
        for row in working_state.get("pending_entries") or []
        if isinstance(row, dict)
    }
    universe = _normalise_candidate_universe(candidate_universe, rows_by_ticker)
    candidates, rejected, audit = build_pead_broad_universe_candidates(
        as_of=as_of_date,
        ohlcv_by_ticker=rows_by_ticker,
        candidate_universe=universe,
        earnings_index=earnings_rows,
        open_position_tickers=active_tickers,
        pending_tickers=pending_tickers,
        config=cfg,
    )
    raw_candidates = list(candidates)
    candidates = candidates[: int(cfg["daily_entry_slots"])]
    for candidate in raw_candidates[len(candidates):]:
        rejected.append({**candidate, "reasons": ["daily_slot_capacity_limit"]})

    open_positions = working_state.get("open_positions") or []
    room = max(0, int(cfg["max_active_positions"]) - len(open_positions))
    new_pending: list[dict[str, Any]] = []
    if room > 0 and cfg.get("paper_enabled", True):
        for candidate in candidates[:room]:
            entry = _pending_entry_from_candidate(candidate, as_of=as_of_date, config=cfg)
            working_state["pending_entries"].append(entry)
            new_pending.append(entry)

    closed = working_state.get("closed_positions") or []
    open_positions = working_state.get("open_positions") or []
    gate = _forward_paper_gate(closed, cfg)

    snapshot = {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "asof_date": as_of_date,
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": bool(cfg.get("paper_enabled", True)),
        "trade_enabled": False,
        "trade_enabled_reason": "default_off_until_gate5_and_live_adapter_pass",
        "experiment_id": "exp-20260604-021",
        "candidate_count": len(candidates),
        "raw_candidate_count": len(raw_candidates),
        "rejected_candidate_count": len(rejected),
        "new_pending_count": len(new_pending),
        "filled_count": len(filled_today),
        "closed_count_today": len(closed_today),
        "pending_count": len(working_state.get("pending_entries") or []),
        "open_position_count": len(open_positions),
        "closed_position_count": len(closed),
        "realized_pnl_to_date": round(
            sum(_money(row.get("pnl")) for row in closed), 2
        ),
        "unrealized_pnl": round(
            sum(_money(row.get("unrealized_pnl")) for row in open_positions), 2
        ),
        "earnings_snapshot_source": {
            "status": "provided" if earnings_index is not None else "local_daily_snapshots",
            "dates_loaded": audit.get("earnings_snapshot_dates_loaded"),
            "covered_ticker_count": len(earnings_rows),
            "source": "data/daily/snapshots/earnings/earnings_snapshot_*.json",
        },
        "candidate_universe": {
            "status": universe.get("status"),
            "ticker_count": len(universe.get("tickers") or []),
        },
        "candidate_reject_counts": audit.get("audit_reject_counts") or {},
        "candidate_audit": audit,
        "candidates": deepcopy(candidates),
        "raw_candidates_sample": deepcopy(raw_candidates[:10]),
        "rejected_candidates": deepcopy(rejected[:50]),
        "new_pending_entries": deepcopy(new_pending),
        "filled_entries": deepcopy(filled_today),
        "closed_positions_today": deepcopy(closed_today),
        "skipped_entries_today": deepcopy(skipped_today),
        "pending_entries": deepcopy(working_state["pending_entries"]),
        "open_positions": deepcopy(open_positions),
        "closed_positions_sample": deepcopy(closed[-20:]),
        "forward_paper_gate": gate,
        "production_impact": _production_impact(),
        "notes": (
            "Default-off broad-universe PEAD paper sleeve (exp-20260604-021 + exp-20260607-003). "
            "Trigger: EPS surprise >= 5%, gap-cancel > 5% (PEAD_MAX_EARNINGS_DAY_GAP_PCT), price >= $5, "
            "avg dollar vol >= $10M. No MA50/RS/pre-event filters. "
            "Universe expanded from ~80-90 to ~500 S&P 500 adjacent tickers via "
            "fetch_broad_earnings_snapshot.py (daily, after run.py) + warehouse OHLCV. "
            "Gate 5 required before any live activation."
        ),
        "next_action": "paper_observe_forward_no_orders",
    }

    if persist:
        save_pead_broad_universe_paper_state(working_state, state_path)
        append_pead_broad_universe_paper_snapshot(snapshot, snapshot_log_path)
    return _safe(snapshot)


def build_pead_broad_universe_candidates(
    *,
    as_of: str,
    ohlcv_by_ticker: dict[str, Any],
    candidate_universe: dict[str, Any] | list[str] | None = None,
    earnings_index: dict[str, list[tuple[str, dict[str, Any]]]] | None = None,
    open_position_tickers: set[str] | None = None,
    pending_tickers: set[str] | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    cfg = _config(config)
    rows_by_ticker = {
        str(ticker).upper(): _normalise_ohlcv_rows(rows)
        for ticker, rows in (ohlcv_by_ticker or {}).items()
    }
    universe = _normalise_candidate_universe(candidate_universe, rows_by_ticker)
    earnings_rows = (
        earnings_index
        if earnings_index is not None
        else load_earnings_snapshot_index()
    )
    trading_dates_list = _trading_dates(rows_by_ticker)
    trading_pos = {date_value: idx for idx, date_value in enumerate(trading_dates_list)}
    as_of_date = _date10(as_of)
    wanted_set = {as_of_date} if as_of_date in trading_pos else set()

    active = {str(t).upper() for t in (open_position_tickers or set())}
    pending = {str(t).upper() for t in (pending_tickers or set())}

    candidates: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    audit: Counter[str] = Counter()
    event_count = 0

    universe_tickers = set(universe.get("tickers") or []).intersection(rows_by_ticker)
    universe_tickers -= EXCLUDED_TICKERS

    for ticker in sorted(universe_tickers):
        rows = rows_by_ticker.get(ticker) or []
        idx_by_date = _row_index(rows)
        events = _pead_broad_positive_surprise_events(
            ticker=ticker,
            earnings_index=earnings_rows,
            trading_dates=trading_dates_list,
            config=cfg,
        )
        event_count += len(events)
        for event in events:
            event_date = str(event["event_confirmed_date"])
            event_trade_pos = trading_pos.get(event_date)
            event_idx = idx_by_date.get(event_date)
            if event_trade_pos is None or event_idx is None:
                audit["missing_event_ohlcv"] += 1
                continue
            if event_idx <= 0:
                audit["missing_event_prior_close"] += 1
                continue

            for offset in range(
                int(cfg["recent_signal_days_min"]),
                int(cfg["recent_signal_days_max"]) + 1,
            ):
                signal_pos = event_trade_pos + offset
                if signal_pos >= len(trading_dates_list):
                    audit["signal_window_out_of_range"] += 1
                    continue
                signal_date = trading_dates_list[signal_pos]
                if signal_date not in wanted_set:
                    continue
                idx = idx_by_date.get(signal_date)
                if idx is None or idx < int(cfg["avg_dollar_volume_days"]):
                    audit["insufficient_ohlcv_history"] += 1
                    continue

                candidate = _candidate_from_event(
                    ticker=ticker,
                    rows=rows,
                    idx=idx,
                    event_idx=event_idx,
                    signal_date=signal_date,
                    offset=offset,
                    event=event,
                    config=cfg,
                    audit=audit,
                )
                if candidate is None:
                    continue
                if ticker in active:
                    rejected.append(
                        {**candidate, "reasons": ["already_open_in_pead_broad_paper"]}
                    )
                    break
                if ticker in pending:
                    rejected.append(
                        {**candidate, "reasons": ["already_pending_in_pead_broad_paper"]}
                    )
                    break
                candidates.append(candidate)
                break

    candidates.sort(key=_candidate_sort_key)
    for rank, candidate in enumerate(candidates, start=1):
        candidate["pead_broad_rank_on_signal_date"] = rank
        candidate["max_paper_trades_per_day"] = int(cfg["daily_entry_slots"])

    return candidates, rejected, {
        "dates_checked": 1 if wanted_set else 0,
        "positive_surprise_event_count": event_count,
        "candidate_count": len(candidates),
        "unique_candidate_tickers": len({row["ticker"] for row in candidates}),
        "earnings_snapshot_dates_loaded": _earnings_date_count(earnings_rows),
        "audit_reject_counts": dict(sorted(audit.items())),
        "rule_version": RULE_VERSION,
    }


def _pead_broad_positive_surprise_events(
    *,
    ticker: str,
    earnings_index: dict[str, list[tuple[str, dict[str, Any]]]],
    trading_dates: list[str],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Simplified event detector: EPS surprise >= min_latest_surprise_pct."""
    index_rows = earnings_index.get(str(ticker).upper(), [])
    if not index_rows:
        return []
    trading_set = set(trading_dates)
    events: list[dict[str, Any]] = []
    for pos in range(1, len(index_rows)):
        snap_date, info = index_rows[pos]
        prev_snap_date, prev_info = index_rows[pos - 1]
        if snap_date not in trading_set:
            continue
        if not _event_is_confirmed(prev_info, info, config):
            continue
        surprise = _surprise_context(info)
        if surprise is None:
            continue
        if surprise["historical_surprise_count"] < int(config["min_surprise_history_count"]):
            continue
        if surprise["positive_historical_surprise_count"] < int(
            config["min_positive_surprise_count"]
        ):
            continue
        if surprise["avg_historical_surprise_pct"] < float(
            config["min_avg_historical_surprise_pct"]
        ):
            continue
        latest_surprise = _surprise_tail(info)
        if latest_surprise is None or latest_surprise < float(config["min_latest_surprise_pct"]):
            continue
        days_to_next = _float_or_none(info.get("days_to_earnings"))
        if days_to_next is None:
            continue
        events.append(
            {
                "ticker": str(ticker).upper(),
                "event_confirmed_date": snap_date,
                "previous_snapshot_source_date": prev_snap_date,
                "earnings_snapshot_source_date": snap_date,
                "latest_surprise_pct": latest_surprise,
                "avg_historical_surprise_pct": surprise["avg_historical_surprise_pct"],
                "historical_surprise_count": surprise["historical_surprise_count"],
                "positive_historical_surprise_count": surprise[
                    "positive_historical_surprise_count"
                ],
                "eps_actual_last": _float_or_none(info.get("eps_actual_last")),
                "days_to_next_earnings_after_event": days_to_next,
            }
        )
    return events


def _candidate_from_event(
    *,
    ticker: str,
    rows: list[dict[str, Any]],
    idx: int,
    event_idx: int,
    signal_date: str,
    offset: int,
    event: dict[str, Any],
    config: dict[str, Any],
    audit: Counter[str],
) -> dict[str, Any] | None:
    """Build candidate dict; return None if any filter fails."""
    close = _positive_float(rows[idx].get("close"))
    volume = _positive_float(rows[idx].get("volume"))
    open_price = _positive_float(rows[idx].get("open"))
    if not close or volume is None or open_price is None:
        audit["missing_close_volume_or_open"] += 1
        return None

    # Price filter
    if close < float(config["min_price"]):
        audit["price_below_minimum"] += 1
        return None

    # Average dollar volume filter
    avg_dv = _avg_dollar_volume(rows, idx, int(config["avg_dollar_volume_days"]))
    if avg_dv is None:
        audit["missing_avg_dollar_volume"] += 1
        return None
    if avg_dv < float(config["min_avg_dollar_volume_20d"]):
        audit["low_avg_dollar_volume"] += 1
        return None

    # Gap-cancel: skip if earnings-day open gap > max_earnings_day_gap_pct
    # event_idx == idx when offset == 0 (signal_date == event_confirmed_date)
    gap_row_idx = event_idx  # the confirmed earnings date
    if gap_row_idx > 0:
        prev_close = _positive_float(rows[gap_row_idx - 1].get("close"))
        event_open = _positive_float(rows[gap_row_idx].get("open"))
        if prev_close and event_open:
            gap_pct = abs(event_open / prev_close - 1.0)
            if gap_pct > float(config["max_earnings_day_gap_pct"]):
                audit["earnings_day_gap_too_large"] += 1
                return None

    score = float(event["latest_surprise_pct"]) / 100.0 + (avg_dv / 1e9)

    return {
        "sleeve": SLEEVE_NAME,
        "ticker": ticker,
        "date": signal_date,
        "strategy": "pead_broad_universe_eps_surprise_only",
        "rule_version": RULE_VERSION,
        "experiment_id": "exp-20260604-021",
        "close": _round(close, 4),
        "volume": _round(volume, 2),
        "avg_dollar_volume_20d": _round(avg_dv, 2),
        "event_confirmed_date": event["event_confirmed_date"],
        "recent_signal_trading_day_offset": offset,
        "latest_surprise_pct": _round(event["latest_surprise_pct"], 6),
        "avg_historical_surprise_pct": _round(
            event["avg_historical_surprise_pct"], 6
        ),
        "historical_surprise_count": event["historical_surprise_count"],
        "positive_historical_surprise_count": event[
            "positive_historical_surprise_count"
        ],
        "eps_actual_last": _round(event.get("eps_actual_last"), 6),
        "days_to_next_earnings_after_event": int(
            event["days_to_next_earnings_after_event"]
        ),
        "earnings_snapshot_source_date": event["earnings_snapshot_source_date"],
        "previous_snapshot_source_date": event["previous_snapshot_source_date"],
        "pead_broad_score": _round(score, 6),
        "base_paper_notional_usd": float(config["paper_notional_usd"]),
        "intended_notional": _round(float(config["paper_notional_usd"]), 2),
        "trade_enabled": False,
        "alters_orders": False,
        "known_at": "after_earnings_snapshot_transition_before_next_open",
        "filter_design": "eps_surprise_only_no_ma50_no_rs_no_pre_event",
    }


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
        key=lambda r: (str(r.get("created_asof") or ""), str(r.get("ticker") or "")),
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
        notional = _positive_float(entry.get("notional")) or float(config["paper_notional_usd"])
        candidate = entry.get("candidate") or {}
        position = {
            "decision_id": entry.get("decision_id"),
            "sleeve": SLEEVE_NAME,
            "ticker": ticker,
            "strategy": "pead_broad_universe_eps_surprise_only",
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


def _pending_entry_from_candidate(
    candidate: dict[str, Any],
    *,
    as_of: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    ticker = str(candidate.get("ticker") or "").upper()
    notional = _positive_float(candidate.get("intended_notional")) or float(
        config["paper_notional_usd"]
    )
    return {
        "decision_id": f"{SLEEVE_NAME}:{RULE_VERSION}:{as_of}:{ticker}",
        "sleeve": SLEEVE_NAME,
        "ticker": ticker,
        "created_asof": as_of,
        "status": "pending_next_open",
        "notional": notional,
        "candidate": deepcopy(candidate),
        "trade_enabled": False,
        "alters_orders": False,
    }


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
        "positive_net_pnl": (
            realized > 0
            if config.get("forward_gate_positive_net_pnl", True)
            else True
        ),
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


def _avg_dollar_volume(rows: list[dict[str, Any]], idx: int, days: int) -> float | None:
    if idx < days:
        return None
    values: list[float] = []
    for row in rows[idx - days: idx]:
        close = _positive_float(row.get("close"))
        volume = _positive_float(row.get("volume"))
        if close is None or volume is None:
            return None
        values.append(close * volume)
    return sum(values) / len(values) if values else None


def _candidate_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row["date"],
        -float(row["pead_broad_score"]),
        -float(row["latest_surprise_pct"]),
        -float(row["avg_dollar_volume_20d"]),
        row["ticker"],
    )


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
        "shared_policy_changed": False,
        "run_adapter_changed": True,
        "backtester_adapter_changed": False,
        "parity_test_added": False,
        "replay_only": False,
        "default_off_paper_only": True,
        "production_signal_path_changed": False,
        "production_orders_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "trade_enabled": False,
        "scope": "default_off_pead_broad_universe_paper_forward_observation",
        "parity_rule": RULE_VERSION,
        "experiment_id": "exp-20260604-021",
    }
