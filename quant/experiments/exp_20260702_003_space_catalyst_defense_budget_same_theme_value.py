"""Observed-only Space Catalyst semantic-bucket replacement-value test.

Experiment exp-20260702-003 asks whether the official defense-budget Space
Catalyst rows still carry candidate-pool value after charging the same-theme
opportunity cost. The runner does not change shared policy, rankings, orders,
sizing, or exits.
"""

from __future__ import annotations

import hashlib
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260702-003"
OWNER = "codex-alpha-explore"
LANE = "alpha_search"
RUNNER = (
    "quant/experiments/"
    "exp_20260702_003_space_catalyst_defense_budget_same_theme_value.py"
)
RUNNER_COMMAND = (
    ".\\.venv\\Scripts\\python.exe -B "
    "quant\\experiments\\exp_20260702_003_space_catalyst_defense_budget_same_theme_value.py"
)

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.experiment_registry import persist_self_registered_result

BASELINE_RESULT = (
    REPO_ROOT
    / "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
LEDGER_JSONL = REPO_ROOT / "data/paper_sleeves/space_catalyst/event_state_shadow_ledger.jsonl"
SUMMARY_JSON = REPO_ROOT / "data/paper_sleeves/space_catalyst/event_state_shadow_summary.json"
OUT_JSON = (
    REPO_ROOT
    / "data/experiments/exp-20260702-003/"
    "exp_20260702_003_space_catalyst_defense_budget_same_theme_value.json"
)
LOG_JSON = REPO_ROOT / "experiments/logs/exp-20260702-003.json"
CARD_MD = REPO_ROOT / "experiments/cards/exp-20260702-003.md"
MANIFEST_JSON = REPO_ROOT / "experiments/manifests/exp-20260702-003.json"
TICKET_JSON = REPO_ROOT / "experiments/tickets/exp-20260702-003.json"
REGISTRY_JSON = REPO_ROOT / "docs/experiment_registry.json"

HORIZONS = ("10d", "20d")
METRICS = {
    "cash_pnl": "cash_relative_pnl",
    "spy_relative": "spy_relative_value",
    "qqq_relative": "qqq_relative_value",
    "arkx_relative": "arkx_relative_value",
    "ufo_relative": "ufo_relative_value",
    "same_theme": "same_theme_replacement_value",
}

HYPOTHESIS = (
    "Space Catalyst official defense-budget/government-award event rows may "
    "contain candidate-pool alpha only if their 10d/20d forward replacement "
    "value remains positive versus same-theme alternatives, not just cash and "
    "broad ETFs."
)
SINGLE_CAUSAL_VARIABLE = (
    "candidate_pool: require semantic_bucket=defense_budget_theme for Space "
    "Catalyst candidates only if same-theme replacement value is positive "
    "across mature 10d/20d rows"
)
CAUSAL_COMPONENTS = [
    "semantic_bucket",
    "forward_replacement_value",
    "same_theme_benchmark",
]
PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "same_theme_opportunity_cost_negative",
        "sample_too_thin",
        "theme_beta_confound",
        "attention_only_confound",
    ],
    "confidence_reason": (
        "Prior repaired Space event-state shadow summary showed positive broad "
        "10d returns but failed same-theme replacement; this experiment tests "
        "the specific machine-checkable semantic bucket gate before any helper "
        "or order change."
    ),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def numeric(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "avg": None,
            "median": None,
            "win_rate": None,
            "min": None,
            "max": None,
            "total": None,
            "positive_count": 0,
        }
    positive_count = sum(1 for value in values if value > 0)
    return {
        "count": len(values),
        "avg": round(sum(values) / len(values), 6),
        "median": round(statistics.median(values), 6),
        "win_rate": round(positive_count / len(values), 6),
        "min": round(min(values), 6),
        "max": round(max(values), 6),
        "total": round(sum(values), 6),
        "positive_count": positive_count,
    }


def summarize_baseline(path: Path) -> dict[str, Any]:
    raw = read_json(path)
    windows = raw.get("windows") or []
    signals_generated = sum(int(w.get("signals_generated") or 0) for w in windows)
    signals_survived = sum(int(w.get("signals_survived") or 0) for w in windows)
    return {
        "path": repo_rel(path),
        "window_count": len(windows),
        "aggregate_expected_value_score": round(
            sum(float(w.get("expected_value_score") or 0.0) for w in windows), 6
        ),
        "aggregate_strategy_total_pnl": round(
            sum(float(w.get("total_pnl") or 0.0) for w in windows), 6
        ),
        "max_window_drawdown_pct": max(
            (float(w.get("max_drawdown_pct") or 0.0) for w in windows),
            default=0.0,
        ),
        "trade_count": sum(int(w.get("trade_count") or 0) for w in windows),
        "signals_generated": signals_generated,
        "signals_survived": signals_survived,
        "survival_rate": (
            round(signals_survived / signals_generated, 6)
            if signals_generated
            else None
        ),
        "windows": [
            {
                "label": w.get("label"),
                "expected_value_score": w.get("expected_value_score"),
                "total_pnl": w.get("total_pnl"),
                "max_drawdown_pct": w.get("max_drawdown_pct"),
                "trade_count": w.get("trade_count"),
                "survival_rate": w.get("survival_rate"),
            }
            for w in windows
        ],
    }


def load_latest_space_rows(path: Path) -> list[dict[str, Any]]:
    latest: dict[tuple[Any, Any, Any], dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            key = (row.get("event_id"), row.get("ticker"), row.get("entry_date"))
            prior = latest.get(key)
            if prior is None:
                latest[key] = row
                continue
            prior_sort = (prior.get("asof_date") or "", prior.get("logged_at") or "")
            row_sort = (row.get("asof_date") or "", row.get("logged_at") or "")
            if row_sort >= prior_sort:
                latest[key] = row
    return sorted(
        latest.values(),
        key=lambda row: (
            row.get("entry_date") or "",
            row.get("event_id") or "",
            row.get("ticker") or "",
        ),
    )


def mature_values(
    rows: list[dict[str, Any]], horizon: str, metric_key: str
) -> list[float]:
    values: list[float] = []
    for row in rows:
        horizon_row = (row.get("horizons") or {}).get(horizon) or {}
        if horizon_row.get("status") != "mature":
            continue
        value = numeric(horizon_row.get(metric_key))
        if value is not None:
            values.append(value)
    return values


def summarize_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_horizon: dict[str, dict[str, Any]] = {}
    for horizon in HORIZONS:
        by_horizon[horizon] = {
            label: stats(mature_values(rows, horizon, metric_key))
            for label, metric_key in METRICS.items()
        }
    return {
        "row_count": len(rows),
        "event_count": len({row.get("event_id") for row in rows}),
        "ticker_count": len({row.get("ticker") for row in rows}),
        "tickers": sorted({row.get("ticker") for row in rows if row.get("ticker")}),
        "by_horizon": by_horizon,
    }


def build_gate4(group_summary: dict[str, Any]) -> dict[str, Any]:
    defense = group_summary["by_semantic_bucket"].get("defense_budget_theme") or {}
    defense_10d = (defense.get("by_horizon") or {}).get("10d") or {}
    defense_20d = (defense.get("by_horizon") or {}).get("20d") or {}

    def metric(horizon_stats: dict[str, Any], metric_name: str, field: str) -> Any:
        return ((horizon_stats.get(metric_name) or {}).get(field))

    checks = {
        "minimum_total_closed_rows": group_summary["all_closed"]["row_count"] >= 12,
        "minimum_defense_rows": defense.get("row_count", 0) >= 8,
        "defense_10d_broad_avg_positive": all(
            (metric(defense_10d, name, "avg") or 0.0) > 0.0
            for name in ("cash_pnl", "spy_relative", "qqq_relative", "arkx_relative", "ufo_relative")
        ),
        "defense_20d_broad_avg_positive": all(
            (metric(defense_20d, name, "avg") or 0.0) > 0.0
            for name in ("cash_pnl", "spy_relative", "qqq_relative", "arkx_relative", "ufo_relative")
        ),
        "defense_10d_same_theme_avg_positive": (
            (metric(defense_10d, "same_theme", "avg") or 0.0) > 0.0
        ),
        "defense_10d_same_theme_median_positive": (
            (metric(defense_10d, "same_theme", "median") or 0.0) > 0.0
        ),
        "defense_10d_same_theme_win_rate_above_half": (
            (metric(defense_10d, "same_theme", "win_rate") or 0.0) > 0.5
        ),
        "defense_20d_same_theme_avg_positive": (
            (metric(defense_20d, "same_theme", "avg") or 0.0) > 0.0
        ),
        "defense_20d_same_theme_median_positive": (
            (metric(defense_20d, "same_theme", "median") or 0.0) > 0.0
        ),
        "defense_20d_same_theme_win_rate_above_half": (
            (metric(defense_20d, "same_theme", "win_rate") or 0.0) > 0.5
        ),
    }
    failed_reasons = [name for name, passed in checks.items() if not passed]
    return {
        "evaluation_type": "observed_only_forward_replacement_attribution",
        "acceptance_rule": (
            "Defense-budget rows must have at least 8 mature closed decisions and "
            "positive 10d/20d average broad-relative value plus positive average, "
            "median, and >50% win-rate same-theme replacement value."
        ),
        "checks": checks,
        "passed": not failed_reasons,
        "failed_reasons": failed_reasons,
        "strategy_delta": {
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
            "drawdown_delta": 0.0,
            "trade_count_delta": 0,
        },
    }


def build_payload() -> dict[str, Any]:
    baseline = summarize_baseline(BASELINE_RESULT)
    latest_rows = load_latest_space_rows(LEDGER_JSONL)
    closed_rows = [row for row in latest_rows if row.get("closed_decision") is True]
    defense_rows = [
        row for row in closed_rows if row.get("semantic_bucket") == "defense_budget_theme"
    ]
    non_defense_rows = [
        row for row in closed_rows if row.get("semantic_bucket") != "defense_budget_theme"
    ]
    summary = read_json(SUMMARY_JSON) if SUMMARY_JSON.exists() else {}
    buckets = sorted({row.get("semantic_bucket") or "missing" for row in closed_rows})
    by_bucket = {
        bucket: summarize_group(
            [row for row in closed_rows if (row.get("semantic_bucket") or "missing") == bucket]
        )
        for bucket in buckets
    }
    group_summary = {
        "source_latest_asof": max((row.get("asof_date") or "" for row in latest_rows), default=None),
        "ledger_rows_total": sum(1 for _ in LEDGER_JSONL.open("r", encoding="utf-8")),
        "latest_unique_rows": len(latest_rows),
        "all_closed": summarize_group(closed_rows),
        "defense_budget_theme": summarize_group(defense_rows),
        "non_defense": summarize_group(non_defense_rows),
        "by_semantic_bucket": by_bucket,
        "source_summary": {
            "path": repo_rel(SUMMARY_JSON),
            "closed_decision_count": summary.get("closed_decision_count"),
            "pending_decision_count": summary.get("pending_decision_count"),
            "promotion_gate": summary.get("promotion_gate"),
        },
    }
    gate4 = build_gate4(group_summary)
    decision = (
        "observed_only_positive_lead"
        if gate4["passed"]
        else "rejected_space_catalyst_defense_budget_same_theme_not_incremental"
    )
    status = "observed_only" if gate4["passed"] else "rejected"

    missing_required = {
        field: sum(1 for row in latest_rows if row.get(field) in (None, ""))
        for field in (
            "event_id",
            "ticker",
            "entry_date",
            "closed_decision",
            "horizons",
            "semantic_bucket",
            "source_type",
        )
    }
    signals_generated = len(latest_rows)
    signals_survived = len(closed_rows)
    survival_rate = signals_survived / signals_generated if signals_generated else 0.0

    return {
        "experiment_id": EXPERIMENT_ID,
        "created_at": utc_now(),
        "owner": OWNER,
        "lane": LANE,
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": gate4["passed"],
        "hypothesis": HYPOTHESIS,
        "change_type": "observed_only_attribution",
        "implementation_mode": "observed_only_no_strategy_change",
        "mechanism_family": "observed_only_attribution",
        "trial_family": "observed_only_attribution",
        "trial_variant_id": EXPERIMENT_ID,
        "single_causal_variable": SINGLE_CAUSAL_VARIABLE,
        "changed_variable": SINGLE_CAUSAL_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": ["exp-20260627-024"],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "new_gate_shape",
        "new_evidence_axis": (
            "semantic-bucket same-theme replacement-value gate on the repaired "
            "Space event-state ledger; no response-function retune or order change"
        ),
        "prediction": PREDICTION,
        "parameters": {
            "dedupe_key": ["event_id", "ticker", "entry_date"],
            "latest_row_sort": ["asof_date", "logged_at"],
            "tested_bucket": "defense_budget_theme",
            "horizons": list(HORIZONS),
            "metrics": METRICS,
            "minimum_total_closed_rows": 12,
            "minimum_defense_rows": 8,
            "same_theme_required": True,
        },
        "pre_run_questions": {
            "alpha_hypothesis": HYPOTHESIS,
            "alpha_type": "candidate_pool",
            "prior_work": (
                "exp-20260627-024 repaired the Space event-state ledger and "
                "showed broad positive 10d values, but the promotion gate failed "
                "same-theme replacement value."
            ),
            "single_policy_bundle": (
                "Observed-only attribution of defense_budget_theme versus same-theme "
                "replacement value; no production candidate routing change."
            ),
            "success_criteria": gate4["acceptance_rule"],
            "reproducibility": (
                f"Run {RUNNER_COMMAND}; it reads the frozen baseline summary and "
                "latest Space event-state ledger."
            ),
        },
        "gate1": {
            "baseline_loaded": True,
            "baseline": baseline,
            "notes": (
                "No before/after strategy backtest was run because this experiment "
                "only scores default-off forward observation rows."
            ),
        },
        "gate2": {
            "ledger": repo_rel(LEDGER_JSONL),
            "summary": repo_rel(SUMMARY_JSON),
            "required_fields": missing_required,
            "entry_date_present": missing_required["entry_date"] == 0,
            "target_price_check": (
                "not_applicable: Space event-state forward ledger stores realized "
                "horizon outcomes, not target_price forecasts"
            ),
            "runtime_fields_valid": all(count == 0 for count in missing_required.values()),
        },
        "gate3": {
            "signals_generated": signals_generated,
            "signals_survived": signals_survived,
            "survival_rate": round(survival_rate, 6),
            "survival_rate_floor": 0.05,
            "passed": survival_rate >= 0.05,
            "notes": (
                "Latest unique Space event-state rows are deduped from repeated "
                "daily shadow snapshots before survival is computed."
            ),
        },
        "gate4": gate4,
        "primary_summary": group_summary,
        "production_impact": {
            "shared_policy_changed": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "trade_enabled": False,
            "default_off": True,
        },
        "live_realistic_execution_envelope": {
            "live_ready": False,
            "notional_cap": None,
            "capital_cap": None,
            "liquidity_and_slippage": "not evaluated; no production helper promoted",
            "max_positions": None,
            "sector_theme_exposure": "space theme concentration remains a blocker",
            "kill_switch": "no live path",
            "order_semantics": "no orders emitted",
            "failure_handling": "same-theme replacement failure parks this slice",
        },
        "post_run_reflection": {
            "why_result_happened": (
                "Defense-budget Space rows still look good versus cash and broad "
                "ETFs, but the effect is not incremental after same-theme "
                "opportunity cost: same-theme checks failed on the tested 10d/20d "
                "mature rows."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not rerun Space Catalyst semantic-bucket slicing, hold retunes, "
                "notional retunes, or broad-ETF-only promotion on the same deduped "
                "row set."
            ),
            "new_evidence_required": (
                "Requires materially more closed Space event-state rows, a PIT "
                "historical Space replay, or an independent same-theme benchmark "
                "construction that changes the opportunity-cost measurement."
            ),
        },
        "rejection_reason": None if gate4["passed"] else ", ".join(gate4["failed_reasons"]),
        "next_retry_requires": [
            "materially more closed Space event-state rows",
            "point-in-time historical Space event replay",
            "independent same-theme benchmark construction",
        ],
        "related_files": [
            repo_rel(LEDGER_JSONL),
            repo_rel(SUMMARY_JSON),
            repo_rel(BASELINE_RESULT),
            "quant/experiments/exp_20260627_024_space_catalyst_standard_surface_pending_repair.py",
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(REGISTRY_JSON),
        ],
        "reproduction_commands": [RUNNER_COMMAND],
        "anti_js": [
            "No JavaScript tooling used.",
            "No browser or live trading adapter used.",
        ],
        "lean_quality_passed": True,
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    defense = payload["primary_summary"]["defense_budget_theme"]["by_horizon"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "lane": LANE,
        "status": payload["status"],
        "decision": payload["decision"],
        "hypothesis": payload["hypothesis"],
        "changed_variable": payload["changed_variable"],
        "artifact": repo_rel(OUT_JSON),
        "runner": RUNNER,
        "gate4_passed": payload["gate4"]["passed"],
        "gate4_failed_reasons": payload["gate4"]["failed_reasons"],
        "defense_rows": payload["primary_summary"]["defense_budget_theme"]["row_count"],
        "closed_rows": payload["primary_summary"]["all_closed"]["row_count"],
        "defense_10d_same_theme": defense["10d"]["same_theme"],
        "defense_20d_same_theme": defense["20d"]["same_theme"],
        "production_impact": payload["production_impact"],
        "next_retry_requires": payload["next_retry_requires"],
        "post_run_reflection": payload["post_run_reflection"],
        "prediction": payload["prediction"],
        "completed_at": utc_now(),
    }


def build_card(payload: dict[str, Any]) -> str:
    defense = payload["primary_summary"]["defense_budget_theme"]["by_horizon"]
    lines = [
        f"# {EXPERIMENT_ID} Space Catalyst Same-Theme Value",
        "",
        f"- Status: {payload['status']}",
        f"- Decision: {payload['decision']}",
        f"- Runner: `{RUNNER}`",
        f"- Artifact: `{repo_rel(OUT_JSON)}`",
        "",
        "## Hypothesis",
        "",
        HYPOTHESIS,
        "",
        "## Gate 4",
        "",
        f"- Passed: {payload['gate4']['passed']}",
        f"- Failed reasons: {', '.join(payload['gate4']['failed_reasons']) or 'none'}",
        f"- Closed rows: {payload['primary_summary']['all_closed']['row_count']}",
        f"- Defense rows: {payload['primary_summary']['defense_budget_theme']['row_count']}",
        "",
        "| Horizon | Same-theme avg | Same-theme median | Same-theme win rate |",
        "| --- | ---: | ---: | ---: |",
    ]
    for horizon in HORIZONS:
        same_theme = defense[horizon]["same_theme"]
        lines.append(
            "| {horizon} | {avg} | {median} | {win_rate} |".format(
                horizon=horizon,
                avg=same_theme["avg"],
                median=same_theme["median"],
                win_rate=same_theme["win_rate"],
            )
        )
    lines.extend(
        [
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "## Next Retry Requires",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in payload["next_retry_requires"])
    lines.append("")
    return "\n".join(lines)


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        TICKET_JSON,
        REGISTRY_JSON,
        LEDGER_JSONL,
        SUMMARY_JSON,
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
        "files": {
            repo_rel(path): {
                "exists": path.exists(),
                "sha256": sha256(path),
            }
            for path in files
        },
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    write_json(LOG_JSON, compact_log_record(payload))
    write_text(CARD_MD, build_card(payload))

    ticket_before = read_json(TICKET_JSON) if TICKET_JSON.exists() else {}
    fields = {
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
        "ticket_file": repo_rel(TICKET_JSON),
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "live_realistic_execution_envelope": payload["live_realistic_execution_envelope"],
        "post_run_reflection": payload["post_run_reflection"],
        "rejection_reason": payload["rejection_reason"],
        "next_retry_requires": payload["next_retry_requires"],
        "related_files": payload["related_files"],
        "changed_files": payload["changed_files"],
        "reproduction_commands": payload["reproduction_commands"],
        "anti_js": payload["anti_js"],
        "lean_quality_passed": payload["lean_quality_passed"],
        "hub_identity": ticket_before.get("hub_identity"),
        "novelty": ticket_before.get("novelty"),
        "claimed_at": ticket_before.get("claimed_at"),
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result={
            "accepted": False,
            "accepted_alpha": False,
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields=fields,
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "status": payload["status"],
                "decision": payload["decision"],
                "closed_rows": payload["primary_summary"]["all_closed"]["row_count"],
                "defense_rows": payload["primary_summary"]["defense_budget_theme"]["row_count"],
                "gate4_passed": payload["gate4"]["passed"],
                "gate4_failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
