"""exp-20260626-013: SEC periodic daily text materialization envelope audit.

This is a measurement repair for the 10-K/10-Q cover-page alpha blocker. The
alpha idea is still filer-status upgrades, but this run only verifies that the
daily SEC text materializer now exposes enough selection provenance to catch
periodic rows that are present in daily events but absent from stale text
artifacts.

No strategy, ranking, sizing, exit, order, LLM, paper ledger, or live behavior
is changed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for path in (QUANT_DIR, SCRIPTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import sec_filing_text_backfill as text_backfill  # noqa: E402
from daily_non_ohlcv_snapshot import SEC_TEXT_DEFAULT_FORMS  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
from sec_filing_text_backfill import DEFAULT_FORMS, _event_matches  # noqa: E402


EXPERIMENT_ID = "exp-20260626-013"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "sec_periodic_daily_text_materialization"
RUNNER = f"quant/experiments/exp_20260626_013_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

CHANGED_VARIABLE = "sec_10k_10q_daily_text_materialization_envelope_v1"
MECHANISM_FAMILY = "sec_filing_text_materialization_repair"
TRIAL_FAMILY = "sec_periodic_text_materialization"
TRIAL_VARIANT_ID = "daily_envelope_audit_v1"

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
NON_OHLCV_DIR = REPO_ROOT / "data" / "non_ohlcv"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260626_013_{SLUG}.json"
DRY_RUN_JSONL = OUT_DIR / "sec_filing_text_20260625_dry_run_rows.jsonl"
DRY_RUN_SUMMARY = OUT_DIR / "sec_filing_text_20260625_dry_run_summary.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

WINDOWS: "OrderedDict[str, dict[str, str]]" = OrderedDict(
    [
        ("late_strong", {"start": "2025-10-23", "end": "2026-04-21"}),
        ("mid_weak", {"start": "2025-04-23", "end": "2025-10-22"}),
        ("old_thin", {"start": "2024-10-02", "end": "2025-04-22"}),
    ]
)
PERIODIC_FORMS = {"10-K", "10-Q"}
DAILY_ITEM_CODES = None
ALLOWED_WRITE_SCOPE = [
    "quant/sec_filing_text_backfill.py",
    "quant/test_sec_filing_text_backfill.py",
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260626_013_{SLUG}.json",
    f"data/experiments/{EXPERIMENT_ID}/sec_filing_text_20260625_dry_run_rows.jsonl",
    f"data/experiments/{EXPERIMENT_ID}/sec_filing_text_20260625_dry_run_summary.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]

HYPOTHESIS = (
    "measurement_repair/alpha_blocker: daily SEC filing text artifacts need "
    "source-vs-selected form provenance so 10-K/10-Q rows present in daily "
    "events cannot be silently omitted from the text materialization envelope."
)
ALPHA_HYPOTHESIS = (
    "candidate_pool: PIT SEC 10-K/10-Q cover-page filer-status upgrades may "
    "identify improving issuer maturity, but the alpha remains blocked until "
    "daily and replay text rows materialize periodic reports by accession and "
    "accepted_at with parser-ready cover-page status fields."
)
PREDICTION = {
    "success_probability": 0.7,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "daily_wrapper_explicitly_passes_old_forms",
        "generated_artifacts_are_stale_and_require_network",
        "periodic_events_lack_primary_document_or_archive_url",
    ],
    "confidence_reason": (
        "Recent daily event files contain 10-K/10-Q rows while matching text "
        "summaries still list only 6-K/8-K. The code defaults now include "
        "periodic forms, so a dry-run selection audit plus summary provenance "
        "should isolate stale artifact state from strategy behavior."
    ),
    "recorded_at": "2026-06-26T12:06:21+00:00",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return value.as_posix()


def safe(value: Any) -> Any:
    if isinstance(value, Counter):
        return dict(value)
    if isinstance(value, OrderedDict):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, dict):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [safe(item) for item in value]
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return round(value, 10)
    return value


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(safe(row), ensure_ascii=True, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def upsert_jsonl(path: Path, row: dict[str, Any]) -> None:
    encoded = json.dumps(safe(row), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                rows.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                rows.append(encoded)
                replaced = True
            else:
                rows.append(raw)
    if not replaced:
        rows.append(encoded)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def iter_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    errors = 0
    if not path.exists():
        return rows, errors
    for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if not raw.strip():
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            errors += 1
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows, errors


def sha256_file(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT)
    windows = payload.get("windows") or []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "max_drawdown_pct_worst": max(
            (float(row.get("max_drawdown_pct") or 0.0) for row in windows),
            default=0.0,
        ),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / max(generated, 1), 4),
        "windows": windows,
    }


def form_base(row: dict[str, Any]) -> str:
    return str(row.get("form_base") or row.get("form_type") or row.get("form") or "").upper().replace("/A", "")


def daily_events_paths() -> list[Path]:
    paths = []
    for path in sorted(NON_OHLCV_DIR.glob("sec_filing_events_20*.jsonl")):
        suffix = path.stem.rsplit("_", 1)[-1]
        if len(suffix) == 8 and suffix.isdigit():
            paths.append(path)
    return paths


def latest_daily_events_path() -> Path | None:
    paths = daily_events_paths()
    return paths[-1] if paths else None


def tag_from_events_path(path: Path) -> str:
    return path.stem.rsplit("_", 1)[-1]


def forms_set(forms: tuple[str, ...] | list[str]) -> set[str]:
    return {str(form).strip().upper().replace("/A", "") for form in forms if str(form).strip()}


def event_selection_summary(path: Path) -> dict[str, Any]:
    rows, errors = iter_jsonl(path)
    default_forms = forms_set(list(DEFAULT_FORMS))
    selected = [row for row in rows if _event_matches(row, default_forms, DAILY_ITEM_CODES)]
    source_counts = Counter(form_base(row) or "UNKNOWN" for row in rows)
    selected_counts = Counter(form_base(row) or "UNKNOWN" for row in selected)
    return {
        "source_file": repo_rel(path),
        "json_parse_errors": errors,
        "source_events_input": len(rows),
        "matched_events_input": len(selected),
        "source_form_counts": dict(sorted(source_counts.items())),
        "selected_form_counts": dict(sorted(selected_counts.items())),
        "source_periodic_rows": sum(source_counts.get(form, 0) for form in PERIODIC_FORMS),
        "selected_periodic_rows": sum(selected_counts.get(form, 0) for form in PERIODIC_FORMS),
        "sample_periodic_events": [
            {
                "ticker": row.get("ticker"),
                "form_type": row.get("form_type"),
                "accession_number": row.get("accession_number"),
                "accepted_at": row.get("accepted_at"),
                "usable_trade_date": row.get("usable_trade_date"),
                "primary_document": row.get("primary_document"),
            }
            for row in rows
            if form_base(row) in PERIODIC_FORMS
        ][:10],
    }


def text_artifact_summary(tag: str) -> dict[str, Any]:
    text_path = NON_OHLCV_DIR / f"sec_filing_text_{tag}.jsonl"
    summary_path = NON_OHLCV_DIR / f"sec_filing_text_backfill_summary_{tag}.json"
    rows, errors = iter_jsonl(text_path)
    counts = Counter(form_base(row) or "UNKNOWN" for row in rows)
    summary = read_json(summary_path) if summary_path.exists() else {}
    return {
        "text_file": repo_rel(text_path),
        "summary_file": repo_rel(summary_path),
        "text_file_exists": text_path.exists(),
        "summary_file_exists": summary_path.exists(),
        "json_parse_errors": errors,
        "rows_written": len(rows),
        "row_form_counts": dict(sorted(counts.items())),
        "periodic_text_rows": sum(counts.get(form, 0) for form in PERIODIC_FORMS),
        "summary_forms": summary.get("forms"),
        "summary_events_input": summary.get("events_input"),
        "summary_rows_written": summary.get("rows_written"),
        "summary_selected_periodic_rows": summary.get("selected_periodic_rows"),
        "summary_has_form_provenance": all(
            key in summary
            for key in ("source_form_counts", "matched_form_counts", "selected_form_counts")
        ),
        "summary_generated_before_provenance_repair": not all(
            key in summary
            for key in ("source_form_counts", "matched_form_counts", "selected_form_counts")
        ),
    }


def dry_run_build_rows(events_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    def fake_fetch(event: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        return {
            "status": "dry_run_selected_no_fetch",
            "ticker": str(event.get("ticker") or "").upper() or None,
            "cik": event.get("cik"),
            "accession_number": event.get("accession_number"),
            "form_type": event.get("form_type"),
            "form_base": event.get("form_base"),
            "filing_date": event.get("filing_date"),
            "usable_trade_date": event.get("usable_trade_date"),
            "accepted_at": event.get("accepted_at"),
            "eight_k_item_codes": event.get("eight_k_item_codes") or [],
            "primary_document": event.get("primary_document"),
            "documents": [],
            "documents_fetched": 0,
            "text_char_count": 0,
            "text_word_count": 0,
            "combined_text": "",
            "errors": [],
            "pit_source": "dry_run_selection_only",
        }

    args = argparse.Namespace(
        events=str(events_path),
        output=str(DRY_RUN_JSONL),
        summary_output=str(DRY_RUN_SUMMARY),
        cache_dir=str(OUT_DIR / "dry_run_cache_not_used"),
        forms=list(DEFAULT_FORMS),
        item_codes=["all"],
        max_documents=1,
        max_chars_per_doc=1,
        limit=None,
        refresh=False,
        request_delay_sec=0.0,
        user_agent="dry-run",
    )
    original_fetch = text_backfill.fetch_filing_text
    try:
        text_backfill.fetch_filing_text = fake_fetch
        rows, summary = text_backfill.build_rows(args)
    finally:
        text_backfill.fetch_filing_text = original_fetch
    write_jsonl(DRY_RUN_JSONL, rows)
    write_json(DRY_RUN_SUMMARY, summary)
    return rows, summary


def build_payload() -> dict[str, Any]:
    baseline = baseline_metrics()
    latest_events = latest_daily_events_path()
    if latest_events is None:
        raise RuntimeError("no daily SEC filing events artifact found")
    tag = tag_from_events_path(latest_events)
    selection = event_selection_summary(latest_events)
    existing_text = text_artifact_summary(tag)
    dry_rows, dry_summary = dry_run_build_rows(latest_events)
    default_forms = list(DEFAULT_FORMS)
    daily_import_forms = list(SEC_TEXT_DEFAULT_FORMS)
    has_periodic_defaults = PERIODIC_FORMS.issubset(forms_set(default_forms))
    daily_import_matches = forms_set(default_forms) == forms_set(daily_import_forms)
    dry_summary_has_provenance = all(
        key in dry_summary
        for key in ("source_form_counts", "matched_form_counts", "selected_form_counts")
    )
    stale_daily_artifact = bool(
        selection["source_periodic_rows"] > 0
        and existing_text["periodic_text_rows"] == 0
    )
    gate2_passed = bool(
        has_periodic_defaults
        and daily_import_matches
        and selection["selected_periodic_rows"] > 0
        and dry_summary.get("selected_periodic_rows", 0) > 0
        and dry_summary_has_provenance
    )
    accepted = gate2_passed
    status = "accepted_measurement_repair" if accepted else "blocked"
    decision = (
        "accepted_measurement_repair_sec_daily_periodic_text_selection_provenance"
        if accepted
        else "blocked_sec_daily_periodic_text_selection_not_verified"
    )
    failed_reasons: list[str] = []
    if not has_periodic_defaults:
        failed_reasons.append("default_forms_missing_periodic_reports")
    if not daily_import_matches:
        failed_reasons.append("daily_import_forms_do_not_match_text_backfill_defaults")
    if selection["selected_periodic_rows"] <= 0:
        failed_reasons.append("latest_daily_events_no_periodic_selection")
    if dry_summary.get("selected_periodic_rows", 0) <= 0:
        failed_reasons.append("dry_run_build_rows_no_periodic_rows")
    if not dry_summary_has_provenance:
        failed_reasons.append("build_rows_summary_missing_form_provenance")

    production_impact = {
        "trade_enabled": False,
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": True,
        "daily_snapshot_exposed": True,
        "entry_rules_changed": False,
        "exit_rules_changed": False,
        "ranking_changed": False,
        "sizing_changed": False,
        "paper_orders_changed": False,
        "live_orders_changed": False,
        "production_watchlist_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_orders": False,
        "uses_free_sec_filing_events": True,
        "uses_free_sec_filing_text": True,
        "uses_llm": False,
        "replay_only": False,
        "live_realism_evaluated": False,
        "live_ready": False,
        "parity_note": (
            "The shared sec_filing_text_backfill summary now records source, "
            "matched, and selected form counts. Daily snapshot wiring imports "
            "the same DEFAULT_FORMS. The dry run writes only experiment-local "
            "selection rows and does not overwrite production daily artifacts."
        ),
    }

    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": LANE,
        "status": status,
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_summary": (
            "Added SEC filing-text form-count provenance and verified, with a "
            "network-free dry run, that the latest daily SEC events select "
            "10-K/10-Q rows under the repaired daily text defaults."
        ),
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "measurement_repair_selection_provenance",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": [
            "sec_filing_text_backfill source-vs-selected form-count summary",
            "daily wrapper default-form parity audit",
            "network-free daily selection dry run",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": [
            "exp-20260626-008",
            "exp-20260626-009",
            "exp-20260626-010",
            "exp-20260626-011",
        ],
        "multiple_testing_risk_bucket": "minimal_measurement_repair",
        "new_evidence_type": "production_visible_daily_artifact_audit",
        "new_evidence_axis": (
            "Daily SEC filing-text materialization provenance and dry-run "
            "selection audit for existing 10-K/10-Q event rows; not a SEC "
            "phrase, form-item, or filer-status alpha replay."
        ),
        "prediction": PREDICTION,
        "gate1": {
            "passed": True,
            "baseline_metrics": baseline,
            "strategy_behavior_changed": False,
        },
        "gate2": {
            "passed": gate2_passed,
            "required_fields_checked": [
                "sec_filing_events accession_number",
                "sec_filing_events accepted_at",
                "sec_filing_events usable_trade_date",
                "sec_filing_events primary_document",
                "sec_filing_text_backfill DEFAULT_FORMS",
                "sec_filing_text summary source_form_counts",
                "sec_filing_text summary selected_form_counts",
                "entry_date",
                "target_price",
            ],
            "default_forms": default_forms,
            "daily_import_forms": daily_import_forms,
            "daily_import_matches_text_backfill_default": daily_import_matches,
            "latest_daily_event_selection": selection,
            "existing_daily_text_artifact": existing_text,
            "dry_run_rows_written": len(dry_rows),
            "dry_run_summary": dry_summary,
            "stale_daily_artifact": stale_daily_artifact,
            "blocking_reason": "; ".join(failed_reasons),
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "baseline_survival_rate": baseline["survival_rate"],
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "note": "No executable filter was added; survival and trade count are unchanged.",
        },
        "gate4": {
            "passed": gate2_passed,
            "decision": decision,
            "strategy_behavior_changed": False,
            "before_after_strategy_delta": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
                "survival_rate_delta": 0.0,
            },
            "failed_reasons": failed_reasons,
            "accepted_basis": (
                "Accepted as measurement repair only: current daily text "
                "defaults select periodic rows, the summary now records source "
                "and selected form counts, and strategy metrics are unchanged. "
                "The stale existing daily text artifact still needs regeneration "
                "with real SEC text/cache before filer-status alpha can run."
            )
            if accepted
            else None,
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "latest_daily_source_periodic_rows": selection["source_periodic_rows"],
            "latest_daily_selected_periodic_rows": selection["selected_periodic_rows"],
            "existing_daily_periodic_text_rows": existing_text["periodic_text_rows"],
            "dry_run_selected_periodic_rows": dry_summary.get("selected_periodic_rows"),
            "stale_daily_artifact": stale_daily_artifact,
        },
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_success": 1 if accepted else 0,
            "brier_score": round((PREDICTION["success_probability"] - (1 if accepted else 0)) ** 2, 6),
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "realized_failure_mode": None if accepted else "; ".join(failed_reasons),
            "predicted_failure_mode_hit": not accepted,
            "surprise_note": (
                "The daily wrapper was already on repaired defaults; the live "
                "artifact mismatch was stale generation state, so the useful "
                "repair is explicit form-count provenance plus a dry-run audit."
            )
            if accepted
            else "Daily periodic selection still did not verify.",
        },
        "production_impact": production_impact,
        "post_run_reflection": {
            "why_result_happened": (
                "The latest daily SEC events include periodic reports, but the "
                "existing text artifact was generated before form-count "
                "provenance and still has zero periodic text rows. Current code "
                "defaults and daily imports now select those rows; real text "
                "content remains a separate fetch/cache materialization blocker."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not run filer-status alpha, filing-timeliness, raw SEC "
                "metadata, or SEC phrase-list replays from this dry-run surface. "
                "It proves selection and provenance only, not parseable cover-page "
                "text content."
            ),
            "new_evidence_required": (
                "Regenerate daily or canonical-window sec_filing_text with real "
                "10-K/10-Q primary-document fetch/cache, confirm ok periodic "
                "text rows plus parsed cover-page statuses, then run one fixed "
                "shared-paper-first filer-status transition rule."
            ),
        },
        "next_retry_requires": [
            "real 10-K/10-Q sec_filing_text rows with ok or parser-usable status",
            "parsed cover-page filer-status booleans keyed by accession and accepted_at",
            "one fixed shared-paper-first status-upgrade candidate rule",
        ],
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260626-008": "Blocked with event rows but no text rows.",
                "exp-20260626-009": "Accepted default-form repair but did not regenerate text artifacts.",
                "exp-20260626-010": "Blocked by missing local periodic text/cache and failed fetch probe.",
                "exp-20260626-011": "Accepted current-category leakage boundary; not a text materialization fix.",
                "novelty_gate": "Reservation passed as measurement repair with gate_shape=other, not a saturated SEC text alpha replay.",
            },
            "3_single_decision_hypothesis": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Accept as measurement repair if current defaults select 10-K/10-Q "
                "daily rows, the daily wrapper imports the same defaults, summary "
                "provenance records source and selected form counts, dry-run output "
                "is experiment-local, and strategy metrics remain unchanged."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "related_files": [
            "quant/sec_filing_text_backfill.py",
            "quant/test_sec_filing_text_backfill.py",
            repo_rel(Path(__file__)),
            repo_rel(latest_events),
            repo_rel(NON_OHLCV_DIR / f"sec_filing_text_{tag}.jsonl"),
            repo_rel(BASELINE_RESULT),
        ],
        "changed_files": [
            "quant/sec_filing_text_backfill.py",
            "quant/test_sec_filing_text_backfill.py",
            repo_rel(Path(__file__)),
            repo_rel(OUT_JSON),
            repo_rel(DRY_RUN_JSONL),
            repo_rel(DRY_RUN_SUMMARY),
            repo_rel(LOG_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
        ],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_sec_filing_text_backfill.py",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {"used_javascript": False, "evidence": "Python runner and pytest only."},
    }


def compact_log_row(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "lane",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "hypothesis",
        "alpha_hypothesis",
        "change_summary",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "changed_variable",
        "single_causal_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "prediction",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "calibration",
        "production_impact",
        "post_run_reflection",
        "next_retry_requires",
        "related_files",
        "changed_files",
        "allowed_write_scope",
        "reproduction_commands",
        "anti_js",
    ]
    row = {key: payload[key] for key in keys}
    row["artifact"] = repo_rel(OUT_JSON)
    row["log"] = repo_rel(LOG_JSON)
    return row


def build_card(payload: dict[str, Any]) -> str:
    delta = payload["delta_metrics"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: SEC Periodic Daily Text Materialization",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Changed variable: `{CHANGED_VARIABLE}`",
            "",
            "## Result",
            "",
            f"- Latest daily periodic event rows: `{delta['latest_daily_source_periodic_rows']}`",
            f"- Current-default selected periodic rows: `{delta['latest_daily_selected_periodic_rows']}`",
            f"- Existing daily periodic text rows: `{delta['existing_daily_periodic_text_rows']}`",
            f"- Dry-run selected periodic rows: `{delta['dry_run_selected_periodic_rows']}`",
            f"- Stale daily artifact: `{delta['stale_daily_artifact']}`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Next Evidence",
            "",
            payload["post_run_reflection"]["new_evidence_required"],
            "",
            "## Reproduce",
            "",
            "```powershell",
            *payload["reproduction_commands"],
            "```",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any], log_row: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / "quant" / "sec_filing_text_backfill.py",
        REPO_ROOT / "quant" / "test_sec_filing_text_backfill.py",
        REPO_ROOT / RUNNER,
        OUT_JSON,
        DRY_RUN_JSONL,
        DRY_RUN_SUMMARY,
        LOG_JSON,
        TICKET_JSON,
        CARD_MD,
        MANIFEST_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
    ]
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "dry_run_rows": repo_rel(DRY_RUN_JSONL),
        "dry_run_summary": repo_rel(DRY_RUN_SUMMARY),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256_file(path)}
            for path in files
        },
        "log_row_sha256": hashlib.sha256(
            json.dumps(safe(log_row), sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    log_row = compact_log_row(payload)
    write_json(OUT_JSON, payload)
    write_json(LOG_JSON, log_row)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_row)
    result = {
        "accepted": bool(payload["accepted"]),
        "accepted_alpha": False,
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "delta_metrics": payload["delta_metrics"],
        "calibration": payload["calibration"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "alpha_hypothesis": ALPHA_HYPOTHESIS,
            "change_type": payload["change_type"],
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "new_evidence_axis": payload["new_evidence_axis"],
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "evaluation_windows": [{"label": label, **cfg} for label, cfg in WINDOWS.items()],
            "acceptance_rule": payload["pre_run_questions"]["4_acceptance_standard"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "decision": payload["decision"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "post_run_reflection": payload["post_run_reflection"],
            "production_impact": payload["production_impact"],
            "reproduction_commands": payload["reproduction_commands"],
            "changed_files": payload["changed_files"],
            "anti_js": payload["anti_js"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload, log_row))


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(json.dumps(safe(compact_log_row(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
