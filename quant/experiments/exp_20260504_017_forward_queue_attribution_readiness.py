"""Audit forward event-queue replacement-value attribution readiness.

This measurement repair does not alter strategy behavior. It checks whether
the current default-off event queues expose enough frozen counterfactual and
paper-state structure to support future forward replacement-value tests.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
OUT_DIR = DATA_DIR / "experiments" / "exp-20260504-017"
OUT_JSON = OUT_DIR / "exp_20260504_017_forward_queue_attribution_readiness.json"

if str(REPO_ROOT / "quant") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "quant"))

from form4_event_queue import build_forward_queue_from_transactions  # noqa: E402
from sec_event_queue import build_forward_queue_from_sec_filing_text  # noqa: E402


EXPERIMENT_ID = "exp-20260504-017"
AS_OF = "2026-05-04"
BASELINE_RESULT_FILE = "data/backtest_results_20260503.json"
BASELINE_METRICS = {
    "late_strong": {
        "expected_value_score": 3.4191,
        "sharpe_daily": 4.35,
        "total_pnl": 78600.33,
        "total_return_pct": 0.786,
        "max_drawdown_pct": 0.0541,
        "win_rate": 0.7895,
        "trade_count": 19,
        "survival_rate": 0.8039,
    },
    "mid_weak": {
        "expected_value_score": 1.4415,
        "sharpe_daily": 2.62,
        "total_pnl": 55015.08,
        "total_return_pct": 0.5502,
        "max_drawdown_pct": 0.0879,
        "win_rate": 0.5238,
        "trade_count": 21,
        "survival_rate": 0.7925,
    },
    "old_thin": {
        "expected_value_score": 0.3179,
        "sharpe_daily": 1.29,
        "total_pnl": 24642.07,
        "total_return_pct": 0.2464,
        "max_drawdown_pct": 0.0805,
        "win_rate": 0.4091,
        "trade_count": 22,
        "survival_rate": 0.9167,
    },
}


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(value).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _counterfactual_contract(candidate: dict[str, Any]) -> dict[str, Any]:
    counterfactual = candidate.get("counterfactual") or {}
    alternatives = counterfactual.get("alternatives") or []
    types = {alt.get("type") for alt in alternatives if isinstance(alt, dict)}
    return {
        "frozen": counterfactual.get("frozen") is True,
        "has_primary_horizon": isinstance(counterfactual.get("primary_horizon_trading_days"), int),
        "alternative_count": len(alternatives),
        "has_cash_alternative": "cash" in types,
        "has_core_signal_alternative": "core_signal" in types,
    }


def _queue_contract(queue: dict[str, Any]) -> dict[str, Any]:
    candidates = queue.get("candidates") or []
    contracts = [_counterfactual_contract(row) for row in candidates]
    candidate_count = len(candidates)
    if candidate_count:
        frozen_ok = all(row["frozen"] for row in contracts)
        horizon_ok = all(row["has_primary_horizon"] for row in contracts)
        cash_ok = all(row["has_cash_alternative"] for row in contracts)
    else:
        frozen_ok = horizon_ok = cash_ok = None
    impact = queue.get("production_impact") or {}
    return {
        "queue_name": queue.get("queue_name"),
        "rule_version": queue.get("rule_version"),
        "enabled": queue.get("enabled"),
        "candidate_count": candidate_count,
        "data_source": queue.get("data_source"),
        "production_impact": impact,
        "counterfactual_contract": {
            "evaluated_candidate_count": candidate_count,
            "all_candidates_frozen": frozen_ok,
            "all_candidates_have_primary_horizon": horizon_ok,
            "all_candidates_have_cash_alternative": cash_ok,
            "candidate_examples": contracts[:3],
        },
        "observe_only_guardrail_passed": (
            queue.get("enabled") is False
            and impact.get("alters_signal_generation") is False
            and impact.get("alters_candidate_ranking") is False
            and impact.get("alters_sizing") is False
            and impact.get("alters_orders") is False
        ),
    }


def _paper_state_contract(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
    required_lists = ("pending_entries", "open_positions", "closed_positions", "skipped_entries")
    missing = [key for key in required_lists if not isinstance(payload.get(key), list)]
    return {
        "path": _repo_rel(path),
        "exists": path.exists(),
        "schema_version": payload.get("schema_version"),
        "sleeve": payload.get("sleeve"),
        "updated_at": payload.get("updated_at"),
        "pending_count": len(payload.get("pending_entries") or []),
        "open_count": len(payload.get("open_positions") or []),
        "closed_count": len(payload.get("closed_positions") or []),
        "skipped_count": len(payload.get("skipped_entries") or []),
        "required_lists_present": not missing,
        "missing_lists": missing,
    }


def build_payload() -> dict[str, Any]:
    sample_core_signals = [
        {
            "ticker": "SPY",
            "strategy": "trend_long",
            "confidence_score": 0.90,
            "trade_quality_score": 0.75,
            "risk_reward_ratio": 2.0,
        }
    ]
    form4_queue = build_forward_queue_from_transactions(
        data_dir=DATA_DIR / "non_ohlcv",
        as_of=AS_OF,
        core_signals=sample_core_signals,
    )
    sec_queue = build_forward_queue_from_sec_filing_text(
        data_dir=DATA_DIR / "non_ohlcv",
        as_of=AS_OF,
        ohlcv_by_ticker={},
        spy_ohlcv=[],
        core_signals=sample_core_signals,
    )
    form4_policy = _load_json(DATA_DIR / "experiments" / "exp-20260504-001" / "form4_forward_event_queue.json")
    form4_harness = _load_json(DATA_DIR / "experiments" / "exp-20260504-013" / "form4_event_sleeve_harness.json")
    sec_policy = _load_json(DATA_DIR / "experiments" / "exp-20260504-012" / "sec_forward_queue_policy.json")
    form4_state = _paper_state_contract(DATA_DIR / "form4_event_sleeve_paper_state.json")

    queue_contracts = {
        "form4_forward_queue": _queue_contract(form4_queue),
        "sec_negative_reaction_forward_queue": _queue_contract(sec_queue),
    }
    form4_ready = (
        queue_contracts["form4_forward_queue"]["observe_only_guardrail_passed"]
        and form4_state["exists"]
        and form4_state["required_lists_present"]
    )
    sec_ready = (
        queue_contracts["sec_negative_reaction_forward_queue"]["observe_only_guardrail_passed"]
        and False
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "lane": "measurement_repair",
        "status": "observed_only",
        "decision": "observed_only",
        "hypothesis": (
            "Default-off event queues can only release SEC/Form4 event-sleeve alpha if their forward artifacts "
            "freeze same-day alternatives and outcome fields needed for replacement-value attribution."
        ),
        "alpha_hypothesis_released": {
            "category": "event_source_forward_replacement_value",
            "text": (
                "Large Form 4 purchase and SEC negative-reaction/leadership-change event queues may be promoted only "
                "after forward paper/replacement outcomes show they beat frozen same-day A/B alternatives."
            ),
            "current_release": (
                "Form 4 paper attribution can continue accumulating forward evidence; SEC queues still need a "
                "persistent paper/outcome ledger before promotion testing."
            ),
        },
        "change_type": "measurement_instrumentation",
        "single_causal_variable": "forward queue replacement attribution readiness",
        "baseline_result_file": BASELINE_RESULT_FILE,
        "before_metrics": BASELINE_METRICS,
        "after_metrics": BASELINE_METRICS,
        "expected_value_score_delta": 0.0,
        "historical_constraints": {
            "form4": [
                "Do not repeat simple Form 4 owner-role/value threshold sweeps.",
                "Do not promote Form 4 into core slots until forward replacement value is positive.",
            ],
            "sec": [
                "Do not repeat keyword phrase tuning, nearby reaction-threshold sweeps, or direct core-slot promotion.",
                "SEC negative-reaction replacement value was historically inconclusive; use forward queue samples next.",
            ],
        },
        "readiness_checks": {
            "as_of": AS_OF,
            "queue_contracts": queue_contracts,
            "paper_state_contracts": {
                "form4_event_sleeve_paper_state": form4_state,
                "sec_event_sleeve_paper_state": {
                    "exists": False,
                    "required_for_forward_replacement_attribution": True,
                    "gap": "No persistent SEC event-sleeve paper/outcome state was found.",
                },
            },
            "prior_artifacts": {
                "form4_queue_policy_decision": form4_policy.get("decision"),
                "form4_harness_decision": form4_harness.get("decision"),
                "sec_queue_policy_decision": sec_policy.get("decision"),
                "form4_current_queue_candidate_count": queue_contracts["form4_forward_queue"]["candidate_count"],
                "sec_current_queue_candidate_count": queue_contracts["sec_negative_reaction_forward_queue"]["candidate_count"],
            },
        },
        "readiness_summary": {
            "form4_forward_attribution_ready": bool(form4_ready),
            "sec_forward_attribution_ready": bool(sec_ready),
            "blocking_gap": (
                "SEC event queues have default-off queue contracts, but no persistent paper/outcome ledger analogous "
                "to data/form4_event_sleeve_paper_state.json."
            ),
            "next_valid_measurement_repair": (
                "Add a default-off SEC event paper/outcome ledger before any LLM/event-sleeve promotion test."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "production_signal_path_changed": False,
            "production_impact": "read_only_audit_artifact_no_orders_changed",
        },
        "gate4": {
            "applicable": False,
            "core_strategy_changed": False,
            "reason": "Read-only measurement audit; no entries, ranking, sizing, exits, or orders changed.",
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "relation": "Releases future LLM/event grading only after forward queue outcomes are measurable.",
        },
        "related_files": [
            _repo_rel(Path("quant/experiments/exp_20260504_017_forward_queue_attribution_readiness.py")),
            _repo_rel(OUT_JSON),
            _repo_rel(Path("data/form4_event_sleeve_paper_state.json")),
            _repo_rel(Path("data/experiments/exp-20260504-001/form4_forward_event_queue.json")),
            _repo_rel(Path("data/experiments/exp-20260504-012/sec_forward_queue_policy.json")),
            _repo_rel(Path("data/experiments/exp-20260504-013/form4_event_sleeve_harness.json")),
        ],
    }


def main() -> int:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "artifact": _repo_rel(OUT_JSON),
                "form4_ready": payload["readiness_summary"]["form4_forward_attribution_ready"],
                "sec_ready": payload["readiness_summary"]["sec_forward_attribution_ready"],
                "blocking_gap": payload["readiness_summary"]["blocking_gap"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
