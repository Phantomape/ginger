"""exp-20260617-009: sector-normalized reinvestment productivity scout.

Replay-only alpha search. The single decision hypothesis is that the raw SEC
Companyfacts CapEx/D&A reinvestment-cycle signal from exp-20260617-007 becomes
more robust when a candidate is admitted only if its revenue productivity and
CapEx/D&A improvement are above same-sector PIT peers on the signal date.

This is not a raw CapEx/D&A threshold sweep. It tests the materially different
industry-normalized productivity evidence named by the failed raw reinvestment
cycle experiment. No production code, shared adapter, live/default orders,
ranking, sizing, exits, LLM/news path, or watchlist behavior is changed. A
positive replay is only a lead until a shared historical/daily helper
reproduces it.

No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

import exp_20260617_007_capex_depreciation_reinvestment_cycle as capex


base = capex.base

EXPERIMENT_ID = "exp-20260617-009"
STEM = "sector_normalized_reinvestment_productivity"
TRIAL_FAMILY = "sector_normalized_reinvestment_productivity_candidate_pool"
TRIAL_VARIANT_ID = "sector_normalized_reinvestment_productivity_top1_next_open_10d_v1"
CHANGED_VARIABLE = "raw_sec_companyfacts_sector_normalized_reinvestment_productivity_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search"

REPO_ROOT = capex.REPO_ROOT
RAW_COMPANYFACTS_CACHE = capex.RAW_COMPANYFACTS_CACHE
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260617_009_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = capex.BASE_NOTIONAL_USD
HOLD_DAYS = capex.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = capex.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = capex.SAME_TICKER_COOLDOWN_DAYS

FY_DURATION_MIN = capex.FY_DURATION_MIN
FY_DURATION_MAX = capex.FY_DURATION_MAX
MAX_ANNUAL_FACT_AGE_DAYS = capex.MAX_ANNUAL_FACT_AGE_DAYS
EXCLUDED_SECTORS = capex.EXCLUDED_SECTORS
CAPEX_TAGS = capex.CAPEX_TAGS
DA_TAGS = capex.DA_TAGS
REVENUE_TAGS = capex.REVENUE_TAGS

MIN_SECTOR_PEERS = 3
MIN_SECTOR_PRODUCTIVITY_EDGE = 0.0
MIN_SECTOR_CAPEX_DA_IMPROVEMENT_EDGE = 0.0
PRODUCTIVITY_CAPEX_INTENSITY_FLOOR = 0.015

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.30,
    "expected_pnl_delta": 4500.0,
    "main_failure_modes": [
        "companyfacts_reinvestment_family_saturated",
        "sector_peer_sample_noisy",
        "old_thin_regression",
        "drawdown_drift",
        "accepted_distribution_comparator_not_beaten",
    ],
    "confidence_reason": (
        "exp-20260617-007 showed raw CapEx/D&A replacement-cycle evidence was "
        "directionally positive but not robust; its reflection named "
        "industry-normalized replacement-cycle productivity as materially "
        "different PIT evidence. Risk remains high because recent raw "
        "Companyfacts fields often relabel 2025 liquid momentum and fail "
        "old_thin or drawdown."
    ),
    "recorded_at": "2026-06-17T07:06:01+00:00",
}

PRODUCTION_IMPACT = {
    **capex.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "execution_envelope": {
        **capex.PRODUCTION_IMPACT["execution_envelope"],
        "failure_handling": (
            "missing raw SEC annual CapEx/D&A/revenue pair, missing prior "
            "annual comparison pair, stale facts, missing CIK mapping, "
            "excluded sector, insufficient same-sector peers, below-peer "
            "reinvestment productivity, missing OHLCV, missing next open, or "
            "missing 10d exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same raw "
        "SEC tag mapping, filed-date PIT annual CapEx/D&A observation, same-"
        "sector peer medians, revenue-productivity edge, liquid SPY-relative "
        "confirmation, cooldown, next-open paper entry, 10-day exit, costs, "
        "and concentration controls in both historical replay and daily "
        "production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: PIT SEC Companyfacts reinvestment-cycle rows may "
        "become more robust if CapEx/D&A acceleration is admitted only when "
        "revenue productivity is strong versus same-sector peers, "
        "distinguishing productive capacity expansion from generic capex-heavy "
        "momentum."
    ),
    "2_history_check": {
        "exp-20260617-007": (
            "Rejected raw CapEx/D&A reinvestment cycle despite positive "
            "aggregate EV/PnL because old_thin regressed and drawdown drift "
            "worsened. Its reflection explicitly named industry-normalized "
            "replacement-cycle productivity as valid materially different "
            "evidence."
        ),
        "exp-20260617-006": (
            "Rejected fixed-asset turnover improvement with old_thin "
            "regression; this run tests peer-normalized productivity around "
            "new reinvestment rather than raw asset-turnover improvement."
        ),
        "exp-20260615-008": (
            "Rejected FCF/CapEx coverage quality. This run intentionally does "
            "not reward low reinvestment or cash coverage; it requires "
            "productive reinvestment relative to sector peers."
        ),
        "exp-20260616-018": (
            "Rejected inventory/revenue leanness. This run uses tangible "
            "reinvestment productivity rather than working-capital leanness."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Aggregate EV/PnL "
        "must be positive, no window EV/PnL regression, at least two EV-"
        "improved windows, at least 20 paper trades across all 3 windows, "
        "survival >=5%, drawdown drift <=0.5pp, concentration pass, and "
        "accepted compression/distribution candidate-pool comparators must be "
        "beaten. Replay-only positives are leads until shared daily/backtest "
        "parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260617_009_sector_normalized_reinvestment_productivity.py"
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return base._round(value, digits)


def _as_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _percentile_rank(value: float, peers: list[float]) -> float | None:
    if not peers:
        return None
    below = sum(1 for peer in peers if peer < value)
    equal = sum(1 for peer in peers if peer == value)
    return (below + 0.5 * equal) / len(peers)


def _reinvestment_productivity(quality: dict[str, Any]) -> float:
    revenue_growth = _as_float(quality.get("revenue_growth"))
    capex_intensity = max(
        _as_float(quality.get("current_capex_to_revenue")),
        PRODUCTIVITY_CAPEX_INTENSITY_FLOOR,
    )
    return revenue_growth / capex_intensity


def _build_quality_index(
    companyfacts_rows: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, Any]]:
    index, summary = capex._build_quality_index(companyfacts_rows)
    return index, {
        **summary,
        "field_source": "raw_sec_companyfacts_cache_with_sector_peer_normalization",
        "normalization": "same_sector_signal_date_peer_median",
        "min_sector_peers_excluding_candidate": MIN_SECTOR_PEERS,
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
        observations: dict[str, dict[str, Any]] = {}
        sector_to_tickers: dict[str, list[str]] = defaultdict(list)

        for ticker in eligible:
            scan["ticker_day_evaluations"] += 1
            meta = sector_entries.get(ticker, {})
            sector = meta.get("sector")
            if not sector:
                scan["missing_sector"] += 1
                continue
            if sector in EXCLUDED_SECTORS:
                scan["excluded_sector"] += 1
                continue
            quality = capex._capex_reinvestment_observation(
                ticker,
                signal_date,
                quality_index[ticker],
            )
            if quality is None:
                scan["failed_raw_capex_reinvestment_gate"] += 1
                continue
            productivity = _reinvestment_productivity(quality)
            observations[ticker] = {
                "meta": meta,
                "sector": str(sector),
                "quality": quality,
                "productivity": productivity,
                "capex_da_improvement": _as_float(
                    quality.get("capex_to_depreciation_improvement")
                ),
            }
            sector_to_tickers[str(sector)].append(ticker)
            scan["raw_reinvestment_observations"] += 1

        for ticker, observation in observations.items():
            sector = str(observation["sector"])
            peer_tickers = [peer for peer in sector_to_tickers[sector] if peer != ticker]
            if len(peer_tickers) < MIN_SECTOR_PEERS:
                scan["failed_sector_peer_count"] += 1
                continue

            peer_productivity = [observations[peer]["productivity"] for peer in peer_tickers]
            peer_improvement = [
                observations[peer]["capex_da_improvement"] for peer in peer_tickers
            ]
            sector_productivity_median = float(median(peer_productivity))
            sector_improvement_median = float(median(peer_improvement))
            productivity = float(observation["productivity"])
            improvement = float(observation["capex_da_improvement"])
            productivity_edge = productivity - sector_productivity_median
            improvement_edge = improvement - sector_improvement_median

            if productivity_edge < MIN_SECTOR_PRODUCTIVITY_EDGE:
                scan["failed_sector_productivity_gate"] += 1
                continue
            if improvement_edge < MIN_SECTOR_CAPEX_DA_IMPROVEMENT_EDGE:
                scan["failed_sector_improvement_gate"] += 1
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

            quality = observation["quality"]
            scan["qualified_candidate_rows"] += 1
            productivity_percentile = _percentile_rank(productivity, peer_productivity)
            improvement_percentile = _percentile_rank(improvement, peer_improvement)
            score = (
                0.65 * min(productivity_edge, 4.0)
                + 0.50 * min(improvement_edge, 1.75)
                + 0.20 * min(_as_float(quality.get("revenue_growth")), 1.0)
                - 0.20
                * max(_as_float(quality.get("capex_growth_minus_revenue_growth")), 0.0)
                + 0.45 * _as_float(confirm["candidate_ret20_excess_spy"])
                + 0.12 * _as_float(confirm["candidate_ret60_excess_spy"])
                + 0.10 * _as_float(confirm["candidate_close_location"])
                + 0.035
                * math.log10(max(_as_float(confirm["candidate_avg_dollar_volume_20d"]), 1.0) / 1_000_000.0)
            )
            meta = observation["meta"]
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "RAW_SEC_SECTOR_NORMALIZED_REINVESTMENT_PRODUCTIVITY_PAPER",
                    "candidate_score": _round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": "raw_annual_companyfacts_filed_and_signal_close_before_next_open_paper_entry",
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "uses_free_sec_companyfacts": True,
                    "uses_raw_sec_companyfacts_cache": True,
                    "uses_free_ohlcv": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    "sector_peer_count": len(peer_tickers),
                    "sector_reinvestment_productivity": _round(productivity, 6),
                    "sector_reinvestment_productivity_peer_median": _round(
                        sector_productivity_median,
                        6,
                    ),
                    "sector_reinvestment_productivity_edge": _round(productivity_edge, 6),
                    "sector_reinvestment_productivity_percentile": _round(
                        productivity_percentile,
                        6,
                    ),
                    "sector_capex_to_depreciation_improvement_peer_median": _round(
                        sector_improvement_median,
                        6,
                    ),
                    "sector_capex_to_depreciation_improvement_edge": _round(
                        improvement_edge,
                        6,
                    ),
                    "sector_capex_to_depreciation_improvement_percentile": _round(
                        improvement_percentile,
                        6,
                    ),
                    **{f"reinvestment_{key}": value for key, value in quality.items()},
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
            -float(row["sector_reinvestment_productivity_edge"] or 0.0),
            -float(row["sector_capex_to_depreciation_improvement_edge"] or 0.0),
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
        "raw_reinvestment_rule_version": capex.RULE_VERSION,
        "productivity_formula": "annual_revenue_growth/current_capex_to_revenue",
        "productivity_capex_intensity_floor": PRODUCTIVITY_CAPEX_INTENSITY_FLOOR,
        "min_sector_peers_excluding_candidate": MIN_SECTOR_PEERS,
        "min_sector_productivity_edge": MIN_SECTOR_PRODUCTIVITY_EDGE,
        "min_sector_capex_to_depreciation_improvement_edge": (
            MIN_SECTOR_CAPEX_DA_IMPROVEMENT_EDGE
        ),
        "max_annual_fact_age_days": MAX_ANNUAL_FACT_AGE_DAYS,
        "excluded_sectors": list(EXCLUDED_SECTORS),
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
        "positive_replay_lead_not_promoted_sector_normalized_reinvestment_productivity"
        if gate["passed"]
        else "rejected_sector_normalized_reinvestment_productivity_candidate_pool"
    )
    return gate


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
    base.MAX_ANNUAL_FACT_AGE_DAYS = MAX_ANNUAL_FACT_AGE_DAYS
    base.PREDICTION = PREDICTION
    base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    base.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    base.load_companyfacts_rows = capex._load_companyfacts_rows_stub
    base._build_quality_index = _build_quality_index
    base._candidate_rows_for_window = _candidate_rows_for_window
    base._gate4 = _gate4


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    status = "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected"
    if gate4["passed"]:
        interpretation = (
            "The sector-normalized reinvestment productivity source cleared "
            "the numeric three-window replay screen, but remains only a replay "
            "lead because no shared daily/backtest helper was promoted."
        )
    else:
        interpretation = (
            "The sector-normalized reinvestment productivity source did not "
            f"clear Gate 4 (failed: {', '.join(gate4['failed_reasons']) or 'none'}). "
            "It is not retained or promoted."
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
                "production_visible_free_sec_companyfacts_reinvestment_cycle_candidate_pool"
            ),
            "new_evidence_type": "industry_normalized_reinvestment_productivity_field",
            "nearby_prior_experiments": [
                "exp-20260617-007",
                "exp-20260617-006",
                "exp-20260615-008",
                "exp-20260616-018",
            ],
            "prior_trial_count": 1,
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
        key: value
        for key, value in payload["parameters"].items()
        if key not in {"min_cash_conversion", "max_accruals_to_assets", "max_annual_fact_age_days"}
    }
    payload["parameters"].update(
        {
            "raw_reinvestment_rule_version": capex.RULE_VERSION,
            "max_annual_fact_age_days": MAX_ANNUAL_FACT_AGE_DAYS,
            "productivity_formula": "annual_revenue_growth/current_capex_to_revenue",
            "productivity_capex_intensity_floor": PRODUCTIVITY_CAPEX_INTENSITY_FLOOR,
            "min_sector_peers_excluding_candidate": MIN_SECTOR_PEERS,
            "min_sector_productivity_edge": MIN_SECTOR_PRODUCTIVITY_EDGE,
            "min_sector_capex_to_depreciation_improvement_edge": (
                MIN_SECTOR_CAPEX_DA_IMPROVEMENT_EDGE
            ),
            "excluded_sectors": list(EXCLUDED_SECTORS),
            "capex_tags": list(CAPEX_TAGS),
            "depreciation_tags": list(DA_TAGS),
            "revenue_tags": list(REVENUE_TAGS),
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Annual CapEx, depreciation/amortization, and revenue are read from "
        "raw SEC Companyfacts tags and are known only by filed date (<= signal "
        "date). Current and prior annual CapEx are matched to same-period D&A "
        "and revenue by fiscal-year end. The experiment first forms the raw "
        "reinvestment-cycle observation, then admits a candidate only when its "
        "revenue growth per CapEx intensity and CapEx/D&A improvement are both "
        "at least same-sector peer medians on the signal date. Price "
        "confirmation uses only signal-date OHLCV. Paper entry is the next "
        "available open with existing entry slippage; exit is the close 10 "
        "trading days after the signal with target-side sell slippage and "
        "ROUND_TRIP_COST_PCT."
    )
    payload["backtest_protocol"]["companyfacts_source"] = _repo_rel(RAW_COMPANYFACTS_CACHE)
    payload["backtest_protocol"]["sector_normalization"] = (
        "same-sector peer medians excluding the candidate; minimum three peers"
    )
    payload["gate2"]["runtime_fields"] = [
        "raw SEC companyfacts annual CapEx facts",
        "raw SEC companyfacts annual depreciation/amortization facts",
        "raw SEC companyfacts annual revenue facts",
        "raw SEC companyfacts filed date and period end",
        "warehouse ticker_universe CIK mapping",
        "warehouse sector metadata for peer medians",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "If rejected, a retry needs materially different PIT reinvestment "
        "evidence such as segment/customer capacity disclosures or closed "
        "forward replacement-value rows. Do not sweep peer-count, percentile, "
        "productivity formula, raw CapEx/D&A thresholds, sector exclusions, "
        "RS/close/volume guards, top-N, hold, cooldown, or notional on these "
        "frozen windows."
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
            "Do not retry by sweeping peer-count, percentile, productivity "
            "formula, raw CapEx/D&A threshold values, tag lists, sector "
            "exclusions, annual fact freshness, RS/close/volume/vol guards, "
            "top-N, hold days, cooldown, or notional on these frozen windows."
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
            f"# {EXPERIMENT_ID} Sector-Normalized Reinvestment Productivity",
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
