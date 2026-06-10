"""exp-20260610-019: Fundamental Growth RS allocator source extension.

Replay-only alpha search. It tests one fixed candidate-pool/allocation
hypothesis: accepted SEC Companyfacts Fundamental Growth RS paper rows may add
orthogonal fundamental evidence when admitted as a low-priority source family
inside the accepted helper source-priority allocator.

This runner does not change production code, shared helpers, live/default
orders, core ranking, sizing, exits, LLM/news, or watchlists. A positive result
is only a replay lead until the same source admission is implemented in the
shared allocator helper, daily snapshot wiring, and parity tests. No JavaScript
is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from copy import deepcopy
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, EXPERIMENTS_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import accepted_helper_source_priority_allocator_paper_sleeve as allocator  # noqa: E402
import exp_20260610_014_revision_source_priority_allocator_extension as base  # noqa: E402
import fundamental_growth_rs_paper_sleeve as fundamental  # noqa: E402
from data_layer import get_universe  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


framework = base.framework

EXPERIMENT_ID = "exp-20260610-019"
STEM = "fundamental_growth_rs_allocator_source_extension"
TRIAL_FAMILY = "accepted_default_off_helper_source_priority_allocation"
TRIAL_VARIANT_ID = (
    "fundamental_growth_rs_source_family_added_to_accepted_helper_source_priority_allocator_v1"
)
CHANGED_VARIABLE = TRIAL_VARIANT_ID
RULE_VERSION = "fundamental_growth_rs_allocator_source_extension_v1"
SOURCE_RULE_VERSION = "accepted_helper_source_priority_top1_with_fundamental_growth_rs_replay_v1"
OWNER = "alpha-search-automation"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260610_019_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = allocator.BASE_NOTIONAL_USD
HOLD_DAYS = allocator.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = allocator.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = allocator.SAME_TICKER_COOLDOWN_DAYS

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

ACCEPTED_ALLOCATOR_COMPARATOR = {
    "experiment_id": "exp-20260610-014",
    "aggregate_ev_delta": 0.9720,
    "aggregate_pnl_delta": 15197.05,
    "window_deltas": {
        "late_strong": {"ev": 0.5079, "pnl": 4879.33},
        "mid_weak": {"ev": 0.3356, "pnl": 6103.41},
        "old_thin": {"ev": 0.1285, "pnl": 4214.31},
    },
}

FUNDAMENTAL_STANDALONE_COMPARATOR = {
    "experiment_id": "exp-20260528-017",
    "decision": "accepted_candidate_fundamental_growth_rs_low_liability_support",
    "aggregate_ev_delta_vs_core": 8.5419,
    "aggregate_pnl_delta_vs_core": 127144.15,
    "aggregate_ev_delta_vs_prior_accepted": 0.2220,
    "aggregate_pnl_delta_vs_prior_accepted": 2637.02,
}

_ACCEPTED = deepcopy(allocator.SOURCE_PRIORITY)
SOURCE_PRIORITY: "OrderedDict[str, dict[str, Any]]" = OrderedDict(
    [
        (name, {**meta, "rank": int(meta["rank"])})
        for name, meta in _ACCEPTED.items()
    ]
)
SOURCE_PRIORITY["fundamental_growth_rs"] = {
    "rank": 8,
    "description": "accepted SEC Companyfacts Fundamental Growth RS default-off paper",
    "accepted_experiment": "exp-20260528-017",
    "accepted_ev_delta_sum": FUNDAMENTAL_STANDALONE_COMPARATOR[
        "aggregate_ev_delta_vs_prior_accepted"
    ],
    "accepted_pnl_delta_sum": FUNDAMENTAL_STANDALONE_COMPARATOR[
        "aggregate_pnl_delta_vs_prior_accepted"
    ],
}

PREDICTION = {
    "success_probability": 0.20,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "source_overlap_displaces_better_rows",
        "accepted_allocator_window_comparator_regression",
        "fundamental_rows_too_stale",
        "old_thin_regression",
    ],
    "confidence_reason": (
        "Companyfacts Fundamental Growth RS has one accepted low-liability "
        "support experiment and production-visible default-off daily fields, "
        "but exp-20260609-006 showed quality-gated replacement can reject top "
        "winners, while recent allocator source extensions often failed by "
        "displacing better accepted rows. Low rank-8 insertion limits harm yet "
        "makes success unlikely unless fundamental rows appear on dates where "
        "higher-priority accepted sources are absent."
    ),
    "recorded_at": "2026-06-10T17:14:35+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_source_extension_scout",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "default_off_paper_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "uses_llm": False,
    "uses_free_ohlcv_only": False,
    "uses_free_non_ohlcv": True,
    "live_realism_evaluated": True,
    "live_ready": False,
    "execution_envelope": {
        "trade_enabled": False,
        "target_notional_per_paper_trade": BASE_NOTIONAL_USD,
        "daily_entry_slots": 1,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "hold_days": HOLD_DAYS,
        "max_active_positions": 8,
        "liquidity_source": (
            "existing Fundamental Growth RS liquidity/trend gates plus "
            "next-open/10-trading-day fixed-notional paper conversion"
        ),
        "order_semantics": "observe-only next-session-open paper entry; no broker order",
        "portfolio_displacement": "none unless a later shared helper and activation envelope pass",
        "kill_switch": "trade_enabled remains false; no production adapter changes in this scout",
        "failure_handling": "missing Companyfacts or OHLCV rows create rejected source candidates only",
    },
    "parity_note": (
        "This experiment changes no production code. It rebuilds accepted helper "
        "source rows in a replay runner and adds Fundamental Growth RS rows from "
        "the existing shared daily candidate builder. A positive result requires "
        "shared allocator helper, daily snapshot wiring, and parity tests before "
        "retention."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate-pool/allocation alpha: accepted SEC Companyfacts Fundamental "
        "Growth RS rows may add a fundamental-quality source to the accepted "
        "source-priority allocator, filling dates where OHLCV/event/revision "
        "helpers are absent."
    ),
    "2_history_check": {
        "exp-20260528-017": (
            "Accepted Fundamental Growth RS low-liability support. Strong versus "
            "core, modest +0.2220 EV / +$2,637.02 versus its prior accepted "
            "Companyfacts comparator."
        ),
        "exp-20260609-006": (
            "Rejected quality-gated Fundamental Growth RS top-1 replacement: "
            "the standalone source improved versus core but failed versus the "
            "current accepted Companyfacts stack."
        ),
        "exp-20260610-014": (
            "Current accepted allocator with revision source: aggregate EV "
            "+0.9720 and PnL +$15,197.05. This is the binding comparator."
        ),
        "exp-20260610-016": (
            "Rejected post-earnings allocator source extension because it did "
            "not beat the accepted allocator comparator."
        ),
        "exp-20260610-018": (
            "Rejected semiconductor basket breadth thrust despite positive "
            "aggregate because old_thin and concentration were weak."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "docs/backtesting.md canonical three windows. Must improve aggregate "
        "EV/PnL, have no EV/PnL regression windows, satisfy sample/survival/"
        "drawdown/concentration guards, and beat exp-20260610-014 aggregate "
        "and per-window EV/PnL comparator. A pass is only a replay lead until "
        "shared helper parity is implemented."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260610_019_fundamental_growth_rs_allocator_source_extension.py"
    ),
}


def _round(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _candidate_universe_from_sector_entries(
    sector_entries: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "status": "window_sector_known_universe",
        "tickers": sorted(sector_entries),
        "records": sector_entries,
    }


def _core_entry_tickers_by_date(
    core_entries_by_date: dict[str, list[dict[str, Any]]],
) -> dict[str, list[str]]:
    return {
        date_value: sorted(
            {
                str(row.get("ticker") or "").upper()
                for row in rows
                if str(row.get("ticker") or "").strip()
            }
        )
        for date_value, rows in core_entries_by_date.items()
    }


def _source_score(row: dict[str, Any]) -> float:
    for key in (
        "candidate_score",
        "fundamental_growth_rs_score_v1",
        "rs_proxy_score_v1",
        "paper_candidate_score",
        "peer_shock_score",
        "compression_score",
        "source_score",
        "score",
        "rank_score",
    ):
        if row.get(key) is not None:
            return _float(row.get(key))
    return 0.0


def _allocator_score(row: dict[str, Any]) -> float:
    rank = max(1, int(row.get("source_priority_rank") or 999))
    return _round(1000.0 / rank + _float(row.get("source_priority_score")), 6) or 0.0


def _decision_id(row: dict[str, Any]) -> str:
    signal_date = str(row.get("signal_date") or row.get("date") or "")[:10]
    ticker = str(row.get("ticker") or "").upper()
    source_family = str(row.get("source_family") or "unknown")
    return f"ACCEPTED_HELPER_SOURCE_PRIORITY_TOP1_PAPER:{SOURCE_RULE_VERSION}:{signal_date}:{ticker}:{source_family}"


def _renormalise_source_row(
    row: dict[str, Any],
    source_family: str | None = None,
) -> dict[str, Any]:
    family = str(source_family or row.get("source_family") or "")
    if family not in SOURCE_PRIORITY:
        return {}
    meta = SOURCE_PRIORITY[family]
    signal_date = str(row.get("signal_date") or row.get("date") or "")[:10]
    ticker = str(row.get("ticker") or "").upper()
    score = _source_score(row)
    uses_non_ohlcv = family in {
        "revision_surprise_low_extension",
        "fundamental_growth_rs",
    }
    return {
        **deepcopy(row),
        "date": signal_date,
        "signal_date": signal_date,
        "ticker": ticker,
        "source_family": family,
        "source_priority_rank": meta["rank"],
        "source_priority_accepted_experiment": meta["accepted_experiment"],
        "source_priority_score": _round(score, 6),
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "notional_usd": BASE_NOTIONAL_USD,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
        "trade_enabled": False,
        "uses_llm": False,
        "uses_free_ohlcv_only": not uses_non_ohlcv,
        "uses_free_non_ohlcv": uses_non_ohlcv,
    }


def _paper_trade_from_fundamental_candidate(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    candidate: dict[str, Any],
    window_end: str,
) -> dict[str, Any] | None:
    ticker = str(candidate.get("ticker") or "").upper()
    rows = rows_by_ticker.get(ticker) or []
    signal_date = str(candidate.get("date") or candidate.get("signal_date") or "")[:10]
    date_position = {str(row.get("date") or "")[:10]: idx for idx, row in enumerate(rows)}
    idx = date_position.get(signal_date)
    if idx is None:
        return None
    entry_idx = idx + 1
    exit_idx = idx + HOLD_DAYS
    if entry_idx >= len(rows) or exit_idx >= len(rows):
        return None
    exit_date = str(rows[exit_idx].get("date") or "")[:10]
    if exit_date > window_end:
        return None
    entry_raw = fundamental._positive_float(rows[entry_idx].get("open"))
    exit_raw = fundamental._positive_float(rows[exit_idx].get("close"))
    if not entry_raw or not exit_raw:
        return None
    entry_price = fundamental.apply_entry_fill(entry_raw)
    exit_price = fundamental.apply_slippage(
        exit_raw,
        fundamental.SLIPPAGE_BPS_TARGET,
        "sell",
    )
    pnl_pct_net = (exit_price / entry_price) - 1.0 - fundamental.ROUND_TRIP_COST_PCT
    pnl = BASE_NOTIONAL_USD * pnl_pct_net
    trade = {
        **deepcopy(candidate),
        "source": "FUNDAMENTAL_GROWTH_RS_PAPER",
        "source_family": "fundamental_growth_rs",
        "source_rule_version": fundamental.SOURCE_RULE_VERSION,
        "rule_version": fundamental.RULE_VERSION,
        "source_score": _round(_source_score(candidate), 6),
        "candidate_score": _round(_source_score(candidate), 6),
        "signal_date": signal_date,
        "date": signal_date,
        "entry_date": str(rows[entry_idx].get("date") or "")[:10],
        "exit_date": exit_date,
        "entry_raw_open": _round(entry_raw, 4),
        "exit_raw_close": _round(exit_raw, 4),
        "entry_price": _round(entry_price, 4),
        "exit_price": _round(exit_price, 4),
        "hold_days": HOLD_DAYS,
        "source_candidate_intended_notional": candidate.get("intended_notional"),
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "notional_usd": BASE_NOTIONAL_USD,
        "pnl_pct_net": _round(pnl_pct_net, 6),
        "pnl": _round(pnl, 2),
        "paper_pnl": _round(pnl, 2),
        "trade_enabled": False,
        "alters_orders": False,
    }
    return _renormalise_source_row(trade, "fundamental_growth_rs")


def _fundamental_source_trades(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    dates: list[str],
    window: dict[str, str],
    core_entries_by_date: dict[str, list[dict[str, Any]]],
    candidate_universe: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    normalised_rows = {
        ticker: fundamental._normalise_ohlcv_rows(rows)
        for ticker, rows in rows_by_ticker.items()
    }
    universe_tickers = [
        ticker
        for ticker in candidate_universe.get("tickers", [])
        if ticker in normalised_rows
    ]
    companyfacts_rows = fundamental.load_companyfacts_rows(
        max_filed=str(window["end"]),
        tickers=universe_tickers,
    )
    config = {
        **fundamental.DEFAULT_CONFIG,
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "daily_entry_slots": 999,
        "hold_days": HOLD_DAYS,
    }
    universe = fundamental._normalise_candidate_universe(candidate_universe, normalised_rows)
    tickers = [
        ticker
        for ticker in universe["tickers"]
        if ticker in normalised_rows
        and ticker not in fundamental.EXCLUDED_TICKERS
        and fundamental.SECTOR_MAP.get(ticker, "Unknown") not in {"Unknown", "ETF", "Commodities"}
    ]
    fundamentals_index = fundamental.CompanyfactsFundamentalIndex(
        companyfacts_rows,
        config=config,
    )
    sector_residuals = fundamental.SectorResidualIndex(
        normalised_rows,
        fundamental.broad_market_sector_map.load_cache(),
    )
    governor = fundamental._closed_ledger_governor_state([], config)
    core_tickers_by_date = _core_entry_tickers_by_date(core_entries_by_date)
    trades: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    accepted_candidate_count = 0
    rejected_candidate_count = 0
    missing_trade_count = 0
    date_counts: Counter[str] = Counter()
    selected_ticker_counts: Counter[str] = Counter()
    low_liability_count = 0
    filing_recency_count = 0
    operating_quality_count = 0
    source_scan_by_date: list[dict[str, Any]] = []

    for date_value in dates:
        rs_by_ticker = fundamental._rs_context_by_ticker(
            normalised_rows,
            tickers=tickers,
            date=date_value,
            config=config,
        )
        candidates: list[dict[str, Any]] = []
        rejected_rows: list[dict[str, Any]] = []
        current_core = set(core_tickers_by_date.get(date_value, []))
        for ticker in tickers:
            candidate = fundamental._candidate_for_ticker(
                rows_by_ticker=normalised_rows,
                ticker=ticker,
                as_of=date_value,
                fundamentals=fundamentals_index,
                rs_by_ticker=rs_by_ticker,
                sector_residuals=sector_residuals,
                governor=governor,
                config=config,
            )
            if candidate is None:
                continue
            if ticker in current_core:
                rejected_rows.append({**candidate, "reasons": ["same_ticker_core_overlap"]})
                continue
            candidates.append(candidate)
        candidates.sort(
            key=lambda row: (
                row["date"],
                -float(row["fundamental_growth_rs_score_v1"]),
                -float(row["rs_proxy_score_v1"]),
                -int(row["fundamental_growth_points_v1"]),
                -float(row["avg_dollar_volume_20"]),
                row["ticker"],
            )
        )
        for rank, candidate in enumerate(candidates, start=1):
            candidate["fundamental_growth_rs_candidate_rank_on_signal_date"] = rank
            candidate["max_paper_trades_per_day"] = int(config["daily_entry_slots"])
        accepted_candidate_count += len(candidates)
        rejected_candidate_count += len(rejected_rows)
        if candidates or rejected_rows:
            source_scan_by_date.append(
                {
                    "date": date_value,
                    "accepted_candidates": len(candidates),
                    "rejected_candidates": len(rejected_rows),
                    "top_candidate": (
                        {
                            "ticker": candidates[0].get("ticker"),
                            "score": candidates[0].get("fundamental_growth_rs_score_v1"),
                        }
                        if candidates
                        else None
                    ),
                }
            )
        for candidate in candidates:
            trade = _paper_trade_from_fundamental_candidate(
                rows_by_ticker=normalised_rows,
                candidate=candidate,
                window_end=str(window["end"]),
            )
            if trade is None:
                missing_trade_count += 1
                rejected.append({**candidate, "filter_reason": "missing_next_open_or_exit"})
                continue
            trades.append(trade)
            date_counts[str(trade.get("signal_date") or "")[:10]] += 1
            selected_ticker_counts[str(trade.get("ticker") or "").upper()] += 1
            if trade.get("low_liability_pass_v1"):
                low_liability_count += 1
            if trade.get("filing_recency_pass_v1"):
                filing_recency_count += 1
            if trade.get("operating_profit_quality_pass_v1"):
                operating_quality_count += 1

    return trades, {
        "rule_version": fundamental.RULE_VERSION,
        "source_rule_version": fundamental.SOURCE_RULE_VERSION,
        "companyfacts_row_count": len(companyfacts_rows),
        "companyfacts_ticker_count": len({str(row.get("ticker") or "").upper() for row in companyfacts_rows}),
        "candidate_count": accepted_candidate_count,
        "rejected_candidate_count": rejected_candidate_count,
        "trade_count": len(trades),
        "missing_trade_count": missing_trade_count,
        "trade_date_count": len(date_counts),
        "unique_trade_ticker_count": len(selected_ticker_counts),
        "selected_ticker_counts": dict(sorted(selected_ticker_counts.items())),
        "low_liability_candidate_trades": low_liability_count,
        "filing_recency_candidate_trades": filing_recency_count,
        "operating_quality_candidate_trades": operating_quality_count,
        "sample_source_scan_by_date": source_scan_by_date[:40],
        "source_caveat": (
            "Rows are rebuilt from the existing shared Fundamental Growth RS "
            "daily candidate builder. This runner adds historical trade "
            "conversion and allocator source admission locally, so a positive "
            "result is not retained until shared historical/daily allocator "
            "parity is implemented."
        ),
    }


def _select_priority_rows(
    *,
    source_rows: list[dict[str, Any]],
    trading_dates: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    candidates = [
        _renormalise_source_row(row)
        for row in source_rows
        if str(row.get("source_family") or "") in SOURCE_PRIORITY
    ]
    candidates = [row for row in candidates if row]
    candidates.sort(
        key=lambda row: (
            str(row.get("signal_date") or "")[:10],
            int(row.get("source_priority_rank") or 999),
            -_float(row.get("source_priority_score")),
            str(row.get("ticker") or ""),
        )
    )
    date_position = {date_value: idx for idx, date_value in enumerate(trading_dates)}
    used_date_counts: Counter[str] = Counter()
    next_allowed_pos_by_ticker: dict[str, int] = {}
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for row in candidates:
        signal_date = str(row.get("signal_date") or "")[:10]
        ticker = str(row.get("ticker") or "").upper()
        pos = date_position.get(signal_date)
        if pos is None:
            rejected.append({**row, "filter_reason": "missing_signal_date_position"})
            continue
        if used_date_counts[signal_date] >= MAX_PAPER_TRADES_PER_DAY:
            rejected.append({**row, "filter_reason": "daily_top1_source_priority_limit"})
            continue
        if pos < next_allowed_pos_by_ticker.get(ticker, -1):
            rejected.append({**row, "filter_reason": "same_ticker_cooldown"})
            continue
        out = {
            **deepcopy(row),
            "source": "ACCEPTED_HELPER_SOURCE_PRIORITY_TOP1_PAPER",
            "sleeve": "ACCEPTED_HELPER_SOURCE_PRIORITY_TOP1_PAPER",
            "rule_version": RULE_VERSION,
            "source_rule_version": SOURCE_RULE_VERSION,
            "decision_id": _decision_id(row),
            "candidate_score": _allocator_score(row),
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "notional_usd": BASE_NOTIONAL_USD,
            "paper_status": "closed",
            "trade_enabled": False,
            "alters_orders": False,
        }
        selected.append(out)
        used_date_counts[signal_date] += 1
        next_allowed_pos_by_ticker[ticker] = pos + SAME_TICKER_COOLDOWN_DAYS
    audit = {
        "source_candidate_count": len(candidates),
        "selected_priority_trade_count": len(selected),
        "filtered_priority_candidate_count": len(rejected),
        "source_candidate_counts": dict(
            Counter(str(row.get("source_family") or "unknown") for row in candidates)
        ),
        "selected_source_counts": dict(
            Counter(str(row.get("source_family") or "unknown") for row in selected)
        ),
        "daily_entry_slots": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
    }
    return selected, rejected, audit


def _build_extended_source_trades(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    dates: list[str],
    label: str,
    cfg: dict[str, str],
    core_entries_by_date: dict[str, list[dict[str, Any]]],
    sector_entries: dict[str, dict[str, Any]],
    candidate_universe: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    existing_rows, existing_audit = base._build_extended_source_trades(
        snapshot=snapshot,
        dates=dates,
        label=label,
        cfg=cfg,
        core_entries_by_date=core_entries_by_date,
        sector_entries=sector_entries,
        candidate_universe=candidate_universe,
    )
    existing_rows = [
        row
        for row in (_renormalise_source_row(row) for row in existing_rows)
        if row
    ]
    fundamental_rows, fundamental_audit = _fundamental_source_trades(
        rows_by_ticker=snapshot,
        dates=dates,
        window=cfg,
        core_entries_by_date=core_entries_by_date,
        candidate_universe=candidate_universe,
    )
    source_rows = existing_rows + fundamental_rows
    source_trade_counts = OrderedDict(
        (source, len([row for row in source_rows if row.get("source_family") == source]))
        for source in SOURCE_PRIORITY
    )
    raw_candidate_counts = OrderedDict()
    for source in SOURCE_PRIORITY:
        if source == "fundamental_growth_rs":
            raw_candidate_counts[source] = fundamental_audit["candidate_count"]
        else:
            raw_candidate_counts[source] = existing_audit.get("raw_candidate_counts", {}).get(source)
    source_audits = dict(existing_audit.get("source_audits", {}))
    source_audits["fundamental_growth_rs"] = fundamental_audit
    return source_rows, {
        "source_priority": SOURCE_PRIORITY,
        "source_trade_counts": dict(source_trade_counts),
        "raw_candidate_counts": dict(raw_candidate_counts),
        "source_audits": source_audits,
        "extension_policy": {
            "fundamental_growth_rs_rank": SOURCE_PRIORITY["fundamental_growth_rs"]["rank"],
            "rank_reason": (
                "Inserted as rank 8 after all current accepted allocator sources. "
                "No source thresholds, notional, hold, top-N, or cooldown are tuned."
            ),
        },
    }


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
    window_rows: OrderedDict[str, dict[str, Any]],
) -> dict[str, Any]:
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    failed: list[str] = []
    aggregate_ev = float(aggregate["expected_value_score_delta_sum"] or 0.0)
    aggregate_pnl = float(aggregate["total_pnl_delta_sum"] or 0.0)
    if aggregate_ev <= 0.0:
        failed.append("aggregate_ev_not_positive")
    if aggregate_pnl <= 0.0:
        failed.append("aggregate_pnl_not_positive")
    if int(aggregate["windows_ev_regressed"] or 0) > 0:
        failed.append("window_ev_regression")
    if int(aggregate["windows_pnl_regressed"] or 0) > 0:
        failed.append("window_pnl_regression")
    if target_summary["total_trade_count"] < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_summary["windows_with_target_trades"]) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if float(aggregate["max_drawdown_delta_max"] or 0.0) > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if min_survival < 0.05:
        failed.append("core_survival_rate_below_5pct")
    if not concentration_passed:
        failed.append("target_concentration_failed")
    if aggregate_ev <= ACCEPTED_ALLOCATOR_COMPARATOR["aggregate_ev_delta"]:
        failed.append("accepted_allocator_ev_comparator_not_beaten")
    if aggregate_pnl <= ACCEPTED_ALLOCATOR_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_allocator_pnl_comparator_not_beaten")

    comparator_regressions: list[str] = []
    for label, row in window_rows.items():
        comparator = ACCEPTED_ALLOCATOR_COMPARATOR["window_deltas"][label]
        delta = row["delta"]
        if float(delta.get("expected_value_score") or 0.0) < comparator["ev"]:
            comparator_regressions.append(f"{label}_ev")
        if float(delta.get("total_pnl") or 0.0) < comparator["pnl"]:
            comparator_regressions.append(f"{label}_pnl")
    if comparator_regressions:
        failed.append("accepted_allocator_window_comparator_regression")

    passed = not failed
    return {
        "passed": passed,
        "decision": (
            "positive_replay_lead_not_promoted_fundamental_growth_rs_allocator_source_extension"
            if passed
            else "rejected_fundamental_growth_rs_allocator_source_extension"
        ),
        "failed_reasons": failed,
        "comparator_regressions": comparator_regressions,
        "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
        "windows_ev_improved": aggregate["windows_ev_improved"],
        "windows_ev_regressed": aggregate["windows_ev_regressed"],
        "windows_pnl_improved": aggregate["windows_pnl_improved"],
        "windows_pnl_regressed": aggregate["windows_pnl_regressed"],
        "target_trade_count": target_summary["total_trade_count"],
        "target_trade_count_min": MIN_TARGET_TRADES,
        "target_windows": target_summary["windows_with_target_trades"],
        "target_window_count_min": MIN_TARGET_WINDOWS,
        "max_drawdown_worse": aggregate["max_drawdown_delta_max"],
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "minimum_core_survival_rate": round(min_survival, 6),
        "survival_guard_passed": min_survival >= 0.05,
        "accepted_allocator_comparator": ACCEPTED_ALLOCATOR_COMPARATOR,
        "target_concentration": {
            "passed": concentration_passed,
            "max_single_positive_pnl_share": target_summary[
                "max_single_positive_pnl_share"
            ],
            "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi": target_summary["positive_pnl_hhi"],
            "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
        },
    }


def _build_payload() -> dict[str, Any]:
    timestamp = framework._utc_now()
    gate2_open_positions = framework.sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(get_universe())
    sector_entries = framework._load_sector_entries()
    before_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    after_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    window_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    target_trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    filtered_candidates_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    source_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    priority_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    warehouse_coverage_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] Fundamental Growth RS source-priority allocator extension")
        before_result = framework.shadow._run_baseline(universe, cfg)
        before = framework.overlay_helper._metrics(before_result)
        snapshot = framework._load_window_snapshot(
            cfg=cfg,
            eligible_tickers=set(sector_entries),
        )
        dates = [
            day
            for day in framework.shadow._trading_dates(snapshot)
            if str(cfg["start"]) <= day <= str(cfg["end"])
        ]
        window_sector_entries = {
            ticker: meta for ticker, meta in sector_entries.items() if ticker in snapshot
        }
        candidate_universe = _candidate_universe_from_sector_entries(window_sector_entries)
        core_entries = framework.shadow._baseline_entries(before_result)
        source_trades, source_audit = _build_extended_source_trades(
            snapshot=snapshot,
            dates=dates,
            label=label,
            cfg=cfg,
            core_entries_by_date=core_entries,
            sector_entries=window_sector_entries,
            candidate_universe=candidate_universe,
        )
        selected, filtered, priority_audit = _select_priority_rows(
            source_rows=source_trades,
            trading_dates=dates,
        )
        overlay = framework.sleeve._overlay_from_paper_trades(before_result, selected)
        after = framework.overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = framework.overlay_helper._delta(after, before)

        before_metrics[label] = before
        after_metrics[label] = after
        target_trades_by_window[label] = selected
        filtered_candidates_by_window[label] = filtered[:100]
        source_audit_by_window[label] = source_audit
        priority_audit_by_window[label] = priority_audit
        warehouse_coverage_by_window[label] = {
            "loaded_ticker_count": len(snapshot),
            "sector_known_candidate_ticker_count": len(window_sector_entries),
            "source": _repo_rel(framework.WAREHOUSE),
        }
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected),
            "all_source_trade_count": len(source_trades),
            "source_trade_counts": source_audit["source_trade_counts"],
            "raw_source_candidate_counts": source_audit["raw_candidate_counts"],
            "selected_source_counts": priority_audit["selected_source_counts"],
            "filtered_priority_candidate_count": len(filtered),
            "fundamental_selected_count": priority_audit["selected_source_counts"].get(
                "fundamental_growth_rs",
                0,
            ),
            "fundamental_source_trade_count": source_audit["source_trade_counts"].get(
                "fundamental_growth_rs",
                0,
            ),
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = framework._aggregate_window_rows(window_rows)
    target_summary = framework.sleeve._target_trade_summary(target_trades_by_window)
    gate4 = _gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
        window_rows=window_rows,
    )
    passed = bool(gate4["passed"])
    status = "positive_replay_lead_not_promoted" if passed else "rejected"
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": passed,
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if passed else 0.0)) ** 2,
            6,
        ),
    }
    if passed:
        interpretation = (
            "Fundamental Growth RS rows beat the accepted allocator comparator "
            "as a replay lead, but no shared allocator policy changed."
        )
        reflection = (
            "The source added fundamental replacement value on dates where "
            "higher-priority source rows were absent or weaker. Retention still "
            "requires a shared allocator helper and daily parity implementation."
        )
    else:
        interpretation = (
            "The Fundamental Growth RS source extension failed to beat the "
            "current accepted source-priority allocator comparator."
        )
        reflection = (
            "The standalone Companyfacts+RS sleeve remains accepted, but its "
            "rows did not add enough incremental replacement value after the "
            "accepted allocator's higher-priority rows and same-ticker cooldown. "
            "The likely failure mode is overlap/displacement plus stale "
            "fundamental-row timing, not a defect in the original standalone "
            "Companyfacts helper."
        )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": gate4["decision"],
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "change_type": "replay_only_candidate_pool_source_extension_scout",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "free_sec_companyfacts_plus_ohlcv_rs_candidate_pool",
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "accepted_companyfacts_source_family_allocator_extension",
        "nearby_prior_experiments": [
            "exp-20260528-017",
            "exp-20260609-006",
            "exp-20260610-014",
            "exp-20260610-016",
            "exp-20260610-018",
        ],
        "prior_trial_count": 6,
        "prediction": PREDICTION,
        "calibration": calibration,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "replay-only Fundamental Growth RS source-family extension over "
                "the accepted helper source-priority allocator"
            ),
            "windows": framework.WINDOWS,
            "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
            "companyfacts_source": "data/non_ohlcv/sec_companyfacts_selected_*.jsonl",
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "Existing accepted allocator source rows are rebuilt through "
                "the accepted helper. Fundamental Growth RS rows are generated "
                "from the existing shared daily candidate builder and converted "
                "to fixed $4,000 next-open/10-trading-day paper trades in this runner."
            ),
        },
        "parameters": {
            "rule_version": RULE_VERSION,
            "source_rule_version": SOURCE_RULE_VERSION,
            "source_priority": SOURCE_PRIORITY,
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "accepted_allocator_comparator": ACCEPTED_ALLOCATOR_COMPARATOR,
            "fundamental_standalone_comparator": FUNDAMENTAL_STANDALONE_COMPARATOR,
            "locked_variables": [
                "all accepted allocator source priorities except adding rank-8 fundamental_growth_rs",
                "all Fundamental Growth RS shared candidate thresholds",
                "allocator daily top-1",
                "allocator same-ticker cooldown",
                "paper notional",
                "10-trading-day hold",
                "core signal generation/ranking/sizing/exits",
                "LLM/news paths",
                "live/default orders",
            ],
        },
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": (
                "docs/backtesting.md current canonical baseline and same-run "
                "before_metrics inside this artifact"
            ),
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "warehouse ohlcv Date/Open/High/Low/Close/Volume",
                "data/reference/broad_market_sector_map.json sector/industry/status",
                "accepted helper source rows with signal_date/ticker/source_family",
                "SEC Companyfacts filed/end/fy/fp/value/canonical",
                "Fundamental Growth RS rows with entry_date, exit_date, entry_price, exit_price, pnl",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": round(min_survival, 6),
            "passed": min_survival >= 0.05,
            "note": (
                "No core filter or live candidate ranking changed. The source "
                "extension is replay-only/default-off paper, so core signals "
                "generated and survived are unchanged from baseline."
            ),
        },
        "gate4": gate4,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict((label, row["delta"]) for label, row in window_rows.items()),
            "aggregate": aggregate,
        },
        "window_rows": window_rows,
        "target_trades_by_window": target_trades_by_window,
        "target_trade_summary": target_summary,
        "filtered_priority_candidates_by_window": filtered_candidates_by_window,
        "source_audit_by_window": source_audit_by_window,
        "priority_audit_by_window": priority_audit_by_window,
        "warehouse_coverage_by_window": warehouse_coverage_by_window,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "accepted_comparators": {
            "accepted_allocator": ACCEPTED_ALLOCATOR_COMPARATOR,
            "fundamental_growth_rs_standalone": FUNDAMENTAL_STANDALONE_COMPARATOR,
            "included_source_priority": SOURCE_PRIORITY,
        },
        "interpretation": interpretation,
        "rejection_reason": None if passed else "; ".join(gate4["failed_reasons"]),
        "post_run_reflection": {
            "why_result_happened": reflection,
            "forbidden_near_neighbor_retry": (
                "Do not retry by changing Fundamental Growth RS source rank, "
                "Companyfacts thresholds, RS thresholds, allocator top-N, "
                "notional, hold days, or cooldown on the same frozen windows."
            ),
            "new_evidence_required": (
                "A retry needs forward allocator displacement rows, a materially "
                "different free data field, or a shared historical/daily "
                "Companyfacts allocator helper that changes evidence timing rather "
                "than source priority retuning."
            ),
        },
        "anti_js": "No JavaScript was used.",
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
    }


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Accepted dEV | Before PnL | After PnL | dPnL | Accepted dPnL | Trades | FGRS selected | Top source |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        row = payload["window_rows"][label]
        selected_counts = row["selected_source_counts"]
        top_source = "none"
        if selected_counts:
            top_source = sorted(selected_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
        comparator = ACCEPTED_ALLOCATOR_COMPARATOR["window_deltas"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | {cev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | ${cpnl:+,.2f} | {trades} | {fg_trades} | {top_source} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                cev=comparator["ev"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                cpnl=comparator["pnl"],
                trades=row["target_trade_count"],
                fg_trades=row["fundamental_selected_count"],
                top_source=top_source,
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Fundamental Growth RS Allocator Source Extension",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4",
            "",
            *rows,
            "",
            "- Aggregate EV delta: `{:+.4f}` versus accepted allocator `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"],
                ACCEPTED_ALLOCATOR_COMPARATOR["aggregate_ev_delta"],
            ),
            "- Aggregate PnL delta: `${:+,.2f}` versus accepted allocator `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"],
                ACCEPTED_ALLOCATOR_COMPARATOR["aggregate_pnl_delta"],
            ),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "## Production Impact",
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "production_accepted": False,
        "shared_adapter_required": bool(payload["gate4"]["passed"]),
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": "experiments/logs/exp-20260610-014.json",
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate[
            "expected_value_score_delta_pct"
        ],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "accepted_comparators": payload["accepted_comparators"],
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_after": payload["after_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label][
                    "total_pnl"
                ],
                "source_trade_count": payload["window_rows"][label]["all_source_trade_count"],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
                "fundamental_selected_count": payload["window_rows"][label][
                    "fundamental_selected_count"
                ],
                "fundamental_source_trade_count": payload["window_rows"][label][
                    "fundamental_source_trade_count"
                ],
                "selected_source_counts": payload["window_rows"][label][
                    "selected_source_counts"
                ],
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _update_ticket_and_registry(
    payload: dict[str, Any],
    log_record: dict[str, Any],
) -> None:
    aggregate = payload["delta_metrics"]["aggregate"]
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "production_accepted": False,
        "shared_adapter_required": bool(payload["gate4"]["passed"]),
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "decision": payload["decision"],
        "summary": payload["interpretation"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": log_record["aggregate_expected_value_delta"],
        "aggregate_strategy_total_pnl_delta": log_record[
            "aggregate_strategy_total_pnl_delta"
        ],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )

    ticket = {}
    if TICKET_JSON.exists():
        ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8"))
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "updated_at": payload["timestamp"],
            "decision": payload["decision"],
            "result": result,
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "card_file": _repo_rel(CARD_MD),
            "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        }
    )
    scope = set(ticket.get("allowed_write_scope") or [])
    scope.update(payload["related_files"])
    ticket["allowed_write_scope"] = sorted(scope)
    framework._write_json(TICKET_JSON, ticket)


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": payload["related_files"],
        "file_hashes": {
            _repo_rel(Path(__file__)): framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): framework._sha256(CARD_MD),
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def main() -> None:
    payload = _build_payload()
    log_record = _build_log_record(payload)
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, log_record)
    framework._write_text(CARD_MD, _build_card(payload))
    framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    _update_ticket_and_registry(payload, log_record)
    _write_manifest(payload)
    print(
        "completed {experiment_id}: {decision} | dEV={ev:+.4f} | dPnL=${pnl:+,.2f}".format(
            experiment_id=EXPERIMENT_ID,
            decision=payload["decision"],
            ev=payload["delta_metrics"]["aggregate"]["expected_value_score_delta_sum"],
            pnl=payload["delta_metrics"]["aggregate"]["total_pnl_delta_sum"],
        )
    )


if __name__ == "__main__":
    main()
