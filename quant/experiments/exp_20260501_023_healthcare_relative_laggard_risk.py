"""exp-20260501-023 Healthcare sector-relative laggard risk cap.

Alpha search. Test one capital-allocation variable: Healthcare signals whose
20-day return is not above the equal-weight Healthcare sector 20-day return may
deserve less risk. This is not a Healthcare sector ban and not a DTE-window
retry; it tests whether sector-relative leadership explains the residual
Healthcare losses after the accepted sizing stack.
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
from risk_engine import SECTOR_MAP  # noqa: E402


EXPERIMENT_ID = "exp-20260501-023"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "healthcare_relative_laggard_risk.json"
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
    ("healthcare_laggard_0_25x", 0.25),
    ("healthcare_laggard_0x", 0.0),
])

_state = {"signals_seen": 0, "signals_resized": 0}


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    resized_trade_count = 0
    resized_trade_pnl = 0.0
    healthcare_trade_count = 0
    healthcare_trade_pnl = 0.0
    for trade in result.get("trades", []):
        if trade.get("sector") == "Healthcare":
            healthcare_trade_count += 1
            healthcare_trade_pnl += float(trade.get("pnl") or 0.0)
        multipliers = trade.get("sizing_multipliers") or {}
        if multipliers.get("healthcare_relative_laggard_risk_multiplier_applied") is not None:
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
        "healthcare_laggard_signals_seen": _state["signals_seen"],
        "healthcare_laggard_signals_resized": _state["signals_resized"],
        "healthcare_laggard_trade_count": resized_trade_count,
        "healthcare_laggard_trade_pnl": round(resized_trade_pnl, 2),
        "healthcare_trade_count": healthcare_trade_count,
        "healthcare_trade_pnl": round(healthcare_trade_pnl, 2),
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


def _sector_avg_ret20(today: pd.Timestamp, ohlcv_all: dict, sector: str) -> float | None:
    returns = []
    for ticker, ticker_sector in SECTOR_MAP.items():
        if ticker_sector != sector:
            continue
        df = ohlcv_all.get(ticker)
        if df is None or df.empty or "Close" not in df.columns:
            continue
        ret = _ret20(df, today)
        if ret is not None:
            returns.append(ret)
    if not returns:
        return None
    return sum(returns) / len(returns)


def _patch_size_signals(target_multiplier: float | None):
    original = pe.size_signals
    avg_cache = {}

    def patched(signals, portfolio_value, risk_pct=None):
        sized = original(signals, portfolio_value, risk_pct=risk_pct)
        if target_multiplier is None:
            return sized

        today, ohlcv_all = _runtime_context()
        if today is None or ohlcv_all is None:
            return sized

        cache_key = str(today.date())
        if cache_key not in avg_cache:
            avg_cache[cache_key] = _sector_avg_ret20(today, ohlcv_all, "Healthcare")
        sector_avg = avg_cache[cache_key]
        if sector_avg is None:
            return sized

        for sig in sized:
            if sig.get("sector") != "Healthcare":
                continue
            ticker = sig.get("ticker")
            df = ohlcv_all.get(ticker)
            if df is None or df.empty or "Close" not in df.columns:
                continue
            ticker_ret = _ret20(df, today)
            if ticker_ret is None:
                continue
            rel_ret = ticker_ret - sector_avg
            if rel_ret > 0:
                continue

            _state["signals_seen"] += 1
            sizing = sig.get("sizing") or {}
            base_risk_pct = sizing.get("base_risk_pct") or risk_pct
            entry = sizing.get("entry_price") or sig.get("entry_price")
            stop = sizing.get("stop_price") or sig.get("stop_price")
            if base_risk_pct is None or entry is None or stop is None:
                continue

            new_risk_pct = base_risk_pct * target_multiplier
            if new_risk_pct <= 0:
                new_sizing = {
                    "portfolio_value_usd": round(portfolio_value, 2),
                    "risk_pct": 0.0,
                    "risk_amount_usd": 0.0,
                    "entry_price": round(float(entry), 2),
                    "stop_price": round(float(stop), 2),
                    "risk_per_share": round(float(entry) - float(stop), 2),
                    "net_risk_per_share": sizing.get("net_risk_per_share"),
                    "shares_to_buy": 0,
                    "position_value_usd": 0.0,
                    "position_pct_of_portfolio": 0.0,
                }
            else:
                new_sizing = pe.compute_position_size(
                    portfolio_value,
                    entry,
                    stop,
                    risk_pct=new_risk_pct,
                )
            if not new_sizing:
                continue

            preserved = dict(sizing)
            preserved.update(new_sizing)
            preserved["base_risk_pct"] = base_risk_pct
            preserved["healthcare_relative_laggard_risk_multiplier_applied"] = (
                target_multiplier
            )
            preserved["healthcare_ticker_ret20_pct"] = round(ticker_ret, 6)
            preserved["healthcare_sector_avg_ret20_pct"] = round(sector_avg, 6)
            preserved["healthcare_ret20_minus_sector_avg_pct"] = round(rel_ret, 6)
            preserved["healthcare_original_risk_pct"] = sizing.get("risk_pct")
            preserved["healthcare_original_shares"] = sizing.get("shares_to_buy")
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
        "healthcare_laggard_signals_resized_delta_sum": sum(
            d["healthcare_laggard_signals_resized"] for d in deltas.values()
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
            f"HCpnl={m['healthcare_trade_pnl']} HCtrades={m['healthcare_trade_count']}"
        )

    variants = OrderedDict()
    for variant, multiplier in VARIANTS.items():
        rows = OrderedDict()
        for label, cfg in WINDOWS.items():
            rows[label] = _run_window(universe, cfg, multiplier)
            m = rows[label]["metrics"]
            print(
                f"[{label} {variant}] EV={m['expected_value_score']} "
                f"PnL={m['total_pnl']} resized={m['healthcare_laggard_signals_resized']} "
                f"HCpnl={m['healthcare_trade_pnl']}"
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
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "accepted_candidate" if accepted else "rejected",
        "decision": "accepted_candidate" if accepted else "rejected",
        "lane": "alpha_search",
        "change_type": "capital_allocation_healthcare_relative_laggard_risk",
        "hypothesis": (
            "Healthcare signals that lag the equal-weight Healthcare sector over "
            "20 trading days may deserve less risk; leaders keep the accepted "
            "stack's normal sizing."
        ),
        "alpha_hypothesis_category": "capital_allocation",
        "why_not_llm_soft_ranking": (
            "Production-aligned LLM ranking samples remain too thin, so this "
            "tests a deterministic sector-relative allocation signal instead."
        ),
        "parameters": {
            "single_causal_variable": "Healthcare relative-laggard total risk cap",
            "baseline": "current accepted sizing stack",
            "tested_multipliers": dict(VARIANTS),
            "selector": (
                "sector == Healthcare and ticker 20-day close return <= "
                "equal-weight Healthcare sector 20-day close return"
            ),
            "locked_variables": [
                "universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "all existing sizing rules before this cap",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "MAX_PER_SECTOR",
                "gap cancels",
                "add-ons",
                "all target/stop exits",
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
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, add Healthcare sector-relative return enrichment "
                "and sizing cap in shared risk_engine/portfolio_engine code."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft-ranking remains sample-limited; this is an alternate "
                "deterministic capital-allocation alpha search."
            ),
        },
        "history_guardrails": {
            "not_healthcare_dte_retry": True,
            "not_coarse_healthcare_sector_ban": True,
            "not_financials_multiplier_retry": True,
            "why_not_simple_repeat": (
                "This uses a sector-relative leadership discriminator inside "
                "Healthcare rather than another event-distance window, ticker "
                "removal, or broad Healthcare haircut."
            ),
        },
        "rejection_reason": (
            None if accepted else
            "No Healthcare relative-laggard cap passed fixed-window Gate 4."
        ),
        "next_retry_requires": [
            "Do not retry nearby Healthcare relative-laggard multipliers without forward evidence.",
            "A valid retry needs event/news context or a broader sector-relative mechanism.",
            "If promoted, compute sector-relative fields in shared production/backtest code.",
        ],
        "related_files": [
            "quant/experiments/exp_20260501_023_healthcare_relative_laggard_risk.py",
            "data/experiments/exp-20260501-023/healthcare_relative_laggard_risk.json",
            "docs/experiments/logs/exp-20260501-023.json",
            "docs/experiments/tickets/exp-20260501-023.json",
        ],
    }
    return payload


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
        "title": "Healthcare relative laggard risk cap",
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
