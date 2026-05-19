from __future__ import annotations

import json
from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import exp_20260516_029_space_dual_catalyst_benchmark_breadth_trend_risk as accepted_stack
import exp_20260516_032_space_forward_benchmark_same_theme_satcom_fallback_pool as prior
import portfolio_engine


EXPERIMENT_ID = "exp-20260516-036"
EXPERIMENT_NAME = "space_vsat_iwm_leader_satcom_fallback_pool"
CHANGED_VARIABLE = "space_forward_benchmark_same_theme_satcom_iwm_leader_fallback_pool_membership"

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
ACCEPTED_BENCHMARK_BREADTH_SCALAR = 1.0125
REQUIRED_IWM_STATE = "smallcap_leader"


@contextmanager
def _iwm_leader_trend_fallback_scope(
    *,
    added_tickers: tuple[str, ...],
    base_tickers: tuple[str, ...],
):
    """Keep added Space signals only as trend fallback during small-cap risk-on tape."""
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
        for signal in signals:
            ticker = str(signal.get("ticker") or "").upper()
            if ticker not in added:
                kept.append(signal)
                continue

            strategy = str(signal.get("strategy") or "")
            date_key = str(signal.get("date") or "")[:10]
            iwm_state = signal.get("space_iwm_relative_state")
            peer_state = signal.get("space_peer_momentum_state")
            reason = None
            if strategy != "trend_long":
                reason = "non_trend"
            elif date_key in dates_with_base_space_signal:
                reason = "official_same_day"
            elif iwm_state != REQUIRED_IWM_STATE:
                reason = "iwm_state_not_smallcap_leader"

            action = "kept" if reason is None else "filtered"
            records.append(
                {
                    "ticker": ticker,
                    "strategy": strategy,
                    "date": date_key,
                    "action": action,
                    "reason": reason or "kept_iwm_leader_trend_fallback",
                    "space_iwm_relative_state": iwm_state,
                    "space_peer_momentum_state": peer_state,
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
            counts[f"kept_{iwm_state or 'unknown_iwm_state'}"] += 1
            kept.append(signal)

        return original_size_signals(kept, portfolio_value, risk_pct=risk_pct)

    portfolio_engine.size_signals = wrapped_size_signals
    try:
        yield {"counts": counts, "records": records}
    finally:
        portfolio_engine.size_signals = original_size_signals


def _fallback_filter_summary(scope: dict[str, Any]) -> dict[str, Any]:
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
            "Added satcom tickers are allowed only for trend_long signals on "
            "dates with no base official Space signal and IWM 20d momentum "
            "above SPY 20d momentum."
        ),
        "required_iwm_relative_state": REQUIRED_IWM_STATE,
        "counts": dict(sorted(scope["counts"].items())),
        "records": records,
        "by_action": dict(sorted(by_action.items())),
        "by_reason": dict(sorted(by_reason.items())),
        "by_iwm_state": dict(sorted(by_iwm_state.items())),
        "by_peer_state": dict(sorted(by_peer_state.items())),
    }


def _run_baseline() -> tuple[dict[str, Any], dict[str, Any]]:
    gates = prior._collect_gates_with_pool(BASE_OFFICIAL_SPACE_TICKERS)
    result, fallback_summary = prior._run_accepted_stack_with_pool(
        label="baseline_exp_20260516_029",
        tickers=BASE_OFFICIAL_SPACE_TICKERS,
        gates=gates,
    )
    return result, fallback_summary


def _run_after() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    gates = prior._collect_gates_with_pool(EXTENDED_OFFICIAL_SPACE_TICKERS)
    with prior.prior_pool.exp013._official_space_pool(EXTENDED_OFFICIAL_SPACE_TICKERS):
        with _iwm_leader_trend_fallback_scope(
            added_tickers=TARGET_ADDED_TICKERS,
            base_tickers=BASE_OFFICIAL_SPACE_TICKERS,
        ) as fallback_scope:
            result = accepted_stack._run_variant(
                benchmark_breadth_scalar=ACCEPTED_BENCHMARK_BREADTH_SCALAR,
                gates=gates,
            )
    result = deepcopy(result)
    result.setdefault("parameters", {})
    result["parameters"].update(
        {
            "label": EXPERIMENT_NAME,
            "accepted_benchmark_breadth_scalar": ACCEPTED_BENCHMARK_BREADTH_SCALAR,
            "official_space_tickers": list(EXTENDED_OFFICIAL_SPACE_TICKERS),
            "added_tickers": list(TARGET_ADDED_TICKERS),
            "required_iwm_relative_state": REQUIRED_IWM_STATE,
        }
    )
    return result, _fallback_filter_summary(fallback_scope), gates


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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
        "- alpha_hypothesis: VSAT satcom fallback pool expansion should require both closed forward benchmark/same-theme evidence and IWM-led small-cap risk appetite.",
        "- prior_similar_experiments: exp-20260516-032 rejected VSAT fallback without IWM gating due late drawdown and old_thin EV regression; exp-20260516-015 accepted IWM-leader confirmation inside dual-catalyst Space trend allocation.",
        f"- one_independent_variable: {record['changed_variable']}",
        "- success_criteria: aggregate EV/PnL improve, no window EV regression, drawdown drift <= 0.5pp, survival >= 5%, and fallback signals/trades are present.",
        "- reproducibility: run this script with .venv\\Scripts\\python.exe; it writes JSON, doc log, ticket, artifact, and experiment_log.jsonl record.",
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
            "## Fallback State Audit",
            "",
            "```json",
            json.dumps(gate["fallback_filter_summary"], indent=2, sort_keys=True),
            "```",
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
            "  live_slots: 0",
            "```",
        ]
    )
    DOC_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT.write_text("\n".join(lines) + "\n", encoding="utf-8")


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
    before_metrics = prior._metrics_summary(baseline)
    after_metrics = prior._metrics_summary(after)
    rejection_reason = None
    if gate["decision"] != "accept":
        failed = [name for name, ok in gate.get("reasons", {}).items() if not ok]
        rejection_reason = "; ".join(failed) or "gate failed"
    return {
        "experiment_id": EXPERIMENT_ID,
        "created_at": now,
        "hypothesis": (
            "VSAT satcom fallback expansion should only be eligible when closed "
            "forward evidence beats cash, same-theme replacement, and broad "
            "benchmarks, and when IWM 20d momentum leads SPY. This tests whether "
            "small-cap risk appetite removes the drawdown and old-window noise "
            "from exp-20260516-032 without adding broad ticker noise."
        ),
        "change_type": "alpha_search",
        "changed_variable": CHANGED_VARIABLE,
        "parameters": {
            "baseline_stack": "accepted_space_exp_20260516_029",
            "accepted_benchmark_breadth_scalar": ACCEPTED_BENCHMARK_BREADTH_SCALAR,
            "base_official_space_tickers": list(BASE_OFFICIAL_SPACE_TICKERS),
            "target_added_tickers": list(TARGET_ADDED_TICKERS),
            "extended_official_space_tickers": list(EXTENDED_OFFICIAL_SPACE_TICKERS),
            "required_iwm_relative_state": REQUIRED_IWM_STATE,
            "forward_gate": extended_gates.get(
                "forward_benchmark_same_theme_satcom_gate"
            ),
            "anti_js": "No JavaScript was used.",
        },
        "alpha_hypothesis": {
            "category": "entry",
            "fits_playbook": True,
            "prior_similar_experiments": [
                "exp-20260516-032 rejected VSAT fallback without IWM gating despite aggregate EV because old_thin regressed and late drawdown drift breached the guardrail.",
                "exp-20260516-015 accepted IWM-leader confirmation inside the dual-catalyst Space trend stack.",
                "exp-20260515-035 rejected older VSAT-only fallback on a weaker stack.",
            ],
            "one_independent_variable": CHANGED_VARIABLE,
            "success_criteria": (
                "3-window aggregate EV and PnL improve, no window EV regresses, "
                "drawdown drift stays within 0.5pp, survival remains above 5%, "
                "and fallback signals/trades are actually present."
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
            "If rejected, do not retry VSAT satcom fallback pool expansion without "
            "additional closed forward rows or a production-visible field that "
            "directly explains the weak window/drawdown behavior."
        ),
        "production_impact": gate["production_impact"],
        "why_not_other_changes": (
            "LLM soft-ranking remains attribution-limited, nearby dual-catalyst "
            "risk scalars and target-width changes are saturated, and broad Space "
            "pool expansion already added old-window noise. This tests one "
            "production-visible risk-appetite membership condition on the only "
            "satcom ticker with closed forward benchmark/same-theme evidence."
        ),
        "known_risks": [
            "VSAT forward evidence is still from one mature event row.",
            "Replay windows predate live Space slots; live slots remain zero unless a separate promotion is later approved.",
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


def main() -> dict[str, Any]:
    accepted_stack.BASE.exp008._install_experiment_path_compat()
    field_check = accepted_stack.BASE.exp051._open_position_field_check()
    base_gates = prior._collect_gates_with_pool(BASE_OFFICIAL_SPACE_TICKERS)
    baseline, _ = _run_baseline()
    after, fallback_summary, extended_gates = _run_after()
    gate = prior._build_gate(
        before=baseline,
        after=after,
        forward_gate=extended_gates["forward_benchmark_same_theme_satcom_gate"],
        fallback_summary=fallback_summary,
    )
    gate["fallback_filter_summary"] = fallback_summary
    gate["production_impact"] = {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": True,
        "parity_test_added": False,
        "live_slots": 0,
    }
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
                "fallback_counts": summary["gate"]["fallback_filter_summary"]["counts"],
                "artifact": summary["artifacts"]["json"],
            },
            indent=2,
            sort_keys=True,
        )
    )
