"""exp-20260617-020: broad SEC filing-timeliness candidate scout.

Replay-only alpha search. The single decision hypothesis is the exact SEC
EDGAR/Companyfacts timing field from exp-20260617-019, but evaluated over the
broad liquid warehouse universe instead of the underpowered core universe:
companies that file their latest annual report (10-K) ABNORMALLY EARLY versus
their own trailing filing-lag norm may exhibit positive post-filing drift,
because faster disclosure proxies clean books / management confidence (the
Griffin 2003 / filing-delay anomaly, inverted) and the market underreacts to
the timeliness signal itself.

Why this is a materially new free-data edge: the accepted fundamental source
exp-20260528-016 used filing RECENCY (how fresh the latest operating-income
fact is). This is different: it compares the latest 10-K's filed-minus-period-
end lag against the SAME company's trailing-average lag, so the signal is
disclosure PROMPTNESS, not freshness, and not a relief/overhang ratio. The
event fires on the first trading day on/after the abnormally-early filed date.

Deliberately NOT a threshold retry: exp-20260617-019 failed on core scope and
explicitly sanctioned only the same fixed gate over the broad liquid universe.
Only a light liquidity gate (price, dollar-volume) is applied; no SPY-relative
leadership filter is required.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. A positive result is
only a replay lead until a shared historical/daily helper reproduces it.
No JavaScript is used.
"""

from __future__ import annotations

import bisect
import json
import sqlite3
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import exp_20260614_020_accruals_cash_conversion_quality as base


EXPERIMENT_ID = "exp-20260617-020"
STEM = "filing_timeliness_broad_early_disclosure"
TRIAL_FAMILY = "free_sec_companyfacts_filing_timeliness_broad_candidate_pool"
TRIAL_VARIANT_ID = "broad_annual_10k_early_filing_vs_own_norm_top1_next_open_10d_v1"
CHANGED_VARIABLE = "sec_filing_timeliness_broad_early_disclosure_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = base.REPO_ROOT
RAW_COMPANYFACTS_CACHE = REPO_ROOT / "data" / "cache" / "sec" / "companyfacts"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260617_020_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = base.BASE_NOTIONAL_USD
HOLD_DAYS = base.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = base.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = base.SAME_TICKER_COOLDOWN_DAYS

FY_DURATION_MIN = 340
FY_DURATION_MAX = 380
MIN_FILING_LAG_DAYS = 5
MAX_FILING_LAG_DAYS = 180
MIN_PRIOR_ANNUAL_FILINGS = 3       # need >=3 prior 10-Ks to define a trailing norm
MIN_EARLINESS_DAYS = 7.0           # filed >=7 days earlier than own trailing avg
MAX_CURRENT_LAG_DAYS = 100         # tradable accelerated/large-filer range
MAX_EVENT_AGE_TRADING_DAYS = 5     # enter within 5 trading days of the filing

# Light liquidity gate only (NO momentum/SPY-relative filter).
MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0

REVENUE_TAGS = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
)
ANNUAL_FORMS = {"10-K", "10-K/A"}

PREDICTION = {
    "success_probability": 0.24,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "broad_universe_adds_noise",
        "old_thin_window_regression",
        "drawdown_drift",
        "accepted_distribution_comparator_not_beaten",
    ],
    "confidence_reason": (
        "The prior core-universe filing timeliness scout failed but explicitly "
        "identified underpowered scope as the blocker: about 1713 broad liquid "
        "early-filing events exist versus 18 core trades. The field is PIT-safe, "
        "free SEC Companyfacts filed-date timing, distinct from filing recency "
        "and recent overhang ratios, but broad event breadth may add noise and "
        "still fail old_thin/drawdown/comparator guards."
    ),
    "recorded_at": "2026-06-17T17:03:34+00:00",
}

PRODUCTION_IMPACT = {
    **base.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "execution_envelope": {
        **base.PRODUCTION_IMPACT["execution_envelope"],
        "liquidity_source": "price >= $10 and ADV20 >= $50M from PIT OHLCV (no momentum gate)",
        "failure_handling": (
            "missing raw SEC annual 10-K filing history, fewer than 3 prior "
            "annual filings, missing CIK mapping, missing OHLCV, missing next "
            "open, or missing 10d exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only a "
        "replay lead until a shared default-off helper computes the same PIT "
        "annual 10-K filed-lag history, abnormally-early-vs-own-norm gate, light "
        "liquidity gate, cooldown, next-open paper entry, 10-day exit, costs, and "
        "concentration controls in both historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: broad liquid-universe companies whose latest annual "
        "10-K is filed abnormally early versus their own trailing filing-lag "
        "norm may drift up over the next 10 trading days, because prompt "
        "disclosure proxies clean books / management confidence and the market "
        "underreacts to the timeliness signal. Tested with the same fixed gate "
        "as exp-20260617-019, only changing the candidate universe scope from "
        "core to broad liquid."
    ),
    "2_history_check": {
        "exp-20260617-019": (
            "Rejected core-universe early 10-K filing scout. Its closeout "
            "explicitly says the only sanctioned next step is the same fixed "
            "gate over the BROAD liquid universe; threshold and core-universe "
            "retries are forbidden."
        ),
        "exp-20260528-016": (
            "Accepted filing RECENCY support inside fundamental_growth_rs (how "
            "fresh the latest operating-income fact is). This run tests filing "
            "PROMPTNESS vs the company's own historical lag, a different field."
        ),
        "exp-20260616-015": (
            "Accepted SBC burden improvement as a momentum-confirmed Companyfacts "
            "quality pool. This run is event-driven and deliberately drops the "
            "price-confirmation gate."
        ),
        "exp-20260617-007": (
            "Rejected CapEx/D&A reinvestment cycle on old_thin/drawdown despite "
            "positive aggregate EV; representative of the price-confirmed quality "
            "pool failure mode this run tries to avoid by event timing."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Aggregate EV/PnL must "
        "be positive, no window EV/PnL regression, at least two EV-improved "
        "windows, at least 20 paper trades across all 3 windows, survival >=5%, "
        "drawdown drift <=0.5pp, concentration pass, and accepted compression/"
        "distribution candidate-pool comparators must be beaten. Replay-only "
        "positives are leads until shared daily/backtest parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260617_020_filing_timeliness_broad_early_disclosure.py"
    ),
}

_RAW_INDEX_CACHE: tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, Any]] | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return base._round(value, digits)


def _d10(value: Any) -> str:
    text = str(value or "")[:10]
    return text if len(text) == 10 and text[4] == "-" and text[7] == "-" else ""


def _annual_filing_lags(usgaap: dict[str, Any]) -> list[dict[str, Any]]:
    """Distinct annual 10-K filings as {end, filed, lag} sorted by filed asc.

    Anchored on revenue FY facts (form 10-K, FY duration). For each fiscal-year
    end the EARLIEST filed date (the original 10-K, not amendments) is kept.
    """
    by_end: dict[str, str] = {}
    for tag in REVENUE_TAGS:
        for arr in usgaap.get(tag, {}).get("units", {}).values():
            if not isinstance(arr, list):
                continue
            for raw in arr:
                if str(raw.get("fp") or "").upper() != "FY":
                    continue
                if str(raw.get("form") or "").upper() not in ANNUAL_FORMS:
                    continue
                end = _d10(raw.get("end"))
                filed = _d10(raw.get("filed"))
                start = _d10(raw.get("start"))
                if not end or not filed or not start:
                    continue
                dur = (date.fromisoformat(end) - date.fromisoformat(start)).days
                if not (FY_DURATION_MIN <= dur <= FY_DURATION_MAX):
                    continue
                lag = (date.fromisoformat(filed) - date.fromisoformat(end)).days
                if not (MIN_FILING_LAG_DAYS <= lag <= MAX_FILING_LAG_DAYS):
                    continue
                prev = by_end.get(end)
                if prev is None or filed < prev:
                    by_end[end] = filed
    filings = [
        {
            "end": end,
            "filed": filed,
            "lag": (date.fromisoformat(filed) - date.fromisoformat(end)).days,
        }
        for end, filed in by_end.items()
    ]
    filings.sort(key=lambda r: (r["filed"], r["end"]))
    return filings


def _load_raw_companyfacts_index() -> tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, Any]]:
    global _RAW_INDEX_CACHE
    if _RAW_INDEX_CACHE is not None:
        return _RAW_INDEX_CACHE
    stats: Counter[str] = Counter()
    ticker_ciks: dict[str, int] = {}
    warehouse_uri = f"file:{Path(base.framework.WAREHOUSE).resolve().as_posix()}?mode=ro&immutable=1"
    with sqlite3.connect(warehouse_uri, uri=True) as con:
        rows = con.execute(
            """
            select u.ticker, u.cik
            from ticker_universe u
            join coverage_summary c on c.ticker = u.ticker
            where u.hygiene_pass = 1
              and c.all_windows_full_liquid = 1
              and u.cik is not null
            order by u.ticker
            """
        ).fetchall()
    for ticker, cik in rows:
        try:
            ticker_ciks[str(ticker).upper()] = int(cik)
        except (TypeError, ValueError):
            stats["invalid_cik_rows"] += 1
    index: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for ticker, cik in ticker_ciks.items():
        stats["warehouse_tickers_with_cik"] += 1
        path = RAW_COMPANYFACTS_CACHE / f"CIK{cik:010d}.json"
        if not path.exists():
            stats["missing_companyfacts_cache_file"] += 1
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            stats["unreadable_companyfacts_cache_file"] += 1
            continue
        usgaap = payload.get("facts", {}).get("us-gaap", {})
        filings = _annual_filing_lags(usgaap)
        if len(filings) < MIN_PRIOR_ANNUAL_FILINGS + 1:
            stats["tickers_with_insufficient_filing_history"] += 1
            continue
        index[ticker] = {"filings": filings}
        stats["tickers_with_filing_history"] += 1
        stats["annual_filing_count"] += len(filings)
    summary = {
        "raw_companyfacts_cache": _repo_rel(RAW_COMPANYFACTS_CACHE),
        "warehouse_source": _repo_rel(base.framework.WAREHOUSE),
        "candidate_universe_scope": "broad_liquid_warehouse_all_windows_full_liquid",
        "revenue_tags": list(REVENUE_TAGS),
        "min_prior_annual_filings": MIN_PRIOR_ANNUAL_FILINGS,
        **dict(stats),
    }
    _RAW_INDEX_CACHE = (index, summary)
    return _RAW_INDEX_CACHE


def _build_quality_index(
    companyfacts_rows: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, Any]]:
    index, summary = _load_raw_companyfacts_index()
    return index, {
        **summary,
        "selected_companyfacts_rows_ignored": len(companyfacts_rows),
        "field_source": "raw_sec_companyfacts_cache_not_selected_sidecar",
    }


def _load_broad_window_snapshot(
    *,
    cfg: dict[str, str],
    eligible_tickers: set[str],
) -> dict[str, list[dict[str, Any]]]:
    """Load broad liquid candidate OHLCV while keeping the core baseline fixed.

    ``base._build_payload`` passes the core baseline universe into this helper.
    For exp020 we intentionally ignore that candidate argument and replay the
    same filing-timeliness gate over the broad liquid SEC/warehouse universe.
    """
    index, _summary = _load_raw_companyfacts_index()
    start = base.framework._parse_date(cfg["start"]) - timedelta(days=120)
    end = base.framework._parse_date(cfg["end"]) + timedelta(days=40)
    tickers = sorted(set(index) | {"SPY", "QQQ"})
    snapshot: dict[str, list[dict[str, Any]]] = {ticker: [] for ticker in tickers}
    warehouse_uri = f"file:{Path(base.framework.WAREHOUSE).resolve().as_posix()}?mode=ro&immutable=1"
    with sqlite3.connect(warehouse_uri, uri=True) as con:
        for chunk_start in range(0, len(tickers), 800):
            chunk = tickers[chunk_start : chunk_start + 800]
            placeholders = ",".join("?" for _ in chunk)
            sql = (
                "select ticker, date, open, high, low, close, volume "
                "from ohlcv "
                f"where ticker in ({placeholders}) and date >= ? and date <= ? "
                "order by ticker, date"
            )
            params = [*chunk, base.framework._date_str(start), base.framework._date_str(end)]
            for row in con.execute(sql, params):
                ticker, day, open_, high, low, close, volume = row
                snapshot[str(ticker).upper()].append(
                    {
                        "Date": str(day)[:10],
                        "Open": float(open_),
                        "High": float(high),
                        "Low": float(low),
                        "Close": float(close),
                        "Volume": float(volume),
                    }
                )
    return {ticker: rows for ticker, rows in snapshot.items() if rows}


def _early_filing_events(filings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each abnormally-early annual filing vs the company's trailing-avg lag."""
    events: list[dict[str, Any]] = []
    for i, filing in enumerate(filings):
        prior = [f for f in filings[:i] if f["filed"] < filing["filed"]]
        if len(prior) < MIN_PRIOR_ANNUAL_FILINGS:
            continue
        trailing_avg = sum(f["lag"] for f in prior) / len(prior)
        current_lag = filing["lag"]
        if current_lag > MAX_CURRENT_LAG_DAYS:
            continue
        earliness = trailing_avg - current_lag
        if earliness < MIN_EARLINESS_DAYS:
            continue
        events.append(
            {
                "filed": filing["filed"],
                "fiscal_year_end": filing["end"],
                "current_lag_days": current_lag,
                "trailing_avg_lag_days": _round(trailing_avg, 4),
                "earliness_days": _round(earliness, 4),
                "prior_filing_count": len(prior),
            }
        )
    return events


def _light_confirmation(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    ticker: str,
    signal_date: str,
) -> dict[str, Any] | None:
    rows = base.framework.shadow._series(snapshot, ticker)
    spy_rows = base.framework.shadow._series(snapshot, "SPY")
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or idx < 60:
        return None
    if idx + HOLD_DAYS >= len(rows):
        return None
    close = base.framework._value(rows[idx], "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = base.framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None
    ret20 = base.framework._ret(rows, idx, 20)
    ret60 = base.framework._ret(rows, idx, 60)
    close_location = base.framework._close_location(rows[idx])
    ret20_excess = None
    if spy_idx is not None and spy_idx >= 60 and ret20 is not None:
        spy_ret20 = base.framework._ret(spy_rows, spy_idx, 20)
        if spy_ret20 is not None:
            ret20_excess = ret20 - spy_ret20
    return {
        "candidate_close": _round(close, 4),
        "candidate_avg_dollar_volume_20d": _round(adv20, 2),
        "candidate_ret20": _round(ret20, 6) if ret20 is not None else None,
        "candidate_ret60": _round(ret60, 6) if ret60 is not None else None,
        "candidate_ret20_excess_spy": _round(ret20_excess, 6) if ret20_excess is not None else None,
        "candidate_close_location": _round(close_location, 6) if close_location is not None else None,
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    sector_entries: dict[str, dict[str, Any]],
    quality_index: dict[str, dict[str, list[dict[str, Any]]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    indices = {
        ticker: base.framework.shadow._row_index(base.framework.shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    dates = base.framework.shadow._trading_dates(snapshot)
    start = str(cfg["start"])
    end = str(cfg["end"])
    eligible = sorted(set(quality_index) & set(snapshot))
    scan: Counter[str] = Counter()
    scan["eligible_history_tickers"] = len(eligible)
    candidates: list[dict[str, Any]] = []
    for ticker in eligible:
        events = _early_filing_events(quality_index[ticker]["filings"])
        scan["early_filing_events"] += len(events)
        for event in events:
            filed = event["filed"]
            pos = bisect.bisect_left(dates, filed)
            if pos >= len(dates):
                scan["event_after_last_trading_day"] += 1
                continue
            signal_date = dates[pos]
            # event must be fresh: first trading session on/after the filed date,
            # and not separated from it by an unusually long market closure.
            if (date.fromisoformat(signal_date) - date.fromisoformat(filed)).days > 7:
                scan["event_after_long_market_gap"] += 1
                continue
            if not (start <= signal_date <= end):
                scan["event_outside_window"] += 1
                continue
            confirm = _light_confirmation(
                snapshot=snapshot,
                indices=indices,
                ticker=ticker,
                signal_date=signal_date,
            )
            if confirm is None:
                scan["failed_light_liquidity_gate"] += 1
                continue
            scan["qualified_candidate_rows"] += 1
            meta = sector_entries.get(ticker, {})
            score = (
                1.00 * min(float(event["earliness_days"]), 60.0)
                + 0.20 * max(0.0, MAX_CURRENT_LAG_DAYS - float(event["current_lag_days"]))
            )
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "SEC_FILING_TIMELINESS_EARLY_DISCLOSURE_PAPER",
                    "candidate_score": _round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": "annual_10k_filed_date_and_signal_close_before_next_open_paper_entry",
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "uses_free_sec_companyfacts": True,
                    "uses_raw_sec_companyfacts_cache": True,
                    "uses_free_ohlcv": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    **{f"timeliness_{k}": v for k, v in event.items()},
                    **confirm,
                }
            )
    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in candidates:
        key = (row["date"], row["ticker"])
        existing = deduped.get(key)
        if existing is None or float(row["candidate_score"]) > float(existing["candidate_score"]):
            deduped[key] = row
    rows = list(deduped.values())
    rows.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"] or 0.0),
            -float(row["timeliness_earliness_days"] or 0.0),
            float(row["timeliness_current_lag_days"] or 0.0),
            -float(row.get("candidate_avg_dollar_volume_20d") or 0.0),
            row["ticker"],
        )
    )
    scan["deduped_candidate_rows"] = len(rows)
    scan["candidate_signal_days"] = len({row["date"] for row in rows})
    scan["candidate_tickers"] = len({row["ticker"] for row in rows})
    # framework card expects 'eligible_quality_tickers'
    scan["eligible_quality_tickers"] = len(eligible)
    return rows, {
        **dict(scan),
        "rule_version": RULE_VERSION,
        "min_prior_annual_filings": MIN_PRIOR_ANNUAL_FILINGS,
        "min_earliness_days": MIN_EARLINESS_DAYS,
        "max_current_lag_days": MAX_CURRENT_LAG_DAYS,
        "max_event_age_trading_days": MAX_EVENT_AGE_TRADING_DAYS,
        "min_price": MIN_PRICE,
        "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
    }


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = base.framework._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = list(gate.get("failed_reasons") or [])
    ev_delta = float(aggregate["expected_value_score_delta_sum"] or 0.0)
    pnl_delta = float(aggregate["total_pnl_delta_sum"] or 0.0)
    if ev_delta <= base.COMPRESSION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_compression_ev_not_beaten")
    if pnl_delta <= base.COMPRESSION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_compression_pnl_not_beaten")
    if ev_delta <= base.DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_distribution_ev_not_beaten")
    if pnl_delta <= base.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_distribution_pnl_not_beaten")
    gate["failed_reasons"] = failed
    gate["accepted_compression_comparator"] = base.COMPRESSION_COMPARATOR
    gate["accepted_distribution_comparator"] = base.DISTRIBUTION_COMPARATOR
    gate["passed"] = not failed
    gate["decision"] = (
        "positive_replay_lead_not_promoted_broad_filing_timeliness_early_disclosure"
        if gate["passed"]
        else "rejected_broad_filing_timeliness_early_disclosure_candidate_pool"
    )
    return gate


def _load_companyfacts_rows_stub(*_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
    return []


def _configure_base() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.RULE_VERSION = RULE_VERSION
    base.OWNER = OWNER
    base.OUT_DIR = OUT_DIR
    base.OUT_JSON = OUT_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.CARD_MD = CARD_MD
    base.MANIFEST_JSON = MANIFEST_JSON
    base.EXPERIMENT_LOG = EXPERIMENT_LOG
    base.REGISTRY_JSON = REGISTRY_JSON
    base.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    base.HOLD_DAYS = HOLD_DAYS
    base.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    base.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    base.FY_DURATION_MIN = FY_DURATION_MIN
    base.FY_DURATION_MAX = FY_DURATION_MAX
    base.PREDICTION = PREDICTION
    base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    base.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    base.load_companyfacts_rows = _load_companyfacts_rows_stub
    base._load_window_snapshot = _load_broad_window_snapshot
    base._build_quality_index = _build_quality_index
    base._candidate_rows_for_window = _candidate_rows_for_window
    base._gate4 = _gate4


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    status = "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected"
    if gate4["passed"]:
        interpretation = (
            "The broad liquid-universe SEC filing-timeliness early-disclosure "
            "source cleared the numeric three-window replay screen with the same "
            "fixed gate from exp-20260617-019, but remains only a replay lead "
            "because no shared daily/backtest helper was promoted."
        )
    else:
        interpretation = (
            "The broad liquid-universe SEC filing-timeliness early-disclosure "
            f"source did not clear Gate 4 (failed: {', '.join(gate4['failed_reasons']) or 'none'}). "
            "This directly tests the breadth caveat from exp-20260617-019: the "
            "same fixed early-10-K-vs-own-history gate is now replayed over the "
            "broad liquid SEC/warehouse universe instead of the core snapshot. "
            "The result is not retained or promoted."
        )
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": _utc_now(),
            "status": status,
            "decision": gate4["decision"],
            "accepted": False,
            "accepted_alpha": False,
            "numeric_gate4_passed": gate4["passed"],
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "default_off_paper_candidate_pool_replay_scout",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": (
                "production_visible_free_sec_companyfacts_filing_timeliness_candidate_pool"
            ),
            "new_evidence_type": "sec_annual_10k_filing_timeliness_vs_own_norm_pit_event",
            "nearby_prior_experiments": [
                "exp-20260617-019",
                "exp-20260528-016",
                "exp-20260616-015",
                "exp-20260617-007",
            ],
            "prior_trial_count": 0,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "interpretation": interpretation,
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["calibration"] = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "actual_success": 1 if gate4["passed"] else 0,
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2,
            6,
        ),
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
    }
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "fy_duration_min": FY_DURATION_MIN,
        "fy_duration_max": FY_DURATION_MAX,
        "min_filing_lag_days": MIN_FILING_LAG_DAYS,
        "max_filing_lag_days": MAX_FILING_LAG_DAYS,
        "min_prior_annual_filings": MIN_PRIOR_ANNUAL_FILINGS,
        "min_earliness_days": MIN_EARLINESS_DAYS,
        "max_current_lag_days": MAX_CURRENT_LAG_DAYS,
        "max_event_age_trading_days": MAX_EVENT_AGE_TRADING_DAYS,
        "min_price": MIN_PRICE,
        "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
        "revenue_tags": list(REVENUE_TAGS),
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"]["execution_model"] = (
        "Annual 10-K filings are read from raw SEC Companyfacts (revenue FY "
        "facts, form 10-K) and known only by filed date. For each company with "
        ">=3 prior annual filings, the latest 10-K's filed-minus-fiscal-year-end "
        "lag is compared to the trailing average of prior filings; an event "
        "fires when the latest filing is >=7 days earlier than the company's own "
        "norm and the current lag is <=100 days. The signal date is the first "
        "trading day on/after the filed date (within 5 trading days). Only a "
        "light liquidity gate (price >= $10, ADV20 >= $50M) is applied; no "
        "SPY-relative momentum filter. Paper entry is the next available open "
        "with entry slippage; exit is the close 10 trading days after the signal "
        "with target-side sell slippage and ROUND_TRIP_COST_PCT."
    )
    payload["backtest_protocol"]["companyfacts_source"] = _repo_rel(RAW_COMPANYFACTS_CACHE)
    payload["gate2"]["runtime_fields"] = [
        "raw SEC companyfacts annual 10-K revenue facts (form/fp/start/end/filed)",
        "derived annual filing-lag history per company",
        "warehouse ticker_universe CIK mapping",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV (descriptive only, not a filter)",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "The broad-universe scope caveat has now been tested. If this fixed "
        "bundle fails, do not retry by sweeping earliness-days, current-lag cap, "
        "prior-filing-count, event-age, price/ADV liquidity floors, FY duration, "
        "top-N, hold days, cooldown, notional, or broad/core scope. A valid retry "
        "needs a materially different disclosure-timing field (quarterly 10-Q "
        "timeliness, accelerated-filer-status change, NT 10-K late-filing "
        "notices, segment/customer disclosure timing) or closed forward "
        "replacement-value rows."
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
            "Do not retry by sweeping earliness-days, current-lag cap, "
            "prior-filing-count, event-age, price/ADV liquidity floors, FY "
            "duration, top-N, hold days, cooldown, notional, or candidate-universe "
            "scope for this fixed annual 10-K early-filing bundle."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
    }
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(EXPERIMENT_LOG),
        _repo_rel(REGISTRY_JSON),
    ]
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Eligible | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {elig} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                elig=scan.get("eligible_quality_tickers", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} SEC Filing-Timeliness Early Disclosure",
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
            *rows,
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(aggregate["expected_value_score_delta_sum"]),
            "- Aggregate PnL delta: `${:+,.2f}`".format(aggregate["total_pnl_delta_sum"]),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Accepted compression comparator: EV `{:+.4f}`, PnL `${:+,.2f}`".format(
                base.COMPRESSION_COMPARATOR["aggregate_expected_value_delta"],
                base.COMPRESSION_COMPARATOR["aggregate_pnl_delta"],
            ),
            "- Accepted distribution comparator: EV `{:+.4f}`, PnL `${:+,.2f}`".format(
                base.DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"],
                base.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"],
            ),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
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


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(Path(__file__)): base.framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): base.framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): base.framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): base.framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): base.framework._sha256(CARD_MD),
        },
    }
    base.framework._write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any]) -> None:
    log_record = base._build_log_record(payload)
    base.framework._write_json(OUT_JSON, payload)
    base.framework._write_json(LOG_JSON, payload)
    base.framework._write_text(CARD_MD, _build_card(payload))
    base.framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
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
        "aggregate_expected_value_delta": log_record["aggregate_expected_value_delta"],
        "aggregate_strategy_total_pnl_delta": log_record["aggregate_strategy_total_pnl_delta"],
    }
    base.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )
    _write_manifest(payload)


def main() -> None:
    _configure_base()
    payload = _postprocess_payload(base._build_payload())
    _persist(payload)
    print(json.dumps(base.framework._safe(base._build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
