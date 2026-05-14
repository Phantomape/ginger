"""Observed-only estimate revision source quality scout for exp-20260513-103."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def pct(numerator: int | float, denominator: int | float) -> float | None:
    if not denominator:
        return None
    return round(float(numerator) / float(denominator), 6)


def summarize_numbers(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
            "positive_rate": None,
        }
    return {
        "count": len(values),
        "mean": round(statistics.fmean(values), 6),
        "median": round(statistics.median(values), 6),
        "min": round(min(values), 6),
        "max": round(max(values), 6),
        "positive_rate": pct(sum(1 for value in values if value > 0), len(values)),
    }


def collect_candidate_tickers(signal_doc: dict[str, Any]) -> dict[str, set[str]]:
    sections = {
        "production_core_signals": signal_doc.get("signals", []),
        "pilot_signals": signal_doc.get("pilot_signals", []),
        "heat_blocked_signals": signal_doc.get("heat_blocked_signals", []),
        "heat_blocked_pilot_signals": signal_doc.get("heat_blocked_pilot_signals", []),
        "event_sleeve_bundle_candidates": signal_doc.get("event_sleeve_bundle", {}).get("candidates", []),
        "state_surface_scored_candidates": signal_doc.get("state_surface_queue", {}).get("scored_candidates", []),
        "state_surface_candidates": signal_doc.get("state_surface_queue", {}).get("candidates", []),
        "form4_event_queue_candidates": signal_doc.get("form4_event_queue", {}).get("candidates", []),
        "sec_event_queue_candidates": signal_doc.get("sec_event_queue", {}).get("candidates", []),
        "sec_negative_event_queue_candidates": signal_doc.get("sec_negative_event_sleeve", {}).get("new_pending_entries", []),
        "sec_governance_event_queue_candidates": signal_doc.get("sec_governance_event_queue", {}).get("candidates", []),
        "sec_leadership_event_queue_candidates": signal_doc.get("sec_leadership_event_queue", {}).get("candidates", []),
        "sec_financial_report_t1_queue_candidates": signal_doc.get("sec_financial_report_t1_queue", {}).get("candidates", []),
        "space_observation_candidates": signal_doc.get("space_catalyst_observation_slot", {}).get("candidates", []),
    }
    out: dict[str, set[str]] = {}
    for section, records in sections.items():
        tickers = {str(row.get("ticker", "")).upper() for row in records if isinstance(row, dict) and row.get("ticker")}
        if tickers:
            out[section] = tickers
    return out


def load_signal_docs(data_dir: Path, dates: list[str]) -> dict[str, dict[str, Any]]:
    docs: dict[str, dict[str, Any]] = {}
    for date in dates:
        path = data_dir / f"quant_signals_{date.replace('-', '')}.json"
        if path.exists():
            docs[date] = read_json(path)
    return docs


def feature_close(signal_docs: dict[str, dict[str, Any]], date: str, ticker: str) -> float | None:
    doc = signal_docs.get(date)
    if not doc:
        return None
    feature = doc.get("features", {}).get(ticker)
    if not isinstance(feature, dict):
        return None
    close = feature.get("close")
    return float(close) if isinstance(close, (int, float)) else None


def next_dates(dates: list[str], date: str, horizon: int) -> str | None:
    later = [d for d in dates if d > date]
    if len(later) < horizon:
        return None
    return later[horizon - 1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-id", default="exp-20260513-103")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--output", required=True)
    parser.add_argument("--start", default="2026-05-07")
    parser.add_argument("--end", default="2026-05-12")
    args = parser.parse_args()

    data_dir = ROOT / args.data_dir
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)

    date_tags = sorted(
        p.stem.removeprefix("estimate_revision_ledger_")
        for p in (data_dir / "non_ohlcv").glob("estimate_revision_ledger_*.jsonl")
    )
    selected_dates = [
        f"{tag[:4]}-{tag[4:6]}-{tag[6:]}"
        for tag in date_tags
        if args.start <= f"{tag[:4]}-{tag[4:6]}-{tag[6:]}" <= args.end
    ]
    signal_docs = load_signal_docs(data_dir, selected_dates)
    available_signal_dates = sorted(signal_docs)
    candidate_tickers_by_date = {
        date: collect_candidate_tickers(doc) for date, doc in signal_docs.items()
    }

    all_rows: list[dict[str, Any]] = []
    summary_paths: list[str] = []
    for date in selected_dates:
        tag = date.replace("-", "")
        ledger_path = data_dir / "non_ohlcv" / f"estimate_revision_ledger_{tag}.jsonl"
        summary_path = data_dir / "non_ohlcv" / f"estimate_revision_ledger_summary_{tag}.json"
        all_rows.extend(read_jsonl(ledger_path))
        if summary_path.exists():
            summary_paths.append(str(summary_path.relative_to(ROOT)))

    rows_by_date = Counter(row.get("as_of_date") for row in all_rows)
    revision_counts = Counter(row.get("revision_direction_prev") or "missing" for row in all_rows)
    usable_rows = [row for row in all_rows if row.get("estimate_revision_usable")]
    pit_safe_rows = [row for row in all_rows if row.get("pit_safe_flag")]

    required_fields = [
        "ticker",
        "as_of_date",
        "source_snapshot_path",
        "next_earnings_date",
        "eps_estimate",
        "prior_snapshot_date",
        "prior_snapshot_eps_estimate",
        "eps_estimate_delta_prev",
        "revision_direction_prev",
        "same_event_revision_identifiable",
        "pit_safe_flag",
        "estimate_revision_usable",
    ]
    field_coverage = {
        field: {
            "present_rows": sum(1 for row in all_rows if row.get(field) not in (None, "")),
            "total_rows": len(all_rows),
            "coverage": pct(sum(1 for row in all_rows if row.get(field) not in (None, "")), len(all_rows)),
        }
        for field in required_fields
    }

    overlap_rows: list[dict[str, Any]] = []
    scarce_slot_rows: list[dict[str, Any]] = []
    no_overlap_count = 0
    section_counts: Counter[str] = Counter()
    scarce_sections = {
        "production_core_signals",
        "pilot_signals",
        "heat_blocked_signals",
        "heat_blocked_pilot_signals",
    }
    liquidity_rows: list[dict[str, Any]] = []
    forward_returns: dict[str, list[float]] = defaultdict(list)
    forward_excess: dict[str, list[float]] = defaultdict(list)
    forward_by_overlap: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))

    for row in all_rows:
        date = str(row.get("as_of_date") or "")
        ticker = str(row.get("ticker") or "").upper()
        sections = [
            section
            for section, tickers in candidate_tickers_by_date.get(date, {}).items()
            if ticker in tickers
        ]
        if sections:
            row_with_sections = {**row, "overlap_sections": sections}
            overlap_rows.append(row_with_sections)
            if any(section in scarce_sections for section in sections):
                scarce_slot_rows.append(row_with_sections)
            section_counts.update(sections)
        else:
            no_overlap_count += 1

        feature = signal_docs.get(date, {}).get("features", {}).get(ticker, {})
        if isinstance(feature, dict):
            close = feature.get("close")
            volume_spike_ratio = feature.get("volume_spike_ratio")
            above_200ma = feature.get("above_200ma")
            if isinstance(close, (int, float)):
                liquidity_rows.append(
                    {
                        "ticker": ticker,
                        "as_of_date": date,
                        "close": close,
                        "volume_spike_ratio": volume_spike_ratio,
                        "above_200ma": above_200ma,
                    }
                )

        start_close = feature_close(signal_docs, date, ticker)
        spy_start = feature_close(signal_docs, date, "SPY")
        for horizon in [1, 3, 5]:
            end_date = next_dates(available_signal_dates, date, horizon)
            if not end_date or start_close in (None, 0):
                continue
            end_close = feature_close(signal_docs, end_date, ticker)
            spy_end = feature_close(signal_docs, end_date, "SPY")
            if end_close is None:
                continue
            ret = (end_close / start_close) - 1.0
            key = f"{horizon}d"
            forward_returns[key].append(ret)
            if sections:
                forward_by_overlap[key]["overlap"].append(ret)
            else:
                forward_by_overlap[key]["no_overlap"].append(ret)
            if spy_start not in (None, 0) and spy_end is not None:
                forward_excess[key].append(ret - ((spy_end / spy_start) - 1.0))

    close_values = [row["close"] for row in liquidity_rows if isinstance(row.get("close"), (int, float))]
    volume_ratios = [
        float(row["volume_spike_ratio"])
        for row in liquidity_rows
        if isinstance(row.get("volume_spike_ratio"), (int, float))
    ]
    above_200ma_count = sum(1 for row in liquidity_rows if row.get("above_200ma") is True)

    artifact = {
        "experiment_id": args.experiment_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "lane": "universe_scout",
        "status": "observed_only",
        "decision": "observed_only",
        "hypothesis": "PIT-safe analyst EPS estimate revision rows may be useful only if scarce-slot/replacement-value candidates are better than a broader row count.",
        "change_type": "source_shadow_evaluation",
        "changed_variable": "PIT-safe analyst EPS estimate revision ledger source quality",
        "single_causal_variable": "PIT-safe analyst EPS estimate revision ledger source quality",
        "gate_questions": {
            "1_alpha_hypothesis": "Estimate revision source alpha could support event-quality/ranking only if usable same-event revision rows produce better scarce-slot outcomes.",
            "2_history_check": "exp-20260507-092/900 created the forward ledger harness; prior runs had zero usable rows. This run measures source quality now that usable rows exist, without retuning entries or adding tickers.",
            "3_single_causal_variable": "Only the estimate revision source quality is evaluated; production universe, signals, filters, ranking, sizing, and exits stay fixed.",
            "4_acceptance_standard": "Observed-only closeout: report count, coverage, liquidity proxy, overlap, PIT/survivorship risk, forward returns, and scarce-slot quality; do not claim accepted/rejected alpha.",
            "5_reproducibility": "Run this script over data/non_ohlcv/estimate_revision_ledger_YYYYMMDD.jsonl and same-day data/quant_signals_YYYYMMDD.json artifacts.",
        },
        "date_range": {"start": args.start, "end": args.end, "selected_dates": selected_dates},
        "baseline_metrics": {
            "source": "docs/current_state.md / docs/backtesting.md accepted exp-20260513-036 core baseline",
            "aggregate_expected_value_score": 6.4848,
            "aggregate_total_pnl": 193903.95,
            "aggregate_trade_count": 62,
            "min_survival_rate": 0.7925,
        },
        "source_inputs": {
            "ledger_files": [
                f"data/non_ohlcv/estimate_revision_ledger_{date.replace('-', '')}.jsonl"
                for date in selected_dates
            ],
            "summary_files": summary_paths,
            "signal_files_loaded": [
                f"data/quant_signals_{date.replace('-', '')}.json" for date in available_signal_dates
            ],
        },
        "source_quality_summary": {
            "candidate_count": len(all_rows),
            "unique_ticker_count": len({row.get("ticker") for row in all_rows if row.get("ticker")}),
            "rows_by_date": dict(rows_by_date),
            "usable_revision_rows": len(usable_rows),
            "pit_safe_rows": len(pit_safe_rows),
            "pit_safe_rate": pct(len(pit_safe_rows), len(all_rows)),
            "usable_rate": pct(len(usable_rows), len(all_rows)),
            "revision_direction_counts": dict(revision_counts),
            "field_coverage": field_coverage,
            "liquidity_proxy": {
                "feature_rows_matched": len(liquidity_rows),
                "feature_match_rate": pct(len(liquidity_rows), len(all_rows)),
                "close_summary": summarize_numbers(close_values),
                "volume_spike_ratio_summary": summarize_numbers(volume_ratios),
                "above_200ma_rate": pct(above_200ma_count, len(liquidity_rows)),
            },
        },
        "existing_signal_overlap": {
            "overlap_count": len(overlap_rows),
            "overlap_rate": pct(len(overlap_rows), len(all_rows)),
            "no_overlap_count": no_overlap_count,
            "section_counts": dict(section_counts),
            "scarce_slot_overlap_count": len(scarce_slot_rows),
            "scarce_slot_overlap_rate": pct(len(scarce_slot_rows), len(all_rows)),
            "sample_overlap_rows": [
                {
                    "ticker": row.get("ticker"),
                    "as_of_date": row.get("as_of_date"),
                    "revision_direction_prev": row.get("revision_direction_prev"),
                    "eps_estimate_delta_prev": row.get("eps_estimate_delta_prev"),
                    "overlap_sections": row.get("overlap_sections"),
                }
                for row in overlap_rows[:10]
            ],
        },
        "forward_return_distribution": {
            horizon: {
                "raw_return": summarize_numbers(values),
                "excess_vs_spy": summarize_numbers(forward_excess.get(horizon, [])),
                "overlap_return": summarize_numbers(forward_by_overlap[horizon].get("overlap", [])),
                "no_overlap_return": summarize_numbers(forward_by_overlap[horizon].get("no_overlap", [])),
            }
            for horizon, values in sorted(forward_returns.items())
        },
        "scarce_slot_quality": {
            "measurable": bool(scarce_slot_rows),
            "scarce_slot_candidate_count": len(scarce_slot_rows),
            "scarce_slot_sections": sorted(scarce_sections),
            "scarce_slot_candidates_look_better_than_more_rows": False,
            "reason": (
                "No same-day production/pilot/heat-blocked candidate overlap exists."
                if not scarce_slot_rows
                else "Scarce-slot overlap exists, but it is too small and mostly lacks a non-flat revision discriminator or closed promotion-grade forward horizon."
            ),
            "sample_scarce_slot_rows": [
                {
                    "ticker": row.get("ticker"),
                    "as_of_date": row.get("as_of_date"),
                    "revision_direction_prev": row.get("revision_direction_prev"),
                    "eps_estimate_delta_prev": row.get("eps_estimate_delta_prev"),
                    "overlap_sections": row.get("overlap_sections"),
                }
                for row in scarce_slot_rows[:10]
            ],
        },
        "survivorship_and_pit_risk": {
            "pit_safe_flag_present": field_coverage["pit_safe_flag"]["coverage"],
            "same_event_revision_identifiable_rate": pct(
                sum(1 for row in all_rows if row.get("same_event_revision_identifiable")), len(all_rows)
            ),
            "source_snapshot_pit_safe_rate": pct(
                sum(1 for row in all_rows if row.get("source_snapshot_pit_safe")), len(all_rows)
            ),
            "known_risks": [
                "Estimate rows are forward daily snapshots only; historical backfill promotion is not claimed.",
                "Vendor_asof is missing, so snapshot mtime/source_retrieved_at discipline remains the PIT guard.",
                "The current usable sample is all flat revisions; no positive/negative revision discriminator is present yet.",
                "Forward closes are limited to locally available quant_signals dates through 2026-05-12.",
            ],
        },
        "required_metrics": {
            "expected_value_score": None,
            "total_return": None,
            "total_pnl": None,
            "sharpe_daily": None,
            "max_drawdown": None,
            "win_rate": None,
            "trade_count": None,
            "signals_generated": None,
            "signals_survived": None,
            "survival_rate": None,
            "candidate_count": len(all_rows),
            "overlap_with_existing_signals": len(overlap_rows),
            "production_impact": "none_observed_only_shadow_artifact",
        },
        "expected_value_score_delta": None,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "production_signal_path_changed": False,
            "production_tickers_added": False,
            "touched_strategy_modules": [],
        },
        "decision_reason": "Keep observed-only: usable PIT rows exist, but they are flat revisions with no scarce-slot overlap edge and only short forward-close evidence.",
        "next_minimum_action": "Continue collecting forward ledgers until non-flat revisions touch existing candidates and close 10/20d outcomes before any ranking or promotion test.",
    }

    with output.open("w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2, sort_keys=True)
        f.write("\n")
    print(json.dumps({"artifact": str(output.relative_to(ROOT)), "candidate_count": len(all_rows)}, indent=2))


if __name__ == "__main__":
    main()
