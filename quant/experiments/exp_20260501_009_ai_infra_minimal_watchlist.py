"""exp-20260501-009 minimal AI infrastructure watchlist promotion test.

Alpha search. Test whether a minimal production-promotable universe expansion
using BE + INTC improves the accepted stack. This changes one causal variable:
tradeable universe membership. Signal generation, ranking, sizing, exits,
add-ons, LLM/news replay, and all thresholds stay locked.
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
import risk_engine  # noqa: E402


EXPERIMENT_ID = "exp-20260501-009"
SOURCE_EXPERIMENT_ID = "exp-20260501-008"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "ai_infra_minimal_watchlist.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": (
            f"data/experiments/{SOURCE_EXPERIMENT_ID}/"
            "ohlcv_aug_20251023_20260421.json"
        ),
        "state_note": "slow-melt bull / accepted-stack dominant tape",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": (
            f"data/experiments/{SOURCE_EXPERIMENT_ID}/"
            "ohlcv_aug_20250423_20251022.json"
        ),
        "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": (
            f"data/experiments/{SOURCE_EXPERIMENT_ID}/"
            "ohlcv_aug_20241002_20250422.json"
        ),
        "state_note": "mixed-to-weak older tape with lower win rate",
    }),
])

VARIANTS = OrderedDict([
    ("add_be_intc", ["BE", "INTC"]),
    ("add_intc_only", ["INTC"]),
    ("add_be_only", ["BE"]),
])

SECTOR_PATCH = {
    "BE": "Energy",
    "INTC": "Technology",
}

BASELINE = {
    "late_strong": {
        "expected_value_score": 2.7000,
        "sharpe_daily": 4.30,
        "total_pnl": 62788.03,
        "total_return_pct": 0.6279,
        "max_drawdown_pct": 0.0439,
        "win_rate": 0.7895,
        "trade_count": 19,
        "survival_rate": 0.8039,
        "tail_loss_share": 0.5045,
    },
    "mid_weak": {
        "expected_value_score": 1.2036,
        "sharpe_daily": 2.58,
        "total_pnl": 46654.10,
        "total_return_pct": 0.4665,
        "max_drawdown_pct": 0.0799,
        "win_rate": 0.5238,
        "trade_count": 21,
        "survival_rate": 0.7925,
        "tail_loss_share": 0.4839,
    },
    "old_thin": {
        "expected_value_score": 0.2563,
        "sharpe_daily": 1.27,
        "total_pnl": 20181.65,
        "total_return_pct": 0.2018,
        "max_drawdown_pct": 0.0688,
        "win_rate": 0.4091,
        "trade_count": 22,
        "survival_rate": 0.9167,
        "tail_loss_share": 0.4234,
    },
}


def _metrics(result: dict) -> dict:
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": (result.get("benchmarks") or {}).get(
            "strategy_total_return_pct"
        ),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
        "tail_loss_share": result.get("tail_loss_share"),
    }


def _delta(after: dict, before: dict) -> dict:
    out = {}
    for key, before_val in before.items():
        after_val = after.get(key)
        out[key] = (
            round(after_val - before_val, 6)
            if isinstance(after_val, (int, float))
            and isinstance(before_val, (int, float))
            else None
        )
    return out


def _candidate_trade_summary(result: dict, added: set[str]) -> dict:
    trades = [t for t in result.get("trades", []) if t.get("ticker") in added]
    by_ticker = {}
    for trade in trades:
        ticker = trade.get("ticker")
        rec = by_ticker.setdefault(ticker, {"trades": 0, "pnl": 0.0, "wins": 0})
        rec["trades"] += 1
        rec["pnl"] += float(trade.get("pnl") or 0.0)
        if (trade.get("pnl") or 0) > 0:
            rec["wins"] += 1
    for rec in by_ticker.values():
        rec["pnl"] = round(rec["pnl"], 2)
        rec["win_rate"] = (
            round(rec["wins"] / rec["trades"], 4) if rec["trades"] else None
        )
    return {
        "candidate_trade_count": len(trades),
        "candidate_pnl": round(sum(float(t.get("pnl") or 0.0) for t in trades), 2),
        "by_ticker": by_ticker,
    }


def _run_window(universe: list[str], window: dict) -> dict:
    engine = BacktestEngine(
        universe,
        start=window["start"],
        end=window["end"],
        ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
    )
    return engine.run()


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)

    baseline_universe = sorted(get_universe())
    original_sector_map = dict(risk_engine.SECTOR_MAP)
    risk_engine.SECTOR_MAP.update(SECTOR_PATCH)

    rows = []
    summary = {}
    for variant, added in VARIANTS.items():
        universe = sorted(set(baseline_universe) | set(added))
        variant_rows = []
        for label, window in WINDOWS.items():
            result = _run_window(universe, window)
            if "error" in result:
                raise RuntimeError(f"{variant} {label} failed: {result['error']}")
            metrics = _metrics(result)
            delta = _delta(metrics, BASELINE[label])
            row = {
                "window": label,
                "variant": variant,
                "added": added,
                "metrics": metrics,
                "delta": delta,
                "candidate_trades": _candidate_trade_summary(result, set(added)),
            }
            rows.append(row)
            variant_rows.append(row)

        pnl_delta_sum = round(sum(r["delta"]["total_pnl"] for r in variant_rows), 2)
        baseline_pnl_sum = round(
            sum(BASELINE[r["window"]]["total_pnl"] for r in variant_rows), 2
        )
        summary[variant] = {
            "added": added,
            "by_window": {
                r["window"]: {
                    "before": BASELINE[r["window"]],
                    "after": r["metrics"],
                    "delta": r["delta"],
                    "candidate_trades": r["candidate_trades"],
                }
                for r in variant_rows
            },
            "aggregate": {
                "expected_value_score_delta_sum": round(
                    sum(r["delta"]["expected_value_score"] for r in variant_rows), 4
                ),
                "total_pnl_delta_sum": pnl_delta_sum,
                "baseline_total_pnl_sum": baseline_pnl_sum,
                "total_pnl_delta_pct": (
                    round(pnl_delta_sum / baseline_pnl_sum, 6)
                    if baseline_pnl_sum else None
                ),
                "ev_windows_improved": sum(
                    1 for r in variant_rows if r["delta"]["expected_value_score"] > 0
                ),
                "ev_windows_regressed": sum(
                    1 for r in variant_rows if r["delta"]["expected_value_score"] < 0
                ),
                "pnl_windows_improved": sum(
                    1 for r in variant_rows if r["delta"]["total_pnl"] > 0
                ),
                "pnl_windows_regressed": sum(
                    1 for r in variant_rows if r["delta"]["total_pnl"] < 0
                ),
                "max_drawdown_delta_max": round(
                    max(r["delta"]["max_drawdown_pct"] for r in variant_rows), 6
                ),
                "trade_count_delta_sum": sum(
                    r["delta"]["trade_count"] for r in variant_rows
                ),
                "win_rate_delta_min": round(
                    min(r["delta"]["win_rate"] for r in variant_rows), 6
                ),
                "candidate_trade_count_sum": sum(
                    r["candidate_trades"]["candidate_trade_count"]
                    for r in variant_rows
                ),
                "candidate_pnl_sum": round(
                    sum(r["candidate_trades"]["candidate_pnl"] for r in variant_rows),
                    2,
                ),
            },
        }

    best_variant = max(
        summary,
        key=lambda name: (
            summary[name]["aggregate"]["ev_windows_improved"],
            summary[name]["aggregate"]["expected_value_score_delta_sum"],
            summary[name]["aggregate"]["total_pnl_delta_sum"],
        ),
    )
    best = summary[best_variant]
    agg = best["aggregate"]
    accepted = bool(
        agg["total_pnl_delta_pct"] is not None
        and agg["total_pnl_delta_pct"] > 0.05
        and agg["ev_windows_improved"] >= 2
        and agg["ev_windows_regressed"] == 0
        and agg["max_drawdown_delta_max"] <= 0.02
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "accepted" if accepted else "rejected",
        "decision": "accepted" if accepted else "rejected",
        "lane": "alpha_search",
        "change_type": "minimal_ai_infra_watchlist_expansion",
        "hypothesis": (
            "A minimal AI infrastructure watchlist promotion using BE and INTC "
            "can add theme beta in different fixed windows while avoiding the "
            "negative old_thin contributors seen in exp-20260501-008."
        ),
        "alpha_hypothesis_category": "candidate_universe",
        "parameters": {
            "single_causal_variable": "tradeable universe membership",
            "tested_variants": VARIANTS,
            "sector_map_patch": SECTOR_PATCH,
            "source_experiment": SOURCE_EXPERIMENT_ID,
            "locked_variables": [
                "signal generation",
                "entry filters",
                "candidate ranking",
                "position sizing",
                "position caps",
                "portfolio heat",
                "add-ons",
                "exits",
                "LLM/news replay",
                "earnings strategy",
            ],
        },
        "date_range": {
            "primary": "2025-10-23 -> 2026-04-21",
            "secondary": [
                "2025-04-23 -> 2025-10-22",
                "2024-10-02 -> 2025-04-22",
            ],
        },
        "market_regime_summary": {
            label: window["state_note"] for label, window in WINDOWS.items()
        },
        "before_metrics": BASELINE,
        "after_metrics": summary,
        "best_variant": best_variant,
        "best_variant_gate4_passed": accepted,
        "gate4_basis": (
            "Accepted: best variant improved EV in at least two windows, regressed "
            "none, improved aggregate PnL by more than 5%, and kept drawdown "
            "within the existing cap."
            if accepted else
            "Rejected: no variant cleared the multi-window EV and aggregate PnL gates."
        ),
        "production_impact": {
            "shared_policy_changed": accepted,
            "backtester_adapter_changed": False,
            "run_adapter_changed": accepted,
            "replay_only": False,
            "parity_test_added": False,
            "note": (
                "If accepted, production parity is satisfied by adding the tickers "
                "to filter.WATCHLIST/news sources and sector tags to risk_engine."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft-ranking remains sample-limited; this experiment avoids "
                "that data constraint by testing deterministic universe membership."
            ),
        },
        "history_guardrails": {
            "not_etf_expansion_repeat": True,
            "not_nearby_threshold_tuning": True,
            "excludes_observed_negative_old_thin_contributors": ["TLN", "VST"],
            "excludes_observed_negative_datacenter_contributor": ["DBRG"],
        },
        "rows": rows,
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            f"quant/experiments/{Path(__file__).name}",
        ],
    }

    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    LOG_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    TICKET_JSON.write_text(
        json.dumps({
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "title": "Minimal AI infra watchlist",
            "summary": f"Best {best_variant} accepted={accepted}",
            "best_variant": best_variant,
            "best_aggregate": agg,
            "production_impact": payload["production_impact"],
        }, indent=2),
        encoding="utf-8",
    )
    with (REPO_ROOT / "docs" / "experiment_log.jsonl").open(
        "a", encoding="utf-8"
    ) as f:
        compact = {k: v for k, v in payload.items() if k != "rows"}
        f.write(json.dumps(compact) + "\n")

    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "best_variant": best_variant,
        "best_aggregate": agg,
    }, indent=2))

    risk_engine.SECTOR_MAP.clear()
    risk_engine.SECTOR_MAP.update(original_sector_map)


if __name__ == "__main__":
    main()
