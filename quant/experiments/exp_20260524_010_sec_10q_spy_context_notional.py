"""exp-20260524-010: SEC 10-Q SPY T+1 context notional scalar.

Alpha search on one stable production-visible SEC context bucket. The run tests
whether accepted 10-Q periodic-report paper entries deserve extra notional when
the same-day SPY T+1 context is not worse than -0.5%.

No JavaScript is used.
"""

from __future__ import annotations

from collections import Counter, OrderedDict
from datetime import datetime, timezone
import json
import sys
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260524-010"
STEM = "exp_20260524_010_sec_10q_spy_context_notional"
REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260519_008_sec_earnings_release_spy_context_notional as base  # noqa: E402
import exp_20260524_005_sec_same_ticker_repeat_scalar as repeat  # noqa: E402


parent = base.prev.parent
ORIGINAL_NOTIONAL_FOR_POSITION = base._notional_for_position

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
DOC_LOG = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_ARTIFACT = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_sec_10q_spy_context_notional.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

ACCEPTED_EARNINGS_RELEASE_SPY_CONTEXT_SCALAR = 1.10
TARGET_SPY_T1_RETURN_MIN = -0.005
CHANGED_VARIABLE = "sec_10q_spy_t1_context_notional_scalar"
TRIAL_FAMILY = "sec_10q_market_context_allocation"
TARGET_SCALARS: "OrderedDict[str, float]" = OrderedDict(
    [
        ("tenq_spy_context_scalar_0_50", 0.50),
        ("tenq_spy_context_scalar_0_75", 0.75),
        ("tenq_spy_context_scalar_1_00", 1.00),
        ("tenq_spy_context_scalar_1_10", 1.10),
        ("tenq_spy_context_scalar_1_25", 1.25),
        ("tenq_spy_context_scalar_1_50", 1.50),
    ]
)

MIN_ADJUSTED_TRADES = 6
MIN_ADJUSTED_WINDOWS = 2
MIN_EV_IMPROVED_WINDOWS = 2
MAX_EV_REGRESSED_WINDOWS = 0
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_TICKER_POSITIVE_SHARE = 0.50
MAX_TOP5_CONTRIBUTION = 0.60
MAX_HHI_CONCENTRATION = 0.35


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00",
        "Z",
    )


def _safe(value: Any) -> Any:
    return base._safe(value)


def _round(value: Any, ndigits: int = 6) -> float | None:
    return base._round(value, ndigits)


def _float(value: Any) -> float | None:
    return base._float(value)


def _source_candidate(position: dict[str, Any]) -> dict[str, Any]:
    return base._source_candidate(position)


def _form_base(candidate: dict[str, Any]) -> str:
    raw = (
        candidate.get("form_base")
        or candidate.get("form_type")
        or candidate.get("form")
        or candidate.get("sec_form")
        or ""
    )
    return str(raw).upper().strip()


def _is_target_position(position: dict[str, Any]) -> bool:
    candidate = _source_candidate(position)
    if not _form_base(candidate).startswith("10-Q"):
        return False
    spy_t1_return = _float(candidate.get("spy_t1_return"))
    return spy_t1_return is not None and spy_t1_return >= TARGET_SPY_T1_RETURN_MIN


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


def _patched_notional_for_position(
    position: dict[str, Any],
    *,
    target_scalar: float,
) -> tuple[float, float, str]:
    notional, scalar, rule = ORIGINAL_NOTIONAL_FOR_POSITION(
        position,
        target_scalar=target_scalar,
    )
    if not _is_target_position(position):
        return notional, scalar, rule
    active_scalar = float(getattr(_patched_notional_for_position, "active_scalar", 1.0))
    scalar *= active_scalar
    return (
        float(parent.DEFAULT_EVENT_NOTIONAL_USD) * scalar,
        scalar,
        f"{rule}+sec_10q_spy_t1_context_scalar",
    )


def _run_variant(
    *,
    core_results: dict[str, dict[str, Any]],
    exp100: dict[str, Any],
    scalar: float,
) -> dict[str, Any]:
    original = base._notional_for_position
    _patched_notional_for_position.active_scalar = float(scalar)
    base._notional_for_position = _patched_notional_for_position
    try:
        row = base._run_variant(
            core_results=core_results,
            exp100=exp100,
            target_scalar=ACCEPTED_EARNINGS_RELEASE_SPY_CONTEXT_SCALAR,
        )
    finally:
        base._notional_for_position = original
    row[CHANGED_VARIABLE] = scalar
    return row


def _target_positions(exp100: dict[str, Any], *, scalar: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label, window in parent.WINDOWS.items():
        prices_by_date = parent._load_snapshot_prices(window["snapshot"])
        candidates_by_t1 = parent._rows_by_t1_date(exp100["windows"][label])
        state = parent.empty_sec_financial_report_event_sleeve_state()
        skipped_entries: list[dict[str, Any]] = []
        for as_of, prices in prices_by_date.items():
            queue = {
                "queue_name": "SEC_FINANCIAL_REPORT_T1_DRIFT_QUEUE_REPLAY",
                "rule_version": f"{EXPERIMENT_ID}-replay",
                "enabled": False,
                "asof_date": as_of,
                "candidate_count": len(candidates_by_t1.get(as_of, [])),
                "candidates": candidates_by_t1.get(as_of, []),
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
            if not _is_target_position(position):
                continue
            candidate = _source_candidate(position)
            baseline_notional, baseline_scalar, baseline_rule = ORIGINAL_NOTIONAL_FOR_POSITION(
                position,
                target_scalar=ACCEPTED_EARNINGS_RELEASE_SPY_CONTEXT_SCALAR,
            )
            adjusted_notional = baseline_notional * float(scalar)
            net_return = (_float(position.get("net_return_pct")) or 0.0) / 100.0
            baseline_pnl = baseline_notional * net_return
            adjusted_pnl = adjusted_notional * net_return
            rows.append(
                {
                    "window": label,
                    "ticker": position.get("ticker"),
                    "entry_date": position.get("entry_date"),
                    "exit_date": position.get("exit_date"),
                    "form_base": candidate.get("form_base") or candidate.get("form_type"),
                    "language_bucket": candidate.get("language_bucket"),
                    "text_event_type": candidate.get("text_event_type"),
                    "sec_text_coverage_status": candidate.get("sec_text_coverage_status"),
                    "spy_t1_return": candidate.get("spy_t1_return"),
                    "event_notional_rule_before": baseline_rule,
                    "event_notional_scalar_before": baseline_scalar,
                    "event_notional_scalar_after": baseline_scalar * float(scalar),
                    "baseline_notional": _round(baseline_notional, 2),
                    "adjusted_notional": _round(adjusted_notional, 2),
                    "baseline_pnl": _round(baseline_pnl, 2),
                    "adjusted_pnl": _round(adjusted_pnl, 2),
                    "incremental_pnl": _round(adjusted_pnl - baseline_pnl, 2),
                }
            )
    return rows


def _selection_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_window = Counter(str(row["window"]) for row in rows)
    by_ticker = Counter(str(row["ticker"]) for row in rows)
    positive_by_ticker: dict[str, float] = {}
    pnl_by_window: dict[str, float] = {}
    for row in rows:
        pnl = float(row.get("incremental_pnl") or 0.0)
        pnl_by_window[str(row["window"])] = pnl_by_window.get(str(row["window"]), 0.0) + pnl
        if pnl > 0:
            ticker = str(row["ticker"])
            positive_by_ticker[ticker] = positive_by_ticker.get(ticker, 0.0) + pnl
    positive_values = sorted(positive_by_ticker.values(), reverse=True)
    positive_total = sum(positive_values)
    hhi = (
        sum((value / positive_total) ** 2 for value in positive_values)
        if positive_total > 0
        else None
    )
    return {
        "adjusted_trade_count": len(rows),
        "windows_present": len(by_window),
        "by_window_count": dict(sorted(by_window.items())),
        "by_window_incremental_pnl": {
            key: _round(value, 2) for key, value in sorted(pnl_by_window.items())
        },
        "by_ticker_count": dict(sorted(by_ticker.items())),
        "positive_incremental_pnl": _round(positive_total, 2),
        "max_single_positive_pnl_share": (
            _round(max(positive_values) / positive_total, 4)
            if positive_total > 0 and positive_values
            else None
        ),
        "pnl_top_5_contribution_pct": (
            _round(sum(positive_values[:5]) / positive_total, 4)
            if positive_total > 0
            else None
        ),
        "pnl_hhi_concentration": _round(hhi, 4) if hhi is not None else None,
        "sample_rows": rows[:25],
    }


def _gate(summary: dict[str, Any], selection: dict[str, Any]) -> dict[str, Any]:
    aggregate = summary["aggregate_delta"]
    max_single = selection["max_single_positive_pnl_share"]
    top5 = selection["pnl_top_5_contribution_pct"]
    hhi = selection["pnl_hhi_concentration"]
    metric_checks = {
        "positive_aggregate_ev": (aggregate.get("expected_value_score_sum_delta") or 0.0) > 0,
        "positive_aggregate_pnl": (aggregate.get("total_pnl_sum_delta") or 0.0) > 0,
        "ev_improved_window_coverage": summary["ev_positive_windows"] >= MIN_EV_IMPROVED_WINDOWS,
        "no_ev_regressed_windows": summary["ev_regressed_windows"] <= MAX_EV_REGRESSED_WINDOWS,
        "drawdown_worse_guard": summary["max_drawdown_delta_max"] <= MAX_DRAWDOWN_WORSE,
        "adjusted_trade_sample": selection["adjusted_trade_count"] >= MIN_ADJUSTED_TRADES,
        "adjusted_window_coverage": selection["windows_present"] >= MIN_ADJUSTED_WINDOWS,
        "single_ticker_positive_share_cap": (
            max_single is None or max_single <= MAX_SINGLE_TICKER_POSITIVE_SHARE
        ),
        "top5_contribution_cap": top5 is None or top5 <= MAX_TOP5_CONTRIBUTION,
        "hhi_concentration_cap": hhi is None or hhi <= MAX_HHI_CONCENTRATION,
    }
    causal_checks = {
        "stable_causal_field": True,
        "reason": (
            "`form_base` and `spy_t1_return` are production-visible event/context "
            "fields already used by the SEC paper sleeve experiments; the -0.5% "
            "SPY T+1 threshold is fixed from prior accepted market-context work."
        ),
    }
    return {
        "aggregate_delta": aggregate,
        "by_window": summary["by_window"],
        "metric_checks": metric_checks,
        "causal_field_checks": causal_checks,
        "metric_gate_passed": all(metric_checks.values()),
        "passed": all(metric_checks.values()) and causal_checks["stable_causal_field"],
        "metrics": {
            "adjusted_trade_count": selection["adjusted_trade_count"],
            "adjusted_windows": sorted(selection["by_window_count"].keys()),
            "windows_ev_improved": summary["ev_positive_windows"],
            "windows_ev_regressed": summary["ev_regressed_windows"],
            "max_drawdown_worse": _round(summary["max_drawdown_delta_max"], 6),
            "max_single_positive_pnl_share": max_single,
            "pnl_top_5_contribution_pct": top5,
            "pnl_hhi_concentration": hhi,
        },
        "rules": {
            "metric_gate": (
                "aggregate EV/PnL positive, at least two EV-improved windows, "
                "zero EV-regressed windows, and max drawdown worsening <= 0.5pp"
            ),
            "sample_guard": {
                "min_adjusted_trades": MIN_ADJUSTED_TRADES,
                "min_adjusted_windows": MIN_ADJUSTED_WINDOWS,
            },
            "tail_guard": {
                "max_single_ticker_positive_share": MAX_SINGLE_TICKER_POSITIVE_SHARE,
                "max_top5_contribution": MAX_TOP5_CONTRIBUTION,
                "max_hhi_concentration": MAX_HHI_CONCENTRATION,
            },
            "production_parity_guard": "Field must be stable event/context data, not archive coverage.",
        },
    }


def _variant_summary(row: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    by_window = repeat._window_deltas(row, baseline)
    return {
        CHANGED_VARIABLE: row[CHANGED_VARIABLE],
        "aggregate_delta": parent._delta(row["aggregate"], baseline["aggregate"]),
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


def _artifact_markdown(payload: dict[str, Any]) -> str:
    gate = payload["gate"]
    aggregate = gate["aggregate_delta"]
    lines = [
        f"# {EXPERIMENT_ID} SEC 10-Q SPY T+1 Context Notional",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "## Best Variant",
        "",
        f"- best_variant: `{payload['best_variant']}`",
        f"- scalar: `{payload['parameters']['best_scalar']}`",
        f"- metric_gate_passed: `{gate['metric_gate_passed']}`",
        f"- final_gate_passed: `{gate['passed']}`",
        f"- EV delta: `{aggregate.get('expected_value_score_sum_delta')}`",
        f"- PnL delta: `${aggregate.get('total_pnl_sum_delta')}`",
        "",
        "## Three-Window Deltas",
        "",
        "| Window | EV delta | PnL delta | DD delta |",
        "|---|---:|---:|---:|",
    ]
    for label, row in gate["by_window"].items():
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
            "## Rejection Reason",
            "",
            payload["rejection_reason"] or "",
            "",
            "## Gate",
            "",
            "```json",
            json.dumps(_safe(gate), indent=2, sort_keys=True),
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

    variants: OrderedDict[str, dict[str, Any]] = OrderedDict()
    summaries: OrderedDict[str, dict[str, Any]] = OrderedDict()
    selections: OrderedDict[str, dict[str, Any]] = OrderedDict()
    gates: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for key, scalar in TARGET_SCALARS.items():
        variants[key] = _run_variant(
            core_results=core_results,
            exp100=exp100,
            scalar=scalar,
        )
    baseline = variants["tenq_spy_context_scalar_1_00"]
    for key, scalar in TARGET_SCALARS.items():
        summaries[key] = _variant_summary(variants[key], baseline)
        selections[key] = _selection_summary(_target_positions(exp100, scalar=scalar))
        gates[key] = _gate(summaries[key], selections[key])

    non_baseline = [key for key in TARGET_SCALARS if key != "tenq_spy_context_scalar_1_00"]
    metric_passing = [key for key in non_baseline if gates[key]["metric_gate_passed"]]
    if metric_passing:
        best_key = max(
            metric_passing,
            key=lambda key: (
                summaries[key]["aggregate_delta"].get("expected_value_score_sum_delta")
                or -999.0,
                -summaries[key]["max_drawdown_delta_max"],
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
    best_scalar = TARGET_SCALARS[best_key]
    gate = gates[best_key]
    status = "rejected"
    decision = "accepted_candidate_sec_10q_spy_context_notional" if gate["passed"] else "rejected_sec_10q_spy_context_notional"
    if (
        gate["metrics"]["adjusted_trade_count"] < MIN_ADJUSTED_TRADES
        or len(gate["metrics"]["adjusted_windows"]) < MIN_ADJUSTED_WINDOWS
    ):
        rejection_reason = (
            "Too few SEC financial-report paper-sleeve closed positions matched "
            "`form_base startswith 10-Q and spy_t1_return >= -0.005` across the "
            "canonical three-window replay, so the scalar fails the sample gate."
        )
    elif not gate["metric_gate_passed"]:
        failed_checks = [
            key for key, value in gate["metric_checks"].items() if not value
        ]
        rejection_reason = (
            "The best variant failed the numeric SEC paper-sleeve gate on "
            f"{', '.join(failed_checks)}."
        )
    else:
        status = "accepted_candidate"
        rejection_reason = None

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "lane": "alpha_search",
        "hypothesis": (
            "SEC financial-report 10-Q paper entries may keep drifting when the "
            "initial broad-market backdrop is not adverse. A bounded additional "
            "paper-notional scalar for `form_base=10-Q` and "
            "`spy_t1_return >= -0.005` may improve default-off allocation without "
            "changing queue eligibility, ranking, hold days, or live orders."
        ),
        "change_summary": (
            "Sweep one paper-notional scalar for SEC financial-report paper-sleeve "
            "positions whose source candidate is a 10-Q and whose SPY T+1 return "
            "is at least -0.5%."
        ),
        "change_type": "alpha_search_sec_market_context_allocation",
        "component": "offline_sec_financial_report_paper_sleeve_replay",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "prior_trial_count": 0,
        "nearby_prior_experiments": [
            "exp-20260512-020",
            "exp-20260512-025",
            "exp-20260518-014",
            "exp-20260519-022",
            "exp-20260520-015",
            "exp-20260524-009",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "stable_sec_form_type_plus_market_context_field",
        "parameters": {
            "target_form_base_prefix": "10-Q",
            "target_spy_t1_return_min": TARGET_SPY_T1_RETURN_MIN,
            "target_scalar_variants": dict(TARGET_SCALARS),
            "best_variant": best_key,
            "best_scalar": best_scalar,
            "accepted_earnings_release_spy_context_scalar": (
                ACCEPTED_EARNINGS_RELEASE_SPY_CONTEXT_SCALAR
            ),
            "base_event_notional_usd": parent.DEFAULT_EVENT_NOTIONAL_USD,
            "periodic_report_scalar": parent.DEFAULT_PERIODIC_REPORT_NOTIONAL_SCALAR,
            "tenq_periodic_report_scalar": parent.ACCEPTED_10Q_PERIODIC_REPORT_SCALAR,
            "max_positions": parent.DEFAULT_MAX_POSITIONS,
            "anti_js": "No JavaScript was used.",
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows for core baseline, "
            "plus default-off SEC financial-report paper-sleeve replay over the "
            "same snapshots."
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
        "selection": selections[best_key],
        "gate": gate,
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "If accepted, promote only to the shared default-off SEC paper sleeve "
            "with parity tests; keep live/default orders disabled until forward "
            "replacement-value evidence matures."
            if gate["passed"]
            else "Do not retry nearby 10-Q market-context scalars on these frozen "
            "windows without new forward replacement-value evidence or a materially "
            "different stable disclosure-quality field."
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
                "capital allocation / event scoring: 10-Q periodic-report paper "
                "entries may deserve extra default-off notional when SPY T+1 "
                "context is not worse than -0.5%."
            ),
            "2_history_check": (
                "10-Q 2.0x notional was accepted in exp-20260512-020; 10-Q queue "
                "priority was rejected in exp-20260512-025; neutral and earnings "
                "SPY T+1 context scalars were accepted; broad bad-SPY context and "
                "SEC text-coverage missingness were rejected."
            ),
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": gate["rules"],
            "5_reproducibility": (
                f".venv\\Scripts\\python.exe -B quant\\experiments\\{STEM}.py"
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": (
                "This deterministic SEC context field does not change LLM prompts, "
                "ranking authority, or veto authority."
            ),
        },
        "related_files": [
            f"quant/experiments/{STEM}.py",
            _repo_rel(OUT_JSON),
            _repo_rel(DOC_LOG),
            _repo_rel(DOC_TICKET),
            _repo_rel(DOC_ARTIFACT),
            _repo_rel(EXPERIMENT_LOG_JSONL),
        ],
        "anti_js": "No JavaScript was used.",
    }
    return payload


def _experiment_log_entry(payload: dict[str, Any]) -> dict[str, Any]:
    selected = payload.get("best_variant")
    selected_summary = (payload.get("variant_summaries", {}) or {}).get(
        str(selected),
        {},
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload.get("timestamp"),
        "lane": "alpha_search",
        "status": payload.get("status"),
        "hypothesis": payload.get("hypothesis"),
        "change_type": payload.get("change_type"),
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "prior_trial_count": payload.get("prior_trial_count"),
        "nearby_prior_experiments": payload.get("nearby_prior_experiments"),
        "multiple_testing_risk_bucket": payload.get("multiple_testing_risk_bucket"),
        "new_evidence_type": payload.get("new_evidence_type"),
        "parameters": payload.get("parameters"),
        "backtest_protocol": payload.get("backtest_protocol"),
        "before_metrics": payload.get("before_metrics"),
        "after_metrics": selected_summary,
        "expected_value_score_delta": payload.get("expected_value_score_delta"),
        "total_pnl_delta": payload.get("total_pnl_delta"),
        "decision": payload.get("decision"),
        "rejection_reason": payload.get("rejection_reason"),
        "next_evidence_needed": payload.get("next_evidence_needed"),
        "production_impact": payload.get("production_impact"),
        "gate": payload.get("gate"),
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
            "artifact_file": _repo_rel(OUT_JSON),
            "result_file": _repo_rel(DOC_LOG),
            "updated_at": payload["timestamp"],
        },
    )
    DOC_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT.write_text(_artifact_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG_JSONL, _experiment_log_entry(payload))


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
                    "metric_gate_passed": payload["gate"]["metric_gate_passed"],
                    "gate_passed": payload["gate"]["passed"],
                    "causal_field_checks": payload["gate"]["causal_field_checks"],
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
