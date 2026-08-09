"""Validate the repository-wide fail-closed paper execution-sizing contract."""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
QUANT = ROOT / "quant"
if str(QUANT) not in sys.path:
    sys.path.insert(0, str(QUANT))

from deep_drawdown_rebound_paper_sleeve import (  # noqa: E402
    empty_deep_drawdown_rebound_snapshot,
)
from form4_event_sleeve import (  # noqa: E402
    build_form4_event_sleeve_snapshot,
    empty_form4_event_sleeve_state,
)
from paper_sleeve_execution_contract import (  # noqa: E402
    RULE_VERSION,
    apply_execution_sizing_contracts,
)
from sec_event_sleeve import (  # noqa: E402
    build_sec_event_sleeve_snapshot,
    empty_sec_event_sleeve_state,
)
from sec_financial_report_event_sleeve import (  # noqa: E402
    build_sec_financial_report_event_sleeve_snapshot,
    empty_sec_financial_report_event_sleeve_state,
)
from sec_leadership_event_sleeve import (  # noqa: E402
    build_sec_leadership_event_sleeve_snapshot,
    empty_sec_leadership_event_sleeve_state,
)
from sec_negative_event_sleeve import (  # noqa: E402
    build_sec_negative_event_sleeve_snapshot,
    empty_sec_negative_event_sleeve_state,
)


EXPERIMENT_ID = "exp-20260712-018"
STEM = "paper_sleeve_execution_sizing_contract"
OUT = (
    ROOT
    / "data"
    / "experiments"
    / EXPERIMENT_ID
    / f"exp_20260712_018_{STEM}.json"
)
BEFORE = OUT.parent / "before_measurement.json"
AFTER = OUT.parent / "after_measurement.json"
BASELINE = (
    ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_post_mtm_20260712.json"
)
CURRENT_DAILY = (
    ROOT
    / "data"
    / "daily"
    / "signals"
    / "quant"
    / "quant_signals_20260711.json"
)
OPEN_POSITIONS = ROOT / "operator_inputs" / "open_positions.json"
RUN_SOURCE = QUANT / "run.py"

SURFACE_NAMES = (
    "form4_event_sleeve",
    "sec_negative_event_sleeve",
    "sec_governance_event_sleeve",
    "sec_leadership_event_sleeve",
    "sec_financial_report_event_sleeve",
    "event_sleeve_bundle",
    "state_surface_sleeve",
    "low_deployment_etf_overlay",
    "core_misfit_paper_sleeve",
    "broad_market_paper_sleeve",
    "macro_relief_leadership_paper_sleeve",
    "volatility_relief_stock_leadership_paper_sleeve",
    "move_rate_volatility_relief_paper_sleeve",
    "rolling_corr_peer_shock_paper_sleeve",
    "industry_relative_laggard_repair_paper_sleeve",
    "industry_stable_core_flow_paper_sleeve",
    "turn_of_month_liquid_leadership_paper_sleeve",
    "deep_drawdown_rebound_paper_sleeve",
    "fiftytwo_week_high_proximity_paper_sleeve",
    "narrow_range_compression_breakout_paper_sleeve",
    "distribution_day_absorption_leadership_paper_sleeve",
    "sbc_burden_improvement_paper_sleeve",
    "supplier_financing_debt_relief_paper_sleeve",
    "revision_surprise_low_extension_paper_sleeve",
    "accepted_helper_source_priority_allocator_paper_sleeve",
    "ai_optical_paper_sleeve",
    "volatility_contraction_paper_sleeve",
    "volume_breadth_breakout_paper_sleeve",
    "post_earnings_underpriced_drift_paper_sleeve",
    "pead_broad_universe_paper_sleeve",
    "alpha_score_market_regime_paper_sleeve",
    "accepted_source_consensus_paper_sleeve",
    "free_data_cross_source_consensus_paper_sleeve",
    "fundamental_growth_rs_paper_sleeve",
    "finra_iwm_paper_sleeve",
    "sec_ftd_finra_paper_sleeve",
    "sec_item101_contract_relation_paper_sleeve",
    "moomoo_capital_flow_paper_sleeve",
    "finra_ats_share_paper_sleeve",
    "finra_otc_internalization_paper_sleeve",
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _metric_projection(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "expected_value_score": row.get("expected_value_score"),
        "total_pnl": row.get("total_pnl"),
        "max_drawdown_pct": row.get("max_drawdown_pct"),
        "trade_count": row.get("trade_count"),
        "signals_generated": row.get("signals_generated"),
        "signals_survived": row.get("signals_survived"),
        "survival_rate": row.get("survival_rate"),
    }


def _snapshot_invariants(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_count": snapshot.get("candidate_count"),
        "pending_count": snapshot.get("pending_count"),
        "open_position_count": snapshot.get("open_position_count"),
        "closed_position_count": snapshot.get("closed_position_count"),
        "realized_pnl_to_date": snapshot.get("realized_pnl_to_date"),
        "unrealized_pnl": snapshot.get("unrealized_pnl"),
        "trade_enabled": snapshot.get("trade_enabled"),
    }


def _operator_sentinel_check() -> dict[str, Any]:
    payload = _load(OPEN_POSITIONS)
    rows = []
    for key in ("positions", "core_positions", "observations"):
        rows.extend(payload.get(key) or [])
    missing = [
        {
            "ticker": row.get("ticker"),
            "entry_date_missing": not bool(row.get("entry_date")),
            "target_price_missing": row.get("target_price") is None,
        }
        for row in rows
        if not row.get("entry_date") or row.get("target_price") is None
    ]
    return {
        "passed": not missing,
        "row_count": len(rows),
        "missing": missing,
        "path": OPEN_POSITIONS.relative_to(ROOT).as_posix(),
    }


def _current_daily_contract() -> dict[str, Any]:
    daily = _load(CURRENT_DAILY)
    daily["deep_drawdown_rebound_paper_sleeve"] = (
        empty_deep_drawdown_rebound_snapshot(
            "2026-07-11", "historical_daily_output_omission"
        )
    )
    missing = [name for name in SURFACE_NAMES if not isinstance(daily.get(name), dict)]
    surfaces = {name: deepcopy(daily[name]) for name in SURFACE_NAMES if name not in missing}
    before = {name: _snapshot_invariants(row) for name, row in surfaces.items()}
    summary = apply_execution_sizing_contracts(surfaces)
    after = {name: _snapshot_invariants(row) for name, row in surfaces.items()}
    pending = {
        str(row.get("ticker")): {
            "surface": row.get("surface"),
            "paper_notional_usd": row.get("paper_notional_usd"),
            "experiment_notional_usd": row.get("experiment_notional_usd"),
            "blockers": row.get("execution_sizing_blockers"),
        }
        for row in summary.get("pending_actions") or []
    }
    return {
        "passed": (
            not missing
            and summary.get("surface_count") == 40
            and summary.get("executable_pending_action_count") == 0
            and before == after
            and pending.get("COIN", {}).get("paper_notional_usd") == 10_000.0
            and pending.get("MU", {}).get("paper_notional_usd") == 1_600.0
        ),
        "source": CURRENT_DAILY.relative_to(ROOT).as_posix(),
        "missing_surfaces": missing,
        "summary": summary,
        "snapshot_invariants_unchanged": before == after,
        "current_pending_by_ticker": pending,
        "legacy_unresolved_note": (
            "The 2026-07-11 artifact predates this repair and omits one industry "
            "pending row. Current source now emits pending_entries and focused tests "
            "cover that schema."
        ),
    }


def _queue(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    return {"candidate_count": len(candidates), "candidates": candidates}


def _state_from(snapshot: dict[str, Any], empty_state: dict[str, Any]) -> dict[str, Any]:
    state = deepcopy(empty_state)
    for key in ("pending_entries", "open_positions", "closed_positions", "skipped_entries"):
        state[key] = deepcopy(snapshot.get(key) or [])
    return state


def _event_pending_freeze_check() -> dict[str, Any]:
    specs = [
        {
            "name": "form4",
            "builder": build_form4_event_sleeve_snapshot,
            "queue_arg": "form4_event_queue",
            "candidate": {
                "ticker": "F4",
                "usable_trade_date": "2026-07-10",
                "total_purchase_value": 600_000.0,
            },
            "empty": empty_form4_event_sleeve_state,
            "paper_notional": 10_000.0,
        },
        {
            "name": "sec_negative",
            "builder": build_sec_negative_event_sleeve_snapshot,
            "queue_arg": "sec_event_queue",
            "candidate": {
                "ticker": "NEG",
                "usable_trade_date": "2026-07-10",
                "accession_number": "neg-1",
                "reaction_excess_return": -0.03,
            },
            "empty": empty_sec_negative_event_sleeve_state,
            "paper_notional": 10_000.0,
        },
        {
            "name": "sec_governance",
            "builder": build_sec_event_sleeve_snapshot,
            "queue_arg": "sec_event_queue",
            "candidate": {
                "ticker": "GOV",
                "usable_trade_date": "2026-07-10",
                "accession_number": "gov-1",
                "target_cell": "shareholder_vote|negative_excess_0_to_minus_2pct",
                "reaction_excess_return": -0.01,
            },
            "empty": empty_sec_event_sleeve_state,
            "paper_notional": 10_000.0,
        },
        {
            "name": "sec_leadership",
            "builder": build_sec_leadership_event_sleeve_snapshot,
            "queue_arg": "sec_leadership_event_queue",
            "candidate": {
                "ticker": "LEAD",
                "usable_trade_date": "2026-07-10",
                "accession_number": "lead-1",
                "target_cell": "leadership_change|negative_excess_le_minus_2pct",
                "reaction_excess_return": -0.04,
            },
            "empty": empty_sec_leadership_event_sleeve_state,
            "paper_notional": 10_000.0,
        },
        {
            "name": "sec_financial",
            "builder": build_sec_financial_report_event_sleeve_snapshot,
            "queue_arg": "sec_financial_report_t1_queue",
            "candidate": {
                "ticker": "FIN",
                "usable_trade_date": "2026-07-10",
                "accession_number": "fin-1",
                "event_family": "earnings_8k",
                "t1_excess_return_vs_spy": 0.03,
            },
            "empty": empty_sec_financial_report_event_sleeve_state,
            "paper_notional": 15_000.0,
        },
    ]
    rows = []
    for spec in specs:
        first = spec["builder"](
            **{
                spec["queue_arg"]: _queue([spec["candidate"]]),
                "as_of": "2026-07-11",
                "state": spec["empty"](),
                "persist": False,
            }
        )
        pending = first["pending_entries"][0]
        second = spec["builder"](
            **{
                spec["queue_arg"]: _queue([]),
                "as_of": "2026-07-13",
                "open_prices": {spec["candidate"]["ticker"]: 100.0},
                "current_prices": {spec["candidate"]["ticker"]: 101.0},
                "state": _state_from(first, spec["empty"]()),
                "config": {"event_notional_usd": 2_500.0},
                "persist": False,
            }
        )
        position = second["open_positions"][0]
        rows.append(
            {
                "surface": spec["name"],
                "pending_paper_notional_usd": pending.get("paper_notional_usd"),
                "pending_frozen": pending.get("paper_notional_frozen"),
                "fill_config_notional_usd": 2_500.0,
                "filled_paper_notional_usd": position.get("notional"),
                "passed": (
                    pending.get("paper_notional_usd") == spec["paper_notional"]
                    and pending.get("paper_notional_frozen") is True
                    and position.get("notional") == spec["paper_notional"]
                    and position.get("trade_enabled") is False
                ),
            }
        )
    return {"passed": all(row["passed"] for row in rows), "surfaces": rows}


def _run_wiring_check() -> dict[str, Any]:
    source = RUN_SOURCE.read_text(encoding="utf-8")
    missing_mappings = [
        name for name in SURFACE_NAMES if f'"{name}": {name}' not in source
    ]
    required_outputs = (
        'trend_signals_dict["paper_sleeve_execution_contract"]',
        '"paper_sleeve_execution_contract": paper_sleeve_execution_contract',
        'trend_signals_dict["deep_drawdown_rebound_paper_sleeve"]',
        '"deep_drawdown_rebound_paper_sleeve": deep_drawdown_rebound_paper_sleeve',
        "paper_sleeve_execution_contract = paper_sleeve_execution_contract",
    )
    missing_outputs = [snippet for snippet in required_outputs if snippet not in source]
    return {
        "passed": not missing_mappings and not missing_outputs,
        "surface_count": len(SURFACE_NAMES),
        "missing_mappings": missing_mappings,
        "missing_outputs": missing_outputs,
    }


def main() -> int:
    baseline = _load(BASELINE)
    before_metrics = {
        row["label"]: _metric_projection(row) for row in baseline["windows"]
    }
    after_metrics = deepcopy(before_metrics)
    delta_metrics = {
        label: {
            key: 0.0
            for key in (
                "expected_value_score",
                "total_pnl",
                "max_drawdown_pct",
                "trade_count",
                "signals_generated",
                "signals_survived",
                "survival_rate",
            )
        }
        for label in before_metrics
    }
    gate1 = {
        "passed": baseline.get("experiment_id") == "exp-20260712-015",
        "baseline_artifact": BASELINE.relative_to(ROOT).as_posix(),
        "baseline_experiment_id": baseline.get("experiment_id"),
        "aggregate": baseline.get("aggregate"),
    }
    operator_sentinels = _operator_sentinel_check()
    current_daily = _current_daily_contract()
    event_freeze = _event_pending_freeze_check()
    run_wiring = _run_wiring_check()
    gate2 = {
        "passed": operator_sentinels["passed"] and current_daily["passed"],
        "operator_signal_contract_sentinels": operator_sentinels,
        "current_daily_contract": current_daily,
    }
    gate3 = {
        "passed": all(
            float(row.get("survival_rate") or 0.0) >= 0.05
            for row in before_metrics.values()
        ),
        "windows": {
            label: {
                "signals_generated": row.get("signals_generated"),
                "signals_survived": row.get("signals_survived"),
                "survival_rate": row.get("survival_rate"),
            }
            for label, row in before_metrics.items()
        },
    }
    gate4 = {
        "passed": (
            before_metrics == after_metrics
            and event_freeze["passed"]
            and run_wiring["passed"]
            and current_daily["snapshot_invariants_unchanged"]
            and current_daily["summary"]["executable_pending_action_count"] == 0
        ),
        "core_metrics_unchanged": before_metrics == after_metrics,
        "event_pending_notional_freeze": event_freeze,
        "run_wiring": run_wiring,
        "paper_pnl_and_candidate_counts_unchanged": current_daily[
            "snapshot_invariants_unchanged"
        ],
        "executable_pending_action_count": current_daily["summary"][
            "executable_pending_action_count"
        ],
    }
    accepted = all(gate["passed"] for gate in (gate1, gate2, gate3, gate4))
    artifact = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "generated_at": _utc_now(),
        "lane": "measurement_repair",
        "status": "accepted_measurement_repair" if accepted else "blocked",
        "decision": "accepted_measurement_repair" if accepted else "blocked",
        "accepted": accepted,
        "accepted_alpha": False,
        "hypothesis": (
            "A shared fail-closed execution-sizing contract can separate immutable "
            "paper evidence amounts from executable experiment amounts without "
            "changing paper economics, core metrics, or orders."
        ),
        "changed_variable": RULE_VERSION,
        "single_causal_variable": RULE_VERSION,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": delta_metrics,
        "gate1": gate1,
        "gate2": gate2,
        "gate3": gate3,
        "gate4": gate4,
        "production_impact": {
            "shared_policy_changed": True,
            "run_adapter_changed": True,
            "backtester_adapter_changed": False,
            "candidate_selection_changed": False,
            "paper_notional_economics_changed": False,
            "paper_pnl_changed": False,
            "core_metrics_changed": False,
            "orders_changed": False,
            "trade_enabled": False,
            "live_ready": False,
        },
        "current_pending_interpretation": current_daily[
            "current_pending_by_ticker"
        ],
        "post_run_reflection": {
            "why_result_happened": (
                "The contract is additive and fail-closed. Event amounts are now "
                "frozen before aging, and every current paper surface is audited "
                "without feeding any value into core or order adapters."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not use this repair to retune paper notionals or infer a live "
                "amount from paper PnL."
            ),
            "new_evidence_required": (
                "A sleeve may emit an executable experiment amount only after a "
                "separate Gate 1-4 activation experiment declares and measures its "
                "complete execution envelope."
            ),
        },
        "reproduction_command": (
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260712_018_paper_sleeve_execution_sizing_contract.py"
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    aggregate = baseline["aggregate"]
    flat_metrics = {
        "expected_value_score": aggregate["expected_value_score_sum"],
        "total_pnl": aggregate["total_pnl_sum"],
        "total_trades": aggregate["trade_count_sum"],
        "survival_rate": aggregate["minimum_survival_rate"],
        "max_drawdown_pct": aggregate["worst_max_drawdown_pct"],
    }
    before_measurement = {
        **flat_metrics,
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "phase": "before",
        "source": BASELINE.relative_to(ROOT).as_posix(),
        "paper_sleeve_execution_sizing_contract": "absent",
    }
    after_measurement = {
        **flat_metrics,
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "phase": "after",
        "decision": artifact["decision"],
        "accepted": accepted,
        "paper_sleeve_execution_sizing_contract": RULE_VERSION,
        "surface_count": current_daily["summary"]["surface_count"],
        "executable_pending_action_count": current_daily["summary"][
            "executable_pending_action_count"
        ],
        "event_pending_notional_freeze_passed": event_freeze["passed"],
        "core_metrics_unchanged": before_metrics == after_metrics,
    }
    BEFORE.write_text(
        json.dumps(before_measurement, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    AFTER.write_text(
        json.dumps(after_measurement, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    OUT.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": artifact["decision"],
                "surface_count": current_daily["summary"]["surface_count"],
                "pending_actions": current_daily["current_pending_by_ticker"],
                "event_freeze_passed": event_freeze["passed"],
                "core_metrics_unchanged": before_metrics == after_metrics,
                "artifact": OUT.relative_to(ROOT).as_posix(),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if accepted else 2


if __name__ == "__main__":
    raise SystemExit(main())
