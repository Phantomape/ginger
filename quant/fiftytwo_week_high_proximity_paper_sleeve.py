"""Default-off 52-week-high proximity core-flow paper sleeve.

Shared helper for the positive exp-20260610-007 replay lead, promoted in
exp-20260610-008. On days that already have selected core A/B entry flow, it
admits the strongest liquid sector-known stock that is pushing into a fresh
52-week-high zone: close within 3% of the trailing 252-trading-day high AND a
new >60-day-high breakout, with SPY-relative leadership and close/volume
quality, excluding same-ticker core overlap.

The candidate computation needs at least 252 prior trading days of OHLCV. With
less history the rule fails closed: the ticker simply cannot qualify.

The sleeve is paper-only. It never changes core signal generation, ranking,
sizing, exits, heat, LLM/news behavior, watchlists, or orders.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import broad_market_sector_map
    import macro_relief_leadership_paper_sleeve as leader
    from constants import ROUND_TRIP_COST_PCT
    from data_paths import DATA_ROOT
    from fill_model import SLIPPAGE_BPS_ENTRY, SLIPPAGE_BPS_TARGET, apply_slippage
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant import broad_market_sector_map
    from quant import macro_relief_leadership_paper_sleeve as leader
    from quant.constants import ROUND_TRIP_COST_PCT
    from quant.data_paths import DATA_ROOT
    from quant.fill_model import SLIPPAGE_BPS_ENTRY, SLIPPAGE_BPS_TARGET, apply_slippage


SLEEVE_NAME = "FIFTYTWO_WEEK_HIGH_PROXIMITY_CORE_FLOW_PAPER"
RULE_VERSION = "fiftytwo_week_high_proximity_core_flow_shared_default_off_adapter_v1"
SOURCE_RULE_VERSION = "fiftytwo_week_high_proximity_core_flow_candidate_source_v1"
STATE_SCHEMA_VERSION = 1

DEFAULT_STATE_PATH = (
    DATA_ROOT / "paper_sleeves" / "fiftytwo_week_high_proximity" / "state.json"
)
DEFAULT_SNAPSHOT_LOG_PATH = (
    DATA_ROOT / "paper_sleeves" / "fiftytwo_week_high_proximity" / "snapshots.jsonl"
)

# Must stay identical to the exp-20260610-007 lead chain exclusion set.
EXCLUDED_TICKERS = {
    "ARKX",
    "BIL",
    "CPER",
    "DIA",
    "GLD",
    "IAU",
    "IBIT",
    "IEF",
    "IWM",
    "QQQ",
    "SHY",
    "SLV",
    "SPY",
    "TLT",
    "UFO",
    "UUP",
    "USO",
    "VIXM",
    "VIXY",
    "VXX",
    "XLB",
    "XLE",
    "XLF",
    "XLI",
    "XLK",
    "XLP",
    "XLU",
    "XLV",
    "XLY",
}

DEFAULT_CONFIG = {
    "enabled": False,
    "paper_enabled": True,
    "trade_enabled": False,
    "paper_notional_usd": 4_000.0,
    "daily_entry_slots": 1,
    "max_active_positions": 10,
    "hold_days": 10,
    "same_ticker_cooldown_days": 10,
    "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
    "min_price": 10.0,
    "min_avg_dollar_volume_20d": 75_000_000.0,
    "high_252_lookback": 252,
    "new_high_breakout_lookback": 60,
    "min_proximity_to_52w_high": 0.97,
    "min_spy_history_days": 65,
    "min_ret20_excess_spy": 0.000,
    "min_ret60_excess_spy": -0.020,
    "min_signal_return": 0.005,
    "min_close_location": 0.60,
    "min_volume_ratio_20d": 0.90,
    "max_volume_ratio_20d": 3.50,
    "min_ret5": -0.020,
    "max_ret5": 0.120,
    "max_realized_vol_20d": 0.080,
    "core_flow_confirmation_required": True,
    "same_ticker_core_overlap_excluded": True,
    "kill_switch_drawdown_pct": 0.08,
    "sleeve_drawdown_stop_pct": 0.05,
    "kill_switch_concentration_min_closed_trades": 20,
    "kill_switch_max_single_positive_share": 0.50,
    "forward_gate_min_closed_trades": 30,
    "forward_gate_positive_net_pnl": True,
    "forward_gate_min_win_rate": 0.50,
    "forward_gate_max_single_ticker_positive_share": 0.50,
    "forward_gate_max_positive_hhi": 0.35,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def empty_fiftytwo_week_high_proximity_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "updated_at": None,
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "skipped_days": [],
    }


def empty_fiftytwo_week_high_proximity_snapshot(as_of: str, reason: str) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
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
        "candidate_universe": {"status": reason, "ticker_count": 0},
        "fiftytwo_week_high_context": {"status": reason},
        "kill_switch": {"triggered": False, "status": reason, "reasons": [reason]},
        "forward_paper_gate": {"passed": False, "status": "blocked", "reasons": [reason]},
        "production_impact": _production_impact(),
        "error": reason,
    }


def load_fiftytwo_week_high_proximity_state(
    path: Path | str = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_fiftytwo_week_high_proximity_state()
    with state_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    state = empty_fiftytwo_week_high_proximity_state()
    if isinstance(payload, dict):
        state.update(payload)
    _normalise_state(state)
    return state


def save_fiftytwo_week_high_proximity_state(
    state: dict[str, Any],
    path: Path | str = DEFAULT_STATE_PATH,
) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now_iso()
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(_safe(state), handle, indent=2, sort_keys=True)
        handle.write("\n")


def append_fiftytwo_week_high_proximity_snapshot(
    snapshot: dict[str, Any],
    path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_safe(snapshot), sort_keys=True) + "\n")


def evaluate_fiftytwo_week_high_kill_switch(
    closed_positions: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Sleeve kill switch and drawdown stop on the realized paper ledger.

    Both replay-derived tests and the daily snapshot share this rule. When the
    hard kill or the softer sleeve drawdown stop triggers, the sleeve stops
    creating new pending paper entries; existing positions still advance and
    close normally. The sleeve never emits orders either way.
    """
    cfg = _config(config)
    closed = sorted(
        [row for row in closed_positions or [] if isinstance(row, dict)],
        key=lambda row: (str(row.get("exit_date") or ""), str(row.get("ticker") or "")),
    )
    committed_capital = float(cfg["max_active_positions"]) * float(cfg["paper_notional_usd"])
    kill_limit_usd = float(cfg["kill_switch_drawdown_pct"]) * committed_capital
    stop_limit_usd = float(cfg["sleeve_drawdown_stop_pct"]) * committed_capital

    cumulative = 0.0
    peak = 0.0
    max_drawdown_usd = 0.0
    by_ticker_positive: Counter[str] = Counter()
    for row in closed:
        pnl = leader._float_or_none(row.get("pnl")) or 0.0
        cumulative += pnl
        peak = max(peak, cumulative)
        max_drawdown_usd = max(max_drawdown_usd, peak - cumulative)
        if pnl > 0:
            by_ticker_positive[str(row.get("ticker") or "").upper()] += pnl

    positive_total = sum(by_ticker_positive.values())
    max_single_positive_share = (
        round(max(by_ticker_positive.values()) / positive_total, 6)
        if positive_total > 0
        else None
    )

    reasons: list[str] = []
    if max_drawdown_usd >= kill_limit_usd:
        reasons.append("realized_drawdown_kill_limit")
    elif max_drawdown_usd >= stop_limit_usd:
        reasons.append("realized_drawdown_sleeve_stop")
    if (
        len(closed) >= int(cfg["kill_switch_concentration_min_closed_trades"])
        and max_single_positive_share is not None
        and max_single_positive_share > float(cfg["kill_switch_max_single_positive_share"])
    ):
        reasons.append("positive_pnl_concentration_kill")

    triggered = bool(reasons)
    return {
        "rule_version": RULE_VERSION,
        "triggered": triggered,
        "status": "triggered" if triggered else "armed",
        "reasons": reasons,
        "blocks_new_pending_entries": triggered,
        "alters_orders": False,
        "metrics": {
            "closed_trades": len(closed),
            "cumulative_realized_pnl": leader._round(cumulative, 2),
            "max_realized_drawdown_usd": leader._round(max_drawdown_usd, 2),
            "committed_capital_usd": leader._round(committed_capital, 2),
            "kill_limit_usd": leader._round(kill_limit_usd, 2),
            "sleeve_stop_limit_usd": leader._round(stop_limit_usd, 2),
            "max_single_positive_share": max_single_positive_share,
        },
        "parameters": {
            "kill_switch_drawdown_pct": cfg["kill_switch_drawdown_pct"],
            "sleeve_drawdown_stop_pct": cfg["sleeve_drawdown_stop_pct"],
            "kill_switch_concentration_min_closed_trades": cfg[
                "kill_switch_concentration_min_closed_trades"
            ],
            "kill_switch_max_single_positive_share": cfg[
                "kill_switch_max_single_positive_share"
            ],
        },
    }


def build_fiftytwo_week_high_proximity_snapshot(
    *,
    as_of: str,
    ohlcv_by_ticker: dict[str, Any],
    candidate_universe: dict[str, Any] | list[str] | None = None,
    core_entries: list[dict[str, Any]] | None = None,
    sector_entries: dict[str, dict[str, Any]] | None = None,
    state: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    persist: bool = True,
    state_path: Path | str = DEFAULT_STATE_PATH,
    snapshot_log_path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> dict[str, Any]:
    cfg = _config(config)
    as_of_date = _date10(as_of)
    working_state = deepcopy(
        state if state is not None else load_fiftytwo_week_high_proximity_state(state_path)
    )
    _normalise_state(working_state)
    rows_by_ticker = leader._normalise_ohlcv_by_ticker(ohlcv_by_ticker)
    if not rows_by_ticker:
        return empty_fiftytwo_week_high_proximity_snapshot(as_of_date, "missing_ohlcv")
    if "SPY" not in rows_by_ticker:
        return empty_fiftytwo_week_high_proximity_snapshot(as_of_date, "missing_spy_ohlcv")

    sector_map = _resolve_sector_entries(
        sector_entries=sector_entries,
        candidate_universe=candidate_universe,
        rows_by_ticker=rows_by_ticker,
    )
    if not sector_map:
        return empty_fiftytwo_week_high_proximity_snapshot(as_of_date, "missing_sector_entries")

    filled_today = leader._fill_pending_entries(working_state, rows_by_ticker, as_of_date, cfg)
    closed_today = leader._advance_open_positions(working_state, rows_by_ticker, as_of_date, cfg)
    kill_switch = evaluate_fiftytwo_week_high_kill_switch(
        working_state.get("closed_positions") or [],
        cfg,
    )

    candidates, contexts, scan = build_fiftytwo_week_high_proximity_candidate_rows(
        ohlcv_by_ticker=rows_by_ticker,
        dates=[as_of_date],
        sector_entries=sector_map,
        core_entries_by_date={as_of_date: list(core_entries or [])},
        config=cfg,
    )
    selected, rejected = select_fiftytwo_week_high_proximity_paper_trades(
        rows_by_ticker=rows_by_ticker,
        candidates=candidates,
        existing_state=working_state,
        config=cfg,
        allow_missing_exit=True,
    )
    new_pending_entries: list[dict[str, Any]] = []
    if cfg.get("paper_enabled", True) and not kill_switch["triggered"]:
        for trade in selected:
            pending = _pending_entry_from_trade(trade, cfg)
            if not leader._has_pending_open_or_closed_decision(
                working_state,
                pending["decision_id"],
            ):
                working_state["pending_entries"].append(pending)
                new_pending_entries.append(pending)
    if kill_switch["triggered"]:
        _append_skip_once(
            working_state,
            _skip_payload(as_of_date, "kill_switch_triggered"),
        )
    elif not selected and not candidates:
        _append_skip_once(
            working_state,
            _skip_payload(as_of_date, "no_core_flow_confirmed_candidate"),
        )

    snapshot = _snapshot_payload(
        working_state,
        as_of=as_of_date,
        candidates=candidates,
        selected=selected,
        rejected=rejected,
        contexts=contexts,
        scan=scan,
        kill_switch=kill_switch,
        new_pending_entries=new_pending_entries,
        filled_today=filled_today,
        closed_today=closed_today,
        candidate_universe=candidate_universe,
        rows_by_ticker=rows_by_ticker,
        config=cfg,
    )
    if persist:
        save_fiftytwo_week_high_proximity_state(working_state, state_path)
        append_fiftytwo_week_high_proximity_snapshot(snapshot, snapshot_log_path)
    return snapshot


def prep_and_build_fiftytwo_week_high_proximity_snapshot(
    *,
    as_of: str,
    broad_market_ohlcv: dict,
    broad_market_candidate_universe: dict,
    spy_ohlcv=None,
    core_entries=None,
):
    """Daily production adapter (mirrors the sibling core-flow sleeves).

    Maps the run.py broad-market context into the shared default-off builder.
    Observe-only: ``build_fiftytwo_week_high_proximity_snapshot`` keeps
    ``trade_enabled=False`` and never emits live/default orders, ranking, or
    sizing. Sectors are resolved from the candidate-universe records inside the
    builder; only SPY is a hard OHLCV requirement (QQQ and other ETFs are
    excluded from the stock candidate pool, not required as inputs).
    """
    if not broad_market_candidate_universe.get("tickers"):
        return empty_fiftytwo_week_high_proximity_snapshot(
            as_of, "broad_market_candidate_universe_unavailable")
    ohlcv = dict(broad_market_ohlcv)
    if "SPY" not in ohlcv and spy_ohlcv is not None:
        ohlcv["SPY"] = spy_ohlcv
    return build_fiftytwo_week_high_proximity_snapshot(
        as_of=as_of, ohlcv_by_ticker=ohlcv, core_entries=core_entries,
        candidate_universe=broad_market_candidate_universe,
    )


def build_fiftytwo_week_high_proximity_historical_trades(
    *,
    ohlcv_by_ticker: dict[str, Any],
    core_entries_by_date: dict[str, list[dict[str, Any]]] | None,
    windows: dict[str, dict[str, str]],
    candidate_universe: dict[str, Any] | list[str] | None = None,
    sector_entries: dict[str, dict[str, Any]] | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cfg = _config(config)
    rows_by_ticker = leader._normalise_ohlcv_by_ticker(ohlcv_by_ticker)
    sector_map = _resolve_sector_entries(
        sector_entries=sector_entries,
        candidate_universe=candidate_universe,
        rows_by_ticker=rows_by_ticker,
    )
    all_trades: list[dict[str, Any]] = []
    audit = {
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "selected_by_window": {},
        "raw_candidate_count_by_window": {},
        "rejected_count_by_window": {},
        "scan_by_window": {},
        "day_contexts_by_window": {},
    }
    for label, window in windows.items():
        dates = [
            day
            for day in _trading_dates(rows_by_ticker)
            if str(window["start"]) <= day <= str(window["end"])
        ]
        candidates, contexts, scan = build_fiftytwo_week_high_proximity_candidate_rows(
            ohlcv_by_ticker=rows_by_ticker,
            dates=dates,
            sector_entries=sector_map,
            core_entries_by_date=core_entries_by_date or {},
            config=cfg,
        )
        selected, rejected = select_fiftytwo_week_high_proximity_paper_trades(
            rows_by_ticker=rows_by_ticker,
            candidates=candidates,
            config=cfg,
        )
        window_trades = [{**row, "window": label} for row in selected]
        all_trades.extend(window_trades)
        audit["selected_by_window"][label] = len(window_trades)
        audit["raw_candidate_count_by_window"][label] = len(candidates)
        audit["rejected_count_by_window"][label] = len(rejected)
        audit["scan_by_window"][label] = scan
        audit["day_contexts_by_window"][label] = contexts[:100]
    return all_trades, _safe(audit)


def build_fiftytwo_week_high_proximity_candidate_rows(
    *,
    ohlcv_by_ticker: dict[str, Any],
    dates: list[str],
    sector_entries: dict[str, dict[str, Any]],
    core_entries_by_date: dict[str, list[dict[str, Any]]] | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    cfg = _config(config)
    rows_by_ticker = leader._normalise_ohlcv_by_ticker(ohlcv_by_ticker)
    indices = {ticker: leader._row_index(rows) for ticker, rows in rows_by_ticker.items()}
    date_set = {_date10(day) for day in dates}
    core_entries_by_date = core_entries_by_date or {}
    candidates: list[dict[str, Any]] = []
    contexts: list[dict[str, Any]] = []
    scan = {
        "scanned_trading_days": len(date_set),
        "core_flow_days": 0,
        "days_with_raw_candidates": 0,
        "raw_candidates": 0,
        "raw_candidates_excluded_same_ticker_core_overlap": 0,
        "unique_candidate_tickers": 0,
        "rule_version": SOURCE_RULE_VERSION,
        "core_flow_confirmation_required": True,
        "same_ticker_core_overlap_excluded": True,
    }
    candidate_tickers: set[str] = set()

    for signal_date in sorted(date_set):
        ab_entries = core_entries_by_date.get(signal_date, [])
        # core-flow displacement anchor: require same-day core A/B entry flow
        if not ab_entries:
            continue
        scan["core_flow_days"] += 1
        day_rows: list[dict[str, Any]] = []
        for ticker in sorted(sector_entries):
            row = _candidate_for_ticker(
                rows_by_ticker=rows_by_ticker,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
                config=cfg,
            )
            if row is None:
                continue
            row["same_day_ab_entry_count"] = len(ab_entries)
            row["same_day_ab_overlap"] = True
            row["same_ticker_ab_overlap"] = any(
                str(trade.get("ticker") or "").upper() == ticker for trade in ab_entries
            )
            if row["same_ticker_ab_overlap"]:
                scan["raw_candidates_excluded_same_ticker_core_overlap"] += 1
            row["core_flow_confirmation"] = {
                "required": True,
                "same_day_ab_entry_count": row["same_day_ab_entry_count"],
                "same_day_ab_overlap": True,
                "same_ticker_core_overlap": row["same_ticker_ab_overlap"],
                "same_ticker_core_overlap_excluded": True,
                "known_at": "after_signal_day_close_before_next_open_paper_entry",
                "rule_version": SOURCE_RULE_VERSION,
            }
            day_rows.append(row)
            candidate_tickers.add(ticker)
        if not day_rows:
            continue
        day_rows.sort(key=_candidate_sort_key)
        candidates.extend(day_rows)
        scan["days_with_raw_candidates"] += 1
        scan["raw_candidates"] += len(day_rows)
        top = day_rows[0]
        contexts.append(
            {
                "date": signal_date,
                "same_day_ab_entry_count": len(ab_entries),
                "raw_candidate_count": len(day_rows),
                "top_candidate": top["ticker"],
                "top_candidate_score": top["candidate_score"],
                "top_candidate_proximity_to_52w_high": top[
                    "candidate_proximity_to_52w_high"
                ],
                "top_candidate_ret20_excess_spy": top["candidate_ret20_excess_spy"],
                "rule_version": SOURCE_RULE_VERSION,
            }
        )

    candidates.sort(key=lambda row: (row["date"], *_candidate_sort_key(row)))
    scan.update({"unique_candidate_tickers": len(candidate_tickers), **_parameter_summary(cfg)})
    return candidates, contexts, scan


def select_fiftytwo_week_high_proximity_paper_trades(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
    existing_state: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    allow_missing_exit: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cfg = _config(config)
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    used_date_counts: Counter[str] = Counter()
    all_dates = _trading_dates(rows_by_ticker)
    date_pos = {day: idx for idx, day in enumerate(all_dates)}
    next_allowed_pos_by_ticker: dict[str, int] = {}
    if existing_state:
        for row in (existing_state.get("pending_entries") or []) + (
            existing_state.get("open_positions") or []
        ) + (existing_state.get("closed_positions") or []):
            if not isinstance(row, dict):
                continue
            ticker = str(row.get("ticker") or "").upper()
            date_value = str(row.get("signal_date") or row.get("date") or "")[:10]
            pos = date_pos.get(date_value)
            if ticker and pos is not None:
                next_allowed_pos_by_ticker[ticker] = max(
                    next_allowed_pos_by_ticker.get(ticker, -1),
                    pos + int(cfg["same_ticker_cooldown_days"]),
                )
    for row in candidates:
        signal_date = str(row.get("date") or "")[:10]
        ticker = str(row.get("ticker") or "").upper()
        pos = date_pos.get(signal_date)
        if pos is None:
            rejected.append({**row, "filter_reason": "missing_signal_date_position"})
            continue
        if row.get("same_ticker_ab_overlap"):
            rejected.append({**row, "filter_reason": "same_ticker_core_overlap"})
            continue
        if used_date_counts[signal_date] >= int(cfg["daily_entry_slots"]):
            rejected.append({**row, "filter_reason": "daily_top1_limit"})
            continue
        next_allowed = next_allowed_pos_by_ticker.get(ticker, -1)
        if pos < next_allowed:
            rejected.append({**row, "filter_reason": "same_ticker_cooldown"})
            continue
        trade = replay_trade_from_candidate(
            rows_by_ticker=rows_by_ticker,
            candidate=row,
            config=cfg,
        )
        if trade is None:
            if allow_missing_exit:
                trade = _candidate_as_selected_signal(row, cfg)
            else:
                rejected.append({**row, "filter_reason": "missing_next_open_or_exit"})
                continue
        selected.append(trade)
        used_date_counts[signal_date] += 1
        next_allowed_pos_by_ticker[ticker] = pos + int(cfg["same_ticker_cooldown_days"])
    return selected, rejected


def replay_trade_from_candidate(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    candidate: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    cfg = _config(config)
    ticker = str(candidate.get("ticker") or "").upper()
    rows = rows_by_ticker.get(ticker) or []
    idx = leader._row_index(rows).get(str(candidate.get("date") or "")[:10])
    if idx is None:
        return None
    entry_idx = idx + 1
    exit_idx = idx + int(cfg["hold_days"])
    if entry_idx >= len(rows) or exit_idx >= len(rows):
        return None
    entry_raw = leader._positive_float(rows[entry_idx].get("open"))
    exit_raw = leader._positive_float(rows[exit_idx].get("close"))
    if entry_raw is None or exit_raw is None:
        return None
    entry_price = apply_slippage(entry_raw, SLIPPAGE_BPS_ENTRY, "buy")
    exit_price = apply_slippage(exit_raw, SLIPPAGE_BPS_TARGET, "sell")
    notional = float(cfg["paper_notional_usd"])
    pnl_pct_net = (exit_price / entry_price) - 1.0 - float(cfg["round_trip_cost_pct"])
    signal_date = str(candidate["date"])[:10]
    return {
        **deepcopy(candidate),
        "decision_id": f"{SLEEVE_NAME}:{SOURCE_RULE_VERSION}:{signal_date}:{ticker}",
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "signal_date": signal_date,
        "entry_date": rows[entry_idx]["date"],
        "entry_raw_open": leader._round(entry_raw, 4),
        "entry_price": leader._round(entry_price, 4),
        "exit_date": rows[exit_idx]["date"],
        "exit_raw_close": leader._round(exit_raw, 4),
        "exit_price": leader._round(exit_price, 4),
        "hold_days": int(cfg["hold_days"]),
        "paper_notional_usd": leader._round(notional, 2),
        "notional_usd": leader._round(notional, 2),
        "pnl_pct_net": leader._round(pnl_pct_net, 6),
        "net_return_pct": leader._round(pnl_pct_net, 6),
        "pnl": leader._round(notional * pnl_pct_net, 2),
        "paper_status": "closed",
        "trade_enabled": False,
        "alters_orders": False,
    }


def _candidate_as_selected_signal(
    candidate: dict[str, Any],
    cfg: dict[str, Any],
) -> dict[str, Any]:
    """Daily-mode selection result when future entry/exit bars do not exist yet."""
    signal_date = str(candidate["date"])[:10]
    ticker = str(candidate.get("ticker") or "").upper()
    return {
        **deepcopy(candidate),
        "decision_id": f"{SLEEVE_NAME}:{SOURCE_RULE_VERSION}:{signal_date}:{ticker}",
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "signal_date": signal_date,
        "hold_days": int(cfg["hold_days"]),
        "paper_notional_usd": float(cfg["paper_notional_usd"]),
        "notional_usd": float(cfg["paper_notional_usd"]),
        "paper_status": "selected_signal",
        "trade_enabled": False,
        "alters_orders": False,
    }


def _candidate_for_ticker(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    config: dict[str, Any],
) -> dict[str, Any] | None:
    if ticker in EXCLUDED_TICKERS:
        return None
    rows = rows_by_ticker.get(ticker) or []
    spy_rows = rows_by_ticker.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None:
        return None
    high_lookback = int(config["high_252_lookback"])
    if idx < high_lookback or spy_idx < int(config["min_spy_history_days"]):
        return None

    close = leader._positive_float(rows[idx].get("close"))
    if close is None or close < float(config["min_price"]):
        return None
    adv20 = leader._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < float(config["min_avg_dollar_volume_20d"]):
        return None

    high252 = _trailing_high(rows, idx, high_lookback)
    prior_high = _prior_high(rows, idx, int(config["new_high_breakout_lookback"]))
    if high252 is None or prior_high is None or high252 <= 0:
        return None
    proximity = close / high252
    if proximity < float(config["min_proximity_to_52w_high"]):
        return None
    # fresh breakout: close clears the prior 60-day high
    if close <= prior_high:
        return None

    signal_return = leader._daily_return(rows, idx)
    ret5 = leader._ret(rows, idx, 5)
    ret20 = leader._ret(rows, idx, 20)
    ret60 = leader._ret(rows, idx, 60)
    spy_ret20 = leader._ret(spy_rows, spy_idx, 20)
    spy_ret60 = leader._ret(spy_rows, spy_idx, 60)
    close_location = leader._close_location(rows[idx])
    volume_ratio = leader._volume_ratio(rows, idx)
    realized_vol20 = leader._realized_vol(rows, idx, 20)
    required = [
        signal_return,
        ret5,
        ret20,
        ret60,
        spy_ret20,
        spy_ret60,
        close_location,
        volume_ratio,
        realized_vol20,
    ]
    if any(value is None for value in required):
        return None

    ret20_excess_spy = float(ret20) - float(spy_ret20)
    ret60_excess_spy = float(ret60) - float(spy_ret60)
    if float(signal_return) < float(config["min_signal_return"]):
        return None
    if float(ret5) < float(config["min_ret5"]) or float(ret5) > float(config["max_ret5"]):
        return None
    if ret20_excess_spy < float(config["min_ret20_excess_spy"]):
        return None
    if ret60_excess_spy < float(config["min_ret60_excess_spy"]):
        return None
    if float(close_location) < float(config["min_close_location"]):
        return None
    if (
        float(volume_ratio) < float(config["min_volume_ratio_20d"])
        or float(volume_ratio) > float(config["max_volume_ratio_20d"])
    ):
        return None
    if float(realized_vol20) > float(config["max_realized_vol_20d"]):
        return None

    # higher score = closer to/through the 52-week high, stronger leadership,
    # cleaner close, lower realized vol and less short-term overextension.
    proximity_edge = proximity - float(config["min_proximity_to_52w_high"])
    score = (
        2.20 * proximity_edge
        + 1.30 * ret20_excess_spy
        + 0.55 * ret60_excess_spy
        + 0.45 * float(signal_return)
        + 0.35 * float(close_location)
        - 0.90 * float(realized_vol20)
        - 0.25 * max(float(ret5), 0.0)
    )
    sector_meta = sector_entries.get(ticker, {})
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": SLEEVE_NAME,
        "candidate_score": round(score, 6),
        "candidate_close": round(float(close), 6),
        "candidate_high_252d": round(float(high252), 6),
        "candidate_proximity_to_52w_high": round(proximity, 6),
        "candidate_prior_60d_high": round(float(prior_high), 6),
        "candidate_new_60d_high_breakout": True,
        "candidate_signal_day_return": round(float(signal_return), 6),
        "candidate_ret5": round(float(ret5), 6),
        "candidate_ret20": round(float(ret20), 6),
        "candidate_ret60": round(float(ret60), 6),
        "candidate_ret20_excess_spy": round(ret20_excess_spy, 6),
        "candidate_ret60_excess_spy": round(ret60_excess_spy, 6),
        "candidate_close_location": round(float(close_location), 6),
        "candidate_avg_dollar_volume_20d": round(float(adv20), 2),
        "candidate_volume_ratio_20d": round(float(volume_ratio), 6),
        "candidate_realized_vol_20d": round(float(realized_vol20), 6),
        "sector": sector_meta.get("sector"),
        "industry": sector_meta.get("industry"),
        "sector_coverage_status": sector_meta.get("sector_coverage_status"),
        "rule_version": SOURCE_RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "uses_free_ohlcv_only": True,
        "uses_llm": False,
        "trade_enabled": False,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
    }


def _trailing_high(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < lookback - 1:
        return None
    highs = [
        leader._float_or_none(rows[i].get("high"))
        for i in range(idx - lookback + 1, idx + 1)
    ]
    highs = [value for value in highs if value is not None]
    if len(highs) < lookback:
        return None
    return max(highs)


def _prior_high(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < lookback:
        return None
    highs = [
        leader._float_or_none(rows[i].get("high"))
        for i in range(idx - lookback, idx)
    ]
    highs = [value for value in highs if value is not None]
    if len(highs) < lookback:
        return None
    return max(highs)


def _pending_entry_from_trade(trade: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(trade)
    for key in (
        "entry_date",
        "entry_raw_open",
        "entry_price",
        "exit_date",
        "exit_raw_close",
        "exit_price",
        "pnl",
        "pnl_pct_net",
        "net_return_pct",
    ):
        out.pop(key, None)
    out.update(
        {
            "sleeve": SLEEVE_NAME,
            "rule_version": RULE_VERSION,
            "source_rule_version": SOURCE_RULE_VERSION,
            "paper_notional_usd": float(config["paper_notional_usd"]),
            "notional_usd": float(config["paper_notional_usd"]),
            "entry_timing": "next_session_open",
            "hold_days": int(config["hold_days"]),
            "paper_status": "pending_entry",
            "trade_enabled": False,
            "alters_orders": False,
        }
    )
    return out


def _snapshot_payload(
    state: dict[str, Any],
    *,
    as_of: str,
    candidates: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
    contexts: list[dict[str, Any]],
    scan: dict[str, Any],
    kill_switch: dict[str, Any],
    new_pending_entries: list[dict[str, Any]],
    filled_today: list[dict[str, Any]],
    closed_today: list[dict[str, Any]],
    candidate_universe: dict[str, Any] | list[str] | None,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    config: dict[str, Any],
) -> dict[str, Any]:
    closed = [row for row in state.get("closed_positions") or [] if isinstance(row, dict)]
    pending = [row for row in state.get("pending_entries") or [] if isinstance(row, dict)]
    open_positions = [row for row in state.get("open_positions") or [] if isinstance(row, dict)]
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "asof_date": as_of,
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": bool(config.get("paper_enabled", True)),
        "trade_enabled": False,
        "trade_enabled_reason": "default_off_until_forward_gate_and_trade_adapter_pass",
        "candidate_count": len(selected),
        "raw_candidate_count": len(candidates),
        "rejected_candidate_count": len(rejected),
        "candidate": selected[0] if selected else None,
        "candidates": selected,
        "rejected_candidates": rejected[:50],
        "fiftytwo_week_high_context": {
            **scan,
            "read_only": True,
            "trade_enabled": False,
            "context_samples": contexts[:10],
        },
        "context_scan": scan,
        "kill_switch": kill_switch,
        "candidate_universe": _candidate_universe_summary(candidate_universe, rows_by_ticker),
        "new_pending_entries": new_pending_entries,
        "new_pending_count": len(new_pending_entries),
        "pending_entries": pending,
        "pending_count": len(pending),
        "filled_today": filled_today,
        "filled_count": len(filled_today),
        "opened_positions_this_run": filled_today,
        "open_positions": open_positions,
        "open_position_count": len(open_positions),
        "closed_today": closed_today,
        "closed_positions_today": closed_today,
        "closed_positions_this_run": closed_today,
        "closed_count_today": len(closed_today),
        "closed_positions": closed,
        "closed_position_count": len(closed),
        "realized_pnl_to_date": leader._round(
            sum(leader._float_or_none(row.get("pnl")) or 0.0 for row in closed),
            2,
        ),
        "unrealized_pnl": leader._unrealized_pnl(open_positions, rows_by_ticker, as_of),
        "forward_paper_gate": leader._forward_paper_gate(closed, config),
        "parameters": _parameter_summary(config),
        "production_impact": _production_impact(),
        "next_action": "paper_observe_forward_outcomes_only_no_orders",
    }


def _resolve_sector_entries(
    *,
    sector_entries: dict[str, dict[str, Any]] | None,
    candidate_universe: dict[str, Any] | list[str] | None,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    if sector_entries:
        raw_entries = sector_entries
    elif isinstance(candidate_universe, dict) and isinstance(candidate_universe.get("records"), dict):
        raw_entries = candidate_universe["records"]
    elif isinstance(candidate_universe, dict) and isinstance(candidate_universe.get("entries"), dict):
        raw_entries = candidate_universe["entries"]
    else:
        cache = broad_market_sector_map.load_cache()
        raw_entries = cache.get("entries", {}) if isinstance(cache, dict) else {}

    allowed = (
        {str(ticker).upper() for ticker in candidate_universe}
        if isinstance(candidate_universe, list)
        else set(rows_by_ticker)
    )
    if isinstance(candidate_universe, dict) and candidate_universe.get("tickers"):
        allowed = {str(ticker).upper() for ticker in candidate_universe.get("tickers") or []}

    out: dict[str, dict[str, Any]] = {}
    for ticker, meta in raw_entries.items():
        ticker_u = str(ticker).upper()
        if ticker_u in EXCLUDED_TICKERS or "." in ticker_u or "-" in ticker_u:
            continue
        if ticker_u not in rows_by_ticker or ticker_u not in allowed:
            continue
        if not isinstance(meta, dict):
            continue
        sector = meta.get("sector") or meta.get("gics_sector")
        status = meta.get("status") or meta.get("sector_coverage_status") or "ok"
        if not sector or status != "ok":
            continue
        out[ticker_u] = {
            "sector": sector,
            "industry": meta.get("industry"),
            "sector_coverage_status": status,
        }
    return out


def _normalise_state(state: dict[str, Any]) -> None:
    state.setdefault("schema_version", STATE_SCHEMA_VERSION)
    state.setdefault("sleeve", SLEEVE_NAME)
    state.setdefault("pending_entries", [])
    state.setdefault("open_positions", [])
    state.setdefault("closed_positions", [])
    state.setdefault("skipped_days", [])


def _append_skip_once(state: dict[str, Any], row: dict[str, Any]) -> None:
    existing = {
        str(item.get("decision_id") or "")
        for item in state.get("skipped_days") or []
        if isinstance(item, dict)
    }
    if row["decision_id"] not in existing:
        state["skipped_days"].append(row)


def _skip_payload(as_of: str, reason: str) -> dict[str, Any]:
    return {
        "decision_id": f"{SLEEVE_NAME}:{RULE_VERSION}:{as_of}:SKIP:{reason}",
        "date": as_of,
        "reason": reason,
        "trade_enabled": False,
        "alters_orders": False,
    }


def _candidate_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        -float(row.get("candidate_score") or 0.0),
        -float(row.get("candidate_proximity_to_52w_high") or 0.0),
        -float(row.get("candidate_ret20_excess_spy") or 0.0),
        -float(row.get("candidate_close_location") or 0.0),
        -float(row.get("candidate_avg_dollar_volume_20d") or 0.0),
        str(row.get("sector") or ""),
        str(row.get("ticker") or ""),
    )


def _trading_dates(rows_by_ticker: dict[str, list[dict[str, Any]]]) -> list[str]:
    return sorted({row["date"] for rows in rows_by_ticker.values() for row in rows})


def _candidate_universe_summary(
    candidate_universe: dict[str, Any] | list[str] | None,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    if isinstance(candidate_universe, dict):
        count = len(candidate_universe.get("tickers") or candidate_universe.get("records") or rows_by_ticker)
        status = candidate_universe.get("status") or "provided"
    elif isinstance(candidate_universe, list):
        count = len(candidate_universe)
        status = "provided_ticker_list"
    else:
        count = len(rows_by_ticker)
        status = "ohlcv_dict_or_sector_cache"
    return {
        "status": status,
        "ticker_count": count,
        "loaded_ohlcv_ticker_count": len(rows_by_ticker),
    }


def _parameter_summary(config: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "paper_notional_usd",
        "daily_entry_slots",
        "max_active_positions",
        "hold_days",
        "same_ticker_cooldown_days",
        "min_price",
        "min_avg_dollar_volume_20d",
        "high_252_lookback",
        "new_high_breakout_lookback",
        "min_proximity_to_52w_high",
        "min_ret20_excess_spy",
        "min_ret60_excess_spy",
        "min_signal_return",
        "min_close_location",
        "min_volume_ratio_20d",
        "max_volume_ratio_20d",
        "min_ret5",
        "max_ret5",
        "max_realized_vol_20d",
        "core_flow_confirmation_required",
        "same_ticker_core_overlap_excluded",
        "kill_switch_drawdown_pct",
        "sleeve_drawdown_stop_pct",
    ]
    return {key: config[key] for key in keys}


def _config(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    if overrides:
        cfg.update({key: value for key, value in overrides.items() if value is not None})
    cfg["enabled"] = False
    cfg["trade_enabled"] = False
    cfg["core_flow_confirmation_required"] = True
    cfg["same_ticker_core_overlap_excluded"] = True
    return cfg


def _date10(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return str(value)[:10]


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _production_impact() -> dict[str, Any]:
    return {
        "shared_policy_changed": True,
        "shared_policy_note": "paper attribution module only; core trading policy unchanged",
        "backtester_adapter_changed": True,
        "run_adapter_changed": False,
        "replay_only": False,
        "default_off_paper_only": True,
        "daily_snapshot_exposed": True,
        "trade_enabled": False,
        "alters_orders": False,
        "production_signal_path_changed": False,
        "production_orders_changed": False,
        "production_watchlist_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "uses_llm": False,
        "uses_free_ohlcv_only": True,
        "adapter_status": "shared_default_off_paper_helper",
        "scope": "default_off_fiftytwo_week_high_proximity_core_flow_paper_attribution",
    }
