"""exp-20260605-021: lagged consensus fill-delay gap guard scout.

Replay-only alpha search. The accepted lagged free-data consensus adapter from
exp-20260604-009 is fixed as the before comparator. This experiment changes one
execution-time variable: skip an accepted lagged consensus paper entry when the
next-open raw fill is more than 2% above the signal-day close.

No shared adapter, production path, live orders, source set, source-family map,
lagged window, cooldown, ranking, sizing, hold period, exits, LLM, or news
behavior is changed. No JavaScript is used.
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
QUANT_DIR = REPO_ROOT / "quant"
for import_path in (REPO_ROOT, EXPERIMENTS_DIR, QUANT_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260604_008_lagged_independent_source_consensus as lagged  # noqa: E402


EXPERIMENT_ID = "exp-20260605-021"
STEM = "lagged_consensus_fill_delay_gap_guard"
TRIAL_FAMILY = "accepted_free_data_cross_source_consensus_fill_delay_execution"
TRIAL_VARIANT_ID = "accepted_lagged_consensus_fill_delay_gap_guard_v1"
CHANGED_VARIABLE = "accepted_lagged_consensus_max_next_open_gap_from_signal_close_pct_v1"
RULE_VERSION = "accepted_lagged_consensus_fill_delay_gap_guard_v1"

MAX_NEXT_OPEN_GAP_FROM_SIGNAL_CLOSE_PCT = 0.02
MIN_KEPT_SOURCE_SHARE = 0.50
MAX_BLOCKED_SOURCE_SHARE = 0.50

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260605_021_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

ACCEPTED_COMPARATOR_ID = "exp-20260604-009"
ACCEPTED_COMPARATOR_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / ACCEPTED_COMPARATOR_ID
    / "exp_20260604_009_lagged_consensus_shared_adapter.json"
)

PREDICTION = {
    "success_probability": 0.24,
    "expected_ev_delta": 0.20,
    "expected_pnl_delta": 3000.0,
    "main_failure_modes": [
        "accepted_comparator_not_beaten",
        "window_regression",
        "filter_too_broad",
        "concentration_failed",
    ],
    "confidence_reason": (
        "Execution gap control is production-visible and distinct from "
        "source/timing/notional retunes, but the accepted lagged consensus "
        "comparator is already strong."
    ),
    "recorded_at": "2026-06-05T14:07:31+00:00",
}

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
        "This experiment changes no production code. A retained result would "
        "need the shared free-data consensus adapter to compute the same "
        "execution-time next-open gap guard in daily production and historical "
        "replay, with parity tests, before any report queue, paper ledger, or "
        "order surface could change."
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    try:
        return Path(path).resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path).replace("\\", "/")


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=2, sort_keys=True)
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


def _row_value(row: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in row:
            return row[name]
    return None


def _snapshot_row(snapshot: dict[str, Any], ticker: str, signal_date: str) -> dict[str, Any] | None:
    ohlcv = snapshot.get("ohlcv") if isinstance(snapshot.get("ohlcv"), dict) else snapshot
    rows = ohlcv.get(ticker) or ohlcv.get(ticker.upper()) or []
    for row in rows:
        row_date = str(_row_value(row, "date", "Date") or "")[:10]
        if row_date == signal_date:
            return row
    return None


def _fill_delay_context(snapshot: dict[str, Any], trade: dict[str, Any]) -> dict[str, Any]:
    ticker = str(trade.get("ticker") or "").upper()
    signal_date = str(trade.get("signal_date") or trade.get("date") or "")[:10]
    row = _snapshot_row(snapshot, ticker, signal_date) if ticker and signal_date else None
    signal_close = _safe_float(_row_value(row or {}, "close", "Close"), default=float("nan"))
    entry_raw_open = _safe_float(trade.get("entry_raw_open"), default=float("nan"))
    if signal_close > 0.0 and entry_raw_open > 0.0:
        gap_pct = (entry_raw_open - signal_close) / signal_close
    else:
        gap_pct = None

    blocked = gap_pct is not None and gap_pct > MAX_NEXT_OPEN_GAP_FROM_SIGNAL_CLOSE_PCT
    if gap_pct is None:
        status = "missing_signal_close_or_entry_open"
    elif blocked:
        status = "blocked_next_open_gap_too_high"
    else:
        status = "kept_next_open_gap_inside_guard"

    return {
        "fill_delay_rule_version": RULE_VERSION,
        "fill_delay_known_at": "next-open raw price known before paper fill",
        "fill_delay_trade_enabled": False,
        "fill_delay_alters_orders": False,
        "fill_delay_status": status,
        "fill_delay_blocked_v1": blocked,
        "fill_delay_signal_close": round(signal_close, 6) if math.isfinite(signal_close) else None,
        "fill_delay_entry_raw_open": round(entry_raw_open, 6)
        if math.isfinite(entry_raw_open)
        else None,
        "fill_delay_next_open_gap_pct": round(gap_pct, 6) if gap_pct is not None else None,
        "fill_delay_max_next_open_gap_pct": MAX_NEXT_OPEN_GAP_FROM_SIGNAL_CLOSE_PCT,
    }


def _run_gap_guard_windows(
    baselines: dict[str, dict[str, Any]],
    comparator_results: list[dict[str, Any]],
    comparator_trades: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]], dict[str, Any]]:
    comparator_by_label = {row["label"]: row for row in comparator_results}
    results: list[dict[str, Any]] = []
    avoided_by_window: dict[str, list[dict[str, Any]]] = {}
    diagnostics: dict[str, Any] = {
        "source_trade_count_by_window": {},
        "kept_trade_count_by_window": {},
        "blocked_trade_count_by_window": {},
        "status_counts_by_window": {},
        "blocked_trade_sample_by_window": {},
    }

    for label, cfg in lagged.same_day.prior.base.WINDOWS.items():
        snapshot = lagged.same_day.prior.base.shadow._load_snapshot(cfg["snapshot"])
        before_result = baselines[label]["result"]
        before = comparator_by_label[label]["after"]
        kept_rows: list[dict[str, Any]] = []
        blocked_incremental_rows: list[dict[str, Any]] = []
        status_counts: Counter[str] = Counter()
        samples: list[dict[str, Any]] = []

        for trade in comparator_trades[label]:
            context = _fill_delay_context(snapshot, trade)
            status_counts[str(context["fill_delay_status"])] += 1
            annotated = {
                **trade,
                **context,
                "rule_version": RULE_VERSION,
                "strategy": "lagged_free_data_consensus_fill_delay_gap_guard",
                "trade_enabled": False,
                "alters_orders": False,
            }
            base_pnl = _safe_float(trade.get("pnl"))
            if context["fill_delay_blocked_v1"]:
                avoided = {
                    **annotated,
                    "pnl": round(-base_pnl, 2),
                    "paper_pnl": round(-base_pnl, 2),
                    "blocked_trade_original_pnl": round(base_pnl, 2),
                    "incremental_avoided_pnl": round(-base_pnl, 2),
                    "paper_pnl_source": "lagged_consensus_fill_delay_gap_guard_avoided_pnl",
                }
                blocked_incremental_rows.append(avoided)
                if len(samples) < 20:
                    samples.append(annotated)
            else:
                kept_rows.append(annotated)

        after_overlay = lagged.same_day.prior.base._overlay_from_paper_trades(
            before_result,
            kept_rows,
        )
        after = lagged.same_day.prior.base.overlay_helper._metrics_with_overlay(
            before_result,
            after_overlay,
        )
        raw_delta = lagged.same_day.prior.base.overlay_helper._delta(after, before)
        comparison = {
            "expected_value_score_delta": raw_delta["expected_value_score"],
            "strategy_total_pnl_delta": raw_delta["total_pnl"],
            "total_pnl_delta": raw_delta["total_pnl"],
            "max_drawdown_delta": raw_delta["max_drawdown_pct"],
            "raw_delta": raw_delta,
        }
        source_count = len(comparator_trades[label])
        blocked_count = len(blocked_incremental_rows)
        results.append(
            {
                "label": label,
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
                "before": before,
                "after": after,
                "comparison": comparison,
                "source_trade_count": source_count,
                "kept_trade_count": len(kept_rows),
                "target_trade_count": blocked_count,
                "target_trade_pnl_usd": round(
                    sum(_safe_float(row.get("pnl")) for row in blocked_incremental_rows),
                    2,
                ),
                "fill_delay_status_counts": dict(sorted(status_counts.items())),
            }
        )
        avoided_by_window[label] = blocked_incremental_rows
        diagnostics["source_trade_count_by_window"][label] = source_count
        diagnostics["kept_trade_count_by_window"][label] = len(kept_rows)
        diagnostics["blocked_trade_count_by_window"][label] = blocked_count
        diagnostics["status_counts_by_window"][label] = dict(sorted(status_counts.items()))
        diagnostics["blocked_trade_sample_by_window"][label] = samples

    source_total = sum(diagnostics["source_trade_count_by_window"].values())
    kept_total = sum(diagnostics["kept_trade_count_by_window"].values())
    blocked_total = sum(diagnostics["blocked_trade_count_by_window"].values())
    diagnostics.update(
        {
            "source_trade_count": source_total,
            "kept_trade_count": kept_total,
            "blocked_trade_count": blocked_total,
            "kept_source_share": round(kept_total / source_total, 6) if source_total else None,
            "blocked_source_share": round(blocked_total / source_total, 6) if source_total else None,
            "thresholds": {
                "max_next_open_gap_from_signal_close_pct": (
                    MAX_NEXT_OPEN_GAP_FROM_SIGNAL_CLOSE_PCT
                ),
                "min_kept_source_share": MIN_KEPT_SOURCE_SHARE,
                "max_blocked_source_share": MAX_BLOCKED_SOURCE_SHARE,
            },
        }
    )
    return results, avoided_by_window, diagnostics


def _gate4(
    aggregate: dict[str, Any],
    results: list[dict[str, Any]],
    target_summary: dict[str, Any],
    diagnostics: dict[str, Any],
) -> dict[str, Any]:
    base_gate = lagged.same_day.prior._gate4_decision(aggregate, results, target_summary)
    comparator_passed = (
        aggregate["comparison"]["expected_value_score_delta"] > 0.0
        and aggregate["comparison"]["strategy_total_pnl_delta"] > 0.0
        and len(base_gate["ev_windows_improved"]) == len(results)
        and len(base_gate["pnl_windows_improved"]) == len(results)
    )
    kept_share = _safe_float(diagnostics.get("kept_source_share"), default=0.0)
    blocked_share = _safe_float(diagnostics.get("blocked_source_share"), default=0.0)
    selectivity_passed = kept_share >= MIN_KEPT_SOURCE_SHARE and blocked_share <= MAX_BLOCKED_SOURCE_SHARE
    gates = {
        **base_gate["gates"],
        "beats_current_accepted_lagged_adapter": comparator_passed,
        "fill_delay_blocked_trade_count_positive": int(diagnostics["blocked_trade_count"]) > 0,
        "fill_delay_selectivity_guard_passed": selectivity_passed,
    }
    passed = bool(base_gate["passed"] and comparator_passed and selectivity_passed)
    if passed:
        decision = "positive_replay_lead_requires_shared_fill_delay_adapter"
        rationale = (
            "The fill-delay gap guard improved the current accepted lagged "
            "consensus adapter across all three windows. It is not promoted "
            "because shared live/backtest adapter parity is required first."
        )
    elif not comparator_passed:
        decision = "rejected_fill_delay_gap_guard_did_not_beat_accepted_adapter"
        rationale = (
            "The fill-delay gap guard did not beat the current accepted lagged "
            "consensus adapter across all three windows."
        )
    elif not selectivity_passed:
        decision = "rejected_fill_delay_gap_guard_failed_selectivity"
        rationale = (
            "The fill-delay gap guard was too broad or too sparse to qualify "
            "as an independent alpha variable."
        )
    elif not base_gate["gates"].get("concentration_guard_passed", False):
        decision = "rejected_fill_delay_gap_guard_incremental_concentration_failed"
        rationale = (
            "The guard improved all three windows, but avoided-loss PnL was "
            f"too concentrated: max single positive share "
            f"{target_summary['max_single_positive_share']:.4f} and HHI "
            f"{target_summary['positive_pnl_hhi']:.4f} breached Gate 4."
        )
    else:
        decision = "rejected_fill_delay_gap_guard_gate4_failed"
        rationale = base_gate["rationale"]
    return {
        "passed": passed,
        "decision": decision,
        "gates": gates,
        "rationale": rationale,
        "min_survival_rate": base_gate.get("min_survival_rate"),
        "max_drawdown_delta": base_gate.get("max_drawdown_delta"),
        "requires_parity_before_promotion": True,
        "accepted_comparator": ACCEPTED_COMPARATOR_ID,
        "kept_source_share": kept_share,
        "blocked_source_share": blocked_share,
    }


def _preflight_payload() -> dict[str, Any]:
    return {
        "alpha_hypothesis": (
            "Accepted lagged free-data consensus paper candidates with limited "
            "next-open fill-delay gap may have better replacement value than "
            "chased gap-up fills."
        ),
        "category": "entry/execution_quality",
        "playbook_alignment": (
            "Meta research favors production-visible default-off paper adapters "
            "and cost/fill-delay context. This tests an execution-time price "
            "field and avoids changing source families, prior timing, notional, "
            "hold period, ranking, live orders, or LLM authority."
        ),
        "nearby_prior_experiments": [
            "exp-20260428-017",
            "exp-20260604-009",
            "exp-20260604-011",
        ],
        "prior_difference": (
            "exp-20260428-017 accepted a core next-open adverse entry cancel; "
            "exp-20260604-009 accepted lagged source timing; exp-20260604-011 "
            "rejected signal-day cost/liquidity support due concentration. "
            "This run leaves source timing and notional fixed and tests only "
            "whether execution-time gap-up fills should be skipped."
        ),
        "single_causal_variable": CHANGED_VARIABLE,
        "acceptance_criteria": {
            "canonical_windows": list(lagged.same_day.prior.base.WINDOWS.keys()),
            "before_comparator": ACCEPTED_COMPARATOR_ID,
            "aggregate_expected_value_delta_vs_accepted_adapter": "> 0",
            "aggregate_pnl_delta_vs_accepted_adapter": "> 0",
            "per_window_expected_value_delta_vs_accepted_adapter": "3 of 3 windows > 0",
            "per_window_pnl_delta_vs_accepted_adapter": "3 of 3 windows > 0",
            "minimum_blocked_trades": lagged.same_day.prior.MIN_TARGET_TRADES,
            "minimum_target_windows": lagged.same_day.prior.MIN_TARGET_WINDOWS,
            "max_drawdown_drift": lagged.same_day.prior.MAX_DRAWDOWN_WORSE,
            "survival_rate_floor": 0.05,
            "max_single_positive_share": lagged.same_day.prior.MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi_max": lagged.same_day.prior.MAX_POSITIVE_HHI,
            "kept_source_share_min": MIN_KEPT_SOURCE_SHARE,
            "blocked_source_share_max": MAX_BLOCKED_SOURCE_SHARE,
        },
        "reproducibility": (
            ".venv\\Scripts\\python.exe -B "
            "quant\\experiments\\exp_20260605_021_lagged_consensus_fill_delay_gap_guard.py"
        ),
    }


def _experiment_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    comparison = payload["aggregate"]["comparison"]
    actual_success = 1 if payload["gate4"]["passed"] else 0
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["completed_at"],
        "lane": "alpha_search",
        "status": "accepted" if payload["gate4"]["passed"] else "rejected",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["preflight"]["alpha_hypothesis"],
        "change_type": "default_off_paper_entry_execution_alpha",
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "prior_trial_count": 3,
        "nearby_prior_experiments": payload["preflight"]["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "production_visible_execution_time_open_gap_field",
        "decision": payload["gate4"]["decision"],
        "accepted": bool(payload["gate4"]["passed"]),
        "rejection_reason": None if payload["gate4"]["passed"] else payload["gate4"]["rationale"],
        "prediction": PREDICTION,
        "calibration": {
            "actual_decision": payload["gate4"]["decision"],
            "actual_success": actual_success,
            "predicted_success_probability": PREDICTION["success_probability"],
            "brier_score": round((PREDICTION["success_probability"] - actual_success) ** 2, 6),
            "expected_ev_delta": PREDICTION["expected_ev_delta"],
            "actual_ev_delta": comparison["expected_value_score_delta"],
            "ev_prediction_error": round(
                comparison["expected_value_score_delta"] - PREDICTION["expected_ev_delta"],
                6,
            ),
            "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
            "actual_pnl_delta": comparison["strategy_total_pnl_delta"],
            "pnl_prediction_error": round(
                comparison["strategy_total_pnl_delta"] - PREDICTION["expected_pnl_delta"],
                2,
            ),
            "realized_failure_mode": None if payload["gate4"]["passed"] else payload["gate4"]["decision"],
        },
        "production_impact": PRODUCTION_IMPACT,
        "requires_parity_before_promotion": True,
        "metrics": {
            "aggregate_expected_value_before": payload["aggregate"]["before"]["expected_value_score"],
            "aggregate_expected_value_after": payload["aggregate"]["after"]["expected_value_score"],
            "aggregate_expected_value_delta": comparison["expected_value_score_delta"],
            "aggregate_strategy_total_pnl_before": payload["aggregate"]["before"]["strategy_total_pnl"],
            "aggregate_strategy_total_pnl_after": payload["aggregate"]["after"]["strategy_total_pnl"],
            "aggregate_strategy_total_pnl_delta": comparison["strategy_total_pnl_delta"],
            "source_trade_count": payload["fill_delay_diagnostics"]["source_trade_count"],
            "kept_trade_count": payload["fill_delay_diagnostics"]["kept_trade_count"],
            "blocked_trade_count": payload["fill_delay_diagnostics"]["blocked_trade_count"],
            "kept_source_share": payload["fill_delay_diagnostics"]["kept_source_share"],
            "blocked_source_share": payload["fill_delay_diagnostics"]["blocked_source_share"],
            "avoided_pnl_usd": payload["target_summary"]["target_trade_pnl_usd"],
            "max_drawdown_delta": payload["gate4"]["max_drawdown_delta"],
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
                "source_trade_count": row["source_trade_count"],
                "kept_trade_count": row["kept_trade_count"],
                "blocked_trade_count": row["target_trade_count"],
                "avoided_pnl_usd": row["target_trade_pnl_usd"],
            }
            for row in payload["results"]
        ],
        "artifact_path": _repo_rel(OUT_JSON),
        "anti_js": "No JavaScript was used.",
    }


def _write_card(payload: dict[str, Any]) -> None:
    comp = payload["aggregate"]["comparison"]
    diag = payload["fill_delay_diagnostics"]
    lines = [
        f"# {EXPERIMENT_ID} Lagged Consensus Fill-Delay Gap Guard",
        "",
        "## Decision",
        "",
        f"- Decision: `{payload['gate4']['decision']}`",
        f"- Rationale: {payload['gate4']['rationale']}",
        "",
        "## Three-Window Result",
        "",
        f"- Before comparator: `{ACCEPTED_COMPARATOR_ID}` accepted lagged free-data consensus.",
        f"- EV delta vs accepted adapter: `{comp['expected_value_score_delta']:+.4f}`",
        f"- PnL delta vs accepted adapter: `${comp['strategy_total_pnl_delta']:+,.2f}`",
        f"- Blocked trades: `{diag['blocked_trade_count']}` / `{diag['source_trade_count']}` "
        f"({diag['blocked_source_share']})",
        "",
        "| Window | EV Before | EV After | EV Delta | PnL Delta | Blocked / Source Trades |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["results"]:
        lines.append(
            f"| {row['label']} | {row['before']['expected_value_score']:.4f} | "
            f"{row['after']['expected_value_score']:.4f} | "
            f"{row['comparison']['expected_value_score_delta']:+.4f} | "
            f"${row['comparison']['strategy_total_pnl_delta']:+,.2f} | "
            f"{row['target_trade_count']} / {row['source_trade_count']} |"
        )
    lines.extend(
        [
            "",
            "## Production Impact",
            "",
            "- Replay-only; no shared adapter, production order, watchlist, ranking, sizing, exit, LLM, or news behavior changed.",
            "- A positive result requires shared live/backtest adapter support and parity tests before promotion.",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    text = "\n".join(lines)
    _write_text(CARD_MD, text)
    _write_text(ARTIFACT_MD, text)


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _load_json(TICKET_JSON) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "id": EXPERIMENT_ID,
            "experiment_id": EXPERIMENT_ID,
            "status": "completed",
            "decision": payload["gate4"]["decision"],
            "completed_at": payload["completed_at"],
            "artifact": _repo_rel(OUT_JSON),
            "markdown_artifact": _repo_rel(ARTIFACT_MD),
            "card": _repo_rel(CARD_MD),
            "log": _repo_rel(LOG_JSON),
            "production_impact": PRODUCTION_IMPACT,
            "gate4": payload["gate4"],
            "result": {
                "aggregate_expected_value_delta": payload["aggregate"]["comparison"][
                    "expected_value_score_delta"
                ],
                "aggregate_strategy_total_pnl_delta": payload["aggregate"]["comparison"][
                    "strategy_total_pnl_delta"
                ],
                "decision": payload["gate4"]["decision"],
            },
        }
    )
    _write_json(TICKET_JSON, ticket)


def _update_manifest(payload: dict[str, Any]) -> None:
    manifest = _load_json(MANIFEST_JSON) if MANIFEST_JSON.exists() else {}
    manifest.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": "completed",
            "decision": payload["gate4"]["decision"],
            "completed_at": payload["completed_at"],
            "artifacts": [
                _repo_rel(OUT_JSON),
                _repo_rel(LOG_JSON),
                _repo_rel(CARD_MD),
                _repo_rel(ARTIFACT_MD),
                _repo_rel(TICKET_JSON),
            ],
        }
    )
    _write_json(MANIFEST_JSON, manifest)


def _upsert_registry(payload: dict[str, Any]) -> None:
    if not REGISTRY_JSON.exists():
        return
    registry = _load_json(REGISTRY_JSON)
    experiments = registry.get("experiments")
    if isinstance(experiments, list):
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
                item["updated_at"] = payload["completed_at"]
                break
    registry["updated_at"] = payload["completed_at"]
    _write_json(REGISTRY_JSON, registry)


def main() -> None:
    lagged._configure_same_day_modules()
    gate2 = lagged.same_day.prior.base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    source_rows = lagged.same_day.prior._source_rows_by_window()
    baselines = lagged.same_day.prior._load_baselines()
    comparator_results, comparator_trades = lagged._run_lagged_windows(baselines, source_rows)
    results, avoided_by_window, diagnostics = _run_gap_guard_windows(
        baselines,
        comparator_results,
        comparator_trades,
    )
    aggregate = lagged.same_day.prior._aggregate_results(results)
    accepted_comparator_aggregate = lagged.same_day.prior._aggregate_results(comparator_results)
    target_summary = lagged.same_day.prior._target_summary(avoided_by_window)
    gate4 = _gate4(aggregate, results, target_summary, diagnostics)
    completed_at = _utc_now()

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": completed_at,
        "completed_at": completed_at,
        "lane": "alpha_search",
        "preflight": _preflight_payload(),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "entry/execution_quality: accepted lagged free-data consensus "
                "paper candidates with limited next-open fill-delay gap may "
                "have better replacement value than chased gap-up fills."
            ),
            "2_history_check": {
                "exp-20260428-017": "Accepted core 2% adverse next-open entry cancel.",
                "exp-20260604-009": "Accepted lagged consensus shared default-off adapter.",
                "exp-20260604-011": "Rejected lagged consensus signal-day cost/liquidity support due concentration.",
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Use docs/backtesting.md three fixed windows; before is the "
                "current accepted exp-20260604-009 lagged adapter. Accept only "
                "if all windows improve with survival, drawdown, sample, "
                "concentration, and selectivity guards."
            ),
            "5_reproducibility": _preflight_payload()["reproducibility"],
        },
        "rule": {
            "rule_version": RULE_VERSION,
            "max_next_open_gap_from_signal_close_pct": MAX_NEXT_OPEN_GAP_FROM_SIGNAL_CLOSE_PCT,
            "known_at": "next-open raw price known before paper fill",
            "unchanged": {
                "accepted_source_names": sorted(lagged.same_day.SOURCE_EXPERIMENT_IDS),
                "min_source_family_count": lagged.same_day.MIN_SOURCE_FAMILY_COUNT,
                "prior_confirmation_trading_days": lagged.PRIOR_CONFIRMATION_TRADING_DAYS,
                "base_notional_usd": lagged.same_day.prior.BASE_NOTIONAL_USD,
                "hold_days": lagged.same_day.prior.HOLD_DAYS,
                "max_paper_trades_per_day": lagged.same_day.prior.MAX_PAPER_TRADES_PER_DAY,
                "same_ticker_cooldown_days": lagged.same_day.prior.SAME_TICKER_COOLDOWN_DAYS,
            },
        },
        "accepted_comparator": {
            "experiment_id": ACCEPTED_COMPARATOR_ID,
            "source_artifact": _repo_rel(ACCEPTED_COMPARATOR_JSON),
            "aggregate": accepted_comparator_aggregate,
            "target_summary": lagged.same_day.prior._target_summary(comparator_trades),
        },
        "production_impact": PRODUCTION_IMPACT,
        "prediction": PREDICTION,
        "gate2": gate2,
        "gate3": {
            "survival_floor": 0.05,
            "new_core_filter_added": False,
            "paper_entry_execution_guard_only": True,
            "min_survival_rate": min(_safe_float(row["after"].get("survival_rate")) for row in results),
        },
        "aggregate": aggregate,
        "results": results,
        "target_summary": target_summary,
        "target_trades_by_window": avoided_by_window,
        "fill_delay_diagnostics": diagnostics,
        "gate4": gate4,
        "anti_js": "No JavaScript was used.",
    }

    _write_json(OUT_JSON, payload)
    record = _experiment_log_record(payload)
    _write_json(LOG_JSON, record)
    _write_card(payload)
    _update_ticket(payload)
    _update_manifest(payload)
    _upsert_registry(payload)
    lagged.same_day.prior.base._upsert_jsonl(EXPERIMENT_LOG, record)

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": gate4["decision"],
                "aggregate_vs_accepted_adapter": aggregate["comparison"],
                "fill_delay_diagnostics": {
                    "source_trade_count": diagnostics["source_trade_count"],
                    "kept_trade_count": diagnostics["kept_trade_count"],
                    "blocked_trade_count": diagnostics["blocked_trade_count"],
                    "blocked_source_share": diagnostics["blocked_source_share"],
                },
                "anti_js": "No JavaScript was used.",
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
