from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import mean, median
from typing import Any


EXPERIMENT_ID = "exp-20260512-101"
WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
    },
}
BASELINE_METRICS = {
    "late_strong": {
        "expected_value_score": 4.2340,
        "total_pnl": 94086.91,
        "sharpe_daily": 4.50,
        "max_drawdown_pct": 0.0548,
        "trade_count": 19,
        "survival_rate": 0.8039,
    },
    "mid_weak": {
        "expected_value_score": 1.6689,
        "total_pnl": 61813.40,
        "sharpe_daily": 2.70,
        "max_drawdown_pct": 0.0941,
        "trade_count": 21,
        "survival_rate": 0.7925,
    },
    "old_thin": {
        "expected_value_score": 0.3853,
        "total_pnl": 28544.11,
        "sharpe_daily": 1.35,
        "max_drawdown_pct": 0.0815,
        "trade_count": 22,
        "survival_rate": 0.9167,
    },
}


def parse_day(value: Any) -> date | None:
    text = str(value or "")[:10]
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if isinstance(obj, dict):
                rows.append(obj)
    return rows


def numeric(value: Any) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(result) or math.isinf(result):
        return 0.0
    return result


def is_eligible_purchase(row: dict[str, Any]) -> bool:
    return (
        bool(row.get("open_market_purchase_flag"))
        and bool(row.get("pit_safe_flag"))
        and str(row.get("acquired_disposed_code") or "").upper() == "A"
        and not bool(row.get("10b5_1_flag"))
        and not bool(row.get("option_exercise_flag"))
        and bool(row.get("is_officer") or row.get("is_director") or row.get("is_10pct_owner"))
        and numeric(row.get("transaction_value")) > 0
    )


def owner_id(row: dict[str, Any]) -> str:
    return str(row.get("owner_cik") or row.get("owner_name") or "").strip().upper()


def build_daily_purchase_events(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, date], dict[str, Any]] = {}
    for row in rows:
        if not is_eligible_purchase(row):
            continue
        ticker = str(row.get("ticker") or "").upper()
        usable_day = parse_day(row.get("usable_trade_date"))
        owner = owner_id(row)
        if not ticker or not usable_day or not owner:
            continue
        key = (ticker, usable_day)
        event = grouped.setdefault(
            key,
            {
                "ticker": ticker,
                "usable_trade_date": usable_day.isoformat(),
                "owners": set(),
                "accessions": set(),
                "transaction_count": 0,
                "total_purchase_value": 0.0,
                "max_purchase_value": 0.0,
                "sample_owner_names": [],
                "sample_officer_titles": [],
            },
        )
        value = numeric(row.get("transaction_value"))
        event["owners"].add(owner)
        if row.get("accession_number"):
            event["accessions"].add(str(row["accession_number"]))
        event["transaction_count"] += 1
        event["total_purchase_value"] += value
        event["max_purchase_value"] = max(event["max_purchase_value"], value)
        append_sample(event["sample_owner_names"], row.get("owner_name"))
        append_sample(event["sample_officer_titles"], row.get("officer_title"))

    events = []
    for event in grouped.values():
        owners = sorted(event.pop("owners"))
        accessions = sorted(event.pop("accessions"))
        event["owner_count"] = len(owners)
        event["accession_count"] = len(accessions)
        event["sample_owner_ids"] = owners[:4]
        event["sample_accessions"] = accessions[:4]
        event["total_purchase_value"] = round(event["total_purchase_value"], 2)
        event["max_purchase_value"] = round(event["max_purchase_value"], 2)
        events.append(event)
    return sorted(events, key=lambda item: (item["usable_trade_date"], item["ticker"]))


def append_sample(values: list[Any], value: Any) -> None:
    if value and value not in values and len(values) < 4:
        values.append(value)


def build_multi_owner_clusters(daily_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in daily_events:
        by_ticker[event["ticker"]].append(event)

    clusters: list[dict[str, Any]] = []
    for ticker, events in by_ticker.items():
        parsed = [(parse_day(event["usable_trade_date"]), event) for event in events]
        parsed = [(day, event) for day, event in parsed if day]
        for day, event in parsed:
            window_start = day - timedelta(days=9)
            members = [
                prior for prior_day, prior in parsed
                if prior_day and window_start <= prior_day <= day
            ]
            owner_ids = sorted({
                owner
                for member in members
                for owner in member.get("sample_owner_ids", [])
            })
            total_value = sum(numeric(member.get("total_purchase_value")) for member in members)
            if len(owner_ids) < 2 or total_value < 500_000:
                continue
            clusters.append({
                "ticker": ticker,
                "cluster_end_date": day.isoformat(),
                "cluster_start_date": window_start.isoformat(),
                "event_count": len(members),
                "owner_count": len(owner_ids),
                "total_purchase_value": round(total_value, 2),
                "max_single_day_purchase_value": max(numeric(member.get("max_purchase_value")) for member in members),
                "source_event_dates": sorted({member["usable_trade_date"] for member in members}),
                "sample_owner_names": sorted({
                    str(name)
                    for member in members
                    for name in member.get("sample_owner_names", [])
                    if name
                })[:6],
                "sample_accessions": [
                    accession
                    for member in members
                    for accession in member.get("sample_accessions", [])
                ][:6],
            })
    return dedupe_overlapping_clusters(clusters)


def dedupe_overlapping_clusters(clusters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    last_end_by_ticker: dict[str, date] = {}
    for cluster in sorted(clusters, key=lambda item: (item["cluster_end_date"], item["ticker"])):
        ticker = cluster["ticker"]
        end_day = parse_day(cluster["cluster_end_date"])
        last_end = last_end_by_ticker.get(ticker)
        if end_day is None:
            continue
        if last_end and (end_day - last_end).days <= 9:
            continue
        selected.append(cluster)
        last_end_by_ticker[ticker] = end_day
    return selected


def load_price_series(snapshot_path: Path) -> dict[str, list[dict[str, Any]]]:
    snapshot = load_json(snapshot_path)
    return {
        ticker.upper(): sorted(rows, key=lambda row: row["Date"])
        for ticker, rows in snapshot.get("ohlcv", {}).items()
        if isinstance(rows, list)
    }


def forward_return(
    series: dict[str, list[dict[str, Any]]],
    ticker: str,
    start_day: str,
    horizon: int,
) -> float | None:
    rows = series.get(ticker.upper())
    if not rows:
        return None
    idx = next((i for i, row in enumerate(rows) if str(row.get("Date")) >= start_day), None)
    if idx is None or idx + horizon >= len(rows):
        return None
    entry = numeric(rows[idx].get("Open")) or numeric(rows[idx].get("Close"))
    exit_price = numeric(rows[idx + horizon].get("Close"))
    if entry <= 0 or exit_price <= 0:
        return None
    return exit_price / entry - 1.0


def summarize(values: list[float]) -> dict[str, Any]:
    clean = [value for value in values if value is not None]
    if not clean:
        return {"count": 0, "mean": None, "median": None, "win_rate": None, "min": None, "max": None}
    return {
        "count": len(clean),
        "mean": round(mean(clean), 6),
        "median": round(median(clean), 6),
        "win_rate": round(sum(1 for value in clean if value > 0) / len(clean), 6),
        "min": round(min(clean), 6),
        "max": round(max(clean), 6),
    }


def run_backtest_trades(window: dict[str, str]) -> list[dict[str, Any]]:
    import sys

    repo = Path(__file__).resolve().parents[2]
    quant_dir = repo / "quant"
    if str(quant_dir) not in sys.path:
        sys.path.insert(0, str(quant_dir))
    try:
        from backtester import BacktestEngine
        from data_layer import get_universe
    except Exception:
        return []
    engine = BacktestEngine(
        get_universe(),
        start=window["start"],
        end=window["end"],
        ohlcv_snapshot_path=window["snapshot"],
    )
    result = engine.run()
    return result.get("trades") or []


def analyze_window(
    label: str,
    window: dict[str, str],
    clusters: list[dict[str, Any]],
    repo: Path,
    include_backtest_overlap: bool,
) -> dict[str, Any]:
    series = load_price_series(repo / window["snapshot"])
    start = window["start"]
    end = window["end"]
    window_clusters = [
        dict(cluster)
        for cluster in clusters
        if start <= cluster["cluster_end_date"] <= end
    ]
    trades = run_backtest_trades(window) if include_backtest_overlap else []
    trade_keys = {(trade.get("ticker"), trade.get("entry_date")) for trade in trades}
    trade_by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        trade_by_day[str(trade.get("entry_date"))].append(trade)

    rows = []
    returns_by_horizon: dict[int, list[float]] = {5: [], 10: [], 20: []}
    excess_by_horizon: dict[int, list[float]] = {5: [], 10: [], 20: []}
    overlap_same_ticker_date = 0
    same_day_core_alternatives = 0
    replacement_values_10d: list[float] = []

    for cluster in window_clusters:
        row = dict(cluster)
        row["overlap_same_ticker_date"] = (cluster["ticker"], cluster["cluster_end_date"]) in trade_keys
        row["same_day_core_trade_count"] = len(trade_by_day.get(cluster["cluster_end_date"], []))
        if row["overlap_same_ticker_date"]:
            overlap_same_ticker_date += 1
        if row["same_day_core_trade_count"]:
            same_day_core_alternatives += 1
        for horizon in (5, 10, 20):
            ret = forward_return(series, cluster["ticker"], cluster["cluster_end_date"], horizon)
            spy = forward_return(series, "SPY", cluster["cluster_end_date"], horizon)
            row[f"forward_{horizon}d_return"] = round(ret, 6) if ret is not None else None
            row[f"forward_{horizon}d_spy_excess"] = (
                round(ret - spy, 6) if ret is not None and spy is not None else None
            )
            if ret is not None:
                returns_by_horizon[horizon].append(ret)
            if ret is not None and spy is not None:
                excess_by_horizon[horizon].append(ret - spy)
        core_same_day_returns = [
            numeric(trade.get("pnl_pct_net"))
            for trade in trade_by_day.get(cluster["cluster_end_date"], [])
            if trade.get("pnl_pct_net") is not None
        ]
        if row.get("forward_10d_return") is not None and core_same_day_returns:
            replacement_values_10d.append(row["forward_10d_return"] - mean(core_same_day_returns))
            row["forward_10d_vs_same_day_core_trade_avg"] = round(replacement_values_10d[-1], 6)
        else:
            row["forward_10d_vs_same_day_core_trade_avg"] = None
        rows.append(row)

    return {
        "window": label,
        "date_range": {"start": start, "end": end},
        "baseline_metrics": BASELINE_METRICS[label],
        "candidate_count": len(window_clusters),
        "unique_tickers": sorted({cluster["ticker"] for cluster in window_clusters}),
        "overlap_same_ticker_date_count": overlap_same_ticker_date,
        "same_day_core_alternative_count": same_day_core_alternatives,
        "core_trade_count_available": len(trades),
        "forward_return_distribution": {
            f"{horizon}d": summarize(returns_by_horizon[horizon])
            for horizon in (5, 10, 20)
        },
        "spy_excess_distribution": {
            f"{horizon}d": summarize(excess_by_horizon[horizon])
            for horizon in (5, 10, 20)
        },
        "scarce_slot_replacement_value": {
            "method": "10d event return minus average pnl_pct_net of same-day executed core trades, when any existed",
            "count": len(replacement_values_10d),
            "distribution": summarize(replacement_values_10d),
        },
        "sample_candidates": rows[:20],
    }


def aggregate_windows(by_window: dict[str, dict[str, Any]]) -> dict[str, Any]:
    total_candidates = sum(row["candidate_count"] for row in by_window.values())
    all_10d = [
        candidate["forward_10d_return"]
        for row in by_window.values()
        for candidate in row["sample_candidates"]
        if candidate.get("forward_10d_return") is not None
    ]
    all_10d_excess = [
        candidate["forward_10d_spy_excess"]
        for row in by_window.values()
        for candidate in row["sample_candidates"]
        if candidate.get("forward_10d_spy_excess") is not None
    ]
    return {
        "candidate_count": total_candidates,
        "windows_with_candidates": sum(1 for row in by_window.values() if row["candidate_count"] > 0),
        "unique_tickers": sorted({
            ticker
            for row in by_window.values()
            for ticker in row["unique_tickers"]
        }),
        "overlap_same_ticker_date_count": sum(row["overlap_same_ticker_date_count"] for row in by_window.values()),
        "same_day_core_alternative_count": sum(row["same_day_core_alternative_count"] for row in by_window.values()),
        "forward_10d_distribution": summarize(all_10d),
        "spy_excess_10d_distribution": summarize(all_10d_excess),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--include-backtest-overlap", action="store_true")
    parser.add_argument(
        "--output",
        default=f"data/experiments/{EXPERIMENT_ID}/exp_20260512_101_form4_multi_owner_buy_cluster_shadow.json",
    )
    args = parser.parse_args()

    repo = Path(args.repo_root).resolve()
    transactions_path = repo / "data/non_ohlcv/form4_transactions_20241002_20260502.jsonl"
    rows = load_jsonl(transactions_path)
    daily_events = build_daily_purchase_events(rows)
    clusters = build_multi_owner_clusters(daily_events)
    by_window = {
        label: analyze_window(label, window, clusters, repo, args.include_backtest_overlap)
        for label, window in WINDOWS.items()
    }
    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "hypothesis": (
            "Multi-owner open-market Form 4 buy clusters may provide a cleaner "
            "default-off event interpretation surface than prior single-owner queues."
        ),
        "single_causal_variable": "owner_count >= 2 within a 10-calendar-day open-market buy cluster",
        "change_type": "event_interpretation",
        "mode": "observed_only_shadow_analysis",
        "data_sources": {
            "form4_transactions": str(transactions_path.relative_to(repo)),
            "ohlcv_snapshots": {label: window["snapshot"] for label, window in WINDOWS.items()},
        },
        "parameters": {
            "cluster_lookback_calendar_days": 10,
            "min_distinct_owners": 2,
            "min_cluster_total_purchase_value": 500000.0,
            "open_market_purchase_flag_required": True,
            "pit_safe_flag_required": True,
            "excluded_10b5_1": True,
            "excluded_option_exercise": True,
            "note": "The value floor is inherited from the existing Form 4 forward queue; the tested variable is multi-owner clustering.",
        },
        "by_window": by_window,
        "aggregate": aggregate_windows(by_window),
        "baseline_reference": {
            "core_stack": "exp-20260510-015",
            "sec_financial_report_default_off": "exp-20260512-020",
            "space_default_off": "exp-20260512-041",
        },
        "historical_experiment_check": {
            "nearby_rejected": {
                "exp-20260505-010": "Form 4 sale-pressure de-risking failed; this tests buy-cluster event interpretation, not sales.",
                "exp-20260512-901": "Single-owner Form 4 queue was positive but not material; this isolates multi-owner clustering rather than owner_count == 1.",
            },
            "not_retried": [
                "broad filters",
                "global slots or heat",
                "SEC same-sample retunes",
                "Space adjacent scalars",
                "LLM soft-ranking",
            ],
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "live_slots_changed": False,
        },
        "decision": "observed_only",
        "next_evidence_needed": (
            "If forward outcomes are attractive, freeze a default-off queue and collect "
            "closed forward replacement value before any production integration."
        ),
    }
    output_path = repo / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "artifact": str(output_path.relative_to(repo)),
        "aggregate": artifact["aggregate"],
        "decision": artifact["decision"],
    }, indent=2))


if __name__ == "__main__":
    main()
