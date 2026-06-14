"""exp-20260614-009: SEC financial-report allocator source extension.

Alpha search on one fixed policy bundle: admit SEC financial-report positive
T+1 drift rows as a rank-2 source family inside the accepted source-priority
allocator, replayed under the allocator's fixed top-1/day, $4k notional,
10-trading-day paper envelope.

This is intentionally replay-only. The SEC financial-report standalone sleeve
uses a different notional/capacity surface, so a positive result here is only a
lead until the shared allocator helper and daily source snapshot expose the
same source rows. No live/default orders, core signal generation, sizing,
exits, watchlists, LLM, or news path are changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from copy import deepcopy
from pathlib import Path
from typing import Any

import exp_20260611_005_lagged_consensus_shared_allocator_source as accepted

framework = accepted.framework
exp008 = accepted.exp008

REPO_ROOT = accepted.REPO_ROOT
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for entry in (str(REPO_ROOT), str(QUANT_ROOT), str(SCRIPTS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import accepted_helper_source_priority_allocator_paper_sleeve as allocator  # noqa: E402
import constants  # noqa: E402
import fill_model  # noqa: E402
from data_layer import get_universe  # noqa: E402
from exp_20260511_112_sec_financial_report_t1_sleeve_capacity import (  # noqa: E402
    _load_exp100,
    _rows_by_t1_date,
)
from exp_20260512_002_sec_financial_report_hold_days import (  # noqa: E402
    _filter_current_queue,
)
from sec_event_queue import (  # noqa: E402
    FINANCIAL_REPORT_T1_MIN_EXCESS_RETURN_VS_SPY,
    FINANCIAL_REPORT_T1_RULE_VERSION,
)
from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260614-009"
STEM = "sec_financial_report_allocator_source_extension"
OWNER = "codex-alpha-search"
TRIAL_FAMILY = "accepted_default_off_helper_source_priority_allocation"
TRIAL_VARIANT_ID = "sec_financial_report_t1_drift_rank2_source_family_added_to_allocator_v1"
CHANGED_VARIABLE = (
    "sec_financial_report_t1_drift_source_family_added_to_accepted_helper_"
    "source_priority_allocator_v1"
)
SEC_SOURCE_FAMILY = "sec_financial_report_t1_drift"
SEC_SOURCE_RULE_VERSION = "sec_financial_report_t1_drift_allocator_signal_10d_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260614_009_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

BASE_NOTIONAL_USD = allocator.BASE_NOTIONAL_USD
HOLD_DAYS = allocator.HOLD_DAYS
MAX_DRAWDOWN_WORSE = 0.005
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MIN_CHANGED_SELECTIONS = 9
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

ACCEPTED_ALLOCATOR_COMPARATOR = {
    "experiment_id": "exp-20260611-005",
    "aggregate_ev_delta": 2.1849,
    "aggregate_pnl_delta": 40397.21,
    "window_deltas": {
        "late_strong": {"ev": 0.9092, "pnl": 9431.68},
        "mid_weak": {"ev": 0.6352, "pnl": 11133.95},
        "old_thin": {"ev": 0.6405, "pnl": 19831.58},
    },
}

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.12,
    "expected_pnl_delta": 2500.0,
    "main_failure_modes": [
        "accepted_allocator_window_comparator_regression",
        "source_overlap_displaces_better_rows",
        "sec_event_not_incremental_after_lagged_consensus",
        "drawdown_drift",
    ],
    "confidence_reason": (
        "SEC financial-report T+1 drift has accepted standalone support and "
        "uses free PIT SEC filings, but source-extension attempts often fail "
        "after lagged consensus by displacing better rows."
    ),
    "recorded_at": "2026-06-14T07:29:42+00:00",
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool/allocation: SEC financial-report positive T+1 drift "
        "may add distinct free event-information replacement value when "
        "admitted as a fixed rank-2 source inside the accepted allocator."
    ),
    "2_history_check": {
        "exp-20260614-004": (
            "Accepted standalone SEC financial-report RS20 notional support; "
            "this run does not retune that scalar and instead tests allocator "
            "source admission under the allocator $4k envelope."
        ),
        "exp-20260611-005": (
            "Current accepted allocator with lagged consensus rank 1; aggregate "
            "EV +2.1849 and PnL +$40,397.21 is the binding comparator."
        ),
        "exp-20260611-008": (
            "Distribution source extension was positive versus core but failed "
            "after accepted allocator comparison."
        ),
        "exp-20260611-015": (
            "SEC FTD+FINRA source extension failed the accepted allocator "
            "comparator despite positive core-relative EV."
        ),
        "exp-20260613-012": (
            "Alpha-score source extension failed the accepted allocator "
            "comparator; do not retune source priority or score fields."
        ),
        "exp-20260610-016/019": (
            "Post-earnings and Fundamental Growth RS source-family admissions "
            "were already rejected as allocator extensions."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. The variant must "
        "improve direct EV/PnL versus the same-run accepted allocator in all "
        "three windows, beat exp-20260611-005 aggregate and per-window EV/PnL "
        "comparators versus core, and pass sample/survival/drawdown/"
        "concentration guards. A positive replay is not accepted until shared "
        "daily allocator helper parity is implemented."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260614_009_sec_financial_report_allocator_source_extension.py"
    ),
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_sec_financial_report_allocator_source_scout",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "default_off_paper_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "uses_llm": False,
    "uses_free_ohlcv_only": False,
    "uses_free_non_ohlcv": True,
    "live_realism_evaluated": True,
    "live_ready": False,
    "execution_envelope": {
        "base_notional": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "daily_entry_slots": allocator.MAX_PAPER_TRADES_PER_DAY,
        "max_concurrent": allocator.EXECUTION_ENVELOPE["max_concurrent_positions"],
        "same_ticker_cooldown_days": allocator.SAME_TICKER_COOLDOWN_DAYS,
        "order_semantics": "next_open_paper_only_no_orders_emitted",
        "kill_switch_drawdown_pct": allocator.EXECUTION_ENVELOPE[
            "kill_switch_drawdown_pct"
        ],
    },
    "parity_note": (
        "Replay-only source-extension scout. SEC source rows are rebuilt from "
        "the existing financial-report positive T+1 queue and replayed under "
        "the accepted allocator's $4k, 10-day envelope. No shared allocator "
        "helper or run.py source snapshot is changed unless Gate 4 passes and "
        "the behavior is promoted through shared daily parity."
    ),
}


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _round(value: Any, digits: int = 6) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _row_value(row: dict[str, Any], key: str) -> float | None:
    raw = row.get(key)
    if raw is None:
        raw = row.get(key.lower())
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _safe(payload: Any) -> Any:
    return framework._safe(payload)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _load_window_snapshot_from_json(
    *,
    cfg: dict[str, str],
    eligible_tickers: set[str],
) -> dict[str, list[dict[str, Any]]]:
    payload = json.loads((REPO_ROOT / cfg["snapshot"]).read_text(encoding="utf-8-sig"))
    allowed = {str(ticker).upper() for ticker in eligible_tickers} | {"SPY", "QQQ"}
    out: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in (payload.get("ohlcv") or {}).items():
        symbol = str(ticker).upper()
        if symbol not in allowed:
            continue
        normalised = []
        for row in rows or []:
            date_value = str(row.get("Date") or row.get("date") or "")[:10]
            if not date_value:
                continue
            normalised.append(
                {
                    "Date": date_value,
                    "Open": _float(row.get("Open") if row.get("Open") is not None else row.get("open")),
                    "High": _float(row.get("High") if row.get("High") is not None else row.get("high")),
                    "Low": _float(row.get("Low") if row.get("Low") is not None else row.get("low")),
                    "Close": _float(row.get("Close") if row.get("Close") is not None else row.get("close")),
                    "Volume": _float(row.get("Volume") if row.get("Volume") is not None else row.get("volume")),
                }
            )
        if normalised:
            out[symbol] = normalised
    return out


def _candidate_universe_from_sector_entries(
    sector_entries: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "status": "window_sector_known_universe",
        "tickers": sorted(sector_entries),
        "records": sector_entries,
    }


def _source_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(str(row.get("source_family") or "unknown") for row in rows))


def _row_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("signal_date") or row.get("date") or "")[:10],
        str(row.get("ticker") or "").upper(),
        str(row.get("source_family") or "unknown"),
    )


def _extended_source_priority() -> OrderedDict[str, dict[str, Any]]:
    out: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for source_family, meta in allocator.SOURCE_PRIORITY.items():
        if source_family == "lagged_cross_source_consensus":
            out[source_family] = dict(meta)
            out[SEC_SOURCE_FAMILY] = {
                "rank": 2,
                "description": (
                    "SEC financial-report positive T+1 drift source, replayed "
                    "under allocator 10-day envelope"
                ),
                "accepted_experiment": "exp-20260614-004",
                "accepted_ev_delta_sum": 0.158184,
                "accepted_pnl_delta_sum": 3235.38,
            }
            continue
        shifted = dict(meta)
        shifted["rank"] = int(meta["rank"]) + 1
        out[source_family] = shifted
    return out


def _with_source_priority(priority: OrderedDict[str, dict[str, Any]], fn):
    old_priority = allocator.SOURCE_PRIORITY
    allocator.SOURCE_PRIORITY = priority
    try:
        return fn()
    finally:
        allocator.SOURCE_PRIORITY = old_priority


def _avg_dollar_volume_20(rows: list[dict[str, Any]], idx: int) -> float | None:
    start = max(0, idx - 19)
    samples: list[float] = []
    for row in rows[start : idx + 1]:
        close = _row_value(row, "Close")
        volume = _row_value(row, "Volume")
        if close is None or volume is None or close <= 0 or volume <= 0:
            continue
        samples.append(float(close) * float(volume))
    if not samples:
        return None
    return sum(samples) / len(samples)


def _paper_trade_10d_from_sec_candidate(
    snapshot: dict[str, list[dict[str, Any]]],
    candidate: dict[str, Any],
) -> dict[str, Any] | None:
    ticker = str(candidate.get("ticker") or "").upper()
    signal_date = str(candidate.get("t1_date") or candidate.get("event_trading_date") or "")[:10]
    rows = snapshot.get(ticker) or []
    row_index = {str(row.get("Date") or "")[:10]: idx for idx, row in enumerate(rows)}
    idx = row_index.get(signal_date)
    if idx is None:
        return None
    entry_idx = idx + 1
    exit_idx = idx + HOLD_DAYS
    if entry_idx >= len(rows) or exit_idx >= len(rows):
        return None
    entry_raw = _row_value(rows[entry_idx], "Open")
    exit_raw = _row_value(rows[exit_idx], "Close")
    if entry_raw is None or exit_raw is None or entry_raw <= 0:
        return None
    entry_price = fill_model.apply_entry_fill(entry_raw)
    exit_price = fill_model.apply_slippage(
        exit_raw,
        bps=fill_model.SLIPPAGE_BPS_TARGET,
        side="sell",
    )
    pnl_pct_net = (
        (exit_price / entry_price)
        - 1.0
        - constants.ROUND_TRIP_COST_PCT
    )
    pnl = BASE_NOTIONAL_USD * pnl_pct_net
    t1_excess = _float(candidate.get("t1_excess_return_vs_spy"))
    return {
        "date": signal_date,
        "signal_date": signal_date,
        "ticker": ticker,
        "source_family": SEC_SOURCE_FAMILY,
        "source_rule_version": SEC_SOURCE_RULE_VERSION,
        "source_score": _round(t1_excess, 6),
        "candidate_score": _round(t1_excess, 6),
        "entry_date": str(rows[entry_idx].get("Date") or "")[:10],
        "exit_date": str(rows[exit_idx].get("Date") or "")[:10],
        "entry_raw_open": _round(entry_raw, 4),
        "exit_raw_close": _round(exit_raw, 4),
        "entry_price": _round(entry_price, 4),
        "exit_price": _round(exit_price, 4),
        "hold_days": HOLD_DAYS,
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "notional_usd": BASE_NOTIONAL_USD,
        "pnl_pct_net": _round(pnl_pct_net, 6),
        "pnl": _round(pnl, 2),
        "paper_status": "closed",
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
        "trade_enabled": False,
        "alters_orders": False,
        "uses_free_non_ohlcv": True,
        "sec_queue_rule_version": FINANCIAL_REPORT_T1_RULE_VERSION,
        "sec_queue_min_t1_excess_vs_spy": FINANCIAL_REPORT_T1_MIN_EXCESS_RETURN_VS_SPY,
        "event_family": candidate.get("event_family"),
        "form_base": candidate.get("form_base"),
        "form_type": candidate.get("form_type"),
        "accession_number": candidate.get("accession_number"),
        "accepted_at": candidate.get("accepted_at"),
        "source_event_date": candidate.get("usable_trade_date"),
        "t1_date": candidate.get("t1_date"),
        "t1_return": _round(candidate.get("t1_return"), 6),
        "spy_t1_return": _round(candidate.get("spy_t1_return"), 6),
        "t1_excess_return_vs_spy": _round(candidate.get("t1_excess_return_vs_spy"), 6),
        "candidate_avg_dollar_volume_20d": _round(_avg_dollar_volume_20(rows, idx), 2),
        "source_experiment": "exp-20260511-100",
    }


def _build_sec_source_trades(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    dates: list[str],
    window_label: str,
    window_payload: dict[str, Any],
    core_entries_by_date: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_t1 = _rows_by_t1_date(window_payload)
    date_set = set(dates)
    selected: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    raw_candidate_count = 0
    for signal_date in dates:
        core_tickers = {
            str(row.get("ticker") or "").upper()
            for row in core_entries_by_date.get(signal_date, [])
        }
        for candidate in by_t1.get(signal_date, []):
            raw_candidate_count += 1
            ticker = str(candidate.get("ticker") or "").upper()
            if signal_date not in date_set:
                filtered.append({**candidate, "filter_reason": "outside_window"})
                continue
            if ticker in core_tickers:
                filtered.append({**candidate, "filter_reason": "same_ticker_core_overlap"})
                continue
            trade = _paper_trade_10d_from_sec_candidate(snapshot, candidate)
            if trade is None:
                filtered.append({**candidate, "filter_reason": "missing_next_open_or_exit"})
                continue
            selected.append(trade)
    return selected, {
        "rule_version": SEC_SOURCE_RULE_VERSION,
        "source_from": "exp-20260511-100 filtered financial-report positive T+1 queue",
        "window": window_label,
        "candidate_count": raw_candidate_count,
        "selected_trade_count": len(selected),
        "filtered_count": len(filtered),
        "filtered_reasons": dict(
            Counter(str(row.get("filter_reason") or "unknown") for row in filtered)
        ),
        "selected_event_family_counts": dict(
            Counter(str(row.get("event_family") or "unknown") for row in selected)
        ),
    }


def _select_extended_rows(
    *,
    source_rows: list[dict[str, Any]],
    trading_dates: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    priority = _extended_source_priority()

    def _run():
        return allocator.select_accepted_helper_source_priority_rows(
            source_rows=source_rows,
            trading_dates=trading_dates,
            config=None,
            create_trades=True,
        )

    selected, filtered, audit = _with_source_priority(priority, _run)
    audit["source_priority"] = priority
    audit["rank2_source_family"] = SEC_SOURCE_FAMILY
    return selected, filtered, audit


def _target_summary(rows_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    return framework.sleeve._target_trade_summary(rows_by_window)


def _top5_positive_share(target_summary: dict[str, Any]) -> float | None:
    positive = target_summary.get("positive_by_ticker_pnl") or {}
    total = sum(float(value) for value in positive.values())
    if total <= 0.0:
        return None
    top5 = sum(sorted((float(value) for value in positive.values()), reverse=True)[:5])
    return round(top5 / total, 6)


def _gate4(
    *,
    aggregate_vs_core: dict[str, Any],
    aggregate_vs_accepted: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
    core_to_extended_rows: OrderedDict[str, dict[str, Any]],
    accepted_to_extended_rows: OrderedDict[str, dict[str, Any]],
    changed_selection_count: int,
) -> dict[str, Any]:
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    failed: list[str] = []
    direct_ev = float(aggregate_vs_accepted["expected_value_score_delta_sum"] or 0.0)
    direct_pnl = float(aggregate_vs_accepted["total_pnl_delta_sum"] or 0.0)
    if direct_ev <= 0.0:
        failed.append("direct_ev_vs_accepted_allocator_not_positive")
    if direct_pnl <= 0.0:
        failed.append("direct_pnl_vs_accepted_allocator_not_positive")
    if int(aggregate_vs_accepted["windows_ev_regressed"] or 0) > 0:
        failed.append("direct_window_ev_regression_vs_accepted_allocator")
    if int(aggregate_vs_accepted["windows_pnl_regressed"] or 0) > 0:
        failed.append("direct_window_pnl_regression_vs_accepted_allocator")
    if float(aggregate_vs_accepted["max_drawdown_delta_max"] or 0.0) > MAX_DRAWDOWN_WORSE:
        failed.append("direct_drawdown_drift_too_high")
    if int(target_summary["total_trade_count"] or 0) < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_summary["windows_with_target_trades"]) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if changed_selection_count < MIN_CHANGED_SELECTIONS:
        failed.append("changed_selection_sample_too_small")
    if min_survival < 0.05:
        failed.append("core_survival_rate_below_5pct")
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    if not concentration_passed:
        failed.append("target_concentration_failed")

    if float(aggregate_vs_core["expected_value_score_delta_sum"] or 0.0) <= (
        ACCEPTED_ALLOCATOR_COMPARATOR["aggregate_ev_delta"]
    ):
        failed.append("accepted_allocator_ev_comparator_not_beaten")
    if float(aggregate_vs_core["total_pnl_delta_sum"] or 0.0) <= (
        ACCEPTED_ALLOCATOR_COMPARATOR["aggregate_pnl_delta"]
    ):
        failed.append("accepted_allocator_pnl_comparator_not_beaten")

    comparator_regressions: list[str] = []
    for label, comparator in ACCEPTED_ALLOCATOR_COMPARATOR["window_deltas"].items():
        delta = core_to_extended_rows[label]["delta"]
        if float(delta.get("expected_value_score") or 0.0) <= float(comparator["ev"]):
            comparator_regressions.append(f"{label}_ev_vs_exp_20260611_005")
        if float(delta.get("total_pnl") or 0.0) <= float(comparator["pnl"]):
            comparator_regressions.append(f"{label}_pnl_vs_exp_20260611_005")
    if comparator_regressions:
        failed.append("accepted_allocator_window_comparator_regression")

    direct_regressions: list[str] = []
    for label, row in accepted_to_extended_rows.items():
        delta = row["delta"]
        if float(delta.get("expected_value_score") or 0.0) < 0.0:
            direct_regressions.append(f"{label}_direct_ev")
        if float(delta.get("total_pnl") or 0.0) < 0.0:
            direct_regressions.append(f"{label}_direct_pnl")

    numeric_passed = not failed
    decision = (
        "positive_replay_lead_not_promoted_sec_financial_report_allocator_source"
        if numeric_passed
        else "rejected_sec_financial_report_allocator_source_extension"
    )
    if numeric_passed:
        failed.append("shared_helper_parity_missing_for_acceptance")
    return {
        "passed": False,
        "numeric_gate4_passed": numeric_passed,
        "decision": decision,
        "failed_reasons": failed,
        "direct_regressions": direct_regressions,
        "comparator_regressions": comparator_regressions,
        "direct_ev_delta_vs_accepted_allocator": round(direct_ev, 6),
        "direct_pnl_delta_vs_accepted_allocator": round(direct_pnl, 2),
        "aggregate_ev_delta_vs_core": aggregate_vs_core["expected_value_score_delta_sum"],
        "aggregate_pnl_delta_vs_core": aggregate_vs_core["total_pnl_delta_sum"],
        "direct_windows_ev_improved": aggregate_vs_accepted["windows_ev_improved"],
        "direct_windows_ev_regressed": aggregate_vs_accepted["windows_ev_regressed"],
        "direct_windows_pnl_improved": aggregate_vs_accepted["windows_pnl_improved"],
        "direct_windows_pnl_regressed": aggregate_vs_accepted["windows_pnl_regressed"],
        "direct_max_drawdown_delta": aggregate_vs_accepted["max_drawdown_delta_max"],
        "target_trade_count": target_summary["total_trade_count"],
        "target_trade_count_min": MIN_TARGET_TRADES,
        "target_window_count_min": MIN_TARGET_WINDOWS,
        "target_windows": target_summary["windows_with_target_trades"],
        "changed_selection_count": changed_selection_count,
        "changed_selection_count_min": MIN_CHANGED_SELECTIONS,
        "minimum_core_survival_rate": _round(min_survival, 6),
        "survival_guard_passed": min_survival >= 0.05,
        "target_concentration": {
            "passed": concentration_passed,
            "max_single_positive_pnl_share": target_summary[
                "max_single_positive_pnl_share"
            ],
            "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi": target_summary["positive_pnl_hhi"],
            "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
            "top5_positive_share": _top5_positive_share(target_summary),
        },
        "note": (
            "Even if numeric Gate 4 passes, this runner is not accepted alpha "
            "because the shared daily allocator helper was not changed."
        ),
    }


def build_payload() -> dict[str, Any]:
    timestamp = framework._utc_now()
    gate2_open_positions = framework.sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position check failed: {gate2_open_positions}")

    raw_exp100 = _load_exp100()
    exp100 = _filter_current_queue(raw_exp100)
    universe = sorted(get_universe())
    sector_entries = framework._load_sector_entries()
    before_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    accepted_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    extended_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    core_to_accepted_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    core_to_extended_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    accepted_to_extended_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    accepted_trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    extended_trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    source_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    sec_source_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    accepted_priority_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    extended_priority_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    baseline_results: OrderedDict[str, dict[str, Any]] = OrderedDict()

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] canonical core baseline")
        before_result = framework.shadow._run_baseline(universe, cfg)
        baseline_results[label] = before_result
        before_metrics[label] = framework.overlay_helper._metrics(before_result)

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] accepted allocator vs SEC financial-report source")
        before_result = baseline_results[label]
        before = before_metrics[label]
        snapshot = _load_window_snapshot_from_json(
            cfg=cfg,
            eligible_tickers=set(sector_entries),
        )
        window_sector_entries = {
            ticker: meta for ticker, meta in sector_entries.items() if ticker in snapshot
        }
        candidate_universe = _candidate_universe_from_sector_entries(window_sector_entries)
        core_entries = framework.shadow._baseline_entries(before_result)
        calendar_dates = framework.shadow._trading_dates(snapshot)
        dates = [day for day in calendar_dates if str(cfg["start"]) <= day <= str(cfg["end"])]
        source_trades, source_audit = allocator._build_source_trades(
            rows_by_ticker=snapshot,
            dates=dates,
            window_label=label,
            window=cfg,
            core_entries_by_date=core_entries,
            sector_entries=window_sector_entries,
            candidate_universe=candidate_universe,
            calendar_dates=calendar_dates,
        )
        sec_trades, sec_audit = _build_sec_source_trades(
            snapshot=snapshot,
            dates=dates,
            window_label=label,
            window_payload=exp100["windows"][label],
            core_entries_by_date=core_entries,
        )
        extended_source_trades = [*source_trades, *sec_trades]
        accepted_selected, accepted_filtered, accepted_priority_audit = (
            allocator.select_accepted_helper_source_priority_rows(
                source_rows=source_trades,
                trading_dates=dates,
                config=None,
                create_trades=True,
            )
        )
        extended_selected, extended_filtered, extended_priority_audit = (
            _select_extended_rows(
                source_rows=extended_source_trades,
                trading_dates=dates,
            )
        )
        accepted_kept, accepted_skipped, accepted_envelope = (
            allocator.apply_execution_envelope_to_trades(accepted_selected)
        )
        extended_kept, extended_skipped, extended_envelope = (
            allocator.apply_execution_envelope_to_trades(extended_selected)
        )
        accepted_overlay = framework.sleeve._overlay_from_paper_trades(
            before_result,
            accepted_kept,
        )
        extended_overlay = framework.sleeve._overlay_from_paper_trades(
            before_result,
            extended_kept,
        )
        accepted_after = framework.overlay_helper._metrics_with_overlay(
            before_result,
            accepted_overlay,
        )
        extended_after = framework.overlay_helper._metrics_with_overlay(
            before_result,
            extended_overlay,
        )
        accepted_delta = framework.overlay_helper._delta(accepted_after, before)
        extended_delta = framework.overlay_helper._delta(extended_after, before)
        direct_delta = framework.overlay_helper._delta(extended_after, accepted_after)

        accepted_keys = {_row_key(row) for row in accepted_kept}
        extended_keys = {_row_key(row) for row in extended_kept}
        changed_keys = sorted(accepted_keys.symmetric_difference(extended_keys))
        changed_count = len(changed_keys) // 2

        accepted_metrics[label] = accepted_after
        extended_metrics[label] = extended_after
        accepted_trades_by_window[label] = accepted_kept
        extended_trades_by_window[label] = extended_kept
        source_audit_by_window[label] = {
            **source_audit,
            "source_trade_counts_with_sec_financial_report": {
                **source_audit["source_trade_counts"],
                SEC_SOURCE_FAMILY: len(sec_trades),
            },
            "raw_candidate_counts_with_sec_financial_report": {
                **source_audit["raw_candidate_counts"],
                SEC_SOURCE_FAMILY: sec_audit["candidate_count"],
            },
        }
        sec_source_audit_by_window[label] = sec_audit
        accepted_priority_audit_by_window[label] = {
            **accepted_priority_audit,
            "envelope": accepted_envelope,
            "envelope_skipped_count": len(accepted_skipped),
        }
        extended_priority_audit_by_window[label] = {
            **extended_priority_audit,
            "envelope": extended_envelope,
            "envelope_skipped_count": len(extended_skipped),
        }
        core_to_accepted_rows[label] = {
            "before": before,
            "after": accepted_after,
            "delta": accepted_delta,
            "target_trade_count": len(accepted_kept),
            "selected_source_counts": _source_counts(accepted_kept),
            "filtered_daily_top1_count": sum(
                1
                for row in accepted_filtered
                if row.get("filter_reason") == "daily_top1_source_priority_limit"
            ),
        }
        core_to_extended_rows[label] = {
            "before": before,
            "after": extended_after,
            "delta": extended_delta,
            "target_trade_count": len(extended_kept),
            "selected_source_counts": _source_counts(extended_kept),
            "sec_financial_report_selected_count": _source_counts(extended_kept).get(
                SEC_SOURCE_FAMILY,
                0,
            ),
            "changed_selection_count": changed_count,
            "source_trade_counts": source_audit_by_window[label][
                "source_trade_counts_with_sec_financial_report"
            ],
        }
        accepted_to_extended_rows[label] = {
            "before": accepted_after,
            "after": extended_after,
            "delta": direct_delta,
            "target_trade_count": len(extended_kept),
            "changed_selection_count": changed_count,
            "accepted_selected_source_counts": _source_counts(accepted_kept),
            "extended_selected_source_counts": _source_counts(extended_kept),
            "extended_rejected_count": len(extended_filtered),
            "changed_keys_sample": changed_keys[:50],
        }

    aggregate_core_to_accepted = framework._aggregate_window_rows(core_to_accepted_rows)
    aggregate_core_to_extended = framework._aggregate_window_rows(core_to_extended_rows)
    aggregate_accepted_to_extended = framework._aggregate_window_rows(
        accepted_to_extended_rows
    )
    extended_summary = _target_summary(extended_trades_by_window)
    accepted_summary = _target_summary(accepted_trades_by_window)
    changed_selection_count = sum(
        int(row["changed_selection_count"])
        for row in accepted_to_extended_rows.values()
    )
    gate4 = _gate4(
        aggregate_vs_core=aggregate_core_to_extended,
        aggregate_vs_accepted=aggregate_accepted_to_extended,
        target_summary=extended_summary,
        before_metrics=before_metrics,
        core_to_extended_rows=core_to_extended_rows,
        accepted_to_extended_rows=accepted_to_extended_rows,
        changed_selection_count=changed_selection_count,
    )

    if gate4["numeric_gate4_passed"]:
        status = "positive_replay_lead"
        interpretation = (
            "SEC financial-report source rows numerically beat the accepted "
            "allocator, but the alpha is not retained because shared helper "
            "and daily snapshot parity were not implemented in this scout."
        )
        reflection = (
            "The SEC event-information source supplied enough distinct "
            "replacement rows under the allocator envelope. The next step "
            "would be shared allocator-source promotion, not rank/threshold "
            "retuning."
        )
    else:
        status = "rejected"
        interpretation = (
            "The SEC financial-report allocator source failed the accepted "
            "allocator comparison; no strategy or production behavior is retained."
        )
        reflection = (
            "The standalone SEC financial-report sleeve can remain useful, but "
            "its event rows did not add robust incremental replacement value "
            "after lagged consensus and the accepted allocator stack. The likely "
            "failure mode is overlap or displacement rather than bad SEC data."
        )

    actual_success = bool(gate4["numeric_gate4_passed"])
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "owner": OWNER,
        "lane": "alpha_search",
        "status": status,
        "decision": gate4["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "change_type": "replay_only_allocator_source_extension",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": (
            "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
        ),
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "production_visible_free_sec_event_source_family_replay",
        "nearby_prior_experiments": [
            "exp-20260614-004",
            "exp-20260611-005",
            "exp-20260611-008",
            "exp-20260611-015",
            "exp-20260613-012",
            "exp-20260610-016",
            "exp-20260610-019",
        ],
        "prior_trial_count": 0,
        "prediction": PREDICTION,
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_gate4_passed": actual_success,
            "actual_success": int(actual_success),
            "actual_ev_delta_vs_accepted_allocator": gate4[
                "direct_ev_delta_vs_accepted_allocator"
            ],
            "actual_pnl_delta_vs_accepted_allocator": gate4[
                "direct_pnl_delta_vs_accepted_allocator"
            ],
            "brier_score": round(
                (PREDICTION["success_probability"] - (1.0 if actual_success else 0.0))
                ** 2,
                6,
            ),
            "failure_modes_observed": gate4["failed_reasons"],
            "predicted_failure_mode_hit": any(
                mode in ";".join(gate4["failed_reasons"])
                for mode in PREDICTION["main_failure_modes"]
            ),
        },
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "accepted-helper allocator overlay and replay-only rank-2 SEC "
                "financial-report source extension"
            ),
            "windows": framework.WINDOWS,
            "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
            "sec_event_source": "exp-20260511-100 filtered financial-report T+1 queue",
            "accepted_allocator_rule_version": allocator.RULE_VERSION,
            "accepted_allocator_source_rule_version": allocator.SOURCE_RULE_VERSION,
            "sec_source_rule_version": SEC_SOURCE_RULE_VERSION,
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
        },
        "parameters": {
            "rank_inserted": 2,
            "rank_basis": (
                "SEC financial-report is distinct PIT event information and "
                "keeps lagged consensus rank 1; all lower accepted allocator "
                "source ranks shift down by one only inside this replay."
            ),
            "sec_signal_source": "exp-20260511-100 filtered by current queue threshold",
            "allocator_execution_envelope": allocator.EXECUTION_ENVELOPE[
                "rule_version"
            ],
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "daily_entry_slots": allocator.MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": allocator.SAME_TICKER_COOLDOWN_DAYS,
            "locked_variables": [
                "financial_report_queue_threshold",
                "lagged consensus remains rank 1",
                "allocator top1_per_day",
                "notional",
                "hold_days",
                "cooldown",
                "core_strategy",
                "live_orders",
            ],
        },
        "gate1": {
            "passed": True,
            "baseline_metrics": before_metrics,
            "baseline_artifact": (
                "docs/backtesting.md current canonical baseline and same-run "
                "before_metrics inside this artifact"
            ),
        },
        "gate2": {
            "passed": True,
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "warehouse OHLCV Date/Open/High/Low/Close/Volume",
                "accepted allocator source rows signal_date/ticker/source_family",
                "SEC financial-report candidate rows ticker/t1_date/t1_excess_return_vs_spy",
            ],
        },
        "gate3": {
            "passed": min(
                float(row.get("survival_rate") or 0.0)
                for row in before_metrics.values()
            )
            >= 0.05,
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": _round(
                min(
                    float(row.get("survival_rate") or 0.0)
                    for row in before_metrics.values()
                ),
                6,
            ),
            "note": "Default-off paper allocator only; core signals/survival unchanged.",
        },
        "gate4": gate4,
        "before_metrics": before_metrics,
        "accepted_allocator_metrics": accepted_metrics,
        "sec_financial_report_allocator_metrics": extended_metrics,
        "delta_metrics": {
            "core_to_accepted_allocator": {
                "by_window": OrderedDict(
                    (label, row["delta"]) for label, row in core_to_accepted_rows.items()
                ),
                "aggregate": aggregate_core_to_accepted,
            },
            "core_to_sec_financial_report_allocator": {
                "by_window": OrderedDict(
                    (label, row["delta"]) for label, row in core_to_extended_rows.items()
                ),
                "aggregate": aggregate_core_to_extended,
            },
            "accepted_allocator_to_sec_financial_report_allocator": {
                "by_window": OrderedDict(
                    (label, row["delta"])
                    for label, row in accepted_to_extended_rows.items()
                ),
                "aggregate": aggregate_accepted_to_extended,
            },
        },
        "window_rows": {
            "core_to_accepted_allocator": core_to_accepted_rows,
            "core_to_sec_financial_report_allocator": core_to_extended_rows,
            "accepted_allocator_to_sec_financial_report_allocator": accepted_to_extended_rows,
        },
        "accepted_trade_summary": accepted_summary,
        "sec_financial_report_allocator_trade_summary": extended_summary,
        "source_audit_by_window": source_audit_by_window,
        "sec_source_audit_by_window": sec_source_audit_by_window,
        "accepted_priority_audit_by_window": accepted_priority_audit_by_window,
        "extended_priority_audit_by_window": extended_priority_audit_by_window,
        "production_impact": PRODUCTION_IMPACT,
        "accepted_comparators": {
            "accepted_allocator": ACCEPTED_ALLOCATOR_COMPARATOR,
            "same_run_accepted_allocator_control": aggregate_core_to_accepted,
        },
        "interpretation": interpretation,
        "rejection_reason": None if gate4["numeric_gate4_passed"] else "; ".join(
            gate4["failed_reasons"]
        ),
        "post_run_reflection": {
            "why_result_happened": reflection,
            "negative_reflection": (
                "If rejected, SEC financial-report drift should stay in its "
                "standalone sleeve rather than being forced into the accepted "
                "allocator. If positive, no retention is valid without shared "
                "daily allocator-source parity."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry by changing SEC source rank, T+1 excess threshold, "
                "SEC event notional, allocator top-N, notional, hold days, "
                "cooldown, or accepted source ranks on the frozen windows."
            ),
            "new_evidence_required": (
                "A retry needs closed forward source-competition replacement "
                "rows, a materially different PIT SEC event-quality field, or "
                "a shared-helper promotion only if this exact fixed bundle "
                "first passes Gate 4."
            ),
        },
        "next_retry_requires": [
            "closed forward source-competition replacement rows",
            "materially new PIT SEC event-quality field",
            "no frozen-window rank/threshold/hold/notional sweep",
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(MANIFEST_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} SEC financial-report allocator source extension",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Three-Window Direct Result",
        "",
        "| Window | Accepted EV | SEC EV | dEV | Accepted PnL | SEC PnL | dPnL | SEC selected | Changed selections |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    direct_rows = payload["window_rows"][
        "accepted_allocator_to_sec_financial_report_allocator"
    ]
    extended_rows = payload["window_rows"]["core_to_sec_financial_report_allocator"]
    for label in framework.WINDOWS:
        row = direct_rows[label]
        before = row["before"]
        after = row["after"]
        delta = row["delta"]
        extended = extended_rows[label]
        lines.append(
            "| {label} | {bev:.6f} | {aev:.6f} | {dev:+.6f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {sec_count} | {changed} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                sec_count=extended["sec_financial_report_selected_count"],
                changed=row["changed_selection_count"],
            )
        )
    gate = payload["gate4"]
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            "- Direct EV delta vs accepted allocator: `{:+.6f}`".format(
                gate["direct_ev_delta_vs_accepted_allocator"]
            ),
            "- Direct PnL delta vs accepted allocator: `${:+,.2f}`".format(
                gate["direct_pnl_delta_vs_accepted_allocator"]
            ),
            "- Aggregate EV delta vs core: `{:+.6f}`".format(
                gate["aggregate_ev_delta_vs_core"]
            ),
            "- Aggregate PnL delta vs core: `${:+,.2f}`".format(
                gate["aggregate_pnl_delta_vs_core"]
            ),
            f"- Numeric Gate 4 passed: `{gate['numeric_gate4_passed']}`",
            f"- Gate failed reasons: `{', '.join(gate['failed_reasons'])}`",
            "",
            "## Production Impact",
            "",
            json.dumps(payload["production_impact"], indent=2, sort_keys=True),
            "",
            "## Post-Run Reflection",
            "",
            json.dumps(payload["post_run_reflection"], indent=2, sort_keys=True),
            "",
        ]
    )
    return "\n".join(lines)


def _card_markdown(payload: dict[str, Any]) -> str:
    gate = payload["gate4"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Direct EV delta vs accepted allocator: `{gate['direct_ev_delta_vs_accepted_allocator']:+.6f}`",
            f"- Direct PnL delta vs accepted allocator: `${gate['direct_pnl_delta_vs_accepted_allocator']:+,.2f}`",
            f"- Failed reasons: `{', '.join(gate['failed_reasons'])}`",
            "",
            "## Reproduce",
            "",
            "```powershell",
            PRE_RUN_QUESTIONS["5_reproducibility"],
            "```",
            "",
        ]
    )


def _upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    encoded = json.dumps(_safe(record), ensure_ascii=False, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                rows.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                rows.append(encoded)
                replaced = True
            else:
                rows.append(raw)
    if not replaced:
        rows.append(encoded)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def persist_closeout(payload: dict[str, Any]) -> None:
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        status=payload["status"],
        result={
            "decision": payload["decision"],
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "card": _repo_rel(CARD_MD),
            "gate4": payload["gate4"],
            "calibration": payload["calibration"],
            "post_run_reflection": payload["post_run_reflection"],
            "production_impact": PRODUCTION_IMPACT,
        },
        prediction=PREDICTION,
        fields={
            "change_type": payload["change_type"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "hypothesis": payload["hypothesis"],
            "owner": OWNER,
        },
    )
    _upsert_jsonl(EXPERIMENT_LOG_JSONL, payload)


def write_outputs(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(TICKET_JSON, {**payload, "ticket_status": payload["status"]})
    _write_json(
        MANIFEST_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "decision": payload["decision"],
            "owner": OWNER,
            "files": payload["related_files"],
            "reproduce": PRE_RUN_QUESTIONS["5_reproducibility"],
        },
    )
    CARD_MD.parent.mkdir(parents=True, exist_ok=True)
    CARD_MD.write_text(_card_markdown(payload), encoding="utf-8")
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact_markdown(payload), encoding="utf-8")
    persist_closeout(payload)


def main() -> None:
    payload = build_payload()
    write_outputs(payload)
    print(json.dumps(_safe({
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "gate4": payload["gate4"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
    }), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
