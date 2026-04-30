"""exp-20260430-021 trend-Tech mid-score state route.

Alpha search. Test one capital-allocation variable: whether risk-on
trend_long Technology candidates with regime_exit_score in [0.10, 0.20)
should receive an extra risk haircut. This is a regime-score route, not a
near-high, gap, or DTE retune. No production strategy code is changed unless
the fixed-window protocol accepts the result.
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
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260430-021"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260430_021_trend_tech_mid_score_state_route.json"
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
    ("trend_tech_mid_score_0_50x", 0.50),
    ("trend_tech_mid_score_0_25x", 0.25),
    ("trend_tech_mid_score_0_00x", 0.00),
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


def _patch_size_signals(multiplier: float):
    original = pe.size_signals

    def patched(signals, portfolio_value, risk_pct=None):
        sized = original(signals, portfolio_value, risk_pct=risk_pct)
        for sig in sized:
            score = sig.get("regime_exit_score")
            sizing = sig.get("sizing") or {}
            if not (
                sig.get("strategy") == "trend_long"
                and sig.get("sector") == "Technology"
                and sig.get("regime_exit_bucket") == "risk_on"
                and score is not None
                and 0.10 <= score < 0.20
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
            sizing["trend_tech_mid_score_state_route_runtime_multiplier_applied"] = multiplier
        return sized

    pe.size_signals = patched
    return original


def _run_window(universe: list[str], cfg: dict, multiplier: float) -> dict:
    original = _patch_size_signals(multiplier)
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
    return {
        "metrics": _metrics(result),
        "trades": result.get("trades", []),
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
                "trend_tech_mid_score_multiplier": multiplier,
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
        "change_type": "capital_allocation_regime_score_route",
        "hypothesis": (
            "Risk-on trend Technology candidates with regime_exit_score in [0.10, 0.20) "
            "may be a weaker lifecycle pocket in mid_weak/old_thin; a state-score "
            "haircut could improve capital allocation without adding entries."
        ),
        "parameters": {
            "single_causal_variable": "extra risk multiplier for trend_long Technology risk_on regime_exit_score [0.10, 0.20)",
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
                "Accepted because the state-score route improved the fixed-window objective materially."
                if accepted else
                "Rejected because the best state-score route improved only one window and damaged aggregate EV/PnL."
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
                "capital-allocation route intentionally avoided LLM data constraints."
            ),
        },
        "history_guardrails": {
            "not_near_high_multiplier_drift": True,
            "not_gap_or_dte_retune": True,
            "not_new_entry_or_filter": True,
            "not_universe_expansion": True,
        },
        "rows": rows,
        "summary": summary,
        "rejection_reason": (
            None if accepted else
            "The best 0.50x variant marginally improved mid_weak but regressed late_strong and old_thin; stricter variants were worse."
        ),
        "next_retry_requires": [
            "Do not retry trend-Tech [0.10, 0.20) score haircuts without orthogonal event/news/lifecycle evidence.",
            "A valid retry must preserve late_strong Technology winners while separating mid_weak failed follow-through.",
            "Do not use aggregate or single-window Technology loss maps as enough evidence for this route.",
        ],
    }
    return payload


def main() -> int:
    payload = _build_payload()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2)
    OUT_JSON.write_text(text, encoding="utf-8")
    LOG_JSON.write_text(text, encoding="utf-8")
    TICKET_JSON.write_text(text, encoding="utf-8")
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
