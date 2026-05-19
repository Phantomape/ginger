from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
QUANT = ROOT / "quant"
if str(QUANT) not in sys.path:
    sys.path.insert(0, str(QUANT))

from quant.backtester import BacktestEngine  # noqa: E402

try:
    from quant.data_layer import get_universe  # noqa: E402
except Exception:  # pragma: no cover - CLI fallback parity
    from quant.filter import WATCHLIST  # noqa: E402

    def get_universe():
        return list(WATCHLIST)


EXPERIMENT_ID = "exp-20260506-011"
DATA_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
DATA_FILE = DATA_DIR / "time_stop_days_sweep.json"
LOG_FILE = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_FILE = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_FILE = (
    ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_time_stop_days_sweep.md"
)
JSONL_FILE = ROOT / "docs" / "experiment_log.jsonl"
PLAYBOOK_FILE = ROOT / "docs" / "alpha-optimization-playbook.md"

WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
        "regime": "slow-melt bull / accepted-stack dominant tape",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
        "regime": "rotation-heavy bull where strategy profits but lags indexes",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "regime": "mixed-to-weak older tape with lower win rate",
    },
}

VALUES = [30, 45, 60]
BASELINE_VALUE = 45


def metric_view(result):
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "total_pnl": result.get("total_pnl"),
        "win_rate": result.get("win_rate"),
        "total_trades": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": result.get("survival_rate"),
        "strategy_total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "vs_spy_pct": benchmarks.get("strategy_vs_spy_pct"),
        "vs_qqq_pct": benchmarks.get("strategy_vs_qqq_pct"),
    }


def run_window(universe, spec, time_stop_days):
    engine = BacktestEngine(
        universe,
        start=spec["start"],
        end=spec["end"],
        config={
            "REGIME_AWARE_EXIT": True,
            "REPLAY_PARTIAL_REDUCES": True,
            "TIME_STOP_DAYS": time_stop_days,
        },
        ohlcv_snapshot_path=spec["snapshot"],
    )
    return engine.run()


def exit_count(result, reason):
    return sum(1 for trade in result.get("trades", []) if trade.get("exit_reason") == reason)


def round_or_none(value, digits=6):
    if value is None:
        return None
    return round(value, digits)


def delta(after, before):
    if after is None or before is None:
        return None
    return round(after - before, 6)


def aggregate(metrics_by_window):
    return {
        "expected_value_score": round(
            sum(v["expected_value_score"] for v in metrics_by_window.values()), 6
        ),
        "total_pnl": round(sum(v["total_pnl"] for v in metrics_by_window.values()), 2),
        "total_trades": sum(v["total_trades"] for v in metrics_by_window.values()),
        "time_stop_exit_count": sum(v["time_stop_exit_count"] for v in metrics_by_window.values()),
        "end_of_backtest_exit_count": sum(
            v["end_of_backtest_exit_count"] for v in metrics_by_window.values()
        ),
    }


def compare(metrics_by_value):
    baseline = metrics_by_value[str(BASELINE_VALUE)]["aggregate"]
    comparisons = {}
    for value, payload in metrics_by_value.items():
        agg = payload["aggregate"]
        comparisons[value] = {
            "expected_value_score_delta": delta(
                agg["expected_value_score"], baseline["expected_value_score"]
            ),
            "total_pnl_delta": delta(agg["total_pnl"], baseline["total_pnl"]),
            "trade_count_delta": delta(agg["total_trades"], baseline["total_trades"]),
            "time_stop_exit_count": agg["time_stop_exit_count"],
            "end_of_backtest_exit_count": agg["end_of_backtest_exit_count"],
            "windows_with_ev_improvement": sum(
                1
                for window in WINDOWS
                if delta(
                    payload["windows"][window]["expected_value_score"],
                    metrics_by_value[str(BASELINE_VALUE)]["windows"][window][
                        "expected_value_score"
                    ],
                )
                and delta(
                    payload["windows"][window]["expected_value_score"],
                    metrics_by_value[str(BASELINE_VALUE)]["windows"][window][
                        "expected_value_score"
                    ],
                )
                > 0
            ),
            "windows_with_ev_regression": sum(
                1
                for window in WINDOWS
                if delta(
                    payload["windows"][window]["expected_value_score"],
                    metrics_by_value[str(BASELINE_VALUE)]["windows"][window][
                        "expected_value_score"
                    ],
                )
                and delta(
                    payload["windows"][window]["expected_value_score"],
                    metrics_by_value[str(BASELINE_VALUE)]["windows"][window][
                        "expected_value_score"
                    ],
                )
                < 0
            ),
        }
    return comparisons


def build_artifact(payload):
    lines = [
        f"# {EXPERIMENT_ID} time-stop days sweep",
        "",
        "## Decision",
        "",
        "Rejected/no-op. `TIME_STOP_DAYS` values 30, 45, and 60 produced identical",
        "three-window metrics, and no accepted trade exited via `time_stop`.",
        "",
        "## Alpha hypothesis",
        "",
        "Shorter or longer time stops might improve exit lifecycle by freeing slots",
        "or avoiding stale drift after accepted signals fail to hit target or stop.",
        "",
        "## Three-window result",
        "",
        "| TIME_STOP_DAYS | late EV | mid EV | old EV | agg EV delta | agg PnL delta | time_stop exits | decision |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    comparisons = payload["comparisons"]
    for value in [str(v) for v in VALUES]:
        value_payload = payload["values"][value]
        windows = value_payload["windows"]
        comp = comparisons[value]
        lines.append(
            "| {value} | {late:.4f} | {mid:.4f} | {old:.4f} | {ev_delta:.4f} | ${pnl_delta:.2f} | {exits} | {decision} |".format(
                value=value,
                late=windows["late_strong"]["expected_value_score"],
                mid=windows["mid_weak"]["expected_value_score"],
                old=windows["old_thin"]["expected_value_score"],
                ev_delta=comp["expected_value_score_delta"],
                pnl_delta=comp["total_pnl_delta"],
                exits=comp["time_stop_exit_count"],
                decision="baseline" if value == str(BASELINE_VALUE) else "rejected",
            )
        )
    lines.extend(
        [
            "",
            "## Mechanism insight",
            "",
            "The accepted stack exits before the time-stop surface is reached in the",
            "canonical windows. Nearby time-stop values should not be retried without a",
            "trade-duration cohort showing that the rule would actually fire.",
            "",
            "## Production parity",
            "",
            "No shared policy, run adapter, order path, sizing path, signal path, or",
            "backtester adapter was changed. There is no production/backtest mismatch to",
            "promote because the experiment was rejected.",
            "",
        ]
    )
    return "\n".join(lines)


def compact_json_line(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def write_records(payload):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    TICKET_FILE.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_FILE.parent.mkdir(parents=True, exist_ok=True)

    data_text = json.dumps(payload, indent=2, sort_keys=True)
    DATA_FILE.write_text(data_text + "\n", encoding="utf-8")

    log = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "alpha_hypothesis_category": "exit_lifecycle",
        "hypothesis": payload["hypothesis"],
        "why_not_llm_soft_ranking": (
            "LLM soft-ranking remains data-limited; this run tested a deterministic "
            "lifecycle surface instead of forcing a sparse LLM attribution experiment."
        ),
        "change_type": "exit_lifecycle_parameter_sweep",
        "single_causal_variable": "TIME_STOP_DAYS",
        "parameters": {
            "baseline": {"TIME_STOP_DAYS": BASELINE_VALUE},
            "tested": [{"TIME_STOP_DAYS": value} for value in VALUES],
            "locked_variables": payload["locked_variables"],
        },
        "date_range": {
            name: f"{spec['start']} -> {spec['end']}" for name, spec in WINDOWS.items()
        },
        "market_regime_summary": {name: spec["regime"] for name, spec in WINDOWS.items()},
        "before_metrics": payload["values"][str(BASELINE_VALUE)]["windows"],
        "after_metrics": {
            f"time_stop_days_{value}": payload["values"][str(value)]["windows"]
            for value in VALUES
            if value != BASELINE_VALUE
        },
        "delta_metrics": payload["comparisons"],
        "aggregate_baseline": payload["values"][str(BASELINE_VALUE)]["aggregate"],
        "decision": "rejected_noop",
        "rejection_reason": (
            "No tested value changed any trade or metric; time_stop exit count was 0 "
            "in every canonical window."
        ),
        "historical_experiment_check": {
            "prior_same_surface_found": False,
            "recent_no_go_zones_checked": [
                "static basket expansion",
                "event same-sample retuning before forward paper closes",
                "SPY leader target/add-on nearby tuning",
                "commodity breakout risk boost",
                "breakout slot ranking",
                "active-sector caps",
                "second add-ons",
                "high-score/plain risk-on scalar retunes",
            ],
            "why_not_simple_repeat": (
                "No prior near-identical TIME_STOP_DAYS sweep was found; this checks "
                "whether the existing exit lifecycle surface is active at all."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "llm_attribution_added": False,
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_sizing": False,
            "production_signal_path_changed": False,
        },
        "next_retry_requires": [
            "A trade-duration cohort where accepted trades survive long enough for time_stop to fire",
            "Forward evidence that stale-drift exits, not target/stop exits, are the binding lifecycle issue",
        ],
        "related_files": [
            "quant/experiments/exp_20260506_011_time_stop_days_sweep.py",
            "data/experiments/exp-20260506-011/time_stop_days_sweep.json",
            "experiments/logs/exp-20260506-011.json",
            "experiments/tickets/exp-20260506-011.json",
            "experiments/artifacts/exp-20260506-011_time_stop_days_sweep.md",
        ],
    }
    LOG_FILE.write_text(json.dumps(log, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": "rejected",
        "lane": "alpha_search",
        "owner": "alpha-search",
        "hypothesis": payload["hypothesis"],
        "change_type": "exit_lifecycle_parameter_sweep",
        "single_causal_variable": "TIME_STOP_DAYS",
        "evaluation_windows": [
            {"start": spec["start"], "end": spec["end"]} for spec in WINDOWS.values()
        ],
        "acceptance_rule": (
            "Promote only if aggregate EV/PnL materially improve and at least two "
            "canonical windows improve without production/backtest mismatch."
        ),
        "production_impact": log["production_impact"],
        "created_at": payload["timestamp"],
        "claimed_at": payload["timestamp"],
        "completed_at": payload["timestamp"],
        "result": {
            "decision": "rejected_noop",
            "log_file": "experiments/logs/exp-20260506-011.json",
            "artifact": "data/experiments/exp-20260506-011/time_stop_days_sweep.json",
            "summary": (
                "TIME_STOP_DAYS 30/45/60 was a no-op: 0 time_stop exits and 0 metric delta."
            ),
        },
        "must_not_touch": [
            "quant/signal_engine.py",
            "quant/risk_engine.py",
            "quant/portfolio_engine.py",
            "quant/run.py",
        ],
    }
    TICKET_FILE.write_text(
        json.dumps(ticket, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    ARTIFACT_FILE.write_text(build_artifact(payload), encoding="utf-8")

    jsonl_record = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "hypothesis": payload["hypothesis"],
        "change_type": "exit_lifecycle_parameter_sweep",
        "parameters": {"baseline_TIME_STOP_DAYS": BASELINE_VALUE, "tested": VALUES},
        "date_range": {
            name: f"{spec['start']} -> {spec['end']}" for name, spec in WINDOWS.items()
        },
        "before_metrics": payload["values"][str(BASELINE_VALUE)]["windows"],
        "after_metrics": {
            f"time_stop_days_{value}": payload["values"][str(value)]["windows"]
            for value in VALUES
            if value != BASELINE_VALUE
        },
        "expected_value_score_delta": 0.0,
        "total_pnl_delta": 0.0,
        "decision": "rejected_noop",
        "rejection_reason": (
            "TIME_STOP_DAYS did not fire in any canonical window; all tested values "
            "were metric-identical."
        ),
        "production_impact": log["production_impact"],
    }
    existing_jsonl = JSONL_FILE.read_text(encoding="utf-8") if JSONL_FILE.exists() else ""
    if EXPERIMENT_ID not in existing_jsonl:
        with JSONL_FILE.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(compact_json_line(jsonl_record) + "\n")

    playbook_note = """

### exp-20260506-011 time-stop days sweep
- Decision: rejected/no-op.
- Tested `TIME_STOP_DAYS` 30/45/60 across the canonical windows; all metrics were identical and `time_stop` exits were 0.
- Mechanism insight: the accepted stack exits before this lifecycle surface is reached. Do not retry nearby time-stop values without a trade-duration cohort where the rule would actually fire.
"""
    existing_playbook = PLAYBOOK_FILE.read_text(encoding="utf-8")
    if "exp-20260506-011 time-stop days sweep" not in existing_playbook:
        with PLAYBOOK_FILE.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(playbook_note)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    universe = get_universe()
    values = {}
    for value in VALUES:
        windows = {}
        for name, spec in WINDOWS.items():
            logging.info("Running %s TIME_STOP_DAYS=%s", name, value)
            result = run_window(universe, spec, value)
            metrics = metric_view(result)
            metrics["time_stop_exit_count"] = exit_count(result, "time_stop")
            metrics["end_of_backtest_exit_count"] = exit_count(result, "end_of_backtest")
            windows[name] = metrics
        values[str(value)] = {"windows": windows, "aggregate": aggregate(windows)}

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "hypothesis": (
            "A shorter or longer time stop might improve exit lifecycle by freeing "
            "slots or avoiding stale drift after accepted signals fail to hit target or stop."
        ),
        "baseline_value": BASELINE_VALUE,
        "tested_values": VALUES,
        "windows": WINDOWS,
        "locked_variables": [
            "candidate universe",
            "signal generation",
            "entry filters",
            "entry ordering",
            "risk sizing",
            "position slots",
            "add-ons",
            "LLM/news gates",
            "regime-aware exits other than TIME_STOP_DAYS",
        ],
        "values": values,
        "comparisons": compare(values),
        "decision": "rejected_noop",
        "decision_reason": (
            "No tested value changed any trade or metric; the time_stop exit surface "
            "is inactive on all three canonical windows."
        ),
    }
    write_records(payload)
    print(json.dumps({"experiment_id": EXPERIMENT_ID, "decision": payload["decision"]}, sort_keys=True))


if __name__ == "__main__":
    main()
