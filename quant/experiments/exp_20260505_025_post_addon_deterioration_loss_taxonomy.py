from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


EXPERIMENT_ID = "exp-20260505-025"
SOURCE_TRADES = Path("data/experiments/current_accepted_trades_20260502_alpha_search.json")
OUTPUT = Path(
    "data/experiments/exp-20260505-025/"
    "exp_20260505_025_post_addon_deterioration_loss_taxonomy.json"
)

WINDOW_SNAPSHOTS = {
    "late_strong": Path("data/ohlcv_snapshot_20251023_20260421.json"),
    "mid_weak": Path("data/ohlcv_snapshot_20250423_20251022.json"),
    "old_thin": Path("data/ohlcv_snapshot_20241002_20250422.json"),
}

CHECKPOINT_DAYS = 2


def load_json(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def round_float(value, digits=4):
    if value is None:
        return None
    return round(float(value), digits)


def pct(numerator, denominator):
    if denominator in (0, None):
        return None
    return numerator / denominator


def summarize(rows):
    pnl = sum(row["pnl"] for row in rows)
    losers = [row for row in rows if row["pnl"] < 0]
    winners = [row for row in rows if row["pnl"] > 0]
    loss_dollars = sum(row["pnl"] for row in losers)
    winner_pnl = sum(row["pnl"] for row in winners)
    return {
        "trade_count": len(rows),
        "winner_count": len(winners),
        "loser_count": len(losers),
        "net_pnl": round_float(pnl, 2),
        "loss_dollars": round_float(loss_dollars, 2),
        "winner_collateral_pnl": round_float(winner_pnl, 2),
        "avg_pnl": round_float(pnl / len(rows), 2) if rows else None,
        "win_rate": round_float(pct(len(winners), len(rows)), 4),
        "avg_winner_pnl": round_float(winner_pnl / len(winners), 2) if winners else None,
        "avg_loser_pnl": round_float(loss_dollars / len(losers), 2) if losers else None,
    }


def by_counter(rows, field):
    return dict(Counter(str(row.get(field, "Unknown")) for row in rows))


def rows_by_date(ohlcv):
    return {row["Date"]: row for row in ohlcv}


def build_path_features(trade, ticker_rows):
    dates = [row["Date"] for row in ticker_rows]
    entry_date = trade["entry_date"]
    exit_date = trade["exit_date"]
    if entry_date not in dates:
        return {}
    entry_idx = dates.index(entry_date)
    addon_idx = entry_idx + CHECKPOINT_DAYS + 1
    if addon_idx >= len(ticker_rows):
        return {}

    addon_row = ticker_rows[addon_idx]
    addon_date = addon_row["Date"]
    if addon_date > exit_date:
        return {}

    addon_price = float(addon_row["Open"])
    path = [
        row for row in ticker_rows[addon_idx:]
        if addon_date <= row["Date"] <= exit_date
    ]
    if not path:
        return {}

    lows = [float(row["Low"]) for row in path]
    highs = [float(row["High"]) for row in path]
    closes = [float(row["Close"]) for row in path]
    exit_close = closes[-1]

    def close_return_after(days):
        idx = min(days, len(path) - 1)
        return closes[idx] / addon_price - 1.0

    return {
        "estimated_addon_date": addon_date,
        "estimated_addon_open": round_float(addon_price, 4),
        "post_addon_sessions": len(path),
        "post_addon_return_to_exit_close": round_float(exit_close / addon_price - 1.0, 6),
        "post_addon_min_low_return": round_float(min(lows) / addon_price - 1.0, 6),
        "post_addon_max_high_return": round_float(max(highs) / addon_price - 1.0, 6),
        "post_addon_close_return_day_3": round_float(close_return_after(3), 6),
        "post_addon_close_return_day_5": round_float(close_return_after(5), 6),
        "post_addon_close_return_day_10": round_float(close_return_after(10), 6),
    }


def annotate_trade(window, trade, ticker_rows):
    row = {
        "window": window,
        "trade_key": trade.get("trade_key"),
        "ticker": trade.get("ticker"),
        "strategy": trade.get("strategy"),
        "sector": trade.get("sector", "Unknown"),
        "entry_date": trade.get("entry_date"),
        "exit_date": trade.get("exit_date"),
        "exit_reason": trade.get("exit_reason"),
        "pnl": round_float(trade.get("pnl", 0.0), 2),
        "pnl_pct_net": round_float(trade.get("pnl_pct_net"), 6),
        "initial_risk_pct": round_float(trade.get("initial_risk_pct"), 6),
        "addon_count": int(trade.get("addon_count") or 0),
        "addon_shares": int(trade.get("addon_shares") or 0),
        "addon_cost": round_float(trade.get("addon_cost") or 0.0, 2),
        "actual_risk_pct": round_float(trade.get("actual_risk_pct"), 6),
        "regime_exit_bucket": trade.get("regime_exit_bucket"),
        "regime_exit_score": round_float(trade.get("regime_exit_score"), 4),
    }
    row.update(build_path_features(trade, ticker_rows))

    post_addon_return = row.get("post_addon_return_to_exit_close")
    post_addon_min = row.get("post_addon_min_low_return")
    row["is_addon_trade"] = row["addon_count"] > 0
    row["is_loss"] = row["pnl"] < 0
    row["is_post_addon_deterioration"] = (
        row["is_addon_trade"]
        and (
            row["is_loss"]
            or row["exit_reason"] == "stop"
            or (post_addon_return is not None and post_addon_return < 0)
            or (post_addon_min is not None and post_addon_min <= -0.02)
        )
    )
    return row


def main():
    source = load_json(SOURCE_TRADES)
    snapshots = {
        window: load_json(path)["ohlcv"]
        for window, path in WINDOW_SNAPSHOTS.items()
    }

    all_rows = []
    for window, payload in source.items():
        ohlcv_by_ticker = snapshots[window]
        for trade in payload.get("trades", []):
            ticker_rows = ohlcv_by_ticker.get(trade.get("ticker"), [])
            all_rows.append(annotate_trade(window, trade, ticker_rows))

    addon_rows = [row for row in all_rows if row["is_addon_trade"]]
    family_rows = [row for row in all_rows if row["is_post_addon_deterioration"]]
    non_family_rows = [row for row in all_rows if not row["is_post_addon_deterioration"]]
    losing_rows = [row for row in all_rows if row["is_loss"]]
    tail_losses = sorted(losing_rows, key=lambda row: row["pnl"])[:3]
    family_losses = [row for row in family_rows if row["is_loss"]]
    addon_winners = [row for row in addon_rows if row["pnl"] > 0]

    window_summary = {}
    for window in source:
        rows = [row for row in all_rows if row["window"] == window]
        fam = [row for row in family_rows if row["window"] == window]
        losses = [row for row in rows if row["is_loss"]]
        fam_losses = [row for row in fam if row["is_loss"]]
        loss_abs = abs(sum(row["pnl"] for row in losses))
        fam_loss_abs = abs(sum(row["pnl"] for row in fam_losses))
        window_summary[window] = {
            "all": summarize(rows),
            "addon_trades": summarize([row for row in rows if row["is_addon_trade"]]),
            "family": summarize(fam),
            "family_loss_share_of_window_losses": round_float(pct(fam_loss_abs, loss_abs), 4),
        }

    family_loss_abs = abs(sum(row["pnl"] for row in family_losses))
    all_loss_abs = abs(sum(row["pnl"] for row in losing_rows))
    addon_winner_pnl = sum(row["pnl"] for row in addon_winners)
    family_loss_pnl = sum(row["pnl"] for row in family_losses)

    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "loss_attribution",
        "change_type": "failure_taxonomy",
        "single_causal_variable": "post-add-on deterioration loss taxonomy",
        "strategy_logic_changed": False,
        "production_change_made": False,
        "source_trades": SOURCE_TRADES.as_posix(),
        "source_snapshots": {k: v.as_posix() for k, v in WINDOW_SNAPSHOTS.items()},
        "definition": {
            "family_rule": (
                "addon_count > 0 and (final trade is a loss, stop exit, "
                "negative estimated post-addon return, or <= -2% post-addon low excursion)"
            ),
            "estimated_addon_date": (
                "entry date + accepted checkpoint_days(2) + next session; used only for "
                "path attribution, not for trade decisions"
            ),
            "reason_not_a_filter": (
                "The deterioration signal is mostly observable after capital is already added; "
                "this audit can propose future shadow lifecycle tests but cannot justify an entry filter."
            ),
        },
        "history_guardrails": {
            "not_generic_hold_quality": True,
            "not_low_mfe_stopout": True,
            "not_near_target_giveback": True,
            "not_overnight_gap": True,
            "not_overlap_pressure": True,
            "not_entry_extension": True,
            "not_production_strategy_change": True,
        },
        "overall": summarize(all_rows),
        "addon_summary": summarize(addon_rows),
        "family_summary": summarize(family_rows),
        "non_family_summary": summarize(non_family_rows),
        "family_loss_share_of_all_losses": round_float(pct(family_loss_abs, all_loss_abs), 4),
        "winner_collateral_to_family_loss_abs_ratio": round_float(
            pct(addon_winner_pnl, family_loss_abs), 4
        ),
        "substrategy_breakdown": {
            "family_by_strategy": by_counter(family_rows, "strategy"),
            "family_by_sector": by_counter(family_rows, "sector"),
            "addon_by_strategy": by_counter(addon_rows, "strategy"),
            "addon_by_sector": by_counter(addon_rows, "sector"),
        },
        "tail_loss_contribution": {
            "worst_3_losses": tail_losses,
            "family_hits_in_worst_3": sum(1 for row in tail_losses if row["is_post_addon_deterioration"]),
            "family_loss_dollars_in_worst_3": round_float(
                sum(row["pnl"] for row in tail_losses if row["is_post_addon_deterioration"]), 2
            ),
        },
        "hold_quality_signatures": {
            "addon_trade_count": len(addon_rows),
            "addon_loss_count": sum(1 for row in addon_rows if row["is_loss"]),
            "family_trade_count": len(family_rows),
            "family_loss_count": len(family_losses),
            "median_post_addon_return_to_exit_close": median(
                row.get("post_addon_return_to_exit_close") for row in addon_rows
            ),
            "median_post_addon_min_low_return": median(
                row.get("post_addon_min_low_return") for row in addon_rows
            ),
            "family_rows": family_rows,
        },
        "false_positive_false_negative_tradeoff": {
            "naive_disable_all_addons_false_positive_cost": round_float(addon_winner_pnl, 2),
            "naive_disable_all_addons_loss_avoided": round_float(abs(family_loss_pnl), 2),
            "collateral_to_loss_ratio": round_float(pct(addon_winner_pnl, family_loss_abs), 4),
            "false_negative_if_ignored": (
                "One observed post-add-on deterioration loss remains untreated, "
                f"equal to ${abs(family_loss_pnl):.2f} in this accepted-trade sample."
            ),
            "interpretation": (
                "The family is real but too sparse and has too much addon-winner collateral "
                "for a direct addon veto. Future work should test a post-addon lifecycle "
                "shadow monitor, not disable follow-through capital."
            ),
        },
        "window_summary": window_summary,
        "future_test_candidates": [
            {
                "candidate": "default-off post-addon day-3 weakness monitor",
                "why": "Deterioration is observable after the add-on, so the natural test is lifecycle management.",
                "not_a_rule_yet": True,
                "required_next_evidence": [
                    "candidate-level path replay showing day-3 post-addon weakness repeats beyond one losing trade",
                    "winner collateral check against addon winners that briefly dipped then hit target",
                    "shared production/backtest lifecycle adapter before any strategy change",
                ],
            }
        ],
        "decision": "observed_only",
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as handle:
        json.dump(artifact, handle, indent=2, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "artifact": OUTPUT.as_posix(),
        "family_trade_count": len(family_rows),
        "family_loss_count": len(family_losses),
        "family_loss_share_of_all_losses": artifact["family_loss_share_of_all_losses"],
        "collateral_to_loss_ratio": artifact["winner_collateral_to_family_loss_abs_ratio"],
    }, indent=2, ensure_ascii=False))


def median(values):
    clean = sorted(value for value in values if value is not None)
    if not clean:
        return None
    mid = len(clean) // 2
    if len(clean) % 2:
        return round_float(clean[mid], 6)
    return round_float((clean[mid - 1] + clean[mid]) / 2.0, 6)


if __name__ == "__main__":
    main()
