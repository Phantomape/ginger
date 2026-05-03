"""Hybrid filing-driven shadow universe scout."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, median


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from data_layer import get_universe  # noqa: E402
from sec_submissions import fetch_submission, parse_recent_filings  # noqa: E402
from sec_ticker_map import load_company_ticker_map, normalize_cik  # noqa: E402


EXP_ID = "exp-20260503-006"
DATA_DIR = REPO_ROOT / "data"
DOCS_DIR = REPO_ROOT / "docs"
ARTIFACT_DIR = DATA_DIR / "experiments" / EXP_ID
ARTIFACT_PATH = ARTIFACT_DIR / "filing_shadow_universe_scout.json"
LOG_PATH = DOCS_DIR / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_PATH = DOCS_DIR / "experiments" / "tickets" / f"{EXP_ID}.json"
EXPERIMENT_LOG_PATH = DOCS_DIR / "experiment_log.jsonl"
FORMS = ("8-K", "10-Q", "10-K")
HORIZONS = (5, 10, 20)
MIN_REPLAY_VALID_10D = 30
MIN_BUCKET_VALID_10D = 3


def _load_json(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def latest_news_path(data_dir: Path = DATA_DIR) -> Path:
    paths = sorted(
        path for path in data_dir.glob("news_*.json")
        if re.fullmatch(r"news_\d{8}\.json", path.name)
    )
    if not paths:
        raise FileNotFoundError("no news_YYYYMMDD.json archive found")
    return paths[-1]


def _news_date_key(path: Path) -> str:
    return path.stem.replace("news_", "")


def _date_from_timestamp(value: str | None, fallback_key: str) -> str:
    if value:
        return str(value)[:10]
    return f"{fallback_key[:4]}-{fallback_key[4:6]}-{fallback_key[6:8]}"


def _event_key(event: dict) -> str:
    return "|".join([
        str(event.get("ticker") or ""),
        str(event.get("cik") or ""),
        str(event.get("filing_type") or ""),
        str(event.get("accession_number") or event.get("archive_url") or event.get("url") or ""),
        str(event.get("filing_date") or ""),
    ])


def build_latest_event_pool(
    news_items: list[dict],
    *,
    date_key: str,
    universe: set[str],
) -> list[dict]:
    deduped = {}
    for item in news_items:
        if item.get("source") != "sec":
            continue
        cik = item.get("sec_cik") or (item.get("source_metadata") or {}).get("sec_cik")
        filing_type = item.get("filing_type") or (item.get("source_metadata") or {}).get("filing_type")
        for ticker in item.get("tickers") or []:
            ticker = str(ticker).upper()
            event = {
                "ticker": ticker,
                "cik": normalize_cik(cik),
                "filing_type": str(filing_type or "").upper(),
                "filing_date": _date_from_timestamp(item.get("published_at"), date_key),
                "accession_number": None,
                "url": item.get("url"),
                "title": item.get("title"),
                "in_current_universe": ticker in universe,
                "source": "latest_news_archive",
            }
            deduped.setdefault(_event_key(event), event)
    return sorted(deduped.values(), key=lambda row: (row["filing_date"], row["ticker"], row["filing_type"]))


def select_historical_ciks(latest_pool: list[dict], max_historical_ciks: int) -> list[dict]:
    by_cik = {}
    for event in sorted(latest_pool, key=lambda row: row.get("filing_date") or "", reverse=True):
        cik = event.get("cik")
        ticker = event.get("ticker")
        if not cik or not ticker or cik in by_cik:
            continue
        by_cik[cik] = {"cik": cik, "ticker": ticker}
        if len(by_cik) >= max_historical_ciks:
            break
    return list(by_cik.values())


def _download_prices(tickers: list[str], start: str, end: str) -> dict[str, list[dict]]:
    import pandas as pd
    import yfinance as yf
    from yfinance_bootstrap import configure_yfinance_runtime

    configure_yfinance_runtime()
    if not tickers:
        return {}
    out = {}

    def _store_downloaded(chunk: list[str]) -> None:
        requested = chunk[0] if len(chunk) == 1 else chunk
        data = yf.download(
            tickers=requested,
            start=start,
            end=end,
            progress=False,
            auto_adjust=True,
            group_by="ticker",
            threads=True,
        )
        if data is None or data.empty:
            return
        for ticker in chunk:
            try:
                if isinstance(data.columns, pd.MultiIndex):
                    frame = data[ticker]
                else:
                    frame = data
            except Exception:
                continue
            if frame is None or frame.empty:
                continue
            frame = frame.reset_index()
            rows = []
            for raw in frame.to_dict("records"):
                date_value = raw.get("Date") or raw.get("Datetime")
                close = raw.get("Close")
                volume = raw.get("Volume")
                if date_value is None or pd.isna(close):
                    continue
                rows.append({
                    "date": str(pd.Timestamp(date_value).date()),
                    "close": float(close),
                    "volume": float(volume) if volume is not None and not pd.isna(volume) else None,
                })
            if rows:
                out[ticker] = rows

    # Fetch the benchmark separately so bad/OTC shadow tickers cannot remove it
    # from a mixed yfinance batch response.
    if "SPY" in tickers:
        _store_downloaded(["SPY"])

    non_spy = [ticker for ticker in tickers if ticker != "SPY"]
    for idx in range(0, len(non_spy), 50):
        chunk = non_spy[idx:idx + 50]
        _store_downloaded(chunk)
    return out


def _entry_index_after(rows: list[dict], filing_date: str) -> int | None:
    for idx, row in enumerate(rows):
        if row["date"] > filing_date:
            return idx
    return None


def _avg_dollar_volume(rows: list[dict], entry_idx: int, lookback: int = 20) -> float | None:
    start = max(0, entry_idx - lookback)
    values = []
    for row in rows[start:entry_idx]:
        close = row.get("close")
        volume = row.get("volume")
        if isinstance(close, (int, float)) and isinstance(volume, (int, float)):
            values.append(close * volume)
    if len(values) < min(lookback, entry_idx):
        return None
    return mean(values) if values else None


def liquidity_bucket(avg_dollar_volume: float | None) -> str:
    if avg_dollar_volume is None:
        return "adv_unknown"
    if avg_dollar_volume >= 20_000_000:
        return "adv_ge_20m"
    if avg_dollar_volume >= 5_000_000:
        return "adv_5m_20m"
    return "adv_lt_5m"


def evaluate_forward_event(
    event: dict,
    ticker_rows: list[dict] | None,
    spy_rows: list[dict] | None,
    *,
    horizons: tuple[int, ...] = HORIZONS,
) -> dict:
    result = dict(event)
    result["horizons"] = {}
    if not ticker_rows:
        result["price_status"] = "no_ticker_price"
        return result
    if not spy_rows:
        result["price_status"] = "no_spy_price"
        return result
    entry_idx = _entry_index_after(ticker_rows, result["filing_date"])
    if entry_idx is None:
        result["price_status"] = "pending_entry"
        return result
    entry_date = ticker_rows[entry_idx]["date"]
    spy_entry_idx = next((idx for idx, row in enumerate(spy_rows) if row["date"] >= entry_date), None)
    if spy_entry_idx is None:
        result["price_status"] = "no_spy_entry"
        return result
    entry_close = ticker_rows[entry_idx].get("close")
    spy_entry_close = spy_rows[spy_entry_idx].get("close")
    if not entry_close or not spy_entry_close:
        result["price_status"] = "bad_entry_price"
        return result

    avg_dv = _avg_dollar_volume(ticker_rows, entry_idx)
    result["entry_date"] = entry_date
    result["entry_close"] = round(entry_close, 4)
    result["avg_dollar_volume_20d"] = round(avg_dv, 2) if avg_dv is not None else None
    result["liquidity_bucket"] = liquidity_bucket(avg_dv)
    result["price_status"] = "covered"
    for horizon in horizons:
        ticker_end_idx = entry_idx + horizon
        spy_end_idx = spy_entry_idx + horizon
        if ticker_end_idx >= len(ticker_rows) or spy_end_idx >= len(spy_rows):
            result["horizons"][f"{horizon}d"] = {"status": "pending"}
            continue
        ticker_ret = ticker_rows[ticker_end_idx]["close"] / entry_close - 1.0
        spy_ret = spy_rows[spy_end_idx]["close"] / spy_entry_close - 1.0
        result["horizons"][f"{horizon}d"] = {
            "status": "valid",
            "return": round(ticker_ret, 6),
            "spy_return": round(spy_ret, 6),
            "excess_return": round(ticker_ret - spy_ret, 6),
            "end_date": ticker_rows[ticker_end_idx]["date"],
        }
    return result


def _summarize_values(values: list[float]) -> dict:
    if not values:
        return {"count": 0, "avg": None, "median": None, "win_rate": None}
    return {
        "count": len(values),
        "avg": round(mean(values), 6),
        "median": round(median(values), 6),
        "win_rate": round(sum(1 for value in values if value > 0) / len(values), 4),
    }


def _group_summary(rows: list[dict], group_key: str) -> dict:
    grouped = defaultdict(list)
    for row in rows:
        grouped[str(row.get(group_key) or "unknown")].append(row)
    out = {}
    for key, group_rows in sorted(grouped.items()):
        horizon_values = {}
        for horizon in HORIZONS:
            hkey = f"{horizon}d"
            values = [
                row["horizons"][hkey]["excess_return"]
                for row in group_rows
                if row.get("horizons", {}).get(hkey, {}).get("status") == "valid"
            ]
            horizon_values[hkey] = _summarize_values(values)
        out[key] = {
            "event_count": len(group_rows),
            "valid_10d_count": horizon_values["10d"]["count"],
            "excess_return": horizon_values,
        }
    return out


def _positive_bucket_count(*summaries: dict) -> int:
    count = 0
    for summary in summaries:
        for bucket in summary.values():
            ten_day = (bucket.get("excess_return") or {}).get("10d") or {}
            if (ten_day.get("count") or 0) >= MIN_BUCKET_VALID_10D and (ten_day.get("avg") or 0) > 0:
                count += 1
    return count


def _valid_10d(rows: list[dict]) -> list[float]:
    values = []
    for row in rows:
        ten_day = row.get("horizons", {}).get("10d", {})
        if ten_day.get("status") == "valid":
            values.append(ten_day["excess_return"])
    return values


def _pending_counts(rows: list[dict]) -> dict:
    out = {}
    for horizon in HORIZONS:
        hkey = f"{horizon}d"
        out[hkey] = sum(1 for row in rows if row.get("horizons", {}).get(hkey, {}).get("status") == "pending")
    return out


def _safe_float(value):
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def _compact_row(row: dict) -> dict:
    keep = {
        "ticker",
        "cik",
        "filing_type",
        "filing_date",
        "accession_number",
        "in_current_universe",
        "entry_date",
        "liquidity_bucket",
        "avg_dollar_volume_20d",
        "price_status",
        "horizons",
    }
    return {key: _safe_float(value) for key, value in row.items() if key in keep}


def run(args: argparse.Namespace) -> dict:
    news_path = Path(args.news_path) if args.news_path else latest_news_path()
    date_key = _news_date_key(news_path)
    news_items = _load_json(news_path)
    universe = set(get_universe())
    latest_pool = build_latest_event_pool(news_items, date_key=date_key, universe=universe)
    selected = select_historical_ciks(latest_pool, args.max_historical_ciks)

    historical_events = {}
    fetch_errors = []
    for row in selected:
        try:
            payload = fetch_submission(
                row["cik"],
                refresh=args.refresh_submissions,
                sleep_seconds=args.sec_sleep_seconds,
            )
        except Exception as exc:
            fetch_errors.append({"cik": row["cik"], "ticker": row["ticker"], "error": str(exc)})
            continue
        filings = parse_recent_filings(
            payload,
            ticker=row["ticker"],
            cik=row["cik"],
            forms=set(FORMS),
            max_filings=args.max_filings_per_cik,
        )
        for event in filings:
            event["in_current_universe"] = event["ticker"] in universe if event.get("ticker") else False
            historical_events.setdefault(_event_key(event), event)

    historical_pool = sorted(
        historical_events.values(),
        key=lambda event: (event["filing_date"], event.get("ticker") or "", event["filing_type"]),
    )
    tickers = sorted({event["ticker"] for event in historical_pool if event.get("ticker")} | {"SPY"})
    if historical_pool:
        min_date = min(event["filing_date"] for event in historical_pool)
        start = str(datetime.fromisoformat(min_date).date() - timedelta(days=60))
    else:
        start = "2024-01-01"
    end = str(datetime.now().date() + timedelta(days=1))
    prices = _download_prices(tickers, start=start, end=end)
    spy_rows = prices.get("SPY")

    evaluated = [
        evaluate_forward_event(event, prices.get(event.get("ticker")), spy_rows)
        for event in historical_pool
    ]
    valid_10d = _valid_10d(evaluated)
    filing_summary = _group_summary(evaluated, "filing_type")
    liquidity_summary = _group_summary(evaluated, "liquidity_bucket")
    universe_summary = _group_summary(evaluated, "in_current_universe")
    positive_buckets = _positive_bucket_count(filing_summary, liquidity_summary)
    price_covered = sum(1 for row in evaluated if row.get("price_status") == "covered")
    price_coverage_rate = round(price_covered / len(evaluated), 4) if evaluated else None

    if len(valid_10d) >= MIN_REPLAY_VALID_10D and positive_buckets >= 2:
        decision = "replay_candidate"
    elif len(valid_10d) < MIN_REPLAY_VALID_10D or (price_coverage_rate is not None and price_coverage_rate < 0.3):
        decision = "coverage_blocked"
    else:
        decision = "observed_only"

    outside = [row for row in evaluated if not row.get("in_current_universe")]
    inside = [row for row in evaluated if row.get("in_current_universe")]
    outside_10d = _summarize_values(_valid_10d(outside))
    inside_10d = _summarize_values(_valid_10d(inside))
    next_action = (
        "If outside-universe excess drift remains stronger with valid sample, run a shadow "
        "universe expansion scout. Do not change production entries from this observed-only artifact."
    )
    if decision == "coverage_blocked":
        next_action = (
            "Coverage is still too thin for promotion. Accumulate more SEC submissions/price coverage "
            "or lower the historical CIK cap only for a bounded follow-up audit."
        )

    artifact = {
        "experiment_id": EXP_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": decision,
        "decision": decision,
        "lane": "alpha_discovery",
        "change_type": "filing_driven_shadow_universe_scout",
        "hypothesis": (
            "SEC filing alpha may be clipped by the current production universe; a shadow "
            "universe built from mapped SEC filings can distinguish universe truncation from "
            "weak filing-type signal."
        ),
        "parameters": {
            "mode": "hybrid",
            "max_historical_ciks": args.max_historical_ciks,
            "max_filings_per_cik": args.max_filings_per_cik,
            "forms": list(FORMS),
            "forward_horizons": list(HORIZONS),
            "min_replay_valid_10d": MIN_REPLAY_VALID_10D,
            "min_bucket_valid_10d": MIN_BUCKET_VALID_10D,
            "single_causal_variable": "shadow SEC filing universe coverage and forward-return audit",
            "locked_variables": [
                "production universe",
                "signal generation",
                "ranking",
                "sizing",
                "entries",
                "exits",
                "LLM/news replay",
            ],
        },
        "latest_archive": {
            "path": str(news_path.relative_to(REPO_ROOT)),
            "date_key": date_key,
            "mapped_event_count": len(latest_pool),
            "unique_tickers": len({event["ticker"] for event in latest_pool}),
            "current_universe_overlap": sum(1 for event in latest_pool if event["in_current_universe"]),
            "outside_universe_count": sum(1 for event in latest_pool if not event["in_current_universe"]),
            "filing_type_counts": dict(Counter(event["filing_type"] for event in latest_pool)),
            "forward_status": "deferred_forward_observation",
            "event_pool": latest_pool,
        },
        "historical_sample": {
            "selected_cik_count": len(selected),
            "fetch_error_count": len(fetch_errors),
            "fetch_errors_sample": fetch_errors[:10],
            "historical_event_count": len(historical_pool),
            "unique_tickers": len({event.get("ticker") for event in historical_pool if event.get("ticker")}),
            "price_covered_count": price_covered,
            "price_coverage_rate": price_coverage_rate,
            "valid_10d_count": len(valid_10d),
            "pending_horizon_counts": _pending_counts(evaluated),
            "overall_10d_excess_return": _summarize_values(valid_10d),
            "current_universe_10d_excess_return": inside_10d,
            "outside_universe_10d_excess_return": outside_10d,
            "positive_bucket_count": positive_buckets,
            "by_filing_type": filing_summary,
            "by_liquidity_bucket": liquidity_summary,
            "by_current_universe": universe_summary,
            "sample_evaluated_events": [_compact_row(row) for row in evaluated[:80]],
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": True,
        },
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "rejection_reason": (
            None if decision == "replay_candidate"
            else "Not production-ready; this is a shadow-only filing universe coverage and drift audit."
        ),
        "next_action": next_action,
        "related_files": [
            "quant/sec_submissions.py",
            "quant/experiments/exp_20260503_006_filing_shadow_universe_scout.py",
            "docs/alpha-optimization-playbook.md",
        ],
    }
    return artifact


def persist(payload: dict) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    TICKET_PATH.parent.mkdir(parents=True, exist_ok=True)
    for path in (ARTIFACT_PATH, LOG_PATH):
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    ticket = {
        "experiment_id": EXP_ID,
        "status": payload["status"],
        "title": "Filing-driven shadow universe scout",
        "summary": payload["hypothesis"],
        "best_variant": payload["decision"],
        "best_variant_gate4": False,
        "delta_metrics": {
            "latest_mapped_event_count": payload["latest_archive"]["mapped_event_count"],
            "latest_current_universe_overlap": payload["latest_archive"]["current_universe_overlap"],
            "historical_event_count": payload["historical_sample"]["historical_event_count"],
            "valid_10d_count": payload["historical_sample"]["valid_10d_count"],
            "positive_bucket_count": payload["historical_sample"]["positive_bucket_count"],
        },
        "next_action": payload["next_action"],
    }
    TICKET_PATH.write_text(json.dumps(ticket, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    append_experiment_log(payload)


def append_experiment_log(payload: dict) -> None:
    if EXPERIMENT_LOG_PATH.exists():
        existing = EXPERIMENT_LOG_PATH.read_text(encoding="utf-8", errors="replace")
        if f'"experiment_id":"{EXP_ID}"' in existing or f'"experiment_id": "{EXP_ID}"' in existing:
            return
    log_record = {
        "experiment_id": payload["experiment_id"],
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": payload["lane"],
        "change_type": payload["change_type"],
        "hypothesis": payload["hypothesis"],
        "parameters": payload["parameters"],
        "date_range": {"primary": "historical SEC submissions sample plus latest SEC archive"},
        "before_metrics": {
            "exp_20260503_005_latest_current_universe_overlap": 1,
            "exp_20260503_005_valid_historical_forward_returns": 0,
        },
        "after_metrics": {
            "latest_mapped_event_count": payload["latest_archive"]["mapped_event_count"],
            "latest_unique_tickers": payload["latest_archive"]["unique_tickers"],
            "latest_current_universe_overlap": payload["latest_archive"]["current_universe_overlap"],
            "historical_event_count": payload["historical_sample"]["historical_event_count"],
            "price_covered_count": payload["historical_sample"]["price_covered_count"],
            "valid_10d_count": payload["historical_sample"]["valid_10d_count"],
            "overall_10d_excess_return": payload["historical_sample"]["overall_10d_excess_return"],
            "positive_bucket_count": payload["historical_sample"]["positive_bucket_count"],
        },
        "delta_metrics": {
            "filing_type_10k_10d_excess_avg": (
                payload["historical_sample"]["by_filing_type"].get("10-K", {})
                .get("excess_return", {})
                .get("10d", {})
                .get("avg")
            ),
            "adv_5m_20m_10d_excess_avg": (
                payload["historical_sample"]["by_liquidity_bucket"].get("adv_5m_20m", {})
                .get("excess_return", {})
                .get("10d", {})
                .get("avg")
            ),
            "adv_lt_5m_10d_excess_avg": (
                payload["historical_sample"]["by_liquidity_bucket"].get("adv_lt_5m", {})
                .get("excess_return", {})
                .get("10d", {})
                .get("avg")
            ),
        },
        "production_impact": payload["production_impact"],
        "llm_metrics": payload["llm_metrics"],
        "rejection_reason": payload["rejection_reason"],
        "next_retry_requires": [
            "Do not promote broad SEC filing signals; overall 10d excess return is negative.",
            "Second-round replay should lock 10-K and ADV >= $5m discriminators.",
            "Any watchlist expansion must prove scarce-slot replacement value before production changes.",
        ],
        "related_files": payload["related_files"] + [
            "data/experiments/exp-20260503-006/filing_shadow_universe_scout.json",
            "docs/experiments/logs/exp-20260503-006.json",
            "docs/experiments/tickets/exp-20260503-006.json",
        ],
    }
    EXPERIMENT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EXPERIMENT_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(log_record, ensure_ascii=False, separators=(",", ":")) + "\n")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--news-path", default=None, help="Optional news_YYYYMMDD.json archive")
    parser.add_argument("--max-historical-ciks", type=int, default=100)
    parser.add_argument("--max-filings-per-cik", type=int, default=10)
    parser.add_argument("--refresh-submissions", action="store_true")
    parser.add_argument("--sec-sleep-seconds", type=float, default=0.11)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    payload = run(parse_args(argv))
    persist(payload)
    print(json.dumps({
        "experiment_id": payload["experiment_id"],
        "decision": payload["decision"],
        "latest": {
            "mapped_event_count": payload["latest_archive"]["mapped_event_count"],
            "unique_tickers": payload["latest_archive"]["unique_tickers"],
            "current_universe_overlap": payload["latest_archive"]["current_universe_overlap"],
        },
        "historical": {
            "historical_event_count": payload["historical_sample"]["historical_event_count"],
            "price_covered_count": payload["historical_sample"]["price_covered_count"],
            "valid_10d_count": payload["historical_sample"]["valid_10d_count"],
            "positive_bucket_count": payload["historical_sample"]["positive_bucket_count"],
            "overall_10d_excess_return": payload["historical_sample"]["overall_10d_excess_return"],
        },
    }, indent=2, ensure_ascii=False))
    print(f"wrote: {ARTIFACT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
