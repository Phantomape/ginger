"""Backfill candidate-day options data and build a default-off overlay report.

This script is deliberately shadow-only. It captures existing backtester entry
candidate events, pulls OnclickMedia option chains for those ticker/date pairs,
summarizes option structure, and compares forward returns for tagged versus
untagged candidates. It does not change Ginger production logic.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
import backtester as backtester_module  # noqa: E402
from data_layer import get_universe  # noqa: E402
from options_onclickmedia import (  # noqa: E402
    DEFAULT_MAX_EXPIRATIONS,
    DEFAULT_MAX_STRIKES_PER_SIDE,
    DEFAULT_REQUEST_SLEEP_SECONDS,
    build_ticker_date_rows,
    normalize_ticker,
)


EXPERIMENT_ID = "exp-20260506-009"
WINDOWS = [
    {
        "label": "late_strong",
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
    },
    {
        "label": "mid_weak",
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
    },
    {
        "label": "old_thin",
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
    },
]


def _repo_path(path: str | Path) -> Path:
    value = Path(path)
    if value.is_absolute():
        return value
    return REPO_ROOT / value


def _repo_rel(path: str | Path) -> str:
    value = _repo_path(path)
    try:
        return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(value).replace("\\", "/")


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _json_default(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    target = _repo_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True, default=_json_default) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    target = _repo_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, default=_json_default) + "\n")


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    source = _repo_path(path)
    if not source.exists():
        return []
    rows = []
    for line in source.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _load_ohlcv_snapshot(path: str | Path) -> dict[str, list[dict[str, Any]]]:
    payload = json.loads(_repo_path(path).read_text(encoding="utf-8"))
    ohlcv = payload.get("ohlcv", payload)
    out: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in ohlcv.items():
        if not isinstance(rows, list):
            continue
        clean = []
        for row in rows:
            if isinstance(row, dict) and row.get("Date"):
                clean.append(row)
        out[normalize_ticker(ticker)] = sorted(clean, key=lambda row: row["Date"])
    return out


def _row_float(row: dict[str, Any], key: str) -> float | None:
    try:
        value = row.get(key)
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _date_index(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {str(row.get("Date"))[:10]: idx for idx, row in enumerate(rows)}


def _forward_stats(
    ohlcv_rows: list[dict[str, Any]],
    signal_date: str,
    horizons: tuple[int, ...] = (5, 10, 20, 60),
) -> dict[str, Any]:
    index = _date_index(ohlcv_rows)
    if signal_date not in index:
        return {
            "forward_returns": {f"{h}d": None for h in horizons},
            "future_drawdown_20d": None,
            "future_realized_vol_20d": None,
            "entry_close": None,
        }
    start_idx = index[signal_date]
    entry_close = _row_float(ohlcv_rows[start_idx], "Close")
    if not entry_close:
        return {
            "forward_returns": {f"{h}d": None for h in horizons},
            "future_drawdown_20d": None,
            "future_realized_vol_20d": None,
            "entry_close": None,
        }

    returns: dict[str, float | None] = {}
    for horizon in horizons:
        target_idx = start_idx + horizon
        if target_idx >= len(ohlcv_rows):
            returns[f"{horizon}d"] = None
            continue
        future_close = _row_float(ohlcv_rows[target_idx], "Close")
        returns[f"{horizon}d"] = (
            round(future_close / entry_close - 1.0, 6)
            if future_close is not None else None
        )

    end_idx = min(len(ohlcv_rows) - 1, start_idx + 20)
    future_slice = ohlcv_rows[start_idx + 1 : end_idx + 1]
    lows = [_row_float(row, "Low") for row in future_slice]
    lows = [value for value in lows if value is not None]
    drawdown = round(min(lows) / entry_close - 1.0, 6) if lows else None

    daily_returns = []
    prev = entry_close
    for row in future_slice:
        close = _row_float(row, "Close")
        if close is not None and prev:
            daily_returns.append(close / prev - 1.0)
            prev = close
    realized_vol = (
        round(statistics.pstdev(daily_returns) * math.sqrt(252), 6)
        if len(daily_returns) >= 2 else None
    )
    return {
        "forward_returns": returns,
        "future_drawdown_20d": drawdown,
        "future_realized_vol_20d": realized_vol,
        "entry_close": round(entry_close, 6),
    }


def _capture_window_candidates(window: dict[str, str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    captured: list[dict[str, Any]] = []
    original = backtester_module._summarize_entry_decision_events

    def capture(events):
        captured.extend(dict(event) for event in (events or []))
        return original(events)

    backtester_module._summarize_entry_decision_events = capture
    try:
        engine = BacktestEngine(
            get_universe(),
            start=window["start"],
            end=window["end"],
            config={
                "REGIME_AWARE_EXIT": True,
                "REPLAY_PARTIAL_REDUCES": True,
            },
            ohlcv_snapshot_path=str(_repo_path(window["snapshot"])),
        )
        result = engine.run()
    finally:
        backtester_module._summarize_entry_decision_events = original

    out = []
    seen = set()
    for event in captured:
        ticker = normalize_ticker(event.get("ticker"))
        event_date = str(event.get("date") or "")[:10]
        if not ticker or not event_date:
            continue
        key = (
            window["label"],
            event_date,
            ticker,
            event.get("strategy"),
            event.get("decision"),
            event.get("candidate_rank"),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "window": window["label"],
            "date": event_date,
            "ticker": ticker,
            "strategy": event.get("strategy"),
            "decision": event.get("decision"),
            "candidate_rank": event.get("candidate_rank"),
            "available_slots_at_entry_loop": event.get("available_slots_at_entry_loop"),
            "details": event.get("details") or {},
        })
    return result, out


def _nearest_by_delta(rows: list[dict[str, Any]], target_delta: float) -> dict[str, Any] | None:
    with_delta = [row for row in rows if row.get("delta") is not None and row.get("implied_vol") is not None]
    if not with_delta:
        return None
    return min(with_delta, key=lambda row: abs(float(row["delta"]) - target_delta))


def _atm_iv(rows: list[dict[str, Any]], underlying_price: float | None) -> float | None:
    if underlying_price is None:
        return None
    candidates = [row for row in rows if row.get("strike") is not None and row.get("implied_vol") is not None]
    if not candidates:
        return None
    nearest = min(candidates, key=lambda row: abs(float(row["strike"]) - underlying_price))
    return round(float(nearest["implied_vol"]), 6)


def summarize_option_structure(rows: list[dict[str, Any]], underlying_price: float | None) -> dict[str, Any]:
    if not rows:
        return {
            "options_rows": 0,
            "option_liquidity_pass_rows": 0,
            "has_options_coverage": False,
        }

    calls = [row for row in rows if row.get("call_put") == "call"]
    puts = [row for row in rows if row.get("call_put") == "put"]
    call_volume = sum(int(row.get("volume") or 0) for row in calls)
    put_volume = sum(int(row.get("volume") or 0) for row in puts)
    call_oi = sum(int(row.get("open_interest") or 0) for row in calls)
    put_oi = sum(int(row.get("open_interest") or 0) for row in puts)
    liquid_rows = [row for row in rows if row.get("option_liquidity_pass")]
    expiries = sorted({row.get("expiry") for row in rows if row.get("expiry")})

    call_concentration = (
        round(max(int(row.get("open_interest") or 0) for row in calls) / call_oi, 6)
        if call_oi and calls else None
    )
    put_concentration = (
        round(max(int(row.get("open_interest") or 0) for row in puts) / put_oi, 6)
        if put_oi and puts else None
    )

    near_expiry = expiries[0] if expiries else None
    far_expiry = expiries[-1] if len(expiries) >= 2 else None
    near_rows = [row for row in rows if row.get("expiry") == near_expiry]
    far_rows = [row for row in rows if row.get("expiry") == far_expiry]
    near_call_25 = _nearest_by_delta([row for row in near_rows if row.get("call_put") == "call"], 0.25)
    near_put_25 = _nearest_by_delta([row for row in near_rows if row.get("call_put") == "put"], -0.25)
    skew_25delta = None
    if near_call_25 and near_put_25:
        skew_25delta = round(float(near_put_25["implied_vol"]) - float(near_call_25["implied_vol"]), 6)

    near_atm_iv = _atm_iv(near_rows, underlying_price)
    far_atm_iv = _atm_iv(far_rows, underlying_price) if far_expiry else None
    term_structure_slope = (
        round(far_atm_iv - near_atm_iv, 6)
        if far_atm_iv is not None and near_atm_iv is not None else None
    )

    put_call_volume_ratio = (
        round(put_volume / call_volume, 6) if call_volume else None
    )
    put_call_oi_ratio = round(put_oi / call_oi, 6) if call_oi else None
    call_structure_support = bool(
        len(liquid_rows) >= 10
        and call_oi > put_oi
        and (call_concentration or 0.0) >= 0.12
    )
    downside_structure_risk = bool(
        len(liquid_rows) >= 10
        and (
            (put_call_oi_ratio is not None and put_call_oi_ratio >= 1.25)
            or (skew_25delta is not None and skew_25delta >= 0.05)
        )
    )
    return {
        "options_rows": len(rows),
        "option_liquidity_pass_rows": len(liquid_rows),
        "option_liquidity_pass_rate": round(len(liquid_rows) / len(rows), 6),
        "has_options_coverage": True,
        "expiry_count": len(expiries),
        "expiries": expiries,
        "call_volume": call_volume,
        "put_volume": put_volume,
        "call_open_interest": call_oi,
        "put_open_interest": put_oi,
        "put_call_volume_ratio": put_call_volume_ratio,
        "put_call_oi_ratio": put_call_oi_ratio,
        "call_oi_concentration": call_concentration,
        "put_oi_concentration": put_concentration,
        "near_atm_iv": near_atm_iv,
        "far_atm_iv": far_atm_iv,
        "term_structure_slope": term_structure_slope,
        "skew_25delta_approx": skew_25delta,
        "call_structure_support": call_structure_support,
        "downside_structure_risk": downside_structure_risk,
        "pit_safe_rows": sum(1 for row in rows if row.get("pit_safe")),
        "pit_unsafe_rows": sum(1 for row in rows if not row.get("pit_safe")),
    }


def _mean(values: list[float | None]) -> float | None:
    clean = [value for value in values if value is not None]
    return round(sum(clean) / len(clean), 6) if clean else None


def _win_rate(values: list[float | None]) -> float | None:
    clean = [value for value in values if value is not None]
    return round(sum(1 for value in clean if value > 0) / len(clean), 6) if clean else None


def _bucket_metrics(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "count": len(candidates),
        "forward_5d_mean": _mean([c.get("forward_returns", {}).get("5d") for c in candidates]),
        "forward_10d_mean": _mean([c.get("forward_returns", {}).get("10d") for c in candidates]),
        "forward_20d_mean": _mean([c.get("forward_returns", {}).get("20d") for c in candidates]),
        "forward_60d_mean": _mean([c.get("forward_returns", {}).get("60d") for c in candidates]),
        "forward_20d_win_rate": _win_rate([c.get("forward_returns", {}).get("20d") for c in candidates]),
        "future_drawdown_20d_mean": _mean([c.get("future_drawdown_20d") for c in candidates]),
        "future_realized_vol_20d_mean": _mean([c.get("future_realized_vol_20d") for c in candidates]),
    }


def _slot_conflict_value(candidates: list[dict[str, Any]], tag_key: str) -> dict[str, Any]:
    by_day: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        by_day[(candidate["window"], candidate["date"])].append(candidate)

    diffs = []
    conflicts = []
    for (window, day), rows in by_day.items():
        entered = [
            row for row in rows
            if row.get("decision") == "entered"
            and row.get("forward_returns", {}).get("20d") is not None
        ]
        tagged_skipped = [
            row for row in rows
            if row.get("decision") != "entered"
            and row.get(tag_key)
            and row.get("forward_returns", {}).get("20d") is not None
        ]
        if not entered or not tagged_skipped:
            continue
        entered_mean = _mean([row["forward_returns"]["20d"] for row in entered])
        for row in tagged_skipped:
            diff = round(row["forward_returns"]["20d"] - entered_mean, 6)
            diffs.append(diff)
            conflicts.append({
                "window": window,
                "date": day,
                "ticker": row.get("ticker"),
                "strategy": row.get("strategy"),
                "decision": row.get("decision"),
                "tag": tag_key,
                "candidate_forward_20d": row["forward_returns"]["20d"],
                "same_day_entered_forward_20d_mean": entered_mean,
                "slot_conflict_value_20d": diff,
            })
    return {
        "conflict_count": len(conflicts),
        "avg_slot_conflict_value_20d": _mean(diffs),
        "positive_conflict_fraction": _win_rate(diffs),
        "examples": conflicts[:20],
    }


def _overlay_summary(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    covered = [row for row in candidates if row.get("has_options_coverage")]
    uncovered = [row for row in candidates if not row.get("has_options_coverage")]
    call_support = [row for row in candidates if row.get("call_structure_support")]
    no_call_support = [
        row for row in candidates
        if row.get("has_options_coverage") and not row.get("call_structure_support")
    ]
    downside = [row for row in candidates if row.get("downside_structure_risk")]
    no_downside = [
        row for row in candidates
        if row.get("has_options_coverage") and not row.get("downside_structure_risk")
    ]

    return {
        "candidate_count": len(candidates),
        "options_covered_candidates": len(covered),
        "options_candidate_coverage_rate": (
            round(len(covered) / len(candidates), 6) if candidates else 0.0
        ),
        "entered_count": sum(1 for row in candidates if row.get("decision") == "entered"),
        "skipped_count": sum(1 for row in candidates if row.get("decision") != "entered"),
        "options_covered_entered_count": sum(1 for row in covered if row.get("decision") == "entered"),
        "options_covered_skipped_count": sum(1 for row in covered if row.get("decision") != "entered"),
        "all_candidates": _bucket_metrics(candidates),
        "options_covered": _bucket_metrics(covered),
        "options_uncovered": _bucket_metrics(uncovered),
        "call_structure_support": _bucket_metrics(call_support),
        "no_call_structure_support": _bucket_metrics(no_call_support),
        "downside_structure_risk": _bucket_metrics(downside),
        "no_downside_structure_risk": _bucket_metrics(no_downside),
        "call_support_minus_no_call_support_forward_20d": (
            round(
                (_bucket_metrics(call_support).get("forward_20d_mean") or 0.0)
                - (_bucket_metrics(no_call_support).get("forward_20d_mean") or 0.0),
                6,
            )
            if call_support and no_call_support else None
        ),
        "downside_minus_no_downside_forward_20d": (
            round(
                (_bucket_metrics(downside).get("forward_20d_mean") or 0.0)
                - (_bucket_metrics(no_downside).get("forward_20d_mean") or 0.0),
                6,
            )
            if downside and no_downside else None
        ),
        "slot_conflict": {
            "call_structure_support": _slot_conflict_value(candidates, "call_structure_support"),
            "downside_structure_risk": _slot_conflict_value(candidates, "downside_structure_risk"),
        },
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=f"data/experiments/{EXPERIMENT_ID}")
    parser.add_argument("--refresh-options", action="store_true")
    parser.add_argument("--max-expirations", type=int, default=DEFAULT_MAX_EXPIRATIONS)
    parser.add_argument("--max-strikes-per-side", type=int, default=DEFAULT_MAX_STRIKES_PER_SIDE)
    parser.add_argument("--sleep-seconds", type=float, default=DEFAULT_REQUEST_SLEEP_SECONDS)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--limit-candidate-days", type=int, default=None)
    return parser


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = build_arg_parser().parse_args(argv)
    output_dir = _repo_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    chain_path = output_dir / "options_candidate_chain.jsonl"
    candidates_path = output_dir / "options_candidate_overlay_rows.jsonl"
    report_path = output_dir / "options_overlay_shadow_report.json"

    all_candidates: list[dict[str, Any]] = []
    baseline_metrics: dict[str, Any] = {}
    ohlcv_by_window: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for window in WINDOWS:
        result, candidates = _capture_window_candidates(window)
        benchmarks = result.get("benchmarks") or {}
        baseline_metrics[window["label"]] = {
            "expected_value_score": result.get("expected_value_score"),
            "total_return_pct": benchmarks.get("strategy_total_return_pct"),
            "total_pnl": result.get("total_pnl"),
            "sharpe_daily": result.get("sharpe_daily"),
            "max_drawdown_pct": result.get("max_drawdown_pct"),
            "win_rate": result.get("win_rate"),
            "trade_count": result.get("total_trades"),
            "signals_generated": result.get("signals_generated"),
            "signals_survived": result.get("signals_survived"),
            "survival_rate": result.get("survival_rate"),
            "vs_spy_pct": benchmarks.get("strategy_vs_spy_pct"),
            "vs_qqq_pct": benchmarks.get("strategy_vs_qqq_pct"),
        }
        ohlcv = _load_ohlcv_snapshot(window["snapshot"])
        ohlcv_by_window[window["label"]] = ohlcv
        for candidate in candidates:
            ticker_rows = ohlcv.get(candidate["ticker"], [])
            forward = _forward_stats(ticker_rows, candidate["date"])
            candidate.update(forward)
        all_candidates.extend(candidates)

    unique_pairs = []
    seen_pairs = set()
    for candidate in all_candidates:
        key = (candidate["ticker"], candidate["date"])
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        unique_pairs.append(key)
    if args.limit_candidate_days:
        unique_pairs = unique_pairs[: args.limit_candidate_days]

    existing_rows = _read_jsonl(chain_path)
    rows_by_pair: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in existing_rows:
        rows_by_pair[(normalize_ticker(row.get("ticker")), str(row.get("date"))[:10])].append(row)

    fetched_rows = list(existing_rows)
    fetch_errors = []
    for ticker, day in unique_pairs:
        if rows_by_pair.get((ticker, day)) and not args.refresh_options:
            continue
        window_label = next(
            (candidate["window"] for candidate in all_candidates if candidate["ticker"] == ticker and candidate["date"] == day),
            None,
        )
        ohlcv_rows = ohlcv_by_window.get(window_label, {}).get(ticker, [])
        idx = _date_index(ohlcv_rows).get(day)
        underlying_price = _row_float(ohlcv_rows[idx], "Close") if idx is not None else None
        rows, stats = build_ticker_date_rows(
            ticker=ticker,
            quote_date=_parse_date(day),
            underlying_price=underlying_price,
            max_expirations=args.max_expirations,
            max_strikes_per_side=args.max_strikes_per_side,
            collection_mode="historical_backfill",
            fetch_kwargs={
                "refresh": args.refresh_options,
                "sleep_seconds": args.sleep_seconds,
                "timeout": args.timeout,
            },
        )
        for row in rows:
            row["experiment_id"] = EXPERIMENT_ID
        rows_by_pair[(ticker, day)] = rows
        fetched_rows.extend(rows)
        fetch_errors.extend(stats.get("errors", []))

    deduped_rows = {}
    for row in fetched_rows:
        key = (
            row.get("ticker"),
            row.get("date"),
            row.get("expiry"),
            row.get("call_put"),
            row.get("strike"),
        )
        deduped_rows[key] = row
    chain_rows = list(deduped_rows.values())
    _write_jsonl(chain_path, chain_rows)
    rows_by_pair = defaultdict(list)
    for row in chain_rows:
        rows_by_pair[(normalize_ticker(row.get("ticker")), str(row.get("date"))[:10])].append(row)

    enriched_candidates = []
    for candidate in all_candidates:
        option_rows = rows_by_pair.get((candidate["ticker"], candidate["date"]), [])
        option_summary = summarize_option_structure(option_rows, candidate.get("entry_close"))
        enriched = {
            **candidate,
            "option_summary": option_summary,
            "has_options_coverage": option_summary.get("has_options_coverage", False),
            "call_structure_support": option_summary.get("call_structure_support", False),
            "downside_structure_risk": option_summary.get("downside_structure_risk", False),
            "pit_safe": False,
            "pit_caveat": "Historical OnclickMedia rows lack vendor_asof metadata; report is shadow-only.",
        }
        enriched_candidates.append(enriched)
    _write_jsonl(candidates_path, enriched_candidates)

    covered = [row for row in enriched_candidates if row.get("has_options_coverage")]
    uncovered = [row for row in enriched_candidates if not row.get("has_options_coverage")]
    call_support = [row for row in enriched_candidates if row.get("call_structure_support")]
    no_call_support = [
        row for row in enriched_candidates
        if row.get("has_options_coverage") and not row.get("call_structure_support")
    ]
    downside = [row for row in enriched_candidates if row.get("downside_structure_risk")]
    no_downside = [
        row for row in enriched_candidates
        if row.get("has_options_coverage") and not row.get("downside_structure_risk")
    ]

    by_window_overlay = {
        window["label"]: _overlay_summary(
            [row for row in enriched_candidates if row.get("window") == window["label"]]
        )
        for window in WINDOWS
    }
    aggregate_overlay = _overlay_summary(enriched_candidates)

    report = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hypothesis": "Options structure may add overlay value to existing Ginger candidates after candidate-day backfill.",
        "mechanism_family": "eod_options_structure_overlay",
        "single_causal_variable": "onclickmedia_options_candidate_day_shadow_overlay",
        "baseline_metrics": baseline_metrics,
        "candidate_count": len(enriched_candidates),
        "unique_candidate_ticker_dates": len(unique_pairs),
        "candidate_tickers": sorted({row["ticker"] for row in enriched_candidates}),
        "options_chain_rows": len(chain_rows),
        "options_covered_candidates": len(covered),
        "options_candidate_coverage_rate": round(len(covered) / len(enriched_candidates), 6) if enriched_candidates else 0.0,
        "fetch_error_count": len(fetch_errors),
        "fetch_errors": fetch_errors[:100],
        "shadow_metrics": aggregate_overlay,
        "shadow_metrics_by_window": by_window_overlay,
        "candidate_overlap_and_slot_value": {
            "entered_count": sum(1 for row in enriched_candidates if row.get("decision") == "entered"),
            "skipped_count": sum(1 for row in enriched_candidates if row.get("decision") != "entered"),
            "options_covered_entered_count": sum(1 for row in covered if row.get("decision") == "entered"),
            "options_covered_skipped_count": sum(1 for row in covered if row.get("decision") != "entered"),
            "call_structure_support_slot_conflict": _slot_conflict_value(enriched_candidates, "call_structure_support"),
            "downside_structure_risk_slot_conflict": _slot_conflict_value(enriched_candidates, "downside_structure_risk"),
        },
        "pit_status": {
            "historical_rows_pit_safe": False,
            "pit_safe_rows": sum(1 for row in chain_rows if row.get("pit_safe")),
            "pit_unsafe_rows": sum(1 for row in chain_rows if not row.get("pit_safe")),
            "reason": "OnclickMedia historical rows do not expose vendor publication/as-of metadata.",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "production_signal_path_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "scope": "shadow_report_only",
        },
        "decision": "shadow_only",
        "output_files": {
            "options_chain": _repo_rel(chain_path),
            "candidate_rows": _repo_rel(candidates_path),
            "report": _repo_rel(report_path),
        },
    }
    _write_json(report_path, report)
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True, default=_json_default))
    return report


if __name__ == "__main__":
    main()
