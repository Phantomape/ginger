"""Observed-only bad-trade failure taxonomy for exp-20260508-027.

This script does not alter strategy behavior. It reads accepted-stack backtest
outputs plus OHLCV snapshots, labels completed trades ex post, and writes a
machine-readable taxonomy artifact for future hypothesis design.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260508-027"
DEFAULT_RESULTS = [
    Path("data/backtest_results_20260507.json"),
    Path("data/backtest_results_20260508.json"),
]
DEFAULT_SNAPSHOTS = [
    Path("data/ohlcv_snapshot_20251023_20260421.json"),
    Path("data/ohlcv_snapshot_20250423_20251022.json"),
    Path("data/ohlcv_snapshot_20241002_20250422.json"),
]
DEFAULT_ARTIFACT = Path(
    "data/experiments/exp-20260508-027/"
    "exp_20260508_027_bad_trade_failure_taxonomy.json"
)


@dataclass(frozen=True)
class PricePath:
    rows: list[dict[str, Any]]

    @property
    def empty(self) -> bool:
        return not self.rows

    def max_high(self) -> float | None:
        highs = [float(row["High"]) for row in self.rows if row.get("High") is not None]
        return max(highs) if highs else None

    def min_low(self) -> float | None:
        lows = [float(row["Low"]) for row in self.rows if row.get("Low") is not None]
        return min(lows) if lows else None

    def worst_overnight_gap_pct(self) -> float | None:
        worst: float | None = None
        prev_close: float | None = None
        for row in self.rows:
            open_price = row.get("Open")
            close_price = row.get("Close")
            if prev_close and open_price is not None:
                gap = float(open_price) / prev_close - 1.0
                worst = gap if worst is None else min(worst, gap)
            if close_price:
                prev_close = float(close_price)
        return worst

    def early_window(self, days: int = 3) -> "PricePath":
        return PricePath(self.rows[:days])


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def norm_period(period: str | None) -> str:
    if not period:
        return "unknown"
    return period.replace("→", "->").replace("Ўъ", "->")


def collect_windows(result_files: list[Path]) -> list[dict[str, Any]]:
    windows: dict[str, dict[str, Any]] = {}
    for result_file in result_files:
        data = load_json(result_file)
        candidates = [data]
        for key in ("primary", "secondary"):
            if isinstance(data.get(key), dict):
                candidates.append(data[key])
        for candidate in candidates:
            trades = candidate.get("trades")
            if not isinstance(trades, list) or not trades:
                continue
            period = norm_period(candidate.get("period"))
            if period in windows:
                continue
            windows[period] = {
                "period": period,
                "source_file": str(result_file),
                "metrics": {
                    "expected_value_score": candidate.get("expected_value_score"),
                    "sharpe": candidate.get("sharpe"),
                    "sharpe_daily": candidate.get("sharpe_daily"),
                    "max_drawdown_pct": candidate.get("max_drawdown_pct"),
                    "total_pnl": candidate.get("total_pnl"),
                    "win_rate": candidate.get("win_rate"),
                    "trade_count": candidate.get("total_trades"),
                    "survival_rate": candidate.get("survival_rate"),
                    "tail_loss_share": candidate.get("tail_loss_share"),
                },
                "trades": trades,
            }
    return list(windows.values())


def load_ohlcv(snapshots: list[Path]) -> dict[str, dict[str, dict[str, Any]]]:
    by_ticker: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for snapshot in snapshots:
        data = load_json(snapshot)
        ohlcv = data.get("ohlcv", data)
        for ticker, rows in ohlcv.items():
            if ticker == "metadata" or not isinstance(rows, list):
                continue
            for row in rows:
                date = row.get("Date")
                if date:
                    by_ticker[ticker][date] = row
    return by_ticker


def path_for_trade(trade: dict[str, Any], ohlcv: dict[str, dict[str, dict[str, Any]]]) -> PricePath:
    ticker = trade["ticker"]
    entry_date = trade["entry_date"]
    exit_date = trade["exit_date"]
    rows = [
        row
        for date, row in sorted(ohlcv.get(ticker, {}).items())
        if entry_date <= date <= exit_date
    ]
    return PricePath(rows)


def trade_features(trade: dict[str, Any], path: PricePath) -> dict[str, Any]:
    entry = float(trade["entry_price"])
    pnl = float(trade.get("pnl", 0.0))
    max_high = path.max_high()
    min_low = path.min_low()
    early = path.early_window(3)
    early_min_low = early.min_low()
    mfe_pct = (max_high / entry - 1.0) if max_high else None
    mae_pct = (min_low / entry - 1.0) if min_low else None
    early_mae_pct = (early_min_low / entry - 1.0) if early_min_low else None
    pnl_pct = trade.get("pnl_pct_net")
    target = float(trade.get("target_mult_used") or 0.0) * float(trade.get("initial_risk_pct") or 0.0)
    target_progress = (mfe_pct / target) if target and mfe_pct is not None else None
    giveback_pct = (mfe_pct - float(pnl_pct)) if mfe_pct is not None and pnl_pct is not None else None
    try:
        hold_days = (
            datetime.fromisoformat(trade["exit_date"])
            - datetime.fromisoformat(trade["entry_date"])
        ).days + 1
    except ValueError:
        hold_days = None
    return {
        "pnl": pnl,
        "is_loss": pnl < 0,
        "mfe_pct": mfe_pct,
        "mae_pct": mae_pct,
        "early_mae_pct": early_mae_pct,
        "worst_overnight_gap_pct": path.worst_overnight_gap_pct(),
        "target_progress": target_progress,
        "giveback_pct": giveback_pct,
        "hold_days": hold_days,
        "path_rows": len(path.rows),
    }


def classify(trade: dict[str, Any], features: dict[str, Any]) -> list[dict[str, str]]:
    labels: list[dict[str, str]] = []
    strategy = trade.get("strategy")
    exit_reason = trade.get("exit_reason")
    mfe = features.get("mfe_pct")
    early_mae = features.get("early_mae_pct")
    gap = features.get("worst_overnight_gap_pct")
    target_progress = features.get("target_progress")
    giveback = features.get("giveback_pct")
    hold_days = features.get("hold_days") or 0

    if strategy == "breakout_long" and mfe is not None and mfe < 0.015:
        labels.append(
            {
                "family": "false_positive",
                "cluster": "breakout_no_follow_through",
            }
        )
    if strategy == "trend_long" and mfe is not None and mfe < 0.01:
        labels.append(
            {
                "family": "false_positive",
                "cluster": "trend_low_mfe_false_start",
            }
        )
    if early_mae is not None and early_mae <= -0.03 and mfe is not None and mfe < 0.02:
        labels.append(
            {
                "family": "hold_quality",
                "cluster": "early_adverse_no_reclaim",
            }
        )
    if gap is not None and gap <= -0.03:
        labels.append(
            {
                "family": "hold_quality",
                "cluster": "overnight_gap_damage",
            }
        )
    if (
        target_progress is not None
        and target_progress >= 0.70
        and giveback is not None
        and giveback >= 0.04
    ):
        labels.append(
            {
                "family": "exit_failure",
                "cluster": "near_target_giveback",
            }
        )
    if mfe is not None and mfe >= 0.03 and hold_days >= 10 and exit_reason == "stop":
        labels.append(
            {
                "family": "exit_failure",
                "cluster": "late_winner_to_stop",
            }
        )
    if not labels:
        labels.append({"family": "unclassified", "cluster": "no_refreshed_taxonomy_match"})
    return labels


def summarize_labeled(trade_rows: list[dict[str, Any]]) -> dict[str, Any]:
    total_loss_abs = sum(abs(row["pnl"]) for row in trade_rows if row["pnl"] < 0)
    total_winner_pnl = sum(row["pnl"] for row in trade_rows if row["pnl"] > 0)
    family_counts: Counter[str] = Counter()
    cluster_counts: Counter[str] = Counter()
    family_loss_abs: Counter[str] = Counter()
    cluster_loss_abs: Counter[str] = Counter()
    family_collateral_count: Counter[str] = Counter()
    family_collateral_pnl: Counter[str] = Counter()
    cluster_collateral_count: Counter[str] = Counter()
    cluster_collateral_pnl: Counter[str] = Counter()
    strategy_counts: dict[str, Counter[str]] = defaultdict(Counter)
    exit_reason_counts: dict[str, Counter[str]] = defaultdict(Counter)

    for row in trade_rows:
        seen_families = {label["family"] for label in row["labels"]}
        seen_clusters = {label["cluster"] for label in row["labels"]}
        if row["pnl"] < 0:
            for family in seen_families:
                family_counts[family] += 1
                family_loss_abs[family] += abs(row["pnl"])
            for cluster in seen_clusters:
                cluster_counts[cluster] += 1
                cluster_loss_abs[cluster] += abs(row["pnl"])
                strategy_counts[cluster][row["strategy"]] += 1
                exit_reason_counts[cluster][row["exit_reason"]] += 1
        elif row["pnl"] > 0:
            for family in seen_families:
                if family != "unclassified":
                    family_collateral_count[family] += 1
                    family_collateral_pnl[family] += row["pnl"]
            for cluster in seen_clusters:
                if cluster != "no_refreshed_taxonomy_match":
                    cluster_collateral_count[cluster] += 1
                    cluster_collateral_pnl[cluster] += row["pnl"]

    def loss_summary(counts: Counter[str], losses: Counter[str]) -> dict[str, Any]:
        out = {}
        for key, count in counts.most_common():
            loss_abs = round(losses[key], 2)
            out[key] = {
                "loss_count": count,
                "loss_abs": loss_abs,
                "tail_loss_share": round(loss_abs / total_loss_abs, 4) if total_loss_abs else None,
            }
        return out

    collateral_by_cluster = {}
    for cluster in sorted(set(cluster_counts) | set(cluster_collateral_count)):
        collateral_pnl = round(cluster_collateral_pnl[cluster], 2)
        loss_abs = round(cluster_loss_abs[cluster], 2)
        collateral_by_cluster[cluster] = {
            "winner_collateral_count": cluster_collateral_count[cluster],
            "winner_collateral_pnl": collateral_pnl,
            "bad_loss_abs": loss_abs,
            "collateral_to_bad_loss_abs_ratio": (
                round(collateral_pnl / loss_abs, 4) if loss_abs else None
            ),
        }

    return {
        "trade_count": len(trade_rows),
        "loss_count": sum(1 for row in trade_rows if row["pnl"] < 0),
        "win_count": sum(1 for row in trade_rows if row["pnl"] > 0),
        "total_loss_abs": round(total_loss_abs, 2),
        "total_winner_pnl": round(total_winner_pnl, 2),
        "families": loss_summary(family_counts, family_loss_abs),
        "clusters": loss_summary(cluster_counts, cluster_loss_abs),
        "good_trade_collateral_risk": {
            "by_family": {
                family: {
                    "winner_collateral_count": family_collateral_count[family],
                    "winner_collateral_pnl": round(family_collateral_pnl[family], 2),
                }
                for family in sorted(set(family_counts) | set(family_collateral_count))
            },
            "by_cluster": collateral_by_cluster,
            "note": (
                "Collateral estimates apply the same ex-post path label to winners. "
                "They are not implementable filters without an ex-ante trigger."
            ),
        },
        "cluster_strategy_counts": {k: dict(v) for k, v in sorted(strategy_counts.items())},
        "cluster_exit_reason_counts": {k: dict(v) for k, v in sorted(exit_reason_counts.items())},
    }


def build_artifact(result_files: list[Path], snapshots: list[Path]) -> dict[str, Any]:
    windows = collect_windows(result_files)
    ohlcv = load_ohlcv(snapshots)
    all_rows: list[dict[str, Any]] = []
    window_outputs = []
    for window in windows:
        rows = []
        for trade in window["trades"]:
            path = path_for_trade(trade, ohlcv)
            features = trade_features(trade, path)
            labels = classify(trade, features)
            row = {
                "period": window["period"],
                "trade_key": trade.get("trade_key"),
                "ticker": trade.get("ticker"),
                "strategy": trade.get("strategy"),
                "sector": trade.get("sector"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "exit_reason": trade.get("exit_reason"),
                "pnl": round(float(trade.get("pnl", 0.0)), 2),
                "pnl_pct_net": trade.get("pnl_pct_net"),
                "features": {
                    key: (round(value, 6) if isinstance(value, float) else value)
                    for key, value in features.items()
                    if key != "pnl"
                },
                "labels": labels,
            }
            rows.append(row)
            all_rows.append(row)
        window_outputs.append(
            {
                "period": window["period"],
                "source_file": window["source_file"],
                "metrics": window["metrics"],
                "taxonomy_summary": summarize_labeled(rows),
                "labeled_trades": rows,
            }
        )
    return {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "classification": "measurement_repair_supporting_alpha_search",
        "single_causal_variable": "refreshed accepted-stack bad trade failure taxonomy",
        "strategy_logic_changed": False,
        "inputs": {
            "result_files": [str(path) for path in result_files],
            "ohlcv_snapshots": [str(path) for path in snapshots],
        },
        "taxonomy_definition": {
            "false_positive": [
                "breakout_no_follow_through",
                "trend_low_mfe_false_start",
            ],
            "hold_quality": [
                "early_adverse_no_reclaim",
                "overnight_gap_damage",
            ],
            "exit_failure": [
                "near_target_giveback",
                "late_winner_to_stop",
            ],
            "unclassified": ["no_refreshed_taxonomy_match"],
        },
        "aggregate_summary": summarize_labeled(all_rows),
        "windows": window_outputs,
        "future_candidate_experiments": [
            {
                "candidate": "event_confirmed_early_adverse_hold_quality_replay",
                "reason": "Early-adverse labels need an orthogonal adverse information source before any lifecycle exit can avoid winner collateral.",
            },
            {
                "candidate": "near_target_giveback_profit_lock_oracle_screen",
                "reason": "Exit-failure labels should first be screened as default-off oracle replays with explicit winner truncation accounting.",
            },
            {
                "candidate": "breakout_no_followthrough_context_audit",
                "reason": "Breakout false positives need pre-entry context decomposition rather than a broad breakout filter.",
            },
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", action="append", type=Path, default=[])
    parser.add_argument("--snapshot", action="append", type=Path, default=[])
    parser.add_argument("--output", type=Path, default=DEFAULT_ARTIFACT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result_files = args.result or DEFAULT_RESULTS
    snapshots = args.snapshot or DEFAULT_SNAPSHOTS
    artifact = build_artifact(result_files, snapshots)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"artifact": str(args.output), "aggregate_summary": artifact["aggregate_summary"]}, indent=2))


if __name__ == "__main__":
    main()
