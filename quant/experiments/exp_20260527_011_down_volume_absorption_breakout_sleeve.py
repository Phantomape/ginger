"""exp-20260527-011: down-volume absorption breakout paper sleeve.

This alpha search tests one free-OHLCV candidate-pool edge: liquid breakouts
whose prior 10 trading days show upside volume dominance and limited downside
volume pressure. It is default-off paper only, enters at the next open, and
uses the existing ten-trading-day fixed-notional overlay measurement.

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

import exp_20260426_volatility_contraction_breakout_shadow as ohlcv_helper  # noqa: E402
import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as base  # noqa: E402


EXPERIMENT_ID = "exp-20260527-011"
STEM = "down_volume_absorption_breakout_sleeve"
TRIAL_FAMILY = "down_volume_absorption_breakout_default_off_paper_sleeve"
CHANGED_VARIABLE = "down_volume_absorption_breakout_top1_v1"
RULE_VERSION = "down_volume_absorption_breakout_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

BREAKOUT_LOOKBACK_DAYS = 20
MOVING_AVERAGE_DAYS = 50
VOLUME_LOOKBACK_DAYS = 20
ABSORPTION_LOOKBACK_DAYS = 10
MIN_ABSORPTION_VALID_DAYS = 8
MIN_DOWN_DAY_COUNT_10 = 2
MIN_GREEN_DAY_COUNT_10 = 4
MIN_UP_DOWN_VOLUME_RATIO_10 = 1.20
MAX_DOWN_VOLUME_SHARE_10 = 0.48
MIN_DOLLAR_VOLUME = 40_000_000.0
MIN_SIGNAL_VOLUME_RATIO_20 = 1.10
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

ABSORPTION_AUDIT: "OrderedDict[str, dict[str, Any]]" = OrderedDict()


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


def _absorption_context(rows: list[dict[str, Any]], idx: int) -> dict[str, Any] | None:
    if idx < ABSORPTION_LOOKBACK_DAYS + 1:
        return None

    valid_days = 0
    green_days = 0
    down_days = 0
    up_volume = 0.0
    down_volume = 0.0
    flat_volume = 0.0
    closes: list[float] = []
    highs: list[float] = []

    for day_idx in range(idx - ABSORPTION_LOOKBACK_DAYS, idx):
        close = ohlcv_helper._value(rows[day_idx], "Close")
        prev_close = ohlcv_helper._value(rows[day_idx - 1], "Close")
        high = ohlcv_helper._value(rows[day_idx], "High")
        volume = ohlcv_helper._value(rows[day_idx], "Volume")
        if close is None or prev_close is None or high is None or volume is None:
            continue
        valid_days += 1
        closes.append(float(close))
        highs.append(float(high))
        if close > prev_close:
            green_days += 1
            up_volume += float(volume)
        elif close < prev_close:
            down_days += 1
            down_volume += float(volume)
        else:
            flat_volume += float(volume)

    total_directional_volume = up_volume + down_volume
    if valid_days < MIN_ABSORPTION_VALID_DAYS or total_directional_volume <= 0:
        return None

    latest_close = closes[-1] if closes else None
    prior_high = max(highs) if highs else None
    down_volume_share = down_volume / total_directional_volume
    up_down_volume_ratio = up_volume / down_volume if down_volume else 9.99
    context = {
        "valid_days": valid_days,
        "green_day_count_10": green_days,
        "down_day_count_10": down_days,
        "flat_volume_10": base._round(flat_volume, 2),
        "up_volume_10": base._round(up_volume, 2),
        "down_volume_10": base._round(down_volume, 2),
        "down_volume_share_10": base._round(down_volume_share, 6),
        "up_down_volume_ratio_10": base._round(up_down_volume_ratio, 6),
        "prior_10d_close_vs_high": base._round((latest_close / prior_high) - 1.0, 6)
        if latest_close and prior_high
        else None,
        "rule_version": RULE_VERSION,
    }
    context["absorption_passed"] = (
        down_days >= MIN_DOWN_DAY_COUNT_10
        and green_days >= MIN_GREEN_DAY_COUNT_10
        and up_down_volume_ratio >= MIN_UP_DOWN_VOLUME_RATIO_10
        and down_volume_share <= MAX_DOWN_VOLUME_SHARE_10
    )
    return context


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
    raw_liquid_breakouts = 0
    absorption_checked = 0
    absorption_passed = 0

    for ticker in sorted(set(universe).intersection(snapshot).difference(EXCLUDED_TICKERS)):
        rows = ohlcv_helper._series(snapshot, ticker)
        idx_by_date = ohlcv_helper._row_index(rows)
        for date in dates:
            idx = idx_by_date.get(date)
            spy_idx = spy_index.get(date)
            min_idx = max(
                BREAKOUT_LOOKBACK_DAYS,
                MOVING_AVERAGE_DAYS,
                VOLUME_LOOKBACK_DAYS,
                ABSORPTION_LOOKBACK_DAYS + 1,
            )
            if idx is None or spy_idx is None or idx < min_idx or spy_idx < 1:
                continue

            close = ohlcv_helper._value(rows[idx], "Close")
            volume = ohlcv_helper._value(rows[idx], "Volume")
            if not close or not volume:
                continue
            dollar_volume = close * volume
            if dollar_volume < MIN_DOLLAR_VOLUME:
                continue

            prior_high = _prior_high(rows, idx, BREAKOUT_LOOKBACK_DAYS)
            ma50 = _prior_average(rows, idx, MOVING_AVERAGE_DAYS, "Close")
            avg_volume = _prior_average(rows, idx, VOLUME_LOOKBACK_DAYS, "Volume")
            if not prior_high or not ma50 or not avg_volume:
                continue
            volume_ratio = volume / avg_volume if avg_volume else None
            if volume_ratio is None or volume_ratio < MIN_SIGNAL_VOLUME_RATIO_20:
                continue
            if close <= prior_high or close <= ma50:
                continue

            candidate_ret = _close_return(rows, idx - 1, idx)
            spy_ret = _close_return(spy_rows, spy_idx - 1, spy_idx)
            if candidate_ret is None or spy_ret is None:
                continue
            rs_vs_spy = candidate_ret - spy_ret
            if rs_vs_spy <= 0:
                continue

            raw_liquid_breakouts += 1
            context = _absorption_context(rows, idx)
            if not context:
                continue
            absorption_checked += 1
            if not context.get("absorption_passed"):
                continue
            absorption_passed += 1

            ab_entries = entries_by_date.get(date, [])
            down_share = float(context.get("down_volume_share_10") or 0.0)
            up_down_ratio = float(context.get("up_down_volume_ratio_10") or 0.0)
            breakout_pct = (close / prior_high) - 1.0
            score = (
                max(rs_vs_spy, 0.0) * 8.0
                + min(max(volume_ratio - 1.0, 0.0), 3.0)
                + max(breakout_pct, 0.0) * 3.0
                + min(max(up_down_ratio - 1.0, 0.0), 3.0) * 0.5
                + max(MAX_DOWN_VOLUME_SHARE_10 - down_share, 0.0) * 2.0
            )
            candidates.append(
                {
                    "date": date,
                    "ticker": ticker,
                    "sector": ohlcv_helper.SECTOR_MAP.get(ticker, "Unknown"),
                    "strategy": "down_volume_absorption_breakout",
                    "close": base._round(close, 4),
                    "breakout_above_prior_20d_high_pct": base._round(breakout_pct, 6),
                    "pct_above_50d_ma": base._round((close / ma50) - 1.0, 6),
                    "candidate_day_return": base._round(candidate_ret, 6),
                    "candidate_day_spy_return": base._round(spy_ret, 6),
                    "candidate_day_rs_vs_spy": base._round(rs_vs_spy, 6),
                    "volume_ratio_20": base._round(volume_ratio, 6),
                    "dollar_volume": base._round(dollar_volume, 2),
                    "absorption_score": base._round(score, 6),
                    "same_day_ab_entry_count": len(ab_entries),
                    "same_day_ab_overlap": bool(ab_entries),
                    "same_ticker_ab_overlap": any(
                        trade.get("ticker") == ticker for trade in ab_entries
                    ),
                    "source_universe": "current_production_universe_ohlcv",
                    "down_volume_absorption_context": context,
                    "down_volume_absorption_rule_version": RULE_VERSION,
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
    ABSORPTION_AUDIT[label] = {
        "candidate_source_tickers": len(
            set(universe).intersection(snapshot).difference(EXCLUDED_TICKERS)
        ),
        "trading_days": len(dates),
        "raw_liquid_breakout_hits": raw_liquid_breakouts,
        "absorption_context_checked": absorption_checked,
        "absorption_context_passed": absorption_passed,
        "candidate_days": len({row["date"] for row in candidates}),
        "unique_candidate_tickers": len({row["ticker"] for row in candidates}),
        "rule_version": RULE_VERSION,
    }
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["absorption_score"]),
            -float(row["candidate_day_rs_vs_spy"]),
            -float(row["volume_ratio_20"]),
            -float(row["dollar_volume"]),
            row["ticker"],
        )
    )
    return candidates


def _update_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4_passed = bool(payload["gate4"]["passed"])
    decision = (
        "promising_replay_only_down_volume_absorption_breakout_sleeve"
        if gate4_passed
        else "rejected_down_volume_absorption_breakout_sleeve"
    )
    payload["status"] = decision
    payload["decision"] = decision
    payload["hypothesis"] = (
        "Breakout candidates should have higher replacement value when the "
        "prior 10 trading days show upside volume dominance and limited "
        "downside volume pressure. The single tested variable is a default-off "
        "top-1 paper candidate source keyed on down-volume absorption."
    )
    payload["change_type"] = "down_volume_absorption_breakout_default_off_paper_sleeve"
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["trial_family"] = TRIAL_FAMILY
    payload["prior_trial_count"] = 0
    payload["nearby_prior_experiments"] = [
        "exp-20260525-022",
        "exp-20260525-032",
        "exp-20260525-037",
        "exp-20260526-007",
        "exp-20260526-013",
        "exp-20260526-014",
        "exp-20260526-015",
        "exp-20260526-021",
    ]
    payload["multiple_testing_risk_bucket"] = "moderate_high"
    payload["new_evidence_type"] = "free_ohlcv_downside_volume_absorption_structure_field"
    payload["parameters"]["shadow_entry_filters"] = {
        "base_source": "new free-OHLCV down-volume absorption breakout source",
        "breakout_close_above_prior_n_day_high": BREAKOUT_LOOKBACK_DAYS,
        "close_above_prior_n_day_moving_average": MOVING_AVERAGE_DAYS,
        "min_candidate_day_dollar_volume": MIN_DOLLAR_VOLUME,
        "min_signal_volume_ratio_20": MIN_SIGNAL_VOLUME_RATIO_20,
        "min_candidate_day_rs_vs_spy": 0.0,
        "absorption_context": {
            "lookback_days": ABSORPTION_LOOKBACK_DAYS,
            "min_valid_days": MIN_ABSORPTION_VALID_DAYS,
            "min_down_day_count": MIN_DOWN_DAY_COUNT_10,
            "min_green_day_count": MIN_GREEN_DAY_COUNT_10,
            "min_up_down_volume_ratio": MIN_UP_DOWN_VOLUME_RATIO_10,
            "max_down_volume_share": MAX_DOWN_VOLUME_SHARE_10,
        },
    }
    payload["parameters"]["selection_rank"] = [
        "signal_date",
        "absorption_score desc",
        "candidate_day_rs_vs_spy desc",
        "volume_ratio_20 desc",
        "dollar_volume desc",
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
            "candidate_pool / entry: liquid breakouts with prior 10-day "
            "up-volume dominance may be higher-quality candidates than generic "
            "breakouts, using only free OHLCV and no noisy ticker additions."
        ),
        "2_history_check": {
            "VCP_family": (
                "Accepted VCP top-2/rank-profile sleeves already exist; this "
                "run does not retune ATR contraction, QQQ/SPY gates, top-N, "
                "rank profile, or notional scalar."
            ),
            "VBB_family": (
                "exp-20260526-013/014 tested same-day volume-breadth confirmed "
                "breakouts. This run does not gate on market breadth; it tests "
                "ticker-level prior down-volume absorption before breakout."
            ),
            "price_pattern_retreads": (
                "Gap-and-hold, smooth momentum path, undercut reclaim, long-base "
                "breakout, pocket pivot, sector breadth, and sector leadership "
                "variants were rejected or underpowered. This run uses a "
                "different trailing volume-structure field."
            ),
            "data_limited_lanes": (
                "Skipped LLM soft-ranking, Kova, and expectation lanes because "
                "recent records are observed-only or sample/PIT limited."
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
            "exp_20260527_011_down_volume_absorption_breakout_sleeve.py"
        ),
    }
    payload["gate2"]["runtime_fields"] = [
        "canonical OHLCV Date/Open/High/Low/Close/Volume rows",
        "candidate ticker trailing 10/20/50-day OHLCV features",
        "SPY OHLCV Close rows for signal-day relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["gate2"]["note"] = (
        "All candidate fields are derived from trailing or same-day OHLCV known "
        "after the signal-date close. Paper entry occurs only at the next open; "
        "no LLM, news, hidden event field, or future bar is used."
    )
    payload["gate3"]["candidate_pool_changed"] = True
    payload["gate3"]["note"] = (
        "No core filter or live entry rule was added. The default-off paper "
        "candidate pool uses a new ticker-level volume-structure source, so "
        "core survival is unchanged from the baseline replay."
    )
    payload["down_volume_absorption_audit"] = ABSORPTION_AUDIT
    payload["why_not_other_changes"] = (
        "Skipped LLM soft-ranking, SEC/Kova semantics, and expectation-revision "
        "activation because current records remain PIT/sample-limited. Skipped "
        "VCP/VBB threshold, top-N, and rank-notional retunes due playbook freeze "
        "and recent rejections. This tests one new free ticker-level OHLCV "
        "volume-structure field."
    )
    payload["interpretation"] = (
        "The down-volume absorption breakout sleeve cleared Gate 4 as a "
        "replay-only lead, but no production/shared policy was promoted."
        if gate4_passed
        else (
            "The down-volume absorption breakout sleeve did not clear Gate 4. "
            "Do not promote it or retry nearby absorption thresholds on the "
            "same frozen windows without forward paper rows or an orthogonal "
            "source-quality field."
        )
    )
    payload["next_evidence_needed"] = (
        "If revisited, collect forward paper rows or add an orthogonal "
        "production-visible context field; do not just retune absorption, "
        "breakout, or volume-ratio thresholds on the frozen sample."
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Candidates | Passes | Tickers |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["down_volume_absorption_audit"].get(label, {})
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | "
            "${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | "
            "{trades} | {candidates} | {passes} | {tickers} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                candidates=audit.get("raw_liquid_breakout_hits"),
                passes=audit.get("absorption_context_passed"),
                tickers=audit.get("unique_candidate_tickers"),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Down-Volume Absorption Breakout Paper Sleeve",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            (
                "Single variable: a default-off paper sleeve admits at most one "
                "liquid breakout candidate per day when the prior 10 trading "
                "days show upside volume dominance and limited downside volume."
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
            "## Absorption Audit",
            "",
            "```json",
            json.dumps(payload["down_volume_absorption_audit"], indent=2, sort_keys=True),
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
        "title": "Down-volume absorption breakout paper sleeve",
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
                    "down_volume_absorption_audit": payload["down_volume_absorption_audit"],
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
