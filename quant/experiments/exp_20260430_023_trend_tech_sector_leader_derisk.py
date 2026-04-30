"""exp-20260430-023 trend-Tech sector-leader de-risk screen.

Alpha search. Test one capital-allocation variable: whether already-selected
`trend_long` Technology names that are 20-day leaders inside a high-breadth
Technology tape should receive less risk. This uses the sector-state audit's
next valid branch: a production-feasible candidate-level state discriminator,
not another regime-score, gap, near-high, DTE, weak-hold, or universe-expansion
retry.
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

import feature_layer as fl  # noqa: E402
import portfolio_engine as pe  # noqa: E402
import risk_engine as re  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260430-023"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260430_023_trend_tech_sector_leader_derisk.json"
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
    ("baseline_1_00x", 1.00),
    ("sector_leader_0_50x", 0.50),
    ("sector_leader_0_25x", 0.25),
    ("sector_leader_0_00x", 0.00),
])

TECH_BREADTH_200_MIN = 0.75
TECH_REL20_MIN = 0.03


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


def _patch_features():
    original = fl.compute_trend_features

    def patched(data):
        features = original(data)
        if not features:
            return features
        ret20 = None
        try:
            if data is not None and len(data) >= 21:
                close = float(data["Close"].iloc[-1])
                prior = float(data["Close"].iloc[-21])
                if prior:
                    ret20 = round(close / prior - 1.0, 4)
        except Exception:
            ret20 = None
        return {**features, "return_20d_pct": ret20}

    fl.compute_trend_features = patched
    return original


def _sector_state(features_dict: dict, sector: str) -> dict:
    members = [
        features
        for ticker, features in (features_dict or {}).items()
        if re.SECTOR_MAP.get(str(ticker).upper()) == sector
    ]
    breadth_base = [f for f in members if f.get("above_200ma") is not None]
    ret20_values = [
        f.get("return_20d_pct")
        for f in members
        if isinstance(f.get("return_20d_pct"), (int, float))
    ]
    return {
        "sector_breadth_200": (
            sum(1 for f in breadth_base if f.get("above_200ma")) / len(breadth_base)
            if breadth_base else None
        ),
        "sector_avg_ret20": (
            sum(ret20_values) / len(ret20_values) if ret20_values else None
        ),
        "sector_member_count": len(members),
    }


def _patch_enrich():
    original = re.enrich_signals

    def patched(signals, features_dict, atr_target_mult=None):
        enriched = original(signals, features_dict, atr_target_mult=atr_target_mult)
        sector_cache = {}
        for sig in enriched:
            sector = sig.get("sector")
            if sector not in sector_cache:
                sector_cache[sector] = _sector_state(features_dict, sector)
            state = sector_cache[sector]
            ticker_features = features_dict.get(sig.get("ticker")) or {}
            ticker_ret20 = ticker_features.get("return_20d_pct")
            rel20 = None
            if (
                isinstance(ticker_ret20, (int, float))
                and isinstance(state.get("sector_avg_ret20"), (int, float))
            ):
                rel20 = round(ticker_ret20 - state["sector_avg_ret20"], 4)
            sig["sector_breadth_200"] = state.get("sector_breadth_200")
            sig["sector_avg_ret20"] = (
                round(state["sector_avg_ret20"], 4)
                if isinstance(state.get("sector_avg_ret20"), (int, float))
                else None
            )
            sig["ticker_ret20"] = ticker_ret20
            sig["ticker_vs_sector_ret20"] = rel20
        return enriched

    re.enrich_signals = patched
    return original


def _patch_size_signals(multiplier: float):
    original = pe.size_signals

    def patched(signals, portfolio_value, risk_pct=None):
        sized = original(signals, portfolio_value, risk_pct=risk_pct)
        for sig in sized:
            sizing = sig.get("sizing") or {}
            if not (
                sig.get("strategy") == "trend_long"
                and sig.get("sector") == "Technology"
                and isinstance(sig.get("sector_breadth_200"), (int, float))
                and sig["sector_breadth_200"] >= TECH_BREADTH_200_MIN
                and isinstance(sig.get("ticker_vs_sector_ret20"), (int, float))
                and sig["ticker_vs_sector_ret20"] >= TECH_REL20_MIN
                and sizing.get("shares_to_buy", 0) > 0
            ):
                continue

            old_shares = sizing["shares_to_buy"]
            new_shares = max(0, math.floor(old_shares * multiplier))
            entry_price = sizing.get("entry_price") or sig.get("entry_price") or 0.0
            sizing["shares_to_buy"] = new_shares
            sizing["position_value_usd"] = round(new_shares * entry_price, 2)
            sizing["risk_amount_usd"] = round(
                (sizing.get("risk_amount_usd") or 0.0) * multiplier,
                2,
            )
            sizing["risk_pct"] = round((sizing.get("risk_pct") or 0.0) * multiplier, 6)
            sizing["position_pct_of_portfolio"] = (
                round(sizing["position_value_usd"] / portfolio_value, 6)
                if portfolio_value else 0.0
            )
            sizing["trend_tech_sector_leader_risk_multiplier_applied"] = multiplier
        return sized

    pe.size_signals = patched
    return original


def _run_window(universe: list[str], cfg: dict, multiplier: float) -> dict:
    original_features = _patch_features()
    original_enrich = _patch_enrich()
    original_size = _patch_size_signals(multiplier)
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
        fl.compute_trend_features = original_features
        re.enrich_signals = original_enrich
        pe.size_signals = original_size

    if "error" in result:
        raise RuntimeError(result["error"])
    touched = 0
    for trade in result.get("trades", []):
        multipliers = trade.get("sizing_multipliers") or {}
        if "trend_tech_sector_leader_risk_multiplier_applied" in multipliers:
            touched += 1
    return {
        "metrics": _metrics(result),
        "trades": result.get("trades", []),
        "touched_trades": touched,
    }


def _build_payload() -> dict:
    universe = get_universe()
    rows = []
    for label, cfg in WINDOWS.items():
        for variant, multiplier in VARIANTS.items():
            result = _run_window(universe, cfg, multiplier)
            rows.append({
                "window": label,
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
                "state_note": cfg["state_note"],
                "variant": variant,
                "trend_tech_sector_leader_multiplier": multiplier,
                **result,
            })
            m = result["metrics"]
            print(
                f"[{label} {variant}] EV={m['expected_value_score']} "
                f"PnL={m['total_pnl']} SharpeD={m['sharpe_daily']} "
                f"DD={m['max_drawdown_pct']} WR={m['win_rate']} "
                f"trades={m['trade_count']} touched={result['touched_trades']}"
            )

    baseline_rows = {
        label: next(r for r in rows if r["window"] == label and r["variant"] == "baseline_1_00x")
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
                "touched_trades": candidate["touched_trades"],
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
                "touched_trades_sum": sum(v["touched_trades"] for v in by_window.values()),
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

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "accepted" if accepted else "rejected",
        "decision": "accepted" if accepted else "rejected",
        "lane": "alpha_search",
        "change_type": "capital_allocation_sector_state",
        "hypothesis": (
            "In high-breadth Technology tapes, trend_long names that already lead "
            "their sector by at least 3 percentage points over 20 trading days may "
            "be crowded/extended enough that full risk misallocates capital."
        ),
        "parameters": {
            "single_causal_variable": "risk multiplier for trend_long Technology sector-relative 20d leaders",
            "selector": {
                "strategy": "trend_long",
                "sector": "Technology",
                "sector_breadth_200_min": TECH_BREADTH_200_MIN,
                "ticker_vs_sector_ret20_min": TECH_REL20_MIN,
            },
            "baseline_multiplier": 1.00,
            "tested_multipliers": [0.50, 0.25, 0.00],
            "locked_variables": [
                "signal generation",
                "entry filters",
                "candidate ranking",
                "all existing Technology near-high/gap/DTE rules",
                "all non-Technology sizing rules",
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
        "date_range": {
            "start": WINDOWS["late_strong"]["start"],
            "end": WINDOWS["late_strong"]["end"],
        },
        "secondary_windows": [
            {"start": WINDOWS["mid_weak"]["start"], "end": WINDOWS["mid_weak"]["end"]},
            {"start": WINDOWS["old_thin"]["start"], "end": WINDOWS["old_thin"]["end"]},
        ],
        "market_regime_summary": {
            label: cfg["state_note"] for label, cfg in WINDOWS.items()
        },
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
                "Accepted because the sector-state selector improved the fixed-window objective materially."
                if accepted else
                "Rejected because no tested sector-state multiplier improved a majority of fixed windows with material aggregate uplift."
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
                "sector-state allocation test intentionally avoided LLM data constraints."
            ),
        },
        "history_guardrails": {
            "not_regime_score_band": True,
            "not_near_high_gap_or_dte_retune": True,
            "not_price_only_weak_hold_exit": True,
            "not_universe_expansion": True,
            "uses_sector_state_audit_next_valid_branch": True,
        },
        "rows": rows,
        "summary": summary,
        "rejection_reason": (
            None if accepted else
            "The selector did not improve a majority of windows with material aggregate EV/PnL uplift."
        ),
        "next_retry_requires": [
            "Do not retry nearby Technology sector-leader relative-return cutoffs without new event/news/lifecycle evidence.",
            "A valid retry must show that the selector changes realized capital in at least two fixed windows without clipping late_strong winners.",
            "If accepted in the future, implement the sector-state features in shared production/backtest enrichment before promotion.",
        ],
    }


def main() -> int:
    payload = _build_payload()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2)
    OUT_JSON.write_text(text, encoding="utf-8")
    LOG_JSON.write_text(text, encoding="utf-8")
    TICKET_JSON.write_text(text, encoding="utf-8")
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "best_variant": payload["delta_metrics"]["best_variant"],
        "best_aggregate": payload["delta_metrics"]["aggregate"],
        "artifact": str(OUT_JSON),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
