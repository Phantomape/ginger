"""exp-20260430-022 breadth-conditioned risk-on plain boost.

Alpha search. Test one capital-allocation variable: whether the accepted
low/mid-score risk_on_unmodified sizing boost should require healthy universe
breadth. This avoids LLM sample limits and does not change production strategy
code unless the fixed-window protocol accepts the result.
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


EXPERIMENT_ID = "exp-20260430-022"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260430_022_breadth_conditioned_risk_on_boost.json"
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
    ("baseline", None),
    ("breadth50_min_0_50", 0.50),
    ("breadth50_min_0_60", 0.60),
    ("breadth50_min_0_70", 0.70),
])


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
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


def _breadth_50dma(today: pd.Timestamp, ohlcv_all: dict, universe: list[str]) -> dict:
    total = 0
    above = 0
    for ticker in universe:
        if ticker in {"SPY", "QQQ"}:
            continue
        df = ohlcv_all.get(ticker)
        if df is None or df.empty or "Close" not in df.columns:
            continue
        hist = df[df.index <= today].tail(50)
        if len(hist) < 50:
            continue
        total += 1
        if float(hist["Close"].iloc[-1]) > float(hist["Close"].mean()):
            above += 1
    return {
        "above_50dma": above,
        "eligible_tickers": total,
        "breadth_50dma": round(above / total, 6) if total else None,
    }


def _patch_size_signals(min_breadth: float | None, universe: list[str]):
    original = pe.size_signals
    breadth_cache = {}

    def patched(signals, portfolio_value, risk_pct=None):
        sized = original(signals, portfolio_value, risk_pct=risk_pct)
        if min_breadth is None:
            return sized

        today, ohlcv_all = _runtime_context()
        breadth = None
        if today is not None and ohlcv_all is not None:
            cache_key = str(today.date())
            if cache_key not in breadth_cache:
                breadth_cache[cache_key] = _breadth_50dma(today, ohlcv_all, universe)
            breadth = breadth_cache[cache_key]

        breadth_value = (breadth or {}).get("breadth_50dma")
        if breadth_value is None or breadth_value >= min_breadth:
            return sized

        for sig in sized:
            sizing = sig.get("sizing") or {}
            applied = sizing.get("risk_on_unmodified_risk_multiplier_applied")
            if applied is None or applied <= pe.RISK_ON_UNMODIFIED_RISK_MULTIPLIER:
                continue
            if sizing.get("shares_to_buy", 0) <= 0:
                continue

            base_risk_pct = sizing.get("base_risk_pct") or risk_pct
            entry = sizing.get("entry_price") or sig.get("entry_price")
            stop = sizing.get("stop_price") or sig.get("stop_price")
            if not base_risk_pct or not entry or not stop:
                continue

            new_risk_pct = base_risk_pct * pe.RISK_ON_UNMODIFIED_RISK_MULTIPLIER
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
            preserved["risk_on_unmodified_risk_multiplier_applied"] = (
                pe.RISK_ON_UNMODIFIED_RISK_MULTIPLIER
            )
            preserved["breadth_conditioned_risk_on_boost_blocked"] = True
            preserved["breadth_conditioned_min_breadth_50dma"] = min_breadth
            preserved["breadth_conditioned_observed_breadth_50dma"] = breadth_value
            preserved["breadth_conditioned_original_multiplier"] = applied
            preserved["breadth_conditioned_original_shares"] = sizing.get("shares_to_buy")
            sig["sizing"] = preserved
        return sized

    pe.size_signals = patched
    return original


def _run_window(universe: list[str], cfg: dict, min_breadth: float | None) -> dict:
    original = _patch_size_signals(min_breadth, universe)
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


def _build_payload() -> dict:
    universe = get_universe()
    rows = []
    for label, cfg in WINDOWS.items():
        for variant, min_breadth in VARIANTS.items():
            result = _run_window(universe, cfg, min_breadth)
            rows.append({
                "window": label,
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
                "state_note": cfg["state_note"],
                "variant": variant,
                "min_breadth_50dma": min_breadth,
                **result,
            })
            m = result["metrics"]
            print(
                f"[{label} {variant}] EV={m['expected_value_score']} "
                f"PnL={m['total_pnl']} SharpeD={m['sharpe_daily']} "
                f"DD={m['max_drawdown_pct']} WR={m['win_rate']} "
                f"trades={m['trade_count']}"
            )

    baseline_rows = {
        label: next(r for r in rows if r["window"] == label and r["variant"] == "baseline")
        for label in WINDOWS
    }
    summary = OrderedDict()
    for variant in list(VARIANTS.keys())[1:]:
        by_window = OrderedDict()
        for label in WINDOWS:
            baseline = baseline_rows[label]
            candidate = next(r for r in rows if r["window"] == label and r["variant"] == variant)
            by_window[label] = {
                "before": baseline["metrics"],
                "after": candidate["metrics"],
                "delta": _delta(candidate["metrics"], baseline["metrics"]),
            }
        baseline_total_pnl = round(sum(v["before"]["total_pnl"] for v in by_window.values()), 2)
        total_pnl_delta = round(sum(v["delta"]["total_pnl"] for v in by_window.values()), 2)
        summary[variant] = {
            "by_window": by_window,
            "aggregate": {
                "expected_value_score_delta_sum": round(
                    sum(v["delta"]["expected_value_score"] for v in by_window.values()),
                    6,
                ),
                "total_pnl_delta_sum": total_pnl_delta,
                "baseline_total_pnl_sum": baseline_total_pnl,
                "total_pnl_delta_pct": round(total_pnl_delta / baseline_total_pnl, 6),
                "windows_improved": sum(
                    1 for v in by_window.values()
                    if v["delta"]["expected_value_score"] > 0
                ),
                "windows_regressed": sum(
                    1 for v in by_window.values()
                    if v["delta"]["expected_value_score"] < 0
                ),
                "max_drawdown_delta_max": max(
                    v["delta"]["max_drawdown_pct"] for v in by_window.values()
                ),
                "trade_count_delta_sum": sum(v["delta"]["trade_count"] for v in by_window.values()),
                "win_rate_delta_min": min(v["delta"]["win_rate"] for v in by_window.values()),
            },
        }

    best_variant, best_summary = max(
        summary.items(),
        key=lambda item: (
            item[1]["aggregate"]["windows_improved"],
            -item[1]["aggregate"]["windows_regressed"],
            item[1]["aggregate"]["expected_value_score_delta_sum"],
            item[1]["aggregate"]["total_pnl_delta_sum"],
        ),
    )
    best_agg = best_summary["aggregate"]
    accepted = (
        best_agg["windows_improved"] >= 2
        and best_agg["expected_value_score_delta_sum"] > 0.10
        and (
            best_agg["total_pnl_delta_pct"] > 0.05
            or best_agg["max_drawdown_delta_max"] < -0.01
            or (best_agg["trade_count_delta_sum"] > 0 and best_agg["win_rate_delta_min"] >= 0)
        )
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "accepted" if accepted else "rejected",
        "decision": "accepted" if accepted else "rejected",
        "lane": "alpha_search",
        "change_type": "capital_allocation_market_breadth_route",
        "hypothesis": (
            "The accepted low/mid-score risk_on_unmodified boost may need a healthy "
            "50-day universe breadth state; below the threshold it may overallocate "
            "to weak-tape plain risk-on candidates."
        ),
        "parameters": {
            "single_causal_variable": "minimum universe 50dma breadth required for low/mid-score risk_on_unmodified boost",
            "baseline_min_breadth": None,
            "tested_min_breadth": [0.50, 0.60, 0.70],
            "blocked_multiplier_replacement": pe.RISK_ON_UNMODIFIED_RISK_MULTIPLIER,
            "locked_variables": [
                "signal generation",
                "entry filters",
                "candidate ranking",
                "all existing sector/near-high/gap/DTE sizing rules",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "MAX_PER_SECTOR",
                "upside/adverse gap cancels",
                "add-ons",
                "all exits",
                "LLM/news replay",
                "earnings strategy",
            ],
        },
        "date_range": {"start": WINDOWS["late_strong"]["start"], "end": WINDOWS["late_strong"]["end"]},
        "secondary_windows": [
            {"start": WINDOWS["mid_weak"]["start"], "end": WINDOWS["mid_weak"]["end"]},
            {"start": WINDOWS["old_thin"]["start"], "end": WINDOWS["old_thin"]["end"]},
        ],
        "market_regime_summary": {k: v["state_note"] for k, v in WINDOWS.items()},
        "before_metrics": {
            label: baseline_rows[label]["metrics"] for label in WINDOWS
        },
        "after_metrics": {
            "best_variant": best_variant,
            **{
                label: best_summary["by_window"][label]["after"]
                for label in WINDOWS
            },
        },
        "delta_metrics": {
            "best_variant": best_variant,
            **{
                label: best_summary["by_window"][label]["delta"]
                for label in WINDOWS
            },
            "aggregate": best_agg,
            "gate4_basis": (
                "Accepted by three-window fixed protocol."
                if accepted
                else "Rejected because the best breadth route did not improve a majority of windows with sufficient EV/PnL evidence."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft ranking remains sample-limited, so this deterministic "
                "breadth-allocation route intentionally avoided LLM data constraints."
            ),
        },
        "history_guardrails": {
            "not_tech_score_haircut": True,
            "not_slot_expansion": True,
            "not_universe_expansion": True,
            "not_low_mfe_exit": True,
            "not_llm_soft_ranking": True,
            "mechanism_note": (
                "This tests a new market-breadth state variable rather than retuning "
                "recently rejected sector, slot, add-on, or price-only lifecycle rules."
            ),
        },
        "rows": rows,
        "summary": summary,
    }
    return payload


def main() -> int:
    payload = _build_payload()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    LOG_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    TICKET_JSON.write_text(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "title": "Breadth-conditioned risk-on boost",
        "summary": payload["delta_metrics"]["gate4_basis"],
        "best_variant": payload["delta_metrics"]["best_variant"],
        "aggregate": payload["delta_metrics"]["aggregate"],
        "production_impact": payload["production_impact"],
    }, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {LOG_JSON}")
    print(f"Wrote {TICKET_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
