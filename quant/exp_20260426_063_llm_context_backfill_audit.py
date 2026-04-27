"""Audit legacy LLM replay files for archive_context backfill candidates.

Observed-only measurement repair for exp-20260427-009. This script does not
rewrite replay files; it reports which existing llm_prompt_resp_YYYYMMDD.json
files lack prompt-time archive_context and can be made attribution-ready from
already persisted sidecars.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = REPO_ROOT / "data"
DEFAULT_OUTPUT = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / "exp_20260426_063_llm_context_backfill_audit.json"
)


def _load_json(path: Path):
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f), None
    except Exception as exc:  # pragma: no cover - defensive artifact detail
        return None, str(exc)


def _date_from_replay(path: Path) -> str:
    stem = path.stem
    return stem.rsplit("_", 1)[-1]


def _ranking_status(context: dict | None) -> str:
    if not isinstance(context, dict):
        return "unknown"
    if context.get("new_trade_locked") is True:
        return "new_trade_locked"
    if context.get("ranking_eligible") is True:
        return "ranking_eligible"
    if context.get("ranking_eligible") is False:
        return "ranking_ineligible"
    return "unknown"


def _new_trade_ticker(payload: dict) -> str | None:
    parsed = payload.get("advice_parsed") if isinstance(payload, dict) else None
    if not isinstance(parsed, dict):
        parsed = payload if isinstance(payload, dict) else {}
    new_trade = parsed.get("new_trade")
    if isinstance(new_trade, dict):
        ticker = new_trade.get("ticker")
        return ticker.upper() if isinstance(ticker, str) and ticker.strip() else None
    return None


def build_audit(data_dir: Path) -> dict:
    sys.path.insert(0, str(REPO_ROOT / "quant"))
    from llm_advisor import _build_archive_context

    replay_paths = sorted(data_dir.glob("llm_prompt_resp_*.json"))
    rows = []
    summary = {
        "replay_files_total": 0,
        "parse_error_files": 0,
        "has_archive_context": 0,
        "missing_archive_context": 0,
        "backfill_candidates": 0,
        "still_unknown_after_backfill": 0,
        "unknown_before_backfill": 0,
        "unknown_resolved_by_backfill": 0,
        "ranking_eligible_after_backfill": 0,
        "ranking_locked_after_backfill": 0,
        "ranking_ineligible_after_backfill": 0,
    }

    for path in replay_paths:
        date_str = _date_from_replay(path)
        payload, error = _load_json(path)
        summary["replay_files_total"] += 1

        if error:
            summary["parse_error_files"] += 1
            rows.append({
                "date": date_str,
                "replay_file": path.relative_to(REPO_ROOT).as_posix(),
                "parse_error": error,
                "current_ranking_status": "unknown",
                "backfilled_ranking_status": "unknown",
                "backfill_candidate": False,
            })
            summary["unknown_before_backfill"] += 1
            summary["still_unknown_after_backfill"] += 1
            continue

        current_context = payload.get("archive_context") if isinstance(payload, dict) else None
        current_status = _ranking_status(current_context)
        if current_status == "unknown":
            summary["unknown_before_backfill"] += 1

        built_context = _build_archive_context(date_str, str(data_dir))
        backfill_candidate = not isinstance(current_context, dict) and isinstance(built_context, dict)
        effective_context = current_context if isinstance(current_context, dict) else built_context
        backfilled_status = _ranking_status(effective_context)

        if isinstance(current_context, dict):
            summary["has_archive_context"] += 1
        else:
            summary["missing_archive_context"] += 1
        if backfill_candidate:
            summary["backfill_candidates"] += 1
        if current_status == "unknown" and backfilled_status != "unknown":
            summary["unknown_resolved_by_backfill"] += 1
        if backfilled_status == "unknown":
            summary["still_unknown_after_backfill"] += 1
        elif backfilled_status == "ranking_eligible":
            summary["ranking_eligible_after_backfill"] += 1
        elif backfilled_status == "new_trade_locked":
            summary["ranking_locked_after_backfill"] += 1
        elif backfilled_status == "ranking_ineligible":
            summary["ranking_ineligible_after_backfill"] += 1

        rows.append({
            "date": date_str,
            "replay_file": path.relative_to(REPO_ROOT).as_posix(),
            "current_has_archive_context": isinstance(current_context, dict),
            "current_ranking_status": current_status,
            "backfill_candidate": backfill_candidate,
            "backfilled_ranking_status": backfilled_status,
            "new_trade_ticker": _new_trade_ticker(payload),
            "current_context_source": (
                current_context.get("source") if isinstance(current_context, dict) else None
            ),
            "backfill_context_source": (
                built_context.get("source") if isinstance(built_context, dict) else None
            ),
            "signals_presented_count": (
                effective_context.get("signals_presented_count")
                if isinstance(effective_context, dict)
                else None
            ),
            "signals_presented": (
                effective_context.get("signals_presented")
                if isinstance(effective_context, dict)
                else None
            ),
        })

    summary["unknown_after_backfill_fraction"] = (
        round(summary["still_unknown_after_backfill"] / summary["replay_files_total"], 6)
        if summary["replay_files_total"]
        else None
    )
    summary["backfill_candidate_fraction_of_missing_context"] = (
        round(summary["backfill_candidates"] / summary["missing_archive_context"], 6)
        if summary["missing_archive_context"]
        else None
    )

    return {
        "experiment_id": "exp-20260427-009",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data_dir": data_dir.relative_to(REPO_ROOT).as_posix()
        if data_dir.is_relative_to(REPO_ROOT)
        else str(data_dir),
        "summary": summary,
        "rows": rows,
        "decision_use": (
            "Observed-only artifact. Backfill candidates are existing real replay "
            "files whose archive_context can be reconstructed from prompt-time "
            "sidecars; no strategy behavior is changed."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    output = Path(args.output)
    artifact = build_audit(data_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(json.dumps(artifact["summary"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
