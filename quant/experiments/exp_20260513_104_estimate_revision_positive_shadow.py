"""Observed-only estimate revision shadow alpha audit for exp-20260513-104."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any


WINDOW_START = "2026-05-07"
WINDOW_END = "2026-05-12"
EXPERIMENT_ID = "exp-20260513-104"
BASELINE_PATH = Path("data/backtest_results_20260513.json")
DEFAULT_OUTPUT = Path(
    "data/experiments/exp-20260513-104/"
    "exp_20260513_104_estimate_revision_positive_shadow.json"
)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_trend_closes(data_dir: Path) -> dict[str, dict[str, float]]:
    closes: dict[str, dict[str, float]] = {}
    for path in sorted(data_dir.glob("trend_signals_*.json")):
        payload = read_json(path)
        asof = str(payload.get("asof_date") or "")
        if not asof:
            continue
        day: dict[str, float] = {}
        for ticker, fields in (payload.get("signals") or {}).items():
            close = fields.get("close")
            if close is not None:
                day[str(ticker).upper()] = float(close)
        closes[asof] = day
    return closes


def horizon_returns(
    row: dict[str, Any],
    dates: list[str],
    closes: dict[str, dict[str, float]],
    horizons: tuple[int, ...] = (1, 2, 3),
) -> dict[str, float | None]:
    asof = row["as_of_date"]
    ticker = row["ticker"]
    if asof not in dates:
        return {f"fwd_{h}_snapshot_return": None for h in horizons}
    start_close = closes.get(asof, {}).get(ticker)
    if start_close in (None, 0):
        return {f"fwd_{h}_snapshot_return": None for h in horizons}
    idx = dates.index(asof)
    out: dict[str, float | None] = {}
    for horizon in horizons:
        target_idx = idx + horizon
        if target_idx >= len(dates):
            out[f"fwd_{horizon}_snapshot_return"] = None
            continue
        target_close = closes.get(dates[target_idx], {}).get(ticker)
        out[f"fwd_{horizon}_snapshot_return"] = (
            round((target_close - start_close) / start_close, 6)
            if target_close is not None
            else None
        )
    return out


def distribution(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "avg": None,
            "median": None,
            "win_rate": None,
            "min": None,
            "max": None,
        }
    return {
        "count": len(values),
        "avg": round(mean(values), 6),
        "median": round(median(values), 6),
        "win_rate": round(sum(1 for value in values if value > 0) / len(values), 6),
        "min": round(min(values), 6),
        "max": round(max(values), 6),
    }


def summarize_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_horizon: dict[str, Any] = {}
    for key in (
        "fwd_1_snapshot_return",
        "fwd_2_snapshot_return",
        "fwd_3_snapshot_return",
    ):
        vals = [row[key] for row in rows if row.get(key) is not None]
        by_horizon[key] = distribution(vals)
    return {
        "row_count": len(rows),
        "unique_tickers": sorted({row["ticker"] for row in rows}),
        "matched_candidate_rows": sum(bool(row.get("matched_candidate_today")) for row in rows),
        "matched_selected_signal_rows": sum(
            bool(row.get("matched_selected_signal_today")) for row in rows
        ),
        "forward_return_distribution": by_horizon,
    }


def metric_snapshot_for_judge(baseline: dict[str, Any]) -> dict[str, Any]:
    benchmarks = baseline.get("benchmarks") or {}
    return {
        "expected_value_score": baseline.get("expected_value_score"),
        "sharpe": baseline.get("sharpe"),
        "sharpe_daily": baseline.get("sharpe_daily"),
        "benchmarks": {
            "strategy_total_return_pct": benchmarks.get("strategy_total_return_pct")
        },
        "max_drawdown_pct": baseline.get("max_drawdown_pct"),
        "win_rate": baseline.get("win_rate"),
        "total_trades": baseline.get("total_trades"),
        "survival_rate": baseline.get("survival_rate"),
        "total_pnl": baseline.get("total_pnl"),
    }


def run(data_dir: Path, output_path: Path) -> dict[str, Any]:
    baseline = read_json(BASELINE_PATH)
    metric_copy = metric_snapshot_for_judge(baseline)
    closes = load_trend_closes(data_dir)
    close_dates = sorted(closes)

    all_rows: list[dict[str, Any]] = []
    for path in sorted((data_dir / "non_ohlcv").glob("estimate_revision_ledger_202605*.jsonl")):
        rows = read_jsonl(path)
        for row in rows:
            asof = row.get("as_of_date")
            if WINDOW_START <= str(asof) <= WINDOW_END:
                all_rows.append(row)

    enriched: list[dict[str, Any]] = []
    for row in all_rows:
        if not row.get("estimate_revision_usable"):
            continue
        item = {
            "as_of_date": row.get("as_of_date"),
            "ticker": row.get("ticker"),
            "revision_direction_prev": row.get("revision_direction_prev"),
            "eps_estimate_delta_prev": row.get("eps_estimate_delta_prev"),
            "next_earnings_date": row.get("next_earnings_date"),
            "matched_candidate_today": bool(row.get("matched_candidate_today")),
            "matched_selected_signal_today": bool(row.get("matched_selected_signal_today")),
            "matched_signal_sources": row.get("matched_signal_sources") or [],
            "matched_signal_record_types": row.get("matched_signal_record_types") or [],
            "candidate_match_gap_reason": row.get("candidate_match_gap_reason"),
        }
        item.update(horizon_returns(item, close_dates, closes))
        enriched.append(item)

    positive = [row for row in enriched if row["revision_direction_prev"] == "up"]
    down = [row for row in enriched if row["revision_direction_prev"] == "down"]
    flat = [row for row in enriched if row["revision_direction_prev"] == "flat"]

    result = {
        **metric_copy,
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "decision": "observed_only",
        "hypothesis": (
            "PIT-safe positive same-event EPS estimate revisions may identify a "
            "narrow production-visible earnings-quality shadow state."
        ),
        "single_causal_variable": "positive same-event EPS estimate revision shadow label",
        "window": {"start": WINDOW_START, "end": WINDOW_END},
        "gate_answers": {
            "alpha_hypothesis": (
                "event_interpretation/ranking alpha: positive same-event EPS estimate "
                "revision labels may improve candidate quality without changing entries."
            ),
            "history_check": (
                "Prior estimate-revision work repaired the ledger but was data-gapped; "
                "this run is the first pass after usable same-event rows appeared."
            ),
            "changed_variable": "positive EPS estimate revision label only",
            "acceptance_standard": (
                "observed_only: measure coverage, overlap, forward returns, and "
                "replacement-value readiness; no production promotion."
            ),
            "reproducibility": (
                "Uses data/non_ohlcv/estimate_revision_ledger_202605*.jsonl and "
                "data/trend_signals_*.json for the stated window."
            ),
        },
        "gate1_baseline": {
            "baseline_result_file": str(BASELINE_PATH).replace("\\", "/"),
            "baseline_metrics_for_judge": metric_copy,
            "known_bias": (
                "This is a forward observed-only label audit, not a strategy-affecting "
                "before/after backtest."
            ),
        },
        "gate2_fields": {
            "ledger_fields": [
                "as_of_date",
                "ticker",
                "estimate_revision_usable",
                "revision_direction_prev",
                "eps_estimate_delta_prev",
                "next_earnings_date",
            ],
            "runtime_position_fields_checked_externally": ["entry_date", "target_price"],
        },
        "gate3": {
            "new_filter_added": False,
            "strategy_survival_rate_changed": False,
        },
        "summary": {
            "ledger_rows_in_window": len(all_rows),
            "usable_revision_rows": len(enriched),
            "positive_revision_candidate_count": len(positive),
            "down_revision_count": len(down),
            "flat_revision_count": len(flat),
            "positive_unique_tickers": sorted({row["ticker"] for row in positive}),
            "overlap": {
                "positive_matched_candidate_rows": sum(
                    bool(row.get("matched_candidate_today")) for row in positive
                ),
                "positive_matched_selected_signal_rows": sum(
                    bool(row.get("matched_selected_signal_today")) for row in positive
                ),
                "overlap_with_existing_strategy_pct": 0.0 if positive else None,
            },
            "scarce_slot_replacement_value": {
                "measurable": False,
                "reason": (
                    "No positive revision row overlapped a persisted candidate, selected "
                    "signal, or slot-blocked signal in this forward window."
                ),
            },
        },
        "groups": {
            "positive_revision": summarize_group(positive),
            "down_revision": summarize_group(down),
            "flat_revision": summarize_group(flat),
        },
        "sample_positive_rows": positive[:20],
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "observed_only": True,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
        },
        "decision_notes": (
            "Useful as a forward shadow label only. It has PIT-usable rows and "
            "some closed close-to-close outcomes, but zero overlap with persisted "
            "Ginger candidates/signals in this window, so scarce-slot value is not "
            "yet measurable."
        ),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    result = run(Path(args.data_dir), Path(args.output))
    print(json.dumps(result["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
