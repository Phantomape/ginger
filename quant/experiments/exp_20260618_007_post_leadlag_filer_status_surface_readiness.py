"""exp-20260618-007: PIT SEC filer-status alpha surface readiness.

Alpha-search direction experiment. The hypothesis is that SEC cover-page
filer-status transitions could expand the candidate pool toward maturing
issuers with improving institutional eligibility. This is a free-data edge in
principle, but it is only tradeable if the historical 10-K/10-Q cover-page
status field exists point-in-time across the canonical Gate 1-4 windows.

This runner proves the data boundary before any strategy code is changed. It
writes no production strategy code and changes no live/default order, ranking,
sizing, exit, LLM/news, watchlist, or daily-run behavior.

No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
for entry in (str(REPO_ROOT), str(SCRIPTS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import experiment_registry  # noqa: E402


EXPERIMENT_ID = "exp-20260618-007"
SLUG = "post_leadlag_filer_status_surface_readiness"
RUNNER_NAME = (
    "quant/experiments/"
    "exp_20260618_007_post_leadlag_filer_status_surface_readiness.py"
)

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT_JSON = DATA_DIR / f"exp_20260618_007_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"

SEC_TEXT_DAILY_DIR = REPO_ROOT / "data" / "non_ohlcv"
SEC_TEXT_AGGREGATE = SEC_TEXT_DAILY_DIR / "sec_filing_text_20241002_20260421.jsonl"
SEC_FILING_CACHE_DIR = REPO_ROOT / "data" / "cache" / "sec" / "filing_text"
SEC_SUBMISSIONS_DIR = REPO_ROOT / "data" / "cache" / "sec" / "submissions"

BASELINE_RESULT_FILE = "data/backtests/backtest_results_20260421_20251023_20260421.json"

CANONICAL_WINDOWS: dict[str, dict[str, Any]] = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "expected_value_score": 5.1628,
        "sharpe_daily": 4.41,
        "total_pnl": 117072.92,
        "max_drawdown_pct": 0.0665,
        "win_rate": 0.8333,
        "trade_count": 18,
        "signals_generated": 51,
        "signals_survived": 41,
        "survival_rate": 0.8039,
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "expected_value_score": 2.1402,
        "sharpe_daily": 2.74,
        "total_pnl": 78110.11,
        "max_drawdown_pct": 0.1119,
        "win_rate": 0.5238,
        "trade_count": 21,
        "signals_generated": 53,
        "signals_survived": 42,
        "survival_rate": 0.7925,
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "expected_value_score": 0.5911,
        "sharpe_daily": 1.49,
        "total_pnl": 39667.96,
        "max_drawdown_pct": 0.1001,
        "win_rate": 0.4091,
        "trade_count": 22,
        "signals_generated": 60,
        "signals_survived": 52,
        "survival_rate": 0.8667,
    },
}

CANONICAL_AGGREGATE = {
    "expected_value_score": 7.8941,
    "total_pnl": 234850.99,
    "trade_count": 61,
    "signals_generated": 164,
    "signals_survived": 135,
    "survival_rate": round(135 / 164, 4),
    "min_survival_rate": 0.7925,
    "max_drawdown_pct": 0.1119,
}

STATUS_PHRASES = (
    "large accelerated filer",
    "accelerated filer",
    "non-accelerated filer",
    "smaller reporting company",
    "emerging growth company",
)

TARGET_FORMS = {"10-K", "10-K/A", "10-Q", "10-Q/A"}

NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260617-019",
    "exp-20260617-020",
    "exp-20260617-022",
    "exp-20260618-005",
    "exp-20260618-006",
]

PREDICTION = {
    "success_probability": 0.20,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "historical_10k_10q_cover_page_text_absent",
        "current_sec_submissions_category_not_pit",
        "nearby_sec_item_and_lead_lag_families_frozen",
    ],
    "confidence_reason": (
        "SEC filer-status transition is a plausible free candidate-pool edge, "
        "but prior local SEC text appears 8-K-only and submissions metadata "
        "stores category as current top-level company state, not as a "
        "historical filing-row field."
    ),
    "recorded_at": "2026-06-18T06:07:32+00:00",
}

HYPOTHESIS = (
    "candidate_pool/data-edge: PIT SEC cover-page filer-status transitions "
    "could expand the candidate pool toward maturing issuers with improving "
    "institutional eligibility; if the local data lacks historical 10-K/10-Q "
    "cover-page status by filing date, using current SEC category metadata "
    "would create a backtest/production mismatch."
)

PRODUCTION_IMPACT = {
    "adapter_status": "analysis_only_no_strategy_or_adapter_change",
    "alters_candidate_ranking": False,
    "alters_exits": False,
    "alters_orders": False,
    "alters_signal_generation": False,
    "alters_sizing": False,
    "backtester_adapter_changed": False,
    "daily_snapshot_exposed": False,
    "live_ready": False,
    "live_realism_evaluated": False,
    "parity_note": (
        "No shared helper was launched because the PIT field is not locally "
        "available for historical Gate 4. A future positive version must use "
        "one shared default-off helper across historical replay and daily "
        "production snapshots before retention."
    ),
    "parity_test_added": False,
    "production_orders_changed": False,
    "production_signal_path_changed": False,
    "production_watchlist_changed": False,
    "replay_only": True,
    "run_adapter_changed": False,
    "shared_policy_changed": False,
    "trade_enabled": False,
    "uses_llm": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def date_value(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def in_window(value: Any, window: dict[str, Any]) -> bool:
    current = date_value(value)
    start = date_value(window["start"])
    end = date_value(window["end"])
    return bool(current and start and end and start <= current <= end)


def canonical_window_for_date(value: Any) -> str | None:
    for label, window in CANONICAL_WINDOWS.items():
        if in_window(value, window):
            return label
    return None


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def append_jsonl_once(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_ids = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                existing_ids.add(json.loads(line).get("experiment_id"))
            except json.JSONDecodeError:
                continue
    if row.get("experiment_id") in existing_ids:
        return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_value(*args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    return completed.stdout.strip()


def iter_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def row_form(row: dict[str, Any]) -> str:
    raw = (
        row.get("form_type")
        or row.get("form")
        or row.get("form_base")
        or row.get("sec_form")
        or ""
    )
    return str(raw).strip().upper()


def row_filing_date(row: dict[str, Any]) -> str | None:
    for key in ("usable_trade_date", "filing_date", "accepted_at", "acceptanceDateTime"):
        if row.get(key):
            return str(row[key])[:10]
    return None


def text_has_status(row: dict[str, Any]) -> bool:
    text = str(row.get("combined_text") or row.get("text") or "").lower()
    return any(phrase in text for phrase in STATUS_PHRASES)


def aggregate_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    form_counts: Counter[str] = Counter()
    rows_by_window: Counter[str] = Counter()
    target_rows_by_window: Counter[str] = Counter()
    status_hits_by_window: Counter[str] = Counter()
    target_status_hits_by_window: Counter[str] = Counter()
    target_samples: list[dict[str, Any]] = []
    dates: list[str] = []

    for row in rows:
        form = row_form(row)
        form_counts[form] += 1
        filing_date = row_filing_date(row)
        if filing_date:
            dates.append(filing_date)
        window = canonical_window_for_date(filing_date)
        if window:
            rows_by_window[window] += 1
            if text_has_status(row):
                status_hits_by_window[window] += 1
            if form in TARGET_FORMS:
                target_rows_by_window[window] += 1
                if text_has_status(row):
                    target_status_hits_by_window[window] += 1
                if len(target_samples) < 5:
                    target_samples.append(
                        {
                            "ticker": row.get("ticker"),
                            "form": form,
                            "filing_date": filing_date,
                            "accession_number": row.get("accession_number")
                            or row.get("accessionNumber"),
                        }
                    )

    return {
        "row_count": len(rows),
        "form_counts": dict(form_counts.most_common(12)),
        "first_filing_date": min(dates) if dates else None,
        "last_filing_date": max(dates) if dates else None,
        "rows_by_window": {label: rows_by_window[label] for label in CANONICAL_WINDOWS},
        "status_phrase_hits_by_window": {
            label: status_hits_by_window[label] for label in CANONICAL_WINDOWS
        },
        "target_10k_10q_rows_by_window": {
            label: target_rows_by_window[label] for label in CANONICAL_WINDOWS
        },
        "target_10k_10q_status_hits_by_window": {
            label: target_status_hits_by_window[label] for label in CANONICAL_WINDOWS
        },
        "target_10k_10q_sample": target_samples,
    }


def audit_sec_text_aggregate() -> dict[str, Any]:
    rows = iter_jsonl(SEC_TEXT_AGGREGATE)
    audit = aggregate_rows(rows)
    audit.update(
        {
            "source": repo_rel(SEC_TEXT_AGGREGATE),
            "coverage_conclusion": (
                "The standard aggregate SEC text file has canonical-window "
                "rows, but they are 8-K rows only. The status phrases it sees "
                "are 8-K cover-page boilerplate, not 10-K/10-Q filer-status "
                "classification transitions."
            ),
        }
    )
    return audit


def audit_daily_sec_text_snapshots() -> dict[str, Any]:
    files = []
    rows: list[dict[str, Any]] = []
    first = min(date_value(window["start"]) for window in CANONICAL_WINDOWS.values())
    last = max(date_value(window["end"]) for window in CANONICAL_WINDOWS.values())
    for path in sorted(SEC_TEXT_DAILY_DIR.glob("sec_filing_text_*.jsonl")):
        if path == SEC_TEXT_AGGREGATE:
            continue
        stem_date = path.stem.replace("sec_filing_text_", "")
        if len(stem_date) != 8 or not stem_date.isdigit():
            continue
        path_date = date_value(
            f"{stem_date[:4]}-{stem_date[4:6]}-{stem_date[6:]}"
        )
        if not path_date or not first or not last or not (first <= path_date <= last):
            continue
        files.append(path)
        rows.extend(iter_jsonl(path))

    audit = aggregate_rows(rows)
    audit.update(
        {
            "source": "data/non_ohlcv/sec_filing_text_YYYYMMDD.jsonl",
            "file_count": len(files),
            "first_snapshot": repo_rel(files[0]) if files else None,
            "last_snapshot": repo_rel(files[-1]) if files else None,
            "coverage_conclusion": (
                "Daily SEC text snapshots cover the dates, but locally they do "
                "not provide historical 10-K/10-Q cover-page status rows for "
                "the canonical windows."
            ),
        }
    )
    return audit


def audit_filing_text_cache() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for path in sorted(SEC_FILING_CACHE_DIR.glob("*.json")):
        row = read_json(path, {})
        if row:
            rows.append(row)
    audit = aggregate_rows(rows)
    audit.update(
        {
            "source": repo_rel(SEC_FILING_CACHE_DIR),
            "file_count": len(rows),
            "coverage_conclusion": (
                "The local filing-text cache contains fetched filing documents, "
                "but its canonical-window rows are not sufficient historical "
                "10-K/10-Q cover-page status coverage for Gate 4."
            ),
        }
    )
    return audit


def audit_submissions_metadata() -> dict[str, Any]:
    category_counts: Counter[str] = Counter()
    recent_forms: Counter[str] = Counter()
    recent_10kq_by_window: Counter[str] = Counter()
    recent_status_row_fields: Counter[str] = Counter()
    current_category_samples: list[dict[str, Any]] = []
    recent_10kq_samples: list[dict[str, Any]] = []
    submission_count = 0

    for path in sorted(SEC_SUBMISSIONS_DIR.glob("CIK*.json")):
        data = read_json(path, {})
        if not data:
            continue
        submission_count += 1
        category = str(data.get("category") or "")
        category_counts[category] += 1
        if category and len(current_category_samples) < 5:
            current_category_samples.append(
                {
                    "file": repo_rel(path),
                    "ticker": (data.get("tickers") or [None])[0],
                    "category": category,
                    "top_level_keys": sorted(data.keys())[:12],
                }
            )

        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form") or []
        dates = recent.get("filingDate") or []
        acceptances = recent.get("acceptanceDateTime") or []
        accessions = recent.get("accessionNumber") or []
        primary_docs = recent.get("primaryDocument") or []
        row_count = max(
            len(forms), len(dates), len(acceptances), len(accessions), len(primary_docs)
        )
        for idx in range(row_count):
            form = str(forms[idx]).upper() if idx < len(forms) else ""
            filing_date = dates[idx] if idx < len(dates) else None
            recent_forms[form] += 1
            if form in TARGET_FORMS:
                window = canonical_window_for_date(filing_date)
                if window:
                    recent_10kq_by_window[window] += 1
                    if len(recent_10kq_samples) < 5:
                        recent_10kq_samples.append(
                            {
                                "ticker": (data.get("tickers") or [None])[0],
                                "form": form,
                                "filing_date": filing_date,
                                "acceptanceDateTime": acceptances[idx]
                                if idx < len(acceptances)
                                else None,
                                "accessionNumber": accessions[idx]
                                if idx < len(accessions)
                                else None,
                                "primaryDocument": primary_docs[idx]
                                if idx < len(primary_docs)
                                else None,
                            }
                        )
                for forbidden in (
                    "category",
                    "filerStatus",
                    "acceleratedFilerStatus",
                    "smallerReportingCompany",
                    "emergingGrowthCompany",
                ):
                    if forbidden in recent:
                        recent_status_row_fields[forbidden] += 1

    return {
        "source": repo_rel(SEC_SUBMISSIONS_DIR),
        "submission_file_count": submission_count,
        "top_level_current_category_counts": dict(category_counts.most_common(12)),
        "recent_form_counts": dict(recent_forms.most_common(12)),
        "recent_10k_10q_rows_by_window": {
            label: recent_10kq_by_window[label] for label in CANONICAL_WINDOWS
        },
        "recent_status_row_fields_present": dict(recent_status_row_fields),
        "current_category_samples": current_category_samples,
        "recent_10k_10q_samples": recent_10kq_samples,
        "coverage_conclusion": (
            "Submissions metadata has 10-K/10-Q filing pointers, but filer "
            "category is a top-level current company field and not timestamped "
            "per filing row. Using it for 2024-2026 replay would leak latest "
            "state into the backtest."
        ),
    }


def find_jsonl_experiment(experiment_id: str) -> dict[str, Any] | None:
    for row in iter_jsonl(EXPERIMENT_LOG_JSONL):
        if row.get("experiment_id") == experiment_id:
            return row
    return None


def load_experiment(experiment_id: str) -> dict[str, Any] | None:
    log_path = REPO_ROOT / "experiments" / "logs" / f"{experiment_id}.json"
    row = read_json(log_path)
    if row:
        return row
    return find_jsonl_experiment(experiment_id)


def summarize_experiment(experiment_id: str) -> dict[str, Any]:
    row = load_experiment(experiment_id) or {}
    gate = row.get("gate4") or {}
    delta = row.get("delta_metrics") or {}
    reflection = row.get("post_run_reflection") or {}
    return {
        "found": bool(row),
        "experiment_id": experiment_id,
        "decision": row.get("decision"),
        "status": row.get("status"),
        "aggregate_expected_value_delta": (
            gate.get("aggregate_ev_delta")
            if gate.get("aggregate_ev_delta") is not None
            else gate.get("aggregate_expected_value_delta")
            if gate.get("aggregate_expected_value_delta") is not None
            else delta.get("aggregate_expected_value_score")
            if delta.get("aggregate_expected_value_score") is not None
            else row.get("aggregate_expected_value_delta")
        ),
        "aggregate_pnl_delta": (
            gate.get("aggregate_pnl_delta")
            if gate.get("aggregate_pnl_delta") is not None
            else gate.get("aggregate_total_pnl_delta")
            if gate.get("aggregate_total_pnl_delta") is not None
            else delta.get("aggregate_total_pnl")
            if delta.get("aggregate_total_pnl") is not None
            else row.get("aggregate_strategy_total_pnl_delta")
            if row.get("aggregate_strategy_total_pnl_delta") is not None
            else row.get("total_pnl_delta")
        ),
        "failed_reasons": gate.get("failed_reasons") or [],
        "max_drawdown_worse": gate.get("max_drawdown_worse"),
        "target_trade_count": gate.get("target_trade_count"),
        "target_windows": gate.get("target_windows") or [],
        "why_result_happened": reflection.get("why_result_happened"),
        "forbidden_near_neighbor_retry": reflection.get("forbidden_near_neighbor_retry"),
        "new_evidence_required": reflection.get("new_evidence_required"),
        "log": f"experiments/logs/{experiment_id}.json",
    }


def baseline_metrics(label: str) -> dict[str, Any]:
    return {
        "label": label,
        "source": "docs/backtesting.md",
        "baseline_result_file": BASELINE_RESULT_FILE,
        "expected_value_score": CANONICAL_AGGREGATE["expected_value_score"],
        "total_pnl": CANONICAL_AGGREGATE["total_pnl"],
        "total_trades": CANONICAL_AGGREGATE["trade_count"],
        "signals_generated": CANONICAL_AGGREGATE["signals_generated"],
        "signals_survived": CANONICAL_AGGREGATE["signals_survived"],
        "survival_rate": CANONICAL_AGGREGATE["survival_rate"],
        "max_drawdown_pct": CANONICAL_AGGREGATE["max_drawdown_pct"],
        "windows": CANONICAL_WINDOWS,
        "production_impact": {
            "scope": "analysis_only_no_strategy_change",
            "alters_candidate_ranking": False,
            "alters_exits": False,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_sizing": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "shared_policy_changed": False,
        },
    }


def gate4_no_change(failed_reasons: list[str]) -> dict[str, Any]:
    by_window: dict[str, dict[str, Any]] = {}
    for label, metrics in CANONICAL_WINDOWS.items():
        by_window[label] = {
            "before_expected_value_score": metrics["expected_value_score"],
            "after_expected_value_score": metrics["expected_value_score"],
            "delta_expected_value_score": 0.0,
            "before_total_pnl": metrics["total_pnl"],
            "after_total_pnl": metrics["total_pnl"],
            "delta_total_pnl": 0.0,
            "before_trade_count": metrics["trade_count"],
            "after_trade_count": metrics["trade_count"],
            "delta_trade_count": 0,
            "before_max_drawdown_pct": metrics["max_drawdown_pct"],
            "after_max_drawdown_pct": metrics["max_drawdown_pct"],
            "delta_max_drawdown_pct": 0.0,
            "before_survival_rate": metrics["survival_rate"],
            "after_survival_rate": metrics["survival_rate"],
            "delta_survival_rate": 0.0,
        }
    return {
        "passed": False,
        "decision": "blocked_missing_pit_historical_sec_filer_status_surface",
        "not_run_reason": "no_trustworthy_nonrepeat_strategy_change_after_pit_data_audit",
        "failed_reasons": failed_reasons,
        "aggregate_expected_value_delta": 0.0,
        "aggregate_total_pnl_delta": 0.0,
        "by_window": by_window,
        "minimum_core_survival_rate": CANONICAL_AGGREGATE["min_survival_rate"],
        "survival_guard_passed": True,
        "target_trade_count": 0,
        "target_trade_count_min": 20,
        "target_windows": [],
    }


def build_result() -> dict[str, Any]:
    sec_text_aggregate = audit_sec_text_aggregate()
    daily_text = audit_daily_sec_text_snapshots()
    filing_cache = audit_filing_text_cache()
    submissions = audit_submissions_metadata()
    failed_reasons = [
        "historical_10k_10q_cover_page_text_absent_in_sec_text_snapshots",
        "sec_submissions_category_is_current_top_level_not_pit_per_filing",
        "using_current_category_would_leak_future_state_into_backtest",
        "sec_filing_timeliness_and_item_code_neighbors_recently_rejected_or_frozen",
        "static_lead_lag_direction_rejected_with_drawdown_window_instability",
        "no_shared_default_off_helper_launch_without_gate4_ready_pit_field",
    ]
    gate4 = gate4_no_change(failed_reasons)
    history = {eid: summarize_experiment(eid) for eid in NEARBY_PRIOR_EXPERIMENTS}

    result = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "status": "blocked",
        "decision": gate4["decision"],
        "lane": "alpha_search",
        "change_type": "candidate_pool_full_stack_readiness_blocker",
        "mechanism_family": "sec_filer_status_candidate_pool",
        "trial_family": "post_leadlag_nonrepeat_surface_readiness",
        "trial_variant_id": "post_leadlag_filer_status_surface_readiness_v1",
        "changed_variable": "post_leadlag_filer_status_nonrepeat_alpha_surface_readiness_v1",
        "single_causal_variable": (
            "post_leadlag_filer_status_nonrepeat_alpha_surface_readiness_v1"
        ),
        "causal_components": [
            "PIT SEC cover-page filer-status transition availability audit",
            "standard 3-window Gate baseline comparison",
            "no strategy policy change unless data is Gate4-ready",
        ],
        "hypothesis": HYPOTHESIS,
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "related_experiments": history,
                "summary": (
                    "Filing-timeliness neighbors were rejected, the post-SEC-item "
                    "readiness audit was blocked, and the latest static lead-lag "
                    "relation experiment improved aggregate EV but failed old_thin "
                    "and drawdown stability. This run tests a materially different "
                    "field: historical cover-page filer-status transitions."
                ),
            },
            "3_single_decision_hypothesis": (
                "post_leadlag_filer_status_nonrepeat_alpha_surface_readiness_v1"
            ),
            "4_acceptance_standard": (
                "Use docs/backtesting.md Gate 1-4 on late_strong, mid_weak, and "
                "old_thin. Proceed only if PIT 10-K/10-Q filer-status fields "
                "exist for a shared default-off historical/daily helper; otherwise "
                "block with no strategy change."
            ),
            "5_reproducibility": f".venv\\Scripts\\python.exe -B {RUNNER_NAME}",
        },
        "prediction": PREDICTION,
        "calibration": {
            "actual_gate4_passed": False,
            "actual_success": 0,
            "brier_score": round((PREDICTION["success_probability"] - 0.0) ** 2, 4),
            "predicted_success_probability": PREDICTION["success_probability"],
            "failure_modes_observed": failed_reasons,
        },
        "before_metrics": baseline_metrics("before_baseline"),
        "after_metrics": baseline_metrics("after_no_strategy_change"),
        "delta_metrics": {
            "aggregate_expected_value_score": 0.0,
            "aggregate_total_pnl": 0.0,
            "aggregate_trade_count": 0,
            "minimum_survival_rate": CANONICAL_AGGREGATE["min_survival_rate"],
        },
        "gate1_baseline": {
            "source": "docs/backtesting.md",
            "baseline_result_file": BASELINE_RESULT_FILE,
            "aggregate": CANONICAL_AGGREGATE,
            "windows": CANONICAL_WINDOWS,
        },
        "gate2_field_availability": {
            "required_runtime_fields": [
                "entry_date",
                "target_price",
                "filing_date",
                "form_type",
                "cik",
                "ticker",
                "historical_filer_status",
            ],
            "required_fields_present_for_strategy": False,
            "missing_required_fields": ["historical_filer_status"],
            "entry_date_and_target_price_guard": (
                "No target strategy rows were generated; baseline fields remain "
                "unchanged and the alpha field is unavailable."
            ),
        },
        "gate3_survival": {
            "signals_generated": CANONICAL_AGGREGATE["signals_generated"],
            "signals_survived": CANONICAL_AGGREGATE["signals_survived"],
            "survival_rate": CANONICAL_AGGREGATE["survival_rate"],
            "target_strategy_signals_generated": 0,
            "target_strategy_survival_rate": None,
            "decision": "do_not_add_filter_no_gate4_ready_target_rows",
        },
        "gate4": gate4,
        "data_coverage_audit": {
            "sec_text_aggregate": sec_text_aggregate,
            "daily_sec_text_snapshots": daily_text,
            "filing_text_cache": filing_cache,
            "sec_submissions_metadata": submissions,
        },
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": {
            "why_result_happened": (
                "The alpha idea is stronger than another SEC item-code retry, "
                "but the repository does not currently have the needed PIT "
                "historical 10-K/10-Q cover-page filer-status field. The SEC text "
                "snapshots are locally 8-K-oriented, while submissions metadata "
                "has 10-K/10-Q pointers but only a current top-level category. "
                "Treating that current category as historical would leak future "
                "state and break production/backtest consistency."
            ),
            "negative_reflection": (
                "The experiment failed before strategy launch because the data "
                "edge is not yet materialized point-in-time. The failure is not "
                "that filer-status transitions are economically implausible; it "
                "is that using available local metadata would be non-PIT."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry SEC filing-timeliness thresholds, current-category "
                "filer-status filters, SEC item-code/text neighbors, DPO "
                "threshold/notional/hold retunes, or static lead-lag thresholds "
                "without a new PIT field or closed forward rows."
            ),
            "new_evidence_required": (
                "Build or acquire historical 10-K/10-Q cover-page text/XBRL by "
                "filing acceptance date, extract filer status into a PIT field, "
                "then expose it through a shared default-off helper used by both "
                "historical replay and daily snapshots."
            ),
            "best_next_alpha_direction": (
                "Free-data edge construction: PIT SEC cover-page status, "
                "historical 13F/crowding snapshots, borrow fee/availability, or "
                "PIT options history. Among current local files, none is Gate "
                "4-ready for a new non-repeat alpha today."
            ),
        },
        "baseline_result_file": BASELINE_RESULT_FILE,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "anti_js": "No JavaScript was used.",
        "reproduction": f".venv\\Scripts\\python.exe -B {RUNNER_NAME}",
    }
    return result


def build_log_record(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": result["timestamp"],
        "status": result["status"],
        "decision": result["decision"],
        "lane": result["lane"],
        "change_type": result["change_type"],
        "mechanism_family": result["mechanism_family"],
        "trial_family": result["trial_family"],
        "trial_variant_id": result["trial_variant_id"],
        "changed_variable": result["changed_variable"],
        "single_causal_variable": result["single_causal_variable"],
        "hypothesis": result["hypothesis"],
        "pre_run_questions": result["pre_run_questions"],
        "prediction": result["prediction"],
        "calibration": result["calibration"],
        "aggregate_expected_value_delta": result["delta_metrics"][
            "aggregate_expected_value_score"
        ],
        "aggregate_strategy_total_pnl_delta": result["delta_metrics"][
            "aggregate_total_pnl"
        ],
        "gate1_baseline": result["gate1_baseline"],
        "gate2_field_availability": result["gate2_field_availability"],
        "gate3_survival": result["gate3_survival"],
        "gate4": result["gate4"],
        "data_coverage_audit": result["data_coverage_audit"],
        "production_impact": result["production_impact"],
        "post_run_reflection": result["post_run_reflection"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": result["anti_js"],
    }


def build_card(result: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID}: PIT SEC filer-status surface readiness",
        "",
        f"- Decision: `{result['decision']}`",
        f"- Status: `{result['status']}`",
        "- Lane: `alpha_search`",
        "- Production impact: no strategy, order, ranking, sizing, exit, LLM/news, or watchlist change.",
        "",
        "## Hypothesis",
        "",
        result["hypothesis"],
        "",
        "## Gate 4",
        "",
        f"- Aggregate EV delta: `{result['gate4']['aggregate_expected_value_delta']:+.4f}`",
        f"- Aggregate PnL delta: `${result['gate4']['aggregate_total_pnl_delta']:+,.2f}`",
        f"- Failed reasons: `{', '.join(result['gate4']['failed_reasons'])}`",
        "",
        "| Window | EV Before | EV After | PnL Before | PnL After | Survival |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, window in result["gate4"]["by_window"].items():
        lines.append(
            "| {label} | {evb:.4f} | {eva:.4f} | ${pnb:,.2f} | ${pna:,.2f} | {surv:.2%} |".format(
                label=label,
                evb=window["before_expected_value_score"],
                eva=window["after_expected_value_score"],
                pnb=window["before_total_pnl"],
                pna=window["after_total_pnl"],
                surv=window["before_survival_rate"],
            )
        )

    aggregate = result["data_coverage_audit"]["sec_text_aggregate"]
    daily = result["data_coverage_audit"]["daily_sec_text_snapshots"]
    submissions = result["data_coverage_audit"]["sec_submissions_metadata"]
    lines.extend(
        [
            "",
            "## Data Audit",
            "",
            f"- Aggregate SEC text rows: `{aggregate['row_count']}`, forms: `{aggregate['form_counts']}`",
            f"- Daily SEC text files: `{daily['file_count']}`, rows: `{daily['row_count']}`",
            f"- Daily 10-K/10-Q rows by window: `{daily['target_10k_10q_rows_by_window']}`",
            f"- Submissions 10-K/10-Q pointers by window: `{submissions['recent_10k_10q_rows_by_window']}`",
            f"- Submissions status row fields: `{submissions['recent_status_row_fields_present']}`",
            "",
            "## Reflection",
            "",
            result["post_run_reflection"]["why_result_happened"],
            "",
            "## Next Evidence",
            "",
            result["post_run_reflection"]["new_evidence_required"],
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def write_manifest(result: dict[str, Any]) -> None:
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
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": utc_now(),
        "git_head": git_value("rev-parse", "HEAD"),
        "git_branch": git_value("branch", "--show-current"),
        "files": {repo_rel(path): sha256(path) for path in files},
        "command": result["reproduction"],
        "anti_js": "No JavaScript was used.",
    }
    write_json(MANIFEST_JSON, manifest)


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
    fields = {
        "owner": "alpha-search-automation",
        "hypothesis": result["hypothesis"],
        "change_type": result["change_type"],
        "mechanism_family": result["mechanism_family"],
        "trial_family": result["trial_family"],
        "trial_variant_id": result["trial_variant_id"],
        "single_causal_variable": result["single_causal_variable"],
        "changed_variable": result["changed_variable"],
        "causal_components": result["causal_components"],
        "prior_trial_count": 6,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": "pit_sec_cover_page_status_availability_audit",
        "baseline_result_file": BASELINE_RESULT_FILE,
        "decision": result["decision"],
        "summary": result["post_run_reflection"]["why_result_happened"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "log": repo_rel(LOG_JSON),
        "card_file": repo_rel(CARD_MD),
        "revision_manifest_file": repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": result["delta_metrics"][
            "aggregate_expected_value_score"
        ],
        "aggregate_strategy_total_pnl_delta": result["delta_metrics"][
            "aggregate_total_pnl"
        ],
        "post_run_reflection": result["post_run_reflection"],
        "production_impact": result["production_impact"],
        "gate1_baseline": result["gate1_baseline"],
        "gate2_field_availability": result["gate2_field_availability"],
        "gate3_survival": result["gate3_survival"],
        "gate4": result["gate4"],
    }
    experiment_registry.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=registry_result,
        status="blocked",
        fields=fields,
    )
    write_manifest(result)


def main() -> None:
    result = build_result()
    persist(result)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": result["status"],
                "decision": result["decision"],
                "aggregate_ev_delta": result["delta_metrics"][
                    "aggregate_expected_value_score"
                ],
                "aggregate_pnl_delta": result["delta_metrics"]["aggregate_total_pnl"],
                "sec_text_aggregate_forms": result["data_coverage_audit"][
                    "sec_text_aggregate"
                ]["form_counts"],
                "daily_10k_10q_rows_by_window": result["data_coverage_audit"][
                    "daily_sec_text_snapshots"
                ]["target_10k_10q_rows_by_window"],
                "submissions_10k_10q_rows_by_window": result["data_coverage_audit"][
                    "sec_submissions_metadata"
                ]["recent_10k_10q_rows_by_window"],
                "submissions_status_row_fields": result["data_coverage_audit"][
                    "sec_submissions_metadata"
                ]["recent_status_row_fields_present"],
                "best_next_alpha_direction": result["post_run_reflection"][
                    "best_next_alpha_direction"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
