from __future__ import annotations

import json
import math
from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import exp_20260511_115_space_basket_momentum_risk as basket_exp
import exp_20260516_029_space_dual_catalyst_benchmark_breadth_trend_risk as accepted_stack
import exp_20260516_032_space_forward_benchmark_same_theme_satcom_fallback_pool as prior_pool
import exp_20260517_018_space_vsat_fallback_risk_scalar as prior_risk


EXPERIMENT_ID = "exp-20260518-017"
EXPERIMENT_NAME = "space_vsat_isolated_fallback_pool"
CHANGED_VARIABLE = "space_vsat_forward_benchmark_same_theme_isolated_fallback_membership"

ROOT = accepted_stack.BASE.ROOT
DATA_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
DOC_LOG = ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_ARTIFACT = (
    ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{EXPERIMENT_NAME}.md"
)
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"

BASE_OFFICIAL_SPACE_TICKERS = prior_pool.BASE_OFFICIAL_SPACE_TICKERS
TARGET_ADDED_TICKERS = ("VSAT",)
EXTENDED_OFFICIAL_SPACE_TICKERS = tuple(
    sorted(set(BASE_OFFICIAL_SPACE_TICKERS).union(TARGET_ADDED_TICKERS))
)
ACCEPTED_BENCHMARK_BREADTH_SCALAR = prior_pool.ACCEPTED_BENCHMARK_BREADTH_SCALAR
RISK_SCALAR = 1.0


def _safe(value: Any) -> Any:
    return accepted_stack._safe(value)


@contextmanager
def _base_official_basket_scope(base_tickers: tuple[str, ...]):
    """Compute Space peer/basket state from the accepted base official pool only."""
    original = basket_exp._space_basket_momentum
    base = tuple(str(ticker).upper() for ticker in base_tickers)

    def patched(features_dict: dict[str, dict[str, Any]]) -> dict[str, Any]:
        values: dict[str, float] = {}
        for ticker in base:
            raw = (features_dict.get(ticker) or {}).get(
                basket_exp.SPACE_BASKET_MOMENTUM_FIELD
            )
            value = basket_exp._round(raw, 6)
            if value is not None:
                values[ticker] = value
        if not values:
            return {"state": "missing", "value": None, "values": {}}
        average = sum(values.values()) / len(values)
        state = (
            "positive"
            if average > basket_exp.SPACE_BASKET_MOMENTUM_THRESHOLD
            else "nonpositive"
        )
        return {
            "state": state,
            "value": basket_exp._round(average, 6),
            "values": dict(sorted(values.items())),
            "scope": "base_official_space_pool_only",
            "excluded_from_basket": list(TARGET_ADDED_TICKERS),
        }

    basket_exp._space_basket_momentum = patched
    try:
        yield
    finally:
        basket_exp._space_basket_momentum = original


def _run_baseline() -> tuple[dict[str, Any], dict[str, Any]]:
    gates = prior_pool._collect_gates_with_pool(BASE_OFFICIAL_SPACE_TICKERS)
    result, _ = prior_pool._run_accepted_stack_with_pool(
        label="baseline_exp_20260516_029",
        tickers=BASE_OFFICIAL_SPACE_TICKERS,
        gates=gates,
    )
    return result, gates


def _run_variant(base_gates: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    with prior_pool.prior_pool.exp013._official_space_pool(
        EXTENDED_OFFICIAL_SPACE_TICKERS
    ):
        with _base_official_basket_scope(BASE_OFFICIAL_SPACE_TICKERS):
            with prior_risk._risk_scaled_trend_fallback_scope(
                added_tickers=TARGET_ADDED_TICKERS,
                base_tickers=BASE_OFFICIAL_SPACE_TICKERS,
                risk_scalar=RISK_SCALAR,
            ) as fallback_scope:
                result = accepted_stack._run_variant(
                    benchmark_breadth_scalar=ACCEPTED_BENCHMARK_BREADTH_SCALAR,
                    gates=base_gates,
                )
    result = deepcopy(result)
    result.setdefault("parameters", {})
    result["parameters"].update(
        {
            "label": EXPERIMENT_NAME,
            "accepted_benchmark_breadth_scalar": ACCEPTED_BENCHMARK_BREADTH_SCALAR,
            "base_official_space_tickers": list(BASE_OFFICIAL_SPACE_TICKERS),
            "candidate_generation_space_tickers": list(EXTENDED_OFFICIAL_SPACE_TICKERS),
            "added_tickers": list(TARGET_ADDED_TICKERS),
            "peer_basket_scope": "base_official_space_pool_only",
            "space_vsat_fallback_risk_scalar": RISK_SCALAR,
        }
    )
    return result, prior_risk._fallback_filter_summary(fallback_scope, RISK_SCALAR)


def _gate_variant(
    *,
    baseline: dict[str, Any],
    variant: dict[str, Any],
    forward_gate: dict[str, Any],
    fallback_summary: dict[str, Any],
) -> dict[str, Any]:
    gate = prior_risk._gate_variant(
        baseline=baseline,
        variant=variant,
        forward_gate=forward_gate,
        fallback_summary=fallback_summary,
    )
    gate["production_impact"] = {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": True,
        "parity_test_added": False,
        "live_slots": 0,
    }
    gate["peer_basket_scope"] = "base_official_space_pool_only"
    return gate


def _metrics_summary(result: dict[str, Any]) -> dict[str, Any]:
    return prior_pool._metrics_summary(result)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                lines.append(line)
                continue
            if row.get("experiment_id") != payload.get("experiment_id"):
                lines.append(line)
    lines.append(json.dumps(_safe(payload), ensure_ascii=False, sort_keys=True))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _failed_reasons(gate: dict[str, Any]) -> str | None:
    if gate.get("passed"):
        return None
    failed = [name for name, ok in (gate.get("reasons") or {}).items() if not ok]
    return "; ".join(failed) or "gate failed"


def _changed_windows(gate: dict[str, Any]) -> dict[str, Any]:
    return {
        label: row
        for label, row in (gate.get("by_window_delta_vs_before") or {}).items()
        if any(abs(float(row.get(key) or 0.0)) > 1e-9 for key in ("expected_value_score", "total_pnl", "max_drawdown_pct"))
    }


def _make_record(
    *,
    baseline: dict[str, Any],
    variant: dict[str, Any],
    base_gates: dict[str, Any],
    forward_gate: dict[str, Any],
    fallback_summary: dict[str, Any],
    field_check: dict[str, Any],
    gate: dict[str, Any],
) -> dict[str, Any]:
    decision = "accept" if gate["passed"] else "reject"
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(UTC).isoformat(),
        "status": "accepted" if decision == "accept" else "rejected",
        "lane": "alpha_search",
        "hypothesis": (
            "VSAT has one mature satcom forward row that beat cash, same-theme "
            "replacement, SPY, QQQ, UFO, and ARKX, but adding it to the official "
            "Space peer basket contaminated existing Space peer/basket states in "
            "exp-20260517-018. An isolated fallback pool may preserve VSAT "
            "replacement alpha without changing the accepted official Space basket."
        ),
        "change_summary": (
            "Add VSAT as a trend-only fallback candidate while computing Space "
            "peer/basket state from the accepted base official pool only."
        ),
        "change_type": "candidate_pool_governance",
        "component": "quant/experiments",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "parameters": {
            "baseline_stack": "accepted_space_exp_20260516_029",
            "accepted_benchmark_breadth_scalar": ACCEPTED_BENCHMARK_BREADTH_SCALAR,
            "base_official_space_tickers": list(BASE_OFFICIAL_SPACE_TICKERS),
            "candidate_generation_space_tickers": list(EXTENDED_OFFICIAL_SPACE_TICKERS),
            "target_added_tickers": list(TARGET_ADDED_TICKERS),
            "risk_scalar_fixed_from_prior_sweep": RISK_SCALAR,
            "peer_basket_scope": "base_official_space_pool_only",
            "forward_gate": forward_gate,
            "anti_js": "No JavaScript was used.",
        },
        "backtest_protocol": (
            "docs/backtesting.md fixed 3-window Space protocol using frozen "
            "Space augmented snapshots"
        ),
        "date_range": {
            label: spec
            for label, spec in accepted_stack.BASE.exp041.source_diversity_exp.WINDOWS.items()
        },
        "gate2_required_fields": field_check,
        "field_check": {
            "open_position_fields": field_check,
            "forward_gate_passed": bool(forward_gate.get("passed")),
            "base_space_gate_pool": base_gates.get("official_space_pool"),
        },
        "before_metrics": _metrics_summary(baseline),
        "after_metrics": _metrics_summary(variant),
        "delta_metrics": {
            "aggregate": gate["aggregate_delta_vs_before"],
            "by_window": gate["by_window_delta_vs_before"],
        },
        "expected_value_score_delta": gate["aggregate_delta_vs_before"][
            "expected_value_score_sum"
        ],
        "total_pnl_delta": gate["aggregate_delta_vs_before"]["total_pnl_sum"],
        "gate_results": gate,
        "fallback_filter_summary": fallback_summary,
        "changed_windows": _changed_windows(gate),
        "decision": decision,
        "rejection_reason": _failed_reasons(gate),
        "next_evidence_needed": (
            "If rejected, do not retry VSAT/satcom fallback membership, scalar, "
            "IWM gate, or basket-scope isolation on these frozen windows without "
            "new closed forward rows or a different production-visible field."
        )
        if decision != "accept"
        else (
            "Promotion would require moving the isolated fallback helper into "
            "shared space_catalyst_sleeve.py/reporting with parity tests; live "
            "Space slots remain zero until a separate promotion gate."
        ),
        "production_impact": gate["production_impact"],
        "why_not_other_changes": (
            "LLM soft-ranking remains attribution-limited; nearby dual-catalyst "
            "Space scalars and target floors are exhausted; broad ticker expansion "
            "added old-window noise. This tests the specific contamination field "
            "called out by the prior VSAT rejection."
        ),
        "known_risks": [
            "VSAT forward evidence is still one mature event row.",
            "This is an experiment-only replay until a shared default-off helper is promoted.",
            "Live Space slots remain zero/default-off.",
        ],
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "Isolated VSAT satcom trend fallback can add replacement-value "
                "alpha without contaminating official Space peer/basket states."
            ),
            "2_history_check": (
                "exp-20260516-032 and exp-20260516-036 rejected VSAT fallback "
                "membership; exp-20260517-018 rejected risk-scaled VSAT fallback "
                "and explicitly required a field that prevents official peer-basket contamination."
            ),
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Three fixed Space windows; aggregate EV/PnL positive, no "
                "EV-regressed window, max drawdown drift <= 0.5pp, survival > 5%, "
                "fallback signals present."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260518_017_space_vsat_isolated_fallback_pool.py"
            ),
        },
        "related_files": [
            "quant/experiments/exp_20260518_017_space_vsat_isolated_fallback_pool.py",
            "data/experiments/exp-20260518-017/space_vsat_isolated_fallback_pool.json",
            "docs/experiments/logs/exp-20260518-017.json",
            "docs/experiments/tickets/exp-20260518-017.json",
            "docs/experiments/artifacts/exp-20260518-017_space_vsat_isolated_fallback_pool.md",
            "docs/experiment_log.jsonl",
        ],
    }


def _write_artifact(record: dict[str, Any]) -> None:
    gate = record["gate_results"]
    before = record["before_metrics"]
    after = record["after_metrics"]
    lines = [
        f"# {EXPERIMENT_ID} {EXPERIMENT_NAME}",
        "",
        f"- hypothesis: {record['hypothesis']}",
        f"- change_type: {record['change_type']}",
        f"- changed_variable: `{record['changed_variable']}`",
        f"- backtest_protocol: {record['backtest_protocol']}",
        f"- decision: `{record['decision']}`",
        f"- rejection_reason: {record['rejection_reason']}",
        "",
        "## Gate Answers",
        "",
        f"- alpha_hypothesis: {record['protocol_answers']['1_alpha_hypothesis']}",
        f"- prior_similar_experiments: {record['protocol_answers']['2_history_check']}",
        f"- one_independent_variable: {record['protocol_answers']['3_single_causal_variable']}",
        f"- success_criteria: {record['protocol_answers']['4_acceptance_standard']}",
        f"- reproducibility: {record['protocol_answers']['5_reproducibility']}",
        "",
        "## Three-Window Metrics",
        "",
        "| window | before EV | after EV | EV delta | before PnL | after PnL | PnL delta | DD delta | survival delta | trades delta |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, delta in gate["by_window_delta_vs_before"].items():
        before_window = before["windows"][name]
        after_window = after["windows"][name]
        lines.append(
            "| {name} | {bev:.6f} | {aev:.6f} | {dev:.6f} | {bpnl:.2f} | {apnl:.2f} | {dpnl:.2f} | {ddd:.6f} | {dsurv:.6f} | {dtrades} |".format(
                name=name,
                bev=float(before_window.get("expected_value_score") or 0.0),
                aev=float(after_window.get("expected_value_score") or 0.0),
                dev=float(delta.get("expected_value_score") or 0.0),
                bpnl=float(before_window.get("total_pnl") or 0.0),
                apnl=float(after_window.get("total_pnl") or 0.0),
                dpnl=float(delta.get("total_pnl") or 0.0),
                ddd=float(delta.get("max_drawdown_pct") or 0.0),
                dsurv=float(delta.get("survival_rate") or 0.0),
                dtrades=int(delta.get("trade_count") or 0),
            )
        )
    lines.extend(
        [
            "",
            "## Aggregate Delta",
            "",
            f"- expected_value_score_delta: `{record['expected_value_score_delta']}`",
            f"- total_pnl_delta: `{record['total_pnl_delta']}`",
            f"- max_drawdown_delta: `{gate['aggregate_delta_vs_before']['max_drawdown_pct_max']}`",
            f"- min_survival_delta: `{gate['aggregate_delta_vs_before']['min_survival_rate']}`",
            "",
            "## Fallback Audit",
            "",
            "```json",
            json.dumps(_safe(record["fallback_filter_summary"]), indent=2, sort_keys=True),
            "```",
            "",
            "## Gate Detail",
            "",
            "```json",
            json.dumps(_safe(gate["reasons"]), indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "```text",
            "production_impact:",
            f"  shared_policy_changed: {record['production_impact']['shared_policy_changed']}",
            f"  backtester_adapter_changed: {record['production_impact']['backtester_adapter_changed']}",
            f"  run_adapter_changed: {record['production_impact']['run_adapter_changed']}",
            f"  replay_only: {record['production_impact']['replay_only']}",
            f"  parity_test_added: {record['production_impact']['parity_test_added']}",
            "  live_slots: 0",
            "```",
        ]
    )
    DOC_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run() -> dict[str, Any]:
    accepted_stack.BASE.exp008._install_experiment_path_compat()
    field_check = accepted_stack.BASE.exp051._open_position_field_check()
    baseline, base_gates = _run_baseline()
    forward_gate = prior_pool._forward_benchmark_same_theme_satcom_gate()
    variant, fallback_summary = _run_variant(base_gates)
    gate = _gate_variant(
        baseline=baseline,
        variant=variant,
        forward_gate=forward_gate,
        fallback_summary=fallback_summary,
    )
    return _make_record(
        baseline=baseline,
        variant=variant,
        base_gates=base_gates,
        forward_gate=forward_gate,
        fallback_summary=fallback_summary,
        field_check=field_check,
        gate=gate,
    )


def persist(record: dict[str, Any]) -> None:
    _write_json(DATA_DIR / f"{EXPERIMENT_NAME}.json", record)
    _write_json(DOC_LOG, record)
    _write_json(
        DOC_TICKET,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": record["status"],
            "summary": record["hypothesis"],
            "changed_variable": record["changed_variable"],
            "expected_value_score_delta": record["expected_value_score_delta"],
            "total_pnl_delta": record["total_pnl_delta"],
            "rejection_reason": record["rejection_reason"],
            "next_evidence_needed": record["next_evidence_needed"],
        },
    )
    _write_artifact(record)
    _append_jsonl(EXPERIMENT_LOG, record)


def main() -> None:
    record = run()
    persist(record)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": record["experiment_id"],
                    "decision": record["decision"],
                    "expected_value_score_delta": record["expected_value_score_delta"],
                    "total_pnl_delta": record["total_pnl_delta"],
                    "rejection_reason": record["rejection_reason"],
                    "gate_reasons": record["gate_results"]["reasons"],
                    "fallback_counts": record["fallback_filter_summary"]["counts"],
                    "artifact": str(DATA_DIR / f"{EXPERIMENT_NAME}.json"),
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
