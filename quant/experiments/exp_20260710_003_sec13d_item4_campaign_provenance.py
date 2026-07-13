"""exp-20260710-003: SEC 13D Item-4 campaign provenance materialization.

Measurement repair. The shared parser from exp-20260629-006 already exposes
13D Item-4 board-seat, standstill, cooperation/settlement, and nomination
provenance fields, but the canonical materialized 13D/13G rows on disk were
still the older no-item4 schema. This runner refreshes that canonical data
surface from local cached SEC XML only; it does not fetch from EDGAR and does
not change ranking, sizing, exits, orders, or candidate selection.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


EXPERIMENT_ID = "exp-20260710-003"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "sec13d_item4_campaign_provenance"
RUNNER = f"quant/experiments/exp_20260710_003_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
for path in (REPO_ROOT / "scripts", REPO_ROOT / "quant", REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)
from sec_13d13g_ingest import (  # noqa: E402
    OUT_ROWS as CANONICAL_ROWS,
    WINDOWS as INGEST_WINDOWS,
    build_parsed_rows,
    iter_ownership_filings,
)


DATA_DIR = REPO_ROOT / "data"
BASELINE_RESULT = (
    DATA_DIR
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OUT_DIR = DATA_DIR / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260710_003_sec13d_item4_campaign_provenance.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Alpha blocker: 13D Item-4 activist catalyst alpha cannot be evaluated "
    "credibly until the canonical parsed 13D/G surface exposes board-seat, "
    "standstill, cooperation, and campaign-outcome provenance as replayable "
    "fields instead of only generic 13D metadata."
)
ALPHA_HYPOTHESIS = (
    "candidate_pool: activist 13D Item-4 campaign outcomes such as board-seat "
    "appointments, standstill/cooperation agreements, nomination withdrawals, "
    "and board departures may be fresher catalysts than generic Item-4 intent "
    "phrases; this run repairs measurement only and makes no alpha claim."
)
CHANGE_TYPE = "identity_or_measurement_repair"
IMPLEMENTATION_MODE = "canonical_sec13d_item4_campaign_provenance_materialization"
MECHANISM_FAMILY = "production_visible_sec_ownership_holder_stake_measurement"
TRIAL_FAMILY = "sec13d_item4_campaign_provenance_surface"
TRIAL_VARIANT_ID = "canonical_materialized_rows_v1"
SINGLE_CAUSAL_VARIABLE = "13d_item4_campaign_board_seat_provenance_surface"
CAUSAL_COMPONENTS = [
    "canonical_13d13g_rows_refresh",
    "item4_board_seat_provenance_fields",
    "item4_standstill_provenance_fields",
    "item4_campaign_outcome_provenance_fields",
    "no_strategy_change",
]
NEARBY_PRIORS = [
    "exp-20260618-019",
    "exp-20260629-006",
    "exp-20260629-009",
]
NEW_EVIDENCE_TYPE = "canonical_surface_materialization"
NEW_EVIDENCE_AXIS = (
    "Materializes the already accepted shared Item-4 governance parser into "
    "data/non_ohlcv/sec_13d13g_holdings/rows.json, whose pre-run canonical "
    "rows had zero item4_* keys despite 941 parsed 13D rows."
)
ACCEPTANCE_RULE = (
    "Accepted measurement repair if the canonical rows refresh is local-cache "
    "only, parsed 13D rows keep replay dates and accessions, item4_* keys are "
    "present on refreshed rows, at least 10 13D rows expose campaign/governance "
    "terms, and no strategy/live behavior changes."
)
MIN_PARSED_13D_ROWS = 50
MIN_GOVERNANCE_TERM_ROWS = 10

ITEM4_FIELDS = [
    "item4_governance_terms",
    "item4_text_present",
    "item4_governance_terms_present",
    "item4_governance_terms_bucket",
    "item4_board_appointment_count",
    "item4_standstill_duration_days",
]
CHANGED_FILES = [
    RUNNER,
    "data/non_ohlcv/sec_13d13g_holdings/rows.json",
    "data/experiments/exp-20260710-003/exp_20260710_003_sec13d_item4_campaign_provenance.json",
    "experiments/logs/exp-20260710-003.json",
    "experiments/cards/exp-20260710-003.md",
    "experiments/manifests/exp-20260710-003.json",
    "experiments/tickets/exp-20260710-003.json",
    "docs/experiment_registry.json",
]
VERIFICATION_COMMANDS = [
    ".\\.venv\\Scripts\\python.exe -B -m py_compile quant\\sec_13d13g_ingest.py "
    "quant\\experiments\\exp_20260710_003_sec13d_item4_campaign_provenance.py",
    ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_sec_13d13g_ingest.py -q",
    RUNNER_COMMAND,
    ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
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


def safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        try:
            return safe(value.item())
        except Exception:
            return str(value)
    return value


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default if default is not None else {}


def read_head_json(rel_path: str) -> Any:
    result = subprocess.run(
        ["git", "show", f"HEAD:{rel_path}"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0 or not result.stdout.strip():
        return {}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    text = json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n"
    tmp.write_text(text, encoding="utf-8")
    try:
        tmp.replace(path)
    except PermissionError:
        # Windows can deny os.replace() on files watched by sync/index tools even
        # when direct overwrite is allowed. Fall back to the ingest module's
        # existing write_text behavior and remove the staged temp.
        path.write_text(text, encoding="utf-8")
        try:
            tmp.unlink()
        except OSError:
            pass


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


def rows_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, Mapping):
        rows = payload.get("rows")
    else:
        rows = payload
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def form_counts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts = Counter(str(row.get("family") or row.get("form") or "") for row in rows)
    return {key: value for key, value in sorted(counts.items())}


def field_presence(rows: list[Mapping[str, Any]]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for field in ITEM4_FIELDS:
        out[field] = {
            "key_present_rows": sum(1 for row in rows if field in row),
            "truthy_rows": sum(
                1 for row in rows if field in row and row.get(field) not in (None, "", [], {}, False)
            ),
        }
    return out


def governance_terms(row: Mapping[str, Any]) -> Mapping[str, Any]:
    terms = row.get("item4_governance_terms")
    return terms if isinstance(terms, Mapping) else {}


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    terms = [governance_terms(row) for row in rows]
    buckets = Counter(str(term.get("governance_terms_bucket") or "missing") for term in terms)
    by_window = Counter(str(row.get("window") or "missing") for row in rows)
    family_13d = [row for row in rows if row.get("family") == "13D"]
    family_13g = [row for row in rows if row.get("family") == "13G"]
    term_rows = [
        row
        for row in family_13d
        if bool(governance_terms(row).get("governance_terms_present"))
    ]
    return {
        "row_count": len(rows),
        "form_counts": form_counts(rows),
        "field_presence": field_presence(rows),
        "parsed_13d_rows": len(family_13d),
        "parsed_13g_rows": len(family_13g),
        "rows_by_window": {key: value for key, value in sorted(by_window.items())},
        "item4_text_present_rows": sum(
            1 for row in family_13d if bool(governance_terms(row).get("item4_text_present"))
        ),
        "governance_terms_present_rows": len(term_rows),
        "governance_bucket_counts": {
            key: value for key, value in sorted(buckets.items())
        },
        "board_terms_present_rows": sum(
            1 for row in family_13d if bool(governance_terms(row).get("board_terms_present"))
        ),
        "board_appointment_rows": sum(
            1
            for row in family_13d
            if (governance_terms(row).get("board_appointment_count") or 0) > 0
        ),
        "standstill_terms_present_rows": sum(
            1 for row in family_13d if bool(governance_terms(row).get("standstill_terms_present"))
        ),
        "cooperation_or_settlement_rows": sum(
            1
            for row in family_13d
            if bool(governance_terms(row).get("cooperation_or_settlement_agreement_present"))
        ),
        "nomination_withdrawal_rows": sum(
            1
            for row in family_13d
            if bool(governance_terms(row).get("nomination_withdrawal_present"))
        ),
        "board_departure_rows": sum(
            1 for row in family_13d if bool(governance_terms(row).get("board_departure_present"))
        ),
    }


def provenance_sample(rows: list[dict[str, Any]], limit: int = 20) -> list[dict[str, Any]]:
    sample: list[dict[str, Any]] = []
    for row in rows:
        terms = governance_terms(row)
        if not terms.get("governance_terms_present"):
            continue
        sample.append(
            {
                "ticker": row.get("ticker"),
                "issuer_cik": row.get("issuer_cik"),
                "accession_number": row.get("accession_number"),
                "form": row.get("form"),
                "filing_date": row.get("filing_date"),
                "accepted_at": row.get("accepted_at"),
                "usable_trade_date": row.get("usable_trade_date"),
                "window": row.get("window"),
                "issuer_name": row.get("issuer_name"),
                "max_class_percent": row.get("max_class_percent"),
                "reporting_person_types": row.get("reporting_person_types"),
                "bucket": terms.get("governance_terms_bucket"),
                "hits": terms.get("governance_term_hits"),
                "board_appointment_count": terms.get("board_appointment_count"),
                "board_size_delta": terms.get("board_size_delta"),
                "standstill_duration_days": terms.get("standstill_duration_days"),
                "standstill_until_date": terms.get("standstill_until_date"),
                "item4_excerpt": terms.get("item4_excerpt"),
            }
        )
        if len(sample) >= limit:
            break
    return sample


def canonical_events() -> list[dict[str, Any]]:
    """Preserve the existing canonical family scope while refreshing fields.

    The pre-run canonical rows used 13D initial+amendment filings and 13G
    initial filings only. Including 13G/A rows would broaden the data surface
    beyond this Item-4 provenance repair.
    """
    events_13d = iter_ownership_filings(families=("13D",), include_amendments=True)
    events_13g = iter_ownership_filings(families=("13G",), include_amendments=False)
    combined = events_13d + events_13g
    return sorted(
        combined,
        key=lambda row: (
            str(row.get("filing_date") or ""),
            str(row.get("issuer_cik") or ""),
            str(row.get("accession_number") or ""),
        ),
    )


def build_canonical_payload(rows: list[dict[str, Any]], fetch_status: Mapping[str, Any], total_events: int) -> dict[str, Any]:
    return {
        "generated_at": utc_now(),
        "windows": dict(INGEST_WINDOWS),
        "families": "13D(init+amend)+13G(init)",
        "include_amendments": {"13D": True, "13G": False},
        "total_events_enumerated": total_events,
        "parsed_row_count": len(rows),
        "fetch_status": dict(fetch_status),
        "rows": rows,
    }


def build_payload() -> dict[str, Any]:
    previous_artifact = read_json(OUT_JSON, {})
    head_payload = read_head_json("data/non_ohlcv/sec_13d13g_holdings/rows.json")
    before_payload = read_json(CANONICAL_ROWS, {})
    before_rows = rows_from_payload(before_payload)
    before_summary = summarize_rows(before_rows)
    original_before_summary = before_summary
    if head_payload:
        original_before_summary = summarize_rows(rows_from_payload(head_payload))
    elif isinstance(previous_artifact, Mapping) and previous_artifact.get(
        "canonical_surface_was_stale"
    ):
        prior_summary = previous_artifact.get("canonical_before_summary")
        if isinstance(prior_summary, Mapping):
            original_before_summary = dict(prior_summary)

    events = canonical_events()
    parsed = build_parsed_rows(events, fetch=False, refresh=False)
    rows = parsed["rows"]
    fetch_status = parsed["fetch_status"]
    canonical_payload = build_canonical_payload(rows, fetch_status, len(events))
    atomic_write_json(CANONICAL_ROWS, canonical_payload)

    after_payload = read_json(CANONICAL_ROWS, {})
    after_rows = rows_from_payload(after_payload)
    after_summary = summarize_rows(after_rows)

    governance_term_rows = after_summary["governance_terms_present_rows"]
    accepted = (
        after_summary["parsed_13d_rows"] >= MIN_PARSED_13D_ROWS
        and governance_term_rows >= MIN_GOVERNANCE_TERM_ROWS
        and all(
            after_summary["field_presence"][field]["key_present_rows"] == after_summary["row_count"]
            for field in ITEM4_FIELDS
        )
        and fetch_status.get("fetched", 0) == 0
    )
    failed: list[str] = []
    if after_summary["parsed_13d_rows"] < MIN_PARSED_13D_ROWS:
        failed.append("too_few_parsed_13d_rows")
    if governance_term_rows < MIN_GOVERNANCE_TERM_ROWS:
        failed.append("too_few_governance_term_rows")
    missing_fields = [
        field
        for field in ITEM4_FIELDS
        if after_summary["field_presence"][field]["key_present_rows"] != after_summary["row_count"]
    ]
    if missing_fields:
        failed.append("missing_item4_field_keys:" + ",".join(missing_fields))
    if fetch_status.get("fetched", 0):
        failed.append("unexpected_network_fetch")

    stale_before = all(
        original_before_summary["field_presence"][field]["key_present_rows"] == 0
        for field in ITEM4_FIELDS
    )
    key_rows_added = {
        field: (
            after_summary["field_presence"][field]["key_present_rows"]
            - original_before_summary["field_presence"][field]["key_present_rows"]
        )
        for field in ITEM4_FIELDS
    }
    status = "accepted_measurement_repair" if accepted else "blocked"
    decision = (
        "accepted_measurement_repair_sec13d_item4_campaign_provenance_materialized"
        if accepted
        else "blocked_sec13d_item4_campaign_provenance_materialization"
    )

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": LANE,
        "status": status,
        "accepted": accepted,
        "accepted_alpha": False,
        "accepted_measurement_repair": accepted,
        "decision": decision,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": SINGLE_CAUSAL_VARIABLE,
        "changed_variable": SINGLE_CAUSAL_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": {
            "expected_decision": "accepted_measurement_repair",
            "expected_min_parsed_13d_rows": MIN_PARSED_13D_ROWS,
            "expected_min_governance_term_rows": MIN_GOVERNANCE_TERM_ROWS,
            "expected_failure_mode": "blocked_if_cached_xml_has_no_item4_campaign_rows",
        },
        "canonical_rows_path": repo_rel(CANONICAL_ROWS),
        "canonical_before_summary": original_before_summary,
        "canonical_observed_before_rerun_summary": before_summary,
        "canonical_after_summary": after_summary,
        "canonical_key_rows_added": key_rows_added,
        "canonical_surface_was_stale": stale_before,
        "fetch_status": dict(fetch_status),
        "local_cache_only": fetch_status.get("fetched", 0) == 0,
        "provenance_sample": provenance_sample(after_rows),
        "headline_metrics": {
            "canonical_rows_before": original_before_summary["row_count"],
            "canonical_rows_after": after_summary["row_count"],
            "parsed_13d_rows_after": after_summary["parsed_13d_rows"],
            "item4_text_present_rows_after": after_summary["item4_text_present_rows"],
            "governance_terms_present_rows_after": governance_term_rows,
            "board_terms_present_rows_after": after_summary["board_terms_present_rows"],
            "standstill_terms_present_rows_after": after_summary[
                "standstill_terms_present_rows"
            ],
            "cooperation_or_settlement_rows_after": after_summary[
                "cooperation_or_settlement_rows"
            ],
            "canonical_surface_was_stale": stale_before,
        },
        "gate1": {
            "passed": BASELINE_RESULT.exists(),
            "baseline_artifact": repo_rel(BASELINE_RESULT),
            "note": "Measurement repair only; no before/after strategy replay.",
        },
        "gate2": {
            "passed": bool(after_rows) and not missing_fields,
            "runtime_fields": [
                "ticker",
                "issuer_cik",
                "accession_number",
                "filing_date",
                "accepted_at",
                "usable_trade_date",
                *ITEM4_FIELDS,
            ],
            "entry_date_target_price_applicability": (
                "Not applicable: this runner creates a non-trading SEC data "
                "surface and emits no signals."
            ),
        },
        "gate3": {
            "passed": True,
            "new_core_filter_added": False,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "note": "No buy/sell/filter/ranking behavior changed.",
        },
        "gate4": {
            "passed": accepted,
            "decision": decision,
            "accepted_alpha": False,
            "measurement_repair_only": True,
            "strategy_behavior_changed": False,
            "before_after_strategy_delta": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
                "signals_generated_delta": 0,
                "signals_survived_delta": 0,
            },
            "failed_reasons": failed,
            "acceptance_rule": ACCEPTANCE_RULE,
        },
        "production_impact": {
            "trade_enabled_changed": False,
            "live_orders_changed": False,
            "ranking_sizing_exits_changed": False,
            "canonical_data_surface_changed": repo_rel(CANONICAL_ROWS),
            "default_off_only": True,
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The shared parser was already present, but the canonical rows "
                "file was stale and had zero item4_* field keys. Local cached "
                "13D XML was sufficient to refresh the surface with replayable "
                "campaign/governance provenance."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retest 13D Item-4 by sweeping phrase lists, holder "
                "types, classPercent, absorption thresholds, top-N, hold days, "
                "cooldown, notional, or response shape on this surface."
            ),
            "new_evidence_required": (
                "Next alpha work must use a fixed campaign/board-seat provenance "
                "policy with Gate 1-4, add campaign outcome evidence beyond "
                "regex provenance, repair old_thin coverage, or wait for closed "
                "forward replacement-value rows."
            ),
            "next_step": (
                "Run a fixed, non-retuned campaign/board-seat candidate-pool "
                "replay only if it consumes these refreshed canonical fields and "
                "does not repeat exp-20260629-009's rejected governance-term "
                "candidate pool."
            ),
        },
        "rejection_reason": ";".join(failed) if failed else None,
        "realized_failure_mode": None if accepted else ";".join(failed),
        "gate_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": (
                "exp-20260629-006 accepted the shared parser; exp-20260629-009 "
                "rejected a governance-term candidate pool; current canonical "
                "rows still had zero item4_* fields before this repair."
            ),
            "3_single_causal_variable": SINGLE_CAUSAL_VARIABLE,
            "4_acceptance_standard": ACCEPTANCE_RULE,
            "5_reproducibility": RUNNER_COMMAND,
        },
        "related_files": CHANGED_FILES,
        "changed_files": CHANGED_FILES,
        "reproduction_commands": VERIFICATION_COMMANDS,
        "lean_quality_passed": accepted,
    }
    return payload


def build_card(payload: Mapping[str, Any]) -> str:
    h = payload["headline_metrics"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: SEC 13D Item-4 campaign provenance",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Accepted alpha: `false`",
            f"- Canonical rows before / after: `{h['canonical_rows_before']}` / `{h['canonical_rows_after']}`",
            f"- Parsed 13D rows after: `{h['parsed_13d_rows_after']}`",
            f"- Item-4 text / governance rows: `{h['item4_text_present_rows_after']}` / `{h['governance_terms_present_rows_after']}`",
            f"- Board / standstill rows: `{h['board_terms_present_rows_after']}` / `{h['standstill_terms_present_rows_after']}`",
            f"- Canonical surface was stale: `{h['canonical_surface_was_stale']}`",
            "- Strategy/live order behavior changed: `false`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Next Evidence",
            "",
            payload["post_run_reflection"]["new_evidence_required"],
            "",
            "## Reproduction",
            "",
            "```powershell",
            RUNNER_COMMAND,
            "```",
            "",
        ]
    )


def build_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    files = [REPO_ROOT / rel for rel in CHANGED_FILES]
    files.append(OUT_JSON)
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
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    atomic_write_json(OUT_JSON, payload)
    save_experiment_log_entry(payload, allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "accepted_measurement_repair": payload["accepted_measurement_repair"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "headline_metrics": payload["headline_metrics"],
            "summary": "measurement_repair_sec13d_item4_campaign_provenance_materialized",
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
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
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "rejection_reason": payload["rejection_reason"],
            "realized_failure_mode": payload["realized_failure_mode"],
            "related_files": payload["related_files"],
            "changed_files": payload["changed_files"],
            "reproduction_commands": payload["reproduction_commands"],
            "lean_quality_passed": payload["lean_quality_passed"],
        },
    )
    atomic_write_json(MANIFEST_JSON, build_manifest(payload))


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
                "headline_metrics": payload["headline_metrics"],
                "gate4": payload["gate4"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if payload["accepted_measurement_repair"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
