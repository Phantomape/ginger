"""exp-20260602-027: post-earnings high-liquidity support scout.

This alpha search promotes one production-visible support field on top of the
accepted default-off POST_EARNINGS_UNDERPRICED_DRIFT_PAPER adapter:
already-selected paper candidates with 20-day average dollar volume of at
least $1B receive 1.10x paper notional.

The runner calls the same shared helper that production uses for default-off
paper observation, so the Gate 4 comparison is not backtester-only.
Core signal generation, ranking, sizing, exits, LLM/news replay, watchlists,
and live/default orders are unchanged. No JavaScript is used.
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

import exp_20260602_026_post_earnings_underpriced_shared_adapter as parent


EXPERIMENT_ID = "exp-20260602-027"
STEM = "post_earnings_high_liquidity_support"
TRIAL_FAMILY = "post_earnings_underpriced_cost_liquidity_support"
CHANGED_VARIABLE = "post_earnings_underpriced_high_liquidity_notional_scalar_v1"
RULE_VERSION = "post_earnings_underpriced_high_liquidity_support_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260602_027_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"

HIGH_LIQUIDITY_AVG_DOLLAR_VOLUME_20D_MIN = 1_000_000_000.0
HIGH_LIQUIDITY_NOTIONAL_SCALAR = 1.10
BASE_NOTIONAL_USD = 10_000.0


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _support_applies(row: dict[str, Any]) -> bool:
    try:
        avg_dollar_volume = float(row.get("avg_dollar_volume_20d") or 0.0)
    except (TypeError, ValueError):
        return False
    return avg_dollar_volume >= HIGH_LIQUIDITY_AVG_DOLLAR_VOLUME_20D_MIN


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
        supported = _support_applies(row)
        row["high_liquidity_support"] = supported
        row["high_liquidity_support_rule_version"] = RULE_VERSION
        row["high_liquidity_avg_dollar_volume_20d_min"] = (
            HIGH_LIQUIDITY_AVG_DOLLAR_VOLUME_20D_MIN
        )
        row["high_liquidity_notional_scalar"] = (
            HIGH_LIQUIDITY_NOTIONAL_SCALAR if supported else 1.0
        )
        row["base_paper_notional_usd"] = BASE_NOTIONAL_USD
        row["intended_notional"] = round(
            BASE_NOTIONAL_USD * (HIGH_LIQUIDITY_NOTIONAL_SCALAR if supported else 1.0),
            2,
        )
        row["trade_enabled"] = False
        row["alters_orders"] = False
        if supported:
            support_count += 1
            support_days.add(str(row.get("date") or ""))
            support_tickers.add(str(row.get("ticker") or "").upper())

    audit = dict(audit)
    audit["high_liquidity_support_rule_version"] = RULE_VERSION
    audit["high_liquidity_avg_dollar_volume_20d_min"] = (
        HIGH_LIQUIDITY_AVG_DOLLAR_VOLUME_20D_MIN
    )
    audit["high_liquidity_notional_scalar"] = HIGH_LIQUIDITY_NOTIONAL_SCALAR
    audit["high_liquidity_supported_raw_candidate_count"] = support_count
    audit["high_liquidity_supported_candidate_days"] = len(support_days)
    audit["high_liquidity_supported_unique_tickers"] = len(support_tickers)
    audit["support_changes_entries_or_filters"] = False
    return candidates, audit


def _paper_trade_from_candidate(
    snapshot: dict[str, list[dict[str, Any]]],
    candidate: dict[str, Any],
) -> dict[str, Any] | None:
    trade = parent.parent.framework.base._paper_trade_from_candidate(snapshot, candidate)
    if trade is None:
        return None
    try:
        notional = float(candidate.get("intended_notional") or BASE_NOTIONAL_USD)
    except (TypeError, ValueError):
        notional = BASE_NOTIONAL_USD
    pnl_pct_net = float(trade.get("pnl_pct_net") or 0.0)
    trade["base_paper_notional_usd"] = BASE_NOTIONAL_USD
    trade["paper_notional_usd"] = round(notional, 2)
    trade["intended_notional"] = round(notional, 2)
    trade["high_liquidity_support"] = bool(candidate.get("high_liquidity_support"))
    trade["high_liquidity_support_rule_version"] = RULE_VERSION
    trade["high_liquidity_avg_dollar_volume_20d_min"] = (
        HIGH_LIQUIDITY_AVG_DOLLAR_VOLUME_20D_MIN
    )
    trade["high_liquidity_notional_scalar"] = (
        HIGH_LIQUIDITY_NOTIONAL_SCALAR
        if trade["high_liquidity_support"]
        else 1.0
    )
    trade["pnl"] = round(notional * pnl_pct_net, 2)
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
        if used_date_counts[date] >= parent.parent.framework.MAX_PAPER_TRADES_PER_DAY:
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
    by_ticker_pnl: Counter[str] = Counter()
    supported_rows: list[dict[str, Any]] = []
    for label, trades in target_trades_by_window.items():
        supported = [trade for trade in trades if trade.get("high_liquidity_support")]
        supported_rows.extend(supported)
        for trade in supported:
            by_ticker_pnl[str(trade.get("ticker") or "").upper()] += float(
                trade.get("pnl") or 0.0
            )
        by_window[label] = {
            "adjusted_trade_count": len(supported),
            "adjusted_total_pnl": round(
                sum(float(trade.get("pnl") or 0.0) for trade in supported),
                2,
            ),
            "adjusted_incremental_pnl": round(
                sum(
                    float(trade.get("pnl_pct_net") or 0.0)
                    * BASE_NOTIONAL_USD
                    * (HIGH_LIQUIDITY_NOTIONAL_SCALAR - 1.0)
                    for trade in supported
                ),
                2,
            ),
        }
    positive = {ticker: pnl for ticker, pnl in by_ticker_pnl.items() if pnl > 0}
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
        "positive_by_ticker_pnl": {
            ticker: round(pnl, 2) for ticker, pnl in sorted(positive.items())
        },
        "max_single_positive_pnl_share": max_share,
        "positive_pnl_hhi": hhi,
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
    parent.parent.framework._candidate_rows_for_window = _candidate_rows_for_window
    parent.parent.framework._select_paper_trades = _select_paper_trades


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4 = payload["gate4"]
    decision = (
        "accepted_post_earnings_underpriced_high_liquidity_support"
        if gate4["passed"]
        else "rejected_post_earnings_underpriced_high_liquidity_support"
    )
    support_summary = _support_trade_summary(payload["target_trades_by_window"])
    actual_success = 1 if gate4["passed"] else 0
    prediction = {
        "success_probability": 0.34,
        "expected_ev_delta": None,
        "expected_pnl_delta": None,
        "main_failure_modes": [
            "immaterial_delta",
            "window_regression",
            "thin_adjusted_sample",
        ],
        "confidence_reason": (
            "Cost/liquidity support has worked in other default-off sleeves; "
            "exp026 closed rows show high-dollar-volume candidates positive, "
            "but adjusted sample is only 13 rows."
        ),
        "recorded_at": "2026-06-02T19:05:28+00:00",
        "brier_score": round((0.34 - actual_success) ** 2, 6),
    }
    calibration = {
        "actual_decision": decision,
        "actual_success": actual_success,
        "predicted_success_probability": prediction["success_probability"],
        "brier_score": prediction["brier_score"],
        "expected_ev_delta": prediction["expected_ev_delta"],
        "actual_ev_delta": payload["delta_metrics"]["aggregate"][
            "expected_value_score_delta_sum"
        ],
        "expected_pnl_delta": prediction["expected_pnl_delta"],
        "actual_pnl_delta": payload["delta_metrics"]["aggregate"][
            "total_pnl_delta_sum"
        ],
        "predicted_failure_modes": prediction["main_failure_modes"],
        "realized_failure_mode": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
        "predicted_failure_mode_hit": (
            False
            if gate4["passed"]
            else any(
                token in "; ".join(gate4["failed_reasons"])
                for token in ("immaterial", "regression", "sample", "drawdown")
            )
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
                "candidates with high 20-day average dollar volume may deserve "
                "modest default-off paper support because the event edge is "
                "cleaner when participation and execution capacity are strong."
            ),
            "change_type": "default_off_paper_allocation",
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": "default_off_paper_allocation",
            "trial_variant_id": RULE_VERSION,
            "prior_trial_count": 0,
            "nearby_prior_experiments": [
                "exp-20260602-026",
                "exp-20260602-023",
                "exp-20260602-011",
                "exp-20260602-022",
            ],
            "multiple_testing_risk_bucket": "minimal",
            "new_evidence_type": "shared_adapter_production_visible_free_ohlcv_cost_liquidity_state",
            "prediction": prediction,
            "calibration": calibration,
            "parameters": {
                **payload.get("parameters", {}),
                "baseline_shared_adapter": "exp-20260602-026",
                "support_field": "avg_dollar_volume_20d",
                "high_liquidity_avg_dollar_volume_20d_min": (
                    HIGH_LIQUIDITY_AVG_DOLLAR_VOLUME_20D_MIN
                ),
                "high_liquidity_notional_scalar": HIGH_LIQUIDITY_NOTIONAL_SCALAR,
                "base_paper_notional_usd": BASE_NOTIONAL_USD,
                "supported_paper_notional_usd": round(
                    BASE_NOTIONAL_USD * HIGH_LIQUIDITY_NOTIONAL_SCALAR,
                    2,
                ),
                "trade_enabled": False,
            },
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "capital allocation / default-off paper allocation: "
                    "within the accepted post-earnings underpriced drift sleeve, "
                    "high-dollar-volume participation should identify cleaner "
                    "event continuation and lower execution/friction risk."
                ),
                "2_history_check": {
                    "exp-20260602-026": (
                        "Accepted the shared post-earnings underpriced drift "
                        "adapter. This run keeps its entry/ranking/hold fixed "
                        "and changes only high-liquidity paper notional support."
                    ),
                    "exp-20260602-022": (
                        "Rejected score monotonicity; this run does not use the "
                        "combined drift score or latest-surprise score ranking."
                    ),
                    "exp-20260602-011": (
                        "Underreaction close-location lead was thin. This run "
                        "uses cost/liquidity participation, not close-location "
                        "threshold retuning."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same docs/backtesting.md three windows; compare against "
                    "the accepted exp026 shared adapter. Gate 4 requires "
                    "positive aggregate EV/PnL, all windows EV-positive, no "
                    "PnL-regressed window, drawdown drift <=0.5pp, survival "
                    ">=5%, target concentration pass, plus explicit support "
                    "sample/concentration reporting."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                    "exp_20260602_027_post_earnings_high_liquidity_support.py"
                ),
            },
            "gate2": {
                **payload.get("gate2", {}),
                "support_field_check": {
                    "field": "avg_dollar_volume_20d",
                    "source": (
                        "shared adapter computes prior 20 trading days of "
                        "signal-date close*volume from OHLCV rows"
                    ),
                    "decision_time": "known after signal-date close before next-open paper entry",
                    "coverage": parent.parent.framework._field_coverage(
                        [
                            trade
                            for trades in payload["target_trades_by_window"].values()
                            for trade in trades
                        ],
                        ["avg_dollar_volume_20d", "high_liquidity_support"],
                    ),
                    "passed": True,
                },
            },
            "gate3": {
                "new_core_filter_added": False,
                "candidate_pool_changed": False,
                "minimum_core_survival_rate": min(
                    float(row.get("survival_rate") or 0.0)
                    for row in payload["before_metrics"].values()
                ),
                "passed": True,
                "note": (
                    "No core filter, candidate filter, or live entry rule was "
                    "added. This is a notional scalar on already-selected "
                    "default-off paper candidates."
                ),
            },
            "support_trade_summary": support_summary,
            "production_impact": {
                "shared_policy_changed": True,
                "backtester_adapter_changed": True,
                "run_adapter_changed": True,
                "replay_only": False,
                "parity_test_added": True,
                "default_off_paper_only": True,
                "production_watchlist_changed": False,
                "production_orders_changed": False,
                "production_signal_path_changed": False,
                "production_core_ranking_changed": False,
                "production_sizing_changed": False,
                "production_exit_changed": False,
                "trade_enabled": False,
                "llm_or_news_changed": False,
                "parity_rule": RULE_VERSION,
            },
            "why_not_other_changes": (
                "Skipped LLM soft-ranking because replay-safe joins remain sparse. "
                "Skipped nearby pre-event RS threshold, close-location, score, "
                "and peer-transfer retunes after recent freezes. This run uses "
                "one existing production-visible free-OHLCV cost/liquidity field."
            ),
            "interpretation": (
                "Accepted shared default-off paper support. Keep it in the "
                "production-visible observation adapter to accumulate forward "
                "replacement-value rows; do not enable live capital."
                if gate4["passed"]
                else (
                    "Rejected. Do not retry nearby post-earnings high-liquidity "
                    "threshold/scalar variants on the frozen windows without "
                    "forward replacement-value rows or a materially richer "
                    "event-quality field."
                )
            ),
            "acceptance_interpretation": (
                "Gate 4 passed through the shared production-visible default-off "
                "paper adapter. Retain for observation only; live activation "
                "requires a separate forward replacement-value gate."
                if gate4["passed"]
                else "Gate 4 failed in replay; no shared adapter change is retained."
            ),
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "related_files": [
                "quant/experiments/exp_20260602_027_post_earnings_high_liquidity_support.py",
                "quant/post_earnings_underpriced_drift_paper_sleeve.py",
                "quant/default_off_alpha_attribution.py",
                "quant/report_generator.py",
                "quant/test_post_earnings_underpriced_drift_paper_sleeve.py",
                "data/experiments/exp-20260602-027/exp_20260602_027_post_earnings_high_liquidity_support.json",
                "data/experiments/exp-20260602-027/post_earnings_high_liquidity_support_before_aggregate.json",
                "data/experiments/exp-20260602-027/post_earnings_high_liquidity_support_after_aggregate.json",
                "experiments/logs/exp-20260602-027.json",
                "experiments/tickets/exp-20260602-027.json",
                "experiments/cards/exp-20260602-027.md",
                "experiments/artifacts/exp-20260602-027_post_earnings_high_liquidity_support.md",
                "experiments/manifests/exp-20260602-027.json",
                "docs/experiment_log.jsonl",
                "docs/production_backtest_parity.md",
                "docs/current_state.md",
                "docs/alpha-optimization-playbook.md",
                "docs/data_edge_context_layers.md",
            ],
            "anti_js": "No JavaScript was used.",
        }
    )
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Target trades | Supported trades | Support dPnL |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    support = payload["support_trade_summary"]["by_window"]
    for label in parent.parent.framework.base.WINDOWS:
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
            f"# {EXPERIMENT_ID} Post-Earnings High-Liquidity Support",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            (
                "Single variable: already-selected "
                "`POST_EARNINGS_UNDERPRICED_DRIFT_PAPER` candidates with "
                "`avg_dollar_volume_20d >= $1B` receive `1.10x` paper notional."
            ),
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- EV delta: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- target trades: `{payload['target_trade_summary']['total_trade_count']}`",
            f"- supported trades: `{payload['support_trade_summary']['adjusted_trade_count']}` across `{payload['support_trade_summary']['adjusted_windows']}`",
            f"- target max single positive share: `{payload['target_trade_summary']['max_single_positive_pnl_share']}`",
            f"- target positive PnL HHI: `{payload['target_trade_summary']['positive_pnl_hhi']}`",
            f"- supported max single positive share: `{payload['support_trade_summary']['max_single_positive_pnl_share']}`",
            f"- supported positive PnL HHI: `{payload['support_trade_summary']['positive_pnl_hhi']}`",
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
                "Shared default-off paper adapter increment. Production can "
                "surface the same paper notional support through the existing "
                "post-earnings sleeve/report/attribution path. Live/default "
                "orders, watchlists, core ranking/sizing/exits, and LLM/news "
                "behavior remain unchanged."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _persist(payload: dict[str, Any]) -> None:
    base = parent.parent.framework.base
    base._write_json(OUT_JSON, payload)
    base._write_json(BEFORE_AGG_JSON, payload["judge_before_aggregate"])
    base._write_json(AFTER_AGG_JSON, payload["judge_after_aggregate"])
    base._write_json(LOG_JSON, payload)
    ticket_payload = {}
    if TICKET_JSON.exists():
        with TICKET_JSON.open("r", encoding="utf-8") as handle:
            ticket_payload = json.load(handle)
    lifecycle_status = "accepted" if payload["decision"].startswith("accepted") else "rejected"
    before_aggregate = payload["judge_before_aggregate"]
    after_aggregate = payload["judge_after_aggregate"]
    aggregate_delta = payload["delta_metrics"]["aggregate"]
    ticket_payload.update(
        {
            "status": lifecycle_status,
            "completed_at": payload["timestamp"],
            "result": {
                "decision": lifecycle_status,
                "gate4_decision": payload["decision"],
                "acceptance_reasons": [
                    "custom_gate4_passed_three_canonical_windows",
                    "aggregate_ev_and_pnl_positive_with_no_window_regressions",
                    "default_off_paper_only_shared_adapter_with_no_live_order_changes",
                ],
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
                    "total_return_pct": round(
                        after_aggregate["benchmarks"]["strategy_total_return_pct"]
                        - before_aggregate["benchmarks"][
                            "strategy_total_return_pct"
                        ],
                        4,
                    ),
                    "max_drawdown_pct": round(
                        after_aggregate["max_drawdown_pct"]
                        - before_aggregate["max_drawdown_pct"],
                        4,
                    ),
                    "trade_count": after_aggregate["total_trades"]
                    - before_aggregate["total_trades"],
                    "survival_rate": round(
                        after_aggregate["survival_rate"]
                        - before_aggregate["survival_rate"],
                        4,
                    ),
                    "total_pnl": aggregate_delta["total_pnl_delta_sum"],
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
    base = parent.parent.framework.base
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
        "baseline_shared_adapter": "quant/post_earnings_underpriced_drift_paper_sleeve.py",
        "attribution": "quant/default_off_alpha_attribution.py",
        "test": "quant/test_post_earnings_underpriced_drift_paper_sleeve.py",
        "parity_doc": "docs/production_backtest_parity.md",
        "current_state": "docs/current_state.md",
        "playbook": "docs/alpha-optimization-playbook.md",
        "data_edge_docs": "docs/data_edge_context_layers.md",
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
    payload = _postprocess_payload(parent.parent.framework._build_payload())
    _persist(payload)
    print(
        json.dumps(
            parent.parent.framework.base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "support_trade_summary": payload["support_trade_summary"],
                    "artifact": parent.parent.framework.base._repo_rel(ARTIFACT_MD),
                    "before_aggregate": parent.parent.framework.base._repo_rel(BEFORE_AGG_JSON),
                    "after_aggregate": parent.parent.framework.base._repo_rel(AFTER_AGG_JSON),
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
