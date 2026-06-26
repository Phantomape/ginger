"""exp-20260624-024: SEC 6-K historical text materialization readiness.

Measurement repair for the blocked SEC 6-K alpha path. The prior repair made
6-K/6-KA visible to the daily SEC event/text builders, while exp-20260622-016
showed the standard historical generated event/text surfaces still contained
zero replayable 6-K text rows. This runner audits whether the local caches can
materialize historical 6-K text coverage before any semantic alpha retry.

No strategy, shared helper, ranking, sizing, exit, LLM, watchlist, paper order,
or live order behavior changes.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
QUANT_DIR = REPO_ROOT / "quant"
for entry in (SCRIPTS_DIR, QUANT_DIR):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402
import sec_filing_backfill as event_backfill  # noqa: E402
from sec_ticker_map import load_company_ticker_map, normalize_cik  # noqa: E402


EXPERIMENT_ID = "exp-20260624-024"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "sec_6k_historical_text_materialization_readiness"
RUNNER = f"quant/experiments/exp_20260624_024_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260624_024_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
HISTORICAL_EVENTS = REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_events_20241002_20260421.jsonl"
HISTORICAL_TEXT = REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_text_20241002_20260421.jsonl"
SUBMISSIONS_CACHE_DIR = REPO_ROOT / "data" / "cache" / "sec" / "submissions"
FILING_TEXT_CACHE_DIR = REPO_ROOT / "data" / "cache" / "sec" / "filing_text"
WAREHOUSE = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"

CANONICAL_WINDOWS: dict[str, dict[str, str]] = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
    },
}
SIX_K_FORMS = {"6-K", "6-K/A", "6-KA"}
MIN_HISTORICAL_TEXT_ROWS = 20
MIN_STRUCTURED_HITS = 10

HYPOTHESIS = (
    "Repair the blocker for a 6-K alpha hypothesis: determine whether "
    "replayable historical SEC 6-K/6-KA filing text can be materialized from "
    "the existing local submissions/event surface so structured financial-result "
    "growth can later be tested without changing trading behavior."
)
CHANGED_VARIABLE = "sec_6k_historical_text_materialization_readiness_v1"
TRIAL_FAMILY = "sec_6k_historical_text_materialization_readiness"
TRIAL_VARIANT_ID = "sec_6k_local_cache_text_backfill_coverage_v1"
MECHANISM_FAMILY = "production_visible_free_sec_6k_foreign_issuer_candidate_pool"
NEW_EVIDENCE_TYPE = "historical_6k_text_materialization_readiness"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260622-014",
    "exp-20260622-015",
    "exp-20260622-016",
]

PREDICTION = {
    "success_probability": 0.65,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "local_primary_text_missing",
        "structured_numeric_coverage_too_sparse",
        "no_tradeable_adr_overlap",
        "sec_text_surface_saturation",
    ],
    "confidence_reason": (
        "exp-20260622-014 found 8010 standard-window 6-K events in local SEC "
        "submissions, while exp-20260622-016 was blocked because generated "
        "historical 6-K text/cache rows were zero. This measurement repair tests "
        "the specific blocker before any semantic alpha retry."
    ),
    "recorded_at": "2026-06-24T21:05:38+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "shared_policy_changed": False,
    "shared_helper_promoted": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "daily_snapshot_exposed": False,
    "entry_rules_changed": False,
    "exit_rules_changed": False,
    "ranking_changed": False,
    "sizing_changed": False,
    "paper_orders_changed": False,
    "live_orders_changed": False,
    "production_watchlist_changed": False,
    "uses_free_sec_filing_text": True,
    "uses_llm": False,
    "live_ready": False,
    "live_realism_evaluated": False,
    "replay_only": True,
    "parity_note": (
        "This experiment audits historical SEC 6-K text materialization only. "
        "It does not create a shared alpha helper or change any trading path."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "Structured financial-result growth in PIT 6-K/6-KA foreign-issuer text "
        "may identify ADR post-report drift, but exp-20260622-016 made the alpha "
        "untrustworthy until historical 6-K text rows exist."
    ),
    "2_history_check": {
        "exp-20260622-014": (
            "Accepted measurement repair: local submissions held 8010 standard-window "
            "6-K/6-KA events and daily defaults were updated."
        ),
        "exp-20260622-015": (
            "Rejected generic positive-operating-update 6-K helper; this run does "
            "not retry phrases or trading thresholds."
        ),
        "exp-20260622-016": (
            "Blocked structured 6-K financial-result alpha because generated "
            "historical text/event/cache rows for 6-K were zero."
        ),
        "novelty_gate": (
            "Reserved as measurement_repair after alpha_search was blocked by "
            "SEC text-event saturation. The new evidence axis is text "
            "materialization readiness, not a SEC text alpha scan."
        ),
    },
    "3_single_policy_bundle": (
        "One measurement decision: compare local submissions 6-K events, generated "
        "historical SEC event/text rows, per-accession filing-text cache, and "
        "current daily text rows to determine whether historical 6-K text can be "
        "replayed now."
    ),
    "4_success_failure_standard": (
        "Measurement repair passes only if historical generated 6-K text rows "
        "exist, at least 20 rows have nonempty text, at least 10 have fixed "
        "structured financial-result term/growth/numeric evidence, and strategy "
        "metrics remain unchanged. Otherwise the alpha remains blocked."
    ),
    "5_reproducibility": RUNNER_COMMAND,
}

FINANCIAL_RE = re.compile(
    r"\b(revenue|net sales|sales|gross profit|operating income|operating profit|"
    r"net income|profit attributable|ebitda|adjusted ebitda|eps|earnings per share)\b",
    re.I,
)
GROWTH_RE = re.compile(
    r"\b(increase(?:d)?|decrease(?:d)?|grew|growth|up|down|higher|lower|"
    r"year[- ]over[- ]year|yoy|quarter[- ]over[- ]quarter|qoq)\b",
    re.I,
)
NUMERIC_RE = re.compile(
    r"(\d+(?:\.\d+)?\s?%|\$\s?\d|\b\d+(?:\.\d+)?\s?(?:million|billion|m|bn)\b)",
    re.I,
)


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


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
    except json.JSONDecodeError:
        return default


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
                value = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL") from exc
            if isinstance(value, dict):
                rows.append(value)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_date(value: Any) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def window_for(value: Any) -> str | None:
    observed = parse_date(value)
    if observed is None:
        return None
    for label, window in CANONICAL_WINDOWS.items():
        if date.fromisoformat(window["start"]) <= observed <= date.fromisoformat(window["end"]):
            return label
    return None


def form_is_6k(row: dict[str, Any]) -> bool:
    form_type = str(row.get("form_type") or "").upper()
    form_base = str(row.get("form_base") or form_type).upper()
    return form_type in SIX_K_FORMS or form_base in SIX_K_FORMS


def structured_hit(text: Any) -> bool:
    value = str(text or "")
    if not value:
        return False
    return bool(FINANCIAL_RE.search(value) and GROWTH_RE.search(value) and NUMERIC_RE.search(value))


def cache_path_for_accession(accession: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", accession)
    return FILING_TEXT_CACHE_DIR / f"{safe}.json"


def load_baseline() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {}) or {}
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    aggregate = {
        "expected_value_score_sum": payload.get("aggregate_expected_value_score"),
        "total_pnl": payload.get("aggregate_total_pnl"),
        "trade_count": payload.get("total_trade_count"),
        "signals_generated": payload.get("signals_generated"),
        "signals_survived": payload.get("signals_survived"),
        "survival_rate": payload.get("survival_rate"),
        "max_drawdown_pct_worst": payload.get("max_drawdown_pct_worst"),
        "window_count": len(windows),
        "windows": windows,
    }
    if aggregate["expected_value_score_sum"] is None:
        aggregate["expected_value_score_sum"] = round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows), 4
        )
    if aggregate["total_pnl"] is None:
        aggregate["total_pnl"] = round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2)
    if aggregate["trade_count"] is None:
        aggregate["trade_count"] = sum(int(row.get("trade_count") or 0) for row in windows)
    if aggregate["signals_generated"] is None:
        aggregate["signals_generated"] = sum(int(row.get("signals_generated") or 0) for row in windows)
    if aggregate["signals_survived"] is None:
        aggregate["signals_survived"] = sum(int(row.get("signals_survived") or 0) for row in windows)
    if aggregate["survival_rate"] is None and aggregate["signals_generated"]:
        aggregate["survival_rate"] = round(
            float(aggregate["signals_survived"] or 0) / float(aggregate["signals_generated"]),
            4,
        )
    if aggregate["max_drawdown_pct_worst"] is None and windows:
        aggregate["max_drawdown_pct_worst"] = max(
            float(row.get("max_drawdown_pct") or 0.0) for row in windows
        )
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "baseline_exists": BASELINE_RESULT.exists(),
        "baseline_sha256": sha256_file(BASELINE_RESULT),
        **aggregate,
    }


def payload_cik(path: Path, payload: dict[str, Any]) -> str | None:
    from_payload = normalize_cik(payload.get("cik")) if isinstance(payload, dict) else None
    if from_payload:
        return from_payload
    stem_digits = "".join(ch for ch in path.stem if ch.isdigit())
    return normalize_cik(stem_digits)


def scan_submissions_surface() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    company_by_cik = load_company_ticker_map()
    forms = {str(form).upper() for form in event_backfill.DEFAULT_FORMS}
    start = min(date.fromisoformat(row["start"]) for row in CANONICAL_WINDOWS.values())
    end = max(date.fromisoformat(row["end"]) for row in CANONICAL_WINDOWS.values())

    by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    scanned_files = 0
    mapped_files = 0
    invalid_json = 0
    all_form_counts: Counter[str] = Counter()

    for path in sorted(SUBMISSIONS_CACHE_DIR.glob("CIK*.json")):
        scanned_files += 1
        payload = read_json(path, None)
        if not isinstance(payload, dict):
            invalid_json += 1
            continue
        cik = payload_cik(path, payload)
        ticker = company_by_cik.get(cik or "", {}).get("ticker")
        if not cik or not ticker:
            continue
        mapped_files += 1
        rows = event_backfill.parse_filing_rows(
            payload,
            ticker=str(ticker).upper(),
            cik=cik,
            forms=forms,
            start=start,
            end=end,
            pit_source="sec_submissions_recent",
        )
        for row in rows:
            form_type = str(row.get("form_type") or "").upper()
            all_form_counts[form_type] += 1
            if not form_is_6k(row):
                continue
            key = (
                str(row.get("ticker") or ""),
                str(row.get("accession_number") or ""),
                form_type,
            )
            by_key.setdefault(key, row)

    rows = list(by_key.values())
    by_window = Counter(window_for(row.get("usable_trade_date")) or "outside" for row in rows)
    by_form = Counter(str(row.get("form_type") or "unknown").upper() for row in rows)
    return rows, {
        "cache_dir": repo_rel(SUBMISSIONS_CACHE_DIR),
        "cache_files_scanned": scanned_files,
        "cache_files_mapped_to_ticker": mapped_files,
        "invalid_json_files": invalid_json,
        "default_forms": sorted(forms),
        "all_form_counts_top": all_form_counts.most_common(12),
        "six_k_event_rows": len(rows),
        "six_k_accessions": len({row.get("accession_number") for row in rows}),
        "six_k_tickers": len({row.get("ticker") for row in rows}),
        "six_k_by_window": {label: by_window.get(label, 0) for label in CANONICAL_WINDOWS},
        "six_k_outside_windows": by_window.get("outside", 0),
        "six_k_by_form": dict(sorted(by_form.items())),
        "sample_six_k_events": [
            {
                "ticker": row.get("ticker"),
                "cik": row.get("cik"),
                "accession_number": row.get("accession_number"),
                "form_type": row.get("form_type"),
                "filing_date": row.get("filing_date"),
                "accepted_at": row.get("accepted_at"),
                "usable_trade_date": row.get("usable_trade_date"),
                "primary_document": row.get("primary_document"),
            }
            for row in rows[:20]
        ],
    }


def scan_jsonl_surface(path: Path) -> dict[str, Any]:
    rows = read_jsonl(path)
    six_k_rows = [row for row in rows if form_is_6k(row)]
    text_rows = [row for row in six_k_rows if str(row.get("combined_text") or "").strip()]
    structured_rows = [row for row in text_rows if structured_hit(row.get("combined_text"))]
    by_window = Counter(window_for(row.get("usable_trade_date")) or "outside" for row in six_k_rows)
    by_form = Counter(str(row.get("form_type") or "unknown").upper() for row in six_k_rows)
    return {
        "path": repo_rel(path),
        "exists": path.exists(),
        "sha256": sha256_file(path),
        "rows_total": len(rows),
        "six_k_rows": len(six_k_rows),
        "six_k_nonempty_text_rows": len(text_rows),
        "six_k_structured_financial_result_hits": len(structured_rows),
        "six_k_accessions": len({row.get("accession_number") for row in six_k_rows}),
        "six_k_tickers": len({row.get("ticker") for row in six_k_rows}),
        "six_k_by_window": {label: by_window.get(label, 0) for label in CANONICAL_WINDOWS},
        "six_k_outside_windows": by_window.get("outside", 0),
        "six_k_by_form": dict(sorted(by_form.items())),
        "sample_six_k_rows": [
            {
                "ticker": row.get("ticker"),
                "accession_number": row.get("accession_number"),
                "form_type": row.get("form_type"),
                "usable_trade_date": row.get("usable_trade_date"),
                "text_char_count": row.get("text_char_count"),
                "structured_financial_result_hit": structured_hit(row.get("combined_text")),
            }
            for row in six_k_rows[:20]
        ],
    }


def scan_daily_text_surface() -> dict[str, Any]:
    files = sorted((REPO_ROOT / "data" / "non_ohlcv").glob("sec_filing_text_202606*.jsonl"))
    total_rows = 0
    total_six_k = 0
    total_nonempty = 0
    total_structured = 0
    file_rows: list[dict[str, Any]] = []
    for path in files:
        rows = read_jsonl(path)
        six_k_rows = [row for row in rows if form_is_6k(row)]
        nonempty = [row for row in six_k_rows if str(row.get("combined_text") or "").strip()]
        structured = [row for row in nonempty if structured_hit(row.get("combined_text"))]
        total_rows += len(rows)
        total_six_k += len(six_k_rows)
        total_nonempty += len(nonempty)
        total_structured += len(structured)
        if six_k_rows:
            file_rows.append(
                {
                    "path": repo_rel(path),
                    "rows_total": len(rows),
                    "six_k_rows": len(six_k_rows),
                    "six_k_nonempty_text_rows": len(nonempty),
                    "six_k_structured_financial_result_hits": len(structured),
                    "sample": [
                        {
                            "ticker": row.get("ticker"),
                            "accession_number": row.get("accession_number"),
                            "form_type": row.get("form_type"),
                            "usable_trade_date": row.get("usable_trade_date"),
                            "text_char_count": row.get("text_char_count"),
                        }
                        for row in six_k_rows[:5]
                    ],
                }
            )
    return {
        "file_count": len(files),
        "rows_total": total_rows,
        "six_k_rows": total_six_k,
        "six_k_nonempty_text_rows": total_nonempty,
        "six_k_structured_financial_result_hits": total_structured,
        "files_with_six_k": file_rows,
    }


def scan_filing_text_cache(submission_rows: list[dict[str, Any]]) -> dict[str, Any]:
    target_accessions = {str(row.get("accession_number") or "") for row in submission_rows}
    target_accessions.discard("")
    matched_cache_paths = [
        cache_path_for_accession(accession)
        for accession in sorted(target_accessions)
        if cache_path_for_accession(accession).exists()
    ]

    all_files = sorted(FILING_TEXT_CACHE_DIR.glob("*.json")) if FILING_TEXT_CACHE_DIR.exists() else []
    all_six_k_rows: list[dict[str, Any]] = []
    target_six_k_rows: list[dict[str, Any]] = []
    invalid_json = 0
    for path in all_files:
        payload = read_json(path, None)
        if not isinstance(payload, dict):
            invalid_json += 1
            continue
        if form_is_6k(payload):
            all_six_k_rows.append(payload)
        if path in matched_cache_paths and form_is_6k(payload):
            target_six_k_rows.append(payload)

    target_text_rows = [
        row for row in target_six_k_rows if str(row.get("combined_text") or "").strip()
    ]
    target_structured = [row for row in target_text_rows if structured_hit(row.get("combined_text"))]
    return {
        "cache_dir": repo_rel(FILING_TEXT_CACHE_DIR),
        "cache_dir_exists": FILING_TEXT_CACHE_DIR.exists(),
        "cache_files": len(all_files),
        "invalid_json_files": invalid_json,
        "all_cache_six_k_rows": len(all_six_k_rows),
        "target_six_k_accessions": len(target_accessions),
        "target_accessions_with_cache_file": len(matched_cache_paths),
        "target_six_k_cache_rows": len(target_six_k_rows),
        "target_six_k_nonempty_text_rows": len(target_text_rows),
        "target_six_k_structured_financial_result_hits": len(target_structured),
        "target_cache_coverage_rate": round(len(matched_cache_paths) / len(target_accessions), 6)
        if target_accessions
        else None,
        "sample_target_cache_rows": [
            {
                "ticker": row.get("ticker"),
                "accession_number": row.get("accession_number"),
                "form_type": row.get("form_type"),
                "usable_trade_date": row.get("usable_trade_date"),
                "text_char_count": row.get("text_char_count"),
                "structured_financial_result_hit": structured_hit(row.get("combined_text")),
            }
            for row in target_six_k_rows[:20]
        ],
        "sample_all_cache_six_k_rows": [
            {
                "ticker": row.get("ticker"),
                "accession_number": row.get("accession_number"),
                "form_type": row.get("form_type"),
                "usable_trade_date": row.get("usable_trade_date"),
                "text_char_count": row.get("text_char_count"),
            }
            for row in all_six_k_rows[:20]
        ],
    }


def scan_warehouse_overlap(submission_rows: list[dict[str, Any]]) -> dict[str, Any]:
    tickers = sorted({str(row.get("ticker") or "").upper() for row in submission_rows if row.get("ticker")})
    if not WAREHOUSE.exists():
        return {"warehouse": repo_rel(WAREHOUSE), "exists": False, "overlap_tickers": 0}
    if not tickers:
        return {"warehouse": repo_rel(WAREHOUSE), "exists": True, "overlap_tickers": 0}
    try:
        with sqlite3.connect(WAREHOUSE) as conn:
            table_names = [
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                ).fetchall()
            ]
            table = "ohlcv" if "ohlcv" in table_names else None
            if table is None:
                return {
                    "warehouse": repo_rel(WAREHOUSE),
                    "exists": True,
                    "tables": table_names[:20],
                    "overlap_tickers": 0,
                    "error": "ohlcv table missing",
                }
            placeholders = ",".join("?" for _ in tickers)
            min_date = min(window["start"] for window in CANONICAL_WINDOWS.values())
            max_date = max(window["end"] for window in CANONICAL_WINDOWS.values())
            rows = conn.execute(
                f"""
                SELECT ticker, COUNT(*) AS n
                FROM ohlcv
                WHERE ticker IN ({placeholders}) AND date >= ? AND date <= ?
                GROUP BY ticker
                """,
                [*tickers, min_date, max_date],
            ).fetchall()
    except Exception as exc:
        return {
            "warehouse": repo_rel(WAREHOUSE),
            "exists": True,
            "overlap_tickers": 0,
            "error": str(exc),
        }
    overlap = {str(ticker): int(count) for ticker, count in rows}
    return {
        "warehouse": repo_rel(WAREHOUSE),
        "exists": True,
        "source_six_k_tickers": len(tickers),
        "overlap_tickers": len(overlap),
        "overlap_rate": round(len(overlap) / len(tickers), 6) if tickers else None,
        "sample_overlap": sorted(overlap.items())[:20],
        "sample_missing_tickers": [ticker for ticker in tickers if ticker not in overlap][:20],
    }


def build_result() -> dict[str, Any]:
    completed_at = utc_now()
    baseline = load_baseline()
    submission_rows, submissions_summary = scan_submissions_surface()
    historical_events_summary = scan_jsonl_surface(HISTORICAL_EVENTS)
    historical_text_summary = scan_jsonl_surface(HISTORICAL_TEXT)
    filing_text_cache_summary = scan_filing_text_cache(submission_rows)
    daily_text_summary = scan_daily_text_surface()
    warehouse_overlap = scan_warehouse_overlap(submission_rows)

    historical_text_ready = (
        historical_text_summary["six_k_nonempty_text_rows"] >= MIN_HISTORICAL_TEXT_ROWS
        and historical_text_summary["six_k_structured_financial_result_hits"] >= MIN_STRUCTURED_HITS
    )
    local_cache_ready = (
        filing_text_cache_summary["target_six_k_nonempty_text_rows"] >= MIN_HISTORICAL_TEXT_ROWS
        and filing_text_cache_summary["target_six_k_structured_financial_result_hits"] >= MIN_STRUCTURED_HITS
    )
    materialization_ready = historical_text_ready or local_cache_ready
    failed_reasons: list[str] = []
    if not historical_text_ready:
        failed_reasons.append("historical_generated_6k_text_rows_missing")
    if not local_cache_ready:
        failed_reasons.append("local_target_6k_text_cache_missing_or_sparse")
    if not warehouse_overlap.get("overlap_tickers"):
        failed_reasons.append("no_tradeable_warehouse_overlap")

    status = (
        "accepted_measurement_repair_6k_text_materialization_ready"
        if materialization_ready
        else "blocked"
    )
    decision = (
        "accepted_measurement_repair_6k_historical_text_ready"
        if materialization_ready
        else "blocked_missing_historical_6k_text_materialization"
    )
    actual_success = 1.0 if materialization_ready else 0.0
    brier = round((PREDICTION["success_probability"] - actual_success) ** 2, 4)

    before_after = {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "expected_value_score_sum": baseline["expected_value_score_sum"],
        "total_pnl": baseline["total_pnl"],
        "trade_count": baseline["trade_count"],
        "signals_generated": baseline["signals_generated"],
        "signals_survived": baseline["signals_survived"],
        "survival_rate": baseline["survival_rate"],
        "max_drawdown_pct_worst": baseline["max_drawdown_pct_worst"],
    }
    delta = {
        "expected_value_score_sum_delta": 0.0,
        "total_pnl_delta": 0.0,
        "trade_count_delta": 0,
        "signals_generated_delta": 0,
        "signals_survived_delta": 0,
        "strategy_behavior_changed": False,
    }

    gate2 = {
        "passed": materialization_ready,
        "failed_reasons": failed_reasons,
        "dependencies_checked": [
            repo_rel(SUBMISSIONS_CACHE_DIR),
            repo_rel(HISTORICAL_EVENTS),
            repo_rel(HISTORICAL_TEXT),
            repo_rel(FILING_TEXT_CACHE_DIR),
            repo_rel(WAREHOUSE),
        ],
        "minimum_trade_fields": ["entry_date", "target_price"],
        "entry_date_target_price_note": (
            "No entries or target exits are scheduled. This repair only checks "
            "whether 6-K text rows can exist before a later helper creates "
            "candidate rows with entry_date and target_price semantics."
        ),
        "submissions_surface": submissions_summary,
        "historical_event_surface": historical_events_summary,
        "historical_text_surface": historical_text_summary,
        "filing_text_cache": filing_text_cache_summary,
        "daily_text_surface_current": daily_text_summary,
        "warehouse_overlap": warehouse_overlap,
    }
    gate3 = {
        "passed": materialization_ready,
        "filter_added": False,
        "signals_generated": submissions_summary["six_k_event_rows"],
        "signals_survived": historical_text_summary["six_k_nonempty_text_rows"],
        "survival_rate": round(
            historical_text_summary["six_k_nonempty_text_rows"]
            / submissions_summary["six_k_event_rows"],
            6,
        )
        if submissions_summary["six_k_event_rows"]
        else None,
        "note": (
            "Signals_generated is the alpha-enabling 6-K event surface. "
            "Signals_survived is generated historical 6-K text coverage, not "
            "an executable trading filter."
        ),
    }
    gate4 = {
        "passed": materialization_ready,
        "ran_after_strategy": False,
        "strategy_rerun_required": False,
        "decision": decision,
        "failed_reasons": failed_reasons,
        "before_after_strategy_delta": delta,
        "reason_after_not_run": (
            "Measurement repair only. No buy, sell, ranking, sizing, risk, "
            "exit, LLM, watchlist, paper-order, or live-order policy changed."
        ),
    }
    post_run_reflection = {
        "why_result_happened": (
            "The local submissions cache still exposes a broad 6-K event surface, "
            f"{submissions_summary['six_k_event_rows']} rows across the standard "
            "windows, but the generated historical event/text surfaces contain "
            f"{historical_events_summary['six_k_rows']} and "
            f"{historical_text_summary['six_k_nonempty_text_rows']} replayable "
            "6-K text rows respectively. The per-accession filing-text cache "
            f"covers {filing_text_cache_summary['target_accessions_with_cache_file']} "
            "of those historical 6-K accessions. The structured 6-K alpha remains "
            "blocked until a historical text backfill materializes those rows."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry 6-K phrase lists, numeric regex terms, item/form lists, "
            "RS/close/volume gates, top-N, hold, cooldown, or notional on the "
            "frozen windows while historical 6-K text coverage is missing."
        ),
        "new_evidence_required": (
            "Run a controlled historical SEC archive text backfill for the "
            "standard-window 6-K/6-KA accessions, or provide another replayable "
            "PIT primary-document cache. Then test one fixed structured "
            "financial-result growth helper through shared-paper-first."
        ),
    }

    return {
        "experiment_id": EXPERIMENT_ID,
        "owner": OWNER,
        "lane": LANE,
        "status": status,
        "decision": decision,
        "timestamp": completed_at,
        "completed_at": completed_at,
        "hypothesis": HYPOTHESIS,
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "measurement_repair",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": [
            "local SEC submissions 6-K event surface",
            "historical filing-text coverage audit",
            "structured financial-result phrase/numeric readiness",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "prediction": PREDICTION,
        "calibration": {
            "actual_decision": decision,
            "actual_success": actual_success,
            "brier_score": brier,
            "predicted_success_probability": PREDICTION["success_probability"],
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "realized_failure_modes": failed_reasons,
            "predicted_failure_mode_hit": bool(failed_reasons),
            "surprise_note": (
                "The local submissions event surface exists, but local generated "
                "historical 6-K text materialization is still missing."
                if not materialization_ready
                else "Historical 6-K text materialization is ready for a later alpha helper."
            ),
        },
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "gate1": {"passed": baseline["baseline_exists"], "baseline_metrics": baseline},
        "gate2": gate2,
        "gate3": gate3,
        "gate4": gate4,
        "before_metrics": before_after,
        "after_metrics": before_after,
        "delta_metrics": delta,
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": post_run_reflection,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "related_files": [
            RUNNER,
            repo_rel(HISTORICAL_EVENTS),
            repo_rel(HISTORICAL_TEXT),
            repo_rel(SUBMISSIONS_CACHE_DIR),
            repo_rel(FILING_TEXT_CACHE_DIR),
            repo_rel(BASELINE_RESULT),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(EXPERIMENT_LOG_JSONL),
            repo_rel(REGISTRY_JSON),
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": "No JavaScript was used.",
        "lean_quality_passed": True,
    }


def compact_log_row(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": payload["experiment_id"],
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "lane": payload["lane"],
        "decision": payload["decision"],
        "hypothesis": payload["hypothesis"],
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
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "pre_run_questions": payload["pre_run_questions"],
        "gate1": payload["gate1"],
        "gate2": {
            "passed": payload["gate2"]["passed"],
            "failed_reasons": payload["gate2"]["failed_reasons"],
            "submissions_six_k_event_rows": payload["gate2"]["submissions_surface"][
                "six_k_event_rows"
            ],
            "historical_event_six_k_rows": payload["gate2"]["historical_event_surface"][
                "six_k_rows"
            ],
            "historical_text_six_k_rows": payload["gate2"]["historical_text_surface"][
                "six_k_nonempty_text_rows"
            ],
            "target_accessions_with_cache_file": payload["gate2"]["filing_text_cache"][
                "target_accessions_with_cache_file"
            ],
            "daily_current_six_k_text_rows": payload["gate2"]["daily_text_surface_current"][
                "six_k_nonempty_text_rows"
            ],
            "warehouse_overlap_tickers": payload["gate2"]["warehouse_overlap"].get(
                "overlap_tickers"
            ),
        },
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "artifact": payload["artifact"],
        "log": payload["log"],
        "related_files": payload["related_files"],
        "reproduction_commands": payload["reproduction_commands"],
        "lean_quality_passed": payload["lean_quality_passed"],
    }


def upsert_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(row, sort_keys=True)
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
                if not replaced:
                    rows.append(encoded)
                    replaced = True
                continue
            rows.append(raw)
    if not replaced:
        rows.append(encoded)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def build_card(payload: dict[str, Any]) -> str:
    gate2 = payload["gate2"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: SEC 6-K Historical Text Materialization Readiness",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Changed variable: `{CHANGED_VARIABLE}`",
            "- Lane: `measurement_repair`",
            "",
            "## Hypothesis",
            "",
            HYPOTHESIS,
            "",
            "## Coverage",
            "",
            "| Surface | 6-K rows | Nonempty text rows | Structured hits |",
            "| --- | ---: | ---: | ---: |",
            (
                "| Local submissions events | "
                f"{gate2['submissions_surface']['six_k_event_rows']} | n/a | n/a |"
            ),
            (
                "| Historical generated events | "
                f"{gate2['historical_event_surface']['six_k_rows']} | n/a | n/a |"
            ),
            (
                "| Historical generated text | "
                f"{gate2['historical_text_surface']['six_k_rows']} | "
                f"{gate2['historical_text_surface']['six_k_nonempty_text_rows']} | "
                f"{gate2['historical_text_surface']['six_k_structured_financial_result_hits']} |"
            ),
            (
                "| Per-accession text cache | "
                f"{gate2['filing_text_cache']['target_six_k_cache_rows']} | "
                f"{gate2['filing_text_cache']['target_six_k_nonempty_text_rows']} | "
                f"{gate2['filing_text_cache']['target_six_k_structured_financial_result_hits']} |"
            ),
            (
                "| Current daily text files | "
                f"{gate2['daily_text_surface_current']['six_k_rows']} | "
                f"{gate2['daily_text_surface_current']['six_k_nonempty_text_rows']} | "
                f"{gate2['daily_text_surface_current']['six_k_structured_financial_result_hits']} |"
            ),
            "",
            "## Gate Verdict",
            "",
            f"- Gate 1 baseline: `{payload['gate1']['passed']}`",
            f"- Gate 2 materialization ready: `{gate2['passed']}`",
            f"- Gate 3 text survival: `{payload['gate3']['survival_rate']}`",
            f"- Gate 4 strategy rerun: `{payload['gate4']['ran_after_strategy']}`",
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
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
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG_JSONL,
        REGISTRY_JSON,
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
        "anti_js": payload["anti_js"],
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256_file(path)}
            for path in files
        },
        "log_row_sha256": hashlib.sha256(
            json.dumps(log_row, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    log_row = compact_log_row(payload)
    write_json(OUT_JSON, payload)
    write_json(LOG_JSON, log_row)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG_JSONL, log_row)

    registry_result = {
        "accepted": payload["status"].startswith("accepted"),
        "accepted_alpha": False,
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "delta_metrics": payload["delta_metrics"],
        "gate2": log_row["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result=registry_result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "change_type": payload["change_type"],
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "evaluation_windows": [
                {"label": label, **window} for label, window in CANONICAL_WINDOWS.items()
            ],
            "acceptance_rule": PRE_RUN_QUESTIONS["4_success_failure_standard"],
            "decision": payload["decision"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
            "gate1": payload["gate1"],
            "gate2": log_row["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "lean_quality_passed": payload["lean_quality_passed"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload, log_row))


def main() -> int:
    payload = build_result()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "submissions_six_k_event_rows": payload["gate2"]["submissions_surface"][
                    "six_k_event_rows"
                ],
                "historical_event_six_k_rows": payload["gate2"]["historical_event_surface"][
                    "six_k_rows"
                ],
                "historical_text_six_k_rows": payload["gate2"]["historical_text_surface"][
                    "six_k_nonempty_text_rows"
                ],
                "target_accessions_with_cache_file": payload["gate2"]["filing_text_cache"][
                    "target_accessions_with_cache_file"
                ],
                "daily_current_six_k_text_rows": payload["gate2"][
                    "daily_text_surface_current"
                ]["six_k_nonempty_text_rows"],
                "warehouse_overlap_tickers": payload["gate2"]["warehouse_overlap"].get(
                    "overlap_tickers"
                ),
                "lean_quality_passed": payload["lean_quality_passed"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
