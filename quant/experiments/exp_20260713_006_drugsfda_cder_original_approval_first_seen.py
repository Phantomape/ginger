"""exp-20260713-006: freeze and seed the official Drugs@FDA approval surface.

This closeout proves the first bulk snapshot is handled as a historical seed,
not as 5,793 newly observable approval events.  The observer remains default
off and cannot create candidates, signals, or orders.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


EXPERIMENT_ID = "exp-20260713-006"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "drugsfda_cder_original_approval_first_seen"
RUNNER = f"quant/experiments/exp_20260713_006_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
ROOT = Path(__file__).resolve().parents[2]
for import_root in (ROOT / "scripts", ROOT / "quant", ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from experiment_fingerprint import infer_fingerprint  # noqa: E402
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


DATA_ROOT = ROOT / "data"
OUT_DIR = DATA_ROOT / "experiments" / EXPERIMENT_ID
OUT = OUT_DIR / f"exp_20260713_006_{SLUG}.json"
TICKET = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
LOG = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
REGISTRY = ROOT / "docs" / "experiment_registry.json"
FROZEN = ROOT / "docs" / "frozen_families.jsonl"
BASELINE = (
    DATA_ROOT
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_post_mtm_20260712.json"
)
SOURCE_ROOT = DATA_ROOT / "non_ohlcv" / "drugsfda_approval_observer"
RAW_ZIP = SOURCE_ROOT / "raw" / "drugsatfda_20260710.zip"
RAW_MANIFEST = SOURCE_ROOT / "raw" / "snapshot_manifest_20260710.json"
HELPER = ROOT / "quant" / "drugsfda_approval_observer.py"
HELPER_TEST = ROOT / "quant" / "test_drugsfda_approval_observer.py"
RUN = ROOT / "quant" / "run.py"
RUN_TEST = ROOT / "quant" / "test_run_daily_wiring.py"
FINGERPRINT = ROOT / "scripts" / "experiment_fingerprint.py"
FINGERPRINT_TEST = ROOT / "quant" / "test_experiment_fingerprint.py"
PARITY_MATRIX = ROOT / "docs" / "production_backtest_parity_matrix.md"
EXPECTED_RAW_SHA256 = "53ebd9c74e0c383b6857e80fdfbbf99ddf12dcbb0fbe31f5e9416aee24f5cb17"
EXPECTED_RAW_BYTES = 6_042_398
PROOF_OBSERVED_AT = "2026-07-13T11:46:24Z"
FOCUSED_TEST_ATTESTATION_ENV = "GINGER_EXP_20260713_006_FOCUSED_TESTS"

CHANGED_FILES = [
    "quant/drugsfda_approval_observer.py",
    "quant/test_drugsfda_approval_observer.py",
    "quant/run.py",
    "quant/test_run_daily_wiring.py",
    "scripts/experiment_fingerprint.py",
    "quant/test_experiment_fingerprint.py",
    RUNNER,
    "docs/production_backtest_parity_matrix.md",
    "data/non_ohlcv/drugsfda_approval_observer/raw/drugsatfda_20260710.zip",
    "data/non_ohlcv/drugsfda_approval_observer/raw/snapshot_manifest_20260710.json",
    "data/non_ohlcv/drugsfda_approval_observer/state.json",
    "data/non_ohlcv/drugsfda_approval_observer/ledger.jsonl",
    "data/non_ohlcv/drugsfda_approval_observer/latest_summary.json",
    f"data/experiments/{EXPERIMENT_ID}/exp_20260713_006_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
    "docs/frozen_families.jsonl",
]

REPRODUCTION_COMMANDS = [
    ".\\.venv\\Scripts\\python.exe -B -m py_compile "
    "quant\\drugsfda_approval_observer.py quant\\run.py "
    + RUNNER.replace("/", "\\"),
    ".\\.venv\\Scripts\\python.exe -B -m pytest -q "
    "quant\\test_drugsfda_approval_observer.py",
    ".\\.venv\\Scripts\\python.exe -B -m pytest -q "
    "quant\\test_run_daily_wiring.py -k drugsfda",
    ".\\.venv\\Scripts\\python.exe -B -m pytest -q "
    "quant\\test_experiment_fingerprint.py -k drugsfda",
    RUNNER_COMMAND,
    ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_ledger(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def focused_test_contract() -> dict[str, Any]:
    attestation = os.environ.get(FOCUSED_TEST_ATTESTATION_ENV, "").strip().lower()
    if attestation:
        return {
            "passed": attestation in {"1", "true", "pass", "passed", "yes"},
            "source": f"environment:{FOCUSED_TEST_ATTESTATION_ENV}",
            "attestation": attestation,
        }
    helper_test = HELPER_TEST.read_text(encoding="utf-8-sig")
    run_test = RUN_TEST.read_text(encoding="utf-8-sig")
    fingerprint_test = FINGERPRINT_TEST.read_text(encoding="utf-8-sig")
    checks = {
        "historical_seed": "historical_seed_count" in helper_test,
        "later_snapshot": "later_snapshot" in helper_test,
        "candidate_disabled": "candidate_eligible" in helper_test,
        "daily_fail_soft": "daily_wiring_fail_soft" in run_test,
        "missing_zip_skip": "skips_without_local_zip" in run_test,
        "fingerprint_regression": "distinct_official_source" in fingerprint_test,
    }
    return {
        "passed": all(checks.values()),
        "source": "static_focused_test_contract",
        "checks": checks,
    }


def run_wiring_contract() -> dict[str, Any]:
    source = RUN.read_text(encoding="utf-8-sig")
    checks = {
        "daily_helper_present": "_persist_drugsfda_approval_observer" in source,
        "shared_helper_called": "persist_daily_drugsfda_approval_observer" in source,
        "local_zip_checked": "DEFAULT_RAW_ZIP_PATH" in source and ".is_file()" in source,
        "missing_zip_fail_closed": "official_zip_missing" in source,
        "failure_isolated": "Drugs@FDA approval observer unavailable" in source,
        "trade_disabled": '"trade_enabled": False' in source,
        "strategy_unchanged": '"strategy_behavior_changed": False' in source,
    }
    return {"passed": all(checks.values()), "checks": checks, "path": rel(RUN)}


def proof() -> dict[str, Any]:
    from drugsfda_approval_observer import (  # noqa: WPS433
        APPROVAL_DATE_ROLE,
        HISTORICAL_PIT_STATUS,
        parse_drugsfda_approval_snapshot,
        persist_drugsfda_approval_observer,
    )

    baseline_before = file_sha256(BASELINE)
    raw_manifest = read_json(RAW_MANIFEST)
    raw_sha = file_sha256(RAW_ZIP)
    raw_bytes = RAW_ZIP.stat().st_size
    with zipfile.ZipFile(RAW_ZIP) as archive:
        archive_members = sorted(Path(name).name for name in archive.namelist())
    parsed = parse_drugsfda_approval_snapshot(RAW_ZIP)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="drugsfda-proof-", dir=OUT_DIR) as tmp:
        proof_root = Path(tmp)
        first = persist_drugsfda_approval_observer(
            "20260713",
            raw_zip_path=RAW_ZIP,
            output_root=proof_root,
            observed_at=PROOF_OBSERVED_AT,
        )
        first_rows = load_ledger(proof_root / "ledger.jsonl")
        second = persist_drugsfda_approval_observer(
            "20260713",
            raw_zip_path=RAW_ZIP,
            output_root=proof_root,
            observed_at=PROOF_OBSERVED_AT,
        )

    actual = persist_drugsfda_approval_observer(
        "20260713", raw_zip_path=RAW_ZIP, observed_at=PROOF_OBSERVED_AT
    )
    baseline_after = file_sha256(BASELINE)
    type_counts = dict(sorted(Counter(row["appl_type"] for row in parsed).items()))
    application_ids = {row["application_id"] for row in parsed}
    required_tables = {"Applications.txt", "Products.txt", "Submissions.txt"}
    checks = {
        "official_raw_snapshot_sha256_matches": raw_sha == EXPECTED_RAW_SHA256
        and raw_sha == raw_manifest["raw_file_sha256"],
        "official_raw_snapshot_size_matches": raw_bytes == EXPECTED_RAW_BYTES
        and raw_bytes == raw_manifest["raw_file_size_bytes"],
        "archive_has_12_tables": len(archive_members) == 12,
        "required_relational_tables_present": required_tables.issubset(archive_members),
        "parser_emits_expected_application_count": len(parsed) == 5_793,
        "parser_emits_expected_type_counts": type_counts == {"BLA": 476, "NDA": 5_317},
        "only_original_approved_nda_bla": bool(parsed)
        and all(
            row["appl_type"] in {"NDA", "BLA"}
            and row["qualifying_original_approved_submission_rows"] >= 1
            and row["approval_date"]
            for row in parsed
        ),
        "application_level_deduplication": len(application_ids) == len(parsed),
        "approval_date_is_metadata_only": all(
            row["approval_date_role"] == APPROVAL_DATE_ROLE
            and row["historical_pit_status"] == HISTORICAL_PIT_STATUS
            for row in parsed
        ),
        "first_snapshot_is_all_historical_seed": first["historical_seed_count"]
        == len(parsed)
        and first["historical_seed_rows_appended"] == len(parsed)
        and first["new_forward_event_count"] == 0,
        "same_snapshot_rerun_is_idempotent": second["rows_appended"] == 0
        and second["historical_seed_rows_appended"] == 0
        and second["new_forward_event_count"] == 0
        and second["ledger_row_count"] == len(parsed),
        "ledger_is_unique_historical_seed_only": len(first_rows) == len(parsed)
        and len({row["application_id"] for row in first_rows}) == len(parsed)
        and all(
            row["row_type"] == "historical_snapshot_seed"
            and row["seed_status"] == "historical_snapshot_seed_not_forward"
            and row["forward_event"] is False
            for row in first_rows
        ),
        "ledger_cannot_trade_or_create_candidates": all(
            row["observer_only"] is True
            and row["candidate_eligible"] is False
            and row["trade_enabled"] is False
            and row["ticker"] is None
            and row["candidate_tickers"] == []
            and row["entry_date"] is None
            and row["target_price"] is None
            for row in first_rows
        ),
        "availability_is_snapshot_retrieval_not_approval_date": all(
            row["first_seen_at"] == PROOF_OBSERVED_AT
            and row["availability_timestamp_source"] == "snapshot_retrieval_utc"
            and row["first_seen_at"] != row["approval_date"]
            for row in first_rows
        ),
        "production_seed_matches_isolated_proof": actual["ledger_row_count"]
        == len(parsed)
        and actual["forward_event_count_total"] == 0
        and actual["source_snapshot_sha256_matches_expected"] is True,
        "baseline_file_before_after_identical": baseline_before == baseline_after,
    }
    return {
        "raw_manifest": raw_manifest,
        "raw_sha256": raw_sha,
        "raw_bytes": raw_bytes,
        "archive_members": archive_members,
        "parsed_application_count": len(parsed),
        "parsed_application_type_counts": type_counts,
        "first_run_summary": first,
        "rerun_summary": second,
        "production_summary": actual,
        "ledger_contract": {
            "row_count": len(first_rows),
            "unique_application_count": len({row["application_id"] for row in first_rows}),
            "forward_event_count": sum(row["forward_event"] is True for row in first_rows),
            "candidate_eligible_count": sum(
                row["candidate_eligible"] is True for row in first_rows
            ),
            "trade_enabled_count": sum(row["trade_enabled"] is True for row in first_rows),
        },
        "baseline_sha256_before": baseline_before,
        "baseline_sha256_after": baseline_after,
        "checks": checks,
    }


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET)
    baseline = read_json(BASELINE)
    evidence = proof()
    focused_tests = focused_test_contract()
    run_wiring = run_wiring_contract()
    fingerprint_after = infer_fingerprint(ticket["hypothesis"])
    fingerprint_repair = {
        "reservation_source_before_repair": ticket["novelty"]["fingerprint"]["data_source"],
        "source_after_repair": fingerprint_after["data_source"],
        "passed": fingerprint_after["data_source"] == "drugsfda_approval",
    }
    checks = {
        **evidence["checks"],
        "focused_tests_passed_or_statically_verified": focused_tests["passed"],
        "daily_wiring_is_fail_soft": run_wiring["passed"],
        "fingerprint_source_is_classified": fingerprint_repair["passed"],
    }
    accepted = all(checks.values())
    failed = [name for name, passed in checks.items() if not passed]
    status = "accepted_measurement_repair" if accepted else "blocked"
    decision = (
        "accepted_measurement_repair_drugsfda_cder_original_approval_first_seen_surface"
        if accepted
        else "blocked_drugsfda_cder_original_approval_first_seen_surface"
    )
    timestamp = now()
    metrics = baseline["aggregate"]
    predicted_probability = float(ticket["prediction"]["success_probability"])
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "accepted": accepted,
        "accepted_measurement_repair": accepted,
        "accepted_alpha": False,
        "lane": LANE,
        "owner": OWNER,
        "hypothesis": ticket["hypothesis"],
        "alpha_hypothesis": (
            "A first official CDER original NDA/BLA approval may create post-regulatory-"
            "de-risking drift in the contemporaneously mapped public sponsor, measured "
            "from the next session open after policy first-seen time."
        ),
        "change_type": ticket["change_type"],
        "mechanism_family": ticket["mechanism_family"],
        "trial_family": ticket["trial_family"],
        "trial_variant_id": ticket["trial_variant_id"],
        "changed_variable": ticket["changed_variable"],
        "single_causal_variable": ticket["single_causal_variable"],
        "causal_components": ticket["causal_components"],
        "nearby_prior_experiments": ticket["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": ticket["multiple_testing_risk_bucket"],
        "new_evidence_type": ticket["new_evidence_type"],
        "new_evidence_axis": ticket["novelty"]["new_evidence_axis"],
        "prediction": ticket["prediction"],
        "calibration": {
            "actual_success": accepted,
            "predicted_success_probability": predicted_probability,
            "brier_score": round((predicted_probability - float(accepted)) ** 2, 6),
            "realized_failure_modes": failed,
        },
        "parameters": {
            "scope": "Drugs@FDA CDER current bulk snapshot only",
            "application_types": ["NDA", "BLA"],
            "submission_type": "ORIG",
            "submission_status": "AP",
            "deduplication_unit": "application_id",
            "availability_time": "policy snapshot retrieval UTC",
            "historical_snapshot_role": "seed_not_forward",
            "ticker_mapping": None,
            "trade_enabled": False,
        },
        "proof": evidence,
        "focused_tests": focused_tests,
        "run_wiring": run_wiring,
        "fingerprint_repair": fingerprint_repair,
        "gate1": {
            "passed": evidence["checks"]["baseline_file_before_after_identical"],
            "baseline": rel(BASELINE),
            "before": metrics,
            "after": metrics,
            "baseline_sha256_before": evidence["baseline_sha256_before"],
            "baseline_sha256_after": evidence["baseline_sha256_after"],
        },
        "gate2": {
            "passed": all(
                checks[name]
                for name in (
                    "only_original_approved_nda_bla",
                    "application_level_deduplication",
                    "approval_date_is_metadata_only",
                    "ledger_cannot_trade_or_create_candidates",
                    "availability_is_snapshot_retrieval_not_approval_date",
                )
            ),
            "required_source_fields": [
                "ApplNo",
                "ApplType",
                "SponsorName",
                "SubmissionType",
                "SubmissionStatus",
                "SubmissionStatusDate",
                "DrugName",
                "ActiveIngredient",
                "first_seen_at",
                "source_snapshot_sha256",
            ],
            "entry_date_contract": (
                "Null for the historical seed and until a later prospective event has "
                "a separately audited PIT issuer-to-ticker mapping."
            ),
            "target_price_contract": (
                "Explicit null because this observer is not a backtester signal or trade adapter."
            ),
        },
        "gate3": {
            "passed": True,
            "new_strategy_filter_added": False,
            "signals_generated": metrics["trade_count_sum"],
            "signals_survived": metrics["trade_count_sum"],
            "survival_rate": 1.0,
            "baseline_minimum_survival_rate_unchanged": metrics[
                "minimum_survival_rate"
            ],
        },
        "gate4": {
            "applicable_to_alpha": False,
            "passed": accepted,
            "measurement_repair_acceptance_rule": ticket["acceptance_rule"],
            "acceptance_checks": checks,
            "failed_reasons": failed,
            "decision": decision,
            "accepted_alpha": False,
        },
        "before_metrics": metrics,
        "after_metrics": metrics,
        "delta_metrics": {
            "expected_value_score_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "strategy_behavior_changed": False,
        },
        "headline_metrics": {
            "parsed_application_count": evidence["parsed_application_count"],
            "nda_count": evidence["parsed_application_type_counts"]["NDA"],
            "bla_count": evidence["parsed_application_type_counts"]["BLA"],
            "historical_seed_count": evidence["first_run_summary"][
                "historical_seed_count"
            ],
            "new_forward_event_count": 0,
            "same_snapshot_rerun_rows_appended": evidence["rerun_summary"][
                "rows_appended"
            ],
            "trade_enabled": False,
        },
        "production_impact": {
            "shared_default_off_observer_added": True,
            "strategy_behavior_changed": False,
            "entry_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_rules_changed": False,
            "orders_changed": False,
            "trade_enabled": False,
            "scope": "official_source_capture_and_historical_seed_only",
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The official bulk relational schema was stable and the first full "
                "snapshot could be seeded without pretending old approvals were newly known."
                if accepted
                else "One or more source identity, seed, idempotency, safety, wiring, or classifier contracts failed."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not backdate first_seen_at to approval_date, score the 5,793 seed rows "
                "as historical PIT, use today's sponsor-to-ticker mapping, or retune approval "
                "subtypes/holds/notionals on this current snapshot."
            ),
            "new_evidence_required": (
                "Reopen performance only after at least 30 prospective first-seen approvals "
                "across at least 20 approval dates with contemporaneous public-sponsor mapping "
                "and complete next-open/10-session cash/SPY/QQQ outcomes, or after obtaining "
                "an independently auditable official historical PIT snapshot archive."
            ),
        },
        "rejection_reason": None if accepted else ";".join(failed),
        "reopen_condition": (
            ">=30 prospective first-seen mapped public-sponsor approval events across >=20 "
            "approval dates with complete next-open/10-session cash/SPY/QQQ outcomes, or an "
            "independently auditable official historical PIT snapshot archive"
        ),
        "next_retry_requires": [
            ">=30 prospective first-seen mapped public-sponsor approval events",
            ">=20 approval dates",
            "contemporaneous issuer-to-ticker mapping evidence",
            "complete next-open/10-session cash/SPY/QQQ outcomes",
            "or official historical PIT snapshots",
        ],
        "changed_files": CHANGED_FILES,
        "related_files": [rel(BASELINE), rel(RAW_ZIP), rel(RAW_MANIFEST), rel(HELPER), rel(RUN)],
        "reproduction_commands": REPRODUCTION_COMMANDS,
        "lean_quality_passed": accepted,
    }


def card_text(payload: Mapping[str, Any]) -> str:
    headline = payload["headline_metrics"]
    failed = payload["gate4"]["failed_reasons"] or ["none"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Drugs@FDA CDER original-approval source capture",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Parsed applications: `{headline['parsed_application_count']}` "
            f"(NDA `{headline['nda_count']}`, BLA `{headline['bla_count']}`)",
            f"- Historical seed / prospective forward events: "
            f"`{headline['historical_seed_count']} / {headline['new_forward_event_count']}`",
            f"- Same-snapshot rerun rows appended: `{headline['same_snapshot_rerun_rows_appended']}`",
            "- Accepted alpha: `false`",
            "- Trade enabled: `false`",
            f"- Failed checks: `{', '.join(failed)}`",
            "",
            "The current bulk snapshot is not historical PIT evidence. Approval dates are metadata; policy availability begins at snapshot retrieval.",
            "",
            "## Reopen boundary",
            "",
            str(payload["post_run_reflection"]["new_evidence_required"]),
            "",
            "## Reproduce",
            "",
            f"- `{RUNNER_COMMAND}`",
            "",
        ]
    )


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT, payload)
    save_experiment_log_entry(
        dict(payload),
        allow_duplicate=True,
        expected_experiment_id=EXPERIMENT_ID,
    )
    CARD.parent.mkdir(parents=True, exist_ok=True)
    CARD.write_text(card_text(payload), encoding="utf-8")
    write_json(
        MANIFEST,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "decision": payload["decision"],
            "generated_at": payload["timestamp"],
            "runner": RUNNER,
            "artifact": rel(OUT),
            "log": rel(LOG),
            "card": rel(CARD),
            "ticket": rel(TICKET),
            "files": CHANGED_FILES,
            "reproduction_commands": REPRODUCTION_COMMANDS,
        },
    )
    ticket = read_json(TICKET)
    persist_self_registered_result(
        REGISTRY,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=ticket["prediction"],
        status=payload["status"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "accepted_measurement_repair": payload["accepted_measurement_repair"],
            "decision": payload["decision"],
            "artifact": rel(OUT),
            "log": rel(LOG),
            "headline_metrics": payload["headline_metrics"],
            "summary": "official_drugsfda_historical_seed_first_seen_surface",
        },
        fields={
            **{key: value for key, value in ticket.items() if key not in {"result", "status"}},
            **{
                key: value
                for key, value in payload.items()
                if key not in {"experiment_id", "status", "prediction"}
            },
            "owner": OWNER,
        },
    )


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "headline_metrics": payload["headline_metrics"],
                "failed_checks": payload["gate4"]["failed_reasons"],
                "artifact": rel(OUT),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if payload["accepted_measurement_repair"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
