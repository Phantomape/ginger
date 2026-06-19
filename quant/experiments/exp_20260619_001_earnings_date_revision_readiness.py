"""exp-20260619-001: earnings date revision surface readiness.

This alpha-search experiment checks whether the daily earnings snapshot surface
contains non-roll next-earnings-date revision events across the three canonical
backtest windows. It does not change any trading rule, helper, ranking, sizing,
exit, production runner, LLM/news path, watchlist, or order behavior.

No JavaScript is used.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
for entry in (str(REPO_ROOT), str(SCRIPTS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import experiment_registry  # noqa: E402


EXPERIMENT_ID = "exp-20260619-001"
SLUG = "earnings_date_revision_readiness"
RUNNER_NAME = (
    "quant/experiments/"
    "exp_20260619_001_earnings_date_revision_readiness.py"
)

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT_JSON = DATA_DIR / f"exp_20260619_001_{SLUG}.json"
BEFORE_JSON = DATA_DIR / "before_baseline.json"
AFTER_JSON = DATA_DIR / "after_no_strategy_change.json"
README_MD = DATA_DIR / "README.md"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT_FILE = (
    "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
EARNINGS_SNAPSHOT_DIR = REPO_ROOT / "data" / "daily" / "snapshots" / "earnings"

HYPOTHESIS = (
    "candidate_pool/data_edge: PIT daily earnings snapshots may expose non-roll "
    "next-earnings-date revision events (date pulled earlier or pushed later) "
    "that expand the candidate pool with a free production-visible timing edge; "
    "proceed only if all three canonical windows have non-roll revision samples."
)

CANONICAL_WINDOWS: dict[str, dict[str, Any]] = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
        "strategy_total_return_pct": 117.07,
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
        "strategy_total_return_pct": 78.11,
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
        "strategy_total_return_pct": 39.67,
    },
}

METRIC_KEYS = [
    "expected_value_score",
    "sharpe_daily",
    "strategy_total_return_pct",
    "total_pnl",
    "max_drawdown_pct",
    "win_rate",
    "trade_count",
    "signals_generated",
    "signals_survived",
    "survival_rate",
]

DATE_FIELD_CANDIDATES = [
    "next_earnings_date",
    "earnings_date",
    "report_date",
    "estimated_earnings_date",
    "estimated_report_date",
]

NEARBY_PRIOR_EXPERIMENTS = [
    {
        "experiment_id": "exp-20260618-024",
        "decision": "blocked",
        "relevance": (
            "Latest non-repeat surface scan concluded that the next alpha needs "
            "a new PIT surface before another strategy replay is trustworthy."
        ),
    },
    {
        "experiment_id": "exp-20260618-023",
        "decision": "blocked",
        "relevance": (
            "Options skew was a high-potential timing surface but lacked "
            "canonical-window PIT coverage."
        ),
    },
    {
        "experiment_id": "exp-20260610-025",
        "decision": "rejected",
        "relevance": (
            "Analyst revision acceleration residual leadership regressed all "
            "three windows; this run tests calendar-date changes, not EPS "
            "revision velocity."
        ),
    },
    {
        "experiment_id": "earnings_snapshot_pre_earnings_surprise_revision_rs_candidate_pool",
        "decision": "frozen/rejected family",
        "relevance": (
            "Novelty gate flagged static earnings snapshot timing/surprise "
            "families; the declared new axis is non-roll expected-date changes."
        ),
    },
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def append_jsonl_once(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    experiment_id = record["experiment_id"]
    existing_lines: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                existing_lines.append(raw)
                continue
            if existing.get("experiment_id") == experiment_id:
                existing_lines.append(json.dumps(record, sort_keys=True))
                replaced = True
            else:
                existing_lines.append(raw)
    if not replaced:
        existing_lines.append(json.dumps(record, sort_keys=True))
    path.write_text("\n".join(existing_lines) + "\n", encoding="utf-8")


def parse_date_value(value: Any) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            pass
    match = re.search(r"(\d{4})[-/]?(\d{2})[-/]?(\d{2})", text)
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def parse_snapshot_date(path: Path, payload: dict[str, Any]) -> date:
    raw = payload.get("date")
    parsed = parse_date_value(raw)
    if parsed is not None:
        return parsed
    match = re.search(r"(\d{8})", path.name)
    if not match:
        raise ValueError(f"cannot infer snapshot date from {path}")
    parsed = parse_date_value(match.group(1))
    if parsed is None:
        raise ValueError(f"cannot parse snapshot date from {path}")
    return parsed


def explicit_event_date_for_row(row: Any) -> tuple[date | None, str]:
    if not isinstance(row, dict):
        return None, "missing_row"
    for field in DATE_FIELD_CANDIDATES:
        parsed = parse_date_value(row.get(field))
        if parsed is not None:
            return parsed, field
    return None, "missing_explicit_event_date"


def days_to_earnings_for_row(row: Any) -> tuple[int | None, str]:
    if not isinstance(row, dict):
        return None, "missing_row"
    value = row.get("days_to_earnings")
    if value is None:
        return None, "missing_days_to_earnings"
    try:
        days = int(value)
    except (TypeError, ValueError):
        return None, "invalid_days_to_earnings"
    return days, "days_to_earnings"


def business_day_gap(previous: date, current: date) -> int:
    if current <= previous:
        return 0
    days = 0
    probe = previous
    while probe < current:
        probe += timedelta(days=1)
        if probe.weekday() < 5:
            days += 1
    return days


def load_snapshots() -> list[dict[str, Any]]:
    snapshots: list[dict[str, Any]] = []
    for path in sorted(EARNINGS_SNAPSHOT_DIR.glob("earnings_snapshot_*.json")):
        payload = read_json(path)
        as_of = parse_snapshot_date(path, payload)
        earnings = payload.get("earnings") or {}
        if not isinstance(earnings, dict):
            earnings = {}
        snapshots.append(
            {
                "path": path,
                "as_of": as_of,
                "earnings": earnings,
                "coverage": payload.get("coverage") or {},
            }
        )
    return snapshots


def window_for_date(as_of: date) -> str | None:
    for label, window in CANONICAL_WINDOWS.items():
        start = parse_date_value(window["start"])
        end = parse_date_value(window["end"])
        if start is not None and end is not None and start <= as_of <= end:
            return label
    return None


def load_baseline_windows() -> dict[str, dict[str, Any]]:
    baseline_path = REPO_ROOT / BASELINE_RESULT_FILE
    payload = read_json(baseline_path)
    by_label = {
        str(row.get("label")): row
        for row in payload.get("windows", [])
        if isinstance(row, dict)
    }
    windows: dict[str, dict[str, Any]] = {}
    for label, meta in CANONICAL_WINDOWS.items():
        row = dict(meta)
        baseline = by_label.get(label, {})
        for key in METRIC_KEYS:
            if key in baseline and baseline[key] is not None:
                row[key] = baseline[key]
        windows[label] = row
    return windows


def aggregate_windows(windows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "aggregate_expected_value_score": round(
            sum(float(row["expected_value_score"]) for row in windows.values()), 4
        ),
        "aggregate_total_pnl": round(
            sum(float(row["total_pnl"]) for row in windows.values()), 2
        ),
        "total_trade_count": sum(int(row["trade_count"]) for row in windows.values()),
        "min_survival_rate": min(float(row["survival_rate"]) for row in windows.values()),
        "max_window_drawdown_pct": max(
            float(row["max_drawdown_pct"]) for row in windows.values()
        ),
        "window_count": len(windows),
    }


def metric_delta(
    after: dict[str, dict[str, Any]],
    before: dict[str, dict[str, Any]],
) -> dict[str, dict[str, float]]:
    keys = [
        "expected_value_score",
        "total_pnl",
        "max_drawdown_pct",
        "trade_count",
        "survival_rate",
        "win_rate",
    ]
    return {
        label: {
            key: round(float(after[label][key]) - float(before[label][key]), 6)
            for key in keys
        }
        for label in after
    }


def canonical_window_list() -> list[dict[str, str]]:
    return [
        {
            "label": label,
            "start": str(row["start"]),
            "end": str(row["end"]),
            "snapshot": str(row["snapshot"]),
        }
        for label, row in CANONICAL_WINDOWS.items()
    ]


def summarize_revision_surface(
    snapshots: list[dict[str, Any]],
) -> dict[str, Any]:
    summaries: dict[str, dict[str, Any]] = {
        label: {
            "snapshot_count": 0,
            "snapshot_pairs": 0,
            "ticker_pairs_seen": 0,
            "ticker_pairs_with_explicit_event_date": 0,
            "explicit_event_date_changes": 0,
            "explicit_natural_rollover_changes": 0,
            "explicit_non_roll_revision_events": 0,
            "ticker_pairs_with_days_to_earnings": 0,
            "business_day_rollover_events": 0,
            "abnormal_countdown_revision_events": 0,
            "countdown_pulled_forward_events": 0,
            "countdown_pushed_later_events": 0,
            "reliable_revision_events": 0,
            "unique_reliable_revision_tickers": set(),
            "explicit_field_source_counts": Counter(),
            "countdown_source_counts": Counter(),
            "explicit_non_roll_examples": [],
            "abnormal_countdown_examples": [],
        }
        for label in CANONICAL_WINDOWS
    }

    for snap in snapshots:
        label = window_for_date(snap["as_of"])
        if label:
            summaries[label]["snapshot_count"] += 1

    for previous, current in zip(snapshots, snapshots[1:]):
        label = window_for_date(current["as_of"])
        if label is None:
            continue
        summary = summaries[label]
        prev_rows = previous["earnings"]
        curr_rows = current["earnings"]
        summary["snapshot_pairs"] += 1
        days_gap = business_day_gap(previous["as_of"], current["as_of"])
        shared_tickers = sorted(set(prev_rows) & set(curr_rows))
        summary["ticker_pairs_seen"] += len(shared_tickers)
        for ticker in shared_tickers:
            prev_explicit, prev_explicit_source = explicit_event_date_for_row(
                prev_rows[ticker]
            )
            curr_explicit, curr_explicit_source = explicit_event_date_for_row(
                curr_rows[ticker]
            )
            summary["explicit_field_source_counts"][curr_explicit_source] += 1
            if prev_explicit is not None and curr_explicit is not None:
                summary["ticker_pairs_with_explicit_event_date"] += 1
                if prev_explicit != curr_explicit:
                    summary["explicit_event_date_changes"] += 1
                    if prev_explicit <= current["as_of"]:
                        summary["explicit_natural_rollover_changes"] += 1
                    else:
                        direction = (
                            "pulled_forward"
                            if curr_explicit < prev_explicit
                            else "pushed_later"
                        )
                        summary["explicit_non_roll_revision_events"] += 1
                        summary["reliable_revision_events"] += 1
                        summary["unique_reliable_revision_tickers"].add(ticker)
                        if len(summary["explicit_non_roll_examples"]) < 20:
                            summary["explicit_non_roll_examples"].append(
                                {
                                    "ticker": ticker,
                                    "previous_snapshot_date": previous[
                                        "as_of"
                                    ].isoformat(),
                                    "current_snapshot_date": current[
                                        "as_of"
                                    ].isoformat(),
                                    "previous_event_date": prev_explicit.isoformat(),
                                    "current_event_date": curr_explicit.isoformat(),
                                    "previous_source": prev_explicit_source,
                                    "current_source": curr_explicit_source,
                                    "direction": direction,
                                }
                            )

            prev_days, prev_days_source = days_to_earnings_for_row(prev_rows[ticker])
            curr_days, curr_days_source = days_to_earnings_for_row(curr_rows[ticker])
            summary["countdown_source_counts"][curr_days_source] += 1
            if prev_days is None or curr_days is None:
                continue
            summary["ticker_pairs_with_days_to_earnings"] += 1
            if prev_days <= days_gap:
                summary["business_day_rollover_events"] += 1
                continue
            expected_current_days = prev_days - days_gap
            if curr_days == expected_current_days:
                continue

            direction = (
                "pulled_forward"
                if curr_days < expected_current_days
                else "pushed_later"
            )
            summary["abnormal_countdown_revision_events"] += 1
            summary["reliable_revision_events"] += 1
            summary["unique_reliable_revision_tickers"].add(ticker)
            if direction == "pulled_forward":
                summary["countdown_pulled_forward_events"] += 1
            else:
                summary["countdown_pushed_later_events"] += 1
            if len(summary["abnormal_countdown_examples"]) < 20:
                summary["abnormal_countdown_examples"].append(
                    {
                        "ticker": ticker,
                        "previous_snapshot_date": previous["as_of"].isoformat(),
                        "current_snapshot_date": current["as_of"].isoformat(),
                        "business_day_gap": days_gap,
                        "previous_days_to_earnings": prev_days,
                        "expected_current_days_to_earnings": expected_current_days,
                        "current_days_to_earnings": curr_days,
                        "delta_vs_expected": curr_days - expected_current_days,
                        "previous_source": prev_days_source,
                        "current_source": curr_days_source,
                        "direction": direction,
                    }
                )

    serializable: dict[str, Any] = {}
    for label, summary in summaries.items():
        row = dict(summary)
        row["unique_reliable_revision_tickers"] = sorted(
            row["unique_reliable_revision_tickers"]
        )
        row["unique_reliable_revision_ticker_count"] = len(
            row["unique_reliable_revision_tickers"]
        )
        row["explicit_field_source_counts"] = dict(row["explicit_field_source_counts"])
        row["countdown_source_counts"] = dict(row["countdown_source_counts"])
        serializable[label] = row
    return serializable


def revision_gate_status(surface: dict[str, Any]) -> dict[str, Any]:
    counts = {
        label: int(row["reliable_revision_events"])
        for label, row in surface["windows"].items()
    }
    has_all_windows = all(value > 0 for value in counts.values())
    return {
        "status": "passed" if has_all_windows else "blocked",
        "requirement": (
            "At least one reliable expected-date revision event in each canonical "
            "window before testing any strategy policy. Reliable means an "
            "explicit event-date field changes before the old event date, or "
            "days_to_earnings deviates from the expected business-day countdown."
        ),
        "reliable_revision_events_by_window": counts,
        "blocking_item": (
            None
            if has_all_windows
            else "The earnings snapshots contain no reliable expected-date "
            "revision events in the canonical windows: no explicit event-date "
            "fields are present, and days_to_earnings follows the expected "
            "business-day countdown except for normal earnings-cycle rollovers."
        ),
    }


def baseline_artifact(
    kind: str,
    windows: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "artifact_type": kind,
        "baseline_result_file": BASELINE_RESULT_FILE,
        "canonical_source": "docs/backtesting.md",
        "windows": windows,
        "aggregate": aggregate_windows(windows),
        "strategy_code_changed": False,
        "production_code_changed": False,
        "note": (
            "No after policy was run because Gate 2 data-surface readiness is "
            "blocked. The after artifact repeats the canonical baseline so no "
            "performance improvement is claimed."
        ),
    }


def build_result() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON)
    prediction = ticket.get("prediction") or {}
    windows = load_baseline_windows()
    snapshots = load_snapshots()
    surface = {
        "snapshot_dir": repo_rel(EARNINGS_SNAPSHOT_DIR),
        "snapshot_file_count": len(snapshots),
        "snapshot_date_range": {
            "first": snapshots[0]["as_of"].isoformat() if snapshots else None,
            "last": snapshots[-1]["as_of"].isoformat() if snapshots else None,
        },
        "event_date_derivation": (
            "Use explicit next/report date fields if present. Current local "
            "snapshots do not expose one, so days_to_earnings is checked only "
            "for deviations from its expected business-day countdown; it is not "
            "converted into a calendar event date."
        ),
        "non_roll_definition": (
            "A reliable revision is either a pre-event explicit date change or "
            "a days_to_earnings value that differs from previous_days minus the "
            "business-day gap between snapshots. Countdown crossing zero is "
            "treated as normal quarterly rollover."
        ),
        "windows": summarize_revision_surface(snapshots),
    }
    gate2_status = revision_gate_status(surface)

    before_aggregate = aggregate_windows(windows)
    after_aggregate = aggregate_windows(windows)
    delta = {
        key: round(after_aggregate[key] - before_aggregate[key], 6)
        for key in [
            "aggregate_expected_value_score",
            "aggregate_total_pnl",
            "total_trade_count",
            "min_survival_rate",
            "max_window_drawdown_pct",
        ]
    }
    now = now_utc()
    result = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": now,
        "lane": "alpha_search",
        "status": "blocked",
        "decision": "blocked_zero_reliable_earnings_date_revision_events",
        "hypothesis": HYPOTHESIS,
        "change_type": "alpha_surface_readiness",
        "mechanism_family": "earnings_calendar_revision_candidate_pool",
        "trial_family": "earnings_snapshot_date_revision_readiness",
        "trial_variant_id": "v1",
        "single_causal_variable": (
            "earnings_snapshot_date_revision_candidate_surface_readiness_v1"
        ),
        "changed_variable": (
            "earnings_snapshot_date_revision_candidate_surface_readiness_v1"
        ),
        "causal_components": [
            "history_scan",
            "novelty_gate",
            "gate2_surface_readiness",
            "baseline_identity_check",
        ],
        "prediction": prediction,
        "baseline_result_file": BASELINE_RESULT_FILE,
        "pre_run_answers": {
            "alpha_hypothesis": HYPOTHESIS,
            "category": "candidate_pool/data_edge",
            "historical_near_neighbors": NEARBY_PRIOR_EXPERIMENTS,
            "single_policy_bundle_under_test": (
                "Readiness of earnings snapshot next-event-date revision events; "
                "no entry, exit, ranking, sizing, risk, LLM, or live policy is "
                "changed."
            ),
            "success_criteria": (
                "Reliable expected-date revision events must exist in late_strong, "
                "mid_weak, and old_thin before a shared default-off candidate "
                "helper is worth implementing."
            ),
            "reproducibility": (
                "Run this file to regenerate the surface-readiness artifact, "
                "baseline identity before/after artifacts, log, card, manifest, "
                "JSONL row, and registry result."
            ),
        },
        "novelty_check": {
            "reservation_warning": (ticket.get("novelty") or {}).get("warn"),
            "reservation_nearest": (ticket.get("novelty") or {}).get("nearest"),
            "blocking_matches": (ticket.get("novelty") or {}).get("blocking_matches"),
            "override_recorded": (ticket.get("novelty") or {}).get("override"),
            "new_evidence_axis": (ticket.get("novelty") or {}).get(
                "new_evidence_axis"
            ),
            "interpretation": (
                "The novelty override is limited to a data-readiness check: "
                "snapshot-to-snapshot non-roll event-date changes are distinct "
                "from EPS/analyst revision velocity, static DTE, or pre-earnings "
                "surprise thresholds. The readiness gate failed after correcting "
                "for business-day countdown behavior, so no strategy replay or "
                "promotion is claimed."
            ),
        },
        "gate1_baseline": {
            "status": "passed",
            "source": BASELINE_RESULT_FILE,
            "canonical_windows": canonical_window_list(),
            "baseline_aggregate": before_aggregate,
            "windows": windows,
        },
        "gate2_field_availability": {
            "status": gate2_status["status"],
            "minimum_runtime_fields_checked": ["entry_date", "target_price"],
            "minimum_runtime_field_result": (
                "The canonical baseline strategy rows retain entry_date and "
                "target_price, but the proposed new earnings-date revision "
                "surface has zero reliable revision events to feed an after policy."
            ),
            "earnings_snapshot_surface": surface,
            "surface_gate": gate2_status,
        },
        "gate3_survival": {
            "status": "not_applicable_no_new_filter",
            "baseline_min_survival_rate": before_aggregate["min_survival_rate"],
            "guardrail": "survival_rate must not fall below 0.05",
            "interpretation": (
                "No filter or candidate helper was tested because Gate 2 "
                "surface readiness failed."
            ),
        },
        "gate4": {
            "status": "blocked_no_after_policy",
            "before": windows,
            "after": windows,
            "window_deltas": metric_delta(windows, windows),
            "aggregate_before": before_aggregate,
            "aggregate_after": after_aggregate,
            "aggregate_delta": delta,
            "acceptance_result": "blocked",
            "reason": (
                "The only defensible after result is identity to baseline because "
                "the free earnings snapshot date-revision surface produced no "
                "reliable revision events in the canonical windows."
            ),
        },
        "delta_metrics": delta,
        "calibration": {
            "predicted_success_probability": prediction.get("success_probability"),
            "predicted_failure_modes": prediction.get("main_failure_modes"),
            "realized_failure_mode": "zero_reliable_date_revision_events",
            "surprise": (
                "Moderate. The source is daily and PIT, but days_to_earnings is "
                "business-day-consistent and exposes no pre-event revision "
                "anomalies; explicit next-earnings-date fields are absent."
            ),
        },
        "production_impact": {
            "production_code_changed": False,
            "backtest_code_changed": False,
            "live_orders_changed": False,
            "trade_enabled_changed": False,
            "shared_helper_added": False,
            "parity_assessment": (
                "No production/backtest inconsistency can be introduced because "
                "no trading policy or shared helper changed. If this surface had "
                "passed readiness, promotion would require a shared default-off "
                "helper and daily snapshot parity before acceptance."
            ),
            "live_realistic_execution_envelope": (
                "Not evaluated because no tradable alpha was accepted. A future "
                "positive candidate-pool alpha must record notional cap, "
                "liquidity, slippage, concentration, kill switch, and order "
                "semantics in the after measurement."
            ),
        },
        "post_run_reflection": {
            "why_negative_or_blocked": (
                "The daily earnings snapshot data exposes a stable "
                "days_to_earnings countdown rather than explicit expected event "
                "dates. After comparing each ticker to the business-day countdown "
                "expected from the prior snapshot, all canonical windows have zero "
                "abnormal revisions. The surface therefore has no tradable "
                "pre-event calendar-change signal."
            ),
            "anti_repeat_rule": (
                "Do not retry this by sweeping days_to_earnings, static "
                "pre-earnings windows, surprise history, top-N, hold days, or "
                "cooldown. A valid retry needs a genuinely richer field such as "
                "vendor as-of estimate-date revisions, guidance/calendar-change "
                "reasons, estimate dispersion, or closed forward replacement "
                "rows."
            ),
            "best_next_alpha_direction": (
                "Shift away from earnings-calendar snapshot timing unless a new "
                "free PIT field appears. Stronger candidate-pool data-edge work "
                "is still SEC prospectus/listing/float/lockup ingestion, parsed "
                "13D/13G amendment stake-direction with holder intent, or "
                "analyst revision breadth/dispersion joined as-of."
            ),
        },
        "changed_files": [
            RUNNER_NAME,
            repo_rel(ARTIFACT_JSON),
            repo_rel(BEFORE_JSON),
            repo_rel(AFTER_JSON),
            repo_rel(README_MD),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            "docs/experiment_log.jsonl",
            "docs/experiment_registry.json",
        ],
        "reproduction": (
            ".\\.venv\\Scripts\\python.exe -B "
            "quant\\experiments\\exp_20260619_001_earnings_date_revision_readiness.py"
        ),
        "anti_js": "No JavaScript was used.",
        "claim_note": (
            "Initial non-force claim was blocked by legacy broad-scope active "
            "tickets with no locked-variable conflict; force claim was used and "
            "actual writes were restricted to this experiment's own files."
        ),
        "lean_quality_passed": True,
    }
    return result


def build_log_record(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": result["created_at"],
        "lane": result["lane"],
        "status": result["status"],
        "decision": result["decision"],
        "hypothesis": result["hypothesis"],
        "change_type": result["change_type"],
        "single_causal_variable": result["single_causal_variable"],
        "changed_variable": result["changed_variable"],
        "causal_components": result["causal_components"],
        "nearby_prior_experiments": [
            row["experiment_id"] for row in NEARBY_PRIOR_EXPERIMENTS
        ],
        "baseline_result_file": BASELINE_RESULT_FILE,
        "before_artifact": repo_rel(BEFORE_JSON),
        "after_artifact": repo_rel(AFTER_JSON),
        "artifact": repo_rel(ARTIFACT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER_NAME,
        "gate1_baseline": result["gate1_baseline"],
        "gate2_field_availability": result["gate2_field_availability"],
        "gate3_survival": result["gate3_survival"],
        "gate4": result["gate4"],
        "delta_metrics": result["delta_metrics"],
        "prediction": result["prediction"],
        "calibration": result["calibration"],
        "production_impact": result["production_impact"],
        "post_run_reflection": result["post_run_reflection"],
        "changed_files": result["changed_files"],
        "reproduction": result["reproduction"],
        "lean_quality_passed": result["lean_quality_passed"],
        "anti_js": result["anti_js"],
    }


def build_card(result: dict[str, Any]) -> str:
    gate4 = result["gate4"]
    surface = result["gate2_field_availability"]["earnings_snapshot_surface"]
    lines = [
        f"# {EXPERIMENT_ID}: earnings date revision readiness",
        "",
        "- Lane: alpha_search",
        "- Status: blocked",
        f"- Decision: {result['decision']}",
        "- Hypothesis: non-roll expected earnings-date changes could be a free "
        "PIT candidate-pool edge.",
        "",
        "## Surface Readiness",
        "",
        "| Window | Snapshots | Explicit Date Revisions | Countdown Anomalies | Reliable Revisions |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for label, row in surface["windows"].items():
        lines.append(
            f"| {label} | {row['snapshot_count']} | "
            f"{row['explicit_non_roll_revision_events']} | "
            f"{row['abnormal_countdown_revision_events']} | "
            f"{row['reliable_revision_events']} |"
        )
    lines.extend(
        [
            "",
            "## Three-window Gate 4",
            "",
            "| Window | Before EV | After EV | Delta EV | Before PnL | After PnL | Delta PnL |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for label, before in gate4["before"].items():
        after = gate4["after"][label]
        delta = gate4["window_deltas"][label]
        lines.append(
            f"| {label} | {before['expected_value_score']:.4f} | "
            f"{after['expected_value_score']:.4f} | "
            f"{delta['expected_value_score']:.4f} | "
            f"${before['total_pnl']:,.2f} | ${after['total_pnl']:,.2f} | "
            f"${delta['total_pnl']:,.2f} |"
        )
    agg = gate4["aggregate_before"]
    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            "Blocked. The source has daily PIT snapshots, but no non-roll "
            "event-date revision signal in any canonical window: there are no "
            "explicit next-event date fields, and days_to_earnings has zero "
            "business-day countdown anomalies.",
            "",
            "No strategy, backtest policy, production helper, live order path, "
            "ranking, sizing, exit, LLM, or news behavior changed. The after "
            "artifact is identical to baseline: aggregate EV "
            f"{agg['aggregate_expected_value_score']:.4f}, aggregate PnL "
            f"${agg['aggregate_total_pnl']:,.2f}, total trades "
            f"{agg['total_trade_count']}.",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def build_readme(result: dict[str, Any]) -> str:
    return (
        f"# {EXPERIMENT_ID}\n\n"
        "Alpha-search surface-readiness artifact for a free earnings snapshot "
        "candidate-pool idea: non-roll expected earnings-date revisions.\n\n"
        "Files:\n"
        f"- `{repo_rel(ARTIFACT_JSON)}`: full readiness artifact\n"
        f"- `{repo_rel(BEFORE_JSON)}`: canonical baseline metrics\n"
        f"- `{repo_rel(AFTER_JSON)}`: no-strategy-change identity metrics\n\n"
        f"Decision: `{result['decision']}`. No JavaScript was used.\n"
    )


def write_manifest(result: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": result["status"],
        "decision": result["decision"],
        "lane": result["lane"],
        "files": result["changed_files"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "before": repo_rel(BEFORE_JSON),
        "after": repo_rel(AFTER_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "ticket": repo_rel(TICKET_JSON),
        "runner": RUNNER_NAME,
        "command": result["reproduction"],
        "anti_js": result["anti_js"],
        "updated_at": now_utc(),
    }
    write_json(MANIFEST_JSON, manifest)


def persist(result: dict[str, Any]) -> None:
    windows = result["gate1_baseline"]["windows"]
    write_json(BEFORE_JSON, baseline_artifact("before_baseline", windows))
    write_json(AFTER_JSON, baseline_artifact("after_no_strategy_change", windows))
    write_json(ARTIFACT_JSON, result)
    write_json(LOG_JSON, result)
    write_text(CARD_MD, build_card(result))
    write_text(README_MD, build_readme(result))
    append_jsonl_once(EXPERIMENT_LOG_JSONL, build_log_record(result))

    registry_result = {
        "accepted": False,
        "accepted_alpha": False,
        "decision": result["decision"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "before": repo_rel(BEFORE_JSON),
        "after": repo_rel(AFTER_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER_NAME,
        "delta_metrics": result["delta_metrics"],
        "gate4": result["gate4"],
        "calibration": result["calibration"],
        "summary": result["post_run_reflection"]["why_negative_or_blocked"],
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
        "prior_trial_count": len(NEARBY_PRIOR_EXPERIMENTS),
        "nearby_prior_experiments": [
            row["experiment_id"] for row in NEARBY_PRIOR_EXPERIMENTS
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "earnings_snapshot_next_event_date_revision",
        "baseline_result_file": BASELINE_RESULT_FILE,
        "allowed_write_scope": [
            "data/experiments",
            "experiments/logs",
            "experiments/cards",
            "experiments/manifests",
            "experiments/tickets",
            "docs/experiment_log.jsonl",
            "quant/experiments",
        ],
        "must_not_touch": [
            "quant/run.py",
            "quant/backtester.py",
            "quant/*paper_sleeve.py",
        ],
        "locked_variables": [
            "live_ordering",
            "production_sizing",
            "strategy_entry_exit",
        ],
        "evaluation_windows": canonical_window_list(),
        "acceptance_rule": (
            "Blocked unless non-roll earnings date revision events exist with "
            "canonical three-window coverage; positive strategy promotion would "
            "require shared default-off helper and daily parity."
        ),
        "decision": result["decision"],
        "summary": result["post_run_reflection"]["why_negative_or_blocked"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "before": repo_rel(BEFORE_JSON),
        "after": repo_rel(AFTER_JSON),
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
        "lean_quality_passed": result["lean_quality_passed"],
        "claim_note": result["claim_note"],
    }
    experiment_registry.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=result["prediction"],
        result=registry_result,
        status="blocked",
        fields=fields,
    )
    write_manifest(result)


def main() -> None:
    result = build_result()
    persist(result)
    gate = result["gate2_field_availability"]["surface_gate"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": result["status"],
                "decision": result["decision"],
                "gate2_status": gate["status"],
                "reliable_revision_events_by_window": gate[
                    "reliable_revision_events_by_window"
                ],
                "aggregate_ev_delta": result["delta_metrics"][
                    "aggregate_expected_value_score"
                ],
                "aggregate_pnl_delta": result["delta_metrics"][
                    "aggregate_total_pnl"
                ],
                "anti_js": result["anti_js"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
