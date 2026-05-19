"""exp-20260518-015: SEC neutral underreaction ticker T+1 floor.

Alpha search on one production-visible field. On top of the accepted
neutral-underreaction SEC financial-report paper path and the accepted SPY T+1
market-context guard, test whether the extra paper-notional scalar should also
require the ticker's own T+1 return to show enough positive absorption.

No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260518-015"
STEM = "exp_20260518_015_sec_neutral_ticker_t1_floor"
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
    / f"{EXPERIMENT_ID}_sec_neutral_ticker_t1_floor.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

ACCEPTED_NEUTRAL_UNDERREACTION_SCALAR = 2.0
ACCEPTED_NEUTRAL_UNDERREACTION_MAX_T1_EXCESS = 0.020
ACCEPTED_SPY_T1_RETURN_MIN = -0.005
ACCEPTED_MARKET_CONTEXT_EXTRA_SCALAR = 1.5
TICKER_T1_RETURN_MIN_VARIANTS = (0.0, 0.005, 0.010, 0.0125, 0.015, 0.020)
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


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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


def _accepted_neutral_underreaction(position: dict[str, Any]) -> bool:
    candidate = parent._source_candidate(position)
    if str(candidate.get("language_bucket") or "") != "neutral_or_mixed_language":
        return False
    t1_excess = _float(candidate.get("t1_excess_return_vs_spy"))
    return (
        t1_excess is not None
        and t1_excess <= ACCEPTED_NEUTRAL_UNDERREACTION_MAX_T1_EXCESS
    )


def _spy_context_confirmed(position: dict[str, Any]) -> bool:
    if not _accepted_neutral_underreaction(position):
        return False
    spy_t1_return = _float(parent._source_candidate(position).get("spy_t1_return"))
    return spy_t1_return is not None and spy_t1_return >= ACCEPTED_SPY_T1_RETURN_MIN


def _ticker_t1_floor_confirmed(
    position: dict[str, Any],
    *,
    ticker_t1_min: float | None,
) -> bool:
    if not _spy_context_confirmed(position):
        return False
    if ticker_t1_min is None:
        return True
    ticker_t1_return = _float(parent._source_candidate(position).get("t1_return"))
    return ticker_t1_return is not None and ticker_t1_return >= ticker_t1_min


def _run_variant(
    *,
    core_results: dict[str, dict[str, Any]],
    exp100: dict[str, Any],
    ticker_t1_min: float | None,
) -> dict[str, Any]:
    original = parent._notional_for_position

    def patched_notional(
        position: dict[str, Any],
        *,
        neutral_language_scalar: float,
    ) -> tuple[float, float, str]:
        del neutral_language_scalar
        _, scalar, rule = parent._base_notional_for_position(position)
        if _accepted_neutral_underreaction(position):
            scalar *= ACCEPTED_NEUTRAL_UNDERREACTION_SCALAR
            rule = f"{rule}+neutral_underreaction_scalar"
            if _ticker_t1_floor_confirmed(
                position,
                ticker_t1_min=ticker_t1_min,
            ):
                scalar *= ACCEPTED_MARKET_CONTEXT_EXTRA_SCALAR
                rule = f"{rule}+neutral_underreaction_spy_t1_context_scalar"
                if ticker_t1_min is not None:
                    rule = f"{rule}+ticker_t1_floor"
        return float(parent.DEFAULT_EVENT_NOTIONAL_USD) * scalar, scalar, rule

    parent._notional_for_position = patched_notional
    try:
        return parent._run_variant(
            core_results=core_results,
            exp100=exp100,
            neutral_language_scalar=1.0,
        )
    finally:
        parent._notional_for_position = original


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
            "neutral_language_closed_trade_count": int(
                after_sleeve.get("neutral_language_closed_trade_count") or 0
            ),
            "neutral_language_pnl_delta": _round(
                float(after_sleeve.get("neutral_language_total_pnl") or 0.0)
                - float(before_sleeve.get("neutral_language_total_pnl") or 0.0),
                2,
            ),
        }
    return checks


def _target_rows(
    exp100: dict[str, Any],
    *,
    ticker_t1_min: float | None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label, window in exp100.get("windows", {}).items():
        for candidate in window.get("candidate_rows") or []:
            if str(candidate.get("language_bucket") or "") != "neutral_or_mixed_language":
                continue
            t1_excess = _float(candidate.get("t1_excess_return_vs_spy"))
            spy_t1_return = _float(candidate.get("spy_t1_return"))
            ticker_t1_return = _float(candidate.get("t1_return"))
            if t1_excess is None or t1_excess > ACCEPTED_NEUTRAL_UNDERREACTION_MAX_T1_EXCESS:
                continue
            if spy_t1_return is None or spy_t1_return < ACCEPTED_SPY_T1_RETURN_MIN:
                continue
            if ticker_t1_min is not None and (
                ticker_t1_return is None or ticker_t1_return < ticker_t1_min
            ):
                continue
            row = dict(candidate)
            row["window"] = label
            row["ticker_t1_return_min"] = ticker_t1_min
            rows.append(row)
    return rows


def _selection_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_window = Counter(str(row["window"]) for row in rows)
    by_ticker = Counter(str(row["ticker"]) for row in rows)
    return {
        "adjusted_candidate_count": len(rows),
        "windows_present": len(by_window),
        "by_window_count": dict(sorted(by_window.items())),
        "by_ticker_count": dict(sorted(by_ticker.items())),
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
    pnl_regressed_windows = sum(1 for row in checks.values() if row["pnl_delta"] < 0)
    max_drawdown_delta_max = max(row["max_drawdown_delta"] for row in checks.values())
    sample_guard_passed = (
        selection["adjusted_candidate_count"] >= MIN_ADJUSTED_TRADES
        and selection["windows_present"] >= MIN_WINDOWS_PRESENT
    )
    metric_gate_passed = (
        (aggregate_delta.get("expected_value_score_sum_delta") or 0.0) > 0
        and (aggregate_delta.get("total_pnl_sum_delta") or 0.0) > 0.0
        and ev_positive_windows == 3
        and ev_regressed_windows == 0
        and pnl_positive_windows == 3
        and pnl_regressed_windows == 0
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
        "pnl_regressed_windows": pnl_regressed_windows,
        "max_drawdown_delta_max": _round(max_drawdown_delta_max, 6),
        "rule": (
            "Pass if aggregate EV/PnL improve versus accepted exp-20260518-014, "
            "EV and PnL improve in all three fixed windows, no window regresses, "
            "max drawdown worsens by <=0.5pp, and adjusted candidates >= "
            f"{MIN_ADJUSTED_TRADES} across all {MIN_WINDOWS_PRESENT} windows."
        ),
    }


def _variant_name(ticker_t1_min: float | None) -> str:
    if ticker_t1_min is None:
        return "accepted_neutral_market_context"
    return f"ticker_t1_return_gte_{ticker_t1_min:+.4f}"


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} SEC Neutral Ticker T+1 Floor",
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
                count=row["selection"]["adjusted_candidate_count"],
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

    baseline = _run_variant(core_results=core_results, exp100=exp100, ticker_t1_min=None)
    variants: OrderedDict[str, dict[str, Any]] = OrderedDict()
    summaries: list[dict[str, Any]] = []
    for ticker_t1_min in TICKER_T1_RETURN_MIN_VARIANTS:
        name = _variant_name(ticker_t1_min)
        row = _run_variant(
            core_results=core_results,
            exp100=exp100,
            ticker_t1_min=ticker_t1_min,
        )
        selection = _selection_summary(_target_rows(exp100, ticker_t1_min=ticker_t1_min))
        gate = _gate(after=row, before=baseline, selection=selection)
        variants[name] = row
        summaries.append(
            {
                "variant_name": name,
                "ticker_t1_return_min": ticker_t1_min,
                "market_context_extra_scalar": ACCEPTED_MARKET_CONTEXT_EXTRA_SCALAR,
                "gate": gate,
                "selection": selection,
            }
        )

    passing = [row for row in summaries if row["gate"]["passed"]]
    if passing:
        best_summary = min(
            passing,
            key=lambda row: (
                row["ticker_t1_return_min"],
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
    status = "accepted_candidate" if gate["passed"] else "rejected"
    decision = (
        "accepted_candidate_sec_neutral_ticker_t1_floor"
        if gate["passed"]
        else "rejected_sec_neutral_ticker_t1_floor"
    )
    interpretation = (
        "The ticker T+1 return floor improved the accepted neutral-underreaction "
        "market-context paper allocation and is eligible for shared default-off "
        "paper implementation."
        if gate["passed"]
        else "Adding a ticker T+1 return floor did not improve the accepted SEC "
        "neutral-underreaction market-context allocation across the three fixed windows."
    )
    production_impact = {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": False,
        "parity_test_added": False,
        "default_off_paper_only": True,
        "alters_orders": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
    }

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "lane": "alpha_search",
        "hypothesis": (
            "Inside the accepted SEC financial-report neutral-underreaction paper "
            "cohort, the extra SPY T+1 market-context notional should be reserved "
            "for candidates whose own T+1 return is also clearly positive, because "
            "weak absolute ticker absorption may indicate a stale or fragile drift."
        ),
        "change_summary": (
            "Sweep a ticker T+1 return floor for applying the accepted 1.5x extra "
            "market-context paper-notional scalar."
        ),
        "change_type": "alpha_search_market_context_notional_allocation",
        "component": "quant/sec_financial_report_event_sleeve.py",
        "changed_variable": "sec_neutral_underreaction_ticker_t1_return_min",
        "single_causal_variable": "ticker T+1 return floor for extra neutral-underreaction market-context paper notional",
        "parameters": {
            "accepted_neutral_underreaction_scalar": ACCEPTED_NEUTRAL_UNDERREACTION_SCALAR,
            "accepted_neutral_underreaction_max_t1_excess": ACCEPTED_NEUTRAL_UNDERREACTION_MAX_T1_EXCESS,
            "accepted_spy_t1_return_min": ACCEPTED_SPY_T1_RETURN_MIN,
            "market_context_extra_scalar": ACCEPTED_MARKET_CONTEXT_EXTRA_SCALAR,
            "ticker_t1_return_min_variants": list(TICKER_T1_RETURN_MIN_VARIANTS),
            "best_ticker_t1_return_min": best_summary["ticker_t1_return_min"],
            "definition": (
                "accepted neutral-underreaction candidate, spy_t1_return >= -0.5%, "
                "and ticker t1_return >= floor"
            ),
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
            "Implement the ticker T+1 floor only if promoted with shared default-off "
            "SEC sleeve code and parity coverage; otherwise do not retry nearby "
            "ticker T+1 floors without forward replacement-value evidence."
            if gate["passed"]
            else "Do not retry nearby ticker T+1 floors on this frozen sample; SEC "
            "work should move to a genuinely new semantic field or forward outcomes."
        ),
        "production_impact": production_impact,
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "capital allocation: use ticker absolute T+1 absorption as a new "
                "production-visible confirmation field inside the accepted SEC "
                "neutral-underreaction market-context paper path."
            ),
            "2_history_check": (
                "exp-20260518-009 accepted neutral-underreaction T+1 excess <=2%; "
                "exp-20260518-014 accepted SPY T+1 market context; earlier entry-gap, "
                "capacity-priority, positive-language, and negative-language SEC "
                "branches failed or were sample/concentration-limited. No current run "
                "isolated ticker absolute T+1 return as the extra-context gate."
            ),
            "3_single_causal_variable": "sec_neutral_underreaction_ticker_t1_return_min",
            "4_acceptance_standard": gate["rule"],
            "5_reproducibility": f".venv\\Scripts\\python.exe quant\\experiments\\{STEM}.py",
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": (
                "LLM soft-ranking remains data-limited; this test uses deterministic "
                "SEC language and T+1 market fields already present in the paper queue."
            ),
        },
        "why_not_other_changes": (
            "State-surface nearby profile retunes are now anti-repeat without a new "
            "quality field, and SEC positive/negative language scalars just failed. "
            "This tests one new production-visible market-confirmation variable."
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
