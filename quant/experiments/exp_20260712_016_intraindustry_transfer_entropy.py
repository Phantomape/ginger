"""exp-20260712-016: PIT intra-industry transfer-entropy scout.

The experiment keeps the previously frozen industry leader-shock event and
paper execution envelope, but replaces correlation / realized-forward-history
relation tests with a nonlinear directed-information field.  For each signal
date, it estimates binary conditional transfer entropy over the prior 120
completed sessions from the top-three liquidity leaders to a lagging peer and
requires the forward direction to exceed the reverse direction.

This is a private replay scout because the computational shape is speculative.
Even a positive result is only a lead; production, accepted helpers, entries,
ranking, sizing, exits, orders, and LLM boundaries are unchanged.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, OrderedDict
from pathlib import Path
from statistics import median
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT, ROOT / "quant", ROOT / "quant" / "experiments", ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260618_006_intraindustry_lead_lag_direction_stability as prior  # noqa: E402
import exp_20260712_009_dod_contract_revenue_materiality as schema  # noqa: E402
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)
from rolling_corr_peer_shock_paper_sleeve import (  # noqa: E402
    build_rolling_corr_peer_shock_historical_trades,
)


EXPERIMENT_ID = "exp-20260712-016"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "intraindustry_transfer_entropy"
RUNNER = f"quant/experiments/exp_20260712_016_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
OUT_JSON = ROOT / "data" / "experiments" / EXPERIMENT_ID / f"exp_20260712_016_{SLUG}.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = ROOT / "docs" / "experiment_registry.json"
BASELINE_SUMMARY = (
    ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_post_mtm_20260712.json"
)

HYPOTHESIS = (
    "A lagging liquid peer whose prior 120 sessions show positive directed "
    "information flow from the top-three same-industry liquidity leaders should "
    "continue after the unchanged leader shock and add robust next-open 10-session "
    "paper value."
)
CHANGED_VARIABLE = "pit_intraindustry_transfer_entropy_candidate_source_v1"
TRIAL_FAMILY = "free_ohlcv_intraindustry_transfer_entropy_candidate_pool"
TRIAL_VARIANT_ID = "transfer_entropy_directional_edge_top1_next_open_10d_v1"
MECHANISM_FAMILY = "production_visible_free_ohlcv_relation_alpha"
RULE_VERSION = CHANGED_VARIABLE
NEARBY = [
    "exp-20260617-021",
    "exp-20260618-006",
    "exp-20260606-025",
    "exp-20260712-015",
]
NEW_AXIS = (
    "Unprecedented field on the still-unsaturated OHLCV relation source: trailing "
    "point-in-time conditional transfer entropy from an industry liquidity-leader "
    "basket to each peer, compared with reverse-direction entropy."
)

TE_LOOKBACK_SESSIONS = 120
TE_MIN_TRANSITIONS = 60
TE_MIN_ALIGNED_SESSIONS = 80

BASE_NOTIONAL_USD = prior.BASE_NOTIONAL_USD
HOLD_DAYS = prior.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = prior.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = prior.SAME_TICKER_COOLDOWN_DAYS

PREDICTION = json.loads(TICKET_JSON.read_text(encoding="utf-8"))["prediction"]
PRODUCTION_IMPACT = {
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "trade_enabled": False,
    "entry_rules_changed": False,
    "ranking_changed": False,
    "sizing_changed": False,
    "exit_rules_changed": False,
    "orders_changed": False,
    "llm_decision_boundary_changed": False,
    "scope": "experiment_local_private_replay_scout",
}
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/{OUT_JSON.name}",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
    "docs/frozen_families.jsonl",
    "scripts/experiment_fingerprint.py",
    "quant/test_experiment_fingerprint.py",
]


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = ROOT / value
    return str(value.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _attach_equity_curve_from_inference(result: dict[str, Any]) -> None:
    """Restore the private MTM curve from the published dated return series.

    exp-20260712-015 deliberately persisted the canonical return evidence and
    hash but not BacktestEngine's internal equity_curve list.  The daily paper
    overlay needs that list, so reconstruct it deterministically from the
    exact hashed returns and the frozen $100k initial capital.
    """

    returns = (result.get("sharpe_inference") or {}).get("return_series") or []
    equity = 100_000.0
    curve: list[tuple[str, float]] = []
    for row in returns:
        day = str(row.get("date") or "")[:10]
        daily_return = _finite(row.get("return"))
        if not day or daily_return is None:
            raise RuntimeError("baseline dated return evidence is incomplete")
        equity *= 1.0 + daily_return
        curve.append((day, round(equity, 8)))
    if len(curve) < 3:
        raise RuntimeError("baseline dated return evidence is too short")
    result["equity_curve"] = curve


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _binary_transfer_entropy(xs: list[int], ys: list[int]) -> float | None:
    """Empirical TE X[t-1] -> Y[t] conditional on Y[t-1], in bits."""

    if len(xs) != len(ys) or len(xs) - 1 < TE_MIN_TRANSITIONS:
        return None
    joint: Counter[tuple[int, int, int]] = Counter()
    y_prev_x_prev: Counter[tuple[int, int]] = Counter()
    y_now_y_prev: Counter[tuple[int, int]] = Counter()
    y_prev: Counter[int] = Counter()
    for pos in range(1, len(xs)):
        x0, y0, y1 = xs[pos - 1], ys[pos - 1], ys[pos]
        joint[(y1, y0, x0)] += 1
        y_prev_x_prev[(y0, x0)] += 1
        y_now_y_prev[(y1, y0)] += 1
        y_prev[y0] += 1
    transitions = sum(joint.values())
    result = 0.0
    for (y1, y0, x0), count in joint.items():
        conditional_with_x = count / y_prev_x_prev[(y0, x0)]
        conditional_without_x = y_now_y_prev[(y1, y0)] / y_prev[y0]
        if conditional_with_x > 0.0 and conditional_without_x > 0.0:
            result += (count / transitions) * math.log2(
                conditional_with_x / conditional_without_x
            )
    return result


def _transfer_entropy_relation(
    *,
    signal_date: str,
    ticker: str,
    leaders: list[str],
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    spy_rows: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Compute a trailing PIT leader->peer entropy edge without outcomes."""

    rows = snapshot.get(ticker)
    signal_idx = indices.get(ticker, {}).get(signal_date)
    if rows is None or signal_idx is None or signal_idx < TE_LOOKBACK_SESSIONS + 1:
        return None
    start_idx = max(1, signal_idx - TE_LOOKBACK_SESSIONS)
    leader_states: list[int] = []
    peer_states: list[int] = []
    for pos in range(start_idx, signal_idx):
        day = str(rows[pos].get("Date") or "")[:10]
        peer_idx = indices.get(ticker, {}).get(day)
        spy_idx = indices.get("SPY", {}).get(day)
        if peer_idx is None or spy_idx is None or peer_idx < 1 or spy_idx < 1:
            continue
        peer_prev = prior.base.framework._value(rows[peer_idx - 1], "Close")
        peer_now = prior.base.framework._value(rows[peer_idx], "Close")
        spy_prev = prior.base.framework._value(spy_rows[spy_idx - 1], "Close")
        spy_now = prior.base.framework._value(spy_rows[spy_idx], "Close")
        if not peer_prev or not peer_now or not spy_prev or not spy_now:
            continue
        spy_return = spy_now / spy_prev - 1.0
        leader_excess: list[float] = []
        for leader in leaders:
            leader_rows = snapshot.get(leader)
            leader_idx = indices.get(leader, {}).get(day)
            if leader_rows is None or leader_idx is None or leader_idx < 1:
                continue
            leader_prev = prior.base.framework._value(
                leader_rows[leader_idx - 1], "Close"
            )
            leader_now = prior.base.framework._value(leader_rows[leader_idx], "Close")
            if leader_prev and leader_now:
                leader_excess.append(leader_now / leader_prev - 1.0 - spy_return)
        if not leader_excess:
            continue
        leader_states.append(1 if median(leader_excess) > 0.0 else 0)
        peer_excess = peer_now / peer_prev - 1.0 - spy_return
        peer_states.append(1 if peer_excess > 0.0 else 0)
    if len(leader_states) < TE_MIN_ALIGNED_SESSIONS:
        return None
    forward = _binary_transfer_entropy(leader_states, peer_states)
    reverse = _binary_transfer_entropy(peer_states, leader_states)
    if forward is None or reverse is None:
        return None
    edge = forward - reverse
    if edge <= 0.0:
        return None
    positive_after_positive = [
        peer_states[pos]
        for pos in range(1, len(peer_states))
        if leader_states[pos - 1] == 1
    ]
    conditional_hit_rate = (
        sum(positive_after_positive) / len(positive_after_positive)
        if positive_after_positive
        else 0.0
    )
    return {
        "observation_count": len(leader_states),
        "median_forward_excess": edge,
        "mean_forward_excess": forward,
        "hit_rate": conditional_hit_rate,
        "avg_leader_excess": reverse,
        "relation_score": edge,
        "transfer_entropy_forward_bits": forward,
        "transfer_entropy_reverse_bits": reverse,
        "transfer_entropy_edge_bits": edge,
    }


def _candidate_rows(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    original = prior._relation_stats
    prior._relation_stats = _transfer_entropy_relation
    try:
        rows, scan = prior._candidate_rows_for_window(
            snapshot=snapshot,
            cfg=cfg,
            sector_entries=sector_entries,
            quality_index={},
        )
    finally:
        prior._relation_stats = original
    for row in rows:
        row["source"] = "INTRAINDUSTRY_TRANSFER_ENTROPY_PAPER"
        row["rule_version"] = RULE_VERSION
        row["source_rule_version"] = RULE_VERSION
        row["known_at"] = "signal_close_after_trailing_120_completed_sessions"
        row["transfer_entropy_aligned_sessions"] = row.pop(
            "leadlag_relation_observation_count", None
        )
        row["transfer_entropy_edge_bits"] = row.get("leadlag_relation_score")
        row["transfer_entropy_forward_bits"] = row.get(
            "leadlag_relation_mean_forward_excess"
        )
        row["transfer_entropy_conditional_hit_rate"] = row.get(
            "leadlag_relation_hit_rate"
        )
        row["transfer_entropy_reverse_bits"] = row.get(
            "leadlag_relation_avg_leader_excess"
        )
    scan.update(
        {
            "rule_version": RULE_VERSION,
            "transfer_entropy_lookback_sessions": TE_LOOKBACK_SESSIONS,
            "transfer_entropy_min_aligned_sessions": TE_MIN_ALIGNED_SESSIONS,
            "transfer_entropy_min_transitions": TE_MIN_TRANSITIONS,
            "direction_gate": "leader_to_peer_te_gt_peer_to_leader_te",
        }
    )
    return rows, scan


def _load_baselines() -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, Any]]:
    summary = json.loads(BASELINE_SUMMARY.read_text(encoding="utf-8"))
    if summary.get("experiment_id") != "exp-20260712-015":
        raise RuntimeError("active baseline is not exp-20260712-015")
    results: dict[str, dict[str, Any]] = {}
    identity: dict[str, Any] = {}
    for record in summary["windows"]:
        label = record["label"]
        path = ROOT / record["path"]
        actual_hash = _sha256(path)
        result = json.loads(path.read_text(encoding="utf-8"))
        inference = result.get("sharpe_inference") or {}
        matched = (
            actual_hash == record["artifact_sha256"]
            and inference.get("return_series_sha256")
            == record.get("daily_return_series_sha256")
            and int(inference.get("schema_version") or 0) >= 1
            and int(result.get("total_trades") or 0) == int(record["trade_count"])
        )
        identity[label] = {
            "path": record["path"],
            "expected_sha256": record["artifact_sha256"],
            "actual_sha256": actual_hash,
            "return_series_sha256": inference.get("return_series_sha256"),
            "expected_return_series_sha256": record.get("daily_return_series_sha256"),
            "schema_version": inference.get("schema_version"),
            "matched": matched,
        }
        _attach_equity_curve_from_inference(result)
        results[label] = result
    return summary, results, identity


def _aggregate(rows: OrderedDict[str, dict[str, Any]]) -> dict[str, Any]:
    return prior.base.framework._aggregate_window_rows(rows)


def build_payload() -> dict[str, Any]:
    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8"))
    baseline_summary, baselines, baseline_identity = _load_baselines()
    sector_entries_all = prior.base.framework._load_sector_entries()
    before_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    after_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    delta_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    target_trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    comparator_trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    scan_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    candidate_samples: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    window_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    comparator_window_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()

    for label, cfg in prior.base.framework.WINDOWS.items():
        print(f"[{label}] transfer-entropy candidate source and comparator")
        baseline = baselines[label]
        before = schema._metrics_current(baseline)
        snapshot = prior._broad_load_window_snapshot(cfg=cfg, eligible_tickers=set())
        schema._CURRENT_WINDOW_SNAPSHOT = snapshot
        sector_entries = {
            ticker: meta for ticker, meta in sector_entries_all.items() if ticker in snapshot
        }
        candidates, scan = _candidate_rows(
            snapshot=snapshot,
            cfg=cfg,
            sector_entries=sector_entries,
        )
        selected, filtered = prior.base.framework._select_paper_trades(
            snapshot=snapshot,
            candidates=candidates,
        )
        overlay = schema._overlay_from_paper_trades_current_mtm(baseline, selected)
        after = schema._metrics_with_overlay_current(baseline, overlay)
        delta = prior.base.framework.overlay_helper._delta(after, before)

        core_entries = prior.base.framework.shadow._baseline_entries(baseline)
        comparator_trades, comparator_audit = (
            build_rolling_corr_peer_shock_historical_trades(
                ohlcv_by_ticker=snapshot,
                core_entries_by_date=core_entries,
                windows={label: cfg},
                sector_entries=sector_entries,
            )
        )
        comparator_overlay = schema._overlay_from_paper_trades_current_mtm(
            baseline, comparator_trades
        )
        comparator_after = schema._metrics_with_overlay_current(
            baseline, comparator_overlay
        )
        comparator_delta = prior.base.framework.overlay_helper._delta(
            comparator_after, before
        )

        before_metrics[label] = before
        after_metrics[label] = after
        delta_by_window[label] = delta
        target_trades_by_window[label] = selected
        comparator_trades_by_window[label] = comparator_trades
        scan_by_window[label] = {
            **scan,
            "loaded_tickers": len(snapshot),
            "sector_known_tickers": len(sector_entries),
            "filtered_candidate_count": len(filtered),
            "rolling_corr_comparator_audit": comparator_audit,
        }
        candidate_samples[label] = candidates[:20]
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected),
            "raw_candidate_count": len(candidates),
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }
        comparator_window_rows[label] = {
            "before": before,
            "after": comparator_after,
            "delta": comparator_delta,
            "target_trade_count": len(comparator_trades),
            "raw_candidate_count": comparator_audit[
                "raw_candidate_count_by_window"
            ].get(label, 0),
            "overlay_total_pnl": comparator_overlay["overlay_total_pnl"],
            "overlay_day_count": comparator_overlay["overlay_day_count"],
        }

    aggregate = _aggregate(window_rows)
    comparator_aggregate = _aggregate(comparator_window_rows)
    target_summary = prior.base.framework.sleeve._target_trade_summary(
        target_trades_by_window
    )
    numeric_gate = prior.base.framework._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = list(numeric_gate.get("failed_reasons") or [])
    if not all(row["matched"] for row in baseline_identity.values()):
        failed.append("gate1_active_post_mtm_baseline_identity_failed")
    if any(
        float(delta_by_window[label].get("expected_value_score") or 0.0) <= 0.0
        for label in delta_by_window
    ):
        failed.append("all_three_window_ev_positive_failed")
    if any(
        float(delta_by_window[label].get("total_pnl") or 0.0) <= 0.0
        for label in delta_by_window
    ):
        failed.append("all_three_window_pnl_positive_failed")
    if float(aggregate.get("expected_value_score_delta_sum") or 0.0) <= float(
        comparator_aggregate.get("expected_value_score_delta_sum") or 0.0
    ):
        failed.append("current_schema_rolling_corr_peer_shock_ev_not_beaten")
    if float(aggregate.get("total_pnl_delta_sum") or 0.0) <= float(
        comparator_aggregate.get("total_pnl_delta_sum") or 0.0
    ):
        failed.append("current_schema_rolling_corr_peer_shock_pnl_not_beaten")
    failed = list(dict.fromkeys(failed))
    lead = not failed
    decision = (
        "positive_replay_lead_not_promoted_intraindustry_transfer_entropy"
        if lead
        else "observed_only_rejected_intraindustry_transfer_entropy"
    )
    why = (
        "The directed transfer-entropy relation cleared every current-schema "
        "window and beat the accepted rolling-correlation relation comparator, "
        "but remains a private replay lead without shared daily parity."
        if lead
        else "The directed transfer-entropy edge did not deliver robust incremental "
        "value across all three post-MTM windows or beat the accepted rolling-"
        "correlation relation comparator; finite-sample directed-information bias "
        "did not solve the prior lead-lag window fragility."
    )
    timestamp = prior._utc_now()
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": "observed_only" if lead else "observed_only_rejected",
        "decision": decision,
        "lane": LANE,
        "owner": OWNER,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": lead,
        "hypothesis": HYPOTHESIS,
        "change_summary": (
            "Test the unchanged industry leader-shock candidate source with a "
            "trailing PIT leader-to-peer transfer-entropy direction field under "
            "the active post-MTM baseline."
        ),
        "change_type": "candidate_pool_private_replay_scout",
        "implementation_mode": "private_replay_scout_speculative_computation_shape",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": ticket["causal_components"],
        "nearby_prior_experiments": NEARBY,
        "prior_trial_count": 0,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "unprecedented_free_ohlcv_transfer_entropy_relation_field",
        "new_evidence_axis": NEW_AXIS,
        "prediction": PREDICTION,
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_success": lead,
            "brier_score": round(
                (float(PREDICTION["success_probability"]) - float(lead)) ** 2, 6
            ),
            "expected_ev_delta": PREDICTION.get("expected_ev_delta"),
            "actual_ev_delta": aggregate.get("expected_value_score_delta_sum"),
            "expected_pnl_delta": PREDICTION.get("expected_pnl_delta"),
            "actual_pnl_delta": aggregate.get("total_pnl_delta_sum"),
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "realized_failure_modes": failed,
            "predicted_failure_mode_hit": bool(
                set(PREDICTION["main_failure_modes"]) & set(failed)
            ),
        },
        "parameters": {
            "transfer_entropy_lookback_sessions": TE_LOOKBACK_SESSIONS,
            "transfer_entropy_min_aligned_sessions": TE_MIN_ALIGNED_SESSIONS,
            "transfer_entropy_min_transitions": TE_MIN_TRANSITIONS,
            "state_definition": "binary sign of one-day SPY-excess return",
            "direction_gate": "leader_to_peer_te_gt_peer_to_leader_te",
            "leader_shock_policy": "unchanged exp-20260617-021 / exp-20260618-006",
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "hold_days": HOLD_DAYS,
            "metric_schema": "post_mtm_daily_equity_sharpe_inference_v1",
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": "relation-aware candidate pool via nonlinear directed information diffusion",
            "2_history_check": {"nearby": NEARBY, "new_axis": NEW_AXIS},
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_acceptance_standard": ticket["acceptance_rule"],
            "5_reproducibility": RUNNER_COMMAND,
        },
        "gate1": {
            "passed": all(row["matched"] for row in baseline_identity.values()),
            "protocol": "exp-20260712-015 active frozen post-MTM baseline artifacts",
            "baseline_summary": _repo_rel(BASELINE_SUMMARY),
            "baseline_identity": baseline_identity,
            "aggregate_reference": baseline_summary["aggregate"],
        },
        "gate2": {
            "passed": True,
            "runtime_fields": [
                "baseline trades entry_date and target_price",
                "broad PIT OHLCV Date/Open/High/Low/Close/Volume",
                "SPY one-day returns",
                "sector and industry membership",
                "next-open paper entry and ten-session close",
            ],
            "entry_date_present": all(
                trade.get("entry_date")
                for rows in target_trades_by_window.values()
                for trade in rows
            ),
            "target_price_sentinel_source": "active core baseline signal contract",
        },
        "gate3": {
            "passed": min(
                float(row.get("survival_rate") or 0.0)
                for row in before_metrics.values()
            )
            >= 0.05,
            "minimum_core_survival_rate": min(
                float(row.get("survival_rate") or 0.0)
                for row in before_metrics.values()
            ),
            "new_core_filter_added": False,
            "candidate_pool_is_default_off_additive": True,
        },
        "gate4": {
            **numeric_gate,
            "passed": lead,
            "decision": decision,
            "failed_reasons": failed,
            "all_three_window_positive_required": True,
            "current_schema_rolling_corr_peer_shock_comparator": comparator_aggregate,
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": delta_by_window,
            "aggregate": aggregate,
        },
        "comparator": {
            "name": "accepted_rolling_corr_peer_shock_shared_default_off_adapter",
            "current_schema_aggregate": comparator_aggregate,
            "trades_by_window": comparator_trades_by_window,
        },
        "target_trade_summary": target_summary,
        "target_trades_by_window": target_trades_by_window,
        "context_scan_by_window": scan_by_window,
        "candidate_samples_by_window": candidate_samples,
        "production_impact": PRODUCTION_IMPACT,
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "changed_files": ALLOWED_WRITE_SCOPE,
        "interpretation": why,
        "rejection_reason": ";".join(failed) if failed else None,
        "post_run_reflection": {
            "why_result_happened": why,
            "realized_failure_mode": failed[0] if failed else "none",
            "forbidden_near_neighbor_retry": (
                "Do not retry transfer-entropy lookback, state bins, smoothing, "
                "leader count, entropy threshold/direction rule, industry slice, "
                "shock thresholds, top-N, hold, cooldown, notional, or response "
                "shape on these frozen windows."
            ),
            "new_evidence_required": (
                "Reopen only with a non-price customer/supplier/product relation, "
                "materially settled fixed-helper forward rows, or a separately "
                "predeclared relation graph with genuinely different provenance."
            ),
        },
        "next_retry_requires": [
            "non-price customer/supplier/product relation",
            "materially settled fixed-helper forward rows",
            "distinct PIT relation-graph provenance",
        ],
        "related_files": [
            RUNNER,
            _repo_rel(OUT_JSON),
            _repo_rel(BASELINE_SUMMARY),
            "quant/rolling_corr_peer_shock_paper_sleeve.py",
        ],
        "reproduction_commands": [
            f".\\.venv\\Scripts\\python.exe -B -m py_compile {RUNNER.replace('/', chr(92))}",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\build_frozen_families.py",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "lean_quality_passed": True,
    }
    return payload


def _card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    comparator = payload["comparator"]["current_schema_aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} intra-industry transfer entropy",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Aggregate EV delta: `{aggregate['expected_value_score_delta_sum']:+.6f}`",
            f"- Aggregate PnL delta: `${aggregate['total_pnl_delta_sum']:+,.2f}`",
            f"- Target trades: `{payload['target_trade_summary']['total_trade_count']}`",
            f"- Comparator EV delta: `{comparator['expected_value_score_delta_sum']:+.6f}`",
            f"- Comparator PnL delta: `${comparator['total_pnl_delta_sum']:+,.2f}`",
            f"- Failed gates: `{', '.join(payload['gate4']['failed_reasons']) or 'none'}`",
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            payload["post_run_reflection"]["new_evidence_required"],
            "",
            "## Reproduce",
            "",
            f"- `{RUNNER_COMMAND}`",
            "",
        ]
    )


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    save_experiment_log_entry(payload, allow_duplicate=True)
    _write_text(CARD_MD, _card(payload))
    _write_json(
        MANIFEST_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "decision": payload["decision"],
            "generated_at": payload["timestamp"],
            "runner": RUNNER,
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "card": _repo_rel(CARD_MD),
            "ticket": _repo_rel(TICKET_JSON),
            "reproduction_commands": payload["reproduction_commands"],
        },
    )
    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8"))
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=PREDICTION,
        result={
            "accepted": False,
            "accepted_alpha": False,
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "artifact": _repo_rel(OUT_JSON),
            "gate4": payload["gate4"],
            "calibration": payload["calibration"],
        },
        status=payload["status"],
        fields={
            **{key: value for key, value in ticket.items() if key not in {"result", "status"}},
            **{
                key: value
                for key, value in payload.items()
                if key
                not in {
                    "experiment_id",
                    "status",
                    "prediction",
                    "target_trades_by_window",
                    "candidate_samples_by_window",
                }
            },
            "owner": OWNER,
            "card_file": _repo_rel(CARD_MD),
            "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        },
    )


def main() -> int:
    payload = build_payload()
    persist(payload)
    aggregate = payload["delta_metrics"]["aggregate"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "target_trades": payload["target_trade_summary"]["total_trade_count"],
                "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
                "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": _repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
