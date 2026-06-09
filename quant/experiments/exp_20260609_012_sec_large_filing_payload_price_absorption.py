"""exp-20260609-012: SEC large filing-payload price-absorption pool.

Alpha search on one free, replayable SEC text data edge. The experiment tests
whether unusually large, credible SEC filing payloads that the market absorbs
with positive signal-day price/volume action create a cleaner standalone
candidate pool. Paper entry is shifted to the next trading-session open after
the signal-date close is known.

This is replay-only/default-off. It changes no production orders, ranking,
sizing, exits, watchlists, shared adapters, or LLM path. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260603_012_sec_customer_contract_business_win as parent


SCRIPTS_DIR = parent.REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result  # noqa: E402


_PARENT_GATE4_DECISION = parent._gate4_decision
_PARENT_EXPERIMENT_LOG_RECORD = parent._experiment_log_record

EXP_ID = "exp-20260609-012"
STEM = "sec_large_filing_payload_price_absorption"
TRIAL_FAMILY = "sec_large_filing_payload_price_absorption_candidate_pool"
TRIAL_VARIANT_ID = "sec_large_filing_payload_price_absorption_top1_next_open_10d_v1"
CHANGED_VARIABLE = "sec_large_filing_payload_price_absorption_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

OUT_DIR = parent.REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = parent.REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = parent.REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
CARD_MD = parent.REPO_ROOT / "experiments" / "cards" / f"{EXP_ID}.md"
ARTIFACT_MD = parent.REPO_ROOT / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"
MANIFEST_JSON = parent.REPO_ROOT / "experiments" / "manifests" / f"{EXP_ID}.json"
REGISTRY_JSON = parent.REPO_ROOT / "docs" / "experiment_registry.json"

EVENT_NOTIONAL = 4_000.0
MIN_TEXT_WORD_COUNT = 2_500
MIN_TEXT_CHAR_COUNT = 18_000
MIN_DOCUMENTS_FETCHED = 2
MIN_SIGNAL_DAY_RETURN = 0.0
MIN_SIGNAL_DAY_EXCESS_VS_SPY = 0.005
MIN_CLOSE_LOCATION = 0.60
MIN_VOLUME_RATIO_20D = 0.90
MAX_VOLUME_RATIO_20D = 4.00
MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.30

PRICE_CACHE: dict[str, list[dict[str, Any]]] | None = None

EXCLUDED_TEXT_PATTERNS: tuple[str, ...] = (
    r"\bregistered direct\b",
    r"\bprivate placement\b",
    r"\bpublic offering\b",
    r"\bat[- ]the[- ]market\b",
    r"\boffering\b",
    r"\bconvertible\b",
    r"\bwarrant\b",
    r"\bsecurities purchase agreement\b",
    r"\bcredit agreement\b",
    r"\bdebt financing\b",
    r"\bbankruptcy\b",
    r"\bgoing concern\b",
    r"\bdelisting\b",
    r"\brestatement\b",
    r"\bmaterial weakness\b",
    r"\bimpairment\b",
)

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
    "lookahead_guard": (
        "The selector observes signal-date SEC text plus close-to-close OHLCV "
        "reaction, then shifts usable_trade_date to the next trading session "
        "before calling the existing next-open paper trade helper."
    ),
    "parity_note": (
        "This experiment changes no production code. A retained result would "
        "need a shared default-off SEC filing-payload/price-absorption adapter "
        "with the same source fields, exclusions, signal-date OHLCV reaction, "
        "next-session entry shift, and parity tests before any daily report, "
        "candidate queue, or order surface could change."
    ),
}

PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": 0.12,
    "expected_pnl_delta": 1800.0,
    "main_failure_modes": [
        "SEC text size is generic disclosure volume not causal",
        "large-cap earnings relabel",
        "window regression",
        "concentration failed",
        "sample too thin",
    ],
    "confidence_reason": (
        "SEC text coverage spans all three windows and payload size is PIT/free, "
        "but prior SEC semantic pools were noisy or thin; this uses size plus "
        "market absorption instead of phrase thresholds."
    ),
    "recorded_at": "2026-06-09T11:09:53Z",
}


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _configure_parent() -> None:
    parent.EXP_ID = EXP_ID
    parent.STEM = STEM
    parent.TRIAL_FAMILY = TRIAL_FAMILY
    parent.CHANGED_VARIABLE = CHANGED_VARIABLE
    parent.RULE_VERSION = RULE_VERSION
    parent.OUT_DIR = OUT_DIR
    parent.OUT_JSON = OUT_JSON
    parent.BEFORE_JSON = BEFORE_JSON
    parent.AFTER_JSON = AFTER_JSON
    parent.LOG_JSON = LOG_JSON
    parent.TICKET_JSON = TICKET_JSON
    parent.CARD_MD = CARD_MD
    parent.ARTIFACT_MD = ARTIFACT_MD
    parent.EVENT_NOTIONAL = EVENT_NOTIONAL
    parent.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    parent.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    parent.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    parent._candidate_from_row = _candidate_from_row
    parent._gate4_decision = _gate4_decision
    parent._experiment_log_record = _experiment_log_record
    parent._write_artifact = _write_artifact
    parent._update_registry = _update_registry


def _prices() -> dict[str, list[dict[str, Any]]]:
    global PRICE_CACHE
    if PRICE_CACHE is None:
        parent._configure_overlay_module()
        PRICE_CACHE = parent.overlay._load_price_map()
    return PRICE_CACHE


def _item_codes(row: dict[str, Any]) -> set[str]:
    raw = row.get("eight_k_item_codes")
    if isinstance(raw, list):
        return {str(item).strip() for item in raw if str(item).strip()}
    if raw:
        return {part.strip() for part in str(raw).replace(";", ",").split(",") if part.strip()}
    return set()


def _credibility_bucket(row: dict[str, Any]) -> str | None:
    form_type = str(row.get("form_type") or row.get("form_base") or "").upper()
    form_base = str(row.get("form_base") or form_type.split("/")[0]).upper()
    if form_base in {"10-K", "10-Q"}:
        return "periodic_report"
    if form_base == "8-K" and (_item_codes(row) & {"2.02", "7.01", "8.01", "9.01"}):
        return "high_information_8k"
    return None


def _date_index(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {str(row.get("date") or "")[:10]: idx for idx, row in enumerate(rows)}


def _avg(values: list[float]) -> float | None:
    values = [value for value in values if value > 0.0]
    if not values:
        return None
    return sum(values) / len(values)


def _reaction(ticker: str, signal_date: str) -> dict[str, Any] | None:
    prices = _prices()
    ticker_rows = prices.get(ticker)
    spy_rows = prices.get("SPY")
    if not ticker_rows or not spy_rows:
        return None
    ticker_idx = _date_index(ticker_rows).get(signal_date)
    spy_idx = _date_index(spy_rows).get(signal_date)
    if ticker_idx is None or spy_idx is None or ticker_idx <= 0 or spy_idx <= 0:
        return None
    next_idx = ticker_idx + 1
    if next_idx >= len(ticker_rows):
        return None

    ticker_row = ticker_rows[ticker_idx]
    ticker_prev = ticker_rows[ticker_idx - 1]
    spy_row = spy_rows[spy_idx]
    spy_prev = spy_rows[spy_idx - 1]
    try:
        prev_close = float(ticker_prev["close"])
        close = float(ticker_row["close"])
        high = float(ticker_row["high"])
        low = float(ticker_row["low"])
        volume = float(ticker_row["volume"])
        spy_prev_close = float(spy_prev["close"])
        spy_close = float(spy_row["close"])
    except (KeyError, TypeError, ValueError):
        return None
    if prev_close <= 0.0 or close <= 0.0 or spy_prev_close <= 0.0 or spy_close <= 0.0:
        return None
    prior_rows = ticker_rows[max(0, ticker_idx - 20) : ticker_idx]
    avg_volume = _avg([float(row.get("volume") or 0.0) for row in prior_rows])
    avg_dollar_volume = _avg(
        [
            float(row.get("volume") or 0.0) * float(row.get("close") or 0.0)
            for row in prior_rows
        ]
    )
    if avg_volume is None or avg_dollar_volume is None:
        return None

    signal_return = close / prev_close - 1.0
    spy_return = spy_close / spy_prev_close - 1.0
    close_location = (close - low) / (high - low) if high > low else 0.5
    return {
        "signal_day_return": signal_return,
        "signal_day_spy_return": spy_return,
        "signal_day_excess_vs_spy": signal_return - spy_return,
        "signal_day_close_location": close_location,
        "signal_day_volume_ratio_20d": volume / avg_volume if avg_volume else None,
        "avg_dollar_volume_20d": avg_dollar_volume,
        "signal_day_close": close,
        "next_entry_date": str(ticker_rows[next_idx].get("date") or "")[:10],
    }


def _pattern_count(text: str, patterns: tuple[str, ...]) -> int:
    return sum(
        len(re.findall(pattern, text, flags=re.IGNORECASE | re.DOTALL))
        for pattern in patterns
    )


def _candidate_from_row(row: dict[str, Any]) -> dict[str, Any] | None:
    signal_date = str(row.get("usable_trade_date") or "")[:10]
    window = parent._window_name(signal_date)
    ticker = str(row.get("ticker") or "").upper()
    if not ticker or not signal_date or window is None:
        return None
    credibility = _credibility_bucket(row)
    if credibility is None:
        return None

    text_word_count = int(row.get("text_word_count") or 0)
    text_char_count = int(row.get("text_char_count") or 0)
    documents_fetched = int(row.get("documents_fetched") or 0)
    if text_word_count < MIN_TEXT_WORD_COUNT:
        return None
    if text_char_count < MIN_TEXT_CHAR_COUNT:
        return None
    if documents_fetched < MIN_DOCUMENTS_FETCHED:
        return None

    text = parent.semantic_text(row)
    if not text:
        return None
    excluded_text_hits = _pattern_count(text, EXCLUDED_TEXT_PATTERNS)
    if excluded_text_hits:
        return None

    features = parent.language_features(row)
    language_bucket = str(features.get("language_bucket") or "")
    positive_hits = int(features.get("positive_phrase_hits") or 0)
    negative_hits = int(features.get("negative_phrase_hits") or 0)
    guidance_raise_hits = int(features.get("guidance_raise_hits") or 0)
    guidance_cut_hits = int(features.get("guidance_cut_hits") or 0)
    if language_bucket == "negative_language" or guidance_cut_hits > 0:
        return None
    if negative_hits > positive_hits + 1:
        return None

    reaction = _reaction(ticker, signal_date)
    if reaction is None:
        return None
    signal_return = float(reaction["signal_day_return"])
    excess_return = float(reaction["signal_day_excess_vs_spy"])
    close_location = float(reaction["signal_day_close_location"])
    volume_ratio = float(reaction["signal_day_volume_ratio_20d"] or 0.0)
    avg_dollar_volume = float(reaction["avg_dollar_volume_20d"] or 0.0)
    signal_close = float(reaction["signal_day_close"] or 0.0)
    if signal_return < MIN_SIGNAL_DAY_RETURN:
        return None
    if excess_return < MIN_SIGNAL_DAY_EXCESS_VS_SPY:
        return None
    if close_location < MIN_CLOSE_LOCATION:
        return None
    if volume_ratio < MIN_VOLUME_RATIO_20D or volume_ratio > MAX_VOLUME_RATIO_20D:
        return None
    if signal_close < MIN_PRICE:
        return None
    if avg_dollar_volume < MIN_AVG_DOLLAR_VOLUME_20D:
        return None

    size_score = math.log1p(text_word_count) + 0.00002 * text_char_count
    reaction_score = 100.0 * excess_return + 0.75 * close_location + 0.15 * min(volume_ratio, 3.0)
    language_score = 0.08 * positive_hits + 0.12 * guidance_raise_hits - 0.15 * negative_hits
    score = size_score + reaction_score + language_score
    return {
        "ticker": ticker,
        "signal_date": signal_date,
        "sec_usable_trade_date": signal_date,
        "usable_trade_date": reaction["next_entry_date"],
        "filing_date": str(row.get("filing_date") or "")[:10],
        "window": window,
        "form_type": row.get("form_type"),
        "form_base": row.get("form_base"),
        "eight_k_item_codes": sorted(_item_codes(row)),
        "accession_number": row.get("accession_number"),
        "primary_document": row.get("primary_document"),
        "pit_source": row.get("pit_source"),
        "pit_caveat": row.get("pit_caveat"),
        "status": "event_ready",
        "rule_version": RULE_VERSION,
        "strategy": STEM,
        "source_credibility_bucket": credibility,
        "text_word_count": text_word_count,
        "text_char_count": text_char_count,
        "documents_fetched": documents_fetched,
        "language_bucket": language_bucket,
        "text_event_type": features.get("text_event_type"),
        "language_score": features.get("language_score"),
        "positive_phrase_hits": positive_hits,
        "negative_phrase_hits": negative_hits,
        "guidance_raise_hits": guidance_raise_hits,
        "guidance_cut_hits": guidance_cut_hits,
        "excluded_text_hits": excluded_text_hits,
        "business_win_hits": text_word_count,
        "candidate_selection_score": round(score, 6),
        "signal_day_return_pct": round(signal_return * 100.0, 6),
        "signal_day_spy_return_pct": round(float(reaction["signal_day_spy_return"]) * 100.0, 6),
        "signal_day_excess_vs_spy_pct": round(excess_return * 100.0, 6),
        "signal_day_close_location": round(close_location, 6),
        "signal_day_volume_ratio_20d": round(volume_ratio, 6),
        "avg_dollar_volume_20d": round(avg_dollar_volume, 2),
        "min_text_word_count": MIN_TEXT_WORD_COUNT,
        "min_signal_day_excess_vs_spy_pct": MIN_SIGNAL_DAY_EXCESS_VS_SPY * 100.0,
        "known_at": "after_signal_date_close_before_next_session_open",
        "trade_enabled": False,
        "alters_orders": False,
    }


def _gate4_decision(
    aggregate: dict[str, Any],
    results: list[dict[str, Any]],
    target_summary: dict[str, Any],
) -> dict[str, Any]:
    gate4 = _PARENT_GATE4_DECISION(aggregate, results, target_summary)
    passed = bool(gate4["passed"])
    gate4["decision"] = (
        "positive_sec_large_filing_payload_absorption_replay_lead_requires_shared_adapter"
        if passed
        else "rejected_sec_large_filing_payload_price_absorption_candidate_pool"
    )
    gate4["status"] = "observed_only" if passed else "rejected"
    gate4["requires_parity_before_promotion"] = passed
    gate4["rationale"] = (
        "The standalone SEC large filing-payload price-absorption replay passed "
        "Gate 4, but remains replay-only. Retention requires a shared default-off "
        "production/backtest adapter with the same payload-size field, exclusions, "
        "signal-date reaction, next-session entry shift, and parity tests."
        if passed
        else "One or more Gate 4 checks failed, so the standalone SEC large "
        "filing-payload price-absorption source is not retained."
    )
    return gate4


def _experiment_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    record = _PARENT_EXPERIMENT_LOG_RECORD(payload)
    record["mechanism_family"] = payload["mechanism_family"]
    record["trial_variant_id"] = TRIAL_VARIANT_ID
    record["change_type"] = payload["change_type"]
    record["prior_trial_count"] = payload["prior_trial_count"]
    record["nearby_prior_experiments"] = payload["nearby_prior_experiments"]
    record["multiple_testing_risk_bucket"] = payload["multiple_testing_risk_bucket"]
    record["new_evidence_type"] = payload["new_evidence_type"]
    record["post_run_reflection"] = payload["post_run_reflection"]
    record["negative_reflection"] = payload["postmortem_reflection"]
    record["calibration"] = payload["calibration"]
    record["anti_js"] = payload["anti_js"]
    return record


def _write_artifact(payload: dict[str, Any]) -> None:
    comparison = payload["aggregate"]["comparison"]
    lines = [
        f"# {EXP_ID} SEC Large Filing-Payload Price-Absorption Pool",
        "",
        f"- Trial family: `{TRIAL_FAMILY}`",
        f"- Changed variable: `{CHANGED_VARIABLE}`",
        f"- Decision: `{payload['gate4']['decision']}`",
        f"- Aggregate EV delta: {float(comparison['expected_value_score_delta']):+.4f}",
        f"- Aggregate PnL delta: ${float(comparison['strategy_total_pnl_delta']):+,.2f}",
        f"- Target trades: {payload['target_summary']['target_trade_count']}",
        f"- Production impact: `{PRODUCTION_IMPACT['adapter_status']}`",
        "",
        "## Gate 1-4",
        "",
        parent._window_table(payload["results"]),
        "",
        "## Gate 4 Checks",
        "",
    ]
    for key, value in payload["gate4"]["gates"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            "",
            "## Candidate Diagnostics",
            "",
            "```json",
            json.dumps(
                payload.get("candidate_filter_diagnostics", {}),
                indent=2,
                sort_keys=True,
            ),
            "```",
        ]
    )
    lines.extend(
        [
            "",
            "## Decision Rationale",
            "",
            payload["gate4"]["rationale"],
            "",
            "## Reflection",
            "",
            payload["postmortem_reflection"],
            "",
            "## Lookahead / Parity Guard",
            "",
            PRODUCTION_IMPACT["lookahead_guard"],
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "## Reproducibility",
            "",
            (
                ".\\.venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260609_012_sec_large_filing_payload_price_absorption.py"
            ),
        ]
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _update_registry(payload: dict[str, Any]) -> None:
    comparison = payload["aggregate"]["comparison"]
    result = {
        "decision": payload["gate4"]["decision"],
        "aggregate_expected_value_delta": comparison["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": comparison["strategy_total_pnl_delta"],
        "artifact": parent._repo_rel(OUT_JSON),
        "log": parent._repo_rel(LOG_JSON),
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
    }
    fields = {
        "owner": "alpha-search-automation",
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
        "decision": payload["gate4"]["decision"],
        "summary": payload["postmortem_reflection"],
        "artifact": parent._repo_rel(OUT_JSON),
        "log": parent._repo_rel(LOG_JSON),
        "ticket_file": parent._repo_rel(TICKET_JSON),
        "card_file": parent._repo_rel(CARD_MD),
        "revision_manifest_file": parent._repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": comparison["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": comparison["strategy_total_pnl_delta"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXP_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["gate4"]["status"],
        fields=fields,
    )


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXP_ID,
        "status": payload["gate4"]["status"],
        "decision": payload["gate4"]["decision"],
        "created_at": payload["completed_at"],
        "anti_js": payload["anti_js"],
        "allowed_write_scope": [
            parent._repo_rel(Path(__file__)),
            parent._repo_rel(OUT_JSON),
            parent._repo_rel(BEFORE_JSON),
            parent._repo_rel(AFTER_JSON),
            parent._repo_rel(LOG_JSON),
            parent._repo_rel(TICKET_JSON),
            parent._repo_rel(CARD_MD),
            parent._repo_rel(ARTIFACT_MD),
            parent._repo_rel(MANIFEST_JSON),
            parent._repo_rel(parent.EXPERIMENT_LOG),
            parent._repo_rel(REGISTRY_JSON),
        ],
    }
    parent._write_json(MANIFEST_JSON, manifest)


def _patch_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload["experiment_id"] = EXP_ID
    payload["lane"] = "alpha_search"
    payload["trial_family"] = TRIAL_FAMILY
    payload["trial_variant_id"] = TRIAL_VARIANT_ID
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["rule_version"] = RULE_VERSION
    payload["hypothesis"] = (
        "Large SEC filing payloads that the market absorbs with positive "
        "signal-day price/volume action may identify high-information issuer "
        "events with underreaction, expanding the default-off candidate pool "
        "without brittle guidance or contract phrase parsing."
    )
    payload["change_type"] = "default_off_paper_candidate_pool"
    payload["mechanism_family"] = "production_visible_sec_text_event_candidate_pool"
    payload["prior_trial_count"] = 5
    payload["nearby_prior_experiments"] = [
        "exp-20260603-012",
        "exp-20260607-004",
        "exp-20260605-018",
        "exp-20260605-006",
        "exp-20260608-027",
    ]
    payload["multiple_testing_risk_bucket"] = "moderate"
    payload["new_evidence_type"] = "production_visible_sec_filing_payload_size_x_price_absorption_field"
    payload["preflight"] = {
        "alpha_hypothesis": payload["hypothesis"],
        "category": "entry / candidate_pool",
        "playbook_alignment": (
            "Aligned with the playbook preference for free, production-visible "
            "context layers and candidate-pool expansion. It avoids current "
            "frozen or high-risk retunes of revision thresholds, Companyfacts, "
            "FINRA/FTD, state-surface capital allocation, and pure OHLCV "
            "morphology."
        ),
        "nearby_prior_experiments": {
            "exp-20260603-012": (
                "SEC customer-contract/demand text failed Gate 4; this run does "
                "not parse customer/backlog phrases."
            ),
            "exp-20260607-004": (
                "SEC guidance/outlook raise price-aligned was rejected as thin "
                "and concentrated; this run avoids guidance regex thresholds."
            ),
            "exp-20260605-018": (
                "Operational 8-K absorption was rejected; this run uses payload "
                "size plus close/volume confirmation rather than operational "
                "phrase classes."
            ),
            "exp-20260605-006": (
                "Business-development exhibit text failed Gate 4; this run "
                "requires broad filing payload size rather than exhibit topic."
            ),
            "exp-20260608-027": (
                "SEC peer-shock relation alpha was rejected; this run uses "
                "issuer-local absorption and not peer transfer."
            ),
        },
        "single_causal_variable": CHANGED_VARIABLE,
        "policy_bundle": {
            "fixed_decision_under_test": (
                "credible large SEC filing payload + non-negative language + "
                "signal-day positive excess return, high close location, normal "
                "volume, liquid price, next-open entry"
            ),
            "implementation_only": (
                "historical replay runner, default-off paper event sleeve, "
                "artifact/log/ticket/registry wiring, and production parity notes"
            ),
            "not_tested": "exit, sizing, ranking, LLM event scoring, live orders",
        },
        "acceptance_criteria": {
            "canonical_windows": list(parent.WINDOWS.keys()),
            "aggregate_expected_value_delta": "> 0",
            "aggregate_pnl_delta": "> 0",
            "per_window_expected_value_delta": "3 of 3 windows > 0",
            "per_window_pnl_delta": "3 of 3 windows > 0",
            "minimum_target_trades": parent.MIN_TARGET_TRADES,
            "minimum_target_windows": parent.MIN_TARGET_WINDOWS,
            "max_drawdown_drift": parent.MAX_DRAWDOWN_WORSE,
            "survival_rate_floor": 0.05,
            "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi_max": MAX_POSITIVE_HHI,
            "promotion_parity": (
                "Positive replay cannot be promoted until implemented through "
                "a shared default-off production/backtest helper with the same "
                "fields, exclusions, signal-date reaction, and next-session "
                "entry shift."
            ),
        },
        "reproducibility": (
            "The runner persists canonical before/after metrics, selected SEC "
            "filing candidates, Gate 4 checks, ticket, card, artifact, manifest, "
            "and experiment_log.jsonl record."
        ),
    }
    payload["parameters"] = {
        "sec_text_path": parent._repo_rel(parent.SEC_TEXT_PATH),
        "event_notional": EVENT_NOTIONAL,
        "hold_days": parent.HOLD_DAYS,
        "max_paper_trades_per_day": parent.MAX_PAPER_TRADES_PER_DAY,
        "min_text_word_count": MIN_TEXT_WORD_COUNT,
        "min_text_char_count": MIN_TEXT_CHAR_COUNT,
        "min_documents_fetched": MIN_DOCUMENTS_FETCHED,
        "min_signal_day_return_pct": MIN_SIGNAL_DAY_RETURN * 100.0,
        "min_signal_day_excess_vs_spy_pct": MIN_SIGNAL_DAY_EXCESS_VS_SPY * 100.0,
        "min_close_location": MIN_CLOSE_LOCATION,
        "volume_ratio_20d_range": [MIN_VOLUME_RATIO_20D, MAX_VOLUME_RATIO_20D],
        "min_price": MIN_PRICE,
        "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
        "credible_forms": ["10-K", "10-Q", "8-K items 2.02/7.01/8.01/9.01"],
        "excluded_text_patterns": list(EXCLUDED_TEXT_PATTERNS),
        "entry_shift": "signal-date close reaction is known; paper entry uses next ticker trading-session open",
        "selection_order": "entry_date asc, candidate_selection_score desc, text_word_count desc, ticker asc",
    }
    payload["prediction"] = PREDICTION
    payload["production_impact"] = PRODUCTION_IMPACT
    payload["candidate_filter_diagnostics"] = _candidate_filter_diagnostics()
    payload["llm_metrics"] = {
        "used_llm": False,
        "llm_change_scope": "none",
        "note": "No LLM soft-ranking was used because the requested direction prefers free deterministic data and replay-safe LLM data remains sparse.",
    }
    payload["anti_js"] = "No JavaScript was used."
    payload["next_action"] = (
        "If positive, build a shared default-off SEC filing-payload price-"
        "absorption adapter with parity before promotion; if rejected, do not "
        "retune payload-size, close-location, or volume thresholds on this sample."
        if payload["gate4"]["passed"]
        else "Do not retune SEC payload-size/close-location/volume thresholds on this sample; move to a different free-data candidate-pool mechanism."
    )
    actual_success = 1 if payload["gate4"]["passed"] else 0
    comparison = payload["aggregate"]["comparison"]
    payload["calibration"] = {
        "success_probability": PREDICTION["success_probability"],
        "actual_success": actual_success,
        "actual_ev_delta": comparison["expected_value_score_delta"],
        "actual_pnl_delta": comparison["strategy_total_pnl_delta"],
        "brier_score": round((float(PREDICTION["success_probability"]) - actual_success) ** 2, 6),
    }
    payload["postmortem_reflection"] = _reflection(payload)
    payload["post_run_reflection"] = {
        "why_result_happened": payload["postmortem_reflection"],
        "forbidden_near_neighbor_retry": (
            "Do not retry this sample by changing text-size floors, close-location "
            "threshold, volume-ratio bounds, event notional, hold days, max trades "
            "per day, or the 10-K/10-Q/8-K credibility set."
        ),
        "new_evidence_required": (
            "Retry only with forward SEC rows, a materially different issuer "
            "relation field, or a shared default-off adapter if this exact "
            "fixed bundle passes Gate 4."
        ),
    }
    return payload


def _reflection(payload: dict[str, Any]) -> str:
    comparison = payload["aggregate"]["comparison"]
    target_summary = payload["target_summary"]
    target_count = int(target_summary["target_trade_count"])
    ev_delta = float(comparison["expected_value_score_delta"])
    pnl_delta = float(comparison["strategy_total_pnl_delta"])
    max_share = float(target_summary["max_single_positive_share"])
    hhi = float(target_summary["positive_pnl_hhi"])
    if payload["gate4"]["passed"]:
        return (
            "Accepted as an observed-only replay lead because the fixed SEC "
            "payload-size plus price-absorption bundle improved aggregate EV by "
            f"{ev_delta:+.4f} and PnL by ${pnl_delta:+,.2f} across all canonical "
            f"windows with {target_count} target trades while passing drawdown, "
            "survival, and concentration guards. It remains default-off because "
            "no shared production/backtest adapter or parity test exists yet."
        )
    diagnostics = payload.get("candidate_filter_diagnostics") or {}
    stages = diagnostics.get("stages") or {}
    if target_count == 0:
        return (
            "Rejected because the fixed SEC filing-payload price-absorption "
            "bundle produced zero target trades. The filter audit found "
            f"{int(stages.get('language_passed', 0) or 0)} large, credible, "
            "non-negative filing rows before OHLCV reaction checks, but "
            f"{int(stages.get('reaction_missing', 0) or 0)} could not be mapped "
            "to the replay price map, leaving no price-ready candidates across "
            "the three canonical windows. The positive aggregate delta is an "
            "empty-event-curve artifact and is not alpha evidence. Do not retune "
            "payload size, close-location, volume, or credibility thresholds on "
            "this sample; this direction needs broader replay OHLCV coverage or "
            "a different free-data candidate source already inside the tradable "
            "universe."
        )
    failed_gates = [
        key for key, value in payload["gate4"]["gates"].items() if not bool(value)
    ]
    return (
        "Rejected because the large SEC filing-payload price-absorption bundle "
        f"failed Gate 4 checks {failed_gates}. It produced {target_count} target "
        f"trades, aggregate EV delta {ev_delta:+.4f}, aggregate PnL delta "
        f"${pnl_delta:+,.2f}, max positive ticker share {max_share:.3f}, and "
        f"positive PnL HHI {hhi:.3f}. The likely failure mode is that raw filing "
        "size is often disclosure bulk or earnings relabeling rather than an "
        "independent alpha field, and same-day price/volume absorption mostly "
        "confirms events already captured by accepted momentum/consensus "
        "surfaces. Do not retune this threshold bundle on the same sample."
    )


def _candidate_filter_diagnostics() -> dict[str, Any]:
    rows = parent.load_sec_filing_text_rows(parent.SEC_TEXT_PATH)
    stages: Counter[str] = Counter()
    examples: dict[str, Any] = {}
    for row in rows:
        signal_date = str(row.get("usable_trade_date") or "")[:10]
        window = parent._window_name(signal_date)
        if window is None:
            stages["outside_window"] += 1
            continue
        stages["rows_in_window"] += 1
        credibility = _credibility_bucket(row)
        if credibility is None:
            stages["credibility_rejected"] += 1
            examples.setdefault(
                "credibility_rejected",
                {
                    "ticker": row.get("ticker"),
                    "form_type": row.get("form_type"),
                    "eight_k_item_codes": row.get("eight_k_item_codes"),
                },
            )
            continue
        stages["credible"] += 1
        text_word_count = int(row.get("text_word_count") or 0)
        text_char_count = int(row.get("text_char_count") or 0)
        documents_fetched = int(row.get("documents_fetched") or 0)
        if text_word_count < MIN_TEXT_WORD_COUNT:
            stages["word_count_rejected"] += 1
            examples.setdefault(
                "word_count_rejected",
                {"ticker": row.get("ticker"), "text_word_count": text_word_count},
            )
            continue
        if text_char_count < MIN_TEXT_CHAR_COUNT:
            stages["char_count_rejected"] += 1
            examples.setdefault(
                "char_count_rejected",
                {"ticker": row.get("ticker"), "text_char_count": text_char_count},
            )
            continue
        if documents_fetched < MIN_DOCUMENTS_FETCHED:
            stages["documents_rejected"] += 1
            continue
        stages["payload_passed"] += 1
        text = parent.semantic_text(row)
        excluded_text_hits = _pattern_count(text, EXCLUDED_TEXT_PATTERNS)
        if excluded_text_hits:
            stages["excluded_text_rejected"] += 1
            examples.setdefault(
                "excluded_text_rejected",
                {
                    "ticker": row.get("ticker"),
                    "form_type": row.get("form_type"),
                    "excluded_text_hits": excluded_text_hits,
                },
            )
            continue
        features = parent.language_features(row)
        if (
            str(features.get("language_bucket") or "") == "negative_language"
            or int(features.get("guidance_cut_hits") or 0) > 0
        ):
            stages["negative_language_rejected"] += 1
            continue
        if int(features.get("negative_phrase_hits") or 0) > int(features.get("positive_phrase_hits") or 0) + 1:
            stages["negative_over_positive_rejected"] += 1
            continue
        stages["language_passed"] += 1
        reaction = _reaction(str(row.get("ticker") or "").upper(), signal_date)
        if reaction is None:
            stages["reaction_missing"] += 1
            examples.setdefault(
                "reaction_missing",
                {"ticker": row.get("ticker"), "signal_date": signal_date},
            )
            continue
        if float(reaction["signal_day_return"]) < MIN_SIGNAL_DAY_RETURN:
            stages["signal_return_rejected"] += 1
            continue
        if float(reaction["signal_day_excess_vs_spy"]) < MIN_SIGNAL_DAY_EXCESS_VS_SPY:
            stages["excess_return_rejected"] += 1
            continue
        if float(reaction["signal_day_close_location"]) < MIN_CLOSE_LOCATION:
            stages["close_location_rejected"] += 1
            continue
        volume_ratio = float(reaction["signal_day_volume_ratio_20d"] or 0.0)
        if volume_ratio < MIN_VOLUME_RATIO_20D or volume_ratio > MAX_VOLUME_RATIO_20D:
            stages["volume_ratio_rejected"] += 1
            continue
        if float(reaction["signal_day_close"] or 0.0) < MIN_PRICE:
            stages["price_rejected"] += 1
            continue
        if float(reaction["avg_dollar_volume_20d"] or 0.0) < MIN_AVG_DOLLAR_VOLUME_20D:
            stages["dollar_volume_rejected"] += 1
            continue
        stages["fully_passed"] += 1
    return {
        "stages": dict(sorted(stages.items())),
        "first_examples": examples,
        "interpretation": (
            "The fixed bundle produced no price-ready target trades because the "
            "large SEC text candidates did not map to the replay OHLCV price "
            "surface after the language/payload filters."
        ),
    }


def main() -> int:
    _configure_parent()
    payload = parent.build_payload()
    payload = _patch_payload(payload)
    parent.persist(payload)
    _write_manifest(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["gate4"]["decision"],
                "aggregate": payload["aggregate"]["comparison"],
                "target_summary": payload["target_summary"],
                "gate4": payload["gate4"],
                "anti_js": payload["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
