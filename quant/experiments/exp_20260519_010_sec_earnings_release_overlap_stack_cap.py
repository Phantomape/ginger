"""exp-20260519-010: SEC earnings-release overlap stack cap.

Alpha search / tail repair on one production-visible default-off paper-sleeve
variable.  The accepted earnings-release SPY T+1 context scalar is profitable,
but stricter tail review shows its positive incremental PnL is slightly too
dependent on the neutral-underreaction overlap stack.  This experiment keeps
the non-overlap earnings-release scalar fixed at 1.10x and sweeps only how much
of that extra 10% applies when the row already has the neutral-underreaction
stack.

Core entries, exits, candidate eligibility, queue capacity, hold days, LLM,
news, and live/default orders are unchanged.

No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260519-010"
STEM = "exp_20260519_010_sec_earnings_release_overlap_stack_cap"
REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from evaluator_gates import evaluate_experiment_promotion_gate  # noqa: E402
import exp_20260519_008_sec_earnings_release_spy_context_notional as prev  # noqa: E402


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
DOC_LOG = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_ARTIFACT = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_sec_earnings_release_overlap_stack_cap.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

TARGET_SCALAR = 1.10
IDENTITY_TARGET_SCALAR = 1.0
OVERLAP_FACTOR_VARIANTS: OrderedDict[str, float] = OrderedDict(
    [
        ("full_overlap_stack_factor_1_00", 1.00),
        ("overlap_stack_factor_0_95", 0.95),
        ("overlap_stack_factor_0_90", 0.90),
        ("overlap_stack_factor_0_75", 0.75),
        ("overlap_stack_factor_0_50", 0.50),
        ("overlap_stack_factor_0_00", 0.00),
    ]
)
FULL_STACK_REFERENCE = "full_overlap_stack_factor_1_00"
_ACTIVE_OVERLAP_FACTOR = 1.0


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00",
        "Z",
    )


def _safe(value: Any) -> Any:
    return prev._safe(value)


def _round(value: Any, ndigits: int = 6) -> float | None:
    return prev._round(value, ndigits)


def _float(value: Any) -> float | None:
    return prev._float(value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    compact = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                rows.append(line)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(compact)
                    replaced = True
                continue
            rows.append(line)
    if not replaced:
        rows.append(compact)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _repo_rel(path: Path | str) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _source_candidate(position: dict[str, Any]) -> dict[str, Any]:
    return prev._source_candidate(position)


def _effective_target_scalar(target_scalar: float, *, overlap: bool) -> float:
    if not overlap:
        return target_scalar
    return 1.0 + (float(target_scalar) - 1.0) * float(_ACTIVE_OVERLAP_FACTOR)


def _notional_for_position(
    position: dict[str, Any],
    *,
    target_scalar: float,
) -> tuple[float, float, str]:
    candidate = _source_candidate(position)
    _, scalar, rule = prev.prev.parent._base_notional_for_position(position)
    rule_parts = [rule]

    overlap = False
    if prev.prev._accepted_neutral_underreaction(candidate):
        overlap = True
        scalar *= prev.prev.ACCEPTED_NEUTRAL_UNDERREACTION_SCALAR
        rule_parts.append("neutral_underreaction_scalar")
        if prev.prev._accepted_market_context(candidate):
            scalar *= prev.prev.ACCEPTED_MARKET_CONTEXT_SCALAR
            rule_parts.append("neutral_underreaction_spy_t1_context_scalar")

    if prev._is_target_candidate(candidate):
        effective_scalar = _effective_target_scalar(target_scalar, overlap=overlap)
        scalar *= effective_scalar
        rule_parts.append("earnings_release_text_spy_t1_context_scalar")
        if overlap:
            rule_parts.append(f"overlap_factor_{_ACTIVE_OVERLAP_FACTOR:.2f}")

    return (
        float(prev.prev.parent.DEFAULT_EVENT_NOTIONAL_USD) * scalar,
        scalar,
        "+".join(rule_parts),
    )


def _with_overlap_factor(factor: float, func):
    global _ACTIVE_OVERLAP_FACTOR
    original_factor = _ACTIVE_OVERLAP_FACTOR
    original_notional = prev._notional_for_position
    _ACTIVE_OVERLAP_FACTOR = float(factor)
    prev._notional_for_position = _notional_for_position
    try:
        return func()
    finally:
        prev._notional_for_position = original_notional
        _ACTIVE_OVERLAP_FACTOR = original_factor


def _run_variant(
    *,
    core_results: dict[str, dict[str, Any]],
    exp100: dict[str, Any],
    target_scalar: float,
    overlap_factor: float,
) -> dict[str, Any]:
    row = _with_overlap_factor(
        overlap_factor,
        lambda: prev._run_variant(
            core_results=core_results,
            exp100=exp100,
            target_scalar=target_scalar,
        ),
    )
    row["earnings_release_overlap_stack_factor"] = overlap_factor
    return row


def _closed_positions_for_factor(
    exp100: dict[str, Any],
    *,
    target_scalar: float,
    overlap_factor: float,
) -> list[dict[str, Any]]:
    return _with_overlap_factor(
        overlap_factor,
        lambda: prev._closed_positions_for_scalar(
            exp100,
            target_scalar=target_scalar,
        ),
    )


def _tail_concentration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    positives = sorted(
        [float(row.get("incremental_pnl") or 0.0) for row in rows if float(row.get("incremental_pnl") or 0.0) > 0],
        reverse=True,
    )
    total = sum(positives)
    if total <= 0:
        return {
            "pnl_top_5_contribution_pct": None,
            "pnl_hhi_concentration": None,
        }
    return {
        "pnl_top_5_contribution_pct": _round(sum(positives[:5]) / total, 4),
        "pnl_hhi_concentration": _round(sum((value / total) ** 2 for value in positives), 4),
    }


def _selection_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    selection = prev.prev._selection_summary(rows)
    selection["adjusted_windows"] = sorted(selection.get("by_window_count") or {})
    selection.update(_tail_concentration(rows))
    return selection


def _variant_summary(row: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    summary = prev._variant_summary(row, baseline)
    summary["earnings_release_overlap_stack_factor"] = row[
        "earnings_release_overlap_stack_factor"
    ]
    return summary


def _tail_aware_gate(
    *,
    summary: dict[str, Any],
    selection: dict[str, Any],
    tail_reference: dict[str, Any],
) -> dict[str, Any]:
    metrics = {
        "aggregate_ev_delta": summary["aggregate_delta"].get(
            "expected_value_score_sum_delta"
        ),
        "aggregate_pnl_delta": summary["aggregate_delta"].get("total_pnl_sum_delta"),
        "windows_ev_improved": summary["ev_positive_windows"],
        "windows_ev_regressed": summary["ev_regressed_windows"],
        "adjusted_trade_count": selection["adjusted_trade_count"],
        "adjusted_windows": selection["adjusted_windows"],
        "max_drawdown_worse_max": summary["max_drawdown_delta_max"],
        "single_ticker_positive_share": selection["max_single_positive_pnl_share"],
        "baseline_single_ticker_positive_share": tail_reference[
            "max_single_positive_pnl_share"
        ],
        "pnl_top_5_contribution_pct": selection["pnl_top_5_contribution_pct"],
        "baseline_pnl_top_5_contribution_pct": tail_reference[
            "pnl_top_5_contribution_pct"
        ],
        "pnl_hhi_concentration": selection["pnl_hhi_concentration"],
        "baseline_pnl_hhi_concentration": tail_reference["pnl_hhi_concentration"],
    }
    gate = evaluate_experiment_promotion_gate(metrics)
    gate["legacy_sec_gate"] = prev.prev._gate(summary, selection)
    gate["tail_reference"] = {
        "variant": FULL_STACK_REFERENCE,
        "max_single_positive_pnl_share": tail_reference[
            "max_single_positive_pnl_share"
        ],
        "pnl_top_5_contribution_pct": tail_reference[
            "pnl_top_5_contribution_pct"
        ],
        "pnl_hhi_concentration": tail_reference["pnl_hhi_concentration"],
    }
    return gate


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} SEC Earnings-Release Overlap Stack Cap",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Single causal variable: `earnings_release_spy_context_neutral_underreaction_overlap_factor`.",
        "",
        "## Sweep",
        "",
        "| Variant | Gate | Factor | dEV | dPnL | EV+ Windows | EV- Windows | Trades | Max DD Worse | Single Share | Top5 | HHI |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        gate = row["tail_aware_gate"]
        metrics = gate["metrics"]
        lines.append(
            "| {variant} | {gate} | {factor:.2f} | {ev:+.4f} | ${pnl:+,.2f} | {wi} | {wr} | {trades} | {dd:+.4%} | {share} | {top5} | {hhi} |".format(
                variant=row["variant_name"],
                gate="PASS" if gate["passed"] else "FAIL",
                factor=row["overlap_factor"],
                ev=metrics["aggregate_ev_delta"],
                pnl=metrics["aggregate_pnl_delta"],
                wi=metrics["windows_ev_improved"],
                wr=metrics["windows_ev_regressed"],
                trades=metrics["adjusted_trade_count"],
                dd=metrics["max_drawdown_worse"],
                share=(
                    f"{row['selection']['max_single_positive_pnl_share']:.2%}"
                    if row["selection"]["max_single_positive_pnl_share"] is not None
                    else "n/a"
                ),
                top5=(
                    f"{row['selection']['pnl_top_5_contribution_pct']:.2%}"
                    if row["selection"]["pnl_top_5_contribution_pct"] is not None
                    else "n/a"
                ),
                hhi=(
                    f"{row['selection']['pnl_hhi_concentration']:.4f}"
                    if row["selection"]["pnl_hhi_concentration"] is not None
                    else "n/a"
                ),
            )
        )
    lines.extend(
        [
            "",
            "## Three-Window Best Variant",
            "",
            "| Window | EV delta | PnL delta | DD delta |",
            "|---|---:|---:|---:|",
        ]
    )
    for label, row in payload["gate"]["legacy_sec_gate"]["by_window"].items():
        lines.append(
            "| {label} | {ev:+.4f} | ${pnl:+,.2f} | {dd:+.4f} |".format(
                label=label,
                ev=row.get("expected_value_score", 0.0),
                pnl=row.get("total_pnl", 0.0),
                dd=row.get("max_drawdown_pct", 0.0),
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            payload["interpretation"],
            "",
            "## Production Impact",
            "",
            "```json",
            json.dumps(_safe(payload["production_impact"]), indent=2, sort_keys=True),
            "```",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def build_payload() -> dict[str, Any]:
    timestamp = _utc_now()
    raw_exp100 = prev.prev.parent._load_exp100()
    current_queue = prev.prev.parent._filter_current_queue(raw_exp100)
    text_rows_by_accession, text_load_stats = prev.prev.parent._load_text_rows()
    exp100 = prev.prev.parent._annotate_language_fields(
        current_queue,
        text_rows_by_accession,
    )
    text_coverage = prev.prev.parent._text_coverage_summary(exp100)
    target_coverage = prev._target_coverage_summary(exp100)
    gate2_fields = prev.prev.parent._gate2_open_position_field_check()

    core_results: dict[str, dict[str, Any]] = {}
    for label, window in prev.prev.parent.WINDOWS.items():
        result = prev.prev.parent._run_core_backtest(window)
        core_results[label] = {
            "metrics": prev.prev.parent._core_metrics(result),
            "equity_curve": prev.prev.parent._normalise_core_curve(result),
        }

    identity = _run_variant(
        core_results=core_results,
        exp100=exp100,
        target_scalar=IDENTITY_TARGET_SCALAR,
        overlap_factor=1.0,
    )

    rows_by_variant: OrderedDict[str, dict[str, Any]] = OrderedDict()
    summaries: OrderedDict[str, dict[str, Any]] = OrderedDict()
    selections: OrderedDict[str, dict[str, Any]] = OrderedDict()
    gates: OrderedDict[str, dict[str, Any]] = OrderedDict()

    for name, factor in OVERLAP_FACTOR_VARIANTS.items():
        row = _run_variant(
            core_results=core_results,
            exp100=exp100,
            target_scalar=TARGET_SCALAR,
            overlap_factor=factor,
        )
        closed_rows = _closed_positions_for_factor(
            exp100,
            target_scalar=TARGET_SCALAR,
            overlap_factor=factor,
        )
        rows_by_variant[name] = row
        summaries[name] = _variant_summary(row, identity)
        selections[name] = _selection_summary(closed_rows)

    tail_reference = selections[FULL_STACK_REFERENCE]
    for name in OVERLAP_FACTOR_VARIANTS:
        gates[name] = _tail_aware_gate(
            summary=summaries[name],
            selection=selections[name],
            tail_reference=tail_reference,
        )

    passing = [name for name, gate in gates.items() if gate["passed"]]
    if passing:
        best_name = max(
            passing,
            key=lambda name: (
                gates[name]["metrics"]["aggregate_ev_delta"] or -999.0,
                gates[name]["metrics"]["aggregate_pnl_delta"] or -999999.0,
                -(selections[name]["max_single_positive_pnl_share"] or 1.0),
                -OVERLAP_FACTOR_VARIANTS[name],
            ),
        )
    else:
        best_name = max(
            OVERLAP_FACTOR_VARIANTS,
            key=lambda name: (
                summaries[name]["aggregate_delta"].get("expected_value_score_sum_delta")
                or -999.0,
                -(selections[name]["max_single_positive_pnl_share"] or 1.0),
            ),
        )

    best_gate = gates[best_name]
    status = "accepted" if best_gate["passed"] else "rejected"
    decision = (
        "accepted_replay_candidate_sec_earnings_release_overlap_stack_cap"
        if best_gate["passed"]
        else "rejected_sec_earnings_release_overlap_stack_cap"
    )
    best_factor = OVERLAP_FACTOR_VARIANTS[best_name]
    interpretation = (
        "The neutral-underreaction overlap stack was the tail-pressure source. "
        f"An overlap factor of {best_factor:.2f} preserved positive aggregate "
        "SEC paper-sleeve EV/PnL versus the identity target scalar while moving "
        "single-ticker and top-five concentration below the stricter tail-aware gate."
        if best_gate["passed"]
        else "No overlap stack factor preserved the earnings-release improvement while clearing the stricter tail-aware gate."
    )

    sweep_summary = []
    for name in OVERLAP_FACTOR_VARIANTS:
        sweep_summary.append(
            {
                "variant_name": name,
                "overlap_factor": OVERLAP_FACTOR_VARIANTS[name],
                "summary": summaries[name],
                "selection": selections[name],
                "tail_aware_gate": gates[name],
            }
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "lane": "alpha_search",
        "hypothesis": (
            "The profitable earnings-release SPY T+1 context scalar is real, but "
            "the extra 10% should be capped when the row already receives the "
            "neutral-underreaction stack; that structural overlap may preserve "
            "broad earnings-release alpha while reducing tail concentration."
        ),
        "change_type": "default_off_paper_allocation_tail_repair",
        "component": "quant/sec_financial_report_event_sleeve.py",
        "changed_variable": (
            "earnings_release_spy_context_neutral_underreaction_overlap_factor"
        ),
        "single_causal_variable": (
            "fraction of the earnings-release SPY-context extra scalar applied "
            "to rows already in the neutral-underreaction overlap stack"
        ),
        "parameters": {
            "target_scalar": TARGET_SCALAR,
            "identity_target_scalar": IDENTITY_TARGET_SCALAR,
            "best_overlap_factor": best_factor,
            "variants": dict(OVERLAP_FACTOR_VARIANTS),
            "tail_reference_variant": FULL_STACK_REFERENCE,
            "source_experiment": "exp-20260519-008",
            "anti_js": "No JavaScript was used.",
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows for core baseline, "
            "plus production SEC financial-report paper-sleeve replay over the "
            "same snapshots."
        ),
        "windows": prev.prev.parent.WINDOWS,
        "candidate_counts_after_current_queue_filter": prev.prev.parent._candidate_counts(exp100),
        "text_load_stats": text_load_stats,
        "text_coverage_summary": text_coverage,
        "target_coverage_summary": target_coverage,
        "gate2_required_fields": gate2_fields,
        "before_metrics": identity["aggregate"],
        "after_metrics": rows_by_variant[best_name]["aggregate"],
        "delta_metrics": {
            "aggregate": best_gate["legacy_sec_gate"]["aggregate_delta"],
            "by_window": best_gate["legacy_sec_gate"]["by_window"],
        },
        "expected_value_score_delta": best_gate["metrics"]["aggregate_ev_delta"],
        "total_pnl_delta": best_gate["metrics"]["aggregate_pnl_delta"],
        "best_variant": best_name,
        "best_overlap_factor": best_factor,
        "sweep_summary": sweep_summary,
        "selection": selections[best_name],
        "gate": best_gate,
        "interpretation": interpretation,
        "rejection_reason": None if best_gate["passed"] else interpretation,
        "next_evidence_needed": (
            "Implement the overlap factor as shared default-off SEC paper-sleeve "
            "policy with parity coverage; live/default orders remain disabled."
            if best_gate["passed"]
            else "Do not retune adjacent earnings-release overlap factors without a new semantic or market discriminator."
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "default_off_paper_only": True,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "live_default_orders_changed": False,
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "capital allocation: cap only the earnings-release SPY-context "
                "extra scalar when it overlaps the existing neutral-underreaction stack."
            ),
            "2_history_check": (
                "exp-20260519-007 rejected broad earnings-release text. "
                "exp-20260519-008 accepted SPY-context earnings-release but had "
                "51.17% max single positive incremental PnL share under stricter tail review."
            ),
            "3_single_causal_variable": (
                "earnings_release_spy_context_neutral_underreaction_overlap_factor"
            ),
            "4_acceptance_standard": (
                "Positive aggregate EV/PnL versus identity scalar, >=2 EV-improved "
                "windows, zero EV-regressed windows, >=9 adjusted trades over >=2 "
                "windows, max drawdown worsening <= 0.5pp, tail concentration under "
                "absolute caps and not worse than the full-stack reference."
            ),
            "5_reproducibility": f".venv\\Scripts\\python.exe quant\\experiments\\{Path(__file__).name}",
        },
        "why_not_other_changes": (
            "Near-high state-surface tests are now anti-repeat, guidance/cut fields "
            "inside the earnings-release target are too sparse, and ticker-specific "
            "guards would overfit the COIN/TSLA contribution."
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(DOC_LOG),
            _repo_rel(DOC_TICKET),
            _repo_rel(DOC_ARTIFACT),
            "docs/experiment_log.jsonl",
        ],
        "anti_js": "No JavaScript was used.",
    }
    return payload


def main() -> None:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(DOC_LOG, payload)
    _write_json(DOC_TICKET, payload)
    DOC_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT.write_text(_artifact_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG_JSONL, payload)
    print(
        json.dumps(
            {
                "anti_js": payload["anti_js"],
                "decision": payload["decision"],
                "experiment_id": payload["experiment_id"],
                "best_variant": payload["best_variant"],
                "best_overlap_factor": payload["best_overlap_factor"],
                "aggregate_ev_delta": payload["expected_value_score_delta"],
                "aggregate_pnl_delta": payload["total_pnl_delta"],
                "max_single_positive_pnl_share": payload["selection"][
                    "max_single_positive_pnl_share"
                ],
                "pnl_top_5_contribution_pct": payload["selection"][
                    "pnl_top_5_contribution_pct"
                ],
                "pnl_hhi_concentration": payload["selection"][
                    "pnl_hhi_concentration"
                ],
                "gate_passed": payload["gate"]["passed"],
                "hard_failures": payload["gate"]["hard_failures"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
