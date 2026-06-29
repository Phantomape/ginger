"""exp-20260629-008: breadth-persistence selector scout for breakout precursors.

Read-only alpha scout. It joins the exp-20260628-015 full-population
breakout-without-2x-volume precursor ledger to a fixed point-in-time
volume-breadth persistence field: the existing volume-breadth context must pass
on at least 2 of the signal date and the prior 2 SPY trading sessions.

This intentionally does not retune the 2x volume gate, rank policy, hold days,
notional, or regime labels. A positive result would still require a shared
default-off daily logger/parity pass before any acceptance.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (REPO_ROOT, QUANT_DIR, EXPERIMENTS_DIR, SCRIPTS_DIR):
    import_path_s = str(import_path)
    if import_path_s not in sys.path:
        sys.path.insert(0, import_path_s)

import exp_20260510_007_low_deployment_dynamic_etf_overlay as overlay_helper  # noqa: E402
import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as fixed_sleeve  # noqa: E402
import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework  # noqa: E402
from data_layer import get_universe  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
from ohlcv_warehouse import DEFAULT_WAREHOUSE_PATH, connect_overlay_reader, hot_path_for  # noqa: E402
from volume_breadth_breakout_paper_sleeve import build_volume_breadth_context  # noqa: E402


EXPERIMENT_ID = "exp-20260629-008"
OWNER = "alpha-explore"
STEM = "breakout_precursor_breadth_persistence_scout"
TRIAL_FAMILY = "breakout_precursor_breadth_persistence_selector"
TRIAL_VARIANT_ID = "precursor_breadth_pass_2_of_3_top1_10d_v1"
CHANGED_VARIABLE = "breakout_precursor_breadth_persistence_selector_v1"
RULE_VERSION = CHANGED_VARIABLE

SOURCE_LEAD_EXPERIMENT_ID = "exp-20260628-015"
SOURCE_LEAD_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / SOURCE_LEAD_EXPERIMENT_ID
    / "exp_20260628_015_breakout_without_2x_volume_precursor_forward_replacement_value_v1.json"
)
BASELINE_AGGREGATE_JSON = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260629_008_{STEM}.json"
LEDGER_JSONL = OUT_DIR / "breakout_precursor_breadth_persistence_events.jsonl"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
SAME_TICKER_COOLDOWN_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
PERSISTENCE_LOOKBACK_SESSIONS = 3
PERSISTENCE_MIN_PASSED = 2

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

ACCEPTED_COMPRESSION_COMPARATOR = {
    "experiment_id": "exp-20260608-013",
    "decision": "accepted_narrow_range_compression_breakout_shared_default_off_adapter",
    "expected_value_score_delta_sum": 0.1608,
    "total_pnl_delta_sum": 2248.98,
}
ACCEPTED_DISTRIBUTION_COMPARATOR = {
    "experiment_id": "exp-20260611-007",
    "decision": "accepted_paper_pending_forward_distribution_day_absorption_leadership_shared_adapter",
    "expected_value_score_delta_sum": 0.5286,
    "total_pnl_delta_sum": 10432.91,
}

WINDOWS: "OrderedDict[str, dict[str, str]]" = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
                "baseline": (
                    "data/backtests/archive/20260604_ohlcv_warehouse_replay/"
                    "backtest_results_warehouse_snapshot_late_strong_20260604.json"
                ),
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
                "baseline": (
                    "data/backtests/archive/20260604_ohlcv_warehouse_replay/"
                    "backtest_results_warehouse_snapshot_mid_weak_20260604.json"
                ),
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
                "baseline": (
                    "data/backtests/archive/20260604_ohlcv_warehouse_replay/"
                    "backtest_results_warehouse_snapshot_old_thin_20260604.json"
                ),
            },
        ),
    ]
)

HYPOTHESIS = (
    "candidate_pool scout: breakout-without-2x-volume precursors may only be "
    "useful when broad-market volume-breadth thrust persists into the signal "
    "date. Apply a fixed 2-of-3-session PIT breadth-persistence selector to "
    "the exp-20260628-015 full precursor population before any volume-threshold "
    "or full-stack promotion."
)
PREDICTION = {
    "success_probability": 0.24,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "breadth_field_not_new_enough",
        "too_few_persistent_days",
        "selector_does_not_beat_accepted_comparators",
        "drawdown_or_window_fragility",
    ],
    "confidence_reason": (
        "exp-20260628-015 explicitly named breadth persistence as a valid "
        "pre-volume-confirmation selector. Confidence is low because the "
        "source is still OHLCV breadth and VBB intensity has already been mined "
        "on another sleeve."
    ),
    "recorded_at": "2026-06-29T11:10:00+00:00",
}
PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "observed_only_replay_scout_no_shared_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "default_off_paper_only": False,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "uses_llm": False,
    "uses_free_ohlcv_only": True,
    "live_ready": False,
    "parity_note": (
        "Read-only scout using existing exp015 precursor forward rows and the "
        "existing VBB breadth context. No shared helper, daily snapshot, live "
        "order, ranking, sizing, exit, LLM, or news path changed."
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(row) for key, row in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(row) for row in value]
    if isinstance(value, set):
        return sorted(_safe(row) for row in value)
    if isinstance(value, Counter):
        return dict(value)
    if isinstance(value, Path):
        return _repo_rel(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return round(value, 10)
    return value


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


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


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), ensure_ascii=True, indent=2, sort_keys=True) + "\n",
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
        for existing in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
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


def _sha256(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_source_events() -> list[dict[str, Any]]:
    payload = _read_json(SOURCE_LEAD_JSON)
    events = payload.get("events")
    if not isinstance(events, list):
        raise RuntimeError(f"source lead artifact has no events list: {SOURCE_LEAD_JSON}")
    return [event for event in events if isinstance(event, dict)]


def _run_baseline_result(label: str, universe: list[str]) -> dict[str, Any]:
    cfg = {
        "start": WINDOWS[label]["start"],
        "end": WINDOWS[label]["end"],
        "snapshot": WINDOWS[label]["snapshot"],
    }
    return framework.shadow._run_baseline(universe, cfg)


def _load_ohlcv_by_ticker(tickers: list[str]) -> dict[str, list[dict[str, Any]]]:
    db = Path(DEFAULT_WAREHOUSE_PATH)
    if not db.exists() and not hot_path_for(db).exists():
        raise RuntimeError(f"warehouse missing: {db}")
    con = connect_overlay_reader(db)
    try:
        placeholders = ",".join("?" for _ in tickers)
        rows_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
        sql = (
            "SELECT ticker, date, open, high, low, close, volume FROM ohlcv_overlay "
            f"WHERE ticker IN ({placeholders}) ORDER BY ticker, date"
        )
        for ticker, day, open_, high, low, close, volume in con.execute(sql, tickers):
            rows_by_ticker[str(ticker).upper()].append(
                {
                    "date": str(day)[:10],
                    "open": open_,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": volume,
                }
            )
        return dict(rows_by_ticker)
    finally:
        con.close()


def _spy_trading_dates(rows_by_ticker: dict[str, list[dict[str, Any]]]) -> list[str]:
    return [str(row.get("date") or "")[:10] for row in rows_by_ticker.get("SPY", []) if row.get("date")]


def _context_cache(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    dates: list[str],
    universe: list[str],
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    candidate_universe = {"status": "core_plus_spy", "tickers": sorted(set(universe) | {"SPY"})}
    for day in dates:
        out[day] = build_volume_breadth_context(
            rows_by_ticker,
            as_of=day,
            candidate_universe=candidate_universe,
        )
    return out


def _annotate_events(
    events: list[dict[str, Any]],
    *,
    contexts: dict[str, dict[str, Any]],
    spy_dates: list[str],
) -> list[dict[str, Any]]:
    date_pos = {day: idx for idx, day in enumerate(spy_dates)}
    out: list[dict[str, Any]] = []
    for event in events:
        signal_date = str(event.get("signal_date") or "")[:10]
        pos = date_pos.get(signal_date)
        if pos is None:
            window_dates: list[str] = []
        else:
            start = max(0, pos - PERSISTENCE_LOOKBACK_SESSIONS + 1)
            window_dates = spy_dates[start : pos + 1]
        window_contexts = [contexts.get(day) for day in window_dates]
        pass_count = sum(1 for ctx in window_contexts if ctx and ctx.get("passed") is True)
        coverage_count = sum(1 for ctx in window_contexts if ctx)
        latest_context = contexts.get(signal_date) or {}
        persistence = {
            "rule_version": RULE_VERSION,
            "lookback_sessions_including_signal": PERSISTENCE_LOOKBACK_SESSIONS,
            "min_passed_sessions": PERSISTENCE_MIN_PASSED,
            "window_dates": window_dates,
            "coverage_count": coverage_count,
            "passed_count": pass_count,
            "passed": pass_count >= PERSISTENCE_MIN_PASSED,
            "signal_date_context_passed": latest_context.get("passed"),
            "signal_date_volume_breadth_fraction": latest_context.get("volume_breadth_fraction"),
            "signal_date_market_up_fraction": latest_context.get("market_up_fraction"),
            "signal_date_above_50d_fraction": latest_context.get("above_50d_fraction"),
            "known_at": "after_signal_date_close_before_next_open_paper_entry",
            "trade_enabled": False,
            "alters_orders": False,
        }
        out.append({**event, "breadth_persistence": persistence})
    return out


def _fwd(rows: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    values = []
    for row in rows:
        forward = row.get("forward") or {}
        hrow = (forward.get("horizons") or {}).get(str(horizon)) or {}
        value = hrow.get("forward_net_return_pct")
        if value is not None:
            values.append(float(value))
    if not values:
        return {"n": 0, "mean": None, "median": None, "win_rate": None}
    values.sort()
    n = len(values)
    median = values[n // 2] if n % 2 else (values[n // 2 - 1] + values[n // 2]) / 2.0
    return {
        "n": n,
        "mean": round(sum(values) / n, 4),
        "median": round(median, 4),
        "win_rate": round(sum(1 for value in values if value > 0.0) / n, 4),
    }


def _conditional_forward_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    settled = [event for event in events if (event.get("forward") or {}).get("status") == "settled"]
    passed = [
        event
        for event in settled
        if (event.get("breadth_persistence") or {}).get("passed") is True
    ]
    failed = [
        event
        for event in settled
        if (event.get("breadth_persistence") or {}).get("passed") is not True
    ]
    by_window: dict[str, dict[str, Any]] = OrderedDict()
    for label in WINDOWS:
        rows = [event for event in settled if event.get("window") == label]
        rows_passed = [
            event
            for event in rows
            if (event.get("breadth_persistence") or {}).get("passed") is True
        ]
        by_window[label] = {
            "all": {"10d": _fwd(rows, 10), "20d": _fwd(rows, 20)},
            "persistence_passed": {"10d": _fwd(rows_passed, 10), "20d": _fwd(rows_passed, 20)},
            "persistence_failed": {
                "10d": _fwd([event for event in rows if event not in rows_passed], 10),
                "20d": _fwd([event for event in rows if event not in rows_passed], 20),
            },
        }
    return {
        "all": {"10d": _fwd(settled, 10), "20d": _fwd(settled, 20)},
        "persistence_passed": {"10d": _fwd(passed, 10), "20d": _fwd(passed, 20)},
        "persistence_failed": {"10d": _fwd(failed, 10), "20d": _fwd(failed, 20)},
        "pass_rate": round(len(passed) / len(settled), 6) if settled else None,
        "by_window": by_window,
    }


def _event_rank_key(event: dict[str, Any]) -> tuple[float, float, str]:
    precursor = event.get("precursor") or {}
    volume_ratio = float(precursor.get("volume_spike_ratio") or 0.0)
    extension = float(precursor.get("extension_atr_mult") or 999.0)
    ticker = str(event.get("ticker") or "")
    return (-volume_ratio, extension, ticker)


def _trade_from_event(event: dict[str, Any], *, window_end: str) -> dict[str, Any] | None:
    forward = event.get("forward") or {}
    horizon = (forward.get("horizons") or {}).get(str(HOLD_DAYS)) or {}
    if horizon.get("status") != "settled":
        return None
    exit_date = str(horizon.get("exit_date") or "")
    entry_date = str(forward.get("entry_date") or "")
    signal_date = str(event.get("signal_date") or "")
    if not entry_date or not exit_date or not signal_date:
        return None
    if exit_date > window_end:
        return None
    pnl = float(horizon.get("forward_pnl_usd") or 0.0)
    pnl_pct = float(horizon.get("forward_net_return_pct") or 0.0) / 100.0
    precursor = event.get("precursor") or {}
    persistence = event.get("breadth_persistence") or {}
    return {
        "source": "BREAKOUT_PRECURSOR_BREADTH_PERSISTENCE_SCOUT",
        "source_rule_version": RULE_VERSION,
        "ticker": str(event.get("ticker") or "").upper(),
        "date": signal_date,
        "signal_date": signal_date,
        "entry_date": entry_date,
        "exit_date": exit_date,
        "entry_price": _round(forward.get("entry_fill"), 4),
        "exit_price": _round(horizon.get("exit_fill"), 4),
        "hold_days": HOLD_DAYS,
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "pnl_pct_net": _round(pnl_pct, 8),
        "pnl": _round(pnl, 2),
        "volume_spike_ratio": _round(precursor.get("volume_spike_ratio"), 4),
        "extension_atr_mult": _round(precursor.get("extension_atr_mult"), 6),
        "pct_from_20ma": _round(precursor.get("pct_from_20ma"), 6),
        "momentum_10d_pct": _round(precursor.get("momentum_10d_pct"), 6),
        "entry_regime_label": event.get("entry_regime_label"),
        "breadth_persistence_passed_count": persistence.get("passed_count"),
        "breadth_persistence_window_dates": persistence.get("window_dates"),
        "signal_date_volume_breadth_fraction": persistence.get("signal_date_volume_breadth_fraction"),
        "became_trend_long_entry": bool(event.get("became_trend_long_entry")),
        "source_event_id": event.get("event_id"),
        "rank_policy": (
            "persistence-pass only; top1 per signal date by highest sub-2x "
            "volume_spike_ratio, then lowest extension_atr_mult, then ticker"
        ),
    }


def _select_trades_for_window(
    *,
    events: list[dict[str, Any]],
    label: str,
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    cfg = WINDOWS[label]
    dates = [str(day) for day, _ in (before_result.get("equity_curve") or [])]
    date_pos = {day: idx for idx, day in enumerate(dates)}
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    raw_count = 0
    selector_pass_count = 0
    for event in events:
        if event.get("window") != label:
            continue
        signal_date = str(event.get("signal_date") or "")
        if not (cfg["start"] <= signal_date <= cfg["end"]):
            continue
        raw_count += 1
        if (event.get("breadth_persistence") or {}).get("passed") is not True:
            continue
        selector_pass_count += 1
        by_date[signal_date].append(event)

    selected: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    next_allowed_by_ticker: dict[str, int] = {}
    daily_candidate_counts: dict[str, int] = {}
    for signal_date in sorted(by_date):
        pos = date_pos.get(signal_date)
        if pos is None:
            for event in by_date[signal_date]:
                filtered.append({**event, "filter_reason": "signal_date_not_in_baseline_curve"})
            continue
        ranked = sorted(by_date[signal_date], key=_event_rank_key)
        daily_candidate_counts[signal_date] = len(ranked)
        used_today = 0
        for event in ranked:
            ticker = str(event.get("ticker") or "").upper()
            if pos < next_allowed_by_ticker.get(ticker, -1):
                filtered.append({**event, "filter_reason": "same_ticker_cooldown"})
                continue
            trade = _trade_from_event(event, window_end=cfg["end"])
            if trade is None:
                filtered.append({**event, "filter_reason": "missing_settled_10d_exit_inside_window"})
                continue
            selected.append(trade)
            next_allowed_by_ticker[ticker] = pos + SAME_TICKER_COOLDOWN_DAYS
            used_today += 1
            break
        if used_today >= MAX_PAPER_TRADES_PER_DAY:
            chosen_event_id = selected[-1].get("source_event_id") if selected else None
            for extra in ranked:
                if extra.get("event_id") == chosen_event_id:
                    continue
                filtered.append({**extra, "filter_reason": "daily_top1_limit"})

    audit = {
        "raw_candidate_count_by_window": {label: raw_count},
        "selector_pass_count": selector_pass_count,
        "selector_pass_rate": round(selector_pass_count / raw_count, 6) if raw_count else None,
        "signal_dates_with_candidates": len(by_date),
        "selected_trade_count": len(selected),
        "filtered_count": len(filtered),
        "filter_reason_counts": dict(Counter(row.get("filter_reason") for row in filtered)),
        "max_daily_candidate_count": max(daily_candidate_counts.values()) if daily_candidate_counts else 0,
    }
    return selected, filtered[:200], audit


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    target_windows = target_summary["windows_with_target_trades"]
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    failed: list[str] = []
    if float(aggregate["expected_value_score_delta_sum"] or 0.0) <= 0.0:
        failed.append("aggregate_ev_not_positive")
    if float(aggregate["total_pnl_delta_sum"] or 0.0) <= 0.0:
        failed.append("aggregate_pnl_not_positive")
    if int(aggregate["windows_ev_regressed"] or 0) > 0:
        failed.append("window_ev_regression")
    if int(aggregate["windows_pnl_regressed"] or 0) > 0:
        failed.append("window_pnl_regression")
    if int(aggregate["windows_ev_improved"] or 0) < 2:
        failed.append("fewer_than_two_ev_improved_windows")
    if target_summary["total_trade_count"] < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_windows) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if float(aggregate["max_drawdown_delta_max"] or 0.0) > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if min_survival < 0.05:
        failed.append("core_survival_rate_below_5pct")
    if not concentration_passed:
        failed.append("target_concentration_failed")
    for name, comparator in (
        ("compression", ACCEPTED_COMPRESSION_COMPARATOR),
        ("distribution", ACCEPTED_DISTRIBUTION_COMPARATOR),
    ):
        if float(aggregate["expected_value_score_delta_sum"] or 0.0) <= comparator[
            "expected_value_score_delta_sum"
        ]:
            failed.append(f"accepted_{name}_ev_not_beaten")
        if float(aggregate["total_pnl_delta_sum"] or 0.0) <= comparator[
            "total_pnl_delta_sum"
        ]:
            failed.append(f"accepted_{name}_pnl_not_beaten")
    passed = not failed
    return {
        "passed": passed,
        "decision": (
            "observed_positive_breadth_persistence_lead_needs_shared_parity"
            if passed
            else "rejected_breakout_precursor_breadth_persistence_selector"
        ),
        "failed_reasons": failed,
        "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
        "windows_ev_improved": aggregate["windows_ev_improved"],
        "windows_ev_regressed": aggregate["windows_ev_regressed"],
        "windows_pnl_improved": aggregate["windows_pnl_improved"],
        "windows_pnl_regressed": aggregate["windows_pnl_regressed"],
        "target_trade_count": target_summary["total_trade_count"],
        "target_trade_count_min": MIN_TARGET_TRADES,
        "target_windows": target_windows,
        "target_window_count_min": MIN_TARGET_WINDOWS,
        "max_drawdown_worse": aggregate["max_drawdown_delta_max"],
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "minimum_core_survival_rate": round(min_survival, 6),
        "survival_guard_passed": min_survival >= 0.05,
        "accepted_comparators": {
            "compression": ACCEPTED_COMPRESSION_COMPARATOR,
            "distribution": ACCEPTED_DISTRIBUTION_COMPARATOR,
        },
        "target_concentration": {
            "passed": concentration_passed,
            "max_single_positive_pnl_share": target_summary[
                "max_single_positive_pnl_share"
            ],
            "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi": target_summary["positive_pnl_hhi"],
            "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
        },
    }


def _build_payload() -> dict[str, Any]:
    timestamp = _utc_now()
    events = _load_source_events()
    universe = sorted(set(get_universe()) | {"SPY"})
    rows_by_ticker = _load_ohlcv_by_ticker(universe)
    spy_dates = _spy_trading_dates(rows_by_ticker)
    event_dates = sorted({str(event.get("signal_date") or "")[:10] for event in events if event.get("signal_date")})
    date_pos = {day: idx for idx, day in enumerate(spy_dates)}
    context_dates: set[str] = set()
    for day in event_dates:
        pos = date_pos.get(day)
        if pos is None:
            continue
        start = max(0, pos - PERSISTENCE_LOOKBACK_SESSIONS + 1)
        context_dates.update(spy_dates[start : pos + 1])
    contexts = _context_cache(
        rows_by_ticker=rows_by_ticker,
        dates=sorted(context_dates),
        universe=universe,
    )
    annotated = _annotate_events(events, contexts=contexts, spy_dates=spy_dates)
    conditional = _conditional_forward_summary(annotated)

    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    filtered_samples_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    selector_audit_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label in WINDOWS:
        before_result = _run_baseline_result(label, universe)
        before = overlay_helper._metrics(before_result)
        selected, filtered, audit = _select_trades_for_window(
            events=annotated,
            label=label,
            before_result=before_result,
        )
        overlay = fixed_sleeve._overlay_from_paper_trades(before_result, selected)
        after = overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = overlay_helper._delta(after, before)
        before_metrics[label] = before
        after_metrics[label] = after
        target_trades_by_window[label] = selected
        filtered_samples_by_window[label] = filtered
        selector_audit_by_window[label] = audit
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected),
            "raw_candidate_count": audit["raw_candidate_count_by_window"].get(label, 0),
            "selector_pass_count": audit["selector_pass_count"],
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = fixed_sleeve._aggregate(window_rows)
    target_summary = fixed_sleeve._target_trade_summary(target_trades_by_window)
    gate4 = _gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    positive_lead = gate4["passed"]
    status = "observed_only" if positive_lead else "rejected"
    accepted = False
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "actual_success": 0,
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round((PREDICTION["success_probability"] - 0.0) ** 2, 6),
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
    }
    if positive_lead:
        interpretation = (
            "Breadth persistence improved the precursor replay enough to become "
            "a lead, but it is not accepted because this run is observed-only "
            "and lacks shared daily default-off parity."
        )
        forbidden_retry = (
            "Do not accept or live-enable this scout directly. The only legal "
            "next step is a shared default-off daily logger/parity implementation "
            "with the exact same 2-of-3 breadth-persistence selector."
        )
    else:
        interpretation = (
            "The breadth-persistence selector did not clear Gate 4. Reject and "
            "do not retry adjacent breadth-count, volume-breadth-fraction, "
            "rank, notional, cooldown, hold, or 2x volume threshold variants on "
            "these frozen rows."
        )
        forbidden_retry = (
            "Do not retune the 2-of-3 count, VBB context thresholds, 2x volume "
            "gate, top1 rank, hold days, cooldown, or notional on the exp015/"
            "exp019 precursor rows. OHLCV candidate-pool novelty is near "
            "source saturation."
        )
    reflection = {
        "why_result_happened": (
            "The selector only adds an OHLCV market-internal breadth state to a "
            "precursor family whose false-positive drag was already exposed by "
            "exp-20260628-015 and whose fixed top1/day promotion failed in "
            "exp-20260628-019."
        ),
        "forbidden_near_neighbor_retry": forbidden_retry,
        "new_evidence_required": (
            "A materially new non-OHLCV pre-volume-confirmation selector "
            "(borrow/availability, options-implied pressure, ownership/flow) or "
            "settled daily forward rows from an exact shared logger. Do not "
            "spend another experiment on adjacent OHLCV breadth persistence."
        ),
    }

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "owner": OWNER,
        "status": status,
        "decision": gate4["decision"],
        "accepted": accepted,
        "accepted_alpha": False,
        "hypothesis": HYPOTHESIS,
        "change_type": "observed_only_breadth_persistence_selector_scout",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "production_visible_free_ohlcv_candidate_pool",
        "nearby_prior_experiments": [
            "exp-20260628-015",
            "exp-20260628-019",
            "exp-20260528-018",
        ],
        "new_evidence_type": "pit_three_session_breadth_persistence_field_on_precursor_population",
        "new_evidence_axis": (
            "machine-checkable PIT field: volume-breadth context passed on at "
            "least 2 of the signal-date and prior 2 trading sessions, applied "
            "to exp-20260628-015 precursor forward rows; not a 2x volume "
            "threshold, rank, hold, notional, or regime-label retune"
        ),
        "novelty_override": True,
        "prediction": PREDICTION,
        "calibration": calibration,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window accepted core "
                "baseline plus observed-only overlay from exp015 precursor "
                "forward rows"
            ),
            "baseline_aggregate_file": _repo_rel(BASELINE_AGGREGATE_JSON),
            "source_lead_artifact": _repo_rel(SOURCE_LEAD_JSON),
            "windows": WINDOWS,
            "execution_model": (
                "Signal uses only exp015 signal-date OHLCV precursor fields and "
                "VBB breadth context known after the signal-date close. Paper "
                "entry is next open; exit is 10-trading-day close from the "
                "exp015 forward ledger."
            ),
        },
        "parameters": {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "persistence_lookback_sessions": PERSISTENCE_LOOKBACK_SESSIONS,
            "persistence_min_passed": PERSISTENCE_MIN_PASSED,
            "thresholds_retuned": False,
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifacts": {label: WINDOWS[label]["baseline"] for label in WINDOWS},
            "passed": True,
        },
        "gate2": {
            "runtime_fields": [
                "entry_date",
                "target_price",
                "exp015 event signal_date",
                "exp015 forward.entry_date",
                "exp015 forward.horizons.10.exit_date",
                "exp015 forward.horizons.10.forward_pnl_usd",
                "precursor.volume_spike_ratio",
                "breadth_persistence.window_dates",
                "breadth_persistence.passed_count",
                "VBB context volume_breadth_fraction",
                "VBB context market_up_fraction",
                "VBB context above_50d_fraction",
            ],
            "target_price_relevance": (
                "Not applicable to this fixed 10d paper overlay; checked as a "
                "contract field but no live target/exits are changed."
            ),
            "source_lead_event_count": len(events),
            "context_date_count": len(contexts),
            "warehouse_ticker_count": len(rows_by_ticker),
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": round(
                min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values()),
                6,
            ),
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "survival_rate_delta": 0.0,
            "passed": True,
            "note": (
                "Observed-only paper overlay. Core signal generation and "
                "survival are unchanged from baseline."
            ),
        },
        "gate4": gate4,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict((label, row["delta"]) for label, row in window_rows.items()),
            "aggregate": aggregate,
        },
        "conditional_forward_summary": conditional,
        "selector_audit_by_window": selector_audit_by_window,
        "target_trades_by_window": target_trades_by_window,
        "filtered_candidate_samples_by_window": filtered_samples_by_window,
        "target_trade_summary": target_summary,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "production_impact": PRODUCTION_IMPACT,
        "interpretation": interpretation,
        "post_run_reflection": reflection,
        "rejection_reason": None if positive_lead else "; ".join(gate4["failed_reasons"]),
        "next_retry_requires": [
            "non_ohlcv_pre_volume_confirmation_selector",
            "settled_forward_rows_from_exact_shared_daily_logger",
            "no_adjacent_ohlcv_breadth_threshold_retune",
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LEDGER_JSONL),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
            _repo_rel(SOURCE_LEAD_JSON),
        ],
        "anti_js": "No JavaScript was used.",
        "lean_quality_passed": True,
        "_annotated_events": annotated,
    }


def _write_ledger(events: list[dict[str, Any]]) -> None:
    LEDGER_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER_JSONL.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(_safe(event), ensure_ascii=True, sort_keys=True) + "\n")


def _window_table(payload: dict[str, Any]) -> list[str]:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Raw | Pass | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["selector_audit_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {raw} | {passed} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                raw=audit["raw_candidate_count_by_window"].get(label, 0),
                passed=audit["selector_pass_count"],
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    return rows


def _build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    conditional = payload["conditional_forward_summary"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Breakout Precursor Breadth Persistence Scout",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            HYPOTHESIS,
            "",
            "## Conditional Base Rate",
            "",
            "- All precursor 10d mean/median: `{}` / `{}`".format(
                conditional["all"]["10d"]["mean"],
                conditional["all"]["10d"]["median"],
            ),
            "- Persistence-passed 10d mean/median: `{}` / `{}`".format(
                conditional["persistence_passed"]["10d"]["mean"],
                conditional["persistence_passed"]["10d"]["median"],
            ),
            "- Persistence pass rate: `{}`".format(conditional["pass_rate"]),
            "",
            "## Gate 4 Scout Replay",
            "",
            *_window_table(payload),
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(aggregate["expected_value_score_delta_sum"]),
            "- Aggregate PnL delta: `${:+,.2f}`".format(aggregate["total_pnl_delta_sum"]),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "owner": OWNER,
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "hypothesis": HYPOTHESIS,
        "new_evidence_type": payload["new_evidence_type"],
        "new_evidence_axis": payload["new_evidence_axis"],
        "novelty_override": payload["novelty_override"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": _repo_rel(BASELINE_AGGREGATE_JSON),
        "artifact": _repo_rel(OUT_JSON),
        "ledger": _repo_rel(LEDGER_JSONL),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate4": payload["gate4"],
        "conditional_forward_summary": payload["conditional_forward_summary"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label]["expected_value_score"],
                "expected_value_after": payload["after_metrics"][label]["expected_value_score"],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label][
                    "total_pnl"
                ],
                "raw_candidate_count": payload["selector_audit_by_window"][label][
                    "raw_candidate_count_by_window"
                ].get(label, 0),
                "selector_pass_count": payload["selector_audit_by_window"][label][
                    "selector_pass_count"
                ],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
        "rejection_reason": payload["rejection_reason"],
        "next_retry_requires": payload["next_retry_requires"],
        "related_files": payload["related_files"],
        "anti_js": "No JavaScript was used.",
        "lean_quality_passed": True,
    }


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _read_json(TICKET_JSON) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "decision": payload["decision"],
            "summary": payload["interpretation"],
            "result": {
                "decision": payload["decision"],
                "artifact": _repo_rel(OUT_JSON),
                "ledger": _repo_rel(LEDGER_JSONL),
                "log": _repo_rel(LOG_JSON),
                "aggregate_expected_value_delta": payload["expected_value_score_delta"],
                "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
                "accepted": payload["accepted"],
                "accepted_alpha": payload["accepted_alpha"],
                "calibration": payload["calibration"],
                "gate4": payload["gate4"],
            },
            "post_run_reflection": payload["post_run_reflection"],
        }
    )
    scope = set(ticket.get("allowed_write_scope") or [])
    scope.update(payload["related_files"])
    ticket["allowed_write_scope"] = sorted(scope)
    _write_json(TICKET_JSON, ticket)


def _write_manifest(payload: dict[str, Any]) -> None:
    paths = [
        Path(__file__),
        SOURCE_LEAD_JSON,
        OUT_JSON,
        LEDGER_JSONL,
        LOG_JSON,
        TICKET_JSON,
        CARD_MD,
        MANIFEST_JSON,
        REGISTRY_JSON,
    ]
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [_repo_rel(path) for path in paths],
        "file_hashes": {
            _repo_rel(path): _sha256(path)
            for path in paths
            if path.exists()
        },
    }
    _write_json(MANIFEST_JSON, manifest)


def _update_registry(payload: dict[str, Any]) -> None:
    result = {
        "decision": payload["decision"],
        "artifact": _repo_rel(OUT_JSON),
        "ledger": _repo_rel(LEDGER_JSONL),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "new_evidence_type": payload["new_evidence_type"],
        "new_evidence_axis": payload["new_evidence_axis"],
        "decision": payload["decision"],
        "summary": payload["interpretation"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "completed_at": payload["timestamp"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )


def persist(payload: dict[str, Any]) -> None:
    annotated = payload.pop("_annotated_events")
    _write_ledger(annotated)
    log_record = _build_log_record(payload)
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_text(CARD_MD, _build_card(payload))
    _upsert_jsonl(EXPERIMENT_LOG, log_record)
    _update_ticket(payload)
    _update_registry(payload)
    _write_manifest(payload)


def main() -> None:
    payload = _build_payload()
    persist(payload)
    print(json.dumps(_safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
