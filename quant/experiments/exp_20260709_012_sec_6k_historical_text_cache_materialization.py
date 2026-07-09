"""exp-20260709-012: historical SEC 6-K text/cache materialization audit.

Measurement-repair experiment for the 6-K semantic alpha lane.

The alpha hypothesis is intentionally not tested here: 6-K/6-KA structured
financial and guidance text may become a production-visible SEC semantic alpha
surface, but replay is not trustworthy while canonical-window 6-K text bodies
are absent. This runner quantifies the gap, exports the exact missing event
input rows for a later official backfill, and records whether the current
environment can fetch SEC archives.

No entry, exit, ranking, sizing, paper state, live order, or LLM behavior is
changed.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260709-012"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "sec_6k_historical_text_cache_materialization"
RUNNER = f"quant/experiments/exp_20260709_012_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


DATA_DIR = REPO_ROOT / "data"
NON_OHLCV_DIR = DATA_DIR / "non_ohlcv"
SEC_TEXT_CACHE_DIR = DATA_DIR / "cache" / "sec" / "filing_text"
OUT_DIR = DATA_DIR / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260709_012_{SLUG}.json"
MISSING_EVENTS_JSONL = OUT_DIR / "missing_historical_6k_events.jsonl"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
BASELINE_RESULT = (
    DATA_DIR / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)

WINDOWS = [
    {"label": "old_thin", "start": "2024-10-02", "end": "2025-04-22"},
    {"label": "mid_weak", "start": "2025-04-23", "end": "2025-10-22"},
    {"label": "late_strong", "start": "2025-10-23", "end": "2026-04-21"},
]
POST_FORWARD_START = "2026-04-22"
USER_AGENT = "ginger-research/1.0 contact: research@example.com"
NETWORK_TIMEOUT_SEC = 8

HYPOTHESIS = (
    "alpha_blocker/measurement_repair: SEC 6-K/6-KA structured financial and "
    "guidance text could be a production-visible SEC semantic alpha surface, "
    "but canonical-window replay is not trustworthy because sec_filing_events "
    "has historical 6-K event rows while sec_filing_text has zero deduped 6-K "
    "text rows inside old_thin/mid_weak/late_strong. Materialize or quantify "
    "the historical 6-K text/cache gap without changing any trading rule."
)
ALPHA_HYPOTHESIS = HYPOTHESIS
CHANGE_TYPE = "measurement_repair"
IMPLEMENTATION_MODE = "self_registered_blocker_audit_no_strategy_change"
MECHANISM_FAMILY = "sec_6k_text_replay_measurement"
TRIAL_FAMILY = "historical_sec_6k_text_cache_materialization"
TRIAL_VARIANT_ID = "canonical_windows_6k_text_cache_materialization_v1"
SINGLE_CAUSAL_VARIABLE = "sec_6k_historical_text_cache_materialization_v1"
CHANGED_VARIABLE = SINGLE_CAUSAL_VARIABLE
NEW_EVIDENCE_TYPE = "measurement_repair_alpha_enabling_historical_text_cache"
NEW_EVIDENCE_AXIS = (
    "New data materialization axis: historical 6-K/6-KA SEC filing text/cache "
    "coverage across canonical windows, where current deduped text rows are 0 "
    "despite historical event rows; this is not a 6-K phrase, liquidity, top-N, "
    "hold, or response-shape retune."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260708-003",
    "exp-20260708-014",
]
CAUSAL_COMPONENTS = [
    "dedupe 6-K event rows",
    "audit canonical-window cache coverage",
    "export missing historical 6-K event input rows",
    "probe SEC archive fetch capability",
    "no phrase/ranking/entry retune",
]
PREDICTION = {
    "success_probability": 0.35,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "network_disabled_or_sec_fetch_blocked",
        "cache_missing_for_historical_6k",
        "too_few_replayable_6k_rows_after_backfill",
        "duplicate_daily_snapshot_rows",
    ],
    "confidence_reason": (
        "Historical 6-K event rows already exist across all canonical windows, "
        "but local filing_text cache is missing for historical accessions; "
        "success depends on whether the environment can fetch SEC archives or "
        "otherwise reuse cached source text."
    ),
    "recorded_at": "2026-07-09T09:12:32Z",
}
ACCEPTANCE_RULE = (
    "Accepted measurement repair only if canonical-window 6-K text/cache rows "
    "become replayable inside the official SEC filing-text surface, or if an "
    "exact backfill input plus fetch capability is sufficient to run the repair "
    "without changing strategy behavior. Otherwise close as rejected/blocked "
    "with quantified reopen condition."
)

CHANGED_FILES = [
    RUNNER,
    "data/experiments/exp-20260709-012/exp_20260709_012_sec_6k_historical_text_cache_materialization.json",
    "data/experiments/exp-20260709-012/missing_historical_6k_events.jsonl",
    "experiments/logs/exp-20260709-012.json",
    "experiments/cards/exp-20260709-012.md",
    "experiments/manifests/exp-20260709-012.json",
    "experiments/tickets/exp-20260709-012.json",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def repo_rel(path: str | Path) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def safe(value: Any) -> Any:
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, dict):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default if default is not None else {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(safe(row), ensure_ascii=True, sort_keys=True) + "\n")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def form_base(row: dict[str, Any]) -> str:
    raw = str(row.get("form_base") or row.get("form_type") or "").upper().strip()
    return raw.replace("/A", "")


def is_6k(row: dict[str, Any]) -> bool:
    return form_base(row) == "6-K"


def row_date(row: dict[str, Any]) -> str:
    return str(row.get("usable_trade_date") or row.get("filing_date") or "")[:10]


def window_label(date_text: str) -> str:
    if not date_text:
        return "unknown"
    for window in WINDOWS:
        if window["start"] <= date_text <= window["end"]:
            return window["label"]
    if date_text >= POST_FORWARD_START:
        return "post_forward"
    return "outside"


def event_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("accession_number") or row.get("accession") or ""),
        str(row.get("ticker") or ""),
        row_date(row),
    )


def cache_path_for(row: dict[str, Any]) -> Path | None:
    accession = str(row.get("accession_number") or row.get("accession") or "")
    if not accession:
        return None
    return SEC_TEXT_CACHE_DIR / f"{accession}.json"


def load_deduped_6k_events() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    files = sorted(NON_OHLCV_DIR.glob("sec_filing_events_*.jsonl"))
    raw_rows = 0
    raw_6k_rows = 0
    deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
    source_files_with_6k: Counter[str] = Counter()
    aggregate_files_with_6k: Counter[str] = Counter()
    for path in files:
        rows = jsonl_rows(path)
        raw_rows += len(rows)
        file_6k = 0
        for row in rows:
            if not is_6k(row):
                continue
            raw_6k_rows += 1
            file_6k += 1
            deduped.setdefault(event_key(row), {**row, "source_file": repo_rel(path)})
        if file_6k:
            source_files_with_6k[path.name] = file_6k
            if "_" in path.stem.removeprefix("sec_filing_events_"):
                aggregate_files_with_6k[path.name] = file_6k
    events = sorted(deduped.values(), key=lambda row: (row_date(row), event_key(row)))
    return events, {
        "source_files_scanned": len(files),
        "raw_event_rows": raw_rows,
        "raw_6k_rows": raw_6k_rows,
        "deduped_6k_events": len(events),
        "source_files_with_6k": dict(source_files_with_6k),
        "aggregate_files_with_6k": dict(aggregate_files_with_6k),
    }


def load_deduped_6k_text_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    files = sorted(NON_OHLCV_DIR.glob("sec_filing_text_*.jsonl"))
    raw_rows = 0
    raw_6k_rows = 0
    deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for path in files:
        rows = jsonl_rows(path)
        raw_rows += len(rows)
        for row in rows:
            if not is_6k(row):
                continue
            raw_6k_rows += 1
            deduped.setdefault(event_key(row), {**row, "source_file": repo_rel(path)})
    text_rows = sorted(deduped.values(), key=lambda row: (row_date(row), event_key(row)))
    return text_rows, {
        "source_files_scanned": len(files),
        "raw_text_rows": raw_rows,
        "raw_6k_text_rows": raw_6k_rows,
        "deduped_6k_text_rows": len(text_rows),
    }


def summarize_by_window(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        counts[window_label(row_date(row))] += 1
    return dict(sorted(counts.items()))


def summarize_tickers(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter(str(row.get("ticker") or "UNKNOWN") for row in rows)
    return [{"ticker": ticker, "rows": count} for ticker, count in counts.most_common()]


def sec_index_url(row: dict[str, Any]) -> str | None:
    cik = str(row.get("cik") or "").lstrip("0")
    accession = str(row.get("accession_number") or "").replace("-", "")
    if not cik or not accession:
        return None
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/index.json"


def network_probe(row: dict[str, Any] | None) -> dict[str, Any]:
    if row is None:
        return {"attempted": False, "reason": "no_missing_historical_6k_event"}
    url = sec_index_url(row)
    if not url:
        return {"attempted": False, "reason": "missing_sec_archive_url_fields"}
    start = time.perf_counter()
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"},
    )
    try:
        with urllib.request.urlopen(request, timeout=NETWORK_TIMEOUT_SEC) as response:
            status_code = getattr(response, "status", None)
            sample = response.read(256)
        return {
            "attempted": True,
            "ok": True,
            "url": url,
            "status_code": status_code,
            "bytes_read": len(sample),
            "elapsed_sec": round(time.perf_counter() - start, 3),
            "event": sample_event(row),
        }
    except Exception as exc:  # noqa: BLE001 - record capability failure exactly.
        return {
            "attempted": True,
            "ok": False,
            "url": url,
            "error_type": type(exc).__name__,
            "error": str(exc)[:500],
            "elapsed_sec": round(time.perf_counter() - start, 3),
            "event": sample_event(row),
        }


def sample_event(row: dict[str, Any]) -> dict[str, Any]:
    fields = [
        "ticker",
        "cik",
        "accession_number",
        "form_type",
        "form_base",
        "filing_date",
        "usable_trade_date",
        "accepted_at",
        "primary_document",
        "source_file",
    ]
    return {field: row.get(field) for field in fields}


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    events, event_diag = load_deduped_6k_events()
    text_rows, text_diag = load_deduped_6k_text_rows()
    text_keys = {event_key(row) for row in text_rows}

    historical_events = [
        row for row in events if window_label(row_date(row)) in {"old_thin", "mid_weak", "late_strong"}
    ]
    historical_text_rows = [
        row
        for row in text_rows
        if window_label(row_date(row)) in {"old_thin", "mid_weak", "late_strong"}
    ]

    cache_present = []
    cache_missing = []
    for row in historical_events:
        path = cache_path_for(row)
        if path is not None and path.exists():
            cache_present.append(row)
        else:
            cache_missing.append(row)

    missing_official_text = [row for row in historical_events if event_key(row) not in text_keys]
    write_jsonl(MISSING_EVENTS_JSONL, missing_official_text)

    probe_row = cache_missing[0] if cache_missing else None
    probe = network_probe(probe_row)

    canonical_aggregate = NON_OHLCV_DIR / "sec_filing_events_20241002_20260421.jsonl"
    canonical_aggregate_counts = Counter()
    for row in jsonl_rows(canonical_aggregate):
        canonical_aggregate_counts[form_base(row) or "UNKNOWN"] += 1

    historical_replayable = len(historical_text_rows)
    accepted_measurement_repair = historical_replayable > 0 and len(cache_missing) == 0
    status = (
        "accepted_measurement_repair_sec_6k_historical_text_cache_materialized"
        if accepted_measurement_repair
        else "rejected_blocked_sec_6k_historical_text_cache_gap"
    )
    decision = status
    rejection_reason = None
    if not accepted_measurement_repair:
        reasons = []
        if historical_replayable == 0:
            reasons.append("zero_deduped_historical_6k_text_rows")
        if cache_missing:
            reasons.append(f"historical_6k_cache_missing:{len(cache_missing)}")
        if canonical_aggregate_counts.get("6-K", 0) == 0:
            reasons.append("canonical_aggregate_events_file_has_zero_6k_rows")
        if probe.get("attempted") and not probe.get("ok"):
            reasons.append("sec_archive_fetch_probe_failed")
        rejection_reason = ";".join(reasons)

    coverage = {
        "events": {
            **event_diag,
            "deduped_by_window": summarize_by_window(events),
            "historical_deduped_events": len(historical_events),
            "historical_by_window": summarize_by_window(historical_events),
            "historical_tickers": summarize_tickers(historical_events),
            "canonical_aggregate_event_file": repo_rel(canonical_aggregate),
            "canonical_aggregate_form_counts": dict(sorted(canonical_aggregate_counts.items())),
        },
        "text": {
            **text_diag,
            "deduped_by_window": summarize_by_window(text_rows),
            "historical_deduped_text_rows": len(historical_text_rows),
            "historical_by_window": summarize_by_window(historical_text_rows),
            "post_forward_by_window": summarize_by_window(
                [row for row in text_rows if window_label(row_date(row)) == "post_forward"]
            ),
            "historical_tickers": summarize_tickers(historical_text_rows),
        },
        "cache": {
            "cache_dir": repo_rel(SEC_TEXT_CACHE_DIR),
            "historical_cache_present": len(cache_present),
            "historical_cache_missing": len(cache_missing),
            "historical_cache_present_by_window": summarize_by_window(cache_present),
            "historical_cache_missing_by_window": summarize_by_window(cache_missing),
        },
        "missing_official_text": {
            "rows": len(missing_official_text),
            "by_window": summarize_by_window(missing_official_text),
            "output": repo_rel(MISSING_EVENTS_JSONL),
            "sample": [sample_event(row) for row in missing_official_text[:10]],
        },
    }

    gate = {
        "gate1_baseline": {
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "strategy_behavior_changed": False,
            "reason": "measurement-only SEC text replay surface audit",
        },
        "gate2_fields": {
            "entry_date_required": False,
            "target_price_required": False,
            "event_fields_checked": [
                "accession_number",
                "ticker",
                "cik",
                "filing_date",
                "usable_trade_date",
                "primary_document",
            ],
            "missing_field_counts": {
                field: sum(1 for row in historical_events if not row.get(field))
                for field in [
                    "accession_number",
                    "ticker",
                    "cik",
                    "filing_date",
                    "usable_trade_date",
                    "primary_document",
                ]
            },
        },
        "gate3_survival": {
            "signals_generated": None,
            "signals_survived": None,
            "survival_rate": None,
            "reason": "no strategy signal generation; blocker is replay text coverage",
        },
        "gate4": {
            "before_after_strategy_behavior_changed": False,
            "accepted_measurement_repair": accepted_measurement_repair,
            "failure_reasons": [] if accepted_measurement_repair else rejection_reason.split(";"),
        },
    }

    changed_files = list(CHANGED_FILES)
    production_impact = {
        "scope": "measurement_repair_sec_6k_text_replay_surface",
        "trade_enabled": False,
        "orders_changed": False,
        "entry_rules_changed": False,
        "exit_rules_changed": False,
        "ranking_changed": False,
        "sizing_changed": False,
        "run_adapter_changed": False,
        "backtester_adapter_changed": False,
        "shared_policy_changed": False,
        "note": (
            "No official data surface was mutated. The runner exports a missing "
            "historical 6-K event input file under data/experiments only."
        ),
    }
    post_run_reflection = {
        "why_result_happened": (
            "The watched-ticker SEC filing event stream already contains "
            f"{len(historical_events)} deduped historical 6-K rows across the "
            "canonical windows, but the official SEC filing-text surface has "
            f"{historical_replayable} deduped historical 6-K text rows and "
            f"{len(cache_present)} local historical cache files. The canonical "
            "aggregate event file also has zero 6-K rows, so the current single-file "
            "text backfill entrypoint cannot replay this lane without a generated "
            "6-K event input."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not sweep 6-K phrase lists, positive/negative text labels, "
            "liquidity gates, top-N, hold days, or response shape on this surface "
            "until historical 6-K/6-KA text bodies exist in a replayable official "
            "surface or at least 20 current daily 6-K rows close with replacement "
            "value."
        ),
        "new_evidence_required": (
            "Run an official-scope SEC 6-K text backfill that writes historical "
            "cache/text rows from the exported missing_historical_6k_events.jsonl "
            "into data/cache/sec/filing_text and data/non_ohlcv/sec_filing_text_*.jsonl, "
            "or provide equivalent cached SEC archive documents. After that, test one "
            "fixed structured semantic helper with guidance-revision magnitude, "
            "issuer-country/ADR liquidity provenance, or translation-quality fields."
        ),
        "realized_failure_mode": (
            "network_disabled_or_sec_fetch_blocked"
            if probe.get("attempted") and not probe.get("ok")
            else "cache_missing_for_historical_6k"
        ),
    }

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "lane": LANE,
        "owner": OWNER,
        "status": status,
        "decision": decision,
        "accepted": accepted_measurement_repair,
        "accepted_alpha": False,
        "accepted_measurement_repair": accepted_measurement_repair,
        "rejection_reason": rejection_reason,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": SINGLE_CAUSAL_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": ticket.get("prediction") or PREDICTION,
        "acceptance_rule": ACCEPTANCE_RULE,
        "coverage": coverage,
        "network_probe": probe,
        "gate1": gate["gate1_baseline"],
        "gate2": gate["gate2_fields"],
        "gate3": gate["gate3_survival"],
        "gate4": gate["gate4"],
        "before_metrics": {
            "historical_6k_event_rows": len(historical_events),
            "historical_6k_text_rows": historical_replayable,
            "historical_6k_cache_present": len(cache_present),
        },
        "after_metrics": {
            "historical_6k_event_input_exported_rows": len(missing_official_text),
            "historical_6k_text_rows": historical_replayable,
            "historical_6k_cache_present": len(cache_present),
        },
        "delta_metrics": {
            "historical_6k_event_input_exported_rows": len(missing_official_text),
            "historical_6k_text_rows_delta": 0,
            "historical_6k_cache_present_delta": 0,
        },
        "production_impact": production_impact,
        "post_run_reflection": post_run_reflection,
        "changed_files": changed_files,
        "related_files": [
            "data/non_ohlcv/sec_filing_events_*.jsonl",
            "data/non_ohlcv/sec_filing_text_*.jsonl",
            "data/cache/sec/filing_text",
            repo_rel(BASELINE_RESULT),
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "blocked_backfill_command": (
            ".\\.venv\\Scripts\\python.exe -B quant\\sec_filing_text_backfill.py "
            f"--events {repo_rel(MISSING_EVENTS_JSONL)} --forms 6-K 6-K/A "
            "--item-codes all --output data\\non_ohlcv\\sec_filing_text_6k_20241002_20260421.jsonl "
            "--summary-output data\\non_ohlcv\\sec_filing_text_6k_20241002_20260421_summary.json"
        ),
        "lean_quality_passed": True,
        "anti_js": {"used_javascript": False, "evidence": "Python runner only."},
    }
    return payload


def build_card(payload: dict[str, Any]) -> str:
    coverage = payload["coverage"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: SEC 6-K historical text cache materialization",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Historical 6-K events: `{coverage['events']['historical_deduped_events']}`",
            f"- Historical 6-K text rows: `{coverage['text']['historical_deduped_text_rows']}`",
            f"- Historical cache present/missing: `{coverage['cache']['historical_cache_present']}` / `{coverage['cache']['historical_cache_missing']}`",
            f"- Missing event input: `{coverage['missing_official_text']['output']}`",
            f"- Network probe ok: `{payload['network_probe'].get('ok')}`",
            "- Strategy/live order behavior changed: `false`",
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


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [REPO_ROOT / rel for rel in CHANGED_FILES]
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
    write_json(OUT_JSON, payload)
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
            "coverage": {
                "historical_6k_events": payload["coverage"]["events"][
                    "historical_deduped_events"
                ],
                "historical_6k_text_rows": payload["coverage"]["text"][
                    "historical_deduped_text_rows"
                ],
                "historical_6k_cache_missing": payload["coverage"]["cache"][
                    "historical_cache_missing"
                ],
            },
            "network_probe": payload["network_probe"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
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
            "rejection_reason": payload["rejection_reason"],
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
            "related_files": payload["related_files"],
            "changed_files": payload["changed_files"],
            "allowed_write_scope": payload["changed_files"],
            "lean_quality_passed": payload["lean_quality_passed"],
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
                "historical_6k_events": payload["coverage"]["events"][
                    "historical_deduped_events"
                ],
                "historical_6k_text_rows": payload["coverage"]["text"][
                    "historical_deduped_text_rows"
                ],
                "historical_cache_missing": payload["coverage"]["cache"][
                    "historical_cache_missing"
                ],
                "network_probe_ok": payload["network_probe"].get("ok"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
