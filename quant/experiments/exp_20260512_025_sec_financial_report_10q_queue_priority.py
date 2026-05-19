"""exp-20260512-025: SEC financial-report 10-Q queue priority.

Alpha search on one causal variable: whether accepted SEC financial-report
10-Q candidates should be filled before other same-day paper candidates inside
the default-off T+1 sleeve. Queue qualification, max positions, notional,
hold days, live orders, and core A/B behavior stay fixed.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, OrderedDict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator


EXPERIMENT_ID = "exp-20260512-025"
STEM = "sec_financial_report_10q_queue_priority"
REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from exp_20260511_112_sec_financial_report_t1_sleeve_capacity import (  # noqa: E402
    SOURCE_EXP100_JSON,
    WINDOWS,
    _aggregate,
    _combine_curves,
    _core_metrics,
    _delta,
    _equity_metrics,
    _load_snapshot_prices,
    _normalise_core_curve,
    _rebuild_sleeve_state,
    _round,
    _rows_by_t1_date,
    _run_core_backtest,
    _safe,
    _write_json,
)
from exp_20260512_002_sec_financial_report_hold_days import (  # noqa: E402
    _filter_current_queue,
)
from sec_event_queue import FINANCIAL_REPORT_T1_MIN_EXCESS_RETURN_VS_SPY  # noqa: E402
from sec_financial_report_event_sleeve import (  # noqa: E402
    DEFAULT_EVENT_NOTIONAL_USD,
    DEFAULT_MAX_POSITIONS,
    DEFAULT_PERIODIC_REPORT_NOTIONAL_SCALAR,
    build_sec_financial_report_event_sleeve_snapshot,
    empty_sec_financial_report_event_sleeve_state,
)
import sec_financial_report_event_sleeve as sleeve_module  # noqa: E402


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
DOC_LOG = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_ARTIFACT = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

BASELINE_PRIORITY = "t1_excess_desc"
VARIANT_PRIORITY = "tenq_first_then_t1_excess"
QUEUE_PRIORITY_VARIANTS = (BASELINE_PRIORITY, VARIANT_PRIORITY)
TENQ_PERIODIC_REPORT_NOTIONAL_SCALAR = 2.0
MAX_DRAWDOWN_WORSENING = 0.005
MIN_SLEEVE_CLOSED_TRADES = 40
MIN_CHANGED_CLOSED_TRADE_COUNT = 1


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _append_jsonl_once(path: Path, payload: dict[str, Any]) -> None:
    compact = json.dumps(_safe(payload), ensure_ascii=False, separators=(",", ":"))
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        lines = [
            line
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if f'"experiment_id":"{EXPERIMENT_ID}"' not in line
            and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
        ]
    else:
        lines = []
    lines.append(compact)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _load_source_candidates() -> dict[str, Any]:
    return json.loads(SOURCE_EXP100_JSON.read_text(encoding="utf-8"))


def _candidate_counts(exp100: dict[str, Any]) -> dict[str, int]:
    return {
        label: len(window.get("candidate_rows") or [])
        for label, window in exp100.get("windows", {}).items()
    }


def _source_candidate(position_or_entry: dict[str, Any]) -> dict[str, Any]:
    candidate = position_or_entry.get("source_candidate")
    if not isinstance(candidate, dict):
        candidate = position_or_entry.get("candidate")
    return candidate if isinstance(candidate, dict) else position_or_entry


def _is_10q_periodic_candidate(candidate: dict[str, Any]) -> bool:
    family = str(candidate.get("event_family") or "")
    form = str(
        candidate.get("form_base")
        or candidate.get("form_type")
        or candidate.get("form")
        or candidate.get("sec_form")
        or ""
    ).upper()
    return family == "periodic_report" and form.startswith("10-Q")


def _event_family(position: dict[str, Any]) -> str:
    return str(_source_candidate(position).get("event_family") or "")


def _form_base(position: dict[str, Any]) -> str:
    candidate = _source_candidate(position)
    raw = (
        candidate.get("form_base")
        or candidate.get("form_type")
        or candidate.get("form")
        or candidate.get("sec_form")
        or ""
    )
    return str(raw).upper().strip() or "UNKNOWN"


def _notional_for_position(
    position: dict[str, Any],
    *,
    tenq_periodic_report_scalar: float,
) -> tuple[float, float, str]:
    base = float(DEFAULT_EVENT_NOTIONAL_USD)
    if _event_family(position) != "periodic_report":
        return base, 1.0, "base"
    if _form_base(position).startswith("10-Q"):
        scalar = float(tenq_periodic_report_scalar)
        return base * scalar, scalar, "periodic_report_10q_scalar"
    scalar = float(DEFAULT_PERIODIC_REPORT_NOTIONAL_SCALAR)
    return base * scalar, scalar, "periodic_report_default_scalar"


def _pnl_for_position(
    position: dict[str, Any],
    *,
    tenq_periodic_report_scalar: float,
    closed: bool,
) -> float:
    adjusted_notional, _, _ = _notional_for_position(
        position,
        tenq_periodic_report_scalar=tenq_periodic_report_scalar,
    )
    if closed:
        return adjusted_notional * (_float_or_zero(position.get("net_return_pct")) / 100.0)

    source_notional = _float_or_zero(position.get("notional"))
    source_pnl = _float_or_zero(position.get("net_pnl_if_closed_now"))
    if source_notional <= 0:
        return 0.0
    return adjusted_notional * (source_pnl / source_notional)


def _adjust_closed_position(
    position: dict[str, Any],
    *,
    tenq_periodic_report_scalar: float,
) -> dict[str, Any]:
    adjusted = dict(position)
    notional, scalar, rule = _notional_for_position(
        position,
        tenq_periodic_report_scalar=tenq_periodic_report_scalar,
    )
    adjusted["base_notional"] = float(DEFAULT_EVENT_NOTIONAL_USD)
    adjusted["notional"] = round(notional, 2)
    adjusted["event_notional_scalar"] = scalar
    adjusted["event_notional_rule"] = rule
    adjusted["form_base"] = _form_base(position)
    adjusted["tenq_periodic_report_notional_scalar"] = tenq_periodic_report_scalar
    adjusted["pnl"] = round(
        _pnl_for_position(
            position,
            tenq_periodic_report_scalar=tenq_periodic_report_scalar,
            closed=True,
        ),
        2,
    )
    return adjusted


def _closed_position_breakdown(
    closed_positions: list[dict[str, Any]],
) -> dict[str, Any]:
    count_by_form = Counter(str(item.get("form_base") or "UNKNOWN") for item in closed_positions)
    pnl_by_form: dict[str, float] = {}
    count_by_rule = Counter(
        str(item.get("event_notional_rule") or "UNKNOWN") for item in closed_positions
    )
    pnl_by_rule: dict[str, float] = {}
    for item in closed_positions:
        form = str(item.get("form_base") or "UNKNOWN")
        rule = str(item.get("event_notional_rule") or "UNKNOWN")
        pnl = float(item.get("pnl") or 0.0)
        pnl_by_form[form] = pnl_by_form.get(form, 0.0) + pnl
        pnl_by_rule[rule] = pnl_by_rule.get(rule, 0.0) + pnl
    return {
        "closed_trade_count_by_form_base": dict(sorted(count_by_form.items())),
        "closed_pnl_by_form_base": {
            key: _round(value, 2) for key, value in sorted(pnl_by_form.items())
        },
        "closed_trade_count_by_rule": dict(sorted(count_by_rule.items())),
        "closed_pnl_by_rule": {
            key: _round(value, 2) for key, value in sorted(pnl_by_rule.items())
        },
        "tenq_closed_trade_count": int(count_by_form.get("10-Q", 0)),
        "tenq_total_pnl": _round(pnl_by_form.get("10-Q", 0.0), 2),
    }


def _float_or_zero(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _tenq_candidate_sort_key(candidate: dict[str, Any]) -> tuple[int, float, str]:
    return (
        0 if _is_10q_periodic_candidate(candidate) else 1,
        -_float_or_zero(candidate.get("t1_excess_return_vs_spy")),
        str(candidate.get("ticker") or ""),
    )


def _tenq_pending_sort_key(entry: dict[str, Any]) -> tuple[str, int, float, str]:
    candidate = _source_candidate(entry)
    return (
        str(entry.get("created_asof") or ""),
        0 if _is_10q_periodic_candidate(candidate) else 1,
        -_float_or_zero(candidate.get("t1_excess_return_vs_spy")),
        str(entry.get("ticker") or ""),
    )


@contextmanager
def _queue_priority(priority: str) -> Iterator[None]:
    original_candidate_sort = sleeve_module._candidate_sort_key
    original_pending_sort = sleeve_module._pending_sort_key
    if priority == VARIANT_PRIORITY:
        sleeve_module._candidate_sort_key = _tenq_candidate_sort_key
        sleeve_module._pending_sort_key = _tenq_pending_sort_key
    try:
        yield
    finally:
        sleeve_module._candidate_sort_key = original_candidate_sort
        sleeve_module._pending_sort_key = original_pending_sort


def _closed_positions_changed(
    before: list[dict[str, Any]],
    after: list[dict[str, Any]],
) -> int:
    before_ids = {str(item.get("decision_id")) for item in before}
    after_ids = {str(item.get("decision_id")) for item in after}
    return len(before_ids.symmetric_difference(after_ids))


def _run_sleeve_replay(
    window_label: str,
    window: dict[str, str],
    window_payload: dict[str, Any],
    *,
    queue_priority: str,
) -> dict[str, Any]:
    prices_by_date = _load_snapshot_prices(window["snapshot"])
    candidates_by_t1 = _rows_by_t1_date(window_payload)
    state = empty_sec_financial_report_event_sleeve_state()
    skipped_entries: list[dict[str, Any]] = []
    pnl_by_date: OrderedDict[str, float] = OrderedDict()
    max_open_positions = 0
    max_gross_notional = 0.0
    enqueued_candidates = 0
    tenq_filled_count = 0

    with _queue_priority(queue_priority):
        for as_of, prices in prices_by_date.items():
            candidates = candidates_by_t1.get(as_of, [])
            enqueued_candidates += len(candidates)
            queue = {
                "queue_name": "SEC_FINANCIAL_REPORT_T1_DRIFT_QUEUE_REPLAY",
                "rule_version": f"{EXPERIMENT_ID}-{queue_priority}",
                "enabled": False,
                "asof_date": as_of,
                "candidate_count": len(candidates),
                "candidates": candidates,
                "data_source": {
                    "status": "replay",
                    "source_experiment": "exp-20260511-100",
                    "window": window_label,
                    "queue_priority": queue_priority,
                },
            }
            snapshot = build_sec_financial_report_event_sleeve_snapshot(
                sec_financial_report_t1_queue=queue,
                as_of=as_of,
                open_prices=prices["open"],
                current_prices=prices["close"],
                state=state,
                config={
                    "max_positions": DEFAULT_MAX_POSITIONS,
                    "event_notional_usd": DEFAULT_EVENT_NOTIONAL_USD,
                    "periodic_report_notional_scalar": (
                        DEFAULT_PERIODIC_REPORT_NOTIONAL_SCALAR
                    ),
                    "tenq_periodic_report_notional_scalar": (
                        TENQ_PERIODIC_REPORT_NOTIONAL_SCALAR
                    ),
                },
                persist=False,
            )
            skipped_entries.extend(snapshot.get("skipped_entries_today") or [])
            state = _rebuild_sleeve_state(snapshot, skipped_entries)
            tenq_filled_count += sum(
                1
                for item in snapshot.get("filled_entries") or []
                if _is_10q_periodic_candidate(_source_candidate(item))
            )
            realized = sum(
                _pnl_for_position(
                    item,
                    tenq_periodic_report_scalar=TENQ_PERIODIC_REPORT_NOTIONAL_SCALAR,
                    closed=True,
                )
                for item in state.get("closed_positions") or []
            )
            unrealized = sum(
                _pnl_for_position(
                    item,
                    tenq_periodic_report_scalar=TENQ_PERIODIC_REPORT_NOTIONAL_SCALAR,
                    closed=False,
                )
                for item in state.get("open_positions") or []
            )
            pnl_by_date[as_of] = realized + unrealized
            max_open_positions = max(
                max_open_positions,
                int(snapshot.get("open_position_count") or 0),
            )
            max_gross_notional = max(
                max_gross_notional,
                sum(
                    _notional_for_position(
                        item,
                        tenq_periodic_report_scalar=TENQ_PERIODIC_REPORT_NOTIONAL_SCALAR,
                    )[0]
                    for item in snapshot.get("open_positions") or []
                ),
            )

    closed_positions = [
        _adjust_closed_position(
            item,
            tenq_periodic_report_scalar=TENQ_PERIODIC_REPORT_NOTIONAL_SCALAR,
        )
        for item in state.get("closed_positions", [])
    ]
    standalone_metrics = _equity_metrics(
        list(pnl_by_date.items()),
        trade_count=len(closed_positions),
        win_rate=(
            sum(1 for item in closed_positions if float(item.get("pnl") or 0.0) > 0)
            / len(closed_positions)
            if closed_positions
            else None
        ),
        signals_generated=enqueued_candidates,
        signals_survived=enqueued_candidates,
    )
    standalone_metrics.update(
        {
            "closed_trade_count": len(closed_positions),
            "open_position_count_end": len(state.get("open_positions") or []),
            "pending_count_end": len(state.get("pending_entries") or []),
            "skipped_capacity_count": len(skipped_entries),
            "max_open_positions": max_open_positions,
            "max_gross_notional": _round(max_gross_notional, 2),
            "queue_priority": queue_priority,
            "tenq_filled_count": tenq_filled_count,
        }
    )
    standalone_metrics.update(_closed_position_breakdown(closed_positions))
    return {
        "closed_positions": closed_positions,
        "daily_pnl": list(pnl_by_date.items()),
        "metrics": standalone_metrics,
        "sample_closed_positions": closed_positions[:10],
    }


def _run_variant(
    *,
    core_results: dict[str, dict[str, Any]],
    exp100: dict[str, Any],
    queue_priority: str,
) -> dict[str, Any]:
    by_window = {}
    for label, window in WINDOWS.items():
        sleeve = _run_sleeve_replay(
            label,
            window,
            exp100["windows"][label],
            queue_priority=queue_priority,
        )
        core_curve = core_results[label]["equity_curve"]
        combined_curve = _combine_curves(core_curve, sleeve["daily_pnl"])
        core_metrics = core_results[label]["metrics"]
        combined_metrics = _equity_metrics(
            combined_curve,
            trade_count=int(core_metrics.get("trade_count") or 0)
            + int(sleeve["metrics"].get("closed_trade_count") or 0),
            win_rate=None,
            signals_generated=core_metrics.get("signals_generated"),
            signals_survived=core_metrics.get("signals_survived"),
        )
        by_window[label] = {
            "closed_positions": sleeve["closed_positions"],
            "combined_metrics": combined_metrics,
            "core_metrics": core_metrics,
            "sample_closed_positions": sleeve["sample_closed_positions"],
            "sleeve_metrics": sleeve["metrics"],
        }
    return {
        "aggregate": _aggregate(by_window),
        "by_window": by_window,
        "queue_priority": queue_priority,
    }


def _window_checks(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    checks = {}
    for label in WINDOWS:
        after_m = after["by_window"][label]["combined_metrics"]
        before_m = before["by_window"][label]["combined_metrics"]
        after_s = after["by_window"][label]["sleeve_metrics"]
        before_s = before["by_window"][label]["sleeve_metrics"]
        checks[label] = {
            "changed_closed_trade_count": _closed_positions_changed(
                before["by_window"][label]["closed_positions"],
                after["by_window"][label]["closed_positions"],
            ),
            "ev_delta": _round(
                float(after_m["expected_value_score"])
                - float(before_m["expected_value_score"]),
                6,
            ),
            "max_drawdown_delta": _round(
                float(after_m["max_drawdown_pct"])
                - float(before_m["max_drawdown_pct"]),
                6,
            ),
            "pnl_delta": _round(
                float(after_m["total_pnl"]) - float(before_m["total_pnl"]),
                2,
            ),
            "sleeve_pnl_delta": _round(
                float(after_s.get("total_pnl") or 0.0)
                - float(before_s.get("total_pnl") or 0.0),
                2,
            ),
            "tenq_closed_trade_count_after": int(
                after_s.get("closed_trade_count_by_form_base", {}).get("10-Q", 0)
            ),
            "tenq_total_pnl_after": _round(after_s.get("tenq_total_pnl"), 2),
        }
    return checks


def _gate(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    aggregate_delta = _delta(after["aggregate"], before["aggregate"])
    checks = _window_checks(after, before)
    ev_positive_windows = sum(1 for row in checks.values() if row["ev_delta"] > 0)
    ev_regressed_windows = sum(1 for row in checks.values() if row["ev_delta"] < 0)
    pnl_positive_windows = sum(1 for row in checks.values() if row["pnl_delta"] > 0)
    pnl_regressed_windows = sum(1 for row in checks.values() if row["pnl_delta"] < 0)
    changed_closed_trade_count = sum(
        row["changed_closed_trade_count"] for row in checks.values()
    )
    max_drawdown_delta_max = max(row["max_drawdown_delta"] for row in checks.values())
    sleeve_trades_after = int(after["aggregate"].get("sleeve_closed_trade_count_sum") or 0)
    passed = (
        (aggregate_delta.get("expected_value_score_sum_delta") or 0.0) > 0
        and (aggregate_delta.get("sleeve_total_pnl_sum_delta") or 0.0) > 0
        and ev_positive_windows >= 2
        and ev_regressed_windows == 0
        and pnl_positive_windows >= 2
        and pnl_regressed_windows == 0
        and max_drawdown_delta_max <= MAX_DRAWDOWN_WORSENING
        and sleeve_trades_after >= MIN_SLEEVE_CLOSED_TRADES
        and changed_closed_trade_count >= MIN_CHANGED_CLOSED_TRADE_COUNT
    )
    return {
        "aggregate_delta": aggregate_delta,
        "changed_closed_trade_count": changed_closed_trade_count,
        "ev_positive_windows": ev_positive_windows,
        "ev_regressed_windows": ev_regressed_windows,
        "max_drawdown_delta_max": _round(max_drawdown_delta_max, 6),
        "passed": passed,
        "pnl_positive_windows": pnl_positive_windows,
        "pnl_regressed_windows": pnl_regressed_windows,
        "rule": (
            "Pass if aggregate EV and sleeve PnL improve, at least two windows "
            "improve on EV/PnL, no window regresses on EV/PnL, max drawdown "
            "worsens by no more than 0.5 percentage points, sleeve closed "
            "trades >= 40, and at least one closed trade changes."
        ),
        "sleeve_closed_trade_count_after": sleeve_trades_after,
        "window_checks": checks,
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} SEC financial-report 10-Q queue priority",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- EV delta: `{payload['expected_value_score_delta']}`",
        (
            f"- Total PnL delta: "
            f"`{payload['gate']['aggregate_delta'].get('total_pnl_sum_delta')}`"
        ),
        (
            f"- Sleeve PnL delta: "
            f"`{payload['gate']['aggregate_delta'].get('sleeve_total_pnl_sum_delta')}`"
        ),
        f"- Changed closed trades: `{payload['gate']['changed_closed_trade_count']}`",
        "",
        "## Aggregate",
        "",
        "| Variant | EV sum | Total PnL | Sleeve PnL | Sleeve closed | Max DD max |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, row in payload["variants"].items():
        agg = row["aggregate"]
        lines.append(
            f"| {name} | {agg['expected_value_score_sum']:.6f} | "
            f"${agg['total_pnl_sum']:,.2f} | ${agg['sleeve_total_pnl_sum']:,.2f} | "
            f"{agg['sleeve_closed_trade_count_sum']} | {agg['max_drawdown_pct_max']:.4f} |"
        )
    lines.extend(["", "## Window Deltas", ""])
    lines.append(
        "| Window | EV delta | PnL delta | Sleeve PnL delta | Changed trades | Max DD delta |"
    )
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for label, row in payload["gate"]["window_checks"].items():
        lines.append(
            f"| {label} | {row['ev_delta']:.6f} | ${row['pnl_delta']:,.2f} | "
            f"${row['sleeve_pnl_delta']:,.2f} | {row['changed_closed_trade_count']} | "
            f"{row['max_drawdown_delta']:.6f} |"
        )
    lines.extend(
        [
            "",
            (
                "This is a default-off paper sleeve candidate-ranking alpha "
                "experiment. It changes no live orders, queue qualification, "
                "capacity, hold days, notional, or core signal path."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    timestamp = _utc_now()
    raw_exp100 = _load_source_candidates()
    exp100 = _filter_current_queue(raw_exp100)

    core_results = {}
    for label, window in WINDOWS.items():
        result = _run_core_backtest(window)
        core_results[label] = {
            "metrics": _core_metrics(result),
            "equity_curve": _normalise_core_curve(result),
        }

    variants: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for priority in QUEUE_PRIORITY_VARIANTS:
        variants[priority] = _run_variant(
            core_results=core_results,
            exp100=exp100,
            queue_priority=priority,
        )

    baseline = variants[BASELINE_PRIORITY]
    after = variants[VARIANT_PRIORITY]
    gate = _gate(after, baseline)
    status = "accepted" if gate["passed"] else "rejected"
    decision = (
        "accepted_for_shared_default_off_10q_queue_priority"
        if gate["passed"]
        else "rejected_10q_queue_priority"
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "hypothesis": (
            "Inside the accepted SEC financial-report T+1 paper sleeve, "
            "10-Q periodic-report candidates have shown stronger event quality "
            "than the broad financial-report queue, so ranking 10-Q candidates "
            "ahead of other same-day candidates may improve capacity use without "
            "adding live orders or changing notional."
        ),
        "change_type": "alpha_search_candidate_ranking",
        "changed_variable": "sec_financial_report_10q_queue_priority",
        "parameters": {
            "baseline_priority": BASELINE_PRIORITY,
            "variant_priority": VARIANT_PRIORITY,
            "base_event_notional_usd": DEFAULT_EVENT_NOTIONAL_USD,
            "earnings_8k_scalar": 1.0,
            "periodic_report_scalar": DEFAULT_PERIODIC_REPORT_NOTIONAL_SCALAR,
            "tenq_periodic_report_scalar": TENQ_PERIODIC_REPORT_NOTIONAL_SCALAR,
            "max_positions": DEFAULT_MAX_POSITIONS,
            "min_t1_excess_return_vs_spy": FINANCIAL_REPORT_T1_MIN_EXCESS_RETURN_VS_SPY,
            "source_candidate_artifact": str(SOURCE_EXP100_JSON.relative_to(REPO_ROOT)),
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows for core baseline, "
            "plus production paper-sleeve replay over the same OHLCV snapshots. "
            "Core replay uses REPLAY_PARTIAL_REDUCES and REGIME_AWARE_EXIT."
        ),
        "date_range": {
            "primary": {
                "start": WINDOWS["late_strong"]["start"],
                "end": WINDOWS["late_strong"]["end"],
            },
            "secondary": [
                {"start": WINDOWS["mid_weak"]["start"], "end": WINDOWS["mid_weak"]["end"]},
                {"start": WINDOWS["old_thin"]["start"], "end": WINDOWS["old_thin"]["end"]},
            ],
        },
        "candidate_counts_after_current_queue_filter": _candidate_counts(exp100),
        "before_metrics": baseline["aggregate"],
        "after_metrics": after["aggregate"],
        "delta_metrics": {
            "aggregate": gate["aggregate_delta"],
            "by_window": gate["window_checks"],
        },
        "expected_value_score_delta": gate["aggregate_delta"].get(
            "expected_value_score_sum_delta"
        ),
        "gate": gate,
        "decision": decision,
        "rejection_reason": (
            None
            if gate["passed"]
            else "10-Q-first queue priority did not clear the three-window candidate-ranking gate."
        ),
        "next_evidence_needed": (
            "Promote only by changing the shared default-off sleeve sort helper "
            "and adding parity tests, then collect forward paper replacement value."
            if gate["passed"]
            else "Do not retry nearby SEC financial-report queue-priority variants on this frozen sample; use forward outcomes or a genuinely new earnings-quality field."
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "default_off_paper_only": True,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": True,
            "alters_sizing": False,
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "ranking: give accepted 10-Q periodic-report paper candidates "
                "queue priority over other same-day SEC financial-report rows."
            ),
            "2_history_check": (
                "exp-20260512-007 accepted periodic-report notional, "
                "exp-20260512-020 accepted 10-Q notional, and "
                "exp-20260512-009 rejected rank1 notional. No recent experiment "
                "changed SEC financial-report queue ordering by form quality."
            ),
            "3_single_causal_variable": "10-Q-first queue priority only",
            "4_acceptance_standard": gate["rule"],
            "5_reproducibility": (
                f"Run .venv\\Scripts\\python.exe quant\\experiments\\"
                f"exp_20260512_025_{STEM}.py"
            ),
        },
        "variants": variants,
        "why_not_other_changes": (
            "LLM soft-ranking remains sample-limited, Space is waiting for "
            "forward catalyst replacement value, and raw SEC notional/hold/floor "
            "retunes have anti-repeat constraints. This tests a distinct "
            "candidate-ranking use of the already accepted 10-Q quality signal."
        ),
    }

    _write_json(OUT_JSON, payload)
    _write_json(DOC_LOG, payload)
    _write_json(
        DOC_TICKET,
        {
            "experiment_id": EXPERIMENT_ID,
            "lane": "alpha_search",
            "owner": "alpha-search",
            "status": status,
            "hypothesis": payload["hypothesis"],
            "single_causal_variable": payload["changed_variable"],
            "acceptance_rule": gate["rule"],
            "result": {
                "artifact_file": str(OUT_JSON.relative_to(REPO_ROOT)),
                "decision": decision,
                "expected_value_score_delta": payload["expected_value_score_delta"],
                "result_file": str(DOC_LOG.relative_to(REPO_ROOT)),
                "total_pnl_delta": gate["aggregate_delta"].get("total_pnl_sum_delta"),
            },
            "updated_at": timestamp,
        },
    )
    DOC_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT.write_text(_artifact_markdown(payload), encoding="utf-8")
    _append_jsonl_once(EXPERIMENT_LOG_JSONL, payload)

    print(json.dumps(_safe(payload["gate"]), indent=2, sort_keys=True))
    print(f"{EXPERIMENT_ID} {decision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
