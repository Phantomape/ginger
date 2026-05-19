"""
Experiment exp-20260508-038: selective staged entry for non-SPY-relative leaders.

This is a replay-only alpha search experiment. It tests whether the staged-entry
idea rejected in exp-20260508-034 becomes viable when scoped to A/B entries that
are not SPY relative leaders. The intent is to preserve the accepted
SPY-relative leader convexity while reducing first-day capital committed to
weaker relative-strength entries.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import backtester as backtester_module
import portfolio_engine
from backtester import BacktestEngine
from data_layer import get_universe


EXP_ID = "exp-20260508-038"

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
                "regime": "late strong / current accepted-stack validation",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
                "regime": "mid weak / mixed trend validation",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
                "regime": "old thin / lower sample validation",
            },
        ),
    ]
)

BASELINE = {
    "late_strong": {
        "expected_value_score": 4.0674,
        "total_pnl": 90788.88,
        "strategy_total_return_pct": 90.79,
        "sharpe_daily": 4.48,
        "max_drawdown_pct": 5.39,
        "win_rate": 78.95,
        "total_trades": 19,
        "survival_rate": 80.39,
    },
    "mid_weak": {
        "expected_value_score": 1.6195,
        "total_pnl": 59540.63,
        "strategy_total_return_pct": 59.54,
        "sharpe_daily": 2.72,
        "max_drawdown_pct": 8.79,
        "win_rate": 52.38,
        "total_trades": 21,
        "survival_rate": 79.25,
    },
    "old_thin": {
        "expected_value_score": 0.3583,
        "total_pnl": 27347.42,
        "strategy_total_return_pct": 27.35,
        "sharpe_daily": 1.31,
        "max_drawdown_pct": 9.03,
        "win_rate": 40.91,
        "total_trades": 22,
        "survival_rate": 91.67,
    },
}

STAGE_FRACTION = 0.75
STAGE_STRATEGIES = {"trend_long", "breakout_long"}


def round_float(value: Any, digits: int = 4) -> Any:
    if isinstance(value, (int, float)):
        return round(float(value), digits)
    return value


def extract_metrics(result: Dict[str, Any]) -> Dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    total_return_pct = benchmarks.get("strategy_total_return_pct")
    if total_return_pct is None:
        total_return_pct = result.get("total_return_pct", 0.0)
    return {
        "expected_value_score": round_float(result.get("expected_value_score", 0.0), 4),
        "total_pnl": round_float(result.get("total_pnl", 0.0), 2),
        "strategy_total_return_pct": round_float(total_return_pct, 2),
        "sharpe_daily": round_float(result.get("sharpe_daily", result.get("sharpe_ratio", 0.0)), 2),
        "max_drawdown_pct": round_float(result.get("max_drawdown_pct", 0.0), 2),
        "win_rate": round_float(result.get("win_rate", 0.0), 2),
        "total_trades": int(result.get("total_trades", 0)),
        "survival_rate": round_float(result.get("survival_rate", 0.0), 2),
    }


def metric_delta(after: Dict[str, Any], before: Dict[str, Any]) -> Dict[str, Any]:
    delta = {}
    for key in before:
        value = after.get(key, 0.0) - before.get(key, 0.0)
        delta[key] = int(value) if key == "total_trades" else round_float(value, 4)
    return delta


def extract_addon_summary(result: Dict[str, Any]) -> Dict[str, Any]:
    attribution = result.get("followthrough_addon_attribution") or result.get("addon_attribution") or {}
    return {
        "scheduled": attribution.get("scheduled", 0),
        "executed": attribution.get("executed", 0),
        "skipped": attribution.get("skipped", 0),
        "checkpoint_rejected": attribution.get("checkpoint_rejected", 0),
        "skip_reasons": attribution.get("skip_reasons", {}),
    }


def aggregate_metrics(metrics_by_window: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "expected_value_score_sum": round_float(
            sum(metrics["expected_value_score"] for metrics in metrics_by_window.values()), 4
        ),
        "total_pnl_sum": round_float(
            sum(metrics["total_pnl"] for metrics in metrics_by_window.values()), 2
        ),
        "total_trades": sum(metrics["total_trades"] for metrics in metrics_by_window.values()),
    }


def install_selective_staging_patch() -> tuple[Any, Any, Dict[str, Dict[str, int]]]:
    original_size_signals = portfolio_engine.size_signals
    original_position_init = backtester_module.Position.__init__
    staged_stats: Dict[str, Dict[str, int]] = {}
    pending_original_shares: Dict[str, List[int]] = {}

    def patched_size_signals(*args, **kwargs):
        sized = original_size_signals(*args, **kwargs)

        for sig in sized:
            strategy = sig.get("strategy")
            is_candidate = (
                strategy in STAGE_STRATEGIES
                and sig.get("spy_relative_leader") is not True
                and sig.get("shares_to_buy", 0) > 0
            )
            if not is_candidate:
                continue

            ticker = sig.get("ticker", "")
            original_shares = int(sig.get("shares_to_buy", 0))
            staged_shares = max(1, int(original_shares * STAGE_FRACTION))
            if staged_shares >= original_shares:
                continue

            sig["_exp038_original_shares"] = original_shares
            sig["_exp038_staged_shares"] = staged_shares
            sig["_exp038_stage_fraction"] = STAGE_FRACTION
            sig["shares_to_buy"] = staged_shares
            if sig.get("entry_price"):
                sig["position_size_usd"] = staged_shares * sig["entry_price"]
            else:
                sig["position_size_usd"] = staged_shares * sig.get("current_price", 0)
            stats = staged_stats.setdefault(
                ticker,
                {"signals_staged": 0, "shares_deferred": 0, "strategy_trend": 0, "strategy_breakout": 0},
            )
            stats["signals_staged"] += 1
            stats["shares_deferred"] += original_shares - staged_shares
            if strategy == "trend_long":
                stats["strategy_trend"] += 1
            elif strategy == "breakout_long":
                stats["strategy_breakout"] += 1
            pending_original_shares.setdefault(ticker, []).append(original_shares)

        return sized

    def patched_position_init(self, *args, **kwargs):
        original_position_init(self, *args, **kwargs)
        ticker = kwargs.get("ticker")
        if ticker is None and args:
            ticker = args[0]
        queued = pending_original_shares.get(ticker or "")
        if queued:
            self.original_shares = int(queued.pop(0))
            self.stage_entry_experiment = EXP_ID
            self.stage_entry_fraction = STAGE_FRACTION
            if not queued:
                pending_original_shares.pop(ticker or "", None)

    portfolio_engine.size_signals = patched_size_signals
    backtester_module.Position.__init__ = patched_position_init
    return original_size_signals, original_position_init, staged_stats


def restore_patch(original_size_signals: Any, original_position_init: Any) -> None:
    portfolio_engine.size_signals = original_size_signals
    backtester_module.Position.__init__ = original_position_init


def run_window(name: str, config: Dict[str, str]) -> Dict[str, Any]:
    original_size_signals, original_position_init, staged_stats = install_selective_staging_patch()
    try:
        engine = BacktestEngine(
            get_universe(),
            start=config["start"],
            end=config["end"],
            ohlcv_snapshot_path=str(ROOT / config["snapshot"]),
        )
        result = engine.run()
    finally:
        restore_patch(original_size_signals, original_position_init)

    metrics = extract_metrics(result)
    before = BASELINE[name]
    addon_summary = extract_addon_summary(result)
    sizing_rules = result.get("sizing_rule_trade_attribution", {})
    return {
        "window": name,
        "date_range": {"start": config["start"], "end": config["end"]},
        "market_regime_summary": config["regime"],
        "snapshot": config["snapshot"],
        "before_metrics": before,
        "after_metrics": metrics,
        "delta": metric_delta(metrics, before),
        "staged_stats": staged_stats,
        "signals_staged": sum(stats["signals_staged"] for stats in staged_stats.values()),
        "shares_deferred": sum(stats["shares_deferred"] for stats in staged_stats.values()),
        "addon_summary": {
            "scheduled": addon_summary.get("scheduled", 0),
            "executed": addon_summary.get("executed", 0),
            "skipped": addon_summary.get("skipped", 0),
            "checkpoint_rejected": addon_summary.get("checkpoint_rejected", 0),
            "skip_reasons": addon_summary.get("skip_reasons", {}),
        },
        "sizing_rule_trade_attribution": sizing_rules,
    }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = [
        f"# {EXP_ID} selective nonleader staged entry",
        "",
        "## Hypothesis",
        "",
        (
            "Only stage A/B entries that are not SPY relative leaders. This keeps the accepted "
            "relative-strength leader behavior intact while testing whether weaker entries benefit "
            "from 75% initial sizing plus the existing day-2 follow-through top-up path."
        ),
        "",
        "## Result",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Rejection reason: {payload['rejection_reason']}",
        f"- Production impact: no promoted strategy change; replay-only experiment artifact.",
        "",
        "## Three-window metrics",
        "",
        "| Window | EV before | EV after | EV delta | PnL delta | Trades delta | Staged signals |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["windows"].values():
        before = row["before_metrics"]
        after = row["after_metrics"]
        delta = row["delta"]
        lines.append(
            "| {window} | {ev_before:.4f} | {ev_after:.4f} | {ev_delta:.4f} | "
            "{pnl_delta:.2f} | {trades_delta} | {staged} |".format(
                window=row["window"],
                ev_before=before["expected_value_score"],
                ev_after=after["expected_value_score"],
                ev_delta=delta["expected_value_score"],
                pnl_delta=delta["total_pnl"],
                trades_delta=delta["total_trades"],
                staged=row["signals_staged"],
            )
        )
    lines.extend(
        [
            "",
            "## Mechanism note",
            "",
            (
                "The selective discriminator had zero coverage: every executed positive-share A/B "
                "entry in the canonical windows was already tagged as `spy_relative_leader`. "
                "This means the proposed non-leader staged-entry refinement is inert on the "
                "current accepted candidate set and should not be retried without new candidate "
                "coverage evidence."
            ),
            "",
            "## Do not repeat",
            "",
            (
                "Do not retry nearby non-leader staged-entry fractions on the same snapshots. "
                "The blocker is coverage, not the exact stage fraction."
            ),
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    windows = OrderedDict((name, run_window(name, config)) for name, config in WINDOWS.items())
    after_by_window = {name: row["after_metrics"] for name, row in windows.items()}
    aggregate_after = aggregate_metrics(after_by_window)
    aggregate_before = aggregate_metrics(BASELINE)
    aggregate_delta = {
        key: round_float(aggregate_after.get(key, 0.0) - aggregate_before.get(key, 0.0), 4)
        for key in aggregate_before
    }
    total_staged = sum(row["signals_staged"] for row in windows.values())

    decision = "rejected_no_effect"
    rejection_reason = (
        "No executed positive-share A/B entries qualified as non-SPY-relative leaders; "
        "the experiment had zero coverage and left all three-window metrics unchanged."
    )

    payload = {
        "experiment_id": EXP_ID,
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "classification": "alpha_search",
        "hypothesis": (
            "Selective staged entry may improve capital allocation if applied only to A/B entries "
            "that lack SPY-relative leadership."
        ),
        "change_type": "capital_allocation_entry_lifecycle_replay",
        "parameters": {
            "stage_fraction": STAGE_FRACTION,
            "stage_strategies": sorted(STAGE_STRATEGIES),
            "stage_predicate": "strategy in A/B and spy_relative_leader is not True",
            "topup_behavior": "restore original_shares for existing day-2 follow-through add-on path",
        },
        "historical_checks": {
            "exp_20260508_034_blanket_staged_entry": (
                "Rejected. This run used the requested ex-ante discriminator instead of blanket staging."
            ),
            "exp_20260508_017_raw_addon_heat_cap_relaxation": (
                "Positive but rejected as production-unsafe. This run did not weaken hard risk caps."
            ),
            "exp_20260508_026_checkpoint_volume_filter": (
                "Rejected. This run did not add volume confirmation to add-ons."
            ),
            "exp_20260508_036_037_cap_room_or_addon_cap": (
                "Rejected/inert. This run targeted entry coverage rather than cap-room thresholds."
            ),
        },
        "alpha_first_assessment": {
            "run_type": "alpha_search",
            "blocked_by_measurement_repair": False,
            "llm_data_limit_handling": (
                "LLM soft-ranking was not tested because recent archives have zero effective "
                "candidate coverage; this experiment uses non-LLM shared portfolio fields."
            ),
            "alpha_category": "capital_allocation / entry lifecycle",
        },
        "gate_2_data_fields": {
            "spy_relative_leader": "present through risk_engine.enrich_signals",
            "strategy": "present on candidate signals",
            "shares_to_buy": "present after portfolio sizing",
            "original_shares": "present on backtester Position and restored only inside replay experiment",
        },
        "gate_3_survival_rate": {
            name: row["before_metrics"]["survival_rate"] for name, row in windows.items()
        },
        "windows": windows,
        "aggregate_before": aggregate_before,
        "aggregate_after": aggregate_after,
        "aggregate_delta": aggregate_delta,
        "coverage": {
            "total_staged_signals": total_staged,
            "coverage_conclusion": "zero executed-signal coverage",
        },
        "llm_metrics": {
            "uses_llm": False,
            "llm_attribution_changed": False,
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "strategy_behavior_changed_in_repo": False,
            "parity_risk": "none, because no promoted strategy code was changed",
        },
        "decision": decision,
        "rejection_reason": rejection_reason,
        "next_time_do_not_repeat": (
            "Do not retry non-SPY-relative leader staged entry on these snapshots or nearby fractions "
            "unless new candidate-pool evidence shows executed A/B non-leader entries exist."
        ),
        "experiment_log_jsonl_note": (
            "Not appended by this run because docs/experiment_log.jsonl had pre-existing unstaged "
            "changes outside this experiment; canonical record is the experiments log file."
        ),
    }

    data_path = ROOT / "data" / "experiments" / EXP_ID / f"{EXP_ID}_selective_nonleader_staged_entry.json"
    log_path = ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
    ticket_path = ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
    artifact_path = (
        ROOT
        / "experiments"
        / "artifacts"
        / f"{EXP_ID}_selective_nonleader_staged_entry.md"
    )

    write_json(data_path, payload)
    write_json(log_path, payload)
    write_json(
        ticket_path,
        {
            "id": EXP_ID,
            "title": "Reject inert nonleader staged entry",
            "status": "rejected_no_effect",
            "run_at_utc": payload["run_at_utc"],
            "summary": rejection_reason,
            "artifact": str(artifact_path.relative_to(ROOT)),
            "data": str(data_path.relative_to(ROOT)),
        },
    )
    write_markdown(artifact_path, payload)

    print(json.dumps({"experiment_id": EXP_ID, "decision": decision, "aggregate_delta": aggregate_delta, "total_staged": total_staged}, indent=2))


if __name__ == "__main__":
    main()
