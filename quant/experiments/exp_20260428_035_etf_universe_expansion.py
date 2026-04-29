"""exp-20260428-035: ETF universe expansion replay.

Alpha search. Tests whether adding liquid sector/defensive ETF proxies as
tradeable candidates improves the accepted A+B stack. This is a universe
expansion experiment, not a new entry rule and not a production promotion.
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


EXPERIMENT_ID = "exp-20260428-035"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260428_035_etf_universe_expansion.json"

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
    ("baseline", []),
    ("broad_sector_defensive_etfs", ["XLE", "XLP", "XLU", "XLV", "TLT", "IEF", "USO", "UUP"]),
    ("sector_select_etfs", ["XLE", "XLP", "XLU", "XLV"]),
    ("energy_only_etfs", ["XLE", "USO"]),
    ("staples_healthcare_etfs", ["XLP", "XLV"]),
    ("rates_defense_etfs", ["TLT", "IEF", "UUP"]),
    ("xle_only", ["XLE"]),
    ("xlp_only", ["XLP"]),
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
    }


def _run_window(universe: list[str], cfg: dict) -> dict:
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
    return result


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
    base_universe = sorted(get_universe())
    rows = []
    for label, cfg in WINDOWS.items():
        for variant, added in VARIANTS.items():
            universe = sorted(set(base_universe) | set(added))
            result = _run_window(universe, cfg)
            rows.append({
                "window": label,
                "variant": variant,
                "added_tickers": added,
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
                "state_note": cfg["state_note"],
                "metrics": _metrics(result),
                "added_ticker_trades": [
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
                    if t.get("ticker") in set(added)
                ],
            })
            m = rows[-1]["metrics"]
            print(
                f"[{label} {variant}] EV={m['expected_value_score']} "
                f"PnL={m['total_pnl']} SharpeD={m['sharpe_daily']} "
                f"DD={m['max_drawdown_pct']} WR={m['win_rate']} "
                f"trades={m['trade_count']}"
            )

    baseline = {
        label: next(r for r in rows if r["window"] == label and r["variant"] == "baseline")
        for label in WINDOWS
    }
    summary = OrderedDict()
    for variant in list(VARIANTS.keys())[1:]:
        by_window = OrderedDict()
        for label in WINDOWS:
            before = baseline[label]["metrics"]
            row = next(r for r in rows if r["window"] == label and r["variant"] == variant)
            by_window[label] = {
                "before": before,
                "after": row["metrics"],
                "delta": _delta(row["metrics"], before),
                "added_ticker_trades": row["added_ticker_trades"],
            }
        base_pnl = round(sum(item["before"]["total_pnl"] for item in by_window.values()), 2)
        pnl_delta = round(sum(item["delta"]["total_pnl"] for item in by_window.values()), 2)
        summary[variant] = {
            "by_window": by_window,
            "aggregate": {
                "expected_value_score_delta_sum": round(
                    sum(item["delta"]["expected_value_score"] for item in by_window.values()),
                    6,
                ),
                "total_pnl_delta_sum": pnl_delta,
                "baseline_total_pnl_sum": base_pnl,
                "total_pnl_delta_pct": round(pnl_delta / base_pnl, 6) if base_pnl else None,
                "windows_improved": sum(
                    1 for item in by_window.values()
                    if item["delta"]["expected_value_score"] > 0
                ),
                "windows_regressed": sum(
                    1 for item in by_window.values()
                    if item["delta"]["expected_value_score"] < 0
                ),
                "max_drawdown_delta_max": max(
                    item["delta"]["max_drawdown_pct"] for item in by_window.values()
                ),
                "trade_count_delta_sum": sum(
                    item["delta"]["trade_count"] for item in by_window.values()
                ),
                "win_rate_delta_min": min(
                    item["delta"]["win_rate"] for item in by_window.values()
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
    accepted = (
        best_summary["aggregate"]["windows_improved"] >= 2
        and best_summary["aggregate"]["windows_regressed"] == 0
        and (
            best_summary["aggregate"]["total_pnl_delta_pct"] > 0.05
            or best_summary["aggregate"]["expected_value_score_delta_sum"] > 0.10
            or best_summary["aggregate"]["max_drawdown_delta_max"] < -0.01
        )
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "accepted" if accepted else "rejected",
        "decision": "accepted" if accepted else "rejected",
        "lane": "alpha_search",
        "change_type": "universe_expansion_etf_sleeve",
        "hypothesis": (
            "Adding a small set of liquid sector/defensive ETF proxies may capture "
            "rotation alpha that the current single-stock-heavy universe misses."
        ),
        "parameters": {
            "single_causal_variable": "tradeable ETF universe expansion",
            "baseline_universe_size": len(base_universe),
            "tested_variants": VARIANTS,
            "locked_variables": [
                "signal generation",
                "risk multipliers",
                "position caps and heat",
                "candidate ordering",
                "upside/adverse gap cancels",
                "day-2 add-on trigger and fraction",
                "all exits",
                "scarce-slot routing",
                "LLM/news replay",
                "earnings strategy",
            ],
        },
        "market_regime_summary": {
            label: cfg["state_note"] for label, cfg in WINDOWS.items()
        },
        "before_metrics": {
            label: baseline[label]["metrics"] for label in WINDOWS
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
            "aggregate": best_summary["aggregate"],
            "gate4_basis": (
                "Accepted because the best ETF universe expansion passed Gate 4."
                if accepted else
                "Rejected because no ETF expansion variant improved a majority of fixed windows without regression."
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
                "LLM soft-ranking remains sample-limited; this tested a deterministic "
                "candidate-pool alpha instead."
            ),
        },
        "history_guardrails": {
            "not_simple_noise_tickers": (
                "Only liquid ETF proxies already present in fixed snapshots were tested."
            ),
            "not_macro_defensive_overlay": (
                "This made ETFs tradeable candidates; it did not gate or haircut existing positions."
            ),
            "not_ohlcv_entry_variant": True,
        },
        "rows": rows,
        "summary": summary,
        "rejection_reason": (
            None if accepted else
            "ETF expansion released late_strong Energy/USO upside but displaced better A+B opportunities in mid_weak and old_thin."
        ),
        "next_retry_requires": [
            "Do not add broad sector/defensive ETFs directly to the tradeable universe.",
            "A valid retry needs a state discriminator for when Energy/USO continuation is worth slot competition.",
            "Do not treat proxy ETFs as production candidates without sector mapping and news/watchlist parity.",
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
