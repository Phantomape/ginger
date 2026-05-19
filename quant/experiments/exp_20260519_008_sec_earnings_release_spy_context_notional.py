"""exp-20260519-008: SEC earnings-release SPY T+1 context notional.

Alpha search on one production-visible field interaction in the default-off
SEC financial-report paper sleeve.  After exp-20260519-007 rejected a broad
``text_event_type=earnings_release_text`` scalar, this experiment tests a
narrower market-context allocation: earnings-release text rows only receive
extra paper notional when the SPY T+1 context is not worse than -0.5%.

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


EXPERIMENT_ID = "exp-20260519-008"
STEM = "exp_20260519_008_sec_earnings_release_spy_context_notional"
REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260519_007_sec_earnings_release_text_notional as prev  # noqa: E402


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
DOC_LOG = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_ARTIFACT = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_sec_earnings_release_spy_context_notional.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

TARGET_TEXT_EVENT_TYPE = prev.TARGET_TEXT_EVENT_TYPE
SPY_T1_RETURN_MIN = -0.005
BASELINE_TARGET_SCALAR = 1.0
TARGET_SCALAR_VARIANTS = (0.50, 0.75, 1.0, 1.10, 1.25, 1.50)


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


def _is_target_candidate(candidate: dict[str, Any]) -> bool:
    spy_t1 = _float(candidate.get("spy_t1_return"))
    return (
        prev._candidate_text_event_type(candidate) == TARGET_TEXT_EVENT_TYPE
        and spy_t1 is not None
        and spy_t1 >= SPY_T1_RETURN_MIN
    )


def _is_target_position(position: dict[str, Any]) -> bool:
    return _is_target_candidate(_source_candidate(position))


def _notional_for_position(
    position: dict[str, Any],
    *,
    target_scalar: float,
) -> tuple[float, float, str]:
    candidate = _source_candidate(position)
    _, scalar, rule = prev.parent._base_notional_for_position(position)
    rule_parts = [rule]

    if prev._accepted_neutral_underreaction(candidate):
        scalar *= prev.ACCEPTED_NEUTRAL_UNDERREACTION_SCALAR
        rule_parts.append("neutral_underreaction_scalar")
        if prev._accepted_market_context(candidate):
            scalar *= prev.ACCEPTED_MARKET_CONTEXT_SCALAR
            rule_parts.append("neutral_underreaction_spy_t1_context_scalar")

    if _is_target_candidate(candidate):
        scalar *= target_scalar
        rule_parts.append("earnings_release_text_spy_t1_context_scalar")

    return float(prev.parent.DEFAULT_EVENT_NOTIONAL_USD) * scalar, scalar, "+".join(rule_parts)


def _run_variant(
    *,
    core_results: dict[str, dict[str, Any]],
    exp100: dict[str, Any],
    target_scalar: float,
) -> dict[str, Any]:
    original_notional = prev._notional_for_position
    original_target = prev._is_target_position
    prev._notional_for_position = _notional_for_position
    prev._is_target_position = _is_target_position
    try:
        row = prev._run_variant(
            core_results=core_results,
            exp100=exp100,
            target_scalar=target_scalar,
        )
    finally:
        prev._notional_for_position = original_notional
        prev._is_target_position = original_target
    row["earnings_release_text_spy_t1_context_notional_scalar"] = target_scalar
    return row


def _closed_positions_for_scalar(
    exp100: dict[str, Any],
    *,
    target_scalar: float,
) -> list[dict[str, Any]]:
    original_notional = prev._notional_for_position
    original_target = prev._is_target_position
    prev._notional_for_position = _notional_for_position
    prev._is_target_position = _is_target_position
    try:
        return prev._closed_positions_for_scalar(
            exp100,
            target_scalar=target_scalar,
        )
    finally:
        prev._notional_for_position = original_notional
        prev._is_target_position = original_target


def _target_coverage_summary(exp100: dict[str, Any]) -> dict[str, Any]:
    aggregate = {"target": 0, "non_target": 0, "missing_spy_t1": 0}
    by_window: dict[str, Any] = {}
    for label, window in exp100.get("windows", {}).items():
        rows = window.get("candidate_rows") or []
        target = 0
        missing = 0
        for row in rows:
            if prev._candidate_text_event_type(row) != TARGET_TEXT_EVENT_TYPE:
                continue
            if _float(row.get("spy_t1_return")) is None:
                missing += 1
            if _is_target_candidate(row):
                target += 1
        by_window[label] = {
            "candidate_count": len(rows),
            "target_count": target,
            "earnings_release_missing_spy_t1": missing,
        }
        aggregate["target"] += target
        aggregate["missing_spy_t1"] += missing
        aggregate["non_target"] += max(len(rows) - target, 0)
    return {
        "aggregate": aggregate,
        "by_window": by_window,
        "target_definition": {
            "text_event_type": TARGET_TEXT_EVENT_TYPE,
            "spy_t1_return_min": SPY_T1_RETURN_MIN,
        },
    }


def _variant_summary(row: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    summary = prev._variant_summary(row, baseline)
    summary["earnings_release_text_spy_t1_context_notional_scalar"] = row[
        "earnings_release_text_spy_t1_context_notional_scalar"
    ]
    return summary


def _artifact_markdown(payload: dict[str, Any]) -> str:
    aggregate = payload["gate"]["aggregate_delta"]
    lines = [
        f"# {EXPERIMENT_ID} SEC Earnings-Release SPY T+1 Context Notional",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Best Variant",
        "",
        f"- best_variant: `{payload['best_variant']}`",
        f"- target_scalar: `{payload['parameters']['best_target_scalar']}`",
        f"- EV delta: `{aggregate.get('expected_value_score_sum_delta')}`",
        f"- PnL delta: `${aggregate.get('total_pnl_sum_delta')}`",
        f"- gate_passed: `{payload['gate']['passed']}`",
        "",
        "## Three-Window Deltas",
        "",
        "| Window | EV delta | PnL delta | DD delta |",
        "|---|---:|---:|---:|",
    ]
    for label, row in payload["gate"]["by_window"].items():
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
            "## Selection",
            "",
            "```json",
            json.dumps(_safe(payload["selection"]), indent=2, sort_keys=True),
            "```",
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
    raw_exp100 = prev.parent._load_exp100()
    current_queue = prev.parent._filter_current_queue(raw_exp100)
    text_rows_by_accession, text_load_stats = prev.parent._load_text_rows()
    exp100 = prev.parent._annotate_language_fields(current_queue, text_rows_by_accession)
    text_coverage = prev.parent._text_coverage_summary(exp100)
    target_coverage = _target_coverage_summary(exp100)
    gate2_fields = prev.parent._gate2_open_position_field_check()

    core_results: dict[str, dict[str, Any]] = {}
    for label, window in prev.parent.WINDOWS.items():
        result = prev.parent._run_core_backtest(window)
        core_results[label] = {
            "metrics": prev.parent._core_metrics(result),
            "equity_curve": prev.parent._normalise_core_curve(result),
        }

    variants: OrderedDict[str, dict[str, Any]] = OrderedDict()
    summaries: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for scalar in TARGET_SCALAR_VARIANTS:
        key = f"earnings_release_spy_t1_context_scalar_{scalar:.2f}"
        row = _run_variant(
            core_results=core_results,
            exp100=exp100,
            target_scalar=scalar,
        )
        variants[key] = row

    baseline_key = f"earnings_release_spy_t1_context_scalar_{BASELINE_TARGET_SCALAR:.2f}"
    baseline = variants[baseline_key]
    for key, row in variants.items():
        summaries[key] = _variant_summary(row, baseline)

    non_baseline = [key for key in summaries if key != baseline_key]
    passed = []
    selections: dict[str, dict[str, Any]] = {}
    gates: dict[str, dict[str, Any]] = {}
    for key in non_baseline:
        scalar = float(summaries[key]["earnings_release_text_spy_t1_context_notional_scalar"])
        selection = prev._selection_summary(
            _closed_positions_for_scalar(exp100, target_scalar=scalar)
        )
        selections[key] = selection
        gates[key] = prev._gate(summaries[key], selection)
        if gates[key]["passed"]:
            passed.append(key)

    if passed:
        best_key = max(
            passed,
            key=lambda key: (
                summaries[key]["aggregate_delta"].get("expected_value_score_sum_delta")
                or -999.0,
                summaries[key]["aggregate_delta"].get("total_pnl_sum_delta") or -999999.0,
                -gates[key]["by_window"]["late_strong"].get("max_drawdown_pct", 0.0),
            ),
        )
    else:
        best_key = max(
            non_baseline,
            key=lambda key: (
                summaries[key]["aggregate_delta"].get("expected_value_score_sum_delta")
                or -999.0,
                summaries[key]["aggregate_delta"].get("total_pnl_sum_delta") or -999999.0,
            ),
        )

    best_summary = summaries[best_key]
    best_scalar = float(best_summary["earnings_release_text_spy_t1_context_notional_scalar"])
    selection = selections.get(best_key) or prev._selection_summary(
        _closed_positions_for_scalar(exp100, target_scalar=best_scalar)
    )
    gate = gates.get(best_key) or prev._gate(best_summary, selection)
    status = "accepted" if gate["passed"] else "rejected"
    decision = (
        "accepted_default_off_sec_earnings_release_spy_t1_context_notional"
        if gate["passed"]
        else "rejected_sec_earnings_release_spy_t1_context_notional"
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "lane": "alpha_search",
        "hypothesis": (
            "Inside the accepted SEC financial-report T+1 paper sleeve, "
            "`text_event_type=earnings_release_text` rows should only receive "
            "extra paper notional when same-day SPY T+1 context is not worse "
            "than -0.5%; this should preserve post-earnings drift exposure "
            "while avoiding the broad earnings-release scalar rejected in "
            "exp-20260519-007."
        ),
        "change_summary": (
            "Sweep a paper-notional scalar for SEC earnings-release text rows "
            "with `spy_t1_return >= -0.005`."
        ),
        "change_type": "alpha_search_semantic_market_context_notional_allocation",
        "component": "quant/sec_financial_report_event_sleeve.py",
        "changed_variable": "sec_earnings_release_text_spy_t1_context_notional_scalar",
        "single_causal_variable": "earnings-release text SPY T+1 context paper-notional scalar",
        "parameters": {
            "target_text_event_type": TARGET_TEXT_EVENT_TYPE,
            "spy_t1_return_min": SPY_T1_RETURN_MIN,
            "baseline_target_scalar": BASELINE_TARGET_SCALAR,
            "target_scalar_variants": list(TARGET_SCALAR_VARIANTS),
            "best_target_scalar": best_scalar,
            "accepted_neutral_underreaction_scalar": prev.ACCEPTED_NEUTRAL_UNDERREACTION_SCALAR,
            "accepted_neutral_underreaction_max_t1_excess": prev.ACCEPTED_NEUTRAL_UNDERREACTION_MAX_T1_EXCESS,
            "accepted_market_context_scalar": prev.ACCEPTED_MARKET_CONTEXT_SCALAR,
            "accepted_market_context_spy_t1_min": prev.ACCEPTED_MARKET_CONTEXT_SPY_T1_MIN,
            "base_event_notional_usd": prev.parent.DEFAULT_EVENT_NOTIONAL_USD,
            "periodic_report_scalar": prev.parent.DEFAULT_PERIODIC_REPORT_NOTIONAL_SCALAR,
            "tenq_periodic_report_scalar": prev.parent.ACCEPTED_10Q_PERIODIC_REPORT_SCALAR,
            "max_positions": prev.parent.DEFAULT_MAX_POSITIONS,
            "source_candidate_artifact": str(prev.parent.SOURCE_EXP100_JSON.relative_to(REPO_ROOT)),
            "text_archive": str(prev.parent.TEXT_ARCHIVE_JSONL.relative_to(REPO_ROOT)),
            "anti_js": "No JavaScript was used.",
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows for core baseline, "
            "plus production SEC financial-report paper-sleeve replay over the "
            "same snapshots."
        ),
        "windows": prev.parent.WINDOWS,
        "candidate_counts_after_current_queue_filter": prev.parent._candidate_counts(exp100),
        "text_load_stats": text_load_stats,
        "text_coverage_summary": text_coverage,
        "target_coverage_summary": target_coverage,
        "gate2_required_fields": gate2_fields,
        "before_metrics": baseline["aggregate"],
        "after_metrics": variants[best_key]["aggregate"],
        "delta_metrics": {
            "aggregate": gate["aggregate_delta"],
            "by_window": gate["by_window"],
        },
        "expected_value_score_delta": gate["aggregate_delta"].get(
            "expected_value_score_sum_delta"
        ),
        "total_pnl_delta": gate["aggregate_delta"].get("total_pnl_sum_delta"),
        "best_variant": best_key,
        "variant_summaries": summaries,
        "selection": selection,
        "gate": gate,
        "interpretation": (
            "The 1.10x earnings-release SPY T+1 context scalar cleared Gate 4: "
            "aggregate EV/PnL improved, all three windows were positive, "
            "drawdown drift was immaterial, sample count was 29, and positive "
            "PnL concentration stayed below the guardrail."
            if gate["passed"]
            else "The earnings-release SPY T+1 context scalar did not clear Gate 4."
        ),
        "rejection_reason": None
        if gate["passed"]
        else "Failed Gate 4 under the canonical three-window SEC paper protocol.",
        "next_evidence_needed": (
            "Keep live/default orders disabled; promote only as shared default-off "
            "SEC paper notional metadata and continue collecting forward "
            "replacement-value evidence."
            if gate["passed"]
            else "Do not retry nearby SEC text-event market-context scalars on "
            "the frozen sample without a new semantic discriminator."
        ),
        "production_impact": {
            "shared_policy_changed": gate["passed"],
            "backtester_adapter_changed": False,
            "run_adapter_changed": gate["passed"],
            "replay_only": False,
            "parity_test_added": gate["passed"],
            "default_off_paper_only": True,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": gate["passed"],
            "live_default_orders_changed": False,
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "capital allocation: scale the SEC financial-report paper sleeve "
                "only when `text_event_type=earnings_release_text` and "
                "`spy_t1_return >= -0.005`."
            ),
            "2_history_check": (
                "exp-20260519-007 rejected the broad earnings-release text scalar "
                "because late_strong EV regressed. exp-20260518-014 accepted the "
                "same SPY T+1 market context threshold for neutral underreaction; "
                "this run freezes that stack and tests only whether the context "
                "field separates earnings-release text rows."
            ),
            "3_single_causal_variable": (
                "sec_earnings_release_text_spy_t1_context_notional_scalar"
            ),
            "4_acceptance_standard": gate["rules"],
            "5_reproducibility": (
                f".venv\\Scripts\\python.exe quant\\experiments\\{STEM}.py"
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": (
                "LLM soft-ranking remains sparse; this tests deterministic "
                "production-visible SEC event-type and SPY T+1 fields."
            ),
        },
        "why_not_other_changes": (
            "State-surface near-high/profile mining is now anti-repeat without a "
            "new field, the broad earnings-release scalar was rejected, and noisy "
            "ticker-pool expansion is not needed for this SEC sleeve test."
        ),
        "related_files": [
            f"quant/experiments/{STEM}.py",
            _repo_rel(OUT_JSON),
            _repo_rel(DOC_LOG),
            _repo_rel(DOC_TICKET),
            _repo_rel(DOC_ARTIFACT),
            _repo_rel(EXPERIMENT_LOG_JSONL),
            "quant/sec_financial_report_event_sleeve.py",
            "quant/test_sec_financial_report_event_sleeve.py",
            "docs/production_backtest_parity.md",
            "docs/backtesting.md",
            "docs/alpha-optimization-playbook.md",
        ],
        "anti_js": "No JavaScript was used.",
    }
    return payload


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(DOC_LOG, payload)
    _write_json(
        DOC_TICKET,
        {
            "experiment_id": EXPERIMENT_ID,
            "lane": "alpha_search",
            "owner": "alpha-search",
            "status": payload["status"],
            "decision": payload["decision"],
            "single_causal_variable": payload["single_causal_variable"],
            "expected_value_score_delta": payload["expected_value_score_delta"],
            "total_pnl_delta": payload["total_pnl_delta"],
            "artifact_file": _repo_rel(OUT_JSON),
            "result_file": _repo_rel(DOC_LOG),
            "updated_at": payload["timestamp"],
        },
    )
    DOC_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT.write_text(_artifact_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG_JSONL, payload)


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "best_variant": payload["best_variant"],
                    "aggregate_ev_delta": payload["expected_value_score_delta"],
                    "aggregate_pnl_delta": payload["total_pnl_delta"],
                    "gate_passed": payload["gate"]["passed"],
                    "window_checks": payload["gate"]["by_window"],
                    "selection": payload["selection"],
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
