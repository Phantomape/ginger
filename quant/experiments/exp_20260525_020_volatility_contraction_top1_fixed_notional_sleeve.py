"""exp-20260525-020: volatility-contraction top-1 fixed-notional sleeve.

This alpha search retests the old observed-only volatility-contraction
breakout source with the current docs/backtesting.md three-window protocol.
The single variable is an additive default-off paper sleeve that admits at
most one volatility-contraction breakout candidate per signal day, enters at
the next available open, and exits after ten trading days at the close.

Core signal generation, ranking, sizing, exits, LLM/news replay, watchlists,
and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as base
import exp_20260426_volatility_contraction_breakout_shadow as volatility_shadow


EXPERIMENT_ID = "exp-20260525-020"
STEM = "volatility_contraction_top1_fixed_notional_sleeve"
TRIAL_FAMILY = "volatility_contraction_breakout_default_off_paper_sleeve"
CHANGED_VARIABLE = "volatility_contraction_top1_next_open_10d_fixed_notional_sleeve_v1"

REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30


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
    base.shadow = volatility_shadow

    # The shared opening-range harness references these names while building
    # its raw parameter block. They are overwritten with the volatility
    # contraction definition before persistence.
    for name in (
        "MIN_PRIOR_DAY_RETURN",
        "MIN_PRIOR_DAY_RS_VS_SPY",
        "MIN_OPEN_VS_PRIOR_CLOSE",
    ):
        if not hasattr(volatility_shadow, name):
            setattr(volatility_shadow, name, None)


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> list[dict[str, Any]]:
    entries_by_date = volatility_shadow._baseline_entries(before_result)
    dates = [
        date
        for date in volatility_shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= date <= str(cfg["end"])
    ]
    candidates: list[dict[str, Any]] = []
    for ticker in sorted(set(universe).intersection(snapshot)):
        if ticker in volatility_shadow.EXCLUDED_TICKERS:
            continue
        for row in volatility_shadow._candidate_rows(snapshot, ticker, dates):
            ab_entries = entries_by_date.get(row["date"], [])
            row["same_day_ab_entry_count"] = len(ab_entries)
            row["same_day_ab_overlap"] = bool(ab_entries)
            row["same_ticker_ab_overlap"] = any(
                trade.get("ticker") == row["ticker"] for trade in ab_entries
            )
            candidates.append(row)
    candidates.sort(
        key=lambda row: (
            row["date"],
            row["short_to_long_atr_ratio"],
            -row["candidate_day_rs_vs_spy"],
            -row["dollar_volume"],
            row["ticker"],
        )
    )
    return candidates


def _decision_from_gate(payload: dict[str, Any]) -> str:
    return (
        "promising_replay_only_volatility_contraction_top1_fixed_notional_sleeve"
        if payload["gate4"]["passed"]
        else "rejected_volatility_contraction_top1_fixed_notional_sleeve"
    )


def _update_payload(payload: dict[str, Any]) -> dict[str, Any]:
    decision = _decision_from_gate(payload)
    payload["status"] = decision
    payload["decision"] = decision
    payload["hypothesis"] = (
        "A volatility-contraction breakout candidate may add candidate-pool "
        "alpha because compressed ranges followed by a close through the prior "
        "20-day high can signal institutional accumulation. A top-1 fixed-"
        "notional default-off paper sleeve tests the source without adding "
        "noisy tickers or changing core production behavior."
    )
    payload["change_type"] = "volatility_contraction_breakout_default_off_paper_sleeve"
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["trial_family"] = TRIAL_FAMILY
    payload["prior_trial_count"] = 1
    payload["nearby_prior_experiments"] = ["exp-20260426-045"]
    payload["multiple_testing_risk_bucket"] = "low"
    payload["new_evidence_type"] = (
        "current_three_window_next_open_slippage_adjusted_fixed_notional_"
        "paper_sleeve_replay"
    )
    payload["parameters"]["shadow_entry_filters"] = {
        "short_atr_days": volatility_shadow.SHORT_ATR_DAYS,
        "long_atr_days": volatility_shadow.LONG_ATR_DAYS,
        "max_short_to_long_atr_ratio": volatility_shadow.MAX_SHORT_TO_LONG_ATR_RATIO,
        "breakout_close_above_prior_n_day_high": volatility_shadow.BREAKOUT_LOOKBACK_DAYS,
        "close_above_n_day_moving_average": volatility_shadow.MA_DAYS,
        "candidate_day_rs_vs_spy_min": volatility_shadow.MIN_CANDIDATE_RS_VS_SPY,
        "min_candidate_day_dollar_volume": volatility_shadow.MIN_DOLLAR_VOLUME,
    }
    payload["parameters"]["selection_rank"] = [
        "signal_date",
        "short_to_long_atr_ratio asc",
        "candidate_day_rs_vs_spy desc",
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
            "entry / candidate_pool: volatility-contraction breakouts may "
            "surface higher-information continuation candidates using only "
            "free daily OHLCV."
        ),
        "2_history_check": {
            "exp-20260426-045": (
                "Observed-only volatility-contraction breakout audit; it did "
                "not run the current canonical 3-window fixed-notional before/"
                "after replay."
            )
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
            "exp_20260525_020_volatility_contraction_top1_fixed_notional_sleeve.py"
        ),
    }
    payload["why_not_other_changes"] = (
        "Skipped expectation-residual leadership because today's attribution "
        "run found zero positive-expectation residual-leader candidates and "
        "insufficient usable sample. Skipped LLM soft-ranking, SEC call "
        "scalars, Space, broad-market, opening-range, sector-leadership, and "
        "AI-infra/compute retreads because the latest logs show data gaps, "
        "fresh rejection, or anti-repeat constraints. This tests a distinct "
        "free-OHLCV candidate source."
    )
    payload["interpretation"] = (
        "The volatility-contraction top-1 paper sleeve cleared Gate 4 as a "
        "replay-only lead, but no production/shared policy was promoted."
        if payload["gate4"]["passed"]
        else (
            "The volatility-contraction top-1 paper sleeve did not clear Gate 4. "
            "Do not promote or retry nearby volatility-contraction thresholds "
            "without forward paper rows or a materially different production-"
            "visible discriminator."
        )
    )
    payload["next_evidence_needed"] = (
        "If revisited, use forward paper outcomes or an orthogonal event/source "
        "confirmation field; do not just retune ATR-compression or breakout "
        "thresholds on the frozen windows."
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | "
            "${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | "
            "{trades} | {raw} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                raw=payload["raw_candidate_counts"][label],
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Volatility-Contraction Top-1 Fixed-Notional Sleeve",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            (
                "Single variable: a default-off paper sleeve admits at most one "
                "volatility-contraction breakout candidate per day, enters at "
                "next open, and exits after ten trading days."
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
            "title": "Volatility-contraction top-1 fixed-notional sleeve",
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
