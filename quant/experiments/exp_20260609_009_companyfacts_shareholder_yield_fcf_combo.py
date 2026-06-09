"""exp-20260609-009: Companyfacts shareholder-yield + FCF combo scout.

Replay-only alpha scout. It tests one fixed candidate-pool hypothesis:
within the accepted Fundamental Growth + RS paper source, keep rows that
simultaneously show filed-date-safe diluted-share contraction and positive
free-cash-flow yield. It changes no production code, shared adapter, live
orders, watchlists, LLM/news path, core ranking, sizing, or exits. No
JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant.experiments import exp_20260601_002_companyfacts_share_contraction_rs_candidate_pool as share_prev  # noqa: E402
from quant.experiments import exp_20260601_019_companyfacts_fcf_yield_rs_candidate_pool as fcf_prev  # noqa: E402


EXPERIMENT_ID = "exp-20260609-009"
STEM = "companyfacts_shareholder_yield_fcf_combo"
TRIAL_FAMILY = "companyfacts_shareholder_yield_fcf_combo"
TRIAL_VARIANT_ID = "companyfacts_shareholder_yield_cash_generation_combo_v1"
CHANGED_VARIABLE = "companyfacts_shareholder_yield_cash_generation_combo_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

SOURCE_EXPERIMENT_ID = share_prev.SOURCE_EXPERIMENT_ID
SOURCE_ARTIFACT = share_prev.SOURCE_ARTIFACT
REFERENCE_EXPERIMENT_ID = "exp-20260528-017"
REFERENCE_LOG_JSON = ROOT / "experiments" / "logs" / f"{REFERENCE_EXPERIMENT_ID}.json"

MAX_SHARE_YOY_CHANGE = share_prev.MAX_SHARE_YOY_CHANGE
MIN_FCF_YIELD = fcf_prev.MIN_FCF_YIELD
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
MANIFEST_JSON = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe(value: Any) -> Any:
    return share_prev._safe(value)


def _round(value: Any, digits: int = 4) -> Any:
    return share_prev._round(value, digits)


def _repo_rel(path: Path | str) -> str:
    return share_prev._repo_rel(path)


def _as_float(value: Any) -> float | None:
    return share_prev._as_float(value)


def _write_json(path: Path, payload: Any, *, sort_keys: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=sort_keys) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_ticket() -> dict[str, Any]:
    if not TICKET_JSON.exists():
        return {}
    return _load_json(TICKET_JSON)


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _select_target_trades(
    rows_by_window: OrderedDict[str, list[dict[str, Any]]],
    share_index: share_prev.ShareCountIndex,
    fcf_index: fcf_prev.FcfYieldIndex,
) -> tuple[OrderedDict[str, list[dict[str, Any]]], dict[str, Any]]:
    selected_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    filtered_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    share_status_counts_by_window: OrderedDict[str, dict[str, int]] = OrderedDict()
    fcf_status_counts_by_window: OrderedDict[str, dict[str, int]] = OrderedDict()
    joint_status_counts_by_window: OrderedDict[str, dict[str, int]] = OrderedDict()

    for label, rows in rows_by_window.items():
        selected: list[dict[str, Any]] = []
        filtered: list[dict[str, Any]] = []
        share_status_counts: Counter[str] = Counter()
        fcf_status_counts: Counter[str] = Counter()
        joint_status_counts: Counter[str] = Counter()

        for row in rows:
            ticker = str(row.get("ticker") or "").upper()
            signal_date = str(row.get("date") or row.get("signal_date") or "")[:10]
            share_context = dict(share_index.yoy_change(ticker, signal_date))
            fcf_context = dict(fcf_index.context(ticker, signal_date, row.get("close")))
            share_known_at = share_context.pop("known_at", None)
            fcf_known_at = fcf_context.pop("known_at", None)
            share_status = str(share_context.get("share_count_status") or "unknown")
            fcf_status = str(fcf_context.get("fcf_yield_status") or "unknown")
            share_status_counts[share_status] += 1
            fcf_status_counts[fcf_status] += 1

            share_passed = share_context.get("share_count_contraction_pass_v1") is True
            fcf_passed = fcf_context.get("fcf_yield_pass_v1") is True
            if share_passed and fcf_passed:
                joint_status_counts["both_passed"] += 1
            elif not share_passed and not fcf_passed:
                joint_status_counts["both_failed_or_unavailable"] += 1
            elif not share_passed:
                joint_status_counts["share_failed_or_unavailable"] += 1
            else:
                joint_status_counts["fcf_failed_or_unavailable"] += 1

            candidate = {
                **row,
                **share_context,
                **fcf_context,
                "ticker": ticker,
                "date": signal_date,
                "signal_date": signal_date,
                "rule_version": RULE_VERSION,
                "candidate_pool_rule_version": RULE_VERSION,
                "share_count_rule_version": RULE_VERSION,
                "fcf_yield_rule_version": RULE_VERSION,
                "strategy": "companyfacts_shareholder_yield_fcf_combo",
                "trade_enabled": False,
                "alters_orders": False,
                "source_experiment_id": SOURCE_EXPERIMENT_ID,
                "source_artifact": _repo_rel(SOURCE_ARTIFACT),
                "paper_pnl_source": "pnl_without_low_liability_support",
                "share_count_known_at": share_known_at,
                "fcf_yield_known_at": fcf_known_at,
            }
            if not share_passed:
                filtered.append({**candidate, "filter_reason": "share_count_contraction_not_available_or_not_met"})
                continue
            if not fcf_passed:
                filtered.append({**candidate, "filter_reason": "fcf_yield_not_available_or_below_floor"})
                continue
            pnl = _as_float(row.get("pnl_without_low_liability_support"))
            if pnl is None:
                pnl = _as_float(row.get("pnl"))
                candidate["paper_pnl_source"] = "pnl"
            if pnl is None:
                filtered.append({**candidate, "filter_reason": "missing_paper_pnl"})
                continue
            selected.append({**candidate, "pnl": _round(pnl, 2), "paper_pnl": _round(pnl, 2)})

        selected_by_window[label] = selected
        filtered_by_window[label] = filtered[:200]
        share_status_counts_by_window[label] = dict(sorted(share_status_counts.items()))
        fcf_status_counts_by_window[label] = dict(sorted(fcf_status_counts.items()))
        joint_status_counts_by_window[label] = dict(sorted(joint_status_counts.items()))

    diagnostics = {
        "source_target_trade_count_by_window": {
            label: len(rows) for label, rows in rows_by_window.items()
        },
        "selected_combo_trade_count_by_window": {
            label: len(rows) for label, rows in selected_by_window.items()
        },
        "share_count_status_counts_by_window": share_status_counts_by_window,
        "fcf_yield_status_counts_by_window": fcf_status_counts_by_window,
        "joint_status_counts_by_window": joint_status_counts_by_window,
        "filtered_candidates_sample_by_window": filtered_by_window,
    }
    return selected_by_window, diagnostics


def _aggregate_metrics(metrics_by_window: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = [metrics_by_window.get(label) or {} for label in share_prev.base.WINDOWS]
    return {
        "expected_value_score_sum": _round(sum(float(row.get("expected_value_score") or 0.0) for row in rows), 6),
        "total_pnl_sum": _round(sum(float(row.get("total_pnl") or 0.0) for row in rows), 2),
        "max_drawdown_pct_max": _round(max(float(row.get("max_drawdown_pct") or 0.0) for row in rows), 6),
    }


def _reference_comparison(after_metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not REFERENCE_LOG_JSON.exists():
        return {"available": False, "reason": "missing_exp_20260528_017_reference"}
    reference = _load_json(REFERENCE_LOG_JSON)
    ref_after = reference.get("after_metrics") or {}
    by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for label in share_prev.base.WINDOWS:
        ref = ref_after.get(label) or {}
        cur = after_metrics.get(label) or {}
        by_window[label] = {
            "expected_value_score_delta": _round(
                float(cur.get("expected_value_score") or 0.0)
                - float(ref.get("expected_value_score") or 0.0),
                6,
            ),
            "total_pnl_delta": _round(
                float(cur.get("total_pnl") or 0.0) - float(ref.get("total_pnl") or 0.0),
                2,
            ),
            "max_drawdown_pct_delta": _round(
                float(cur.get("max_drawdown_pct") or 0.0)
                - float(ref.get("max_drawdown_pct") or 0.0),
                6,
            ),
        }
    ref_agg = _aggregate_metrics(ref_after)
    cur_agg = _aggregate_metrics(after_metrics)
    return {
        "available": True,
        "reference_experiment_id": REFERENCE_EXPERIMENT_ID,
        "reference_after_aggregate": ref_agg,
        "current_after_aggregate": cur_agg,
        "by_window_delta_after_vs_accepted_low_liability": by_window,
        "aggregate_delta_after_vs_accepted_low_liability": {
            "expected_value_score_delta_sum": _round(
                float(cur_agg["expected_value_score_sum"]) - float(ref_agg["expected_value_score_sum"]),
                6,
            ),
            "total_pnl_delta_sum": _round(
                float(cur_agg["total_pnl_sum"]) - float(ref_agg["total_pnl_sum"]),
                2,
            ),
            "max_drawdown_pct_delta_max": _round(
                float(cur_agg["max_drawdown_pct_max"]) - float(ref_agg["max_drawdown_pct_max"]),
                6,
            ),
        },
    }


def _accepted_stack_gate(reference_comparison: dict[str, Any]) -> tuple[bool, list[str]]:
    failed: list[str] = []
    if not reference_comparison.get("available"):
        return False, ["missing_accepted_low_liability_reference"]
    aggregate = reference_comparison["aggregate_delta_after_vs_accepted_low_liability"]
    by_window = reference_comparison["by_window_delta_after_vs_accepted_low_liability"]
    if float(aggregate.get("expected_value_score_delta_sum") or 0.0) <= 0.0:
        failed.append("aggregate_ev_not_above_accepted_exp017")
    if float(aggregate.get("total_pnl_delta_sum") or 0.0) <= 0.0:
        failed.append("aggregate_pnl_not_above_accepted_exp017")
    if any(float(row.get("expected_value_score_delta") or 0.0) < 0.0 for row in by_window.values()):
        failed.append("window_ev_regressed_vs_accepted_exp017")
    if any(float(row.get("total_pnl_delta") or 0.0) < 0.0 for row in by_window.values()):
        failed.append("window_pnl_regressed_vs_accepted_exp017")
    return not failed, failed


def _gate4(
    aggregate: dict[str, Any],
    window_rows: OrderedDict[str, dict[str, Any]],
    target_summary: dict[str, Any],
    baseline_caveat: dict[str, Any],
    reference_comparison: dict[str, Any],
) -> dict[str, Any]:
    ev_windows_improved = [
        label
        for label, row in window_rows.items()
        if float(row["delta"].get("expected_value_score") or 0.0) > 0.0
    ]
    pnl_windows_improved = [
        label
        for label, row in window_rows.items()
        if float(row["delta"].get("total_pnl") or 0.0) > 0.0
    ]
    max_drawdown_delta = max(float(row["delta"].get("max_drawdown_pct") or 0.0) for row in window_rows.values())
    min_survival_rate = min(float(row["after"].get("survival_rate") or 0.0) for row in window_rows.values())
    target_trade_count = int(target_summary["target_trade_count"])
    target_window_count = sum(1 for rows in target_summary["trades_by_window"].values() if rows > 0)
    accepted_stack_passed, accepted_stack_failed = _accepted_stack_gate(reference_comparison)

    core_gates = OrderedDict(
        [
            ("aggregate_expected_value_positive", float(aggregate["delta"]["expected_value_score"]) > 0.0),
            ("aggregate_pnl_positive", float(aggregate["delta"]["total_pnl"]) > 0.0),
            ("all_windows_expected_value_improved", len(ev_windows_improved) == len(window_rows)),
            ("all_windows_pnl_improved", len(pnl_windows_improved) == len(window_rows)),
            ("target_trade_count_passed", target_trade_count >= MIN_TARGET_TRADES),
            ("target_window_count_passed", target_window_count >= MIN_TARGET_WINDOWS),
            ("drawdown_drift_passed", max_drawdown_delta <= MAX_DRAWDOWN_WORSE),
            ("survival_floor_passed", min_survival_rate >= 0.05),
            (
                "concentration_guard_passed",
                float(target_summary["max_single_positive_share"] or 0.0) <= MAX_SINGLE_POSITIVE_SHARE
                and float(target_summary["positive_pnl_hhi"] or 0.0) <= MAX_POSITIVE_HHI,
            ),
        ]
    )
    gates = OrderedDict(core_gates)
    gates["baseline_matches_docs_for_retention"] = bool(baseline_caveat["baseline_matches_docs"])
    gates["accepted_low_liability_comparator_passed"] = accepted_stack_passed
    core_failed = [name for name, passed in core_gates.items() if not passed]
    failed = [name for name, passed in gates.items() if not passed]
    core_gate4_passed = not core_failed
    metrics_gate4_passed = (
        core_gate4_passed
        and bool(baseline_caveat["baseline_matches_docs"])
        and accepted_stack_passed
    )
    promotable_now = False

    if metrics_gate4_passed:
        decision = "positive_replay_lead_not_promoted_requires_shared_adapter"
        rationale = (
            "The combo cleared the replay metrics and accepted comparator, but it "
            "remains a replay-only scout. Promotion would require the exact same "
            "logic in a shared default-off adapter and parity tests."
        )
    else:
        decision = "rejected_companyfacts_shareholder_yield_fcf_combo"
        rationale = (
            "The fixed share-contraction plus FCF-yield combo did not clear Gate 4 "
            "and/or the accepted low-liability comparator, so no production or "
            "shared policy change is retained."
        )

    return {
        "passed": promotable_now,
        "metrics_gate4_passed": metrics_gate4_passed,
        "core_gate4_passed": core_gate4_passed,
        "promotable_now": promotable_now,
        "decision": decision,
        "rationale": rationale,
        "gates": gates,
        "core_failed_gates": core_failed,
        "failed_gates": failed,
        "accepted_low_liability_failed_checks": accepted_stack_failed,
        "ev_windows_improved": ev_windows_improved,
        "pnl_windows_improved": pnl_windows_improved,
        "max_drawdown_delta": _round(max_drawdown_delta, 6),
        "min_survival_rate": _round(min_survival_rate, 6),
        "requires_shared_adapter_before_promotion": metrics_gate4_passed,
    }


def _post_run_reflection(payload: dict[str, Any]) -> dict[str, Any]:
    gate4 = payload["gate4"]
    target = payload["target_trade_summary"]
    failed = set(gate4["failed_gates"]) | set(gate4["accepted_low_liability_failed_checks"])
    if gate4["metrics_gate4_passed"]:
        why = (
            "The fixed intersection appears to preserve enough of the prior free-data "
            "fundamental edge while improving concentration and beating the accepted "
            "low-liability comparator. Because this run is replay-only, the result is "
            "only a lead."
        )
        retry = (
            "Implement the same selector as a shared default-off adapter covering "
            "historical replay and daily snapshots; do not alter thresholds first."
        )
    elif "target_trade_count_passed" in failed or "target_window_count_passed" in failed:
        why = (
            "The intersection was too sparse to evaluate as a durable candidate-pool "
            "edge. Combining two individually interesting Companyfacts fields removed "
            "too many source rows."
        )
        retry = (
            "Only retry with a genuinely broader free-data candidate pool or forward "
            "closed rows, not by loosening the same thresholds on these windows."
        )
    elif "concentration_guard_passed" in failed:
        why = (
            "The combo still failed the known Companyfacts failure mode: positive PnL "
            f"was too concentrated in a small number of tickers (max share "
            f"{target['max_single_positive_share']}, HHI {target['positive_pnl_hhi']})."
        )
        retry = (
            "Do not retry another APP/MU-dominated Companyfacts scalar intersection "
            "without an ex-ante diversification or capacity mechanism."
        )
    elif any(name.endswith("_accepted_exp017") or name.startswith("window_") for name in failed):
        why = (
            "The combo may improve versus the core baseline, but it does not beat the "
            "already accepted low-liability support stack. Replacing accepted support "
            "with a weaker fundamental filter would be opportunity-cost negative."
        )
        retry = (
            "Require new forward evidence or a different free-data mechanism; do not "
            "mine more same-sample Companyfacts value/quality intersections."
        )
    else:
        why = (
            "The predeclared combination failed one or more core Gate 4 constraints, "
            "so its apparent edge is not strong enough to retain."
        )
        retry = "Move to another alpha family with new evidence rather than retuning this pair."

    return {
        "why_result_happened": why,
        "forbidden_near_neighbor_retry": (
            "No same-window threshold/scalar retry of share contraction, FCF yield, "
            "earnings yield, or quality-gated top1 Companyfacts variants without "
            "new data or a new causal mechanism."
        ),
        "new_evidence_required": retry,
        "prediction_calibration": {
            "predicted_success_probability": (payload.get("ticket", {}).get("prediction") or {}).get(
                "success_probability"
            ),
            "actual_metrics_gate4_passed": gate4["metrics_gate4_passed"],
            "actual_promotable": gate4["promotable_now"],
            "failure_modes_observed": gate4["failed_gates"] + gate4["accepted_low_liability_failed_checks"],
        },
    }


def _artifact(payload: dict[str, Any]) -> str:
    agg = payload["aggregate"]
    gate4 = payload["gate4"]
    target = payload["target_trade_summary"]
    lines = [
        f"# {EXPERIMENT_ID}: Companyfacts Shareholder-Yield + FCF Combo",
        "",
        f"- decision: `{payload['decision']}`",
        f"- aggregate EV: `{agg['before']['expected_value_score']}` -> `{agg['after']['expected_value_score']}` "
        f"({agg['delta']['expected_value_score']:+.4f})",
        f"- aggregate PnL: `${agg['before']['total_pnl']:,.2f}` -> `${agg['after']['total_pnl']:,.2f}` "
        f"({agg['delta']['total_pnl']:+,.2f})",
        f"- target trades: `{target['target_trade_count']}`",
        f"- max single positive share: `{target['max_single_positive_share']}`",
        f"- positive PnL HHI: `{target['positive_pnl_hhi']}`",
        f"- failed gates: `{', '.join(gate4['failed_gates']) or 'none'}`",
        f"- accepted comparator failed checks: `{', '.join(gate4['accepted_low_liability_failed_checks']) or 'none'}`",
        "",
        "## Three-Window Result",
        "",
        "| window | EV before | EV after | EV delta | PnL delta | target trades |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, row in payload["window_results"].items():
        lines.append(
            f"| {label} | {row['before']['expected_value_score']:.4f} | "
            f"{row['after']['expected_value_score']:.4f} | "
            f"{row['delta']['expected_value_score']:+.4f} | "
            f"${row['delta']['total_pnl']:+,.2f} | {row['target_trade_count']} |"
        )
    lines.extend(
        [
            "",
            "## Accepted Comparator",
            "",
            "```json",
            json.dumps(
                _safe(payload["reference_accepted_low_liability_exp017_comparison"]),
                indent=2,
                sort_keys=True,
            ),
            "```",
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "This scout used only SEC Companyfacts rows filed on or before the signal "
            "date plus the source paper row's signal-day close. It made no live/default "
            "order, ranking, sizing, exit, LLM, news, watchlist, or shared adapter change.",
            "",
            "## Top Positive Contributors",
            "",
            "| ticker | trades | paper PnL | positive PnL share |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in target["ticker_rows"][:10]:
        lines.append(
            f"| {row['ticker']} | {row['trade_count']} | "
            f"${row['paper_pnl_usd']:,.2f} | {row['positive_pnl_share']} |"
        )
    lines.append("")
    return "\n".join(lines)


def _card(payload: dict[str, Any]) -> str:
    ticket = payload["ticket"]
    prediction = ticket.get("prediction") or {}
    return "\n".join(
        [
            "---",
            f'experiment_id: "{EXPERIMENT_ID}"',
            f'experiment_uid: "{ticket.get("experiment_uid")}"',
            f'status: "{payload["decision"]}"',
            'lane: "alpha_search"',
            'change_type: "default_off_candidate_pool_scout"',
            'mechanism_family: "free_data_companyfacts_fundamental_candidate_pool"',
            f'trial_family: "{TRIAL_FAMILY}"',
            f'trial_variant_id: "{TRIAL_VARIANT_ID}"',
            f'changed_variable: "{CHANGED_VARIABLE}"',
            'new_evidence_type: "fixed_intersection_of_two_prior_free_data_fundamental_edges"',
            f'created_at: "{ticket.get("created_at")}"',
            f'completed_at: "{payload["timestamp"]}"',
            'baseline_result_file: "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"',
            'tags:',
            '  - "alpha_search"',
            '  - "companyfacts_shareholder_yield_fcf_combo"',
            '  - "free_sec_companyfacts"',
            "---",
            "",
            f"# Experiment Card: {EXPERIMENT_ID}",
            "",
            "## Summary",
            "",
            payload["hypothesis"],
            "",
            "## Identity",
            "",
            f"- Status: `{payload['decision']}`",
            "- Lane: `alpha_search`",
            "- Change type: `default_off_candidate_pool_scout`",
            f"- Owner: `{ticket.get('owner')}`",
            f"- UID: `{ticket.get('experiment_uid')}`",
            "",
            "## Causal Variable",
            "",
            f"- Single causal variable: `{CHANGED_VARIABLE}`",
            f"- Changed variable: `{CHANGED_VARIABLE}`",
            "",
            "## Pre-Run Prediction",
            "",
            "```json",
            json.dumps(_safe(prediction), indent=2, ensure_ascii=True, sort_keys=True),
            "```",
            "",
            "## Closeout Notes",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Before artifact: `{_repo_rel(BEFORE_JSON)}`",
            f"- After artifact: `{_repo_rel(AFTER_JSON)}`",
            f"- Main blocker or acceptance basis: {payload['post_run_reflection']['why_result_happened']}",
            f"- Next retry requires: {payload['post_run_reflection']['new_evidence_required']}",
            "",
        ]
    )


def _ticket_result(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "metrics_gate4_passed": payload["gate4"]["metrics_gate4_passed"],
        "promotable_now": payload["gate4"]["promotable_now"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "report": _repo_rel(ARTIFACT_MD),
        "aggregate_expected_value_delta": payload["delta_metrics"]["aggregate"][
            "expected_value_score_delta_sum"
        ],
        "aggregate_strategy_total_pnl_delta": payload["delta_metrics"]["aggregate"][
            "total_pnl_delta_sum"
        ],
        "target_trade_count": payload["target_trade_summary"]["target_trade_count"],
        "max_single_positive_share": payload["target_trade_summary"]["max_single_positive_share"],
        "positive_pnl_hhi": payload["target_trade_summary"]["positive_pnl_hhi"],
        "failed_gates": payload["gate4"]["failed_gates"],
        "accepted_low_liability_failed_checks": payload["gate4"][
            "accepted_low_liability_failed_checks"
        ],
    }


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = dict(payload["ticket"])
    ticket["status"] = "completed"
    ticket["completed_at"] = payload["timestamp"]
    ticket["result"] = _ticket_result(payload)
    _write_json(TICKET_JSON, ticket)


def _log_row(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["decision"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": payload["mechanism_family"],
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate4": payload["gate4"],
        "gate_questions": payload["gate_questions"],
        "post_run_reflection": payload["post_run_reflection"],
        "production_impact": payload["production_impact"],
        "llm_metrics": payload["llm_metrics"],
        "artifact": _repo_rel(OUT_JSON),
        "report": _repo_rel(ARTIFACT_MD),
        "log": _repo_rel(LOG_JSON),
        "anti_js": payload["anti_js"],
    }


def _sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _update_manifest(payload: dict[str, Any]) -> None:
    manifest = _load_json(MANIFEST_JSON) if MANIFEST_JSON.exists() else {}
    manifest["completed_at"] = payload["timestamp"]
    manifest["result"] = _ticket_result(payload)
    files = {
        "runner": Path(__file__),
        "data": OUT_JSON,
        "before": BEFORE_JSON,
        "after": AFTER_JSON,
        "log": LOG_JSON,
        "artifact": ARTIFACT_MD,
        "card": CARD_MD,
        "ticket": TICKET_JSON,
    }
    manifest["files"] = {
        name: {
            "path": _repo_rel(path),
            "exists": path.exists(),
            "sha256": _sha256(path),
        }
        for name, path in files.items()
    }
    _write_json(MANIFEST_JSON, manifest)


def _build_payload() -> dict[str, Any]:
    gate2_open_positions = share_prev.base._audit_open_positions()
    if not gate2_open_positions.get("passed"):
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    source_payload = share_prev._load_source_payload()
    source_rows_by_window = share_prev._source_target_rows_by_window(source_payload)
    tickers = {
        str(row.get("ticker") or "").upper()
        for rows in source_rows_by_window.values()
        for row in rows
        if row.get("ticker")
    }
    share_index = share_prev.ShareCountIndex(tickers=tickers)
    fcf_index = fcf_prev.FcfYieldIndex(tickers=tickers)
    selected_by_window, selection_diagnostics = _select_target_trades(
        source_rows_by_window,
        share_index,
        fcf_index,
    )
    baselines = share_prev._load_baselines()
    window_rows = share_prev._run_windows(baselines, selected_by_window)
    aggregate = share_prev._aggregate(window_rows)
    target_summary = share_prev._target_summary(selected_by_window)
    baseline_caveat = fcf_prev._baseline_caveat(aggregate)
    before_metrics = OrderedDict((label, row["before"]) for label, row in window_rows.items())
    after_metrics = OrderedDict((label, row["after"]) for label, row in window_rows.items())
    delta_by_window = OrderedDict((label, row["delta"]) for label, row in window_rows.items())
    reference_comparison = _reference_comparison(after_metrics)
    gate4 = _gate4(
        aggregate,
        window_rows,
        target_summary,
        baseline_caveat,
        reference_comparison,
    )
    timestamp = _utc_now()
    ticket = _load_ticket()

    delta_metrics = {
        "aggregate": {
            "baseline_expected_value_score_sum": aggregate["before"]["expected_value_score"],
            "after_expected_value_score_sum": aggregate["after"]["expected_value_score"],
            "expected_value_score_delta_sum": aggregate["delta"]["expected_value_score"],
            "expected_value_score_delta_pct": aggregate["delta"]["expected_value_score_pct"],
            "baseline_total_pnl_sum": aggregate["before"]["total_pnl"],
            "after_total_pnl_sum": aggregate["after"]["total_pnl"],
            "total_pnl_delta_sum": aggregate["delta"]["total_pnl"],
            "total_pnl_delta_pct": aggregate["delta"]["strategy_total_pnl_pct"],
            "max_drawdown_delta_max": aggregate["delta"]["max_drawdown_pct"],
            "target_trade_count_sum": target_summary["target_trade_count"],
            "windows_ev_improved": len(gate4["ev_windows_improved"]),
            "windows_pnl_improved": len(gate4["pnl_windows_improved"]),
        },
        "by_window": delta_by_window,
    }
    decision = gate4["decision"]
    accepted = bool(gate4["promotable_now"])

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "accepted": accepted,
        "hypothesis": (
            "Entry / candidate-pool alpha: filed-date SEC Companyfacts rows showing "
            "both diluted-share contraction and >=3% free-cash-flow yield may isolate "
            "shareholder-yield, cash-generative growth+RS candidates and reduce the "
            "concentration that invalidated the individual Companyfacts value leads."
        ),
        "change_type": "default_off_candidate_pool_scout",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "free_data_companyfacts_fundamental_candidate_pool",
        "prior_trial_count": 4,
        "nearby_prior_experiments": [
            "exp-20260601-002",
            "exp-20260601-019",
            "exp-20260601-004",
            "exp-20260609-006",
        ],
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "fixed_intersection_of_two_prior_free_data_fundamental_edges",
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": share_prev.base.WINDOWS,
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "Selected source trades use already slippage-adjusted next-open entry "
                "and ten-trading-day exit PnL. The overlay is booked on each paper "
                "exit date against the canonical core baseline equity curve."
            ),
        },
        "parameters": {
            "source_experiment_id": SOURCE_EXPERIMENT_ID,
            "source_artifact": _repo_rel(SOURCE_ARTIFACT),
            "share_count_rule": (
                "latest shares_diluted filed <= signal_date versus same fiscal period "
                "prior fiscal year <= -0.5% YoY change"
            ),
            "fcf_yield_rule": (
                "latest filed operating_cash_flow minus abs(capex), annualized by "
                "duration_days, divided by signal-day close times latest shares_diluted; "
                "minimum >= 3%"
            ),
            "max_shares_diluted_yoy_change": MAX_SHARE_YOY_CHANGE,
            "min_fcf_yield": MIN_FCF_YIELD,
            "paper_pnl_source": "pnl_without_low_liability_support",
            "locked_variables": [
                "core order generation",
                "core ranking",
                "core sizing",
                "core exits",
                "LLM/news replay",
                "accepted alpha_score/source-consensus scalars",
                "accepted fundamental_growth_rs thresholds and top1 selection",
                "live/default orders",
            ],
            "acceptance": {
                "aggregate_ev_delta_gt": 0,
                "aggregate_pnl_delta_gt": 0,
                "ev_improved_windows": 3,
                "pnl_improved_windows": 3,
                "min_target_trades": MIN_TARGET_TRADES,
                "min_target_windows": MIN_TARGET_WINDOWS,
                "max_drawdown_worse": MAX_DRAWDOWN_WORSE,
                "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
                "max_positive_hhi": MAX_POSITIVE_HHI,
                "baseline_matches_docs_for_retention": True,
                "must_beat_accepted_exp017": True,
                "shared_adapter_required_for_promotion": True,
            },
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "entry / candidate_pool: shareholder-yield plus cash-generation "
                "evidence should prefer companies funding growth without dilution "
                "and with real cash support."
            ),
            "2_history_check": {
                "exp-20260601-002": "share contraction was strong but rejected for APP-dominated concentration",
                "exp-20260601-019": "FCF yield was positive but rejected for concentration and baseline caveat",
                "exp-20260601-004": "earnings yield was positive but concentration failed",
                "exp-20260609-006": "quality-gated top1 improved aggregate but failed late window, concentration, and accepted comparator",
                "current_difference": (
                    "This is not another threshold retune. It tests one fixed "
                    "intersection of two prior free-data mechanisms and requires "
                    "deconcentration plus beating the accepted exp-20260528-017 comparator."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "docs/backtesting.md three standard windows; positive aggregate EV/PnL; "
                "all three windows improve; >=20 target trades across all windows; "
                "trades in all three windows; drawdown drift <=0.5pp; survival >=5%; "
                "max single positive share <=0.40 and HHI <=0.30; baseline matches docs; "
                "after metrics beat accepted exp-20260528-017 in aggregate and no window regresses."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260609_009_companyfacts_shareholder_yield_fcf_combo.py"
            ),
        },
        "gate1": {
            "passed": True,
            "baseline_metrics": before_metrics,
            "baseline_artifact": _repo_rel(BEFORE_JSON),
            "baseline_caveat": baseline_caveat,
        },
        "gate2": {
            "passed": True,
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "source target_trades_by_window entry_date",
                "source target_trades_by_window exit_date",
                "source pnl_without_low_liability_support",
                "source target_trades_by_window close",
                "sec_companyfacts_selected shares_diluted filed <= signal_date",
                "sec_companyfacts_selected operating_cash_flow filed <= signal_date",
                "sec_companyfacts_selected capex filed <= signal_date",
            ],
        },
        "gate3": {
            "passed": gate4["min_survival_rate"] >= 0.05,
            "note": (
                "No core production filter was added. Survival rates are inherited "
                "from the canonical core baseline plus default-off paper overlay."
            ),
            "signals_generated_survived_by_window": {
                label: {
                    "signals_generated": row["after"].get("signals_generated"),
                    "signals_survived": row["after"].get("signals_survived"),
                    "survival_rate": row["after"].get("survival_rate"),
                }
                for label, row in window_rows.items()
            },
        },
        "gate4": gate4,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": delta_metrics,
        "aggregate": aggregate,
        "baseline_caveat": baseline_caveat,
        "window_results": window_rows,
        "target_trade_summary": target_summary,
        "target_trades_by_window": selected_by_window,
        "selection_diagnostics": selection_diagnostics,
        "reference_accepted_low_liability_exp017_comparison": reference_comparison,
        "production_impact": {
            "replay_only": True,
            "shared_policy_changed": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "parity_test_added": False,
            "trade_enabled": False,
            "alters_orders": False,
            "production_orders_changed": False,
            "production_signal_path_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "production_watchlist_changed": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": "LLM soft-ranking data was skipped; this tests a free deterministic SEC data edge.",
        },
        "ticket": ticket,
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(CARD_MD),
            _repo_rel(TICKET_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }
    payload["post_run_reflection"] = _post_run_reflection(payload)
    payload["interpretation"] = gate4["rationale"]
    payload["next_retry_requires"] = [
        payload["post_run_reflection"]["new_evidence_required"],
        payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
    ]
    return payload


def _persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(
        BEFORE_JSON,
        {
            **payload["aggregate"]["before"],
            "windows": payload["before_metrics"],
            "experiment_id": EXPERIMENT_ID,
            "artifact_role": "before_aggregate",
            "baseline_caveat": payload["baseline_caveat"],
        },
    )
    _write_json(
        AFTER_JSON,
        {
            **payload["aggregate"]["after"],
            "windows": payload["after_metrics"],
            "experiment_id": EXPERIMENT_ID,
            "artifact_role": "after_aggregate",
            "baseline_caveat": payload["baseline_caveat"],
        },
    )
    _write_json(LOG_JSON, payload)
    _write_text(ARTIFACT_MD, _artifact(payload))
    _write_text(CARD_MD, _card(payload))
    _update_ticket(payload)
    _upsert_jsonl(EXPERIMENT_LOG, _log_row(payload))
    _update_manifest(payload)


def main() -> int:
    payload = _build_payload()
    _persist(payload)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "accepted": payload["accepted"],
                    "expected_value_score_delta": payload["delta_metrics"]["aggregate"][
                        "expected_value_score_delta_sum"
                    ],
                    "total_pnl_delta": payload["delta_metrics"]["aggregate"]["total_pnl_delta_sum"],
                    "target_trade_count": payload["target_trade_summary"]["target_trade_count"],
                    "gate4": payload["gate4"],
                    "artifact": _repo_rel(ARTIFACT_MD),
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
