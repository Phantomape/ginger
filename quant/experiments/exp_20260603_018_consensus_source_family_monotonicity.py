"""exp-20260603-018: consensus source-family count monotonicity.

Replay-only alpha search. This tests whether independent source-family count
inside the already accepted default-off consensus sleeve is durable ranking
evidence, or merely a useful admission guard.

No production adapters, live orders, watchlists, ranking, sizing, exits,
thresholds, source sets, or hold periods are changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
for path in (REPO_ROOT, QUANT_DIR, EXPERIMENT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260603_014_accepted_consensus_independent_source_family as consensus


EXPERIMENT_ID = "exp-20260603-018"
STEM = "consensus_source_family_monotonicity"
TRIAL_FAMILY = "accepted_free_data_cross_source_consensus_source_family_count_monotonicity"
CHANGED_VARIABLE = "independent_source_family_count_monotonicity_bucket_v1"
RULE_VERSION = "source_family_count_monotonicity_bucket_v1"

OUT_DIR = Path("data/experiments") / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260603_018_{STEM}.json"
LOG_JSON = Path("experiments/logs") / f"{EXPERIMENT_ID}.json"
TICKET_JSON = Path("experiments/tickets") / f"{EXPERIMENT_ID}.json"
CARD_MD = Path("experiments/cards") / f"{EXPERIMENT_ID}.md"
EXPERIMENT_LOG = Path("docs/experiment_log.jsonl")
REGISTRY_JSON = Path("docs/experiment_registry.json")
CURRENT_ACCEPTED_CONSENSUS_ARTIFACT = Path(
    "data/experiments/exp-20260603-014/accepted_consensus_independent_source_family.json"
)

MIN_AGGREGATE_HIGH_BUCKET_TRADES = 10
MIN_PER_WINDOW_HIGH_BUCKET_TRADES = 3
MIN_PER_WINDOW_LOW_BUCKET_TRADES = 3

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_observational_validation",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "parity_test_added": False,
    "production_watchlist_changed": False,
    "production_orders_changed": False,
    "parity_note": (
        "This experiment changes no production code. It validates persisted "
        "source-family-count evidence inside the already accepted default-off "
        "consensus sleeve and cannot alter daily orders, reports, candidate "
        "queues, ranking, sizing, exits, or shared adapters."
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _round(value: float, digits: int = 6) -> float:
    if not math.isfinite(value):
        return 0.0
    return round(value, digits)


def _configure_consensus_module() -> None:
    consensus.EXPERIMENT_ID = EXPERIMENT_ID
    consensus.STEM = STEM
    consensus.TRIAL_FAMILY = TRIAL_FAMILY
    consensus.CHANGED_VARIABLE = CHANGED_VARIABLE
    consensus.RULE_VERSION = RULE_VERSION
    consensus.OUT_DIR = OUT_DIR
    consensus.OUT_JSON = OUT_JSON
    consensus.LOG_JSON = LOG_JSON
    consensus.TICKET_JSON = TICKET_JSON
    consensus.CARD_MD = CARD_MD
    consensus.EXPERIMENT_LOG = EXPERIMENT_LOG
    consensus.REGISTRY_JSON = REGISTRY_JSON
    consensus.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    consensus._configure_prior_module()
    consensus.prior._configure_base_module()


def _preflight_payload() -> dict[str, Any]:
    return {
        "alpha_hypothesis": (
            "Within the already accepted independent-source consensus sleeve, trades with three or "
            "more independent source families should outperform two-family trades if source-family "
            "count is durable cross-sectional ranking evidence rather than just an admission guard."
        ),
        "category": "ranking",
        "playbook_alignment": (
            "This extracts evidence density from the accepted default-off consensus sleeve without "
            "adding a source, threshold, allocator, state machine, or live behavior."
        ),
        "nearby_prior_experiments": [
            "exp-20260531-030",
            "exp-20260601-001",
            "exp-20260601-028",
            "exp-20260603-014",
            "exp-20260603-015",
            "exp-20260603-016",
        ],
        "prior_difference": (
            "Earlier consensus experiments used independent source-family count for admission or "
            "source-set expansion. This run does not change the sleeve; it tests whether the "
            "persisted family-count field is monotonic enough to justify future ranking use."
        ),
        "single_causal_variable": CHANGED_VARIABLE,
        "acceptance_criteria": {
            "canonical_windows": list(consensus.prior.base.WINDOWS.keys()),
            "three_window_before_after": "must exactly replay current accepted consensus metrics",
            "monotonic_bucket_order": "3plus-family bucket must beat 2-family bucket on aggregate avg/median PnL",
            "aggregate_high_bucket_min_trades": MIN_AGGREGATE_HIGH_BUCKET_TRADES,
            "per_window_high_bucket_min_trades": MIN_PER_WINDOW_HIGH_BUCKET_TRADES,
            "per_window_low_bucket_min_trades": MIN_PER_WINDOW_LOW_BUCKET_TRADES,
            "production_parity": "no production path changed; retained evidence would still need shared adapter work",
        },
        "reproducibility": (
            "The runner persists the canonical before/after replay, selected target trades, bucket "
            "statistics, monotonic gates, current accepted identity check, and rejection rationale."
        ),
    }


def _bucket_for_trade(trade: dict[str, Any]) -> str:
    count = int(trade.get("source_family_count") or len(trade.get("source_families") or []))
    if count >= 3:
        return "family_count_3plus"
    return "family_count_2"


def _trade_return(trade: dict[str, Any]) -> float:
    value = trade.get("pnl_pct_net")
    if value is not None:
        return float(value)
    notional = float(trade.get("paper_notional_usd") or 0.0)
    if notional <= 0:
        return 0.0
    return float(trade.get("pnl") or 0.0) / notional


def _summarize_trades(trades: list[dict[str, Any]]) -> dict[str, Any]:
    pnls = [float(trade.get("pnl") or 0.0) for trade in trades]
    returns = [_trade_return(trade) for trade in trades]
    positive = [pnl for pnl in pnls if pnl > 0]
    return {
        "trade_count": len(trades),
        "total_pnl": _round(sum(pnls), 2),
        "avg_pnl": _round(sum(pnls) / len(pnls), 2) if pnls else 0.0,
        "median_pnl": _round(median(pnls), 2) if pnls else 0.0,
        "avg_return": _round(sum(returns) / len(returns), 6) if returns else 0.0,
        "median_return": _round(median(returns), 6) if returns else 0.0,
        "win_rate": _round(len(positive) / len(pnls), 6) if pnls else 0.0,
        "tickers": sorted({str(trade.get("ticker") or "") for trade in trades if trade.get("ticker")}),
    }


def _bucket_summaries(
    target_trades_by_window: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    by_window: dict[str, dict[str, Any]] = {}
    aggregate_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    exact_count_rows: dict[int, list[dict[str, Any]]] = defaultdict(list)

    for label, trades in target_trades_by_window.items():
        window_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for trade in trades:
            bucket = _bucket_for_trade(trade)
            count = int(trade.get("source_family_count") or len(trade.get("source_families") or []))
            window_rows[bucket].append(trade)
            aggregate_rows[bucket].append(trade)
            exact_count_rows[count].append(trade)
        by_window[label] = {
            bucket: _summarize_trades(rows) for bucket, rows in sorted(window_rows.items())
        }
        for required in ("family_count_2", "family_count_3plus"):
            by_window[label].setdefault(required, _summarize_trades([]))

    aggregate = {
        bucket: _summarize_trades(rows) for bucket, rows in sorted(aggregate_rows.items())
    }
    for required in ("family_count_2", "family_count_3plus"):
        aggregate.setdefault(required, _summarize_trades([]))

    return {
        "bucket_definition": {
            "family_count_2": "exactly two independent accepted source families",
            "family_count_3plus": "three or more independent accepted source families",
        },
        "aggregate": aggregate,
        "by_window": by_window,
        "exact_source_family_count": {
            str(count): _summarize_trades(rows) for count, rows in sorted(exact_count_rows.items())
        },
    }


def _monotonic_gate(bucket_summary: dict[str, Any]) -> dict[str, Any]:
    aggregate = bucket_summary["aggregate"]
    low = aggregate["family_count_2"]
    high = aggregate["family_count_3plus"]

    aggregate_sample_passed = (
        int(low["trade_count"]) >= MIN_AGGREGATE_HIGH_BUCKET_TRADES
        and int(high["trade_count"]) >= MIN_AGGREGATE_HIGH_BUCKET_TRADES
    )
    aggregate_avg_monotonic = float(high["avg_pnl"]) > float(low["avg_pnl"])
    aggregate_median_monotonic = float(high["median_pnl"]) > float(low["median_pnl"])
    aggregate_return_monotonic = float(high["avg_return"]) > float(low["avg_return"])

    per_window_rows: list[dict[str, Any]] = []
    per_window_sample_passed = True
    per_window_avg_monotonic = True
    per_window_median_monotonic = True
    for label in consensus.prior.base.WINDOWS:
        window = bucket_summary["by_window"][label]
        window_low = window["family_count_2"]
        window_high = window["family_count_3plus"]
        sample_passed = (
            int(window_low["trade_count"]) >= MIN_PER_WINDOW_LOW_BUCKET_TRADES
            and int(window_high["trade_count"]) >= MIN_PER_WINDOW_HIGH_BUCKET_TRADES
        )
        avg_monotonic = float(window_high["avg_pnl"]) > float(window_low["avg_pnl"])
        median_monotonic = float(window_high["median_pnl"]) > float(window_low["median_pnl"])
        per_window_sample_passed = per_window_sample_passed and sample_passed
        per_window_avg_monotonic = per_window_avg_monotonic and avg_monotonic
        per_window_median_monotonic = per_window_median_monotonic and median_monotonic
        per_window_rows.append(
            {
                "label": label,
                "sample_passed": sample_passed,
                "avg_pnl_monotonic": avg_monotonic,
                "median_pnl_monotonic": median_monotonic,
                "family_count_2_trade_count": window_low["trade_count"],
                "family_count_3plus_trade_count": window_high["trade_count"],
                "family_count_2_avg_pnl": window_low["avg_pnl"],
                "family_count_3plus_avg_pnl": window_high["avg_pnl"],
                "family_count_2_median_pnl": window_low["median_pnl"],
                "family_count_3plus_median_pnl": window_high["median_pnl"],
            }
        )

    gates = {
        "aggregate_sample_passed": aggregate_sample_passed,
        "aggregate_avg_pnl_monotonic": aggregate_avg_monotonic,
        "aggregate_median_pnl_monotonic": aggregate_median_monotonic,
        "aggregate_avg_return_monotonic": aggregate_return_monotonic,
        "per_window_sample_passed": per_window_sample_passed,
        "per_window_avg_pnl_monotonic": per_window_avg_monotonic,
        "per_window_median_pnl_monotonic": per_window_median_monotonic,
    }
    passed = all(gates.values())
    if passed:
        decision = "positive_observational_source_family_count_monotonicity_not_promoted"
        rationale = (
            "Source-family count was ordered and adequately sampled, but this replay-only run does "
            "not promote ranking behavior or production changes."
        )
    elif not aggregate_sample_passed or not per_window_sample_passed:
        decision = "rejected_source_family_count_monotonicity_thin_3plus_bucket"
        rationale = (
            "The 3plus-family bucket is directionally strong but too thin across canonical windows "
            "to justify a new ranking feature."
        )
    else:
        decision = "rejected_source_family_count_not_monotonic"
        rationale = (
            "Source-family count failed monotonic validation, so it remains an admission guard only."
        )

    return {
        "passed": passed,
        "decision": decision,
        "rationale": rationale,
        "gates": gates,
        "per_window": per_window_rows,
    }


def _current_accepted_identity(
    aggregate: dict[str, Any],
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    source = consensus.prior._load_json(consensus.ROOT / CURRENT_ACCEPTED_CONSENSUS_ARTIFACT)
    source_results = {str(row["label"]): row for row in source.get("results", [])}
    by_window: list[dict[str, Any]] = []
    mismatched_windows: list[str] = []

    for row in results:
        label = str(row["label"])
        source_row = source_results[label]
        ev_delta = round(
            float(row["after"]["expected_value_score"])
            - float(source_row["after"]["expected_value_score"]),
            6,
        )
        pnl_delta = round(
            float(row["after"]["total_pnl"]) - float(source_row["after"]["total_pnl"]),
            2,
        )
        trade_delta = int(row["target_trade_count"]) - int(source_row["target_trade_count"])
        if ev_delta != 0 or pnl_delta != 0 or trade_delta != 0:
            mismatched_windows.append(label)
        by_window.append(
            {
                "label": label,
                "after_expected_value_delta_vs_current_accepted": ev_delta,
                "after_total_pnl_delta_vs_current_accepted": pnl_delta,
                "target_trade_count_delta_vs_current_accepted": trade_delta,
            }
        )

    aggregate_ev_delta = round(
        float(aggregate["after"]["expected_value_score"])
        - float(source["aggregate"]["after"]["expected_value_score"]),
        6,
    )
    aggregate_pnl_delta = round(
        float(aggregate["after"]["strategy_total_pnl"])
        - float(source["aggregate"]["after"]["strategy_total_pnl"]),
        2,
    )
    passed = aggregate_ev_delta == 0 and aggregate_pnl_delta == 0 and not mismatched_windows
    return {
        "comparison_artifact": str(CURRENT_ACCEPTED_CONSENSUS_ARTIFACT).replace("\\", "/"),
        "current_accepted_experiment_id": str(source.get("experiment_id")),
        "passed": passed,
        "aggregate_after_expected_value_delta_vs_current_accepted": aggregate_ev_delta,
        "aggregate_after_strategy_total_pnl_delta_vs_current_accepted": aggregate_pnl_delta,
        "mismatched_windows": mismatched_windows,
        "by_window": by_window,
    }


def _target_trade_pnl_consistency(
    target_trades_by_window: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    by_window: dict[str, Any] = {}
    all_rows: list[dict[str, Any]] = []
    for label, trades in target_trades_by_window.items():
        rows: list[dict[str, Any]] = []
        for trade in trades:
            pnl = float(trade.get("pnl") or 0.0)
            notional = float(trade.get("paper_notional_usd") or 0.0)
            ret = float(trade.get("pnl_pct_net") or 0.0)
            implied_pnl = round(notional * ret, 2)
            diff = round(pnl - implied_pnl, 2)
            row = {
                "window": label,
                "date": trade.get("date") or trade.get("signal_date"),
                "ticker": trade.get("ticker"),
                "paper_notional_usd": notional,
                "pnl_pct_net": ret,
                "recorded_pnl": round(pnl, 2),
                "implied_pnl_from_notional_and_return": implied_pnl,
                "pnl_diff": diff,
            }
            rows.append(row)
            all_rows.append(row)
        by_window[label] = _pnl_consistency_summary(rows)
    return {
        "formula": "recorded_pnl should equal round(paper_notional_usd * pnl_pct_net, 2)",
        "aggregate": _pnl_consistency_summary(all_rows),
        "by_window": by_window,
        "sample_mismatches": [
            row for row in all_rows if abs(float(row["pnl_diff"])) > 0.02
        ][:10],
    }


def _pnl_consistency_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    recorded = sum(float(row["recorded_pnl"]) for row in rows)
    implied = sum(float(row["implied_pnl_from_notional_and_return"]) for row in rows)
    diff = sum(float(row["pnl_diff"]) for row in rows)
    mismatch_count = sum(1 for row in rows if abs(float(row["pnl_diff"])) > 0.02)
    return {
        "trade_count": len(rows),
        "recorded_pnl": _round(recorded, 2),
        "implied_pnl_from_notional_and_return": _round(implied, 2),
        "pnl_diff": _round(diff, 2),
        "mismatch_count": mismatch_count,
        "passed": mismatch_count == 0,
    }


def _apply_monotonic_gate(
    gate4: dict[str, Any],
    monotonic_gate: dict[str, Any],
    identity: dict[str, Any],
    pnl_consistency: dict[str, Any],
) -> dict[str, Any]:
    gate4["gates"]["current_accepted_consensus_identity_passed"] = bool(identity["passed"])
    for name, value in monotonic_gate["gates"].items():
        gate4["gates"][f"monotonic_{name}"] = bool(value)
    gate4["monotonic_validation"] = monotonic_gate
    gate4["current_accepted_identity"] = identity
    gate4["pnl_consistency"] = pnl_consistency

    if not identity["passed"]:
        gate4["passed"] = False
        accepted_consistency = pnl_consistency["current_accepted_artifact"]["aggregate"]
        if not accepted_consistency["passed"]:
            gate4["decision"] = "rejected_current_accepted_consensus_pnl_notional_identity_failed"
            gate4["rationale"] = (
                "The observational replay selected the same target-trade count but did not match "
                "the current accepted artifact because the accepted artifact's recorded PnL does "
                "not equal paper_notional_usd times pnl_pct_net. Treat source-family-count ranking "
                "as blocked until the accepted consensus baseline is repaired."
            )
        else:
            gate4["decision"] = "rejected_current_accepted_consensus_replay_identity_failed"
            gate4["rationale"] = (
                "The observational replay did not exactly match the current accepted consensus metrics."
            )
        gate4["requires_parity_before_promotion"] = False
        return gate4

    if not monotonic_gate["passed"]:
        gate4["passed"] = False
        gate4["decision"] = monotonic_gate["decision"]
        gate4["rationale"] = monotonic_gate["rationale"]
        gate4["requires_parity_before_promotion"] = False
    else:
        gate4["passed"] = False
        gate4["decision"] = monotonic_gate["decision"]
        gate4["rationale"] = (
            monotonic_gate["rationale"]
            + " Source-count ranking remains default-off and unpromoted in this experiment."
        )
        gate4["requires_parity_before_promotion"] = False
    return gate4


def _experiment_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    comparison = payload["aggregate"]["comparison"]
    prediction = {
        "success_probability": 0.16,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "non_monotonic_bucket_outcomes",
            "thin_3plus_family_sample",
            "nearby_source_count_overfit",
            "current_accepted_comparator_not_replayed",
        ],
        "confidence_reason": (
            "The accepted consensus uses family count only as admission; ranking by count is a "
            "frozen nearby direction unless monotonic evidence is dense across windows."
        ),
        "recorded_at": "2026-06-03T16:09:15Z",
    }
    actual_success = 1 if payload["monotonic_gate"]["passed"] else 0
    high = payload["bucket_summary"]["aggregate"]["family_count_3plus"]
    low = payload["bucket_summary"]["aggregate"]["family_count_2"]
    accepted_pnl_consistency = payload["pnl_consistency_audit"]["current_accepted_artifact"][
        "aggregate"
    ]
    current_pnl_consistency = payload["pnl_consistency_audit"]["current_replay"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["completed_at"],
        "lane": "alpha_search",
        "status": "rejected",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": "source_family_count_2_vs_3plus_bucket_v1",
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["preflight"]["alpha_hypothesis"],
        "change_type": "default_off_paper_ranking_validation",
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "prior_trial_count": 9,
        "nearby_prior_experiments": payload["preflight"]["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "source_family_count_monotonicity_validation",
        "decision": payload["gate4"]["decision"],
        "accepted": False,
        "rejection_reason": payload["gate4"]["rationale"],
        "prediction": prediction,
        "calibration": {
            "actual_decision": payload["gate4"]["decision"],
            "actual_success": actual_success,
            "predicted_success_probability": prediction["success_probability"],
            "brier_score": round((prediction["success_probability"] - actual_success) ** 2, 6),
            "expected_ev_delta": prediction["expected_ev_delta"],
            "actual_ev_delta": comparison["expected_value_score_delta"],
            "ev_prediction_error": round(
                comparison["expected_value_score_delta"] - prediction["expected_ev_delta"], 6
            ),
            "expected_pnl_delta": prediction["expected_pnl_delta"],
            "actual_pnl_delta": comparison["strategy_total_pnl_delta"],
            "pnl_prediction_error": round(
                comparison["strategy_total_pnl_delta"] - prediction["expected_pnl_delta"], 2
            ),
            "realized_failure_mode": "thin_3plus_family_sample"
            if not payload["monotonic_gate"]["gates"]["aggregate_sample_passed"]
            else "source_family_count_monotonicity_failed",
        },
        "production_impact": PRODUCTION_IMPACT,
        "requires_parity_before_promotion": False,
        "metrics": {
            "aggregate_expected_value_before": payload["aggregate"]["before"]["expected_value_score"],
            "aggregate_expected_value_after": payload["aggregate"]["after"]["expected_value_score"],
            "aggregate_expected_value_delta": comparison["expected_value_score_delta"],
            "aggregate_strategy_total_pnl_before": payload["aggregate"]["before"]["strategy_total_pnl"],
            "aggregate_strategy_total_pnl_after": payload["aggregate"]["after"]["strategy_total_pnl"],
            "aggregate_strategy_total_pnl_delta": comparison["strategy_total_pnl_delta"],
            "target_trade_count": payload["target_summary"]["target_trade_count"],
            "family_count_2_trade_count": low["trade_count"],
            "family_count_2_avg_pnl": low["avg_pnl"],
            "family_count_2_median_pnl": low["median_pnl"],
            "family_count_3plus_trade_count": high["trade_count"],
            "family_count_3plus_avg_pnl": high["avg_pnl"],
            "family_count_3plus_median_pnl": high["median_pnl"],
            "current_accepted_identity_passed": payload["current_accepted_identity"]["passed"],
            "current_replay_pnl_consistency_passed": current_pnl_consistency["passed"],
            "accepted_artifact_pnl_consistency_passed": accepted_pnl_consistency["passed"],
            "accepted_artifact_pnl_diff": accepted_pnl_consistency["pnl_diff"],
            "accepted_artifact_pnl_mismatch_count": accepted_pnl_consistency["mismatch_count"],
        },
        "windows": [
            {
                "label": row["label"],
                "expected_value_before": row["before"]["expected_value_score"],
                "expected_value_after": row["after"]["expected_value_score"],
                "expected_value_delta": row["comparison"]["expected_value_score_delta"],
                "strategy_total_pnl_delta": row["comparison"]["strategy_total_pnl_delta"],
                "target_trade_count": row["target_trade_count"],
                "target_trade_pnl_usd": row["target_trade_pnl_usd"],
            }
            for row in payload["results"]
        ],
        "artifact_path": str(OUT_JSON).replace("\\", "/"),
        "anti_js": "No JavaScript was used.",
    }


def _write_card(payload: dict[str, Any]) -> None:
    aggregate = payload["aggregate"]
    comparison = aggregate["comparison"]
    low = payload["bucket_summary"]["aggregate"]["family_count_2"]
    high = payload["bucket_summary"]["aggregate"]["family_count_3plus"]
    current_pnl = payload["pnl_consistency_audit"]["current_replay"]["aggregate"]
    accepted_pnl = payload["pnl_consistency_audit"]["current_accepted_artifact"]["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID}: consensus source-family monotonicity",
        "",
        f"- Decision: `{payload['gate4']['decision']}`",
        f"- Rationale: {payload['gate4']['rationale']}",
        f"- Before aggregate EV/PnL: `{aggregate['before']['expected_value_score']}` / `${aggregate['before']['strategy_total_pnl']}`",
        f"- After aggregate EV/PnL: `{aggregate['after']['expected_value_score']}` / `${aggregate['after']['strategy_total_pnl']}`",
        f"- Delta EV/PnL: `{comparison['expected_value_score_delta']}` / `${comparison['strategy_total_pnl_delta']}`",
        f"- Current accepted replay identity passed: `{payload['current_accepted_identity']['passed']}`",
        f"- Current replay PnL consistency passed: `{current_pnl['passed']}`",
        f"- Accepted artifact PnL consistency passed: `{accepted_pnl['passed']}`",
        f"- Accepted artifact PnL diff vs notional*return: `${accepted_pnl['pnl_diff']}` across `{accepted_pnl['mismatch_count']}` trades",
        "",
        "## Bucket Evidence",
        "",
        "| bucket | trades | total pnl | avg pnl | median pnl | win rate |",
        "|---|---:|---:|---:|---:|---:|",
        (
            f"| family_count_2 | {low['trade_count']} | {low['total_pnl']} | "
            f"{low['avg_pnl']} | {low['median_pnl']} | {low['win_rate']} |"
        ),
        (
            f"| family_count_3plus | {high['trade_count']} | {high['total_pnl']} | "
            f"{high['avg_pnl']} | {high['median_pnl']} | {high['win_rate']} |"
        ),
        "",
        "## Three Windows",
        "",
        "| window | EV before | EV after | EV delta | PnL delta | target trades |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in payload["results"]:
        lines.append(
            "| {label} | {before_ev} | {after_ev} | {ev_delta} | {pnl_delta} | {trades} |".format(
                label=row["label"],
                before_ev=row["before"]["expected_value_score"],
                after_ev=row["after"]["expected_value_score"],
                ev_delta=row["comparison"]["expected_value_score_delta"],
                pnl_delta=row["comparison"]["strategy_total_pnl_delta"],
                trades=row["target_trade_count"],
            )
        )
    lines.extend(
        [
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    CARD_MD.parent.mkdir(parents=True, exist_ok=True)
    CARD_MD.write_text("\n".join(lines), encoding="utf-8")


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = consensus.prior._load_json(TICKET_JSON) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "id": EXPERIMENT_ID,
            "experiment_id": EXPERIMENT_ID,
            "status": "completed",
            "decision": payload["gate4"]["decision"],
            "completed_at": payload["completed_at"],
            "artifact": str(OUT_JSON).replace("\\", "/"),
            "log": str(LOG_JSON).replace("\\", "/"),
            "production_impact": PRODUCTION_IMPACT,
            "gate4": payload["gate4"],
            "result": {
                "accepted": False,
                "summary": payload["gate4"]["rationale"],
            },
        }
    )
    consensus.prior._write_json(TICKET_JSON, ticket)


def _upsert_registry(payload: dict[str, Any]) -> None:
    if not REGISTRY_JSON.exists():
        return
    registry = consensus.prior._load_json(REGISTRY_JSON)
    experiments = registry.get("experiments")
    if not isinstance(experiments, list):
        return
    for item in experiments:
        if isinstance(item, dict) and item.get("experiment_id") == EXPERIMENT_ID:
            item["status"] = "completed"
            item["decision"] = payload["gate4"]["decision"]
            item["completed_at"] = payload["completed_at"]
            item["artifact"] = str(OUT_JSON).replace("\\", "/")
            item["log"] = str(LOG_JSON).replace("\\", "/")
            item["aggregate_expected_value_delta"] = payload["aggregate"]["comparison"][
                "expected_value_score_delta"
            ]
            item["aggregate_strategy_total_pnl_delta"] = payload["aggregate"]["comparison"][
                "strategy_total_pnl_delta"
            ]
            item["result"] = {
                "accepted": False,
                "summary": payload["gate4"]["rationale"],
            }
            break
    REGISTRY_JSON.write_text(
        json.dumps(registry, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    _configure_consensus_module()
    gate2 = consensus.prior.base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    source_rows = consensus.prior._source_rows_by_window()
    baselines = consensus.prior._load_baselines()
    results, target_trades_by_window = consensus._run_windows(baselines, source_rows)
    aggregate = consensus.prior._aggregate_results(results)
    target_summary = consensus.prior._target_summary(target_trades_by_window)
    source_family_summary = consensus._source_family_summary(target_trades_by_window)
    base_gate4 = consensus.prior._gate4_decision(aggregate, results, target_summary)
    bucket_summary = _bucket_summaries(target_trades_by_window)
    monotonic_gate = _monotonic_gate(bucket_summary)
    current_accepted_identity = _current_accepted_identity(aggregate, results)
    accepted_artifact = consensus.prior._load_json(
        consensus.ROOT / CURRENT_ACCEPTED_CONSENSUS_ARTIFACT
    )
    pnl_consistency_audit = {
        "current_replay": _target_trade_pnl_consistency(target_trades_by_window),
        "current_accepted_artifact": _target_trade_pnl_consistency(
            accepted_artifact["target_trades_by_window"]
        ),
    }
    gate4 = _apply_monotonic_gate(
        base_gate4,
        monotonic_gate,
        current_accepted_identity,
        pnl_consistency_audit,
    )
    completed_at = _utc_now()

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": completed_at,
        "completed_at": completed_at,
        "lane": "alpha_search",
        "preflight": _preflight_payload(),
        "source_files": {
            name: str(path).replace("\\", "/") for name, path in consensus.SOURCE_FILES.items()
        },
        "rule": {
            "rule_version": RULE_VERSION,
            "observed_bucket_field": "source_family_count",
            "bucket_min_count_thresholds": {
                "aggregate_high_bucket": MIN_AGGREGATE_HIGH_BUCKET_TRADES,
                "per_window_high_bucket": MIN_PER_WINDOW_HIGH_BUCKET_TRADES,
                "per_window_low_bucket": MIN_PER_WINDOW_LOW_BUCKET_TRADES,
            },
            "no_candidate_selection_change": True,
            "base_notional_usd": consensus.prior.BASE_NOTIONAL_USD,
            "hold_days": consensus.prior.HOLD_DAYS,
            "max_paper_trades_per_day": consensus.prior.MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": consensus.prior.SAME_TICKER_COOLDOWN_DAYS,
        },
        "production_impact": PRODUCTION_IMPACT,
        "gate2": gate2,
        "gate3": {
            "survival_floor": 0.05,
            "new_core_filter_added": False,
            "observational_bucket_validation_only": True,
        },
        "aggregate": aggregate,
        "results": results,
        "target_summary": target_summary,
        "target_trades_by_window": target_trades_by_window,
        "source_family_summary": source_family_summary,
        "bucket_summary": bucket_summary,
        "monotonic_gate": monotonic_gate,
        "current_accepted_identity": current_accepted_identity,
        "pnl_consistency_audit": pnl_consistency_audit,
        "gate4": gate4,
        "anti_js": "No JavaScript was used.",
    }

    consensus.prior._write_json(OUT_JSON, payload)
    record = _experiment_log_record(payload)
    consensus.prior._write_json(LOG_JSON, record)
    _write_card(payload)
    _update_ticket(payload)
    _upsert_registry(payload)
    consensus.prior.base._upsert_jsonl(EXPERIMENT_LOG, record)

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": gate4["decision"],
                "aggregate": aggregate["comparison"],
                "bucket_summary": bucket_summary["aggregate"],
                "monotonic_gate": monotonic_gate,
                "current_accepted_identity": current_accepted_identity,
                "anti_js": payload["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
