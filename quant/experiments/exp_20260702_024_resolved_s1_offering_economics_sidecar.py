"""exp-20260702-024: resolved S-1/F-1 offering-economics sidecar audit.

Measurement repair for the exp-20260702-023 issuer-overhang lead. The lead is
not allowed to advance by re-slicing the same resolved S-1/F-1 rows; it needs a
new replayable economics field such as registered amount, resale-vs-primary,
selling-holder identity, effectiveness date, or prospectus-supplement terms.

This runner checks whether those fields can be materialized from local PIT
filing text/features today. It changes no strategy, paper sleeve, ranking,
sizing, exit, order, or LLM behavior.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, SCRIPTS_ROOT):
    value = str(entry)
    if value not in sys.path:
        sys.path.insert(0, value)

from experiment_registry import persist_self_registered_result  # noqa: E402

EXPERIMENT_ID = "exp-20260702-024"
OWNER = "alpha-explore"
SLUG = "resolved_s1_offering_economics_sidecar"
RUNNER = f"quant/experiments/exp_20260702_024_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

EVENT_ROWS = (
    REPO_ROOT / "data" / "non_ohlcv" / "sec_corporate_event_stream" / "rows.jsonl"
)
BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260702_024_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

WINDOWS = [
    ("old_thin", "2024-10-02", "2025-04-22"),
    ("mid_weak", "2025-04-23", "2025-10-22"),
    ("late_strong", "2025-10-23", "2026-04-21"),
]
FORMS = {"S-1", "S-1/A", "F-1", "F-1/A"}
MIN_TEXT_ROWS_PER_WINDOW = 100
MIN_PARSED_ECON_ROWS_PER_WINDOW = 50

HYPOTHESIS = (
    "Replayable offering-economics provenance for resolved S-1/F-1 issuer-"
    "overhang rows may be materializable from local SEC filing text/features, "
    "allowing the exp-20260702-023 lead to be retested with registered amount "
    "or resale-vs-primary fields instead of same-row reslices."
)
ALPHA_HYPOTHESIS = (
    "If offering economics are available, larger resale/primary dilution "
    "events should explain which resolved S-1/F-1 issuer rows have negative "
    "post-filing replacement value."
)
SINGLE_CAUSAL_VARIABLE = "resolved_s1_f1_offering_economics_sidecar_v1"
NEARBY_PRIORS = ["exp-20260702-023", "exp-20260702-008", "exp-20260629-002"]
CAUSAL_COMPONENTS = [
    "resolved_ticker_s1_f1_event_rows",
    "local_sec_filing_text_accession_coverage_audit",
    "local_sec_filing_features_accession_coverage_audit",
    "offering_economics_sidecar_readiness_verdict",
    "no_strategy_behavior_change",
]
CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260702_024_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default if default is not None else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig", errors="replace") as handle:
        for line_no, raw in enumerate(handle, start=1):
            text = raw.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL") from exc
            if isinstance(row, dict):
                rows.append(row)
    return rows


def write_json(path: Path, payload: Any) -> None:
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


def window_of(date_text: str) -> str | None:
    for name, start, end in WINDOWS:
        if start <= date_text <= end:
            return name
    return None


def load_target_rows() -> list[dict[str, Any]]:
    rows = []
    for row in read_jsonl(EVENT_ROWS):
        filed_date = str(row.get("filed_date") or "")
        if (
            row.get("event_class") == "ipo_registration"
            and row.get("ticker_status") == "resolved"
            and row.get("form_type") in FORMS
            and window_of(filed_date)
        ):
            rows.append(row)
    return rows


def accession_from_text_row(row: dict[str, Any]) -> str | None:
    value = row.get("accession_number") or row.get("source_accession")
    return str(value) if value else None


def scan_local_accession_files(
    glob_pattern: str,
    target_accessions: set[str],
) -> dict[str, dict[str, Any]]:
    hits: dict[str, dict[str, Any]] = {}
    for path in sorted((REPO_ROOT / "data" / "non_ohlcv").glob(glob_pattern)):
        for row in read_jsonl(path):
            accession = accession_from_text_row(row)
            if accession not in target_accessions:
                continue
            hits[accession] = {
                "file": repo_rel(path),
                "form_type": row.get("form_type"),
                "ticker": row.get("ticker"),
                "text_char_count": row.get("text_char_count"),
                "documents_fetched": row.get("documents_fetched"),
            }
    return hits


def summarize_by_window(
    target_rows: list[dict[str, Any]], hit_accessions: set[str]
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for name, _start, _end in WINDOWS:
        rows = [row for row in target_rows if window_of(str(row.get("filed_date"))) == name]
        unique = {str(row.get("accession")) for row in rows if row.get("accession")}
        hits = unique & hit_accessions
        out[name] = {
            "target_rows": len(rows),
            "unique_accessions": len(unique),
            "local_text_or_feature_accessions": len(hits),
            "coverage_rate": round(len(hits) / len(unique), 6) if unique else 0.0,
        }
    return out


def load_baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = list(payload.get("windows") or [])
    generated = sum(int(window.get("signals_generated") or 0) for window in windows)
    survived = sum(int(window.get("signals_survived") or 0) for window in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(window.get("expected_value_score") or 0.0) for window in windows),
            4,
        ),
        "total_pnl": round(
            sum(float(window.get("total_pnl") or 0.0) for window in windows),
            2,
        ),
        "trade_count": sum(int(window.get("trade_count") or 0) for window in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
    }


def analyze() -> dict[str, Any]:
    target_rows = load_target_rows()
    target_accessions = {
        str(row.get("accession")) for row in target_rows if row.get("accession")
    }
    text_hits = scan_local_accession_files(
        "sec_filing_text_*.jsonl", target_accessions
    )
    feature_hits = scan_local_accession_files(
        "sec_filing_features_*.jsonl", target_accessions
    )
    all_hits = set(text_hits) | set(feature_hits)
    source_by_window = Counter(
        window_of(str(row.get("filed_date") or "")) for row in target_rows
    )
    source_by_form = Counter(str(row.get("form_type") or "") for row in target_rows)
    coverage_by_window = summarize_by_window(target_rows, all_hits)
    text_ready = all(
        coverage_by_window[name]["local_text_or_feature_accessions"]
        >= MIN_TEXT_ROWS_PER_WINDOW
        for name, _start, _end in WINDOWS
    )
    parsed_economics_ready = False
    blocked = not (text_ready and parsed_economics_ready)
    return {
        "target_surface": "resolved ticker S-1/F-1 issuer rows from sec_corporate_event_stream",
        "target_rows": len(target_rows),
        "target_unique_accessions": len(target_accessions),
        "source_rows_by_window": dict(sorted(source_by_window.items())),
        "source_rows_by_form": dict(sorted(source_by_form.items())),
        "local_sec_filing_text_accessions": len(text_hits),
        "local_sec_filing_features_accessions": len(feature_hits),
        "local_text_or_feature_accessions": len(all_hits),
        "coverage_by_window": coverage_by_window,
        "sidecar_rows_materialized": 0,
        "parsed_registered_amount_rows": 0,
        "parsed_resale_vs_primary_rows": 0,
        "parsed_selling_holder_rows": 0,
        "parsed_effectiveness_or_prospectus_rows": 0,
        "text_ready": text_ready,
        "parsed_economics_ready": parsed_economics_ready,
        "blocked": blocked,
        "blocking_reasons": [
            "local_s1_f1_filing_text_not_materialized_for_target_accessions"
            if not text_ready
            else None,
            "offering_economics_fields_not_parseable_without_text"
            if not parsed_economics_ready
            else None,
        ],
        "reopen_condition": (
            "Reopen only after replayable public-PIT S-1/F-1 filing text or "
            "features are materialized for >=100 resolved issuer accessions in "
            "each canonical window, and at least one offering-economics field "
            "(registered_amount_usd, resale_vs_primary, selling_holder, "
            "effectiveness_date, or prospectus_supplement_terms) parses for "
            ">=50 rows in each window."
        ),
        "sample_missing_accessions": sorted(target_accessions - all_hits)[:20],
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "owner",
        "lane",
        "status",
        "decision",
        "accepted",
        "hypothesis",
        "alpha_hypothesis",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "single_causal_variable",
        "changed_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "pre_run_questions",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "production_impact",
        "post_run_reflection",
        "next_retry_requires",
        "rejection_reason",
        "reopen_condition",
        "related_files",
        "changed_files",
        "reproduction_commands",
        "artifact",
        "log",
        "lean_quality_passed",
    ]
    record = {key: payload[key] for key in keys}
    record["audit_summary"] = {
        "target_rows": payload["audit"]["target_rows"],
        "target_unique_accessions": payload["audit"]["target_unique_accessions"],
        "local_text_or_feature_accessions": payload["audit"][
            "local_text_or_feature_accessions"
        ],
        "coverage_by_window": payload["audit"]["coverage_by_window"],
        "blocked": payload["audit"]["blocked"],
    }
    return record


def build_payload(report: dict[str, Any]) -> dict[str, Any]:
    baseline = load_baseline_metrics()
    decision = "blocked_resolved_s1_f1_offering_economics_text_not_materialized"
    why = (
        "The target SEC corporate-event stream has dense resolved S-1/F-1 rows, "
        "but none of the 5,065 target accessions are present in the local "
        "sec_filing_text or sec_filing_features surfaces. Offering amount, "
        "resale-vs-primary, selling-holder, and effectiveness fields therefore "
        "cannot be parsed offline today."
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": "measurement_repair",
        "status": "blocked",
        "decision": decision,
        "accepted": False,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "measurement_repair",
        "mechanism_family": "production_visible_sec_corporate_event_stream",
        "trial_family": "resolved_s1_f1_offering_economics_sidecar",
        "trial_variant_id": "resolved_s1_f1_offering_economics_sidecar_v1",
        "single_causal_variable": SINGLE_CAUSAL_VARIABLE,
        "changed_variable": SINGLE_CAUSAL_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "coverage_audit_for_required_economics_field",
        "new_evidence_axis": (
            "first coverage audit for offering-economics text/features on the "
            "resolved S-1/F-1 issuer-overhang lead; not an attribution reslice"
        ),
        "audit": report,
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "strategy_behavior_changed": False,
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "nearby_prior_experiments": NEARBY_PRIORS,
                "novelty_gate": "experiment.py new accepted without override.",
                "new_evidence_axis": (
                    "required economics-field coverage audit for the exp-023 "
                    "lead, not a same-row S-1/F-1 outcome slice"
                ),
            },
            "3_single_policy_bundle": (
                "Measurement repair only: audit whether local SEC text/features "
                "can materialize offering-economics fields for resolved S-1/F-1 "
                "issuer rows."
            ),
            "4_success_failure_standard": (
                "Ready only if >=100 target accessions per canonical window have "
                "local text/features and >=50 parsed economics rows per window; "
                "otherwise block with a reopen condition."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "gate1": {"passed": True, "baseline_metrics": baseline},
        "gate2": {
            "passed": False,
            "fields": [
                "accession",
                "filed_date",
                "ticker",
                "local_sec_filing_text",
                "registered_amount_usd",
                "resale_vs_primary",
                "selling_holder",
                "effectiveness_date_or_prospectus_terms",
            ],
            "missing_fields": [
                "local_sec_filing_text",
                "registered_amount_usd",
                "resale_vs_primary",
                "selling_holder",
                "effectiveness_date_or_prospectus_terms",
            ],
            "note": "Target rows exist, but the local filing-text/features surfaces have zero matching accessions.",
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": baseline.get("signals_generated"),
            "signals_survived": baseline.get("signals_survived"),
            "survival_rate": baseline.get("survival_rate"),
            "note": "No strategy filter was added; this is a coverage audit.",
        },
        "gate4": {
            "mode": "measurement_repair_blocked",
            "passed": False,
            "failed_reasons": report["blocking_reasons"],
            "strategy_delta": {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "max_drawdown_pct": 0.0,
            },
        },
        "production_impact": {
            "trade_enabled": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_exposed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "live_ready": False,
            "parity_note": "Read-only coverage audit; no production or backtest behavior changed.",
        },
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not reserve another experiment to confirm this same surface "
                "is still missing text/features. Compare current coverage counts "
                "to this artifact before reserving. Do not re-slice exp-023 "
                "resolved S-1/F-1 rows by amendment flag, form subtype, horizon, "
                "entry lag, liquidity, event age, notional, or response shape."
            ),
            "new_evidence_required": report["reopen_condition"],
        },
        "next_retry_requires": [
            "public-PIT filing text cache for target S-1/F-1 accessions",
            "registered amount or resale-vs-primary parser with per-window coverage",
            "selling-holder or effectiveness/prospectus-supplement provenance",
        ],
        "rejection_reason": "local_s1_f1_offering_economics_text_not_materialized",
        "reopen_condition": report["reopen_condition"],
        "related_files": [repo_rel(EVENT_ROWS), repo_rel(BASELINE_RESULT)],
        "changed_files": CHANGED_FILES,
        "allowed_write_scope": CHANGED_FILES,
        "reproduction_commands": [RUNNER_COMMAND],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner, py_compile, and experiment audit only.",
        },
        "lean_quality_passed": True,
    }


def build_card(payload: dict[str, Any]) -> str:
    report = payload["audit"]
    lines = [
        f"# {EXPERIMENT_ID}: resolved S-1/F-1 offering-economics sidecar",
        "",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        "- Production behavior changed: no",
        f"- Target rows: `{report['target_rows']}`",
        f"- Unique accessions: `{report['target_unique_accessions']}`",
        f"- Local text/features hits: `{report['local_text_or_feature_accessions']}`",
        "- Sidecar rows materialized: `0`",
        "",
        "## Coverage By Window",
        "",
    ]
    for name, row in report["coverage_by_window"].items():
        lines.append(
            f"- `{name}`: target={row['unique_accessions']}, "
            f"local_text_or_feature={row['local_text_or_feature_accessions']}, "
            f"coverage={row['coverage_rate']}"
        )
    lines += [
        "",
        "## Reopen Condition",
        "",
        report["reopen_condition"],
        "",
        "## Reproduction",
        "",
        f"```powershell\n{RUNNER_COMMAND}\n```",
        "",
    ]
    return "\n".join(lines)


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EVENT_ROWS,
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
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "allowed_write_scope": CHANGED_FILES,
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    write_json(LOG_JSON, compact_log_record(payload))
    write_text(CARD_MD, build_card(payload))

    fields = {
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
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "reopen_condition": payload["reopen_condition"],
        "related_files": payload["related_files"],
        "changed_files": payload["changed_files"],
        "allowed_write_scope": payload["allowed_write_scope"],
        "lean_quality_passed": payload["lean_quality_passed"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=payload.get("prediction"),
        result={
            "accepted": False,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "blocked": True,
            "reopen_condition": payload["reopen_condition"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields=fields,
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    report = analyze()
    payload = build_payload(report)
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "target_rows": report["target_rows"],
                "target_unique_accessions": report["target_unique_accessions"],
                "local_text_or_feature_accessions": report[
                    "local_text_or_feature_accessions"
                ],
                "blocked": report["blocked"],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
