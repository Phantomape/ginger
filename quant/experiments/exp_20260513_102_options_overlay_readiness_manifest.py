"""Build a read-only readiness manifest for the options overlay alpha.

This script does not import strategy modules and does not mutate production
state. It summarizes whether the current OnClickMedia options forward ledger is
ready for an attribution experiment on existing Ginger candidates.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_LEDGER_REPORT = Path(
    "data/experiments/exp-20260513-099/options_forward_candidate_ledger_report.json"
)
DEFAULT_LEDGER = Path(
    "data/experiments/exp-20260513-099/options_forward_candidate_ledger.jsonl"
)
DEFAULT_QUALITY = Path(
    "data/experiments/exp-20260513-099/options_collection_quality_gate.json"
)
DEFAULT_OUTPUT = Path(
    "data/experiments/exp-20260513-102/exp_20260513_102_options_overlay_readiness_manifest.json"
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def quant_signal_path_for(date_text: str) -> Path:
    return Path(f"data/quant_signals_{date_text.replace('-', '')}.json")


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_quote: dict[str, dict[str, Any]] = {}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("options_quote_date"))].append(row)

    for quote_date, quote_rows in sorted(grouped.items()):
        usable_dates = sorted(
            {str(row.get("options_usable_from")) for row in quote_rows if row.get("options_usable_from")}
        )
        candidate_dates = sorted(
            {str(row.get("candidate_source_date")) for row in quote_rows if row.get("candidate_source_date")}
        )
        candidate_files = sorted(
            {str(row.get("candidate_source_file")) for row in quote_rows if row.get("candidate_source_file")}
        )
        by_quote[quote_date] = {
            "ledger_rows": len(quote_rows),
            "candidate_count": len(quote_rows),
            "usable_trade_dates": usable_dates,
            "candidate_source_dates": candidate_dates,
            "candidate_source_files_present": {
                path: Path(path).exists() for path in candidate_files
            },
            "next_usable_quant_signal_file_present": {
                date: quant_signal_path_for(date).exists() for date in usable_dates
            },
            "pit_join_safe_candidates": sum(1 for row in quote_rows if row.get("pit_candidate_join_safe")),
            "options_scoring_allowed_candidates": sum(
                1 for row in quote_rows if row.get("options_scoring_allowed")
            ),
            "option_liquidity_eligible_candidates": sum(
                1 for row in quote_rows if row.get("option_liquidity_filter")
            ),
            "squeeze_overlay_candidates": sum(1 for row in quote_rows if row.get("squeeze_overlay")),
            "downside_risk_overlay_candidates": sum(
                1 for row in quote_rows if row.get("downside_risk_overlay")
            ),
            "earnings_vol_overlay_candidates": sum(
                1 for row in quote_rows if row.get("earnings_vol_overlay")
            ),
            "outcome_status_counts": dict(Counter(str(row.get("outcome_status")) for row in quote_rows)),
            "source_section_counts": dict(
                Counter(str(row.get("candidate_source_section")) for row in quote_rows)
            ),
        }
    return by_quote


def closed_forward_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"5d": 0, "10d": 0, "20d": 0, "60d": 0}
    for row in rows:
        forward_returns = row.get("forward_returns") or {}
        for horizon in counts:
            if forward_returns.get(horizon) is not None:
                counts[horizon] += 1
    return counts


def build_manifest(args: argparse.Namespace) -> dict[str, Any]:
    report = load_json(args.ledger_report)
    quality = load_json(args.quality_gate)
    rows = load_jsonl(args.ledger)
    by_quote = summarize_rows(rows)
    closed_counts = closed_forward_counts(rows)

    usable_quote_dates = quality.get("usable_quote_dates", [])
    usable_dates_from_rows = {
        usable_date
        for quote_summary in by_quote.values()
        for usable_date in quote_summary["usable_trade_dates"]
    }
    usable_dates_from_quality = {
        usable_date
        for quote in quality.get("by_quote_date", {}).values()
        for usable_date in quote.get("usable_trade_dates", [])
    }
    missing_candidate_dates = sorted(
        date
        for date in usable_dates_from_rows | usable_dates_from_quality
        if not quant_signal_path_for(date).exists()
    )
    usable_quote_dates_without_ledger_rows = sorted(
        quote_date for quote_date in usable_quote_dates if quote_date not in by_quote
    )
    all_closed_counts_zero = all(value == 0 for value in closed_counts.values())
    has_scoring_candidates = sum(
        quote["options_scoring_allowed_candidates"] for quote in by_quote.values()
    )

    blockers = []
    if missing_candidate_dates:
        blockers.append(
            {
                "blocker": "missing_quant_signal_candidate_file",
                "dates": missing_candidate_dates,
                "why_it_blocks_alpha": (
                    "The options quote can only be joined PIT-safely to the next usable "
                    "candidate file; without that file, the overlay cannot be scored on "
                    "the current production candidate set."
                ),
            }
        )
    if usable_quote_dates_without_ledger_rows:
        blockers.append(
            {
                "blocker": "usable_options_quote_date_without_ledger_rows",
                "quote_dates": usable_quote_dates_without_ledger_rows,
                "why_it_blocks_alpha": (
                    "These options snapshots passed the quality gate but produced no candidate "
                    "ledger rows yet; confirm whether this is true zero candidate overlap or a "
                    "missing next-day candidate join."
                ),
            }
        )
    if all_closed_counts_zero:
        blockers.append(
            {
                "blocker": "no_closed_forward_outcomes",
                "closed_forward_counts": closed_counts,
                "why_it_blocks_alpha": (
                    "The overlay has candidate coverage but no realized forward return, "
                    "drawdown, or volatility attribution yet."
                ),
            }
        )
    if has_scoring_candidates == 0:
        blockers.append(
            {
                "blocker": "no_scoring_allowed_candidates",
                "why_it_blocks_alpha": "No options rows pass the current shadow quality gate.",
            }
        )

    decision = "ready_for_alpha_attribution" if not blockers else "blocked_observed_only"
    return {
        "experiment_id": "exp-20260513-102",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "hypothesis_unblocked": (
            "Test whether PIT-safe options IV/skew/term/open-interest structure improves "
            "replacement value when used only as a default-off overlay on existing Ginger "
            "candidates."
        ),
        "change_type": "measurement_instrumentation",
        "strategy_behavior_changed": False,
        "source_artifacts": {
            "ledger_report": str(args.ledger_report),
            "ledger": str(args.ledger),
            "quality_gate": str(args.quality_gate),
        },
        "baseline_report_summary": {
            "candidate_count": report.get("shadow_metrics", {}).get("candidate_count"),
            "pit_join_safe_candidates": report.get("shadow_metrics", {}).get("pit_join_safe_candidates"),
            "options_scoring_allowed_candidates": report.get("shadow_metrics", {}).get(
                "options_scoring_allowed_candidates"
            ),
            "outcome_status_counts": report.get("shadow_metrics", {}).get("outcome_status_counts"),
            "next_minimum_action": report.get("next_minimum_action"),
        },
        "quality_summary": {
            "usable_quote_dates": usable_quote_dates,
            "quarantined_quote_dates": quality.get("quarantined_quote_dates", []),
            "overall_status": quality.get("overall_status"),
        },
        "readiness_summary": {
            "quote_dates_with_ledger_rows": sorted(by_quote),
            "ledger_rows": len(rows),
            "closed_forward_counts": closed_counts,
            "missing_next_usable_quant_signal_dates": missing_candidate_dates,
            "usable_quote_dates_without_ledger_rows": usable_quote_dates_without_ledger_rows,
            "total_pit_join_safe_candidates": sum(
                quote["pit_join_safe_candidates"] for quote in by_quote.values()
            ),
            "total_options_scoring_allowed_candidates": has_scoring_candidates,
            "total_squeeze_overlay_candidates": sum(
                quote["squeeze_overlay_candidates"] for quote in by_quote.values()
            ),
            "total_downside_risk_overlay_candidates": sum(
                quote["downside_risk_overlay_candidates"] for quote in by_quote.values()
            ),
        },
        "by_options_quote_date": by_quote,
        "blockers": blockers,
        "decision": decision,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger-report", type=Path, default=DEFAULT_LEDGER_REPORT)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--quality-gate", type=Path, default=DEFAULT_QUALITY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    manifest = build_manifest(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "decision": manifest["decision"]}, indent=2))


if __name__ == "__main__":
    main()
