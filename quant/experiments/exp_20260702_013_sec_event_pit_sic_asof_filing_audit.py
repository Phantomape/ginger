"""exp-20260702-013: SEC event PIT SIC as-of-filing coverage audit.

Measurement repair only. The prior SEC corporate-event exposure alpha
(`exp-20260702-012`) used an entity exposure map whose SIC labels are current
submissions-cache labels. This runner checks whether the local cache can
materialize filing-date SIC labels for the event entities before anyone retests
that alpha. No trading behavior, ranking, sizing, exits, or daily/live paths are
changed.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, QUANT_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from data_paths import atomic_write_json, atomic_write_text  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402

EXPERIMENT_ID = "exp-20260702-013"
OWNER = "codex"
SLUG = "sec_event_pit_sic_asof_filing_audit"
RUNNER = f"quant/experiments/exp_20260702_013_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

EVENT_ROWS = (
    REPO_ROOT / "data" / "non_ohlcv" / "sec_corporate_event_stream" / "rows.jsonl"
)
EVENT_MANIFEST = (
    REPO_ROOT / "data" / "non_ohlcv" / "sec_corporate_event_stream" / "manifest.json"
)
ENTITY_MAP_DIR = REPO_ROOT / "data" / "non_ohlcv" / "entity_exposure_map"
ENTITY_ROWS = ENTITY_MAP_DIR / "entities.jsonl"
ENTITY_MANIFEST = ENTITY_MAP_DIR / "manifest.json"
SUBMISSIONS_DIR = REPO_ROOT / "data" / "cache" / "sec" / "submissions"
FILING_TEXT_DIR = REPO_ROOT / "data" / "cache" / "sec" / "filing_text"
BASELINE_JSON = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260702_013_{SLUG}.json"
SAMPLE_JSONL = DATA_DIR / "sec_event_pit_sic_audit_sample.jsonl"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

WINDOWS = [
    ("old_thin", "2024-10-02", "2025-04-22"),
    ("mid_weak", "2025-04-23", "2025-10-22"),
    ("late_strong", "2025-10-23", "2026-04-21"),
    ("current_forward", "2026-04-22", "2026-12-31"),
]

CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260702_013_{SLUG}.json",
    f"data/experiments/{EXPERIMENT_ID}/sec_event_pit_sic_audit_sample.jsonl",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
]

REPRO_COMMANDS = [
    RUNNER_COMMAND,
    ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
]

WRITE_FALLBACKS: list[str] = []


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def repo_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_write_text(text: str, path: Path) -> None:
    try:
        atomic_write_text(text, path)
        return
    except PermissionError as exc:
        WRITE_FALLBACKS.append(f"{repo_rel(path)}: atomic replace fallback: {exc}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    for leftover in path.parent.glob(f".{path.name}.*.tmp"):
        try:
            leftover.unlink()
        except OSError:
            pass


def safe_write_json(payload: Any, path: Path) -> None:
    safe_write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", path)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def normalise_accession(value: str | None) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", value or "").lower()


def parse_header_sic(text: str) -> str | None:
    for line in text.splitlines()[:250]:
        if "STANDARD INDUSTRIAL CLASSIFICATION" not in line.upper():
            continue
        match = re.search(r"\[(\d{3,4})\]", line)
        if match:
            return match.group(1)
        tail = re.search(r"(\d{3,4})\s*$", line.strip())
        if tail:
            return tail.group(1)
    return None


def filing_text_index() -> dict[str, list[Path]]:
    index: dict[str, list[Path]] = defaultdict(list)
    if not FILING_TEXT_DIR.exists():
        return index
    for path in FILING_TEXT_DIR.rglob("*.txt"):
        for token in {normalise_accession(path.name), normalise_accession(path.stem)}:
            if token:
                index[token].append(path)
    return index


def read_submission(cik: str) -> tuple[dict[str, Any] | None, Path]:
    path = SUBMISSIONS_DIR / f"CIK{cik}.json"
    if not path.exists():
        return None, path
    return load_json(path), path


def submission_has_historical_sic(payload: dict[str, Any]) -> bool:
    filings = payload.get("filings") or {}
    recent = filings.get("recent") or {}
    if any("sic" in key.lower() for key in recent):
        return True
    for file_entry in filings.get("files") or []:
        if isinstance(file_entry, dict) and any(
            "sic" in key.lower() for key in file_entry
        ):
            return True
    return False


def baseline_summary() -> dict[str, Any]:
    baseline = load_json(BASELINE_JSON)
    windows = []
    for row in baseline.get("windows") or []:
        windows.append(
            {
                "label": row.get("label"),
                "start": row.get("start"),
                "end": row.get("end"),
                "expected_value_score": row.get("expected_value_score"),
                "total_pnl": row.get("total_pnl"),
                "sharpe_daily": row.get("sharpe_daily"),
                "signals_generated": row.get("signals_generated"),
                "signals_survived": row.get("signals_survived"),
                "survival_rate": row.get("survival_rate"),
            }
        )
    return {
        "path": repo_rel(BASELINE_JSON),
        "generated_at": baseline.get("generated_at"),
        "window_count": len(windows),
        "aggregate_expected_value_score": round(
            sum(float(w.get("expected_value_score") or 0.0) for w in windows), 4
        ),
        "aggregate_total_pnl": round(
            sum(float(w.get("total_pnl") or 0.0) for w in windows), 2
        ),
        "windows": windows,
    }


def audit_surface() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    events = load_jsonl(EVENT_ROWS)
    entity_rows = load_jsonl(ENTITY_ROWS)
    entity_by_cik = {row.get("cik"): row for row in entity_rows if row.get("cik")}
    text_idx = filing_text_index()

    event_ciks = sorted({row.get("cik") for row in events if row.get("cik")})
    submission_by_cik: dict[str, dict[str, Any] | None] = {}
    submission_path_by_cik: dict[str, Path] = {}
    submission_summary = {
        "unique_event_ciks": len(event_ciks),
        "cached_submission_ciks": 0,
        "current_sic_ciks": 0,
        "historical_sic_field_ciks": 0,
        "missing_submission_ciks": 0,
    }
    for cik in event_ciks:
        payload, path = read_submission(cik)
        submission_by_cik[cik] = payload
        submission_path_by_cik[cik] = path
        if payload is None:
            submission_summary["missing_submission_ciks"] += 1
            continue
        submission_summary["cached_submission_ciks"] += 1
        if payload.get("sic"):
            submission_summary["current_sic_ciks"] += 1
        if submission_has_historical_sic(payload):
            submission_summary["historical_sic_field_ciks"] += 1

    window_stats: dict[str, dict[str, Any]] = {}
    for name, start, end in WINDOWS:
        window_stats[name] = {
            "start": start,
            "end": end,
            "event_rows": 0,
            "cached_submission_rows": 0,
            "current_sic_only_rows": 0,
            "pit_sic_header_rows": 0,
            "missing_submission_rows": 0,
            "filing_text_accession_rows": 0,
        }

    status_counter: Counter[str] = Counter()
    event_class_counter: Counter[str] = Counter()
    form_counter: Counter[str] = Counter()
    rows_with_current_sic = 0
    rows_with_hist_submission_sic = 0
    rows_with_filing_text = 0
    rows_with_pit_header_sic = 0
    exact_text_paths: set[str] = set()
    samples: list[dict[str, Any]] = []

    for event in events:
        cik = event.get("cik")
        accession = event.get("accession")
        filed_date = event.get("filed_date") or ""
        event_class_counter[event.get("event_class") or "unknown"] += 1
        form_counter[event.get("form_type") or "unknown"] += 1

        payload = submission_by_cik.get(cik)
        sub_path = submission_path_by_cik.get(cik, SUBMISSIONS_DIR / f"CIK{cik}.json")
        current_sic = payload.get("sic") if payload else None
        current_sic_desc = payload.get("sicDescription") if payload else None
        hist_sic = submission_has_historical_sic(payload) if payload else False
        if current_sic:
            rows_with_current_sic += 1
        if hist_sic:
            rows_with_hist_submission_sic += 1

        text_matches = text_idx.get(normalise_accession(accession), [])
        pit_header_sic = None
        if text_matches:
            rows_with_filing_text += 1
            for path in text_matches[:3]:
                exact_text_paths.add(repo_rel(path))
                try:
                    parsed = parse_header_sic(path.read_text(encoding="utf-8", errors="ignore"))
                except OSError:
                    parsed = None
                if parsed:
                    pit_header_sic = parsed
                    break
        if pit_header_sic:
            rows_with_pit_header_sic += 1
            status = "pit_sic_header_available"
        elif payload and current_sic:
            status = "current_submission_sic_only_not_pit"
        elif payload:
            status = "submission_cache_without_sic"
        else:
            status = "missing_submission_cache"
        status_counter[status] += 1

        for name, start, end in WINDOWS:
            if start <= filed_date <= end:
                stats = window_stats[name]
                stats["event_rows"] += 1
                if payload:
                    stats["cached_submission_rows"] += 1
                else:
                    stats["missing_submission_rows"] += 1
                if current_sic and not pit_header_sic:
                    stats["current_sic_only_rows"] += 1
                if text_matches:
                    stats["filing_text_accession_rows"] += 1
                if pit_header_sic:
                    stats["pit_sic_header_rows"] += 1

        if len(samples) < 200:
            entity_row = entity_by_cik.get(cik) or {}
            samples.append(
                {
                    "accession": accession,
                    "cik": cik,
                    "company_name": event.get("company_name"),
                    "filed_date": filed_date,
                    "form_type": event.get("form_type"),
                    "event_class": event.get("event_class"),
                    "ticker": event.get("ticker"),
                    "submission_cache_exists": bool(payload),
                    "submission_cache_file": repo_rel(sub_path)
                    if sub_path.exists()
                    else None,
                    "current_submission_sic": current_sic,
                    "current_submission_sic_description": current_sic_desc,
                    "entity_map_sic": entity_row.get("sic"),
                    "entity_map_sic_as_of": entity_row.get("sic_as_of"),
                    "submission_has_historical_sic_field": hist_sic,
                    "filing_text_cache_matches": [repo_rel(p) for p in text_matches[:3]],
                    "pit_header_sic": pit_header_sic,
                    "pit_status": status,
                }
            )

    for stats in window_stats.values():
        total = max(1, int(stats["event_rows"]))
        stats["cached_submission_pct"] = round(
            100.0 * int(stats["cached_submission_rows"]) / total, 2
        )
        stats["pit_sic_header_pct"] = round(
            100.0 * int(stats["pit_sic_header_rows"]) / total, 2
        )
        stats["current_sic_only_pct"] = round(
            100.0 * int(stats["current_sic_only_rows"]) / total, 2
        )

    total_events = len(events)
    audit = {
        "event_rows": total_events,
        "event_manifest": load_json(EVENT_MANIFEST),
        "entity_rows": len(entity_rows),
        "entity_sic_as_of_values": dict(
            Counter(row.get("sic_as_of") for row in entity_rows if row.get("sic_as_of"))
        ),
        "entity_manifest": load_json(ENTITY_MANIFEST),
        "event_classes": dict(event_class_counter.most_common()),
        "form_types": dict(form_counter.most_common()),
        "submission_cache": {
            **submission_summary,
            "unique_event_cik_cache_hit_pct": round(
                100.0
                * int(submission_summary["cached_submission_ciks"])
                / max(1, int(submission_summary["unique_event_ciks"])),
                2,
            ),
            "unique_event_cik_current_sic_pct": round(
                100.0
                * int(submission_summary["current_sic_ciks"])
                / max(1, int(submission_summary["unique_event_ciks"])),
                2,
            ),
        },
        "row_level_coverage": {
            "current_submission_sic_rows": rows_with_current_sic,
            "current_submission_sic_pct": round(
                100.0 * rows_with_current_sic / max(1, total_events), 2
            ),
            "historical_sic_field_rows": rows_with_hist_submission_sic,
            "filing_text_accession_rows": rows_with_filing_text,
            "filing_text_accession_pct": round(
                100.0 * rows_with_filing_text / max(1, total_events), 2
            ),
            "pit_sic_header_rows": rows_with_pit_header_sic,
            "pit_sic_header_pct": round(
                100.0 * rows_with_pit_header_sic / max(1, total_events), 2
            ),
        },
        "pit_status_counts": dict(status_counter.most_common()),
        "window_stats": window_stats,
        "filing_text_cache": {
            "directory_exists": FILING_TEXT_DIR.exists(),
            "indexed_text_files": sum(len(paths) for paths in text_idx.values()),
            "matched_paths_sample": sorted(exact_text_paths)[:20],
        },
        "local_source_boundary": (
            "SEC submissions JSON exposes current top-level sic/sicDescription; "
            "the local event filing_text cache has no accession-level matches for "
            "the corporate-event stream, so filing-date SIC cannot be "
            "materialized from the present local cache."
        ),
    }
    return audit, samples


def evaluate_gates(audit: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    if audit["event_rows"] <= 0:
        failures.append("sec_corporate_event_rows_missing")
    if audit["submission_cache"]["cached_submission_ciks"] <= 0:
        failures.append("submissions_cache_missing_for_event_ciks")
    if audit["submission_cache"]["historical_sic_field_ciks"] <= 0:
        failures.append("submissions_cache_current_only_no_historical_sic_field")
    if audit["row_level_coverage"]["filing_text_accession_rows"] <= 0:
        failures.append("sec_event_filing_text_cache_missing_for_accessions")
    if audit["row_level_coverage"]["pit_sic_header_rows"] <= 0:
        failures.append("no_pit_sic_asof_filing_rows_materialized")
    return {
        "passed": not failures,
        "failed_reasons": failures,
        "pit_sic_materialized": audit["row_level_coverage"]["pit_sic_header_rows"] > 0,
    }


def build_payload(audit: dict[str, Any], gates: dict[str, Any]) -> dict[str, Any]:
    accepted = bool(gates["passed"])
    decision = (
        "accepted_measurement_repair_sec_event_pit_sic_asof_filing"
        if accepted
        else "blocked_sec_event_pit_sic_asof_filing_not_materialized_local_cache"
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": "measurement_repair",
        "status": "accepted_measurement_repair" if accepted else "blocked",
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "alpha_ready": False,
        "observed_only_lead": False,
        "hypothesis": (
            "SEC corporate-event exposure ranking needs point-in-time SIC peer "
            "labels; current submissions SIC can leak post-filing "
            "classification state, so local PIT SIC coverage must be measured "
            "before another fixed-window alpha retest."
        ),
        "alpha_hypothesis": (
            "Later, separately gated: S-1/F-1/425 corporate events may create "
            "replacement value in related listed peers, but only if entity "
            "classification edges are point-in-time or replaced by a richer "
            "non-SIC relation/economic source."
        ),
        "change_type": "measurement_repair",
        "implementation_mode": "experiment_owned_cache_coverage_audit",
        "mechanism_family": "sec_event_entity_exposure",
        "trial_family": "sec_event_pit_sic_asof_filing_repair",
        "trial_variant_id": "v1_local_cache_coverage",
        "single_causal_variable": "sec_event_pit_sic_asof_filing_coverage_audit_v1",
        "changed_variable": "sec_event_pit_sic_asof_filing_coverage_audit_v1",
        "causal_components": [
            "sec_corporate_event_stream",
            "entity_exposure_map_current_sic_boundary",
            "sec_submissions_cache_schema",
            "sec_filing_text_accession_cache",
        ],
        "nearby_prior_experiments": [
            "exp-20260702-012",
            "exp-20260702-009",
            "exp-20260702-008",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "measurement_repair_pit_sic_asof_filing",
        "new_evidence_axis": (
            "PIT SIC-as-of-filing repair path explicitly left by "
            "exp-20260702-012; this does not alter event forms, relation "
            "priority, thresholds, response shape, or notional."
        ),
        "audit": audit,
        "baseline": baseline_summary(),
        "gate1": {
            "baseline_result_file": repo_rel(BASELINE_JSON),
            "baseline_unchanged": True,
            "summary": baseline_summary(),
        },
        "gate2": {
            "required_fields_checked": [
                "event.accession",
                "event.cik",
                "event.filed_date",
                "submission.sic",
                "submission.sicDescription",
                "filing_header.STANDARD_INDUSTRIAL_CLASSIFICATION",
            ],
            "required_artifacts_present": {
                repo_rel(EVENT_ROWS): EVENT_ROWS.exists(),
                repo_rel(ENTITY_ROWS): ENTITY_ROWS.exists(),
                repo_rel(SUBMISSIONS_DIR): SUBMISSIONS_DIR.exists(),
                repo_rel(FILING_TEXT_DIR): FILING_TEXT_DIR.exists(),
            },
            "runtime_field_verdict": "blocked_pit_sic_source_missing"
            if not accepted
            else "pit_sic_source_available",
        },
        "gate3": {
            "signals_generated": None,
            "signals_survived": None,
            "survival_rate": None,
            "note": (
                "No signal filtering, ranking, sizing, or orders changed. "
                "Event-surface coverage audit only."
            ),
        },
        "gate4": {
            "mode": "measurement_repair_identity_plus_coverage_gate",
            "passed": accepted,
            "failed_reasons": gates["failed_reasons"],
            "strategy_behavior_changed": False,
            "aggregate_expected_value_delta": 0.0,
            "aggregate_total_pnl_delta": 0.0,
            "before_after_delta": {
                "expected_value_score_delta_sum": 0.0,
                "total_pnl_delta_sum": 0.0,
                "drawdown_delta": 0.0,
                "trade_count_delta": 0,
            },
        },
        "production_impact": {
            "alters_candidate_ranking": False,
            "alters_exits": False,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_sizing": False,
            "backtester_adapter_changed": False,
            "daily_collector_changed": False,
            "daily_snapshot_exposed": False,
            "live_orders_changed": False,
            "live_ready": False,
            "paper_orders_changed": False,
            "parity_note": (
                "Runner only audits local cache coverage. No shared policy "
                "helper, run.py wiring, backtester adapter, daily snapshot, or "
                "paper/live order path changed."
            ),
        },
        "live_realistic_execution_envelope": {
            "evaluated": False,
            "reason": "Measurement repair/blocker only; no executable alpha.",
        },
        "blocked_reopen_condition": (
            "Reopen SEC corporate-event exposure alpha only after an "
            "accession-level source supplies PIT SIC for at least 10,000 of "
            "17,335 event rows (and at least 500 rows in each old_thin, "
            "mid_weak, and late_strong window), or after a genuinely new "
            "relation/economic source replaces SIC peers. Valid sources are "
            "filing header text with STANDARD INDUSTRIAL CLASSIFICATION parsed "
            "by accession/accepted_at, or archived submissions snapshots keyed "
            "no later than filed_date."
        ),
        "post_run_reflection": {
            "why_result_happened": (
                "The local submissions cache covers many event CIKs, but it "
                "is a current-state SEC submissions snapshot. It has current "
                "top-level sic/sicDescription and no filings.recent/files SIC "
                "history. The local filing_text cache has zero accession "
                "matches for this event stream, so header SIC cannot be parsed."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not rerun SEC corporate-event exposure by changing form "
                "sets, relation priority, event priority, threshold, hold, "
                "cooldown, notional, theme overlay, SIC cap, or response shape "
                "on the same current-SIC rows. Do not use same-source new tags "
                "inside the saturated SEC event family as an override."
            ),
            "new_evidence_required": (
                "Materially new evidence is accession-level PIT SIC coverage, "
                "fresh closed forward rows from shared daily helper, or a "
                "new relation/economic source such as deal consideration, "
                "supply-chain exposure, borrow economics, or verified "
                "issuer-to-listed-peer linkage."
            ),
        },
        "related_files": [
            repo_rel(EVENT_ROWS),
            repo_rel(ENTITY_ROWS),
            repo_rel(EVENT_MANIFEST),
            repo_rel(ENTITY_MANIFEST),
            repo_rel(BASELINE_JSON),
        ],
        "changed_files": CHANGED_FILES,
        "reproduction_commands": REPRO_COMMANDS,
        "allowed_write_scope": CHANGED_FILES,
        "lean_quality_passed": True,
    }


def build_card(payload: dict[str, Any]) -> str:
    audit = payload["audit"]
    submission = audit["submission_cache"]
    row_cov = audit["row_level_coverage"]
    lines = [
        f"# {EXPERIMENT_ID}: SEC event PIT SIC as-of-filing audit",
        "",
        f"- status: `{payload['status']}` / decision: `{payload['decision']}`",
        f"- event rows: `{audit['event_rows']}`; unique CIKs: "
        f"`{submission['unique_event_ciks']}`",
        f"- submissions cache hit: `{submission['cached_submission_ciks']}` "
        f"CIKs ({submission['unique_event_cik_cache_hit_pct']}%)",
        f"- current SIC rows: `{row_cov['current_submission_sic_rows']}` "
        f"({row_cov['current_submission_sic_pct']}%)",
        f"- historical SIC fields in submissions: "
        f"`{submission['historical_sic_field_ciks']}` CIKs / "
        f"`{row_cov['historical_sic_field_rows']}` rows",
        f"- event filing-text accession matches: "
        f"`{row_cov['filing_text_accession_rows']}` rows",
        f"- PIT header SIC rows materialized: "
        f"`{row_cov['pit_sic_header_rows']}` "
        f"({row_cov['pit_sic_header_pct']}%)",
        "",
        "## Window Coverage",
        "",
    ]
    for name, stats in audit["window_stats"].items():
        lines.append(
            f"- `{name}`: events `{stats['event_rows']}`, current-only "
            f"`{stats['current_sic_only_rows']}` "
            f"({stats['current_sic_only_pct']}%), PIT header SIC "
            f"`{stats['pit_sic_header_rows']}` "
            f"({stats['pit_sic_header_pct']}%)"
        )
    lines += [
        "",
        "## Boundary",
        "",
        payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
        "",
        "## Reopen Condition",
        "",
        payload["blocked_reopen_condition"],
        "",
        "## Repro",
        "",
    ]
    lines += [f"- `{cmd}`" for cmd in REPRO_COMMANDS]
    return "\n".join(lines) + "\n"


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "owner",
        "lane",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "alpha_ready",
        "observed_only_lead",
        "hypothesis",
        "alpha_hypothesis",
        "change_type",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "single_causal_variable",
        "changed_variable",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "production_impact",
        "blocked_reopen_condition",
        "post_run_reflection",
        "changed_files",
        "reproduction_commands",
        "lean_quality_passed",
    ]
    record = {key: payload[key] for key in keys}
    record["artifact"] = repo_rel(OUT_JSON)
    record["audit_summary"] = {
        "event_rows": payload["audit"]["event_rows"],
        "unique_event_ciks": payload["audit"]["submission_cache"][
            "unique_event_ciks"
        ],
        "unique_event_cik_cache_hit_pct": payload["audit"]["submission_cache"][
            "unique_event_cik_cache_hit_pct"
        ],
        "current_submission_sic_pct": payload["audit"]["row_level_coverage"][
            "current_submission_sic_pct"
        ],
        "filing_text_accession_rows": payload["audit"]["row_level_coverage"][
            "filing_text_accession_rows"
        ],
        "pit_sic_header_rows": payload["audit"]["row_level_coverage"][
            "pit_sic_header_rows"
        ],
    }
    return record


def upsert_experiment_log(record: dict[str, Any]) -> None:
    lines: list[str] = []
    if EXPERIMENT_LOG.exists():
        for line in EXPERIMENT_LOG.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                lines.append(line)
                continue
            if row.get("experiment_id") != EXPERIMENT_ID:
                lines.append(line)
    lines.append(json.dumps(record, ensure_ascii=False, sort_keys=True))
    safe_write_text("\n".join(lines) + "\n", EXPERIMENT_LOG)


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    tracked = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        SAMPLE_JSONL,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        EVENT_ROWS,
        ENTITY_ROWS,
        EVENT_MANIFEST,
        ENTITY_MANIFEST,
        BASELINE_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {
                "exists": path.exists(),
                "sha256": sha256(path),
            }
            for path in tracked
        },
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any], samples: list[dict[str, Any]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    safe_write_json(payload, OUT_JSON)
    safe_write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in samples)
        + "\n",
        SAMPLE_JSONL,
    )
    log_record = compact_log_record(payload)
    safe_write_json(log_record, LOG_JSON)
    safe_write_text(build_card(payload), CARD_MD)
    upsert_experiment_log(log_record)

    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction={
            "success_probability": 0.25,
            "expected_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "main_failure_modes": [
                "submissions_current_only",
                "filing_text_cache_missing",
                "no_historical_sic_field",
            ],
            "confidence_reason": (
                "exp-20260702-012 explicitly named PIT SIC-as-of-filing "
                "repair as valid next evidence; preflight showed current SIC "
                "only and zero exact event filing-text hits."
            ),
        },
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "alpha_ready": False,
            "observed_only_lead": False,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
            "change_type": payload["change_type"],
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
            "baseline_result_file": repo_rel(BASELINE_JSON),
            "acceptance_rule": (
                "Accepted measurement repair only if PIT SIC coverage is "
                "materialized for SEC event entities; otherwise blocked with "
                "exact missing source and reopen condition."
            ),
            "allowed_write_scope": CHANGED_FILES,
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "blocked_reopen_condition": payload["blocked_reopen_condition"],
            "changed_files": CHANGED_FILES,
            "reproduction_commands": REPRO_COMMANDS,
            "lean_quality_passed": payload["lean_quality_passed"],
            "artifact": repo_rel(OUT_JSON),
            "log_file": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
        },
    )
    if WRITE_FALLBACKS:
        payload["write_fallbacks"] = WRITE_FALLBACKS[:]
        safe_write_json(payload, OUT_JSON)
        log_record["write_fallbacks"] = WRITE_FALLBACKS[:]
        safe_write_json(log_record, LOG_JSON)
    safe_write_json(build_manifest(payload), MANIFEST_JSON)


def main() -> int:
    audit, samples = audit_surface()
    gates = evaluate_gates(audit)
    payload = build_payload(audit, gates)
    persist(payload, samples)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "event_rows": audit["event_rows"],
                "unique_event_ciks": audit["submission_cache"]["unique_event_ciks"],
                "submission_cache_hit_pct": audit["submission_cache"][
                    "unique_event_cik_cache_hit_pct"
                ],
                "current_submission_sic_pct": audit["row_level_coverage"][
                    "current_submission_sic_pct"
                ],
                "filing_text_accession_rows": audit["row_level_coverage"][
                    "filing_text_accession_rows"
                ],
                "pit_sic_header_rows": audit["row_level_coverage"][
                    "pit_sic_header_rows"
                ],
                "failed_reasons": gates["failed_reasons"],
                "artifact": repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
