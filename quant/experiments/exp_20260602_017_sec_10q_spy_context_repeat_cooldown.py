"""exp-20260602-017: SEC 10-Q SPY-context repeat cooldown.

This alpha search tests one admission-control variable on the prior positive
but unpromoted SEC 10-Q/SPY-context paper sleeve. The 1.5x route from
exp-20260524-010 improved all three windows but failed concentration. This run
locks the form predicate, SPY T+1 threshold, notional scalar, hold, queue, and
production paths, and only adds a 90-calendar-day same-ticker cooldown before
SEC financial-report paper-sleeve admission.

No production orders, live watchlists, shared adapters, LLM/news paths, core
ranking, sizing, or exits are changed. No JavaScript is used.
"""

from __future__ import annotations

import copy
import json
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260602-017"
STEM = "sec_10q_spy_context_repeat_cooldown"
REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260524_010_sec_10q_spy_context_notional as tenq  # noqa: E402


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260602_017_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
NO_COOLDOWN_AGG_JSON = OUT_DIR / f"{STEM}_no_cooldown_1_50_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

COOLDOWN_DAYS = 90
BASELINE_SCALAR = 1.00
TARGET_SCALAR = 1.50
TARGET_SPY_T1_RETURN_MIN = tenq.TARGET_SPY_T1_RETURN_MIN
CHANGED_VARIABLE = "sec_10q_spy_context_same_ticker_cooldown_90d_v1"
TRIAL_FAMILY = "sec_10q_spy_context_repeat_cooldown_candidate_pool"
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
    return tenq._safe(value)


def _round(value: Any, ndigits: int = 6) -> float | None:
    return tenq._round(value, ndigits)


def _float(value: Any) -> float | None:
    return tenq._float(value)


def _repo_rel(path: Path | str) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


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


def _date10(value: Any) -> str:
    return str(value or "")[:10]


def _parse_date(value: Any) -> date | None:
    text = _date10(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _target_candidate(row: dict[str, Any]) -> bool:
    form = (
        row.get("form_base")
        or row.get("form_type")
        or row.get("form")
        or row.get("sec_form")
        or ""
    )
    if not str(form).upper().strip().startswith("10-Q"):
        return False
    spy_t1 = _float(row.get("spy_t1_return"))
    return spy_t1 is not None and spy_t1 >= TARGET_SPY_T1_RETURN_MIN


def _cooldown_date(row: dict[str, Any]) -> date | None:
    for key in ("shadow_entry_date", "t1_date", "usable_trade_date", "event_trading_date"):
        value = _parse_date(row.get(key))
        if value is not None:
            return value
    return None


def _apply_target_cooldown(exp100: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    filtered = copy.deepcopy(exp100)
    entries: list[dict[str, Any]] = []
    for label, window in (exp100.get("windows") or {}).items():
        for idx, row in enumerate(window.get("candidate_rows") or []):
            if not isinstance(row, dict) or not _target_candidate(row):
                continue
            when = _cooldown_date(row)
            if when is None:
                continue
            entries.append(
                {
                    "window": label,
                    "index": idx,
                    "ticker": str(row.get("ticker") or "").upper(),
                    "date": when,
                    "date_text": when.isoformat(),
                    "accession_number": row.get("accession_number"),
                    "spy_t1_return": row.get("spy_t1_return"),
                    "form_base": row.get("form_base") or row.get("form_type"),
                }
            )
    entries.sort(key=lambda row: (row["date"], row["ticker"], str(row.get("accession_number") or "")))

    last_admitted: dict[str, date] = {}
    excluded: list[dict[str, Any]] = []
    admitted: list[dict[str, Any]] = []
    excluded_keys: set[tuple[str, int]] = set()
    def public_item(item: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in item.items()
            if key != "date"
        }

    for item in entries:
        ticker = item["ticker"]
        prior = last_admitted.get(ticker)
        if prior is not None and (item["date"] - prior).days <= COOLDOWN_DAYS:
            excluded_keys.add((item["window"], item["index"]))
            excluded.append(
                {
                    **public_item(item),
                    "prior_admitted_date": prior.isoformat(),
                    "days_since_prior_admission": (item["date"] - prior).days,
                    "cooldown_days": COOLDOWN_DAYS,
                }
            )
            continue
        last_admitted[ticker] = item["date"]
        admitted.append(public_item(item))

    for label, window in (filtered.get("windows") or {}).items():
        rows = window.get("candidate_rows") or []
        window["candidate_rows"] = [
            row for idx, row in enumerate(rows) if (label, idx) not in excluded_keys
        ]
        summary = window.get("candidate_summary")
        if isinstance(summary, dict):
            summary["candidate_count_after_cooldown"] = len(window["candidate_rows"])
            summary["target_10q_spy_context_cooldown_excluded"] = sum(
                1 for row in excluded if row["window"] == label
            )

    by_window = Counter(row["window"] for row in entries)
    excluded_by_window = Counter(row["window"] for row in excluded)
    by_ticker = Counter(row["ticker"] for row in entries)
    excluded_by_ticker = Counter(row["ticker"] for row in excluded)
    diagnostics = {
        "cooldown_days": COOLDOWN_DAYS,
        "target_candidate_count": len(entries),
        "admitted_target_candidate_count": len(admitted),
        "excluded_target_candidate_count": len(excluded),
        "target_by_window": dict(sorted(by_window.items())),
        "excluded_by_window": dict(sorted(excluded_by_window.items())),
        "target_by_ticker": dict(sorted(by_ticker.items())),
        "excluded_by_ticker": dict(sorted(excluded_by_ticker.items())),
        "admitted_target_candidates": admitted,
        "excluded_target_candidates": excluded,
    }
    return filtered, diagnostics


def _variant_summary(row: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    summary = tenq._variant_summary(row, baseline)
    summary[CHANGED_VARIABLE] = True
    return summary


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
        "positive_incremental_pnl_by_ticker": {
            key: _round(value, 2) for key, value in sorted(positive_by_ticker.items())
        },
        "sample_rows": rows[:30],
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
    failed = [key for key, value in metric_checks.items() if not value]
    return {
        "aggregate_delta": aggregate,
        "by_window": summary["by_window"],
        "metric_checks": metric_checks,
        "failed_checks": failed,
        "metric_gate_passed": all(metric_checks.values()),
        "passed": all(metric_checks.values()),
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
                "aggregate EV/PnL positive versus scalar=1.0 baseline, at least "
                "two EV-improved windows, zero EV-regressed windows, and max "
                "drawdown worsening <= 0.5pp"
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
            "production_parity_guard": (
                "Uses production-visible SEC form_base, ticker, dates, and "
                "spy_t1_return fields only; no archive coverage or LLM field."
            ),
        },
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    gate = payload["gate"]
    aggregate = gate["aggregate_delta"]
    direct = payload["cooldown_delta_vs_no_cooldown_1_50"]
    lines = [
        f"# {EXPERIMENT_ID} SEC 10-Q SPY Context Repeat Cooldown",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Results vs Scalar 1.0 Baseline",
        "",
        f"- EV delta: `{aggregate.get('expected_value_score_sum_delta')}`",
        f"- PnL delta: `${aggregate.get('total_pnl_sum_delta')}`",
        f"- gate_passed: `{gate['passed']}`",
        f"- failed_checks: `{gate['failed_checks']}`",
        "",
        "## Cooldown Delta vs 1.5x No-Cooldown",
        "",
        f"- EV delta: `{direct.get('aggregate_delta', {}).get('expected_value_score_sum_delta')}`",
        f"- PnL delta: `${direct.get('aggregate_delta', {}).get('total_pnl_sum_delta')}`",
        "",
        "## Three-Window Deltas vs Scalar 1.0 Baseline",
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
            "## Cooldown Diagnostics",
            "",
            "```json",
            json.dumps(_safe(payload["cooldown_diagnostics"]), indent=2, sort_keys=True),
            "```",
            "",
            "## Gate",
            "",
            "```json",
            json.dumps(_safe(gate), indent=2, sort_keys=True),
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


def _gate2_position_fields() -> dict[str, Any]:
    return tenq.parent._gate2_open_position_field_check()


def build_payload() -> dict[str, Any]:
    timestamp = _utc_now()
    raw_exp100 = tenq.parent._load_exp100()
    current_queue = tenq.parent._filter_current_queue(raw_exp100)
    text_rows_by_accession, text_load_stats = tenq.parent._load_text_rows()
    exp100 = tenq.parent._annotate_language_fields(current_queue, text_rows_by_accession)
    filtered_exp100, cooldown_diagnostics = _apply_target_cooldown(exp100)
    text_coverage = tenq.parent._text_coverage_summary(exp100)
    gate2_fields = _gate2_position_fields()

    core_results: dict[str, dict[str, Any]] = {}
    for label, window in tenq.parent.WINDOWS.items():
        result = tenq.parent._run_core_backtest(window)
        core_results[label] = {
            "metrics": tenq.parent._core_metrics(result),
            "equity_curve": tenq.parent._normalise_core_curve(result),
        }

    baseline = tenq._run_variant(
        core_results=core_results,
        exp100=exp100,
        scalar=BASELINE_SCALAR,
    )
    no_cooldown_1_50 = tenq._run_variant(
        core_results=core_results,
        exp100=exp100,
        scalar=TARGET_SCALAR,
    )
    after = tenq._run_variant(
        core_results=core_results,
        exp100=filtered_exp100,
        scalar=TARGET_SCALAR,
    )
    summary = _variant_summary(after, baseline)
    no_cooldown_summary = _variant_summary(no_cooldown_1_50, baseline)
    direct_summary = _variant_summary(after, no_cooldown_1_50)
    selection = _selection_summary(
        tenq._target_positions(filtered_exp100, scalar=TARGET_SCALAR)
    )
    no_cooldown_selection = _selection_summary(
        tenq._target_positions(exp100, scalar=TARGET_SCALAR)
    )
    gate = _gate(summary, selection)
    actual_success = 1 if gate["passed"] else 0

    if gate["passed"]:
        status = "accepted_default_off"
        decision = "accepted_research_sec_10q_spy_context_repeat_cooldown"
        rejection_reason = None
    else:
        status = "rejected"
        decision = "rejected_sec_10q_spy_context_repeat_cooldown"
        rejection_reason = (
            "Cooldown route failed Gate 4 checks: "
            + ", ".join(gate["failed_checks"])
            if gate["failed_checks"]
            else "Cooldown route failed Gate 4."
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "lane": "alpha_search",
        "hypothesis": (
            "SEC 10-Q paper entries with non-adverse SPY T+1 context may retain "
            "the prior all-window lift while reducing concentration if repeated "
            "same-ticker 10-Q admissions are cooled down for 90 calendar days."
        ),
        "change_summary": (
            "Apply a 90-calendar-day same-ticker cooldown only to 10-Q candidates "
            "with spy_t1_return >= -0.005 before replaying the SEC financial-report "
            "default-off paper sleeve at the fixed prior 1.5x target scalar."
        ),
        "change_type": "default_off_paper_candidate_pool",
        "component": "offline_sec_financial_report_paper_sleeve_replay",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": "sec_10q_spy_context_90d_cooldown_v1",
        "prior_trial_count": 7,
        "nearby_prior_experiments": [
            "exp-20260512-020",
            "exp-20260512-025",
            "exp-20260519-008",
            "exp-20260524-005",
            "exp-20260524-010",
            "exp-20260511-114",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": (
            "production_visible_sec_form_type_plus_spy_context_with_repeat_"
            "concentration_control"
        ),
        "prediction": {
            "success_probability": 0.22,
            "expected_ev_delta": 0.15,
            "expected_pnl_delta": 3000.0,
            "main_failure_modes": [
                "removes_winners",
                "insufficient_adjusted_trades",
                "top5_concentration_persists",
                "window_regression",
                "drawdown_drift",
            ],
            "confidence_reason": (
                "The prior 10-Q/SPY context sleeve was positive in all three "
                "windows but failed concentration; a cooldown directly targets "
                "that failure without changing scalar or thresholds."
            ),
            "recorded_at": "2026-06-02T11:20:51+00:00",
            "brier_score": _round((0.22 - actual_success) ** 2, 6),
        },
        "parameters": {
            "target_form_base_prefix": "10-Q",
            "target_spy_t1_return_min": TARGET_SPY_T1_RETURN_MIN,
            "cooldown_days": COOLDOWN_DAYS,
            "baseline_scalar": BASELINE_SCALAR,
            "target_scalar_locked_from_prior_best_variant": TARGET_SCALAR,
            "base_event_notional_usd": tenq.parent.DEFAULT_EVENT_NOTIONAL_USD,
            "periodic_report_scalar": tenq.parent.DEFAULT_PERIODIC_REPORT_NOTIONAL_SCALAR,
            "tenq_periodic_report_scalar": tenq.parent.ACCEPTED_10Q_PERIODIC_REPORT_SCALAR,
            "max_positions": tenq.parent.DEFAULT_MAX_POSITIONS,
            "locked_variables": [
                "core signal generation",
                "core ranking",
                "core position sizing",
                "core exits",
                "LLM/news replay",
                "SEC queue source fields",
                "10-Q form predicate",
                "SPY T+1 threshold",
                "notional scalar",
                "production orders",
                "watchlists",
            ],
            "anti_js": "No JavaScript was used.",
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows for core baseline, "
            "plus default-off SEC financial-report paper-sleeve replay over the "
            "same snapshots."
        ),
        "windows": tenq.parent.WINDOWS,
        "candidate_counts_after_current_queue_filter": tenq.parent._candidate_counts(exp100),
        "candidate_counts_after_cooldown": tenq.parent._candidate_counts(filtered_exp100),
        "cooldown_diagnostics": cooldown_diagnostics,
        "text_load_stats": text_load_stats,
        "text_coverage_summary": text_coverage,
        "gate2_required_fields": gate2_fields,
        "before_metrics": baseline["aggregate"],
        "no_cooldown_1_50_metrics": no_cooldown_1_50["aggregate"],
        "after_metrics": after["aggregate"],
        "delta_metrics": {
            "aggregate": gate["aggregate_delta"],
            "by_window": gate["by_window"],
        },
        "cooldown_delta_vs_no_cooldown_1_50": {
            "aggregate_delta": direct_summary["aggregate_delta"],
            "by_window": direct_summary["by_window"],
        },
        "expected_value_score_delta": gate["aggregate_delta"].get(
            "expected_value_score_sum_delta"
        ),
        "total_pnl_delta": gate["aggregate_delta"].get("total_pnl_sum_delta"),
        "no_cooldown_1_50_summary_vs_baseline": no_cooldown_summary,
        "selection": selection,
        "no_cooldown_1_50_selection": no_cooldown_selection,
        "gate": gate,
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "If accepted, implement only through the shared default-off SEC paper "
            "sleeve adapter with explicit production/replay parity tests; keep "
            "live/default orders disabled until forward replacement-value evidence "
            "matures."
            if gate["passed"]
            else "Do not retry nearby 10-Q/SPY-context scalar or cooldown variants "
            "on these frozen windows without forward replacement-value evidence or "
            "a materially different stable disclosure-quality field."
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
            "promotion_blocker_if_positive": (
                "A shared SEC financial-report paper adapter path must apply the "
                "same cooldown before any daily report or production-facing paper "
                "state changes are retained."
            ),
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "candidate-pool / capital allocation: repeat 10-Q/SPY-context "
                "admissions can concentrate incremental PnL; a same-ticker "
                "cooldown may preserve lift with less tail concentration."
            ),
            "2_history_check": (
                "exp-20260524-010 found scalar=1.5 improved EV/PnL in all three "
                "windows but failed top5 contribution. 10-Q priority and 10-K "
                "exclusion were rejected; this does not retune form/SPY thresholds."
            ),
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": gate["rules"],
            "5_reproducibility": (
                f".venv\\Scripts\\python.exe -B quant\\experiments\\{Path(__file__).name}"
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "why_not_llm": (
                "This route uses deterministic SEC form/date/ticker and SPY context "
                "fields; LLM soft-ranking remains attribution-sparse."
            ),
        },
        "related_files": [
            _repo_rel(OUT_JSON),
            _repo_rel(BEFORE_AGG_JSON),
            _repo_rel(NO_COOLDOWN_AGG_JSON),
            _repo_rel(AFTER_AGG_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(DOC_TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(Path(__file__)),
        ],
    }
    return payload


def _ticket(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "title": "SEC 10-Q SPY-context repeat cooldown",
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": payload["lane"],
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "created_at": payload["timestamp"],
        "completed_at": payload["timestamp"],
        "result": {
            "artifact": _repo_rel(OUT_JSON),
            "before_aggregate": _repo_rel(BEFORE_AGG_JSON),
            "no_cooldown_1_50_aggregate": _repo_rel(NO_COOLDOWN_AGG_JSON),
            "after_aggregate": _repo_rel(AFTER_AGG_JSON),
            "log": _repo_rel(LOG_JSON),
            "report": _repo_rel(ARTIFACT_MD),
            "decision": payload["decision"],
            "gate": payload["gate"],
        },
    }


def _write_outputs(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(BEFORE_AGG_JSON, payload["before_metrics"])
    _write_json(NO_COOLDOWN_AGG_JSON, payload["no_cooldown_1_50_metrics"])
    _write_json(AFTER_AGG_JSON, payload["after_metrics"])
    ticket = _ticket(payload)
    _write_json(TICKET_JSON, ticket)
    _write_json(DOC_TICKET_JSON, ticket)
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "updated_at": payload["timestamp"],
        "result_files": [
            _repo_rel(OUT_JSON),
            _repo_rel(BEFORE_AGG_JSON),
            _repo_rel(NO_COOLDOWN_AGG_JSON),
            _repo_rel(AFTER_AGG_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(ARTIFACT_MD),
        ],
    }
    _write_json(MANIFEST_JSON, manifest)
    artifact = _artifact_markdown(payload)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(artifact, encoding="utf-8")
    CARD_MD.parent.mkdir(parents=True, exist_ok=True)
    CARD_MD.write_text("\n".join(artifact.splitlines()[:60]) + "\n", encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG_JSONL, payload)


def main() -> None:
    payload = build_payload()
    _write_outputs(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "expected_value_score_delta": payload["expected_value_score_delta"],
                "total_pnl_delta": payload["total_pnl_delta"],
                "cooldown_delta_vs_no_cooldown_1_50": payload[
                    "cooldown_delta_vs_no_cooldown_1_50"
                ]["aggregate_delta"],
                "gate": {
                    "passed": payload["gate"]["passed"],
                    "failed_checks": payload["gate"]["failed_checks"],
                    "metrics": payload["gate"]["metrics"],
                },
                "artifact": _repo_rel(ARTIFACT_MD),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
