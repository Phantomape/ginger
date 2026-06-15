"""exp-20260615-010: sector-relative gross profitability quality scout.

Replay-only alpha search. The single decision hypothesis is a PIT free SEC
Companyfacts candidate source: production-universe names with high annual gross
profitability versus same-sector peers, paired with liquid SPY-relative price
confirmation, may identify durable quality leaders better than operating-income
/ assets, cash-conversion, asset-growth, or dilution variants.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. A positive replay is
only a lead until a shared historical/daily helper reproduces it. No JavaScript
is used.
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260614_020_accruals_cash_conversion_quality as base


EXPERIMENT_ID = "exp-20260615-010"
STEM = "gross_profitability_quality"
TRIAL_FAMILY = "gross_profitability_quality_candidate_pool"
TRIAL_VARIANT_ID = "sector_relative_gross_profitability_top1_next_open_10d_v1"
CHANGED_VARIABLE = "gross_profitability_quality_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260615_010_{STEM}.json"
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
MAX_ANNUAL_FACT_AGE_DAYS = 430
MIN_PEER_GROUP_SIZE = 3
MIN_SECTOR_GROSS_PROFITABILITY_PERCENTILE = 0.65
MIN_GROSS_MARGIN = 0.20
MIN_GROSS_PROFIT_TO_ASSETS = 0.05

PREDICTION = {
    "success_probability": 0.17,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "gross_margin_near_neighbor",
        "window_regression",
        "drawdown_drift",
        "accepted_comparator_not_beaten",
        "concentration_failed",
    ],
    "confidence_reason": (
        "Gross profitability is a distinct free SEC Companyfacts quality field "
        "from cash conversion, asset growth, and operating-income/assets; prior "
        "cash-quality results show quality plus RS can be predictive, but "
        "gross-margin and Companyfacts families are crowded and comparator/"
        "drawdown failure is likely."
    ),
    "recorded_at": "2026-06-15T09:08:13+00:00",
}

PRODUCTION_IMPACT = {
    **base.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "execution_envelope": {
        **base.PRODUCTION_IMPACT["execution_envelope"],
        "failure_handling": (
            "missing annual gross_profit/revenue, missing assets, missing "
            "same-sector peer group, missing OHLCV, missing next open, or "
            "missing 10d exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same PIT "
        "annual sector-relative gross-profitability quality gate, liquid "
        "SPY-relative confirmation, cooldown, next-open paper entry, 10-day "
        "exit, costs, and concentration controls in both historical replay and "
        "daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: PIT SEC Companyfacts annual gross profit over assets, "
        "ranked within same-sector peers and paired with liquid SPY-relative "
        "confirmation, may select durable quality leadership rather than broad "
        "cash-conversion or asset-growth momentum."
    ),
    "2_history_check": {
        "exp-20260528-012": (
            "Rejected gross-margin expansion due concentration. This run is "
            "not a gross-margin expansion support scalar; it ranks gross "
            "profitability over assets cross-sectionally versus sector peers "
            "as a standalone default-off candidate source."
        ),
        "exp-20260613-031/exp-20260614-014": (
            "Operating-income/assets and Kova capital efficiency failed "
            "accepted Companyfacts comparators. Gross profitability is a "
            "pre-expense quality field and does not sweep operating-income/"
            "assets thresholds."
        ),
        "exp-20260614-020/025/027": (
            "Annual accruals, TTM accruals, and TTM cash-flow acceleration "
            "were rejected or drawdown-failing. This run does not retune "
            "cash-conversion, fact freshness, deployment, stops, or exits."
        ),
        "exp-20260615-002/003/006/008": (
            "Low asset growth, cash-backed low asset growth, industry-relative "
            "asset growth, and FCF/capex coverage failed window or drawdown "
            "gates. This run uses gross-profitability peer rank, not asset "
            "growth or capex/cash-flow coverage."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Aggregate EV/PnL "
        "must be positive, no window EV/PnL regression, at least two "
        "EV-improved windows, at least 20 paper trades across all 3 windows, "
        "survival >=5%, drawdown drift <=0.5pp, concentration pass, and the "
        "accepted compression and distribution candidate-pool comparators must "
        "be beaten. Replay-only positives are leads until shared daily/"
        "backtest parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260615_010_gross_profitability_quality.py"
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return base._round(value, digits)


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
        gross_profit = base._annual_facts(rows, "gross_profit")
        revenue = base._annual_facts(rows, "revenue")
        assets = base._instant_facts(rows, "assets")
        if not gross_profit or not revenue or not assets:
            stats["tickers_missing_required_facts"] += 1
            continue
        index[ticker] = {
            "gross_profit": gross_profit,
            "revenue": revenue,
            "assets": assets,
        }
        stats["tickers_with_gross_profitability_facts"] += 1
    return index, {
        "companyfacts_rows_loaded": len(companyfacts_rows),
        "tickers_seen": len(by_ticker),
        **dict(stats),
    }


def _gross_profitability_observation(
    ticker: str,
    asof: str,
    facts: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    gross_profit = base._latest_on_or_before(facts["gross_profit"], asof)
    if gross_profit is None:
        return None
    revenue = base._matched_on_or_before(facts["revenue"], asof, gross_profit["end"])
    if revenue is None:
        return None
    assets = base._latest_on_or_before(facts["assets"], asof)
    if assets is None or assets["value"] <= 0.0:
        return None
    if base._days_between(asof, gross_profit["filed"]) > MAX_ANNUAL_FACT_AGE_DAYS:
        return None

    gross_profit_value = float(gross_profit["value"])
    revenue_value = float(revenue["value"])
    asset_value = float(assets["value"])
    if gross_profit_value <= 0.0 or revenue_value <= 0.0 or asset_value <= 0.0:
        return None
    gross_margin = gross_profit_value / revenue_value
    gross_profit_to_assets = gross_profit_value / asset_value
    if gross_margin < MIN_GROSS_MARGIN:
        return None
    if gross_profit_to_assets < MIN_GROSS_PROFIT_TO_ASSETS:
        return None
    return {
        "fiscal_year_end": gross_profit["end"],
        "gross_profit_filed": gross_profit["filed"],
        "revenue_filed": revenue["filed"],
        "assets_filed": assets["filed"],
        "gross_profit": _round(gross_profit_value, 2),
        "revenue": _round(revenue_value, 2),
        "total_assets": _round(asset_value, 2),
        "gross_margin": _round(gross_margin, 6),
        "gross_profit_to_assets": _round(gross_profit_to_assets, 6),
        "fact_age_days": base._days_between(asof, gross_profit["filed"]),
    }


def _peer_bucket(ticker: str, sector_entries: dict[str, dict[str, Any]]) -> str | None:
    sector = str((sector_entries.get(ticker, {}) or {}).get("sector") or "").strip()
    return sector or None


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
        by_peer: dict[str, list[tuple[str, float]]] = defaultdict(list)
        for ticker in eligible:
            scan["ticker_day_evaluations"] += 1
            peer_bucket = _peer_bucket(ticker, sector_entries)
            if not peer_bucket:
                scan["missing_sector_peer_bucket"] += 1
                continue
            quality = _gross_profitability_observation(ticker, signal_date, quality_index[ticker])
            if quality is None:
                scan["failed_gross_profitability_observation"] += 1
                continue
            gp_assets = float(quality["gross_profit_to_assets"] or 0.0)
            observations[ticker] = quality
            by_peer[peer_bucket].append((ticker, gp_assets))

        peer_stats: dict[str, dict[str, Any]] = {}
        for peer_bucket, members in by_peer.items():
            if len(members) < MIN_PEER_GROUP_SIZE:
                scan["peer_groups_too_small"] += 1
                continue
            sorted_values = sorted(value for _, value in members)
            count = len(sorted_values)
            median = (
                sorted_values[count // 2]
                if count % 2
                else (sorted_values[(count // 2) - 1] + sorted_values[count // 2]) / 2.0
            )
            peer_stats[peer_bucket] = {
                "count": count,
                "mean": sum(sorted_values) / count,
                "median": median,
                "sorted_values": sorted_values,
            }

        for ticker, quality in observations.items():
            peer_bucket = _peer_bucket(ticker, sector_entries)
            if not peer_bucket or peer_bucket not in peer_stats:
                scan["failed_peer_group_gate"] += 1
                continue
            stats = peer_stats[peer_bucket]
            gp_assets = float(quality["gross_profit_to_assets"] or 0.0)
            rank_count = sum(1 for value in stats["sorted_values"] if value <= gp_assets)
            percentile = rank_count / float(stats["count"])
            if percentile < MIN_SECTOR_GROSS_PROFITABILITY_PERCENTILE:
                scan["failed_sector_relative_gross_profitability_gate"] += 1
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
                0.85 * percentile
                + 1.10 * min(gp_assets, 1.0)
                + 0.35 * float(quality["gross_margin"] or 0.0)
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
                    "source": "GROSS_PROFITABILITY_QUALITY_PAPER",
                    "candidate_score": _round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": "annual_companyfacts_filed_sector_peer_rank_and_signal_close_before_next_open_paper_entry",
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "uses_free_sec_companyfacts": True,
                    "uses_free_ohlcv": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    **{f"quality_{key}": value for key, value in quality.items()},
                    "quality_peer_bucket": peer_bucket,
                    "quality_peer_group_count": stats["count"],
                    "quality_peer_gross_profitability_mean": _round(stats["mean"], 6),
                    "quality_peer_gross_profitability_median": _round(stats["median"], 6),
                    "quality_gross_profitability_percentile": _round(percentile, 6),
                    "quality_peer_relative_gross_profitability": _round(
                        gp_assets - float(stats["median"]), 6
                    ),
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
            -float(row["quality_gross_profitability_percentile"] or 0.0),
            -float(row["quality_gross_profit_to_assets"] or 0.0),
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
        "max_annual_fact_age_days": MAX_ANNUAL_FACT_AGE_DAYS,
        "min_peer_group_size": MIN_PEER_GROUP_SIZE,
        "min_sector_gross_profitability_percentile": MIN_SECTOR_GROSS_PROFITABILITY_PERCENTILE,
        "min_gross_margin": MIN_GROSS_MARGIN,
        "min_gross_profit_to_assets": MIN_GROSS_PROFIT_TO_ASSETS,
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
        "positive_replay_lead_not_promoted_gross_profitability_quality"
        if gate["passed"]
        else "rejected_gross_profitability_quality_candidate_pool"
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
    base._build_quality_index = _build_quality_index
    base._candidate_rows_for_window = _candidate_rows_for_window
    base._gate4 = _gate4


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    status = "observed_only_positive_replay_lead" if gate4["passed"] else "rejected"
    if gate4["passed"]:
        interpretation = (
            "The sector-relative gross-profitability quality source cleared the "
            "numeric three-window replay screen, but remains only a replay lead "
            "because no shared daily/backtest helper was promoted."
        )
    else:
        interpretation = (
            "The sector-relative gross-profitability quality source did not "
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
            "hypothesis": (
                "PIT SEC Companyfacts annual gross profit over assets, ranked "
                "within same-sector peers and paired with liquid SPY-relative "
                "confirmation, may identify durable quality leaders better than "
                "operating-income/assets or cash-conversion variants."
            ),
            "change_type": "default_off_paper_candidate_pool_replay_scout",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_sec_companyfacts_gross_profitability_candidate_pool",
            "new_evidence_type": "free_sec_companyfacts_sector_relative_gross_profitability_plus_ohlcv",
            "nearby_prior_experiments": [
                "exp-20260528-012",
                "exp-20260613-031",
                "exp-20260614-014",
                "exp-20260614-020",
                "exp-20260614-025",
                "exp-20260615-002",
                "exp-20260615-003",
                "exp-20260615-006",
                "exp-20260615-008",
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
        key: value
        for key, value in payload["parameters"].items()
        if key
        not in {
            "min_cash_conversion",
            "max_accruals_to_assets",
            "max_annual_fact_age_days",
        }
    }
    payload["parameters"].update(
        {
            "max_annual_fact_age_days": MAX_ANNUAL_FACT_AGE_DAYS,
            "min_peer_group_size": MIN_PEER_GROUP_SIZE,
            "min_sector_gross_profitability_percentile": MIN_SECTOR_GROSS_PROFITABILITY_PERCENTILE,
            "min_gross_margin": MIN_GROSS_MARGIN,
            "min_gross_profit_to_assets": MIN_GROSS_PROFIT_TO_ASSETS,
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Annual gross_profit and revenue are known by SEC filed date "
        "(<= signal date) and matched on the same fiscal-year period end; total "
        "assets uses the latest filed value. Same-sector peer percentiles are "
        "computed at the signal date from only PIT-available observations. "
        "Price confirmation uses only signal-date OHLCV. Paper entry is the "
        "next available open with existing entry slippage; exit is the close "
        "10 trading days after the signal with target-side sell slippage and "
        "ROUND_TRIP_COST_PCT."
    )
    payload["gate2"]["runtime_fields"] = [
        "SEC companyfacts canonical gross_profit (annual)",
        "SEC companyfacts canonical revenue (annual)",
        "SEC companyfacts canonical assets",
        "SEC companyfacts filed date and period end",
        "sector_entries sector peer bucket",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "A retry needs materially different PIT gross-profitability evidence "
        "or closed forward replacement rows. Do not sweep gross-margin, "
        "gross-profit/assets, sector-percentile, fact freshness, RS/close/"
        "volume/vol guards, top-N, hold, cooldown, or notional on these frozen "
        "windows."
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
            "Do not retry by sweeping gross-margin, gross-profit/assets, "
            "sector-percentile, annual fact freshness, RS/close/volume/vol "
            "guards, top-N, hold days, cooldown, or notional on these frozen "
            "windows."
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
            f"# {EXPERIMENT_ID} Gross Profitability Quality",
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
