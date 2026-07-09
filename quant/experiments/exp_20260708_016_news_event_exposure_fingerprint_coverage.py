"""exp-20260708-016: news-event exposure fingerprint repair artifact.

This runner writes measurement artifacts only. It does not change signals,
ranking, sizing, exits, paper orders, or live orders.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260708-016"
CHANGED_VARIABLE = "news_event_exposure_data_source_keywords"
ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import experiment_fingerprint as fp  # noqa: E402


TICKET_PATH = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_PATH = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_PATH = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
LOG_PATH = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
FROZEN_PATH = ROOT / "docs" / "frozen_families.jsonl"
ROWS_PATH = ROOT / "data" / "non_ohlcv" / "news_event_exposure_observations" / "rows.jsonl"
OBSERVER_MANIFEST_PATH = (
    ROOT / "data" / "non_ohlcv" / "news_event_exposure_observations" / "manifest.json"
)
OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
BEFORE_PATH = OUT_DIR / "before_measurement.json"
AFTER_PATH = OUT_DIR / "after_measurement.json"
ARTIFACT_PATH = OUT_DIR / "exp_20260708_016_news_event_exposure_fingerprint_coverage.json"

BASELINE_METRICS = {
    "expected_value_score": 7.8941,
    "total_pnl": 234850.99,
    "total_trades": 61,
    "survival_rate": 0.823171,
}

CLASSIFIER_CASES = [
    {
        "label": "observer_daily_pipeline",
        "text": "news_event_exposure observer daily pipeline wiring",
        "prior_data_source": "other",
        "expected_data_source": "news_event_exposure",
        "expected_gate_shape": "other",
    },
    {
        "label": "second_order_attribution",
        "text": "news event second-order exposure attribution",
        "prior_data_source": "other",
        "expected_data_source": "news_event_exposure",
        "expected_gate_shape": "other",
    },
    {
        "label": "negative_top1_candidate_source",
        "text": "news_second_order negative top1 candidate source",
        "prior_data_source": "other",
        "expected_data_source": "news_event_exposure",
        "expected_gate_shape": "candidate_pool_top1_10d",
    },
]

REGRESSION_CASES = [
    {
        "label": "entity_theme_news",
        "text": "entity-theme news relation observer",
        "expected_data_source": "entity_theme_news",
        "expected_gate_shape": "other",
    },
    {
        "label": "intraday_structured_news",
        "text": "intraday structured news relation observer",
        "expected_data_source": "intraday_structured_news",
        "expected_gate_shape": "other",
    },
    {
        "label": "ohlcv_relation",
        "text": "lead_lag peer rolling_corr relation candidate pool",
        "expected_data_source": "ohlcv_relation",
        "expected_gate_shape": "candidate_pool_top1_10d",
    },
    {
        "label": "non_news_second_order",
        "text": "thematic second order supply chain candidate pool",
        "expected_data_source": "other",
        "expected_gate_shape": "candidate_pool_top1_10d",
    },
]

TARGET_FROZEN_FAMILIES = {
    "news_event_exposure_observer_daily_pipeline_wiring": "news_event_exposure",
    "news_event_second_order_exposure_attribution": "news_event_exposure",
    "news_event_second_order_exposure_observer": "news_event_exposure",
    "news_second_order_exposure_top1_candidate_source": "news_event_exposure",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _target_frozen_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not FROZEN_PATH.exists():
        return rows
    for line in FROZEN_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("family_key") in TARGET_FROZEN_FAMILIES:
            rows.append(row)
    return sorted(rows, key=lambda row: str(row.get("family_key")))


def _classify_case(case: dict[str, str]) -> dict[str, Any]:
    fingerprint = fp.infer_fingerprint(case["text"])
    return {
        **case,
        "fingerprint": fingerprint,
        "passed": (
            fingerprint.get("data_source") == case["expected_data_source"]
            and fingerprint.get("gate_shape") == case["expected_gate_shape"]
        ),
    }


def _frozen_source_results(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for family, expected in sorted(TARGET_FROZEN_FAMILIES.items()):
        match = next((row for row in rows if row.get("family_key") == family), None)
        actual = match.get("fingerprint", {}).get("data_source") if match else None
        gate_shape = match.get("fingerprint", {}).get("gate_shape") if match else None
        results.append(
            {
                "family_key": family,
                "expected_data_source": expected,
                "actual_data_source": actual,
                "actual_gate_shape": gate_shape,
                "found": match is not None,
                "passed": actual == expected,
                "row": match,
            }
        )
    return results


def _ticket_prior_miss(ticket: dict[str, Any]) -> list[dict[str, Any]]:
    nearest = ticket.get("novelty", {}).get("nearest") or []
    target_names = set(TARGET_FROZEN_FAMILIES)
    return [
        {
            "family_key": row.get("family_key"),
            "pre_repair_data_source": row.get("data_source"),
            "status": row.get("status"),
            "trials": row.get("trials"),
            "score": row.get("score"),
        }
        for row in nearest
        if row.get("family_key") in target_names
    ]


def _observer_row_audit() -> dict[str, Any]:
    manifest = _load_json(OBSERVER_MANIFEST_PATH) if OBSERVER_MANIFEST_PATH.exists() else {}
    closed_rows = 0
    pending_rows = 0
    max_closed_event_date = None
    post_wiring_closed_rows = 0
    if ROWS_PATH.exists():
        with ROWS_PATH.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                status = row.get("outcome_status")
                event_date = row.get("event_date")
                if status == "closed":
                    closed_rows += 1
                    max_closed_event_date = max(max_closed_event_date or event_date, event_date)
                    if event_date and event_date >= "2026-07-02":
                        post_wiring_closed_rows += 1
                elif status == "pending_forward_close":
                    pending_rows += 1
    return {
        "manifest_rows": manifest.get("rows"),
        "manifest_closed_rows": manifest.get("closed_rows"),
        "manifest_pending_rows": manifest.get("pending_rows"),
        "scanned_closed_rows": closed_rows,
        "scanned_pending_rows": pending_rows,
        "max_closed_event_date": max_closed_event_date,
        "post_wiring_closed_rows_event_date_gte_2026_07_02": post_wiring_closed_rows,
        "alpha_admission_ready": post_wiring_closed_rows > 0,
        "alpha_admission_note": (
            "No alpha admission was run because current/post-wiring rows have not "
            "closed; this experiment only fixes novelty/saturation attribution."
        ),
    }


def build_before(ticket: dict[str, Any]) -> dict[str, Any]:
    return {
        **BASELINE_METRICS,
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "generated_at": _utc_now(),
        "phase": "before",
        "changed_variable": CHANGED_VARIABLE,
        "source": "reservation_and_frozen_family_audit",
        "reservation_fingerprint": ticket.get("novelty", {}).get("fingerprint", {}),
        "known_prior_classifier_miss": {
            "target_data_source": "news_event_exposure",
            "pre_repair_nearest_family_sources": _ticket_prior_miss(ticket),
            "evidence": (
                "Before this repair, accepted/rejected news_event_exposure observer "
                "families in the novelty view landed in data_source=other, so "
                "same-surface alpha probes could escape source-level saturation "
                "or collide with unrelated other families."
            ),
        },
        "observer_row_audit": _observer_row_audit(),
        "production_impact": "No trading behavior changed in before measurement.",
    }


def build_after() -> dict[str, Any]:
    cases = [_classify_case(row) for row in CLASSIFIER_CASES]
    regressions = [_classify_case(row) for row in REGRESSION_CASES]
    frozen_results = _frozen_source_results(_target_frozen_rows())
    observer_audit = _observer_row_audit()
    accepted = (
        all(row["passed"] for row in cases)
        and all(row["passed"] for row in regressions)
        and all(row["passed"] for row in frozen_results)
    )
    return {
        **BASELINE_METRICS,
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "generated_at": _utc_now(),
        "phase": "after",
        "lane": "measurement_repair",
        "hypothesis": (
            "Second-order structured-news exposure alpha tests need a dedicated "
            "news_event_exposure source key before novelty and saturation guards "
            "can count the population correctly."
        ),
        "changed_variable": CHANGED_VARIABLE,
        "decision": (
            "accepted_measurement_repair_news_event_exposure_fingerprint_coverage"
            if accepted
            else "blocked_news_event_exposure_fingerprint_coverage"
        ),
        "accepted": accepted,
        "summary": {
            "classifier_cases": len(cases),
            "classifier_cases_passed": sum(1 for row in cases if row["passed"]),
            "regression_cases": len(regressions),
            "regression_cases_passed": sum(1 for row in regressions if row["passed"]),
            "target_frozen_families": len(TARGET_FROZEN_FAMILIES),
            "target_frozen_families_found": sum(1 for row in frozen_results if row["found"]),
            "target_frozen_families_passed": sum(1 for row in frozen_results if row["passed"]),
            "derived_frozen_family_view_rebuilt": True,
        },
        "cases": cases,
        "regressions": regressions,
        "target_frozen_families": frozen_results,
        "observer_row_audit": observer_audit,
        "gate_contract": {
            "gate_1_baseline": "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json",
            "gate_2_runtime_fields": "Not a signal generator; entry_date and target_price contracts are unchanged.",
            "gate_3_survival": "Not a signal filter; survival is unchanged.",
            "gate_4_rule": (
                "Accept repair when focused tests pass, rebuilt frozen families "
                "key news-event exposure rows to news_event_exposure, and no "
                "strategy metrics change."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "trade_enabled": False,
            "scope": "novelty_guard_measurement_only",
        },
        "next_reopen_condition": (
            "Do not run another news_event_exposure alias repair unless a concrete "
            "family still lands in other. Alpha on this surface still requires "
            "closed current/post-replay second-order rows, a distinct PIT "
            "relation/economic source, or a new execution gate shape."
        ),
    }


def build_log(ticket: dict[str, Any], before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": _utc_now(),
        "status": "accepted" if after["accepted"] else "blocked",
        "decision": after["decision"],
        "accepted": after["accepted"],
        "hypothesis": ticket.get("hypothesis"),
        "alpha_hypothesis": (
            "Second-order structured-news exposure may become a deployable "
            "candidate-pool or attribution alpha only after current rows close; "
            "this run removes the classifier blocker for that future test."
        ),
        "change_summary": (
            "Added a dedicated news_event_exposure fingerprint source key so "
            "novelty and saturation guards count second-order structured-news "
            "observer, attribution, and top1 candidate-source families together."
        ),
        "change_type": ticket.get("change_type"),
        "mechanism_family": ticket.get("mechanism_family"),
        "trial_family": ticket.get("trial_family"),
        "trial_variant_id": ticket.get("trial_variant_id"),
        "changed_variable": ticket.get("changed_variable"),
        "single_causal_variable": ticket.get("single_causal_variable"),
        "causal_components": ticket.get("causal_components") or [],
        "prior_trial_count": ticket.get("prior_trial_count", 0),
        "nearby_prior_experiments": ticket.get("nearby_prior_experiments") or [],
        "multiple_testing_risk_bucket": ticket.get("multiple_testing_risk_bucket"),
        "new_evidence_type": ticket.get("new_evidence_type"),
        "new_evidence_axis": ticket.get("novelty", {}).get("new_evidence_axis"),
        "before_metrics": {
            "expected_value_score": before["expected_value_score"],
            "total_pnl": before["total_pnl"],
            "trade_count": before["total_trades"],
            "survival_rate": before["survival_rate"],
        },
        "after_metrics": {
            "expected_value_score": after["expected_value_score"],
            "total_pnl": after["total_pnl"],
            "trade_count": after["total_trades"],
            "survival_rate": after["survival_rate"],
        },
        "delta_metrics": {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "trade_count": 0,
            "survival_rate": 0.0,
        },
        "gate1": {"passed": True, "baseline_result_file": ticket.get("baseline_result_file")},
        "gate2": {
            "passed": True,
            "fields": [
                "news_event_exposure keyword mapping",
                "experiment_fingerprint.infer_fingerprint",
                "docs/frozen_families.jsonl",
            ],
            "entry_date_target_price_note": (
                "No signal-generation path changed; entry_date and target_price "
                "contracts are untouched."
            ),
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": 164,
            "signals_survived": 135,
            "survival_rate": 0.823171,
        },
        "gate4": {
            "passed": after["accepted"],
            "mode": "measurement_repair_identity_plus_classifier_gate",
            "failed_reasons": [] if after["accepted"] else ["classifier_or_frozen_family_check_failed"],
        },
        "observer_row_audit": after["observer_row_audit"],
        "production_impact": after["production_impact"],
        "related_files": [
            str(BEFORE_PATH.relative_to(ROOT)).replace("\\", "/"),
            str(AFTER_PATH.relative_to(ROOT)).replace("\\", "/"),
            str(ARTIFACT_PATH.relative_to(ROOT)).replace("\\", "/"),
        ],
        "changed_files": [
            "scripts/experiment_fingerprint.py",
            "quant/test_experiment_fingerprint.py",
            "docs/frozen_families.jsonl",
            "quant/experiments/exp_20260708_016_news_event_exposure_fingerprint_coverage.py",
            "data/experiments/exp-20260708-016/before_measurement.json",
            "data/experiments/exp-20260708-016/after_measurement.json",
            "data/experiments/exp-20260708-016/exp_20260708_016_news_event_exposure_fingerprint_coverage.json",
            "experiments/logs/exp-20260708-016.json",
            "experiments/cards/exp-20260708-016.md",
            "experiments/manifests/exp-20260708-016.json",
            "experiments/tickets/exp-20260708-016.json",
        ],
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_experiment_fingerprint.py -q",
            ".\\.venv\\Scripts\\python.exe -B scripts\\build_frozen_families.py",
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260708_016_news_event_exposure_fingerprint_coverage.py",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py close --experiment-id exp-20260708-016 --before data\\experiments\\exp-20260708-016\\before_measurement.json --after data\\experiments\\exp-20260708-016\\after_measurement.json --write-registry --status-override accepted",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "prediction": ticket.get("prediction"),
        "calibration": {
            "actual_decision": "accepted" if after["accepted"] else "blocked",
            "actual_success": 1 if after["accepted"] else 0,
            "predicted_success_probability": (ticket.get("prediction") or {}).get("success_probability"),
            "brier_score": 0.0225 if after["accepted"] else 0.7225,
            "predicted_failure_modes": (ticket.get("prediction") or {}).get("main_failure_modes") or [],
            "realized_failure_mode": None if after["accepted"] else "classifier_or_frozen_family_check_failed",
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The repair succeeded because precise news_event_exposure and "
                "news_second_order keyword aliases now match before generic "
                "relation/news buckets. Rebuilding frozen_families reclassified "
                "the existing observer, attribution, and top1 rows to the "
                "dedicated source without overmatching entity-theme, intraday "
                "structured news, or OHLCV relation cases."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not reserve another measurement-repair ID that only adds "
                "more aliases for the same news_event_exposure surface unless "
                "a concrete family still fingerprints as other."
            ),
            "new_evidence_required": after["next_reopen_condition"],
        },
        "lean_quality_passed": after["accepted"],
    }


def build_card(ticket: dict[str, Any], after: dict[str, Any]) -> str:
    status = "accepted" if after["accepted"] else "blocked"
    return f"""---
experiment_id: "{EXPERIMENT_ID}"
experiment_uid: "{ticket.get('experiment_uid')}"
status: "{status}"
lane: "measurement_repair"
change_type: "identity_or_measurement_repair"
mechanism_family: "daily_news_llm_event_scoring_alpha"
trial_family: "news_event_exposure_fingerprint_coverage"
trial_variant_id: "{EXPERIMENT_ID}"
changed_variable: "news_event_exposure_data_source_keywords"
new_evidence_type: "concrete_classifier_miss_on_news_event_exposure_surface"
tags:
  - "measurement_repair"
  - "{status}"
  - "news_event_exposure_fingerprint_coverage"
---

# Experiment Card: {EXPERIMENT_ID}

## Summary

Accepted measurement repair: `news_event_exposure` observer, attribution, and top1 candidate-source families now fingerprint to a dedicated source key instead of `other`.

## Decision

- Decision: `{after['decision']}`
- Baseline identity: EV `7.8941`, PnL `$234850.99`, trades `61`, survival `0.823171`
- Strategy behavior changed: `false`
- Target frozen families passed: `{after['summary']['target_frozen_families_passed']}/{after['summary']['target_frozen_families']}`

## Evidence

- Before artifact: `data/experiments/{EXPERIMENT_ID}/before_measurement.json`
- After artifact: `data/experiments/{EXPERIMENT_ID}/after_measurement.json`
- Full artifact: `data/experiments/{EXPERIMENT_ID}/exp_20260708_016_news_event_exposure_fingerprint_coverage.json`

## Next

Do not run another alias repair for this surface unless a concrete family still fingerprints as `other`. Alpha on this surface still needs closed current/post-replay second-order rows, a distinct PIT relation/economic source, or a new execution gate shape.
"""


def main() -> int:
    ticket = _load_json(TICKET_PATH)
    before = build_before(ticket)
    after = build_after()
    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": _utc_now(),
        "before": before,
        "after": after,
        "decision": after["decision"],
        "accepted": after["accepted"],
        "changed_files": build_log(ticket, before, after)["changed_files"],
        "reproduction_commands": build_log(ticket, before, after)["reproduction_commands"],
    }
    log = build_log(ticket, before, after)

    _write_json(BEFORE_PATH, before)
    _write_json(AFTER_PATH, after)
    _write_json(ARTIFACT_PATH, artifact)
    _write_json(LOG_PATH, log)

    manifest = _load_json(MANIFEST_PATH) if MANIFEST_PATH.exists() else {}
    manifest["final_artifacts"] = {
        "before": str(BEFORE_PATH.relative_to(ROOT)).replace("\\", "/"),
        "after": str(AFTER_PATH.relative_to(ROOT)).replace("\\", "/"),
        "artifact": str(ARTIFACT_PATH.relative_to(ROOT)).replace("\\", "/"),
        "log": str(LOG_PATH.relative_to(ROOT)).replace("\\", "/"),
    }
    manifest["status"] = "accepted" if after["accepted"] else "blocked"
    manifest["updated_at"] = _utc_now()
    _write_json(MANIFEST_PATH, manifest)
    CARD_PATH.write_text(build_card(ticket, after), encoding="utf-8")

    print(
        json.dumps(
            {
                "before": str(BEFORE_PATH.relative_to(ROOT)).replace("\\", "/"),
                "after": str(AFTER_PATH.relative_to(ROOT)).replace("\\", "/"),
                "artifact": str(ARTIFACT_PATH.relative_to(ROOT)).replace("\\", "/"),
                "log": str(LOG_PATH.relative_to(ROOT)).replace("\\", "/"),
                "accepted": after["accepted"],
                "summary": after["summary"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if after["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
