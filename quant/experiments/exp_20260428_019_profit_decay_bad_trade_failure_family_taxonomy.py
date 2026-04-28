"""exp-20260428-019: profit-decay bad-trade taxonomy.

Observed-only loss attribution runner. It changes no production strategy
behavior and writes only the artifact declared in the experiment ticket.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260428-019"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260428_019_profit_decay_bad_trade_failure_family_taxonomy.json"

WINDOW = {
    "name": "late_strong",
    "start": "2025-10-23",
    "end": "2026-04-21",
    "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
    "regime": "slow-melt bull / accepted-stack dominant tape",
}

PRIOR_OVERLAP_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260428-009"
    / "exp_20260428_009_bad_trade_family_overlap_priority_taxonomy.json"
)

MIN_MFE_PCT = 0.03
MIN_TARGET_PROGRESS = 0.15
PROTECTIVE_PROFIT_PCT = 0.02


def _safe_round(value: float | None, digits: int = 6) -> float | None:
    if value is None or not isinstance(value, (int, float)) or math.isnan(value):
        return None
    return round(float(value), digits)


def _safe_mean(values: list[float]) -> float | None:
    clean = [float(v) for v in values if isinstance(v, (int, float)) and not math.isnan(v)]
    return mean(clean) if clean else None


def _safe_median(values: list[float]) -> float | None:
    clean = [float(v) for v in values if isinstance(v, (int, float)) and not math.isnan(v)]
    return median(clean) if clean else None


def _load_frames(snapshot_path: str) -> dict[str, pd.DataFrame]:
    payload = json.loads((REPO_ROOT / snapshot_path).read_text(encoding="utf-8"))
    frames = {}
    for ticker, rows in (payload.get("ohlcv") or {}).items():
        df = pd.DataFrame(rows)
        if df.empty:
            continue
        df["Date"] = pd.to_datetime(df["Date"])
        frames[ticker.upper()] = df.set_index("Date").sort_index()
    return frames


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "strategy_total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
        "tail_loss_share": result.get("tail_loss_share"),
    }


def _trade_key(row: dict) -> tuple[str, str, str, str]:
    return (
        str(row.get("window", WINDOW["name"])),
        str(row.get("ticker")),
        str(row.get("entry_date")),
        str(row.get("exit_date")),
    )


def _prior_overlap_index() -> dict[tuple[str, str, str, str], dict]:
    if not PRIOR_OVERLAP_ARTIFACT.exists():
        return {}
    payload = json.loads(PRIOR_OVERLAP_ARTIFACT.read_text(encoding="utf-8"))
    return {_trade_key(row): row for row in payload.get("loss_rows", [])}


def _trade_features(trade: dict, df: pd.DataFrame) -> dict:
    entry_date = pd.Timestamp(trade["entry_date"])
    exit_date = pd.Timestamp(trade["exit_date"])
    if entry_date not in df.index or exit_date not in df.index:
        return {"feature_status": "missing_trade_dates"}

    entry_loc = int(df.index.get_loc(entry_date))
    exit_loc = int(df.index.get_loc(exit_date))
    hold_rows = df.iloc[min(entry_loc, exit_loc) : max(entry_loc, exit_loc) + 1]
    entry_price = trade.get("entry_price")
    stop_price = trade.get("stop_price")
    target_mult = trade.get("target_mult_used")
    risk_pct = trade.get("initial_risk_pct")

    if not isinstance(entry_price, (int, float)) or hold_rows.empty:
        return {"feature_status": "missing_price_path"}
    if not isinstance(risk_pct, (int, float)) and isinstance(stop_price, (int, float)):
        risk_pct = (entry_price - stop_price) / entry_price

    highs = [float(v) for v in hold_rows["High"].tolist() if isinstance(v, (int, float))]
    lows = [float(v) for v in hold_rows["Low"].tolist() if isinstance(v, (int, float))]
    if not highs or not lows:
        return {"feature_status": "missing_high_low_path"}

    max_high = max(highs)
    min_low = min(lows)
    mfe_pct = (max_high / entry_price) - 1
    mae_pct = (min_low / entry_price) - 1
    mfe_r = mfe_pct / risk_pct if risk_pct else None
    target_progress = None
    if isinstance(risk_pct, (int, float)) and isinstance(target_mult, (int, float)) and risk_pct > 0:
        target_progress = mfe_pct / (risk_pct * target_mult)

    pnl_pct = trade.get("pnl_pct_net")
    profit_decay_trigger = (
        isinstance(mfe_pct, (int, float))
        and isinstance(target_progress, (int, float))
        and mfe_pct >= MIN_MFE_PCT
        and target_progress >= MIN_TARGET_PROGRESS
    )
    is_family_loss = bool(trade.get("pnl", 0) < 0 and profit_decay_trigger)
    is_winner_collateral = bool(trade.get("pnl", 0) > 0 and profit_decay_trigger)
    giveback_from_mfe_pct = None
    if isinstance(pnl_pct, (int, float)):
        giveback_from_mfe_pct = mfe_pct - pnl_pct

    return {
        "feature_status": "ok",
        "holding_days": int(len(hold_rows)),
        "mfe_pct": _safe_round(mfe_pct),
        "mae_pct": _safe_round(mae_pct),
        "mfe_r": _safe_round(mfe_r),
        "target_progress": _safe_round(target_progress),
        "giveback_from_mfe_pct": _safe_round(giveback_from_mfe_pct),
        "profit_decay_trigger": profit_decay_trigger,
        "profit_decay_family_loss": is_family_loss,
        "winner_collateral_match": is_winner_collateral,
    }


def _summarize(rows: list[dict]) -> dict:
    pnl = [float(r["pnl"]) for r in rows]
    return {
        "count": len(rows),
        "pnl_sum": _safe_round(sum(pnl), 2) if pnl else 0,
        "avg_pnl": _safe_round(_safe_mean(pnl), 2),
        "median_pnl": _safe_round(_safe_median(pnl), 2),
        "strategy_counts": dict(Counter(r.get("strategy") for r in rows)),
        "sector_counts": dict(Counter(r.get("sector") for r in rows)),
        "exit_reason_counts": dict(Counter(r.get("exit_reason") for r in rows)),
        "tickers": sorted(set(r.get("ticker") for r in rows)),
    }


def _tail_losses(loss_rows: list[dict]) -> list[dict]:
    if not loss_rows:
        return []
    losses = sorted(loss_rows, key=lambda r: r["pnl"])
    n = max(1, math.ceil(len(losses) * 0.25))
    return losses[:n]


def _compact_row(trade: dict) -> dict:
    keys = [
        "window",
        "ticker",
        "strategy",
        "sector",
        "entry_date",
        "exit_date",
        "exit_reason",
        "pnl",
        "pnl_pct_net",
        "initial_risk_pct",
        "holding_days",
        "mfe_pct",
        "mae_pct",
        "mfe_r",
        "target_progress",
        "giveback_from_mfe_pct",
        "profit_decay_trigger",
        "profit_decay_family_loss",
        "winner_collateral_match",
        "prior_primary_family",
        "prior_family_flags",
    ]
    return {key: trade.get(key) for key in keys}


def run() -> dict:
    result = BacktestEngine(
        get_universe(),
        start=WINDOW["start"],
        end=WINDOW["end"],
        ohlcv_snapshot_path=str(REPO_ROOT / WINDOW["snapshot"]),
    ).run()
    frames = _load_frames(WINDOW["snapshot"])
    prior_index = _prior_overlap_index()

    rows = []
    for trade in result.get("trades") or []:
        ticker = str(trade.get("ticker", "")).upper()
        features = _trade_features(trade, frames[ticker]) if ticker in frames else {"feature_status": "missing_ticker_frame"}
        row = {**trade, **features, "window": WINDOW["name"]}
        prior = prior_index.get(_trade_key(row), {})
        row["prior_primary_family"] = prior.get("primary_family")
        row["prior_family_flags"] = prior.get("family_flags") or {}
        rows.append(row)

    losses = [r for r in rows if r.get("pnl", 0) < 0]
    winners = [r for r in rows if r.get("pnl", 0) > 0]
    family_losses = [r for r in losses if r.get("profit_decay_family_loss")]
    collateral_winners = [r for r in winners if r.get("winner_collateral_match")]
    tail = _tail_losses(losses)
    tail_family = [r for r in tail if r.get("profit_decay_family_loss")]

    total_loss_abs = sum(abs(float(r["pnl"])) for r in losses)
    family_loss_abs = sum(abs(float(r["pnl"])) for r in family_losses)
    tail_loss_abs = sum(abs(float(r["pnl"])) for r in tail)
    tail_family_abs = sum(abs(float(r["pnl"])) for r in tail_family)
    collateral_pnl = sum(float(r["pnl"]) for r in collateral_winners)
    protected_loss_proxy = 0.0
    for r in family_losses:
        # A future lifecycle repair might try to protect +2% once the trade has
        # made meaningful progress. This is an oracle proxy, not a rule.
        entry_value = float(r["entry_price"]) * float(r["shares"])
        protected_loss_proxy += abs(float(r["pnl"])) + (entry_value * PROTECTIVE_PROFIT_PCT)

    overlap_counts = Counter(r.get("prior_primary_family") or "unclassified_prior" for r in family_losses)
    flag_overlap_counts = Counter()
    for row in family_losses:
        for name, enabled in (row.get("prior_family_flags") or {}).items():
            if enabled:
                flag_overlap_counts[name] += 1

    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "lane": "loss_attribution",
        "change_type": "failure_taxonomy",
        "single_causal_variable": "profit-decay bad-trade failure family taxonomy",
        "strategy_behavior_changed": False,
        "history_guardrails": {
            "does_not_add_filter": True,
            "does_not_change_strategy_logic": True,
            "distinct_from_low_mfe": f"requires MFE >= {MIN_MFE_PCT:.0%} and target_progress >= {MIN_TARGET_PROGRESS:.0%}",
            "not_a_production_rule": "condition is observed from realized in-trade path and is only an attribution lens",
            "overlap_quantified_against": str(PRIOR_OVERLAP_ARTIFACT.relative_to(REPO_ROOT)),
        },
        "taxonomy_definition": {
            "name": "profit_decay_loser",
            "criteria": {
                "pnl": "< 0",
                "mfe_pct_gte": MIN_MFE_PCT,
                "target_progress_gte": MIN_TARGET_PROGRESS,
            },
            "interpretation": "The trade had enough favorable excursion to matter, then decayed into a realized loser. A future fix would be lifecycle profit protection, not an entry veto.",
        },
        "window": {
            "name": WINDOW["name"],
            "range": {"start": WINDOW["start"], "end": WINDOW["end"]},
            "regime": WINDOW["regime"],
            "metrics": _metrics(result),
        },
        "aggregate": {
            "trade_count": len(rows),
            "loss_count": len(losses),
            "win_count": len(winners),
            "total_loss_abs": _safe_round(total_loss_abs, 2),
            "family_loss_count": len(family_losses),
            "family_loss_abs": _safe_round(family_loss_abs, 2),
            "family_loss_frequency_share": _safe_round(len(family_losses) / len(losses) if losses else None, 4),
            "family_loss_dollar_share": _safe_round(family_loss_abs / total_loss_abs if total_loss_abs else None, 4),
            "tail_loss_count": len(tail),
            "tail_loss_abs": _safe_round(tail_loss_abs, 2),
            "tail_family_count": len(tail_family),
            "tail_family_abs": _safe_round(tail_family_abs, 2),
            "tail_loss_share_explained": _safe_round(tail_family_abs / tail_loss_abs if tail_loss_abs else None, 4),
            "winner_collateral_count": len(collateral_winners),
            "winner_collateral_pnl": _safe_round(collateral_pnl, 2),
            "oracle_loss_protection_proxy": _safe_round(protected_loss_proxy, 2),
            "oracle_protection_minus_winner_collateral": _safe_round(protected_loss_proxy - collateral_pnl, 2),
        },
        "overlap_with_prior_taxonomies": {
            "primary_family_counts": dict(overlap_counts),
            "family_flag_counts": dict(flag_overlap_counts),
            "new_unexplained_family_loss_count": sum(1 for r in family_losses if not r.get("prior_primary_family")),
            "new_unexplained_family_loss_abs": _safe_round(
                sum(abs(float(r["pnl"])) for r in family_losses if not r.get("prior_primary_family")),
                2,
            ),
        },
        "family_loss_summary": _summarize(family_losses),
        "winner_collateral_summary": _summarize(collateral_winners),
        "future_candidate_fix_shape": {
            "candidate_type": "observed-only lifecycle profit-protection audit, not a hard entry filter",
            "why": "The signal is only knowable after entry and overlaps existing gap-down families in this window.",
            "next_test": "Only retry if a non-oracle adverse event, failed reclaim, or news confirmation can separate decaying losers from high-MFE winners.",
            "risk": "Naive profit protection would touch many winners in the same window and likely truncate the accepted stack's largest source of PnL.",
        },
        "loss_rows": [_compact_row(r) for r in family_losses],
        "winner_collateral_rows": [_compact_row(r) for r in collateral_winners],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8")
    return artifact


if __name__ == "__main__":
    output = run()
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "artifact": str(OUT_JSON),
                "aggregate": output["aggregate"],
                "overlap_with_prior_taxonomies": output["overlap_with_prior_taxonomies"],
            },
            indent=2,
            sort_keys=True,
        )
    )
