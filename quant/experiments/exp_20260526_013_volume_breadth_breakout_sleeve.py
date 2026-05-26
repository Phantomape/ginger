"""exp-20260526-013: volume-breadth confirmed breakout paper sleeve.

This alpha search tests one new free-OHLCV data edge: market-wide up-volume
participation on the signal date. The sleeve admits at most one liquid breakout
candidate per day only when a broad volume-breadth thrust is present, enters at
the next open, and exits after ten trading days.

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


EXPERIMENT_ID = "exp-20260526-013"
STEM = "volume_breadth_breakout_sleeve"
TRIAL_FAMILY = "volume_breadth_confirmed_breakout_default_off_paper_sleeve"
CHANGED_VARIABLE = "volume_breadth_thrust_confirmed_breakout_top1_v1"
RULE_VERSION = "volume_breadth_thrust_confirmed_breakout_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

BREAKOUT_LOOKBACK_DAYS = 20
MOVING_AVERAGE_DAYS = 50
VOLUME_LOOKBACK_DAYS = 20
MIN_DOLLAR_VOLUME = 40_000_000.0
MIN_CANDIDATE_VOLUME_RATIO_20 = 1.25
MIN_VOLUME_BREADTH_FRACTION = 0.12
MIN_MARKET_UP_FRACTION = 0.52
MIN_ABOVE_50D_FRACTION = 0.45
MIN_BREADTH_ELIGIBLE_TICKERS = 30
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

BREATH_AUDIT: "OrderedDict[str, dict[str, Any]]" = OrderedDict()


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
    values = [
        ohlcv_helper._value(row, "High")
        for row in rows[idx - days:idx]
    ]
    clean = [value for value in values if isinstance(value, (int, float))]
    if len(clean) < days:
        return None
    return max(clean)


def _prior_average(rows: list[dict[str, Any]], idx: int, days: int, key: str) -> float | None:
    if idx < days:
        return None
    values = [
        ohlcv_helper._value(row, key)
        for row in rows[idx - days:idx]
    ]
    clean = [value for value in values if isinstance(value, (int, float))]
    if len(clean) < days:
        return None
    return _avg(clean)


def _breadth_context_by_date(
    snapshot: dict[str, list[dict[str, Any]]],
    dates: list[str],
    universe: list[str],
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    tickers = sorted(set(universe).intersection(snapshot).difference(EXCLUDED_TICKERS))
    row_indices = {
        ticker: ohlcv_helper._row_index(ohlcv_helper._series(snapshot, ticker))
        for ticker in tickers
    }
    for date in dates:
        eligible = 0
        up_volume_spike = 0
        positive_day = 0
        above_50d = 0
        for ticker in tickers:
            rows = ohlcv_helper._series(snapshot, ticker)
            idx = row_indices[ticker].get(date)
            if idx is None or idx < MOVING_AVERAGE_DAYS:
                continue
            close = ohlcv_helper._value(rows[idx], "Close")
            prev_close = ohlcv_helper._value(rows[idx - 1], "Close")
            volume = ohlcv_helper._value(rows[idx], "Volume")
            avg_volume = _prior_average(rows, idx, VOLUME_LOOKBACK_DAYS, "Volume")
            ma50 = _prior_average(rows, idx, MOVING_AVERAGE_DAYS, "Close")
            if not close or not prev_close or not volume or not avg_volume or not ma50:
                continue
            eligible += 1
            volume_ratio = volume / avg_volume if avg_volume else 0.0
            if close > prev_close:
                positive_day += 1
            if close > ma50:
                above_50d += 1
            if close > prev_close and volume_ratio >= MIN_CANDIDATE_VOLUME_RATIO_20:
                up_volume_spike += 1

        volume_breadth = up_volume_spike / eligible if eligible else None
        market_up = positive_day / eligible if eligible else None
        above50 = above_50d / eligible if eligible else None
        passed = (
            eligible >= MIN_BREADTH_ELIGIBLE_TICKERS
            and volume_breadth is not None
            and market_up is not None
            and above50 is not None
            and volume_breadth >= MIN_VOLUME_BREADTH_FRACTION
            and market_up >= MIN_MARKET_UP_FRACTION
            and above50 >= MIN_ABOVE_50D_FRACTION
        )
        out[date] = {
            "eligible_ticker_count": eligible,
            "up_volume_spike_count": up_volume_spike,
            "positive_day_count": positive_day,
            "above_50d_count": above_50d,
            "volume_breadth_fraction": base._round(volume_breadth, 6),
            "market_up_fraction": base._round(market_up, 6),
            "above_50d_fraction": base._round(above50, 6),
            "volume_breadth_thrust_passed": passed,
            "rule_version": RULE_VERSION,
        }
    return out


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
    breadth_by_date = _breadth_context_by_date(snapshot, dates, universe)
    spy_rows = ohlcv_helper._series(snapshot, "SPY")
    spy_index = ohlcv_helper._row_index(spy_rows)
    candidates: list[dict[str, Any]] = []
    raw_breakouts = 0
    breadth_pass_dates = [
        date
        for date, context in breadth_by_date.items()
        if context["volume_breadth_thrust_passed"]
    ]

    for ticker in sorted(set(universe).intersection(snapshot).difference(EXCLUDED_TICKERS)):
        rows = ohlcv_helper._series(snapshot, ticker)
        idx_by_date = ohlcv_helper._row_index(rows)
        for date in dates:
            context = breadth_by_date.get(date) or {}
            if not context.get("volume_breadth_thrust_passed"):
                continue
            idx = idx_by_date.get(date)
            spy_idx = spy_index.get(date)
            if idx is None or spy_idx is None or idx < MOVING_AVERAGE_DAYS or spy_idx < 1:
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
            if volume_ratio is None or volume_ratio < MIN_CANDIDATE_VOLUME_RATIO_20:
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
            raw_breakouts += 1
            ab_entries = entries_by_date.get(date, [])
            score = (
                max(rs_vs_spy, 0.0) * 8.0
                + min(max(volume_ratio - 1.0, 0.0), 3.0)
                + max((close / prior_high) - 1.0, 0.0) * 3.0
                + max(float(context.get("volume_breadth_fraction") or 0.0), 0.0)
            )
            candidates.append(
                {
                    "date": date,
                    "ticker": ticker,
                    "sector": ohlcv_helper.SECTOR_MAP.get(ticker, "Unknown"),
                    "strategy": "volume_breadth_breakout",
                    "close": base._round(close, 4),
                    "breakout_above_prior_20d_high_pct": base._round((close / prior_high) - 1.0, 6),
                    "pct_above_50d_ma": base._round((close / ma50) - 1.0, 6),
                    "candidate_day_return": base._round(candidate_ret, 6),
                    "candidate_day_spy_return": base._round(spy_ret, 6),
                    "candidate_day_rs_vs_spy": base._round(rs_vs_spy, 6),
                    "volume_ratio_20": base._round(volume_ratio, 6),
                    "dollar_volume": base._round(dollar_volume, 2),
                    "volume_breadth_score": base._round(score, 6),
                    "same_day_ab_entry_count": len(ab_entries),
                    "same_day_ab_overlap": bool(ab_entries),
                    "same_ticker_ab_overlap": any(
                        trade.get("ticker") == ticker for trade in ab_entries
                    ),
                    "source_universe": "current_production_universe_ohlcv",
                    "volume_breadth_context": context,
                    "volume_breadth_rule_version": RULE_VERSION,
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
    BREATH_AUDIT[label] = {
        "candidate_source_tickers": len(
            set(universe).intersection(snapshot).difference(EXCLUDED_TICKERS)
        ),
        "trading_days": len(dates),
        "breadth_pass_days": len(breadth_pass_dates),
        "breadth_pass_day_fraction": base._round(
            len(breadth_pass_dates) / len(dates) if dates else None,
            6,
        ),
        "raw_liquid_breadth_breakout_hits": raw_breakouts,
        "candidate_days": len({row["date"] for row in candidates}),
        "unique_candidate_tickers": len({row["ticker"] for row in candidates}),
        "sample_breadth_context": {
            date: breadth_by_date[date] for date in breadth_pass_dates[:10]
        },
        "rule_version": RULE_VERSION,
    }
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["volume_breadth_score"]),
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
        "promising_replay_only_volume_breadth_breakout_sleeve"
        if gate4_passed
        else "rejected_volume_breadth_breakout_sleeve"
    )
    payload["status"] = decision
    payload["decision"] = decision
    payload["hypothesis"] = (
        "Breakout candidates should have higher replacement value when the "
        "signal date is supported by broad up-volume participation across the "
        "current OHLCV universe. The single tested variable is a default-off "
        "top-1 paper candidate source keyed on a market volume-breadth thrust."
    )
    payload["change_type"] = "volume_breadth_confirmed_breakout_default_off_paper_sleeve"
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["trial_family"] = TRIAL_FAMILY
    payload["prior_trial_count"] = 0
    payload["nearby_prior_experiments"] = [
        "exp-20260525-022",
        "exp-20260525-037",
        "exp-20260526-007",
        "exp-20260526-009",
        "exp-20260526-010",
        "exp-20260526-011",
    ]
    payload["multiple_testing_risk_bucket"] = "moderate"
    payload["new_evidence_type"] = "free_ohlcv_market_volume_breadth_internal_structure_field"
    payload["parameters"]["shadow_entry_filters"] = {
        "base_source": "new free-OHLCV market volume-breadth confirmed breakout source",
        "breakout_close_above_prior_n_day_high": BREAKOUT_LOOKBACK_DAYS,
        "close_above_prior_n_day_moving_average": MOVING_AVERAGE_DAYS,
        "min_candidate_day_dollar_volume": MIN_DOLLAR_VOLUME,
        "min_candidate_volume_ratio_20": MIN_CANDIDATE_VOLUME_RATIO_20,
        "min_candidate_day_rs_vs_spy": 0.0,
        "breadth_context": {
            "min_eligible_tickers": MIN_BREADTH_ELIGIBLE_TICKERS,
            "min_up_volume_spike_fraction": MIN_VOLUME_BREADTH_FRACTION,
            "min_market_up_fraction": MIN_MARKET_UP_FRACTION,
            "min_above_50d_fraction": MIN_ABOVE_50D_FRACTION,
            "volume_ratio_lookback_days": VOLUME_LOOKBACK_DAYS,
        },
    }
    payload["parameters"]["selection_rank"] = [
        "signal_date",
        "volume_breadth_score desc",
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
            "candidate_pool: a market-wide up-volume breadth thrust can identify "
            "higher-quality breakout candidates using only free OHLCV, improving "
            "candidate-pool replacement value without adding noisy tickers."
        ),
        "2_history_check": {
            "VCP_family": (
                "exp-20260525-022, exp-20260525-037, and exp-20260526-007 accepted "
                "QQQ-confirmed VCP top-2/rank-profile paper. This run does not "
                "retune VCP ATR, QQQ/SPY, top-N, or rank-notional."
            ),
            "recent_mechanical_sources": (
                "gap-and-hold, smooth momentum, undercut/reclaim, long-base, "
                "pocket-pivot, sector-leadership, and pullback-reclaim were "
                "rejected or anti-repeat constrained. This run tests a distinct "
                "market-internal volume-breadth field."
            ),
            "data_edge_playbook": (
                "docs/data_edge_context_layers.md lists breadth/internal "
                "structure and volume-spike breadth as useful free-data fields."
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
            "exp_20260526_013_volume_breadth_breakout_sleeve.py"
        ),
    }
    payload["gate2"]["runtime_fields"] = [
        "canonical OHLCV Date/Open/High/Low/Close/Volume rows",
        "candidate ticker trailing 20/50-day OHLCV features",
        "same-date universe volume-ratio, positive-day, and above-50d breadth counts",
        "SPY OHLCV Close rows for signal-day relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["gate2"]["note"] = (
        "All candidate and breadth fields are derived from trailing or same-day "
        "OHLCV known after the signal-date close. Paper entry occurs only at the "
        "next open; no LLM or hidden event field is used."
    )
    payload["gate3"]["candidate_pool_changed"] = True
    payload["gate3"]["note"] = (
        "No core filter or live entry rule was added. The default-off paper "
        "candidate pool uses a new breadth context source, so core survival is "
        "unchanged from the baseline replay."
    )
    payload["volume_breadth_audit"] = BREATH_AUDIT
    payload["why_not_other_changes"] = (
        "Skipped LLM soft-ranking, SEC semantics, and expectation-revision "
        "activation because current records remain PIT/sample-limited. Skipped "
        "VCP top-N/rank-profile/threshold retunes due explicit playbook freeze, "
        "and skipped recent price-pattern retreads. This tests one new free "
        "market-internal breadth field."
    )
    payload["interpretation"] = (
        "The volume-breadth confirmed breakout sleeve cleared Gate 4 as a "
        "replay-only lead, but no production/shared policy was promoted."
        if gate4_passed
        else (
            "The volume-breadth confirmed breakout sleeve did not clear Gate 4. "
            "Do not promote it or retry nearby volume-breadth thresholds on the "
            "same frozen windows without forward paper rows or an orthogonal "
            "source-quality field."
        )
    )
    payload["next_evidence_needed"] = (
        "If revisited, collect forward paper rows or add an orthogonal "
        "production-visible context field; do not just retune volume-breadth, "
        "breakout, or volume-ratio thresholds on the frozen sample."
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Candidates | Breadth days | Tickers |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["volume_breadth_audit"].get(label, {})
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
                candidates=audit.get("raw_liquid_breadth_breakout_hits"),
                days=audit.get("breadth_pass_days"),
                tickers=audit.get("unique_candidate_tickers"),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Volume-Breadth Confirmed Breakout Paper Sleeve",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            (
                "Single variable: a default-off paper sleeve admits at most one "
                "liquid breakout candidate per day only when same-date market "
                "up-volume breadth confirms broad participation."
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
            "## Breadth Audit",
            "",
            "```json",
            json.dumps(payload["volume_breadth_audit"], indent=2, sort_keys=True),
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
            "title": "Volume-breadth confirmed breakout paper sleeve",
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
                    "volume_breadth_audit": payload["volume_breadth_audit"],
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
