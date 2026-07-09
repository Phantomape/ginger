"""exp-20260703-018: SEC Item 1.01 issuer-self contract relation scout.

Observed-only alpha attribution.  The fixed SEC 8-K Item 1.01 contract
relation provenance surface from exp-20260703-017 is compressed into one
issuer-self paper candidate per usable trade date, then measured at next-open
entry and 10-session close against cash, SPY, and QQQ.

No strategy behavior changes here: no entries, ranking, sizing, exits, paper
orders, live orders, prompts, or watchlists are changed.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


EXPERIMENT_ID = "exp-20260703-018"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "sec_item101_contract_relation_issuer_self"
RUNNER = f"quant/experiments/exp_20260703_018_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
SOURCE_ROWS = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / "sec_contract_relation_provenance"
    / "rows.jsonl"
)
SOURCE_SUMMARY = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / "sec_contract_relation_provenance"
    / "latest_summary.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260703_018_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "SEC 8-K Item 1.01 specific contract-relation provenance may identify "
    "issuer-self material-agreement underreaction; a fixed daily top-1 "
    "next-open 10-session paper source should show positive replacement value "
    "versus cash, SPY, and QQQ before any shared default-off promotion."
)
CHANGED_VARIABLE = "sec_item_101_contract_relation_issuer_self_top1_10d_v1"
TRIAL_FAMILY = "sec_item101_contract_relation_issuer_self_candidate_source"
TRIAL_VARIANT_ID = "fixed_relation_priority_top1_10d_v1"
NEARBY_PRIORS = ["exp-20260703-017", "exp-20260702-012", "exp-20260622-004"]
NEW_EVIDENCE_AXIS = (
    "new gate shape: fixed SEC 8-K Item 1.01 contract-relation provenance "
    "surface from exp-20260703-017 with accession-level relation buckets and "
    "evidence snippets; this alpha reads those materialized rows without "
    "changing regexes, item codes, thresholds, hold, notional, or response "
    "curves"
)
PREDICTION = {
    "success_probability": 0.24,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "SEC text source saturation",
        "financing/purchase boilerplate dilution",
        "sparse per-window sample",
        "ticker concentration",
        "public-archive PIT caveat",
    ],
    "confidence_reason": (
        "The new exp-20260703-017 provenance surface is a distinct gate shape "
        "over Item 1.01 contract relations rather than a phrase-threshold "
        "sweep, but nearby SEC text candidate sources have usually failed and "
        "issuer-self material-agreement disclosures can be boilerplate or "
        "already priced."
    ),
    "recorded_at": "2026-07-03T18:04:36+00:00",
}

WINDOWS = {
    "old_thin": ("2024-10-02", "2025-04-22"),
    "mid_weak": ("2025-04-23", "2025-10-22"),
    "late_strong": ("2025-10-23", "2026-04-21"),
}
RELATION_PRIORITY = {
    "customer_or_revenue_contract": 1,
    "supplier_or_supply_contract": 2,
    "license_or_collaboration_agreement": 3,
    "purchase_or_sales_agreement": 4,
    "credit_or_financing_agreement": 5,
    "lease_or_real_estate_agreement": 6,
    "general_material_agreement": 7,
}
PRIMARY_METRICS = [
    "replacement_value_vs_cash_usd",
    "replacement_value_vs_spy_usd",
    "replacement_value_vs_qqq_usd",
]
ACCEPTANCE_RULE = {
    "min_settled_top1_rows": 20,
    "min_settled_windows": 2,
    "min_rows_per_settled_window": 5,
    "min_positive_windows_vs_spy_and_qqq": 2,
    "max_top_ticker_share": 0.40,
    "require_aggregate_primary_means_positive": True,
    "require_aggregate_primary_medians_nonnegative": True,
}
CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260703_018_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        if raw.strip():
            payload = json.loads(raw)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def date10(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value)
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        return text[:10]
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(text[:10], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def numeric_value(row: dict[str, Any], key: str) -> float | None:
    value = row.get(key)
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    return converted if math.isfinite(converted) else None


def summarize_values(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "n": 0,
            "sum": None,
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
            "positive_rate": None,
        }
    return {
        "n": len(values),
        "sum": round(sum(values), 2),
        "mean": round(mean(values), 4),
        "median": round(median(values), 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "positive_rate": round(sum(1 for value in values if value > 0) / len(values), 6),
    }


def metric_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        key: summarize_values(
            [value for row in rows if (value := numeric_value(row, key)) is not None]
        )
        for key in [*PRIMARY_METRICS, "pnl_usd"]
    }


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_PATH, {}) or {}
    windows = list(payload.get("windows") or [])
    generated = sum(int(window.get("signals_generated") or 0) for window in windows)
    survived = sum(int(window.get("signals_survived") or 0) for window in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_PATH),
        "expected_value_score_sum": round(
            sum(float(window.get("expected_value_score") or 0.0) for window in windows),
            4,
        ),
        "total_pnl": round(
            sum(float(window.get("total_pnl") or 0.0) for window in windows),
            2,
        ),
        "trade_count": sum(
            int(window.get("trade_count") or window.get("total_trades") or 0)
            for window in windows
        ),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / max(generated, 1), 6),
        "window_count": len(windows),
    }


def default_warehouse_paths() -> list[Path]:
    return [
        REPO_ROOT / "data" / "warehouse" / "warehouse_main_hot.sqlite",
        REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite",
        REPO_ROOT
        / "data"
        / "experiments"
        / "exp-20260519-030"
        / "warehouse_main.sqlite",
    ]


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def table_columns(con: sqlite3.Connection, table: str) -> dict[str, str]:
    return {
        str(row[1]).lower(): str(row[1])
        for row in con.execute(f"pragma table_info({quote_identifier(table)})")
    }


def load_table_bars(
    con: sqlite3.Connection,
    *,
    table: str,
    tickers: list[str],
) -> list[dict[str, Any]]:
    columns = table_columns(con, table)

    def column(*names: str) -> str | None:
        for name in names:
            if name.lower() in columns:
                return columns[name.lower()]
        return None

    ticker_col = column("ticker", "symbol")
    date_col = column("date", "Date", "timestamp")
    open_col = column("open", "Open")
    high_col = column("high", "High")
    low_col = column("low", "Low")
    close_col = column("close", "Close")
    volume_col = column("volume", "Volume")
    if any(value is None for value in (ticker_col, date_col, open_col, high_col, low_col, close_col)):
        return []
    placeholders = ",".join("?" for _ in tickers)
    select_volume = quote_identifier(volume_col) if volume_col else "null"
    query = f"""
        select
            {quote_identifier(ticker_col)} as ticker,
            {quote_identifier(date_col)} as date,
            {quote_identifier(open_col)} as open,
            {quote_identifier(high_col)} as high,
            {quote_identifier(low_col)} as low,
            {quote_identifier(close_col)} as close,
            {select_volume} as volume
        from {quote_identifier(table)}
        where upper({quote_identifier(ticker_col)}) in ({placeholders})
        order by {quote_identifier(ticker_col)}, {quote_identifier(date_col)}
    """
    return [
        {
            "ticker": str(ticker).upper(),
            "date": date,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
        for ticker, date, open_, high, low, close, volume in con.execute(
            query, [ticker.upper() for ticker in tickers]
        )
    ]


def load_bars(tickers: list[str]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    requested = sorted({str(ticker).upper() for ticker in tickers if str(ticker).strip()})
    bars: dict[str, list[dict[str, Any]]] = {ticker: [] for ticker in requested}
    seen: set[tuple[str, str]] = set()
    sources: list[dict[str, Any]] = []
    for path in default_warehouse_paths():
        source = {"path": str(path), "exists": path.exists(), "tables": [], "returned_rows": 0}
        if not path.exists():
            sources.append(source)
            continue
        try:
            with sqlite3.connect(path) as con:
                tables = {
                    str(row[0])
                    for row in con.execute(
                        "select name from sqlite_master where type='table'"
                    )
                }
                for table in ("ohlcv", "ohlcv_snapshot_versions"):
                    if table not in tables:
                        continue
                    row_count = int(
                        con.execute(
                            f"select count(*) from {quote_identifier(table)}"
                        ).fetchone()[0]
                    )
                    table_info = {
                        "table": table,
                        "row_count": row_count,
                        "returned_rows": 0,
                    }
                    if row_count:
                        rows = load_table_bars(con, table=table, tickers=requested)
                        table_info["returned_rows"] = len(rows)
                        source["returned_rows"] += len(rows)
                        for row in rows:
                            ticker = str(row.get("ticker") or "").upper()
                            day = date10(row.get("date"))
                            if not ticker or not day or ticker not in bars:
                                continue
                            key = (ticker, day)
                            if key in seen:
                                continue
                            seen.add(key)
                            bars[ticker].append(
                                {
                                    **row,
                                    "_date": day,
                                    "open": float(row["open"]),
                                    "close": float(row["close"]),
                                }
                            )
                    source["tables"].append(table_info)
        except Exception as exc:
            source["error"] = str(exc)
        sources.append(source)
    for ticker_rows in bars.values():
        ticker_rows.sort(key=lambda row: row["_date"])
    all_dates = [row["_date"] for ticker_rows in bars.values() for row in ticker_rows]
    return bars, {
        "status": "ok" if all_dates else "no_bars",
        "requested_tickers": len(requested),
        "returned_tickers": len([ticker for ticker, rows in bars.items() if rows]),
        "returned_rows": sum(len(rows) for rows in bars.values()),
        "date_min": min(all_dates) if all_dates else None,
        "date_max": max(all_dates) if all_dates else None,
        "sources": sources,
    }


def first_bar_on_or_after(rows: list[dict[str, Any]], day: str) -> int | None:
    for index, row in enumerate(rows):
        if row["_date"] >= day:
            return index
    return None


def bar_by_date(rows: list[dict[str, Any]], day: str) -> dict[str, Any] | None:
    for row in rows:
        if row["_date"] == day:
            return row
    return None


def pnl_for_bars(entry_bar: dict[str, Any], exit_bar: dict[str, Any], notional: float) -> float:
    return round(notional * (float(exit_bar["close"]) / float(entry_bar["open"]) - 1.0), 2)


def window_for_entry(entry_date: str | None) -> str | None:
    if not entry_date:
        return None
    for label, (start, end) in WINDOWS.items():
        if start <= entry_date <= end:
            return label
    return None


def provenance_rank(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        RELATION_PRIORITY.get(str(row.get("relation_bucket") or ""), 99),
        -int(row.get("evidence_phrase_count") or 0),
        0 if row.get("counterparty_candidates") else 1,
        str(row.get("accepted_at") or ""),
        str(row.get("ticker") or ""),
        str(row.get("accession_number") or ""),
    )


def dedupe_accessions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_accession: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row.get("relation_quality") != "specific_relation_phrase":
            continue
        ticker = str(row.get("ticker") or "").upper()
        usable = date10(row.get("usable_trade_date") or row.get("filing_date"))
        accession = str(row.get("accession_number") or "")
        if not ticker or not usable or not accession:
            continue
        candidate = {**row, "ticker": ticker, "usable_trade_date": usable}
        current = by_accession.get(accession)
        if current is None or provenance_rank(candidate) < provenance_rank(current):
            by_accession[accession] = candidate
    return sorted(by_accession.values(), key=provenance_rank)


def daily_top1(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_day[str(row["usable_trade_date"])].append(row)
    selected = []
    for day, day_rows in by_day.items():
        best = sorted(day_rows, key=provenance_rank)[0]
        selected.append({**best, "selection_date": day, "daily_candidate_count": len(day_rows)})
    return sorted(selected, key=lambda row: (row["selection_date"], provenance_rank(row)))


def build_outcomes(
    selected_rows: list[dict[str, Any]],
    bars: dict[str, list[dict[str, Any]]],
    *,
    horizon: int = 10,
    notional: float = 4000.0,
) -> list[dict[str, Any]]:
    outcomes = []
    for row in selected_rows:
        ticker = str(row.get("ticker") or "").upper()
        ticker_bars = bars.get(ticker, [])
        entry_idx = first_bar_on_or_after(ticker_bars, row["usable_trade_date"])
        base = {
            "observer_only": True,
            "trade_enabled": False,
            "source_experiment": "exp-20260703-017",
            "source_row_key": {
                "accession_number": row.get("accession_number"),
                "relation_bucket": row.get("relation_bucket"),
                "source_text_hash16": row.get("source_text_hash16"),
            },
            "ticker": ticker,
            "selection_date": row["selection_date"],
            "usable_trade_date": row["usable_trade_date"],
            "daily_candidate_count": row.get("daily_candidate_count"),
            "relation_bucket": row.get("relation_bucket"),
            "relation_quality": row.get("relation_quality"),
            "evidence_phrase_count": row.get("evidence_phrase_count"),
            "counterparty_candidate_count": len(row.get("counterparty_candidates") or []),
            "accession_number": row.get("accession_number"),
            "accepted_at": row.get("accepted_at"),
            "filing_date": row.get("filing_date"),
            "horizon_trading_days": horizon,
            "notional_usd": notional,
            "pit_caveat": row.get("pit_caveat"),
        }
        if entry_idx is None:
            outcomes.append({**base, "outcome_status": "unsettled_no_entry_bar"})
            continue
        exit_idx = entry_idx + horizon - 1
        entry_bar = ticker_bars[entry_idx]
        base["entry_date"] = entry_bar["_date"]
        base["entry_open"] = round(float(entry_bar["open"]), 4)
        base["window"] = window_for_entry(entry_bar["_date"])
        if exit_idx >= len(ticker_bars):
            outcomes.append({**base, "outcome_status": "unsettled_horizon"})
            continue
        exit_bar = ticker_bars[exit_idx]
        pnl = pnl_for_bars(entry_bar, exit_bar, notional)
        base.update(
            {
                "exit_date": exit_bar["_date"],
                "exit_close": round(float(exit_bar["close"]), 4),
                "pnl_usd": pnl,
                "replacement_value_vs_cash_usd": pnl,
            }
        )
        missing_comparator = False
        comparator_detail: dict[str, Any] = {}
        for comparator in ("SPY", "QQQ"):
            comp_rows = bars.get(comparator, [])
            comp_entry = bar_by_date(comp_rows, entry_bar["_date"])
            comp_exit = bar_by_date(comp_rows, exit_bar["_date"])
            comp_pnl = (
                pnl_for_bars(comp_entry, comp_exit, notional)
                if comp_entry and comp_exit
                else None
            )
            if comp_pnl is None:
                missing_comparator = True
            base[f"replacement_value_vs_{comparator.lower()}_usd"] = (
                round(pnl - comp_pnl, 2) if comp_pnl is not None else None
            )
            comparator_detail[comparator] = {
                "entry_date": comp_entry["_date"] if comp_entry else None,
                "exit_date": comp_exit["_date"] if comp_exit else None,
                "pnl_usd": comp_pnl,
            }
        base["comparator_detail"] = comparator_detail
        base["outcome_status"] = "missing_comparator_bars" if missing_comparator else "settled"
        outcomes.append(base)
    return outcomes


def group_rows(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key) or "UNKNOWN")].append(row)
    return dict(sorted(grouped.items()))


def group_summaries(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    output = []
    for value, subset in group_rows(rows, key).items():
        metrics = metric_summary(subset)
        output.append(
            {
                key: value,
                "row_count": len(subset),
                "ticker_count": len({row.get("ticker") for row in subset}),
                "metrics": metrics,
                "primary_means_positive": all(
                    (metrics[metric]["mean"] or 0.0) > 0 for metric in PRIMARY_METRICS
                ),
                "spy_and_qqq_means_positive": (
                    (metrics["replacement_value_vs_spy_usd"]["mean"] or 0.0) > 0
                    and (metrics["replacement_value_vs_qqq_usd"]["mean"] or 0.0) > 0
                ),
            }
        )
    return sorted(output, key=lambda item: item["row_count"], reverse=True)


def count_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tickers = Counter(str(row.get("ticker") or "UNKNOWN") for row in rows)
    buckets = Counter(str(row.get("relation_bucket") or "UNKNOWN") for row in rows)
    windows = Counter(str(row.get("window") or "outside") for row in rows)
    total = len(rows)
    return {
        "row_count": total,
        "ticker_count": len(tickers),
        "bucket_count": len(buckets),
        "window_count": len([window for window in windows if window != "outside"]),
        "top_ticker_share": round(tickers.most_common(1)[0][1] / total, 6)
        if total
        else None,
        "top_tickers_by_rows": [
            {"ticker": ticker, "rows": count, "share": round(count / total, 6)}
            for ticker, count in tickers.most_common(10)
        ]
        if total
        else [],
        "relation_buckets_by_rows": [
            {"relation_bucket": bucket, "rows": count, "share": round(count / total, 6)}
            for bucket, count in buckets.most_common()
        ]
        if total
        else [],
        "windows_by_rows": dict(sorted(windows.items())),
    }


def build_result() -> dict[str, Any]:
    timestamp = utc_now()
    baseline = baseline_metrics()
    source_summary = read_json(SOURCE_SUMMARY, {}) or {}
    raw_rows = load_jsonl(SOURCE_ROWS)
    accession_rows = dedupe_accessions(raw_rows)
    selected = daily_top1(accession_rows)
    tickers = sorted({row["ticker"] for row in selected} | {"SPY", "QQQ"})
    bars, warehouse_summary = load_bars(tickers)
    outcomes = build_outcomes(selected, bars)
    settled = [row for row in outcomes if row.get("outcome_status") == "settled"]
    canonical_settled = [row for row in settled if row.get("window") in WINDOWS]
    outside_settled = [row for row in settled if row.get("window") not in WINDOWS]

    overall_metrics = metric_summary(canonical_settled)
    by_window = group_summaries(canonical_settled, "window")
    by_bucket = group_summaries(canonical_settled, "relation_bucket")
    by_ticker = group_summaries(canonical_settled, "ticker")
    counts = count_summary(canonical_settled)

    window_rows = {
        item["window"]: item["row_count"]
        for item in by_window
        if item.get("window") in WINDOWS
    }
    settled_windows = [
        label
        for label, row_count in window_rows.items()
        if row_count >= ACCEPTANCE_RULE["min_rows_per_settled_window"]
    ]
    positive_windows_vs_spy_and_qqq = sum(
        1
        for item in by_window
        if item.get("window") in WINDOWS and item["spy_and_qqq_means_positive"]
    )
    aggregate_means_positive = all(
        (overall_metrics[metric]["mean"] or 0.0) > 0 for metric in PRIMARY_METRICS
    )
    aggregate_medians_nonnegative = all(
        (overall_metrics[metric]["median"] or 0.0) >= 0 for metric in PRIMARY_METRICS
    )
    checks = {
        "settled_top1_rows_min_passed": len(canonical_settled)
        >= ACCEPTANCE_RULE["min_settled_top1_rows"],
        "settled_windows_min_passed": len(settled_windows)
        >= ACCEPTANCE_RULE["min_settled_windows"],
        "positive_windows_vs_spy_and_qqq_passed": positive_windows_vs_spy_and_qqq
        >= ACCEPTANCE_RULE["min_positive_windows_vs_spy_and_qqq"],
        "aggregate_primary_means_positive": aggregate_means_positive,
        "aggregate_primary_medians_nonnegative": aggregate_medians_nonnegative,
        "top_ticker_share_passed": (
            counts["top_ticker_share"] is not None
            and counts["top_ticker_share"] <= ACCEPTANCE_RULE["max_top_ticker_share"]
        ),
    }
    directional_support = all(checks.values())
    failed_reasons = [name for name, passed in checks.items() if not passed]
    if directional_support:
        status = "observed_only_positive_lead"
        decision = "observed_only_positive_sec_item101_contract_relation_issuer_self_lead"
    else:
        status = "observed_only_rejected"
        decision = "observed_only_rejected_no_sec_item101_contract_relation_issuer_self_edge"

    status_counts = Counter(str(row.get("outcome_status") or "unknown") for row in outcomes)
    why = (
        "The fixed daily top-1 Item 1.01 contract-relation issuer-self source "
        "cleared the observed-only replacement-value checks, but it is not "
        "accepted alpha because the historical text cache is a public-archive "
        "PIT proxy and no shared default-off helper was promoted."
        if directional_support
        else "The fixed daily top-1 Item 1.01 contract-relation issuer-self "
        "source did not show enough broad 10-session replacement value after "
        "top-1 compression and ETF opportunity-cost checks."
    )

    result: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "owner": OWNER,
        "lane": LANE,
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": directional_support,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": "candidate_pool_observed_attribution",
        "implementation_mode": "observed_only_attribution",
        "mechanism_family": "sec_contract_relation_candidate_pool_alpha",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": [
            "fixed relation bucket priority",
            "issuer-self candidate source",
            "daily top-1 compression",
            "next-open 10-session outcomes",
            "cash/SPY/QQQ replacement-value verdict",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "new_structured_relation_provenance_surface",
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": PREDICTION,
        "calibration": {
            "actual_success": 1 if directional_support else 0,
            "predicted_success_probability": PREDICTION["success_probability"],
            "brier_score": round(
                (PREDICTION["success_probability"] - (1 if directional_support else 0))
                ** 2,
                4,
            ),
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "realized_failure_modes": failed_reasons
            if failed_reasons
            else ["public-archive PIT caveat"],
            "predicted_failure_mode_hit": bool(failed_reasons),
            "expected_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "actual_ev_delta": 0.0,
            "actual_pnl_delta": 0.0,
            "surprise_note": (
                "Moderate surprise: the fixed relation-provenance source passed "
                "observed-only replacement checks despite the dry SEC text base rate."
                if directional_support
                else "Low surprise: the SEC text candidate-pool base rate is very low, "
                "and issuer-self Item 1.01 relation rows remained noisy after top-1 "
                "compression."
            ),
        },
        "source_artifacts": {
            "source_rows": repo_rel(SOURCE_ROWS),
            "source_summary": repo_rel(SOURCE_SUMMARY),
            "source_summary_payload": source_summary,
            "warehouse_summary": warehouse_summary,
        },
        "policy_bundle": {
            "relation_priority": RELATION_PRIORITY,
            "dedupe": "one best relation row per accession_number by fixed priority, evidence count, counterparty presence, accepted_at, ticker",
            "selection": "one best accession candidate per usable_trade_date by the same fixed rank",
            "entry": "first local OHLCV open on or after usable_trade_date",
            "exit": "10th trading session close after entry",
            "notional_usd": 4000.0,
            "comparators": ["cash", "SPY", "QQQ"],
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "strategy_behavior_changed": False,
        },
        "gate1": {
            "passed": True,
            "baseline_metrics": baseline,
            "note": "Observed-only attribution; canonical strategy baseline unchanged.",
        },
        "gate2": {
            "passed": bool(canonical_settled),
            "fields_checked": [
                "ticker",
                "accession_number",
                "relation_bucket",
                "relation_quality",
                "usable_trade_date",
                "accepted_at",
                "evidence_phrase_count",
                "counterparty_candidates",
                "entry_date",
                "exit_date",
                "replacement_value_vs_cash_usd",
                "replacement_value_vs_spy_usd",
                "replacement_value_vs_qqq_usd",
            ],
            "source_rows": len(raw_rows),
            "accession_deduped_rows": len(accession_rows),
            "daily_top1_candidates": len(selected),
            "canonical_settled_rows": len(canonical_settled),
            "entry_date_present_rows": sum(1 for row in canonical_settled if row.get("entry_date")),
            "target_price_relevance": (
                "This observer-only fixed-horizon paper read does not create "
                "target exits or orders; target_price is not part of the surface."
            ),
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": len(selected),
            "signals_survived": len(canonical_settled),
            "survival_rate": round(len(canonical_settled) / max(len(selected), 1), 6),
            "note": (
                "No executable filter, ranking, sizing, exit, prompt, or order "
                "rule was added. Survival here means daily top-1 candidates with "
                "settled canonical-window 10-session outcomes."
            ),
        },
        "gate4": {
            "passed": directional_support,
            "observed_only": True,
            "accepted_alpha": False,
            "decision": decision,
            "acceptance_rule": ACCEPTANCE_RULE,
            "acceptance_checks": checks,
            "failed_reasons": failed_reasons,
            "strategy_rerun_required": False,
            "before_after_strategy_delta": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
                "strategy_behavior_changed": False,
            },
        },
        "analysis": {
            "source_row_count": len(raw_rows),
            "accession_deduped_row_count": len(accession_rows),
            "daily_top1_candidate_count": len(selected),
            "outcome_status_counts": dict(sorted(status_counts.items())),
            "canonical_settled_counts": counts,
            "outside_canonical_settled_count": len(outside_settled),
            "overall_metrics": overall_metrics,
            "window_summaries": by_window,
            "relation_bucket_summaries": by_bucket,
            "top_ticker_summaries": by_ticker[:12],
            "positive_windows_vs_spy_and_qqq": positive_windows_vs_spy_and_qqq,
            "settled_windows": settled_windows,
            "sample_candidates": canonical_settled[:20],
        },
        "summary": {
            "source_rows": len(raw_rows),
            "accession_deduped_rows": len(accession_rows),
            "daily_top1_candidates": len(selected),
            "canonical_settled_rows": len(canonical_settled),
            "outside_canonical_settled_rows": len(outside_settled),
            "settled_windows": settled_windows,
            "positive_windows_vs_spy_and_qqq": positive_windows_vs_spy_and_qqq,
            "row_mean_cash": overall_metrics["replacement_value_vs_cash_usd"]["mean"],
            "row_mean_spy": overall_metrics["replacement_value_vs_spy_usd"]["mean"],
            "row_mean_qqq": overall_metrics["replacement_value_vs_qqq_usd"]["mean"],
            "row_median_cash": overall_metrics["replacement_value_vs_cash_usd"]["median"],
            "row_median_spy": overall_metrics["replacement_value_vs_spy_usd"]["median"],
            "row_median_qqq": overall_metrics["replacement_value_vs_qqq_usd"]["median"],
            "top_ticker_share": counts["top_ticker_share"],
            "decision": decision,
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_exposed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "feeds_llm_prompt": False,
            "paper_orders_changed": False,
            "live_orders_changed": False,
            "trade_enabled": False,
            "live_realism_evaluated": False,
            "live_ready": False,
            "parity_note": (
                "Read-only analysis over exp-20260703-017 observer provenance "
                "rows. No helper, adapter, order, rank, size, exit, watchlist, "
                "or LLM behavior changed."
            ),
        },
        "rejection_reason": ";".join(failed_reasons) if failed_reasons else None,
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not sweep Item 1.01 relation regexes, item codes, relation "
                "priority, RS/close/volume guards, top-N, hold days, cooldown, "
                "notional, or response curves on these rows. Do not retry issuer-"
                "self contract relation on the same public-archive surface unless "
                "prospective rows mature or relation economics are materially richer."
            ),
            "new_evidence_required": (
                "A valid retry needs normalized counterparty identity, contract "
                "value/duration/revenue-exposure provenance, a counterparty/peer "
                "target-side relation test, or prospectively accumulated daily "
                "rows with closed replacement value under the unchanged rule."
            ),
        },
        "next_retry_requires": [
            "normalized counterparty identity or contract value/duration/revenue exposure",
            "counterparty/peer target-side relation rather than issuer-self retune",
            "prospectively accumulated daily rows with closed replacement value",
            "shared-paper-first helper only if a fixed policy clears observed-only evidence",
        ],
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": "experiment.py new required novelty and saturated-source overrides; both were accepted as a new gate shape from exp-20260703-017.",
                "nearby_prior_experiments": NEARBY_PRIORS,
                "why_not_repeat": NEW_EVIDENCE_AXIS,
            },
            "3_single_policy_bundle": (
                "Fixed issuer-self Item 1.01 relation provenance, accession "
                "dedupe, daily top-1, next-open 10-session outcome, cash/SPY/QQQ "
                "replacement-value verdict."
            ),
            "4_success_failure_standard": (
                "Observed-only lead iff aggregate cash/SPY/QQQ means are positive, "
                "medians nonnegative, at least two windows with >=5 rows are "
                "settled, at least two windows are positive versus SPY and QQQ, "
                "and max ticker share <=40%."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "related_files": [
            RUNNER,
            repo_rel(SOURCE_ROWS),
            repo_rel(SOURCE_SUMMARY),
            "experiments/logs/exp-20260703-017.json",
            "experiments/logs/exp-20260702-012.json",
            "experiments/logs/exp-20260622-004.json",
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "changed_files": CHANGED_FILES,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "lean_quality_passed": True,
    }
    return result


def compact_log_record(result: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "owner",
        "lane",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "observed_only_lead",
        "hypothesis",
        "alpha_hypothesis",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "single_causal_variable",
        "changed_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "prediction",
        "calibration",
        "policy_bundle",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "summary",
        "production_impact",
        "post_run_reflection",
        "next_retry_requires",
        "related_files",
        "changed_files",
        "reproduction_commands",
        "artifact",
        "log",
        "lean_quality_passed",
    ]
    return {key: result[key] for key in keys}


def build_card(result: dict[str, Any]) -> str:
    summary = result["summary"]
    failures = result["gate4"]["failed_reasons"] or ["none"]
    return f"""# Experiment Card: {EXPERIMENT_ID}

## Summary

- Status: `{result["status"]}`
- Decision: `{result["decision"]}`
- Accepted alpha: `false`
- Observed-only lead: `{str(result["observed_only_lead"]).lower()}`
- Daily top-1 candidates: `{summary["daily_top1_candidates"]}`
- Canonical settled rows: `{summary["canonical_settled_rows"]}`
- Settled windows: `{", ".join(summary["settled_windows"]) or "none"}`
- Positive windows vs SPY and QQQ: `{summary["positive_windows_vs_spy_and_qqq"]}`
- Row means cash/SPY/QQQ: `{summary["row_mean_cash"]}` / `{summary["row_mean_spy"]}` / `{summary["row_mean_qqq"]}`
- Row medians cash/SPY/QQQ: `{summary["row_median_cash"]}` / `{summary["row_median_spy"]}` / `{summary["row_median_qqq"]}`
- Top ticker share: `{summary["top_ticker_share"]}`
- Failed checks: `{", ".join(failures)}`

## Boundary

{result["post_run_reflection"]["forbidden_near_neighbor_retry"]}

## Reproduce

```powershell
{RUNNER_COMMAND}
.\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict
```
"""


def update_ticket(result: dict[str, Any]) -> None:
    ticket = read_json(TICKET_JSON, {}) or {}
    ticket["status"] = result["status"]
    ticket["completed_at"] = result["timestamp"]
    ticket["result"] = {
        "decision": result["decision"],
        "artifact": result["artifact"],
        "log": result["log"],
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": result["observed_only_lead"],
    }
    ticket["gate4"] = result["gate4"]
    ticket["post_run_reflection"] = result["post_run_reflection"]
    ticket["next_retry_requires"] = result["next_retry_requires"]
    write_json(TICKET_JSON, ticket)


def write_manifest(result: dict[str, Any]) -> None:
    write_json(
        MANIFEST_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": result["status"],
            "decision": result["decision"],
            "artifact": result["artifact"],
            "log": result["log"],
            "runner": RUNNER,
            "generated_at": result["timestamp"],
            "changed_files": CHANGED_FILES,
            "reproduction_commands": result["reproduction_commands"],
        },
    )


def main() -> int:
    result = build_result()
    write_json(OUT_JSON, result)
    save_experiment_log_entry(compact_log_record(result), allow_duplicate=True)
    write_text(CARD_MD, build_card(result))
    write_manifest(result)
    update_ticket(result)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=PREDICTION,
        result={
            "accepted": False,
            "accepted_alpha": False,
            "alpha_ready": False,
            "observed_only_lead": result["observed_only_lead"],
            "decision": result["decision"],
            "artifact": result["artifact"],
            "log": result["log"],
            "runner": RUNNER,
            "gate4": result["gate4"],
            "summary": result["summary"],
        },
        status=result["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "alpha_hypothesis": HYPOTHESIS,
            "change_type": result["change_type"],
            "implementation_mode": result["implementation_mode"],
            "mechanism_family": result["mechanism_family"],
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": result["causal_components"],
            "nearby_prior_experiments": NEARBY_PRIORS,
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": result["new_evidence_type"],
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "decision": result["decision"],
            "artifact": result["artifact"],
            "log_file": result["log"],
            "card_file": repo_rel(CARD_MD),
            "gate1": result["gate1"],
            "gate2": result["gate2"],
            "gate3": result["gate3"],
            "gate4": result["gate4"],
            "production_impact": result["production_impact"],
            "post_run_reflection": result["post_run_reflection"],
            "next_retry_requires": result["next_retry_requires"],
            "related_files": result["related_files"],
            "changed_files": CHANGED_FILES,
            "allowed_write_scope": CHANGED_FILES,
            "lean_quality_passed": result["lean_quality_passed"],
        },
    )
    print(json.dumps(compact_log_record(result), indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
