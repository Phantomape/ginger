"""Lookahead diagnostics for skipped entry candidates.

This module is observation-only. It joins entry_execution_attribution skip
samples with future OHLCV highs to estimate which skip reasons deserve deeper
audit. It must not be used as a tradable rule.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

try:
    from constants import ROUND_TRIP_COST_PCT
except Exception:  # pragma: no cover
    ROUND_TRIP_COST_PCT = 0.0035


def _load_json(path):
    with Path(path).open(encoding="utf-8") as f:
        return json.load(f)


def infer_snapshot_path(backtest_result):
    known = backtest_result.get("known_biases") or {}
    source = known.get("ohlcv_source") or {}
    return source.get("snapshot_path")


def _ohlcv_rows_by_date(snapshot):
    rows_by_ticker = {}
    for ticker, rows in (snapshot.get("ohlcv") or {}).items():
        rows_by_ticker[ticker.upper()] = {
            row.get("Date"): row
            for row in rows or []
            if row.get("Date")
        }
    return rows_by_ticker


def _next_rows_after(rows_by_date, signal_date, horizon_days):
    dates = sorted(rows_by_date)
    eligible = [day for day in dates if day > signal_date]
    return [rows_by_date[day] for day in eligible[:horizon_days]]


def _rows_until(rows_by_date, date_str):
    return [
        rows_by_date[day]
        for day in sorted(rows_by_date)
        if day <= date_str
    ]


def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pct_change(start, end):
    if start is None or end is None or start == 0:
        return None
    return (end / start) - 1


def _median(values):
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def _context_for_gap(rows_by_ticker, ticker, signal_date):
    rows_by_date = rows_by_ticker.get((ticker or "").upper()) or {}
    prior = _rows_until(rows_by_date, signal_date)
    if not prior:
        return {}
    current = prior[-1]
    close = _safe_float(current.get("Close"))
    volume = _safe_float(current.get("Volume"))

    def close_n_days_back(n):
        if len(prior) <= n:
            return None
        return _safe_float(prior[-1 - n].get("Close"))

    prior20 = prior[-20:]
    prior252 = prior[-252:]
    high20 = max((_safe_float(row.get("High")) or 0 for row in prior20), default=0)
    high252 = max((_safe_float(row.get("High")) or 0 for row in prior252), default=0)
    prior_5d_return = _pct_change(close_n_days_back(5), close)
    prior_10d_return = _pct_change(close_n_days_back(10), close)
    vol20 = [
        _safe_float(row.get("Volume"))
        for row in prior20
        if _safe_float(row.get("Volume")) is not None
    ]

    return {
        "prior_5d_return_pct": (
            round(prior_5d_return, 6)
            if prior_5d_return is not None else None
        ),
        "prior_10d_return_pct": (
            round(prior_10d_return, 6)
            if prior_10d_return is not None else None
        ),
        "pct_from_20d_high": (
            round((close / high20) - 1, 6)
            if close is not None and high20 else None
        ),
        "pct_from_252d_high": (
            round((close / high252) - 1, 6)
            if close is not None and high252 else None
        ),
        "volume_vs_20d_avg": (
            round(volume / (sum(vol20) / len(vol20)), 6)
            if volume is not None and vol20 and sum(vol20) > 0 else None
        ),
    }


def _avg_field(rows, field):
    values = [
        row.get(field)
        for row in rows
        if row.get(field) is not None
    ]
    return round(sum(values) / len(values), 6) if values else None


def _gap_context_summary(gap_rows, strong_return_threshold=0.10):
    groups = {
        "strong_forward": [
            row for row in gap_rows
            if row["max_forward_return_pct"] >= strong_return_threshold
        ],
        "weak_forward": [
            row for row in gap_rows
            if row["max_forward_return_pct"] < strong_return_threshold
        ],
    }
    fields = [
        "gap_pct",
        "prior_5d_return_pct",
        "prior_10d_return_pct",
        "pct_from_20d_high",
        "pct_from_252d_high",
        "volume_vs_20d_avg",
        "max_forward_return_pct",
    ]
    out = {}
    for name, group_rows in groups.items():
        out[name] = {
            "count": len(group_rows),
            **{f"avg_{field}": _avg_field(group_rows, field) for field in fields},
        }
    return out


def _gap_cancel_audit(rows, rows_by_ticker=None, threshold_values=(0.015, 0.02, 0.03, 0.05, 0.10)):
    rows_by_ticker = rows_by_ticker or {}
    gap_rows = []
    for row in rows:
        if row.get("decision") != "gap_cancel":
            continue
        details = row.get("details") or {}
        fill_price = details.get("fill_price")
        signal_entry = details.get("signal_entry")
        if not fill_price or not signal_entry:
            continue
        gap_pct = (float(fill_price) / float(signal_entry)) - 1
        context = _context_for_gap(
            rows_by_ticker,
            row.get("ticker"),
            row.get("date"),
        )
        gap_rows.append({**row, **context, "gap_pct": round(gap_pct, 6)})

    if not gap_rows:
        return {
            "sample_count": 0,
            "threshold_sweep": {},
            "rows": [],
        }

    gaps = [row["gap_pct"] for row in gap_rows]
    returns = [row["max_forward_return_pct"] for row in gap_rows]
    sweep = {}
    for threshold in threshold_values:
        admitted = [row for row in gap_rows if row["gap_pct"] <= threshold]
        admitted_returns = [row["max_forward_return_pct"] for row in admitted]
        sweep[f"{threshold:.3f}"] = {
            "threshold_pct": threshold,
            "would_admit_count": len(admitted),
            "would_still_cancel_count": len(gap_rows) - len(admitted),
            "avg_max_forward_return_pct": (
                round(sum(admitted_returns) / len(admitted_returns), 6)
                if admitted_returns else None
            ),
            "median_max_forward_return_pct": (
                round(_median(admitted_returns), 6)
                if admitted_returns else None
            ),
            "best_max_forward_return_pct": (
                round(max(admitted_returns), 6)
                if admitted_returns else None
            ),
            "worst_max_forward_return_pct": (
                round(min(admitted_returns), 6)
                if admitted_returns else None
            ),
        }

    return {
        "sample_count": len(gap_rows),
        "avg_gap_pct": round(sum(gaps) / len(gaps), 6),
        "median_gap_pct": round(_median(gaps), 6),
        "max_gap_pct": round(max(gaps), 6),
        "avg_max_forward_return_pct": round(sum(returns) / len(returns), 6),
        "context_summary": _gap_context_summary(gap_rows),
        "threshold_sweep": sweep,
        "rows": sorted(
            gap_rows,
            key=lambda row: row["max_forward_return_pct"],
            reverse=True,
        ),
    }


def build_entry_skip_oracle(backtest_result, snapshot, horizon_days=20):
    attribution = backtest_result.get("entry_execution_attribution") or {}
    skips = attribution.get("sample_skips") or []
    rows_by_ticker = _ohlcv_rows_by_date(snapshot)
    rows = []
    missing = []

    for event in skips:
        ticker = (event.get("ticker") or "").upper()
        signal_date = event.get("date")
        decision = event.get("decision") or "unknown"
        ticker_rows = rows_by_ticker.get(ticker)
        if not ticker_rows:
            missing.append({**event, "missing_reason": "missing_ohlcv"})
            continue
        forward = _next_rows_after(ticker_rows, signal_date, horizon_days)
        if not forward:
            missing.append({**event, "missing_reason": "no_forward_rows"})
            continue

        details = event.get("details") or {}
        entry_date = details.get("fill_date") or forward[0].get("Date")
        entry_open = details.get("fill_price") or forward[0].get("Open")
        if not entry_open:
            missing.append({**event, "missing_reason": "invalid_entry_open"})
            continue

        entry_open = float(entry_open)
        best_row = max(forward, key=lambda row: float(row.get("High") or 0))
        best_high = float(best_row.get("High") or 0)
        max_forward_return = (best_high * (1 - ROUND_TRIP_COST_PCT) / entry_open) - 1
        rows.append({
            "date": signal_date,
            "ticker": ticker,
            "strategy": event.get("strategy"),
            "decision": decision,
            "candidate_rank": event.get("candidate_rank"),
            "available_slots_at_entry_loop": event.get("available_slots_at_entry_loop"),
            "entry_date": entry_date,
            "entry_open": round(entry_open, 4),
            "oracle_exit_date": best_row.get("Date"),
            "oracle_exit_price": round(best_high * (1 - ROUND_TRIP_COST_PCT), 4),
            "max_forward_return_pct": round(max_forward_return, 6),
            "details": details,
        })

    by_decision = {}
    for row in rows:
        rec = by_decision.setdefault(row["decision"], {
            "sample_count": 0,
            "positive_count": 0,
            "returns": [],
        })
        rec["sample_count"] += 1
        rec["positive_count"] += 1 if row["max_forward_return_pct"] > 0 else 0
        rec["returns"].append(row["max_forward_return_pct"])

    summary = {}
    for decision, rec in by_decision.items():
        returns = rec.pop("returns")
        summary[decision] = {
            "sample_count": rec["sample_count"],
            "positive_fraction": round(rec["positive_count"] / rec["sample_count"], 4),
            "avg_max_forward_return_pct": round(sum(returns) / len(returns), 6),
            "median_max_forward_return_pct": round(_median(returns), 6),
            "best_max_forward_return_pct": round(max(returns), 6),
            "worst_max_forward_return_pct": round(min(returns), 6),
        }

    return {
        "oracle_type": "entry_skip_forward_upper_bound",
        "is_tradable": False,
        "lookahead_warning": (
            "Uses future highs for skipped entry samples. This is a research "
            "triage diagnostic, not a strategy acceptance metric."
        ),
        "horizon_days": horizon_days,
        "source_skip_events": "entry_execution_attribution.sample_skips",
        "source_skip_event_count": len(skips),
        "evaluated_skip_event_count": len(rows),
        "missing_skip_event_count": len(missing),
        "full_skip_count_reported_by_backtest": attribution.get("skipped_count"),
        "coverage_note": (
            "If sample_skips is smaller than skipped_count, this diagnostic covers "
            "only the persisted sample. Persist full skip events before drawing "
            "final conclusions."
        ),
        "by_decision": dict(sorted(summary.items())),
        "gap_cancel_audit": _gap_cancel_audit(rows, rows_by_ticker=rows_by_ticker),
        "top_skipped_opportunities": sorted(
            rows,
            key=lambda row: row["max_forward_return_pct"],
            reverse=True,
        )[:15],
        "missing": missing,
    }


def build_entry_skip_diagnostics(backtest_path, snapshot_path=None, horizon_days=20):
    backtest = _load_json(backtest_path)
    snapshot_path = snapshot_path or infer_snapshot_path(backtest)
    if not snapshot_path:
        raise ValueError("No OHLCV snapshot path found; pass --snapshot explicitly.")
    snapshot = _load_json(snapshot_path)
    return {
        "source_backtest": os.path.abspath(backtest_path),
        "source_snapshot": os.path.abspath(snapshot_path),
        "period": backtest.get("period"),
        "entry_skip_oracle": build_entry_skip_oracle(
            backtest,
            snapshot,
            horizon_days=horizon_days,
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backtest", required=True, help="Backtest result JSON.")
    parser.add_argument("--snapshot", help="OHLCV snapshot JSON. Defaults to known_biases path.")
    parser.add_argument("--horizon-days", type=int, default=20)
    parser.add_argument("--out", help="Optional output JSON path.")
    args = parser.parse_args()

    result = build_entry_skip_diagnostics(
        args.backtest,
        args.snapshot,
        horizon_days=args.horizon_days,
    )
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
