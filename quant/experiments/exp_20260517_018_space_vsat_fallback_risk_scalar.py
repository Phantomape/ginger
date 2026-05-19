from __future__ import annotations

import json
import math
from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import exp_20260516_029_space_dual_catalyst_benchmark_breadth_trend_risk as accepted_stack
import exp_20260516_032_space_forward_benchmark_same_theme_satcom_fallback_pool as prior
import portfolio_engine


EXPERIMENT_ID = "exp-20260517-018"
EXPERIMENT_NAME = "space_vsat_fallback_risk_scalar"
CHANGED_VARIABLE = "space_vsat_forward_benchmark_same_theme_satcom_fallback_risk_scalar"

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

BASE_OFFICIAL_SPACE_TICKERS = prior.BASE_OFFICIAL_SPACE_TICKERS
TARGET_ADDED_TICKERS = ("VSAT",)
EXTENDED_OFFICIAL_SPACE_TICKERS = tuple(
    sorted(set(BASE_OFFICIAL_SPACE_TICKERS).union(TARGET_ADDED_TICKERS))
)
ACCEPTED_BENCHMARK_BREADTH_SCALAR = prior.ACCEPTED_BENCHMARK_BREADTH_SCALAR
SCALARS = (0.125, 0.25, 0.5, 0.75, 1.0)


def _safe(value: Any) -> Any:
    return accepted_stack._safe(value)


@contextmanager
def _risk_scaled_trend_fallback_scope(
    *,
    added_tickers: tuple[str, ...],
    base_tickers: tuple[str, ...],
    risk_scalar: float,
):
    original_size_signals = portfolio_engine.size_signals
    added = {str(ticker).upper() for ticker in added_tickers}
    base = {str(ticker).upper() for ticker in base_tickers}
    counts: Counter[str] = Counter()
    records: list[dict[str, Any]] = []

    def wrapped_size_signals(
        signals: list[dict[str, Any]],
        portfolio_value: float,
        risk_pct: float | None = None,
    ) -> list[dict[str, Any]]:
        signals_by_date: dict[str, list[dict[str, Any]]] = {}
        for signal in signals:
            date_key = str(signal.get("date") or "")[:10]
            signals_by_date.setdefault(date_key, []).append(signal)

        dates_with_base_space_signal = {
            date_key
            for date_key, rows in signals_by_date.items()
            if any(str(row.get("ticker") or "").upper() in base for row in rows)
        }

        kept: list[dict[str, Any]] = []
        kept_keys: set[tuple[str, str, str]] = set()
        for signal in signals:
            ticker = str(signal.get("ticker") or "").upper()
            if ticker not in added:
                kept.append(signal)
                continue

            strategy = str(signal.get("strategy") or "")
            date_key = str(signal.get("date") or "")[:10]
            reason = None
            if strategy != "trend_long":
                reason = "non_trend"
            elif date_key in dates_with_base_space_signal:
                reason = "official_same_day"

            action = "kept" if reason is None else "filtered"
            records.append(
                {
                    "ticker": ticker,
                    "strategy": strategy,
                    "date": date_key,
                    "action": action,
                    "reason": reason or "kept_trend_fallback",
                    "space_iwm_relative_state": signal.get("space_iwm_relative_state"),
                    "space_peer_momentum_state": signal.get("space_peer_momentum_state"),
                    "risk_scalar": risk_scalar,
                }
            )
            if reason is not None:
                counts["filtered_extension_signal"] += 1
                counts[f"filtered_extension_{reason}"] += 1
                counts[f"filtered_{ticker}"] += 1
                counts[f"filtered_{strategy or 'unknown'}"] += 1
                continue

            counts["kept_extension_signal"] += 1
            counts[f"kept_{ticker}"] += 1
            kept_keys.add((ticker, date_key, strategy))
            kept.append(signal)

        sized = original_size_signals(kept, portfolio_value, risk_pct=risk_pct)
        for signal in sized:
            ticker = str(signal.get("ticker") or "").upper()
            strategy = str(signal.get("strategy") or "")
            date_key = str(signal.get("date") or "")[:10]
            if (ticker, date_key, strategy) not in kept_keys:
                continue
            sizing = signal.get("sizing") or {}
            old_shares = int(sizing.get("shares_to_buy") or 0)
            if old_shares <= 0:
                continue
            entry = float(sizing.get("entry_price") or signal.get("entry_price") or 0.0)
            if entry <= 0.0:
                continue
            new_shares = int(math.floor(old_shares * risk_scalar))
            net_risk_per_share = float(sizing.get("net_risk_per_share") or 0.0)
            sizing["space_vsat_fallback_risk_scalar_applied"] = risk_scalar
            sizing["space_vsat_fallback_baseline_shares"] = old_shares
            sizing["space_vsat_fallback_new_shares"] = new_shares
            sizing["shares_to_buy"] = new_shares
            sizing["position_value_usd"] = round(entry * new_shares, 2)
            sizing["position_pct_of_portfolio"] = (
                round((entry * new_shares) / portfolio_value, 4)
                if portfolio_value
                else 0.0
            )
            sizing["risk_amount_usd"] = round(net_risk_per_share * new_shares, 2)
            sizing["risk_pct"] = (
                (net_risk_per_share * new_shares) / portfolio_value
                if portfolio_value
                else 0.0
            )
            signal["space_vsat_fallback_risk_scalar"] = risk_scalar
            signal["space_vsat_fallback_bucket"] = True
            counts["risk_scaled_extension_signal"] += 1
            counts[f"risk_scaled_{ticker}"] += 1
            records.append(
                {
                    "ticker": ticker,
                    "strategy": strategy,
                    "date": date_key,
                    "action": "risk_scaled",
                    "risk_scalar": risk_scalar,
                    "old_shares": old_shares,
                    "new_shares": new_shares,
                }
            )
        return sized

    portfolio_engine.size_signals = wrapped_size_signals
    try:
        yield {"counts": counts, "records": records}
    finally:
        portfolio_engine.size_signals = original_size_signals


def _fallback_filter_summary(scope: dict[str, Any], risk_scalar: float) -> dict[str, Any]:
    records = list(scope["records"])
    by_action: Counter[str] = Counter()
    by_reason: Counter[str] = Counter()
    by_iwm_state: Counter[str] = Counter()
    by_peer_state: Counter[str] = Counter()
    for record in records:
        by_action[str(record.get("action") or "unknown")] += 1
        by_reason[str(record.get("reason") or "unknown")] += 1
        by_iwm_state[str(record.get("space_iwm_relative_state") or "unknown")] += 1
        by_peer_state[str(record.get("space_peer_momentum_state") or "unknown")] += 1
    return {
        "rule": (
            "VSAT is eligible only as a trend_long fallback on dates with no base "
            "official Space signal, then sized by the tested fallback risk scalar."
        ),
        "risk_scalar": risk_scalar,
        "counts": dict(sorted(scope["counts"].items())),
        "records": records,
        "by_action": dict(sorted(by_action.items())),
        "by_reason": dict(sorted(by_reason.items())),
        "by_iwm_state": dict(sorted(by_iwm_state.items())),
        "by_peer_state": dict(sorted(by_peer_state.items())),
    }


def _run_baseline() -> dict[str, Any]:
    gates = prior._collect_gates_with_pool(BASE_OFFICIAL_SPACE_TICKERS)
    result, _ = prior._run_accepted_stack_with_pool(
        label="baseline_exp_20260516_029",
        tickers=BASE_OFFICIAL_SPACE_TICKERS,
        gates=gates,
    )
    return result


def _run_variant(
    *,
    risk_scalar: float,
    gates: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    with prior.prior_pool.exp013._official_space_pool(EXTENDED_OFFICIAL_SPACE_TICKERS):
        with _risk_scaled_trend_fallback_scope(
            added_tickers=TARGET_ADDED_TICKERS,
            base_tickers=BASE_OFFICIAL_SPACE_TICKERS,
            risk_scalar=risk_scalar,
        ) as fallback_scope:
            result = accepted_stack._run_variant(
                benchmark_breadth_scalar=ACCEPTED_BENCHMARK_BREADTH_SCALAR,
                gates=gates,
            )
    result = deepcopy(result)
    result.setdefault("parameters", {})
    result["parameters"].update(
        {
            "label": f"{EXPERIMENT_NAME}_{risk_scalar}",
            "accepted_benchmark_breadth_scalar": ACCEPTED_BENCHMARK_BREADTH_SCALAR,
            "official_space_tickers": list(EXTENDED_OFFICIAL_SPACE_TICKERS),
            "base_official_space_tickers": list(BASE_OFFICIAL_SPACE_TICKERS),
            "added_tickers": list(TARGET_ADDED_TICKERS),
            "space_vsat_forward_benchmark_same_theme_satcom_fallback_risk_scalar": (
                risk_scalar
            ),
        }
    )
    return result, _fallback_filter_summary(fallback_scope, risk_scalar)


def _gate_variant(
    *,
    baseline: dict[str, Any],
    variant: dict[str, Any],
    forward_gate: dict[str, Any],
    fallback_summary: dict[str, Any],
) -> dict[str, Any]:
    gate = prior._build_gate(
        before=baseline,
        after=variant,
        forward_gate=forward_gate,
        fallback_summary=fallback_summary,
    )
    scalar = float(fallback_summary["risk_scalar"])
    gate["risk_scalar"] = scalar
    gate["fallback_filter_summary"] = fallback_summary
    gate["reasons"]["nonzero_risk_scalar"] = scalar > 0.0
    gate["passed"] = bool(gate["passed"] and scalar > 0.0)
    gate["decision"] = "accept" if gate["passed"] else "reject"
    gate["production_impact"] = {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": True,
        "parity_test_added": False,
        "live_slots": 0,
    }
    return gate


def _variant_summary(variant: dict[str, Any], gate: dict[str, Any]) -> dict[str, Any]:
    return {
        "risk_scalar": gate["risk_scalar"],
        "aggregate": variant.get("aggregate", {}),
        "gate": gate,
        "metrics": prior._metrics_summary(variant),
    }


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


def _write_artifact(record: dict[str, Any]) -> None:
    gate = record["gate_results"]
    before = record["before_metrics"]
    after = record["after_metrics"]
    lines = [
        f"# {EXPERIMENT_ID} {EXPERIMENT_NAME}",
        "",
        f"- hypothesis: {record['hypothesis']}",
        f"- change_type: {record['change_type']}",
        f"- changed_variable: {record['changed_variable']}",
        f"- backtest_protocol: {record['backtest_protocol']}",
        f"- selected_scalar: `{record['parameters']['selected_scalar']}`",
        f"- decision: {record['decision']}",
        f"- rejection_reason: {record['rejection_reason']}",
        "",
        "## Gate Answers",
        "",
        "- alpha_hypothesis: VSAT has one mature forward row that beat cash, same-theme, SPY, QQQ, UFO, and ARKX; if it is real alpha, a conservative fallback risk scalar should preserve upside while controlling exp-032 drawdown.",
        "- prior_similar_experiments: exp-20260516-032 rejected full-risk VSAT fallback because old_thin regressed and max drawdown drift breached the guardrail; exp-20260516-036 rejected IWM-gated membership because the selected extension trade vanished and old_thin still regressed.",
        f"- one_independent_variable: {record['changed_variable']}",
        "- success_criteria: docs/backtesting.md fixed three-window Space protocol; aggregate EV/PnL positive, no EV-regressed window, max drawdown drift <= 0.5pp, survival > 5%, fallback signals present.",
        "- reproducibility: .venv\\Scripts\\python.exe quant\\experiments\\exp_20260517_018_space_vsat_fallback_risk_scalar.py",
        "",
        "## Sweep",
        "",
        "| scalar | decision | dEV | dPnL | max DD delta | improved windows | regressed windows | extension trades |",
        "|---:|---|---:|---:|---:|---|---|---:|",
    ]
    for variant in record["variant_summaries"]:
        vg = variant["gate"]
        delta = vg["aggregate_delta_vs_before"]
        lines.append(
            "| {scalar:.4f} | {decision} | {ev:.6f} | {pnl:.2f} | {dd:.6f} | {improved} | {regressed} | {trades} |".format(
                scalar=float(variant["risk_scalar"]),
                decision=vg["decision"],
                ev=float(delta.get("expected_value_score_sum") or 0.0),
                pnl=float(delta.get("total_pnl_sum") or 0.0),
                dd=float(delta.get("max_drawdown_pct_max") or 0.0),
                improved=", ".join(sorted(vg.get("improved_windows") or {})) or "-",
                regressed=", ".join(sorted(vg.get("regressed_windows") or {})) or "-",
                trades=int(vg.get("extension_trade_count") or 0),
            )
        )
    lines.extend(
        [
            "",
            "## Selected Three-Window Metrics",
            "",
            "| window | before EV | after EV | EV delta | before PnL | after PnL | PnL delta | DD delta | survival delta | trades delta |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
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


def _make_record(
    *,
    baseline: dict[str, Any],
    best_variant: dict[str, Any],
    best_gate: dict[str, Any],
    variant_summaries: list[dict[str, Any]],
    field_check: dict[str, Any],
    extended_gates: dict[str, Any],
) -> dict[str, Any]:
    decision = "accept" if best_gate["passed"] else "reject"
    failed = [name for name, ok in best_gate.get("reasons", {}).items() if not ok]
    rejection_reason = None if decision == "accept" else "; ".join(failed)
    selected_scalar = float(best_gate["risk_scalar"])
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(UTC).isoformat(),
        "status": "accepted" if decision == "accept" else "rejected",
        "lane": "alpha_search",
        "hypothesis": (
            "VSAT's mature satcom forward row beat cash, same-theme replacement, "
            "and broad benchmarks, but full-risk fallback admission failed on "
            "drawdown and old_thin. A conservative fallback risk scalar may keep "
            "the candidate-pool edge while limiting Space peer-state noise."
        ),
        "change_summary": (
            "Sweep a risk scalar for prequalified VSAT trend fallback admission "
            "on top of accepted exp-20260516-029."
        ),
        "change_type": "risk_allocation_candidate_pool",
        "component": "quant/experiments",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "parameters": {
            "baseline_stack": "accepted_space_exp_20260516_029",
            "scalars_tested": list(SCALARS),
            "selected_scalar": selected_scalar,
            "accepted_benchmark_breadth_scalar": ACCEPTED_BENCHMARK_BREADTH_SCALAR,
            "base_official_space_tickers": list(BASE_OFFICIAL_SPACE_TICKERS),
            "target_added_tickers": list(TARGET_ADDED_TICKERS),
            "extended_official_space_tickers": list(EXTENDED_OFFICIAL_SPACE_TICKERS),
            "forward_gate": extended_gates.get(
                "forward_benchmark_same_theme_satcom_gate"
            ),
            "anti_js": "No JavaScript was used.",
        },
        "backtest_protocol": "docs/backtesting.md fixed 3-window Space protocol using frozen Space augmented snapshots",
        "date_range": {
            label: spec
            for label, spec in accepted_stack.BASE.exp041.source_diversity_exp.WINDOWS.items()
        },
        "gate2_required_fields": field_check,
        "before_metrics": prior._metrics_summary(baseline),
        "after_metrics": prior._metrics_summary(best_variant),
        "delta_metrics": {
            "aggregate": best_gate["aggregate_delta_vs_before"],
            "by_window": best_gate["by_window_delta_vs_before"],
        },
        "expected_value_score_delta": best_gate["aggregate_delta_vs_before"][
            "expected_value_score_sum"
        ],
        "total_pnl_delta": best_gate["aggregate_delta_vs_before"]["total_pnl_sum"],
        "variant_summaries": variant_summaries,
        "gate_results": best_gate,
        "decision": decision,
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "Do not retry VSAT/satcom fallback scalar or membership on these frozen "
            "windows unless new closed forward rows or a field that prevents "
            "official peer-basket contamination becomes available."
        )
        if decision != "accept"
        else (
            "Promote only through shared space_catalyst_sleeve.py observe-only "
            "metadata and parity tests; live Space slots remain zero."
        ),
        "production_impact": best_gate["production_impact"],
        "why_not_other_changes": (
            "LLM soft-ranking remains attribution-limited, dual-catalyst nearby "
            "scalars and target floors are exhausted, and broad ticker expansion "
            "has added old-window noise. This tests the narrowest remaining "
            "Space candidate-pool/risk-allocation variable with closed forward "
            "evidence."
        ),
        "known_risks": [
            "VSAT forward evidence is one mature event row.",
            "The extended official pool can change peer/basket state even if VSAT risk is small.",
            "Live Space slots remain zero/default-off.",
        ],
        "protocol_answers": {
            "1_alpha_hypothesis": "Risk-scaled VSAT satcom trend fallback may add Space replacement value without exp-032's drawdown.",
            "2_history_check": "exp-20260516-032 rejected full-risk VSAT fallback; exp-20260516-036 rejected IWM-gated VSAT fallback. Neither swept risk-scaled fallback admission.",
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": "Three fixed Space windows; aggregate EV/PnL positive, no EV-regressed window, max drawdown drift <= 0.5pp, survival > 5%, fallback signals present.",
            "5_reproducibility": ".venv\\Scripts\\python.exe quant\\experiments\\exp_20260517_018_space_vsat_fallback_risk_scalar.py",
        },
        "related_files": [
            "quant/experiments/exp_20260517_018_space_vsat_fallback_risk_scalar.py",
            "data/experiments/exp-20260517-018/space_vsat_fallback_risk_scalar.json",
            "experiments/logs/exp-20260517-018.json",
            "experiments/tickets/exp-20260517-018.json",
            "experiments/artifacts/exp-20260517-018_space_vsat_fallback_risk_scalar.md",
            "docs/experiment_log.jsonl",
        ],
    }


def run() -> dict[str, Any]:
    accepted_stack.BASE.exp008._install_experiment_path_compat()
    field_check = accepted_stack.BASE.exp051._open_position_field_check()
    baseline = _run_baseline()
    extended_gates = prior._collect_gates_with_pool(EXTENDED_OFFICIAL_SPACE_TICKERS)
    forward_gate = extended_gates["forward_benchmark_same_theme_satcom_gate"]

    variants: list[dict[str, Any]] = []
    for scalar in SCALARS:
        variant, fallback_summary = _run_variant(
            risk_scalar=scalar,
            gates=extended_gates,
        )
        gate = _gate_variant(
            baseline=baseline,
            variant=variant,
            forward_gate=forward_gate,
            fallback_summary=fallback_summary,
        )
        variants.append(
            {
                "risk_scalar": scalar,
                "variant": variant,
                "gate": gate,
                "summary": _variant_summary(variant, gate),
            }
        )

    accepted = [row for row in variants if row["gate"]["passed"]]
    if accepted:
        best = max(
            accepted,
            key=lambda row: (
                row["gate"]["aggregate_delta_vs_before"]["expected_value_score_sum"],
                row["gate"]["aggregate_delta_vs_before"]["total_pnl_sum"],
            ),
        )
    else:
        best = max(
            variants,
            key=lambda row: (
                row["gate"]["aggregate_delta_vs_before"]["expected_value_score_sum"],
                row["gate"]["aggregate_delta_vs_before"]["total_pnl_sum"],
            ),
        )

    return _make_record(
        baseline=baseline,
        best_variant=best["variant"],
        best_gate=best["gate"],
        variant_summaries=[row["summary"] for row in variants],
        field_check=field_check,
        extended_gates=extended_gates,
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
            "selected_scalar": record["parameters"]["selected_scalar"],
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
                    "selected_scalar": record["parameters"]["selected_scalar"],
                    "expected_value_score_delta": record["expected_value_score_delta"],
                    "total_pnl_delta": record["total_pnl_delta"],
                    "rejection_reason": record["rejection_reason"],
                    "gate_reasons": record["gate_results"]["reasons"],
                    "artifact": str(DATA_DIR / f"{EXPERIMENT_NAME}.json"),
                }
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
