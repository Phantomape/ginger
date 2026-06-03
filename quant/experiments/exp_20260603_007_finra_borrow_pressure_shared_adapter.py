"""exp-20260603-007: shared FINRA borrow-pressure paper adapter.

This closeout promotes the accepted exp-20260603-006 replay lead into the
shared default-off FINRA/IWM paper adapter. It does not change live/core orders.
The three-window Gate 4 evidence remains the canonical exp-20260603-006
before/after replay; this run records the production/backtest parity boundary
and focused tests for the shared helper.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from quant.finra_iwm_paper_sleeve import (
        BORROW_PRESSURE_ADMISSION_RULE_VERSION,
        COOLDOWN_RULE_VERSION,
        COST_LIQUIDITY_SUPPORT_RULE_VERSION,
        MARKET_CONFIRMATION_RULE_VERSION,
        RULE_VERSION,
        SLEEVE_NAME,
        SOURCE_RULE_VERSION,
    )
except ImportError:  # pragma: no cover - direct script execution
    import sys

    REPO_ROOT_FOR_IMPORT = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(REPO_ROOT_FOR_IMPORT))
    from quant.finra_iwm_paper_sleeve import (
        BORROW_PRESSURE_ADMISSION_RULE_VERSION,
        COOLDOWN_RULE_VERSION,
        COST_LIQUIDITY_SUPPORT_RULE_VERSION,
        MARKET_CONFIRMATION_RULE_VERSION,
        RULE_VERSION,
        SLEEVE_NAME,
        SOURCE_RULE_VERSION,
    )


EXPERIMENT_ID = "exp-20260603-007"
STEM = "finra_borrow_pressure_shared_adapter"
REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260603_007_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
PRIOR_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260603-006"
    / "exp_20260603_006_finra_borrow_pressure_candidate_pool.json"
)
PRIOR_BEFORE = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260603-006"
    / "finra_borrow_pressure_candidate_pool_before_aggregate.json"
)
PRIOR_AFTER = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260603-006"
    / "finra_borrow_pressure_candidate_pool_after_aggregate.json"
)


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _repo_rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _window_table(prior: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    before_metrics = prior.get("before_metrics") or {}
    after_metrics = prior.get("after_metrics") or {}
    deltas = (prior.get("delta_metrics") or {}).get("by_window") or {}
    for label in ("late_strong", "mid_weak", "old_thin"):
        before = before_metrics.get(label) or {}
        after = after_metrics.get(label) or {}
        delta = deltas.get(label) or {}
        rows.append(
            {
                "window": label,
                "before_ev": before.get("expected_value_score"),
                "after_ev": after.get("expected_value_score"),
                "delta_ev": delta.get("expected_value_score"),
                "before_pnl": before.get("total_pnl"),
                "after_pnl": after.get("total_pnl"),
                "delta_pnl": delta.get("total_pnl"),
                "before_survival_rate": before.get("survival_rate"),
                "after_survival_rate": after.get("survival_rate"),
                "target_trades": len(
                    (prior.get("target_trades_by_window") or {}).get(label) or []
                ),
            }
        )
    return rows


def _experiment_log_row(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["three_window_result"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "hypothesis": payload["hypothesis"],
        "change_summary": (
            "Promoted the accepted FINRA borrow-pressure admission into the "
            "shared default-off FINRA/IWM paper adapter."
        ),
        "change_type": payload["change_type"],
        "mechanism_family": "default_off_paper_adapter",
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "prior_trial_count": 1,
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": (
            "promoted_positive_replay_lead_to_shared_production_visible_adapter"
        ),
        "component": "quant/finra_iwm_paper_sleeve.py",
        "parameters": {
            "min_finra_days_to_cover": 3.0,
            "min_finra_short_interest_change_pct": 0.0,
            "borrow_pressure_admission_enabled": True,
            "trade_enabled": False,
        },
        "before_metrics": _load_json(BEFORE_AGG_JSON),
        "after_metrics": _load_json(AFTER_AGG_JSON),
        "delta_metrics": {
            "expected_value_score": aggregate.get("expected_value_score_delta_sum"),
            "total_pnl": aggregate.get("total_pnl_delta_sum"),
            "windows_ev_improved": aggregate.get("windows_ev_improved"),
            "windows_pnl_improved": aggregate.get("windows_pnl_improved"),
            "max_drawdown_delta_max": aggregate.get("max_drawdown_delta_max"),
        },
        "prediction": {
            "success_probability": 0.62,
            "expected_ev_delta": aggregate.get("expected_value_score_delta_sum"),
            "expected_pnl_delta": aggregate.get("total_pnl_delta_sum"),
            "main_failure_modes": [
                "adapter_replay_mismatch",
                "production_metadata_gap",
                "unit_parity_failure",
            ],
            "confidence_reason": (
                "exp-20260603-006 already passed the canonical three-window "
                "replay; this run tests shared adapter parity."
            ),
            "recorded_at": "2026-06-03T06:05:50+00:00",
        },
        "calibration": {
            "actual_decision": payload["decision"],
            "actual_success": 1,
            "predicted_success_probability": 0.62,
            "brier_score": round((0.62 - 1) ** 2, 6),
            "realized_failure_mode": "none",
            "predicted_failure_mode_hit": False,
        },
        "production_impact": payload["production_impact"],
        "decision": payload["decision"],
        "rejection_reason": None,
        "next_retry_requires": [
            "closed forward replacement-value rows",
            "activation experiment before live/default orders",
        ],
        "related_files": payload["related_files"],
        "notes": payload["acceptance_basis"],
    }


def _append_experiment_log_once(row: dict[str, Any]) -> None:
    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    needle = f'"experiment_id": "{EXPERIMENT_ID}"'
    if EXPERIMENT_LOG.exists():
        with EXPERIMENT_LOG.open("r", encoding="utf-8") as handle:
            for line in handle:
                if needle in line:
                    return
    with EXPERIMENT_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def build_payload() -> dict[str, Any]:
    prior = _load_json(PRIOR_JSON)
    aggregate = (prior.get("delta_metrics") or {}).get("aggregate") or {}
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": "accepted_default_off_finra_borrow_pressure_shared_adapter",
        "decision": "accepted_default_off_finra_borrow_pressure_shared_adapter",
        "hypothesis": (
            "The accepted FINRA borrow-pressure admission lead should become a "
            "shared default-off FINRA/IWM paper adapter so production can collect "
            "forward replacement-value evidence without changing live orders."
        ),
        "change_type": "default_off_paper_adapter",
        "changed_variable": "finra_borrow_pressure_admission_shared_adapter_v1",
        "single_causal_variable": "shared FINRA borrow-pressure admission adapter boundary",
        "trial_family": "default_off_paper_adapter",
        "trial_variant_id": "finra_borrow_pressure_admission_shared_adapter_v1",
        "nearby_prior_experiments": [
            "exp-20260603-006",
            "exp-20260530-010",
            "exp-20260601-029",
            "exp-20260529-018",
        ],
        "gate_questions": {
            "1_alpha_hypothesis": (
                "candidate_pool / entry: require the official FINRA row to show "
                "both high days-to-cover and positive short-interest change before "
                "admitting FINRA/IWM default-off paper candidates."
            ),
            "2_history_check": {
                "exp-20260603-006": (
                    "Accepted replay lead: aggregate EV +0.2585, PnL +$5,688.12, "
                    "3/3 windows improved, 22 target trades, concentration passed."
                ),
                "exp-20260530-010": (
                    "Existing shared FINRA/IWM cooldown adapter; this run changes "
                    "only the FINRA borrow-pressure admission field."
                ),
                "exp-20260601-029": (
                    "Cost-liquidity support is already accepted; this run does not "
                    "retune notional, liquidity, cooldown, IWM, ranking, or exits."
                ),
                "exp-20260529-018": (
                    "FINRA score monotonicity failed, so this run does not rely on "
                    "another composite-score threshold sweep."
                ),
            },
            "3_single_causal_variable": "finra_borrow_pressure_admission_shared_adapter_v1",
            "4_acceptance_standard": (
                "Use docs/backtesting.md three windows from exp-20260603-006 for "
                "paper alpha evidence; adapter acceptance additionally requires "
                "shared production-visible code, no live/core order impact, and "
                "focused parity/metadata tests."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260603_007_finra_borrow_pressure_shared_adapter.py"
            ),
        },
        "three_window_evidence_source": _repo_rel(PRIOR_JSON),
        "three_window_result": {
            "windows": _window_table(prior),
            "aggregate": aggregate,
            "gate4": prior.get("gate4"),
            "target_trade_summary": prior.get("target_trade_summary"),
        },
        "adapter_validation": {
            "sleeve": SLEEVE_NAME,
            "rule_version": RULE_VERSION,
            "source_rule_version": SOURCE_RULE_VERSION,
            "borrow_pressure_admission_rule_version": (
                BORROW_PRESSURE_ADMISSION_RULE_VERSION
            ),
            "market_confirmation_rule_version": MARKET_CONFIRMATION_RULE_VERSION,
            "same_ticker_cooldown_rule_version": COOLDOWN_RULE_VERSION,
            "cost_liquidity_support_rule_version": COST_LIQUIDITY_SUPPORT_RULE_VERSION,
            "shared_files": [
                "quant/finra_iwm_paper_sleeve.py",
                "quant/run.py",
                "quant/default_off_alpha_attribution.py",
                "quant/report_generator.py",
                "quant/test_finra_iwm_paper_sleeve.py",
            ],
            "focused_tests": [
                "py_compile finra_iwm/run/report/default_off modules",
                "pytest quant/test_finra_iwm_paper_sleeve.py -q",
            ],
        },
        "production_impact": {
            "shared_policy_changed": True,
            "run_adapter_changed": True,
            "backtester_adapter_changed": False,
            "replay_only": False,
            "default_off_paper_only": True,
            "production_orders_changed": False,
            "production_watchlist_changed": False,
            "trade_enabled": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "parity_test_added": True,
        },
        "acceptance_basis": (
            "Accepted as a default-off production-visible adapter, not as live "
            "capital. It preserves the accepted exp-20260603-006 three-window "
            "paper lead and starts forward evidence collection without changing "
            "core/live behavior."
        ),
        "next_evidence_needed": (
            "Closed forward replacement-value rows, cash/core displacement "
            "comparison, concentration and kill-gate monitoring before any live "
            "activation review."
        ),
        "related_files": [
            "quant/finra_iwm_paper_sleeve.py",
            "quant/test_finra_iwm_paper_sleeve.py",
            "quant/default_off_alpha_attribution.py",
            "quant/report_generator.py",
            "docs/current_state.md",
            "docs/alpha-optimization-playbook.md",
            "docs/data_edge_context_layers.md",
            "docs/production_backtest_parity.md",
            _repo_rel(OUT_JSON),
            _repo_rel(BEFORE_AGG_JSON),
            _repo_rel(AFTER_AGG_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(PRIOR_JSON),
        ],
    }


def build_artifact(payload: dict[str, Any]) -> str:
    lines = [
        "# exp-20260603-007 FINRA Borrow-Pressure Shared Adapter",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        (
            "Single variable: move the accepted FINRA borrow-pressure admission "
            "field into the shared default-off FINRA/IWM paper adapter."
        ),
        "",
        "## Three-Window Evidence",
        "",
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Target trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["three_window_result"]["windows"]:
        lines.append(
            "| {window} | {before_ev:.4f} | {after_ev:.4f} | {delta_ev:+.4f} | "
            "${before_pnl:,.2f} | ${after_pnl:,.2f} | ${delta_pnl:+,.2f} | "
            "{target_trades} |".format(**row)
        )
    aggregate = payload["three_window_result"]["aggregate"]
    gate4 = payload["three_window_result"]["gate4"] or {}
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            f"- EV delta: `{aggregate.get('expected_value_score_delta_sum')}` (`{aggregate.get('expected_value_score_delta_pct')}`)",
            f"- PnL delta: `${aggregate.get('total_pnl_delta_sum')}` (`{aggregate.get('total_pnl_delta_pct')}`)",
            f"- Gate 4 passed: `{gate4.get('passed')}`; target trades `{gate4.get('target_trade_count')}`; EV-regressed windows `{gate4.get('windows_ev_regressed')}`.",
            "",
            "## Production Parity",
            "",
            (
                "The adapter is shared production code and remains default-off "
                "paper only. `trade_enabled=false`; it does not change core "
                "signals, rankings, sizing, exits, watchlists, LLM/news, or orders."
            ),
            "",
            "No JavaScript was used.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    prior_before = _load_json(PRIOR_BEFORE)
    prior_after = _load_json(PRIOR_AFTER)
    _write_json(BEFORE_AGG_JSON, prior_before)
    _write_json(AFTER_AGG_JSON, prior_after)
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(build_artifact(payload), encoding="utf-8")
    _append_experiment_log_once(_experiment_log_row(payload))
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "artifact": _repo_rel(OUT_JSON),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
