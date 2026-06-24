"""exp-20260623-025: shared-adapter screen for the non-OHLCV confluence lead.

This is a pre-implementation Gate 4 check for promoting exp-20260623-024's
observed-only Form 4 plus SEC filing confluence lead into a shared default-off
paper adapter. It intentionally changes no shared helper, daily snapshot,
ranking, sizing, exit, ledger, or order path because the fixed lead already
fails the accepted distribution-day comparator on existing evidence.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, QUANT_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260623-025"
SLUG = "non_ohlcv_confluence_shared_adapter"
RUNNER = f"quant/experiments/exp_20260623_025_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
OWNER = "alpha-explore"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260623_025_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
PRIOR_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260623-024"
    / "exp_20260623_024_non_ohlcv_attention_confluence.json"
)

HYPOTHESIS = (
    "Shared-paper-first candidate_pool: the fixed same usable-trade-date Form 4 "
    "plus SEC filing event/text confluence lead from exp-20260623-024 should "
    "reproduce through a shared historical replay and daily default-off "
    "snapshot helper without changing live orders, ranking, sizing, or exits."
)
CHANGE_TYPE = "candidate_pool_full_stack"
MECHANISM_FAMILY = "candidate_pool_full_stack"
TRIAL_FAMILY = "non_ohlcv_cross_source_attention_confluence_shared_default_off_adapter"
TRIAL_VARIANT_ID = "non_ohlcv_cross_source_attention_confluence_shared_default_off_adapter_v1"
CHANGED_VARIABLE = "non_ohlcv_cross_source_attention_confluence_shared_default_off_adapter_v1"
NEW_EVIDENCE_TYPE = "shared_adapter_promotion_screen"
NEW_EVIDENCE_AXIS = (
    "New gate shape: promote exp-20260623-024 from observed-only attribution "
    "into a shared historical replay plus daily default-off snapshot helper "
    "with fixed parameters and parity coverage; no Form4/SEC threshold sweep."
)
NEARBY_PRIOR_EXPERIMENTS = ["exp-20260623-024"]
CAUSAL_COMPONENTS = [
    "shared helper promotion screen",
    "accepted comparator check",
    "execution envelope",
    "full-stack verdict",
]
ALLOWED_WRITE_SCOPE = [
    "quant/non_ohlcv_attention_confluence_paper_sleeve.py",
    "quant/test_non_ohlcv_attention_confluence_paper_sleeve.py",
    "quant/run.py",
    "quant/default_off_alpha_attribution.py",
    RUNNER,
    "data/experiments/exp-20260623-025/exp_20260623_025_non_ohlcv_confluence_shared_adapter.json",
    "experiments/cards/exp-20260623-025.md",
    "experiments/manifests/exp-20260623-025.json",
    "experiments/tickets/exp-20260623-025.json",
    "experiments/logs/exp-20260623-025.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]

ACCEPTED_COMPARATORS = {
    "compression_shared_adapter": {
        "experiment_id": "exp-20260608-013",
        "expected_value_delta": 0.1608,
        "total_pnl_delta": 2248.98,
        "source": "experiments/cards/exp-20260608-013.md",
    },
    "distribution_day_shared_adapter": {
        "experiment_id": "exp-20260611-007",
        "expected_value_delta": 0.5286,
        "total_pnl_delta": 10432.91,
        "source": "experiments/cards/exp-20260611-007.md",
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def repo_rel(path: Path | str) -> str:
    path = Path(path)
    if not path.is_absolute():
        path = REPO_ROOT / path
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: list[dict[str, Any]] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if item.get("experiment_id") != record.get("experiment_id"):
                existing.append(item)
    existing.append(record)
    with path.open("w", encoding="utf-8") as handle:
        for item in existing:
            handle.write(json.dumps(item, sort_keys=True) + "\n")


def metric(source: dict[str, Any], *keys: str, default: Any = None) -> Any:
    cur: Any = source
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def build_payload() -> dict[str, Any]:
    prior = load_json(PRIOR_ARTIFACT)
    baseline = load_json(BASELINE_RESULT)
    confluence = metric(
        prior,
        "attribution",
        "analysis",
        "by_bucket",
        "confluence",
        default={},
    )
    gate2 = prior.get("gate2", {})
    gate3 = prior.get("gate3", {})

    confluence_pnl = float(confluence.get("total_replacement_value_vs_cash_usd", 0.0))
    confluence_spy = float(confluence.get("total_replacement_value_vs_spy_usd", 0.0))
    confluence_qqq = float(confluence.get("total_replacement_value_vs_qqq_usd", 0.0))
    distribution_pnl = ACCEPTED_COMPARATORS["distribution_day_shared_adapter"]["total_pnl_delta"]
    compression_pnl = ACCEPTED_COMPARATORS["compression_shared_adapter"]["total_pnl_delta"]
    pnl_gap_to_distribution = round(confluence_pnl - distribution_pnl, 2)

    failed_reasons = []
    if confluence_pnl <= distribution_pnl:
        failed_reasons.append("accepted_distribution_pnl_comparator_not_beaten")
    if confluence_pnl <= compression_pnl:
        failed_reasons.append("accepted_compression_pnl_comparator_not_beaten")
    if not prior.get("observed_only_lead"):
        failed_reasons.append("prior_observed_only_lead_missing")
    if not gate2.get("dependencies_validated"):
        failed_reasons.append("prior_gate2_dependencies_not_validated")
    if float(gate3.get("survival_rate", 0.0)) < 0.05:
        failed_reasons.append("prior_survival_rate_below_5pct")

    decision = "rejected_preimplementation_accepted_distribution_comparator_not_beaten"
    status = "rejected"
    timestamp = utc_now()
    source_audit = gate2.get("source_audit", {})

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "owner": OWNER,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": False,
        "prior_observed_only_lead": bool(prior.get("observed_only_lead")),
        "implementation_mode": "preimplementation_shared_adapter_gate4_screen",
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "multiple_testing_risk_bucket": "minimal",
        "prediction": {
            "recorded_at": "2026-06-23T21:02:58+00:00",
            "success_probability": 0.28,
            "expected_ev_delta": None,
            "expected_pnl_delta": None,
            "main_failure_modes": [
                "observed_only_lead_not_reproduced",
                "daily_path_missing_source_rows",
                "parity_mismatch",
                "accepted_comparator_not_beaten",
            ],
            "confidence_reason": (
                "exp-20260623-024 found a fixed cross-source non-OHLCV "
                "confluence lead with 30 outcome rows, 21 tickers, positive "
                "cash/SPY/QQQ replacement value in all three windows, and no "
                "concentration failure. The risk is that the lead remains too "
                "small versus accepted comparators."
            ),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": (
                "Reservation novelty gate allowed this only as a shared-adapter "
                "promotion screen for exp-20260623-024; no Form4/SEC threshold "
                "sweep is tested."
            ),
            "3_single_policy_bundle": (
                "Fixed same usable-trade-date Form4 plus SEC event/text "
                "confluence with exp024's fixed price/liquidity confirmation."
            ),
            "4_success_failure_standard": (
                "A shared adapter is worth implementation only if the fixed lead "
                "can beat accepted candidate-pool comparators before adding any "
                "new shared strategy surface."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "prior_artifact": repo_rel(PRIOR_ARTIFACT),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "fixed_policy_source": "exp-20260623-024",
            "accepted_comparators": ACCEPTED_COMPARATORS,
            "no_threshold_sweep": True,
            "preimplementation_rejection_rule": (
                "Do not implement a shared default-off adapter when the fixed "
                "source's aggregate cash replacement value is already below the "
                "current accepted distribution-day candidate-pool comparator."
            ),
        },
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "baseline_total_pnl": metric(baseline, "after_metrics", "total_pnl"),
            "baseline_expected_value_score_sum": metric(
                baseline, "after_metrics", "expected_value_score_sum"
            ),
            "source": "canonical standard-window baseline from docs/backtesting.md",
        },
        "gate2": {
            "dependencies_validated": bool(gate2.get("dependencies_validated")),
            "entry_date_present": bool(gate2.get("entry_date_present")),
            "target_price_present": bool(gate2.get("target_price_present")),
            "fields_checked": gate2.get("fields_checked", []),
            "source_ticker_date_rows": gate2.get("source_ticker_date_rows"),
            "outcome_rows": gate2.get("outcome_rows"),
            "source_files": source_audit.get("source_files", {}),
        },
        "gate3": {
            "signals_generated": gate3.get("signals_generated"),
            "signals_survived": gate3.get("signals_survived"),
            "survival_rate": gate3.get("survival_rate"),
            "baseline_survival_rate": gate3.get("baseline_survival_rate"),
            "passed_minimum_survival": float(gate3.get("survival_rate", 0.0)) >= 0.05,
        },
        "gate4": {
            "decision": decision,
            "accepted": False,
            "preimplementation_screen": True,
            "strategy_rerun_required": False,
            "shared_adapter_implemented": False,
            "failed_reasons": failed_reasons,
            "confluence_replacement_value_vs_cash_usd": confluence_pnl,
            "confluence_replacement_value_vs_spy_usd": confluence_spy,
            "confluence_replacement_value_vs_qqq_usd": confluence_qqq,
            "accepted_comparators": ACCEPTED_COMPARATORS,
            "comparator_checks": {
                "beats_compression_pnl": confluence_pnl > compression_pnl,
                "beats_distribution_pnl": confluence_pnl > distribution_pnl,
                "pnl_gap_to_distribution_usd": pnl_gap_to_distribution,
                "distribution_comparator_required": True,
            },
            "reasoning": (
                "The fixed confluence lead is positive and beats the older "
                "compression PnL comparator, but it is less than one quarter of "
                "the accepted distribution-day shared adapter PnL delta. Adding "
                "a shared helper would create production-visible strategy "
                "surface without a credible accepted-comparator path."
            ),
        },
        "analysis": {
            "prior_exp024_confluence": confluence,
            "prior_window_confluence": metric(
                prior,
                "gate4",
                "acceptance_checks",
                "per_window_confluence",
                default={},
            ),
            "source_summary": {
                "source_ticker_date_rows": gate2.get("source_ticker_date_rows"),
                "outcome_rows": gate2.get("outcome_rows"),
                "confluence_rows": confluence.get("n"),
                "confluence_distinct_tickers": confluence.get("distinct_tickers"),
                "max_single_ticker_row_share": confluence.get(
                    "max_single_ticker_row_share"
                ),
            },
            "promotion_screen": {
                "fixed_lead_total_cash_replacement_usd": confluence_pnl,
                "accepted_distribution_pnl_delta_usd": distribution_pnl,
                "gap_to_distribution_usd": pnl_gap_to_distribution,
                "promotion_worth_implementing": False,
            },
        },
        "production_impact": {
            "shared_helper_promoted": False,
            "daily_snapshot_exposed": False,
            "trade_enabled": False,
            "paper_orders_changed": False,
            "live_orders_changed": False,
            "entry_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_rules_changed": False,
            "uses_non_ohlcv_sources": True,
            "live_realistic_execution_envelope": (
                "Not live-ready and not promoted. The inherited diagnostic "
                "envelope is $4,000 paper notional, price >= $10, ADV20 >= "
                "$50M, next-open paper entry, 10-trading-day close exit, shared "
                "slippage/cost conventions, and no capital cap, order semantics, "
                "kill switch, or displacement path."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The exp024 confluence lead is directionally positive but too "
                "small to justify shared adapter work: $2,439.01 cash "
                "replacement value versus $10,432.91 for the current accepted "
                "distribution-day shared adapter."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry by sweeping Form4 transaction code, SEC form type, "
                "close-location, ADV, same-day return, hold-day, notional, "
                "top-N, cooldown, or benchmark thresholds on the same archived "
                "sources."
            ),
            "new_evidence_required": (
                "A valid retry needs a materially new evidence axis such as "
                "parsed filing surprise semantics, named customer/supplier "
                "entities, borrow/options structure joined to the same events, "
                "or closed forward replacement rows from a shared helper built "
                "for a stronger source."
            ),
        },
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "related_files": [
            RUNNER,
            repo_rel(PRIOR_ARTIFACT),
            repo_rel(BASELINE_RESULT),
            "experiments/cards/exp-20260608-013.md",
            "experiments/cards/exp-20260611-007.md",
            "docs/backtesting.md",
            "docs/production_backtest_parity.md",
        ],
        "changed_files_expected": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
        ],
    }
    return payload


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "owner": OWNER,
        "lane": payload["lane"],
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "hypothesis": payload["hypothesis"],
        "changed_variable": payload["changed_variable"],
        "single_causal_variable": payload["single_causal_variable"],
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "artifact": repo_rel(OUT_JSON),
        "runner": RUNNER,
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "prediction": payload["prediction"],
    }


def build_card(payload: dict[str, Any]) -> str:
    gate4 = payload["gate4"]
    checks = gate4["comparator_checks"]
    lines = [
        f"# {EXPERIMENT_ID} Non-OHLCV Confluence Shared Adapter Screen",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Gate 4",
        "",
        f"- Exp024 confluence cash replacement: `${gate4['confluence_replacement_value_vs_cash_usd']:,.2f}`",
        f"- Accepted compression comparator PnL: `${ACCEPTED_COMPARATORS['compression_shared_adapter']['total_pnl_delta']:,.2f}`",
        f"- Accepted distribution comparator PnL: `${ACCEPTED_COMPARATORS['distribution_day_shared_adapter']['total_pnl_delta']:,.2f}`",
        f"- Beats compression PnL: `{checks['beats_compression_pnl']}`",
        f"- Beats distribution PnL: `{checks['beats_distribution_pnl']}`",
        f"- Failed reasons: `{', '.join(gate4['failed_reasons'])}`",
        "",
        "## Production Impact",
        "",
        "- Shared helper promoted: `false`",
        "- Daily snapshot exposed: `false`",
        "- Live/default orders changed: `false`",
        "",
        "## Reflection",
        "",
        payload["post_run_reflection"]["why_result_happened"],
        "",
        payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
        "",
        "No JavaScript was used.",
    ]
    return "\n".join(lines) + "\n"


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        PRIOR_ARTIFACT,
        BASELINE_RESULT,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)} for path in files},
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)

    registry_result = {
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": False,
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "gate4": payload["gate4"],
        "analysis": payload["analysis"]["promotion_screen"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result=registry_result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "change_type": payload["change_type"],
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": payload["single_causal_variable"],
            "changed_variable": payload["changed_variable"],
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "new_evidence_axis": payload["new_evidence_axis"],
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "allowed_write_scope": ALLOWED_WRITE_SCOPE,
            "related_files": payload["related_files"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "confluence_cash_replacement_usd": payload["gate4"][
                    "confluence_replacement_value_vs_cash_usd"
                ],
                "accepted_distribution_pnl_delta_usd": ACCEPTED_COMPARATORS[
                    "distribution_day_shared_adapter"
                ]["total_pnl_delta"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "shared_helper_promoted": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
