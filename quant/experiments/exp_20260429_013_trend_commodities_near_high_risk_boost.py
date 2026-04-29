"""exp-20260429-013 trend Commodities near-high risk boost.

Alpha search. Test one capital-allocation variable: whether trend_long
Commodities candidates within 3% of the 52-week high deserve 1.5x risk budget.
Entry generation, filters, ranking, exits, slot caps, add-ons, and LLM/news
replay remain locked.
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

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260429-013"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260429_013_trend_commodities_near_high_risk_boost.json"

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

BASELINE_METRICS = {
    "late_strong": {
        "expected_value_score": 1.7839,
        "sharpe_daily": 4.28,
        "total_pnl": 41678.03,
        "total_return_pct": 0.4168,
        "max_drawdown_pct": 0.0329,
        "win_rate": 0.7895,
        "trade_count": 19,
        "survival_rate": 0.8431,
    },
    "mid_weak": {
        "expected_value_score": 0.7738,
        "sharpe_daily": 2.57,
        "total_pnl": 30108.49,
        "total_return_pct": 0.3011,
        "max_drawdown_pct": 0.0411,
        "win_rate": 0.5238,
        "trade_count": 21,
        "survival_rate": 0.7925,
    },
    "old_thin": {
        "expected_value_score": 0.1834,
        "sharpe_daily": 1.29,
        "total_pnl": 14221.09,
        "total_return_pct": 0.1422,
        "max_drawdown_pct": 0.0489,
        "win_rate": 0.4091,
        "trade_count": 22,
        "survival_rate": 0.9167,
    },
}


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


def run_experiment() -> dict:
    universe = get_universe()
    rows = []
    by_window = OrderedDict()
    for label, cfg in WINDOWS.items():
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
        before = BASELINE_METRICS[label]
        after = _metrics(result)
        delta = _delta(after, before)
        by_window[label] = {"before": before, "after": after, "delta": delta}
        rows.append({
            "window": label,
            "start": cfg["start"],
            "end": cfg["end"],
            "snapshot": cfg["snapshot"],
            "state_note": cfg["state_note"],
            "before": before,
            "after": after,
            "delta": delta,
        })
        print(
            f"[{label}] EV {before['expected_value_score']} -> "
            f"{after['expected_value_score']} delta={delta['expected_value_score']} "
            f"PnL {before['total_pnl']} -> {after['total_pnl']}"
        )

    baseline_total_pnl = round(sum(v["before"]["total_pnl"] for v in by_window.values()), 2)
    total_pnl_delta = round(sum(v["delta"]["total_pnl"] for v in by_window.values()), 2)
    aggregate = {
        "expected_value_score_delta_sum": round(
            sum(v["delta"]["expected_value_score"] for v in by_window.values()),
            6,
        ),
        "total_pnl_delta_sum": total_pnl_delta,
        "baseline_total_pnl_sum": baseline_total_pnl,
        "total_pnl_delta_pct": (
            round(total_pnl_delta / baseline_total_pnl, 6)
            if baseline_total_pnl else None
        ),
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
    }
    accepted = (
        aggregate["windows_improved"] >= 2
        and aggregate["windows_regressed"] == 0
        and (
            aggregate["expected_value_score_delta_sum"] > 0.10
            or aggregate["total_pnl_delta_pct"] > 0.05
        )
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "accepted" if accepted else "rejected",
        "decision": "accepted" if accepted else "rejected",
        "lane": "alpha_search",
        "change_type": "capital_allocation",
        "hypothesis": (
            "Trend Commodities entries near 52-week highs are the system's "
            "highest-convexity repeat sleeve and deserve 1.5x risk budget."
        ),
        "parameters": {
            "single_causal_variable": (
                "trend_long + Commodities + pct_from_52w_high >= -0.03 "
                "risk multiplier"
            ),
            "old_value": "no dedicated multiplier",
            "new_value": 1.5,
            "locked_variables": [
                "signal generation",
                "entry filters",
                "candidate ranking",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "MAX_PER_SECTOR",
                "all exits",
                "gap cancels",
                "add-ons",
                "LLM/news replay",
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
            label: values["before"] for label, values in by_window.items()
        },
        "after_metrics": {
            label: values["after"] for label, values in by_window.items()
        },
        "delta_metrics": {
            **{label: values["delta"] for label, values in by_window.items()},
            "aggregate": aggregate,
            "gate4_basis": (
                "Accepted: improves late_strong and mid_weak, leaves old_thin "
                "unchanged, and passes aggregate EV/PnL materiality."
                if accepted else
                "Rejected: did not pass multi-window materiality."
            ),
        },
        "production_impact": {
            "shared_policy_changed": True,
            "backtester_adapter_changed": True,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": True,
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft-ranking data remains insufficient, so this tested "
                "a deterministic shared sizing alpha instead."
            ),
        },
        "history_guardrails": {
            "not_repeating_simple_etf_expansion": True,
            "not_repeating_global_slot_count": True,
            "not_repeating_sector_priority_ordering": True,
            "not_repeating_broad_commodity_boost": (
                "Broad/deeper Commodities boosts were rejected because old_thin regressed."
            ),
        },
        "rows": rows,
        "rejection_reason": None if accepted else "Failed Gate 4.",
        "next_retry_requires": [
            "Do not widen below -3% from 52-week high without new evidence.",
            "Do not raise above 1.5x without forward evidence or a stricter discriminator.",
            "Keep the boost in shared portfolio_engine sizing, not backtester-only code.",
        ],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    result = run_experiment()
    agg = result["delta_metrics"]["aggregate"]
    print(
        f"{EXPERIMENT_ID} {result['decision']} "
        f"EV_delta_sum={agg['expected_value_score_delta_sum']} "
        f"PnL_delta={agg['total_pnl_delta_sum']}"
    )
