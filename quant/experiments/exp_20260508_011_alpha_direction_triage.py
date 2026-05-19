"""exp-20260508-011 alpha direction triage.

This is an alpha-search run, not a production strategy change.

Primary hypothesis: after the same-event earnings key repair, PIT EPS estimate
revision momentum can qualify existing A/B candidates.

If that alpha is still data-limited, pivot to the strongest non-LLM,
non-earnings-C candidate-pool lead already in the record: liquidity-gated 10-K
filing scouts from exp-20260503-011. This script writes a concise, reproducible
decision artifact and does not alter entries, ranking, sizing, exits, universe,
LLM/news, or production adapters.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))


EXPERIMENT_ID = "exp-20260508-011"
STEM = "alpha_direction_triage"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

SEC_10K_SOURCE = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260503-011"
    / "sec_10k_liquidity_shadow_scout.json"
)
SOURCE_CANDIDATE_EVENTS = REPO_ROOT / "data" / "experiments" / "exp-20260507-013"

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "candidate_events": SOURCE_CANDIDATE_EVENTS
                / "entry_candidate_events_late_strong.json",
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "candidate_events": SOURCE_CANDIDATE_EVENTS
                / "entry_candidate_events_mid_weak.json",
                "state_note": "rotation-heavy bull where strategy makes money but can lag indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "candidate_events": SOURCE_CANDIDATE_EVENTS
                / "entry_candidate_events_old_thin.json",
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)

BASELINE = {
    "late_strong": {
        "expected_value_score": 3.7435,
        "sharpe_daily": 4.48,
        "max_drawdown_pct": 0.0539,
        "total_pnl": 83562.53,
        "strategy_total_return_pct": 0.8356,
        "win_rate": 0.7895,
        "total_trades": 19,
        "survival_rate": 0.8039,
    },
    "mid_weak": {
        "expected_value_score": 1.5478,
        "sharpe_daily": 2.69,
        "max_drawdown_pct": 0.0879,
        "total_pnl": 57542.74,
        "strategy_total_return_pct": 0.5754,
        "win_rate": 0.5238,
        "total_trades": 21,
        "survival_rate": 0.7925,
    },
    "old_thin": {
        "expected_value_score": 0.3359,
        "sharpe_daily": 1.28,
        "max_drawdown_pct": 0.0905,
        "total_pnl": 26242.68,
        "strategy_total_return_pct": 0.2624,
        "win_rate": 0.4091,
        "total_trades": 22,
        "survival_rate": 0.9167,
    },
}


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8-sig") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n")


def _repo_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def _float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _add_business_days(date_str: str, days: int) -> str:
    date = datetime.strptime(date_str, "%Y-%m-%d").date()
    remaining = int(days)
    step = 1 if remaining >= 0 else -1
    remaining = abs(remaining)
    while remaining:
        date += timedelta(days=step)
        if date.weekday() < 5:
            remaining -= 1
    return date.isoformat()


def _snapshot_date(path: Path) -> str | None:
    suffix = path.stem.replace("earnings_snapshot_", "")
    if len(suffix) != 8 or not suffix.isdigit():
        return None
    return f"{suffix[:4]}-{suffix[4:6]}-{suffix[6:]}"


def _candidate_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = _load_json(path)
    rows = payload.get("candidate_events") if isinstance(payload, dict) else []
    return rows if isinstance(rows, list) else []


def _estimate_revision_audit() -> dict[str, Any]:
    rows_by_window: dict[str, dict[str, Any]] = OrderedDict()
    all_revision_records: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for window, spec in WINDOWS.items():
        start = spec["start"]
        end = spec["end"]
        event_series: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        file_count = 0
        total_rows = 0
        eps_rows = 0
        usable_rows = 0
        dte0_or_dte1_rows = 0

        for path in sorted((REPO_ROOT / "data").glob("earnings_snapshot_*.json")):
            date_str = _snapshot_date(path)
            if not date_str or not (start <= date_str <= end):
                continue
            file_count += 1
            payload = _load_json(path)
            earnings = payload.get("earnings") if isinstance(payload, dict) else {}
            if not isinstance(earnings, dict):
                continue
            for ticker, raw in earnings.items():
                if not isinstance(raw, dict):
                    continue
                total_rows += 1
                eps = _float(raw.get("eps_estimate"))
                dte = _float(raw.get("days_to_earnings"))
                if eps is None:
                    continue
                eps_rows += 1
                if dte is None:
                    continue
                dte_int = int(dte)
                if dte_int <= 1:
                    dte0_or_dte1_rows += 1
                    continue
                next_date = _add_business_days(date_str, dte_int)
                usable_rows += 1
                event_series[(str(ticker).upper(), next_date)].append(
                    {
                        "snapshot_date": date_str,
                        "ticker": str(ticker).upper(),
                        "next_earnings_date": next_date,
                        "days_to_earnings": dte_int,
                        "eps_estimate": eps,
                    }
                )

        revision_steps = []
        revision_event_keys = set()
        for key, records in event_series.items():
            ordered = sorted(records, key=lambda row: row["snapshot_date"])
            for before, after in zip(ordered, ordered[1:]):
                before_eps = before["eps_estimate"]
                after_eps = after["eps_estimate"]
                if abs(after_eps - before_eps) <= 1e-9:
                    continue
                denominator = abs(before_eps) if abs(before_eps) > 1e-9 else 1.0
                revision = {
                    "window": window,
                    "ticker": after["ticker"],
                    "revision_date": after["snapshot_date"],
                    "next_earnings_date": after["next_earnings_date"],
                    "days_to_earnings": after["days_to_earnings"],
                    "previous_eps_estimate": round(before_eps, 6),
                    "eps_estimate": round(after_eps, 6),
                    "revision_abs": round(after_eps - before_eps, 6),
                    "revision_pct": round((after_eps - before_eps) / denominator, 6),
                }
                revision_steps.append(revision)
                revision_event_keys.add(key)
                all_revision_records[window].append(revision)

        candidates = _candidate_rows(spec["candidate_events"])
        recent_revision_by_ticker_date: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for revision in revision_steps:
            recent_revision_by_ticker_date[
                (revision["ticker"], revision["revision_date"])
            ].append(revision)

        touched_candidates = []
        for candidate in candidates:
            ticker = str(candidate.get("ticker") or "").upper()
            candidate_date = str(candidate.get("date") or "")[:10]
            if not ticker or not candidate_date:
                continue
            # Use same-day or last five calendar days. This is intentionally
            # conservative and PIT-safe for a daily batch process.
            for offset in range(0, 6):
                probe_date = (
                    datetime.strptime(candidate_date, "%Y-%m-%d").date()
                    - timedelta(days=offset)
                ).isoformat()
                revisions = recent_revision_by_ticker_date.get((ticker, probe_date))
                if not revisions:
                    continue
                touched_candidates.append(
                    {
                        "date": candidate_date,
                        "ticker": ticker,
                        "strategy": candidate.get("strategy"),
                        "decision": candidate.get("decision"),
                        "revision_count": len(revisions),
                        "latest_revision": revisions[-1],
                    }
                )
                break

        rows_by_window[window] = {
            "start": start,
            "end": end,
            "snapshot_files": file_count,
            "earnings_rows": total_rows,
            "eps_estimate_rows": eps_rows,
            "usable_non_event_day_rows": usable_rows,
            "dte0_or_dte1_rows_excluded": dte0_or_dte1_rows,
            "same_event_keys": len(event_series),
            "revision_steps": len(revision_steps),
            "revision_event_keys": len(revision_event_keys),
            "candidate_rows_checked": len(candidates),
            "candidate_rows_with_recent_revision": len(touched_candidates),
            "candidate_touch_sample": touched_candidates[:10],
            "state_note": spec["state_note"],
        }

    revision_windows = [
        window
        for window, row in rows_by_window.items()
        if row["revision_steps"] > 0
    ]
    candidate_touch_windows = [
        window
        for window, row in rows_by_window.items()
        if row["candidate_rows_with_recent_revision"] > 0
    ]
    return {
        "hypothesis": (
            "PIT EPS estimate revisions can qualify existing A/B candidates "
            "after same-event key repair."
        ),
        "decision": "blocked_not_promoted",
        "rows": rows_by_window,
        "aggregate": {
            "windows_with_revision_steps": revision_windows,
            "windows_with_candidate_touches": candidate_touch_windows,
            "revision_steps_sum": sum(row["revision_steps"] for row in rows_by_window.values()),
            "candidate_touch_sum": sum(
                row["candidate_rows_with_recent_revision"]
                for row in rows_by_window.values()
            ),
        },
        "blocker": (
            "Estimate revisions are not yet a reliable three-window alpha "
            "input: mid_weak and old_thin have zero non-event-day revision "
            "steps, and candidate overlap is too sparse for promotion."
        ),
    }


def _sec_10k_direction_review() -> dict[str, Any]:
    payload = _load_json(SEC_10K_SOURCE)
    shadow = payload.get("shadow_metrics") or {}
    by_window = shadow.get("by_window") or {}
    rows = OrderedDict()
    for window in WINDOWS:
        metrics = by_window.get(window) or {}
        forward = metrics.get("forward_distribution") or {}
        ten_day = forward.get("10d") or {}
        rows[window] = {
            "candidate_count": metrics.get("candidate_count"),
            "ten_day_return_avg": (ten_day.get("return") or {}).get("avg"),
            "ten_day_excess_avg": (ten_day.get("excess_return") or {}).get("avg"),
            "ten_day_excess_win_rate": (ten_day.get("excess_return") or {}).get(
                "win_rate"
            ),
            "ten_day_excess_count": (ten_day.get("excess_return") or {}).get("count"),
            "state_note": WINDOWS[window]["state_note"],
        }
    slot_conflict = shadow.get("slot_conflict") or {}
    return {
        "source_experiment": "exp-20260503-011",
        "hypothesis": (
            "Liquidity-gated outside-universe 10-K filings can improve the "
            "candidate pool if they beat same-day A/B alternatives."
        ),
        "decision": "best_next_forward_alpha_direction_not_promoted",
        "rows": rows,
        "slot_conflict": {
            "same_day_core_conflict_count": slot_conflict.get(
                "same_day_core_conflict_count"
            ),
            "same_day_core_conflict_rate": slot_conflict.get(
                "same_day_core_conflict_rate"
            ),
            "replacement_value_10d_excess_proxy": slot_conflict.get(
                "replacement_value_10d_excess_proxy"
            ),
        },
        "interpretation": (
            "This is stronger than the estimate-revision path today because it "
            "has positive old/late 10d excess and positive same-day replacement "
            "proxy, but it is not production-ready: mid_weak has only one "
            "negative candidate and the source remains shadow/PIT-observation "
            "rather than a frozen forward entry queue with enough closed outcomes."
        ),
        "next_evidence_required": [
            "append-only PIT 10-K eligibility ledger",
            "frozen same-day A/B alternatives before entry",
            "closed forward replacement-value outcomes across at least two regimes",
        ],
    }


def _baseline_after_no_change() -> dict[str, Any]:
    return {window: dict(metrics) for window, metrics in BASELINE.items()}


def _experiment_payload() -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    estimate_revision = _estimate_revision_audit()
    sec_10k = _sec_10k_direction_review()
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": "completed",
        "decision": "no_production_change",
        "lane": "alpha_search",
        "change_type": "alpha_direction_triage",
        "alpha_hypothesis_category": "candidate_pool / event_quality",
        "hypothesis": (
            "Prefer a replayable alpha direction over another local sizing or "
            "threshold tweak: test analyst-revision readiness first, then "
            "compare the current best candidate-pool lead."
        ),
        "parameters": {
            "single_executable_policy_changed": False,
            "estimate_revision_min_days_to_earnings": 2,
            "candidate_revision_lookback_calendar_days": 5,
            "sec_10k_source_experiment": "exp-20260503-011",
            "locked_variables": [
                "signal generation",
                "entry filters",
                "candidate ranking",
                "sizing",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "exits",
                "gap cancels",
                "add-ons",
                "LLM/news replay",
                "production universe",
            ],
        },
        "date_range": {
            window: f"{spec['start']} -> {spec['end']}"
            for window, spec in WINDOWS.items()
        },
        "market_regime_summary": {
            window: spec["state_note"] for window, spec in WINDOWS.items()
        },
        "before_metrics": _baseline_after_no_change(),
        "after_metrics": _baseline_after_no_change(),
        "expected_value_score_delta": {
            "late_strong": 0.0,
            "mid_weak": 0.0,
            "old_thin": 0.0,
            "aggregate": 0.0,
        },
        "gate4": {
            "passed": False,
            "basis": (
                "No strategy change was promoted. Core metrics are unchanged; "
                "the estimate-revision alpha is coverage-blocked, and the 10-K "
                "candidate-pool lead needs forward/PIT outcomes before live use."
            ),
        },
        "estimate_revision_audit": estimate_revision,
        "sec_10k_direction_review": sec_10k,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "production_impact": "none; no executable strategy rule changed",
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft-ranking remains sample-limited, so this run used "
                "deterministic PIT/non-OHLCV alpha diagnostics instead."
            ),
        },
        "history_guardrails": {
            "not_repeating_recent_rejections": [
                "no earnings C re-enable",
                "no event bundle same-sample retune",
                "no platform RS20/no-gap promotion",
                "no gap-cancel BB-width retry",
                "no nearby risk_on/sector sizing scalar",
                "no zero-risk sleeve reactivation",
            ],
            "why_this_is_not_a_simple_repeat": (
                "The estimate-revision audit uses the newly repaired same-event "
                "key from exp-20260508-006, then pivots away when the data is "
                "not three-window usable."
            ),
        },
        "conclusion": {
            "current_best_alpha_direction": (
                "candidate-pool expansion through liquidity-gated 10-K filing "
                "scouts, but only via forward/PIT observation and replacement "
                "value, not immediate core promotion"
            ),
            "rejected_now": (
                "analyst EPS estimate revision as an existing-candidate ranking "
                "field; it lacks stable mid/old-window revision coverage"
            ),
            "do_not_do_next": (
                "Do not retune local risk multipliers or event-bundle thresholds "
                "while stronger directions need forward candidate evidence."
            ),
        },
        "related_files": [
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(SEC_10K_SOURCE),
        ],
    }


def _write_artifact(payload: dict[str, Any]) -> None:
    rev = payload["estimate_revision_audit"]
    sec = payload["sec_10k_direction_review"]
    lines = [
        f"# {EXPERIMENT_ID} Alpha Direction Triage",
        "",
        "## Decision",
        "",
        "`no_production_change`. This was an alpha-search triage run, not a bug fix.",
        "",
        "Analyst estimate revisions are still not usable as a three-window alpha input. "
        "The stronger current direction is candidate-pool expansion through liquidity-gated "
        "10-K filing scouts, but only as forward/PIT observation until closed replacement-value "
        "outcomes exist.",
        "",
        "## Three-Window Core Metrics",
        "",
        "| Window | EV before | EV after | Sharpe daily | PnL | Max DD | Win rate | Trades |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for window, metrics in BASELINE.items():
        lines.append(
            "| {window} | {ev:.4f} | {ev:.4f} | {sharpe:.2f} | {pnl:.2f} | {dd:.2%} | {win:.2%} | {trades} |".format(
                window=window,
                ev=metrics["expected_value_score"],
                sharpe=metrics["sharpe_daily"],
                pnl=metrics["total_pnl"],
                dd=metrics["max_drawdown_pct"],
                win=metrics["win_rate"],
                trades=metrics["total_trades"],
            )
        )
    lines.extend(
        [
            "",
            "No executable rule changed, so before/after core metrics are intentionally identical.",
            "",
            "## Estimate Revision Audit",
            "",
            "| Window | Snapshot files | Usable rows | Revision steps | Candidate touches |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for window, row in rev["rows"].items():
        lines.append(
            f"| {window} | {row['snapshot_files']} | {row['usable_non_event_day_rows']} | "
            f"{row['revision_steps']} | {row['candidate_rows_with_recent_revision']} |"
        )
    lines.extend(
        [
            "",
            f"Blocker: {rev['blocker']}",
            "",
            "## 10-K Candidate-Pool Review",
            "",
            "| Window | Candidates | 10d excess avg | 10d excess win rate |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for window, row in sec["rows"].items():
        count = row.get("candidate_count")
        avg = row.get("ten_day_excess_avg")
        win = row.get("ten_day_excess_win_rate")
        lines.append(
            f"| {window} | {count} | {avg if avg is not None else 'n/a'} | "
            f"{win if win is not None else 'n/a'} |"
        )
    slot = sec["slot_conflict"]
    lines.extend(
        [
            "",
            "Same-day A/B conflict sample: "
            f"{slot.get('same_day_core_conflict_count')} conflicts, "
            f"{slot.get('same_day_core_conflict_rate')} conflict rate.",
            "",
            f"Interpretation: {sec['interpretation']}",
            "",
            "## Production Parity",
            "",
            "No shared policy, backtester adapter, run adapter, entry, ranking, sizing, "
            "exit, LLM, or universe code changed. A future positive 10-K rule must be "
            "implemented through a shared policy/adapter before live use.",
            "",
        ]
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    payload = _experiment_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "title": "Alpha direction triage",
        "status": payload["decision"],
        "summary": payload["conclusion"],
        "next_action": payload["sec_10k_direction_review"]["next_evidence_required"],
    }
    _write_json(TICKET_JSON, ticket)
    _write_artifact(payload)
    _append_jsonl(EXPERIMENT_LOG, payload)
    print(json.dumps(payload["conclusion"], ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
