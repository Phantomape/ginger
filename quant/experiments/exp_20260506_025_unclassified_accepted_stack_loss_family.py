"""exp-20260506-025: unclassified accepted-stack loss family audit.

Observed-only loss attribution. This script changes no production behavior. It
replays the accepted stack over three fixed OHLCV snapshot windows and classifies
losses not already explained by recent add-on, low-MFE, wide-stop, or state-map
audits into reproducible residual families with measured winner collateral.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from statistics import mean, median

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
QUANT_DIR = os.path.join(ROOT, "quant")
if QUANT_DIR not in sys.path:
    sys.path.insert(0, QUANT_DIR)

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402

EXPERIMENT_ID = "exp-20260506-025"
OUT_DIR = os.path.join(ROOT, "data", "experiments", EXPERIMENT_ID)
OUT_JSON = os.path.join(
    OUT_DIR,
    "exp_20260506_025_unclassified_accepted_stack_loss_family.json",
)

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": os.path.join(ROOT, "data", "ohlcv_snapshot_20251023_20260421.json"),
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": os.path.join(ROOT, "data", "ohlcv_snapshot_20250423_20251022.json"),
                "state_note": "rotation-heavy bull where strategy profits but lags indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": os.path.join(ROOT, "data", "ohlcv_snapshot_20241002_20250422.json"),
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)

KNOWN_FAMILIES = [
    "recent_addon_touched",
    "low_mfe_stopout",
    "wide_stop_distance",
    "state_map_non_risk_on_or_sector_breakdown",
]

RESIDUAL_FAMILIES = [
    "moderate_mfe_full_reversal_stopout",
    "early_followthrough_underperformance",
    "loss_cluster_same_entry_date",
    "gap_or_open_damage_after_entry",
    "event_strategy_residual_loss",
]


def _round(value, ndigits=6):
    return round(float(value), ndigits) if isinstance(value, (int, float)) else None


def _pct(num, den):
    if not isinstance(num, (int, float)) or not isinstance(den, (int, float)) or den == 0:
        return None
    return (float(num) / float(den)) - 1.0


def _load_snapshot(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["ohlcv"]


def _index_by_date(rows):
    return {row["Date"]: idx for idx, row in enumerate(rows)}


def _slice(rows, start, end):
    lo, hi = sorted((start, end))
    return rows[lo : hi + 1]


def _safe_mean(vals):
    vals = [v for v in vals if isinstance(v, (int, float))]
    return mean(vals) if vals else None


def _safe_median(vals):
    vals = [v for v in vals if isinstance(v, (int, float))]
    return median(vals) if vals else None


def _path_features(trade, rows, entry_idx, exit_idx):
    path = _slice(rows, entry_idx, exit_idx)
    entry = trade.get("entry_price")
    stop = trade.get("stop_price")
    risk_pct = trade.get("initial_risk_pct")
    if not isinstance(risk_pct, (int, float)) and isinstance(entry, (int, float)) and isinstance(stop, (int, float)):
        risk_pct = (entry - stop) / entry
    if not path or not isinstance(entry, (int, float)):
        return {"path_status": "missing"}

    highs = [row.get("High") for row in path if isinstance(row.get("High"), (int, float))]
    lows = [row.get("Low") for row in path if isinstance(row.get("Low"), (int, float))]
    closes = [row.get("Close") for row in path if isinstance(row.get("Close"), (int, float))]
    max_high = max(highs) if highs else None
    min_low = min(lows) if lows else None
    mfe_pct = _pct(max_high, entry)
    mae_pct = _pct(min_low, entry)
    mfe_r = mfe_pct / risk_pct if isinstance(mfe_pct, (int, float)) and risk_pct else None
    mae_r = mae_pct / risk_pct if isinstance(mae_pct, (int, float)) and risk_pct else None

    target_progress = None
    target_mult = trade.get("target_mult_used")
    if isinstance(max_high, (int, float)) and isinstance(stop, (int, float)) and isinstance(target_mult, (int, float)) and entry > stop:
        target = entry + target_mult * (entry - stop)
        if target > entry:
            target_progress = (max_high - entry) / (target - entry)

    overnight_gaps = []
    open_vs_entry = []
    for row in path[1:]:
        gap = _pct(row.get("Open"), path[path.index(row) - 1].get("Close"))
        if gap is not None:
            overnight_gaps.append(gap)
        oe = _pct(row.get("Open"), entry)
        if oe is not None:
            open_vs_entry.append(oe)

    close_below_entry_count = sum(1 for c in closes if isinstance(c, (int, float)) and c < entry)
    return {
        "path_status": "ok",
        "hold_bars": len(path) - 1,
        "mfe_pct": _round(mfe_pct),
        "mae_pct": _round(mae_pct),
        "mfe_r": _round(mfe_r),
        "mae_r": _round(mae_r),
        "max_high": _round(max_high, 4),
        "min_low": _round(min_low, 4),
        "target_progress": _round(target_progress),
        "worst_overnight_gap_pct": _round(min(overnight_gaps) if overnight_gaps else None),
        "worst_open_vs_entry_pct": _round(min(open_vs_entry) if open_vs_entry else None),
        "close_below_entry_share": _round(close_below_entry_count / len(closes) if closes else None),
    }


def _forward_features(rows, spy_rows, entry_idx, entry_date):
    spy_idx = _index_by_date(spy_rows).get(entry_date)
    if entry_idx is None or spy_idx is None:
        return {"status": "missing_entry"}
    if entry_idx + 2 >= len(rows) or spy_idx + 2 >= len(spy_rows):
        return {"status": "insufficient_forward"}
    entry_open = rows[entry_idx].get("Open")
    spy_open = spy_rows[spy_idx].get("Open")
    d1_close = rows[entry_idx + 1].get("Close")
    d2_close = rows[entry_idx + 2].get("Close")
    spy_d1_close = spy_rows[spy_idx + 1].get("Close")
    spy_d2_close = spy_rows[spy_idx + 2].get("Close")
    d1_ret = _pct(d1_close, entry_open)
    d2_ret = _pct(d2_close, entry_open)
    spy_d1 = _pct(spy_d1_close, spy_open)
    spy_d2 = _pct(spy_d2_close, spy_open)
    d1_excess = d1_ret - spy_d1 if d1_ret is not None and spy_d1 is not None else None
    d2_excess = d2_ret - spy_d2 if d2_ret is not None and spy_d2 is not None else None
    return {
        "status": "ok",
        "d1_return_from_entry_open": _round(d1_ret),
        "d2_return_from_entry_open": _round(d2_ret),
        "d1_excess_vs_spy": _round(d1_excess),
        "d2_excess_vs_spy": _round(d2_excess),
        "d1_close_below_entry_open": bool(isinstance(d1_ret, (int, float)) and d1_ret < 0),
        "d2_close_below_entry_open": bool(isinstance(d2_ret, (int, float)) and d2_ret < 0),
        "d1_underperformed_spy": bool(isinstance(d1_excess, (int, float)) and d1_excess < 0),
        "d2_underperformed_spy": bool(isinstance(d2_excess, (int, float)) and d2_excess < 0),
    }


def _sector_return(snapshot, universe, ticker_sector, sector, entry_date, exit_date):
    if not sector:
        return None
    vals = []
    for ticker in universe:
        if ticker_sector.get(ticker) != sector:
            continue
        rows = snapshot.get(ticker) or []
        idx = _index_by_date(rows)
        si, ei = idx.get(entry_date), idx.get(exit_date)
        if si is None or ei is None:
            continue
        ret = _pct(rows[ei].get("Close"), rows[si].get("Open"))
        if ret is not None:
            vals.append(ret)
    return mean(vals) if vals else None


def _summarize(rows):
    pnl_sum = sum(float(r.get("pnl") or 0.0) for r in rows)
    loss_abs = -sum(float(r.get("pnl") or 0.0) for r in rows if float(r.get("pnl") or 0.0) < 0)
    winner_pnl = sum(float(r.get("pnl") or 0.0) for r in rows if float(r.get("pnl") or 0.0) > 0)
    return {
        "count": len(rows),
        "pnl_sum": _round(pnl_sum, 2),
        "loss_pnl_abs": _round(loss_abs, 2),
        "winner_pnl": _round(winner_pnl, 2),
        "avg_pnl": _round(pnl_sum / len(rows), 2) if rows else None,
        "median_pnl": _round(_safe_median([r.get("pnl") for r in rows]), 2),
        "strategy_counts": dict(Counter(r.get("strategy") for r in rows)),
        "sector_counts": dict(Counter(r.get("sector") for r in rows)),
        "state_counts": dict(Counter(r.get("regime_exit_bucket") or "unknown" for r in rows)),
        "ticker_counts": dict(Counter(r.get("ticker") for r in rows)),
        "window_counts": dict(Counter(r.get("window") for r in rows)),
    }


def _family_stats(all_rows, loss_rows, family_names):
    stats = {}
    total_loss_abs = -sum(float(r.get("pnl") or 0.0) for r in loss_rows)
    for name in family_names:
        touched = [r for r in all_rows if name in r.get("matching_residual_families", [])]
        losses = [r for r in loss_rows if name in r.get("matching_residual_families", [])]
        winners = [r for r in touched if float(r.get("pnl") or 0.0) > 0]
        loss_abs = -sum(float(r.get("pnl") or 0.0) for r in losses)
        winner_pnl = sum(float(r.get("pnl") or 0.0) for r in winners)
        stats[name] = {
            "definition": FAMILY_DEFINITIONS[name],
            "loss_count": len(losses),
            "winner_collateral_count": len(winners),
            "all_trade_hit_count": len(touched),
            "loss_pnl_abs": _round(loss_abs, 2),
            "tail_loss_share_of_all_losses": _round(loss_abs / total_loss_abs if total_loss_abs else None),
            "winner_collateral_pnl": _round(winner_pnl, 2),
            "collateral_to_loss_abs": _round(winner_pnl / loss_abs if loss_abs else None),
            "naive_observed_net_if_avoided": _round(loss_abs - winner_pnl, 2) if loss_abs else None,
            "loss_summary": _summarize(losses),
            "winner_collateral_summary": _summarize(winners),
            "sample_losses": [
                {
                    "window": r.get("window"),
                    "ticker": r.get("ticker"),
                    "strategy": r.get("strategy"),
                    "sector": r.get("sector"),
                    "entry_date": r.get("entry_date"),
                    "exit_date": r.get("exit_date"),
                    "pnl": _round(r.get("pnl"), 2),
                    "mfe_pct": r.get("mfe_pct"),
                    "d2_excess_vs_spy": r.get("d2_excess_vs_spy"),
                    "known_family_flags": r.get("known_family_flags"),
                }
                for r in losses[:12]
            ],
        }
    return stats


FAMILY_DEFINITIONS = {
    "moderate_mfe_full_reversal_stopout": (
        "Loss stopout with at least 1pct MFE and target progress below 50pct, "
        "then reversal to stop; excludes low-MFE and add-on-touched known families."
    ),
    "early_followthrough_underperformance": (
        "Within two bars after entry, close is below entry open and underperforms SPY; "
        "tests a failed initial acceptance path rather than a broad threshold change."
    ),
    "loss_cluster_same_entry_date": (
        "Entry dates with at least two accepted-stack losses across the three-window audit, "
        "suggesting same-day tape/context fragility."
    ),
    "gap_or_open_damage_after_entry": (
        "Post-entry overnight/open damage of at least 1.25pct or 0.4R; observed damage path, not a rule."
    ),
    "event_strategy_residual_loss": (
        "Residual losing trades from earnings/event-style sleeve after excluding known families."
    ),
}


def _run_window(label, cfg, universe):
    engine = BacktestEngine(
        universe,
        start=cfg["start"],
        end=cfg["end"],
        config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
        ohlcv_snapshot_path=cfg["snapshot"],
    )
    result = engine.run()
    if "error" in result:
        raise RuntimeError(f"{label}: {result['error']}")

    snapshot = _load_snapshot(cfg["snapshot"])
    spy_rows = snapshot.get("SPY") or []
    ticker_sector = {t.get("ticker"): t.get("sector") for t in result.get("trades", [])}
    enriched = []
    for trade in result.get("trades", []):
        row = dict(trade)
        row["window"] = label
        row["window_state_note"] = cfg["state_note"]
        rows = snapshot.get(trade.get("ticker")) or []
        idx = _index_by_date(rows)
        entry_idx = idx.get(trade.get("entry_date"))
        exit_idx = idx.get(trade.get("exit_date"))
        if entry_idx is not None and exit_idx is not None:
            row.update(_path_features(trade, rows, entry_idx, exit_idx))
            row.update(_forward_features(rows, spy_rows, entry_idx, trade.get("entry_date")))
        else:
            row.update({"path_status": "missing_dates", "status": "missing_dates"})
        sector_ret = _sector_return(snapshot, universe, ticker_sector, trade.get("sector"), trade.get("entry_date"), trade.get("exit_date"))
        spy_idx = _index_by_date(spy_rows)
        spy_ret = None
        if trade.get("entry_date") in spy_idx and trade.get("exit_date") in spy_idx:
            spy_ret = _pct(spy_rows[spy_idx[trade.get("exit_date")]].get("Close"), spy_rows[spy_idx[trade.get("entry_date")]].get("Open"))
        stock_ret = _pct(trade.get("exit_raw_price") or trade.get("exit_price"), trade.get("entry_price"))
        row["sector_return_entry_to_exit"] = _round(sector_ret)
        row["spy_return_entry_to_exit"] = _round(spy_ret)
        row["stock_vs_sector_return"] = _round(stock_ret - sector_ret if stock_ret is not None and sector_ret is not None else None)
        row["sector_vs_spy_return"] = _round(sector_ret - spy_ret if sector_ret is not None and spy_ret is not None else None)
        row["is_loss"] = float(row.get("pnl") or 0.0) < 0
        enriched.append(row)
    return result, enriched


def _known_flags(row):
    risk = float(row.get("initial_risk_pct") or 0.0)
    mfe = row.get("mfe_pct")
    flags = {
        "recent_addon_touched": int(row.get("addon_count") or 0) > 0 or int(row.get("addon_shares") or 0) > 0,
        "low_mfe_stopout": row.get("exit_reason") == "stop" and isinstance(mfe, (int, float)) and mfe < 0.01,
        "wide_stop_distance": risk >= 0.05,
        "state_map_non_risk_on_or_sector_breakdown": (row.get("regime_exit_bucket") not in (None, "risk_on"))
        or ((row.get("sector_vs_spy_return") or 0.0) <= -0.02 and (row.get("stock_vs_sector_return") or 0.0) <= -0.02),
    }
    return flags


def _residual_families(row, clustered_entry_dates):
    risk = float(row.get("initial_risk_pct") or 0.0)
    worst_gap = row.get("worst_overnight_gap_pct")
    worst_open = row.get("worst_open_vs_entry_pct")
    worst_gap_r = worst_gap / risk if isinstance(worst_gap, (int, float)) and risk else None
    fam = []
    if (
        row.get("exit_reason") == "stop"
        and isinstance(row.get("mfe_pct"), (int, float))
        and row["mfe_pct"] >= 0.01
        and (row.get("target_progress") is None or row.get("target_progress") < 0.5)
    ):
        fam.append("moderate_mfe_full_reversal_stopout")
    if row.get("d2_close_below_entry_open") and row.get("d2_underperformed_spy"):
        fam.append("early_followthrough_underperformance")
    if row.get("entry_date") in clustered_entry_dates:
        fam.append("loss_cluster_same_entry_date")
    if (isinstance(worst_gap, (int, float)) and worst_gap <= -0.0125) or (isinstance(worst_open, (int, float)) and worst_open <= -0.0125) or (isinstance(worst_gap_r, (int, float)) and worst_gap_r <= -0.4):
        fam.append("gap_or_open_damage_after_entry")
    if row.get("strategy") == "earnings_event_long":
        fam.append("event_strategy_residual_loss")
    return fam


def main():
    universe = get_universe()
    all_rows = []
    windows = OrderedDict()
    for label, cfg in WINDOWS.items():
        result, rows = _run_window(label, cfg, universe)
        windows[label] = {
            "window": {"start": cfg["start"], "end": cfg["end"], "state_note": cfg["state_note"]},
            "metrics": {
                "expected_value_score": result.get("expected_value_score"),
                "sharpe_daily": result.get("sharpe_daily"),
                "max_drawdown_pct": result.get("max_drawdown_pct"),
                "total_pnl": result.get("total_pnl"),
                "win_rate": result.get("win_rate"),
                "trade_count": result.get("total_trades"),
                "survival_rate": result.get("survival_rate"),
            },
        }
        all_rows.extend(rows)

    losses = [r for r in all_rows if r["is_loss"]]
    losses_by_entry = defaultdict(list)
    for row in losses:
        losses_by_entry[row.get("entry_date")].append(row)
    clustered_entry_dates = {date for date, rows in losses_by_entry.items() if date and len(rows) >= 2}

    for row in all_rows:
        flags = _known_flags(row)
        row["known_family_flags"] = flags
        row["known_family_names"] = [name for name, hit in flags.items() if hit]
        row["covered_by_recent_known_audit"] = bool(row["known_family_names"])
        row["matching_residual_families"] = _residual_families(row, clustered_entry_dates)
        if row["covered_by_recent_known_audit"]:
            row["unclassified_after_known_audits"] = False
        else:
            row["unclassified_after_known_audits"] = row["is_loss"]

    losses = [r for r in all_rows if r["is_loss"]]
    known_covered_losses = [r for r in losses if r["covered_by_recent_known_audit"]]
    residual_losses = [r for r in losses if not r["covered_by_recent_known_audit"]]
    residual_tagged = [r for r in residual_losses if r["matching_residual_families"]]
    residual_untagged = [r for r in residual_losses if not r["matching_residual_families"]]

    total_loss_abs = -sum(float(r.get("pnl") or 0.0) for r in losses)
    residual_loss_abs = -sum(float(r.get("pnl") or 0.0) for r in residual_losses)

    family_stats = _family_stats(all_rows, residual_losses, RESIDUAL_FAMILIES)
    known_stats = {}
    for name in KNOWN_FAMILIES:
        hit_losses = [r for r in losses if r["known_family_flags"].get(name)]
        known_stats[name] = {
            "loss_count": len(hit_losses),
            "loss_pnl_abs": _round(-sum(float(r.get("pnl") or 0.0) for r in hit_losses), 2),
            "loss_summary": _summarize(hit_losses),
        }

    best_candidates = []
    for name, stats in family_stats.items():
        if stats["loss_count"] >= 3 and (stats["collateral_to_loss_abs"] is None or stats["collateral_to_loss_abs"] <= 0.75):
            best_candidates.append(
                {
                    "family": name,
                    "loss_count": stats["loss_count"],
                    "loss_pnl_abs": stats["loss_pnl_abs"],
                    "winner_collateral_count": stats["winner_collateral_count"],
                    "winner_collateral_pnl": stats["winner_collateral_pnl"],
                    "collateral_to_loss_abs": stats["collateral_to_loss_abs"],
                    "next_test_shape": (
                        "Default-off shadow replay of a candidate risk/exit qualifier; "
                        "must use only fields observable by entry plus first two bars, "
                        "and must compare avoided losers against matched winners across all three windows."
                    ),
                }
            )
    best_candidates.sort(key=lambda x: (-(x["loss_pnl_abs"] or 0), x["collateral_to_loss_abs"] or 999))

    compact_loss_rows = []
    for row in losses:
        compact_loss_rows.append(
            {
                "window": row.get("window"),
                "ticker": row.get("ticker"),
                "strategy": row.get("strategy"),
                "sector": row.get("sector"),
                "state": row.get("regime_exit_bucket") or "unknown",
                "entry_date": row.get("entry_date"),
                "exit_date": row.get("exit_date"),
                "exit_reason": row.get("exit_reason"),
                "pnl": _round(row.get("pnl"), 2),
                "pnl_pct_net": row.get("pnl_pct_net"),
                "initial_risk_pct": row.get("initial_risk_pct"),
                "mfe_pct": row.get("mfe_pct"),
                "mfe_r": row.get("mfe_r"),
                "target_progress": row.get("target_progress"),
                "d2_excess_vs_spy": row.get("d2_excess_vs_spy"),
                "worst_overnight_gap_pct": row.get("worst_overnight_gap_pct"),
                "known_family_names": row.get("known_family_names"),
                "matching_residual_families": row.get("matching_residual_families"),
            }
        )

    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "lane": "loss_attribution",
        "change_type": "failure_taxonomy",
        "single_causal_variable": "unclassified accepted-stack loss family",
        "strategy_behavior_changed": False,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "production_signal_path_changed": False,
            "production_orders_changed": False,
        },
        "alpha_hypothesis": {
            "category": "loss_attribution_to_future_exit_or_entry_risk_experiment",
            "text": "Accepted-stack residual losses may be concentrated in early follow-through failure or moderate-MFE full-reversal families after known add-on, low-MFE, wide-stop, and state-map families are removed.",
            "why_not_production": "Observed-only taxonomy; no filter or strategy logic changed. Candidate must pass a future default-off replay with entry/early-path observable fields and winner-collateral accounting.",
        },
        "historical_guardrail_check": {
            "recent_addon_audits_not_repeated": True,
            "low_mfe_audit_not_repeated": True,
            "wide_stop_audit_not_repeated": True,
            "state_map_audit_not_repeated": True,
            "mechanism_insight_check": "This run does not tune thresholds, expand candidate pools, add filters, retest add-on enablement, retest generic low-MFE exits, retest wide-stop distance, or modify production code. It only quantifies the residual accepted-stack loss family.",
        },
        "windows": windows,
        "family_definitions": FAMILY_DEFINITIONS,
        "aggregate": {
            "trade_count": len(all_rows),
            "loss_count": len(losses),
            "win_count": len(all_rows) - len(losses),
            "total_loss_pnl_abs": _round(total_loss_abs, 2),
            "known_covered_loss_count": len(known_covered_losses),
            "known_covered_loss_pnl_abs": _round(-sum(float(r.get("pnl") or 0.0) for r in known_covered_losses), 2),
            "residual_unclassified_loss_count_after_known_audits": len(residual_losses),
            "residual_unclassified_loss_pnl_abs": _round(residual_loss_abs, 2),
            "residual_tail_share_of_all_losses": _round(residual_loss_abs / total_loss_abs if total_loss_abs else None),
            "residual_tagged_by_new_taxonomy_count": len(residual_tagged),
            "residual_still_untagged_count": len(residual_untagged),
            "clustered_loss_entry_dates": sorted(clustered_entry_dates),
            "loss_summary": _summarize(losses),
            "residual_loss_summary": _summarize(residual_losses),
        },
        "known_recent_family_stats": known_stats,
        "residual_family_stats": family_stats,
        "loss_rows": compact_loss_rows,
        "candidate_next_experiments": best_candidates[:3],
        "decision": "observed_only",
        "interpretation": [
            "The audit is descriptive and cannot justify a direct filter because several residual families use post-entry path information.",
            "A valid next experiment should convert the strongest residual family into a default-off replay using only entry-observable or explicitly early-lifecycle fields.",
            "Good-trade collateral is explicitly measured by applying the same family tags to all accepted-stack winners. Families with high collateral_to_loss_abs should not be promoted.",
        ],
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(OUT_JSON)


if __name__ == "__main__":
    main()
