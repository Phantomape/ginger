"""exp-20260712-009: DoD new-contract revenue-materiality candidate pool.

The fixed decision hypothesis is that an official DoD award is informative only
when it is a new contract (not a modification, ceiling, option, IDIQ, or order
under an existing vehicle) and is economically material relative to the
issuer's latest annual revenue known by the announcement date.  The unchanged
exp-20260711-020 absorption/liquidity, next-open, 10-session, top-1/day, cost,
and cooldown policy is retained.

The runner deliberately uses the already materialized official announcement
rows from exp-20260711-020 and raw SEC Companyfacts cache.  It does not fetch or
rewrite either source.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260616_003_raw_sec_rd_intensity_candidate_pool as companyfacts
import exp_20260711_020_dod_contract_awards as prior
from experiment_registry import persist_self_registered_result
from sharpe_inference import build_backtest_sharpe_inference


EXPERIMENT_ID = "exp-20260712-009"
STEM = "dod_contract_revenue_materiality"
TRIAL_FAMILY = "dod_new_contract_revenue_materiality_candidate_pool"
TRIAL_VARIANT_ID = "dod_new_contract_award_to_pit_annual_revenue_top1_v1"
CHANGED_VARIABLE = "dod_new_contract_award_to_pit_annual_revenue_top1_candidate_pool_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-explore"

REPO_ROOT = prior.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260712_009_{STEM}.json"
SOURCE_EVENTS_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260711-020"
    / "dod_contract_award_events.json"
)
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = prior.BASE_NOTIONAL_USD
HOLD_DAYS = prior.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = prior.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = prior.SAME_TICKER_COOLDOWN_DAYS

MIN_PRICE = prior.MIN_PRICE
MIN_AVG_DOLLAR_VOLUME_20D = prior.MIN_AVG_DOLLAR_VOLUME_20D
MIN_SIGNAL_RETURN = prior.MIN_SIGNAL_RETURN
MIN_SIGNAL_EXCESS_SPY = prior.MIN_SIGNAL_EXCESS_SPY
MIN_CLOSE_LOCATION = prior.MIN_CLOSE_LOCATION
MIN_VOLUME_RATIO_20D = prior.MIN_VOLUME_RATIO_20D
MAX_REALIZED_VOL_20D = prior.MAX_REALIZED_VOL_20D
MIN_RET20_EXCESS_SPY = prior.MIN_RET20_EXCESS_SPY
MAX_EVENT_AGE_TRADING_DAYS = prior.MAX_EVENT_AGE_TRADING_DAYS

MAX_REVENUE_FACT_AGE_DAYS = 550
EXISTING_VEHICLE_TERMS = (
    "ceiling",
    "indefinite-delivery",
    "indefinite delivery",
    "maximum",
    "not-to-exceed",
    "multiple award",
    "delivery order",
    "task order",
    "previously awarded",
    "basic ordering agreement",
    "exercise an option",
    "exercises an option",
    "one-year option",
    "one year option",
    "up to a maximum",
)

PREDICTION = {
    "success_probability": 0.24,
    "expected_ev_delta": 0.20,
    "expected_pnl_delta": 3_000.0,
    "main_failure_modes": [
        "routine_awards_already_priced",
        "issuer_revenue_denominator_misses_segment_materiality",
        "prime_concentration",
        "old_thin_regression",
    ],
    "confidence_reason": (
        "The two prior DoD trials blurred multi-year ceilings, modifications, "
        "and issuer-scale economics. The official text plus filed-date SEC "
        "annual revenue supplies the richer relation explicitly requested by "
        "their reflections, with 516 preflight-covered clean ticker-days; but "
        "awards may still be anticipated and segment economics are unavailable."
    ),
    "recorded_at": "2026-07-12T07:09:53+00:00",
}

PRODUCTION_IMPACT = {
    **prior.PRODUCTION_IMPACT,
    "adapter_status": "full_stack_candidate_attempt_retained_only_if_gate4_passes",
    "uses_free_sec_companyfacts": True,
    "trade_enabled": False,
    "parity_note": (
        "No live/default order behavior changes. The exact candidate builder "
        "is experiment-local until Gate 4 passes; a passing result must be "
        "moved unchanged into a shared helper and daily default-off snapshot "
        "within this experiment before acceptance."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool/full_stack: excluding DoD modifications and existing-"
        "vehicle ceiling/IDIQ/order language, then ranking new contract awards "
        "by award value divided by the issuer's latest filed annual SEC revenue "
        "isolates economically material demand shocks with after-cost 10-day "
        "continuation under the unchanged absorption policy."
    ),
    "2_history_check": {
        "exp-20260711-020": (
            "Rejected absolute >=$250M awardee-self pool; its reflection "
            "explicitly requires new-award versus modification/ceiling and "
            "revenue/backlog normalization before reopening."
        ),
        "exp-20260711-023": (
            "Rejected peer substitution and forbids peer/rank/threshold sweeps; "
            "it explicitly allows obligated-versus-ceiling/new-award economics "
            "or a genuinely different supplier/backlog relation."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Current-code Gate 1 baseline and challenger on all three canonical "
        "windows; positive aggregate EV/PnL, no EV/PnL window regression, at "
        "least 20 trades across all windows, drawdown/concentration/survival "
        "guards, and closest accepted candidate-pool comparator after costs."
    ),
    "5_reproducibility": (
        ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260712_009_dod_contract_revenue_materiality.py"
    ),
}

_EVENT_INDEX_CACHE: tuple[dict[str, list[dict[str, Any]]], dict[str, Any]] | None = None
_REVENUE_INDEX_CACHE: tuple[dict[str, list[dict[str, Any]]], dict[str, Any]] | None = None
_CURRENT_WINDOW_SNAPSHOT: dict[str, list[dict[str, Any]]] | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return prior._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return prior._round(value, digits)


def _is_new_contract_event(row: dict[str, Any]) -> bool:
    if bool(row.get("any_modification")):
        return False
    excerpt = str(row.get("largest_award_excerpt") or "").lower()
    return bool(excerpt) and not any(term in excerpt for term in EXISTING_VEHICLE_TERMS)


def _load_revenue_index() -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    global _REVENUE_INDEX_CACHE
    if _REVENUE_INDEX_CACHE is not None:
        return _REVENUE_INDEX_CACHE
    refs = json.loads(
        (REPO_ROOT / "data" / "reference" / "sec_company_tickers.json").read_text(
            encoding="utf-8"
        )
    )
    ticker_cik = {
        str(row.get("ticker") or "").upper(): int(row["cik_str"])
        for row in refs.values()
        if row.get("ticker") and row.get("cik_str") is not None
    }
    stats: Counter[str] = Counter()
    index: dict[str, list[dict[str, Any]]] = {}
    for ticker, cik in ticker_cik.items():
        path = companyfacts.RAW_COMPANYFACTS_CACHE / f"CIK{cik:010d}.json"
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            stats["unreadable_companyfacts"] += 1
            continue
        facts = companyfacts._raw_annual_facts(
            payload.get("facts", {}).get("us-gaap", {}),
            companyfacts.REVENUE_TAGS,
        )
        if facts:
            index[ticker] = facts
            stats["tickers_with_annual_revenue"] += 1
    _REVENUE_INDEX_CACHE = (
        index,
        {
            **dict(stats),
            "source": _repo_rel(companyfacts.RAW_COMPANYFACTS_CACHE),
            "filed_date_bound": True,
            "max_revenue_fact_age_days": MAX_REVENUE_FACT_AGE_DAYS,
        },
    )
    return _REVENUE_INDEX_CACHE


def _load_event_index() -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    global _EVENT_INDEX_CACHE
    if _EVENT_INDEX_CACHE is not None:
        return _EVENT_INDEX_CACHE
    # exp-20260711-020 intentionally compacted its < $250M rows to
    # ticker/date/amount only.  This hypothesis needs the frozen paragraph
    # text for every amount, so reconstruct the same ticker-day rows from the
    # already cached official article bodies.  This is read-only and performs
    # no network fetch.
    articles = prior._rss_articles()
    liquid = prior._warehouse_liquid_tickers()
    parse_stats: Counter[str] = Counter()
    parsed_articles = 0
    events: dict[tuple[str, str], dict[str, Any]] = {}
    for article in articles:
        date = str(article.get("announce_date") or "")
        if not (prior.FETCH_START <= date <= prior.FETCH_END):
            continue
        path = prior.CACHE_DIR / f"article_{article['article_id']}.html"
        if not path.exists():
            parse_stats["article_body_missing"] += 1
            continue
        article_rows, row_stats = prior._parse_article(
            path.read_text(encoding="utf-8", errors="ignore")
        )
        parse_stats.update(row_stats)
        parsed_articles += 1
        for row in article_rows:
            ticker = str(row["ticker"]).upper()
            if ticker not in liquid:
                parse_stats["mapped_but_not_warehouse_liquid"] += 1
                continue
            key = (date, ticker)
            event = events.setdefault(
                key,
                {
                    "ticker": ticker,
                    "filing_date": date,
                    "accepted_after_close": True,
                    "acceptance_datetime": article.get("publication_datetime_et")
                    or f"{date}T17:00:00-05:00",
                    "article_id": article["article_id"],
                    "article_url": article["url"],
                    "award_total_usd": 0.0,
                    "award_count": 0,
                    "max_single_award_usd": 0.0,
                    "branches": [],
                    "any_modification": False,
                    "contractors": [],
                    "largest_award_excerpt": "",
                },
            )
            event["award_total_usd"] += float(row["amount_usd"])
            event["award_count"] += 1
            if float(row["amount_usd"]) > float(event["max_single_award_usd"]):
                event["max_single_award_usd"] = float(row["amount_usd"])
                event["largest_award_excerpt"] = row["excerpt"]
            if row["branch"] not in event["branches"]:
                event["branches"].append(row["branch"])
            event["any_modification"] = bool(
                event["any_modification"] or row["is_modification"]
            )
            if row["contractor"] not in event["contractors"]:
                event["contractors"].append(row["contractor"])
    all_rows = sorted(events.values(), key=lambda row: (row["filing_date"], row["ticker"]))
    revenue_index, revenue_summary = _load_revenue_index()
    stats: Counter[str] = Counter()
    index: dict[str, list[dict[str, Any]]] = {}
    seen: set[tuple[str, str]] = set()
    for raw in all_rows:
        stats["source_ticker_day_rows"] += 1
        if not _is_new_contract_event(raw):
            stats["excluded_modification_or_existing_vehicle"] += 1
            continue
        ticker = str(raw.get("ticker") or "").upper()
        event_date = str(raw.get("filing_date") or "")[:10]
        key = (ticker, event_date)
        if not ticker or not event_date or key in seen:
            stats["invalid_or_duplicate_ticker_day"] += 1
            continue
        seen.add(key)
        fact = companyfacts._latest_period_fact(
            revenue_index.get(ticker, []),
            asof=event_date,
        )
        if fact is None or float(fact.get("value") or 0.0) <= 0.0:
            stats["missing_pit_annual_revenue"] += 1
            continue
        fact_age_days = prior.runner.base._days_between(event_date, str(fact["filed"]))
        if fact_age_days > MAX_REVENUE_FACT_AGE_DAYS:
            stats["stale_annual_revenue"] += 1
            continue
        award_total = float(raw.get("award_total_usd") or 0.0)
        if award_total <= 0.0:
            stats["nonpositive_award"] += 1
            continue
        event = {
            **raw,
            "pit_annual_revenue_usd": float(fact["value"]),
            "pit_annual_revenue_filed": fact["filed"],
            "pit_annual_revenue_period_end": fact["end"],
            "pit_annual_revenue_tag": fact["tag"],
            "pit_annual_revenue_fact_age_days": fact_age_days,
            "award_to_annual_revenue": award_total / float(fact["value"]),
        }
        index.setdefault(ticker, []).append(event)
        stats["eligible_new_contract_revenue_rows"] += 1
    for ticker in index:
        index[ticker].sort(key=lambda row: str(row.get("filing_date") or ""))
    _EVENT_INDEX_CACHE = (
        index,
        {
            **dict(stats),
            **revenue_summary,
            "cached_articles_parsed": parsed_articles,
            "cached_parse_stats": dict(parse_stats),
            "events_artifact": _repo_rel(SOURCE_EVENTS_JSON),
            "full_text_source": _repo_rel(prior.CACHE_DIR),
            "event_classification": "new_contract_excludes_modification_ceiling_idiq_option_existing_order_v1",
            "candidate_universe_scope": "broad_liquid_warehouse_all_windows_full_liquid",
            "tickers_with_events": len(index),
            "event_dates": len(
                {
                    str(row.get("filing_date"))
                    for rows in index.values()
                    for row in rows
                }
            ),
        },
    )
    return _EVENT_INDEX_CACHE


def _build_quality_index(
    companyfacts_rows: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    index, summary = _load_event_index()
    return index, {
        **summary,
        "selected_companyfacts_rows_ignored": len(companyfacts_rows),
        "field_source": "official_dod_announcements_plus_raw_sec_annual_revenue",
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    sector_entries: dict[str, dict[str, Any]],
    quality_index: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    global _CURRENT_WINDOW_SNAPSHOT
    _CURRENT_WINDOW_SNAPSHOT = snapshot
    shadow = prior.runner.base.framework.shadow
    indices = {
        ticker: shadow._row_index(shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    dates = shadow._trading_dates(snapshot)
    start, end = str(cfg["start"]), str(cfg["end"])
    scan: Counter[str] = Counter()
    scan["eligible_event_tickers"] = len(set(quality_index) & set(snapshot))
    scan["dod_award_events_total"] = sum(len(rows) for rows in quality_index.values())
    candidates: list[dict[str, Any]] = []
    for ticker in sorted(set(quality_index) & set(snapshot)):
        for event in quality_index[ticker]:
            signal_date = prior.runner._signal_date_for_event(event, dates)
            if signal_date is None:
                scan["event_after_last_or_stale"] += 1
                continue
            if not (start <= signal_date <= end):
                scan["event_outside_window"] += 1
                continue
            scan["dod_award_events_in_window"] += 1
            confirm = prior.runner._absorption_confirmation(
                snapshot=snapshot,
                indices=indices,
                ticker=ticker,
                signal_date=signal_date,
            )
            if confirm is None:
                scan["failed_absorption_or_liquidity_gate"] += 1
                continue
            scan["qualified_candidate_rows"] += 1
            ratio = float(event["award_to_annual_revenue"])
            meta = sector_entries.get(ticker, {})
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "DOD_NEW_CONTRACT_REVENUE_MATERIALITY_PAPER",
                    "candidate_score": _round(ratio, 9),
                    "candidate_score_semantics": "award_to_latest_filed_annual_revenue",
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": "dod_publication_and_sec_revenue_filing_before_next_open",
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "uses_free_sec_companyfacts": True,
                    "uses_dod_contract_announcements": True,
                    "uses_free_ohlcv": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    "dod_announce_date": event.get("filing_date"),
                    "dod_publication_datetime_et": event.get("acceptance_datetime"),
                    "dod_award_total_usd": event.get("award_total_usd"),
                    "dod_award_to_annual_revenue": _round(ratio, 9),
                    "dod_pit_annual_revenue_usd": event.get("pit_annual_revenue_usd"),
                    "dod_pit_annual_revenue_filed": event.get("pit_annual_revenue_filed"),
                    "dod_pit_annual_revenue_period_end": event.get("pit_annual_revenue_period_end"),
                    "dod_pit_annual_revenue_tag": event.get("pit_annual_revenue_tag"),
                    "dod_contractors": event.get("contractors"),
                    "dod_branches": event.get("branches"),
                    "dod_article_id": event.get("article_id"),
                    "dod_article_url": event.get("article_url"),
                    "dod_largest_award_excerpt": event.get("largest_award_excerpt"),
                    **confirm,
                }
            )
    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in candidates:
        key = (row["date"], row["ticker"])
        if key not in deduped or float(row["candidate_score"]) > float(
            deduped[key]["candidate_score"]
        ):
            deduped[key] = row
    rows = list(deduped.values())
    rows.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"] or 0.0),
            -float(row.get("candidate_signal_excess_spy") or 0.0),
            row["ticker"],
        )
    )
    scan["deduped_candidate_rows"] = len(rows)
    scan["candidate_signal_days"] = len({row["date"] for row in rows})
    scan["candidate_tickers"] = len({row["ticker"] for row in rows})
    scan["eligible_quality_tickers"] = scan["eligible_event_tickers"]
    return rows, {
        **dict(scan),
        "rule_version": RULE_VERSION,
        "event_rule": "new contract only; rank by award/latest-filed annual revenue",
        "no_absolute_award_threshold": True,
        "max_revenue_fact_age_days": MAX_REVENUE_FACT_AGE_DAYS,
        "min_price": MIN_PRICE,
        "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
        "min_signal_return": MIN_SIGNAL_RETURN,
        "min_signal_excess_spy": MIN_SIGNAL_EXCESS_SPY,
        "min_close_location": MIN_CLOSE_LOCATION,
        "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
        "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
        "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
        "max_event_age_trading_days": MAX_EVENT_AGE_TRADING_DAYS,
    }


def _overlay_from_paper_trades_current_mtm(
    before_result: dict[str, Any],
    paper_trades: list[dict[str, Any]],
) -> dict[str, Any]:
    """Mark every open paper trade daily under the schema-v1 cost contract."""

    if _CURRENT_WINDOW_SNAPSHOT is None:
        raise RuntimeError("current window snapshot is unavailable for paper MTM")
    shadow = prior.runner.base.framework.shadow
    close_by_ticker_date: dict[str, dict[str, float]] = {}
    for ticker in {str(row.get("ticker") or "").upper() for row in paper_trades}:
        close_by_ticker_date[ticker] = {
            shadow._date(row): float(shadow._value(row, "Close"))
            for row in shadow._series(_CURRENT_WINDOW_SNAPSHOT, ticker)
            if shadow._date(row) and shadow._value(row, "Close") is not None
        }
    round_trip_cost = float(prior.runner.base.framework.sleeve.ROUND_TRIP_COST_PCT)
    combined_curve: list[tuple[str, float]] = []
    for raw_day, raw_equity in before_result.get("equity_curve") or []:
        day = str(raw_day)[:10]
        contribution = 0.0
        for trade in paper_trades:
            entry_date = str(trade.get("entry_date") or "")[:10]
            exit_date = str(trade.get("exit_date") or "")[:10]
            if not entry_date or not exit_date or day < entry_date:
                continue
            if day >= exit_date:
                contribution += float(trade.get("pnl") or 0.0)
                continue
            ticker = str(trade.get("ticker") or "").upper()
            close = close_by_ticker_date.get(ticker, {}).get(day)
            entry_price = float(trade.get("entry_price") or 0.0)
            notional = float(trade.get("paper_notional_usd") or 0.0)
            if close is None or entry_price <= 0.0 or notional <= 0.0:
                continue
            contribution += notional * (close / entry_price - 1.0)
            contribution -= notional * round_trip_cost / 2.0
        combined_curve.append((day, round(float(raw_equity) + contribution, 8)))
    return {
        "overlay_total_pnl": _round(sum(float(row.get("pnl") or 0.0) for row in paper_trades), 2),
        "combined_equity_curve": combined_curve,
        "overlay_days": [
            {
                "date": row.get("exit_date"),
                "ticker": row.get("ticker"),
                "signal_date": row.get("signal_date"),
                "entry_date": row.get("entry_date"),
                "exit_date": row.get("exit_date"),
                "pnl": row.get("pnl"),
                "source": STEM,
            }
            for row in paper_trades
        ],
        "overlay_day_count": len(paper_trades),
        "paper_trade_count": len(paper_trades),
        "paper_mtm_contract": {
            "schema_version": 1,
            "open_positions_marked_daily": True,
            "entry_half_cost_recognized_while_open": True,
            "full_net_pnl_recognized_on_fixed_exit": True,
            "final_liquidation_costs_included": True,
        },
    }


def _metrics_current(result: dict[str, Any]) -> dict[str, Any]:
    inference = result.get("sharpe_inference") or build_backtest_sharpe_inference(
        result.get("equity_curve") or []
    )
    if inference.get("status") != "computable" or int(inference.get("schema_version") or 0) < 1:
        raise RuntimeError(f"baseline Sharpe inference unavailable: {inference}")
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 6),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "strategy_total_return_pct": _round(benchmarks.get("strategy_total_return_pct"), 6),
        "sharpe_daily": _round(inference.get("annualized_sharpe"), 6),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 6),
        "win_rate": _round(result.get("win_rate"), 6),
        "trade_count": int(result.get("total_trades") or 0),
        "paper_trade_count": 0,
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": _round(result.get("survival_rate"), 6),
        "sharpe_inference": inference,
        "paper_mtm_contract": {
            "schema_version": 1,
            "open_positions_marked_daily": True,
            "entry_half_cost_recognized_while_open": True,
            "full_net_pnl_recognized_on_fixed_exit": True,
            "final_liquidation_costs_included": True,
        },
    }


def _metrics_with_overlay_current(
    result: dict[str, Any],
    overlay: dict[str, Any],
) -> dict[str, Any]:
    inference = build_backtest_sharpe_inference(overlay["combined_equity_curve"])
    if inference.get("status") != "computable" or int(inference.get("schema_version") or 0) < 1:
        raise RuntimeError(f"challenger Sharpe inference unavailable: {inference}")
    initial_capital = float(prior.runner.base.framework.overlay_helper.INITIAL_CAPITAL)
    total_pnl = float(result.get("total_pnl") or 0.0) + float(overlay["overlay_total_pnl"] or 0.0)
    strategy_return = total_pnl / initial_capital
    sharpe = float(inference["annualized_sharpe"])
    peak = 0.0
    max_drawdown = 0.0
    for _, equity in overlay["combined_equity_curve"]:
        peak = max(peak, float(equity))
        if peak > 0.0:
            max_drawdown = max(max_drawdown, (peak - float(equity)) / peak)
    paper_trades = int(overlay.get("paper_trade_count") or 0)
    core_trades = int(result.get("total_trades") or 0)
    return {
        "expected_value_score": round(strategy_return * sharpe, 6),
        "total_pnl": round(total_pnl, 2),
        "strategy_total_return_pct": round(strategy_return, 6),
        "sharpe_daily": round(sharpe, 6),
        "max_drawdown_pct": round(max_drawdown, 6),
        "win_rate": _round(result.get("win_rate"), 6),
        "trade_count": core_trades + paper_trades,
        "paper_trade_count": paper_trades,
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": _round(result.get("survival_rate"), 6),
        "sharpe_inference": inference,
        "paper_mtm_contract": overlay["paper_mtm_contract"],
    }


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = prior.runner.base.framework._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = list(gate.get("failed_reasons") or [])
    pnl_delta = float(aggregate["total_pnl_delta_sum"] or 0.0)
    if pnl_delta <= prior.runner.base.COMPRESSION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_compression_pnl_not_beaten")
    if pnl_delta <= prior.runner.base.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_distribution_pnl_not_beaten")
    gate["failed_reasons"] = failed
    gate["passed"] = not failed
    gate["accepted_comparator_protocol"] = {
        "pnl_comparable_across_exp_20260712_006_migration": True,
        "ev_comparison_deferred_if_numeric_gate_passes": (
            "Archived comparator EV used the pre-MTM-repair schema and is not "
            "used across the protocol boundary. Rerun the closest accepted "
            "helper under current schema before accepting a positive result."
        ),
    }
    gate["decision"] = (
        "positive_replay_lead_requires_current_schema_comparator_and_shared_helper"
        if gate["passed"]
        else "rejected_dod_new_contract_revenue_materiality_candidate_pool"
    )
    return gate


def _interpretation(payload: dict[str, Any]) -> str:
    gate4 = payload["gate4"]
    if gate4["passed"]:
        return (
            "The fixed revenue-materiality bundle cleared the current-code core "
            "screen and PnL comparators. Before acceptance it still requires a "
            "current-schema EV comparator rerun and unchanged shared daily helper."
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    trade_count = payload["target_trade_summary"]["total_trade_count"]
    return (
        "The new-contract revenue-materiality relation produced only "
        f"{trade_count} trades. It added ${float(aggregate['total_pnl_delta_sum']):,.2f} "
        f"and {float(aggregate['expected_value_score_delta_sum']):+.4f} aggregate EV, "
        "but schema-v1 daily MTM made late_strong EV regress and the result did "
        "not beat either accepted candidate-pool PnL comparator. The relation "
        "is too sparse and weak for a shared helper; no strategy code is retained."
    )


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    interpretation = _interpretation(payload)
    status = "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected"
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": _utc_now(),
            "status": status,
            "decision": gate4["decision"],
            "accepted": False,
            "accepted_alpha": False,
            "numeric_gate4_passed": gate4["passed"],
            "full_stack_verdict": "pending" if gate4["passed"] else "reject",
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "candidate_pool_full_stack",
            "implementation_mode": "full_stack_attempt_shared_retention_conditional_on_gate4",
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_dod_contract_award_candidate_pool",
            "new_evidence_type": "pit_award_economics_relation_field",
            "new_evidence_axis": (
                "The exp-20260711-020/023 reflections explicitly require richer "
                "award economics: new-contract versus modification/ceiling "
                "decomposition plus issuer revenue/backlog normalization. This "
                "run joins the official event to latest-filed annual SEC revenue."
            ),
            "nearby_prior_experiments": ["exp-20260711-020", "exp-20260711-023"],
            "prior_trial_count": 2,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "interpretation": interpretation,
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
        }
    )
    payload["calibration"] = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "actual_success": bool(gate4["passed"]),
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
        "predicted_failure_modes": PREDICTION["main_failure_modes"],
        "predicted_failure_mode_hit": any(
            mode in ";".join(gate4["failed_reasons"])
            for mode in PREDICTION["main_failure_modes"]
        ),
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2,
            6,
        ),
    }
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "event_scope": "new_contract_excludes_modification_ceiling_idiq_option_existing_order_v1",
        "candidate_rank": "award_total_usd/latest_filed_annual_revenue_usd descending",
        "absolute_award_threshold": None,
        "max_revenue_fact_age_days": MAX_REVENUE_FACT_AGE_DAYS,
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"]["announcement_source"] = _repo_rel(SOURCE_EVENTS_JSON)
    payload["backtest_protocol"]["revenue_source"] = _repo_rel(
        companyfacts.RAW_COMPANYFACTS_CACHE
    )
    payload["backtest_protocol"]["current_metric_schema"] = (
        "sharpe_inference_v1_daily_paper_mtm"
    )
    payload["measurement_repairs_during_run"] = [
        (
            "Reparsed the existing 379 cached official articles read-only because "
            "exp-20260711-020 compacted sub-$250M rows without classification text."
        ),
        (
            "Replaced the legacy exit-day-only paper curve with schema-v1 daily "
            "mark-to-market, half-cost recognition while open, final liquidation "
            "costs, and persisted PSR return evidence."
        ),
    ]
    payload["gate2"]["runtime_fields"] = [
        "official DoD announcement publication timestamp and parsed contract text",
        "award_total_usd",
        "any_modification and existing-vehicle language classifier",
        "SEC annual revenue value, period end, tag, and filed date <= event date",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume and SPY confirmation",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "Do not retry DoD award thresholds, award/market-cap ratios, contractor/"
        "branch/peer lists, absorption thresholds, top-N, hold, cooldown, or "
        "notional. Reopen only with obligated-versus-ceiling data from a second "
        "PIT source, segment/backlog normalization, or materially settled "
        "forward replacement rows from a fixed shared helper."
    )
    payload["post_run_reflection"] = {
        "why_result_happened": interpretation,
        "outcome_summary": (
            "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}; max "
            "drawdown drift {:+.4f}; {} paper trades.".format(
                aggregate["expected_value_score_delta_sum"],
                aggregate["total_pnl_delta_sum"],
                float(aggregate["max_drawdown_delta_max"] or 0.0),
                payload["target_trade_summary"]["total_trade_count"],
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by changing award/revenue cutoffs, absolute award "
            "thresholds, event text exclusions, contractor/peer lists, "
            "absorption thresholds, top-N, hold, cooldown, or notional."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
    }
    payload["calibration"]["surprise_note"] = (
        "The preflight counted revenue coverage but did not predict that the "
        "unchanged absorption gate would reduce 98 eligible new-contract rows to "
        "8 trades. Daily MTM also changed late_strong from nominally positive PnL "
        "to negative incremental EV, reinforcing rejection."
    )
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(SOURCE_EVENTS_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
    ]
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    rows = [
        f"# {EXPERIMENT_ID} DoD New-Contract Revenue Materiality",
        "",
        f"Status: `{payload['status']}`",
        f"Decision: `{payload['decision']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Gate 4",
        "",
        "| Window | EV delta | PnL delta | Drawdown delta | Trades |",
        "|---|---:|---:|---:|---:|",
    ]
    for label in prior.runner.base.framework.WINDOWS:
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {ev:+.4f} | ${pnl:+,.2f} | {dd:+.4f} | {trades} |".format(
                label=label,
                ev=delta.get("expected_value_score", 0.0),
                pnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    rows.extend(
        [
            "",
            f"- Aggregate EV delta: `{aggregate['expected_value_score_delta_sum']:+.4f}`",
            f"- Aggregate PnL delta: `${aggregate['total_pnl_delta_sum']:+,.2f}`",
            f"- Target trades: `{payload['target_trade_summary']['total_trade_count']}`",
            f"- Failed reasons: `{', '.join(payload['gate4']['failed_reasons']) or 'none'}`",
            "",
            "## Production Impact",
            "",
            "Default-off research only; no live/default orders, core signals, ranking, sizing, or exits changed.",
        ]
    )
    return "\n".join(rows) + "\n"


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "allowed_write_scope": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            "scripts/experiment_fingerprint.py",
            "quant/test_experiment_fingerprint.py",
            "docs/frozen_families.jsonl",
        ],
        "file_hashes": {
            _repo_rel(Path(__file__)): prior.runner.base.framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): prior.runner.base.framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): prior.runner.base.framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): prior.runner.base.framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): prior.runner.base.framework._sha256(CARD_MD),
            "scripts/experiment_fingerprint.py": prior.runner.base.framework._sha256(
                REPO_ROOT / "scripts" / "experiment_fingerprint.py"
            ),
            "quant/test_experiment_fingerprint.py": prior.runner.base.framework._sha256(
                REPO_ROOT / "quant" / "test_experiment_fingerprint.py"
            ),
            "docs/frozen_families.jsonl": prior.runner.base.framework._sha256(
                REPO_ROOT / "docs" / "frozen_families.jsonl"
            ),
        },
    }
    prior.runner.base.framework._write_json(MANIFEST_JSON, manifest)


def _persist_payload(payload: dict[str, Any]) -> None:
    """Persist through the sanctioned registry helper; JSONL is derived."""

    framework = prior.runner.base.framework
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, payload)
    framework._write_text(CARD_MD, _build_card(payload))
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": payload["delta_metrics"]["aggregate"][
            "expected_value_score_delta_sum"
        ],
        "aggregate_strategy_total_pnl_delta": payload["delta_metrics"]["aggregate"][
            "total_pnl_delta_sum"
        ],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "decision": payload["decision"],
        "summary": payload["interpretation"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": result["aggregate_expected_value_delta"],
        "aggregate_strategy_total_pnl_delta": result[
            "aggregate_strategy_total_pnl_delta"
        ],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )
    _write_manifest(payload)


def _install() -> None:
    prior.EXPERIMENT_ID = EXPERIMENT_ID
    prior.STEM = STEM
    prior.TRIAL_FAMILY = TRIAL_FAMILY
    prior.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    prior.CHANGED_VARIABLE = CHANGED_VARIABLE
    prior.RULE_VERSION = RULE_VERSION
    prior.OWNER = OWNER
    prior.OUT_DIR = OUT_DIR
    prior.OUT_JSON = OUT_JSON
    prior.LOG_JSON = LOG_JSON
    prior.TICKET_JSON = TICKET_JSON
    prior.CARD_MD = CARD_MD
    prior.MANIFEST_JSON = MANIFEST_JSON
    prior.PREDICTION = PREDICTION
    prior.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    prior.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    prior._EVENT_INDEX_CACHE = None
    prior._load_event_index = _load_event_index
    prior._build_quality_index = _build_quality_index
    prior._candidate_rows_for_window = _candidate_rows_for_window
    prior._gate4 = _gate4
    prior._postprocess_payload = _postprocess_payload
    prior._build_card = _build_card
    prior._write_manifest = _write_manifest
    prior.runner._persist = _persist_payload
    prior.runner.base.framework.sleeve._overlay_from_paper_trades = (
        _overlay_from_paper_trades_current_mtm
    )
    prior.runner.base.framework.overlay_helper._metrics = _metrics_current
    prior.runner.base.framework.overlay_helper._metrics_with_overlay = (
        _metrics_with_overlay_current
    )


def main() -> None:
    _install()
    if len(sys.argv) > 1 and sys.argv[1] == "persist-existing":
        payload = json.loads(OUT_JSON.read_text(encoding="utf-8"))
        payload = _postprocess_payload(payload)
        _persist_payload(payload)
        print(
            json.dumps(
                {
                    "experiment_id": payload["experiment_id"],
                    "status": payload["status"],
                    "decision": payload["decision"],
                    "timestamp": payload["timestamp"],
                },
                indent=2,
            )
        )
        return
    prior.main()


if __name__ == "__main__":
    main()
