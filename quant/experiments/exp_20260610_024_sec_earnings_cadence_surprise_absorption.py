"""exp-20260610-024: SEC earnings cadence surprise absorption candidate pool.

Replay-only alpha search. This tests one fixed candidate-source variable:
SEC 8-K Item 2.02 earnings releases that arrive after a long issuer-specific
quiet period and are absorbed by same-day liquid leadership before a top-1
next-open default-off paper entry with a fixed 10-trading-day hold.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import exp_20260610_023_sec_contract_demand_text_leadership as previous


framework = previous.framework
base = previous.base

EXPERIMENT_ID = "exp-20260610-024"
STEM = "sec_earnings_cadence_surprise_absorption"
TRIAL_FAMILY = "sec_earnings_cadence_surprise_absorption_candidate_pool"
TRIAL_VARIANT_ID = "sec_earnings_cadence_surprise_absorption_top1_next_open_10d_v1"
CHANGED_VARIABLE = "sec_earnings_cadence_surprise_absorption_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "codex-alpha-search"

REPO_ROOT = previous.REPO_ROOT
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result  # noqa: E402

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260610_024_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

SEC_TEXT_PATH = (
    REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_text_20241002_20260421.jsonl"
)

BASE_NOTIONAL_USD = previous.BASE_NOTIONAL_USD
HOLD_DAYS = previous.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = previous.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = previous.SAME_TICKER_COOLDOWN_DAYS

ITEM_CODE_REQUIRED = "2.02"
MIN_CADENCE_GAP_DAYS = 70
MIN_TEXT_WORD_COUNT = 2_000

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = previous.MAX_DRAWDOWN_WORSE
MAX_SINGLE_POSITIVE_SHARE = previous.MAX_SINGLE_POSITIVE_SHARE
MAX_POSITIVE_HHI = previous.MAX_POSITIVE_HHI

ACCEPTED_COMPRESSION_COMPARATOR = previous.ACCEPTED_COMPRESSION_COMPARATOR
BASE_GATE4 = previous.BASE_GATE4
BASE_BUILD_PAYLOAD = previous.BASE_BUILD_PAYLOAD

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.12,
    "expected_pnl_delta": 2500.0,
    "main_failure_modes": [
        "post_earnings_near_neighbor_no_incremental_edge",
        "mapped_sample_too_small",
        "old_thin_drawdown_regression",
        "sec_text_replay_proxy_not_production_ready",
    ],
    "confidence_reason": (
        "The field is free and PIT-keyed with 232 mapped SEC 8-K rows across "
        "three windows, and cadence/timing is distinct from prior SEC phrase "
        "and payload tests. Confidence remains low because all rows are "
        "earnings-release related and prior SEC text candidate pools have been "
        "noisy or sample-limited."
    ),
    "recorded_at": "2026-06-10T22:11:36+00:00",
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
    "uses_free_sec_filing_text": True,
    "uses_free_ohlcv": True,
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead. Promotion would require a shared default-off adapter "
        "that loads the same PIT SEC filing text rows, applies the exact same "
        "Item 2.02, issuer cadence gap, text completeness, signal-date OHLCV "
        "absorption gates, overlap exclusion, next-open paper entry, 10-trading-"
        "day exit, costs, cooldown, comparator, and concentration guards in "
        "historical replay and daily production before any report queue, paper "
        "ledger, candidate priority, sizing, watchlist, or order surface could "
        "change."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: SEC 8-K Item 2.02 earnings releases after a long "
        "issuer-specific filing cadence gap, when paired with same-day liquid "
        "SPY-relative price and volume absorption, may identify low-information-"
        "flow earnings underreaction candidates for next-open 10d paper drift."
    ),
    "2_history_check": {
        "exp-20260602-026": (
            "Accepted post-earnings underpriced shared adapter; it did not use "
            "SEC filing cadence/timing surprise as the candidate source."
        ),
        "exp-20260609-012": (
            "Rejected SEC large filing payload price absorption; 164 filing rows "
            "could not map to the replay price map, and payload size alone was "
            "not alpha evidence."
        ),
        "exp-20260610-023": (
            "Rejected SEC contract-demand text leadership; only two mapped "
            "trades survived, so semantic phrase evidence was sparse/noisy."
        ),
        "history_search": (
            "No prior filing cadence/timing surprise experiment was found in "
            "experiment_log.jsonl, experiments/logs, or quant/experiments."
        ),
    },
    "3_single_causal_variable": (
        "One fixed policy bundle: PIT SEC 8-K text rows, Item 2.02 required, "
        "same issuer prior SEC text usable_trade_date gap >=70 calendar days, "
        "minimum filing text word count, existing liquid sector-known stock "
        "universe and OHLCV leadership/absorption gates, same-ticker core-overlap "
        "exclusion, top-1 next-open paper entry, 10-day hold, cost, cooldown, "
        "and concentration gates."
    ),
    "4_acceptance_standard": (
        "Use docs/backtesting.md three canonical windows. Treat as positive "
        "replay lead only if aggregate EV/PnL improve, no EV/PnL regression "
        "window appears, target sample >=20 across all 3 windows, survival >=5%, "
        "drawdown drift <=0.5pp, concentration guard passes, and exp-20260608-013 "
        "accepted compression comparator is beaten. Production retention still "
        "requires a shared default-off helper."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260610_024_sec_earnings_cadence_surprise_absorption.py"
    ),
}

_EVENT_CACHE: dict[str, Any] | None = None


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _date10(value: Any) -> str:
    return str(value or "")[:10]


def _item_codes(row: dict[str, Any]) -> set[str]:
    raw = row.get("eight_k_item_codes")
    if isinstance(raw, list):
        return {str(item).strip() for item in raw if str(item).strip()}
    if raw:
        return {
            part.strip()
            for part in str(raw).replace(";", ",").split(",")
            if part.strip()
        }
    return set()


def _date_gap_days(current_date: str, previous_date: str | None) -> int | None:
    if not current_date or not previous_date:
        return None
    try:
        return (date.fromisoformat(current_date) - date.fromisoformat(previous_date)).days
    except ValueError:
        return None


def _load_cadence_events() -> dict[str, Any]:
    global _EVENT_CACHE
    if _EVENT_CACHE is not None:
        return _EVENT_CACHE

    by_ticker: dict[str, list[dict[str, Any]]] = {}
    scan = Counter()
    if not SEC_TEXT_PATH.exists():
        _EVENT_CACHE = {
            "by_date_ticker": {},
            "scan": {"text_file_missing": True, "path": _repo_rel(SEC_TEXT_PATH)},
            "examples": [],
        }
        return _EVENT_CACHE

    with SEC_TEXT_PATH.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            if not line.strip():
                continue
            scan["text_rows_loaded"] += 1
            row = json.loads(line)
            ticker = str(row.get("ticker") or "").upper().strip()
            usable_date = _date10(row.get("usable_trade_date") or row.get("filing_date"))
            form_type = str(row.get("form_type") or row.get("form_base") or "").upper()
            if not ticker or not usable_date:
                scan["missing_ticker_or_date"] += 1
                continue
            if str(row.get("status") or "ok").lower() not in {"ok", ""}:
                scan["status_rejected"] += 1
                continue
            if "8-K" not in form_type:
                scan["non_8k_rejected"] += 1
                continue
            scan["eight_k_rows"] += 1
            item_codes = sorted(_item_codes(row))
            if ITEM_CODE_REQUIRED not in item_codes:
                scan["missing_item_202"] += 1
                continue
            scan["item_202_rows"] += 1
            word_count = int(row.get("text_word_count") or 0)
            if word_count < MIN_TEXT_WORD_COUNT:
                scan["short_text_rejected"] += 1
                continue
            by_ticker.setdefault(ticker, []).append(
                {
                    "ticker": ticker,
                    "usable_trade_date": usable_date,
                    "filing_date": _date10(row.get("filing_date")),
                    "accepted_at": row.get("accepted_at"),
                    "accession_number": row.get("accession_number"),
                    "primary_document": row.get("primary_document"),
                    "form_type": form_type,
                    "item_codes": item_codes,
                    "documents_fetched": row.get("documents_fetched"),
                    "text_word_count": word_count,
                    "text_char_count": row.get("text_char_count"),
                    "source_text_hash": hashlib.sha256(
                        str(row.get("combined_text") or "").encode(
                            "utf-8", errors="ignore"
                        )
                    ).hexdigest()[:16],
                    "pit_source": row.get("pit_source"),
                    "pit_caveat": row.get("pit_caveat"),
                }
            )

    by_date_ticker: dict[str, dict[str, list[dict[str, Any]]]] = {}
    examples: list[dict[str, Any]] = []
    gap_distribution = Counter()
    for ticker, rows in by_ticker.items():
        rows.sort(
            key=lambda event: (
                event["usable_trade_date"],
                str(event.get("accepted_at") or ""),
                str(event.get("accession_number") or ""),
            )
        )
        previous_usable: str | None = None
        for event in rows:
            gap = _date_gap_days(event["usable_trade_date"], previous_usable)
            event["prior_usable_trade_date"] = previous_usable
            event["cadence_gap_days"] = gap
            if gap is None:
                scan["first_seen_rejected_left_censored"] += 1
            elif gap < MIN_CADENCE_GAP_DAYS:
                scan["cadence_gap_too_short"] += 1
            else:
                scan["cadence_gap_passed_rows"] += 1
                gap_distribution[str(min((gap // 10) * 10, 180))] += 1
                by_date_ticker.setdefault(event["usable_trade_date"], {}).setdefault(
                    ticker, []
                ).append(event)
                if len(examples) < 12:
                    examples.append(
                        {
                            "date": event["usable_trade_date"],
                            "ticker": ticker,
                            "cadence_gap_days": gap,
                            "prior_usable_trade_date": previous_usable,
                            "item_codes": event["item_codes"],
                            "text_word_count": event["text_word_count"],
                            "accession_number": event["accession_number"],
                        }
                    )
            previous_usable = event["usable_trade_date"]

    _EVENT_CACHE = {
        "by_date_ticker": by_date_ticker,
        "scan": {
            **dict(scan),
            "source_text_file": _repo_rel(SEC_TEXT_PATH),
            "min_cadence_gap_days": MIN_CADENCE_GAP_DAYS,
            "min_text_word_count": MIN_TEXT_WORD_COUNT,
            "required_item_code": ITEM_CODE_REQUIRED,
            "ticker_count_after_item_202": len(by_ticker),
            "gap_distribution_10d_floor": dict(sorted(gap_distribution.items())),
        },
        "examples": examples,
    }
    return _EVENT_CACHE


def _events_for_date(signal_date: str) -> dict[str, list[dict[str, Any]]]:
    return _load_cadence_events()["by_date_ticker"].get(signal_date, {})


def _candidate_for_cadence_ticker(
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
        month_label="sec_earnings_cadence_surprise",
    )
    if row is None:
        return None

    top_event = sorted(
        events,
        key=lambda event: (
            -int(event.get("cadence_gap_days") or 0),
            -int(event.get("text_word_count") or 0),
            str(event.get("accession_number") or ""),
        ),
    )[0]
    gap_days = int(top_event.get("cadence_gap_days") or 0)
    cadence_score = (
        min(gap_days / 90.0, 1.75)
        + min(float(top_event.get("text_word_count") or 0) / 8_000.0, 0.75)
        + float(row.get("candidate_score") or 0.0)
    )
    row["source"] = "SEC_EARNINGS_CADENCE_SURPRISE_ABSORPTION_PAPER"
    row.pop("candidate_month_label", None)
    row["candidate_cadence_score"] = round(cadence_score, 6)
    row["candidate_cadence_gap_days"] = gap_days
    row["candidate_prior_sec_text_usable_trade_date"] = top_event.get(
        "prior_usable_trade_date"
    )
    row["candidate_sec_text_word_count"] = top_event.get("text_word_count")
    row["candidate_sec_text_char_count"] = top_event.get("text_char_count")
    row["candidate_sec_text_item_codes"] = top_event.get("item_codes")
    row["candidate_sec_text_accession"] = top_event.get("accession_number")
    row["candidate_sec_text_primary_document"] = top_event.get("primary_document")
    row["candidate_sec_text_source_hash"] = top_event.get("source_text_hash")
    row["candidate_sec_text_pit_source"] = top_event.get("pit_source")
    row["candidate_cadence_event_count"] = len(events)
    row["uses_free_ohlcv_only"] = False
    row["uses_free_sec_filing_text"] = True
    row["known_at"] = "signal_date_sec_filing_cadence_and_ohlcv_before_next_open_paper_entry"
    row["rule_version"] = RULE_VERSION
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
    all_dates = framework.shadow._trading_dates(snapshot)
    dates = [
        date_value
        for date_value in all_dates
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    candidates: list[dict[str, Any]] = []
    day_contexts: list[dict[str, Any]] = []
    gap_bucket_distribution: Counter[str] = Counter()
    item_distribution: Counter[str] = Counter()
    scan = {
        "scanned_trading_days": len(dates),
        "days_with_cadence_event_tickers": 0,
        "cadence_event_tickers": 0,
        "days_with_raw_cadence_candidates": 0,
        "raw_cadence_candidates": 0,
        "same_ticker_core_overlap_rejections": 0,
        "source_text_scan": _load_cadence_events()["scan"],
        "source_text_examples": _load_cadence_events()["examples"][:12],
    }

    for signal_date in dates:
        events_by_ticker = _events_for_date(signal_date)
        if not events_by_ticker:
            continue
        scan["days_with_cadence_event_tickers"] += 1
        scan["cadence_event_tickers"] += len(events_by_ticker)

        ab_entries = entries_by_date.get(signal_date, [])
        ab_tickers = {trade.get("ticker") for trade in ab_entries}
        day_rows: list[dict[str, Any]] = []
        for ticker, events in sorted(events_by_ticker.items()):
            if ticker not in sector_entries:
                scan["sector_missing_rejections"] = (
                    scan.get("sector_missing_rejections", 0) + 1
                )
                continue
            if ticker in ab_tickers:
                scan["same_ticker_core_overlap_rejections"] += 1
                continue
            row = _candidate_for_cadence_ticker(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
                events=events,
            )
            if row is None:
                scan["ohlcv_absorption_gate_rejections"] = (
                    scan.get("ohlcv_absorption_gate_rejections", 0) + 1
                )
                continue
            gap_bucket_distribution[str(min((row["candidate_cadence_gap_days"] // 10) * 10, 180))] += 1
            for item_code in row.get("candidate_sec_text_item_codes") or []:
                item_distribution[item_code] += 1
            row["same_day_ab_entry_count"] = len(ab_entries)
            row["same_day_ab_overlap"] = bool(ab_entries)
            row["same_ticker_ab_overlap"] = False
            day_rows.append(row)
        if not day_rows:
            continue
        day_rows.sort(
            key=lambda row: (
                -float(row["candidate_cadence_score"]),
                -float(row["candidate_score"]),
                -int(row["candidate_cadence_gap_days"]),
                -float(row["candidate_ret20_excess_spy"]),
                -float(row["candidate_close_location"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                str(row.get("sector") or ""),
                row["ticker"],
            )
        )
        candidates.extend(day_rows)
        scan["days_with_raw_cadence_candidates"] += 1
        scan["raw_cadence_candidates"] += len(day_rows)
        top = day_rows[0]
        day_contexts.append(
            {
                "date": signal_date,
                "raw_candidate_count": len(day_rows),
                "top_candidate": top["ticker"],
                "top_candidate_score": top["candidate_score"],
                "top_candidate_cadence_score": top["candidate_cadence_score"],
                "top_candidate_cadence_gap_days": top["candidate_cadence_gap_days"],
                "top_candidate_ret20_excess_spy": top["candidate_ret20_excess_spy"],
                "top_candidate_close_location": top["candidate_close_location"],
            }
        )
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_cadence_score"]),
            -float(row["candidate_score"]),
            -int(row["candidate_cadence_gap_days"]),
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
            "required_item_code": ITEM_CODE_REQUIRED,
            "min_cadence_gap_days": MIN_CADENCE_GAP_DAYS,
            "min_text_word_count": MIN_TEXT_WORD_COUNT,
            "gap_bucket_distribution_10d_floor": dict(
                sorted(gap_bucket_distribution.items())
            ),
            "item_distribution": dict(sorted(item_distribution.items())),
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
    gate["accepted_compression_comparator"] = ACCEPTED_COMPRESSION_COMPARATOR
    gate["passed"] = not gate.get("failed_reasons")
    gate["decision"] = (
        "positive_replay_lead_not_promoted_sec_earnings_cadence_surprise_absorption"
        if gate["passed"]
        else "rejected_sec_earnings_cadence_surprise_absorption_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    payload["backtest_protocol"]["execution_model"] = (
        "Signal uses only PIT SEC 8-K text usable_trade_date rows plus "
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
            "mechanism_family": "production_visible_sec_event_timing_alpha",
            "new_evidence_type": (
                "production_visible_sec_earnings_filing_cadence_gap_x_price_absorption_field"
            ),
            "nearby_prior_experiments": [
                "exp-20260602-026",
                "exp-20260609-012",
                "exp-20260610-023",
            ],
            "prior_trial_count": 4,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "accepted_compression_comparator": ACCEPTED_COMPRESSION_COMPARATOR,
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the likely reason is that SEC earnings cadence "
                "surprise is still a near-neighbor of post-earnings drift and "
                "does not add enough replacement value once next-open execution, "
                "costs, liquid leadership, cooldown, and overlap controls are "
                "imposed. Do not answer by sweeping cadence-day thresholds, "
                "word-count thresholds, RS gates, top-N, hold-day, cooldown, "
                "or notional on these frozen windows without materially new "
                "PIT evidence such as actual-estimate surprise, guidance "
                "direction, named customer relation, or forward source-utility "
                "labels."
            ),
            "next_evidence_needed": (
                "A retry needs materially richer PIT event evidence: filing "
                "time relative to earnings calendar, reported surprise versus "
                "estimates, guidance direction, or a source-utility ledger that "
                "shows which earnings filing cadence buckets beat the displaced "
                "candidate after costs."
            ),
        }
    )
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "sec_text_path": _repo_rel(SEC_TEXT_PATH),
        "required_item_code": ITEM_CODE_REQUIRED,
        "min_cadence_gap_days": MIN_CADENCE_GAP_DAYS,
        "min_text_word_count": MIN_TEXT_WORD_COUNT,
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
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The fixed SEC earnings cadence surprise absorption bundle cleared "
            "the canonical three-window gates and beat the accepted compression "
            "comparator, suggesting low-disclosure-flow earnings releases plus "
            "same-day absorption added replacement value. It remains only a "
            "replay lead because no shared daily adapter or production parity "
            "path was added."
            if passed
            else (
                "The fixed SEC earnings cadence surprise absorption bundle "
                "failed Gate 4. That means cadence/timing alone did not create "
                "a stable edge beyond existing post-earnings and OHLCV helpers "
                "after next-open execution, costs, 10-day hold, cooldown, "
                "overlap controls, and accepted compression comparison. The "
                "useful next evidence is richer earnings information, not a "
                "cadence or price-threshold sweep."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping cadence-gap days, word-count thresholds, "
            "Item 2.02 subsets, ret20/ret60 relative-strength thresholds, "
            "signal-day return, close-location, volume-ratio bounds, top-N, "
            "hold-day, cooldown, or paper notional on the same frozen windows."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
    }
    payload["interpretation"] = (
        "The SEC earnings cadence surprise absorption source passed as a replay-"
        "only promotion lead, but no production surface changed and a shared "
        "default-off parity adapter is required before use."
        if passed
        else (
            "The SEC earnings cadence surprise absorption source was rejected; "
            "it did not establish a distinct free SEC timing/OHLCV candidate-"
            "pool edge under the standard three-window protocol."
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
                event_days=scan.get("days_with_cadence_event_tickers", 0),
                days=scan.get("days_with_raw_cadence_candidates", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} SEC Earnings Cadence Surprise Absorption",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
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
            "- Comparator EV/PnL: `{}` / `${:,.2f}`".format(
                ACCEPTED_COMPRESSION_COMPARATOR["expected_value_score_delta_sum"],
                ACCEPTED_COMPRESSION_COMPARATOR["total_pnl_delta_sum"],
            ),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "",
            "## Production Impact",
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
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
        "mechanism_family": "production_visible_sec_event_timing_alpha",
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
                "cadence_event_day_count": payload["context_scan_by_window"][label].get(
                    "days_with_cadence_event_tickers"
                ),
                "raw_candidate_count": payload["context_scan_by_window"][label].get(
                    "raw_cadence_candidates"
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
