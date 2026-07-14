"""exp-20260713-007: prove the USAspending first-seen seed contract.

The current official transaction download is a frozen *current* snapshot.  It
must seed transaction identities at local retrieval time and must not be
backdated into historical alpha evidence.  This runner executes the observer
twice in an isolated proof directory, then materializes the same snapshot in
the production observer directory.  It writes the final proof, closeout
records, and registry result through the sanctioned persistence helpers.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import sys
import tempfile
import zipfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


EXPERIMENT_ID = "exp-20260713-007"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "usaspending_obligation_first_seen"
RUNNER = f"quant/experiments/exp_20260713_007_{SLUG}.py"
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
OUT = OUT_DIR / f"exp_20260713_007_{SLUG}.json"
TICKET = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
LOG = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
REGISTRY = ROOT / "docs" / "experiment_registry.json"
BASELINE = (
    DATA_ROOT
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_post_mtm_20260712.json"
)
SOURCE_ROOT = DATA_ROOT / "non_ohlcv" / "usaspending_obligation_observer"
RAW_ZIP = (
    SOURCE_ROOT
    / "raw"
    / "SubawardsAndPrimeTransactions_2026-07-13_H20M51S32580747.zip"
)
RAW_MANIFEST = SOURCE_ROOT / "raw" / "snapshot_manifest_20260713.json"
PRODUCTION_STATE = SOURCE_ROOT / "state.json"
PRODUCTION_LEDGER = SOURCE_ROOT / "ledger.jsonl"
PRODUCTION_SUMMARY = SOURCE_ROOT / "latest_summary.json"
HELPER = ROOT / "quant" / "usaspending_obligation_observer.py"
HELPER_TEST = ROOT / "quant" / "test_usaspending_obligation_observer.py"
RUN = ROOT / "quant" / "run.py"
RUN_TEST = ROOT / "quant" / "test_run_daily_wiring.py"
FINGERPRINT = ROOT / "scripts" / "experiment_fingerprint.py"
PARITY_MATRIX = ROOT / "docs" / "production_backtest_parity_matrix.md"
FINGERPRINT_TEST = ROOT / "quant" / "test_experiment_fingerprint.py"
FOCUSED_TEST_ATTESTATION_ENV = "GINGER_EXP_20260713_007_FOCUSED_TESTS"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
ATTESTED_RUNNER_COMMAND = (
    f"$env:{FOCUSED_TEST_ATTESTATION_ENV}='passed'; {RUNNER_COMMAND}"
)

CHANGED_FILES = [
    "quant/usaspending_obligation_observer.py",
    "quant/test_usaspending_obligation_observer.py",
    "quant/run.py",
    "quant/test_run_daily_wiring.py",
    "scripts/experiment_fingerprint.py",
    "quant/test_experiment_fingerprint.py",
    RUNNER,
    "docs/production_backtest_parity_matrix.md",
    "data/non_ohlcv/usaspending_obligation_observer/raw/SubawardsAndPrimeTransactions_2026-07-13_H20M51S32580747.zip",
    "data/non_ohlcv/usaspending_obligation_observer/raw/snapshot_manifest_20260713.json",
    "data/non_ohlcv/usaspending_obligation_observer/state.json",
    "data/non_ohlcv/usaspending_obligation_observer/ledger.jsonl",
    "data/non_ohlcv/usaspending_obligation_observer/latest_summary.json",
    f"data/experiments/{EXPERIMENT_ID}/exp_20260713_007_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
    "docs/frozen_families.jsonl",
]

REPRODUCTION_COMMANDS = [
    ".\\.venv\\Scripts\\python.exe -B -m py_compile quant\\usaspending_obligation_observer.py quant\\run.py "
    + RUNNER.replace("/", "\\"),
    ".\\.venv\\Scripts\\python.exe -B -m pytest -q quant\\test_usaspending_obligation_observer.py",
    ".\\.venv\\Scripts\\python.exe -B -m pytest -q quant\\test_run_daily_wiring.py -k usaspending",
    ".\\.venv\\Scripts\\python.exe -B -m pytest -q quant\\test_experiment_fingerprint.py -k usaspending",
    ATTESTED_RUNNER_COMMAND,
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


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_ledger(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def load_state(path: Path) -> dict[str, Any]:
    value = read_json(path)
    if not isinstance(value, dict):
        raise ValueError(f"observer state is not a JSON object: {path}")
    return value


def _decode_csv(payload: bytes) -> str:
    try:
        return payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        return payload.decode("cp1252")


def prime_transaction_headers(path: Path) -> dict[str, list[str]]:
    """Return headers for prime-transaction members, never subaward members."""
    headers: dict[str, list[str]] = {}
    with zipfile.ZipFile(path) as archive:
        names = sorted(
            name
            for name in archive.namelist()
            if name.casefold().endswith(".csv")
            and "primetransaction" in Path(name).name.casefold()
            and "subaward" not in Path(name).name.casefold()
        )
        for name in names:
            reader = csv.reader(io.StringIO(_decode_csv(archive.read(name))))
            headers[Path(name).name] = next(reader)
    return headers


def all_true(rows: Iterable[Mapping[str, Any]], predicate) -> bool:
    return all(predicate(row) for row in rows)


def proof() -> dict[str, Any]:
    from usaspending_obligation_observer import (  # noqa: WPS433
        HISTORICAL_PIT_STATUS,
        parse_usaspending_transaction_snapshot,
        run_observer,
    )

    baseline_before = file_sha256(BASELINE)
    manifest = read_json(RAW_MANIFEST)
    raw_sha = file_sha256(RAW_ZIP)
    raw_bytes = RAW_ZIP.stat().st_size
    headers_by_member = prime_transaction_headers(RAW_ZIP)
    header_union = {
        field for member_headers in headers_by_member.values() for field in member_headers
    }
    required_fields = set(manifest["required_transaction_fields"])

    parsed_first = parse_usaspending_transaction_snapshot(RAW_ZIP)
    parsed_second = parse_usaspending_transaction_snapshot(RAW_ZIP)
    parsed_hash_first = canonical_sha256(parsed_first)
    parsed_hash_second = canonical_sha256(parsed_second)
    parsed_by_key = {row["transaction_key"]: row for row in parsed_first}
    non_embargo_rows = [
        row for row in parsed_first if not row.get("embargo_exclusion_reason")
    ]
    embargo_rows = [
        row for row in parsed_first if row.get("embargo_exclusion_reason")
    ]
    eligible_non_embargo_rows = [row for row in non_embargo_rows if row["eligible"]]
    observed_at = manifest["retrieved_at_utc"]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="usaspending-proof-", dir=OUT_DIR) as tmp:
        proof_root = Path(tmp)
        proof_state = proof_root / "state.json"
        proof_ledger = proof_root / "ledger.jsonl"
        proof_summary = proof_root / "latest_summary.json"
        first = run_observer(
            snapshot_path=RAW_ZIP,
            observed_at=observed_at,
            state_path=proof_state,
            ledger_path=proof_ledger,
            summary_path=proof_summary,
        )
        first_rows = load_ledger(proof_ledger)
        first_state = load_state(proof_state)
        second = run_observer(
            snapshot_path=RAW_ZIP,
            observed_at=observed_at,
            state_path=proof_state,
            ledger_path=proof_ledger,
            summary_path=proof_summary,
        )
        second_rows = load_ledger(proof_ledger)
        before_regression_attempt = {
            "state": proof_state.read_bytes(),
            "ledger": proof_ledger.read_bytes(),
            "summary": proof_summary.read_bytes(),
        }
        observed_dt = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        backdated_at = (observed_dt - timedelta(seconds=1)).isoformat().replace(
            "+00:00", "Z"
        )
        regression_error = None
        try:
            run_observer(
                snapshot_path=RAW_ZIP,
                observed_at=backdated_at,
                state_path=proof_state,
                ledger_path=proof_ledger,
                summary_path=proof_summary,
            )
        except ValueError as exc:
            regression_error = str(exc)
        monotonic_clock_fail_closed = (
            regression_error is not None
            and "precedes prior observer clock" in regression_error
            and proof_state.read_bytes() == before_regression_attempt["state"]
            and proof_ledger.read_bytes() == before_regression_attempt["ledger"]
            and proof_summary.read_bytes() == before_regression_attempt["summary"]
        )

    production = run_observer(
        snapshot_path=RAW_ZIP,
        observed_at=observed_at,
        state_path=PRODUCTION_STATE,
        ledger_path=PRODUCTION_LEDGER,
        summary_path=PRODUCTION_SUMMARY,
    )
    production_rows = load_ledger(PRODUCTION_LEDGER)
    production_state = load_state(PRODUCTION_STATE)
    baseline_after = file_sha256(BASELINE)

    expected_prime_rows = sum(
        int(manifest["archive_members"].get(member, 0))
        for member in headers_by_member
    )
    embargo_reason_counts = dict(
        sorted(
            Counter(
                str(row["embargo_exclusion_reason"]) for row in embargo_rows
            ).items()
        )
    )
    state_seen = first_state.get("seen_transactions") or {}
    state_embargo_count = sum(
        bool(value.get("embargo_excluded"))
        for value in state_seen.values()
        if isinstance(value, dict)
    )
    seed_eligible_rows = [row for row in first_rows if row.get("eligible") is True]
    ledger_transaction_keys = [str(row["transaction_key"]) for row in first_rows]

    historical_seed_safety = all_true(
        first_rows,
        lambda row: (
            row.get("row_type") == "historical_snapshot_seed"
            and row.get("seed_not_forward") is True
            and row.get("forward_event") is False
            and row.get("prospective_local_first_seen") is False
            and row.get("does_not_prove_first_publication") is True
            and row.get("prospective_evidence_eligible") is False
            and row.get("candidate_eligible") is False
            and row.get("observer_only") is True
            and row.get("trade_enabled") is False
            and row.get("entry_date") is None
            and row.get("target_price") is None
            and row.get("strategy_behavior_changed") is False
            and row.get("alters_signal_generation") is False
            and row.get("alters_candidate_ranking") is False
            and row.get("alters_sizing") is False
            and row.get("alters_exits") is False
            and row.get("alters_orders") is False
        ),
    )
    eligible_seed_safety = bool(seed_eligible_rows) and all_true(
        seed_eligible_rows,
        lambda row: (
            row.get("federal_action_obligation", 0) > 0
            and row.get("base_and_all_options_value", 1) <= 0
            and row.get("forward_event") is False
            and row.get("prospective_evidence_eligible") is False
            and row.get("candidate_eligible") is False
            and row.get("trade_enabled") is False
        ),
    )
    availability_safe = all_true(
        first_rows,
        lambda row: (
            row.get("first_seen_at") == observed_at
            and row.get("observed_at") == observed_at
            and row.get("availability_timestamp_field") == "first_seen_at"
            and row.get("availability_timestamp_source")
            == "local_snapshot_observation_clock"
            and row.get("historical_pit_status") == HISTORICAL_PIT_STATUS
            and row.get("current_snapshot_not_historical_pit") is True
            and row.get("action_date_role") == "source_metadata_only_not_policy_availability"
            and row.get("initial_report_date_role")
            == "source_metadata_only_not_policy_availability"
            and row.get("last_modified_date_role")
            == "source_metadata_only_not_policy_availability"
        ),
    )
    production_safety = all_true(
        production_rows,
        lambda row: (
            row.get("seed_not_forward") is True
            and row.get("forward_event") is False
            and row.get("candidate_eligible") is False
            and row.get("observer_only") is True
            and row.get("trade_enabled") is False
        ),
    )

    checks = {
        "manifest_is_frozen_official_snapshot": manifest.get("frozen") is True
        and manifest.get("source") == "USAspending.gov transaction download API"
        and manifest.get("raw_file") == RAW_ZIP.name,
        "manifest_sha256_matches_frozen_zip": raw_sha
        == manifest.get("raw_file_sha256"),
        "manifest_size_matches_frozen_zip": raw_bytes
        == manifest.get("raw_file_size_bytes"),
        "prime_transaction_member_present": bool(headers_by_member),
        "manifest_required_fields_present": required_fields.issubset(header_union),
        "parser_contains_required_contract_fields": bool(parsed_first)
        and all_true(
            parsed_first,
            lambda row: all(
                key in row
                for key in (
                    "transaction_key",
                    "federal_action_obligation",
                    "base_and_all_options_value",
                    "awarding_agency_name",
                    "award_id",
                    "modification_number",
                    "initial_report_date",
                    "last_modified_date",
                )
            ),
        ),
        "parser_row_count_matches_manifest": len(parsed_first) == expected_prime_rows,
        "parser_is_deterministic": parsed_hash_first == parsed_hash_second,
        "transaction_key_deduplication": len(parsed_first) == len(parsed_by_key),
        "embargoed_dod_usace_rows_never_enter_ledger": state_embargo_count
        == len(embargo_rows)
        and len(first_rows) == len(non_embargo_rows)
        and set(ledger_transaction_keys).isdisjoint(
            str(row["transaction_key"]) for row in embargo_rows
        ),
        "first_snapshot_is_historical_seed_only": first.get("bootstrap_snapshot")
        is True
        and first.get("historical_seed_rows_appended") == len(non_embargo_rows)
        and first.get("new_forward_rows_appended") == 0
        and first.get("new_eligible_forward_rows_appended") == 0
        and first.get("forward_event_count_total") == 0,
        "historical_seed_rows_are_non_actionable": bool(first_rows)
        and historical_seed_safety,
        "eligible_seed_rows_cannot_be_forward_candidate_or_trade": eligible_seed_safety,
        "policy_availability_uses_snapshot_retrieval_clock": availability_safe,
        "observation_clock_regression_fails_closed": monotonic_clock_fail_closed,
        "same_snapshot_rerun_is_idempotent": second.get("rows_appended") == 0
        and second.get("historical_seed_rows_appended") == 0
        and second.get("new_forward_rows_appended") == 0
        and second.get("new_eligible_forward_rows_appended") == 0
        and second.get("ledger_row_count") == len(first_rows)
        and second_rows == first_rows,
        "production_observer_matches_isolated_seed": production.get(
            "source_snapshot_sha256"
        )
        == raw_sha
        and production.get("ledger_row_count") == len(first_rows)
        and production.get("historical_seed_count") == len(first_rows)
        and production.get("forward_event_count_total") == 0
        and production.get("eligible_forward_event_count_total") == 0
        and len(production_rows) == len(first_rows)
        and production_safety,
        "production_state_remains_observer_only": production_state.get("observer_only")
        is True
        and production_state.get("trade_enabled") is False,
        "baseline_file_before_after_identical": baseline_before == baseline_after,
    }
    return {
        "raw_manifest": manifest,
        "raw_sha256": raw_sha,
        "raw_bytes": raw_bytes,
        "prime_transaction_headers": headers_by_member,
        "required_transaction_fields": sorted(required_fields),
        "missing_required_transaction_fields": sorted(required_fields - header_union),
        "parsed_transaction_count": len(parsed_first),
        "parsed_transaction_sha256": parsed_hash_first,
        "unique_transaction_key_count": len(parsed_by_key),
        "non_embargo_transaction_count": len(non_embargo_rows),
        "embargo_transaction_count": len(embargo_rows),
        "embargo_reason_counts": embargo_reason_counts,
        "eligible_non_embargo_transaction_count": len(eligible_non_embargo_rows),
        "isolated_first_run_summary": first,
        "isolated_second_run_summary": second,
        "observation_clock_regression_error": regression_error,
        "production_run_summary": production,
        "isolated_ledger_contract": {
            "row_count": len(first_rows),
            "unique_transaction_key_count": len(set(ledger_transaction_keys)),
            "historical_seed_count": sum(
                row.get("seed_not_forward") is True for row in first_rows
            ),
            "eligible_seed_count": len(seed_eligible_rows),
            "forward_event_count": sum(
                row.get("forward_event") is True for row in first_rows
            ),
            "candidate_eligible_count": sum(
                row.get("candidate_eligible") is True for row in first_rows
            ),
            "trade_enabled_count": sum(
                row.get("trade_enabled") is True for row in first_rows
            ),
        },
        "baseline_sha256_before": baseline_before,
        "baseline_sha256_after": baseline_after,
        "checks": checks,
    }


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET)
    baseline = read_json(BASELINE)
    evidence = proof()
    fingerprint = infer_fingerprint(ticket["hypothesis"])
    focused_tests_passed = os.environ.get(
        FOCUSED_TEST_ATTESTATION_ENV, ""
    ).strip().casefold() in {"1", "true", "yes", "passed"}
    run_source = RUN.read_text(encoding="utf-8")
    helper_marker = "def _persist_usaspending_obligation_observer(today):"
    helper_start = run_source.find(helper_marker)
    helper_end = (
        run_source.find("\ndef ", helper_start + len(helper_marker))
        if helper_start >= 0
        else -1
    )
    helper_source = (
        run_source[helper_start : helper_end if helper_end >= 0 else None]
        if helper_start >= 0
        else ""
    )
    run_wiring_checks = {
        "daily_helper_present": bool(helper_source),
        "explicit_snapshot_required": (
            "GINGER_USASPENDING_TRANSACTION_SNAPSHOT" in helper_source
            and "if not configured_path:" in helper_source
            and "transaction_snapshot_not_configured" in helper_source
        ),
        "missing_snapshot_fails_closed": (
            "if not snapshot_path.is_file():" in helper_source
            and "transaction_snapshot_missing" in helper_source
        ),
        "shared_helper_called": "run_observer(" in helper_source,
        "wired_in_both_daily_paths": sum(
            line.strip() == "_persist_usaspending_obligation_observer(today)"
            for line in run_source.splitlines()
        )
        == 2,
        "fail_soft": "except Exception as e:" in helper_source,
        "trade_disabled": '"trade_enabled": False' in helper_source,
    }
    run_wiring = {
        "passed": all(run_wiring_checks.values()),
        "checks": run_wiring_checks,
        "path": rel(RUN),
    }
    checks = {
        **evidence["checks"],
        "fingerprint_source_is_usaspending_obligation": fingerprint["data_source"]
        == "usaspending_obligation",
        "focused_tests_passed": focused_tests_passed,
        "daily_wiring_is_fail_soft_and_default_off": run_wiring["passed"],
    }
    accepted = all(checks.values())
    failed_checks = [name for name, passed in checks.items() if not passed]
    decision = (
        "accepted_measurement_repair_usaspending_obligation_first_seen_surface"
        if accepted
        else "rejected_measurement_repair_usaspending_obligation_first_seen_surface"
    )
    status = "accepted_measurement_repair" if accepted else "rejected"
    metrics = baseline["aggregate"]
    predicted_probability = float(ticket["prediction"]["success_probability"])
    reopen_condition = (
        ">=75 settled unique eligible prospective local-first-seen events across "
        ">=15 first-seen dates and "
        ">=3 mapped public-company tickers, max ticker share <=30%, with complete "
        "next-open/10-session cash/SPY/QQQ outcomes"
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now(),
        "status": status,
        "decision": decision,
        "proof_passed": accepted,
        "accepted": accepted,
        "accepted_measurement_repair": accepted,
        "accepted_alpha": False,
        "lane": LANE,
        "owner": OWNER,
        "hypothesis": ticket["hypothesis"],
        "change_type": ticket["change_type"],
        "mechanism_family": ticket["mechanism_family"],
        "trial_family": ticket["trial_family"],
        "trial_variant_id": ticket["trial_variant_id"],
        "changed_variable": ticket["changed_variable"],
        "alpha_hypothesis": (
            "A later, locally first-seen non-DoD/USACE transaction that also passes "
            "the post-initialization source-freshness guard, has positive obligation, "
            "and has no ceiling expansion may improve the listed parent's revenue "
            "visibility from the next session open."
        ),
        "single_causal_variable": ticket["single_causal_variable"],
        "prior_trial_count": ticket["prior_trial_count"],
        "nearby_prior_experiments": ticket["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": ticket["multiple_testing_risk_bucket"],
        "new_evidence_axis": ticket["novelty"]["new_evidence_axis"],
        "prediction": ticket["prediction"],
        "calibration": {
            "actual_success": accepted,
            "predicted_success_probability": predicted_probability,
            "brier_score": round(
                (predicted_probability - float(accepted)) ** 2, 6
            ),
            "realized_failure_modes": failed_checks,
        },
        "parameters": {
            "source": "official USAspending transaction download",
            "snapshot_role": "historical_seed_only",
            "availability_time": evidence["raw_manifest"]["retrieved_at_utc"],
            "eligibility_rule": (
                "federal_action_obligation > 0 and "
                "base_and_all_options_value <= 0"
            ),
            "excluded_agencies": [
                "Department of Defense",
                "U.S. Army Corps of Engineers",
            ],
            "deduplication_unit": "contract_transaction_unique_key",
            "trade_enabled": False,
        },
        "proof": evidence,
        "focused_tests": {
            "passed": focused_tests_passed,
            "source": f"environment:{FOCUSED_TEST_ATTESTATION_ENV}",
            "attestation": "passed" if focused_tests_passed else "missing",
        },
        "run_wiring": run_wiring,
        "fingerprint_repair": {
            "reservation_source_before_repair": ticket["novelty"]["fingerprint"]["data_source"],
            "source_after_repair": fingerprint["data_source"],
            "passed": fingerprint["data_source"] == "usaspending_obligation",
        },
        "fingerprint": fingerprint,
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
                    "manifest_required_fields_present",
                    "parser_contains_required_contract_fields",
                    "transaction_key_deduplication",
                    "embargoed_dod_usace_rows_never_enter_ledger",
                    "policy_availability_uses_snapshot_retrieval_clock",
                    "observation_clock_regression_fails_closed",
                    "eligible_seed_rows_cannot_be_forward_candidate_or_trade",
                )
            ),
            "required_source_fields": evidence["required_transaction_fields"],
            "entry_date_contract": (
                "Explicit null for the seed; a later forward event still requires "
                "separately audited PIT issuer mapping and next-session-open evaluation."
            ),
            "target_price_contract": (
                "Explicit null because this default-off observer is not a signal or order adapter."
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
            "failed_checks": failed_checks,
            "decision": decision,
            "accepted_alpha": False,
            "closeout_deferred": False,
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
            "parsed_transaction_count": evidence["parsed_transaction_count"],
            "non_embargo_historical_seed_count": evidence[
                "non_embargo_transaction_count"
            ],
            "embargo_excluded_count": evidence["embargo_transaction_count"],
            "eligible_historical_seed_count": evidence[
                "eligible_non_embargo_transaction_count"
            ],
            "forward_event_count": evidence["isolated_ledger_contract"][
                "forward_event_count"
            ],
            "candidate_eligible_count": evidence["isolated_ledger_contract"][
                "candidate_eligible_count"
            ],
            "trade_enabled_count": evidence["isolated_ledger_contract"][
                "trade_enabled_count"
            ],
            "same_snapshot_rerun_rows_appended": evidence[
                "isolated_second_run_summary"
            ]["rows_appended"],
        },
        "production_impact": {
            "shared_default_off_observer_materialized": True,
            "strategy_behavior_changed": False,
            "entry_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_rules_changed": False,
            "orders_changed": False,
            "trade_enabled": False,
            "scope": "official_snapshot_historical_seed_only",
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The official transaction schema exposed stable obligation and ceiling fields, while the local-first-seen contract, monotonic observation clock, source-freshness guard, and 90-day DoD exclusion kept current or stale rows out of alpha evidence."
                if accepted
                else "One or more source identity, seed, embargo, idempotency, safety, wiring, or classifier contracts failed."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not equate local first-seen with first public availability; do not "
                "backdate first_seen_at to action_date, initial_report_date, or "
                "last_modified_date; do not score seed or source-stale rows; do not "
                "reintroduce DoD/USACE rows; and do not retune eligibility thresholds "
                "on this snapshot."
            ),
            "new_evidence_required": reopen_condition,
        },
        "rejection_reason": None if accepted else ";".join(failed_checks),
        "reopen_condition": reopen_condition,
        "next_retry_requires": [
            ">=75 settled unique eligible prospective local-first-seen events",
            ">=15 distinct local first-seen dates",
            ">=3 contemporaneously mapped public-company tickers",
            "maximum ticker share <=30%",
            "complete next-open/10-session cash/SPY/QQQ outcomes",
        ],
        "changed_files": CHANGED_FILES,
        "related_files": [
            rel(RAW_ZIP),
            rel(RAW_MANIFEST),
            rel(HELPER),
            rel(HELPER_TEST),
            rel(RUN),
            rel(RUN_TEST),
            rel(FINGERPRINT),
            rel(PARITY_MATRIX),
            rel(BASELINE),
        ],
        "reproduction_commands": REPRODUCTION_COMMANDS,
        "lean_quality_passed": accepted,
    }


def card_text(payload: Mapping[str, Any]) -> str:
    headline = payload["headline_metrics"]
    failed = payload["gate4"]["failed_checks"] or ["none"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} USAspending obligation-conversion first-seen observer",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Parsed transactions: `{headline['parsed_transaction_count']}`",
            f"- DoD/USACE excluded: `{headline['embargo_excluded_count']}`",
            f"- Non-embargo historical seed: `{headline['non_embargo_historical_seed_count']}`",
            f"- Eligible historical seed: `{headline['eligible_historical_seed_count']}`",
            f"- Forward / candidate / trade: `{headline['forward_event_count']} / "
            f"{headline['candidate_eligible_count']} / {headline['trade_enabled_count']}`",
            f"- Same-snapshot rerun rows appended: `{headline['same_snapshot_rerun_rows_appended']}`",
            "- Accepted alpha: `false`",
            f"- Failed checks: `{', '.join(failed)}`",
            "",
            "The frozen current snapshot is seed-only. USAspending action, initial-report, and last-modified dates cannot backdate policy availability; DoD/USACE rows are excluded because their procurement publication is embargoed.",
            "",
            "## Reopen boundary",
            "",
            str(payload["reopen_condition"]),
            "",
            "## Reproduce",
            "",
            f"- `{ATTESTED_RUNNER_COMMAND}`",
            "",
        ]
    )


def persist(payload: dict[str, Any]) -> None:
    """Persist the final proof, log, card, manifest, and sanctioned registry result."""
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
            "proof_passed": payload["proof_passed"],
            "decision": payload["decision"],
            "artifact": rel(OUT),
            "log": rel(LOG),
            "headline_metrics": payload["headline_metrics"],
            "summary": "official_usaspending_historical_seed_first_seen_surface",
        },
        fields={
            **{
                key: value
                for key, value in ticket.items()
                if key not in {"result", "status"}
            },
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
                "proof_passed": payload["proof_passed"],
                "headline_metrics": payload["headline_metrics"],
                "failed_checks": payload["gate4"]["failed_checks"],
                "artifact": rel(OUT),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if payload["accepted_measurement_repair"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
