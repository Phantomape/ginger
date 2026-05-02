"""exp-20260502-006 commodity breakout leader position cap.

Alpha search. Prior experiment exp-20260502-005 found commodity breakout leader
risk-budget boosts were economically inert because the selected signals were
already capped by MAX_POSITION_PCT. Test the next single causal variable:
whether this narrow cohort deserves a higher position cap.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import portfolio_engine as pe  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from constants import EXEC_LAG_PCT, ROUND_TRIP_COST_PCT  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260502-006"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "commodity_breakout_leader_cap.json"
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
    ("commodity_breakout_leader_cap_50pct", 0.50),
    ("commodity_breakout_leader_cap_60pct", 0.60),
])

_state = {"signals_seen": 0, "signals_resized": 0}


def _position_size_with_cap(portfolio_value, entry_price, stop_price, risk_pct, max_position_pct):
    if portfolio_value <= 0 or entry_price <= 0 or stop_price <= 0 or stop_price >= entry_price:
        return None
    risk_amount = portfolio_value * risk_pct
    risk_per_share = entry_price - stop_price
    net_risk_per_share = (
        risk_per_share
        + entry_price * ROUND_TRIP_COST_PCT
        + entry_price * EXEC_LAG_PCT
    )
    shares = max(1, math.floor(risk_amount / net_risk_per_share))
    max_shares = max(1, math.floor(portfolio_value * max_position_pct / entry_price))
    shares = min(shares, max_shares)
    position_value = shares * entry_price
    return {
        "portfolio_value_usd": round(portfolio_value, 2),
        "risk_pct": risk_pct,
        "risk_amount_usd": round(risk_amount, 2),
        "entry_price": round(entry_price, 2),
        "stop_price": round(stop_price, 2),
        "risk_per_share": round(risk_per_share, 2),
        "net_risk_per_share": round(net_risk_per_share, 4),
        "shares_to_buy": shares,
        "position_value_usd": round(position_value, 2),
        "position_pct_of_portfolio": round(position_value / portfolio_value, 4),
    }


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    resized_trade_count = 0
    resized_trade_pnl = 0.0
    resized_trade_tickers = []
    for trade in result.get("trades", []):
        multipliers = trade.get("sizing_multipliers") or {}
        if multipliers.get("commodity_breakout_leader_position_cap_applied"):
            resized_trade_count += 1
            resized_trade_pnl += float(trade.get("pnl") or 0.0)
            resized_trade_tickers.append({
                "ticker": trade.get("ticker"),
                "entry_date": trade.get("entry_date"),
                "pnl": round(float(trade.get("pnl") or 0.0), 2),
                "position_cap": multipliers.get("commodity_breakout_leader_position_cap_applied"),
            })
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
        "commodity_breakout_leader_cap_signals_seen": _state["signals_seen"],
        "commodity_breakout_leader_cap_signals_resized": _state["signals_resized"],
        "commodity_breakout_leader_cap_trade_count": resized_trade_count,
        "commodity_breakout_leader_cap_trade_pnl": round(resized_trade_pnl, 2),
        "commodity_breakout_leader_cap_trades": resized_trade_tickers,
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


def _has_other_sizing_rule(sizing: dict) -> bool:
    allowed = {
        "risk_on_unmodified_risk_multiplier_applied",
        "spy_relative_leader_risk_on_multiplier_applied",
    }
    for key, value in sizing.items():
        if not key.endswith("_multiplier_applied") or key in allowed:
            continue
        if isinstance(value, (int, float)) and value != 1.0:
            return True
    return False


def _patch_size_signals(max_position_pct: float | None):
    original = pe.size_signals

    def patched(signals, portfolio_value, risk_pct=None):
        sized = original(signals, portfolio_value, risk_pct=risk_pct)
        if max_position_pct is None:
            return sized

        for sig in sized:
            if sig.get("strategy") != "breakout_long" or sig.get("sector") != "Commodities":
                continue
            sizing = sig.get("sizing") or {}
            leader_applied = sizing.get("spy_relative_leader_risk_on_multiplier_applied")
            if not isinstance(leader_applied, (int, float)) or leader_applied <= 1.0:
                continue
            if _has_other_sizing_rule(sizing):
                continue

            _state["signals_seen"] += 1
            entry = sizing.get("entry_price") or sig.get("entry_price")
            stop = sizing.get("stop_price") or sig.get("stop_price")
            signal_risk_pct = sizing.get("risk_pct")
            if not signal_risk_pct or not entry or not stop:
                continue

            new_sizing = _position_size_with_cap(
                portfolio_value,
                entry,
                stop,
                risk_pct=signal_risk_pct,
                max_position_pct=max_position_pct,
            )
            if not new_sizing:
                continue
            preserved = dict(sizing)
            preserved.update(new_sizing)
            preserved["base_risk_pct"] = sizing.get("base_risk_pct")
            preserved["risk_on_unmodified_risk_multiplier_applied"] = leader_applied
            preserved["spy_relative_leader_risk_on_multiplier_applied"] = leader_applied
            preserved["commodity_breakout_leader_position_cap_applied"] = max_position_pct
            preserved["commodity_breakout_leader_original_cap_position_pct"] = (
                sizing.get("position_pct_of_portfolio")
            )
            preserved["commodity_breakout_leader_original_shares"] = sizing.get("shares_to_buy")
            sig["sizing"] = preserved
            _state["signals_resized"] += 1
        return sized

    pe.size_signals = patched
    return original


def _run_window(universe: list[str], cfg: dict, max_position_pct: float | None) -> dict:
    _state["signals_seen"] = 0
    _state["signals_resized"] = 0
    original = _patch_size_signals(max_position_pct)
    try:
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
    finally:
        pe.size_signals = original
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
        "commodity_breakout_leader_cap_signals_resized_delta_sum": sum(
            d["commodity_breakout_leader_cap_signals_resized"] for d in deltas.values()
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
    baseline = OrderedDict()
    for label, cfg in WINDOWS.items():
        baseline[label] = _run_window(universe, cfg, None)
        m = baseline[label]["metrics"]
        print(
            f"[{label} baseline] EV={m['expected_value_score']} "
            f"PnL={m['total_pnl']} SharpeD={m['sharpe_daily']} "
            f"DD={m['max_drawdown_pct']} WR={m['win_rate']} trades={m['trade_count']}"
        )

    variants = OrderedDict()
    for variant, cap in VARIANTS.items():
        rows = OrderedDict()
        for label, cfg in WINDOWS.items():
            rows[label] = _run_window(universe, cfg, cap)
            m = rows[label]["metrics"]
            print(
                f"[{label} {variant}] EV={m['expected_value_score']} "
                f"PnL={m['total_pnl']} SharpeD={m['sharpe_daily']} "
                f"resized={m['commodity_breakout_leader_cap_signals_resized']}"
            )
        aggregate = _aggregate(baseline, rows)
        variants[variant] = {
            "position_cap": cap,
            "rows": rows,
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
        "change_type": "capital_allocation_commodity_breakout_spy_leader_position_cap",
        "hypothesis": (
            "Commodity breakout SPY-relative leaders may be capped before their "
            "positive convexity can express. A narrow higher position cap could "
            "increase winner capture without changing entries, exits, or universe."
        ),
        "alpha_hypothesis_category": "capital_allocation_meta_routing",
        "why_not_llm_soft_ranking": (
            "Production-aligned LLM ranking samples remain too thin; this tests a "
            "deterministic allocation signal that does not depend on LLM coverage."
        ),
        "parameters": {
            "single_causal_variable": "commodity breakout SPY-relative leader position cap",
            "baseline_position_cap": 0.40,
            "tested_position_caps": dict(VARIANTS),
            "selector": {
                "strategy": "breakout_long",
                "sector": "Commodities",
                "regime_exit_bucket": "risk_on",
                "spy_relative_leader": True,
                "other_sizing_rules": "none except risk_on_unmodified and spy_relative_leader",
            },
            "locked_variables": [
                "universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "risk multiplier",
                "all other sizing rules",
                "MAX_POSITIONS",
                "MAX_PORTFOLIO_HEAT",
                "MAX_PER_SECTOR",
                "gap cancels",
                "add-ons",
                "all exits and target widths",
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
        "before_metrics": {label: baseline[label]["metrics"] for label in WINDOWS},
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
            "shared_policy_changed": accepted,
            "backtester_adapter_changed": accepted,
            "run_adapter_changed": accepted,
            "replay_only": False,
            "parity_test_added": accepted,
            "promotion_requirement": (
                "If accepted, add a shared portfolio_engine branch or helper so "
                "production and backtest use the same cohort cap."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": (
                "LLM soft-ranking remains sample-limited; this avoids that data "
                "constraint rather than weakening LLM."
            ),
        },
        "history_guardrails": {
            "follows_exp_20260502_005_cap_blocker": True,
            "not_precious_breakout_target_retry": True,
            "not_liquid_proxy_etf_retry": True,
            "not_broad_position_cap_retry": True,
            "why_not_simple_repeat": (
                "This tests the cap constraint exposed by exp-20260502-005, not "
                "another risk multiplier or a broad MAX_POSITION_PCT change."
            ),
        },
        "rejection_reason": (
            None if accepted else
            "No commodity breakout leader position-cap variant passed fixed-window Gate 4."
        ),
        "next_retry_requires": [
            "Do not retry nearby commodity breakout leader cap levels without forward evidence.",
            "A valid retry needs event/news or lifecycle context, not another cap scalar.",
            "Do not generalize this into broad commodity or broad position-cap changes.",
        ],
        "related_files": [
            "quant/experiments/exp_20260502_006_commodity_breakout_leader_cap.py",
            "data/experiments/exp-20260502-006/commodity_breakout_leader_cap.json",
            "docs/experiments/logs/exp-20260502-006.json",
            "docs/experiments/tickets/exp-20260502-006.json",
            "docs/experiment_log.jsonl",
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
        "title": "Commodity breakout leader cap",
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
