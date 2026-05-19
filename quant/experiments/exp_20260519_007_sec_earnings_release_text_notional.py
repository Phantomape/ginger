"""exp-20260519-007: SEC earnings-release text notional.

Alpha search on one production-visible field already emitted by the SEC
financial-report queue: ``text_event_type``.  On top of the accepted default-off
SEC paper stack through exp-20260518-014, test whether rows classified as
``earnings_release_text`` deserve a separate paper-notional scalar.

No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260519-007"
STEM = "exp_20260519_007_sec_earnings_release_text_notional"
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
    / f"{EXPERIMENT_ID}_sec_earnings_release_text_notional.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

ACCEPTED_NEUTRAL_UNDERREACTION_SCALAR = 2.0
ACCEPTED_NEUTRAL_UNDERREACTION_MAX_T1_EXCESS = 0.020
ACCEPTED_MARKET_CONTEXT_SCALAR = 1.5
ACCEPTED_MARKET_CONTEXT_SPY_T1_MIN = -0.005
TARGET_TEXT_EVENT_TYPE = "earnings_release_text"
BASELINE_TARGET_SCALAR = 1.0
TARGET_SCALAR_VARIANTS = (0.50, 0.75, 1.0, 1.10, 1.25, 1.50)
MIN_ADJUSTED_TRADES = 20
MIN_WINDOWS_PRESENT = 3
MAX_DRAWDOWN_WORSENING = 0.005
MAX_SINGLE_POSITIVE_PNL_SHARE = 0.65


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


def _source_candidate(position: dict[str, Any]) -> dict[str, Any]:
    candidate = position.get("source_candidate") or {}
    return candidate if isinstance(candidate, dict) else {}


def _candidate_text_event_type(candidate: dict[str, Any]) -> str:
    return str(candidate.get("text_event_type") or "missing")


def _is_target_position(position: dict[str, Any]) -> bool:
    return _candidate_text_event_type(_source_candidate(position)) == TARGET_TEXT_EVENT_TYPE


def _accepted_neutral_underreaction(candidate: dict[str, Any]) -> bool:
    if str(candidate.get("language_bucket") or "") != "neutral_or_mixed_language":
        return False
    t1_excess = _float(candidate.get("t1_excess_return_vs_spy"))
    return (
        t1_excess is not None
        and t1_excess <= ACCEPTED_NEUTRAL_UNDERREACTION_MAX_T1_EXCESS
    )


def _accepted_market_context(candidate: dict[str, Any]) -> bool:
    if not _accepted_neutral_underreaction(candidate):
        return False
    spy_t1 = _float(candidate.get("spy_t1_return"))
    return spy_t1 is not None and spy_t1 >= ACCEPTED_MARKET_CONTEXT_SPY_T1_MIN


def _notional_for_position(
    position: dict[str, Any],
    *,
    target_scalar: float,
) -> tuple[float, float, str]:
    candidate = _source_candidate(position)
    _, scalar, rule = parent._base_notional_for_position(position)
    rule_parts = [rule]
    if _accepted_neutral_underreaction(candidate):
        scalar *= ACCEPTED_NEUTRAL_UNDERREACTION_SCALAR
        rule_parts.append("neutral_underreaction_scalar")
        if _accepted_market_context(candidate):
            scalar *= ACCEPTED_MARKET_CONTEXT_SCALAR
            rule_parts.append("neutral_underreaction_spy_t1_context_scalar")
    if _candidate_text_event_type(candidate) == TARGET_TEXT_EVENT_TYPE:
        scalar *= target_scalar
        rule_parts.append("earnings_release_text_scalar")
    return float(parent.DEFAULT_EVENT_NOTIONAL_USD) * scalar, scalar, "+".join(rule_parts)


def _patched_parent_notional(target_scalar: float):
    def patched_notional(
        position: dict[str, Any],
        *,
        neutral_language_scalar: float,
    ) -> tuple[float, float, str]:
        del neutral_language_scalar
        return _notional_for_position(position, target_scalar=target_scalar)

    return patched_notional


def _run_variant(
    *,
    core_results: dict[str, dict[str, Any]],
    exp100: dict[str, Any],
    target_scalar: float,
) -> dict[str, Any]:
    original_notional = parent._notional_for_position
    parent._notional_for_position = _patched_parent_notional(target_scalar)
    try:
        row = parent._run_variant(
            core_results=core_results,
            exp100=exp100,
            neutral_language_scalar=1.0,
        )
    finally:
        parent._notional_for_position = original_notional
    row["earnings_release_text_notional_scalar"] = target_scalar
    return row


def _pnl_for_position(
    position: dict[str, Any],
    *,
    target_scalar: float,
    closed: bool,
) -> float:
    adjusted_notional, _, _ = _notional_for_position(
        position,
        target_scalar=target_scalar,
    )
    if closed:
        net_return = _float(position.get("net_return_pct")) or 0.0
        return adjusted_notional * (net_return / 100.0)
    source_notional = _float(position.get("notional"))
    source_pnl = _float(position.get("net_pnl_if_closed_now")) or 0.0
    if not source_notional or source_notional <= 0:
        return 0.0
    return adjusted_notional * (source_pnl / source_notional)


def _closed_positions_for_scalar(
    exp100: dict[str, Any],
    *,
    target_scalar: float,
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
            if not _is_target_position(position):
                continue
            candidate = _source_candidate(position)
            baseline_pnl = _pnl_for_position(
                position,
                target_scalar=BASELINE_TARGET_SCALAR,
                closed=True,
            )
            adjusted_pnl = _pnl_for_position(
                position,
                target_scalar=target_scalar,
                closed=True,
            )
            notional, scalar, rule = _notional_for_position(
                position,
                target_scalar=target_scalar,
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
                    "text_event_type": candidate.get("text_event_type"),
                    "t1_excess_return_vs_spy": candidate.get("t1_excess_return_vs_spy"),
                    "t1_return": candidate.get("t1_return"),
                    "spy_t1_return": candidate.get("spy_t1_return"),
                    "event_notional_rule": rule,
                    "event_notional_scalar": scalar,
                    "notional": _round(notional, 2),
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
        }
    return checks


def _variant_summary(row: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    aggregate_delta = parent._delta(row["aggregate"], baseline["aggregate"])
    by_window = _window_deltas(row, baseline)
    return {
        "earnings_release_text_notional_scalar": row[
            "earnings_release_text_notional_scalar"
        ],
        "aggregate_delta": aggregate_delta,
        "by_window": by_window,
        "ev_positive_windows": sum(
            1
            for item in by_window.values()
            if (item["expected_value_score"] or 0.0) > 0
        ),
        "ev_regressed_windows": sum(
            1
            for item in by_window.values()
            if (item["expected_value_score"] or 0.0) < 0
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


def _target_coverage_summary(exp100: dict[str, Any]) -> dict[str, Any]:
    aggregate = Counter()
    by_window: dict[str, Any] = {}
    for label, window in exp100.get("windows", {}).items():
        rows = window.get("candidate_rows") or []
        counts = Counter(str(row.get("text_event_type") or "missing") for row in rows)
        aggregate.update(counts)
        by_window[label] = {
            "candidate_count": len(rows),
            "text_event_type": dict(sorted(counts.items())),
        }
    return {"aggregate": dict(sorted(aggregate.items())), "by_window": by_window}


def _gate(summary: dict[str, Any], selection: dict[str, Any]) -> dict[str, Any]:
    aggregate = summary["aggregate_delta"]
    metric_gate_passed = (
        (aggregate.get("expected_value_score_sum_delta") or 0.0) > 0
        and (aggregate.get("total_pnl_sum_delta") or 0.0) > 0
        and summary["ev_positive_windows"] == 3
        and summary["ev_regressed_windows"] == 0
        and summary["pnl_positive_windows"] == 3
        and summary["pnl_regressed_windows"] == 0
        and summary["max_drawdown_delta_max"] <= MAX_DRAWDOWN_WORSENING
    )
    sample_guard_passed = (
        selection["adjusted_trade_count"] >= MIN_ADJUSTED_TRADES
        and selection["windows_present"] >= MIN_WINDOWS_PRESENT
    )
    concentration = selection["max_single_positive_pnl_share"]
    concentration_guard_passed = (
        concentration is None or concentration <= MAX_SINGLE_POSITIVE_PNL_SHARE
    )
    return {
        "aggregate_delta": aggregate,
        "by_window": summary["by_window"],
        "metric_gate_passed": metric_gate_passed,
        "sample_guard_passed": sample_guard_passed,
        "concentration_guard_passed": concentration_guard_passed,
        "passed": metric_gate_passed and sample_guard_passed and concentration_guard_passed,
        "rules": {
            "metric_gate": (
                "aggregate EV/PnL positive, all three windows EV/PnL positive, "
                "no window regression, and max drawdown worsening <= 0.5pp"
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
    aggregate = payload["gate"]["aggregate_delta"]
    lines = [
        f"# {EXPERIMENT_ID} SEC Earnings-Release Text Notional",
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
    raw_exp100 = parent._load_exp100()
    current_queue = parent._filter_current_queue(raw_exp100)
    text_rows_by_accession, text_load_stats = parent._load_text_rows()
    exp100 = parent._annotate_language_fields(current_queue, text_rows_by_accession)
    text_coverage = parent._text_coverage_summary(exp100)
    target_coverage = _target_coverage_summary(exp100)
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
    for scalar in TARGET_SCALAR_VARIANTS:
        key = f"earnings_release_text_scalar_{scalar:.2f}"
        row = _run_variant(
            core_results=core_results,
            exp100=exp100,
            target_scalar=scalar,
        )
        variants[key] = row

    baseline_key = f"earnings_release_text_scalar_{BASELINE_TARGET_SCALAR:.2f}"
    baseline = variants[baseline_key]
    for key, row in variants.items():
        summaries[key] = _variant_summary(row, baseline)

    non_baseline = [key for key in summaries if key != baseline_key]
    passed = []
    for key in non_baseline:
        scalar = float(summaries[key]["earnings_release_text_notional_scalar"])
        selection = _selection_summary(
            _closed_positions_for_scalar(exp100, target_scalar=scalar)
        )
        if _gate(summaries[key], selection)["passed"]:
            passed.append(key)
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
    best_scalar = float(best_summary["earnings_release_text_notional_scalar"])
    selection = _selection_summary(
        _closed_positions_for_scalar(exp100, target_scalar=best_scalar)
    )
    gate = _gate(best_summary, selection)
    status = "accepted_candidate" if gate["passed"] else "rejected"
    decision = (
        "accepted_candidate_sec_earnings_release_text_notional"
        if gate["passed"]
        else "rejected_sec_earnings_release_text_notional"
    )
    interpretation = (
        "Earnings-release text rows improved with a production-visible paper "
        "notional scalar on top of the accepted SEC stack. Promotion requires "
        "moving the same rule into the shared default-off SEC sleeve and adding "
        "focused parity tests before it is treated as accepted."
        if gate["passed"]
        else "Earnings-release text paper-notional scalars did not clear the "
        "three-window Gate 4 standard on top of the accepted SEC stack."
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "lane": "alpha_search",
        "hypothesis": (
            "Inside the accepted SEC financial-report T+1 paper sleeve, "
            "`text_event_type=earnings_release_text` should be a cleaner "
            "post-earnings drift source than miscellaneous Item 2.02 text or "
            "missing-text rows, so a bounded paper-notional scalar may improve "
            "allocation without changing queue eligibility, capacity, hold days, "
            "or live orders."
        ),
        "change_summary": (
            "Sweep a paper-notional scalar for SEC financial-report paper rows "
            "whose production-visible `text_event_type` is `earnings_release_text`."
        ),
        "change_type": "alpha_search_semantic_notional_allocation",
        "component": "quant/sec_financial_report_event_sleeve.py",
        "changed_variable": "sec_financial_report_earnings_release_text_notional_scalar",
        "single_causal_variable": "earnings-release text-event-type paper-notional scalar",
        "parameters": {
            "target_text_event_type": TARGET_TEXT_EVENT_TYPE,
            "baseline_target_scalar": BASELINE_TARGET_SCALAR,
            "target_scalar_variants": list(TARGET_SCALAR_VARIANTS),
            "best_target_scalar": best_scalar,
            "accepted_neutral_underreaction_scalar": ACCEPTED_NEUTRAL_UNDERREACTION_SCALAR,
            "accepted_neutral_underreaction_max_t1_excess": ACCEPTED_NEUTRAL_UNDERREACTION_MAX_T1_EXCESS,
            "accepted_market_context_scalar": ACCEPTED_MARKET_CONTEXT_SCALAR,
            "accepted_market_context_spy_t1_min": ACCEPTED_MARKET_CONTEXT_SPY_T1_MIN,
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
            "plus production SEC financial-report paper-sleeve replay over the "
            "same snapshots."
        ),
        "windows": parent.WINDOWS,
        "candidate_counts_after_current_queue_filter": parent._candidate_counts(exp100),
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
        "interpretation": interpretation,
        "rejection_reason": None if gate["passed"] else interpretation,
        "next_evidence_needed": (
            "If promoted, implement only in shared default-off SEC sleeve code "
            "using the production `text_event_type` candidate field; keep live "
            "orders disabled until forward replacement-value evidence matures."
            if gate["passed"]
            else "Do not retry nearby SEC text-event-type scalar splits on the "
            "frozen sample without a new semantic discriminator or forward "
            "replacement-value evidence."
        ),
        "production_impact": {
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
            "promotion_requirement": (
                "Positive result requires shared sec_financial_report_event_sleeve.py "
                "implementation and focused parity tests before final acceptance."
            ),
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "capital allocation: scale the SEC financial-report paper sleeve "
                "only when `text_event_type` identifies an earnings-release text."
            ),
            "2_history_check": (
                "Recent SEC branches covered neutral underreaction, SPY market "
                "context, ticker T+1 floors, positive/negative language, AI "
                "credibility, cash-flow forecast, and operational-fact density. "
                "No current experiment isolated `text_event_type=earnings_release_text` "
                "on top of the accepted exp-20260518-014 stack."
            ),
            "3_single_causal_variable": (
                "sec_financial_report_earnings_release_text_notional_scalar"
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
                "LLM soft-ranking remains sparse; this tests a deterministic "
                "production-visible SEC event-type field."
            ),
        },
        "why_not_other_changes": (
            "State-surface near-high/profile mining is now anti-repeat without a "
            "new field, LLM soft-ranking data remains sparse, and noisy ticker-pool "
            "expansion is not needed for this SEC sleeve test."
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
