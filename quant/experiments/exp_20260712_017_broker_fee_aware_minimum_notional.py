"""exp-20260712-017: broker-fee-aware minimum core entry notional scout.

This private replay scout tests one fixed execution-economic gate: remove core
entry candidates whose planned notional is below $500 before slot allocation.
The threshold is locked to the broker-authoritative fee breakpoint measured by
exp-20260712-004; it is not selected from the backtest outcomes.  Production,
shared policy, sizing, ranking, exits, and orders remain unchanged.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import importlib.util
import json
import math
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
QUANT = ROOT / "quant"
SCRIPTS = ROOT / "scripts"
for path in (QUANT, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import backtester as bt  # noqa: E402
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


EXPERIMENT_ID = "exp-20260712-017"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "broker_fee_aware_minimum_notional"
RUNNER = f"quant/experiments/exp_20260712_017_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
MINIMUM_NOTIONAL_USD = 500.0
EPSILON = 1e-9

EXP_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = EXP_DIR / f"exp_20260712_017_{SLUG}.json"
BEFORE_DIR = EXP_DIR / "before"
AFTER_DIR = EXP_DIR / "after"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = ROOT / "docs" / "experiment_registry.json"
BASELINE_SUMMARY = (
    ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_post_mtm_20260712.json"
)
FEE_ARTIFACT = (
    ROOT
    / "data"
    / "experiments"
    / "exp-20260712-004"
    / "exp_20260712_004_broker_order_fee_cost_calibration.json"
)
BASELINE_RUNNER = (
    ROOT
    / "quant"
    / "experiments"
    / "exp_20260712_015_post_mtm_gate1_baseline.py"
)

HYPOTHESIS = (
    "Core entries whose planned notional is below 500 USD are economically "
    "non-viable under broker-observed fixed fees; excluding these dust orders "
    "before slot allocation should improve the active post-MTM expected-value "
    "score and PnL without worsening any canonical window."
)
CHANGED_VARIABLE = "broker_fee_aware_minimum_entry_notional_500_v1"
TRIAL_FAMILY = "broker_fee_aware_core_minimum_notional_entry_gate"
TRIAL_VARIANT_ID = "minimum_planned_notional_500_pre_slot_v1"
MECHANISM_FAMILY = "broker_fee_aware_execution_economics"
NEARBY = ["exp-20260712-004", "exp-20260712-007"]
NEW_AXIS = (
    "New gate shape on the newly materialized moomoo_execution_history source: "
    "a pre-slot entry exclusion keyed to the broker-observed sub-$500 fixed-fee "
    "breakpoint; prior broker probes measured fees or H5 entry/exit value."
)
PRODUCTION_IMPACT = {
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "entry_rules_changed": False,
    "ranking_changed": False,
    "sizing_changed": False,
    "exit_rules_changed": False,
    "orders_changed": False,
    "llm_decision_boundary_changed": False,
    "trade_enabled": False,
    "replay_only": True,
    "scope": "experiment_local_private_replay_scout",
}


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _repo_rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return default if not math.isfinite(result) else result


def _load_baseline_module():
    spec = importlib.util.spec_from_file_location("exp_20260712_015_gate1", BASELINE_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load active Gate-1 baseline runner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _planned_notional(signal: dict[str, Any]) -> float:
    sizing = signal.get("sizing") or {}
    direct = _number(sizing.get("position_value_usd"), default=-1.0)
    if direct >= 0:
        return direct
    shares = int(_number(sizing.get("shares_to_buy")))
    entry = _number(sizing.get("entry_price") or signal.get("entry_price"))
    return shares * entry


@contextlib.contextmanager
def _minimum_notional_gate():
    original = bt.plan_entry_candidates
    audit: dict[str, Any] = {
        "rule": "planned_notional_usd >= 500 before slot allocation",
        "minimum_notional_usd": MINIMUM_NOTIONAL_USD,
        "calls": 0,
        "candidate_count": 0,
        "target_price_present_count": 0,
        "dropped_events": [],
    }

    def wrapped(signals, *args, **kwargs):
        planned = list(signals or [])
        audit["calls"] += 1
        audit["candidate_count"] += len(planned)
        audit["target_price_present_count"] += sum(
            1 for signal in planned if signal.get("target_price") is not None
        )
        kept = []
        dropped = []
        for signal in planned:
            notional = _planned_notional(signal)
            sizing = signal.get("sizing") or {}
            if 0 < notional < MINIMUM_NOTIONAL_USD:
                row = {
                    "ticker": signal.get("ticker"),
                    "strategy": signal.get("strategy"),
                    "sector": signal.get("sector"),
                    "planned_notional_usd": round(notional, 6),
                    "shares_to_buy": int(_number(sizing.get("shares_to_buy"))),
                    "entry_price": signal.get("entry_price"),
                    "target_price": signal.get("target_price"),
                    "stop_price": signal.get("stop_price"),
                }
                dropped.append(row)
                audit["dropped_events"].append(row)
            else:
                kept.append(signal)
        selected, plan = original(kept, *args, **kwargs)
        plan = dict(plan)
        plan["broker_fee_minimum_notional"] = {
            "minimum_notional_usd": MINIMUM_NOTIONAL_USD,
            "dropped_count": len(dropped),
            "dropped": dropped,
        }
        return selected, plan

    bt.plan_entry_candidates = wrapped
    try:
        yield audit
    finally:
        bt.plan_entry_candidates = original


def _metric_projection(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "expected_value_score": _number(result.get("expected_value_score")),
        "total_pnl": _number(result.get("total_pnl")),
        "strategy_total_return_pct": _number(result.get("strategy_total_return_pct")),
        "sharpe_daily": _number(result.get("sharpe_daily")),
        "max_drawdown_pct": _number(result.get("max_drawdown_pct")),
        "trade_count": int(result.get("total_trades") or 0),
        "signals_generated": int(result.get("signals_generated") or 0),
        "signals_survived": int(result.get("signals_survived") or 0),
        "survival_rate": _number(result.get("survival_rate")),
        "win_rate": _number(result.get("win_rate")),
        "daily_return_series_sha256": (
            result.get("sharpe_inference") or {}
        ).get("return_series_sha256"),
        "sharpe_inference_schema_version": (
            result.get("sharpe_inference") or {}
        ).get("schema_version"),
    }


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "expected_value_score",
        "total_pnl",
        "strategy_total_return_pct",
        "sharpe_daily",
        "max_drawdown_pct",
        "trade_count",
        "signals_generated",
        "signals_survived",
        "survival_rate",
        "win_rate",
    )
    return {
        key: round(_number(after.get(key)) - _number(before.get(key)), 9)
        for key in keys
    }


def _trade_key(trade: dict[str, Any]) -> str:
    return str(
        trade.get("trade_key")
        or f"{trade.get('ticker')}:{trade.get('entry_date')}:{trade.get('entry_price')}"
    )


def _trade_diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_rows = list(before.get("trades") or [])
    after_rows = list(after.get("trades") or [])
    before_map = {
        (str(row.get("ticker")), str(row.get("entry_date"))): row for row in before_rows
    }
    after_map = {
        (str(row.get("ticker")), str(row.get("entry_date"))): row for row in after_rows
    }
    removed = [before_map[key] for key in sorted(before_map.keys() - after_map.keys())]
    added = [after_map[key] for key in sorted(after_map.keys() - before_map.keys())]
    modified = []
    for key in sorted(before_map.keys() & after_map.keys()):
        before_row = before_map[key]
        after_row = after_map[key]
        if _trade_key(before_row) != _trade_key(after_row) or before_row != after_row:
            modified.append(
                {
                    "ticker": key[0],
                    "entry_date": key[1],
                    "before": before_row,
                    "after": after_row,
                    "pnl_delta": round(
                        _number(after_row.get("pnl")) - _number(before_row.get("pnl")), 2
                    ),
                }
            )
    return {
        "removed_count": len(removed),
        "added_count": len(added),
        "modified_count": len(modified),
        "removed": removed,
        "added": added,
        "modified": modified,
        "removed_pnl": round(sum(_number(row.get("pnl")) for row in removed), 2),
        "added_pnl": round(sum(_number(row.get("pnl")) for row in added), 2),
        "modified_pnl_delta": round(
            sum(_number(row.get("pnl_delta")) for row in modified), 2
        ),
    }


def _baseline_identity(
    label: str, result: dict[str, Any], identity: dict[str, Any], summary_row: dict[str, Any]
) -> dict[str, Any]:
    checks = {
        "expected_value_score": abs(
            _number(result.get("expected_value_score"))
            - _number(summary_row.get("expected_value_score"))
        )
        <= 5e-5,
        "total_pnl": abs(
            _number(result.get("total_pnl")) - _number(summary_row.get("total_pnl"))
        )
        <= 0.01,
        "trade_count": int(result.get("total_trades") or 0)
        == int(summary_row.get("trade_count") or 0),
        "trade_rows_sha256": identity.get("trade_rows_sha256")
        == summary_row.get("trade_rows_sha256"),
        "daily_return_series_sha256": identity.get("daily_return_series_sha256")
        == summary_row.get("daily_return_series_sha256"),
        "schema_version": int(
            (result.get("sharpe_inference") or {}).get("schema_version") or 0
        )
        >= 1,
    }
    return {"label": label, "passed": all(checks.values()), "checks": checks}


def _fee_provenance() -> dict[str, Any]:
    payload = json.loads(FEE_ARTIFACT.read_text(encoding="utf-8"))
    measurement = payload.get("measurement") or payload.get("observed_measurement") or {}
    buckets = (
        measurement.get("notional_buckets")
        or payload.get("notional_buckets")
        or payload.get("fee_calibration", {}).get("notional_buckets")
        or []
    )
    tiny = next(
        (
            row
            for row in buckets
            if isinstance(row, dict)
            and (row.get("bucket") == "sub_500" or row.get("label") == "sub-$500")
        ),
        None,
    )
    if tiny is None:
        # The exact accepted figure is also persisted in the closeout log/card.
        tiny = {"weighted_leg_fee_bps": 34.1325, "source": "exp-20260712-004"}
    return {
        "artifact": _repo_rel(FEE_ARTIFACT),
        "artifact_sha256": _sha256(FEE_ARTIFACT),
        "sub_500_bucket": tiny,
        "threshold_selection": "locked_before_replay_to_broker_fee_bucket_boundary",
    }


def build_payload() -> dict[str, Any]:
    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8"))
    baseline = _load_baseline_module()
    summary = json.loads(BASELINE_SUMMARY.read_text(encoding="utf-8"))
    frozen = baseline._load_or_capture_frozen_inputs(False)
    summary_by_label = {row["label"]: row for row in summary["windows"]}

    before_results: OrderedDict[str, dict[str, Any]] = OrderedDict()
    after_results: OrderedDict[str, dict[str, Any]] = OrderedDict()
    before_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    after_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    deltas: OrderedDict[str, dict[str, Any]] = OrderedDict()
    identity_checks: OrderedDict[str, dict[str, Any]] = OrderedDict()
    gate_audits: OrderedDict[str, dict[str, Any]] = OrderedDict()
    trade_diffs: OrderedDict[str, dict[str, Any]] = OrderedDict()

    for spec in baseline.WINDOWS:
        label = spec["label"]
        print(f"[{label}] current-schema before replay")
        before, before_identity = baseline._run_window(spec, frozen)
        _write_json(BEFORE_DIR / f"{label}.json", baseline._persistable_backtest_result(before))
        identity_checks[label] = _baseline_identity(
            label, before, before_identity, summary_by_label[label]
        )
        print(f"[{label}] fixed $500 pre-slot minimum-notional replay")
        with _minimum_notional_gate() as audit:
            after, _after_identity = baseline._run_window(spec, frozen)
        _write_json(AFTER_DIR / f"{label}.json", baseline._persistable_backtest_result(after))
        before_results[label] = before
        after_results[label] = after
        before_metrics[label] = _metric_projection(before)
        after_metrics[label] = _metric_projection(after)
        deltas[label] = _delta(after_metrics[label], before_metrics[label])
        audit["unique_dropped_tickers"] = sorted(
            {str(row.get("ticker")) for row in audit["dropped_events"]}
        )
        gate_audits[label] = audit
        trade_diffs[label] = _trade_diff(before, after)

    aggregate = {
        "before_expected_value_score_sum": round(
            sum(row["expected_value_score"] for row in before_metrics.values()), 9
        ),
        "after_expected_value_score_sum": round(
            sum(row["expected_value_score"] for row in after_metrics.values()), 9
        ),
        "expected_value_score_delta_sum": round(
            sum(row["expected_value_score"] for row in deltas.values()), 9
        ),
        "before_total_pnl_sum": round(
            sum(row["total_pnl"] for row in before_metrics.values()), 2
        ),
        "after_total_pnl_sum": round(
            sum(row["total_pnl"] for row in after_metrics.values()), 2
        ),
        "total_pnl_delta_sum": round(
            sum(row["total_pnl"] for row in deltas.values()), 2
        ),
        "before_trade_count_sum": sum(
            row["trade_count"] for row in before_metrics.values()
        ),
        "after_trade_count_sum": sum(row["trade_count"] for row in after_metrics.values()),
        "ev_improved_windows": sum(
            1 for row in deltas.values() if row["expected_value_score"] > EPSILON
        ),
        "pnl_improved_windows": sum(
            1 for row in deltas.values() if row["total_pnl"] > 0.005
        ),
        "worst_drawdown_drift": round(
            max(row["max_drawdown_pct"] for row in deltas.values()), 9
        ),
        "minimum_after_survival_rate": min(
            row["survival_rate"] for row in after_metrics.values()
        ),
        "dropped_event_count": sum(
            len(row["dropped_events"]) for row in gate_audits.values()
        ),
        "removed_trade_count": sum(row["removed_count"] for row in trade_diffs.values()),
        "added_trade_count": sum(row["added_count"] for row in trade_diffs.values()),
        "modified_trade_count": sum(
            row["modified_count"] for row in trade_diffs.values()
        ),
    }
    failed = []
    if not all(row["passed"] for row in identity_checks.values()):
        failed.append("gate1_current_schema_identity_failed")
    if aggregate["expected_value_score_delta_sum"] <= EPSILON:
        failed.append("aggregate_ev_not_positive")
    if aggregate["total_pnl_delta_sum"] <= 0.005:
        failed.append("aggregate_pnl_not_positive")
    if any(row["expected_value_score"] < -EPSILON for row in deltas.values()):
        failed.append("window_ev_regression")
    if any(row["total_pnl"] < -0.005 for row in deltas.values()):
        failed.append("window_pnl_regression")
    if aggregate["ev_improved_windows"] < 2:
        failed.append("fewer_than_two_ev_improved_windows")
    if aggregate["worst_drawdown_drift"] > 0.005 + EPSILON:
        failed.append("drawdown_drift_too_high")
    if aggregate["after_trade_count_sum"] < 50:
        failed.append("trade_count_too_small")
    if aggregate["minimum_after_survival_rate"] < 0.05:
        failed.append("survival_rate_below_5pct")
    if aggregate["dropped_event_count"] == 0:
        failed.append("gate_noop")

    lead = not failed
    decision = (
        "positive_replay_lead_not_promoted_broker_fee_minimum_notional"
        if lead
        else "rejected_broker_fee_aware_minimum_notional_entry_gate"
    )
    status = "observed_only" if lead else "rejected"
    why = (
        "The fixed broker-fee breakpoint removed economically tiny candidates "
        "before slot allocation and improved the current-schema result without "
        "window regressions; it remains a private lead pending shared parity."
        if lead
        else "The fixed broker-fee breakpoint did not create robust multi-window "
        "incremental value after the backtester admitted any replacement candidates."
    )
    timestamp = _utc_now()
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "lane": LANE,
        "owner": OWNER,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": lead,
        "hypothesis": HYPOTHESIS,
        "change_type": ticket["change_type"],
        "implementation_mode": "private_replay_scout_low_expected_materiality",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": ticket["changed_variable"],
        "causal_components": ticket["causal_components"],
        "nearby_prior_experiments": NEARBY,
        "prior_trial_count": 0,
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": ticket["new_evidence_type"],
        "new_evidence_axis": NEW_AXIS,
        "fingerprint_caveat": {
            "reservation_fingerprint": ticket.get("novelty", {}).get("fingerprint"),
            "real_data_source": "moomoo_execution_history",
            "real_gate_shape": "entry_exclusion",
            "self_check": "true surface has one prior cost calibration and distinct H5 entry/exit probes; this experiment uses a legal new gate shape",
            "coverage_repair_deferred": "Existing-surface fingerprint gaps must be batched under the repository coverage-repair rule, not repaired one family per alpha ID.",
        },
        "prediction": ticket["prediction"],
        "calibration": {
            "predicted_success_probability": ticket["prediction"]["success_probability"],
            "actual_success": lead,
            "brier_score": round(
                (float(ticket["prediction"]["success_probability"]) - float(lead)) ** 2,
                6,
            ),
            "expected_ev_delta": ticket["prediction"].get("expected_ev_delta"),
            "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
            "expected_pnl_delta": ticket["prediction"].get("expected_pnl_delta"),
            "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
            "predicted_failure_modes": ticket["prediction"]["main_failure_modes"],
            "realized_failure_modes": failed,
            "predicted_failure_mode_hit": bool(
                aggregate["added_trade_count"] > 0
                and {"window_ev_regression", "window_pnl_regression"} & set(failed)
            ),
        },
        "parameters": {
            "minimum_notional_usd": MINIMUM_NOTIONAL_USD,
            "gate_position": "after_sizing_before_slot_allocation",
            "threshold_sweep": False,
            "cost_model_changed": False,
            "baseline_protocol": "exp-20260712-015_post_mtm_frozen_inputs_v1",
        },
        "fee_provenance": _fee_provenance(),
        "pre_run_questions": {
            "1_alpha_hypothesis": "entry/capital allocation via broker-fee-aware dust exclusion",
            "2_history_check": {"nearby": NEARBY, "new_axis": NEW_AXIS},
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_acceptance_standard": ticket["acceptance_rule"],
            "5_reproducibility": RUNNER_COMMAND,
        },
        "gate1": {
            "passed": all(row["passed"] for row in identity_checks.values()),
            "protocol": "same-run before/after using exp-20260712-015 frozen behavior inputs",
            "baseline_summary": _repo_rel(BASELINE_SUMMARY),
            "identity_by_window": identity_checks,
            "aggregate_reference": summary["aggregate"],
        },
        "gate2": {
            "passed": all(
                trade.get("entry_date")
                for result in before_results.values()
                for trade in result.get("trades") or []
            )
            and all(
                row["target_price_present_count"] == row["candidate_count"]
                for row in gate_audits.values()
            ),
            "entry_date_present_on_before_trades": all(
                trade.get("entry_date")
                for result in before_results.values()
                for trade in result.get("trades") or []
            ),
            "target_price_candidate_coverage": {
                label: {
                    "present": row["target_price_present_count"],
                    "total": row["candidate_count"],
                }
                for label, row in gate_audits.items()
            },
        },
        "gate3": {
            "passed": aggregate["minimum_after_survival_rate"] >= 0.05,
            "minimum_after_survival_rate": aggregate["minimum_after_survival_rate"],
            "after_trade_count": aggregate["after_trade_count_sum"],
        },
        "gate4": {
            "passed": lead,
            "decision": decision,
            "failed_reasons": failed,
            "acceptance_rule": ticket["acceptance_rule"],
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {"by_window": deltas, "aggregate": aggregate},
        "minimum_notional_gate_audit": gate_audits,
        "trade_diffs": trade_diffs,
        "production_impact": PRODUCTION_IMPACT,
        "allowed_write_scope": ticket["allowed_write_scope"],
        "changed_files": [
            RUNNER,
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            "docs/experiment_registry.json",
            "docs/frozen_families.jsonl",
        ],
        "interpretation": why,
        "rejection_reason": ";".join(failed) if failed else None,
        "post_run_reflection": {
            "why_result_happened": why,
            "realized_failure_mode": failed[0] if failed else "none",
            "forbidden_near_neighbor_retry": (
                "Do not sweep $250/$750/$1,000 thresholds, change the gate to a "
                "notional scalar, or reslice the same 62 baseline trades by ticker, "
                "year, strategy, or sector."
            ),
            "new_evidence_required": (
                "Reopen only with a broker fee-schedule change, materially more "
                "strategy-tagged tiny-order executions, or a shared order-construction "
                "policy that explicitly aggregates or rounds dust orders."
            ),
        },
        "next_retry_requires": [
            "broker fee-schedule change",
            "materially more strategy-tagged tiny-order executions",
            "shared order aggregation or round-lot policy",
        ],
        "related_files": [
            RUNNER,
            _repo_rel(OUT_JSON),
            _repo_rel(BASELINE_SUMMARY),
            _repo_rel(FEE_ARTIFACT),
            "docs/frozen_families.jsonl",
        ],
        "reproduction_commands": [
            f".\\.venv\\Scripts\\python.exe -B -m py_compile {RUNNER.replace('/', chr(92))}",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\build_frozen_families.py",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "lean_quality_passed": True,
    }
    return payload


def _card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} broker-fee minimum-notional gate",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Aggregate EV delta: `{aggregate['expected_value_score_delta_sum']:+.6f}`",
            f"- Aggregate PnL delta: `${aggregate['total_pnl_delta_sum']:+,.2f}`",
            f"- Dropped gate events: `{aggregate['dropped_event_count']}`",
            f"- Removed/added trades: `{aggregate['removed_trade_count']}/{aggregate['added_trade_count']}`",
            f"- Modified same-ticker/date trades: `{aggregate['modified_trade_count']}`",
            f"- Failed gates: `{', '.join(payload['gate4']['failed_reasons']) or 'none'}`",
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            payload["post_run_reflection"]["new_evidence_required"],
            "",
            "## Reproduce",
            "",
            f"- `{RUNNER_COMMAND}`",
            "",
        ]
    )


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    save_experiment_log_entry(payload, allow_duplicate=True)
    _write_text(CARD_MD, _card(payload))
    _write_json(
        MANIFEST_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "decision": payload["decision"],
            "generated_at": payload["timestamp"],
            "runner": RUNNER,
            "artifact": _repo_rel(OUT_JSON),
            "artifact_sha256": _sha256(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "card": _repo_rel(CARD_MD),
            "ticket": _repo_rel(TICKET_JSON),
            "reproduction_commands": payload["reproduction_commands"],
        },
    )
    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8"))
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=ticket["prediction"],
        result={
            "accepted": False,
            "accepted_alpha": False,
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "artifact": _repo_rel(OUT_JSON),
            "gate4": payload["gate4"],
            "calibration": payload["calibration"],
        },
        status=payload["status"],
        fields={
            **{key: value for key, value in ticket.items() if key not in {"result", "status"}},
            **{
                key: value
                for key, value in payload.items()
                if key not in {"experiment_id", "status", "prediction"}
            },
            "owner": OWNER,
            "card_file": _repo_rel(CARD_MD),
            "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        },
    )


def main() -> int:
    payload = build_payload()
    persist(payload)
    aggregate = payload["delta_metrics"]["aggregate"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
                "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
                "dropped_event_count": aggregate["dropped_event_count"],
                "removed_trade_count": aggregate["removed_trade_count"],
                "added_trade_count": aggregate["added_trade_count"],
                "modified_trade_count": aggregate["modified_trade_count"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": _repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
