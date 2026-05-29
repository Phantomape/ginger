"""exp-20260529-019: SEC Item 5.02 positive-reaction candidate pool.

This alpha search tests one free-data candidate source: PIT-safe SEC 8-K
Item 5.02 leadership-change filings whose issuer also shows same-day positive
price confirmation, liquidity, trend, and relative-strength support.

The sleeve is default-off paper only, admits at most one candidate per signal
day, enters at the next available open, and exits after ten trading days.
Core signal generation, ranking, sizing, exits, LLM/news replay, watchlists,
and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260529_015_sec_fd_other_8k_positive_reaction_candidate_pool as prior


REPO_ROOT = Path(__file__).resolve().parents[2]
framework = prior.framework

EXPERIMENT_ID = "exp-20260529-019"
STEM = "sec_item502_positive_reaction_candidate_pool"
TRIAL_FAMILY = "sec_item502_positive_reaction_candidate_pool"
CHANGED_VARIABLE = "sec_item502_positive_reaction_candidate_source_v1"
RULE_VERSION = "sec_item502_positive_reaction_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260529_019_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

SEC_EVENTS_FILE = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / "sec_filing_events_20241002_20260421.jsonl"
)

TARGET_ITEM_CODES = {"5.02"}
EXCLUDED_ITEM_CODES = {"1.01", "1.02", "2.02", "2.03", "3.02", "5.01", "5.03", "5.07"}
MOVING_AVERAGE_DAYS = 50
RELATIVE_STRENGTH_DAYS = 20
AVG_DOLLAR_VOLUME_DAYS = 20
MIN_CLOSE = 5.0
MIN_AVG_DOLLAR_VOLUME_20D = 20_000_000.0
MIN_RS20_VS_SPY = 0.0
MIN_SIGNAL_EXCESS_RETURN_1D_VS_SPY = 0.0
MIN_SIGNAL_CLOSE_LOCATION = 0.55
MAX_PAPER_TRADES_PER_DAY = 1
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30

_SEC_ITEM502_EVENTS_CACHE: list[dict[str, Any]] | None = None


def _patch_framework() -> None:
    framework.EXPERIMENT_ID = EXPERIMENT_ID
    framework.STEM = STEM
    framework.TRIAL_FAMILY = TRIAL_FAMILY
    framework.CHANGED_VARIABLE = CHANGED_VARIABLE
    framework.RULE_VERSION = RULE_VERSION
    framework.OUT_DIR = OUT_DIR
    framework.OUT_JSON = OUT_JSON
    framework.BEFORE_AGG_JSON = BEFORE_AGG_JSON
    framework.AFTER_AGG_JSON = AFTER_AGG_JSON
    framework.LOG_JSON = LOG_JSON
    framework.TICKET_JSON = TICKET_JSON
    framework.DOC_TICKET_JSON = TICKET_JSON
    framework.ARTIFACT_MD = ARTIFACT_MD
    framework.EXPERIMENT_LOG = EXPERIMENT_LOG
    framework.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    framework.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    framework.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    framework.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    framework.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    framework.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._gate4 = prior._gate4
    framework._build_report = _build_report


def _load_sec_item502_events() -> list[dict[str, Any]]:
    global _SEC_ITEM502_EVENTS_CACHE
    if _SEC_ITEM502_EVENTS_CACHE is not None:
        return _SEC_ITEM502_EVENTS_CACHE

    paths = [SEC_EVENTS_FILE] if SEC_EVENTS_FILE.exists() else []
    if not paths:
        paths = sorted((REPO_ROOT / "data" / "non_ohlcv").glob("sec_filing_events_*.jsonl"))

    deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ticker = str(row.get("ticker") or "").upper().strip()
                usable_trade_date = str(row.get("usable_trade_date") or "").strip()[:10]
                accession = str(row.get("accession_number") or "").strip()
                if not ticker or not usable_trade_date or not accession:
                    continue
                form = str(row.get("form_base") or row.get("form_type") or "").upper()
                if form != "8-K":
                    continue
                if row.get("pit_safe_flag") is not True:
                    continue
                if bool(row.get("is_amendment")):
                    continue
                item_codes = {
                    str(code).strip()
                    for code in (row.get("eight_k_item_codes") or [])
                    if str(code).strip()
                }
                if not item_codes.intersection(TARGET_ITEM_CODES):
                    continue
                if item_codes.intersection(EXCLUDED_ITEM_CODES):
                    continue
                deduped[(ticker, accession, usable_trade_date)] = {
                    "ticker": ticker,
                    "usable_trade_date": usable_trade_date,
                    "accession_number": accession,
                    "accepted_at": row.get("accepted_at"),
                    "filing_date": str(row.get("filing_date") or "")[:10] or None,
                    "form_type": row.get("form_type"),
                    "form_base": row.get("form_base"),
                    "eight_k_item_codes": sorted(item_codes),
                    "archive_url": row.get("archive_url"),
                    "pit_source": row.get("pit_source"),
                    "source_file": path.name,
                }

    _SEC_ITEM502_EVENTS_CACHE = sorted(
        deduped.values(),
        key=lambda row: (
            str(row["usable_trade_date"]),
            str(row["ticker"]),
            str(row["accession_number"]),
        ),
    )
    return _SEC_ITEM502_EVENTS_CACHE


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = framework.ohlcv_helper._baseline_entries(before_result)
    dates = {
        date
        for date in framework.ohlcv_helper._trading_dates(snapshot)
        if str(cfg["start"]) <= date <= str(cfg["end"])
    }
    spy_rows = framework.ohlcv_helper._series(snapshot, "SPY")
    spy_index = framework.ohlcv_helper._row_index(spy_rows)
    events = [
        event for event in _load_sec_item502_events() if event["usable_trade_date"] in dates
    ]
    candidates: list[dict[str, Any]] = []
    audit: Counter[str] = Counter()
    seen_ticker_dates: set[tuple[str, str]] = set()

    for event in events:
        ticker = str(event["ticker"]).upper()
        signal_date = str(event["usable_trade_date"])
        if ticker in framework.EXCLUDED_TICKERS:
            audit["excluded_ticker"] += 1
            continue
        rows = framework.ohlcv_helper._series(snapshot, ticker)
        idx = framework.ohlcv_helper._row_index(rows).get(signal_date)
        spy_idx = spy_index.get(signal_date)
        if (
            idx is None
            or spy_idx is None
            or idx < max(MOVING_AVERAGE_DAYS, RELATIVE_STRENGTH_DAYS)
            or spy_idx < RELATIVE_STRENGTH_DAYS
        ):
            audit["missing_ohlcv_or_history"] += 1
            continue

        close = framework.ohlcv_helper._value(rows[idx], "Close")
        volume = framework.ohlcv_helper._value(rows[idx], "Volume")
        if close is None or volume is None or float(close) < MIN_CLOSE:
            audit["missing_or_low_price_volume"] += 1
            continue

        avg_dollar_volume = prior._avg_dollar_volume(
            rows,
            idx,
            AVG_DOLLAR_VOLUME_DAYS,
        )
        if avg_dollar_volume is None or avg_dollar_volume < MIN_AVG_DOLLAR_VOLUME_20D:
            audit["low_avg_dollar_volume"] += 1
            continue

        ma50 = framework._prior_average(rows, idx, MOVING_AVERAGE_DAYS, "Close")
        if ma50 is None or float(close) <= float(ma50):
            audit["below_50d_trend"] += 1
            continue

        ret20 = framework._close_return(rows, idx - RELATIVE_STRENGTH_DAYS, idx)
        spy_ret20 = framework._close_return(
            spy_rows,
            spy_idx - RELATIVE_STRENGTH_DAYS,
            spy_idx,
        )
        if ret20 is None or spy_ret20 is None:
            audit["missing_rs20"] += 1
            continue
        rs20_vs_spy = ret20 - spy_ret20
        if rs20_vs_spy < MIN_RS20_VS_SPY:
            audit["weak_rs20_vs_spy"] += 1
            continue

        signal_return_1d = prior._daily_return(rows, idx)
        spy_return_1d = prior._daily_return(spy_rows, spy_idx)
        if signal_return_1d is None or spy_return_1d is None:
            audit["missing_signal_return"] += 1
            continue
        signal_excess_return = signal_return_1d - spy_return_1d
        if signal_excess_return < MIN_SIGNAL_EXCESS_RETURN_1D_VS_SPY:
            audit["weak_signal_day_excess_return"] += 1
            continue

        signal_close_location = prior._close_location(rows[idx])
        if signal_close_location is None or signal_close_location < MIN_SIGNAL_CLOSE_LOCATION:
            audit["weak_close_location"] += 1
            continue

        key = (ticker, signal_date)
        if key in seen_ticker_dates:
            audit["duplicate_ticker_date_item502"] += 1
            continue
        seen_ticker_dates.add(key)

        ab_entries = entries_by_date.get(signal_date, [])
        score = (
            rs20_vs_spy
            + signal_excess_return
            + (signal_close_location * 0.10)
            + min(math.log10(max(avg_dollar_volume, 1.0)) / 100.0, 0.10)
        )
        candidates.append(
            {
                "date": signal_date,
                "ticker": ticker,
                "strategy": STEM,
                "rule_version": RULE_VERSION,
                "sec_accession_number": event.get("accession_number"),
                "sec_accepted_at": event.get("accepted_at"),
                "sec_filing_date": event.get("filing_date"),
                "sec_form_type": event.get("form_type"),
                "sec_8k_item_codes": event.get("eight_k_item_codes"),
                "sec_archive_url": event.get("archive_url"),
                "sec_pit_source": event.get("pit_source"),
                "sec_source_file": event.get("source_file"),
                "close": framework.base._round(close, 4),
                "volume": framework.base._round(volume, 2),
                "ma50": framework.base._round(ma50, 4),
                "avg_dollar_volume_20d": framework.base._round(avg_dollar_volume, 2),
                "ret20": framework.base._round(ret20, 6),
                "spy_ret20": framework.base._round(spy_ret20, 6),
                "rs20_vs_spy": framework.base._round(rs20_vs_spy, 6),
                "signal_return_1d": framework.base._round(signal_return_1d, 6),
                "spy_return_1d": framework.base._round(spy_return_1d, 6),
                "signal_excess_return_1d_vs_spy": framework.base._round(
                    signal_excess_return,
                    6,
                ),
                "signal_close_location": framework.base._round(signal_close_location, 6),
                "item502_candidate_score": framework.base._round(score, 6),
                "same_day_ab_entry_count": len(ab_entries),
                "same_day_ab_overlap": bool(ab_entries),
                "same_ticker_ab_overlap": any(
                    trade.get("ticker") == ticker for trade in ab_entries
                ),
                "known_at": "after_sec_8k_usable_trade_date_close_before_next_open_paper_entry",
                "trade_enabled": False,
                "alters_orders": False,
            }
        )

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["item502_candidate_score"]),
            -float(row["rs20_vs_spy"]),
            -float(row["signal_excess_return_1d_vs_spy"]),
            -float(row["avg_dollar_volume_20d"]),
            row["ticker"],
        )
    )
    return candidates, {
        "dates_checked": len(dates),
        "sec_item502_events_in_window": len(events),
        "candidate_count": len(candidates),
        "candidate_days": len({row["date"] for row in candidates}),
        "unique_candidate_tickers": len({row["ticker"] for row in candidates}),
        "candidate_universe_argument_count": len(universe),
        "audit_reject_counts": dict(sorted(audit.items())),
        "rule_version": RULE_VERSION,
        "sec_events_source": framework.base._repo_rel(SEC_EVENTS_FILE),
    }


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4 = payload["gate4"]
    decision = (
        "accepted_candidate_sec_item502_positive_reaction"
        if gate4["passed"]
        else "rejected_sec_item502_positive_reaction"
    )
    all_target_trades = [
        trade
        for trades in payload["target_trades_by_window"].values()
        for trade in trades
    ]
    actual_success = 1 if gate4["passed"] else 0
    prediction = {
        "success_probability": 0.21,
        "expected_ev_delta": 0.10,
        "expected_pnl_delta": 1800.0,
        "main_failure_modes": [
            "leadership event sample too noisy",
            "late_strong regression",
            "sample too small after positive reaction confirmation",
            "single ticker concentration",
        ],
        "confidence_reason": (
            "Meta research favors production-visible candidate-pool alpha, and "
            "Item 5.02 has broader coverage than 10-K and Item 1.01. Confidence "
            "stays modest because event/SEC direct issuer pools have recently "
            "failed Gate 4."
        ),
        "recorded_at": "2026-05-29T16:06:33+00:00",
        "brier_score": round((0.21 - actual_success) ** 2, 6),
    }

    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": decision,
            "decision": decision,
            "hypothesis": (
                "PIT-safe SEC 8-K Item 5.02 leadership-change filings with "
                "positive same-day issuer reaction, liquidity, trend, and "
                "relative-strength confirmation may provide a free-data "
                "candidate-pool expansion source."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": (
                "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
            ),
            "trial_variant_id": RULE_VERSION,
            "prior_trial_count": 0,
            "nearby_prior_experiments": [
                "exp-20260504-026",
                "exp-20260529-015",
                "exp-20260529-016",
            ],
            "multiple_testing_risk_bucket": "minimal",
            "new_evidence_type": (
                "production_visible_free_sec_item502_leadership_change_plus_ohlcv_confirmation"
            ),
            "prediction": prediction,
            "parameters": {
                "base_universe_count": payload["parameters"]["base_universe_count"],
                "stock_excluded_tickers": sorted(framework.EXCLUDED_TICKERS),
                "paper_notional_usd": framework.base.BASE_NOTIONAL_USD,
                "hold_days": framework.base.HOLD_DAYS,
                "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
                "target_item_codes": sorted(TARGET_ITEM_CODES),
                "excluded_item_codes": sorted(EXCLUDED_ITEM_CODES),
                "moving_average_days": MOVING_AVERAGE_DAYS,
                "relative_strength_days": RELATIVE_STRENGTH_DAYS,
                "avg_dollar_volume_days": AVG_DOLLAR_VOLUME_DAYS,
                "min_close": MIN_CLOSE,
                "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
                "min_rs20_vs_spy": MIN_RS20_VS_SPY,
                "min_signal_excess_return_1d_vs_spy": (
                    MIN_SIGNAL_EXCESS_RETURN_1D_VS_SPY
                ),
                "min_signal_close_location": MIN_SIGNAL_CLOSE_LOCATION,
                "source_definition": [
                    "SEC filing event has form_base/form_type 8-K",
                    "event row must have pit_safe_flag true and usable_trade_date",
                    "amended 8-K rows are excluded",
                    "item codes must include 5.02 leadership-change disclosure",
                    "earnings, material agreement, financing, governance vote, and charter item codes are excluded",
                    "ticker must have exact signal-date OHLCV in the fixed snapshot",
                    "close must be above the prior 50-day moving average",
                    "20-day return must beat SPY by at least 0 percentage points",
                    "20-day average dollar volume must be at least USD 20 million",
                    "signal-day ticker-minus-SPY return must be nonnegative",
                    "signal-day close location must be at least 0.55",
                    "top-1 selected paper entry per signal date",
                ],
                "selection_rank": [
                    "signal_date",
                    "item502_candidate_score desc",
                    "rs20_vs_spy desc",
                    "signal_excess_return_1d_vs_spy desc",
                    "avg_dollar_volume_20d desc",
                    "ticker asc",
                ],
                "locked_variables": [
                    "core universe membership",
                    "core signal generation",
                    "core ranking",
                    "core position sizing",
                    "core exits",
                    "portfolio heat",
                    "slot rules",
                    "LLM/news replay",
                    "watchlists",
                    "live/default orders",
                ],
                "acceptance": {
                    "aggregate_ev_delta_gt": 0,
                    "aggregate_pnl_delta_gt": 0,
                    "max_ev_regressed_windows": 0,
                    "max_pnl_regressed_windows": 0,
                    "min_target_trades": MIN_TARGET_TRADES,
                    "min_target_windows": MIN_TARGET_WINDOWS,
                    "max_drawdown_worse": MAX_DRAWDOWN_WORSE,
                    "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
                    "max_positive_hhi": MAX_POSITIVE_HHI,
                },
            },
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "candidate_pool / entry: leadership-change 8-Ks with immediate "
                    "issuer price confirmation can capture management transition "
                    "clarity better than generic FD/Other or material-agreement rows."
                ),
                "2_history_check": {
                    "exp-20260504-026": (
                        "Accepted a default-off leadership-change negative-reaction "
                        "event sleeve. This run is not a retry of that negative "
                        "reaction branch; it tests positive same-day issuer "
                        "confirmation and direct ten-day continuation."
                    ),
                    "exp-20260529-015": (
                        "Generic 7.01/8.01 FD/Other direct issuer positive reaction "
                        "regressed all windows. This run targets only Item 5.02 "
                        "leadership-change filings."
                    ),
                    "exp-20260529-016": (
                        "Item 1.01 material-agreement positive reaction was too "
                        "sparse and negative. This run uses the broader leadership "
                        "event family and excludes Item 1.01."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same three docs/backtesting.md windows; positive aggregate EV/PnL; "
                    "no EV- or PnL-regressed window; >=20 paper trades across all "
                    "3 windows; drawdown drift <=0.5pp; survival >=5%; concentration "
                    "inside guardrails."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                    "exp_20260529_019_sec_item502_positive_reaction_candidate_pool.py"
                ),
            },
            "why_not_other_changes": (
                "Skipped LLM soft-ranking because replay attribution remains sparse. "
                "Skipped Companyfacts, VBB, VCP, state-surface, FINRA, and OHLCV "
                "pattern-name retunes per playbook freeze guidance. This run tests "
                "one free SEC Item 5.02 event candidate-source variable only."
            ),
            "production_impact": {
                "shared_policy_changed": False,
                "backtester_adapter_changed": False,
                "run_adapter_changed": False,
                "replay_only": True,
                "parity_test_added": False,
                "default_off_paper_only": True,
                "production_watchlist_changed": False,
                "production_orders_changed": False,
                "trade_enabled": False,
                "promotion_requirement": (
                    "A retained result would still require a shared default-off paper "
                    "adapter and parity tests before any daily report or live/default "
                    "behavior changes."
                ),
            },
            "production_parity": {
                "alters_production_orders": False,
                "alters_live_watchlists": False,
                "alters_core_backtester": False,
                "default_enabled": False,
                "replay_only": True,
                "parity_note": (
                    "No production code path is changed. If accepted, promotion would "
                    "require a shared SEC Item 5.02 paper sleeve with exact item-code, "
                    "as-of OHLCV, and entry/exit parity tests."
                ),
            },
            "interpretation": (
                "The SEC Item 5.02 positive-reaction candidate pool cleared Gate 4 "
                "as a default-off replay lead, but no production/shared policy was promoted."
                if gate4["passed"]
                else (
                    "The SEC Item 5.02 positive-reaction candidate pool did not clear "
                    "Gate 4. Do not promote it or retry nearby leadership positive-"
                    "reaction thresholds on the same frozen windows without new "
                    "forward rows or a sharper structured leadership-quality field."
                )
            ),
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "next_evidence_needed": (
                "Forward replacement-value rows or a materially sharper leadership-quality "
                "field such as CEO/CFO appointment versus resignation, succession "
                "clarity, founder transition, or evidence-bound text classification."
            ),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "SEC 8-K event metadata uses pit_safe usable_trade_date. OHLCV filters "
        "are observed through the signal-date close; paper entry is the next "
        "available open with production entry slippage; exit is ten trading days "
        "after the signal with target-side sell slippage and ROUND_TRIP_COST_PCT."
    )
    payload["gate2"]["runtime_field_coverage"] = {
        "sec_events": {
            "source": framework.base._repo_rel(SEC_EVENTS_FILE),
            "required_fields": [
                "ticker",
                "usable_trade_date",
                "accession_number",
                "form_base/form_type",
                "pit_safe_flag",
                "eight_k_item_codes",
                "is_amendment",
            ],
            "events_loaded": len(_load_sec_item502_events()),
        }
    }
    payload["gate2"]["target_trade_field_coverage"] = framework._field_coverage(
        all_target_trades,
        [
            "ticker",
            "signal_date",
            "entry_date",
            "exit_date",
            "entry_price",
            "exit_price",
            "pnl",
            "known_at",
            "sec_accession_number",
            "sec_accepted_at",
            "sec_8k_item_codes",
            "rs20_vs_spy",
            "signal_excess_return_1d_vs_spy",
            "avg_dollar_volume_20d",
        ],
    )
    payload["related_files"] = [
        framework.base._repo_rel(Path(__file__)),
        framework.base._repo_rel(OUT_JSON),
        framework.base._repo_rel(BEFORE_AGG_JSON),
        framework.base._repo_rel(AFTER_AGG_JSON),
        framework.base._repo_rel(LOG_JSON),
        framework.base._repo_rel(TICKET_JSON),
        framework.base._repo_rel(CARD_MD),
        framework.base._repo_rel(ARTIFACT_MD),
        framework.base._repo_rel(EXPERIMENT_LOG),
        framework.base._repo_rel(SEC_EVENTS_FILE),
    ]
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} | {raw} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                raw=payload["raw_candidate_counts"][label],
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    return "\n".join(
        [
            "# exp-20260529-019 SEC Item 5.02 Positive-Reaction Candidate Pool",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: a default-off paper candidate source that admits PIT-safe SEC 8-K Item 5.02 leadership-change filings with positive same-day issuer reaction, liquidity, trend, and RS confirmation, top-1 per day, next-open entry, ten-trading-day exit.",
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- EV delta: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- target trades: `{payload['target_trade_summary']['total_trade_count']}` across `{len(payload['target_trade_summary']['windows_with_target_trades'])}` windows",
            f"- max single positive share: `{payload['target_trade_summary']['max_single_positive_pnl_share']}`",
            f"- positive PnL HHI: `{payload['target_trade_summary']['positive_pnl_hhi']}`",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(gate4, indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _persist(payload: dict[str, Any]) -> None:
    framework.base._write_json(OUT_JSON, payload)
    framework.base._write_json(BEFORE_AGG_JSON, payload["judge_before_aggregate"])
    framework.base._write_json(AFTER_AGG_JSON, payload["judge_after_aggregate"])
    framework.base._write_json(LOG_JSON, payload)
    ticket_payload = {
        "experiment_id": EXPERIMENT_ID,
        "title": "SEC Item 5.02 positive-reaction candidate pool",
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": framework.base._repo_rel(ARTIFACT_MD),
        "json": framework.base._repo_rel(OUT_JSON),
        "before_aggregate": framework.base._repo_rel(BEFORE_AGG_JSON),
        "after_aggregate": framework.base._repo_rel(AFTER_AGG_JSON),
        "summary": payload["interpretation"],
    }
    framework.base._write_json(TICKET_JSON, ticket_payload)
    framework.base._write_text(ARTIFACT_MD, _build_report(payload))
    framework.base._write_text(CARD_MD, _build_report(payload))
    framework.base._upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    _patch_framework()
    payload = _postprocess_payload(framework._build_payload())
    _persist(payload)
    print(
        json.dumps(
            framework.base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "target_trade_summary": payload["target_trade_summary"],
                    "artifact": framework.base._repo_rel(ARTIFACT_MD),
                    "before_aggregate": framework.base._repo_rel(BEFORE_AGG_JSON),
                    "after_aggregate": framework.base._repo_rel(AFTER_AGG_JSON),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    if not math.isfinite(1.0):
        raise SystemExit("unexpected math failure")
    raise SystemExit(main())
