"""exp-20260603-019: Space selected sector-residual paper support.

This alpha search keeps the accepted default-off Space route fixed through the
shared cost/liquidity support helper. It changes one causal variable: already
selected Space paper candidates receive a modest additional paper-notional
support when signal-date 20-day return is at least the public-sector median.

Core entries, ranking, sizing, exits, heat, LLM/news replay, watchlists, and
live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

import exp_20260602_025_space_cost_liquidity_shared_helper as accepted_shared


EXPERIMENT_ID = "exp-20260603-019"
STEM = "exp_20260603_019_space_sector_residual_support"
TRIAL_FAMILY = "governed_space_selected_sector_residual_paper_support"
CHANGED_VARIABLE = "space_selected_sector_residual_paper_support_v1"
RULE_VERSION = "space_selected_sector_residual_support_v1"

ACCEPTED_BASELINE_EXPERIMENT_ID = "exp-20260602-025"
BASE_NOTIONAL_USD = 10_000.0
SECTOR_RESIDUAL_SUPPORT_SCALAR = 1.05
SECTOR_RESIDUAL_LOOKBACK_DAYS = 20
SECTOR_RESIDUAL_MIN_EXCESS = 0.0
SECTOR_RESIDUAL_MIN_MEMBER_RETURNS = 3
MIN_SUPPORTED_TRADES = 3
MIN_SUPPORTED_WINDOWS = 2

source = accepted_shared.source
space_base = source.space_base
REPO_ROOT = source.REPO_ROOT
WINDOWS = source.WINDOWS
TARGET_TICKERS = source.TARGET_TICKERS
TARGET_SECTOR_MAP = source.TARGET_SECTOR_MAP

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
SECTOR_MAP_JSON = REPO_ROOT / "data" / "reference" / "broad_market_sector_map.json"
ACCEPTED_BASELINE_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / ACCEPTED_BASELINE_EXPERIMENT_ID
    / "exp_20260602_025_space_cost_liquidity_shared_helper.json"
)


def _repo_rel(path: Path | str) -> str:
    return space_base._repo_rel(path)


def _load_sector_entries() -> dict[str, dict[str, Any]]:
    if not SECTOR_MAP_JSON.exists():
        return {}
    payload = json.loads(SECTOR_MAP_JSON.read_text(encoding="utf-8"))
    entries = payload.get("entries") or {}
    return entries if isinstance(entries, dict) else {}


def _sector_for_ticker(ticker: str, entries: dict[str, dict[str, Any]]) -> str | None:
    norm = str(ticker or "").upper()
    entry = entries.get(norm) or {}
    if entry.get("status") == "ok" and entry.get("sector"):
        return str(entry["sector"])
    fallback = TARGET_SECTOR_MAP.get(norm)
    return str(fallback) if fallback and fallback != "Unknown" else None


def _return_over_lookback(
    snapshot_map: dict[str, list[dict[str, Any]]],
    ticker: str,
    signal_day: str | None,
) -> float | None:
    if not signal_day:
        return None
    return source.accepted._return_over_lookback(
        snapshot_map,
        str(ticker or "").upper(),
        signal_day,
        SECTOR_RESIDUAL_LOOKBACK_DAYS,
    )


def _sector_residual_support_state(
    snapshot_map: dict[str, list[dict[str, Any]]],
    sector_entries: dict[str, dict[str, Any]],
    trade: dict[str, Any],
    market_state: dict[str, Any],
) -> dict[str, Any]:
    ticker = str(trade.get("ticker") or "").upper()
    signal_day = market_state.get("signal_day")
    sector = _sector_for_ticker(ticker, sector_entries)
    ticker_return = _return_over_lookback(snapshot_map, ticker, signal_day)
    sector_returns: list[float] = []
    if sector:
        for candidate_ticker in snapshot_map:
            candidate_sector = _sector_for_ticker(candidate_ticker, sector_entries)
            if candidate_sector != sector:
                continue
            candidate_return = _return_over_lookback(
                snapshot_map,
                candidate_ticker,
                signal_day,
            )
            if candidate_return is not None:
                sector_returns.append(candidate_return)
    median_return = median(sector_returns) if sector_returns else None
    excess = (
        ticker_return - median_return
        if ticker_return is not None and median_return is not None
        else None
    )
    selected = bool(market_state.get("passed"))
    supported = (
        selected
        and sector is not None
        and ticker_return is not None
        and median_return is not None
        and len(sector_returns) >= SECTOR_RESIDUAL_MIN_MEMBER_RETURNS
        and excess is not None
        and excess >= SECTOR_RESIDUAL_MIN_EXCESS
    )
    if supported:
        reason = "selected_sector_relative_leader"
    elif not selected:
        reason = "not_selected_space_paper_candidate"
    elif sector is None:
        reason = "missing_sector"
    elif ticker_return is None:
        reason = "missing_ticker_return"
    elif len(sector_returns) < SECTOR_RESIDUAL_MIN_MEMBER_RETURNS:
        reason = "sector_sample_too_small"
    elif excess is not None and excess < SECTOR_RESIDUAL_MIN_EXCESS:
        reason = "sector_residual_below_floor"
    else:
        reason = "sector_residual_not_supported"
    return {
        "rule_version": RULE_VERSION,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
        "support_bucket": supported,
        "support_reason": reason,
        "sector": sector,
        "sector_map_path": _repo_rel(SECTOR_MAP_JSON),
        "lookback_days": SECTOR_RESIDUAL_LOOKBACK_DAYS,
        "min_excess_vs_sector_median": SECTOR_RESIDUAL_MIN_EXCESS,
        "min_member_returns": SECTOR_RESIDUAL_MIN_MEMBER_RETURNS,
        "signal_day": signal_day,
        "ticker_return_20d": space_base._round(ticker_return, 6),
        "sector_median_return_20d": space_base._round(median_return, 6),
        "excess_vs_sector_median_20d": space_base._round(excess, 6),
        "sector_member_return_count": len(sector_returns),
        "support_scalar": SECTOR_RESIDUAL_SUPPORT_SCALAR if supported else 1.0,
        "uses_free_ohlcv_only": True,
        "uses_public_sector_cache": True,
        "trade_enabled": False,
        "alters_orders": False,
    }


def _strategy_with_sector_residual_support(
    snapshot: str,
    trades: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    snapshot_map = source.accepted._load_snapshot(snapshot)
    sector_entries = _load_sector_entries()
    base_states = source._strategy_high_close_thrust_with_cost_liquidity_support(
        snapshot,
        trades,
    )
    out: dict[str, dict[str, Any]] = {}
    for trade in trades:
        key = f"{trade.get('entry_date')}|{trade.get('ticker')}|{trade.get('exit_date')}"
        state = dict(base_states.get(key) or {})
        state["space_sector_residual_support"] = _sector_residual_support_state(
            snapshot_map,
            sector_entries,
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
    sector_support = market_state.get("space_sector_residual_support") or {}
    pre_sector_notional = float(
        cost_liquidity.get("supported_notional_usd") or BASE_NOTIONAL_USD
    )
    sector_scalar = float(sector_support.get("support_scalar") or 1.0)
    notional = round(pre_sector_notional * sector_scalar, 2)
    return {
        **trade,
        "core_sized_pnl": space_base._round(trade.get("pnl"), 2),
        "core_sized_shares": trade.get("shares"),
        "base_paper_notional_usd": BASE_NOTIONAL_USD,
        "pre_sector_residual_paper_notional_usd": pre_sector_notional,
        "paper_notional_usd": notional,
        "space_cost_liquidity_support": cost_liquidity,
        "space_sector_residual_support": sector_support,
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
    return {
        "baseline_experiment_id": ACCEPTED_BASELINE_EXPERIMENT_ID,
        "baseline_artifact": _repo_rel(ACCEPTED_BASELINE_JSON),
        "accepted_after_aggregate": accepted_aggregate,
        "current_after_aggregate": current_aggregate,
        "aggregate_expected_value_score_delta": space_base._round(
            current_aggregate["expected_value_score_sum"]
            - accepted_aggregate["expected_value_score_sum"],
            4,
        ),
        "aggregate_total_pnl_delta": space_base._round(
            current_aggregate["total_pnl_sum"] - accepted_aggregate["total_pnl_sum"],
            2,
        ),
        "windows_ev_regressed": windows_ev_regressed,
        "windows_pnl_regressed": windows_pnl_regressed,
        "by_window": by_window,
    }


def _support_trade_summary(payload: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for label, trades in payload.get("target_trades_by_window", {}).items():
        for trade in trades:
            support = trade.get("space_sector_residual_support") or {}
            if support.get("support_bucket"):
                rows.append({**trade, "window": label})
    return {
        "trade_count": len(rows),
        "windows": sorted({row["window"] for row in rows}),
        "incremental_notional_usd": space_base._round(
            sum(
                float(row.get("paper_notional_usd") or 0.0)
                - float(row.get("pre_sector_residual_paper_notional_usd") or 0.0)
                for row in rows
            ),
            2,
        ),
        "incremental_pnl": space_base._round(
            sum(
                float(row.get("pnl_pct_net") or 0.0)
                * (
                    float(row.get("paper_notional_usd") or 0.0)
                    - float(row.get("pre_sector_residual_paper_notional_usd") or 0.0)
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
    space_base._market_confirmation = _strategy_with_sector_residual_support
    space_base._fixed_notional_trade = _supported_notional_trade


def _customize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    accepted_comparison = _accepted_baseline_comparison(payload)
    support_summary = _support_trade_summary(payload)
    base_gate4_passed = bool(payload["gate4"]["passed"])
    improves_current_accepted = (
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
        and improves_current_accepted
        and support_sample_passed
    )
    decision = (
        "positive_replay_lead_requires_shared_space_sector_residual_helper"
        if gate4_passed
        else "rejected_space_sector_residual_support"
    )
    aggregate = payload["delta_metrics"]["aggregate"]
    before_metrics = payload["before_metrics"]
    min_survival = min(
        float(row.get("survival_rate") or 0.0) for row in before_metrics.values()
    )
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    predicted_success_probability = 0.24
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
            "prior_trial_count": 0,
            "nearby_prior_experiments": [
                "exp-20260531-022",
                "exp-20260602-024",
                "exp-20260602-025",
                "exp-20260602-010",
                "exp-20260603-004",
            ],
            "multiple_testing_risk_bucket": "minimal",
            "new_evidence_type": "new_production_visible_sector_relative_strength_field",
            "hypothesis": (
                "Already selected default-off Space paper candidates may deserve "
                "modest paper support when their signal-date 20-day return is at "
                "least the public-sector median, indicating sector-relative "
                "leadership rather than isolated space-theme beta."
            ),
            "prediction": {
                "success_probability": predicted_success_probability,
                "expected_ev_delta_vs_current_accepted": "positive_low_confidence",
                "expected_pnl_delta_vs_current_accepted": "positive_low_confidence",
                "main_failure_modes": [
                    "thin_supported_sample",
                    "window_instability",
                    "sector_residual_overfit",
                    "current_space_route_regression",
                ],
                "confidence_reason": (
                    "No nearby Space sector-residual trial found; sector-relative "
                    "support helped other paper sleeves, but Space selected rows "
                    "are thin and recent Space threshold/scalar retunes are frozen."
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
                "sector_residual_support_scalar": SECTOR_RESIDUAL_SUPPORT_SCALAR,
                "sector_residual_lookback_days": SECTOR_RESIDUAL_LOOKBACK_DAYS,
                "sector_residual_min_excess": SECTOR_RESIDUAL_MIN_EXCESS,
                "sector_residual_min_member_returns": SECTOR_RESIDUAL_MIN_MEMBER_RETURNS,
                "sector_map": _repo_rel(SECTOR_MAP_JSON),
                "accepted_baseline_experiment_id": ACCEPTED_BASELINE_EXPERIMENT_ID,
                "target_tickers": payload["parameters"]["target_tickers"],
                "target_sector_map": TARGET_SECTOR_MAP,
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
                    "capital allocation: already selected default-off Space "
                    "paper candidates may deserve 1.05x support when signal-date "
                    "20-day return is at least the public-sector median."
                ),
                "2_history_check": {
                    "exp-20260531-022": (
                        "Accepted Space ARKX>UFO breakout complement; current "
                        "Space candidate route remains fixed."
                    ),
                    "exp-20260602-024": (
                        "Positive Space cost/liquidity support replay lead."
                    ),
                    "exp-20260602-025": (
                        "Accepted shared Space cost/liquidity helper; current "
                        "Space comparator."
                    ),
                    "exp-20260602-010": (
                        "Accepted Companyfacts sector-residual support, proving "
                        "the free sector-relative field can be production-visible."
                    ),
                    "exp-20260603-004": (
                        "Accepted post-earnings sector-residual support; this "
                        "does not retune those thresholds or sleeves."
                    ),
                    "llm_soft_ranking": (
                        "Skipped because replay-safe Space semantic ranking rows "
                        "and closed replacement outcomes remain sparse."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same docs/backtesting.md Space three-window replay; positive "
                    "aggregate EV/PnL versus core; no EV/PnL-regressed windows "
                    "versus core; aggregate EV/PnL improvement versus accepted "
                    "exp-20260602-025; supported sample across >=2 windows; "
                    "drawdown drift <=0.5pp; survival >=5%; concentration guard "
                    "passes; and no production/backtest split before retention."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe quant\\experiments\\"
                    "exp_20260603_019_space_sector_residual_support.py"
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
                    "A passing replay remains a lead until a shared default-off "
                    "Space sector-residual helper and focused parity tests expose "
                    "the same metadata. Live Space slots remain zero."
                ),
            },
            "why_not_other_changes": (
                "Skipped LLM soft-ranking because replay-safe Space semantic rows "
                "remain sparse; skipped broad Space ticker expansion because prior "
                "broad pools failed stability/concentration; skipped nearby "
                "price-action, ETF, and cost/liquidity threshold retunes because "
                "the playbook says to avoid frozen-window mining."
            ),
            "interpretation": (
                "The Space sector-residual support is a positive replay lead, but "
                "it is not promoted or retained as strategy behavior until a "
                "shared production helper removes the replay-only boundary."
                if gate4_passed
                else (
                    "The Space sector-residual support did not clear Gate 4 versus "
                    "the current accepted Space route; do not promote or retune it "
                    "without forward replacement evidence or a materially new field."
                )
            ),
            "next_evidence_needed": (
                "If pursued, reserve a separate helper-promotion experiment that "
                "adds shared production metadata and parity tests; otherwise collect "
                "forward Space replacement-value rows."
                if gate4_passed
                else (
                    "Forward replacement-value outcomes or a materially new Space "
                    "event-quality/candidate-pool field; avoid sector-residual "
                    "threshold/scalar retunes on frozen windows."
                )
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
                _repo_rel(SECTOR_MAP_JSON),
            ],
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["gate2"]["runtime_fields"] = [
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
        "target OHLCV rows in all three Space replay snapshots",
        "existing signal strategy field generated before next-open paper entry",
        "signal-date OHLCV close history through the signal date",
        "public sector labels from data/reference/broad_market_sector_map.json",
    ]
    payload["gate3"].update(
        {
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": space_base._round(min_survival, 4),
            "note": (
                "No new core filter, core entry rule, or paper admission filter was "
                "added. The experiment changes only default-off paper notional for "
                "already selected Space paper candidates, so core survival is unchanged."
            ),
        }
    )
    payload["gate4"].update(
        {
            "acceptance_rule": (
                "positive aggregate EV/PnL versus core; zero EV/PnL-regressed "
                "windows versus core; aggregate EV/PnL improvement versus accepted "
                "exp-20260602-025; supported sample across >=2 windows; drawdown "
                "drift <=0.5pp; survival >=5%; concentration guard passes"
            ),
            "passed": gate4_passed,
            "base_gate4_passed": base_gate4_passed,
            "accepted_baseline_improved": improves_current_accepted,
            "supported_sample_passed": support_sample_passed,
            "aggregate_expected_value_score_delta": aggregate[
                "expected_value_score_delta_sum"
            ],
            "aggregate_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        }
    )
    payload["rejection_reason"] = None if gate4_passed else (
        "failed_core_gate_or_failed_current_accepted_baseline_comparison"
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
            f"# {EXPERIMENT_ID} Space Sector-Residual Support",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: keep the accepted Space route fixed and apply a 1.05x default-off paper-notional support only to already selected candidates whose signal-date 20-day return is at least the public-sector median.",
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
            "This runner is replay-only and does not promote a shared helper. Live Space slots remain zero, and no production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.",
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
            "mechanism_family": "default_off_paper_allocation",
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
