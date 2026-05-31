"""exp-20260531-022: Space ARKX/UFO breakout complement.

This alpha search tests one causal routing policy on top of the accepted Space
high-close intraday-thrust route. Keep the accepted trend_long route fixed, and
admit an additional default-off paper branch for breakout_long candidates only
when the signal day is high-close/thrust-confirmed and ARKX 20d momentum leads
UFO 20d momentum.

Core entries, ranking, sizing, exits, heat, LLM/news replay, watchlists, and
live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260529_020_space_trend_high_close_orderly_range_fixed_notional_sleeve as accepted


EXPERIMENT_ID = "exp-20260531-022"
STEM = "exp_20260531_022_space_arkx_ufo_breakout_complement"
TRIAL_FAMILY = (
    "governed_space_high_close_thrust_with_space_etf_relative_breakout_complement"
)
CHANGED_VARIABLE = "space_high_close_thrust_plus_arkx_ufo_breakout_branch_v1"
RULE_VERSION = "space_high_close_thrust_arkx_ufo_breakout_complement_v1"

TARGET_TICKERS = accepted.TARGET_TICKERS
TARGET_SECTOR_MAP = accepted.TARGET_SECTOR_MAP

BASE_NOTIONAL_USD = 10_000.0
TARGET_TREND_STRATEGY = "trend_long"
TARGET_BREAKOUT_STRATEGY = "breakout_long"
MIN_SIGNAL_DAY_CLOSE_LOCATION = accepted.MIN_SIGNAL_DAY_CLOSE_LOCATION
MIN_SIGNAL_DAY_OPEN_CLOSE_RETURN = accepted.MIN_SIGNAL_DAY_OPEN_CLOSE_RETURN
SPACE_QUALITY_ETF_TICKER = "ARKX"
SPACE_ATTENTION_ETF_TICKER = "UFO"
ETF_MOMENTUM_LOOKBACK_DAYS = 20
MIN_TARGET_TRADES = 6
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.45
ACCEPTED_BASELINE_EXPERIMENT_ID = "exp-20260529-020"

space_base = accepted.space_base
REPO_ROOT = accepted.REPO_ROOT
SOURCE_UNIVERSE_STATE = accepted.SOURCE_UNIVERSE_STATE
SOURCE_OHLCV_EXPERIMENT_ID = accepted.SOURCE_OHLCV_EXPERIMENT_ID
WINDOWS = accepted.WINDOWS

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / (
    f"{EXPERIMENT_ID}_space_arkx_ufo_breakout_complement.md"
)
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
ACCEPTED_BASELINE_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / ACCEPTED_BASELINE_EXPERIMENT_ID
    / "exp_20260529_020_space_trend_high_close_orderly_range_fixed_notional_sleeve.json"
)


def _repo_rel(path: Path | str) -> str:
    return space_base._repo_rel(path)


def _row_value(row: dict[str, Any], key: str) -> Any:
    return row.get(key) if key in row else row.get(key.capitalize())


def _load_snapshot(snapshot: str) -> dict[str, list[dict[str, Any]]]:
    payload = space_base.prior._load_json(REPO_ROOT / snapshot)
    return payload.get("ohlcv") or payload


def _rows_to_signal_day(
    snapshot_map: dict[str, list[dict[str, Any]]],
    ticker: str,
    signal_day: str,
) -> list[dict[str, Any]]:
    rows = [
        row
        for row in snapshot_map.get(str(ticker or "").upper(), []) or []
        if isinstance(row, dict)
        and _row_value(row, "date")
        and str(_row_value(row, "date")) <= signal_day
    ]
    return sorted(rows, key=lambda row: str(_row_value(row, "date")))


def _return_over_lookback(
    snapshot_map: dict[str, list[dict[str, Any]]],
    ticker: str,
    signal_day: str,
    lookback_days: int,
) -> float | None:
    rows = _rows_to_signal_day(snapshot_map, ticker, signal_day)
    if len(rows) <= lookback_days:
        return None
    try:
        close_now = float(_row_value(rows[-1], "close"))
        close_then = float(_row_value(rows[-1 - lookback_days], "close"))
    except (TypeError, ValueError):
        return None
    if close_then <= 0:
        return None
    return (close_now / close_then) - 1.0


def _space_etf_leadership_state(
    snapshot_map: dict[str, list[dict[str, Any]]],
    signal_day: str | None,
) -> dict[str, Any]:
    if not signal_day:
        return {
            "quality_etf": SPACE_QUALITY_ETF_TICKER,
            "attention_etf": SPACE_ATTENTION_ETF_TICKER,
            "lookback_days": ETF_MOMENTUM_LOOKBACK_DAYS,
            "quality_etf_return_20d": None,
            "attention_etf_return_20d": None,
            "quality_minus_attention_return_20d": None,
            "passed": False,
        }
    quality = _return_over_lookback(
        snapshot_map,
        SPACE_QUALITY_ETF_TICKER,
        signal_day,
        ETF_MOMENTUM_LOOKBACK_DAYS,
    )
    attention = _return_over_lookback(
        snapshot_map,
        SPACE_ATTENTION_ETF_TICKER,
        signal_day,
        ETF_MOMENTUM_LOOKBACK_DAYS,
    )
    excess = None
    if quality is not None and attention is not None:
        excess = quality - attention
    return {
        "quality_etf": SPACE_QUALITY_ETF_TICKER,
        "attention_etf": SPACE_ATTENTION_ETF_TICKER,
        "lookback_days": ETF_MOMENTUM_LOOKBACK_DAYS,
        "quality_etf_return_20d": space_base._round(quality, 6),
        "attention_etf_return_20d": space_base._round(attention, 6),
        "quality_minus_attention_return_20d": space_base._round(excess, 6),
        "passed": excess is not None and excess > 0.0,
    }


def _strategy_high_close_thrust_with_breakout_complement(
    snapshot: str,
    trades: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    snapshot_map = _load_snapshot(snapshot)
    out: dict[str, dict[str, Any]] = {}
    for trade in trades:
        key = f"{trade.get('entry_date')}|{trade.get('ticker')}|{trade.get('exit_date')}"
        ticker = str(trade.get("ticker") or "").upper()
        entry_date = str(trade.get("entry_date") or "")
        strategy = str(trade.get("strategy") or "")
        state = accepted._signal_day_state(
            accepted._signal_day_row(snapshot_map, ticker, entry_date)
        )
        signal_day = state["signal_day"]
        close_location = state["close_location"]
        open_close_return = state["open_close_return"]
        high_close_passed = (
            close_location is not None
            and close_location >= MIN_SIGNAL_DAY_CLOSE_LOCATION
        )
        intraday_thrust_passed = (
            open_close_return is not None
            and open_close_return >= MIN_SIGNAL_DAY_OPEN_CLOSE_RETURN
        )
        trend_branch_passed = (
            strategy == TARGET_TREND_STRATEGY
            and high_close_passed
            and intraday_thrust_passed
        )
        etf_state = _space_etf_leadership_state(snapshot_map, signal_day)
        breakout_complement_passed = (
            strategy == TARGET_BREAKOUT_STRATEGY
            and high_close_passed
            and intraday_thrust_passed
            and bool(etf_state["passed"])
        )
        out[key] = {
            "rule_version": RULE_VERSION,
            "known_at": "after_signal_day_close_before_next_open_paper_entry",
            "uses_existing_signal_strategy_field": True,
            "uses_free_ohlcv_only": True,
            "strategy": strategy,
            "accepted_trend_strategy": TARGET_TREND_STRATEGY,
            "breakout_complement_strategy": TARGET_BREAKOUT_STRATEGY,
            "signal_day": signal_day,
            "signal_day_close_location_value": close_location,
            "min_signal_day_close_location": MIN_SIGNAL_DAY_CLOSE_LOCATION,
            "signal_day_open_close_return_pct": open_close_return,
            "min_signal_day_open_close_return_pct": (
                MIN_SIGNAL_DAY_OPEN_CLOSE_RETURN
            ),
            "signal_day_range_pct": state["range_pct"],
            "high_close_passed": high_close_passed,
            "intraday_thrust_passed": intraday_thrust_passed,
            "trend_branch_passed": trend_branch_passed,
            "space_etf_relative_leadership": etf_state,
            "breakout_complement_passed": breakout_complement_passed,
            "passed": trend_branch_passed or breakout_complement_passed,
        }
    return out


def _configure_space_base() -> None:
    space_base.EXPERIMENT_ID = EXPERIMENT_ID
    space_base.STEM = STEM
    space_base.TRIAL_FAMILY = TRIAL_FAMILY
    space_base.CHANGED_VARIABLE = CHANGED_VARIABLE
    space_base.TARGET_TICKERS = TARGET_TICKERS
    space_base.TARGET_SECTOR_MAP = TARGET_SECTOR_MAP
    space_base.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    space_base.THEME_BENCHMARK_TICKER = "SPY"
    space_base.BROAD_BENCHMARK_TICKER = "SPY"
    space_base.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    space_base.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    space_base.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    space_base.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    space_base.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    space_base.OUT_DIR = OUT_DIR
    space_base.OUT_JSON = OUT_JSON
    space_base.LOG_JSON = LOG_JSON
    space_base.TICKET_JSON = TICKET_JSON
    space_base.ARTIFACT_MD = ARTIFACT_MD
    space_base.EXPERIMENT_LOG = EXPERIMENT_LOG
    space_base._target_universe = accepted.high_close._target_universe
    space_base._market_confirmation = (
        _strategy_high_close_thrust_with_breakout_complement
    )


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


def _breakout_complement_trade_summary(payload: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for label, trades in payload.get("target_trades_by_window", {}).items():
        for trade in trades:
            confirmation = trade.get("market_confirmation") or {}
            if confirmation.get("breakout_complement_passed"):
                rows.append({**trade, "window": label})
    return {
        "trade_count": len(rows),
        "windows": sorted({row["window"] for row in rows}),
        "total_pnl": space_base._round(
            sum(float(row.get("pnl") or 0.0) for row in rows),
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


def _customize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    accepted_comparison = _accepted_baseline_comparison(payload)
    breakout_summary = _breakout_complement_trade_summary(payload)
    base_gate4_passed = bool(payload["gate4"]["passed"])
    improves_current_accepted = (
        accepted_comparison["aggregate_expected_value_score_delta"] > 0
        and accepted_comparison["aggregate_total_pnl_delta"] > 0
        and accepted_comparison["windows_ev_regressed"] == 0
        and accepted_comparison["windows_pnl_regressed"] == 0
    )
    incremental_branch_observed = breakout_summary["trade_count"] > 0
    gate4_passed = (
        base_gate4_passed
        and improves_current_accepted
        and incremental_branch_observed
    )
    decision = (
        "accepted_default_off_space_arkx_ufo_breakout_complement"
        if gate4_passed
        else "rejected_space_arkx_ufo_breakout_complement"
    )
    aggregate = payload["delta_metrics"]["aggregate"]
    before_metrics = payload["before_metrics"]
    min_survival = min(
        float(row.get("survival_rate") or 0.0) for row in before_metrics.values()
    )
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    predicted_success_probability = 0.28
    actual_success = bool(gate4_passed)
    brier_score = (
        (1.0 if actual_success else 0.0) - predicted_success_probability
    ) ** 2
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
            "prior_trial_count": 1,
            "nearby_prior_experiments": [
                "exp-20260525-006",
                "exp-20260526-020",
                "exp-20260527-904",
                "exp-20260528-026",
                "exp-20260529-020",
            ],
            "multiple_testing_risk_bucket": "high",
            "new_evidence_type": "production_visible_space_etf_relative_leadership_field",
            "hypothesis": (
                "Accepted Space trend high-close intraday-thrust candidates may "
                "be complemented by high-close breakout candidates only when "
                "ARKX 20d momentum leads UFO 20d momentum, indicating "
                "institutional space ETF breadth over speculative attention."
            ),
            "prediction": {
                "success_probability": predicted_success_probability,
                "expected_ev_delta_vs_current_accepted": "positive_low_confidence",
                "expected_pnl_delta_vs_current_accepted": "positive_low_confidence",
                "main_failure_modes": [
                    "thin_incremental_sample",
                    "breakout_loss_leakage",
                    "arkx_ufo_overfit",
                    "window_instability",
                ],
                "confidence_reason": (
                    "Prior Space broad ETF and full-pool experiments often failed "
                    "stability, but the accepted high-close/thrust route created "
                    "a narrow production-visible scaffold for one breakout "
                    "complement test."
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
                "surprise_level": "medium" if actual_success else "low",
                "actual_ev_delta_vs_current_accepted": (
                    accepted_comparison["aggregate_expected_value_score_delta"]
                ),
                "actual_pnl_delta_vs_current_accepted": (
                    accepted_comparison["aggregate_total_pnl_delta"]
                ),
            },
            "parameters": {
                "base_notional_usd": BASE_NOTIONAL_USD,
                "target_tickers": payload["parameters"]["target_tickers"],
                "target_sector_map": TARGET_SECTOR_MAP,
                "accepted_trend_strategy": TARGET_TREND_STRATEGY,
                "breakout_complement_strategy": TARGET_BREAKOUT_STRATEGY,
                "min_signal_day_close_location": MIN_SIGNAL_DAY_CLOSE_LOCATION,
                "min_signal_day_open_close_return_pct": (
                    MIN_SIGNAL_DAY_OPEN_CLOSE_RETURN
                ),
                "space_quality_etf_ticker": SPACE_QUALITY_ETF_TICKER,
                "space_attention_etf_ticker": SPACE_ATTENTION_ETF_TICKER,
                "etf_momentum_lookback_days": ETF_MOMENTUM_LOOKBACK_DAYS,
                "accepted_baseline_experiment_id": ACCEPTED_BASELINE_EXPERIMENT_ID,
                "rule_version": RULE_VERSION,
                "source_universe_state": _repo_rel(SOURCE_UNIVERSE_STATE),
                "source_ohlcv_experiment_id": SOURCE_OHLCV_EXPERIMENT_ID,
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
                    "paper base notional",
                    "accepted trend high-close intraday-thrust branch",
                ],
                "anti_js": "No JavaScript was used.",
            },
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "candidate_pool/risk allocation: keep the accepted Space "
                    "trend high-close intraday-thrust route fixed and add only a "
                    "breakout_long complement when ARKX 20d return exceeds UFO "
                    "20d return."
                ),
                "2_history_check": {
                    "exp-20260525-006": (
                        "Space comm ARKX-confirmed sleeve failed stability and "
                        "concentration; this does not use a broad ARKX gate or "
                        "trade only communication names."
                    ),
                    "exp-20260526-020": (
                        "Full governed Space volume-breadth sleeve was rejected "
                        "after late_strong and concentration failures; this avoids "
                        "a full-pool breadth gate."
                    ),
                    "exp-20260527-904": (
                        "Trend-only Space sleeve failed old_thin and drawdown; "
                        "this keeps the accepted trend branch and only tests a "
                        "narrow breakout complement."
                    ),
                    "exp-20260528-026": (
                        "Accepted high-close trend route improved aggregate EV by "
                        "+0.7505."
                    ),
                    "exp-20260529-020": (
                        "Accepted high-close intraday-thrust route improved the "
                        "high-close baseline by +0.0282 EV and is the current "
                        "baseline for this experiment."
                    ),
                    "llm_soft_ranking": (
                        "Skipped because replay-safe Space semantic rows and "
                        "closed same-theme replacement outcomes remain sparse."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same three docs/backtesting.md Space observation windows; "
                    "positive aggregate EV/PnL versus core; no EV/PnL-regressed "
                    "windows versus core; improvement versus accepted "
                    "exp-20260529-020; >=6 target paper trades across 3 windows; "
                    "drawdown drift <=0.5pp; survival >=5%; target concentration "
                    "inside guardrails; and no production/backtest split."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe quant\\experiments\\"
                    "exp_20260531_022_space_arkx_ufo_breakout_complement.py"
                ),
            },
            "accepted_baseline_comparison": accepted_comparison,
            "breakout_complement_trade_summary": breakout_summary,
            "production_impact": {
                "shared_policy_changed": gate4_passed,
                "backtester_adapter_changed": gate4_passed,
                "run_adapter_changed": gate4_passed,
                "replay_only": True,
                "parity_test_added": gate4_passed,
                "default_off_paper_only": True,
                "metadata_only": True,
                "production_fields": [
                    "daily_close_location",
                    "signal_day_ticker_open_close_return_pct",
                    "ARKX momentum_20d_pct",
                    "UFO momentum_20d_pct",
                ],
                "production_bucket": "space_arkx_ufo_breakout_complement_bucket",
                "production_watchlist_changed": False,
                "production_orders_changed": False,
                "production_ranking_changed": False,
                "production_sizing_changed": False,
                "production_exits_changed": False,
                "trade_enabled": False,
            },
            "why_not_other_changes": (
                "Skipped LLM soft-ranking because replay-safe Space semantic rows "
                "remain sparse; skipped broad ticker expansion because recent "
                "Space pools failed stability or concentration; skipped another "
                "notional scalar because this tests admission quality. The only "
                "new field is production-visible ARKX-versus-UFO relative 20d "
                "momentum on high-close/thrust breakout candidates."
            ),
            "interpretation": (
                "The Space ARKX/UFO breakout complement cleared Gate 4 as a "
                "default-off observation-sleeve increment on top of the accepted "
                "trend high-close intraday-thrust route. It is not a live capital "
                "change; production should expose the same metadata with "
                "trade_enabled false."
                if gate4_passed
                else (
                    "The Space ARKX/UFO breakout complement did not clear Gate 4 "
                    "versus the current accepted Space route; do not promote it "
                    "without forward replacement evidence."
                )
            ),
            "next_evidence_needed": (
                "Expose the ARKX/UFO breakout-complement bucket in the shared "
                "default-off Space observation helper and collect forward "
                "replacement-value rows before any live/default behavior changes."
                if gate4_passed
                else (
                    "Forward replacement-value outcomes or a materially new Space "
                    "event-quality field; avoid nearby ETF threshold retunes on "
                    "these frozen windows."
                )
            ),
            "related_files": [
                _repo_rel(Path(__file__)),
                _repo_rel(OUT_JSON),
                _repo_rel(LOG_JSON),
                _repo_rel(TICKET_JSON),
                _repo_rel(ARTIFACT_MD),
                _repo_rel(CARD_MD),
                _repo_rel(EXPERIMENT_LOG),
                _repo_rel(REGISTRY_JSON),
                "quant/feature_layer.py",
                "quant/space_catalyst_sleeve.py",
                "quant/test_space_catalyst_sleeve.py",
            ],
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["gate2"]["runtime_fields"] = [
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
        "universe_state records.theme/theme_segment/status/liquidity_tier/history_class",
        "target OHLCV rows in all three exp-20260519-029 snapshots",
        "ARKX and UFO OHLCV rows in all three exp-20260519-029 snapshots",
        "existing signal strategy field generated before next-open paper entry",
        "signal-day OHLCV open/high/low/close from previous market date before next-open paper entry",
        "20-trading-day ARKX and UFO return computed from signal-day-close-known OHLCV",
        "risk_engine.SECTOR_MAP target tickers patched from TARGET_SECTOR_MAP in replay",
    ]
    payload["gate3"].update(
        {
            "candidate_pool_changed": True,
            "minimum_core_survival_rate": space_base._round(min_survival, 4),
            "note": (
                "No new core filter or core entry rule was added. The target cohort "
                "is evaluated as additive default-off paper, so core survival is "
                "unchanged from the baseline replay."
            ),
        }
    )
    payload["gate4"].update(
        {
            "acceptance_rule": (
                "positive aggregate EV/PnL versus core; zero EV/PnL-regressed "
                "windows versus core; aggregate EV/PnL improvement versus "
                "accepted exp-20260529-020; >=6 target trades across 3 windows; "
                "drawdown drift <=0.5pp; survival >=5%; concentration guard passes"
            ),
            "passed": gate4_passed,
            "base_gate4_passed": base_gate4_passed,
            "accepted_baseline_improved": improves_current_accepted,
            "incremental_branch_observed": incremental_branch_observed,
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
    breakout = payload["breakout_complement_trade_summary"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Space ARKX/UFO Breakout Complement",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: keep the accepted Space trend high-close intraday-thrust branch fixed, and add a breakout_long high-close/thrust complement only when ARKX 20d return is greater than UFO 20d return.",
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
            f"- breakout complement trades: `{breakout['trade_count']}`",
            f"- breakout complement PnL: `${breakout['total_pnl']}`",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "If retained, metadata is surfaced through the shared default-off Space observation slot. Live Space slots remain zero, and no production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.",
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
            "mechanism_family": (
                "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
            ),
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
                "artifact": _repo_rel(ARTIFACT_MD),
                "decision": payload["decision"],
                "expected_value_score_delta": payload["expected_value_score_delta"],
                "json": _repo_rel(OUT_JSON),
                "summary": payload["interpretation"],
                "total_pnl_delta": payload["total_pnl_delta"],
            },
        }
    )
    space_base._write_json(TICKET_JSON, ticket)

    if not REGISTRY_JSON.exists():
        return
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


def _persist(payload: dict[str, Any]) -> None:
    report = _build_report(payload)
    space_base._write_json(OUT_JSON, payload)
    space_base._write_json(LOG_JSON, payload)
    space_base._write_text(ARTIFACT_MD, report)
    space_base._write_text(CARD_MD, report)
    space_base._upsert_jsonl(EXPERIMENT_LOG, payload)
    _update_ticket_and_registry(payload)


def main() -> int:
    _configure_space_base()
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
                    "breakout_complement_trade_summary": payload[
                        "breakout_complement_trade_summary"
                    ],
                    "gate4": payload["gate4"],
                    "target_trade_summary": payload["target_trade_summary"],
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
