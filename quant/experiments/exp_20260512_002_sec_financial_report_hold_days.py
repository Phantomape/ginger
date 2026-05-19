"""exp-20260512-002: SEC financial-report T+1 sleeve hold days.

Alpha search on one causal variable: the default-off SEC financial-report
paper sleeve hold period. The accepted max-3 capacity and 1% ticker-vs-SPY
T+1 excess floor are fixed. This replay calls the production paper-sleeve
builder directly and never enables live orders.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260512-002"
STEM = "exp_20260512_002_sec_financial_report_hold_days"
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
    _load_exp100,
    _load_snapshot_prices,
    _normalise_core_curve,
    _rebuild_sleeve_state,
    _round,
    _rows_by_t1_date,
    _run_core_backtest,
    _safe,
    _write_json,
)
from sec_event_queue import FINANCIAL_REPORT_T1_MIN_EXCESS_RETURN_VS_SPY  # noqa: E402
from sec_financial_report_event_sleeve import (  # noqa: E402
    DEFAULT_CONFIG,
    DEFAULT_MAX_POSITIONS,
    build_sec_financial_report_event_sleeve_snapshot,
    empty_sec_financial_report_event_sleeve_state,
)


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
DOC_LOG = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_ARTIFACT = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_sec_financial_report_hold_days.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
EXPERIMENT_REGISTRY = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_HOLD_DAYS = 10
HOLD_DAY_VARIANTS = (5, 7, 10, 12, 15, 20)
MIN_PROMOTION_CLOSED_TRADES = 40


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


def _upsert_registry(payload: dict[str, Any]) -> None:
    if EXPERIMENT_REGISTRY.exists():
        registry = json.loads(EXPERIMENT_REGISTRY.read_text(encoding="utf-8-sig"))
    else:
        registry = {"experiments": []}
    experiments = [
        row
        for row in registry.get("experiments", [])
        if row.get("experiment_id") != EXPERIMENT_ID
    ]
    experiments.append(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": payload["hypothesis"],
            "lane": "alpha_search",
            "owner": "alpha-search",
            "status": payload["status"],
            "ticket_file": f"experiments/tickets/{EXPERIMENT_ID}.json",
            "updated_at": payload["timestamp"],
        }
    )
    registry["experiments"] = sorted(
        experiments, key=lambda row: str(row.get("experiment_id") or "")
    )
    _write_json(EXPERIMENT_REGISTRY, registry)


def _float_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _filter_current_queue(exp100: dict[str, Any]) -> dict[str, Any]:
    filtered = json.loads(json.dumps(exp100))
    floor = float(FINANCIAL_REPORT_T1_MIN_EXCESS_RETURN_VS_SPY)
    for window in filtered.get("windows", {}).values():
        rows = []
        for row in window.get("candidate_rows") or []:
            excess = _float_or_none(row.get("t1_excess_return_vs_spy"))
            if excess is not None and excess >= floor:
                rows.append(row)
        window["candidate_rows"] = rows
    return filtered


def _candidate_counts(exp100: dict[str, Any]) -> dict[str, int]:
    return {
        label: len(window.get("candidate_rows") or [])
        for label, window in exp100.get("windows", {}).items()
    }


def _run_sleeve_replay(
    window_label: str,
    window: dict[str, str],
    window_payload: dict[str, Any],
    *,
    hold_days: int,
) -> dict[str, Any]:
    prices_by_date = _load_snapshot_prices(window["snapshot"])
    candidates_by_t1 = _rows_by_t1_date(window_payload)
    state = empty_sec_financial_report_event_sleeve_state()
    skipped_entries: list[dict[str, Any]] = []
    pnl_by_date: OrderedDict[str, float] = OrderedDict()
    max_open_positions = 0
    max_gross_notional = 0.0
    enqueued_candidates = 0

    for as_of, prices in prices_by_date.items():
        candidates = candidates_by_t1.get(as_of, [])
        enqueued_candidates += len(candidates)
        queue = {
            "queue_name": "SEC_FINANCIAL_REPORT_T1_DRIFT_QUEUE_REPLAY",
            "rule_version": "exp-20260512-002-replay",
            "enabled": False,
            "asof_date": as_of,
            "candidate_count": len(candidates),
            "candidates": candidates,
            "data_source": {
                "status": "replay",
                "source_experiment": "exp-20260511-100",
                "window": window_label,
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
                "hold_days": hold_days,
            },
            persist=False,
        )
        skipped_entries.extend(snapshot.get("skipped_entries_today") or [])
        state = _rebuild_sleeve_state(snapshot, skipped_entries)
        realized = float(snapshot.get("realized_pnl_to_date") or 0.0)
        unrealized = float(snapshot.get("unrealized_pnl") or 0.0)
        pnl_by_date[as_of] = realized + unrealized
        open_positions = snapshot.get("open_positions") or []
        max_open_positions = max(max_open_positions, len(open_positions))
        max_gross_notional = max(
            max_gross_notional,
            sum(float(item.get("notional") or 0.0) for item in open_positions),
        )

    closed_positions = state.get("closed_positions") or []
    wins = sum(1 for item in closed_positions if float(item.get("pnl") or 0.0) > 0)
    sleeve_curve = [
        (date_value, 100_000.0 + pnl) for date_value, pnl in pnl_by_date.items()
    ]
    standalone_metrics = _equity_metrics(
        sleeve_curve,
        trade_count=len(closed_positions),
        win_rate=(wins / len(closed_positions) if closed_positions else None),
    )
    standalone_metrics.update(
        {
            "candidate_count": enqueued_candidates,
            "closed_trade_count": len(closed_positions),
            "open_position_count_end": len(state.get("open_positions") or []),
            "skipped_capacity_count": len(skipped_entries),
            "max_open_positions": max_open_positions,
            "max_gross_notional": _round(max_gross_notional, 2),
        }
    )
    return {
        "daily_pnl": list(pnl_by_date.items()),
        "metrics": standalone_metrics,
        "sample_closed_positions": closed_positions[:10],
    }


def _run_variant(
    *,
    core_results: dict[str, dict[str, Any]],
    exp100: dict[str, Any],
    hold_days: int,
) -> dict[str, Any]:
    by_window = {}
    for label, window in WINDOWS.items():
        sleeve = _run_sleeve_replay(
            label,
            window,
            exp100["windows"][label],
            hold_days=hold_days,
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
            "combined_metrics": combined_metrics,
            "core_metrics": core_metrics,
            "sleeve_metrics": sleeve["metrics"],
        }
    return {"by_window": by_window, "aggregate": _aggregate(by_window)}


def _window_checks(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    checks = {}
    for label in WINDOWS:
        after_m = after["by_window"][label]["combined_metrics"]
        before_m = before["by_window"][label]["combined_metrics"]
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
            "sleeve_closed_trade_delta": int(
                after["by_window"][label]["sleeve_metrics"].get("closed_trade_count")
                or 0
            )
            - int(
                before["by_window"][label]["sleeve_metrics"].get("closed_trade_count")
                or 0
            ),
        }
    return checks


def _gate(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    aggregate_delta = _delta(after["aggregate"], before["aggregate"])
    checks = _window_checks(after, before)
    ev_positive_windows = sum(1 for row in checks.values() if row["ev_delta"] > 0)
    ev_regressed_windows = sum(1 for row in checks.values() if row["ev_delta"] < 0)
    pnl_positive_windows = sum(1 for row in checks.values() if row["pnl_delta"] > 0)
    max_drawdown_delta_max = max(row["max_drawdown_delta"] for row in checks.values())
    sleeve_trades_after = int(after["aggregate"].get("sleeve_closed_trade_count_sum") or 0)
    passed = (
        (aggregate_delta.get("expected_value_score_sum_delta") or 0.0) > 0
        and (aggregate_delta.get("sleeve_total_pnl_sum_delta") or 0.0) >= 0.0
        and ev_positive_windows >= 2
        and ev_regressed_windows <= 1
        and pnl_positive_windows >= 2
        and max_drawdown_delta_max <= 0.005
        and sleeve_trades_after >= MIN_PROMOTION_CLOSED_TRADES
    )
    return {
        "aggregate_delta": aggregate_delta,
        "ev_positive_windows": ev_positive_windows,
        "ev_regressed_windows": ev_regressed_windows,
        "max_drawdown_delta_max": _round(max_drawdown_delta_max, 6),
        "passed": passed,
        "pnl_positive_windows": pnl_positive_windows,
        "rule": (
            "Pass if aggregate EV and sleeve PnL improve, EV improves in at "
            "least two windows with at most one EV regression, PnL improves in "
            "at least two windows, max drawdown worsens by no more than 0.5 "
            "percentage points, and the sleeve keeps at least 40 closed trades."
        ),
        "sleeve_closed_trade_count_after": sleeve_trades_after,
        "window_checks": checks,
    }


def _best_candidate(variants: OrderedDict[str, dict[str, Any]]) -> str:
    baseline = variants[f"hold_{BASELINE_HOLD_DAYS}d"]
    candidates = [
        (name, row)
        for name, row in variants.items()
        if int(row["hold_days"]) != BASELINE_HOLD_DAYS
    ]
    gated = [
        (name, row, _gate(row, baseline))
        for name, row in candidates
        if int(row["aggregate"].get("sleeve_closed_trade_count_sum") or 0)
        >= MIN_PROMOTION_CLOSED_TRADES
    ]
    if not gated:
        return candidates[0][0]
    return max(
        gated,
        key=lambda item: (
            bool(item[2]["passed"]),
            float(item[2]["aggregate_delta"].get("expected_value_score_sum_delta") or 0.0),
            float(item[2]["aggregate_delta"].get("sleeve_total_pnl_sum_delta") or 0.0),
            -float(item[2]["max_drawdown_delta_max"] or 0.0),
        ),
    )[0]


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} SEC financial-report hold days",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Changed variable: `{payload['changed_variable']}`",
        f"- Best hold days: `{payload['best_hold_days']}`",
        "- Replay path: accepted max-3 and T+1 excess >=1% default-off paper sleeve; no live orders.",
        "",
        "## Aggregate",
        "",
        "| Variant | Hold days | EV sum | Total PnL | Sleeve PnL | Sleeve closed | Max DD max |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, row in payload["variants"].items():
        agg = row["aggregate"]
        lines.append(
            f"| {name} | {row['hold_days']} | "
            f"{agg['expected_value_score_sum']:.6f} | "
            f"${agg['total_pnl_sum']:,.2f} | "
            f"${agg['sleeve_total_pnl_sum']:,.2f} | "
            f"{agg['sleeve_closed_trade_count_sum']} | "
            f"{agg['max_drawdown_pct_max']:.4f} |"
        )
    lines.extend(
        [
            "",
            "## Gate",
            "",
            json.dumps(_safe(payload["gate"]), ensure_ascii=False, indent=2, sort_keys=True),
            "",
            "## Production impact",
            "",
            (
                "No live orders changed. If accepted, promote only by changing "
                "the shared default-off paper sleeve hold-days config and adding "
                "a focused no-orders lifecycle test."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    now = _utc_now()
    exp100 = _filter_current_queue(_load_exp100())
    counts = _candidate_counts(exp100)

    core_results: dict[str, dict[str, Any]] = {}
    for label, window in WINDOWS.items():
        result = _run_core_backtest(window)
        core_results[label] = {
            "metrics": _core_metrics(result),
            "equity_curve": _normalise_core_curve(result),
        }

    variants: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for hold_days in HOLD_DAY_VARIANTS:
        result = _run_variant(
            core_results=core_results,
            exp100=exp100,
            hold_days=hold_days,
        )
        result["hold_days"] = hold_days
        result["candidate_counts"] = counts
        result["candidate_count_sum"] = sum(counts.values())
        variants[f"hold_{hold_days}d"] = result

    baseline = variants[f"hold_{BASELINE_HOLD_DAYS}d"]
    best_name = _best_candidate(variants)
    best = variants[best_name]
    gate = _gate(best, baseline)
    production_hold_days = int(DEFAULT_CONFIG.get("hold_days") or BASELINE_HOLD_DAYS)
    promotion_applied = gate["passed"] and production_hold_days == int(best["hold_days"])
    decision = (
        "accepted_default_off_hold_days"
        if gate["passed"]
        else "rejected_hold_days"
    )

    payload: dict[str, Any] = {
        "after_metrics": best["by_window"],
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows for core baseline, "
            "plus production paper-sleeve replay over the same OHLCV snapshots. "
            "Core replay uses REPLAY_PARTIAL_REDUCES and REGIME_AWARE_EXIT."
        ),
        "before_metrics": baseline["by_window"],
        "best_hold_days": best["hold_days"],
        "best_variant": best_name,
        "change_type": "alpha_search_exit_lifecycle",
        "changed_variable": "sec_financial_report_event_sleeve_hold_days",
        "decision": decision,
        "delta_metrics": {
            "aggregate": gate["aggregate_delta"],
            "by_window": gate["window_checks"],
        },
        "experiment_id": EXPERIMENT_ID,
        "gate": gate,
        "hypothesis": (
            "Inside the accepted max-3 and T+1 excess >=1% SEC financial-report "
            "paper sleeve, the post-filing drift lifecycle may be shorter or "
            "longer than the current 10-trading-day hold."
        ),
        "lane": "alpha_search",
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm_soft_ranking": (
                "LLM soft-ranking data remains sparse; this tests a deterministic "
                "exit/lifecycle variable on the production-visible paper sleeve."
            ),
        },
        "parameters": {
            "baseline_hold_days": BASELINE_HOLD_DAYS,
            "hold_day_variants": list(HOLD_DAY_VARIANTS),
            "max_positions": DEFAULT_MAX_POSITIONS,
            "min_promotion_closed_trades": MIN_PROMOTION_CLOSED_TRADES,
            "production_hold_days_at_run": production_hold_days,
            "t1_excess_floor": FINANCIAL_REPORT_T1_MIN_EXCESS_RETURN_VS_SPY,
            "source_candidate_artifact": str(SOURCE_EXP100_JSON.relative_to(REPO_ROOT)),
        },
        "production_impact": {
            "shared_policy_changed": promotion_applied,
            "backtester_adapter_changed": False,
            "run_adapter_changed": promotion_applied,
            "replay_only": not promotion_applied,
            "parity_test_added": promotion_applied,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_sizing": False,
            "alters_candidate_ranking": False,
            "alters_exit_lifecycle": True,
            "default_off_paper_only": True,
            "live_orders_changed": False,
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "exit/lifecycle: the SEC financial-report positive T+1 drift "
                "paper sleeve may need a different fixed hold period."
            ),
            "2_history_check": (
                "exp-20260511-112 tested capacity, exp-20260511-113 pending "
                "priority, exp-20260511-114 form-base exclusion, and "
                "exp-20260512-001 T+1 excess floor. No logged experiment isolated "
                "hold_days for this sleeve."
            ),
            "3_single_causal_variable": "hold_days only",
            "4_acceptance_standard": (
                "Three fixed windows, aggregate EV and sleeve PnL improve, EV "
                "positive in at least 2/3 windows, drawdown drift <=0.5pp, and "
                "at least 40 sleeve closed trades."
            ),
            "5_reproducibility": (
                f"Run .venv\\Scripts\\python.exe quant\\experiments\\{STEM}.py"
            ),
        },
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(DOC_LOG.relative_to(REPO_ROOT)),
            str(DOC_TICKET.relative_to(REPO_ROOT)),
            str(DOC_ARTIFACT.relative_to(REPO_ROOT)),
        ],
        "single_causal_variable": "sec_financial_report_event_sleeve_hold_days",
        "status": "accepted_candidate" if gate["passed"] else "rejected",
        "timestamp": now,
        "variants": variants,
    }
    payload["rejection_reason"] = (
        None
        if gate["passed"]
        else "No tested hold period cleared the three-window lifecycle gate."
    )

    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "hypothesis": payload["hypothesis"],
        "lane": "alpha_search",
        "owner": "alpha-search",
        "status": payload["status"],
        "created_at": now,
        "updated_at": now,
        "next_action": (
            "Promote through shared default-off hold-days config plus focused no-orders test."
            if gate["passed"] and not promotion_applied
            else "Forward-observe the promoted default-off hold-days setting."
            if promotion_applied
            else "Keep 10-day hold; do not retry nearby hold periods without forward evidence."
        ),
    }
    log_payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "changed_variable": payload["changed_variable"],
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
        "backtest_protocol": payload["backtest_protocol"],
        "parameters": payload["parameters"],
        "before_metrics": baseline["aggregate"],
        "after_metrics": best["aggregate"],
        "delta_metrics": payload["delta_metrics"],
        "expected_value_score_delta": gate["aggregate_delta"].get(
            "expected_value_score_sum_delta"
        ),
        "decision": decision,
        "rejection_reason": payload["rejection_reason"],
        "next_evidence_needed": (
            "Shared default-off lifecycle promotion and forward paper observation."
            if gate["passed"]
            else "Forward replacement-value evidence by hold-period bucket."
        ),
        "production_impact": payload["production_impact"],
    }

    _write_json(OUT_JSON, payload)
    _write_json(DOC_LOG, log_payload)
    _write_json(DOC_TICKET, ticket)
    DOC_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT.write_text(_artifact_markdown(payload), encoding="utf-8")
    _append_jsonl_once(EXPERIMENT_LOG_JSONL, log_payload)
    _upsert_registry(payload)

    print(json.dumps(_safe(log_payload), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
