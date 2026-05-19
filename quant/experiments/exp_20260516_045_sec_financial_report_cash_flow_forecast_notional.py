"""exp-20260516-045: SEC financial-report cash-flow forecast notional.

Alpha search on one causal variable: a paper-notional multiplier for covered
SEC financial-report T+1 paper-sleeve candidates whose archived filing text
contains a cash-flow forecast / guidance / outlook context. The accepted SEC
queue, T+1 excess floor, hold days, max positions, base notional, form-family
scalars, core backtest, and live orders stay fixed.
"""

from __future__ import annotations

import json
import re
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260516_033_sec_financial_report_neutral_language_notional as base


EXPERIMENT_ID = "exp-20260516-045"
STEM = "exp_20260516_045_sec_financial_report_cash_flow_forecast_notional"
REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
DOC_LOG = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_ARTIFACT = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_sec_financial_report_cash_flow_forecast_notional.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

BASELINE_CASH_FLOW_FORECAST_SCALAR = 1.0
CASH_FLOW_FORECAST_SCALAR_VARIANTS = (0.50, 0.75, 1.0, 1.10, 1.25, 1.50, 2.0)
CASH_FLOW_FORECAST_CONTEXT_RE = re.compile(
    r"(cash\s+flows?|free\s+cash\s+flow|operating\s+cash\s+flow)"
    r".{0,90}"
    r"(guidance|outlook|forecast|projection|projected|expect|expected|target)"
    r"|"
    r"(guidance|outlook|forecast|projection|projected|expect|expected|target)"
    r".{0,90}"
    r"(cash\s+flows?|free\s+cash\s+flow|operating\s+cash\s+flow)",
    re.IGNORECASE | re.DOTALL,
)
CASH_FLOW_FORECAST_PHRASES = (
    "cash flow guidance",
    "free cash flow guidance",
    "operating cash flow guidance",
    "cash flow outlook",
    "free cash flow outlook",
    "operating cash flow outlook",
    "cash flow forecast",
    "free cash flow forecast",
    "operating cash flow forecast",
    "expected free cash flow",
    "expects free cash flow",
    "projected free cash flow",
    "free cash flow target",
    "cash flow target",
)
_ORIGINAL_ADJUST_CLOSED_POSITION = base._adjust_closed_position


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _configure_base_paths() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.STEM = STEM
    base.OUT_DIR = OUT_DIR
    base.OUT_JSON = OUT_JSON
    base.DOC_LOG = DOC_LOG
    base.DOC_TICKET = DOC_TICKET
    base.DOC_ARTIFACT = DOC_ARTIFACT
    base.EXPERIMENT_LOG_JSONL = EXPERIMENT_LOG_JSONL


def _accession(row: dict[str, Any]) -> str:
    return base._accession(row)


def _cash_flow_forecast_hits(text: str) -> list[str]:
    lower = text.lower()
    hits = [phrase for phrase in CASH_FLOW_FORECAST_PHRASES if phrase in lower]
    if CASH_FLOW_FORECAST_CONTEXT_RE.search(text):
        hits.append("cash_flow_forecast_context")
    return sorted(set(hits))


def _annotate_cash_flow_fields(
    exp100: dict[str, Any],
    text_rows_by_accession: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    annotated = base._annotate_language_fields(exp100, text_rows_by_accession)
    for window in annotated.get("windows", {}).values():
        for row in window.get("candidate_rows") or []:
            text_row = text_rows_by_accession.get(_accession(row))
            if not text_row:
                row["cash_flow_forecast_present"] = False
                row["cash_flow_forecast_hits"] = []
                continue
            hits = _cash_flow_forecast_hits(str(text_row.get("combined_text") or ""))
            row["cash_flow_forecast_present"] = bool(hits)
            row["cash_flow_forecast_hits"] = hits
    return annotated


def _source_candidate(position: dict[str, Any]) -> dict[str, Any]:
    return base._source_candidate(position)


def _is_cash_flow_forecast_position(position: dict[str, Any]) -> bool:
    candidate = _source_candidate(position)
    return (
        base._coverage_status(position) == "covered"
        and candidate.get("cash_flow_forecast_present") is True
    )


def _notional_for_position(
    position: dict[str, Any],
    *,
    neutral_language_scalar: float,
) -> tuple[float, float, str]:
    notional, scalar, rule = base._base_notional_for_position(position)
    if not _is_cash_flow_forecast_position(position):
        return notional, scalar, rule
    combined_scalar = scalar * float(neutral_language_scalar)
    return (
        float(base.DEFAULT_EVENT_NOTIONAL_USD) * combined_scalar,
        combined_scalar,
        f"{rule}+cash_flow_forecast_scalar",
    )


def _adjust_closed_position(
    position: dict[str, Any],
    *,
    neutral_language_scalar: float,
) -> dict[str, Any]:
    adjusted = _ORIGINAL_ADJUST_CLOSED_POSITION(
        position,
        neutral_language_scalar=neutral_language_scalar,
    )
    candidate = _source_candidate(position)
    adjusted["cash_flow_forecast_present"] = _is_cash_flow_forecast_position(position)
    adjusted["cash_flow_forecast_hits"] = candidate.get("cash_flow_forecast_hits") or []
    adjusted["cash_flow_forecast_notional_scalar"] = neutral_language_scalar
    return adjusted


def _cash_flow_coverage_summary(exp100: dict[str, Any]) -> dict[str, Any]:
    by_window: dict[str, Any] = {}
    aggregate = Counter()
    aggregate_hits = Counter()
    total = 0
    for label, window in exp100.get("windows", {}).items():
        rows = window.get("candidate_rows") or []
        present = sum(1 for row in rows if row.get("cash_flow_forecast_present") is True)
        hits = Counter(
            hit
            for row in rows
            for hit in (row.get("cash_flow_forecast_hits") or [])
        )
        total += len(rows)
        aggregate["present"] += present
        aggregate["absent"] += len(rows) - present
        aggregate_hits.update(hits)
        by_window[label] = {
            "candidate_count": len(rows),
            "cash_flow_forecast_present_count": present,
            "cash_flow_forecast_present_rate": (
                base._round(present / len(rows), 4) if rows else None
            ),
            "cash_flow_forecast_hits": dict(sorted(hits.items())),
        }
    return {
        "aggregate": {
            "candidate_count": total,
            "cash_flow_forecast_present_count": int(aggregate["present"]),
            "cash_flow_forecast_present_rate": (
                base._round(aggregate["present"] / total, 4) if total else None
            ),
            "presence": dict(sorted(aggregate.items())),
            "cash_flow_forecast_hits": dict(sorted(aggregate_hits.items())),
        },
        "by_window": by_window,
    }


def _best_candidate(variants: OrderedDict[str, dict[str, Any]]) -> str:
    baseline = variants[
        f"cash_flow_forecast_scalar_{BASELINE_CASH_FLOW_FORECAST_SCALAR:.2f}"
    ]
    candidates = [
        (name, row, base._gate(row, baseline))
        for name, row in variants.items()
        if row["cash_flow_forecast_notional_scalar"]
        != BASELINE_CASH_FLOW_FORECAST_SCALAR
    ]
    passed = [(name, row, gate) for name, row, gate in candidates if gate["passed"]]
    if passed:
        return max(
            passed,
            key=lambda item: (
                item[2]["aggregate_delta"].get("expected_value_score_sum_delta") or 0.0,
                item[2]["aggregate_delta"].get("sleeve_total_pnl_sum_delta") or 0.0,
            ),
        )[0]
    return max(
        candidates,
        key=lambda item: (
            item[2]["aggregate_delta"].get("expected_value_score_sum_delta") or -999.0,
            item[2]["aggregate_delta"].get("sleeve_total_pnl_sum_delta") or -999999.0,
        ),
    )[0]


def _retag_gate(gate: dict[str, Any]) -> dict[str, Any]:
    gate = json.loads(json.dumps(base._safe(gate)))
    gate["cash_flow_forecast_closed_trade_count_after"] = gate.pop(
        "neutral_language_closed_trade_count_after",
        None,
    )
    for row in gate.get("window_checks", {}).values():
        row["cash_flow_forecast_closed_trade_count"] = row.pop(
            "neutral_language_closed_trade_count",
            None,
        )
        row["cash_flow_forecast_pnl_delta"] = row.pop(
            "neutral_language_pnl_delta",
            None,
        )
    gate["rule"] = (
        "Pass if aggregate EV and sleeve PnL improve, EV and PnL improve in "
        "all three windows, max drawdown worsens by no more than 0.5 percentage "
        "points in any window, sleeve closed trades >= 40, and cash-flow "
        "forecast-context closed trades >= 20."
    )
    return gate


def _artifact_markdown(payload: dict[str, Any]) -> str:
    gate = payload["gate"]
    coverage = payload["cash_flow_forecast_coverage_summary"]["aggregate"]
    lines = [
        f"# {payload['experiment_id']} SEC cash-flow forecast notional",
        "",
        f"- decision: `{payload['decision']}`",
        f"- changed_variable: `{payload['changed_variable']}`",
        f"- best_variant: `{payload['best_variant']}`",
        f"- expected_value_score_delta: `{payload['expected_value_score_delta']}`",
        f"- total_pnl_delta: `{gate['aggregate_delta'].get('total_pnl_sum_delta')}`",
        f"- sleeve_pnl_delta: `{gate['aggregate_delta'].get('sleeve_total_pnl_sum_delta')}`",
        f"- gate_passed: `{gate['passed']}`",
        f"- cash_flow_forecast_present_rate: `{coverage.get('cash_flow_forecast_present_rate')}`",
        "",
        "## Window Deltas",
        "",
        "| window | EV delta | PnL delta | Max DD delta | Field trades | Field PnL delta |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, row in gate["window_checks"].items():
        lines.append(
            "| {label} | {ev} | {pnl} | {dd} | {count} | {field_pnl} |".format(
                label=label,
                ev=row["ev_delta"],
                pnl=row["pnl_delta"],
                dd=row["max_drawdown_delta"],
                count=row["cash_flow_forecast_closed_trade_count"],
                field_pnl=row["cash_flow_forecast_pnl_delta"],
            )
        )
    lines.extend(["", "## Interpretation", "", payload["next_evidence_needed"]])
    return "\n".join(lines) + "\n"


def main() -> int:
    _configure_base_paths()
    base._is_neutral_language_position = _is_cash_flow_forecast_position
    base._notional_for_position = _notional_for_position
    base._adjust_closed_position = _adjust_closed_position

    timestamp = _utc_now()
    raw_exp100 = base._load_exp100()
    current_queue = base._filter_current_queue(raw_exp100)
    text_rows_by_accession, text_load_stats = base._load_text_rows()
    exp100 = _annotate_cash_flow_fields(current_queue, text_rows_by_accession)
    text_coverage = base._text_coverage_summary(exp100)
    cash_flow_coverage = _cash_flow_coverage_summary(exp100)
    gate2_fields = base._gate2_open_position_field_check()

    core_results = {}
    for label, window in base.WINDOWS.items():
        result = base._run_core_backtest(window)
        core_results[label] = {
            "metrics": base._core_metrics(result),
            "equity_curve": base._normalise_core_curve(result),
        }

    variants: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for scalar in CASH_FLOW_FORECAST_SCALAR_VARIANTS:
        name = f"cash_flow_forecast_scalar_{scalar:.2f}"
        row = base._run_variant(
            core_results=core_results,
            exp100=exp100,
            neutral_language_scalar=scalar,
        )
        row["cash_flow_forecast_notional_scalar"] = scalar
        row["neutral_language_notional_scalar"] = scalar
        variants[name] = row

    baseline_key = (
        f"cash_flow_forecast_scalar_{BASELINE_CASH_FLOW_FORECAST_SCALAR:.2f}"
    )
    baseline = variants[baseline_key]
    best_key = _best_candidate(variants)
    best = variants[best_key]
    raw_gate = base._gate(best, baseline)
    gate = _retag_gate(raw_gate)
    metric_gate_passed = bool(gate["passed"])
    status = "observed_only" if metric_gate_passed else "rejected"
    decision = (
        "observed_only_cash_flow_forecast_notional_positive_field_blocked"
        if metric_gate_passed
        else "rejected_cash_flow_forecast_notional_scalar"
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "lane": "alpha_search",
        "hypothesis": (
            "Inside the accepted SEC financial-report T+1 paper sleeve, filings "
            "with cash-flow forecast/guidance/outlook context may carry more "
            "complete forward information and deserve a separate paper-notional "
            "allocation scalar."
        ),
        "change_summary": (
            "Replay-only paper-notional multiplier for covered SEC financial-report "
            "T+1 sleeve rows with cash-flow forecast context in archived filing text."
        ),
        "change_type": "alpha_search_semantic_risk_allocation",
        "component": "quant/experiments",
        "changed_variable": "sec_financial_report_cash_flow_forecast_notional_scalar",
        "parameters": {
            "baseline_cash_flow_forecast_notional_scalar": (
                BASELINE_CASH_FLOW_FORECAST_SCALAR
            ),
            "cash_flow_forecast_definition": (
                "sec_text_coverage_status == covered and archived filing text has "
                "cash-flow forecast/guidance/outlook/expectation/target context"
            ),
            "cash_flow_forecast_scalar_variants": list(
                CASH_FLOW_FORECAST_SCALAR_VARIANTS
            ),
            "cash_flow_forecast_phrases": list(CASH_FLOW_FORECAST_PHRASES),
            "base_event_notional_usd": base.DEFAULT_EVENT_NOTIONAL_USD,
            "periodic_report_scalar": base.DEFAULT_PERIODIC_REPORT_NOTIONAL_SCALAR,
            "tenq_periodic_report_scalar": base.ACCEPTED_10Q_PERIODIC_REPORT_SCALAR,
            "max_positions": base.DEFAULT_MAX_POSITIONS,
            "min_t1_excess_return_vs_spy": (
                base.FINANCIAL_REPORT_T1_MIN_EXCESS_RETURN_VS_SPY
            ),
            "source_candidate_artifact": str(
                base.SOURCE_EXP100_JSON.relative_to(REPO_ROOT)
            ),
            "text_archive": str(base.TEXT_ARCHIVE_JSONL.relative_to(REPO_ROOT)),
            "anti_js": "No JavaScript was used.",
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows for core baseline, "
            "plus production paper-sleeve replay over the same OHLCV snapshots. "
            "Core replay uses REPLAY_PARTIAL_REDUCES and REGIME_AWARE_EXIT."
        ),
        "date_range": {
            "late_strong": base.WINDOWS["late_strong"],
            "mid_weak": base.WINDOWS["mid_weak"],
            "old_thin": base.WINDOWS["old_thin"],
        },
        "candidate_counts_after_current_queue_filter": base._candidate_counts(exp100),
        "text_load_stats": text_load_stats,
        "text_coverage_summary": text_coverage,
        "cash_flow_forecast_coverage_summary": cash_flow_coverage,
        "gate2_required_fields": gate2_fields,
        "before_metrics": baseline["aggregate"],
        "after_metrics": best["aggregate"],
        "delta_metrics": {
            "aggregate": gate["aggregate_delta"],
            "by_window": gate["window_checks"],
        },
        "expected_value_score_delta": gate["aggregate_delta"].get(
            "expected_value_score_sum_delta"
        ),
        "best_variant": best_key,
        "gate": gate,
        "decision": decision,
        "rejection_reason": (
            None
            if metric_gate_passed
            else "No cash-flow forecast scalar cleared the three-window semantic allocation gate."
        ),
        "next_evidence_needed": (
            "Metric gate passed on replay, but do not promote until SEC financial-report "
            "production candidates carry cash_flow_forecast_present fields and parity "
            "tests prove the same field is visible in run.py and backtester paths."
            if metric_gate_passed
            else "Do not retry cash-flow forecast notional scalars on this frozen sample; "
            "future SEC completeness work needs broader production-visible forecast "
            "fields, fuller text coverage, or forward replacement-value evidence."
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
            "production_field_blocked": True,
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "risk allocation: use a new replayable SEC filing-text completeness "
                "field to scale paper notional only for financial-report T+1 "
                "candidates with cash-flow forecast context."
            ),
            "2_history_check": (
                "Recent SEC financial-report experiments accepted max-3 capacity, "
                "T+1 excess floor, 10-day hold, 10-Q 2.0x notional, and rejected "
                "neutral-language and guidance-raise scalar splits. The playbook "
                "specifically calls for forecast-completeness fields before more "
                "SEC threshold work."
            ),
            "3_single_causal_variable": (
                "cash-flow forecast context paper-notional scalar only"
            ),
            "4_acceptance_standard": gate["rule"],
            "5_reproducibility": (
                f".venv\\Scripts\\python.exe quant\\experiments\\{STEM}.py"
            ),
        },
        "variants": variants,
        "why_not_other_changes": (
            "LLM soft-ranking remains attribution-limited, Space/core nearby "
            "scalars are anti-repeat logged, and broad candidate-pool expansion "
            "recently added old-window noise. This tests one new deterministic SEC "
            "completeness field instead of adding noisy tickers."
        ),
        "related_files": [
            f"quant/experiments/{STEM}.py",
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(DOC_LOG.relative_to(REPO_ROOT)),
            str(DOC_TICKET.relative_to(REPO_ROOT)),
            str(DOC_ARTIFACT.relative_to(REPO_ROOT)),
            str(EXPERIMENT_LOG_JSONL.relative_to(REPO_ROOT)),
        ],
    }

    base._write_json(OUT_JSON, payload)
    base._write_json(DOC_LOG, payload)
    base._write_json(
        DOC_TICKET,
        {
            "experiment_id": EXPERIMENT_ID,
            "lane": "alpha_search",
            "owner": "alpha-search",
            "status": status,
            "hypothesis": payload["hypothesis"],
            "single_causal_variable": payload["changed_variable"],
            "acceptance_rule": gate["rule"],
            "result": {
                "decision": decision,
                "artifact_file": str(OUT_JSON.relative_to(REPO_ROOT)),
                "result_file": str(DOC_LOG.relative_to(REPO_ROOT)),
                "expected_value_score_delta": payload["expected_value_score_delta"],
                "total_pnl_delta": gate["aggregate_delta"].get("total_pnl_sum_delta"),
                "production_field_blocked": True,
            },
            "updated_at": timestamp,
        },
    )
    DOC_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT.write_text(_artifact_markdown(payload), encoding="utf-8")
    base._append_jsonl_once(EXPERIMENT_LOG_JSONL, payload)

    print(json.dumps(base._safe(payload["gate"]), indent=2, sort_keys=True))
    print(f"{EXPERIMENT_ID} {decision} best={best_key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
