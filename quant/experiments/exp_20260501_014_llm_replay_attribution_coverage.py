"""Read-only LLM replay attribution coverage audit for exp-20260501-014."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260501-014"
DEFAULT_START = "2025-10-23"
DEFAULT_END = "2026-04-21"
DEFAULT_OUTPUT = Path(
    "data/experiments/exp-20260501-014/"
    "exp_20260501_014_llm_replay_attribution_coverage.json"
)
DEFAULT_BASELINE = Path("data/backtest_results_20260430.json")
PREVIOUS_AUDIT = Path(
    "data/experiments/exp-20260430-009/"
    "exp_20260430_009_llm_replay_attribution_coverage.json"
)


def iso_to_ymd(value: str) -> str:
    return datetime.strptime(value, "%Y-%m-%d").strftime("%Y%m%d")


def weekdays(start: str, end: str) -> list[str]:
    current = datetime.strptime(start, "%Y-%m-%d")
    final = datetime.strptime(end, "%Y-%m-%d")
    out: list[str] = []
    while current <= final:
        if current.weekday() < 5:
            out.append(current.strftime("%Y%m%d"))
        current += timedelta(days=1)
    return out


def date_from_path(path: Path) -> str | None:
    token = path.stem.rsplit("_", 1)[-1]
    if len(token) == 8 and token.isdigit():
        return token
    return None


def collect_files(data_dir: Path, pattern: str, start_ymd: str, end_ymd: str) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for path in sorted(data_dir.glob(pattern)):
        date = date_from_path(path)
        if date and start_ymd <= date <= end_ymd:
            out[date] = path
    return out


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def signal_tickers(signals: list[dict[str, Any]]) -> set[str]:
    tickers: set[str] = set()
    for signal in signals:
        if isinstance(signal, str):
            if signal.strip():
                tickers.add(signal.strip().upper())
            continue
        if not isinstance(signal, dict):
            continue
        ticker = signal.get("ticker") or signal.get("symbol")
        if ticker:
            tickers.add(str(ticker).strip().upper())
    return tickers


def advice_body(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    parsed = raw.get("advice_parsed")
    if isinstance(parsed, dict):
        return parsed
    return raw


def approved_tickers(raw: Any) -> set[str]:
    body = advice_body(raw)
    new_trade = body.get("new_trade")
    if not isinstance(new_trade, dict):
        return set()
    ticker = new_trade.get("ticker")
    if isinstance(ticker, str) and ticker.strip():
        return {ticker.strip().upper()}
    return set()


def classify_new_trade(raw: Any) -> str:
    body = advice_body(raw)
    value = body.get("new_trade") if isinstance(body, dict) else None
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
        ticker = value.get("ticker")
        if isinstance(ticker, str) and ticker.strip():
            return "structured_trade"
        action = str(value.get("action") or value.get("decision") or "").upper()
        if "NO" in action and "TRADE" in action:
            return "structured_no_trade"
        return "structured_unknown"
    return type(value).__name__


def fraction(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def metric_delta(current: dict[str, Any], previous: dict[str, Any], path: list[str]) -> int | float | None:
    cur: Any = current
    prev: Any = previous
    for key in path:
        if not isinstance(cur, dict) or not isinstance(prev, dict):
            return None
        cur = cur.get(key)
        prev = prev.get(key)
    if isinstance(cur, (int, float)) and isinstance(prev, (int, float)):
        return round(cur - prev, 6)
    return None


def build_audit(start: str, end: str, data_dir: Path, baseline_path: Path, previous_path: Path) -> dict[str, Any]:
    start_ymd = iso_to_ymd(start)
    end_ymd = iso_to_ymd(end)
    weekday_dates = weekdays(start, end)

    prompt_resp = collect_files(data_dir, "llm_prompt_resp_*.json", start_ymd, end_ymd)
    decision_logs = collect_files(data_dir, "llm_decision_log_*.json", start_ymd, end_ymd)
    quant_signals = collect_files(data_dir, "quant_signals_*.json", start_ymd, end_ymd)
    prompts = collect_files(data_dir, "llm_prompt_*.txt", start_ymd, end_ymd)
    raw_outputs = collect_files(data_dir, "llm_output_*.json", start_ymd, end_ymd)

    all_dates = sorted(set(prompt_resp) | set(decision_logs) | set(quant_signals) | set(prompts) | set(raw_outputs))

    rows: list[dict[str, Any]] = []
    totals = Counter()
    new_trade_shape = Counter()
    missing_archive_context_dates: list[str] = []
    candidate_context_missing_archive_context: list[str] = []
    candidate_context_missing_prompt_resp: list[str] = []
    candidate_context_missing_quant_signals: list[str] = []
    full_triplet_dates: list[str] = []
    effective_dates: list[str] = []
    approved_overlap_dates: list[str] = []

    for date in all_dates:
        decision = load_json(decision_logs[date]) if date in decision_logs else {}
        quant = load_json(quant_signals[date]) if date in quant_signals else {}
        response = load_json(prompt_resp[date]) if date in prompt_resp else {}

        response_context = response.get("archive_context") if isinstance(response, dict) else None
        has_archive_context = isinstance(response_context, dict)
        decision_signals = decision.get("signals_presented") or decision.get("signal_details") or []
        quant_signal_list = quant.get("signals") if isinstance(quant, dict) else []
        quant_signal_list = quant_signal_list or []
        decision_tickers = signal_tickers(decision_signals)
        quant_tickers = signal_tickers(quant_signal_list)
        overlap = sorted(decision_tickers & quant_tickers)
        approved = sorted(approved_tickers(response))

        signals_presented = len(decision_signals)
        candidate_context = signals_presented > 0
        context_ranking_eligible = response_context.get("ranking_eligible") if has_archive_context else None
        if not isinstance(context_ranking_eligible, bool):
            context_ranking_eligible = None
        new_trade_locked = response_context.get("new_trade_locked") if has_archive_context else decision.get("new_trade_locked")
        if not isinstance(new_trade_locked, bool):
            new_trade_locked = False

        ranking_eligible = bool(
            date in prompt_resp
            and candidate_context
            and has_archive_context
            and context_ranking_eligible is not False
            and not new_trade_locked
        )
        production_aligned = bool(ranking_eligible and date in quant_signals and overlap)
        effective = production_aligned

        if date in prompt_resp and not has_archive_context:
            missing_archive_context_dates.append(date)
        if date in prompt_resp and date in decision_logs and date in quant_signals:
            full_triplet_dates.append(date)
        if candidate_context:
            totals["candidate_context_days"] += 1
            totals["candidate_context_signals_presented"] += signals_presented
            if date not in prompt_resp:
                candidate_context_missing_prompt_resp.append(date)
            if not has_archive_context:
                candidate_context_missing_archive_context.append(date)
            if date not in quant_signals:
                candidate_context_missing_quant_signals.append(date)
        if effective:
            effective_dates.append(date)
            totals["effective_attribution_signals"] += len(overlap)
        if approved and set(approved) & set(overlap):
            approved_overlap_dates.append(date)

        if date in prompt_resp:
            new_trade_shape[classify_new_trade(response)] += 1

        totals["prompt_resp_days"] += int(date in prompt_resp)
        totals["prompt_resp_days_with_archive_context"] += int(date in prompt_resp and has_archive_context)
        totals["decision_log_days"] += int(date in decision_logs)
        totals["quant_signal_days"] += int(date in quant_signals)
        totals["ranking_eligible_days"] += int(ranking_eligible)
        totals["production_aligned_days"] += int(production_aligned)
        totals["effective_attribution_days"] += int(effective)

        rows.append(
            {
                "date": date,
                "has_prompt_resp": date in prompt_resp,
                "has_archive_context": has_archive_context,
                "has_decision_log": date in decision_logs,
                "has_quant_signals": date in quant_signals,
                "signals_presented": signals_presented,
                "decision_tickers": sorted(decision_tickers),
                "quant_tickers": sorted(quant_tickers),
                "overlap_tickers": overlap,
                "approved_tickers": approved,
                "candidate_context": candidate_context,
                "archive_ranking_eligible": context_ranking_eligible,
                "new_trade_locked": new_trade_locked,
                "ranking_eligible": ranking_eligible,
                "production_aligned": production_aligned,
                "effective_attribution": effective,
                "new_trade_shape": classify_new_trade(response) if date in prompt_resp else "no_prompt_resp",
            }
        )

    baseline = load_json(baseline_path) if baseline_path.exists() else {}
    baseline_llm = baseline.get("llm_attribution") or {}
    previous = load_json(previous_path) if previous_path.exists() else {}

    coverage = {
        "weekday_count": len(weekday_dates),
        "prompt_resp_days": totals["prompt_resp_days"],
        "prompt_resp_days_with_archive_context": totals["prompt_resp_days_with_archive_context"],
        "prompt_resp_archive_context_fraction": fraction(
            totals["prompt_resp_days_with_archive_context"], totals["prompt_resp_days"]
        ),
        "decision_log_days": totals["decision_log_days"],
        "quant_signal_days": totals["quant_signal_days"],
        "full_triplet_days": len(full_triplet_dates),
        "raw_replay_day_coverage_vs_weekdays": fraction(totals["prompt_resp_days"], len(weekday_dates)),
        "full_triplet_day_coverage_vs_weekdays": fraction(len(full_triplet_dates), len(weekday_dates)),
    }
    readiness = {
        "candidate_context_days": totals["candidate_context_days"],
        "candidate_context_signals_presented": totals["candidate_context_signals_presented"],
        "candidate_context_days_with_prompt_resp": (
            totals["candidate_context_days"] - len(candidate_context_missing_prompt_resp)
        ),
        "candidate_context_days_with_archive_context": (
            totals["candidate_context_days"] - len(candidate_context_missing_archive_context)
        ),
        "candidate_context_days_with_quant_signals": (
            totals["candidate_context_days"] - len(candidate_context_missing_quant_signals)
        ),
        "ranking_eligible_days": totals["ranking_eligible_days"],
        "production_aligned_days": totals["production_aligned_days"],
        "effective_attribution_days": totals["effective_attribution_days"],
        "effective_attribution_signals": totals["effective_attribution_signals"],
        "effective_day_fraction_of_candidate_context": fraction(
            totals["effective_attribution_days"], totals["candidate_context_days"]
        ),
        "effective_signal_fraction_of_presented": fraction(
            totals["effective_attribution_signals"], totals["candidate_context_signals_presented"]
        ),
    }

    return {
        "experiment_id": EXPERIMENT_ID,
        "lane": "measurement_repair",
        "change_type": "replay_fix",
        "single_causal_variable": "LLM replay attribution coverage",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "window": {"start": start, "end": end},
        "alpha_hypothesis_blocked": (
            "event/LLM ranking alpha: use prompt-time semantic judgement to rank or grade "
            "existing candidates before scarce-slot allocation."
        ),
        "why_not_alpha_now": (
            "The auditable sample is still too small and some recent prompt responses lack "
            "archive_context, so a ranking alpha test would mix real prompt-time decisions "
            "with unauditable bare advice files."
        ),
        "strategy_behavior_changed": False,
        "coverage": coverage,
        "attribution_readiness": readiness,
        "decision_shape": {
            "new_trade_shapes": dict(sorted(new_trade_shape.items())),
            "approved_overlap_dates": approved_overlap_dates,
        },
        "measurement_gap_queue": {
            "prompt_resp_missing_archive_context": missing_archive_context_dates,
            "candidate_context_missing_archive_context": candidate_context_missing_archive_context,
            "candidate_context_missing_prompt_resp": candidate_context_missing_prompt_resp,
            "candidate_context_missing_quant_signals": candidate_context_missing_quant_signals,
        },
        "date_sets": {
            "full_triplet_dates": full_triplet_dates,
            "effective_attribution_dates": effective_dates,
            "prompt_resp_dates": sorted(prompt_resp),
            "decision_log_dates": sorted(decision_logs),
            "quant_signal_dates": sorted(quant_signals),
        },
        "baseline_backtest_llm_attribution": {
            "baseline_file": str(baseline_path),
            "replay_enabled": baseline_llm.get("replay_enabled"),
            "candidate_signals_total": baseline_llm.get("candidate_signals_total"),
            "candidate_signal_coverage_fraction": baseline_llm.get("candidate_signal_coverage_fraction"),
            "effective_candidate_signal_fraction": (
                (baseline_llm.get("effective_attribution") or {}).get(
                    "effective_candidate_signal_fraction_of_total"
                )
            ),
        },
        "comparison_to_previous_audit": {
            "previous_audit": str(previous_path),
            "prompt_resp_days_delta": metric_delta({"coverage": coverage}, previous, ["coverage", "prompt_resp_days"]),
            "full_triplet_days_delta": metric_delta({"coverage": coverage}, previous, ["coverage", "full_triplet_days"]),
            "effective_attribution_days_delta": metric_delta(
                {"attribution_readiness": readiness},
                previous,
                ["attribution_readiness", "effective_attribution_days"],
            ),
            "effective_attribution_signals_delta": metric_delta(
                {"attribution_readiness": readiness},
                previous,
                ["attribution_readiness", "effective_attribution_signals"],
            ),
        },
        "readiness_verdict": {
            "status": "blocked",
            "reason": (
                "Effective attribution is still only a tiny historical sample; continue "
                "persisting archive_context with prompt responses before testing "
                "event/LLM ranking alpha."
            ),
            "minimum_next_step": (
                "Ensure every future llm_prompt_resp_YYYYMMDD.json includes archive_context "
                "with signals_presented, ranking_eligible, and new_trade_locked."
            ),
        },
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=DEFAULT_END)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--baseline", default=str(DEFAULT_BASELINE))
    parser.add_argument("--previous-audit", default=str(PREVIOUS_AUDIT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    audit = build_audit(
        start=args.start,
        end=args.end,
        data_dir=Path(args.data_dir),
        baseline_path=Path(args.baseline),
        previous_path=Path(args.previous_audit),
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
        "measurement_gap_queue": audit["measurement_gap_queue"],
        "readiness_verdict": audit["readiness_verdict"],
    }
    print(json.dumps(printable, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
