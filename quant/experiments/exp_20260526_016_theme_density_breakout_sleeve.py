"""exp-20260526-016: theme-density confirmed breakout paper sleeve.

This alpha search tests one new free-OHLCV candidate-pool field: same-theme
participation and SPY-relative theme strength on the signal date. It is
replay-only and default-off paper. Core entries, exits, ranking, sizing,
LLM/news, watchlists, and live/default orders are unchanged.
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
from daily_context_archive import THEME_TICKERS  # noqa: E402


EXPERIMENT_ID = "exp-20260526-016"
STEM = "theme_density_breakout_sleeve"
TRIAL_FAMILY = "theme_density_confirmed_breakout_default_off_paper_sleeve"
CHANGED_VARIABLE = "theme_density_confirmed_breakout_top1_v1"
RULE_VERSION = "theme_density_confirmed_breakout_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

BREAKOUT_LOOKBACK_DAYS = 20
MOVING_AVERAGE_DAYS = 50
VOLUME_LOOKBACK_DAYS = 20
THEME_RETURN_LOOKBACK_DAYS = 20
MIN_DOLLAR_VOLUME = 40_000_000.0
MIN_CANDIDATE_VOLUME_RATIO_20 = 1.20
MIN_THEME_ELIGIBLE_TICKERS = 4
MIN_THEME_POSITIVE_RET20_FRACTION = 0.60
MIN_THEME_ABOVE_50D_FRACTION = 0.50
MIN_THEME_BREAKOUT_COUNT = 2
MIN_THEME_AVG_RET20_EXCESS_SPY = 0.0
MAX_PAPER_TRADES_PER_DAY = 1
MIN_TARGET_TRADES = 20
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

THEME_DENSITY_AUDIT: "OrderedDict[str, dict[str, Any]]" = OrderedDict()


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


def _ticker_themes(ticker: str) -> list[str]:
    ticker = str(ticker or "").upper()
    return [
        theme
        for theme, tickers in sorted(THEME_TICKERS.items())
        if ticker in {str(row).upper() for row in tickers}
    ]


def _theme_groups(universe: list[str], snapshot: dict[str, list[dict[str, Any]]]) -> dict[str, list[str]]:
    allowed = set(universe).intersection(snapshot).difference(EXCLUDED_TICKERS)
    out: dict[str, list[str]] = {}
    for theme, tickers in sorted(THEME_TICKERS.items()):
        members = sorted({str(ticker).upper() for ticker in tickers}.intersection(allowed))
        if members:
            out[theme] = members
    return out


def _theme_contexts_by_date(
    snapshot: dict[str, list[dict[str, Any]]],
    dates: list[str],
    universe: list[str],
) -> dict[str, dict[str, dict[str, Any]]]:
    groups = _theme_groups(universe, snapshot)
    spy_rows = ohlcv_helper._series(snapshot, "SPY")
    spy_index = ohlcv_helper._row_index(spy_rows)
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for date in dates:
        spy_idx = spy_index.get(date)
        spy_ret20 = (
            _close_return(spy_rows, spy_idx - THEME_RETURN_LOOKBACK_DAYS, spy_idx)
            if spy_idx is not None
            else None
        )
        out[date] = {}
        for theme, tickers in groups.items():
            eligible = 0
            positive_ret20 = 0
            above_50d = 0
            breakout_count = 0
            ret20_values: list[float | None] = []
            for ticker in tickers:
                rows = ohlcv_helper._series(snapshot, ticker)
                idx = ohlcv_helper._row_index(rows).get(date)
                if idx is None or idx < MOVING_AVERAGE_DAYS:
                    continue
                close = ohlcv_helper._value(rows[idx], "Close")
                ma50 = _prior_average(rows, idx, MOVING_AVERAGE_DAYS, "Close")
                prior_high = _prior_high(rows, idx, BREAKOUT_LOOKBACK_DAYS)
                ret20 = _close_return(rows, idx - THEME_RETURN_LOOKBACK_DAYS, idx)
                if close is None or ma50 is None or prior_high is None or ret20 is None:
                    continue
                eligible += 1
                ret20_values.append(ret20)
                if ret20 > 0:
                    positive_ret20 += 1
                if close > ma50:
                    above_50d += 1
                if close > prior_high:
                    breakout_count += 1

            avg_ret20 = _avg(ret20_values)
            avg_ret20_excess_spy = (
                avg_ret20 - spy_ret20
                if avg_ret20 is not None and spy_ret20 is not None
                else None
            )
            positive_fraction = positive_ret20 / eligible if eligible else None
            above_50d_fraction = above_50d / eligible if eligible else None
            breakout_fraction = breakout_count / eligible if eligible else None
            passed = (
                eligible >= MIN_THEME_ELIGIBLE_TICKERS
                and positive_fraction is not None
                and above_50d_fraction is not None
                and avg_ret20_excess_spy is not None
                and positive_fraction >= MIN_THEME_POSITIVE_RET20_FRACTION
                and above_50d_fraction >= MIN_THEME_ABOVE_50D_FRACTION
                and breakout_count >= MIN_THEME_BREAKOUT_COUNT
                and avg_ret20_excess_spy >= MIN_THEME_AVG_RET20_EXCESS_SPY
            )
            out[date][theme] = {
                "asof_date": date,
                "theme": theme,
                "members": tickers,
                "eligible_ticker_count": eligible,
                "positive_ret20_count": positive_ret20,
                "above_50d_count": above_50d,
                "breakout_count": breakout_count,
                "theme_positive_ret20_fraction": base._round(positive_fraction, 6),
                "theme_above_50d_fraction": base._round(above_50d_fraction, 6),
                "theme_breakout_fraction": base._round(breakout_fraction, 6),
                "theme_avg_ret20": base._round(avg_ret20, 6),
                "spy_ret20": base._round(spy_ret20, 6),
                "theme_avg_ret20_excess_spy": base._round(avg_ret20_excess_spy, 6),
                "passed": passed,
                "status": "passed" if passed else "failed",
                "rule_version": RULE_VERSION,
                "known_at": "after_signal_date_close_before_next_open_paper_entry",
                "trade_enabled": False,
                "alters_orders": False,
            }
    return out


def _best_theme_context(ticker: str, contexts: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    for theme in _ticker_themes(ticker):
        context = contexts.get(theme)
        if not context or context.get("passed") is not True:
            continue
        if best is None:
            best = context
            continue
        current_score = (
            float(context.get("theme_avg_ret20_excess_spy") or 0.0),
            float(context.get("theme_breakout_fraction") or 0.0),
            float(context.get("theme_positive_ret20_fraction") or 0.0),
            str(context.get("theme") or ""),
        )
        best_score = (
            float(best.get("theme_avg_ret20_excess_spy") or 0.0),
            float(best.get("theme_breakout_fraction") or 0.0),
            float(best.get("theme_positive_ret20_fraction") or 0.0),
            str(best.get("theme") or ""),
        )
        if current_score > best_score:
            best = context
    return best


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
    theme_contexts = _theme_contexts_by_date(snapshot, dates, universe)
    spy_rows = ohlcv_helper._series(snapshot, "SPY")
    spy_index = ohlcv_helper._row_index(spy_rows)
    candidates: list[dict[str, Any]] = []
    raw_breakouts = 0
    theme_pass_dates = set()
    theme_pass_instances = 0

    for ticker in sorted(set(universe).intersection(snapshot).difference(EXCLUDED_TICKERS)):
        ticker_themes = _ticker_themes(ticker)
        if not ticker_themes:
            continue
        rows = ohlcv_helper._series(snapshot, ticker)
        idx_by_date = ohlcv_helper._row_index(rows)
        for date in dates:
            theme_context = _best_theme_context(ticker, theme_contexts.get(date, {}))
            if not theme_context:
                continue
            theme_pass_dates.add(date)
            theme_pass_instances += 1
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
                max(rs_vs_spy, 0.0) * 7.0
                + min(max(volume_ratio - 1.0, 0.0), 3.0)
                + max((close / prior_high) - 1.0, 0.0) * 3.0
                + float(theme_context.get("theme_avg_ret20_excess_spy") or 0.0) * 2.0
                + float(theme_context.get("theme_breakout_fraction") or 0.0)
                + float(theme_context.get("theme_positive_ret20_fraction") or 0.0) * 0.5
            )
            candidates.append(
                {
                    "date": date,
                    "ticker": ticker,
                    "sector": ohlcv_helper.SECTOR_MAP.get(ticker, "Unknown"),
                    "themes": ticker_themes,
                    "selected_theme": theme_context.get("theme"),
                    "strategy": "theme_density_breakout",
                    "close": base._round(close, 4),
                    "breakout_above_prior_20d_high_pct": base._round((close / prior_high) - 1.0, 6),
                    "pct_above_50d_ma": base._round((close / ma50) - 1.0, 6),
                    "candidate_day_return": base._round(candidate_ret, 6),
                    "candidate_day_spy_return": base._round(spy_ret, 6),
                    "candidate_day_rs_vs_spy": base._round(rs_vs_spy, 6),
                    "volume_ratio_20": base._round(volume_ratio, 6),
                    "dollar_volume": base._round(dollar_volume, 2),
                    "theme_density_score": base._round(score, 6),
                    "theme_density_context": theme_context,
                    "same_day_ab_entry_count": len(ab_entries),
                    "same_day_ab_overlap": bool(ab_entries),
                    "same_ticker_ab_overlap": any(
                        trade.get("ticker") == ticker for trade in ab_entries
                    ),
                    "source_universe": "current_production_universe_ohlcv",
                    "theme_density_rule_version": RULE_VERSION,
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
    theme_pass_counts: dict[str, int] = {}
    for contexts in theme_contexts.values():
        for theme, context in contexts.items():
            if context.get("passed") is True:
                theme_pass_counts[theme] = theme_pass_counts.get(theme, 0) + 1
    THEME_DENSITY_AUDIT[label] = {
        "candidate_source_tickers": len(
            set(universe).intersection(snapshot).difference(EXCLUDED_TICKERS)
        ),
        "theme_groups": _theme_groups(universe, snapshot),
        "trading_days": len(dates),
        "theme_pass_days": len(theme_pass_dates),
        "theme_pass_instances": theme_pass_instances,
        "theme_pass_counts": theme_pass_counts,
        "raw_liquid_theme_density_breakout_hits": raw_breakouts,
        "candidate_days": len({row["date"] for row in candidates}),
        "unique_candidate_tickers": len({row["ticker"] for row in candidates}),
        "selected_theme_counts": {
            theme: sum(1 for row in candidates if row.get("selected_theme") == theme)
            for theme in sorted({str(row.get("selected_theme")) for row in candidates})
        },
        "rule_version": RULE_VERSION,
    }
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["theme_density_score"]),
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
        "promising_replay_only_theme_density_breakout_sleeve"
        if gate4_passed
        else "rejected_theme_density_breakout_sleeve"
    )
    payload["status"] = decision
    payload["decision"] = decision
    payload["hypothesis"] = (
        "Breakout candidates should have higher replacement value when they are "
        "part of a same-theme cohort with broad positive 20-day participation, "
        "multiple same-theme breakouts, and SPY-relative theme leadership. The "
        "single tested variable is a default-off top-1 paper candidate source "
        "keyed on this theme-density context."
    )
    payload["change_type"] = "theme_density_confirmed_breakout_default_off_paper_sleeve"
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["mechanism_family"] = "free_ohlcv_theme_density_candidate_pool"
    payload["trial_family"] = TRIAL_FAMILY
    payload["trial_variant_id"] = "theme_density_breakout_top1_v1"
    payload["prior_trial_count"] = 0
    payload["nearby_prior_experiments"] = [
        "exp-20260524-013",
        "exp-20260524-014",
        "exp-20260526-013",
        "exp-20260526-014",
        "exp-20260526-015",
    ]
    payload["multiple_testing_risk_bucket"] = "moderate"
    payload["new_evidence_type"] = "free_ohlcv_theme_density_internal_structure_field"
    payload["parameters"]["shadow_entry_filters"] = {
        "base_source": "new free-OHLCV theme-density confirmed breakout source",
        "breakout_close_above_prior_n_day_high": BREAKOUT_LOOKBACK_DAYS,
        "close_above_prior_n_day_moving_average": MOVING_AVERAGE_DAYS,
        "min_candidate_day_dollar_volume": MIN_DOLLAR_VOLUME,
        "min_candidate_volume_ratio_20": MIN_CANDIDATE_VOLUME_RATIO_20,
        "min_candidate_day_rs_vs_spy": 0.0,
        "theme_context": {
            "theme_membership_source": "daily_context_archive.THEME_TICKERS",
            "min_eligible_tickers": MIN_THEME_ELIGIBLE_TICKERS,
            "ret20_lookback_days": THEME_RETURN_LOOKBACK_DAYS,
            "min_positive_ret20_fraction": MIN_THEME_POSITIVE_RET20_FRACTION,
            "min_above_50d_fraction": MIN_THEME_ABOVE_50D_FRACTION,
            "min_breakout_count": MIN_THEME_BREAKOUT_COUNT,
            "min_avg_ret20_excess_spy": MIN_THEME_AVG_RET20_EXCESS_SPY,
        },
    }
    payload["parameters"]["selection_rank"] = [
        "signal_date",
        "theme_density_score desc",
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
        "accepted VCP adapter",
        "accepted volume-breadth breakout adapter",
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
            "candidate_pool: theme-density confirmation can improve breakout "
            "candidate quality with free OHLCV and existing production-visible "
            "theme membership. This matches the playbook's theme-density and "
            "relative-strength data-edge direction."
        ),
        "2_history_check": {
            "theme_component": (
                "exp-20260524-013 and exp-20260524-014 rejected core low-theme "
                "component top-ups. This run is not a core sizing scalar; it "
                "tests a default-off candidate source requiring positive theme "
                "participation."
            ),
            "market_and_sector_breadth": (
                "exp-20260526-013/014 accepted market-wide volume breadth; "
                "exp-20260526-015 rejected sector breadth. This run does not "
                "retune either threshold family; it uses theme cohorts and 20-day "
                "theme leadership as the independent variable."
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
            "exp_20260526_016_theme_density_breakout_sleeve.py"
        ),
    }
    payload["gate2"]["runtime_fields"] = [
        "canonical OHLCV Date/Open/High/Low/Close/Volume rows",
        "daily_context_archive.THEME_TICKERS theme membership",
        "candidate ticker trailing 20/50-day OHLCV features",
        "same-date same-theme 20-day return, breakout, and above-50d counts",
        "SPY OHLCV Close rows for signal-day and theme 20-day relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["gate2"]["note"] = (
        "All candidate and theme-density fields are derived from same-day or "
        "trailing OHLCV plus static shared theme membership known before next "
        "open. Paper entry occurs at the next open; no LLM, hidden event, or "
        "future field is used."
    )
    payload["gate3"]["candidate_pool_changed"] = True
    payload["gate3"]["note"] = (
        "No core filter or live entry rule was added. The default-off paper "
        "candidate source is additive research, so core survival is unchanged."
    )
    payload["theme_density_audit"] = THEME_DENSITY_AUDIT
    payload["why_not_other_changes"] = (
        "Skipped LLM soft-ranking, SEC semantics, and expectation-revision "
        "activation because current records remain PIT/sample-limited. Skipped "
        "VCP, market volume-breadth, sector-breadth, pocket-pivot, gap, "
        "long-base, smooth, and pullback threshold retunes due recent rejections "
        "or playbook freezes. This tests one orthogonal theme-density field."
    )
    payload["interpretation"] = (
        "The theme-density confirmed breakout sleeve cleared Gate 4 as a "
        "replay-only lead, but no production/shared policy was promoted."
        if gate4_passed
        else (
            "The theme-density confirmed breakout sleeve did not clear Gate 4. "
            "Do not promote it or retry nearby theme-density thresholds on the "
            "same frozen windows without forward paper rows or an orthogonal "
            "event/source-quality field."
        )
    )
    payload["next_evidence_needed"] = (
        "If revisited, collect forward paper rows or add an orthogonal "
        "production-visible event/source confirmation; do not just retune "
        "theme-density thresholds on the frozen sample."
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Candidates | Theme days | Tickers |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["theme_density_audit"].get(label, {})
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
                candidates=audit.get("raw_liquid_theme_density_breakout_hits"),
                days=audit.get("theme_pass_days"),
                tickers=audit.get("unique_candidate_tickers"),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Theme-Density Confirmed Breakout Paper Sleeve",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            (
                "Single variable: a default-off paper sleeve admits at most one "
                "liquid breakout candidate per day only when same-theme "
                "participation and SPY-relative theme strength confirm the setup."
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
            "## Theme-Density Audit",
            "",
            "```json",
            json.dumps(payload["theme_density_audit"], indent=2, sort_keys=True),
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
            "title": "Theme-density confirmed breakout paper sleeve",
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
                    "theme_density_audit": payload["theme_density_audit"],
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
