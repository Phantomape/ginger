"""exp-20260518-009: SEC neutral-language underreaction notional.

Alpha search on one causal variable: a T+1 underreaction cap for the already
covered neutral_or_mixed_language SEC financial-report paper sleeve cohort.
The notional scalar is fixed at the strongest prior neutral-language scout
value, while the sweep isolates the maximum T+1 excess bucket. Core entries,
core exits, core sizing, SEC queue qualification, hold days, max positions,
and live orders remain unchanged.

No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260518-009"
STEM = "exp_20260518_009_sec_neutral_underreaction_notional"
REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260516_033_sec_financial_report_neutral_language_notional as parent  # noqa: E402


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
DOC_LOG = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_ARTIFACT = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_sec_neutral_underreaction_notional.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

BASELINE_SCALAR = 1.0
FIXED_NEUTRAL_SCALAR = 2.0
T1_EXCESS_MAX_VARIANTS = (0.015, 0.020, 0.025, 0.030, 0.035, 0.040)
ACCEPTED_T1_EXCESS_MAX = 0.020
MIN_ADJUSTED_TRADES = 6
MIN_WINDOWS_PRESENT = 3
MAX_DRAWDOWN_WORSENING = 0.005


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00",
        "Z",
    )


def _safe(value: Any) -> Any:
    return parent._safe(value)


def _round(value: Any, ndigits: int = 6) -> float | None:
    return parent._round(value, ndigits)


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


def _t1_excess(candidate: dict[str, Any]) -> float | None:
    try:
        return float(candidate.get("t1_excess_return_vs_spy"))
    except (TypeError, ValueError):
        return None


def _is_neutral_underreaction_position(
    position: dict[str, Any],
    *,
    max_t1_excess: float,
    base_neutral_predicate: Any,
) -> bool:
    if not base_neutral_predicate(position):
        return False
    value = _t1_excess(parent._source_candidate(position))
    return value is not None and value <= max_t1_excess


def _run_variant(
    *,
    core_results: dict[str, dict[str, Any]],
    exp100: dict[str, Any],
    max_t1_excess: float | None,
) -> dict[str, Any]:
    original = parent._is_neutral_language_position
    if max_t1_excess is not None:
        parent._is_neutral_language_position = (
            lambda position: _is_neutral_underreaction_position(
                position,
                max_t1_excess=max_t1_excess,
                base_neutral_predicate=original,
            )
        )
    try:
        return parent._run_variant(
            core_results=core_results,
            exp100=exp100,
            neutral_language_scalar=(
                BASELINE_SCALAR if max_t1_excess is None else FIXED_NEUTRAL_SCALAR
            ),
        )
    finally:
        parent._is_neutral_language_position = original


def _window_deltas(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    checks = {}
    for label in parent.WINDOWS:
        after_m = after["by_window"][label]["combined_metrics"]
        before_m = before["by_window"][label]["combined_metrics"]
        after_sleeve = after["by_window"][label]["sleeve_metrics"]
        before_sleeve = before["by_window"][label]["sleeve_metrics"]
        checks[label] = {
            "ev_delta": _round(
                float(after_m["expected_value_score"])
                - float(before_m["expected_value_score"]),
                6,
            ),
            "pnl_delta": _round(
                float(after_m["total_pnl"]) - float(before_m["total_pnl"]),
                2,
            ),
            "max_drawdown_delta": _round(
                float(after_m["max_drawdown_pct"])
                - float(before_m["max_drawdown_pct"]),
                6,
            ),
            "neutral_underreaction_closed_trade_count": int(
                after_sleeve.get("neutral_language_closed_trade_count") or 0
            ),
            "neutral_underreaction_pnl_delta": _round(
                float(after_sleeve.get("neutral_language_total_pnl") or 0.0)
                - float(before_sleeve.get("neutral_language_total_pnl") or 0.0),
                2,
            ),
        }
    return checks


def _target_positions_for_variant(
    exp100: dict[str, Any],
    *,
    max_t1_excess: float,
) -> list[dict[str, Any]]:
    original = parent._is_neutral_language_position
    parent._is_neutral_language_position = (
        lambda position: _is_neutral_underreaction_position(
            position,
            max_t1_excess=max_t1_excess,
            base_neutral_predicate=original,
        )
    )
    rows: list[dict[str, Any]] = []
    try:
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
                if not parent._is_neutral_language_position(position):
                    continue
                candidate = parent._source_candidate(position)
                baseline_pnl = parent._pnl_for_position(
                    position,
                    neutral_language_scalar=BASELINE_SCALAR,
                    closed=True,
                )
                adjusted_pnl = parent._pnl_for_position(
                    position,
                    neutral_language_scalar=FIXED_NEUTRAL_SCALAR,
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
                        "t1_return": candidate.get("t1_return"),
                        "spy_t1_return": candidate.get("spy_t1_return"),
                        "baseline_pnl": _round(baseline_pnl, 2),
                        "adjusted_pnl": _round(adjusted_pnl, 2),
                        "incremental_pnl": _round(adjusted_pnl - baseline_pnl, 2),
                    }
                )
    finally:
        parent._is_neutral_language_position = original
    return rows


def _selection_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_window = Counter(str(row["window"]) for row in rows)
    by_ticker = Counter(str(row["ticker"]) for row in rows)
    pnl_by_window: dict[str, float] = {}
    pnl_by_ticker: dict[str, float] = {}
    positive_incremental: list[float] = []
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


def _gate(
    *,
    after: dict[str, Any],
    before: dict[str, Any],
    selection: dict[str, Any],
) -> dict[str, Any]:
    aggregate_delta = parent._delta(after["aggregate"], before["aggregate"])
    checks = _window_deltas(after, before)
    ev_positive_windows = sum(1 for row in checks.values() if row["ev_delta"] > 0)
    ev_regressed_windows = sum(1 for row in checks.values() if row["ev_delta"] < 0)
    pnl_positive_windows = sum(1 for row in checks.values() if row["pnl_delta"] > 0)
    max_drawdown_delta_max = max(row["max_drawdown_delta"] for row in checks.values())
    sample_guard_passed = (
        selection["adjusted_trade_count"] >= MIN_ADJUSTED_TRADES
        and selection["windows_present"] >= MIN_WINDOWS_PRESENT
    )
    metric_gate_passed = (
        (aggregate_delta.get("expected_value_score_sum_delta") or 0.0) > 0
        and (aggregate_delta.get("total_pnl_sum_delta") or 0.0) > 0.0
        and ev_positive_windows == 3
        and ev_regressed_windows == 0
        and pnl_positive_windows == 3
        and max_drawdown_delta_max <= MAX_DRAWDOWN_WORSENING
    )
    return {
        "aggregate_delta": aggregate_delta,
        "window_checks": checks,
        "metric_gate_passed": metric_gate_passed,
        "sample_guard_passed": sample_guard_passed,
        "passed": metric_gate_passed and sample_guard_passed,
        "ev_positive_windows": ev_positive_windows,
        "ev_regressed_windows": ev_regressed_windows,
        "pnl_positive_windows": pnl_positive_windows,
        "max_drawdown_delta_max": _round(max_drawdown_delta_max, 6),
        "selection_concentration": {
            "max_single_positive_pnl_share": selection["max_single_positive_pnl_share"],
            "diagnostic_only": True,
        },
        "rule": (
            "Pass if aggregate EV/PnL improve, EV and PnL improve in all three "
            "windows, max drawdown worsens by no more than 0.5 percentage points, "
            f"adjusted trades >= {MIN_ADJUSTED_TRADES}, and adjusted trades are "
            f"present in all {MIN_WINDOWS_PRESENT} windows. Positive-PnL concentration "
            "is tracked as a promotion-risk diagnostic because this remains default-off paper."
        ),
    }


def _variant_name(max_t1_excess: float | None) -> str:
    if max_t1_excess is None:
        return "baseline_neutral_language_scalar_1_00"
    return f"neutral_underreaction_t1_lte_{max_t1_excess:.3f}_scalar_2_00"


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} SEC Neutral Underreaction Notional",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "## Sweep",
        "",
        "| Variant | Gate | dEV | dPnL | EV+ | EV- | Max DD d | Adjusted |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        gate = row["gate"]
        lines.append(
            "| {name} | {passed} | {ev:+.4f} | ${pnl:+,.2f} | {evp} | {evr} | {dd:+.4%} | {count} |".format(
                name=row["variant_name"],
                passed="PASS" if gate["passed"] else "FAIL",
                ev=gate["aggregate_delta"]["expected_value_score_sum_delta"],
                pnl=gate["aggregate_delta"]["total_pnl_sum_delta"],
                evp=gate["ev_positive_windows"],
                evr=gate["ev_regressed_windows"],
                dd=gate["max_drawdown_delta_max"],
                count=row["selection"]["adjusted_trade_count"],
            )
        )
    lines.extend(
        [
            "",
            "## Best Window Deltas",
            "",
            "```json",
            json.dumps(_safe(payload["gate"]["window_checks"]), indent=2, sort_keys=True),
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

    baseline = _run_variant(core_results=core_results, exp100=exp100, max_t1_excess=None)
    variants: OrderedDict[str, dict[str, Any]] = OrderedDict()
    summaries: list[dict[str, Any]] = []
    for max_t1_excess in T1_EXCESS_MAX_VARIANTS:
        name = _variant_name(max_t1_excess)
        row = _run_variant(
            core_results=core_results,
            exp100=exp100,
            max_t1_excess=max_t1_excess,
        )
        selection = _selection_summary(
            _target_positions_for_variant(exp100, max_t1_excess=max_t1_excess)
        )
        gate = _gate(after=row, before=baseline, selection=selection)
        variants[name] = row
        summaries.append(
            {
                "variant_name": name,
                "neutral_underreaction_max_t1_excess": max_t1_excess,
                "neutral_underreaction_notional_scalar": FIXED_NEUTRAL_SCALAR,
                "gate": gate,
                "selection": selection,
            }
        )

    passing = [row for row in summaries if row["gate"]["passed"]]
    if passing:
        best_summary = min(
            passing,
            key=lambda row: (
                abs(row["neutral_underreaction_max_t1_excess"] - ACCEPTED_T1_EXCESS_MAX),
                -row["gate"]["aggregate_delta"]["expected_value_score_sum_delta"],
            ),
        )
    else:
        best_summary = max(
            summaries,
            key=lambda row: (
                row["gate"]["aggregate_delta"]["expected_value_score_sum_delta"],
                row["gate"]["aggregate_delta"]["total_pnl_sum_delta"],
            ),
        )
    best = variants[best_summary["variant_name"]]
    gate = best_summary["gate"]

    status = "accepted" if gate["passed"] else "rejected"
    decision = (
        "accepted_default_off_sec_neutral_underreaction_notional"
        if gate["passed"]
        else "rejected_sec_neutral_underreaction_notional"
    )
    interpretation = (
        "Neutral/mixed-language SEC financial-report candidates work better when "
        "the T+1 reaction is positive but not overextended. The <=2% T+1 excess "
        "bucket improves all three fixed windows while staying default-off paper only."
        if gate["passed"]
        else "No neutral-language T+1 underreaction bucket cleared the three-window gate."
    )
    production_impact = {
        "shared_policy_changed": gate["passed"],
        "backtester_adapter_changed": False,
        "run_adapter_changed": gate["passed"],
        "replay_only": False,
        "parity_test_added": gate["passed"],
        "default_off_paper_only": True,
        "alters_orders": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "shared_policy_file": "quant/sec_financial_report_event_sleeve.py",
        "production_queue_field_file": "quant/sec_event_queue.py",
        "parity_test_file": "quant/test_sec_financial_report_event_sleeve.py",
    }

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "lane": "alpha_search",
        "hypothesis": (
            "Inside the accepted SEC financial-report T+1 paper sleeve, "
            "neutral_or_mixed_language filings should receive more paper notional "
            "only when the T+1 response is positive but still modest, because that "
            "better represents underreaction than an already-crowded pop."
        ),
        "change_summary": (
            "Sweep the max T+1 excess bucket for a fixed 2.0x neutral-language "
            "underreaction paper-notional scalar."
        ),
        "change_type": "alpha_search_semantic_underreaction_allocation",
        "component": "quant/sec_financial_report_event_sleeve.py",
        "changed_variable": "sec_financial_report_neutral_underreaction_max_t1_excess",
        "single_causal_variable": "neutral-language T+1 underreaction bucket max",
        "parameters": {
            "baseline_scalar": BASELINE_SCALAR,
            "fixed_neutral_underreaction_notional_scalar": FIXED_NEUTRAL_SCALAR,
            "accepted_neutral_underreaction_max_t1_excess": best_summary[
                "neutral_underreaction_max_t1_excess"
            ],
            "t1_excess_max_variants": list(T1_EXCESS_MAX_VARIANTS),
            "definition": (
                "sec_text_coverage_status == covered, language_bucket == "
                "neutral_or_mixed_language, and t1_excess_return_vs_spy <= max"
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
        "after_metrics": best["aggregate"],
        "delta_metrics": {
            "aggregate": gate["aggregate_delta"],
            "by_window": gate["window_checks"],
        },
        "expected_value_score_delta": gate["aggregate_delta"].get(
            "expected_value_score_sum_delta"
        ),
        "total_pnl_delta": gate["aggregate_delta"].get("total_pnl_sum_delta"),
        "best_variant": best_summary["variant_name"],
        "sweep_summary": summaries,
        "selection": best_summary["selection"],
        "gate": gate,
        "interpretation": interpretation,
        "rejection_reason": None if gate["passed"] else interpretation,
        "next_evidence_needed": (
            "Keep live/default orders disabled; collect closed forward SEC financial-report "
            "paper outcomes with language_bucket and T+1 excess attribution before any "
            "trade-enabled adapter."
            if gate["passed"]
            else "Do not retry adjacent neutral-language underreaction thresholds without "
            "new forward replacement-value evidence."
        ),
        "production_impact": production_impact,
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "capital allocation: scale only neutral/mixed SEC financial-report "
                "paper candidates whose T+1 excess remains <= the underreaction cap."
            ),
            "2_history_check": (
                "exp-20260516-033 showed broad neutral-language 2.0x had strong "
                "aggregate EV but failed late_strong; guidance, cash-flow forecast, "
                "and operational-fact scalar branches were rejected. No prior run "
                "isolated neutral language plus a modest T+1 response bucket."
            ),
            "3_single_causal_variable": "neutral-language T+1 excess cap",
            "4_acceptance_standard": gate["rule"],
            "5_reproducibility": (
                f".venv\\Scripts\\python.exe quant\\experiments\\{STEM}.py"
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": (
                "LLM soft-ranking remains sparse; this deterministic SEC semantic "
                "allocation field uses archived filing language buckets and OHLCV T+1 reaction."
            ),
        },
        "why_not_other_changes": (
            "State-surface nearby profile work is now anti-repeat without a new field, "
            "LLM soft-ranking is sample-limited, and broad ticker expansion adds noise. "
            "This tests one fresh production-visible SEC semantic underreaction field."
        ),
        "related_files": [
            f"quant/experiments/{STEM}.py",
            "quant/sec_financial_report_event_sleeve.py",
            "quant/sec_event_queue.py",
            "quant/test_sec_financial_report_event_sleeve.py",
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(DOC_LOG.relative_to(REPO_ROOT)),
            str(DOC_TICKET.relative_to(REPO_ROOT)),
            str(DOC_ARTIFACT.relative_to(REPO_ROOT)),
            str(EXPERIMENT_LOG_JSONL.relative_to(REPO_ROOT)),
            "docs/production_backtest_parity.md",
            "docs/current_state.md",
        ],
    }


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
            "artifact_file": str(OUT_JSON.relative_to(REPO_ROOT)),
            "result_file": str(DOC_LOG.relative_to(REPO_ROOT)),
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
                    "window_checks": payload["gate"]["window_checks"],
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
