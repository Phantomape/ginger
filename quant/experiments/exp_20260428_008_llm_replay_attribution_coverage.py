"""Audit LLM replay attribution coverage for exp-20260428-008.

This is a read-only measurement artifact. It inventories existing LLM response
archives, prompt-time context, and decision-log sidecars so the next LLM/event
ranking alpha test can use a stable denominator instead of headline file counts.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from quant.llm_replay import get_llm_decision_for_date


EXPERIMENT_ID = "exp-20260428-008"
DEFAULT_START = "2025-10-23"
DEFAULT_END = "2026-04-21"


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _date_from_stem(path: Path, prefix: str) -> date:
    stamp = path.stem.replace(prefix, "")
    return datetime.strptime(stamp, "%Y%m%d").date()


def _load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return {"_json_error": True}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _advice_body(raw: dict[str, Any]) -> dict[str, Any]:
    parsed = raw.get("advice_parsed")
    return parsed if isinstance(parsed, dict) else raw


def _approved_ticker(raw: dict[str, Any]) -> str | None:
    new_trade = _advice_body(raw).get("new_trade")
    if isinstance(new_trade, dict):
        ticker = new_trade.get("ticker")
        if isinstance(ticker, str) and ticker.strip():
            return ticker.strip().upper()
    return None


def _normalize_tickers(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return sorted(
        {
            value.strip().upper()
            for value in values
            if isinstance(value, str) and value.strip()
        }
    )


def _decision_log_context(data_dir: Path, stamp: str) -> dict[str, Any]:
    raw = _as_dict(_load_json(data_dir / f"llm_decision_log_{stamp}.json"))
    if not raw:
        return {
            "decision_log_present": False,
            "decision_log_candidate_count": None,
            "decision_log_ranking_eligible": None,
            "decision_log_new_trade_locked": None,
            "decision_log_tickers": [],
        }

    signals_presented = _normalize_tickers(raw.get("signals_presented"))
    count = raw.get("signals_presented_count")
    if not isinstance(count, int):
        count = len(signals_presented)
    ranking_eligible = bool(count > 0 and raw.get("new_trade_locked") is not True)

    return {
        "decision_log_present": True,
        "decision_log_candidate_count": count,
        "decision_log_ranking_eligible": ranking_eligible,
        "decision_log_new_trade_locked": raw.get("new_trade_locked"),
        "decision_log_has_actionable_news": raw.get("has_actionable_news"),
        "decision_log_tickers": signals_presented,
        "decision_log_news_summary": raw.get("news_summary"),
    }


def _prior_manifest_summary(path: Path) -> dict[str, Any]:
    raw = _as_dict(_load_json(path))
    return _as_dict(raw.get("summary"))


def build_artifact(
    data_dir: Path,
    baseline_file: Path,
    prior_manifest: Path,
    start: date,
    end: date,
) -> dict[str, Any]:
    baseline = _as_dict(_load_json(baseline_file))
    baseline_llm = _as_dict(baseline.get("llm_attribution"))
    baseline_effective = _as_dict(baseline_llm.get("effective_attribution"))
    prior_summary = _prior_manifest_summary(prior_manifest)

    samples: list[dict[str, Any]] = []
    for response_path in sorted(data_dir.glob("llm_prompt_resp_????????.json")):
        sample_date = _date_from_stem(response_path, "llm_prompt_resp_")
        stamp = sample_date.strftime("%Y%m%d")
        raw = _as_dict(_load_json(response_path))
        replay_decision = get_llm_decision_for_date(stamp, data_dir=str(data_dir))
        sidecar = _decision_log_context(data_dir, stamp)
        approved = _approved_ticker(raw)
        presented = _normalize_tickers(replay_decision.get("signals_presented"))
        sidecar_tickers = sidecar["decision_log_tickers"]
        context_present = replay_decision.get("archive_context_present") is True
        ranking_eligible = replay_decision.get("ranking_eligible")
        replay_ready = (
            context_present
            and ranking_eligible is True
            and bool(presented)
            and approved in presented
        )
        sidecar_backfill_candidate = (
            not context_present
            and sidecar["decision_log_present"]
            and bool(sidecar_tickers)
        )

        if replay_ready:
            classification = "production_aligned_ranking_ready"
        elif context_present and ranking_eligible is False:
            classification = "covered_but_not_ranking_eligible"
        elif sidecar_backfill_candidate:
            classification = "sidecar_backfill_candidate"
        elif not context_present:
            classification = "legacy_response_missing_context"
        else:
            classification = "covered_unknown_ranking_value"

        samples.append(
            {
                "date": sample_date.isoformat(),
                "date_str": stamp,
                "file": str(response_path).replace("\\", "/"),
                "in_evaluation_window": start <= sample_date <= end,
                "archive_context_present": context_present,
                "ranking_eligible": ranking_eligible,
                "new_trade_locked": replay_decision.get("new_trade_locked"),
                "signals_presented": presented,
                "signals_presented_count": replay_decision.get("signals_presented_count"),
                "approved_ticker": approved,
                "approved_in_presented": approved in presented if approved else False,
                "decision_log_present": sidecar["decision_log_present"],
                "decision_log_candidate_count": sidecar["decision_log_candidate_count"],
                "decision_log_ranking_eligible": sidecar["decision_log_ranking_eligible"],
                "decision_log_new_trade_locked": sidecar["decision_log_new_trade_locked"],
                "decision_log_tickers": sidecar_tickers,
                "decision_log_has_actionable_news": sidecar.get("decision_log_has_actionable_news"),
                "decision_log_news_summary": sidecar.get("decision_log_news_summary"),
                "classification": classification,
                "usable_for_soft_ranking_attribution": replay_ready and start <= sample_date <= end,
            }
        )

    in_window = [sample for sample in samples if sample["in_evaluation_window"]]
    ranking_ready = [sample for sample in in_window if sample["usable_for_soft_ranking_attribution"]]
    missing_context = [
        sample
        for sample in in_window
        if sample["classification"] == "legacy_response_missing_context"
    ]
    backfill_candidates = [
        sample
        for sample in in_window
        if sample["classification"] == "sidecar_backfill_candidate"
    ]

    current_summary = {
        "replay_files_total": len(samples),
        "replay_files_in_window": len(in_window),
        "archive_context_present_total": sum(1 for sample in samples if sample["archive_context_present"]),
        "archive_context_present_in_window": sum(1 for sample in in_window if sample["archive_context_present"]),
        "decision_log_sidecars_total": sum(1 for sample in samples if sample["decision_log_present"]),
        "decision_log_sidecars_in_window": sum(1 for sample in in_window if sample["decision_log_present"]),
        "ranking_ready_days_in_window": len(ranking_ready),
        "ranking_ready_presented_signals_in_window": sum(
            len(sample["signals_presented"]) for sample in ranking_ready
        ),
        "legacy_missing_context_days_in_window": len(missing_context),
        "legacy_missing_context_dates_in_window": [sample["date"] for sample in missing_context],
        "sidecar_backfill_candidate_days_in_window": len(backfill_candidates),
        "sidecar_backfill_candidate_dates_in_window": [sample["date"] for sample in backfill_candidates],
        "covered_but_not_ranking_eligible_days_in_window": sum(
            1 for sample in in_window if sample["classification"] == "covered_but_not_ranking_eligible"
        ),
        "baseline_replay_enabled": baseline_llm.get("replay_enabled"),
        "baseline_candidate_signals_total": baseline_llm.get("candidate_signals_total"),
        "baseline_effective_candidate_days": baseline_effective.get("effective_candidate_days"),
        "baseline_effective_candidate_signals": baseline_effective.get("effective_candidate_signals"),
    }

    summary_delta = {
        key: current_summary.get(key, 0) - prior_summary.get(old_key, 0)
        for key, old_key in {
            "replay_files_total": "replay_files_total",
            "replay_files_in_window": "replay_files_in_window",
            "archive_context_present_in_window": "archive_context_present_in_window",
            "ranking_ready_days_in_window": "aligned_ranking_sample_days_in_window",
            "ranking_ready_presented_signals_in_window": "aligned_ranking_sample_signals_in_window",
        }.items()
        if isinstance(current_summary.get(key), int) and isinstance(prior_summary.get(old_key), int)
    }

    return {
        "experiment_id": EXPERIMENT_ID,
        "artifact_type": "llm_replay_attribution_coverage_audit",
        "strategy_behavior_changed": False,
        "evaluation_window": {"start": start.isoformat(), "end": end.isoformat()},
        "baseline_file": str(baseline_file).replace("\\", "/"),
        "prior_manifest_file": str(prior_manifest).replace("\\", "/"),
        "summary": current_summary,
        "delta_vs_prior_manifest": summary_delta,
        "samples": samples,
        "blocked_alpha_hypothesis": {
            "alpha_hypothesis": "LLM/event soft ranking can improve scarce-slot allocation among code-surviving candidates.",
            "why_not_now": (
                "Only production-aligned ranking-ready samples should be used. "
                "The current fixed window still has three usable days and eight "
                "presented signals; legacy missing-context days cannot be inferred."
            ),
        },
        "decision_guidance": [
            "Do not count dated LLM response files as ranking-ready samples unless archive_context is present.",
            "Do not treat covered-but-not-ranking-eligible days as LLM ranking evidence.",
            "Do not backfill legacy missing-context days unless a sidecar has candidate tickers.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--baseline", default="data/backtest_results_20260427.json")
    parser.add_argument(
        "--prior-manifest",
        default=(
            "data/experiments/exp-20260427-018/"
            "exp_20260427_018_llm_production_aligned_ranking_manifest_v2.json"
        ),
    )
    parser.add_argument(
        "--output",
        default=(
            "data/experiments/exp-20260428-008/"
            "exp_20260428_008_llm_replay_attribution_coverage.json"
        ),
    )
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=DEFAULT_END)
    args = parser.parse_args()

    artifact = build_artifact(
        data_dir=Path(args.data_dir),
        baseline_file=Path(args.baseline),
        prior_manifest=Path(args.prior_manifest),
        start=_parse_date(args.start),
        end=_parse_date(args.end),
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(artifact, handle, indent=2, sort_keys=True)
        handle.write("\n")

    print(json.dumps(artifact["summary"], indent=2, sort_keys=True))
    print(json.dumps({"delta_vs_prior_manifest": artifact["delta_vs_prior_manifest"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
