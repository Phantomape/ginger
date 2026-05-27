"""exp-20260527-022: industry-leadership breadth breakout paper sleeve.

This alpha search tests one new free-data candidate-pool discriminator:
industry-level leadership breadth. A liquid breakout candidate is admitted to a
default-off paper sleeve only when at least two same-industry peers also show
same-date leadership using close-of-day OHLCV features.

Core signal generation, ranking, sizing, exits, LLM/news replay, watchlists,
and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
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

import broad_market_sector_map  # noqa: E402
import exp_20260426_volatility_contraction_breakout_shadow as ohlcv_helper  # noqa: E402
import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as base  # noqa: E402


EXPERIMENT_ID = "exp-20260527-022"
STEM = "industry_leadership_breadth_breakout_sleeve"
TRIAL_FAMILY = "industry_leadership_breadth_confirmed_breakout_default_off_paper_sleeve"
CHANGED_VARIABLE = "industry_leadership_breadth_confirmed_breakout_top1_v1"
RULE_VERSION = "industry_leadership_breadth_breakout_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

BREAKOUT_LOOKBACK_DAYS = 20
MOVING_AVERAGE_DAYS = 50
RETURN_LOOKBACK_DAYS = 20
VOLUME_LOOKBACK_DAYS = 20
MIN_CANDIDATE_DOLLAR_VOLUME = 40_000_000.0
MIN_CANDIDATE_VOLUME_RATIO_20 = 1.10
MIN_CANDIDATE_DAY_RS_VS_SPY = 0.0
MIN_CANDIDATE_RET20_EXCESS_SPY = 0.02
MIN_INDUSTRY_DOLLAR_VOLUME = 30_000_000.0
MIN_INDUSTRY_ELIGIBLE_TICKERS = 3
MIN_INDUSTRY_LEADER_COUNT = 2
MIN_INDUSTRY_LEADERSHIP_FRACTION = 0.35
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

INDUSTRY_AUDIT: "OrderedDict[str, dict[str, Any]]" = OrderedDict()


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


def _ticker_context(
    snapshot: dict[str, list[dict[str, Any]]],
    ticker: str,
    idx: int,
    spy_rows: list[dict[str, Any]],
    spy_idx: int,
) -> dict[str, Any] | None:
    rows = ohlcv_helper._series(snapshot, ticker)
    if idx < MOVING_AVERAGE_DAYS or spy_idx < RETURN_LOOKBACK_DAYS:
        return None
    close = ohlcv_helper._value(rows[idx], "Close")
    volume = ohlcv_helper._value(rows[idx], "Volume")
    ma50 = _prior_average(rows, idx, MOVING_AVERAGE_DAYS, "Close")
    avg_volume = _prior_average(rows, idx, VOLUME_LOOKBACK_DAYS, "Volume")
    if not close or not volume or not ma50 or not avg_volume:
        return None
    ret20 = _close_return(rows, idx - RETURN_LOOKBACK_DAYS, idx)
    spy_ret20 = _close_return(spy_rows, spy_idx - RETURN_LOOKBACK_DAYS, spy_idx)
    candidate_day_ret = _close_return(rows, idx - 1, idx)
    spy_day_ret = _close_return(spy_rows, spy_idx - 1, spy_idx)
    if (
        ret20 is None
        or spy_ret20 is None
        or candidate_day_ret is None
        or spy_day_ret is None
    ):
        return None
    dollar_volume = close * volume
    volume_ratio = volume / avg_volume if avg_volume else None
    rs_vs_spy = candidate_day_ret - spy_day_ret
    ret20_excess_spy = ret20 - spy_ret20
    return {
        "close": close,
        "volume": volume,
        "ma50": ma50,
        "avg_volume_20": avg_volume,
        "dollar_volume": dollar_volume,
        "volume_ratio_20": volume_ratio,
        "ret20": ret20,
        "spy_ret20": spy_ret20,
        "ret20_excess_spy": ret20_excess_spy,
        "candidate_day_return": candidate_day_ret,
        "candidate_day_spy_return": spy_day_ret,
        "candidate_day_rs_vs_spy": rs_vs_spy,
        "above_50d": close > ma50,
        "industry_leader": (
            dollar_volume >= MIN_INDUSTRY_DOLLAR_VOLUME
            and close > ma50
            and ret20_excess_spy > 0.0
            and rs_vs_spy > 0.0
        ),
    }


def _industry_lookup_by_ticker(universe: list[str]) -> dict[str, dict[str, Any]]:
    cache = broad_market_sector_map.load_cache()
    out: dict[str, dict[str, Any]] = {}
    for ticker in sorted(set(universe).difference(EXCLUDED_TICKERS)):
        lookup = broad_market_sector_map.lookup_sector(ticker, cache)
        if (
            lookup.get("status") == broad_market_sector_map.OK_STATUS
            and lookup.get("industry")
        ):
            out[ticker] = lookup
    return out


def _industry_context_by_date(
    snapshot: dict[str, list[dict[str, Any]]],
    dates: list[str],
    universe: list[str],
    lookup_by_ticker: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    tickers = sorted(set(universe).intersection(snapshot).intersection(lookup_by_ticker))
    row_indices = {
        ticker: ohlcv_helper._row_index(ohlcv_helper._series(snapshot, ticker))
        for ticker in tickers
    }
    spy_rows = ohlcv_helper._series(snapshot, "SPY")
    spy_index = ohlcv_helper._row_index(spy_rows)
    out: dict[str, dict[str, Any]] = {}
    for date in dates:
        spy_idx = spy_index.get(date)
        if spy_idx is None:
            out[date] = {
                "industry_count": 0,
                "passed_industry_count": 0,
                "passed_industries": {},
                "rule_version": RULE_VERSION,
            }
            continue

        by_industry: dict[str, dict[str, Any]] = {}
        for ticker in tickers:
            idx = row_indices[ticker].get(date)
            if idx is None:
                continue
            ticker_ctx = _ticker_context(snapshot, ticker, idx, spy_rows, spy_idx)
            if not ticker_ctx:
                continue
            if ticker_ctx["dollar_volume"] < MIN_INDUSTRY_DOLLAR_VOLUME:
                continue
            lookup = lookup_by_ticker[ticker]
            industry = str(lookup.get("industry") or "Unknown")
            industry_ctx = by_industry.setdefault(
                industry,
                {
                    "sector": lookup.get("sector"),
                    "eligible_count": 0,
                    "leader_count": 0,
                    "leaders": [],
                    "avg_ret20_excess_spy": 0.0,
                    "avg_day_rs_vs_spy": 0.0,
                },
            )
            industry_ctx["eligible_count"] += 1
            industry_ctx["avg_ret20_excess_spy"] += float(ticker_ctx["ret20_excess_spy"])
            industry_ctx["avg_day_rs_vs_spy"] += float(ticker_ctx["candidate_day_rs_vs_spy"])
            if ticker_ctx["industry_leader"]:
                industry_ctx["leader_count"] += 1
                industry_ctx["leaders"].append(ticker)

        passed_industries: dict[str, dict[str, Any]] = {}
        for industry, context in by_industry.items():
            eligible_count = int(context["eligible_count"])
            if not eligible_count:
                continue
            leader_count = int(context["leader_count"])
            leadership_fraction = leader_count / eligible_count
            context["avg_ret20_excess_spy"] = base._round(
                float(context["avg_ret20_excess_spy"]) / eligible_count,
                6,
            )
            context["avg_day_rs_vs_spy"] = base._round(
                float(context["avg_day_rs_vs_spy"]) / eligible_count,
                6,
            )
            context["leadership_fraction"] = base._round(leadership_fraction, 6)
            context["passed"] = (
                eligible_count >= MIN_INDUSTRY_ELIGIBLE_TICKERS
                and leader_count >= MIN_INDUSTRY_LEADER_COUNT
                and leadership_fraction >= MIN_INDUSTRY_LEADERSHIP_FRACTION
            )
            if context["passed"]:
                passed_industries[industry] = {
                    "sector": context.get("sector"),
                    "eligible_count": eligible_count,
                    "leader_count": leader_count,
                    "leaders": sorted(context["leaders"]),
                    "leadership_fraction": context["leadership_fraction"],
                    "avg_ret20_excess_spy": context["avg_ret20_excess_spy"],
                    "avg_day_rs_vs_spy": context["avg_day_rs_vs_spy"],
                }

        out[date] = {
            "industry_count": len(by_industry),
            "passed_industry_count": len(passed_industries),
            "passed_industries": passed_industries,
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
    lookup_by_ticker = _industry_lookup_by_ticker(universe)
    industry_by_date = _industry_context_by_date(snapshot, dates, universe, lookup_by_ticker)
    spy_rows = ohlcv_helper._series(snapshot, "SPY")
    spy_index = ohlcv_helper._row_index(spy_rows)
    candidates: list[dict[str, Any]] = []
    raw_breakouts = 0
    raw_industry_confirmed_breakouts = 0

    for ticker in sorted(set(universe).intersection(snapshot).intersection(lookup_by_ticker)):
        rows = ohlcv_helper._series(snapshot, ticker)
        idx_by_date = ohlcv_helper._row_index(rows)
        lookup = lookup_by_ticker[ticker]
        industry = str(lookup.get("industry") or "Unknown")
        sector = lookup.get("sector") or "Unknown"
        for date in dates:
            day_context = industry_by_date.get(date) or {}
            industry_context = (day_context.get("passed_industries") or {}).get(industry)
            if not industry_context:
                continue
            idx = idx_by_date.get(date)
            spy_idx = spy_index.get(date)
            if idx is None or spy_idx is None:
                continue
            ticker_ctx = _ticker_context(snapshot, ticker, idx, spy_rows, spy_idx)
            if not ticker_ctx:
                continue
            if ticker_ctx["dollar_volume"] < MIN_CANDIDATE_DOLLAR_VOLUME:
                continue
            prior_high = _prior_high(rows, idx, BREAKOUT_LOOKBACK_DAYS)
            if not prior_high:
                continue
            close = float(ticker_ctx["close"])
            raw_breakouts += int(close > prior_high)
            if close <= prior_high or not ticker_ctx["above_50d"]:
                continue
            volume_ratio = ticker_ctx["volume_ratio_20"]
            if volume_ratio is None or volume_ratio < MIN_CANDIDATE_VOLUME_RATIO_20:
                continue
            if ticker_ctx["candidate_day_rs_vs_spy"] <= MIN_CANDIDATE_DAY_RS_VS_SPY:
                continue
            if ticker_ctx["ret20_excess_spy"] < MIN_CANDIDATE_RET20_EXCESS_SPY:
                continue
            raw_industry_confirmed_breakouts += 1
            ab_entries = entries_by_date.get(date, [])
            breakout_margin = (close / prior_high) - 1.0
            score = (
                max(float(ticker_ctx["ret20_excess_spy"]), 0.0) * 4.0
                + max(float(ticker_ctx["candidate_day_rs_vs_spy"]), 0.0) * 8.0
                + min(max(float(volume_ratio) - 1.0, 0.0), 3.0)
                + max(breakout_margin, 0.0) * 3.0
                + float(industry_context["leadership_fraction"])
                + min(float(industry_context["leader_count"]), 6.0) / 10.0
            )
            candidates.append(
                {
                    "date": date,
                    "ticker": ticker,
                    "sector": sector,
                    "industry": industry,
                    "strategy": "industry_leadership_breadth_breakout",
                    "close": base._round(close, 4),
                    "breakout_above_prior_20d_high_pct": base._round(breakout_margin, 6),
                    "pct_above_50d_ma": base._round((close / ticker_ctx["ma50"]) - 1.0, 6),
                    "candidate_day_return": base._round(
                        ticker_ctx["candidate_day_return"],
                        6,
                    ),
                    "candidate_day_spy_return": base._round(
                        ticker_ctx["candidate_day_spy_return"],
                        6,
                    ),
                    "candidate_day_rs_vs_spy": base._round(
                        ticker_ctx["candidate_day_rs_vs_spy"],
                        6,
                    ),
                    "ret20_excess_spy": base._round(ticker_ctx["ret20_excess_spy"], 6),
                    "volume_ratio_20": base._round(volume_ratio, 6),
                    "dollar_volume": base._round(ticker_ctx["dollar_volume"], 2),
                    "industry_leadership_score": base._round(score, 6),
                    "same_day_ab_entry_count": len(ab_entries),
                    "same_day_ab_overlap": bool(ab_entries),
                    "same_ticker_ab_overlap": any(
                        trade.get("ticker") == ticker for trade in ab_entries
                    ),
                    "source_universe": "current_production_universe_with_industry_cache",
                    "industry_leadership_context": industry_context,
                    "sector_lookup": lookup,
                    "industry_leadership_rule_version": RULE_VERSION,
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
    passed_days = [
        date
        for date, context in industry_by_date.items()
        if context.get("passed_industry_count", 0) > 0
    ]
    industry_counts = Counter()
    for row in candidates:
        industry_counts[str(row.get("industry") or "Unknown")] += 1
    coverage = broad_market_sector_map.coverage_report(universe)
    INDUSTRY_AUDIT[label] = {
        "candidate_source_tickers": len(set(universe).intersection(snapshot).difference(EXCLUDED_TICKERS)),
        "industry_cache_coverage": coverage,
        "trading_days": len(dates),
        "industry_pass_days": len(passed_days),
        "industry_pass_day_fraction": base._round(
            len(passed_days) / len(dates) if dates else None,
            6,
        ),
        "raw_breakouts_after_industry_day_precheck": raw_breakouts,
        "raw_industry_confirmed_breakouts": raw_industry_confirmed_breakouts,
        "candidate_days": len({row["date"] for row in candidates}),
        "unique_candidate_tickers": len({row["ticker"] for row in candidates}),
        "unique_candidate_industries": len(industry_counts),
        "top_candidate_industries": dict(industry_counts.most_common(10)),
        "sample_industry_context": {
            date: industry_by_date[date] for date in passed_days[:5]
        },
        "rule_version": RULE_VERSION,
    }
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["industry_leadership_score"]),
            -float(row["ret20_excess_spy"]),
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
        "promising_replay_only_industry_leadership_breadth_breakout_sleeve"
        if gate4_passed
        else "rejected_industry_leadership_breadth_breakout_sleeve"
    )
    payload["status"] = decision
    payload["decision"] = decision
    payload["hypothesis"] = (
        "Breakout candidates should have higher replacement value when their "
        "industry has same-date peer leadership breadth. The single tested "
        "variable is a default-off top-1 paper candidate source keyed on at "
        "least two same-industry leaders and a minimum leadership fraction."
    )
    payload["change_type"] = "industry_leadership_breadth_confirmed_breakout_default_off_paper_sleeve"
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["trial_family"] = TRIAL_FAMILY
    payload["prior_trial_count"] = 0
    payload["nearby_prior_experiments"] = [
        "exp-20260525-038",
        "exp-20260526-015",
        "exp-20260527-012",
        "exp-20260527-021",
        "exp-20260527-901",
    ]
    payload["multiple_testing_risk_bucket"] = "moderate"
    payload["new_evidence_type"] = "free_ohlcv_industry_peer_leadership_breadth_field"
    payload["parameters"]["shadow_entry_filters"] = {
        "base_source": "new free-OHLCV industry-leadership breadth confirmed breakout source",
        "breakout_close_above_prior_n_day_high": BREAKOUT_LOOKBACK_DAYS,
        "close_above_prior_n_day_moving_average": MOVING_AVERAGE_DAYS,
        "min_candidate_day_dollar_volume": MIN_CANDIDATE_DOLLAR_VOLUME,
        "min_candidate_volume_ratio_20": MIN_CANDIDATE_VOLUME_RATIO_20,
        "min_candidate_day_rs_vs_spy": MIN_CANDIDATE_DAY_RS_VS_SPY,
        "min_candidate_ret20_excess_spy": MIN_CANDIDATE_RET20_EXCESS_SPY,
        "industry_context": {
            "min_industry_dollar_volume": MIN_INDUSTRY_DOLLAR_VOLUME,
            "min_eligible_tickers": MIN_INDUSTRY_ELIGIBLE_TICKERS,
            "min_leader_count": MIN_INDUSTRY_LEADER_COUNT,
            "min_leadership_fraction": MIN_INDUSTRY_LEADERSHIP_FRACTION,
            "leader_definition": (
                "dollar_volume >= min_industry_dollar_volume, close > 50d MA, "
                "20d return excess SPY > 0, and signal-day RS vs SPY > 0"
            ),
        },
    }
    payload["parameters"]["selection_rank"] = [
        "signal_date",
        "industry_leadership_score desc",
        "ret20_excess_spy desc",
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
            "candidate_pool / entry: same-industry peer leadership breadth can "
            "separate stronger liquid breakouts from isolated ticker moves using "
            "only free OHLCV plus the existing offline industry map."
        ),
        "2_history_check": {
            "sector_map_measurement": (
                "exp-20260525-038 accepted broad-market sector/industry lookup as "
                "a read-only context surface. This run consumes that cache but "
                "does not alter it."
            ),
            "nearby_rejected_sector_tests": (
                "exp-20260527-021 and exp-20260527-901 rejected same-sector open "
                "crowding support/haircuts; exp-20260526-015 rejected sector "
                "breadth top-1; exp-20260527-012 rejected same-sector core "
                "activity. None tested industry-level peer leadership breadth "
                "as a candidate-pool source."
            ),
            "avoided_retreads": (
                "Skipped Companyfacts+RS, VCP/VBB threshold retunes, LLM "
                "soft-ranking, state-surface scalars, and recent smooth-momentum "
                "or same-sector crowding variants per playbook and memory freeze."
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
            "exp_20260527_022_industry_leadership_breadth_breakout_sleeve.py"
        ),
    }
    payload["gate2"]["runtime_fields"] = [
        "canonical OHLCV Date/Open/High/Low/Close/Volume rows",
        "candidate ticker trailing 20/50-day OHLCV features",
        "same-date same-industry peer leadership counts",
        "data/reference/broad_market_sector_map.json sector/industry/status rows",
        "SPY OHLCV Close rows for signal-day and trailing relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["gate2"]["note"] = (
        "All candidate and industry leadership fields are derived from trailing "
        "or same-day OHLCV known after the signal-date close plus the existing "
        "offline sector/industry cache. Paper entry occurs only at the next open; "
        "no LLM or hidden event field is used."
    )
    payload["gate3"]["candidate_pool_changed"] = True
    payload["gate3"]["note"] = (
        "No core filter or live entry rule was added. The default-off paper "
        "candidate pool uses an additive industry-breadth source, so core "
        "survival is unchanged from the baseline replay."
    )
    payload["industry_leadership_audit"] = INDUSTRY_AUDIT
    payload["why_not_other_changes"] = (
        "Skipped LLM soft-ranking, SEC semantics, and Companyfacts+RS retries "
        "because recent records are PIT/sample/concentration limited. Skipped "
        "VCP/VBB and state-surface threshold/top-N/scalar retunes due explicit "
        "playbook freezes. This tests one new free industry peer-breadth field "
        "rather than adding noisy tickers."
    )
    payload["interpretation"] = (
        "The industry-leadership breadth breakout sleeve cleared Gate 4 as a "
        "replay-only lead, but no production/shared policy was promoted."
        if gate4_passed
        else (
            "The industry-leadership breadth breakout sleeve did not clear Gate "
            "4. Do not promote it or retry nearby industry-leadership thresholds "
            "on the same frozen windows without forward paper rows or an "
            "orthogonal source-quality field."
        )
    )
    payload["next_evidence_needed"] = (
        "If revisited, collect forward paper rows or add an orthogonal "
        "production-visible source-quality field such as cost-adjusted "
        "replacement value; do not just retune same-industry leader thresholds "
        "on the frozen sample."
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
        base._repo_rel(DOC_TICKET_JSON),
        base._repo_rel(ARTIFACT_MD),
        base._repo_rel(EXPERIMENT_LOG),
    ]
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Candidates | Industry days | Industries |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["industry_leadership_audit"].get(label, {})
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | "
            "${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | "
            "{trades} | {candidates} | {days} | {industries} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                candidates=audit.get("raw_industry_confirmed_breakouts"),
                days=audit.get("industry_pass_days"),
                industries=audit.get("unique_candidate_industries"),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Industry-Leadership Breadth Breakout Paper Sleeve",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            (
                "Single variable: a default-off paper sleeve admits at most one "
                "liquid breakout candidate per day only when its industry has "
                "same-date peer leadership breadth."
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
            "## Industry Audit",
            "",
            "```json",
            json.dumps(payload["industry_leadership_audit"], indent=2, sort_keys=True),
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


def _ticket(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "title": "Industry-leadership breadth breakout paper sleeve",
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": base._repo_rel(ARTIFACT_MD),
        "json": base._repo_rel(OUT_JSON),
        "summary": payload["interpretation"],
    }


def _persist(payload: dict[str, Any]) -> None:
    base._write_json(OUT_JSON, payload)
    base._write_json(LOG_JSON, payload)
    ticket = _ticket(payload)
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
                    "industry_leadership_audit": payload["industry_leadership_audit"],
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
