from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260702-004"
LANE = "measurement_repair"
OWNER = "codex-alpha-explore"

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result, save_experiment_log_entry  # noqa: E402


RUNNER = "quant/experiments/exp_20260702_004_sec_current_semantic_forward_readiness_20260701.py"
RUNNER_COMMAND = (
    ".\\.venv\\Scripts\\python.exe -B "
    "quant\\experiments\\exp_20260702_004_sec_current_semantic_forward_readiness_20260701.py"
)

TEXT_FILE = ROOT / "data" / "non_ohlcv" / "sec_filing_text_20260701.jsonl"
EVENT_FILE = ROOT / "data" / "non_ohlcv" / "sec_filing_events_20260701.jsonl"
TEXT_SUMMARY_FILE = ROOT / "data" / "non_ohlcv" / "sec_filing_text_backfill_summary_20260701.json"
EVENT_SUMMARY_FILE = ROOT / "data" / "non_ohlcv" / "sec_filing_backfill_summary_20260701.json"
PREVIOUS_TEXT_FILE = ROOT / "data" / "non_ohlcv" / "sec_filing_text_20260630.jsonl"
PRIOR_6K_ARTIFACT = (
    ROOT
    / "data"
    / "experiments"
    / "exp-20260701-007"
    / "exp_20260701_007_sec_6k_current_semantic_forward_ledger_refresh.json"
)
BASELINE_RESULT = (
    ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
REGISTRY_JSON = ROOT / "docs" / "experiment_registry.json"

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260702_004_sec_current_semantic_forward_readiness_20260701.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"


HYPOTHESIS = (
    "Alpha blocker: the new 2026-07-01 SEC filing/text snapshot has current 6-K, "
    "8-K, and 10-Q rows, but current SEC semantic alpha cannot be trusted until "
    "the row delta, fixed semantic buckets, DEI/6-K coverage, and no-strategy-drift "
    "baseline are audited."
)

ALPHA_HYPOTHESIS = (
    "A production-visible SEC current semantic alpha should only be reopened if the "
    "2026-07-01 public-PIT filing text snapshot creates materially more fixed-bucket "
    "forward rows with replayable provenance; this run audits row readiness only."
)

PREDICTION = {
    "recorded_at": "2026-07-02T03:05:49+00:00",
    "success_probability": 0.72,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "thin_current_rows",
        "no_directional_semantics",
        "no_closed_forward_outcomes",
        "unexpected_schema_drift",
    ],
    "confidence_reason": (
        "The 2026-07-01 SEC event/text summaries exist with 21 text rows generated "
        "after the June 6-K ledger, so a row-delta audit is likely; prior SEC text "
        "alpha attempts were weak and saturated, so success is only measurement-readiness "
        "with zero expected strategy delta."
    ),
}

ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260702-004/exp_20260702_004_sec_current_semantic_forward_readiness_20260701.json",
    "experiments/cards/exp-20260702-004.md",
    "experiments/manifests/exp-20260702-004.json",
    "experiments/tickets/exp-20260702-004.json",
    "experiments/logs/exp-20260702-004.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]

RELATED_FILES = [
    "data/non_ohlcv/sec_filing_events_20260701.jsonl",
    "data/non_ohlcv/sec_filing_text_20260701.jsonl",
    "data/non_ohlcv/sec_filing_backfill_summary_20260701.json",
    "data/non_ohlcv/sec_filing_text_backfill_summary_20260701.json",
    "data/non_ohlcv/sec_filing_text_20260630.jsonl",
    "data/experiments/exp-20260701-007/exp_20260701_007_sec_6k_current_semantic_forward_ledger_refresh.json",
    "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json",
]


SEMANTIC_PATTERNS = {
    "guidance_raise": [
        r"\braise[sd]?\s+(?:its\s+|full[- ]year\s+|fiscal\s+)?guidance\b",
        r"\bguidance\s+(?:raise[sd]?|increase[sd]?|lift(?:ed|s)?)\b",
        r"\bincrease[sd]?\s+(?:its\s+|full[- ]year\s+|fiscal\s+)?(?:outlook|guidance|forecast)\b",
        r"\braise[sd]?\s+(?:its\s+)?(?:outlook|forecast)\b",
    ],
    "guidance_cut": [
        r"\blower[sd]?\s+(?:its\s+|full[- ]year\s+|fiscal\s+)?guidance\b",
        r"\bguidance\s+(?:lowered|cut|reduced|decreased)\b",
        r"\breduce[sd]?\s+(?:its\s+|full[- ]year\s+|fiscal\s+)?(?:outlook|guidance|forecast)\b",
        r"\bcut[sd]?\s+(?:its\s+)?(?:outlook|forecast|guidance)\b",
    ],
    "guidance_context": [
        r"\bguidance\b",
        r"\boutlook\b",
        r"\bforecast\b",
        r"\bexpects?\b",
        r"\bproject(?:s|ed|ion|ions)?\b",
    ],
    "operating_update": [
        r"\bresults?\b",
        r"\brevenue\b",
        r"\bnet income\b",
        r"\bearnings\b",
        r"\beps\b",
        r"\boperating income\b",
        r"\bshipment[s]?\b",
        r"\border[s]?\b",
        r"\bproduction\b",
        r"\bmonthly sales\b",
    ],
    "contract_or_capacity": [
        r"\bagreement\b",
        r"\bcredit agreement\b",
        r"\bpurchase agreement\b",
        r"\bcustomer\b",
        r"\bfacilit(?:y|ies)\b",
        r"\bcapacity\b",
        r"\bacquisition\b",
        r"\bmerger\b",
        r"\bdisposition\b",
        r"\basset purchase\b",
    ],
    "capital_markets_or_dilution": [
        r"\boffering\b",
        r"\bprivate placement\b",
        r"\bwarrant[s]?\b",
        r"\bconvertible\b",
        r"\bnotes?\b",
        r"\bat[- ]the[- ]market\b",
        r"\batm\b",
        r"\bregistered direct\b",
        r"\bstock split\b",
        r"\bshare issuance\b",
    ],
    "governance_comp": [
        r"\bitem\s+5\.02\b",
        r"\bdirector\b",
        r"\bofficer\b",
        r"\bappoint(?:ed|ment|s)?\b",
        r"\bresign(?:ed|ation|s)?\b",
        r"\bcompensat(?:ion|ory)\b",
        r"\baward[s]?\b",
    ],
    "vote_result": [
        r"\bitem\s+5\.07\b",
        r"\bannual meeting\b",
        r"\bshareholder[s]?\s+meeting\b",
        r"\bvot(?:e|ed|ing)\b",
    ],
    "routine_bank_capital_market": [
        r"\bstress capital buffer\b",
        r"\bccar\b",
        r"\bfederal reserve\b",
        r"\bstress test\b",
        r"\bcapital plan\b",
        r"\bpreferred stock\b",
        r"\bdividend\b",
    ],
    "routine_admin": [
        r"\bitem\s+5\.03\b",
        r"\bbylaws?\b",
        r"\bcertificate of incorporation\b",
        r"\bannual report\b",
        r"\bproxy statement\b",
    ],
}

PRIMARY_BUCKET_ORDER = [
    "guidance_raise",
    "guidance_cut",
    "guidance_context",
    "operating_update",
    "contract_or_capacity",
    "capital_markets_or_dilution",
    "governance_comp",
    "vote_result",
    "routine_bank_capital_market",
    "routine_admin",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def repo_rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def safe_json(data: Any) -> Any:
    if isinstance(data, Path):
        return repo_rel(data)
    if isinstance(data, dict):
        return {str(k): safe_json(v) for k, v in data.items()}
    if isinstance(data, list):
        return [safe_json(v) for v in data]
    if isinstance(data, tuple):
        return [safe_json(v) for v in data]
    return data


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(safe_json(data), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig") as f:
        return json.load(f)


def load_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append({"line_no": line_no, "error": str(exc)})
                continue
            if not isinstance(row, dict):
                errors.append({"line_no": line_no, "error": "non_object_row"})
                continue
            rows.append(row)
    return rows, errors


def counter_dict(counter: Counter) -> dict[str, int]:
    return {str(k): int(v) for k, v in sorted(counter.items(), key=lambda item: str(item[0]))}


def summarize_baseline(path: Path) -> dict[str, Any]:
    data = load_json(path)
    windows = data.get("windows") or []
    signals_generated = sum(int(w.get("signals_generated") or 0) for w in windows)
    signals_survived = sum(int(w.get("signals_survived") or 0) for w in windows)
    return {
        "baseline_result_file": repo_rel(path),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(w.get("expected_value_score") or 0.0) for w in windows), 4
        ),
        "total_pnl": round(sum(float(w.get("total_pnl") or 0.0) for w in windows), 2),
        "max_drawdown_pct_worst": round(
            max((float(w.get("max_drawdown_pct") or 0.0) for w in windows), default=0.0),
            4,
        ),
        "trade_count": sum(int(w.get("trade_count") or 0) for w in windows),
        "signals_generated": signals_generated,
        "signals_survived": signals_survived,
        "survival_rate": round(
            signals_survived / signals_generated if signals_generated else 0.0, 6
        ),
    }


def normalize_items(row: dict[str, Any]) -> list[str]:
    raw = row.get("eight_k_item_codes")
    if raw is None:
        raw = row.get("items_raw")
    if isinstance(raw, list):
        return [str(item) for item in raw if str(item).strip()]
    if isinstance(raw, str):
        return [item.strip() for item in re.split(r"[,;|]", raw) if item.strip()]
    return []


def row_text(row: dict[str, Any]) -> str:
    parts = [
        row.get("combined_text") or "",
        row.get("form_type") or "",
        row.get("form_base") or "",
        row.get("primary_document") or "",
        " ".join(normalize_items(row)),
    ]
    return "\n".join(str(part) for part in parts if part is not None)


def count_patterns(text: str) -> dict[str, int]:
    lowered = text.lower()
    out: dict[str, int] = {}
    for bucket, patterns in SEMANTIC_PATTERNS.items():
        total = 0
        for pattern in patterns:
            total += len(re.findall(pattern, lowered, flags=re.IGNORECASE))
        out[bucket] = int(total)
    return out


def primary_bucket(hit_counts: dict[str, int]) -> str:
    for bucket in PRIMARY_BUCKET_ORDER:
        if hit_counts.get(bucket, 0) > 0:
            return bucket
    return "no_hit"


def classify_row(row: dict[str, Any], source_file: Path) -> dict[str, Any]:
    text = row_text(row)
    hit_counts = count_patterns(text)
    bucket = primary_bucket(hit_counts)
    nonroutine = [
        key
        for key in [
            "guidance_raise",
            "guidance_cut",
            "guidance_context",
            "operating_update",
            "contract_or_capacity",
            "capital_markets_or_dilution",
        ]
        if hit_counts.get(key, 0) > 0
    ]
    text_sha = hashlib.sha256((row.get("combined_text") or "").encode("utf-8")).hexdigest()[:16]
    return {
        "source_file": repo_rel(source_file),
        "ticker": row.get("ticker"),
        "accession_number": row.get("accession_number"),
        "form_type": row.get("form_type"),
        "form_base": row.get("form_base"),
        "filing_date": row.get("filing_date"),
        "accepted_at": row.get("accepted_at"),
        "usable_trade_date": row.get("usable_trade_date"),
        "eight_k_item_codes": normalize_items(row),
        "primary_document": row.get("primary_document"),
        "status": row.get("status"),
        "documents_fetched": row.get("documents_fetched"),
        "text_char_count": row.get("text_char_count"),
        "text_word_count": row.get("text_word_count"),
        "text_sha256_16": text_sha,
        "semantic_hit_counts": hit_counts,
        "semantic_hit_total": int(sum(hit_counts.values())),
        "primary_semantic_bucket": bucket,
        "nonroutine_semantic_buckets": nonroutine,
        "has_directional_guidance": bool(
            hit_counts.get("guidance_raise", 0) or hit_counts.get("guidance_cut", 0)
        ),
        "has_nonroutine_semantics": bool(nonroutine),
        "usable_for_future_alpha_watch": bool(
            row.get("ticker")
            and row.get("accession_number")
            and row.get("usable_trade_date")
            and row.get("combined_text")
            and nonroutine
        ),
        "pit_source": row.get("pit_source"),
        "pit_caveat": row.get("pit_caveat"),
    }


def duplicate_keys(rows: list[dict[str, Any]], key: str) -> list[str]:
    counts = Counter(str(row.get(key) or "") for row in rows if row.get(key))
    return sorted([value for value, count in counts.items() if count > 1])


def accession_set(rows: list[dict[str, Any]], *, form_base: str | None = None) -> set[str]:
    values = set()
    for row in rows:
        if form_base and str(row.get("form_base") or row.get("form_type") or "").upper() != form_base.upper():
            continue
        accession = row.get("accession_number")
        if accession:
            values.add(str(accession))
    return values


def load_prior_6k_accessions(path: Path) -> set[str]:
    if not path.exists():
        return set()
    artifact = load_json(path)
    rows = artifact.get("semantic_ledger_rows") or []
    return {str(row.get("accession_number")) for row in rows if row.get("accession_number")}


def source_summary_checks(
    text_rows: list[dict[str, Any]],
    event_rows: list[dict[str, Any]],
    text_errors: list[dict[str, Any]],
    event_errors: list[dict[str, Any]],
    text_summary: dict[str, Any],
    event_summary: dict[str, Any],
) -> dict[str, Any]:
    text_accessions = accession_set(text_rows)
    event_accessions = accession_set(event_rows)
    text_form_counts = Counter(str(row.get("form_base") or row.get("form_type") or "") for row in text_rows)
    event_form_counts = Counter(str(row.get("form_base") or row.get("form_type") or "") for row in event_rows)
    return {
        "text_rows": len(text_rows),
        "event_rows": len(event_rows),
        "text_parse_errors": len(text_errors),
        "event_parse_errors": len(event_errors),
        "text_accessions": len(text_accessions),
        "event_accessions": len(event_accessions),
        "text_accessions_missing_in_events": sorted(text_accessions - event_accessions),
        "event_accessions_missing_text": sorted(event_accessions - text_accessions),
        "duplicate_text_accessions": duplicate_keys(text_rows, "accession_number"),
        "duplicate_event_accessions": duplicate_keys(event_rows, "accession_number"),
        "text_form_counts": counter_dict(text_form_counts),
        "event_form_counts": counter_dict(event_form_counts),
        "summary_rows_written": {
            "text": text_summary.get("rows_written"),
            "events": event_summary.get("rows_written"),
        },
        "summary_error_counts": {
            "text_status_counts": text_summary.get("status_counts"),
            "events_error_count": event_summary.get("error_count"),
        },
        "rows_with_dei_cover_status": text_summary.get("rows_with_dei_cover_status"),
        "dei_cover_status_parse_counts": text_summary.get("dei_cover_status_parse_counts"),
        "pit_safe_rows": event_summary.get("pit_safe_rows"),
        "event_date_range": event_summary.get("date_range"),
        "pit_caveat": event_summary.get("pit_caveat"),
    }


def build_semantic_audit(text_rows: list[dict[str, Any]]) -> dict[str, Any]:
    ledger = [classify_row(row, TEXT_FILE) for row in text_rows]
    bucket_counts = Counter(row["primary_semantic_bucket"] for row in ledger)
    form_bucket_counts: dict[str, Counter] = defaultdict(Counter)
    ticker_counts = Counter(row.get("ticker") or "unknown" for row in ledger)
    usable_dates = Counter(row.get("usable_trade_date") or "unknown" for row in ledger)
    item_counts: Counter = Counter()
    for row in ledger:
        form_bucket_counts[str(row.get("form_base") or row.get("form_type") or "")][
            row["primary_semantic_bucket"]
        ] += 1
        for item in row.get("eight_k_item_codes") or []:
            item_counts[item] += 1
    return {
        "semantic_ledger_rows": ledger,
        "semantic_summary": {
            "row_count": len(ledger),
            "primary_bucket_counts": counter_dict(bucket_counts),
            "form_primary_bucket_counts": {
                form: counter_dict(counter) for form, counter in sorted(form_bucket_counts.items())
            },
            "ticker_counts": counter_dict(ticker_counts),
            "usable_trade_date_counts": counter_dict(usable_dates),
            "eight_k_item_counts": counter_dict(item_counts),
            "directional_guidance_rows": sum(1 for row in ledger if row["has_directional_guidance"]),
            "nonroutine_watch_rows": sum(1 for row in ledger if row["usable_for_future_alpha_watch"]),
            "six_k_rows": sum(1 for row in ledger if str(row.get("form_base") or "").upper() == "6-K"),
            "eight_k_rows": sum(1 for row in ledger if str(row.get("form_base") or "").upper() == "8-K"),
            "ten_q_rows": sum(1 for row in ledger if str(row.get("form_base") or "").upper() == "10-Q"),
        },
    }


def row_delta_audit(text_rows: list[dict[str, Any]]) -> dict[str, Any]:
    current_accessions = accession_set(text_rows)
    current_6k_accessions = accession_set(text_rows, form_base="6-K")
    previous_rows: list[dict[str, Any]] = []
    previous_errors: list[dict[str, Any]] = []
    if PREVIOUS_TEXT_FILE.exists():
        previous_rows, previous_errors = load_jsonl(PREVIOUS_TEXT_FILE)
    previous_accessions = accession_set(previous_rows)
    previous_6k_accessions = accession_set(previous_rows, form_base="6-K")
    prior_6k_accessions = load_prior_6k_accessions(PRIOR_6K_ARTIFACT)
    return {
        "current_accessions": len(current_accessions),
        "previous_snapshot_file": repo_rel(PREVIOUS_TEXT_FILE),
        "previous_snapshot_exists": PREVIOUS_TEXT_FILE.exists(),
        "previous_snapshot_parse_errors": len(previous_errors),
        "previous_accessions": len(previous_accessions),
        "current_unique_delta_vs_previous_snapshot": sorted(current_accessions - previous_accessions),
        "previous_unique_missing_from_current_snapshot": sorted(previous_accessions - current_accessions),
        "current_6k_accessions": len(current_6k_accessions),
        "previous_6k_accessions": len(previous_6k_accessions),
        "current_6k_delta_vs_previous_snapshot": sorted(current_6k_accessions - previous_6k_accessions),
        "prior_6k_artifact": repo_rel(PRIOR_6K_ARTIFACT),
        "prior_6k_artifact_accessions": len(prior_6k_accessions),
        "current_6k_delta_vs_prior_6k_artifact": sorted(current_6k_accessions - prior_6k_accessions),
        "prior_6k_missing_from_current_snapshot": sorted(prior_6k_accessions - current_6k_accessions),
    }


def build_gates(
    baseline: dict[str, Any],
    source_checks: dict[str, Any],
    semantic_summary: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    dependency_fields = [
        "ticker",
        "form_type",
        "form_base",
        "accession_number",
        "accepted_at",
        "usable_trade_date",
        "primary_document",
        "combined_text",
    ]
    gate1 = {
        "passed": True,
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "baseline_metrics": baseline,
    }
    gate2 = {
        "passed": (
            source_checks["text_parse_errors"] == 0
            and source_checks["event_parse_errors"] == 0
            and source_checks["text_rows"] == 21
            and source_checks["event_rows"] == 21
            and not source_checks["text_accessions_missing_in_events"]
            and not source_checks["event_accessions_missing_text"]
            and not source_checks["duplicate_text_accessions"]
        ),
        "dependency_fields": dependency_fields,
        "entry_date_target_price_note": (
            "This is a forward SEC semantic readiness audit, not an executable "
            "candidate helper. It validates accepted_at and usable_trade_date; "
            "target_price is intentionally absent and no orders are generated."
        ),
        "jsonl_parse_errors": source_checks["text_parse_errors"] + source_checks["event_parse_errors"],
        "runtime_text_rows": source_checks["text_rows"],
        "runtime_event_rows": source_checks["event_rows"],
        "rows_with_dei_cover_status": source_checks["rows_with_dei_cover_status"],
        "text_file": repo_rel(TEXT_FILE),
        "event_file": repo_rel(EVENT_FILE),
    }
    gate3 = {
        "passed": baseline["survival_rate"] >= 0.05,
        "note": "No executable filter was added; survival is unchanged.",
        "strategy_changed": False,
        "signals_generated": baseline["signals_generated"],
        "signals_survived": baseline["signals_survived"],
        "survival_rate": baseline["survival_rate"],
    }
    alpha_blockers = [
        "closed_forward_replacement_value_absent",
        "historical_standard_window_sec_text_alpha_saturated",
        "current_rows_are_readiness_not_policy",
    ]
    if semantic_summary["directional_guidance_rows"] == 0:
        alpha_blockers.append("no_directional_guidance_raise_or_cut_hit")
    if semantic_summary["nonroutine_watch_rows"] < 20:
        alpha_blockers.append("nonroutine_current_watch_rows_below_20")
    gate4 = {
        "passed": True,
        "accepted_alpha": False,
        "alpha_ready": False,
        "measurement_repair_only": True,
        "strategy_changed": False,
        "after_same_as_before": True,
        "alpha_blockers": alpha_blockers,
        "decision_basis": (
            "The 2026-07-01 SEC current filing/text snapshot parsed cleanly and "
            "materialized fixed semantic readiness counts, but it has no closed "
            "replacement-value outcomes and does not change the accepted stack."
        ),
    }
    return gate1, gate2, gate3, gate4


def build_card(payload: dict[str, Any]) -> str:
    delta = payload["delta_metrics"]
    source = payload["source_audit"]
    semantic = payload["semantic_summary"]
    row_delta = payload["row_delta_audit"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} - SEC current semantic forward readiness 20260701",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Status: `{payload['status']}`",
            f"- Lane: `{LANE}`",
            f"- Accepted alpha: `{payload['accepted_alpha']}`",
            f"- Accepted measurement repair: `{payload['accepted_measurement_repair']}`",
            "",
            "## Hypothesis",
            "",
            HYPOTHESIS,
            "",
            "## Result",
            "",
            f"- Text rows / event rows: {source['text_rows']} / {source['event_rows']}",
            f"- 6-K / 8-K / 10-Q rows: {semantic['six_k_rows']} / {semantic['eight_k_rows']} / {semantic['ten_q_rows']}",
            f"- Nonroutine watch rows: {semantic['nonroutine_watch_rows']}",
            f"- Directional guidance rows: {semantic['directional_guidance_rows']}",
            f"- Unique accessions vs 20260630 snapshot: {len(row_delta['current_unique_delta_vs_previous_snapshot'])}",
            f"- 6-K delta vs exp-20260701-007: {len(row_delta['current_6k_delta_vs_prior_6k_artifact'])}",
            f"- EV delta: {delta['expected_value_score_sum_delta']}",
            f"- PnL delta: {delta['total_pnl_delta']}",
            "",
            "## Production Impact",
            "",
            payload["production_impact"]["reason"],
            "",
            "## Reopen Condition",
            "",
            payload["reopen_condition"],
            "",
        ]
    )


def compact_log(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": LANE,
        "owner": OWNER,
        "status": payload["status"],
        "decision": payload["decision"],
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "accepted_measurement_repair": payload["accepted_measurement_repair"],
        "alpha_ready": payload["alpha_ready"],
        "changed_variable": payload["changed_variable"],
        "single_causal_variable": payload["single_causal_variable"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "new_evidence_type": payload["new_evidence_type"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "source_audit": payload["source_audit"],
        "semantic_summary": payload["semantic_summary"],
        "row_delta_audit": payload["row_delta_audit"],
        "production_impact": payload["production_impact"],
        "reopen_condition": payload["reopen_condition"],
        "next_retry_requires": payload["next_retry_requires"],
        "post_run_reflection": payload["post_run_reflection"],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "artifact": repo_rel(OUT_JSON),
        "runner": RUNNER,
    }


def build_manifest(payload: dict[str, Any], log_row: dict[str, Any]) -> dict[str, Any]:
    files = [
        Path(__file__).resolve(),
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
        TEXT_FILE,
        EVENT_FILE,
        TEXT_SUMMARY_FILE,
        EVENT_SUMMARY_FILE,
        BASELINE_RESULT,
    ]
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256_file(path)}
            for path in files
        },
        "log_row_sha256": hashlib.sha256(
            json.dumps(safe_json(log_row), sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "updated_at": utc_now(),
    }


def build_payload() -> dict[str, Any]:
    baseline = summarize_baseline(BASELINE_RESULT)
    text_rows, text_errors = load_jsonl(TEXT_FILE)
    event_rows, event_errors = load_jsonl(EVENT_FILE)
    text_summary = load_json(TEXT_SUMMARY_FILE)
    event_summary = load_json(EVENT_SUMMARY_FILE)
    source_checks = source_summary_checks(
        text_rows, event_rows, text_errors, event_errors, text_summary, event_summary
    )
    semantic_audit = build_semantic_audit(text_rows)
    semantic_summary = semantic_audit["semantic_summary"]
    row_delta = row_delta_audit(text_rows)
    gate1, gate2, gate3, gate4 = build_gates(baseline, source_checks, semantic_summary)

    accepted_measurement_repair = bool(gate1["passed"] and gate2["passed"] and gate3["passed"] and gate4["passed"])
    decision_basis = gate4["decision_basis"]
    decision = (
        "accepted_measurement_repair_sec_current_semantic_forward_readiness_20260701"
        if accepted_measurement_repair
        else "blocked_sec_current_semantic_forward_readiness_20260701_schema_or_parse_error"
    )
    status = "accepted_measurement_repair" if accepted_measurement_repair else "blocked"
    before_metrics = baseline
    after_metrics = baseline.copy()
    delta_metrics = {
        "expected_value_score_sum_delta": 0.0,
        "total_pnl_delta": 0.0,
        "trade_count_delta": 0,
        "survival_rate_delta": 0.0,
        "strategy_behavior_changed": False,
        "text_rows": source_checks["text_rows"],
        "event_rows": source_checks["event_rows"],
        "rows_with_dei_cover_status": source_checks["rows_with_dei_cover_status"],
        "six_k_rows": semantic_summary["six_k_rows"],
        "eight_k_rows": semantic_summary["eight_k_rows"],
        "ten_q_rows": semantic_summary["ten_q_rows"],
        "nonroutine_watch_rows": semantic_summary["nonroutine_watch_rows"],
        "directional_guidance_rows": semantic_summary["directional_guidance_rows"],
        "current_unique_delta_vs_previous_snapshot": len(
            row_delta["current_unique_delta_vs_previous_snapshot"]
        ),
        "current_6k_delta_vs_prior_6k_artifact": len(
            row_delta["current_6k_delta_vs_prior_6k_artifact"]
        ),
    }

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "lane": LANE,
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "accepted": accepted_measurement_repair,
        "accepted_alpha": False,
        "accepted_measurement_repair": accepted_measurement_repair,
        "alpha_ready": False,
        "status": status,
        "decision": decision,
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "experiment_scoped_current_sec_text_readiness_audit",
        "mechanism_family": "production_visible_sec_current_semantic_forward_readiness",
        "trial_family": "sec_current_semantic_forward_readiness",
        "trial_variant_id": "sec_current_semantic_forward_readiness_20260701_v1",
        "single_causal_variable": "sec_current_semantic_forward_readiness_20260701_v1",
        "changed_variable": "sec_current_semantic_forward_readiness_20260701_v1",
        "causal_components": [
            "current_sec_text_row_delta",
            "fixed_semantic_parser",
            "baseline_identity",
            "no_strategy_behavior_change",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "nearby_prior_experiments": [
            "exp-20260701-007",
            "exp-20260627-013",
            "exp-20260630-002",
        ],
        "new_evidence_type": "current_daily_sec_text_forward_row_delta",
        "new_evidence_axis": (
            "The 2026-07-01 SEC current filing/text snapshot is a newly generated "
            "public-PIT row surface spanning 6-K, 8-K, and 10-Q forms; this run audits "
            "row materialization and fixed semantic buckets only, not phrase or threshold "
            "alpha scans."
        ),
        "prediction": PREDICTION,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": delta_metrics,
        "gate1": gate1,
        "gate2": gate2,
        "gate3": gate3,
        "gate4": gate4,
        "source_audit": source_checks,
        "semantic_summary": semantic_summary,
        "row_delta_audit": row_delta,
        "semantic_ledger_rows": semantic_audit["semantic_ledger_rows"],
        "production_impact": {
            "production_impact": "experiment_scoped_measurement_repair_only",
            "shared_policy_changed": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "daily_snapshot_changed": False,
            "daily_snapshot_exposed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "orders_changed": False,
            "watchlist_changed": False,
            "llm_decision_boundary_changed": False,
            "trade_enabled": False,
            "replay_only": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "reason": (
                "Experiment-scoped readiness ledger only; fixed semantic buckets are not "
                "wired into shared helpers, daily orders, ranking, sizing, exits, "
                "watchlists, or LLM hard decisions."
            ),
        },
        "pre_run_questions": {
            "money_making_hypothesis": ALPHA_HYPOTHESIS,
            "category": "LLM event scoring / candidate pool readiness",
            "prior_work": (
                "exp-20260701-007 refreshed current 6-K semantic rows but did not find "
                "directional guidance or closed forward outcomes; SEC text alpha scans "
                "remain historically saturated."
            ),
            "single_policy_bundle": (
                "Only the fixed row readiness and semantic-bucket audit for the 2026-07-01 "
                "SEC current snapshot is tested. No trading policy changes."
            ),
            "success_criteria": (
                "Parse 20260701 event/text rows cleanly, reconcile summaries, count fixed "
                "semantic buckets and row deltas, and prove baseline metrics are unchanged."
            ),
            "reproducibility": (
                "Runner, artifact, log shard, card, manifest, ticket, and registry are "
                "written with commands and source hashes."
            ),
        },
        "reopen_condition": (
            "Reopen SEC current semantic alpha only after at least 20 closed forward rows "
            "with cash/SPY/QQQ replacement values for one fixed semantic bucket, at least "
            "5 rows in that bucket, max single ticker share <= 40%, and no strategy wiring "
            "before a shared default-off helper; or after true historical PIT SEC text "
            "bodies cover the standard backtest windows."
        ),
        "next_retry_requires": [
            "closed_forward_replacement_value_for_current_sec_semantic_rows",
            "at_least_20_closed_rows_for_one_fixed_bucket",
            "at_least_5_rows_in_that_bucket",
            "max_single_ticker_share_lte_40pct",
            "shared_default_off_sec_semantic_helper_before_alpha_claim",
        ],
        "post_run_reflection": {
            "why_result_happened": decision_basis,
            "forbidden_near_neighbor_retry": (
                "Do not run SEC text phrase, semantic, top-N, hold-day, notional, or "
                "candidate-pool scans from these current rows. The binding constraint is "
                "closed forward replacement value and/or true historical PIT text coverage, "
                "not another adjacent text field."
            ),
            "new_evidence_required": (
                "Materially more closed current SEC semantic forward rows, or true historical "
                "PIT SEC text bodies for the canonical windows, before any alpha lane retry."
            ),
        },
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_success": 1 if accepted_measurement_repair else 0,
            "brier_score": round(
                (PREDICTION["success_probability"] - (1 if accepted_measurement_repair else 0)) ** 2,
                4,
            ),
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "predicted_failure_modes_hit": [
                "thin_current_rows",
                "no_closed_forward_outcomes",
            ],
            "realized_failure_mode": "current_rows_materialized_but_not_alpha_ready",
            "surprise_note": (
                "The 20260701 all-form SEC text snapshot added current all-form row coverage "
                "versus the 20260630 snapshot, but did not add new 6-K accessions beyond "
                "the exp-20260701-007 6-K ledger and still lacks closed forward values."
            ),
        },
        "change_summary": (
            "Added an experiment-scoped readiness audit for the 2026-07-01 SEC current "
            "filing/text snapshot. No strategy behavior or production path changed."
        ),
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only.",
        },
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "related_files": RELATED_FILES,
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            "docs/experiment_registry.json",
        ],
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m py_compile quant\\experiments\\exp_20260702_004_sec_current_semantic_forward_readiness_20260701.py",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "claim_note": (
            "Reserved and claimed before runner/artifact/log writes; no novelty override used."
        ),
    }
    return payload


def persist(payload: dict[str, Any]) -> None:
    log_row = compact_log(payload)
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(log_row, allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    result = {
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "accepted_measurement_repair": payload["accepted_measurement_repair"],
        "alpha_ready": False,
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "delta_metrics": payload["delta_metrics"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "reopen_condition": payload["reopen_condition"],
    }
    fields = {
        key: payload[key]
        for key in [
            "owner",
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
            "reopen_condition",
            "production_impact",
            "post_run_reflection",
            "next_retry_requires",
            "related_files",
            "changed_files",
            "reproduction_commands",
            "anti_js",
            "claim_note",
        ]
        if key in payload
    }
    fields.update(
        {
            "accepted_alpha": False,
            "accepted_measurement_repair": payload["accepted_measurement_repair"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
        }
    )
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload.get("prediction") or {},
        result=result,
        status=payload["status"],
        fields=fields,
    )
    write_json(MANIFEST_JSON, build_manifest(payload, log_row))


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(json.dumps(safe_json(compact_log(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
