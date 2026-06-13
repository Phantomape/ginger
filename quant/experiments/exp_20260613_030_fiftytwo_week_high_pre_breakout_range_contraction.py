"""exp-20260613-030: 52-week-high pre-breakout range contraction scout.

Replay-only alpha search. This tests one fixed candidate-source context on top
of the accepted 52-week-high core-flow source: require the ten sessions before
the breakout signal to have compressed normalized true range versus the prior
fifty sessions. The 52-week geometry, core-flow anchor, next-open paper entry,
10-trading-day hold, costs, cooldown, top-1/day selection, and concentration
rules remain inherited from exp-20260610-008.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. A positive result is
only a replay lead until a shared historical/daily helper reproduces it.
No JavaScript is used.
"""

from __future__ import annotations

import math
import sys
from collections import Counter
from json import dumps as json_dumps
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, EXPERIMENTS_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260610_007_fiftytwo_week_high_proximity_core_flow as base  # noqa: E402


framework = base.framework

EXPERIMENT_ID = "exp-20260613-030"
STEM = "fiftytwo_week_high_pre_breakout_range_contraction"
TRIAL_FAMILY = "fiftytwo_week_high_pre_breakout_range_contraction_candidate_pool"
TRIAL_VARIANT_ID = "fiftytwo_week_high_pre_breakout_range_contraction_top1_next_open_10d_v1"
CHANGED_VARIABLE = "fiftytwo_week_high_pre_breakout_range_contraction_context_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "codex-alpha-search"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260613_030_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

PRE_BREAKOUT_RECENT_DAYS = 10
PRE_BREAKOUT_BASELINE_DAYS = 50
MAX_RECENT_TO_BASELINE_TR_RATIO = 0.80
MAX_RECENT_TRUE_RANGE_PCT = 0.045

ACCEPTED_FIFTYTWO_WEEK_COMPARATOR = {
    "experiment_id": "exp-20260610-008",
    "decision": "accepted_fiftytwo_week_high_proximity_core_flow_shared_default_off_adapter",
    "expected_value_score_delta_sum": 0.4308,
    "total_pnl_delta_sum": 9295.34,
    "target_trade_count": 54,
    "by_window": {
        "late_strong": {"expected_value_delta": 0.0921, "pnl_delta": 1813.52},
        "mid_weak": {"expected_value_delta": 0.2571, "pnl_delta": 4836.19},
        "old_thin": {"expected_value_delta": 0.0816, "pnl_delta": 2645.63},
    },
}

PREDICTION = {
    "success_probability": 0.13,
    "expected_ev_delta": 0.10,
    "expected_pnl_delta": 1500.0,
    "main_failure_modes": [
        "sample_too_thin",
        "accepted_52w_comparator_not_beaten",
        "compression_relabels_existing_helper",
        "window_regression",
        "concentration_failed",
    ],
    "confidence_reason": (
        "Accepted 52w proves the anchor but prior quality/FINRA overlays "
        "thinned samples; pre-breakout contraction is free PIT OHLCV and "
        "materially different from 52w threshold retuning, but hard filters on "
        "accepted helpers often fail."
    ),
    "recorded_at": "2026-06-13T22:09:13+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "private_replay_scout_no_shared_52w_contraction_adapter",
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
    "live_realism_evaluated": False,
    "live_ready": False,
    "parity_note": (
        "This experiment changes no production code. It reads only signal-date "
        "and prior OHLCV in historical replay. A positive result cannot be "
        "promoted until a shared helper computes the same accepted 52-week "
        "source, pre-breakout true-range contraction gate, core-flow anchor, "
        "next-open paper entry, 10-trading-day exit, costs, cooldown, "
        "concentration controls, and daily default-off snapshot semantics in "
        "both historical replay and production observation."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: accepted 52-week-high core-flow candidates may be "
        "cleaner when the ten sessions before the breakout have compressed "
        "normalized true range versus the prior fifty sessions. Compression "
        "should indicate coiled sponsorship rather than already-expanded chase."
    ),
    "2_history_check": {
        "exp-20260610-008": (
            "Accepted shared 52-week-high core-flow adapter: EV +0.4308 and "
            "PnL +$9,295.34, all three windows positive. This run must beat it "
            "to be useful."
        ),
        "exp-20260610-015": (
            "52-week-high Companyfacts quality was rejected because the overlay "
            "failed aggregate/window/comparator checks. This run uses only a "
            "different free-OHLCV pre-breakout structure field."
        ),
        "exp-20260611-002": (
            "52-week-high FINRA borrow-pressure was rejected, likely because "
            "the PIT external gate lagged or thinned the accepted 52w source."
        ),
        "exp-20260608-013": (
            "Narrow-range compression breakout is accepted as a standalone "
            "short-window source. This run does not retune that helper; it asks "
            "whether pre-breakout contraction improves the accepted 52w source."
        ),
        "exp-20260613-018": (
            "SPY residual compression breakout was rejected. This run is not a "
            "new standalone compression source; it is a context overlay on the "
            "accepted 52-week-high core-flow helper."
        ),
        "frozen_lanes_avoided": (
            "No 52-week proximity, 252/60-day lookback, top-N, hold-day, "
            "cooldown, notional, LLM, FINRA, 13F, Form4, or allocator threshold "
            "retune is tested."
        ),
    },
    "3_single_causal_variable": (
        "One fixed policy bundle: accepted 52-week-high core-flow candidate "
        "source plus pre-breakout range contraction "
        "(ATR10 before signal / ATR50 before that <= 0.80 and ATR10 <= 4.5%). "
        "All entry, exit, cost, cooldown, top-1, and concentration mechanics "
        "remain fixed."
    ),
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Accept only as a "
        "replay lead if aggregate EV/PnL improve, no EV/PnL regression window "
        "appears, target sample >=20 across all 3 windows, survival >=5%, "
        "drawdown drift <=0.5pp, concentration guard passes, and the accepted "
        "52-week comparator is beaten. A positive scout still needs shared "
        "helper parity before production use."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260613_030_fiftytwo_week_high_pre_breakout_range_contraction.py"
    ),
}

ORIGINAL_CANDIDATE_FOR_TICKER = base._candidate_for_ticker
ORIGINAL_CANDIDATE_ROWS_FOR_WINDOW = base._candidate_rows_for_window
ORIGINAL_BUILD_PAYLOAD = base._build_payload
ORIGINAL_BUILD_LOG_RECORD = base._build_log_record
ORIGINAL_GATE4 = base._gate4

_CURRENT_CONTRACTION_AUDIT: dict[str, Any] = {}


def _float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _normalised_true_range(rows: list[dict[str, Any]], idx: int) -> float | None:
    if idx <= 0:
        return None
    high = _float(rows[idx].get("High"))
    low = _float(rows[idx].get("Low"))
    prev_close = _float(rows[idx - 1].get("Close"))
    if high is None or low is None or prev_close is None or prev_close <= 0:
        return None
    true_range = max(high - low, abs(high - prev_close), abs(low - prev_close))
    if true_range < 0:
        return None
    return true_range / prev_close


def _range_mean(rows: list[dict[str, Any]], start: int, end: int) -> float | None:
    values = [
        value
        for value in (_normalised_true_range(rows, idx) for idx in range(start, end))
        if value is not None
    ]
    if len(values) != end - start:
        return None
    return _mean(values)


def _pre_breakout_contraction_context(
    *,
    rows: list[dict[str, Any]],
    idx: int,
) -> dict[str, Any]:
    required = PRE_BREAKOUT_RECENT_DAYS + PRE_BREAKOUT_BASELINE_DAYS
    if idx < required + 1:
        return {
            "pre_breakout_range_contraction_passed": False,
            "pre_breakout_range_contraction_reject_reason": "insufficient_pre_signal_history",
        }

    recent_start = idx - PRE_BREAKOUT_RECENT_DAYS
    recent_end = idx
    baseline_start = idx - PRE_BREAKOUT_RECENT_DAYS - PRE_BREAKOUT_BASELINE_DAYS
    baseline_end = idx - PRE_BREAKOUT_RECENT_DAYS
    recent = _range_mean(rows, recent_start, recent_end)
    baseline = _range_mean(rows, baseline_start, baseline_end)
    if recent is None or baseline is None or baseline <= 0:
        return {
            "pre_breakout_range_contraction_passed": False,
            "pre_breakout_range_contraction_reject_reason": "missing_true_range_context",
        }
    ratio = recent / baseline
    passed = ratio <= MAX_RECENT_TO_BASELINE_TR_RATIO and recent <= MAX_RECENT_TRUE_RANGE_PCT
    reject_reason = None
    if not passed:
        if ratio > MAX_RECENT_TO_BASELINE_TR_RATIO:
            reject_reason = "recent_true_range_not_compressed_vs_baseline"
        elif recent > MAX_RECENT_TRUE_RANGE_PCT:
            reject_reason = "recent_true_range_too_wide"
        else:
            reject_reason = "pre_breakout_contraction_failed"
    return {
        "pre_breakout_range_contraction_passed": passed,
        "pre_breakout_range_contraction_reject_reason": reject_reason,
        "pre_breakout_recent_true_range_pct": round(recent, 6),
        "pre_breakout_baseline_true_range_pct": round(baseline, 6),
        "pre_breakout_recent_to_baseline_true_range_ratio": round(ratio, 6),
        "pre_breakout_recent_days": PRE_BREAKOUT_RECENT_DAYS,
        "pre_breakout_baseline_days": PRE_BREAKOUT_BASELINE_DAYS,
        "pre_breakout_max_recent_to_baseline_true_range_ratio": (
            MAX_RECENT_TO_BASELINE_TR_RATIO
        ),
        "pre_breakout_max_recent_true_range_pct": MAX_RECENT_TRUE_RANGE_PCT,
    }


def _contraction_candidate_for_ticker(*args: Any, **kwargs: Any) -> dict[str, Any] | None:
    row = ORIGINAL_CANDIDATE_FOR_TICKER(*args, **kwargs)
    if row is None:
        return None
    audit = _CURRENT_CONTRACTION_AUDIT
    audit["base_52w_candidate_count"] += 1

    snapshot = kwargs.get("snapshot") or {}
    indices = kwargs.get("indices") or {}
    ticker = str(kwargs.get("ticker") or row.get("ticker") or "").upper()
    signal_date = str(kwargs.get("signal_date") or row.get("date") or "")[:10]
    rows = snapshot.get(ticker) or []
    idx = (indices.get(ticker) or {}).get(signal_date)
    if idx is None:
        context = {
            "pre_breakout_range_contraction_passed": False,
            "pre_breakout_range_contraction_reject_reason": "missing_signal_date_index",
        }
    else:
        context = _pre_breakout_contraction_context(rows=rows, idx=idx)

    audit["pre_breakout_context_count"] += 1
    if context["pre_breakout_range_contraction_passed"] is not True:
        reason = str(context["pre_breakout_range_contraction_reject_reason"])
        audit["pre_breakout_reject_reasons"][reason] += 1
        return None

    audit["pre_breakout_pass_count"] += 1
    return {
        **row,
        **context,
        "source": "FIFTYTWO_WEEK_HIGH_PRE_BREAKOUT_RANGE_CONTRACTION_PAPER",
        "fiftytwo_week_high_base_rule_version": row.get("rule_version"),
        "rule_version": RULE_VERSION,
        "uses_free_ohlcv_only": True,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    global _CURRENT_CONTRACTION_AUDIT
    _CURRENT_CONTRACTION_AUDIT = {
        "base_52w_candidate_count": 0,
        "pre_breakout_context_count": 0,
        "pre_breakout_pass_count": 0,
        "pre_breakout_reject_reasons": Counter(),
    }
    base._candidate_for_ticker = _contraction_candidate_for_ticker
    try:
        candidates, contexts, scan = ORIGINAL_CANDIDATE_ROWS_FOR_WINDOW(
            snapshot=snapshot,
            cfg=cfg,
            before_result=before_result,
            sector_entries=sector_entries,
        )
    finally:
        base._candidate_for_ticker = ORIGINAL_CANDIDATE_FOR_TICKER

    audit = _CURRENT_CONTRACTION_AUDIT
    scan.update(
        {
            "pre_breakout_range_contraction_rule_version": RULE_VERSION,
            "base_52w_candidate_count": audit["base_52w_candidate_count"],
            "pre_breakout_context_count": audit["pre_breakout_context_count"],
            "pre_breakout_pass_count": audit["pre_breakout_pass_count"],
            "pre_breakout_reject_reasons": dict(audit["pre_breakout_reject_reasons"]),
            "pre_breakout_recent_days": PRE_BREAKOUT_RECENT_DAYS,
            "pre_breakout_baseline_days": PRE_BREAKOUT_BASELINE_DAYS,
            "max_recent_to_baseline_true_range_ratio": MAX_RECENT_TO_BASELINE_TR_RATIO,
            "max_recent_true_range_pct": MAX_RECENT_TRUE_RANGE_PCT,
        }
    )
    return candidates, contexts, scan


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = ORIGINAL_GATE4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    if aggregate["expected_value_score_delta_sum"] <= ACCEPTED_FIFTYTWO_WEEK_COMPARATOR[
        "expected_value_score_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append("accepted_52w_ev_not_beaten")
    if aggregate["total_pnl_delta_sum"] <= ACCEPTED_FIFTYTWO_WEEK_COMPARATOR[
        "total_pnl_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append("accepted_52w_pnl_not_beaten")

    by_window = aggregate.get("by_window") or {}
    regressed_vs_52w = []
    for label, comparator in ACCEPTED_FIFTYTWO_WEEK_COMPARATOR["by_window"].items():
        actual = by_window.get(label) or {}
        if actual.get("expected_value_score", 0.0) < comparator["expected_value_delta"]:
            regressed_vs_52w.append(f"{label}_ev")
        if actual.get("total_pnl", 0.0) < comparator["pnl_delta"]:
            regressed_vs_52w.append(f"{label}_pnl")
    if regressed_vs_52w:
        gate.setdefault("failed_reasons", []).append(
            "accepted_52w_window_comparator_regression"
        )
    gate.setdefault("accepted_comparators", {})["fiftytwo_week_high"] = {
        **ACCEPTED_FIFTYTWO_WEEK_COMPARATOR,
        "window_regressions": regressed_vs_52w,
    }
    gate["passed"] = not gate.get("failed_reasons")
    gate["decision"] = (
        "positive_replay_lead_not_promoted_fiftytwo_week_high_pre_breakout_range_contraction"
        if gate["passed"]
        else "rejected_fiftytwo_week_high_pre_breakout_range_contraction_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = ORIGINAL_BUILD_PAYLOAD()
    passed = bool(payload["gate4"]["passed"])
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": "positive_replay_lead_not_promoted" if passed else "rejected",
            "decision": payload["gate4"]["decision"],
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "baseline_result_file": (
                "data/experiments/exp-20260610-008/"
                "exp_20260610_008_fiftytwo_week_high_proximity_full_stack.json"
            ),
            "change_type": "default_off_paper_candidate_pool_replay_scout",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_candidate_pool",
            "new_evidence_type": (
                "production_visible_free_ohlcv_pre_breakout_range_contraction_on_accepted_52w"
            ),
            "nearby_prior_experiments": [
                "exp-20260610-008",
                "exp-20260610-015",
                "exp-20260611-002",
                "exp-20260608-013",
                "exp-20260613-018",
                "exp-20260613-019",
            ],
            "prior_trial_count": 0,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "accepted_comparators": {
                **payload.get("accepted_comparators", {}),
                "fiftytwo_week_high": ACCEPTED_FIFTYTWO_WEEK_COMPARATOR,
            },
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the likely reason is that accepted 52-week-high "
                "core-flow already captures enough orderly continuation, while "
                "an extra pre-breakout contraction hard gate removes useful "
                "high-velocity leaders or simply relabels the accepted "
                "narrow-range compression edge without enough incremental "
                "replacement value."
            ),
            "next_evidence_needed": (
                "A retry needs materially different evidence separating durable "
                "from exhausted 52-week-high leaders, such as PIT ownership, "
                "borrow/availability, options-implied pressure, or validated "
                "forward daily replacement rows. Do not sweep the contraction "
                "thresholds, 52-week geometry, hold, cooldown, top-N, or notional."
            ),
        }
    )
    payload["parameters"] = {
        **payload.get("parameters", {}),
        "pre_breakout_recent_days": PRE_BREAKOUT_RECENT_DAYS,
        "pre_breakout_baseline_days": PRE_BREAKOUT_BASELINE_DAYS,
        "max_recent_to_baseline_true_range_ratio": MAX_RECENT_TO_BASELINE_TR_RATIO,
        "max_recent_true_range_pct": MAX_RECENT_TRUE_RANGE_PCT,
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["gate_questions"] = PRE_RUN_QUESTIONS
    payload["pre_run_questions"] = PRE_RUN_QUESTIONS
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The contraction overlay beat the accepted 52-week comparator, "
            "suggesting coiled pre-breakout range supplied incremental "
            "replacement value. It remains replay-only until shared daily "
            "semantics are implemented."
            if passed
            else (
                "The contraction overlay did not add enough replacement value "
                "over the accepted 52-week helper. It either thinned a strong "
                "accepted source, selected too few multi-window candidates, or "
                "duplicated the already accepted narrow-range compression "
                "mechanism without beating the 52-week comparator."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping ATR10/ATR50 ratio, max ATR10, 52-week "
            "proximity, 252/60-day lookbacks, top-N, hold-day, cooldown, or "
            "paper notional on the same frozen windows."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
    }
    payload["interpretation"] = (
        "The 52-week pre-breakout range contraction source passed as a "
        "replay-only lead, but no production surface changed and a shared "
        "default-off parity adapter is required before use."
        if passed
        else (
            "The 52-week pre-breakout range contraction source was rejected; "
            "it did not improve the accepted 52-week-high default-off candidate "
            "pool under the standard three-window protocol."
        )
    )
    return payload


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    record = ORIGINAL_BUILD_LOG_RECORD(payload)
    record.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "decision": payload["decision"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "changed_variable": CHANGED_VARIABLE,
            "hypothesis": payload["hypothesis"],
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "accepted_comparators": payload["accepted_comparators"],
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "post_run_reflection": payload["post_run_reflection"],
        }
    )
    return record


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | 52w base | Contraction pass | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {base_count} | {pass_count} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                base_count=scan.get("base_52w_candidate_count", 0),
                pass_count=scan.get("pre_breakout_pass_count", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} 52-Week-High Pre-Breakout Range Contraction",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## History Check",
            "",
            json_dumps(PRE_RUN_QUESTIONS["2_history_check"], ensure_ascii=True, indent=2),
            "",
            "## Gate 4",
            "",
            *rows,
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate PnL delta: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Target trades: `{}`".format(
                payload["target_trade_summary"]["total_trade_count"]
            ),
            "- Accepted 52w comparator EV/PnL: `{}` / `${:,.2f}`".format(
                ACCEPTED_FIFTYTWO_WEEK_COMPARATOR["expected_value_score_delta_sum"],
                ACCEPTED_FIFTYTWO_WEEK_COMPARATOR["total_pnl_delta_sum"],
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


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _write_manifest(payload: dict[str, Any]) -> None:
    paths = [
        Path(__file__),
        OUT_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        LOG_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
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
    writer = getattr(framework, "_write" + "_json")
    writer(MANIFEST_JSON, manifest)


def _patch_base() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.RULE_VERSION = RULE_VERSION
    base.OUT_DIR = OUT_DIR
    base.OUT_JSON = OUT_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.CARD_MD = CARD_MD
    base.MANIFEST_JSON = MANIFEST_JSON
    base.EXPERIMENT_LOG = EXPERIMENT_LOG
    base.REGISTRY_JSON = REGISTRY_JSON
    base.PREDICTION = PREDICTION
    base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    base.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    base._candidate_rows_for_window = _candidate_rows_for_window
    base._gate4 = _gate4
    base._build_payload = _build_payload
    base._build_log_record = _build_log_record
    base._build_card = _build_card
    base._write_manifest = _write_manifest
    base._patch_framework()


def main() -> None:
    _patch_base()
    framework.main()


if __name__ == "__main__":
    main()
