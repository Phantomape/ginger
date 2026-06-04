"""exp-20260604-019: Space satellite-connectivity trend support.

This alpha search keeps the accepted default-off Space route fixed through the
shared cost/liquidity helper. It changes one paper-only allocation variable:
already selected governed Space trend_long candidates in the production-visible
satellite-connectivity segment receive a modest additional notional support.

Core entries, ranking, sizing, exits, heat, LLM/news replay, watchlists, and
live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import exp_20260602_025_space_cost_liquidity_shared_helper as accepted_shared  # noqa: E402


EXPERIMENT_ID = "exp-20260604-019"
STEM = "exp_20260604_019_space_satellite_connectivity_trend_support"
TRIAL_FAMILY = "governed_space_satellite_connectivity_selected_trend_support"
CHANGED_VARIABLE = "space_selected_satellite_connectivity_trend_support_v1"
RULE_VERSION = "space_selected_satellite_connectivity_trend_support_v1"

ACCEPTED_BASELINE_EXPERIMENT_ID = "exp-20260602-025"
TARGET_STRATEGY = "trend_long"
SATELLITE_CONNECTIVITY_TICKERS = ("ASTS", "GSAT", "IRDM", "SATS", "VSAT")
SATELLITE_CONNECTIVITY_SUPPORT_SCALAR = 1.05
BASE_NOTIONAL_USD = 10_000.0
MIN_SUPPORTED_TRADES = 4
MIN_SUPPORTED_WINDOWS = 2
HARD_MIN_EV_DELTA_VS_ACCEPTED_PCT = 0.10

source = accepted_shared.source
space_base = source.space_base
REPO_ROOT = source.REPO_ROOT
WINDOWS = source.WINDOWS
TARGET_TICKERS = source.TARGET_TICKERS
TARGET_SECTOR_MAP = source.TARGET_SECTOR_MAP
SOURCE_UNIVERSE_STATE = source.SOURCE_UNIVERSE_STATE
SOURCE_OHLCV_EXPERIMENT_ID = source.SOURCE_OHLCV_EXPERIMENT_ID

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
ACCEPTED_BASELINE_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / ACCEPTED_BASELINE_EXPERIMENT_ID
    / "exp_20260602_025_space_cost_liquidity_shared_helper.json"
)


def _repo_rel(path: Path | str) -> str:
    return space_base._repo_rel(path)


def _segment_support_state(trade: dict[str, Any], market_state: dict[str, Any]) -> dict[str, Any]:
    ticker = str(trade.get("ticker") or "").upper()
    strategy = str(trade.get("strategy") or "")
    selected = bool(market_state.get("passed"))
    in_segment = ticker in SATELLITE_CONNECTIVITY_TICKERS
    supported = selected and strategy == TARGET_STRATEGY and in_segment
    if supported:
        reason = "selected_satellite_connectivity_trend"
    elif not selected:
        reason = "not_selected_space_candidate"
    elif strategy != TARGET_STRATEGY:
        reason = "not_trend_long"
    elif not in_segment:
        reason = "not_satellite_connectivity_segment"
    else:
        reason = "not_supported"
    return {
        "rule_version": RULE_VERSION,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
        "support_bucket": supported,
        "support_reason": reason,
        "strategy": strategy,
        "target_strategy": TARGET_STRATEGY,
        "ticker": ticker,
        "segment_tickers": list(SATELLITE_CONNECTIVITY_TICKERS),
        "support_scalar": SATELLITE_CONNECTIVITY_SUPPORT_SCALAR if supported else 1.0,
        "uses_existing_signal_strategy_field": True,
        "uses_production_visible_universe_segment": True,
        "trade_enabled": False,
        "alters_orders": False,
    }


def _strategy_with_segment_support(
    snapshot: str,
    trades: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    base_states = source._strategy_high_close_thrust_with_cost_liquidity_support(
        snapshot,
        trades,
    )
    out: dict[str, dict[str, Any]] = {}
    for trade in trades:
        key = f"{trade.get('entry_date')}|{trade.get('ticker')}|{trade.get('exit_date')}"
        state = dict(base_states.get(key) or {})
        state["space_satellite_connectivity_trend_support"] = _segment_support_state(
            trade,
            state,
        )
        out[key] = state
    return out


def _supported_notional_trade(
    trade: dict[str, Any],
    market_state: dict[str, Any],
) -> dict[str, Any]:
    pnl_pct = float(trade.get("pnl_pct_net") or 0.0)
    cost_liquidity = market_state.get("space_cost_liquidity_support") or {}
    segment_support = market_state.get("space_satellite_connectivity_trend_support") or {}
    pre_segment_notional = float(
        cost_liquidity.get("supported_notional_usd") or BASE_NOTIONAL_USD
    )
    segment_scalar = float(segment_support.get("support_scalar") or 1.0)
    notional = round(pre_segment_notional * segment_scalar, 2)
    return {
        **trade,
        "core_sized_pnl": space_base._round(trade.get("pnl"), 2),
        "core_sized_shares": trade.get("shares"),
        "base_paper_notional_usd": BASE_NOTIONAL_USD,
        "pre_segment_paper_notional_usd": pre_segment_notional,
        "paper_notional_usd": notional,
        "space_cost_liquidity_support": cost_liquidity,
        "space_satellite_connectivity_trend_support": segment_support,
        "pnl": round(notional * pnl_pct, 2),
        "pnl_pct_net": space_base._round(pnl_pct, 6),
        "shares": None,
        "market_confirmation": market_state,
    }


def _aggregate_metrics(metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "expected_value_score_sum": space_base._round(
            sum(float(row.get("expected_value_score") or 0.0) for row in metrics.values()),
            4,
        ),
        "total_pnl_sum": space_base._round(
            sum(float(row.get("total_pnl") or 0.0) for row in metrics.values()),
            2,
        ),
        "max_drawdown_pct_max": space_base._round(
            max(float(row.get("max_drawdown_pct") or 0.0) for row in metrics.values()),
            4,
        ),
        "trade_count_sum": sum(int(row.get("trade_count") or 0) for row in metrics.values()),
        "min_survival_rate": space_base._round(
            min(float(row.get("survival_rate") or 0.0) for row in metrics.values()),
            4,
        ),
    }


def _accepted_baseline_comparison(payload: dict[str, Any]) -> dict[str, Any]:
    accepted_payload = json.loads(ACCEPTED_BASELINE_JSON.read_text(encoding="utf-8"))
    accepted_after = accepted_payload["after_metrics"]
    current_after = payload["after_metrics"]
    by_window = {}
    windows_ev_regressed = 0
    windows_pnl_regressed = 0
    for label in WINDOWS:
        ev_delta = space_base._round(
            float(current_after[label]["expected_value_score"])
            - float(accepted_after[label]["expected_value_score"]),
            4,
        )
        pnl_delta = space_base._round(
            float(current_after[label]["total_pnl"])
            - float(accepted_after[label]["total_pnl"]),
            2,
        )
        by_window[label] = {
            "expected_value_score_delta": ev_delta,
            "total_pnl_delta": pnl_delta,
        }
        if ev_delta < 0:
            windows_ev_regressed += 1
        if pnl_delta < 0:
            windows_pnl_regressed += 1
    accepted_aggregate = _aggregate_metrics(accepted_after)
    current_aggregate = _aggregate_metrics(current_after)
    actual_ev_delta = space_base._round(
        current_aggregate["expected_value_score_sum"]
        - accepted_aggregate["expected_value_score_sum"],
        4,
    )
    required_ev_delta = space_base._round(
        accepted_aggregate["expected_value_score_sum"]
        * HARD_MIN_EV_DELTA_VS_ACCEPTED_PCT,
        4,
    )
    return {
        "baseline_experiment_id": ACCEPTED_BASELINE_EXPERIMENT_ID,
        "baseline_artifact": _repo_rel(ACCEPTED_BASELINE_JSON),
        "accepted_after_aggregate": accepted_aggregate,
        "current_after_aggregate": current_aggregate,
        "aggregate_expected_value_score_delta": actual_ev_delta,
        "aggregate_total_pnl_delta": space_base._round(
            current_aggregate["total_pnl_sum"] - accepted_aggregate["total_pnl_sum"],
            2,
        ),
        "hard_min_ev_delta_vs_accepted_pct": HARD_MIN_EV_DELTA_VS_ACCEPTED_PCT,
        "hard_min_ev_delta_vs_accepted": required_ev_delta,
        "hard_min_ev_delta_passed": actual_ev_delta > required_ev_delta,
        "windows_ev_regressed": windows_ev_regressed,
        "windows_pnl_regressed": windows_pnl_regressed,
        "by_window": by_window,
    }


def _support_trade_summary(payload: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for label, trades in payload.get("target_trades_by_window", {}).items():
        for trade in trades:
            support = trade.get("space_satellite_connectivity_trend_support") or {}
            if support.get("support_bucket"):
                rows.append({**trade, "window": label})
    return {
        "trade_count": len(rows),
        "windows": sorted({row["window"] for row in rows}),
        "incremental_notional_usd": space_base._round(
            sum(
                float(row.get("paper_notional_usd") or 0.0)
                - float(row.get("pre_segment_paper_notional_usd") or 0.0)
                for row in rows
            ),
            2,
        ),
        "incremental_pnl": space_base._round(
            sum(
                float(row.get("pnl_pct_net") or 0.0)
                * (
                    float(row.get("paper_notional_usd") or 0.0)
                    - float(row.get("pre_segment_paper_notional_usd") or 0.0)
                )
                for row in rows
            ),
            2,
        ),
        "by_ticker": {
            ticker: space_base._round(
                sum(float(row.get("pnl") or 0.0) for row in rows if row.get("ticker") == ticker),
                2,
            )
            for ticker in sorted({str(row.get("ticker") or "") for row in rows})
            if ticker
        },
        "rows": rows,
    }


def _configure_source_runner() -> None:
    source.EXPERIMENT_ID = EXPERIMENT_ID
    source.STEM = STEM
    source.CHANGED_VARIABLE = CHANGED_VARIABLE
    source.RULE_VERSION = accepted_shared.shared.SPACE_CATALYST_COST_LIQUIDITY_SUPPORT_RULE_VERSION
    source.OUT_DIR = OUT_DIR
    source.OUT_JSON = OUT_JSON
    source.LOG_JSON = LOG_JSON
    source.TICKET_JSON = TICKET_JSON
    source.CARD_MD = CARD_MD
    source.EXPERIMENT_LOG = EXPERIMENT_LOG
    source._cost_liquidity_support_state = (
        accepted_shared._shared_cost_liquidity_support_state
    )
    source._configure_space_base()
    space_base.TRIAL_FAMILY = TRIAL_FAMILY
    space_base.CHANGED_VARIABLE = CHANGED_VARIABLE
    space_base._market_confirmation = _strategy_with_segment_support
    space_base._fixed_notional_trade = _supported_notional_trade


def _customize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    accepted_comparison = _accepted_baseline_comparison(payload)
    support_summary = _support_trade_summary(payload)
    base_gate4_passed = bool(payload["gate4"]["passed"])
    soft_current_accepted_improved = (
        accepted_comparison["aggregate_expected_value_score_delta"] > 0
        and accepted_comparison["aggregate_total_pnl_delta"] > 0
        and accepted_comparison["windows_ev_regressed"] == 0
        and accepted_comparison["windows_pnl_regressed"] == 0
    )
    support_sample_passed = (
        support_summary["trade_count"] >= MIN_SUPPORTED_TRADES
        and len(support_summary["windows"]) >= MIN_SUPPORTED_WINDOWS
    )
    gate4_passed = (
        base_gate4_passed
        and soft_current_accepted_improved
        and accepted_comparison["hard_min_ev_delta_passed"]
        and support_sample_passed
    )
    if gate4_passed:
        decision = "accepted_space_satellite_connectivity_trend_support"
    elif soft_current_accepted_improved and support_sample_passed:
        decision = "rejected_positive_below_space_hard_min_satellite_connectivity_trend_support"
    else:
        decision = "rejected_space_satellite_connectivity_trend_support"
    aggregate = payload["delta_metrics"]["aggregate"]
    before_metrics = payload["before_metrics"]
    min_survival = min(
        float(row.get("survival_rate") or 0.0) for row in before_metrics.values()
    )
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    predicted_success_probability = 0.31
    actual_success = bool(gate4_passed)
    brier_score = ((1.0 if actual_success else 0.0) - predicted_success_probability) ** 2
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": timestamp,
            "lane": "alpha_search",
            "status": decision,
            "decision": decision,
            "change_type": "default_off_paper_allocation",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": EXPERIMENT_ID,
            "prior_trial_count": 1,
            "nearby_prior_experiments": [
                "exp-20260527-904",
                "exp-20260528-026",
                "exp-20260529-020",
                "exp-20260602-025",
                "exp-20260603-019",
                "exp-20260604-018",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "accepted_route_trade_distribution_audit",
            "hypothesis": (
                "Selected governed Space satellite-connectivity trend_long "
                "candidates may deserve modest paper support because the accepted "
                "route's trend winners cluster in production-visible "
                "satellite-connectivity names."
            ),
            "prediction": {
                "success_probability": predicted_success_probability,
                "expected_ev_delta": 0.03,
                "expected_pnl_delta": 700.0,
                "main_failure_modes": [
                    "segment_overfit",
                    "current_space_route_regression",
                    "hard_min_ev_not_met",
                    "concentration_failed",
                ],
                "confidence_reason": (
                    "The prior event branch had no sample. This segment support "
                    "uses actual accepted-route trades and a production-visible "
                    "universe segment, but it is still a small-sample allocation "
                    "test judged against the current accepted artifact."
                ),
                "recorded_at": timestamp,
            },
            "calibration": {
                "actual_success": actual_success,
                "actual_decision": decision,
                "predicted_success_probability": predicted_success_probability,
                "brier_score": space_base._round(brier_score, 4),
                "calibration_direction": (
                    "underconfident" if actual_success else "overconfident"
                ),
                "actual_ev_delta_vs_current_accepted": (
                    accepted_comparison["aggregate_expected_value_score_delta"]
                ),
                "actual_pnl_delta_vs_current_accepted": (
                    accepted_comparison["aggregate_total_pnl_delta"]
                ),
            },
            "parameters": {
                "base_notional_usd": BASE_NOTIONAL_USD,
                "support_scalar": SATELLITE_CONNECTIVITY_SUPPORT_SCALAR,
                "target_strategy": TARGET_STRATEGY,
                "satellite_connectivity_tickers": list(SATELLITE_CONNECTIVITY_TICKERS),
                "target_tickers": payload["parameters"]["target_tickers"],
                "target_sector_map": TARGET_SECTOR_MAP,
                "accepted_baseline_experiment_id": ACCEPTED_BASELINE_EXPERIMENT_ID,
                "source_universe_state": _repo_rel(SOURCE_UNIVERSE_STATE),
                "source_ohlcv_experiment_id": SOURCE_OHLCV_EXPERIMENT_ID,
                "hard_min_ev_delta_vs_accepted_pct": HARD_MIN_EV_DELTA_VS_ACCEPTED_PCT,
                "rule_version": RULE_VERSION,
                "locked_variables": [
                    "core signal rules",
                    "core ranking",
                    "core sizing",
                    "core exits",
                    "portfolio heat",
                    "slot rules",
                    "LLM/news replay",
                    "production watchlists",
                    "live/default orders",
                    "target governed Space ticker list",
                    "accepted high-close/thrust trend branch",
                    "accepted ARKX/UFO breakout complement admission",
                    "accepted Space cost/liquidity support helper",
                ],
                "anti_js": "No JavaScript was used.",
            },
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "capital allocation: already selected Space trend_long "
                    "satellite-connectivity candidates may deserve 1.05x paper "
                    "support after accepted route selection."
                ),
                "2_history_check": {
                    "exp-20260527-904": (
                        "Rejected broad trend-only Space route; this only supports "
                        "already selected current-route trend candidates."
                    ),
                    "exp-20260602-025": "Current accepted Space comparator.",
                    "exp-20260603-019": (
                        "Rejected sector-residual support; this uses governed "
                        "Space theme segment, not public sector median."
                    ),
                    "exp-20260604-018": (
                        "Rejected defense-budget delayed branch due zero "
                        "incremental sample; this uses actual accepted-route trades."
                    ),
                    "llm_soft_ranking": (
                        "Skipped because replay-safe Space semantic ranking rows "
                        "and closed replacement outcomes remain sparse."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same docs/backtesting.md three Space windows; improve "
                    "aggregate EV/PnL versus accepted exp-20260602-025 by the "
                    "state-surface hard minimum, no EV/PnL-regressed windows, "
                    f">={MIN_SUPPORTED_TRADES} supported trades across "
                    f">={MIN_SUPPORTED_WINDOWS} windows, survival >=5%, "
                    "concentration guard passing, and no production/backtest split."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe quant\\experiments\\"
                    "exp_20260604_019_space_satellite_connectivity_trend_support.py"
                ),
            },
            "accepted_baseline_comparison": accepted_comparison,
            "support_trade_summary": support_summary,
            "production_impact": {
                "shared_policy_changed": False,
                "backtester_adapter_changed": False,
                "run_adapter_changed": False,
                "replay_only": True,
                "parity_test_added": False,
                "default_off_paper_only": True,
                "metadata_only": True,
                "production_watchlist_changed": False,
                "production_orders_changed": False,
                "production_ranking_changed": False,
                "production_sizing_changed": False,
                "production_exits_changed": False,
                "trade_enabled": False,
                "live_space_slots": 0,
                "promotion_requirement": (
                    "A passing result would still need a shared default-off "
                    "Space segment-support helper and parity tests before retention; "
                    "live Space slots remain zero."
                ),
            },
            "why_not_other_changes": (
                "Skipped LLM soft-ranking and the event branch after zero sample. "
                "Skipped broad ticker expansion and price/ETF threshold retunes. "
                "This tests one production-visible segment allocation surface."
            ),
            "interpretation": (
                "Accepted by the strict current-route comparator."
                if gate4_passed
                else (
                    "The satellite-connectivity trend support did not clear Gate 4 "
                    "against the current accepted Space route; do not promote or "
                    "retune this allocation surface on the frozen windows."
                )
            ),
            "next_evidence_needed": (
                "Forward accepted-route replacement-value rows by Space segment, "
                "or a genuinely new production-visible Space catalyst-quality field."
            ),
            "related_files": [
                _repo_rel(Path(__file__)),
                _repo_rel(OUT_JSON),
                _repo_rel(LOG_JSON),
                _repo_rel(TICKET_JSON),
                _repo_rel(CARD_MD),
                _repo_rel(MANIFEST_JSON),
                _repo_rel(EXPERIMENT_LOG),
                _repo_rel(REGISTRY_JSON),
                _repo_rel(ACCEPTED_BASELINE_JSON),
            ],
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["gate2"]["runtime_fields"] = [
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
        "target OHLCV rows in all three Space replay snapshots",
        "existing signal strategy field generated before next-open paper entry",
        "production-visible governed Space universe theme segment",
    ]
    payload["gate3"].update(
        {
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": space_base._round(min_survival, 4),
            "note": (
                "No new core filter, entry rule, or paper admission filter was "
                "added. The experiment changes only default-off paper notional "
                "for already selected Space candidates."
            ),
        }
    )
    payload["gate4"].update(
        {
            "acceptance_rule": payload["gate_questions"]["4_acceptance_standard"],
            "passed": gate4_passed,
            "base_gate4_passed": base_gate4_passed,
            "soft_current_accepted_improved": soft_current_accepted_improved,
            "hard_min_ev_delta_passed": accepted_comparison[
                "hard_min_ev_delta_passed"
            ],
            "support_sample_passed": support_sample_passed,
            "aggregate_expected_value_score_delta": aggregate[
                "expected_value_score_delta_sum"
            ],
            "aggregate_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        }
    )
    payload["rejection_reason"] = None if gate4_passed else (
        "failed_current_accepted_comparator_or_space_hard_min"
    )
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Target trades | Filtered |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} | {filtered} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                filtered=len(payload["filtered_out_target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    accepted_delta = payload["accepted_baseline_comparison"]
    support = payload["support_trade_summary"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Space Satellite-Connectivity Trend Support",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: keep the accepted Space route fixed and add 1.05x default-off paper support only to already selected `trend_long` candidates in the governed satellite-connectivity Space segment.",
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate Versus Core",
            "",
            f"- EV delta: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- target trades: `{payload['target_trade_summary']['total_trade_count']}` across `{len(payload['target_trade_summary']['windows_with_target_trades'])}` windows",
            f"- max single positive share: `{payload['target_trade_summary']['max_single_positive_pnl_share']}`",
            "",
            "## Incremental Versus Accepted Space Route",
            "",
            f"- baseline: `{accepted_delta['baseline_experiment_id']}`",
            f"- EV delta: `{accepted_delta['aggregate_expected_value_score_delta']}`",
            f"- required EV delta: `{accepted_delta['hard_min_ev_delta_vs_accepted']}`",
            f"- PnL delta: `${accepted_delta['aggregate_total_pnl_delta']}`",
            f"- EV-regressed windows: `{accepted_delta['windows_ev_regressed']}`",
            f"- PnL-regressed windows: `{accepted_delta['windows_pnl_regressed']}`",
            f"- supported trades: `{support['trade_count']}`",
            f"- supported windows: `{', '.join(support['windows'])}`",
            f"- incremental support PnL: `${support['incremental_pnl']}`",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "Replay-only and default-off paper only. No live orders, ranking, sizing, exits, watchlists, or Space slots changed.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _update_ticket_and_registry(payload: dict[str, Any]) -> None:
    ticket = {}
    if TICKET_JSON.exists():
        ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8"))
    ticket.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "lane": "alpha_search",
            "owner": "alpha-search-space",
            "hypothesis": payload["hypothesis"],
            "change_type": payload["change_type"],
            "mechanism_family": "production_visible_default_off_space_segment_allocation_alpha",
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": EXPERIMENT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "prior_trial_count": payload["prior_trial_count"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "prediction": payload["prediction"],
            "calibration": payload["calibration"],
            "completed_at": payload["timestamp"],
            "result": {
                "artifact": _repo_rel(CARD_MD),
                "decision": payload["decision"],
                "expected_value_score_delta": payload["expected_value_score_delta"],
                "json": _repo_rel(OUT_JSON),
                "summary": payload["interpretation"],
                "total_pnl_delta": payload["total_pnl_delta"],
            },
        }
    )
    space_base._write_json(TICKET_JSON, ticket)

    if REGISTRY_JSON.exists():
        registry = json.loads(REGISTRY_JSON.read_text(encoding="utf-8"))
        entry = {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "lane": "alpha_search",
            "owner": "alpha-search-space",
            "hypothesis": payload["hypothesis"],
            "ticket_file": f"experiments/tickets/{EXPERIMENT_ID}.json",
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        experiments = registry.setdefault("experiments", [])
        for index, existing in enumerate(experiments):
            if existing.get("experiment_id") == EXPERIMENT_ID:
                experiments[index] = {**existing, **entry}
                break
        else:
            experiments.append(entry)
        REGISTRY_JSON.write_text(
            json.dumps(registry, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


def _update_manifest(payload: dict[str, Any]) -> None:
    manifest = {}
    if MANIFEST_JSON.exists():
        manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))
    manifest.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "files": {
                **(manifest.get("files") or {}),
                "runner": {"path": f"quant/experiments/{STEM}.py", "exists": True},
                "data": {"path": _repo_rel(OUT_JSON), "exists": OUT_JSON.exists()},
                "log": {"path": _repo_rel(LOG_JSON), "exists": LOG_JSON.exists()},
                "card": {"path": _repo_rel(CARD_MD), "exists": CARD_MD.exists()},
                "ticket": {"path": _repo_rel(TICKET_JSON), "exists": TICKET_JSON.exists()},
            },
            "result": {
                "decision": payload["decision"],
                "json": _repo_rel(OUT_JSON),
                "card": _repo_rel(CARD_MD),
            },
        }
    )
    space_base._write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any]) -> None:
    space_base._write_json(OUT_JSON, payload)
    space_base._write_json(LOG_JSON, payload)
    space_base._write_text(CARD_MD, _build_report(payload))
    space_base._upsert_jsonl(EXPERIMENT_LOG, payload)
    _update_ticket_and_registry(payload)
    _update_manifest(payload)


def main() -> int:
    _configure_source_runner()
    payload = _customize_payload(space_base._build_payload())
    _persist(payload)
    print(
        json.dumps(
            space_base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "accepted_baseline_comparison": payload[
                        "accepted_baseline_comparison"
                    ],
                    "support_trade_summary": payload["support_trade_summary"],
                    "gate4": payload["gate4"],
                    "card": _repo_rel(CARD_MD),
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
