"""exp-20260507-032: entry-state oracle integration audit.

This experiment turns the META/NFLX timing work into a reusable oracle surface:
candidate rows are tagged by signal-date entry state, then grouped by future
20-trading-day returns. The output is diagnostic only. It does not alter entry,
exit, ranking, sizing, universe, LLM/news, or production execution.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from oracle_diagnostics import build_entry_state_oracle  # noqa: E402


EXPERIMENT_ID = "exp-20260507-032"
STEM = "entry_state_oracle_integration"
SOURCE_EXPERIMENTS = ("exp-20260507-028", "exp-20260507-030")

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

SEED_TICKERS = ("META", "NFLX")
PLATFORM_TICKERS = ("META", "NFLX", "GOOG", "AMZN", "SPOT", "DIS", "APP")

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
                "candidate_events": (
                    "data/experiments/exp-20260507-013/"
                    "entry_candidate_events_late_strong.json"
                ),
                "backtest_results": (
                    "data/experiments/exp-20260507-013/"
                    "backtest_results_late_strong.json"
                ),
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
                "candidate_events": (
                    "data/experiments/exp-20260507-013/"
                    "entry_candidate_events_mid_weak.json"
                ),
                "backtest_results": (
                    "data/experiments/exp-20260507-013/"
                    "backtest_results_mid_weak.json"
                ),
                "state_note": "rotation-heavy bull where strategy profits but can lag indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
                "candidate_events": (
                    "data/experiments/exp-20260507-013/"
                    "entry_candidate_events_old_thin.json"
                ),
                "backtest_results": (
                    "data/experiments/exp-20260507-013/"
                    "backtest_results_old_thin.json"
                ),
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8-sig") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n")


def _candidate_events(payload: dict[str, Any]) -> list[dict[str, Any]]:
    events = payload.get("candidate_events") if isinstance(payload, dict) else []
    return [event for event in events or [] if isinstance(event, dict)]


def _filter_events(events: list[dict[str, Any]], tickers: tuple[str, ...]) -> dict[str, Any]:
    wanted = {ticker.upper() for ticker in tickers}
    return {
        "candidate_events": [
            event for event in events
            if str(event.get("ticker") or "").upper() in wanted
        ]
    }


def _normalize_date(raw_date: Any) -> str | None:
    if raw_date is None:
        return None
    text = str(raw_date)
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return text[:10]


def _load_earnings_for_events(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for event in events:
        date_str = _normalize_date(event.get("date") or event.get("signal_date"))
        if not date_str or date_str in out:
            continue
        compact = date_str.replace("-", "")
        path = REPO_ROOT / "data" / f"earnings_snapshot_{compact}.json"
        if not path.exists():
            out[date_str] = {}
            continue
        payload = _load_json(path)
        earnings = payload.get("earnings") if isinstance(payload, dict) else {}
        out[date_str] = earnings if isinstance(earnings, dict) else {}
    return out


def _compact_tag_summary(oracle: dict[str, Any], limit: int = 12) -> dict[str, Any]:
    by_tag = oracle.get("by_tag") or {}
    ordered = sorted(
        by_tag.items(),
        key=lambda item: (
            item[1].get("candidate_count", 0),
            item[1].get("avg_forward_return_pct")
            if item[1].get("avg_forward_return_pct") is not None else -999,
        ),
        reverse=True,
    )
    return {
        "candidate_count": oracle.get("candidate_count"),
        "entered_count": oracle.get("entered_count"),
        "missing_candidate_count": oracle.get("missing_candidate_count"),
        "decision_counts": oracle.get("decision_counts"),
        "avg_forward_return_pct": oracle.get("avg_forward_return_pct"),
        "median_forward_return_pct": oracle.get("median_forward_return_pct"),
        "win_rate": oracle.get("win_rate"),
        "top_tags_by_count": [
            {"tag": tag, **summary}
            for tag, summary in ordered[:limit]
        ],
    }


def _merge_tag_summaries(oracles: list[dict[str, Any]]) -> dict[str, Any]:
    merged: dict[str, dict[str, Any]] = {}
    for oracle in oracles:
        for tag, rec in (oracle.get("by_tag") or {}).items():
            count = int(rec.get("candidate_count") or 0)
            if not count:
                continue
            dest = merged.setdefault(tag, {
                "candidate_count": 0,
                "entered_count": 0,
                "weighted_return_sum": 0.0,
                "weighted_win_sum": 0.0,
                "windows_present": 0,
            })
            avg_return = rec.get("avg_forward_return_pct")
            win_rate = rec.get("win_rate")
            dest["candidate_count"] += count
            dest["entered_count"] += int(rec.get("entered_count") or 0)
            dest["windows_present"] += 1
            if avg_return is not None:
                dest["weighted_return_sum"] += float(avg_return) * count
            if win_rate is not None:
                dest["weighted_win_sum"] += float(win_rate) * count

    out = {}
    for tag, rec in merged.items():
        count = rec["candidate_count"]
        out[tag] = {
            "candidate_count": count,
            "entered_count": rec["entered_count"],
            "windows_present": rec["windows_present"],
            "weighted_avg_forward_return_pct": round(
                rec["weighted_return_sum"] / count,
                6,
            ),
            "weighted_win_rate": round(rec["weighted_win_sum"] / count, 4),
        }
    return dict(sorted(
        out.items(),
        key=lambda item: (
            item[1]["candidate_count"],
            item[1]["weighted_avg_forward_return_pct"],
        ),
        reverse=True,
    ))


def _run_window(label: str, cfg: dict[str, Any]) -> dict[str, Any]:
    snapshot = _load_json(REPO_ROOT / cfg["snapshot"])
    backtest = _load_json(REPO_ROOT / cfg["backtest_results"])
    events_payload = _load_json(REPO_ROOT / cfg["candidate_events"])
    events = _candidate_events(events_payload)
    earnings_by_date = _load_earnings_for_events(events)

    all_oracle = build_entry_state_oracle(
        backtest,
        snapshot,
        candidate_events={"candidate_events": events},
        earnings_by_date=earnings_by_date,
        horizon_days=20,
    )
    platform_oracle = build_entry_state_oracle(
        backtest,
        snapshot,
        candidate_events=_filter_events(events, PLATFORM_TICKERS),
        earnings_by_date=earnings_by_date,
        horizon_days=20,
    )
    seed_oracle = build_entry_state_oracle(
        backtest,
        snapshot,
        candidate_events=_filter_events(events, SEED_TICKERS),
        earnings_by_date=earnings_by_date,
        horizon_days=20,
    )

    return {
        "label": label,
        "date_range": f"{cfg['start']} -> {cfg['end']}",
        "market_regime_summary": cfg["state_note"],
        "source_files": {
            "snapshot": cfg["snapshot"],
            "candidate_events": cfg["candidate_events"],
            "backtest_results": cfg["backtest_results"],
        },
        "all_candidates": all_oracle,
        "platform_candidates": platform_oracle,
        "seed_candidates": seed_oracle,
        "compact": {
            "all_candidates": _compact_tag_summary(all_oracle),
            "platform_candidates": _compact_tag_summary(platform_oracle),
            "seed_candidates": _compact_tag_summary(seed_oracle),
        },
    }


def _write_artifact(payload: dict[str, Any]) -> None:
    aggregate = payload["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} Entry-State Oracle Integration",
        "",
        "## Decision",
        "",
        "- decision: accepted_measurement_oracle",
        "- production_impact: replay_only diagnostic; no trading logic changed",
        "- next_action: use entry_state as a standing oracle feature, not a live entry rule",
        "",
        "## Aggregate",
        "",
        f"- all candidate rows: {aggregate['all_candidate_count']}",
        f"- platform candidate rows: {aggregate['platform_candidate_count']}",
        f"- seed candidate rows: {aggregate['seed_candidate_count']}",
        "",
        "## Top Tags",
        "",
    ]
    for tag, rec in list(aggregate["all_tags"].items())[:10]:
        lines.append(
            "- "
            f"{tag}: count={rec['candidate_count']}, "
            f"avg20d={rec['weighted_avg_forward_return_pct']}, "
            f"win_rate={rec['weighted_win_rate']}, "
            f"windows={rec['windows_present']}"
        )
    lines.extend([
        "",
        "## Notes",
        "",
        "- This is oracle diagnostics only; future prices are used for attribution.",
        "- META/NFLX remain underpowered as a standalone candidate replay sample.",
        "- The useful outcome is a shared diagnostic surface for future entry work.",
        "",
    ])
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    created_at = datetime.now(timezone.utc).isoformat()
    windows = OrderedDict((label, _run_window(label, cfg)) for label, cfg in WINDOWS.items())
    all_oracles = [window["all_candidates"] for window in windows.values()]
    platform_oracles = [window["platform_candidates"] for window in windows.values()]
    seed_oracles = [window["seed_candidates"] for window in windows.values()]

    aggregate = {
        "all_candidate_count": sum(oracle.get("candidate_count") or 0 for oracle in all_oracles),
        "platform_candidate_count": sum(
            oracle.get("candidate_count") or 0 for oracle in platform_oracles
        ),
        "seed_candidate_count": sum(oracle.get("candidate_count") or 0 for oracle in seed_oracles),
        "all_tags": _merge_tag_summaries(all_oracles),
        "platform_tags": _merge_tag_summaries(platform_oracles),
        "seed_tags": _merge_tag_summaries(seed_oracles),
    }
    decision_read = {
        "status": "accepted_measurement_oracle",
        "reason": (
            "Entry timing can now be audited through a reusable oracle surface. "
            "It remains non-tradable and does not justify a production entry rule yet."
        ),
        "next_action": "monitor_entry_state_tags_before_replay",
        "seed_candidate_count": aggregate["seed_candidate_count"],
        "platform_candidate_count": aggregate["platform_candidate_count"],
    }
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": created_at,
        "title": "Entry-state oracle integration",
        "source_experiments": SOURCE_EXPERIMENTS,
        "lane": "measurement_repair_supporting_alpha_search",
        "alpha_hypothesis": (
            "State-conditioned entry timing tags can expose repeatable candidate-quality "
            "differences before any live entry timing policy is promoted."
        ),
        "single_causal_variable": "entry_state_oracle_diagnostic_surface",
        "change_type": "oracle_diagnostics_only",
        "decision": "accepted_measurement_oracle",
        "decision_read": decision_read,
        "gate4": {
            "passed": None,
            "basis": "No production strategy or replay policy changed; observed-only oracle artifact.",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "oracle_diagnostics_changed": True,
            "replay_only": True,
            "alters_entry": False,
            "alters_exit": False,
            "alters_ranking": False,
            "alters_sizing": False,
        },
        "historical_experiment_check": {
            "exp-20260507-008": "Rejected mechanical platform pullback timing.",
            "exp-20260507-028": "Observed promising META/NFLX daily timing surfaces.",
            "exp-20260507-030": (
                "Found true META/NFLX candidate overlap is underpowered; bridge into "
                "oracle diagnostics before replay."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": "LLM/news are outside this timing oracle integration.",
        },
        "windows": windows,
        "aggregate": aggregate,
        "artifact_paths": {
            "data_json": str(OUT_JSON.relative_to(REPO_ROOT)),
            "log_json": str(LOG_JSON.relative_to(REPO_ROOT)),
            "ticket_json": str(TICKET_JSON.relative_to(REPO_ROOT)),
            "artifact_md": str(ARTIFACT_MD.relative_to(REPO_ROOT)),
        },
    }
    log_payload = {
        key: payload[key]
        for key in (
            "experiment_id",
            "created_at",
            "lane",
            "alpha_hypothesis",
            "single_causal_variable",
            "change_type",
            "decision",
            "decision_read",
            "gate4",
            "production_impact",
            "historical_experiment_check",
            "llm_metrics",
            "aggregate",
            "artifact_paths",
        )
    }
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": "completed",
        "title": "Entry-state oracle integration",
        "result": "accepted_measurement_oracle",
        "next_action": "monitor_entry_state_tags_before_replay",
        "created_at": created_at,
        "completed_at": created_at,
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, log_payload)
    _write_json(TICKET_JSON, ticket)
    _write_artifact(payload)
    _append_jsonl(EXPERIMENT_LOG, log_payload)
    print(json.dumps(decision_read, indent=2, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
