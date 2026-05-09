"""Build a narrow LLM/event alpha readiness coverage manifest.

This is an observed-only measurement script. It does not import strategy
modules or alter replay behavior; it summarizes existing artifacts that gate a
future LLM/event soft-ranking alpha test.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DATE_RE = re.compile(r"(\d{8})")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def date_key_to_iso(date_key: str) -> str:
    return f"{date_key[:4]}-{date_key[4:6]}-{date_key[6:]}"


def key_in_range(date_key: str, start_key: str, end_key: str) -> bool:
    return start_key <= date_key <= end_key


def extract_date_key(path: Path) -> str | None:
    match = DATE_RE.search(path.name)
    return match.group(1) if match else None


def business_date_keys_from_coverage(start_key: str, end_key: str) -> list[str]:
    coverage_path = ROOT / "data" / "non_ohlcv" / f"backtest_coverage_{start_key}_{end_key}.json"
    if coverage_path.exists():
        coverage = load_json(coverage_path)
        records = coverage.get("records", [])
        return [r["date_key"] for r in records if "date_key" in r]
    return []


def count_dated_files(pattern: str, start_key: str, end_key: str) -> tuple[list[str], list[str]]:
    files = sorted((ROOT / "data").glob(pattern))
    covered: list[str] = []
    paths: list[str] = []
    for path in files:
        date_key = extract_date_key(path)
        if date_key and key_in_range(date_key, start_key, end_key):
            covered.append(date_key)
            paths.append(str(path.relative_to(ROOT)))
    return covered, paths


def classify_llm_archive(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    date_key = extract_date_key(path) or ""
    keys = sorted(payload.keys()) if isinstance(payload, dict) else []
    has_legacy_parsed = isinstance(payload, dict) and isinstance(payload.get("advice_parsed"), dict)
    has_daily_actions = isinstance(payload, dict) and (
        "new_trade" in payload or "position_actions" in payload or "add_on_vetoes" in payload
    )
    has_archive_context = isinstance(payload, dict) and isinstance(payload.get("archive_context"), dict)
    return {
        "date_key": date_key,
        "path": str(path.relative_to(ROOT)),
        "schema_family": "legacy_advice_parsed" if has_legacy_parsed else "daily_action_snapshot" if has_daily_actions else "unknown",
        "has_structured_fields": bool(has_legacy_parsed or has_daily_actions),
        "has_archive_context": has_archive_context,
        "top_level_keys": keys,
    }


def sum_signal_counts(counts: dict[str, int], dates: list[str]) -> int:
    return sum(int(counts.get(d, 0)) for d in dates)


def find_window_backtest(start_iso: str, end_iso: str, preferred: Path) -> tuple[Path, dict[str, Any]]:
    candidates = [preferred] + sorted((ROOT / "data").glob("backtest_results_*.json"), reverse=True)
    seen: set[Path] = set()
    for path in candidates:
        if not path.exists() or path in seen:
            continue
        seen.add(path)
        payload = load_json(path)
        period = str(payload.get("period", ""))
        if start_iso in period and end_iso in period:
            return path, payload
    return preferred, load_json(preferred)


def build_manifest(experiment_id: str, start: str, end: str, baseline_result_file: str) -> dict[str, Any]:
    start_key = start.replace("-", "")
    end_key = end.replace("-", "")
    business_keys = business_date_keys_from_coverage(start_key, end_key)
    business_set = set(business_keys)
    business_days = len(business_keys)

    backtest_path, backtest = find_window_backtest(
        start,
        end,
        ROOT / baseline_result_file,
    )
    llm_attr = backtest.get("llm_attribution", {})
    news_attr = backtest.get("news_attribution", {})
    non_ohlcv = backtest.get("non_ohlcv_coverage", {})

    llm_files = [
        classify_llm_archive(path)
        for path in sorted((ROOT / "data").glob("llm_prompt_resp_*.json"))
        if (extract_date_key(path) and key_in_range(extract_date_key(path) or "", start_key, end_key))
    ]
    llm_dates = sorted({row["date_key"] for row in llm_files})
    llm_archive_context_dates = sorted({row["date_key"] for row in llm_files if row["has_archive_context"]})

    clean_trade_news_dates, clean_trade_news_paths = count_dated_files(
        "clean_trade_news_*.json",
        start_key,
        end_key,
    )
    clean_news_dates, clean_news_paths = count_dated_files("clean_news_*.json", start_key, end_key)
    earnings_dates, _ = count_dated_files("earnings_snapshot_*.json", start_key, end_key)

    sec_event_dates = []
    daily_snapshot_dates = []
    for base_pattern, target in [
        ("non_ohlcv/sec_filing_events_*.jsonl", sec_event_dates),
        ("non_ohlcv/daily_non_ohlcv_snapshot_*.json", daily_snapshot_dates),
    ]:
        for path in sorted((ROOT / "data").glob(base_pattern)):
            date_key = extract_date_key(path)
            if date_key and key_in_range(date_key, start_key, end_key):
                target.append(date_key)

    news_candidate_covered = news_attr.get("candidate_dates_covered", [])
    news_candidate_missing = news_attr.get("candidate_dates_missing", [])
    news_signal_counts = news_attr.get("candidate_signal_counts_by_date", {})
    news_candidate_signals_total = sum_signal_counts(
        news_signal_counts,
        list(news_signal_counts.keys()),
    )
    news_candidate_signals_covered = sum_signal_counts(news_signal_counts, news_candidate_covered)

    llm_effective = llm_attr.get("effective_attribution", {})
    llm_context = llm_attr.get("context_alignment", {})
    llm_candidate_signals_total = int(llm_attr.get("candidate_signals_total", 0) or 0)
    llm_candidate_signals_covered = int(llm_attr.get("candidate_signals_covered", 0) or 0)

    readiness_checks = {
        "raw_llm_archive_days_at_least_30": len(llm_dates) >= 30,
        "llm_effective_candidate_signals_positive": int(
            llm_effective.get("effective_candidate_signals", 0) or 0
        )
        > 0,
        "news_candidate_day_coverage_at_least_half": (
            len(news_candidate_covered) / max(1, len(news_candidate_covered) + len(news_candidate_missing))
        )
        >= 0.5,
        "non_ohlcv_window_complete": float(non_ohlcv.get("complete_fraction", 0) or 0) >= 1.0,
        "candidate_outcome_join_available": bool(backtest.get("trades")),
    }
    ready_for_alpha_test = all(readiness_checks.values())

    remaining_blockers = []
    if not readiness_checks["raw_llm_archive_days_at_least_30"]:
        remaining_blockers.append(
            f"LLM archive has {len(llm_dates)} dated files in-window; need >=30 before testing LLM soft ranking."
        )
    if not readiness_checks["llm_effective_candidate_signals_positive"]:
        remaining_blockers.append(
            "Backtest LLM effective attribution has zero candidate signals, so veto/pass/rank quality cannot be measured yet."
        )
    if not readiness_checks["news_candidate_day_coverage_at_least_half"]:
        remaining_blockers.append(
            f"News replay covers {len(news_candidate_covered)} of "
            f"{len(news_candidate_covered) + len(news_candidate_missing)} candidate days; improve archive coverage before event grading."
        )

    return {
        "schema_version": 1,
        "experiment_id": experiment_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lane": "measurement_repair",
        "single_causal_variable": "llm event alpha readiness coverage manifest",
        "strategy_behavior_changed": False,
        "alpha_hypothesis_unblocked": {
            "category": "ranking / event_quality",
            "hypothesis": (
                "LLM/news event grading may improve scarce-slot ranking or event veto quality "
                "once prompt archives and candidate outcome joins cover enough candidate days."
            ),
            "why_not_tested_now": "Current manifest shows attribution coverage is not yet sufficient for a reliable alpha test.",
            "next_alpha_test_when_ready": (
                "Default-off replay: rank same-day A/B candidates by structured LLM/news event grade and compare "
                "selected-vs-replaced candidate forward returns across at least three windows."
            ),
        },
        "window": {
            "start": start,
            "end": end,
            "business_days_from_coverage_manifest": business_days,
        },
        "baseline": {
            "ticket_baseline_result_file": baseline_result_file,
            "window_matched_backtest_file": str(backtest_path.relative_to(ROOT)),
            "expected_value_score": backtest.get("expected_value_score"),
            "total_trades": backtest.get("total_trades"),
            "signals_survived": backtest.get("signals_survived"),
        },
        "coverage": {
            "non_ohlcv": {
                "complete_fraction": non_ohlcv.get("complete_fraction"),
                "complete_days": non_ohlcv.get("complete_days"),
                "business_days": non_ohlcv.get("business_days"),
                "missing_by_artifact": non_ohlcv.get("missing_by_artifact", {}),
            },
            "llm_archive": {
                "dated_file_count": len(llm_dates),
                "business_day_fraction": round(len(set(llm_dates) & business_set) / max(1, business_days), 4),
                "archive_context_file_count": len(llm_archive_context_dates),
                "dates": llm_dates,
                "schema_families": sorted({row["schema_family"] for row in llm_files}),
                "files": llm_files,
            },
            "news_archive": {
                "clean_trade_news_file_count": len(clean_trade_news_dates),
                "clean_news_file_count": len(clean_news_dates),
                "candidate_days_covered": len(news_candidate_covered),
                "candidate_days_total": len(news_candidate_covered) + len(news_candidate_missing),
                "candidate_day_coverage_fraction": round(
                    len(news_candidate_covered) / max(1, len(news_candidate_covered) + len(news_candidate_missing)),
                    4,
                ),
                "candidate_signals_covered": news_candidate_signals_covered,
                "candidate_signals_total": news_candidate_signals_total,
                "sample_paths": (clean_trade_news_paths + clean_news_paths)[:10],
            },
            "event_snapshots": {
                "earnings_snapshot_files": len(earnings_dates),
                "sec_filing_event_files": len(sec_event_dates),
                "daily_non_ohlcv_snapshot_files": len(daily_snapshot_dates),
            },
            "llm_effective_attribution": {
                "replay_enabled": llm_attr.get("replay_enabled"),
                "candidate_signals_covered": llm_candidate_signals_covered,
                "candidate_signals_total": llm_candidate_signals_total,
                "candidate_signal_coverage_fraction": llm_attr.get("candidate_signal_coverage_fraction"),
                "effective_candidate_days": llm_effective.get("effective_candidate_days"),
                "effective_candidate_signals": llm_effective.get("effective_candidate_signals"),
                "ranking_eligible_aligned_days": llm_context.get("ranking_eligible_aligned_days"),
                "ranking_eligible_aligned_signals": llm_context.get("ranking_eligible_aligned_signals"),
            },
        },
        "readiness": {
            "ready_for_llm_event_alpha_test": ready_for_alpha_test,
            "checks": readiness_checks,
            "remaining_blockers": remaining_blockers,
            "minimal_next_measurement": (
                "Persist prompt-time candidate context and LLM response for additional production days, "
                "then rerun this manifest until effective candidate signals are non-zero."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-id", default="exp-20260508-030")
    parser.add_argument("--start", default="2025-10-23")
    parser.add_argument("--end", default="2026-04-21")
    parser.add_argument("--baseline-result-file", default="data/backtest_results_20260508.json")
    parser.add_argument(
        "--output",
        default="data/experiments/exp-20260508-030/exp_20260508_030_llm_event_readiness_manifest.json",
    )
    args = parser.parse_args()

    manifest = build_manifest(args.experiment_id, args.start, args.end, args.baseline_result_file)
    output_path = ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "experiment_id": args.experiment_id,
        "output": str(output_path.relative_to(ROOT)),
        "ready_for_llm_event_alpha_test": manifest["readiness"]["ready_for_llm_event_alpha_test"],
        "llm_dated_file_count": manifest["coverage"]["llm_archive"]["dated_file_count"],
        "news_candidate_day_coverage_fraction": manifest["coverage"]["news_archive"]["candidate_day_coverage_fraction"],
        "llm_effective_candidate_signals": manifest["coverage"]["llm_effective_attribution"]["effective_candidate_signals"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
