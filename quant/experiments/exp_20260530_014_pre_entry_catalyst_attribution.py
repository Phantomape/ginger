"""exp-20260530-014: pre-entry catalyst attribution for early-entry research.

This observed-only alpha search asks whether existing core trades already show
better outcomes when a production-visible non-OHLCV catalyst appears in the
10 calendar days before entry. It is a research bridge after the rejected
OHLCV-only early-entry test in exp-20260530-013.

No production, ranking, sizing, entry, exit, or order behavior is changed.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Any


EXPERIMENT_ID = "exp-20260530-014"
STEM = "pre_entry_catalyst_attribution"
CHANGED_VARIABLE = "pre_entry_catalyst_context_bucket_v1"
TRIAL_FAMILY = "pre_entry_catalyst_context_attribution"
TRIAL_VARIANT_ID = "multi_source_pre_entry_catalyst_v1"
LOOKBACK_CALENDAR_DAYS = 10
MIN_TAGGED_TRADES = 10
MIN_POSITIVE_LIFT_WINDOWS = 2
MAX_POSITIVE_PNL_TICKER_SHARE = 0.50

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine, DEFAULT_CONFIG  # noqa: E402
from data_layer import get_universe  # noqa: E402


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

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260530_014_{STEM}.json"
ROWS_JSON = OUT_DIR / f"{STEM}_trade_rows.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
DOC_LOG = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_ARTIFACT = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

POSITIVE_NEWS_TERMS = {
    "acquire",
    "approval",
    "beat",
    "beats",
    "bullish",
    "contract",
    "growth",
    "higher",
    "jump",
    "jumps",
    "launch",
    "maintains buy",
    "outperform",
    "partnership",
    "raise",
    "raises",
    "raised",
    "record",
    "rises",
    "strong",
    "surge",
    "surges",
    "upgrade",
    "upgrades",
    "win",
    "wins",
}
NEGATIVE_NEWS_TERMS = {
    "bearish",
    "bloodbath",
    "cut",
    "cuts",
    "downgrade",
    "downgrades",
    "falls",
    "lawsuit",
    "miss",
    "plunge",
    "plunges",
    "slump",
    "weak",
}
HIGH_CONFIDENCE_CATEGORIES = {
    "sec_financial_report",
    "form4_open_market_purchase",
    "positive_estimate_revision",
    "positive_t1_t2_news",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(key): _safe(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [_safe(value) for value in obj]
    if isinstance(obj, tuple):
        return [_safe(value) for value in obj]
    if isinstance(obj, set):
        return sorted(_safe(value) for value in obj)
    if hasattr(obj, "item"):
        return obj.item()
    return obj


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _append_jsonl_once(path: Path, payload: dict[str, Any]) -> None:
    compact = json.dumps(_safe(payload), ensure_ascii=False, separators=(",", ":"))
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        lines = [
            line
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if f'"experiment_id":"{EXPERIMENT_ID}"' not in line
            and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
        ]
    else:
        lines = []
    lines.append(compact)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _repo_rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return value


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    text = str(value)
    if "T" in text:
        text = text.split("T", 1)[0]
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _date_from_filename(path: Path) -> date | None:
    digits = "".join(ch for ch in path.stem if ch.isdigit())
    if len(digits) < 8:
        return None
    try:
        return datetime.strptime(digits[-8:], "%Y%m%d").date()
    except ValueError:
        return None


def _iter_jsonl(path: Path):
    try:
        with path.open(encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        return


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _event_index():
    index: dict[str, dict[date, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    stats: Counter[str] = Counter()
    seen: set[tuple[str, str, str, str]] = set()

    non_ohlcv = REPO_ROOT / "data" / "non_ohlcv"
    for path in sorted(non_ohlcv.glob("sec_filing_events_*.jsonl")):
        stats["sec_files_seen"] += 1
        for row in _iter_jsonl(path):
            ticker = str(row.get("ticker") or "").upper().strip()
            usable = _parse_date(row.get("usable_trade_date"))
            if not ticker or usable is None:
                continue
            form_base = str(row.get("form_base") or row.get("form_type") or "").upper()
            if form_base in {"10-K", "10-Q"}:
                category = "sec_financial_report"
            elif form_base == "8-K":
                category = "sec_8k"
            else:
                category = "sec_other"
            key = (
                "sec",
                ticker,
                usable.isoformat(),
                str(row.get("accession_number") or row.get("archive_url") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            stats[f"{category}_events"] += 1
            index[ticker][usable].append(
                {
                    "date": usable.isoformat(),
                    "source": "sec",
                    "category": category,
                    "form_type": row.get("form_type"),
                    "accession_number": row.get("accession_number"),
                    "high_confidence": category in HIGH_CONFIDENCE_CATEGORIES,
                }
            )

    for path in sorted(non_ohlcv.glob("form4_transactions_*.jsonl")):
        stats["form4_files_seen"] += 1
        for row in _iter_jsonl(path):
            ticker = str(row.get("ticker") or row.get("issuer_trading_symbol") or "").upper().strip()
            usable = _parse_date(row.get("usable_trade_date"))
            if not ticker or usable is None:
                continue
            if not row.get("open_market_purchase_flag"):
                continue
            value = _as_float(row.get("transaction_value")) or 0.0
            key = (
                "form4",
                ticker,
                usable.isoformat(),
                str(row.get("accession_number") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            stats["form4_open_market_purchase_events"] += 1
            index[ticker][usable].append(
                {
                    "date": usable.isoformat(),
                    "source": "form4",
                    "category": "form4_open_market_purchase",
                    "owner_name": row.get("owner_name"),
                    "officer_title": row.get("officer_title"),
                    "transaction_value": _round(value, 2),
                    "accession_number": row.get("accession_number"),
                    "high_confidence": True,
                }
            )

    for path in sorted(non_ohlcv.glob("estimate_revision_ledger_*.jsonl")):
        stats["estimate_files_seen"] += 1
        for row in _iter_jsonl(path):
            ticker = str(row.get("ticker") or "").upper().strip()
            as_of = _parse_date(row.get("as_of_date")) or _date_from_filename(path)
            if not ticker or as_of is None:
                continue
            deltas = [
                _as_float(row.get("eps_estimate_delta_prev")),
                _as_float(row.get("eps_estimate_delta_7d")),
                _as_float(row.get("eps_estimate_delta_30d")),
            ]
            if not any(delta is not None and delta > 0 for delta in deltas):
                continue
            key = ("estimate", ticker, as_of.isoformat(), str(row.get("next_earnings_date") or ""))
            if key in seen:
                continue
            seen.add(key)
            stats["positive_estimate_revision_events"] += 1
            index[ticker][as_of].append(
                {
                    "date": as_of.isoformat(),
                    "source": "estimate_revision",
                    "category": "positive_estimate_revision",
                    "eps_estimate_delta_prev": row.get("eps_estimate_delta_prev"),
                    "eps_estimate_delta_7d": row.get("eps_estimate_delta_7d"),
                    "eps_estimate_delta_30d": row.get("eps_estimate_delta_30d"),
                    "next_earnings_date": row.get("next_earnings_date"),
                    "high_confidence": True,
                }
            )

    for root, source_name in [
        (REPO_ROOT / "data" / "daily" / "news" / "trade", "trade_news"),
        (REPO_ROOT / "data" / "daily" / "news" / "clean", "clean_news"),
    ]:
        for path in sorted(root.glob("*_news_*.json")):
            stats[f"{source_name}_files_seen"] += 1
            payload = _load_json(path)
            if not isinstance(payload, list):
                continue
            fallback_date = _date_from_filename(path)
            for item in payload:
                tickers = item.get("tickers") if isinstance(item, dict) else None
                if not isinstance(tickers, list):
                    continue
                event_date = _parse_date(item.get("published_at")) or fallback_date
                if event_date is None:
                    continue
                title = str(item.get("title") or "")
                summary = str(item.get("summary") or "")
                text = f"{title} {summary}".lower()
                positive = any(term in text for term in POSITIVE_NEWS_TERMS)
                negative = any(term in text for term in NEGATIVE_NEWS_TERMS)
                if not positive or negative:
                    continue
                tier = str(item.get("tier") or "").upper()
                category = "positive_t1_t2_news" if tier in {"T1", "T2"} else "positive_other_news"
                for raw_ticker in tickers:
                    ticker = str(raw_ticker or "").upper().strip()
                    if not ticker:
                        continue
                    key = (
                        "news",
                        ticker,
                        event_date.isoformat(),
                        title[:120],
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                    stats[f"{category}_events"] += 1
                    index[ticker][event_date].append(
                        {
                            "date": event_date.isoformat(),
                            "source": source_name,
                            "category": category,
                            "tier": tier or None,
                            "title": title[:240],
                            "high_confidence": category in HIGH_CONFIDENCE_CATEGORIES,
                        }
                    )

    stats["unique_ticker_date_buckets"] = sum(len(days) for days in index.values())
    stats["unique_tickers"] = len(index)
    return index, dict(sorted(stats.items()))


def _events_for_trade(
    index: dict[str, dict[date, list[dict[str, Any]]]],
    ticker: str,
    entry: date,
) -> list[dict[str, Any]]:
    start = entry - timedelta(days=LOOKBACK_CALENDAR_DAYS)
    events: list[dict[str, Any]] = []
    cursor = start
    while cursor <= entry:
        events.extend(index.get(ticker, {}).get(cursor, []))
        cursor += timedelta(days=1)
    return sorted(events, key=lambda row: (row.get("date") or "", row.get("category") or ""))


def _run_window(universe: list[str], window: dict[str, str]) -> dict[str, Any]:
    engine = BacktestEngine(
        universe,
        start=window["start"],
        end=window["end"],
        config=dict(DEFAULT_CONFIG),
        ohlcv_snapshot_path=window["snapshot"],
    )
    return engine.run()


def _result_metrics(result: dict[str, Any]) -> dict[str, Any]:
    ret = result.get("strategy_total_return_pct")
    if ret is None:
        ret = (result.get("benchmarks") or {}).get("strategy_total_return_pct")
    trades = result.get("trade_count")
    if trades is None:
        trades = result.get("total_trades")
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "strategy_total_return_pct": _round(ret, 4),
        "sharpe_daily": _round(result.get("sharpe_daily"), 2),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": trades,
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": _round(result.get("survival_rate"), 4),
    }


def _aggregate_metrics(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "expected_value_score": _round(
            sum(float(row["metrics"]["expected_value_score"] or 0.0) for row in rows.values()),
            4,
        ),
        "benchmarks": {
            "strategy_total_return_pct": _round(
                sum(float(row["metrics"]["strategy_total_return_pct"] or 0.0) for row in rows.values()),
                4,
            )
        },
        "sharpe_daily": None,
        "max_drawdown_pct": _round(
            max(float(row["metrics"]["max_drawdown_pct"] or 0.0) for row in rows.values()),
            4,
        ),
        "win_rate": None,
        "total_trades": sum(int(row["metrics"]["trade_count"] or 0) for row in rows.values()),
        "survival_rate": _round(
            min(float(row["metrics"]["survival_rate"] or 0.0) for row in rows.values()),
            4,
        ),
        "total_pnl": _round(
            sum(float(row["metrics"]["total_pnl"] or 0.0) for row in rows.values()),
            2,
        ),
    }


def _summarize_trade_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pnls = [float(row.get("pnl") or 0.0) for row in rows]
    pct = [float(row.get("pnl_pct_net") or 0.0) for row in rows if row.get("pnl_pct_net") is not None]
    positive_by_ticker: Counter[str] = Counter()
    for row in rows:
        pnl = float(row.get("pnl") or 0.0)
        if pnl > 0:
            positive_by_ticker[str(row.get("ticker") or "")] += pnl
    total_positive = sum(positive_by_ticker.values())
    max_positive_share = (
        max(positive_by_ticker.values()) / total_positive
        if total_positive > 0 and positive_by_ticker
        else 0.0
    )
    top_positive_ticker = (
        positive_by_ticker.most_common(1)[0][0] if positive_by_ticker else None
    )
    return {
        "trade_count": len(rows),
        "total_pnl": _round(sum(pnls), 2),
        "avg_pnl": _round(sum(pnls) / len(pnls), 2) if pnls else None,
        "median_pnl": _round(median(pnls), 2) if pnls else None,
        "avg_pnl_pct_net": _round(sum(pct) / len(pct), 6) if pct else None,
        "win_rate": _round(sum(1 for pnl in pnls if pnl > 0) / len(pnls), 4)
        if pnls
        else None,
        "max_single_ticker_positive_pnl_share": _round(max_positive_share, 6),
        "top_positive_ticker": top_positive_ticker,
    }


def _bucket_summaries(rows: list[dict[str, Any]], flag: str) -> dict[str, Any]:
    yes = [row for row in rows if row.get(flag)]
    no = [row for row in rows if not row.get(flag)]
    yes_summary = _summarize_trade_group(yes)
    no_summary = _summarize_trade_group(no)
    lift = None
    if yes_summary["avg_pnl"] is not None and no_summary["avg_pnl"] is not None:
        lift = _round(float(yes_summary["avg_pnl"]) - float(no_summary["avg_pnl"]), 2)
    return {
        "yes": yes_summary,
        "no": no_summary,
        "avg_pnl_lift_yes_minus_no": lift,
    }


def _category_summaries(rows: list[dict[str, Any]]) -> dict[str, Any]:
    categories = sorted({category for row in rows for category in row.get("catalyst_categories", [])})
    summaries: dict[str, Any] = {}
    for category in categories:
        hit_rows = [row for row in rows if category in row.get("catalyst_categories", [])]
        miss_rows = [row for row in rows if category not in row.get("catalyst_categories", [])]
        hit = _summarize_trade_group(hit_rows)
        miss = _summarize_trade_group(miss_rows)
        lift = None
        if hit["avg_pnl"] is not None and miss["avg_pnl"] is not None:
            lift = _round(float(hit["avg_pnl"]) - float(miss["avg_pnl"]), 2)
        summaries[category] = {
            "hit": hit,
            "miss": miss,
            "avg_pnl_lift_hit_minus_miss": lift,
        }
    return summaries


def _window_lift_count(rows: list[dict[str, Any]], flag: str) -> int:
    count = 0
    for label in WINDOWS:
        bucket = _bucket_summaries([row for row in rows if row["window"] == label], flag)
        lift = bucket.get("avg_pnl_lift_yes_minus_no")
        if lift is not None and lift > 0:
            count += 1
    return count


def _build_trade_rows(
    backtest_rows: dict[str, dict[str, Any]],
    event_index: dict[str, dict[date, list[dict[str, Any]]]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for label, row in backtest_rows.items():
        for trade in row["raw"].get("trades") or []:
            ticker = str(trade.get("ticker") or "").upper().strip()
            entry = _parse_date(trade.get("entry_date"))
            if not ticker or entry is None:
                continue
            events = _events_for_trade(event_index, ticker, entry)
            categories = sorted({event["category"] for event in events})
            sources = sorted({event["source"] for event in events})
            high_conf = [event for event in events if event.get("high_confidence")]
            out.append(
                {
                    "window": label,
                    "ticker": ticker,
                    "strategy": trade.get("strategy"),
                    "entry_date": entry.isoformat(),
                    "exit_date": trade.get("exit_date"),
                    "pnl": _round(trade.get("pnl"), 2),
                    "pnl_pct_net": _round(trade.get("pnl_pct_net"), 6),
                    "win": bool((trade.get("pnl") or 0) > 0),
                    "has_any_catalyst_context": bool(events),
                    "has_high_confidence_catalyst": bool(high_conf),
                    "catalyst_event_count": len(events),
                    "high_confidence_catalyst_count": len(high_conf),
                    "catalyst_categories": categories,
                    "catalyst_sources": sources,
                    "catalyst_examples": events[:8],
                }
            )
    return out


def _artifact_markdown(payload: dict[str, Any]) -> str:
    high = payload["attribution_summary"]["high_confidence_catalyst_bucket"]
    any_bucket = payload["attribution_summary"]["any_catalyst_context_bucket"]
    lines = [
        f"# {EXPERIMENT_ID} Pre-Entry Catalyst Attribution",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- High-confidence tagged trades: `{high['yes']['trade_count']}`",
        f"- High-confidence avg PnL lift: `{high['avg_pnl_lift_yes_minus_no']}`",
        f"- Any-catalyst tagged trades: `{any_bucket['yes']['trade_count']}`",
        f"- Any-catalyst avg PnL lift: `{any_bucket['avg_pnl_lift_yes_minus_no']}`",
        f"- Useful-for-next-experiment gate passed: `{payload['observed_gate']['passed']}`",
        "",
        "| Window | Trades | High-conf tagged | High-conf avg lift | Any-context tagged | Any-context avg lift |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, summary in payload["window_attribution"].items():
        lines.append(
            f"| {label} | {summary['trade_count']} | "
            f"{summary['high_confidence_catalyst_bucket']['yes']['trade_count']} | "
            f"{summary['high_confidence_catalyst_bucket']['avg_pnl_lift_yes_minus_no']} | "
            f"{summary['any_catalyst_context_bucket']['yes']['trade_count']} | "
            f"{summary['any_catalyst_context_bucket']['avg_pnl_lift_yes_minus_no']} |"
        )
    lines.extend(
        [
            "",
            "Observed-only result. The joined catalyst context is not consumed by "
            "entries, ranking, sizing, exits, or production orders.",
            "",
            "## Gate",
            "",
            "```json",
            json.dumps(payload["observed_gate"], indent=2, sort_keys=True),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    timestamp = _utc_now()
    universe = get_universe()
    event_index, source_stats = _event_index()

    backtest_rows: dict[str, dict[str, Any]] = {}
    for label, window in WINDOWS.items():
        result = _run_window(universe, window)
        backtest_rows[label] = {
            "window": window,
            "metrics": _result_metrics(result),
            "raw": result,
        }

    trade_rows = _build_trade_rows(backtest_rows, event_index)
    before_after = _aggregate_metrics(backtest_rows)
    high_bucket = _bucket_summaries(trade_rows, "has_high_confidence_catalyst")
    any_bucket = _bucket_summaries(trade_rows, "has_any_catalyst_context")
    window_attr: dict[str, Any] = {}
    for label in WINDOWS:
        rows = [row for row in trade_rows if row["window"] == label]
        window_attr[label] = {
            "trade_count": len(rows),
            "high_confidence_catalyst_bucket": _bucket_summaries(
                rows,
                "has_high_confidence_catalyst",
            ),
            "any_catalyst_context_bucket": _bucket_summaries(
                rows,
                "has_any_catalyst_context",
            ),
            "category_summaries": _category_summaries(rows),
        }

    high_windows_positive = _window_lift_count(trade_rows, "has_high_confidence_catalyst")
    high_share = high_bucket["yes"]["max_single_ticker_positive_pnl_share"] or 0.0
    observed_passed = (
        high_bucket["yes"]["trade_count"] >= MIN_TAGGED_TRADES
        and (high_bucket["avg_pnl_lift_yes_minus_no"] or 0) > 0
        and high_windows_positive >= MIN_POSITIVE_LIFT_WINDOWS
        and high_share <= MAX_POSITIVE_PNL_TICKER_SHARE
    )
    observed_gate = {
        "passed": observed_passed,
        "rule": (
            "Observed-only usefulness gate: high-confidence catalyst tagged "
            "trades >= 10, average PnL lift versus no high-confidence catalyst "
            "> 0, at least two windows with positive lift, and tagged positive "
            "PnL max single-ticker share <= 50%."
        ),
        "high_confidence_tagged_trades": high_bucket["yes"]["trade_count"],
        "high_confidence_avg_pnl_lift": high_bucket["avg_pnl_lift_yes_minus_no"],
        "positive_lift_windows": high_windows_positive,
        "max_single_ticker_positive_pnl_share": high_share,
        "failed_reasons": [
            reason
            for reason, failed in [
                ("tagged_sample_below_10", high_bucket["yes"]["trade_count"] < MIN_TAGGED_TRADES),
                (
                    "high_confidence_avg_pnl_lift_not_positive",
                    (high_bucket["avg_pnl_lift_yes_minus_no"] or 0) <= 0,
                ),
                (
                    "fewer_than_two_positive_lift_windows",
                    high_windows_positive < MIN_POSITIVE_LIFT_WINDOWS,
                ),
                (
                    "tagged_positive_pnl_concentration_above_50pct",
                    high_share > MAX_POSITIVE_PNL_TICKER_SHARE,
                ),
            ]
            if failed
        ],
    }
    decision = (
        "observed_useful_pre_entry_catalyst_context"
        if observed_passed
        else "observed_only_no_pre_entry_catalyst_edge"
    )
    actual_success = 1 if observed_passed else 0

    snow_rows = [row for row in trade_rows if row["ticker"] == "SNOW"]
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": "observed_only",
        "lane": "alpha_search",
        "hypothesis": (
            "Core breakout/trend winners, including SNOW-like late-entry cases, "
            "should show materially better outcomes when a production-visible "
            "non-OHLCV catalyst appears in the 10 calendar days before entry."
        ),
        "change_type": "read_only_pre_entry_catalyst_attribution",
        "mechanism_family": "event_or_llm",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": (
            "Join read-only multi-source PIT catalyst context to already executed "
            "core trades; no strategy behavior changes."
        ),
        "parameters": {
            "lookback_calendar_days": LOOKBACK_CALENDAR_DAYS,
            "high_confidence_categories": sorted(HIGH_CONFIDENCE_CATEGORIES),
            "sources": [
                "sec_filing_events usable_trade_date",
                "form4 open_market_purchase usable_trade_date",
                "estimate_revision_ledger positive EPS deltas",
                "clean/trade news positive keyword T1/T2",
            ],
            "news_positive_terms": sorted(POSITIVE_NEWS_TERMS),
            "news_negative_terms": sorted(NEGATIVE_NEWS_TERMS),
            "windows": WINDOWS,
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "entry / event_or_llm: catalyst-backed early-entry research "
                "should only continue if prior non-OHLCV context separates "
                "accepted core winners from losers."
            ),
            "2_history_check": {
                "exp-20260530-013": (
                    "Rejected OHLCV-only pre-breakout early entry: aggregate EV "
                    "-1.9239 and PnL -$48,109.45."
                ),
                "exp-20260525-030/033": (
                    "VCP event-context attribution was not a clean catalyst "
                    "quality gate; prior catalyst/support buckets did not beat "
                    "the strongest baseline."
                ),
                "exp-20260530-006/008/009": (
                    "Raw SEC recurrence/event-graph fields failed. This run "
                    "does not trade SEC recurrence; it joins multiple catalyst "
                    "sources to existing core trades."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": observed_gate["rule"],
            "5_reproducibility": (
                f".venv\\Scripts\\python.exe -B quant\\experiments\\{Path(__file__).name}"
            ),
        },
        "backtest_protocol": (
            "Uses docs/backtesting.md canonical windows to obtain unchanged core "
            "baseline trades, then performs read-only attribution. No after "
            "strategy variant is run because no trade behavior changes."
        ),
        "before_metrics": before_after,
        "after_metrics": before_after,
        "delta_metrics": {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "trade_count": 0,
        },
        "attribution_summary": {
            "trade_count": len(trade_rows),
            "high_confidence_catalyst_bucket": high_bucket,
            "any_catalyst_context_bucket": any_bucket,
            "category_summaries": _category_summaries(trade_rows),
            "snow_trade_rows": snow_rows,
        },
        "window_attribution": window_attr,
        "source_coverage": source_stats,
        "observed_gate": observed_gate,
        "decision": decision,
        "rejection_reason": (
            None if observed_passed else "; ".join(observed_gate["failed_reasons"])
        ),
        "next_retry_requires": (
            "If the observed gate fails, do not test a catalyst-backed early buy "
            "rule yet. Next step should improve catalyst quality labels or collect "
            "forward replacement rows on named latency cases before changing entry."
        ),
        "prediction": {
            "success_probability": 0.25,
            "expected_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "main_failure_modes": [
                "coverage_too_thin",
                "no_catalyst_separation",
                "single_ticker_concentration",
                "news_archive_incomplete",
            ],
            "confidence_reason": (
                "OHLCV-only early entry failed in exp-20260530-013, while the "
                "playbook still ranks event/LLM fields as viable only when they "
                "become auditable production-visible context."
            ),
            "recorded_at": "2026-05-30T08:01:11+00:00",
            "brier_score": round((0.25 - actual_success) ** 2, 6),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "read_only_attribution": True,
            "parity_test_added": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
        },
        "related_files": [
            _repo_rel(OUT_JSON),
            _repo_rel(ROWS_JSON),
            _repo_rel(BEFORE_AGG_JSON),
            _repo_rel(AFTER_AGG_JSON),
            _repo_rel(DOC_LOG),
            _repo_rel(DOC_TICKET),
            _repo_rel(DOC_ARTIFACT),
            f"quant/experiments/{Path(__file__).name}",
        ],
    }

    _write_json(OUT_JSON, payload)
    _write_json(ROWS_JSON, trade_rows)
    _write_json(BEFORE_AGG_JSON, before_after)
    _write_json(AFTER_AGG_JSON, before_after)
    _write_json(DOC_LOG, payload)
    _write_json(
        DOC_TICKET,
        {
            "experiment_id": EXPERIMENT_ID,
            "lane": "alpha_search",
            "owner": "codex-catalyst-early-entry",
            "status": "observed_only",
            "hypothesis": payload["hypothesis"],
            "single_causal_variable": payload["single_causal_variable"],
            "decision": decision,
            "observed_gate": observed_gate,
            "updated_at": timestamp,
        },
    )
    DOC_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT.write_text(_artifact_markdown(payload), encoding="utf-8")
    _append_jsonl_once(EXPERIMENT_LOG_JSONL, payload)

    print(json.dumps(_safe(observed_gate), indent=2, sort_keys=True))
    print(f"{EXPERIMENT_ID} {decision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
