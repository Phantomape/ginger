"""exp-20260613-019: post-thrust pause quality candidate pool.

Replay-only alpha search. It tests one production-visible broad OHLCV tail
state: a liquid stock with a strong thrust day, an orderly 1-3 day pause, and
a controlled reclaim near the pause high.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
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
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
LEGACY_DIR = EXPERIMENTS_DIR / "legacy"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, EXPERIMENTS_DIR, LEGACY_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


shadow = framework.shadow
overlay_helper = framework.overlay_helper
sleeve = framework.sleeve
get_universe = framework.get_universe

EXPERIMENT_ID = "exp-20260613-019"
STEM = "post_thrust_pause_quality"
TRIAL_FAMILY = "post_thrust_pause_quality_candidate_pool"
TRIAL_VARIANT_ID = "post_thrust_pause_quality_top1_next_open_10d_v1"
CHANGED_VARIABLE = "post_thrust_pause_quality_bucket_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260613_019_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 10

PAUSE_LENGTHS = (1, 2, 3)
MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_THRUST_RETURN = 0.055
MIN_THRUST_RELATIVE_SPY = 0.040
MIN_THRUST_CLOSE_LOCATION = 0.75
MIN_THRUST_VOLUME_RATIO_20D = 1.35
MAX_PAUSE_DRAWDOWN_FROM_THRUST_CLOSE = -0.070
MAX_PAUSE_HIGH_EXTENSION_FROM_THRUST_HIGH = 0.025
MAX_PAUSE_VOLUME_RATIO_20D = 2.20
MIN_SIGNAL_CLOSE_LOCATION = 0.65
MIN_SIGNAL_RETURN = -0.005
MAX_SIGNAL_RETURN = 0.050
MIN_SIGNAL_VOLUME_RATIO_20D = 0.45
MAX_SIGNAL_VOLUME_RATIO_20D = 2.60
MIN_SIGNAL_RECLAIM_OF_PAUSE_HIGH = -0.005
MIN_RET20_EXCESS_SPY = 0.000
MAX_RET5 = 0.180
MAX_REALIZED_VOL_20D = 0.090

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

WINDOWS = framework.WINDOWS

PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": 0.2,
    "expected_pnl_delta": 3000.0,
    "main_failure_modes": [
        "window_regression",
        "drawdown_drift_too_high",
        "gap_chase_noise",
        "post_thrust_inside_day_repeat",
        "target_sample_too_small",
    ],
    "confidence_reason": (
        "The playbook asks for tail-state field building, but nearby gap-hold "
        "and post-thrust scouts failed. An orderly multi-day pause plus reclaim "
        "is materially more specific yet still broad-OHLCV and production-visible."
    ),
    "recorded_at": "2026-06-13T15:09:35Z",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_no_live_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "default_off_paper_only": True,
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
    "live_realism_evaluated": True,
    "live_ready": False,
    "execution_envelope": {
        "trade_enabled": False,
        "target_notional_per_paper_trade": BASE_NOTIONAL_USD,
        "daily_entry_slots": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "hold_days": HOLD_DAYS,
        "liquidity_source": "price >= $10 and ADV20 >= $50M from PIT OHLCV",
        "order_semantics": "observe-only next-session-open paper entry; no broker order",
        "portfolio_displacement": "none unless a later shared helper and activation gate pass",
        "kill_switch": "trade_enabled remains false; no production adapter changes",
        "failure_handling": "missing OHLCV, next open, or exit close rejects the paper candidate",
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same "
        "thrust, pause, reclaim, liquidity, same-ticker core-overlap exclusion, "
        "cooldown, next-open paper entry, 10-trading-day exit, costs, and "
        "concentration controls in both historical replay and the daily snapshot."
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _round(value: Any, digits: int = 6) -> float | None:
    return framework._round(value, digits)


def _repo_rel(path: Path | str) -> str:
    return framework._repo_rel(path)


def _safe(payload: Any) -> Any:
    return framework._safe(payload)


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


def _patch_framework_globals() -> None:
    framework.EXPERIMENT_ID = EXPERIMENT_ID
    framework.STEM = STEM
    framework.TRIAL_FAMILY = TRIAL_FAMILY
    framework.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    framework.CHANGED_VARIABLE = CHANGED_VARIABLE
    framework.RULE_VERSION = RULE_VERSION
    framework.OUT_DIR = OUT_DIR
    framework.OUT_JSON = OUT_JSON
    framework.LOG_JSON = LOG_JSON
    framework.TICKET_JSON = TICKET_JSON
    framework.CARD_MD = CARD_MD
    framework.MANIFEST_JSON = MANIFEST_JSON
    framework.EXPERIMENT_LOG = EXPERIMENT_LOG
    framework.REGISTRY_JSON = REGISTRY_JSON
    framework.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    framework.HOLD_DAYS = HOLD_DAYS
    framework.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    framework.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    framework.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    framework.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    framework.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    framework.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    sleeve.EXPERIMENT_ID = EXPERIMENT_ID
    sleeve.STEM = STEM
    sleeve.TRIAL_FAMILY = TRIAL_FAMILY
    sleeve.CHANGED_VARIABLE = CHANGED_VARIABLE
    sleeve.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    sleeve.HOLD_DAYS = HOLD_DAYS
    sleeve.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    sleeve.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    sleeve.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    sleeve.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    sleeve.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    sleeve.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    sleeve.OUT_DIR = OUT_DIR
    sleeve.OUT_JSON = OUT_JSON
    sleeve.LOG_JSON = LOG_JSON
    sleeve.TICKET_JSON = TICKET_JSON
    sleeve.CARD_MD = CARD_MD
    sleeve.EXPERIMENT_LOG = EXPERIMENT_LOG


def _candidate_for_pause_length(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    pause_len: int,
) -> dict[str, Any] | None:
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None:
        return None
    thrust_idx = idx - pause_len - 1
    if thrust_idx < 20 or spy_idx < 20:
        return None

    row = rows[idx]
    close = framework._value(row, "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None

    thrust_row = rows[thrust_idx]
    thrust_return = framework._daily_return(rows, thrust_idx)
    spy_thrust_return = framework._daily_return(spy_rows, spy_idx - pause_len - 1)
    if thrust_return is None or spy_thrust_return is None:
        return None
    thrust_relative_spy = thrust_return - spy_thrust_return
    if thrust_return < MIN_THRUST_RETURN or thrust_relative_spy < MIN_THRUST_RELATIVE_SPY:
        return None
    thrust_close_location = framework._close_location(thrust_row)
    if thrust_close_location is None or thrust_close_location < MIN_THRUST_CLOSE_LOCATION:
        return None
    thrust_volume_ratio = framework._volume_ratio(rows, thrust_idx) or 0.0
    if thrust_volume_ratio < MIN_THRUST_VOLUME_RATIO_20D:
        return None

    thrust_close = framework._value(thrust_row, "Close")
    thrust_high = framework._value(thrust_row, "High")
    if thrust_close is None or thrust_close <= 0 or thrust_high is None:
        return None
    pause_rows = rows[thrust_idx + 1 : idx]
    if len(pause_rows) != pause_len:
        return None
    pause_lows = [framework._value(day, "Low") for day in pause_rows]
    pause_highs = [framework._value(day, "High") for day in pause_rows]
    pause_closes = [framework._value(day, "Close") for day in pause_rows]
    if any(value is None for value in pause_lows + pause_highs + pause_closes):
        return None
    pause_low = min(float(value) for value in pause_lows if value is not None)
    pause_high = max(float(value) for value in pause_highs if value is not None)
    pause_last_close = float(pause_closes[-1])
    pause_drawdown = (pause_low / thrust_close) - 1.0
    if pause_drawdown < MAX_PAUSE_DRAWDOWN_FROM_THRUST_CLOSE:
        return None
    pause_high_extension = (pause_high / thrust_high) - 1.0
    if pause_high_extension > MAX_PAUSE_HIGH_EXTENSION_FROM_THRUST_HIGH:
        return None
    pause_volume_ratios = [
        framework._volume_ratio(rows, day_idx) or 0.0 for day_idx in range(thrust_idx + 1, idx)
    ]
    pause_volume_ratio_max = max(pause_volume_ratios) if pause_volume_ratios else 0.0
    if pause_volume_ratio_max > MAX_PAUSE_VOLUME_RATIO_20D:
        return None

    signal_return = framework._daily_return(rows, idx)
    if signal_return is None or signal_return < MIN_SIGNAL_RETURN or signal_return > MAX_SIGNAL_RETURN:
        return None
    close_location = framework._close_location(row)
    if close_location is None or close_location < MIN_SIGNAL_CLOSE_LOCATION:
        return None
    signal_volume_ratio = framework._volume_ratio(rows, idx) or 0.0
    if (
        signal_volume_ratio < MIN_SIGNAL_VOLUME_RATIO_20D
        or signal_volume_ratio > MAX_SIGNAL_VOLUME_RATIO_20D
    ):
        return None
    signal_reclaim_vs_pause_high = (close / pause_high) - 1.0
    if signal_reclaim_vs_pause_high < MIN_SIGNAL_RECLAIM_OF_PAUSE_HIGH:
        return None

    ret5 = framework._ret(rows, idx, 5)
    ret20 = framework._ret(rows, idx, 20)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    if ret5 is None or ret20 is None or spy_ret20 is None:
        return None
    ret20_excess_spy = ret20 - spy_ret20
    if ret20_excess_spy < MIN_RET20_EXCESS_SPY or ret5 > MAX_RET5:
        return None
    realized_vol = framework._realized_vol(rows, idx)
    if realized_vol is None or realized_vol > MAX_REALIZED_VOL_20D:
        return None

    pause_tightness = abs(pause_drawdown)
    reclaim_quality = max(0.0, signal_reclaim_vs_pause_high + 0.015)
    signal_extension_from_thrust_close = (close / thrust_close) - 1.0
    score = (
        1.80 * thrust_relative_spy
        + 1.10 * ret20_excess_spy
        + 0.70 * reclaim_quality
        + 0.22 * close_location
        + 0.06 * math.log10(max(adv20, 1.0) / 1_000_000.0)
        - 0.70 * pause_tightness
        - 0.45 * max(0.0, signal_extension_from_thrust_close - 0.04)
        - 0.35 * realized_vol
    )
    sector_meta = sector_entries[ticker]
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": "POST_THRUST_PAUSE_QUALITY_PAPER",
        "candidate_score": round(score, 6),
        "pause_quality_bucket": "post_thrust_orderly_pause_reclaim",
        "pause_len": pause_len,
        "thrust_date": shadow._date(thrust_row),
        "thrust_return": round(thrust_return, 6),
        "thrust_relative_spy": round(thrust_relative_spy, 6),
        "thrust_close_location": round(thrust_close_location, 6),
        "thrust_volume_ratio_20d": round(thrust_volume_ratio, 6),
        "pause_drawdown_from_thrust_close": round(pause_drawdown, 6),
        "pause_high_extension_from_thrust_high": round(pause_high_extension, 6),
        "pause_last_close_vs_thrust_close": round((pause_last_close / thrust_close) - 1.0, 6),
        "pause_volume_ratio_max_20d": round(pause_volume_ratio_max, 6),
        "signal_return": round(signal_return, 6),
        "signal_reclaim_vs_pause_high": round(signal_reclaim_vs_pause_high, 6),
        "signal_extension_from_thrust_close": round(signal_extension_from_thrust_close, 6),
        "signal_close_location": round(close_location, 6),
        "signal_volume_ratio_20d": round(signal_volume_ratio, 6),
        "ret5": round(ret5, 6),
        "ret20": round(ret20, 6),
        "spy_ret20": round(spy_ret20, 6),
        "ret20_excess_spy": round(ret20_excess_spy, 6),
        "avg_dollar_volume_20d": round(adv20, 2),
        "realized_vol_20d": round(realized_vol, 6),
        "sector": sector_meta.get("sector"),
        "industry": sector_meta.get("industry"),
        "sector_coverage_status": sector_meta.get("sector_coverage_status"),
        "rule_version": RULE_VERSION,
        "uses_free_ohlcv_only": True,
        "uses_llm": False,
        "trade_enabled": False,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = shadow._baseline_entries(before_result)
    indices = {ticker: shadow._row_index(shadow._series(snapshot, ticker)) for ticker in snapshot}
    dates = [
        date_value
        for date_value in shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    candidates: list[dict[str, Any]] = []
    audit: dict[str, Any] = {
        "scanned_trading_days": len(dates),
        "eligible_sector_known_tickers": len(sector_entries),
        "candidate_counts_by_pause_len": Counter(),
        "candidate_day_count": 0,
    }
    for signal_date in dates:
        for ticker in sector_entries:
            best: dict[str, Any] | None = None
            for pause_len in PAUSE_LENGTHS:
                row = _candidate_for_pause_length(
                    snapshot=snapshot,
                    indices=indices,
                    sector_entries=sector_entries,
                    ticker=ticker,
                    signal_date=signal_date,
                    pause_len=pause_len,
                )
                if row is None:
                    continue
                if best is None or float(row["candidate_score"]) > float(best["candidate_score"]):
                    best = row
            if best is None:
                continue
            ab_entries = entries_by_date.get(signal_date, [])
            best["same_day_ab_entry_count"] = len(ab_entries)
            best["same_day_ab_overlap"] = bool(ab_entries)
            best["same_ticker_ab_overlap"] = any(
                trade.get("ticker") == ticker for trade in ab_entries
            )
            audit["candidate_counts_by_pause_len"][str(best["pause_len"])] += 1
            candidates.append(best)
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["signal_reclaim_vs_pause_high"]),
            -float(row["ret20_excess_spy"]),
            -float(row["avg_dollar_volume_20d"]),
            row["ticker"],
        )
    )
    audit["candidate_counts_by_pause_len"] = dict(audit["candidate_counts_by_pause_len"])
    audit["candidate_day_count"] = len({row["date"] for row in candidates})
    return candidates, audit


def _select_paper_trades(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    used_date_counts: Counter[str] = Counter()
    dates = shadow._trading_dates(snapshot)
    date_pos = {date_value: idx for idx, date_value in enumerate(dates)}
    next_allowed_pos_by_ticker: dict[str, int] = {}
    for row in candidates:
        signal_date = str(row.get("date") or "")
        ticker = str(row.get("ticker") or "").upper()
        pos = date_pos.get(signal_date)
        if pos is None:
            filtered.append({**row, "filter_reason": "missing_signal_date_position"})
            continue
        if row.get("same_ticker_ab_overlap"):
            filtered.append({**row, "filter_reason": "same_ticker_core_overlap"})
            continue
        if used_date_counts[signal_date] >= MAX_PAPER_TRADES_PER_DAY:
            filtered.append({**row, "filter_reason": "daily_top1_limit"})
            continue
        next_allowed = next_allowed_pos_by_ticker.get(ticker, -1)
        if pos < next_allowed:
            filtered.append({**row, "filter_reason": "same_ticker_cooldown"})
            continue
        trade = sleeve._paper_trade_from_candidate(snapshot, row)
        if trade is None:
            filtered.append({**row, "filter_reason": "missing_next_open_or_exit"})
            continue
        selected.append(trade)
        used_date_counts[signal_date] += 1
        next_allowed_pos_by_ticker[ticker] = pos + SAME_TICKER_COOLDOWN_DAYS
    return selected, filtered


def _build_payload() -> dict[str, Any]:
    _patch_framework_globals()
    timestamp = _utc_now()
    gate2_open_positions = sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(get_universe())
    sector_entries_all = framework._load_sector_entries()
    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    filtered_candidates_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    raw_candidate_counts: "OrderedDict[str, int]" = OrderedDict()
    scan_audit_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    warehouse_coverage_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in WINDOWS.items():
        print(f"[{label}] core baseline and post-thrust pause replay")
        before_result = shadow._run_baseline(universe, cfg)
        before = overlay_helper._metrics(before_result)
        snapshot = framework._load_window_snapshot(
            cfg=cfg,
            eligible_tickers=set(sector_entries_all),
        )
        sector_entries = {
            ticker: meta for ticker, meta in sector_entries_all.items() if ticker in snapshot
        }
        warehouse_coverage_by_window[label] = {
            "loaded_ticker_count": len(snapshot),
            "sector_known_candidate_ticker_count": len(sector_entries),
            "source": _repo_rel(framework.WAREHOUSE),
        }
        candidates, scan_audit = _candidate_rows_for_window(
            snapshot=snapshot,
            cfg=cfg,
            before_result=before_result,
            sector_entries=sector_entries,
        )
        selected_trades, filtered_candidates = _select_paper_trades(
            snapshot=snapshot,
            candidates=candidates,
        )
        overlay = sleeve._overlay_from_paper_trades(before_result, selected_trades)
        after = overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = overlay_helper._delta(after, before)

        before_metrics[label] = before
        after_metrics[label] = after
        target_trades_by_window[label] = selected_trades
        filtered_candidates_by_window[label] = filtered_candidates[:200]
        raw_candidate_counts[label] = len(candidates)
        scan_audit_by_window[label] = scan_audit
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected_trades),
            "raw_candidate_count": len(candidates),
            "candidate_day_count": scan_audit["candidate_day_count"],
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = sleeve._aggregate(window_rows)
    target_summary = sleeve._target_trade_summary(target_trades_by_window)
    gate4 = framework._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    gate4["decision"] = (
        "positive_replay_lead_not_promoted_post_thrust_pause_quality"
        if gate4["passed"]
        else "rejected_post_thrust_pause_quality_candidate_pool"
    )
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    status = "accepted" if gate4["passed"] else "rejected"
    decision = gate4["decision"]
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2,
            6,
        ),
    }
    if gate4["passed"]:
        reflection = {
            "why_result_happened": (
                "The orderly pause and reclaim structure separated demand absorption "
                "from raw thrust noise across the three canonical windows without "
                "material drawdown or concentration drift."
            ),
            "realized_failure_mode": "none_gate4_passed",
            "forbidden_near_neighbor_retry": (
                "Do not retune thrust, pause length, reclaim, notional, hold, or "
                "cooldown on the same frozen windows; promote only through a shared "
                "default-off helper and daily parity snapshot."
            ),
            "new_evidence_required": (
                "Promotion requires shared historical and daily helper parity plus "
                "forward paper rows that show the same pause/reclaim edge."
            ),
        }
    else:
        reflection = {
            "why_result_happened": (
                "The pause/reclaim structure still mostly relabeled crowded short "
                "horizon momentum. Mid-window rebounds helped, but late_strong and "
                "old_thin reversed enough that aggregate EV and PnL fell and old_thin "
                "drawdown worsened beyond the Gate 4 limit."
            ),
            "realized_failure_mode": (
                "window_regression_and_drawdown_drift_from_generic_post_thrust_momentum"
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry nearby post-thrust pause, gap-hold, inside-day, hold-day, "
                "notional, cooldown, or reclaim-threshold variants on these frozen "
                "windows without a materially new PIT information field."
            ),
            "new_evidence_required": (
                "A retry needs external PIT confirmation such as event quality, "
                "revision trajectory, ownership sponsorship, or forward replacement "
                "rows; free-OHLCV threshold nudges are insufficient evidence."
            ),
        }
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": (
            "Post-thrust stocks that pause orderly for 1-3 trading days and "
            "then reclaim near the pause high may represent absorbed demand "
            "rather than gap-chase noise, creating a production-visible "
            "default-off candidate pool with better 10d replacement value than "
            "generic post-thrust inside-day or gap-hold candidates."
        ),
        "change_type": "default_off_paper_candidate_pool_scout",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "production_visible_free_ohlcv_tail_state_candidate_pool",
        "nearby_prior_experiments": [
            "exp-20260609-004",
            "exp-20260609-002",
            "exp-20260609-003",
            "exp-20260611-023",
            "exp-20260613-011",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "production_visible_free_ohlcv_post_thrust_pause_quality_field",
        "prediction": PREDICTION,
        "calibration": calibration,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "replay-only broad warehouse default-off paper overlay"
            ),
            "windows": WINDOWS,
            "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "Signal uses only close-of-day OHLCV available on signal date. "
                "Paper entry is next available open with existing entry slippage; "
                "exit is the close 10 trading days after the signal with "
                "target-side sell slippage and ROUND_TRIP_COST_PCT."
            ),
        },
        "parameters": {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "pause_lengths": PAUSE_LENGTHS,
            "min_price": MIN_PRICE,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
            "min_thrust_return": MIN_THRUST_RETURN,
            "min_thrust_relative_spy": MIN_THRUST_RELATIVE_SPY,
            "min_thrust_close_location": MIN_THRUST_CLOSE_LOCATION,
            "min_thrust_volume_ratio_20d": MIN_THRUST_VOLUME_RATIO_20D,
            "max_pause_drawdown_from_thrust_close": MAX_PAUSE_DRAWDOWN_FROM_THRUST_CLOSE,
            "max_pause_high_extension_from_thrust_high": MAX_PAUSE_HIGH_EXTENSION_FROM_THRUST_HIGH,
            "max_pause_volume_ratio_20d": MAX_PAUSE_VOLUME_RATIO_20D,
            "min_signal_close_location": MIN_SIGNAL_CLOSE_LOCATION,
            "min_signal_return": MIN_SIGNAL_RETURN,
            "max_signal_return": MAX_SIGNAL_RETURN,
            "min_signal_reclaim_of_pause_high": MIN_SIGNAL_RECLAIM_OF_PAUSE_HIGH,
            "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
            "max_ret5": MAX_RET5,
            "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "candidate_pool alpha: a thrust followed by orderly pause and "
                "controlled reclaim may separate absorbed demand from failed "
                "gap-hold/post-thrust noise."
            ),
            "2_history_check": {
                "exp-20260609-004": (
                    "Rejected post-thrust inside-day absorption. This run "
                    "requires a 1-3 day pause plus reclaim and is not an "
                    "inside-day-only retry."
                ),
                "exp-20260609-002/003": (
                    "Rejected gap-and-hold variants. This run rejects raw gap "
                    "chase and waits for an orderly pause/reclaim structure."
                ),
                "exp-20260611-023": (
                    "Rejected broad tail-state attribution. This tests a fixed "
                    "candidate source, not a broad ex-post tail attribution."
                ),
                "exp-20260613-011": (
                    "Rejected allocator front-loaded extension exclusion. This "
                    "does not alter accepted allocator rows or source priority."
                ),
            },
            "3_single_decision_hypothesis": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Use docs/backtesting.md three canonical windows. Aggregate "
                "EV/PnL must be positive, no window EV/PnL regression, at "
                "least 20 paper trades across all 3 windows, survival >=5%, "
                "drawdown drift <=0.5pp, and concentration pass. Positive "
                "replay-only output is a lead until shared parity exists."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260613_019_post_thrust_pause_quality.py"
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
                "warehouse ohlcv Date/Open/High/Low/Close/Volume",
                "SPY daily OHLCV",
                "data/reference/broad_market_sector_map.json sector/status",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": round(min_survival, 6),
            "passed": min_survival >= 0.05,
            "note": (
                "No new core filter or entry rule was added. The candidate "
                "source is additive replay-only paper, so core signals and "
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
        "warehouse_coverage_by_window": warehouse_coverage_by_window,
        "raw_candidate_counts": raw_candidate_counts,
        "scan_audit_by_window": scan_audit_by_window,
        "target_trades_by_window": target_trades_by_window,
        "filtered_candidates_sample_by_window": filtered_candidates_by_window,
        "target_trade_summary": target_summary,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "interpretation": (
            "The post-thrust pause quality candidate source cleared Gate 4 as "
            "a replay-only/default-off lead, but no production surface was promoted."
            if gate4["passed"]
            else (
                "The post-thrust pause quality candidate source did not clear "
                "Gate 4. Do not promote or retry nearby post-thrust pause/gap "
                "chase filters on the same frozen windows without materially "
                "new PIT evidence."
            )
        ),
        "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
        "post_run_reflection": reflection,
        "negative_reflection": (
            reflection["why_result_happened"] if not gate4["passed"] else None
        ),
        "next_evidence_needed": reflection["new_evidence_required"],
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Candidate days | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {days} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                days=payload["scan_audit_by_window"][label]["candidate_day_count"],
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Post-Thrust Pause Quality Candidate Pool",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4",
            "",
            *rows,
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate PnL delta: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "",
            "## Production Impact",
            "",
            "Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.",
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
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
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["gate4"]["passed"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": (
            "data/experiments/exp-20260602-003/"
            "exp_20260602_003_post_earnings_explicit_continuation.json"
        ),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate4": payload["gate4"],
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
                "candidate_day_count": payload["scan_audit_by_window"][label][
                    "candidate_day_count"
                ],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
        "negative_reflection": payload["negative_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _update_ticket_and_registry(payload: dict[str, Any], log_record: dict[str, Any]) -> None:
    result = {
        "decision": payload["decision"],
        "accepted": payload["gate4"]["passed"],
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "decision": payload["decision"],
        "summary": payload["interpretation"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": log_record["aggregate_expected_value_delta"],
        "aggregate_strategy_total_pnl_delta": log_record[
            "aggregate_strategy_total_pnl_delta"
        ],
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


def _write_manifest(payload: dict[str, Any]) -> None:
    files = [
        Path(__file__),
        OUT_JSON,
        LOG_JSON,
        TICKET_JSON,
        CARD_MD,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
    ]
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": payload["timestamp"],
        "owner": OWNER,
        "files": [
            {
                "path": _repo_rel(path),
                "sha256": framework._sha256(path),
            }
            for path in files
        ],
        "anti_js": "No JavaScript was used.",
    }
    _write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, log_record)
    _write_text(CARD_MD, _build_card(payload))
    _upsert_jsonl(EXPERIMENT_LOG, log_record)
    _update_ticket_and_registry(payload, log_record)
    _write_manifest(payload)


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
                    "artifact": _repo_rel(OUT_JSON),
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
