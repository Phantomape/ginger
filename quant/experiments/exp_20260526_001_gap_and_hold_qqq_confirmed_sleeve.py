"""exp-20260526-001: gap-and-hold QQQ-confirmed paper sleeve.

This alpha search revisits the old gap-and-hold shadow source only under the
explicit condition allowed by exp-20260426-044: add a genuinely different,
production-visible regime conditioner and run a real current three-window
before/after replay. The single variable is an additive default-off paper
sleeve that admits at most one daily gap-and-hold candidate per signal day
when QQQ's 20-day return is above SPY's 20-day return.

Core signal generation, ranking, sizing, exits, LLM/news replay, watchlists,
and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as base
import exp_20260426_044_gap_and_hold_continuation_shadow as gap_shadow


EXPERIMENT_ID = "exp-20260526-001"
STEM = "gap_and_hold_qqq_confirmed_sleeve"
TRIAL_FAMILY = "gap_and_hold_qqq_confirmed_default_off_paper_sleeve"
CHANGED_VARIABLE = (
    "gap_and_hold_daily_top1_qqq_gt_spy20_next_open_10d_fixed_notional_sleeve_v1"
)

REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

MARKET_LOOKBACK_DAYS = 20
MIN_QQQ_MINUS_SPY_RET20 = 0.0
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30

MARKET_GATE_AUDIT: "OrderedDict[str, dict[str, Any]]" = OrderedDict()


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
    base.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    base.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    base.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    base.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    base.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    base.shadow = gap_shadow

    # The shared replay harness was first written for opening-range candidates
    # and references these names while building its initial parameter block.
    for name in (
        "MIN_PRIOR_DAY_RETURN",
        "MIN_PRIOR_DAY_RS_VS_SPY",
        "MIN_OPEN_VS_PRIOR_CLOSE",
        "MIN_CANDIDATE_RS_VS_SPY",
    ):
        if not hasattr(gap_shadow, name):
            setattr(gap_shadow, name, None)


def _close_return_to_date(
    snapshot: dict[str, list[dict[str, Any]]],
    ticker: str,
    date: str,
    lookback_days: int,
) -> float | None:
    rows = gap_shadow._series(snapshot, ticker)
    idx = gap_shadow._row_index(rows).get(date)
    if idx is None or idx - lookback_days < 0:
        return None
    return gap_shadow._return_from_closes(rows, idx - lookback_days, idx)


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> list[dict[str, Any]]:
    entries_by_date = gap_shadow._baseline_entries(before_result)
    dates = [
        date
        for date in gap_shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= date <= str(cfg["end"])
    ]
    raw_candidates: list[dict[str, Any]] = []
    missing_market_context = 0
    market_rejected = 0
    candidates: list[dict[str, Any]] = []

    for ticker in sorted(set(universe).intersection(snapshot)):
        if ticker in gap_shadow.EXCLUDED_TICKERS:
            continue
        for row in gap_shadow._candidate_rows(snapshot, ticker, dates):
            raw_candidates.append(row)
            qqq_ret20 = _close_return_to_date(
                snapshot, "QQQ", row["date"], MARKET_LOOKBACK_DAYS
            )
            spy_ret20 = _close_return_to_date(
                snapshot, "SPY", row["date"], MARKET_LOOKBACK_DAYS
            )
            if qqq_ret20 is None or spy_ret20 is None:
                missing_market_context += 1
                continue
            qqq_minus_spy = qqq_ret20 - spy_ret20
            if qqq_minus_spy <= MIN_QQQ_MINUS_SPY_RET20:
                market_rejected += 1
                continue

            ab_entries = entries_by_date.get(row["date"], [])
            row["qqq_ret20"] = base._round(qqq_ret20, 6)
            row["spy_ret20"] = base._round(spy_ret20, 6)
            row["qqq_minus_spy_ret20"] = base._round(qqq_minus_spy, 6)
            row["market_confirmation"] = "qqq_ret20_gt_spy_ret20"
            row["known_at"] = f"{row['date']} close"
            row["trade_enabled"] = False
            row["alters_orders"] = False
            row["same_day_ab_entry_count"] = len(ab_entries)
            row["same_day_ab_overlap"] = bool(ab_entries)
            row["same_ticker_ab_overlap"] = any(
                trade.get("ticker") == row["ticker"] for trade in ab_entries
            )
            candidates.append(row)

    label = str(cfg.get("label") or "")
    if not label:
        label = next(
            (
                window_label
                for window_label, window_cfg in base.WINDOWS.items()
                if window_cfg is cfg
            ),
            str(cfg.get("start")),
        )
    MARKET_GATE_AUDIT[label] = {
        "raw_gap_and_hold_candidates": len(raw_candidates),
        "missing_market_context": missing_market_context,
        "qqq_not_stronger_than_spy_rejected": market_rejected,
        "qqq_confirmed_candidates": len(candidates),
        "candidate_days_after_confirmation": len({row["date"] for row in candidates}),
        "market_rule": "QQQ 20d close-to-close return > SPY 20d close-to-close return",
    }

    candidates.sort(
        key=lambda row: (
            row["date"],
            -row["rs_vs_spy"],
            -row["close_location"],
            -row["gap_up"],
            -row["dollar_volume"],
            row["ticker"],
        )
    )
    return candidates


def _decision_from_gate(payload: dict[str, Any]) -> str:
    return (
        "promising_replay_only_gap_and_hold_qqq_confirmed_sleeve"
        if payload["gate4"]["passed"]
        else "rejected_gap_and_hold_qqq_confirmed_sleeve"
    )


def _update_payload(payload: dict[str, Any]) -> dict[str, Any]:
    decision = _decision_from_gate(payload)
    payload["status"] = decision
    payload["decision"] = decision
    payload["hypothesis"] = (
        "A daily gap-and-hold continuation candidate may add candidate-pool "
        "alpha only when the growth tape confirms risk appetite. The test uses "
        "free daily OHLCV and requires QQQ's 20-day return to exceed SPY's "
        "20-day return before admitting the top ranked gap-and-hold candidate "
        "as default-off paper."
    )
    payload["change_type"] = "gap_and_hold_qqq_confirmed_default_off_paper_sleeve"
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["trial_family"] = TRIAL_FAMILY
    payload["prior_trial_count"] = 1
    payload["nearby_prior_experiments"] = [
        "exp-20260426-044",
        "exp-20260428-022",
        "exp-20260508-014",
        "exp-20260525-011",
        "exp-20260525-012",
        "exp-20260525-901",
        "exp-20260525-022",
        "exp-20260525-037",
    ]
    payload["multiple_testing_risk_bucket"] = "medium_high"
    payload["new_evidence_type"] = (
        "orthogonal_production_visible_qqq_vs_spy_regime_conditioner_on_"
        "gap_and_hold_source_with_current_three_window_fixed_notional_replay"
    )
    payload["parameters"]["shadow_entry_filters"] = {
        "gap_up_min": gap_shadow.MIN_GAP_UP,
        "close_vs_prev_close_min": gap_shadow.MIN_CLOSE_VS_PREV_CLOSE,
        "close_must_be_above_open": True,
        "close_location_min": gap_shadow.MIN_CLOSE_LOCATION,
        "rs_vs_spy_min": gap_shadow.MIN_RS_VS_SPY,
        "min_candidate_day_dollar_volume": gap_shadow.MIN_DOLLAR_VOLUME,
    }
    payload["parameters"]["market_confirmation"] = {
        "source": "free daily OHLCV",
        "lookback_trading_days": MARKET_LOOKBACK_DAYS,
        "rule": "QQQ close-to-close return > SPY close-to-close return",
        "min_qqq_minus_spy_ret20": MIN_QQQ_MINUS_SPY_RET20,
        "known_at": "signal-date close",
        "entry_timing": "next available open",
    }
    payload["parameters"]["selection_rank"] = [
        "signal_date",
        "rs_vs_spy desc",
        "close_location desc",
        "gap_up desc",
        "dollar_volume desc",
        "ticker asc",
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
            "entry / candidate_pool: gap-and-hold continuation may have "
            "better replacement value when QQQ confirms a growth-led tape. "
            "This follows the playbook's default-off paper candidate-pool "
            "direction and uses a new production-visible field, not an LLM "
            "soft-ranking field or a mined threshold scalar."
        ),
        "2_history_check": {
            "exp-20260426-044": (
                "Observed-only gap-and-hold audit was mixed and explicitly "
                "blocked nearby threshold retunes; it allowed a retry only "
                "with a genuinely different event/sector/regime conditioner "
                "and real slot replay. QQQ>SPY20 is the distinct regime "
                "conditioner tested here."
            ),
            "exp-20260525-011/012/901": (
                "Opening-range sleeves were rejected after 3-window replay; "
                "this uses daily gap-and-hold, not opening-range continuation."
            ),
            "exp-20260525-022/037": (
                "VCP+QQQ was the strongest recent lead, but memory/playbook "
                "now warn against further frozen-sample VCP/topN retunes."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Same three docs/backtesting.md windows; positive aggregate EV/PnL; "
            "3/3 EV-improved windows; no PnL-regressed window; >=20 paper "
            "trades across all 3 windows; drawdown drift <=0.5pp; survival "
            ">=5%; concentration inside guardrails."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260526_001_gap_and_hold_qqq_confirmed_sleeve.py"
        ),
    }
    payload["gate2"]["runtime_fields"] = [
        "canonical OHLCV Date/Open/High/Low/Close/Volume rows",
        "SPY OHLCV rows for same-window relative strength",
        "QQQ and SPY 20-day close-to-close returns known at signal-date close",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["gate2"]["note"] = (
        "The sleeve uses same-day daily OHLCV plus QQQ/SPY closes available "
        "at the signal-date close, then enters only at the next open. It does "
        "not ask LLM or production to infer hidden fields."
    )
    payload["market_gate_audit"] = MARKET_GATE_AUDIT
    payload["why_not_other_changes"] = (
        "Skipped LLM soft-ranking, SEC call semantics, and expectation-residual "
        "leaders because recent logs show sparse or unusable data. Skipped VCP, "
        "state-surface, broad-market scalar, opening-range, sector-leadership, "
        "inside-day, and AI-optical threshold retreads because the latest memory "
        "and experiment log mark those families as accepted-but-do-not-retune or "
        "freshly rejected. This tests a distinct free-OHLCV candidate source "
        "with an orthogonal regime conditioner."
    )
    payload["interpretation"] = (
        "The gap-and-hold QQQ-confirmed sleeve cleared Gate 4 as a replay-only "
        "lead, but no production/shared policy was promoted."
        if payload["gate4"]["passed"]
        else (
            "The gap-and-hold QQQ-confirmed sleeve did not clear Gate 4. Do "
            "not promote or retry nearby gap-and-hold thresholds on these "
            "windows without forward paper rows or a materially different "
            "event/sector/regime evidence source."
        )
    )
    payload["rejection_reason"] = (
        None if payload["gate4"]["passed"] else payload.get("rejection_reason")
    )
    payload["next_evidence_needed"] = (
        "If revisited, use forward paper outcomes or a materially different "
        "free data edge, such as verified event/sector context. Do not just "
        "retune gap, close-location, QQQ/SPY lookback, or topN thresholds on "
        "the frozen windows."
    )
    payload["production_impact"]["promotion_requirement"] = (
        "A retained result would still require a shared default-off paper "
        "adapter, daily report exposure, forward replacement-value ledger, and "
        "parity tests before any live/default behavior changes."
    )
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | QQQ-confirmed | Raw candidates |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        market_audit = payload["market_gate_audit"].get(label, {})
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | "
            "${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | "
            "{trades} | {confirmed} | {raw} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                confirmed=market_audit.get("qqq_confirmed_candidates"),
                raw=market_audit.get("raw_gap_and_hold_candidates"),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Gap-and-Hold QQQ-Confirmed Paper Sleeve",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            (
                "Single variable: a default-off paper sleeve admits at most one "
                "daily gap-and-hold candidate per day when QQQ's 20-day return "
                "is greater than SPY's 20-day return, enters at next open, and "
                "exits after ten trading days."
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
            f"- target trades: `{payload['target_trade_summary']['total_trade_count']}` across `{len(payload['target_trade_summary']['windows_with_target_trades'])}` windows",
            f"- max single positive share: `{payload['target_trade_summary']['max_single_positive_pnl_share']}`",
            f"- positive PnL HHI: `{payload['target_trade_summary']['positive_pnl_hhi']}`",
            "",
            "## Market Gate Audit",
            "",
            "```json",
            json.dumps(payload["market_gate_audit"], indent=2, sort_keys=True),
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


def _persist(payload: dict[str, Any]) -> None:
    base._write_json(OUT_JSON, payload)
    base._write_json(LOG_JSON, payload)
    base._write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Gap-and-hold QQQ-confirmed paper sleeve",
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": base._repo_rel(ARTIFACT_MD),
            "json": base._repo_rel(OUT_JSON),
            "summary": payload["interpretation"],
        },
    )
    base._write_text(ARTIFACT_MD, _build_report(payload))
    base._upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    _configure_base_module()
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
                    "market_gate_audit": payload["market_gate_audit"],
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
