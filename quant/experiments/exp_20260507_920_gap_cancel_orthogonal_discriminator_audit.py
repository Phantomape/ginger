"""exp-20260507-920 gap-cancel orthogonal discriminator audit.

Loss-attribution only. This script gathers the three canonical windows'
``gap_cancel`` and ``adverse_gap_down_cancel`` entry skips, joins point-in-time
candidate features, and ranks one-variable discriminators for forward 20-day
return separation.

It does not change production policy, backtester behavior, signal generation,
ranking, sizing, fills, exits, or prompts.
"""

from __future__ import annotations

import csv
import json
import math
import re
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from constants import ROUND_TRIP_COST_PCT  # noqa: E402
from risk_engine import SECTOR_MAP  # noqa: E402


EXP_ID = "exp-20260507-920_gap_cancel_orthogonal_discriminator_audit"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_CSV = OUT_DIR / "gap_cancel_orthogonal_features.csv"
OUT_RANKING = OUT_DIR / "discriminator_ranking.json"
OUT_CATALOG = OUT_DIR / "event_catalog.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXP_ID}.json"

ORACLE_DIR = REPO_ROOT / "data" / "experiments" / "oracle_standard_3window_20260501_220042"

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": REPO_ROOT / "data" / "ohlcv_snapshot_20251023_20260421.json",
                "backtest": ORACLE_DIR / "late_strong_backtest.json",
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": REPO_ROOT / "data" / "ohlcv_snapshot_20250423_20251022.json",
                "backtest": ORACLE_DIR / "mid_weak_backtest.json",
                "state_note": "rotation-heavy bull where strategy profits but can lag indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": REPO_ROOT / "data" / "ohlcv_snapshot_20241002_20250422.json",
                "backtest": ORACLE_DIR / "old_thin_backtest.json",
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)

TARGET_DECISIONS = {"gap_cancel", "adverse_gap_down_cancel"}
FORWARD_RETURN_FIELD = "max_forward_return_pct"
STRONG_RETURN_THRESHOLD = 0.10

NEWS_POSITIVE_PATTERNS = (
    r"\bbeat(?:s|en)?\b",
    r"\braises? (?:guidance|outlook|forecast)\b",
    r"\bguidance raise\b",
    r"\bupgrade(?:s|d)?\b",
    r"\bapproval\b",
    r"\bbuyback\b",
    r"\brecord revenue\b",
    r"\bstrong demand\b",
)
NEWS_NEGATIVE_PATTERNS = (
    r"\bmiss(?:es|ed)?\b",
    r"\bcuts? (?:guidance|outlook|forecast)\b",
    r"\bguidance cut\b",
    r"\bdowngrade(?:s|d)?\b",
    r"\brecall\b",
    r"\bsec charges\b",
    r"\bdoj charges\b",
    r"\bbankruptcy\b",
    r"\bprofit warning\b",
)

CSV_FIELDS = [
    "window",
    "signal_date",
    "entry_date",
    "ticker",
    "sector",
    "strategy",
    "decision",
    "candidate_rank",
    "available_slots_at_entry_loop",
    "fill_open",
    "signal_entry",
    "gap_pct",
    "gap_abs_pct",
    "gap_bucket",
    "max_forward_return_pct",
    "forward_positive",
    "forward_strong_ge_10pct",
    "volume_vs_20d_avg",
    "news_t1_count_3d",
    "news_t2_count_3d",
    "news_t1t2_count_3d",
    "news_pos_count_3d",
    "news_neg_count_3d",
    "news_archive_covered_days_3d",
    "form4_buy_5d",
    "form4_net_buy_usd_5d",
    "form4_archive_available",
    "recent_8k_severity_5d",
    "recent_8k_count_5d",
    "sec_filing_archive_available",
    "days_since_earnings",
    "earnings_shock_pct",
    "earnings_archive_available",
    "atr14_t_over_t20",
    "bbwidth20",
    "sector_5d_rs",
    "sector_5d_rs_source",
    "feature_coverage_count",
]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in CSV_FIELDS})


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _repo_rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _date(value: Any) -> datetime:
    return datetime.strptime(str(value)[:10], "%Y-%m-%d")


def _date_key(value: datetime | str) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y%m%d")
    return str(value)[:10].replace("-", "")


def _iso(value: datetime) -> str:
    return value.strftime("%Y-%m-%d")


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _round(value: Any, digits: int = 6) -> Any:
    number = _safe_float(value)
    if number is None:
        return None
    return round(number, digits)


def _mean(values: list[float]) -> float | None:
    clean = [float(v) for v in values if isinstance(v, (int, float)) and math.isfinite(float(v))]
    return sum(clean) / len(clean) if clean else None


def _median(values: list[float]) -> float | None:
    clean = sorted(float(v) for v in values if isinstance(v, (int, float)) and math.isfinite(float(v)))
    if not clean:
        return None
    mid = len(clean) // 2
    if len(clean) % 2:
        return clean[mid]
    return (clean[mid - 1] + clean[mid]) / 2


def _pct_change(start: Any, end: Any) -> float | None:
    start_f = _safe_float(start)
    end_f = _safe_float(end)
    if start_f is None or end_f is None or start_f == 0:
        return None
    return end_f / start_f - 1.0


def _row_date(row: dict[str, Any]) -> str:
    return str(row.get("Date") or row.get("date") or "")[:10]


def _row_open(row: dict[str, Any]) -> float | None:
    return _safe_float(row.get("Open") if "Open" in row else row.get("open"))


def _row_high(row: dict[str, Any]) -> float | None:
    return _safe_float(row.get("High") if "High" in row else row.get("high"))


def _row_low(row: dict[str, Any]) -> float | None:
    return _safe_float(row.get("Low") if "Low" in row else row.get("low"))


def _row_close(row: dict[str, Any]) -> float | None:
    return _safe_float(row.get("Close") if "Close" in row else row.get("close"))


def _row_volume(row: dict[str, Any]) -> float | None:
    return _safe_float(row.get("Volume") if "Volume" in row else row.get("volume"))


def _ohlcv_rows_by_ticker(snapshot: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in (snapshot.get("ohlcv") or {}).items():
        clean = [row for row in rows or [] if _row_date(row)]
        out[str(ticker).upper()] = sorted(clean, key=_row_date)
    return out


def _row_index_by_date(rows_by_ticker: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, int]]:
    return {
        ticker: {_row_date(row): idx for idx, row in enumerate(rows)}
        for ticker, rows in rows_by_ticker.items()
    }


def _prior_rows(rows: list[dict[str, Any]], signal_date: str) -> list[dict[str, Any]]:
    return [row for row in rows if _row_date(row) <= signal_date]


def _next_rows_after(rows: list[dict[str, Any]], signal_date: str, horizon_days: int) -> list[dict[str, Any]]:
    return [row for row in rows if _row_date(row) > signal_date][:horizon_days]


def _trading_dates(rows_by_ticker: dict[str, list[dict[str, Any]]]) -> list[str]:
    dates = sorted({_row_date(row) for rows in rows_by_ticker.values() for row in rows})
    return [date for date in dates if date]


def _calendar_window(end_date: str, days_back: int) -> list[str]:
    end = _date(end_date)
    return [_date_key(end - timedelta(days=offset)) for offset in range(days_back, -1, -1)]


def _signal_context(rows_by_ticker: dict[str, list[dict[str, Any]]], ticker: str, signal_date: str) -> dict[str, Any]:
    prior = _prior_rows(rows_by_ticker.get(ticker, []), signal_date)
    if not prior:
        return {}
    current = prior[-1]
    volume = _row_volume(current)
    close = _row_close(current)
    prior20 = prior[-20:]
    volumes = [_row_volume(row) for row in prior20]
    volumes = [value for value in volumes if value is not None]
    return {
        "volume_vs_20d_avg": (
            volume / (sum(volumes) / len(volumes))
            if volume is not None and volumes and sum(volumes) > 0
            else None
        ),
        "close": close,
    }


def _true_ranges(rows: list[dict[str, Any]]) -> list[float | None]:
    out: list[float | None] = []
    previous_close = None
    for row in rows:
        high = _row_high(row)
        low = _row_low(row)
        if high is None or low is None:
            out.append(None)
            previous_close = _row_close(row)
            continue
        if previous_close is None:
            out.append(high - low)
        else:
            out.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
        previous_close = _row_close(row)
    return out


def _atr14_t_over_t20(rows_by_ticker: dict[str, list[dict[str, Any]]], ticker: str, signal_date: str) -> float | None:
    prior = _prior_rows(rows_by_ticker.get(ticker, []), signal_date)
    if len(prior) < 34:
        return None
    trs = _true_ranges(prior)
    atr14_series: list[float | None] = []
    for idx in range(len(trs)):
        window = [value for value in trs[max(0, idx - 13): idx + 1] if value is not None]
        atr14_series.append(sum(window) / len(window) if len(window) == 14 else None)
    current = atr14_series[-1]
    trailing = [value for value in atr14_series[-20:] if value is not None]
    avg = sum(trailing) / len(trailing) if trailing else None
    if current is None or avg is None or avg == 0:
        return None
    return current / avg


def _bbwidth20(rows_by_ticker: dict[str, list[dict[str, Any]]], ticker: str, signal_date: str) -> float | None:
    prior = _prior_rows(rows_by_ticker.get(ticker, []), signal_date)
    closes = [_row_close(row) for row in prior[-20:]]
    closes = [value for value in closes if value is not None]
    if len(closes) < 20:
        return None
    avg = sum(closes) / len(closes)
    if avg == 0:
        return None
    variance = sum((value - avg) ** 2 for value in closes) / len(closes)
    return 4.0 * math.sqrt(variance) / avg


def _return_over_trading_days(
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    idx_by_ticker: dict[str, dict[str, int]],
    ticker: str,
    signal_date: str,
    lookback_days: int,
) -> float | None:
    rows = rows_by_ticker.get(ticker)
    idx = idx_by_ticker.get(ticker, {}).get(signal_date)
    if not rows or idx is None or idx < lookback_days:
        return None
    start = _row_close(rows[idx - lookback_days])
    end = _row_close(rows[idx])
    return _pct_change(start, end)


def _sector_5d_rs(
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    idx_by_ticker: dict[str, dict[str, int]],
    ticker: str,
    signal_date: str,
) -> tuple[float | None, str | None]:
    sector = SECTOR_MAP.get(ticker, "Unknown")
    ticker_return = _return_over_trading_days(rows_by_ticker, idx_by_ticker, ticker, signal_date, 5)
    if ticker_return is None or sector == "Unknown":
        return None, None
    peer_returns = []
    for peer, peer_sector in SECTOR_MAP.items():
        if peer == ticker or peer_sector != sector:
            continue
        peer_return = _return_over_trading_days(rows_by_ticker, idx_by_ticker, peer, signal_date, 5)
        if peer_return is not None:
            peer_returns.append(peer_return)
    if not peer_returns:
        spy_return = _return_over_trading_days(rows_by_ticker, idx_by_ticker, "SPY", signal_date, 5)
        if spy_return is None:
            return None, None
        return ticker_return - spy_return, "spy_fallback"
    return ticker_return - (sum(peer_returns) / len(peer_returns)), "equal_weight_sector_basket"


def _gap_bucket(gap_pct: float | None) -> str | None:
    if gap_pct is None:
        return None
    value = abs(gap_pct)
    if 0.015 <= value < 0.02:
        return "1.5-2%"
    if 0.02 <= value < 0.03:
        return "2-3%"
    if 0.03 <= value < 0.04:
        return "3-4%"
    if 0.04 <= value < 0.05:
        return "4-5%"
    if value >= 0.05:
        return ">5%"
    return "<1.5%"


def _headline_matches(patterns: tuple[str, ...], text: str) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def _news_features(ticker: str, signal_date: str) -> dict[str, Any]:
    covered = 0
    t1 = t2 = pos = neg = 0
    examples = []
    for date_key in _calendar_window(signal_date, 3):
        path = REPO_ROOT / "data" / f"clean_trade_news_{date_key}.json"
        if not path.exists():
            continue
        covered += 1
        payload = _load_json(path)
        if not isinstance(payload, list):
            continue
        for item in payload:
            tickers = [str(value).upper() for value in item.get("tickers") or []]
            if ticker not in tickers:
                continue
            tier = item.get("tier")
            if tier == "T1":
                t1 += 1
            elif tier == "T2":
                t2 += 1
            text = f"{item.get('title') or ''} {item.get('summary') or ''}"
            is_pos = _headline_matches(NEWS_POSITIVE_PATTERNS, text)
            is_neg = _headline_matches(NEWS_NEGATIVE_PATTERNS, text)
            pos += int(is_pos)
            neg += int(is_neg)
            if len(examples) < 5:
                examples.append(
                    {
                        "archive_date": date_key,
                        "tier": tier,
                        "polarity": "mixed" if is_pos and is_neg else "positive" if is_pos else "negative" if is_neg else "unknown",
                        "title": item.get("title"),
                    }
                )
    if covered == 0:
        return {
            "news_t1_count_3d": None,
            "news_t2_count_3d": None,
            "news_t1t2_count_3d": None,
            "news_pos_count_3d": None,
            "news_neg_count_3d": None,
            "news_archive_covered_days_3d": 0,
            "news_examples": [],
        }
    return {
        "news_t1_count_3d": t1,
        "news_t2_count_3d": t2,
        "news_t1t2_count_3d": t1 + t2,
        "news_pos_count_3d": pos,
        "news_neg_count_3d": neg,
        "news_archive_covered_days_3d": covered,
        "news_examples": examples,
    }


def _form4_features(ticker: str, signal_date: str) -> dict[str, Any]:
    date_key = _date_key(signal_date)
    path = REPO_ROOT / "data" / "non_ohlcv" / f"form4_transactions_{date_key}.jsonl"
    if not path.exists():
        return {"form4_buy_5d": None, "form4_net_buy_usd_5d": None, "form4_archive_available": False, "form4_examples": []}
    start = _date(signal_date) - timedelta(days=5)
    end = _date(signal_date)
    rows = []
    for row in _load_jsonl(path):
        if str(row.get("ticker") or "").upper() != ticker:
            continue
        usable = row.get("usable_trade_date") or row.get("filing_date")
        if not usable:
            continue
        usable_dt = _date(usable)
        if not (start <= usable_dt <= end):
            continue
        rows.append(row)
    purchases = [row for row in rows if row.get("open_market_purchase_flag")]
    net_buy = 0.0
    for row in rows:
        value = _safe_float(row.get("transaction_value")) or 0.0
        if row.get("open_market_purchase_flag") or str(row.get("acquired_disposed_code") or "").upper() == "A":
            net_buy += value
        elif str(row.get("acquired_disposed_code") or "").upper() == "D":
            net_buy -= value
    return {
        "form4_buy_5d": len(purchases),
        "form4_net_buy_usd_5d": round(net_buy, 2),
        "form4_archive_available": True,
        "form4_examples": [
            {
                "usable_trade_date": row.get("usable_trade_date"),
                "transaction_code": row.get("transaction_code"),
                "open_market_purchase_flag": row.get("open_market_purchase_flag"),
                "transaction_value": row.get("transaction_value"),
                "owner_name": row.get("owner_name"),
            }
            for row in rows[:5]
        ],
    }


def _item_codes(value: Any) -> list[str]:
    if isinstance(value, list):
        out = []
        for item in value:
            if isinstance(item, dict):
                code = item.get("code")
            else:
                code = item
            if code:
                out.append(str(code))
        return out
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def _eight_k_severity(codes: list[str]) -> int:
    if not codes:
        return 1
    score = 1
    if "2.02" in codes:
        score = max(score, 3)
    if set(codes) & {"1.01", "2.03", "3.02", "5.02"}:
        score = max(score, 2)
    return score


def _sec_filing_features(ticker: str, signal_date: str) -> dict[str, Any]:
    date_key = _date_key(signal_date)
    path = REPO_ROOT / "data" / "non_ohlcv" / f"sec_filing_features_{date_key}.jsonl"
    if not path.exists():
        return {
            "recent_8k_severity_5d": None,
            "recent_8k_count_5d": None,
            "sec_filing_archive_available": False,
            "sec_filing_examples": [],
        }
    start = _date(signal_date) - timedelta(days=5)
    end = _date(signal_date)
    matches = []
    for row in _load_jsonl(path):
        if str(row.get("ticker") or "").upper() != ticker:
            continue
        if not str(row.get("form_type") or "").upper().startswith("8-K"):
            continue
        usable = row.get("usable_trade_date") or row.get("event_date")
        if not usable:
            continue
        usable_dt = _date(usable)
        if start <= usable_dt <= end:
            codes = _item_codes(row.get("eight_k_item_type") or row.get("eight_k_item_codes"))
            matches.append({**row, "_codes": codes, "_severity": _eight_k_severity(codes)})
    return {
        "recent_8k_severity_5d": max([row["_severity"] for row in matches], default=0),
        "recent_8k_count_5d": len(matches),
        "sec_filing_archive_available": True,
        "sec_filing_examples": [
            {
                "usable_trade_date": row.get("usable_trade_date"),
                "form_type": row.get("form_type"),
                "eight_k_item_type": row.get("eight_k_item_type"),
                "severity": row.get("_severity"),
                "source_accession": row.get("source_accession"),
            }
            for row in matches[:5]
        ],
    }


def _earnings_features(ticker: str, signal_date: str) -> dict[str, Any]:
    date_key = _date_key(signal_date)
    path = REPO_ROOT / "data" / f"event_snapshot_{date_key}.json"
    if not path.exists():
        return {
            "days_since_earnings": None,
            "earnings_shock_pct": None,
            "earnings_archive_available": False,
            "earnings_examples": [],
        }
    start = _date(signal_date) - timedelta(days=20)
    end = _date(signal_date)
    examples = []
    for offset in range(20, -1, -1):
        key = _date_key(end - timedelta(days=offset))
        event_path = REPO_ROOT / "data" / f"event_snapshot_{key}.json"
        if not event_path.exists():
            continue
        payload = _load_json(event_path)
        for event in (payload.get("events_by_ticker") or {}).get(ticker, []) or []:
            if event.get("event_type") != "earnings":
                continue
            event_date = event.get("event_date") or key
            try:
                event_dt = datetime.strptime(str(event_date)[:8], "%Y%m%d")
            except ValueError:
                event_dt = _date(str(event_date))
            if not (start <= event_dt <= end):
                continue
            attrs = event.get("attributes") or {}
            shock = attrs.get("avg_historical_surprise_pct") or attrs.get("sue_proxy")
            examples.append(
                {
                    "event_date": _iso(event_dt),
                    "days_since": (end - event_dt).days,
                    "event_subtype": event.get("event_subtype"),
                    "surprise_direction": event.get("surprise_direction"),
                    "earnings_shock_pct": shock,
                    "headline_item_count": attrs.get("headline_item_count"),
                }
            )
    if not examples:
        return {
            "days_since_earnings": None,
            "earnings_shock_pct": None,
            "earnings_archive_available": True,
            "earnings_examples": [],
        }
    latest = sorted(examples, key=lambda item: item["event_date"])[-1]
    return {
        "days_since_earnings": latest["days_since"],
        "earnings_shock_pct": _round(latest["earnings_shock_pct"]),
        "earnings_archive_available": True,
        "earnings_examples": examples[-5:],
    }


def _forward_oracle_row(
    event: dict[str, Any],
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    horizon_days: int = 20,
) -> dict[str, Any] | None:
    ticker = str(event.get("ticker") or "").upper()
    signal_date = str(event.get("date") or "")[:10]
    ticker_rows = rows_by_ticker.get(ticker) or []
    forward = _next_rows_after(ticker_rows, signal_date, horizon_days)
    if not forward:
        return None
    details = event.get("details") or {}
    entry_date = details.get("fill_date") or _row_date(forward[0])
    entry_open = _safe_float(details.get("fill_price") or _row_open(forward[0]))
    if entry_open is None or entry_open <= 0:
        return None
    best_row = max(forward, key=lambda row: _row_high(row) or 0.0)
    best_high = _row_high(best_row)
    if best_high is None:
        return None
    max_forward_return = (best_high * (1 - ROUND_TRIP_COST_PCT) / entry_open) - 1
    return {
        "entry_date": entry_date,
        "entry_open": entry_open,
        "oracle_exit_date": _row_date(best_row),
        "oracle_exit_price": best_high * (1 - ROUND_TRIP_COST_PCT),
        "max_forward_return_pct": max_forward_return,
    }


def _collect_cancel_events() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    events = []
    coverage = {}
    for window, cfg in WINDOWS.items():
        snapshot = _load_json(cfg["snapshot"])
        rows_by_ticker = _ohlcv_rows_by_ticker(snapshot)
        backtest = _load_json(cfg["backtest"])
        sample_skips = (backtest.get("entry_execution_attribution") or {}).get("sample_skips") or []
        cancel_events = [row for row in sample_skips if row.get("decision") in TARGET_DECISIONS]
        evaluated = []
        for event in cancel_events:
            oracle = _forward_oracle_row(event, rows_by_ticker)
            if oracle is None:
                continue
            evaluated.append({**event, **oracle, "window": window})
        coverage[window] = {
            "source_sample_skips": len(sample_skips),
            "cancel_like_sample_skips": len(cancel_events),
            "evaluated_cancel_like_events": len(evaluated),
            "reported_skipped_count": (backtest.get("entry_execution_attribution") or {}).get("skipped_count"),
            "source_backtest": _repo_rel(cfg["backtest"]),
            "source_snapshot": _repo_rel(cfg["snapshot"]),
        }
        events.extend(evaluated)
    return events, coverage


def _feature_row(
    event: dict[str, Any],
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    idx_by_ticker: dict[str, dict[str, int]],
) -> dict[str, Any]:
    ticker = str(event.get("ticker") or "").upper()
    signal_date = str(event.get("date") or "")[:10]
    details = event.get("details") or {}
    fill_open = _safe_float(details.get("fill_price") or event.get("entry_open"))
    signal_entry = _safe_float(details.get("signal_entry"))
    gap_pct = _pct_change(signal_entry, fill_open)
    context = _signal_context(rows_by_ticker, ticker, signal_date)
    sector_rs, sector_rs_source = _sector_5d_rs(rows_by_ticker, idx_by_ticker, ticker, signal_date)
    row: dict[str, Any] = {
        "window": event.get("window"),
        "signal_date": signal_date,
        "entry_date": event.get("entry_date"),
        "ticker": ticker,
        "sector": SECTOR_MAP.get(ticker, "Unknown"),
        "strategy": event.get("strategy"),
        "decision": event.get("decision"),
        "candidate_rank": event.get("candidate_rank"),
        "available_slots_at_entry_loop": event.get("available_slots_at_entry_loop"),
        "fill_open": _round(fill_open, 4),
        "signal_entry": _round(signal_entry, 4),
        "gap_pct": _round(gap_pct),
        "gap_abs_pct": _round(abs(gap_pct) if gap_pct is not None else None),
        "gap_bucket": _gap_bucket(gap_pct),
        "max_forward_return_pct": _round(event.get(FORWARD_RETURN_FIELD)),
        "forward_positive": bool((event.get(FORWARD_RETURN_FIELD) or 0) > 0),
        "forward_strong_ge_10pct": bool((event.get(FORWARD_RETURN_FIELD) or 0) >= STRONG_RETURN_THRESHOLD),
        "volume_vs_20d_avg": _round(context.get("volume_vs_20d_avg")),
        "atr14_t_over_t20": _round(_atr14_t_over_t20(rows_by_ticker, ticker, signal_date)),
        "bbwidth20": _round(_bbwidth20(rows_by_ticker, ticker, signal_date)),
        "sector_5d_rs": _round(sector_rs),
        "sector_5d_rs_source": sector_rs_source,
        "oracle_exit_date": event.get("oracle_exit_date"),
        "oracle_exit_price": _round(event.get("oracle_exit_price"), 4),
        "details": details,
    }
    for payload in (
        _news_features(ticker, signal_date),
        _form4_features(ticker, signal_date),
        _sec_filing_features(ticker, signal_date),
        _earnings_features(ticker, signal_date),
    ):
        row.update(payload)
    feature_fields = [
        "gap_pct",
        "volume_vs_20d_avg",
        "news_t1t2_count_3d",
        "news_neg_count_3d",
        "form4_buy_5d",
        "recent_8k_count_5d",
        "days_since_earnings",
        "atr14_t_over_t20",
        "bbwidth20",
        "sector_5d_rs",
    ]
    row["feature_coverage_count"] = sum(row.get(field) is not None for field in feature_fields)
    return row


def _build_feature_rows(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    by_window = {name: [] for name in WINDOWS}
    for event in events:
        by_window[event["window"]].append(event)
    for window, window_events in by_window.items():
        snapshot = _load_json(WINDOWS[window]["snapshot"])
        rows_by_ticker = _ohlcv_rows_by_ticker(snapshot)
        idx_by_ticker = _row_index_by_date(rows_by_ticker)
        for event in window_events:
            rows.append(_feature_row(event, rows_by_ticker, idx_by_ticker))
    return sorted(rows, key=lambda row: (row["window"], row["signal_date"], row["ticker"], row["decision"]))


def _feature_coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    fields = [
        "gap_pct",
        "gap_bucket",
        "volume_vs_20d_avg",
        "news_t1t2_count_3d",
        "news_neg_count_3d",
        "form4_buy_5d",
        "form4_net_buy_usd_5d",
        "recent_8k_count_5d",
        "recent_8k_severity_5d",
        "days_since_earnings",
        "earnings_shock_pct",
        "atr14_t_over_t20",
        "bbwidth20",
        "sector_5d_rs",
    ]
    out = {}
    for field in fields:
        count = sum(1 for row in rows if row.get(field) is not None)
        out[field] = {"covered": count, "coverage": round(count / len(rows), 4) if rows else None}
    out["news_archive_any_3d"] = {
        "covered": sum(1 for row in rows if (row.get("news_archive_covered_days_3d") or 0) > 0),
        "coverage": round(
            sum(1 for row in rows if (row.get("news_archive_covered_days_3d") or 0) > 0) / len(rows),
            4,
        )
        if rows else None,
    }
    out["form4_archive_available"] = {
        "covered": sum(1 for row in rows if row.get("form4_archive_available")),
        "coverage": round(sum(1 for row in rows if row.get("form4_archive_available")) / len(rows), 4)
        if rows else None,
    }
    out["sec_filing_archive_available"] = {
        "covered": sum(1 for row in rows if row.get("sec_filing_archive_available")),
        "coverage": round(sum(1 for row in rows if row.get("sec_filing_archive_available")) / len(rows), 4)
        if rows else None,
    }
    return out


def _summarize_values(rows: list[dict[str, Any]]) -> dict[str, Any]:
    returns = [row[FORWARD_RETURN_FIELD] for row in rows if row.get(FORWARD_RETURN_FIELD) is not None]
    return {
        "count": len(rows),
        "avg_forward_return": _round(_mean(returns)),
        "median_forward_return": _round(_median(returns)),
        "positive_rate": _round(sum(1 for value in returns if value > 0) / len(returns)) if returns else None,
        "strong_ge_10pct_rate": _round(sum(1 for value in returns if value >= STRONG_RETURN_THRESHOLD) / len(returns)) if returns else None,
        "tickers": sorted({str(row.get("ticker")) for row in rows if row.get("ticker")}),
        "windows": dict(sorted(Counter(str(row.get("window")) for row in rows).items())),
    }


def _numeric_splits(rows: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    values = [row.get(field) for row in rows if isinstance(row.get(field), (int, float))]
    med = _median(values)
    if med is None:
        return []
    groups = [
        (f"{field}>=median", [row for row in rows if isinstance(row.get(field), (int, float)) and row[field] >= med]),
        (f"{field}<median", [row for row in rows if isinstance(row.get(field), (int, float)) and row[field] < med]),
    ]
    return [
        {
            "field": field,
            "predicate": name,
            "threshold": _round(med),
            **_summarize_values(group),
        }
        for name, group in groups
        if group
    ]


def _categorical_splits(rows: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    values = sorted({row.get(field) for row in rows if row.get(field) not in (None, "")})
    out = []
    for value in values:
        group = [row for row in rows if row.get(field) == value]
        if group:
            out.append(
                {
                    "field": field,
                    "predicate": f"{field}=={value}",
                    "value": value,
                    **_summarize_values(group),
                }
            )
    return out


def _separation_score(candidate: dict[str, Any], baseline: dict[str, Any]) -> float | None:
    avg = candidate.get("avg_forward_return")
    base = baseline.get("avg_forward_return")
    if avg is None or base is None:
        return None
    support = candidate.get("count") or 0
    if support <= 0:
        return None
    support_weight = min(1.0, support / 3.0)
    window_weight = min(1.0, len(candidate.get("windows") or {}) / 2.0)
    return (avg - base) * support_weight * window_weight


def _rank_discriminators(rows: list[dict[str, Any]]) -> dict[str, Any]:
    baseline = _summarize_values(rows)
    numeric_fields = [
        "gap_abs_pct",
        "volume_vs_20d_avg",
        "news_t1_count_3d",
        "news_t2_count_3d",
        "news_t1t2_count_3d",
        "news_pos_count_3d",
        "news_neg_count_3d",
        "form4_buy_5d",
        "form4_net_buy_usd_5d",
        "recent_8k_severity_5d",
        "recent_8k_count_5d",
        "days_since_earnings",
        "earnings_shock_pct",
        "atr14_t_over_t20",
        "bbwidth20",
        "sector_5d_rs",
    ]
    categorical_fields = ["gap_bucket"]
    candidates = []
    for field in numeric_fields:
        candidates.extend(_numeric_splits(rows, field))
    for field in categorical_fields:
        candidates.extend(_categorical_splits(rows, field))
    enriched = []
    for item in candidates:
        score = _separation_score(item, baseline)
        if score is None:
            continue
        lift = (
            item["avg_forward_return"] / baseline["avg_forward_return"]
            if baseline.get("avg_forward_return") not in (None, 0)
            else None
        )
        enriched.append(
            {
                **item,
                "score": _round(score),
                "avg_return_lift_vs_all": _round(lift),
                "baseline_avg_forward_return": baseline.get("avg_forward_return"),
            }
        )
    enriched.sort(
        key=lambda item: (
            item.get("score") if item.get("score") is not None else -999,
            item.get("count") or 0,
        ),
        reverse=True,
    )
    return {
        "baseline": baseline,
        "single_variable_ranking": enriched,
        "top_joint_pairs": _joint_pairs(rows, enriched[:8], baseline),
        "ranking_notes": [
            "Scores are descriptive only and use same-sample oracle forward returns.",
            "A Phase B pre-registration should require the selected discriminator to separate in at least two windows.",
            "Joint pairs are only candidates if their lift is at least 1.5x the better marginal lift and support spans at least two windows.",
            "Raw sector, strategy, and decision labels are intentionally not ranked because prior sector/strategy exception families were rejected.",
        ],
    }


def _predicate(row: dict[str, Any], candidate: dict[str, Any]) -> bool:
    field = candidate.get("field")
    if "value" in candidate:
        return row.get(field) == candidate.get("value")
    threshold = candidate.get("threshold")
    predicate = str(candidate.get("predicate") or "")
    value = row.get(field)
    if not isinstance(value, (int, float)) or threshold is None:
        return False
    if ">=" in predicate:
        return value >= threshold
    if "<" in predicate:
        return value < threshold
    return False


def _joint_pairs(
    rows: list[dict[str, Any]],
    top: list[dict[str, Any]],
    baseline: dict[str, Any],
) -> list[dict[str, Any]]:
    out = []
    for idx, left in enumerate(top):
        for right in top[idx + 1:]:
            if left.get("field") == right.get("field"):
                continue
            group = [row for row in rows if _predicate(row, left) and _predicate(row, right)]
            if not group:
                continue
            summary = _summarize_values(group)
            lift = (
                summary["avg_forward_return"] / baseline["avg_forward_return"]
                if baseline.get("avg_forward_return") not in (None, 0)
                else None
            )
            better_marginal = max(
                left.get("avg_return_lift_vs_all") or 0,
                right.get("avg_return_lift_vs_all") or 0,
            )
            out.append(
                {
                    "left": left.get("predicate"),
                    "right": right.get("predicate"),
                    **summary,
                    "avg_return_lift_vs_all": _round(lift),
                    "better_marginal_lift": _round(better_marginal),
                    "joint_lift_vs_better_marginal": _round(lift / better_marginal)
                    if lift is not None and better_marginal else None,
                    "meets_1_5x_marginal_lift_rule": bool(
                        lift is not None
                        and better_marginal
                        and lift >= 1.5 * better_marginal
                        and len(summary.get("windows") or {}) >= 2
                    ),
                }
            )
    out.sort(
        key=lambda item: (
            bool(item.get("meets_1_5x_marginal_lift_rule")),
            item.get("avg_return_lift_vs_all") or -999,
            item.get("count") or 0,
        ),
        reverse=True,
    )
    return out


def _window_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out = {}
    for window in WINDOWS:
        group = [row for row in rows if row.get("window") == window]
        out[window] = {
            **_summarize_values(group),
            "decision_counts": dict(sorted(Counter(str(row.get("decision")) for row in group).items())),
        }
    return out


def _catalog(rows: list[dict[str, Any]], source_coverage: dict[str, Any], ranking: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXP_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "loss_attribution",
        "is_tradable": False,
        "lookahead_warning": (
            "Forward returns use future 20-day highs for skipped entry samples. "
            "Use this only to pre-register Phase B parameters."
        ),
        "source_coverage": source_coverage,
        "feature_coverage": _feature_coverage(rows),
        "source_event_count_note": (
            "Current replayable standard three-window sample contains 20 evaluated "
            "gap/adverse cancel events. The analyst ticket cited 21; no-entry-restriction "
            "oracle artifacts do not currently include the missing skip-detail row."
        ),
        "window_summary": _window_summary(rows),
        "ranking_summary": {
            "baseline": ranking.get("baseline"),
            "top_single": ranking.get("single_variable_ranking", [])[:5],
            "top_joint_pairs": ranking.get("top_joint_pairs", [])[:5],
        },
        "events": rows,
    }


def main() -> None:
    events, source_coverage = _collect_cancel_events()
    rows = _build_feature_rows(events)
    ranking = _rank_discriminators(rows)
    catalog = _catalog(rows, source_coverage, ranking)
    log_payload = {
        "experiment_id": EXP_ID,
        "timestamp": catalog["generated_at"],
        "lane": "loss_attribution",
        "status": "completed_observe_only",
        "decision": "phase_a_completed_no_strategy_change",
        "change_type": "loss_attribution_feature_audit",
        "hypothesis": (
            "Some next-open gap cancels are confirmation gaps rather than bad fills; "
            "point-in-time orthogonal features may identify which skipped entries "
            "deserve a pre-registered Phase B bypass replay."
        ),
        "alpha_hypothesis": {
            "category": "entry",
            "entry_exit_ranking_or_allocation": "entry execution discriminator",
            "why_not_direct_phase_b": (
                "The gap-threshold and policy-state families are already rejected; "
                "this run first ranks orthogonal per-event features and records coverage."
            ),
        },
        "historical_experiment_check": {
            "exp-20260428-021": "Global upside gap threshold sweep rejected; this does not retune CANCEL_GAP_PCT.",
            "exp-20260428-022": "Sector/strategy gap exceptions rejected; this does not use sector or strategy as a bypass rule.",
            "exp-20260428-023": "Adverse-gap context exceptions rejected; this audits orthogonal event/features before any replay.",
            "exp-20260427-019_to_025": "Scarce-slot/regime/breadth/rank/TQS conditionals rejected; this is per-event feature attribution.",
            "exp-20260504-055": "Frozen event-bundle coverage was 0%; this uses broader feature coverage and records missingness.",
        },
        "single_causal_variable": "none_research_artifact_only",
        "parameters": {
            "target_decisions": sorted(TARGET_DECISIONS),
            "horizon_days": 20,
            "strong_return_threshold": STRONG_RETURN_THRESHOLD,
            "ranking_method": "median numeric splits plus categorical buckets; same-sample descriptive lift",
            "strategy_change_attempted": False,
        },
        "date_range": {
            name: {
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": _repo_rel(cfg["snapshot"]),
            }
            for name, cfg in WINDOWS.items()
        },
        "market_regime_summary": {name: cfg["state_note"] for name, cfg in WINDOWS.items()},
        "source_coverage": source_coverage,
        "feature_coverage": catalog["feature_coverage"],
        "event_count": len(rows),
        "source_event_count_note": catalog["source_event_count_note"],
        "window_summary": catalog["window_summary"],
        "ranking_top_single": ranking["single_variable_ranking"][:8],
        "ranking_top_joint_pairs": ranking["top_joint_pairs"][:8],
        "gate4": {
            "status": "not_applicable_research_only",
            "reason": "Phase A creates research artifacts and does not alter the strategy path.",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "production_signal_path_changed": False,
            "alters_orders": False,
            "alters_sizing": False,
            "alters_candidate_ranking": False,
            "replay_only": False,
            "observe_only": True,
            "parity_test_added": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "llm_change_scope": "none",
        },
        "next_action": (
            "Use the top discriminator only as Phase B pre-registration input if it "
            "has enough PIT-safe coverage and separates in at least two windows."
        ),
        "related_files": [
            _repo_rel(OUT_CSV),
            _repo_rel(OUT_RANKING),
            _repo_rel(OUT_CATALOG),
            _repo_rel(LOG_JSON),
        ],
    }

    _write_csv(OUT_CSV, rows)
    _write_json(OUT_RANKING, ranking)
    _write_json(OUT_CATALOG, catalog)
    _write_json(LOG_JSON, log_payload)

    print(
        json.dumps(
            {
                "experiment_id": EXP_ID,
                "event_count": len(rows),
                "feature_coverage": catalog["feature_coverage"],
                "top_single": ranking["single_variable_ranking"][:5],
                "top_joint_pairs": ranking["top_joint_pairs"][:3],
                "outputs": log_payload["related_files"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
