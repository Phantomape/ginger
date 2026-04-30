"""Audit LLM replay attribution coverage without changing strategy behavior.

This experiment is intentionally read-only for production code. It measures
whether saved production LLM archives are usable for a later LLM/event ranking
alpha experiment.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260430-009"
DEFAULT_START = "2025-10-23"
DEFAULT_END = "2026-04-21"
DEFAULT_OUTPUT = Path(
    "data/experiments/exp-20260430-009/"
    "exp_20260430_009_llm_replay_attribution_coverage.json"
)
DEFAULT_BASELINE = Path("data/backtest_results_20260429.json")


def ymd_to_date(value: str) -> datetime:
    return datetime.strptime(value, "%Y%m%d")


def iso_to_ymd(value: str) -> str:
    return datetime.strptime(value, "%Y-%m-%d").strftime("%Y%m%d")


def date_range_weekdays(start: str, end: str) -> list[str]:
    current = datetime.strptime(start, "%Y-%m-%d")
    final = datetime.strptime(end, "%Y-%m-%d")
    out: list[str] = []
    while current <= final:
        if current.weekday() < 5:
            out.append(current.strftime("%Y%m%d"))
        current += timedelta(days=1)
    return out


def date_from_path(path: Path) -> str | None:
    stem = path.stem
    token = stem.rsplit("_", 1)[-1]
    if len(token) == 8 and token.isdigit():
        return token
    return None


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def collect_files(data_dir: Path, pattern: str, start_ymd: str, end_ymd: str) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for path in sorted(data_dir.glob(pattern)):
        date = date_from_path(path)
        if date and start_ymd <= date <= end_ymd:
            files[date] = path
    return files


def signal_tickers(signals: list[dict[str, Any]]) -> set[str]:
    tickers = set()
    for signal in signals:
        ticker = signal.get("ticker") or signal.get("symbol")
        if ticker:
            tickers.add(str(ticker).upper())
    return tickers


def classify_new_trade(value: Any) -> str:
    if value is None:
        return "missing"
    if isinstance(value, str):
        normalized = value.strip().upper()
        if not normalized:
            return "empty"
        if "NO NEW TRADE" in normalized or "NO_TRADE" in normalized:
            return "no_new_trade"
        return "text_trade_or_reason"
    if isinstance(value, dict):
        action = str(value.get("action") or value.get("decision") or "").upper()
        if "NO" in action and "TRADE" in action:
            return "no_new_trade"
        if action:
            return "structured_action"
        return "structured_unknown"
    return type(value).__name__


def pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def build_audit(start: str, end: str, data_dir: Path, baseline_path: Path) -> dict[str, Any]:
    start_ymd = iso_to_ymd(start)
    end_ymd = iso_to_ymd(end)
    weekdays = date_range_weekdays(start, end)

    prompt_resp = collect_files(data_dir, "llm_prompt_resp_*.json", start_ymd, end_ymd)
    decision_logs = collect_files(data_dir, "llm_decision_log_*.json", start_ymd, end_ymd)
    quant_signals = collect_files(data_dir, "quant_signals_*.json", start_ymd, end_ymd)
    prompts = collect_files(data_dir, "llm_prompt_*.txt", start_ymd, end_ymd)
    raw_outputs = collect_files(data_dir, "llm_output_*.json", start_ymd, end_ymd)
    investment_advice = collect_files(data_dir, "investment_advice_*.json", start_ymd, end_ymd)
    clean_trade_news = collect_files(data_dir, "clean_trade_news_*.json", start_ymd, end_ymd)

    all_dates = sorted(
        set(prompt_resp)
        | set(decision_logs)
        | set(quant_signals)
        | set(prompts)
        | set(raw_outputs)
        | set(investment_advice)
        | set(clean_trade_news)
    )

    rows: list[dict[str, Any]] = []
    totals = Counter()
    mode_counts = Counter()
    new_trade_classes = Counter()
    effective_dates: list[str] = []
    candidate_context_dates: list[str] = []
    candidate_context_missing_prompt: list[str] = []
    candidate_context_missing_quant: list[str] = []
    full_triplet_dates: list[str] = []
    prompt_only_dates: list[str] = []
    decision_only_dates: list[str] = []
    context_only_dates: list[str] = []
    raw_recoverable_dates: list[str] = []

    for date in all_dates:
        decision = load_json(decision_logs[date]) if date in decision_logs else {}
        quant = load_json(quant_signals[date]) if date in quant_signals else {}
        response = load_json(prompt_resp[date]) if date in prompt_resp else {}

        decision_signals = decision.get("signal_details") or []
        quant_signal_list = quant.get("signals") or []
        decision_tickers = signal_tickers(decision_signals)
        quant_tickers = signal_tickers(quant_signal_list)
        overlap = sorted(decision_tickers & quant_tickers)

        signals_presented = len(decision.get("signals_presented") or decision_signals)
        has_candidate_context = signals_presented > 0
        new_trade_locked = bool(decision.get("new_trade_locked"))
        ranking_eligible = bool(
            date in prompt_resp
            and date in decision_logs
            and has_candidate_context
            and not new_trade_locked
        )
        production_aligned = bool(ranking_eligible and date in quant_signals and overlap)
        effective = bool(production_aligned)

        if date in prompt_resp and date in decision_logs and date in quant_signals:
            full_triplet_dates.append(date)
        elif date in prompt_resp and date not in decision_logs and date not in quant_signals:
            prompt_only_dates.append(date)
        elif date in decision_logs and date not in prompt_resp:
            decision_only_dates.append(date)

        if has_candidate_context:
            candidate_context_dates.append(date)
            if date not in prompt_resp:
                candidate_context_missing_prompt.append(date)
            if date not in quant_signals:
                candidate_context_missing_quant.append(date)

        if effective:
            effective_dates.append(date)

        if date in raw_outputs and date not in prompt_resp:
            raw_recoverable_dates.append(date)

        has_any_context = date in decision_logs or date in quant_signals or date in clean_trade_news
        if has_any_context and date not in prompt_resp:
            context_only_dates.append(date)

        position_actions = response.get("position_actions") if isinstance(response, dict) else []
        if isinstance(position_actions, list):
            for action in position_actions:
                if isinstance(action, dict):
                    mode_counts[str(action.get("decision_mode") or "missing")] += 1

        new_trade_class = classify_new_trade(response.get("new_trade") if isinstance(response, dict) else None)
        if date in prompt_resp:
            new_trade_classes[new_trade_class] += 1

        totals["signals_presented"] += signals_presented
        totals["quant_signals"] += len(quant_signal_list)
        totals["effective_signals"] += len(overlap) if effective else 0
        if date in prompt_resp:
            totals["prompt_resp_days"] += 1
        if date in decision_logs:
            totals["decision_log_days"] += 1
        if date in quant_signals:
            totals["quant_signal_days"] += 1
        if has_candidate_context:
            totals["candidate_context_days"] += 1
        if ranking_eligible:
            totals["ranking_eligible_days"] += 1
        if production_aligned:
            totals["production_aligned_days"] += 1
        if effective:
            totals["effective_attribution_days"] += 1
        if new_trade_locked:
            totals["new_trade_locked_days"] += 1

        rows.append(
            {
                "date": date,
                "has_prompt_resp": date in prompt_resp,
                "has_decision_log": date in decision_logs,
                "has_quant_signals": date in quant_signals,
                "has_prompt_text": date in prompts,
                "has_raw_llm_output": date in raw_outputs,
                "signals_presented": signals_presented,
                "quant_signal_count": len(quant_signal_list),
                "decision_tickers": sorted(decision_tickers),
                "quant_tickers": sorted(quant_tickers),
                "overlap_tickers": overlap,
                "new_trade_locked": new_trade_locked,
                "ranking_eligible": ranking_eligible,
                "production_aligned": production_aligned,
                "effective_attribution": effective,
                "new_trade_class": new_trade_class if date in prompt_resp else "no_prompt_resp",
            }
        )

    baseline = load_json(baseline_path) if baseline_path.exists() else {}
    baseline_llm = baseline.get("llm_attribution") or {}
    baseline_known_bias = (baseline.get("known_biases") or {}).get("llm_gate_unreplayed") or {}

    summary = {
        "experiment_id": EXPERIMENT_ID,
        "lane": "measurement_repair",
        "change_type": "replay_fix",
        "single_causal_variable": "LLM replay attribution coverage",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "window": {"start": start, "end": end, "weekday_count": len(weekdays)},
        "alpha_hypothesis_blocked": (
            "LLM/event soft ranking or grading could improve candidate ordering, "
            "but it needs production-aligned replay samples before a strategy test."
        ),
        "strategy_behavior_changed": False,
        "audit_scope": {
            "prompt_resp_files": "data/llm_prompt_resp_YYYYMMDD.json",
            "decision_log_files": "data/llm_decision_log_YYYYMMDD.json",
            "production_candidate_files": "data/quant_signals_YYYYMMDD.json",
            "baseline_file": str(baseline_path),
        },
        "coverage": {
            "prompt_resp_days": totals["prompt_resp_days"],
            "decision_log_days": totals["decision_log_days"],
            "quant_signal_days": totals["quant_signal_days"],
            "full_triplet_days": len(full_triplet_dates),
            "raw_replay_day_coverage_vs_weekdays": pct(totals["prompt_resp_days"], len(weekdays)),
            "decision_log_day_coverage_vs_weekdays": pct(totals["decision_log_days"], len(weekdays)),
            "full_triplet_day_coverage_vs_weekdays": pct(len(full_triplet_dates), len(weekdays)),
        },
        "attribution_readiness": {
            "candidate_context_days": totals["candidate_context_days"],
            "candidate_context_signals_presented": totals["signals_presented"],
            "candidate_context_days_with_prompt_resp": (
                totals["candidate_context_days"] - len(candidate_context_missing_prompt)
            ),
            "candidate_context_days_with_quant_signals": (
                totals["candidate_context_days"] - len(candidate_context_missing_quant)
            ),
            "ranking_eligible_days": totals["ranking_eligible_days"],
            "production_aligned_days": totals["production_aligned_days"],
            "effective_attribution_days": totals["effective_attribution_days"],
            "effective_attribution_signals": totals["effective_signals"],
            "effective_day_fraction_of_candidate_context": pct(
                totals["effective_attribution_days"], totals["candidate_context_days"]
            ),
            "effective_signal_fraction_of_presented": pct(
                totals["effective_signals"], totals["signals_presented"]
            ),
        },
        "decision_shape": {
            "new_trade_classes": dict(sorted(new_trade_classes.items())),
            "position_action_decision_modes": dict(sorted(mode_counts.items())),
            "new_trade_locked_days": totals["new_trade_locked_days"],
        },
        "backlog": {
            "candidate_context_missing_prompt_resp": candidate_context_missing_prompt,
            "candidate_context_missing_quant_signals": candidate_context_missing_quant,
            "context_only_dates": context_only_dates,
            "prompt_only_dates": prompt_only_dates,
            "decision_only_dates": decision_only_dates,
            "raw_response_recoverable_without_prompt_resp": raw_recoverable_dates,
        },
        "date_sets": {
            "prompt_resp_dates": sorted(prompt_resp),
            "decision_log_dates": sorted(decision_logs),
            "quant_signal_dates": sorted(quant_signals),
            "full_triplet_dates": full_triplet_dates,
            "candidate_context_dates": candidate_context_dates,
            "effective_attribution_dates": effective_dates,
        },
        "baseline_backtest_llm_attribution": {
            "replay_enabled": baseline_llm.get("replay_enabled"),
            "coverage_fraction": baseline_llm.get("coverage_fraction"),
            "candidate_signal_coverage_fraction": baseline_llm.get(
                "candidate_signal_coverage_fraction"
            ),
            "effective_candidate_signal_fraction": (
                (baseline_llm.get("effective_attribution") or {}).get(
                    "effective_candidate_signal_fraction_of_total"
                )
            ),
            "known_bias_llm_gate_unreplayed": baseline_known_bias,
        },
        "interpretation": {
            "measurement_gap": (
                "Raw LLM prompt/response files are present for some recent days, "
                "but effective soft-ranking attribution requires candidate context, "
                "prompt/response, production quant signals, and ticker overlap on "
                "the same date."
            ),
            "closeout_expected": "observed_only",
            "next_alpha_unblocked_when": (
                "effective_attribution_days is large enough to compare LLM-ranked "
                "or LLM-vetoed candidates against non-vetoed candidates."
            ),
        },
        "rows": rows,
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=DEFAULT_END)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--baseline", default=str(DEFAULT_BASELINE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    audit = build_audit(
        start=args.start,
        end=args.end,
        data_dir=Path(args.data_dir),
        baseline_path=Path(args.baseline),
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        json.dump(audit, handle, indent=2, ensure_ascii=False, sort_keys=True)
        handle.write("\n")

    printable = {
        "experiment_id": audit["experiment_id"],
        "output": str(output),
        "coverage": audit["coverage"],
        "attribution_readiness": audit["attribution_readiness"],
        "strategy_behavior_changed": audit["strategy_behavior_changed"],
    }
    print(json.dumps(printable, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
