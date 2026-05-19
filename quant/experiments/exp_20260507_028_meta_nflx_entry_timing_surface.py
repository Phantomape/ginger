"""exp-20260507-028: META/NFLX entry timing surface audit.

Observed-only alpha research. The prior core-platform experiments found that
mechanical pullback entries, post-target runners, and cap-aware sizing do not
justify production changes. This audit asks a different question: for META and
NFLX, plus a small platform peer cohort, which ex-ante entry states have better
next-open forward return, MFE, and MAE?

This is not a tradable backtest. Daily rows overlap heavily, and no orders,
ranking, sizing, exits, universe, LLM/news, or production path are changed.
"""

from __future__ import annotations

import json
import math
import statistics
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260507-028"
STEM = "meta_nflx_entry_timing_surface"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

SEED_TICKERS = ("META", "NFLX")
PEER_TICKERS = ("GOOG", "AMZN", "SPOT", "DIS", "APP")
PLATFORM_TICKERS = SEED_TICKERS + PEER_TICKERS
BENCHMARKS = ("SPY", "QQQ")
FORWARD_HORIZONS = (5, 10, 20, 40, 60)
PRIMARY_HORIZONS = (20, 40)

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
                "state_note": "rotation-heavy bull where strategy profits but can lag indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)


_EARNINGS_CACHE: dict[str, dict[str, Any]] = {}


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(out) or math.isinf(out):
        return None
    return round(out, digits)


def _float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8-sig") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _load_ohlcv(snapshot_path: Path) -> dict[str, list[dict[str, Any]]]:
    payload = _load_json(snapshot_path)
    ohlcv = payload.get("ohlcv")
    if not isinstance(ohlcv, dict):
        raise RuntimeError(f"Unexpected OHLCV snapshot shape: {snapshot_path}")
    out: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in ohlcv.items():
        if not isinstance(rows, list):
            continue
        clean = [row for row in rows if isinstance(row, dict) and row.get("Date")]
        out[str(ticker).upper()] = sorted(clean, key=lambda row: str(row["Date"]))
    return out


def _date_value(row: dict[str, Any]) -> str:
    return str(row.get("Date"))[:10]


def _date_index(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {_date_value(row): idx for idx, row in enumerate(rows)}


def _idx_for_date(rows: list[dict[str, Any]], date_str: str | None) -> int | None:
    if not date_str:
        return None
    return _date_index(rows).get(str(date_str)[:10])


def _close(row: dict[str, Any]) -> float | None:
    return _float(row.get("Close"))


def _open(row: dict[str, Any]) -> float | None:
    return _float(row.get("Open"))


def _high(row: dict[str, Any]) -> float | None:
    return _float(row.get("High"))


def _low(row: dict[str, Any]) -> float | None:
    return _float(row.get("Low"))


def _volume(row: dict[str, Any]) -> float | None:
    return _float(row.get("Volume"))


def _earnings_payload(date_str: str) -> dict[str, Any]:
    key = str(date_str)[:10].replace("-", "")
    if key not in _EARNINGS_CACHE:
        path = REPO_ROOT / "data" / f"earnings_snapshot_{key}.json"
        if not path.exists():
            _EARNINGS_CACHE[key] = {}
        else:
            payload = _load_json(path)
            earnings = payload.get("earnings") if isinstance(payload, dict) else {}
            _EARNINGS_CACHE[key] = earnings if isinstance(earnings, dict) else {}
    return _EARNINGS_CACHE[key]


def _dte_for(ticker: str, date_str: str) -> int | None:
    row = _earnings_payload(date_str).get(ticker.upper())
    if not isinstance(row, dict):
        return None
    value = row.get("days_to_earnings")
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _sma(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx + 1 < lookback:
        return None
    values = [_close(row) for row in rows[idx - lookback + 1 : idx + 1]]
    clean = [value for value in values if value is not None]
    if len(clean) != lookback:
        return None
    return sum(clean) / lookback


def _avg_volume(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx + 1 < lookback:
        return None
    values = [_volume(row) for row in rows[idx - lookback + 1 : idx + 1]]
    clean = [value for value in values if value is not None]
    if len(clean) != lookback:
        return None
    return sum(clean) / lookback


def _return_lookback(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < lookback:
        return None
    start = _close(rows[idx - lookback])
    end = _close(rows[idx])
    if start is None or end is None or start <= 0:
        return None
    return end / start - 1.0


def _max_close(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < 1:
        return None
    start = max(0, idx - lookback + 1)
    values = [_close(row) for row in rows[start : idx + 1]]
    clean = [value for value in values if value is not None]
    return max(clean) if clean else None


def _max_high(rows: list[dict[str, Any]], idx: int, lookback: int, *, include_today: bool) -> float | None:
    end = idx + 1 if include_today else idx
    start = max(0, end - lookback)
    if start >= end:
        return None
    values = [_high(row) for row in rows[start:end]]
    clean = [value for value in values if value is not None]
    return max(clean) if clean else None


def _forward_packet(
    rows: list[dict[str, Any]],
    idx: int,
    window_end_idx: int,
    bench_rows: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    entry_idx = idx + 1
    if entry_idx >= len(rows) or entry_idx > window_end_idx:
        return {"entry_status": "no_next_open"}
    entry_open = _open(rows[entry_idx])
    if entry_open is None or entry_open <= 0:
        return {"entry_status": "missing_next_open"}

    out: dict[str, Any] = {
        "entry_status": "ok",
        "entry_date": _date_value(rows[entry_idx]),
        "entry_open": _round(entry_open, 4),
    }
    entry_date = _date_value(rows[entry_idx])
    for horizon in FORWARD_HORIZONS:
        end_idx = entry_idx + horizon
        if end_idx > window_end_idx or end_idx >= len(rows):
            out[f"return_{horizon}d"] = None
            out[f"mfe_{horizon}d"] = None
            out[f"mae_{horizon}d"] = None
            out[f"excess_spy_{horizon}d"] = None
            out[f"excess_qqq_{horizon}d"] = None
            continue
        end_close = _close(rows[end_idx])
        if end_close is None:
            out[f"return_{horizon}d"] = None
        else:
            out[f"return_{horizon}d"] = (end_close / entry_open) - 1.0

        highs = [_high(row) for row in rows[entry_idx : end_idx + 1]]
        lows = [_low(row) for row in rows[entry_idx : end_idx + 1]]
        highs_clean = [value for value in highs if value is not None]
        lows_clean = [value for value in lows if value is not None]
        out[f"mfe_{horizon}d"] = (
            max(highs_clean) / entry_open - 1.0 if highs_clean else None
        )
        out[f"mae_{horizon}d"] = (
            min(lows_clean) / entry_open - 1.0 if lows_clean else None
        )

        for bench in BENCHMARKS:
            b_rows = bench_rows.get(bench) or []
            b_entry_idx = _idx_for_date(b_rows, entry_date)
            bench_value = None
            if b_entry_idx is not None and b_entry_idx + horizon < len(b_rows):
                b_entry = _open(b_rows[b_entry_idx])
                b_end = _close(b_rows[b_entry_idx + horizon])
                if b_entry is not None and b_entry > 0 and b_end is not None:
                    bench_value = b_end / b_entry - 1.0
            ticker_value = out.get(f"return_{horizon}d")
            out[f"excess_{bench.lower()}_{horizon}d"] = (
                ticker_value - bench_value
                if ticker_value is not None and bench_value is not None
                else None
            )
    return out


def _dte_bucket(dte: int | None, days_since_earnings: int | None) -> str:
    if days_since_earnings is not None:
        if 1 <= days_since_earnings <= 5:
            return "post_earnings_1_5"
        if 6 <= days_since_earnings <= 15:
            return "post_earnings_6_15"
    if dte is None:
        return "dte_unknown"
    if dte <= 7:
        return "pre_earnings_0_7"
    if dte <= 21:
        return "pre_earnings_8_21"
    if dte <= 45:
        return "pre_earnings_22_45"
    return "pre_earnings_46_plus"


def _days_since_earnings_series(
    ticker: str, rows: list[dict[str, Any]]
) -> tuple[dict[int, int | None], dict[int, int | None]]:
    dte_by_idx: dict[int, int | None] = {}
    since_by_idx: dict[int, int | None] = {}
    prev_dte: int | None = None
    last_earnings_idx: int | None = None
    for idx, row in enumerate(rows):
        dte = _dte_for(ticker, _date_value(row))
        dte_by_idx[idx] = dte
        if dte == 0:
            last_earnings_idx = idx
        elif prev_dte is not None and prev_dte <= 1 and dte is not None and dte >= 20:
            last_earnings_idx = idx
        since_by_idx[idx] = idx - last_earnings_idx if last_earnings_idx is not None else None
        prev_dte = dte
    return dte_by_idx, since_by_idx


def _tags_for(row: dict[str, Any]) -> list[str]:
    tags = ["all_days", row["dte_bucket"]]
    if row.get("above_sma20"):
        tags.append("above_sma20")
    if row.get("above_sma50"):
        tags.append("above_sma50")
    if row.get("sma20_gt_sma50"):
        tags.append("sma20_gt_sma50")
    if row.get("rs20_vs_spy") is not None and row["rs20_vs_spy"] > 0:
        tags.append("rs20_leader")
    if row.get("rs60_vs_spy") is not None and row["rs60_vs_spy"] > 0:
        tags.append("rs60_leader")
    if row.get("gap_pct") is not None and row["gap_pct"] >= 0.03:
        tags.append("gap_up_3pct")
    if row.get("gap_pct") is not None and row["gap_pct"] <= -0.03:
        tags.append("gap_down_3pct")
    if row.get("volume_ratio20") is not None and row["volume_ratio20"] >= 1.5:
        tags.append("volume_surge_1_5x")
    if row.get("breakout_20d_high"):
        tags.append("breakout_20d_high")
    if row.get("near_252d_high"):
        tags.append("near_252d_high")
    if row.get("sma20_reclaim"):
        tags.append("sma20_reclaim")
    if row.get("sma50_reclaim"):
        tags.append("sma50_reclaim")
    pullback60 = row.get("pullback_60d_high_pct")
    if pullback60 is not None:
        if -0.08 <= pullback60 <= -0.03 and row.get("above_sma50"):
            tags.append("orderly_pullback_3_8_above_sma50")
        if -0.15 <= pullback60 < -0.08 and row.get("above_sma200"):
            tags.append("deep_pullback_8_15_above_sma200")
    if (
        row.get("near_252d_high")
        and row.get("distance_sma20_pct") is not None
        and row["distance_sma20_pct"] >= 0.05
    ):
        tags.append("near_high_extended_5pct_above_sma20")
    if (
        row.get("days_since_earnings") is not None
        and 1 <= row["days_since_earnings"] <= 10
        and row.get("above_sma20")
        and row.get("rs20_vs_spy") is not None
        and row["rs20_vs_spy"] > 0
    ):
        tags.append("post_earnings_drift_1_10")
    if (
        row.get("dte") is not None
        and 0 <= row["dte"] <= 14
        and row.get("rs20_vs_spy") is not None
        and row["rs20_vs_spy"] > 0
    ):
        tags.append("pre_earnings_runup_0_14")
    if row.get("gap_pct") is not None and row["gap_pct"] >= 0.03:
        if row.get("close_vs_open_pct") is not None and row["close_vs_open_pct"] > 0:
            tags.append("gap_up_follow_through")
        elif row.get("close_vs_open_pct") is not None and row["close_vs_open_pct"] < 0:
            tags.append("gap_up_fade")
    if row.get("above_sma50") is False:
        tags.append("below_sma50")
    return sorted(set(tags))


def _surface_row(
    ticker: str,
    rows: list[dict[str, Any]],
    idx: int,
    window_name: str,
    window_end_idx: int,
    bench_rows: dict[str, list[dict[str, Any]]],
    dte_by_idx: dict[int, int | None],
    since_by_idx: dict[int, int | None],
) -> dict[str, Any] | None:
    row = rows[idx]
    date_str = _date_value(row)
    close = _close(row)
    opn = _open(row)
    if close is None or opn is None:
        return None

    sma20 = _sma(rows, idx, 20)
    sma50 = _sma(rows, idx, 50)
    sma200 = _sma(rows, idx, 200)
    prev_close = _close(rows[idx - 1]) if idx > 0 else None
    prev_sma20 = _sma(rows, idx - 1, 20) if idx > 0 else None
    prev_sma50 = _sma(rows, idx - 1, 50) if idx > 0 else None
    high20_prev = _max_high(rows, idx, 20, include_today=False)
    high60 = _max_close(rows, idx, 60)
    high252 = _max_close(rows, idx, 252)
    avg_vol20 = _avg_volume(rows, idx, 20)
    vol = _volume(row)

    spy_rows = bench_rows.get("SPY") or []
    spy_idx = _idx_for_date(spy_rows, date_str)
    rs20 = None
    rs60 = None
    own20 = _return_lookback(rows, idx, 20)
    own60 = _return_lookback(rows, idx, 60)
    if spy_idx is not None:
        spy20 = _return_lookback(spy_rows, spy_idx, 20)
        spy60 = _return_lookback(spy_rows, spy_idx, 60)
        if own20 is not None and spy20 is not None:
            rs20 = own20 - spy20
        if own60 is not None and spy60 is not None:
            rs60 = own60 - spy60

    dte = dte_by_idx.get(idx)
    since = since_by_idx.get(idx)
    out: dict[str, Any] = {
        "window": window_name,
        "ticker": ticker,
        "cohort": "seed" if ticker in SEED_TICKERS else "peer",
        "date": date_str,
        "close": close,
        "dte": dte,
        "days_since_earnings": since,
        "dte_bucket": _dte_bucket(dte, since),
        "above_sma20": close > sma20 if sma20 is not None else None,
        "above_sma50": close > sma50 if sma50 is not None else None,
        "above_sma200": close > sma200 if sma200 is not None else None,
        "sma20_gt_sma50": sma20 > sma50 if sma20 is not None and sma50 is not None else None,
        "distance_sma20_pct": (close / sma20 - 1.0) if sma20 else None,
        "distance_sma50_pct": (close / sma50 - 1.0) if sma50 else None,
        "ret_5d": _return_lookback(rows, idx, 5),
        "ret_20d": own20,
        "ret_60d": own60,
        "rs20_vs_spy": rs20,
        "rs60_vs_spy": rs60,
        "gap_pct": (opn / prev_close - 1.0) if prev_close else None,
        "close_vs_open_pct": close / opn - 1.0 if opn else None,
        "volume_ratio20": vol / avg_vol20 if vol is not None and avg_vol20 else None,
        "pullback_60d_high_pct": close / high60 - 1.0 if high60 else None,
        "pullback_252d_high_pct": close / high252 - 1.0 if high252 else None,
        "breakout_20d_high": close >= high20_prev if high20_prev is not None else None,
        "near_252d_high": close >= high252 * 0.97 if high252 else None,
        "sma20_reclaim": (
            prev_close is not None
            and prev_sma20 is not None
            and prev_close < prev_sma20
            and sma20 is not None
            and close > sma20
        ),
        "sma50_reclaim": (
            prev_close is not None
            and prev_sma50 is not None
            and prev_close < prev_sma50
            and sma50 is not None
            and close > sma50
        ),
    }
    out.update(_forward_packet(rows, idx, window_end_idx, bench_rows))
    if out.get("entry_status") != "ok":
        return None
    out["tags"] = _tags_for(out)
    return out


def _stats(values: list[float | None], digits: int = 6) -> dict[str, Any]:
    clean = [float(value) for value in values if value is not None and math.isfinite(value)]
    if not clean:
        return {
            "count": 0,
            "avg": None,
            "median": None,
            "p25": None,
            "p75": None,
            "win_rate": None,
            "best": None,
            "worst": None,
        }
    ordered = sorted(clean)

    def pctile(pct: float) -> float:
        if len(ordered) == 1:
            return ordered[0]
        raw = (len(ordered) - 1) * pct
        lo = math.floor(raw)
        hi = math.ceil(raw)
        if lo == hi:
            return ordered[lo]
        return ordered[lo] + (ordered[hi] - ordered[lo]) * (raw - lo)

    return {
        "count": len(clean),
        "avg": _round(sum(clean) / len(clean), digits),
        "median": _round(statistics.median(clean), digits),
        "p25": _round(pctile(0.25), digits),
        "p75": _round(pctile(0.75), digits),
        "win_rate": _round(sum(1 for value in clean if value > 0) / len(clean), 4),
        "best": _round(max(clean), digits),
        "worst": _round(min(clean), digits),
    }


def _summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "count": len(rows),
        "forward": {
            f"{horizon}d": {
                "return": _stats([_float(row.get(f"return_{horizon}d")) for row in rows]),
                "excess_spy": _stats(
                    [_float(row.get(f"excess_spy_{horizon}d")) for row in rows]
                ),
                "excess_qqq": _stats(
                    [_float(row.get(f"excess_qqq_{horizon}d")) for row in rows]
                ),
                "mfe": _stats([_float(row.get(f"mfe_{horizon}d")) for row in rows]),
                "mae": _stats([_float(row.get(f"mae_{horizon}d")) for row in rows]),
            }
            for horizon in FORWARD_HORIZONS
        },
    }


def _analyze_window(name: str, spec: dict[str, Any]) -> dict[str, Any]:
    ohlcv = _load_ohlcv(REPO_ROOT / spec["snapshot"])
    bench_rows = {bench: ohlcv.get(bench) or [] for bench in BENCHMARKS}
    rows_out: list[dict[str, Any]] = []

    for ticker in PLATFORM_TICKERS:
        rows = ohlcv.get(ticker)
        if not rows:
            continue
        date_to_idx = _date_index(rows)
        start_idx = date_to_idx.get(spec["start"])
        end_idx = date_to_idx.get(spec["end"])
        if start_idx is None or end_idx is None:
            continue
        dte_by_idx, since_by_idx = _days_since_earnings_series(ticker, rows)
        for idx in range(start_idx, end_idx + 1):
            row = _surface_row(
                ticker,
                rows,
                idx,
                name,
                end_idx,
                bench_rows,
                dte_by_idx,
                since_by_idx,
            )
            if row:
                rows_out.append(row)

    return {
        "window": name,
        "window_spec": spec,
        "row_count": len(rows_out),
        "ticker_counts": dict(sorted(Counter(row["ticker"] for row in rows_out).items())),
        "cohort_counts": dict(sorted(Counter(row["cohort"] for row in rows_out).items())),
        "rows": rows_out,
    }


def _bucket_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        cohorts = ("all_platform", row["cohort"], f"ticker:{row['ticker']}")
        for cohort in cohorts:
            for tag in row.get("tags") or []:
                groups[f"{cohort}|{tag}"].append(row)

    out = {}
    for key, items in sorted(groups.items()):
        cohort, tag = key.split("|", 1)
        out[key] = {
            "cohort": cohort,
            "tag": tag,
            **_summarize_rows(items),
        }
    return out


def _baseline_lookup(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out = {}
    for key, value in summary.items():
        if key.endswith("|all_days"):
            out[value["cohort"]] = value
    return out


def _tag_window_stats(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        for cohort in ("all_platform", row["cohort"], f"ticker:{row['ticker']}"):
            for tag in row.get("tags") or []:
                groups[f"{cohort}|{tag}|{row['window']}"].append(row)
    out = {}
    for key, items in groups.items():
        cohort, tag, window = key.split("|", 2)
        out[key] = {
            "cohort": cohort,
            "tag": tag,
            "window": window,
            "count": len(items),
            "avg_return_20d": _round(
                _stats([_float(row.get("return_20d")) for row in items])["avg"], 6
            ),
            "avg_return_40d": _round(
                _stats([_float(row.get("return_40d")) for row in items])["avg"], 6
            ),
            "avg_excess_spy_20d": _round(
                _stats([_float(row.get("excess_spy_20d")) for row in items])["avg"], 6
            ),
            "avg_excess_spy_40d": _round(
                _stats([_float(row.get("excess_spy_40d")) for row in items])["avg"], 6
            ),
        }
    return out


def _rank_surface(rows: list[dict[str, Any]], summary: dict[str, Any]) -> dict[str, Any]:
    baseline = _baseline_lookup(summary)
    window_stats = _tag_window_stats(rows)
    ranked: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for key, stats in summary.items():
        cohort = stats["cohort"]
        tag = stats["tag"]
        if tag == "all_days":
            continue
        count = stats["count"]
        min_count = 12 if cohort in ("seed", "ticker:META", "ticker:NFLX") else 25
        if count < min_count:
            continue
        ret20 = stats["forward"]["20d"]["return"]["avg"]
        ret40 = stats["forward"]["40d"]["return"]["avg"]
        ex20 = stats["forward"]["20d"]["excess_spy"]["avg"]
        ex40 = stats["forward"]["40d"]["excess_spy"]["avg"]
        mae20 = stats["forward"]["20d"]["mae"]["avg"]
        if ret20 is None and ret40 is None:
            continue

        base = baseline.get(cohort)
        lift20 = None
        lift40 = None
        if base:
            base20 = base["forward"]["20d"]["return"]["avg"]
            base40 = base["forward"]["40d"]["return"]["avg"]
            lift20 = ret20 - base20 if ret20 is not None and base20 is not None else None
            lift40 = ret40 - base40 if ret40 is not None and base40 is not None else None
        window_positive = 0
        window_count = 0
        for window_name in WINDOWS:
            w = window_stats.get(f"{cohort}|{tag}|{window_name}")
            if not w or w.get("count", 0) < max(3, min_count // 6):
                continue
            window_count += 1
            w20 = w.get("avg_excess_spy_20d")
            w40 = w.get("avg_excess_spy_40d")
            combined = sum(value for value in (w20, w40) if value is not None)
            if combined > 0:
                window_positive += 1
        score = sum(
            value
            for value in (
                ex20,
                ex40,
                0.5 * lift20 if lift20 is not None else None,
                0.5 * lift40 if lift40 is not None else None,
                0.25 * mae20 if mae20 is not None else None,
            )
            if value is not None
        )
        ranked[cohort].append(
            {
                "tag": tag,
                "count": count,
                "score": _round(score, 6),
                "avg_return_20d": ret20,
                "avg_return_40d": ret40,
                "avg_excess_spy_20d": ex20,
                "avg_excess_spy_40d": ex40,
                "avg_mae_20d": mae20,
                "lift_vs_all_days_20d": _round(lift20, 6),
                "lift_vs_all_days_40d": _round(lift40, 6),
                "windows_with_samples": window_count,
                "windows_positive_excess": window_positive,
            }
        )

    return {
        cohort: sorted(items, key=lambda item: item["score"], reverse=True)[:12]
        for cohort, items in sorted(ranked.items())
    }


def _compact_summary(summary: dict[str, Any], ranked: dict[str, Any]) -> dict[str, Any]:
    keep_keys = set()
    for cohort in ("all_platform", "seed", "peer", "ticker:META", "ticker:NFLX"):
        keep_keys.add(f"{cohort}|all_days")
        for item in ranked.get(cohort, [])[:8]:
            keep_keys.add(f"{cohort}|{item['tag']}")
    return {key: value for key, value in summary.items() if key in keep_keys}


def _aggregate(by_window: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for window in by_window.values():
        rows.extend(window["rows"])
    summary = _bucket_summary(rows)
    ranked = _rank_surface(rows, summary)
    compact = _compact_summary(summary, ranked)

    seed_best = ranked.get("seed", [])[:5]
    meta_best = ranked.get("ticker:META", [])[:5]
    nflx_best = ranked.get("ticker:NFLX", [])[:5]
    platform_best = ranked.get("all_platform", [])[:5]
    return {
        "row_count": len(rows),
        "ticker_counts": dict(sorted(Counter(row["ticker"] for row in rows).items())),
        "cohort_counts": dict(sorted(Counter(row["cohort"] for row in rows).items())),
        "tag_counts_top": dict(Counter(tag for row in rows for tag in row["tags"]).most_common(25)),
        "best_surface": {
            "all_platform": platform_best,
            "seed": seed_best,
            "ticker:META": meta_best,
            "ticker:NFLX": nflx_best,
        },
        "surface_summary_compact": compact,
        "decision_read": _decision_read(seed_best, meta_best, nflx_best),
    }


def _decision_read(
    seed_best: list[dict[str, Any]],
    meta_best: list[dict[str, Any]],
    nflx_best: list[dict[str, Any]],
) -> dict[str, Any]:
    stable_seed = [
        item
        for item in seed_best
        if item.get("windows_with_samples", 0) >= 2
        and item.get("windows_positive_excess", 0) >= 2
        and (item.get("lift_vs_all_days_20d") or 0.0) > 0
    ]
    stable_ticker = []
    for item in meta_best + nflx_best:
        if (
            item.get("windows_with_samples", 0) >= 2
            and item.get("windows_positive_excess", 0) >= 2
            and (item.get("lift_vs_all_days_20d") or 0.0) > 0
        ):
            stable_ticker.append(item)
    if stable_seed:
        return {
            "status": "promising_surface_not_promoted",
            "next_action": "pre_register_candidate_level_entry_timing_replay",
            "reason": (
                "At least one seed-level tag beat all-days on 20d return and "
                "showed positive excess in at least two windows."
            ),
            "top_seed_tags": stable_seed[:3],
        }
    if stable_ticker:
        return {
            "status": "ticker_specific_surface_only",
            "next_action": "do_not_promote_without_peer_or_forward_confirmation",
            "reason": (
                "Signal appears ticker-specific rather than seed-cohort stable; "
                "use as research lead only."
            ),
            "top_ticker_tags": stable_ticker[:3],
        }
    return {
        "status": "no_stable_timing_surface",
        "next_action": "do_not_start_mechanical_meta_nflx_entry_strategy",
        "reason": (
            "No seed-level timing tag cleared the minimum cross-window stability "
            "read. Mechanical timing should wait for event/news or forward evidence."
        ),
    }


def _log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["decision"],
        "decision": payload["decision"],
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis_category": "entry_timing_surface",
        "change_type": "observed_only_surface_audit",
        "mechanism_family": "meta_nflx_platform_entry_timing",
        "single_causal_variable": "observed_entry_state_surface",
        "date_range": {
            name: f"{spec['start']} -> {spec['end']}" for name, spec in WINDOWS.items()
        },
        "market_regime_summary": {
            name: spec["state_note"] for name, spec in WINDOWS.items()
        },
        "historical_experiment_check": payload["history_check"],
        "parameters": payload["parameters"],
        "observed_metrics": {
            "row_count": payload["aggregate"]["row_count"],
            "ticker_counts": payload["aggregate"]["ticker_counts"],
            "best_surface": payload["aggregate"]["best_surface"],
            "decision_read": payload["aggregate"]["decision_read"],
        },
        "gate4": {
            "passed": None,
            "basis": "Observed-only overlapping daily entry surface; no after-metrics or production change.",
        },
        "production_impact": payload["production_impact"],
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": (
                "LLM/news semantics are deliberately not changed; this audit can "
                "nominate where event/news semantics may be needed next."
            ),
        },
        "next_action": payload["aggregate"]["decision_read"]["next_action"],
        "next_retry_requires": payload["next_retry_requires"],
        "related_files": payload["related_files"],
    }


def _ticket(payload: dict[str, Any]) -> dict[str, Any]:
    read = payload["aggregate"]["decision_read"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "title": "META/NFLX entry timing surface audit",
        "decision": payload["decision"],
        "surface_status": read["status"],
        "next_action": read["next_action"],
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    agg = payload["aggregate"]
    read = agg["decision_read"]
    lines = [
        f"# {EXPERIMENT_ID} META/NFLX Entry Timing Surface",
        "",
        f"Decision: `{payload['decision']}`",
        f"Surface status: `{read['status']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Scope",
        "",
        f"- Seeds: {', '.join(SEED_TICKERS)}",
        f"- Peers: {', '.join(PEER_TICKERS)}",
        "- Decision price: current close; hypothetical entry: next open.",
        "- This is observed-only and uses overlapping daily rows.",
        "",
        "## Best Seed Timing Tags",
        "",
        "| Tag | Count | Score | 20d ret | 40d ret | 20d excess SPY | 40d excess SPY | Windows + |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in agg["best_surface"].get("seed", [])[:8]:
        lines.append(
            "| {tag} | {count} | {score} | {r20} | {r40} | {e20} | {e40} | {wp}/{ws} |".format(
                tag=item["tag"],
                count=item["count"],
                score=item["score"],
                r20=item["avg_return_20d"],
                r40=item["avg_return_40d"],
                e20=item["avg_excess_spy_20d"],
                e40=item["avg_excess_spy_40d"],
                wp=item["windows_positive_excess"],
                ws=item["windows_with_samples"],
            )
        )
    lines.extend(
        [
            "",
            "## META And NFLX Reads",
            "",
            "### META",
            "",
            "| Tag | Count | Score | 20d ret | 40d ret | 20d excess SPY | Windows + |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for item in agg["best_surface"].get("ticker:META", [])[:6]:
        lines.append(
            "| {tag} | {count} | {score} | {r20} | {r40} | {e20} | {wp}/{ws} |".format(
                tag=item["tag"],
                count=item["count"],
                score=item["score"],
                r20=item["avg_return_20d"],
                r40=item["avg_return_40d"],
                e20=item["avg_excess_spy_20d"],
                wp=item["windows_positive_excess"],
                ws=item["windows_with_samples"],
            )
        )
    lines.extend(["", "### NFLX", "", "| Tag | Count | Score | 20d ret | 40d ret | 20d excess SPY | Windows + |", "|---|---:|---:|---:|---:|---:|---:|"])
    for item in agg["best_surface"].get("ticker:NFLX", [])[:6]:
        lines.append(
            "| {tag} | {count} | {score} | {r20} | {r40} | {e20} | {wp}/{ws} |".format(
                tag=item["tag"],
                count=item["count"],
                score=item["score"],
                r20=item["avg_return_20d"],
                r40=item["avg_return_40d"],
                e20=item["avg_excess_spy_20d"],
                wp=item["windows_positive_excess"],
                ws=item["windows_with_samples"],
            )
        )
    lines.extend(
        [
            "",
            "## Decision Read",
            "",
            read["reason"],
            "",
            f"Next action: `{read['next_action']}`",
            "",
            "## Guardrails",
            "",
            "- No production path changed.",
            "- No ticker-specific privilege is promoted from this audit.",
            "- No LLM, news, exit, sizing, ranking, or universe logic changed.",
            "- Any next strategy replay must be candidate-level and pre-registered.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    by_window = OrderedDict((name, _analyze_window(name, spec)) for name, spec in WINDOWS.items())
    aggregate = _aggregate(by_window)
    decision = "observed_only"
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hypothesis": (
            "META/NFLX entry quality may depend on ex-ante platform lifecycle "
            "states such as orderly pullback, breakout, post-earnings drift, "
            "relative strength, and trend structure. The goal is to discover "
            "which states deserve a later candidate-level replay, not to change "
            "production entries now."
        ),
        "history_check": {
            "exp-20260507-008": "Rejected core-platform pullback limit entry timing.",
            "exp-20260507-014": "Rejected core-platform post-target runner exits.",
            "exp-20260507-027": (
                "Cap-aware platform sizing was positive but immaterial and "
                "single-ticker concentrated."
            ),
            "exp-20260505-011_and_020": (
                "Rejected consumer-platform universe/gate. This audit adds no "
                "new names and promotes no ticker-specific rule."
            ),
            "mechanism_insight_conflict": (
                "This is not an OHLCV threshold promotion; it is observed-only "
                "surface discovery to decide whether a later replay is justified."
            ),
        },
        "parameters": {
            "seed_tickers": list(SEED_TICKERS),
            "peer_tickers": list(PEER_TICKERS),
            "benchmarks": list(BENCHMARKS),
            "forward_horizons": list(FORWARD_HORIZONS),
            "decision_price": "same-day close",
            "hypothetical_entry": "next trading-day open",
            "surface_tags": [
                "orderly_pullback_3_8_above_sma50",
                "deep_pullback_8_15_above_sma200",
                "breakout_20d_high",
                "near_high_extended_5pct_above_sma20",
                "sma20_reclaim",
                "sma50_reclaim",
                "post_earnings_drift_1_10",
                "pre_earnings_runup_0_14",
                "rs20_leader",
                "rs60_leader",
                "gap_up_follow_through",
                "gap_up_fade",
                "below_sma50",
            ],
            "locked_variables": [
                "production universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "sizing",
                "exits",
                "add-ons",
                "LLM/news replay",
                "earnings strategy",
            ],
        },
        "by_window_counts": {
            name: {
                "row_count": window["row_count"],
                "ticker_counts": window["ticker_counts"],
                "cohort_counts": window["cohort_counts"],
            }
            for name, window in by_window.items()
        },
        "aggregate": aggregate,
        "decision": decision,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": True,
            "alters_orders": False,
            "alters_exits": False,
            "alters_sizing": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
        },
        "next_retry_requires": [
            "Do not promote ticker-specific META/NFLX timing directly from overlapping daily rows.",
            "A valid next step must freeze one or two timing tags and replay them only against candidate-level alternatives.",
            "Any strategy promotion must move the policy into shared run.py/backtester.py code with parity tests.",
        ],
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "docs/experiment_log.jsonl",
        ],
    }
    log_record = _log_record(payload)
    ticket = _ticket(payload)

    payload["by_window_sample_rows"] = {
        name: window["rows"][:5] for name, window in by_window.items()
    }
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, log_record)
    _write_json(TICKET_JSON, ticket)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact_markdown(payload), encoding="utf-8")
    _append_jsonl(EXPERIMENT_LOG, log_record)

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": decision,
                "decision_read": aggregate["decision_read"],
                "best_seed_surface": aggregate["best_surface"].get("seed", [])[:5],
                "out_json": str(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
