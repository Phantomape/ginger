"""exp-20260614-014: Kova Companyfacts capital-efficiency candidate scout.

Replay-only alpha search. This tests one fixed candidate-pool hypothesis:
the broad Kova SEC Companyfacts file can expand the candidate pool with
filed-date-safe, capital-efficient growth leaders rather than retuning the
existing Fundamental Growth RS helper thresholds.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. A positive result is
only a replay lead until a shared historical/daily helper reproduces it.
No JavaScript is used.
"""

from __future__ import annotations

import bisect
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime
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


EXPERIMENT_ID = "exp-20260614-014"
STEM = "kova_companyfacts_capital_efficiency"
TRIAL_FAMILY = "kova_companyfacts_capital_efficient_growth_candidate_pool"
TRIAL_VARIANT_ID = "kova_companyfacts_capital_efficiency_top1_next_open_10d_v1"
CHANGED_VARIABLE = "kova_companyfacts_capital_efficient_growth_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260614_014_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
KOVA_FACTS_PATH = REPO_ROOT / "data" / "non_ohlcv" / "sec_companyfacts_selected_kova_20260613.jsonl"

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 10

MIN_PRICE = 12.0
MIN_AVG_DOLLAR_VOLUME_20D = 100_000_000.0
MIN_REVENUE_YOY = 0.10
MIN_OPERATING_INCOME_ASSETS = 0.025
MAX_FACT_END_AGE_DAYS = 540
MIN_RET20_EXCESS_SPY = 0.0
MIN_RET60_EXCESS_SPY = 0.04
MIN_RS_SCORE = 0.025
MIN_CLOSE_LOCATION = 0.50
MIN_SIGNAL_RETURN = -0.015
MAX_SIGNAL_RETURN = 0.075
MAX_REALIZED_VOL_20D = 0.085

MIN_TARGET_TRADES = 30
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30

ACCEPTED_COMPANYFACTS_COMPARATOR = {
    "experiment_id": "exp-20260528-017",
    "decision": "accepted_candidate_fundamental_growth_rs_low_liability_support",
    "aggregate_expected_value_delta": 8.5419,
    "aggregate_pnl_delta": 127_144.15,
    "by_window": {
        "late_strong": {"expected_value_delta": 2.5177, "pnl_delta": 25_684.45},
        "mid_weak": {"expected_value_delta": 3.9309, "pnl_delta": 55_909.19},
        "old_thin": {"expected_value_delta": 2.0933, "pnl_delta": 45_550.51},
    },
}

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "old_thin_coverage_thin",
        "companyfacts_near_neighbor_comparator_failed",
        "concentration_failed",
        "warehouse_universe_survivorship_bias",
    ],
    "confidence_reason": (
        "Mechanism: newly available Kova SEC Companyfacts file covers over "
        "1100 tickers and can filter broad liquid leaders by filed-date-safe "
        "operating income/assets plus growth/RS, potentially expanding the "
        "candidate pool instead of retuning accepted helper thresholds. Nearby "
        "disconfirmers are strong: Companyfacts quality gates and broad OHLCV "
        "expansions often failed accepted comparators, and Kova coverage starts "
        "in 2025 so old_thin may be thin."
    ),
    "recorded_at": "2026-06-14T13:06:02+00:00",
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
    "uses_free_non_ohlcv": True,
    "uses_free_ohlcv": True,
    "live_realism_evaluated": False,
    "live_ready": False,
    "parity_note": (
        "Replay-only private scout. No shared helper, run adapter, daily "
        "snapshot, production watchlist, order path, core signal, ranking, "
        "sizing, or exit behavior changed. A positive result must be promoted "
        "through a shared default-off helper plus historical/daily parity before "
        "it can be retained as accepted paper alpha."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: the broad Kova SEC Companyfacts coverage can expand "
        "the paper candidate pool with filed-date-safe capital-efficient growth "
        "leaders, improving 10-day next-open replacement value without adding "
        "noise tickers."
    ),
    "2_history_check": {
        "exp-20260528-017": (
            "Accepted low-liability Companyfacts support is the binding closest "
            "comparator; this scout must beat it before it can be considered "
            "more than a weak lead."
        ),
        "exp-20260613-031": (
            "Operating-income/assets selector on the existing Fundamental "
            "Growth RS source improved core but lost to the accepted "
            "low-liability comparator and failed concentration."
        ),
        "exp-20260613-020": (
            "Seasoned new-listing broad candidate expansion failed; this run "
            "uses filed-date-safe fundamentals plus liquidity/RS rather than "
            "listing age or raw young momentum."
        ),
    },
    "3_single_causal_variable": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Core Gate 4 must pass "
        "aggregate EV/PnL, every window, survival, drawdown, sample, and "
        "concentration checks; because this is a Companyfacts-adjacent candidate "
        "pool, exp-20260528-017 accepted low-liability comparator must also be "
        "beaten in aggregate and every window. A positive private scout is not "
        "accepted alpha until a shared helper/daily snapshot reproduces it."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260614_014_kova_companyfacts_capital_efficiency.py"
    ),
}

ORIGINAL_GATE4 = framework._gate4
ORIGINAL_BUILD_PAYLOAD = framework._build_payload

FACT_INDEX: dict[str, dict[str, list[dict[str, Any]]]] | None = None
FACT_FILED_ORDS: dict[tuple[str, str], list[int]] = {}
FACT_TICKERS: set[str] = set()
FACT_LOAD_SUMMARY: dict[str, Any] = {}


def _date_ord(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date().toordinal()
    except ValueError:
        return None


def _float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _load_fact_index() -> dict[str, dict[str, list[dict[str, Any]]]]:
    global FACT_INDEX, FACT_LOAD_SUMMARY
    if FACT_INDEX is not None:
        return FACT_INDEX

    index: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    canonical_counts: Counter[str] = Counter()
    rows_read = 0
    rows_kept = 0
    for line in KOVA_FACTS_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        rows_read += 1
        row = json.loads(line)
        ticker = str(row.get("ticker") or "").upper()
        canonical = str(row.get("canonical") or "")
        if canonical not in {"assets", "operating_income", "revenue", "net_income"}:
            continue
        value = _float(row.get("value"))
        filed_ord = _date_ord(row.get("filed"))
        end_ord = _date_ord(row.get("end"))
        if not ticker or value is None or filed_ord is None or end_ord is None:
            continue
        rec = {
            "ticker": ticker,
            "canonical": canonical,
            "value": value,
            "filed": str(row.get("filed"))[:10],
            "end": str(row.get("end"))[:10],
            "filed_ord": filed_ord,
            "end_ord": end_ord,
            "fy": row.get("fy"),
            "fp": row.get("fp"),
            "form": row.get("form"),
            "accession_number": row.get("accession_number"),
        }
        index[ticker][canonical].append(rec)
        FACT_TICKERS.add(ticker)
        canonical_counts[canonical] += 1
        rows_kept += 1

    for ticker, by_canonical in index.items():
        for canonical, records in by_canonical.items():
            records.sort(key=lambda rec: (int(rec["filed_ord"]), int(rec["end_ord"])))
            FACT_FILED_ORDS[(ticker, canonical)] = [int(rec["filed_ord"]) for rec in records]

    FACT_INDEX = {ticker: dict(by_canonical) for ticker, by_canonical in index.items()}
    FACT_LOAD_SUMMARY = {
        "path": framework._repo_rel(KOVA_FACTS_PATH),
        "rows_read": rows_read,
        "rows_kept": rows_kept,
        "ticker_count": len(FACT_INDEX),
        "canonical_counts": dict(sorted(canonical_counts.items())),
        "rule_version": RULE_VERSION,
    }
    return FACT_INDEX


def _latest_fact(
    index: dict[str, dict[str, list[dict[str, Any]]]],
    ticker: str,
    canonical: str,
    signal_ord: int,
) -> dict[str, Any] | None:
    records = index.get(ticker, {}).get(canonical) or []
    if not records:
        return None
    filed_ords = FACT_FILED_ORDS.get((ticker, canonical), [])
    pos = bisect.bisect_right(filed_ords, signal_ord) - 1
    while pos >= 0:
        rec = records[pos]
        if int(rec["end_ord"]) <= signal_ord:
            return rec
        pos -= 1
    return None


def _prior_yoy_fact(
    index: dict[str, dict[str, list[dict[str, Any]]]],
    ticker: str,
    canonical: str,
    current: dict[str, Any],
    signal_ord: int,
) -> dict[str, Any] | None:
    records = index.get(ticker, {}).get(canonical) or []
    if not records:
        return None
    current_end = int(current["end_ord"])
    target_low = current_end - 460
    target_high = current_end - 270
    current_fp = current.get("fp")
    best: dict[str, Any] | None = None
    best_distance = 9999
    filed_ords = FACT_FILED_ORDS.get((ticker, canonical), [])
    pos = bisect.bisect_right(filed_ords, signal_ord) - 1
    while pos >= 0:
        rec = records[pos]
        end_ord = int(rec["end_ord"])
        value = _float(rec.get("value"))
        if value is not None and value > 0.0 and target_low <= end_ord <= target_high:
            if not current_fp or not rec.get("fp") or rec.get("fp") == current_fp:
                distance = abs((current_end - end_ord) - 365)
                if distance < best_distance:
                    best = rec
                    best_distance = distance
        pos -= 1
    return best


def _fundamental_context(ticker: str, signal_date: str) -> dict[str, Any] | None:
    index = _load_fact_index()
    signal_ord = _date_ord(signal_date)
    if signal_ord is None:
        return None
    revenue = _latest_fact(index, ticker, "revenue", signal_ord)
    operating_income = _latest_fact(index, ticker, "operating_income", signal_ord)
    assets = _latest_fact(index, ticker, "assets", signal_ord)
    net_income = _latest_fact(index, ticker, "net_income", signal_ord)
    if not revenue or not operating_income or not assets:
        return None
    prior_revenue = _prior_yoy_fact(index, ticker, "revenue", revenue, signal_ord)
    if not prior_revenue:
        return None

    revenue_value = _float(revenue.get("value"))
    prior_revenue_value = _float(prior_revenue.get("value"))
    operating_income_value = _float(operating_income.get("value"))
    assets_value = _float(assets.get("value"))
    net_income_value = _float(net_income.get("value")) if net_income else None
    if (
        revenue_value is None
        or prior_revenue_value is None
        or prior_revenue_value <= 0.0
        or operating_income_value is None
        or assets_value is None
        or assets_value <= 0.0
    ):
        return None

    revenue_yoy = (revenue_value / prior_revenue_value) - 1.0
    operating_income_assets = operating_income_value / assets_value
    freshest_filed_ord = max(
        int(revenue["filed_ord"]),
        int(operating_income["filed_ord"]),
        int(assets["filed_ord"]),
    )
    newest_end_ord = max(
        int(revenue["end_ord"]),
        int(operating_income["end_ord"]),
        int(assets["end_ord"]),
    )
    if signal_ord - newest_end_ord > MAX_FACT_END_AGE_DAYS:
        return None
    if revenue_yoy < MIN_REVENUE_YOY:
        return None
    if operating_income_assets < MIN_OPERATING_INCOME_ASSETS:
        return None
    if operating_income_value <= 0.0:
        return None
    if net_income_value is not None and net_income_value <= 0.0:
        return None

    return {
        "kova_companyfacts_rule_version": RULE_VERSION,
        "kova_companyfacts_known_at": "SEC Companyfacts filed date <= signal_date",
        "kova_companyfacts_source_path": framework._repo_rel(KOVA_FACTS_PATH),
        "kova_revenue_current": round(revenue_value, 6),
        "kova_revenue_prior_yoy": round(prior_revenue_value, 6),
        "kova_revenue_yoy_growth": round(revenue_yoy, 6),
        "kova_operating_income": round(operating_income_value, 6),
        "kova_assets": round(assets_value, 6),
        "kova_operating_income_assets_ratio": round(operating_income_assets, 6),
        "kova_net_income": None if net_income_value is None else round(net_income_value, 6),
        "kova_revenue_filed": revenue["filed"],
        "kova_revenue_period_end": revenue["end"],
        "kova_operating_income_filed": operating_income["filed"],
        "kova_assets_filed": assets["filed"],
        "kova_freshest_filed_age_days": signal_ord - freshest_filed_ord,
        "kova_newest_period_end_age_days": signal_ord - newest_end_ord,
        "trade_enabled": False,
        "alters_orders": False,
        "uses_llm": False,
    }


def _candidate_for_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
) -> dict[str, Any] | None:
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None or idx < 80 or spy_idx < 80:
        return None
    row = rows[idx]
    close = framework._value(row, "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None

    context = _fundamental_context(ticker, signal_date)
    if context is None:
        return None

    signal_return = framework._daily_return(rows, idx)
    ret20 = framework._ret(rows, idx, 20)
    ret60 = framework._ret(rows, idx, 60)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    spy_ret60 = framework._ret(spy_rows, spy_idx, 60)
    if None in (signal_return, ret20, ret60, spy_ret20, spy_ret60):
        return None
    signal_return = float(signal_return)
    ret20_excess_spy = float(ret20) - float(spy_ret20)
    ret60_excess_spy = float(ret60) - float(spy_ret60)
    rs_score = 0.45 * ret20_excess_spy + 0.55 * ret60_excess_spy
    if signal_return < MIN_SIGNAL_RETURN or signal_return > MAX_SIGNAL_RETURN:
        return None
    if ret20_excess_spy < MIN_RET20_EXCESS_SPY:
        return None
    if ret60_excess_spy < MIN_RET60_EXCESS_SPY:
        return None
    if rs_score < MIN_RS_SCORE:
        return None

    close_location = framework._close_location(row)
    if close_location is None or close_location < MIN_CLOSE_LOCATION:
        return None
    realized_vol = framework._realized_vol(rows, idx)
    if realized_vol is None or realized_vol > MAX_REALIZED_VOL_20D:
        return None
    volume_ratio = framework._volume_ratio(rows, idx) or 0.0
    revenue_yoy = float(context["kova_revenue_yoy_growth"])
    operating_income_assets = float(context["kova_operating_income_assets_ratio"])
    score = (
        1.45 * operating_income_assets
        + 0.80 * min(revenue_yoy, 0.80)
        + 0.85 * rs_score
        + 0.30 * ret20_excess_spy
        + 0.18 * float(close_location)
        + 0.03 * math.log10(max(adv20, 1.0) / 1_000_000.0)
        - 0.30 * float(realized_vol)
        - 0.18 * max(signal_return - 0.045, 0.0)
    )
    sector_meta = sector_entries[ticker]
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": "KOVA_COMPANYFACTS_CAPITAL_EFFICIENCY_PAPER",
        "candidate_score": round(score, 6),
        "signal_return": round(signal_return, 6),
        "ret20_excess_spy": round(ret20_excess_spy, 6),
        "ret60_excess_spy": round(ret60_excess_spy, 6),
        "rs_score": round(rs_score, 6),
        "close_location": round(float(close_location), 6),
        "avg_dollar_volume_20d": round(float(adv20), 2),
        "volume_ratio_20d": round(float(volume_ratio), 6),
        "realized_vol_20d": round(float(realized_vol), 6),
        "sector": sector_meta.get("sector"),
        "industry": sector_meta.get("industry"),
        "sector_coverage_status": sector_meta.get("sector_coverage_status"),
        "rule_version": RULE_VERSION,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
        **context,
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = framework.shadow._baseline_entries(before_result)
    indices = {
        ticker: framework.shadow._row_index(framework.shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    dates = [
        date_value
        for date_value in framework.shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    eligible_tickers = sorted(set(FACT_TICKERS or _load_fact_index().keys()).intersection(sector_entries, snapshot))
    candidates: list[dict[str, Any]] = []
    contexts: list[dict[str, Any]] = []
    scan = {
        "scanned_trading_days": len(dates),
        "eligible_kova_sector_warehouse_tickers": len(eligible_tickers),
        "candidate_rows_before_selection": 0,
        "candidate_days": 0,
        "rule_version": RULE_VERSION,
    }
    for signal_date in dates:
        date_count = 0
        for ticker in eligible_tickers:
            row = _candidate_for_ticker(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
            )
            if row is None:
                continue
            ab_entries = entries_by_date.get(signal_date, [])
            row["same_day_ab_entry_count"] = len(ab_entries)
            row["same_day_ab_overlap"] = bool(ab_entries)
            row["same_ticker_ab_overlap"] = any(
                trade.get("ticker") == ticker for trade in ab_entries
            )
            candidates.append(row)
            date_count += 1
        if date_count:
            scan["candidate_days"] += 1
            contexts.append(
                {
                    "date": signal_date,
                    "candidate_count": date_count,
                    "rule_version": RULE_VERSION,
                }
            )
    scan["candidate_rows_before_selection"] = len(candidates)
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["rs_score"]),
            -float(row["kova_operating_income_assets_ratio"]),
            -float(row["avg_dollar_volume_20d"]),
            str(row.get("sector") or ""),
            row["ticker"],
        )
    )
    return candidates, contexts, scan


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = ORIGINAL_GATE4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = list(gate.get("failed_reasons") or [])
    if (
        float(aggregate["expected_value_score_delta_sum"] or 0.0)
        <= ACCEPTED_COMPANYFACTS_COMPARATOR["aggregate_expected_value_delta"]
    ):
        failed.append("accepted_companyfacts_ev_not_beaten")
    if (
        float(aggregate["total_pnl_delta_sum"] or 0.0)
        <= ACCEPTED_COMPANYFACTS_COMPARATOR["aggregate_pnl_delta"]
    ):
        failed.append("accepted_companyfacts_pnl_not_beaten")
    for label, comparator in ACCEPTED_COMPANYFACTS_COMPARATOR["by_window"].items():
        window_delta = aggregate.get("by_window", {}).get(label) if False else None
        _ = window_delta
        # Per-window deltas are checked in _build_payload where the window rows are available.
        if label not in framework.WINDOWS:
            continue
    gate["accepted_companyfacts_comparator"] = ACCEPTED_COMPANYFACTS_COMPARATOR
    gate["failed_reasons"] = list(dict.fromkeys(failed))
    gate["passed"] = not gate["failed_reasons"]
    gate["decision"] = (
        "positive_replay_lead_not_promoted_kova_companyfacts_capital_efficiency"
        if gate["passed"]
        else "rejected_kova_companyfacts_capital_efficiency_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = ORIGINAL_BUILD_PAYLOAD()
    aggregate = payload["delta_metrics"]["aggregate"]
    window_failed: list[str] = []
    for label, comparator in ACCEPTED_COMPANYFACTS_COMPARATOR["by_window"].items():
        delta = payload["delta_metrics"]["by_window"][label]
        if float(delta.get("expected_value_score") or 0.0) <= comparator["expected_value_delta"]:
            window_failed.append(f"accepted_companyfacts_window_ev_not_beaten:{label}")
        if float(delta.get("total_pnl") or 0.0) <= comparator["pnl_delta"]:
            window_failed.append(f"accepted_companyfacts_window_pnl_not_beaten:{label}")
    if window_failed:
        failed = list(payload["gate4"].get("failed_reasons") or [])
        failed.extend(window_failed)
        payload["gate4"]["failed_reasons"] = list(dict.fromkeys(failed))
        payload["gate4"]["passed"] = False
        payload["gate4"]["decision"] = "rejected_kova_companyfacts_capital_efficiency_candidate_pool"
    passed = bool(payload["gate4"]["passed"])
    status = "positive_replay_lead_not_promoted" if passed else "rejected"
    reflection = {
        "why_result_happened": (
            "The broad Kova Companyfacts capital-efficiency source cleared the "
            "private replay gate, but it remains only a lead because no shared "
            "historical/daily helper exists."
            if passed
            else (
                "The broad Kova Companyfacts source did not clear the binding "
                "Gate 4/comparator screen. The likely cause is that the filed "
                "capital-efficiency filter still overlaps the already accepted "
                "Companyfacts low-liability/RS edge, while the broader universe "
                "adds old-window coverage and survivorship risk without enough "
                "incremental replacement value."
            )
        ),
        "realized_failure_mode": (
            "none_numeric_gate4_passed"
            if passed
            else "companyfacts_comparator_or_broad_universe_incremental_value_failed"
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping operating_income/assets, revenue_yoy, "
            "ret20/ret60 RS, liquidity, top-N, hold-day, cooldown, or notional "
            "thresholds on the same Kova frozen file."
        ),
        "new_evidence_required": (
            "A valid retry needs a materially different PIT data edge such as "
            "analyst breadth/dispersion, options/borrow/ownership flow, "
            "customer/supplier relation provenance, or closed forward "
            "replacement rows from a shared daily helper."
        ),
    }
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": status,
            "decision": payload["gate4"]["decision"],
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "default_off_paper_candidate_pool_scout",
            "implementation_mode": "private_replay_scout",
            "mechanism_family": "free_sec_companyfacts_plus_ohlcv_rs_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "prior_trial_count": 19,
            "nearby_prior_experiments": [
                "exp-20260528-017",
                "exp-20260613-031",
                "exp-20260613-020",
            ],
            "multiple_testing_risk_bucket": "high",
            "new_evidence_type": "broad_kova_companyfacts_filed_date_safe_candidate_pool",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "accepted_comparators": {"companyfacts_low_liability": ACCEPTED_COMPANYFACTS_COMPARATOR},
            "fact_load_summary": FACT_LOAD_SUMMARY,
            "post_run_reflection": reflection,
            "negative_reflection": None if passed else reflection["why_result_happened"],
            "next_evidence_needed": reflection["new_evidence_required"],
            "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
            "total_pnl_delta": aggregate["total_pnl_delta_sum"],
            "interpretation": (
                "The Kova Companyfacts capital-efficiency source passed only as "
                "a private replay lead; shared-paper-first promotion is required "
                "before retention."
                if passed
                else (
                    "The Kova Companyfacts capital-efficiency source was "
                    "rejected; it did not prove incremental candidate-pool value "
                    "under the standard three-window protocol and accepted "
                    "Companyfacts comparator."
                )
            ),
            "rejection_reason": None if passed else "; ".join(payload["gate4"]["failed_reasons"]),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "min_price": MIN_PRICE,
        "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
        "min_revenue_yoy": MIN_REVENUE_YOY,
        "min_operating_income_assets": MIN_OPERATING_INCOME_ASSETS,
        "max_fact_end_age_days": MAX_FACT_END_AGE_DAYS,
        "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
        "min_ret60_excess_spy": MIN_RET60_EXCESS_SPY,
        "min_rs_score": MIN_RS_SCORE,
        "min_close_location": MIN_CLOSE_LOCATION,
        "min_signal_return": MIN_SIGNAL_RETURN,
        "max_signal_return": MAX_SIGNAL_RETURN,
        "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
        "source_facts_path": framework._repo_rel(KOVA_FACTS_PATH),
    }
    payload["gate2"]["runtime_fields"] = [
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
        "data/non_ohlcv/sec_companyfacts_selected_kova_20260613.jsonl filed/end/canonical/value",
        "warehouse ohlcv Date/Open/High/Low/Close/Volume",
        "SPY OHLCV Close rows for RS proxy",
        "data/reference/broad_market_sector_map.json sector/status",
    ]
    payload["gate2"]["note"] = (
        "Companyfacts rows are gated by filed date <= signal_date and period "
        "end <= signal_date; OHLCV signal fields use signal-date/trailing rows; "
        "paper entry remains next open."
    )
    payload["gate3"]["candidate_pool_changed"] = True
    payload["gate3"]["note"] = (
        "No live/core filter was added. The source is an additive default-off "
        "paper candidate pool; core signals generated/survived are unchanged."
    )
    return payload


def _window_table(payload: dict[str, Any]) -> list[str]:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Raw | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | "
            "${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {raw} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                raw=payload["raw_candidate_counts"][label],
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    return rows


def _build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Kova Companyfacts Capital Efficiency",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## History Check",
            "",
            json.dumps(PRE_RUN_QUESTIONS["2_history_check"], ensure_ascii=True, indent=2),
            "",
            "## Gate 4",
            "",
            *_window_table(payload),
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate PnL delta: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Target trades: `{}`".format(
                payload["target_trade_summary"]["total_trade_count"]
            ),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "",
            "## Production Impact",
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
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
        "production_accepted": False,
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": (
            "data/experiments/exp-20260602-003/"
            "exp_20260602_003_post_earnings_explicit_continuation.json"
        ),
        "artifact": framework._repo_rel(OUT_JSON),
        "log": framework._repo_rel(LOG_JSON),
        "card": framework._repo_rel(CARD_MD),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "accepted_comparators": payload["accepted_comparators"],
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_after": payload["after_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "pnl_delta": payload["delta_metrics"]["by_window"][label]["total_pnl"],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
                "raw_candidate_count": payload["raw_candidate_counts"][label],
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "post_run_reflection": payload["post_run_reflection"],
        "negative_reflection": payload["negative_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _update_ticket_and_registry(
    payload: dict[str, Any],
    log_record: dict[str, Any],
) -> None:
    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8")) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "decision": payload["decision"],
            "summary": payload["interpretation"],
            "result": {
                "decision": payload["decision"],
                "artifact": framework._repo_rel(OUT_JSON),
                "log": framework._repo_rel(LOG_JSON),
                "card": framework._repo_rel(CARD_MD),
                "aggregate_expected_value_delta": log_record[
                    "aggregate_expected_value_delta"
                ],
                "aggregate_strategy_total_pnl_delta": log_record[
                    "aggregate_strategy_total_pnl_delta"
                ],
                "accepted": False,
                "accepted_alpha": False,
                "calibration": payload["calibration"],
                "gate4": payload["gate4"],
            },
        }
    )
    framework._write_json(TICKET_JSON, ticket)

    result = {
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "artifact": framework._repo_rel(OUT_JSON),
        "log": framework._repo_rel(LOG_JSON),
        "card": framework._repo_rel(CARD_MD),
        "aggregate_expected_value_delta": log_record["aggregate_expected_value_delta"],
        "aggregate_strategy_total_pnl_delta": log_record[
            "aggregate_strategy_total_pnl_delta"
        ],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
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
        "artifact": framework._repo_rel(OUT_JSON),
        "log": framework._repo_rel(LOG_JSON),
        "ticket_file": framework._repo_rel(TICKET_JSON),
        "card_file": framework._repo_rel(CARD_MD),
        "revision_manifest_file": framework._repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": log_record["aggregate_expected_value_delta"],
        "aggregate_strategy_total_pnl_delta": log_record[
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


def _patch_framework() -> None:
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
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._gate4 = _gate4
    framework._build_payload = _build_payload
    framework._build_card = _build_card
    framework._build_log_record = _build_log_record
    framework._update_ticket_and_registry = _update_ticket_and_registry
    framework._configure_sleeve_globals()


def main() -> None:
    _patch_framework()
    framework.main()


if __name__ == "__main__":
    main()
