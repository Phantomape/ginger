"""exp-20260602-030: post-earnings surprise-acceleration support scout.

This alpha search tests one event-quality allocation field on top of the
accepted default-off POST_EARNINGS_UNDERPRICED_DRIFT_PAPER + high-liquidity
support stack from exp-20260602-027. Already-selected paper candidates whose
latest EPS surprise exceeds their own historical average surprise by at least
5 percentage points receive 1.05x incremental paper notional.

This is a scout only: the shared production adapter is intentionally not
modified in this ticket, so a positive replay lead is not retained until a
separate shared-adapter promotion removes backtest/production drift. Core
signal generation, ranking, exits, LLM/news replay, watchlists, and live/default
orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
if str(QUANT_ROOT) not in sys.path:
    sys.path.insert(0, str(QUANT_ROOT))

import exp_20260602_027_post_earnings_high_liquidity_support as parent


EXPERIMENT_ID = "exp-20260602-030"
STEM = "post_earnings_surprise_acceleration_support"
TRIAL_FAMILY = "post_earnings_event_quality_support"
CHANGED_VARIABLE = "post_earnings_surprise_acceleration_notional_scalar_v1"
RULE_VERSION = "post_earnings_surprise_acceleration_support_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260602_030_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
BASELINE_EXP027_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260602-027"
    / "exp_20260602_027_post_earnings_high_liquidity_support.json"
)

SURPRISE_ACCELERATION_MIN_DELTA_PCT = 5.0
SURPRISE_ACCELERATION_NOTIONAL_SCALAR = 1.05
BASE_NOTIONAL_USD = parent.BASE_NOTIONAL_USD
MIN_SUPPORTED_TRADES = 10
MAX_SINGLE_POSITIVE_INCREMENTAL_SHARE = 0.50
MAX_POSITIVE_INCREMENTAL_HHI = 0.30


def _framework():
    return parent.parent.parent.framework


def _base():
    return _framework().base


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _surprise_delta_pct(row: dict[str, Any]) -> float | None:
    latest = _float_or_none(row.get("latest_surprise_pct"))
    historical_avg = _float_or_none(row.get("avg_historical_surprise_pct"))
    if latest is None or historical_avg is None:
        return None
    return latest - historical_avg


def _support_applies(row: dict[str, Any]) -> bool:
    delta = _surprise_delta_pct(row)
    history_count = _float_or_none(row.get("historical_surprise_count"))
    if delta is None or history_count is None:
        return False
    return (
        history_count >= 4
        and delta >= SURPRISE_ACCELERATION_MIN_DELTA_PCT
    )


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidates, audit = parent._candidate_rows_for_window(
        snapshot,
        cfg,
        universe,
        before_result,
    )
    support_count = 0
    support_days: set[str] = set()
    support_tickers: set[str] = set()
    for row in candidates:
        delta = _surprise_delta_pct(row)
        supported = _support_applies(row)
        pre_surprise_notional = _float_or_none(row.get("intended_notional"))
        if pre_surprise_notional is None:
            pre_surprise_notional = BASE_NOTIONAL_USD
        scalar = SURPRISE_ACCELERATION_NOTIONAL_SCALAR if supported else 1.0
        row["surprise_acceleration_support"] = supported
        row["surprise_acceleration_support_rule_version"] = RULE_VERSION
        row["surprise_acceleration_delta_pct"] = (
            round(delta, 6) if delta is not None else None
        )
        row["surprise_acceleration_min_delta_pct"] = (
            SURPRISE_ACCELERATION_MIN_DELTA_PCT
        )
        row["surprise_acceleration_notional_scalar"] = scalar
        row["pre_surprise_paper_notional_usd"] = round(pre_surprise_notional, 2)
        row["intended_notional"] = round(pre_surprise_notional * scalar, 2)
        row["trade_enabled"] = False
        row["alters_orders"] = False
        if supported:
            support_count += 1
            support_days.add(str(row.get("date") or ""))
            support_tickers.add(str(row.get("ticker") or "").upper())

    audit = dict(audit)
    audit["surprise_acceleration_support_rule_version"] = RULE_VERSION
    audit["surprise_acceleration_min_delta_pct"] = (
        SURPRISE_ACCELERATION_MIN_DELTA_PCT
    )
    audit["surprise_acceleration_notional_scalar"] = (
        SURPRISE_ACCELERATION_NOTIONAL_SCALAR
    )
    audit["surprise_acceleration_supported_raw_candidate_count"] = support_count
    audit["surprise_acceleration_supported_candidate_days"] = len(support_days)
    audit["surprise_acceleration_supported_unique_tickers"] = len(support_tickers)
    audit["support_changes_entries_or_filters"] = False
    return candidates, audit


def _paper_trade_from_candidate(
    snapshot: dict[str, list[dict[str, Any]]],
    candidate: dict[str, Any],
) -> dict[str, Any] | None:
    trade = parent._paper_trade_from_candidate(snapshot, candidate)
    if trade is None:
        return None
    final_notional = _float_or_none(candidate.get("intended_notional"))
    if final_notional is None:
        final_notional = BASE_NOTIONAL_USD
    pre_surprise_notional = _float_or_none(candidate.get("pre_surprise_paper_notional_usd"))
    if pre_surprise_notional is None:
        pre_surprise_notional = final_notional
    pnl_pct_net = float(trade.get("pnl_pct_net") or 0.0)
    supported = bool(candidate.get("surprise_acceleration_support"))
    scalar = SURPRISE_ACCELERATION_NOTIONAL_SCALAR if supported else 1.0
    trade["paper_notional_usd"] = round(final_notional, 2)
    trade["intended_notional"] = round(final_notional, 2)
    trade["pre_surprise_paper_notional_usd"] = round(pre_surprise_notional, 2)
    trade["surprise_acceleration_support"] = supported
    trade["surprise_acceleration_support_rule_version"] = RULE_VERSION
    trade["surprise_acceleration_delta_pct"] = candidate.get(
        "surprise_acceleration_delta_pct"
    )
    trade["surprise_acceleration_min_delta_pct"] = (
        SURPRISE_ACCELERATION_MIN_DELTA_PCT
    )
    trade["surprise_acceleration_notional_scalar"] = scalar
    trade["surprise_acceleration_incremental_pnl"] = round(
        pnl_pct_net * pre_surprise_notional * (scalar - 1.0),
        2,
    )
    trade["pnl"] = round(final_notional * pnl_pct_net, 2)
    trade["trade_enabled"] = False
    trade["alters_orders"] = False
    return trade


def _select_paper_trades(
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    used_date_counts: Counter[str] = Counter()
    for row in candidates:
        date = str(row.get("date") or "")
        if row.get("same_ticker_ab_overlap"):
            filtered.append({**row, "filter_reason": "same_ticker_core_overlap"})
            continue
        if used_date_counts[date] >= _framework().MAX_PAPER_TRADES_PER_DAY:
            filtered.append({**row, "filter_reason": "daily_top1_limit"})
            continue
        trade = _paper_trade_from_candidate(snapshot, row)
        if trade is None:
            filtered.append({**row, "filter_reason": "missing_next_open_or_exit"})
            continue
        selected.append(trade)
        used_date_counts[date] += 1
    return selected, filtered


def _support_trade_summary(
    target_trades_by_window: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    by_window: dict[str, dict[str, Any]] = {}
    incremental_by_ticker: Counter[str] = Counter()
    supported_rows: list[dict[str, Any]] = []
    for label, trades in target_trades_by_window.items():
        supported = [trade for trade in trades if trade.get("surprise_acceleration_support")]
        supported_rows.extend(supported)
        for trade in supported:
            incremental_by_ticker[str(trade.get("ticker") or "").upper()] += float(
                trade.get("surprise_acceleration_incremental_pnl") or 0.0
            )
        by_window[label] = {
            "adjusted_trade_count": len(supported),
            "adjusted_total_pnl": round(
                sum(float(trade.get("pnl") or 0.0) for trade in supported),
                2,
            ),
            "adjusted_incremental_pnl": round(
                sum(
                    float(trade.get("surprise_acceleration_incremental_pnl") or 0.0)
                    for trade in supported
                ),
                2,
            ),
        }
    positive = {
        ticker: pnl for ticker, pnl in incremental_by_ticker.items() if pnl > 0
    }
    positive_total = sum(positive.values())
    max_share = (
        round(max(positive.values()) / positive_total, 6)
        if positive_total > 0 and positive
        else None
    )
    hhi = (
        round(sum((pnl / positive_total) ** 2 for pnl in positive.values()), 6)
        if positive_total > 0 and positive
        else None
    )
    return {
        "adjusted_trade_count": len(supported_rows),
        "adjusted_windows": [
            label for label, row in by_window.items() if row["adjusted_trade_count"]
        ],
        "by_window": by_window,
        "positive_by_ticker_incremental_pnl": {
            ticker: round(pnl, 2) for ticker, pnl in sorted(positive.items())
        },
        "max_single_positive_incremental_pnl_share": max_share,
        "positive_incremental_pnl_hhi": hhi,
    }


def _patch_parent() -> None:
    parent.EXPERIMENT_ID = EXPERIMENT_ID
    parent.STEM = STEM
    parent.TRIAL_FAMILY = TRIAL_FAMILY
    parent.CHANGED_VARIABLE = CHANGED_VARIABLE
    parent.RULE_VERSION = RULE_VERSION
    parent.OUT_DIR = OUT_DIR
    parent.OUT_JSON = OUT_JSON
    parent.BEFORE_AGG_JSON = BEFORE_AGG_JSON
    parent.AFTER_AGG_JSON = AFTER_AGG_JSON
    parent.LOG_JSON = LOG_JSON
    parent.TICKET_JSON = TICKET_JSON
    parent.CARD_MD = CARD_MD
    parent.ARTIFACT_MD = ARTIFACT_MD
    parent.EXPERIMENT_LOG = EXPERIMENT_LOG
    parent.MANIFEST_JSON = MANIFEST_JSON
    parent._patch_parent()
    _framework()._candidate_rows_for_window = _candidate_rows_for_window
    _framework()._select_paper_trades = _select_paper_trades


def _load_exp027_baseline() -> dict[str, Any]:
    with BASELINE_EXP027_JSON.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _numeric_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    deltas: dict[str, Any] = {}
    for key, before_value in before.items():
        after_value = after.get(key)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            deltas[key] = round(float(after_value) - float(before_value), 6)
    return deltas


def _rebase_delta_metrics(payload: dict[str, Any], baseline_payload: dict[str, Any]) -> None:
    before_metrics = baseline_payload["after_metrics"]
    after_metrics = payload["after_metrics"]
    by_window = {
        label: _numeric_delta(before_metrics[label], after_metrics[label])
        for label in _framework().base.WINDOWS
    }
    before_ev = sum(
        float(before_metrics[label]["expected_value_score"])
        for label in _framework().base.WINDOWS
    )
    after_ev = sum(
        float(after_metrics[label]["expected_value_score"])
        for label in _framework().base.WINDOWS
    )
    before_pnl = sum(
        float(before_metrics[label]["total_pnl"]) for label in _framework().base.WINDOWS
    )
    after_pnl = sum(
        float(after_metrics[label]["total_pnl"]) for label in _framework().base.WINDOWS
    )
    payload["framework_core_before_metrics"] = payload["before_metrics"]
    payload["framework_core_delta_metrics"] = payload["delta_metrics"]
    payload["before_metrics"] = before_metrics
    payload["judge_before_aggregate"] = baseline_payload["judge_after_aggregate"]
    payload["delta_metrics"] = {
        "by_window": by_window,
        "aggregate": {
            "baseline_expected_value_score_sum": round(before_ev, 4),
            "after_expected_value_score_sum": round(after_ev, 4),
            "expected_value_score_delta_sum": round(after_ev - before_ev, 4),
            "expected_value_score_delta_pct": (
                round((after_ev - before_ev) / before_ev, 6)
                if before_ev
                else None
            ),
            "baseline_total_pnl_sum": round(before_pnl, 2),
            "after_total_pnl_sum": round(after_pnl, 2),
            "total_pnl_delta_sum": round(after_pnl - before_pnl, 2),
            "total_pnl_delta_pct": (
                round((after_pnl - before_pnl) / before_pnl, 6)
                if before_pnl
                else None
            ),
            "windows_ev_improved": sum(
                1 for row in by_window.values() if row.get("expected_value_score", 0) > 0
            ),
            "windows_ev_regressed": sum(
                1 for row in by_window.values() if row.get("expected_value_score", 0) < 0
            ),
            "windows_pnl_improved": sum(
                1 for row in by_window.values() if row.get("total_pnl", 0) > 0
            ),
            "windows_pnl_regressed": sum(
                1 for row in by_window.values() if row.get("total_pnl", 0) < 0
            ),
            "max_drawdown_delta_max": round(
                max(row.get("max_drawdown_pct", 0.0) for row in by_window.values()),
                6,
            ),
            "target_trade_count_sum": sum(
                len(payload["target_trades_by_window"][label])
                for label in _framework().base.WINDOWS
            ),
        },
    }


def _custom_gate4(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    support = payload["support_trade_summary"]
    failed: list[str] = []
    if aggregate["expected_value_score_delta_sum"] <= 0:
        failed.append("aggregate_ev_not_positive")
    if aggregate["total_pnl_delta_sum"] <= 0:
        failed.append("aggregate_pnl_not_positive")
    if aggregate["windows_ev_regressed"]:
        failed.append("window_ev_regression")
    if aggregate["windows_pnl_regressed"]:
        failed.append("window_pnl_regression")
    if aggregate["max_drawdown_delta_max"] > 0.005:
        failed.append("drawdown_drift_gt_50bp")
    if min(payload["after_metrics"][label]["survival_rate"] for label in _framework().base.WINDOWS) < 0.05:
        failed.append("survival_rate_below_5pct")
    if support["adjusted_trade_count"] < MIN_SUPPORTED_TRADES:
        failed.append("thin_adjusted_sample")
    if len(support["adjusted_windows"]) < 3:
        failed.append("not_all_windows_adjusted")
    max_share = support["max_single_positive_incremental_pnl_share"]
    if max_share is not None and max_share > MAX_SINGLE_POSITIVE_INCREMENTAL_SHARE:
        failed.append("support_incremental_concentration_max_share_failed")
    hhi = support["positive_incremental_pnl_hhi"]
    if hhi is not None and hhi > MAX_POSITIVE_INCREMENTAL_HHI:
        failed.append("support_incremental_hhi_failed")

    metric_gate4_passed = not failed
    retained_failed = list(failed)
    if metric_gate4_passed:
        retained_failed.append("shared_adapter_not_changed_positive_replay_not_retained")
    return {
        "passed": False if metric_gate4_passed else False,
        "metric_gate4_passed": metric_gate4_passed,
        "failed_reasons": retained_failed,
        "acceptance_rule": (
            "Metric Gate 4 uses docs/backtesting.md three canonical windows "
            "versus exp-20260602-027 accepted after-state. Retention also "
            "requires shared-adapter promotion, which this scout intentionally "
            "does not do."
        ),
        "support_min_trade_count": MIN_SUPPORTED_TRADES,
        "max_single_positive_incremental_share_limit": (
            MAX_SINGLE_POSITIVE_INCREMENTAL_SHARE
        ),
        "positive_incremental_hhi_limit": MAX_POSITIVE_INCREMENTAL_HHI,
    }


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    baseline_payload = _load_exp027_baseline()
    _rebase_delta_metrics(payload, baseline_payload)
    support_summary = _support_trade_summary(payload["target_trades_by_window"])
    payload["support_trade_summary"] = support_summary
    payload["gate4"] = _custom_gate4(payload)
    aggregate = payload["delta_metrics"]["aggregate"]
    metric_gate4_passed = payload["gate4"]["metric_gate4_passed"]
    decision = (
        "positive_replay_lead_post_earnings_surprise_acceleration_requires_shared_adapter"
        if metric_gate4_passed
        else "rejected_post_earnings_surprise_acceleration_support"
    )
    actual_success = 1 if payload["gate4"]["passed"] else 0
    prediction = {
        "success_probability": 0.24,
        "expected_ev_delta": None,
        "expected_pnl_delta": None,
        "main_failure_modes": [
            "thin_adjusted_sample",
            "window_regression",
            "concentration_failed",
            "nearby_event_quality_overfit",
        ],
        "confidence_reason": (
            "The accepted post-earnings adapter has replacement value and "
            "latest-versus-own-history surprise acceleration is a distinct "
            "event-quality field, but nearby surprise/score tests are crowded."
        ),
        "recorded_at": "2026-06-02T22:08:37+00:00",
        "brier_score": round((0.24 - actual_success) ** 2, 6),
    }
    calibration = {
        "actual_decision": decision,
        "actual_success": actual_success,
        "metric_gate4_passed": metric_gate4_passed,
        "predicted_success_probability": prediction["success_probability"],
        "brier_score": prediction["brier_score"],
        "expected_ev_delta": prediction["expected_ev_delta"],
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "expected_pnl_delta": prediction["expected_pnl_delta"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
        "predicted_failure_modes": prediction["main_failure_modes"],
        "realized_failure_mode": "; ".join(payload["gate4"]["failed_reasons"]),
        "predicted_failure_mode_hit": any(
            token in "; ".join(payload["gate4"]["failed_reasons"])
            for token in ("sample", "regression", "concentration", "overfit")
        ),
    }
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": "completed",
            "decision": decision,
            "hypothesis": (
                "Already-selected post-earnings underpriced drift paper "
                "candidates whose latest EPS surprise exceeds their own "
                "historical average surprise may deserve modest default-off "
                "paper support."
            ),
            "change_type": "default_off_paper_allocation_scout",
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": "default_off_paper_allocation",
            "trial_variant_id": RULE_VERSION,
            "prior_trial_count": 4,
            "nearby_prior_experiments": [
                "exp-20260602-006",
                "exp-20260602-022",
                "exp-20260602-026",
                "exp-20260602-027",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "production_visible_event_quality_field_from_free_earnings_snapshot",
            "comparison_baseline_experiment_id": "exp-20260602-027",
            "prediction": prediction,
            "calibration": calibration,
            "parameters": {
                **payload.get("parameters", {}),
                "baseline_accepted_stack": "exp-20260602-027",
                "support_field": "latest_surprise_pct_minus_avg_historical_surprise_pct",
                "surprise_acceleration_min_delta_pct": (
                    SURPRISE_ACCELERATION_MIN_DELTA_PCT
                ),
                "surprise_acceleration_notional_scalar": (
                    SURPRISE_ACCELERATION_NOTIONAL_SCALAR
                ),
                "base_notional_source": "existing exp027 paper_notional_usd",
                "trade_enabled": False,
            },
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "capital allocation / event-quality allocation: within "
                    "the accepted post-earnings underpriced drift sleeve, "
                    "latest surprise strength relative to the ticker's own "
                    "history may identify stronger continuation."
                ),
                "2_history_check": {
                    "exp-20260602-006": (
                        "Accepted positive-surprise drift candidate pool; "
                        "this run does not add candidates or rerank by score."
                    ),
                    "exp-20260602-022": (
                        "Rejected score monotonicity; this run uses a binary "
                        "latest-vs-own-history event-quality support field, "
                        "not combined score ranking."
                    ),
                    "exp-20260602-026": (
                        "Accepted shared post-earnings underpriced adapter; "
                        "this run keeps the adapter's candidate logic fixed."
                    ),
                    "exp-20260602-027": (
                        "Accepted high-liquidity support; this run compares "
                        "incremental value against that accepted after-state."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same docs/backtesting.md three windows, rebased versus "
                    "exp027 after-state. Metrics need positive aggregate "
                    "EV/PnL, no EV or PnL-regressed window, drawdown drift "
                    "<=0.5pp, survival >=5%, at least 10 supported trades "
                    "across all windows, and concentration pass. Retention "
                    "requires a separate shared-adapter promotion."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                    "exp_20260602_030_post_earnings_surprise_acceleration_support.py"
                ),
            },
            "gate2": {
                **payload.get("gate2", {}),
                "support_field_check": {
                    "fields": [
                        "latest_surprise_pct",
                        "avg_historical_surprise_pct",
                        "historical_surprise_count",
                    ],
                    "source": (
                        "post_earnings_underpriced_drift_paper_sleeve shared "
                        "earnings snapshot candidate rows"
                    ),
                    "decision_time": (
                        "known from the daily earnings snapshot before the "
                        "next-open default-off paper entry"
                    ),
                    "coverage": _framework()._field_coverage(
                        [
                            trade
                            for trades in payload["target_trades_by_window"].values()
                            for trade in trades
                        ],
                        [
                            "latest_surprise_pct",
                            "avg_historical_surprise_pct",
                            "historical_surprise_count",
                            "surprise_acceleration_delta_pct",
                        ],
                    ),
                },
            },
            "production_impact": {
                "live_orders_changed": False,
                "default_orders_changed": False,
                "core_entry_exit_ranking_changed": False,
                "candidate_pool_changed": False,
                "shared_adapter_changed": False,
                "backtester_adapter_changed": True,
                "retained_strategy_change": False,
                "parity_interpretation": (
                    "No positive behavior is retained from this scout because "
                    "the shared production adapter is not changed. Promotion "
                    "would require adding this field to "
                    "quant/post_earnings_underpriced_drift_paper_sleeve.py "
                    "and rerunning Gate 4."
                ),
            },
            "anti_js": "No JavaScript was used.",
            "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
            "total_pnl_delta": aggregate["total_pnl_delta_sum"],
            "interpretation": (
                "Positive replay lead only; not retained without shared adapter promotion."
                if metric_gate4_passed
                else "Rejected; surprise acceleration did not clear incremental Gate 4 versus exp027."
            ),
            "acceptance_interpretation": (
                "Observed-only replay lead; no strategy behavior retained."
                if metric_gate4_passed
                else "Rejected and not retained."
            ),
            "rejection_reason": "; ".join(payload["gate4"]["failed_reasons"]),
            "next_evidence_needed": (
                "If metric-positive, run a separate shared-adapter promotion "
                "ticket and collect forward replacement-value rows before "
                "considering live/default activation."
            ),
            "why_not_other_changes": [
                "Skipped LLM soft-ranking because replay-safe attribution rows remain sparse.",
                "Skipped options historical alpha because historical OnclickMedia backfill lacks vendor_asof PIT safety.",
                "Skipped Companyfacts scalar mining because meta research and playbook freeze nearby support-threshold retunes.",
                "Skipped same-industry peer shock variants after exp020/021/029 rejected similar event-graph propagation.",
            ],
            "related_files": [
                "docs/backtesting.md",
                "docs/current_state.md",
                "docs/alpha-optimization-playbook.md",
                "docs/production_backtest_parity.md",
                "quant/post_earnings_underpriced_drift_paper_sleeve.py",
                "quant/experiments/exp_20260602_027_post_earnings_high_liquidity_support.py",
            ],
        }
    )
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Exp027 EV | After EV | dEV | Exp027 PnL | After PnL | dPnL | DD d | Target trades | Supported trades | Support dPnL |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    support = payload["support_trade_summary"]["by_window"]
    for label in _framework().base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        support_row = support[label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} | {supported} | ${support_dpnl:+,.2f} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                supported=support_row["adjusted_trade_count"],
                support_dpnl=support_row["adjusted_incremental_pnl"],
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Post-Earnings Surprise-Acceleration Support",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            (
                "Single variable: on top of accepted exp027, already-selected "
                "`POST_EARNINGS_UNDERPRICED_DRIFT_PAPER` candidates with "
                "`latest_surprise_pct - avg_historical_surprise_pct >= 5pp` "
                "receive `1.05x` incremental paper notional."
            ),
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- EV delta vs exp027: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta vs exp027: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- target trades: `{payload['target_trade_summary']['total_trade_count']}`",
            f"- supported trades: `{payload['support_trade_summary']['adjusted_trade_count']}` across `{payload['support_trade_summary']['adjusted_windows']}`",
            f"- supported max positive incremental share: `{payload['support_trade_summary']['max_single_positive_incremental_pnl_share']}`",
            f"- supported positive incremental HHI: `{payload['support_trade_summary']['positive_incremental_pnl_hhi']}`",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            (
                "No strategy behavior is retained in this scout. The support "
                "field is evaluated through replay only; a positive result "
                "requires a separate shared-adapter promotion before it can be "
                "considered production/backtest consistent."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _persist(payload: dict[str, Any]) -> None:
    base = _base()
    base._write_json(OUT_JSON, payload)
    base._write_json(BEFORE_AGG_JSON, payload["judge_before_aggregate"])
    base._write_json(AFTER_AGG_JSON, payload["judge_after_aggregate"])
    base._write_json(LOG_JSON, payload)
    ticket_payload = {}
    if TICKET_JSON.exists():
        with TICKET_JSON.open("r", encoding="utf-8") as handle:
            ticket_payload = json.load(handle)
    lifecycle_status = "observed_only" if payload["gate4"]["metric_gate4_passed"] else "rejected"
    aggregate_delta = payload["delta_metrics"]["aggregate"]
    ticket_payload.update(
        {
            "status": lifecycle_status,
            "completed_at": payload["timestamp"],
            "result": {
                "decision": lifecycle_status,
                "gate4_decision": payload["decision"],
                "acceptance_reasons": [],
                "artifact": base._repo_rel(OUT_JSON),
                "log": base._repo_rel(LOG_JSON),
                "summary": payload["interpretation"],
                "before_result_file": base._repo_rel(BEFORE_AGG_JSON),
                "after_result_file": base._repo_rel(AFTER_AGG_JSON),
                "expected_value_score_delta": payload["expected_value_score_delta"],
                "total_pnl_delta": payload["total_pnl_delta"],
                "support_trade_summary": {
                    "adjusted_trade_count": payload["support_trade_summary"][
                        "adjusted_trade_count"
                    ],
                    "adjusted_windows": payload["support_trade_summary"][
                        "adjusted_windows"
                    ],
                    "adjusted_incremental_pnl": round(
                        sum(
                            window["adjusted_incremental_pnl"]
                            for window in payload["support_trade_summary"][
                                "by_window"
                            ].values()
                        ),
                        2,
                    ),
                },
                "production_impact": payload["production_impact"],
                "delta_metrics": {
                    "expected_value_score": aggregate_delta[
                        "expected_value_score_delta_sum"
                    ],
                    "total_pnl": aggregate_delta["total_pnl_delta_sum"],
                    "windows_ev_regressed": aggregate_delta["windows_ev_regressed"],
                    "windows_pnl_regressed": aggregate_delta["windows_pnl_regressed"],
                },
            },
        }
    )
    base._write_json(TICKET_JSON, ticket_payload)
    base._write_text(ARTIFACT_MD, _build_report(payload))
    base._write_text(CARD_MD, _build_report(payload))
    base._upsert_jsonl(EXPERIMENT_LOG, payload)
    _write_manifest()


def _write_manifest() -> None:
    base = _base()
    files = {
        "runner": base._repo_rel(Path(__file__)),
        "result": base._repo_rel(OUT_JSON),
        "before_aggregate": base._repo_rel(BEFORE_AGG_JSON),
        "after_aggregate": base._repo_rel(AFTER_AGG_JSON),
        "log": base._repo_rel(LOG_JSON),
        "ticket": base._repo_rel(TICKET_JSON),
        "card": base._repo_rel(CARD_MD),
        "artifact": base._repo_rel(ARTIFACT_MD),
        "manifest": base._repo_rel(MANIFEST_JSON),
        "experiment_log": base._repo_rel(EXPERIMENT_LOG),
        "baseline_result": base._repo_rel(BASELINE_EXP027_JSON),
        "parity_doc": "docs/production_backtest_parity.md",
        "current_state": "docs/current_state.md",
        "playbook": "docs/alpha-optimization-playbook.md",
    }
    manifest = {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_revision_manifest",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": {
            label: {
                "path": rel_path,
                "exists": (REPO_ROOT / rel_path).exists(),
                "sha256": _sha256(REPO_ROOT / rel_path),
            }
            for label, rel_path in files.items()
        },
    }
    base._write_json(MANIFEST_JSON, manifest)


def main() -> int:
    _patch_parent()
    payload = _postprocess_payload(_framework()._build_payload())
    _persist(payload)
    print(
        json.dumps(
            _base()._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "metric_gate4_passed": payload["gate4"]["metric_gate4_passed"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "support_trade_summary": payload["support_trade_summary"],
                    "artifact": _base()._repo_rel(ARTIFACT_MD),
                    "before_aggregate": _base()._repo_rel(BEFORE_AGG_JSON),
                    "after_aggregate": _base()._repo_rel(AFTER_AGG_JSON),
                    "production_impact": payload["production_impact"],
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    if not math.isfinite(1.0):
        raise SystemExit("unexpected math failure")
    raise SystemExit(main())
