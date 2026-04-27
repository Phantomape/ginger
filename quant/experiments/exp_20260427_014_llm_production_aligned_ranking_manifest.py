"""Build a read-only manifest of LLM ranking-ready replay samples.

This measurement artifact converts the replay metadata exposed by
``quant.llm_replay`` into a stable sample list for the next default-off LLM
ranking experiment. It does not call the LLM and does not change strategy
behavior.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from quant.llm_replay import get_llm_decision_for_date


DEFAULT_START = "2025-10-23"
DEFAULT_END = "2026-04-21"


def _parse_yyyy_mm_dd(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _date_from_replay_name(path: Path) -> date:
    stamp = path.stem.replace("llm_prompt_resp_", "")
    return datetime.strptime(stamp, "%Y%m%d").date()


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    return raw if isinstance(raw, dict) else {}


def _advice_body(raw: dict) -> dict:
    if isinstance(raw.get("advice_parsed"), dict):
        return raw["advice_parsed"]
    return raw


def _new_trade_ticker(raw: dict) -> str | None:
    body = _advice_body(raw)
    new_trade = body.get("new_trade") if isinstance(body, dict) else None
    if not isinstance(new_trade, dict):
        return None
    ticker = new_trade.get("ticker")
    if isinstance(ticker, str) and ticker.strip():
        return ticker.strip().upper()
    return None


def build_manifest(data_dir: Path, baseline_file: Path, start: date, end: date) -> dict:
    replay_paths = sorted(data_dir.glob("llm_prompt_resp_????????.json"))
    baseline = _load_json(baseline_file) if baseline_file.exists() else {}
    baseline_llm = baseline.get("llm_attribution", {})

    samples = []
    for replay_path in replay_paths:
        replay_date = _date_from_replay_name(replay_path)
        date_str = replay_date.strftime("%Y%m%d")
        raw = _load_json(replay_path)
        decision = get_llm_decision_for_date(date_str, data_dir=str(data_dir))
        approved = _new_trade_ticker(raw)
        presented = decision.get("signals_presented") or []
        presented_set = {ticker.upper() for ticker in presented}
        rejected = sorted(ticker for ticker in presented_set if ticker != approved)
        in_window = start <= replay_date <= end
        ranking_eligible = decision.get("ranking_eligible") is True
        context_present = decision.get("archive_context_present") is True
        aligned_for_ranking = (
            in_window
            and context_present
            and ranking_eligible
            and len(presented_set) > 0
            and approved in presented_set
        )

        samples.append(
            {
                "date": replay_date.isoformat(),
                "date_str": date_str,
                "file": str(replay_path).replace("\\", "/"),
                "in_evaluation_window": in_window,
                "archive_context_present": context_present,
                "ranking_eligible": decision.get("ranking_eligible"),
                "new_trade_locked": decision.get("new_trade_locked"),
                "lock_reason": decision.get("lock_reason"),
                "source": decision.get("source"),
                "signals_presented": sorted(presented_set),
                "signals_presented_count": decision.get("signals_presented_count"),
                "approved_ticker": approved,
                "approved_in_presented": approved in presented_set if approved else False,
                "rejected_tickers": rejected,
                "aligned_for_ranking_sample": aligned_for_ranking,
            }
        )

    window_samples = [sample for sample in samples if sample["in_evaluation_window"]]
    aligned_samples = [sample for sample in samples if sample["aligned_for_ranking_sample"]]
    unknown_context = [
        sample
        for sample in samples
        if sample["in_evaluation_window"] and not sample["archive_context_present"]
    ]

    summary = {
        "replay_files_total": len(samples),
        "replay_files_in_window": len(window_samples),
        "archive_context_present_total": sum(1 for sample in samples if sample["archive_context_present"]),
        "archive_context_present_in_window": sum(1 for sample in window_samples if sample["archive_context_present"]),
        "ranking_eligible_days_total": sum(1 for sample in samples if sample["ranking_eligible"] is True),
        "ranking_eligible_days_in_window": sum(1 for sample in window_samples if sample["ranking_eligible"] is True),
        "aligned_ranking_sample_days_in_window": len(aligned_samples),
        "aligned_ranking_sample_signals_in_window": sum(
            len(sample["signals_presented"]) for sample in aligned_samples
        ),
        "unknown_context_days_in_window": len(unknown_context),
        "unknown_context_dates_in_window": [sample["date"] for sample in unknown_context],
        "baseline_candidate_signal_total": baseline_llm.get("candidate_signals_total"),
        "baseline_effective_candidate_days": (
            baseline_llm.get("effective_attribution", {}).get("effective_candidate_days")
        ),
        "baseline_effective_candidate_signals": (
            baseline_llm.get("effective_attribution", {}).get("effective_candidate_signals")
        ),
    }

    return {
        "experiment_id": "exp-20260427-014",
        "artifact_type": "llm_production_aligned_ranking_manifest",
        "strategy_behavior_changed": False,
        "evaluation_window": {"start": start.isoformat(), "end": end.isoformat()},
        "baseline_file": str(baseline_file).replace("\\", "/"),
        "summary": summary,
        "samples": samples,
        "next_alpha_experiment_released": {
            "hypothesis": (
                "Default-off LLM soft ranking can be tested only on dates where "
                "prompt-time archive_context is present, Task A was ranking eligible, "
                "and the approved ticker was among presented candidates."
            ),
            "minimum_current_sample": (
                "Use aligned_ranking_sample_days_in_window as the current auditable "
                "sample; do not infer quality from headline replay file count."
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--baseline", default="data/backtest_results_20260426.json")
    parser.add_argument(
        "--output",
        default=(
            "data/experiments/exp-20260427-014/"
            "exp_20260427_014_llm_production_aligned_ranking_manifest.json"
        ),
    )
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=DEFAULT_END)
    args = parser.parse_args()

    artifact = build_manifest(
        data_dir=Path(args.data_dir),
        baseline_file=Path(args.baseline),
        start=_parse_yyyy_mm_dd(args.start),
        end=_parse_yyyy_mm_dd(args.end),
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(artifact, handle, indent=2, sort_keys=True)
        handle.write("\n")

    print(json.dumps(artifact["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
