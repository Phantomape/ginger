"""exp-20260611-003: VBB source-priority allocator extension scout.

Replay-only alpha search. This tests one fixed candidate-pool/allocation
hypothesis: the accepted volume-breadth breakout paper helper should be
visible as a rank-1 source family inside the accepted helper source-priority
allocator because its standalone three-window EV was higher than the current
allocator components.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. A positive result is
only a replay lead until the allocator helper and daily snapshot surface are
updated and parity-tested. No JavaScript is used.
"""

from __future__ import annotations

import json
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

import exp_20260610_009_fiftytwo_allocator_source_extension as allocator_base  # noqa: E402
import exp_20260526_013_volume_breadth_breakout_sleeve as vbb_prior  # noqa: E402
import volume_breadth_breakout_paper_sleeve as vbb  # noqa: E402


framework = allocator_base.framework

EXPERIMENT_ID = "exp-20260611-003"
STEM = "vbb_allocator_source_extension"
TRIAL_FAMILY = "accepted_default_off_helper_source_priority_allocation"
TRIAL_VARIANT_ID = (
    "volume_breadth_source_family_added_to_accepted_helper_source_priority_allocator_v1"
)
CHANGED_VARIABLE = TRIAL_VARIANT_ID
RULE_VERSION = "volume_breadth_allocator_source_extension_replay_v1"
SOURCE_RULE_VERSION = "accepted_helper_source_priority_top1_with_vbb_replay_v1"
OWNER = "alpha-search-automation"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260611_003_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

ACCEPTED_VBB_COMPARATOR = {
    "experiment_id": "exp-20260526-014",
    "decision": "accepted_shared_volume_breadth_breakout_paper_adapter",
    "aggregate_ev_delta": 0.7124,
    "aggregate_pnl_delta": 13225.50,
    "target_trade_count": 47,
}

ACCEPTED_ALLOCATOR_COMPARATOR = allocator_base.ACCEPTED_ALLOCATOR_COMPARATOR

EXECUTION_ENVELOPE = allocator_base.ExecutionEnvelope(
    base_notional=allocator_base.BASE_NOTIONAL_USD,
    max_capital_pct=0.32,
    min_dollar_volume=vbb_prior.MIN_DOLLAR_VOLUME,
    slippage_bps=5.0,
    max_displacement=1,
    max_concurrent=8,
    order_semantics="next_open_paper_only",
    kill_switch_drawdown_pct=None,
    sleeve_drawdown_stop_pct=None,
    notes=(
        "Top-1/day accepted-helper allocator, fixed $4,000 paper notional, "
        "8 max active default-off paper positions, 10-trading-day hold, and "
        "12-trading-day same-ticker cooldown. VBB source rows keep the accepted "
        "$40M signal-day dollar-volume minimum plus volume-breadth, market-up, "
        "above-50d, breakout, volume-ratio, and SPY-relative gates. This "
        "experiment is not live-ready because the allocator still needs a "
        "dedicated realized-ledger kill switch before any trade_enabled=true "
        "release."
    ),
)

SOURCE_PRIORITY: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
SOURCE_PRIORITY["volume_breadth_breakout"] = {
    "rank": 1,
    "description": "accepted volume-breadth breakout source",
    "accepted_experiment": "exp-20260526-014",
    "accepted_ev_delta_sum": ACCEPTED_VBB_COMPARATOR["aggregate_ev_delta"],
    "accepted_pnl_delta_sum": ACCEPTED_VBB_COMPARATOR["aggregate_pnl_delta"],
}
for source_name, source_meta in allocator_base.ACCEPTED_SOURCE_PRIORITY.items():
    meta = deepcopy(source_meta)
    meta["rank"] = int(meta["rank"]) + 1
    SOURCE_PRIORITY[source_name] = meta

PREDICTION = {
    "success_probability": 0.24,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "source_overlap_with_existing_allocator",
        "accepted_allocator_comparator_not_beaten",
        "window_regression",
        "displaces_better_existing_rows",
        "concentration_failed",
    ],
    "confidence_reason": (
        "VBB was an accepted shared free-OHLCV paper source with EV +0.7124 "
        "and PnL +$13,225.50, higher than current allocator components. The "
        "test remains low-to-moderate confidence because source additions must "
        "beat exp-20260610-005 after displacement, not merely core baseline."
    ),
    "recorded_at": "2026-06-11T01:17:09+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "private_replay_scout_no_shared_vbb_allocator_source",
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
    "uses_free_ohlcv_only": True,
    "live_realism_evaluated": True,
    "live_ready": False,
    "execution_envelope": EXECUTION_ENVELOPE.to_dict(),
    "parity_note": (
        "This experiment changes no production code. It reconstructs VBB source "
        "rows from the accepted VBB replay semantics and applies the accepted "
        "allocator overlay in replay only. A positive result cannot be promoted "
        "until the shared allocator helper, daily snapshots, ledger, and parity "
        "tests admit the same VBB source semantics."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool/allocation: the accepted VBB source has higher "
        "standalone three-window EV than current allocator components but is "
        "absent from accepted source-priority allocation. Admitting it as fixed "
        "rank 1 may add broad-participation breakout replacement value without "
        "adding noisy tickers."
    ),
    "2_history_check": {
        "exp-20260526-014": (
            "Accepted shared VBB adapter: aggregate EV +0.7124, PnL +$13,225.50, "
            "47 trades, and production-visible default-off helper semantics."
        ),
        "exp-20260610-005": (
            "Accepted source-priority allocator without VBB: aggregate EV +0.8971 "
            "and PnL +$14,502.52. This is the binding comparator."
        ),
        "exp-20260610-006": (
            "Rejected macro-relief allocator extension; source additions can be "
            "positive vs core but still fail the accepted allocator comparator."
        ),
        "exp-20260610-009": (
            "Rejected 52-week allocator extension; overlap/displacement risk is "
            "the expected failure mode."
        ),
    },
    "3_single_causal_variable": (
        "One fixed policy bundle: accepted VBB top-1 source rows added as "
        "rank-1 source family inside the accepted helper source-priority "
        "allocator. VBB thresholds, existing source rules, next-open entry, "
        "10-day hold, costs, top-1/day, and cooldown remain fixed."
    ),
    "4_acceptance_standard": (
        "Use docs/backtesting.md three canonical windows. Accept only as a "
        "replay lead if aggregate EV/PnL improve, no EV/PnL regression window "
        "appears, target sample >=20 across all three windows, survival >=5%, "
        "drawdown drift <=0.5pp, concentration guard passes, and exp-20260610-005 "
        "accepted allocator aggregate plus per-window EV/PnL comparator is beaten."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260611_003_vbb_allocator_source_extension.py"
    ),
}

def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _build_vbb_source_trades(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    dates: list[str],
    candidate_universe: dict[str, Any],
    core_entries_by_date: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    universe = sorted(
        set(candidate_universe.get("tickers") or [])
        .intersection(rows_by_ticker)
        .difference(vbb_prior.EXCLUDED_TICKERS)
    )
    breadth_by_date = vbb_prior._breadth_context_by_date(
        rows_by_ticker,
        dates,
        universe,
    )
    spy_rows = vbb_prior.ohlcv_helper._series(rows_by_ticker, "SPY")
    spy_index = vbb_prior.ohlcv_helper._row_index(spy_rows)
    candidates: list[dict[str, Any]] = []
    raw_breakouts = 0
    breadth_pass_dates = [
        date
        for date, context in breadth_by_date.items()
        if context["volume_breadth_thrust_passed"]
    ]

    for ticker in universe:
        rows = vbb_prior.ohlcv_helper._series(rows_by_ticker, ticker)
        idx_by_date = vbb_prior.ohlcv_helper._row_index(rows)
        for signal_date in dates:
            context = breadth_by_date.get(signal_date) or {}
            if not context.get("volume_breadth_thrust_passed"):
                continue
            idx = idx_by_date.get(signal_date)
            spy_idx = spy_index.get(signal_date)
            if (
                idx is None
                or spy_idx is None
                or idx < vbb_prior.MOVING_AVERAGE_DAYS
                or spy_idx < 1
            ):
                continue
            close = vbb_prior.ohlcv_helper._value(rows[idx], "Close")
            volume = vbb_prior.ohlcv_helper._value(rows[idx], "Volume")
            if not close or not volume:
                continue
            dollar_volume = close * volume
            if dollar_volume < vbb_prior.MIN_DOLLAR_VOLUME:
                continue
            prior_high = vbb_prior._prior_high(
                rows,
                idx,
                vbb_prior.BREAKOUT_LOOKBACK_DAYS,
            )
            ma50 = vbb_prior._prior_average(
                rows,
                idx,
                vbb_prior.MOVING_AVERAGE_DAYS,
                "Close",
            )
            avg_volume = vbb_prior._prior_average(
                rows,
                idx,
                vbb_prior.VOLUME_LOOKBACK_DAYS,
                "Volume",
            )
            if not prior_high or not ma50 or not avg_volume:
                continue
            volume_ratio = volume / avg_volume if avg_volume else None
            if (
                volume_ratio is None
                or volume_ratio < vbb_prior.MIN_CANDIDATE_VOLUME_RATIO_20
            ):
                continue
            if close <= prior_high or close <= ma50:
                continue
            candidate_ret = vbb_prior._close_return(rows, idx - 1, idx)
            spy_ret = vbb_prior._close_return(spy_rows, spy_idx - 1, spy_idx)
            if candidate_ret is None or spy_ret is None:
                continue
            rs_vs_spy = candidate_ret - spy_ret
            if rs_vs_spy <= 0:
                continue
            raw_breakouts += 1
            ab_entries = core_entries_by_date.get(signal_date, [])
            score = (
                max(rs_vs_spy, 0.0) * 8.0
                + min(max(volume_ratio - 1.0, 0.0), 3.0)
                + max((close / prior_high) - 1.0, 0.0) * 3.0
                + max(float(context.get("volume_breadth_fraction") or 0.0), 0.0)
            )
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "sector": vbb_prior.ohlcv_helper.SECTOR_MAP.get(ticker, "Unknown"),
                    "strategy": "volume_breadth_breakout",
                    "close": allocator_base._round(close, 4),
                    "breakout_above_prior_20d_high_pct": allocator_base._round(
                        (close / prior_high) - 1.0,
                        6,
                    ),
                    "pct_above_50d_ma": allocator_base._round((close / ma50) - 1.0, 6),
                    "candidate_day_return": allocator_base._round(candidate_ret, 6),
                    "candidate_day_spy_return": allocator_base._round(spy_ret, 6),
                    "candidate_day_rs_vs_spy": allocator_base._round(rs_vs_spy, 6),
                    "volume_ratio_20": allocator_base._round(volume_ratio, 6),
                    "dollar_volume": allocator_base._round(dollar_volume, 2),
                    "volume_breadth_score": allocator_base._round(score, 6),
                    "source_score": allocator_base._round(score, 6),
                    "same_day_ab_entry_count": len(ab_entries),
                    "same_day_ab_overlap": bool(ab_entries),
                    "same_ticker_ab_overlap": any(
                        trade.get("ticker") == ticker for trade in ab_entries
                    ),
                    "source_universe": "current_production_universe_ohlcv",
                    "volume_breadth_context": context,
                    "volume_breadth_rule_version": vbb.BREADTH_RULE_VERSION,
                    "trade_enabled": False,
                    "alters_orders": False,
                }
            )

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["volume_breadth_score"]),
            -float(row["candidate_day_rs_vs_spy"]),
            -float(row["volume_ratio_20"]),
            -float(row["dollar_volume"]),
            row["ticker"],
        )
    )
    used_dates: set[str] = set()
    source_rows: list[dict[str, Any]] = []
    for row in candidates:
        if row["date"] in used_dates:
            continue
        used_dates.add(row["date"])
        source_rows.append(
            allocator_base._normalise_source_row(
                {
                    **row,
                    "source_family": "volume_breadth_breakout",
                    "source_score": row.get("volume_breadth_score"),
                    "candidate_score": row.get("volume_breadth_score"),
                    "paper_notional_usd": allocator_base.BASE_NOTIONAL_USD,
                },
                "volume_breadth_breakout",
            )
        )

    return source_rows, {
        "rule_version": vbb.RULE_VERSION,
        "source_rule_version": vbb.BREADTH_RULE_VERSION,
        "raw_candidate_count": raw_breakouts,
        "source_trade_count": len(source_rows),
        "breadth_pass_days": len(breadth_pass_dates),
        "breadth_pass_day_fraction": round(
            len(breadth_pass_dates) / len(dates),
            6,
        )
        if dates
        else None,
        "unique_source_tickers": len({row["ticker"] for row in source_rows}),
        "sample_breadth_context": {
            date: breadth_by_date[date] for date in breadth_pass_dates[:10]
        },
        "daily_entry_slots": 1,
    }


def _build_extended_allocator_trades(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    dates: list[str],
    window_label: str,
    window: dict[str, str],
    core_entries_by_date: dict[str, list[dict[str, Any]]],
    sector_entries: dict[str, dict[str, Any]],
    candidate_universe: dict[str, Any],
    calendar_dates: list[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_trades, source_audit = allocator_base.build_accepted_allocator_source_trades(
        rows_by_ticker=rows_by_ticker,
        dates=dates,
        window_label=window_label,
        window=window,
        core_entries_by_date=core_entries_by_date,
        sector_entries=sector_entries,
        candidate_universe=candidate_universe,
        calendar_dates=calendar_dates,
    )
    vbb_rows, vbb_audit = _build_vbb_source_trades(
        rows_by_ticker=rows_by_ticker,
        dates=dates,
        candidate_universe=candidate_universe,
        core_entries_by_date=core_entries_by_date,
    )
    source_trades.extend(vbb_rows)
    selected, filtered, priority_audit = allocator_base._select_priority_trades(
        source_trades=source_trades,
        trading_dates=dates,
    )

    source_trade_counts = dict(source_audit["source_trade_counts"])
    raw_candidate_counts = dict(source_audit["raw_candidate_counts"])
    source_audits = dict(source_audit["source_audits"])
    source_trade_counts["volume_breadth_breakout"] = len(vbb_rows)
    raw_candidate_counts["volume_breadth_breakout"] = vbb_audit["raw_candidate_count"]
    source_audits["volume_breadth_breakout"] = vbb_audit
    return selected, {
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "source_priority": SOURCE_PRIORITY,
        "selected_by_window": {window_label: len(selected)},
        "selected_source_counts_by_window": {
            window_label: priority_audit["selected_source_counts"]
        },
        "source_trade_counts_by_window": {window_label: source_trade_counts},
        "raw_candidate_counts_by_window": {window_label: raw_candidate_counts},
        "filtered_count_by_window": {window_label: len(filtered)},
        "source_audits_by_window": {window_label: source_audits},
        "priority_audit_by_window": {window_label: priority_audit},
        "total_selected": len(selected),
    }


ORIGINAL_BINDING_GATE4 = allocator_base._binding_gate4
ORIGINAL_BUILD_PAYLOAD = allocator_base.build_payload


def _binding_gate4(*args: Any, **kwargs: Any) -> dict[str, Any]:
    gate = ORIGINAL_BINDING_GATE4(*args, **kwargs)
    gate["decision"] = (
        "positive_replay_lead_not_promoted_vbb_allocator_source_extension"
        if gate["passed"]
        else "rejected_vbb_allocator_source_extension"
    )
    return gate


def _prepare_base() -> None:
    allocator_base.__file__ = str(Path(__file__))
    allocator_base.EXPERIMENT_ID = EXPERIMENT_ID
    allocator_base.STEM = STEM
    allocator_base.TRIAL_FAMILY = TRIAL_FAMILY
    allocator_base.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    allocator_base.CHANGED_VARIABLE = CHANGED_VARIABLE
    allocator_base.RULE_VERSION = RULE_VERSION
    allocator_base.SOURCE_RULE_VERSION = SOURCE_RULE_VERSION
    allocator_base.OWNER = OWNER
    allocator_base.OUT_DIR = OUT_DIR
    allocator_base.OUT_JSON = OUT_JSON
    allocator_base.LOG_JSON = LOG_JSON
    allocator_base.TICKET_JSON = TICKET_JSON
    allocator_base.CARD_MD = CARD_MD
    allocator_base.MANIFEST_JSON = MANIFEST_JSON
    allocator_base.EXPERIMENT_LOG = EXPERIMENT_LOG
    allocator_base.REGISTRY_JSON = REGISTRY_JSON
    allocator_base.SOURCE_PRIORITY = SOURCE_PRIORITY
    allocator_base.PREDICTION = PREDICTION
    allocator_base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    allocator_base.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    allocator_base.EXECUTION_ENVELOPE = EXECUTION_ENVELOPE
    allocator_base._build_extended_allocator_trades = _build_extended_allocator_trades
    allocator_base._binding_gate4 = _binding_gate4


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    accepted = bool(payload["gate4"]["passed"])
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": "positive_replay_lead_not_promoted" if accepted else "rejected",
            "decision": payload["gate4"]["decision"],
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "default_off_paper_candidate_pool_replay_scout",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": (
                "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
            ),
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "accepted_vbb_source_family_added_to_allocator_replay",
            "nearby_prior_experiments": [
                "exp-20260526-014",
                "exp-20260610-005",
                "exp-20260610-006",
                "exp-20260610-009",
            ],
            "prior_trial_count": 3,
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["parameters"] = {
        **payload.get("parameters", {}),
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "source_priority": SOURCE_PRIORITY,
        "accepted_vbb_comparator": ACCEPTED_VBB_COMPARATOR,
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"]["execution_model"] = (
        "Replay reconstructs accepted source-priority rows plus accepted VBB "
        "top-1/day source rows from the accepted VBB replay semantics, then "
        "selects one paper trade per signal date by fixed source priority and "
        "applies the accepted allocator 12-trading-day same-ticker cooldown."
    )
    payload["gate2"]["runtime_fields"] = [
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "shared VBB candidate fields including signal_date/ticker/volume_breadth_score",
        "accepted allocator source rows with signal_date/ticker/source_family",
    ]
    for label, row in payload["window_rows"].items():
        source_counts = row.get("source_trade_counts") or {}
        selected_counts = row.get("selected_source_counts") or {}
        row["volume_breadth_source_trade_count"] = source_counts.get(
            "volume_breadth_breakout",
            0,
        )
        row["volume_breadth_selected_count"] = selected_counts.get(
            "volume_breadth_breakout",
            0,
        )
    payload["accepted_comparators"] = {
        "accepted_allocator": ACCEPTED_ALLOCATOR_COMPARATOR,
        "accepted_vbb_standalone": ACCEPTED_VBB_COMPARATOR,
        "included_source_priority": SOURCE_PRIORITY,
    }
    payload["interpretation"] = (
        "The VBB source-family extension beat the accepted allocator comparator "
        "as a replay-only lead; shared allocator wiring and daily parity are "
        "required before use."
        if accepted
        else (
            "The VBB source-family extension failed to beat the accepted "
            "allocator comparator."
        )
    )
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The VBB source added enough broad-participation breakout rows to "
            "beat accepted allocator displacement costs across the canonical "
            "windows. It remains replay-only because shared allocator wiring "
            "was not changed."
            if accepted
            else (
                "The VBB source likely overlapped with or displaced stronger "
                "accepted allocator rows; broad volume-breadth breakout strength "
                "did not add enough incremental replacement value under fixed "
                "top-1/day source priority."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by changing VBB thresholds, source rank, allocator "
            "top-N, notional, hold days, or cooldown on the same frozen windows."
        ),
        "new_evidence_required": (
            "A retry needs closed forward allocator displacement rows, a truly "
            "new source interaction, or shared-daily replacement-value evidence."
        ),
    }
    payload["next_retry_requires"] = [
        "closed forward allocator displacement rows",
        "shared allocator daily parity if positive",
        "no frozen-window VBB threshold or rank retune",
    ]
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(EXPERIMENT_LOG),
        _repo_rel(REGISTRY_JSON),
    ]
    return payload


def build_payload() -> dict[str, Any]:
    _prepare_base()
    return _postprocess_payload(ORIGINAL_BUILD_PAYLOAD())


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
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": (
            "data/experiments/exp-20260610-005/"
            "exp_20260610_005_accepted_helper_source_priority_allocator.json"
        ),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate[
            "expected_value_score_delta_pct"
        ],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
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
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][
                    label
                ]["total_pnl"],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
                "volume_breadth_source_trade_count": payload["window_rows"][label].get(
                    "volume_breadth_source_trade_count",
                    0,
                ),
                "volume_breadth_selected_count": payload["window_rows"][label].get(
                    "volume_breadth_selected_count",
                    0,
                ),
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


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Accepted dEV | Before PnL | After PnL | dPnL | Accepted dPnL | DD d | Trades | VBB selected |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    comparator = ACCEPTED_ALLOCATOR_COMPARATOR
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        row = payload["window_rows"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | {cev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | ${cpnl:+,.2f} | {dd:+.4f} | {trades} | {vbb_selected} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                cev=comparator["window_deltas"][label]["ev"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                cpnl=comparator["window_deltas"][label]["pnl"],
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                vbb_selected=row.get("volume_breadth_selected_count", 0),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} VBB Allocator Source Extension",
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
            "- Aggregate EV delta: `{:+.4f}` vs accepted allocator `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"],
                comparator["aggregate_ev_delta"],
            ),
            "- Aggregate PnL delta: `${:+,.2f}` vs accepted allocator `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"],
                comparator["aggregate_pnl_delta"],
            ),
            "- Target trades: `{}`".format(
                payload["target_trade_summary"]["total_trade_count"]
            ),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "",
            "## Production Impact",
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _load_json(TICKET_JSON, {})
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "decision": payload["decision"],
            "summary": payload["interpretation"],
            "result": {
                "decision": payload["decision"],
                "full_stack_verdict": payload["full_stack_verdict"],
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "aggregate_expected_value_delta": payload["expected_value_score_delta"],
                "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
                "accepted": payload["gate4"]["passed"],
                "calibration": payload["calibration"],
                "production_impact": PRODUCTION_IMPACT,
            },
        }
    )
    scope = set(ticket.get("allowed_write_scope") or [])
    scope.update(payload["related_files"])
    ticket["allowed_write_scope"] = sorted(scope)
    framework._write_json(TICKET_JSON, ticket)


def _update_registry(payload: dict[str, Any]) -> None:
    result = {
        "decision": payload["decision"],
        "full_stack_verdict": payload["full_stack_verdict"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "accepted": payload["gate4"]["passed"],
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
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "completed_at": payload["timestamp"],
    }
    allocator_base.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )


def _write_manifest(payload: dict[str, Any]) -> None:
    paths = [
        Path(__file__),
        REGISTRY_JSON,
        EXPERIMENT_LOG,
        OUT_JSON,
        LOG_JSON,
        TICKET_JSON,
        CARD_MD,
        MANIFEST_JSON,
    ]
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [_repo_rel(path) for path in paths],
        "file_hashes": {
            _repo_rel(path): framework._sha256(path)
            for path in paths
            if path.exists()
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, log_record)
    framework._write_text(CARD_MD, _build_card(payload))
    framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    _update_ticket(payload)
    _update_registry(payload)
    _write_manifest(payload)


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            framework._safe(_build_log_record(payload)),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
