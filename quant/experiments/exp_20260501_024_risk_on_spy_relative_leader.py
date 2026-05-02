"""exp-20260501-024 risk-on SPY-relative leader allocation.

Alpha search. Test one capital-allocation variable: otherwise-unmodified
risk_on signals whose own 20-day return exceeds SPY's 20-day return may deserve
more risk. This is a broad meta-allocation discriminator, not a new entry,
filter, sector priority, or universe expansion.
"""

from __future__ import annotations

import inspect
import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import portfolio_engine as pe  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260501-024"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "risk_on_spy_relative_leader.json"
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
    ("spy_relative_leader_1_8x", 1.8),
    ("spy_relative_leader_2_0x", 2.0),
])

_state = {"signals_seen": 0, "signals_resized": 0}


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    resized_trade_count = 0
    resized_trade_pnl = 0.0
    for trade in result.get("trades", []):
        multipliers = trade.get("sizing_multipliers") or {}
        if multipliers.get("spy_relative_leader_risk_on_multiplier_applied"):
            resized_trade_count += 1
            resized_trade_pnl += float(trade.get("pnl") or 0.0)
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
        "spy_relative_leader_signals_seen": _state["signals_seen"],
        "spy_relative_leader_signals_resized": _state["signals_resized"],
        "spy_relative_leader_trade_count": resized_trade_count,
        "spy_relative_leader_trade_pnl": round(resized_trade_pnl, 2),
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


def _runtime_context() -> tuple[pd.Timestamp | None, dict | None]:
    for frame_info in inspect.stack():
        local_vars = frame_info.frame.f_locals
        today = local_vars.get("today")
        ohlcv_all = local_vars.get("ohlcv_all")
        if today is not None and isinstance(ohlcv_all, dict):
            return pd.Timestamp(today), ohlcv_all
    return None, None


def _ret20(df: pd.DataFrame, today: pd.Timestamp) -> float | None:
    if today not in df.index:
        return None
    pos = df.index.get_loc(today)
    if isinstance(pos, slice) or pos < 20:
        return None
    start = float(df.iloc[pos - 20]["Close"])
    end = float(df.iloc[pos]["Close"])
    if start <= 0:
        return None
    return end / start - 1.0


def _has_other_sizing_rule(sizing: dict) -> bool:
    for key, value in sizing.items():
        if not key.endswith("_multiplier_applied"):
            continue
        if key == "risk_on_unmodified_risk_multiplier_applied":
            continue
        if isinstance(value, (int, float)) and value != 1.0:
            return True
    return False


def _patch_size_signals(target_multiplier: float | None):
    original = pe.size_signals
    ret_cache = {}

    def patched(signals, portfolio_value, risk_pct=None):
        sized = original(signals, portfolio_value, risk_pct=risk_pct)
        if target_multiplier is None:
            return sized

        today, ohlcv_all = _runtime_context()
        if today is None or ohlcv_all is None:
            return sized

        spy_df = ohlcv_all.get("SPY")
        if spy_df is None or spy_df.empty or "Close" not in spy_df.columns:
            return sized
        spy_ret = _ret20(spy_df, today)
        if spy_ret is None:
            return sized

        for sig in sized:
            sizing = sig.get("sizing") or {}
            applied = sizing.get("risk_on_unmodified_risk_multiplier_applied")
            if not isinstance(applied, (int, float)) or applied <= 1.0:
                continue
            if _has_other_sizing_rule(sizing):
                continue
            ticker = sig.get("ticker")
            if not ticker or ticker == "SPY":
                continue
            cache_key = (str(today.date()), ticker)
            if cache_key not in ret_cache:
                df = ohlcv_all.get(ticker)
                ret_cache[cache_key] = (
                    _ret20(df, today)
                    if df is not None and not df.empty and "Close" in df.columns
                    else None
                )
            ticker_ret = ret_cache[cache_key]
            if ticker_ret is None or ticker_ret <= spy_ret:
                continue

            _state["signals_seen"] += 1
            base_risk_pct = sizing.get("base_risk_pct") or risk_pct
            entry = sizing.get("entry_price") or sig.get("entry_price")
            stop = sizing.get("stop_price") or sig.get("stop_price")
            if not base_risk_pct or not entry or not stop:
                continue

            new_sizing = pe.compute_position_size(
                portfolio_value,
                entry,
                stop,
                risk_pct=base_risk_pct * target_multiplier,
            )
            if not new_sizing:
                continue
            preserved = dict(sizing)
            preserved.update(new_sizing)
            preserved["base_risk_pct"] = base_risk_pct
            preserved["risk_on_unmodified_risk_multiplier_applied"] = target_multiplier
            preserved["spy_relative_leader_risk_on_multiplier_applied"] = target_multiplier
            preserved["spy_relative_leader_original_multiplier"] = applied
            preserved["spy_relative_leader_original_shares"] = sizing.get("shares_to_buy")
            preserved["ticker_ret20_pct"] = round(ticker_ret, 6)
            preserved["spy_ret20_pct"] = round(spy_ret, 6)
            preserved["ticker_ret20_minus_spy_pct"] = round(ticker_ret - spy_ret, 6)
            sig["sizing"] = preserved
            _state["signals_resized"] += 1
        return sized

    pe.size_signals = patched
    return original


def _run_window(universe: list[str], cfg: dict, target_multiplier: float | None) -> dict:
    _state["signals_seen"] = 0
    _state["signals_resized"] = 0
    original = _patch_size_signals(target_multiplier)
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
        "spy_relative_leader_signals_resized_delta_sum": sum(
            d["spy_relative_leader_signals_resized"] for d in deltas.values()
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
    for variant, multiplier in VARIANTS.items():
        rows = OrderedDict()
        for label, cfg in WINDOWS.items():
            rows[label] = _run_window(universe, cfg, multiplier)
            m = rows[label]["metrics"]
            print(
                f"[{label} {variant}] EV={m['expected_value_score']} "
                f"PnL={m['total_pnl']} SharpeD={m['sharpe_daily']} "
                f"resized={m['spy_relative_leader_signals_resized']}"
            )
        aggregate = _aggregate(baseline, rows)
        variants[variant] = {
            "multiplier": multiplier,
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
        "status": "accepted" if accepted else "rejected",
        "decision": "accepted" if accepted else "rejected",
        "lane": "alpha_search",
        "change_type": "capital_allocation_risk_on_spy_relative_leader",
        "hypothesis": (
            "Otherwise-unmodified risk_on signals with 20-day return above SPY's "
            "20-day return deserve more risk because they represent selected "
            "idiosyncratic leaders rather than broad beta followers."
        ),
        "alpha_hypothesis_category": "capital_allocation_meta_routing",
        "why_not_llm_soft_ranking": (
            "Production-aligned LLM ranking samples remain too thin, so this "
            "tests a deterministic relative-strength allocation signal instead."
        ),
        "parameters": {
            "single_causal_variable": "risk_on SPY-relative leader total risk multiplier",
            "baseline": "current accepted risk_on_unmodified low/mid/default multipliers",
            "tested_multipliers": dict(VARIANTS),
            "selector": {
                "regime_exit_bucket": "risk_on",
                "other_sizing_rules": "none except risk_on_unmodified",
                "ticker_ret20_minus_spy_ret20": "> 0",
            },
            "locked_variables": [
                "universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "all sector-specific haircuts/boosts",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "MAX_PER_SECTOR",
                "gap cancels",
                "add-ons",
                "all exits including gold 8ATR target",
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
                "If accepted, compute ticker-vs-SPY 20-day relative strength in "
                "shared enrichment before using it in portfolio_engine."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft-ranking remains sample-limited; this avoids that data "
                "constraint rather than weakening LLM."
            ),
        },
        "history_guardrails": {
            "not_ai_infra_watchlist_retry": True,
            "not_synchronous_sector_retry": True,
            "not_plain_risk_on_nearby_scalar": True,
            "not_financials_leader_retry": True,
            "why_not_simple_repeat": (
                "This tests broad ticker-vs-index relative strength only within "
                "already-selected plain risk_on inventory, rather than another "
                "sector synchronization threshold, raw scalar, or universe add."
            ),
        },
        "rejection_reason": (
            None if accepted else
            "No SPY-relative leader risk_on multiplier passed fixed-window Gate 4."
        ),
        "next_retry_requires": [
            "Do not retry nearby SPY-relative multipliers without forward evidence.",
            "A valid retry needs event/news or lifecycle context, not another scalar.",
            "If promoted, compute the relative-strength field in shared production/backtest code.",
        ],
        "related_files": [
            "quant/experiments/exp_20260501_024_risk_on_spy_relative_leader.py",
            "data/experiments/exp-20260501-024/risk_on_spy_relative_leader.json",
            "docs/experiments/logs/exp-20260501-024.json",
            "docs/experiments/tickets/exp-20260501-024.json",
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
        "title": "Risk-on SPY-relative leader allocation",
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
