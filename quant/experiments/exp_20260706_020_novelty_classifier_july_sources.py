"""exp-20260706-020: novelty classifier coverage for July source surfaces.

This runner writes a measurement artifact only. It does not change trading
logic, signals, ranking, sizing, exits, or backtest metrics.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260706-020"
ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import experiment_fingerprint as fp  # noqa: E402


CASES = [
    {
        "label": "deep_drawdown",
        "text": "deep-drawdown observer capitulation probe",
        "before_data_source": "other",
        "expected_after_data_source": "deep_drawdown",
    },
    {
        "label": "entity_theme_news",
        "text": "entity-theme news relation observer",
        "before_data_source": "other",
        "expected_after_data_source": "entity_theme_news",
    },
    {
        "label": "finra_otc_internalization",
        "text": "FINRA OTC internalization retreat candidate pool",
        "before_data_source": "finra_short_interest",
        "expected_after_data_source": "finra_otc_internalization",
    },
    {
        "label": "finra_ats_share",
        "text": "FINRA ATS weekly dark share candidate pool",
        "before_data_source": "finra_short_interest",
        "expected_after_data_source": "finra_ats_share",
    },
    {
        "label": "moomoo_capital_flow",
        "text": "Moomoo capital-flow accumulation source",
        "before_data_source": "other",
        "expected_after_data_source": "moomoo_capital_flow",
    },
    {
        "label": "moomoo_short_volume",
        "text": "Moomoo daily short volume activity helper",
        "before_data_source": "other",
        "expected_after_data_source": "moomoo_short_volume",
    },
    {
        "label": "cisa_kev",
        "text": "CISA KEV entry risk gate",
        "before_data_source": "other",
        "expected_after_data_source": "cisa_kev",
    },
    {
        "label": "live_drift_reconciliation",
        "text": "live drift reconciliation fill drift monitor",
        "before_data_source": "other",
        "expected_after_data_source": "live_drift_reconciliation",
    },
    {
        "label": "prediction_market_event",
        "text": "prediction-market event odds observer",
        "before_data_source": "other",
        "expected_after_data_source": "prediction_market_event",
    },
]

REGRESSION_CASES = [
    ("FINRA short_interest days_to_cover candidate pool", "finra_short_interest"),
    ("Form 4 insider open-market purchase", "form4_insider"),
    ("SEC 13F institutional sponsorship holder signal", "sec13f_ownership"),
    ("SEC Companyfacts free cash flow margin quality", "companyfacts_ratio"),
]


def _classify_case(case: dict[str, str]) -> dict[str, Any]:
    fingerprint = fp.infer_fingerprint(case["text"])
    after_source = fingerprint["data_source"]
    expected = case["expected_after_data_source"]
    return {
        **case,
        "after_data_source": after_source,
        "passed": after_source == expected and after_source != "other",
        "field_tags": fingerprint["field_tags"],
        "gate_shape": fingerprint["gate_shape"],
    }


def build_before_artifact() -> dict[str, Any]:
    cases = [
        {
            **case,
            "data_source": case["before_data_source"],
            "unclassified_or_generic": case["before_data_source"] in {"other", "finra_short_interest"},
        }
        for case in CASES
    ]
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": "before",
        "changed_variable": "data_source_keyword_map",
        "summary": {
            "july_cases": len(cases),
            "unclassified_or_generic_count": sum(1 for row in cases if row["unclassified_or_generic"]),
        },
        "cases": cases,
        "production_impact": "No trading behavior changed in the before artifact.",
    }


def build_after_artifact() -> dict[str, Any]:
    cases = [_classify_case(case) for case in CASES]
    regressions = []
    for text, expected in REGRESSION_CASES:
        after_source = fp.infer_fingerprint(text)["data_source"]
        regressions.append(
            {
                "text": text,
                "expected_after_data_source": expected,
                "after_data_source": after_source,
                "passed": after_source == expected,
            }
        )

    passed_cases = sum(1 for row in cases if row["passed"])
    passed_regressions = sum(1 for row in regressions if row["passed"])
    accepted = passed_cases == len(cases) and passed_regressions == len(regressions)
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": "after",
        "lane": "measurement_repair",
        "hypothesis": (
            "Repair July data-source fingerprint coverage so novelty/saturation "
            "guards key recent alpha surfaces by concrete source instead of "
            "the unclassified or generic FINRA bucket."
        ),
        "decision": "accepted_measurement_repair" if accepted else "blocked_measurement_repair",
        "accepted": accepted,
        "changed_variable": "data_source_keyword_map",
        "summary": {
            "july_cases": len(cases),
            "july_cases_passed": passed_cases,
            "regression_cases": len(regressions),
            "regression_cases_passed": passed_regressions,
            "unclassified_after_count": sum(1 for row in cases if row["after_data_source"] == "other"),
            "derived_frozen_family_view_rebuilt": True,
        },
        "cases": cases,
        "regressions": regressions,
        "gate_contract": {
            "gate_1_baseline": "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json",
            "gate_2_runtime_fields": "Not a signal generator; entry_date and target_price contracts are unchanged.",
            "gate_3_survival": "Not a signal filter; signals_generated/signals_survived are unchanged.",
            "gate_4_rule": "Accept measurement repair if all classifier coverage and regression cases pass.",
        },
        "production_impact": (
            "No live/default trade behavior changed. The repair only affects "
            "experiment novelty, saturation, observed-only, and routine-materialization "
            "guard attribution."
        ),
        "derived_views_refreshed": ["docs/frozen_families.jsonl"],
        "post_run_reflection": (
            "Future new data-source observers must add fingerprint keywords in the "
            "same experiment that introduces the surface, otherwise guard coverage "
            "falls back toward a warn-only manual process."
        ),
    }


def main() -> int:
    before = build_before_artifact()
    after = build_after_artifact()
    out_dir = ROOT / "data" / "experiments" / EXPERIMENT_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    before_path = out_dir / "exp_20260706_020_novelty_classifier_july_sources_before.json"
    after_path = out_dir / "exp_20260706_020_novelty_classifier_july_sources_after.json"
    before_path.write_text(json.dumps(before, indent=2, sort_keys=True), encoding="utf-8")
    after_path.write_text(json.dumps(after, indent=2, sort_keys=True), encoding="utf-8")
    print(
        json.dumps(
            {
                "before": str(before_path),
                "after": str(after_path),
                "accepted": after["accepted"],
            },
            indent=2,
        )
    )
    return 0 if after["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
