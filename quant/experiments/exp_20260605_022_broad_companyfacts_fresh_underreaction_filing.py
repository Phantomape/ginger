"""exp-20260605-022: broad Companyfacts fresh underreaction filing.

This alpha search tests one replay-only/default-off paper candidate source:
fresh SEC Companyfacts dual-growth filings are eligible only when the ticker
did not outperform SPY before the filing and the first usable trading day
closes constructively. Unlike exp-20260605-011, this does not reuse stale
growth rows every day; each filing event can emit at most one delayed next-open
paper candidate.

No production adapter, live order path, shared policy, ranking, sizing, exits,
LLM/news path, or watchlist is changed. No JavaScript is used.
"""

from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
from typing import Any

import pandas as pd

import exp_20260605_011_broad_companyfacts_dual_growth_rs_candidate_pool as base


_BASE_BUILD_PAYLOAD = base.build_payload

EXP_ID = "exp-20260605-022"
STEM = "broad_companyfacts_fresh_underreaction_filing"
TRIAL_FAMILY = "broad_companyfacts_fresh_underreaction_filing_candidate_pool"
TRIAL_VARIANT_ID = "broad_companyfacts_fresh_underreaction_filing_top1_v1"
CHANGED_VARIABLE = "broad_companyfacts_fresh_underreaction_filing_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"exp_20260605_022_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXP_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXP_ID}.json"

PAPER_NOTIONAL = 4_000.0
HOLD_DAYS = 10
MAX_DRAWDOWN_WORSE = 0.005
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.30

MAX_FILING_TO_SIGNAL_TRADING_DAYS = 2
MIN_REVENUE_YOY_GROWTH = 0.15
MIN_PROFIT_YOY_GROWTH = 0.15
MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_SIGNAL_CLOSE_LOCATION = 0.60
MIN_SIGNAL_DAY_RETURN = 0.0
MIN_RET20_EXCESS_SPY = -0.02
MAX_PREFILING_RET20_EXCESS_SPY = 0.0
SAME_TICKER_COOLDOWN_DAYS = 30
MAX_PAPER_TRADES_PER_ENTRY_DAY = 1

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_no_live_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "parity_note": (
        "This runner changes no production code. It uses only SEC Companyfacts "
        "growth rows with filed-date visibility, warehouse OHLCV known after "
        "the first usable trading-day close, and delayed next-open paper "
        "entry. A positive result would require a separate shared default-off "
        "fresh Companyfacts filing adapter, daily production exposure of the "
        "same filed-date and OHLCV confirmation fields, warehouse/snapshot "
        "replay parity, and focused tests before any report queue, paper "
        "ledger, candidate priority, or order surface could change."
    ),
}


def _patch_base_module() -> None:
    base.EXP_ID = EXP_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.RULE_VERSION = RULE_VERSION
    base.OUT_DIR = OUT_DIR
    base.OUT_JSON = OUT_JSON
    base.BEFORE_JSON = BEFORE_JSON
    base.AFTER_JSON = AFTER_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.CARD_MD = CARD_MD
    base.ARTIFACT_MD = ARTIFACT_MD
    base.MANIFEST_JSON = MANIFEST_JSON
    base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    base.PAPER_NOTIONAL = PAPER_NOTIONAL
    base.HOLD_DAYS = HOLD_DAYS
    base.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    base.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    base.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    base.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    base.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI


def _growth_pair_for_filing(
    growth_index: dict[str, dict[str, list[dict[str, Any]]]],
    ticker: str,
    signal_day_s: str,
) -> dict[str, Any] | None:
    revenue = base._latest_growth_row(growth_index, ticker, "revenue", signal_day_s)
    profit = base._profit_growth_row(growth_index, ticker, signal_day_s)
    if revenue is None or profit is None:
        return None
    revenue_growth = float(revenue["yoy_growth"])
    profit_growth = float(profit["yoy_growth"])
    if revenue_growth < MIN_REVENUE_YOY_GROWTH or profit_growth < MIN_PROFIT_YOY_GROWTH:
        return None
    if revenue.get("current_value") is None or float(revenue["current_value"]) <= 0.0:
        return None
    filing_date = max(str(revenue["asof_date"]), str(profit["asof_date"]))
    return {
        "revenue": revenue,
        "profit": profit,
        "filing_date": filing_date,
        "revenue_growth": revenue_growth,
        "profit_growth": profit_growth,
        "growth_score": min(max(revenue_growth, -1.0), 1.5)
        + min(max(profit_growth, -1.0), 1.5),
    }


def _first_signal_pos_after_filing(frame: pd.DataFrame, filing_date: str) -> int | None:
    pos = int(frame.index.searchsorted(pd.Timestamp(filing_date), side="left"))
    if pos >= len(frame):
        return None
    signal_pos = pos + 1
    if signal_pos >= len(frame):
        return None
    if signal_pos - pos > MAX_FILING_TO_SIGNAL_TRADING_DAYS:
        return None
    return signal_pos


def _candidate_for_ticker_filing(
    *,
    ticker: str,
    frame: pd.DataFrame,
    spy_frame: pd.DataFrame,
    signal_pos: int,
    growth: dict[str, Any],
) -> dict[str, Any] | None:
    signal_day = frame.index[signal_pos]
    spy_signal_pos = base._frame_pos(spy_frame, signal_day)
    if spy_signal_pos is None or signal_pos < 21 or spy_signal_pos < 21:
        return None

    close = float(frame["Close"].iloc[signal_pos])
    if close < MIN_PRICE:
        return None
    adv20 = base._avg_dollar_volume(frame, signal_pos)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None
    close_location = base._close_location(frame, signal_pos)
    if close_location is None or close_location < MIN_SIGNAL_CLOSE_LOCATION:
        return None

    signal_day_return = close / float(frame["Close"].iloc[signal_pos - 1]) - 1.0
    if signal_day_return < MIN_SIGNAL_DAY_RETURN:
        return None

    ret20 = base._ret(frame, signal_pos, 20)
    spy_ret20 = base._ret(spy_frame, spy_signal_pos, 20)
    ret20_prev = base._ret(frame, signal_pos - 1, 20)
    spy_ret20_prev = base._ret(spy_frame, spy_signal_pos - 1, 20)
    if (
        ret20 is None
        or spy_ret20 is None
        or ret20_prev is None
        or spy_ret20_prev is None
    ):
        return None
    ret20_excess_spy = ret20 - spy_ret20
    prefiling_ret20_excess_spy = ret20_prev - spy_ret20_prev
    if ret20_excess_spy < MIN_RET20_EXCESS_SPY:
        return None
    if prefiling_ret20_excess_spy > MAX_PREFILING_RET20_EXCESS_SPY:
        return None

    volume_ratio_20d = base._volume_ratio(frame, signal_pos) or 0.0
    score = (
        float(growth["growth_score"])
        + 3.5 * ret20_excess_spy
        + 1.5 * (MAX_PREFILING_RET20_EXCESS_SPY - prefiling_ret20_excess_spy)
        + close_location
        + 0.10 * min(volume_ratio_20d, 3.0)
    )
    revenue = growth["revenue"]
    profit = growth["profit"]
    metadata = {
        "companyfacts_filing_date": growth["filing_date"],
        "companyfacts_revenue_asof_date": revenue["asof_date"],
        "companyfacts_profit_asof_date": profit["asof_date"],
        "companyfacts_revenue_yoy_growth": round(float(growth["revenue_growth"]), 6),
        "companyfacts_profit_yoy_growth": round(float(growth["profit_growth"]), 6),
        "companyfacts_profit_canonical": profit["canonical"],
        "companyfacts_revenue_form": revenue.get("current_form"),
        "companyfacts_profit_form": profit.get("current_form"),
        "filing_to_signal_calendar_days": (
            signal_day - pd.Timestamp(growth["filing_date"])
        ).days,
        "signal_day_return": round(signal_day_return, 6),
        "ret20": round(ret20, 6),
        "spy_ret20": round(spy_ret20, 6),
        "ret20_excess_spy": round(ret20_excess_spy, 6),
        "prefiling_ret20_excess_spy": round(prefiling_ret20_excess_spy, 6),
        "close_location": round(close_location, 6),
        "avg_dollar_volume_20d": round(adv20, 2),
        "volume_ratio_20d": round(volume_ratio_20d, 6),
        "candidate_score": round(score, 6),
        "source": "BROAD_COMPANYFACTS_FRESH_UNDERREACTION_FILING_PAPER",
    }
    return base._candidate_trade(ticker, frame, signal_day, signal_pos, metadata)


def _generate_candidates(
    frames: dict[str, pd.DataFrame],
    growth_index: dict[str, dict[str, list[dict[str, Any]]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    spy_frame = frames.get("SPY")
    if spy_frame is None:
        raise RuntimeError("SPY missing from warehouse frames")

    selected: list[dict[str, Any]] = []
    candidates_by_window: dict[str, int] = defaultdict(int)
    selected_by_window: dict[str, int] = defaultdict(int)
    raw_filing_events_by_window: dict[str, int] = defaultdict(int)
    underreaction_rejects_by_window: dict[str, int] = defaultdict(int)
    last_selected_by_ticker: dict[str, pd.Timestamp] = {}
    seen_events: set[tuple[str, str]] = set()

    for label, window in base.WINDOWS.items():
        by_signal_day: dict[pd.Timestamp, list[dict[str, Any]]] = defaultdict(list)
        for ticker, frame in frames.items():
            if ticker == "SPY":
                continue
            for canonical_rows in growth_index.get(ticker, {}).values():
                for row in canonical_rows:
                    filing_date = str(row.get("asof_date") or "")[:10]
                    if not filing_date:
                        continue
                    signal_pos = _first_signal_pos_after_filing(frame, filing_date)
                    if signal_pos is None:
                        continue
                    signal_day = frame.index[signal_pos]
                    signal_day_s = str(signal_day.date())
                    if not (window["start"] <= signal_day_s <= window["end"]):
                        continue
                    if (ticker, filing_date) in seen_events:
                        continue
                    seen_events.add((ticker, filing_date))
                    growth = _growth_pair_for_filing(growth_index, ticker, signal_day_s)
                    if growth is None or growth["filing_date"] != filing_date:
                        continue
                    raw_filing_events_by_window[label] += 1
                    last_selected = last_selected_by_ticker.get(ticker)
                    if (
                        last_selected is not None
                        and (signal_day - last_selected).days < SAME_TICKER_COOLDOWN_DAYS
                    ):
                        continue
                    candidate = _candidate_for_ticker_filing(
                        ticker=ticker,
                        frame=frame,
                        spy_frame=spy_frame,
                        signal_pos=signal_pos,
                        growth=growth,
                    )
                    if candidate is None:
                        underreaction_rejects_by_window[label] += 1
                        continue
                    by_signal_day[signal_day].append({**candidate, "window": label})

        for day in sorted(by_signal_day):
            day_candidates = by_signal_day[day]
            candidates_by_window[label] += len(day_candidates)
            day_candidates.sort(key=lambda item: float(item["candidate_score"]), reverse=True)
            for candidate in day_candidates[:MAX_PAPER_TRADES_PER_ENTRY_DAY]:
                selected.append(candidate)
                selected_by_window[label] += 1
                last_selected_by_ticker[str(candidate["ticker"])] = day

    audit = {
        "raw_candidate_count": len(selected),
        "raw_filing_events_by_window": dict(raw_filing_events_by_window),
        "candidate_rows_before_daily_top1_by_window": dict(candidates_by_window),
        "selected_by_window": dict(selected_by_window),
        "underreaction_rejects_by_window": dict(underreaction_rejects_by_window),
        "growth_ticker_count": len(growth_index),
        "warehouse_frame_count": len(frames),
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "max_paper_trades_per_entry_day": MAX_PAPER_TRADES_PER_ENTRY_DAY,
        "fresh_filing_rule": {
            "max_filing_to_signal_trading_days": MAX_FILING_TO_SIGNAL_TRADING_DAYS,
            "min_revenue_yoy_growth": MIN_REVENUE_YOY_GROWTH,
            "min_profit_yoy_growth": MIN_PROFIT_YOY_GROWTH,
            "min_signal_close_location": MIN_SIGNAL_CLOSE_LOCATION,
            "min_signal_day_return": MIN_SIGNAL_DAY_RETURN,
            "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
            "max_prefiling_ret20_excess_spy": MAX_PREFILING_RET20_EXCESS_SPY,
        },
    }
    return selected, audit


def _write_artifact(payload: dict[str, Any]) -> None:
    lines = [
        f"# {EXP_ID} Broad Companyfacts Fresh Underreaction Filing",
        "",
        f"- Trial family: `{TRIAL_FAMILY}`",
        f"- Changed variable: `{CHANGED_VARIABLE}`",
        f"- Decision: `{payload['gate4']['decision']}`",
        (
            "- Aggregate EV delta: "
            f"{payload['aggregate']['comparison']['expected_value_score_delta']:+.4f}"
        ),
        (
            "- Aggregate PnL delta: "
            f"${payload['aggregate']['comparison']['strategy_total_pnl_delta']:+,.2f}"
        ),
        f"- Target trades: `{payload['target_summary']['target_trade_count']}`",
        "- Production impact: `replay_only_no_live_adapter`",
        "",
        "## Gate 1-4",
        "",
        "| Window | Target trades | Target PnL | EV before | EV after | EV delta | PnL delta | DD delta |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for result in payload["results"]:
        lines.append(
            "| {label} | {trades} | ${target_pnl:,.2f} | {ev_before:.4f} | "
            "{ev_after:.4f} | {ev_delta:+.4f} | ${pnl_delta:+,.2f} | {dd_delta:+.4f} |".format(
                label=result["label"],
                trades=result["target_trade_count"],
                target_pnl=result["target_trade_pnl_usd"],
                ev_before=float(result["before"]["expected_value_score"]),
                ev_after=float(result["after"]["expected_value_score"]),
                ev_delta=float(result["comparison"]["expected_value_score_delta"]),
                pnl_delta=float(result["comparison"]["strategy_total_pnl_delta"]),
                dd_delta=float(result["comparison"]["max_drawdown_delta"]),
            )
        )
    lines.extend(
        [
            "",
            "## Rule",
            "",
            (
                "Select filed-date-safe SEC Companyfacts events where revenue and "
                "positive profit growth are both at least 15%, the ticker did not "
                "outperform SPY over the prior 20 trading days before the filing, "
                "and the first usable trading day closes green near the high. "
                "Entry is delayed to the next open after that confirmation."
            ),
            "",
            "## Gate 4 Checks",
            "",
        ]
    )
    for key, value in payload["gate4"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Production / Backtest Parity",
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "## Reproducibility",
            "",
            (
                ".\\.venv\\Scripts\\python.exe -B "
                f"quant\\experiments\\exp_20260605_022_{STEM}.py"
            ),
            "",
            "No JavaScript was used.",
        ]
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_payload() -> dict[str, Any]:
    _patch_base_module()
    base._generate_candidates = _generate_candidates
    base._write_artifact = _write_artifact
    payload = _BASE_BUILD_PAYLOAD()
    payload["gate4"]["decision"] = (
        "positive_replay_lead_not_promoted_requires_shared_adapter"
        if payload["gate4"]["passed"]
        else "rejected_broad_companyfacts_fresh_underreaction_filing_candidate_pool"
    )
    payload["preflight"] = {
        "alpha_hypothesis": (
            "Fresh SEC Companyfacts dual-growth filings with pre-filing "
            "SPY-relative underreaction and first-usable-day price confirmation "
            "may add cleaner default-off paper candidates than stale daily broad "
            "growth rows."
        ),
        "category": "entry_candidate_pool",
        "nearby_prior_experiments": [
            "exp-20260605-011",
            "exp-20260605-014",
            "exp-20260605-015",
            "exp-20260605-016",
        ],
        "single_causal_variable": CHANGED_VARIABLE,
        "success_standard": (
            "Canonical three-window before/after aggregate EV and PnL must "
            "improve, no window EV/PnL regression, max drawdown drift <= "
            f"{MAX_DRAWDOWN_WORSE}, target trades >= {MIN_TARGET_TRADES}, all "
            "three windows represented, concentration within guardrails, and "
            "any positive replay must be promoted only through a shared "
            "default-off adapter with parity tests."
        ),
        "reproducible_if_failed": True,
    }
    payload["parameters"] = {
        "paper_notional": PAPER_NOTIONAL,
        "hold_days": HOLD_DAYS,
        "min_revenue_yoy_growth": MIN_REVENUE_YOY_GROWTH,
        "min_profit_yoy_growth": MIN_PROFIT_YOY_GROWTH,
        "min_price": MIN_PRICE,
        "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
        "min_signal_close_location": MIN_SIGNAL_CLOSE_LOCATION,
        "min_signal_day_return": MIN_SIGNAL_DAY_RETURN,
        "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
        "max_prefiling_ret20_excess_spy": MAX_PREFILING_RET20_EXCESS_SPY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "daily_selection": "top_1_by_fresh_filing_underreaction_score",
        "round_trip_cost_pct": base.ROUND_TRIP_COST_PCT,
        "trade_enabled": False,
    }
    payload["next_retry_requires"] = [
        "do not retune fresh Companyfacts filing underreaction thresholds on the frozen windows",
        "collect forward paper replacement-value rows before revisiting this relation",
        "positive replay would require shared default-off adapter and parity tests before promotion",
        "use a genuinely new free-data relation if this fails",
    ]
    payload["related_files"] = [
        base._repo_rel(Path(__file__)),
        base._repo_rel(OUT_JSON),
        base._repo_rel(LOG_JSON),
        base._repo_rel(ARTIFACT_MD),
        base._repo_rel(TICKET_JSON),
        base._repo_rel(base.GROWTH_PATH),
    ]
    return payload


def _experiment_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    comparison = payload["aggregate"]["comparison"]
    actual_success = 1 if payload["gate4"]["passed"] else 0
    prediction = payload.get("prediction") or {}
    return {
        "experiment_id": EXP_ID,
        "timestamp": payload["completed_at"],
        "status": payload["gate4"]["status"],
        "lane": "alpha_search",
        "hypothesis": payload["preflight"]["alpha_hypothesis"],
        "change_summary": (
            "Tested fresh SEC Companyfacts dual-growth filings with "
            "pre-filing SPY-relative underreaction and first-usable-day price "
            "confirmation as a replay-only default-off paper candidate source."
        ),
        "change_type": "default_off_paper_candidate_pool",
        "mechanism_family": "default_off_paper_candidate_pool",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": 0,
        "nearby_prior_experiments": [
            "exp-20260605-011",
            "exp-20260605-014",
            "exp-20260605-015",
            "exp-20260605-016",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "production_visible_filed_date_companyfacts_event_timing_field",
        "component": base._repo_rel(Path(__file__)),
        "parameters": payload["parameters"],
        "before_metrics": payload["aggregate"]["before"],
        "after_metrics": payload["aggregate"]["after"],
        "delta_metrics": comparison,
        "production_impact": PRODUCTION_IMPACT,
        "decision": payload["gate4"]["decision"],
        "rejection_reason": ";".join(payload["gate4"]["failed_reasons"])
        if payload["gate4"]["failed_reasons"]
        else None,
        "next_retry_requires": payload["next_retry_requires"],
        "related_files": payload["related_files"],
        "prediction": {
            **prediction,
            "actual_success": actual_success,
            "actual_ev_delta": comparison["expected_value_score_delta"],
            "actual_pnl_delta": comparison["strategy_total_pnl_delta"],
            "brier_score": round(
                (float(prediction.get("success_probability") or 0.0) - actual_success) ** 2,
                6,
            ),
        },
        "windows": [
            {
                "label": row["label"],
                "expected_value_before": row["before"]["expected_value_score"],
                "expected_value_after": row["after"]["expected_value_score"],
                "expected_value_delta": row["comparison"]["expected_value_score_delta"],
                "strategy_total_pnl_delta": row["comparison"]["strategy_total_pnl_delta"],
                "target_trade_count": row["target_trade_count"],
                "target_trade_pnl_usd": row["target_trade_pnl_usd"],
            }
            for row in payload["results"]
        ],
        "anti_js": "No JavaScript was used.",
    }


def main() -> None:
    _patch_base_module()
    base._generate_candidates = _generate_candidates
    base._write_artifact = _write_artifact
    payload = build_payload()
    base._write_json(OUT_JSON, payload)
    base._write_json(LOG_JSON, _experiment_log_record(payload))
    base._write_json(BEFORE_JSON, payload["aggregate"]["before"])
    base._write_json(AFTER_JSON, payload["aggregate"]["after"])
    _write_artifact(payload)
    base._update_ticket(payload)
    base._update_registry(payload)
    base._append_experiment_log(_experiment_log_record(payload))
    print(
        json.dumps(
            {
                "experiment_id": EXP_ID,
                "decision": payload["gate4"]["decision"],
                "aggregate": payload["aggregate"]["comparison"],
                "target_summary": {
                    "target_trade_count": payload["target_summary"]["target_trade_count"],
                    "target_trade_pnl_usd": payload["target_summary"]["target_trade_pnl_usd"],
                    "max_single_positive_share": payload["target_summary"][
                        "max_single_positive_share"
                    ],
                    "positive_pnl_hhi": payload["target_summary"]["positive_pnl_hhi"],
                },
                "gate4_failed_reasons": payload["gate4"]["failed_reasons"],
                "anti_js": "No JavaScript was used.",
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
