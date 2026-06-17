"""exp-20260617-016: AOCI overhang relief candidate scout.

Replay-only alpha search. The single decision hypothesis is a PIT free SEC
Companyfacts candidate source: production-universe names whose accumulated
other comprehensive income loss burden is falling versus assets/equity may have
hidden mark-to-market balance-sheet overhang easing. Liquid SPY-relative
leadership then tests whether price is starting to recognize that relief before
a next-open, 10-trading-day default-off paper continuation trade.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. A positive replay is
only a lead until a shared historical/daily helper reproduces the exact PIT
field mapping. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260614_020_accruals_cash_conversion_quality as base
import exp_20260616_003_raw_sec_rd_intensity_candidate_pool as rd


EXPERIMENT_ID = "exp-20260617-016"
STEM = "aoci_overhang_relief"
TRIAL_FAMILY = "aoci_overhang_relief_candidate_pool"
TRIAL_VARIANT_ID = "aoci_overhang_relief_top1_next_open_10d_v1"
CHANGED_VARIABLE = "raw_sec_companyfacts_aoci_overhang_relief_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = base.REPO_ROOT
RAW_COMPANYFACTS_CACHE = REPO_ROOT / "data" / "cache" / "sec" / "companyfacts"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260617_016_{STEM}.json"
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

FY_DURATION_MIN = base.FY_DURATION_MIN
FY_DURATION_MAX = base.FY_DURATION_MAX
MAX_AOCI_FACT_AGE_DAYS = 430
MIN_CURRENT_ASSETS = 500_000_000.0
MIN_CURRENT_EQUITY = 100_000_000.0
MIN_PRIOR_AOCI_LOSS = 25_000_000.0
MIN_PRIOR_AOCI_TO_ASSETS = 0.005
MAX_CURRENT_AOCI_TO_ASSETS = 0.30
MAX_CURRENT_AOCI_TO_EQUITY = 1.00
MIN_AOCI_ASSET_RATIO_RELIEF = 0.0015
MIN_AOCI_RELIEF_PCT = 0.10
MIN_PERIOD_GAP_DAYS = 250
MAX_PERIOD_GAP_DAYS = 460

AOCI_TAGS = (
    "AccumulatedOtherComprehensiveIncomeLossNetOfTax",
    "AccumulatedOtherComprehensiveIncomeLoss",
    "AccumulatedOtherComprehensiveIncome",
)
ASSET_TAGS = ("Assets",)
EQUITY_TAGS = (
    "StockholdersEquity",
    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    "CommonStocksIncludingAdditionalPaidInCapital",
)

PREDICTION = {
    "success_probability": 0.12,
    "expected_ev_delta": 0.12,
    "expected_pnl_delta": 1800.0,
    "main_failure_modes": [
        "field_is_macro_accounting_noise",
        "window_regression",
        "drawdown_drift",
        "target_concentration_failed",
        "accepted_distribution_comparator_not_beaten",
    ],
    "confidence_reason": (
        "AOCI burden relief is a distinct official filed-date SEC balance-"
        "sheet overhang field with broad coverage and no matching history hit, "
        "but recent Companyfacts burden-relief scouts frequently failed "
        "old_thin, concentration, or accepted comparator gates."
    ),
    "recorded_at": "2026-06-17T14:08:44+00:00",
}

PRODUCTION_IMPACT = {
    **base.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "uses_free_sec_companyfacts": True,
    "uses_raw_companyfacts_cache": True,
    "execution_envelope": {
        **base.PRODUCTION_IMPACT["execution_envelope"],
        "failure_handling": (
            "missing raw SEC AOCI, assets, or equity facts, missing prior AOCI "
            "comparison point, stale facts, missing CIK mapping, missing OHLCV, "
            "missing next open, or missing 10d exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same raw "
        "SEC AOCI/assets/equity tag mapping, filed-date PIT balance-sheet "
        "normalization, liquid SPY-relative confirmation, cooldown, "
        "next-open paper entry, 10-day exit, costs, and concentration controls "
        "in both historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: raw SEC Companyfacts accumulated other comprehensive "
        "income loss burden falling versus assets/equity may identify companies "
        "where hidden mark-to-market balance-sheet overhang is easing; liquid "
        "SPY-relative leadership then tests whether the market is recognizing "
        "that relief before a 10-trading-day continuation leg."
    ),
    "2_history_check": {
        "exp-20260616-025": (
            "Rejected operating lease burden relief. This run avoids lease "
            "obligations and tests accumulated OCI mark-to-market overhang."
        ),
        "exp-20260616-029": (
            "Rejected principal debt burden relief despite high aggregate EV "
            "because old_thin and drawdown failed. This run is not debt service "
            "or leverage relief."
        ),
        "exp-20260617-013": (
            "Rejected deferred-tax valuation allowance release on sample and "
            "concentration. This run tests OCI mark-to-market losses, not tax "
            "asset confidence."
        ),
        "exp-20260617-015": (
            "Rejected pension/postretirement obligation relief. This run does "
            "not use benefit obligations; it tests accumulated OCI loss burden "
            "reported in equity."
        ),
        "history_scan": (
            "No prior committed experiment_log or experiments/logs entry used "
            "AOCI or accumulated other comprehensive income loss relief as the "
            "decision field."
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
        "exp_20260617_016_aoci_overhang_relief.py"
    ),
}

_RAW_INDEX_CACHE: tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, Any]] | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return base._round(value, digits)


def _raw_instant_facts(usgaap: dict[str, Any], tags: tuple[str, ...]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for tag in tags:
        tag_payload = usgaap.get(tag) or {}
        for raw in tag_payload.get("units", {}).get("USD", []):
            start = str(raw.get("start") or "")[:10]
            end = str(raw.get("end") or "")[:10]
            filed = str(raw.get("filed") or "")[:10]
            value = rd._float_or_none(raw.get("val"))
            if start:
                continue
            if not end or not filed or value is None:
                continue
            facts.append(
                {
                    "filed": filed,
                    "start": end,
                    "end": end,
                    "value": value,
                    "tag": tag,
                    "form": str(raw.get("form") or ""),
                    "fy": raw.get("fy"),
                    "fp": str(raw.get("fp") or ""),
                }
            )
    facts.sort(key=lambda row: (row["end"], row["filed"], row["tag"], row["value"]))
    return facts


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
        aoci_facts = _raw_instant_facts(usgaap, AOCI_TAGS)
        asset_facts = _raw_instant_facts(usgaap, ASSET_TAGS)
        equity_facts = _raw_instant_facts(usgaap, EQUITY_TAGS)
        if not aoci_facts:
            stats["tickers_missing_raw_aoci"] += 1
            continue
        if not asset_facts:
            stats["tickers_missing_raw_assets"] += 1
            continue
        if not equity_facts:
            stats["tickers_missing_raw_equity"] += 1
            continue
        index[ticker] = {"aoci": aoci_facts, "assets": asset_facts, "equity": equity_facts}
        stats["tickers_with_raw_aoci_assets_equity"] += 1
        stats["raw_aoci_fact_count"] += len(aoci_facts)
        stats["raw_asset_fact_count"] += len(asset_facts)
        stats["raw_equity_fact_count"] += len(equity_facts)

    summary = {
        "raw_companyfacts_cache": _repo_rel(RAW_COMPANYFACTS_CACHE),
        "aoci_tags": list(AOCI_TAGS),
        "asset_tags": list(ASSET_TAGS),
        "equity_tags": list(EQUITY_TAGS),
        "warehouse_source": _repo_rel(base.framework.WAREHOUSE),
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


def _latest_instant_fact(
    facts: list[dict[str, Any]],
    *,
    asof: str,
    before_end: str | None = None,
    end_lte: str | None = None,
) -> dict[str, Any] | None:
    candidates = [
        fact
        for fact in facts
        if fact["filed"] <= asof
        and (before_end is None or fact["end"] < before_end)
        and (end_lte is None or fact["end"] <= end_lte)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda row: (row["end"], row["filed"], abs(float(row["value"])), row["tag"]))


def _latest_prior_yoy_instant_fact(
    facts: list[dict[str, Any]],
    *,
    asof: str,
    current_end: str,
) -> dict[str, Any] | None:
    candidates = []
    for fact in facts:
        if fact["filed"] > asof or fact["end"] >= current_end:
            continue
        period_gap_days = base._days_between(current_end, fact["end"])
        if MIN_PERIOD_GAP_DAYS <= period_gap_days <= MAX_PERIOD_GAP_DAYS:
            candidates.append(fact)
    if not candidates:
        return None
    return max(candidates, key=lambda row: (row["end"], row["filed"], abs(float(row["value"])), row["tag"]))


def _aoci_loss_amount(fact: dict[str, Any]) -> float:
    value = float(fact["value"])
    return abs(value) if value < 0.0 else 0.0


def _aoci_relief_observation(
    ticker: str,
    asof: str,
    facts: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    current = _latest_instant_fact(facts["aoci"], asof=asof)
    if current is None:
        return None
    if base._days_between(asof, current["filed"]) > MAX_AOCI_FACT_AGE_DAYS:
        return None
    prior = _latest_prior_yoy_instant_fact(facts["aoci"], asof=asof, current_end=current["end"])
    if prior is None:
        return None
    period_gap_days = base._days_between(current["end"], prior["end"])

    current_assets = _latest_instant_fact(facts["assets"], asof=asof, end_lte=current["end"])
    prior_assets = _latest_instant_fact(facts["assets"], asof=asof, end_lte=prior["end"])
    current_equity = _latest_instant_fact(facts["equity"], asof=asof, end_lte=current["end"])
    prior_equity = _latest_instant_fact(facts["equity"], asof=asof, end_lte=prior["end"])
    if (
        current_assets is None
        or prior_assets is None
        or current_equity is None
        or prior_equity is None
    ):
        return None

    current_loss = _aoci_loss_amount(current)
    prior_loss = _aoci_loss_amount(prior)
    current_asset_value = float(current_assets["value"])
    prior_asset_value = float(prior_assets["value"])
    current_equity_value = float(current_equity["value"])
    prior_equity_value = float(prior_equity["value"])
    if (
        prior_loss < MIN_PRIOR_AOCI_LOSS
        or current_asset_value < MIN_CURRENT_ASSETS
        or prior_asset_value <= 0.0
        or current_equity_value < MIN_CURRENT_EQUITY
        or prior_equity_value <= 0.0
    ):
        return None

    current_asset_ratio = current_loss / current_asset_value
    prior_asset_ratio = prior_loss / prior_asset_value
    current_equity_ratio = current_loss / current_equity_value
    prior_equity_ratio = prior_loss / prior_equity_value
    asset_ratio_relief = prior_asset_ratio - current_asset_ratio
    equity_ratio_relief = prior_equity_ratio - current_equity_ratio
    relief_pct = (prior_loss - current_loss) / prior_loss

    if prior_asset_ratio < MIN_PRIOR_AOCI_TO_ASSETS:
        return None
    if current_asset_ratio > MAX_CURRENT_AOCI_TO_ASSETS:
        return None
    if current_equity_ratio > MAX_CURRENT_AOCI_TO_EQUITY:
        return None
    if asset_ratio_relief < MIN_AOCI_ASSET_RATIO_RELIEF:
        return None
    if relief_pct < MIN_AOCI_RELIEF_PCT:
        return None

    return {
        "ticker": ticker,
        "current_period_end": current["end"],
        "prior_period_end": prior["end"],
        "current_aoci_filed": current["filed"],
        "prior_aoci_filed": prior["filed"],
        "current_aoci_tag": current["tag"],
        "prior_aoci_tag": prior["tag"],
        "current_aoci_value": _round(float(current["value"]), 2),
        "prior_aoci_value": _round(float(prior["value"]), 2),
        "current_aoci_loss": _round(current_loss, 2),
        "prior_aoci_loss": _round(prior_loss, 2),
        "current_assets_period_end": current_assets["end"],
        "prior_assets_period_end": prior_assets["end"],
        "current_assets": _round(current_asset_value, 2),
        "prior_assets": _round(prior_asset_value, 2),
        "current_equity": _round(current_equity_value, 2),
        "prior_equity": _round(prior_equity_value, 2),
        "current_aoci_to_assets": _round(current_asset_ratio, 6),
        "prior_aoci_to_assets": _round(prior_asset_ratio, 6),
        "current_aoci_to_equity": _round(current_equity_ratio, 6),
        "prior_aoci_to_equity": _round(prior_equity_ratio, 6),
        "aoci_asset_ratio_relief": _round(asset_ratio_relief, 6),
        "aoci_equity_ratio_relief": _round(equity_ratio_relief, 6),
        "aoci_relief_pct": _round(relief_pct, 6),
        "period_gap_days": period_gap_days,
        "fact_age_days": base._days_between(asof, current["filed"]),
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
    window_dates = [day for day in dates if str(cfg["start"]) <= day <= str(cfg["end"])]
    eligible = sorted(set(quality_index) & set(snapshot))
    scan: Counter[str] = Counter()
    scan["scanned_trading_days"] = len(window_dates)
    scan["eligible_quality_tickers"] = len(eligible)
    candidates: list[dict[str, Any]] = []
    for signal_date in window_dates:
        for ticker in eligible:
            scan["ticker_day_evaluations"] += 1
            quality = _aoci_relief_observation(ticker, signal_date, quality_index[ticker])
            if quality is None:
                scan["failed_aoci_relief_gate"] += 1
                continue
            confirm = base._price_confirmation(
                snapshot=snapshot,
                indices=indices,
                ticker=ticker,
                signal_date=signal_date,
            )
            if confirm is None:
                scan["failed_price_confirmation"] += 1
                continue
            scan["qualified_candidate_rows"] += 1
            meta = sector_entries.get(ticker, {})
            score = (
                1.15 * min(float(quality["aoci_relief_pct"] or 0.0), 1.0)
                + 10.0 * min(float(quality["aoci_asset_ratio_relief"] or 0.0), 0.10)
                + 0.20 * min(max(float(quality["aoci_equity_ratio_relief"] or 0.0), 0.0), 1.0)
                + 0.45 * float(confirm["candidate_ret20_excess_spy"])
                + 0.12 * float(confirm["candidate_ret60_excess_spy"])
                + 0.10 * float(confirm["candidate_close_location"])
                + 0.035
                * math.log10(max(float(confirm["candidate_avg_dollar_volume_20d"]), 1.0) / 1_000_000.0)
            )
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "RAW_SEC_AOCI_OVERHANG_RELIEF_PAPER",
                    "candidate_score": _round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": "raw_instant_companyfacts_filed_and_signal_close_before_next_open_paper_entry",
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "uses_free_sec_companyfacts": True,
                    "uses_raw_sec_companyfacts_cache": True,
                    "uses_free_ohlcv": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    **{f"quality_{key}": value for key, value in quality.items()},
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
            -float(row["quality_aoci_asset_ratio_relief"] or 0.0),
            -float(row["quality_aoci_relief_pct"] or 0.0),
            -float(row["candidate_ret20_excess_spy"] or 0.0),
            -float(row["candidate_avg_dollar_volume_20d"] or 0.0),
            row["ticker"],
        )
    )
    scan["deduped_candidate_rows"] = len(rows)
    scan["candidate_signal_days"] = len({row["date"] for row in rows})
    scan["candidate_tickers"] = len({row["ticker"] for row in rows})
    return rows, {
        **dict(scan),
        "rule_version": RULE_VERSION,
        "max_aoci_fact_age_days": MAX_AOCI_FACT_AGE_DAYS,
        "min_current_assets": MIN_CURRENT_ASSETS,
        "min_current_equity": MIN_CURRENT_EQUITY,
        "min_prior_aoci_loss": MIN_PRIOR_AOCI_LOSS,
        "min_prior_aoci_to_assets": MIN_PRIOR_AOCI_TO_ASSETS,
        "max_current_aoci_to_assets": MAX_CURRENT_AOCI_TO_ASSETS,
        "max_current_aoci_to_equity": MAX_CURRENT_AOCI_TO_EQUITY,
        "min_aoci_asset_ratio_relief": MIN_AOCI_ASSET_RATIO_RELIEF,
        "min_aoci_relief_pct": MIN_AOCI_RELIEF_PCT,
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
        "positive_replay_lead_not_promoted_aoci_overhang_relief"
        if gate["passed"]
        else "rejected_aoci_overhang_relief_candidate_pool"
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
    base.MAX_ANNUAL_FACT_AGE_DAYS = MAX_AOCI_FACT_AGE_DAYS
    base.PREDICTION = PREDICTION
    base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    base.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    base.load_companyfacts_rows = _load_companyfacts_rows_stub
    base._build_quality_index = _build_quality_index
    base._candidate_rows_for_window = _candidate_rows_for_window
    base._gate4 = _gate4


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    status = "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected"
    if gate4["passed"]:
        interpretation = (
            "The AOCI overhang relief source cleared the numeric "
            "three-window replay screen, but remains only a replay lead because "
            "no shared daily/backtest helper was promoted."
        )
    else:
        regressed_windows = [
            label
            for label, delta in payload["delta_metrics"]["by_window"].items()
            if float(delta.get("expected_value_score") or 0.0) < 0.0
            or float(delta.get("total_pnl") or 0.0) < 0.0
        ]
        interpretation = (
            "The AOCI overhang relief source did not clear Gate 4 "
            f"(failed: {', '.join(gate4['failed_reasons']) or 'none'}). "
            "The signal is directionally useful in some windows but not "
            "repeatable enough: it regressed "
            f"{', '.join(regressed_windows) or 'no individual window'}, "
            "worsened drawdown beyond the guardrail when present, and failed "
            "the accepted distribution-day absorption comparator. This looks "
            "more like rate/FX/security revaluation accounting noise than an "
            "independent candidate-pool alpha. It is not retained or promoted."
        )

    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": _utc_now(),
            "lane": "alpha_search",
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
            "mechanism_family": "production_visible_free_sec_companyfacts_balance_sheet_overhang_candidate_pool",
            "new_evidence_type": "raw_sec_companyfacts_accumulated_other_comprehensive_income_loss_pit_field",
            "nearby_prior_experiments": [
                "exp-20260616-025",
                "exp-20260616-029",
                "exp-20260617-013",
                "exp-20260617-015",
            ],
            "prior_trial_count": 0,
            "multiple_testing_risk_bucket": "high",
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
        "base_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "max_aoci_fact_age_days": MAX_AOCI_FACT_AGE_DAYS,
        "min_current_assets": MIN_CURRENT_ASSETS,
        "min_current_equity": MIN_CURRENT_EQUITY,
        "min_prior_aoci_loss": MIN_PRIOR_AOCI_LOSS,
        "min_prior_aoci_to_assets": MIN_PRIOR_AOCI_TO_ASSETS,
        "max_current_aoci_to_assets": MAX_CURRENT_AOCI_TO_ASSETS,
        "max_current_aoci_to_equity": MAX_CURRENT_AOCI_TO_EQUITY,
        "min_aoci_asset_ratio_relief": MIN_AOCI_ASSET_RATIO_RELIEF,
        "min_aoci_relief_pct": MIN_AOCI_RELIEF_PCT,
        "min_period_gap_days": MIN_PERIOD_GAP_DAYS,
        "max_period_gap_days": MAX_PERIOD_GAP_DAYS,
        "aoci_tags": list(AOCI_TAGS),
        "asset_tags": list(ASSET_TAGS),
        "equity_tags": list(EQUITY_TAGS),
        "min_price": base.MIN_PRICE,
        "min_avg_dollar_volume_20d": base.MIN_AVG_DOLLAR_VOLUME_20D,
        "min_ret20_excess_spy": base.MIN_RET20_EXCESS_SPY,
        "min_ret60_excess_spy": base.MIN_RET60_EXCESS_SPY,
        "min_signal_return": base.MIN_SIGNAL_RETURN,
        "max_signal_return": base.MAX_SIGNAL_RETURN,
        "min_close_location": base.MIN_CLOSE_LOCATION,
        "max_realized_vol_20d": base.MAX_REALIZED_VOL_20D,
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"]["execution_model"] = (
        "AccumulatedOtherComprehensiveIncomeLoss instant facts plus Assets and "
        "StockholdersEquity instant facts are read from raw SEC Companyfacts "
        "and known only by filed date (<= signal date). Current and prior AOCI "
        "loss burdens are normalized by same-or-earlier period assets/equity. "
        "Price confirmation uses only signal-date "
        "OHLCV. Paper entry is the next available open with existing entry "
        "slippage; exit is the close 10 trading days after the signal with "
        "target-side sell slippage and ROUND_TRIP_COST_PCT."
    )
    payload["backtest_protocol"]["companyfacts_source"] = _repo_rel(RAW_COMPANYFACTS_CACHE)
    payload["gate2"]["runtime_fields"] = [
        "raw SEC companyfacts AccumulatedOtherComprehensiveIncomeLoss instant facts",
        "raw SEC companyfacts Assets instant facts",
        "raw SEC companyfacts StockholdersEquity instant facts",
        "raw SEC companyfacts filed date and period end",
        "warehouse ticker_universe CIK mapping",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "A retry needs materially different PIT AOCI decomposition such as "
        "available-for-sale securities, FX translation, pension OCI component, "
        "or rate-duration exposure joined to the same issuers, or closed "
        "forward replacement-value rows. Do not sweep AOCI tag lists, burden "
        "thresholds, fact freshness, RS/close/volume guards, top-N, hold, "
        "cooldown, or notional on these frozen windows."
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
            "Do not retry by sweeping AOCI tags, AOCI/assets or AOCI/equity "
            "thresholds, relief percentages, fact freshness, RS/close/"
            "volume/vol guards, top-N, hold days, cooldown, or notional on "
            "these frozen windows."
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
            f"# {EXPERIMENT_ID} AOCI Overhang Relief",
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
            "- Aggregate EV delta: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
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
        "aggregate_strategy_total_pnl_delta": log_record[
            "aggregate_strategy_total_pnl_delta"
        ],
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
