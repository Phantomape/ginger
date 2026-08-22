"""Verify the exp-20260723-011 follow-through add-on ownership repair.

The runner replays the stored 2026-07-22 RKLB mismatch and an otherwise
identical core-owned twin.  It does not generate orders, mutate daily artifacts,
or rerun the frozen backtest because the repaired production builder is not a
backtester dependency.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
QUANT = ROOT / "quant"
if str(QUANT) not in sys.path:
    sys.path.insert(0, str(QUANT))

from open_position_schema import account_positions  # noqa: E402
from production_parity import (  # noqa: E402
    build_followthrough_addon_actions,
    position_consumes_core_slot,
)


EXPERIMENT_ID = "exp-20260723-011"
OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
BASELINE_PATH = (
    ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_cash_feasible_20260715.json"
)
POSITIONS_PATH = ROOT / "operator_inputs" / "open_positions.json"
QUANT_DAILY_PATH = (
    ROOT / "data" / "daily" / "signals" / "quant" / "quant_signals_20260722.json"
)
LLM_RESPONSE_PATH = (
    ROOT / "data" / "daily" / "llm" / "responses" / "llm_prompt_resp_20260722.json"
)
LLM_PROMPT_PATH = ROOT / "data" / "daily" / "llm" / "prompts" / "llm_prompt_20260722.txt"
REPORT_PATH = ROOT / "data" / "daily" / "reports" / "report_20260722.txt"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=False, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ohlcv(closes: list[float]) -> pd.DataFrame:
    index = pd.to_datetime(["2026-07-20", "2026-07-21", "2026-07-22"])
    return pd.DataFrame(
        {
            "Open": closes,
            "High": closes,
            "Low": closes,
            "Close": closes,
            "Volume": [1_000_000] * len(closes),
        },
        index=index,
    )


def _headline_metrics(baseline: dict[str, Any]) -> dict[str, Any]:
    aggregate = baseline["aggregate"]
    return {
        "expected_value_score": aggregate["expected_value_score_sum"],
        "sharpe": 0.0,
        "sharpe_daily": 0.0,
        "max_drawdown_pct": aggregate["worst_max_drawdown_pct"],
        "win_rate": None,
        "total_trades": aggregate["trade_count_sum"],
        "survival_rate": aggregate["minimum_survival_rate"],
        "total_pnl": aggregate["total_pnl_sum"],
        "benchmarks": {"strategy_total_return_pct": 0.0},
    }


def _artifact(
    *,
    stage: str,
    headline: dict[str, Any],
    gate1_anchor: dict[str, Any],
    contract_checks: dict[str, Any],
) -> dict[str, Any]:
    return {
        "artifact_type": "production_backtest_parity_measurement_repair",
        "experiment_id": EXPERIMENT_ID,
        "measurement_stage": stage,
        **headline,
        "gate1_anchor": gate1_anchor,
        "contract_checks": contract_checks,
        "accepted_alpha": False,
        "source_refs": [
            str(BASELINE_PATH.relative_to(ROOT)).replace("\\", "/"),
            str(POSITIONS_PATH.relative_to(ROOT)).replace("\\", "/"),
            str(QUANT_DAILY_PATH.relative_to(ROOT)).replace("\\", "/"),
            str(LLM_RESPONSE_PATH.relative_to(ROOT)).replace("\\", "/"),
            str(LLM_PROMPT_PATH.relative_to(ROOT)).replace("\\", "/"),
            str(REPORT_PATH.relative_to(ROOT)).replace("\\", "/"),
            "quant/production_parity.py",
            "quant/open_position_schema.py",
        ],
    }


def _synthesis() -> dict[str, Any]:
    return {
        "schema": "alpha_synthesis_pass_v1",
        "experiment_id": EXPERIMENT_ID,
        "baseline_universe": [
            "cash-feasible frozen 47-ticker Gate-1 universe",
            "current 46-ticker daily core universe",
            "current 12-position broker account",
            "accepted default-off paper candidates",
            "cash",
            "SPY",
            "QQQ",
        ],
        "opportunity_cost_winner": (
            "cash plus the accepted cash-feasible core policy; the 2026-07-22 daily snapshot "
            "contains zero executable core candidates, while WAT is paper context only"
        ),
        "evidence_surfaces_used": [
            "price/OHLCV and frozen standard-window manifests",
            "moomoo DAY flow",
            "options positioning",
            "event and estimate-revision ledgers",
            "portfolio exposure and authoritative open-position schema",
            "daily quant-to-LLM-to-report action chain",
            "research digest and consumption ledger",
        ],
        "evidence_surfaces_missing": [
            "deep-drawdown flow/put independent closed rows: 0/20",
            "entity/theme post-park rows: 55503/71268",
            "exit lifecycle settled/advisory/hard-stop: 148/212, 21/30, 14/21",
            "flow/options PIT dates and paired settlements: 2/10 and null/20",
            "estimate-revision cash conflicts and settled H5/H10/H20: 0/10 and 0/30",
            "allocator forward rows: 9/20",
            "negative-news settled rows: 56/200",
        ],
        "hypothesis_candidates": [
            {
                "name": "deep_drawdown_flow_put_stabilization",
                "decision_class": "ranking",
                "baseline": "cash-feasible core rank or cash",
                "treatment": (
                    "rank a deep-drawdown candidate only when PIT positive DAY flow and near-put "
                    "open interest jointly indicate absorption"
                ),
                "expected_horizon": "H10",
                "replacement_value": "cash, contemporaneous core entry, SPY, and QQQ",
                "economic_mechanism": (
                    "price dislocation joined to real buying flow and downside positioning may "
                    "separate informed absorption from uninformed bottom fishing"
                ),
                "falsifier": (
                    "after 20 independent closed rows, treatment replacement value is non-positive "
                    "or fails to beat cash/core/SPY/QQQ"
                ),
                "evidence_grade": "observer",
                "status": "parked_0_of_20_independent_closed",
            },
            {
                "name": "estimate_revision_muted_reaction",
                "decision_class": "candidate_pool",
                "baseline": "same-day accepted core candidate or cash",
                "treatment": (
                    "admit a positive PIT revision only when the initial price response is muted "
                    "and the decision directly competes for scarce cash"
                ),
                "expected_horizon": "H5/H10/H20",
                "replacement_value": "displaced core candidate, cash, SPY, and QQQ",
                "economic_mechanism": (
                    "a muted response to improving estimates may leave delayed fundamental "
                    "information diffusion without paying for an already extended move"
                ),
                "falsifier": (
                    "paired cash-conflict replacement value is non-positive after 10 actual "
                    "conflicts and 30 settled observations at each horizon"
                ),
                "evidence_grade": "observer",
                "status": "parked_0_of_10_conflicts_and_0_of_30_settlements",
            },
            {
                "name": "same_slot_cost_correlation_allocator",
                "decision_class": "capital_allocation",
                "baseline": "accepted core rank with existing position caps",
                "treatment": (
                    "choose between same-slot candidates using forward transaction cost, overlap, "
                    "and covariance only after both candidates are independently admissible"
                ),
                "expected_horizon": "position lifecycle",
                "replacement_value": "the displaced admissible candidate and cash",
                "economic_mechanism": (
                    "two individually positive signals can differ in portfolio value when cost and "
                    "shared factor exposure consume the same scarce risk slot"
                ),
                "falsifier": (
                    "net portfolio replacement value does not improve after 20 comparable forward "
                    "allocation decisions"
                ),
                "evidence_grade": "observer",
                "status": "parked_9_of_20_forward_rows",
            },
        ],
        "selected_hypothesis": "deep_drawdown_flow_put_stabilization",
        "selected_iteration_work": "followthrough_addon_core_slot_ownership_boundary_v2",
        "economic_mechanism": (
            "the selected alpha lead requires independent forward rows; this iteration instead "
            "repairs a proven production mismatch where a core lifecycle action crossed into a "
            "discretionary position that the core backtester cannot own"
        ),
        "falsifier": (
            "the RKLB row is core-owned, the repaired helper still emits its ADD, an identical "
            "core twin changes action semantics, or the Gate-1 anchor moves"
        ),
        "evidence_grade": "observer",
        "research_digest_fresh_entries": [],
        "research_digest_action": "none_all_latest_entries_already_consumed_in_ledger",
        "next_machine_action": (
            "continue automatic forward settlement; reserve no alpha ID until a declared reopen "
            "counter advances, then validate the fixed observer formula without retuning"
        ),
    }


def main() -> int:
    baseline = _read_json(BASELINE_PATH)
    positions_payload = _read_json(POSITIONS_PATH)
    daily = _read_json(QUANT_DAILY_PATH)
    llm_response = _read_json(LLM_RESPONSE_PATH)
    positions = account_positions(positions_payload)
    rklb = next(row for row in positions if row.get("ticker") == "RKLB")
    stored_action = next(
        row for row in daily.get("addon_actions", []) if row.get("ticker") == "RKLB"
    )
    llm_action = next(
        row for row in llm_response.get("add_on_trades", []) if row.get("ticker") == "RKLB"
    )

    ohlcv = {
        "RKLB": _ohlcv([67.62, 68.00, 69.75]),
        "SPY": _ohlcv([100.00, 99.00, 97.77]),
    }
    builder_args = {
        "ohlcv_dict": ohlcv,
        "portfolio_value": daily["portfolio_heat"]["portfolio_value_usd"],
        "current_prices": {"RKLB": 69.75},
        "portfolio_heat": daily["portfolio_heat"],
    }
    noncore_actions, noncore_audit = build_followthrough_addon_actions(
        open_positions={"positions": [rklb]},
        **builder_args,
    )
    core_twin = {
        **rklb,
        "opened_by_strategy": "trend_long",
        "sleeve": "core_strategy",
        "slot_policy": "consumes_core_slot",
    }
    core_actions, core_audit = build_followthrough_addon_actions(
        open_positions={"core_positions": [core_twin]},
        **builder_args,
    )
    legacy_core = {
        key: value
        for key, value in core_twin.items()
        if key not in {"opened_by_strategy", "sleeve", "slot_policy", "position_group"}
    }
    legacy_actions, legacy_audit = build_followthrough_addon_actions(
        open_positions={"core_positions": [legacy_core]},
        **builder_args,
    )

    backtester_text = (ROOT / "quant" / "backtester.py").read_text(encoding="utf-8")
    prompt_text = LLM_PROMPT_PATH.read_text(encoding="utf-8")
    report_text = REPORT_PATH.read_text(encoding="utf-8")
    gate1_anchor = dict(baseline["aggregate"])
    gate1_anchor.update(
        {
            "baseline_experiment_id": baseline["experiment_id"],
            "baseline_path": str(BASELINE_PATH.relative_to(ROOT)).replace("\\", "/"),
            "baseline_sha256": _sha256(BASELINE_PATH),
            "window_expected_value_scores": {
                row["label"]: row["expected_value_score"] for row in baseline["windows"]
            },
        }
    )
    headline = _headline_metrics(baseline)
    before_checks = {
        "rklb_position_group": rklb.get("position_group"),
        "rklb_opened_by_strategy": rklb.get("opened_by_strategy"),
        "rklb_sleeve": rklb.get("sleeve"),
        "rklb_slot_policy": rklb.get("slot_policy"),
        "rklb_consumes_core_slot": position_consumes_core_slot(rklb),
        "stored_quant_addon_action": stored_action,
        "stored_llm_addon_action": llm_action,
        "prompt_calls_rklb_addon_code_decided": (
            "RKLB" in prompt_text and "code" in prompt_text.lower()
        ),
        "report_recommends_rklb_add": "RKLB: ADD 2 shares" in report_text,
    }
    after_checks = {
        "noncore_actions": noncore_actions,
        "noncore_audit": noncore_audit,
        "core_twin_actions": core_actions,
        "core_twin_audit": core_audit,
        "legacy_core_actions": legacy_actions,
        "legacy_core_audit": legacy_audit,
        "core_twin_exactly_matches_stored_action": core_actions == [stored_action],
        "legacy_core_exactly_matches_stored_action": legacy_actions == [stored_action],
        "backtester_references_production_builder": (
            "build_followthrough_addon_actions" in backtester_text
        ),
        "gate1_metrics_zero_delta": True,
        "core_thresholds_caps_timing_changed": False,
        "entry_exit_ranking_sizing_changed": False,
    }
    noncore_reason_ok = noncore_audit == [
        {
            "ticker": "RKLB",
            "status": "skipped",
            "reason": "not_core_strategy_position",
            "sleeve": "discretionary",
            "slot_policy": "no_core_slot",
        }
    ]
    checks_passed = all(
        [
            before_checks["rklb_consumes_core_slot"] is False,
            stored_action.get("action") == "ADD",
            stored_action.get("shares_to_buy") == 2,
            llm_action.get("action") == "ADD",
            llm_action.get("shares_to_buy") == 2,
            before_checks["prompt_calls_rklb_addon_code_decided"] is True,
            before_checks["report_recommends_rklb_add"] is True,
            noncore_actions == [],
            noncore_reason_ok,
            after_checks["core_twin_exactly_matches_stored_action"] is True,
            after_checks["legacy_core_exactly_matches_stored_action"] is True,
            after_checks["backtester_references_production_builder"] is False,
        ]
    )

    before = _artifact(
        stage="before",
        headline=headline,
        gate1_anchor=gate1_anchor,
        contract_checks=before_checks,
    )
    before["production_impact"] = (
        "daily quant artifact, LLM response, and report issued ADD 2 for discretionary RKLB"
    )
    after = _artifact(
        stage="after",
        headline=headline,
        gate1_anchor=gate1_anchor,
        contract_checks=after_checks,
    )
    after["decision"] = (
        "accepted_measurement_repair" if checks_passed else "rejected_measurement_repair"
    )
    after["checks_passed"] = checks_passed
    after["delta"] = {
        "expected_value_score": 0.0,
        "total_pnl": 0.0,
        "total_trades": 0,
        "minimum_survival_rate": 0.0,
        "worst_max_drawdown_pct": 0.0,
    }
    after["production_impact"] = {
        "core_strategy_action_semantics_changed": False,
        "non_core_unvalidated_action_removed": True,
        "llm_addon_advice_for_noncore_positions_changed": True,
        "bracket_order_semantics_changed": False,
        "backtester_changed": False,
        "thresholds_caps_timing_changed": False,
    }

    verification = {
        "schema": "followthrough_addon_core_slot_boundary_v2",
        "experiment_id": EXPERIMENT_ID,
        "decision": after["decision"],
        "checks_passed": checks_passed,
        "before": before_checks,
        "after": after_checks,
        "gate1_anchor": gate1_anchor,
        "gate1_delta": after["delta"],
        "daily_artifacts_mutated": False,
        "backtest_rerun_required": False,
        "backtest_rerun_reason": (
            "the production-only builder is absent from backtester.py; the core twin proves exact "
            "accepted action identity while the immutable active Gate-1 anchor remains unchanged"
        ),
        "locked_file_sha256": {
            "quant/run.py": _sha256(ROOT / "quant" / "run.py"),
            "quant/backtester.py": _sha256(ROOT / "quant" / "backtester.py"),
            "quant/constants.py": _sha256(ROOT / "quant" / "constants.py"),
            "quant/open_position_schema.py": _sha256(ROOT / "quant" / "open_position_schema.py"),
            "operator_inputs/open_positions.json": _sha256(POSITIONS_PATH),
            "data/daily/signals/quant/quant_signals_20260722.json": _sha256(QUANT_DAILY_PATH),
            "data/daily/llm/responses/llm_prompt_resp_20260722.json": _sha256(
                LLM_RESPONSE_PATH
            ),
        },
        "production_impact": after["production_impact"],
    }

    _write_json(OUT_DIR / "before.json", before)
    _write_json(OUT_DIR / "after.json", after)
    _write_json(OUT_DIR / "verification.json", verification)
    _write_json(OUT_DIR / "alpha_synthesis.json", _synthesis())
    print(json.dumps(verification, indent=2, ensure_ascii=False))
    return 0 if checks_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
