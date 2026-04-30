"""exp-20260430-025 breakout gap/quality ranking.

Alpha search. Test one candidate-ranking variable: the ordering used inside
the existing breakout_long subsequence. Production code is unchanged unless
the fixed-window protocol accepts a variant.
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


EXPERIMENT_ID = "exp-20260430-025"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260430_025_breakout_gap_quality_ranking.json"
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
    ("baseline_pct52_conf", "baseline"),
    ("quality_then_pct52", "quality_then_pct52"),
    ("low_gap_then_pct52", "low_gap_then_pct52"),
    ("low_gap_quality_pct52", "low_gap_quality_pct52"),
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


def _pct_from_52w_high(sig: dict) -> float:
    value = (sig.get("conditions_met") or {}).get("pct_from_52w_high")
    return float(value) if value is not None else float("-inf")


def _quality(sig: dict) -> float:
    value = sig.get("trade_quality_score")
    if value is None:
        value = sig.get("confidence_score", 0)
    return float(value or 0)


def _negative_gap(sig: dict) -> float:
    value = sig.get("gap_vulnerability_pct")
    if value is None:
        return float("-inf")
    return -float(value)


def _ranked_breakouts(signals: list[dict], variant: str) -> list[dict]:
    breakout_signals = [s for s in signals if s.get("strategy") == "breakout_long"]
    if len(breakout_signals) <= 1 or variant == "baseline":
        return list(signals)

    if variant == "quality_then_pct52":
        key = lambda s: (_quality(s), _pct_from_52w_high(s), s.get("confidence_score", 0))
    elif variant == "low_gap_then_pct52":
        key = lambda s: (_negative_gap(s), _pct_from_52w_high(s), s.get("confidence_score", 0))
    elif variant == "low_gap_quality_pct52":
        key = lambda s: (_negative_gap(s), _quality(s), _pct_from_52w_high(s))
    else:
        raise ValueError(f"Unknown variant: {variant}")

    ranked_breakouts = sorted(breakout_signals, key=key, reverse=True)
    breakout_iter = iter(ranked_breakouts)
    reranked = []
    for signal in signals:
        if signal.get("strategy") == "breakout_long":
            reranked.append(next(breakout_iter))
        else:
            reranked.append(signal)
    return reranked


@contextmanager
def _ranking_patch(variant: str):
    original = signal_engine.rank_signals_for_allocation

    def patched(signals):
        if variant == "baseline":
            return original(signals)
        return _ranked_breakouts(list(signals or []), variant)

    signal_engine.rank_signals_for_allocation = patched
    try:
        yield
    finally:
        signal_engine.rank_signals_for_allocation = original


def _run_window(universe: list[str], cfg: dict, variant: str) -> dict:
    with _ranking_patch(variant):
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
    return {
        "metrics": _metrics(result),
        "trades": result.get("trades", []),
    }


def _build_payload() -> dict:
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
        label: next(r for r in rows if r["window"] == label and r["variant"] == "baseline_pct52_conf")
        for label in WINDOWS
    }
    summary = OrderedDict()
    for variant_name in list(VARIANTS.keys())[1:]:
        by_window = OrderedDict()
        for label in WINDOWS:
            baseline = baseline_rows[label]
            candidate = next(r for r in rows if r["window"] == label and r["variant"] == variant_name)
            by_window[label] = {
                "before": baseline["metrics"],
                "after": candidate["metrics"],
                "delta": _delta(candidate["metrics"], baseline["metrics"]),
            }
        baseline_total_pnl = round(sum(v["before"]["total_pnl"] for v in by_window.values()), 2)
        total_pnl_delta = round(sum(v["delta"]["total_pnl"] for v in by_window.values()), 2)
        summary[variant_name] = {
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

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "accepted" if accepted else "rejected",
        "decision": "accepted" if accepted else "rejected",
        "lane": "alpha_search",
        "change_type": "candidate_ranking",
        "hypothesis": (
            "Within the existing breakout_long subsequence, low gap vulnerability "
            "and setup quality may rank marginal slot candidates better than pure "
            "proximity to the 52-week high."
        ),
        "parameters": {
            "single_causal_variable": "breakout_long subsequence ranking key",
            "baseline_order": "pct_from_52w_high then confidence_score",
            "tested_orders": list(VARIANTS.keys())[1:],
            "locked_variables": [
                "universe",
                "signal generation",
                "entry filters",
                "all non-breakout candidate ordering",
                "position sizing",
                "scarce-slot breakout deferral",
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
        "date_range": {"start": WINDOWS["late_strong"]["start"], "end": WINDOWS["late_strong"]["end"]},
        "secondary_windows": [
            {"start": WINDOWS["mid_weak"]["start"], "end": WINDOWS["mid_weak"]["end"]},
            {"start": WINDOWS["old_thin"]["start"], "end": WINDOWS["old_thin"]["end"]},
        ],
        "market_regime_summary": {label: cfg["state_note"] for label, cfg in WINDOWS.items()},
        "before_metrics": {label: baseline_rows[label]["metrics"] for label in WINDOWS},
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
                if accepted else
                "Rejected because no breakout ranking variant improved a majority of fixed windows with material EV/PnL evidence."
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
                "LLM soft ranking remains sample-limited, so this tested a deterministic "
                "breakout ranking alpha with fields already present in production/backtest."
            ),
        },
        "history_guardrails": {
            "not_same_sector_candidate_chooser": True,
            "not_breakout_deferral_quality_exception": True,
            "not_breadth_only_ranking": True,
            "not_global_capacity_change": True,
            "mechanism_note": (
                "This changes only the existing breakout subsequence order, not which "
                "breakouts are allowed through scarce-slot deferral."
            ),
        },
        "rows": rows,
        "summary": summary,
        "rejection_reason": None if accepted else (
            "The best tested ordering failed the fixed-window majority/materiality gate."
        ),
        "next_retry_requires": [
            "Do not retry nearby breakout subsequence sorting keys without candidate replacement evidence.",
            "A valid retry needs event/news context or a ranking signal that changes executed trades in at least two windows.",
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
    TICKET_JSON.write_text(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "title": "Breakout gap-quality ranking",
        "summary": payload["delta_metrics"]["gate4_basis"],
        "best_variant": payload["delta_metrics"]["best_variant"],
        "aggregate": payload["delta_metrics"]["aggregate"],
        "production_impact": payload["production_impact"],
    }, indent=2), encoding="utf-8")
    with (REPO_ROOT / "docs" / "experiment_log.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, separators=(",", ":")) + "\n")
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
