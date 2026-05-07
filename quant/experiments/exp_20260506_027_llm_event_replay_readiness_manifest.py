from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPERIMENT_ID = "exp-20260506-027"
WINDOW_START = "2025-10-23"
WINDOW_END = "2026-04-21"
BASELINE_RESULT_FILE = Path("data/backtest_results_20260506.json")
OUTPUT_FILE = Path("data/experiments/exp-20260506-027/exp_20260506_027_llm_event_replay_readiness_manifest.json")

PAPER_SOURCES = {
    "form4_meaningful_purchase": Path("data/form4_event_sleeve_paper_state.json"),
    "sec_governance_procedural": Path("data/sec_governance_event_sleeve_paper_state.json"),
    "sec_leadership_change": Path("data/sec_leadership_event_sleeve_paper_state.json"),
    "sec_negative_reaction": Path("data/sec_negative_event_sleeve_paper_state.json"),
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def maybe_parse_advice(raw: Any) -> Any:
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
    return None


def extract_new_trade(doc: dict[str, Any]) -> Any:
    if "advice_parsed" in doc:
        parsed = maybe_parse_advice(doc.get("advice_parsed"))
    elif "advice_raw" in doc:
        parsed = maybe_parse_advice(doc.get("advice_raw"))
    else:
        parsed = doc
    if isinstance(parsed, dict):
        return parsed.get("new_trade")
    return None


def usable_new_trade_count(new_trade: Any) -> int:
    if isinstance(new_trade, dict):
        ticker = str(new_trade.get("ticker") or "").strip().upper()
        if ticker and ticker not in {"NO NEW TRADE", "NONE", "N/A"}:
            return 1
    if isinstance(new_trade, str):
        text = new_trade.strip().upper()
        if text and text not in {"NO NEW TRADE", "NONE", "N/A", "NO_TRADE"}:
            return 1
    if isinstance(new_trade, list):
        return sum(usable_new_trade_count(item) for item in new_trade)
    return 0


def llm_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(Path("data").glob("llm_prompt_resp_*.json")):
        date = path.stem.replace("llm_prompt_resp_", "")
        iso_date = f"{date[:4]}-{date[4:6]}-{date[6:8]}" if len(date) == 8 else date
        try:
            doc = load_json(path)
        except Exception as exc:
            rows.append({"date": iso_date, "file": str(path), "parse_error": str(exc)})
            continue
        archive_context = doc.get("archive_context") if isinstance(doc, dict) else None
        new_trade = extract_new_trade(doc) if isinstance(doc, dict) else None
        heuristic_new_trades = usable_new_trade_count(new_trade)
        signals_presented_count = 0
        ranking_eligible = None
        new_trade_locked = None
        if isinstance(archive_context, dict):
            signals_presented_count = int(archive_context.get("signals_presented_count") or len(archive_context.get("signals_presented") or []))
            ranking_eligible = archive_context.get("ranking_eligible")
            new_trade_locked = archive_context.get("new_trade_locked")
        else:
            signals_presented_count = heuristic_new_trades
        rows.append({
            "date": iso_date,
            "file": str(path),
            "in_primary_window": WINDOW_START <= iso_date <= WINDOW_END,
            "has_archive_context": isinstance(archive_context, dict),
            "has_prompt": any(k in doc for k in ("prompt", "advice_raw", "advice_parsed", "new_trade")) if isinstance(doc, dict) else False,
            "signals_presented_count": signals_presented_count,
            "heuristic_new_trade_count": heuristic_new_trades,
            "ranking_eligible": ranking_eligible,
            "new_trade_locked": new_trade_locked,
            "effective_candidate_day": bool(signals_presented_count),
            "production_aligned_candidate_day": bool(isinstance(archive_context, dict) and ranking_eligible is True and signals_presented_count > 0),
        })
    return rows


def summarize_llm(rows: list[dict[str, Any]]) -> dict[str, Any]:
    in_window = [r for r in rows if r.get("in_primary_window")]
    aligned = [r for r in rows if r.get("production_aligned_candidate_day")]
    aligned_in_window = [r for r in in_window if r.get("production_aligned_candidate_day")]
    return {
        "all_archive_days": len(rows),
        "primary_window_archive_days": len(in_window),
        "all_days_with_archive_context": sum(1 for r in rows if r.get("has_archive_context")),
        "primary_window_days_with_archive_context": sum(1 for r in in_window if r.get("has_archive_context")),
        "all_ranking_eligible_candidate_days": len(aligned),
        "primary_window_ranking_eligible_candidate_days": len(aligned_in_window),
        "all_signals_presented": sum(int(r.get("signals_presented_count") or 0) for r in rows),
        "primary_window_signals_presented": sum(int(r.get("signals_presented_count") or 0) for r in in_window),
        "primary_window_archive_context_fraction": round((sum(1 for r in in_window if r.get("has_archive_context")) / len(in_window)), 4) if in_window else 0.0,
        "ranking_ready_for_soft_alpha": len(aligned_in_window) >= 5,
        "readiness_reason": "needs at least 5 production-aligned candidate days in the primary window before LLM soft ranking alpha is testable",
    }


def count_jsonl_rows(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip())


def summarize_paper_source(name: str, path: Path) -> dict[str, Any]:
    snapshot_file = Path(str(path).replace("_state.json", "_snapshots.jsonl"))
    if not path.exists():
        return {"exists": False, "state_file": str(path), "snapshot_file": str(snapshot_file), "snapshot_rows": count_jsonl_rows(snapshot_file)}
    state = load_json(path)
    closed = state.get("closed_positions") or []
    open_positions = state.get("open_positions") or []
    pending = state.get("pending_entries") or []
    skipped = state.get("skipped_entries") or []
    closed_with_counterfactual = 0
    for row in closed:
        source = row.get("source_candidate") if isinstance(row, dict) else None
        cf = source.get("counterfactual") if isinstance(source, dict) else None
        if isinstance(cf, dict) and cf.get("frozen"):
            closed_with_counterfactual += 1
    return {
        "exists": True,
        "state_file": str(path),
        "snapshot_file": str(snapshot_file),
        "snapshot_rows": count_jsonl_rows(snapshot_file),
        "schema_version": state.get("schema_version"),
        "sleeve": state.get("sleeve"),
        "updated_at": state.get("updated_at"),
        "closed_positions": len(closed),
        "open_positions": len(open_positions),
        "pending_entries": len(pending),
        "skipped_entries": len(skipped),
        "closed_with_frozen_counterfactual": closed_with_counterfactual,
        "has_replacement_value_sample": closed_with_counterfactual > 0,
    }


def summarize_event_paper() -> dict[str, Any]:
    sources = {name: summarize_paper_source(name, path) for name, path in PAPER_SOURCES.items()}
    totals = {
        "source_count": len(sources),
        "snapshot_rows": sum(int(src.get("snapshot_rows") or 0) for src in sources.values()),
        "closed_positions": sum(int(src.get("closed_positions") or 0) for src in sources.values()),
        "open_positions": sum(int(src.get("open_positions") or 0) for src in sources.values()),
        "pending_entries": sum(int(src.get("pending_entries") or 0) for src in sources.values()),
        "skipped_entries": sum(int(src.get("skipped_entries") or 0) for src in sources.values()),
        "sources_with_closed_outcomes": sum(1 for src in sources.values() if int(src.get("closed_positions") or 0) > 0),
        "sources_with_replacement_value_sample": sum(1 for src in sources.values() if src.get("has_replacement_value_sample")),
        "sources_with_pending_or_open": sum(1 for src in sources.values() if int(src.get("pending_entries") or 0) + int(src.get("open_positions") or 0) > 0),
    }
    totals["event_paper_ready_for_promotion_test"] = totals["sources_with_replacement_value_sample"] > 0
    totals["readiness_reason"] = "needs closed paper positions with frozen same-day alternatives before event-bundle promotion can be judged"
    return {"sources": sources, "totals": totals}


def baseline_metrics() -> dict[str, Any]:
    result = load_json(BASELINE_RESULT_FILE)
    keys = ["expected_value_score", "sharpe_daily", "sharpe", "total_pnl", "total_return_pct", "max_drawdown_pct", "win_rate", "total_trades", "trade_count", "signals_generated", "signals_survived", "survival_rate"]
    out = {k: result.get(k) for k in keys if k in result}
    if "trade_count" not in out and "total_trades" in out:
        out["trade_count"] = out["total_trades"]
    return out


def main() -> None:
    rows = llm_rows()
    llm_summary = summarize_llm(rows)
    event_summary = summarize_event_paper()
    metrics = baseline_metrics()
    blocked = []
    released = []
    if not llm_summary["ranking_ready_for_soft_alpha"]:
        blocked.append("LLM soft ranking / event grading alpha remains blocked by insufficient production-aligned candidate days in the primary replay window.")
    else:
        released.append("LLM soft-ranking shadow replay can be started on the primary window.")
    if not event_summary["totals"]["event_paper_ready_for_promotion_test"]:
        blocked.append("Default-off event sleeve promotion remains blocked by missing closed paper outcomes with frozen alternatives.")
    else:
        released.append("Event paper replacement-value promotion audit can be started.")
    if llm_summary["all_archive_days"] > 0 and event_summary["totals"]["snapshot_rows"] > 0:
        released.append("Fresh readiness manifest is available for future alpha tickets to reference without rerunning this audit.")

    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lane": "measurement_repair",
        "change_type": "measurement_instrumentation",
        "single_causal_variable": "LLM event replay readiness manifest",
        "date_range": {"start": WINDOW_START, "end": WINDOW_END},
        "baseline_result_file": str(BASELINE_RESULT_FILE),
        "baseline_metrics": metrics,
        "after_metrics": metrics,
        "expected_value_score_delta": 0.0,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "strategy_behavior_changed": False,
        },
        "llm_replay_coverage": {"summary": llm_summary, "rows": rows},
        "event_forward_paper_readiness": event_summary,
        "alpha_hypothesis_blocked": blocked,
        "alpha_hypothesis_released": released,
        "next_alpha_unlocked": "Keep accumulating production-aligned LLM prompt_resp archives and closed event paper outcomes; once ready, test default-off LLM/event candidate grading against same-day A/B alternatives.",
        "historical_context": {
            "previous_manifest": "data/experiments/exp-20260505-027/exp_20260505_027_llm_event_replay_coverage_manifest.json",
            "why_not_repeat": "This is a fresh current-state manifest after new 2026-05-06 paper state; it does not retune thresholds, event sources, or LLM responsibilities.",
            "mechanism_insight_guardrails": [
                "Do not promote event sleeves before closed forward paper replacement-value evidence.",
                "Do not promote LLM soft ranking from dated prompt-response coverage alone."
            ],
        },
        "gate4": {"applicable": False, "reason": "Observed-only manifest; no strategy behavior, metrics, orders, ranking, sizing, or exits changed."},
    }
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "output_file": str(OUTPUT_FILE),
        "llm_primary_window_archive_days": llm_summary["primary_window_archive_days"],
        "llm_primary_window_ranking_eligible_candidate_days": llm_summary["primary_window_ranking_eligible_candidate_days"],
        "event_snapshot_rows": event_summary["totals"]["snapshot_rows"],
        "event_open_positions": event_summary["totals"]["open_positions"],
        "event_closed_positions": event_summary["totals"]["closed_positions"],
    }, indent=2))


if __name__ == "__main__":
    main()
