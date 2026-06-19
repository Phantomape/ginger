"""exp-20260619-008: parsed 13D/A stake-decrease absorption scout.

Replay-only alpha search. The single decision hypothesis is that parsed
Schedule 13D/A amendments where the same issuer-holder beneficial ownership
percentage *falls* versus the prior PIT parsed 13D row can become bullish only
when signal-day price action absorbs the visible holder reduction versus SPY.

This is not the exp-20260618-017 stake-increase accumulation test, not a raw
13D metadata retry, and not a stake-percent / holder-type / top-N / hold /
notional sweep. No production code, shared adapter, live/default orders,
ranking, sizing, exits, LLM/news path, or watchlist behavior is changed. A
positive result is only a replay lead until a shared historical/daily helper
reproduces it. No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260618_017_parsed_13d_stake_increase_absorption as base

if str(base.REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(base.REPO_ROOT))

from quant import sec_13d13g_ingest as ingest  # noqa: E402


EXPERIMENT_ID = "exp-20260619-008"
STEM = "parsed_13d_stake_decrease_absorption"
TRIAL_FAMILY = "parsed_13d_amend_stake_decrease_absorption_candidate_pool"
TRIAL_VARIANT_ID = "parsed_13d_stake_decrease_absorption_top1_next_open_10d_v1"
CHANGED_VARIABLE = "parsed_13d_amend_stake_decrease_absorption_candidate_pool_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260619_008_{STEM}.json"
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

MIN_PRICE = base.MIN_PRICE
MIN_AVG_DOLLAR_VOLUME_20D = base.MIN_AVG_DOLLAR_VOLUME_20D
MIN_SIGNAL_RETURN = base.MIN_SIGNAL_RETURN
MIN_SIGNAL_EXCESS_SPY = base.MIN_SIGNAL_EXCESS_SPY
MIN_CLOSE_LOCATION = base.MIN_CLOSE_LOCATION
MIN_VOLUME_RATIO_20D = base.MIN_VOLUME_RATIO_20D
MAX_REALIZED_VOL_20D = base.MAX_REALIZED_VOL_20D
MIN_RET20_EXCESS_SPY = base.MIN_RET20_EXCESS_SPY
MAX_EVENT_AGE_TRADING_DAYS = base.MAX_EVENT_AGE_TRADING_DAYS

PREDICTION = {
    "success_probability": 0.14,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "thin_sample",
        "old_thin_coverage_gap",
        "stake_decrease_is_bearish_overhang_not_relief",
        "accepted_comparator_not_beaten",
        "drawdown_drift",
    ],
    "confidence_reason": (
        "Prior raw 13D metadata and positive 13D/A stake-increase tests failed, "
        "but they did not test the opposite directional mechanism: visible "
        "large-holder supply reduction that is already absorbed by price. The "
        "evidence axis is sequential parsed stake-decrease direction from "
        "primary_doc XML plus same-day absorption, not stake threshold, "
        "holder-type, or raw metadata retuning."
    ),
    "recorded_at": "2026-06-19T09:05:04+00:00",
}

PRODUCTION_IMPACT = {
    **base.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "uses_free_sec_companyfacts": False,
    "uses_free_sec_submissions": True,
    "uses_parsed_sec_13d13g": True,
    "uses_free_ohlcv": True,
    "execution_envelope": {
        **base.PRODUCTION_IMPACT["execution_envelope"],
        "liquidity_source": "price >= $10 and ADV20 >= $50M from PIT OHLCV",
        "failure_handling": (
            "missing parsed 13D rows, missing prior same issuer-holder parsed "
            "row, non-negative stake change, missing OHLCV, missing next open, "
            "or missing 10d exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same PIT "
        "parsed 13D/A stake-decrease direction, acceptance-time signal date, "
        "price-absorption gate, cooldown, next-open paper entry, 10-day exit, "
        "costs, and concentration controls in both historical replay and daily "
        "production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: parsed 13D/A amendments where the same issuer-holder "
        "stake percentage decreases versus the prior PIT parsed 13D row may "
        "identify large-holder overhang relief when the signal-day tape absorbs "
        "the visible reduction versus SPY. Same-day liquid price absorption "
        "then tests whether demand accepted the disclosed supply before "
        "next-open paper entry."
    ),
    "2_history_check": {
        "exp-20260612-015": (
            "Rejected direct SC 13D activist-initiation metadata. This run uses "
            "parsed sequential holder stake direction, not metadata forms."
        ),
        "exp-20260618-016": (
            "Observed parsed 13D/13G static subsets. No static holder/stake "
            "subset was clean; it required direction or richer provenance."
        ),
        "exp-20260618-017": (
            "Rejected parsed 13D/A stake increases. This run tests the opposite "
            "economic sign: stake decrease plus price absorption as overhang "
            "relief, not accumulation."
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
        ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260619_008_parsed_13d_stake_decrease_absorption.py"
    ),
}

_ORIG_CANDIDATE_ROWS_FOR_WINDOW = base._candidate_rows_for_window
_ORIG_GATE4 = base._gate4
_EVENT_INDEX_CACHE: tuple[dict[str, list[dict[str, Any]]], dict[str, Any]] | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _load_13d_stake_decrease_events() -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    events = ingest.iter_ownership_filings(families=("13D",), include_amendments=True)
    parsed = ingest.build_parsed_rows(events, fetch=False, refresh=False)
    rows = parsed["rows"]
    rows.sort(
        key=lambda row: (
            str(row.get("ticker") or ""),
            base._holder_key(row),
            str(row.get("filing_date") or ""),
            str(row.get("accepted_at") or ""),
            str(row.get("accession_number") or ""),
        )
    )

    previous_by_holder: dict[tuple[str, str], dict[str, Any]] = {}
    index: dict[str, list[dict[str, Any]]] = {}
    stats: Counter[str] = Counter()
    stats["enumerated_13d_events"] = len(events)
    stats["parsed_13d_rows"] = len(rows)
    stats.update({f"fetch_status_{key}": value for key, value in parsed["fetch_status"].items()})

    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        holder = base._holder_key(row)
        key = (ticker, holder)
        current_pct = row.get("max_class_percent")
        prior = previous_by_holder.get(key)
        if row.get("is_amendment"):
            stats["parsed_13d_amendment_rows"] += 1
        else:
            stats["parsed_13d_initial_rows"] += 1
        if (
            row.get("is_amendment")
            and ticker
            and current_pct is not None
            and prior
            and prior.get("max_class_percent") is not None
        ):
            delta = float(current_pct) - float(prior["max_class_percent"])
            if delta < 0.0:
                event = {
                    "ticker": ticker,
                    "form": row.get("form"),
                    "family": row.get("family"),
                    "filing_date": row.get("filing_date"),
                    "accepted_after_close": base.runner._acceptance_after_close(row.get("accepted_at")),
                    "acceptance_datetime": row.get("accepted_at"),
                    "accession_number": row.get("accession_number"),
                    "amendment_no": row.get("amendment_no"),
                    "holder_key": holder,
                    "current_class_percent": base._round(current_pct, 4),
                    "prior_class_percent": base._round(prior.get("max_class_percent"), 4),
                    "stake_delta_pct_points": base._round(delta, 4),
                    "stake_delta_abs_pct_points": base._round(abs(delta), 4),
                    "current_aggregate_shares": row.get("reporting_persons", [{}])[0].get(
                        "aggregate_shares"
                    )
                    if row.get("reporting_persons")
                    else None,
                    "prior_accession_number": prior.get("accession_number"),
                    "prior_filing_date": prior.get("filing_date"),
                    "prior_amendment_no": prior.get("amendment_no"),
                    "reporting_person_types": row.get("reporting_person_types") or [],
                    "n_reporting_persons": row.get("n_reporting_persons"),
                    "is_big3": bool(row.get("is_big3")),
                    "issuer_cik": row.get("issuer_cik"),
                    "issuer_name": row.get("issuer_name"),
                    "issuer_cusip": row.get("issuer_cusip"),
                    "source_row_window": row.get("window"),
                }
                index.setdefault(ticker, []).append(event)
                stats["negative_stake_change_events"] += 1
                stats[f"negative_stake_change_{row.get('window')}"] += 1
            elif delta > 0.0:
                stats["positive_stake_change_events"] += 1
            else:
                stats["flat_stake_change_events"] += 1
        if current_pct is not None:
            previous_by_holder[key] = row

    for ticker in index:
        index[ticker].sort(
            key=lambda event: (
                str(event.get("filing_date") or ""),
                str(event.get("acceptance_datetime") or ""),
                str(event.get("accession_number") or ""),
            )
        )
    stats["tickers_with_negative_stake_changes"] = len(index)
    stats["candidate_event_count"] = sum(len(rows_) for rows_ in index.values())
    summary = {
        "parsed_surface": "quant/sec_13d13g_ingest.py build_parsed_rows(fetch=False)",
        "xml_cache": _repo_rel(ingest.XML_CACHE_DIR),
        "candidate_universe_scope": "broad_liquid_warehouse_all_windows_full_liquid",
        "direction_rule": (
            "current parsed 13D/A max_class_percent < prior same issuer-holder "
            "parsed 13D max_class_percent"
        ),
        "no_js": True,
        **dict(stats),
    }
    return index, summary


def _load_event_index() -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    global _EVENT_INDEX_CACHE
    if _EVENT_INDEX_CACHE is None:
        _EVENT_INDEX_CACHE = _load_13d_stake_decrease_events()
    return _EVENT_INDEX_CACHE


def _build_quality_index(
    companyfacts_rows: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    index, summary = _load_event_index()
    return index, {
        **summary,
        "selected_companyfacts_rows_ignored": len(companyfacts_rows),
        "field_source": "parsed_sec_13d13g_holder_stake_decrease_direction_not_companyfacts",
    }


def _candidate_rows_for_window(**kwargs: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows, scan = _ORIG_CANDIDATE_ROWS_FOR_WINDOW(**kwargs)
    for row in rows:
        row["source"] = "SEC_13D_AMEND_STAKE_DECREASE_ABSORPTION_PAPER"
        row["known_at"] = "parsed_13d_stake_decrease_and_signal_close_before_next_open_paper_entry"
        row["sec_13d_direction"] = "decrease"
        row["sec_13d_stake_delta_abs_pct_points"] = abs(
            float(row.get("sec_13d_stake_delta_pct_points") or 0.0)
        )

    for key in list(scan):
        if key.startswith("positive_stake_change"):
            scan[key.replace("positive_stake_change", "negative_stake_change")] = scan.pop(key)
    scan["direction_rule"] = (
        "current parsed 13D/A max_class_percent < prior same issuer-holder "
        "parsed 13D max_class_percent"
    )
    return rows, scan


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = _ORIG_GATE4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    gate["decision"] = (
        "positive_replay_lead_not_promoted_parsed_13d_stake_decrease_absorption"
        if gate["passed"]
        else "rejected_parsed_13d_stake_decrease_absorption_candidate_pool"
    )
    return gate


def _interpretation(payload: dict[str, Any]) -> str:
    gate4 = payload["gate4"]
    if gate4["passed"]:
        return (
            "The parsed 13D/A stake-decrease absorption source cleared the "
            "numeric three-window replay screen, but remains only a replay lead "
            "because no shared daily/backtest helper was promoted."
        )
    return (
        "The parsed 13D/A stake-decrease absorption source did not clear "
        f"Gate 4 (failed: {', '.join(gate4['failed_reasons']) or 'none'}). "
        "The fixed bundle tested only negative sequential stake-change direction "
        "plus signal-day SPY-relative price absorption. The result is not "
        "retained or promoted."
    )


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
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
            "single_causal_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_sec_ownership_holder_stake_candidate_pool",
            "new_evidence_type": "parsed_sequential_13d_amend_stake_decrease_direction",
            "nearby_prior_experiments": [
                "exp-20260612-015",
                "exp-20260618-016",
                "exp-20260618-017",
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
        "predicted_failure_modes": PREDICTION["main_failure_modes"],
        "predicted_failure_mode_hit": bool(
            set(PREDICTION["main_failure_modes"]) & set(gate4["failed_reasons"])
        ),
    }
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "direction_rule": (
            "current parsed 13D/A max_class_percent < prior same issuer-holder "
            "parsed 13D max_class_percent"
        ),
        "no_static_class_percent_threshold": True,
        "no_holder_type_filter": True,
        "min_price": MIN_PRICE,
        "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
        "min_signal_return": MIN_SIGNAL_RETURN,
        "min_signal_excess_spy": MIN_SIGNAL_EXCESS_SPY,
        "min_close_location": MIN_CLOSE_LOCATION,
        "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
        "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
        "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
        "max_event_age_trading_days": MAX_EVENT_AGE_TRADING_DAYS,
        "candidate_universe": "broad_liquid_warehouse_all_windows_full_liquid",
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"]["execution_model"] = (
        "Parsed Schedule 13D/A amendments are read from the local EDGAR "
        "primary_doc.xml cache through quant/sec_13d13g_ingest.py. A row is "
        "eligible only when its current max_class_percent is lower than the "
        "prior same issuer-holder parsed 13D row known earlier in filing/"
        "acceptance order. The signal date is the filing date unless the SEC "
        "acceptance timestamp is after 16:00, in which case it is the next "
        "trading day. Candidates must show signal-day price absorption before "
        "next-open paper entry: non-negative daily return, return minus SPY >= "
        "0.5%, close location >= 0.56, volume ratio >= 0.75, realized vol <= "
        "12%, ret20 excess vs SPY >= -5%, price >= $10, and ADV20 >= $50M. "
        "Paper entry is the next available open with entry slippage; exit is "
        "the close 10 trading days after the signal with target-side sell "
        "slippage and ROUND_TRIP_COST_PCT."
    )
    payload["backtest_protocol"]["parsed_surface"] = "quant/sec_13d13g_ingest.py"
    payload["gate2"]["runtime_fields"] = [
        "parsed 13D/13D-A accession number",
        "parsed 13D/13D-A filing date",
        "parsed 13D/13D-A acceptanceDateTime",
        "parsed reporting-person names",
        "parsed max_class_percent",
        "prior same issuer-holder parsed max_class_percent",
        "warehouse ticker_universe CIK mapping",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for price absorption",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "If this fixed stake-decrease absorption source fails, do not retry by "
        "sweeping stake-delta thresholds, classPercent thresholds, holder type, "
        "Big-3 exclusions, signal excess, close-location, volume, volatility, "
        "ret20, price/ADV, event-age, top-N, hold days, cooldown, or notional "
        "on these frozen windows. A valid retry needs 13D Item 4 purpose text "
        "showing a true exit/overhang-resolution catalyst, 13G/A stake-change "
        "direction coverage, repaired old_thin structured XML coverage, or "
        "closed forward replacement-value rows."
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
        "negative_reflection": (
            "A negative result means parsed 13D/A ownership reductions are still "
            "too stale, issuer-control-heavy, or economically bearish even when "
            "the same-day tape initially absorbs the filing. The field may be "
            "useful as ownership-overhang context, but it is not sufficient "
            "entry timing evidence."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping stake-delta thresholds, classPercent "
            "thresholds, holder type, Big-3 exclusions, signal excess, "
            "close-location, volume, volatility, ret20, price/ADV, event-age, "
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Events | Raw | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.runner.base.framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {events} | {raw} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                events=scan.get("negative_stake_change_events_in_window", 0),
                raw=scan.get("deduped_candidate_rows", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Parsed 13D/A Stake-Decrease Absorption",
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
            "- Aggregate PnL delta: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
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
            _repo_rel(Path(__file__)): base.runner.base.framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): base.runner.base.framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): base.runner.base.framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): base.runner.base.framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): base.runner.base.framework._sha256(CARD_MD),
        },
    }
    base.runner.base.framework._write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any]) -> None:
    log_record = base.runner.base._build_log_record(payload)
    base.runner.base.framework._write_json(OUT_JSON, payload)
    base.runner.base.framework._write_json(LOG_JSON, payload)
    base.runner.base.framework._write_text(CARD_MD, _build_card(payload))
    base.runner.base.framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
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
    base.runner.base.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )
    _write_manifest(payload)


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
    base.MIN_PRICE = MIN_PRICE
    base.MIN_AVG_DOLLAR_VOLUME_20D = MIN_AVG_DOLLAR_VOLUME_20D
    base.MIN_SIGNAL_RETURN = MIN_SIGNAL_RETURN
    base.MIN_SIGNAL_EXCESS_SPY = MIN_SIGNAL_EXCESS_SPY
    base.MIN_CLOSE_LOCATION = MIN_CLOSE_LOCATION
    base.MIN_VOLUME_RATIO_20D = MIN_VOLUME_RATIO_20D
    base.MAX_REALIZED_VOL_20D = MAX_REALIZED_VOL_20D
    base.MIN_RET20_EXCESS_SPY = MIN_RET20_EXCESS_SPY
    base.MAX_EVENT_AGE_TRADING_DAYS = MAX_EVENT_AGE_TRADING_DAYS
    base.PREDICTION = PREDICTION
    base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    base.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    base._EVENT_INDEX_CACHE = None
    base._load_event_index = _load_event_index
    base._build_quality_index = _build_quality_index
    base._candidate_rows_for_window = _candidate_rows_for_window
    base._gate4 = _gate4
    base._postprocess_payload = _postprocess_payload
    base._build_card = _build_card
    base._write_manifest = _write_manifest
    base._persist = _persist


def main() -> None:
    _install()
    base.main()


if __name__ == "__main__":
    main()
