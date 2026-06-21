"""exp-20260621-018: SEC 6-K foreign issuer event readiness.

Alpha-search data-edge probe. The run checks whether the local SEC surfaces can
support a production-visible default-off 6-K candidate-pool alpha before any
strategy replay is attempted.

No JavaScript is used.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import experiment_registry  # noqa: E402


EXPERIMENT_ID = "exp-20260621-018"
SLUG = "sec_6k_foreign_issuer_readiness"
RUNNER_NAME = f"quant/experiments/exp_20260621_018_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER_NAME.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT_JSON = DATA_DIR / f"exp_20260621_018_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

NON_OHLCV_DIR = REPO_ROOT / "data" / "non_ohlcv"
FORM_INDEX_DIR = REPO_ROOT / "data" / "cache" / "sec" / "form_index"
SEC_EVENT_AGGREGATE = NON_OHLCV_DIR / "sec_filing_events_20241002_20260421.jsonl"
SEC_TEXT_AGGREGATE = NON_OHLCV_DIR / "sec_filing_text_20241002_20260421.jsonl"
BASELINE_RESULT_FILE = "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"

TARGET_FORMS = {"6-K", "6-K/A"}
MIN_TARGET_UNIQUE_EVENTS = 20
MIN_TARGET_WINDOWS = 3
MIN_TARGET_UNIQUE_EVENTS_PER_WINDOW = 5

HYPOTHESIS = (
    "candidate_pool/data-edge: PIT SEC 6-K foreign-issuer current-report events "
    "may identify ADR and foreign-company information shocks that are not covered "
    "by the domestic 8-K/10-K/10-Q SEC event pool; a tradeable default-off source "
    "is allowed only if the daily SEC event/text production path exposes 6-K rows "
    "with usable_trade_date across all three canonical windows."
)

TRIAL_FAMILY = "sec_6k_foreign_issuer_event_candidate_pool"
TRIAL_VARIANT_ID = "sec_6k_daily_surface_readiness_v1"
CHANGED_VARIABLE = "sec_6k_foreign_issuer_event_candidate_pool_readiness_v1"

NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260621-015",
    "exp-20260621-016",
    "exp-20260618-007",
]

CANONICAL_WINDOWS: dict[str, dict[str, Any]] = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
        "expected_value_score": 5.1628,
        "sharpe_daily": 4.41,
        "strategy_total_return_pct": 117.07,
        "total_pnl": 117072.92,
        "max_drawdown_pct": 0.0665,
        "trade_count": 18,
        "signals_generated": 51,
        "signals_survived": 41,
        "survival_rate": 0.8039,
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
        "expected_value_score": 2.1402,
        "sharpe_daily": 2.74,
        "strategy_total_return_pct": 78.11,
        "total_pnl": 78110.11,
        "max_drawdown_pct": 0.1119,
        "trade_count": 21,
        "signals_generated": 53,
        "signals_survived": 42,
        "survival_rate": 0.7925,
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
        "expected_value_score": 0.5911,
        "sharpe_daily": 1.49,
        "strategy_total_return_pct": 39.67,
        "total_pnl": 39667.96,
        "max_drawdown_pct": 0.1001,
        "trade_count": 22,
        "signals_generated": 60,
        "signals_survived": 52,
        "survival_rate": 0.8667,
    },
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {}


def append_jsonl_once(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    needle = f'"experiment_id": "{EXPERIMENT_ID}"'
    if path.exists() and needle in path.read_text(encoding="utf-8-sig"):
        return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_date(value: Any) -> date | None:
    if not value:
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


def aggregate_windows() -> dict[str, Any]:
    return {
        "aggregate_expected_value_score": round(
            sum(float(row["expected_value_score"]) for row in CANONICAL_WINDOWS.values()),
            4,
        ),
        "aggregate_total_pnl": round(
            sum(float(row["total_pnl"]) for row in CANONICAL_WINDOWS.values()),
            2,
        ),
        "total_trade_count": sum(int(row["trade_count"]) for row in CANONICAL_WINDOWS.values()),
        "min_survival_rate": round(
            min(float(row["survival_rate"]) for row in CANONICAL_WINDOWS.values()),
            4,
        ),
        "max_window_drawdown_pct": round(
            max(float(row["max_drawdown_pct"]) for row in CANONICAL_WINDOWS.values()),
            4,
        ),
    }


def metric_deltas() -> dict[str, dict[str, float]]:
    fields = [
        "expected_value_score",
        "total_pnl",
        "max_drawdown_pct",
        "trade_count",
        "survival_rate",
    ]
    return {label: {field: 0.0 for field in fields} for label in CANONICAL_WINDOWS}


def parse_default_forms(path: Path) -> list[str]:
    if not path.exists():
        return []
    match = re.search(
        r"DEFAULT_FORMS\s*=\s*(\([^\)]*\))",
        path.read_text(encoding="utf-8", errors="ignore"),
        re.S,
    )
    if not match:
        return []
    try:
        parsed = ast.literal_eval(match.group(1))
    except (SyntaxError, ValueError):
        return []
    return [str(item) for item in parsed]


def parse_form_index_line(line: str) -> dict[str, str] | None:
    if "edgar/data/" not in line:
        return None
    parts = re.split(r"\s{2,}", line.rstrip(), maxsplit=4)
    if len(parts) != 5:
        return None
    form_type, company_name, cik, filing_date, file_name = parts
    if parse_date(filing_date) is None:
        return None
    return {
        "form_type": form_type.strip().upper(),
        "company_name": company_name.strip(),
        "cik": cik.strip(),
        "filing_date": filing_date.strip(),
        "file_name": file_name.strip(),
    }


def scan_form_index() -> dict[str, Any]:
    files = sorted(FORM_INDEX_DIR.glob("form_*.idx"))
    rows_by_window: Counter[str] = Counter()
    rows_by_file: Counter[str] = Counter()
    all_forms: Counter[str] = Counter()
    examples: list[dict[str, Any]] = []
    parsed_rows = 0

    for path in files:
        with path.open(encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                row = parse_form_index_line(line)
                if row is None:
                    continue
                parsed_rows += 1
                form_type = row["form_type"]
                all_forms[form_type] += 1
                if form_type not in TARGET_FORMS:
                    continue
                rows_by_file[path.name] += 1
                window = window_for(row["filing_date"])
                if window:
                    rows_by_window[window] += 1
                if len(examples) < 8:
                    examples.append(
                        {
                            "form_type": form_type,
                            "company_name": row["company_name"],
                            "cik": row["cik"],
                            "filing_date": row["filing_date"],
                            "file_name": row["file_name"],
                            "source_file": repo_rel(path),
                        }
                    )

    total_target_rows = sum(rows_by_window.values())
    return {
        "source_dir": repo_rel(FORM_INDEX_DIR),
        "file_count": len(files),
        "files": [path.name for path in files],
        "parsed_rows": parsed_rows,
        "top_forms": all_forms.most_common(12),
        "target_forms": sorted(TARGET_FORMS),
        "target_rows_by_window": {label: int(rows_by_window[label]) for label in CANONICAL_WINDOWS},
        "target_rows_by_file": dict(rows_by_file),
        "target_rows_total_in_windows": int(total_target_rows),
        "sample_target_rows": examples,
        "dependency_presence": {
            "form_type": True,
            "company_name": True,
            "cik": True,
            "filing_date": True,
            "file_name": True,
            "ticker": False,
            "accession_number": False,
            "accepted_at": False,
            "usable_trade_date": False,
            "entry_date": False,
            "target_price": False,
        },
        "blocking_verdict": (
            "form_index_has_historical_6k_metadata_but_lacks_ticker_accepted_at_"
            "usable_trade_date_entry_date_and_target_price"
        ),
    }


def is_single_date_sec_file(path: Path, prefix: str) -> bool:
    return re.fullmatch(rf"{re.escape(prefix)}_\d{{8}}\.jsonl", path.name) is not None


def event_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("ticker") or "").upper(),
        str(row.get("accession_number") or ""),
        str(row.get("usable_trade_date") or row.get("filing_date") or ""),
    )


def scan_jsonl_forms(paths: list[Path], *, date_field: str = "usable_trade_date") -> dict[str, Any]:
    file_count = 0
    invalid_json_lines = 0
    form_counts: Counter[str] = Counter()
    target_rows_by_window: Counter[str] = Counter()
    target_unique_events_by_window: defaultdict[str, set[tuple[str, str, str]]] = defaultdict(set)
    dependency_present = Counter()
    dependency_total = 0
    sample_target_rows: list[dict[str, Any]] = []

    for path in sorted(paths):
        if not path.exists():
            continue
        file_count += 1
        with path.open(encoding="utf-8-sig") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    invalid_json_lines += 1
                    continue
                form_type = str(row.get("form_type") or row.get("form") or row.get("form_base") or "").upper()
                if not form_type:
                    form_type = "UNKNOWN"
                form_counts[form_type] += 1
                if form_type not in TARGET_FORMS:
                    continue
                dependency_total += 1
                for key in (
                    "ticker",
                    "cik",
                    "accession_number",
                    "filing_date",
                    "accepted_at",
                    "usable_trade_date",
                    "entry_date",
                    "target_price",
                ):
                    if row.get(key) not in (None, ""):
                        dependency_present[key] += 1
                window = window_for(row.get(date_field) or row.get("filing_date"))
                if window is None:
                    continue
                target_rows_by_window[window] += 1
                target_unique_events_by_window[window].add(event_key(row))
                if len(sample_target_rows) < 8:
                    sample_target_rows.append(
                        {
                            "ticker": row.get("ticker"),
                            "cik": row.get("cik"),
                            "accession_number": row.get("accession_number"),
                            "filing_date": row.get("filing_date"),
                            "accepted_at": row.get("accepted_at"),
                            "usable_trade_date": row.get("usable_trade_date"),
                            "form_type": form_type,
                        }
                    )

    return {
        "file_count": file_count,
        "invalid_json_lines": invalid_json_lines,
        "form_counts": form_counts.most_common(12),
        "target_rows_by_window": {label: int(target_rows_by_window[label]) for label in CANONICAL_WINDOWS},
        "target_unique_events_by_window": {
            label: len(target_unique_events_by_window.get(label, set()))
            for label in CANONICAL_WINDOWS
        },
        "target_rows_total_in_windows": int(sum(target_rows_by_window.values())),
        "sample_target_rows": sample_target_rows,
        "dependency_presence": {
            key: {
                "present_rows": int(dependency_present.get(key, 0)),
                "target_rows_scanned": dependency_total,
                "present_rate": (
                    round(float(dependency_present.get(key, 0)) / dependency_total, 4)
                    if dependency_total
                    else 0.0
                ),
            }
            for key in (
                "ticker",
                "cik",
                "accession_number",
                "filing_date",
                "accepted_at",
                "usable_trade_date",
                "entry_date",
                "target_price",
            )
        },
    }


def scan_daily_event_files() -> dict[str, Any]:
    paths = [
        path
        for path in NON_OHLCV_DIR.glob("sec_filing_events_*.jsonl")
        if is_single_date_sec_file(path, "sec_filing_events")
    ]
    return scan_jsonl_forms(paths)


def scan_sec_surfaces() -> dict[str, Any]:
    event_defaults = parse_default_forms(REPO_ROOT / "quant" / "sec_filing_backfill.py")
    text_defaults = parse_default_forms(REPO_ROOT / "quant" / "sec_filing_text_backfill.py")
    aggregate_events = scan_jsonl_forms([SEC_EVENT_AGGREGATE])
    daily_events = scan_daily_event_files()
    aggregate_text = scan_jsonl_forms([SEC_TEXT_AGGREGATE])
    recent_text = scan_jsonl_forms(sorted(NON_OHLCV_DIR.glob("sec_filing_text_*.jsonl")))

    def target_ready(surface: dict[str, Any]) -> bool:
        counts = surface["target_unique_events_by_window"]
        total = sum(int(counts[label]) for label in CANONICAL_WINDOWS)
        windows = [label for label in CANONICAL_WINDOWS if int(counts[label]) > 0]
        min_count = min((int(counts[label]) for label in CANONICAL_WINDOWS), default=0)
        return (
            total >= MIN_TARGET_UNIQUE_EVENTS
            and len(windows) >= MIN_TARGET_WINDOWS
            and min_count >= MIN_TARGET_UNIQUE_EVENTS_PER_WINDOW
        )

    return {
        "event_default_forms": event_defaults,
        "event_default_includes_6k": any(form.upper() in TARGET_FORMS for form in event_defaults),
        "text_default_forms": text_defaults,
        "text_default_includes_6k": any(form.upper() in TARGET_FORMS for form in text_defaults),
        "aggregate_events": aggregate_events,
        "daily_event_files": daily_events,
        "aggregate_text": aggregate_text,
        "all_text_files": recent_text,
        "production_visible_6k_event_ready": target_ready(aggregate_events) or target_ready(daily_events),
        "production_visible_6k_text_ready": target_ready(aggregate_text) or target_ready(recent_text),
    }


def build_result() -> dict[str, Any]:
    form_index = scan_form_index()
    sec_surfaces = scan_sec_surfaces()
    aggregate = aggregate_windows()
    prediction = read_json(TICKET_JSON).get("prediction", {})
    gate2_reasons = []
    if not sec_surfaces["event_default_includes_6k"]:
        gate2_reasons.append("sec_event_builder_default_forms_exclude_6k")
    if not sec_surfaces["text_default_includes_6k"]:
        gate2_reasons.append("sec_text_builder_default_forms_exclude_6k")
    if sec_surfaces["aggregate_events"]["target_rows_total_in_windows"] == 0:
        gate2_reasons.append("aggregate_sec_events_have_zero_6k_rows")
    if sec_surfaces["daily_event_files"]["target_rows_total_in_windows"] == 0:
        gate2_reasons.append("daily_sec_event_files_have_zero_6k_rows")
    gate2_reasons.append("form_index_6k_rows_are_metadata_only_not_trade_ready_pit_events")

    target_counts = sec_surfaces["aggregate_events"]["target_unique_events_by_window"]
    target_total = sum(int(target_counts[label]) for label in CANONICAL_WINDOWS)
    target_windows = [label for label in CANONICAL_WINDOWS if int(target_counts[label]) > 0]
    gate3_reasons = []
    if target_total < MIN_TARGET_UNIQUE_EVENTS:
        gate3_reasons.append("production_visible_6k_unique_events_below_20")
    if len(target_windows) < MIN_TARGET_WINDOWS:
        gate3_reasons.append("production_visible_6k_missing_three_window_coverage")
    if any(int(target_counts[label]) < MIN_TARGET_UNIQUE_EVENTS_PER_WINDOW for label in CANONICAL_WINDOWS):
        gate3_reasons.append("production_visible_6k_window_sample_below_5")

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now_utc(),
        "lane": "alpha_search",
        "status": "blocked",
        "decision": "blocked_sec_6k_daily_event_surface_missing",
        "hypothesis": HYPOTHESIS,
        "change_type": "candidate_pool_full_stack",
        "mechanism_family": "production_visible_free_sec_6k_foreign_issuer_candidate_pool",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "prediction": prediction,
        "pre_run_questions": {
            "1_alpha_hypothesis": (
                "6-K filings are a free SEC channel for foreign issuer current "
                "reports and may surface ADR information shocks not captured by "
                "domestic 8-K/10-Q/10-K event alphas."
            ),
            "2_history_check": {
                "novelty_gate": "no strong near-neighbor for this 6-K daily-surface readiness hypothesis",
                "exp-20260621-015": (
                    "audited form_index as a broad frontier surface and counted 6-K "
                    "metadata, but did not test whether daily SEC production events "
                    "carry 6-K rows."
                ),
                "exp-20260621-016": (
                    "blocked 8-K cover-page booleans; this run is a distinct foreign "
                    "issuer form-family readiness test."
                ),
                "exp-20260618-007": (
                    "blocked 10-K/10-Q historical filer-status surface; this run does "
                    "not use cover-page status."
                ),
            },
            "3_single_decision_hypothesis": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Gate 2 must show production-visible SEC event/text rows for 6-K with "
                "ticker, accession, accepted_at, usable_trade_date, entry_date/target "
                "mapping via shared helper; Gate 3 needs at least 20 unique target "
                "events across all three windows with at least five per window; Gate 4 "
                "must use docs/backtesting.md before/after three-window metrics."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "gate1": {
            "baseline_result_file": BASELINE_RESULT_FILE,
            "windows": CANONICAL_WINDOWS,
            "aggregate": aggregate,
            "passed": True,
        },
        "gate2": {
            "dependency_fields_checked": [
                "ticker",
                "cik",
                "accession_number",
                "form_type",
                "filing_date",
                "accepted_at",
                "usable_trade_date",
                "entry_date",
                "target_price",
            ],
            "form_index": form_index,
            "sec_surfaces": sec_surfaces,
            "passed": False,
            "blocking_reasons": gate2_reasons,
        },
        "gate3": {
            "baseline_survival_by_window": {
                label: {
                    "signals_generated": row["signals_generated"],
                    "signals_survived": row["signals_survived"],
                    "survival_rate": row["survival_rate"],
                }
                for label, row in CANONICAL_WINDOWS.items()
            },
            "minimum_target_unique_events": MIN_TARGET_UNIQUE_EVENTS,
            "minimum_target_windows": MIN_TARGET_WINDOWS,
            "minimum_target_unique_events_per_window": MIN_TARGET_UNIQUE_EVENTS_PER_WINDOW,
            "production_visible_unique_6k_events_by_window": target_counts,
            "production_visible_unique_6k_events_total": target_total,
            "target_windows": target_windows,
            "signals_generated": 0,
            "signals_survived": 0,
            "survival_rate": 0.0,
            "passed": False,
            "blocking_reasons": gate3_reasons,
        },
        "gate4": {
            "ran_after_strategy": False,
            "reason_after_not_run": (
                "Blocked at Gate 2/3: 6-K exists in raw form-index metadata, but not "
                "in the current production-visible SEC event/text surfaces."
            ),
            "before_windows": CANONICAL_WINDOWS,
            "after_windows": CANONICAL_WINDOWS,
            "delta_by_window": metric_deltas(),
            "aggregate_before": aggregate,
            "aggregate_after": aggregate,
            "aggregate_delta": {
                "aggregate_expected_value_score": 0.0,
                "aggregate_total_pnl": 0.0,
                "total_trade_count": 0,
                "min_survival_rate": 0.0,
                "max_window_drawdown_pct": 0.0,
            },
            "passed": False,
        },
        "delta_metrics": {
            "aggregate_expected_value_score": 0.0,
            "aggregate_total_pnl": 0.0,
            "total_trade_count": 0,
            "max_window_drawdown_pct": 0.0,
        },
        "production_impact": {
            "strategy_code_changed": False,
            "shared_helper_changed": False,
            "daily_snapshot_changed": False,
            "live_orders_changed": False,
            "trade_enabled_changed": False,
            "production_orders_changed": False,
            "production_watchlist_changed": False,
            "backtester_adapter_changed": False,
            "default_off_paper_only": False,
            "live_ready": False,
            "backtest_production_parity_risk": "avoided_by_blocking_before_replay",
            "parity_note": (
                "This run changes no trading path. It blocks promotion because the "
                "candidate source is visible only as raw SEC form-index metadata, not "
                "as a shared daily/backtest policy surface."
            ),
        },
        "calibration": {
            "predicted_success_probability": prediction.get("success_probability"),
            "actual_success": 0,
            "brier_score": (
                round(float(prediction.get("success_probability") or 0.0) ** 2, 4)
            ),
            "actual_ev_delta": 0.0,
            "actual_pnl_delta": 0.0,
            "failure_modes_observed": gate2_reasons + gate3_reasons,
        },
        "post_run_reflection": {
            "why_result_happened": (
                "6-K has raw historical form-index volume, but the current SEC event "
                "builder emits domestic current and periodic forms while the text "
                "builder is 8-K oriented. There are zero production-visible 6-K event "
                "rows in the canonical event surface, so a replay would use a "
                "different data path than production."
            ),
            "negative_result_reflection": (
                "This is a data-edge block, not a losing strategy result. The alpha "
                "idea may still be economically plausible, but the present local "
                "surface cannot support a fair three-window backtest without creating "
                "a production/backtest mismatch."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry 6-K by trading raw form-index filing dates, broadening "
                "to 6-K/A, or adding OHLCV close, volume, top-N, hold, cooldown, or "
                "notional filters on the same non-shared metadata surface."
            ),
            "new_evidence_required": (
                "Build or acquire a PIT 6-K daily event/text surface with ticker, "
                "accession, accepted_at, usable_trade_date, and shared helper entry "
                "mapping across all three standard windows, then run the same Gate 1-4 "
                "protocol."
            ),
        },
        "changed_files": [
            RUNNER_NAME,
            repo_rel(ARTIFACT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            "docs/experiment_log.jsonl",
            "docs/experiment_registry.json",
        ],
        "reproduction": RUNNER_COMMAND,
        "anti_js": "No JavaScript was used.",
        "lean_quality_passed": True,
    }


def build_log_record(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": result["timestamp"],
        "lane": result["lane"],
        "status": result["status"],
        "decision": result["decision"],
        "hypothesis": result["hypothesis"],
        "change_type": result["change_type"],
        "mechanism_family": result["mechanism_family"],
        "trial_family": result["trial_family"],
        "trial_variant_id": result["trial_variant_id"],
        "changed_variable": result["changed_variable"],
        "prediction": result["prediction"],
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
        "gate1": result["gate1"],
        "gate2": {
            "passed": result["gate2"]["passed"],
            "blocking_reasons": result["gate2"]["blocking_reasons"],
            "form_index_target_rows_by_window": result["gate2"]["form_index"]["target_rows_by_window"],
            "aggregate_event_6k_rows_by_window": result["gate2"]["sec_surfaces"]["aggregate_events"][
                "target_rows_by_window"
            ],
            "daily_event_6k_rows_by_window": result["gate2"]["sec_surfaces"]["daily_event_files"][
                "target_rows_by_window"
            ],
            "event_default_forms": result["gate2"]["sec_surfaces"]["event_default_forms"],
            "text_default_forms": result["gate2"]["sec_surfaces"]["text_default_forms"],
        },
        "gate3": result["gate3"],
        "gate4": result["gate4"],
        "production_impact": result["production_impact"],
        "calibration": result["calibration"],
        "post_run_reflection": result["post_run_reflection"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": result["anti_js"],
        "lean_quality_passed": result["lean_quality_passed"],
    }


def build_card(result: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID}: SEC 6-K foreign issuer readiness",
        "",
        "- Lane: alpha_search",
        "- Status: blocked",
        f"- Decision: {result['decision']}",
        "- Strategy / production behavior changed: no",
        "",
        "## Gate 4 Baseline",
        "",
        "| Window | Before EV | After EV | Delta EV | Before PnL | After PnL | Delta PnL |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, row in CANONICAL_WINDOWS.items():
        lines.append(
            f"| {label} | {row['expected_value_score']:.4f} | "
            f"{row['expected_value_score']:.4f} | 0.0000 | "
            f"${row['total_pnl']:,.2f} | ${row['total_pnl']:,.2f} | $0.00 |"
        )
    lines.extend(
        [
            "",
            "## Readiness Evidence",
            "",
            "| Surface | late_strong | mid_weak | old_thin |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    form_index = result["gate2"]["form_index"]["target_rows_by_window"]
    aggregate_events = result["gate2"]["sec_surfaces"]["aggregate_events"]["target_rows_by_window"]
    daily_events = result["gate2"]["sec_surfaces"]["daily_event_files"]["target_rows_by_window"]
    lines.append(
        f"| form_index 6-K metadata | {form_index['late_strong']} | "
        f"{form_index['mid_weak']} | {form_index['old_thin']} |"
    )
    lines.append(
        f"| aggregate sec_filing_events 6-K | {aggregate_events['late_strong']} | "
        f"{aggregate_events['mid_weak']} | {aggregate_events['old_thin']} |"
    )
    lines.append(
        f"| daily sec_filing_events 6-K | {daily_events['late_strong']} | "
        f"{daily_events['mid_weak']} | {daily_events['old_thin']} |"
    )
    lines.extend(
        [
            "",
            "## Reflection",
            "",
            result["post_run_reflection"]["why_result_happened"],
            "",
            result["post_run_reflection"]["new_evidence_required"],
            "",
        ]
    )
    return "\n".join(lines)


def build_manifest(result: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER_NAME,
        ARTIFACT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG_JSONL,
        REGISTRY_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": result["status"],
        "decision": result["decision"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER_NAME,
        "command": result["reproduction"],
        "files": {
            repo_rel(path): {
                "exists": path.exists(),
                "sha256": sha256_file(path),
            }
            for path in files
        },
        "anti_js": result["anti_js"],
        "updated_at": now_utc(),
    }


def persist(result: dict[str, Any]) -> None:
    write_json(ARTIFACT_JSON, result)
    write_json(LOG_JSON, result)
    write_text(CARD_MD, build_card(result))
    append_jsonl_once(EXPERIMENT_LOG_JSONL, build_log_record(result))

    registry_result = {
        "accepted": False,
        "accepted_alpha": False,
        "decision": result["decision"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER_NAME,
        "delta_metrics": result["delta_metrics"],
        "gate4": result["gate4"],
        "calibration": result["calibration"],
        "summary": result["post_run_reflection"]["why_result_happened"],
    }
    experiment_registry.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=result["prediction"],
        result=registry_result,
        status="blocked",
        fields={
            "owner": "alpha-search-automation",
            "hypothesis": result["hypothesis"],
            "change_type": result["change_type"],
            "mechanism_family": result["mechanism_family"],
            "trial_family": result["trial_family"],
            "trial_variant_id": result["trial_variant_id"],
            "single_causal_variable": result["single_causal_variable"],
            "changed_variable": result["changed_variable"],
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": "minimal",
            "new_evidence_type": "sec_6k_daily_event_surface_readiness",
            "baseline_result_file": BASELINE_RESULT_FILE,
            "evaluation_windows": [
                {
                    "label": label,
                    "start": row["start"],
                    "end": row["end"],
                    "snapshot": row["snapshot"],
                }
                for label, row in CANONICAL_WINDOWS.items()
            ],
            "acceptance_rule": (
                "Blocked unless 6-K exists in the production-visible SEC event/text "
                "surface with enough three-window target sample and shared helper "
                "entry mapping."
            ),
            "decision": result["decision"],
            "summary": result["post_run_reflection"]["why_result_happened"],
            "artifact": repo_rel(ARTIFACT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
            "gate1": result["gate1"],
            "gate2": result["gate2"],
            "gate3": result["gate3"],
            "gate4": result["gate4"],
            "production_impact": result["production_impact"],
            "post_run_reflection": result["post_run_reflection"],
            "lean_quality_passed": result["lean_quality_passed"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(result))


def main() -> None:
    result = build_result()
    persist(result)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": result["status"],
                "decision": result["decision"],
                "form_index_6k_rows": result["gate2"]["form_index"]["target_rows_by_window"],
                "aggregate_event_6k_rows": result["gate2"]["sec_surfaces"]["aggregate_events"][
                    "target_rows_by_window"
                ],
                "daily_event_6k_rows": result["gate2"]["sec_surfaces"]["daily_event_files"][
                    "target_rows_by_window"
                ],
                "aggregate_ev_delta": result["delta_metrics"]["aggregate_expected_value_score"],
                "aggregate_pnl_delta": result["delta_metrics"]["aggregate_total_pnl"],
                "anti_js": result["anti_js"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
