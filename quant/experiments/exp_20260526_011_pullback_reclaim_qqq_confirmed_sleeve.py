"""exp-20260526-011: QQQ-confirmed pullback-reclaim paper sleeve.

This alpha search retests the old pullback-reclaim shadow source under the
current docs/backtesting.md three-window before/after protocol. The single
variable is a default-off paper sleeve that admits at most one liquid
pullback-reclaim continuation candidate per signal day when QQQ 20-day
momentum leads SPY, enters at the next open, and exits after ten trading days.

Core signal generation, ranking, sizing, exits, LLM/news replay, watchlists,
and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
LEGACY_DIR = EXPERIMENT_DIR / "legacy"
for path in (QUANT_DIR, EXPERIMENT_DIR, LEGACY_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260426_pullback_reclaim_continuation_shadow as pullback_shadow  # noqa: E402
import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as base  # noqa: E402


EXPERIMENT_ID = "exp-20260526-011"
STEM = "pullback_reclaim_qqq_confirmed_sleeve"
TRIAL_FAMILY = "pullback_reclaim_qqq_confirmed_default_off_paper_sleeve"
CHANGED_VARIABLE = (
    "pullback_reclaim_daily_top1_qqq_gt_spy20_next_open_10d_"
    "fixed_notional_sleeve_v1"
)
RULE_VERSION = "pullback_reclaim_qqq_confirmed_v1"
MARKET_CONFIRMATION_RULE_VERSION = "qqq_gt_spy20_close_to_close_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

MARKET_CONFIRM_LOOKBACK_DAYS = 20
MIN_DOLLAR_VOLUME = 40_000_000.0
MAX_PAPER_TRADES_PER_DAY = 1
MIN_TARGET_TRADES = 30
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30

EXCLUDED_TICKERS = {
    "ARKX",
    "GLD",
    "IAU",
    "IEF",
    "IWM",
    "QQQ",
    "SLV",
    "SPY",
    "TLT",
    "UFO",
    "UUP",
    "USO",
    "XLE",
    "XLP",
    "XLU",
    "XLV",
}

PULLBACK_AUDIT: "OrderedDict[str, dict[str, Any]]" = OrderedDict()


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
    base.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    base.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    base.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    base.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    base.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    base.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    base.shadow = pullback_shadow

    for name in (
        "MIN_PRIOR_DAY_RETURN",
        "MIN_PRIOR_DAY_RS_VS_SPY",
        "MIN_OPEN_VS_PRIOR_CLOSE",
    ):
        if not hasattr(pullback_shadow, name):
            setattr(pullback_shadow, name, None)


def _close_return(rows: list[dict[str, Any]], start_idx: int, end_idx: int) -> float | None:
    if start_idx < 0 or end_idx >= len(rows):
        return None
    start = pullback_shadow._value(rows[start_idx], "Close")
    end = pullback_shadow._value(rows[end_idx], "Close")
    if not start or end is None:
        return None
    return (end / start) - 1.0


def _market_context(
    snapshot: dict[str, list[dict[str, Any]]],
    date: str,
) -> dict[str, Any]:
    qqq_rows = pullback_shadow._series(snapshot, "QQQ")
    spy_rows = pullback_shadow._series(snapshot, "SPY")
    qqq_idx = pullback_shadow._row_index(qqq_rows).get(date)
    spy_idx = pullback_shadow._row_index(spy_rows).get(date)
    qqq_ret20 = (
        _close_return(qqq_rows, qqq_idx - MARKET_CONFIRM_LOOKBACK_DAYS, qqq_idx)
        if qqq_idx is not None
        else None
    )
    spy_ret20 = (
        _close_return(spy_rows, spy_idx - MARKET_CONFIRM_LOOKBACK_DAYS, spy_idx)
        if spy_idx is not None
        else None
    )
    qqq_gt_spy = (
        qqq_ret20 is not None and spy_ret20 is not None and qqq_ret20 > spy_ret20
    )
    return {
        "qqq_gt_spy20": qqq_gt_spy,
        "qqq_ret20_on_signal": base._round(qqq_ret20, 6),
        "spy_ret20_on_signal": base._round(spy_ret20, 6),
        "qqq_minus_spy_ret20": (
            base._round(qqq_ret20 - spy_ret20, 6)
            if qqq_ret20 is not None and spy_ret20 is not None
            else None
        ),
        "market_confirmation_rule_version": MARKET_CONFIRMATION_RULE_VERSION,
        "known_at": "after_signal_date_close_before_next_open_paper_entry",
    }


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> list[dict[str, Any]]:
    entries_by_date = pullback_shadow._baseline_entries(before_result)
    dates = [
        date
        for date in pullback_shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= date <= str(cfg["end"])
    ]
    candidates: list[dict[str, Any]] = []
    raw_pullback_hits = 0
    source_tickers = 0
    raw_ticker_days = 0

    for ticker in sorted(set(universe).intersection(snapshot).difference(EXCLUDED_TICKERS)):
        rows = pullback_shadow._series(snapshot, ticker)
        if not rows:
            continue
        source_tickers += 1
        date_index = pullback_shadow._row_index(rows)
        raw_rows = pullback_shadow._candidate_rows(snapshot, ticker, dates)
        raw_pullback_hits += len(raw_rows)
        raw_ticker_days += sum(1 for date in dates if date in date_index)
        for row in raw_rows:
            if float(row.get("dollar_volume") or 0.0) < MIN_DOLLAR_VOLUME:
                continue
            market = _market_context(snapshot, str(row.get("date") or ""))
            if market["qqq_gt_spy20"] is not True:
                continue
            ab_entries = entries_by_date.get(row["date"], [])
            row["same_day_ab_entry_count"] = len(ab_entries)
            row["same_day_ab_overlap"] = bool(ab_entries)
            row["same_ticker_ab_overlap"] = any(
                trade.get("ticker") == row["ticker"] for trade in ab_entries
            )
            row["source_universe"] = "current_production_universe_ohlcv"
            row["strategy"] = "pullback_reclaim_qqq_confirmed"
            row["pullback_reclaim_rule_version"] = RULE_VERSION
            row["trade_enabled"] = False
            row["alters_orders"] = False
            row.update(market)
            score = (
                max(float(row.get("candidate_day_rs_vs_spy") or 0.0), 0.0) * 6.0
                + max(float(row.get("pct_above_10d_ma") or 0.0), 0.0) * 2.0
                + max(float(row.get("pct_above_50d_ma") or 0.0), 0.0)
                + abs(float(row.get("pullback_from_20d_high") or 0.0))
                + max(float(market.get("qqq_minus_spy_ret20") or 0.0), 0.0)
            )
            row["pullback_reclaim_score"] = base._round(score, 6)
            candidates.append(row)

    label = next(
        (
            window_label
            for window_label, window_cfg in base.WINDOWS.items()
            if window_cfg is cfg
        ),
        str(cfg.get("start")),
    )
    PULLBACK_AUDIT[label] = {
        "raw_ticker_days_considered": raw_ticker_days,
        "source_tickers_considered": source_tickers,
        "raw_pullback_reclaim_hits": raw_pullback_hits,
        "qqq_confirmed_liquid_pullback_reclaim_candidates": len(candidates),
        "candidate_days": len({row["date"] for row in candidates}),
        "unique_candidate_tickers": len({row["ticker"] for row in candidates}),
        "rule_version": RULE_VERSION,
        "market_confirmation_rule_version": MARKET_CONFIRMATION_RULE_VERSION,
    }
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["pullback_reclaim_score"]),
            -float(row["candidate_day_rs_vs_spy"]),
            float(row["pullback_from_20d_high"]),
            -float(row["dollar_volume"]),
            row["ticker"],
        )
    )
    return candidates


def _decision_from_gate(payload: dict[str, Any]) -> str:
    return (
        "promising_replay_only_pullback_reclaim_qqq_confirmed_sleeve"
        if payload["gate4"]["passed"]
        else "rejected_pullback_reclaim_qqq_confirmed_sleeve"
    )


def _update_payload(payload: dict[str, Any]) -> dict[str, Any]:
    decision = _decision_from_gate(payload)
    payload["status"] = decision
    payload["decision"] = decision
    payload["hypothesis"] = (
        "Multi-day pullback-reclaim continuation candidates may add default-off "
        "paper alpha when the broader growth tape confirms via QQQ 20-day "
        "momentum above SPY. The no-displacement paper boundary tests whether "
        "the old shadow source failed because of core slot/capital competition "
        "rather than lack of standalone edge."
    )
    payload["change_type"] = "pullback_reclaim_qqq_confirmed_default_off_paper_sleeve"
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["trial_family"] = TRIAL_FAMILY
    payload["prior_trial_count"] = 2
    payload["mechanism_family"] = "free_ohlcv_candidate_pool_reclaim_continuation"
    payload["trial_variant_id"] = "pullback_reclaim_top1_qqq_confirmed_v1"
    payload["nearby_prior_experiments"] = [
        "exp-20260426-047",
        "exp-20260426-051",
        "exp-20260526-001",
        "exp-20260526-002",
        "exp-20260526-003",
        "exp-20260526-004",
        "exp-20260526-005",
        "exp-20260526-009",
        "exp-20260526-010",
    ]
    payload["multiple_testing_risk_bucket"] = "moderate"
    payload["new_evidence_type"] = (
        "current_three_window_next_open_slippage_adjusted_pullback_reclaim_"
        "qqq_confirmed_paper_sleeve_replay"
    )
    payload["parameters"]["source_universe"] = (
        "current get_universe() production universe names with canonical OHLCV snapshots"
    )
    payload["parameters"]["excluded_tickers"] = sorted(EXCLUDED_TICKERS)
    payload["parameters"]["shadow_entry_filters"] = {
        "base_source": "legacy pullback-reclaim continuation shadow definition",
        "fast_ma_days": pullback_shadow.FAST_MA_DAYS,
        "mid_ma_days": pullback_shadow.MID_MA_DAYS,
        "slow_ma_days": pullback_shadow.SLOW_MA_DAYS,
        "pullback_lookback_days": pullback_shadow.PULLBACK_LOOKBACK_DAYS,
        "recent_high_lookback_days": pullback_shadow.RECENT_HIGH_LOOKBACK_DAYS,
        "pullback_from_recent_high_range": [
            pullback_shadow.MIN_PULLBACK_FROM_HIGH,
            pullback_shadow.MAX_PULLBACK_FROM_HIGH,
        ],
        "min_candidate_rs_vs_spy": pullback_shadow.MIN_CANDIDATE_RS_VS_SPY,
        "min_candidate_day_dollar_volume": MIN_DOLLAR_VOLUME,
        "market_confirmation": "QQQ 20d close-to-close return > SPY 20d return",
        "market_confirmation_lookback_days": MARKET_CONFIRM_LOOKBACK_DAYS,
    }
    payload["parameters"]["selection_rank"] = [
        "signal_date",
        "pullback_reclaim_score desc",
        "candidate_day_rs_vs_spy desc",
        "pullback_from_20d_high asc",
        "dollar_volume desc",
        "ticker asc",
    ]
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
            "entry / candidate_pool: QQQ-confirmed pullback reclaim may expand "
            "the candidate pool using only free OHLCV while avoiding data-limited "
            "LLM soft-ranking."
        ),
        "2_history_check": {
            "exp-20260426-047": (
                "Observed-only pullback-reclaim shadow had positive 10d forward "
                "returns in all windows, but no current fixed-notional before/"
                "after replay."
            ),
            "exp-20260426-051": (
                "Production-path pullback-reclaim replay regressed because it "
                "competed for core slots and capital; this run is no-displacement "
                "default-off paper only."
            ),
            "exp-20260526-001_to_010": (
                "Recent free-OHLCV gap, smooth, undercut, long-base, pocket-pivot, "
                "and sector-leadership sources are rejected or anti-repeat "
                "constrained; this uses the older pullback-reclaim source with a "
                "fixed QQQ/SPY market confirmation, not their thresholds."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Same three docs/backtesting.md windows; positive aggregate EV/PnL; "
            "3/3 EV-improved windows; no PnL-regressed window; >=30 paper trades "
            "across all 3 windows; drawdown drift <=0.5pp; survival >=5%; "
            "concentration inside guardrails."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260526_011_pullback_reclaim_qqq_confirmed_sleeve.py"
        ),
    }
    payload["gate2"]["runtime_fields"] = [
        "canonical OHLCV Date/Open/High/Low/Close/Volume rows",
        "candidate ticker trailing 10/20/50/100-day OHLCV features",
        "SPY OHLCV Close rows for signal-day relative strength",
        "QQQ and SPY OHLCV Close rows for 20-day market confirmation",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["gate2"]["note"] = (
        "All candidate fields are derived from trailing or same-day OHLCV known "
        "after the signal-date close. Paper entry occurs only at the next open."
    )
    payload["gate3"]["candidate_pool_changed"] = True
    payload["pullback_reclaim_audit"] = PULLBACK_AUDIT
    payload["why_not_other_changes"] = (
        "Skipped LLM soft-ranking and expectation-revision alpha because current "
        "records remain PIT/sample-limited. Skipped VCP threshold/top-N/profile "
        "retunes, state-surface/broad-market scalar work, Space/AI optical fixed "
        "pools, and the just-rejected gap/smooth/undercut/long-base/pocket/sector "
        "sources. This tests a distinct no-displacement pullback-reclaim source "
        "with one production-visible market confirmation."
    )
    payload["interpretation"] = (
        "The QQQ-confirmed pullback-reclaim sleeve cleared Gate 4 as a replay-only "
        "lead, but no production/shared policy was promoted."
        if payload["gate4"]["passed"]
        else (
            "The QQQ-confirmed pullback-reclaim sleeve did not clear Gate 4. Do "
            "not promote or retry nearby pullback depth, reclaim, or QQQ/SPY "
            "thresholds on these frozen windows without forward paper rows or a "
            "materially different source-quality field."
        )
    )
    payload["next_evidence_needed"] = (
        "If revisited, require forward paper rows or an orthogonal production-"
        "visible catalyst/source field; do not just retune pullback depth, moving "
        "average, or market-confirmation thresholds on the frozen sample."
    )
    payload["production_impact"]["promotion_requirement"] = (
        "A retained result would still require a shared default-off paper adapter, "
        "daily report exposure, forward replacement-value ledger, and parity tests "
        "before any live/default behavior changes."
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Candidates | Days | Tickers |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["pullback_reclaim_audit"].get(label, {})
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | "
            "${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | "
            "{trades} | {candidates} | {days} | {tickers} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                candidates=audit.get("qqq_confirmed_liquid_pullback_reclaim_candidates"),
                days=audit.get("candidate_days"),
                tickers=audit.get("unique_candidate_tickers"),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} QQQ-Confirmed Pullback-Reclaim Paper Sleeve",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            (
                "Single variable: a default-off paper sleeve admits at most one "
                "QQQ-confirmed liquid pullback-reclaim candidate per day, enters "
                "at next open, and exits after ten trading days."
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
            "## Pattern Audit",
            "",
            "```json",
            json.dumps(payload["pullback_reclaim_audit"], indent=2, sort_keys=True),
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
            "title": "QQQ-confirmed pullback-reclaim paper sleeve",
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
                    "pullback_reclaim_audit": payload["pullback_reclaim_audit"],
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
