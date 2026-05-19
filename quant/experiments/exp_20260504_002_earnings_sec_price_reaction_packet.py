"""exp-20260504-002 earnings + SEC filing + price reaction packet audit.

Shadow-only alpha search. This script builds a replayable event packet from:

1. inferred point-in-time earnings calendar rows,
2. backfilled SEC public-PIT filing events, and
3. first post-shock price reaction / forward drift.

It does not change production or backtest strategy logic.
"""

from __future__ import annotations

import json
import math
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
EXPERIMENT_ID = "exp-20260504-002"
START = "2025-10-23"
END = "2026-04-21"
SNAPSHOT_PATH = DATA_DIR / "ohlcv_snapshot_20251023_20260421.json"
SEC_EVENTS_PATH = DATA_DIR / "non_ohlcv" / "sec_filing_events_20241002_20260421.jsonl"
BASELINE_PATH = DATA_DIR / "backtest_results_20260503.json"
OUT_DIR = DATA_DIR / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "earnings_sec_price_reaction_packet.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REPORT_MD = (
    REPO_ROOT
    / "docs"
    / "non_ohlcv_data_audit"
    / "earnings_sec_price_reaction_packet_20260504.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": START,
        "end": END,
        "coverage": "covered",
        "state_note": "slow-melt bull / accepted-stack dominant tape",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "coverage": "blocked_no_earnings_snapshots",
        "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "coverage": "blocked_no_earnings_snapshots",
        "state_note": "mixed-to-weak older tape with lower win rate",
    }),
])

EARNINGS_DTE_LOOKAHEAD = 7
SEC_8K_MATCH_TRADING_DAYS = 3
SEC_PERIODIC_MATCH_TRADING_DAYS = 10
HORIZONS = (5, 10, 20)
STRONG_REACTION_EXCESS_MIN = 0.02
MIN_PROMISING_VALID_10D = 10


def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _as_float(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        out = float(value)
        if math.isfinite(out):
            return out
    return None


def _round(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def _pct_change(start: float | None, end: float | None) -> float | None:
    if start is None or end is None or start <= 0:
        return None
    return end / start - 1.0


def _compact_pct(value: float | None) -> float | None:
    return _round(value * 100.0, 4) if value is not None else None


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def load_snapshot(path: Path = SNAPSHOT_PATH) -> dict[str, list[dict[str, Any]]]:
    payload = _load_json(path, {})
    raw = payload.get("ohlcv") if isinstance(payload, dict) else {}
    out: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in (raw or {}).items():
        converted = []
        for row in rows or []:
            date_value = str(row.get("Date") or row.get("date") or "")[:10]
            if not date_value:
                continue
            converted.append({
                "date": date_value,
                "open": _as_float(row.get("Open") if "Open" in row else row.get("open")),
                "close": _as_float(row.get("Close") if "Close" in row else row.get("close")),
                "volume": _as_float(row.get("Volume") if "Volume" in row else row.get("volume")),
            })
        if converted:
            out[str(ticker).upper()] = sorted(converted, key=lambda item: item["date"])
    return out


def trading_dates_from_snapshot(snapshot: dict[str, list[dict[str, Any]]]) -> list[str]:
    return [row["date"] for row in snapshot.get("SPY", [])]


def idx_on_or_after(rows: list[dict[str, Any]] | list[str], target_date: str) -> int | None:
    for idx, row in enumerate(rows):
        row_date = row if isinstance(row, str) else row["date"]
        if row_date >= target_date:
            return idx
    return None


def idx_after(rows: list[dict[str, Any]] | list[str], target_date: str) -> int | None:
    for idx, row in enumerate(rows):
        row_date = row if isinstance(row, str) else row["date"]
        if row_date > target_date:
            return idx
    return None


def add_trading_days(trading_dates: list[str], start_date: str, days: int) -> str | None:
    start_idx = idx_on_or_after(trading_dates, start_date)
    if start_idx is None:
        return None
    target_idx = start_idx + days
    if target_idx >= len(trading_dates):
        return None
    return trading_dates[target_idx]


def _snapshot_date_from_path(path: Path) -> str:
    raw = path.stem.split("_")[-1]
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"


def load_earnings_snapshot_rows() -> dict[str, dict[str, dict[str, Any]]]:
    snapshots: dict[str, dict[str, dict[str, Any]]] = {}
    for path in sorted(DATA_DIR.glob("earnings_snapshot_*.json")):
        payload = _load_json(path, {})
        earnings = payload.get("earnings") if isinstance(payload, dict) else {}
        if not isinstance(earnings, dict):
            continue
        snapshots[_snapshot_date_from_path(path)] = {
            str(ticker).upper(): dict(row)
            for ticker, row in earnings.items()
            if isinstance(row, dict)
        }
    return snapshots


def _actual_changed(before: float | None, after: float | None) -> bool:
    if before is None or after is None:
        return False
    return abs(after - before) > 1e-9


def _attach_post_event_actual(
    event: dict[str, Any],
    earnings_snapshots: dict[str, dict[str, dict[str, Any]]],
    trading_dates: list[str],
) -> None:
    ticker = event["ticker"]
    event_date = event["event_date"]
    pre_actual = _as_float(event.get("eps_actual_last"))
    pre_estimate = _as_float(event.get("eps_estimate"))
    if pre_actual is None:
        return
    start_idx = idx_after(trading_dates, event_date)
    if start_idx is None:
        return
    end_idx = min(len(trading_dates) - 1, start_idx + 10)
    for date_value in trading_dates[start_idx : end_idx + 1]:
        row = (earnings_snapshots.get(date_value) or {}).get(ticker)
        if not row:
            continue
        post_actual = _as_float(row.get("eps_actual_last"))
        if not _actual_changed(pre_actual, post_actual):
            continue
        event["post_event_eps_actual"] = post_actual
        event["post_event_actual_snapshot_date"] = date_value
        if pre_estimate is not None and abs(pre_estimate) > 1e-9:
            event["eps_surprise_pct"] = _round((post_actual - pre_estimate) / abs(pre_estimate) * 100.0, 4)
        return


def build_earnings_events(
    earnings_snapshots: dict[str, dict[str, dict[str, Any]]],
    trading_dates: list[str],
    *,
    start: str = START,
    end: str = END,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for snapshot_date, rows in sorted(earnings_snapshots.items()):
        if snapshot_date > end:
            continue
        for ticker, data in rows.items():
            dte = data.get("days_to_earnings")
            if not isinstance(dte, int) or dte < 0 or dte > EARNINGS_DTE_LOOKAHEAD:
                continue
            event_date = add_trading_days(trading_dates, snapshot_date, dte)
            if event_date is None or event_date < start or event_date > end:
                continue
            observation = {
                "ticker": ticker,
                "event_date": event_date,
                "source_snapshot_date": snapshot_date,
                "days_to_earnings": dte,
                "eps_estimate": _as_float(data.get("eps_estimate")),
                "eps_actual_last": _as_float(data.get("eps_actual_last")),
                "avg_historical_surprise_pct": _as_float(data.get("avg_historical_surprise_pct")),
                "historical_surprise_pct": data.get("historical_surprise_pct") or [],
            }
            grouped[(ticker, event_date)].append(observation)

    events: list[dict[str, Any]] = []
    for (ticker, event_date), observations in grouped.items():
        observations = sorted(
            observations,
            key=lambda row: (row["days_to_earnings"], row["source_snapshot_date"]),
        )
        chosen = dict(observations[0])
        chosen["pre_event_snapshot_count"] = len(observations)
        chosen["all_source_snapshot_dates"] = [row["source_snapshot_date"] for row in observations]
        chosen["min_days_to_earnings_seen"] = min(row["days_to_earnings"] for row in observations)
        _attach_post_event_actual(chosen, earnings_snapshots, trading_dates)
        events.append(chosen)
    return sorted(events, key=lambda row: (row["event_date"], row["ticker"]))


def load_sec_events(path: Path = SEC_EVENTS_PATH) -> dict[str, list[dict[str, Any]]]:
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in _load_jsonl(path):
        ticker = str(row.get("ticker") or "").upper()
        usable = str(row.get("usable_trade_date") or "")[:10]
        if not ticker or not usable:
            continue
        normalized = dict(row)
        normalized["ticker"] = ticker
        normalized["usable_trade_date"] = usable
        normalized["form_base"] = str(row.get("form_base") or "").upper()
        normalized["form_type"] = str(row.get("form_type") or "").upper()
        normalized["eight_k_item_codes"] = [str(code) for code in row.get("eight_k_item_codes") or []]
        by_ticker[ticker].append(normalized)
    return {
        ticker: sorted(rows, key=lambda item: (item["usable_trade_date"], item.get("accepted_at") or ""))
        for ticker, rows in by_ticker.items()
    }


def match_sec_filings(
    event: dict[str, Any],
    sec_by_ticker: dict[str, list[dict[str, Any]]],
    trading_dates: list[str],
) -> dict[str, Any]:
    event_date = event["event_date"]
    max_8k = add_trading_days(trading_dates, event_date, SEC_8K_MATCH_TRADING_DAYS) or event_date
    max_periodic = add_trading_days(trading_dates, event_date, SEC_PERIODIC_MATCH_TRADING_DAYS) or event_date
    matches = []
    for row in sec_by_ticker.get(event["ticker"], []):
        usable = row["usable_trade_date"]
        form_base = row.get("form_base")
        if form_base == "8-K" and event_date <= usable <= max_8k:
            matches.append(row)
        elif form_base in {"10-Q", "10-K"} and event_date <= usable <= max_periodic:
            matches.append(row)

    form_bases = sorted({row.get("form_base") for row in matches if row.get("form_base")})
    form_types = sorted({row.get("form_type") for row in matches if row.get("form_type")})
    item_codes = sorted({
        code
        for row in matches
        for code in row.get("eight_k_item_codes") or []
    })
    has_results_8k = any(
        row.get("form_base") == "8-K" and "2.02" in (row.get("eight_k_item_codes") or [])
        for row in matches
    )
    has_periodic = any(row.get("form_base") in {"10-Q", "10-K"} for row in matches)
    if has_results_8k:
        packet_type = "results_8k"
    elif has_periodic:
        packet_type = "periodic_10q_10k"
    elif matches:
        packet_type = "other_nearby_sec"
    else:
        packet_type = "no_nearby_sec"
    return {
        "sec_match_count": len(matches),
        "sec_packet_type": packet_type,
        "has_results_8k": has_results_8k,
        "has_periodic_10q_10k": has_periodic,
        "sec_form_bases": form_bases,
        "sec_form_types": form_types,
        "eight_k_item_codes": item_codes,
        "sec_usable_trade_dates": sorted({row["usable_trade_date"] for row in matches}),
        "sec_accessions": sorted({str(row.get("accession_number")) for row in matches if row.get("accession_number")}),
        "sample_archive_urls": [row.get("archive_url") for row in matches[:3] if row.get("archive_url")],
    }


def _reaction_bucket(excess_return: float | None) -> str:
    if excess_return is None:
        return "reaction_unknown"
    if excess_return >= STRONG_REACTION_EXCESS_MIN:
        return "positive_excess_ge_2pct"
    if excess_return >= 0:
        return "positive_excess_0_to_2pct"
    if excess_return <= -STRONG_REACTION_EXCESS_MIN:
        return "negative_excess_le_minus_2pct"
    return "negative_excess_0_to_minus_2pct"


def _surprise_bucket(value: float | None) -> str:
    if value is None:
        return "surprise_unknown"
    if value >= 10:
        return "avg_hist_surprise_ge_10pct"
    if value >= 3:
        return "avg_hist_surprise_3_to_10pct"
    if value >= 0:
        return "avg_hist_surprise_0_to_3pct"
    return "avg_hist_surprise_negative"


def _current_surprise_bucket(value: float | None) -> str:
    if value is None:
        return "current_surprise_unknown"
    if value >= 10:
        return "current_surprise_ge_10pct"
    if value >= 0:
        return "current_surprise_0_to_10pct"
    return "current_surprise_negative"


def evaluate_event(
    event: dict[str, Any],
    snapshot: dict[str, list[dict[str, Any]]],
    trading_dates: list[str],
) -> dict[str, Any]:
    row = dict(event)
    ticker_rows = snapshot.get(event["ticker"])
    spy_rows = snapshot.get("SPY")
    qqq_rows = snapshot.get("QQQ")
    if not ticker_rows or not spy_rows:
        row["price_status"] = "missing_ticker_or_spy_price"
        return row

    shock_trade_date = (
        event["sec_usable_trade_dates"][0]
        if event.get("sec_usable_trade_dates")
        else event["event_date"]
    )
    reaction_idx = idx_on_or_after(ticker_rows, shock_trade_date)
    spy_reaction_idx = idx_on_or_after(spy_rows, shock_trade_date)
    if reaction_idx is None or spy_reaction_idx is None:
        row["price_status"] = "no_reaction_day"
        return row
    if reaction_idx == 0 or spy_reaction_idx == 0:
        row["price_status"] = "no_previous_close"
        return row
    entry_idx = idx_after(ticker_rows, ticker_rows[reaction_idx]["date"])
    spy_entry_idx = idx_after(spy_rows, spy_rows[spy_reaction_idx]["date"])
    if entry_idx is None or spy_entry_idx is None:
        row["price_status"] = "no_entry_day"
        return row

    prev = ticker_rows[reaction_idx - 1]
    reaction = ticker_rows[reaction_idx]
    spy_prev = spy_rows[spy_reaction_idx - 1]
    spy_reaction = spy_rows[spy_reaction_idx]
    reaction_return = _pct_change(prev["close"], reaction["close"])
    spy_reaction_return = _pct_change(spy_prev["close"], spy_reaction["close"])
    reaction_excess = (
        reaction_return - spy_reaction_return
        if reaction_return is not None and spy_reaction_return is not None
        else None
    )
    gap_return = _pct_change(prev["close"], reaction["open"])
    intraday_reaction_return = _pct_change(reaction["open"], reaction["close"])

    qqq_reaction_return = None
    qqq_reaction_excess = None
    qqq_entry_idx = None
    if qqq_rows:
        qqq_reaction_idx = idx_on_or_after(qqq_rows, shock_trade_date)
        if qqq_reaction_idx is not None and qqq_reaction_idx > 0:
            qqq_reaction_return = _pct_change(
                qqq_rows[qqq_reaction_idx - 1]["close"],
                qqq_rows[qqq_reaction_idx]["close"],
            )
            if reaction_return is not None and qqq_reaction_return is not None:
                qqq_reaction_excess = reaction_return - qqq_reaction_return
            qqq_entry_idx = idx_after(qqq_rows, qqq_rows[qqq_reaction_idx]["date"])

    row.update({
        "price_status": "covered",
        "shock_trade_date": shock_trade_date,
        "reaction_date": reaction["date"],
        "entry_date": ticker_rows[entry_idx]["date"],
        "reaction_return": _round(reaction_return),
        "spy_reaction_return": _round(spy_reaction_return),
        "reaction_excess_return": _round(reaction_excess),
        "qqq_reaction_return": _round(qqq_reaction_return),
        "reaction_excess_vs_qqq": _round(qqq_reaction_excess),
        "gap_return": _round(gap_return),
        "intraday_reaction_return": _round(intraday_reaction_return),
        "reaction_bucket": _reaction_bucket(reaction_excess),
        "avg_hist_surprise_bucket": _surprise_bucket(_as_float(event.get("avg_historical_surprise_pct"))),
        "current_surprise_bucket": _current_surprise_bucket(_as_float(event.get("eps_surprise_pct"))),
        "horizons": {},
    })

    entry_open = ticker_rows[entry_idx]["open"]
    spy_entry_open = spy_rows[spy_entry_idx]["open"]
    qqq_entry_open = qqq_rows[qqq_entry_idx]["open"] if qqq_rows and qqq_entry_idx is not None else None
    for horizon in HORIZONS:
        key = f"{horizon}d"
        end_idx = entry_idx + horizon
        spy_end_idx = spy_entry_idx + horizon
        if end_idx >= len(ticker_rows) or spy_end_idx >= len(spy_rows):
            row["horizons"][key] = {"status": "pending"}
            continue
        ticker_return = _pct_change(entry_open, ticker_rows[end_idx]["close"])
        spy_return = _pct_change(spy_entry_open, spy_rows[spy_end_idx]["close"])
        if ticker_return is None or spy_return is None:
            row["horizons"][key] = {"status": "bad_price"}
            continue
        horizon_payload = {
            "status": "valid",
            "return": _round(ticker_return),
            "spy_return": _round(spy_return),
            "excess_return": _round(ticker_return - spy_return),
            "end_date": ticker_rows[end_idx]["date"],
        }
        if qqq_rows and qqq_entry_idx is not None and qqq_entry_open is not None:
            qqq_end_idx = qqq_entry_idx + horizon
            if qqq_end_idx < len(qqq_rows):
                qqq_return = _pct_change(qqq_entry_open, qqq_rows[qqq_end_idx]["close"])
                horizon_payload["qqq_return"] = _round(qqq_return)
                horizon_payload["excess_vs_qqq"] = (
                    _round(ticker_return - qqq_return)
                    if qqq_return is not None
                    else None
                )
        row["horizons"][key] = horizon_payload
    return row


def _date_rank(value: Any) -> int:
    text = str(value or "").replace("-", "")
    return int(text) if text.isdigit() else 0


def dedupe_event_packets(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        accessions = tuple(row.get("sec_accessions") or [])
        if accessions:
            key = (
                row.get("ticker"),
                row.get("shock_trade_date") or row.get("event_date"),
                row.get("sec_packet_type"),
                accessions,
            )
        else:
            key = (
                row.get("ticker"),
                row.get("event_date"),
                row.get("sec_packet_type"),
                accessions,
            )
        grouped[key].append(row)

    deduped = []
    duplicate_groups = 0
    duplicate_rows_removed = 0
    for group_rows in grouped.values():
        if len(group_rows) > 1:
            duplicate_groups += 1
            duplicate_rows_removed += len(group_rows) - 1
        chosen = sorted(
            group_rows,
            key=lambda row: (
                row.get("price_status") != "covered",
                row.get("days_to_earnings") if isinstance(row.get("days_to_earnings"), int) else 99,
                -_date_rank(row.get("source_snapshot_date")),
            ),
        )[0]
        chosen = dict(chosen)
        chosen["deduped_from_event_count"] = len(group_rows)
        if len(group_rows) > 1:
            chosen["deduped_event_dates"] = sorted({str(row.get("event_date")) for row in group_rows})
        deduped.append(chosen)
    return sorted(deduped, key=lambda row: (row.get("reaction_date") or row.get("event_date") or "", row.get("ticker") or "")), {
        "duplicate_packet_groups": duplicate_groups,
        "duplicate_packet_rows_removed": duplicate_rows_removed,
    }


def _summary(values: list[float]) -> dict[str, Any]:
    clean = [float(value) for value in values if isinstance(value, (int, float)) and math.isfinite(float(value))]
    if not clean:
        return {"count": 0, "avg": None, "median": None, "p25": None, "p75": None, "win_rate": None}
    ordered = sorted(clean)
    return {
        "count": len(clean),
        "avg": round(mean(clean), 6),
        "median": round(median(clean), 6),
        "p25": round(ordered[int((len(ordered) - 1) * 0.25)], 6),
        "p75": round(ordered[int((len(ordered) - 1) * 0.75)], 6),
        "win_rate": round(sum(1 for value in clean if value > 0) / len(clean), 4),
    }


def _valid_values(rows: list[dict[str, Any]], horizon_key: str, field: str = "excess_return") -> list[float]:
    values = []
    for row in rows:
        data = (row.get("horizons") or {}).get(horizon_key) or {}
        value = data.get(field)
        if data.get("status") == "valid" and isinstance(value, (int, float)):
            values.append(float(value))
    return values


def summarize_forward(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        f"{horizon}d": {
            "return": _summary(_valid_values(rows, f"{horizon}d", "return")),
            "excess_return": _summary(_valid_values(rows, f"{horizon}d", "excess_return")),
            "excess_vs_qqq": _summary(_valid_values(rows, f"{horizon}d", "excess_vs_qqq")),
        }
        for horizon in HORIZONS
    }


def summarize_group(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key) or "unknown")].append(row)
    return {
        group_key: {
            "event_count": len(group_rows),
            "forward_distribution": summarize_forward(group_rows),
        }
        for group_key, group_rows in sorted(grouped.items())
    }


def summarize_pair(rows: list[dict[str, Any]], left: str, right: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[f"{row.get(left) or 'unknown'}|{row.get(right) or 'unknown'}"].append(row)
    return {
        group_key: {
            "event_count": len(group_rows),
            "forward_distribution": summarize_forward(group_rows),
        }
        for group_key, group_rows in sorted(grouped.items())
    }


def _latest_baseline_metrics() -> dict[str, Any]:
    payload = _load_json(BASELINE_PATH, {})
    benchmarks = payload.get("benchmarks") or {}
    return {
        "source_file": str(BASELINE_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
        "period": payload.get("period"),
        "expected_value_score": payload.get("expected_value_score"),
        "sharpe_daily": payload.get("sharpe_daily"),
        "total_pnl": payload.get("total_pnl"),
        "total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "max_drawdown_pct": payload.get("max_drawdown_pct"),
        "win_rate": payload.get("win_rate"),
        "trade_count": payload.get("total_trades"),
        "survival_rate": payload.get("survival_rate"),
        "signals_generated": payload.get("signals_generated"),
        "signals_survived": payload.get("signals_survived"),
        "converged": (payload.get("convergence") or {}).get("converged"),
    }


def _horizon_excess(
    ticker: str,
    entry_date: str,
    snapshot: dict[str, list[dict[str, Any]]],
    horizon: int = 10,
) -> float | None:
    rows = snapshot.get(str(ticker).upper())
    spy_rows = snapshot.get("SPY")
    if not rows or not spy_rows:
        return None
    entry_idx = idx_on_or_after(rows, entry_date)
    spy_entry_idx = idx_on_or_after(spy_rows, entry_date)
    if entry_idx is None or spy_entry_idx is None:
        return None
    end_idx = entry_idx + horizon
    spy_end_idx = spy_entry_idx + horizon
    if end_idx >= len(rows) or spy_end_idx >= len(spy_rows):
        return None
    ticker_ret = _pct_change(rows[entry_idx]["open"], rows[end_idx]["close"])
    spy_ret = _pct_change(spy_rows[spy_entry_idx]["open"], spy_rows[spy_end_idx]["close"])
    if ticker_ret is None or spy_ret is None:
        return None
    return ticker_ret - spy_ret


def attach_slot_conflicts(
    rows: list[dict[str, Any]],
    baseline_path: Path,
    snapshot: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    baseline = _load_json(baseline_path, {})
    core_by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in baseline.get("trades") or []:
        if trade.get("strategy") not in {"trend_long", "breakout_long"}:
            continue
        entry_date = str(trade.get("entry_date") or "")[:10]
        ticker = str(trade.get("ticker") or "").upper()
        if not entry_date or not ticker:
            continue
        core_by_day[entry_date].append({
            "ticker": ticker,
            "strategy": trade.get("strategy"),
            "pnl": trade.get("pnl"),
            "pnl_pct_net": trade.get("pnl_pct_net"),
            "core_10d_excess_return": _horizon_excess(ticker, entry_date, snapshot, horizon=10),
        })

    enriched = []
    replacement_values = []
    conflict_count = 0
    valid_replacement_count = 0
    positive_replacement_count = 0
    for row in rows:
        candidate = dict(row)
        same_day = core_by_day.get(str(row.get("entry_date") or "")[:10], [])
        candidate["same_day_core_trade_count"] = len(same_day)
        candidate["same_day_core_trades"] = same_day[:5]
        candidate["slot_conflict_proxy"] = bool(same_day)
        if same_day:
            conflict_count += 1
        core_values = [
            float(item["core_10d_excess_return"])
            for item in same_day
            if isinstance(item.get("core_10d_excess_return"), (int, float))
        ]
        candidate_10d = ((candidate.get("horizons") or {}).get("10d") or {}).get("excess_return")
        if core_values and isinstance(candidate_10d, (int, float)):
            core_avg = mean(core_values)
            replacement = float(candidate_10d) - core_avg
            candidate["same_day_core_avg_10d_excess_return"] = _round(core_avg)
            candidate["replacement_value_10d_excess_proxy"] = _round(replacement)
            replacement_values.append(replacement)
            valid_replacement_count += 1
            if replacement > 0:
                positive_replacement_count += 1
        else:
            candidate["same_day_core_avg_10d_excess_return"] = None
            candidate["replacement_value_10d_excess_proxy"] = None
        enriched.append(candidate)

    return enriched, {
        "same_day_core_conflict_count": conflict_count,
        "same_day_core_conflict_rate": round(conflict_count / len(rows), 4) if rows else None,
        "valid_replacement_proxy_count": valid_replacement_count,
        "positive_replacement_proxy_count": positive_replacement_count,
        "positive_replacement_proxy_rate": (
            round(positive_replacement_count / valid_replacement_count, 4)
            if valid_replacement_count
            else None
        ),
        "replacement_value_10d_excess_proxy": _summary(replacement_values),
    }


def _compact_event(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": row.get("ticker"),
        "event_date": row.get("event_date"),
        "source_snapshot_date": row.get("source_snapshot_date"),
        "days_to_earnings": row.get("days_to_earnings"),
        "eps_estimate": row.get("eps_estimate"),
        "eps_actual_last": row.get("eps_actual_last"),
        "post_event_eps_actual": row.get("post_event_eps_actual"),
        "eps_surprise_pct": row.get("eps_surprise_pct"),
        "avg_historical_surprise_pct": row.get("avg_historical_surprise_pct"),
        "sec_packet_type": row.get("sec_packet_type"),
        "sec_match_count": row.get("sec_match_count"),
        "eight_k_item_codes": row.get("eight_k_item_codes"),
        "shock_trade_date": row.get("shock_trade_date"),
        "reaction_date": row.get("reaction_date"),
        "entry_date": row.get("entry_date"),
        "reaction_excess_return": row.get("reaction_excess_return"),
        "reaction_excess_vs_qqq": row.get("reaction_excess_vs_qqq"),
        "reaction_bucket": row.get("reaction_bucket"),
        "horizons": row.get("horizons"),
        "same_day_core_trade_count": row.get("same_day_core_trade_count"),
        "replacement_value_10d_excess_proxy": row.get("replacement_value_10d_excess_proxy"),
    }


def _primary_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row for row in rows
        if row.get("sec_packet_type") == "results_8k"
        and row.get("reaction_bucket") in {"positive_excess_ge_2pct", "positive_excess_0_to_2pct"}
    ]


def _strong_primary_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row for row in rows
        if row.get("sec_packet_type") == "results_8k"
        and row.get("reaction_bucket") == "positive_excess_ge_2pct"
    ]


def _safe_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {key: _safe_payload(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_safe_payload(value) for value in payload]
    if isinstance(payload, float) and not math.isfinite(payload):
        return None
    return payload


def build_payload() -> dict[str, Any]:
    snapshot = load_snapshot(SNAPSHOT_PATH)
    trading_dates = trading_dates_from_snapshot(snapshot)
    earnings_snapshots = load_earnings_snapshot_rows()
    earnings_events = build_earnings_events(earnings_snapshots, trading_dates)
    sec_by_ticker = load_sec_events(SEC_EVENTS_PATH)

    raw_enriched_events = []
    for event in earnings_events:
        with_sec = dict(event)
        with_sec.update(match_sec_filings(event, sec_by_ticker, trading_dates))
        raw_enriched_events.append(evaluate_event(with_sec, snapshot, trading_dates))

    enriched_events, dedupe_summary = dedupe_event_packets(raw_enriched_events)
    covered = [row for row in enriched_events if row.get("price_status") == "covered"]
    covered, slot_summary = attach_slot_conflicts(covered, BASELINE_PATH, snapshot)
    primary_rows = _primary_rows(covered)
    strong_primary_rows = _strong_primary_rows(covered)
    primary_10d = _valid_values(primary_rows, "10d")
    strong_primary_10d = _valid_values(strong_primary_rows, "10d")

    if (
        len(primary_10d) >= MIN_PROMISING_VALID_10D
        and mean(primary_10d) > 0
        and _valid_values(primary_rows, "20d")
        and mean(_valid_values(primary_rows, "20d")) > 0
    ):
        status = "shadow_promising_coverage_limited"
        decision = "shadow_promising_coverage_limited"
        decision_rationale = (
            "Earnings events with nearby PIT-safe results 8-K filings and positive first "
            "excess reaction show positive 10d/20d drift in the covered late_strong window. "
            "This is not promotable yet because earnings snapshots do not cover the older "
            "non-overlapping windows."
        )
        next_action = (
            "Backfill or procure PIT earnings/revision fields for older windows, then retest "
            "the same event-packet definition before considering any ranking overlay."
        )
    else:
        status = "observed_only_not_promoted"
        decision = "observed_only_not_promoted"
        decision_rationale = (
            "The covered event packet did not clear a promotion-quality drift bar, or the "
            "sample is too thin after requiring nearby results 8-K context and positive reaction."
        )
        next_action = (
            "Do not tune nearby reaction thresholds. The next valid retry needs older PIT "
            "earnings coverage, XBRL fundamentals, or LLM financial-statement grading."
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": status,
        "decision": decision,
        "lane": "alpha_search",
        "mechanism_family": "earnings_sec_filing_price_reaction_alpha",
        "change_type": "shadow_event_packet_replay",
        "hypothesis": (
            "Inferred earnings events accompanied by PIT-safe SEC results filings and positive "
            "first excess price reaction may identify post-event drift better than earnings-only "
            "or raw SEC filing reaction cohorts."
        ),
        "alpha_hypothesis_category": "entry_ranking_event_confirmation",
        "history_check": {
            "mechanism_insight_guardrail": (
                "This avoids the rejected C-strategy single-field/checklist family and avoids "
                "the rejected raw SEC +2% reaction threshold by conditioning on earnings event packets."
            ),
            "similar_experiments": {
                "exp-20260426-037": "Post-earnings continuation used DTE0 snapshots and price confirmation but no SEC public-PIT filing backbone.",
                "exp-20260503-002": "Round-1 earnings/SEC schema was coverage-blocked before accession-level SEC backfill.",
                "exp-20260503-051": "Raw SEC filing reaction drift was rejected; this tests earnings-linked SEC filing packets.",
            },
            "why_not_simple_repeat": (
                "The new causal input is nearby PIT-safe SEC filing context attached to inferred "
                "earnings events from the snapshot archive."
            ),
        },
        "parameters": {
            "single_causal_variable": "nearby SEC filing context attached to inferred earnings events",
            "event_date_inference": "snapshot_date + days_to_earnings trading days, using SPY calendar",
            "earnings_dte_lookahead": EARNINGS_DTE_LOOKAHEAD,
            "sec_8k_match_window_trading_days": SEC_8K_MATCH_TRADING_DAYS,
            "sec_periodic_match_window_trading_days": SEC_PERIODIC_MATCH_TRADING_DAYS,
            "primary_packet": "sec_packet_type == results_8k and first reaction excess return > 0",
            "strong_packet": "sec_packet_type == results_8k and first reaction excess return >= +2%",
            "entry_timing": "next trading-day open after the reaction close",
            "forward_horizons": list(HORIZONS),
            "locked_variables": [
                "production universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "position sizing",
                "add-ons",
                "exits",
                "LLM/news replay",
            ],
        },
        "date_range": {
            "covered": f"{START} -> {END}",
            "blocked_secondary_windows": [
                "2025-04-23 -> 2025-10-22",
                "2024-10-02 -> 2025-04-22",
            ],
        },
        "market_regime_summary": {label: cfg["state_note"] for label, cfg in WINDOWS.items()},
        "coverage_by_window": {label: cfg["coverage"] for label, cfg in WINDOWS.items()},
        "before_metrics": {"late_strong": _latest_baseline_metrics()},
        "after_metrics": {"late_strong": _latest_baseline_metrics()},
        "expected_value_score_delta": 0.0,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "production_impact": "shadow_only_no_strategy_logic_changed",
        },
        "gate4": {
            "passed": False,
            "basis": "No promoted strategy change; baseline metrics are unchanged by design.",
        },
        "coverage": {
            "earnings_snapshot_dates": len(earnings_snapshots),
            "raw_inferred_earnings_event_count": len(earnings_events),
            "deduped_event_packet_count": len(enriched_events),
            **dedupe_summary,
            "price_covered_count": len(covered),
            "price_coverage_rate": round(len(covered) / len(enriched_events), 4) if enriched_events else None,
            "with_nearby_sec_count": sum(1 for row in covered if row.get("sec_packet_type") != "no_nearby_sec"),
            "with_results_8k_count": sum(1 for row in covered if row.get("sec_packet_type") == "results_8k"),
            "with_periodic_count": sum(1 for row in covered if row.get("sec_packet_type") == "periodic_10q_10k"),
            "with_current_eps_surprise_count": sum(1 for row in covered if row.get("eps_surprise_pct") is not None),
            "primary_packet_event_count": len(primary_rows),
            "primary_packet_valid_10d_count": len(primary_10d),
            "strong_packet_event_count": len(strong_primary_rows),
            "strong_packet_valid_10d_count": len(strong_primary_10d),
            "by_price_status": dict(Counter(row.get("price_status") for row in enriched_events)),
            "by_sec_packet_type": dict(Counter(row.get("sec_packet_type") for row in covered)),
            "by_reaction_bucket": dict(Counter(row.get("reaction_bucket") for row in covered)),
        },
        "shadow_metrics": {
            "all_earnings_events": {
                "forward_distribution": summarize_forward(covered),
                "by_sec_packet_type": summarize_group(covered, "sec_packet_type"),
                "by_reaction_bucket": summarize_group(covered, "reaction_bucket"),
                "by_avg_hist_surprise_bucket": summarize_group(covered, "avg_hist_surprise_bucket"),
                "by_current_surprise_bucket": summarize_group(covered, "current_surprise_bucket"),
                "by_packet_and_reaction": summarize_pair(covered, "sec_packet_type", "reaction_bucket"),
            },
            "primary_results_8k_positive_reaction": {
                "event_count": len(primary_rows),
                "forward_distribution": summarize_forward(primary_rows),
                "by_current_surprise_bucket": summarize_group(primary_rows, "current_surprise_bucket"),
                "top_10d_excess": [
                    _compact_event(row)
                    for row in sorted(
                        [
                            row for row in primary_rows
                            if isinstance(((row.get("horizons") or {}).get("10d") or {}).get("excess_return"), (int, float))
                        ],
                        key=lambda item: ((item.get("horizons") or {}).get("10d") or {}).get("excess_return"),
                        reverse=True,
                    )[:20]
                ],
            },
            "strong_results_8k_positive_reaction_ge_2pct": {
                "event_count": len(strong_primary_rows),
                "forward_distribution": summarize_forward(strong_primary_rows),
            },
            "slot_conflict": slot_summary,
            "sample_events": [_compact_event(row) for row in covered[:100]],
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
        },
        "decision_rationale": decision_rationale,
        "rejection_reason": None if decision != "observed_only_not_promoted" else decision_rationale,
        "next_retry_requires": [
            "Older PIT earnings coverage for at least two non-overlapping windows.",
            "If promoted later, a shared production/backtest feature module and reporting path.",
            "Richer filing semantics such as XBRL surprise fields or LLM financial-statement grading.",
        ],
        "next_action": next_action,
        "related_files": [
            "data/non_ohlcv/sec_filing_events_20241002_20260421.jsonl",
            "data/ohlcv_snapshot_20251023_20260421.json",
            "data/backtest_results_20260503.json",
            "quant/experiments/exp_20260504_002_earnings_sec_price_reaction_packet.py",
            "data/experiments/exp-20260504-002/earnings_sec_price_reaction_packet.json",
            "experiments/logs/exp-20260504-002.json",
            "docs/non_ohlcv_data_audit/earnings_sec_price_reaction_packet_20260504.md",
        ],
    }
    return _safe_payload(payload)


def _format_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.2f}%"


def _report_table(title: str, rows: dict[str, Any]) -> list[str]:
    lines = [f"## {title}", "", "| Cohort | Events | 10d excess avg | 10d win | 20d excess avg | 20d win |", "|---|---:|---:|---:|---:|---:|"]
    for key, data in rows.items():
        forward = data.get("forward_distribution") or {}
        d10 = ((forward.get("10d") or {}).get("excess_return") or {})
        d20 = ((forward.get("20d") or {}).get("excess_return") or {})
        lines.append(
            f"| {key} | {data.get('event_count')} | "
            f"{_format_pct(d10.get('avg'))} | {_format_pct(d10.get('win_rate'))} | "
            f"{_format_pct(d20.get('avg'))} | {_format_pct(d20.get('win_rate'))} |"
        )
    lines.append("")
    return lines


def build_report(payload: dict[str, Any]) -> str:
    coverage = payload["coverage"]
    primary = payload["shadow_metrics"]["primary_results_8k_positive_reaction"]
    primary_10d = primary["forward_distribution"]["10d"]["excess_return"]
    primary_20d = primary["forward_distribution"]["20d"]["excess_return"]
    lines = [
        "# Earnings + SEC filing + price reaction packet audit",
        "",
        f"- Experiment: `{EXPERIMENT_ID}`",
        f"- Status: `{payload['status']}`",
        f"- Covered window: `{payload['date_range']['covered']}`",
        "- Production impact: shadow-only; no strategy logic changed.",
        "",
        "## Headline",
        "",
        payload["decision_rationale"],
        "",
        "## Coverage",
        "",
        f"- Raw inferred earnings events: `{coverage['raw_inferred_earnings_event_count']}`",
        f"- Deduped event packets: `{coverage['deduped_event_packet_count']}`",
        f"- Price-covered events: `{coverage['price_covered_count']}`",
        f"- Nearby SEC packet events: `{coverage['with_nearby_sec_count']}`",
        f"- Results 8-K events: `{coverage['with_results_8k_count']}`",
        f"- Primary packet events: `{coverage['primary_packet_event_count']}`",
        f"- Primary valid 10d outcomes: `{coverage['primary_packet_valid_10d_count']}`",
        f"- Current EPS surprise inferred: `{coverage['with_current_eps_surprise_count']}`",
        "",
        "## Primary Packet",
        "",
        "| Cohort | Events | 10d excess avg | 10d win | 20d excess avg | 20d win |",
        "|---|---:|---:|---:|---:|---:|",
        (
            f"| results_8k + positive reaction | {primary['event_count']} | "
            f"{_format_pct(primary_10d.get('avg'))} | {_format_pct(primary_10d.get('win_rate'))} | "
            f"{_format_pct(primary_20d.get('avg'))} | {_format_pct(primary_20d.get('win_rate'))} |"
        ),
        "",
    ]
    lines.extend(_report_table("By SEC Packet Type", payload["shadow_metrics"]["all_earnings_events"]["by_sec_packet_type"]))
    lines.extend(_report_table("By Reaction Bucket", payload["shadow_metrics"]["all_earnings_events"]["by_reaction_bucket"]))
    lines.extend([
        "## Gate / Caveat",
        "",
        "- Gate 4 is intentionally not passed because this is not a promoted strategy change.",
        "- Mid/old windows are blocked by missing PIT earnings snapshots, so this cannot yet support production ranking.",
        "- The SEC side is public-availability PIT via EDGAR `accepted_at`; it does not prove local production observation.",
        "",
        "## Next Action",
        "",
        payload["next_action"],
        "",
    ])
    return "\n".join(lines)


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "title": "Earnings SEC price reaction packet",
        "summary": payload["decision_rationale"],
        "best_variant": "results_8k_positive_reaction",
        "best_variant_gate4": False,
        "delta_metrics": {
            "expected_value_score_delta": payload["expected_value_score_delta"],
            "coverage": payload["coverage"],
            "primary_packet": payload["shadow_metrics"]["primary_results_8k_positive_reaction"]["forward_distribution"],
        },
        "production_impact": payload["production_impact"],
        "next_action": payload["next_action"],
    }
    _write_json(TICKET_JSON, ticket)
    _write_text(REPORT_MD, build_report(payload))

    compact = dict(payload)
    compact.pop("shadow_metrics", None)
    compact["shadow_metrics_summary"] = {
        "primary_results_8k_positive_reaction": payload["shadow_metrics"]["primary_results_8k_positive_reaction"],
        "strong_results_8k_positive_reaction_ge_2pct": payload["shadow_metrics"]["strong_results_8k_positive_reaction_ge_2pct"],
        "slot_conflict": payload["shadow_metrics"]["slot_conflict"],
    }
    existing_lines = (
        EXPERIMENT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        if EXPERIMENT_LOG.exists()
        else []
    )
    kept_lines = [
        line for line in existing_lines
        if f'"experiment_id":"{EXPERIMENT_ID}"' not in line
        and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
    ]
    kept_lines.append(json.dumps(compact, ensure_ascii=False, separators=(",", ":")))
    EXPERIMENT_LOG.write_text("\n".join(kept_lines) + "\n", encoding="utf-8")


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(json.dumps({
        "experiment_id": payload["experiment_id"],
        "status": payload["status"],
        "decision": payload["decision"],
        "coverage": payload["coverage"],
        "primary_packet_10d_excess": (
            payload["shadow_metrics"]["primary_results_8k_positive_reaction"]
            ["forward_distribution"]["10d"]["excess_return"]
        ),
        "primary_packet_20d_excess": (
            payload["shadow_metrics"]["primary_results_8k_positive_reaction"]
            ["forward_distribution"]["20d"]["excess_return"]
        ),
        "slot_conflict": payload["shadow_metrics"]["slot_conflict"],
    }, indent=2, ensure_ascii=False))
    print(f"wrote: {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
