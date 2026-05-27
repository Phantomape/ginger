"""exp-20260527-013: RS-line new-high paper sleeve.

Alpha search. This tests one free-OHLCV candidate-pool variable:
a ticker's SPY-relative strength line makes a fresh 60-trading-day high while
price is near, but not already through, its 20-day high. It is replay-only /
default-off paper and does not alter core entries, ranking, sizing, exits,
LLM/news, watchlists, or orders.
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

import exp_20260426_volatility_contraction_breakout_shadow as ohlcv_helper  # noqa: E402
import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as base  # noqa: E402


EXPERIMENT_ID = "exp-20260527-013"
STEM = "rs_line_new_high_paper_sleeve"
TRIAL_FAMILY = "relative_strength_line_new_high_default_off_paper_sleeve"
CHANGED_VARIABLE = "rs_line_new_high_top1_next_open_10d_fixed_notional_sleeve_v1"
RULE_VERSION = "rs_line_new_high_near_price_high_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

RS_LOOKBACK_DAYS = 60
PRICE_NEAR_HIGH_LOOKBACK_DAYS = 20
TREND_MA_DAYS = 50
RET20_DAYS = 20
RET60_DAYS = 60
VOLUME_LOOKBACK_DAYS = 20
MIN_AVG_DOLLAR_VOLUME_20 = 40_000_000.0
MIN_RET20_EXCESS_SPY = 0.03
MIN_RET60_EXCESS_SPY = 0.05
MIN_SIGNAL_DAY_RS_VS_SPY = 0.0
MIN_PRICE_VS_20D_HIGH = -0.08
MAX_PRICE_VS_20D_HIGH = 0.0
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

RS_LINE_AUDIT: "OrderedDict[str, dict[str, Any]]" = OrderedDict()


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
    base.shadow = ohlcv_helper
    for name in (
        "MIN_PRIOR_DAY_RETURN",
        "MIN_PRIOR_DAY_RS_VS_SPY",
        "MIN_OPEN_VS_PRIOR_CLOSE",
    ):
        if not hasattr(ohlcv_helper, name):
            setattr(ohlcv_helper, name, None)


def _avg(values: list[float | None]) -> float | None:
    clean = [float(value) for value in values if isinstance(value, (int, float))]
    if not clean:
        return None
    return sum(clean) / len(clean)


def _close_return(rows: list[dict[str, Any]], start_idx: int, end_idx: int) -> float | None:
    if start_idx < 0 or end_idx >= len(rows):
        return None
    start = ohlcv_helper._value(rows[start_idx], "Close")
    end = ohlcv_helper._value(rows[end_idx], "Close")
    if not start or end is None:
        return None
    return (end / start) - 1.0


def _prior_high(rows: list[dict[str, Any]], idx: int, days: int) -> float | None:
    if idx < days:
        return None
    values = [ohlcv_helper._value(row, "High") for row in rows[idx - days:idx]]
    clean = [value for value in values if isinstance(value, (int, float))]
    if len(clean) < days:
        return None
    return max(clean)


def _prior_average(rows: list[dict[str, Any]], idx: int, days: int, key: str) -> float | None:
    if idx < days:
        return None
    values = [ohlcv_helper._value(row, key) for row in rows[idx - days:idx]]
    clean = [value for value in values if isinstance(value, (int, float))]
    if len(clean) < days:
        return None
    return _avg(clean)


def _rs_ratio(
    rows: list[dict[str, Any]],
    spy_rows: list[dict[str, Any]],
    idx: int,
    spy_idx: int,
) -> float | None:
    close = ohlcv_helper._value(rows[idx], "Close")
    spy_close = ohlcv_helper._value(spy_rows[spy_idx], "Close")
    if not close or not spy_close:
        return None
    return float(close) / float(spy_close)


def _prior_rs_high(
    rows: list[dict[str, Any]],
    spy_rows: list[dict[str, Any]],
    idx: int,
    spy_idx: int,
    days: int,
) -> float | None:
    if idx < days or spy_idx < days:
        return None
    ratios: list[float] = []
    for offset in range(days, 0, -1):
        ratio = _rs_ratio(rows, spy_rows, idx - offset, spy_idx - offset)
        if ratio is None:
            return None
        ratios.append(ratio)
    return max(ratios) if ratios else None


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> list[dict[str, Any]]:
    entries_by_date = ohlcv_helper._baseline_entries(before_result)
    dates = [
        date
        for date in ohlcv_helper._trading_dates(snapshot)
        if str(cfg["start"]) <= date <= str(cfg["end"])
    ]
    spy_rows = ohlcv_helper._series(snapshot, "SPY")
    spy_index = ohlcv_helper._row_index(spy_rows)
    candidates: list[dict[str, Any]] = []
    checked = 0
    rs_new_high = 0
    trend_passed = 0
    near_price_high_passed = 0

    for ticker in sorted(set(universe).intersection(snapshot).difference(EXCLUDED_TICKERS)):
        sector = ohlcv_helper.SECTOR_MAP.get(ticker, "Unknown")
        if sector in {"Unknown", "ETF", "Commodities"}:
            continue
        rows = ohlcv_helper._series(snapshot, ticker)
        idx_by_date = ohlcv_helper._row_index(rows)
        for date in dates:
            idx = idx_by_date.get(date)
            spy_idx = spy_index.get(date)
            min_idx = max(
                RS_LOOKBACK_DAYS,
                PRICE_NEAR_HIGH_LOOKBACK_DAYS,
                TREND_MA_DAYS,
                RET60_DAYS,
                VOLUME_LOOKBACK_DAYS,
            )
            if idx is None or spy_idx is None or idx < min_idx or spy_idx < min_idx:
                continue
            close = ohlcv_helper._value(rows[idx], "Close")
            volume = ohlcv_helper._value(rows[idx], "Volume")
            if not close or not volume:
                continue
            checked += 1

            ratio = _rs_ratio(rows, spy_rows, idx, spy_idx)
            prior_rs_high = _prior_rs_high(rows, spy_rows, idx, spy_idx, RS_LOOKBACK_DAYS)
            if ratio is None or prior_rs_high is None or ratio <= prior_rs_high:
                continue
            rs_new_high += 1

            avg_volume = _prior_average(rows, idx, VOLUME_LOOKBACK_DAYS, "Volume")
            avg_close = _prior_average(rows, idx, VOLUME_LOOKBACK_DAYS, "Close")
            ma50 = _prior_average(rows, idx, TREND_MA_DAYS, "Close")
            prior_20d_high = _prior_high(rows, idx, PRICE_NEAR_HIGH_LOOKBACK_DAYS)
            if not avg_volume or not avg_close or not ma50 or not prior_20d_high:
                continue
            avg_dollar_volume = avg_volume * avg_close
            if avg_dollar_volume < MIN_AVG_DOLLAR_VOLUME_20 or close <= ma50:
                continue
            trend_passed += 1

            price_vs_20d_high = (close / prior_20d_high) - 1.0
            if (
                price_vs_20d_high < MIN_PRICE_VS_20D_HIGH
                or price_vs_20d_high > MAX_PRICE_VS_20D_HIGH
            ):
                continue
            near_price_high_passed += 1

            candidate_ret = _close_return(rows, idx - 1, idx)
            spy_ret = _close_return(spy_rows, spy_idx - 1, spy_idx)
            ret20 = _close_return(rows, idx - RET20_DAYS, idx)
            spy_ret20 = _close_return(spy_rows, spy_idx - RET20_DAYS, spy_idx)
            ret60 = _close_return(rows, idx - RET60_DAYS, idx)
            spy_ret60 = _close_return(spy_rows, spy_idx - RET60_DAYS, spy_idx)
            if (
                candidate_ret is None
                or spy_ret is None
                or ret20 is None
                or spy_ret20 is None
                or ret60 is None
                or spy_ret60 is None
            ):
                continue
            signal_day_rs = candidate_ret - spy_ret
            ret20_excess = ret20 - spy_ret20
            ret60_excess = ret60 - spy_ret60
            if (
                signal_day_rs <= MIN_SIGNAL_DAY_RS_VS_SPY
                or ret20_excess < MIN_RET20_EXCESS_SPY
                or ret60_excess < MIN_RET60_EXCESS_SPY
            ):
                continue

            ab_entries = entries_by_date.get(date, [])
            rs_breakout_margin = (ratio / prior_rs_high) - 1.0
            volume_ratio = (
                float(volume) / float(avg_volume)
                if avg_volume and avg_volume > 0
                else None
            )
            score = (
                max(ret20_excess, 0.0) * 4.0
                + max(ret60_excess, 0.0) * 1.5
                + max(signal_day_rs, 0.0) * 6.0
                + max(rs_breakout_margin, 0.0) * 30.0
                + max(price_vs_20d_high - MIN_PRICE_VS_20D_HIGH, 0.0) * 2.0
                + min(max((volume_ratio or 1.0) - 1.0, 0.0), 2.0) * 0.25
            )
            candidates.append(
                {
                    "date": date,
                    "ticker": ticker,
                    "sector": sector,
                    "strategy": "rs_line_new_high",
                    "close": base._round(close, 4),
                    "avg_dollar_volume_20": base._round(avg_dollar_volume, 2),
                    "volume_ratio_20": base._round(volume_ratio, 6),
                    "rs_line_ratio": base._round(ratio, 8),
                    "prior_60d_rs_line_high": base._round(prior_rs_high, 8),
                    "rs_line_breakout_margin": base._round(rs_breakout_margin, 6),
                    "price_vs_prior_20d_high": base._round(price_vs_20d_high, 6),
                    "pct_above_50d_ma": base._round((close / ma50) - 1.0, 6),
                    "candidate_day_return": base._round(candidate_ret, 6),
                    "candidate_day_spy_return": base._round(spy_ret, 6),
                    "candidate_day_rs_vs_spy": base._round(signal_day_rs, 6),
                    "ret20": base._round(ret20, 6),
                    "spy_ret20": base._round(spy_ret20, 6),
                    "ret20_excess_spy": base._round(ret20_excess, 6),
                    "ret60": base._round(ret60, 6),
                    "spy_ret60": base._round(spy_ret60, 6),
                    "ret60_excess_spy": base._round(ret60_excess, 6),
                    "rs_line_new_high_score": base._round(score, 6),
                    "same_day_ab_entry_count": len(ab_entries),
                    "same_day_ab_overlap": bool(ab_entries),
                    "same_ticker_ab_overlap": any(
                        trade.get("ticker") == ticker for trade in ab_entries
                    ),
                    "source_universe": "current_production_universe_ohlcv",
                    "rs_line_new_high_rule_version": RULE_VERSION,
                    "known_at": "after_signal_date_close_before_next_open_paper_entry",
                    "trade_enabled": False,
                    "alters_orders": False,
                }
            )

    label = next(
        (
            window_label
            for window_label, window_cfg in base.WINDOWS.items()
            if window_cfg is cfg
        ),
        str(cfg.get("start")),
    )
    RS_LINE_AUDIT[label] = {
        "candidate_source_tickers": len(
            set(universe).intersection(snapshot).difference(EXCLUDED_TICKERS)
        ),
        "trading_days": len(dates),
        "context_checked": checked,
        "rs_line_new_high_hits": rs_new_high,
        "trend_passed": trend_passed,
        "near_price_high_passed": near_price_high_passed,
        "raw_rs_line_candidates": len(candidates),
        "candidate_days": len({row["date"] for row in candidates}),
        "unique_candidate_tickers": len({row["ticker"] for row in candidates}),
        "rule_version": RULE_VERSION,
    }
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["rs_line_new_high_score"]),
            -float(row["ret20_excess_spy"]),
            -float(row["candidate_day_rs_vs_spy"]),
            -float(row["avg_dollar_volume_20"]),
            row["ticker"],
        )
    )
    return candidates


def _update_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4_passed = bool(payload["gate4"]["passed"])
    decision = (
        "promising_replay_only_rs_line_new_high_paper_sleeve"
        if gate4_passed
        else "rejected_rs_line_new_high_paper_sleeve"
    )
    payload["status"] = decision
    payload["decision"] = decision
    payload["hypothesis"] = (
        "Stocks whose SPY-relative strength line reaches a fresh 60-day high "
        "before price itself breaks a 20-day high may be higher-quality "
        "candidate-pool additions than generic breakout retreads. The single "
        "tested variable is a default-off top-1 paper source using only free "
        "OHLCV known at the signal-date close."
    )
    payload["change_type"] = "relative_strength_line_new_high_default_off_paper_sleeve"
    payload["mechanism_family"] = "free_ohlcv_relative_strength_candidate_pool"
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["trial_family"] = TRIAL_FAMILY
    payload["trial_variant_id"] = "rs_line_new_high_near_price_high_top1_v1"
    payload["prior_trial_count"] = 0
    payload["nearby_prior_experiments"] = [
        "exp-20260525-020",
        "exp-20260525-022",
        "exp-20260525-037",
        "exp-20260526-001",
        "exp-20260526-003",
        "exp-20260526-005",
        "exp-20260526-011",
        "exp-20260526-013",
        "exp-20260526-014",
        "exp-20260527-011",
        "exp-20260527-012",
    ]
    payload["multiple_testing_risk_bucket"] = "moderate"
    payload["new_evidence_type"] = "free_ohlcv_relative_strength_line_new_high_field"
    payload["parameters"]["shadow_entry_filters"] = {
        "base_source": "new free-OHLCV RS-line new-high candidate source",
        "rs_line_lookback_days": RS_LOOKBACK_DAYS,
        "price_near_high_lookback_days": PRICE_NEAR_HIGH_LOOKBACK_DAYS,
        "trend_ma_days": TREND_MA_DAYS,
        "min_avg_dollar_volume_20": MIN_AVG_DOLLAR_VOLUME_20,
        "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
        "min_ret60_excess_spy": MIN_RET60_EXCESS_SPY,
        "min_signal_day_rs_vs_spy": MIN_SIGNAL_DAY_RS_VS_SPY,
        "min_price_vs_prior_20d_high": MIN_PRICE_VS_20D_HIGH,
        "max_price_vs_prior_20d_high": MAX_PRICE_VS_20D_HIGH,
    }
    payload["parameters"]["selection_rank"] = [
        "signal_date",
        "rs_line_new_high_score desc",
        "ret20_excess_spy desc",
        "candidate_day_rs_vs_spy desc",
        "avg_dollar_volume_20 desc",
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
        "accepted VCP paper adapter",
        "accepted volume-breadth breakout paper adapter",
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
            "candidate_pool / entry: RS-line new highs can identify leaders "
            "before price breakout, using free OHLCV and a non-noise production "
            "universe. This fits the playbook's preference for new fields over "
            "nearby VCP/VBB/scalar retunes."
        ),
        "2_history_check": {
            "accepted_candidate_pool_leads": (
                "VCP+QQQ top-2 and VBB top-1 are accepted default-off paper "
                "adapters. This run does not retune their thresholds, top-N, "
                "rank profiles, or notional."
            ),
            "recent_rejections": (
                "Gap/smooth/undercut/long-base/pocket-pivot/pullback-reclaim, "
                "down-volume absorption, and sector-leadership confirmations "
                "were rejected or anti-repeat constrained. This tests a distinct "
                "relative-strength-line field."
            ),
            "data_limited_lanes": (
                "LLM soft-ranking, Kova, and expectation revision remain sparse "
                "or PIT-limited for immediate promotion-grade alpha."
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
            "exp_20260527_013_rs_line_new_high_paper_sleeve.py"
        ),
    }
    payload["gate2"]["runtime_fields"] = [
        "canonical OHLCV Date/Open/High/Low/Close/Volume rows",
        "SPY OHLCV Close rows for relative-strength-line ratio",
        "candidate ticker trailing 20/50/60-day OHLCV features",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["gate2"]["note"] = (
        "All RS-line, return, trend, liquidity, and near-high fields are "
        "derived from trailing or same-day OHLCV known after the signal-date "
        "close. Paper entry occurs only at the next open; no LLM, news, hidden "
        "event field, or future bar is used."
    )
    payload["gate3"]["candidate_pool_changed"] = True
    payload["gate3"]["note"] = (
        "No core filter or live entry rule was added. The default-off paper "
        "candidate pool is additive research, so core survival is unchanged."
    )
    payload["rs_line_new_high_audit"] = RS_LINE_AUDIT
    payload["why_not_other_changes"] = (
        "Skipped LLM soft-ranking, SEC/Kova semantics, and expectation-revision "
        "activation because recent records remain PIT/sample-limited. Skipped "
        "VCP/VBB threshold, top-N, rank-notional, and source-capacity retunes "
        "due playbook freezes. This tests one new free OHLCV relative-strength "
        "field in a default-off paper boundary."
    )
    payload["interpretation"] = (
        "The RS-line new-high paper sleeve cleared Gate 4 as a replay-only lead, "
        "but no production/shared policy was promoted."
        if gate4_passed
        else (
            "The RS-line new-high paper sleeve did not clear Gate 4. Do not "
            "promote it or retry nearby RS-line lookback/near-high thresholds "
            "on the same frozen windows without forward rows or an orthogonal "
            "source-quality field."
        )
    )
    payload["next_evidence_needed"] = (
        "If revisited, require forward paper rows or a materially orthogonal "
        "production-visible source-quality field; do not just retune RS-line, "
        "near-high, or return thresholds on the frozen sample."
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
        base._repo_rel(DOC_TICKET_JSON),
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
        audit = payload["rs_line_new_high_audit"].get(label, {})
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
                candidates=audit.get("raw_rs_line_candidates"),
                days=audit.get("candidate_days"),
                tickers=audit.get("unique_candidate_tickers"),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} RS-Line New-High Paper Sleeve",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            (
                "Single variable: a default-off paper sleeve admits at most one "
                "liquid candidate per day when its SPY-relative strength line "
                "makes a fresh 60-day high while price is near but not through "
                "its 20-day high."
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
            "## RS-Line Audit",
            "",
            "```json",
            json.dumps(payload["rs_line_new_high_audit"], indent=2, sort_keys=True),
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
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "title": "RS-line new-high paper sleeve",
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": base._repo_rel(ARTIFACT_MD),
        "json": base._repo_rel(OUT_JSON),
        "summary": payload["interpretation"],
    }
    base._write_json(OUT_JSON, payload)
    base._write_json(LOG_JSON, payload)
    base._write_json(TICKET_JSON, ticket)
    base._write_json(DOC_TICKET_JSON, ticket)
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
                    "rs_line_new_high_audit": payload["rs_line_new_high_audit"],
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
