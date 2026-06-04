"""exp-20260604-017: AI optical lagged-prior source confirmation scout.

Replay-only alpha search. This tests one variable versus the accepted lagged
free-data consensus adapter: the accepted AI optical IWM-confirmed paper sleeve
may confirm a current accepted source row only when it appeared for the same
ticker in the prior three trading days. AI optical is not admitted as a current
same-date anchor.

No production code, shared adapter, live orders, ranking, sizing, exits, source
artifacts, notional, hold period, cooldown, LLM, news, or default trade
surfaces are changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS_DIR = REPO_ROOT / "quant" / "experiments"
QUANT_DIR = REPO_ROOT / "quant"
for import_path in (REPO_ROOT, EXPERIMENTS_DIR, QUANT_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260604_015_vcp_lagged_prior_consensus as lagged_prior  # noqa: E402


same_day = lagged_prior.same_day

EXPERIMENT_ID = "exp-20260604-017"
STEM = "ai_optical_lagged_prior_consensus"
TRIAL_FAMILY = "accepted_free_data_cross_source_consensus_source_timing"
TRIAL_VARIANT_ID = "ai_optical_lagged_prior_3_trading_days_v1"
CHANGED_VARIABLE = "ai_optical_prior_confirmation_source_family_prior_3_trading_days_v1"
RULE_VERSION = "ai_optical_lagged_prior_confirmation_source_family_v1"
PRIOR_CONFIRMATION_TRADING_DAYS = 3

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260604_017_ai_optical_lagged_prior_consensus.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

ACCEPTED_LAGGED_COMPARATOR_ID = "exp-20260604-009"
ACCEPTED_LAGGED_COMPARATOR_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / ACCEPTED_LAGGED_COMPARATOR_ID
    / "exp_20260604_009_lagged_consensus_shared_adapter.json"
)
ACCEPTED_LAGGED_RESULTS_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260604-008"
    / "lagged_independent_source_consensus.json"
)

AI_OPTICAL_SOURCE = "AI_OPTICAL_IWM_CONFIRMED_PAPER"
AI_OPTICAL_SOURCE_EXPERIMENT_ID = "exp-20260525-003"
AI_OPTICAL_SOURCE_FAMILY = "ai_optical_iwm_confirmed"
AI_OPTICAL_SOURCE_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260525-003"
    / "ai_optical_iwm_confirmed_fixed_notional_sleeve.json"
)

SOURCE_EXPERIMENT_IDS = {
    **same_day.SOURCE_EXPERIMENT_IDS,
    AI_OPTICAL_SOURCE: AI_OPTICAL_SOURCE_EXPERIMENT_ID,
}
SOURCE_FAMILIES = {
    **same_day.SOURCE_FAMILIES,
    AI_OPTICAL_SOURCE: AI_OPTICAL_SOURCE_FAMILY,
}

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.12,
    "expected_pnl_delta": 2500.0,
    "main_failure_modes": [
        "accepted_lagged_adapter_not_beaten",
        "ai_optical_prior_overlap_sparse",
        "window_regression",
        "concentration_failed",
    ],
    "confidence_reason": (
        "AI optical same-day consensus had zero selected overlap, but lagged "
        "source timing is now accepted and may turn a zero-overlap source into "
        "prior confirmation without adding noisy tickers."
    ),
    "recorded_at": "2026-06-04T16:07:46+00:00",
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
        "require the shared accepted free-data consensus adapter to reconstruct "
        "the same AI optical prior-confirmation history in historical replay "
        "and daily production, with parity tests, before any report queue, "
        "paper notional, candidate priority, or order surface could change."
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def _repo_rel(path: Path | str) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _configure_modules() -> None:
    lagged_prior.EXPERIMENT_ID = EXPERIMENT_ID
    lagged_prior.STEM = STEM
    lagged_prior.TRIAL_FAMILY = TRIAL_FAMILY
    lagged_prior.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    lagged_prior.CHANGED_VARIABLE = CHANGED_VARIABLE
    lagged_prior.RULE_VERSION = RULE_VERSION
    lagged_prior.VCP_SOURCE = AI_OPTICAL_SOURCE
    lagged_prior.VCP_SOURCE_EXPERIMENT_ID = AI_OPTICAL_SOURCE_EXPERIMENT_ID
    lagged_prior.VCP_SOURCE_FAMILY = AI_OPTICAL_SOURCE_FAMILY
    lagged_prior.VCP_SOURCE_ARTIFACT = AI_OPTICAL_SOURCE_ARTIFACT
    lagged_prior.SOURCE_EXPERIMENT_IDS = SOURCE_EXPERIMENT_IDS
    lagged_prior.SOURCE_FAMILIES = SOURCE_FAMILIES
    lagged_prior.OUT_DIR = OUT_DIR
    lagged_prior.OUT_JSON = OUT_JSON
    lagged_prior.BEFORE_JSON = BEFORE_JSON
    lagged_prior.AFTER_JSON = AFTER_JSON
    lagged_prior.LOG_JSON = LOG_JSON
    lagged_prior.TICKET_JSON = TICKET_JSON
    lagged_prior.CARD_MD = CARD_MD
    lagged_prior.ARTIFACT_MD = ARTIFACT_MD
    lagged_prior.MANIFEST_JSON = MANIFEST_JSON
    lagged_prior.EXPERIMENT_LOG = EXPERIMENT_LOG
    lagged_prior.REGISTRY_JSON = REGISTRY_JSON
    lagged_prior.PREDICTION = PREDICTION
    lagged_prior.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    same_day._configure_prior_module()


def _safe_float(value: Any, default: float = 0.0) -> float:
    return lagged_prior._safe_float(value, default)


def _ai_optical_source_row(trade: dict[str, Any]) -> dict[str, Any]:
    market = trade.get("market_confirmation") if isinstance(trade.get("market_confirmation"), dict) else {}
    signal_date = market.get("market_state_as_of") or trade.get("decision_date") or trade.get("entry_date")
    ticker = str(trade.get("ticker") or "").upper()
    return {
        "source_name": AI_OPTICAL_SOURCE,
        "source_experiment_id": AI_OPTICAL_SOURCE_EXPERIMENT_ID,
        "date": signal_date,
        "signal_date": signal_date,
        "entry_date": trade.get("entry_date"),
        "exit_date": trade.get("exit_date"),
        "ticker": ticker,
        "paper_pnl": trade.get("pnl"),
        "pnl_usd": trade.get("pnl"),
        "return_pct": trade.get("pnl_pct_net"),
        "paper_notional_usd": trade.get("paper_notional_usd"),
        "ai_optical_iwm_momentum20": market.get("iwm_momentum20"),
        "ai_optical_spy_momentum20": market.get("spy_momentum20"),
        "ai_optical_iwm_spy_momentum_spread": market.get("iwm_spy_momentum_spread"),
        "ai_optical_min_iwm_spy_momentum_spread": market.get("min_iwm_spy_momentum_spread"),
        "known_at": f"{signal_date}T21:00:00Z" if signal_date else None,
        "trade_enabled": False,
        "alters_orders": False,
    }


def _ai_optical_rows_by_window() -> tuple[dict[str, dict[tuple[str, str], list[dict[str, Any]]]], dict[str, Any]]:
    payload = _load_json(AI_OPTICAL_SOURCE_ARTIFACT)
    rows_by_window: dict[str, dict[tuple[str, str], list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    audit = {
        "source": AI_OPTICAL_SOURCE,
        "source_experiment_id": AI_OPTICAL_SOURCE_EXPERIMENT_ID,
        "source_artifact": _repo_rel(AI_OPTICAL_SOURCE_ARTIFACT),
        "source_decision": payload.get("decision"),
        "source_gate4_passed": bool((payload.get("gate4") or {}).get("passed")),
        "windows": {},
    }
    for label, trades in (payload.get("target_trades_by_window") or {}).items():
        selected_rows = [row for row in trades if isinstance(row, dict)]
        for trade in selected_rows:
            source_row = _ai_optical_source_row(trade)
            signal_date = str(source_row.get("signal_date") or source_row.get("date") or "")
            ticker = str(source_row.get("ticker") or "").upper()
            if not signal_date or not ticker:
                continue
            rows_by_window[str(label)][(signal_date, ticker)].append(source_row)
        audit["windows"][str(label)] = {
            "selected_trade_count": len(selected_rows),
            "selected_trade_pnl_usd": round(sum(_safe_float(row.get("pnl")) for row in selected_rows), 2),
            "candidate_day_count": len(
                {
                    str(
                        ((row.get("market_confirmation") or {}).get("market_state_as_of"))
                        or row.get("entry_date")
                        or ""
                    )
                    for row in selected_rows
                    if isinstance(row, dict)
                }
            ),
            "tickers": sorted({str(row.get("ticker") or "").upper() for row in selected_rows}),
        }
    return rows_by_window, audit


def _ai_prior_summary(vcp_style_summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "prior_confirmation_trading_days": PRIOR_CONFIRMATION_TRADING_DAYS,
        "total_trade_count": vcp_style_summary["total_trade_count"],
        "ai_optical_prior_selected_trade_count": vcp_style_summary["vcp_prior_selected_trade_count"],
        "ai_optical_prior_selected_trade_count_by_window": vcp_style_summary[
            "vcp_prior_selected_trade_count_by_window"
        ],
        "ai_optical_prior_selected_trade_pnl_usd": vcp_style_summary[
            "vcp_prior_selected_trade_pnl_usd"
        ],
        "selected_family_combo_counts": vcp_style_summary["selected_family_combo_counts"],
        "selected_raw_source_combo_counts": vcp_style_summary["selected_raw_source_combo_counts"],
        "all_selected_have_min_family_count": vcp_style_summary["all_selected_have_min_family_count"],
        "current_anchor_ai_optical_count": vcp_style_summary["current_anchor_vcp_count"],
    }


def _gate4(
    aggregate: dict[str, Any],
    results: list[dict[str, Any]],
    target_summary: dict[str, Any],
    vs_lagged_comparator: dict[str, Any],
    ai_summary: dict[str, Any],
) -> dict[str, Any]:
    base_gate = same_day.prior._gate4_decision(aggregate, results, target_summary)
    comp = vs_lagged_comparator["comparison"]
    comparator_passed = (
        comp["expected_value_score_delta"] > 0.0
        and comp["strategy_total_pnl_delta"] > 0.0
        and comp["windows_ev_improved"] == 3
        and comp["windows_pnl_improved"] == 3
    )
    ai_sample_passed = int(ai_summary["ai_optical_prior_selected_trade_count"]) > 0
    source_family_passed = bool(ai_summary["all_selected_have_min_family_count"])
    no_current_ai_anchor = int(ai_summary["current_anchor_ai_optical_count"]) == 0
    gates = {
        **base_gate["gates"],
        "beats_exp_20260604_009_accepted_lagged_adapter": comparator_passed,
        "ai_optical_prior_selected_trade_count_positive": ai_sample_passed,
        "source_family_min_count_passed": source_family_passed,
        "ai_optical_not_used_as_current_anchor": no_current_ai_anchor,
    }
    passed = bool(
        base_gate["passed"]
        and comparator_passed
        and ai_sample_passed
        and source_family_passed
        and no_current_ai_anchor
    )
    if passed:
        decision = "positive_replay_lead_requires_ai_optical_lagged_shared_adapter"
        rationale = (
            "AI optical prior-confirmation timing improved core and the accepted "
            "lagged adapter comparator across all three windows. Promotion would "
            "require shared production/backtest adapter parity first."
        )
    elif not no_current_ai_anchor:
        decision = "rejected_ai_optical_lagged_prior_current_anchor_invariant_failed"
        rationale = "At least one selected trade used AI optical as a current same-date anchor."
    elif not ai_sample_passed:
        decision = "rejected_ai_optical_lagged_prior_no_selected_prior_rows"
        rationale = "The AI optical prior-confirmation rule produced no selected AI-optical-prior trades."
    elif not comparator_passed:
        decision = "rejected_ai_optical_lagged_prior_did_not_beat_accepted_lagged_adapter"
        rationale = (
            "The AI optical prior-confirmation variant did not beat exp-20260604-009 "
            "accepted lagged adapter across aggregate EV/PnL and all three "
            "per-window EV/PnL comparisons."
        )
    elif not source_family_passed:
        decision = "rejected_ai_optical_lagged_prior_source_family_invariant_failed"
        rationale = "At least one selected trade failed the independent source-family invariant."
    else:
        decision = "rejected_ai_optical_lagged_prior_gate4_failed"
        rationale = base_gate["rationale"]
    return {
        "passed": passed,
        "decision": decision,
        "gates": gates,
        "rationale": rationale,
        "min_survival_rate": base_gate.get("min_survival_rate"),
        "max_drawdown_delta": base_gate.get("max_drawdown_delta"),
        "requires_parity_before_promotion": True,
        "accepted_comparator": ACCEPTED_LAGGED_COMPARATOR_ID,
    }


def _preflight_payload() -> dict[str, Any]:
    return {
        "alpha_hypothesis": (
            "A current accepted free-data source row may be stronger when the "
            "same ticker had the accepted AI optical IWM-confirmed paper source "
            "in the prior three trading days."
        ),
        "category": "entry/candidate_pool",
        "playbook_alignment": (
            "This uses a free production-visible default-off paper source as "
            "lagged confirmation. It avoids LLM soft-ranking, direct noisy "
            "ticker expansion, state-surface tuning, post-earnings support "
            "retunes, and same-date AI optical consensus that previously had "
            "zero selected overlap."
        ),
        "nearby_prior_experiments": [
            "exp-20260603-023",
            "exp-20260604-008",
            "exp-20260604-009",
            "exp-20260604-010",
            "exp-20260604-011",
            "exp-20260604-012",
            "exp-20260604-013",
            "exp-20260604-015",
        ],
        "prior_difference": (
            "exp-20260603-023 added AI optical as a same-date independent source "
            "family and found zero selected overlap. exp-20260604-008/009 "
            "accepted prior 3-day source timing for existing source families. "
            "This run changes only the prior-history source set by adding AI "
            "optical prior rows; AI optical cannot be a current anchor."
        ),
        "single_causal_variable": CHANGED_VARIABLE,
        "acceptance_criteria": {
            "canonical_windows": list(same_day.prior.base.WINDOWS.keys()),
            "aggregate_expected_value_delta_vs_core": "> 0",
            "aggregate_pnl_delta_vs_core": "> 0",
            "per_window_expected_value_delta_vs_core": "3 of 3 windows > 0",
            "per_window_pnl_delta_vs_core": "3 of 3 windows > 0",
            "must_beat_exp_20260604_009_accepted_lagged_adapter": True,
            "per_window_delta_vs_accepted_lagged_adapter": "3 of 3 windows > 0",
            "minimum_target_trades": same_day.prior.MIN_TARGET_TRADES,
            "minimum_target_windows": same_day.prior.MIN_TARGET_WINDOWS,
            "max_drawdown_drift": same_day.prior.MAX_DRAWDOWN_WORSE,
            "survival_rate_floor": 0.05,
            "max_single_positive_share": same_day.prior.MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi_max": same_day.prior.MAX_POSITIVE_HHI,
            "source_family_min_count": same_day.MIN_SOURCE_FAMILY_COUNT,
            "ai_optical_current_anchor_count": 0,
        },
        "reproducibility": (
            ".venv\\Scripts\\python.exe -B "
            "quant\\experiments\\exp_20260604_017_ai_optical_lagged_prior_consensus.py"
        ),
    }


def _experiment_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    comparison = payload["aggregate"]["comparison"]
    accepted = payload["vs_accepted_lagged_adapter"]["comparison"]
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
        "change_type": "default_off_paper_adapter_source_timing_alpha",
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "prior_trial_count": 13,
        "nearby_prior_experiments": payload["preflight"]["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": (
            "materially_different_prior_timing_construction_for_zero_overlap_ai_optical_source_family"
        ),
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
            "accepted_lagged_adapter_ev_delta": accepted["expected_value_score_delta"],
            "accepted_lagged_adapter_pnl_delta": accepted["strategy_total_pnl_delta"],
            "accepted_lagged_adapter_windows_ev_improved": accepted["windows_ev_improved"],
            "accepted_lagged_adapter_windows_pnl_improved": accepted["windows_pnl_improved"],
            "target_trade_count": payload["target_summary"]["target_trade_count"],
            "target_trade_pnl_usd": payload["target_summary"]["target_trade_pnl_usd"],
            "ai_optical_prior_selected_trade_count": payload["ai_optical_prior_summary"][
                "ai_optical_prior_selected_trade_count"
            ],
            "ai_optical_prior_selected_trade_pnl_usd": payload["ai_optical_prior_summary"][
                "ai_optical_prior_selected_trade_pnl_usd"
            ],
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
                "target_trade_count": row["target_trade_count"],
                "target_trade_pnl_usd": row["target_trade_pnl_usd"],
                "ai_optical_prior_selected_trade_count": payload["ai_optical_prior_summary"][
                    "ai_optical_prior_selected_trade_count_by_window"
                ].get(row["label"], 0),
            }
            for row in payload["results"]
        ],
        "artifact_path": _repo_rel(OUT_JSON),
        "anti_js": "No JavaScript was used.",
    }


def _write_card(payload: dict[str, Any]) -> None:
    comp = payload["aggregate"]["comparison"]
    accepted = payload["vs_accepted_lagged_adapter"]["comparison"]
    summary = payload["ai_optical_prior_summary"]
    lines = [
        f"# {EXPERIMENT_ID} AI optical lagged-prior consensus",
        "",
        "## Decision",
        "",
        f"- Decision: `{payload['gate4']['decision']}`",
        f"- Rationale: {payload['gate4']['rationale']}",
        "",
        "## Three-window result",
        "",
        f"- Vs core: EV `{comp['expected_value_score_delta']:+.4f}`, PnL `${comp['strategy_total_pnl_delta']:+,.2f}`",
        f"- Vs accepted lagged adapter: EV `{accepted['expected_value_score_delta']:+.4f}`, PnL `${accepted['strategy_total_pnl_delta']:+,.2f}`",
        f"- AI optical prior selected trades: `{summary['ai_optical_prior_selected_trade_count']}`",
        "",
        "## Production impact",
        "",
        "- Replay-only; no production code or live/default order behavior changed.",
        "- Positive retention would require a shared AI-optical-lagged consensus adapter and parity tests first.",
        "",
        "No JavaScript was used.",
        "",
    ]
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
            item["updated_at"] = payload["completed_at"]
            break
    registry["updated_at"] = payload["completed_at"]
    _write_json(REGISTRY_JSON, registry)


def main() -> None:
    _configure_modules()
    gate2 = same_day.prior.base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    base_source_rows = same_day.prior._source_rows_by_window()
    ai_source_rows, ai_source_audit = _ai_optical_rows_by_window()
    baselines = same_day.prior._load_baselines()
    results, target_trades_by_window = lagged_prior._run_windows(
        baselines,
        base_source_rows,
        ai_source_rows,
    )
    aggregate = same_day.prior._aggregate_results(results)
    target_summary = same_day.prior._target_summary(target_trades_by_window)
    vcp_style_summary = lagged_prior._vcp_prior_summary(target_trades_by_window)
    ai_prior_summary = _ai_prior_summary(vcp_style_summary)
    comparator_payload = _load_json(ACCEPTED_LAGGED_COMPARATOR_JSON)
    comparator_results_payload = _load_json(ACCEPTED_LAGGED_RESULTS_JSON)
    vs_lagged = lagged_prior._aggregate_vs_comparator(
        results,
        comparator_results_payload["results"],
    )
    gate4 = _gate4(aggregate, results, target_summary, vs_lagged, ai_prior_summary)
    completed_at = _utc_now()

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": completed_at,
        "completed_at": completed_at,
        "lane": "alpha_search",
        "preflight": _preflight_payload(),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "entry/candidate_pool: AI optical IWM-confirmed paper rows may "
                "add value as a prior source-family confirmation for current "
                "accepted rows."
            ),
            "2_history_check": {
                "exp-20260603-023": (
                    "Rejected AI optical as same-date source-family expansion "
                    "because selected consensus overlap was zero."
                ),
                "exp-20260604-008": (
                    "Accepted positive replay lead for prior 3-day independent "
                    "source timing."
                ),
                "exp-20260604-009": (
                    "Promoted lagged source consensus to default-off shared adapter."
                ),
                "exp-20260604-015": (
                    "Rejected VCP prior confirmation because it did not beat the "
                    "accepted lagged adapter in all required comparisons."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Use docs/backtesting.md three fixed windows; retain only if "
                "the variant beats core and exp-20260604-009 accepted lagged "
                "adapter in all windows, with concentration and survival guards."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260604_017_ai_optical_lagged_prior_consensus.py"
            ),
        },
        "source_files": {
            **{name: _repo_rel(REPO_ROOT / path) for name, path in same_day.SOURCE_FILES.items()},
            AI_OPTICAL_SOURCE: _repo_rel(AI_OPTICAL_SOURCE_ARTIFACT),
        },
        "rule": {
            "rule_version": RULE_VERSION,
            "prior_confirmation_trading_days": PRIOR_CONFIRMATION_TRADING_DAYS,
            "min_source_family_count": same_day.MIN_SOURCE_FAMILY_COUNT,
            "source_families": SOURCE_FAMILIES,
            "base_notional_usd": same_day.prior.BASE_NOTIONAL_USD,
            "hold_days": same_day.prior.HOLD_DAYS,
            "max_paper_trades_per_day": same_day.prior.MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": same_day.prior.SAME_TICKER_COOLDOWN_DAYS,
            "current_anchor_source_set": "accepted_sources_only_excludes_ai_optical",
            "ai_optical_source_role": "prior_confirmation_only",
        },
        "production_impact": PRODUCTION_IMPACT,
        "prediction": PREDICTION,
        "gate2": gate2,
        "gate3": {
            "survival_floor": 0.05,
            "new_core_filter_added": False,
            "candidate_pool_source_timing_admission_only": True,
            "min_survival_rate": min(
                _safe_float(row["before"].get("survival_rate")) for row in results
            ),
        },
        "aggregate": aggregate,
        "accepted_lagged_comparator": {
            "experiment_id": ACCEPTED_LAGGED_COMPARATOR_ID,
            "source_artifact": _repo_rel(ACCEPTED_LAGGED_COMPARATOR_JSON),
            "results_artifact": _repo_rel(ACCEPTED_LAGGED_RESULTS_JSON),
            "aggregate": {
                "after": {
                    "expected_value_score": comparator_payload["metrics"][
                        "aggregate_expected_value_after"
                    ],
                    "strategy_total_pnl": comparator_payload["metrics"][
                        "aggregate_strategy_total_pnl_after"
                    ],
                    "total_pnl": comparator_payload["metrics"][
                        "aggregate_strategy_total_pnl_after"
                    ],
                },
                "before": {
                    "expected_value_score": comparator_payload["metrics"][
                        "aggregate_expected_value_before"
                    ],
                    "strategy_total_pnl": comparator_payload["metrics"][
                        "aggregate_strategy_total_pnl_before"
                    ],
                    "total_pnl": comparator_payload["metrics"][
                        "aggregate_strategy_total_pnl_before"
                    ],
                },
                "comparison": {
                    "expected_value_score_delta": comparator_payload["metrics"][
                        "aggregate_expected_value_delta"
                    ],
                    "strategy_total_pnl_delta": comparator_payload["metrics"][
                        "aggregate_strategy_total_pnl_delta"
                    ],
                    "total_pnl_delta": comparator_payload["metrics"][
                        "aggregate_strategy_total_pnl_delta"
                    ],
                },
            },
        },
        "vs_accepted_lagged_adapter": vs_lagged,
        "results": results,
        "target_summary": target_summary,
        "ai_optical_source_audit": ai_source_audit,
        "ai_optical_prior_summary": ai_prior_summary,
        "target_trades_by_window": target_trades_by_window,
        "gate4": gate4,
        "anti_js": "No JavaScript was used.",
    }

    _write_json(OUT_JSON, payload)
    _write_json(BEFORE_JSON, aggregate["before"])
    _write_json(AFTER_JSON, aggregate["after"])
    record = _experiment_log_record(payload)
    _write_json(LOG_JSON, record)
    _write_card(payload)
    _update_ticket(payload)
    _update_manifest(payload)
    _upsert_registry(payload)
    same_day.prior.base._upsert_jsonl(EXPERIMENT_LOG, record)

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": gate4["decision"],
                "aggregate_vs_core": aggregate["comparison"],
                "aggregate_vs_accepted_lagged_adapter": vs_lagged["comparison"],
                "ai_optical_prior_summary": ai_prior_summary,
                "anti_js": "No JavaScript was used.",
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
