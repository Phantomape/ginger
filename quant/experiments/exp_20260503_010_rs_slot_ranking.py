"""exp-20260503-010 medium-term relative-strength slot ranking.

Alpha search. Test one candidate-ranking variable: the ordering of already
survived, already sized core candidates before scarce slot slicing. Production
code is unchanged unless a fixed-window result passes the promotion gate.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import backtester  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260503-010"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "rs_slot_ranking.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

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
    ("baseline_existing_order", "baseline"),
    ("rs20_then_tqs", "rs20_then_tqs"),
    ("spy_leader_rs20_then_tqs", "spy_leader_rs20_then_tqs"),
    ("tqs_then_rs20", "tqs_then_rs20"),
])


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
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


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for key, before_value in before.items():
        after_value = after.get(key)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            out[key] = round(after_value - before_value, 6)
        else:
            out[key] = None
    return out


def _float_value(value: Any, default: float = float("-inf")) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _slot_ranked(signals: list[dict[str, Any]], variant: str) -> list[dict[str, Any]]:
    if variant == "baseline" or len(signals) <= 1:
        return list(signals)

    def rs20(sig: dict[str, Any]) -> float:
        return _float_value(sig.get("ticker_ret20_minus_spy_pct"))

    def tqs(sig: dict[str, Any]) -> float:
        value = sig.get("trade_quality_score")
        if value is None:
            value = sig.get("confidence_score")
        return _float_value(value, default=0.0)

    def conf(sig: dict[str, Any]) -> float:
        return _float_value(sig.get("confidence_score"), default=0.0)

    def spy_leader(sig: dict[str, Any]) -> int:
        return 1 if sig.get("spy_relative_leader") is True else 0

    if variant == "rs20_then_tqs":
        key = lambda sig: (rs20(sig), tqs(sig), conf(sig))
    elif variant == "spy_leader_rs20_then_tqs":
        key = lambda sig: (spy_leader(sig), rs20(sig), tqs(sig), conf(sig))
    elif variant == "tqs_then_rs20":
        key = lambda sig: (tqs(sig), rs20(sig), conf(sig))
    else:
        raise ValueError(f"Unknown variant: {variant}")

    return sorted(signals, key=key, reverse=True)


@contextmanager
def _entry_plan_rank_patch(variant: str):
    original = backtester.plan_entry_candidates

    def patched(signals, open_positions, *args, **kwargs):
        ranked = _slot_ranked(list(signals or []), variant)
        return original(ranked, open_positions, *args, **kwargs)

    backtester.plan_entry_candidates = patched
    try:
        yield
    finally:
        backtester.plan_entry_candidates = original


def _run_window(universe: list[str], cfg: dict[str, Any], variant: str) -> dict[str, Any]:
    with _entry_plan_rank_patch(variant):
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
        raise RuntimeError(str(result["error"]))
    return {
        "metrics": _metrics(result),
        "entry_decision_summary": result.get("entry_decision_summary"),
        "trades": result.get("trades", []),
    }


def _aggregate(by_window: OrderedDict[str, dict[str, Any]]) -> dict[str, Any]:
    baseline_total_pnl = round(sum(v["before"]["total_pnl"] for v in by_window.values()), 2)
    total_pnl_delta = round(sum(v["delta"]["total_pnl"] for v in by_window.values()), 2)
    return {
        "expected_value_score_delta_sum": round(
            sum(v["delta"]["expected_value_score"] for v in by_window.values()),
            6,
        ),
        "total_pnl_delta_sum": total_pnl_delta,
        "baseline_total_pnl_sum": baseline_total_pnl,
        "total_pnl_delta_pct": round(total_pnl_delta / baseline_total_pnl, 6),
        "ev_windows_improved": sum(
            1 for v in by_window.values()
            if v["delta"]["expected_value_score"] > 0
        ),
        "ev_windows_regressed": sum(
            1 for v in by_window.values()
            if v["delta"]["expected_value_score"] < 0
        ),
        "pnl_windows_improved": sum(
            1 for v in by_window.values()
            if v["delta"]["total_pnl"] > 0
        ),
        "pnl_windows_regressed": sum(
            1 for v in by_window.values()
            if v["delta"]["total_pnl"] < 0
        ),
        "max_drawdown_delta_max": max(
            v["delta"]["max_drawdown_pct"] for v in by_window.values()
        ),
        "trade_count_delta_sum": sum(v["delta"]["trade_count"] for v in by_window.values()),
        "win_rate_delta_min": min(v["delta"]["win_rate"] for v in by_window.values()),
    }


def _build_payload() -> dict[str, Any]:
    universe = get_universe()
    rows = []
    for label, cfg in WINDOWS.items():
        for variant_name, variant in VARIANTS.items():
            result = _run_window(universe, cfg, variant)
            row = {
                "window": label,
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
                "state_note": cfg["state_note"],
                "variant": variant_name,
                "ranking_variant": variant,
                **result,
            }
            rows.append(row)
            m = result["metrics"]
            print(
                f"[{label} {variant_name}] EV={m['expected_value_score']} "
                f"PnL={m['total_pnl']} SharpeD={m['sharpe_daily']} "
                f"DD={m['max_drawdown_pct']} WR={m['win_rate']} "
                f"trades={m['trade_count']}"
            )

    baseline_rows = {
        label: next(r for r in rows if r["window"] == label and r["variant"] == "baseline_existing_order")
        for label in WINDOWS
    }

    summary = OrderedDict()
    for variant_name in list(VARIANTS.keys())[1:]:
        by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
        for label in WINDOWS:
            before = baseline_rows[label]["metrics"]
            candidate = next(r for r in rows if r["window"] == label and r["variant"] == variant_name)
            by_window[label] = {
                "before": before,
                "after": candidate["metrics"],
                "delta": _delta(candidate["metrics"], before),
                "entry_decision_summary": candidate.get("entry_decision_summary"),
            }
        summary[variant_name] = {
            "by_window": by_window,
            "aggregate": _aggregate(by_window),
        }

    best_variant, best_summary = max(
        summary.items(),
        key=lambda item: (
            item[1]["aggregate"]["ev_windows_improved"],
            -item[1]["aggregate"]["ev_windows_regressed"],
            item[1]["aggregate"]["expected_value_score_delta_sum"],
            item[1]["aggregate"]["total_pnl_delta_sum"],
        ),
    )
    best_agg = best_summary["aggregate"]
    accepted = (
        best_agg["ev_windows_improved"] >= 2
        and best_agg["expected_value_score_delta_sum"] > 0.10
        and (
            best_agg["total_pnl_delta_pct"] > 0.05
            or best_agg["max_drawdown_delta_max"] < -0.01
            or (
                best_agg["trade_count_delta_sum"] > 0
                and best_agg["win_rate_delta_min"] >= 0
            )
        )
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "accepted" if accepted else "rejected",
        "decision": "accepted" if accepted else "rejected",
        "lane": "alpha_search",
        "change_type": "candidate_slot_ranking",
        "hypothesis": (
            "Among already survived candidates, medium-term ticker-vs-SPY "
            "relative strength may allocate scarce entry slots better than the "
            "accepted confidence/breakout subsequence order."
        ),
        "parameters": {
            "single_causal_variable": "pre-slot candidate ranking key",
            "baseline_order": "accepted signal_engine order plus production_parity slot plan",
            "tested_orders": list(VARIANTS.keys())[1:],
            "fields_used": [
                "ticker_ret20_minus_spy_pct",
                "spy_relative_leader",
                "trade_quality_score",
                "confidence_score",
            ],
            "locked_variables": [
                "universe",
                "signal generation",
                "entry filters",
                "position sizing",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "MAX_PER_SECTOR",
                "gap cancels",
                "scarce-slot breakout deferral thresholds",
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
        "market_regime_summary": {label: cfg["state_note"] for label, cfg in WINDOWS.items()},
        "before_metrics": {label: baseline_rows[label]["metrics"] for label in WINDOWS},
        "after_metrics": {
            "best_variant": best_variant,
            **{label: best_summary["by_window"][label]["after"] for label in WINDOWS},
        },
        "delta_metrics": {
            "best_variant": best_variant,
            "by_window": {
                label: best_summary["by_window"][label]["delta"]
                for label in WINDOWS
            },
            "aggregate": best_agg,
        },
        "all_variant_summaries": summary,
        "gate4_basis": (
            "Accepted by the three-window fixed protocol."
            if accepted else
            "Rejected because no slot-rank variant cleared the fixed-window Gate 4 materiality and stability bar."
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted later, implement this as a shared production_parity "
                "candidate-ranking helper called by both run.py and backtester.py."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft-ranking remains sample-limited, so this tests a "
                "deterministic slot-allocation alpha with production-available fields."
            ),
        },
        "history_guardrails": {
            "not_pullback_rs_direct_promotion": True,
            "not_sector_or_universe_expansion": True,
            "not_sizing_multiplier_retry": True,
            "not_exit_lifecycle_retry": True,
        },
        "rejection_reason": (
            None if accepted else
            "The tested medium-term RS slot ordering did not improve a majority of windows with material aggregate EV/PnL evidence."
        ),
        "next_retry_requires": [
            "Do not promote medium-term RS as a global slot rank without majority-window EV evidence.",
            "A valid retry should be scoped to a narrower collision class, such as same-day slot-sliced candidates only or sector-neutral candidate pairs.",
            "Any positive retry must be implemented through shared production/backtest policy before acceptance.",
        ],
        "related_files": [
            "quant/experiments/exp_20260503_010_rs_slot_ranking.py",
            "data/experiments/exp-20260503-010/rs_slot_ranking.json",
            "experiments/logs/exp-20260503-010.json",
            "experiments/tickets/exp-20260503-010.json",
        ],
    }


def main() -> int:
    payload = _build_payload()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)

    text = json.dumps(payload, indent=2, ensure_ascii=False)
    OUT_JSON.write_text(text + "\n", encoding="utf-8")
    LOG_JSON.write_text(text + "\n", encoding="utf-8")
    TICKET_JSON.write_text(text + "\n", encoding="utf-8")

    compact = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    with EXPERIMENT_LOG.open("a", encoding="utf-8") as f:
        f.write(compact + "\n")

    print(
        f"\n{payload['experiment_id']} {payload['status']} "
        f"best={payload['after_metrics']['best_variant']} "
        f"aggregate={payload['delta_metrics']['aggregate']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
