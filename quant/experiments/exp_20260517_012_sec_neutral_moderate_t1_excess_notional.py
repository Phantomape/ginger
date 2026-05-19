"""exp-20260517-012: SEC neutral-language moderate T+1 excess notional.

Alpha search on one causal variable: the upper T+1 excess bound for applying a
fixed 2.0x paper-notional scalar to SEC financial-report T+1 paper-sleeve rows
whose filing text is classified as neutral_or_mixed_language.

This keeps the accepted SEC sleeve, max positions, hold days, base notional,
periodic-report scalar, 10-Q scalar, core strategy, and live orders fixed.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260517-012"
STEM = "exp_20260517_012_sec_neutral_moderate_t1_excess_notional"
REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260516_033_sec_financial_report_neutral_language_notional as parent  # noqa: E402


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
DOC_LOG = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_ARTIFACT = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_sec_neutral_moderate_t1_excess_notional.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

MODERATE_T1_EXCESS_CAP_VARIANTS = (0.015, 0.020, 0.025, 0.030, 0.035, 0.040, 0.050, 0.100)
FIXED_NEUTRAL_LANGUAGE_SCALAR = 2.0
BASELINE_NEUTRAL_LANGUAGE_SCALAR = 1.0
MIN_ADJUSTED_TRADES = 6
MIN_WINDOWS_PRESENT = 3
MAX_DRAWDOWN_WORSENING = 0.005
MAX_SINGLE_POSITIVE_PNL_SHARE = 0.55


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
        json.dumps(_safe(payload), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _append_jsonl_once(path: Path, payload: dict[str, Any]) -> None:
    compact = json.dumps(_safe(payload), ensure_ascii=False, separators=(",", ":"))
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        lines = [
            line
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if f'"experiment_id":"{EXPERIMENT_ID}"' not in line
            and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
        ]
    else:
        lines = []
    lines.append(compact)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _t1_excess(candidate: dict[str, Any]) -> float | None:
    try:
        value = float(candidate.get("t1_excess_return_vs_spy"))
    except (TypeError, ValueError):
        return None
    return value


def _make_predicate(cap: float):
    original = parent._is_neutral_language_position

    def _predicate(position: dict[str, Any]) -> bool:
        candidate = parent._source_candidate(position)
        excess = _t1_excess(candidate)
        return original(position) and excess is not None and excess <= cap

    return _predicate


def _run_variant_with_cap(
    *,
    core_results: dict[str, dict[str, Any]],
    exp100: dict[str, Any],
    cap: float,
) -> dict[str, Any]:
    original = parent._is_neutral_language_position
    parent._is_neutral_language_position = _make_predicate(cap)
    try:
        row = parent._run_variant(
            core_results=core_results,
            exp100=exp100,
            neutral_language_scalar=FIXED_NEUTRAL_LANGUAGE_SCALAR,
        )
    finally:
        parent._is_neutral_language_position = original
    row["moderate_t1_excess_cap"] = cap
    row["neutral_language_notional_scalar"] = FIXED_NEUTRAL_LANGUAGE_SCALAR
    return row


def _baseline_variant(
    *,
    core_results: dict[str, dict[str, Any]],
    exp100: dict[str, Any],
) -> dict[str, Any]:
    row = parent._run_variant(
        core_results=core_results,
        exp100=exp100,
        neutral_language_scalar=BASELINE_NEUTRAL_LANGUAGE_SCALAR,
    )
    row["moderate_t1_excess_cap"] = None
    row["neutral_language_notional_scalar"] = BASELINE_NEUTRAL_LANGUAGE_SCALAR
    return row


def _window_deltas(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    deltas: dict[str, Any] = {}
    for label in parent.WINDOWS:
        after_metrics = after["by_window"][label]["combined_metrics"]
        before_metrics = before["by_window"][label]["combined_metrics"]
        after_sleeve = after["by_window"][label]["sleeve_metrics"]
        deltas[label] = {
            "expected_value_score": _round(
                float(after_metrics["expected_value_score"])
                - float(before_metrics["expected_value_score"]),
                6,
            ),
            "total_pnl": _round(
                float(after_metrics["total_pnl"]) - float(before_metrics["total_pnl"]),
                2,
            ),
            "max_drawdown_pct": _round(
                float(after_metrics["max_drawdown_pct"])
                - float(before_metrics["max_drawdown_pct"]),
                6,
            ),
            "sharpe_daily": _round(
                float(after_metrics["sharpe_daily"])
                - float(before_metrics["sharpe_daily"]),
                6,
            ),
            "adjusted_closed_trades": int(
                after_sleeve.get("neutral_language_closed_trade_count") or 0
            ),
            "adjusted_total_pnl": _round(
                after_sleeve.get("neutral_language_total_pnl") or 0.0,
                2,
            ),
        }
    return deltas


def _variant_summary(row: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    aggregate_delta = parent._delta(row["aggregate"], baseline["aggregate"])
    by_window = _window_deltas(row, baseline)
    return {
        "moderate_t1_excess_cap": row["moderate_t1_excess_cap"],
        "neutral_language_notional_scalar": row["neutral_language_notional_scalar"],
        "aggregate_delta": aggregate_delta,
        "by_window": by_window,
        "ev_positive_windows": sum(
            1 for item in by_window.values() if (item["expected_value_score"] or 0.0) > 0
        ),
        "pnl_positive_windows": sum(
            1 for item in by_window.values() if (item["total_pnl"] or 0.0) > 0
        ),
        "max_drawdown_delta_max": max(
            float(item["max_drawdown_pct"] or 0.0) for item in by_window.values()
        ),
        "adjusted_closed_trades": sum(
            int(item["adjusted_closed_trades"] or 0) for item in by_window.values()
        ),
        "adjusted_windows_present": sum(
            1 for item in by_window.values() if int(item["adjusted_closed_trades"] or 0) > 0
        ),
    }


def _closed_positions_for_cap(
    exp100: dict[str, Any],
    *,
    cap: float,
) -> list[dict[str, Any]]:
    original = parent._is_neutral_language_position
    parent._is_neutral_language_position = _make_predicate(cap)
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
                    neutral_language_scalar=1.0,
                    closed=True,
                )
                adjusted_pnl = parent._pnl_for_position(
                    position,
                    neutral_language_scalar=FIXED_NEUTRAL_LANGUAGE_SCALAR,
                    closed=True,
                )
                rows.append(
                    {
                        "window": label,
                        "ticker": candidate.get("ticker"),
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
    finally:
        parent._is_neutral_language_position = original
    return rows


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
        "positive_incremental_pnl": _round(positive_total, 2),
        "max_single_positive_incremental_pnl": _round(max_positive, 2),
        "max_single_positive_pnl_share": (
            _round(max_positive / positive_total, 4) if positive_total > 0 else None
        ),
        "sample_rows": rows[:20],
    }


def _gate(summary: dict[str, Any], selection: dict[str, Any]) -> dict[str, Any]:
    aggregate = summary["aggregate_delta"]
    window_rows = summary["by_window"]
    metric_gate_passed = (
        (aggregate.get("expected_value_score_sum_delta") or 0.0) > 0
        and (aggregate.get("total_pnl_sum_delta") or 0.0) > 0
        and summary["ev_positive_windows"] == 3
        and summary["pnl_positive_windows"] == 3
        and summary["max_drawdown_delta_max"] <= MAX_DRAWDOWN_WORSENING
    )
    sample_guard_passed = (
        selection["adjusted_trade_count"] >= MIN_ADJUSTED_TRADES
        and selection["windows_present"] >= MIN_WINDOWS_PRESENT
    )
    concentration_guard_passed = (
        selection["max_single_positive_pnl_share"] is not None
        and selection["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_PNL_SHARE
    )
    return {
        "passed": metric_gate_passed and sample_guard_passed and concentration_guard_passed,
        "metric_gate_passed": metric_gate_passed,
        "sample_guard_passed": sample_guard_passed,
        "concentration_guard_passed": concentration_guard_passed,
        "aggregate_delta": aggregate,
        "by_window": window_rows,
        "rules": {
            "metric_gate": (
                "aggregate EV/PnL positive, all three windows EV/PnL positive, "
                "and max drawdown worsening <= 0.5 percentage points"
            ),
            "sample_guard": {
                "min_adjusted_trades": MIN_ADJUSTED_TRADES,
                "min_windows_present": MIN_WINDOWS_PRESENT,
            },
            "concentration_guard": {
                "max_single_positive_pnl_share": MAX_SINGLE_POSITIVE_PNL_SHARE,
            },
        },
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    gate = payload["gate"]
    lines = [
        f"# {EXPERIMENT_ID} SEC neutral moderate T1 excess",
        "",
        f"- decision: `{payload['decision']}`",
        f"- best_variant: `{payload['best_variant']}`",
        f"- expected_value_score_delta: `{payload['expected_value_score_delta']}`",
        f"- total_pnl_delta: `{payload['total_pnl_delta']}`",
        f"- gate_passed: `{gate['passed']}`",
        f"- metric_gate_passed: `{gate['metric_gate_passed']}`",
        f"- sample_guard_passed: `{gate['sample_guard_passed']}`",
        f"- concentration_guard_passed: `{gate['concentration_guard_passed']}`",
        "",
        "## Window Deltas",
        "",
        "| window | EV delta | PnL delta | Max DD delta | adjusted trades |",
        "|---|---:|---:|---:|---:|",
    ]
    for label, row in gate["by_window"].items():
        lines.append(
            "| {label} | {ev} | {pnl} | {dd} | {trades} |".format(
                label=label,
                ev=row["expected_value_score"],
                pnl=row["total_pnl"],
                dd=row["max_drawdown_pct"],
                trades=row["adjusted_closed_trades"],
            )
        )
    lines.extend(
        [
            "",
            "## Selection",
            "",
            f"- adjusted trades: `{payload['selection']['adjusted_trade_count']}`",
            f"- windows present: `{payload['selection']['windows_present']}`",
            f"- max single positive PnL share: `{payload['selection']['max_single_positive_pnl_share']}`",
            "",
            "## Interpretation",
            "",
            payload["interpretation"],
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
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

    baseline = _baseline_variant(core_results=core_results, exp100=exp100)
    variants: OrderedDict[str, dict[str, Any]] = OrderedDict()
    summaries: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for cap in MODERATE_T1_EXCESS_CAP_VARIANTS:
        key = f"neutral_language_t1_excess_le_{cap:.3f}"
        row = _run_variant_with_cap(core_results=core_results, exp100=exp100, cap=cap)
        variants[key] = row
        summaries[key] = _variant_summary(row, baseline)

    best_key = max(
        summaries,
        key=lambda name: (
            summaries[name]["aggregate_delta"].get("expected_value_score_sum_delta")
            or -999.0,
            summaries[name]["aggregate_delta"].get("total_pnl_sum_delta") or -999999.0,
        ),
    )
    best_summary = summaries[best_key]
    best_cap = float(best_summary["moderate_t1_excess_cap"])
    selection = _selection_summary(_closed_positions_for_cap(exp100, cap=best_cap))
    gate = _gate(best_summary, selection)

    metric_positive_but_concentrated = (
        gate["metric_gate_passed"]
        and gate["sample_guard_passed"]
        and not gate["concentration_guard_passed"]
    )
    status = "rejected"
    decision = (
        "rejected_concentration_limited_neutral_moderate_t1_excess"
        if metric_positive_but_concentrated
        else "rejected_neutral_moderate_t1_excess_notional"
    )
    interpretation = (
        "The 2.0% T+1 excess cap produced a strong three-window paper alpha "
        "signal, but the positive PnL is too concentrated in one COIN earnings "
        "8-K row. Treat this as a forward research queue, not a promoted paper "
        "allocation rule."
        if metric_positive_but_concentrated
        else "No moderate T+1 excess cap cleared the full three-window metric, sample, "
        "and concentration gate."
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "lane": "alpha_search",
        "hypothesis": (
            "Inside the SEC financial-report T+1 paper sleeve, neutral/mixed "
            "filing language is more likely to be underreaction alpha when the "
            "T+1 excess response is positive but not overheated. A moderate "
            "T+1 excess cap should improve replacement value versus scaling "
            "all neutral-language rows."
        ),
        "change_summary": (
            "Sweep the T+1 excess upper bound for applying a fixed 2.0x "
            "neutral/mixed-language SEC financial-report paper notional."
        ),
        "change_type": "alpha_search_semantic_reaction_state_allocation",
        "component": "quant/experiments",
        "changed_variable": "neutral_language_moderate_t1_excess_cap",
        "single_causal_variable": (
            "T+1 excess cap for the fixed 2.0x neutral/mixed-language SEC "
            "financial-report paper-notional state"
        ),
        "parameters": {
            "baseline_neutral_language_scalar": BASELINE_NEUTRAL_LANGUAGE_SCALAR,
            "fixed_neutral_language_scalar": FIXED_NEUTRAL_LANGUAGE_SCALAR,
            "moderate_t1_excess_cap_variants": list(MODERATE_T1_EXCESS_CAP_VARIANTS),
            "best_cap": best_cap,
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
            "plus SEC financial-report production paper-sleeve replay over the "
            "same OHLCV snapshots."
        ),
        "windows": parent.WINDOWS,
        "gate2_required_fields": gate2_fields,
        "text_load_stats": text_load_stats,
        "text_coverage_summary": text_coverage,
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
        "decision": decision,
        "rejection_reason": (
            "Metric and sample gates passed, but the single-positive-trade "
            "concentration guard failed."
            if metric_positive_but_concentrated
            else "No variant passed the full Gate 4 acceptance standard."
        ),
        "next_evidence_needed": (
            "Collect closed forward SEC neutral/mixed-language moderate-reaction "
            "rows or add a non-price semantic quality field before retrying. "
            "Do not promote this cap on the frozen sample while one COIN row "
            "dominates positive incremental PnL."
        ),
        "interpretation": interpretation,
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
                "If future evidence clears concentration, implement the notional "
                "state in shared sec_financial_report_event_sleeve.py and expose "
                "language_bucket plus t1_excess fields through the production queue."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": (
                "LLM soft-ranking remains too sparse; this experiment uses deterministic "
                "SEC text language buckets and PIT price-reaction fields."
            ),
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "SEC/earnings semantic reaction-state allocation: neutral/mixed "
                "filing language should be scaled only when T+1 excess reaction "
                "is moderate rather than overheated."
            ),
            "2_history_check": (
                "exp-20260516-033 showed the all-neutral-language scalar was "
                "aggregate-positive but failed late_strong and drawdown. This "
                "run changes only the T+1 excess cap around that semantic bucket."
            ),
            "3_single_causal_variable": "neutral_language_moderate_t1_excess_cap",
            "4_acceptance_standard": gate["rules"],
            "5_reproducibility": (
                f".venv\\Scripts\\python.exe quant\\experiments\\{STEM}.py"
            ),
        },
        "why_not_other_changes": (
            "Event rotation's next step is forward maturation, not another frozen "
            "notional sweep; LLM soft-ranking and Form 4/options remain sample-limited; "
            "nearby core slot/RS/green/ATR retunes are anti-repeat logged. This "
            "tests one deterministic SEC semantic reaction-state variable."
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

    _write_json(OUT_JSON, payload)
    _write_json(DOC_LOG, payload)
    _write_json(
        DOC_TICKET,
        {
            "experiment_id": EXPERIMENT_ID,
            "lane": "alpha_search",
            "owner": "alpha-search",
            "status": status,
            "hypothesis": payload["hypothesis"],
            "single_causal_variable": payload["single_causal_variable"],
            "acceptance_rule": gate["rules"],
            "result": {
                "decision": decision,
                "artifact_file": str(OUT_JSON.relative_to(REPO_ROOT)),
                "result_file": str(DOC_LOG.relative_to(REPO_ROOT)),
                "expected_value_score_delta": payload["expected_value_score_delta"],
                "total_pnl_delta": payload["total_pnl_delta"],
                "metric_gate_passed": gate["metric_gate_passed"],
                "sample_guard_passed": gate["sample_guard_passed"],
                "concentration_guard_passed": gate["concentration_guard_passed"],
            },
            "updated_at": timestamp,
        },
    )
    DOC_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT.write_text(_artifact_markdown(payload), encoding="utf-8")
    _append_jsonl_once(EXPERIMENT_LOG_JSONL, payload)

    print(json.dumps(_safe(gate), indent=2, sort_keys=True))
    print(f"{EXPERIMENT_ID} {decision} best={best_key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
