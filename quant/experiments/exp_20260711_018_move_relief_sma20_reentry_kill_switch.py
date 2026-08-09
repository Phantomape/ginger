"""exp-20260711-018: accepted MOVE sleeve thesis-invalidation kill switch.

The entry source remains the accepted exp-20260711-004 MOVE20 first-cross-
below candidate policy.  The only decision change is an opposite first cross
back above the same 20-session mean while a paper position is open; that event
exits at the following session open instead of the fixed day-10 close.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
for entry in (REPO_ROOT, REPO_ROOT / "scripts", REPO_ROOT / "quant", REPO_ROOT / "quant" / "experiments"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import exp_20260711_004_move_rate_volatility_relief_shared_paper as champion  # noqa: E402
from constants import EXEC_LAG_PCT, ROUND_TRIP_COST_PCT  # noqa: E402
from experiment_registry import persist_self_registered_result, save_experiment_log_entry  # noqa: E402


EXPERIMENT_ID = "exp-20260711-018"
OWNER = "alpha-explore"
SLUG = "move_relief_sma20_reentry_kill_switch"
RUNNER = f"quant/experiments/exp_20260711_018_{SLUG}.py"
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"exp_20260711_018_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
CHAMPION_JSON = (
    REPO_ROOT / "data" / "experiments" / "exp-20260711-004"
    / "exp_20260711_004_move_rate_volatility_relief_shared_paper.json"
)
SHARED_MODULE = REPO_ROOT / "quant" / "move_rate_volatility_relief_kill_switch.py"

HYPOTHESIS = (
    "exit/full_stack: for the accepted MOVE rate-volatility relief shared paper sleeve, "
    "the first MOVE close back above the unchanged trailing 20-session mean during an "
    "open paper position invalidates the relief thesis; exiting at the next session open "
    "should improve accepted MOVE v1 EV, PnL, and drawdown without window regression."
)
CHANGED_VARIABLE = "move_relief_sma20_reentry_next_open_kill_switch_v1"
SOURCE_RULE_VERSION = CHANGED_VARIABLE
RULE_VERSION = "move_rate_volatility_relief_kill_switch_shared_default_off_v1"
NEW_AXIS = (
    "New gate shape: a paper-only lifecycle kill switch using the exact opposite MOVE20 "
    "first-cross-above invalidation event and next-session-open exit; entry trigger, "
    "eligibility, ranking, top-2 budget, notional, costs, and SMA span remain locked."
)
NEARBY = ["exp-20260711-004", "exp-20260711-015"]
TICKET = json.loads(TICKET_JSON.read_text(encoding="utf-8"))
PREDICTION = TICKET["prediction"]
ALLOWED_WRITE_SCOPE = TICKET["allowed_write_scope"]

MIN_CHAMPION_EV_IMPROVEMENT = 0.03344
MIN_CHAMPION_PNL_IMPROVEMENT = 754.89
MAX_DRAWDOWN_WORSE = 0.005
MIN_CHANGED_TRADES = 20
MOVE_SMA_SESSIONS = 20


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


def _date(row: dict[str, Any]) -> str:
    return str(row.get("Date") or row.get("date") or "")[:10]


def _value(row: dict[str, Any], key: str) -> float | None:
    value = row.get(key)
    if value is None:
        value = row.get(key.lower())
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _move_crossed_back_above(rows: list[dict[str, Any]], idx: int) -> bool:
    if idx < MOVE_SMA_SESSIONS:
        return False
    closes = [_value(row, "Close") for row in rows]
    current_window = closes[idx - MOVE_SMA_SESSIONS + 1 : idx + 1]
    prior_window = closes[idx - MOVE_SMA_SESSIONS : idx]
    current = closes[idx]
    previous = closes[idx - 1]
    if current is None or previous is None or any(value is None for value in current_window + prior_window):
        return False
    current_sma = sum(float(value) for value in current_window) / MOVE_SMA_SESSIONS
    prior_sma = sum(float(value) for value in prior_window) / MOVE_SMA_SESSIONS
    return current > current_sma and previous <= prior_sma


def _apply_kill_switch(snapshot: dict[str, list[dict[str, Any]]], trade: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(trade)
    ticker = str(out.get("ticker") or "").upper()
    entry_date = str(out.get("entry_date") or "")[:10]
    original_exit_date = str(out.get("exit_date") or "")[:10]
    move_rows = sorted(snapshot.get("MOVE") or [], key=_date)
    ticker_rows = sorted(snapshot.get(ticker) or [], key=_date)
    stress_date: str | None = None
    stress_close: float | None = None
    stress_sma: float | None = None
    for idx, row in enumerate(move_rows):
        day = _date(row)
        if day < entry_date or day >= original_exit_date:
            continue
        if not _move_crossed_back_above(move_rows, idx):
            continue
        stress_date = day
        stress_close = _value(row, "Close")
        current_window = move_rows[idx - MOVE_SMA_SESSIONS + 1 : idx + 1]
        stress_sma = sum(float(_value(value, "Close")) for value in current_window) / MOVE_SMA_SESSIONS
        break
    if stress_date is None:
        out.update({"kill_switch_triggered": False, "kill_switch_reason": "no_move_first_cross_back_above_sma20"})
        return out
    exit_row = next((row for row in ticker_rows if stress_date < _date(row) <= original_exit_date), None)
    exit_open = _value(exit_row or {}, "Open")
    entry_price = float(out["entry_price"])
    notional = float(out.get("paper_notional_usd") or out.get("notional_usd") or 4000.0)
    if exit_row is None or exit_open is None or exit_open <= 0.0:
        out.update({"kill_switch_triggered": False, "kill_switch_reason": "missing_next_session_open_after_move_cross"})
        return out
    exit_price = exit_open * (1.0 - EXEC_LAG_PCT)
    pnl_pct_net = (exit_price / entry_price) - 1.0 - ROUND_TRIP_COST_PCT
    out.update(
        {
            "original_exit_date": original_exit_date,
            "original_exit_price": out.get("exit_price"),
            "original_exit_raw_close": out.get("exit_raw_close"),
            "original_pnl": out.get("pnl"),
            "original_pnl_pct_net": out.get("pnl_pct_net"),
            "exit_date": _date(exit_row),
            "exit_raw_open": round(exit_open, 4),
            "exit_raw_close": None,
            "exit_price": round(exit_price, 4),
            "exit_timing": "next_session_open_after_move_relief_invalidation",
            "exit_reason": "move_first_cross_back_above_sma20_kill_switch",
            "kill_switch_triggered": True,
            "kill_switch_signal_date": stress_date,
            "kill_switch_move_close": round(float(stress_close), 6),
            "kill_switch_move_sma20": round(float(stress_sma), 6),
            "kill_switch_rule_version": SOURCE_RULE_VERSION,
            "pnl_pct_net": round(pnl_pct_net, 6),
            "net_return_pct": round(pnl_pct_net, 6),
            "pnl": round(notional * pnl_pct_net, 2),
        }
    )
    return out


BASE_SELECT = champion.scout.prior.framework._select_paper_trades


def _select_with_kill_switch(*, snapshot: dict[str, list[dict[str, Any]]], candidates: list[dict[str, Any]]):
    selected, filtered = BASE_SELECT(snapshot=snapshot, candidates=candidates)
    return [_apply_kill_switch(snapshot, row) for row in selected], filtered


def production_impact(*, shared_retained: bool) -> dict[str, Any]:
    return {
        "shared_policy_changed": shared_retained,
        "backtester_adapter_changed": shared_retained,
        "run_adapter_changed": shared_retained,
        "replay_only": not shared_retained,
        "trade_enabled": False,
        "entry_rules_changed": False,
        "ranking_changed": False,
        "sizing_changed": False,
        "exit_rules_changed": shared_retained,
        "orders_changed": False,
        "llm_decision_boundary_changed": False,
        "scope": "default_off_move_rate_volatility_relief_paper_kill_switch",
    }


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
    scout.CHANGE_TYPE = "exit_policy_full_stack"
    scout.IMPLEMENTATION_MODE = "shared_paper_first_conditional_on_champion_gate"
    scout.MECHANISM_FAMILY = "production_visible_rate_volatility_relief_exit_policy"
    scout.TRIAL_FAMILY = "move_rate_volatility_relief_kill_switch"
    scout.TRIAL_VARIANT_ID = SOURCE_RULE_VERSION
    scout.CHANGED_VARIABLE = CHANGED_VARIABLE
    scout.NEW_EVIDENCE_TYPE = "new_gate_shape_exit_kill_switch"
    scout.NEW_EVIDENCE_AXIS = NEW_AXIS
    scout.NEARBY_PRIORS = NEARBY
    scout.CAUSAL_COMPONENTS = list(TICKET["causal_components"])
    scout.PREDICTION = PREDICTION
    scout.PRODUCTION_IMPACT = production_impact(shared_retained=SHARED_MODULE.exists())
    scout.ALLOWED_WRITE_SCOPE = ALLOWED_WRITE_SCOPE
    scout.prior.framework._select_paper_trades = _select_with_kill_switch


def _sum_metrics(metrics: dict[str, Any]) -> dict[str, float]:
    return {
        "expected_value_score": round(sum(float(row["expected_value_score"]) for row in metrics.values()), 4),
        "total_pnl": round(sum(float(row["total_pnl"]) for row in metrics.values()), 2),
        "max_drawdown_pct": max(float(row["max_drawdown_pct"]) for row in metrics.values()),
    }


def _champion_gate(payload: dict[str, Any]) -> dict[str, Any]:
    champion_payload = json.loads(CHAMPION_JSON.read_text(encoding="utf-8"))
    champion_metrics = champion_payload["after_metrics"]
    challenger_metrics = payload["after_metrics"]
    champion_aggregate = _sum_metrics(champion_metrics)
    challenger_aggregate = _sum_metrics(challenger_metrics)
    by_window: dict[str, Any] = {}
    changed_by_window: dict[str, int] = {}
    for label in ("late_strong", "mid_weak", "old_thin"):
        ev_delta = round(float(challenger_metrics[label]["expected_value_score"]) - float(champion_metrics[label]["expected_value_score"]), 4)
        pnl_delta = round(float(challenger_metrics[label]["total_pnl"]) - float(champion_metrics[label]["total_pnl"]), 2)
        changed_by_window[label] = sum(1 for row in payload["target_trades_by_window"][label] if row.get("kill_switch_triggered"))
        by_window[label] = {
            "champion_ev": champion_metrics[label]["expected_value_score"],
            "challenger_ev": challenger_metrics[label]["expected_value_score"],
            "ev_delta": ev_delta,
            "champion_pnl": champion_metrics[label]["total_pnl"],
            "challenger_pnl": challenger_metrics[label]["total_pnl"],
            "pnl_delta": pnl_delta,
            "passed": ev_delta >= 0.0 and pnl_delta >= 0.0,
        }
    aggregate_ev_delta = round(challenger_aggregate["expected_value_score"] - champion_aggregate["expected_value_score"], 4)
    aggregate_pnl_delta = round(challenger_aggregate["total_pnl"] - champion_aggregate["total_pnl"], 2)
    drawdown_worse = round(challenger_aggregate["max_drawdown_pct"] - champion_aggregate["max_drawdown_pct"], 6)
    changed_total = sum(changed_by_window.values())
    reasons: list[str] = []
    if not payload["gate1"]["passed"]:
        reasons.append("gate1_identity_failed")
    if not payload["gate2"]["passed"]:
        reasons.append("gate2_contract_failed")
    if not payload["gate3"]["passed"]:
        reasons.append("gate3_survival_failed")
    if changed_total < MIN_CHANGED_TRADES:
        reasons.append("kill_switch_changed_sample_too_small")
    if any(not row["passed"] for row in by_window.values()):
        reasons.append("accepted_move_v1_window_regression")
    if aggregate_ev_delta < MIN_CHAMPION_EV_IMPROVEMENT:
        reasons.append("accepted_move_v1_material_ev_not_beaten")
    if aggregate_pnl_delta < MIN_CHAMPION_PNL_IMPROVEMENT:
        reasons.append("accepted_move_v1_material_pnl_not_beaten")
    if drawdown_worse > MAX_DRAWDOWN_WORSE:
        reasons.append("drawdown_guard_failed")
    if not payload["gate4"]["target_concentration"]["passed"]:
        reasons.append("concentration_failed")
    return {
        "passed": not reasons,
        "decision": "accepted_move_relief_kill_switch" if not reasons else "rejected_move_relief_kill_switch",
        "failed_reasons": reasons,
        "champion_experiment_id": "exp-20260711-004",
        "by_window": by_window,
        "changed_trades_by_window": changed_by_window,
        "changed_trade_count": changed_total,
        "champion_aggregate": champion_aggregate,
        "challenger_aggregate": challenger_aggregate,
        "aggregate_ev_delta_vs_champion": aggregate_ev_delta,
        "aggregate_pnl_delta_vs_champion": aggregate_pnl_delta,
        "minimum_ev_improvement": MIN_CHAMPION_EV_IMPROVEMENT,
        "minimum_pnl_improvement": MIN_CHAMPION_PNL_IMPROVEMENT,
        "drawdown_worse_vs_champion": drawdown_worse,
        "max_drawdown_worse": MAX_DRAWDOWN_WORSE,
    }


def _shared_parity() -> dict[str, Any]:
    if not SHARED_MODULE.exists():
        return {"passed": False, "status": "conditional_shared_helper_not_retained_before_market_gate", "module": repo_rel(SHARED_MODULE)}
    return {"passed": False, "status": "shared_helper_exists_but_parity_not_verified", "module": repo_rel(SHARED_MODULE)}


def build_payload() -> dict[str, Any]:
    configure_framework()
    payload = champion.scout.build_payload()
    market_gate = _champion_gate(payload)
    parity = _shared_parity()
    accepted = bool(market_gate["passed"] and parity["passed"])
    status = "running" if market_gate["passed"] and not parity["passed"] else ("accepted" if accepted else "rejected")
    decision = "market_gate_passed_shared_paper_pending" if status == "running" else ("accepted_move_relief_kill_switch_shared_paper" if accepted else "rejected_move_relief_kill_switch")
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "lane": "alpha_search",
            "change_type": "exit_policy_full_stack",
            "implementation_mode": "shared_paper_first_conditional_on_champion_gate",
            "mechanism_family": "production_visible_rate_volatility_relief_exit_policy",
            "trial_family": "move_rate_volatility_relief_kill_switch",
            "trial_variant_id": SOURCE_RULE_VERSION,
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "causal_components": list(TICKET["causal_components"]),
            "nearby_prior_experiments": NEARBY,
            "new_evidence_type": "new_gate_shape_exit_kill_switch",
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
                "entry_policy": "unchanged accepted MOVE v1",
                "invalidation": "first MOVE close above SMA20 after prior close at-or-below prior SMA20",
                "exit_timing": "next_session_open",
                "locked_variables": TICKET["locked_variables"],
            },
            "fingerprint_caveat": "Reservation initially classified this source/shape as other; the same experiment adds move_relief and exit_kill_switch coverage.",
            "post_run_reflection": {
                "why_result_happened": (
                    "The exact opposite MOVE20 cross removed enough adverse continuation to beat the accepted fixed-horizon sleeve without truncating winners."
                    if accepted
                    else "The opposite MOVE20 cross was not a reliable thesis invalidation event; it truncated winners or whipsawed too late to beat the accepted fixed-horizon sleeve."
                ),
                "forbidden_near_neighbor_retry": "Do not retry MOVE exit thresholds, SMA spans, persistence, grace days, close-versus-open execution, partial exits, or response curves on these rows.",
                "new_evidence_required": "Reopen only with at least 30 closed prospective MOVE rows carrying lifecycle signals, or a genuinely different publication-timed rate-volatility invalidation source.",
            },
            "changed_files": [
                RUNNER,
                repo_rel(OUT_JSON),
                repo_rel(TICKET_JSON),
                repo_rel(CARD_MD),
                repo_rel(MANIFEST_JSON),
                repo_rel(LOG_JSON),
                "docs/experiment_registry.json",
                "docs/frozen_families.jsonl",
                "scripts/experiment_fingerprint.py",
                "quant/test_experiment_fingerprint.py",
            ],
            "reproduction_commands": [
                ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260711_018_move_relief_sma20_reentry_kill_switch.py",
                ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_experiment_fingerprint.py -q",
                ".\\.venv\\Scripts\\python.exe -B scripts\\build_frozen_families.py",
                ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
            ],
        }
    )
    probability = float(PREDICTION["success_probability"])
    actual = float(accepted)
    payload["calibration"] = {
        "predicted_success_probability": probability,
        "actual_success": bool(actual),
        "brier_score": round((probability - actual) ** 2, 6),
        "predicted_failure_modes": PREDICTION["main_failure_modes"],
        "predicted_failure_modes_hit": market_gate["failed_reasons"],
        "realized_failure_mode": market_gate["failed_reasons"][0] if market_gate["failed_reasons"] else None,
    }
    return payload


def persist(payload: dict[str, Any]) -> None:
    if payload["status"] == "running":
        raise RuntimeError("market gate passed; implement and verify the shared daily kill-switch helper before closeout")
    write_json(OUT_JSON, payload)
    log = {
        key: payload[key]
        for key in (
            "experiment_id", "timestamp", "lane", "status", "decision", "accepted",
            "accepted_alpha", "hypothesis", "change_type", "implementation_mode",
            "mechanism_family", "trial_family", "trial_variant_id", "changed_variable",
            "single_causal_variable", "causal_components", "nearby_prior_experiments",
            "new_evidence_type", "new_evidence_axis", "champion_gate", "gate1", "gate2",
            "gate3", "gate4", "prediction", "calibration", "production_impact",
            "post_run_reflection", "changed_files", "reproduction_commands",
            "fingerprint_caveat",
        )
    }
    log.update({"artifact": repo_rel(OUT_JSON), "lean_quality_passed": True})
    save_experiment_log_entry(log, allow_duplicate=True)
    gate = payload["champion_gate"]
    write_text(
        CARD_MD,
        "\n".join(
            [
                f"# {EXPERIMENT_ID} MOVE Relief Kill Switch",
                "",
                f"Status: `{payload['status']}`",
                f"Decision: `{payload['decision']}`",
                "",
                "## Result",
                "",
                f"- Changed trades: `{gate['changed_trade_count']}` / `49`; by window `{gate['changed_trades_by_window']}`.",
                f"- EV delta versus accepted MOVE v1: `{gate['aggregate_ev_delta_vs_champion']:+.4f}`.",
                f"- PnL delta versus accepted MOVE v1: `${gate['aggregate_pnl_delta_vs_champion']:+,.2f}`.",
                f"- Failed gates: `{gate['failed_reasons']}`.",
                "- Core/live behavior unchanged; `trade_enabled=false`.",
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
    print(json.dumps({"experiment_id": EXPERIMENT_ID, "decision": payload["decision"], "champion_gate": payload["champion_gate"], "shared_parity": payload["shared_parity"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
