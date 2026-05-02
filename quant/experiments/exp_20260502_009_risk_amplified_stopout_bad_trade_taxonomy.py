"""Observed-only risk-amplified stopout loss attribution.

This audit intentionally does not change strategy behavior. It asks whether
accepted-stack losses are concentrated in trades that received a realized risk
budget above the base risk, and compares the loss dollars to winner collateral
from applying the same risk normalization to comparable winners.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = REPO_ROOT / "data" / "backtest_results_20260501.json"
DEFAULT_OUTPUT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260502-009"
    / "exp_20260502_009_risk_amplified_stopout_bad_trade_taxonomy.json"
)


def _round(value: float | None, digits: int = 4) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def _risk_amp(trade: dict) -> float:
    base = float(trade.get("base_risk_pct") or 0.01)
    actual = float(trade.get("actual_risk_pct") or base)
    if base <= 0:
        return 1.0
    return actual / base


def _summary(rows: list[dict]) -> dict:
    if not rows:
        return {
            "count": 0,
            "pnl_sum": 0.0,
            "avg_pnl": None,
            "median_pnl": None,
            "tickers": [],
            "strategy_counts": {},
            "sector_counts": {},
            "entry_date_counts": {},
            "risk_amp_counts": {},
        }
    pnls = [float(row["pnl"]) for row in rows]
    return {
        "count": len(rows),
        "pnl_sum": _round(sum(pnls), 2),
        "avg_pnl": _round(sum(pnls) / len(pnls), 2),
        "median_pnl": _round(median(pnls), 2),
        "tickers": sorted({row["ticker"] for row in rows}),
        "strategy_counts": dict(Counter(row["strategy"] for row in rows)),
        "sector_counts": dict(Counter(row["sector"] for row in rows)),
        "entry_date_counts": dict(Counter(row["entry_date"] for row in rows)),
        "risk_amp_counts": dict(
            Counter(f"{float(row['risk_amp']):.2f}x" for row in rows)
        ),
    }


def _trade_row(trade: dict) -> dict:
    amp = _risk_amp(trade)
    pnl = float(trade.get("pnl") or 0.0)
    normalization_delta = pnl - (pnl / amp) if amp > 0 else 0.0
    return {
        "trade_key": trade.get("trade_key"),
        "ticker": trade.get("ticker"),
        "strategy": trade.get("strategy"),
        "sector": trade.get("sector") or "Unknown",
        "entry_date": trade.get("entry_date"),
        "exit_date": trade.get("exit_date"),
        "exit_reason": trade.get("exit_reason"),
        "pnl": _round(pnl, 2),
        "pnl_pct_net": _round(trade.get("pnl_pct_net"), 6),
        "base_risk_pct": _round(trade.get("base_risk_pct"), 6),
        "actual_risk_pct": _round(trade.get("actual_risk_pct"), 6),
        "risk_amp": _round(amp, 4),
        "sizing_multipliers": trade.get("sizing_multipliers") or {},
        "addon_count": trade.get("addon_count", 0),
        "initial_risk_pct": _round(trade.get("initial_risk_pct"), 6),
        "normalization_delta": _round(normalization_delta, 2),
    }


def analyze_window(name: str, result: dict) -> dict:
    trades = result.get("trades") or []
    rows = [_trade_row(trade) for trade in trades]
    amplified = [row for row in rows if float(row["risk_amp"] or 1.0) > 1.0001]
    family_losses = [
        row
        for row in amplified
        if float(row["pnl"]) < 0 and row.get("exit_reason") == "stop"
    ]
    amplified_winners = [row for row in amplified if float(row["pnl"]) > 0]
    amplified_losers = [row for row in amplified if float(row["pnl"]) < 0]

    loss_abs = -sum(float(row["pnl"]) for row in family_losses)
    all_loss_abs = -sum(float(row["pnl"]) for row in rows if float(row["pnl"]) < 0)
    amplified_loss_abs = -sum(float(row["pnl"]) for row in amplified_losers)
    winner_pnl = sum(float(row["pnl"]) for row in amplified_winners)

    family_normalization_saved = -sum(
        float(row["normalization_delta"]) for row in family_losses
    )
    winner_normalization_collateral = sum(
        float(row["normalization_delta"]) for row in amplified_winners
    )
    amplified_loser_normalization_saved = -sum(
        float(row["normalization_delta"]) for row in amplified_losers
    )

    by_sector = defaultdict(lambda: {"loss_count": 0, "loss_abs": 0.0})
    by_strategy = defaultdict(lambda: {"loss_count": 0, "loss_abs": 0.0})
    for row in family_losses:
        sector = row["sector"]
        strategy = row["strategy"]
        by_sector[sector]["loss_count"] += 1
        by_sector[sector]["loss_abs"] += -float(row["pnl"])
        by_strategy[strategy]["loss_count"] += 1
        by_strategy[strategy]["loss_abs"] += -float(row["pnl"])

    return {
        "window": name,
        "period": result.get("period"),
        "baseline_metrics": {
            "expected_value_score": result.get("expected_value_score"),
            "sharpe_daily": result.get("sharpe_daily"),
            "max_drawdown_pct": result.get("max_drawdown_pct"),
            "total_pnl": result.get("total_pnl"),
            "win_rate": result.get("win_rate"),
            "trade_count": result.get("total_trades"),
            "survival_rate": result.get("survival_rate"),
        },
        "counts": {
            "trade_count": len(rows),
            "loss_count": sum(1 for row in rows if float(row["pnl"]) < 0),
            "win_count": sum(1 for row in rows if float(row["pnl"]) > 0),
            "risk_amplified_trade_count": len(amplified),
            "risk_amplified_winner_count": len(amplified_winners),
            "risk_amplified_loser_count": len(amplified_losers),
            "risk_amplified_stopout_loss_count": len(family_losses),
        },
        "loss_dollars": {
            "total_loss_abs": _round(all_loss_abs, 2),
            "risk_amplified_loss_abs": _round(amplified_loss_abs, 2),
            "risk_amplified_stopout_loss_abs": _round(loss_abs, 2),
            "risk_amplified_stopout_share_of_all_loss_abs": _round(
                loss_abs / all_loss_abs if all_loss_abs else 0.0, 4
            ),
            "risk_amplified_stopout_share_of_amplified_loss_abs": _round(
                loss_abs / amplified_loss_abs if amplified_loss_abs else 0.0, 4
            ),
        },
        "oracle_comparison": {
            "unrealizable_family_avoidance_oracle_saved": _round(loss_abs, 2),
            "risk_normalization_oracle_saved_on_family_losses": _round(
                family_normalization_saved, 2
            ),
            "risk_normalization_saved_on_all_amplified_losers": _round(
                amplified_loser_normalization_saved, 2
            ),
            "winner_collateral_if_all_amplified_winners_normalized": _round(
                winner_normalization_collateral, 2
            ),
            "net_family_normalization_after_winner_collateral": _round(
                family_normalization_saved - winner_normalization_collateral, 2
            ),
            "full_amplified_trade_veto_net_after_winners": _round(
                amplified_loss_abs - winner_pnl, 2
            ),
        },
        "summaries": {
            "family_losses": _summary(family_losses),
            "risk_amplified_winners": _summary(amplified_winners),
            "risk_amplified_losers": _summary(amplified_losers),
            "family_losses_by_sector": {
                key: {
                    "loss_count": value["loss_count"],
                    "loss_abs": _round(value["loss_abs"], 2),
                }
                for key, value in sorted(by_sector.items())
            },
            "family_losses_by_strategy": {
                key: {
                    "loss_count": value["loss_count"],
                    "loss_abs": _round(value["loss_abs"], 2),
                }
                for key, value in sorted(by_strategy.items())
            },
        },
        "family_loss_rows": family_losses,
        "risk_amplified_winner_collateral_rows": amplified_winners,
    }


def build_audit(source: Path) -> dict:
    result = json.loads(source.read_text(encoding="utf-8"))
    windows = {"primary": result.get("primary") or result}
    if isinstance(result.get("secondary"), dict):
        windows["secondary"] = result["secondary"]

    window_results = {name: analyze_window(name, data) for name, data in windows.items()}
    primary = window_results["primary"]
    secondary = window_results.get("secondary")
    total_family_loss = sum(
        item["loss_dollars"]["risk_amplified_stopout_loss_abs"]
        for item in window_results.values()
    )
    total_winner_collateral = sum(
        item["oracle_comparison"][
            "winner_collateral_if_all_amplified_winners_normalized"
        ]
        for item in window_results.values()
    )
    total_family_norm_saved = sum(
        item["oracle_comparison"]["risk_normalization_oracle_saved_on_family_losses"]
        for item in window_results.values()
    )

    return {
        "experiment_id": "exp-20260502-009",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "lane": "loss_attribution",
        "change_type": "failure_taxonomy",
        "single_causal_variable": "risk-amplified stopout bad-trade taxonomy",
        "strategy_behavior_changed": False,
        "source_result": str(source.relative_to(REPO_ROOT)),
        "history_guardrails": {
            "does_not_add_filter": True,
            "does_not_modify_production_strategy": True,
            "does_not_treat_loss_trades_as_rule": True,
            "checks_winner_collateral": True,
            "distinct_from_prior_price_path_taxonomies": (
                "uses realized risk amplification from sizing attribution, not "
                "MFE, overnight gap, wide stop, weak hold, same-day cluster, "
                "sector-relative breakdown, or extension follow-through."
            ),
        },
        "taxonomy_definition": {
            "name": "risk_amplified_stopout_loss",
            "criteria": {
                "pnl": "< 0",
                "exit_reason": "stop",
                "actual_risk_pct": "> base_risk_pct",
            },
            "oracle_method": (
                "Compare unrealizable family avoidance with a linear base-risk "
                "normalization estimate. Winner collateral is the PnL given up "
                "if the same normalization is applied to all risk-amplified winners."
            ),
        },
        "windows": window_results,
        "aggregate": {
            "window_count": len(window_results),
            "risk_amplified_stopout_loss_abs": _round(total_family_loss, 2),
            "risk_normalization_oracle_saved_on_family_losses": _round(
                total_family_norm_saved, 2
            ),
            "winner_collateral_if_all_amplified_winners_normalized": _round(
                total_winner_collateral, 2
            ),
            "net_family_normalization_after_winner_collateral": _round(
                total_family_norm_saved - total_winner_collateral, 2
            ),
        },
        "interpretation": {
            "decision": "observed_only",
            "primary_takeaway": (
                "Risk-amplified stopouts exist, but the comparable amplified "
                "winner collateral is far larger than the loss dollars saved by "
                "base-risk normalization. Do not convert this into a hard risk "
                "haircut without an orthogonal adverse-information discriminator."
            ),
            "primary_counts": primary["counts"],
            "primary_loss_dollars": primary["loss_dollars"],
            "primary_oracle_comparison": primary["oracle_comparison"],
            "secondary_check": secondary["counts"] if secondary else None,
        },
        "future_test_candidates": [
            {
                "candidate": "event_or_news_confirmed_risk_amplification_guard",
                "reason": (
                    "Only test a risk-down rule if archived event/news context "
                    "separates the amplified Energy/Financials stopouts from "
                    "the much larger amplified winner set."
                ),
                "must_quantify_before_rule": [
                    "candidate count",
                    "loss dollars saved",
                    "winner collateral",
                    "multi-window stability",
                    "production/backtest shared policy path",
                ],
            }
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=str(DEFAULT_SOURCE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    source = Path(args.source)
    output = Path(args.output)
    audit = build_audit(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "artifact": str(output.relative_to(REPO_ROOT)),
        "primary_counts": audit["interpretation"]["primary_counts"],
        "primary_loss_dollars": audit["interpretation"]["primary_loss_dollars"],
        "primary_oracle_comparison": audit["interpretation"]["primary_oracle_comparison"],
        "aggregate": audit["aggregate"],
    }, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
