"""exp-20260428-018: minimal event-ranking readiness audit.

This measurement-only artifact consolidates recent clean-news and LLM replay
coverage into a single go/no-go manifest for the next event-aware ranking alpha
test. It does not import or modify strategy modules.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ID = "exp-20260428-018"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260428_018_minimal_alpha_blocking_measurement_gap.json"

SOURCE_ARTIFACTS = {
    "llm_replay_coverage": REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260428-008"
    / "exp_20260428_008_llm_replay_attribution_coverage.json",
    "positive_clean_news": REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260428-010"
    / "exp_20260428_010_news_confirmed_ab_candidate_quality.json",
    "negative_clean_news": REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260428-016"
    / "exp_20260428_016_fresh_negative_clean_news_context_for_existing_a_b_candidates.json",
}

READINESS_MIN_MATCHED_SIGNALS = 10
READINESS_MIN_WINDOWS_WITH_MATCHES = 2


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def artifact_status() -> dict:
    return {
        name: {
            "path": str(path.relative_to(REPO_ROOT)),
            "exists": path.exists(),
        }
        for name, path in SOURCE_ARTIFACTS.items()
    }


def read_llm_coverage() -> dict:
    path = SOURCE_ARTIFACTS["llm_replay_coverage"]
    if not path.exists():
        return {"available": False}
    payload = load_json(path)
    summary = payload.get("summary") or payload.get("coverage_summary") or {}
    if not summary:
        # exp-20260428-008 stores the most important values in its closeout log,
        # but keep this parser tolerant of the artifact's actual shape.
        summary = {
            key: payload.get(key)
            for key in [
                "replay_files_total",
                "in_window_files",
                "in_window_files_with_archive_context",
                "ranking_ready_in_window_days",
                "ranking_ready_presented_signals",
                "legacy_missing_context_days",
                "in_window_sidecar_backfill_candidates",
            ]
            if key in payload
        }
    return {
        "available": True,
        "summary": summary,
    }


def clean_news_counts(payload: dict, polarity: str) -> dict:
    windows = payload.get("windows") or {}
    out = {}
    total_ab = 0
    total_deferred = 0
    total_matches = 0
    windows_with_matches = 0
    for label, window in windows.items():
        coverage = window.get("coverage") or {}
        ab_count = int(coverage.get("ab_entry_count") or 0)
        deferred_count = int(coverage.get("scarce_slot_deferred_count") or 0)
        if polarity == "positive":
            matched_ab = int(coverage.get("news_confirmed_ab_entry_count") or 0)
            matched_deferred = int(coverage.get("news_confirmed_deferred_count") or 0)
        else:
            matched_ab = int(coverage.get("negative_confirmed_ab_entry_count") or 0)
            matched_deferred = int(coverage.get("negative_confirmed_deferred_count") or 0)
        matched_total = matched_ab + matched_deferred
        total_ab += ab_count
        total_deferred += deferred_count
        total_matches += matched_total
        if matched_total:
            windows_with_matches += 1
        out[label] = {
            "ab_entry_count": ab_count,
            "scarce_slot_deferred_count": deferred_count,
            "matched_ab_entries": matched_ab,
            "matched_deferred_candidates": matched_deferred,
            "matched_total": matched_total,
            "candidate_total": ab_count + deferred_count,
            "match_rate": round(matched_total / (ab_count + deferred_count), 4)
            if (ab_count + deferred_count)
            else None,
        }
    return {
        "by_window": out,
        "totals": {
            "ab_entry_count": total_ab,
            "scarce_slot_deferred_count": total_deferred,
            "candidate_total": total_ab + total_deferred,
            "matched_total": total_matches,
            "windows_with_matches": windows_with_matches,
            "match_rate": round(total_matches / (total_ab + total_deferred), 4)
            if (total_ab + total_deferred)
            else None,
        },
    }


def read_clean_news_coverage() -> dict:
    coverage = {}
    for polarity, name in [("positive", "positive_clean_news"), ("negative", "negative_clean_news")]:
        path = SOURCE_ARTIFACTS[name]
        if not path.exists():
            coverage[polarity] = {"available": False}
            continue
        payload = load_json(path)
        coverage[polarity] = {
            "available": True,
            "news_archive": payload.get("news_coverage") or {},
            **clean_news_counts(payload, polarity),
        }
    return coverage


def readiness(clean_news: dict, llm: dict) -> dict:
    combined_matches = 0
    matched_windows = set()
    for polarity in ["positive", "negative"]:
        data = clean_news.get(polarity) or {}
        totals = data.get("totals") or {}
        combined_matches += int(totals.get("matched_total") or 0)
        for label, row in (data.get("by_window") or {}).items():
            if int(row.get("matched_total") or 0) > 0:
                matched_windows.add(label)

    enough_clean_news = (
        combined_matches >= READINESS_MIN_MATCHED_SIGNALS
        and len(matched_windows) >= READINESS_MIN_WINDOWS_WITH_MATCHES
    )
    llm_summary = llm.get("summary") or {}
    llm_ready_signals = int(
        llm_summary.get("ranking_ready_presented_signals")
        or llm_summary.get("ranking_ready_presented_signals_in_window")
        or 0
    )
    enough_llm = llm_ready_signals >= READINESS_MIN_MATCHED_SIGNALS

    return {
        "event_ranking_ready": enough_clean_news or enough_llm,
        "clean_news_ready": enough_clean_news,
        "llm_replay_ready": enough_llm,
        "thresholds": {
            "min_matched_signals": READINESS_MIN_MATCHED_SIGNALS,
            "min_windows_with_matches": READINESS_MIN_WINDOWS_WITH_MATCHES,
        },
        "observed": {
            "combined_clean_news_matched_signals": combined_matches,
            "clean_news_windows_with_matches": sorted(matched_windows),
            "llm_ranking_ready_presented_signals": llm_ready_signals,
        },
        "blocker": (
            "Event-aware ranking remains sample-limited; do not run another "
            "production-promotion ranking test until clean-news or LLM replay "
            "coverage clears the manifest thresholds."
        )
        if not (enough_clean_news or enough_llm)
        else (
            "Coverage threshold is met; the next event-aware ranking alpha test "
            "can use this manifest to define its eligible sample."
        ),
        "alpha_hypothesis_unblocked": (
            "Event-aware ranking of existing A/B candidates can improve candidate "
            "quality once a reproducible matched event-context sample exists."
        ),
    }


def run() -> dict:
    clean_news = read_clean_news_coverage()
    llm = read_llm_coverage()
    result = {
        "experiment_id": EXPERIMENT_ID,
        "status": "observed_only",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "hypothesis": (
            "A minimal audit artifact can remove a current measurement blocker "
            "for the next alpha experiment without changing strategy behavior."
        ),
        "single_causal_variable": "minimal alpha-blocking measurement gap",
        "production_code_changed": False,
        "strategy_behavior_changed": False,
        "source_artifacts": artifact_status(),
        "clean_news_coverage": clean_news,
        "llm_replay_coverage": llm,
        "readiness": readiness(clean_news, llm),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result["readiness"], indent=2, ensure_ascii=False))
    print(f"Wrote {OUT_JSON}")
    return result


if __name__ == "__main__":
    run()
