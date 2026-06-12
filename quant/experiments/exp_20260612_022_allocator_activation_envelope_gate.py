"""exp-20260612-022: allocator activation envelope gate.

Narrow activation-envelope Gate 1-4 for the accepted source-priority allocator
paper sleeve. The fixed bundle declares a dedicated-bucket execution envelope
(8 max concurrent positions matching the production daily cap that replay never
enforced, 4k USD notional in a 32k USD bucket, realized-drawdown kill switch at
8pct, ADV floor, next-open no-chase orders, zero core displacement) and
re-measures the accepted allocator replay with the envelope enforced. Before =
accepted unconstrained replay; after = envelope-constrained replay. Accept only
if every canonical window keeps a positive EV delta vs the core baseline, the
aggregate EV retention is >= 80pct, and the kill switch never triggers in a
canonical window. trade_enabled stays False; live enablement remains a separate
config/release decision after genuine forward rows mature.
No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework

REPO_ROOT = framework.REPO_ROOT
QUANT_DIR = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from experiment_registry import persist_self_registered_result  # noqa: E402
import accepted_helper_source_priority_allocator_paper_sleeve as allocator  # noqa: E402

EXPERIMENT_ID = "exp-20260612-022"
STEM = "allocator_activation_envelope_gate"
CHANGED_VARIABLE = "accepted_helper_source_priority_allocator_execution_envelope_v1"
OWNER = "claude-scheduled-alpha"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260612_022_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

MIN_EV_RETENTION = 0.80
OOS_CFG = {"start": "2026-04-22", "end": "2026-06-11"}

PREDICTION = {
    "success_probability": 0.60,
    "expected_ev_delta": -0.5,
    "expected_pnl_delta": -8000.0,
    "main_failure_modes": [
        "concurrency_cap_binds_hard",
        "kill_switch_false_trigger_mid_weak",
        "retention_below_80pct",
        "window_flips_negative",
    ],
    "confidence_reason": (
        "The allocator fires about 0.9 trades per day with a 10-day hold, so "
        "steady-state concurrency is about 9; production daily already caps open "
        "positions at 8 while accepted replay never enforced the cap. The "
        "allocator ranks by ex-ante priority, so skipped marginal trades should "
        "be lower value, but if the skipped tail carries the PnL or mid_weak "
        "drawdown crosses 8pct of the bucket the declared envelope fails."
    ),
    "recorded_at": "2026-06-12T21:57:20Z",
}

def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _window_replay(label: str, cfg: dict[str, str], oos: bool) -> dict[str, Any]:
    universe = sorted(framework.get_universe())
    if oos:
        engine = framework.shadow.BacktestEngine(
            universe=universe,
            start=cfg["start"],
            end=cfg["end"],
            config=framework.shadow.BASE_CONFIG,
            replay_llm=False,
            replay_news=False,
            data_dir=str(REPO_ROOT / "data"),
            ohlcv_warehouse_path=str(framework.WAREHOUSE),
        )
        baseline = engine.run()
    else:
        baseline = framework.shadow._run_baseline(universe, cfg)
    core_metrics = framework.overlay_helper._metrics(baseline)
    core_entries = framework.shadow._baseline_entries(baseline)
    sector_entries = framework._load_sector_entries()
    snapshot = framework._load_window_snapshot(
        cfg=cfg,
        eligible_tickers=set(sector_entries),
    )
    trades, audit = allocator.build_accepted_helper_source_priority_allocator_historical_trades(
        ohlcv_by_ticker=snapshot,
        core_entries_by_date=core_entries,
        windows=OrderedDict([(label, dict(cfg))]),
        candidate_universe=sector_entries,
        sector_entries=sector_entries,
    )
    kept, skipped, envelope_audit = allocator.apply_execution_envelope_to_trades(trades)
    before_overlay = framework.sleeve._overlay_from_paper_trades(baseline, trades)
    after_overlay = framework.sleeve._overlay_from_paper_trades(baseline, kept)
    before = framework.overlay_helper._metrics_with_overlay(baseline, before_overlay)
    after = framework.overlay_helper._metrics_with_overlay(baseline, after_overlay)
    return {
        "label": label,
        "window": dict(cfg),
        "core_metrics": core_metrics,
        "before_metrics": before,
        "after_metrics": after,
        "delta": framework.overlay_helper._delta(after, before),
        "unconstrained_trade_count": len(trades),
        "kept_trade_count": len(kept),
        "envelope_audit": framework._safe(envelope_audit),
        "allocator_audit": framework._safe(audit),
        "kept_trades": framework._safe(kept),
        "skipped_sample": framework._safe(skipped[:100]),
        "before_ev_delta_vs_core": round(
            float(before["expected_value_score"]) - float(core_metrics["expected_value_score"]), 6
        ),
        "after_ev_delta_vs_core": round(
            float(after["expected_value_score"]) - float(core_metrics["expected_value_score"]), 6
        ),
        "before_pnl_delta_vs_core": round(
            float(before["total_pnl"]) - float(core_metrics["total_pnl"]), 2
        ),
        "after_pnl_delta_vs_core": round(
            float(after["total_pnl"]) - float(core_metrics["total_pnl"]), 2
        ),
    }


def _gate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    failed: list[str] = []
    before_sum = sum(row["before_ev_delta_vs_core"] for row in rows)
    after_sum = sum(row["after_ev_delta_vs_core"] for row in rows)
    retention = (after_sum / before_sum) if before_sum > 0 else None
    for row in rows:
        label = row["label"]
        if row["after_ev_delta_vs_core"] <= 0:
            failed.append("window_ev_delta_not_positive:" + label)
        if row["envelope_audit"]["final_kill_switch_state"]["triggered"]:
            failed.append("kill_switch_triggered:" + label)
    if retention is None or retention < MIN_EV_RETENTION:
        failed.append("ev_retention_below_threshold")
    passed = not failed
    return {
        "passed": passed,
        "failed_reasons": failed,
        "before_ev_delta_sum": round(before_sum, 6),
        "after_ev_delta_sum": round(after_sum, 6),
        "ev_retention": round(retention, 6) if retention is not None else None,
        "min_ev_retention": MIN_EV_RETENTION,
        "decision": (
            "accepted_allocator_activation_envelope_gate"
            if passed
            else "rejected_allocator_envelope_as_declared"
        ),
    }


def build_payload() -> dict[str, Any]:
    timestamp = framework._utc_now()
    rows: list[dict[str, Any]] = []
    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] allocator replay with and without envelope")
        rows.append(_window_replay(label, cfg, oos=False))
    gate = _gate(rows)
    print("[post_acceptance_oos] observe-only envelope replay")
    try:
        oos_row = _window_replay("post_acceptance_oos", OOS_CFG, oos=True)
    except Exception as error:  # noqa: BLE001
        oos_row = {"label": "post_acceptance_oos", "error": f"{type(error).__name__}: {error}"}
    passed = bool(gate["passed"])
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate_passed": passed,
        "failure_modes_observed": gate["failed_reasons"],
        "brier_score": round((PREDICTION["success_probability"] - (1.0 if passed else 0.0)) ** 2, 6),
    }
    skipped_total = sum(
        int(row["envelope_audit"]["skipped_trade_count"]) for row in rows
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": "accepted" if passed else "rejected",
        "decision": gate["decision"],
        "change_type": "activation_envelope_gate",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": "allocator_activation_envelope",
        "trial_variant_id": "allocator_dedicated_bucket_envelope_v1",
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "hypothesis": (
            "The accepted source-priority allocator keeps its replay edge inside the "
            "declared dedicated-bucket execution envelope: 8 max concurrent positions, "
            "4k USD notional in a 32k USD bucket, 8pct realized-drawdown kill switch, "
            "ADV floor, next-open no-chase orders, zero core displacement."
        ),
        "nearby_prior_experiments": [
            "exp-20260610-014", "exp-20260611-005", "exp-20260611-008", "exp-20260612-019",
        ],
        "execution_envelope": allocator.EXECUTION_ENVELOPE,
        "parity_gap_repaired": (
            "Production daily caps open positions at max_active_positions=8 while the "
            "accepted replay never enforced concurrency; this gate measures the "
            "constrained replay so accepted metrics and production behavior match."
        ),
        "gate4": gate,
        "windows": framework._safe(rows),
        "post_acceptance_oos_observe_only": framework._safe(oos_row),
        "envelope_skipped_trade_total": skipped_total,
        "prediction": {
            **PREDICTION,
            "actual_success": 1 if passed else 0,
            "brier_score": calibration["brier_score"],
        },
        "calibration": calibration,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three windows; before = accepted "
                "unconstrained allocator replay over core baseline; after = same trade "
                "stream post-processed by apply_execution_envelope_to_trades; "
                "post_acceptance_oos window is observe-only"
            ),
            "windows": framework.WINDOWS,
            "oos_window": OOS_CFG,
            "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
        },
        "production_impact": {
            "trade_enabled": False,
            "alters_orders": False,
            "shared_policy_changed": True,
            "shared_policy_note": (
                "EXECUTION_ENVELOPE, evaluate_kill_switch_state, and "
                "apply_execution_envelope_to_trades added to the shared allocator "
                "helper; daily snapshot now exposes execution_envelope and "
                "kill_switch_state. Selection, ranking, sizing, exits, and order "
                "behavior unchanged; sleeve remains default-off paper."
            ),
            "parity_test_added": True,
            "parity_test": "quant/test_allocator_execution_envelope.py",
            "replay_only": False,
            "daily_snapshot_exposed": True,
            "live_realism_evaluated": True,
            "live_ready": False,
            "remaining_live_blockers": [
                "genuine forward closed rows under the unified universe",
                "replay_vs_forward_parity_on_forward_rows",
                "operator_decision_on_pilot_notional",
            ],
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The allocator selects at most one ex-ante ranked row per day, so the "
                "concurrency cap mostly trims overlapping tail entries; retention and "
                "kill-switch outcomes quantify exactly what production can execute."
                if passed
                else (
                    "The declared envelope failed its gate; see failed_reasons. Do not "
                    "loosen the kill switch or grow the bucket just to pass; redesign "
                    "needs either fewer overlapping holds or a deliberate bucket-size "
                    "decision with its own gate."
                )
            ),
            "forbidden_near_neighbor_retry": (
                "Do not sweep bucket size, concurrency cap, kill-switch threshold, or "
                "ADV floor on the frozen windows to manufacture a pass."
            ),
            "new_evidence_required": (
                "Genuine forward closed rows under the unified universe plus "
                "replay-vs-forward parity; then live pilot sizing is an operator "
                "config decision behind the kill switch."
            ),
        },
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            "quant/accepted_helper_source_priority_allocator_paper_sleeve.py",
            "quant/test_allocator_execution_envelope.py",
        ],
        "anti_js": "No JavaScript was used.",
    }


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Core EV | +Sleeve EV | +Envelope EV | Kept/All | Skips | KS max DD |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["windows"]:
        audit = row["envelope_audit"]
        rows.append(
            "| {label} | {core:.4f} | {before:.4f} | {after:.4f} | {kept}/{total} | {skips} | {dd:.2%} |".format(
                label=row["label"],
                core=row["core_metrics"]["expected_value_score"],
                before=row["before_metrics"]["expected_value_score"],
                after=row["after_metrics"]["expected_value_score"],
                kept=row["kept_trade_count"],
                total=row["unconstrained_trade_count"],
                skips=audit["skipped_trade_count"],
                dd=float(audit["final_kill_switch_state"]["max_realized_drawdown_pct_of_bucket"] or 0),
            )
        )
    gate = payload["gate4"]
    parts = [
        "# " + EXPERIMENT_ID + " Allocator Activation Envelope Gate",
        "",
        "Status: " + str(payload["status"]) + " / " + str(payload["decision"]),
        "",
        payload["parity_gap_repaired"],
        "",
    ]
    parts.extend(rows)
    parts.extend([
        "",
        "- EV retention: " + str(gate["ev_retention"]) + " (min " + str(gate["min_ev_retention"]) + ")",
        "- Failed reasons: " + (", ".join(gate["failed_reasons"]) or "none"),
        "",
        "No JavaScript was used.",
    ])
    newline = chr(10)
    return newline.join(parts) + newline


def persist(payload: dict[str, Any]) -> None:
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, payload)
    framework._write_text(CARD_MD, _build_card(payload))
    gate = payload["gate4"]
    log_record = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": bool(gate["passed"]),
        "accepted_alpha": False,
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "gate4": gate,
        "execution_envelope": payload["execution_envelope"],
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }
    framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    result = {
        "decision": payload["decision"],
        "accepted": bool(gate["passed"]),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "gate4": gate,
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "decision": payload["decision"],
        "summary": payload["parity_gap_repaired"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card_file": _repo_rel(CARD_MD),
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


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_payload()
    persist(payload)
    print(json.dumps(framework._safe(payload["gate4"]), indent=2))


if __name__ == "__main__":
    main()
