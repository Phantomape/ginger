"""exp-20260526-002: smooth momentum path paper sleeve.

This alpha search tests one new free-OHLCV candidate-pool source: liquid
production-universe leaders with strong 60-day relative strength, positive
20-day trend, and a smooth recent daily-return path without a single-day
euphoric jump. The route is default-off paper only: at most one candidate per
signal day, next-open paper entry, and ten-trading-day close exit.

Core signal generation, ranking, sizing, exits, LLM/news replay, watchlists,
and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
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

import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as base  # noqa: E402
import exp_20260426_041_opening_range_continuation_shadow as ohlcv_shadow  # noqa: E402


EXPERIMENT_ID = "exp-20260526-002"
STEM = "smooth_momentum_path_sleeve"
TRIAL_FAMILY = "smooth_momentum_path_default_off_paper_sleeve"
CHANGED_VARIABLE = (
    "smooth_momentum_path_daily_top1_next_open_10d_fixed_notional_sleeve_v1"
)
RULE_VERSION = "smooth_momentum_path_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

LOOKBACK_RS = 60
LOOKBACK_PATH = 20
LOOKBACK_SMA = 50
LOOKBACK_PULL = 5
MIN_RET60 = 0.12
MIN_RET60_EXCESS_SPY = 0.05
MIN_RET20 = 0.025
MIN_RET20_EXCESS_SPY = 0.005
MIN_RET5 = -0.015
MAX_RET5 = 0.04
MIN_POSITIVE_DAY_RATIO_20 = 0.50
MAX_POSITIVE_DAY_RATIO_20 = 0.75
MAX_DAILY_RETURN_20 = 0.075
MAX_ABS_DAILY_RETURN_20 = 0.095
MAX_REALIZED_VOL_20 = 0.055
MIN_AVG_DOLLAR_VOLUME_20 = 25_000_000.0
MAX_PAPER_TRADES_PER_DAY = 1
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30

PATH_AUDIT: "OrderedDict[str, dict[str, Any]]" = OrderedDict()


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
    base.shadow = ohlcv_shadow

    # The shared fixed-notional harness was first written for opening-range
    # candidates and reads these names before this script overwrites the
    # parameter block with the smooth-path definition.
    for name in (
        "MIN_PRIOR_DAY_RETURN",
        "MIN_PRIOR_DAY_RS_VS_SPY",
        "MIN_OPEN_VS_PRIOR_CLOSE",
        "MIN_CANDIDATE_RS_VS_SPY",
        "MIN_DOLLAR_VOLUME",
    ):
        if not hasattr(ohlcv_shadow, name):
            setattr(ohlcv_shadow, name, None)


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _std(values: list[float]) -> float | None:
    if not values:
        return None
    avg = sum(values) / len(values)
    return math.sqrt(sum((value - avg) ** 2 for value in values) / len(values))


def _close_return(rows: list[dict[str, Any]], start_idx: int, end_idx: int) -> float | None:
    if start_idx < 0 or end_idx >= len(rows):
        return None
    start = ohlcv_shadow._value(rows[start_idx], "Close")
    end = ohlcv_shadow._value(rows[end_idx], "Close")
    if not start or not end:
        return None
    return (end / start) - 1.0


def _daily_returns(rows: list[dict[str, Any]], start_idx: int, end_idx: int) -> list[float] | None:
    if start_idx < 1 or end_idx >= len(rows):
        return None
    values: list[float] = []
    for idx in range(start_idx, end_idx + 1):
        prev_close = ohlcv_shadow._value(rows[idx - 1], "Close")
        close = ohlcv_shadow._value(rows[idx], "Close")
        if not prev_close or not close:
            return None
        values.append((close / prev_close) - 1.0)
    return values


def _sma(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx - lookback + 1 < 0:
        return None
    closes = [
        ohlcv_shadow._value(rows[row_idx], "Close")
        for row_idx in range(idx - lookback + 1, idx + 1)
    ]
    if any(value is None for value in closes):
        return None
    return float(sum(closes)) / lookback


def _avg_dollar_volume(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx - lookback + 1 < 0:
        return None
    values: list[float] = []
    for row_idx in range(idx - lookback + 1, idx + 1):
        close = ohlcv_shadow._value(rows[row_idx], "Close")
        volume = ohlcv_shadow._value(rows[row_idx], "Volume")
        if close is None or volume is None:
            return None
        values.append(close * volume)
    return sum(values) / len(values)


def _smooth_momentum_candidate(
    snapshot: dict[str, list[dict[str, Any]]],
    ticker: str,
    rows: list[dict[str, Any]],
    idx: int,
) -> dict[str, Any] | None:
    date = ohlcv_shadow._date(rows[idx])
    spy_rows = ohlcv_shadow._series(snapshot, "SPY")
    spy_idx = ohlcv_shadow._row_index(spy_rows).get(date)
    if spy_idx is None:
        return None

    close = ohlcv_shadow._value(rows[idx], "Close")
    if close is None:
        return None
    sma50 = _sma(rows, idx, LOOKBACK_SMA)
    ret60 = _close_return(rows, idx - LOOKBACK_RS, idx)
    ret20 = _close_return(rows, idx - LOOKBACK_PATH, idx)
    ret5 = _close_return(rows, idx - LOOKBACK_PULL, idx)
    spy_ret60 = _close_return(spy_rows, spy_idx - LOOKBACK_RS, spy_idx)
    spy_ret20 = _close_return(spy_rows, spy_idx - LOOKBACK_PATH, spy_idx)
    daily20 = _daily_returns(rows, idx - LOOKBACK_PATH + 1, idx)
    avg_dollar_volume20 = _avg_dollar_volume(rows, idx, LOOKBACK_PATH)
    if (
        sma50 is None
        or ret60 is None
        or ret20 is None
        or ret5 is None
        or spy_ret60 is None
        or spy_ret20 is None
        or daily20 is None
        or avg_dollar_volume20 is None
    ):
        return None

    positive_day_ratio20 = sum(1 for value in daily20 if value > 0.0) / len(daily20)
    max_daily_return20 = max(daily20)
    max_abs_daily_return20 = max(abs(value) for value in daily20)
    realized_vol20 = _std(daily20)
    ret60_excess_spy = ret60 - spy_ret60
    ret20_excess_spy = ret20 - spy_ret20

    if avg_dollar_volume20 < MIN_AVG_DOLLAR_VOLUME_20:
        return None
    if close <= sma50:
        return None
    if ret60 < MIN_RET60 or ret60_excess_spy < MIN_RET60_EXCESS_SPY:
        return None
    if ret20 < MIN_RET20 or ret20_excess_spy < MIN_RET20_EXCESS_SPY:
        return None
    if ret5 < MIN_RET5 or ret5 > MAX_RET5:
        return None
    if not (MIN_POSITIVE_DAY_RATIO_20 <= positive_day_ratio20 <= MAX_POSITIVE_DAY_RATIO_20):
        return None
    if max_daily_return20 > MAX_DAILY_RETURN_20:
        return None
    if max_abs_daily_return20 > MAX_ABS_DAILY_RETURN_20:
        return None
    if realized_vol20 is None or realized_vol20 > MAX_REALIZED_VOL_20:
        return None

    score = (
        ret60_excess_spy * 1.0
        + ret20_excess_spy * 0.7
        - max_daily_return20 * 0.35
        - realized_vol20 * 0.5
    )
    return {
        "ticker": ticker,
        "date": date,
        "sector": ohlcv_shadow.SECTOR_MAP.get(ticker, "Unknown"),
        "close": base._round(close, 4),
        "sma50": base._round(sma50, 4),
        "ret60": base._round(ret60, 6),
        "spy_ret60": base._round(spy_ret60, 6),
        "ret60_excess_spy": base._round(ret60_excess_spy, 6),
        "ret20": base._round(ret20, 6),
        "spy_ret20": base._round(spy_ret20, 6),
        "ret20_excess_spy": base._round(ret20_excess_spy, 6),
        "ret5": base._round(ret5, 6),
        "positive_day_ratio20": base._round(positive_day_ratio20, 6),
        "max_daily_return20": base._round(max_daily_return20, 6),
        "max_abs_daily_return20": base._round(max_abs_daily_return20, 6),
        "realized_vol20": base._round(realized_vol20, 6),
        "avg_dollar_volume20": base._round(avg_dollar_volume20, 2),
        "smooth_momentum_score": base._round(score, 6),
        "smooth_momentum_rule_version": RULE_VERSION,
        "known_at": "signal-date close before next-open paper entry",
        "trade_enabled": False,
        "alters_orders": False,
    }


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> list[dict[str, Any]]:
    entries_by_date = ohlcv_shadow._baseline_entries(before_result)
    dates = {
        date
        for date in ohlcv_shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= date <= str(cfg["end"])
    }
    raw_considered = 0
    candidates: list[dict[str, Any]] = []
    for ticker in sorted(set(universe).intersection(snapshot)):
        if ticker in ohlcv_shadow.EXCLUDED_TICKERS:
            continue
        rows = ohlcv_shadow._series(snapshot, ticker)
        for idx, row in enumerate(rows):
            date = ohlcv_shadow._date(row)
            if date not in dates:
                continue
            raw_considered += 1
            candidate = _smooth_momentum_candidate(snapshot, ticker, rows, idx)
            if candidate is None:
                continue
            ab_entries = entries_by_date.get(candidate["date"], [])
            candidate["same_day_ab_entry_count"] = len(ab_entries)
            candidate["same_day_ab_overlap"] = bool(ab_entries)
            candidate["same_ticker_ab_overlap"] = any(
                trade.get("ticker") == candidate["ticker"] for trade in ab_entries
            )
            candidates.append(candidate)

    label = next(
        (
            window_label
            for window_label, window_cfg in base.WINDOWS.items()
            if window_cfg is cfg
        ),
        str(cfg.get("start")),
    )
    PATH_AUDIT[label] = {
        "raw_ticker_days_considered": raw_considered,
        "smooth_momentum_candidates": len(candidates),
        "candidate_days": len({row["date"] for row in candidates}),
        "rule_version": RULE_VERSION,
    }
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["smooth_momentum_score"]),
            -float(row["ret60_excess_spy"]),
            float(row["max_daily_return20"]),
            -float(row["avg_dollar_volume20"]),
            row["ticker"],
        )
    )
    return candidates


def _update_payload(payload: dict[str, Any]) -> dict[str, Any]:
    decision = (
        "promising_replay_only_smooth_momentum_path_sleeve"
        if payload["gate4"]["passed"]
        else "rejected_smooth_momentum_path_sleeve"
    )
    payload["status"] = decision
    payload["decision"] = decision
    payload["hypothesis"] = (
        "Daily-return path alpha may be cleaner when a stock is already a "
        "60-day SPY-relative leader, remains above its 50-day average, and its "
        "recent 20-day advance is broad rather than dominated by one large "
        "daily jump. This tests a default-off paper candidate source using "
        "only free OHLCV fields known at the signal-date close."
    )
    payload["change_type"] = "smooth_momentum_path_default_off_paper_sleeve"
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["trial_family"] = TRIAL_FAMILY
    payload["prior_trial_count"] = 0
    payload["mechanism_family"] = "daily_return_path_free_ohlcv_candidate_pool"
    payload["trial_variant_id"] = "smooth_momentum_path_top1_v1"
    payload["nearby_prior_experiments"] = [
        "exp-20260503-008",
        "exp-20260506-019",
        "exp-20260512-024",
        "exp-20260523-006",
        "exp-20260525-011",
        "exp-20260525-020",
        "exp-20260525-026",
        "exp-20260526-001",
    ]
    payload["multiple_testing_risk_bucket"] = "moderate"
    payload["new_evidence_type"] = "production_visible_daily_return_path_cluster_from_free_ohlcv"
    payload["parameters"]["shadow_entry_filters"] = {
        "lookback_rs_days": LOOKBACK_RS,
        "lookback_path_days": LOOKBACK_PATH,
        "lookback_sma_days": LOOKBACK_SMA,
        "lookback_pull_days": LOOKBACK_PULL,
        "min_ret60": MIN_RET60,
        "min_ret60_excess_spy": MIN_RET60_EXCESS_SPY,
        "min_ret20": MIN_RET20,
        "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
        "ret5_range": [MIN_RET5, MAX_RET5],
        "positive_day_ratio20_range": [
            MIN_POSITIVE_DAY_RATIO_20,
            MAX_POSITIVE_DAY_RATIO_20,
        ],
        "max_daily_return20": MAX_DAILY_RETURN_20,
        "max_abs_daily_return20": MAX_ABS_DAILY_RETURN_20,
        "max_realized_vol20": MAX_REALIZED_VOL_20,
        "min_avg_dollar_volume20": MIN_AVG_DOLLAR_VOLUME_20,
        "close_above_sma50": True,
    }
    payload["parameters"]["selection_rank"] = [
        "signal_date",
        "smooth_momentum_score desc",
        "ret60_excess_spy desc",
        "max_daily_return20 asc",
        "avg_dollar_volume20 desc",
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
            "entry / candidate_pool: a smooth daily-return path among 60-day "
            "SPY-relative leaders may expand the paper candidate pool with less "
            "tail/chase risk than gap, opening-range, pullback, or raw "
            "sector-leadership sources. This matches the playbook's free-data "
            "daily-return pattern direction and avoids LLM soft-ranking."
        ),
        "2_history_check": {
            "exp-20260503-008": (
                "Standalone pullback-RS EOD research was promising but "
                "survivorship-biased and not promotable."
            ),
            "exp-20260506-019": (
                "Pullback/60d score failed when used for slot-aware candidate "
                "ranking; this test does not reorder core candidates."
            ),
            "exp-20260512-024": (
                "Pullback-reclaim entry replay failed all three canonical "
                "windows; this test is not a pullback/reclaim rule."
            ),
            "exp-20260523-006": (
                "Broad-market max-daily-return support failed as a notional "
                "scalar; this test uses smooth path as a new default-off paper "
                "candidate source, not a broad-market scalar."
            ),
            "exp-20260525-011/026/20260526-001": (
                "Opening-range, inside-day, and gap-and-hold paper sources were "
                "freshly rejected; this uses a different daily-return path "
                "cluster."
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
            "exp_20260526_002_smooth_momentum_path_sleeve.py"
        ),
    }
    payload["gate2"]["runtime_fields"] = [
        "canonical OHLCV Date/Open/High/Low/Close/Volume rows",
        "SPY OHLCV Close rows for signal-date relative strength",
        "derived 60d/20d/5d returns known at signal-date close",
        "derived 20d daily-return path statistics known at signal-date close",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["gate2"]["note"] = (
        "The sleeve uses only same-day and trailing daily OHLCV fields known at "
        "the signal-date close, then enters paper only at the next open. It "
        "does not ask LLM or production to infer hidden fields."
    )
    payload["smooth_path_audit"] = PATH_AUDIT
    payload["why_not_other_changes"] = (
        "Skipped LLM soft-ranking and expectation-residual leaders because "
        "recent logs show sparse usable data. Skipped state-surface, VCP "
        "top-N/threshold, broad-market scalar, opening-range, sector-leadership, "
        "inside-day, gap-and-hold, and pullback retreads due fresh rejections "
        "or anti-repeat rules. This tests a distinct free-OHLCV daily-return "
        "path source inside the existing production universe."
    )
    payload["interpretation"] = (
        "The smooth momentum path sleeve cleared Gate 4 as a replay-only lead, "
        "but no production/shared policy was promoted."
        if payload["gate4"]["passed"]
        else (
            "The smooth momentum path sleeve did not clear Gate 4. Do not "
            "promote or retry nearby smooth-path thresholds on these windows "
            "without forward paper rows or a materially different source/event "
            "confirmation field."
        )
    )
    payload["rejection_reason"] = (
        None if payload["gate4"]["passed"] else payload.get("rejection_reason")
    )
    payload["next_evidence_needed"] = (
        "If revisited, require forward paper outcomes or an orthogonal "
        "production-visible event/source confirmation field. Do not just retune "
        "ret60, ret20, max-daily-return, or top-N thresholds on the frozen sample."
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Candidates | Days |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["smooth_path_audit"].get(label, {})
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | "
            "${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | "
            "{trades} | {candidates} | {days} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                candidates=audit.get("smooth_momentum_candidates"),
                days=audit.get("candidate_days"),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Smooth Momentum Path Paper Sleeve",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            (
                "Single variable: a default-off paper sleeve admits at most one "
                "smooth daily-return-path momentum leader per day, enters at "
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
            "## Smooth Path Audit",
            "",
            "```json",
            json.dumps(payload["smooth_path_audit"], indent=2, sort_keys=True),
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
            "title": "Smooth momentum path paper sleeve",
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
                    "smooth_path_audit": payload["smooth_path_audit"],
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
