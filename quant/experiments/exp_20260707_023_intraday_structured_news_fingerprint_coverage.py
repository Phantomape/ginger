"""exp-20260707-023: intraday structured-news fingerprint coverage repair.

This runner writes measurement artifacts only. It does not change signals,
ranking, sizing, exits, paper orders, or live orders.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260707-023"
CHANGED_VARIABLE = "intraday_structured_news_data_source_keywords"
ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import experiment_fingerprint as fp  # noqa: E402


TICKET_PATH = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
FROZEN_PATH = ROOT / "docs" / "frozen_families.jsonl"
EVENTS_PATH = (
    ROOT
    / "data"
    / "daily"
    / "intraday"
    / "structured"
    / "intraday_news_structured_events_20260707_1302ET.json"
)
OBSERVATIONS_PATH = (
    ROOT
    / "data"
    / "daily"
    / "intraday"
    / "structured"
    / "intraday_news_structured_event_observations_20260707_1302ET.jsonl"
)
OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
BEFORE_PATH = OUT_DIR / "before_measurement.json"
AFTER_PATH = OUT_DIR / "after_measurement.json"
ARTIFACT_PATH = OUT_DIR / "exp_20260707_023_intraday_structured_news_fingerprint_coverage.json"

CLASSIFIER_CASES = [
    {
        "label": "relation_observer_text",
        "text": "intraday structured news relation observer",
        "prior_data_source": "ohlcv_relation",
        "expected_data_source": "intraday_structured_news",
        "expected_gate_shape": "other",
    },
    {
        "label": "forward_observation_artifact_name",
        "text": "intraday_news_structured_event forward observation",
        "prior_data_source": "other",
        "expected_data_source": "intraday_structured_news",
        "expected_gate_shape": "other",
    },
    {
        "label": "trade_news_target_relation_quality",
        "text": "intraday trade news target relation quality",
        "prior_data_source": "ohlcv_relation",
        "expected_data_source": "intraday_structured_news",
        "expected_gate_shape": "other",
    },
    {
        "label": "existing_intraday_quality_family",
        "text": "intraday structured relation quality short horizon read",
        "prior_data_source": "ohlcv_relation",
        "expected_data_source": "intraday_structured_news",
        "expected_gate_shape": "other",
    },
]

REGRESSION_CASES = [
    {
        "label": "generic_ohlcv_relation",
        "text": "lead_lag peer rolling_corr relation candidate pool",
        "expected_data_source": "ohlcv_relation",
    },
    {
        "label": "entity_theme_news",
        "text": "entity-theme news relation observer",
        "expected_data_source": "entity_theme_news",
    },
    {
        "label": "prediction_market_event",
        "text": "prediction-market event odds observer",
        "expected_data_source": "prediction_market_event",
    },
]

TARGET_FROZEN_FAMILIES = {
    "intraday_structured_relation_quality_short_horizon_read",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _target_frozen_rows() -> list[dict[str, Any]]:
    if not FROZEN_PATH.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in FROZEN_PATH.read_text(encoding="utf-8-sig").splitlines():
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


def _classify_regression(case: dict[str, str]) -> dict[str, Any]:
    fingerprint = fp.infer_fingerprint(case["text"])
    return {
        **case,
        "fingerprint": fingerprint,
        "passed": fingerprint.get("data_source") == case["expected_data_source"],
    }


def _intraday_surface_snapshot() -> dict[str, Any]:
    events_payload = _load_json(EVENTS_PATH) if EVENTS_PATH.exists() else {}
    observations = _load_jsonl(OBSERVATIONS_PATH)
    statuses = Counter(str(row.get("outcome_status") or "missing") for row in observations)
    closed_rows = sum(
        1
        for row in observations
        if row.get("outcome_status") in {"closed", "settled", "closed_forward"}
    )
    rv_complete_rows = sum(
        1
        for row in observations
        if all(
            row.get(field) is not None
            for field in (
                "replacement_value_vs_cash_usd",
                "replacement_value_vs_spy_usd",
                "replacement_value_vs_qqq_usd",
            )
        )
    )
    target_quality_rows = sum(1 for row in observations if row.get("target_relation_quality"))
    required_fields_ok = (
        events_payload.get("event_contract_audit", {})
        .get("required_field_audit", {})
        .get("all_required_fields_present")
    )
    observation_required_fields_ok = (
        events_payload.get("forward_observation_contract_audit", {})
        .get("required_field_audit", {})
        .get("all_required_fields_present")
    )
    return {
        "events_path": str(EVENTS_PATH.relative_to(ROOT)).replace("\\", "/"),
        "observations_path": str(OBSERVATIONS_PATH.relative_to(ROOT)).replace("\\", "/"),
        "events_file_exists": EVENTS_PATH.exists(),
        "observations_file_exists": OBSERVATIONS_PATH.exists(),
        "source_kind": events_payload.get("event_contract_audit", {}).get("source_kind"),
        "event_rows": events_payload.get("event_contract_audit", {}).get("ledger_rows"),
        "observation_rows": len(observations),
        "outcome_status_counts": dict(sorted(statuses.items())),
        "closed_or_settled_rows": closed_rows,
        "replacement_value_complete_rows": rv_complete_rows,
        "target_relation_quality_rows": target_quality_rows,
        "event_required_fields_ok": bool(required_fields_ok),
        "observation_required_fields_ok": bool(observation_required_fields_ok),
        "entry_dates_present": sum(1 for row in observations if row.get("entry_date")),
        "target_price_contract": (
            "not_applicable_fixed_horizon_observation; no executable signal or target-price exit"
        ),
    }


def build_before() -> dict[str, Any]:
    ticket = _load_json(TICKET_PATH)
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "generated_at": _utc_now(),
        "phase": "before",
        "changed_variable": CHANGED_VARIABLE,
        "source": "reservation_and_preflight_classifier_audit",
        "reservation_fingerprint": ticket.get("novelty", {}).get("fingerprint", {}),
        "known_prior_classifier_miss": {
            "cases": [
                {
                    "label": case["label"],
                    "text": case["text"],
                    "prior_data_source": case["prior_data_source"],
                    "expected_data_source": case["expected_data_source"],
                }
                for case in CLASSIFIER_CASES
            ],
            "evidence": (
                "Pre-repair checks classified intraday structured-news relation text as "
                "ohlcv_relation or other instead of a distinct intraday observer surface."
            ),
        },
        "alpha_hypothesis": (
            "Timestamped intraday structured-news target-relation-quality rows may "
            "carry next-session/10-session replacement value, but the current rows "
            "are pending and cannot support Gate 4 alpha attribution yet."
        ),
        "production_impact": "No trading behavior changed in before measurement.",
    }


def build_after() -> dict[str, Any]:
    cases = [_classify_case(row) for row in CLASSIFIER_CASES]
    regressions = [_classify_regression(row) for row in REGRESSION_CASES]
    frozen_rows = _target_frozen_rows()
    frozen_family_keys = {str(row.get("family_key")) for row in frozen_rows}
    missing_frozen = sorted(TARGET_FROZEN_FAMILIES - frozen_family_keys)
    frozen_passed = all(
        row.get("fingerprint", {}).get("data_source") == "intraday_structured_news"
        for row in frozen_rows
    )
    snapshot = _intraday_surface_snapshot()
    accepted = (
        all(row["passed"] for row in cases)
        and all(row["passed"] for row in regressions)
        and not missing_frozen
        and frozen_passed
        and snapshot["events_file_exists"]
        and snapshot["observations_file_exists"]
        and snapshot["observation_rows"] > 0
        and snapshot["closed_or_settled_rows"] == 0
    )
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "generated_at": _utc_now(),
        "phase": "after",
        "lane": "measurement_repair",
        "hypothesis": (
            "The intraday structured-news observer is a distinct production-visible "
            "forward surface, but novelty fingerprints previously mapped it to "
            "ohlcv_relation or other."
        ),
        "alpha_hypothesis": (
            "Timestamped intraday structured-news target-relation-quality rows may "
            "predict next-session/10-session replacement value after enough rows "
            "close with cash/SPY/QQQ comparators."
        ),
        "changed_variable": CHANGED_VARIABLE,
        "decision": (
            "accepted_measurement_repair_intraday_structured_news_fingerprint_coverage"
            if accepted
            else "blocked_intraday_structured_news_fingerprint_coverage"
        ),
        "accepted": accepted,
        "summary": {
            "classifier_cases": len(cases),
            "classifier_cases_passed": sum(1 for row in cases if row["passed"]),
            "regression_cases": len(regressions),
            "regression_cases_passed": sum(1 for row in regressions if row["passed"]),
            "target_frozen_families": len(TARGET_FROZEN_FAMILIES),
            "target_frozen_families_found": len(frozen_rows),
            "target_frozen_families_passed": sum(
                1
                for row in frozen_rows
                if row.get("fingerprint", {}).get("data_source") == "intraday_structured_news"
            ),
            "missing_target_frozen_families": missing_frozen,
            "derived_frozen_family_view_rebuilt": True,
            "alpha_rows_closed_or_settled": snapshot["closed_or_settled_rows"],
            "alpha_replacement_value_complete_rows": snapshot["replacement_value_complete_rows"],
        },
        "cases": cases,
        "regressions": regressions,
        "target_frozen_families": frozen_rows,
        "intraday_surface_snapshot": snapshot,
        "gate_contract": {
            "gate_1_baseline": "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json",
            "gate_2_runtime_fields": (
                "Observation rows carry entry_date; target_price is explicitly not "
                "applicable because this is fixed-horizon attribution, not an orderable signal."
            ),
            "gate_3_survival": "Not a signal filter; survival is unchanged.",
            "gate_4_rule": (
                "Accept repair when focused classifier tests pass, the existing "
                "intraday structured relation family rebuilds under the specific "
                "source, and generic relation/news surfaces do not overclassify."
            ),
        },
        "reopen_condition": {
            "surface": "intraday_structured_news_forward_observation",
            "status": "blocked_pending_forward_close",
            "blocking_reason": (
                "Alpha activation is blocked because all current intraday structured-news "
                "observation rows are pending and have no replacement value."
            ),
            "current_counts": {
                "observation_rows": snapshot["observation_rows"],
                "target_relation_quality_rows": snapshot["target_relation_quality_rows"],
                "closed_or_settled_rows": snapshot["closed_or_settled_rows"],
                "replacement_value_complete_rows": snapshot["replacement_value_complete_rows"],
            },
            "required_to_reopen": {
                "closed_or_settled_rows_min": 9,
                "replacement_value_complete_rows_min": 9,
                "target_relation_quality_closed_rows_min": 3,
            },
            "reopen_rule": (
                "Reopen alpha only after materially more timestamped intraday "
                "structured-news rows close with cash/SPY/QQQ replacement values, "
                "or with a genuinely new intraday execution gate shape."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "live_orders_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "replay_only": False,
            "trade_enabled": False,
            "scope": "novelty_guard_measurement_only",
        },
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    before = build_before()
    after = build_after()
    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": _utc_now(),
        "before": before,
        "after": after,
        "decision": after["decision"],
        "accepted": after["accepted"],
        "changed_files": [
            "scripts/experiment_fingerprint.py",
            "quant/test_experiment_fingerprint.py",
            "docs/frozen_families.jsonl",
            "quant/experiments/exp_20260707_023_intraday_structured_news_fingerprint_coverage.py",
        ],
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_experiment_fingerprint.py -q",
            ".\\.venv\\Scripts\\python.exe -B scripts\\build_frozen_families.py",
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260707_023_intraday_structured_news_fingerprint_coverage.py",
        ],
    }
    BEFORE_PATH.write_text(json.dumps(before, indent=2, sort_keys=True), encoding="utf-8")
    AFTER_PATH.write_text(json.dumps(after, indent=2, sort_keys=True), encoding="utf-8")
    ARTIFACT_PATH.write_text(json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8")
    print(
        json.dumps(
            {
                "before": BEFORE_PATH.as_posix(),
                "after": AFTER_PATH.as_posix(),
                "artifact": ARTIFACT_PATH.as_posix(),
                "accepted": after["accepted"],
            },
            indent=2,
        )
    )
    return 0 if after["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
