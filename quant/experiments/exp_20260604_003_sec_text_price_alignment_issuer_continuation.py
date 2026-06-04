"""exp-20260604-003: SEC text-price alignment issuer continuation.

Alpha search on one production-visible free-data field. A high/medium
credibility SEC filing must have positive filing text or earnings-release text,
and the issuer must react positively versus SPY on the PIT signal date. The
paper entry is shifted to the next trading-session open so the reaction is
known before entry.

Core signal generation, ranking, sizing, exits, LLM/news replay, watchlists,
shared adapters, and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260603_012_sec_customer_contract_business_win as parent


_PARENT_GATE4_DECISION = parent._gate4_decision

EXP_ID = "exp-20260604-003"
STEM = "sec_text_price_alignment_issuer_continuation"
TRIAL_FAMILY = "sec_text_price_alignment_issuer_continuation_candidate_pool"
CHANGED_VARIABLE = "sec_text_price_alignment_issuer_continuation_candidate_source_v1"
RULE_VERSION = "sec_text_price_alignment_positive_language_or_earnings_text_excess1_v1"

OUT_DIR = parent.REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = parent.REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = parent.REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
CARD_MD = parent.REPO_ROOT / "experiments" / "cards" / f"{EXP_ID}.md"
ARTIFACT_MD = parent.REPO_ROOT / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"

EVENT_NOTIONAL = 4_000.0
MIN_SIGNAL_DAY_RETURN = 0.0
MIN_SIGNAL_DAY_EXCESS_VS_SPY = 0.01
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.30

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
        "The candidate selector observes signal-date close-to-close reaction, "
        "then shifts usable_trade_date to the next trading session before "
        "calling the existing next-open paper trade helper."
    ),
    "parity_note": (
        "This experiment changes no production code. A retained result would "
        "need a shared default-off SEC text-price alignment adapter using the "
        "same filing credibility, language bucket, signal-day OHLCV reaction, "
        "next-session entry shift, and parity tests before any daily report, "
        "candidate queue, or order surface could change."
    ),
}

_PRICE_CACHE: dict[str, list[dict[str, Any]]] | None = None


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
    parent._write_artifact = _write_artifact


def _prices() -> dict[str, list[dict[str, Any]]]:
    global _PRICE_CACHE
    if _PRICE_CACHE is None:
        parent._configure_overlay_module()
        _PRICE_CACHE = parent.overlay._load_price_map()
    return _PRICE_CACHE


def _item_codes(row: dict[str, Any]) -> set[str]:
    raw = row.get("eight_k_item_codes")
    if isinstance(raw, list):
        return {str(item).strip() for item in raw if str(item).strip()}
    if raw:
        return {part.strip() for part in str(raw).replace(";", ",").split(",") if part.strip()}
    return set()


def _credibility_bucket(row: dict[str, Any]) -> str | None:
    form_type = str(row.get("form_type") or row.get("form_base") or "").upper()
    form_base = form_type.split("/")[0]
    if form_base in {"10-K", "10-Q"}:
        return "high"
    if form_base == "8-K" and (_item_codes(row) & {"2.02", "2.05"}):
        return "medium"
    return None


def _date_index(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {str(row.get("date") or "")[:10]: idx for idx, row in enumerate(rows)}


def _reaction(
    *,
    ticker: str,
    signal_date: str,
) -> dict[str, Any] | None:
    prices = _prices()
    ticker_rows = prices.get(ticker)
    spy_rows = prices.get("SPY")
    if not ticker_rows or not spy_rows:
        return None
    ticker_idx = _date_index(ticker_rows).get(signal_date)
    spy_idx = _date_index(spy_rows).get(signal_date)
    if ticker_idx is None or spy_idx is None or ticker_idx <= 0 or spy_idx <= 0:
        return None
    ticker_prev = ticker_rows[ticker_idx - 1].get("close")
    ticker_close = ticker_rows[ticker_idx].get("close")
    spy_prev = spy_rows[spy_idx - 1].get("close")
    spy_close = spy_rows[spy_idx].get("close")
    if not ticker_prev or ticker_close is None or not spy_prev or spy_close is None:
        return None
    signal_return = (float(ticker_close) / float(ticker_prev)) - 1.0
    spy_return = (float(spy_close) / float(spy_prev)) - 1.0
    next_idx = ticker_idx + 1
    if next_idx >= len(ticker_rows):
        return None
    next_date = str(ticker_rows[next_idx].get("date") or "")[:10]
    if not next_date:
        return None
    return {
        "signal_day_return": signal_return,
        "signal_day_spy_return": spy_return,
        "signal_day_excess_vs_spy": signal_return - spy_return,
        "next_entry_date": next_date,
    }


def _candidate_from_row(row: dict[str, Any]) -> dict[str, Any] | None:
    signal_date = str(row.get("usable_trade_date") or "")[:10]
    window = parent._window_name(signal_date)
    ticker = str(row.get("ticker") or "").upper()
    if not ticker or not signal_date or window is None:
        return None
    credibility = _credibility_bucket(row)
    if credibility is None:
        return None

    features = parent.language_features(row)
    language_bucket = str(features.get("language_bucket") or "")
    text_event_type = str(features.get("text_event_type") or "")
    guidance_cut_hits = int(features.get("guidance_cut_hits") or 0)
    guidance_raise_hits = int(features.get("guidance_raise_hits") or 0)
    positive_hits = int(features.get("positive_phrase_hits") or 0)
    negative_hits = int(features.get("negative_phrase_hits") or 0)

    aligned_text = (
        language_bucket == "positive_language"
        or text_event_type == "earnings_release_text"
        or guidance_raise_hits > 0
    )
    if not aligned_text:
        return None
    if language_bucket == "negative_language" or guidance_cut_hits > 0:
        return None

    reaction = _reaction(ticker=ticker, signal_date=signal_date)
    if reaction is None:
        return None
    signal_return = float(reaction["signal_day_return"])
    excess_return = float(reaction["signal_day_excess_vs_spy"])
    if signal_return < MIN_SIGNAL_DAY_RETURN:
        return None
    if excess_return < MIN_SIGNAL_DAY_EXCESS_VS_SPY:
        return None

    score = (
        excess_return * 100.0
        + 0.25 * positive_hits
        + 0.50 * guidance_raise_hits
        + 0.10 * float(features.get("language_score") or 0.0)
        - 0.25 * negative_hits
    )
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
        "status": "event_ready",
        "rule_version": RULE_VERSION,
        "strategy": STEM,
        "source_credibility_bucket": credibility,
        "language_bucket": language_bucket,
        "text_event_type": text_event_type,
        "language_score": features.get("language_score"),
        "positive_phrase_hits": positive_hits,
        "negative_phrase_hits": negative_hits,
        "guidance_raise_hits": guidance_raise_hits,
        "guidance_cut_hits": guidance_cut_hits,
        "business_win_hits": positive_hits + guidance_raise_hits,
        "candidate_selection_score": round(score, 6),
        "signal_day_return_pct": round(signal_return * 100.0, 6),
        "signal_day_spy_return_pct": round(float(reaction["signal_day_spy_return"]) * 100.0, 6),
        "signal_day_excess_vs_spy_pct": round(excess_return * 100.0, 6),
        "min_signal_day_return_pct": MIN_SIGNAL_DAY_RETURN * 100.0,
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
        "positive_sec_text_price_alignment_replay_lead_requires_shared_adapter"
        if passed
        else "rejected_sec_text_price_alignment_issuer_continuation"
    )
    gate4["status"] = "observed_only" if passed else "rejected"
    gate4["requires_parity_before_promotion"] = passed
    gate4["rationale"] = (
        "The standalone SEC text-price alignment issuer-continuation replay "
        "passed Gate 4, but remains replay-only. Retention requires a shared "
        "default-off production/backtest adapter with the same next-session "
        "entry shift and parity tests."
        if passed
        else "One or more Gate 4 checks failed, so the standalone SEC text-price "
        "alignment issuer-continuation source is not retained."
    )
    return gate4


def _window_table(results: list[dict[str, Any]]) -> str:
    return parent._window_table(results)


def _write_artifact(payload: dict[str, Any]) -> None:
    comparison = payload["aggregate"]["comparison"]
    lines = [
        f"# {EXP_ID} SEC Text-Price Alignment Issuer Continuation",
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
        _window_table(payload["results"]),
        "",
        "## Gate 4 Checks",
        "",
    ]
    for key, value in payload["gate4"]["gates"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            "",
            "## Decision Rationale",
            "",
            payload["gate4"]["rationale"],
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
                "quant\\experiments\\exp_20260604_003_sec_text_price_alignment_issuer_continuation.py"
            ),
        ]
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _patch_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload["experiment_id"] = EXP_ID
    payload["trial_family"] = TRIAL_FAMILY
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["rule_version"] = RULE_VERSION
    payload["preflight"] = {
        "alpha_hypothesis": (
            "SEC high/medium credibility filings with positive filing text or "
            "earnings-release text plus positive signal-day reaction versus SPY "
            "may form a cleaner standalone issuer-continuation paper candidate "
            "pool than prior SEC demand-phrase and source-family variants."
        ),
        "category": "entry / candidate_pool",
        "playbook_alignment": (
            "Uses a free, production-visible SEC text and OHLCV alignment field "
            "from the playbook's text_price_alignment/modality-alignment backlog. "
            "It avoids LLM soft-ranking, source-family retuning, and adjacent SEC "
            "demand phrase variants."
        ),
        "nearby_prior_experiments": {
            "exp-20260603-017": (
                "SEC credible-reaction source-family improved all core windows "
                "but failed versus the accepted independent-source consensus "
                "comparator."
            ),
            "exp-20260603-012": (
                "SEC customer-demand text failed aggregate and window Gate 4; "
                "this run changes the causal variable to text-price alignment."
            ),
        },
        "single_causal_variable": CHANGED_VARIABLE,
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
                "a shared default-off production/backtest helper."
            ),
        },
        "reproducibility": (
            "The runner persists canonical before/after metrics, selected SEC "
            "text-price candidates, Gate 4 checks, ticket, card, artifact, and "
            "experiment_log.jsonl record."
        ),
    }
    payload["parameters"] = {
        "sec_text_path": parent._repo_rel(parent.SEC_TEXT_PATH),
        "event_notional": EVENT_NOTIONAL,
        "hold_days": parent.HOLD_DAYS,
        "max_paper_trades_per_day": parent.MAX_PAPER_TRADES_PER_DAY,
        "min_signal_day_return_pct": MIN_SIGNAL_DAY_RETURN * 100.0,
        "min_signal_day_excess_vs_spy_pct": MIN_SIGNAL_DAY_EXCESS_VS_SPY * 100.0,
        "credible_forms": ["10-K", "10-Q", "8-K item 2.02", "8-K item 2.05"],
        "text_alignment_rule": (
            "language_bucket=positive_language OR text_event_type=earnings_release_text "
            "OR guidance_raise_hits>0; exclude negative_language and guidance cuts"
        ),
        "entry_shift": "signal_date close reaction is known; paper entry uses next ticker trading-session open",
        "selection_order": "entry_date asc, candidate_selection_score desc, text positive hits desc, ticker asc",
    }
    payload["prediction"] = {
        "success_probability": 0.22,
        "expected_ev_delta": 0.18,
        "expected_pnl_delta": 3500.0,
        "main_failure_modes": [
            "window_regression",
            "thin_sample",
            "sec_text_noise",
            "concentration_failed",
        ],
        "confidence_reason": (
            "SEC credible-reaction rows improved all core windows in exp-20260603-017, "
            "but SEC demand text and source-family expansion failed; standalone "
            "text-price alignment may isolate the useful subset."
        ),
        "recorded_at": "2026-06-04T02:14:35Z",
    }
    payload["production_impact"] = PRODUCTION_IMPACT
    payload["llm_metrics"] = {
        "used_llm": False,
        "llm_change_scope": "none",
        "note": "No LLM soft-ranking was used because replay-safe LLM data remains sparse.",
    }
    payload["anti_js"] = "No JavaScript was used."
    payload["next_action"] = (
        "If positive, build a shared default-off SEC text-price alignment adapter "
        "with the same next-session entry shift and parity tests before promotion; "
        "if rejected, do not retune adjacent SEC text-price thresholds on this sample."
        if payload["gate4"]["passed"]
        else "Do not retune adjacent SEC text-price thresholds on this sample; move to a different free-data relation mechanism."
    )
    return payload


def main() -> int:
    _configure_parent()
    payload = parent.build_payload()
    payload = _patch_payload(payload)
    parent.persist(payload)
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
