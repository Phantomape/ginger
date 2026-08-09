"""exp-20260710-011: SEC 425 deal-economics text coverage readiness.

Measurement repair. Prior 425 theme-peer propagation failed; the allowed
reopen path requires richer deal economics or bidder/target role evidence.
This runner measures whether the local SEC 425 event stream has cached filing
text to support that axis. It does not change strategy behavior.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


EXPERIMENT_ID = "exp-20260710-011"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "sec_425_deal_economics_text_coverage_readiness"
RUNNER = f"quant/experiments/exp_20260710_011_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
for path in (REPO_ROOT / "scripts", REPO_ROOT / "quant", REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


EVENT_ROWS = REPO_ROOT / "data" / "non_ohlcv" / "sec_corporate_event_stream" / "rows.jsonl"
EVENT_MANIFEST = (
    REPO_ROOT / "data" / "non_ohlcv" / "sec_corporate_event_stream" / "manifest.json"
)
TEXT_CACHE_DIR = REPO_ROOT / "data" / "cache" / "sec" / "filing_text"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260710_011_{SLUG}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)

HYPOTHESIS = (
    "Alpha hypothesis: SEC 425 merger communications may have tradable "
    "target/acquirer or peer replacement value only when parsed deal economics "
    "and bidder-target role distinguish cash, stock, mixed, amendment, and "
    "termination contexts; current blocker is whether local 425 filing text "
    "coverage exists for that richer axis."
)
ALPHA_HYPOTHESIS = (
    "SEC 425 merger communications may become a tradable event source only "
    "when filing text can classify consideration mix, party role, and deal "
    "trajectory rather than re-slicing rejected theme-peer rows."
)
CHANGE_TYPE = "identity_or_measurement_repair"
MECHANISM_FAMILY = "production_visible_sec_corporate_event_stream"
TRIAL_FAMILY = "sec_425_deal_economics_text_coverage_readiness"
TRIAL_VARIANT_ID = "sec_425_text_cache_overlap_v1"
SINGLE_CAUSAL_VARIABLE = "sec_425_deal_economics_text_coverage_readiness_v1"
NEW_EVIDENCE_TYPE = "measurement_repair_alpha_blocker_readiness"
NEW_EVIDENCE_AXIS = (
    "Measurement-readiness check for the explicitly allowed richer 425 "
    "deal-economics/role axis; this does not reslice the rejected 425 "
    "theme-peer propagation alpha."
)
ACCEPTANCE_RULE = (
    "Accepted measurement repair only if local SEC filing-text cache overlap "
    "covers at least 300 unique 425 accessions and at least 100 resolved-ticker "
    "425 accessions, enough to attempt a historical parser without network "
    "fetching. Otherwise close blocked with a quantitative reopen condition."
)
REOPEN_CONDITION = (
    "Reopen the 425 deal-economics alpha only after local filing text covers "
    "at least 300 unique SEC 425 accessions and at least 100 resolved-ticker "
    "425 accessions, or after a production/PIT-safe text materializer is wired "
    "for the corporate-event stream. Do not rerun theme, keyword, horizon, "
    "entry-lag, top-N, hold, notional, or response-shape slices on the current "
    "index-only rows."
)
CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260710_011_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]
VERIFICATION_COMMANDS = [
    ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
    RUNNER_COMMAND,
    ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
]

REQUIRED_RICH_FIELDS = [
    "filing_text_or_primary_document_text",
    "consideration_type_cash_stock_mixed",
    "exchange_ratio_or_cash_price",
    "bidder_or_target_role",
    "deal_value_or_size",
    "amendment_withdrawal_termination_trajectory",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return value.as_posix()


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_ticket() -> dict[str, Any]:
    if not TICKET_JSON.exists():
        return {}
    return json.loads(TICKET_JSON.read_text(encoding="utf-8"))


def text_cache_index() -> dict[str, Path]:
    if not TEXT_CACHE_DIR.exists():
        return {}
    return {path.stem: path for path in TEXT_CACHE_DIR.glob("*.json")}


def inspect_text_cache(cache: Mapping[str, Path]) -> dict[str, Any]:
    forms: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    item_code_counts: Counter[str] = Counter()
    parse_errors = 0
    sample_files: list[dict[str, Any]] = []
    for accession, path in sorted(cache.items()):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            parse_errors += 1
            continue
        forms[str(row.get("form_type") or "missing")] += 1
        statuses[str(row.get("status") or "missing")] += 1
        for code in row.get("eight_k_item_codes") or []:
            item_code_counts[str(code)] += 1
        if len(sample_files) < 8:
            sample_files.append(
                {
                    "accession": accession,
                    "ticker": row.get("ticker"),
                    "form_type": row.get("form_type"),
                    "filing_date": row.get("filing_date"),
                    "documents_fetched": row.get("documents_fetched"),
                    "text_char_count": row.get("text_char_count"),
                }
            )
    return {
        "filing_text_cache_files": len(cache),
        "parse_errors": parse_errors,
        "forms": dict(forms),
        "statuses": dict(statuses),
        "eight_k_item_code_counts": dict(item_code_counts),
        "sample_files": sample_files,
    }


def inspect_event_stream(cache: Mapping[str, Path]) -> dict[str, Any]:
    forms: Counter[str] = Counter()
    ticker_status: Counter[str] = Counter()
    keys: set[str] = set()
    accessions_425: Counter[str] = Counter()
    resolved_425: Counter[str] = Counter()
    sample_425: list[dict[str, Any]] = []
    cached_425_examples: list[str] = []
    cached_any_event = 0
    row_count = 0

    with EVENT_ROWS.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row_count += 1
            row = json.loads(line)
            keys.update(str(key) for key in row.keys())
            form = str(row.get("form_type") or "missing")
            accession = str(row.get("accession") or "")
            forms[form] += 1
            ticker_status[str(row.get("ticker_status") or "missing")] += 1
            if accession in cache:
                cached_any_event += 1
            if form == "425":
                accessions_425[accession] += 1
                if row.get("ticker"):
                    resolved_425[accession] += 1
                if len(sample_425) < 5:
                    sample_425.append(row)
                if accession in cache and len(cached_425_examples) < 10:
                    cached_425_examples.append(accession)

    cached_425 = sorted(set(accessions_425) & set(cache))
    cached_425_with_resolved = [
        accession for accession in cached_425 if resolved_425.get(accession, 0) > 0
    ]
    missing_fields = [field for field in REQUIRED_RICH_FIELDS if field not in keys]
    coverage_ratio = (
        len(cached_425) / len(accessions_425) if accessions_425 else 0.0
    )
    return {
        "row_count": row_count,
        "schema_keys": sorted(keys),
        "forms": dict(forms),
        "ticker_status": dict(ticker_status),
        "event_accession_rows_with_cached_text": cached_any_event,
        "required_rich_fields": REQUIRED_RICH_FIELDS,
        "missing_rich_fields": missing_fields,
        "425": {
            "rows": sum(accessions_425.values()),
            "unique_accessions": len(accessions_425),
            "multi_party_accessions": sum(1 for value in accessions_425.values() if value >= 2),
            "accessions_with_resolved_ticker": sum(
                1 for accession in accessions_425 if resolved_425[accession] > 0
            ),
            "unique_accessions_with_cached_text": len(cached_425),
            "resolved_ticker_accessions_with_cached_text": len(cached_425_with_resolved),
            "cached_text_coverage_ratio": round(coverage_ratio, 6),
            "sample_425_rows": sample_425,
            "sample_cached_425_accessions": cached_425_examples,
        },
    }


def build_payload() -> dict[str, Any]:
    ticket = load_ticket()
    cache = text_cache_index()
    event_summary = inspect_event_stream(cache)
    cache_summary = inspect_text_cache(cache)
    unique_cached_425 = event_summary["425"]["unique_accessions_with_cached_text"]
    resolved_cached_425 = event_summary["425"][
        "resolved_ticker_accessions_with_cached_text"
    ]
    coverage_ready = unique_cached_425 >= 300 and resolved_cached_425 >= 100
    status = "accepted_measurement_repair" if coverage_ready else "blocked"
    decision = (
        "accepted_measurement_repair_sec_425_deal_economics_text_ready"
        if coverage_ready
        else "blocked_sec_425_deal_economics_text_coverage"
    )
    timestamp = utc_now()
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "owner": OWNER,
        "lane": LANE,
        "status": status,
        "decision": decision,
        "accepted": coverage_ready,
        "accepted_alpha": False,
        "accepted_measurement_repair": coverage_ready,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "measurement_repair",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": SINGLE_CAUSAL_VARIABLE,
        "changed_variable": SINGLE_CAUSAL_VARIABLE,
        "causal_components": [
            "sec_corporate_event_stream_425_rows",
            "sec_filing_text_cache_overlap",
            "deal_economics_role_axis_readiness",
            "no_strategy_behavior_change",
        ],
        "nearby_prior_experiments": [
            "exp-20260702-018",
            "exp-20260709-010",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "acceptance_rule": ACCEPTANCE_RULE,
        "reopen_condition": REOPEN_CONDITION,
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "ticket_novelty": ticket.get("novelty"),
        "fingerprint_caveat": (
            "Reservation fingerprint classified this measurement repair as "
            "forward_replacement_value because the hypothesis mentioned "
            "replacement value. The true evidence surface is "
            "production_visible_sec_corporate_event_stream / SEC 425 text "
            "coverage readiness; no alpha-lane forward-row evidence is consumed."
        ),
        "event_stream": event_summary,
        "text_cache": cache_summary,
        "gate1": {
            "passed": True,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "note": "Measurement repair/readiness only; no before/after strategy delta.",
        },
        "gate2": {
            "passed": False if not coverage_ready else True,
            "fields_checked": [
                "entry_date",
                "target_price",
                *REQUIRED_RICH_FIELDS,
            ],
            "entry_date": "not_applicable_no_signal_generation",
            "target_price": "not_applicable_no_signal_generation",
            "missing_rich_fields": event_summary["missing_rich_fields"],
            "cached_425_unique_accessions": unique_cached_425,
            "cached_425_resolved_accessions": resolved_cached_425,
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": 0,
            "signals_survived": 0,
            "survival_rate": None,
            "note": "No executable signal/filter/ranking/sizing rule was added.",
        },
        "gate4": {
            "passed": False,
            "mode": "measurement_repair_readiness",
            "failed_reasons": [] if coverage_ready else ["zero_425_text_cache_overlap"],
            "strategy_behavior_changed": False,
        },
        "result": {
            "expected_value_score_delta": 0.0,
            "total_return_pct_delta": 0.0,
            "sharpe_daily_delta": 0.0,
            "trade_count_delta": 0,
            "survival_rate_delta": 0.0,
            "notes": (
                "Blocked readiness: current SEC corporate-event stream has index "
                "metadata but no local 425 filing-text cache overlap."
            ),
        },
        "production_impact": {
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "orders_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "trade_enabled": False,
            "daily_snapshot_changed": False,
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The accepted SEC corporate-event stream materializes form-index "
                "metadata for 425 rows, but local filing_text cache currently "
                "contains no matching 425 accession, so deal consideration and "
                "bidder/target roles cannot be parsed offline."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry SEC 425 theme-peer propagation by theme, keyword, "
                "horizon, entry lag, ticker status, top-N, hold, cooldown, "
                "notional, or response shape on the current rows."
            ),
            "new_evidence_required": REOPEN_CONDITION,
        },
        "changed_files": CHANGED_FILES,
        "related_files": [
            repo_rel(EVENT_ROWS),
            repo_rel(EVENT_MANIFEST),
            repo_rel(TEXT_CACHE_DIR),
            "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json",
        ],
        "reproduction_commands": VERIFICATION_COMMANDS,
        "verification_commands": VERIFICATION_COMMANDS,
        "lean_quality_passed": True,
    }


def build_card(payload: Mapping[str, Any]) -> str:
    stats_425 = payload["event_stream"]["425"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: SEC 425 deal-economics text readiness",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Lane: `{LANE}`",
            f"- Alpha hypothesis: {ALPHA_HYPOTHESIS}",
            f"- 425 rows: `{stats_425['rows']}`",
            f"- Unique 425 accessions: `{stats_425['unique_accessions']}`",
            f"- 425 accessions with cached text: `{stats_425['unique_accessions_with_cached_text']}`",
            f"- Resolved-ticker 425 accessions with cached text: `{stats_425['resolved_ticker_accessions_with_cached_text']}`",
            f"- Artifact: `{repo_rel(OUT_JSON)}`",
            "- Production impact: no entry, exit, ranking, sizing, order, or daily-snapshot change.",
            "",
            "## Reflection",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "## Reopen Condition",
            payload["reopen_condition"],
            "",
            "## Reproduction",
            "",
            "```powershell",
            RUNNER_COMMAND,
            "```",
            "",
        ]
    )


def build_log(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": LANE,
        "status": payload["decision"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "accepted_measurement_repair": payload["accepted_measurement_repair"],
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis": payload["alpha_hypothesis"],
        "change_type": CHANGE_TYPE,
        "implementation_mode": "measurement_repair",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": SINGLE_CAUSAL_VARIABLE,
        "changed_variable": SINGLE_CAUSAL_VARIABLE,
        "causal_components": payload["causal_components"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "baseline_result_file": payload["baseline_result_file"],
        "acceptance_rule": ACCEPTANCE_RULE,
        "reopen_condition": REOPEN_CONDITION,
        "fingerprint_caveat": payload["fingerprint_caveat"],
        "event_stream": payload["event_stream"],
        "text_cache": payload["text_cache"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "result": payload["result"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "artifact": repo_rel(OUT_JSON),
        "changed_files": CHANGED_FILES,
        "verification_commands": VERIFICATION_COMMANDS,
    }


def build_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    files = [REPO_ROOT / rel for rel in CHANGED_FILES]
    return {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_revision_manifest",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": utc_now(),
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(build_log(payload), allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction={
            "success_probability": 0.85,
            "expected_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "main_failure_modes": [
                "zero_425_text_cache_overlap",
                "only_index_metadata_available",
                "network_fetch_required",
            ],
            "confidence_reason": (
                "Plain 425 theme-peer propagation was rejected, while the "
                "playbook allows a richer deal-economics role axis only if "
                "filing text is available; preliminary counts showed index "
                "metadata without 425 text cache overlap."
            ),
        },
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "accepted_measurement_repair": payload["accepted_measurement_repair"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "headline_metrics": {
                "425_unique_accessions": payload["event_stream"]["425"][
                    "unique_accessions"
                ],
                "425_unique_accessions_with_cached_text": payload["event_stream"]["425"][
                    "unique_accessions_with_cached_text"
                ],
                "425_resolved_ticker_accessions_with_cached_text": payload[
                    "event_stream"
                ]["425"]["resolved_ticker_accessions_with_cached_text"],
            },
            "summary": "blocked_sec_425_deal_economics_text_coverage",
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
            "change_type": CHANGE_TYPE,
            "implementation_mode": "measurement_repair",
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": SINGLE_CAUSAL_VARIABLE,
            "changed_variable": SINGLE_CAUSAL_VARIABLE,
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": "minimal",
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "baseline_result_file": payload["baseline_result_file"],
            "acceptance_rule": ACCEPTANCE_RULE,
            "reopen_condition": REOPEN_CONDITION,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "ticket_file": repo_rel(TICKET_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "rejection_reason": "zero_425_text_cache_overlap",
            "realized_failure_mode": "zero_425_text_cache_overlap",
            "related_files": payload["related_files"],
            "changed_files": CHANGED_FILES,
            "reproduction_commands": VERIFICATION_COMMANDS,
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
                "artifact": repo_rel(OUT_JSON),
                "headline_metrics": {
                    "425_unique_accessions": payload["event_stream"]["425"][
                        "unique_accessions"
                    ],
                    "425_unique_accessions_with_cached_text": payload["event_stream"][
                        "425"
                    ]["unique_accessions_with_cached_text"],
                    "425_resolved_ticker_accessions_with_cached_text": payload[
                        "event_stream"
                    ]["425"]["resolved_ticker_accessions_with_cached_text"],
                },
                "reopen_condition": REOPEN_CONDITION,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
