"""Read-only LLM replay attribution coverage audit for exp-20260509-022.

This script produces the measurement artifact promised by the ticket. It is
deliberately tolerant of mixed historical LLM output schemas: the audit counts
usable prompt/response evidence without treating response-shape differences as
strategy defects.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260509-022"
DEFAULT_START = "2025-10-23"
DEFAULT_END = "2026-04-21"
DEFAULT_BASELINE = Path("data/backtest_results_20260509.json")
DEFAULT_OUTPUT = Path(
    "data/experiments/exp-20260509-022/"
    "exp_20260509_022_llm_replay_attribution_coverage.json"
)
RELATED_PRIOR_ARTIFACTS = [
    "data/experiments/exp-20260430-009/exp_20260430_009_llm_replay_attribution_coverage.json",
    "data/experiments/exp-20260501-014/exp_20260501_014_llm_replay_attribution_coverage.json",
    "data/experiments/exp-20260505-027/exp_20260505_027_llm_event_replay_coverage_manifest.json",
    "data/experiments/exp-20260506-027/exp_20260506_027_llm_event_replay_readiness_manifest.json",
    "data/experiments/exp-20260507-902/exp_20260507_902_llm_replay_attribution_coverage.json",
    "data/experiments/exp-20260508-030/exp_20260508_030_llm_event_readiness_manifest.json",
]


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def try_load_json(path: Path) -> tuple[Any, str | None]:
    try:
        return load_json(path), None
    except Exception as exc:  # noqa: BLE001 - audit should record, not fail.
        return None, str(exc)


def date_token(path: Path) -> str | None:
    token = path.stem.rsplit("_", 1)[-1]
    if len(token) == 8 and token.isdigit():
        return token
    return None


def ymd_to_iso(token: str) -> str:
    return f"{token[:4]}-{token[4:6]}-{token[6:]}"


def iso_to_ymd(value: str) -> str:
    return value.replace("-", "")


def weekday_tokens(start: str, end: str) -> list[str]:
    current = datetime.strptime(start, "%Y-%m-%d")
    final = datetime.strptime(end, "%Y-%m-%d")
    out: list[str] = []
    while current <= final:
        if current.weekday() < 5:
            out.append(current.strftime("%Y%m%d"))
        current += timedelta(days=1)
    return out


def collect_dated_files(data_dir: Path, pattern: str, start_ymd: str, end_ymd: str) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for path in sorted(data_dir.glob(pattern)):
        token = date_token(path)
        if token and start_ymd <= token <= end_ymd:
            out[token] = path
    return out


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def signal_tickers(signals: list[Any]) -> set[str]:
    tickers: set[str] = set()
    for signal in signals:
        if isinstance(signal, str):
            ticker = signal.strip().upper()
            if ticker:
                tickers.add(ticker)
            continue
        if not isinstance(signal, dict):
            continue
        ticker = signal.get("ticker") or signal.get("symbol")
        if isinstance(ticker, str) and ticker.strip():
            tickers.add(ticker.strip().upper())
    return tickers


def parsed_advice(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    parsed = payload.get("advice_parsed")
    if isinstance(parsed, dict):
        return parsed
    raw = payload.get("advice_raw")
    if isinstance(raw, str) and raw.strip():
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            decoded = None
        if isinstance(decoded, dict):
            return decoded
    return payload


def new_trade_shape(payload: Any) -> str:
    body = parsed_advice(payload)
    value = body.get("new_trade") if isinstance(body, dict) else None
    if value is None:
        return "missing"
    if isinstance(value, str):
        normalized = value.strip().upper()
        if not normalized:
            return "empty_string"
        if "NO NEW TRADE" in normalized or "NO_TRADE" in normalized or normalized == "NONE":
            return "no_new_trade_text"
        return "trade_or_reason_text"
    if isinstance(value, dict):
        ticker = value.get("ticker")
        if isinstance(ticker, str) and ticker.strip():
            return "structured_trade"
        action = str(value.get("action") or value.get("decision") or "").upper()
        if "NO" in action and "TRADE" in action:
            return "structured_no_trade"
        return "structured_unknown"
    if isinstance(value, list):
        return "list"
    return type(value).__name__


def approved_tickers(payload: Any) -> set[str]:
    body = parsed_advice(payload)
    value = body.get("new_trade") if isinstance(body, dict) else None
    if isinstance(value, dict):
        ticker = value.get("ticker")
        if isinstance(ticker, str) and ticker.strip():
            return {ticker.strip().upper()}
    if isinstance(value, list):
        out: set[str] = set()
        for item in value:
            out.update(approved_tickers({"new_trade": item}))
        return out
    return set()


def archive_context(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    context = payload.get("archive_context")
    return context if isinstance(context, dict) else {}


def count_context_signals(context: dict[str, Any]) -> int:
    count = context.get("signals_presented_count")
    if isinstance(count, int):
        return count
    signals = context.get("signals_presented")
    return len(signals) if isinstance(signals, list) else 0


def metric_subset(result: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "expected_value_score",
        "total_return_pct",
        "sharpe_daily",
        "max_drawdown_pct",
        "worst_trade_pct",
        "max_consecutive_losses",
        "tail_loss_share",
        "total_pnl",
        "win_rate",
        "total_trades",
        "signals_generated",
        "signals_survived",
        "survival_rate",
    ]
    return {key: result.get(key) for key in keys if key in result}


def fraction(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def build_audit(start: str, end: str, data_dir: Path, baseline_path: Path) -> dict[str, Any]:
    start_ymd = iso_to_ymd(start)
    end_ymd = iso_to_ymd(end)
    expected_weekdays = weekday_tokens(start, end)
    expected_set = set(expected_weekdays)

    prompt_resp = collect_dated_files(data_dir, "llm_prompt_resp_*.json", start_ymd, end_ymd)
    decision_logs = collect_dated_files(data_dir, "llm_decision_log_*.json", start_ymd, end_ymd)
    prompts = collect_dated_files(data_dir, "llm_prompt_*.txt", start_ymd, end_ymd)
    raw_outputs = collect_dated_files(data_dir, "llm_output_*.json", start_ymd, end_ymd)
    quant_signals = collect_dated_files(data_dir, "quant_signals_*.json", start_ymd, end_ymd)
    clean_trade_news = collect_dated_files(data_dir, "clean_trade_news_*.json", start_ymd, end_ymd)
    clean_news = collect_dated_files(data_dir, "clean_news_*.json", start_ymd, end_ymd)
    earnings = collect_dated_files(data_dir, "earnings_snapshot_*.json", start_ymd, end_ymd)

    dates = sorted(
        set(prompt_resp)
        | set(decision_logs)
        | set(prompts)
        | set(raw_outputs)
        | set(quant_signals)
    )

    rows: list[dict[str, Any]] = []
    totals = Counter()
    shapes = Counter()
    parse_errors: list[dict[str, str]] = []
    missing_archive_context_dates: list[str] = []
    candidate_dates_missing_prompt_resp: list[str] = []
    candidate_dates_missing_archive_context: list[str] = []
    candidate_dates_missing_quant_signals: list[str] = []
    effective_dates: list[str] = []
    approved_overlap_dates: list[str] = []

    for token in dates:
        response_payload: Any = {}
        response_error: str | None = None
        if token in prompt_resp:
            response_payload, response_error = try_load_json(prompt_resp[token])
            if response_error:
                parse_errors.append({"date": ymd_to_iso(token), "file": str(prompt_resp[token]), "error": response_error})

        decision_payload: Any = {}
        if token in decision_logs:
            decision_payload, decision_error = try_load_json(decision_logs[token])
            if decision_error:
                parse_errors.append({"date": ymd_to_iso(token), "file": str(decision_logs[token]), "error": decision_error})

        quant_payload: Any = {}
        if token in quant_signals:
            quant_payload, quant_error = try_load_json(quant_signals[token])
            if quant_error:
                parse_errors.append({"date": ymd_to_iso(token), "file": str(quant_signals[token]), "error": quant_error})

        context = archive_context(response_payload)
        decision = as_dict(decision_payload)
        quant = as_dict(quant_payload)
        decision_signals = as_list(decision.get("signals_presented") or decision.get("signal_details"))
        quant_signal_list = as_list(quant.get("signals"))
        decision_tickers = signal_tickers(decision_signals)
        quant_tickers = signal_tickers(quant_signal_list)
        context_signal_count = count_context_signals(context)
        signals_presented = len(decision_signals) or context_signal_count
        candidate_context = signals_presented > 0
        overlap = sorted(decision_tickers & quant_tickers)
        approved = sorted(approved_tickers(response_payload))
        has_archive_context = bool(context)
        ranking_eligible = context.get("ranking_eligible") if has_archive_context else None
        new_trade_locked = context.get("new_trade_locked") if has_archive_context else decision.get("new_trade_locked")

        # Effective attribution is intentionally conservative: prompt-time context
        # must exist, Task A must be eligible, and saved production candidates must
        # overlap the decision log. Response wording itself is not a blocker.
        effective = bool(
            candidate_context
            and has_archive_context
            and ranking_eligible is True
            and new_trade_locked is not True
            and token in quant_signals
            and overlap
        )

        if token in prompt_resp:
            shape = new_trade_shape(response_payload)
            shapes[shape] += 1
            totals["usable_prompt_response_files"] += int(response_error is None and shape != "missing")
            if not has_archive_context:
                missing_archive_context_dates.append(token)

        if candidate_context:
            totals["candidate_context_days"] += 1
            totals["candidate_context_signals_presented"] += signals_presented
            if token not in prompt_resp:
                candidate_dates_missing_prompt_resp.append(token)
            if not has_archive_context:
                candidate_dates_missing_archive_context.append(token)
            if token not in quant_signals:
                candidate_dates_missing_quant_signals.append(token)

        if effective:
            effective_dates.append(token)
            totals["effective_attribution_signals"] += len(overlap)
        if approved and set(approved) & set(overlap):
            approved_overlap_dates.append(token)

        totals["prompt_resp_days"] += int(token in prompt_resp)
        totals["decision_log_days"] += int(token in decision_logs)
        totals["prompt_txt_days"] += int(token in prompts)
        totals["raw_output_days"] += int(token in raw_outputs)
        totals["quant_signal_days"] += int(token in quant_signals)
        totals["archive_context_days"] += int(has_archive_context)
        totals["full_prompt_response_decision_quant_days"] += int(
            token in prompt_resp and token in decision_logs and token in quant_signals
        )
        totals["ranking_eligible_days"] += int(ranking_eligible is True)
        totals["ranking_locked_days"] += int(new_trade_locked is True)
        totals["effective_attribution_days"] += int(effective)

        rows.append(
            {
                "date": ymd_to_iso(token),
                "has_prompt_resp": token in prompt_resp,
                "has_prompt_txt": token in prompts,
                "has_raw_output": token in raw_outputs,
                "has_decision_log": token in decision_logs,
                "has_quant_signals": token in quant_signals,
                "has_archive_context": has_archive_context,
                "signals_presented": signals_presented,
                "decision_tickers": sorted(decision_tickers),
                "quant_tickers": sorted(quant_tickers),
                "overlap_tickers": overlap,
                "approved_tickers": approved,
                "candidate_context": candidate_context,
                "archive_ranking_eligible": ranking_eligible,
                "new_trade_locked": new_trade_locked,
                "effective_attribution": effective,
                "new_trade_shape": new_trade_shape(response_payload) if token in prompt_resp else "no_prompt_resp",
            }
        )

    baseline = load_json(baseline_path) if baseline_path.exists() else {}
    baseline_llm = as_dict(baseline.get("llm_attribution"))
    baseline_effective = as_dict(baseline_llm.get("effective_attribution"))
    baseline_context = as_dict(baseline_llm.get("context_alignment"))
    missing_by_file_type = {
        "llm_prompt_resp": [ymd_to_iso(d) for d in expected_weekdays if d not in prompt_resp],
        "llm_decision_log": [ymd_to_iso(d) for d in expected_weekdays if d not in decision_logs],
        "llm_prompt_txt": [ymd_to_iso(d) for d in expected_weekdays if d not in prompts],
        "llm_raw_output": [ymd_to_iso(d) for d in expected_weekdays if d not in raw_outputs],
        "quant_signals": [ymd_to_iso(d) for d in expected_weekdays if d not in quant_signals],
    }

    coverage = {
        "expected_weekdays": len(expected_weekdays),
        "prompt_resp_days": totals["prompt_resp_days"],
        "decision_log_days": totals["decision_log_days"],
        "prompt_txt_days": totals["prompt_txt_days"],
        "raw_output_days": totals["raw_output_days"],
        "quant_signal_days": totals["quant_signal_days"],
        "clean_trade_news_days": len(clean_trade_news),
        "clean_news_days": len(clean_news),
        "earnings_snapshot_days": len(earnings),
        "archive_context_days": totals["archive_context_days"],
        "full_prompt_response_decision_quant_days": totals["full_prompt_response_decision_quant_days"],
        "prompt_resp_coverage_vs_weekdays": fraction(totals["prompt_resp_days"], len(expected_weekdays)),
        "decision_log_coverage_vs_weekdays": fraction(totals["decision_log_days"], len(expected_weekdays)),
        "quant_signal_coverage_vs_weekdays": fraction(totals["quant_signal_days"], len(expected_weekdays)),
        "full_triplet_coverage_vs_weekdays": fraction(
            totals["full_prompt_response_decision_quant_days"],
            len(expected_weekdays),
        ),
        "archive_context_fraction_of_prompt_resp": fraction(
            totals["archive_context_days"],
            totals["prompt_resp_days"],
        ),
    }
    prompt_response_quality = {
        "usable_prompt_response_count": totals["usable_prompt_response_files"],
        "parse_error_count": len(parse_errors),
        "new_trade_shapes": dict(sorted(shapes.items())),
        "parse_errors": parse_errors,
    }
    attribution_readiness = {
        "candidate_context_days": totals["candidate_context_days"],
        "candidate_context_signals_presented": totals["candidate_context_signals_presented"],
        "candidate_days_with_prompt_resp": totals["candidate_context_days"] - len(candidate_dates_missing_prompt_resp),
        "candidate_days_with_archive_context": totals["candidate_context_days"]
        - len(candidate_dates_missing_archive_context),
        "candidate_days_with_quant_signals": totals["candidate_context_days"] - len(candidate_dates_missing_quant_signals),
        "ranking_eligible_days": totals["ranking_eligible_days"],
        "ranking_locked_days": totals["ranking_locked_days"],
        "effective_attribution_days": totals["effective_attribution_days"],
        "effective_attribution_signals": totals["effective_attribution_signals"],
        "effective_day_fraction_of_candidate_context": fraction(
            totals["effective_attribution_days"],
            totals["candidate_context_days"],
        ),
        "effective_signal_fraction_of_presented": fraction(
            totals["effective_attribution_signals"],
            totals["candidate_context_signals_presented"],
        ),
        "approved_overlap_dates": [ymd_to_iso(d) for d in approved_overlap_dates],
    }

    blockers = []
    released = [
        "The current coverage state is now reproducible from a single per-ticket JSON artifact.",
        "LLM output schema inconsistency is classified as response shape, not a strategy blocker.",
    ]
    if totals["effective_attribution_days"] < 5:
        blockers.append(
            "LLM/event ranking alpha remains blocked: fewer than 5 production-aligned effective candidate days."
        )
    if totals["effective_attribution_signals"] == 0:
        blockers.append(
            "No effective prompt-time candidate signals can be joined to saved quant candidate overlap."
        )
    if baseline_effective.get("effective_candidate_signals", 0) == 0:
        blockers.append(
            "The current baseline backtest also reports zero effective LLM candidate signals."
        )

    return {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "measurement_repair",
        "change_type": "replay_fix",
        "single_causal_variable": "LLM replay attribution coverage",
        "date_range": {"start": start, "end": end},
        "baseline_result_file": str(baseline_path).replace("\\", "/"),
        "baseline_period": baseline.get("period"),
        "baseline_metrics": metric_subset(baseline),
        "after_metrics": metric_subset(baseline),
        "expected_value_score_delta": 0.0,
        "strategy_behavior_changed": False,
        "coverage": coverage,
        "prompt_response_quality": prompt_response_quality,
        "attribution_readiness": attribution_readiness,
        "missing_dates": missing_by_file_type,
        "missing_or_unusable_candidate_context": {
            "prompt_resp_missing_archive_context": [ymd_to_iso(d) for d in missing_archive_context_dates],
            "candidate_context_missing_prompt_resp": [ymd_to_iso(d) for d in candidate_dates_missing_prompt_resp],
            "candidate_context_missing_archive_context": [ymd_to_iso(d) for d in candidate_dates_missing_archive_context],
            "candidate_context_missing_quant_signals": [ymd_to_iso(d) for d in candidate_dates_missing_quant_signals],
        },
        "date_sets": {
            "prompt_resp_dates": [ymd_to_iso(d) for d in sorted(prompt_resp)],
            "decision_log_dates": [ymd_to_iso(d) for d in sorted(decision_logs)],
            "quant_signal_dates": [ymd_to_iso(d) for d in sorted(quant_signals)],
            "effective_attribution_dates": [ymd_to_iso(d) for d in effective_dates],
        },
        "baseline_backtest_llm_attribution": {
            "replay_enabled": baseline_llm.get("replay_enabled"),
            "candidate_signals_total": baseline_llm.get("candidate_signals_total"),
            "candidate_signals_covered": baseline_llm.get("candidate_signals_covered"),
            "candidate_signal_coverage_fraction": baseline_llm.get("candidate_signal_coverage_fraction"),
            "ranking_eligible_aligned_days": baseline_context.get("ranking_eligible_aligned_days"),
            "ranking_eligible_aligned_signals": baseline_context.get("ranking_eligible_aligned_signals"),
            "effective_candidate_days": baseline_effective.get("effective_candidate_days"),
            "effective_candidate_signals": baseline_effective.get("effective_candidate_signals"),
        },
        "alpha_hypothesis_status": {
            "hypothesis": (
                "LLM/event semantic grading could improve scarce-slot candidate ranking "
                "once prompt-time candidate context and responses can be joined to outcomes."
            ),
            "blocked": blockers,
            "unblocked": released,
            "next_alpha_when_unblocked": (
                "Run a separate default-off ranking replay that compares LLM/event graded "
                "candidate selections against same-day rejected candidates with forward outcomes."
            ),
        },
        "historical_constraints": {
            "related_prior_artifacts": RELATED_PRIOR_ARTIFACTS,
            "why_this_is_not_a_repeated_alpha_test": (
                "This is an observed-only current coverage checkpoint. It does not retune "
                "thresholds, change LLM authority, or alter entries, exits, ranking, sizing, "
                "risk, filters, or orders."
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
        "gate4": {
            "applicable": False,
            "reason": "Observed-only measurement artifact; strategy behavior and backtest metrics are unchanged.",
        },
        "rows": rows,
    }


def main() -> int:
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
    output.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "experiment_id": audit["experiment_id"],
                "output": str(output).replace("\\", "/"),
                "coverage": audit["coverage"],
                "prompt_response_quality": audit["prompt_response_quality"],
                "attribution_readiness": audit["attribution_readiness"],
                "alpha_hypothesis_status": audit["alpha_hypothesis_status"],
                "strategy_behavior_changed": audit["strategy_behavior_changed"],
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
