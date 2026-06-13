"""exp-20260613-026: Form 4 tax-withholding absorption candidate pool.

Replay-only alpha search. This tests one fixed candidate-source variable:
PIT-safe Form 4 non-derivative transaction-code F tax-withholding/RSU vesting
clusters that are followed by same-day liquid leadership.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import exp_20260611_026_form4_sale_absorption_leadership as sale_scout


framework = sale_scout.framework
base = sale_scout.base

EXPERIMENT_ID = "exp-20260613-026"
STEM = "form4_tax_withholding_absorption"
TRIAL_FAMILY = "form4_tax_withholding_absorption_candidate_pool"
TRIAL_VARIANT_ID = "form4_tax_withholding_absorption_top1_next_open_10d_v1"
CHANGED_VARIABLE = "form4_tax_withholding_absorption_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = sale_scout.REPO_ROOT
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result  # noqa: E402

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260613_026_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

FORM4_GLOB = "form4_transactions_*.jsonl"
FORM4_DIR = REPO_ROOT / "data" / "non_ohlcv"

BASE_NOTIONAL_USD = sale_scout.BASE_NOTIONAL_USD
HOLD_DAYS = sale_scout.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = sale_scout.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = sale_scout.SAME_TICKER_COOLDOWN_DAYS

MIN_TOTAL_WITHHELD_VALUE_USD = 500_000.0
MIN_EVENT_ROW_VALUE_USD = 50_000.0
WITHHOLDING_TRANSACTION_CODE = "F"
WITHHOLDING_ACQUIRED_DISPOSED_CODE = "D"
REQUIRED_TABLE = "non_derivative"

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = sale_scout.MAX_DRAWDOWN_WORSE
MAX_SINGLE_POSITIVE_SHARE = sale_scout.MAX_SINGLE_POSITIVE_SHARE
MAX_POSITIVE_HHI = sale_scout.MAX_POSITIVE_HHI

ACCEPTED_COMPRESSION_COMPARATOR = sale_scout.ACCEPTED_COMPRESSION_COMPARATOR
ACCEPTED_DISTRIBUTION_COMPARATOR = sale_scout.ACCEPTED_DISTRIBUTION_COMPARATOR
BASE_GATE4 = sale_scout.BASE_GATE4
BASE_BUILD_PAYLOAD = sale_scout.BASE_BUILD_PAYLOAD

PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": 0.25,
    "expected_pnl_delta": 3500.0,
    "main_failure_modes": [
        "routine_compensation_noise",
        "mega_cap_tech_concentration",
        "window_regression",
        "drawdown_drift_too_high",
        "accepted_distribution_comparator_not_beaten",
    ],
    "confidence_reason": (
        "Form 4 F-code rows are PIT-safe and abundant across all three "
        "windows; unlike prior purchase/sale and owner-count/liquidity "
        "retries this tests non-sale RSU/tax-withholding overhang absorption "
        "plus price leadership. Main risk is routine equity-compensation "
        "noise and concentration in tech winners."
    ),
    "recorded_at": "2026-06-13T18:07:25+00:00",
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
    "uses_free_sec_form4": True,
    "uses_free_ohlcv": True,
    "parity_note": (
        "This experiment changes no production code. A positive result would "
        "remain only a replay lead. Promotion would require one shared "
        "default-off adapter that loads the same PIT Form 4 transaction rows, "
        "uses the same non-derivative F/D withholding definition, minimum "
        "ticker-day withheld value, signal-date OHLCV leadership envelope, "
        "same-ticker core overlap exclusion, top-1 next-open paper entry, "
        "10-trading-day exit, costs, cooldown, comparator, and concentration "
        "guards in both historical replay and daily production before any "
        "report queue, paper ledger, candidate priority, sizing, watchlist, "
        "or order surface could change."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: large PIT-safe Form 4 tax-withholding/RSU vesting "
        "clusters are usually routine compensation mechanics, but if the "
        "stock also closes with liquid SPY-relative leadership on the usable "
        "trade date, the tape may be showing compensation-overhang clearing "
        "and insider-retention confirmation rather than open-market selling "
        "pressure."
    ),
    "2_history_check": {
        "exp-20260611-026": (
            "Rejected Form 4 sale absorption leadership. This run deliberately "
            "does not retry sale-side S-code pressure; it tests non-sale F-code "
            "tax-withholding/RSU vesting semantics."
        ),
        "exp-20260609-025": (
            "Form 4 liquidity/cost cluster work froze owner-count and "
            "liquidity-intensity near-neighbor retries without forward "
            "replacement value. This run uses a different transaction-code "
            "event class plus inherited OHLCV leadership."
        ),
        "exp-20260611-007": (
            "Accepted distribution-day absorption comparator. A positive "
            "withholding scout must beat its aggregate EV/PnL before any "
            "promotion pressure."
        ),
        "prior_purchase_family": (
            "Earlier Form 4 purchase queues and owner-count variants were "
            "sparse or rejected. This is not a purchase, owner-count, or "
            "open-market-sale retry."
        ),
        "playbook_fit": (
            "The playbook prioritizes broad PIT candidate sources and warns "
            "against generic OHLCV retunes. This test uses free PIT SEC "
            "transaction data as the source edge and keeps OHLCV gates fixed."
        ),
    },
    "3_single_causal_variable": (
        "One fixed policy bundle: PIT-safe Form 4 non-derivative withholding "
        "rows with transaction_code=F, acquired_disposed_code=D, usable_trade_date, "
        "row value >= $50k, and same-day ticker total withheld value >= $500k; "
        "same ticker core overlap is excluded; the existing liquid leadership "
        "envelope, top-1 next-open paper entry, 10-day hold, costs, cooldown, "
        "comparator, and concentration gates are inherited unchanged."
    ),
    "4_acceptance_standard": (
        "Use docs/backtesting.md three canonical windows. Treat as positive "
        "replay lead only if aggregate EV/PnL improve, no EV/PnL regression "
        "window appears, target sample >=20 across all 3 windows, survival "
        ">=5%, drawdown drift <=0.5pp, concentration guard passes, and both "
        "accepted compression and distribution comparators are beaten. A "
        "shared default-off helper and daily parity path are required for any "
        "retention."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260613_026_form4_tax_withholding_absorption.py"
    ),
}

_EVENT_CACHE: dict[str, Any] | None = None


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _date10(value: Any) -> str:
    return str(value or "")[:10]


def _form4_files() -> list[Path]:
    return sorted(FORM4_DIR.glob(FORM4_GLOB))


def _transaction_value(row: dict[str, Any]) -> float:
    value = _float(row.get("transaction_value"))
    if value is not None:
        return max(value, 0.0)
    shares = _float(row.get("shares"))
    price = _float(row.get("price"))
    if shares is None or price is None:
        return 0.0
    return max(shares * price, 0.0)


def _eligible_withholding_row(row: dict[str, Any]) -> bool:
    if row.get("pit_safe_flag") is False:
        return False
    if str(row.get("table") or "").lower() != REQUIRED_TABLE:
        return False
    if str(row.get("transaction_code") or "").upper() != WITHHOLDING_TRANSACTION_CODE:
        return False
    if (
        str(row.get("acquired_disposed_code") or "").upper()
        != WITHHOLDING_ACQUIRED_DISPOSED_CODE
    ):
        return False
    if not str(row.get("ticker") or "").strip():
        return False
    if not _date10(row.get("usable_trade_date")):
        return False
    return _transaction_value(row) >= MIN_EVENT_ROW_VALUE_USD


def _row_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("accession_number"),
        str(row.get("ticker") or "").upper().strip(),
        row.get("owner_cik"),
        _date10(row.get("transaction_date")),
        row.get("shares"),
        row.get("price"),
        row.get("transaction_value"),
    )


def _context_text(row: dict[str, Any]) -> str:
    return " ".join(
        str(row.get(field) or "")
        for field in ("security_title", "footnote_text", "remarks", "officer_title")
    ).lower()


def _event_from_row(row: dict[str, Any]) -> dict[str, Any]:
    text = _context_text(row)
    return {
        "ticker": str(row.get("ticker") or "").upper().strip(),
        "usable_trade_date": _date10(row.get("usable_trade_date")),
        "filing_date": row.get("filing_date"),
        "accepted_at": row.get("accepted_at"),
        "accession_number": row.get("accession_number"),
        "archive_url": row.get("archive_url"),
        "primary_document": row.get("primary_document"),
        "issuer_name": row.get("issuer_name"),
        "owner_cik": row.get("owner_cik"),
        "owner_name": row.get("owner_name"),
        "is_officer": bool(row.get("is_officer")),
        "is_director": bool(row.get("is_director")),
        "is_10pct_owner": bool(row.get("is_10pct_owner")),
        "officer_title": row.get("officer_title"),
        "transaction_date": _date10(row.get("transaction_date")),
        "transaction_value": round(_transaction_value(row), 2),
        "shares": _float(row.get("shares")),
        "price": _float(row.get("price")),
        "security_title": row.get("security_title"),
        "option_exercise_flag": bool(row.get("option_exercise_flag")),
        "open_market_purchase_flag": bool(row.get("open_market_purchase_flag")),
        "tax_withholding_text_flag": "withhold" in text or "tax" in text,
        "rsu_text_flag": "rsu" in text or "restricted stock" in text,
        "source": row.get("source"),
        "pit_safe_flag": row.get("pit_safe_flag"),
    }


def _load_withholding_events() -> dict[str, Any]:
    global _EVENT_CACHE
    if _EVENT_CACHE is not None:
        return _EVENT_CACHE

    by_date_ticker: dict[str, dict[str, list[dict[str, Any]]]] = {}
    files = _form4_files()
    scan: dict[str, Any] = {
        "source_dir": _repo_rel(FORM4_DIR),
        "source_glob": FORM4_GLOB,
        "source_file_count": len(files),
        "raw_rows": 0,
        "eligible_withholding_rows": 0,
        "duplicate_withholding_rows": 0,
        "below_ticker_total_withheld_value_rows": 0,
        "kept_withholding_rows": 0,
        "withholding_dates": 0,
        "withholding_tickers": 0,
        "min_event_row_value_usd": MIN_EVENT_ROW_VALUE_USD,
        "min_total_withheld_value_usd": MIN_TOTAL_WITHHELD_VALUE_USD,
    }
    ticker_distribution: Counter[str] = Counter()
    owner_role_distribution: Counter[str] = Counter()
    context_distribution: Counter[str] = Counter()
    examples: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    staged: dict[str, dict[str, list[dict[str, Any]]]] = {}

    for path in files:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            scan["raw_rows"] += 1
            row = json.loads(line)
            if not _eligible_withholding_row(row):
                continue
            key = _row_key(row)
            if key in seen:
                scan["duplicate_withholding_rows"] += 1
                continue
            seen.add(key)
            event = _event_from_row(row)
            staged.setdefault(event["usable_trade_date"], {}).setdefault(
                event["ticker"], []
            ).append(event)
            scan["eligible_withholding_rows"] += 1

    for signal_date, by_ticker in staged.items():
        for ticker, events in by_ticker.items():
            total_value = sum(float(event["transaction_value"]) for event in events)
            if total_value < MIN_TOTAL_WITHHELD_VALUE_USD:
                scan["below_ticker_total_withheld_value_rows"] += len(events)
                continue
            by_date_ticker.setdefault(signal_date, {})[ticker] = events
            ticker_distribution[ticker] += len(events)
            scan["kept_withholding_rows"] += len(events)
            for event in events:
                if event["is_officer"]:
                    owner_role_distribution["officer"] += 1
                if event["is_director"]:
                    owner_role_distribution["director"] += 1
                if event["is_10pct_owner"]:
                    owner_role_distribution["ten_pct_owner"] += 1
                if event["tax_withholding_text_flag"]:
                    context_distribution["tax_withholding_text"] += 1
                if event["rsu_text_flag"]:
                    context_distribution["rsu_text"] += 1
                if event["option_exercise_flag"]:
                    context_distribution["option_exercise_flag"] += 1
            if len(examples) < 20:
                top = sorted(
                    events,
                    key=lambda event: (
                        -float(event["transaction_value"]),
                        str(event.get("accepted_at") or ""),
                    ),
                )[0]
                examples.append(
                    {
                        "ticker": ticker,
                        "usable_trade_date": signal_date,
                        "event_count": len(events),
                        "total_withheld_value": round(total_value, 2),
                        "top_owner_name": top.get("owner_name"),
                        "top_security_title": top.get("security_title"),
                        "top_transaction_value": top.get("transaction_value"),
                        "top_accession_number": top.get("accession_number"),
                        "any_option_exercise_flag": any(
                            bool(event.get("option_exercise_flag")) for event in events
                        ),
                    }
                )

    all_tickers = {
        ticker
        for tickers in by_date_ticker.values()
        for ticker in tickers
    }
    scan["withholding_dates"] = len(by_date_ticker)
    scan["withholding_tickers"] = len(all_tickers)
    scan["ticker_distribution_top20"] = dict(ticker_distribution.most_common(20))
    scan["owner_role_distribution"] = dict(sorted(owner_role_distribution.items()))
    scan["context_distribution"] = dict(sorted(context_distribution.items()))

    _EVENT_CACHE = {
        "by_date_ticker": by_date_ticker,
        "scan": scan,
        "examples": examples,
    }
    return _EVENT_CACHE


def _events_for_date(signal_date: str) -> dict[str, list[dict[str, Any]]]:
    return _load_withholding_events()["by_date_ticker"].get(signal_date, {})


def _withholding_stats(events: list[dict[str, Any]], adv20: float) -> dict[str, Any]:
    total_value = sum(float(event["transaction_value"]) for event in events)
    owner_names = {
        str(event.get("owner_name") or "")
        for event in events
        if str(event.get("owner_name") or "")
    }
    owner_ciks = {
        str(event.get("owner_cik") or "")
        for event in events
        if str(event.get("owner_cik") or "")
    }
    withheld_value_to_adv20 = total_value / max(float(adv20), 1.0)
    return {
        "event_count": len(events),
        "owner_count": len(owner_ciks or owner_names),
        "total_withheld_value": round(total_value, 2),
        "max_withheld_value": round(
            max(float(event["transaction_value"]) for event in events), 2
        ),
        "withheld_value_to_adv20": round(withheld_value_to_adv20, 8),
        "officer_withholding_count": sum(
            1 for event in events if event.get("is_officer")
        ),
        "director_withholding_count": sum(
            1 for event in events if event.get("is_director")
        ),
        "ten_pct_owner_withholding_count": sum(
            1 for event in events if event.get("is_10pct_owner")
        ),
        "tax_withholding_text_count": sum(
            1 for event in events if event.get("tax_withholding_text_flag")
        ),
        "rsu_text_count": sum(1 for event in events if event.get("rsu_text_flag")),
        "option_exercise_count": sum(
            1 for event in events if event.get("option_exercise_flag")
        ),
    }


def _withholding_absorption_score(row: dict[str, Any], stats: dict[str, Any]) -> float:
    value_score = min(
        math.log10(1.0 + float(stats["total_withheld_value"]) / 500_000.0), 2.0
    )
    intensity_score = min(float(stats["withheld_value_to_adv20"]) / 0.015, 1.0)
    owner_score = min(float(stats["owner_count"]), 6.0) / 6.0
    officer_bonus = 0.05 if int(stats["officer_withholding_count"]) > 0 else 0.0
    context_bonus = (
        0.04
        if int(stats["tax_withholding_text_count"]) > 0 or int(stats["rsu_text_count"]) > 0
        else 0.0
    )
    score = (
        float(row["candidate_score"])
        + 0.14 * value_score
        + 0.12 * intensity_score
        + 0.05 * owner_score
        + officer_bonus
        + context_bonus
    )
    return round(score, 6)


def _candidate_for_withholding_ticker(
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
        month_label="form4_tax_withholding_absorption",
    )
    if row is None:
        return None

    stats = _withholding_stats(events, float(row["candidate_avg_dollar_volume_20d"]))
    top_event = sorted(
        events,
        key=lambda event: (
            -float(event["transaction_value"]),
            str(event.get("accepted_at") or ""),
            str(event.get("accession_number") or ""),
        ),
    )[0]
    row.pop("candidate_month_label", None)
    row.update(
        {
            "source": "FORM4_TAX_WITHHOLDING_ABSORPTION_PAPER",
            "strategy": TRIAL_FAMILY,
            "rule_version": RULE_VERSION,
            "candidate_form4_tax_withholding_score": _withholding_absorption_score(
                row, stats
            ),
            "candidate_form4_withholding_event_count": stats["event_count"],
            "candidate_form4_withholding_owner_count": stats["owner_count"],
            "candidate_form4_total_withheld_value": stats["total_withheld_value"],
            "candidate_form4_max_withheld_value": stats["max_withheld_value"],
            "candidate_form4_withheld_value_to_adv20": stats[
                "withheld_value_to_adv20"
            ],
            "candidate_form4_officer_withholding_count": stats[
                "officer_withholding_count"
            ],
            "candidate_form4_director_withholding_count": stats[
                "director_withholding_count"
            ],
            "candidate_form4_ten_pct_owner_withholding_count": stats[
                "ten_pct_owner_withholding_count"
            ],
            "candidate_form4_tax_withholding_text_count": stats[
                "tax_withholding_text_count"
            ],
            "candidate_form4_rsu_text_count": stats["rsu_text_count"],
            "candidate_form4_option_exercise_count": stats["option_exercise_count"],
            "candidate_form4_top_owner_name": top_event.get("owner_name"),
            "candidate_form4_top_owner_title": top_event.get("officer_title"),
            "candidate_form4_top_security_title": top_event.get("security_title"),
            "candidate_form4_top_transaction_value": top_event.get(
                "transaction_value"
            ),
            "candidate_form4_top_accession": top_event.get("accession_number"),
            "candidate_form4_top_archive_url": top_event.get("archive_url"),
            "candidate_form4_top_accepted_at": top_event.get("accepted_at"),
            "candidate_form4_top_transaction_date": top_event.get(
                "transaction_date"
            ),
            "uses_free_sec_form4": True,
            "uses_free_ohlcv": True,
            "uses_free_ohlcv_only": False,
            "known_at": "signal_date_form4_usable_trade_date_and_ohlcv_before_next_open_paper_entry",
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
    ticker_distribution: Counter[str] = Counter()
    role_distribution: Counter[str] = Counter()
    scan: dict[str, Any] = {
        "scanned_trading_days": len(dates),
        "days_with_form4_withholding_event_tickers": 0,
        "form4_withholding_event_tickers": 0,
        "days_with_raw_form4_withholding_candidates": 0,
        "raw_form4_withholding_candidates": 0,
        "same_ticker_core_overlap_rejections": 0,
        "source_event_scan": _load_withholding_events()["scan"],
        "source_event_examples": _load_withholding_events()["examples"][:12],
    }

    for signal_date in dates:
        events_by_ticker = _events_for_date(signal_date)
        if not events_by_ticker:
            continue
        scan["days_with_form4_withholding_event_tickers"] += 1
        scan["form4_withholding_event_tickers"] += len(events_by_ticker)

        ab_entries = entries_by_date.get(signal_date, [])
        ab_tickers = {trade.get("ticker") for trade in ab_entries}
        day_rows: list[dict[str, Any]] = []
        for ticker, events in sorted(events_by_ticker.items()):
            if ticker not in sector_entries:
                continue
            if ticker in ab_tickers:
                scan["same_ticker_core_overlap_rejections"] += 1
                continue
            row = _candidate_for_withholding_ticker(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
                events=events,
            )
            if row is None:
                continue
            ticker_distribution[ticker] += 1
            if row["candidate_form4_officer_withholding_count"]:
                role_distribution["officer"] += 1
            if row["candidate_form4_director_withholding_count"]:
                role_distribution["director"] += 1
            if row["candidate_form4_ten_pct_owner_withholding_count"]:
                role_distribution["ten_pct_owner"] += 1
            row["same_day_ab_entry_count"] = len(ab_entries)
            row["same_day_ab_overlap"] = bool(ab_entries)
            row["same_ticker_ab_overlap"] = False
            day_rows.append(row)

        if not day_rows:
            continue
        day_rows.sort(
            key=lambda row: (
                -float(row["candidate_form4_tax_withholding_score"]),
                -float(row["candidate_score"]),
                -float(row["candidate_form4_withheld_value_to_adv20"]),
                -float(row["candidate_ret20_excess_spy"]),
                -float(row["candidate_close_location"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                str(row.get("sector") or ""),
                row["ticker"],
            )
        )
        candidates.extend(day_rows)
        scan["days_with_raw_form4_withholding_candidates"] += 1
        scan["raw_form4_withholding_candidates"] += len(day_rows)
        top = day_rows[0]
        day_contexts.append(
            {
                "date": signal_date,
                "raw_candidate_count": len(day_rows),
                "top_candidate": top["ticker"],
                "top_candidate_score": top["candidate_score"],
                "top_candidate_form4_tax_withholding_score": top[
                    "candidate_form4_tax_withholding_score"
                ],
                "top_candidate_total_withheld_value": top[
                    "candidate_form4_total_withheld_value"
                ],
                "top_candidate_withheld_value_to_adv20": top[
                    "candidate_form4_withheld_value_to_adv20"
                ],
                "top_candidate_ret20_excess_spy": top["candidate_ret20_excess_spy"],
                "top_candidate_close_location": top["candidate_close_location"],
            }
        )

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_form4_tax_withholding_score"]),
            -float(row["candidate_score"]),
            -float(row["candidate_form4_withheld_value_to_adv20"]),
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
            "candidate_ticker_distribution_top20": dict(
                ticker_distribution.most_common(20)
            ),
            "candidate_owner_role_distribution": dict(sorted(role_distribution.items())),
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
        "positive_replay_lead_not_promoted_form4_tax_withholding_absorption"
        if gate["passed"]
        else "rejected_form4_tax_withholding_absorption_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    for trades in payload["target_trades_by_window"].values():
        for trade in trades:
            trade.setdefault("target_price", trade.get("exit_price"))
    payload["backtest_protocol"]["execution_model"] = (
        "Signal uses only PIT Form 4 transaction rows on usable_trade_date plus "
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
            "mechanism_family": "production_visible_free_sec_form4_ohlcv_candidate_pool",
            "new_evidence_type": "form4_tax_withholding_rsu_absorption_plus_ohlcv_leadership",
            "nearby_prior_experiments": [
                "exp-20260611-026",
                "exp-20260609-025",
                "exp-20260611-007",
            ],
            "prior_trial_count": 3,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "accepted_compression_comparator": ACCEPTED_COMPRESSION_COMPARATOR,
            "accepted_distribution_comparator": ACCEPTED_DISTRIBUTION_COMPARATOR,
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the likely reason is that F-code withholding "
                "clusters are routine compensation plumbing rather than "
                "forward demand information. The leadership gate may simply "
                "select the same mega-cap/software winners without an "
                "incremental SEC-source edge, and RSU vesting tax sales may "
                "already be reflected before next-open entry. Do not answer by "
                "sweeping withholding-value thresholds, top-N, hold days, "
                "cooldown, notional, or role weights on these frozen windows."
            ),
            "next_evidence_needed": (
                "A retry needs materially new PIT evidence, such as a daily "
                "shared Form 4 withholding adapter with forward observations, "
                "explicit post-vesting ownership-retention fields, or relation "
                "evidence to accepted source conflicts. Pure threshold, role, "
                "option-exercise, or liquidity retunes stay frozen."
            ),
        }
    )
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "form4_source_dir": _repo_rel(FORM4_DIR),
        "form4_source_glob": FORM4_GLOB,
        "withholding_transaction_code": WITHHOLDING_TRANSACTION_CODE,
        "withholding_acquired_disposed_code": WITHHOLDING_ACQUIRED_DISPOSED_CODE,
        "required_table": REQUIRED_TABLE,
        "min_event_row_value_usd": MIN_EVENT_ROW_VALUE_USD,
        "min_total_withheld_value_usd": MIN_TOTAL_WITHHELD_VALUE_USD,
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
        "form4_source_dir_exists": FORM4_DIR.exists(),
        "form4_file_count": len(_form4_files()),
        "form4_withholding_rows": _load_withholding_events()["scan"],
    }
    payload["gate3_survival_note"] = (
        "Core survival is checked by BASE_GATE4. Target survival is a "
        "default-off overlay candidate sample; no additional filter is added "
        "after Gate 3."
    )
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The Form 4 tax-withholding absorption source did not clear Gate 4. "
            "F-code events were likely routine equity-compensation mechanics, "
            "already digested before next-open execution, or too concentrated "
            "in liquid software/mega-cap names to add replacement value beyond "
            "the existing leadership envelope."
            if not passed
            else (
                "The Form 4 tax-withholding absorption source passed Gate 4, "
                "but it remains only a replay lead until one shared "
                "historical/daily helper proves parity with the same Form 4 "
                "and OHLCV semantics."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping F-code value thresholds, owner roles, "
            "option-exercise flags, top-N, notional, hold days, or cooldown on "
            "these windows."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
    }
    payload["interpretation"] = (
        "The Form 4 tax-withholding absorption source passed as a replay-only "
        "lead, but no production surface changed and a shared default-off "
        "parity adapter is required before use."
        if passed
        else (
            "The Form 4 tax-withholding absorption source was rejected; it did "
            "not establish a distinct free SEC Form 4/OHLCV candidate-pool "
            "edge under the standard three-window protocol."
        )
    )
    payload["rejection_reason"] = (
        None if passed else "; ".join(payload["gate4"].get("failed_reasons", []))
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Withholding days | Candidate days | Trades |",
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
                event_days=scan.get("days_with_form4_withholding_event_tickers", 0),
                days=scan.get("days_with_raw_form4_withholding_candidates", 0),
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
            "- Gate 4 failures: `{}`".format(
                payload["gate4"].get("failed_reasons", [])
            ),
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
                "form4_withholding_event_day_count": payload[
                    "context_scan_by_window"
                ][label].get("days_with_form4_withholding_event_tickers"),
                "raw_candidate_count": payload["context_scan_by_window"][label].get(
                    "raw_form4_withholding_candidates"
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
