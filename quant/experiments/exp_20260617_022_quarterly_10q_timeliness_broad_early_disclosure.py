"""exp-20260617-022: quarterly 10-Q filing-timeliness candidate scout.

Replay-only alpha search. The single decision hypothesis is a materially new
disclosure-timing field allowed by exp-20260617-020's closeout: companies whose
latest quarterly 10-Q is filed abnormally early versus their own historical
same-fiscal-quarter filing-lag norm may drift up over the next 10 trading days.

This is not an annual 10-K early-filing threshold or universe retry. It uses
only Q1/Q2/Q3 10-Q facts with true quarter-duration revenue periods, compares
each filing only to prior filings for the same fiscal quarter, and keeps the
same replay-only next-open 10-day paper envelope used by the annual scout.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. A positive result is
only a replay lead until a shared historical/daily helper reproduces it.
No JavaScript is used.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260617_020_filing_timeliness_broad_early_disclosure as annual


EXPERIMENT_ID = "exp-20260617-022"
STEM = "quarterly_10q_timeliness_broad_early_disclosure"
TRIAL_FAMILY = "free_sec_companyfacts_quarterly_timeliness_broad_candidate_pool"
TRIAL_VARIANT_ID = "broad_quarterly_10q_early_filing_vs_same_quarter_norm_top1_next_open_10d_v1"
CHANGED_VARIABLE = "sec_quarterly_10q_timeliness_broad_early_disclosure_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-explore-automation"

REPO_ROOT = annual.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260617_022_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = annual.BASE_NOTIONAL_USD
HOLD_DAYS = annual.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = annual.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = annual.SAME_TICKER_COOLDOWN_DAYS

QUARTER_FORMS = {"10-Q", "10-Q/A", "10-QT"}
QUARTER_FPS = {"Q1", "Q2", "Q3"}
QUARTER_DURATION_MIN = 65
QUARTER_DURATION_MAX = 105
MIN_FILING_LAG_DAYS = 5
MAX_FILING_LAG_DAYS = 120
MIN_PRIOR_SAME_QUARTER_FILINGS = 2
MIN_EARLINESS_DAYS = 4.0
MAX_CURRENT_LAG_DAYS = 55

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "broad_universe_adds_noise",
        "old_thin_window_regression",
        "quarterly_lag_field_noisy",
        "accepted_distribution_comparator_not_beaten",
    ],
    "confidence_reason": (
        "exp-20260617-020 closed the annual 10-K breadth caveat and explicitly "
        "allowed a materially different quarterly 10-Q timeliness field. "
        "Quarterly filing promptness is PIT/free and event-timed, but shorter "
        "filing-lag variance may be noisy and broad-event breadth can regress "
        "old_thin or fail accepted distribution comparator."
    ),
    "recorded_at": "2026-06-17T17:54:47+00:00",
}

PRODUCTION_IMPACT = {
    **annual.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "execution_envelope": {
        **annual.PRODUCTION_IMPACT["execution_envelope"],
        "failure_handling": (
            "missing raw SEC quarterly 10-Q filing history, fewer than 2 prior "
            "same-quarter filings, missing CIK mapping, missing OHLCV, missing "
            "next open, or missing 10d exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same PIT "
        "quarterly 10-Q filed-lag history, abnormally-early-vs-same-quarter-own-"
        "norm gate, light liquidity gate, cooldown, next-open paper entry, "
        "10-day exit, costs, and concentration controls in both historical replay "
        "and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: broad liquid-universe companies whose latest quarterly "
        "10-Q is filed abnormally early versus the same company's own same-"
        "fiscal-quarter filing-lag norm may drift up over the next 10 trading "
        "days, because prompt interim disclosure proxies clean books / "
        "management confidence and is a materially different disclosure-timing "
        "field from rejected annual 10-K early filing."
    ),
    "2_history_check": {
        "exp-20260617-020": (
            "Rejected broad annual 10-K early filing. Its closeout forbids "
            "annual 10-K threshold/scope retries but explicitly allows quarterly "
            "10-Q timeliness as a materially different disclosure-timing field."
        ),
        "exp-20260617-019": (
            "Rejected underpowered core annual 10-K early filing. This run is "
            "not the sanctioned broad annual retry; exp020 already closed that."
        ),
        "exp-20260528-016": (
            "Accepted filing recency support inside fundamental_growth_rs. This "
            "run tests promptness versus own same-quarter history, not freshness."
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
        "exp_20260617_022_quarterly_10q_timeliness_broad_early_disclosure.py"
    ),
}

_ORIGINAL_CANDIDATE_ROWS = annual._candidate_rows_for_window


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return annual._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return annual._round(value, digits)


def _quarterly_filing_lags(usgaap: dict[str, Any]) -> list[dict[str, Any]]:
    """Distinct Q1/Q2/Q3 10-Q filings sorted by filed date.

    SEC Companyfacts frequently carries both YTD and true-quarter revenue facts
    in the same 10-Q. The duration filter keeps the true interim quarter rather
    than cumulative YTD rows.
    """
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for tag in annual.REVENUE_TAGS:
        for arr in usgaap.get(tag, {}).get("units", {}).values():
            if not isinstance(arr, list):
                continue
            for raw in arr:
                fp = str(raw.get("fp") or "").upper()
                if fp not in QUARTER_FPS:
                    continue
                if str(raw.get("form") or "").upper() not in QUARTER_FORMS:
                    continue
                end = annual._d10(raw.get("end"))
                filed = annual._d10(raw.get("filed"))
                start = annual._d10(raw.get("start"))
                if not end or not filed or not start:
                    continue
                dur = (date.fromisoformat(end) - date.fromisoformat(start)).days
                if not (QUARTER_DURATION_MIN <= dur <= QUARTER_DURATION_MAX):
                    continue
                lag = (date.fromisoformat(filed) - date.fromisoformat(end)).days
                if not (MIN_FILING_LAG_DAYS <= lag <= MAX_FILING_LAG_DAYS):
                    continue
                key = (fp, end)
                prev = by_key.get(key)
                if prev is None or filed < prev["filed"]:
                    by_key[key] = {
                        "end": end,
                        "filed": filed,
                        "lag": lag,
                        "fiscal_quarter": fp,
                        "fy": raw.get("fy"),
                    }
    filings = list(by_key.values())
    filings.sort(key=lambda r: (r["filed"], r["end"], r["fiscal_quarter"]))
    return filings


def _early_filing_events(filings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for i, filing in enumerate(filings):
        fp = filing["fiscal_quarter"]
        prior = [
            f
            for f in filings[:i]
            if f["fiscal_quarter"] == fp and f["filed"] < filing["filed"]
        ]
        if len(prior) < MIN_PRIOR_SAME_QUARTER_FILINGS:
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
                "fiscal_quarter_end": filing["end"],
                "fiscal_quarter": fp,
                "fiscal_year": filing.get("fy"),
                "current_lag_days": current_lag,
                "trailing_avg_lag_days": _round(trailing_avg, 4),
                "earliness_days": _round(earliness, 4),
                "prior_filing_count": len(prior),
            }
        )
    return events


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    sector_entries: dict[str, dict[str, Any]],
    quality_index: dict[str, dict[str, list[dict[str, Any]]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows, scan = _ORIGINAL_CANDIDATE_ROWS(
        snapshot=snapshot,
        cfg=cfg,
        sector_entries=sector_entries,
        quality_index=quality_index,
    )
    for row in rows:
        row["source"] = "SEC_QUARTERLY_10Q_TIMELINESS_EARLY_DISCLOSURE_PAPER"
        row["known_at"] = "quarterly_10q_filed_date_and_signal_close_before_next_open_paper_entry"
        row["rule_version"] = RULE_VERSION
        row["source_rule_version"] = RULE_VERSION
    scan = {
        **scan,
        "rule_version": RULE_VERSION,
        "quarter_forms": sorted(QUARTER_FORMS),
        "quarter_fps": sorted(QUARTER_FPS),
        "quarter_duration_min": QUARTER_DURATION_MIN,
        "quarter_duration_max": QUARTER_DURATION_MAX,
        "min_prior_same_quarter_filings": MIN_PRIOR_SAME_QUARTER_FILINGS,
    }
    return rows, scan


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = annual.base.framework._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = list(gate.get("failed_reasons") or [])
    ev_delta = float(aggregate["expected_value_score_delta_sum"] or 0.0)
    pnl_delta = float(aggregate["total_pnl_delta_sum"] or 0.0)
    if ev_delta <= annual.base.COMPRESSION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_compression_ev_not_beaten")
    if pnl_delta <= annual.base.COMPRESSION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_compression_pnl_not_beaten")
    if ev_delta <= annual.base.DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_distribution_ev_not_beaten")
    if pnl_delta <= annual.base.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_distribution_pnl_not_beaten")
    gate["failed_reasons"] = failed
    gate["accepted_compression_comparator"] = annual.base.COMPRESSION_COMPARATOR
    gate["accepted_distribution_comparator"] = annual.base.DISTRIBUTION_COMPARATOR
    gate["passed"] = not failed
    gate["decision"] = (
        "positive_replay_lead_not_promoted_quarterly_10q_timeliness_early_disclosure"
        if gate["passed"]
        else "rejected_quarterly_10q_timeliness_early_disclosure_candidate_pool"
    )
    return gate


def _configure_scaffold() -> None:
    annual.EXPERIMENT_ID = EXPERIMENT_ID
    annual.STEM = STEM
    annual.TRIAL_FAMILY = TRIAL_FAMILY
    annual.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    annual.CHANGED_VARIABLE = CHANGED_VARIABLE
    annual.RULE_VERSION = RULE_VERSION
    annual.OWNER = OWNER
    annual.OUT_DIR = OUT_DIR
    annual.OUT_JSON = OUT_JSON
    annual.LOG_JSON = LOG_JSON
    annual.TICKET_JSON = TICKET_JSON
    annual.CARD_MD = CARD_MD
    annual.MANIFEST_JSON = MANIFEST_JSON
    annual.EXPERIMENT_LOG = EXPERIMENT_LOG
    annual.REGISTRY_JSON = REGISTRY_JSON
    annual.FY_DURATION_MIN = QUARTER_DURATION_MIN
    annual.FY_DURATION_MAX = QUARTER_DURATION_MAX
    annual.MIN_FILING_LAG_DAYS = MIN_FILING_LAG_DAYS
    annual.MAX_FILING_LAG_DAYS = MAX_FILING_LAG_DAYS
    annual.MIN_PRIOR_ANNUAL_FILINGS = MIN_PRIOR_SAME_QUARTER_FILINGS
    annual.MIN_EARLINESS_DAYS = MIN_EARLINESS_DAYS
    annual.MAX_CURRENT_LAG_DAYS = MAX_CURRENT_LAG_DAYS
    annual.PREDICTION = PREDICTION
    annual.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    annual.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    annual._RAW_INDEX_CACHE = None
    annual._annual_filing_lags = _quarterly_filing_lags
    annual._early_filing_events = _early_filing_events
    annual._candidate_rows_for_window = _candidate_rows_for_window
    annual._gate4 = _gate4
    annual._configure_base()


def _interpretation(payload: dict[str, Any]) -> str:
    gate4 = payload["gate4"]
    if gate4["passed"]:
        return (
            "The broad liquid-universe quarterly 10-Q filing-timeliness source "
            "cleared the numeric three-window replay screen, but remains only a "
            "replay lead because no shared daily/backtest helper was promoted."
        )
    return (
        "The broad liquid-universe quarterly 10-Q filing-timeliness source did "
        f"not clear Gate 4 (failed: {', '.join(gate4['failed_reasons']) or 'none'}). "
        "This tests a materially different disclosure-timing field from the "
        "rejected annual 10-K early-filing bundle: true quarter-duration Q1/Q2/Q3 "
        "10-Q rows are compared only against the same company's prior same-fiscal-"
        "quarter filing-lag norm. The result is not retained or promoted."
    )


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload = annual._postprocess_payload(payload)
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    status = "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected"
    interpretation = _interpretation(payload)
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
            "mechanism_family": "production_visible_free_sec_companyfacts_filing_timeliness_candidate_pool",
            "new_evidence_type": "sec_quarterly_10q_filing_timeliness_vs_same_quarter_norm_pit_event",
            "nearby_prior_experiments": ["exp-20260617-020", "exp-20260617-019", "exp-20260528-016"],
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
        "quarter_forms": sorted(QUARTER_FORMS),
        "quarter_fps": sorted(QUARTER_FPS),
        "quarter_duration_min": QUARTER_DURATION_MIN,
        "quarter_duration_max": QUARTER_DURATION_MAX,
        "min_filing_lag_days": MIN_FILING_LAG_DAYS,
        "max_filing_lag_days": MAX_FILING_LAG_DAYS,
        "min_prior_same_quarter_filings": MIN_PRIOR_SAME_QUARTER_FILINGS,
        "min_earliness_days": MIN_EARLINESS_DAYS,
        "max_current_lag_days": MAX_CURRENT_LAG_DAYS,
        "min_price": annual.MIN_PRICE,
        "min_avg_dollar_volume_20d": annual.MIN_AVG_DOLLAR_VOLUME_20D,
        "revenue_tags": list(annual.REVENUE_TAGS),
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"]["execution_model"] = (
        "Quarterly 10-Q filings are read from raw SEC Companyfacts revenue facts "
        "(forms 10-Q/10-Q/A/10-QT, fp Q1/Q2/Q3, true quarter-duration periods) "
        "and known only by filed date. For each company with at least two prior "
        "filings for the same fiscal quarter, the current filed-minus-quarter-end "
        "lag is compared to that same-quarter trailing average; an event fires "
        "when the current filing is at least 4 days earlier than the company's "
        "own same-quarter norm and current lag is <=55 days. The signal date is "
        "the first trading day on/after the filed date. Only a light liquidity "
        "gate (price >= $10, ADV20 >= $50M) is applied; no SPY-relative momentum "
        "filter. Paper entry is the next available open with entry slippage; exit "
        "is the close 10 trading days after the signal with target-side sell "
        "slippage and ROUND_TRIP_COST_PCT."
    )
    payload["backtest_protocol"]["companyfacts_source"] = _repo_rel(annual.RAW_COMPANYFACTS_CACHE)
    payload["gate2"]["runtime_fields"] = [
        "raw SEC companyfacts quarterly 10-Q revenue facts (form/fp/start/end/filed)",
        "derived same-fiscal-quarter filing-lag history per company",
        "warehouse ticker_universe CIK mapping",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV (descriptive only, not a filter)",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "If this fixed quarterly 10-Q bundle fails, do not retry by sweeping "
        "earliness-days, current-lag cap, prior same-quarter count, event age, "
        "price/ADV liquidity floors, quarter-duration bounds, top-N, hold days, "
        "cooldown, or notional. A valid retry needs a materially different "
        "disclosure-timing field such as accelerated-filer-status change, NT 10-K/"
        "10-Q late-filing notices, segment/customer disclosure timing, or closed "
        "forward replacement-value rows."
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
            "Do not retry by sweeping quarterly earliness-days, current-lag cap, "
            "prior same-quarter count, event age, price/ADV liquidity floors, "
            "quarter-duration bounds, top-N, hold days, cooldown, or notional on "
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
    for label in annual.base.framework.WINDOWS:
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
            f"# {EXPERIMENT_ID} Quarterly 10-Q Filing Timeliness",
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
            _repo_rel(Path(__file__)): annual.base.framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): annual.base.framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): annual.base.framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): annual.base.framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): annual.base.framework._sha256(CARD_MD),
        },
    }
    annual.base.framework._write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any]) -> None:
    log_record = annual.base._build_log_record(payload)
    annual.base.framework._write_json(OUT_JSON, payload)
    annual.base.framework._write_json(LOG_JSON, payload)
    annual.base.framework._write_text(CARD_MD, _build_card(payload))
    annual.base.framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
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
    annual.base.persist_self_registered_result(
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
    _configure_scaffold()
    payload = _postprocess_payload(annual.base._build_payload())
    _persist(payload)
    print(json.dumps(annual.base.framework._safe(annual.base._build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
