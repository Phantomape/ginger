"""exp-20260605-014: Broad Companyfacts peer-confirmed filing drift.

This alpha search tests one replay-only/default-off paper candidate source:
SEC Companyfacts dual realized growth is only eligible when a recent
same-industry peer also has fresh dual-growth evidence. The intent is to
extend the candidate pool with a relationship field instead of another
threshold/scalar retune.

No production adapter, live order path, shared policy, ranking, sizing, exits,
LLM/news path, or watchlist is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from broad_market_sector_map import (  # noqa: E402
    OK_STATUS,
    RULE_VERSION as SECTOR_MAP_RULE_VERSION,
    coverage_report,
    load_cache,
    lookup_sector,
)
import exp_20260605_011_broad_companyfacts_dual_growth_rs_candidate_pool as base  # noqa: E402


EXP_ID = "exp-20260605-014"
STEM = "broad_companyfacts_peer_confirmed_filing_drift"
TRIAL_FAMILY = "broad_companyfacts_peer_confirmed_filing_drift_candidate_pool"
TRIAL_VARIANT_ID = "broad_companyfacts_peer_confirmed_filing_drift_top1_v1"
CHANGED_VARIABLE = "broad_companyfacts_peer_confirmed_filing_drift_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"exp_20260605_014_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXP_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"

PAPER_NOTIONAL = 4_000.0
HOLD_DAYS = 10
MAX_DRAWDOWN_WORSE = 0.005
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.30

MAX_FUNDAMENTAL_AGE_DAYS = 120
PEER_CONFIRMATION_LOOKBACK_DAYS = 45
MIN_PEER_CONFIRMATIONS = 1
MIN_REVENUE_YOY_GROWTH = 0.15
MIN_PROFIT_YOY_GROWTH = 0.15
MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_RET20_EXCESS_SPY = 0.00
MIN_CLOSE_LOCATION = 0.55
MIN_VOLUME_RATIO_20D = 0.90
SAME_TICKER_COOLDOWN_DAYS = 30

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_no_live_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "parity_note": (
        "This runner changes no production code. A positive result would "
        "require a separate shared default-off Companyfacts peer-confirmation "
        "adapter, daily production exposure of the same filed-date-safe "
        "growth and industry fields, warehouse/snapshot replay parity, and "
        "focused tests before any report queue, paper ledger, candidate "
        "priority, or order surface could change."
    ),
}


_DUAL_GROWTH_CACHE: dict[tuple[str, str], dict[str, Any] | None] = {}


def _patch_base_module() -> None:
    """Point the reused measurement harness at this experiment."""

    base.EXP_ID = EXP_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.RULE_VERSION = RULE_VERSION
    base.OUT_DIR = OUT_DIR
    base.OUT_JSON = OUT_JSON
    base.BEFORE_JSON = BEFORE_JSON
    base.AFTER_JSON = AFTER_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.CARD_MD = CARD_MD
    base.ARTIFACT_MD = ARTIFACT_MD
    base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    base.PAPER_NOTIONAL = PAPER_NOTIONAL
    base.HOLD_DAYS = HOLD_DAYS
    base.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    base.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    base.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    base.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    base.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    base.MAX_FUNDAMENTAL_AGE_DAYS = MAX_FUNDAMENTAL_AGE_DAYS
    base.MIN_REVENUE_YOY_GROWTH = MIN_REVENUE_YOY_GROWTH
    base.MIN_PROFIT_YOY_GROWTH = MIN_PROFIT_YOY_GROWTH
    base.MIN_PRICE = MIN_PRICE
    base.MIN_AVG_DOLLAR_VOLUME_20D = MIN_AVG_DOLLAR_VOLUME_20D
    base.MIN_RET20_EXCESS_SPY = MIN_RET20_EXCESS_SPY
    base.MIN_CLOSE_LOCATION = MIN_CLOSE_LOCATION
    base.MIN_VOLUME_RATIO_20D = MIN_VOLUME_RATIO_20D
    base.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS


def _latest_dual_growth(
    growth_index: dict[str, dict[str, list[dict[str, Any]]]],
    ticker: str,
    signal_day_s: str,
) -> dict[str, Any] | None:
    cache_key = (ticker, signal_day_s)
    if cache_key in _DUAL_GROWTH_CACHE:
        return _DUAL_GROWTH_CACHE[cache_key]

    revenue = base._latest_growth_row(growth_index, ticker, "revenue", signal_day_s)
    profit = base._profit_growth_row(growth_index, ticker, signal_day_s)
    if revenue is None or profit is None:
        _DUAL_GROWTH_CACHE[cache_key] = None
        return None
    revenue_growth = float(revenue["yoy_growth"])
    profit_growth = float(profit["yoy_growth"])
    if revenue_growth < MIN_REVENUE_YOY_GROWTH or profit_growth < MIN_PROFIT_YOY_GROWTH:
        _DUAL_GROWTH_CACHE[cache_key] = None
        return None
    if revenue.get("current_value") is None or float(revenue["current_value"]) <= 0.0:
        _DUAL_GROWTH_CACHE[cache_key] = None
        return None

    filing_date = max(str(revenue["asof_date"]), str(profit["asof_date"]))
    filing_age_days = (pd.Timestamp(signal_day_s) - pd.Timestamp(filing_date)).days
    if filing_age_days < 0 or filing_age_days > MAX_FUNDAMENTAL_AGE_DAYS:
        _DUAL_GROWTH_CACHE[cache_key] = None
        return None

    result = {
        "revenue": revenue,
        "profit": profit,
        "revenue_growth": revenue_growth,
        "profit_growth": profit_growth,
        "filing_date": filing_date,
        "filing_age_days": filing_age_days,
        "growth_score": min(max(revenue_growth, -1.0), 1.5)
        + min(max(profit_growth, -1.0), 1.5),
    }
    _DUAL_GROWTH_CACHE[cache_key] = result
    return result


def _load_industry_groups(
    frames: dict[str, pd.DataFrame],
) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]], dict[str, Any]]:
    cache = load_cache()
    sector_lookup: dict[str, dict[str, Any]] = {}
    groups: defaultdict[str, list[str]] = defaultdict(list)
    for ticker in frames:
        lookup = lookup_sector(ticker, cache)
        sector_lookup[ticker] = lookup
        industry = str(lookup.get("industry") or "").strip()
        if lookup.get("status") == OK_STATUS and industry:
            groups[industry].append(ticker)
    return (
        sector_lookup,
        {key: sorted(values) for key, values in groups.items()},
        coverage_report(frames.keys(), cache),
    )


def _peer_confirmations(
    *,
    growth_index: dict[str, dict[str, list[dict[str, Any]]]],
    ticker: str,
    signal_day_s: str,
    industry: str,
    industry_groups: dict[str, list[str]],
) -> list[dict[str, Any]]:
    peers: list[dict[str, Any]] = []
    for peer_ticker in industry_groups.get(industry, []):
        if peer_ticker == ticker:
            continue
        peer_growth = _latest_dual_growth(growth_index, peer_ticker, signal_day_s)
        if peer_growth is None:
            continue
        if peer_growth["filing_age_days"] > PEER_CONFIRMATION_LOOKBACK_DAYS:
            continue
        peers.append(
            {
                "ticker": peer_ticker,
                "filing_date": peer_growth["filing_date"],
                "filing_age_days": peer_growth["filing_age_days"],
                "revenue_yoy_growth": round(peer_growth["revenue_growth"], 6),
                "profit_yoy_growth": round(peer_growth["profit_growth"], 6),
                "growth_score": round(peer_growth["growth_score"], 6),
            }
        )
    peers.sort(key=lambda row: (row["growth_score"], -row["filing_age_days"]), reverse=True)
    return peers


def _score_candidate(
    *,
    own_growth_score: float,
    peer_confirmations: list[dict[str, Any]],
    ret20_excess_spy: float,
    close_location: float,
    volume_ratio_20d: float,
) -> float:
    peer_count = min(len(peer_confirmations), 4)
    peer_score = sum(float(row["growth_score"]) for row in peer_confirmations[:3])
    return (
        own_growth_score
        + 0.60 * peer_count
        + 0.20 * min(peer_score, 4.5)
        + 3.0 * ret20_excess_spy
        + close_location
        + 0.10 * min(volume_ratio_20d, 3.0)
    )


def _candidate_for_ticker_day(
    *,
    ticker: str,
    frame: pd.DataFrame,
    spy_frame: pd.DataFrame,
    signal_day: pd.Timestamp,
    growth_index: dict[str, dict[str, list[dict[str, Any]]]],
    sector_lookup: dict[str, dict[str, Any]],
    industry_groups: dict[str, list[str]],
) -> dict[str, Any] | None:
    pos = base._frame_pos(frame, signal_day)
    spy_pos = base._frame_pos(spy_frame, signal_day)
    if pos is None or spy_pos is None:
        return None
    if pos < 20 or spy_pos < 20:
        return None

    signal_day_s = str(signal_day.date())
    own_growth = _latest_dual_growth(growth_index, ticker, signal_day_s)
    if own_growth is None:
        return None

    lookup = sector_lookup.get(ticker) or {}
    industry = str(lookup.get("industry") or "").strip()
    if not industry:
        return None
    peers = _peer_confirmations(
        growth_index=growth_index,
        ticker=ticker,
        signal_day_s=signal_day_s,
        industry=industry,
        industry_groups=industry_groups,
    )
    if len(peers) < MIN_PEER_CONFIRMATIONS:
        return None

    close = float(frame["Close"].iloc[pos])
    if close < MIN_PRICE:
        return None
    adv20 = base._avg_dollar_volume(frame, pos)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None
    volume_ratio_20d = base._volume_ratio(frame, pos)
    if volume_ratio_20d is None or volume_ratio_20d < MIN_VOLUME_RATIO_20D:
        return None
    close_location = base._close_location(frame, pos)
    if close_location is None or close_location < MIN_CLOSE_LOCATION:
        return None
    ret20 = base._ret(frame, pos, 20)
    spy_ret20 = base._ret(spy_frame, spy_pos, 20)
    if ret20 is None or spy_ret20 is None:
        return None
    ret20_excess_spy = ret20 - spy_ret20
    if ret20_excess_spy < MIN_RET20_EXCESS_SPY:
        return None

    revenue = own_growth["revenue"]
    profit = own_growth["profit"]
    score = _score_candidate(
        own_growth_score=float(own_growth["growth_score"]),
        peer_confirmations=peers,
        ret20_excess_spy=ret20_excess_spy,
        close_location=close_location,
        volume_ratio_20d=volume_ratio_20d,
    )
    metadata = {
        "companyfacts_revenue_yoy_growth": round(own_growth["revenue_growth"], 6),
        "companyfacts_profit_yoy_growth": round(own_growth["profit_growth"], 6),
        "companyfacts_profit_canonical": profit["canonical"],
        "companyfacts_revenue_asof_date": revenue["asof_date"],
        "companyfacts_profit_asof_date": profit["asof_date"],
        "companyfacts_filing_date": own_growth["filing_date"],
        "companyfacts_filing_age_days": own_growth["filing_age_days"],
        "companyfacts_revenue_form": revenue.get("current_form"),
        "companyfacts_profit_form": profit.get("current_form"),
        "peer_relation_type": "same_industry_recent_dual_growth",
        "peer_relation_key": industry,
        "peer_relation_sector": lookup.get("sector"),
        "peer_relation_rule_version": SECTOR_MAP_RULE_VERSION,
        "peer_confirmation_lookback_days": PEER_CONFIRMATION_LOOKBACK_DAYS,
        "peer_confirmation_count": len(peers),
        "peer_confirmation_tickers": [row["ticker"] for row in peers[:8]],
        "peer_confirmation_score": round(sum(float(row["growth_score"]) for row in peers), 6),
        "peer_confirmations": peers[:8],
        "ret20": round(ret20, 6),
        "spy_ret20": round(spy_ret20, 6),
        "ret20_excess_spy": round(ret20_excess_spy, 6),
        "close_location": round(close_location, 6),
        "avg_dollar_volume_20d": round(adv20, 2),
        "volume_ratio_20d": round(volume_ratio_20d, 6),
        "candidate_score": round(score, 6),
        "source": "BROAD_COMPANYFACTS_PEER_CONFIRMED_FILING_DRIFT_PAPER",
    }
    return base._candidate_trade(ticker, frame, signal_day, pos, metadata)


def _generate_candidates(
    frames: dict[str, pd.DataFrame],
    growth_index: dict[str, dict[str, list[dict[str, Any]]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    spy_frame = frames.get("SPY")
    if spy_frame is None:
        raise RuntimeError("SPY missing from warehouse frames")

    sector_lookup, industry_groups, sector_coverage = _load_industry_groups(frames)
    selected: list[dict[str, Any]] = []
    candidates_by_window: dict[str, int] = defaultdict(int)
    selected_by_window: dict[str, int] = defaultdict(int)
    peer_rejected_by_window: dict[str, int] = defaultdict(int)
    last_selected_by_ticker: dict[str, pd.Timestamp] = {}

    for label, window in base.WINDOWS.items():
        for day in base._trading_days(frames, window["start"], window["end"]):
            day_candidates: list[dict[str, Any]] = []
            for ticker, frame in frames.items():
                if ticker == "SPY":
                    continue
                last_selected = last_selected_by_ticker.get(ticker)
                if (
                    last_selected is not None
                    and (day - last_selected).days < SAME_TICKER_COOLDOWN_DAYS
                ):
                    continue
                candidate = _candidate_for_ticker_day(
                    ticker=ticker,
                    frame=frame,
                    spy_frame=spy_frame,
                    signal_day=day,
                    growth_index=growth_index,
                    sector_lookup=sector_lookup,
                    industry_groups=industry_groups,
                )
                if candidate is None:
                    own_growth = _latest_dual_growth(growth_index, ticker, str(day.date()))
                    industry = str((sector_lookup.get(ticker) or {}).get("industry") or "")
                    if own_growth is not None and industry:
                        peers = _peer_confirmations(
                            growth_index=growth_index,
                            ticker=ticker,
                            signal_day_s=str(day.date()),
                            industry=industry,
                            industry_groups=industry_groups,
                        )
                        if len(peers) < MIN_PEER_CONFIRMATIONS:
                            peer_rejected_by_window[label] += 1
                    continue
                day_candidates.append({**candidate, "window": label})
            candidates_by_window[label] += len(day_candidates)
            if not day_candidates:
                continue
            best = max(day_candidates, key=lambda item: float(item["candidate_score"]))
            selected.append(best)
            selected_by_window[label] += 1
            last_selected_by_ticker[str(best["ticker"])] = day

    audit = {
        "raw_candidate_count": len(selected),
        "candidate_rows_before_daily_top1_by_window": dict(candidates_by_window),
        "selected_by_window": dict(selected_by_window),
        "peer_rejected_by_window": dict(peer_rejected_by_window),
        "growth_ticker_count": len(growth_index),
        "warehouse_frame_count": len(frames),
        "industry_group_count": len(industry_groups),
        "sector_coverage": sector_coverage,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "peer_confirmation_lookback_days": PEER_CONFIRMATION_LOOKBACK_DAYS,
        "min_peer_confirmations": MIN_PEER_CONFIRMATIONS,
    }
    return selected, audit


def _gate4(
    aggregate_comparison: dict[str, Any],
    results: list[dict[str, Any]],
    target_summary: dict[str, Any],
) -> dict[str, Any]:
    gate4 = base._gate4(aggregate_comparison, results, target_summary)
    if gate4["passed"]:
        gate4["decision"] = "positive_replay_lead_not_promoted_requires_shared_adapter"
    else:
        gate4["decision"] = (
            "rejected_broad_companyfacts_peer_confirmed_filing_drift_candidate_pool"
        )
    gate4["requires_parity_before_promotion"] = True
    gate4["production_parity_note"] = PRODUCTION_IMPACT["parity_note"]
    return gate4


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload["experiment_id"] = EXP_ID
    payload["anti_js"] = "No JavaScript was used."
    payload["preflight"] = {
        "alpha_hypothesis": (
            "Broad Companyfacts filing events with recent same-industry "
            "dual-growth confirmation can add cleaner default-off paper "
            "candidates than standalone broad dual-growth relative strength."
        ),
        "category": "entry_candidate_pool",
        "nearby_prior_experiments": [
            "exp-20260605-011",
            "exp-20260605-007",
            "exp-20260604-014",
            "exp-20260602-020",
        ],
        "single_causal_variable": CHANGED_VARIABLE,
        "success_standard": (
            "Canonical three-window before/after aggregate EV and PnL must "
            "improve, no window EV/PnL regression, max drawdown drift <= "
            f"{MAX_DRAWDOWN_WORSE}, target trades >= {MIN_TARGET_TRADES}, "
            "all three windows represented, concentration within guardrails."
        ),
        "reproducible_if_failed": True,
    }
    payload["parameters"] = {
        "paper_notional": PAPER_NOTIONAL,
        "hold_days": HOLD_DAYS,
        "max_fundamental_age_days": MAX_FUNDAMENTAL_AGE_DAYS,
        "peer_confirmation_lookback_days": PEER_CONFIRMATION_LOOKBACK_DAYS,
        "min_peer_confirmations": MIN_PEER_CONFIRMATIONS,
        "min_revenue_yoy_growth": MIN_REVENUE_YOY_GROWTH,
        "min_profit_yoy_growth": MIN_PROFIT_YOY_GROWTH,
        "min_price": MIN_PRICE,
        "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
        "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
        "min_close_location": MIN_CLOSE_LOCATION,
        "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "daily_selection": "top_1_by_fixed_peer_confirmed_growth_drift_score",
        "round_trip_cost_pct": base.ROUND_TRIP_COST_PCT,
        "trade_enabled": False,
    }
    payload["source_data"]["sector_map_path"] = base._repo_rel(
        REPO_ROOT / "data" / "reference" / "broad_market_sector_map.json"
    )
    payload["source_data"]["sector_map_rule_version"] = SECTOR_MAP_RULE_VERSION
    payload["gate4"] = _gate4(
        payload["aggregate"]["comparison"],
        payload["results"],
        payload["target_summary"],
    )
    payload["production_impact"] = PRODUCTION_IMPACT
    payload["next_retry_requires"] = [
        "treat this relationship feature as frozen until new peer/filing evidence exists",
        "if positive, promote only through a shared default-off adapter with parity tests",
        "if rejected, avoid same-industry Companyfacts peer confirmation retunes",
        "do not expand by adding noisy tickers outside liquid broad warehouse coverage",
    ]
    payload["related_files"] = [
        base._repo_rel(Path(__file__)),
        base._repo_rel(OUT_JSON),
        base._repo_rel(LOG_JSON),
        base._repo_rel(ARTIFACT_MD),
        base._repo_rel(TICKET_JSON),
        base._repo_rel(base.GROWTH_PATH),
        "data/reference/broad_market_sector_map.json",
    ]
    return payload


def _experiment_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    comparison = payload["aggregate"]["comparison"]
    actual_success = 1 if payload["gate4"]["passed"] else 0
    prediction = payload.get("prediction") or {}
    return {
        "experiment_id": EXP_ID,
        "timestamp": payload["completed_at"],
        "status": payload["gate4"]["status"],
        "lane": "alpha_search",
        "hypothesis": payload["preflight"]["alpha_hypothesis"],
        "change_summary": (
            "Tested a replay-only broad Companyfacts candidate source that "
            "requires own fresh dual growth plus recent same-industry peer "
            "dual-growth confirmation."
        ),
        "change_type": "default_off_paper_candidate_pool",
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": 0,
        "nearby_prior_experiments": [
            "exp-20260605-011",
            "exp-20260605-007",
            "exp-20260604-014",
            "exp-20260602-020",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "production_visible_companyfacts_peer_relation_field",
        "component": base._repo_rel(Path(__file__)),
        "parameters": payload["parameters"],
        "before_metrics": payload["aggregate"]["before"],
        "after_metrics": payload["aggregate"]["after"],
        "delta_metrics": comparison,
        "production_impact": PRODUCTION_IMPACT,
        "decision": payload["gate4"]["decision"],
        "rejection_reason": ";".join(payload["gate4"]["failed_reasons"])
        if payload["gate4"]["failed_reasons"]
        else None,
        "next_retry_requires": payload["next_retry_requires"],
        "related_files": payload["related_files"],
        "prediction": {
            **prediction,
            "actual_success": actual_success,
            "actual_ev_delta": comparison["expected_value_score_delta"],
            "actual_pnl_delta": comparison["strategy_total_pnl_delta"],
            "brier_score": round(
                (float(prediction.get("success_probability") or 0.0) - actual_success) ** 2,
                6,
            ),
        },
        "windows": [
            {
                "label": row["label"],
                "expected_value_before": row["before"]["expected_value_score"],
                "expected_value_after": row["after"]["expected_value_score"],
                "expected_value_delta": row["comparison"]["expected_value_score_delta"],
                "strategy_total_pnl_delta": row["comparison"]["strategy_total_pnl_delta"],
                "target_trade_count": row["target_trade_count"],
                "target_trade_pnl_usd": row["target_trade_pnl_usd"],
            }
            for row in payload["results"]
        ],
        "anti_js": "No JavaScript was used.",
    }


def _write_artifact(payload: dict[str, Any]) -> None:
    comparison = payload["aggregate"]["comparison"]
    lines = [
        f"# {EXP_ID} Broad Companyfacts Peer-Confirmed Filing Drift",
        "",
        f"- Trial family: `{TRIAL_FAMILY}`",
        f"- Changed variable: `{CHANGED_VARIABLE}`",
        f"- Decision: `{payload['gate4']['decision']}`",
        f"- Aggregate EV delta: {float(comparison['expected_value_score_delta']):+.4f}",
        f"- Aggregate PnL delta: ${float(comparison['strategy_total_pnl_delta']):+,.2f}",
        f"- Target trades: {payload['target_summary']['target_trade_count']}",
        f"- Production impact: `{PRODUCTION_IMPACT['adapter_status']}`",
        "",
        "## Hypothesis",
        "",
        payload["preflight"]["alpha_hypothesis"],
        "",
        "## Gate 1-4",
        "",
        base._window_table(payload["results"]),
        "",
        "## Candidate Audit",
        "",
        "```json",
        json.dumps(payload["candidate_audit"], indent=2, sort_keys=True),
        "```",
        "",
        "## Gate 4",
        "",
    ]
    for key, value in payload["gate4"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Production / Backtest Parity",
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "## Reproducibility",
            "",
            (
                ".\\.venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260605_014_broad_companyfacts_peer_confirmed_filing_drift.py"
            ),
            "",
            "No JavaScript was used.",
        ]
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _judge_compatible_aggregate(metrics: dict[str, Any]) -> dict[str, Any]:
    payload = dict(metrics)
    payload["total_pnl"] = metrics.get("strategy_total_pnl")
    payload["max_drawdown_pct"] = metrics.get("max_drawdown_pct_max")
    payload["survival_rate"] = metrics.get("min_survival_rate")
    payload["total_trades"] = metrics.get("trade_count")
    return payload


def main() -> None:
    _patch_base_module()
    base._generate_candidates = _generate_candidates
    payload = _postprocess_payload(base.build_payload())
    base._write_json(OUT_JSON, payload)
    base._write_json(LOG_JSON, _experiment_log_record(payload))
    base._write_json(BEFORE_JSON, _judge_compatible_aggregate(payload["aggregate"]["before"]))
    base._write_json(AFTER_JSON, _judge_compatible_aggregate(payload["aggregate"]["after"]))
    _write_artifact(payload)
    base._update_ticket(payload)
    base._update_registry(payload)
    base._append_experiment_log(_experiment_log_record(payload))
    print(
        json.dumps(
            {
                "experiment_id": EXP_ID,
                "decision": payload["gate4"]["decision"],
                "aggregate": payload["aggregate"]["comparison"],
                "target_summary": {
                    "target_trade_count": payload["target_summary"]["target_trade_count"],
                    "target_trade_pnl_usd": payload["target_summary"]["target_trade_pnl_usd"],
                    "max_single_positive_share": payload["target_summary"][
                        "max_single_positive_share"
                    ],
                    "positive_pnl_hhi": payload["target_summary"]["positive_pnl_hhi"],
                },
                "gate4_failed_reasons": payload["gate4"]["failed_reasons"],
                "anti_js": "No JavaScript was used.",
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
