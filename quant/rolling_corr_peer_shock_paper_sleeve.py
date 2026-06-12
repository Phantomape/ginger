"""Default-off rolling-correlation peer-shock paper sleeve.

Shared helper for the exp-20260606-024 core-flow peer-shock lead. The helper is
intentionally default-off: it can emit paper candidates/snapshots and historical
paper trades, but it never alters live orders, core ranking, sizing, exits,
watchlists, LLM, or news behavior.
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
    from constants import ROUND_TRIP_COST_PCT
    from data_paths import DATA_ROOT
    from fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant import broad_market_sector_map
    from quant.constants import ROUND_TRIP_COST_PCT
    from quant.data_paths import DATA_ROOT
    from quant.fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage


SLEEVE_NAME = "ROLLING_CORR_PEER_SHOCK_CORE_FLOW_PAPER"
RULE_VERSION = "rolling_corr_peer_shock_core_flow_shared_adapter_v1"
SOURCE_RULE_VERSION = "rolling_corr_peer_shock_core_flow_positive_candidate_source_v1"
STATE_SCHEMA_VERSION = 1

DEFAULT_STATE_PATH = DATA_ROOT / "paper_sleeves" / "rolling_corr_peer_shock" / "state.json"
DEFAULT_SNAPSHOT_LOG_PATH = (
    DATA_ROOT / "paper_sleeves" / "rolling_corr_peer_shock" / "snapshots.jsonl"
)

EXCLUDED_TICKERS = {
    "ARKX",
    "BIL",
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
    "UUP",
    "USO",
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
    "hold_days": 10,
    "same_ticker_cooldown_days": 10,
    "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
    "min_price": 10.0,
    "min_avg_dollar_volume_20d": 50_000_000.0,
    "correlation_lookback_days": 60,
    "min_correlation": 0.58,
    "max_shock_peers_per_day": 10,
    "max_laggard_candidates_per_day": 350,
    "max_raw_rows_per_day": 50,
    "min_peer_signal_return": 0.055,
    "min_peer_relative_vs_spy": 0.040,
    "min_peer_volume_ratio_20d": 1.05,
    "min_peer_ret20_excess_spy": -0.02,
    "min_candidate_signal_return": 0.0,
    "max_candidate_signal_return": 0.020,
    "min_candidate_close_location": 0.35,
    "min_candidate_ret5": -0.055,
    "max_candidate_ret5": 0.055,
    "min_candidate_ret20_excess_spy": -0.030,
    "min_candidate_ret60_excess_spy": -0.080,
    "max_candidate_realized_vol_20d": 0.090,
    "forward_gate_min_closed_trades": 30,
    "forward_gate_positive_net_pnl": True,
    "forward_gate_min_win_rate": 0.50,
    "forward_gate_max_single_ticker_positive_share": 0.50,
    "forward_gate_max_positive_hhi": 0.35,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def empty_rolling_corr_peer_shock_paper_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "updated_at": None,
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "skipped_entries": [],
    }


def load_rolling_corr_peer_shock_paper_state(
    path: Path | str = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_rolling_corr_peer_shock_paper_state()
    with state_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    state = empty_rolling_corr_peer_shock_paper_state()
    if isinstance(payload, dict):
        state.update(payload)
    _normalise_state(state)
    return state


def save_rolling_corr_peer_shock_paper_state(
    state: dict[str, Any],
    path: Path | str = DEFAULT_STATE_PATH,
) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now_iso()
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(_safe(state), handle, indent=2, sort_keys=True)
        handle.write("\n")


def append_rolling_corr_peer_shock_paper_snapshot(
    snapshot: dict[str, Any],
    path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_safe(snapshot), sort_keys=True) + "\n")


def empty_rolling_corr_peer_shock_paper_sleeve_snapshot(
    as_of: str,
    reason: str,
) -> dict[str, Any]:
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
        "rejected_candidate_count": 0,
        "new_pending_count": 0,
        "pending_count": 0,
        "open_position_count": 0,
        "closed_position_count": 0,
        "closed_count_today": 0,
        "realized_pnl_to_date": 0.0,
        "unrealized_pnl": 0.0,
        "peer_shock_context": {
            "status": reason,
            "rule_version": SOURCE_RULE_VERSION,
            "read_only": True,
            "trade_enabled": False,
            "candidate_count": 0,
        },
        "forward_paper_gate": {"passed": False, "status": "blocked", "reasons": [reason]},
        "production_impact": _production_impact(),
        "error": reason,
    }


def build_rolling_corr_peer_shock_paper_sleeve_snapshot(
    *,
    as_of: str,
    ohlcv_by_ticker: dict[str, Any] | None = None,
    core_entries: list[dict[str, Any]] | None = None,
    candidate_universe: dict[str, Any] | list[str] | None = None,
    sector_entries: dict[str, dict[str, Any]] | None = None,
    state: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    persist: bool = True,
    state_path: Path | str = DEFAULT_STATE_PATH,
    snapshot_log_path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> dict[str, Any]:
    cfg = _config(config)
    as_of_date = _date10(as_of)
    rows_by_ticker = _normalise_ohlcv_by_ticker(ohlcv_by_ticker or {})
    if not rows_by_ticker:
        return empty_rolling_corr_peer_shock_paper_sleeve_snapshot(as_of_date, "missing_ohlcv")
    if "SPY" not in rows_by_ticker:
        return empty_rolling_corr_peer_shock_paper_sleeve_snapshot(as_of_date, "missing_spy_ohlcv")

    sector_map = _resolve_sector_entries(
        sector_entries=sector_entries,
        candidate_universe=candidate_universe,
        rows_by_ticker=rows_by_ticker,
    )
    if not sector_map:
        return empty_rolling_corr_peer_shock_paper_sleeve_snapshot(
            as_of_date,
            "missing_sector_entries",
        )

    working_state = deepcopy(
        state if state is not None else load_rolling_corr_peer_shock_paper_state(state_path)
    )
    _normalise_state(working_state)
    lifecycle = _advance_paper_state(
        rows_by_ticker=rows_by_ticker,
        state=working_state,
        as_of_date=as_of_date,
        config=cfg,
    )

    candidates, peer_contexts, scan = build_rolling_corr_peer_shock_candidate_rows(
        ohlcv_by_ticker=rows_by_ticker,
        dates=[as_of_date],
        sector_entries=sector_map,
        core_entries_by_date={as_of_date: list(core_entries or [])},
        config=cfg,
    )
    selected, rejected = _select_candidates_for_paper(
        rows_by_ticker=rows_by_ticker,
        candidates=candidates,
        state=working_state,
        config=cfg,
        create_trades=False,
    )
    pending = [_pending_entry_from_candidate(row, cfg) for row in selected]
    working_state["pending_entries"].extend(pending)

    snapshot = {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "asof_date": as_of_date,
        "generated_at": utc_now_iso(),
        "enabled": bool(cfg["enabled"]),
        "paper_enabled": bool(cfg["paper_enabled"]),
        "trade_enabled": False,
        "candidate_count": len(selected),
        "raw_candidate_count": len(candidates),
        "rejected_candidate_count": len(rejected),
        "new_pending_count": len(pending),
        "pending_count": len(working_state["pending_entries"]),
        "open_position_count": len(working_state["open_positions"]),
        "closed_position_count": len(working_state["closed_positions"]),
        "closed_count_today": len(lifecycle["closed_this_run"]),
        "realized_pnl_to_date": _round(
            sum(float(row.get("pnl") or 0.0) for row in working_state["closed_positions"]),
            2,
        ),
        "unrealized_pnl": _unrealized_pnl(
            rows_by_ticker=rows_by_ticker,
            open_positions=working_state["open_positions"],
            as_of_date=as_of_date,
            config=cfg,
        ),
        "candidates": selected,
        "rejected_candidates": rejected[:50],
        "opened_positions_this_run": lifecycle["opened_this_run"],
        "closed_positions_this_run": lifecycle["closed_this_run"],
        "skipped_entries_this_run": lifecycle["skipped_this_run"],
        "peer_shock_context": {
            **scan,
            "rule_version": SOURCE_RULE_VERSION,
            "read_only": True,
            "trade_enabled": False,
            "candidate_count": len(selected),
            "raw_candidate_count": len(candidates),
            "context_samples": peer_contexts[:10],
        },
        "forward_paper_gate": _forward_paper_gate(working_state, cfg),
        "production_impact": _production_impact(),
    }
    if persist:
        save_rolling_corr_peer_shock_paper_state(working_state, state_path)
        append_rolling_corr_peer_shock_paper_snapshot(snapshot, snapshot_log_path)
    return _safe(snapshot)


def build_rolling_corr_peer_shock_historical_trades(
    *,
    ohlcv_by_ticker: dict[str, Any],
    core_entries_by_date: dict[str, list[dict[str, Any]]] | None,
    windows: dict[str, dict[str, str]],
    candidate_universe: dict[str, Any] | list[str] | None = None,
    sector_entries: dict[str, dict[str, Any]] | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cfg = _config(config)
    rows_by_ticker = _normalise_ohlcv_by_ticker(ohlcv_by_ticker)
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
        "peer_contexts_by_window": {},
    }
    for label, window in windows.items():
        dates = [
            day
            for day in _trading_dates(rows_by_ticker)
            if str(window["start"]) <= day <= str(window["end"])
        ]
        candidates, peer_contexts, scan = build_rolling_corr_peer_shock_candidate_rows(
            ohlcv_by_ticker=rows_by_ticker,
            dates=dates,
            sector_entries=sector_map,
            core_entries_by_date=core_entries_by_date or {},
            config=cfg,
        )
        selected, rejected = _select_candidates_for_paper(
            rows_by_ticker=rows_by_ticker,
            candidates=candidates,
            state=empty_rolling_corr_peer_shock_paper_state(),
            config=cfg,
            create_trades=True,
        )
        window_trades = [{**row, "window": label} for row in selected]
        all_trades.extend(window_trades)
        audit["selected_by_window"][label] = len(window_trades)
        audit["raw_candidate_count_by_window"][label] = len(candidates)
        audit["rejected_count_by_window"][label] = len(rejected)
        audit["scan_by_window"][label] = scan
        audit["peer_contexts_by_window"][label] = peer_contexts[:100]
    return all_trades, _safe(audit)


def build_rolling_corr_peer_shock_candidate_rows(
    *,
    ohlcv_by_ticker: dict[str, Any],
    dates: list[str],
    sector_entries: dict[str, dict[str, Any]],
    core_entries_by_date: dict[str, list[dict[str, Any]]],
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    cfg = _config(config)
    rows_by_ticker = _normalise_ohlcv_by_ticker(ohlcv_by_ticker)
    indices = {ticker: _row_index(rows) for ticker, rows in rows_by_ticker.items()}
    all_dates = _trading_dates(rows_by_ticker)
    date_pos = {day: pos for pos, day in enumerate(all_dates)}
    date_set = set(_date10(day) for day in dates)
    eligible_tickers = sorted(ticker for ticker in sector_entries if ticker in rows_by_ticker)
    candidates: list[dict[str, Any]] = []
    peer_contexts: list[dict[str, Any]] = []
    scan = {
        "scanned_trading_days": len(date_set),
        "days_with_peer_shocks": 0,
        "days_with_laggard_candidates": 0,
        "days_with_corr_pairs": 0,
        "raw_peer_shocks": 0,
        "raw_laggard_candidates": 0,
        "raw_corr_pairs": 0,
        "raw_candidates_before_core_flow_filter": 0,
        "raw_candidates_after_core_flow_filter": 0,
        "core_flow_confirmation_required": True,
        "positive_candidate_signal_return_required": True,
        "min_correlation": cfg["min_correlation"],
        "correlation_lookback_days": cfg["correlation_lookback_days"],
        "max_shock_peers_per_day": cfg["max_shock_peers_per_day"],
        "max_laggard_candidates_per_day": cfg["max_laggard_candidates_per_day"],
    }

    for signal_date in sorted(date_set):
        pos = date_pos.get(signal_date)
        if pos is None or pos < int(cfg["correlation_lookback_days"]):
            continue
        prior_dates = all_dates[pos - int(cfg["correlation_lookback_days"]) : pos]
        core_entries = core_entries_by_date.get(signal_date, [])
        if not core_entries:
            continue

        peer_rows = [
            row
            for ticker in eligible_tickers
            if (
                row := _peer_shock_for_ticker(
                    rows_by_ticker=rows_by_ticker,
                    indices=indices,
                    sector_entries=sector_entries,
                    ticker=ticker,
                    signal_date=signal_date,
                    config=cfg,
                )
            )
            is not None
        ]
        if not peer_rows:
            continue
        scan["days_with_peer_shocks"] += 1
        scan["raw_peer_shocks"] += len(peer_rows)
        peer_rows.sort(
            key=lambda row: (
                -float(row["peer_score"]),
                -float(row["peer_signal_day_return"]),
                -float(row["peer_avg_dollar_volume_20d"]),
                row["ticker"],
            )
        )
        peer_rows = peer_rows[: int(cfg["max_shock_peers_per_day"])]

        laggard_rows = [
            row
            for ticker in eligible_tickers
            if (
                row := _laggard_candidate_for_ticker(
                    rows_by_ticker=rows_by_ticker,
                    indices=indices,
                    sector_entries=sector_entries,
                    ticker=ticker,
                    signal_date=signal_date,
                    config=cfg,
                )
            )
            is not None
        ]
        if not laggard_rows:
            continue
        scan["days_with_laggard_candidates"] += 1
        scan["raw_laggard_candidates"] += len(laggard_rows)
        laggard_rows.sort(
            key=lambda row: (
                -float(row["candidate_lag_quality_score"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                row["ticker"],
            )
        )
        laggard_rows = laggard_rows[: int(cfg["max_laggard_candidates_per_day"])]

        vector_by_ticker: dict[str, list[float]] = {}
        for row in [*peer_rows, *laggard_rows]:
            ticker = str(row["ticker"])
            if ticker not in vector_by_ticker:
                vector = _prior_return_vector_for_dates(
                    rows_by_ticker=rows_by_ticker,
                    indices=indices,
                    ticker=ticker,
                    prior_dates=prior_dates,
                )
                if vector is not None:
                    vector_by_ticker[ticker] = vector

        day_rows: list[dict[str, Any]] = []
        for peer in peer_rows:
            peer_ticker = str(peer["ticker"])
            peer_vector = vector_by_ticker.get(peer_ticker)
            if peer_vector is None:
                continue
            for laggard in laggard_rows:
                ticker = str(laggard["ticker"])
                if ticker == peer_ticker:
                    continue
                laggard_vector = vector_by_ticker.get(ticker)
                if laggard_vector is None:
                    continue
                corr = _pearson_corr(peer_vector, laggard_vector)
                if corr is None or corr < float(cfg["min_correlation"]):
                    continue
                same_sector = peer.get("peer_sector") == laggard.get("sector")
                same_industry = peer.get("peer_industry") == laggard.get("industry")
                score = (
                    1.80 * corr
                    + 2.40 * float(peer["peer_relative_vs_spy"])
                    + 1.10 * float(peer["peer_signal_day_return"])
                    + 0.75 * float(laggard["candidate_lag_quality_score"])
                    - 1.20 * max(float(laggard["candidate_signal_day_return"]), 0.0)
                    + (0.08 if same_sector else 0.0)
                    + (0.05 if same_industry else 0.0)
                )
                day_rows.append(
                    {
                        "date": signal_date,
                        "ticker": ticker,
                        "source": SLEEVE_NAME,
                        "candidate_score": _round(score, 6),
                        "peer_ticker": peer_ticker,
                        "rolling_corr_60d": _round(corr, 6),
                        "same_sector_as_peer": bool(same_sector),
                        "same_industry_as_peer": bool(same_industry),
                        "peer_signal_day_return": peer["peer_signal_day_return"],
                        "peer_relative_vs_spy": peer["peer_relative_vs_spy"],
                        "peer_volume_ratio_20d": peer["peer_volume_ratio_20d"],
                        "peer_ret20_excess_spy": peer["peer_ret20_excess_spy"],
                        "peer_avg_dollar_volume_20d": peer["peer_avg_dollar_volume_20d"],
                        "peer_sector": peer.get("peer_sector"),
                        "peer_industry": peer.get("peer_industry"),
                        **laggard,
                        "same_day_ab_entry_count": len(core_entries),
                        "same_day_ab_overlap": True,
                        "same_ticker_ab_overlap": any(
                            str(entry.get("ticker") or "").upper() == ticker
                            for entry in core_entries
                        ),
                        "rule_version": RULE_VERSION,
                        "source_rule_version": SOURCE_RULE_VERSION,
                        "uses_free_ohlcv_only": True,
                        "uses_llm": False,
                        "trade_enabled": False,
                        "known_at": "after_signal_day_close_before_next_open_paper_entry",
                    }
                )

        scan["raw_candidates_before_core_flow_filter"] += len(day_rows)
        if not day_rows:
            continue
        day_rows.sort(key=_candidate_sort_key)
        day_rows = day_rows[: int(cfg["max_raw_rows_per_day"])]
        candidates.extend(day_rows)
        scan["days_with_corr_pairs"] += 1
        scan["raw_corr_pairs"] += len(day_rows)
        scan["raw_candidates_after_core_flow_filter"] += len(day_rows)
        peer_contexts.append(
            {
                "date": signal_date,
                "raw_peer_shock_count": len(peer_rows),
                "raw_laggard_candidate_count": len(laggard_rows),
                "corr_pair_count_kept": len(day_rows),
                "top_peer_ticker": day_rows[0]["peer_ticker"],
                "top_candidate": day_rows[0]["ticker"],
                "top_score": day_rows[0]["candidate_score"],
                "top_rolling_corr_60d": day_rows[0]["rolling_corr_60d"],
                "top_peer_relative_vs_spy": day_rows[0]["peer_relative_vs_spy"],
                "top_candidate_signal_day_return": day_rows[0][
                    "candidate_signal_day_return"
                ],
            }
        )

    candidates.sort(key=_candidate_sort_key)
    scan.update(_threshold_audit(cfg))
    return candidates, peer_contexts, scan


def _select_candidates_for_paper(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
    state: dict[str, Any],
    config: dict[str, Any],
    create_trades: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    used_date_counts: Counter[str] = Counter()
    trading_dates = _trading_dates(rows_by_ticker)
    date_pos = {day: pos for pos, day in enumerate(trading_dates)}
    next_allowed_pos_by_ticker = _cooldown_positions_from_state(
        state=state,
        trading_dates=trading_dates,
        config=config,
    )
    blocked = _blocked_tickers(state)
    for row in candidates:
        signal_date = str(row.get("date") or "")
        ticker = str(row.get("ticker") or "").upper()
        pos = date_pos.get(signal_date)
        if pos is None:
            rejected.append({**row, "filter_reason": "missing_signal_date_position"})
            continue
        if row.get("same_ticker_ab_overlap"):
            rejected.append({**row, "filter_reason": "same_ticker_core_overlap"})
            continue
        if ticker in blocked:
            rejected.append({**row, "filter_reason": "already_pending_or_open"})
            continue
        if used_date_counts[signal_date] >= int(config["daily_entry_slots"]):
            rejected.append({**row, "filter_reason": "daily_top1_limit"})
            continue
        next_allowed = next_allowed_pos_by_ticker.get(ticker, -1)
        if pos < next_allowed:
            rejected.append({**row, "filter_reason": "same_ticker_cooldown"})
            continue
        if create_trades:
            trade = _paper_trade_from_candidate(rows_by_ticker, row, config)
            if trade is None:
                rejected.append({**row, "filter_reason": "missing_next_open_or_exit"})
                continue
            selected.append(trade)
        else:
            selected.append(
                {
                    **row,
                    "intended_notional": float(config["paper_notional_usd"]),
                    "paper_notional_usd": float(config["paper_notional_usd"]),
                }
            )
        used_date_counts[signal_date] += 1
        next_allowed_pos_by_ticker[ticker] = pos + int(config["same_ticker_cooldown_days"])
    return selected, rejected


def _advance_paper_state(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    state: dict[str, Any],
    as_of_date: str,
    config: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    trading_dates = _trading_dates(rows_by_ticker)
    if _asof_trading_pos(trading_dates, as_of_date) is None:
        return {"opened_this_run": [], "closed_this_run": [], "skipped_this_run": []}

    opened_this_run: list[dict[str, Any]] = []
    closed_this_run: list[dict[str, Any]] = []
    skipped_this_run: list[dict[str, Any]] = []

    still_open: list[dict[str, Any]] = []
    for position in state.get("open_positions") or []:
        if not isinstance(position, dict):
            continue
        closed = _close_open_position_if_due(
            rows_by_ticker=rows_by_ticker,
            position=position,
            as_of_date=as_of_date,
            config=config,
        )
        if closed is None:
            still_open.append(position)
        else:
            closed_this_run.append(closed)
    state["open_positions"] = still_open

    still_pending: list[dict[str, Any]] = []
    for pending in state.get("pending_entries") or []:
        if not isinstance(pending, dict):
            continue
        opened, skip_reason = _open_pending_entry_if_due(
            rows_by_ticker=rows_by_ticker,
            pending=pending,
            as_of_date=as_of_date,
            config=config,
        )
        if opened is None:
            if skip_reason is None:
                still_pending.append(pending)
            else:
                skipped = {
                    **pending,
                    "skip_reason": skip_reason,
                    "skipped_at": utc_now_iso(),
                }
                skipped_this_run.append(skipped)
                state["skipped_entries"].append(skipped)
            continue
        opened_this_run.append(opened)
        closed = _close_open_position_if_due(
            rows_by_ticker=rows_by_ticker,
            position=opened,
            as_of_date=as_of_date,
            config=config,
        )
        if closed is None:
            state["open_positions"].append(opened)
        else:
            closed_this_run.append(closed)
    state["pending_entries"] = still_pending
    state["closed_positions"].extend(closed_this_run)

    return {
        "opened_this_run": opened_this_run,
        "closed_this_run": closed_this_run,
        "skipped_this_run": skipped_this_run,
    }


def _open_pending_entry_if_due(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    pending: dict[str, Any],
    as_of_date: str,
    config: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    ticker = str(pending.get("ticker") or "").upper()
    rows = rows_by_ticker.get(ticker) or []
    idx = _row_index(rows).get(str(pending.get("signal_date") or ""))
    if idx is None:
        return None, "missing_signal_date_position"
    entry_idx = idx + 1
    if entry_idx >= len(rows):
        return None, "missing_next_open"
    if _date(rows[entry_idx]) > _date10(as_of_date):
        return None, None
    entry_raw = _value(rows[entry_idx], "open")
    if not entry_raw:
        return None, "missing_entry_open"
    entry_price = apply_entry_fill(entry_raw)
    return (
        {
            **pending,
            "entry_date": _date(rows[entry_idx]),
            "entry_raw_open": _round(entry_raw, 4),
            "entry_price": _round(entry_price, 4),
            "hold_days": int(config["hold_days"]),
            "opened_at": utc_now_iso(),
        },
        None,
    )


def _close_open_position_if_due(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    position: dict[str, Any],
    as_of_date: str,
    config: dict[str, Any],
) -> dict[str, Any] | None:
    ticker = str(position.get("ticker") or "").upper()
    rows = rows_by_ticker.get(ticker) or []
    idx = _row_index(rows).get(str(position.get("signal_date") or ""))
    if idx is None:
        return None
    exit_idx = idx + int(config["hold_days"])
    if exit_idx >= len(rows) or _date(rows[exit_idx]) > _date10(as_of_date):
        return None
    exit_raw = _value(rows[exit_idx], "close")
    if not exit_raw:
        return None
    entry_price = float(position.get("entry_price") or 0.0)
    if entry_price <= 0.0:
        entry_raw = _value(rows[idx + 1], "open") if idx + 1 < len(rows) else None
        if not entry_raw:
            return None
        entry_price = apply_entry_fill(entry_raw)
    exit_price = apply_slippage(exit_raw, SLIPPAGE_BPS_TARGET, "sell")
    pnl_pct_net = (exit_price / entry_price) - 1.0 - float(config["round_trip_cost_pct"])
    notional = float(
        position.get("paper_notional_usd")
        or position.get("intended_notional")
        or config["paper_notional_usd"]
    )
    return {
        **position,
        "exit_date": _date(rows[exit_idx]),
        "exit_raw_close": _round(exit_raw, 4),
        "exit_price": _round(exit_price, 4),
        "pnl_pct_net": _round(pnl_pct_net, 6),
        "pnl": _round(notional * pnl_pct_net, 2),
        "closed_at": utc_now_iso(),
    }


def _unrealized_pnl(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    open_positions: list[dict[str, Any]],
    as_of_date: str,
    config: dict[str, Any],
) -> float:
    total = 0.0
    trading_dates = _trading_dates(rows_by_ticker)
    if _asof_trading_pos(trading_dates, as_of_date) is None:
        return 0.0
    for position in open_positions:
        ticker = str(position.get("ticker") or "").upper()
        rows = rows_by_ticker.get(ticker) or []
        current_idx = _latest_row_index_on_or_before(rows, as_of_date)
        if current_idx is None:
            continue
        current_close = _value(rows[current_idx], "close")
        entry_price = float(position.get("entry_price") or 0.0)
        if not current_close or entry_price <= 0.0:
            continue
        exit_price = apply_slippage(current_close, SLIPPAGE_BPS_TARGET, "sell")
        notional = float(
            position.get("paper_notional_usd")
            or position.get("intended_notional")
            or config["paper_notional_usd"]
        )
        total += notional * (
            (exit_price / entry_price) - 1.0 - float(config["round_trip_cost_pct"])
        )
    return _round(total, 2)


def _paper_trade_from_candidate(
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    candidate: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any] | None:
    rows = rows_by_ticker.get(str(candidate.get("ticker") or "").upper()) or []
    idx = _row_index(rows).get(str(candidate.get("date") or ""))
    if idx is None:
        return None
    entry_idx = idx + 1
    exit_idx = idx + int(config["hold_days"])
    if entry_idx >= len(rows) or exit_idx >= len(rows):
        return None
    entry_raw = _value(rows[entry_idx], "open")
    exit_raw = _value(rows[exit_idx], "close")
    if not entry_raw or not exit_raw:
        return None
    entry_price = apply_entry_fill(entry_raw)
    exit_price = apply_slippage(exit_raw, SLIPPAGE_BPS_TARGET, "sell")
    pnl_pct_net = (exit_price / entry_price) - 1.0 - float(config["round_trip_cost_pct"])
    pnl = float(config["paper_notional_usd"]) * pnl_pct_net
    return {
        **candidate,
        "signal_date": candidate.get("date"),
        "entry_date": _date(rows[entry_idx]),
        "exit_date": _date(rows[exit_idx]),
        "entry_raw_open": _round(entry_raw, 4),
        "exit_raw_close": _round(exit_raw, 4),
        "entry_price": _round(entry_price, 4),
        "exit_price": _round(exit_price, 4),
        "hold_days": int(config["hold_days"]),
        "paper_notional_usd": float(config["paper_notional_usd"]),
        "pnl_pct_net": _round(pnl_pct_net, 6),
        "pnl": _round(pnl, 2),
    }


def _pending_entry_from_candidate(row: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": str(row.get("ticker") or "").upper(),
        "signal_date": row.get("date"),
        "source": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "intended_notional": float(config["paper_notional_usd"]),
        "paper_notional_usd": float(config["paper_notional_usd"]),
        "candidate_score": row.get("candidate_score"),
        "peer_ticker": row.get("peer_ticker"),
        "rolling_corr_60d": row.get("rolling_corr_60d"),
        "trade_enabled": False,
        "created_at": utc_now_iso(),
    }


def _peer_shock_for_ticker(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    config: dict[str, Any],
) -> dict[str, Any] | None:
    rows = rows_by_ticker.get(ticker) or []
    spy_rows = rows_by_ticker.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    lookback = int(config["correlation_lookback_days"])
    if idx is None or spy_idx is None or idx < lookback + 1 or spy_idx < 20:
        return None
    close = _value(rows[idx], "close")
    if close is None or close < float(config["min_price"]):
        return None
    adv20 = _avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < float(config["min_avg_dollar_volume_20d"]):
        return None
    signal_return = _daily_return(rows, idx)
    spy_return = _daily_return(spy_rows, spy_idx)
    volume_ratio = _volume_ratio(rows, idx)
    ret20 = _ret(rows, idx, 20)
    spy_ret20 = _ret(spy_rows, spy_idx, 20)
    if (
        signal_return is None
        or spy_return is None
        or volume_ratio is None
        or ret20 is None
        or spy_ret20 is None
    ):
        return None
    relative_vs_spy = signal_return - spy_return
    ret20_excess_spy = ret20 - spy_ret20
    if signal_return < float(config["min_peer_signal_return"]):
        return None
    if relative_vs_spy < float(config["min_peer_relative_vs_spy"]):
        return None
    if volume_ratio < float(config["min_peer_volume_ratio_20d"]):
        return None
    if ret20_excess_spy < float(config["min_peer_ret20_excess_spy"]):
        return None
    sector_meta = sector_entries[ticker]
    score = (
        3.0 * signal_return
        + 2.0 * relative_vs_spy
        + 0.30 * ret20_excess_spy
        + 0.08 * min(volume_ratio, 5.0)
        + 0.04 * math.log10(max(adv20, 1.0) / 1_000_000.0)
    )
    return {
        "ticker": ticker,
        "peer_signal_day_return": _round(signal_return, 6),
        "peer_relative_vs_spy": _round(relative_vs_spy, 6),
        "peer_volume_ratio_20d": _round(volume_ratio, 6),
        "peer_ret20_excess_spy": _round(ret20_excess_spy, 6),
        "peer_avg_dollar_volume_20d": _round(adv20, 2),
        "peer_score": _round(score, 6),
        "peer_sector": sector_meta.get("sector"),
        "peer_industry": sector_meta.get("industry"),
    }


def _laggard_candidate_for_ticker(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    config: dict[str, Any],
) -> dict[str, Any] | None:
    rows = rows_by_ticker.get(ticker) or []
    spy_rows = rows_by_ticker.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    lookback = int(config["correlation_lookback_days"])
    if idx is None or spy_idx is None:
        return None
    if idx < lookback + 1 or spy_idx < 60 or idx + int(config["hold_days"]) >= len(rows):
        return None
    close = _value(rows[idx], "close")
    if close is None or close < float(config["min_price"]):
        return None
    adv20 = _avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < float(config["min_avg_dollar_volume_20d"]):
        return None
    signal_return = _daily_return(rows, idx)
    close_location = _close_location(rows[idx])
    ret5 = _ret(rows, idx, 5)
    ret20 = _ret(rows, idx, 20)
    ret60 = _ret(rows, idx, 60)
    spy_ret20 = _ret(spy_rows, spy_idx, 20)
    spy_ret60 = _ret(spy_rows, spy_idx, 60)
    realized_vol20 = _realized_vol(rows, idx, 20)
    volume_ratio = _volume_ratio(rows, idx) or 0.0
    required = [
        signal_return,
        close_location,
        ret5,
        ret20,
        ret60,
        spy_ret20,
        spy_ret60,
        realized_vol20,
    ]
    if any(value is None for value in required):
        return None
    assert signal_return is not None
    assert close_location is not None
    assert ret5 is not None
    assert ret20 is not None
    assert ret60 is not None
    assert spy_ret20 is not None
    assert spy_ret60 is not None
    assert realized_vol20 is not None
    ret20_excess_spy = ret20 - spy_ret20
    ret60_excess_spy = ret60 - spy_ret60
    if signal_return < float(config["min_candidate_signal_return"]):
        return None
    if signal_return > float(config["max_candidate_signal_return"]):
        return None
    if close_location < float(config["min_candidate_close_location"]):
        return None
    if ret5 < float(config["min_candidate_ret5"]) or ret5 > float(config["max_candidate_ret5"]):
        return None
    if ret20_excess_spy < float(config["min_candidate_ret20_excess_spy"]):
        return None
    if ret60_excess_spy < float(config["min_candidate_ret60_excess_spy"]):
        return None
    if realized_vol20 > float(config["max_candidate_realized_vol_20d"]):
        return None
    sector_meta = sector_entries[ticker]
    lag_quality = (
        -1.0 * abs(signal_return)
        + 0.65 * ret20_excess_spy
        + 0.25 * ret60_excess_spy
        + 0.15 * close_location
        + 0.04 * math.log10(max(adv20, 1.0) / 1_000_000.0)
        - 0.25 * realized_vol20
    )
    return {
        "ticker": ticker,
        "candidate_signal_day_return": _round(signal_return, 6),
        "candidate_close_location": _round(close_location, 6),
        "candidate_ret5": _round(ret5, 6),
        "candidate_ret20": _round(ret20, 6),
        "candidate_spy_ret20": _round(spy_ret20, 6),
        "candidate_ret20_excess_spy": _round(ret20_excess_spy, 6),
        "candidate_ret60": _round(ret60, 6),
        "candidate_spy_ret60": _round(spy_ret60, 6),
        "candidate_ret60_excess_spy": _round(ret60_excess_spy, 6),
        "candidate_avg_dollar_volume_20d": _round(adv20, 2),
        "candidate_volume_ratio_20d": _round(volume_ratio, 6),
        "candidate_realized_vol_20d": _round(realized_vol20, 6),
        "candidate_lag_quality_score": _round(lag_quality, 6),
        "sector": sector_meta.get("sector"),
        "industry": sector_meta.get("industry"),
        "sector_coverage_status": sector_meta.get("sector_coverage_status"),
    }


def _prior_return_vector_for_dates(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    ticker: str,
    prior_dates: list[str],
) -> list[float] | None:
    rows = rows_by_ticker.get(ticker) or []
    values: list[float] = []
    for day in prior_dates:
        idx = indices.get(ticker, {}).get(day)
        if idx is None or idx < 1:
            return None
        ret = _daily_return(rows, idx)
        if ret is None:
            return None
        values.append(float(ret))
    return values


def _pearson_corr(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < int(DEFAULT_CONFIG["correlation_lookback_days"]):
        return None
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    left_demeaned = [value - left_mean for value in left]
    right_demeaned = [value - right_mean for value in right]
    left_var = sum(value * value for value in left_demeaned)
    right_var = sum(value * value for value in right_demeaned)
    if left_var <= 0.0 or right_var <= 0.0:
        return None
    return sum(a * b for a, b in zip(left_demeaned, right_demeaned)) / math.sqrt(
        left_var * right_var
    )


def _normalise_ohlcv_by_ticker(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return {
        str(ticker).upper(): rows
        for ticker, data in payload.items()
        if (rows := _normalise_ohlcv_rows(data))
    }


def _normalise_ohlcv_rows(rows: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if rows is None:
        return out
    if hasattr(rows, "iterrows"):
        for idx, row in rows.iterrows():
            normalised = _normalise_ohlcv_row(row, idx)
            if normalised is not None:
                out.append(normalised)
    elif isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            normalised = _normalise_ohlcv_row(row, None)
            if normalised is not None:
                out.append(normalised)
    out.sort(key=lambda row: row["date"])
    return out


def _normalise_ohlcv_row(row: Any, idx: Any) -> dict[str, Any] | None:
    def pick(*names: str) -> Any:
        for name in names:
            try:
                value = row.get(name)
            except AttributeError:
                value = None
            if value is not None:
                return value
        return None

    day = pick("date", "Date")
    if day is None or (isinstance(day, str) and not day):
        day = idx
    if day is None or (isinstance(day, str) and not day):
        return None
    return {
        "date": _date10(day),
        "open": _positive_float(pick("open", "Open")),
        "high": _positive_float(pick("high", "High")),
        "low": _positive_float(pick("low", "Low")),
        "close": _positive_float(pick("close", "Close")),
        "volume": _nonnegative_float(pick("volume", "Volume")),
    }


def _resolve_sector_entries(
    *,
    sector_entries: dict[str, dict[str, Any]] | None,
    candidate_universe: dict[str, Any] | list[str] | None,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    allowed = (
        {str(ticker).upper() for ticker in candidate_universe}
        if isinstance(candidate_universe, list)
        else set(rows_by_ticker)
    )

    sources: list[dict[str, Any]] = []
    if sector_entries:
        sources.append(sector_entries)
    if isinstance(candidate_universe, dict) and isinstance(candidate_universe.get("entries"), dict):
        sources.append(candidate_universe["entries"])
    for raw_entries in sources:
        out = _filter_sector_entries(raw_entries, allowed=allowed, rows_by_ticker=rows_by_ticker)
        if out:
            return out

    # Governance fallback feeds carry ticker/title/theme metadata without any
    # sector fields, so an empty resolution falls through to the persisted
    # broad-market sector cache restricted to the same allowed tickers.
    cache = broad_market_sector_map.load_cache()
    cache_entries = cache.get("entries", {}) if isinstance(cache, dict) else {}
    return _filter_sector_entries(cache_entries, allowed=allowed, rows_by_ticker=rows_by_ticker)


def _filter_sector_entries(
    raw_entries: dict[str, Any],
    *,
    allowed: set[str],
    rows_by_ticker: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for ticker, meta in raw_entries.items():
        ticker_u = str(ticker).upper()
        if ticker_u in EXCLUDED_TICKERS or ticker_u not in rows_by_ticker or ticker_u not in allowed:
            continue
        if not isinstance(meta, dict):
            continue
        sector = meta.get("sector")
        status = meta.get("status") or meta.get("sector_coverage_status")
        if not sector or status not in (None, "ok"):
            continue
        out[ticker_u] = {
            "sector": sector,
            "industry": meta.get("industry"),
            "sector_coverage_status": status or "ok",
        }
    return out


def _normalise_state(state: dict[str, Any]) -> None:
    for key in ["pending_entries", "open_positions", "closed_positions", "skipped_entries"]:
        if not isinstance(state.get(key), list):
            state[key] = []
    state["schema_version"] = STATE_SCHEMA_VERSION
    state["sleeve"] = SLEEVE_NAME


def _blocked_tickers(state: dict[str, Any]) -> set[str]:
    blocked = set()
    for key in ["pending_entries", "open_positions"]:
        for row in state.get(key) or []:
            ticker = str(row.get("ticker") or "").upper()
            if ticker:
                blocked.add(ticker)
    return blocked


def _cooldown_positions_from_state(
    *,
    state: dict[str, Any],
    trading_dates: list[str],
    config: dict[str, Any],
) -> dict[str, int]:
    date_pos = {day: pos for pos, day in enumerate(trading_dates)}
    cooldown = int(config["same_ticker_cooldown_days"])
    next_allowed: dict[str, int] = {}
    for key in ["closed_positions", "skipped_entries"]:
        for row in state.get(key) or []:
            if not isinstance(row, dict):
                continue
            ticker = str(row.get("ticker") or "").upper()
            signal_date = str(row.get("signal_date") or row.get("date") or "")
            pos = date_pos.get(signal_date)
            if not ticker or pos is None:
                continue
            next_allowed[ticker] = max(next_allowed.get(ticker, -1), pos + cooldown)
    return next_allowed


def _asof_trading_pos(trading_dates: list[str], as_of_date: str) -> int | None:
    as_of = _date10(as_of_date)
    eligible = [pos for pos, day in enumerate(trading_dates) if day <= as_of]
    return max(eligible) if eligible else None


def _latest_row_index_on_or_before(
    rows: list[dict[str, Any]],
    as_of_date: str,
) -> int | None:
    as_of = _date10(as_of_date)
    candidates = [idx for idx, row in enumerate(rows) if _date(row) <= as_of]
    return max(candidates) if candidates else None


def _forward_paper_gate(state: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    closed = [row for row in state.get("closed_positions") or [] if isinstance(row, dict)]
    pnl_by_ticker: Counter[str] = Counter()
    wins = 0
    for row in closed:
        ticker = str(row.get("ticker") or "").upper()
        pnl = float(row.get("pnl") or 0.0)
        pnl_by_ticker[ticker] += pnl
        if pnl > 0:
            wins += 1
    total_pnl = sum(pnl_by_ticker.values())
    positive = {ticker: pnl for ticker, pnl in pnl_by_ticker.items() if pnl > 0}
    positive_total = sum(positive.values())
    max_share = (
        max(positive.values()) / positive_total if positive_total > 0 and positive else None
    )
    hhi = (
        sum((pnl / positive_total) ** 2 for pnl in positive.values())
        if positive_total > 0 and positive
        else None
    )
    reasons = []
    if len(closed) < int(config["forward_gate_min_closed_trades"]):
        reasons.append("not_enough_closed_forward_paper_trades")
    if bool(config["forward_gate_positive_net_pnl"]) and total_pnl <= 0.0:
        reasons.append("forward_net_pnl_not_positive")
    if closed and wins / len(closed) < float(config["forward_gate_min_win_rate"]):
        reasons.append("forward_win_rate_too_low")
    if max_share is not None and max_share > float(config["forward_gate_max_single_ticker_positive_share"]):
        reasons.append("forward_positive_pnl_concentration_too_high")
    if hhi is not None and hhi > float(config["forward_gate_max_positive_hhi"]):
        reasons.append("forward_positive_hhi_too_high")
    passed = not reasons
    return {
        "passed": passed,
        "status": "passed" if passed else "blocked",
        "reasons": reasons,
        "closed_trade_count": len(closed),
        "net_pnl": _round(total_pnl, 2),
        "win_rate": _round(wins / len(closed), 6) if closed else None,
        "max_single_ticker_positive_share": _round(max_share, 6) if max_share is not None else None,
        "positive_pnl_hhi": _round(hhi, 6) if hhi is not None else None,
    }


def _production_impact() -> dict[str, Any]:
    return {
        "trade_enabled": False,
        "alters_orders": False,
        "shared_policy_changed": False,
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
    }


def _candidate_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        str(row.get("date") or ""),
        -float(row.get("candidate_score") or 0.0),
        -float(row.get("rolling_corr_60d") or 0.0),
        -float(row.get("peer_relative_vs_spy") or 0.0),
        -float(row.get("candidate_avg_dollar_volume_20d") or 0.0),
        str(row.get("peer_ticker") or ""),
        str(row.get("ticker") or ""),
    )


def _threshold_audit(config: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "min_peer_signal_return",
        "min_peer_relative_vs_spy",
        "min_peer_volume_ratio_20d",
        "min_peer_ret20_excess_spy",
        "min_candidate_signal_return",
        "max_candidate_signal_return",
        "min_candidate_close_location",
        "min_candidate_ret5",
        "max_candidate_ret5",
        "min_candidate_ret20_excess_spy",
        "min_candidate_ret60_excess_spy",
        "max_candidate_realized_vol_20d",
    ]
    return {key: config[key] for key in keys}


def _config(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    if overrides:
        cfg.update({key: value for key, value in overrides.items() if value is not None})
    cfg["enabled"] = False
    cfg["trade_enabled"] = False
    return cfg


def _value(row: dict[str, Any], key: str) -> float | None:
    value = row.get(key.lower(), row.get(key.capitalize(), row.get(key.upper())))
    if key.lower() == "volume":
        return _nonnegative_float(value)
    return _positive_float(value)


def _daily_return(rows: list[dict[str, Any]], idx: int) -> float | None:
    if idx < 1:
        return None
    prior = _value(rows[idx - 1], "close")
    close = _value(rows[idx], "close")
    if prior is None or prior <= 0 or close is None:
        return None
    return (close / prior) - 1.0


def _ret(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < lookback:
        return None
    prior = _value(rows[idx - lookback], "close")
    close = _value(rows[idx], "close")
    if prior is None or prior <= 0 or close is None:
        return None
    return (close / prior) - 1.0


def _avg_dollar_volume(rows: list[dict[str, Any]], idx: int, lookback: int = 20) -> float | None:
    if idx < lookback - 1:
        return None
    values = []
    for row in rows[idx - lookback + 1 : idx + 1]:
        close = _value(row, "close")
        volume = _value(row, "volume")
        if close is None or volume is None:
            return None
        values.append(close * volume)
    return sum(values) / len(values)


def _volume_ratio(rows: list[dict[str, Any]], idx: int, lookback: int = 20) -> float | None:
    if idx < lookback:
        return None
    current = _value(rows[idx], "volume")
    prior = [_value(row, "volume") for row in rows[idx - lookback : idx]]
    if current is None or any(value is None for value in prior):
        return None
    avg = sum(float(value) for value in prior if value is not None) / len(prior)
    if avg <= 0:
        return None
    return current / avg


def _close_location(row: dict[str, Any]) -> float | None:
    high = _value(row, "high")
    low = _value(row, "low")
    close = _value(row, "close")
    if high is None or low is None or close is None:
        return None
    span = high - low
    if span <= 0:
        return 0.5
    return (close - low) / span


def _realized_vol(rows: list[dict[str, Any]], idx: int, lookback: int = 20) -> float | None:
    if idx < lookback:
        return None
    values = [_daily_return(rows, day_idx) for day_idx in range(idx - lookback + 1, idx + 1)]
    if any(value is None for value in values):
        return None
    valid = [float(value) for value in values if value is not None]
    mean_value = sum(valid) / len(valid)
    variance = sum((value - mean_value) ** 2 for value in valid) / len(valid)
    return math.sqrt(variance)


def _trading_dates(rows_by_ticker: dict[str, list[dict[str, Any]]]) -> list[str]:
    dates = sorted({row["date"] for rows in rows_by_ticker.values() for row in rows})
    return dates


def _row_index(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {str(row.get("date")): idx for idx, row in enumerate(rows) if row.get("date")}


def _date(row: dict[str, Any]) -> str:
    return _date10(row.get("date") or row.get("Date"))


def _date10(value: Any) -> str:
    return str(value)[:10]


def _positive_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out) or out <= 0:
        return None
    return out


def _nonnegative_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out) or out < 0:
        return None
    return out


def _round(value: Any, digits: int = 4) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_safe(item) for item in value]
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        return None
    return value
