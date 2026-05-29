"""exp-20260529-020: Space high-close intraday-thrust paper sleeve.

This alpha search tests one causal routing policy on top of the accepted
Space high-close trend idea: admit governed full-history Space observation
candidates into an additive, default-off, fixed-notional paper sleeve only
when the existing production signal engine classified the discovery as
``trend_long``, signal-day close-location is at least 0.84, and signal-day
open-to-close return is at least 4%.

Core entries, ranking, sizing, exits, heat, LLM/news replay, watchlists, and
live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260528_026_space_trend_high_close_fixed_notional_sleeve as high_close


EXPERIMENT_ID = "exp-20260529-020"
STEM = "exp_20260529_020_space_trend_high_close_orderly_range_fixed_notional_sleeve"
TRIAL_FAMILY = (
    "governed_space_trend_high_close_intraday_thrust_fixed_notional_paper_sleeve"
)
CHANGED_VARIABLE = (
    "space_governed_trend_high_close_intraday_thrust_fixed_notional_"
    "paper_sleeve_routing_v1"
)
RULE_VERSION = "space_trend_high_close_intraday_thrust_paper_sleeve_v1"

TARGET_TICKERS = high_close.TARGET_TICKERS
TARGET_SECTOR_MAP = high_close.TARGET_SECTOR_MAP

BASE_NOTIONAL_USD = 10_000.0
TARGET_STRATEGY = "trend_long"
MIN_SIGNAL_DAY_CLOSE_LOCATION = 0.84
MIN_SIGNAL_DAY_OPEN_CLOSE_RETURN = 0.04
MIN_TARGET_TRADES = 5
MIN_TARGET_WINDOWS = 2
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.45
ACCEPTED_HIGH_CLOSE_EXPERIMENT_ID = "exp-20260528-026"

space_base = high_close.space_base
REPO_ROOT = high_close.REPO_ROOT
SOURCE_UNIVERSE_STATE = high_close.SOURCE_UNIVERSE_STATE
SOURCE_OHLCV_EXPERIMENT_ID = high_close.SOURCE_OHLCV_EXPERIMENT_ID
WINDOWS = high_close.WINDOWS

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOCS_TICKET_JSON = (
    REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
)
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / (
    f"{EXPERIMENT_ID}_space_trend_high_close_intraday_thrust_fixed_notional_sleeve.md"
)
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
ACCEPTED_HIGH_CLOSE_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / ACCEPTED_HIGH_CLOSE_EXPERIMENT_ID
    / "exp_20260528_026_space_trend_high_close_fixed_notional_sleeve.json"
)


def _repo_rel(path: Path | str) -> str:
    return space_base._repo_rel(path)


def _row_value(row: dict[str, Any], key: str) -> Any:
    return row.get(key) if key in row else row.get(key.capitalize())


def _load_snapshot(snapshot: str) -> dict[str, list[dict[str, Any]]]:
    payload = space_base.prior._load_json(REPO_ROOT / snapshot)
    return payload.get("ohlcv") or payload


def _signal_day_row(
    snapshot_map: dict[str, list[dict[str, Any]]],
    ticker: str,
    entry_date: str,
) -> dict[str, Any] | None:
    rows = [
        row
        for row in snapshot_map.get(str(ticker or "").upper(), []) or []
        if isinstance(row, dict)
        and _row_value(row, "date")
        and str(_row_value(row, "date")) < entry_date
    ]
    if not rows:
        return None
    return max(rows, key=lambda row: str(_row_value(row, "date")))


def _signal_day_state(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {
            "signal_day": None,
            "close_location": None,
            "open_close_return": None,
            "range_pct": None,
        }
    try:
        open_ = float(_row_value(row, "open"))
        high = float(_row_value(row, "high"))
        low = float(_row_value(row, "low"))
        close = float(_row_value(row, "close"))
    except (TypeError, ValueError):
        return {
            "signal_day": str(_row_value(row, "date")) if row else None,
            "close_location": None,
            "open_close_return": None,
            "range_pct": None,
        }
    day_range = high - low
    close_location = None
    if day_range > 0:
        close_location = max(0.0, min(1.0, (close - low) / day_range))
    return {
        "signal_day": str(_row_value(row, "date")),
        "close_location": space_base._round(close_location, 6),
        "open_close_return": (
            space_base._round((close - open_) / open_, 6) if open_ > 0 else None
        ),
        "range_pct": space_base._round(day_range / close, 6) if close > 0 else None,
    }


def _strategy_high_close_intraday_thrust_confirmation(
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
        state = _signal_day_state(_signal_day_row(snapshot_map, ticker, entry_date))
        close_location = state["close_location"]
        open_close_return = state["open_close_return"]
        strategy_passed = strategy == TARGET_STRATEGY
        high_close_passed = (
            close_location is not None
            and close_location >= MIN_SIGNAL_DAY_CLOSE_LOCATION
        )
        intraday_thrust_passed = (
            open_close_return is not None
            and open_close_return >= MIN_SIGNAL_DAY_OPEN_CLOSE_RETURN
        )
        out[key] = {
            "rule_version": RULE_VERSION,
            "known_at": "after_signal_day_close_before_next_open_paper_entry",
            "uses_existing_signal_strategy_field": True,
            "uses_free_ohlcv_only": True,
            "strategy": strategy,
            "target_strategy": TARGET_STRATEGY,
            "signal_day": state["signal_day"],
            "signal_day_close_location_value": close_location,
            "min_signal_day_close_location": MIN_SIGNAL_DAY_CLOSE_LOCATION,
            "signal_day_open_close_return_pct": open_close_return,
            "min_signal_day_open_close_return_pct": (
                MIN_SIGNAL_DAY_OPEN_CLOSE_RETURN
            ),
            "signal_day_range_pct": state["range_pct"],
            "strategy_passed": strategy_passed,
            "high_close_passed": high_close_passed,
            "intraday_thrust_passed": intraday_thrust_passed,
            "passed": (
                strategy_passed and high_close_passed and intraday_thrust_passed
            ),
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
    space_base._target_universe = high_close._target_universe
    space_base._market_confirmation = (
        _strategy_high_close_intraday_thrust_confirmation
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


def _accepted_high_close_comparison(payload: dict[str, Any]) -> dict[str, Any]:
    accepted = json.loads(ACCEPTED_HIGH_CLOSE_JSON.read_text(encoding="utf-8"))
    accepted_after = accepted["after_metrics"]
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
        "baseline_experiment_id": ACCEPTED_HIGH_CLOSE_EXPERIMENT_ID,
        "baseline_artifact": _repo_rel(ACCEPTED_HIGH_CLOSE_JSON),
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


def _customize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload = high_close._customize_payload(payload)
    accepted_comparison = _accepted_high_close_comparison(payload)
    base_gate4_passed = bool(payload["gate4"]["passed"])
    improves_accepted_high_close = (
        accepted_comparison["aggregate_expected_value_score_delta"] > 0
        and accepted_comparison["aggregate_total_pnl_delta"] > 0
        and accepted_comparison["windows_ev_regressed"] == 0
        and accepted_comparison["windows_pnl_regressed"] == 0
    )
    gate4_passed = base_gate4_passed and improves_accepted_high_close
    decision = (
        "accepted_default_off_space_trend_high_close_intraday_thrust_sleeve"
        if gate4_passed
        else "rejected_space_trend_high_close_intraday_thrust_sleeve"
    )
    aggregate = payload["delta_metrics"]["aggregate"]
    before_metrics = payload["before_metrics"]
    min_survival = min(
        float(row.get("survival_rate") or 0.0) for row in before_metrics.values()
    )
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": timestamp,
            "lane": "alpha_search",
            "registry_lane": "alpha_discovery",
            "status": decision,
            "decision": decision,
            "change_type": "candidate_pool_paper_sleeve_shadow",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": EXPERIMENT_ID,
            "prior_trial_count": 1,
            "nearby_prior_experiments": [
                "exp-20260526-020",
                "exp-20260527-904",
                "exp-20260528-026",
                "exp-20260529-004",
            ],
            "multiple_testing_risk_bucket": "high",
            "new_evidence_type": (
                "orthogonal_existing_production_ohlcv_intraday_thrust_field_"
                "on_accepted_space_high_close_trend_pool"
            ),
            "hypothesis": (
                "Governed full-history Space observation candidates may have "
                "cleaner additive fixed-notional paper replacement value when "
                "the accepted trend_long high-close signal also posts at least "
                "a 4% signal-day open-to-close gain. This tests decisive "
                "intraday demand using an existing production-visible OHLCV "
                "field, without adding noisy tickers, ETF/breadth gates, LLM "
                "soft-ranking, scalars, or live Space slots."
            ),
            "parameters": {
                "base_notional_usd": BASE_NOTIONAL_USD,
                "target_tickers": payload["parameters"]["target_tickers"],
                "target_sector_map": TARGET_SECTOR_MAP,
                "target_strategy": TARGET_STRATEGY,
                "min_signal_day_close_location": MIN_SIGNAL_DAY_CLOSE_LOCATION,
                "min_signal_day_open_close_return_pct": (
                    MIN_SIGNAL_DAY_OPEN_CLOSE_RETURN
                ),
                "accepted_high_close_baseline_experiment_id": (
                    ACCEPTED_HIGH_CLOSE_EXPERIMENT_ID
                ),
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
                    "accepted high-close close-location threshold",
                ],
                "anti_js": "No JavaScript was used.",
            },
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "entry/candidate_pool/risk allocation: accepted governed "
                    "Space high-close trend candidates may have stronger "
                    "replacement value when the signal-day open-to-close gain "
                    "is at least 4%."
                ),
                "2_history_check": {
                    "exp-20260526-020": (
                        "Full governed Space volume-breadth sleeve was rejected "
                        "after late_strong and concentration failures; this avoids "
                        "breadth gates."
                    ),
                    "exp-20260527-904": (
                        "Trend-only Space sleeve failed old_thin and drawdown; "
                        "this keeps the accepted high-close absorption field."
                    ),
                    "exp-20260528-026": (
                        "Accepted high-close trend route improved aggregate EV by "
                        "+0.7505; this tests one orthogonal existing OHLCV field "
                        "against that accepted baseline."
                    ),
                    "exp-20260529-004": (
                        "Accepted VBB cost/liquidity support showed that execution "
                        "quality fields can matter, but this does not reuse VBB "
                        "thresholds or trade a VBB sleeve."
                    ),
                    "llm_soft_ranking": (
                        "Skipped because replay-safe Space semantic rows and closed "
                        "same-theme replacement outcomes remain sparse."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same three docs/backtesting.md Space observation windows, "
                    "positive aggregate EV/PnL versus core, no EV/PnL-regressed "
                    "windows versus core, improvement versus accepted "
                    "exp-20260528-026 high-close baseline, >=5 target paper trades "
                    "across >=2 windows, drawdown drift <=0.5pp, survival >=5%, "
                    "and target concentration inside guardrails."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe quant\\experiments\\"
                    "exp_20260529_020_space_trend_high_close_orderly_range_"
                    "fixed_notional_sleeve.py"
                ),
            },
            "accepted_high_close_comparison": accepted_comparison,
            "production_impact": {
                "shared_policy_changed": gate4_passed,
                "backtester_adapter_changed": gate4_passed,
                "run_adapter_changed": gate4_passed,
                "replay_only": True,
                "parity_test_added": gate4_passed,
                "default_off_paper_only": True,
                "metadata_only": True,
                "production_field": "signal_day_ticker_open_close_return_pct",
                "production_bucket": (
                    "space_trend_high_close_intraday_thrust_bucket"
                ),
                "production_watchlist_changed": False,
                "production_orders_changed": False,
                "production_ranking_changed": False,
                "production_sizing_changed": False,
                "production_exits_changed": False,
                "trade_enabled": False,
                "promotion_requirement": (
                    "Shared default-off Space observation metadata may be exposed "
                    "after a retained result, but live/default behavior still "
                    "requires a separate promotion experiment. Live Space slots "
                    "remain zero."
                ),
            },
            "why_not_other_changes": (
                "Skipped LLM soft-ranking because replay-safe Space semantic rows "
                "remain sparse; skipped high-close threshold retuning because "
                "exp-20260528-026 is already accepted; skipped ticker expansion "
                "because recent Space core/paper cohorts failed stability or "
                "concentration. This tests one existing production-visible OHLCV "
                "intraday-thrust field on the accepted high-close trend pool."
            ),
            "interpretation": (
                "The Space high-close intraday-thrust route cleared Gate 4 as a "
                "default-off observation-sleeve refinement and improved the "
                "accepted high-close baseline. It is not a live capital change; "
                "the production helper should expose the same metadata with "
                "trade_enabled false."
                if gate4_passed
                else (
                    "The Space high-close intraday-thrust route did not clear "
                    "Gate 4 versus the accepted high-close baseline; do not "
                    "promote it or retry nearby Space price-action thresholds on "
                    "the frozen sample without forward replacement evidence."
                )
            ),
            "next_evidence_needed": (
                "Expose the same intraday-thrust bucket in the shared default-off "
                "Space observation helper and collect forward replacement-value "
                "rows before any live/default behavior changes."
                if gate4_passed
                else (
                    "Forward replacement-value outcomes or a materially new Space "
                    "event-quality field; avoid nearby price-action threshold "
                    "retunes on these frozen windows."
                )
            ),
            "related_files": [
                _repo_rel(Path(__file__)),
                _repo_rel(OUT_JSON),
                _repo_rel(LOG_JSON),
                _repo_rel(TICKET_JSON),
                _repo_rel(DOCS_TICKET_JSON),
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
        "existing signal strategy field generated before next-open paper entry",
        "signal-day OHLCV open/high/low/close from previous market date before next-open paper entry",
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
                "accepted exp-20260528-026 high-close baseline; >=5 target trades "
                "across >=2 windows; drawdown drift <=0.5pp; survival >=5%; "
                "concentration guard passes"
            ),
            "passed": gate4_passed,
            "base_gate4_passed": base_gate4_passed,
            "accepted_high_close_baseline_improved": improves_accepted_high_close,
            "aggregate_expected_value_score_delta": aggregate[
                "expected_value_score_delta_sum"
            ],
            "aggregate_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        }
    )
    payload["rejection_reason"] = None if gate4_passed else (
        "failed_core_gate_or_failed_incremental_accepted_high_close_comparison"
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
    accepted = payload["accepted_high_close_comparison"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Space High-Close Intraday-Thrust Sleeve",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: route the governed full-history Space observation pool into an additive fixed-notional default-off paper sleeve only when the existing signal engine labels the discovery `trend_long`, signal-day close-location is `>= 0.84`, and signal-day open-to-close return is `>= 4%`.",
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
            "## Incremental Versus Accepted High-Close",
            "",
            f"- baseline: `{accepted['baseline_experiment_id']}`",
            f"- EV delta: `{accepted['aggregate_expected_value_score_delta']}`",
            f"- PnL delta: `${accepted['aggregate_total_pnl_delta']}`",
            f"- EV-regressed windows: `{accepted['windows_ev_regressed']}`",
            f"- PnL-regressed windows: `{accepted['windows_pnl_regressed']}`",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "Gate-passing metadata is surfaced through the shared feature layer and default-off Space observation slot. Live Space slots remain zero, and no production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _registry_index_entry(ticket: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": ticket.get("status"),
        "lane": ticket.get("lane"),
        "owner": ticket.get("owner"),
        "hypothesis": ticket.get("hypothesis"),
        "ticket_file": f"docs/experiments/tickets/{EXPERIMENT_ID}.json",
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def _update_registry_ticket(payload: dict[str, Any]) -> None:
    ticket = {}
    if DOCS_TICKET_JSON.exists():
        ticket = json.loads(DOCS_TICKET_JSON.read_text(encoding="utf-8"))
    ticket.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "lane": "alpha_discovery",
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
    DOCS_TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    DOCS_TICKET_JSON.write_text(
        json.dumps(space_base._safe(ticket), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    if not REGISTRY_JSON.exists():
        return
    registry = json.loads(REGISTRY_JSON.read_text(encoding="utf-8"))
    entry = _registry_index_entry(ticket)
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
    space_base._write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Space high-close intraday-thrust sleeve",
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": _repo_rel(ARTIFACT_MD),
            "json": _repo_rel(OUT_JSON),
            "summary": payload["interpretation"],
        },
    )
    space_base._write_text(ARTIFACT_MD, report)
    space_base._write_text(CARD_MD, report)
    space_base._upsert_jsonl(EXPERIMENT_LOG, payload)
    _update_registry_ticket(payload)


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
                    "accepted_high_close_comparison": payload[
                        "accepted_high_close_comparison"
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
