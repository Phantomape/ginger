"""exp-20260605-035: low-deployment ETF cash-substitute execution model.

Replay-only alpha search. The prior low-deployment ETF selector was
directionally useful, but production activation remains blocked by forward
sample/concentration and cash semantics. This experiment keeps the existing
free-OHLCV ETF selector, but evaluates a production-realistic execution
boundary on the current PIT-DTE core baseline:

    signal after the low-deployment day's close, enter the selected ETF at the
    next trading day's open, hold to the 10th trading-day close after signal,
    and allow only one open ETF substitute position at a time.

No production code, live orders, watchlists, core ranking, sizing, exits, LLM,
or news behavior are changed. No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
LEGACY_DIR = EXPERIMENTS_DIR / "legacy"
for import_path in (QUANT_DIR, EXPERIMENTS_DIR, LEGACY_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260426_041_opening_range_continuation_shadow as shadow  # noqa: E402
import exp_20260510_007_low_deployment_dynamic_etf_overlay as overlay_helper  # noqa: E402
import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as sleeve  # noqa: E402
from constants import ROUND_TRIP_COST_PCT  # noqa: E402
from data_layer import get_universe  # noqa: E402
from fill_model import SLIPPAGE_BPS_ENTRY, SLIPPAGE_BPS_TARGET, apply_slippage  # noqa: E402


EXPERIMENT_ID = "exp-20260605-035"
STEM = "low_deployment_etf_cash_substitute"
TRIAL_FAMILY = "low_deployment_etf_cash_substitute_execution_model"
TRIAL_VARIANT_ID = "low_deployment_etf_next_open_10d_cash_substitute_v1"
CHANGED_VARIABLE = "low_deployment_etf_prior_close_selector_next_open_10d_cash_substitute_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260605_035_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"exp_20260605_035_{STEM}_aggregate_before.json"
AFTER_JSON = OUT_DIR / f"exp_20260605_035_{STEM}_aggregate_after.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

BASE_NOTIONAL_USD = 100_000.0
HOLD_DAYS = 10
MAX_ACTIVE_CORE_POSITIONS = 1
MAX_OVERLAY_OPEN_POSITIONS = 1
STATE_SMA_DAYS = 200
STATE_MOMENTUM_DAYS = 20
OVERLAY_CANDIDATES = ("QQQ", "SPY", "IWM", "GLD", "SLV")
MIN_TARGET_TRADES = 15
MIN_TARGET_WINDOWS = 3
MIN_EV_DELTA_PCT = 0.10
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.75
MAX_POSITIVE_PNL_HHI = 0.50

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

PREDICTION = {
    "success_probability": 0.12,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "current_core_baseline_erases_prior_edge",
        "next_open_10d_execution_adds_beta_noise",
        "old_thin_window_regression",
        "positive_pnl_concentration",
        "forward_cash_semantics_still_blocked",
    ],
    "confidence_reason": (
        "The raw low-deployment ETF overlay was historically positive, but "
        "adjacent ETF refinements and forward activation readiness failed. "
        "This tests production-realistic execution on the current baseline "
        "instead of another selector threshold."
    ),
    "recorded_at": "2026-06-05T23:09:55Z",
}

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
        "This runner changes no production code. If positive, promotion would "
        "require a shared default-off adapter using the same active-core count "
        "definition, ETF candidate set, close-known trend/momentum selector, "
        "next-open entry, 10-trading-day close exit, one-open-position cap, "
        "cost/slippage model, cash budget semantics, and no-live-order boundary "
        "in both replay and daily production."
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {str(key): _safe(value) for key, value in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [_safe(value) for value in payload]
    if isinstance(payload, set):
        return sorted(_safe(value) for value in payload)
    if isinstance(payload, Counter):
        return dict(payload)
    if isinstance(payload, Path):
        return str(payload)
    if isinstance(payload, float):
        if math.isnan(payload) or math.isinf(payload):
            return None
        return round(payload, 10)
    return payload


def _round(value: Any, digits: int = 6) -> float | None:
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


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _sha256(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _value(row: dict[str, Any], key: str) -> float | None:
    return shadow._value(row, key)


def _rows_by_date(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {str(shadow._date(row)): idx for idx, row in enumerate(rows)}


def _core_active_count_by_date(result: dict[str, Any]) -> dict[str, int]:
    curve_dates = [str(day) for day, _ in result.get("equity_curve") or []]
    counts = {day: 0 for day in curve_dates}
    for trade in result.get("trades") or []:
        if trade.get("strategy") not in {"trend_long", "breakout_long"}:
            continue
        entry_date = str(trade.get("entry_date") or "")[:10]
        exit_date = str(trade.get("exit_date") or "")[:10]
        if not entry_date or not exit_date:
            continue
        for day in curve_dates:
            if entry_date <= day <= exit_date:
                counts[day] = counts.get(day, 0) + 1
    return counts


def _candidate_state(rows: list[dict[str, Any]], idx: int) -> dict[str, Any] | None:
    if idx < max(STATE_SMA_DAYS, STATE_MOMENTUM_DAYS):
        return None
    close = _value(rows[idx], "Close")
    momentum_base = _value(rows[idx - STATE_MOMENTUM_DAYS], "Close")
    if close is None or momentum_base is None or momentum_base <= 0:
        return None
    sma_window = rows[idx - STATE_SMA_DAYS + 1 : idx + 1]
    closes = [_value(row, "Close") for row in sma_window]
    if len(closes) != STATE_SMA_DAYS or any(value is None for value in closes):
        return None
    sma = sum(float(value) for value in closes if value is not None) / STATE_SMA_DAYS
    momentum = close / momentum_base - 1.0
    if close <= sma or momentum <= 0.0:
        return None
    return {
        "signal_close": close,
        "sma200": sma,
        "momentum20": momentum,
    }


def _select_overlay_ticker(
    snapshot: dict[str, list[dict[str, Any]]],
    index_by_ticker_date: dict[str, dict[str, int]],
    signal_date: str,
) -> dict[str, Any] | None:
    candidates = []
    for ticker in OVERLAY_CANDIDATES:
        rows = shadow._series(snapshot, ticker)
        idx = index_by_ticker_date.get(ticker, {}).get(signal_date)
        if idx is None:
            continue
        state = _candidate_state(rows, idx)
        if state is None:
            continue
        candidates.append(
            {
                "ticker": ticker,
                "idx": idx,
                "momentum": float(state["momentum20"]),
                "state": state,
            }
        )
    if not candidates:
        return None
    return max(candidates, key=lambda row: (row["momentum"], row["ticker"]))


def _trade_from_signal(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    selection: dict[str, Any],
    signal_date: str,
    active_core_positions: int,
) -> dict[str, Any] | None:
    ticker = str(selection["ticker"])
    rows = shadow._series(snapshot, ticker)
    idx = int(selection["idx"])
    entry_idx = idx + 1
    exit_idx = idx + HOLD_DAYS
    if entry_idx >= len(rows) or exit_idx >= len(rows):
        return None
    entry_raw = _value(rows[entry_idx], "Open")
    exit_raw = _value(rows[exit_idx], "Close")
    if entry_raw is None or exit_raw is None:
        return None
    entry_price = apply_slippage(entry_raw, SLIPPAGE_BPS_ENTRY, "buy")
    exit_price = apply_slippage(exit_raw, SLIPPAGE_BPS_TARGET, "sell")
    pnl_pct_net = (exit_price / entry_price) - 1.0 - ROUND_TRIP_COST_PCT
    pnl = BASE_NOTIONAL_USD * pnl_pct_net
    state = selection["state"]
    return {
        "ticker": ticker,
        "source": STEM,
        "date": signal_date,
        "signal_date": signal_date,
        "entry_date": shadow._date(rows[entry_idx]),
        "exit_date": shadow._date(rows[exit_idx]),
        "active_core_positions_on_signal": active_core_positions,
        "entry_raw_open": _round(entry_raw, 4),
        "exit_raw_close": _round(exit_raw, 4),
        "entry_price": _round(entry_price, 4),
        "exit_price": _round(exit_price, 4),
        "hold_days": HOLD_DAYS,
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "pnl_pct_net": _round(pnl_pct_net, 6),
        "pnl": _round(pnl, 2),
        "selector_state": {
            "signal_close": _round(state["signal_close"], 4),
            "sma200": _round(state["sma200"], 4),
            "momentum20": _round(state["momentum20"], 6),
        },
    }


def _overlay_trades(
    before_result: dict[str, Any],
    snapshot: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    core_counts = _core_active_count_by_date(before_result)
    index_by_ticker_date = {
        ticker: _rows_by_date(shadow._series(snapshot, ticker))
        for ticker in OVERLAY_CANDIDATES
    }
    open_overlay_exits: list[str] = []
    trades: list[dict[str, Any]] = []
    skipped: Counter[str] = Counter()
    low_deployment_day_count = 0
    selectable_day_count = 0

    for day, _ in before_result.get("equity_curve") or []:
        signal_date = str(day)
        open_overlay_exits = [exit_date for exit_date in open_overlay_exits if exit_date > signal_date]
        active_core_positions = int(core_counts.get(signal_date, 0))
        if active_core_positions > MAX_ACTIVE_CORE_POSITIONS:
            skipped["core_above_low_deployment_threshold"] += 1
            continue
        low_deployment_day_count += 1
        if len(open_overlay_exits) >= MAX_OVERLAY_OPEN_POSITIONS:
            skipped["overlay_position_cap_full"] += 1
            continue
        selection = _select_overlay_ticker(snapshot, index_by_ticker_date, signal_date)
        if selection is None:
            skipped["no_etf_passing_prior_close_state"] += 1
            continue
        selectable_day_count += 1
        trade = _trade_from_signal(
            snapshot=snapshot,
            selection=selection,
            signal_date=signal_date,
            active_core_positions=active_core_positions,
        )
        if trade is None:
            skipped["missing_entry_or_exit_price"] += 1
            continue
        trades.append(trade)
        open_overlay_exits.append(str(trade["exit_date"]))

    return trades, {
        "low_deployment_day_count": low_deployment_day_count,
        "selectable_day_count_before_position_cap": selectable_day_count,
        "skipped": dict(skipped),
        "max_active_core_positions": MAX_ACTIVE_CORE_POSITIONS,
        "max_overlay_open_positions": MAX_OVERLAY_OPEN_POSITIONS,
    }


def _aggregate(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ev_before = sum(row["before"]["expected_value_score"] for row in rows.values())
    ev_after = sum(row["after"]["expected_value_score"] for row in rows.values())
    pnl_before = sum(row["before"]["total_pnl"] for row in rows.values())
    pnl_after = sum(row["after"]["total_pnl"] for row in rows.values())
    ev_delta = ev_after - ev_before
    pnl_delta = pnl_after - pnl_before
    return {
        "baseline_expected_value_score_sum": _round(ev_before, 6),
        "after_expected_value_score_sum": _round(ev_after, 6),
        "expected_value_score_delta_sum": _round(ev_delta, 6),
        "expected_value_score_delta_pct": _round(ev_delta / ev_before, 6) if ev_before else None,
        "required_expected_value_score_delta_sum": _round(ev_before * MIN_EV_DELTA_PCT, 6),
        "expected_value_score_delta_gt_required": ev_delta > ev_before * MIN_EV_DELTA_PCT,
        "baseline_total_pnl_sum": _round(pnl_before, 2),
        "after_total_pnl_sum": _round(pnl_after, 2),
        "total_pnl_delta_sum": _round(pnl_delta, 2),
        "total_pnl_delta_pct": _round(pnl_delta / pnl_before, 6) if pnl_before else None,
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
            max(row["delta"]["max_drawdown_pct"] for row in rows.values()),
            6,
        ),
        "target_trade_count_sum": sum(row["target_trade_count"] for row in rows.values()),
        "target_windows": [
            label for label, row in rows.items() if int(row["target_trade_count"] or 0) > 0
        ],
    }


def _concentration(trades_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    by_ticker: Counter[str] = Counter()
    total_positive = 0.0
    for trades in trades_by_window.values():
        for trade in trades:
            pnl = float(trade.get("pnl") or 0.0)
            if pnl <= 0.0:
                continue
            ticker = str(trade.get("ticker") or "").upper()
            by_ticker[ticker] += pnl
            total_positive += pnl
    if total_positive <= 0.0:
        return {
            "positive_pnl_total": 0.0,
            "ticker_positive_pnl": {},
            "max_single_positive_share": None,
            "positive_pnl_hhi": None,
            "passed": False,
        }
    shares = {ticker: pnl / total_positive for ticker, pnl in by_ticker.items()}
    max_share = max(shares.values()) if shares else None
    hhi = sum(share * share for share in shares.values())
    return {
        "positive_pnl_total": _round(total_positive, 2),
        "ticker_positive_pnl": {ticker: _round(pnl, 2) for ticker, pnl in by_ticker.items()},
        "max_single_positive_share": _round(max_share, 6),
        "positive_pnl_hhi": _round(hhi, 6),
        "passed": bool(
            max_share is not None
            and max_share <= MAX_SINGLE_POSITIVE_SHARE
            and hhi <= MAX_POSITIVE_PNL_HHI
        ),
    }


def _gate(
    *,
    aggregate: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
    concentration: dict[str, Any],
) -> dict[str, Any]:
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    failed: list[str] = []
    if not aggregate["expected_value_score_delta_gt_required"]:
        failed.append("aggregate_ev_delta_not_gt_10pct")
    if float(aggregate["total_pnl_delta_sum"] or 0.0) <= 0.0:
        failed.append("aggregate_pnl_not_positive")
    if int(aggregate["windows_ev_regressed"] or 0) > 0:
        failed.append("window_ev_regression")
    if int(aggregate["windows_pnl_regressed"] or 0) > 0:
        failed.append("window_pnl_regression")
    if int(aggregate["target_trade_count_sum"] or 0) < MIN_TARGET_TRADES:
        failed.append("target_trade_count_too_small")
    if len(aggregate["target_windows"]) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if float(aggregate["max_drawdown_delta_max"] or 0.0) > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if min_survival < 0.05:
        failed.append("core_survival_rate_below_5pct")
    if not concentration["passed"]:
        failed.append("positive_pnl_concentration_failed")
    return {
        "passed": not failed,
        "failed_reasons": failed,
        "minimum_core_survival_rate": _round(min_survival, 6),
        "aggregate": aggregate,
        "concentration": concentration,
    }


def _build_payload() -> dict[str, Any]:
    timestamp = _utc_now()
    gate2_open_positions = sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(get_universe())
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    diagnostics_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in WINDOWS.items():
        print(f"[{label}] core baseline and low-deployment ETF cash substitute replay")
        before_result = shadow._run_baseline(universe, cfg)
        before = overlay_helper._metrics(before_result)
        snapshot = shadow._load_snapshot(cfg["snapshot"])
        trades, diagnostics = _overlay_trades(before_result, snapshot)
        overlay = sleeve._overlay_from_paper_trades(before_result, trades)
        after = overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = overlay_helper._delta(after, before)
        before_metrics[label] = before
        trades_by_window[label] = trades
        diagnostics_by_window[label] = diagnostics
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(trades),
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "ticker_trade_counts": dict(Counter(str(trade["ticker"]) for trade in trades)),
            "overlay_trades_sample": trades[:20],
            "diagnostics": diagnostics,
        }

    aggregate = _aggregate(window_rows)
    concentration = _concentration(trades_by_window)
    gate4 = _gate(
        aggregate=aggregate,
        before_metrics=before_metrics,
        concentration=concentration,
    )
    status = "accepted" if gate4["passed"] else "rejected"
    decision = (
        "positive_replay_lead_not_promoted_low_deployment_etf_cash_substitute"
        if gate4["passed"]
        else "rejected_low_deployment_etf_cash_substitute"
    )
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "failure_modes_observed": gate4["failed_reasons"],
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": (
            "When the core strategy has at most one active core position, the "
            "accepted free-OHLCV ETF trend/momentum selector may provide "
            "production-realistic cash-substitute replacement value if entered "
            "at the next open and held for the same 10-trading-day paper horizon "
            "used by other default-off candidate-pool sleeves."
        ),
        "change_type": "default_off_paper_cash_substitute_sleeve",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "nearby_prior_experiments": [
            "exp-20260510-007",
            "exp-20260522-018",
            "exp-20260522-021",
            "exp-20260525-002",
            "exp-20260605-028",
        ],
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "production_realistic_next_open_cash_substitute_execution_on_current_core_baseline",
        "prediction": PREDICTION,
        "calibration": calibration,
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": WINDOWS,
            "baseline_result_file": (
                "data/experiments/exp-20260602-003/"
                "exp_20260602_003_post_earnings_explicit_continuation.json"
            ),
            "REGIME_AWARE_EXIT": True,
            "replay_llm": False,
            "replay_news": False,
            "execution_model": (
                "Signal is known after the low-deployment day close. ETF "
                "selection uses only that close and earlier OHLCV. Paper entry "
                "is next trading open, exit is 10 trading-day close after signal, "
                "with entry/exit slippage and ROUND_TRIP_COST_PCT."
            ),
        },
        "parameters": {
            "base_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_active_core_positions": MAX_ACTIVE_CORE_POSITIONS,
            "max_overlay_open_positions": MAX_OVERLAY_OPEN_POSITIONS,
            "state_sma_days": STATE_SMA_DAYS,
            "state_momentum_days": STATE_MOMENTUM_DAYS,
            "overlay_candidates": OVERLAY_CANDIDATES,
            "min_ev_delta_pct_for_risk_allocation": MIN_EV_DELTA_PCT,
            "max_drawdown_worse": MAX_DRAWDOWN_WORSE,
            "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
            "max_positive_pnl_hhi": MAX_POSITIVE_PNL_HHI,
            "locked_variables": [
                "core signal generation",
                "core ranking",
                "core sizing",
                "core exits",
                "LLM/news replay",
                "ETF candidate set",
                "prior-close 20d momentum ranking",
                "positive 200d trend gate",
                "positive 20d momentum gate",
                "low-deployment threshold",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "capital allocation / candidate-pool extension: low core "
                "deployment creates replacement-value gaps that a liquid ETF "
                "cash substitute may fill using only free OHLCV."
            ),
            "2_history_check": {
                "exp-20260510-007": (
                    "Raw low-deployment ETF overlay improved all windows on an "
                    "older baseline but used same-day open-to-close fixed-notional "
                    "paper and remained blocked by cash semantics."
                ),
                "exp-20260522-018": "Momentum-lead confidence refinement was rejected.",
                "exp-20260522-021": "Active-core-one notional scalar variants were rejected.",
                "exp-20260525-002": "Small-cap breadth confirmation variants were rejected.",
                "exp-20260605-028": (
                    "Forward readiness audit found low_deployment_etf closest, "
                    "but still below closed-sample and concentration gates."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Same three standard windows. As a capital/risk allocation "
                "experiment, acceptance requires aggregate EV delta >10% of "
                "baseline, positive aggregate PnL, no window EV/PnL regression, "
                "drawdown drift <=0.5pp, core survival >=5%, target trades in all "
                "windows, and concentration passing."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260605_035_low_deployment_etf_cash_substitute.py"
            ),
        },
        "gate1": {"baseline_metrics": before_metrics, "passed": True},
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "core baseline trades entry_date",
                "core baseline trades exit_date",
                "ETF Date/Open/Close OHLCV",
                "baseline equity_curve dates",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "minimum_core_survival_rate": min(
                float(row.get("survival_rate") or 0.0) for row in before_metrics.values()
            ),
            "passed": min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
            >= 0.05,
        },
        "gate4": gate4,
        "before_metrics": before_metrics,
        "window_metrics": window_rows,
        "trades_by_window": trades_by_window,
        "diagnostics_by_window": diagnostics_by_window,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "interpretation": (
            "The production-realistic ETF cash-substitute action did not clear "
            "Gate 4 and is not retained or promoted."
            if not gate4["passed"]
            else (
                "The replay lead cleared Gate 4, but remains default-off until "
                "a shared adapter, cash semantics, and parity tests exist."
            )
        ),
        "negative_reflection": (
            "If rejected, the likely reason is that the historical edge in the "
            "same-day raw overlay was mostly intraday/uptrend beta, while the "
            "next-open 10-day constrained sleeve either collides with core "
            "deployment, concentrates in one ETF, or adds market beta without "
            "enough replacement value. Do not retry by changing ETF thresholds, "
            "notional, or hold days without new forward cash/replacement rows."
        ),
        "next_evidence_needed": (
            "Further ETF-cash work needs closed forward replacement-value rows "
            "with actual cash/core-capacity context and concentration controls, "
            "or a materially different free data field. Frozen-window ETF "
            "selector/notional/hold retunes should stay paused."
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(BEFORE_JSON),
            _repo_rel(AFTER_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | dEV | dPnL | Trades | Low-deploy days | Tickers |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for label in WINDOWS:
        row = payload["window_metrics"][label]
        delta = row["delta"]
        tickers = ", ".join(
            f"{ticker}:{count}" for ticker, count in sorted(row["ticker_trade_counts"].items())
        )
        rows.append(
            f"| {label} | {delta.get('expected_value_score', 0.0):+.4f} | "
            f"${delta.get('total_pnl', 0.0):+,.2f} | {row['target_trade_count']} | "
            f"{row['diagnostics']['low_deployment_day_count']} | {tickers or 'none'} |"
        )
    agg = payload["gate4"]["aggregate"]
    concentration = payload["gate4"]["concentration"]
    return "\n".join(
        [
            "---",
            f'experiment_id: "{EXPERIMENT_ID}"',
            f'status: "{payload["status"]}"',
            'lane: "alpha_search"',
            'change_type: "default_off_paper_cash_substitute_sleeve"',
            'mechanism_family: "low_deployment_dynamic_etf_overlay_allocation"',
            f'changed_variable: "{CHANGED_VARIABLE}"',
            f'updated_at: "{payload["timestamp"]}"',
            "---",
            "",
            f"# Experiment Card: {EXPERIMENT_ID}",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "## Three-Window Deltas",
            "",
            *rows,
            "",
            "## Aggregate Gate",
            "",
            f"- EV delta: `{agg['expected_value_score_delta_sum']}` "
            f"(required `{agg['required_expected_value_score_delta_sum']}`)",
            f"- PnL delta: `${agg['total_pnl_delta_sum']}`",
            f"- Target trades: `{agg['target_trade_count_sum']}`",
            f"- Max drawdown delta: `{agg['max_drawdown_delta_max']}`",
            f"- Concentration: `{concentration}`",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "Replay-only/default-off; no production orders changed. No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    gate4 = payload["gate4"]
    aggregate = gate4["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": gate4["passed"],
        "mechanism_family": "low_deployment_dynamic_etf_overlay_allocation",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate4": gate4,
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["window_metrics"][label]["before"][
                    "expected_value_score"
                ],
                "expected_value_after": payload["window_metrics"][label]["after"][
                    "expected_value_score"
                ],
                "expected_value_delta": payload["window_metrics"][label]["delta"][
                    "expected_value_score"
                ],
                "strategy_total_pnl_delta": payload["window_metrics"][label]["delta"][
                    "total_pnl"
                ],
                "target_trade_count": payload["window_metrics"][label]["target_trade_count"],
            }
            for label in WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "anti_js": "No JavaScript was used.",
    }


def _judge_metric_artifacts(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    aggregate = payload["gate4"]["aggregate"]
    min_survival = min(
        float(row.get("survival_rate") or 0.0) for row in payload["before_metrics"].values()
    )
    before = {
        "expected_value_score": aggregate["baseline_expected_value_score_sum"],
        "total_pnl": aggregate["baseline_total_pnl_sum"],
        "max_drawdown_pct": max(
            float(row.get("max_drawdown_pct") or 0.0)
            for row in payload["before_metrics"].values()
        ),
        "survival_rate": min_survival,
        "total_trades": sum(
            int(row.get("trade_count") or 0) for row in payload["before_metrics"].values()
        ),
        "window_count": len(payload["before_metrics"]),
        "source": "aggregate_current_core_baseline_from_docs_backtesting_three_windows",
    }
    after = {
        "expected_value_score": aggregate["after_expected_value_score_sum"],
        "total_pnl": aggregate["after_total_pnl_sum"],
        "max_drawdown_pct": before["max_drawdown_pct"] + aggregate["max_drawdown_delta_max"],
        "survival_rate": min_survival,
        "total_trades": before["total_trades"] + aggregate["target_trade_count_sum"],
        "target_trade_count": aggregate["target_trade_count_sum"],
        "window_count": len(payload["before_metrics"]),
        "source": "aggregate_after_low_deployment_etf_cash_substitute_overlay",
    }
    return before, after


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8")) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "status": payload["status"],
            "owner": "alpha-search",
            "claimed_at": ticket.get("claimed_at") or payload["timestamp"],
            "completed_at": payload["timestamp"],
            "allowed_write_scope": [
                _repo_rel(Path(__file__)),
                _repo_rel(OUT_JSON),
                _repo_rel(BEFORE_JSON),
                _repo_rel(AFTER_JSON),
                _repo_rel(CARD_MD),
                _repo_rel(MANIFEST_JSON),
                _repo_rel(TICKET_JSON),
                _repo_rel(LOG_JSON),
                _repo_rel(EXPERIMENT_LOG),
            ],
            "result": {
                "decision": payload["decision"],
                "artifact": _repo_rel(OUT_JSON),
                "before": _repo_rel(BEFORE_JSON),
                "after": _repo_rel(AFTER_JSON),
                "log": _repo_rel(LOG_JSON),
                "accepted": payload["gate4"]["passed"],
                "aggregate_expected_value_delta": payload["expected_value_score_delta"],
                "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
                "calibration": payload["calibration"],
            },
        }
    )
    _write_json(TICKET_JSON, ticket)


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(BEFORE_JSON),
            _repo_rel(AFTER_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
        ],
        "file_hashes": {
            _repo_rel(Path(__file__)): _sha256(Path(__file__)),
            _repo_rel(OUT_JSON): _sha256(OUT_JSON),
            _repo_rel(BEFORE_JSON): _sha256(BEFORE_JSON),
            _repo_rel(AFTER_JSON): _sha256(AFTER_JSON),
            _repo_rel(LOG_JSON): _sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): _sha256(TICKET_JSON),
            _repo_rel(CARD_MD): _sha256(CARD_MD),
            _repo_rel(EXPERIMENT_LOG): _sha256(EXPERIMENT_LOG),
        },
    }
    _write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    before_judge, after_judge = _judge_metric_artifacts(payload)
    _write_json(OUT_JSON, payload)
    _write_json(BEFORE_JSON, before_judge)
    _write_json(AFTER_JSON, after_judge)
    _write_json(LOG_JSON, payload)
    _write_text(CARD_MD, _build_card(payload))
    _update_ticket(payload)
    _write_manifest(payload)
    _upsert_jsonl(EXPERIMENT_LOG, log_record)


def main() -> None:
    payload = _build_payload()
    persist(payload)
    print(json.dumps(_safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
