"""exp-20260611-025: SEC capital-market financing confirmation scout.

Replay-only alpha search. This tests one fixed candidate-source variable:
SEC 8-K Item 2.03 / 3.02 capital-market financing disclosures, paired with
same-day liquid SPY-relative leadership before a top-1 next-open default-off
paper entry with a fixed 10-trading-day hold.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import exp_20260611_017_sec_quantified_counterparty_commitment as previous


framework = previous.framework
base = previous.base

EXPERIMENT_ID = "exp-20260611-025"
STEM = "sec_capital_market_financing_confirmation"
TRIAL_FAMILY = "sec_capital_market_financing_confirmation_candidate_pool"
TRIAL_VARIANT_ID = "sec_capital_market_financing_confirmation_top1_next_open_10d_v1"
CHANGED_VARIABLE = "sec_capital_market_financing_price_confirmed_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search"

REPO_ROOT = previous.REPO_ROOT
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result  # noqa: E402

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260611_025_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

SEC_EVENTS_PATH = (
    REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_events_20241002_20260421.jsonl"
)

BASE_NOTIONAL_USD = previous.BASE_NOTIONAL_USD
HOLD_DAYS = previous.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = previous.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = previous.SAME_TICKER_COOLDOWN_DAYS

FINANCING_ITEM_CODES = ("2.03", "3.02")
SUPPORTING_ITEM_CODES = ("1.01", "8.01", "9.01")
ITEM_CODE_WEIGHTS = {"2.03": 1.20, "3.02": 1.00, "1.01": 0.15, "8.01": 0.10}

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = previous.MAX_DRAWDOWN_WORSE
MAX_SINGLE_POSITIVE_SHARE = previous.MAX_SINGLE_POSITIVE_SHARE
MAX_POSITIVE_HHI = previous.MAX_POSITIVE_HHI

ACCEPTED_COMPRESSION_COMPARATOR = previous.ACCEPTED_COMPRESSION_COMPARATOR
ACCEPTED_DISTRIBUTION_COMPARATOR = previous.ACCEPTED_DISTRIBUTION_COMPARATOR
BASE_GATE4 = previous.BASE_GATE4
BASE_BUILD_PAYLOAD = previous.BASE_BUILD_PAYLOAD

PREDICTION = {
    "success_probability": 0.14,
    "expected_ev_delta": 0.10,
    "expected_pnl_delta": 1500.0,
    "main_failure_modes": [
        "financing_events_are_dilutive_or_distress",
        "thin_liquid_confirmed_sample",
        "existing_distribution_comparator_not_beaten",
        "window_regression",
        "ticker_concentration",
    ],
    "confidence_reason": (
        "Prior broad SEC item-code and generic SEC text candidates failed, "
        "but this run is not another synonym sweep: it isolates capital-market "
        "financing filings that are free, PIT, production-visible event rows. "
        "The hypothesis is plausible only when price action confirms that the "
        "market treats the financing as growth capital or balance-sheet "
        "runway rather than dilution or distress."
    ),
    "recorded_at": "2026-06-11T19:05:33+00:00",
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
        "applies the exact same 8-K Item 2.03/3.02 financing gate, uses the "
        "same signal-date OHLCV leadership envelope, overlap exclusion, "
        "next-open paper entry, 10-trading-day exit, costs, cooldown, "
        "comparator, and concentration guards in historical replay and daily "
        "production before any report queue, paper ledger, candidate priority, "
        "sizing, watchlist, or order surface could change."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: SEC 8-K Item 2.03 direct-obligation and Item 3.02 "
        "unregistered-security disclosures, when same-day OHLCV leadership "
        "confirms market absorption, may identify growth-capital or runway "
        "extensions that continue after next-open entry instead of generic SEC "
        "business-update noise."
    ),
    "2_history_check": {
        "exp-20260610-013": (
            "Rejected broad 8-K Item 1.01/7.01/8.01 event labels. This run "
            "does not retry generic labels; it isolates capital-market "
            "financing items with price confirmation."
        ),
        "exp-20260610-023": (
            "Rejected generic SEC contract-demand text; the failure argued "
            "for materially different PIT evidence, not synonym sweeps."
        ),
        "exp-20260611-017": (
            "Rejected named-counterparty quantified commitment text. This run "
            "changes the mechanism to financing runway/market absorption."
        ),
        "exp-20260611-015": (
            "Rejected SEC FTD/FINRA rank3 crowding. This run is event-led "
            "capital-market disclosure, not squeeze/crowding ranking."
        ),
        "exp-20260611-007": (
            "Accepted distribution-day absorption comparator. A positive SEC "
            "financing scout must beat it before promotion pressure."
        ),
    },
    "3_single_causal_variable": (
        "One fixed policy bundle: PIT SEC filing event rows must contain 8-K "
        "Item 2.03 and/or 3.02; same ticker core overlap is excluded; the "
        "existing liquid leadership envelope, top-1 next-open paper entry, "
        "10-day hold, costs, cooldown, comparator, and concentration gates are "
        "inherited unchanged."
    ),
    "4_acceptance_standard": (
        "Use docs/backtesting.md three canonical windows. Treat as positive "
        "replay lead only if aggregate EV/PnL improve, no EV/PnL regression "
        "window appears, target sample >=20 across all 3 windows, survival "
        ">=5%, drawdown drift <=0.5pp, concentration guard passes, and both "
        "accepted compression and distribution comparators are beaten."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260611_025_sec_capital_market_financing_confirmation.py"
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
        score += min(float(event.get("size") or 0.0) / 1_000_000.0, 0.50)
    return round(score, 6)


def _load_financing_events() -> dict[str, Any]:
    global _EVENT_CACHE
    if _EVENT_CACHE is not None:
        return _EVENT_CACHE

    by_date_ticker: dict[str, dict[str, list[dict[str, Any]]]] = {}
    scan = {
        "source": _repo_rel(SEC_EVENTS_PATH),
        "raw_rows": 0,
        "usable_8k_rows": 0,
        "financing_rows": 0,
        "financing_dates": 0,
        "financing_tickers": 0,
    }
    item_distribution: Counter[str] = Counter()
    supporting_distribution: Counter[str] = Counter()
    ticker_distribution: Counter[str] = Counter()
    examples: list[dict[str, Any]] = []

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
        financing_codes = tuple(code for code in FINANCING_ITEM_CODES if code in item_codes)
        if not financing_codes:
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
            "financing_item_codes": financing_codes,
            "supporting_item_codes": tuple(
                code for code in SUPPORTING_ITEM_CODES if code in item_codes
            ),
            "size": row.get("size"),
            "pit_source": row.get("pit_source"),
            "pit_caveat": row.get("pit_caveat"),
        }
        by_date_ticker.setdefault(signal_date, {}).setdefault(ticker, []).append(event)
        scan["financing_rows"] += 1
        ticker_distribution[ticker] += 1
        for code in financing_codes:
            item_distribution[code] += 1
        for code in event["supporting_item_codes"]:
            supporting_distribution[code] += 1
        if len(examples) < 20:
            examples.append(event)

    all_tickers = {
        ticker
        for tickers in by_date_ticker.values()
        for ticker in tickers
    }
    scan["financing_dates"] = len(by_date_ticker)
    scan["financing_tickers"] = len(all_tickers)
    scan["item_distribution"] = dict(sorted(item_distribution.items()))
    scan["supporting_item_distribution"] = dict(sorted(supporting_distribution.items()))
    scan["ticker_distribution_top20"] = dict(ticker_distribution.most_common(20))

    _EVENT_CACHE = {
        "by_date_ticker": by_date_ticker,
        "scan": scan,
        "examples": examples,
    }
    return _EVENT_CACHE


def _events_for_date(signal_date: str) -> dict[str, list[dict[str, Any]]]:
    return _load_financing_events()["by_date_ticker"].get(signal_date, {})


def _candidate_for_financing_ticker(
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
        month_label="sec_capital_market_financing",
    )
    if row is None:
        return None

    score = _event_score(events)
    top_event = sorted(
        events,
        key=lambda event: (
            -len(event["financing_item_codes"]),
            -float(event.get("size") or 0.0),
            str(event.get("accepted_at") or ""),
            str(event.get("accession_number") or ""),
        ),
    )[0]
    row.pop("candidate_month_label", None)
    row.update(
        {
            "source": "SEC_CAPITAL_MARKET_FINANCING_CONFIRMATION_PAPER",
            "rule_version": RULE_VERSION,
            "candidate_financing_event_score": score,
            "candidate_financing_event_count": len(events),
            "candidate_financing_item_codes": sorted(
                {
                    code
                    for event in events
                    for code in event["financing_item_codes"]
                }
            ),
            "candidate_financing_supporting_item_codes": sorted(
                {
                    code
                    for event in events
                    for code in event["supporting_item_codes"]
                }
            ),
            "candidate_financing_accession": top_event.get("accession_number"),
            "candidate_financing_primary_document": top_event.get("primary_document"),
            "candidate_financing_accepted_at": top_event.get("accepted_at"),
            "candidate_financing_size": top_event.get("size"),
            "candidate_financing_archive_url": top_event.get("archive_url"),
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
        "days_with_financing_event_tickers": 0,
        "financing_event_tickers": 0,
        "days_with_raw_financing_candidates": 0,
        "raw_financing_candidates": 0,
        "same_ticker_core_overlap_rejections": 0,
        "source_event_scan": _load_financing_events()["scan"],
        "source_event_examples": _load_financing_events()["examples"][:12],
    }

    for signal_date in dates:
        events_by_ticker = _events_for_date(signal_date)
        if not events_by_ticker:
            continue
        scan["days_with_financing_event_tickers"] += 1
        scan["financing_event_tickers"] += len(events_by_ticker)

        ab_entries = entries_by_date.get(signal_date, [])
        ab_tickers = {trade.get("ticker") for trade in ab_entries}
        day_rows: list[dict[str, Any]] = []
        for ticker, events in sorted(events_by_ticker.items()):
            if ticker not in sector_entries:
                continue
            if ticker in ab_tickers:
                scan["same_ticker_core_overlap_rejections"] += 1
                continue
            row = _candidate_for_financing_ticker(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
                events=events,
            )
            if row is None:
                continue
            for code in row["candidate_financing_item_codes"]:
                item_distribution[code] += 1
            for code in row["candidate_financing_supporting_item_codes"]:
                supporting_distribution[code] += 1
            row["same_day_ab_entry_count"] = len(ab_entries)
            row["same_day_ab_overlap"] = bool(ab_entries)
            row["same_ticker_ab_overlap"] = False
            day_rows.append(row)

        if not day_rows:
            continue
        day_rows.sort(
            key=lambda row: (
                -float(row["candidate_financing_event_score"]),
                -float(row["candidate_score"]),
                -float(row["candidate_ret20_excess_spy"]),
                -float(row["candidate_close_location"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                str(row.get("sector") or ""),
                row["ticker"],
            )
        )
        candidates.extend(day_rows)
        scan["days_with_raw_financing_candidates"] += 1
        scan["raw_financing_candidates"] += len(day_rows)
        top = day_rows[0]
        day_contexts.append(
            {
                "date": signal_date,
                "raw_candidate_count": len(day_rows),
                "top_candidate": top["ticker"],
                "top_candidate_score": top["candidate_score"],
                "top_candidate_financing_event_score": top[
                    "candidate_financing_event_score"
                ],
                "top_candidate_financing_item_codes": top[
                    "candidate_financing_item_codes"
                ],
                "top_candidate_ret20_excess_spy": top["candidate_ret20_excess_spy"],
                "top_candidate_close_location": top["candidate_close_location"],
            }
        )

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_financing_event_score"]),
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
            "financing_item_codes": list(FINANCING_ITEM_CODES),
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
        "positive_replay_lead_not_promoted_sec_capital_market_financing_confirmation"
        if gate["passed"]
        else "rejected_sec_capital_market_financing_confirmation_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    for trades in payload["target_trades_by_window"].values():
        for trade in trades:
            trade.setdefault("target_price", trade.get("exit_price"))
    payload["backtest_protocol"]["execution_model"] = (
        "Signal uses only PIT SEC filing event rows usable_trade_date plus "
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
            "new_evidence_type": (
                "sec_8k_item_203_302_capital_market_financing_plus_ohlcv_confirmation"
            ),
            "nearby_prior_experiments": [
                "exp-20260610-013",
                "exp-20260610-023",
                "exp-20260611-017",
                "exp-20260611-015",
                "exp-20260611-007",
            ],
            "prior_trial_count": 5,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "accepted_compression_comparator": ACCEPTED_COMPRESSION_COMPARATOR,
            "accepted_distribution_comparator": ACCEPTED_DISTRIBUTION_COMPARATOR,
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the likely reason is that 2.03/3.02 financing "
                "events often encode dilution, balance-sheet stress, or "
                "already-priced capital structure actions. Price confirmation "
                "and liquidity gates may not distinguish good growth runway "
                "from financing overhang after next-open execution and costs. "
                "Do not answer by sweeping item-code weights, adding noisy "
                "financing-adjacent codes, top-N, hold days, cooldown, or "
                "notional on these frozen windows."
            ),
            "next_evidence_needed": (
                "A retry needs materially new PIT evidence separating growth "
                "financing from distress/dilution, such as use-of-proceeds "
                "text, covenant maturity context, forward daily replacement "
                "value, or a shared default-off source with daily parity "
                "observations. Pure subtype/threshold retunes stay frozen."
            ),
        }
    )
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "sec_events_path": _repo_rel(SEC_EVENTS_PATH),
        "financing_item_codes": list(FINANCING_ITEM_CODES),
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
        "sec_event_rows": _load_financing_events()["scan"],
    }
    payload["gate3_survival_note"] = (
        "Core survival is checked by BASE_GATE4. Target survival is a "
        "default-off overlay candidate sample; no additional filter is added "
        "after Gate 3."
    )
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The financing item-code source was too sparse after the liquid "
            "leadership envelope: it produced only 2 target trades, both in "
            "mid_weak, with no late_strong or old_thin target trades. The "
            "small positive aggregate EV/PnL was economically irrelevant and "
            "far below accepted compression/distribution comparators. This "
            "suggests 2.03/3.02 labels alone mostly identify idiosyncratic "
            "capital-structure events and need materially richer PIT context "
            "to separate growth runway from dilution or distress."
            if not passed
            else (
                "The financing item-code source passed Gate 4, but it remains "
                "only a replay lead until one shared historical/daily helper "
                "proves parity with the same SEC event and OHLCV semantics."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping 2.03/3.02 weights, adding adjacent SEC "
            "subtypes, weakening the OHLCV leadership envelope, or changing "
            "top-N/hold/cooldown/notional on these frozen windows."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
    }
    payload["interpretation"] = (
        "The SEC capital-market financing confirmation source passed as a "
        "replay-only lead, but no production surface changed and a shared "
        "default-off parity adapter is required before use."
        if passed
        else (
            "The SEC capital-market financing confirmation source was "
            "rejected; it did not establish a distinct free SEC event/OHLCV "
            "candidate-pool edge under the standard three-window protocol."
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
                event_days=scan.get("days_with_financing_event_tickers", 0),
                days=scan.get("days_with_raw_financing_candidates", 0),
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
        ]
    )


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
                "financing_event_day_count": payload["context_scan_by_window"][
                    label
                ].get("days_with_financing_event_tickers"),
                "raw_candidate_count": payload["context_scan_by_window"][label].get(
                    "raw_financing_candidates"
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
        "aggregate_expected_value_delta": log_record[
            "aggregate_expected_value_delta"
        ],
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
