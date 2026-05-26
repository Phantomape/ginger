"""exp-20260526-004: undercut-and-reclaim paper sleeve.

This alpha search tests one new free-OHLCV candidate-pool source: liquid
stocks that undercut a prior 20-day low during a short pullback, reclaim that
level by the close, and close in the upper part of the daily range on stronger
volume. The route is default-off paper only: at most one candidate per signal
day, next-open paper entry, and ten-trading-day close exit.

Core signal generation, ranking, sizing, exits, LLM/news replay, watchlists,
and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
LEGACY_DIR = EXPERIMENT_DIR / "legacy"
for path in (QUANT_DIR, EXPERIMENT_DIR, LEGACY_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as base  # noqa: E402
import exp_20260426_041_opening_range_continuation_shadow as ohlcv_shadow  # noqa: E402


EXPERIMENT_ID = "exp-20260526-004"
STEM = "undercut_reclaim_paper_sleeve"
TRIAL_FAMILY = "undercut_reclaim_reversal_default_off_paper_sleeve"
CHANGED_VARIABLE = "undercut_reclaim_daily_top1_next_open_10d_fixed_notional_sleeve_v1"
RULE_VERSION = "undercut_reclaim_reversal_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

LOOKBACK_LOW_DAYS = 20
LOOKBACK_VOLUME_DAYS = 20
LOOKBACK_PULLBACK_DAYS = 5
LOOKBACK_RS_DAYS = 10
MIN_UNDERCUT_PCT = 0.005
MIN_RECLAIM_PCT = 0.0025
MIN_VOLUME_RATIO = 1.10
MAX_PRIOR_5D_RETURN = -0.03
MIN_CLOSE_LOCATION = 0.60
MIN_RS_10D_VS_SPY = -0.02
MIN_AVG_DOLLAR_VOLUME_20 = 25_000_000.0
MAX_PAPER_TRADES_PER_DAY = 1
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30

PATTERN_AUDIT: "OrderedDict[str, dict[str, Any]]" = OrderedDict()


def _configure_base_module() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.OUT_DIR = OUT_DIR
    base.OUT_JSON = OUT_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.ARTIFACT_MD = ARTIFACT_MD
    base.EXPERIMENT_LOG = EXPERIMENT_LOG
    base.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    base.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    base.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    base.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    base.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    base.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    base.shadow = ohlcv_shadow

    for name in (
        "MIN_PRIOR_DAY_RETURN",
        "MIN_PRIOR_DAY_RS_VS_SPY",
        "MIN_OPEN_VS_PRIOR_CLOSE",
        "MIN_CANDIDATE_RS_VS_SPY",
        "MIN_DOLLAR_VOLUME",
    ):
        if not hasattr(ohlcv_shadow, name):
            setattr(ohlcv_shadow, name, None)


def _close_return(rows: list[dict[str, Any]], start_idx: int, end_idx: int) -> float | None:
    if start_idx < 0 or end_idx >= len(rows):
        return None
    start = ohlcv_shadow._value(rows[start_idx], "Close")
    end = ohlcv_shadow._value(rows[end_idx], "Close")
    if not start or end is None:
        return None
    return (end / start) - 1.0


def _avg_dollar_volume(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx - lookback + 1 < 0:
        return None
    values: list[float] = []
    for row_idx in range(idx - lookback + 1, idx + 1):
        close = ohlcv_shadow._value(rows[row_idx], "Close")
        volume = ohlcv_shadow._value(rows[row_idx], "Volume")
        if close is None or volume is None:
            return None
        values.append(close * volume)
    return sum(values) / len(values)


def _prior_low(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx - lookback < 0:
        return None
    lows = [
        ohlcv_shadow._value(rows[row_idx], "Low")
        for row_idx in range(idx - lookback, idx)
    ]
    if any(value is None for value in lows):
        return None
    return min(float(value) for value in lows)


def _avg_prior_volume(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx - lookback < 0:
        return None
    volumes = [
        ohlcv_shadow._value(rows[row_idx], "Volume")
        for row_idx in range(idx - lookback, idx)
    ]
    if any(value is None for value in volumes):
        return None
    return sum(float(value) for value in volumes) / lookback


def _undercut_reclaim_candidate(
    snapshot: dict[str, list[dict[str, Any]]],
    ticker: str,
    rows: list[dict[str, Any]],
    idx: int,
) -> dict[str, Any] | None:
    date = ohlcv_shadow._date(rows[idx])
    spy_rows = ohlcv_shadow._series(snapshot, "SPY")
    spy_idx = ohlcv_shadow._row_index(spy_rows).get(date)
    if spy_idx is None:
        return None

    row = rows[idx]
    open_ = ohlcv_shadow._value(row, "Open")
    high = ohlcv_shadow._value(row, "High")
    low = ohlcv_shadow._value(row, "Low")
    close = ohlcv_shadow._value(row, "Close")
    volume = ohlcv_shadow._value(row, "Volume")
    prior_low20 = _prior_low(rows, idx, LOOKBACK_LOW_DAYS)
    avg_prior_volume20 = _avg_prior_volume(rows, idx, LOOKBACK_VOLUME_DAYS)
    avg_dollar_volume20 = _avg_dollar_volume(rows, idx, LOOKBACK_VOLUME_DAYS)
    prior_5d_return = _close_return(rows, idx - LOOKBACK_PULLBACK_DAYS, idx - 1)
    stock_ret10 = _close_return(rows, idx - LOOKBACK_RS_DAYS, idx)
    spy_ret10 = _close_return(spy_rows, spy_idx - LOOKBACK_RS_DAYS, spy_idx)
    if (
        open_ is None
        or high is None
        or low is None
        or close is None
        or volume is None
        or prior_low20 is None
        or avg_prior_volume20 is None
        or avg_dollar_volume20 is None
        or prior_5d_return is None
        or stock_ret10 is None
        or spy_ret10 is None
    ):
        return None
    if avg_dollar_volume20 < MIN_AVG_DOLLAR_VOLUME_20:
        return None
    if high <= low or prior_low20 <= 0:
        return None
    if close <= open_:
        return None

    undercut_pct = (low / prior_low20) - 1.0
    reclaim_pct = (close / prior_low20) - 1.0
    volume_ratio = volume / avg_prior_volume20 if avg_prior_volume20 else None
    close_location = (close - low) / (high - low)
    rs10_vs_spy = stock_ret10 - spy_ret10
    if undercut_pct > -MIN_UNDERCUT_PCT:
        return None
    if reclaim_pct < MIN_RECLAIM_PCT:
        return None
    if volume_ratio is None or volume_ratio < MIN_VOLUME_RATIO:
        return None
    if prior_5d_return > MAX_PRIOR_5D_RETURN:
        return None
    if close_location < MIN_CLOSE_LOCATION:
        return None
    if rs10_vs_spy < MIN_RS_10D_VS_SPY:
        return None

    score = (
        abs(undercut_pct) * 4.0
        + reclaim_pct * 5.0
        + min(volume_ratio - MIN_VOLUME_RATIO, 2.0) * 0.20
        + close_location * 0.25
        + max(rs10_vs_spy, 0.0) * 0.75
    )
    return {
        "ticker": ticker,
        "date": date,
        "sector": ohlcv_shadow.SECTOR_MAP.get(ticker, "Unknown"),
        "close": base._round(close, 4),
        "prior_low20": base._round(prior_low20, 4),
        "undercut_pct": base._round(undercut_pct, 6),
        "reclaim_pct": base._round(reclaim_pct, 6),
        "volume_ratio20": base._round(volume_ratio, 6),
        "prior_5d_return": base._round(prior_5d_return, 6),
        "close_location": base._round(close_location, 6),
        "stock_ret10": base._round(stock_ret10, 6),
        "spy_ret10": base._round(spy_ret10, 6),
        "rs10_vs_spy": base._round(rs10_vs_spy, 6),
        "avg_dollar_volume20": base._round(avg_dollar_volume20, 2),
        "undercut_reclaim_score": base._round(score, 6),
        "undercut_reclaim_rule_version": RULE_VERSION,
        "known_at": "signal-date close before next-open paper entry",
        "trade_enabled": False,
        "alters_orders": False,
    }


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> list[dict[str, Any]]:
    entries_by_date = ohlcv_shadow._baseline_entries(before_result)
    dates = {
        date
        for date in ohlcv_shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= date <= str(cfg["end"])
    }
    raw_considered = 0
    candidates: list[dict[str, Any]] = []
    for ticker in sorted(set(universe).intersection(snapshot)):
        if ticker in ohlcv_shadow.EXCLUDED_TICKERS:
            continue
        rows = ohlcv_shadow._series(snapshot, ticker)
        for idx, row in enumerate(rows):
            date = ohlcv_shadow._date(row)
            if date not in dates:
                continue
            raw_considered += 1
            candidate = _undercut_reclaim_candidate(snapshot, ticker, rows, idx)
            if candidate is None:
                continue
            ab_entries = entries_by_date.get(candidate["date"], [])
            candidate["same_day_ab_entry_count"] = len(ab_entries)
            candidate["same_day_ab_overlap"] = bool(ab_entries)
            candidate["same_ticker_ab_overlap"] = any(
                trade.get("ticker") == candidate["ticker"] for trade in ab_entries
            )
            candidates.append(candidate)

    label = next(
        (
            window_label
            for window_label, window_cfg in base.WINDOWS.items()
            if window_cfg is cfg
        ),
        str(cfg.get("start")),
    )
    PATTERN_AUDIT[label] = {
        "raw_ticker_days_considered": raw_considered,
        "undercut_reclaim_candidates": len(candidates),
        "candidate_days": len({row["date"] for row in candidates}),
        "rule_version": RULE_VERSION,
    }
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["undercut_reclaim_score"]),
            -float(row["volume_ratio20"]),
            -float(row["close_location"]),
            row["ticker"],
        )
    )
    return candidates


def _update_payload(payload: dict[str, Any]) -> dict[str, Any]:
    decision = (
        "promising_replay_only_undercut_reclaim_paper_sleeve"
        if payload["gate4"]["passed"]
        else "rejected_undercut_reclaim_paper_sleeve"
    )
    payload["status"] = decision
    payload["decision"] = decision
    payload["hypothesis"] = (
        "A liquid undercut-and-reclaim reversal after a short pullback may add "
        "default-off paper candidate-pool alpha because it captures failed "
        "breakdowns rather than continuation chases. The field uses only free "
        "daily OHLCV known at the signal-date close."
    )
    payload["change_type"] = "undercut_reclaim_reversal_default_off_paper_sleeve"
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["trial_family"] = TRIAL_FAMILY
    payload["prior_trial_count"] = 1
    payload["mechanism_family"] = "free_ohlcv_reversal_candidate_pool"
    payload["trial_variant_id"] = "undercut_reclaim_top1_v1"
    payload["nearby_prior_experiments"] = [
        "exp-20260426-060",
        "exp-20260426-051",
        "exp-20260525-020",
        "exp-20260525-026",
        "exp-20260526-001",
        "exp-20260526-002",
        "exp-20260526-003",
    ]
    payload["multiple_testing_risk_bucket"] = "moderate"
    payload["new_evidence_type"] = "production_visible_undercut_reclaim_reversal_source_from_free_ohlcv"
    payload["parameters"]["shadow_entry_filters"] = {
        "lookback_low_days": LOOKBACK_LOW_DAYS,
        "lookback_volume_days": LOOKBACK_VOLUME_DAYS,
        "lookback_pullback_days": LOOKBACK_PULLBACK_DAYS,
        "lookback_rs_days": LOOKBACK_RS_DAYS,
        "min_undercut_pct_below_prior_low": MIN_UNDERCUT_PCT,
        "min_reclaim_pct_above_prior_low": MIN_RECLAIM_PCT,
        "min_volume_ratio_vs_prior20": MIN_VOLUME_RATIO,
        "max_prior_5d_return": MAX_PRIOR_5D_RETURN,
        "min_close_location": MIN_CLOSE_LOCATION,
        "min_rs10_vs_spy": MIN_RS_10D_VS_SPY,
        "min_avg_dollar_volume20": MIN_AVG_DOLLAR_VOLUME_20,
        "requires_green_day": True,
    }
    payload["parameters"]["selection_rank"] = [
        "signal_date",
        "undercut_reclaim_score desc",
        "volume_ratio20 desc",
        "close_location desc",
        "ticker asc",
    ]
    payload["parameters"]["acceptance"].update(
        {
            "min_target_trades": MIN_TARGET_TRADES,
            "min_target_windows": MIN_TARGET_WINDOWS,
            "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
            "max_positive_hhi": MAX_POSITIVE_HHI,
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry / candidate_pool: failed-breakdown reversal candidates may "
            "expand the paper pool without repeating recent continuation "
            "sources. This matches the playbook's free-data candidate-pool "
            "direction and avoids LLM soft-ranking."
        ),
        "2_history_check": {
            "exp-20260426-060": (
                "Observed-only undercut/reclaim universe scout; no current "
                "three-window next-open fixed-notional before/after Gate 4."
            ),
            "exp-20260426-051": (
                "Pullback-reclaim replay failed; this rule is undercut/reclaim "
                "after a failed breakdown, not a multi-day pullback reclaim."
            ),
            "exp-20260525-020/022/037": (
                "VCP+QQQ is accepted paper; this does not retune VCP thresholds "
                "or top-N."
            ),
            "exp-20260526-001/002/003": (
                "Gap-and-hold and smooth-path sources were freshly rejected; "
                "this is a different reversal source."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Same three docs/backtesting.md windows; positive aggregate EV/PnL; "
            "3/3 EV-improved windows; no PnL-regressed window; >=20 paper "
            "trades across all 3 windows; drawdown drift <=0.5pp; survival "
            ">=5%; concentration inside guardrails."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260526_004_undercut_reclaim_paper_sleeve.py"
        ),
    }
    payload["gate2"]["runtime_fields"] = [
        "canonical OHLCV Date/Open/High/Low/Close/Volume rows",
        "SPY OHLCV Close rows for 10-day relative strength",
        "derived prior 20-day low known at signal-date close",
        "derived prior 20-day volume and dollar-volume fields",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["gate2"]["note"] = (
        "The sleeve uses only same-day and trailing daily OHLCV fields known at "
        "the signal-date close, then enters paper only at the next open. It "
        "does not ask LLM or production to infer hidden fields."
    )
    payload["undercut_reclaim_audit"] = PATTERN_AUDIT
    payload["why_not_other_changes"] = (
        "Skipped LLM soft-ranking and expectation-residual leaders because "
        "recent logs show sparse usable data. Skipped state-surface, VCP "
        "top-N/threshold, broad-market scalar, opening-range, sector-leadership, "
        "inside-day, gap-and-hold, and smooth-path retreads due fresh rejections "
        "or anti-repeat rules. This tests a distinct free-OHLCV reversal source "
        "inside the existing production universe."
    )
    payload["interpretation"] = (
        "The undercut-and-reclaim sleeve cleared Gate 4 as a replay-only lead, "
        "but no production/shared policy was promoted."
        if payload["gate4"]["passed"]
        else (
            "The undercut-and-reclaim sleeve did not clear Gate 4. Do not "
            "promote or retry nearby undercut/reclaim thresholds on these "
            "windows without forward paper rows or a materially different "
            "event/source confirmation field."
        )
    )
    payload["rejection_reason"] = (
        None if payload["gate4"]["passed"] else payload.get("rejection_reason")
    )
    payload["next_evidence_needed"] = (
        "If revisited, require forward paper outcomes or an orthogonal "
        "production-visible event/source confirmation field. Do not just retune "
        "undercut, reclaim, volume, or close-location thresholds on the frozen sample."
    )
    payload["production_impact"]["promotion_requirement"] = (
        "A retained result would still require a shared default-off paper "
        "adapter, daily report exposure, forward replacement-value ledger, and "
        "parity tests before any live/default behavior changes."
    )
    payload["related_files"] = [
        base._repo_rel(Path(__file__)),
        base._repo_rel(OUT_JSON),
        base._repo_rel(LOG_JSON),
        base._repo_rel(TICKET_JSON),
        base._repo_rel(ARTIFACT_MD),
        base._repo_rel(EXPERIMENT_LOG),
    ]
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Candidates | Days |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["undercut_reclaim_audit"].get(label, {})
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | "
            "${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | "
            "{trades} | {candidates} | {days} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                candidates=audit.get("undercut_reclaim_candidates"),
                days=audit.get("candidate_days"),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Undercut-and-Reclaim Paper Sleeve",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            (
                "Single variable: a default-off paper sleeve admits at most one "
                "liquid undercut-and-reclaim reversal candidate per day, enters "
                "at next open, and exits after ten trading days."
            ),
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- EV delta: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- target trades: `{payload['target_trade_summary']['total_trade_count']}` across `{len(payload['target_trade_summary']['windows_with_target_trades'])}` windows",
            f"- max single positive share: `{payload['target_trade_summary']['max_single_positive_pnl_share']}`",
            f"- positive PnL HHI: `{payload['target_trade_summary']['positive_pnl_hhi']}`",
            "",
            "## Pattern Audit",
            "",
            "```json",
            json.dumps(payload["undercut_reclaim_audit"], indent=2, sort_keys=True),
            "```",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            (
                "Replay-only and default-off paper only. No shared policy, run "
                "adapter, backtester adapter, production watchlist, order path, "
                "core entry, ranking, sizing, or exit behavior changed."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _persist(payload: dict[str, Any]) -> None:
    base._write_json(OUT_JSON, payload)
    base._write_json(LOG_JSON, payload)
    base._write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Undercut-and-reclaim paper sleeve",
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": base._repo_rel(ARTIFACT_MD),
            "json": base._repo_rel(OUT_JSON),
            "summary": payload["interpretation"],
        },
    )
    base._write_text(ARTIFACT_MD, _build_report(payload))
    base._upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    _configure_base_module()
    base._candidate_rows_for_window = _candidate_rows_for_window
    payload = _update_payload(base._build_payload())
    _persist(payload)
    print(
        json.dumps(
            base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "target_trade_summary": payload["target_trade_summary"],
                    "undercut_reclaim_audit": payload["undercut_reclaim_audit"],
                    "artifact": base._repo_rel(ARTIFACT_MD),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
