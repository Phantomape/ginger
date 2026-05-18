"""exp-20260518-012: SEC positive-language paper-notional scalar.

Alpha search on one causal variable: a paper-notional scalar for covered
``positive_language`` SEC financial-report T+1 paper-sleeve rows, measured on
top of the accepted neutral-underreaction notional rule from exp-20260518-009.

Core entries, core exits, core sizing, SEC queue qualification, hold days,
max positions, accepted periodic/10-Q scalars, accepted neutral-underreaction
notional, and live orders remain unchanged.

No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260518-012"
STEM = "exp_20260518_012_sec_positive_language_notional"
REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260516_033_sec_financial_report_neutral_language_notional as parent  # noqa: E402
import exp_20260518_011_sec_negative_language_notional as prior  # noqa: E402


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
DOC_LOG = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_ARTIFACT = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_sec_positive_language_notional.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

ACCEPTED_NEUTRAL_UNDERREACTION_SCALAR = 2.0
ACCEPTED_NEUTRAL_UNDERREACTION_MAX_T1_EXCESS = 0.02
BASELINE_POSITIVE_LANGUAGE_SCALAR = 1.0
POSITIVE_LANGUAGE_SCALAR_VARIANTS = (0.0, 0.25, 0.50, 0.75, 1.0, 1.10, 1.25, 1.50, 2.0)


def _safe(value: Any) -> Any:
    return parent._safe(value)


def _round(value: Any, ndigits: int = 6) -> float | None:
    return parent._round(value, ndigits)


def _t1_excess(candidate: dict[str, Any]) -> float | None:
    return prior._t1_excess(candidate)


def _is_accepted_neutral_underreaction(position: dict[str, Any]) -> bool:
    candidate = parent._source_candidate(position)
    if str(candidate.get("sec_text_coverage_status") or "") != "covered":
        return False
    if str(candidate.get("language_bucket") or "") != "neutral_or_mixed_language":
        return False
    value = _t1_excess(candidate)
    return value is not None and value <= ACCEPTED_NEUTRAL_UNDERREACTION_MAX_T1_EXCESS


def _is_positive_language_position(position: dict[str, Any]) -> bool:
    candidate = parent._source_candidate(position)
    return (
        str(candidate.get("sec_text_coverage_status") or "") == "covered"
        and str(candidate.get("language_bucket") or "") == "positive_language"
    )


def _custom_notional_for_position(
    position: dict[str, Any],
    *,
    positive_language_scalar: float,
) -> tuple[float, float, str]:
    _, base_scalar, base_rule = parent._base_notional_for_position(position)
    combined_scalar = float(base_scalar)
    rules = [base_rule]

    if _is_accepted_neutral_underreaction(position):
        combined_scalar *= ACCEPTED_NEUTRAL_UNDERREACTION_SCALAR
        rules.append("neutral_underreaction_scalar")

    if _is_positive_language_position(position):
        combined_scalar *= float(positive_language_scalar)
        rules.append("positive_language_scalar")

    return (
        float(parent.DEFAULT_EVENT_NOTIONAL_USD) * combined_scalar,
        combined_scalar,
        "+".join(rules),
    )


def _run_variant(
    *,
    core_results: dict[str, dict[str, Any]],
    exp100: dict[str, Any],
    positive_language_scalar: float,
) -> dict[str, Any]:
    original_notional = parent._notional_for_position

    def patched_notional(position: dict[str, Any], *, neutral_language_scalar: float) -> tuple[float, float, str]:
        return _custom_notional_for_position(
            position,
            positive_language_scalar=neutral_language_scalar,
        )

    parent._notional_for_position = patched_notional
    try:
        row = parent._run_variant(
            core_results=core_results,
            exp100=exp100,
            neutral_language_scalar=positive_language_scalar,
        )
    finally:
        parent._notional_for_position = original_notional
    row["positive_language_notional_scalar"] = positive_language_scalar
    return row


def _pnl_for_position(
    position: dict[str, Any],
    *,
    positive_language_scalar: float,
    closed: bool,
) -> float:
    adjusted_notional, _, _ = _custom_notional_for_position(
        position,
        positive_language_scalar=positive_language_scalar,
    )
    if closed:
        try:
            net_return = float(position.get("net_return_pct") or 0.0) / 100.0
        except (TypeError, ValueError):
            net_return = 0.0
        return adjusted_notional * net_return

    try:
        source_notional = float(position.get("notional") or 0.0)
        source_pnl = float(position.get("net_pnl_if_closed_now") or 0.0)
    except (TypeError, ValueError):
        return 0.0
    if source_notional <= 0:
        return 0.0
    return adjusted_notional * (source_pnl / source_notional)


def _closed_positions_for_scalar(
    exp100: dict[str, Any],
    *,
    positive_language_scalar: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label, window in parent.WINDOWS.items():
        prices_by_date = parent._load_snapshot_prices(window["snapshot"])
        candidates_by_t1 = parent._rows_by_t1_date(exp100["windows"][label])
        state = parent.empty_sec_financial_report_event_sleeve_state()
        skipped_entries: list[dict[str, Any]] = []
        for as_of, prices in prices_by_date.items():
            candidates = candidates_by_t1.get(as_of, [])
            queue = {
                "queue_name": "SEC_FINANCIAL_REPORT_T1_DRIFT_QUEUE_REPLAY",
                "rule_version": f"{EXPERIMENT_ID}-replay",
                "enabled": False,
                "asof_date": as_of,
                "candidate_count": len(candidates),
                "candidates": candidates,
                "data_source": {"status": "replay", "window": label},
            }
            snapshot = parent.build_sec_financial_report_event_sleeve_snapshot(
                sec_financial_report_t1_queue=queue,
                as_of=as_of,
                open_prices=prices["open"],
                current_prices=prices["close"],
                state=state,
                config={
                    "max_positions": parent.DEFAULT_MAX_POSITIONS,
                    "event_notional_usd": parent.DEFAULT_EVENT_NOTIONAL_USD,
                    "periodic_report_notional_scalar": parent.DEFAULT_PERIODIC_REPORT_NOTIONAL_SCALAR,
                    "tenq_periodic_report_notional_scalar": parent.ACCEPTED_10Q_PERIODIC_REPORT_SCALAR,
                    "neutral_underreaction_notional_enabled": False,
                },
                persist=False,
            )
            skipped_entries.extend(snapshot.get("skipped_entries_today") or [])
            state = parent._rebuild_sleeve_state(snapshot, skipped_entries)

        for position in state.get("closed_positions") or []:
            if not _is_positive_language_position(position):
                continue
            candidate = parent._source_candidate(position)
            baseline_pnl = _pnl_for_position(
                position,
                positive_language_scalar=BASELINE_POSITIVE_LANGUAGE_SCALAR,
                closed=True,
            )
            adjusted_pnl = _pnl_for_position(
                position,
                positive_language_scalar=positive_language_scalar,
                closed=True,
            )
            rows.append(
                {
                    "window": label,
                    "ticker": position.get("ticker"),
                    "entry_date": position.get("entry_date"),
                    "exit_date": position.get("exit_date"),
                    "event_family": candidate.get("event_family"),
                    "form_base": candidate.get("form_base") or candidate.get("form_type"),
                    "language_bucket": candidate.get("language_bucket"),
                    "t1_excess_return_vs_spy": candidate.get("t1_excess_return_vs_spy"),
                    "baseline_pnl": _round(baseline_pnl, 2),
                    "adjusted_pnl": _round(adjusted_pnl, 2),
                    "incremental_pnl": _round(adjusted_pnl - baseline_pnl, 2),
                }
            )
    return rows


def _window_deltas(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    for label in parent.WINDOWS:
        after_m = after["by_window"][label]["combined_metrics"]
        before_m = before["by_window"][label]["combined_metrics"]
        after_sleeve = after["by_window"][label]["sleeve_metrics"]
        before_sleeve = before["by_window"][label]["sleeve_metrics"]
        checks[label] = {
            "expected_value_score": _round(
                float(after_m["expected_value_score"])
                - float(before_m["expected_value_score"]),
                6,
            ),
            "total_pnl": _round(
                float(after_m["total_pnl"]) - float(before_m["total_pnl"]),
                2,
            ),
            "max_drawdown_pct": _round(
                float(after_m["max_drawdown_pct"])
                - float(before_m["max_drawdown_pct"]),
                6,
            ),
            "sharpe_daily": _round(
                float(after_m["sharpe_daily"]) - float(before_m["sharpe_daily"]),
                6,
            ),
            "positive_language_closed_trade_count": int(
                (after_sleeve.get("closed_trade_count_by_language_bucket") or {}).get(
                    "positive_language", 0
                )
            ),
            "positive_language_pnl_delta": _round(
                float(
                    (after_sleeve.get("closed_pnl_by_language_bucket") or {}).get(
                        "positive_language", 0.0
                    )
                )
                - float(
                    (before_sleeve.get("closed_pnl_by_language_bucket") or {}).get(
                        "positive_language", 0.0
                    )
                ),
                2,
            ),
        }
    return checks


def _variant_summary(row: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    aggregate_delta = parent._delta(row["aggregate"], baseline["aggregate"])
    by_window = _window_deltas(row, baseline)
    return {
        "positive_language_notional_scalar": row["positive_language_notional_scalar"],
        "aggregate_delta": aggregate_delta,
        "by_window": by_window,
        "ev_positive_windows": sum(
            1 for item in by_window.values() if (item["expected_value_score"] or 0.0) > 0
        ),
        "ev_regressed_windows": sum(
            1 for item in by_window.values() if (item["expected_value_score"] or 0.0) < 0
        ),
        "pnl_positive_windows": sum(
            1 for item in by_window.values() if (item["total_pnl"] or 0.0) > 0
        ),
        "pnl_regressed_windows": sum(
            1 for item in by_window.values() if (item["total_pnl"] or 0.0) < 0
        ),
        "max_drawdown_delta_max": max(
            float(item["max_drawdown_pct"] or 0.0) for item in by_window.values()
        ),
    }


def _selection_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_window = Counter(str(row["window"]) for row in rows)
    by_ticker = Counter(str(row["ticker"]) for row in rows)
    pnl_by_window: dict[str, float] = {}
    pnl_by_ticker: dict[str, float] = {}
    positive_incremental = []
    for row in rows:
        pnl = float(row.get("incremental_pnl") or 0.0)
        pnl_by_window[str(row["window"])] = pnl_by_window.get(str(row["window"]), 0.0) + pnl
        pnl_by_ticker[str(row["ticker"])] = pnl_by_ticker.get(str(row["ticker"]), 0.0) + pnl
        if pnl > 0:
            positive_incremental.append(pnl)
    positive_total = sum(positive_incremental)
    max_positive = max(positive_incremental) if positive_incremental else 0.0
    return {
        "adjusted_trade_count": len(rows),
        "windows_present": len(by_window),
        "by_window_count": dict(sorted(by_window.items())),
        "by_window_incremental_pnl": {
            key: _round(value, 2) for key, value in sorted(pnl_by_window.items())
        },
        "by_ticker_count": dict(sorted(by_ticker.items())),
        "by_ticker_incremental_pnl": {
            key: _round(value, 2) for key, value in sorted(pnl_by_ticker.items())
        },
        "max_single_positive_incremental_pnl": _round(max_positive, 2),
        "max_single_positive_pnl_share": (
            _round(max_positive / positive_total, 4) if positive_total > 0 else None
        ),
        "positive_incremental_pnl": _round(positive_total, 2),
        "sample_rows": rows[:20],
    }


def _gate(summary: dict[str, Any], selection: dict[str, Any]) -> dict[str, Any]:
    return prior._gate(summary, selection)


def _artifact_markdown(payload: dict[str, Any]) -> str:
    aggregate = payload["gate"]["aggregate_delta"]
    lines = [
        f"# {EXPERIMENT_ID} SEC Positive-Language Notional",
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
        f"- positive_language_scalar: `{payload['parameters']['best_positive_language_scalar']}`",
        f"- EV delta: `{aggregate.get('expected_value_score_sum_delta')}`",
        f"- PnL delta: `${aggregate.get('total_pnl_sum_delta')}`",
        f"- gate_passed: `{payload['gate']['passed']}`",
        "",
        "## Three-Window Deltas",
        "",
        "| Window | EV delta | PnL delta | DD delta | Positive trades | Positive PnL delta |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, row in payload["gate"]["by_window"].items():
        lines.append(
            "| {label} | {ev:+.4f} | ${pnl:+,.2f} | {dd:+.4f} | {count} | ${pos_pnl:+,.2f} |".format(
                label=label,
                ev=row.get("expected_value_score", 0.0),
                pnl=row.get("total_pnl", 0.0),
                dd=row.get("max_drawdown_pct", 0.0),
                count=row.get("positive_language_closed_trade_count", 0),
                pos_pnl=row.get("positive_language_pnl_delta", 0.0),
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
    timestamp = prior._utc_now()
    raw_exp100 = parent._load_exp100()
    current_queue = parent._filter_current_queue(raw_exp100)
    text_rows_by_accession, text_load_stats = parent._load_text_rows()
    exp100 = parent._annotate_language_fields(current_queue, text_rows_by_accession)
    text_coverage = parent._text_coverage_summary(exp100)
    gate2_fields = parent._gate2_open_position_field_check()

    core_results: dict[str, dict[str, Any]] = {}
    for label, window in parent.WINDOWS.items():
        result = parent._run_core_backtest(window)
        core_results[label] = {
            "metrics": parent._core_metrics(result),
            "equity_curve": parent._normalise_core_curve(result),
        }

    variants: OrderedDict[str, dict[str, Any]] = OrderedDict()
    summaries: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for scalar in POSITIVE_LANGUAGE_SCALAR_VARIANTS:
        key = f"positive_language_scalar_{scalar:.2f}"
        row = _run_variant(
            core_results=core_results,
            exp100=exp100,
            positive_language_scalar=scalar,
        )
        variants[key] = row

    baseline_key = f"positive_language_scalar_{BASELINE_POSITIVE_LANGUAGE_SCALAR:.2f}"
    baseline = variants[baseline_key]
    for key, row in variants.items():
        summaries[key] = _variant_summary(row, baseline)

    non_baseline = [key for key in summaries if key != baseline_key]
    passed = [
        key
        for key in non_baseline
        if _gate(
            summaries[key],
            _selection_summary(
                _closed_positions_for_scalar(
                    exp100,
                    positive_language_scalar=summaries[key]["positive_language_notional_scalar"],
                )
            ),
        )["passed"]
    ]
    if passed:
        best_key = max(
            passed,
            key=lambda key: (
                summaries[key]["aggregate_delta"].get("expected_value_score_sum_delta")
                or -999.0,
                summaries[key]["aggregate_delta"].get("total_pnl_sum_delta") or -999999.0,
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
    best_scalar = float(best_summary["positive_language_notional_scalar"])
    selection = _selection_summary(
        _closed_positions_for_scalar(exp100, positive_language_scalar=best_scalar)
    )
    gate = _gate(best_summary, selection)
    status = "accepted_candidate" if gate["passed"] else "rejected"
    decision = (
        "accepted_candidate_sec_positive_language_notional"
        if gate["passed"]
        else "rejected_sec_positive_language_notional"
    )
    interpretation = (
        "Covered positive-language SEC financial-report rows improved with a "
        "paper-notional scalar on top of the accepted neutral-underreaction rule. "
        "Promotion requires moving the same rule into shared paper-only sleeve code "
        "and parity tests before closeout."
        if gate["passed"]
        else "Positive-language paper-notional scalars did not clear the three-window gate on top of exp-20260518-009."
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "lane": "alpha_search",
        "hypothesis": (
            "Inside the accepted SEC financial-report T+1 paper sleeve, covered "
            "positive_language filings may have a distinct continuation profile "
            "after positive T+1 confirmation. A bounded paper-notional scalar "
            "should improve replacement value without changing SEC queue "
            "eligibility, capacity, or live orders."
        ),
        "change_summary": (
            "Sweep a paper-notional scalar for covered positive_language SEC "
            "financial-report rows on top of accepted neutral-underreaction sizing."
        ),
        "change_type": "alpha_search_semantic_notional_allocation",
        "component": "quant/experiments",
        "changed_variable": "sec_financial_report_positive_language_notional_scalar",
        "single_causal_variable": "positive-language paper-notional scalar only",
        "parameters": {
            "baseline_positive_language_scalar": BASELINE_POSITIVE_LANGUAGE_SCALAR,
            "positive_language_scalar_variants": list(POSITIVE_LANGUAGE_SCALAR_VARIANTS),
            "best_positive_language_scalar": best_scalar,
            "accepted_neutral_underreaction_scalar": ACCEPTED_NEUTRAL_UNDERREACTION_SCALAR,
            "accepted_neutral_underreaction_max_t1_excess": ACCEPTED_NEUTRAL_UNDERREACTION_MAX_T1_EXCESS,
            "positive_language_definition": (
                "sec_text_coverage_status == covered and language_bucket == positive_language"
            ),
            "base_event_notional_usd": parent.DEFAULT_EVENT_NOTIONAL_USD,
            "periodic_report_scalar": parent.DEFAULT_PERIODIC_REPORT_NOTIONAL_SCALAR,
            "tenq_periodic_report_scalar": parent.ACCEPTED_10Q_PERIODIC_REPORT_SCALAR,
            "max_positions": parent.DEFAULT_MAX_POSITIONS,
            "source_candidate_artifact": str(parent.SOURCE_EXP100_JSON.relative_to(REPO_ROOT)),
            "text_archive": str(parent.TEXT_ARCHIVE_JSONL.relative_to(REPO_ROOT)),
            "anti_js": "No JavaScript was used.",
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows for core baseline, "
            "plus production SEC financial-report paper-sleeve replay over the same snapshots."
        ),
        "windows": parent.WINDOWS,
        "candidate_counts_after_current_queue_filter": parent._candidate_counts(exp100),
        "text_load_stats": text_load_stats,
        "text_coverage_summary": text_coverage,
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
        "interpretation": interpretation,
        "rejection_reason": None if gate["passed"] else interpretation,
        "next_evidence_needed": (
            "Promote only after the same paper-only scalar is implemented in "
            "shared sec_financial_report_event_sleeve.py with production report "
            "visibility and focused tests."
            if gate["passed"]
            else "Do not retry nearby positive-language notional scalars on this frozen sample without a new semantic field or forward replacement-value evidence."
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
            "promotion_requirement": (
                "If accepted, move rule to shared SEC paper sleeve before final decision."
            ),
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "capital allocation: scale covered positive-language SEC financial-report "
                "paper rows while keeping the accepted neutral-underreaction top-up fixed."
            ),
            "2_history_check": (
                "exp-20260518-009 accepted neutral-underreaction notional; "
                "exp-20260518-010 rejected capacity priority; exp-20260518-011 "
                "rejected negative-language notional. Earlier exp-20260516-033 "
                "used language annotations, but no prior run isolated positive-language "
                "notional on top of the accepted neutral-underreaction stack."
            ),
            "3_single_causal_variable": "positive-language paper-notional scalar",
            "4_acceptance_standard": gate["rules"],
            "5_reproducibility": f".venv\\Scripts\\python.exe quant\\experiments\\{STEM}.py",
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": (
                "LLM soft-ranking remains sparse; this uses deterministic archived "
                "SEC text language buckets and T+1 price reaction fields."
            ),
        },
        "why_not_other_changes": (
            "State-surface profile retunes are anti-repeat without a new field; "
            "negative-language and capacity-priority SEC branches just failed. "
            "This tests one untried production-visible semantic allocation field."
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
    return payload


def persist(payload: dict[str, Any]) -> None:
    prior._write_json(OUT_JSON, payload)
    prior._write_json(DOC_LOG, payload)
    prior._write_json(
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
            "artifact_file": str(OUT_JSON.relative_to(REPO_ROOT)),
            "result_file": str(DOC_LOG.relative_to(REPO_ROOT)),
            "updated_at": payload["timestamp"],
        },
    )
    DOC_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT.write_text(_artifact_markdown(payload), encoding="utf-8")
    prior._upsert_jsonl(EXPERIMENT_LOG_JSONL, payload)


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
                    "anti_js": payload["parameters"]["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
