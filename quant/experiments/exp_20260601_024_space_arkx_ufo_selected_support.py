"""exp-20260601-024: Space selected ARKX/UFO paper support.

This alpha search keeps the accepted Space high-close/thrust plus ARKX/UFO
breakout-complement route fixed. It changes only one causal variable: already
selected default-off Space paper candidates receive a modest paper-notional
support when ARKX 20d momentum leads UFO 20d momentum.

Core entries, ranking, sizing, exits, heat, LLM/news replay, watchlists, and
live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260531_022_space_arkx_ufo_breakout_complement as accepted


EXPERIMENT_ID = "exp-20260601-024"
STEM = "exp_20260601_024_space_arkx_ufo_selected_support"
TRIAL_FAMILY = "governed_space_selected_arkx_ufo_paper_notional_support"
CHANGED_VARIABLE = "space_selected_arkx_ufo_leader_paper_notional_support_v1"
RULE_VERSION = "space_selected_arkx_ufo_leader_paper_support_v1"

ACCEPTED_BASELINE_EXPERIMENT_ID = "exp-20260531-022"
BASE_NOTIONAL_USD = 10_000.0
ARKX_UFO_LEADER_SUPPORT_SCALAR = 1.10
MIN_SUPPORTED_TRADES = 3
MIN_SUPPORTED_WINDOWS = 2
MAX_DRAWDOWN_WORSE = 0.005

space_base = accepted.space_base
REPO_ROOT = accepted.REPO_ROOT
SOURCE_UNIVERSE_STATE = accepted.SOURCE_UNIVERSE_STATE
SOURCE_OHLCV_EXPERIMENT_ID = accepted.SOURCE_OHLCV_EXPERIMENT_ID
WINDOWS = accepted.WINDOWS
TARGET_TICKERS = accepted.TARGET_TICKERS
TARGET_SECTOR_MAP = accepted.TARGET_SECTOR_MAP

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
ACCEPTED_BASELINE_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / ACCEPTED_BASELINE_EXPERIMENT_ID
    / "exp_20260531_022_space_arkx_ufo_breakout_complement.json"
)


def _repo_rel(path: Path | str) -> str:
    return space_base._repo_rel(path)


def _arkx_ufo_leader_support_state(market_state: dict[str, Any]) -> dict[str, Any]:
    etf_state = market_state.get("space_etf_relative_leadership") or {}
    supported = bool(market_state.get("passed")) and bool(etf_state.get("passed"))
    return {
        "rule_version": RULE_VERSION,
        "support_bucket": supported,
        "support_reason": "arkx_20d_momentum_gt_ufo"
        if supported
        else "not_selected_arkx_ufo_leader",
        "base_notional_usd": BASE_NOTIONAL_USD,
        "support_scalar": ARKX_UFO_LEADER_SUPPORT_SCALAR if supported else 1.0,
        "supported_notional_usd": (
            round(BASE_NOTIONAL_USD * ARKX_UFO_LEADER_SUPPORT_SCALAR, 2)
            if supported
            else BASE_NOTIONAL_USD
        ),
        "space_etf_relative_leadership": etf_state,
        "trade_enabled": False,
        "alters_orders": False,
    }


def _supported_notional_trade(
    trade: dict[str, Any],
    market_state: dict[str, Any],
) -> dict[str, Any]:
    pnl_pct = float(trade.get("pnl_pct_net") or 0.0)
    support = _arkx_ufo_leader_support_state(market_state)
    notional = float(support["supported_notional_usd"])
    return {
        **trade,
        "core_sized_pnl": space_base._round(trade.get("pnl"), 2),
        "core_sized_shares": trade.get("shares"),
        "base_paper_notional_usd": BASE_NOTIONAL_USD,
        "paper_notional_usd": notional,
        "space_arkx_ufo_selected_support": support,
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
            support = trade.get("space_arkx_ufo_selected_support") or {}
            if support.get("support_bucket"):
                rows.append({**trade, "window": label})
    return {
        "trade_count": len(rows),
        "windows": sorted({row["window"] for row in rows}),
        "incremental_notional_usd": space_base._round(
            sum(
                float((row.get("space_arkx_ufo_selected_support") or {}).get("supported_notional_usd") or 0.0)
                - BASE_NOTIONAL_USD
                for row in rows
            ),
            2,
        ),
        "incremental_pnl": space_base._round(
            sum(
                float(row.get("pnl_pct_net") or 0.0)
                * (
                    float((row.get("space_arkx_ufo_selected_support") or {}).get("supported_notional_usd") or 0.0)
                    - BASE_NOTIONAL_USD
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


def _configure_space_base() -> None:
    accepted._configure_space_base()
    space_base.EXPERIMENT_ID = EXPERIMENT_ID
    space_base.STEM = STEM
    space_base.TRIAL_FAMILY = TRIAL_FAMILY
    space_base.CHANGED_VARIABLE = CHANGED_VARIABLE
    space_base.TARGET_TICKERS = TARGET_TICKERS
    space_base.TARGET_SECTOR_MAP = TARGET_SECTOR_MAP
    space_base.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    space_base.MIN_TARGET_TRADES = accepted.MIN_TARGET_TRADES
    space_base.MIN_TARGET_WINDOWS = accepted.MIN_TARGET_WINDOWS
    space_base.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    space_base.MAX_SINGLE_POSITIVE_SHARE = accepted.MAX_SINGLE_POSITIVE_SHARE
    space_base.MAX_POSITIVE_HHI = accepted.MAX_POSITIVE_HHI
    space_base.OUT_DIR = OUT_DIR
    space_base.OUT_JSON = OUT_JSON
    space_base.LOG_JSON = LOG_JSON
    space_base.TICKET_JSON = TICKET_JSON
    space_base.ARTIFACT_MD = CARD_MD
    space_base.EXPERIMENT_LOG = EXPERIMENT_LOG
    space_base._target_universe = accepted.accepted.high_close._target_universe
    space_base._market_confirmation = (
        accepted._strategy_high_close_thrust_with_breakout_complement
    )
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
        "positive_replay_lead_requires_shared_space_arkx_ufo_support_helper"
        if gate4_passed
        else "rejected_space_arkx_ufo_selected_support"
    )
    aggregate = payload["delta_metrics"]["aggregate"]
    before_metrics = payload["before_metrics"]
    min_survival = min(
        float(row.get("survival_rate") or 0.0) for row in before_metrics.values()
    )
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    predicted_success_probability = 0.32
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
            "change_type": "default_off_paper_allocation",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": EXPERIMENT_ID,
            "prior_trial_count": 1,
            "nearby_prior_experiments": [
                "exp-20260528-026",
                "exp-20260529-020",
                "exp-20260531-022",
            ],
            "multiple_testing_risk_bucket": "high",
            "new_evidence_type": (
                "production_visible_space_etf_relative_leadership_field_on_"
                "selected_space_paper_candidates"
            ),
            "hypothesis": (
                "Accepted Space high-close/thrust paper candidates may deserve "
                "modest default-off notional support when ARKX 20d momentum "
                "leads UFO, indicating institutional space breadth rather than "
                "speculative attention."
            ),
            "prediction": {
                "success_probability": predicted_success_probability,
                "expected_ev_delta_vs_current_accepted": "positive_low_confidence",
                "expected_pnl_delta_vs_current_accepted": "positive_low_confidence",
                "main_failure_modes": [
                    "nearby_etf_field_overfit",
                    "thin_supported_sample",
                    "window_instability",
                    "drawdown_drift",
                ],
                "confidence_reason": (
                    "Existing accepted Space route is all-positive and ARKX>UFO "
                    "already admitted one useful breakout complement, but this is "
                    "a nearby ETF/notional support test with high multiple-testing "
                    "risk."
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
                "arkx_ufo_leader_support_scalar": ARKX_UFO_LEADER_SUPPORT_SCALAR,
                "target_tickers": payload["parameters"]["target_tickers"],
                "target_sector_map": TARGET_SECTOR_MAP,
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
                    "accepted high-close/thrust trend branch",
                    "accepted ARKX/UFO breakout complement admission",
                ],
                "anti_js": "No JavaScript was used.",
            },
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "risk allocation/capital allocation: already selected "
                    "default-off Space paper candidates may deserve a modest "
                    "notional support when ARKX 20d momentum leads UFO."
                ),
                "2_history_check": {
                    "exp-20260528-026": (
                        "Accepted high-close trend route improved aggregate EV "
                        "but should not be threshold-retuned on frozen windows."
                    ),
                    "exp-20260529-020": (
                        "Accepted intraday-thrust refinement improved the high-close "
                        "baseline; this keeps those admission rules fixed."
                    ),
                    "exp-20260531-022": (
                        "Accepted ARKX>UFO breakout complement improved only old_thin "
                        "via one RKLB trade; this tests support only after selection "
                        "rather than admitting more candidates."
                    ),
                    "llm_soft_ranking": (
                        "Skipped because replay-safe Space semantic rows and closed "
                        "same-theme replacement outcomes remain sparse."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same three docs/backtesting.md Space observation windows; "
                    "positive aggregate EV/PnL versus core; no EV/PnL-regressed "
                    "windows versus core; improvement versus accepted exp-20260531-022; "
                    f">={MIN_SUPPORTED_TRADES} supported target paper trades across "
                    f">={MIN_SUPPORTED_WINDOWS} windows; drawdown drift <=0.5pp; "
                    "survival >=5%; target concentration inside guardrails; and no "
                    "production/backtest split before promotion."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe quant\\experiments\\"
                    "exp_20260601_024_space_arkx_ufo_selected_support.py"
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
                "production_fields": [
                    "ARKX momentum_20d_pct",
                    "UFO momentum_20d_pct",
                ],
                "production_watchlist_changed": False,
                "production_orders_changed": False,
                "production_ranking_changed": False,
                "production_sizing_changed": False,
                "production_exits_changed": False,
                "trade_enabled": False,
                "promotion_requirement": (
                    "A passing replay remains a lead until the shared default-off "
                    "Space observation helper and focused parity tests expose the "
                    "same support metadata; live Space slots remain zero."
                ),
            },
            "why_not_other_changes": (
                "Skipped LLM soft-ranking because replay-safe Space semantic rows "
                "remain sparse; skipped Space ticker expansion because prior broad "
                "Space pools failed stability or concentration; skipped ARKX/UFO "
                "threshold retuning because this uses the accepted zero-threshold "
                "relative-leadership state and only changes selected paper notional."
            ),
            "interpretation": (
                "The ARKX>UFO selected-candidate support is a positive replay lead, "
                "but it is not promoted in this runner because production must expose "
                "the same default-off metadata before retention."
                if gate4_passed
                else (
                    "The ARKX>UFO selected-candidate support did not clear Gate 4 "
                    "versus the current accepted Space route; do not promote it "
                    "without forward replacement evidence."
                )
            ),
            "next_evidence_needed": (
                "Add a shared default-off Space observation helper/parity test for "
                "the support metadata, then collect forward replacement-value rows."
                if gate4_passed
                else (
                    "Forward replacement-value outcomes or a materially new Space "
                    "event-quality field; avoid nearby ARKX/UFO notional retunes on "
                    "these frozen windows."
                )
            ),
            "related_files": [
                _repo_rel(Path(__file__)),
                _repo_rel(OUT_JSON),
                _repo_rel(LOG_JSON),
                _repo_rel(TICKET_JSON),
                _repo_rel(CARD_MD),
                _repo_rel(EXPERIMENT_LOG),
                _repo_rel(REGISTRY_JSON),
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
        "20-trading-day ARKX and UFO return computed from signal-day-close-known OHLCV",
        "risk_engine.SECTOR_MAP target tickers patched from TARGET_SECTOR_MAP in replay",
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
                "exp-20260531-022; supported sample across >=2 windows; drawdown "
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
            f"# {EXPERIMENT_ID} Space ARKX/UFO Selected Support",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: keep the accepted Space paper route fixed and apply a 1.10x default-off paper-notional support only to already selected candidates when ARKX 20d momentum leads UFO.",
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
            "This runner does not promote the support into production. A retained change would need the shared default-off Space observation helper and focused parity tests before it can be accepted; live Space slots remain zero.",
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
                    "support_trade_summary": payload["support_trade_summary"],
                    "gate4": payload["gate4"],
                    "target_trade_summary": payload["target_trade_summary"],
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
