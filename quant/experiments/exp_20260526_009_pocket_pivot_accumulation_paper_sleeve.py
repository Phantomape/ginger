"""exp-20260526-009: pocket-pivot accumulation paper sleeve.

This alpha search tests a distinct free-OHLCV candidate source. The single
variable is a default-off paper sleeve that admits at most one liquid
pocket-pivot accumulation candidate per signal day when QQQ 20-day momentum is
above SPY, enters at the next open, and exits after ten trading days.

Core signal generation, ranking, sizing, exits, LLM/news replay, watchlists,
and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
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

import exp_20260426_041_opening_range_continuation_shadow as ohlcv_shadow  # noqa: E402
import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as base  # noqa: E402


EXPERIMENT_ID = "exp-20260526-009"
STEM = "pocket_pivot_accumulation_paper_sleeve"
TRIAL_FAMILY = "pocket_pivot_accumulation_default_off_paper_sleeve"
CHANGED_VARIABLE = (
    "pocket_pivot_accumulation_daily_top1_qqq_gt_spy20_next_open_10d_"
    "fixed_notional_sleeve_v1"
)
RULE_VERSION = "pocket_pivot_accumulation_qqq_confirmed_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

POCKET_LOOKBACK_DAYS = 10
MARKET_CONFIRM_LOOKBACK_DAYS = 20
MA_DAYS = 50
MIN_CLOSE = 8.0
MIN_AVG_DOLLAR_VOLUME_20 = 40_000_000.0
MIN_SIGNAL_DAY_RS_VS_SPY = 0.0
MAX_PCT_ABOVE_50D_MA = 0.30
MAX_PAPER_TRADES_PER_DAY = 1
MIN_TARGET_TRADES = 30
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30

EXCLUDED_TICKERS = {
    "ARKX",
    "GLD",
    "IAU",
    "IEF",
    "IWM",
    "QQQ",
    "SLV",
    "SPY",
    "TLT",
    "UFO",
    "UUP",
    "USO",
    "XLE",
    "XLP",
    "XLU",
    "XLV",
}

POCKET_AUDIT: "OrderedDict[str, dict[str, Any]]" = OrderedDict()


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


def _moving_average(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx - lookback < 0:
        return None
    values = [
        ohlcv_shadow._value(rows[row_idx], "Close")
        for row_idx in range(idx - lookback, idx)
    ]
    if any(value is None for value in values):
        return None
    return sum(float(value) for value in values) / len(values)


def _avg_dollar_volume(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx - lookback < 0:
        return None
    values: list[float] = []
    for row_idx in range(idx - lookback, idx):
        close = ohlcv_shadow._value(rows[row_idx], "Close")
        volume = ohlcv_shadow._value(rows[row_idx], "Volume")
        if close is None or volume is None:
            return None
        values.append(close * volume)
    return sum(values) / len(values)


def _market_context(
    snapshot: dict[str, list[dict[str, Any]]],
    date: str,
) -> dict[str, Any]:
    qqq_rows = ohlcv_shadow._series(snapshot, "QQQ")
    spy_rows = ohlcv_shadow._series(snapshot, "SPY")
    qqq_idx = ohlcv_shadow._row_index(qqq_rows).get(date)
    spy_idx = ohlcv_shadow._row_index(spy_rows).get(date)
    qqq_ret20 = (
        _close_return(qqq_rows, qqq_idx - MARKET_CONFIRM_LOOKBACK_DAYS, qqq_idx)
        if qqq_idx is not None
        else None
    )
    spy_ret20 = (
        _close_return(spy_rows, spy_idx - MARKET_CONFIRM_LOOKBACK_DAYS, spy_idx)
        if spy_idx is not None
        else None
    )
    qqq_gt_spy = (
        qqq_ret20 is not None and spy_ret20 is not None and qqq_ret20 > spy_ret20
    )
    return {
        "qqq_gt_spy20": qqq_gt_spy,
        "qqq_ret20_on_signal": base._round(qqq_ret20, 6),
        "spy_ret20_on_signal": base._round(spy_ret20, 6),
        "qqq_minus_spy_ret20": (
            base._round(qqq_ret20 - spy_ret20, 6)
            if qqq_ret20 is not None and spy_ret20 is not None
            else None
        ),
        "market_confirmation_rule_version": "qqq_gt_spy20_close_to_close_v1",
        "known_at": "after_signal_date_close_before_next_open_paper_entry",
    }


def _pocket_pivot_on_signal_date(
    rows: list[dict[str, Any]],
    idx: int,
) -> dict[str, Any] | None:
    if idx <= 0 or idx - POCKET_LOOKBACK_DAYS < 0:
        return None
    close = ohlcv_shadow._value(rows[idx], "Close")
    prev_close = ohlcv_shadow._value(rows[idx - 1], "Close")
    volume = ohlcv_shadow._value(rows[idx], "Volume")
    if close is None or prev_close is None or volume is None or close <= prev_close:
        return None

    down_volumes: list[float] = []
    for prior_idx in range(idx - POCKET_LOOKBACK_DAYS, idx):
        prior_close = ohlcv_shadow._value(rows[prior_idx], "Close")
        prior_prev_close = ohlcv_shadow._value(rows[prior_idx - 1], "Close")
        prior_volume = ohlcv_shadow._value(rows[prior_idx], "Volume")
        if prior_close is None or prior_prev_close is None or prior_volume is None:
            continue
        if prior_close < prior_prev_close:
            down_volumes.append(float(prior_volume))
    if not down_volumes:
        return None
    max_down_volume = max(down_volumes)
    if volume <= max_down_volume:
        return None
    return {
        "pocket_pivot_volume_ratio": base._round(volume / max_down_volume, 6),
        "pocket_pivot_max_prior_down_volume": base._round(max_down_volume, 2),
        "pocket_pivot_down_volume_count": len(down_volumes),
        "pocket_pivot_scan_days": POCKET_LOOKBACK_DAYS,
        "pocket_pivot_rule_version": RULE_VERSION,
    }


def _candidate_for_day(
    snapshot: dict[str, list[dict[str, Any]]],
    ticker: str,
    rows: list[dict[str, Any]],
    idx: int,
) -> dict[str, Any] | None:
    date = ohlcv_shadow._date(rows[idx])
    pocket = _pocket_pivot_on_signal_date(rows, idx)
    if pocket is None:
        return None

    spy_rows = ohlcv_shadow._series(snapshot, "SPY")
    spy_idx = ohlcv_shadow._row_index(spy_rows).get(date)
    if spy_idx is None:
        return None

    row = rows[idx]
    close = ohlcv_shadow._value(row, "Close")
    volume = ohlcv_shadow._value(row, "Volume")
    if close is None or volume is None or close < MIN_CLOSE:
        return None
    avg_dollar_volume20 = _avg_dollar_volume(rows, idx, 20)
    ma50 = _moving_average(rows, idx, MA_DAYS)
    ret20 = _close_return(rows, idx - 20, idx)
    spy_ret20 = _close_return(spy_rows, spy_idx - 20, spy_idx)
    signal_ret = _close_return(rows, idx - 1, idx)
    spy_signal_ret = _close_return(spy_rows, spy_idx - 1, spy_idx)
    if (
        avg_dollar_volume20 is None
        or ma50 is None
        or ret20 is None
        or spy_ret20 is None
        or signal_ret is None
        or spy_signal_ret is None
    ):
        return None
    pct_above_50d_ma = (close / ma50) - 1.0 if ma50 else None
    signal_day_rs_vs_spy = signal_ret - spy_signal_ret
    rs20_vs_spy = ret20 - spy_ret20
    market = _market_context(snapshot, date)
    if avg_dollar_volume20 < MIN_AVG_DOLLAR_VOLUME_20:
        return None
    if pct_above_50d_ma is None or pct_above_50d_ma <= 0:
        return None
    if pct_above_50d_ma > MAX_PCT_ABOVE_50D_MA:
        return None
    if signal_day_rs_vs_spy <= MIN_SIGNAL_DAY_RS_VS_SPY:
        return None
    if market["qqq_gt_spy20"] is not True:
        return None

    score = (
        float(pocket["pocket_pivot_volume_ratio"]) * 0.50
        + max(rs20_vs_spy, 0.0) * 4.0
        + max(signal_day_rs_vs_spy, 0.0) * 6.0
        + min(pct_above_50d_ma, MAX_PCT_ABOVE_50D_MA)
    )
    return {
        "ticker": ticker,
        "date": date,
        "sector": ohlcv_shadow.SECTOR_MAP.get(ticker, "Unknown"),
        "strategy": "pocket_pivot_accumulation",
        "close": base._round(close, 4),
        "volume": base._round(volume, 2),
        "ret20": base._round(ret20, 6),
        "spy_ret20_on_signal": base._round(spy_ret20, 6),
        "rs20_vs_spy": base._round(rs20_vs_spy, 6),
        "signal_day_return": base._round(signal_ret, 6),
        "signal_day_spy_return": base._round(spy_signal_ret, 6),
        "signal_day_rs_vs_spy": base._round(signal_day_rs_vs_spy, 6),
        "pct_above_50d_ma": base._round(pct_above_50d_ma, 6),
        "avg_dollar_volume20": base._round(avg_dollar_volume20, 2),
        "pocket_pivot_accumulation_score": base._round(score, 6),
        "trade_enabled": False,
        "alters_orders": False,
        **pocket,
        **market,
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
    candidates: list[dict[str, Any]] = []
    source_tickers = 0
    raw_ticker_days = 0
    pocket_hit_count = 0
    for ticker in sorted(set(universe).intersection(snapshot).difference(EXCLUDED_TICKERS)):
        rows = ohlcv_shadow._series(snapshot, ticker)
        if not rows:
            continue
        source_tickers += 1
        for idx, row in enumerate(rows):
            date = ohlcv_shadow._date(row)
            if date not in dates:
                continue
            raw_ticker_days += 1
            if _pocket_pivot_on_signal_date(rows, idx) is not None:
                pocket_hit_count += 1
            candidate = _candidate_for_day(snapshot, ticker, rows, idx)
            if candidate is None:
                continue
            ab_entries = entries_by_date.get(candidate["date"], [])
            candidate["same_day_ab_entry_count"] = len(ab_entries)
            candidate["same_day_ab_overlap"] = bool(ab_entries)
            candidate["same_ticker_ab_overlap"] = any(
                trade.get("ticker") == candidate["ticker"] for trade in ab_entries
            )
            candidate["source_universe"] = "current_production_universe_ohlcv"
            candidates.append(candidate)

    label = next(
        (
            window_label
            for window_label, window_cfg in base.WINDOWS.items()
            if window_cfg is cfg
        ),
        str(cfg.get("start")),
    )
    POCKET_AUDIT[label] = {
        "raw_ticker_days_considered": raw_ticker_days,
        "source_tickers_considered": source_tickers,
        "raw_signal_day_pocket_pivot_hits": pocket_hit_count,
        "qqq_confirmed_liquid_trend_candidates": len(candidates),
        "candidate_days": len({row["date"] for row in candidates}),
        "unique_candidate_tickers": len({row["ticker"] for row in candidates}),
        "rule_version": RULE_VERSION,
    }
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["pocket_pivot_accumulation_score"]),
            -float(row["pocket_pivot_volume_ratio"]),
            -float(row["signal_day_rs_vs_spy"]),
            -float(row["avg_dollar_volume20"]),
            row["ticker"],
        )
    )
    return candidates


def _update_payload(payload: dict[str, Any]) -> dict[str, Any]:
    decision = (
        "promising_replay_only_pocket_pivot_accumulation_paper_sleeve"
        if payload["gate4"]["passed"]
        else "rejected_pocket_pivot_accumulation_paper_sleeve"
    )
    payload["status"] = decision
    payload["decision"] = decision
    payload["hypothesis"] = (
        "Daily pocket-pivot volume signatures in liquid production-universe names, "
        "when QQQ 20-day momentum leads SPY and price is above the 50-day moving "
        "average, may identify institutional accumulation earlier than the "
        "current core candidate stack."
    )
    payload["change_type"] = "pocket_pivot_accumulation_default_off_paper_sleeve"
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["trial_family"] = TRIAL_FAMILY
    payload["prior_trial_count"] = 1
    payload["mechanism_family"] = "free_ohlcv_daily_return_pattern_candidate_pool"
    payload["trial_variant_id"] = "pocket_pivot_accumulation_top1_qqq_confirmed_v1"
    payload["nearby_prior_experiments"] = [
        "exp-20260525-027",
        "exp-20260525-033",
        "exp-20260525-037",
        "exp-20260526-001",
        "exp-20260526-002",
        "exp-20260526-003",
        "exp-20260526-004",
        "exp-20260526-005",
        "exp-20260526-007",
        "exp-20260526-008",
    ]
    payload["multiple_testing_risk_bucket"] = "moderate"
    payload["new_evidence_type"] = (
        "current_three_window_next_open_slippage_adjusted_pocket_pivot_"
        "paper_sleeve_replay"
    )
    payload["parameters"]["source_universe"] = (
        "current get_universe() production universe names with canonical OHLCV snapshots"
    )
    payload["parameters"]["excluded_tickers"] = sorted(EXCLUDED_TICKERS)
    payload["parameters"]["shadow_entry_filters"] = {
        "signal_day_pocket_pivot": (
            "up day volume > max prior down-day volume in previous 10 trading days"
        ),
        "pocket_lookback_days": POCKET_LOOKBACK_DAYS,
        "market_confirmation": "QQQ 20d close-to-close return > SPY 20d return",
        "market_confirmation_lookback_days": MARKET_CONFIRM_LOOKBACK_DAYS,
        "min_close": MIN_CLOSE,
        "min_avg_dollar_volume20": MIN_AVG_DOLLAR_VOLUME_20,
        "close_above_50d_moving_average": True,
        "max_pct_above_50d_ma": MAX_PCT_ABOVE_50D_MA,
        "min_signal_day_rs_vs_spy": MIN_SIGNAL_DAY_RS_VS_SPY,
    }
    payload["parameters"]["selection_rank"] = [
        "signal_date",
        "pocket_pivot_accumulation_score desc",
        "pocket_pivot_volume_ratio desc",
        "signal_day_rs_vs_spy desc",
        "avg_dollar_volume20 desc",
        "ticker asc",
    ]
    payload["parameters"]["locked_variables"] = [
        "core universe membership",
        "core signal generation",
        "core ranking",
        "core position sizing",
        "core exits",
        "portfolio heat",
        "slot rules",
        "LLM/news replay",
        "watchlists",
        "live/default orders",
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
            "entry / candidate_pool: a signal-day pocket-pivot accumulation "
            "source may expand the default-off candidate pool using only free "
            "OHLCV and a production-visible QQQ-vs-SPY market confirmation."
        ),
        "2_history_check": {
            "exp-20260525-027": (
                "Prior pocket-pivot work was a support/metadata gate on exp-022 "
                "VCP candidates and failed as a replacement; it did not test "
                "standalone signal-day pocket-pivot candidates."
            ),
            "exp-20260525-037_and_exp-20260526-007": (
                "VCP top-2 and rank-notional profile are accepted default-off "
                "paper; this run does not alter VCP thresholds, ranks, or notional."
            ),
            "exp-20260526-001_to_005": (
                "Recent gap, smooth, undercut, and long-base OHLCV sources were "
                "rejected; this changes the source to a volume-accumulation "
                "pattern rather than retuning those sources."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Same three docs/backtesting.md windows; positive aggregate EV/PnL; "
            "3/3 EV-improved windows; no PnL-regressed window; >=30 paper trades "
            "across all 3 windows; drawdown drift <=0.5pp; survival >=5%; "
            "concentration inside guardrails."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260526_009_pocket_pivot_accumulation_paper_sleeve.py"
        ),
    }
    payload["gate2"]["runtime_fields"] = [
        "canonical OHLCV Date/Open/High/Low/Close/Volume rows",
        "candidate ticker prior 10 trading-day down-volume history",
        "candidate ticker 20-day average dollar volume",
        "candidate ticker 50-day moving average",
        "SPY OHLCV Close rows for signal-day and 20-day relative strength",
        "QQQ OHLCV Close rows for 20-day market confirmation",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["gate2"]["note"] = (
        "All candidate fields are derived from trailing or same-day OHLCV known "
        "after the signal-date close. Paper entry occurs only at the next open."
    )
    payload["gate3"]["candidate_pool_changed"] = True
    payload["pocket_pivot_audit"] = POCKET_AUDIT
    payload["why_not_other_changes"] = (
        "Skipped LLM soft-ranking and expectation-revision alpha because current "
        "records remain PIT/sample-limited. Skipped VCP threshold/top-N/pocket "
        "support retunes, state-surface/broad-market scalar work, opening-range, "
        "sector-leadership, gap/smooth, undercut, and long-base retreads because "
        "they are fresh accepted, rejected, or anti-repeat constrained. This "
        "tests a distinct signal-day volume-accumulation source."
    )
    payload["interpretation"] = (
        "The pocket-pivot accumulation sleeve cleared Gate 4 as a replay-only "
        "lead, but no production/shared policy was promoted."
        if payload["gate4"]["passed"]
        else (
            "The pocket-pivot accumulation sleeve did not clear Gate 4. Do not "
            "promote or retry nearby pocket-pivot scan, QQQ/SPY, 50-day MA, or "
            "volume thresholds on these frozen windows without forward paper "
            "rows or a materially different source-quality field."
        )
    )
    payload["next_evidence_needed"] = (
        "If revisited, require forward paper rows or an orthogonal production-"
        "visible catalyst/source field; do not just retune pocket-pivot volume "
        "or market-confirmation thresholds on the frozen sample."
    )
    payload["production_impact"]["promotion_requirement"] = (
        "A retained result would still require a shared default-off paper adapter, "
        "daily report exposure, forward replacement-value ledger, and parity tests "
        "before any live/default behavior changes."
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Candidates | Days | Tickers |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["pocket_pivot_audit"].get(label, {})
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | "
            "${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | "
            "{trades} | {candidates} | {days} | {tickers} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                candidates=audit.get("qqq_confirmed_liquid_trend_candidates"),
                days=audit.get("candidate_days"),
                tickers=audit.get("unique_candidate_tickers"),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Pocket-Pivot Accumulation Paper Sleeve",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            (
                "Single variable: a default-off paper sleeve admits at most one "
                "QQQ-confirmed liquid pocket-pivot accumulation candidate per day, "
                "enters at next open, and exits after ten trading days."
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
            json.dumps(payload["pocket_pivot_audit"], indent=2, sort_keys=True),
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
            "title": "Pocket-pivot accumulation paper sleeve",
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
                    "pocket_pivot_audit": payload["pocket_pivot_audit"],
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
