"""exp-20260512-007: SEC financial-report periodic-report notional scalar.

Alpha search on one causal variable: a paper-notional scalar for
``periodic_report`` rows inside the accepted default-off SEC financial-report
T+1 sleeve. Capacity, T+1 excess floor, hold days, candidate ranking, live
orders, and the earnings_8k notional stay fixed.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260512-007"
STEM = "exp_20260512_007_sec_financial_report_periodic_notional"
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


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
DOC_LOG = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_ARTIFACT = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_sec_financial_report_periodic_notional.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

BASELINE_PERIODIC_REPORT_SCALAR = 1.0
PERIODIC_REPORT_SCALAR_VARIANTS = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0)
MIN_PROMOTION_CLOSED_TRADES = 40
MAX_DRAWDOWN_WORSENING = 0.005


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


def _candidate_counts(exp100: dict[str, Any]) -> dict[str, int]:
    return {
        label: len(window.get("candidate_rows") or [])
        for label, window in exp100.get("windows", {}).items()
    }


def _event_family(position: dict[str, Any]) -> str:
    candidate = position.get("source_candidate") or {}
    return str(candidate.get("event_family") or "")


def _notional_for_position(
    position: dict[str, Any],
    *,
    periodic_report_scalar: float,
) -> float:
    base = float(DEFAULT_EVENT_NOTIONAL_USD)
    if _event_family(position) == "periodic_report":
        return base * float(periodic_report_scalar)
    return base


def _pnl_for_position(
    position: dict[str, Any],
    *,
    periodic_report_scalar: float,
    closed: bool,
) -> float:
    adjusted_notional = _notional_for_position(
        position,
        periodic_report_scalar=periodic_report_scalar,
    )
    if closed:
        try:
            net_return = float(position.get("net_return_pct") or 0.0) / 100.0
        except (TypeError, ValueError):
            net_return = 0.0
        return adjusted_notional * net_return

    try:
        source_notional = float(position.get("notional") or 0.0)
        source_pnl = float(position.get("net_pnl_if_closed_now") or 0.0)
    except (TypeError, ValueError):
        return 0.0
    if source_notional <= 0:
        return 0.0
    return adjusted_notional * (source_pnl / source_notional)


def _adjust_closed_position(
    position: dict[str, Any],
    *,
    periodic_report_scalar: float,
) -> dict[str, Any]:
    adjusted = dict(position)
    notional = _notional_for_position(
        position,
        periodic_report_scalar=periodic_report_scalar,
    )
    adjusted["base_notional"] = float(DEFAULT_EVENT_NOTIONAL_USD)
    adjusted["notional"] = round(notional, 2)
    adjusted["periodic_report_notional_scalar"] = periodic_report_scalar
    adjusted["pnl"] = round(
        _pnl_for_position(
            position,
            periodic_report_scalar=periodic_report_scalar,
            closed=True,
        ),
        2,
    )
    return adjusted


def _run_sleeve_replay(
    window_label: str,
    window: dict[str, str],
    window_payload: dict[str, Any],
    *,
    periodic_report_scalar: float,
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
            "rule_version": "exp-20260512-007-replay",
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
                "event_notional_usd": DEFAULT_EVENT_NOTIONAL_USD,
            },
            persist=False,
        )
        skipped_entries.extend(snapshot.get("skipped_entries_today") or [])
        state = _rebuild_sleeve_state(snapshot, skipped_entries)

        realized = sum(
            _pnl_for_position(
                item,
                periodic_report_scalar=periodic_report_scalar,
                closed=True,
            )
            for item in state.get("closed_positions") or []
        )
        unrealized = sum(
            _pnl_for_position(
                item,
                periodic_report_scalar=periodic_report_scalar,
                closed=False,
            )
            for item in state.get("open_positions") or []
        )
        pnl_by_date[as_of] = realized + unrealized
        open_positions = state.get("open_positions") or []
        max_open_positions = max(max_open_positions, len(open_positions))
        max_gross_notional = max(
            max_gross_notional,
            sum(
                _notional_for_position(
                    item,
                    periodic_report_scalar=periodic_report_scalar,
                )
                for item in open_positions
            ),
        )

    closed_positions = [
        _adjust_closed_position(
            item,
            periodic_report_scalar=periodic_report_scalar,
        )
        for item in state.get("closed_positions") or []
    ]
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
    periodic_report_scalar: float,
) -> dict[str, Any]:
    by_window = {}
    for label, window in WINDOWS.items():
        sleeve = _run_sleeve_replay(
            label,
            window,
            exp100["windows"][label],
            periodic_report_scalar=periodic_report_scalar,
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
            "sample_closed_positions": sleeve["sample_closed_positions"],
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
        and ev_positive_windows == 3
        and ev_regressed_windows == 0
        and pnl_positive_windows == 3
        and max_drawdown_delta_max <= MAX_DRAWDOWN_WORSENING
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
            "Pass if aggregate EV and sleeve PnL improve, EV and PnL improve "
            "in all three windows, max drawdown worsens by no more than 0.5 "
            "percentage points in any window, and the sleeve keeps at least "
            "40 closed trades."
        ),
        "sleeve_closed_trade_count_after": sleeve_trades_after,
        "window_checks": checks,
    }


def _best_candidate(variants: OrderedDict[str, dict[str, Any]]) -> str:
    baseline = variants[f"periodic_scalar_{BASELINE_PERIODIC_REPORT_SCALAR:.2f}"]
    candidates = [
        (name, row, _gate(row, baseline))
        for name, row in variants.items()
        if row["periodic_report_notional_scalar"] != BASELINE_PERIODIC_REPORT_SCALAR
    ]
    passed = [(name, row, gate) for name, row, gate in candidates if gate["passed"]]
    if passed:
        return max(
            passed,
            key=lambda item: (
                item[2]["aggregate_delta"].get("expected_value_score_sum_delta") or 0.0,
                item[2]["aggregate_delta"].get("sleeve_total_pnl_sum_delta") or 0.0,
                -item[2]["max_drawdown_delta_max"],
            ),
        )[0]
    return max(
        candidates,
        key=lambda item: (
            item[2]["aggregate_delta"].get("expected_value_score_sum_delta") or -999.0,
            item[2]["aggregate_delta"].get("sleeve_total_pnl_sum_delta") or -999999.0,
        ),
    )[0]


def main() -> int:
    timestamp = _utc_now()
    raw_exp100 = _load_exp100()
    exp100 = _filter_current_queue(raw_exp100)

    core_results = {}
    for label, window in WINDOWS.items():
        result = _run_core_backtest(window)
        core_results[label] = {
            "metrics": _core_metrics(result),
            "equity_curve": _normalise_core_curve(result),
        }

    variants: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for scalar in PERIODIC_REPORT_SCALAR_VARIANTS:
        name = f"periodic_scalar_{scalar:.2f}"
        row = _run_variant(
            core_results=core_results,
            exp100=exp100,
            periodic_report_scalar=scalar,
        )
        row["periodic_report_notional_scalar"] = scalar
        variants[name] = row

    baseline_key = f"periodic_scalar_{BASELINE_PERIODIC_REPORT_SCALAR:.2f}"
    baseline = variants[baseline_key]
    best_key = _best_candidate(variants)
    best = variants[best_key]
    gate = _gate(best, baseline)
    promotion_applied = (
        gate["passed"]
        and abs(
            float(best["periodic_report_notional_scalar"])
            - float(DEFAULT_PERIODIC_REPORT_NOTIONAL_SCALAR)
        )
        < 1e-12
    )
    decision = (
        f"accepted_default_off_periodic_report_notional_{best['periodic_report_notional_scalar']:.2f}x"
        if gate["passed"]
        else "rejected_periodic_report_notional_scalar"
    )
    status = "accepted" if gate["passed"] else "rejected"

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "hypothesis": (
            "Inside the accepted SEC financial-report T+1 paper sleeve, "
            "periodic_report rows may deserve a higher paper notional than "
            "earnings_8k rows because their accepted-sleeve drift is stronger "
            "across all three canonical windows."
        ),
        "change_type": "alpha_search_semantic_risk_allocation",
        "changed_variable": "sec_financial_report_periodic_report_notional_scalar",
        "parameters": {
            "baseline_periodic_report_notional_scalar": BASELINE_PERIODIC_REPORT_SCALAR,
            "periodic_report_scalar_variants": list(PERIODIC_REPORT_SCALAR_VARIANTS),
            "base_event_notional_usd": DEFAULT_EVENT_NOTIONAL_USD,
            "earnings_8k_scalar": 1.0,
            "max_positions": DEFAULT_MAX_POSITIONS,
            "min_t1_excess_return_vs_spy": FINANCIAL_REPORT_T1_MIN_EXCESS_RETURN_VS_SPY,
            "production_periodic_report_notional_scalar_at_run": (
                DEFAULT_PERIODIC_REPORT_NOTIONAL_SCALAR
            ),
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
        "after_metrics": best["aggregate"],
        "delta_metrics": {
            "aggregate": gate["aggregate_delta"],
            "by_window": gate["window_checks"],
        },
        "expected_value_score_delta": gate["aggregate_delta"].get(
            "expected_value_score_sum_delta"
        ),
        "best_variant": best_key,
        "gate": gate,
        "decision": decision,
        "rejection_reason": (
            None
            if gate["passed"]
            else "No periodic-report notional scalar cleared the three-window semantic risk-allocation gate."
        ),
        "next_evidence_needed": (
            "Promote only as shared default-off paper-sleeve metadata/helper, then collect forward replacement-value evidence before any live-order scope."
            if gate["passed"]
            else "Forward replacement-value evidence by SEC event-family bucket before retrying semantic notional allocation."
        ),
        "production_impact": {
            "shared_policy_changed": promotion_applied,
            "backtester_adapter_changed": False,
            "run_adapter_changed": promotion_applied,
            "replay_only": not promotion_applied,
            "parity_test_added": promotion_applied,
            "default_off_paper_only": True,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": True,
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "risk allocation: use existing SEC event_family semantics to scale "
                "paper notional for periodic_report rows."
            ),
            "2_history_check": (
                "exp-20260511-114 tested excluding 10-K rows and failed; "
                "exp-20260512-006 tested a global event-notional budget and passed. "
                "No logged experiment has isolated event-family-conditioned notional."
            ),
            "3_single_causal_variable": "periodic_report paper-notional scalar only",
            "4_acceptance_standard": (
                "Three fixed windows, aggregate EV and sleeve PnL improve, EV/PnL "
                "improve in all three windows, max drawdown drift <=0.5pp, and "
                "at least 40 closed sleeve trades."
            ),
            "5_reproducibility": (
                f"Run .venv\\Scripts\\python.exe quant\\experiments\\{STEM}.py"
            ),
        },
        "variants": variants,
        "why_not_other_changes": (
            "LLM soft-ranking and filing-shock data remain field-limited. Nearby "
            "SEC floor, hold-day, form-exclusion, and global-notional sweeps are "
            "already logged, so this run changes only a semantic event-family "
            "risk-allocation variable."
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
                "decision": decision,
                "artifact_file": str(OUT_JSON.relative_to(REPO_ROOT)),
                "result_file": str(DOC_LOG.relative_to(REPO_ROOT)),
                "expected_value_score_delta": payload["expected_value_score_delta"],
                "total_pnl_delta": gate["aggregate_delta"].get("total_pnl_sum_delta"),
            },
            "updated_at": timestamp,
        },
    )
    DOC_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT.write_text(
        "\n".join(
            [
                f"# {EXPERIMENT_ID} SEC financial-report periodic notional",
                "",
                f"- Decision: `{decision}`",
                f"- Best variant: `{best_key}`",
                f"- EV delta: `{payload['expected_value_score_delta']}`",
                f"- Total PnL delta: `{gate['aggregate_delta'].get('total_pnl_sum_delta')}`",
                f"- Max drawdown delta max: `{gate['max_drawdown_delta_max']}`",
                f"- Closed sleeve trades after: `{gate['sleeve_closed_trade_count_after']}`",
                "",
                (
                    "This is a semantic default-off paper sleeve risk-allocation "
                    "experiment. It changes no live orders, queue qualification, "
                    "candidate ranking, capacity, or hold period."
                ),
                "",
            ]
        ),
        encoding="utf-8",
    )
    _append_jsonl_once(EXPERIMENT_LOG_JSONL, payload)

    print(json.dumps(_safe(payload["gate"]), indent=2, sort_keys=True))
    print(f"{EXPERIMENT_ID} {decision} best={best_key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
