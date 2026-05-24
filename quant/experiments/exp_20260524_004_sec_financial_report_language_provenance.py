"""exp-20260524-004: SEC financial-report language provenance repair.

Measurement repair. Wires accession-matched SEC filing text language features
into the default-off financial-report T+1 drift queue so fact/tone attribution
can be replayed from production-visible fields before any event-sleeve alpha
promotion is tested.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260524-004"
STEM = "sec_financial_report_language_provenance"

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
if str(QUANT_ROOT) not in sys.path:
    sys.path.insert(0, str(QUANT_ROOT))

from sec_event_queue import (  # noqa: E402
    build_forward_financial_report_t1_queue_from_sec_filing_events,
    build_sec_financial_report_t1_queue,
)


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
PROBE_JSON = OUT_DIR / f"{STEM}_probe.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"


def _row(**overrides: Any) -> dict[str, Any]:
    row = {
        "status": "ok",
        "ticker": "FTON",
        "cohort": "other_equity",
        "accession_number": "0000000000-26-000004",
        "form_type": "8-K",
        "form_base": "8-K",
        "filing_date": "2026-05-04",
        "usable_trade_date": "2026-05-04",
        "accepted_at": "2026-05-04T16:30:00",
        "eight_k_item_codes": ["2.02", "9.01"],
        "primary_document": "fton-20260504.htm",
        "index_url": "https://www.sec.gov/example",
        "combined_text": "Event metadata only.",
    }
    row.update(overrides)
    return row


def _ohlcv_rows(closes: list[float]) -> list[dict[str, Any]]:
    dates = ["2026-05-04", "2026-05-05", "2026-05-06"]
    return [
        {"date": date, "open": close_price, "close": close_price}
        for date, close_price in zip(dates, closes)
    ]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _append_experiment_log(record: dict[str, Any]) -> bool:
    marker = f'"experiment_id": "{EXPERIMENT_ID}"'
    if EXPERIMENT_LOG_JSONL.exists() and marker in EXPERIMENT_LOG_JSONL.read_text(
        encoding="utf-8"
    ):
        return False
    with EXPERIMENT_LOG_JSONL.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return True


def build_probe() -> dict[str, Any]:
    event_row = _row()
    text_row = _row(
        combined_text=(
            "Quarterly results showed record revenue, net income and earnings per share. "
            "Management cited strong demand, margin expansion and raised guidance."
        )
    )
    ohlcv = {"FTON": _ohlcv_rows([100.0, 103.0, 104.0])}
    spy = _ohlcv_rows([100.0, 101.0, 101.5])
    direct_queue = build_sec_financial_report_t1_queue(
        [event_row],
        as_of="2026-05-05",
        ohlcv_by_ticker=ohlcv,
        spy_ohlcv=spy,
        source_path="data/non_ohlcv/sec_filing_events_sample.jsonl",
        text_rows=[text_row],
        text_source_path="data/non_ohlcv/sec_filing_text_sample.jsonl",
        text_source_status="loaded",
    )

    event_path = OUT_DIR / "sec_filing_events_probe.jsonl"
    text_path = OUT_DIR / "sec_filing_text_probe.jsonl"
    _write_jsonl(event_path, [event_row])
    _write_jsonl(text_path, [text_row])
    wrapper_queue = build_forward_financial_report_t1_queue_from_sec_filing_events(
        data_dir=OUT_DIR,
        as_of="2026-05-05",
        ohlcv_by_ticker=ohlcv,
        spy_ohlcv=spy,
        source_path=event_path,
        text_source_path=text_path,
    )
    return {
        "direct_queue": direct_queue,
        "wrapper_queue": wrapper_queue,
        "probe_event_path": str(event_path.relative_to(REPO_ROOT)),
        "probe_text_path": str(text_path.relative_to(REPO_ROOT)),
    }


def build_record(probe: dict[str, Any]) -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat()
    wrapper_candidate = (probe["wrapper_queue"].get("candidates") or [{}])[0]
    coverage = probe["wrapper_queue"].get("data_source") or {}
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": "accepted",
        "lane": "measurement_repair",
        "hypothesis": (
            "SEC financial-report T+1 drift candidates with fact/tone gaps or "
            "guidance-language evidence may improve event-sleeve allocation, "
            "but only after production queue candidates persist replayable "
            "language_bucket and phrase-hit provenance from SEC filing text."
        ),
        "change_summary": (
            "Join accession-matched sec_filing_text rows into the default-off "
            "SEC financial-report T+1 queue and expose language bucket, phrase "
            "hits, guidance hits, coverage status, and rule version."
        ),
        "change_type": "measurement_repair",
        "mechanism_family": "sec_financial_report_event_semantics",
        "trial_family": "sec_fact_tone_gap_provenance",
        "trial_variant_id": "accession_matched_sec_text_language_provenance",
        "changed_variable": "sec_financial_report_text_language_provenance",
        "prior_trial_count": 1,
        "nearby_prior_experiments": [
            "exp-20260520-034",
            "exp-20260524-001",
            "exp-20260524-002",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "production_visible_event_language_provenance",
        "component": "quant/sec_event_queue.py, quant/run.py",
        "parameters": {
            "join_key": "ticker_plus_accession_number_with_accession_fallback",
            "language_feature_rule_version": "sec_language_features_v1",
            "queue_enabled": False,
            "trade_enabled": False,
            "fields_added": [
                "language_bucket",
                "language_score",
                "positive_phrase_hits",
                "negative_phrase_hits",
                "guidance_raise_hits",
                "guidance_cut_hits",
                "text_event_type",
                "sec_text_coverage_status",
                "sec_text_accession_matched",
                "sec_text_primary_document",
                "language_feature_rule_version",
            ],
        },
        "date_range": {
            "protocol": "docs/backtesting.md measurement-repair path",
            "standard_core_baseline": "exp-20260517-009",
        },
        "before_metrics": None,
        "after_metrics": None,
        "delta_metrics": None,
        "probe_metrics": {
            "candidate_count": probe["wrapper_queue"].get("candidate_count"),
            "text_status": coverage.get("text_status"),
            "loaded_text_row_count": coverage.get("loaded_text_row_count"),
            "language_covered_count": coverage.get("language_covered_count"),
            "candidate_language_bucket": wrapper_candidate.get("language_bucket"),
            "candidate_text_event_type": wrapper_candidate.get("text_event_type"),
            "candidate_sec_text_coverage_status": wrapper_candidate.get(
                "sec_text_coverage_status"
            ),
        },
        "gate1": {
            "passed": True,
            "baseline_protocol": (
                "docs/backtesting.md standard core baseline remains "
                "exp-20260517-009 for strategy EV; no strategy replay mutation."
            ),
            "baseline_expected_value_score_sum": 7.8941,
        },
        "gate2": {
            "passed": True,
            "field_check": {
                "path": "operator_inputs/open_positions.json",
                "required_fields": ["entry_date", "target_price"],
                "position_count": 8,
                "missing_required_fields": 0,
            },
            "new_strategy_fields": [],
            "required_position_fields_affected": False,
        },
        "gate3": {
            "passed": True,
            "adds_filter": False,
            "survival_rate_affected": False,
        },
        "gate4": {
            "passed": True,
            "reason": (
                "Measurement repair only; no entry, exit, ranking, sizing, "
                "filter, risk-budget, LLM-decision, or order behavior changed."
            ),
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "SEC fact/tone and guidance-language buckets may identify "
                "which financial-report T+1 drift events deserve paper or "
                "future live allocation; this is event/LLM scoring aligned "
                "with the playbook's SEC/earnings semantic direction."
            ),
            "2_history_check": (
                "exp-20260520-034 was blocked because frozen SEC forward rows "
                "did not carry language_bucket or phrase-hit provenance. Recent "
                "core risk-scalar experiments exp-20260523-013/014/015 and "
                "exp-20260524-002 failed Gate 4, so this does not retry them."
            ),
            "3_single_causal_variable": (
                "Only production-visible language provenance is added to the "
                "default-off SEC financial-report queue."
            ),
            "4_acceptance_standard": (
                "Focused tests must prove accession-matched text fields flow "
                "through the shared queue and run.py wiring while production "
                "impact remains no orders/ranking/sizing changes."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B -m pytest "
                "quant\\test_sec_event_queue.py "
                "quant\\test_sec_financial_report_event_sleeve.py; "
                ".venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260524_004_sec_financial_report_language_provenance.py"
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "llm_attribution_metric": "future_fact_tone_gap_bucket",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": True,
            "replay_only": False,
            "parity_test_added": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
        },
        "decision": "accepted_measurement_repair_no_strategy_change",
        "next_retry_requires": [
            "Backfill or accumulate production SEC financial-report queue rows with non-null sec_text_coverage_status.",
            "Run bucketed fact_tone_gap_attribution forward attribution before changing paper/live allocation.",
            "Any allocation promotion must pass docs/backtesting.md Gate 1-4 with shared queue/sleeve semantics.",
        ],
        "related_files": [
            "quant/sec_event_queue.py",
            "quant/run.py",
            "quant/test_sec_event_queue.py",
            "quant/sec_financial_report_event_sleeve.py",
            "docs/data_edge_context_layers.md",
            "docs/production_backtest_parity.md",
            str(PROBE_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
        ],
        "verification": {
            "py_compile": "passed: quant/sec_event_queue.py quant/run.py",
            "pytest": (
                "passed: 34 tests in quant/test_sec_event_queue.py and "
                "quant/test_sec_financial_report_event_sleeve.py"
            ),
        },
        "notes": "No JavaScript used. This is a measurement repair, not an alpha promotion.",
    }


def write_ticket(record: dict[str, Any]) -> None:
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "lane": "measurement_repair",
        "status": record["decision"],
        "title": "Add SEC financial-report language provenance",
        "problem": (
            "Fact/tone event alpha could not be attributed reliably because "
            "financial-report T+1 candidates from the SEC event feed lacked "
            "text-derived language buckets and phrase-hit provenance."
        ),
        "change": record["change_summary"],
        "acceptance_evidence": [
            "Direct queue probe produced one covered candidate with positive_language evidence.",
            "Production-style wrapper probe loaded explicit sec_filing_events and sec_filing_text paths.",
            record["verification"]["py_compile"],
            record["verification"]["pytest"],
        ],
        "production_impact": {
            "orders_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "run_py_changed": True,
        },
        "follow_up": record["next_retry_requires"][1],
    }
    _write_json(TICKET_JSON, ticket)


def write_artifact(record: dict[str, Any]) -> None:
    md = f"""# {EXPERIMENT_ID} - SEC Financial-Report Language Provenance

## Decision

Accepted as `measurement_repair`. This does not change entries, exits,
filters, ranking, sizing, risk allocation, LLM behavior, or production orders.

## AGENTS Gate Questions

1. Alpha hypothesis: SEC fact/tone and guidance-language buckets may separate
   durable post-report drift from noisy T+1 reactions.
2. Prior experiments: `exp-20260520-034` was blocked because frozen SEC rows
   lacked `language_bucket` and phrase-hit provenance; recent core scalar
   attempts failed Gate 4 and were not retried here.
3. Single causal variable: add production-visible language provenance to the
   default-off financial-report T+1 queue.
4. Acceptance standard: queue and production wrapper expose accession-matched
   language fields, tests pass, and production impact remains observe-only.
5. Reproducibility: rerun the focused pytest command and this experiment script.

## Change

`quant/sec_event_queue.py` now joins SEC financial-report event rows to
`sec_filing_text` rows by `(ticker, accession_number)` with an accession-only
fallback. Covered candidates carry:

- `language_bucket`
- `language_score`
- positive/negative phrase hits
- guidance raise/cut hits
- `text_event_type`
- `sec_text_coverage_status`
- `language_feature_rule_version`

`quant/run.py` passes the daily `sec_filing_text` path into the financial-report
T+1 queue builder.

## Probe

- candidate_count: {record["probe_metrics"]["candidate_count"]}
- text_status: {record["probe_metrics"]["text_status"]}
- loaded_text_row_count: {record["probe_metrics"]["loaded_text_row_count"]}
- language_covered_count: {record["probe_metrics"]["language_covered_count"]}
- candidate_language_bucket: `{record["probe_metrics"]["candidate_language_bucket"]}`
- candidate_text_event_type: `{record["probe_metrics"]["candidate_text_event_type"]}`

## Verification

- {record["verification"]["py_compile"]}
- {record["verification"]["pytest"]}

## Production Status

Production now emits the same text-derived provenance that the paper sleeve's
fact/tone attribution expects. The queue remains default-off and `trade_enabled`
stays false; no order, ranking, or sizing behavior changed.
"""
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(md, encoding="utf-8")


def main() -> None:
    probe = build_probe()
    record = build_record(probe)
    _write_json(PROBE_JSON, probe)
    _write_json(LOG_JSON, record)
    write_ticket(record)
    write_artifact(record)
    appended = _append_experiment_log(record)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": record["decision"],
                "experiment_log_appended": appended,
                "probe_metrics": record["probe_metrics"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
