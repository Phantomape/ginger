"""exp-20260501-017 Technology A/B cofire trend preference.

Alpha search. Test one candidate-routing variable: when a Technology ticker
simultaneously qualifies for trend_long and breakout_long on the same day,
prefer the trend_long sleeve so the accepted Technology trend wider-target
lifecycle can operate. Standalone Technology breakouts are unchanged.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import signal_engine  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
from risk_engine import SECTOR_MAP  # noqa: E402


EXPERIMENT_ID = "exp-20260501-017"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "tech_cofire_trend_preference.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
        "state_note": "slow-melt bull / accepted-stack dominant tape",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
        "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "state_note": "mixed-to-weak older tape with lower win rate",
    }),
])

VARIANTS = OrderedDict([
    ("baseline_native_dedup", False),
    ("tech_cofire_prefer_trend", True),
])

_state = {
    "tech_breakouts_suppressed": 0,
}


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    tech_trade_count = 0
    tech_trade_pnl = 0.0
    tech_trend_count = 0
    tech_breakout_count = 0
    for trade in result.get("trades", []):
        if trade.get("sector") == "Technology":
            tech_trade_count += 1
            tech_trade_pnl += float(trade.get("pnl") or 0.0)
            if trade.get("strategy") == "trend_long":
                tech_trend_count += 1
            elif trade.get("strategy") == "breakout_long":
                tech_breakout_count += 1
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
        "tail_loss_share": result.get("tail_loss_share"),
        "tech_trade_count": tech_trade_count,
        "tech_trade_pnl": round(tech_trade_pnl, 2),
        "tech_trend_trade_count": tech_trend_count,
        "tech_breakout_trade_count": tech_breakout_count,
        "tech_breakouts_suppressed": _state["tech_breakouts_suppressed"],
    }


def _delta(after: dict, before: dict) -> dict:
    out = {}
    for key, before_value in before.items():
        after_value = after.get(key)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            out[key] = round(after_value - before_value, 6)
        else:
            out[key] = None
    return out


@contextmanager
def _tech_cofire_patch(enabled: bool):
    original_breakout = signal_engine.strategy_b_breakout

    def patched_breakout(ticker, features, market_context=None, breakout_max_pullback_from_52w_high=None):
        signal = original_breakout(
            ticker,
            features,
            market_context=market_context,
            breakout_max_pullback_from_52w_high=breakout_max_pullback_from_52w_high,
        )
        if not enabled or signal is None:
            return signal
        if SECTOR_MAP.get(ticker) != "Technology":
            return signal
        trend_signal = signal_engine.strategy_a_trend(
            ticker,
            features,
            market_context=market_context,
        )
        if trend_signal is None:
            return signal
        _state["tech_breakouts_suppressed"] += 1
        return None

    signal_engine.strategy_b_breakout = patched_breakout
    try:
        yield
    finally:
        signal_engine.strategy_b_breakout = original_breakout


def _run_window(universe: list[str], cfg: dict, prefer_trend: bool) -> dict:
    _state["tech_breakouts_suppressed"] = 0
    with _tech_cofire_patch(prefer_trend):
        result = BacktestEngine(
            universe=universe,
            start=cfg["start"],
            end=cfg["end"],
            config={"REGIME_AWARE_EXIT": True},
            replay_llm=False,
            replay_news=False,
            data_dir=str(REPO_ROOT / "data"),
            ohlcv_snapshot_path=str(REPO_ROOT / cfg["snapshot"]),
        ).run()
    if "error" in result:
        raise RuntimeError(result["error"])
    return {"metrics": _metrics(result), "trades": result.get("trades", [])}


def _aggregate(before: OrderedDict, after: OrderedDict) -> dict:
    deltas = OrderedDict(
        (label, _delta(after[label]["metrics"], before[label]["metrics"]))
        for label in WINDOWS
    )
    baseline_total_pnl = round(
        sum(before[label]["metrics"]["total_pnl"] for label in WINDOWS), 2
    )
    total_pnl_delta = round(sum(d["total_pnl"] for d in deltas.values()), 2)
    baseline_ev = round(
        sum(before[label]["metrics"]["expected_value_score"] for label in WINDOWS),
        6,
    )
    ev_delta = round(sum(d["expected_value_score"] for d in deltas.values()), 6)
    return {
        "by_window": deltas,
        "expected_value_score_delta_sum": ev_delta,
        "expected_value_score_delta_pct": round(ev_delta / baseline_ev, 6) if baseline_ev else None,
        "baseline_expected_value_score_sum": baseline_ev,
        "total_pnl_delta_sum": total_pnl_delta,
        "baseline_total_pnl_sum": baseline_total_pnl,
        "total_pnl_delta_pct": round(total_pnl_delta / baseline_total_pnl, 6) if baseline_total_pnl else None,
        "ev_windows_improved": sum(1 for d in deltas.values() if d["expected_value_score"] > 0),
        "ev_windows_regressed": sum(1 for d in deltas.values() if d["expected_value_score"] < 0),
        "pnl_windows_improved": sum(1 for d in deltas.values() if d["total_pnl"] > 0),
        "pnl_windows_regressed": sum(1 for d in deltas.values() if d["total_pnl"] < 0),
        "max_drawdown_delta_max": max(d["max_drawdown_pct"] for d in deltas.values()),
        "trade_count_delta_sum": sum(d["trade_count"] for d in deltas.values()),
        "win_rate_delta_min": min(d["win_rate"] for d in deltas.values()),
        "sharpe_daily_delta_max": max(d["sharpe_daily"] for d in deltas.values()),
        "tech_breakouts_suppressed_delta_sum": sum(
            d["tech_breakouts_suppressed"] for d in deltas.values()
        ),
    }


def _passes_gate4(aggregate: dict) -> bool:
    if aggregate["ev_windows_improved"] < 2 or aggregate["ev_windows_regressed"] > 0:
        return False
    if aggregate["expected_value_score_delta_pct"] and aggregate["expected_value_score_delta_pct"] > 0.10:
        return True
    if aggregate["total_pnl_delta_pct"] and aggregate["total_pnl_delta_pct"] > 0.05:
        return True
    if aggregate["sharpe_daily_delta_max"] > 0.10:
        return True
    if aggregate["max_drawdown_delta_max"] < -0.01:
        return True
    if aggregate["trade_count_delta_sum"] > 0 and aggregate["win_rate_delta_min"] >= 0:
        return True
    return False


def build_payload() -> dict:
    universe = get_universe()
    rows = OrderedDict()
    for variant, prefer_trend in VARIANTS.items():
        rows[variant] = OrderedDict()
        for label, cfg in WINDOWS.items():
            rows[variant][label] = _run_window(universe, cfg, prefer_trend)
            m = rows[variant][label]["metrics"]
            print(
                f"[{label} {variant}] EV={m['expected_value_score']} "
                f"PnL={m['total_pnl']} SharpeD={m['sharpe_daily']} "
                f"WR={m['win_rate']} trades={m['trade_count']} "
                f"tech_suppressed={m['tech_breakouts_suppressed']}"
            )

    baseline = rows["baseline_native_dedup"]
    variants = OrderedDict()
    for variant in list(VARIANTS.keys())[1:]:
        aggregate = _aggregate(baseline, rows[variant])
        variants[variant] = {
            "rows": rows[variant],
            "aggregate": aggregate,
            "passes_gate4": _passes_gate4(aggregate),
        }
    best_variant, best = max(
        variants.items(),
        key=lambda item: (
            item[1]["aggregate"]["ev_windows_improved"],
            -item[1]["aggregate"]["ev_windows_regressed"],
            item[1]["aggregate"]["expected_value_score_delta_sum"],
            item[1]["aggregate"]["total_pnl_delta_sum"],
        ),
    )
    accepted = best["passes_gate4"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "accepted_candidate" if accepted else "rejected",
        "decision": "accepted_candidate" if accepted else "rejected",
        "lane": "alpha_search",
        "change_type": "candidate_routing_technology_ab_cofire_prefer_trend",
        "hypothesis": (
            "When a Technology ticker co-fires trend_long and breakout_long, the "
            "trend_long sleeve may deserve priority because the accepted Technology "
            "trend wider target captures winners better than the generic breakout path."
        ),
        "alpha_hypothesis_category": "entry_routing_lifecycle",
        "why_not_llm_soft_ranking": (
            "Production-aligned LLM ranking samples remain too thin, so this tests "
            "a deterministic lifecycle/routing rule using existing signal fields."
        ),
        "parameters": {
            "single_causal_variable": "Technology same-ticker A/B cofire dedup preference",
            "baseline": "highest-confidence native dedup",
            "tested_variant": "suppress Technology breakout_long only when strategy_a_trend also fires",
            "locked_variables": [
                "universe",
                "standalone trend_long signals",
                "standalone breakout_long signals",
                "non-Technology A/B cofire handling",
                "confidence scores",
                "risk sizing",
                "candidate ranking after dedup",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "MAX_PER_SECTOR",
                "gap cancels",
                "add-ons",
                "all exits",
                "LLM/news replay",
                "earnings strategy",
            ],
        },
        "date_range": {
            "primary": f"{WINDOWS['late_strong']['start']} -> {WINDOWS['late_strong']['end']}",
            "secondary": [
                f"{WINDOWS['mid_weak']['start']} -> {WINDOWS['mid_weak']['end']}",
                f"{WINDOWS['old_thin']['start']} -> {WINDOWS['old_thin']['end']}",
            ],
        },
        "market_regime_summary": {
            label: cfg["state_note"] for label, cfg in WINDOWS.items()
        },
        "before_metrics": {
            label: baseline[label]["metrics"] for label in WINDOWS
        },
        "after_metrics": {
            best_variant: {
                label: best["rows"][label]["metrics"] for label in WINDOWS
            }
        },
        "delta_metrics": {
            name: variant["aggregate"] for name, variant in variants.items()
        },
        "best_variant": best_variant,
        "best_variant_gate4": accepted,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, implement the same Technology cofire preference in "
                "signal_engine.generate_signals so run.py and backtester.py share it."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft-ranking remains sample-limited; this is an alternate "
                "deterministic alpha search."
            ),
        },
        "history_guardrails": {
            "not_global_trend_first": True,
            "not_breakout_subsequence_sort_retry": True,
            "not_technology_target_width_sweep": True,
            "not_universe_expansion": True,
            "why_not_simple_repeat": (
                "This is not the rejected global same-day trend-first ordering. "
                "It changes only same-ticker Technology A/B cofires and leaves "
                "standalone breakouts plus all non-Technology cofires untouched."
            ),
        },
        "rejection_reason": (
            None if accepted else
            "Technology A/B cofire trend preference did not pass fixed-window Gate 4."
        ),
        "next_retry_requires": [
            "Do not retry global same-day trend-first from this result.",
            "Do not retry nearby Technology cofire routing without forward or event evidence.",
            "If accepted later, promote only through shared signal_engine dedup logic.",
        ],
        "related_files": [
            "quant/experiments/exp_20260501_017_tech_cofire_trend_preference.py",
            "data/experiments/exp-20260501-017/tech_cofire_trend_preference.json",
            "docs/experiments/logs/exp-20260501-017.json",
            "docs/experiments/tickets/exp-20260501-017.json",
        ],
    }


def main() -> int:
    payload = build_payload()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2)
    OUT_JSON.write_text(text, encoding="utf-8")
    LOG_JSON.write_text(text, encoding="utf-8")
    TICKET_JSON.write_text(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "title": "Technology cofire trend preference",
        "summary": (
            f"Best {payload['best_variant']} "
            f"Gate4={payload['best_variant_gate4']}"
        ),
        "best_variant": payload["best_variant"],
        "delta_metrics": payload["delta_metrics"][payload["best_variant"]],
        "production_impact": payload["production_impact"],
    }, indent=2), encoding="utf-8")
    with (REPO_ROOT / "docs" / "experiment_log.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, separators=(",", ":")) + "\n")
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "best_variant": payload["best_variant"],
        "best_gate4": payload["best_variant_gate4"],
        "best_delta": payload["delta_metrics"][payload["best_variant"]],
        "artifact": str(OUT_JSON),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
