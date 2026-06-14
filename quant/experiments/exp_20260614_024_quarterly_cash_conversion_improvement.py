"""exp-20260614-024: quarterly cash-conversion improvement candidate pool.

Replay-only alpha search. The single decision hypothesis is a sharper free
PIT SEC-Companyfacts candidate source derived from the rejected annual
accruals/cash-conversion lead: among the production universe, candidates whose
latest reported QUARTERLY operating-cash-flow / net-income ratio improves
materially versus the prior-year comparable quarter, while current quarterly
accruals remain low relative to assets, may isolate higher-conviction
earnings-quality momentum. The candidate enters paper at the next open with a
fixed 10-trading-day hold.

Why this is not a retry of exp-20260614-020/021/023: those experiments tested
annual cash-conversion, then deployment cap, then a protective stop. This one
changes the information field itself to a current-quarter improvement measure
where quarterly operating cash flow is reported cleanly.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. A positive result is
only a replay lead until a shared historical/daily helper reproduces it.
No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sqlite3
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, EXPERIMENTS_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
from fundamental_growth_rs_paper_sleeve import load_companyfacts_rows  # noqa: E402


EXPERIMENT_ID = "exp-20260614-024"
STEM = "quarterly_cash_conversion_improvement"
TRIAL_FAMILY = "quarterly_cash_conversion_improvement_candidate_pool"
TRIAL_VARIANT_ID = "companyfacts_quarterly_cash_conversion_improvement_top1_next_open_10d_v1"
CHANGED_VARIABLE = "quarterly_cash_conversion_improvement_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260614_024_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 10

# Accruals / cash-conversion improvement (quarterly, point-in-time)
QUARTER_DURATION_MIN = 60
QUARTER_DURATION_MAX = 130
MAX_QUARTER_FACT_AGE_DAYS = 220
MIN_CURRENT_CASH_CONVERSION = 1.00
MIN_PRIOR_CASH_CONVERSION = 0.50
MIN_CASH_CONVERSION_IMPROVEMENT = 0.20
MAX_QUARTER_ACCRUALS_TO_ASSETS = 0.01

# Liquid SPY-relative price confirmation
MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_RET20_EXCESS_SPY = 0.0       # non-negative 20d relative strength vs SPY
MIN_RET60_EXCESS_SPY = -0.05
MIN_SIGNAL_RETURN = -0.03
MAX_SIGNAL_RETURN = 0.06         # do not chase a same-day spike
MIN_CLOSE_LOCATION = 0.40
MAX_REALIZED_VOL_20D = 0.10

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

# Closest accepted standalone default-off candidate-pool comparators.
COMPRESSION_COMPARATOR = {
    "experiment_id": "exp-20260608-013",
    "decision": "accepted_narrow_range_compression_breakout_shared_default_off_adapter",
    "aggregate_expected_value_delta": 0.1608,
    "aggregate_pnl_delta": 2248.98,
}
DISTRIBUTION_COMPARATOR = {
    "experiment_id": "exp-20260611-007",
    "decision": "accepted_paper_pending_forward_distribution_day_absorption_leadership_shared_adapter",
    "aggregate_expected_value_delta": 0.5286,
    "aggregate_pnl_delta": 10432.91,
}

PREDICTION = {
    "success_probability": 0.22,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "thin_sample",
        "window_regression",
        "annual_cash_conversion_overlap",
        "accepted_comparator_not_beaten",
        "concentration_failed",
    ],
    "confidence_reason": (
        "Annual cash conversion was positive but overdeployed in exp-20260614-020; "
        "a latest-quarter improvement field is a distinct PIT Companyfacts "
        "discriminator, not a threshold/cap/stop retry. Risk is thin sample and "
        "concentration because few tickers report clean quarterly operating cash "
        "flow."
    ),
    "recorded_at": "2026-06-14T19:06:00+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "default_off_paper_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "uses_llm": False,
    "uses_free_sec_companyfacts": True,
    "uses_free_ohlcv": True,
    "live_realism_evaluated": True,
    "live_ready": False,
    "execution_envelope": {
        "trade_enabled": False,
        "target_notional_per_paper_trade": BASE_NOTIONAL_USD,
        "daily_entry_slots": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "hold_days": HOLD_DAYS,
        "liquidity_source": "price >= $10 and ADV20 >= $50M from PIT OHLCV",
        "order_semantics": "observe-only next-session-open paper entry; no broker order",
        "portfolio_displacement": "none unless a later shared helper and activation gate pass",
        "kill_switch": "trade_enabled remains false; no production adapter changes",
        "failure_handling": (
            "missing current/prior comparable quarterly net_income and "
            "operating_cash_flow, missing assets, missing OHLCV, missing next "
            "open, or missing 10d exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only a "
        "replay lead until a shared default-off helper computes the same PIT "
        "quarterly cash-conversion improvement gate, liquid SPY-relative "
        "confirmation, cooldown, next-open paper entry, 10-day exit, costs, and "
        "concentration controls in both historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: production-universe names whose latest reported "
        "quarterly operating cash flow backs net income better than the "
        "prior-year comparable quarter, while same-day price action confirms "
        "liquid SPY-relative demand, should be a sharper version of the annual "
        "cash-conversion lead."
    ),
    "2_history_check": {
        "exp-20260528-016/017/019 and exp-20260602-001": (
            "Accepted/rejected fundamental_growth_rs Companyfacts support fields "
            "and the prior cash-conversion support field rode the accepted "
            "operating-profit + RS sleeve; they did not test a standalone "
            "quarterly improvement candidate source."
        ),
        "exp-20260614-020": (
            "Annual accruals / cash-conversion candidate pool was positive in "
            "all three windows but rejected because full deployment worsened "
            "drawdown by +5.22pp."
        ),
        "exp-20260614-021 and exp-20260614-023": (
            "Low-deployment and protective-stop retries failed; this run does "
            "not retune deployment, stop, annual ratio, price guards, hold, or "
            "cooldown. It changes the PIT quality discriminator."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Aggregate EV/PnL must "
        "be positive, no window EV/PnL regression, at least two EV-improved "
        "windows, at least 20 paper trades across all 3 windows, survival >=5%, "
        "drawdown drift <=0.5pp, concentration pass, and the accepted "
        "compression and distribution candidate-pool comparators must be beaten. "
        "Replay-only positives are leads until shared daily/backtest parity "
        "exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260614_024_quarterly_cash_conversion_improvement.py"
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _configure_framework() -> None:
    framework.EXPERIMENT_ID = EXPERIMENT_ID
    framework.STEM = STEM
    framework.TRIAL_FAMILY = TRIAL_FAMILY
    framework.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    framework.CHANGED_VARIABLE = CHANGED_VARIABLE
    framework.RULE_VERSION = RULE_VERSION
    framework.OUT_DIR = OUT_DIR
    framework.OUT_JSON = OUT_JSON
    framework.LOG_JSON = LOG_JSON
    framework.TICKET_JSON = TICKET_JSON
    framework.CARD_MD = CARD_MD
    framework.MANIFEST_JSON = MANIFEST_JSON
    framework.EXPERIMENT_LOG = EXPERIMENT_LOG
    framework.REGISTRY_JSON = REGISTRY_JSON
    framework.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    framework.HOLD_DAYS = HOLD_DAYS
    framework.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    framework.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    framework.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    framework.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    framework.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    framework.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    framework.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    framework.PREDICTION = PREDICTION
    framework.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    framework._configure_sleeve_globals()


def _repo_rel(path: Path | str) -> str:
    return framework._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return framework._round(value, digits)


def _load_window_snapshot(
    *,
    cfg: dict[str, str],
    eligible_tickers: set[str],
) -> dict[str, list[dict[str, Any]]]:
    start = framework._parse_date(cfg["start"]) - timedelta(days=120)
    end = framework._parse_date(cfg["end"]) + timedelta(days=40)
    tickers = sorted(set(eligible_tickers) | {"SPY", "QQQ"})
    snapshot: dict[str, list[dict[str, Any]]] = {ticker: [] for ticker in tickers}
    warehouse_uri = f"file:{Path(framework.WAREHOUSE).resolve().as_posix()}?mode=ro&immutable=1"
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
            params = [*chunk, framework._date_str(start), framework._date_str(end)]
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


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _quarterly_facts(rows: list[dict[str, Any]], canonical: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for raw in rows:
        if str(raw.get("canonical") or "") != canonical:
            continue
        dur = raw.get("duration_days")
        try:
            dur_i = int(dur) if dur is not None else None
        except (TypeError, ValueError):
            dur_i = None
        if dur_i is None or not (QUARTER_DURATION_MIN <= dur_i <= QUARTER_DURATION_MAX):
            continue
        filed = str(raw.get("filed") or "")[:10]
        end = str(raw.get("end") or "")[:10]
        value = _float_or_none(raw.get("value"))
        if not filed or not end or value is None:
            continue
        facts.append({"filed": filed, "end": end, "value": value, "duration_days": dur_i})
    facts.sort(key=lambda r: (r["filed"], r["end"]))
    return facts


def _instant_facts(rows: list[dict[str, Any]], canonical: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for raw in rows:
        if str(raw.get("canonical") or "") != canonical:
            continue
        filed = str(raw.get("filed") or "")[:10]
        value = _float_or_none(raw.get("value"))
        if not filed or value is None:
            continue
        facts.append({"filed": filed, "value": value})
    facts.sort(key=lambda r: r["filed"])
    return facts


def _build_quality_index(
    companyfacts_rows: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, Any]]:
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw in companyfacts_rows:
        ticker = str(raw.get("ticker") or "").upper()
        if ticker:
            by_ticker[ticker].append(raw)
    index: dict[str, dict[str, list[dict[str, Any]]]] = {}
    stats: Counter[str] = Counter()
    for ticker, rows in by_ticker.items():
        ni = _quarterly_facts(rows, "net_income")
        ocf = _quarterly_facts(rows, "operating_cash_flow")
        assets = _instant_facts(rows, "assets")
        if not ni or not ocf or not assets:
            stats["tickers_missing_required_facts"] += 1
            continue
        index[ticker] = {"net_income": ni, "operating_cash_flow": ocf, "assets": assets}
        stats["tickers_with_quarterly_cash_conversion_facts"] += 1
    return index, {
        "companyfacts_rows_loaded": len(companyfacts_rows),
        "tickers_seen": len(by_ticker),
        **dict(stats),
    }


def _latest_on_or_before(facts: list[dict[str, Any]], asof: str) -> dict[str, Any] | None:
    chosen: dict[str, Any] | None = None
    for fact in facts:
        if fact["filed"] <= asof:
            chosen = fact
        else:
            break
    return chosen


def _matched_on_or_before(
    facts: list[dict[str, Any]], asof: str, end: str
) -> dict[str, Any] | None:
    chosen: dict[str, Any] | None = None
    for fact in facts:
        if fact["filed"] <= asof and fact["end"] == end:
            chosen = fact
    return chosen


def _days_between(later: str, earlier: str) -> int:
    return (framework._parse_date(later) - framework._parse_date(earlier)).days


def _prior_comparable_quarter(
    facts: list[dict[str, Any]], asof: str, current_end: str
) -> dict[str, Any] | None:
    current_end_date = framework._parse_date(current_end)
    candidates: list[tuple[int, int, dict[str, Any]]] = []
    for fact in facts:
        if fact["filed"] > asof or fact["end"] >= current_end:
            continue
        gap = (current_end_date - framework._parse_date(fact["end"])).days
        if 250 <= gap <= 450:
            candidates.append((abs(gap - 365), -gap, fact))
    candidates.sort(key=lambda row: (row[0], row[1], row[2]["filed"]))
    return candidates[0][2] if candidates else None


def _quarterly_cash_conversion_improvement(
    ticker: str,
    asof: str,
    facts: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    ni = _latest_on_or_before(facts["net_income"], asof)
    if ni is None:
        return None
    ocf = _matched_on_or_before(facts["operating_cash_flow"], asof, ni["end"])
    if ocf is None:
        return None
    assets = _latest_on_or_before(facts["assets"], asof)
    if assets is None or assets["value"] <= 0.0:
        return None
    ni_val = ni["value"]
    ocf_val = ocf["value"]
    if ni_val <= 0.0 or ocf_val <= 0.0:
        return None
    if _days_between(asof, ni["filed"]) > MAX_QUARTER_FACT_AGE_DAYS:
        return None
    prior_ni = _prior_comparable_quarter(facts["net_income"], asof, ni["end"])
    if prior_ni is None:
        return None
    prior_ocf = _matched_on_or_before(facts["operating_cash_flow"], asof, prior_ni["end"])
    if prior_ocf is None:
        return None
    prior_ni_val = prior_ni["value"]
    prior_ocf_val = prior_ocf["value"]
    if prior_ni_val <= 0.0 or prior_ocf_val <= 0.0:
        return None
    current_accruals_to_assets = (ni_val - ocf_val) / assets["value"]
    current_cash_conversion = ocf_val / ni_val
    prior_cash_conversion = prior_ocf_val / prior_ni_val
    cash_conversion_improvement = current_cash_conversion - prior_cash_conversion
    if current_cash_conversion < MIN_CURRENT_CASH_CONVERSION:
        return None
    if prior_cash_conversion < MIN_PRIOR_CASH_CONVERSION:
        return None
    if cash_conversion_improvement < MIN_CASH_CONVERSION_IMPROVEMENT:
        return None
    if current_accruals_to_assets > MAX_QUARTER_ACCRUALS_TO_ASSETS:
        return None
    return {
        "current_quarter_end": ni["end"],
        "prior_comparable_quarter_end": prior_ni["end"],
        "net_income_filed": ni["filed"],
        "operating_cash_flow_filed": ocf["filed"],
        "prior_net_income_filed": prior_ni["filed"],
        "prior_operating_cash_flow_filed": prior_ocf["filed"],
        "assets_filed": assets["filed"],
        "net_income": _round(ni_val, 2),
        "operating_cash_flow": _round(ocf_val, 2),
        "prior_net_income": _round(prior_ni_val, 2),
        "prior_operating_cash_flow": _round(prior_ocf_val, 2),
        "total_assets": _round(assets["value"], 2),
        "quarter_accruals_to_assets": _round(current_accruals_to_assets, 6),
        "cash_conversion_ratio": _round(current_cash_conversion, 6),
        "prior_cash_conversion_ratio": _round(prior_cash_conversion, 6),
        "cash_conversion_improvement": _round(cash_conversion_improvement, 6),
        "fact_age_days": _days_between(asof, ni["filed"]),
    }


def _price_confirmation(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    ticker: str,
    signal_date: str,
) -> dict[str, Any] | None:
    rows = framework.shadow._series(snapshot, ticker)
    spy_rows = framework.shadow._series(snapshot, "SPY")
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None or idx < 60 or spy_idx < 60:
        return None
    if idx + HOLD_DAYS >= len(rows):
        return None
    close = framework._value(rows[idx], "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None
    signal_return = framework._daily_return(rows, idx)
    close_location = framework._close_location(rows[idx])
    ret20 = framework._ret(rows, idx, 20)
    ret60 = framework._ret(rows, idx, 60)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    spy_ret60 = framework._ret(spy_rows, spy_idx, 60)
    realized_vol = framework._realized_vol(rows, idx, 20)
    if any(
        value is None
        for value in (signal_return, close_location, ret20, ret60, spy_ret20, spy_ret60, realized_vol)
    ):
        return None
    assert signal_return is not None and close_location is not None
    assert ret20 is not None and ret60 is not None
    assert spy_ret20 is not None and spy_ret60 is not None and realized_vol is not None
    if signal_return < MIN_SIGNAL_RETURN or signal_return > MAX_SIGNAL_RETURN:
        return None
    if close_location < MIN_CLOSE_LOCATION:
        return None
    if realized_vol > MAX_REALIZED_VOL_20D:
        return None
    ret20_excess_spy = ret20 - spy_ret20
    ret60_excess_spy = ret60 - spy_ret60
    if ret20_excess_spy < MIN_RET20_EXCESS_SPY:
        return None
    if ret60_excess_spy < MIN_RET60_EXCESS_SPY:
        return None
    volume_ratio = framework._volume_ratio(rows, idx) or 0.0
    return {
        "candidate_signal_return": _round(signal_return, 6),
        "candidate_close_location": _round(close_location, 6),
        "candidate_ret20": _round(ret20, 6),
        "candidate_ret20_excess_spy": _round(ret20_excess_spy, 6),
        "candidate_ret60_excess_spy": _round(ret60_excess_spy, 6),
        "candidate_avg_dollar_volume_20d": _round(adv20, 2),
        "candidate_volume_ratio_20d": _round(volume_ratio, 6),
        "candidate_realized_vol_20d": _round(realized_vol, 6),
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    sector_entries: dict[str, dict[str, Any]],
    quality_index: dict[str, dict[str, list[dict[str, Any]]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    indices = {ticker: framework.shadow._row_index(framework.shadow._series(snapshot, ticker)) for ticker in snapshot}
    dates = framework.shadow._trading_dates(snapshot)
    window_dates = [day for day in dates if str(cfg["start"]) <= day <= str(cfg["end"])]
    eligible = sorted(set(quality_index) & set(snapshot))
    scan: Counter[str] = Counter()
    scan["scanned_trading_days"] = len(window_dates)
    scan["eligible_quality_tickers"] = len(eligible)
    candidates: list[dict[str, Any]] = []
    for signal_date in window_dates:
        for ticker in eligible:
            scan["ticker_day_evaluations"] += 1
            quality = _quarterly_cash_conversion_improvement(ticker, signal_date, quality_index[ticker])
            if quality is None:
                scan["failed_quality_gate"] += 1
                continue
            confirm = _price_confirmation(
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
                0.85 * min(float(quality["cash_conversion_improvement"]), 2.0)
                + 0.55 * min(float(quality["cash_conversion_ratio"]), 3.0)
                + 0.45 * float(confirm["candidate_ret20_excess_spy"])
                + 0.12 * float(confirm["candidate_ret60_excess_spy"])
                + 0.10 * float(confirm["candidate_close_location"])
                + 0.035 * math.log10(max(float(confirm["candidate_avg_dollar_volume_20d"]), 1.0) / 1_000_000.0)
            )
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "QUARTERLY_CASH_CONVERSION_IMPROVEMENT_PAPER",
                    "candidate_score": _round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": "quarterly_companyfacts_filed_and_signal_close_before_next_open_paper_entry",
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "uses_free_sec_companyfacts": True,
                    "uses_free_ohlcv": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    **{f"quality_{k}": v for k, v in quality.items()},
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
            -float(row["quality_cash_conversion_improvement"] or 0.0),
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
        "min_current_cash_conversion": MIN_CURRENT_CASH_CONVERSION,
        "min_prior_cash_conversion": MIN_PRIOR_CASH_CONVERSION,
        "min_cash_conversion_improvement": MIN_CASH_CONVERSION_IMPROVEMENT,
        "max_quarter_accruals_to_assets": MAX_QUARTER_ACCRUALS_TO_ASSETS,
        "max_quarter_fact_age_days": MAX_QUARTER_FACT_AGE_DAYS,
    }


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = framework._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = list(gate.get("failed_reasons") or [])
    ev_delta = float(aggregate["expected_value_score_delta_sum"] or 0.0)
    pnl_delta = float(aggregate["total_pnl_delta_sum"] or 0.0)
    if ev_delta <= COMPRESSION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_compression_ev_not_beaten")
    if pnl_delta <= COMPRESSION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_compression_pnl_not_beaten")
    if ev_delta <= DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_distribution_ev_not_beaten")
    if pnl_delta <= DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_distribution_pnl_not_beaten")
    gate["failed_reasons"] = failed
    gate["accepted_compression_comparator"] = COMPRESSION_COMPARATOR
    gate["accepted_distribution_comparator"] = DISTRIBUTION_COMPARATOR
    gate["passed"] = not failed
    gate["decision"] = (
        "positive_replay_lead_not_promoted_quarterly_cash_conversion_improvement"
        if gate["passed"]
        else "rejected_quarterly_cash_conversion_improvement_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    _configure_framework()
    timestamp = _utc_now()
    gate2_open_positions = framework.sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(framework.get_universe())
    sector_entries_all = framework._load_sector_entries()

    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    filtered_candidates_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    raw_candidate_counts: "OrderedDict[str, int]" = OrderedDict()
    context_scan_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    quality_index_summary_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    warehouse_coverage_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] core baseline and quarterly cash-conversion improvement replay")
        before_result = framework.shadow._run_baseline(universe, cfg)
        before = framework.overlay_helper._metrics(before_result)
        snapshot = _load_window_snapshot(cfg=cfg, eligible_tickers=set(universe))
        sector_entries = {
            ticker: meta
            for ticker, meta in sector_entries_all.items()
            if ticker in snapshot
        }
        companyfacts_rows = load_companyfacts_rows(
            max_filed=str(cfg["end"]),
            tickers=[ticker for ticker in universe if ticker in snapshot],
        )
        quality_index, quality_summary = _build_quality_index(companyfacts_rows)
        warehouse_coverage_by_window[label] = {
            "loaded_ticker_count": len(snapshot),
            "sector_known_ticker_count": len(sector_entries),
            "source": _repo_rel(framework.WAREHOUSE),
        }
        quality_index_summary_by_window[label] = quality_summary
        candidates, context_scan = _candidate_rows_for_window(
            snapshot=snapshot,
            cfg=cfg,
            sector_entries=sector_entries,
            quality_index=quality_index,
        )
        selected_trades, filtered_candidates = framework._select_paper_trades(
            snapshot=snapshot,
            candidates=candidates,
        )
        overlay = framework.sleeve._overlay_from_paper_trades(before_result, selected_trades)
        after = framework.overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = framework.overlay_helper._delta(after, before)

        before_metrics[label] = before
        after_metrics[label] = after
        target_trades_by_window[label] = selected_trades
        filtered_candidates_by_window[label] = filtered_candidates[:200]
        raw_candidate_counts[label] = len(candidates)
        context_scan_by_window[label] = context_scan
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected_trades),
            "raw_candidate_count": len(candidates),
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = framework._aggregate_window_rows(window_rows)
    target_summary = framework.sleeve._target_trade_summary(target_trades_by_window)
    gate4 = _gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    status = "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected"
    failed_set = set(gate4["failed_reasons"])
    drawdown_only_failure = (
        not gate4["passed"]
        and float(aggregate["expected_value_score_delta_sum"] or 0.0) > 0.0
        and float(aggregate["total_pnl_delta_sum"] or 0.0) > 0.0
        and int(aggregate["windows_ev_regressed"] or 0) == 0
        and int(aggregate["windows_pnl_regressed"] or 0) == 0
        and failed_set.issubset({"drawdown_drift_too_high"})
    )
    calibration = {
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
    rejection_reason = None if gate4["passed"] else "; ".join(gate4["failed_reasons"])
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": gate4["decision"],
        "hypothesis": (
            "Quarterly cash-conversion improvement in SEC Companyfacts can "
            "sharpen the rejected annual accruals lead by requiring the latest "
            "reported quarterly operating-cash-flow/net-income ratio to improve "
            "versus the prior-year comparable quarter while keeping next-open "
            "default-off paper execution fixed."
        ),
        "change_type": "default_off_paper_candidate_pool_replay_scout",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "production_visible_free_sec_companyfacts_quality_candidate_pool",
        "new_evidence_type": "free_sec_companyfacts_quarterly_cash_conversion_improvement_plus_ohlcv",
        "nearby_prior_experiments": [
            "exp-20260602-001",
            "exp-20260614-020",
            "exp-20260614-021",
            "exp-20260614-023",
        ],
        "prior_trial_count": 0,
        "multiple_testing_risk_bucket": "minimal",
        "prediction": PREDICTION,
        "calibration": calibration,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "replay-only broad warehouse default-off paper overlay"
            ),
            "windows": framework.WINDOWS,
            "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
            "companyfacts_source": "data/non_ohlcv/sec_companyfacts_selected_*.jsonl",
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "Quarterly net_income and operating_cash_flow are known by "
                "their SEC filed date (<= signal date), matched on the same "
                "quarterly period end, and compared with the prior-year "
                "comparable quarter. Total assets uses the latest filed value. "
                "Price confirmation uses only signal-date OHLCV. Paper entry is "
                "the next available open with existing entry slippage; exit is "
                "the close 10 trading days after the signal with target-side "
                "sell slippage and ROUND_TRIP_COST_PCT."
            ),
        },
        "parameters": {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "quarter_duration_min": QUARTER_DURATION_MIN,
            "quarter_duration_max": QUARTER_DURATION_MAX,
            "max_quarter_fact_age_days": MAX_QUARTER_FACT_AGE_DAYS,
            "min_current_cash_conversion": MIN_CURRENT_CASH_CONVERSION,
            "min_prior_cash_conversion": MIN_PRIOR_CASH_CONVERSION,
            "min_cash_conversion_improvement": MIN_CASH_CONVERSION_IMPROVEMENT,
            "max_quarter_accruals_to_assets": MAX_QUARTER_ACCRUALS_TO_ASSETS,
            "min_price": MIN_PRICE,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
            "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
            "min_ret60_excess_spy": MIN_RET60_EXCESS_SPY,
            "min_signal_return": MIN_SIGNAL_RETURN,
            "max_signal_return": MAX_SIGNAL_RETURN,
            "min_close_location": MIN_CLOSE_LOCATION,
            "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
            "single_causal_variable": CHANGED_VARIABLE,
        },
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json",
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "SEC companyfacts canonical net_income (quarterly)",
                "SEC companyfacts canonical operating_cash_flow (quarterly)",
                "SEC companyfacts canonical assets",
                "SEC companyfacts filed date and period end",
                "warehouse OHLCV Date/Open/High/Low/Close/Volume",
                "SPY OHLCV for relative strength",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": round(min_survival, 6),
            "survival_rate_by_window": {
                label: before_metrics[label].get("survival_rate") for label in before_metrics
            },
            "passed": min_survival >= 0.05,
            "note": (
                "No new core filter or entry rule was added. The candidate source "
                "is additive default-off paper, so core signals generated/survived "
                "are unchanged from baseline."
            ),
        },
        "gate4": gate4,
        "accepted_compression_comparator": COMPRESSION_COMPARATOR,
        "accepted_distribution_comparator": DISTRIBUTION_COMPARATOR,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict((label, row["delta"]) for label, row in window_rows.items()),
            "aggregate": aggregate,
        },
        "warehouse_coverage_by_window": warehouse_coverage_by_window,
        "quality_index_summary_by_window": quality_index_summary_by_window,
        "raw_candidate_counts": raw_candidate_counts,
        "context_scan_by_window": context_scan_by_window,
        "target_trades_by_window": target_trades_by_window,
        "filtered_candidates_sample_by_window": filtered_candidates_by_window,
        "target_trade_summary": target_summary,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "interpretation": (
            "The quarterly cash-conversion improvement source cleared Gate 4 "
            "as a replay-only/default-off lead, but no production surface was "
            "promoted. It still requires a shared historical/daily helper before "
            "it can be retained as accepted paper alpha."
            if gate4["passed"]
            else (
                "The quarterly cash-conversion improvement source was positive "
                "except for drawdown drift, but failed Gate 4. It is not retained "
                "without a shared helper or a passing three-window result."
                if drawdown_only_failure
                else (
                    "The quarterly cash-conversion improvement source did "
                    "not clear Gate 4 (failed: "
                    + (", ".join(gate4["failed_reasons"]) or "none")
                    + "). Do not promote or tune this fixed quarterly "
                    "improvement definition on the same frozen windows."
                )
            )
        ),
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "A retry needs a materially different earnings-quality construction "
            "(for example true PIT TTM accruals built from annual-plus-YTD facts, "
            "forward closed replacement-value rows, or a new ownership/borrow/"
            "options context), not a sweep of quarterly ratio, improvement, "
            "freshness, RS, close, volume, top-N, hold, or cooldown thresholds."
        ),
        "post_run_reflection": {
            "why_result_happened": (
                (
                    "Rejected on drawdown drift only. The quarterly improvement "
                    "field was directionally useful: aggregate EV {:+.4f} and "
                    "PnL ${:+,.2f} with no EV/PnL window regression, but max "
                    "drawdown drift {:+.4f} exceeded the 0.5pp guardrail. This "
                    "suggests the field can still select fragile momentum paths "
                    "when paired with next-open 10-day paper execution."
                ).format(
                    aggregate["expected_value_score_delta_sum"],
                    aggregate["total_pnl_delta_sum"],
                    float(aggregate["max_drawdown_delta_max"] or 0.0),
                )
                if drawdown_only_failure
                else (
                    "Rejected. Quarterly cash-conversion improvement plus liquid "
                    "SPY-relative confirmation did not clear Gate 4 versus the "
                    "accepted compression/distribution comparators (failed: {}). "
                    "The likely failure is thin and concentrated clean-quarterly "
                    "cash-flow coverage; the few eligible rows do not reliably "
                    "beat existing momentum/relation paper sources after next-open "
                    "execution and costs."
                ).format(", ".join(gate4["failed_reasons"]) or "none")
            ),
            "outcome_summary": (
                "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}; "
                "max drawdown drift {:+.4f}; {} paper trades.".format(
                    aggregate["expected_value_score_delta_sum"],
                    aggregate["total_pnl_delta_sum"],
                    float(aggregate["max_drawdown_delta_max"] or 0.0),
                    target_summary["total_trade_count"],
                )
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry by sweeping quarterly cash-conversion ratio, prior "
                "ratio, improvement gap, accruals/assets threshold, fact "
                "freshness, RS/close/volume/vol guards, top-N, hold days, "
                "cooldown, or notional on these frozen windows."
            ),
            "new_evidence_required": (
                "Need true PIT TTM same-period accruals, closed forward "
                "replacement-value rows, or a materially different free data "
                "context such as ownership, borrow, or options."
                if drawdown_only_failure
                else (
                    "Need true PIT TTM same-period accruals or closed forward "
                    "replacement-value rows before revisiting quarterly cash-flow "
                    "quality."
                )
            ),
        },
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Eligible | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
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
            f"# {EXPERIMENT_ID} Quarterly Cash-Conversion Improvement",
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
                COMPRESSION_COMPARATOR["aggregate_expected_value_delta"],
                COMPRESSION_COMPARATOR["aggregate_pnl_delta"],
            ),
            "- Accepted distribution comparator: EV `{:+.4f}`, PnL `${:+,.2f}`".format(
                DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"],
                DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"],
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


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json",
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "accepted_compression_comparator": COMPRESSION_COMPARATOR,
        "accepted_distribution_comparator": DISTRIBUTION_COMPARATOR,
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label]["expected_value_score"],
                "expected_value_after": payload["after_metrics"][label]["expected_value_score"],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label]["expected_value_score"],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label]["total_pnl"],
                "eligible_quality_tickers": payload["context_scan_by_window"][label].get("eligible_quality_tickers"),
                "raw_candidate_count": payload["raw_candidate_counts"][label],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "negative_reflection": payload["post_run_reflection"]["why_result_happened"],
        "post_run_reflection": payload["post_run_reflection"],
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "anti_js": "No JavaScript was used.",
    }


def _persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, payload)
    framework._write_text(CARD_MD, _build_card(payload))
    framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
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
            _repo_rel(Path(__file__)): framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): framework._sha256(CARD_MD),
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def main() -> None:
    payload = _build_payload()
    _persist(payload)
    print(json.dumps(framework._safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
