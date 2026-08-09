"""Form 4 sale-overhang context logger.

This helper builds a point-in-time, data-only ledger from local daily Form 4
transaction archives. It exposes the fixed sale/10b5/officer-overhang fields
used by exp-20260628-014 and exp-20260629-003 without ranking candidates,
sizing positions, or placing orders.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = REPO_ROOT / "data" / "non_ohlcv"
DEFAULT_CANDIDATE_LEDGER_PATH = (
    REPO_ROOT
    / "data"
    / "paper_sleeves"
    / "candidate_decision_training_ledger"
    / "rows.jsonl"
)
DEFAULT_FORWARD_LEDGER_PATH = (
    DEFAULT_DATA_DIR / "form4_sale_overhang_forward" / "rows.jsonl"
)

SCHEMA_VERSION = 1
RULE_VERSION = "form4_sale_overhang_shared_daily_context_logger_v1"
FORWARD_SCHEMA_VERSION = 1
FORWARD_RULE_VERSION = "form4_sale_overhang_forward_settlement_v1"
FORWARD_EFFECTIVE_DATE = "2026-07-28"
DEFAULT_LOOKBACK_DAYS = 10
FORWARD_HORIZONS = (10, 20)

HIGH_SALE_VALUE_USD = 5_000_000.0
HIGH_OFFICER_SALE_VALUE_USD = 1_000_000.0
HIGH_TEN_B5_SALE_ROWS = 1

OUTCOME_JOIN_SCHEMA = {
    "join_keys": [
        "ticker",
        "entry_date",
        "context_as_of_lte_entry_date",
        "form4_latest_usable_trade_date_lte_context_as_of",
    ],
    "forward_outcome_fields": [
        "cash_replacement_value_10d",
        "cash_replacement_value_20d",
        "spy_replacement_value_10d",
        "spy_replacement_value_20d",
        "qqq_replacement_value_10d",
        "qqq_replacement_value_20d",
        "closed_forward_row",
    ],
    "pit_guard": (
        "Only context rows with context_as_of <= entry_date and underlying "
        "Form 4 usable_trade_date <= context_as_of are eligible for an entry join."
    ),
}

FORWARD_REOPEN_GATE = {
    "closed_forward_rows_min": 25,
    "high_sale_overhang_forward_rows_min": 8,
    "single_ticker_share_max": 0.40,
    "required_replacement_values": ["cash", "SPY", "QQQ"],
    "required_context_rule_version": RULE_VERSION,
    "park_after_materialization_runs_without_new_closable_rows": 3,
}

FORM4_FILE_RE = re.compile(r"form4_transactions_(?P<tag>\d{8})\.jsonl$")
FORM4_CONTEXT_FILE_RE = re.compile(
    r"form4_sale_overhang_context_(?P<tag>\d{8})\.jsonl$"
)


def persist_form4_sale_overhang_context(
    *,
    as_of: str | date | datetime,
    data_dir: str | Path = DEFAULT_DATA_DIR,
    output_dir: str | Path | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> dict[str, Any]:
    """Write the date-stamped Form 4 sale-overhang context ledger."""

    as_of_date = parse_date(as_of)
    if as_of_date is None:
        raise ValueError(f"invalid as_of date: {as_of!r}")
    tag = as_of_date.strftime("%Y%m%d")
    source_root = Path(data_dir)
    root = Path(output_dir) if output_dir is not None else source_root
    rows_path = root / f"form4_sale_overhang_context_{tag}.jsonl"
    summary_path = root / f"form4_sale_overhang_context_summary_{tag}.json"
    rows, build_summary = build_form4_sale_overhang_context_rows(
        as_of=as_of_date,
        data_dir=source_root,
        lookback_days=lookback_days,
    )
    content_identity = form4_context_content_identity(
        rows,
        content_as_of=as_of_date,
    )
    write_jsonl(rows_path, rows)
    summary = {
        **build_summary,
        "status": "ok",
        "asof_date": as_of_date.isoformat(),
        "lookback_days": int(lookback_days),
        "output_path": path_text(rows_path),
        "summary_output": path_text(summary_path),
        "schema_version": SCHEMA_VERSION,
        "rule_version": RULE_VERSION,
        "trade_enabled": False,
        "daily_snapshot_wired": True,
        "entry_context_schema": entry_context_schema(),
        "outcome_join_schema": OUTCOME_JOIN_SCHEMA,
        "forward_reopen_gate": FORWARD_REOPEN_GATE,
        "content_identity": content_identity,
        "production_impact": production_impact("form4_sale_overhang_context_collection"),
    }
    write_json(summary_path, summary)
    return summary


def build_form4_sale_overhang_context_rows(
    *,
    as_of: str | date | datetime,
    data_dir: str | Path = DEFAULT_DATA_DIR,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    as_of_date = parse_date(as_of)
    if as_of_date is None:
        raise ValueError(f"invalid as_of date: {as_of!r}")

    index, source_audit = load_form4_index(data_dir=data_dir, as_of=as_of_date)
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows: list[dict[str, Any]] = []
    for ticker in sorted(index):
        context_rows = form4_rows_for_context(
            index,
            ticker=ticker,
            context_day=as_of_date,
            lookback_days=lookback_days,
        )
        if not context_rows:
            continue
        context = summarize_form4_context(context_rows, lookback_days=lookback_days)
        row = {
            "schema_version": SCHEMA_VERSION,
            "rule_version": RULE_VERSION,
            "asof_date": as_of_date.isoformat(),
            "context_as_of": as_of_date.isoformat(),
            "generated_at": generated_at,
            "ticker": ticker,
            "trade_enabled": False,
            "alters_orders": False,
            "eligible_for_forward_outcome_join": True,
            **context,
            "form4_high_sale_overhang": (
                context["form4_sale_overhang_bucket"] == "high_sale_overhang"
            ),
            "form4_context_sample_transactions": sample_context_rows(context_rows),
        }
        rows.append(row)

    rows.sort(key=lambda row: (str(row.get("ticker") or ""), str(row.get("context_as_of") or "")))
    return rows, summarize_context_rows(rows, source_audit=source_audit)


def load_form4_index(
    *,
    data_dir: str | Path = DEFAULT_DATA_DIR,
    as_of: str | date | datetime | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Load local Form 4 transaction archives, skipping future source files."""

    as_of_date = parse_date(as_of) if as_of is not None else None
    root = Path(data_dir)
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen: set[tuple[Any, ...]] = set()
    files = sorted(root.glob("form4_transactions_*.jsonl"))
    source_files_used: list[str] = []
    source_files_skipped_future = 0
    bad_json_rows = 0
    raw_rows = 0
    rows_loaded = 0
    usable_days: list[date] = []
    transaction_code_counts: Counter[str] = Counter()

    for path in files:
        source_day = source_file_date(path)
        if as_of_date is not None and source_day is not None and source_day > as_of_date:
            source_files_skipped_future += 1
            continue
        try:
            lines = path.read_text(encoding="utf-8-sig").splitlines()
        except OSError:
            continue
        source_files_used.append(path_text(path))
        for line in lines:
            if not line.strip():
                continue
            raw_rows += 1
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                bad_json_rows += 1
                continue
            if not isinstance(row, dict):
                continue
            ticker = str(row.get("ticker") or row.get("issuer_trading_symbol") or "").upper()
            usable_trade_date = parse_date(row.get("usable_trade_date"))
            if not ticker or usable_trade_date is None:
                continue
            if as_of_date is not None and usable_trade_date > as_of_date:
                continue
            key = form4_row_key(row)
            if key in seen:
                continue
            seen.add(key)
            code = str(row.get("transaction_code") or "").upper()
            shares = finite_float(row.get("shares"))
            price = finite_float(row.get("price"))
            transaction_value = finite_float(row.get("transaction_value"))
            if transaction_value is None and shares is not None and price is not None:
                transaction_value = shares * price
            record = {
                "ticker": ticker,
                "usable_trade_date": usable_trade_date,
                "transaction_date": parse_date(row.get("transaction_date")),
                "accepted_at": row.get("accepted_at"),
                "accession_number": row.get("accession_number"),
                "owner_cik": row.get("owner_cik"),
                "owner_name": row.get("owner_name"),
                "transaction_code": code,
                "acquired_disposed_code": row.get("acquired_disposed_code"),
                "transaction_value": transaction_value,
                "shares": shares,
                "price": price,
                "ten_b5_1_flag": truthy(row.get("10b5_1_flag")),
                "is_officer": truthy(row.get("is_officer")),
                "is_director": truthy(row.get("is_director")),
                "is_10pct_owner": truthy(row.get("is_10pct_owner")),
                "open_market_purchase_flag": truthy(row.get("open_market_purchase_flag")),
                "option_exercise_flag": truthy(row.get("option_exercise_flag")),
                "source_file": path_text(path),
            }
            by_ticker[ticker].append(record)
            transaction_code_counts[code] += 1
            usable_days.append(usable_trade_date)
            rows_loaded += 1

    for rows in by_ticker.values():
        rows.sort(key=lambda row: (row["usable_trade_date"], str(row.get("accession_number") or "")))

    return by_ticker, {
        "form4_dir": path_text(root),
        "asof_date": as_of_date.isoformat() if as_of_date else None,
        "source_file_count": len(files),
        "source_files_used": len(source_files_used),
        "source_files_skipped_future": source_files_skipped_future,
        "sample_source_files_used": source_files_used[-8:],
        "raw_jsonl_rows": raw_rows,
        "deduped_rows_loaded": rows_loaded,
        "bad_json_rows": bad_json_rows,
        "ticker_count": len(by_ticker),
        "min_usable_trade_date": min(usable_days).isoformat() if usable_days else None,
        "max_usable_trade_date": max(usable_days).isoformat() if usable_days else None,
        "transaction_code_counts": dict(sorted(transaction_code_counts.items())),
    }


def form4_row_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("accession_number"),
        row.get("ticker") or row.get("issuer_trading_symbol"),
        row.get("owner_cik"),
        row.get("transaction_date"),
        row.get("transaction_code"),
        row.get("acquired_disposed_code"),
        row.get("security_title"),
        row.get("table"),
        row.get("shares"),
        row.get("price"),
    )


def form4_rows_for_context(
    index: dict[str, list[dict[str, Any]]],
    *,
    ticker: str,
    context_day: str | date | datetime | None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> list[dict[str, Any]]:
    day = parse_date(context_day)
    if day is None:
        return []
    start = day - timedelta(days=max(0, int(lookback_days)))
    return [
        row
        for row in index.get(ticker.upper(), [])
        if start <= row["usable_trade_date"] <= day
    ]


def summarize_form4_context(
    rows: list[dict[str, Any]],
    *,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> dict[str, Any]:
    sale_rows = [row for row in rows if row.get("transaction_code") == "S"]
    tax_rows = [row for row in rows if row.get("transaction_code") == "F"]
    purchase_rows = [
        row
        for row in rows
        if row.get("transaction_code") == "P" or row.get("open_market_purchase_flag")
    ]
    exercise_rows = [row for row in rows if row.get("option_exercise_flag")]
    ten_b5_sale_rows = [row for row in sale_rows if row.get("ten_b5_1_flag")]
    officer_sale_rows = [row for row in sale_rows if row.get("is_officer")]

    sale_value = value_sum(sale_rows)
    tax_value = value_sum(tax_rows)
    purchase_value = value_sum(purchase_rows)
    officer_sale_value = value_sum(officer_sale_rows)
    ten_b5_sale_value = value_sum(ten_b5_sale_rows)
    high = (
        sale_value >= HIGH_SALE_VALUE_USD
        or officer_sale_value >= HIGH_OFFICER_SALE_VALUE_USD
        or len(ten_b5_sale_rows) >= HIGH_TEN_B5_SALE_ROWS
    )
    if high:
        bucket = "high_sale_overhang"
    elif sale_rows or tax_rows:
        bucket = "moderate_or_routine_disposal"
    else:
        bucket = "no_sale_overhang"

    return {
        "form4_sale_overhang_bucket": bucket,
        "form4_lookback_calendar_days": int(lookback_days),
        "form4_rows": len(rows),
        "form4_sale_rows": len(sale_rows),
        "form4_tax_withholding_rows": len(tax_rows),
        "form4_purchase_rows": len(purchase_rows),
        "form4_option_exercise_rows": len(exercise_rows),
        "form4_ten_b5_sale_rows": len(ten_b5_sale_rows),
        "form4_officer_sale_rows": len(officer_sale_rows),
        "form4_sale_value_usd": round_float(sale_value, 2),
        "form4_tax_withholding_value_usd": round_float(tax_value, 2),
        "form4_purchase_value_usd": round_float(purchase_value, 2),
        "form4_officer_sale_value_usd": round_float(officer_sale_value, 2),
        "form4_ten_b5_sale_value_usd": round_float(ten_b5_sale_value, 2),
        "form4_net_sale_value_usd": round_float(sale_value - purchase_value, 2),
        "form4_unique_owners": len({row.get("owner_cik") for row in rows if row.get("owner_cik")}),
        "form4_latest_usable_trade_date": (
            max(row["usable_trade_date"] for row in rows).isoformat() if rows else None
        ),
        "form4_sample_accessions": sorted(
            {str(row.get("accession_number")) for row in rows if row.get("accession_number")}
        )[:8],
    }


def latest_form4_sale_overhang_context_for_entry(
    *,
    rows: list[dict[str, Any]],
    ticker: str,
    entry_date: str | date | datetime,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> dict[str, Any]:
    entry_day = parse_date(entry_date)
    if entry_day is None:
        return empty_entry_context(ticker=ticker, entry_date=None, reason="invalid_entry_date")
    start_day = entry_day - timedelta(days=max(0, int(lookback_days)))
    selected: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("ticker") or "").upper() != ticker.upper():
            continue
        context_day = parse_date(row.get("context_as_of") or row.get("asof_date"))
        latest_usable = parse_date(row.get("form4_latest_usable_trade_date"))
        if context_day is None or latest_usable is None:
            continue
        if start_day <= context_day <= entry_day and latest_usable <= context_day:
            selected.append(row)
    if not selected:
        return empty_entry_context(
            ticker=ticker,
            entry_date=entry_day.isoformat(),
            reason="no_pit_form4_sale_overhang_context",
        )
    selected.sort(
        key=lambda row: (
            str(row.get("context_as_of") or row.get("asof_date") or ""),
            str(row.get("form4_latest_usable_trade_date") or ""),
        )
    )
    latest = selected[-1]
    return {
        "ticker": ticker.upper(),
        "entry_date": entry_day.isoformat(),
        "lookback_days": int(lookback_days),
        "form4_context_rows": latest.get("form4_rows"),
        "form4_sale_overhang_bucket": latest.get("form4_sale_overhang_bucket"),
        "form4_high_sale_overhang": bool(latest.get("form4_high_sale_overhang")),
        "form4_sale_rows": latest.get("form4_sale_rows"),
        "form4_ten_b5_sale_rows": latest.get("form4_ten_b5_sale_rows"),
        "form4_officer_sale_rows": latest.get("form4_officer_sale_rows"),
        "form4_sale_value_usd": latest.get("form4_sale_value_usd"),
        "form4_officer_sale_value_usd": latest.get("form4_officer_sale_value_usd"),
        "form4_ten_b5_sale_value_usd": latest.get("form4_ten_b5_sale_value_usd"),
        "form4_latest_usable_trade_date": latest.get("form4_latest_usable_trade_date"),
        "form4_context_as_of": latest.get("context_as_of") or latest.get("asof_date"),
        "eligible_for_forward_outcome_join": True,
    }


def empty_entry_context(*, ticker: str, entry_date: str | None, reason: str) -> dict[str, Any]:
    return {
        "ticker": ticker.upper(),
        "entry_date": entry_date,
        "lookback_days": None,
        "form4_context_rows": 0,
        "form4_sale_overhang_bucket": "no_pit_form4_sale_overhang_context",
        "form4_high_sale_overhang": False,
        "form4_sale_rows": 0,
        "form4_ten_b5_sale_rows": 0,
        "form4_officer_sale_rows": 0,
        "form4_sale_value_usd": None,
        "form4_officer_sale_value_usd": None,
        "form4_ten_b5_sale_value_usd": None,
        "form4_latest_usable_trade_date": None,
        "form4_context_as_of": None,
        "eligible_for_forward_outcome_join": False,
        "reason": reason,
    }


def entry_context_schema() -> dict[str, Any]:
    return {
        "keys": ["ticker", "entry_date"],
        "pit_filter": (
            "context_as_of <= entry_date and underlying Form4 "
            "usable_trade_date <= context_as_of"
        ),
        "context_fields": [
            "form4_context_rows",
            "form4_sale_overhang_bucket",
            "form4_high_sale_overhang",
            "form4_sale_rows",
            "form4_ten_b5_sale_rows",
            "form4_officer_sale_rows",
            "form4_sale_value_usd",
            "form4_latest_usable_trade_date",
            "form4_context_as_of",
        ],
    }


def summarize_context_rows(
    rows: list[dict[str, Any]],
    *,
    source_audit: dict[str, Any],
) -> dict[str, Any]:
    bucket_counts: Counter[str] = Counter(
        str(row.get("form4_sale_overhang_bucket") or "unknown") for row in rows
    )
    usable_days = [
        row.get("form4_latest_usable_trade_date")
        for row in rows
        if row.get("form4_latest_usable_trade_date")
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rows_written": len(rows),
        "ticker_count": len({str(row.get("ticker") or "").upper() for row in rows}),
        "rows_with_form4_sale_rows": sum(1 for row in rows if int(row.get("form4_sale_rows") or 0) > 0),
        "rows_with_high_sale_overhang": sum(1 for row in rows if row.get("form4_high_sale_overhang")),
        "rows_with_ten_b5_sale": sum(1 for row in rows if int(row.get("form4_ten_b5_sale_rows") or 0) > 0),
        "rows_with_officer_sale": sum(1 for row in rows if int(row.get("form4_officer_sale_rows") or 0) > 0),
        "form4_sale_overhang_bucket_counts": dict(sorted(bucket_counts.items())),
        "min_latest_usable_trade_date": min(usable_days) if usable_days else None,
        "max_latest_usable_trade_date": max(usable_days) if usable_days else None,
        "forward_reopen_progress": summarize_forward_reopen_progress(rows),
        "source_audit": source_audit,
    }


def form4_context_content_identity(
    rows: list[dict[str, Any]],
    *,
    content_as_of: str | date | datetime | None = None,
) -> dict[str, Any]:
    """Return a semantic identity for one daily Form4 context snapshot.

    The hash deliberately excludes process-written clocks and the snapshot date.
    A frozen upstream transaction set therefore cannot masquerade as fresh merely
    because another daily process rewrote ``generated_at`` or ``context_as_of``.
    ``content_as_of`` remains a separate freshness clock and is checked together
    with the semantic hash by the forward observer.
    """

    excluded = {"generated_at", "asof_date", "context_as_of"}
    semantic_rows = [
        {
            str(key): safe(value)
            for key, value in row.items()
            if str(key) not in excluded
        }
        for row in rows
        if isinstance(row, Mapping)
    ]
    semantic_rows.sort(
        key=lambda row: (
            str(row.get("ticker") or ""),
            json.dumps(row, ensure_ascii=True, sort_keys=True, separators=(",", ":")),
        )
    )
    payload = json.dumps(
        semantic_rows,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    content_day = parse_date(content_as_of)
    if content_day is None:
        context_days = [
            parse_date(row.get("context_as_of") or row.get("asof_date"))
            for row in rows
        ]
        content_day = max((day for day in context_days if day is not None), default=None)
    usable_days = [
        parse_date(row.get("form4_latest_usable_trade_date")) for row in rows
    ]
    latest_usable = max((day for day in usable_days if day is not None), default=None)
    return {
        "schema_version": 1,
        "identity_type": "semantic_form4_context_rows",
        "algorithm": "sha256",
        "sha256": digest,
        "content_as_of": content_day.isoformat() if content_day else None,
        "row_count": len(semantic_rows),
        "ticker_count": len(
            {str(row.get("ticker") or "").upper() for row in semantic_rows}
        ),
        "max_latest_usable_trade_date": (
            latest_usable.isoformat() if latest_usable else None
        ),
        "rule_version": RULE_VERSION,
    }


def aggregate_form4_sale_overhang_forward_rows(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge append-only decision/outcome records into one row per decision."""

    decisions: dict[str, dict[str, Any]] = {}
    outcomes: dict[tuple[str, int], dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, Mapping):
            continue
        record_type = str(record.get("record_type") or "")
        decision_id = str(record.get("form4_forward_decision_id") or "")
        if not decision_id:
            continue
        if record_type == "form4_sale_overhang_forward_decision":
            decision_day = parse_date(record.get("decision_as_of"))
            effective_day = parse_date(record.get("effective_date"))
            if (
                not truthy(record.get("prospective_forward_evidence"))
                or decision_day is None
                or effective_day is None
                or decision_day < effective_day
            ):
                continue
            decisions.setdefault(decision_id, dict(record))
        elif record_type == "form4_sale_overhang_forward_outcome":
            horizon = _forward_horizon(record)
            if horizon in FORWARD_HORIZONS:
                outcomes.setdefault((decision_id, horizon), dict(record))

    aggregate_rows: list[dict[str, Any]] = []
    for decision_id, decision in decisions.items():
        aggregate = dict(decision)
        aggregate["record_type"] = "form4_sale_overhang_forward_aggregate"
        complete_horizons: list[str] = []
        for horizon in FORWARD_HORIZONS:
            outcome = outcomes.get((decision_id, horizon))
            complete = False
            if outcome is not None:
                cash = finite_float(outcome.get("replacement_value_vs_cash_usd"))
                spy = finite_float(outcome.get("replacement_value_vs_spy_usd"))
                qqq = finite_float(outcome.get("replacement_value_vs_qqq_usd"))
                aggregate[f"cash_replacement_value_{horizon}d"] = cash
                aggregate[f"spy_replacement_value_{horizon}d"] = spy
                aggregate[f"qqq_replacement_value_{horizon}d"] = qqq
                aggregate[f"candidate_return_pct_{horizon}d"] = round_float(
                    outcome.get("candidate_return_pct"),
                    8,
                )
                aggregate[f"spy_return_pct_{horizon}d"] = round_float(
                    outcome.get("spy_return_pct"),
                    8,
                )
                aggregate[f"qqq_return_pct_{horizon}d"] = round_float(
                    outcome.get("qqq_return_pct"),
                    8,
                )
                aggregate[f"exit_date_{horizon}d"] = outcome.get("exit_date")
                complete = cash is not None and spy is not None and qqq is not None
            else:
                aggregate[f"cash_replacement_value_{horizon}d"] = None
                aggregate[f"spy_replacement_value_{horizon}d"] = None
                aggregate[f"qqq_replacement_value_{horizon}d"] = None
                aggregate[f"candidate_return_pct_{horizon}d"] = None
                aggregate[f"spy_return_pct_{horizon}d"] = None
                aggregate[f"qqq_return_pct_{horizon}d"] = None
                aggregate[f"exit_date_{horizon}d"] = None
            if complete:
                complete_horizons.append(f"{horizon}d")
        aggregate["complete_outcome_horizons"] = complete_horizons
        aggregate["required_outcome_horizons"] = [
            f"{horizon}d" for horizon in FORWARD_HORIZONS
        ]
        aggregate["closed_forward_row"] = len(complete_horizons) == len(
            FORWARD_HORIZONS
        )
        aggregate["outcome_status"] = (
            "closed_fixed_10d_20d"
            if aggregate["closed_forward_row"]
            else "pending_fixed_horizon_outcomes"
        )
        aggregate["evidence_grade"] = (
            "settled_forward"
            if aggregate["closed_forward_row"]
            else "PIT_forward_unsettled"
        )
        aggregate_rows.append(aggregate)

    aggregate_rows.sort(
        key=lambda row: (
            str(row.get("decision_as_of") or ""),
            str(row.get("ticker") or ""),
            str(row.get("source_observation_id") or ""),
        )
    )
    return aggregate_rows


def refresh_form4_sale_overhang_forward_ledger(
    *,
    as_of: str | date | datetime,
    candidate_ledger_path: str | Path = DEFAULT_CANDIDATE_LEDGER_PATH,
    candidate_state_path: str | Path | None = None,
    data_dir: str | Path = DEFAULT_DATA_DIR,
    ledger_path: str | Path | None = None,
    state_path: str | Path | None = None,
    effective_date: str | date | datetime = FORWARD_EFFECTIVE_DATE,
) -> dict[str, Any]:
    """Refresh the prospective Form4 decision/outcome observer.

    This function consumes, but never mutates, the candidate-decision training
    ledger.  Only candidate decisions whose immutable ``as_of`` and planned
    ``entry_date`` are both on/after ``effective_date`` may become Form4 forward
    evidence.  Decision context is frozen from daily PIT snapshots before any
    matching fixed-horizon outcome is copied into this observer's own append-only
    ledger.
    """

    run_day = parse_date(as_of)
    effective_day = parse_date(effective_date)
    if run_day is None:
        raise ValueError(f"invalid as_of date: {as_of!r}")
    if effective_day is None:
        raise ValueError(f"invalid effective_date: {effective_date!r}")

    candidate_path = Path(candidate_ledger_path)
    candidate_state = (
        Path(candidate_state_path)
        if candidate_state_path is not None
        else candidate_path.with_name("state.json")
    )
    output_path = Path(ledger_path) if ledger_path is not None else DEFAULT_FORWARD_LEDGER_PATH
    output_state = (
        Path(state_path) if state_path is not None else output_path.with_name("state.json")
    )
    root = Path(data_dir)

    producer_health = _candidate_producer_health(
        run_day=run_day,
        ledger_path=candidate_path,
        state_path=candidate_state,
    )
    context_health, current_context_rows = _current_context_health(
        run_day=run_day,
        data_dir=root,
    )
    health_reasons = [
        *producer_health.get("reasons", []),
        *context_health.get("reasons", []),
    ]
    if health_reasons:
        health_status = (
            "stale"
            if producer_health.get("status") == "stale"
            or context_health.get("status") == "stale"
            else "unavailable"
        )
    else:
        health_status = "ok"
    health = {
        "status": health_status,
        "fail_closed": bool(health_reasons),
        "reasons": health_reasons,
        "candidate_producer": producer_health,
        "current_form4_context": context_health,
    }

    existing_records = _read_jsonl_records(output_path)
    candidate_records = _read_jsonl_records(candidate_path) if not health_reasons else []
    new_decisions: list[dict[str, Any]] = []
    new_outcomes: list[dict[str, Any]] = []
    skipped: Counter[str] = Counter()
    decision_rows_seen = sum(
        1
        for row in candidate_records
        if row.get("record_type") == "candidate_decision_snapshot"
    )
    eligible_decision_rows_seen = 0

    if not health_reasons:
        pit_context_rows = _load_pit_context_rows(data_dir=root, as_of=run_day)
        existing_decision_ids = {
            str(row.get("form4_forward_decision_id"))
            for row in existing_records
            if row.get("record_type") == "form4_sale_overhang_forward_decision"
            and row.get("form4_forward_decision_id")
        }
        existing_outcome_ids = {
            str(row.get("form4_forward_outcome_id"))
            for row in existing_records
            if row.get("record_type") == "form4_sale_overhang_forward_outcome"
            and row.get("form4_forward_outcome_id")
        }
        outcome_horizons = {
            (
                str(row.get("form4_forward_decision_id") or ""),
                _forward_horizon(row),
            )
            for row in existing_records
            if row.get("record_type") == "form4_sale_overhang_forward_outcome"
        }
        decision_by_observation: dict[str, str] = {
            str(row.get("source_observation_id")): str(
                row.get("form4_forward_decision_id")
            )
            for row in existing_records
            if row.get("record_type") == "form4_sale_overhang_forward_decision"
            and row.get("source_observation_id")
            and row.get("form4_forward_decision_id")
        }

        for source in candidate_records:
            if source.get("record_type") != "candidate_decision_snapshot":
                continue
            observation_id = str(source.get("observation_id") or "")
            decision_day = parse_date(source.get("as_of"))
            entry_day = parse_date(source.get("entry_date"))
            if not observation_id or decision_day is None or entry_day is None:
                skipped["missing_decision_identity_or_date"] += 1
                continue
            if decision_day < effective_day or entry_day < effective_day:
                skipped["pre_effective_decision_excluded"] += 1
                continue
            if decision_day > run_day:
                skipped["future_decision_excluded"] += 1
                continue
            eligible_decision_rows_seen += 1
            decision_id = _stable_forward_id(
                "decision",
                observation_id,
                effective_day.isoformat(),
            )
            decision_by_observation[observation_id] = decision_id
            if decision_id in existing_decision_ids:
                skipped["duplicate_decision"] += 1
                continue
            ticker = str(source.get("ticker") or "").upper()
            context = latest_form4_sale_overhang_context_for_entry(
                rows=pit_context_rows,
                ticker=ticker,
                entry_date=entry_day,
                lookback_days=DEFAULT_LOOKBACK_DAYS,
            )
            if not context.get("eligible_for_forward_outcome_join"):
                skipped["no_pit_form4_context"] += 1
                decision_by_observation.pop(observation_id, None)
                continue
            context_day = parse_date(context.get("form4_context_as_of"))
            latest_usable = parse_date(context.get("form4_latest_usable_trade_date"))
            if (
                context_day is None
                or latest_usable is None
                or context_day > entry_day
                or latest_usable > context_day
            ):
                skipped["pit_context_guard_failed"] += 1
                decision_by_observation.pop(observation_id, None)
                continue
            context_payload = {
                key: context.get(key)
                for key in sorted(context)
                if key not in {"ticker", "entry_date"}
            }
            context_sha = hashlib.sha256(
                json.dumps(
                    safe(context_payload),
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            new_decisions.append(
                {
                    "schema_version": FORWARD_SCHEMA_VERSION,
                    "record_type": "form4_sale_overhang_forward_decision",
                    "rule_version": FORWARD_RULE_VERSION,
                    "form4_context_rule_version": RULE_VERSION,
                    "surface_contract": "append_only_form4_sale_overhang_forward_ledger",
                    "form4_forward_decision_id": decision_id,
                    "source_observation_id": observation_id,
                    "source_candidate_rule_version": source.get("rule_version"),
                    "effective_date": effective_day.isoformat(),
                    "decision_as_of": decision_day.isoformat(),
                    "entry_date": entry_day.isoformat(),
                    "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "ticker": ticker,
                    "rank": source.get("rank"),
                    "strategy": source.get("strategy"),
                    "sector": source.get("sector"),
                    "candidate_status": source.get("candidate_status"),
                    "form4_context_row_sha256": context_sha,
                    "prospective_forward_evidence": True,
                    "known_future_leakage": False,
                    "trade_enabled": False,
                    "alters_orders": False,
                    **context_payload,
                }
            )
            existing_decision_ids.add(decision_id)

        for source in candidate_records:
            if source.get("record_type") != "candidate_decision_outcome":
                continue
            observation_id = str(source.get("observation_id") or "")
            decision_id = decision_by_observation.get(observation_id)
            if not decision_id:
                skipped["outcome_without_eligible_form4_decision"] += 1
                continue
            horizon = _forward_horizon(source)
            if horizon not in FORWARD_HORIZONS:
                skipped["non_contract_horizon"] += 1
                continue
            exit_day = parse_date(source.get("exit_date"))
            if exit_day is None or exit_day > run_day:
                skipped["outcome_not_known_as_of"] += 1
                continue
            cash = finite_float(source.get("replacement_value_vs_cash_usd"))
            spy = finite_float(source.get("replacement_value_vs_spy_usd"))
            qqq = finite_float(source.get("replacement_value_vs_qqq_usd"))
            if cash is None or spy is None or qqq is None:
                skipped["outcome_missing_required_replacement_values"] += 1
                continue
            if (decision_id, horizon) in outcome_horizons:
                skipped["duplicate_outcome_horizon"] += 1
                continue
            source_outcome_id = str(source.get("outcome_id") or "")
            outcome_id = _stable_forward_id(
                "outcome",
                decision_id,
                source_outcome_id or f"{horizon}d:{exit_day.isoformat()}",
            )
            if outcome_id in existing_outcome_ids:
                skipped["duplicate_outcome"] += 1
                continue
            new_outcomes.append(
                {
                    "schema_version": FORWARD_SCHEMA_VERSION,
                    "record_type": "form4_sale_overhang_forward_outcome",
                    "rule_version": FORWARD_RULE_VERSION,
                    "surface_contract": "append_only_form4_sale_overhang_forward_ledger",
                    "form4_forward_outcome_id": outcome_id,
                    "form4_forward_decision_id": decision_id,
                    "source_observation_id": observation_id,
                    "source_candidate_outcome_id": source_outcome_id or None,
                    "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "as_of": run_day.isoformat(),
                    "ticker": str(source.get("ticker") or "").upper(),
                    "horizon": f"{horizon}d",
                    "horizon_trading_days": horizon,
                    "entry_date": source.get("entry_date"),
                    "exit_date": exit_day.isoformat(),
                    "candidate_return_pct": round_float(source.get("candidate_return_pct"), 8),
                    "spy_return_pct": round_float(source.get("spy_return_pct"), 8),
                    "qqq_return_pct": round_float(source.get("qqq_return_pct"), 8),
                    "replacement_value_vs_cash_usd": round_float(cash, 2),
                    "replacement_value_vs_spy_usd": round_float(spy, 2),
                    "replacement_value_vs_qqq_usd": round_float(qqq, 2),
                    "label_source": source.get("label_source"),
                    "oracle_label_used": False,
                    "trade_enabled": False,
                    "alters_orders": False,
                }
            )
            existing_outcome_ids.add(outcome_id)
            outcome_horizons.add((decision_id, horizon))

        new_decisions.sort(
            key=lambda row: (
                str(row.get("decision_as_of") or ""),
                str(row.get("ticker") or ""),
                str(row.get("source_observation_id") or ""),
            )
        )
        new_outcomes.sort(
            key=lambda row: (
                str(row.get("form4_forward_decision_id") or ""),
                int(row.get("horizon_trading_days") or 0),
            )
        )
        _append_jsonl_records(output_path, [*new_decisions, *new_outcomes])

    all_records = [*existing_records, *new_decisions, *new_outcomes]
    aggregate_rows = aggregate_form4_sale_overhang_forward_rows(all_records)
    progress = summarize_forward_reopen_progress(aggregate_rows)
    if health_reasons:
        progress["gate_ready"] = False
        progress["not_ready_reasons"] = list(
            dict.fromkeys(
                [*progress.get("not_ready_reasons", []), "observer_health_fail_closed"]
            )
        )
    progress["observer_health_status"] = health_status

    state = {
        "schema_version": FORWARD_SCHEMA_VERSION,
        "rule_version": FORWARD_RULE_VERSION,
        "surface_contract": "append_only_form4_sale_overhang_forward_ledger",
        "status": health_status,
        "as_of": run_day.isoformat(),
        "effective_date": effective_day.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "trade_enabled": False,
        "health": health,
        "decision_rows_seen": decision_rows_seen,
        "eligible_decision_rows_seen": eligible_decision_rows_seen,
        "decision_rows_written": len(new_decisions),
        "outcome_rows_written": len(new_outcomes),
        "aggregate_rows_current": len(aggregate_rows),
        "append_skip_reasons": dict(sorted(skipped.items())),
        "ledger_path": path_text(output_path),
        "state_path": path_text(output_state),
        "candidate_ledger_path": path_text(candidate_path),
        "candidate_state_path": path_text(candidate_state),
        "forward_reopen_progress": progress,
        "production_impact": production_impact(
            "form4_sale_overhang_forward_measurement_only"
        ),
    }
    write_json(output_state, state)
    return state


def _candidate_producer_health(
    *,
    run_day: date,
    ledger_path: Path,
    state_path: Path,
) -> dict[str, Any]:
    reasons: list[str] = []
    state = _load_json_mapping(state_path)
    actual_identity = _ledger_bytes_identity(ledger_path)
    if not ledger_path.is_file():
        reasons.append("candidate_producer_ledger_missing")
    if not state:
        reasons.append("candidate_producer_state_missing")
        producer_day = None
        expected_identity: dict[str, Any] = {}
    else:
        producer_day = parse_date(state.get("last_run_as_of") or state.get("as_of"))
        if producer_day is None:
            reasons.append("candidate_producer_freshness_clock_missing")
        elif producer_day != run_day:
            reasons.append("candidate_producer_stale")
        raw_identity = state.get("ledger_content_identity")
        expected_identity = (
            dict(raw_identity) if isinstance(raw_identity, Mapping) else {}
        )
        if (
            expected_identity.get("status") != "ok"
            or not expected_identity.get("sha256")
        ):
            reasons.append("candidate_producer_content_identity_missing")
        elif any(
            expected_identity.get(key) != actual_identity.get(key)
            for key in ("sha256", "byte_count", "record_count")
        ):
            reasons.append("candidate_producer_content_identity_mismatch")
    status = "ok"
    if reasons:
        status = "stale" if "candidate_producer_stale" in reasons else "unavailable"
    return {
        "status": status,
        "reasons": reasons,
        "expected_as_of": run_day.isoformat(),
        "producer_as_of": producer_day.isoformat() if producer_day else None,
        "ledger_path": path_text(ledger_path),
        "state_path": path_text(state_path),
        "content_identity": expected_identity,
        "verified_content_identity": actual_identity,
    }


def _current_context_health(
    *,
    run_day: date,
    data_dir: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    tag = run_day.strftime("%Y%m%d")
    rows_path = data_dir / f"form4_sale_overhang_context_{tag}.jsonl"
    summary_path = data_dir / f"form4_sale_overhang_context_summary_{tag}.json"
    reasons: list[str] = []
    summary = _load_json_mapping(summary_path)
    rows = _read_jsonl_records(rows_path)
    if not rows_path.is_file():
        reasons.append("current_form4_context_rows_missing")
    if not summary:
        reasons.append("current_form4_context_summary_missing")
    elif summary.get("status") != "ok":
        reasons.append("current_form4_context_status_not_ok")
    if not rows:
        reasons.append("current_form4_context_empty")

    expected_identity = summary.get("content_identity") if summary else None
    if not isinstance(expected_identity, Mapping) or not expected_identity.get("sha256"):
        reasons.append("current_form4_context_content_identity_missing")
        expected_identity = {}
    actual_identity = form4_context_content_identity(rows, content_as_of=run_day)
    if expected_identity:
        if expected_identity.get("content_as_of") != run_day.isoformat():
            reasons.append("current_form4_context_identity_stale")
        if expected_identity.get("sha256") != actual_identity.get("sha256"):
            reasons.append("current_form4_context_identity_mismatch")
        if int(expected_identity.get("row_count") or -1) != len(rows):
            reasons.append("current_form4_context_identity_row_count_mismatch")

    for row in rows:
        context_day = parse_date(row.get("context_as_of") or row.get("asof_date"))
        latest_usable = parse_date(row.get("form4_latest_usable_trade_date"))
        if context_day != run_day:
            reasons.append("current_form4_context_row_stale")
            break
        if latest_usable is None or latest_usable > context_day:
            reasons.append("current_form4_context_pit_guard_failed")
            break

    reasons = list(dict.fromkeys(reasons))
    status = "ok"
    if reasons:
        status = (
            "stale"
            if any("stale" in reason for reason in reasons)
            else "unavailable"
        )
    return (
        {
            "status": status,
            "reasons": reasons,
            "expected_as_of": run_day.isoformat(),
            "rows_path": path_text(rows_path),
            "summary_path": path_text(summary_path),
            "content_identity": dict(expected_identity),
            "verified_content_identity": actual_identity,
        },
        rows,
    )


def _load_pit_context_rows(
    *,
    data_dir: Path,
    as_of: date,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(data_dir.glob("form4_sale_overhang_context_*.jsonl")):
        match = FORM4_CONTEXT_FILE_RE.fullmatch(path.name)
        if not match:
            continue
        try:
            file_day = datetime.strptime(match.group("tag"), "%Y%m%d").date()
        except ValueError:
            continue
        if file_day > as_of:
            continue
        for row in _read_jsonl_records(path):
            context_day = parse_date(row.get("context_as_of") or row.get("asof_date"))
            latest_usable = parse_date(row.get("form4_latest_usable_trade_date"))
            if (
                row.get("rule_version") != RULE_VERSION
                or context_day is None
                or latest_usable is None
                or context_day > as_of
                or latest_usable > context_day
            ):
                continue
            rows.append(row)
    rows.sort(
        key=lambda row: (
            str(row.get("ticker") or ""),
            str(row.get("context_as_of") or row.get("asof_date") or ""),
        )
    )
    return rows


def _forward_horizon(row: Mapping[str, Any]) -> int | None:
    value = row.get("horizon_trading_days")
    if value is None:
        text = str(row.get("horizon") or "").lower().rstrip("d")
        value = text
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _stable_forward_id(*parts: Any) -> str:
    payload = json.dumps(
        [FORWARD_RULE_VERSION, *parts],
        ensure_ascii=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _read_jsonl_records(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return []
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            records.append(row)
    return records


def _ledger_bytes_identity(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except OSError:
        return {
            "status": "missing",
            "sha256": None,
            "byte_count": 0,
            "record_count": 0,
        }
    return {
        "status": "ok",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "byte_count": len(raw),
        "record_count": sum(1 for line in raw.splitlines() if line.strip()),
    }


def _load_json_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def _append_jsonl_records(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(
                json.dumps(safe(row), ensure_ascii=True, sort_keys=True) + "\n"
            )


def summarize_forward_reopen_progress(
    rows: list[dict[str, Any]],
    *,
    gate: dict[str, Any] = FORWARD_REOPEN_GATE,
) -> dict[str, Any]:
    """Report settled-row progress toward the Form4 alpha reopen gate."""

    closed_rows = [row for row in rows if truthy(row.get("closed_forward_row"))]
    high_context_rows = [row for row in rows if truthy(row.get("form4_high_sale_overhang"))]
    high_closed_rows = [
        row for row in closed_rows if truthy(row.get("form4_high_sale_overhang"))
    ]
    complete_closed_rows = [
        row for row in closed_rows if row_has_required_replacement_values(row, gate)
    ]

    closed_by_ticker: Counter[str] = Counter(
        str(row.get("ticker") or "").upper() or "UNKNOWN" for row in closed_rows
    )
    max_single_ticker_share = (
        max(closed_by_ticker.values()) / len(closed_rows) if closed_rows else None
    )

    closed_min = int(gate.get("closed_forward_rows_min") or 0)
    high_min = int(gate.get("high_sale_overhang_forward_rows_min") or 0)
    max_share = finite_float(gate.get("single_ticker_share_max"))
    not_ready_reasons: list[str] = []
    if len(closed_rows) < closed_min:
        not_ready_reasons.append("closed_forward_rows_below_min")
    if len(high_closed_rows) < high_min:
        not_ready_reasons.append("high_sale_overhang_forward_rows_below_min")
    if len(complete_closed_rows) < len(closed_rows):
        not_ready_reasons.append("closed_forward_rows_missing_required_replacement_values")
    if (
        max_share is not None
        and max_single_ticker_share is not None
        and max_single_ticker_share > max_share
    ):
        not_ready_reasons.append("single_ticker_share_above_max")

    return {
        "context_rows_current": len(rows),
        "high_sale_overhang_context_rows_current": len(high_context_rows),
        "closed_forward_rows_current": len(closed_rows),
        "high_sale_overhang_closed_forward_rows_current": len(high_closed_rows),
        "replacement_value_complete_closed_rows_current": len(complete_closed_rows),
        "closed_forward_rows_without_required_replacement_values": (
            len(closed_rows) - len(complete_closed_rows)
        ),
        "unique_tickers_closed_forward_rows": len(closed_by_ticker),
        "max_single_ticker_closed_forward_row_share": round_float(
            max_single_ticker_share,
            6,
        ),
        "gate_ready": not not_ready_reasons,
        "not_ready_reasons": not_ready_reasons,
        "gate": gate,
    }


def row_has_required_replacement_values(
    row: dict[str, Any],
    gate: dict[str, Any] = FORWARD_REOPEN_GATE,
) -> bool:
    required = [str(item).lower() for item in gate.get("required_replacement_values") or []]
    for benchmark in required:
        prefix = f"{benchmark}_replacement_value"
        values = [
            value
            for key, value in row.items()
            if str(key).lower().startswith(prefix)
        ]
        if not any(finite_float(value) is not None for value in values):
            return False
    return True


def sample_context_rows(rows: list[dict[str, Any]], *, limit: int = 8) -> list[dict[str, Any]]:
    sample = []
    for row in sorted(rows, key=lambda item: item["usable_trade_date"], reverse=True)[:limit]:
        sample.append(
            {
                "usable_trade_date": row["usable_trade_date"].isoformat(),
                "transaction_date": (
                    row["transaction_date"].isoformat() if row.get("transaction_date") else None
                ),
                "accession_number": row.get("accession_number"),
                "owner_cik": row.get("owner_cik"),
                "owner_name": row.get("owner_name"),
                "transaction_code": row.get("transaction_code"),
                "transaction_value": round_float(row.get("transaction_value"), 2),
                "ten_b5_1_flag": bool(row.get("ten_b5_1_flag")),
                "is_officer": bool(row.get("is_officer")),
                "source_file": row.get("source_file"),
            }
        )
    return sample


def source_file_date(path: Path) -> date | None:
    match = FORM4_FILE_RE.search(path.name)
    if not match:
        return None
    try:
        return datetime.strptime(match.group("tag"), "%Y%m%d").date()
    except ValueError:
        return None


def value_sum(rows: list[dict[str, Any]]) -> float:
    return sum(float(row.get("transaction_value") or 0.0) for row in rows)


def parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text[:10]).date()
    except ValueError:
        return None


def finite_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def round_float(value: Any, digits: int = 6) -> float | None:
    number = finite_float(value)
    if number is None:
        return None
    return round(number, digits)


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y"}


def production_impact(scope: str) -> dict[str, Any]:
    return {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": True,
        "replay_only": False,
        "trade_enabled": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_orders": False,
        "scope": scope,
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(safe(row), ensure_ascii=True, sort_keys=True) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def path_text(path: str | Path | None) -> str | None:
    if path is None:
        return None
    return str(path).replace("\\", "/")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Write Form 4 sale-overhang context rows.")
    parser.add_argument("--as-of", required=True, help="As-of date YYYY-MM-DD")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    summary = persist_form4_sale_overhang_context(
        as_of=args.as_of,
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        lookback_days=args.lookback_days,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
