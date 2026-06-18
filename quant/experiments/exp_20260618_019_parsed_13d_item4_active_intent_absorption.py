"""exp-20260618-019: parsed 13D Item-4 active-intent absorption scout.

Replay-only alpha search. The single decision hypothesis is that local parsed
Schedule 13D Item-4 purpose text can separate active strategic/governance
ownership intent from stale 13D metadata, founder/control, estate-planning, and
transaction-mechanics noise. Qualified events are tested as a default-off paper
candidate pool only when same-day price action absorbs the filing versus SPY
before next-open entry.

No production code, shared adapter, live/default orders, ranking, sizing, exits,
LLM/news path, or watchlist behavior is changed. A positive result is only a
replay lead until a shared historical/daily helper reproduces it. No JavaScript
is used.
"""

from __future__ import annotations

import json
import math
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260617_024_s8_employee_equity_registration_absorption_scout as runner

if str(runner.REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(runner.REPO_ROOT))

from quant import sec_13d13g_ingest as ingest  # noqa: E402


EXPERIMENT_ID = "exp-20260618-019"
STEM = "parsed_13d_item4_active_intent_absorption"
TRIAL_FAMILY = "parsed_13d_item4_active_intent_absorption_candidate_pool"
TRIAL_VARIANT_ID = "parsed_13d_item4_active_intent_absorption_top1_next_open_10d_v1"
CHANGED_VARIABLE = "parsed_13d_item4_active_intent_absorption_candidate_pool_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = runner.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260618_019_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = runner.BASE_NOTIONAL_USD
HOLD_DAYS = runner.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = runner.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = runner.SAME_TICKER_COOLDOWN_DAYS

MIN_PRICE = runner.MIN_PRICE
MIN_AVG_DOLLAR_VOLUME_20D = runner.MIN_AVG_DOLLAR_VOLUME_20D
MIN_SIGNAL_RETURN = runner.MIN_SIGNAL_RETURN
MIN_SIGNAL_EXCESS_SPY = runner.MIN_SIGNAL_EXCESS_SPY
MIN_CLOSE_LOCATION = runner.MIN_CLOSE_LOCATION
MIN_VOLUME_RATIO_20D = runner.MIN_VOLUME_RATIO_20D
MAX_REALIZED_VOL_20D = runner.MAX_REALIZED_VOL_20D
MIN_RET20_EXCESS_SPY = runner.MIN_RET20_EXCESS_SPY
MAX_EVENT_AGE_TRADING_DAYS = runner.MAX_EVENT_AGE_TRADING_DAYS

INSIDER_TYPES = {"IN", "HC"}

ACTIVE_PHRASES = (
    "strategic alternatives",
    "maximize shareholder value",
    "enhance shareholder value",
    "unlock shareholder value",
    "board representation",
    "board seat",
    "nomination",
    "nominated",
    "director nominee",
    "cooperation agreement",
    "settlement agreement",
    "letter to the board",
    "proxy contest",
    "shareholder proposal",
    "special meeting",
    "consent solicitation",
    "business practices and governance",
    "corporate governance",
    "engage in discussions with management",
    "engage in discussions with the board",
    "discussions with management",
    "discussions with the board",
)

NOISE_PHRASES = (
    "estate planning",
    "gifted",
    "gift ",
    "charitable",
    "revocable trust",
    "family trust",
    "inheritance",
    "prepaid forward",
    "registration rights",
    "secondary offering",
    "share repurchase",
    "merger",
    "business combination",
    "control of the company",
    "parents of the company",
    "parent of the company",
    "issuer and the reporting",
    "solely for investment purposes",
)

PREDICTION = {
    "success_probability": 0.14,
    "expected_ev_delta": 0.20,
    "expected_pnl_delta": 3000.0,
    "main_failure_modes": [
        "thin_sample",
        "issuer_control_noise",
        "priced_before_next_open",
        "window_ev_regression",
        "accepted_comparator_not_beaten",
        "drawdown_drift",
    ],
    "confidence_reason": (
        "Parsed 13D/13G diagnostics explicitly named Item-4 purpose text as the "
        "next valid evidence axis after raw metadata and 13D/A stake-increase "
        "failed; the risk is sparse activist-quality sample and stale ownership "
        "timing."
    ),
    "recorded_at": "2026-06-18T18:05:23+00:00",
}

PRODUCTION_IMPACT = {
    **runner.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "uses_free_sec_companyfacts": False,
    "uses_free_sec_submissions": True,
    "uses_parsed_sec_13d13g": True,
    "uses_free_ohlcv": True,
    "execution_envelope": {
        **runner.PRODUCTION_IMPACT["execution_envelope"],
        "liquidity_source": "price >= $10 and ADV20 >= $50M from PIT OHLCV",
        "failure_handling": (
            "missing parsed 13D row, missing cached primary_doc.xml, missing "
            "Item-4 purpose text, inactive/noisy intent classification, missing "
            "OHLCV, missing next open, or missing 10d exit rejects the paper "
            "candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same PIT "
        "13D Item-4 text extraction, active-intent classifier, acceptance-time "
        "signal date, price-absorption gate, cooldown, next-open paper entry, "
        "10-day exit, costs, and concentration controls in both historical "
        "replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: parsed Schedule 13D Item-4 purpose text that signals "
        "active strategic or governance intent, combined with same-day liquid "
        "SPY-relative absorption, may identify ownership events with fresher "
        "demand than raw 13D metadata or stake-size direction alone."
    ),
    "2_history_check": {
        "exp-20260612-015": (
            "Rejected direct SC 13D activist-initiation metadata; required parsed "
            "13D documents including purpose text before retry."
        ),
        "exp-20260618-016": (
            "Observed-only parsed 13D/13G diagnostic found no clean static subset "
            "and explicitly named 13D Item-4 purpose-text classification as a "
            "valid next evidence axis."
        ),
        "exp-20260618-017": (
            "Rejected parsed 13D/A stake-increase direction. This run tests "
            "Item-4 intent text rather than sequential stake direction."
        ),
        "exp-20260618-018": (
            "Blocked 13G/A stake-increase due to missing parsed amendment rows. "
            "This run uses already cached local 13D XML."
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
        "exp_20260618_019_parsed_13d_item4_active_intent_absorption.py"
    ),
}

_EVENT_INDEX_CACHE: tuple[dict[str, list[dict[str, Any]]], dict[str, Any]] | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return runner.base._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return runner._round(value, digits)


def _localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _extract_item4_text(accession_number: str) -> str:
    path = ingest.XML_CACHE_DIR / f"{accession_number.replace('-', '')}.xml"
    if not path.exists():
        return ""
    try:
        root = ET.fromstring(path.read_text(encoding="utf-8", errors="replace"))
    except ET.ParseError:
        return ""
    chunks: list[str] = []
    for el in root.iter():
        if _localname(el.tag) in {"item4", "transactionPurpose"}:
            chunks.extend(text.strip() for text in el.itertext() if text and text.strip())
    return " ".join(" ".join(chunks).split())


def _intent_classification(row: dict[str, Any], item4_text: str) -> dict[str, Any]:
    lower = item4_text.lower()
    active_hits = [phrase for phrase in ACTIVE_PHRASES if phrase in lower]
    noise_hits = [phrase for phrase in NOISE_PHRASES if phrase in lower]
    types = {str(t).upper() for t in row.get("reporting_person_types") or []}
    pure_insider = bool(types) and types <= INSIDER_TYPES
    max_pct = row.get("max_class_percent")
    extreme_control = max_pct is not None and float(max_pct) >= 50.0
    eligible = bool(active_hits) and not noise_hits and not pure_insider and not extreme_control
    return {
        "eligible": eligible,
        "active_hits": active_hits,
        "noise_hits": noise_hits,
        "pure_insider": pure_insider,
        "extreme_control": extreme_control,
        "active_score": len(active_hits),
        "intent_bucket": "active_strategic_governance" if eligible else "excluded_or_inactive",
    }


def _load_13d_item4_events() -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    events = ingest.iter_ownership_filings(families=("13D",), include_amendments=True)
    parsed = ingest.build_parsed_rows(events, fetch=False, refresh=False)
    rows = parsed["rows"]
    index: dict[str, list[dict[str, Any]]] = {}
    stats: Counter[str] = Counter()
    stats["enumerated_13d_events"] = len(events)
    stats["parsed_13d_rows"] = len(rows)
    stats.update({f"fetch_status_{key}": value for key, value in parsed["fetch_status"].items()})

    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            stats["missing_ticker"] += 1
            continue
        item4_text = _extract_item4_text(str(row.get("accession_number") or ""))
        if not item4_text:
            stats["missing_item4_text"] += 1
            continue
        stats["rows_with_item4_text"] += 1
        classification = _intent_classification(row, item4_text)
        if classification["noise_hits"]:
            stats["excluded_noise_text"] += 1
        if classification["pure_insider"]:
            stats["excluded_pure_insider_type"] += 1
        if classification["extreme_control"]:
            stats["excluded_extreme_control_pct"] += 1
        if not classification["active_hits"]:
            stats["excluded_no_active_phrase"] += 1
        if not classification["eligible"]:
            continue
        stats["active_intent_events"] += 1
        stats[f"active_intent_{row.get('window')}"] += 1
        stats[f"active_intent_form_{row.get('form')}"] += 1
        excerpt = item4_text[:700]
        index.setdefault(ticker, []).append(
            {
                "ticker": ticker,
                "form": row.get("form"),
                "family": row.get("family"),
                "filing_date": row.get("filing_date"),
                "accepted_after_close": runner._acceptance_after_close(row.get("accepted_at")),
                "acceptance_datetime": row.get("accepted_at"),
                "accession_number": row.get("accession_number"),
                "amendment_no": row.get("amendment_no"),
                "holder_key": _holder_key(row),
                "max_class_percent": _round(row.get("max_class_percent"), 4),
                "reporting_person_types": row.get("reporting_person_types") or [],
                "n_reporting_persons": row.get("n_reporting_persons"),
                "is_big3": bool(row.get("is_big3")),
                "issuer_cik": row.get("issuer_cik"),
                "issuer_name": row.get("issuer_name"),
                "issuer_cusip": row.get("issuer_cusip"),
                "source_row_window": row.get("window"),
                "item4_intent_bucket": classification["intent_bucket"],
                "item4_active_hits": classification["active_hits"],
                "item4_noise_hits": classification["noise_hits"],
                "item4_active_score": classification["active_score"],
                "item4_excerpt": excerpt,
            }
        )

    for ticker in index:
        index[ticker].sort(
            key=lambda event: (
                str(event.get("filing_date") or ""),
                str(event.get("acceptance_datetime") or ""),
                str(event.get("accession_number") or ""),
            )
        )
    stats["tickers_with_active_intent_events"] = len(index)
    stats["candidate_event_count"] = sum(len(rows_) for rows_ in index.values())
    summary = {
        "parsed_surface": "quant/sec_13d13g_ingest.py build_parsed_rows(fetch=False)",
        "xml_cache": _repo_rel(ingest.XML_CACHE_DIR),
        "candidate_universe_scope": "broad_liquid_warehouse_all_windows_full_liquid",
        "intent_rule": "13D Item-4 active strategic/governance phrase present, no fixed noise/control exclusion hit",
        "active_phrases": list(ACTIVE_PHRASES),
        "noise_phrases": list(NOISE_PHRASES),
        "no_js": True,
        **dict(stats),
    }
    return index, summary


def _holder_key(row: dict[str, Any]) -> str:
    names: list[str] = []
    for person in row.get("reporting_persons") or []:
        name = str(person.get("reporting_person_name") or "").lower()
        normalized = " ".join(
            name.replace(",", " ").replace(".", " ").replace("&", " and ").split()
        )
        if normalized:
            names.append(normalized)
    return "|".join(sorted(names)) or str(row.get("accession_number") or "")


def _load_event_index() -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    global _EVENT_INDEX_CACHE
    if _EVENT_INDEX_CACHE is None:
        _EVENT_INDEX_CACHE = _load_13d_item4_events()
    return _EVENT_INDEX_CACHE


def _build_quality_index(
    companyfacts_rows: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    index, summary = _load_event_index()
    return index, {
        **summary,
        "selected_companyfacts_rows_ignored": len(companyfacts_rows),
        "field_source": "parsed_sec_13d_item4_text_intent_not_companyfacts",
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    sector_entries: dict[str, dict[str, Any]],
    quality_index: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    indices = {
        ticker: runner.base.framework.shadow._row_index(
            runner.base.framework.shadow._series(snapshot, ticker)
        )
        for ticker in snapshot
    }
    dates = runner.base.framework.shadow._trading_dates(snapshot)
    start = str(cfg["start"])
    end = str(cfg["end"])
    scan: Counter[str] = Counter()
    scan["eligible_event_tickers"] = len(set(quality_index) & set(snapshot))
    scan["active_intent_events_total"] = sum(len(v) for v in quality_index.values())
    candidates: list[dict[str, Any]] = []
    for ticker in sorted(set(quality_index) & set(snapshot)):
        for event in quality_index[ticker]:
            signal_date = runner._signal_date_for_event(event, dates)
            if signal_date is None:
                scan["event_after_last_or_stale"] += 1
                continue
            if not (start <= signal_date <= end):
                scan["event_outside_window"] += 1
                continue
            scan["active_intent_events_in_window"] += 1
            scan[f"source_window_{event.get('source_row_window')}"] += 1
            confirm = runner._absorption_confirmation(
                snapshot=snapshot,
                indices=indices,
                ticker=ticker,
                signal_date=signal_date,
            )
            if confirm is None:
                scan["failed_absorption_or_liquidity_gate"] += 1
                continue
            scan["qualified_candidate_rows"] += 1
            meta = sector_entries.get(ticker, {})
            score = (
                1.60 * float(confirm["candidate_signal_excess_spy"])
                + 0.40 * float(confirm["candidate_close_location"])
                + 0.25 * max(0.0, float(confirm["candidate_ret20_excess_spy"]))
                + 0.08
                * math.log10(
                    max(float(confirm["candidate_avg_dollar_volume_20d"]), 1.0)
                    / 1_000_000.0
                )
                + min(0.30, 0.06 * float(event.get("item4_active_score") or 0.0))
            )
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "SEC_13D_ITEM4_ACTIVE_INTENT_ABSORPTION_PAPER",
                    "candidate_score": _round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": "parsed_13d_item4_text_and_signal_close_before_next_open_paper_entry",
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "uses_free_sec_submissions": True,
                    "uses_parsed_sec_13d13g": True,
                    "uses_free_sec_companyfacts": False,
                    "uses_free_ohlcv": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    "sec_13d_form": event.get("form"),
                    "sec_13d_filing_date": event.get("filing_date"),
                    "sec_13d_accepted_after_close": event.get("accepted_after_close"),
                    "sec_13d_acceptance_datetime": event.get("acceptance_datetime"),
                    "sec_13d_accession_number": event.get("accession_number"),
                    "sec_13d_amendment_no": event.get("amendment_no"),
                    "sec_13d_holder_key": event.get("holder_key"),
                    "sec_13d_max_class_percent": event.get("max_class_percent"),
                    "sec_13d_reporting_person_types": event.get("reporting_person_types"),
                    "sec_13d_n_reporting_persons": event.get("n_reporting_persons"),
                    "sec_13d_is_big3": event.get("is_big3"),
                    "sec_13d_issuer_cik": event.get("issuer_cik"),
                    "sec_13d_issuer_name": event.get("issuer_name"),
                    "sec_13d_item4_intent_bucket": event.get("item4_intent_bucket"),
                    "sec_13d_item4_active_hits": event.get("item4_active_hits"),
                    "sec_13d_item4_active_score": event.get("item4_active_score"),
                    "sec_13d_item4_excerpt": event.get("item4_excerpt"),
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
            -float(row["candidate_signal_excess_spy"] or 0.0),
            -float(row["candidate_close_location"] or 0.0),
            -float(row.get("candidate_avg_dollar_volume_20d") or 0.0),
            row["ticker"],
        )
    )
    scan["deduped_candidate_rows"] = len(rows)
    scan["candidate_signal_days"] = len({row["date"] for row in rows})
    scan["candidate_tickers"] = len({row["ticker"] for row in rows})
    scan["eligible_quality_tickers"] = scan["eligible_event_tickers"]
    return rows, {
        **dict(scan),
        "rule_version": RULE_VERSION,
        "intent_rule": "fixed Item-4 active strategic/governance text classifier",
        "min_price": MIN_PRICE,
        "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
        "min_signal_return": MIN_SIGNAL_RETURN,
        "min_signal_excess_spy": MIN_SIGNAL_EXCESS_SPY,
        "min_close_location": MIN_CLOSE_LOCATION,
        "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
        "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
        "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
        "max_event_age_trading_days": MAX_EVENT_AGE_TRADING_DAYS,
    }


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = runner.base.framework._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = list(gate.get("failed_reasons") or [])
    ev_delta = float(aggregate["expected_value_score_delta_sum"] or 0.0)
    pnl_delta = float(aggregate["total_pnl_delta_sum"] or 0.0)
    if ev_delta <= runner.base.COMPRESSION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_compression_ev_not_beaten")
    if pnl_delta <= runner.base.COMPRESSION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_compression_pnl_not_beaten")
    if ev_delta <= runner.base.DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_distribution_ev_not_beaten")
    if pnl_delta <= runner.base.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_distribution_pnl_not_beaten")
    gate["failed_reasons"] = failed
    gate["accepted_compression_comparator"] = runner.base.COMPRESSION_COMPARATOR
    gate["accepted_distribution_comparator"] = runner.base.DISTRIBUTION_COMPARATOR
    gate["passed"] = not failed
    gate["decision"] = (
        "positive_replay_lead_not_promoted_parsed_13d_item4_active_intent_absorption"
        if gate["passed"]
        else "rejected_parsed_13d_item4_active_intent_absorption_candidate_pool"
    )
    return gate


def _interpretation(payload: dict[str, Any]) -> str:
    gate4 = payload["gate4"]
    if gate4["passed"]:
        return (
            "The parsed 13D Item-4 active-intent absorption source cleared the "
            "numeric three-window replay screen, but remains only a replay lead "
            "because no shared daily/backtest helper was promoted."
        )
    return (
        "The parsed 13D Item-4 active-intent absorption source did not clear "
        f"Gate 4 (failed: {', '.join(gate4['failed_reasons']) or 'none'}). "
        "The fixed bundle tested one deterministic Item-4 intent classifier plus "
        "signal-day SPY-relative price absorption. The result is not retained or "
        "promoted."
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
            "new_evidence_type": "parsed_13d_item4_purpose_text_intent",
            "nearby_prior_experiments": [
                "exp-20260612-015",
                "exp-20260618-016",
                "exp-20260618-017",
                "exp-20260618-018",
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
        "intent_rule": "fixed Item-4 active strategic/governance text classifier",
        "active_phrases": list(ACTIVE_PHRASES),
        "noise_phrases": list(NOISE_PHRASES),
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
        "Parsed Schedule 13D Item-4 purpose text is read from local cached EDGAR "
        "primary_doc.xml through quant/sec_13d13g_ingest.py event enumeration. A "
        "row is eligible only when a fixed active strategic/governance phrase is "
        "present and fixed estate/gift/family/control/transaction-mechanics noise "
        "phrases are absent. Pure insider-type and >=50% control rows are excluded. "
        "The signal date is the filing date unless the SEC acceptance timestamp is "
        "after 16:00, in which case it is the next trading day. Candidates must "
        "show signal-day price absorption before next-open paper entry: "
        "non-negative daily return, return minus SPY >= 0.5%, close location >= "
        "0.56, volume ratio >= 0.75, realized vol <= 12%, ret20 excess vs SPY >= "
        "-5%, price >= $10, and ADV20 >= $50M. Paper entry is the next available "
        "open with entry slippage; exit is the close 10 trading days after the "
        "signal with target-side sell slippage and ROUND_TRIP_COST_PCT."
    )
    payload["backtest_protocol"]["parsed_surface"] = "quant/sec_13d13g_ingest.py"
    payload["gate2"]["runtime_fields"] = [
        "parsed 13D accession number",
        "parsed 13D filing date",
        "parsed 13D acceptanceDateTime",
        "cached 13D primary_doc.xml",
        "Item-4 transactionPurpose/item4 text",
        "parsed reporting-person names",
        "parsed reporting-person types",
        "parsed max_class_percent",
        "warehouse ticker_universe CIK mapping",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for price absorption",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "If this fixed Item-4 active-intent source fails, do not retry by "
        "sweeping phrase lists, holder types, classPercent thresholds, signal "
        "excess, close-location, volume, volatility, ret20, price/ADV, event age, "
        "top-N, hold days, cooldown, or notional on these frozen windows. A valid "
        "retry needs materially richer purpose-text provenance such as direct "
        "activist campaign/board-seat outcomes, 13G/A stake-change direction, "
        "repaired old_thin structured XML coverage, or closed forward "
        "replacement-value rows."
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
            "A negative result means deterministic Item-4 active/governance text "
            "still arrives too late, remains too issuer-control/transactional, or "
            "does not add timing value after next-open execution and price "
            "absorption. Keep the field as ownership context unless stronger "
            "forward replacement rows appear."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping phrase lists, holder types, classPercent "
            "thresholds, signal excess, close-location, volume, volatility, ret20, "
            "price/ADV, event age, top-N, hold days, cooldown, or notional on "
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Events | Raw | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in runner.base.framework.WINDOWS:
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
                events=scan.get("active_intent_events_in_window", 0),
                raw=scan.get("deduped_candidate_rows", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Parsed 13D Item-4 Active-Intent Absorption",
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
            _repo_rel(Path(__file__)): runner.base.framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): runner.base.framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): runner.base.framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): runner.base.framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): runner.base.framework._sha256(CARD_MD),
        },
    }
    runner.base.framework._write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any]) -> None:
    log_record = runner.base._build_log_record(payload)
    runner.base.framework._write_json(OUT_JSON, payload)
    runner.base.framework._write_json(LOG_JSON, payload)
    runner.base.framework._write_text(CARD_MD, _build_card(payload))
    runner.base.framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
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
    runner.base.persist_self_registered_result(
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
    runner.EXPERIMENT_ID = EXPERIMENT_ID
    runner.STEM = STEM
    runner.TRIAL_FAMILY = TRIAL_FAMILY
    runner.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    runner.CHANGED_VARIABLE = CHANGED_VARIABLE
    runner.RULE_VERSION = RULE_VERSION
    runner.OWNER = OWNER
    runner.OUT_DIR = OUT_DIR
    runner.OUT_JSON = OUT_JSON
    runner.LOG_JSON = LOG_JSON
    runner.TICKET_JSON = TICKET_JSON
    runner.CARD_MD = CARD_MD
    runner.MANIFEST_JSON = MANIFEST_JSON
    runner.EXPERIMENT_LOG = EXPERIMENT_LOG
    runner.REGISTRY_JSON = REGISTRY_JSON
    runner.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    runner.HOLD_DAYS = HOLD_DAYS
    runner.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    runner.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    runner.MIN_PRICE = MIN_PRICE
    runner.MIN_AVG_DOLLAR_VOLUME_20D = MIN_AVG_DOLLAR_VOLUME_20D
    runner.MIN_SIGNAL_RETURN = MIN_SIGNAL_RETURN
    runner.MIN_SIGNAL_EXCESS_SPY = MIN_SIGNAL_EXCESS_SPY
    runner.MIN_CLOSE_LOCATION = MIN_CLOSE_LOCATION
    runner.MIN_VOLUME_RATIO_20D = MIN_VOLUME_RATIO_20D
    runner.MAX_REALIZED_VOL_20D = MAX_REALIZED_VOL_20D
    runner.MIN_RET20_EXCESS_SPY = MIN_RET20_EXCESS_SPY
    runner.MAX_EVENT_AGE_TRADING_DAYS = MAX_EVENT_AGE_TRADING_DAYS
    runner.PREDICTION = PREDICTION
    runner.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    runner.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    runner._EVENT_INDEX_CACHE = None
    runner._load_event_index = _load_event_index
    runner._build_quality_index = _build_quality_index
    runner._candidate_rows_for_window = _candidate_rows_for_window
    runner._gate4 = _gate4
    runner._postprocess_payload = _postprocess_payload
    runner._build_card = _build_card
    runner._write_manifest = _write_manifest
    runner._persist = _persist


def main() -> None:
    _install()
    runner.main()


if __name__ == "__main__":
    main()
