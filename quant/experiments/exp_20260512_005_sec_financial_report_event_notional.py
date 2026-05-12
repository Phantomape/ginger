"""exp-20260512-005: SEC financial-report T+1 paper notional.

Alpha search on one causal variable: the default-off SEC financial-report
paper sleeve's per-event notional budget. The accepted max-3 capacity and
1% ticker-vs-SPY T+1 excess floor are fixed. This replay calls the production
paper-sleeve builder directly and never enables live orders.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260512-005"
STEM = "exp_20260512_005_sec_financial_report_event_notional"
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
from sec_financial_report_event_sleeve import (  # noqa: E402
    DEFAULT_EVENT_NOTIONAL_USD,
    DEFAULT_MAX_POSITIONS,
    empty_sec_financial_report_event_sleeve_state,
    build_sec_financial_report_event_sleeve_snapshot,
)
from sec_event_queue import FINANCIAL_REPORT_T1_MIN_EXCESS_RETURN_VS_SPY  # noqa: E402


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
DOC_LOG = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_ARTIFACT = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_sec_financial_report_event_notional.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

BASELINE_EVENT_NOTIONAL_USD = 10_000.0
EVENT_NOTIONAL_VARIANTS = (5_000.0, 7_500.0, 10_000.0, 12_500.0, 15_000.0, 20_000.0, 25_000.0)
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


def _run_sleeve_replay(
    window_label: str,
    window: dict[str, str],
    window_payload: dict[str, Any],
    *,
    event_notional_usd: float,
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
            "rule_version": "exp-20260512-005-replay",
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
                "event_notional_usd": event_notional_usd,
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
    event_notional_usd: float,
) -> dict[str, Any]:
    by_window = {}
    for label, window in WINDOWS.items():
        sleeve = _run_sleeve_replay(
            label,
            window,
            exp100["windows"][label],
            event_notional_usd=event_notional_usd,
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
    baseline = variants[f"notional_{int(BASELINE_EVENT_NOTIONAL_USD)}"]
    candidates = [
        (name, row, _gate(row, baseline))
        for name, row in variants.items()
        if row["event_notional_usd"] != BASELINE_EVENT_NOTIONAL_USD
    ]
    passed = [(name, row, gate) for name, row, gate in candidates if gate["passed"]]
    if passed:
        return max(
            passed,
            key=lambda item: (
                item[2]["aggregate_delta"].get("expected_value_score_sum_delta") or 0.0,
                item[2]["aggregate_delta"].get("sleeve_total_pnl_sum_delta") or 0.0,
            ),
        )[0]
    return max(
        candidates,
        key=lambda item: (
            item[2]["aggregate_delta"].get("expected_value_score_sum_delta") or -999.0,
            item[2]["aggregate_delta"].get("sleeve_total_pnl_sum_delta") or -999_999.0,
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
    for notional in EVENT_NOTIONAL_VARIANTS:
        name = f"notional_{int(notional)}"
        row = _run_variant(
            core_results=core_results,
            exp100=exp100,
            event_notional_usd=notional,
        )
        row["event_notional_usd"] = notional
        variants[name] = row

    baseline_key = f"notional_{int(BASELINE_EVENT_NOTIONAL_USD)}"
    baseline = variants[baseline_key]
    best_key = _best_candidate(variants)
    best = variants[best_key]
    gate = _gate(best, baseline)
    decision = (
        "accepted_default_off_event_notional_15000"
        if gate["passed"] and best["event_notional_usd"] == 15_000.0
        else "rejected_event_notional_budget"
    )
    status = "accepted" if decision.startswith("accepted") else "rejected"

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "hypothesis": (
            "Inside the accepted max-3 and T+1 excess >=1% SEC financial-report "
            "paper sleeve, the stronger event-quality floor may support a larger "
            "per-event paper notional budget without adding noisy tickers or "
            "changing live orders."
        ),
        "change_type": "alpha_search_risk_allocation",
        "changed_variable": "sec_financial_report_event_sleeve_event_notional_usd",
        "parameters": {
            "baseline_event_notional_usd": BASELINE_EVENT_NOTIONAL_USD,
            "event_notional_variants": list(EVENT_NOTIONAL_VARIANTS),
            "max_positions": DEFAULT_MAX_POSITIONS,
            "min_t1_excess_return_vs_spy": FINANCIAL_REPORT_T1_MIN_EXCESS_RETURN_VS_SPY,
            "production_event_notional_at_run": DEFAULT_EVENT_NOTIONAL_USD,
            "source_candidate_artifact": str(SOURCE_EXP100_JSON.relative_to(REPO_ROOT)),
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows for core baseline, "
            "plus production paper-sleeve replay over the same OHLCV snapshots. "
            "Core replay uses REPLAY_PARTIAL_REDUCES and REGIME_AWARE_EXIT."
        ),
        "date_range": {
            "primary": {"start": WINDOWS["late_strong"]["start"], "end": WINDOWS["late_strong"]["end"]},
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
            if status == "accepted"
            else "No notional variant cleared the three-window risk-allocation gate."
        ),
        "next_evidence_needed": (
            "Forward default-off paper replacement-value evidence before any live-order scope."
        ),
        "production_impact": {
            "shared_policy_changed": status == "accepted",
            "backtester_adapter_changed": False,
            "run_adapter_changed": status == "accepted",
            "replay_only": False,
            "parity_test_added": status == "accepted",
            "default_off_paper_only": True,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": True,
        },
        "variants": variants,
        "why_not_other_changes": (
            "LLM soft-ranking and SEC filing-shock data remain field-limited; "
            "nearby SEC hold days, form-base exclusion, and raw candidate capacity "
            "have already been tested. This run changes only the event paper "
            "risk budget after the accepted quality floor."
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
                f"# {EXPERIMENT_ID} SEC financial-report event notional",
                "",
                f"- Decision: `{decision}`",
                f"- Best variant: `{best_key}`",
                f"- EV delta: `{payload['expected_value_score_delta']}`",
                f"- Total PnL delta: `{gate['aggregate_delta'].get('total_pnl_sum_delta')}`",
                f"- Max drawdown delta max: `{gate['max_drawdown_delta_max']}`",
                f"- Closed sleeve trades after: `{gate['sleeve_closed_trade_count_after']}`",
                "",
                "This is a default-off paper sleeve risk-allocation experiment. It changes no live orders.",
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
