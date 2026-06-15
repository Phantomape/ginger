"""exp-20260615-002: low asset-growth quality candidate pool.

Replay-only alpha search. The single decision hypothesis is a free/PIT SEC
Companyfacts capital-discipline field: production-universe names whose latest
annual 10-K total assets grew only modestly, or contracted without extreme
distress, may avoid the overinvestment / asset-growth anomaly losers. Paired
with liquid SPY-relative price confirmation, that should select higher-quality
paper candidates without adding noisy tickers.

This is not a retry of cash-conversion thresholds, quarterly accruals, diluted
share contraction, SEC deleveraging text, 13F, options, or LLM soft-ranking.
No production code, shared adapter, live/default orders, ranking, sizing, exits,
LLM/news path, or watchlist behavior is changed. A positive replay remains only
a lead until a shared daily/backtest helper reproduces it. No JavaScript is
used.
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260614_020_accruals_cash_conversion_quality as base
from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260615-002"
STEM = "low_asset_growth_quality"
TRIAL_FAMILY = "low_asset_growth_quality_candidate_pool"
TRIAL_VARIANT_ID = "companyfacts_low_asset_growth_top1_next_open_10d_v1"
CHANGED_VARIABLE = "low_asset_growth_quality_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260615_002_{STEM}.json"
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

MAX_ASSET_FACT_AGE_DAYS = 460
MIN_ASSET_GROWTH = -0.25
MAX_ASSET_GROWTH = 0.10
MIN_PRIOR_ASSETS_USD = 250_000_000.0

PREDICTION = {
    "success_probability": 0.17,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "companyfacts_family_crowded",
        "asset_growth_relabels_low_liability",
        "window_regression",
        "accepted_comparator_not_beaten",
        "drawdown_drift",
    ],
    "confidence_reason": (
        "Low asset growth is a documented free SEC fundamental anomaly and no "
        "exact prior asset-growth experiment was found; related Companyfacts "
        "quality fields are crowded, so the main risk is overlap with accepted "
        "low-liability/RS and generic momentum."
    ),
    "recorded_at": "2026-06-15T01:07:47+00:00",
}

PRODUCTION_IMPACT = {
    **base.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "execution_envelope": {
        **base.PRODUCTION_IMPACT["execution_envelope"],
        "failure_handling": (
            "missing annual 10-K current/prior assets, missing OHLCV, missing "
            "next open, or missing 10d exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same PIT "
        "annual 10-K asset-growth gate, liquid SPY-relative confirmation, "
        "cooldown, next-open paper entry, 10-day exit, costs, and concentration "
        "controls in both historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: production-universe names whose latest filed annual "
        "10-K total assets grew no more than 10%, and did not contract more "
        "than 25%, may avoid overinvestment losers while retaining capital-"
        "disciplined leaders when liquid SPY-relative confirmation is present."
    ),
    "2_history_check": {
        "exp-20260528-017": (
            "Accepted low-liability Companyfacts support; this run compares "
            "same-ticker annual total assets through time, not liability level."
        ),
        "exp-20260613-031": (
            "Rejected operating-efficiency-assets support; this run does not "
            "scale earnings by assets and instead tests annual asset growth."
        ),
        "exp-20260614-020/024/025/027": (
            "Cash-conversion, quarterly cash conversion, TTM accruals, and TTM "
            "cash-flow acceleration were rejected or drawdown-failing. This "
            "run does not retune their ratios, fact age, stops, or thresholds."
        ),
        "exp-20260614-029": (
            "Diluted share contraction was rejected. Asset growth is a distinct "
            "balance-sheet investment/overinvestment field."
        ),
        "exp-20260615-001": (
            "SEC deleveraging text was rejected. This run uses numeric PIT "
            "Companyfacts assets and no filing-language classifier."
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
        "exp_20260615_002_low_asset_growth_quality.py"
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _round(value: Any, digits: int = 6) -> float | None:
    return base._round(value, digits)


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _float_or_none(value: Any) -> float | None:
    return base._float_or_none(value)


def _annual_asset_facts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for raw in rows:
        if str(raw.get("canonical") or "") != "assets":
            continue
        form = str(raw.get("form") or "").upper()
        if not form.startswith("10-K"):
            continue
        filed = str(raw.get("filed") or "")[:10]
        end = str(raw.get("end") or "")[:10]
        value = _float_or_none(raw.get("value"))
        if not filed or not end or value is None or value <= 0.0:
            continue
        facts.append(
            {
                "filed": filed,
                "end": end,
                "value": value,
                "concept": raw.get("concept"),
                "form": raw.get("form"),
            }
        )
    facts.sort(key=lambda row: (row["filed"], row["end"], row["value"]))
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
        assets = _annual_asset_facts(rows)
        if len(assets) < 2:
            stats["tickers_missing_two_annual_asset_facts"] += 1
            continue
        index[ticker] = {"assets": assets}
        stats["tickers_with_two_annual_asset_facts"] += 1
    return index, {
        "companyfacts_rows_loaded": len(companyfacts_rows),
        "tickers_seen": len(by_ticker),
        **dict(stats),
    }


def _days_between(later: str, earlier: str) -> int:
    return base._days_between(later, earlier)


def _latest_on_or_before(facts: list[dict[str, Any]], asof: str) -> dict[str, Any] | None:
    chosen: dict[str, Any] | None = None
    for fact in facts:
        if fact["filed"] <= asof:
            chosen = fact
        else:
            break
    return chosen


def _prior_comparable_annual_fact(
    facts: list[dict[str, Any]], asof: str, current: dict[str, Any]
) -> dict[str, Any] | None:
    current_end = base.framework._parse_date(current["end"])
    candidates: list[tuple[int, int, str, dict[str, Any]]] = []
    for fact in facts:
        if fact["filed"] > asof or fact["end"] >= current["end"]:
            continue
        gap = (current_end - base.framework._parse_date(fact["end"])).days
        if 300 <= gap <= 430:
            candidates.append((abs(gap - 365), -_days_between(fact["filed"], "1900-01-01"), fact["filed"], fact))
    candidates.sort(key=lambda row: (row[0], row[1], row[2]))
    return candidates[0][3] if candidates else None


def _asset_growth_quality(
    ticker: str,
    asof: str,
    facts: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    current = _latest_on_or_before(facts["assets"], asof)
    if current is None:
        return None
    prior = _prior_comparable_annual_fact(facts["assets"], asof, current)
    if prior is None:
        return None
    if _days_between(asof, current["filed"]) > MAX_ASSET_FACT_AGE_DAYS:
        return None
    current_assets = float(current["value"])
    prior_assets = float(prior["value"])
    if prior_assets < MIN_PRIOR_ASSETS_USD or current_assets <= 0.0:
        return None
    growth = (current_assets - prior_assets) / prior_assets
    if growth < MIN_ASSET_GROWTH or growth > MAX_ASSET_GROWTH:
        return None
    return {
        "current_period_end": current["end"],
        "prior_period_end": prior["end"],
        "current_filed": current["filed"],
        "prior_filed": prior["filed"],
        "current_assets": _round(current_assets, 2),
        "prior_assets": _round(prior_assets, 2),
        "asset_growth_ratio": _round(growth, 6),
        "asset_discipline_score": _round(min(max(MAX_ASSET_GROWTH - growth, 0.0), 0.30), 6),
        "fact_age_days": _days_between(asof, current["filed"]),
        "current_form": current.get("form"),
        "current_concept": current.get("concept"),
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
            quality = _asset_growth_quality(ticker, signal_date, quality_index[ticker])
            if quality is None:
                scan["failed_asset_growth_gate"] += 1
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
            discipline = float(quality["asset_discipline_score"] or 0.0)
            score = (
                2.10 * discipline
                + 0.55 * float(confirm["candidate_ret20_excess_spy"])
                + 0.14 * float(confirm["candidate_ret60_excess_spy"])
                + 0.10 * float(confirm["candidate_close_location"])
                + 0.035
                * math.log10(max(float(confirm["candidate_avg_dollar_volume_20d"]), 1.0) / 1_000_000.0)
            )
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "LOW_ASSET_GROWTH_QUALITY_PAPER",
                    "candidate_score": _round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": "annual_10k_assets_companyfacts_filed_and_signal_close_before_next_open_paper_entry",
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
            float(row["quality_asset_growth_ratio"] or 0.0),
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
        "min_asset_growth": MIN_ASSET_GROWTH,
        "max_asset_growth": MAX_ASSET_GROWTH,
        "max_asset_fact_age_days": MAX_ASSET_FACT_AGE_DAYS,
        "min_prior_assets_usd": MIN_PRIOR_ASSETS_USD,
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
        "positive_replay_lead_not_promoted_low_asset_growth_quality"
        if gate["passed"]
        else "rejected_low_asset_growth_quality_candidate_pool"
    )
    return gate


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    decision = gate4["decision"]
    status = "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected"
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": _utc_now(),
            "status": status,
            "decision": decision,
            "accepted": False,
            "accepted_alpha": False,
            "numeric_gate4_passed": gate4["passed"],
            "hypothesis": (
                "PIT SEC Companyfacts low annual 10-K asset growth paired "
                "with liquid SPY-relative confirmation may identify capital-"
                "disciplined leaders and avoid overinvestment losers."
            ),
            "change_type": "default_off_paper_candidate_pool_replay_scout",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_sec_companyfacts_asset_growth_candidate_pool",
            "new_evidence_type": "free_sec_companyfacts_annual_asset_growth_plus_ohlcv",
            "nearby_prior_experiments": [
                "exp-20260528-017",
                "exp-20260613-031",
                "exp-20260614-020",
                "exp-20260614-024",
                "exp-20260614-025",
                "exp-20260614-027",
                "exp-20260614-029",
                "exp-20260615-001",
            ],
            "prior_trial_count": 0,
            "multiple_testing_risk_bucket": "minimal",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "pre_run_questions": PRE_RUN_QUESTIONS,
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
    payload["backtest_protocol"]["execution_model"] = (
        "Annual 10-K assets facts are known by SEC filed date (<= signal date) "
        "and compared against the prior comparable annual period. Price "
        "confirmation uses only signal-date OHLCV. Paper entry is the next "
        "available open with existing entry slippage; exit is the close 10 "
        "trading days after the signal with target-side sell slippage and "
        "ROUND_TRIP_COST_PCT."
    )
    payload["parameters"] = {
        key: value
        for key, value in payload["parameters"].items()
        if key
        not in {
            "fy_duration_min",
            "fy_duration_max",
            "max_annual_fact_age_days",
            "min_cash_conversion",
            "max_accruals_to_assets",
        }
    }
    payload["parameters"].update(
        {
            "max_asset_fact_age_days": MAX_ASSET_FACT_AGE_DAYS,
            "min_asset_growth": MIN_ASSET_GROWTH,
            "max_asset_growth": MAX_ASSET_GROWTH,
            "min_prior_assets_usd": MIN_PRIOR_ASSETS_USD,
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["gate2"]["runtime_fields"] = [
        "SEC companyfacts canonical assets (annual 10-K instant facts)",
        "SEC companyfacts filed date, period end, and form",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    if gate4["passed"]:
        interpretation = (
            "The low asset-growth source cleared the numeric three-window "
            "replay screen, but remains only a replay lead because no shared "
            "daily/backtest helper was promoted."
        )
    else:
        interpretation = (
            "The low asset-growth source did not clear Gate 4 "
            f"(failed: {', '.join(gate4['failed_reasons']) or 'none'}). Do not "
            "promote or tune this fixed asset-growth bundle on the same frozen "
            "windows."
        )
    payload["interpretation"] = interpretation
    payload["rejection_reason"] = None if gate4["passed"] else "; ".join(gate4["failed_reasons"])
    payload["next_evidence_needed"] = (
        "A retry needs materially different PIT investment discipline evidence "
        "such as asset growth relative to industry peers, capex-free-cash-flow "
        "coverage, or closed forward replacement rows. Do not sweep asset-"
        "growth thresholds, fact age, price guards, top-N, hold, cooldown, or "
        "notional on these frozen windows."
    )
    payload["post_run_reflection"] = {
        "why_result_happened": interpretation,
        "outcome_summary": (
            "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}; "
            "max drawdown drift {:+.4f}; {} paper trades.".format(
                aggregate["expected_value_score_delta_sum"],
                aggregate["total_pnl_delta_sum"],
                float(aggregate["max_drawdown_delta_max"] or 0.0),
                payload["target_trade_summary"]["total_trade_count"],
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping asset-growth thresholds, annual fact "
            "freshness, RS/close/volume/vol guards, top-N, hold days, cooldown, "
            "or notional on these frozen windows."
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
            f"# {EXPERIMENT_ID} Low Asset Growth Quality",
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
            _repo_rel(Path(__file__)): base.framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): base.framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): base.framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): base.framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): base.framework._sha256(CARD_MD),
        },
    }
    base.framework._write_json(MANIFEST_JSON, manifest)


def _install() -> None:
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
    base._build_quality_index = _build_quality_index
    base._candidate_rows_for_window = _candidate_rows_for_window
    base._gate4 = _gate4
    base._build_card = _build_card


def main() -> None:
    _install()
    payload = _postprocess_payload(base._build_payload())
    _persist(payload)
    print(json.dumps(base.framework._safe(base._build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
