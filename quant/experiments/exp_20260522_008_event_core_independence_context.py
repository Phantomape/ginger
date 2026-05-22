from __future__ import annotations

import copy
import json
import math
import sys
from collections import OrderedDict, defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

import exp_20260522_007_event_governance_503_haircut as exp007

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EXPERIMENT_ID = "exp-20260522-008"
OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "event_core_independence_context.json"
LOG_JSON = OUT_DIR / "event_core_independence_context_log.json"
TICKET_JSON = OUT_DIR / "event_core_independence_context_ticket.json"
ARTIFACT_MD = OUT_DIR / "README.md"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"
OPERATOR_POSITIONS = ROOT / "operator_inputs" / "open_positions.json"

VARIANTS: OrderedDict[str, dict[str, float]] = OrderedDict(
    [
        ("baseline_exp007", {"core_independent_scalar": 1.0}),
        ("core_independent_105", {"core_independent_scalar": 1.05}),
        ("core_independent_110", {"core_independent_scalar": 1.10}),
        ("core_independent_115", {"core_independent_scalar": 1.15}),
    ]
)


def _parse_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text[:10]).date()
    except ValueError:
        return None


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number):
        return default
    return number


def _operator_position_field_check() -> dict[str, Any]:
    if not OPERATOR_POSITIONS.exists():
        return {
            "path": str(OPERATOR_POSITIONS),
            "exists": False,
            "checked_fields": ["entry_date", "target_price"],
            "missing_or_empty": ["__file__"],
            "passed": False,
        }
    payload = json.loads(OPERATOR_POSITIONS.read_text(encoding="utf-8"))
    positions = payload.get("positions", payload if isinstance(payload, list) else [])
    missing: list[str] = []
    for idx, position in enumerate(positions):
        for field in ("entry_date", "target_price"):
            if position.get(field) in (None, ""):
                missing.append(f"positions[{idx}].{field}")
    return {
        "path": str(OPERATOR_POSITIONS),
        "exists": True,
        "checked_fields": ["entry_date", "target_price"],
        "positions_checked": len(positions),
        "missing_or_empty": missing,
        "passed": not missing,
    }


def _accepted_event_scalar_after_exp007(trade: dict[str, Any]) -> float:
    scalar = _safe_float(exp007.base._accepted_event_scalar_after_exp013(trade), 1.0)
    if exp007._is_target_governance_503(trade):
        scalar *= 0.25
    return scalar


def _core_position_index(core_results: dict[str, Any]) -> dict[str, dict[str, list[dict[str, Any]]]]:
    by_window: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for window_name, result in core_results.items():
        tickers: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for trade in result.get("trades", []):
            ticker = str(trade.get("ticker", "")).upper().strip()
            if not ticker:
                continue
            entry = _parse_date(trade.get("entry_date"))
            exit_date = _parse_date(trade.get("exit_date")) or _parse_date(trade.get("date"))
            if entry is None or exit_date is None:
                continue
            tickers[ticker].append(
                {
                    "ticker": ticker,
                    "entry_date": entry,
                    "exit_date": exit_date,
                    "pnl": _safe_float(trade.get("pnl")),
                    "return_pct": _safe_float(trade.get("return_pct")),
                }
            )
        by_window[window_name] = tickers
    return by_window


def _has_core_overlap(
    trade: dict[str, Any],
    window_name: str,
    core_index: dict[str, dict[str, list[dict[str, Any]]]],
) -> tuple[bool, list[dict[str, Any]]]:
    ticker = str(trade.get("ticker", "")).upper().strip()
    entry = _parse_date(trade.get("entry_date"))
    if not ticker or entry is None:
        return False, []
    overlaps = [
        {
            "entry_date": item["entry_date"].isoformat(),
            "exit_date": item["exit_date"].isoformat(),
            "pnl": item["pnl"],
            "return_pct": item["return_pct"],
        }
        for item in core_index.get(window_name, {}).get(ticker, [])
        if item["entry_date"] <= entry <= item["exit_date"]
    ]
    return bool(overlaps), overlaps


def _tagged_event_trades(
    event_trades: dict[str, list[dict[str, Any]]],
    core_results: dict[str, Any],
) -> list[dict[str, Any]]:
    core_index = _core_position_index(core_results)
    rows: list[dict[str, Any]] = []
    for window_name, trades in event_trades.items():
        for trade in trades:
            row = copy.deepcopy(trade)
            overlap, overlaps = _has_core_overlap(row, window_name, core_index)
            row["window"] = window_name
            row["core_overlap"] = overlap
            row["core_overlap_count"] = len(overlaps)
            row["core_overlap_positions"] = overlaps
            row["accepted_exp007_event_scalar"] = _accepted_event_scalar_after_exp007(row)
            rows.append(row)
    return rows


def _scaled_trade(trade: dict[str, Any], variant_name: str, config: dict[str, float]) -> dict[str, Any]:
    parent = exp007._parent()
    row = copy.deepcopy(trade)
    base_scalar = _safe_float(row.get("accepted_exp007_event_scalar"), 1.0)
    context_scalar = _safe_float(config["core_independent_scalar"], 1.0)
    applied_context_scalar = context_scalar if not row.get("core_overlap") else 1.0
    final_scalar = base_scalar * applied_context_scalar
    raw_pnl = _safe_float(row.get("raw_pnl", row.get("pnl")))
    raw_return_pct = _safe_float(row.get("raw_return_pct", row.get("return_pct")))
    base_notional = _safe_float(row.get("base_notional", row.get("notional")), parent.base.EVENT_NOTIONAL)
    base_shares = _safe_float(row.get("base_shares", row.get("shares")))
    row["variant"] = variant_name
    row["event_scalar"] = final_scalar
    row["core_independent_scalar"] = applied_context_scalar
    row["base_notional"] = round(base_notional, 2)
    row["notional"] = round(base_notional * final_scalar, 2)
    row["base_shares"] = base_shares
    row["shares"] = base_shares * final_scalar
    row["state_surface_scalar"] = round(final_scalar, 4)
    row["pnl"] = raw_pnl * final_scalar
    row["return_pct"] = raw_return_pct * final_scalar
    row["sleeve"] = "event_overlay"
    return row


def _aggregate_window_metrics(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "expected_value_score": sum(
            _safe_float(metrics.get("expected_value_score")) for metrics in rows.values()
        ),
        "total_pnl": sum(_safe_float(metrics.get("total_pnl")) for metrics in rows.values()),
        "trade_count": sum(int(metrics.get("trade_count", 0) or 0) for metrics in rows.values()),
        "max_drawdown_pct": max(
            (_safe_float(metrics.get("max_drawdown_pct")) for metrics in rows.values()),
            default=0.0,
        ),
    }


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

    aggregate = _aggregate_window_metrics(window_results)
    return {
        "variant": variant_name,
        "config": config,
        "windows": window_results,
        "aggregate": aggregate,
    }


def _sum_by_key(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {"trade_count": 0, "pnl": 0.0})
    for row in rows:
        value = str(row.get(key))
        grouped[value]["trade_count"] += 1
        grouped[value]["pnl"] += _safe_float(row.get("pnl"))
    return [
        {"value": value, "trade_count": data["trade_count"], "pnl": round(data["pnl"], 2)}
        for value, data in sorted(grouped.items())
    ]


def _selection_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    target = [row for row in rows if not row.get("core_overlap")]
    overlap = [row for row in rows if row.get("core_overlap")]
    target_pnls = [_safe_float(row.get("pnl")) for row in target]
    positives = [value for value in target_pnls if value > 0]
    positive_total = sum(positives)
    positive_by_ticker: dict[str, float] = defaultdict(float)
    for row in target:
        pnl = _safe_float(row.get("pnl"))
        if pnl > 0:
            positive_by_ticker[str(row.get("ticker", "")).upper()] += pnl
    ranked_positive = sorted(positive_by_ticker.values(), reverse=True)
    max_positive_share = (ranked_positive[0] / positive_total) if positive_total else 1.0
    top5_positive_share = (sum(ranked_positive[:5]) / positive_total) if positive_total else 1.0
    return {
        "target_definition": "event candidates with no active core trade on event entry date",
        "target_trade_count": len(target),
        "overlap_trade_count": len(overlap),
        "target_windows_present": sorted({row.get("window") for row in target}),
        "target_ticker_count": len({str(row.get("ticker", "")).upper() for row in target}),
        "target_win_rate": round(sum(1 for value in target_pnls if value > 0) / len(target), 4)
        if target
        else 0.0,
        "target_total_pnl": round(sum(target_pnls), 2),
        "target_max_single_positive_share": round(max_positive_share, 4),
        "target_top5_positive_share": round(top5_positive_share, 4),
        "by_core_overlap": _sum_by_key(rows, "core_overlap"),
        "by_window": _sum_by_key(rows, "window"),
        "by_source": _sum_by_key(rows, "source"),
    }


def _gate_summary(
    parent: Any,
    baseline_metrics: dict[str, dict[str, Any]],
    after_metrics: dict[str, dict[str, Any]],
    selection_summary: dict[str, Any],
) -> dict[str, Any]:
    base_gate = parent.base._gate_summary(baseline_metrics, after_metrics)
    max_drawdown_drift = max(
        (
            _safe_float(after_metrics[label].get("max_drawdown_pct"))
            - _safe_float(baseline_metrics[label].get("max_drawdown_pct"))
        )
        for label in baseline_metrics
    )
    window_count = len(selection_summary["target_windows_present"])
    sample_guard = {
        "target_trade_count": selection_summary["target_trade_count"],
        "target_windows_present": selection_summary["target_windows_present"],
        "target_ticker_count": selection_summary["target_ticker_count"],
        "target_win_rate": selection_summary["target_win_rate"],
        "target_total_pnl": selection_summary["target_total_pnl"],
        "target_max_single_positive_share": selection_summary["target_max_single_positive_share"],
        "target_top5_positive_share": selection_summary["target_top5_positive_share"],
        "min_target_trades": 15,
        "min_windows": 3,
        "min_tickers": 10,
        "min_win_rate": 0.60,
        "max_single_positive_share": 0.35,
        "max_top5_positive_share": 0.70,
        "passed": (
            selection_summary["target_trade_count"] >= 15
            and window_count >= 3
            and selection_summary["target_ticker_count"] >= 10
            and selection_summary["target_win_rate"] >= 0.60
            and selection_summary["target_total_pnl"] > 0
            and selection_summary["target_max_single_positive_share"] <= 0.35
            and selection_summary["target_top5_positive_share"] <= 0.70
        ),
    }
    risk_guard = {
        "max_drawdown_drift": round(max_drawdown_drift, 6),
        "max_allowed_drawdown_drift": 0.02,
        "passed": max_drawdown_drift <= 0.02,
    }
    base_gate["sample_guard"] = sample_guard
    base_gate["sample_guard_passed"] = sample_guard["passed"]
    base_gate["risk_guard"] = risk_guard
    base_gate["risk_guard_passed"] = risk_guard["passed"]
    base_gate["max_window_drawdown_drift"] = round(max_drawdown_drift, 6)
    base_gate["max_drawdown_drift_limit"] = 0.02
    base_gate["passed"] = bool(base_gate.get("passed") and sample_guard["passed"] and risk_guard["passed"])
    return base_gate


def _compact_window_metrics(result: dict[str, Any]) -> dict[str, Any]:
    return exp007.base._compact_metrics_by_window(result)


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


def _artifact_markdown(ticket: dict[str, Any], result: dict[str, Any]) -> str:
    best = result["best_variant"]
    baseline = result["baseline"]
    gate = result["gate4"]
    rows = [
        f"# {EXPERIMENT_ID} event core independence context",
        "",
        "## Hypothesis",
        ticket["hypothesis"],
        "",
        "## Trial accounting",
        "```json",
        json.dumps(ticket["trial_accounting"], indent=2, sort_keys=True),
        "```",
        "",
        "## Baseline",
        f"- variant: {baseline['variant']}",
        f"- aggregate expected_value_score: {baseline['aggregate']['expected_value_score']}",
        f"- aggregate total_pnl: {baseline['aggregate']['total_pnl']}",
        "",
        "## Best replay variant",
        f"- variant: {best['variant']}",
        f"- config: `{json.dumps(best['config'], sort_keys=True)}`",
        f"- aggregate expected_value_score: {best['aggregate']['expected_value_score']}",
        f"- aggregate total_pnl: {best['aggregate']['total_pnl']}",
        f"- gate4 passed: {gate['passed']}",
        f"- decision: {result['decision']}",
        "",
        "## Production impact",
        "```json",
        json.dumps(result["production_impact"], indent=2, sort_keys=True),
        "```",
        "",
        "## Gate 4",
        "```json",
        json.dumps(gate, indent=2, sort_keys=True),
        "```",
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
    exp007._configure_modules()
    parent = exp007._parent()
    operator_check = _operator_position_field_check()
    raw_event_trades, source_coverage, prices = parent.base._load_event_trades()
    event_trades = parent.base._enrich_event_trades(raw_event_trades)
    core_results = {
        label: parent.base._load_core_result(window)
        for label, window in parent.base.WINDOWS.items()
    }
    tagged_trades = _tagged_event_trades(event_trades, core_results)
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
        candidate["variant"]: _gate_summary(
            parent,
            baseline["windows"],
            candidate["windows"],
            selection,
        )
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
        decision = "promising_replay_only_requires_shared_core_position_context"
    else:
        best = max(
            candidates,
            key=lambda item: (
                item["aggregate"]["expected_value_score"] - baseline["aggregate"]["expected_value_score"],
                item["aggregate"]["total_pnl"] - baseline["aggregate"]["total_pnl"],
            ),
        )
        decision = "rejected_failed_gate4"

    gate4 = gates[best["variant"]]
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
        "notes": (
            "No strategy behavior was changed. Positive replay evidence requires a shared "
            "core-position context adapter before promotion."
        ),
    }
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "hypothesis": (
            "Event overlay rows that are independent of active core positions have higher replacement "
            "value than rows duplicating existing core exposure, so a small independent-context notional "
            "scalar may improve expected_value_score without adding noisy tickers."
        ),
        "change_type": "alpha_search",
        "changed_variable": "event_core_independent_notional_scalar",
        "trial_accounting": {
            "trial_family": "event_overlay_replacement_value_core_overlap_context",
            "changed_variable": "event_core_independent_notional_scalar",
            "prior_trial_count": 1,
            "nearby_prior_experiments": [
                "exp-20260521-019_event_attention_persistence_rejected_sparse_repeat_context",
                "exp-20260521-020_event_same_day_core_overlap_signal_rejected_sparse_probe",
                "exp-20260522-007_event_governance_503_haircut_accepted",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "new_core_backtest_overlap_context_after_exp007",
        },
        "why_this_direction": (
            "LLM soft-ranking remains attribution-sparse, broad-market local allocation is blocked by "
            "candidate-universe identity drift, and state-surface allocation/profile retunes face the "
            "strict >10% aggregate EV gate after many nearby trials."
        ),
        "only_changed_one_causal_variable": True,
        "acceptance_criteria": {
            "protocol": "docs/backtesting.md standard three non-overlapping half-year windows",
            "gate4": "aggregate expected_value_score improvement with all standard windows checked",
            "sample_guard": "target >=15 trades, 3 windows, >=10 tickers, win rate >=60%, concentration guarded",
            "production_parity": "replay-only unless a shared production core-position context adapter is added",
        },
    }
    result = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "ticket": ticket,
        "operator_position_field_check": operator_check,
        "selection_summary": selection,
        "baseline": _compact_variant(baseline),
        "best_variant": _compact_variant(best),
        "all_variants": [_compact_variant(variants[name]) for name in VARIANTS],
        "gate4": gate4,
        "delta_vs_baseline": delta,
        "decision": decision,
        "production_impact": production_impact,
    }
    record = {
        "experiment_id": EXPERIMENT_ID,
        "date": result["generated_at"][:10],
        "hypothesis": ticket["hypothesis"],
        "change_type": "alpha_search",
        "changed_variable": ticket["changed_variable"],
        "trial_family": ticket["trial_accounting"]["trial_family"],
        "prior_trial_count": ticket["trial_accounting"]["prior_trial_count"],
        "nearby_prior_experiments": ticket["trial_accounting"]["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": ticket["trial_accounting"]["multiple_testing_risk_bucket"],
        "new_evidence_type": ticket["trial_accounting"]["new_evidence_type"],
        "parameters": {
            "variants": dict(VARIANTS),
            "selection": selection["target_definition"],
        },
        "date_range": "standard_windows_late_strong_mid_weak_old_thin",
        "backtest_protocol": "docs/backtesting.md standard three-window replay",
        "before_metrics": result["baseline"],
        "after_metrics": result["best_variant"],
        "expected_value_score_delta": delta["expected_value_score"],
        "decision": decision,
        "rejection_reason": None
        if decision.startswith("promising")
        else "best candidate failed Gate 4 sample/risk/window checks",
        "next_evidence_needed": (
            "If repeated forward evidence remains positive, add a shared production/backtest "
            "core-position context adapter before any notional promotion."
        ),
        "production_impact": production_impact,
    }
    _write_json(OUT_JSON, result)
    _write_json(LOG_JSON, {"variants": result["all_variants"], "gate4_by_variant": gates})
    _write_json(TICKET_JSON, ticket)
    ARTIFACT_MD.write_text(_artifact_markdown(ticket, result), encoding="utf-8")
    _upsert_experiment_log(record)
    return result


if __name__ == "__main__":
    payload = run()
    print(json.dumps(payload["delta_vs_baseline"], sort_keys=True))
    print(payload["decision"])
