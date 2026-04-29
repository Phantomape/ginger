"""exp-20260428-036: state-filtered Energy ETF universe replay.

Alpha search. exp-20260428-035 showed that adding XLE/USO directly released
late-window upside but hurt other windows. This replay tests whether those
proxies should only compete for slots when their own signal-day state is
strong, without changing entries, exits, sizing, add-ons, gap cancels, or LLM.
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

import backtester as backtester_module  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260428-036"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260428_036_energy_etf_state_filter.json"

ENERGY_ETFS = {"XLE", "USO"}

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
    ("energy_etf_unfiltered", {
        "min_rs_vs_spy": None,
        "min_pct_from_52w_high": None,
        "strategy": "any",
    }),
    ("energy_etf_rs_positive", {
        "min_rs_vs_spy": 0.0,
        "min_pct_from_52w_high": None,
        "strategy": "any",
    }),
    ("energy_etf_rs_3pct", {
        "min_rs_vs_spy": 0.03,
        "min_pct_from_52w_high": None,
        "strategy": "any",
    }),
    ("energy_etf_near_high_2pct", {
        "min_rs_vs_spy": 0.0,
        "min_pct_from_52w_high": -0.02,
        "strategy": "any",
    }),
    ("energy_etf_breakout_only", {
        "min_rs_vs_spy": 0.0,
        "min_pct_from_52w_high": None,
        "strategy": "breakout_long",
    }),
])


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    entry = result.get("entry_execution_attribution") or {}
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
        "entry_reason_counts": entry.get("reason_counts", {}),
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


def _energy_etf_passes(sig: dict, rule: dict | None) -> bool:
    if not rule or sig.get("ticker") not in ENERGY_ETFS:
        return True
    if rule.get("strategy") != "any" and sig.get("strategy") != rule.get("strategy"):
        return False
    conditions = sig.get("conditions_met") or {}
    rs_vs_spy = conditions.get("rs_vs_spy")
    pct_from_52w_high = conditions.get("pct_from_52w_high")
    min_rs = rule.get("min_rs_vs_spy")
    min_high = rule.get("min_pct_from_52w_high")
    if min_rs is not None and (rs_vs_spy is None or rs_vs_spy < min_rs):
        return False
    if min_high is not None and (
        pct_from_52w_high is None or pct_from_52w_high < min_high
    ):
        return False
    return True


def _run_window(universe: list[str], cfg: dict, rule: dict | None) -> dict:
    original_filter = backtester_module.filter_entry_signal_candidates
    filtered_out = []

    def state_filtered_entry_candidates(signals, *args, **kwargs):
        planned, audit = original_filter(signals, *args, **kwargs)
        if not rule:
            audit["energy_etf_state_dropped"] = []
            return planned, audit
        kept = []
        for sig in planned:
            if _energy_etf_passes(sig, rule):
                kept.append(sig)
            else:
                filtered_out.append({
                    "ticker": sig.get("ticker"),
                    "strategy": sig.get("strategy"),
                    "conditions_met": sig.get("conditions_met"),
                    "confidence_score": sig.get("confidence_score"),
                    "trade_quality_score": sig.get("trade_quality_score"),
                })
        audit["energy_etf_state_dropped"] = list(filtered_out)
        audit["signals_after_entry_filters"] = len(kept)
        return kept, audit

    try:
        backtester_module.filter_entry_signal_candidates = state_filtered_entry_candidates
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
        backtester_module.filter_entry_signal_candidates = original_filter

    if "error" in result:
        raise RuntimeError(result["error"])
    trades = [
        {
            "ticker": t.get("ticker"),
            "strategy": t.get("strategy"),
            "sector": t.get("sector"),
            "entry_date": t.get("entry_date"),
            "exit_date": t.get("exit_date"),
            "pnl": t.get("pnl"),
            "exit_reason": t.get("exit_reason"),
        }
        for t in result.get("trades", [])
        if t.get("ticker") in ENERGY_ETFS
    ]
    return {
        "metrics": _metrics(result),
        "energy_etf_trades": trades,
        "energy_etf_state_dropped": filtered_out,
    }


def _variant_universe(base_universe: list[str], variant: str) -> list[str]:
    if variant == "baseline":
        return sorted(base_universe)
    return sorted(set(base_universe) | ENERGY_ETFS)


def run_experiment() -> dict:
    base_universe = sorted(get_universe())
    rows = []
    for label, cfg in WINDOWS.items():
        for variant, rule in VARIANTS.items():
            result = _run_window(_variant_universe(base_universe, variant), cfg, rule)
            rows.append({
                "window": label,
                "variant": variant,
                "rule": rule,
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
                "state_note": cfg["state_note"],
                **result,
            })
            m = result["metrics"]
            print(
                f"[{label} {variant}] EV={m['expected_value_score']} "
                f"PnL={m['total_pnl']} SharpeD={m['sharpe_daily']} "
                f"DD={m['max_drawdown_pct']} WR={m['win_rate']} "
                f"trades={m['trade_count']} energy_trades={len(result['energy_etf_trades'])} "
                f"energy_dropped={len(result['energy_etf_state_dropped'])}"
            )

    baseline_rows = {
        label: next(
            row for row in rows
            if row["window"] == label and row["variant"] == "baseline"
        )
        for label in WINDOWS
    }
    summary = OrderedDict()
    for variant in VARIANTS:
        if variant == "baseline":
            continue
        by_window = OrderedDict()
        for label in WINDOWS:
            before = baseline_rows[label]["metrics"]
            row = next(
                row for row in rows
                if row["window"] == label and row["variant"] == variant
            )
            by_window[label] = {
                "before": before,
                "after": row["metrics"],
                "delta": _delta(row["metrics"], before),
                "energy_etf_trades": row["energy_etf_trades"],
                "energy_etf_state_dropped_count": len(row["energy_etf_state_dropped"]),
            }
        baseline_total_pnl = round(sum(v["before"]["total_pnl"] for v in by_window.values()), 2)
        total_pnl_delta = round(sum(v["delta"]["total_pnl"] for v in by_window.values()), 2)
        summary[variant] = {
            "rule": VARIANTS[variant],
            "by_window": by_window,
            "aggregate": {
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
                "energy_etf_trades": sum(len(v["energy_etf_trades"]) for v in by_window.values()),
                "energy_etf_state_dropped": sum(
                    v["energy_etf_state_dropped_count"] for v in by_window.values()
                ),
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
        and best_agg["windows_regressed"] == 0
        and (
            best_agg["expected_value_score_delta_sum"] > 0.10
            or best_agg["total_pnl_delta_pct"] > 0.05
            or best_agg["max_drawdown_delta_max"] < -0.01
            or (best_agg["trade_count_delta_sum"] > 0 and best_agg["win_rate_delta_min"] >= 0)
        )
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "accepted_shadow" if accepted else "rejected",
        "decision": "accepted_shadow" if accepted else "rejected",
        "lane": "alpha_search",
        "change_type": "state_filtered_universe_expansion",
        "hypothesis": (
            "Energy ETF proxies may be worth scarce slot competition only when "
            "their own signal-day state confirms relative strength or near-high momentum."
        ),
        "why_tested": (
            "exp-20260428-035 rejected simple ETF expansion but identified Energy/USO "
            "late-window upside and required a state discriminator for any valid retry."
        ),
        "parameters": {
            "single_causal_variable": "Energy ETF tradeability state predicate",
            "energy_etfs": sorted(ENERGY_ETFS),
            "tested_variants": VARIANTS,
            "locked_variables": [
                "existing stock universe",
                "signal generation for all non-Energy-ETF tickers",
                "risk multipliers",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "MAX_POSITIONS",
                "MAX_PER_SECTOR",
                "candidate ordering",
                "upside/adverse gap cancels",
                "day-2 add-on trigger and fraction",
                "all exits",
                "scarce-slot routing",
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
                "Shadow-accepted because the best state-filtered Energy ETF variant passed Gate 4; "
                "production promotion still requires shared policy and watchlist/news parity."
                if accepted else
                "Rejected because no state-filtered Energy ETF variant improved a majority of fixed windows without regression."
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
                "LLM soft-ranking remains sample-limited, so this deterministic "
                "candidate-pool alpha was tested instead."
            ),
        },
        "history_guardrails": {
            "not_repeating_simple_etf_expansion": (
                "This only retries exp-20260428-035 with the required state discriminator."
            ),
            "not_broad_macro_overlay": True,
            "not_addon_or_gap_threshold_tuning": True,
        },
        "rows": rows,
        "summary": summary,
        "rejection_reason": (
            None if accepted else
            "Energy ETF state filters did not solve the slot displacement problem across fixed windows."
        ),
        "next_retry_requires": [
            "Do not retry Energy ETF universe expansion with only self-OHLCV state predicates.",
            "A valid retry needs an orthogonal event/state source, such as energy breadth, fresh commodity news, or production watchlist parity.",
            "If a shadow result is promoted later, implement it in shared production/backtest policy first.",
        ],
    }


def main() -> int:
    payload = run_experiment()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
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
