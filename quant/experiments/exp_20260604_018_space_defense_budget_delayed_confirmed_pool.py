"""exp-20260604-018: Space defense-budget delayed confirmed pool.

This alpha search keeps the accepted default-off Space route fixed through the
shared cost/liquidity helper, then tests one additional paper-only routing
branch: trend_long governed Space candidates whose current event-state profile
is both defense-budget delayed-benchmark positive and same-theme winner
positive.

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

import space_catalyst_sleeve as shared  # noqa: E402
import exp_20260602_025_space_cost_liquidity_shared_helper as accepted_shared  # noqa: E402


EXPERIMENT_ID = "exp-20260604-018"
STEM = "exp_20260604_018_space_defense_budget_delayed_confirmed_pool"
TRIAL_FAMILY = "governed_space_defense_budget_delayed_confirmed_candidate_pool"
CHANGED_VARIABLE = "space_defense_budget_delayed_confirmed_same_theme_candidate_pool_v1"
RULE_VERSION = "space_defense_budget_delayed_confirmed_pool_v1"

ACCEPTED_BASELINE_EXPERIMENT_ID = "exp-20260602-025"
TARGET_STRATEGY = "trend_long"
BASE_NOTIONAL_USD = 10_000.0
MIN_INCREMENTAL_BRANCH_TRADES = 3
MIN_INCREMENTAL_BRANCH_WINDOWS = 2
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


def _defense_budget_delayed_confirmed_profiles() -> dict[str, dict[str, Any]]:
    profiles = shared.space_catalyst_forward_replacement_positive_profiles(
        included_tickers=TARGET_TICKERS
    )
    out: dict[str, dict[str, Any]] = {}
    for ticker, profile in profiles.items():
        if not shared._is_space_defense_budget_delayed_benchmark_profile(profile):
            continue
        if not shared._is_space_defense_budget_same_theme_winner_profile(profile):
            continue
        out[ticker] = profile
    return out


def _profile_summary(profile: dict[str, Any] | None) -> dict[str, Any] | None:
    if not profile:
        return None
    return {
        "horizon": profile.get("horizon"),
        "closed_event_count": profile.get("closed_event_count"),
        "avg_5d_cash_relative_pnl": profile.get("avg_5d_cash_relative_pnl"),
        "avg_10d_cash_relative_pnl": profile.get("avg_10d_cash_relative_pnl"),
        "avg_10d_same_theme_replacement_value": (
            profile.get("avg_10d_same_theme_replacement_value")
        ),
        "avg_10d_spy_relative_value": profile.get("avg_10d_spy_relative_value"),
        "avg_10d_qqq_relative_value": profile.get("avg_10d_qqq_relative_value"),
        "avg_10d_ufo_relative_value": profile.get("avg_10d_ufo_relative_value"),
        "avg_10d_arkx_relative_value": profile.get("avg_10d_arkx_relative_value"),
        "event_ids": profile.get("event_ids") or [],
        "semantic_buckets": profile.get("semantic_buckets") or [],
        "source_types": profile.get("source_types") or [],
    }


def _strategy_with_defense_budget_delayed_confirmed_branch(
    snapshot: str,
    trades: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    base_states = source._strategy_high_close_thrust_with_cost_liquidity_support(
        snapshot,
        trades,
    )
    profiles = _defense_budget_delayed_confirmed_profiles()
    out: dict[str, dict[str, Any]] = {}
    for trade in trades:
        key = f"{trade.get('entry_date')}|{trade.get('ticker')}|{trade.get('exit_date')}"
        state = dict(base_states.get(key) or {})
        ticker = str(trade.get("ticker") or "").upper()
        strategy = str(trade.get("strategy") or "")
        profile = profiles.get(ticker)
        base_passed = bool(state.get("passed"))
        branch_profile_passed = bool(profile) and strategy == TARGET_STRATEGY
        incremental_branch_passed = branch_profile_passed and not base_passed
        branch_state = {
            "rule_version": RULE_VERSION,
            "known_at": (
                "after_event_state_ledger_update_before_default_off_paper_review"
            ),
            "uses_existing_signal_strategy_field": True,
            "uses_shared_space_event_state_profile": True,
            "uses_llm": False,
            "target_strategy": TARGET_STRATEGY,
            "strategy": strategy,
            "profile_bucket": bool(profile),
            "branch_profile_passed": branch_profile_passed,
            "incremental_branch_passed": incremental_branch_passed,
            "defense_budget_delayed_benchmark_profile": _profile_summary(profile),
            "trade_enabled": False,
            "alters_orders": False,
            "replay_only_point_in_time_limit": (
                "The current event-state ledger is auditable but not a "
                "point-in-time historical adapter for these replay windows."
            ),
        }
        state["space_defense_budget_delayed_confirmed_branch"] = branch_state
        state["passed"] = base_passed or branch_profile_passed
        out[key] = state
    return out


def _fixed_notional_trade(
    trade: dict[str, Any],
    market_state: dict[str, Any],
) -> dict[str, Any]:
    pnl_pct = float(trade.get("pnl_pct_net") or 0.0)
    support = market_state.get("space_cost_liquidity_support") or {}
    notional = float(support.get("supported_notional_usd") or BASE_NOTIONAL_USD)
    branch = market_state.get("space_defense_budget_delayed_confirmed_branch") or {}
    return {
        **trade,
        "core_sized_pnl": space_base._round(trade.get("pnl"), 2),
        "core_sized_shares": trade.get("shares"),
        "base_paper_notional_usd": BASE_NOTIONAL_USD,
        "paper_notional_usd": notional,
        "space_cost_liquidity_support": support,
        "space_defense_budget_delayed_confirmed_branch": branch,
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
    required_ev_delta = space_base._round(
        accepted_aggregate["expected_value_score_sum"]
        * HARD_MIN_EV_DELTA_VS_ACCEPTED_PCT,
        4,
    )
    actual_ev_delta = space_base._round(
        current_aggregate["expected_value_score_sum"]
        - accepted_aggregate["expected_value_score_sum"],
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


def _branch_trade_summary(payload: dict[str, Any]) -> dict[str, Any]:
    branch_rows = []
    incremental_rows = []
    for label, trades in payload.get("target_trades_by_window", {}).items():
        for trade in trades:
            branch = trade.get("space_defense_budget_delayed_confirmed_branch") or {}
            if branch.get("branch_profile_passed"):
                branch_rows.append({**trade, "window": label})
            if branch.get("incremental_branch_passed"):
                incremental_rows.append({**trade, "window": label})
    return {
        "branch_trade_count": len(branch_rows),
        "branch_windows": sorted({row["window"] for row in branch_rows}),
        "incremental_trade_count": len(incremental_rows),
        "incremental_windows": sorted({row["window"] for row in incremental_rows}),
        "incremental_total_pnl": space_base._round(
            sum(float(row.get("pnl") or 0.0) for row in incremental_rows),
            2,
        ),
        "incremental_by_ticker": {
            ticker: space_base._round(
                sum(
                    float(row.get("pnl") or 0.0)
                    for row in incremental_rows
                    if row.get("ticker") == ticker
                ),
                2,
            )
            for ticker in sorted({str(row.get("ticker") or "") for row in incremental_rows})
            if ticker
        },
        "profile_tickers": sorted(_defense_budget_delayed_confirmed_profiles()),
        "rows": incremental_rows,
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
    space_base._market_confirmation = (
        _strategy_with_defense_budget_delayed_confirmed_branch
    )
    space_base._fixed_notional_trade = _fixed_notional_trade


def _customize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    accepted_comparison = _accepted_baseline_comparison(payload)
    branch_summary = _branch_trade_summary(payload)
    base_gate4_passed = bool(payload["gate4"]["passed"])
    improves_current_accepted = (
        accepted_comparison["aggregate_expected_value_score_delta"] > 0
        and accepted_comparison["aggregate_total_pnl_delta"] > 0
        and accepted_comparison["windows_ev_regressed"] == 0
        and accepted_comparison["windows_pnl_regressed"] == 0
        and accepted_comparison["hard_min_ev_delta_passed"]
    )
    incremental_sample_passed = (
        branch_summary["incremental_trade_count"] >= MIN_INCREMENTAL_BRANCH_TRADES
        and len(branch_summary["incremental_windows"]) >= MIN_INCREMENTAL_BRANCH_WINDOWS
    )
    metrics_gate_passed = (
        base_gate4_passed
        and improves_current_accepted
        and incremental_sample_passed
    )
    retention_blocked_by_replay_only_event_profile = True
    gate4_passed = metrics_gate_passed and not retention_blocked_by_replay_only_event_profile
    if metrics_gate_passed:
        decision = "positive_replay_lead_blocked_by_point_in_time_event_adapter"
    else:
        decision = "rejected_space_defense_budget_delayed_confirmed_pool"
    aggregate = payload["delta_metrics"]["aggregate"]
    before_metrics = payload["before_metrics"]
    min_survival = min(
        float(row.get("survival_rate") or 0.0) for row in before_metrics.values()
    )
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    predicted_success_probability = 0.22
    actual_success = bool(gate4_passed)
    brier_score = ((1.0 if actual_success else 0.0) - predicted_success_probability) ** 2
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": timestamp,
            "lane": "alpha_search",
            "status": decision,
            "decision": decision,
            "change_type": "candidate_pool_paper_sleeve_shadow",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": EXPERIMENT_ID,
            "prior_trial_count": 5,
            "nearby_prior_experiments": [
                "exp-20260513-113",
                "exp-20260514-030",
                "exp-20260514-051",
                "exp-20260515-021",
                "exp-20260602-025",
                "exp-20260603-019",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "new_forward_event_state_rows",
            "hypothesis": (
                "Official Space defense-budget events may produce delayed "
                "absorption alpha when a governed same-theme trend_long "
                "candidate has both defense-budget delayed-benchmark evidence "
                "and same-theme winner evidence."
            ),
            "prediction": {
                "success_probability": predicted_success_probability,
                "expected_ev_delta": 0.05,
                "expected_pnl_delta": 1000.0,
                "main_failure_modes": [
                    "thin_sample",
                    "lookahead_risk",
                    "current_space_route_regression",
                    "concentration_failed",
                ],
                "confidence_reason": (
                    "The latest event ledger shows defense-budget events were "
                    "weak early but strong at 10d/20d. Prior broad defense-budget "
                    "and sector-residual tests warn against another scalar retune, "
                    "so this tests a narrow candidate route and blocks retention "
                    "without point-in-time event replay."
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
                "metrics_gate_passed": metrics_gate_passed,
                "actual_ev_delta_vs_current_accepted": (
                    accepted_comparison["aggregate_expected_value_score_delta"]
                ),
                "actual_pnl_delta_vs_current_accepted": (
                    accepted_comparison["aggregate_total_pnl_delta"]
                ),
            },
            "parameters": {
                "base_notional_usd": BASE_NOTIONAL_USD,
                "target_strategy": TARGET_STRATEGY,
                "target_tickers": payload["parameters"]["target_tickers"],
                "target_sector_map": TARGET_SECTOR_MAP,
                "accepted_baseline_experiment_id": ACCEPTED_BASELINE_EXPERIMENT_ID,
                "rule_version": RULE_VERSION,
                "source_universe_state": _repo_rel(SOURCE_UNIVERSE_STATE),
                "source_ohlcv_experiment_id": SOURCE_OHLCV_EXPERIMENT_ID,
                "event_ledger_path": _repo_rel(shared.DEFAULT_SPACE_CATALYST_EVENT_LEDGER_PATH),
                "hard_min_ev_delta_vs_accepted_pct": HARD_MIN_EV_DELTA_VS_ACCEPTED_PCT,
                "min_incremental_branch_trades": MIN_INCREMENTAL_BRANCH_TRADES,
                "min_incremental_branch_windows": MIN_INCREMENTAL_BRANCH_WINDOWS,
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
                    "entry/candidate_pool: add a paper-only trend_long branch "
                    "for governed Space tickers with defense-budget delayed "
                    "benchmark and same-theme winner event-state profiles."
                ),
                "2_history_check": {
                    "exp-20260513-113": (
                        "Accepted broad forward replacement-positive risk scalar; "
                        "this does not retune that scalar."
                    ),
                    "exp-20260514-030": (
                        "Accepted delayed absorption trend profile; this requires "
                        "the more specific defense-budget plus same-theme condition."
                    ),
                    "exp-20260514-051": (
                        "Prior defense-budget delayed benchmark trend profile; "
                        "current test is judged versus the latest accepted Space "
                        "route and blocks retention without point-in-time replay."
                    ),
                    "exp-20260515-021": (
                        "Prior defense-budget same-theme winner profile; this "
                        "requires both delayed and same-theme evidence."
                    ),
                    "exp-20260602-025": (
                        "Current accepted shared Space cost/liquidity helper and "
                        "main comparator."
                    ),
                    "exp-20260603-019": (
                        "Rejected generic sector-residual support; this avoids "
                        "another sector scalar."
                    ),
                    "llm_soft_ranking": (
                        "Skipped because replay-safe Space semantic ranking rows "
                        "and closed same-theme outcomes are still sparse."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same docs/backtesting.md three Space windows; improve "
                    "aggregate EV/PnL versus accepted exp-20260602-025 by the "
                    "state-surface hard minimum, no EV/PnL-regressed windows, "
                    f">={MIN_INCREMENTAL_BRANCH_TRADES} incremental branch trades "
                    f"across >={MIN_INCREMENTAL_BRANCH_WINDOWS} windows, survival "
                    ">=5%, concentration guard passing, and no production/backtest "
                    "split before retention."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe quant\\experiments\\"
                    "exp_20260604_018_space_defense_budget_delayed_confirmed_pool.py"
                ),
            },
            "accepted_baseline_comparison": accepted_comparison,
            "defense_budget_branch_summary": branch_summary,
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
                "retention_blocked_by_replay_only_event_profile": (
                    retention_blocked_by_replay_only_event_profile
                ),
                "promotion_requirement": (
                    "A metrics-positive result is not retained until a "
                    "point-in-time event-state replay adapter and parity tests "
                    "expose the same fields before each historical decision. "
                    "Live Space slots remain zero."
                ),
            },
            "why_not_other_changes": (
                "Skipped LLM soft-ranking because replay-safe Space semantic rows "
                "are sparse. Skipped broad ticker expansion because prior broad "
                "Space pools failed stability/concentration. Skipped sector, ETF, "
                "cost/liquidity, and price-action retunes because current playbook "
                "freezes nearby thresholds without new evidence."
            ),
            "interpretation": (
                "Metrics cleared the current-route comparator, but the result is "
                "not retained because the event ledger is not point-in-time for "
                "historical decisions."
                if metrics_gate_passed
                else (
                    "The defense-budget delayed confirmed branch did not clear "
                    "Gate 4 versus the current accepted Space route; do not "
                    "promote or retune this event-state surface without a "
                    "point-in-time event adapter or materially new forward rows."
                )
            ),
            "next_evidence_needed": (
                "Build point-in-time Space event-state replay before retesting "
                "event-state candidate routing; otherwise move to a different "
                "Space alpha surface."
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
                _repo_rel(shared.DEFAULT_SPACE_CATALYST_EVENT_LEDGER_PATH),
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
        "shared Space event-state ledger rows",
        "shared defense-budget delayed benchmark profile helper",
        "shared defense-budget same-theme winner profile helper",
    ]
    payload["gate3"].update(
        {
            "candidate_pool_changed": True,
            "minimum_core_survival_rate": space_base._round(min_survival, 4),
            "note": (
                "No core entry rule or live filter changed. The branch is evaluated "
                "as additive default-off paper, so core survival is unchanged from "
                "the baseline replay."
            ),
        }
    )
    payload["gate4"].update(
        {
            "acceptance_rule": payload["gate_questions"]["4_acceptance_standard"],
            "passed": gate4_passed,
            "metrics_gate_passed": metrics_gate_passed,
            "base_gate4_passed": base_gate4_passed,
            "accepted_baseline_improved": improves_current_accepted,
            "incremental_sample_passed": incremental_sample_passed,
            "retention_blocked_by_replay_only_event_profile": (
                retention_blocked_by_replay_only_event_profile
            ),
            "aggregate_expected_value_score_delta": aggregate[
                "expected_value_score_delta_sum"
            ],
            "aggregate_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        }
    )
    payload["rejection_reason"] = None if gate4_passed else (
        "failed_metrics_gate_or_blocked_by_replay_only_event_profile"
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
    branch = payload["defense_budget_branch_summary"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Space Defense-Budget Delayed Confirmed Pool",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: keep the accepted Space route fixed and add one paper-only `trend_long` branch for governed Space tickers whose shared event-state profile is both defense-budget delayed-benchmark positive and same-theme winner positive.",
            "",
            "## Gate Questions",
            "",
            f"- alpha_hypothesis: {payload['gate_questions']['1_alpha_hypothesis']}",
            f"- single_causal_variable: `{payload['gate_questions']['3_single_causal_variable']}`",
            f"- reproducibility: `{payload['gate_questions']['5_reproducibility']}`",
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
            f"- profile tickers: `{', '.join(branch['profile_tickers'])}`",
            f"- incremental branch trades: `{branch['incremental_trade_count']}`",
            f"- incremental branch windows: `{', '.join(branch['incremental_windows'])}`",
            f"- incremental branch PnL: `${branch['incremental_total_pnl']}`",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "Replay-only and default-off paper only. The current event-state ledger is auditable, but this runner does not promote the branch because historical decisions need a point-in-time event-state adapter before retention. No live orders, ranking, sizing, exits, watchlists, or Space slots changed.",
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
            "mechanism_family": "production_visible_default_off_space_event_candidate_pool_alpha",
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
                    "defense_budget_branch_summary": payload[
                        "defense_budget_branch_summary"
                    ],
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
