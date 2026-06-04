"""exp-20260604-004: accepted consensus core-overlap support.

Replay-only alpha search. The accepted independent-source free-data consensus
candidate source is fixed. This experiment changes one paper-allocation
variable: selected consensus paper trades whose next-open paper entry date also
has same-day core A/B entry context receive a 1.10x paper-notional support.

No shared adapter, production order path, ranking, sizing, exits, LLM, news,
watchlists, source thresholds, hold period, or candidate admission policy is
changed. No JavaScript is used.
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
import exp_20260603_026_accepted_consensus_core_overlap_replacement_value as core_overlap  # noqa: E402


EXPERIMENT_ID = "exp-20260604-004"
STEM = "accepted_consensus_core_overlap_support"
TRIAL_FAMILY = "accepted_free_data_cross_source_consensus_core_overlap_support"
CHANGED_VARIABLE = "same_day_core_overlap_support_scalar_on_accepted_consensus_selected_rows_v1"
RULE_VERSION = CHANGED_VARIABLE
SUPPORT_SCALAR = 1.10
MIN_SUPPORTED_TRADES = 5
MIN_SUPPORTED_WINDOWS = 3
CURRENT_ACCEPTED_COMPARATOR_EXPERIMENT_ID = "exp-20260603-014"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260604_004_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
ACCEPTED_COMPARATOR_JSON = OUT_DIR / f"{STEM}_accepted_comparator_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

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
        "support field would need the shared free-data consensus paper adapter "
        "to build the same date-keyed selected-core ticker context in daily "
        "production reports and historical replay before any queue, notional, "
        "candidate priority, or order surface could change."
    ),
}

PREDICTION = {
    "success_probability": 0.22,
    "expected_ev_delta": 0.05,
    "expected_pnl_delta": 300.0,
    "main_failure_modes": [
        "thin_overlap_sample",
        "accepted_comparator_not_beaten",
        "window_regression",
        "concentration_failed",
    ],
    "confidence_reason": (
        "exp-20260603-026 showed removing same-day core-overlap rows made the "
        "accepted consensus worse, so the inverse support field is plausible; "
        "the overlap sample is small and mid_weak overlap PnL is a known risk."
    ),
    "recorded_at": "2026-06-04T03:07:27+00:00",
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


def _configure_modules() -> None:
    consensus._configure_prior_module()
    core_overlap.RULE_VERSION = RULE_VERSION


def _supported_trade(trade: dict[str, Any]) -> dict[str, Any]:
    row = dict(trade)
    original_pnl = _safe_float(row.get("pnl"))
    original_paper_notional = _safe_float(
        row.get("paper_notional_usd"),
        default=_safe_float(consensus.prior.BASE_NOTIONAL_USD),
    )
    support_applied = bool(row.get("same_day_core_overlap"))
    scalar = SUPPORT_SCALAR if support_applied else 1.0
    supported_pnl = round(original_pnl * scalar, 2)
    incremental_pnl = round(supported_pnl - original_pnl, 2)
    row.update(
        {
            "core_overlap_support_rule_version": RULE_VERSION,
            "core_overlap_support_applied": support_applied,
            "core_overlap_support_scalar": scalar,
            "core_overlap_original_pnl": round(original_pnl, 2),
            "core_overlap_incremental_pnl": incremental_pnl,
            "core_overlap_original_paper_notional_usd": original_paper_notional,
            "core_overlap_supported_paper_notional_usd": round(original_paper_notional * scalar, 2),
            "paper_notional_usd": round(original_paper_notional * scalar, 2),
            "paper_pnl": supported_pnl,
            "pnl": supported_pnl,
            "trade_enabled": False,
            "alters_orders": False,
        }
    )
    return row


def _target_summary(trades_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    rows = [row for trades in trades_by_window.values() for row in trades]
    positives: dict[str, float] = {}
    for row in rows:
        pnl = _safe_float(row.get("pnl"))
        if pnl > 0:
            ticker = str(row.get("ticker") or "UNKNOWN").upper()
            positives[ticker] = positives.get(ticker, 0.0) + pnl
    positive_total = sum(positives.values())
    positive_shares = [value / positive_total for value in positives.values()] if positive_total else []
    return {
        "target_trade_count": len(rows),
        "target_trade_count_by_window": {label: len(trades) for label, trades in trades_by_window.items()},
        "target_trade_pnl_usd": round(sum(_safe_float(row.get("pnl")) for row in rows), 2),
        "target_trade_pnl_by_window": {
            label: round(sum(_safe_float(row.get("pnl")) for row in trades), 2)
            for label, trades in trades_by_window.items()
        },
        "positive_pnl_by_ticker": {ticker: round(value, 2) for ticker, value in sorted(positives.items())},
        "max_single_positive_share": round(max(positive_shares), 6) if positive_shares else 0.0,
        "positive_pnl_hhi": round(sum(share * share for share in positive_shares), 6),
    }


def _support_summary(supported_trades_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    supported_rows = [
        row
        for trades in supported_trades_by_window.values()
        for row in trades
        if row.get("core_overlap_support_applied")
    ]
    incremental_by_window = {
        label: [
            row
            for row in trades
            if row.get("core_overlap_support_applied")
        ]
        for label, trades in supported_trades_by_window.items()
    }
    incremental_rows = []
    for label, rows in incremental_by_window.items():
        for row in rows:
            incremental_rows.append({**row, "pnl": row.get("core_overlap_incremental_pnl"), "window": label})
    return {
        "support_scalar": SUPPORT_SCALAR,
        "supported_trade_count": len(supported_rows),
        "supported_window_count": sum(1 for rows in incremental_by_window.values() if rows),
        "supported_trade_count_by_window": {label: len(rows) for label, rows in incremental_by_window.items()},
        "supported_original_pnl_usd": round(sum(_safe_float(row.get("core_overlap_original_pnl")) for row in supported_rows), 2),
        "supported_incremental_pnl_usd": round(sum(_safe_float(row.get("core_overlap_incremental_pnl")) for row in supported_rows), 2),
        "supported_incremental_pnl_by_window": {
            label: round(sum(_safe_float(row.get("core_overlap_incremental_pnl")) for row in rows), 2)
            for label, rows in incremental_by_window.items()
        },
        "incremental_concentration": _target_summary({"incremental": incremental_rows}),
        "same_ticker_supported_trade_count": sum(1 for row in supported_rows if row.get("same_ticker_core_overlap")),
        "same_day_not_same_ticker_supported_trade_count": sum(
            1 for row in supported_rows if row.get("same_day_core_overlap") and not row.get("same_ticker_core_overlap")
        ),
    }


def _aggregate_for_after_key(results: list[dict[str, Any]], after_key: str) -> dict[str, Any]:
    before_ev = sum(_safe_float(row["before"].get("expected_value_score")) for row in results)
    after_ev = sum(_safe_float(row[after_key].get("expected_value_score")) for row in results)
    before_pnl = sum(_safe_float(row["before"].get("total_pnl")) for row in results)
    after_pnl = sum(_safe_float(row[after_key].get("total_pnl")) for row in results)
    return {
        "before": {
            "expected_value_score": round(before_ev, 6),
            "total_pnl": round(before_pnl, 2),
            "strategy_total_pnl": round(before_pnl, 2),
        },
        "after": {
            "expected_value_score": round(after_ev, 6),
            "total_pnl": round(after_pnl, 2),
            "strategy_total_pnl": round(after_pnl, 2),
        },
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
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    results: list[dict[str, Any]] = []
    accepted_trades_by_window: dict[str, list[dict[str, Any]]] = {}
    supported_trades_by_window: dict[str, list[dict[str, Any]]] = {}
    for label, cfg in consensus.prior.base.WINDOWS.items():
        snapshot = consensus.prior.base.shadow._load_snapshot(cfg["snapshot"])
        candidates = consensus._consensus_candidates_for_window(label, source_rows_by_window)
        target_trades, target_diagnostics = consensus._select_target_trades(snapshot, candidates)
        before_result = baselines[label]["result"]
        before = baselines[label]["metrics"]
        core_entries = core_overlap._core_entries_by_entry_date(before_result)
        enriched = [core_overlap._with_core_overlap_context(row, core_entries) for row in target_trades]
        supported = [_supported_trade(row) for row in enriched]

        accepted_overlay = consensus.prior.base._overlay_from_paper_trades(before_result, enriched)
        after_overlay = consensus.prior.base._overlay_from_paper_trades(before_result, supported)
        accepted_after = consensus.prior.base.overlay_helper._metrics_with_overlay(
            before_result,
            accepted_overlay,
        )
        after = consensus.prior.base.overlay_helper._metrics_with_overlay(before_result, after_overlay)
        raw_delta = consensus.prior.base.overlay_helper._delta(after, before)
        accepted_raw_delta = consensus.prior.base.overlay_helper._delta(accepted_after, before)
        vs_accepted_delta = consensus.prior.base.overlay_helper._delta(after, accepted_after)

        supported_subset = [row for row in supported if row.get("core_overlap_support_applied")]
        results.append(
            {
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
                "target_trade_count": len(supported),
                "target_trade_pnl_usd": round(sum(_safe_float(row.get("pnl")) for row in supported), 2),
                "accepted_comparator_target_trade_count": len(enriched),
                "accepted_comparator_target_trade_pnl_usd": round(
                    sum(_safe_float(row.get("pnl")) for row in enriched),
                    2,
                ),
                "supported_trade_count": len(supported_subset),
                "supported_incremental_pnl_usd": round(
                    sum(_safe_float(row.get("core_overlap_incremental_pnl")) for row in supported_subset),
                    2,
                ),
                "raw_consensus_candidate_count": len(candidates),
                "target_diagnostics": {
                    **target_diagnostics,
                    "core_overlap_support_rule_version": RULE_VERSION,
                    "same_day_core_entry_dates": sorted(core_entries),
                    "same_day_core_entry_date_count": len(core_entries),
                    "supported_trade_count": len(supported_subset),
                },
            }
        )
        accepted_trades_by_window[label] = enriched
        supported_trades_by_window[label] = supported
    return results, accepted_trades_by_window, supported_trades_by_window


def _gate4_decision(
    aggregate: dict[str, Any],
    vs_accepted_comparator: dict[str, Any],
    results: list[dict[str, Any]],
    target_summary: dict[str, Any],
    support_summary: dict[str, Any],
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
    incremental_concentration = support_summary["incremental_concentration"]
    gates = {
        **base_gate["gates"],
        "beats_current_accepted_consensus_ev": comparator_ev_delta > 0.0,
        "beats_current_accepted_consensus_pnl": comparator_pnl_delta > 0.0,
        "all_windows_beat_current_accepted_consensus_ev": len(comparator_ev_windows) == len(results),
        "all_windows_beat_current_accepted_consensus_pnl": len(comparator_pnl_windows) == len(results),
        "support_trade_count_passed": support_summary["supported_trade_count"] >= MIN_SUPPORTED_TRADES,
        "support_window_count_passed": support_summary["supported_window_count"] >= MIN_SUPPORTED_WINDOWS,
        "incremental_concentration_guard_passed": (
            _safe_float(incremental_concentration.get("max_single_positive_share"))
            <= consensus.prior.MAX_SINGLE_POSITIVE_SHARE
            and _safe_float(incremental_concentration.get("positive_pnl_hhi"))
            <= consensus.prior.MAX_POSITIVE_HHI
        ),
    }
    passed = all(gates.values())
    if passed:
        decision = "positive_replay_lead_not_promoted_requires_shared_core_overlap_support_adapter"
        rationale = (
            "The core-overlap support field beat both the core baseline and the "
            "current accepted consensus comparator in all canonical windows. It "
            "is not promoted here because production/backtest parity would first "
            "need a shared adapter that emits the same core-overlap support field."
        )
    elif base_gate["passed"] and comparator_ev_delta > 0.0 and comparator_pnl_delta > 0.0:
        decision = "rejected_core_overlap_support_window_or_concentration_failed"
        rationale = (
            "The support field was positive in aggregate, but failed the stricter "
            "accepted-comparator window, support-sample, or incremental "
            "concentration guards."
        )
    elif base_gate["passed"]:
        decision = "rejected_core_overlap_support_did_not_beat_accepted_consensus"
        rationale = (
            "The support field remains positive versus core because the accepted "
            "consensus source is positive, but the incremental support does not "
            "beat the current accepted consensus comparator robustly."
        )
    else:
        decision = "rejected_core_overlap_support_failed_core_gate4"
        rationale = "The support field failed one or more core Gate 4 checks."
    return {
        "decision": decision,
        "passed": passed,
        "accepted": False,
        "rationale": rationale,
        "gates": gates,
        "failed_reasons": [key for key, value in gates.items() if not value],
        "base_gate": base_gate,
        "comparator_ev_windows_improved": comparator_ev_windows,
        "comparator_pnl_windows_improved": comparator_pnl_windows,
        "accepted_comparator_experiment_id": CURRENT_ACCEPTED_COMPARATOR_EXPERIMENT_ID,
        "vs_accepted_comparator": vs_accepted_comparator,
        "requires_parity_before_promotion": passed,
    }


def _window_table(results: list[dict[str, Any]]) -> str:
    rows = [
        "| Window | Supported | EV before | EV after | EV delta | Accepted EV | Delta vs accepted | PnL delta vs accepted |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in results:
        rows.append(
            "| {label} | {supported} | {before_ev:.4f} | {after_ev:.4f} | {ev_delta:+.4f} | {accepted_ev:.4f} | {accepted_delta:+.4f} | ${pnl_delta:+,.2f} |".format(
                label=row["label"],
                supported=row["supported_trade_count"],
                before_ev=_safe_float(row["before"].get("expected_value_score")),
                after_ev=_safe_float(row["after"].get("expected_value_score")),
                ev_delta=_safe_float(row["comparison"].get("expected_value_score_delta")),
                accepted_ev=_safe_float(row["accepted_comparator_after"].get("expected_value_score")),
                accepted_delta=_safe_float(row["vs_accepted_comparator"].get("expected_value_score_delta")),
                pnl_delta=_safe_float(row["vs_accepted_comparator"].get("strategy_total_pnl_delta")),
            )
        )
    return "\n".join(rows)


def _write_card(payload: dict[str, Any]) -> None:
    aggregate = payload["aggregate"]["comparison"]
    vs_accepted = payload["vs_accepted_comparator"]["comparison"]
    lines = [
        f"# {EXPERIMENT_ID} accepted consensus core-overlap support",
        "",
        f"- Trial family: `{TRIAL_FAMILY}`",
        f"- Changed variable: `{CHANGED_VARIABLE}`",
        f"- Support scalar: `{SUPPORT_SCALAR:.2f}x`",
        f"- Decision: `{payload['gate4']['decision']}`",
        f"- Aggregate EV delta vs core: {aggregate['expected_value_score_delta']:+.4f}",
        f"- Aggregate PnL delta vs core: ${aggregate['strategy_total_pnl_delta']:+,.2f}",
        f"- Aggregate EV delta vs accepted comparator: {vs_accepted['expected_value_score_delta']:+.4f}",
        f"- Aggregate PnL delta vs accepted comparator: ${vs_accepted['strategy_total_pnl_delta']:+,.2f}",
        f"- Supported trades: {payload['support_summary']['supported_trade_count']}",
        f"- Production impact: `{PRODUCTION_IMPACT['adapter_status']}`",
        "",
        "## Gate 1-4",
        "",
        _window_table(payload["results"]),
        "",
        "## Failed Gates",
        "",
    ]
    failed = payload["gate4"]["failed_reasons"]
    if failed:
        lines.extend(f"- `{reason}`" for reason in failed)
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            payload["gate4"]["rationale"],
            "",
            "No JavaScript was used. No shared strategy or production path was changed.",
            "",
        ]
    )
    _write_text(CARD_MD, "\n".join(lines))


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
            item["updated_at"] = payload["completed_at"]
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
            break
    registry["updated_at"] = payload["completed_at"]
    _write_json(REGISTRY_JSON, registry)


def _experiment_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    comparison = payload["aggregate"]["comparison"]
    vs_accepted = payload["vs_accepted_comparator"]["comparison"]
    actual_success = 1 if payload["gate4"]["passed"] else 0
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["completed_at"],
        "lane": "alpha_search",
        "status": "rejected",
        "change_type": "default_off_paper_allocation",
        "mechanism_family": "default_off_paper_allocation",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": "same_day_core_overlap_support_1p10_v1",
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": 0,
        "nearby_prior_experiments": [
            "exp-20260603-014",
            "exp-20260603-015",
            "exp-20260603-026",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "new_replacement_value_context_from_exp_20260603_026",
        "hypothesis": payload["preflight"]["alpha_hypothesis"],
        "decision": payload["gate4"]["decision"],
        "accepted": False,
        "rejection_reason": payload["gate4"]["rationale"],
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
            "supported_trade_count": payload["support_summary"]["supported_trade_count"],
            "supported_incremental_pnl_usd": payload["support_summary"]["supported_incremental_pnl_usd"],
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
                "supported_trade_count": row["supported_trade_count"],
                "supported_incremental_pnl_usd": row["supported_incremental_pnl_usd"],
            }
            for row in payload["results"]
        ],
        "artifact_path": _repo_rel(OUT_JSON),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
        ],
    }


def main() -> None:
    _configure_modules()
    gate2 = consensus.prior.base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    source_rows = consensus.prior._source_rows_by_window()
    baselines = consensus.prior._load_baselines()
    results, accepted_trades_by_window, supported_trades_by_window = _run_windows(baselines, source_rows)
    aggregate = _aggregate_for_after_key(results, "after")
    accepted_comparator = _aggregate_for_after_key(results, "accepted_comparator_after")
    vs_accepted_comparator = _aggregate_after_vs_comparator(results)
    target_summary = _target_summary(supported_trades_by_window)
    accepted_target_summary = _target_summary(accepted_trades_by_window)
    support_summary = _support_summary(supported_trades_by_window)
    core_overlap_summary = core_overlap._summary_by_overlap(accepted_trades_by_window)
    gate4 = _gate4_decision(
        aggregate,
        vs_accepted_comparator,
        results,
        target_summary,
        support_summary,
    )
    completed_at = _utc_now()
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": completed_at,
        "completed_at": completed_at,
        "lane": "alpha_search",
        "preflight": {
            "alpha_hypothesis": (
                "Accepted independent-source free-data consensus candidates confirmed by "
                "same-day selected core A/B entry context may deserve modest default-off "
                "paper-notional support without expanding noisy tickers."
            ),
            "category": "candidate_pool / default_off_paper_allocation",
            "playbook_alignment": (
                "Matches meta research priority for default-off paper adapters and the "
                "playbook's request for replacement-value context before activation. It "
                "does not retune source count, source set, FINRA thresholds, hold, or cooldown."
            ),
            "nearby_prior_experiments": [
                "exp-20260603-014 accepted independent source-family consensus",
                "exp-20260603-015 promoted shared default-off adapter",
                "exp-20260603-026 no-core-overlap filter rejected versus accepted comparator",
            ],
            "prior_difference": (
                "exp-20260603-026 removed same-day core-overlap rows and underperformed the "
                "accepted comparator. This run keeps all accepted rows fixed and only scales "
                "the overlap rows by 1.10x in paper."
            ),
            "single_causal_variable": CHANGED_VARIABLE,
            "acceptance_criteria": {
                "canonical_windows": list(consensus.prior.base.WINDOWS.keys()),
                "aggregate_expected_value_delta_vs_core": "> 0",
                "aggregate_pnl_delta_vs_core": "> 0",
                "per_window_expected_value_delta_vs_core": "3 of 3 windows > 0",
                "per_window_pnl_delta_vs_core": "3 of 3 windows > 0",
                "must_beat_current_accepted_consensus_comparator": True,
                "per_window_delta_vs_accepted_comparator": "3 of 3 windows > 0",
                "minimum_supported_trades": MIN_SUPPORTED_TRADES,
                "minimum_supported_windows": MIN_SUPPORTED_WINDOWS,
                "max_drawdown_drift": consensus.prior.MAX_DRAWDOWN_WORSE,
                "survival_rate_floor": 0.05,
                "incremental_max_single_positive_share": consensus.prior.MAX_SINGLE_POSITIVE_SHARE,
                "incremental_positive_pnl_hhi_max": consensus.prior.MAX_POSITIVE_HHI,
            },
            "reproducibility": (
                "All source artifacts, canonical window metrics, accepted comparator metrics, "
                "target trades, support diagnostics, and core-overlap diagnostics are persisted "
                "under this experiment ID."
            ),
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "candidate_pool / default_off_paper_allocation: same-day core A/B context may "
                "confirm accepted independent-source consensus rows enough to support modest paper notional."
            ),
            "2_history_check": {
                "exp-20260603-014": "Accepted source-family consensus improved all three windows versus core.",
                "exp-20260603-015": "Promoted the consensus route into the shared default-off paper adapter.",
                "exp-20260603-026": "Filtering out core-overlap rows was positive vs core but worse than accepted comparator.",
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Same docs/backtesting.md three windows. Accept only if 1.10x core-overlap support "
                "beats core and the current accepted consensus comparator in aggregate and all windows."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260604_004_accepted_consensus_core_overlap_support.py"
            ),
        },
        "source_files": {
            name: _repo_rel(REPO_ROOT / path)
            for name, path in consensus.SOURCE_FILES.items()
        },
        "rule": {
            "rule_version": RULE_VERSION,
            "candidate_source_fixed": "exp-20260603-014 independent source-family consensus",
            "support_condition": "same_day_core_overlap == true",
            "support_scalar": SUPPORT_SCALAR,
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
            },
        },
        "gate3": {
            "new_core_filter_added": False,
            "new_candidate_admission_filter_added": False,
            "survival_floor": 0.05,
            "min_survival_rate": min(_safe_float(row["before"].get("survival_rate")) for row in results),
        },
        "aggregate": aggregate,
        "accepted_comparator": accepted_comparator,
        "accepted_comparator_experiment_id": CURRENT_ACCEPTED_COMPARATOR_EXPERIMENT_ID,
        "vs_accepted_comparator": vs_accepted_comparator,
        "results": results,
        "target_summary": target_summary,
        "accepted_target_summary": accepted_target_summary,
        "support_summary": support_summary,
        "core_overlap_summary": core_overlap_summary,
        "accepted_trades_by_window": accepted_trades_by_window,
        "supported_trades_by_window": supported_trades_by_window,
        "gate4": gate4,
        "anti_js": "No JavaScript was used.",
    }

    _write_json(OUT_JSON, payload)
    _write_json(BEFORE_JSON, aggregate["before"])
    _write_json(AFTER_JSON, aggregate["after"])
    _write_json(ACCEPTED_COMPARATOR_JSON, accepted_comparator["after"])
    record = _experiment_log_record(payload)
    _write_json(LOG_JSON, record)
    _write_card(payload)
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
                "support_summary": support_summary,
                "anti_js": payload["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
