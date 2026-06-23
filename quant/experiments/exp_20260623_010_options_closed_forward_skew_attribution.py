"""exp-20260623-010: options closed-forward skew attribution.

Observed-only alpha attribution. This runner settles closeable rows from the
exp-20260623-009 OnclickMedia options observation ledger against warehouse
OHLCV, then tests whether a fixed call-led / low-put-protection skew score has
monotonic 10-trading-day replacement-value separation.

No strategy, helper, ranking, sizing, exit, order, watchlist, LLM, or daily
collector behavior changes in this experiment.
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
from quant.ohlcv_warehouse import (  # noqa: E402
    DEFAULT_WAREHOUSE_PATH,
    load_warehouse_ohlcv_frames,
)


EXPERIMENT_ID = "exp-20260623-010"
SLUG = "options_closed_forward_skew_attribution"
RUNNER = f"quant/experiments/exp_20260623_010_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
OWNER = "alpha-explore"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260623_010_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

SOURCE_LEDGER = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260623-009"
    / "options_forward_observation_ledger.jsonl"
)
BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)

HYPOTHESIS = (
    "Observed-only attribution: closed forward OnclickMedia options ledger rows "
    "may show monotonic next-10-trading-day replacement-value separation from "
    "put/call volume and IV skew, creating a future options confirmation lead "
    "without changing any strategy behavior."
)
CHANGE_TYPE = "observed_only_attribution"
MECHANISM_FAMILY = "production_visible_forward_options_attribution"
TRIAL_FAMILY = "onclickmedia_options_closed_forward_skew_attribution"
TRIAL_VARIANT_ID = "closed_forward_put_call_iv_skew_monotonicity_v1"
CHANGED_VARIABLE = "onclickmedia_options_closed_forward_skew_monotonicity_v1"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260617-004",
    "exp-20260618-023",
    "exp-20260623-009",
]
NEW_EVIDENCE_AXIS = (
    "New closed forward replacement-value rows derived from the exp-20260623-009 "
    "options observation ledger; this is not a canonical-window options threshold, "
    "moneyness, expiration, top-N, hold, or notional sweep."
)
CAUSAL_COMPONENTS = [
    "exp009 options forward ledger",
    "warehouse OHLCV outcome settlement",
    "put-call volume and IV skew tertiles",
    "replacement value versus cash SPY QQQ",
    "no strategy behavior change",
]

CONFIG = {
    "hold_days": 10,
    "paper_notional_usd": 4000.0,
    "quality_min_liquid_contract_rate": 0.50,
    "quality_min_avg_liquidity_score": 0.50,
    "quality_max_wide_spread_contract_rate": 0.75,
    "quality_max_zero_bid_or_ask_count": 60,
    "min_closed_rows": 30,
    "min_quality_rows": 30,
    "max_single_positive_pnl_share": 0.50,
}
BUCKETS = ["low_bullish", "mid_bullish", "high_bullish"]

DEFAULT_PREDICTION = {
    "success_probability": 0.22,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "closed_sample_too_small",
        "no_monotonic_separation",
        "options_quality_flags_dominate",
        "mega_cap_concentration",
    ],
    "confidence_reason": (
        "Prior options alpha attempts were blocked for missing PIT coverage, but "
        "exp-20260623-009 normalized 1846 forward observations with usable trade "
        "dates. This run uses only newly closeable forward outcomes from that "
        "ledger, not historical threshold sweeps; the main risk is that sample "
        "quality and vendor-asof caveats overwhelm any skew signal."
    ),
    "recorded_at": "2026-06-23T07:05:46+00:00",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
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


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def load_ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    return prediction or DEFAULT_PREDICTION


def load_baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
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
            (float(window.get("max_drawdown_pct") or 0.0) for window in windows),
            default=None,
        ),
        "windows": windows,
    }


def load_source_ledger() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not SOURCE_LEDGER.exists():
        return rows
    with SOURCE_LEDGER.open(encoding="utf-8-sig") as handle:
        for raw in handle:
            if not raw.strip():
                continue
            row = json.loads(raw)
            ticker = str(row.get("ticker") or "").upper()
            usable = str(row.get("usable_trade_date") or "")[:10]
            if not ticker or len(usable) != 10:
                continue
            rows.append({**row, "ticker": ticker, "usable_trade_date": usable})
    return rows


def date_text(raw: Any) -> str:
    return str(raw)[:10]


def frame_to_rows(frame: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for day, row in frame.iterrows():
        open_ = as_float(row.get("Open"))
        high = as_float(row.get("High"))
        low = as_float(row.get("Low"))
        close = as_float(row.get("Close"))
        volume = as_float(row.get("Volume"))
        if open_ is None or high is None or low is None or close is None:
            continue
        out.append(
            {
                "Date": date_text(day),
                "Open": open_,
                "High": high,
                "Low": low,
                "Close": close,
                "Volume": volume or 0.0,
            }
        )
    out.sort(key=lambda row: row["Date"])
    return out


def load_ohlcv_rows(ledger: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    tickers = {str(row["ticker"]).upper() for row in ledger}
    tickers.update({"SPY", "QQQ"})
    usable_dates = sorted({str(row["usable_trade_date"]) for row in ledger})
    start = usable_dates[0] if usable_dates else "2026-01-01"
    end = "2026-12-31"
    frames = load_warehouse_ohlcv_frames(DEFAULT_WAREHOUSE_PATH, sorted(tickers), start, end)
    return {ticker: frame_to_rows(frame) for ticker, frame in frames.items()}


def first_index_on_or_after(rows: list[dict[str, Any]], day: str) -> int | None:
    for index, row in enumerate(rows):
        if row["Date"] >= day:
            return index
    return None


def index_by_date(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {row["Date"]: index for index, row in enumerate(rows)}


def stock_pnl_from_dates(
    rows: list[dict[str, Any]],
    entry_date: str,
    exit_date: str,
    notional: float,
) -> float | None:
    idx = index_by_date(rows)
    entry_index = idx.get(entry_date)
    exit_index = idx.get(exit_date)
    if entry_index is None or exit_index is None:
        return None
    entry_raw = as_float(rows[entry_index].get("Open"))
    exit_raw = as_float(rows[exit_index].get("Close"))
    if entry_raw is None or entry_raw <= 0 or exit_raw is None or exit_raw <= 0:
        return None
    entry_price = apply_entry_fill(entry_raw)
    exit_price = apply_slippage(exit_raw, SLIPPAGE_BPS_TARGET, "sell")
    return notional * (exit_price / entry_price - 1.0 - ROUND_TRIP_COST_PCT)


def settle_row(row: dict[str, Any], bars: dict[str, list[dict[str, Any]]]) -> tuple[dict[str, Any] | None, str]:
    ticker = row["ticker"]
    rows = bars.get(ticker)
    if not rows:
        return None, "missing_ticker_ohlcv"
    entry_index = first_index_on_or_after(rows, row["usable_trade_date"])
    if entry_index is None:
        return None, "missing_entry_bar"
    exit_index = entry_index + int(CONFIG["hold_days"])
    if exit_index >= len(rows):
        return None, "not_yet_10d_closed"
    entry = rows[entry_index]
    exit_ = rows[exit_index]
    entry_raw = as_float(entry.get("Open"))
    exit_raw = as_float(exit_.get("Close"))
    if entry_raw is None or entry_raw <= 0 or exit_raw is None or exit_raw <= 0:
        return None, "bad_entry_or_exit_price"

    notional = float(CONFIG["paper_notional_usd"])
    entry_price = apply_entry_fill(entry_raw)
    exit_price = apply_slippage(exit_raw, SLIPPAGE_BPS_TARGET, "sell")
    pnl_pct_net = exit_price / entry_price - 1.0 - ROUND_TRIP_COST_PCT
    pnl = notional * pnl_pct_net
    spy_pnl = stock_pnl_from_dates(bars.get("SPY", []), entry["Date"], exit_["Date"], notional)
    qqq_pnl = stock_pnl_from_dates(bars.get("QQQ", []), entry["Date"], exit_["Date"], notional)

    put_call_volume_ratio = as_float(row.get("put_call_volume_ratio"))
    iv_skew = as_float(row.get("put_minus_call_volume_weighted_iv"))
    if put_call_volume_ratio is None or iv_skew is None:
        return None, "missing_skew_fields"

    settled = {
        **row,
        "entry_date": entry["Date"],
        "exit_date": exit_["Date"],
        "entry_price": round(entry_price, 4),
        "exit_price": round(exit_price, 4),
        "forward_10d_return_pct": round(pnl_pct_net, 6),
        "pnl": round(pnl, 2),
        "replacement_value_vs_cash_usd": round(pnl, 2),
        "replacement_value_vs_spy_usd": round(pnl - spy_pnl, 2) if spy_pnl is not None else None,
        "replacement_value_vs_qqq_usd": round(pnl - qqq_pnl, 2) if qqq_pnl is not None else None,
        "spy_same_window_pnl": round(spy_pnl, 2) if spy_pnl is not None else None,
        "qqq_same_window_pnl": round(qqq_pnl, 2) if qqq_pnl is not None else None,
        "paper_notional_usd": notional,
        "outcome_status": "closed_10d_forward",
        "entry_month": entry["Date"][:7],
        "put_call_volume_ratio": round(put_call_volume_ratio, 6),
        "put_minus_call_volume_weighted_iv": round(iv_skew, 6),
    }
    settled["quality_pass"] = quality_pass(settled)
    return settled, "closed"


def quality_pass(row: dict[str, Any]) -> bool:
    if as_float(row.get("pit_safe_contract_rate")) != 1.0:
        return False
    if (as_float(row.get("liquid_contract_rate")) or 0.0) < CONFIG["quality_min_liquid_contract_rate"]:
        return False
    if (as_float(row.get("avg_liquidity_score")) or 0.0) < CONFIG["quality_min_avg_liquidity_score"]:
        return False
    wide = as_float(row.get("wide_spread_contract_rate"))
    if wide is not None and wide > CONFIG["quality_max_wide_spread_contract_rate"]:
        return False
    if int(as_float(row.get("zero_bid_or_ask_count")) or 0) > CONFIG["quality_max_zero_bid_or_ask_count"]:
        return False
    return True


def percentile_map(rows: list[dict[str, Any]], field: str) -> dict[int, float]:
    pairs = sorted(
        (index, float(row[field]))
        for index, row in enumerate(rows)
        if as_float(row.get(field)) is not None
    )
    if len(pairs) <= 1:
        return {index: 0.5 for index, _value in pairs}
    out: dict[int, float] = {}
    start = 0
    while start < len(pairs):
        end = start + 1
        while end < len(pairs) and pairs[end][1] == pairs[start][1]:
            end += 1
        pct = ((start + end - 1) / 2) / (len(pairs) - 1)
        for offset in range(start, end):
            out[pairs[offset][0]] = pct
        start = end
    return out


def assign_bullish_scores(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    vol_pct = percentile_map(rows, "put_call_volume_ratio")
    iv_pct = percentile_map(rows, "put_minus_call_volume_weighted_iv")
    scored: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if index not in vol_pct or index not in iv_pct:
            continue
        score = ((1.0 - vol_pct[index]) + (1.0 - iv_pct[index])) / 2.0
        scored.append({**row, "bullish_option_skew_score": round(score, 6)})
    scored.sort(key=lambda item: (item["bullish_option_skew_score"], item["entry_date"], item["ticker"]))
    n = len(scored)
    for rank, row in enumerate(scored):
        if rank < n / 3:
            bucket = "low_bullish"
        elif rank < 2 * n / 3:
            bucket = "mid_bullish"
        else:
            bucket = "high_bullish"
        row["bullish_option_skew_bucket"] = bucket
    return scored


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


def concentration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_ticker: dict[str, float] = defaultdict(float)
    for row in rows:
        pnl = as_float(row.get("pnl"))
        if pnl is not None and pnl > 0:
            by_ticker[str(row.get("ticker"))] += pnl
    total = sum(by_ticker.values())
    if total <= 0:
        return {
            "positive_pnl": 0.0,
            "max_single_positive_pnl_share": None,
            "positive_pnl_hhi": None,
            "top_positive_tickers": [],
        }
    shares = {ticker: pnl / total for ticker, pnl in by_ticker.items()}
    return {
        "positive_pnl": round(total, 2),
        "max_single_positive_pnl_share": round(max(shares.values()), 6),
        "positive_pnl_hhi": round(sum(share * share for share in shares.values()), 6),
        "top_positive_tickers": [
            {"ticker": ticker, "pnl": round(pnl, 2), "share": round(shares[ticker], 6)}
            for ticker, pnl in sorted(by_ticker.items(), key=lambda item: item[1], reverse=True)[:8]
        ],
    }


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pnls = [float(row["pnl"]) for row in rows if as_float(row.get("pnl")) is not None]
    repl_spy = [
        float(row["replacement_value_vs_spy_usd"])
        for row in rows
        if as_float(row.get("replacement_value_vs_spy_usd")) is not None
    ]
    repl_qqq = [
        float(row["replacement_value_vs_qqq_usd"])
        for row in rows
        if as_float(row.get("replacement_value_vs_qqq_usd")) is not None
    ]
    scores = [
        float(row["bullish_option_skew_score"])
        for row in rows
        if as_float(row.get("bullish_option_skew_score")) is not None
    ]
    return {
        "n": len(rows),
        "mean_pnl": round_or_none(mean(pnls), 4),
        "median_pnl": round_or_none(median(pnls), 4) if pnls else None,
        "total_pnl": round_or_none(sum(pnls), 2) if pnls else 0.0,
        "win_rate": round(sum(1 for value in pnls if value > 0) / len(pnls), 6) if pnls else None,
        "mean_replacement_vs_spy": round_or_none(mean(repl_spy), 4),
        "mean_replacement_vs_qqq": round_or_none(mean(repl_qqq), 4),
        "median_replacement_vs_spy": round_or_none(median(repl_spy), 4) if repl_spy else None,
        "median_replacement_vs_qqq": round_or_none(median(repl_qqq), 4) if repl_qqq else None,
        "mean_bullish_score": round_or_none(mean(scores), 6),
        "ticker_count": len({row.get("ticker") for row in rows}),
        "entry_months": sorted({str(row.get("entry_month")) for row in rows}),
        "concentration": concentration(rows),
    }


def bucket_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for bucket in BUCKETS:
        out[bucket] = summarize_rows(
            [row for row in rows if row.get("bullish_option_skew_bucket") == bucket]
        )
    return out


def month_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for month in sorted({str(row.get("entry_month")) for row in rows}):
        month_rows = [row for row in rows if row.get("entry_month") == month]
        out[month] = {
            "all": summarize_rows(month_rows),
            "buckets": bucket_summary(month_rows),
        }
    return out


def monotonic_high_mid_low(summary: dict[str, Any], metric: str) -> bool:
    high = as_float(summary["high_bullish"].get(metric))
    mid = as_float(summary["mid_bullish"].get(metric))
    low = as_float(summary["low_bullish"].get(metric))
    return high is not None and mid is not None and low is not None and high > mid > low


def analyze(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored_all = assign_bullish_scores(rows)
    quality_rows = [row for row in scored_all if row.get("quality_pass")]
    xs = [float(row["bullish_option_skew_score"]) for row in quality_rows]
    y_cash = [float(row["replacement_value_vs_cash_usd"]) for row in quality_rows]
    y_spy = [
        float(row["replacement_value_vs_spy_usd"])
        for row in quality_rows
        if as_float(row.get("replacement_value_vs_spy_usd")) is not None
    ]
    xs_spy = [
        float(row["bullish_option_skew_score"])
        for row in quality_rows
        if as_float(row.get("replacement_value_vs_spy_usd")) is not None
    ]
    buckets = bucket_summary(quality_rows)
    months = month_summary(quality_rows)
    month_high_beats_low = 0
    month_high_positive = 0
    for month_payload in months.values():
        month_buckets = month_payload["buckets"]
        high = as_float(month_buckets["high_bullish"].get("mean_pnl"))
        low = as_float(month_buckets["low_bullish"].get("mean_pnl"))
        if high is not None and low is not None and high > low:
            month_high_beats_low += 1
        if high is not None and high > 0:
            month_high_positive += 1
    return {
        "all_closed_rows": summarize_rows(scored_all),
        "quality_rows": summarize_rows(quality_rows),
        "quality_bucket_summary": buckets,
        "quality_month_summary": months,
        "quality_month_count": len(months),
        "quality_month_high_beats_low_count": month_high_beats_low,
        "quality_month_high_positive_count": month_high_positive,
        "spearman_score_to_cash_replacement": spearman(xs, y_cash),
        "spearman_score_to_spy_replacement": spearman(xs_spy, y_spy),
        "sample_rows": quality_rows[:200],
    }


def build_settled_rows(ledger: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    bars = load_ohlcv_rows(ledger)
    settled: list[dict[str, Any]] = []
    skipped: dict[str, int] = defaultdict(int)
    for row in ledger:
        outcome, reason = settle_row(row, bars)
        if outcome is None:
            skipped[reason] += 1
            continue
        settled.append(outcome)
    return settled, {
        "source_ledger_rows": len(ledger),
        "loaded_ohlcv_tickers": len(bars),
        "warehouse_path": repo_rel(Path(DEFAULT_WAREHOUSE_PATH)),
        "settled_rows": len(settled),
        "skipped_reasons": dict(sorted(skipped.items())),
        "settled_date_range": {
            "entry_start": min((row["entry_date"] for row in settled), default=None),
            "entry_end": max((row["entry_date"] for row in settled), default=None),
            "exit_start": min((row["exit_date"] for row in settled), default=None),
            "exit_end": max((row["exit_date"] for row in settled), default=None),
        },
    }


def acceptance_checks(analysis: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    quality = analysis["quality_rows"]
    buckets = analysis["quality_bucket_summary"]
    conc = quality["concentration"]
    checks = {
        "closed_sample_min_passed": analysis["all_closed_rows"]["n"] >= CONFIG["min_closed_rows"],
        "quality_sample_min_passed": quality["n"] >= CONFIG["min_quality_rows"],
        "high_mean_cash_beats_low": (
            as_float(buckets["high_bullish"].get("mean_pnl"))
            is not None
            and as_float(buckets["low_bullish"].get("mean_pnl")) is not None
            and buckets["high_bullish"]["mean_pnl"] > buckets["low_bullish"]["mean_pnl"]
        ),
        "high_median_cash_beats_low": (
            as_float(buckets["high_bullish"].get("median_pnl"))
            is not None
            and as_float(buckets["low_bullish"].get("median_pnl")) is not None
            and buckets["high_bullish"]["median_pnl"] > buckets["low_bullish"]["median_pnl"]
        ),
        "high_mean_spy_beats_low": (
            as_float(buckets["high_bullish"].get("mean_replacement_vs_spy"))
            is not None
            and as_float(buckets["low_bullish"].get("mean_replacement_vs_spy")) is not None
            and buckets["high_bullish"]["mean_replacement_vs_spy"]
            > buckets["low_bullish"]["mean_replacement_vs_spy"]
        ),
        "high_mean_qqq_beats_low": (
            as_float(buckets["high_bullish"].get("mean_replacement_vs_qqq"))
            is not None
            and as_float(buckets["low_bullish"].get("mean_replacement_vs_qqq")) is not None
            and buckets["high_bullish"]["mean_replacement_vs_qqq"]
            > buckets["low_bullish"]["mean_replacement_vs_qqq"]
        ),
        "mean_cash_monotonic_high_mid_low": monotonic_high_mid_low(buckets, "mean_pnl"),
        "median_cash_monotonic_high_mid_low": monotonic_high_mid_low(buckets, "median_pnl"),
        "spearman_cash_positive": (
            analysis["spearman_score_to_cash_replacement"] is not None
            and analysis["spearman_score_to_cash_replacement"] > 0
        ),
        "spearman_spy_positive": (
            analysis["spearman_score_to_spy_replacement"] is not None
            and analysis["spearman_score_to_spy_replacement"] > 0
        ),
        "concentration_passed": (
            conc["max_single_positive_pnl_share"] is not None
            and conc["max_single_positive_pnl_share"] <= CONFIG["max_single_positive_pnl_share"]
        ),
        "at_least_two_months_high_beats_low": analysis["quality_month_high_beats_low_count"] >= 2,
        "at_least_two_months_high_positive": analysis["quality_month_high_positive_count"] >= 2,
    }
    failed: list[str] = []
    for key, value in checks.items():
        if not value:
            failed.append(key.replace("_passed", "_failed"))
    return checks, failed


def calibration(prediction: dict[str, Any], decision_passed: bool, failed: list[str]) -> dict[str, Any]:
    predicted = float(prediction.get("success_probability") or 0.0)
    actual = 1 if decision_passed else 0
    predicted_modes = prediction.get("main_failure_modes") or []
    return {
        "actual_success": actual,
        "actual_decision": (
            "observed_only_positive_options_skew_lead_not_promoted"
            if decision_passed
            else "rejected_no_monotonic_options_forward_skew_edge"
        ),
        "predicted_success_probability": predicted,
        "brier_score": round((predicted - actual) ** 2, 6),
        "predicted_failure_modes": predicted_modes,
        "realized_failure_modes": failed,
        "predicted_failure_mode_hit": bool(
            set(predicted_modes).intersection(failed)
            or ("no_monotonic_separation" in predicted_modes and any("monotonic" in item for item in failed))
        ),
        "surprise_note": (
            "Closed options rows passed the observed-only monotonic screen but remain non-promoted."
            if decision_passed
            else "Closed options rows did not show robust monotonic separation; this matches the low-confidence, quality-caveat prediction."
        ),
    }


def build_payload() -> dict[str, Any]:
    prediction = load_ticket_prediction()
    baseline = load_baseline_metrics()
    ledger = load_source_ledger()
    settled_rows, settlement_audit = build_settled_rows(ledger)
    if settled_rows:
        analysis = analyze(settled_rows)
        checks, failed = acceptance_checks(analysis)
    else:
        analysis = {
            "all_closed_rows": summarize_rows([]),
            "quality_rows": summarize_rows([]),
            "quality_bucket_summary": bucket_summary([]),
            "quality_month_summary": {},
            "quality_month_count": 0,
            "quality_month_high_beats_low_count": 0,
            "quality_month_high_positive_count": 0,
            "spearman_score_to_cash_replacement": None,
            "spearman_score_to_spy_replacement": None,
            "sample_rows": [],
        }
        checks = {
            "closed_sample_min_passed": False,
            "quality_sample_min_passed": False,
        }
        failed = ["closed_sample_too_small"]

    observed_lead = not failed
    status = "observed_only_positive_lead" if observed_lead else "observed_only_rejected"
    decision = (
        "observed_only_positive_options_skew_lead_not_promoted"
        if observed_lead
        else "rejected_no_monotonic_options_forward_skew_edge"
    )
    now = utc_now()
    why = (
        "The fixed call-led / low-put-protection score separated closed forward "
        "options rows across cash and ETF replacement-value checks, but no "
        "strategy or helper was promoted."
        if observed_lead
        else "The closed forward options rows did not show enough monotonic "
        "replacement-value separation. The ledger is usable for observation, "
        "but current vendor-asof caveats, spread/zero-bid quality flags, and "
        "mega-cap option-flow noise are not yet a tradeable confirmation edge."
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
        "new_evidence_type": "closed_forward_replacement_value_rows",
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "exp-20260617-004": "Blocked options alpha because canonical-window PIT options coverage was missing.",
                "exp-20260618-023": "Blocked options-skew leadership confirmation for the same coverage reason and named 20-30 closed forward rows as valid new evidence.",
                "exp-20260623-009": "Accepted measurement repair created the forward options observation ledger but left outcomes pending.",
                "novelty_gate": "Reservation recorded no blocking near-neighbor and stored the closed-forward replacement-value new evidence axis.",
            },
            "3_single_policy_bundle": (
                "A fixed observed-only attribution: settle exp009 options ledger "
                "rows for 10 trading days, score lower put/call volume ratio and "
                "lower put-minus-call IV as more bullish, bucket into tertiles, "
                "and test monotonic cash/SPY/QQQ replacement value. No trading "
                "policy changes."
            ),
            "4_success_failure_standard": (
                "Observed-only lead only if closed and quality samples are >=30, "
                "high bullish bucket beats low on mean/median cash PnL and mean "
                "SPY/QQQ replacement value, cash mean/median are high>mid>low, "
                "Spearman is positive, concentration passes, and at least two "
                "entry-month cohorts support the high bucket."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "source_ledger": repo_rel(SOURCE_LEDGER),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "warehouse_path": repo_rel(Path(DEFAULT_WAREHOUSE_PATH)),
            "config": CONFIG,
            "score_definition": (
                "bullish_option_skew_score = average percentile of low "
                "put_call_volume_ratio and low put_minus_call_volume_weighted_iv"
            ),
            "bucket_method": "tertiles on bullish_option_skew_score within settled rows",
        },
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_metrics": baseline,
            "note": "Observed-only attribution; before and after policy are identical.",
        },
        "gate2": {
            "dependencies_validated": SOURCE_LEDGER.exists() and settlement_audit["settled_rows"] > 0,
            "source_ledger_exists": SOURCE_LEDGER.exists(),
            "source_ledger_rows": settlement_audit["source_ledger_rows"],
            "settled_rows": settlement_audit["settled_rows"],
            "quality_rows": analysis["quality_rows"]["n"],
            "fields_checked": [
                "usable_trade_date",
                "entry_date",
                "exit_date",
                "put_call_volume_ratio",
                "put_minus_call_volume_weighted_iv",
                "replacement_value_vs_cash_usd",
                "replacement_value_vs_spy_usd",
                "replacement_value_vs_qqq_usd",
            ],
            "entry_date_present": all(bool(row.get("entry_date")) for row in settled_rows),
            "target_price_relevance": (
                "Not applicable: this is observed-only 10-trading-day outcome "
                "attribution and does not schedule target exits or orders."
            ),
            "settlement_audit": settlement_audit,
        },
        "gate3": {
            "filter_added": False,
            "signals_generated": settlement_audit["source_ledger_rows"],
            "signals_survived": settlement_audit["settled_rows"],
            "survival_rate": round(
                settlement_audit["settled_rows"] / settlement_audit["source_ledger_rows"],
                4,
            )
            if settlement_audit["source_ledger_rows"]
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
                "Forward-only observations, not canonical fixed-window PIT options coverage.",
                "No shared helper or daily adapter promoted.",
                "Vendor-asof is missing and open-interest same-day usability remains false.",
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
            "settlement_audit": settlement_audit,
            "analysis": analysis,
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
            "uses_onclickmedia_options": True,
            "forward_only_not_fixed_window_pit_coverage": True,
            "live_realistic_execution_envelope": (
                "Not evaluated for live use; this is observed-only attribution "
                "and cannot become live-ready."
            ),
        },
        "calibration": calibration(prediction, observed_lead, failed),
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retry options put/call ratio, IV skew, open interest, "
                "volume, expiration, moneyness, top-N, hold, cooldown, or "
                "notional thresholds on this forward ledger. It now has closed "
                "outcomes, and the fixed monotonic screen is the attribution result."
            ),
            "new_evidence_required": (
                "A valid options retry needs materially more closed forward rows "
                "with replacement value, PIT vendor/asof controls, borrow or "
                "loan-availability context, or historical PIT options chains "
                "covering the canonical windows."
            ),
        },
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "related_files": [
            RUNNER,
            repo_rel(SOURCE_LEDGER),
            repo_rel(BASELINE_RESULT),
            "experiments/logs/exp-20260617-004.json",
            "experiments/logs/exp-20260618-023.json",
            "experiments/logs/exp-20260623-009.json",
        ],
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    analysis = payload["attribution"]["analysis"]
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
            "settlement_audit": payload["gate2"]["settlement_audit"],
        },
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "attribution": {
            "all_closed_rows": analysis["all_closed_rows"],
            "quality_rows": analysis["quality_rows"],
            "quality_bucket_summary": analysis["quality_bucket_summary"],
            "quality_month_count": analysis["quality_month_count"],
            "quality_month_high_beats_low_count": analysis["quality_month_high_beats_low_count"],
            "spearman_score_to_cash_replacement": analysis["spearman_score_to_cash_replacement"],
            "spearman_score_to_spy_replacement": analysis["spearman_score_to_spy_replacement"],
        },
        "production_impact": payload["production_impact"],
        "calibration": payload["calibration"],
        "post_run_reflection": payload["post_run_reflection"],
        "related_files": payload["related_files"],
        "anti_js": payload["anti_js"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
    }


def money(value: Any) -> str:
    number = as_float(value)
    return "n/a" if number is None else f"${number:,.2f}"


def build_card(payload: dict[str, Any]) -> str:
    analysis = payload["attribution"]["analysis"]
    buckets = analysis["quality_bucket_summary"]
    rows = [
        "| Bucket | Rows | Mean PnL | Median PnL | Mean vs SPY | Mean vs QQQ | Win Rate |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for bucket_name in BUCKETS:
        bucket = buckets[bucket_name]
        win = bucket["win_rate"]
        rows.append(
            "| {name} | {n} | {mean_pnl} | {median_pnl} | {spy} | {qqq} | {win} |".format(
                name=bucket_name,
                n=bucket["n"],
                mean_pnl=money(bucket["mean_pnl"]),
                median_pnl=money(bucket["median_pnl"]),
                spy=money(bucket["mean_replacement_vs_spy"]),
                qqq=money(bucket["mean_replacement_vs_qqq"]),
                win="n/a" if win is None else f"{win:.2%}",
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: options closed-forward skew attribution",
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
            "## Quality Buckets",
            "",
            *rows,
            "",
            f"- Closed rows: `{analysis['all_closed_rows']['n']}`",
            f"- Quality rows: `{analysis['quality_rows']['n']}`",
            f"- Spearman(score, cash replacement): `{analysis['spearman_score_to_cash_replacement']}`",
            f"- Spearman(score, SPY replacement): `{analysis['spearman_score_to_spy_replacement']}`",
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
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "attribution": {
            "all_closed_rows": payload["attribution"]["analysis"]["all_closed_rows"],
            "quality_rows": payload["attribution"]["analysis"]["quality_rows"],
            "quality_bucket_summary": payload["attribution"]["analysis"]["quality_bucket_summary"],
            "spearman_score_to_cash_replacement": payload["attribution"]["analysis"][
                "spearman_score_to_cash_replacement"
            ],
        },
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
            "implementation_mode": payload["implementation_mode"],
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
            "related_files": payload["related_files"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    analysis = payload["attribution"]["analysis"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "closed_rows": analysis["all_closed_rows"]["n"],
                "quality_rows": analysis["quality_rows"]["n"],
                "spearman_cash": analysis["spearman_score_to_cash_replacement"],
                "bucket_summary": analysis["quality_bucket_summary"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
