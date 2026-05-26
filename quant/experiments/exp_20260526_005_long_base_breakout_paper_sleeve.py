"""exp-20260526-005: long-base breakout paper sleeve.

This alpha search converts the old observed-only narrow shadow-universe idea
into the current docs/backtesting.md three-window before/after protocol. The
single variable is a default-off paper sleeve that admits at most one liquid
long-base 63-day breakout candidate per signal day, enters at the next open,
and exits after ten trading days.

Core signal generation, ranking, sizing, exits, LLM/news replay, watchlists,
and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
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


EXPERIMENT_ID = "exp-20260526-005"
STEM = "long_base_breakout_paper_sleeve"
TRIAL_FAMILY = "long_base_breakout_default_off_paper_sleeve"
CHANGED_VARIABLE = "long_base_breakout_daily_top1_next_open_10d_fixed_notional_sleeve_v1"
RULE_VERSION = "long_base_63d_breakout_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

HIGH_LOOKBACK_DAYS = 63
MIN_BASE_DAYS_WITHOUT_FRESH_HIGH = 30
MAX_RET20_BEFORE_BREAKOUT = 0.18
MIN_VOLUME_RATIO_20 = 1.10
MIN_CLOSE_LOCATION = 0.60
MIN_CLOSE = 8.0
MIN_AVG_DOLLAR_VOLUME_20 = 40_000_000.0
MIN_RS20_VS_SPY = -0.02
MAX_PAPER_TRADES_PER_DAY = 1
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30

EXCLUDED_TICKERS = {
    "GLD",
    "IAU",
    "IEF",
    "IWM",
    "QQQ",
    "SLV",
    "SPY",
    "TLT",
    "UUP",
    "USO",
    "XLE",
    "XLP",
    "XLU",
    "XLV",
}

LONG_BASE_AUDIT: "OrderedDict[str, dict[str, Any]]" = OrderedDict()


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


def _avg_volume(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx - lookback < 0:
        return None
    values = [ohlcv_shadow._value(rows[row_idx], "Volume") for row_idx in range(idx - lookback, idx)]
    if any(value is None for value in values):
        return None
    return sum(float(value) for value in values) / len(values)


def _high_prev(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx - lookback < 0:
        return None
    values = [ohlcv_shadow._value(rows[row_idx], "High") for row_idx in range(idx - lookback, idx)]
    if any(value is None for value in values):
        return None
    return max(float(value) for value in values)


def _fresh_high_days_before(rows: list[dict[str, Any]], lookback: int) -> list[int | None]:
    values: list[int | None] = []
    days_since: int | None = None
    for idx, row in enumerate(rows):
        values.append(days_since)
        high_prev = _high_prev(rows, idx, lookback)
        close = ohlcv_shadow._value(row, "Close")
        fresh = high_prev is not None and close is not None and close > high_prev
        if fresh:
            days_since = 0
        elif days_since is not None:
            days_since += 1
    return values


def _long_base_candidate(
    snapshot: dict[str, list[dict[str, Any]]],
    ticker: str,
    rows: list[dict[str, Any]],
    fresh_high_days_before: list[int | None],
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
    high63_prev = _high_prev(rows, idx, HIGH_LOOKBACK_DAYS)
    days_since_fresh_high = fresh_high_days_before[idx]
    avg_volume20 = _avg_volume(rows, idx, 20)
    avg_dollar_volume20 = _avg_dollar_volume(rows, idx, 20)
    ret20 = _close_return(rows, idx - 20, idx)
    ret63 = _close_return(rows, idx - HIGH_LOOKBACK_DAYS, idx)
    spy_ret20 = _close_return(spy_rows, spy_idx - 20, spy_idx)
    spy_ret63 = _close_return(spy_rows, spy_idx - HIGH_LOOKBACK_DAYS, spy_idx)
    if (
        open_ is None
        or high is None
        or low is None
        or close is None
        or volume is None
        or high63_prev is None
        or days_since_fresh_high is None
        or avg_volume20 is None
        or avg_dollar_volume20 is None
        or ret20 is None
        or ret63 is None
        or spy_ret20 is None
        or spy_ret63 is None
    ):
        return None
    if close < MIN_CLOSE or avg_dollar_volume20 < MIN_AVG_DOLLAR_VOLUME_20:
        return None
    if high <= low or close <= open_:
        return None
    if close <= high63_prev:
        return None
    if days_since_fresh_high < MIN_BASE_DAYS_WITHOUT_FRESH_HIGH:
        return None
    if ret20 > MAX_RET20_BEFORE_BREAKOUT:
        return None
    volume_ratio20 = volume / avg_volume20 if avg_volume20 else None
    close_location = (close - low) / (high - low)
    rs20_vs_spy = ret20 - spy_ret20
    rs63_vs_spy = ret63 - spy_ret63
    if volume_ratio20 is None or volume_ratio20 < MIN_VOLUME_RATIO_20:
        return None
    if close_location < MIN_CLOSE_LOCATION:
        return None
    if rs20_vs_spy < MIN_RS20_VS_SPY:
        return None

    breakout_pct = (close / high63_prev) - 1.0
    score = (
        min(days_since_fresh_high / 100.0, 1.0) * 0.35
        + max(rs20_vs_spy, 0.0) * 2.0
        + max(rs63_vs_spy, 0.0)
        + min(volume_ratio20 - MIN_VOLUME_RATIO_20, 2.0) * 0.12
        + close_location * 0.25
        + breakout_pct * 3.0
    )
    return {
        "ticker": ticker,
        "date": date,
        "sector": ohlcv_shadow.SECTOR_MAP.get(ticker, "Unknown"),
        "close": base._round(close, 4),
        "high63_prev": base._round(high63_prev, 4),
        "breakout_pct_above_high63_prev": base._round(breakout_pct, 6),
        "days_since_prior_fresh_high63": int(days_since_fresh_high),
        "ret20": base._round(ret20, 6),
        "ret63": base._round(ret63, 6),
        "spy_ret20": base._round(spy_ret20, 6),
        "spy_ret63": base._round(spy_ret63, 6),
        "rs20_vs_spy": base._round(rs20_vs_spy, 6),
        "rs63_vs_spy": base._round(rs63_vs_spy, 6),
        "volume_ratio20": base._round(volume_ratio20, 6),
        "close_location": base._round(close_location, 6),
        "avg_dollar_volume20": base._round(avg_dollar_volume20, 2),
        "long_base_breakout_score": base._round(score, 6),
        "long_base_breakout_rule_version": RULE_VERSION,
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
    del universe
    entries_by_date = ohlcv_shadow._baseline_entries(before_result)
    dates = {
        date
        for date in ohlcv_shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= date <= str(cfg["end"])
    }
    raw_ticker_days_considered = 0
    source_tickers = 0
    candidates: list[dict[str, Any]] = []
    for ticker in sorted(set(snapshot).difference(EXCLUDED_TICKERS)):
        if ticker == "SPY":
            continue
        rows = ohlcv_shadow._series(snapshot, ticker)
        if not rows:
            continue
        source_tickers += 1
        fresh_days = _fresh_high_days_before(rows, HIGH_LOOKBACK_DAYS)
        for idx, row in enumerate(rows):
            date = ohlcv_shadow._date(row)
            if date not in dates:
                continue
            raw_ticker_days_considered += 1
            candidate = _long_base_candidate(snapshot, ticker, rows, fresh_days, idx)
            if candidate is None:
                continue
            ab_entries = entries_by_date.get(candidate["date"], [])
            candidate["same_day_ab_entry_count"] = len(ab_entries)
            candidate["same_day_ab_overlap"] = bool(ab_entries)
            candidate["same_ticker_ab_overlap"] = any(
                trade.get("ticker") == candidate["ticker"] for trade in ab_entries
            )
            candidate["source_universe"] = "fixed_ohlcv_snapshot_liquid_tickers"
            candidates.append(candidate)

    label = next(
        (
            window_label
            for window_label, window_cfg in base.WINDOWS.items()
            if window_cfg is cfg
        ),
        str(cfg.get("start")),
    )
    LONG_BASE_AUDIT[label] = {
        "raw_ticker_days_considered": raw_ticker_days_considered,
        "source_tickers_considered": source_tickers,
        "long_base_breakout_candidates": len(candidates),
        "candidate_days": len({row["date"] for row in candidates}),
        "unique_candidate_tickers": len({row["ticker"] for row in candidates}),
        "rule_version": RULE_VERSION,
    }
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["long_base_breakout_score"]),
            -float(row["rs20_vs_spy"]),
            -float(row["volume_ratio20"]),
            row["ticker"],
        )
    )
    return candidates


def _update_payload(payload: dict[str, Any]) -> dict[str, Any]:
    decision = (
        "promising_replay_only_long_base_breakout_paper_sleeve"
        if payload["gate4"]["passed"]
        else "rejected_long_base_breakout_paper_sleeve"
    )
    payload["status"] = decision
    payload["decision"] = decision
    payload["hypothesis"] = (
        "Liquid stocks that close above a prior 63-day high after at least "
        "30 trading days without a fresh 63-day breakout may capture delayed "
        "institutional accumulation. A top-1 daily default-off paper sleeve "
        "should expand the candidate pool without adding arbitrary noise tickers."
    )
    payload["change_type"] = "long_base_breakout_default_off_paper_sleeve"
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["trial_family"] = TRIAL_FAMILY
    payload["prior_trial_count"] = 1
    payload["mechanism_family"] = "free_ohlcv_daily_return_pattern_candidate_pool"
    payload["trial_variant_id"] = "long_base_63d_breakout_top1_v1"
    payload["nearby_prior_experiments"] = [
        "exp-20260428-020",
        "exp-20260426-062",
        "exp-20260525-011",
        "exp-20260525-020",
        "exp-20260525-026",
        "exp-20260526-001",
        "exp-20260526-002",
        "exp-20260526-003",
        "exp-20260526-004",
    ]
    payload["multiple_testing_risk_bucket"] = "moderate"
    payload["new_evidence_type"] = (
        "current_three_window_next_open_slippage_adjusted_long_base_breakout_"
        "paper_sleeve_replay"
    )
    payload["parameters"]["source_universe"] = (
        "fixed OHLCV snapshot liquid tickers only; not a production watchlist change"
    )
    payload["parameters"]["excluded_tickers"] = sorted(EXCLUDED_TICKERS)
    payload["parameters"]["shadow_entry_filters"] = {
        "fresh_close_above_prior_63d_high": True,
        "min_trading_days_without_prior_fresh_high63": MIN_BASE_DAYS_WITHOUT_FRESH_HIGH,
        "max_ret20_before_breakout": MAX_RET20_BEFORE_BREAKOUT,
        "min_volume_ratio20": MIN_VOLUME_RATIO_20,
        "min_close_location": MIN_CLOSE_LOCATION,
        "min_close": MIN_CLOSE,
        "min_avg_dollar_volume20": MIN_AVG_DOLLAR_VOLUME_20,
        "min_rs20_vs_spy": MIN_RS20_VS_SPY,
        "requires_green_day": True,
    }
    payload["parameters"]["selection_rank"] = [
        "signal_date",
        "long_base_breakout_score desc",
        "rs20_vs_spy desc",
        "volume_ratio20 desc",
        "ticker asc",
    ]
    payload["parameters"]["locked_variables"] = [
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
            "entry / candidate_pool: long-base 63-day breakouts may identify "
            "delayed accumulation candidates. This fits the playbook's free "
            "OHLCV daily-return-pattern direction and avoids data-limited LLM "
            "soft-ranking."
        ),
        "2_history_check": {
            "exp-20260428-020": (
                "Observed-only narrow shadow universe scout using a similar 63-day "
                "base-breakout idea; it did not run current docs/backtesting.md "
                "next-open fixed-notional before/after Gate 4."
            ),
            "exp-20260426-062": (
                "Market-pullback resilience was observed-only and was later "
                "prechecked as negative fixed-notional PnL, so this run does not "
                "use that pullback-resilience condition."
            ),
            "recent_free_ohlcv_paper_sources": (
                "Opening-range, VCP, inside-day, gap-and-hold, smooth-path, and "
                "undercut/reclaim have fresh Gate 4 records; this source changes "
                "the base-breakout trigger, not those thresholds."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Same three docs/backtesting.md windows; positive aggregate EV/PnL; "
            "3/3 EV-improved windows; no PnL-regressed window; >=20 paper trades "
            "across all 3 windows; drawdown drift <=0.5pp; survival >=5%; "
            "concentration inside guardrails."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260526_005_long_base_breakout_paper_sleeve.py"
        ),
    }
    payload["gate2"]["runtime_fields"] = [
        "canonical OHLCV Date/Open/High/Low/Close/Volume rows",
        "SPY OHLCV Close rows for 20-day and 63-day relative strength",
        "derived prior 63-day high known at signal-date close",
        "derived prior fresh-high spacing known at signal-date close",
        "derived 20-day volume and dollar-volume fields",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["gate2"]["note"] = (
        "The sleeve uses only same-day and trailing daily OHLCV fields known at "
        "the signal-date close, then enters paper only at the next open. It "
        "does not ask LLM or production to infer hidden fields."
    )
    payload["gate3"]["candidate_pool_changed"] = True
    payload["long_base_breakout_audit"] = LONG_BASE_AUDIT
    payload["why_not_other_changes"] = (
        "Skipped LLM soft-ranking and expectation-residual leadership because "
        "recent logs show sparse usable data. Skipped state-surface capital "
        "scalar work, VCP threshold/top-N retunes, opening-range, sector "
        "leadership, inside-day, gap-and-hold, smooth-path, and undercut/reclaim "
        "retreads due fresh rejections or anti-repeat rules. This tests a "
        "distinct free-OHLCV long-base candidate source."
    )
    payload["interpretation"] = (
        "The long-base breakout sleeve cleared Gate 4 as a replay-only lead, "
        "but no production/shared policy was promoted."
        if payload["gate4"]["passed"]
        else (
            "The long-base breakout sleeve did not clear Gate 4. Do not promote "
            "or retry nearby 63-day base, volume, or close-location thresholds "
            "on these frozen windows without forward paper rows or an orthogonal "
            "event/source confirmation field."
        )
    )
    payload["rejection_reason"] = (
        None if payload["gate4"]["passed"] else payload.get("rejection_reason")
    )
    payload["next_evidence_needed"] = (
        "If revisited, require forward paper outcomes or a materially different "
        "production-visible event/source confirmation field. Do not just retune "
        "base length, volume ratio, or close-location thresholds on the frozen sample."
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
        audit = payload["long_base_breakout_audit"].get(label, {})
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
                candidates=audit.get("long_base_breakout_candidates"),
                days=audit.get("candidate_days"),
                tickers=audit.get("unique_candidate_tickers"),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Long-Base Breakout Paper Sleeve",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            (
                "Single variable: a default-off paper sleeve admits at most one "
                "liquid long-base 63-day breakout candidate per day, enters at "
                "next open, and exits after ten trading days."
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
            json.dumps(payload["long_base_breakout_audit"], indent=2, sort_keys=True),
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
            "title": "Long-base breakout paper sleeve",
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
                    "long_base_breakout_audit": payload["long_base_breakout_audit"],
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
