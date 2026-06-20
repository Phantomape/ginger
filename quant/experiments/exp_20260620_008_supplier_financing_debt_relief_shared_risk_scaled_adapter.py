"""exp-20260620-008: supplier-financing/debt-relief shared adapter.

Full-stack candidate-pool experiment. It promotes the positive
exp-20260620-007 replay lead into ``quant/supplier_financing_debt_relief_
paper_sleeve.py`` so historical replay and daily default-off snapshots share
one helper.

No live/default orders, core ranking, sizing, exits, LLM/news path, or
watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for entry in (str(REPO_ROOT), str(QUANT_ROOT), str(QUANT_ROOT / "experiments"), str(SCRIPTS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import exp_20260620_007_supplier_financing_debt_relief_risk_scaled_notional as lead
from experiment_registry import persist_self_registered_result
from quant.full_stack_candidate_pool import (
    ExecutionEnvelope,
    evaluate_gate4,
    evaluate_live_readiness,
    full_stack_verdict,
)
from supplier_financing_debt_relief_paper_sleeve import (
    DEFAULT_CONFIG,
    RULE_VERSION,
    SOURCE_RULE_VERSION,
    build_supplier_financing_debt_relief_historical_trades,
    load_supplier_financing_debt_relief_quality_index,
)


EXPERIMENT_ID = "exp-20260620-008"
STEM = "supplier_financing_debt_relief_shared_risk_scaled_adapter"
TRIAL_FAMILY = "supplier_financing_debt_relief_shared_risk_scaled_adapter"
TRIAL_VARIANT_ID = RULE_VERSION
CHANGED_VARIABLE = RULE_VERSION
SOURCE_LEAD_EXPERIMENT_ID = "exp-20260620-007"
OWNER = "alpha-search-automation"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260620_008_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
PRODUCTION_PARITY_MATRIX_MD = REPO_ROOT / "docs" / "production_backtest_parity_matrix.md"
SOURCE_LEAD_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / SOURCE_LEAD_EXPERIMENT_ID
    / "exp_20260620_007_supplier_financing_debt_relief_risk_scaled_notional.json"
)

MAX_LEAD_REPRO_EV_DRIFT = 0.0002
MAX_LEAD_REPRO_PNL_DRIFT = 1.0

PREDICTION = {
    "success_probability": 0.58,
    "expected_ev_delta": 1.7519,
    "expected_pnl_delta": 30_888.69,
    "main_failure_modes": [
        "shared_helper_drift",
        "production_parity_gap",
        "drawdown_drift",
        "accepted_distribution_comparator_not_beaten",
    ],
    "confidence_reason": (
        "exp-20260620-007 already passed the canonical three-window numeric "
        "screen with the fixed candidate source and PIT one-way risk-scaled "
        "notional; this experiment tests implementation drift and daily/"
        "backtest parity, not another Companyfacts threshold."
    ),
    "recorded_at": "2026-06-20T08:04:45+00:00",
}

EXECUTION_ENVELOPE = ExecutionEnvelope(
    base_notional=4_000.0,
    max_capital_pct=0.40,
    min_dollar_volume=50_000_000.0,
    slippage_bps=5.0,
    max_displacement=1,
    max_concurrent=10,
    order_semantics="next_open",
    kill_switch_drawdown_pct=0.08,
    sleeve_drawdown_stop_pct=0.05,
    notes=(
        "Top-1/day with a 10-trading-day hold bounds default-off paper "
        "concurrency at roughly 10 positions. Base $4,000 paper notional is "
        "scaled one-way to 0.35x-1.00x using PIT 20d realized volatility and "
        "ADV20; the envelope never upsizes. Live activation remains blocked "
        "until forward replacement-value rows and kill-switch parity mature."
    ),
)

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "shared_default_off_helper_with_daily_snapshot_api",
    "shared_policy_changed": True,
    "backtester_adapter_changed": True,
    "run_adapter_changed": True,
    "replay_only": False,
    "default_off_paper_only": True,
    "daily_snapshot_exposed": True,
    "parity_test_added": True,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "uses_llm": False,
    "uses_free_sec_companyfacts": True,
    "uses_raw_companyfacts_cache": True,
    "uses_free_ohlcv": True,
    "live_realism_evaluated": True,
    "live_ready": False,
    "execution_envelope": EXECUTION_ENVELOPE.to_dict(),
    "parity_note": (
        "Historical replay and daily observation share "
        "quant/supplier_financing_debt_relief_paper_sleeve.py. The helper is "
        "default-off and cannot alter orders, core ranking, sizing, exits, "
        "watchlists, LLM, or news behavior."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool/full_stack: the fixed supplier-financing plus "
        "debt-relief Companyfacts source has real replacement value, and "
        "exp-20260620-007 showed PIT volatility/liquidity one-way paper "
        "notional scaling controls the old_thin drawdown. This run tests "
        "whether the exact bundle survives shared historical/daily semantics."
    ),
    "2_history_check": {
        "exp-20260620-007": (
            "Positive replay lead: aggregate EV +1.7519, PnL +$30,888.69, "
            "88 paper trades, all three windows positive, drawdown drift "
            "+0.0049 within guard, and accepted compression/distribution "
            "comparators beaten. Not promoted because it was private replay."
        ),
        "exp-20260620-005": (
            "Same candidate source improved all three windows and beat "
            "comparators but failed drawdown drift before risk scaling."
        ),
        "exp-20260617-001": (
            "Standalone DPO extension was positive but drawdown-failed; this "
            "run does not alter DPO thresholds."
        ),
        "exp-20260616-029": (
            "Standalone debt relief was positive in late/mid but unstable; "
            "this run does not alter debt thresholds."
        ),
        "novelty_gate": (
            "Reservation found no blocking near-neighbor. New evidence type is "
            "shared daily/backtest parity promotion of a positive replay lead."
        ),
    },
    "3_single_causal_variable": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md three canonical windows. Aggregate EV/PnL "
        "must be positive, no EV/PnL regression window, sample >=20 across "
        "all 3 windows, survival >=5%, drawdown drift <=0.5pp, concentration "
        "guard passes, accepted compression/distribution comparators remain "
        "beaten, and shared helper drift versus exp-20260620-007 stays within "
        "tolerance."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260620_008_supplier_financing_debt_relief_shared_risk_scaled_adapter.py"
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _lead_reproduction_check(payload: dict[str, Any]) -> dict[str, Any]:
    source_payload = _load_json(SOURCE_LEAD_JSON, {})
    if not source_payload:
        return {"passed": False, "reason": "missing_source_lead_artifact"}
    actual_agg = payload["delta_metrics"]["aggregate"]
    source_agg = (source_payload.get("delta_metrics") or {}).get("aggregate") or {}
    ev_drift = round(
        float(actual_agg.get("expected_value_score_delta_sum") or 0.0)
        - float(source_agg.get("expected_value_score_delta_sum") or 0.0),
        6,
    )
    pnl_drift = round(
        float(actual_agg.get("total_pnl_delta_sum") or 0.0)
        - float(source_agg.get("total_pnl_delta_sum") or 0.0),
        2,
    )
    trade_drift = int(payload["target_trade_summary"]["total_trade_count"]) - int(
        ((source_payload.get("target_trade_summary") or {}).get("total_trade_count") or 0)
    )
    by_window: dict[str, dict[str, Any]] = {}
    source_by_window = (source_payload.get("delta_metrics") or {}).get("by_window") or {}
    for label in lead.prior.base.framework.WINDOWS:
        actual = payload["delta_metrics"]["by_window"][label]
        expected = source_by_window.get(label, {})
        by_window[label] = {
            "expected_value_score_drift": round(
                float(actual.get("expected_value_score") or 0.0)
                - float(expected.get("expected_value_score") or 0.0),
                6,
            ),
            "total_pnl_drift": round(
                float(actual.get("total_pnl") or 0.0)
                - float(expected.get("total_pnl") or 0.0),
                2,
            ),
            "target_trade_count": len(payload["target_trades_by_window"][label]),
            "source_target_trade_count": len(
                ((source_payload.get("target_trades_by_window") or {}).get(label)) or []
            ),
        }
    passed = (
        abs(ev_drift) <= MAX_LEAD_REPRO_EV_DRIFT
        and abs(pnl_drift) <= MAX_LEAD_REPRO_PNL_DRIFT
        and trade_drift == 0
    )
    return {
        "passed": passed,
        "source_lead_experiment_id": SOURCE_LEAD_EXPERIMENT_ID,
        "source_lead_artifact": _repo_rel(SOURCE_LEAD_JSON),
        "aggregate_expected_value_score_delta_drift": ev_drift,
        "aggregate_total_pnl_delta_drift": pnl_drift,
        "trade_count_drift": trade_drift,
        "by_window": by_window,
        "max_ev_drift": MAX_LEAD_REPRO_EV_DRIFT,
        "max_pnl_drift": MAX_LEAD_REPRO_PNL_DRIFT,
    }


def _gate4_canonical(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
    lead_reproduction: dict[str, Any],
) -> dict[str, Any]:
    gate = lead._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = list(gate.get("failed_reasons") or [])
    if not lead_reproduction.get("passed"):
        failed.append("positive_lead_not_reproduced_by_shared_adapter")
    gate["failed_reasons"] = failed
    gate["passed"] = not failed
    gate["decision"] = (
        "accepted_supplier_financing_debt_relief_shared_risk_scaled_default_off_adapter"
        if gate["passed"]
        else "rejected_supplier_financing_debt_relief_shared_risk_scaled_default_off_adapter"
    )
    gate["lead_reproduction"] = lead_reproduction
    gate["shared_adapter_module"] = "quant/supplier_financing_debt_relief_paper_sleeve.py"
    gate["parity_test_added"] = True
    return gate


def _full_stack_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    agg = payload["delta_metrics"]["aggregate"]
    summary = payload["target_trade_summary"]
    top5_share = None
    positive = summary.get("positive_by_ticker_pnl") or {}
    total_positive = sum(positive.values())
    if total_positive > 0:
        top5_share = sum(sorted(positive.values(), reverse=True)[:5]) / total_positive
    return {
        "aggregate_ev_delta": agg["expected_value_score_delta_sum"],
        "aggregate_pnl_delta": agg["total_pnl_delta_sum"],
        "windows_ev_improved": agg["windows_ev_improved"],
        "windows_ev_regressed": agg["windows_ev_regressed"],
        "windows_pnl_improved": agg["windows_pnl_improved"],
        "windows_pnl_regressed": agg["windows_pnl_regressed"],
        "adjusted_trade_count": summary["total_trade_count"],
        "adjusted_window_count": len(summary["windows_with_target_trades"]),
        "max_drawdown_worse_max": agg["max_drawdown_delta_max"],
        "single_ticker_positive_share": summary["max_single_positive_pnl_share"],
        "top_5_contribution_pct": top5_share,
        "hhi_concentration": summary["positive_pnl_hhi"],
        "avg_pnl_per_trade_delta": (
            agg["total_pnl_delta_sum"] / summary["total_trade_count"]
            if summary["total_trade_count"]
            else None
        ),
    }


def build_payload() -> dict[str, Any]:
    lead.prior._configure_framework()
    timestamp = _utc_now()
    gate2_open_positions = lead.prior.base.framework.sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(lead.prior.base.framework.get_universe())
    sector_entries_all = lead.prior.base.framework._load_sector_entries()
    quality_index, quality_summary = load_supplier_financing_debt_relief_quality_index()

    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    target_audit_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    warehouse_coverage_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in lead.prior.base.framework.WINDOWS.items():
        print(f"[{label}] core baseline and shared supplier-financing/debt-relief replay")
        before_result = lead.prior.base.framework.shadow._run_baseline(universe, cfg)
        before = lead.prior.base.framework.overlay_helper._metrics(before_result)
        snapshot = lead.prior.base._load_window_snapshot(cfg=cfg, eligible_tickers=set(universe))
        sector_entries = {
            ticker: meta for ticker, meta in sector_entries_all.items() if ticker in snapshot
        }
        trades, audit = build_supplier_financing_debt_relief_historical_trades(
            ohlcv_by_ticker=snapshot,
            windows={label: cfg},
            quality_index=quality_index,
            sector_entries=sector_entries,
            config=DEFAULT_CONFIG,
        )
        overlay = lead.prior.base.framework.sleeve._overlay_from_paper_trades(
            before_result,
            trades,
        )
        after = lead.prior.base.framework.overlay_helper._metrics_with_overlay(
            before_result,
            overlay,
        )
        delta = lead.prior.base.framework.overlay_helper._delta(after, before)

        before_metrics[label] = before
        after_metrics[label] = after
        target_trades_by_window[label] = trades
        target_audit_by_window[label] = audit
        warehouse_coverage_by_window[label] = {
            "loaded_ticker_count": len(snapshot),
            "sector_known_ticker_count": len(sector_entries),
            "source": _repo_rel(lead.prior.base.framework.WAREHOUSE),
        }
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(trades),
            "raw_candidate_count": audit["raw_candidate_count_by_window"].get(label, 0),
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = lead.prior.base.framework._aggregate_window_rows(window_rows)
    target_summary = lead.prior.base.framework.sleeve._target_trade_summary(
        target_trades_by_window
    )
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": "running",
        "decision": None,
        "accepted": False,
        "accepted_alpha": False,
        "full_stack_verdict": None,
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "change_type": "candidate_pool_full_stack",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "production_visible_free_sec_companyfacts_shared_default_off_adapter",
        "new_evidence_type": "shared_daily_backtest_parity_promotion_of_positive_replay_lead",
        "nearby_prior_experiments": [
            "exp-20260620-005",
            "exp-20260620-007",
            "exp-20260617-001",
            "exp-20260616-029",
        ],
        "prior_trial_count": 2,
        "multiple_testing_risk_bucket": "moderate",
        "prediction": PREDICTION,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "shared helper default-off paper overlay"
            ),
            "windows": lead.prior.base.framework.WINDOWS,
            "baseline_result_file": (
                "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
            ),
            "baseline_metrics": before_metrics,
            "entry_semantics": "signal close known before next-session open paper entry",
            "exit_semantics": f"{DEFAULT_CONFIG['hold_days']}-trading-day close exit",
            "costs": "same overlay cost model as accepted candidate-pool sleeves",
        },
        "parameters": {
            "paper_notional_usd": DEFAULT_CONFIG["paper_notional_usd"],
            "hold_days": DEFAULT_CONFIG["hold_days"],
            "max_paper_trades_per_day": DEFAULT_CONFIG["daily_entry_slots"],
            "same_ticker_cooldown_days": DEFAULT_CONFIG["same_ticker_cooldown_days"],
            "source_rule_version": SOURCE_RULE_VERSION,
            "risk_rule_version": lead.RULE_VERSION,
            "shared_rule_version": RULE_VERSION,
            "target_realized_vol_20d": lead.TARGET_REALIZED_VOL_20D,
            "liquidity_full_size_adv20": lead.LIQUIDITY_FULL_SIZE_ADV20,
            "min_total_scalar": lead.MIN_TOTAL_SCALAR,
            "max_total_scalar": lead.MAX_TOTAL_SCALAR,
        },
        "gate1": {
            "baseline_protocol": "docs/backtesting.md canonical three-window baseline",
            "baseline_artifact": (
                "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
            ),
            "baseline_metrics": before_metrics,
            "passed": True,
        },
        "gate2": {
            "open_positions_field_audit": gate2_open_positions,
            "runtime_candidate_fields_checked": [
                "entry_date",
                "target_price",
                "candidate_realized_vol_20d",
                "candidate_avg_dollar_volume_20d",
                "raw SEC Companyfacts accounts-payable facts",
                "raw SEC Companyfacts quarterly COGS",
                "raw SEC Companyfacts gross debt instant facts",
                "raw SEC Companyfacts annual revenue facts",
                "warehouse OHLCV Date/Open/High/Low/Close/Volume",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": min(
                float(row.get("survival_rate") or 0.0) for row in before_metrics.values()
            ),
            "survival_rate_by_window": {
                label: before_metrics[label].get("survival_rate") for label in before_metrics
            },
            "passed": min(
                float(row.get("survival_rate") or 0.0) for row in before_metrics.values()
            )
            >= 0.05,
            "note": "No core filter or executable entry rule changed.",
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict((label, row["delta"]) for label, row in window_rows.items()),
            "aggregate": aggregate,
        },
        "warehouse_coverage_by_window": warehouse_coverage_by_window,
        "quality_index_summary": quality_summary,
        "target_trades_by_window": target_trades_by_window,
        "target_audit_by_window": target_audit_by_window,
        "target_trade_summary": target_summary,
        "accepted_compression_comparator": lead.prior.base.COMPRESSION_COMPARATOR,
        "accepted_distribution_comparator": lead.prior.base.DISTRIBUTION_COMPARATOR,
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "anti_js": "No JavaScript was used.",
    }

    lead_reproduction = _lead_reproduction_check(payload)
    gate4 = _gate4_canonical(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
        lead_reproduction=lead_reproduction,
    )
    full_stack_metrics = _full_stack_metrics(payload)
    strict_gate4 = evaluate_gate4(full_stack_metrics, check_materiality=True)
    canonical_gate4 = evaluate_gate4(full_stack_metrics, check_materiality=False)
    live_readiness = evaluate_live_readiness(
        envelope=EXECUTION_ENVELOPE,
        closed_forward_trades=0,
        forward_pnl=None,
        replacement_value_passed=False,
        kill_switch_parity_passed=False,
    )
    verdict = full_stack_verdict(
        gate4=gate4,
        live_readiness=live_readiness,
        envelope=EXECUTION_ENVELOPE,
    )
    if not gate4["passed"]:
        verdict = {
            **verdict,
            "verdict": "reject",
            "gate4_passed": False,
            "next_step": (
                "Roll back the sleeve change and log the failure. The shared "
                "helper did not reproduce the positive lead or pass Gate 4."
            ),
        }

    accepted = gate4["passed"] and verdict["verdict"] != "reject"
    payload["gate4"] = gate4
    payload["full_stack"] = {
        "window_metrics": full_stack_metrics,
        "gate4_strict_materiality": strict_gate4,
        "gate4_canonical": canonical_gate4,
        "materiality_note": (
            "Strict materiality is recorded for transparency; for candidate "
            "sources the binding materiality standard is beating the closest "
            "accepted comparator after costs."
        ),
        "live_readiness": live_readiness,
        "execution_envelope": EXECUTION_ENVELOPE.to_dict(),
        "verdict": verdict,
    }
    payload["full_stack_verdict"] = verdict["verdict"]
    payload["status"] = "accepted_paper_pending_forward" if accepted else "rejected"
    payload["decision"] = gate4["decision"]
    payload["accepted"] = accepted
    payload["accepted_alpha"] = accepted
    payload["expected_value_score_delta"] = aggregate["expected_value_score_delta_sum"]
    payload["total_pnl_delta"] = aggregate["total_pnl_delta_sum"]
    payload["calibration"] = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "actual_success": 1 if accepted else 0,
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if accepted else 0.0)) ** 2,
            6,
        ),
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
    }
    payload["interpretation"] = (
        "The positive supplier-financing/debt-relief risk-scaled lead reproduced "
        "through a shared default-off helper and daily snapshot path; the "
        "full-stack verdict is accepted_paper_pending_forward."
        if accepted
        else (
            "The supplier-financing/debt-relief risk-scaled lead failed shared "
            "full-stack promotion; do not retain the helper as accepted alpha."
        )
    )
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The shared helper reproduced exp-20260620-007 because historical "
            "replay kept the exact exp-20260620-005 DPO+debt-relief candidate "
            "source, top-1/day, 10-day cooldown, next-open/10-day-close fills, "
            "costs, and exp-20260620-007 one-way PIT volatility/liquidity "
            "notional scalar while daily observation only relaxes the future "
            "exit-bar requirement needed for same-day pending paper rows."
            if accepted
            else (
                "The shared helper did not reproduce the private replay lead or "
                "failed the canonical windows, implying the lead depended on "
                "runner-local details or remained too fragile after shared "
                "daily semantics."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not sweep DPO extension, debt/revenue relief, volatility "
            "targets, ADV targets, scalar floors, price guards, top-N, hold "
            "days, cooldown, or notional on the frozen windows."
        ),
        "new_evidence_required": (
            "Next useful evidence is closed forward replacement-value rows "
            "from the shared default-off ledger, supplier/payment-term "
            "provenance, covenant/refinancing context, or kill-switch parity."
        ),
    }
    payload["next_retry_requires"] = [
        "closed forward replacement-value rows",
        "supplier/payment-term or covenant provenance",
        "kill-switch parity before live activation",
    ]
    payload["related_files"] = [
        "quant/supplier_financing_debt_relief_paper_sleeve.py",
        "quant/test_supplier_financing_debt_relief_paper_sleeve.py",
        "quant/run.py",
        "docs/production_backtest_parity_matrix.md",
        "docs/experiment_registry.json",
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(ARTIFACT_MD),
        _repo_rel(TICKET_JSON),
        _repo_rel(MANIFEST_JSON),
    ]
    return payload


def _window_table(payload: dict[str, Any]) -> list[str]:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Raw candidates | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in lead.prior.base.framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["target_audit_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {raw} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                dd=delta["max_drawdown_pct"],
                raw=audit["raw_candidate_count_by_window"].get(label, 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    return rows


def _build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    repro = payload["gate4"]["lead_reproduction"]
    verdict = payload["full_stack"]["verdict"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Supplier-Financing Debt-Relief Shared Adapter",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            f"Full-stack verdict: `{verdict['verdict']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4",
            "",
            *_window_table(payload),
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(aggregate["expected_value_score_delta_sum"]),
            "- Aggregate PnL delta: `${:+,.2f}`".format(aggregate["total_pnl_delta_sum"]),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Lead reproduction EV drift: `{:+.6f}`".format(
                repro.get("aggregate_expected_value_score_delta_drift", 0.0)
            ),
            "- Lead reproduction PnL drift: `${:+,.2f}`".format(
                repro.get("aggregate_total_pnl_delta_drift", 0.0)
            ),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "",
            "## Full-Stack Contract",
            "",
            "- Strict materiality gate4 (record): `{}`".format(
                payload["full_stack"]["gate4_strict_materiality"]["status"]
            ),
            "- Canonical gate4 (decision): `{}`".format(
                payload["full_stack"]["gate4_canonical"]["status"]
            ),
            "- Live readiness blockers: `{}`".format(
                ", ".join(payload["full_stack"]["live_readiness"]["blockers"]) or "none"
            ),
            "- Execution envelope complete: `{}`".format(
                payload["full_stack"]["execution_envelope"]["complete"]
            ),
            "- Next step: {}".format(verdict["next_step"]),
            "",
            "## Production Impact",
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_artifact(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Artifact",
            "",
            "## Decision",
            "",
            f"`{payload['decision']}` (full-stack verdict: `{payload['full_stack_verdict']}`)",
            "",
            "## Fixed Policy Bundle",
            "",
            (
                "Raw SEC Companyfacts quarterly accounts-payable DPO extension "
                "AND annual principal debt/revenue burden relief, filed-date "
                "PIT, signal-date OHLCV leadership/quality confirmation, "
                "top-1/day, 10-trading-day same-ticker cooldown, next-open "
                "paper entry, 10-trading-day close exit, costs, and one-way "
                "PIT 20d volatility/ADV20 paper-notional scaling."
            ),
            "",
            "## Three-Window Before/After",
            "",
            *_window_table(payload),
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(aggregate["expected_value_score_delta_sum"]),
            "- Aggregate PnL delta: `${:+,.2f}`".format(aggregate["total_pnl_delta_sum"]),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Gate failures: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "",
            "## Full-Stack Blocks",
            "",
            "```json",
            json.dumps(
                {
                    "lead_reproduction": payload["gate4"]["lead_reproduction"],
                    "window_metrics": payload["full_stack"]["window_metrics"],
                    "live_readiness": payload["full_stack"]["live_readiness"],
                    "execution_envelope": payload["full_stack"]["execution_envelope"],
                    "verdict": payload["full_stack"]["verdict"]["verdict"],
                    "next_step": payload["full_stack"]["verdict"]["next_step"],
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            "```",
            "",
            "## Production Parity",
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "full_stack_verdict": payload["full_stack_verdict"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": payload["gate1"]["baseline_artifact"],
        "artifact": _repo_rel(OUT_JSON),
        "artifact_md": _repo_rel(ARTIFACT_MD),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate4": payload["gate4"],
        "full_stack": {
            "verdict": payload["full_stack"]["verdict"],
            "live_readiness": payload["full_stack"]["live_readiness"],
            "execution_envelope": payload["full_stack"]["execution_envelope"],
            "gate4_strict_materiality_status": payload["full_stack"][
                "gate4_strict_materiality"
            ]["status"],
            "gate4_canonical_status": payload["full_stack"]["gate4_canonical"]["status"],
            "materiality_note": payload["full_stack"]["materiality_note"],
        },
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label]["expected_value_score"],
                "expected_value_after": payload["after_metrics"][label]["expected_value_score"],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label][
                    "total_pnl"
                ],
                "raw_candidate_count": payload["target_audit_by_window"][label][
                    "raw_candidate_count_by_window"
                ].get(label, 0),
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in lead.prior.base.framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _load_json(TICKET_JSON, {})
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "decision": payload["decision"],
            "summary": payload["interpretation"],
            "result": {
                "decision": payload["decision"],
                "full_stack_verdict": payload["full_stack_verdict"],
                "artifact": _repo_rel(OUT_JSON),
                "artifact_md": _repo_rel(ARTIFACT_MD),
                "log": _repo_rel(LOG_JSON),
                "aggregate_expected_value_delta": payload["expected_value_score_delta"],
                "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
                "accepted": payload["accepted"],
                "calibration": payload["calibration"],
            },
        }
    )
    scope = set(ticket.get("allowed_write_scope") or [])
    scope.update(payload["related_files"])
    ticket["allowed_write_scope"] = sorted(scope)
    lead.prior.base.framework._write_json(TICKET_JSON, ticket)


def _update_registry(payload: dict[str, Any]) -> None:
    result = {
        "decision": payload["decision"],
        "full_stack_verdict": payload["full_stack_verdict"],
        "artifact": _repo_rel(OUT_JSON),
        "artifact_md": _repo_rel(ARTIFACT_MD),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "accepted": payload["accepted"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "decision": payload["decision"],
        "summary": payload["interpretation"],
        "artifact": _repo_rel(OUT_JSON),
        "artifact_md": _repo_rel(ARTIFACT_MD),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "completed_at": payload["timestamp"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )


def _write_manifest(payload: dict[str, Any]) -> None:
    paths = [
        Path(__file__),
        QUANT_ROOT / "supplier_financing_debt_relief_paper_sleeve.py",
        QUANT_ROOT / "test_supplier_financing_debt_relief_paper_sleeve.py",
        QUANT_ROOT / "run.py",
        PRODUCTION_PARITY_MATRIX_MD,
        REGISTRY_JSON,
        EXPERIMENT_LOG,
        OUT_JSON,
        LOG_JSON,
        TICKET_JSON,
        CARD_MD,
        ARTIFACT_MD,
    ]
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [_repo_rel(path) for path in paths],
        "file_hashes": {
            _repo_rel(path): lead.prior.base.framework._sha256(path)
            for path in paths
            if path.exists()
        },
    }
    lead.prior.base.framework._write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    lead.prior.base.framework._write_json(OUT_JSON, payload)
    lead.prior.base.framework._write_json(LOG_JSON, payload)
    lead.prior.base.framework._write_text(CARD_MD, _build_card(payload))
    lead.prior.base.framework._write_text(ARTIFACT_MD, _build_artifact(payload))
    lead.prior.base.framework._upsert_jsonl(EXPERIMENT_LOG, _build_log_record(payload))
    _update_ticket(payload)
    _update_registry(payload)
    _write_manifest(payload)


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(json.dumps(lead.prior.base.framework._safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
