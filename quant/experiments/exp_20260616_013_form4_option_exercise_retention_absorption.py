"""exp-20260616-013: Form 4 option-exercise retention absorption.

Replay-only alpha search. This tests one fixed candidate-source variable:
PIT-safe Form 4 non-derivative M/A option-exercise rows where the reporting
insider keeps a large post-exercise share stake and the same accession/owner
does not also report an S/F disposal. The OHLCV leadership envelope, top-1
next-open paper entry, 10-trading-day exit, costs, cooldown, and Gate 4
comparators are inherited from exp-20260611-026.

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

EXPERIMENT_ID = "exp-20260616-013"
STEM = "form4_option_exercise_retention_absorption"
TRIAL_FAMILY = "form4_option_exercise_retention_absorption_candidate_pool"
TRIAL_VARIANT_ID = "form4_option_exercise_retention_absorption_top1_next_open_10d_v1"
CHANGED_VARIABLE = "form4_option_exercise_retention_absorption_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search"

REPO_ROOT = sale_scout.REPO_ROOT
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result  # noqa: E402

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260616_013_{STEM}.json"
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

OPTION_EXERCISE_TRANSACTION_CODE = "M"
OPTION_EXERCISE_ACQUIRED_CODE = "A"
DISPOSAL_CODES = {"S", "F"}
DISPOSAL_ACQUIRED_DISPOSED_CODE = "D"
REQUIRED_EXERCISE_TABLE = "non_derivative"
MIN_TOTAL_EXERCISED_MARKET_VALUE_USD = 500_000.0
MIN_POST_EXERCISE_SHARES_TO_EXERCISED_SHARES = 3.0

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
    "success_probability": 0.12,
    "expected_ev_delta": 0.18,
    "expected_pnl_delta": 2500.0,
    "main_failure_modes": [
        "routine_option_exercise_noise",
        "10b5_1_compensation_plumbing",
        "thin_sample",
        "mega_cap_concentration",
        "accepted_distribution_comparator_not_beaten",
    ],
    "confidence_reason": (
        "This is a high-risk Form 4 near-neighbor, but it uses the materially "
        "new evidence requested after the withholding failure: explicit "
        "post-vesting/post-exercise ownership retention rather than F-code "
        "withholding, sale retention, purchase role, or liquidity threshold "
        "retunes."
    ),
    "recorded_at": "2026-06-16T11:19:04+00:00",
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
        "uses the same non-derivative M/A option-exercise definition, excludes "
        "same-accession same-owner S/F disposals, computes the same "
        "post-exercise shares-to-exercised-shares ratio, applies the same "
        "minimum market value and OHLCV leadership envelope, same-ticker core "
        "overlap exclusion, top-1 next-open paper entry, 10-trading-day exit, "
        "costs, cooldown, comparator, and concentration guards in both "
        "historical replay and daily production before any report queue, paper "
        "ledger, candidate priority, sizing, watchlist, or order surface could "
        "change."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: PIT-safe Form 4 option-exercise M events where the "
        "insider keeps a large post-exercise share stake and no same-accession "
        "sale/tax-disposal appears may indicate equity-compensation conversion "
        "into continued ownership. With the inherited liquid SPY-relative "
        "leadership envelope, next-open paper entries may improve replacement "
        "value without adding noise tickers."
    ),
    "2_history_check": {
        "exp-20260613-026": (
            "Rejected F-code tax-withholding/RSU absorption. Its reflection "
            "froze pure threshold, role, option-exercise, and liquidity "
            "retunes, but explicitly named post-vesting ownership-retention "
            "fields as the materially new evidence needed."
        ),
        "exp-20260616-012": (
            "Rejected sale-side post-sale retention. This run does not retry "
            "S-code sale pressure or retention thresholds; it tests M-code "
            "exercise-and-hold semantics with no same-accession S/F disposal."
        ),
        "exp-20260615-024": (
            "Rejected CEO/CFO low-liability purchase source. This run is not "
            "an open-market purchase, owner-role, or balance-sheet overlay."
        ),
        "exp-20260611-026": (
            "Rejected raw Form 4 sale absorption. This run inherits only the "
            "fixed OHLCV leadership and execution envelope, not sale rows."
        ),
        "exp-20260611-007": (
            "Accepted distribution-day absorption comparator. A positive Form "
            "4 exercise-retention scout must beat it before promotion pressure."
        ),
    },
    "3_single_causal_variable": (
        "One fixed policy bundle: PIT-safe Form 4 non-derivative rows must "
        "have transaction_code=M, acquired_disposed_code=A, option_exercise_"
        "flag, usable_trade_date, no same-accession same-owner non-derivative "
        "S/F D disposal, post_exercise_shares_to_exercised_shares >= 3.0, and "
        "ticker-day exercised market value >= $500k using signal-day close. "
        "The exp-20260611-026 liquid leadership envelope, same-ticker core "
        "overlap exclusion, top-1 next-open paper entry, 10-day hold, costs, "
        "cooldown, comparator, and concentration gates are inherited unchanged."
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
        "exp_20260616_013_form4_option_exercise_retention_absorption.py"
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


def _row_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("accession_number"),
        str(row.get("ticker") or "").upper().strip(),
        row.get("owner_cik"),
        _date10(row.get("transaction_date")),
        row.get("security_title"),
        row.get("shares"),
        row.get("price"),
        row.get("transaction_value"),
        row.get("acquired_disposed_code"),
    )


def _group_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        str(row.get("ticker") or "").upper().strip(),
        row.get("accession_number"),
        row.get("owner_cik") or row.get("owner_name"),
        _date10(row.get("transaction_date")),
    )


def _eligible_exercise_row(row: dict[str, Any]) -> bool:
    if row.get("pit_safe_flag") is False:
        return False
    if str(row.get("table") or "").lower() != REQUIRED_EXERCISE_TABLE:
        return False
    if str(row.get("transaction_code") or "").upper() != OPTION_EXERCISE_TRANSACTION_CODE:
        return False
    if str(row.get("acquired_disposed_code") or "").upper() != OPTION_EXERCISE_ACQUIRED_CODE:
        return False
    if not bool(row.get("option_exercise_flag")):
        return False
    if not str(row.get("ticker") or "").strip():
        return False
    if not _date10(row.get("usable_trade_date")):
        return False
    shares = _float(row.get("shares"))
    post_shares = _float(row.get("shares_owned_following_transaction"))
    return bool(shares and shares > 0.0 and post_shares and post_shares > 0.0)


def _is_same_accession_disposal(row: dict[str, Any]) -> bool:
    if row.get("pit_safe_flag") is False:
        return False
    if str(row.get("table") or "").lower() != REQUIRED_EXERCISE_TABLE:
        return False
    if str(row.get("acquired_disposed_code") or "").upper() != DISPOSAL_ACQUIRED_DISPOSED_CODE:
        return False
    if str(row.get("transaction_code") or "").upper() not in DISPOSAL_CODES:
        return False
    if not str(row.get("ticker") or "").strip():
        return False
    return bool(row.get("accession_number") and (row.get("owner_cik") or row.get("owner_name")))


def _event_from_row(row: dict[str, Any]) -> dict[str, Any]:
    shares = float(_float(row.get("shares")) or 0.0)
    post_shares = float(_float(row.get("shares_owned_following_transaction")) or 0.0)
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
        "shares": shares,
        "shares_owned_following_transaction": post_shares,
        "post_exercise_shares_to_exercised_shares": (
            round(post_shares / shares, 6) if shares > 0.0 else None
        ),
        "exercise_price": _float(row.get("price")),
        "exercise_transaction_value": round(float(_float(row.get("transaction_value")) or 0.0), 2),
        "security_title": row.get("security_title"),
        "10b5_1_flag": bool(row.get("10b5_1_flag")),
        "direct_or_indirect": row.get("direct_or_indirect"),
        "source": row.get("source"),
        "pit_safe_flag": row.get("pit_safe_flag"),
    }


def _load_exercise_events() -> dict[str, Any]:
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
        "eligible_exercise_rows": 0,
        "duplicate_exercise_rows": 0,
        "same_accession_disposal_rows": 0,
        "below_post_exercise_retention_rows": 0,
        "kept_exercise_rows": 0,
        "exercise_dates": 0,
        "exercise_tickers": 0,
        "required_exercise_table": REQUIRED_EXERCISE_TABLE,
        "exercise_transaction_code": OPTION_EXERCISE_TRANSACTION_CODE,
        "exercise_acquired_disposed_code": OPTION_EXERCISE_ACQUIRED_CODE,
        "disposal_codes_excluded": sorted(DISPOSAL_CODES),
        "min_post_exercise_shares_to_exercised_shares": (
            MIN_POST_EXERCISE_SHARES_TO_EXERCISED_SHARES
        ),
    }
    staged: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    disposal_keys: set[tuple[Any, ...]] = set()
    seen: set[tuple[Any, ...]] = set()
    ticker_distribution: Counter[str] = Counter()
    owner_role_distribution: Counter[str] = Counter()
    retention_bucket_distribution: Counter[str] = Counter()
    examples: list[dict[str, Any]] = []

    for path in files:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            scan["raw_rows"] += 1
            row = json.loads(line)
            if _is_same_accession_disposal(row):
                disposal_keys.add(_group_key(row))
            if not _eligible_exercise_row(row):
                continue
            key = _row_key(row)
            if key in seen:
                scan["duplicate_exercise_rows"] += 1
                continue
            seen.add(key)
            staged.setdefault(_group_key(row), []).append(_event_from_row(row))
            scan["eligible_exercise_rows"] += 1

    for group, events in staged.items():
        if group in disposal_keys:
            scan["same_accession_disposal_rows"] += len(events)
            continue
        total_shares = sum(float(event["shares"]) for event in events)
        max_post_shares = max(
            float(event["shares_owned_following_transaction"]) for event in events
        )
        ratio = max_post_shares / total_shares if total_shares > 0.0 else 0.0
        if ratio < MIN_POST_EXERCISE_SHARES_TO_EXERCISED_SHARES:
            scan["below_post_exercise_retention_rows"] += len(events)
            continue

        signal_date = str(events[0]["usable_trade_date"])
        ticker = str(events[0]["ticker"])
        by_date_ticker.setdefault(signal_date, {}).setdefault(ticker, []).extend(events)
        ticker_distribution[ticker] += len(events)
        scan["kept_exercise_rows"] += len(events)
        bucket = "10.00" if ratio >= 10.0 else "5.00" if ratio >= 5.0 else "3.00"
        retention_bucket_distribution[bucket] += len(events)
        for event in events:
            if event["is_officer"]:
                owner_role_distribution["officer"] += 1
            if event["is_director"]:
                owner_role_distribution["director"] += 1
            if event["is_10pct_owner"]:
                owner_role_distribution["ten_pct_owner"] += 1
        if len(examples) < 20:
            top = sorted(
                events,
                key=lambda event: (
                    -float(event["shares"]),
                    str(event.get("accepted_at") or ""),
                    str(event.get("accession_number") or ""),
                ),
            )[0]
            examples.append(
                {
                    "ticker": ticker,
                    "usable_trade_date": signal_date,
                    "event_count": len(events),
                    "total_exercised_shares": round(total_shares, 2),
                    "max_post_exercise_shares": round(max_post_shares, 2),
                    "post_exercise_shares_to_exercised_shares": round(ratio, 6),
                    "top_owner_name": top.get("owner_name"),
                    "top_security_title": top.get("security_title"),
                    "top_accession_number": top.get("accession_number"),
                    "top_exercise_price": top.get("exercise_price"),
                    "any_10b5_1_flag": any(
                        bool(event.get("10b5_1_flag")) for event in events
                    ),
                }
            )

    all_tickers = {
        ticker
        for tickers in by_date_ticker.values()
        for ticker in tickers
    }
    scan["exercise_dates"] = len(by_date_ticker)
    scan["exercise_tickers"] = len(all_tickers)
    scan["ticker_distribution_top20"] = dict(ticker_distribution.most_common(20))
    scan["owner_role_distribution"] = dict(sorted(owner_role_distribution.items()))
    scan["post_exercise_retention_bucket_distribution"] = dict(
        sorted(retention_bucket_distribution.items())
    )

    _EVENT_CACHE = {
        "by_date_ticker": by_date_ticker,
        "scan": scan,
        "examples": examples,
    }
    return _EVENT_CACHE


def _events_for_date(signal_date: str) -> dict[str, list[dict[str, Any]]]:
    return _load_exercise_events()["by_date_ticker"].get(signal_date, {})


def _exercise_stats(events: list[dict[str, Any]], close: float, adv20: float) -> dict[str, Any]:
    total_shares = sum(float(event["shares"]) for event in events)
    max_post_shares = max(
        float(event["shares_owned_following_transaction"]) for event in events
    )
    market_value = total_shares * close
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
    return {
        "event_count": len(events),
        "owner_count": len(owner_ciks or owner_names),
        "total_exercised_shares": round(total_shares, 2),
        "max_exercised_shares": round(max(float(event["shares"]) for event in events), 2),
        "max_post_exercise_shares": round(max_post_shares, 2),
        "post_exercise_shares_to_exercised_shares": round(
            max_post_shares / total_shares, 6
        )
        if total_shares > 0.0
        else None,
        "total_exercised_market_value": round(market_value, 2),
        "exercised_market_value_to_adv20": round(market_value / max(float(adv20), 1.0), 8),
        "officer_exercise_count": sum(1 for event in events if event.get("is_officer")),
        "director_exercise_count": sum(1 for event in events if event.get("is_director")),
        "ten_pct_owner_exercise_count": sum(
            1 for event in events if event.get("is_10pct_owner")
        ),
        "any_10b5_1_flag": any(bool(event.get("10b5_1_flag")) for event in events),
    }


def _exercise_retention_score(row: dict[str, Any], stats: dict[str, Any]) -> float:
    value_score = min(
        math.log10(1.0 + float(stats["total_exercised_market_value"]) / 500_000.0),
        2.0,
    )
    retention_score = min(
        float(stats["post_exercise_shares_to_exercised_shares"] or 0.0) / 10.0,
        1.0,
    )
    intensity_score = min(float(stats["exercised_market_value_to_adv20"]) / 0.02, 1.0)
    score = (
        float(row["candidate_score"])
        + 0.16 * value_score
        + 0.10 * retention_score
        + 0.08 * intensity_score
    )
    return round(score, 6)


def _candidate_for_exercise_ticker(
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
        month_label="form4_option_exercise_retention_absorption",
    )
    if row is None:
        return None

    rows = snapshot.get(ticker) or []
    idx = indices.get(ticker, {}).get(signal_date)
    if idx is None:
        return None
    close = framework._value(rows[idx], "Close")
    if close is None:
        return None

    stats = _exercise_stats(
        events,
        float(close),
        float(row["candidate_avg_dollar_volume_20d"]),
    )
    if float(stats["total_exercised_market_value"]) < MIN_TOTAL_EXERCISED_MARKET_VALUE_USD:
        return None

    top_event = sorted(
        events,
        key=lambda event: (
            -float(event["shares"]),
            str(event.get("accepted_at") or ""),
            str(event.get("accession_number") or ""),
        ),
    )[0]
    row.pop("candidate_month_label", None)
    row.update(
        {
            "source": "FORM4_OPTION_EXERCISE_RETENTION_ABSORPTION_PAPER",
            "strategy": TRIAL_FAMILY,
            "rule_version": RULE_VERSION,
            "candidate_form4_option_exercise_retention_score": _exercise_retention_score(
                row, stats
            ),
            "candidate_form4_exercise_event_count": stats["event_count"],
            "candidate_form4_exercise_owner_count": stats["owner_count"],
            "candidate_form4_total_exercised_shares": stats["total_exercised_shares"],
            "candidate_form4_max_exercised_shares": stats["max_exercised_shares"],
            "candidate_form4_max_post_exercise_shares": stats[
                "max_post_exercise_shares"
            ],
            "candidate_form4_post_exercise_shares_to_exercised_shares": stats[
                "post_exercise_shares_to_exercised_shares"
            ],
            "candidate_form4_total_exercised_market_value": stats[
                "total_exercised_market_value"
            ],
            "candidate_form4_exercised_market_value_to_adv20": stats[
                "exercised_market_value_to_adv20"
            ],
            "candidate_form4_officer_exercise_count": stats["officer_exercise_count"],
            "candidate_form4_director_exercise_count": stats["director_exercise_count"],
            "candidate_form4_ten_pct_owner_exercise_count": stats[
                "ten_pct_owner_exercise_count"
            ],
            "candidate_form4_any_10b5_1_flag": stats["any_10b5_1_flag"],
            "candidate_form4_no_same_accession_disposal": True,
            "candidate_form4_top_owner_name": top_event.get("owner_name"),
            "candidate_form4_top_owner_title": top_event.get("officer_title"),
            "candidate_form4_top_security_title": top_event.get("security_title"),
            "candidate_form4_top_exercise_price": top_event.get("exercise_price"),
            "candidate_form4_top_accession": top_event.get("accession_number"),
            "candidate_form4_top_archive_url": top_event.get("archive_url"),
            "candidate_form4_top_accepted_at": top_event.get("accepted_at"),
            "candidate_form4_top_transaction_date": top_event.get("transaction_date"),
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
        "days_with_form4_exercise_event_tickers": 0,
        "form4_exercise_event_tickers": 0,
        "days_with_raw_form4_exercise_candidates": 0,
        "raw_form4_exercise_candidates": 0,
        "below_market_value_rejections": 0,
        "same_ticker_core_overlap_rejections": 0,
        "source_event_scan": _load_exercise_events()["scan"],
        "source_event_examples": _load_exercise_events()["examples"][:12],
    }

    for signal_date in dates:
        events_by_ticker = _events_for_date(signal_date)
        if not events_by_ticker:
            continue
        scan["days_with_form4_exercise_event_tickers"] += 1
        scan["form4_exercise_event_tickers"] += len(events_by_ticker)

        ab_entries = entries_by_date.get(signal_date, [])
        ab_tickers = {trade.get("ticker") for trade in ab_entries}
        day_rows: list[dict[str, Any]] = []
        for ticker, events in sorted(events_by_ticker.items()):
            if ticker not in sector_entries:
                continue
            if ticker in ab_tickers:
                scan["same_ticker_core_overlap_rejections"] += 1
                continue
            row = _candidate_for_exercise_ticker(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
                events=events,
            )
            if row is None:
                scan["below_market_value_rejections"] += 1
                continue
            ticker_distribution[ticker] += 1
            if row["candidate_form4_officer_exercise_count"]:
                role_distribution["officer"] += 1
            if row["candidate_form4_director_exercise_count"]:
                role_distribution["director"] += 1
            if row["candidate_form4_ten_pct_owner_exercise_count"]:
                role_distribution["ten_pct_owner"] += 1
            row["same_day_ab_entry_count"] = len(ab_entries)
            row["same_day_ab_overlap"] = bool(ab_entries)
            row["same_ticker_ab_overlap"] = False
            day_rows.append(row)

        if not day_rows:
            continue
        day_rows.sort(
            key=lambda row: (
                -float(row["candidate_form4_option_exercise_retention_score"]),
                -float(row["candidate_score"]),
                -float(row["candidate_form4_exercised_market_value_to_adv20"]),
                -float(row["candidate_form4_post_exercise_shares_to_exercised_shares"]),
                -float(row["candidate_ret20_excess_spy"]),
                -float(row["candidate_close_location"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                str(row.get("sector") or ""),
                row["ticker"],
            )
        )
        candidates.extend(day_rows)
        scan["days_with_raw_form4_exercise_candidates"] += 1
        scan["raw_form4_exercise_candidates"] += len(day_rows)
        top = day_rows[0]
        day_contexts.append(
            {
                "date": signal_date,
                "raw_candidate_count": len(day_rows),
                "top_candidate": top["ticker"],
                "top_candidate_score": top["candidate_score"],
                "top_candidate_form4_option_exercise_retention_score": top[
                    "candidate_form4_option_exercise_retention_score"
                ],
                "top_candidate_total_exercised_market_value": top[
                    "candidate_form4_total_exercised_market_value"
                ],
                "top_candidate_exercised_market_value_to_adv20": top[
                    "candidate_form4_exercised_market_value_to_adv20"
                ],
                "top_candidate_post_exercise_shares_to_exercised_shares": top[
                    "candidate_form4_post_exercise_shares_to_exercised_shares"
                ],
                "top_candidate_ret20_excess_spy": top["candidate_ret20_excess_spy"],
                "top_candidate_close_location": top["candidate_close_location"],
            }
        )

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_form4_option_exercise_retention_score"]),
            -float(row["candidate_score"]),
            -float(row["candidate_form4_exercised_market_value_to_adv20"]),
            -float(row["candidate_form4_post_exercise_shares_to_exercised_shares"]),
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
            "min_total_exercised_market_value_usd": (
                MIN_TOTAL_EXERCISED_MARKET_VALUE_USD
            ),
            "min_post_exercise_shares_to_exercised_shares": (
                MIN_POST_EXERCISE_SHARES_TO_EXERCISED_SHARES
            ),
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
        "positive_replay_lead_not_promoted_form4_option_exercise_retention_absorption"
        if gate["passed"]
        else "rejected_form4_option_exercise_retention_absorption_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    for trades in payload["target_trades_by_window"].values():
        for trade in trades:
            trade.setdefault("target_price", trade.get("exit_price"))
    payload["backtest_protocol"]["execution_model"] = (
        "Signal uses only PIT Form 4 option-exercise rows on usable_trade_date "
        "plus close-of-day OHLCV available on the signal date. Eligible rows "
        "must be non-derivative M/A option-exercise acquisitions, have no "
        "same-accession same-owner S/F disposal, retain at least 3x exercised "
        "shares afterward, and clear $500k exercised market value at the "
        "signal close. Paper entry is next available open with existing entry "
        "slippage; exit is the close 10 trading days after the signal with "
        "target-side sell slippage and ROUND_TRIP_COST_PCT."
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
            "new_evidence_type": "form4_post_exercise_ownership_retention_plus_ohlcv_leadership",
            "nearby_prior_experiments": [
                "exp-20260613-026",
                "exp-20260616-012",
                "exp-20260615-024",
                "exp-20260611-026",
                "exp-20260611-007",
            ],
            "prior_trial_count": 5,
            "multiple_testing_risk_bucket": "high",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "accepted_compression_comparator": ACCEPTED_COMPRESSION_COMPARATOR,
            "accepted_distribution_comparator": ACCEPTED_DISTRIBUTION_COMPARATOR,
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the likely reason is that exercise-and-hold rows "
                "are routine compensation or 10b5-1 plumbing rather than "
                "incremental forward demand information. The no-disposal and "
                "post-exercise retention fields may narrow noise but still "
                "select liquid mega-cap/software leadership already captured "
                "by the inherited OHLCV envelope. Do not answer by sweeping "
                "exercise-value thresholds, retention ratios, owner roles, "
                "10b5-1 flags, top-N, notional, hold days, or cooldown on "
                "these frozen windows."
            ),
            "next_evidence_needed": (
                "A retry needs materially new PIT evidence beyond raw Form 4 "
                "exercise-and-hold rows, such as closed daily forward "
                "replacement-value observations from a shared default-off "
                "adapter, parsed executive compensation/holdings context, or "
                "relation evidence that the exercise-retention source conflicts "
                "with accepted source candidates. Pure threshold, role, "
                "10b5-1, option-exercise, or liquidity retunes stay frozen."
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
        "option_exercise_transaction_code": OPTION_EXERCISE_TRANSACTION_CODE,
        "option_exercise_acquired_disposed_code": OPTION_EXERCISE_ACQUIRED_CODE,
        "disposal_codes_excluded": sorted(DISPOSAL_CODES),
        "required_exercise_table": REQUIRED_EXERCISE_TABLE,
        "min_total_exercised_market_value_usd": MIN_TOTAL_EXERCISED_MARKET_VALUE_USD,
        "min_post_exercise_shares_to_exercised_shares": (
            MIN_POST_EXERCISE_SHARES_TO_EXERCISED_SHARES
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
        "form4_option_exercise_rows": _load_exercise_events()["scan"],
    }
    payload["gate3_survival_note"] = (
        "Core survival is checked by BASE_GATE4. Target survival is a "
        "default-off overlay candidate sample; no additional filter is added "
        "after Gate 3."
    )
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The Form 4 option-exercise retention source did not clear Gate 4. "
            "Exercise-and-hold semantics were likely routine compensation "
            "mechanics, already anticipated before next-open execution, or too "
            "concentrated in liquid leadership names to add replacement value "
            "beyond the existing OHLCV envelope."
            if not passed
            else (
                "The Form 4 option-exercise retention source passed Gate 4, "
                "but it remains only a replay lead until one shared historical/"
                "daily helper proves parity with the same Form 4 and OHLCV "
                "semantics."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping exercise-value thresholds, retention "
            "ratios, owner roles, 10b5-1 flags, top-N, notional, hold days, or "
            "cooldown on these windows."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
    }
    payload["interpretation"] = (
        "The Form 4 option-exercise retention source passed as a replay-only "
        "lead, but no production surface changed and a shared default-off "
        "parity adapter is required before use."
        if passed
        else (
            "The Form 4 option-exercise retention source was rejected; it did "
            "not establish a distinct free SEC Form 4/OHLCV candidate-pool edge "
            "under the standard three-window protocol."
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Exercise days | Candidate days | Trades |",
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
                event_days=scan.get("days_with_form4_exercise_event_tickers", 0),
                days=scan.get("days_with_raw_form4_exercise_candidates", 0),
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
                "form4_exercise_event_day_count": payload[
                    "context_scan_by_window"
                ][label].get("days_with_form4_exercise_event_tickers"),
                "raw_candidate_count": payload["context_scan_by_window"][label].get(
                    "raw_form4_exercise_candidates"
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
