"""exp-20260528-035: industry-leadership high-close paper route.

This alpha search keeps the industry-leadership breadth breakout source from
exp-20260527-022 fixed, then tests one production-visible OHLCV routing field:
only admit default-off paper candidates whose signal day closed in the upper
30% of its own intraday range.

Core signal generation, ranking, sizing, exits, LLM/news replay, watchlists,
and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
LEGACY_DIR = EXPERIMENT_DIR / "legacy"
for path in (QUANT_DIR, EXPERIMENT_DIR, LEGACY_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as base  # noqa: E402
import exp_20260527_022_industry_leadership_breadth_breakout_sleeve as source  # noqa: E402


EXPERIMENT_ID = "exp-20260528-035"
STEM = "industry_leadership_high_close"
TRIAL_FAMILY = "industry_leadership_signal_day_high_close_candidate_pool"
CHANGED_VARIABLE = "industry_leadership_signal_day_high_close_routing_v1"
RULE_VERSION = "industry_leadership_signal_day_high_close_routing_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260528_035_industry_leadership_high_close.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

MIN_SIGNAL_DAY_CLOSE_LOCATION = 0.70
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30

HIGH_CLOSE_AUDIT: "OrderedDict[str, dict[str, Any]]" = OrderedDict()


def _configure_base_module() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.OUT_DIR = OUT_DIR
    base.OUT_JSON = OUT_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.ARTIFACT_MD = ARTIFACT_MD
    base.EXPERIMENT_LOG = EXPERIMENT_LOG
    base.MAX_PAPER_TRADES_PER_DAY = source.MAX_PAPER_TRADES_PER_DAY
    base.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    base.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    base.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    base.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    base.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    base.shadow = source.ohlcv_helper
    for name in (
        "MIN_PRIOR_DAY_RETURN",
        "MIN_PRIOR_DAY_RS_VS_SPY",
        "MIN_OPEN_VS_PRIOR_CLOSE",
    ):
        if not hasattr(source.ohlcv_helper, name):
            setattr(source.ohlcv_helper, name, None)


def _row_value(row: dict[str, Any], key: str) -> Any:
    return row.get(key) if key in row else row.get(key.capitalize())


def _float_or_none(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _window_label(cfg: dict[str, str]) -> str:
    return next(
        (
            window_label
            for window_label, window_cfg in base.WINDOWS.items()
            if window_cfg is cfg
        ),
        str(cfg.get("start")),
    )


def _signal_day_row(
    snapshot: dict[str, list[dict[str, Any]]],
    candidate: dict[str, Any],
) -> dict[str, Any] | None:
    ticker = str(candidate.get("ticker") or "").upper()
    signal_date = str(candidate.get("date") or candidate.get("signal_date") or "")[:10]
    if not ticker or not signal_date:
        return None
    for row in snapshot.get(ticker, []) or []:
        row_date = str(_row_value(row, "date") or "")[:10]
        if row_date == signal_date:
            return row
    return None


def _close_location(
    snapshot: dict[str, list[dict[str, Any]]],
    candidate: dict[str, Any],
) -> float | None:
    row = _signal_day_row(snapshot, candidate)
    if row is None:
        return None
    high = _float_or_none(_row_value(row, "high"))
    low = _float_or_none(_row_value(row, "low"))
    close = _float_or_none(_row_value(row, "close"))
    if high is None or low is None or close is None or high <= low:
        return None
    return max(0.0, min(1.0, (close - low) / (high - low)))


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> list[dict[str, Any]]:
    raw = source._candidate_rows_for_window(snapshot, cfg, universe, before_result)
    selected: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    close_values: list[float] = []
    selected_values: list[float] = []
    label = _window_label(cfg)

    for row in raw:
        value = _close_location(snapshot, row)
        if value is not None:
            close_values.append(value)
        if value is not None and value >= MIN_SIGNAL_DAY_CLOSE_LOCATION:
            candidate = dict(row)
            candidate["strategy"] = "industry_leadership_high_close"
            candidate["industry_leadership_high_close_rule_version"] = RULE_VERSION
            candidate["signal_day_close_location_value"] = base._round(value, 6)
            candidate["min_signal_day_close_location"] = MIN_SIGNAL_DAY_CLOSE_LOCATION
            candidate["known_at"] = "after_signal_date_close_before_next_open_paper_entry"
            candidate["trade_enabled"] = False
            candidate["alters_orders"] = False
            selected.append(candidate)
            selected_values.append(value)
        else:
            filtered.append(
                {
                    **row,
                    "filter_reason": "signal_day_close_location_below_threshold",
                    "signal_day_close_location_value": base._round(value, 6),
                    "min_signal_day_close_location": MIN_SIGNAL_DAY_CLOSE_LOCATION,
                }
            )

    raw_industries = Counter(str(row.get("industry") or "Unknown") for row in raw)
    selected_industries = Counter(str(row.get("industry") or "Unknown") for row in selected)
    HIGH_CLOSE_AUDIT[label] = {
        "rule_version": RULE_VERSION,
        "min_signal_day_close_location": MIN_SIGNAL_DAY_CLOSE_LOCATION,
        "raw_candidate_count": len(raw),
        "selected_candidate_count": len(selected),
        "filtered_candidate_count": len(filtered),
        "raw_candidate_days": len({row["date"] for row in raw}),
        "selected_candidate_days": len({row["date"] for row in selected}),
        "raw_unique_tickers": len({row["ticker"] for row in raw}),
        "selected_unique_tickers": len({row["ticker"] for row in selected}),
        "raw_top_industries": dict(raw_industries.most_common(10)),
        "selected_top_industries": dict(selected_industries.most_common(10)),
        "all_close_location_min": base._round(min(close_values) if close_values else None, 6),
        "all_close_location_max": base._round(max(close_values) if close_values else None, 6),
        "selected_close_location_min": base._round(
            min(selected_values) if selected_values else None,
            6,
        ),
        "selected_close_location_max": base._round(
            max(selected_values) if selected_values else None,
            6,
        ),
    }
    return selected


def _update_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4_passed = bool(payload["gate4"]["passed"])
    decision = (
        "promising_replay_only_industry_leadership_high_close"
        if gate4_passed
        else "rejected_industry_leadership_high_close"
    )
    payload["status"] = decision
    payload["decision"] = decision
    payload["hypothesis"] = (
        "Industry-leadership breadth breakout candidates may have cleaner "
        "replacement value when the signal day closes in the upper 30% of its "
        "own intraday range. The source candidate definition, ranking, paper "
        "notional, hold period, execution model, core stack, LLM/news replay, "
        "and live orders stay fixed."
    )
    payload["change_type"] = "default_off_paper_candidate_pool_routing"
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["trial_family"] = TRIAL_FAMILY
    payload["trial_variant_id"] = "close_location_gte_0p70_fixed_notional_v1"
    payload["mechanism_family"] = (
        "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
    )
    payload["prior_trial_count"] = 3
    payload["nearby_prior_experiments"] = [
        "exp-20260527-022",
        "exp-20260528-032",
        "exp-20260528-034",
        "exp-20260528-022",
        "exp-20260528-026",
    ]
    payload["multiple_testing_risk_bucket"] = "moderate"
    payload["new_evidence_type"] = (
        "orthogonal_free_ohlcv_signal_day_close_location_field"
    )
    payload["parameters"]["shadow_entry_filters"] = {
        **payload["parameters"].get("shadow_entry_filters", {}),
        "source_experiment": "exp-20260527-022 industry-leadership breadth breakout",
        "added_route": "signal_day_close_location_value >= 0.70",
        "min_signal_day_close_location": MIN_SIGNAL_DAY_CLOSE_LOCATION,
        "locked_source_thresholds": {
            "breakout_lookback_days": source.BREAKOUT_LOOKBACK_DAYS,
            "moving_average_days": source.MOVING_AVERAGE_DAYS,
            "return_lookback_days": source.RETURN_LOOKBACK_DAYS,
            "min_candidate_dollar_volume": source.MIN_CANDIDATE_DOLLAR_VOLUME,
            "min_candidate_volume_ratio_20": source.MIN_CANDIDATE_VOLUME_RATIO_20,
            "min_candidate_day_rs_vs_spy": source.MIN_CANDIDATE_DAY_RS_VS_SPY,
            "min_candidate_ret20_excess_spy": source.MIN_CANDIDATE_RET20_EXCESS_SPY,
            "min_industry_eligible_tickers": source.MIN_INDUSTRY_ELIGIBLE_TICKERS,
            "min_industry_leader_count": source.MIN_INDUSTRY_LEADER_COUNT,
            "min_industry_leadership_fraction": source.MIN_INDUSTRY_LEADERSHIP_FRACTION,
        },
    }
    payload["parameters"]["locked_variables"] = [
        "core universe membership",
        "core signal generation",
        "core ranking",
        "core position sizing",
        "core exits",
        "portfolio heat",
        "slot rules",
        "LLM/news replay",
        "watchlists",
        "live/default orders",
        "industry-leadership source thresholds from exp-20260527-022",
        "paper notional, next-open entry, and ten-trading-day exit",
    ]
    payload["parameters"]["acceptance"].update(
        {
            "min_target_trades": MIN_TARGET_TRADES,
            "min_target_windows": MIN_TARGET_WINDOWS,
            "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
            "max_positive_hhi": MAX_POSITIVE_HHI,
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "candidate_pool / entry: same-industry leadership breakouts are "
            "more likely to add replacement value when the signal day closes "
            "near its own high, which is a free OHLCV demand-quality field."
        ),
        "2_history_check": {
            "exp-20260527-022": (
                "Raw industry-leadership breadth breakout had positive aggregate "
                "EV/PnL but failed Gate 4 because late_strong regressed."
            ),
            "exp-20260528-032": (
                "Sector-breadth closed-ledger governor stayed positive in "
                "aggregate but still failed late_strong."
            ),
            "exp-20260528-034": (
                "No-core-overlap industry-leadership improved mid_weak and "
                "old_thin but failed late_strong and concentration."
            ),
            "positive_field_analogs": (
                "VBB signal-day high-close support and Space trend high-close "
                "routing were recently useful on separate paper surfaces, but "
                "this run fixes the threshold at 0.70 instead of mining a new "
                "sweep."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Same docs/backtesting.md three windows; positive aggregate EV/PnL; "
            "3/3 EV-improved windows; no PnL-regressed window; >=20 paper trades "
            "across all 3 windows; drawdown drift <=0.5pp; survival >=5%; "
            "target concentration inside guardrails."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260528_035_industry_leadership_high_close.py"
        ),
    }
    payload["gate2"]["runtime_fields"] = [
        "canonical OHLCV Date/Open/High/Low/Close/Volume rows",
        "candidate ticker signal-day high/low/close",
        "candidate ticker trailing 20/50-day OHLCV features",
        "same-date same-industry peer leadership counts",
        "data/reference/broad_market_sector_map.json sector/industry/status rows",
        "SPY OHLCV Close rows for signal-day and trailing relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["gate2"]["note"] = (
        "The high-close route uses only signal-day OHLCV known after that close "
        "and before next-open paper entry. No future price path, LLM judgment, "
        "or hidden production-only field is used."
    )
    payload["gate3"]["candidate_pool_changed"] = True
    payload["gate3"]["note"] = (
        "No core filter or live entry rule was added. This is default-off paper "
        "candidate routing, so core survival is unchanged."
    )
    payload["industry_leadership_audit"] = source.INDUSTRY_AUDIT
    payload["high_close_audit"] = HIGH_CLOSE_AUDIT
    payload["why_not_other_changes"] = (
        "This run does alpha_search, not measurement repair, because the "
        "baseline, Gate 2 fields, and survival audit are readable. It avoids "
        "data-limited LLM/PEAD/Kova exit work, state-surface scalar mining, and "
        "nearby Companyfacts/VBB/VCP frozen-sample retunes."
    )
    payload["interpretation"] = (
        "The industry-leadership high-close route cleared the numeric Gate 4 "
        "as a replay-only lead. It was not promoted into production because a "
        "shared default-off paper adapter and parity tests would be required "
        "before retaining any strategy behavior."
        if gate4_passed
        else (
            "The industry-leadership high-close route did not clear Gate 4. Do "
            "not promote it or retry nearby close-location/industry-overlap "
            "variants on these frozen windows without forward paper rows or a "
            "materially different production-visible field."
        )
    )
    payload["rejection_reason"] = None if gate4_passed else "; ".join(
        payload["gate4"].get("failed_reasons") or []
    )
    payload["next_retry_requires"] = [
        "new_forward_industry_leadership_closed_outcomes",
        "materially_different_free_data_source_quality_field",
        "shared_default_off_paper_adapter_before_any_production_retention",
    ]
    payload["production_impact"] = {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": True,
        "parity_test_added": False,
        "default_off_paper_only": True,
        "production_signal_path_changed": False,
        "production_watchlist_changed": False,
        "production_orders_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "trade_enabled": False,
        "promotion_requirement": (
            "A positive result cannot be retained as strategy behavior until the "
            "same route is implemented in a shared default-off paper adapter, "
            "surfaced by production, and covered by parity tests."
        ),
    }
    payload["calibration"] = {
        "actual_decision": payload["decision"],
        "actual_success": 1 if gate4_passed else 0,
        "predicted_success_probability": 0.32,
        "brier_score": base._round((0.32 - (1 if gate4_passed else 0)) ** 2, 6),
        "expected_ev_delta": 0.20,
        "actual_ev_delta": payload.get("expected_value_score_delta"),
        "expected_pnl_delta": 6000.0,
        "actual_pnl_delta": payload.get("total_pnl_delta"),
        "predicted_failure_modes": [
            "late_strong_regression",
            "sample_concentration",
            "target_sample_too_small",
        ],
        "realized_failure_mode": payload["rejection_reason"],
    }
    payload["related_files"] = [
        base._repo_rel(Path(__file__)),
        base._repo_rel(OUT_JSON),
        base._repo_rel(LOG_JSON),
        base._repo_rel(TICKET_JSON),
        base._repo_rel(ARTIFACT_MD),
        base._repo_rel(EXPERIMENT_LOG),
    ]
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw | Routed |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["high_close_audit"].get(label, {})
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | "
            "${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | "
            "{trades} | {raw} | {routed} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                raw=audit.get("raw_candidate_count"),
                routed=audit.get("selected_candidate_count"),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Industry-Leadership High-Close Route",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            (
                "Single variable: route industry-leadership paper candidates only "
                "when signal-day close-location value is `>= 0.70`."
            ),
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
            "## Aggregate",
            "",
            f"- EV delta: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- target trades: `{payload['target_trade_summary']['total_trade_count']}` across `{len(payload['target_trade_summary']['windows_with_target_trades'])}` windows",
            f"- max single positive share: `{payload['target_trade_summary']['max_single_positive_pnl_share']}`",
            f"- positive PnL HHI: `{payload['target_trade_summary']['positive_pnl_hhi']}`",
            "",
            "## High-Close Audit",
            "",
            "```json",
            json.dumps(payload["high_close_audit"], indent=2, sort_keys=True),
            "```",
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
                "Replay-only and default-off paper only. No shared policy, run "
                "adapter, backtester adapter, production watchlist, order path, "
                "core entry, ranking, sizing, or exit behavior changed."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _ticket(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "title": "Industry-leadership high-close paper route",
        "status": payload["status"],
        "lane": "alpha_discovery",
        "owner": "codex-alpha-search",
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "decision": payload["decision"],
        "completed_at": payload["timestamp"],
        "result": {
            "decision": payload["decision"],
            "expected_value_score_delta": payload["expected_value_score_delta"],
            "total_pnl_delta": payload["total_pnl_delta"],
            "gate4_passed": payload["gate4"]["passed"],
            "failed_reasons": payload["gate4"].get("failed_reasons", []),
        },
        "artifact": base._repo_rel(ARTIFACT_MD),
        "json": base._repo_rel(OUT_JSON),
        "summary": payload["interpretation"],
    }


def _persist(payload: dict[str, Any]) -> None:
    base._write_json(OUT_JSON, payload)
    base._write_json(LOG_JSON, payload)
    base._write_json(TICKET_JSON, _ticket(payload))
    base._write_text(ARTIFACT_MD, _build_report(payload))
    base._upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    _configure_base_module()
    source.INDUSTRY_AUDIT.clear()
    HIGH_CLOSE_AUDIT.clear()
    base._candidate_rows_for_window = _candidate_rows_for_window
    payload = _update_payload(base._build_payload())
    _persist(payload)
    print(
        json.dumps(
            base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "target_trade_summary": payload["target_trade_summary"],
                    "high_close_audit": payload["high_close_audit"],
                    "artifact": base._repo_rel(ARTIFACT_MD),
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
