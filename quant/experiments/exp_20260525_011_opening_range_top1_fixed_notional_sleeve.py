"""exp-20260525-011: opening-range top-1 fixed-notional sleeve.

This alpha search retests an old shadow-entry family with the current
docs/backtesting.md windows and production-safe execution assumptions. The
single variable is a default-off paper sleeve that admits at most one
opening-range continuation candidate per signal day, enters at the next
available open, and exits after ten trading days at the close.

Core signal generation, ranking, sizing, exits, LLM/news replay, watchlists,
and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
LEGACY_DIR = EXPERIMENT_DIR / "legacy"
for path in (QUANT_DIR, EXPERIMENT_DIR, LEGACY_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260426_041_opening_range_continuation_shadow as shadow  # noqa: E402
import exp_20260510_007_low_deployment_dynamic_etf_overlay as overlay_helper  # noqa: E402
from constants import ROUND_TRIP_COST_PCT  # noqa: E402
from data_layer import get_universe  # noqa: E402
from fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage  # noqa: E402


EXPERIMENT_ID = "exp-20260525-011"
STEM = "opening_range_top1_fixed_notional_sleeve"
TRIAL_FAMILY = "opening_range_continuation_default_off_paper_sleeve"
CHANGED_VARIABLE = "opening_range_top1_next_open_10d_fixed_notional_sleeve_v1"

BASE_NOTIONAL_USD = 10_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
MIN_TARGET_TRADES = 30
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.35
MAX_POSITIVE_HHI = 0.25

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
OPEN_POSITIONS_JSON = REPO_ROOT / "operator_inputs" / "open_positions.json"

WINDOWS: "OrderedDict[str, dict[str, str]]" = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
            },
        ),
    ]
)


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(row) for key, row in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(row) for row in value]
    if isinstance(value, set):
        return sorted(_safe(row) for row in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _audit_open_positions() -> dict[str, Any]:
    if not OPEN_POSITIONS_JSON.exists():
        return {
            "passed": False,
            "path": _repo_rel(OPEN_POSITIONS_JSON),
            "reason": "missing_open_positions_json",
        }
    payload = json.loads(OPEN_POSITIONS_JSON.read_text(encoding="utf-8"))
    rows = []
    for key in ("positions", "observations"):
        value = payload.get(key)
        if isinstance(value, list):
            rows.extend(row for row in value if isinstance(row, dict))
    missing_entry = [
        str(row.get("ticker") or "<unknown>") for row in rows if not row.get("entry_date")
    ]
    missing_target = [
        str(row.get("ticker") or "<unknown>") for row in rows if row.get("target_price") in (None, "")
    ]
    return {
        "passed": not missing_entry and not missing_target,
        "path": _repo_rel(OPEN_POSITIONS_JSON),
        "position_count": len(rows),
        "missing_entry_date_tickers": missing_entry,
        "missing_target_price_tickers": missing_target,
    }


def _overlay_from_paper_trades(
    before_result: dict[str, Any],
    paper_trades: list[dict[str, Any]],
) -> dict[str, Any]:
    pnl_by_exit_date: Counter[str] = Counter()
    overlay_days: list[dict[str, Any]] = []
    for trade in paper_trades:
        exit_date = str(trade.get("exit_date") or "")
        pnl = float(trade.get("pnl") or 0.0)
        pnl_by_exit_date[exit_date] += pnl
        overlay_days.append(
            {
                "date": exit_date,
                "ticker": trade.get("ticker"),
                "signal_date": trade.get("signal_date"),
                "entry_date": trade.get("entry_date"),
                "exit_date": exit_date,
                "pnl": _round(pnl, 2),
                "source": STEM,
            }
        )

    cumulative_overlay = 0.0
    combined_curve = []
    for day, equity in before_result.get("equity_curve") or []:
        cumulative_overlay += float(pnl_by_exit_date.get(str(day), 0.0))
        combined_curve.append((str(day), round(float(equity) + cumulative_overlay, 2)))

    return {
        "overlay_total_pnl": _round(sum(pnl_by_exit_date.values()), 2),
        "combined_equity_curve": combined_curve,
        "overlay_days": overlay_days,
        "overlay_day_count": len(overlay_days),
    }


def _paper_trade_from_candidate(
    snapshot: dict[str, list[dict[str, Any]]],
    candidate: dict[str, Any],
) -> dict[str, Any] | None:
    rows = shadow._series(snapshot, str(candidate.get("ticker") or ""))
    idx = shadow._row_index(rows).get(str(candidate.get("date") or ""))
    if idx is None:
        return None
    entry_idx = idx + 1
    exit_idx = idx + HOLD_DAYS
    if entry_idx >= len(rows) or exit_idx >= len(rows):
        return None

    entry_raw = shadow._value(rows[entry_idx], "Open")
    exit_raw = shadow._value(rows[exit_idx], "Close")
    if not entry_raw or not exit_raw:
        return None

    entry_price = apply_entry_fill(entry_raw)
    exit_price = apply_slippage(exit_raw, SLIPPAGE_BPS_TARGET, "sell")
    pnl_pct_net = (exit_price / entry_price) - 1.0 - ROUND_TRIP_COST_PCT
    pnl = BASE_NOTIONAL_USD * pnl_pct_net
    return {
        **candidate,
        "signal_date": candidate.get("date"),
        "entry_date": shadow._date(rows[entry_idx]),
        "exit_date": shadow._date(rows[exit_idx]),
        "entry_raw_open": _round(entry_raw, 4),
        "exit_raw_close": _round(exit_raw, 4),
        "entry_price": _round(entry_price, 4),
        "exit_price": _round(exit_price, 4),
        "hold_days": HOLD_DAYS,
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "pnl_pct_net": _round(pnl_pct_net, 6),
        "pnl": _round(pnl, 2),
    }


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> list[dict[str, Any]]:
    entries_by_date = shadow._baseline_entries(before_result)
    dates = [
        date
        for date in shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= date <= str(cfg["end"])
    ]
    candidates: list[dict[str, Any]] = []
    for ticker in sorted(set(universe).intersection(snapshot)):
        if ticker in shadow.EXCLUDED_TICKERS:
            continue
        for row in shadow._candidate_rows(snapshot, ticker, dates):
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
            -row["prior_day_rs_vs_spy"],
            -row["candidate_day_rs_vs_spy"],
            -row["dollar_volume"],
            row["ticker"],
        )
    )
    return candidates


def _select_paper_trades(
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    used_date_counts: Counter[str] = Counter()
    for row in candidates:
        date = str(row.get("date") or "")
        if row.get("same_ticker_ab_overlap"):
            filtered.append({**row, "filter_reason": "same_ticker_core_overlap"})
            continue
        if used_date_counts[date] >= MAX_PAPER_TRADES_PER_DAY:
            filtered.append({**row, "filter_reason": "daily_top1_limit"})
            continue
        trade = _paper_trade_from_candidate(snapshot, row)
        if trade is None:
            filtered.append({**row, "filter_reason": "missing_next_open_or_exit"})
            continue
        selected.append(trade)
        used_date_counts[date] += 1
    return selected, filtered


def _target_trade_summary(
    target_trades_by_window: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    by_ticker_count: Counter[str] = Counter()
    by_ticker_pnl: Counter[str] = Counter()
    by_window_pnl = {}
    for label, trades in target_trades_by_window.items():
        by_window_pnl[label] = round(sum(float(trade.get("pnl") or 0.0) for trade in trades), 2)
        for trade in trades:
            ticker = str(trade.get("ticker") or "").upper()
            pnl = float(trade.get("pnl") or 0.0)
            by_ticker_count[ticker] += 1
            by_ticker_pnl[ticker] += pnl

    positive = {ticker: pnl for ticker, pnl in by_ticker_pnl.items() if pnl > 0}
    positive_total = sum(positive.values())
    max_positive_share = (
        round(max(positive.values()) / positive_total, 6)
        if positive_total > 0 and positive
        else None
    )
    positive_hhi = (
        round(sum((pnl / positive_total) ** 2 for pnl in positive.values()), 6)
        if positive_total > 0 and positive
        else None
    )
    return {
        "total_trade_count": sum(by_ticker_count.values()),
        "windows_with_target_trades": [
            label for label, trades in target_trades_by_window.items() if trades
        ],
        "total_pnl": round(sum(by_ticker_pnl.values()), 2),
        "by_window_pnl": by_window_pnl,
        "by_ticker_count": dict(sorted(by_ticker_count.items())),
        "by_ticker_pnl": {
            ticker: round(pnl, 2) for ticker, pnl in sorted(by_ticker_pnl.items())
        },
        "positive_by_ticker_pnl": {
            ticker: round(pnl, 2) for ticker, pnl in sorted(positive.items())
        },
        "max_single_positive_pnl_share": max_positive_share,
        "positive_pnl_hhi": positive_hhi,
    }


def _aggregate(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ev_before = sum(row["before"]["expected_value_score"] for row in rows.values())
    ev_after = sum(row["after"]["expected_value_score"] for row in rows.values())
    pnl_before = sum(row["before"]["total_pnl"] for row in rows.values())
    pnl_after = sum(row["after"]["total_pnl"] for row in rows.values())
    return {
        "baseline_expected_value_score_sum": _round(ev_before, 6),
        "after_expected_value_score_sum": _round(ev_after, 6),
        "expected_value_score_delta_sum": _round(ev_after - ev_before, 6),
        "expected_value_score_delta_pct": _round((ev_after - ev_before) / ev_before, 6)
        if ev_before
        else None,
        "baseline_total_pnl_sum": _round(pnl_before, 2),
        "after_total_pnl_sum": _round(pnl_after, 2),
        "total_pnl_delta_sum": _round(pnl_after - pnl_before, 2),
        "total_pnl_delta_pct": _round((pnl_after - pnl_before) / pnl_before, 6)
        if pnl_before
        else None,
        "windows_ev_improved": sum(
            1 for row in rows.values() if row["delta"]["expected_value_score"] > 0
        ),
        "windows_ev_regressed": sum(
            1 for row in rows.values() if row["delta"]["expected_value_score"] < 0
        ),
        "windows_pnl_improved": sum(
            1 for row in rows.values() if row["delta"]["total_pnl"] > 0
        ),
        "windows_pnl_regressed": sum(
            1 for row in rows.values() if row["delta"]["total_pnl"] < 0
        ),
        "max_drawdown_delta_max": _round(
            max(row["delta"]["max_drawdown_pct"] for row in rows.values()), 6
        ),
        "target_trade_count_sum": sum(row["target_trade_count"] for row in rows.values()),
    }


def _build_payload() -> dict[str, Any]:
    gate2_open_positions = _audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(get_universe())
    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    filtered_candidates_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    raw_candidate_counts: "OrderedDict[str, int]" = OrderedDict()
    candidate_day_counts: "OrderedDict[str, int]" = OrderedDict()

    for label, cfg in WINDOWS.items():
        print(f"[{label}] baseline core replay")
        before_result = shadow._run_baseline(universe, cfg)
        before = overlay_helper._metrics(before_result)
        snapshot = shadow._load_snapshot(cfg["snapshot"])
        candidates = _candidate_rows_for_window(snapshot, cfg, universe, before_result)
        selected_trades, filtered_candidates = _select_paper_trades(snapshot, candidates)
        overlay = _overlay_from_paper_trades(before_result, selected_trades)
        after = overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = overlay_helper._delta(after, before)

        before_metrics[label] = before
        after_metrics[label] = after
        target_trades_by_window[label] = selected_trades
        filtered_candidates_by_window[label] = filtered_candidates[:200]
        raw_candidate_counts[label] = len(candidates)
        candidate_day_counts[label] = len({row["date"] for row in candidates})
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected_trades),
            "raw_candidate_count": len(candidates),
            "raw_candidate_days": candidate_day_counts[label],
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = _aggregate(window_rows)
    target_summary = _target_trade_summary(target_trades_by_window)
    target_windows = target_summary["windows_with_target_trades"]
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    gate4_passed = (
        aggregate["expected_value_score_delta_sum"] > 0
        and aggregate["total_pnl_delta_sum"] > 0
        and aggregate["windows_ev_improved"] == len(WINDOWS)
        and aggregate["windows_ev_regressed"] == 0
        and aggregate["windows_pnl_regressed"] == 0
        and target_summary["total_trade_count"] >= MIN_TARGET_TRADES
        and len(target_windows) >= MIN_TARGET_WINDOWS
        and aggregate["max_drawdown_delta_max"] <= MAX_DRAWDOWN_WORSE
        and min_survival >= 0.05
        and concentration_passed
    )

    failed: list[str] = []
    if aggregate["expected_value_score_delta_sum"] <= 0:
        failed.append("aggregate_ev_not_positive")
    if aggregate["total_pnl_delta_sum"] <= 0:
        failed.append("aggregate_pnl_not_positive")
    if aggregate["windows_ev_improved"] != len(WINDOWS) or aggregate["windows_ev_regressed"]:
        failed.append("window_ev_regression")
    if aggregate["windows_pnl_regressed"]:
        failed.append("window_pnl_regression")
    if target_summary["total_trade_count"] < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_windows) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if aggregate["max_drawdown_delta_max"] > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if not concentration_passed:
        failed.append("target_concentration_failed")

    decision = (
        "promising_replay_only_opening_range_top1_fixed_notional_sleeve"
        if gate4_passed
        else "rejected_opening_range_top1_fixed_notional_sleeve"
    )
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "A production-visible opening-range continuation candidate may add "
            "replacement alpha when strong prior-day relative momentum is not "
            "faded at the next open and the stock closes through the prior high. "
            "Using only the top ranked candidate per day should reduce noise "
            "versus broad ticker-pool expansion."
        ),
        "change_type": "opening_range_continuation_default_off_paper_sleeve",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "prior_trial_count": 2,
        "nearby_prior_experiments": [
            "exp-20260426-040",
            "exp-20260426-041",
            "exp-20260426-050",
            "exp-20260426-051",
            "exp-20260426-061",
            "exp-20260426-062",
        ],
        "multiple_testing_risk_bucket": "medium",
        "new_evidence_type": (
            "current_three_window_next_open_slippage_adjusted_fixed_notional_"
            "paper_sleeve_replay"
        ),
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": WINDOWS,
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "Signal uses only close-of-day OHLCV available on the signal date; "
                "paper entry is next available open with production entry slippage; "
                "exit is the close ten trading days after the signal with target-side "
                "sell slippage and ROUND_TRIP_COST_PCT."
            ),
        },
        "parameters": {
            "base_universe_count": len(universe),
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "excluded_tickers": sorted(shadow.EXCLUDED_TICKERS),
            "shadow_entry_filters": {
                "min_prior_day_return": shadow.MIN_PRIOR_DAY_RETURN,
                "min_prior_day_rs_vs_spy": shadow.MIN_PRIOR_DAY_RS_VS_SPY,
                "min_open_vs_prior_close": shadow.MIN_OPEN_VS_PRIOR_CLOSE,
                "min_candidate_rs_vs_spy": shadow.MIN_CANDIDATE_RS_VS_SPY,
                "min_dollar_volume": shadow.MIN_DOLLAR_VOLUME,
                "close_must_be_above_open": True,
                "close_must_be_above_prior_high": True,
            },
            "selection_rank": [
                "signal_date",
                "prior_day_rs_vs_spy desc",
                "candidate_day_rs_vs_spy desc",
                "dollar_volume desc",
                "ticker asc",
            ],
            "locked_variables": [
                "core universe",
                "core signal generation",
                "core ranking",
                "core position sizing",
                "core exits",
                "portfolio heat",
                "slot rules",
                "LLM/news replay",
                "live/default orders",
            ],
            "acceptance": {
                "aggregate_ev_delta_gt": 0,
                "aggregate_pnl_delta_gt": 0,
                "ev_improved_windows": 3,
                "max_ev_regressed_windows": 0,
                "max_pnl_regressed_windows": 0,
                "min_target_trades": MIN_TARGET_TRADES,
                "min_target_windows": MIN_TARGET_WINDOWS,
                "max_drawdown_worse": MAX_DRAWDOWN_WORSE,
                "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
                "max_positive_hhi": MAX_POSITIVE_HHI,
            },
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "entry / candidate_pool: opening-range continuation may surface "
                "a higher-quality, production-visible candidate source using only "
                "free OHLCV."
            ),
            "2_history_check": {
                "exp-20260426-041": (
                    "Observed-only opening-range shadow audit; did not use current "
                    "snapshot paths or next-open fixed-notional before/after EV."
                ),
                "exp-20260426-051": (
                    "Pullback reclaim production-path replay failed; this is a "
                    "different entry definition and no-displacement paper boundary."
                ),
                "exp-20260426-062": (
                    "Market-pullback resilience shadow family was separately "
                    "prechecked this run and showed negative fixed-notional PnL."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Same three docs/backtesting.md windows; positive aggregate EV/PnL; "
                "3/3 EV-improved windows; no PnL-regressed window; >=30 paper "
                "trades across all 3 windows; drawdown drift <=0.5pp; survival "
                ">=5%; concentration inside guardrails."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260525_011_opening_range_top1_fixed_notional_sleeve.py"
            ),
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": f"{_repo_rel(OUT_JSON)}#before_metrics",
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "canonical OHLCV Date/Open/High/Close/Volume rows",
                "SPY OHLCV rows for same-window relative strength",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "passed": True,
            "note": (
                "The sleeve uses only same-day and prior-day OHLCV fields plus "
                "next-open/exit prices available to the replay. It does not ask "
                "LLM or production to infer hidden fields."
            ),
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": _round(min_survival, 4),
            "passed": min_survival >= 0.05,
            "note": (
                "No new core filter or core entry rule was added. The target source "
                "is evaluated as additive default-off paper, so core survival is "
                "unchanged from the baseline replay."
            ),
        },
        "gate4": {
            "passed": gate4_passed,
            "aggregate_ev_delta_positive": aggregate["expected_value_score_delta_sum"] > 0,
            "aggregate_pnl_delta_positive": aggregate["total_pnl_delta_sum"] > 0,
            "windows_ev_improved": aggregate["windows_ev_improved"],
            "windows_ev_regressed": aggregate["windows_ev_regressed"],
            "windows_pnl_regressed": aggregate["windows_pnl_regressed"],
            "target_trade_count": target_summary["total_trade_count"],
            "target_trade_count_min": MIN_TARGET_TRADES,
            "target_windows": target_windows,
            "target_window_count_min": MIN_TARGET_WINDOWS,
            "max_drawdown_worse": aggregate["max_drawdown_delta_max"],
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
            "survival_guard_passed": min_survival >= 0.05,
            "target_concentration": {
                "passed": concentration_passed,
                "max_single_positive_pnl_share": target_summary[
                    "max_single_positive_pnl_share"
                ],
                "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
                "positive_pnl_hhi": target_summary["positive_pnl_hhi"],
                "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
            },
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict((label, row["delta"]) for label, row in window_rows.items()),
            "aggregate": aggregate,
        },
        "raw_candidate_counts": raw_candidate_counts,
        "candidate_day_counts": candidate_day_counts,
        "target_trades_by_window": target_trades_by_window,
        "filtered_candidates_sample_by_window": filtered_candidates_by_window,
        "target_trade_summary": target_summary,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "default_off_paper_only": True,
            "production_watchlist_changed": False,
            "production_orders_changed": False,
            "trade_enabled": False,
            "promotion_requirement": (
                "A retained result would still require a shared default-off paper "
                "adapter and parity tests before any daily report or live/default "
                "behavior changes."
            ),
        },
        "why_not_other_changes": (
            "Skipped LLM soft-ranking because attribution remains sparse; skipped "
            "AI power/datacenter after a precheck showed IWM-confirmed fixed "
            "notional PnL remained negative with only two trades; skipped more "
            "AI infra/compute/optical fixed-notional retreads per playbook freeze "
            "guidance. This uses a separate, free OHLCV entry source."
        ),
        "interpretation": (
            "The opening-range top-1 paper sleeve cleared Gate 4 as a replay-only "
            "lead, but no production/shared policy was promoted."
            if gate4_passed
            else (
                "The opening-range top-1 paper sleeve did not clear Gate 4. Do "
                "not promote or retry nearby opening-range filters without a new "
                "production-visible discriminator or broader forward sample."
            )
        ),
        "rejection_reason": None if gate4_passed else "; ".join(failed),
        "next_evidence_needed": (
            "If revisited, use a materially new discriminator such as source/event "
            "confirmation or forward paper rows; do not just retune the same OHLCV "
            "thresholds on this frozen sample."
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(EXPERIMENT_LOG),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} | {raw} |".format(
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
            f"# {EXPERIMENT_ID} Opening-Range Top-1 Fixed-Notional Sleeve",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: a default-off paper sleeve admits at most one opening-range continuation candidate per day, enters at next open, and exits after ten trading days.",
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
            "Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Opening-range top-1 fixed-notional sleeve",
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": _repo_rel(ARTIFACT_MD),
            "json": _repo_rel(OUT_JSON),
            "summary": payload["interpretation"],
        },
    )
    _write_text(ARTIFACT_MD, _build_report(payload))
    _upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    payload = _build_payload()
    persist(payload)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
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
