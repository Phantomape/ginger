"""exp-20260614-025: TTM same-period accruals quality candidate pool.

Replay-only alpha search. The single decision hypothesis is a sharper PIT
Companyfacts earnings-quality field for the rejected annual cash-conversion
lead: build TTM net income and operating cash flow as latest annual plus
current YTD minus prior-year comparable YTD, then admit only cash-backed
earnings momentum (TTM OCF / NI >= 1 and TTM accruals/assets <= 0).

This is not a sweep of annual cash-conversion thresholds, deployment, stop,
hold, cooldown, or notional. It changes the accounting construction itself to
the playbook-approved TTM same-period accruals field. No production code,
shared adapter, live/default orders, ranking, sizing, exits, LLM/news path, or
watchlist behavior is changed. A positive replay remains only a lead until a
shared daily/backtest helper reproduces it.
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


EXPERIMENT_ID = "exp-20260614-025"
STEM = "ttm_same_period_accruals_quality"
TRIAL_FAMILY = "ttm_same_period_accruals_quality_candidate_pool"
TRIAL_VARIANT_ID = "companyfacts_ttm_same_period_accruals_top1_next_open_10d_v1"
CHANGED_VARIABLE = "ttm_same_period_accruals_quality_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260614_025_{STEM}.json"
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

FY_DURATION_MIN = 340
FY_DURATION_MAX = 380
YTD_DURATION_MIN = 120
YTD_DURATION_MAX = 320
MAX_TTM_FACT_AGE_DAYS = 220
MIN_TTM_CASH_CONVERSION = 1.00
MAX_TTM_ACCRUALS_TO_ASSETS = 0.00

PREDICTION = {
    "success_probability": 0.24,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "thin_ttm_sample",
        "annual_cash_conversion_overlap",
        "window_regression",
        "accepted_comparator_not_beaten",
        "concentration_failed",
    ],
    "confidence_reason": (
        "Annual accruals cash-conversion was all-window positive but "
        "overdeployed; quarterly improvement was too thin and concentrated. "
        "True PIT TTM same-period accruals is the playbook-approved different "
        "information field, using annual plus current YTD minus prior-year YTD "
        "facts rather than threshold, deployment, stop, hold, or notional "
        "retuning."
    ),
    "recorded_at": "2026-06-14T20:06:02+00:00",
}

PRODUCTION_IMPACT = {
    **base.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "execution_envelope": {
        **base.PRODUCTION_IMPACT["execution_envelope"],
        "failure_handling": (
            "missing annual net_income/operating_cash_flow, missing current or "
            "prior-year comparable YTD facts, missing assets, missing OHLCV, "
            "missing next open, or missing 10d exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same PIT "
        "TTM same-period accruals gate, liquid SPY-relative confirmation, "
        "cooldown, next-open paper entry, 10-day exit, costs, and concentration "
        "controls in both historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: production-universe names whose TTM operating cash "
        "flow covers TTM net income, constructed PIT from annual plus current "
        "YTD minus prior-year YTD Companyfacts, should be a sharper and less "
        "tail-heavy version of the annual cash-conversion lead."
    ),
    "2_history_check": {
        "exp-20260614-020": (
            "Annual accruals / cash-conversion was positive in all three "
            "windows but rejected because full deployment worsened drawdown by "
            "+5.22pp."
        ),
        "exp-20260614-021": (
            "Max-active-one deployment kept the annual field fixed and still "
            "failed old_thin/drawdown, so this run does not retune deployment."
        ),
        "exp-20260614-023": (
            "A daily-close 7% protective stop kept the annual field fixed and "
            "failed Gate 4, so this run does not retune stops or exits."
        ),
        "exp-20260614-024": (
            "Latest-quarter cash-conversion improvement was too thin and "
            "concentrated; this run uses TTM annual-plus-YTD same-period "
            "accruals rather than a quarter-only improvement gate."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Aggregate EV/PnL "
        "must be positive, no window EV/PnL regression, at least two "
        "EV-improved windows, at least 20 paper trades across all 3 windows, "
        "survival >=5%, drawdown drift <=0.5pp, concentration pass, and the "
        "accepted compression and distribution candidate-pool comparators must "
        "be beaten. Replay-only positives are leads until shared "
        "daily/backtest parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260614_025_ttm_same_period_accruals_quality.py"
    ),
}

_ORIGINAL_CANDIDATE_ROWS_FOR_WINDOW = base._candidate_rows_for_window


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _float_or_none(value: Any) -> float | None:
    return base._float_or_none(value)


def _annual_facts(rows: list[dict[str, Any]], canonical: str) -> list[dict[str, Any]]:
    return base._annual_facts(rows, canonical)


def _instant_facts(rows: list[dict[str, Any]], canonical: str) -> list[dict[str, Any]]:
    return base._instant_facts(rows, canonical)


def _ytd_facts(rows: list[dict[str, Any]], canonical: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for raw in rows:
        if str(raw.get("canonical") or "") != canonical:
            continue
        dur = raw.get("duration_days")
        try:
            dur_i = int(dur) if dur is not None else None
        except (TypeError, ValueError):
            dur_i = None
        if dur_i is None or not (YTD_DURATION_MIN <= dur_i <= YTD_DURATION_MAX):
            continue
        filed = str(raw.get("filed") or "")[:10]
        end = str(raw.get("end") or "")[:10]
        value = _float_or_none(raw.get("value"))
        if not filed or not end or value is None:
            continue
        facts.append({"filed": filed, "end": end, "value": value, "duration_days": dur_i})
    facts.sort(key=lambda r: (r["filed"], r["end"], r["duration_days"]))
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
        annual_ni = _annual_facts(rows, "net_income")
        annual_ocf = _annual_facts(rows, "operating_cash_flow")
        ytd_ni = _ytd_facts(rows, "net_income")
        ytd_ocf = _ytd_facts(rows, "operating_cash_flow")
        assets = _instant_facts(rows, "assets")
        if not annual_ni or not annual_ocf or not ytd_ni or not ytd_ocf or not assets:
            stats["tickers_missing_required_facts"] += 1
            continue
        index[ticker] = {
            "annual_net_income": annual_ni,
            "annual_operating_cash_flow": annual_ocf,
            "ytd_net_income": ytd_ni,
            "ytd_operating_cash_flow": ytd_ocf,
            "assets": assets,
        }
        stats["tickers_with_ttm_same_period_facts"] += 1
    return index, {
        "companyfacts_rows_loaded": len(companyfacts_rows),
        "tickers_seen": len(by_ticker),
        **dict(stats),
    }


def _days_between(later: str, earlier: str) -> int:
    return base._days_between(later, earlier)


def _latest_on_or_before(facts: list[dict[str, Any]], asof: str) -> dict[str, Any] | None:
    return base._latest_on_or_before(facts, asof)


def _matched_on_or_before(
    facts: list[dict[str, Any]], asof: str, end: str
) -> dict[str, Any] | None:
    return base._matched_on_or_before(facts, asof, end)


def _latest_annual_before_ytd(
    facts: list[dict[str, Any]], asof: str, ytd_end: str
) -> dict[str, Any] | None:
    chosen: dict[str, Any] | None = None
    for fact in facts:
        if fact["filed"] <= asof and fact["end"] < ytd_end:
            chosen = fact
    return chosen


def _prior_comparable_ytd(
    facts: list[dict[str, Any]], asof: str, current: dict[str, Any]
) -> dict[str, Any] | None:
    current_end = base.framework._parse_date(current["end"])
    candidates: list[tuple[int, int, str, dict[str, Any]]] = []
    for fact in facts:
        if fact["filed"] > asof or fact["end"] >= current["end"]:
            continue
        gap = (current_end - base.framework._parse_date(fact["end"])).days
        dur_gap = abs(int(fact["duration_days"]) - int(current["duration_days"]))
        if 250 <= gap <= 450 and dur_gap <= 20:
            candidates.append((dur_gap, abs(gap - 365), fact["filed"], fact))
    candidates.sort(key=lambda row: (row[0], row[1], row[2]))
    return candidates[0][3] if candidates else None


def _ttm_same_period_accruals_quality(
    ticker: str,
    asof: str,
    facts: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    current_ni = _latest_on_or_before(facts["ytd_net_income"], asof)
    if current_ni is None:
        return None
    current_ocf = _matched_on_or_before(
        facts["ytd_operating_cash_flow"], asof, current_ni["end"]
    )
    if current_ocf is None:
        return None
    prior_ni = _prior_comparable_ytd(facts["ytd_net_income"], asof, current_ni)
    if prior_ni is None:
        return None
    prior_ocf = _matched_on_or_before(
        facts["ytd_operating_cash_flow"], asof, prior_ni["end"]
    )
    if prior_ocf is None:
        return None
    annual_ni = _latest_annual_before_ytd(facts["annual_net_income"], asof, current_ni["end"])
    if annual_ni is None:
        return None
    annual_ocf = _matched_on_or_before(
        facts["annual_operating_cash_flow"], asof, annual_ni["end"]
    )
    if annual_ocf is None:
        return None
    assets = _latest_on_or_before(facts["assets"], asof)
    if assets is None or assets["value"] <= 0.0:
        return None
    if _days_between(asof, current_ni["filed"]) > MAX_TTM_FACT_AGE_DAYS:
        return None

    ttm_ni = annual_ni["value"] + current_ni["value"] - prior_ni["value"]
    ttm_ocf = annual_ocf["value"] + current_ocf["value"] - prior_ocf["value"]
    if ttm_ni <= 0.0 or ttm_ocf <= 0.0:
        return None
    accruals_to_assets = (ttm_ni - ttm_ocf) / assets["value"]
    cash_conversion = ttm_ocf / ttm_ni
    if cash_conversion < MIN_TTM_CASH_CONVERSION:
        return None
    if accruals_to_assets > MAX_TTM_ACCRUALS_TO_ASSETS:
        return None

    current_ytd_conversion = (
        current_ocf["value"] / current_ni["value"] if current_ni["value"] > 0 else None
    )
    prior_ytd_conversion = (
        prior_ocf["value"] / prior_ni["value"] if prior_ni["value"] > 0 else None
    )
    return {
        "fiscal_year_end": annual_ni["end"],
        "current_ytd_end": current_ni["end"],
        "prior_ytd_end": prior_ni["end"],
        "net_income_filed": current_ni["filed"],
        "operating_cash_flow_filed": current_ocf["filed"],
        "annual_net_income_filed": annual_ni["filed"],
        "annual_operating_cash_flow_filed": annual_ocf["filed"],
        "prior_net_income_filed": prior_ni["filed"],
        "prior_operating_cash_flow_filed": prior_ocf["filed"],
        "assets_filed": assets["filed"],
        "net_income": base._round(ttm_ni, 2),
        "operating_cash_flow": base._round(ttm_ocf, 2),
        "annual_net_income": base._round(annual_ni["value"], 2),
        "annual_operating_cash_flow": base._round(annual_ocf["value"], 2),
        "current_ytd_net_income": base._round(current_ni["value"], 2),
        "current_ytd_operating_cash_flow": base._round(current_ocf["value"], 2),
        "prior_ytd_net_income": base._round(prior_ni["value"], 2),
        "prior_ytd_operating_cash_flow": base._round(prior_ocf["value"], 2),
        "current_ytd_duration_days": current_ni["duration_days"],
        "prior_ytd_duration_days": prior_ni["duration_days"],
        "total_assets": base._round(assets["value"], 2),
        "accruals_to_assets": base._round(accruals_to_assets, 6),
        "cash_conversion_ratio": base._round(cash_conversion, 6),
        "current_ytd_cash_conversion_ratio": base._round(current_ytd_conversion, 6),
        "prior_ytd_cash_conversion_ratio": base._round(prior_ytd_conversion, 6),
        "fact_age_days": _days_between(asof, current_ni["filed"]),
    }


def _candidate_rows_for_window(**kwargs: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows, scan = _ORIGINAL_CANDIDATE_ROWS_FOR_WINDOW(**kwargs)
    for row in rows:
        row["source"] = "TTM_SAME_PERIOD_ACCRUALS_QUALITY_PAPER"
        row["known_at"] = (
            "annual_plus_ytd_companyfacts_filed_and_signal_close_before_next_open_paper_entry"
        )
    return rows, {
        **scan,
        "rule_version": RULE_VERSION,
        "min_ttm_cash_conversion": MIN_TTM_CASH_CONVERSION,
        "max_ttm_accruals_to_assets": MAX_TTM_ACCRUALS_TO_ASSETS,
        "max_ttm_fact_age_days": MAX_TTM_FACT_AGE_DAYS,
    }


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    drawdown_only_failure = gate4["failed_reasons"] == ["drawdown_drift_too_high"]
    decision = (
        "positive_replay_lead_not_promoted_ttm_same_period_accruals_quality"
        if gate4["passed"]
        else "rejected_ttm_same_period_accruals_quality_candidate_pool"
    )
    status = (
        "observed_only_positive_replay_lead" if gate4["passed"] else "rejected"
    )
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
                "PIT TTM same-period accruals quality, built from annual plus "
                "latest YTD Companyfacts cash-flow and net-income facts, may "
                "sharpen the rejected annual cash-conversion lead by selecting "
                "cash-backed earnings momentum with less drawdown."
            ),
            "change_type": "default_off_paper_candidate_pool_replay_scout",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_sec_companyfacts_quality_candidate_pool",
            "new_evidence_type": "free_sec_companyfacts_ttm_same_period_accruals_plus_ohlcv",
            "nearby_prior_experiments": [
                "exp-20260614-020",
                "exp-20260614-021",
                "exp-20260614-023",
                "exp-20260614-024",
            ],
            "prior_trial_count": 0,
            "multiple_testing_risk_bucket": "minimal",
            "prediction": PREDICTION,
            "calibration": {
                "predicted_success_probability": PREDICTION["success_probability"],
                "actual_gate4_passed": gate4["passed"],
                "actual_success": 1 if gate4["passed"] else 0,
                "failure_modes_observed": gate4["failed_reasons"],
                "brier_score": round(
                    (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0))
                    ** 2,
                    6,
                ),
                "expected_ev_delta": PREDICTION["expected_ev_delta"],
                "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
                "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
                "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
            },
            "production_impact": PRODUCTION_IMPACT,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "anti_js": "No JavaScript was used.",
        }
    )
    gate4["decision"] = decision
    payload["backtest_protocol"]["execution_model"] = (
        "TTM net_income and operating_cash_flow are constructed point-in-time "
        "as latest annual fact plus current YTD fact minus prior-year "
        "comparable YTD fact, all known by SEC filed date (<= signal date). "
        "Total assets uses the latest filed value. Price confirmation uses "
        "only signal-date OHLCV. Paper entry is the next available open with "
        "existing entry slippage; exit is the close 10 trading days after the "
        "signal with target-side sell slippage and ROUND_TRIP_COST_PCT."
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
            "fy_duration_min": FY_DURATION_MIN,
            "fy_duration_max": FY_DURATION_MAX,
            "ytd_duration_min": YTD_DURATION_MIN,
            "ytd_duration_max": YTD_DURATION_MAX,
            "max_ttm_fact_age_days": MAX_TTM_FACT_AGE_DAYS,
            "min_ttm_cash_conversion": MIN_TTM_CASH_CONVERSION,
            "max_ttm_accruals_to_assets": MAX_TTM_ACCRUALS_TO_ASSETS,
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["gate2"]["runtime_fields"] = [
        "SEC companyfacts canonical net_income (annual and YTD)",
        "SEC companyfacts canonical operating_cash_flow (annual and YTD)",
        "SEC companyfacts canonical assets",
        "SEC companyfacts filed date, period end, and duration_days",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    if gate4["passed"]:
        interpretation = (
            "The TTM same-period accruals quality source cleared the numeric "
            "three-window replay screen, but remains only a replay lead because "
            "no shared daily/backtest helper was promoted."
        )
    elif drawdown_only_failure:
        interpretation = (
            "The TTM same-period accruals quality source was directionally "
            "positive but still failed on drawdown drift. The field may improve "
            "earnings-quality timing, but the historical 10-day next-open paper "
            "envelope still carries unacceptable tail exposure."
        )
    else:
        interpretation = (
            "The TTM same-period accruals quality source did not clear Gate 4 "
            f"(failed: {', '.join(gate4['failed_reasons']) or 'none'}). Do not "
            "promote or tune this fixed TTM construction on the same windows."
        )
    payload["interpretation"] = interpretation
    payload["rejection_reason"] = None if gate4["passed"] else "; ".join(gate4["failed_reasons"])
    payload["next_evidence_needed"] = (
        "A retry needs closed forward replacement-value rows or a materially "
        "different free data context such as borrow fee, lendable-share "
        "availability, ownership crowding/underownership, or options outcomes. "
        "Do not sweep TTM duration windows, cash-conversion cutoffs, accruals "
        "thresholds, price guards, top-N, hold, cooldown, or notional on the "
        "same frozen windows."
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
            "Do not retry by sweeping TTM YTD duration ranges, cash-conversion "
            "threshold, accruals/assets threshold, fact freshness, RS/close/"
            "volume/vol guards, top-N, hold days, cooldown, or notional on "
            "these frozen windows."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
    }
    payload["related_files"] = [
        base._repo_rel(Path(__file__)),
        base._repo_rel(OUT_JSON),
        base._repo_rel(LOG_JSON),
        base._repo_rel(TICKET_JSON),
        base._repo_rel(CARD_MD),
        base._repo_rel(MANIFEST_JSON),
        base._repo_rel(EXPERIMENT_LOG),
        base._repo_rel(REGISTRY_JSON),
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
            f"# {EXPERIMENT_ID} TTM Same-Period Accruals Quality",
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
        "artifact": base._repo_rel(OUT_JSON),
        "log": base._repo_rel(LOG_JSON),
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
        "artifact": base._repo_rel(OUT_JSON),
        "log": base._repo_rel(LOG_JSON),
        "ticket_file": base._repo_rel(TICKET_JSON),
        "card_file": base._repo_rel(CARD_MD),
        "revision_manifest_file": base._repo_rel(MANIFEST_JSON),
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
            base._repo_rel(Path(__file__)),
            base._repo_rel(OUT_JSON),
            base._repo_rel(CARD_MD),
            base._repo_rel(MANIFEST_JSON),
            base._repo_rel(TICKET_JSON),
            base._repo_rel(LOG_JSON),
            base._repo_rel(EXPERIMENT_LOG),
            base._repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            base._repo_rel(Path(__file__)): base.framework._sha256(Path(__file__)),
            base._repo_rel(OUT_JSON): base.framework._sha256(OUT_JSON),
            base._repo_rel(LOG_JSON): base.framework._sha256(LOG_JSON),
            base._repo_rel(TICKET_JSON): base.framework._sha256(TICKET_JSON),
            base._repo_rel(CARD_MD): base.framework._sha256(CARD_MD),
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
    base.FY_DURATION_MIN = FY_DURATION_MIN
    base.FY_DURATION_MAX = FY_DURATION_MAX
    base.MAX_ANNUAL_FACT_AGE_DAYS = MAX_TTM_FACT_AGE_DAYS
    base.MIN_CASH_CONVERSION = MIN_TTM_CASH_CONVERSION
    base.MAX_ACCRUALS_TO_ASSETS = MAX_TTM_ACCRUALS_TO_ASSETS
    base.PREDICTION = PREDICTION
    base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    base.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    base._build_quality_index = _build_quality_index
    base._accruals_quality = _ttm_same_period_accruals_quality
    base._candidate_rows_for_window = _candidate_rows_for_window
    base._build_card = _build_card


def main() -> None:
    _install()
    payload = _postprocess_payload(base._build_payload())
    _persist(payload)
    print(json.dumps(base.framework._safe(base._build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
