from __future__ import annotations

import copy
import json
import math
import sys
from collections import OrderedDict, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260522_008_event_core_independence_context as core_context

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EXPERIMENT_ID = "exp-20260523-005"
OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "event_core_overlap_haircut.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_event_core_overlap_haircut.md"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"

VARIANTS: OrderedDict[str, dict[str, float]] = OrderedDict(
    [
        ("baseline_exp007", {"core_overlap_scalar": 1.0}),
        ("core_overlap_095", {"core_overlap_scalar": 0.95}),
        ("core_overlap_090", {"core_overlap_scalar": 0.90}),
        ("core_overlap_085", {"core_overlap_scalar": 0.85}),
        ("core_overlap_075", {"core_overlap_scalar": 0.75}),
        ("core_overlap_050", {"core_overlap_scalar": 0.50}),
    ]
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number):
        return default
    return number


def _json_default(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=_json_default) + "\n",
        encoding="utf-8",
    )


def _scaled_trade(trade: dict[str, Any], variant_name: str, config: dict[str, float]) -> dict[str, Any]:
    parent = core_context.exp007._parent()
    row = copy.deepcopy(trade)
    base_scalar = _safe_float(row.get("accepted_exp007_event_scalar"), 1.0)
    overlap_scalar = _safe_float(config["core_overlap_scalar"], 1.0)
    applied_overlap_scalar = overlap_scalar if row.get("core_overlap") else 1.0
    final_scalar = base_scalar * applied_overlap_scalar
    raw_pnl = _safe_float(row.get("raw_pnl", row.get("pnl")))
    raw_return_pct = _safe_float(row.get("raw_return_pct", row.get("return_pct")))
    base_notional = _safe_float(row.get("base_notional", row.get("notional")), parent.base.EVENT_NOTIONAL)
    base_shares = _safe_float(row.get("base_shares", row.get("shares")))
    row["variant"] = variant_name
    row["event_scalar"] = round(final_scalar, 6)
    row["core_overlap_scalar"] = applied_overlap_scalar
    row["base_notional"] = round(base_notional, 2)
    row["notional"] = round(base_notional * final_scalar, 2)
    row["base_shares"] = base_shares
    row["shares"] = base_shares * final_scalar
    row["state_surface_scalar"] = round(final_scalar, 4)
    row["pnl"] = raw_pnl * final_scalar
    row["return_pct"] = raw_return_pct * final_scalar
    row["sleeve"] = "event_overlay"
    return row


def _combined_results_for_variant(
    tagged_trades: list[dict[str, Any]],
    variant_name: str,
    config: dict[str, float],
    parent: Any,
    core_results: dict[str, Any],
    prices: dict[str, Any],
) -> dict[str, Any]:
    by_window: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in tagged_trades:
        by_window[trade["window"]].append(_scaled_trade(trade, variant_name, config))

    window_results: dict[str, Any] = {}
    for window_name, window in parent.base.WINDOWS.items():
        trades = by_window.get(window_name, [])
        curve = parent.base._event_equity_curve(
            trades,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        window_results[window_name] = parent.base._combined_metrics(
            core_results[window_name],
            curve,
            trades,
        )
        window_results[window_name]["trades"] = trades

    return {
        "variant": variant_name,
        "config": config,
        "windows": window_results,
        "aggregate": core_context._aggregate_window_metrics(window_results),
    }


def _compact_window_metrics(result: dict[str, Any]) -> dict[str, Any]:
    return core_context.exp007.base._compact_metrics_by_window(result)


def _compact_variant(result: dict[str, Any]) -> dict[str, Any]:
    aggregate = result["aggregate"]
    return {
        "variant": result["variant"],
        "config": result["config"],
        "aggregate": {
            "expected_value_score": round(_safe_float(aggregate.get("expected_value_score")), 6),
            "total_pnl": round(_safe_float(aggregate.get("total_pnl")), 2),
            "trade_count": int(aggregate.get("trade_count", 0)),
            "max_drawdown_pct": round(_safe_float(aggregate.get("max_drawdown_pct")), 6),
        },
        "windows": _compact_window_metrics(result["windows"]),
    }


def _positive_concentration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    positive_by_ticker: dict[str, float] = defaultdict(float)
    for row in rows:
        pnl = _safe_float(row.get("pnl"))
        if pnl > 0:
            positive_by_ticker[str(row.get("ticker", "")).upper()] += pnl
    positive_total = sum(positive_by_ticker.values())
    ranked = sorted(positive_by_ticker.values(), reverse=True)
    return {
        "positive_pnl": round(positive_total, 2),
        "max_single_positive_share": round((ranked[0] / positive_total) if positive_total else 1.0, 6),
        "top5_positive_share": round((sum(ranked[:5]) / positive_total) if positive_total else 1.0, 6),
        "positive_ticker_count": len(positive_by_ticker),
    }


def _selection_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    overlap = [row for row in rows if row.get("core_overlap")]
    independent = [row for row in rows if not row.get("core_overlap")]
    overlap_pnls = [_safe_float(row.get("pnl")) for row in overlap]
    return {
        "target_definition": "event candidates with an active same-ticker core trade on event entry date",
        "target_trade_count": len(overlap),
        "independent_trade_count": len(independent),
        "target_windows_present": sorted({str(row.get("window")) for row in overlap}),
        "target_ticker_count": len({str(row.get("ticker", "")).upper() for row in overlap}),
        "target_win_rate": round(sum(1 for value in overlap_pnls if value > 0) / len(overlap), 4)
        if overlap
        else 0.0,
        "target_total_pnl": round(sum(overlap_pnls), 2),
        "target_concentration": _positive_concentration(overlap),
        "by_core_overlap": core_context._sum_by_key(rows, "core_overlap"),
        "by_window": core_context._sum_by_key(overlap, "window"),
        "by_source": core_context._sum_by_key(overlap, "source"),
    }


def _delta_by_window(
    baseline_metrics: dict[str, dict[str, Any]],
    after_metrics: dict[str, dict[str, Any]],
) -> dict[str, dict[str, float]]:
    keys = [
        "expected_value_score",
        "total_pnl",
        "strategy_total_return_pct",
        "sharpe_daily",
        "max_drawdown_pct",
        "trade_count",
        "win_rate",
        "survival_rate",
    ]
    deltas: dict[str, dict[str, float]] = {}
    for label in baseline_metrics:
        deltas[label] = {
            key: round(_safe_float(after_metrics[label].get(key)) - _safe_float(baseline_metrics[label].get(key)), 6)
            for key in keys
        }
    return deltas


def _gate_summary(
    parent: Any,
    baseline_metrics: dict[str, dict[str, Any]],
    after_metrics: dict[str, dict[str, Any]],
    selection: dict[str, Any],
) -> dict[str, Any]:
    base_gate = parent.base._gate_summary(baseline_metrics, after_metrics)
    window_deltas = _delta_by_window(baseline_metrics, after_metrics)
    regressed_windows = [
        label for label, metrics in window_deltas.items() if metrics["expected_value_score"] < 0
    ]
    improved_windows = [
        label for label, metrics in window_deltas.items() if metrics["expected_value_score"] > 0
    ]
    max_drawdown_drift = max(metrics["max_drawdown_pct"] for metrics in window_deltas.values())
    min_survival_after = min(_safe_float(metrics.get("survival_rate")) for metrics in after_metrics.values())
    concentration = selection["target_concentration"]
    sample_guard = {
        "target_trade_count": selection["target_trade_count"],
        "target_windows_present": selection["target_windows_present"],
        "target_ticker_count": selection["target_ticker_count"],
        "target_win_rate": selection["target_win_rate"],
        "target_total_pnl": selection["target_total_pnl"],
        "max_single_positive_share": concentration["max_single_positive_share"],
        "top5_positive_share": concentration["top5_positive_share"],
        "min_target_trades": 8,
        "min_windows": 2,
        "min_tickers": 4,
        "passed": (
            selection["target_trade_count"] >= 8
            and len(selection["target_windows_present"]) >= 2
            and selection["target_ticker_count"] >= 4
            and concentration["max_single_positive_share"] <= 0.55
            and concentration["top5_positive_share"] <= 0.95
        ),
    }
    metric_guard = {
        "aggregate_ev_delta": round(base_gate["delta"]["aggregate_ev_delta"], 6),
        "aggregate_pnl_delta": round(base_gate["delta"]["aggregate_pnl_delta"], 2),
        "windows_ev_improved": len(improved_windows),
        "windows_ev_regressed": len(regressed_windows),
        "improved_windows": improved_windows,
        "regressed_windows": regressed_windows,
        "passed": (
            base_gate["delta"]["aggregate_ev_delta"] > 0
            and base_gate["delta"]["aggregate_pnl_delta"] > 0
            and len(regressed_windows) == 0
            and len(improved_windows) >= 2
        ),
    }
    risk_guard = {
        "max_drawdown_drift": round(max_drawdown_drift, 6),
        "max_allowed_drawdown_drift": 0.02,
        "min_survival_after": round(min_survival_after, 6),
        "min_survival_required": 0.05,
        "passed": max_drawdown_drift <= 0.02 and min_survival_after >= 0.05,
    }
    base_gate["window_deltas"] = window_deltas
    base_gate["sample_guard"] = sample_guard
    base_gate["metric_guard"] = metric_guard
    base_gate["risk_guard"] = risk_guard
    base_gate["passed"] = bool(sample_guard["passed"] and metric_guard["passed"] and risk_guard["passed"])
    return base_gate


def _artifact_markdown(ticket: dict[str, Any], result: dict[str, Any]) -> str:
    baseline = result["baseline"]
    best = result["best_variant"]
    delta = result["delta_vs_baseline"]
    rows = [
        f"# {EXPERIMENT_ID} Event Core-Overlap Haircut",
        "",
        f"Decision: `{result['decision']}`.",
        "",
        "## Hypothesis",
        ticket["hypothesis"],
        "",
        "## Trial Accounting",
        f"- trial_family: `{ticket['trial_accounting']['trial_family']}`",
        f"- changed_variable: `{ticket['changed_variable']}`",
        f"- prior_trial_count: `{ticket['trial_accounting']['prior_trial_count']}`",
        f"- multiple_testing_risk_bucket: `{ticket['trial_accounting']['multiple_testing_risk_bucket']}`",
        f"- new_evidence_type: `{ticket['trial_accounting']['new_evidence_type']}`",
        "",
        "## Three-Window Result",
        f"- baseline EV: `{baseline['aggregate']['expected_value_score']}`",
        f"- best EV: `{best['aggregate']['expected_value_score']}`",
        f"- EV delta: `{delta['expected_value_score']}`",
        f"- PnL delta: `${delta['total_pnl']}`",
        f"- best variant: `{best['variant']}`",
        "",
        "## Gate 4",
        "```json",
        json.dumps(result["gate4"], indent=2, sort_keys=True),
        "```",
        "",
        "## Production Impact",
        "```json",
        json.dumps(result["production_impact"], indent=2, sort_keys=True),
        "```",
        "",
        "No JavaScript was used.",
        "",
    ]
    return "\n".join(rows)


def _upsert_experiment_log(record: dict[str, Any]) -> None:
    lines: list[str] = []
    if EXPERIMENT_LOG.exists():
        lines = [
            line
            for line in EXPERIMENT_LOG.read_text(encoding="utf-8").splitlines()
            if line.strip()
            and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
            and f'"id": "{EXPERIMENT_ID}"' not in line
        ]
    lines.append(json.dumps(record, sort_keys=True, default=_json_default))
    EXPERIMENT_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run() -> dict[str, Any]:
    core_context.exp007._configure_modules()
    parent = core_context.exp007._parent()
    operator_check = core_context._operator_position_field_check()
    raw_event_trades, source_coverage, prices = parent.base._load_event_trades()
    event_trades = parent.base._enrich_event_trades(raw_event_trades)
    core_results = {
        label: parent.base._load_core_result(window)
        for label, window in parent.base.WINDOWS.items()
    }
    tagged_trades = core_context._tagged_event_trades(event_trades, core_results)
    selection = _selection_summary(
        [_scaled_trade(row, "baseline_exp007", VARIANTS["baseline_exp007"]) for row in tagged_trades]
    )
    variants = {
        name: _combined_results_for_variant(
            tagged_trades,
            name,
            config,
            parent,
            core_results,
            prices,
        )
        for name, config in VARIANTS.items()
    }
    baseline = variants["baseline_exp007"]
    candidates = [variants[name] for name in VARIANTS if name != "baseline_exp007"]
    gates = {
        candidate["variant"]: _gate_summary(parent, baseline["windows"], candidate["windows"], selection)
        for candidate in candidates
    }
    passed = [candidate for candidate in candidates if gates[candidate["variant"]]["passed"]]
    if passed:
        best = max(
            passed,
            key=lambda item: (
                item["aggregate"]["expected_value_score"] - baseline["aggregate"]["expected_value_score"],
                item["aggregate"]["total_pnl"] - baseline["aggregate"]["total_pnl"],
            ),
        )
        decision = "promising_replay_only_requires_shared_core_overlap_adapter"
    else:
        best = max(
            candidates,
            key=lambda item: (
                item["aggregate"]["expected_value_score"] - baseline["aggregate"]["expected_value_score"],
                item["aggregate"]["total_pnl"] - baseline["aggregate"]["total_pnl"],
            ),
        )
        decision = "rejected_event_core_overlap_haircut"
    delta = {
        "expected_value_score": round(
            _safe_float(best["aggregate"].get("expected_value_score"))
            - _safe_float(baseline["aggregate"].get("expected_value_score")),
            6,
        ),
        "total_pnl": round(
            _safe_float(best["aggregate"].get("total_pnl"))
            - _safe_float(baseline["aggregate"].get("total_pnl")),
            2,
        ),
        "trade_count": int(best["aggregate"].get("trade_count", 0))
        - int(baseline["aggregate"].get("trade_count", 0)),
    }
    production_impact = {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": True,
        "parity_test_added": False,
        "production_orders_changed": False,
        "promotion_requirement": (
            "If accepted later, move the core-overlap context into a shared "
            "event_sleeve_bundle/run.py-visible adapter and add parity tests."
        ),
    }
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "hypothesis": (
            "Default-off event overlay rows that duplicate an active same-ticker core position "
            "may have lower incremental replacement value than independent event rows; applying "
            "a bounded paper-notional haircut to overlap rows could improve EV and risk without "
            "changing event eligibility, source queues, ranking, exits, live orders, LLM, or news."
        ),
        "change_type": "alpha_search",
        "changed_variable": "event_core_overlap_notional_scalar",
        "trial_accounting": {
            "trial_family": "event_overlay_replacement_value_core_overlap_context",
            "changed_variable": "event_core_overlap_notional_scalar",
            "prior_trial_count": 2,
            "nearby_prior_experiments": [
                "exp-20260509-002",
                "exp-20260521-020",
                "exp-20260522-008",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "new_overlap_side_of_existing_core_context_field",
        },
        "why_this_direction": (
            "This follows the playbook's event overlay displacement/core-overlap priority while "
            "avoiding data-limited LLM soft-ranking, recently rejected SEC fact/tone slices, "
            "state-surface profile mining, and the failed AI optical candidate-pool family."
        ),
        "only_changed_one_causal_variable": True,
        "acceptance_criteria": {
            "protocol": "docs/backtesting.md standard three non-overlapping half-year windows",
            "gate4": "positive aggregate EV/PnL, at least two EV-improved windows, zero EV-regressed windows, drawdown drift <=2pp, survival >=5%",
            "sample_guard": "target >=8 overlap trades, >=2 windows, >=4 tickers, concentration guarded",
            "production_parity": "replay-only scout unless shared production core-overlap adapter is added",
        },
    }
    result = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "ticket": ticket,
        "operator_position_field_check": operator_check,
        "source_coverage": source_coverage,
        "selection_summary": selection,
        "baseline": _compact_variant(baseline),
        "best_variant": _compact_variant(best),
        "all_variants": [_compact_variant(variants[name]) for name in VARIANTS],
        "gate4": gates[best["variant"]],
        "delta_vs_baseline": delta,
        "decision": decision,
        "production_impact": production_impact,
    }
    record = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": result["generated_at"],
        "status": decision,
        "hypothesis": ticket["hypothesis"],
        "change_summary": "Sweep a bounded default-off event paper-notional haircut for rows with active same-ticker core overlap.",
        "change_type": "alpha_search",
        "mechanism_family": "external_event_satellite_overlay_allocation",
        "trial_family": ticket["trial_accounting"]["trial_family"],
        "trial_variant_id": best["variant"],
        "changed_variable": ticket["changed_variable"],
        "prior_trial_count": ticket["trial_accounting"]["prior_trial_count"],
        "nearby_prior_experiments": ticket["trial_accounting"]["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": ticket["trial_accounting"]["multiple_testing_risk_bucket"],
        "new_evidence_type": ticket["trial_accounting"]["new_evidence_type"],
        "component": "offline_default_off_event_overlay_replay",
        "parameters": {
            "anti_js": "No JavaScript was used.",
            "variants": dict(VARIANTS),
            "locked_variables": [
                "core universe",
                "core signal generation",
                "core ranking",
                "core sizing",
                "core exits",
                "event source definitions",
                "event source capacity",
                "event holding period",
                "accepted event 5.03 haircut",
                "LLM prompt and replay",
                "news veto",
                "production orders",
            ],
        },
        "date_range": {
            "late_strong": "2025-10-23 -> 2026-04-21",
            "mid_weak": "2025-04-23 -> 2025-10-22",
            "old_thin": "2024-10-02 -> 2025-04-22",
        },
        "backtest_protocol": "docs/backtesting.md canonical fixed-snapshot three-window replay plus default-off event paper overlay accounting",
        "before_metrics": result["baseline"],
        "after_metrics": result["best_variant"],
        "delta_metrics": {
            "aggregate_delta": delta,
            "gate4": result["gate4"],
        },
        "expected_value_score_delta": delta["expected_value_score"],
        "total_pnl_delta": delta["total_pnl"],
        "gate1": {
            "baseline_artifact": str(OUT_JSON),
            "baseline_metrics_readable": True,
            "baseline_protocol": "docs/backtesting.md standard three non-overlapping windows",
        },
        "gate2": {
            "passed": bool(operator_check.get("passed")),
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "event trade entry_date/ticker",
                "core backtest trade entry_date/exit_date/ticker",
            ],
            "open_positions": operator_check,
        },
        "gate3": {
            "new_filter_added": False,
            "minimum_after_survival_rate": result["gate4"]["risk_guard"]["min_survival_after"],
            "passed": result["gate4"]["risk_guard"]["min_survival_after"] >= 0.05,
        },
        "gate4": result["gate4"],
        "decision": decision,
        "rejection_reason": None
        if decision.startswith("promising")
        else "No tested core-overlap haircut cleared the three-window EV/PnL/no-regression gate.",
        "next_evidence_needed": (
            "Do not retry nearby core-overlap event scalars on the frozen sample without new "
            "closed forward rows or a shared production-visible overlap/displacement adapter."
        ),
        "production_impact": production_impact,
        "related_files": [
            str(Path("quant/experiments") / f"{Path(__file__).stem}.py"),
            str(OUT_JSON.relative_to(ROOT)),
            str(LOG_JSON.relative_to(ROOT)),
            str(TICKET_JSON.relative_to(ROOT)),
            str(ARTIFACT_MD.relative_to(ROOT)),
            "docs/experiment_log.jsonl",
        ],
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
        },
        "why_not_other_changes": ticket["why_this_direction"],
    }
    _write_json(OUT_JSON, result)
    _write_json(LOG_JSON, record)
    _write_json(TICKET_JSON, ticket)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact_markdown(ticket, result), encoding="utf-8")
    _upsert_experiment_log(record)
    return result


if __name__ == "__main__":
    payload = run()
    print(json.dumps(payload["delta_vs_baseline"], sort_keys=True))
    print(payload["decision"])
