"""exp-20260501-019 precious-metals breakout target width.

Alpha search. Trend gold target widening is accepted, but that does not imply
breakout_long precious-metals entries should also use wider exits. This
experiment changes one causal variable: ATR target width for GLD/IAU/SLV
breakout_long signals. Entries, ranking, sizing, slots, add-ons, LLM/news
replay, and trend target widths remain locked.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import risk_engine as re  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
from risk_engine import _retarget_signal_with_atr_mult  # noqa: E402


EXPERIMENT_ID = "exp-20260501-019"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "precious_breakout_target_width.json"
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

PRECIOUS_BREAKOUT_TICKERS = ("GLD", "IAU", "SLV")
BASELINE_TARGET_ATR = 4.5
TESTED_TARGETS = OrderedDict([
    ("precious_breakout_5_5atr", 5.5),
    ("precious_breakout_6_0atr", 6.0),
    ("precious_breakout_7_0atr", 7.0),
])

_state = {
    "target_atr": None,
    "retargeted_signals": 0,
}


def _patched_enrich_signals(signals, features_dict, atr_target_mult=None):
    enriched = _original_enrich_signals(
        signals,
        features_dict,
        atr_target_mult=atr_target_mult,
    )
    target_atr = _state.get("target_atr")
    if target_atr is None:
        return enriched

    out = []
    for sig in enriched:
        ticker = sig.get("ticker")
        if (
            sig.get("strategy") == "breakout_long"
            and ticker in PRECIOUS_BREAKOUT_TICKERS
        ):
            atr = (features_dict.get(ticker) or {}).get("atr")
            if atr:
                sig = _retarget_signal_with_atr_mult(sig, atr, target_atr)
                sig["precious_breakout_target_width_applied"] = target_atr
                _state["retargeted_signals"] += 1
        out.append(sig)
    return out


def _install_patch():
    global _original_enrich_signals
    _original_enrich_signals = re.enrich_signals
    re.enrich_signals = _patched_enrich_signals


def _remove_patch():
    re.enrich_signals = _original_enrich_signals


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    precious_breakout_trades = [
        t for t in result.get("trades", [])
        if t.get("strategy") == "breakout_long"
        and t.get("ticker") in PRECIOUS_BREAKOUT_TICKERS
    ]
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
        "precious_breakout_trade_count": len(precious_breakout_trades),
        "precious_breakout_pnl": round(
            sum(float(t.get("pnl") or 0.0) for t in precious_breakout_trades),
            2,
        ),
        "retargeted_signals": _state["retargeted_signals"],
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


def _run_window(universe: list[str], cfg: dict, target_atr: float | None) -> dict:
    _state["target_atr"] = target_atr
    _state["retargeted_signals"] = 0
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
        sum(before[label]["metrics"]["total_pnl"] for label in WINDOWS),
        2,
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
        "expected_value_score_delta_pct": round(ev_delta / baseline_ev, 6),
        "baseline_expected_value_score_sum": baseline_ev,
        "total_pnl_delta_sum": total_pnl_delta,
        "baseline_total_pnl_sum": baseline_total_pnl,
        "total_pnl_delta_pct": round(total_pnl_delta / baseline_total_pnl, 6),
        "ev_windows_improved": sum(1 for d in deltas.values() if d["expected_value_score"] > 0),
        "ev_windows_regressed": sum(1 for d in deltas.values() if d["expected_value_score"] < 0),
        "pnl_windows_improved": sum(1 for d in deltas.values() if d["total_pnl"] > 0),
        "pnl_windows_regressed": sum(1 for d in deltas.values() if d["total_pnl"] < 0),
        "max_drawdown_delta_max": max(d["max_drawdown_pct"] for d in deltas.values()),
        "trade_count_delta_sum": sum(d["trade_count"] for d in deltas.values()),
        "win_rate_delta_min": min(d["win_rate"] for d in deltas.values()),
        "sharpe_daily_delta_max": max(d["sharpe_daily"] for d in deltas.values()),
        "retargeted_signals_delta_sum": sum(d["retargeted_signals"] for d in deltas.values()),
    }


def _passes_gate4(aggregate: dict) -> bool:
    if aggregate["ev_windows_improved"] < 2 or aggregate["ev_windows_regressed"] > 0:
        return False
    if aggregate["expected_value_score_delta_pct"] > 0.10:
        return True
    if aggregate["total_pnl_delta_pct"] > 0.05:
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
    _install_patch()
    try:
        baseline = OrderedDict()
        for label, cfg in WINDOWS.items():
            baseline[label] = _run_window(universe, cfg, None)
            m = baseline[label]["metrics"]
            print(
                f"[{label} baseline] EV={m['expected_value_score']} "
                f"PnL={m['total_pnl']} SharpeD={m['sharpe_daily']}"
            )

        variants = OrderedDict()
        for name, target_atr in TESTED_TARGETS.items():
            rows = OrderedDict()
            for label, cfg in WINDOWS.items():
                rows[label] = _run_window(universe, cfg, target_atr)
                m = rows[label]["metrics"]
                print(
                    f"[{label} {name}] EV={m['expected_value_score']} "
                    f"PnL={m['total_pnl']} SharpeD={m['sharpe_daily']} "
                    f"retargeted={m['retargeted_signals']}"
                )
            aggregate = _aggregate(baseline, rows)
            variants[name] = {
                "target_atr": target_atr,
                "rows": rows,
                "aggregate": aggregate,
                "passes_gate4": _passes_gate4(aggregate),
            }
    finally:
        _remove_patch()

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
        "change_type": "exit_lifecycle_precious_breakout_target_width",
        "hypothesis": (
            "Precious-metals breakout winners may have the same continuation "
            "convexity as the accepted gold/commodity trend sleeve; widening "
            "only GLD/IAU/SLV breakout targets might lift return without "
            "adding tickers, risk, or filters."
        ),
        "alpha_hypothesis_category": "exit_lifecycle",
        "why_not_llm_soft_ranking": (
            "Production-aligned LLM ranking samples remain too thin, so this "
            "tests an alternate deterministic exit alpha using existing "
            "ticker/strategy fields."
        ),
        "parameters": {
            "single_causal_variable": "GLD/IAU/SLV breakout_long target ATR width",
            "baseline_target_atr": BASELINE_TARGET_ATR,
            "tested_target_atr": dict(TESTED_TARGETS),
            "precious_breakout_tickers": list(PRECIOUS_BREAKOUT_TICKERS),
            "locked_variables": [
                "universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "all sizing constants",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "MAX_PER_SECTOR",
                "gap cancels",
                "add-ons",
                "trend target widths including accepted gold 8ATR",
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
            name: {label: variant["rows"][label]["metrics"] for label in WINDOWS}
            for name, variant in variants.items()
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
                "If accepted, add a shared breakout precious-metals target "
                "constant in quant/constants.py and apply it in risk_engine.py, "
                "which is shared by run.py and backtester.py."
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
            "not_gold_trend_target_retry": True,
            "not_gold_risk_or_cap_retry": True,
            "not_universe_expansion": True,
            "why_not_simple_repeat": (
                "This tests breakout_long exit width only. It does not extend "
                "the accepted gold trend target, raise gold risk/cap, or add "
                "new precious-metals tickers."
            ),
        },
        "rejection_reason": (
            None if accepted else
            "No precious-metals breakout target variant passed fixed-window Gate 4."
        ),
        "next_retry_requires": [
            "Do not infer breakout target convexity from accepted gold trend target convexity.",
            "Do not retry nearby precious breakout ATR widths without forward/event evidence.",
            "A valid retry needs event/news context or a materially different breakout lifecycle discriminator.",
        ],
        "related_files": [
            "quant/experiments/exp_20260501_019_precious_breakout_target_width.py",
            "data/experiments/exp-20260501-019/precious_breakout_target_width.json",
            "docs/experiments/logs/exp-20260501-019.json",
            "docs/experiments/tickets/exp-20260501-019.json",
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
        "title": "Precious breakout target width",
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
