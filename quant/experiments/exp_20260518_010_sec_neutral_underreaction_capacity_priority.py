"""exp-20260518-010: SEC neutral-underreaction capacity priority.

Alpha search on one causal variable: within the accepted default-off SEC
financial-report T+1 paper sleeve, prioritize the already accepted
neutral-underreaction cohort when pending entries compete for the same paper
capacity. Candidate eligibility, notional rules, hold days, max positions,
core strategy, and live orders remain unchanged.

No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260518-010"
STEM = "exp_20260518_010_sec_neutral_underreaction_capacity_priority"
REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260516_033_sec_financial_report_neutral_language_notional as parent  # noqa: E402
import exp_20260518_009_sec_neutral_underreaction_notional as accepted  # noqa: E402
import sec_financial_report_event_sleeve as sleeve  # noqa: E402


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
DOC_LOG = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_ARTIFACT = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_sec_neutral_underreaction_capacity_priority.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

ACCEPTED_T1_EXCESS_MAX = 0.02
MIN_TARGET_TRADES = 6
MIN_WINDOWS_PRESENT = 3
MAX_DRAWDOWN_WORSENING = 0.005


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00",
        "Z",
    )


def _safe(value: Any) -> Any:
    return parent._safe(value)


def _round(value: Any, ndigits: int = 6) -> float | None:
    return parent._round(value, ndigits)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    compact = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                rows.append(line)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(compact)
                    replaced = True
                continue
            rows.append(line)
    if not replaced:
        rows.append(compact)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _candidate_is_accepted_neutral_underreaction(candidate: dict[str, Any]) -> bool:
    position = {"source_candidate": candidate}
    return accepted._is_neutral_underreaction_position(
        position,
        max_t1_excess=ACCEPTED_T1_EXCESS_MAX,
        base_neutral_predicate=parent._is_neutral_language_position,
    )


def _target_first_pending_sort_key(entry: dict[str, Any]) -> tuple[str, int, float, str]:
    candidate = entry.get("candidate") or {}
    target_priority = 0 if _candidate_is_accepted_neutral_underreaction(candidate) else 1
    try:
        t1_excess = float(candidate.get("t1_excess_return_vs_spy") or 0.0)
    except (TypeError, ValueError):
        t1_excess = 0.0
    return (
        str(entry.get("created_asof") or ""),
        target_priority,
        -t1_excess,
        str(entry.get("ticker") or ""),
    )


def _with_priority_sort(fn):
    original = sleeve._pending_sort_key
    sleeve._pending_sort_key = _target_first_pending_sort_key
    try:
        return fn()
    finally:
        sleeve._pending_sort_key = original


def _run_current_policy(
    *,
    core_results: dict[str, dict[str, Any]],
    exp100: dict[str, Any],
) -> dict[str, Any]:
    return accepted._run_variant(
        core_results=core_results,
        exp100=exp100,
        max_t1_excess=ACCEPTED_T1_EXCESS_MAX,
    )


def _run_priority_policy(
    *,
    core_results: dict[str, dict[str, Any]],
    exp100: dict[str, Any],
) -> dict[str, Any]:
    return _with_priority_sort(
        lambda: accepted._run_variant(
            core_results=core_results,
            exp100=exp100,
            max_t1_excess=ACCEPTED_T1_EXCESS_MAX,
        )
    )


def _target_positions(
    exp100: dict[str, Any],
    *,
    priority_sort: bool,
) -> list[dict[str, Any]]:
    runner = lambda: accepted._target_positions_for_variant(
        exp100,
        max_t1_excess=ACCEPTED_T1_EXCESS_MAX,
    )
    return _with_priority_sort(runner) if priority_sort else runner()


def _selection_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_window = Counter(str(row["window"]) for row in rows)
    by_ticker = Counter(str(row["ticker"]) for row in rows)
    pnl_by_window: dict[str, float] = {}
    pnl_by_ticker: dict[str, float] = {}
    positive_incremental: list[float] = []
    for row in rows:
        pnl = float(row.get("incremental_pnl") or 0.0)
        pnl_by_window[str(row["window"])] = pnl_by_window.get(str(row["window"]), 0.0) + pnl
        pnl_by_ticker[str(row["ticker"])] = pnl_by_ticker.get(str(row["ticker"]), 0.0) + pnl
        if pnl > 0:
            positive_incremental.append(pnl)
    positive_total = sum(positive_incremental)
    max_positive = max(positive_incremental) if positive_incremental else 0.0
    return {
        "adjusted_trade_count": len(rows),
        "windows_present": len(by_window),
        "by_window_count": dict(sorted(by_window.items())),
        "by_window_incremental_pnl": {
            key: _round(value, 2) for key, value in sorted(pnl_by_window.items())
        },
        "by_ticker_count": dict(sorted(by_ticker.items())),
        "by_ticker_incremental_pnl": {
            key: _round(value, 2) for key, value in sorted(pnl_by_ticker.items())
        },
        "max_single_positive_incremental_pnl": _round(max_positive, 2),
        "max_single_positive_pnl_share": (
            _round(max_positive / positive_total, 4) if positive_total > 0 else None
        ),
        "positive_incremental_pnl": _round(positive_total, 2),
        "sample_rows": rows[:30],
    }


def _row_key(row: dict[str, Any]) -> str:
    return "|".join(
        [
            str(row.get("window") or ""),
            str(row.get("ticker") or ""),
            str(row.get("entry_date") or ""),
            str(row.get("exit_date") or ""),
            str(row.get("event_family") or ""),
        ]
    )


def _selection_diff(
    before_rows: list[dict[str, Any]],
    after_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    before = {_row_key(row): row for row in before_rows}
    after = {_row_key(row): row for row in after_rows}
    added = [after[key] for key in sorted(set(after) - set(before))]
    removed = [before[key] for key in sorted(set(before) - set(after))]
    common = sorted(set(before) & set(after))
    return {
        "added_target_rows": added,
        "removed_target_rows": removed,
        "common_target_count": len(common),
        "added_count": len(added),
        "removed_count": len(removed),
    }


def _window_deltas(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    checks = {}
    for label in parent.WINDOWS:
        after_m = after["by_window"][label]["combined_metrics"]
        before_m = before["by_window"][label]["combined_metrics"]
        after_sleeve = after["by_window"][label]["sleeve_metrics"]
        before_sleeve = before["by_window"][label]["sleeve_metrics"]
        checks[label] = {
            "ev_delta": _round(
                float(after_m["expected_value_score"])
                - float(before_m["expected_value_score"]),
                6,
            ),
            "pnl_delta": _round(
                float(after_m["total_pnl"]) - float(before_m["total_pnl"]),
                2,
            ),
            "max_drawdown_delta": _round(
                float(after_m["max_drawdown_pct"])
                - float(before_m["max_drawdown_pct"]),
                6,
            ),
            "sleeve_trade_count_delta": int(
                after_sleeve.get("closed_trade_count") or 0
            )
            - int(before_sleeve.get("closed_trade_count") or 0),
            "neutral_underreaction_closed_trade_count": int(
                after_sleeve.get("neutral_language_closed_trade_count") or 0
            ),
            "neutral_underreaction_pnl_delta": _round(
                float(after_sleeve.get("neutral_language_total_pnl") or 0.0)
                - float(before_sleeve.get("neutral_language_total_pnl") or 0.0),
                2,
            ),
        }
    return checks


def _gate(
    *,
    after: dict[str, Any],
    before: dict[str, Any],
    selection: dict[str, Any],
) -> dict[str, Any]:
    aggregate_delta = parent._delta(after["aggregate"], before["aggregate"])
    checks = _window_deltas(after, before)
    ev_positive_windows = sum(1 for row in checks.values() if row["ev_delta"] > 0)
    ev_regressed_windows = sum(1 for row in checks.values() if row["ev_delta"] < 0)
    pnl_positive_windows = sum(1 for row in checks.values() if row["pnl_delta"] > 0)
    pnl_regressed_windows = sum(1 for row in checks.values() if row["pnl_delta"] < 0)
    max_drawdown_delta_max = max(row["max_drawdown_delta"] for row in checks.values())
    sample_guard_passed = (
        selection["adjusted_trade_count"] >= MIN_TARGET_TRADES
        and selection["windows_present"] >= MIN_WINDOWS_PRESENT
    )
    metric_gate_passed = (
        (aggregate_delta.get("expected_value_score_sum_delta") or 0.0) > 0
        and (aggregate_delta.get("total_pnl_sum_delta") or 0.0) > 0.0
        and ev_positive_windows == 3
        and ev_regressed_windows == 0
        and pnl_positive_windows == 3
        and pnl_regressed_windows == 0
        and max_drawdown_delta_max <= MAX_DRAWDOWN_WORSENING
    )
    return {
        "aggregate_delta": aggregate_delta,
        "window_checks": checks,
        "metric_gate_passed": metric_gate_passed,
        "sample_guard_passed": sample_guard_passed,
        "passed": metric_gate_passed and sample_guard_passed,
        "ev_positive_windows": ev_positive_windows,
        "ev_regressed_windows": ev_regressed_windows,
        "pnl_positive_windows": pnl_positive_windows,
        "pnl_regressed_windows": pnl_regressed_windows,
        "max_drawdown_delta_max": _round(max_drawdown_delta_max, 6),
        "rule": (
            "Pass if aggregate EV/PnL improve versus exp-20260518-009, EV and "
            "PnL improve in all three fixed windows, no window regresses, max "
            "drawdown worsens by no more than 0.5 percentage points, target "
            f"neutral-underreaction trades >= {MIN_TARGET_TRADES}, and target "
            f"trades are present in all {MIN_WINDOWS_PRESENT} windows."
        ),
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} SEC Neutral-Underreaction Capacity Priority",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "## Gate 4",
        "",
        "```json",
        json.dumps(_safe(payload["gate"]), indent=2, sort_keys=True),
        "```",
        "",
        "## Selection Diff",
        "",
        "```json",
        json.dumps(_safe(payload["selection_diff"]), indent=2, sort_keys=True),
        "```",
        "",
        "No JavaScript was used.",
        "",
    ]
    return "\n".join(lines)


def build_payload() -> dict[str, Any]:
    timestamp = _utc_now()
    raw_exp100 = parent._load_exp100()
    current_queue = parent._filter_current_queue(raw_exp100)
    text_rows_by_accession, text_load_stats = parent._load_text_rows()
    exp100 = parent._annotate_language_fields(current_queue, text_rows_by_accession)
    text_coverage = parent._text_coverage_summary(exp100)
    gate2_fields = parent._gate2_open_position_field_check()

    core_results: dict[str, dict[str, Any]] = {}
    for label, window in parent.WINDOWS.items():
        result = parent._run_core_backtest(window)
        core_results[label] = {
            "metrics": parent._core_metrics(result),
            "equity_curve": parent._normalise_core_curve(result),
        }

    baseline = _run_current_policy(core_results=core_results, exp100=exp100)
    after = _run_priority_policy(core_results=core_results, exp100=exp100)
    before_rows = _target_positions(exp100, priority_sort=False)
    after_rows = _target_positions(exp100, priority_sort=True)
    selection = _selection_summary(after_rows)
    diff = _selection_diff(before_rows, after_rows)
    gate = _gate(after=after, before=baseline, selection=selection)

    status = "accepted" if gate["passed"] else "rejected"
    decision = (
        "accepted_default_off_sec_neutral_underreaction_capacity_priority"
        if gate["passed"]
        else "rejected_sec_neutral_underreaction_capacity_priority"
    )
    interpretation = (
        "The accepted SEC neutral-underreaction sleeve has a capacity-priority edge: "
        "when paper slots are scarce, filling neutral-underreaction rows before other "
        "financial-report T+1 rows improves all three fixed windows while remaining "
        "default-off paper only."
        if gate["passed"]
        else "Prioritizing neutral-underreaction rows in SEC paper capacity did not "
        "clear the three-window no-regression gate versus exp-20260518-009."
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "lane": "alpha_search",
        "hypothesis": (
            "The accepted neutral-underreaction SEC financial-report paper cohort is "
            "being under-allocated when max_positions capacity is full, because the "
            "current pending-entry sort still favors higher T+1 excess rows. Giving "
            "the accepted neutral-underreaction cohort capacity priority should improve "
            "replacement value without changing candidate eligibility or notional."
        ),
        "change_summary": (
            "Replay SEC financial-report paper sleeve with accepted neutral-underreaction "
            "pending entries sorted ahead of non-target entries under capacity pressure."
        ),
        "change_type": "alpha_search_sec_paper_capacity_priority",
        "component": "quant/sec_financial_report_event_sleeve.py",
        "changed_variable": "sec_neutral_underreaction_capacity_priority",
        "single_causal_variable": (
            "pending-entry capacity priority for the accepted neutral-underreaction "
            "SEC financial-report paper cohort"
        ),
        "parameters": {
            "baseline": "exp-20260518-009 accepted neutral-underreaction notional policy",
            "accepted_neutral_underreaction_max_t1_excess": ACCEPTED_T1_EXCESS_MAX,
            "neutral_underreaction_notional_scalar": accepted.FIXED_NEUTRAL_SCALAR,
            "capacity_priority": (
                "same created_asof; accepted neutral-underreaction candidates first; "
                "then higher t1_excess_return_vs_spy; then ticker"
            ),
            "base_event_notional_usd": parent.DEFAULT_EVENT_NOTIONAL_USD,
            "periodic_report_scalar": parent.DEFAULT_PERIODIC_REPORT_NOTIONAL_SCALAR,
            "tenq_periodic_report_scalar": parent.ACCEPTED_10Q_PERIODIC_REPORT_SCALAR,
            "max_positions": parent.DEFAULT_MAX_POSITIONS,
            "source_candidate_artifact": str(parent.SOURCE_EXP100_JSON.relative_to(REPO_ROOT)),
            "text_archive": str(parent.TEXT_ARCHIVE_JSONL.relative_to(REPO_ROOT)),
            "anti_js": "No JavaScript was used.",
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows for core baseline, "
            "plus production SEC financial-report paper-sleeve replay over the same snapshots."
        ),
        "windows": parent.WINDOWS,
        "text_load_stats": text_load_stats,
        "text_coverage_summary": text_coverage,
        "gate2_required_fields": gate2_fields,
        "before_metrics": baseline["aggregate"],
        "after_metrics": after["aggregate"],
        "delta_metrics": {
            "aggregate": gate["aggregate_delta"],
            "by_window": gate["window_checks"],
        },
        "expected_value_score_delta": gate["aggregate_delta"].get(
            "expected_value_score_sum_delta"
        ),
        "total_pnl_delta": gate["aggregate_delta"].get("total_pnl_sum_delta"),
        "selection_before": _selection_summary(before_rows),
        "selection_after": selection,
        "selection_diff": diff,
        "gate": gate,
        "interpretation": interpretation,
        "rejection_reason": None if gate["passed"] else interpretation,
        "next_evidence_needed": (
            "Promote the priority into shared sec_financial_report_event_sleeve.py, "
            "add parity tests, keep live/default orders disabled, and collect closed "
            "forward replacement-value evidence before any trade-enabled adapter."
            if gate["passed"]
            else "Keep exp-20260518-009 capacity order unchanged. Future SEC work should "
            "use a new semantic field or forward replacement-value evidence rather than "
            "another capacity priority variation on this frozen sample."
        ),
        "production_impact": {
            "shared_policy_changed": gate["passed"],
            "backtester_adapter_changed": False,
            "run_adapter_changed": gate["passed"],
            "replay_only": False,
            "parity_test_added": gate["passed"],
            "default_off_paper_only": True,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": True,
            "alters_sizing": False,
            "shared_policy_file": "quant/sec_financial_report_event_sleeve.py",
            "parity_test_file": "quant/test_sec_financial_report_event_sleeve.py",
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": (
                "LLM soft-ranking remains sparse; this deterministic SEC paper-ranking "
                "test uses archived filing language buckets and OHLCV T+1 reaction."
            ),
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "ranking/capital allocation: prioritize the accepted SEC neutral-"
                "underreaction paper rows when default-off sleeve capacity is scarce."
            ),
            "2_history_check": (
                "exp-20260518-009 accepted the neutral-underreaction notional scalar; "
                "nearby T+1 caps above 2% regressed late_strong. No prior run changed "
                "capacity fill priority while keeping the accepted underreaction cap "
                "and notional fixed."
            ),
            "3_single_causal_variable": "sec_neutral_underreaction_capacity_priority",
            "4_acceptance_standard": gate["rule"],
            "5_reproducibility": (
                f".venv\\Scripts\\python.exe quant\\experiments\\{STEM}.py"
            ),
        },
        "why_not_other_changes": (
            "State-surface profile retunes are anti-repeat without a new field, event "
            "rotation needs forward maturation, and LLM soft-ranking is sample-limited. "
            "This tests one production-visible SEC paper capacity variable instead of "
            "adding noisy tickers or changing live core logic."
        ),
        "related_files": [
            f"quant/experiments/{STEM}.py",
            "quant/sec_financial_report_event_sleeve.py",
            "quant/test_sec_financial_report_event_sleeve.py",
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(DOC_LOG.relative_to(REPO_ROOT)),
            str(DOC_TICKET.relative_to(REPO_ROOT)),
            str(DOC_ARTIFACT.relative_to(REPO_ROOT)),
            str(EXPERIMENT_LOG_JSONL.relative_to(REPO_ROOT)),
        ],
    }


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(DOC_LOG, payload)
    _write_json(
        DOC_TICKET,
        {
            "experiment_id": EXPERIMENT_ID,
            "lane": "alpha_search",
            "owner": "alpha-search",
            "status": payload["status"],
            "decision": payload["decision"],
            "single_causal_variable": payload["single_causal_variable"],
            "expected_value_score_delta": payload["expected_value_score_delta"],
            "total_pnl_delta": payload["total_pnl_delta"],
            "artifact_file": str(OUT_JSON.relative_to(REPO_ROOT)),
            "result_file": str(DOC_LOG.relative_to(REPO_ROOT)),
            "updated_at": payload["timestamp"],
        },
    )
    DOC_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT.write_text(_artifact_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG_JSONL, payload)


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "aggregate_ev_delta": payload["expected_value_score_delta"],
                    "aggregate_pnl_delta": payload["total_pnl_delta"],
                    "gate_passed": payload["gate"]["passed"],
                    "window_checks": payload["gate"]["window_checks"],
                    "selection_after": payload["selection_after"],
                    "selection_diff": payload["selection_diff"],
                    "anti_js": payload["parameters"]["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
