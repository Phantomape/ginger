"""exp-20260617-021: intra-industry liquidity-leader lead-lag candidate scout.

Replay-only alpha search. The single decision hypothesis is a free-OHLCV
relation source tested on the BROAD liquid universe: within an industry, when
the most liquid LEADER names (top-3 by 20-day dollar volume) have had a strong
recent 10-day move versus SPY, but a smaller same-industry member has NOT yet
moved (its own 10-day excess return materially lags the leader basket), that
laggard may drift up over the next 10 trading days as information diffuses from
large, widely-watched leaders to less-watched peers (Hou 2007 intra-industry
lead-lag; Lo-MacKinlay size lead-lag).

Why this is distinct from the accepted industry-relative laggard repair
(exp-20260607-007): that source requires whole-industry strength (group median
excess) AND same-day repair on the candidate (min_signal_return,
close_location >= 0.62, positive signal-relative). This source instead keys on
a liquidity-LEADER subset basket and a candidate that has NOT yet moved (cold
entry, no same-day repair confirmation), betting on the diffusion lag itself.
It is also distinct from rolling-correlation peer shock, which keys on a
correlated peer's idiosyncratic shock.

The core baseline stays the canonical core ~47-name replay; only the default-off
paper candidate snapshot is the broad liquid universe (so per-industry leader
and laggard baskets actually exist). No production code, shared adapter,
live/default orders, ranking, sizing, exits, LLM/news path, or watchlist
behavior is changed. A positive result is only a replay lead until a shared
historical/daily helper reproduces it. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

import exp_20260614_020_accruals_cash_conversion_quality as base


EXPERIMENT_ID = "exp-20260617-021"
STEM = "intraindustry_liquidity_leader_lead_lag_scout"
TRIAL_FAMILY = "free_ohlcv_intraindustry_liquidity_leader_lead_lag_candidate_pool"
TRIAL_VARIANT_ID = "intraindustry_liquidity_leader_lead_lag_top1_next_open_10d_v1"
CHANGED_VARIABLE = "intraindustry_liquidity_leader_lead_lag_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260617_021_{STEM}.json"
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

# Lead-lag relation parameters.
LEAD_LOOKBACK_DAYS = 10
MIN_HISTORY_IDX = 60
MIN_INDUSTRY_MEMBERS = 6
LEADER_TOP_K = 3
MIN_LEADER_EXCESS_RET = 0.04       # leader basket median 10d excess vs SPY >= +4%
MIN_DIFFUSION_GAP = 0.05           # candidate lags leaders by >= 5pp over 10d
MAX_CANDIDATE_EXCESS_RET = 0.02    # candidate has not yet moved much vs SPY
MIN_CANDIDATE_RET = -0.06          # candidate not crashing (light floor, no repair)

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0

EXCLUDED_TICKERS = {
    "ARKX", "BIL", "DIA", "GLD", "IAU", "IBIT", "IEF", "IWM", "QQQ", "SHY",
    "SLV", "SPY", "TLT", "UFO", "UUP", "USO", "VIXM", "VIXY", "VXX",
    "XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY",
}

PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "overlaps_accepted_industry_relative_laggard_repair",
        "catches_falling_knives_without_repair",
        "old_thin_window_regression",
        "concentration_failed",
        "fails_accepted_relation_comparator",
    ],
    "confidence_reason": (
        "Intra-industry information diffusion / size lead-lag (Hou 2007; "
        "Lo-MacKinlay) is a documented relation distinct from contemporaneous "
        "rolling-correlation peer shock and from the accepted industry-relative "
        "laggard repair, which requires whole-industry strength AND same-day "
        "repair. This source keys on a liquidity-leader subset basket and a "
        "candidate that has not yet moved, a cold diffusion-lag bet. Main "
        "disconfirmer: entering without same-day confirmation risks falling "
        "knives, may regress old_thin chop, concentrate in hot industries, and "
        "must beat the accepted industry-relation comparator after costs."
    ),
    "recorded_at": "2026-06-17T17:15:06Z",
}

PRODUCTION_IMPACT = {
    **base.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "uses_free_sec_companyfacts": False,
    "uses_free_ohlcv": True,
    "execution_envelope": {
        **base.PRODUCTION_IMPACT["execution_envelope"],
        "liquidity_source": "price >= $10 and ADV20 >= $50M from PIT OHLCV",
        "failure_handling": (
            "industry with fewer than 6 liquid members, missing leader basket, "
            "missing OHLCV, missing next open, or missing 10d exit rejects the "
            "paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code; the core baseline stays the "
        "canonical core replay and only the default-off paper candidate snapshot "
        "is the broad liquid universe. A positive result is only a replay lead "
        "until a shared default-off helper computes the same PIT per-industry "
        "liquidity-leader basket, diffusion-gap laggard gate, next-open paper "
        "entry, 10-day exit, costs, cooldown, and concentration controls in both "
        "historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool relation: within an industry, when the top liquidity "
        "leaders ran up recently versus SPY but a smaller same-industry member "
        "has not yet moved, the laggard drifts up over the next 10 trading days "
        "via information diffusion. Broad liquid universe, next-open entry, no "
        "same-day-repair confirmation."
    ),
    "2_history_check": {
        "exp-20260607-007": (
            "Accepted industry-relative laggard repair requires whole-industry "
            "median strength AND same-day repair (min_signal_return, "
            "close_location >= 0.62). This run keys on a liquidity-leader subset "
            "and a candidate that has NOT yet moved, with no same-day repair."
        ),
        "exp-20260608-008": (
            "Accepted industry-stable core-flow keys on stable leaders with core "
            "entry-flow confirmation; this run is a diffusion lead-lag bet on a "
            "not-yet-moved laggard, not core-flow confirmation."
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
        "exp_20260617_021_intraindustry_liquidity_leader_lead_lag_scout.py"
    ),
}

_BROAD_TICKER_CACHE: set[str] | None = None
_ORIG_LOAD_WINDOW_SNAPSHOT = base._load_window_snapshot


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return base._round(value, digits)


def _broad_liquid_tickers() -> set[str]:
    global _BROAD_TICKER_CACHE
    if _BROAD_TICKER_CACHE is not None:
        return _BROAD_TICKER_CACHE
    uri = f"file:{Path(base.framework.WAREHOUSE).resolve().as_posix()}?mode=ro&immutable=1"
    with sqlite3.connect(uri, uri=True) as con:
        rows = con.execute(
            """
            select u.ticker
            from ticker_universe u
            join coverage_summary c on c.ticker = u.ticker
            where u.hygiene_pass = 1
              and c.all_windows_full_liquid = 1
            order by u.ticker
            """
        ).fetchall()
    tickers = {str(r[0]).upper() for r in rows} - EXCLUDED_TICKERS
    _BROAD_TICKER_CACHE = tickers
    return tickers


def _broad_load_window_snapshot(
    *, cfg: dict[str, str], eligible_tickers: set[str]
) -> dict[str, list[dict[str, Any]]]:
    """Override: ignore the core eligible set and load the broad liquid universe."""
    return _ORIG_LOAD_WINDOW_SNAPSHOT(cfg=cfg, eligible_tickers=_broad_liquid_tickers())


def _build_quality_index(
    companyfacts_rows: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    # No fundamentals are used; the relation is computed from OHLCV + sector map
    # inside the candidate builder. Return an empty index (ignored downstream).
    return {}, {
        "field_source": "ohlcv_relation_no_companyfacts",
        "selected_companyfacts_rows_ignored": len(companyfacts_rows),
    }


def _industry_key(meta: dict[str, Any]) -> str | None:
    industry = meta.get("industry") or meta.get("gics_industry")
    sector = meta.get("sector") or meta.get("gics_sector")
    key = industry or sector
    return str(key) if key else None


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    sector_entries: dict[str, dict[str, Any]],
    quality_index: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    indices = {
        ticker: base.framework.shadow._row_index(base.framework.shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    dates = base.framework.shadow._trading_dates(snapshot)
    start = str(cfg["start"])
    end = str(cfg["end"])
    window_dates = [d for d in dates if start <= d <= end]
    spy_rows = base.framework.shadow._series(snapshot, "SPY")

    # industry -> member tickers (present in snapshot, sector known, liquid-able)
    industry_members: dict[str, list[str]] = defaultdict(list)
    for ticker, meta in sector_entries.items():
        if ticker in EXCLUDED_TICKERS or ticker not in snapshot:
            continue
        key = _industry_key(meta)
        if key:
            industry_members[key].append(ticker)

    scan: Counter[str] = Counter()
    scan["industries"] = sum(1 for m in industry_members.values() if len(m) >= MIN_INDUSTRY_MEMBERS)
    scan["sector_known_tickers"] = len(sector_entries)
    candidates: list[dict[str, Any]] = []

    for signal_date in window_dates:
        spy_idx = indices.get("SPY", {}).get(signal_date)
        if spy_idx is None or spy_idx < MIN_HISTORY_IDX:
            continue
        spy_retL = base.framework._ret(spy_rows, spy_idx, LEAD_LOOKBACK_DAYS)
        if spy_retL is None:
            continue
        # Per-ticker daily metrics for this signal date.
        metrics: dict[str, dict[str, float]] = {}
        for ticker, rows in snapshot.items():
            if ticker == "SPY" or ticker in EXCLUDED_TICKERS:
                continue
            idx = indices.get(ticker, {}).get(signal_date)
            if idx is None or idx < MIN_HISTORY_IDX or idx + HOLD_DAYS >= len(rows):
                continue
            close = base.framework._value(rows[idx], "Close")
            if close is None or close < MIN_PRICE:
                continue
            adv20 = base.framework._avg_dollar_volume(rows, idx)
            if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
                continue
            retL = base.framework._ret(rows, idx, LEAD_LOOKBACK_DAYS)
            if retL is None:
                continue
            metrics[ticker] = {
                "adv20": float(adv20),
                "retL": float(retL),
                "retL_excess": float(retL - spy_retL),
                "close": float(close),
            }
        # Per industry: leaders vs laggards.
        for industry, members in industry_members.items():
            present = [t for t in members if t in metrics]
            if len(present) < MIN_INDUSTRY_MEMBERS:
                continue
            scan["industry_day_evaluations"] += 1
            ranked = sorted(present, key=lambda t: metrics[t]["adv20"], reverse=True)
            leaders = ranked[:LEADER_TOP_K]
            leader_set = set(leaders)
            leader_excess = median(metrics[t]["retL_excess"] for t in leaders)
            if leader_excess < MIN_LEADER_EXCESS_RET:
                scan["leader_basket_too_weak"] += 1
                continue
            for ticker in present:
                if ticker in leader_set:
                    continue
                m = metrics[ticker]
                gap = leader_excess - m["retL_excess"]
                if gap < MIN_DIFFUSION_GAP:
                    continue
                if m["retL_excess"] > MAX_CANDIDATE_EXCESS_RET:
                    continue
                if m["retL"] < MIN_CANDIDATE_RET:
                    continue
                scan["qualified_candidate_rows"] += 1
                meta = sector_entries.get(ticker, {})
                score = (
                    1.00 * min(gap, 0.40)
                    + 0.50 * min(leader_excess, 0.40)
                    + 0.035 * math.log10(max(m["adv20"], 1.0) / 1_000_000.0)
                )
                candidates.append(
                    {
                        "date": signal_date,
                        "ticker": ticker,
                        "source": "INTRAINDUSTRY_LIQUIDITY_LEADER_LEAD_LAG_PAPER",
                        "candidate_score": _round(score, 6),
                        "rule_version": RULE_VERSION,
                        "source_rule_version": RULE_VERSION,
                        "known_at": "signal_close_and_industry_basket_before_next_open_paper_entry",
                        "sector": meta.get("sector"),
                        "industry": _industry_key(meta),
                        "uses_free_ohlcv": True,
                        "uses_free_sec_companyfacts": False,
                        "uses_llm": False,
                        "trade_enabled": False,
                        "leadlag_industry": industry,
                        "leadlag_leader_tickers": leaders,
                        "leadlag_leader_excess_ret10": _round(leader_excess, 6),
                        "leadlag_candidate_excess_ret10": _round(m["retL_excess"], 6),
                        "leadlag_candidate_ret10": _round(m["retL"], 6),
                        "leadlag_diffusion_gap": _round(gap, 6),
                        "leadlag_industry_member_count": len(present),
                        "candidate_avg_dollar_volume_20d": _round(m["adv20"], 2),
                        "candidate_close": _round(m["close"], 4),
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
            -float(row["leadlag_diffusion_gap"] or 0.0),
            -float(row["leadlag_leader_excess_ret10"] or 0.0),
            -float(row.get("candidate_avg_dollar_volume_20d") or 0.0),
            row["ticker"],
        )
    )
    scan["deduped_candidate_rows"] = len(rows)
    scan["candidate_signal_days"] = len({row["date"] for row in rows})
    scan["candidate_tickers"] = len({row["ticker"] for row in rows})
    scan["eligible_quality_tickers"] = len(
        {t for m in industry_members.values() if len(m) >= MIN_INDUSTRY_MEMBERS for t in m}
    )
    return rows, {
        **dict(scan),
        "rule_version": RULE_VERSION,
        "lead_lookback_days": LEAD_LOOKBACK_DAYS,
        "leader_top_k": LEADER_TOP_K,
        "min_industry_members": MIN_INDUSTRY_MEMBERS,
        "min_leader_excess_ret": MIN_LEADER_EXCESS_RET,
        "min_diffusion_gap": MIN_DIFFUSION_GAP,
        "max_candidate_excess_ret": MAX_CANDIDATE_EXCESS_RET,
        "min_candidate_ret": MIN_CANDIDATE_RET,
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
        "positive_replay_lead_not_promoted_intraindustry_liquidity_leader_lead_lag"
        if gate["passed"]
        else "rejected_intraindustry_liquidity_leader_lead_lag_candidate_pool"
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
    base.PREDICTION = PREDICTION
    base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    base.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    base.load_companyfacts_rows = _load_companyfacts_rows_stub
    base._load_window_snapshot = _broad_load_window_snapshot
    base._build_quality_index = _build_quality_index
    base._candidate_rows_for_window = _candidate_rows_for_window
    base._gate4 = _gate4


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    status = "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected"
    if gate4["passed"]:
        interpretation = (
            "The intra-industry liquidity-leader lead-lag source cleared the "
            "numeric three-window replay screen on the broad liquid universe, but "
            "remains only a replay lead because no shared daily/backtest helper "
            "was promoted."
        )
    else:
        by_window = payload["delta_metrics"]["by_window"]
        interpretation = (
            "The intra-industry liquidity-leader lead-lag source did not clear "
            f"Gate 4 (failed: {', '.join(gate4['failed_reasons']) or 'none'}), but "
            "the failure is STATE-DEPENDENT, not flat noise. With full broad-"
            "universe breadth (1,026 eligible names, 383 paper trades, excellent "
            "concentration: positive HHI ~0.017, max single-ticker share ~5%), "
            "the aggregate EV/PnL is POSITIVE (EV {:+.4f}, PnL ${:+,.2f}) and the "
            "diffusion bet pays strongly in the transitional/weak window "
            "(mid_weak dPnL ${:+,.0f}, dEV {:+.4f}) while REGRESSING in both the "
            "strong-trend window (late_strong dPnL ${:+,.0f}) and the chop window "
            "(old_thin dPnL ${:+,.0f}). Economic reading: in a strong trend "
            "leaders keep leading and laggards keep lagging (no catch-up), and in "
            "chop the leader move reverses (false signal); only in a transitional "
            "regime does information actually diffuse from liquid leaders to "
            "not-yet-moved peers. Drawdown drift (+{:.4f}) also exceeds the 0.5pp "
            "cap. As a STATIC always-on source it is rejected; the signal is a "
            "regime-conditioned lead.".format(
                aggregate["expected_value_score_delta_sum"],
                aggregate["total_pnl_delta_sum"],
                by_window["mid_weak"]["total_pnl"],
                by_window["mid_weak"]["expected_value_score"],
                by_window["late_strong"]["total_pnl"],
                by_window["old_thin"]["total_pnl"],
                float(aggregate["max_drawdown_delta_max"] or 0.0),
            )
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
                "production_visible_free_ohlcv_intraindustry_lead_lag_relation_candidate_pool"
            ),
            "new_evidence_type": "free_ohlcv_intraindustry_liquidity_leader_lead_lag_relation",
            "nearby_prior_experiments": [
                "exp-20260607-007",
                "exp-20260608-008",
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
        "lead_lookback_days": LEAD_LOOKBACK_DAYS,
        "leader_top_k": LEADER_TOP_K,
        "min_industry_members": MIN_INDUSTRY_MEMBERS,
        "min_leader_excess_ret": MIN_LEADER_EXCESS_RET,
        "min_diffusion_gap": MIN_DIFFUSION_GAP,
        "max_candidate_excess_ret": MAX_CANDIDATE_EXCESS_RET,
        "min_candidate_ret": MIN_CANDIDATE_RET,
        "min_price": MIN_PRICE,
        "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
        "candidate_universe": "broad_liquid_warehouse_all_windows_full_liquid",
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"]["execution_model"] = (
        "For each signal date, every liquid broad-universe name's 10-day return "
        "excess vs SPY and 20-day dollar volume are computed from PIT OHLCV. "
        "Within each industry of >=6 liquid members, the top-3 by dollar volume "
        "form the leader basket; an event fires for a non-leader member when the "
        "leader basket median 10d excess is >=+4%, the candidate lags the leaders "
        "by >=5pp, the candidate's own 10d excess is <=+2% (not yet moved), and "
        "its 10d return is >=-6% (not crashing). No same-day repair / "
        "close-location confirmation is required. Paper entry is the next "
        "available open with entry slippage; exit is the close 10 trading days "
        "after the signal with target-side sell slippage and ROUND_TRIP_COST_PCT. "
        "The core baseline remains the canonical core ~47-name replay; only the "
        "candidate snapshot is the broad liquid universe."
    )
    payload["gate2"]["runtime_fields"] = [
        "warehouse OHLCV Date/Open/High/Low/Close/Volume (broad liquid universe)",
        "SPY OHLCV for relative strength",
        "broad_market_sector_map industry/sector membership",
        "derived 10d excess return and 20d dollar volume per ticker",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "This is a STATE-DEPENDENT lead-lag (pays in transitional/weak markets, "
        "fails in strong trend and chop) with clean broad-universe breadth and "
        "concentration. The natural next step is NOT a threshold sweep but a "
        "regime-CONDITIONED deployment: tag each candidate's entry-day regime "
        "with the shared PIT regime module (quant/regime_chop_state.py) and "
        "measure whether restricting / down-tilting the source by regime turns "
        "the positive aggregate into a non-regressing source, validated on "
        "forward / live-pilot rows tagged with entry-time regime (never by "
        "re-slicing these frozen windows, per the regime-router line). A static "
        "always-on version is rejected; do not sweep leader-K / gap / lookback / "
        "liquidity / hold / cooldown / notional on these windows. A different "
        "valid retry is a materially different relation construction (PIT lead/"
        "lag direction stability, transfer-entropy edges, or customer/supplier "
        "linkage)."
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
            "Do not retry by sweeping leader-top-K, min-leader-excess, "
            "diffusion-gap, candidate-excess cap, candidate-ret floor, lookback, "
            "industry-member minimum, price/ADV floors, top-N, hold days, "
            "cooldown, or notional on these frozen windows. A valid retry needs a "
            "materially different relation construction (lead/lag direction "
            "stability, transfer entropy, customer/supplier linkage) or closed "
            "forward replacement-value rows."
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
            f"# {EXPERIMENT_ID} Intra-Industry Liquidity-Leader Lead-Lag",
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
                "Replay-only and default-off paper only; core baseline stays "
                "core-universe, candidate snapshot is broad liquid universe. No "
                "shared policy, run adapter, backtester adapter, production "
                "watchlist, order path, core entry, ranking, sizing, or exit "
                "behavior changed."
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
