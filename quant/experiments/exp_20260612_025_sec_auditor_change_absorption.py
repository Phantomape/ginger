"""exp-20260612-025: SEC auditor-change absorption candidate pool.

Replay-only alpha search. This tests one fixed candidate-source variable:
PIT SEC 8-K Item 4.01 auditor/accountant change event rows, paired with the
existing same-day liquid leadership envelope, before top-1 next-open
default-off paper entry with a fixed 10-trading-day hold.

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

EXPERIMENT_ID = "exp-20260612-025"
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
OUT_JSON = OUT_DIR / "exp_20260612_025_sec_auditor_change_absorption.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

SEC_EVENTS_PATH = previous.SEC_EVENTS_PATH
WAREHOUSE_PATH = Path(framework.WAREHOUSE).resolve()
WAREHOUSE_IMMUTABLE_URI = f"file:{WAREHOUSE_PATH.as_posix()}?immutable=1&mode=ro"
ORIGINAL_SQLITE_CONNECT = framework.sqlite3.connect

BASE_NOTIONAL_USD = previous.BASE_NOTIONAL_USD
HOLD_DAYS = previous.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = previous.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = previous.SAME_TICKER_COOLDOWN_DAYS

AUDITOR_ITEM_CODE = "4.01"
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
        "Direct Item 4.01 has not been three-window tested; however prior SEC "
        "item/text candidates mostly failed and raw Item 4.01 coverage appears "
        "very sparse, so this is a low-probability but free/PIT semantic "
        "candidate-source check rather than a threshold retune."
    ),
    "recorded_at": "2026-06-12T23:16:58+00:00",
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
        "This experiment changes no production code. A positive result remains "
        "only a replay lead. Promotion would require one shared default-off "
        "adapter that loads the same PIT SEC filing event rows, applies the "
        "same Item 4.01 auditor/accountant-change gate, signal-date OHLCV "
        "leadership envelope, overlap exclusion, next-open paper entry, "
        "10-trading-day exit, costs, cooldown, comparator, and concentration "
        "guards in historical replay and daily production before any report "
        "queue, paper ledger, candidate priority, sizing, watchlist, or order "
        "surface could change."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: SEC 8-K Item 4.01 auditor/accountant change events, "
        "only when same-day liquid leadership confirms absorption, may signal "
        "governance uncertainty already resolved by price and produce "
        "next-open continuation beyond generic SEC event noise."
    ),
    "2_history_check": {
        "exp-20260610-013": (
            "Rejected broad SEC business-update labels; this run uses the "
            "explicit Item 4.01 event code rather than broad 7.01/8.01 text."
        ),
        "exp-20260610-023": (
            "Rejected generic SEC contract-demand text; this run is not a "
            "customer-contract synonym or text-score retry."
        ),
        "exp-20260611-017": (
            "Rejected quantified counterparty commitment with zero target rows; "
            "this run uses filing-event taxonomy only, no named-counterparty text."
        ),
        "exp-20260611-025": (
            "Rejected SEC capital-market financing confirmation; auditor-change "
            "events are governance/accounting uncertainty, not financing item codes."
        ),
        "exp-20260612-005": (
            "Rejected SEC periodic filing timing surprise with only 4 trades. "
            "This run tests a different discrete 8-K event rather than filing-lag timing."
        ),
    },
    "3_single_causal_variable": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Gate 1-4 per docs/backtesting.md on late_strong, mid_weak, and "
        "old_thin. Aggregate EV/PnL must be positive, drawdown/survival cannot "
        "materially worsen, target sample and concentration must pass, and "
        "accepted compression/distribution candidate-source comparators must be "
        "beaten. A positive replay result is not accepted for production until "
        "shared-helper parity exists."
    ),
    "5_reproducibility": (
        ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260612_025_sec_auditor_change_absorption.py"
    ),
}

_EVENT_CACHE: dict[str, Any] | None = None


def _sqlite_connect(database: Any, *args: Any, **kwargs: Any) -> Any:
    """Open the current broad warehouse read-only when a hot journal is present."""

    try:
        requested = Path(database).resolve()
    except (TypeError, ValueError):
        requested = None
    if requested == WAREHOUSE_PATH:
        kwargs["uri"] = True
        return ORIGINAL_SQLITE_CONNECT(WAREHOUSE_IMMUTABLE_URI, *args, **kwargs)
    return ORIGINAL_SQLITE_CONNECT(database, *args, **kwargs)


def _repo_rel(path: Path | str) -> str:
    path = Path(path)
    try:
        return str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _item_codes(row: dict[str, Any]) -> set[str]:
    raw = row.get("eight_k_item_codes") or row.get("item_codes")
    if isinstance(raw, list):
        return {str(item).strip() for item in raw if str(item).strip()}
    if raw:
        return {
            part.strip()
            for part in str(raw).replace(";", ",").split(",")
            if part.strip()
        }
    return set()


def _auditor_score(row: dict[str, Any]) -> float:
    codes = _item_codes(row)
    score = 1.0
    if "9.01" in codes:
        score += 0.10
    if row.get("accepted_at"):
        score += 0.05
    if row.get("primary_document"):
        score += 0.05
    return round(score, 6)


def _load_auditor_events() -> dict[str, Any]:
    global _EVENT_CACHE
    if _EVENT_CACHE is not None:
        return _EVENT_CACHE

    by_date_ticker: dict[str, dict[str, list[dict[str, Any]]]] = {}
    item_distribution: Counter[str] = Counter()
    ticker_distribution: Counter[str] = Counter()
    examples: list[dict[str, Any]] = []
    scan = {
        "source_path": _repo_rel(SEC_EVENTS_PATH),
        "source_exists": SEC_EVENTS_PATH.exists(),
        "raw_rows": 0,
        "eight_k_rows": 0,
        "pit_safe_eight_k_rows": 0,
        "item_401_rows": 0,
        "missing_ticker_or_usable_date_rows": 0,
    }
    if not SEC_EVENTS_PATH.exists():
        _EVENT_CACHE = {"by_date_ticker": by_date_ticker, "scan": scan, "examples": []}
        return _EVENT_CACHE

    for line in SEC_EVENTS_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        scan["raw_rows"] += 1
        row = json.loads(line)
        form = str(row.get("form_base") or row.get("form_type") or "").upper()
        if "8-K" not in form:
            continue
        scan["eight_k_rows"] += 1
        if row.get("pit_safe_flag") is not True:
            continue
        scan["pit_safe_eight_k_rows"] += 1
        codes = _item_codes(row)
        for code in codes:
            item_distribution[code] += 1
        if AUDITOR_ITEM_CODE not in codes:
            continue
        ticker = str(row.get("ticker") or "").upper().strip()
        signal_date = str(row.get("usable_trade_date") or "")[:10]
        if not ticker or not signal_date:
            scan["missing_ticker_or_usable_date_rows"] += 1
            continue
        event = {
            **row,
            "ticker": ticker,
            "usable_trade_date": signal_date,
            "item_codes": sorted(codes),
            "auditor_event_score": _auditor_score(row),
            "rule_version": RULE_VERSION,
        }
        by_date_ticker.setdefault(signal_date, {}).setdefault(ticker, []).append(event)
        ticker_distribution[ticker] += 1
        scan["item_401_rows"] += 1
        if len(examples) < 12:
            examples.append(
                {
                    "usable_trade_date": signal_date,
                    "ticker": ticker,
                    "accepted_at": row.get("accepted_at"),
                    "accession_number": row.get("accession_number"),
                    "primary_document": row.get("primary_document"),
                    "item_codes": sorted(codes),
                }
            )

    scan["item_distribution_top20"] = dict(item_distribution.most_common(20))
    scan["ticker_distribution_top20"] = dict(ticker_distribution.most_common(20))
    _EVENT_CACHE = {
        "by_date_ticker": by_date_ticker,
        "scan": scan,
        "examples": examples,
    }
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
            -float(event.get("auditor_event_score") or 0.0),
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
            "candidate_auditor_event_score": top_event["auditor_event_score"],
            "candidate_auditor_item_codes": top_event["item_codes"],
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
                item_distribution[str(code)] += 1
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
            "item_distribution_after_ohlcv_confirmation": dict(
                sorted(item_distribution.items())
            ),
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
    gate["failed_reasons"] = list(dict.fromkeys(gate.get("failed_reasons") or []))
    gate["passed"] = not gate["failed_reasons"]
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
        "Signal uses only PIT SEC filing event rows with Item 4.01 plus "
        "close-of-day OHLCV available on the signal date. Paper entry is next "
        "available open with existing entry slippage; exit is the close 10 "
        "trading days after the signal with target-side sell slippage and "
        "ROUND_TRIP_COST_PCT."
    )
    passed = bool(payload["gate4"]["passed"])
    aggregate = payload["delta_metrics"]["aggregate"]
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
                "If rejected, the likely reason is that Item 4.01 is too "
                "sparse, too governance-noisy, or mostly attached to already "
                "crowded crypto/data-center tickers; same-day price leadership "
                "does not turn the accounting-change event into a reliable "
                "10-day replacement-value source."
            ),
            "next_evidence_needed": (
                "A valid retry needs materially richer PIT auditor-change "
                "provenance, such as resignation versus dismissal, adverse "
                "opinion/disagreement extraction, auditor quality change, "
                "restatement linkage, or closed forward replacement-value rows "
                "from a shared daily adapter. Do not sweep OHLCV thresholds on "
                "this frozen sample."
            ),
        }
    )
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "warehouse_path": _repo_rel(WAREHOUSE_PATH),
        "warehouse_open_mode": "sqlite_immutable_mode_ro_hot_journal_safe",
        "sec_events_path": _repo_rel(SEC_EVENTS_PATH),
        "auditor_item_code": AUDITOR_ITEM_CODE,
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
        "warehouse_read_mode": "immutable=1&mode=ro",
        "sec_events_path_exists": SEC_EVENTS_PATH.exists(),
        "sec_event_rows": _load_auditor_events()["scan"],
        "required_sec_fields": [
            "ticker",
            "form_base",
            "filing_date",
            "accepted_at",
            "usable_trade_date",
            "pit_safe_flag",
            "eight_k_item_codes",
        ],
    }
    payload["gate3_survival_note"] = (
        "Core survival is checked by BASE_GATE4. Target survival is a "
        "default-off overlay candidate sample; no live/core filter is added."
    )
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The SEC auditor-change absorption source passed Gate 4, but it "
            "remains only a replay lead until one shared historical/daily "
            "helper proves parity with the same SEC event and OHLCV semantics."
            if passed
            else (
                "The SEC auditor-change absorption source did not clear the "
                "canonical Gate 4 bar. Item 4.01 coverage was very sparse in "
                "the PIT event ledger, and the same-day OHLCV leadership "
                "envelope did not produce enough robust target trades to beat "
                "accepted compression/distribution comparators."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping auditor Item 4.01 raw event filters, "
            "same-day ret20/ret60, volume, close-location, top-N, hold-day, "
            "cooldown, or notional on these frozen windows."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
    }
    payload["interpretation"] = (
        "The SEC auditor-change absorption source passed as a replay-only lead, "
        "but no production surface changed and a shared default-off parity "
        "adapter is required before use."
        if passed
        else (
            "The SEC auditor-change absorption source was rejected; it did not "
            "establish a distinct free SEC event/OHLCV candidate-pool edge "
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
            f"# {EXPERIMENT_ID} SEC Auditor Change Absorption",
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
    framework.sqlite3.connect = _sqlite_connect
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
