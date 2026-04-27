"""Observed-only audit for post-entry overnight gap-down damage.

This experiment does not change strategy behavior. It replays the accepted
stack on fixed OHLCV snapshots and classifies trades by their worst overnight
gap after entry. The goal is to quantify whether gap-down damage is a repeated
loss family, and how much winner collateral a future mitigation would risk.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from statistics import mean, median


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QUANT_DIR = os.path.join(REPO_ROOT, "quant")
if QUANT_DIR not in sys.path:
    sys.path.insert(0, QUANT_DIR)

from backtester import BacktestEngine  # noqa: E402
from convergence import compute_expected_value_score  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260426-048"
OUT_JSON = os.path.join(
    REPO_ROOT,
    "docs",
    "experiments",
    "artifacts",
    "exp_20260426_048_gap_down_damage_audit.json",
)

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
        "regime": "slow-melt bull / accepted-stack dominant tape",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
        "regime": "rotation-heavy bull with weaker follow-through",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "regime": "mixed-to-weak older tape",
    }),
])

CONFIG = {"REGIME_AWARE_EXIT": True}
GAP_DOWN_PCT = -0.02
GAP_R_MULT = -0.50


def _load_snapshot(path: str) -> dict[str, list[dict]]:
    with open(path, encoding="utf-8") as f:
        return json.load(f).get("ohlcv", {})


def _run_window(universe: list[str], cfg: dict) -> dict:
    engine = BacktestEngine(
        universe=universe,
        start=cfg["start"],
        end=cfg["end"],
        config=CONFIG,
        replay_llm=False,
        replay_news=False,
        data_dir=os.path.join(REPO_ROOT, "data"),
        ohlcv_snapshot_path=os.path.join(REPO_ROOT, cfg["snapshot"]),
    )
    result = engine.run()
    result["expected_value_score"] = compute_expected_value_score(result)
    return result


def _trade_rows(snapshot: dict[str, list[dict]], trade: dict) -> list[dict]:
    rows = snapshot.get(trade.get("ticker"), [])
    entry = trade.get("entry_date")
    exit_ = trade.get("exit_date")
    return [
        row for row in rows
        if entry <= row.get("Date", "") <= exit_
    ]


def _overnight_gaps(rows: list[dict], entry_date: str | None) -> list[dict]:
    gaps = []
    previous = None
    for row in rows:
        date = row.get("Date")
        if previous and date and date > (entry_date or ""):
            prev_close = previous.get("Close")
            open_price = row.get("Open")
            if isinstance(prev_close, (int, float)) and prev_close > 0 and isinstance(open_price, (int, float)):
                gaps.append({
                    "date": date,
                    "prev_close": prev_close,
                    "open": open_price,
                    "gap_pct": (open_price / prev_close) - 1.0,
                })
        previous = row
    return gaps


def _diagnostics(trade: dict, snapshot: dict[str, list[dict]]) -> dict:
    rows = _trade_rows(snapshot, trade)
    gaps = _overnight_gaps(rows, trade.get("entry_date"))
    entry = trade.get("entry_price")
    stop = trade.get("stop_price")
    risk_pct = None
    if isinstance(entry, (int, float)) and entry > 0 and isinstance(stop, (int, float)):
        risk_pct = (entry - stop) / entry

    worst_gap = min(gaps, key=lambda item: item["gap_pct"], default=None)
    worst_gap_pct = worst_gap["gap_pct"] if worst_gap else None
    worst_gap_r = None
    if isinstance(worst_gap_pct, (int, float)) and isinstance(risk_pct, (int, float)) and risk_pct > 0:
        worst_gap_r = worst_gap_pct / risk_pct

    has_gap_damage = (
        isinstance(worst_gap_pct, (int, float))
        and (
            worst_gap_pct <= GAP_DOWN_PCT
            or (isinstance(worst_gap_r, (int, float)) and worst_gap_r <= GAP_R_MULT)
        )
    )
    is_bad = (trade.get("pnl") or 0) <= 0
    if is_bad and has_gap_damage:
        family = "bad_gap_down_damage"
    elif is_bad:
        family = "bad_without_gap_damage"
    elif has_gap_damage:
        family = "winner_collateral_gap_exposed"
    else:
        family = "winner_no_gap_damage"

    return {
        "ticker": trade.get("ticker"),
        "strategy": trade.get("strategy"),
        "sector": trade.get("sector"),
        "entry_date": trade.get("entry_date"),
        "exit_date": trade.get("exit_date"),
        "exit_reason": trade.get("exit_reason"),
        "pnl": trade.get("pnl"),
        "pnl_pct_net": trade.get("pnl_pct_net"),
        "entry_price": entry,
        "stop_price": stop,
        "initial_risk_pct": trade.get("initial_risk_pct"),
        "risk_pct_from_stop": round(risk_pct, 6) if isinstance(risk_pct, (int, float)) else None,
        "worst_gap_date": worst_gap.get("date") if worst_gap else None,
        "worst_gap_pct": round(worst_gap_pct, 6) if isinstance(worst_gap_pct, (int, float)) else None,
        "worst_gap_r": round(worst_gap_r, 6) if isinstance(worst_gap_r, (int, float)) else None,
        "gap_count_lte_minus_2pct": sum(1 for gap in gaps if gap["gap_pct"] <= GAP_DOWN_PCT),
        "gap_count_lte_minus_half_r": sum(
            1
            for gap in gaps
            if isinstance(risk_pct, (int, float))
            and risk_pct > 0
            and gap["gap_pct"] / risk_pct <= GAP_R_MULT
        ),
        "hold_days_observed": len(rows),
        "family": family,
    }


def _summary(rows: list[dict]) -> dict:
    pnls = [row["pnl"] for row in rows if isinstance(row.get("pnl"), (int, float))]
    return {
        "count": len(rows),
        "pnl_sum": round(sum(pnls), 2) if pnls else 0.0,
        "avg_pnl": round(mean(pnls), 2) if pnls else None,
        "median_pnl": round(median(pnls), 2) if pnls else None,
        "winner_count": sum(1 for pnl in pnls if pnl > 0),
        "loser_count": sum(1 for pnl in pnls if pnl <= 0),
    }


def _count(rows: list[dict], key: str) -> dict:
    return dict(sorted(Counter(row.get(key) or "unknown" for row in rows).items()))


def _window_audit(label: str, cfg: dict, universe: list[str]) -> dict:
    result = _run_window(universe, cfg)
    snapshot = _load_snapshot(os.path.join(REPO_ROOT, cfg["snapshot"]))
    rows = [_diagnostics(trade, snapshot) for trade in result.get("trades", [])]

    by_family = defaultdict(list)
    for row in rows:
        by_family[row["family"]].append(row)

    bad_gap = by_family["bad_gap_down_damage"]
    collateral = by_family["winner_collateral_gap_exposed"]

    return {
        "date_range": {"start": cfg["start"], "end": cfg["end"]},
        "snapshot": cfg["snapshot"],
        "market_regime_summary": cfg["regime"],
        "metrics": {
            "expected_value_score": result.get("expected_value_score"),
            "sharpe": result.get("sharpe"),
            "sharpe_daily": result.get("sharpe_daily"),
            "total_pnl": result.get("total_pnl"),
            "total_return_pct": result.get("benchmarks", {}).get("strategy_total_return_pct"),
            "max_drawdown_pct": result.get("max_drawdown_pct"),
            "trade_count": result.get("total_trades"),
            "win_rate": result.get("win_rate"),
        },
        "thresholds": {
            "gap_down_pct": GAP_DOWN_PCT,
            "gap_r_mult": GAP_R_MULT,
        },
        "family_counts": _count(rows, "family"),
        "summary_by_family": {
            family: _summary(items)
            for family, items in sorted(by_family.items())
        },
        "bad_gap_strategy_counts": _count(bad_gap, "strategy"),
        "bad_gap_sector_counts": _count(bad_gap, "sector"),
        "collateral_strategy_counts": _count(collateral, "strategy"),
        "collateral_sector_counts": _count(collateral, "sector"),
        "bad_gap_rows": sorted(bad_gap, key=lambda row: row.get("pnl") or 0),
        "winner_collateral_rows": sorted(collateral, key=lambda row: row.get("pnl") or 0, reverse=True),
    }


def main() -> int:
    universe = get_universe()
    windows = OrderedDict(
        (label, _window_audit(label, cfg, universe))
        for label, cfg in WINDOWS.items()
    )

    all_bad = [row for window in windows.values() for row in window["bad_gap_rows"]]
    all_collateral = [
        row for window in windows.values() for row in window["winner_collateral_rows"]
    ]
    total_trades = sum(window["metrics"]["trade_count"] or 0 for window in windows.values())
    bad_pnl = sum(row.get("pnl") or 0.0 for row in all_bad)
    collateral_pnl = sum(row.get("pnl") or 0.0 for row in all_collateral)

    aggregate = {
        "total_trades": total_trades,
        "bad_gap_down_damage_count": len(all_bad),
        "bad_gap_down_damage_frequency": round(len(all_bad) / total_trades, 4) if total_trades else None,
        "bad_gap_down_damage_pnl_sum": round(bad_pnl, 2),
        "winner_collateral_gap_exposed_count": len(all_collateral),
        "winner_collateral_gap_exposed_pnl_sum": round(collateral_pnl, 2),
        "bad_gap_strategy_counts": _count(all_bad, "strategy"),
        "bad_gap_sector_counts": _count(all_bad, "sector"),
        "collateral_strategy_counts": _count(all_collateral, "strategy"),
        "collateral_sector_counts": _count(all_collateral, "sector"),
        "collateral_to_bad_count_ratio": (
            round(len(all_collateral) / len(all_bad), 4) if all_bad else None
        ),
        "collateral_to_bad_pnl_abs_ratio": (
            round(collateral_pnl / abs(bad_pnl), 4) if bad_pnl else None
        ),
    }

    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "loss_attribution",
        "change_type": "failure_taxonomy",
        "single_causal_variable": (
            "post-entry overnight gap-down damage taxonomy for accepted-stack trades"
        ),
        "hypothesis": (
            "Accepted-stack losses may contain a reproducible post-entry "
            "overnight gap-down damage family distinct from prior instant-failure, "
            "rollover, breakout false-positive, add-on adverse, and near-target "
            "giveback audits."
        ),
        "parameters": {
            "gap_down_pct": GAP_DOWN_PCT,
            "gap_r_mult": GAP_R_MULT,
            "config": CONFIG,
        },
        "windows": windows,
        "aggregate": aggregate,
        "interpretation": {
            "decision": "observed_only",
            "finding": (
                "Post-entry gap-down damage is measurable, but a future alpha or "
                "risk experiment must compare bad-trade frequency against winner "
                "collateral before testing any mitigation."
            ),
            "next_alpha_implication": (
                "If the bad family is concentrated and collateral is low, the next "
                "test should be a shadow-mode gap-risk lifecycle mitigation; if "
                "collateral is high, pivot to event-conditioned gap diagnosis "
                "rather than a broad gap rule."
            ),
        },
    }

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2)
        f.write("\n")

    print(json.dumps(aggregate, indent=2))
    print(f"wrote: {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
