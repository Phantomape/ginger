"""exp-20260612-026: SEC auditor-change absorption candidate pool.

Replay-only alpha search. This tests one fixed candidate-source variable:
SEC 8-K Item 4.01 auditor/accountant change events, paired with the existing
same-day liquid leadership envelope before top-1 next-open paper entry and a
fixed 10-trading-day hold.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import exp_20260612_005_sec_periodic_filing_timing_surprise as previous


framework = previous.framework
base = previous.base

EXPERIMENT_ID = "exp-20260612-026"
STEM = "sec_auditor_change_absorption"
TRIAL_FAMILY = "sec_auditor_change_absorption_candidate_pool"
TRIAL_VARIANT_ID = "sec_auditor_change_absorption_top1_next_open_10d_v1"
CHANGED_VARIABLE = "sec_auditor_change_absorption_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = previous.REPO_ROOT
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result  # noqa: E402

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260612_026_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

SEC_EVENTS_PATH = previous.SEC_EVENTS_PATH

BASE_NOTIONAL_USD = previous.BASE_NOTIONAL_USD
HOLD_DAYS = previous.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = previous.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = previous.SAME_TICKER_COOLDOWN_DAYS

AUDITOR_ITEM_CODE = "4.01"
SUPPORTING_ITEM_CODES = ("9.01", "8.01")
ITEM_CODE_WEIGHTS = {"4.01": 1.00, "9.01": 0.10, "8.01": 0.05}

MIN_TARGET_TRADES = previous.MIN_TARGET_TRADES
MIN_TARGET_WINDOWS = previous.MIN_TARGET_WINDOWS
MAX_DRAWDOWN_WORSE = previous.MAX_DRAWDOWN_WORSE
MAX_SINGLE_POSITIVE_SHARE = previous.MAX_SINGLE_POSITIVE_SHARE
MAX_POSITIVE_HHI = previous.MAX_POSITIVE_HHI

ACCEPTED_COMPRESSION_COMPARATOR = previous.ACCEPTED_COMPRESSION_COMPARATOR
ACCEPTED_DISTRIBUTION_COMPARATOR = previous.ACCEPTED_DISTRIBUTION_COMPARATOR
BASE_GATE4 = previous.BASE_GATE4
BASE_BUILD_PAYLOAD = previous.BASE_BUILD_PAYLOAD

PREDICTION = {
    "success_probability": 0.08,
    "expected_ev_delta": 0.02,
    "expected_pnl_delta": 500.0,
    "main_failure_modes": [
        "thin_item_401_sample",
        "governance_event_noise",
        "accepted_comparator_not_beaten",
        "window_regression",
        "concentration_failed",
    ],
    "confidence_reason": (
        "Direct Item 4.01 has not been three-window tested, but prior SEC "
        "item/text candidates mostly failed and raw Item 4.01 coverage is "
        "sparse. This is a low-probability free/PIT semantic candidate-source "
        "check rather than a threshold retune."
    ),
    "recorded_at": "2026-06-12T23:17:58+00:00",
}

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
    "uses_llm": False,
    "uses_free_sec_filing_events": True,
    "uses_free_ohlcv": True,
    "parity_note": (
        "This experiment changes no production code. A positive result would "
        "remain only a replay lead. Promotion would require one shared "
        "default-off adapter that loads the same PIT SEC filing event rows, "
        "applies the exact same 8-K Item 4.01 auditor-change gate, uses the "
        "same signal-date OHLCV leadership envelope, same-ticker core overlap "
        "exclusion, next-open paper entry, 10-trading-day exit, costs, "
        "cooldown, comparator, and concentration guards in historical replay "
        "and daily production before any report queue, paper ledger, candidate "
        "priority, sizing, watchlist, or order surface could change."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: PIT SEC 8-K Item 4.01 auditor/accountant change "
        "events, when same-day OHLCV leadership confirms absorption, may "
        "identify governance-uncertainty events already accepted by the "
        "market and continuing after next-open entry."
    ),
    "2_history_check": {
        "direct_prior": (
            "No direct three-window Item 4.01 auditor-change replay was found. "
            "Item 4.01 appeared mainly as an exclusion/background code in SEC "
            "8-K experiments."
        ),
        "exp-20260610-013": (
            "Rejected broad 8-K Item 1.01/7.01/8.01 business update labels. "
            "This run does not retry generic business labels."
        ),
        "exp-20260610-023": (
            "Rejected SEC contract-demand text. This run uses no SEC text, "
            "LLM, counterparty, or synonym scoring."
        ),
        "exp-20260611-017": (
            "Rejected quantified counterparty commitment text. This run "
            "changes the mechanism to auditor-change absorption."
        ),
        "exp-20260611-025": (
            "Rejected SEC 2.03/3.02 capital-market financing confirmation. "
            "This run avoids financing/dilution event labels."
        ),
        "exp-20260612-005": (
            "Rejected SEC periodic filing timing. This run uses a different "
            "event semantic field, not periodic-report lag thresholds."
        ),
    },
    "3_single_causal_variable": (
        "One fixed policy bundle: PIT SEC filing event rows must contain 8-K "
        "Item 4.01; same ticker core overlap is excluded; the inherited "
        "liquid leadership envelope, top-1 next-open paper entry, 10-day hold, "
        "costs, cooldown, comparator, and concentration gates are unchanged."
    ),
    "4_acceptance_standard": (
        "Use docs/backtesting.md three canonical windows. Treat as positive "
        "replay lead only if aggregate EV/PnL improve, no material drawdown "
        "or survival degradation appears, target sample is adequate across "
        "the windows, concentration passes, and both accepted compression and "
        "distribution comparators are beaten."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260612_026_sec_auditor_change_absorption.py"
    ),
}

_EVENT_CACHE: dict[str, Any] | None = None


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _item_codes(row: dict[str, Any]) -> tuple[str, ...]:
    raw = row.get("eight_k_item_codes") or row.get("items_raw") or []
    if isinstance(raw, str):
        values = raw.replace(";", ",").split(",")
    else:
        values = list(raw)
    return tuple(sorted({str(value).strip() for value in values if str(value).strip()}))


def _event_score(events: list[dict[str, Any]]) -> float:
    score = 0.0
    for event in events:
        for code in event["item_codes"]:
            score += ITEM_CODE_WEIGHTS.get(code, 0.0)
    return round(score, 6)


def _load_auditor_events() -> dict[str, Any]:
    global _EVENT_CACHE
    if _EVENT_CACHE is not None:
        return _EVENT_CACHE

    by_date_ticker: dict[str, dict[str, list[dict[str, Any]]]] = {}
    scan = {
        "source": _repo_rel(SEC_EVENTS_PATH),
        "source_exists": SEC_EVENTS_PATH.exists(),
        "raw_rows": 0,
        "usable_8k_rows": 0,
        "auditor_change_rows": 0,
        "auditor_change_dates": 0,
        "auditor_change_tickers": 0,
    }
    item_distribution: Counter[str] = Counter()
    supporting_distribution: Counter[str] = Counter()
    ticker_distribution: Counter[str] = Counter()
    examples: list[dict[str, Any]] = []

    if not SEC_EVENTS_PATH.exists():
        _EVENT_CACHE = {"by_date_ticker": by_date_ticker, "scan": scan, "examples": []}
        return _EVENT_CACHE

    for line in SEC_EVENTS_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        scan["raw_rows"] += 1
        row = json.loads(line)
        if str(row.get("form_type") or "").upper() not in {"8-K", "8-K/A"}:
            continue
        if row.get("pit_safe_flag") is False:
            continue
        scan["usable_8k_rows"] += 1
        item_codes = _item_codes(row)
        if AUDITOR_ITEM_CODE not in item_codes:
            continue
        ticker = str(row.get("ticker") or "").upper().strip()
        signal_date = str(row.get("usable_trade_date") or row.get("filing_date") or "")
        if not ticker or not signal_date:
            continue

        event = {
            "ticker": ticker,
            "usable_trade_date": signal_date,
            "filing_date": row.get("filing_date"),
            "accepted_at": row.get("accepted_at"),
            "accession_number": row.get("accession_number"),
            "primary_document": row.get("primary_document"),
            "archive_url": row.get("archive_url"),
            "form_type": row.get("form_type"),
            "item_codes": item_codes,
            "supporting_item_codes": tuple(
                code for code in SUPPORTING_ITEM_CODES if code in item_codes
            ),
            "size": row.get("size"),
            "pit_source": row.get("pit_source"),
            "pit_caveat": row.get("pit_caveat"),
        }
        by_date_ticker.setdefault(signal_date, {}).setdefault(ticker, []).append(event)
        scan["auditor_change_rows"] += 1
        ticker_distribution[ticker] += 1
        for code in item_codes:
            item_distribution[code] += 1
        for code in event["supporting_item_codes"]:
            supporting_distribution[code] += 1
        if len(examples) < 20:
            examples.append(event)

    all_tickers = {ticker for tickers in by_date_ticker.values() for ticker in tickers}
    scan["auditor_change_dates"] = len(by_date_ticker)
    scan["auditor_change_tickers"] = len(all_tickers)
    scan["item_distribution"] = dict(sorted(item_distribution.items()))
    scan["supporting_item_distribution"] = dict(sorted(supporting_distribution.items()))
    scan["ticker_distribution_top20"] = dict(ticker_distribution.most_common(20))

    _EVENT_CACHE = {"by_date_ticker": by_date_ticker, "scan": scan, "examples": examples}
    return _EVENT_CACHE


def _events_for_date(signal_date: str) -> dict[str, list[dict[str, Any]]]:
    return _load_auditor_events()["by_date_ticker"].get(signal_date, {})


def _candidate_for_auditor_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    events: list[dict[str, Any]],
) -> dict[str, Any] | None:
    row = base._candidate_for_ticker(
        snapshot=snapshot,
        indices=indices,
        sector_entries=sector_entries,
        ticker=ticker,
        signal_date=signal_date,
        month_label="sec_auditor_change_absorption",
    )
    if row is None:
        return None

    top_event = sorted(
        events,
        key=lambda event: (
            -_event_score([event]),
            str(event.get("accepted_at") or ""),
            str(event.get("accession_number") or ""),
        ),
    )[0]
    row.pop("candidate_month_label", None)
    row.update(
        {
            "source": "SEC_AUDITOR_CHANGE_ABSORPTION_PAPER",
            "rule_version": RULE_VERSION,
            "candidate_auditor_event_count": len(events),
            "candidate_auditor_event_score": _event_score(events),
            "candidate_auditor_item_codes": top_event["item_codes"],
            "candidate_auditor_supporting_item_codes": top_event[
                "supporting_item_codes"
            ],
            "candidate_auditor_filing_date": top_event.get("filing_date"),
            "candidate_auditor_accepted_at": top_event.get("accepted_at"),
            "candidate_auditor_accession": top_event.get("accession_number"),
            "candidate_auditor_primary_document": top_event.get("primary_document"),
            "candidate_auditor_archive_url": top_event.get("archive_url"),
            "uses_free_sec_filing_events": True,
            "uses_free_ohlcv": True,
            "uses_free_ohlcv_only": False,
            "known_at": "signal_date_sec_event_and_ohlcv_before_next_open_paper_entry",
        }
    )
    return row


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = framework.shadow._baseline_entries(before_result)
    indices = {
        ticker: framework.shadow._row_index(framework.shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    dates = [
        date_value
        for date_value in framework.shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    candidates: list[dict[str, Any]] = []
    day_contexts: list[dict[str, Any]] = []
    item_distribution: Counter[str] = Counter()
    supporting_distribution: Counter[str] = Counter()
    scan = {
        "scanned_trading_days": len(dates),
        "days_with_auditor_event_tickers": 0,
        "auditor_event_tickers": 0,
        "days_with_raw_auditor_candidates": 0,
        "raw_auditor_candidates": 0,
        "same_ticker_core_overlap_rejections": 0,
        "source_event_scan": _load_auditor_events()["scan"],
        "source_event_examples": _load_auditor_events()["examples"][:12],
    }

    for signal_date in dates:
        events_by_ticker = _events_for_date(signal_date)
        if not events_by_ticker:
            continue
        scan["days_with_auditor_event_tickers"] += 1
        scan["auditor_event_tickers"] += len(events_by_ticker)

        ab_entries = entries_by_date.get(signal_date, [])
        ab_tickers = {trade.get("ticker") for trade in ab_entries}
        day_rows: list[dict[str, Any]] = []
        for ticker, events in sorted(events_by_ticker.items()):
            if ticker not in sector_entries:
                continue
            if ticker in ab_tickers:
                scan["same_ticker_core_overlap_rejections"] += 1
                continue
            row = _candidate_for_auditor_ticker(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
                events=events,
            )
            if row is None:
                continue
            for code in row["candidate_auditor_item_codes"]:
                item_distribution[code] += 1
            for code in row["candidate_auditor_supporting_item_codes"]:
                supporting_distribution[code] += 1
            row["same_day_ab_entry_count"] = len(ab_entries)
            row["same_day_ab_overlap"] = bool(ab_entries)
            row["same_ticker_ab_overlap"] = False
            day_rows.append(row)

        if not day_rows:
            continue
        day_rows.sort(
            key=lambda row: (
                -float(row["candidate_auditor_event_score"]),
                -float(row["candidate_score"]),
                -float(row["candidate_ret20_excess_spy"]),
                -float(row["candidate_close_location"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                str(row.get("sector") or ""),
                row["ticker"],
            )
        )
        candidates.extend(day_rows)
        scan["days_with_raw_auditor_candidates"] += 1
        scan["raw_auditor_candidates"] += len(day_rows)
        top = day_rows[0]
        day_contexts.append(
            {
                "date": signal_date,
                "raw_candidate_count": len(day_rows),
                "top_candidate": top["ticker"],
                "top_candidate_score": top["candidate_score"],
                "top_candidate_auditor_event_score": top[
                    "candidate_auditor_event_score"
                ],
                "top_candidate_item_codes": top["candidate_auditor_item_codes"],
                "top_candidate_ret20_excess_spy": top["candidate_ret20_excess_spy"],
                "top_candidate_close_location": top["candidate_close_location"],
            }
        )

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_auditor_event_score"]),
            -float(row["candidate_score"]),
            -float(row["candidate_ret20_excess_spy"]),
            -float(row["candidate_close_location"]),
            -float(row["candidate_avg_dollar_volume_20d"]),
            str(row.get("sector") or ""),
            row["ticker"],
        )
    )
    scan.update(
        {
            "rule_version": RULE_VERSION,
            "auditor_item_code": AUDITOR_ITEM_CODE,
            "supporting_item_codes": list(SUPPORTING_ITEM_CODES),
            "item_code_weights": ITEM_CODE_WEIGHTS,
            "item_distribution": dict(sorted(item_distribution.items())),
            "supporting_item_distribution": dict(sorted(supporting_distribution.items())),
            "min_price": base.MIN_PRICE,
            "min_avg_dollar_volume_20d": base.MIN_AVG_DOLLAR_VOLUME_20D,
            "min_ret20_excess_spy": base.MIN_RET20_EXCESS_SPY,
            "min_ret60_excess_spy": base.MIN_RET60_EXCESS_SPY,
            "min_signal_return": base.MIN_SIGNAL_RETURN,
            "min_close_location": base.MIN_CLOSE_LOCATION,
            "min_volume_ratio_20d": base.MIN_VOLUME_RATIO_20D,
            "max_volume_ratio_20d": base.MAX_VOLUME_RATIO_20D,
            "min_ret5": base.MIN_RET5,
            "max_ret5": base.MAX_RET5,
            "max_ret20": base.MAX_RET20,
            "max_realized_vol_20d": base.MAX_REALIZED_VOL_20D,
        }
    )
    return candidates, day_contexts, scan


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = BASE_GATE4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    if aggregate["expected_value_score_delta_sum"] <= ACCEPTED_COMPRESSION_COMPARATOR[
        "expected_value_score_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append("accepted_compression_ev_not_beaten")
    if aggregate["total_pnl_delta_sum"] <= ACCEPTED_COMPRESSION_COMPARATOR[
        "total_pnl_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append("accepted_compression_pnl_not_beaten")
    if aggregate["expected_value_score_delta_sum"] <= ACCEPTED_DISTRIBUTION_COMPARATOR[
        "expected_value_score_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append("accepted_distribution_ev_not_beaten")
    if aggregate["total_pnl_delta_sum"] <= ACCEPTED_DISTRIBUTION_COMPARATOR[
        "total_pnl_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append("accepted_distribution_pnl_not_beaten")
    gate["accepted_compression_comparator"] = ACCEPTED_COMPRESSION_COMPARATOR
    gate["accepted_distribution_comparator"] = ACCEPTED_DISTRIBUTION_COMPARATOR
    gate["passed"] = not gate.get("failed_reasons")
    gate["decision"] = (
        "positive_replay_lead_not_promoted_sec_auditor_change_absorption"
        if gate["passed"]
        else "rejected_sec_auditor_change_absorption_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    for trades in payload["target_trades_by_window"].values():
        for trade in trades:
            trade.setdefault("target_price", trade.get("exit_price"))
    payload["backtest_protocol"]["execution_model"] = (
        "Signal uses only PIT SEC filing event rows with 8-K Item 4.01 plus "
        "close-of-day OHLCV available on the signal date. Paper entry is next "
        "available open with existing entry slippage; exit is the close 10 "
        "trading days after the signal with target-side sell slippage and "
        "ROUND_TRIP_COST_PCT."
    )
    passed = bool(payload["gate4"]["passed"])
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": "positive_replay_lead_not_promoted" if passed else "rejected",
            "decision": payload["gate4"]["decision"],
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "default_off_paper_candidate_pool_replay_scout",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_sec_event_ohlcv_candidate_pool",
            "new_evidence_type": "sec_8k_item_401_auditor_change_event_plus_ohlcv_confirmation",
            "nearby_prior_experiments": [
                "exp-20260610-013",
                "exp-20260610-023",
                "exp-20260611-017",
                "exp-20260611-025",
                "exp-20260612-005",
            ],
            "prior_trial_count": 5,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "accepted_compression_comparator": ACCEPTED_COMPRESSION_COMPARATOR,
            "accepted_distribution_comparator": ACCEPTED_DISTRIBUTION_COMPARATOR,
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the likely reason is that auditor-change events "
                "are too sparse and context-dependent. Item 4.01 alone cannot "
                "separate routine auditor changes, governance stress, and "
                "already-priced uncertainty after next-open execution and "
                "costs. Do not answer by sweeping top-N, hold days, cooldown, "
                "notional, or adjacent SEC item codes on these frozen windows."
            ),
            "next_evidence_needed": (
                "A retry needs materially new PIT evidence that distinguishes "
                "benign auditor transitions from adverse resignations, such "
                "as Item 4.01 disagreement/resignation text, EX-16 wording, "
                "forward daily replacement value, or a shared default-off "
                "adapter with closed paper outcomes. Pure item-code retunes "
                "stay frozen."
            ),
        }
    )
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "sec_events_path": _repo_rel(SEC_EVENTS_PATH),
        "auditor_item_code": AUDITOR_ITEM_CODE,
        "supporting_item_codes": list(SUPPORTING_ITEM_CODES),
        "item_code_weights": ITEM_CODE_WEIGHTS,
        "min_price": base.MIN_PRICE,
        "min_avg_dollar_volume_20d": base.MIN_AVG_DOLLAR_VOLUME_20D,
        "min_ret20_excess_spy": base.MIN_RET20_EXCESS_SPY,
        "min_ret60_excess_spy": base.MIN_RET60_EXCESS_SPY,
        "min_signal_return": base.MIN_SIGNAL_RETURN,
        "min_close_location": base.MIN_CLOSE_LOCATION,
        "min_volume_ratio_20d": base.MIN_VOLUME_RATIO_20D,
        "max_volume_ratio_20d": base.MAX_VOLUME_RATIO_20D,
        "min_ret5": base.MIN_RET5,
        "max_ret5": base.MAX_RET5,
        "max_ret20": base.MAX_RET20,
        "max_realized_vol_20d": base.MAX_REALIZED_VOL_20D,
        "same_ticker_core_overlap_excluded": True,
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["gate_questions"] = PRE_RUN_QUESTIONS
    payload["pre_run_questions"] = PRE_RUN_QUESTIONS
    payload["gate2_runtime_fields"] = {
        "entry_date": "verified_in_overlay_target_trades",
        "target_price": "verified_in_overlay_target_trades",
        "sec_events_path_exists": SEC_EVENTS_PATH.exists(),
        "sec_event_rows": _load_auditor_events()["scan"],
        "required_sec_fields": [
            "ticker",
            "form_type",
            "eight_k_item_codes",
            "filing_date",
            "accepted_at",
            "usable_trade_date",
            "pit_safe_flag",
        ],
    }
    payload["gate3_survival_note"] = (
        "Core survival is checked by BASE_GATE4. Target survival is a "
        "default-off overlay candidate sample; no live/core filter is added."
    )
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The SEC auditor-change source passed Gate 4, but it remains only "
            "a replay lead until one shared historical/daily helper proves "
            "parity with the same SEC event and OHLCV semantics."
            if passed
            else (
                "The Item 4.01 source did not clear Gate 4. The source scan "
                "shows the free PIT event field is extremely sparse across "
                "the standard windows, and the surviving price-confirmed "
                "sample is not large enough to establish a standalone "
                "candidate-pool edge against accepted free-data comparators."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by adding adjacent SEC item codes, weakening the "
            "OHLCV leadership gate, or changing top-N/hold/notional/cooldown "
            "on these frozen windows."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
    }
    payload["interpretation"] = (
        "The SEC auditor-change absorption source passed as a replay-only "
        "lead, but no production surface changed and a shared default-off "
        "parity adapter is required before use."
        if passed
        else (
            "The SEC auditor-change absorption source was rejected; it did "
            "not establish a distinct free SEC event/OHLCV candidate-pool edge "
            "under the standard three-window protocol."
        )
    )
    payload["rejection_reason"] = (
        None if passed else "; ".join(payload["gate4"]["failed_reasons"])
    )
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Event days | Candidate days | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {event_days} | {days} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                event_days=scan.get("days_with_auditor_event_tickers", 0),
                days=scan.get("days_with_raw_auditor_candidates", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} {STEM}",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Status: `{payload['status']}`",
            f"- Trial family: `{TRIAL_FAMILY}`",
            f"- Changed variable: `{CHANGED_VARIABLE}`",
            f"- Artifact: `{_repo_rel(OUT_JSON)}`",
            f"- Log: `{_repo_rel(LOG_JSON)}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## History Check",
            "",
            json.dumps(PRE_RUN_QUESTIONS["2_history_check"], ensure_ascii=False, indent=2),
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
            "- Target trades: `{}`".format(
                payload["target_trade_summary"]["total_trade_count"]
            ),
            "- Accepted distribution comparator EV/PnL: `{}` / `${:,.2f}`".format(
                ACCEPTED_DISTRIBUTION_COMPARATOR["expected_value_score_delta_sum"],
                ACCEPTED_DISTRIBUTION_COMPARATOR["total_pnl_delta_sum"],
            ),
            "- Gate 4 failures: `{}`".format(payload["gate4"]["failed_reasons"]),
            "",
            "## Production Impact",
            "",
            json.dumps(PRODUCTION_IMPACT, ensure_ascii=False, indent=2),
            "",
            "## Reflection",
            "",
            json.dumps(payload["post_run_reflection"], ensure_ascii=False, indent=2),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": (
            "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
        ),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate[
            "expected_value_score_delta_pct"
        ],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "accepted_compression_comparator": ACCEPTED_COMPRESSION_COMPARATOR,
        "accepted_distribution_comparator": ACCEPTED_DISTRIBUTION_COMPARATOR,
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_after": payload["after_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][
                    label
                ]["total_pnl"],
                "auditor_event_day_count": payload["context_scan_by_window"][
                    label
                ].get("days_with_auditor_event_tickers"),
                "raw_candidate_count": payload["context_scan_by_window"][label].get(
                    "raw_auditor_candidates"
                ),
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": {**payload["calibration"]},
        "production_impact": PRODUCTION_IMPACT,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "negative_reflection": payload["negative_reflection"],
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _update_ticket_and_registry(
    payload: dict[str, Any],
    log_record: dict[str, Any],
) -> None:
    aggregate = payload["delta_metrics"]["aggregate"]
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
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
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
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
            _repo_rel(Path(__file__)): framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): framework._sha256(CARD_MD),
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def _patch_framework() -> None:
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.RULE_VERSION = RULE_VERSION
    framework.EXPERIMENT_ID = EXPERIMENT_ID
    framework.STEM = STEM
    framework.TRIAL_FAMILY = TRIAL_FAMILY
    framework.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    framework.CHANGED_VARIABLE = CHANGED_VARIABLE
    framework.RULE_VERSION = RULE_VERSION
    framework.OUT_DIR = OUT_DIR
    framework.OUT_JSON = OUT_JSON
    framework.LOG_JSON = LOG_JSON
    framework.TICKET_JSON = TICKET_JSON
    framework.CARD_MD = CARD_MD
    framework.MANIFEST_JSON = MANIFEST_JSON
    framework.EXPERIMENT_LOG = EXPERIMENT_LOG
    framework.REGISTRY_JSON = REGISTRY_JSON
    framework.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    framework.HOLD_DAYS = HOLD_DAYS
    framework.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    framework.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    framework.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    framework.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    framework.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    framework.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    framework.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    framework.PREDICTION = PREDICTION
    framework.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._gate4 = _gate4
    framework._build_payload = _build_payload
    framework._build_card = _build_card
    framework._build_log_record = _build_log_record
    framework._update_ticket_and_registry = _update_ticket_and_registry
    framework._write_manifest = _write_manifest


_patch_framework()


def main() -> None:
    framework.main()


if __name__ == "__main__":
    main()
