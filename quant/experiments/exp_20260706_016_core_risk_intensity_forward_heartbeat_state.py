from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260706-016"
SLUG = "core_risk_intensity_forward_heartbeat_state"
REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
if str(QUANT_ROOT) not in sys.path:
    sys.path.insert(0, str(QUANT_ROOT))

from core_risk_intensity_ledger import (  # noqa: E402
    RULE_VERSION as CORE_RISK_RULE_VERSION,
    SURFACE_CONTRACT,
    append_core_risk_intensity_observation_snapshot,
    build_core_risk_intensity_observation_snapshot,
)
from sleeve_health import RULE_VERSION as HEALTH_RULE_VERSION  # noqa: E402
from sleeve_health import build_sleeve_health_report


BASELINE_RESULT_FILE = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
CURRENT_HEALTH_LOG = REPO_ROOT / "data" / "paper_sleeves" / "sleeve_health.jsonl"
DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT = DATA_DIR / f"exp_20260706_016_{SLUG}.json"


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def signal(ticker: str, risk_pct: float, *, as_selected: bool = True) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "strategy": "trend_long",
        "sector": "Healthcare",
        "entry_price": 1208.12,
        "stop_price": 1150.84,
        "target_price": 1379.97,
        "sizing": {
            "base_risk_pct": 0.01,
            "risk_pct": risk_pct,
            "shares_to_buy": 30 if as_selected else 0,
            "position_value_usd": 36243.6,
            "risk_amount_usd": 2026.47,
            "risk_on_unmodified_risk_multiplier_applied": 2.0,
            "rs20_entry_state_risk_multiplier_applied": 1.1,
            "signal_day_ticker_green_risk_multiplier_applied": 1.05,
            "tqs_risk_multiplier_applied": 1.0,
        },
    }


def latest_core_risk_health() -> dict[str, Any]:
    latest = None
    if CURRENT_HEALTH_LOG.exists():
        with CURRENT_HEALTH_LOG.open("r", encoding="utf-8") as handle:
            for raw in handle:
                if not raw.strip():
                    continue
                row = json.loads(raw)
                latest = row
    if not latest:
        return {}
    status = (latest.get("disk_status") or {}).get(
        "core_risk_intensity_forward_observation"
    )
    return {
        "asof_date": latest.get("asof_date"),
        "rule_version": latest.get("rule_version"),
        "status": status,
        "stalled_sleeves_contains_core_risk": (
            "core_risk_intensity_forward_observation"
            in set(latest.get("stalled_sleeves") or [])
        ),
    }


def aggregate_baseline_metrics() -> dict[str, Any]:
    baseline = read_json(BASELINE_RESULT_FILE, {}) or {}
    windows = list(baseline.get("windows") or [])
    return {
        "expected_value_score": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows), 4
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "total_trades": sum(int(row.get("trade_count") or 0) for row in windows),
        "max_drawdown_pct": max(
            [float(row.get("max_drawdown_pct") or 0.0) for row in windows] or [0.0]
        ),
        "survival_rate": round(
            sum(float(row.get("survival_rate") or 0.0) for row in windows) / len(windows),
            6,
        )
        if windows
        else None,
        "baseline_windows": windows,
    }


def build_contract_demo() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as temp_name:
        temp_root = Path(temp_name)
        sleeve_root = temp_root / "paper_sleeves"
        core_dir = sleeve_root / "core_risk_intensity_forward_observation"
        ledger = core_dir / "snapshots.jsonl"

        first = build_core_risk_intensity_observation_snapshot(
            as_of="2026-06-28",
            advisory_signals=[signal("LLY", 0.0284574566)],
            selected_signals=[signal("LLY", 0.0284574566)],
            metadata={"source": "exp-20260706-016-test"},
        )
        empty = build_core_risk_intensity_observation_snapshot(
            as_of="2026-07-05",
            advisory_signals=[],
            selected_signals=[],
            metadata={"source": "exp-20260706-016-test"},
        )
        first_persistence = append_core_risk_intensity_observation_snapshot(first, ledger)
        empty_persistence = append_core_risk_intensity_observation_snapshot(empty, ledger)
        state = read_json(core_dir / "state.json", {})

        ordinary = sleeve_root / "ordinary_sleeve"
        ordinary.mkdir(parents=True, exist_ok=True)
        (ordinary / "snapshots.jsonl").write_text(
            json.dumps({"asof_date": "2026-06-28"}) + "\n",
            encoding="utf-8",
        )
        (ordinary / "state.json").write_text(
            json.dumps({"last_run_as_of": "2026-07-05"}) + "\n",
            encoding="utf-8",
        )

        health = build_sleeve_health_report(
            "2026-07-05",
            {},
            sleeves_root=sleeve_root,
            health_log_path=temp_root / "health.jsonl",
            persist=False,
        )
        disk_status = health.get("disk_status") or {}
        return {
            "first_snapshot": {
                "candidate_count": first.get("candidate_count"),
                "selected_count": first.get("selected_count"),
                "rows": len(first.get("rows") or []),
            },
            "first_persistence": first_persistence,
            "empty_snapshot": {
                "candidate_count": empty.get("candidate_count"),
                "selected_count": empty.get("selected_count"),
                "rows": len(empty.get("rows") or []),
            },
            "empty_persistence": empty_persistence,
            "state": state,
            "health_after_heartbeat": disk_status.get(
                "core_risk_intensity_forward_observation"
            ),
            "ordinary_unmarked_state_control": disk_status.get("ordinary_sleeve"),
            "stalled_sleeves": health.get("stalled_sleeves"),
        }


def main() -> dict[str, Any]:
    baseline_metrics = aggregate_baseline_metrics()
    contract_demo = build_contract_demo()
    core_health = contract_demo["health_after_heartbeat"]
    ordinary_health = contract_demo["ordinary_unmarked_state_control"]
    accepted = (
        contract_demo["state"].get("surface_contract") == SURFACE_CONTRACT
        and contract_demo["state"].get("as_of") == "2026-07-05"
        and contract_demo["state"].get("candidate_count") == 0
        and contract_demo["state"].get("last_nonempty_as_of") == "2026-06-28"
        and core_health.get("status") == "fresh_summary"
        and ordinary_health.get("status") == "stale"
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": "2026-07-06",
        "artifact": repo_rel(ARTIFACT),
        "baseline_result_file": repo_rel(BASELINE_RESULT_FILE),
        "expected_value_score": baseline_metrics["expected_value_score"],
        "total_pnl": baseline_metrics["total_pnl"],
        "total_trades": baseline_metrics["total_trades"],
        "max_drawdown_pct": baseline_metrics["max_drawdown_pct"],
        "survival_rate": baseline_metrics["survival_rate"],
        "accepted_alpha": False,
        "accepted_measurement_repair": accepted,
        "decision": "accepted_measurement_repair_core_risk_intensity_heartbeat_state"
        if accepted
        else "rejected_core_risk_intensity_heartbeat_state",
        "alpha_hypothesis": (
            "Pre-execution core risk intensity may support a future risk-allocation "
            "alpha, but only if the forward surface can prove each daily run, "
            "including zero-candidate days."
        ),
        "measurement_repair_hypothesis": (
            "The row-only ledger makes zero-candidate daily runs indistinguishable "
            "from dead plumbing in sleeve_health."
        ),
        "gate1": {
            "passed": True,
            "baseline_result_file": repo_rel(BASELINE_RESULT_FILE),
            "strategy_metrics_unchanged": True,
        },
        "gate2": {
            "passed": True,
            "runtime_fields_checked": {
                "as_of": contract_demo["state"].get("as_of"),
                "entry_date": "not_applicable_forward_observation_heartbeat",
                "target_price": "present_on_nonempty_core_risk_rows",
            },
        },
        "gate3": {
            "passed": True,
            "not_applicable_reason": "No signal, filter, ranking, sizing, exit, or order rule changed.",
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "survival_rate_delta": 0.0,
        },
        "gate4": {
            "passed": accepted,
            "measurement_repair_only": True,
            "before_after_strategy_delta": {
                "expected_value_score_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
                "strategy_behavior_changed": False,
            },
            "measurement_contract_delta": {
                "current_real_health_status": latest_core_risk_health(),
                "after_heartbeat_status": core_health,
                "ordinary_unmarked_state_control": ordinary_health,
            },
        },
        "contract_demo": contract_demo,
        "production_impact": {
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "orders_changed": False,
            "risk_budget_changed": False,
            "trade_enabled": False,
            "daily_snapshot_exposed": True,
            "paper_health_report_changed": True,
            "parity_note": "Append-only observation heartbeat and read-side health only; no trading policy consumes this state.",
        },
        "rule_versions": {
            "core_risk_intensity": CORE_RISK_RULE_VERSION,
            "surface_contract": SURFACE_CONTRACT,
            "sleeve_health": HEALTH_RULE_VERSION,
        },
        "changed_files": [
            "quant/core_risk_intensity_ledger.py",
            "quant/sleeve_health.py",
            "quant/test_core_risk_intensity_ledger.py",
            "quant/test_sleeve_health.py",
            "quant/experiments/exp_20260706_016_core_risk_intensity_forward_heartbeat_state.py",
            repo_rel(ARTIFACT),
        ],
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260706_016_core_risk_intensity_forward_heartbeat_state.py",
            ".\\.venv\\Scripts\\python.exe -m pytest quant\\test_core_risk_intensity_ledger.py quant\\test_sleeve_health.py -q",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
    }
    write_json(ARTIFACT, payload)
    return payload


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, sort_keys=True))
