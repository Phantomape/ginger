"""Build a read-only LLM/event replay attribution coverage manifest.

This experiment intentionally does not change strategy behavior. It summarizes
whether the current persisted LLM replay files and default-off event paper
ledgers are fresh enough to unblock a future LLM/event ranking or event-bundle
promotion test.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260505-027"
DEFAULT_BASELINE = Path("data/backtest_results_20260505.json")
DEFAULT_OUTPUT = Path(
    "data/experiments/exp-20260505-027/"
    "exp_20260505_027_llm_event_replay_coverage_manifest.json"
)
EVENT_STATE_FILES = {
    "form4_meaningful_purchase": Path("data/form4_event_sleeve_paper_state.json"),
    "sec_negative_reaction": Path("data/sec_negative_event_sleeve_paper_state.json"),
    "sec_governance_procedural": Path("data/sec_governance_event_sleeve_paper_state.json"),
    "sec_leadership_change": Path("data/sec_leadership_event_sleeve_paper_state.json"),
}
EVENT_SNAPSHOT_FILES = {
    "form4_meaningful_purchase": Path("data/form4_event_sleeve_paper_snapshots.jsonl"),
    "sec_negative_reaction": Path("data/sec_negative_event_sleeve_paper_snapshots.jsonl"),
    "sec_governance_procedural": Path("data/sec_governance_event_sleeve_paper_snapshots.jsonl"),
    "sec_leadership_change": Path("data/sec_leadership_event_sleeve_paper_snapshots.jsonl"),
}


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8-sig"))


def date_token(path: Path) -> str | None:
    token = path.stem.rsplit("_", 1)[-1]
    if len(token) == 8 and token.isdigit():
        return token
    return None


def date_to_iso(token: str | None) -> str | None:
    if not token:
        return None
    return datetime.strptime(token, "%Y%m%d").date().isoformat()


def collect_dated_files(data_dir: Path, pattern: str) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for path in sorted(data_dir.glob(pattern)):
        token = date_token(path)
        if token:
            out[token] = path
    return out


def archive_context(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    context = payload.get("archive_context")
    return context if isinstance(context, dict) else {}


def count_signals(context: dict[str, Any]) -> int:
    value = context.get("signals_presented_count")
    if isinstance(value, int):
        return value
    signals = context.get("signals_presented")
    return len(signals) if isinstance(signals, list) else 0


def summarize_llm(data_dir: Path, baseline: dict[str, Any]) -> dict[str, Any]:
    prompt_resp = collect_dated_files(data_dir, "llm_prompt_resp_*.json")
    decision_logs = collect_dated_files(data_dir, "llm_decision_log_*.json")
    prompts = collect_dated_files(data_dir, "llm_prompt_*.txt")
    raw_outputs = collect_dated_files(data_dir, "llm_output_*.json")

    rows: list[dict[str, Any]] = []
    totals = Counter()
    for ymd, path in sorted(prompt_resp.items()):
        payload = load_json(path)
        context = archive_context(payload)
        has_context = bool(context)
        ranking_eligible = context.get("ranking_eligible")
        new_trade_locked = context.get("new_trade_locked")
        signals_presented_count = count_signals(context)
        effective_candidate = (
            has_context
            and ranking_eligible is True
            and new_trade_locked is not True
            and signals_presented_count > 0
        )

        totals["prompt_resp_days"] += 1
        totals["archive_context_days"] += int(has_context)
        totals["ranking_eligible_days"] += int(ranking_eligible is True)
        totals["new_trade_locked_days"] += int(new_trade_locked is True)
        totals["effective_candidate_days"] += int(effective_candidate)
        totals["signals_presented"] += signals_presented_count

        rows.append(
            {
                "date": date_to_iso(ymd),
                "file": str(path).replace("\\", "/"),
                "has_archive_context": has_context,
                "has_decision_log": ymd in decision_logs,
                "has_prompt": ymd in prompts,
                "has_raw_output": ymd in raw_outputs,
                "ranking_eligible": ranking_eligible,
                "new_trade_locked": new_trade_locked,
                "signals_presented_count": signals_presented_count,
                "effective_candidate_day": effective_candidate,
            }
        )

    llm_attr = baseline.get("llm_attribution") or {}
    known_llm = (baseline.get("known_biases") or {}).get("llm_gate_unreplayed") or {}
    effective = llm_attr.get("effective_attribution") or {}

    return {
        "source_files": {
            "prompt_resp_days": len(prompt_resp),
            "decision_log_days": len(decision_logs),
            "prompt_days": len(prompts),
            "raw_output_days": len(raw_outputs),
            "latest_prompt_resp_date": date_to_iso(max(prompt_resp) if prompt_resp else None),
            "latest_decision_log_date": date_to_iso(max(decision_logs) if decision_logs else None),
        },
        "archive_context": {
            "days_with_archive_context": totals["archive_context_days"],
            "archive_context_fraction": (
                round(totals["archive_context_days"] / totals["prompt_resp_days"], 4)
                if totals["prompt_resp_days"]
                else 0.0
            ),
            "ranking_eligible_days": totals["ranking_eligible_days"],
            "new_trade_locked_days": totals["new_trade_locked_days"],
            "effective_candidate_days_from_files": totals["effective_candidate_days"],
            "signals_presented_from_files": totals["signals_presented"],
        },
        "baseline_reported_attribution": {
            "baseline_replay_enabled": llm_attr.get("replay_enabled"),
            "baseline_candidate_signals_total": llm_attr.get("candidate_signals_total"),
            "baseline_candidate_signals_covered": llm_attr.get("candidate_signals_covered"),
            "baseline_candidate_signal_coverage_fraction": llm_attr.get(
                "candidate_signal_coverage_fraction"
            ),
            "baseline_effective_rows": effective.get("rows"),
            "baseline_ranking_eligible_aligned_signals": effective.get(
                "ranking_eligible_aligned_signals"
            ),
            "known_bias_candidate_signal_fraction": known_llm.get(
                "production_aligned_candidate_signal_fraction"
            ),
        },
        "rows": rows,
    }


def count_jsonl_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(encoding="utf-8-sig") as handle:
        return sum(1 for line in handle if line.strip())


def summarize_event_state() -> dict[str, Any]:
    source_rows: dict[str, Any] = {}
    totals = Counter()
    closed_sources = 0
    pending_sources = 0
    for source, path in EVENT_STATE_FILES.items():
        payload = load_json(path) or {}
        pending = payload.get("pending_entries") if isinstance(payload, dict) else []
        open_positions = payload.get("open_positions") if isinstance(payload, dict) else []
        closed = payload.get("closed_positions") if isinstance(payload, dict) else []
        skipped = payload.get("skipped_entries") if isinstance(payload, dict) else []
        pending = pending if isinstance(pending, list) else []
        open_positions = open_positions if isinstance(open_positions, list) else []
        closed = closed if isinstance(closed, list) else []
        skipped = skipped if isinstance(skipped, list) else []
        snapshot_path = EVENT_SNAPSHOT_FILES[source]
        snapshot_count = count_jsonl_lines(snapshot_path)

        pending_sources += int(bool(pending or open_positions))
        closed_sources += int(bool(closed))
        totals["pending_entries"] += len(pending)
        totals["open_positions"] += len(open_positions)
        totals["closed_positions"] += len(closed)
        totals["skipped_entries"] += len(skipped)
        totals["snapshot_rows"] += snapshot_count

        source_rows[source] = {
            "state_file": str(path).replace("\\", "/"),
            "exists": path.exists(),
            "sleeve": payload.get("sleeve") if isinstance(payload, dict) else None,
            "updated_at": payload.get("updated_at") if isinstance(payload, dict) else None,
            "schema_version": payload.get("schema_version") if isinstance(payload, dict) else None,
            "pending_entries": len(pending),
            "open_positions": len(open_positions),
            "closed_positions": len(closed),
            "skipped_entries": len(skipped),
            "snapshot_file": str(snapshot_path).replace("\\", "/"),
            "snapshot_rows": snapshot_count,
            "has_replacement_value_sample": bool(closed),
        }

    return {
        "sources": source_rows,
        "totals": {
            "source_count": len(EVENT_STATE_FILES),
            "sources_with_pending_or_open": pending_sources,
            "sources_with_closed_outcomes": closed_sources,
            "pending_entries": totals["pending_entries"],
            "open_positions": totals["open_positions"],
            "closed_positions": totals["closed_positions"],
            "skipped_entries": totals["skipped_entries"],
            "snapshot_rows": totals["snapshot_rows"],
        },
    }


def metric_subset(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "total_pnl": result.get("total_pnl"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades") or result.get("trade_count"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": result.get("survival_rate"),
    }


def build_manifest(data_dir: Path, baseline_path: Path) -> dict[str, Any]:
    baseline = load_json(baseline_path) or {}
    llm = summarize_llm(data_dir, baseline)
    event_state = summarize_event_state()
    event_totals = event_state["totals"]
    llm_effective_days = llm["archive_context"]["effective_candidate_days_from_files"]
    llm_effective_signals = (
        (baseline.get("llm_attribution") or {})
        .get("effective_attribution", {})
        .get("ranking_eligible_aligned_signals")
    )

    blockers = []
    if not llm_effective_days:
        blockers.append("no effective LLM candidate days from prompt_resp archive_context")
    if not llm_effective_signals:
        blockers.append("baseline reports no ranking-eligible aligned LLM signals")
    if event_totals["closed_positions"] == 0:
        blockers.append("event paper ledgers have no closed forward outcomes yet")

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "lane": "measurement_repair",
        "change_type": "measurement_instrumentation",
        "single_causal_variable": "LLM/event replay attribution coverage manifest freshness",
        "strategy_behavior_changed": False,
        "baseline_result_file": str(baseline_path).replace("\\", "/"),
        "baseline_metrics": metric_subset(baseline),
        "after_metrics": metric_subset(baseline),
        "expected_value_score_delta": 0.0,
        "alpha_hypothesis_blocked": (
            "LLM/event soft ranking could grade existing A/B candidates, and the "
            "default-off event bundle could eventually receive live satellite "
            "capital, but only after production-aligned LLM samples and event "
            "paper outcomes can be attributed to replay or forward results."
        ),
        "historical_constraints": {
            "llm": [
                "Do not weaken or remove LLM because replay coverage is sparse.",
                "Do not promote LLM soft ranking until approved/non-approved candidates join to outcomes.",
                "Do not count dated prompt responses without prompt-time archive_context as ranking samples.",
            ],
            "event_bundle": [
                "Do not retune event thresholds, notionals, holding periods, or source composition on the frozen sample.",
                "Do not promote event sleeves to live capital before closed forward paper outcomes show replacement value.",
            ],
        },
        "llm_replay_coverage": llm,
        "event_forward_attribution": event_state,
        "readiness_verdict": {
            "status": "blocked_but_measurable",
            "blockers": blockers,
            "llm_soft_ranking_ready": bool(llm_effective_days and llm_effective_signals),
            "event_bundle_forward_promotion_ready": event_totals["closed_positions"] > 0,
            "minimum_next_step": (
                "Run daily production/paper pipeline until LLM prompt_resp files keep "
                "archive_context and event paper ledgers accumulate closed outcomes; "
                "then run a separate alpha ticket using this manifest as the coverage gate."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "production_signal_path_changed": False,
            "production_impact": "read_only_manifest_no_strategy_behavior_change",
        },
        "gate4": {
            "applicable": False,
            "reason": "Observed-only measurement manifest; entries, exits, ranking, sizing, and orders are unchanged.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--baseline", default=str(DEFAULT_BASELINE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    manifest = build_manifest(Path(args.data_dir), Path(args.baseline))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "experiment_id": manifest["experiment_id"],
                "output": str(output).replace("\\", "/"),
                "baseline_metrics": manifest["baseline_metrics"],
                "llm_source_files": manifest["llm_replay_coverage"]["source_files"],
                "event_totals": manifest["event_forward_attribution"]["totals"],
                "readiness_verdict": manifest["readiness_verdict"],
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
