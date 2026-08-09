"""exp-20260711-015: MOVE relief rate-sensitive-sector priority ranking.

The only decision change is ranking qualified MOVE-relief candidates from
Technology, Communication Services, Consumer Cyclical, and Real Estate ahead
of other qualified candidates.  The MOVE trigger, eligibility rules, top-2
budget, execution, costs, notional, and cooldown remain frozen from
exp-20260711-004.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import importlib
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
for entry in (REPO_ROOT, REPO_ROOT / "scripts", REPO_ROOT / "quant", REPO_ROOT / "quant" / "experiments"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import exp_20260711_004_move_rate_volatility_relief_shared_paper as champion  # noqa: E402
from experiment_registry import persist_self_registered_result, save_experiment_log_entry  # noqa: E402


EXPERIMENT_ID = "exp-20260711-015"
OWNER = "alpha-explore"
SLUG = "move_rate_volatility_relief_duration_priority"
RUNNER = f"quant/experiments/exp_20260711_015_{SLUG}.py"
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"exp_20260711_015_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
CHAMPION_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260711-004"
    / "exp_20260711_004_move_rate_volatility_relief_shared_paper.json"
)
SHARED_MODULE = REPO_ROOT / "quant" / "move_rate_volatility_relief_duration_priority_paper_sleeve.py"

HYPOTHESIS = (
    "ranking/full_stack: within the accepted MOVE rate-volatility relief shared paper source, "
    "prioritize economically rate-sensitive long-duration sectors (Technology, Communication "
    "Services, Consumer Cyclical, Real Estate) ahead of other qualified leaders while preserving "
    "the frozen selector, top-2 budget, next-open entry, 10-session exit, costs, cooldown, and "
    "notional; the challenger must beat the accepted MOVE v1 helper without any window regression."
)
CHANGED_VARIABLE = "move_relief_rate_sensitive_sector_priority_ranking_v1"
SOURCE_RULE_VERSION = CHANGED_VARIABLE
RULE_VERSION = "move_rate_volatility_relief_duration_priority_shared_default_off_adapter_v1"
RATE_SENSITIVE_SECTORS = frozenset(
    {"Technology", "Communication Services", "Consumer Cyclical", "Real Estate"}
)
NEW_AXIS = (
    "New gate shape: deterministic rate-sensitive-sector priority ranking inside the accepted MOVE "
    "shared paper candidate source, with the MOVE trigger and all eligibility/execution variables "
    "locked; prior MOVE experiments tested source admission, shared promotion, core overlap, and "
    "exit continuation, not candidate ranking."
)
NEARBY = [
    "exp-20260711-002",
    "exp-20260711-004",
    "exp-20260711-008",
    "exp-20260711-011",
    "exp-20260711-013",
]
TICKET = json.loads(TICKET_JSON.read_text(encoding="utf-8"))
PREDICTION = TICKET["prediction"]
ALLOWED_WRITE_SCOPE = TICKET["allowed_write_scope"]
ACTUAL_REJECTED_FILES = [
    RUNNER,
    "data/experiments/exp-20260711-015/exp_20260711_015_move_rate_volatility_relief_duration_priority.json",
    "experiments/tickets/exp-20260711-015.json",
    "experiments/cards/exp-20260711-015.md",
    "experiments/manifests/exp-20260711-015.json",
    "experiments/logs/exp-20260711-015.json",
    "docs/experiment_registry.json",
]

MIN_CHAMPION_EV_IMPROVEMENT = 0.03344
MIN_CHAMPION_PNL_IMPROVEMENT = 754.89
MAX_DRAWDOWN_WORSE = 0.005
MIN_TARGET_TRADES = 20


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _priority_candidate(**kwargs: Any) -> dict[str, Any] | None:
    if SHARED_MODULE.exists():
        shared = importlib.import_module("move_rate_volatility_relief_duration_priority_paper_sleeve")
        return shared.move_rate_volatility_relief_duration_priority_candidate_for_ticker(**kwargs)
    row = champion.replay_candidate(**kwargs)
    if row is None:
        return None
    base_score = float(row["candidate_score"])
    sector = str(row.get("sector") or "")
    priority = 0 if sector in RATE_SENSITIVE_SECTORS else 1
    row.update(
        {
            "source": "MOVE_RATE_VOLATILITY_RELIEF_DURATION_PRIORITY_PAPER",
            "rule_version": SOURCE_RULE_VERSION,
            "source_rule_version": SOURCE_RULE_VERSION,
            "candidate_score_base": round(base_score, 6),
            "candidate_rate_sensitive_sector": priority == 0,
            "candidate_duration_priority_bucket": priority,
            # The inherited framework sorts descending candidate_score.  A fixed
            # offset implements lexicographic sector priority without changing
            # any eligibility threshold or within-bucket score ordering.
            "candidate_score": round(base_score + (1000.0 if priority == 0 else 0.0), 6),
        }
    )
    return row


def configure_framework() -> None:
    champion.configure_scout_framework()
    scout = champion.scout
    scout.EXPERIMENT_ID = EXPERIMENT_ID
    scout.SLUG = SLUG
    scout.RUNNER = RUNNER
    scout.RUNNER_PS = RUNNER.replace("/", "\\")
    scout.RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + scout.RUNNER_PS
    scout.OUT_DIR = OUT_JSON.parent
    scout.OUT_JSON = OUT_JSON
    scout.LOG_JSON = LOG_JSON
    scout.CARD_MD = CARD_MD
    scout.MANIFEST_JSON = MANIFEST_JSON
    scout.TICKET_JSON = TICKET_JSON
    scout.REGISTRY_JSON = REGISTRY_JSON
    scout.HYPOTHESIS = HYPOTHESIS
    scout.CHANGE_TYPE = "ranking_full_stack"
    scout.IMPLEMENTATION_MODE = "shared_paper_first_conditional_on_champion_gate"
    scout.MECHANISM_FAMILY = "production_visible_rate_volatility_relief_candidate_pool"
    scout.TRIAL_FAMILY = "move_rate_volatility_relief_sector_priority_ranking"
    scout.TRIAL_VARIANT_ID = SOURCE_RULE_VERSION
    scout.CHANGED_VARIABLE = CHANGED_VARIABLE
    scout.NEW_EVIDENCE_TYPE = "new_gate_shape_ranking"
    scout.NEW_EVIDENCE_AXIS = NEW_AXIS
    scout.NEARBY_PRIORS = NEARBY
    scout.CAUSAL_COMPONENTS = list(TICKET["causal_components"])
    scout.PREDICTION = PREDICTION
    scout.PRODUCTION_IMPACT = production_impact(shared_retained=SHARED_MODULE.exists())
    scout.ALLOWED_WRITE_SCOPE = ALLOWED_WRITE_SCOPE
    scout.move_relief_context = champion.replay_context
    scout.candidate_for_ticker = _priority_candidate


def production_impact(*, shared_retained: bool) -> dict[str, Any]:
    return {
        "shared_policy_changed": shared_retained,
        "backtester_adapter_changed": shared_retained,
        "run_adapter_changed": shared_retained,
        "replay_only": not shared_retained,
        "trade_enabled": False,
        "entry_rules_changed": False,
        "ranking_changed": shared_retained,
        "sizing_changed": False,
        "exit_rules_changed": False,
        "orders_changed": False,
        "llm_decision_boundary_changed": False,
        "scope": "default_off_move_rate_volatility_relief_duration_priority_paper",
    }


def _sum_metrics(metrics: dict[str, Any]) -> dict[str, float]:
    return {
        "expected_value_score": round(
            sum(float(row["expected_value_score"]) for row in metrics.values()), 4
        ),
        "total_pnl": round(sum(float(row["total_pnl"]) for row in metrics.values()), 2),
        "max_drawdown_pct": max(float(row["max_drawdown_pct"]) for row in metrics.values()),
    }


def _champion_gate(payload: dict[str, Any]) -> dict[str, Any]:
    champion_payload = json.loads(CHAMPION_JSON.read_text(encoding="utf-8"))
    current = champion_payload["after_metrics"]
    challenger = payload["after_metrics"]
    current_aggregate = _sum_metrics(current)
    challenger_aggregate = _sum_metrics(challenger)
    by_window: dict[str, Any] = {}
    for label in ("late_strong", "mid_weak", "old_thin"):
        ev_delta = round(
            float(challenger[label]["expected_value_score"])
            - float(current[label]["expected_value_score"]),
            4,
        )
        pnl_delta = round(
            float(challenger[label]["total_pnl"]) - float(current[label]["total_pnl"]), 2
        )
        by_window[label] = {
            "champion_ev": current[label]["expected_value_score"],
            "challenger_ev": challenger[label]["expected_value_score"],
            "ev_delta": ev_delta,
            "champion_pnl": current[label]["total_pnl"],
            "challenger_pnl": challenger[label]["total_pnl"],
            "pnl_delta": pnl_delta,
            "passed": ev_delta >= 0.0 and pnl_delta >= 0.0,
        }
    aggregate_ev_delta = round(
        challenger_aggregate["expected_value_score"] - current_aggregate["expected_value_score"], 4
    )
    aggregate_pnl_delta = round(
        challenger_aggregate["total_pnl"] - current_aggregate["total_pnl"], 2
    )
    drawdown_worse = round(
        challenger_aggregate["max_drawdown_pct"] - current_aggregate["max_drawdown_pct"], 6
    )
    target_count = int(payload["target_trade_summary"]["total_trade_count"])
    target_windows = len(payload["target_trade_summary"]["windows_with_target_trades"])
    concentration_passed = bool(payload["gate4"]["target_concentration"]["passed"])
    reasons: list[str] = []
    if not bool(payload["gate1"]["passed"]):
        reasons.append("gate1_identity_failed")
    if not bool(payload["gate2"]["passed"]):
        reasons.append("gate2_contract_failed")
    if not bool(payload["gate3"]["passed"]):
        reasons.append("gate3_survival_failed")
    if target_count < MIN_TARGET_TRADES:
        reasons.append("target_trade_count_too_small")
    if target_windows < 3:
        reasons.append("target_window_coverage_too_small")
    if any(not row["passed"] for row in by_window.values()):
        reasons.append("accepted_move_v1_window_regression")
    if aggregate_ev_delta < MIN_CHAMPION_EV_IMPROVEMENT:
        reasons.append("accepted_move_v1_material_ev_not_beaten")
    if aggregate_pnl_delta < MIN_CHAMPION_PNL_IMPROVEMENT:
        reasons.append("accepted_move_v1_material_pnl_not_beaten")
    if drawdown_worse > MAX_DRAWDOWN_WORSE:
        reasons.append("drawdown_guard_failed")
    if not concentration_passed:
        reasons.append("concentration_failed")
    return {
        "passed": not reasons,
        "decision": "accepted_move_duration_priority_ranking" if not reasons else "rejected_move_duration_priority_ranking",
        "failed_reasons": reasons,
        "champion_experiment_id": "exp-20260711-004",
        "by_window": by_window,
        "champion_aggregate": current_aggregate,
        "challenger_aggregate": challenger_aggregate,
        "aggregate_ev_delta_vs_champion": aggregate_ev_delta,
        "aggregate_pnl_delta_vs_champion": aggregate_pnl_delta,
        "minimum_ev_improvement": MIN_CHAMPION_EV_IMPROVEMENT,
        "minimum_pnl_improvement": MIN_CHAMPION_PNL_IMPROVEMENT,
        "drawdown_worse_vs_champion": drawdown_worse,
        "max_drawdown_worse": MAX_DRAWDOWN_WORSE,
        "target_trade_count": target_count,
        "target_window_count": target_windows,
        "concentration_passed": concentration_passed,
    }


def _shared_parity() -> dict[str, Any]:
    if not SHARED_MODULE.exists():
        return {
            "passed": False,
            "status": "conditional_shared_helper_not_retained_before_market_gate",
            "module": repo_rel(SHARED_MODULE),
        }
    shared = importlib.import_module("move_rate_volatility_relief_duration_priority_paper_sleeve")
    passed = (
        shared.SOURCE_RULE_VERSION == SOURCE_RULE_VERSION
        and shared.RULE_VERSION == RULE_VERSION
        and frozenset(shared.RATE_SENSITIVE_SECTORS) == RATE_SENSITIVE_SECTORS
    )
    return {
        "passed": passed,
        "status": "shared_historical_daily_rule_identity" if passed else "shared_rule_identity_failed",
        "module": repo_rel(SHARED_MODULE),
        "source_rule_version": getattr(shared, "SOURCE_RULE_VERSION", None),
        "rule_version": getattr(shared, "RULE_VERSION", None),
        "focused_test": "quant/test_move_rate_volatility_relief_duration_priority_paper_sleeve.py",
    }


def build_payload() -> dict[str, Any]:
    configure_framework()
    payload = champion.scout.build_payload()
    market_gate = _champion_gate(payload)
    parity = _shared_parity()
    accepted = bool(market_gate["passed"] and parity["passed"])
    if market_gate["passed"] and not parity["passed"]:
        decision = "market_gate_passed_shared_paper_pending"
        status = "running"
    elif accepted:
        decision = "accepted_move_duration_priority_shared_paper"
        status = "accepted"
    else:
        decision = "rejected_move_duration_priority_ranking"
        status = "rejected"
    changed_trade_count = sum(
        1
        for label, row in market_gate["by_window"].items()
        if row["ev_delta"] != 0.0 or row["pnl_delta"] != 0.0
    )
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "lane": "alpha_search",
            "change_type": "ranking_full_stack",
            "implementation_mode": "shared_paper_first_conditional_on_champion_gate",
            "mechanism_family": "production_visible_rate_volatility_relief_candidate_pool",
            "trial_family": "move_rate_volatility_relief_sector_priority_ranking",
            "trial_variant_id": SOURCE_RULE_VERSION,
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "causal_components": list(TICKET["causal_components"]),
            "nearby_prior_experiments": NEARBY,
            "new_evidence_type": "new_gate_shape_ranking",
            "new_evidence_axis": NEW_AXIS,
            "prediction": PREDICTION,
            "accepted": accepted,
            "accepted_alpha": accepted,
            "status": status,
            "decision": decision,
            "champion_gate": market_gate,
            "shared_parity": parity,
            "production_impact": production_impact(shared_retained=accepted),
            "policy_bundle": {
                "priority_sectors": sorted(RATE_SENSITIVE_SECTORS),
                "priority_shape": "lexicographic sector bucket then unchanged candidate score",
                "locked_variables": TICKET["locked_variables"],
            },
            "changed_window_count_vs_champion": changed_trade_count,
            "post_run_reflection": {
                "why_result_happened": (
                    "The predeclared duration-sensitive sector priority materially beat the accepted MOVE v1 helper without window regression."
                    if accepted
                    else "The duration-sensitive sector priority did not materially and consistently beat the accepted MOVE v1 helper."
                ),
                "forbidden_near_neighbor_retry": (
                    "Do not retry MOVE sector lists, sector tiers, score bonuses, thresholds, top-N, hold, cooldown, notional, or response functions on the same canonical rows."
                ),
                "new_evidence_required": (
                    "A retry requires at least 30 closed prospective MOVE rows with sector-aware replacement value, a genuinely new issuer-duration field, or a different ranking gate justified before observing outcomes."
                ),
            },
            "changed_files": list(ALLOWED_WRITE_SCOPE if accepted else ACTUAL_REJECTED_FILES),
            "reproduction_commands": [
                ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260711_015_move_rate_volatility_relief_duration_priority.py",
                ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
            ]
            + (
                [".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_move_rate_volatility_relief_duration_priority_paper_sleeve.py -q"]
                if accepted
                else []
            ),
        }
    )
    probability = float(PREDICTION["success_probability"])
    payload["calibration"] = {
        "predicted_success_probability": probability,
        "actual_success": accepted,
        "brier_score": round((probability - float(accepted)) ** 2, 6),
        "predicted_failure_modes": PREDICTION["main_failure_modes"],
        "predicted_failure_modes_hit": market_gate["failed_reasons"],
    }
    return payload


def persist(payload: dict[str, Any]) -> None:
    if payload["status"] == "running":
        raise RuntimeError("market gate passed; implement and verify the shared daily helper before closeout")
    write_json(OUT_JSON, payload)
    log = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "hypothesis": HYPOTHESIS,
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": payload["causal_components"],
        "nearby_prior_experiments": NEARBY,
        "new_evidence_type": payload["new_evidence_type"],
        "new_evidence_axis": NEW_AXIS,
        "artifact": repo_rel(OUT_JSON),
        "champion_gate": payload["champion_gate"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "changed_files": payload["changed_files"],
        "reproduction_commands": payload["reproduction_commands"],
        "lean_quality_passed": True,
    }
    save_experiment_log_entry(log, allow_duplicate=True)
    gate = payload["champion_gate"]
    write_text(
        CARD_MD,
        "\n".join(
            [
                f"# {EXPERIMENT_ID} MOVE Duration-Priority Ranking",
                "",
                f"Status: `{payload['status']}`",
                f"Decision: `{payload['decision']}`",
                "",
                "## Result",
                "",
                f"- EV delta versus accepted MOVE v1: `{gate['aggregate_ev_delta_vs_champion']:+.4f}`",
                f"- PnL delta versus accepted MOVE v1: `${gate['aggregate_pnl_delta_vs_champion']:+,.2f}`",
                f"- Target trades: `{gate['target_trade_count']}` across `{gate['target_window_count']}` windows",
                f"- Failed gates: `{gate['failed_reasons']}`",
                "- Production orders/core behavior: unchanged; `trade_enabled=false`.",
                "",
                "## Reflection",
                "",
                payload["post_run_reflection"]["why_result_happened"],
                "",
                payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
                "",
            ]
        ),
    )
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": utc_now(),
        "runner": RUNNER,
        "files": [
            {"path": repo_rel(path), "sha256": sha256(path)}
            for path in (OUT_JSON, LOG_JSON, CARD_MD, TICKET_JSON)
            if path.exists()
        ],
    }
    write_json(MANIFEST_JSON, manifest)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": payload["accepted_alpha"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "champion_gate": payload["champion_gate"],
            "calibration": payload["calibration"],
        },
        status=payload["status"],
        fields={**log, "owner": OWNER, "allowed_write_scope": ALLOWED_WRITE_SCOPE},
    )
    write_json(MANIFEST_JSON, manifest)


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "champion_gate": payload["champion_gate"],
                "shared_parity": payload["shared_parity"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
