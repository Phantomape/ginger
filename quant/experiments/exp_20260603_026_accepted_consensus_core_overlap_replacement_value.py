"""exp-20260603-026: accepted consensus core-overlap replacement value.

Replay-only alpha search. It keeps the accepted independent-source free-data
consensus candidate source fixed, then tests one deployment-priority field:
selected paper candidates whose next-open entry date does not overlap an
executed core entry date may have cleaner replacement value than candidates
competing with same-day core A/B slots.

No shared adapter, production order path, ranking, sizing, exits, LLM, news,
watchlists, source thresholds, hold period, or notional policy is changed.
No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS_DIR = REPO_ROOT / "quant" / "experiments"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS_DIR))

import exp_20260603_014_accepted_consensus_independent_source_family as consensus  # noqa: E402


EXPERIMENT_ID = "exp-20260603-026"
STEM = "accepted_consensus_core_overlap_replacement_value"
TRIAL_FAMILY = "accepted_free_data_cross_source_consensus_displacement_value"
CHANGED_VARIABLE = "accepted_consensus_same_day_core_overlap_replacement_value_v1"
RULE_VERSION = CHANGED_VARIABLE

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260603_026_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
ACCEPTED_COMPARATOR_JSON = OUT_DIR / f"{STEM}_accepted_comparator_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

CURRENT_ACCEPTED_COMPARATOR_EXPERIMENT_ID = "exp-20260603-014"
CURRENT_ACCEPTED_COMPARATOR_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / CURRENT_ACCEPTED_COMPARATOR_EXPERIMENT_ID
    / "accepted_consensus_independent_source_family.json"
)

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_no_live_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "parity_test_added": False,
    "production_watchlist_changed": False,
    "production_orders_changed": False,
    "parity_note": (
        "This experiment changes no production code. A retained core-overlap "
        "priority field would need a shared default-off adapter path that builds "
        "the same core-entry map in live reports and backtests before any daily "
        "queue, candidate priority, or order surface could change."
    ),
}

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.15,
    "expected_pnl_delta": 1500.0,
    "main_failure_modes": [
        "same_day_core_overlap_sparse",
        "overlap_slice_negative",
        "window_regression",
        "accepted_consensus_comparator_not_beaten",
    ],
    "confidence_reason": (
        "Playbook explicitly asks for same-day core replacement-value evidence "
        "before activation; current accepted consensus is historically strong "
        "versus cash but has not proven scarce-slot displacement value."
    ),
    "recorded_at": "2026-06-03T23:10:55+00:00",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _core_entries_by_entry_date(before_result: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    by_date: dict[str, list[dict[str, Any]]] = {}
    for row in before_result.get("trades") or []:
        if not isinstance(row, dict):
            continue
        entry_date = str(row.get("entry_date") or "")[:10]
        ticker = str(row.get("ticker") or "").upper()
        if not entry_date or not ticker:
            continue
        by_date.setdefault(entry_date, []).append(
            {
                "ticker": ticker,
                "entry_date": entry_date,
                "exit_date": row.get("exit_date"),
                "strategy": row.get("strategy"),
                "pnl": round(_safe_float(row.get("pnl")), 2),
                "pnl_pct_net": row.get("pnl_pct_net"),
                "trade_key": row.get("trade_key"),
            }
        )
    return by_date


def _with_core_overlap_context(
    trade: dict[str, Any],
    core_entries_by_date: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    ticker = str(trade.get("ticker") or "").upper()
    entry_date = str(trade.get("entry_date") or "")[:10]
    same_day_entries = core_entries_by_date.get(entry_date, [])
    same_day_tickers = sorted({str(row.get("ticker") or "").upper() for row in same_day_entries})
    same_day_core_overlap = bool(same_day_entries)
    same_ticker_core_overlap = ticker in set(same_day_tickers)
    core_pnls = [_safe_float(row.get("pnl")) for row in same_day_entries]
    core_avg_pnl = sum(core_pnls) / len(core_pnls) if core_pnls else None
    paper_pnl = _safe_float(trade.get("pnl"))
    if same_ticker_core_overlap:
        displaced_resource = "same_ticker_core_entry"
    elif same_day_core_overlap:
        displaced_resource = "same_day_core_entry"
    else:
        displaced_resource = "paper_cash_slot"
    return {
        **trade,
        "core_overlap_rule_version": RULE_VERSION,
        "core_overlap_context_status": "ok" if entry_date else "missing_entry_date",
        "same_day_core_overlap": same_day_core_overlap,
        "same_ticker_core_overlap": same_ticker_core_overlap,
        "same_day_core_entry_count": len(same_day_entries),
        "same_day_core_tickers": same_day_tickers,
        "same_day_core_entries": same_day_entries,
        "same_day_core_pnl_total": round(sum(core_pnls), 2) if core_pnls else 0.0,
        "same_day_core_pnl_avg": round(core_avg_pnl, 2) if core_avg_pnl is not None else None,
        "same_day_core_pnl_best": round(max(core_pnls), 2) if core_pnls else None,
        "same_day_core_pnl_worst": round(min(core_pnls), 2) if core_pnls else None,
        "replacement_value_vs_same_day_core_avg": (
            round(paper_pnl - core_avg_pnl, 2) if core_avg_pnl is not None else None
        ),
        "cash_relative_paper_pnl": round(paper_pnl, 2),
        "displaced_resource": displaced_resource,
        "core_overlap_candidate_filter_pass": not same_day_core_overlap,
        "trade_enabled": False,
        "alters_orders": False,
    }


def _summary_by_overlap(enriched_trades_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    rows = [row for trades in enriched_trades_by_window.values() for row in trades]
    overlap = [row for row in rows if row.get("same_day_core_overlap")]
    non_overlap = [row for row in rows if not row.get("same_day_core_overlap")]
    same_ticker = [row for row in rows if row.get("same_ticker_core_overlap")]
    replacement_values = [
        _safe_float(row.get("replacement_value_vs_same_day_core_avg"))
        for row in overlap
        if row.get("replacement_value_vs_same_day_core_avg") is not None
    ]
    return {
        "all_selected_trade_count": len(rows),
        "same_day_core_overlap_trade_count": len(overlap),
        "same_ticker_core_overlap_trade_count": len(same_ticker),
        "non_core_overlap_trade_count": len(non_overlap),
        "all_selected_pnl_usd": round(sum(_safe_float(row.get("pnl")) for row in rows), 2),
        "same_day_core_overlap_pnl_usd": round(sum(_safe_float(row.get("pnl")) for row in overlap), 2),
        "same_ticker_core_overlap_pnl_usd": round(sum(_safe_float(row.get("pnl")) for row in same_ticker), 2),
        "non_core_overlap_pnl_usd": round(sum(_safe_float(row.get("pnl")) for row in non_overlap), 2),
        "overlap_replacement_value_vs_core_avg_pnl": round(sum(replacement_values), 2),
        "overlap_replacement_value_vs_core_avg_trade_count": len(replacement_values),
        "window_counts": {
            label: {
                "all": len(trades),
                "same_day_core_overlap": sum(1 for row in trades if row.get("same_day_core_overlap")),
                "same_ticker_core_overlap": sum(1 for row in trades if row.get("same_ticker_core_overlap")),
                "non_core_overlap": sum(1 for row in trades if not row.get("same_day_core_overlap")),
                "same_day_core_overlap_pnl_usd": round(
                    sum(_safe_float(row.get("pnl")) for row in trades if row.get("same_day_core_overlap")),
                    2,
                ),
                "non_core_overlap_pnl_usd": round(
                    sum(_safe_float(row.get("pnl")) for row in trades if not row.get("same_day_core_overlap")),
                    2,
                ),
            }
            for label, trades in enriched_trades_by_window.items()
        },
        "displaced_resource_counts": dict(
            sorted(Counter(str(row.get("displaced_resource") or "unknown") for row in rows).items())
        ),
    }


def _aggregate_for_after_key(results: list[dict[str, Any]], after_key: str) -> dict[str, Any]:
    before_ev = sum(_safe_float(row["before"].get("expected_value_score")) for row in results)
    after_ev = sum(_safe_float(row[after_key].get("expected_value_score")) for row in results)
    before_pnl = sum(_safe_float(row["before"].get("total_pnl")) for row in results)
    after_pnl = sum(_safe_float(row[after_key].get("total_pnl")) for row in results)
    before = {
        "expected_value_score": round(before_ev, 6),
        "total_pnl": round(before_pnl, 2),
        "strategy_total_pnl": round(before_pnl, 2),
    }
    after = {
        "expected_value_score": round(after_ev, 6),
        "total_pnl": round(after_pnl, 2),
        "strategy_total_pnl": round(after_pnl, 2),
    }
    return {
        "before": before,
        "after": after,
        "comparison": {
            "expected_value_score_delta": round(after_ev - before_ev, 6),
            "expected_value_score_delta_pct": round((after_ev - before_ev) / before_ev, 6)
            if before_ev
            else None,
            "strategy_total_pnl_delta": round(after_pnl - before_pnl, 2),
            "total_pnl_delta": round(after_pnl - before_pnl, 2),
            "strategy_total_pnl_delta_pct": round((after_pnl - before_pnl) / before_pnl, 6)
            if before_pnl
            else None,
        },
    }


def _aggregate_after_vs_comparator(results: list[dict[str, Any]]) -> dict[str, Any]:
    after_ev = sum(_safe_float(row["after"].get("expected_value_score")) for row in results)
    comparator_ev = sum(
        _safe_float(row["accepted_comparator_after"].get("expected_value_score")) for row in results
    )
    after_pnl = sum(_safe_float(row["after"].get("total_pnl")) for row in results)
    comparator_pnl = sum(_safe_float(row["accepted_comparator_after"].get("total_pnl")) for row in results)
    return {
        "after": {
            "expected_value_score": round(after_ev, 6),
            "total_pnl": round(after_pnl, 2),
            "strategy_total_pnl": round(after_pnl, 2),
        },
        "accepted_comparator_after": {
            "expected_value_score": round(comparator_ev, 6),
            "total_pnl": round(comparator_pnl, 2),
            "strategy_total_pnl": round(comparator_pnl, 2),
        },
        "comparison": {
            "expected_value_score_delta": round(after_ev - comparator_ev, 6),
            "strategy_total_pnl_delta": round(after_pnl - comparator_pnl, 2),
            "total_pnl_delta": round(after_pnl - comparator_pnl, 2),
        },
    }


def _run_windows(
    baselines: dict[str, dict[str, Any]],
    source_rows_by_window: dict[str, dict[tuple[str, str], list[dict[str, Any]]]],
) -> tuple[
    list[dict[str, Any]],
    dict[str, list[dict[str, Any]]],
    dict[str, list[dict[str, Any]]],
    dict[str, list[dict[str, Any]]],
]:
    results: list[dict[str, Any]] = []
    filtered_trades_by_window: dict[str, list[dict[str, Any]]] = {}
    overlap_trades_by_window: dict[str, list[dict[str, Any]]] = {}
    enriched_trades_by_window: dict[str, list[dict[str, Any]]] = {}
    for label, cfg in consensus.prior.base.WINDOWS.items():
        snapshot = consensus.prior.base.shadow._load_snapshot(cfg["snapshot"])
        candidates = consensus._consensus_candidates_for_window(label, source_rows_by_window)
        full_target_trades, target_diagnostics = consensus._select_target_trades(snapshot, candidates)
        before_result = baselines[label]["result"]
        before = baselines[label]["metrics"]
        core_entries = _core_entries_by_entry_date(before_result)
        enriched_full = [_with_core_overlap_context(row, core_entries) for row in full_target_trades]
        filtered = [row for row in enriched_full if not row.get("same_day_core_overlap")]
        overlap = [row for row in enriched_full if row.get("same_day_core_overlap")]

        filtered_overlay = consensus.prior.base._overlay_from_paper_trades(before_result, filtered)
        full_overlay = consensus.prior.base._overlay_from_paper_trades(before_result, enriched_full)
        after = consensus.prior.base.overlay_helper._metrics_with_overlay(before_result, filtered_overlay)
        accepted_after = consensus.prior.base.overlay_helper._metrics_with_overlay(before_result, full_overlay)
        raw_delta = consensus.prior.base.overlay_helper._delta(after, before)
        accepted_raw_delta = consensus.prior.base.overlay_helper._delta(accepted_after, before)
        vs_accepted_delta = consensus.prior.base.overlay_helper._delta(after, accepted_after)

        result = {
            "label": label,
            "start": cfg["start"],
            "end": cfg["end"],
            "snapshot": cfg["snapshot"],
            "before": before,
            "after": after,
            "accepted_comparator_after": accepted_after,
            "comparison": {
                "expected_value_score_delta": raw_delta["expected_value_score"],
                "strategy_total_pnl_delta": raw_delta["total_pnl"],
                "total_pnl_delta": raw_delta["total_pnl"],
                "max_drawdown_delta": raw_delta["max_drawdown_pct"],
                "raw_delta": raw_delta,
            },
            "accepted_comparator_comparison": {
                "expected_value_score_delta": accepted_raw_delta["expected_value_score"],
                "strategy_total_pnl_delta": accepted_raw_delta["total_pnl"],
                "total_pnl_delta": accepted_raw_delta["total_pnl"],
                "max_drawdown_delta": accepted_raw_delta["max_drawdown_pct"],
                "raw_delta": accepted_raw_delta,
            },
            "vs_accepted_comparator": {
                "expected_value_score_delta": vs_accepted_delta["expected_value_score"],
                "strategy_total_pnl_delta": vs_accepted_delta["total_pnl"],
                "total_pnl_delta": vs_accepted_delta["total_pnl"],
                "max_drawdown_delta": vs_accepted_delta["max_drawdown_pct"],
                "raw_delta": vs_accepted_delta,
            },
            "target_trade_count": len(filtered),
            "target_trade_pnl_usd": round(sum(_safe_float(row.get("pnl")) for row in filtered), 2),
            "accepted_comparator_target_trade_count": len(enriched_full),
            "accepted_comparator_target_trade_pnl_usd": round(
                sum(_safe_float(row.get("pnl")) for row in enriched_full),
                2,
            ),
            "same_day_core_overlap_trade_count": len(overlap),
            "same_day_core_overlap_trade_pnl_usd": round(
                sum(_safe_float(row.get("pnl")) for row in overlap),
                2,
            ),
            "same_ticker_core_overlap_trade_count": sum(
                1 for row in overlap if row.get("same_ticker_core_overlap")
            ),
            "raw_consensus_candidate_count": len(candidates),
            "target_diagnostics": {
                **target_diagnostics,
                "core_overlap_rule_version": RULE_VERSION,
                "same_day_core_entry_dates": sorted(core_entries),
                "same_day_core_entry_date_count": len(core_entries),
                "core_overlap_filtered_trade_count": len(overlap),
                "core_overlap_filtered_pnl_usd": round(
                    sum(_safe_float(row.get("pnl")) for row in overlap),
                    2,
                ),
            },
        }
        results.append(result)
        filtered_trades_by_window[label] = filtered
        overlap_trades_by_window[label] = overlap
        enriched_trades_by_window[label] = enriched_full
    return results, filtered_trades_by_window, overlap_trades_by_window, enriched_trades_by_window


def _gate4_decision(
    aggregate: dict[str, Any],
    accepted_comparator: dict[str, Any],
    vs_accepted_comparator: dict[str, Any],
    results: list[dict[str, Any]],
    target_summary: dict[str, Any],
) -> dict[str, Any]:
    base_gate = consensus.prior._gate4_decision(aggregate, results, target_summary)
    comparator_ev_delta = _safe_float(vs_accepted_comparator["comparison"].get("expected_value_score_delta"))
    comparator_pnl_delta = _safe_float(vs_accepted_comparator["comparison"].get("strategy_total_pnl_delta"))
    comparator_ev_windows = [
        row["label"]
        for row in results
        if _safe_float(row["vs_accepted_comparator"].get("expected_value_score_delta")) > 0.0
    ]
    comparator_pnl_windows = [
        row["label"]
        for row in results
        if _safe_float(row["vs_accepted_comparator"].get("strategy_total_pnl_delta")) > 0.0
    ]
    gates = {
        **base_gate["gates"],
        "beats_current_accepted_consensus_ev": comparator_ev_delta > 0.0,
        "beats_current_accepted_consensus_pnl": comparator_pnl_delta > 0.0,
        "all_windows_beat_current_accepted_consensus_ev": len(comparator_ev_windows) == len(results),
        "all_windows_beat_current_accepted_consensus_pnl": len(comparator_pnl_windows) == len(results),
    }
    passed = all(gates.values())
    if passed:
        decision = "positive_replay_lead_not_promoted_requires_shared_core_overlap_adapter"
        rationale = (
            "The no-core-overlap consensus slice beat both the core baseline and "
            "the current accepted consensus comparator. Promotion would require a "
            "shared production/backtest core-overlap adapter before retention."
        )
    elif base_gate["passed"]:
        decision = "rejected_positive_vs_core_but_worse_than_current_accepted_consensus"
        rationale = (
            "The no-core-overlap consensus slice is positive versus the core "
            "baseline, but it removes profitable accepted-consensus rows and does "
            "not beat the current accepted comparator. Do not retain it."
        )
    else:
        decision = "rejected_accepted_consensus_core_overlap_replacement_value"
        rationale = "The no-core-overlap consensus slice failed one or more core Gate 4 checks."
    failed = [key for key, value in gates.items() if not value]
    return {
        "decision": decision,
        "passed": passed,
        "accepted": False,
        "rationale": rationale,
        "gates": gates,
        "failed_reasons": failed,
        "base_gate": base_gate,
        "comparator_ev_windows_improved": comparator_ev_windows,
        "comparator_pnl_windows_improved": comparator_pnl_windows,
        "accepted_comparator_experiment_id": CURRENT_ACCEPTED_COMPARATOR_EXPERIMENT_ID,
        "accepted_comparator_aggregate": accepted_comparator,
        "vs_accepted_comparator": vs_accepted_comparator,
        "requires_parity_before_promotion": passed,
    }


def _window_table(results: list[dict[str, Any]]) -> str:
    rows = [
        "| Window | No-core trades | Overlap trades | EV before | EV after | EV delta | Accepted EV | Delta vs accepted | PnL delta |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in results:
        rows.append(
            "| {label} | {count} | {overlap_count} | {before_ev:.4f} | {after_ev:.4f} | {ev_delta:+.4f} | {accepted_ev:.4f} | {accepted_delta:+.4f} | ${pnl_delta:+,.2f} |".format(
                label=row["label"],
                count=row["target_trade_count"],
                overlap_count=row["same_day_core_overlap_trade_count"],
                before_ev=_safe_float(row["before"].get("expected_value_score")),
                after_ev=_safe_float(row["after"].get("expected_value_score")),
                ev_delta=_safe_float(row["comparison"].get("expected_value_score_delta")),
                accepted_ev=_safe_float(row["accepted_comparator_after"].get("expected_value_score")),
                accepted_delta=_safe_float(row["vs_accepted_comparator"].get("expected_value_score_delta")),
                pnl_delta=_safe_float(row["comparison"].get("strategy_total_pnl_delta")),
            )
        )
    return "\n".join(rows)


def _write_card_and_artifact(payload: dict[str, Any]) -> None:
    aggregate = payload["aggregate"]["comparison"]
    vs_accepted = payload["vs_accepted_comparator"]["comparison"]
    lines = [
        f"# {EXPERIMENT_ID} accepted consensus core-overlap replacement value",
        "",
        f"- Trial family: `{TRIAL_FAMILY}`",
        f"- Changed variable: `{CHANGED_VARIABLE}`",
        f"- Decision: `{payload['gate4']['decision']}`",
        f"- Aggregate EV delta vs core: {aggregate['expected_value_score_delta']:+.4f}",
        f"- Aggregate PnL delta vs core: ${aggregate['strategy_total_pnl_delta']:+,.2f}",
        f"- Aggregate EV delta vs accepted comparator: {vs_accepted['expected_value_score_delta']:+.4f}",
        f"- Aggregate PnL delta vs accepted comparator: ${vs_accepted['strategy_total_pnl_delta']:+,.2f}",
        f"- No-core target trades: {payload['target_summary']['target_trade_count']}",
        f"- Filtered same-day core-overlap trades: {payload['core_overlap_summary']['same_day_core_overlap_trade_count']}",
        f"- Production impact: `{PRODUCTION_IMPACT['adapter_status']}`",
        "",
        "## Gate 1-4",
        "",
        _window_table(payload["results"]),
        "",
        "## Gate 4 Checks",
        "",
    ]
    for key, value in payload["gate4"]["gates"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            payload["gate4"]["rationale"],
            "",
            "The overlap context is derived from the same before-result core trades used for the replay, keyed by paper `entry_date`. It is replay-only in this experiment and does not change live orders.",
            "",
        ]
    )
    text = "\n".join(lines) + "\n"
    _write_text(CARD_MD, text)
    _write_text(ARTIFACT_MD, text)


def _upsert_registry(payload: dict[str, Any]) -> None:
    if not REGISTRY_JSON.exists():
        return
    registry = _load_json(REGISTRY_JSON)
    experiments = registry.get("experiments")
    if not isinstance(experiments, list):
        return
    for item in experiments:
        if isinstance(item, dict) and item.get("experiment_id") == EXPERIMENT_ID:
            item["status"] = "completed"
            item["decision"] = payload["gate4"]["decision"]
            item["completed_at"] = payload["completed_at"]
            item["artifact"] = _repo_rel(OUT_JSON)
            item["log"] = _repo_rel(LOG_JSON)
            item["aggregate_expected_value_delta"] = payload["aggregate"]["comparison"][
                "expected_value_score_delta"
            ]
            item["aggregate_strategy_total_pnl_delta"] = payload["aggregate"]["comparison"][
                "strategy_total_pnl_delta"
            ]
            item["result"] = {
                "accepted": False,
                "decision": payload["gate4"]["decision"],
                "artifact": _repo_rel(OUT_JSON),
            }
            item["updated_at"] = payload["completed_at"]
            break
    registry["updated_at"] = payload["completed_at"]
    _write_json(REGISTRY_JSON, registry)


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _load_json(TICKET_JSON) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "id": EXPERIMENT_ID,
            "experiment_id": EXPERIMENT_ID,
            "status": "completed",
            "decision": payload["gate4"]["decision"],
            "completed_at": payload["completed_at"],
            "updated_at": payload["completed_at"],
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "production_impact": PRODUCTION_IMPACT,
            "gate4": payload["gate4"],
            "result": {
                "accepted": False,
                "decision": payload["gate4"]["decision"],
                "artifact": _repo_rel(OUT_JSON),
            },
        }
    )
    _write_json(TICKET_JSON, ticket)


def _experiment_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    comparison = payload["aggregate"]["comparison"]
    vs_accepted = payload["vs_accepted_comparator"]["comparison"]
    actual_success = 1 if payload["gate4"]["passed"] else 0
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["completed_at"],
        "lane": "alpha_search",
        "trial_family": TRIAL_FAMILY,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["preflight"]["alpha_hypothesis"],
        "decision": payload["gate4"]["decision"],
        "accepted": False,
        "anti_js": "No JavaScript was used.",
        "production_impact": PRODUCTION_IMPACT,
        "requires_parity_before_promotion": bool(payload["gate4"]["requires_parity_before_promotion"]),
        "prediction": PREDICTION,
        "calibration": {
            "actual_success": actual_success,
            "predicted_success_probability": PREDICTION["success_probability"],
            "brier_score": round((PREDICTION["success_probability"] - actual_success) ** 2, 6),
            "expected_ev_delta": PREDICTION["expected_ev_delta"],
            "actual_ev_delta_vs_core": comparison["expected_value_score_delta"],
            "actual_ev_delta_vs_accepted_comparator": vs_accepted["expected_value_score_delta"],
            "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
            "actual_pnl_delta_vs_core": comparison["strategy_total_pnl_delta"],
            "actual_pnl_delta_vs_accepted_comparator": vs_accepted["strategy_total_pnl_delta"],
            "realized_failure_mode": "; ".join(payload["gate4"]["failed_reasons"]) or None,
        },
        "metrics": {
            "aggregate_expected_value_before": payload["aggregate"]["before"]["expected_value_score"],
            "aggregate_expected_value_after": payload["aggregate"]["after"]["expected_value_score"],
            "aggregate_expected_value_delta": comparison["expected_value_score_delta"],
            "aggregate_strategy_total_pnl_before": payload["aggregate"]["before"]["strategy_total_pnl"],
            "aggregate_strategy_total_pnl_after": payload["aggregate"]["after"]["strategy_total_pnl"],
            "aggregate_strategy_total_pnl_delta": comparison["strategy_total_pnl_delta"],
            "accepted_comparator_expected_value_after": payload["accepted_comparator"]["after"][
                "expected_value_score"
            ],
            "accepted_comparator_strategy_total_pnl_after": payload["accepted_comparator"]["after"][
                "strategy_total_pnl"
            ],
            "delta_vs_accepted_comparator_ev": vs_accepted["expected_value_score_delta"],
            "delta_vs_accepted_comparator_pnl": vs_accepted["strategy_total_pnl_delta"],
            "target_trade_count": payload["target_summary"]["target_trade_count"],
            "target_trade_pnl_usd": payload["target_summary"]["target_trade_pnl_usd"],
            "same_day_core_overlap_trade_count": payload["core_overlap_summary"][
                "same_day_core_overlap_trade_count"
            ],
            "same_day_core_overlap_pnl_usd": payload["core_overlap_summary"][
                "same_day_core_overlap_pnl_usd"
            ],
            "non_core_overlap_pnl_usd": payload["core_overlap_summary"]["non_core_overlap_pnl_usd"],
            "max_drawdown_delta": payload["gate4"]["base_gate"]["max_drawdown_delta"],
            "max_single_positive_share": payload["target_summary"]["max_single_positive_share"],
            "positive_pnl_hhi": payload["target_summary"]["positive_pnl_hhi"],
        },
        "windows": [
            {
                "label": row["label"],
                "expected_value_before": row["before"]["expected_value_score"],
                "expected_value_after": row["after"]["expected_value_score"],
                "expected_value_delta": row["comparison"]["expected_value_score_delta"],
                "strategy_total_pnl_delta": row["comparison"]["strategy_total_pnl_delta"],
                "accepted_comparator_expected_value_after": row["accepted_comparator_after"][
                    "expected_value_score"
                ],
                "expected_value_delta_vs_accepted_comparator": row["vs_accepted_comparator"][
                    "expected_value_score_delta"
                ],
                "strategy_total_pnl_delta_vs_accepted_comparator": row["vs_accepted_comparator"][
                    "strategy_total_pnl_delta"
                ],
                "target_trade_count": row["target_trade_count"],
                "same_day_core_overlap_trade_count": row["same_day_core_overlap_trade_count"],
                "target_trade_pnl_usd": row["target_trade_pnl_usd"],
            }
            for row in payload["results"]
        ],
        "artifact_path": _repo_rel(OUT_JSON),
    }


def main() -> None:
    consensus._configure_prior_module()
    gate2 = consensus.prior.base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    source_rows = consensus.prior._source_rows_by_window()
    baselines = consensus.prior._load_baselines()
    results, target_trades_by_window, overlap_trades_by_window, enriched_trades_by_window = _run_windows(
        baselines,
        source_rows,
    )
    aggregate = consensus.prior._aggregate_results(results)
    accepted_comparator = _aggregate_for_after_key(results, "accepted_comparator_after")
    vs_accepted_comparator = _aggregate_after_vs_comparator(results)
    target_summary = consensus.prior._target_summary(target_trades_by_window)
    full_target_summary = consensus.prior._target_summary(enriched_trades_by_window)
    overlap_summary = consensus.prior._target_summary(overlap_trades_by_window)
    core_overlap_summary = _summary_by_overlap(enriched_trades_by_window)
    gate4 = _gate4_decision(
        aggregate,
        accepted_comparator,
        vs_accepted_comparator,
        results,
        target_summary,
    )
    completed_at = _utc_now()
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": completed_at,
        "completed_at": completed_at,
        "preflight": {
            "alpha_hypothesis": (
                "Accepted independent-source consensus candidates should have "
                "positive replacement value only when they do not compete with "
                "same-day core A/B candidates; same-day core overlap should "
                "identify weaker deployment priority."
            ),
            "category": "candidate_pool",
            "playbook_alignment": (
                "Matches the playbook next-valid request for same-day core "
                "replacement-value evidence before activation instead of "
                "retuning source count, source set, FINRA thresholds, or "
                "notional."
            ),
            "nearby_prior_experiments": [
                "exp-20260531-030",
                "exp-20260601-001",
                "exp-20260601-028",
                "exp-20260603-014",
                "exp-20260603-015",
                "exp-20260603-025",
            ],
            "prior_difference": (
                "The accepted independent-source consensus candidate source is "
                "fixed. This run only tests same-day core-entry overlap as a "
                "deployment-priority/replacement-value field."
            ),
            "single_causal_variable": CHANGED_VARIABLE,
            "acceptance_criteria": {
                "canonical_windows": list(consensus.prior.base.WINDOWS.keys()),
                "aggregate_expected_value_delta_vs_core": "> 0",
                "aggregate_pnl_delta_vs_core": "> 0",
                "per_window_expected_value_delta_vs_core": "3 of 3 windows > 0",
                "per_window_pnl_delta_vs_core": "3 of 3 windows > 0",
                "must_beat_current_accepted_consensus_comparator": True,
                "minimum_target_trades": consensus.prior.MIN_TARGET_TRADES,
                "minimum_target_windows": consensus.prior.MIN_TARGET_WINDOWS,
                "max_drawdown_drift": consensus.prior.MAX_DRAWDOWN_WORSE,
                "survival_rate_floor": 0.05,
                "max_single_positive_share": consensus.prior.MAX_SINGLE_POSITIVE_SHARE,
                "positive_pnl_hhi_max": consensus.prior.MAX_POSITIVE_HHI,
            },
            "reproducibility": (
                "All source artifacts, canonical windows, before/after metrics, "
                "accepted comparator metrics, target trades, and core-overlap "
                "diagnostics are persisted under this experiment ID."
            ),
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "candidate_pool / deployment priority: accepted independent-source "
                "consensus rows without same-day core slot competition may have "
                "cleaner scarce-slot replacement value."
            ),
            "2_history_check": {
                "exp-20260603-014": (
                    "Accepted source-family consensus improved all windows versus core "
                    "and became the current accepted comparator after exp-20260603-015."
                ),
                "exp-20260603-025": (
                    "VIX low-stress context was positive versus core but worse than the "
                    "current accepted consensus comparator."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Same docs/backtesting.md three windows. Accept only if the no-core-overlap "
                "slice improves aggregate and all windows versus core and also beats the "
                "current accepted exp-20260603-014 consensus comparator."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260603_026_accepted_consensus_core_overlap_replacement_value.py"
            ),
        },
        "source_files": {
            name: _repo_rel(REPO_ROOT / path)
            for name, path in consensus.SOURCE_FILES.items()
        },
        "accepted_comparator": accepted_comparator,
        "accepted_comparator_experiment_id": CURRENT_ACCEPTED_COMPARATOR_EXPERIMENT_ID,
        "accepted_comparator_artifact": _repo_rel(CURRENT_ACCEPTED_COMPARATOR_ARTIFACT),
        "vs_accepted_comparator": vs_accepted_comparator,
        "rule": {
            "rule_version": RULE_VERSION,
            "candidate_source_fixed": "exp-20260603-014 independent source-family consensus",
            "filter": "keep selected paper target trades only when same_day_core_overlap is false",
            "core_overlap_key": "paper entry_date matched to before_result core trade entry_date",
            "base_notional_usd": consensus.prior.BASE_NOTIONAL_USD,
            "hold_days": consensus.prior.HOLD_DAYS,
            "max_paper_trades_per_day": consensus.prior.MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": consensus.prior.SAME_TICKER_COOLDOWN_DAYS,
        },
        "production_impact": PRODUCTION_IMPACT,
        "prediction": PREDICTION,
        "gate1": {
            "baseline_source": "consensus.prior._load_baselines() with docs/backtesting.md canonical windows",
            "canonical_windows": list(consensus.prior.base.WINDOWS.keys()),
            "passed": True,
        },
        "gate2": {
            **gate2,
            "additional_field_check": {
                "field": "before_result.trades[*].entry_date",
                "source": "same standard core baseline result used for each window",
                "status": "ok",
                "known_at": "available from replay before paper overlay evaluation",
            },
        },
        "aggregate": aggregate,
        "results": results,
        "target_summary": target_summary,
        "full_target_summary": full_target_summary,
        "overlap_target_summary": overlap_summary,
        "core_overlap_summary": core_overlap_summary,
        "target_trades_by_window": target_trades_by_window,
        "same_day_core_overlap_trades_by_window": overlap_trades_by_window,
        "all_selected_trades_by_window": enriched_trades_by_window,
        "gate4": gate4,
        "anti_js": "No JavaScript was used.",
    }

    _write_json(OUT_JSON, payload)
    _write_json(BEFORE_JSON, aggregate["before"])
    _write_json(AFTER_JSON, aggregate["after"])
    _write_json(ACCEPTED_COMPARATOR_JSON, accepted_comparator["after"])
    record = _experiment_log_record(payload)
    _write_json(LOG_JSON, record)
    _write_card_and_artifact(payload)
    _update_ticket(payload)
    _upsert_registry(payload)
    consensus.prior.base._upsert_jsonl(EXPERIMENT_LOG, record)

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": gate4["decision"],
                "aggregate_vs_core": aggregate["comparison"],
                "aggregate_vs_accepted_comparator": vs_accepted_comparator["comparison"],
                "core_overlap_summary": core_overlap_summary,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
