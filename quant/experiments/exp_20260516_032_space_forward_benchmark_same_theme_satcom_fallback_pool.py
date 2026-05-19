from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

import exp_20260516_010_space_forward_cash_satcom_fallback_pool as prior_pool
import exp_20260516_029_space_dual_catalyst_benchmark_breadth_trend_risk as accepted_stack


EXPERIMENT_ID = "exp-20260516-032"
EXPERIMENT_NAME = "space_forward_benchmark_same_theme_satcom_fallback_pool"
CHANGED_VARIABLE = "space_forward_benchmark_same_theme_satcom_fallback_pool_membership"

ROOT = accepted_stack.BASE.ROOT
DATA_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
DOC_LOG = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_ARTIFACT = (
    ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{EXPERIMENT_NAME}.md"
)
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"

SPACE_LEDGER = ROOT / "data" / "paper_sleeves" / "space_catalyst" / "event_state_shadow_ledger.jsonl"

BASE_OFFICIAL_SPACE_TICKERS = tuple(prior_pool.exp008.exp037.OFFICIAL_SPACE_TICKERS)
TARGET_ADDED_TICKERS = ("VSAT",)
EXTENDED_OFFICIAL_SPACE_TICKERS = tuple(
    sorted(set(BASE_OFFICIAL_SPACE_TICKERS).union(TARGET_ADDED_TICKERS))
)

ACCEPTED_BENCHMARK_BREADTH_SCALAR = 1.0125


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _metric(row: dict[str, Any], horizon: str, key: str) -> float | None:
    value = ((row.get("horizons") or {}).get(horizon) or {}).get(key)
    if value is None:
        return None
    return float(value)


def _latest_rows_by_ticker(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        ticker = row.get("ticker")
        if ticker not in TARGET_ADDED_TICKERS:
            continue
        semantic_bucket = row.get("semantic_bucket") or row.get("event_bucket")
        theme_segment = row.get("theme_segment") or row.get("event_subtype")
        if semantic_bucket != "defense_budget_theme":
            continue
        if theme_segment != "satellite_connectivity":
            continue
        current = latest.get(ticker)
        if current is None or str(row.get("asof_date", "")) > str(current.get("asof_date", "")):
            latest[ticker] = row
    return latest


def _forward_benchmark_same_theme_satcom_gate() -> dict[str, Any]:
    rows = _latest_rows_by_ticker(_load_jsonl(SPACE_LEDGER))
    per_ticker: dict[str, Any] = {}
    passed_tickers: list[str] = []
    required = {
        "5d_cash": ("5d", "cash_relative_pnl"),
        "10d_cash": ("10d", "cash_relative_pnl"),
        "10d_same_theme": ("10d", "same_theme_replacement_value"),
        "10d_spy": ("10d", "spy_relative_value"),
        "10d_qqq": ("10d", "qqq_relative_value"),
        "10d_ufo": ("10d", "ufo_relative_value"),
        "10d_arkx": ("10d", "arkx_relative_value"),
    }
    for ticker in TARGET_ADDED_TICKERS:
        row = rows.get(ticker)
        metrics = {
            name: (_metric(row, horizon, key) if row else None)
            for name, (horizon, key) in required.items()
        }
        horizons = (row.get("horizons") if row else {}) or {}
        closed = bool(
            row
            and (horizons.get("5d") or {}).get("status") == "mature"
            and (horizons.get("10d") or {}).get("status") == "mature"
        )
        passed = closed and all(value is not None and value > 0.0 for value in metrics.values())
        per_ticker[ticker] = {
            "passed": bool(passed),
            "asof_date": row.get("asof_date") if row else None,
            "event_date": row.get("event_date") if row else None,
            "source_type": row.get("source_type") if row else None,
            "semantic_bucket": row.get("semantic_bucket") if row else None,
            "theme_segment": row.get("theme_segment") if row else None,
            "metrics": metrics,
        }
        if passed:
            passed_tickers.append(ticker)
    return {
        "description": (
            "Add only satcom fallback tickers with closed positive 5d cash, "
            "10d cash, same-theme replacement, and broad benchmark evidence."
        ),
        "target_added_tickers": list(TARGET_ADDED_TICKERS),
        "passed_tickers": passed_tickers,
        "per_ticker": per_ticker,
        "passed": sorted(passed_tickers) == sorted(TARGET_ADDED_TICKERS),
    }


def _collect_gates_with_pool(tickers: tuple[str, ...]) -> dict[str, Any]:
    with prior_pool.exp013._official_space_pool(tickers):
        gates = accepted_stack.BASE.exp021._collect_gates()
    gates = deepcopy(gates)
    gates["official_space_pool"] = list(tickers)
    gates["forward_benchmark_same_theme_satcom_gate"] = (
        _forward_benchmark_same_theme_satcom_gate()
    )
    return gates


def _run_accepted_stack_with_pool(
    *,
    label: str,
    tickers: tuple[str, ...],
    gates: dict[str, Any],
    added_tickers: tuple[str, ...] = (),
) -> tuple[dict[str, Any], dict[str, Any]]:
    if added_tickers:
        with prior_pool.exp013._official_space_pool(tickers):
            with prior_pool.exp035._trend_fallback_extension_scope(
                added_tickers=added_tickers,
                base_tickers=BASE_OFFICIAL_SPACE_TICKERS,
            ) as fallback_scope:
                result = accepted_stack._run_variant(
                    benchmark_breadth_scalar=ACCEPTED_BENCHMARK_BREADTH_SCALAR,
                    gates=gates,
                )
            fallback_summary = prior_pool.exp035._fallback_filter_summary(
                fallback_scope
            )
    else:
        with prior_pool.exp013._official_space_pool(tickers):
            result = accepted_stack._run_variant(
                benchmark_breadth_scalar=ACCEPTED_BENCHMARK_BREADTH_SCALAR,
                gates=gates,
            )
        fallback_summary = {"counts": {}, "records": [], "by_window": {}}
    result = deepcopy(result)
    result.setdefault("parameters", {})
    result["parameters"].update(
        {
            "label": label,
            "accepted_benchmark_breadth_scalar": ACCEPTED_BENCHMARK_BREADTH_SCALAR,
            "official_space_tickers": list(tickers),
            "added_tickers": list(added_tickers),
            "trend_fallback_scope": "added_tickers_only_when_no_base_space_same_day_signal",
        }
    )
    return result, fallback_summary


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, float]:
    after_drawdown = after.get("max_drawdown_pct", after.get("max_drawdown", 0.0))
    before_drawdown = before.get("max_drawdown_pct", before.get("max_drawdown", 0.0))
    return {
        "total_pnl_delta": float(after.get("total_pnl", 0.0))
        - float(before.get("total_pnl", 0.0)),
        "expected_value_score_delta": float(after.get("expected_value_score", 0.0))
        - float(before.get("expected_value_score", 0.0)),
        "max_drawdown_delta": float(after_drawdown or 0.0)
        - float(before_drawdown or 0.0),
        "trade_count_delta": int(after.get("trade_count", 0))
        - int(before.get("trade_count", 0)),
        "survival_rate_delta": float(after.get("survival_rate", 0.0))
        - float(before.get("survival_rate", 0.0)),
    }


def _aggregate_delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, float]:
    return {
        "total_pnl_delta": float(after.get("total_pnl_sum", 0.0))
        - float(before.get("total_pnl_sum", 0.0)),
        "expected_value_score_delta": float(after.get("expected_value_score_sum", 0.0))
        - float(before.get("expected_value_score_sum", 0.0)),
        "max_drawdown_delta": float(after.get("max_drawdown_pct_max", 0.0))
        - float(before.get("max_drawdown_pct_max", 0.0)),
        "trade_count_delta": int(after.get("trade_count_sum", 0))
        - int(before.get("trade_count_sum", 0)),
        "survival_rate_delta": float(after.get("min_survival_rate", 0.0))
        - float(before.get("min_survival_rate", 0.0)),
    }


def _build_gate(
    *,
    before: dict[str, Any],
    after: dict[str, Any],
    forward_gate: dict[str, Any],
    fallback_summary: dict[str, Any],
) -> dict[str, Any]:
    gate = prior_pool.exp029._gate(
        after,
        before,
        added_tickers=TARGET_ADDED_TICKERS,
    )
    window_deltas = {
        name: _delta(after["by_window"][name]["metrics"], row["metrics"])
        for name, row in sorted(before.get("by_window", {}).items())
    }
    aggregate_delta = _aggregate_delta(
        after.get("aggregate", {}),
        before.get("aggregate", {}),
    )
    window_ev_regressions = [
        name
        for name, values in window_deltas.items()
        if values["expected_value_score_delta"] < -1.0e-9
    ]
    max_window_drawdown_delta = max(
        (values["max_drawdown_delta"] for values in window_deltas.values()),
        default=0.0,
    )
    reasons = dict(gate.get("reasons") or {})
    reasons.update(
        {
            "forward_gate_passed": bool(forward_gate.get("passed")),
            "fallback_signals_present": int(
                (fallback_summary.get("counts") or {}).get("kept_extension_signal")
                or 0
            )
            > 0,
            "no_window_ev_regression": not window_ev_regressions,
            "aggregate_ev_positive": aggregate_delta["expected_value_score_delta"]
            > 0.0,
            "max_window_drawdown_delta_lte_0_5pp": max_window_drawdown_delta <= 0.005,
        }
    )
    passed = bool(
        gate.get("passed")
        and reasons["forward_gate_passed"]
        and reasons["fallback_signals_present"]
        and reasons["no_window_ev_regression"]
        and reasons["aggregate_ev_positive"]
        and reasons["max_window_drawdown_delta_lte_0_5pp"]
    )
    gate.update(
        {
            "passed": passed,
            "decision": "accept" if passed else "reject",
            "aggregate_delta": aggregate_delta,
            "window_deltas": window_deltas,
            "window_ev_regressions": window_ev_regressions,
            "forward_gate": forward_gate,
            "fallback_filter_summary": fallback_summary,
            "reasons": reasons,
            "production_impact": {
                "shared_policy_changed": False,
                "backtester_adapter_changed": False,
                "run_adapter_changed": False,
                "replay_only": True,
                "parity_test_added": False,
            },
        }
    )
    return gate


def _metrics_summary(result: dict[str, Any]) -> dict[str, Any]:
    by_window = result.get("by_window") or {}
    return {
        "aggregate": result.get("aggregate", {}),
        "windows": {
            name: {
                "total_pnl": metrics.get("total_pnl"),
                "strategy_total_return_pct": metrics.get("strategy_total_return_pct"),
                "sharpe_daily": metrics.get("sharpe_daily"),
                "expected_value_score": metrics.get("expected_value_score"),
                "max_drawdown_pct": metrics.get(
                    "max_drawdown_pct",
                    metrics.get("max_drawdown"),
                ),
                "trade_count": metrics.get("trade_count"),
                "signals_generated": metrics.get("signals_generated"),
                "signals_survived": metrics.get("signals_survived"),
                "survival_rate": metrics.get("survival_rate"),
                "worst_trade_pct": metrics.get("worst_trade_pct"),
                "max_consecutive_losses": metrics.get("max_consecutive_losses"),
                "tail_loss_share": metrics.get("tail_loss_share"),
            }
            for name, row in sorted(by_window.items())
            for metrics in [row.get("metrics", {})]
        },
    }


def _make_record(
    *,
    baseline: dict[str, Any],
    after: dict[str, Any],
    field_check: dict[str, Any],
    base_gates: dict[str, Any],
    extended_gates: dict[str, Any],
    gate: dict[str, Any],
) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    before_metrics = _metrics_summary(baseline)
    after_metrics = _metrics_summary(after)
    rejection_reason = None
    if gate["decision"] != "accept":
        failed = [name for name, ok in gate.get("reasons", {}).items() if not ok]
        rejection_reason = "; ".join(failed) or "gate failed"
    return {
        "experiment_id": EXPERIMENT_ID,
        "created_at": now,
        "hypothesis": (
            "A Space candidate-pool expansion should require closed forward evidence "
            "that a satcom fallback ticker beats cash, same-theme replacement, and "
            "broad benchmarks; VSAT passes this stronger gate while IRDM does not."
        ),
        "change_type": "alpha_search",
        "changed_variable": CHANGED_VARIABLE,
        "parameters": {
            "baseline_stack": "accepted_space_exp_20260516_029",
            "accepted_benchmark_breadth_scalar": ACCEPTED_BENCHMARK_BREADTH_SCALAR,
            "base_official_space_tickers": list(BASE_OFFICIAL_SPACE_TICKERS),
            "target_added_tickers": list(TARGET_ADDED_TICKERS),
            "extended_official_space_tickers": list(EXTENDED_OFFICIAL_SPACE_TICKERS),
            "forward_gate": extended_gates.get(
                "forward_benchmark_same_theme_satcom_gate"
            ),
        },
        "alpha_hypothesis": {
            "category": "entry",
            "fits_playbook": True,
            "prior_similar_experiments": [
                "exp-20260516-010 rejected broad IRDM/VSAT satcom fallback due old_thin regression",
                "exp-20260515-035 rejected VSAT-only fallback on an older stack",
                "exp-20260516-031 rejected target-width changes for current dual-catalyst bucket",
            ],
            "one_independent_variable": CHANGED_VARIABLE,
            "success_criteria": (
                "3-window aggregate EV and PnL improve, no window EV regresses, "
                "drawdown drift stays within 0.5pp, survival remains above 5%, "
                "and fallback signals are actually present."
            ),
        },
        "date_range": "standard_3_window_protocol",
        "backtest_protocol": "docs/backtesting.md standard 3-window frozen Space replay",
        "field_check": field_check,
        "baseline_metrics": before_metrics,
        "after_metrics": after_metrics,
        "expected_value_score_delta": gate["aggregate_delta"][
            "expected_value_score_delta"
        ],
        "total_pnl_delta": gate["aggregate_delta"]["total_pnl_delta"],
        "gate": gate,
        "decision": gate["decision"],
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "If rejected, do not retry satcom fallback pool expansion without either "
            "additional closed forward rows or a production-visible quality field "
            "that explains the weak window."
        ),
        "production_impact": gate["production_impact"],
        "why_not_other_changes": (
            "LLM soft-ranking remains attribution-limited, nearby dual-catalyst "
            "risk scalars are already saturated, target-width changes were no-op, "
            "and noisy ticker expansion violates the current Space playbook."
        ),
        "known_risks": [
            "VSAT forward evidence is from one mature event row.",
            "Replay-only experiment is not promoted unless the 3-window gate passes and a shared production-visible helper is added.",
        ],
        "artifacts": {
            "json": str(DATA_DIR / f"{EXPERIMENT_NAME}.json"),
            "doc_log": str(DOC_LOG),
            "doc_ticket": str(DOC_TICKET),
            "doc_artifact": str(DOC_ARTIFACT),
        },
        "base_gate_summary": {
            "benchmark_breadth_targets": base_gates.get("benchmark_breadth_gate", {}).get(
                "target_tickers"
            ),
            "forward_satcom_gate": base_gates.get(
                "forward_benchmark_same_theme_satcom_gate"
            ),
        },
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                lines.append(line)
                continue
            if row.get("experiment_id") != payload.get("experiment_id"):
                lines.append(line)
    lines.append(json.dumps(payload, sort_keys=True))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_artifact(record: dict[str, Any]) -> None:
    gate = record["gate"]
    before = record["baseline_metrics"]
    after = record["after_metrics"]
    lines = [
        f"# {EXPERIMENT_ID} {EXPERIMENT_NAME}",
        "",
        f"- hypothesis: {record['hypothesis']}",
        f"- change_type: {record['change_type']}",
        f"- changed_variable: {record['changed_variable']}",
        f"- backtest_protocol: {record['backtest_protocol']}",
        f"- decision: {record['decision']}",
        f"- rejection_reason: {record['rejection_reason']}",
        "",
        "## Gate Answers",
        "",
        "- alpha_hypothesis: VSAT-only satcom fallback candidate-pool expansion gated by closed cash, same-theme, and benchmark outperformance evidence.",
        "- prior_similar_experiments: exp-20260516-010 broad satcom fallback rejected; exp-20260515-035 older VSAT-only fallback rejected; exp-20260516-031 target-width no-op.",
        f"- one_independent_variable: {record['changed_variable']}",
        "- success_criteria: aggregate EV/PnL improve, no window EV regression, drawdown drift <= 0.5pp, survival >= 5%, fallback signals present.",
        "- reproducibility: script, JSON artifact, doc artifact, ticket, and experiment_log.jsonl record are written by this run.",
        "",
        "## Three-Window Metrics",
        "",
        "| window | before EV | after EV | EV delta | before PnL | after PnL | PnL delta | DD delta | survival delta | trades delta |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, delta in gate["window_deltas"].items():
        before_window = before["windows"][name]
        after_window = after["windows"][name]
        lines.append(
            "| {name} | {bev:.6f} | {aev:.6f} | {dev:.6f} | {bpnl:.2f} | {apnl:.2f} | {dpnl:.2f} | {ddd:.6f} | {dsurv:.6f} | {dtrades} |".format(
                name=name,
                bev=float(before_window.get("expected_value_score") or 0.0),
                aev=float(after_window.get("expected_value_score") or 0.0),
                dev=float(delta["expected_value_score_delta"]),
                bpnl=float(before_window.get("total_pnl") or 0.0),
                apnl=float(after_window.get("total_pnl") or 0.0),
                dpnl=float(delta["total_pnl_delta"]),
                ddd=float(delta["max_drawdown_delta"]),
                dsurv=float(delta["survival_rate_delta"]),
                dtrades=int(delta["trade_count_delta"]),
            )
        )
    lines.extend(
        [
            "",
            "## Aggregate Delta",
            "",
            f"- expected_value_score_delta: {gate['aggregate_delta']['expected_value_score_delta']:.6f}",
            f"- total_pnl_delta: {gate['aggregate_delta']['total_pnl_delta']:.2f}",
            f"- max_drawdown_delta: {gate['aggregate_delta']['max_drawdown_delta']:.6f}",
            f"- trade_count_delta: {gate['aggregate_delta']['trade_count_delta']}",
            "",
            "## Gate Detail",
            "",
            "```json",
            json.dumps(gate, indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "```text",
            "production_impact:",
            f"  shared_policy_changed: {gate['production_impact']['shared_policy_changed']}",
            f"  backtester_adapter_changed: {gate['production_impact']['backtester_adapter_changed']}",
            f"  run_adapter_changed: {gate['production_impact']['run_adapter_changed']}",
            f"  replay_only: {gate['production_impact']['replay_only']}",
            f"  parity_test_added: {gate['production_impact']['parity_test_added']}",
            "```",
        ]
    )
    DOC_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> dict[str, Any]:
    accepted_stack.BASE.exp008._install_experiment_path_compat()
    field_check = accepted_stack.BASE.exp051._open_position_field_check()
    base_gates = _collect_gates_with_pool(BASE_OFFICIAL_SPACE_TICKERS)
    extended_gates = _collect_gates_with_pool(EXTENDED_OFFICIAL_SPACE_TICKERS)
    baseline, _ = _run_accepted_stack_with_pool(
        label="baseline_exp_20260516_029",
        tickers=BASE_OFFICIAL_SPACE_TICKERS,
        gates=base_gates,
    )
    after, fallback_summary = _run_accepted_stack_with_pool(
        label="vsat_forward_benchmark_same_theme_satcom_fallback_pool",
        tickers=EXTENDED_OFFICIAL_SPACE_TICKERS,
        gates=extended_gates,
        added_tickers=TARGET_ADDED_TICKERS,
    )
    gate = _build_gate(
        before=baseline,
        after=after,
        forward_gate=extended_gates["forward_benchmark_same_theme_satcom_gate"],
        fallback_summary=fallback_summary,
    )
    record = _make_record(
        baseline=baseline,
        after=after,
        field_check=field_check,
        base_gates=base_gates,
        extended_gates=extended_gates,
        gate=gate,
    )
    _write_json(DATA_DIR / f"{EXPERIMENT_NAME}.json", record)
    _write_json(DOC_LOG, record)
    _write_json(
        DOC_TICKET,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": record["decision"],
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
    return record


if __name__ == "__main__":
    summary = main()
    print(
        json.dumps(
            {
                "experiment_id": summary["experiment_id"],
                "decision": summary["decision"],
                "expected_value_score_delta": summary["expected_value_score_delta"],
                "total_pnl_delta": summary["total_pnl_delta"],
                "rejection_reason": summary["rejection_reason"],
                "gate_reasons": summary["gate"]["reasons"],
                "artifact": summary["artifacts"]["json"],
            },
            indent=2,
            sort_keys=True,
        )
    )
