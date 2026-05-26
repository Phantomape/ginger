"""exp-20260526-006: expectation revision residual-overextension attribution.

Observed-only alpha search. This experiment follows the exp-20260525-034
bucket inversion: strict PIT positive 7d EPS revision rows performed better
without residual-leader status than with it. This script keeps the same
PIT-safe watchlist input and changes one causal variable: residual state is
treated as a possible overextension classifier instead of a positive enhancer.

No entries, exits, ranking, sizing, LLM/news, paper sleeves, or orders change.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260526-006"
STEM = "expectation_revision_overextension_attribution"
MECHANISM_FAMILY = "expectation_revision"
TRIAL_FAMILY = "expectation_revision_overextension_attribution"
CHANGED_VARIABLE = "revision_residual_overextension_state_v1"

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS_DIR = Path(__file__).resolve().parent
if str(EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS_DIR))

from exp_20260525_017_expectation_residual_leadership_attribution import (  # noqa: E402
    FORWARD_HORIZONS,
    PAPER_NOTIONAL_USD,
    RESIDUAL_LEADER_STATES,
)
from exp_20260525_034_expectation_revision_watchlist_attribution import (  # noqa: E402
    build_payload as build_watchlist_payload,
    summarize_rows,
)


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
DOC_LOG = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_ARTIFACT = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
EXPERIMENT_REGISTRY = REPO_ROOT / "docs" / "experiment_registry.json"

STATE_BUCKETS = (
    "neutral_non_overextended",
    "beta_lagging_non_overextended",
    "overextended_residual_leader",
    "missing_residual_context",
)
AGGREGATE_BUCKETS = (
    "non_overextended",
    "overextended_residual_leader",
    "missing_residual_context",
)
MIN_PRIMARY_POSITIVE_ROWS = 30
MIN_GROUP_5D_OUTCOMES = 8
MIN_GROUP_10D_OUTCOMES_FOR_STRONG_READOUT = 8
MAX_TOP5_POSITIVE_SHARE = 0.60
MAX_SINGLE_TICKER_POSITIVE_SHARE = 0.50


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00",
        "Z",
    )


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, Path):
        return _repo_rel(value)
    return value


def _repo_rel(path: Path | str) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    compact = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                rows.append(line)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(compact)
                    replaced = True
                continue
            rows.append(line)
    if not replaced:
        rows.append(compact)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def classify_residual_overextension_state(row: dict[str, Any]) -> str:
    state = row.get("residual_state")
    if state in RESIDUAL_LEADER_STATES:
        return "overextended_residual_leader"
    if state == "neutral":
        return "neutral_non_overextended"
    if state == "beta_lagging":
        return "beta_lagging_non_overextended"
    return "missing_residual_context"


def classify_residual_overextension_aggregate(row: dict[str, Any]) -> str:
    bucket = classify_residual_overextension_state(row)
    if bucket in {"neutral_non_overextended", "beta_lagging_non_overextended"}:
        return "non_overextended"
    if bucket == "overextended_residual_leader":
        return bucket
    return "missing_residual_context"


def primary_positive_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        delta_7d = row.get("eps_estimate_delta_7d")
        if (
            row.get("primary_expectation_positive") is True
            and isinstance(delta_7d, (int, float))
            and delta_7d > 0
        ):
            out.append(row)
    return out


def annotate_overextension(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    annotated = []
    for row in rows:
        enriched = dict(row)
        enriched["revision_residual_overextension_state"] = (
            classify_residual_overextension_state(row)
        )
        enriched["revision_residual_overextension_aggregate"] = (
            classify_residual_overextension_aggregate(row)
        )
        annotated.append(enriched)
    return annotated


def _ticker_contribution(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(str(row.get("ticker") or "missing") for row in rows))


def build_overextension_summary(
    rows: list[dict[str, Any]],
    *,
    bucket_key: str,
    bucket_order: tuple[str, ...],
) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(bucket_key) or "missing_residual_context")].append(row)

    summary: dict[str, Any] = {}
    for bucket in bucket_order:
        bucket_rows = groups.get(bucket, [])
        summary[bucket] = {
            "row_count": len(bucket_rows),
            "ticker_count": len({row.get("ticker") for row in bucket_rows}),
            "tickers": sorted({str(row.get("ticker")) for row in bucket_rows}),
            "residual_state_breakdown": dict(
                Counter(str(row.get("residual_state") or "missing") for row in bucket_rows)
            ),
            "ticker_row_counts": _ticker_contribution(bucket_rows),
            "candidate_hit_counts": {
                "3td": sum(1 for row in bucket_rows if row.get("candidate_hit_3td")),
                "10td": sum(1 for row in bucket_rows if row.get("candidate_hit_10td")),
            },
            "horizons": {
                f"{horizon}d": summarize_rows(bucket_rows, f"{horizon}d")
                for horizon in FORWARD_HORIZONS
            },
        }
    return summary


def evaluate_overextension_gate(aggregate_summary: dict[str, Any], total_rows: int) -> dict[str, Any]:
    non = aggregate_summary["non_overextended"]
    over = aggregate_summary["overextended_residual_leader"]
    non_5d = non["horizons"]["5d"]
    over_5d = over["horizons"]["5d"]
    data_gap_reasons = []
    if total_rows < MIN_PRIMARY_POSITIVE_ROWS:
        data_gap_reasons.append("primary_positive_7d_rows")
    if non_5d["closed_outcomes"] < MIN_GROUP_5D_OUTCOMES:
        data_gap_reasons.append("non_overextended_closed_5d_outcomes")
    if over_5d["closed_outcomes"] < MIN_GROUP_5D_OUTCOMES:
        data_gap_reasons.append("overextended_closed_5d_outcomes")
    if data_gap_reasons:
        return {
            "promotion_gate_passed": False,
            "directional_passed": False,
            "decision": "observed_only_data_gap",
            "reason": "insufficient_primary_positive_or_5d_group_sample",
            "data_gap_reasons": data_gap_reasons,
            "total_primary_positive_7d_rows": total_rows,
            "minimum_primary_positive_7d_rows": MIN_PRIMARY_POSITIVE_ROWS,
            "non_overextended_closed_5d_outcomes": non_5d["closed_outcomes"],
            "overextended_closed_5d_outcomes": over_5d["closed_outcomes"],
            "minimum_group_5d_outcomes": MIN_GROUP_5D_OUTCOMES,
        }

    comparisons = []
    directional_passed = True
    for horizon in ("5d", "10d"):
        non_h = non["horizons"][horizon]
        over_h = over["horizons"][horizon]
        passed = (
            non_h["avg_return"] is not None
            and over_h["avg_return"] is not None
            and non_h["avg_return"] > over_h["avg_return"]
        )
        comparisons.append(
            {
                "horizon": horizon,
                "non_overextended_avg_return": non_h["avg_return"],
                "overextended_residual_leader_avg_return": over_h["avg_return"],
                "non_overextended_closed_outcomes": non_h["closed_outcomes"],
                "overextended_closed_outcomes": over_h["closed_outcomes"],
                "passed": passed,
            }
        )
        directional_passed = directional_passed and passed

    concentration = {
        "top5_positive_contribution_share": non_5d["top5_positive_contribution_share"],
        "max_single_ticker_positive_share": non_5d["max_single_ticker_positive_share"],
        "top5_positive_contribution_guardrail": MAX_TOP5_POSITIVE_SHARE,
        "max_single_ticker_positive_guardrail": MAX_SINGLE_TICKER_POSITIVE_SHARE,
    }
    concentration["passed"] = (
        concentration["top5_positive_contribution_share"] is not None
        and concentration["max_single_ticker_positive_share"] is not None
        and concentration["top5_positive_contribution_share"] <= MAX_TOP5_POSITIVE_SHARE
        and concentration["max_single_ticker_positive_share"] <= MAX_SINGLE_TICKER_POSITIVE_SHARE
    )

    warnings = []
    for group_name, group in (
        ("non_overextended", non),
        ("overextended_residual_leader", over),
    ):
        if group["horizons"]["10d"]["closed_outcomes"] < MIN_GROUP_10D_OUTCOMES_FOR_STRONG_READOUT:
            warnings.append(f"{group_name}_10d_closed_outcomes_thin")
        if group["horizons"]["20d"]["closed_outcomes"] == 0:
            warnings.append(f"{group_name}_20d_no_closed_outcomes")

    promotion_gate_passed = bool(directional_passed and concentration["passed"])
    if promotion_gate_passed:
        decision = "observed_only_promising_overextension_guard"
        reason = "non_overextended_beats_residual_leader_and_passes_concentration"
    elif directional_passed:
        decision = "observed_only_promising_but_concentration_or_maturity_blocked"
        reason = "directional_readout_positive_but_not_promotable"
    else:
        decision = "rejected_revision_overextension_guard"
        reason = "non_overextended_did_not_beat_residual_leader_on_5d_and_10d"

    return {
        "promotion_gate_passed": promotion_gate_passed,
        "directional_passed": directional_passed,
        "decision": decision,
        "reason": reason,
        "comparisons": comparisons,
        "concentration": concentration,
        "warnings": warnings,
        "total_primary_positive_7d_rows": total_rows,
        "non_overextended_closed_5d_outcomes": non_5d["closed_outcomes"],
        "overextended_closed_5d_outcomes": over_5d["closed_outcomes"],
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Expectation Revision Overextension Attribution",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Observed-only alpha search. No entries, exits, ranking, sizing, paper sleeves, LLM/news, or orders changed.",
        "",
        "## Coverage",
        "",
        "```json",
        json.dumps(payload["coverage"], indent=2, sort_keys=True),
        "```",
        "",
        "## Aggregate Buckets",
        "",
        "| Bucket | Rows | 5d Closed | 5d Avg Return | 10d Closed | 10d Avg Return | 20d Closed | 20d Avg Return |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for bucket, row in payload["aggregate_summary"].items():
        h5 = row["horizons"]["5d"]
        h10 = row["horizons"]["10d"]
        h20 = row["horizons"]["20d"]
        lines.append(
            "| {bucket} | {rows} | {h5_count} | {h5_avg} | {h10_count} | {h10_avg} | {h20_count} | {h20_avg} |".format(
                bucket=bucket,
                rows=row["row_count"],
                h5_count=h5["closed_outcomes"],
                h5_avg="" if h5["avg_return"] is None else f"{h5['avg_return']:.4%}",
                h10_count=h10["closed_outcomes"],
                h10_avg="" if h10["avg_return"] is None else f"{h10['avg_return']:.4%}",
                h20_count=h20["closed_outcomes"],
                h20_avg="" if h20["avg_return"] is None else f"{h20['avg_return']:.4%}",
            )
        )
    lines.extend(
        [
            "",
            "## State Buckets",
            "",
            "| Bucket | Rows | 5d Closed | 5d Avg Return | 10d Closed | 10d Avg Return |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for bucket, row in payload["state_summary"].items():
        h5 = row["horizons"]["5d"]
        h10 = row["horizons"]["10d"]
        lines.append(
            "| {bucket} | {rows} | {h5_count} | {h5_avg} | {h10_count} | {h10_avg} |".format(
                bucket=bucket,
                rows=row["row_count"],
                h5_count=h5["closed_outcomes"],
                h5_avg="" if h5["avg_return"] is None else f"{h5['avg_return']:.4%}",
                h10_count=h10["closed_outcomes"],
                h10_avg="" if h10["avg_return"] is None else f"{h10['avg_return']:.4%}",
            )
        )
    lines.extend(
        [
            "",
            "## Gate",
            "",
            "```json",
            json.dumps(payload["gate"], indent=2, sort_keys=True),
            "```",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def build_payload(data_dir: Path | None = None) -> dict[str, Any]:
    timestamp = _utc_now()
    watchlist_payload = build_watchlist_payload(data_dir)
    source_rows = watchlist_payload.get("annotated_watchlist_rows") or []
    primary_rows = annotate_overextension(primary_positive_rows(source_rows))
    state_summary = build_overextension_summary(
        primary_rows,
        bucket_key="revision_residual_overextension_state",
        bucket_order=STATE_BUCKETS,
    )
    aggregate_summary = build_overextension_summary(
        primary_rows,
        bucket_key="revision_residual_overextension_aggregate",
        bucket_order=AGGREGATE_BUCKETS,
    )
    gate = evaluate_overextension_gate(aggregate_summary, len(primary_rows))
    status = "observed_only_data_gap" if gate["decision"] == "observed_only_data_gap" else (
        "observed_only" if gate["directional_passed"] else "rejected"
    )
    related_files = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(DOC_LOG),
        _repo_rel(DOC_TICKET),
        _repo_rel(DOC_ARTIFACT),
        _repo_rel(EXPERIMENT_LOG_JSONL),
        _repo_rel(EXPERIMENT_REGISTRY),
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": gate["decision"],
        "lane": "alpha_search",
        "hypothesis": (
            "Strict PIT positive 7d EPS revision rows may have better forward "
            "returns when residual strength is neutral or beta-lagging, while "
            "residual-leader status may indicate extension/overheating instead "
            "of confirmation."
        ),
        "change_summary": (
            "Read-only attribution over exp-20260525-034 PIT-safe primary "
            "positive revision rows. The only changed variable is residual "
            "overextension state."
        ),
        "change_type": "observed_only_revision_overextension_attribution",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": "primary_positive_7d_non_overextended_vs_residual_leader",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "prior_trial_count": 4,
        "nearby_prior_experiments": [
            "exp-20260525-017",
            "exp-20260525-021",
            "exp-20260525-031",
            "exp-20260525-034",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "exp-20260525-034_bucket_inversion",
        "component": "quant/experiments/exp_20260526_006_expectation_revision_overextension_attribution.py",
        "parameters": {
            "source_experiment": "exp-20260525-034",
            "primary_positive_expectation_definition": "estimate_revision_usable && eps_estimate_delta_7d > 0",
            "state_bucket_key": "revision_residual_overextension_state",
            "aggregate_bucket_key": "revision_residual_overextension_aggregate",
            "non_overextended_states": [
                "neutral",
                "beta_lagging",
            ],
            "overextended_states": sorted(RESIDUAL_LEADER_STATES),
            "forward_horizons": list(FORWARD_HORIZONS),
            "paper_notional_usd": PAPER_NOTIONAL_USD,
            "gate_thresholds": {
                "min_primary_positive_rows": MIN_PRIMARY_POSITIVE_ROWS,
                "min_group_5d_outcomes": MIN_GROUP_5D_OUTCOMES,
                "min_group_10d_outcomes_for_strong_readout": MIN_GROUP_10D_OUTCOMES_FOR_STRONG_READOUT,
                "max_top5_positive_share": MAX_TOP5_POSITIVE_SHARE,
                "max_single_ticker_positive_share": MAX_SINGLE_TICKER_POSITIVE_SHARE,
            },
            "anti_js": "No JavaScript was used.",
        },
        "date_range": watchlist_payload.get("date_range"),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "ranking/candidate-pool research: positive estimate revisions "
                "may be useful before the name is already a residual leader; "
                "residual leadership may mark overextension."
            ),
            "2_history_check": (
                "exp-20260525-034 found Bucket A positive revision plus residual "
                "leader underperformed positive revision only on 5d and 10d; "
                "exp-20260525-017/031 showed candidate-only samples were sparse."
            ),
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Observed-only: non-overextended primary positive 7d rows beat "
                "residual-leader primary positive 7d rows on closed 5d and 10d "
                "average returns, while sample size and concentration are reported."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260526_006_expectation_revision_overextension_attribution.py"
            ),
        },
        "gate1": {
            "passed": True,
            "baseline_protocol": "docs/backtesting.md canonical three fixed windows",
            "baseline_artifact": "data/experiments/exp-20260517-009/",
            "accepted_core_expected_value_score_sum": 7.8941,
            "accepted_core_total_pnl_sum": 234850.99,
            "note": "Read-only attribution; no before/after strategy behavior changes.",
        },
        "gate2": {
            "passed": True,
            "source_gate2": watchlist_payload.get("gate2"),
            "rule_dependencies": [
                "exp-20260525-034 PIT-safe annotated watchlist rows",
                "eps_estimate_delta_7d primary positive flag",
                "residual_state from OHLCV feature context",
                "forward_outcomes from local OHLCV price lookup",
            ],
        },
        "gate3": {
            "adds_filter": False,
            "candidate_pool_changed": False,
            "survival_rate_not_applicable": True,
            "passed": True,
        },
        "gate4": {
            "strategy_behavior_changed": False,
            "canonical_backtest_required": False,
            "passed": False,
            "note": "A passing observed-only readout can only unlock a later default-off paper sleeve or ranking-component Gate 1-4 test.",
        },
        "coverage": {
            "source_experiment_id": watchlist_payload.get("experiment_id"),
            "source_decision": watchlist_payload.get("decision"),
            **(watchlist_payload.get("coverage") or {}),
            "primary_rows_used_in_this_experiment": len(primary_rows),
            "state_bucket_counts": dict(
                Counter(row["revision_residual_overextension_state"] for row in primary_rows)
            ),
            "aggregate_bucket_counts": dict(
                Counter(row["revision_residual_overextension_aggregate"] for row in primary_rows)
            ),
        },
        "state_summary": state_summary,
        "aggregate_summary": aggregate_summary,
        "gate": gate,
        "sample_primary_positive_rows": primary_rows[:80],
        "before_metrics": {
            "accepted_core_expected_value_score_sum": 7.8941,
            "accepted_core_total_pnl_sum": 234850.99,
            "strategy_behavior_changed": False,
        },
        "after_metrics": {
            "accepted_core_expected_value_score_sum": 7.8941,
            "accepted_core_total_pnl_sum": 234850.99,
            "strategy_behavior_changed": False,
            "primary_positive_7d_rows": len(primary_rows),
            "non_overextended_rows": aggregate_summary["non_overextended"]["row_count"],
            "overextended_residual_leader_rows": aggregate_summary["overextended_residual_leader"]["row_count"],
        },
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_sum_delta": 0.0,
            "strategy_behavior_delta": 0,
        },
        "expected_value_score_delta": 0.0,
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "observed_only_attribution": True,
            "parity_test_added": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "trade_enabled": False,
        },
        "interpretation": (
            "This tests whether residual leadership should be treated as an "
            "overextension/risk-state modifier for positive EPS revision rows. "
            "It does not promote live logic."
        ),
        "rejection_reason": None
        if gate["directional_passed"]
        else "non-overextended positive revision rows did not beat residual-leader rows on 5d and 10d",
        "next_evidence_needed": (
            "If the directional readout persists, add a forward default-off "
            "watchlist/paper sleeve that tracks positive 7d revisions in "
            "neutral or beta-lagging residual states, then require closed "
            "replacement-value and concentration evidence before any ranking change."
        ),
        "related_files": related_files,
        "anti_js": "No JavaScript was used.",
    }


def _experiment_log_entry(payload: dict[str, Any]) -> dict[str, Any]:
    keep_keys = (
        "experiment_id",
        "timestamp",
        "status",
        "hypothesis",
        "change_summary",
        "change_type",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "changed_variable",
        "prior_trial_count",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "component",
        "parameters",
        "date_range",
        "gate_questions",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "coverage",
        "state_summary",
        "aggregate_summary",
        "gate",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "expected_value_score_delta",
        "llm_metrics",
        "production_impact",
        "decision",
        "rejection_reason",
        "next_evidence_needed",
        "related_files",
        "anti_js",
    )
    return {key: payload[key] for key in keep_keys}


def _upsert_registry(payload: dict[str, Any]) -> None:
    if not EXPERIMENT_REGISTRY.exists():
        return
    registry = json.loads(EXPERIMENT_REGISTRY.read_text(encoding="utf-8"))
    entry = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "lane": "alpha_discovery",
        "owner": "codex-expectation-revision",
        "hypothesis": payload["hypothesis"],
        "ticket_file": _repo_rel(DOC_TICKET),
        "log_file": _repo_rel(DOC_LOG),
        "updated_at": payload["timestamp"],
        "result": {
            "decision": payload["decision"],
            "artifact": _repo_rel(DOC_ARTIFACT),
            "json": _repo_rel(OUT_JSON),
            "summary": payload["gate"]["reason"],
        },
    }
    experiments = registry.setdefault("experiments", [])
    for idx, row in enumerate(experiments):
        if row.get("experiment_id") == EXPERIMENT_ID:
            experiments[idx] = {**row, **entry}
            break
    else:
        experiments.append(entry)
    registry["updated_at"] = payload["timestamp"]
    EXPERIMENT_REGISTRY.write_text(
        json.dumps(_safe(registry), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(DOC_LOG, payload)
    _write_json(
        DOC_TICKET,
        {
            "experiment_id": EXPERIMENT_ID,
            "lane": "alpha_search",
            "owner": "codex-expectation-revision",
            "status": payload["status"],
            "decision": payload["decision"],
            "single_causal_variable": CHANGED_VARIABLE,
            "artifact_file": _repo_rel(OUT_JSON),
            "result_file": _repo_rel(DOC_LOG),
            "updated_at": payload["timestamp"],
        },
    )
    DOC_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT.write_text(_artifact_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG_JSONL, _experiment_log_entry(payload))
    _upsert_registry(payload)


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "status": payload["status"],
                    "decision": payload["decision"],
                    "coverage": payload["coverage"],
                    "aggregate_summary": payload["aggregate_summary"],
                    "gate": payload["gate"],
                    "output": _repo_rel(OUT_JSON),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
