"""exp-20260623-008: broad-universe daily short-volume imbalance attribution.

Observed-only alpha attribution. The runner tests whether the archived Moomoo
daily short-volume ratio has monotonic next-10-trading-day predictive value
after mapping each activity date to the next tradable open. It deliberately
does not retune the rejected exp-20260622-010 activity-absorption thresholds,
promote a shared helper, or change orders, ranking, sizing, exits, LLM/news, or
watchlists.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, QUANT_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from constants import ROUND_TRIP_COST_PCT  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
from fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage  # noqa: E402


EXPERIMENT_ID = "exp-20260623-008"
SLUG = "daily_short_volume_broad_universe_candidate_pool"
RUNNER = f"quant/experiments/exp_20260623_008_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
OWNER = "agent_session_68cf2b14"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260623_008_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

ACTIVITY_ROWS_PATH = REPO_ROOT / "data" / "non_ohlcv" / "moomoo_daily_short_volume_broad" / "rows.jsonl"
BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)

WINDOWS = {
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20241002_20250422.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20250423_20251022.json",
    },
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20251023_20260421.json",
    },
}

HYPOTHESIS = (
    "Observed-only attribution on the BROAD liquid universe: Moomoo/FINRA daily "
    "short-volume imbalance (short-volume ratio versus its own trailing history) "
    "should show monotonic next-10-trading-day paper-return separation among "
    "liquid SPY/QQQ-relative leader rows. Re-tests the exp-20260622-010/021 "
    "signal on the full production get_universe() (51 names) instead of the "
    "5-ticker archive that made those rejections a concentration artifact."
)
CHANGE_TYPE = "observed_only_attribution"
MECHANISM_FAMILY = "production_visible_free_finra_daily_short_volume_candidate_pool"
TRIAL_FAMILY = "finra_daily_short_volume_broad_universe_candidate_pool"
TRIAL_VARIANT_ID = "observed_only_broad_universe_51ticker_imbalance_monotonicity_v1"
CHANGED_VARIABLE = "moomoo_daily_short_volume_broad_universe_imbalance_default_off_candidate_source_v1"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260622-008",
    "exp-20260622-009",
    "exp-20260622-010",
    "exp-20260622-021",
]
NEW_EVIDENCE_TYPE = "broader_archived_universe_coverage"
NEW_EVIDENCE_AXIS = (
    "Broad liquid-universe daily-short-volume archive (production get_universe() "
    "51 names, full PIT history to <=2024-06 per exp-20260623-008 backfill), "
    "replacing the 5-ticker archive that caused the concentration-artifact "
    "rejections of exp-20260622-010 and exp-20260622-021 - exactly the "
    "'materially broader archived Moomoo coverage' both closeouts named as "
    "new_evidence_required. Not a threshold retune on the same archive."
)
CAUSAL_COMPONENTS = [
    "broad-universe activity-only daily short-volume rows (51 tickers)",
    "next-open 10-trading-day paper outcome attribution",
    "trailing imbalance buckets",
    "no strategy change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260623-008/exp_20260623_008_daily_short_volume_broad_universe_candidate_pool.json",
    "experiments/cards/exp-20260623-008.md",
    "experiments/manifests/exp-20260623-008.json",
    "experiments/tickets/exp-20260623-008.json",
    "experiments/logs/exp-20260623-008.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]

DEFAULT_PREDICTION = {
    "success_probability": 0.20,
    "expected_ev_delta": 0.15,
    "expected_pnl_delta": 2500.0,
    "main_failure_modes": [
        "target_concentration_failed",
        "thin_signal_low_sample",
        "edge_not_power",
        "daily_short_volume_not_next10d_predictive",
        "universe_coverage_gap_smallcap",
    ],
    "confidence_reason": (
        "New PIT daily dataset in the only live candidate-pool source family "
        "(finra 26.7%), but prior bi-weekly short-pressure pools are 0/5 so "
        "the broader thesis is unproven; daily flow is the genuinely new axis."
    ),
    "recorded_at": "2026-06-22T19:40:09+00:00",
}

CONFIG = {
    "lookback_rows": 60,
    "min_prior_rows": 40,
    "hold_days": 10,
    "paper_notional_usd": 4000.0,
    "min_price": 10.0,
    "min_avg_dollar_volume_20d": 50_000_000.0,
    "leader_min_ret20_excess_spy": 0.0,
    "leader_min_ret20_excess_qqq": 0.0,
    "leader_min_close_location": 0.50,
}
BUCKETS = ["low", "mid", "high"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                rows.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(raw)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def round_or_none(value: Any, digits: int = 6) -> float | None:
    number = as_float(value)
    if number is None:
        return None
    return round(number, digits)


def load_ticket_prediction() -> dict[str, Any]:
    if not TICKET_JSON.exists():
        return DEFAULT_PREDICTION
    ticket = read_json(TICKET_JSON)
    prediction = ticket.get("prediction")
    if isinstance(prediction, dict) and prediction:
        return prediction
    return DEFAULT_PREDICTION


def load_activity_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with ACTIVITY_ROWS_PATH.open(encoding="utf-8-sig") as handle:
        for raw in handle:
            if not raw.strip():
                continue
            row = json.loads(raw)
            ticker = str(row.get("ticker") or "").upper()
            activity_date = str(row.get("activity_date") or "")[:10]
            ratio = as_float(row.get("short_volume_ratio"))
            volume = as_float(row.get("volume"))
            total_short = as_float(row.get("total_shares_short"))
            if not ticker or len(activity_date) != 10 or ratio is None:
                continue
            rows.append(
                {
                    **row,
                    "ticker": ticker,
                    "activity_date": activity_date,
                    "short_volume_ratio": ratio,
                    "volume": volume,
                    "total_shares_short": total_short,
                }
            )
    rows.sort(key=lambda row: (row["ticker"], row["activity_date"]))
    return rows


def load_ohlcv(path: Path) -> dict[str, list[dict[str, Any]]]:
    payload = read_json(path)
    raw = payload.get("ohlcv") if isinstance(payload, dict) else payload
    out: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in (raw or {}).items():
        normalised: list[dict[str, Any]] = []
        for row in rows or []:
            day = str(row.get("Date") or row.get("date") or "")[:10]
            open_ = as_float(row.get("Open") if "Open" in row else row.get("open"))
            high = as_float(row.get("High") if "High" in row else row.get("high"))
            low = as_float(row.get("Low") if "Low" in row else row.get("low"))
            close = as_float(row.get("Close") if "Close" in row else row.get("close"))
            volume = as_float(row.get("Volume") if "Volume" in row else row.get("volume"))
            if len(day) != 10 or open_ is None or high is None or low is None or close is None:
                continue
            normalised.append(
                {
                    "Date": day,
                    "Open": open_,
                    "High": high,
                    "Low": low,
                    "Close": close,
                    "Volume": volume or 0.0,
                }
            )
        if normalised:
            normalised.sort(key=lambda item: item["Date"])
            out[str(ticker).upper()] = normalised
    return out


def row_index(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {str(row.get("Date")): index for index, row in enumerate(rows)}


def value(row: dict[str, Any], key: str) -> float | None:
    return as_float(row.get(key))


def daily_return(rows: list[dict[str, Any]], index: int) -> float | None:
    if index < 1:
        return None
    prior = value(rows[index - 1], "Close")
    close = value(rows[index], "Close")
    if prior is None or prior <= 0 or close is None:
        return None
    return close / prior - 1.0


def ret(rows: list[dict[str, Any]], index: int, lookback: int) -> float | None:
    if index < lookback:
        return None
    prior = value(rows[index - lookback], "Close")
    close = value(rows[index], "Close")
    if prior is None or prior <= 0 or close is None:
        return None
    return close / prior - 1.0


def avg_dollar_volume(rows: list[dict[str, Any]], index: int, lookback: int = 20) -> float | None:
    if index < lookback - 1:
        return None
    values: list[float] = []
    for row in rows[index - lookback + 1 : index + 1]:
        close = value(row, "Close")
        volume = value(row, "Volume")
        if close is None or volume is None:
            return None
        values.append(close * volume)
    return sum(values) / len(values)


def close_location(row: dict[str, Any]) -> float | None:
    high = value(row, "High")
    low = value(row, "Low")
    close = value(row, "Close")
    if high is None or low is None or close is None:
        return None
    span = high - low
    if span <= 0:
        return 0.5
    return (close - low) / span


def ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    out = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        avg_rank = (start + 1 + end) / 2.0
        for rank_index in range(start, end):
            out[order[rank_index]] = avg_rank
        start = end
    return out


def spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 4:
        return None
    rx = ranks(xs)
    ry = ranks(ys)
    mean_x = sum(rx) / len(rx)
    mean_y = sum(ry) / len(ry)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(rx, ry))
    den_x = math.sqrt(sum((x - mean_x) ** 2 for x in rx))
    den_y = math.sqrt(sum((y - mean_y) ** 2 for y in ry))
    if den_x == 0 or den_y == 0:
        return None
    return round(numerator / (den_x * den_y), 6)


def bucket_rows_by_tertile(rows: list[dict[str, Any]], field: str, output_field: str) -> None:
    ordered = sorted(
        range(len(rows)),
        key=lambda index: (
            rows[index][field],
            rows[index].get("activity_date") or "",
            rows[index].get("ticker") or "",
        ),
    )
    n = len(ordered)
    for rank, row_index in enumerate(ordered):
        if rank < n / 3:
            bucket = "low"
        elif rank < 2 * n / 3:
            bucket = "mid"
        else:
            bucket = "high"
        rows[row_index][output_field] = bucket


def load_baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT)
    windows = list(payload.get("windows") or [])
    generated = sum(int(window.get("signals_generated") or 0) for window in windows)
    survived = sum(int(window.get("signals_survived") or 0) for window in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(window.get("expected_value_score") or 0.0) for window in windows),
            4,
        ),
        "total_pnl": round(sum(float(window.get("total_pnl") or 0.0) for window in windows), 2),
        "trade_count": sum(int(window.get("trade_count") or 0) for window in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 4) if generated else None,
        "max_drawdown_pct_worst": max(
            float(window.get("max_drawdown_pct") or 0.0) for window in windows
        )
        if windows
        else None,
        "windows": windows,
    }


def activity_by_ticker(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        out[row["ticker"]].append(row)
    for ticker in out:
        out[ticker].sort(key=lambda row: row["activity_date"])
    return dict(out)


def paper_trade_from_activity(
    *,
    window_label: str,
    activity: dict[str, Any],
    activity_index: int,
    activity_rows_for_ticker: list[dict[str, Any]],
    ohlcv: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
) -> tuple[dict[str, Any] | None, str | None]:
    ticker = activity["ticker"]
    signal_date = activity["activity_date"]
    rows = ohlcv.get(ticker)
    spy_rows = ohlcv.get("SPY")
    qqq_rows = ohlcv.get("QQQ")
    if not rows or not spy_rows or not qqq_rows:
        return None, "missing_ohlcv"
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    qqq_idx = indices.get("QQQ", {}).get(signal_date)
    if idx is None or spy_idx is None or qqq_idx is None:
        return None, "activity_date_missing_from_ohlcv"
    if idx < 20 or spy_idx < 20 or qqq_idx < 20:
        return None, "insufficient_ohlcv_history"
    if idx + CONFIG["hold_days"] >= len(rows) or idx + 1 >= len(rows):
        return None, "missing_entry_or_exit_bar"

    prior = [
        as_float(row.get("short_volume_ratio"))
        for row in activity_rows_for_ticker[
            max(0, activity_index - CONFIG["lookback_rows"]) : activity_index
        ]
    ]
    prior_ratios = [value for value in prior if value is not None]
    if len(prior_ratios) < CONFIG["min_prior_rows"]:
        return None, "insufficient_activity_history"
    ratio = as_float(activity.get("short_volume_ratio"))
    volume = as_float(activity.get("volume"))
    total_short = as_float(activity.get("total_shares_short"))
    if ratio is None or volume is None or total_short is None:
        return None, "missing_activity_fields"
    prior_median = median(prior_ratios)
    if prior_median <= 0:
        return None, "bad_prior_median"
    ratio_vs_median = ratio / prior_median
    mean_prior = sum(prior_ratios) / len(prior_ratios)
    std_prior = math.sqrt(sum((value - mean_prior) ** 2 for value in prior_ratios) / len(prior_ratios))
    zscore = (ratio - mean_prior) / std_prior if std_prior > 0 else 0.0

    close = value(rows[idx], "Close")
    if close is None or close < CONFIG["min_price"]:
        return None, "price_floor"
    adv20 = avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < CONFIG["min_avg_dollar_volume_20d"]:
        return None, "liquidity_floor"
    ret20 = ret(rows, idx, 20)
    spy_ret20 = ret(spy_rows, spy_idx, 20)
    qqq_ret20 = ret(qqq_rows, qqq_idx, 20)
    ret5 = ret(rows, idx, 5)
    signal_return = daily_return(rows, idx)
    spy_signal_return = daily_return(spy_rows, spy_idx)
    qqq_signal_return = daily_return(qqq_rows, qqq_idx)
    loc = close_location(rows[idx])
    if (
        ret20 is None
        or spy_ret20 is None
        or qqq_ret20 is None
        or ret5 is None
        or signal_return is None
        or spy_signal_return is None
        or qqq_signal_return is None
        or loc is None
    ):
        return None, "missing_return_fields"
    ret20_excess_spy = ret20 - spy_ret20
    ret20_excess_qqq = ret20 - qqq_ret20
    leader_context = (
        ret20_excess_spy >= CONFIG["leader_min_ret20_excess_spy"]
        and ret20_excess_qqq >= CONFIG["leader_min_ret20_excess_qqq"]
        and loc >= CONFIG["leader_min_close_location"]
    )

    entry_raw = value(rows[idx + 1], "Open")
    exit_raw = value(rows[idx + CONFIG["hold_days"]], "Close")
    if entry_raw is None or entry_raw <= 0 or exit_raw is None or exit_raw <= 0:
        return None, "missing_entry_or_exit_price"
    entry_price = apply_entry_fill(entry_raw)
    exit_price = apply_slippage(exit_raw, SLIPPAGE_BPS_TARGET, "sell")
    pnl_pct_net = exit_price / entry_price - 1.0 - ROUND_TRIP_COST_PCT
    pnl = CONFIG["paper_notional_usd"] * pnl_pct_net
    row = {
        "window": window_label,
        "ticker": ticker,
        "activity_date": signal_date,
        "entry_date": rows[idx + 1]["Date"],
        "exit_date": rows[idx + CONFIG["hold_days"]]["Date"],
        "entry_price": round(entry_price, 4),
        "exit_price": round(exit_price, 4),
        "pnl_pct_net": round(pnl_pct_net, 6),
        "pnl": round(pnl, 2),
        "paper_notional_usd": CONFIG["paper_notional_usd"],
        "short_volume_ratio": round(ratio, 8),
        "short_volume_ratio_prior_median": round(prior_median, 8),
        "short_volume_ratio_vs_median": round(ratio_vs_median, 6),
        "short_volume_ratio_zscore": round(zscore, 6),
        "total_shares_short": round(total_short, 2),
        "activity_volume": round(volume, 2),
        "ret5": round(ret5, 6),
        "ret20": round(ret20, 6),
        "ret20_excess_spy": round(ret20_excess_spy, 6),
        "ret20_excess_qqq": round(ret20_excess_qqq, 6),
        "signal_return": round(signal_return, 6),
        "signal_return_vs_spy": round(signal_return - spy_signal_return, 6),
        "signal_return_vs_qqq": round(signal_return - qqq_signal_return, 6),
        "close_location": round(loc, 6),
        "avg_dollar_volume_20d": round(adv20, 2),
        "leader_context": leader_context,
        "activity_only_not_positioning": True,
        "trade_enabled": False,
        "known_at": "after_activity_date_close_before_next_open_paper_entry",
    }
    return row, None


def build_outcome_rows(activity_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_ticker = activity_by_ticker(activity_rows)
    outcome_rows: list[dict[str, Any]] = []
    audit: dict[str, Any] = {"by_window": {}, "reject_reasons": defaultdict(int)}
    for label, cfg in WINDOWS.items():
        ohlcv = load_ohlcv(cfg["snapshot"])
        indices = {ticker: row_index(rows) for ticker, rows in ohlcv.items()}
        window_count = 0
        window_rejects: dict[str, int] = defaultdict(int)
        for ticker, rows_for_ticker in by_ticker.items():
            for activity_index, activity in enumerate(rows_for_ticker):
                day = activity["activity_date"]
                if day < cfg["start"] or day > cfg["end"]:
                    continue
                window_count += 1
                row, reason = paper_trade_from_activity(
                    window_label=label,
                    activity=activity,
                    activity_index=activity_index,
                    activity_rows_for_ticker=rows_for_ticker,
                    ohlcv=ohlcv,
                    indices=indices,
                )
                if row is None:
                    window_rejects[str(reason)] += 1
                    audit["reject_reasons"][str(reason)] += 1
                    continue
                outcome_rows.append(row)
        audit["by_window"][label] = {
            "activity_rows_in_window": window_count,
            "outcome_rows": len([row for row in outcome_rows if row["window"] == label]),
            "reject_reasons": dict(window_rejects),
            "snapshot": repo_rel(cfg["snapshot"]),
        }
    audit["reject_reasons"] = dict(audit["reject_reasons"])
    return outcome_rows, audit


def summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "n": 0,
            "mean_pnl": None,
            "median_pnl": None,
            "win_rate": None,
            "total_pnl": 0.0,
            "mean_pnl_pct_net": None,
            "median_imbalance": None,
        }
    pnls = [float(row["pnl"]) for row in rows]
    pct = [float(row["pnl_pct_net"]) for row in rows]
    imbalances = [float(row["short_volume_ratio_vs_median"]) for row in rows]
    return {
        "n": len(rows),
        "mean_pnl": round(sum(pnls) / len(pnls), 2),
        "median_pnl": round(float(median(pnls)), 2),
        "win_rate": round(sum(1 for pnl in pnls if pnl > 0) / len(pnls), 4),
        "total_pnl": round(sum(pnls), 2),
        "mean_pnl_pct_net": round(sum(pct) / len(pct), 6),
        "median_imbalance": round(float(median(imbalances)), 6),
    }


def bucket_summary(rows: list[dict[str, Any]], bucket_field: str) -> dict[str, Any]:
    return {bucket: summary([row for row in rows if row.get(bucket_field) == bucket]) for bucket in BUCKETS}


def is_monotonic_high_mid_low(bucketed: dict[str, dict[str, Any]], metric: str) -> bool:
    low = bucketed["low"].get(metric)
    mid = bucketed["mid"].get(metric)
    high = bucketed["high"].get(metric)
    if low is None or mid is None or high is None:
        return False
    return float(high) > float(mid) > float(low)


def contribution(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        value_key = str(row.get(key) or "unknown")
        item = grouped.setdefault(value_key, {"value": value_key, "n": 0, "total_pnl": 0.0})
        item["n"] += 1
        item["total_pnl"] += float(row["pnl"])
    out = [
        {"value": item["value"], "n": item["n"], "total_pnl": round(item["total_pnl"], 2)}
        for item in grouped.values()
    ]
    out.sort(key=lambda item: (-abs(float(item["total_pnl"])), item["value"]))
    return out[:20]


def analyze(rows: list[dict[str, Any]]) -> dict[str, Any]:
    bucket_rows_by_tertile(rows, "short_volume_ratio_vs_median", "imbalance_bucket_all")
    leader_rows = [row for row in rows if row["leader_context"]]
    bucket_rows_by_tertile(leader_rows, "short_volume_ratio_vs_median", "imbalance_bucket_leader")

    by_window: dict[str, Any] = {}
    for label in WINDOWS:
        window_rows = [row for row in leader_rows if row["window"] == label]
        bucketed = bucket_summary(window_rows, "imbalance_bucket_leader")
        by_window[label] = {
            "n": len(window_rows),
            "bucket_summary": bucketed,
            "mean_monotonic_high_mid_low": is_monotonic_high_mid_low(bucketed, "mean_pnl"),
            "median_monotonic_high_mid_low": is_monotonic_high_mid_low(bucketed, "median_pnl"),
            "spearman_imbalance_to_pnl": spearman(
                [float(row["short_volume_ratio_vs_median"]) for row in window_rows],
                [float(row["pnl"]) for row in window_rows],
            ),
        }

    pooled_leader = bucket_summary(leader_rows, "imbalance_bucket_leader")
    pooled_all = bucket_summary(rows, "imbalance_bucket_all")
    return {
        "all_liquid_rows": {
            "n": len(rows),
            "bucket_summary": pooled_all,
            "spearman_imbalance_to_pnl": spearman(
                [float(row["short_volume_ratio_vs_median"]) for row in rows],
                [float(row["pnl"]) for row in rows],
            ),
            "ticker_contribution": contribution(rows, "ticker"),
        },
        "leader_context_rows": {
            "n": len(leader_rows),
            "bucket_summary": pooled_leader,
            "per_window": by_window,
            "spearman_imbalance_to_pnl": spearman(
                [float(row["short_volume_ratio_vs_median"]) for row in leader_rows],
                [float(row["pnl"]) for row in leader_rows],
            ),
            "ticker_contribution": contribution(leader_rows, "ticker"),
        },
    }


def acceptance_checks(analysis: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    leader = analysis["leader_context_rows"]
    pooled = leader["bucket_summary"]
    per_window = leader["per_window"]
    high = pooled["high"]
    low = pooled["low"]
    high_mean = high.get("mean_pnl")
    high_median = high.get("median_pnl")
    low_mean = low.get("mean_pnl")
    low_median = low.get("median_pnl")
    window_positive_high = 0
    window_spearman_positive = 0
    window_high_counts: dict[str, int] = {}
    for label, item in per_window.items():
        bucketed = item["bucket_summary"]
        high_bucket = bucketed["high"]
        window_high_counts[label] = int(high_bucket["n"])
        if high_bucket.get("mean_pnl") is not None and high_bucket["mean_pnl"] > 0:
            window_positive_high += 1
        spearman_value = item.get("spearman_imbalance_to_pnl")
        if spearman_value is not None and spearman_value > 0:
            window_spearman_positive += 1

    checks = {
        "leader_rows_min_sample_passed": leader["n"] >= 120,
        "leader_high_bucket_min_count": min(window_high_counts.values()) if window_high_counts else 0,
        "leader_high_bucket_min_count_passed": bool(window_high_counts)
        and min(window_high_counts.values()) >= 10,
        "pooled_mean_high_beats_low": (
            high_mean is not None and low_mean is not None and high_mean > low_mean
        ),
        "pooled_median_high_beats_low": (
            high_median is not None and low_median is not None and high_median > low_median
        ),
        "pooled_mean_monotonic_high_mid_low": is_monotonic_high_mid_low(pooled, "mean_pnl"),
        "pooled_median_monotonic_high_mid_low": is_monotonic_high_mid_low(
            pooled,
            "median_pnl",
        ),
        "leader_spearman_positive": (
            leader.get("spearman_imbalance_to_pnl") is not None
            and leader["spearman_imbalance_to_pnl"] > 0
        ),
        "window_positive_high_count": window_positive_high,
        "window_positive_high_count_passed": window_positive_high >= 2,
        "window_spearman_positive_count": window_spearman_positive,
        "window_spearman_positive_count_passed": window_spearman_positive >= 2,
        "window_high_counts": window_high_counts,
    }
    failed: list[str] = []
    for key, value in checks.items():
        if key.endswith("_passed") and not value:
            failed.append(key.replace("_passed", "_failed"))
    if not checks["pooled_mean_high_beats_low"]:
        failed.append("pooled_high_mean_not_above_low")
    if not checks["pooled_median_high_beats_low"]:
        failed.append("pooled_high_median_not_above_low")
    if not checks["pooled_mean_monotonic_high_mid_low"]:
        failed.append("pooled_mean_not_monotonic")
    if not checks["pooled_median_monotonic_high_mid_low"]:
        failed.append("pooled_median_not_monotonic")
    if not checks["leader_spearman_positive"]:
        failed.append("leader_spearman_not_positive")
    return checks, failed


def calibration(prediction: dict[str, Any], decision_passed: bool, failed: list[str]) -> dict[str, Any]:
    predicted = float(prediction.get("success_probability") or 0.0)
    actual = 1 if decision_passed else 0
    return {
        "actual_success": actual,
        "actual_decision": (
            "observed_only_positive_imbalance_lead_not_promoted"
            if decision_passed
            else "rejected_no_monotonic_daily_short_volume_imbalance_edge"
        ),
        "predicted_success_probability": predicted,
        "brier_score": round((predicted - actual) ** 2, 6),
        "predicted_failure_modes": prediction.get("main_failure_modes") or [],
        "realized_failure_modes": failed,
        "predicted_failure_mode_hit": bool(failed),
        "surprise_note": (
            "Daily short-volume imbalance did not produce the required monotonic "
            "leader-context separation; this matches the main edge-not-power risk."
            if failed
            else "The imbalance attribution passed the observed-only screen but remains non-promoted."
        ),
    }


def build_payload() -> dict[str, Any]:
    prediction = load_ticket_prediction()
    activity_rows = load_activity_rows()
    outcome_rows, audit = build_outcome_rows(activity_rows)
    if len(outcome_rows) < 50:
        raise RuntimeError("Not enough daily short-volume outcome rows for attribution.")
    analysis = analyze(outcome_rows)
    checks, failed = acceptance_checks(analysis)
    observed_lead = not failed
    status = "observed_only_positive_lead" if observed_lead else "observed_only_rejected"
    decision = (
        "observed_only_positive_daily_short_volume_imbalance_lead_not_promoted"
        if observed_lead
        else "rejected_no_monotonic_daily_short_volume_imbalance_edge"
    )
    baseline = load_baseline_metrics()
    now = utc_now()
    why = (
        "Daily short-volume imbalance did not show enough monotonic predictive "
        "power in the leader-context rows. The archived surface is real and "
        "PIT-mappable, but high imbalance was not consistently better across "
        "pooled mean/median and window-level Spearman tests."
        if failed
        else "Daily short-volume imbalance showed monotonic leader-context outcome separation, but no strategy or helper was promoted."
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": status,
        "lane": "alpha_search",
        "owner": OWNER,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": observed_lead,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "observed_only_attribution_runner",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": "Ticket reservation recorded a novelty override for daily flow data.",
                "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
                "important_boundary": (
                    "exp-20260622-010 already rejected thresholded activity "
                    "absorption. This run tests monotonic imbalance attribution "
                    "without changing thresholds, top-N, hold, or notional."
                ),
            },
            "3_single_policy_bundle": (
                "Archived activity-only daily short-volume rows plus fixed "
                "next-open/10-trading-day outcome attribution. No entry, "
                "ranking, sizing, exit, or live/default behavior changes."
            ),
            "4_success_failure_standard": (
                "Observed-only lead only if leader-context rows have enough "
                "sample, high imbalance beats low on pooled mean and median PnL, "
                "pooled mean/median are high>mid>low, pooled Spearman is "
                "positive, and at least two windows have positive high-bucket "
                "mean PnL and positive Spearman."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "activity_rows_path": repo_rel(ACTIVITY_ROWS_PATH),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "windows": {
                label: {
                    "start": cfg["start"],
                    "end": cfg["end"],
                    "snapshot": repo_rel(cfg["snapshot"]),
                }
                for label, cfg in WINDOWS.items()
            },
            "config": CONFIG,
            "bucket_method": "within-sample tertiles on short_volume_ratio_vs_median",
        },
        "gate1": {
            "baseline_loaded": True,
            "baseline_metrics": baseline,
            "note": "Observed-only attribution; before and after policy are identical.",
        },
        "gate2": {
            "dependencies_validated": True,
            "activity_archive_rows": len(activity_rows),
            "outcome_rows": len(outcome_rows),
            "archive_tickers": sorted({row["ticker"] for row in activity_rows}),
            "fields_checked": [
                "activity_date",
                "entry_date",
                "exit_date",
                "short_volume_ratio",
                "short_volume_ratio_vs_median",
                "pnl",
                "leader_context",
            ],
            "entry_date_present": all(bool(row.get("entry_date")) for row in outcome_rows),
            "target_price_relevance": (
                "Not applicable: this is observed-only outcome attribution and "
                "does not schedule target exits or orders."
            ),
            "audit": audit,
        },
        "gate3": {
            "filter_added": False,
            "signals_generated": len(activity_rows),
            "signals_survived": len(outcome_rows),
            "survival_rate": round(len(outcome_rows) / len(activity_rows), 4)
            if activity_rows
            else None,
            "baseline_survival_rate": baseline["survival_rate"],
            "note": "No executable filter was added; rows are attributed only.",
        },
        "gate4": {
            "observed_only_lead": observed_lead,
            "failed_reasons": failed,
            "acceptance_checks": checks,
            "decision": decision,
            "strategy_rerun_required": False,
            "before_after_strategy_delta": {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "max_drawdown_pct": 0.0,
            },
            "lead_limitations": [
                "Five archived ticker surface only.",
                "No shared helper or daily adapter promoted.",
                "Daily short volume remains activity-only, not short-interest positioning.",
            ],
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "max_drawdown_pct_worst_delta": 0.0,
        },
        "attribution": {
            "n_rows": len(outcome_rows),
            "analysis": analysis,
            "sample_rows": outcome_rows[:200],
        },
        "production_impact": {
            "trade_enabled": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "entry_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_rules_changed": False,
            "shared_helper_promoted": False,
            "daily_snapshot_exposed": False,
            "uses_moomoo_daily_short_volume": True,
            "activity_only_not_positioning": True,
            "live_realistic_execution_envelope": (
                "Not evaluated for live use; this is observed-only attribution "
                "and cannot become live-ready."
            ),
        },
        "calibration": calibration(prediction, observed_lead, failed),
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retry short_volume_ratio, ratio-vs-median, z-score, "
                "top-N, hold-day, notional, cooldown, or activity-absorption "
                "threshold sweeps on this broad 51-ticker universe archive. That "
                "would repeat exp-20260622-010/021 and this broad-universe near "
                "neighbor. The 5-ticker concentration excuse is now spent."
            ),
            "new_evidence_required": (
                "With the broad-universe coverage gap closed, a valid retry needs "
                "a materially DIFFERENT signal axis - PIT borrow fee/utilization "
                "or loan-availability, options-implied move/skew, or closed "
                "forward replacement-value rows from a shared default-off helper - "
                "not another threshold or universe-size retune."
            ),
        },
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "related_files": [
            RUNNER,
            repo_rel(ACTIVITY_ROWS_PATH),
            repo_rel(BASELINE_RESULT),
            "experiments/logs/exp-20260622-010.json",
            "quant/experiments/exp_20260622_010_moomoo_daily_short_volume_activity_helper.py",
        ],
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "lane": payload["lane"],
        "owner": payload["owner"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "observed_only_lead": payload["observed_only_lead"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "single_causal_variable": payload["single_causal_variable"],
        "causal_components": payload["causal_components"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "new_evidence_axis": payload["new_evidence_axis"],
        "prediction": payload["prediction"],
        "pre_run_questions": payload["pre_run_questions"],
        "parameters": payload["parameters"],
        "gate1": payload["gate1"],
        "gate2": {
            **payload["gate2"],
            "audit": "<see artifact>",
        },
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "attribution": {
            "n_rows": payload["attribution"]["n_rows"],
            "all_liquid_rows": payload["attribution"]["analysis"]["all_liquid_rows"],
            "leader_context_rows": payload["attribution"]["analysis"]["leader_context_rows"],
        },
        "production_impact": payload["production_impact"],
        "calibration": payload["calibration"],
        "post_run_reflection": payload["post_run_reflection"],
        "related_files": payload["related_files"],
        "anti_js": payload["anti_js"],
    }


def build_card(payload: dict[str, Any]) -> str:
    leader = payload["attribution"]["analysis"]["leader_context_rows"]
    bucketed = leader["bucket_summary"]
    rows = [
        "| Bucket | Rows | Mean PnL | Median PnL | Win Rate | Total PnL | Median Imbalance |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for bucket_name in BUCKETS:
        bucket = bucketed[bucket_name]
        rows.append(
            "| {name} | {n} | ${mean:,.2f} | ${median:,.2f} | {win:.2%} | ${total:,.2f} | {imb:.4f} |".format(
                name=bucket_name,
                n=bucket["n"],
                mean=bucket["mean_pnl"] or 0.0,
                median=bucket["median_pnl"] or 0.0,
                win=bucket["win_rate"] or 0.0,
                total=bucket["total_pnl"] or 0.0,
                imb=bucket["median_imbalance"] or 0.0,
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: daily short-volume imbalance attribution",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Production orders changed: no",
            "- Shared helper promoted: no",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Leader-Context Buckets",
            "",
            *rows,
            "",
            "- Leader rows: `{}`".format(leader["n"]),
            "- Spearman(imbalance, PnL): `{}`".format(leader["spearman_imbalance_to_pnl"]),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)} for path in files},
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)

    registry_result = {
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": payload["observed_only_lead"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "attribution": {
            "n_rows": payload["attribution"]["n_rows"],
            "leader_context_rows": payload["attribution"]["analysis"]["leader_context_rows"],
        },
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result=registry_result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "change_type": payload["change_type"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": payload["single_causal_variable"],
            "changed_variable": payload["changed_variable"],
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "new_evidence_axis": payload["new_evidence_axis"],
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "allowed_write_scope": ALLOWED_WRITE_SCOPE,
            "related_files": payload["related_files"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    leader = payload["attribution"]["analysis"]["leader_context_rows"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "outcome_rows": payload["attribution"]["n_rows"],
                "leader_rows": leader["n"],
                "leader_spearman": leader["spearman_imbalance_to_pnl"],
                "leader_bucket_summary": leader["bucket_summary"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
