"""Default-off supplier-financing/debt-relief paper sleeve.

Shared helper for the positive exp-20260620-007 replay lead. The fixed bundle
uses the exp-20260620-005 raw SEC Companyfacts cross-statement candidate source
and applies the exp-20260620-007 one-way PIT volatility/liquidity paper-notional
envelope. Historical replay and daily observation call this module so the
accepted paper surface cannot drift into a backtester-only rule.

The sleeve is observe-only: ``trade_enabled`` is always false and no live or
default order path is touched.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_QUANT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _QUANT_DIR.parent
_EXPERIMENT_DIR = _QUANT_DIR / "experiments"
for _path in (_QUANT_DIR, _EXPERIMENT_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

try:
    import broad_market_sector_map
    from constants import ROUND_TRIP_COST_PCT
    from data_paths import DATA_ROOT
    from fill_model import (
        SLIPPAGE_BPS_TARGET,
        apply_entry_fill,
        apply_slippage,
    )
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant import broad_market_sector_map
    from quant.constants import ROUND_TRIP_COST_PCT
    from quant.data_paths import DATA_ROOT
    from quant.fill_model import (
        SLIPPAGE_BPS_TARGET,
        apply_entry_fill,
        apply_slippage,
    )

import exp_20260620_005_supplier_financing_debt_relief_intersection as source
import exp_20260620_007_supplier_financing_debt_relief_risk_scaled_notional as risk_lead


SLEEVE_NAME = "SUPPLIER_FINANCING_DEBT_RELIEF_RISK_SCALED_PAPER"
RULE_VERSION = "supplier_financing_debt_relief_shared_risk_scaled_default_off_adapter_v1"
SOURCE_RULE_VERSION = source.CHANGED_VARIABLE
RISK_RULE_VERSION = risk_lead.RULE_VERSION
STATE_SCHEMA_VERSION = 1

DEFAULT_STATE_PATH = (
    DATA_ROOT / "paper_sleeves" / "supplier_financing_debt_relief" / "state.json"
)
DEFAULT_SNAPSHOT_LOG_PATH = (
    DATA_ROOT
    / "paper_sleeves"
    / "supplier_financing_debt_relief"
    / "snapshots.jsonl"
)

BASE_NOTIONAL_USD = source.BASE_NOTIONAL_USD
HOLD_DAYS = source.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = source.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = source.SAME_TICKER_COOLDOWN_DAYS

DEFAULT_CONFIG = {
    "enabled": False,
    "paper_enabled": True,
    "trade_enabled": False,
    "paper_notional_usd": BASE_NOTIONAL_USD,
    "daily_entry_slots": MAX_PAPER_TRADES_PER_DAY,
    "max_active_positions": 10,
    "hold_days": HOLD_DAYS,
    "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
    "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
    "forward_gate_min_closed_trades": 30,
    "forward_gate_positive_net_pnl": True,
    "forward_gate_min_win_rate": 0.50,
    "forward_gate_max_single_ticker_positive_share": 0.50,
    "forward_gate_max_positive_hhi": 0.35,
}

_QUALITY_INDEX_CACHE: tuple[dict[str, dict[str, Any]], dict[str, Any]] | None = None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def empty_supplier_financing_debt_relief_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "updated_at": None,
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "skipped_days": [],
    }


def empty_supplier_financing_debt_relief_paper_sleeve_snapshot(
    as_of: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "risk_rule_version": RISK_RULE_VERSION,
        "asof_date": _date10(as_of),
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": False,
        "trade_enabled": False,
        "candidate_count": 0,
        "raw_candidate_count": 0,
        "rejected_candidate_count": 0,
        "new_pending_count": 0,
        "filled_count": 0,
        "closed_count_today": 0,
        "pending_count": 0,
        "open_position_count": 0,
        "closed_position_count": 0,
        "realized_pnl_to_date": 0.0,
        "unrealized_pnl": 0.0,
        "candidate_universe": {"status": reason, "ticker_count": 0},
        "supplier_financing_debt_relief_context": {"status": reason},
        "forward_paper_gate": {"passed": False, "status": "blocked", "reasons": [reason]},
        "production_impact": _production_impact(),
        "error": reason,
    }


def load_supplier_financing_debt_relief_state(
    path: Path | str = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_supplier_financing_debt_relief_state()
    with state_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    state = empty_supplier_financing_debt_relief_state()
    if isinstance(payload, dict):
        state.update(payload)
    _normalise_state(state)
    return state


def save_supplier_financing_debt_relief_state(
    state: dict[str, Any],
    path: Path | str = DEFAULT_STATE_PATH,
) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now_iso()
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(_safe(state), handle, indent=2, sort_keys=True)
        handle.write("\n")


def append_supplier_financing_debt_relief_snapshot(
    snapshot: dict[str, Any],
    path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_safe(snapshot), sort_keys=True) + "\n")


def load_supplier_financing_debt_relief_quality_index() -> tuple[
    dict[str, dict[str, Any]], dict[str, Any]
]:
    global _QUALITY_INDEX_CACHE
    if _QUALITY_INDEX_CACHE is None:
        _QUALITY_INDEX_CACHE = source._build_quality_index([])
    return _QUALITY_INDEX_CACHE


def build_supplier_financing_debt_relief_historical_trades(
    *,
    ohlcv_by_ticker: dict[str, Any],
    windows: dict[str, dict[str, str]],
    quality_index: dict[str, dict[str, Any]] | None = None,
    candidate_universe: dict[str, Any] | list[str] | None = None,
    sector_entries: dict[str, dict[str, Any]] | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build closed paper trades using the exact exp007 fixed replay bundle."""

    _configure_replay_framework()
    cfg = _config(config)
    snapshot = _framework_snapshot(ohlcv_by_ticker)
    sector_map = _resolve_sector_entries(
        sector_entries=sector_entries,
        candidate_universe=candidate_universe,
        snapshot=snapshot,
    )
    quality = quality_index
    quality_summary: dict[str, Any] = {
        "source": "provided_quality_index",
        "ticker_count": len(quality or {}),
    }
    if quality is None:
        quality, quality_summary = load_supplier_financing_debt_relief_quality_index()

    all_trades: list[dict[str, Any]] = []
    audit: dict[str, Any] = {
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "risk_rule_version": RISK_RULE_VERSION,
        "quality_index_summary": quality_summary,
        "selected_by_window": {},
        "raw_candidate_count_by_window": {},
        "rejected_count_by_window": {},
        "scan_by_window": {},
        "risk_scan_by_window": {},
    }

    for label, window in windows.items():
        candidates, scan = source._candidate_rows_for_window(
            snapshot=snapshot,
            cfg=window,
            sector_entries=sector_map,
            quality_index=quality,
        )
        selected, rejected = source.base.framework._select_paper_trades(
            snapshot=snapshot,
            candidates=candidates,
        )
        adjusted, risk_scan = risk_lead._apply_risk_scaled_notional(selected)
        for trade in adjusted:
            trade["window"] = label
            _stamp_shared_trade(trade)
        all_trades.extend(adjusted)
        audit["selected_by_window"][label] = len(adjusted)
        audit["raw_candidate_count_by_window"][label] = len(candidates)
        audit["rejected_count_by_window"][label] = len(rejected)
        audit["scan_by_window"][label] = scan
        audit["risk_scan_by_window"][label] = risk_scan

    audit["total_selected"] = len(all_trades)
    audit["total_raw_candidates"] = sum(audit["raw_candidate_count_by_window"].values())
    audit["parameters"] = _parameter_summary(cfg)
    return all_trades, audit


def build_supplier_financing_debt_relief_candidate_rows(
    *,
    ohlcv_by_ticker: dict[str, Any],
    dates: list[str],
    quality_index: dict[str, dict[str, Any]],
    sector_entries: dict[str, dict[str, Any]] | None = None,
    candidate_universe: dict[str, Any] | list[str] | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Daily-capable candidate builder.

    This mirrors exp-20260620-005, except callers can set
    ``require_future_exit=False`` for same-day daily observation.
    """

    cfg = _config(config)
    snapshot = _framework_snapshot(ohlcv_by_ticker)
    sector_map = _resolve_sector_entries(
        sector_entries=sector_entries,
        candidate_universe=candidate_universe,
        snapshot=snapshot,
    )
    indices = {
        ticker: source.base.framework.shadow._row_index(
            source.base.framework.shadow._series(snapshot, ticker)
        )
        for ticker in snapshot
    }
    allowed = _candidate_universe_tickers(candidate_universe, snapshot)
    eligible = sorted((set(quality_index) & set(snapshot) & allowed) - _excluded_tickers())
    scan: Counter[str] = Counter()
    scan["scanned_trading_days"] = len(dates)
    scan["eligible_quality_tickers"] = len(eligible)
    candidates: list[dict[str, Any]] = []
    require_future_exit = bool(cfg.get("require_future_exit", True))

    for raw_date in dates:
        signal_date = _date10(raw_date)
        if not signal_date:
            continue
        for ticker in eligible:
            scan["ticker_day_evaluations"] += 1
            payables_observation = source.dpo._payables_observation(
                ticker,
                signal_date,
                quality_index[ticker]["payables"],
            )
            if payables_observation is None:
                scan["failed_dpo_extension_gate"] += 1
                continue
            debt_observation = source.debt._debt_observation(
                ticker,
                signal_date,
                quality_index[ticker]["debt"],
            )
            if debt_observation is None:
                scan["failed_debt_relief_gate"] += 1
                continue
            confirm = _price_confirmation(
                snapshot=snapshot,
                indices=indices,
                ticker=ticker,
                signal_date=signal_date,
                require_future_exit=require_future_exit,
                hold_days=int(cfg["hold_days"]),
            )
            if confirm is None:
                scan["failed_price_confirmation"] += 1
                continue
            scan["qualified_candidate_rows"] += 1
            meta = sector_map.get(ticker, {})
            dpo_extension = float(payables_observation["dpo_extension_days"] or 0.0)
            cogs_growth = float(payables_observation["cogs_growth"] or 0.0)
            gross_profit_growth = payables_observation.get("gross_profit_growth")
            gross_profit_component = 0.0
            if gross_profit_growth is not None:
                gross_profit_component = max(min(float(gross_profit_growth), 0.60), -0.05)
            debt_ratio_improvement = float(
                debt_observation["debt_ratio_improvement"] or 0.0
            )
            revenue_growth = float(debt_observation["revenue_growth"] or 0.0)
            debt_growth_spread = float(
                debt_observation["debt_growth_minus_revenue_growth"] or 0.0
            )
            current_debt_ratio = float(debt_observation["current_debt_to_revenue"] or 0.0)
            current_dpo = float(payables_observation["current_dpo_days"] or 0.0)
            score = (
                0.018 * min(dpo_extension, 50.0)
                + 1.20 * min(debt_ratio_improvement, 0.45)
                + 0.16 * max(min(cogs_growth, 0.60), -0.05)
                + 0.16 * gross_profit_component
                + 0.18 * max(min(revenue_growth, 0.60), 0.0)
                + 0.10 * max(min(-debt_growth_spread, 0.50), -0.25)
                + 0.45 * float(confirm["candidate_ret20_excess_spy"])
                + 0.12 * float(confirm["candidate_ret60_excess_spy"])
                + 0.08 * float(confirm["candidate_close_location"])
                + 0.030
                * math.log10(
                    max(float(confirm["candidate_avg_dollar_volume_20d"]), 1.0)
                    / 1_000_000.0
                )
                - 0.002 * max(current_dpo - 120.0, 0.0)
                - 0.025 * max(current_debt_ratio - 0.75, 0.0)
            )
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": SLEEVE_NAME,
                    "candidate_score": _round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": SOURCE_RULE_VERSION,
                    "risk_rule_version": RISK_RULE_VERSION,
                    "known_at": (
                        "raw_companyfacts_filed_and_signal_close_before_next_open_paper_entry"
                    ),
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "sector_coverage_status": meta.get("sector_coverage_status")
                    or meta.get("status"),
                    "uses_free_sec_companyfacts": True,
                    "uses_raw_sec_companyfacts_cache": True,
                    "uses_free_ohlcv": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    "alters_orders": False,
                    **{f"payables_{key}": value for key, value in payables_observation.items()},
                    **{f"debt_{key}": value for key, value in debt_observation.items()},
                    **confirm,
                }
            )

    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in candidates:
        key = (row["date"], row["ticker"])
        existing = deduped.get(key)
        if existing is None or float(row["candidate_score"]) > float(
            existing["candidate_score"]
        ):
            deduped[key] = row
    rows = list(deduped.values())
    rows.sort(key=_candidate_sort_tuple)
    scan["deduped_candidate_rows"] = len(rows)
    scan["candidate_signal_days"] = len({row["date"] for row in rows})
    scan["candidate_tickers"] = len({row["ticker"] for row in rows})
    return rows, {
        **dict(scan),
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "risk_rule_version": RISK_RULE_VERSION,
        "require_future_exit": require_future_exit,
        "intersection_gate": (
            "DPO extension observation and principal debt burden relief "
            "observation must both exist for the same ticker/signal date."
        ),
    }


def build_supplier_financing_debt_relief_paper_sleeve_snapshot(
    *,
    as_of: str,
    ohlcv_by_ticker: dict[str, Any],
    candidate_universe: dict[str, Any] | list[str] | None = None,
    sector_entries: dict[str, dict[str, Any]] | None = None,
    quality_index: dict[str, dict[str, Any]] | None = None,
    open_prices: dict[str, Any] | None = None,
    current_prices: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    persist: bool = True,
    state_path: Path | str = DEFAULT_STATE_PATH,
    snapshot_log_path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> dict[str, Any]:
    del open_prices, current_prices
    cfg = _config(config)
    as_of_date = _date10(as_of)
    snapshot = _framework_snapshot(ohlcv_by_ticker)
    if not snapshot:
        return empty_supplier_financing_debt_relief_paper_sleeve_snapshot(
            as_of_date, "missing_ohlcv"
        )
    if "SPY" not in snapshot:
        return empty_supplier_financing_debt_relief_paper_sleeve_snapshot(
            as_of_date, "missing_spy_ohlcv"
        )

    quality = quality_index
    quality_summary: dict[str, Any] = {
        "source": "provided_quality_index",
        "ticker_count": len(quality or {}),
    }
    if quality is None:
        quality, quality_summary = load_supplier_financing_debt_relief_quality_index()

    working_state = deepcopy(
        state
        if state is not None
        else load_supplier_financing_debt_relief_state(state_path)
    )
    _normalise_state(working_state)

    filled_today = _fill_pending_entries(working_state, snapshot, as_of_date, cfg)
    closed_today = _advance_open_positions(working_state, snapshot, as_of_date, cfg)
    candidates, scan = build_supplier_financing_debt_relief_candidate_rows(
        ohlcv_by_ticker=snapshot,
        dates=[as_of_date],
        quality_index=quality,
        sector_entries=sector_entries,
        candidate_universe=candidate_universe,
        config={**cfg, "require_future_exit": False},
    )
    selected_rows, rejected = select_supplier_financing_debt_relief_signal_rows(
        ohlcv_by_ticker=snapshot,
        candidates=candidates,
        existing_state=working_state,
        config=cfg,
    )

    active_count = len(working_state.get("pending_entries") or []) + len(
        working_state.get("open_positions") or []
    )
    if active_count >= int(cfg["max_active_positions"]):
        rejected.extend({**row, "filter_reason": "max_active_positions"} for row in selected_rows)
        selected_rows = []

    new_pending_entries: list[dict[str, Any]] = []
    if cfg.get("paper_enabled", True):
        for row in selected_rows:
            pending = _pending_entry_from_candidate(row, cfg)
            if not _has_pending_open_or_closed_decision(working_state, pending["decision_id"]):
                working_state["pending_entries"].append(pending)
                new_pending_entries.append(pending)

    if not selected_rows:
        reason = "no_supplier_financing_debt_relief_candidate" if candidates else "no_raw_candidate"
        _append_skip_once(working_state, _skip_payload(as_of_date, reason))

    snapshot_payload = _snapshot_payload(
        working_state,
        as_of=as_of_date,
        candidates=candidates,
        selected_rows=selected_rows,
        rejected=rejected,
        scan=scan,
        quality_summary=quality_summary,
        new_pending_entries=new_pending_entries,
        filled_today=filled_today,
        closed_today=closed_today,
        candidate_universe=candidate_universe,
        rows_by_ticker=snapshot,
        config=cfg,
    )
    if persist:
        save_supplier_financing_debt_relief_state(working_state, state_path)
        append_supplier_financing_debt_relief_snapshot(snapshot_payload, snapshot_log_path)
    return snapshot_payload


def select_supplier_financing_debt_relief_signal_rows(
    *,
    ohlcv_by_ticker: dict[str, Any],
    candidates: list[dict[str, Any]],
    existing_state: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cfg = _config(config)
    snapshot = _framework_snapshot(ohlcv_by_ticker)
    dates = source.base.framework.shadow._trading_dates(snapshot)
    date_pos = {day: idx for idx, day in enumerate(dates)}
    next_allowed = _state_cooldown_map(
        existing_state=existing_state,
        date_pos=date_pos,
        config=cfg,
    )
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    used_date_counts: Counter[str] = Counter()
    for row in candidates:
        signal_date = str(row.get("date") or "")[:10]
        ticker = str(row.get("ticker") or "").upper()
        pos = date_pos.get(signal_date)
        if pos is None:
            rejected.append({**row, "filter_reason": "missing_signal_date_position"})
            continue
        if used_date_counts[signal_date] >= int(cfg["daily_entry_slots"]):
            rejected.append({**row, "filter_reason": "daily_top1_limit"})
            continue
        if pos < next_allowed.get(ticker, -1):
            rejected.append({**row, "filter_reason": "same_ticker_cooldown"})
            continue
        selected_row = _candidate_with_risk_payload(row, cfg)
        selected.append(selected_row)
        used_date_counts[signal_date] += 1
        next_allowed[ticker] = pos + int(cfg["same_ticker_cooldown_days"])
    return selected, rejected


def prep_and_build_supplier_financing_debt_relief_paper_sleeve_snapshot(
    *,
    as_of: str,
    broad_market_ohlcv: dict[str, Any],
    broad_market_candidate_universe: dict[str, Any],
    spy_ohlcv: Any = None,
    open_prices: dict[str, Any] | None = None,
    current_prices: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not broad_market_candidate_universe.get("tickers"):
        return empty_supplier_financing_debt_relief_paper_sleeve_snapshot(
            as_of,
            "broad_market_candidate_universe_unavailable",
        )
    ohlcv = dict(broad_market_ohlcv)
    if "SPY" not in ohlcv and spy_ohlcv is not None:
        ohlcv["SPY"] = spy_ohlcv
    return build_supplier_financing_debt_relief_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=ohlcv,
        candidate_universe=broad_market_candidate_universe,
        open_prices=open_prices,
        current_prices=current_prices,
    )


def _price_confirmation(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    ticker: str,
    signal_date: str,
    require_future_exit: bool,
    hold_days: int,
) -> dict[str, Any] | None:
    rows = source.base.framework.shadow._series(snapshot, ticker)
    spy_rows = source.base.framework.shadow._series(snapshot, "SPY")
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None or idx < 60 or spy_idx < 60:
        return None
    if require_future_exit and idx + hold_days >= len(rows):
        return None
    close = source.base.framework._value(rows[idx], "Close")
    if close is None or close < source.base.MIN_PRICE:
        return None
    adv20 = source.base.framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < source.base.MIN_AVG_DOLLAR_VOLUME_20D:
        return None
    signal_return = source.base.framework._daily_return(rows, idx)
    close_location = source.base.framework._close_location(rows[idx])
    ret20 = source.base.framework._ret(rows, idx, 20)
    ret60 = source.base.framework._ret(rows, idx, 60)
    spy_ret20 = source.base.framework._ret(spy_rows, spy_idx, 20)
    spy_ret60 = source.base.framework._ret(spy_rows, spy_idx, 60)
    realized_vol = source.base.framework._realized_vol(rows, idx, 20)
    if any(
        value is None
        for value in (
            signal_return,
            close_location,
            ret20,
            ret60,
            spy_ret20,
            spy_ret60,
            realized_vol,
        )
    ):
        return None
    assert signal_return is not None and close_location is not None
    assert ret20 is not None and ret60 is not None
    assert spy_ret20 is not None and spy_ret60 is not None and realized_vol is not None
    if signal_return < source.base.MIN_SIGNAL_RETURN or signal_return > source.base.MAX_SIGNAL_RETURN:
        return None
    if close_location < source.base.MIN_CLOSE_LOCATION:
        return None
    if realized_vol > source.base.MAX_REALIZED_VOL_20D:
        return None
    ret20_excess_spy = ret20 - spy_ret20
    ret60_excess_spy = ret60 - spy_ret60
    if ret20_excess_spy < source.base.MIN_RET20_EXCESS_SPY:
        return None
    if ret60_excess_spy < source.base.MIN_RET60_EXCESS_SPY:
        return None
    volume_ratio = source.base.framework._volume_ratio(rows, idx) or 0.0
    return {
        "candidate_signal_return": _round(signal_return, 6),
        "candidate_close_location": _round(close_location, 6),
        "candidate_ret20": _round(ret20, 6),
        "candidate_ret20_excess_spy": _round(ret20_excess_spy, 6),
        "candidate_ret60_excess_spy": _round(ret60_excess_spy, 6),
        "candidate_avg_dollar_volume_20d": _round(adv20, 2),
        "candidate_volume_ratio_20d": _round(volume_ratio, 6),
        "candidate_realized_vol_20d": _round(realized_vol, 6),
    }


def _candidate_with_risk_payload(
    row: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    payload = risk_lead._notional_scalar_payload(row)
    scalar = float(payload["risk_notional_scalar"] or 1.0)
    notional = round(float(config["paper_notional_usd"]) * scalar, 2)
    out = {
        **row,
        **payload,
        "sleeve": SLEEVE_NAME,
        "source": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "risk_source_rule_version": RISK_RULE_VERSION,
        "risk_rule_version": RULE_VERSION,
        "decision_id": _decision_id(row),
        "paper_notional_usd": notional,
        "notional_usd": notional,
        "trade_enabled": False,
        "alters_orders": False,
    }
    return out


def _configure_replay_framework() -> None:
    source._configure_framework()
    for module in (source.base.framework, source.base.framework.sleeve):
        module.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
        module.HOLD_DAYS = HOLD_DAYS
        module.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
        if hasattr(module, "SAME_TICKER_COOLDOWN_DAYS"):
            module.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS


def _stamp_shared_trade(trade: dict[str, Any]) -> None:
    trade["sleeve"] = SLEEVE_NAME
    trade["source"] = SLEEVE_NAME
    trade["rule_version"] = RULE_VERSION
    trade["source_rule_version"] = SOURCE_RULE_VERSION
    trade["risk_source_rule_version"] = RISK_RULE_VERSION
    trade["risk_rule_version"] = RULE_VERSION
    trade["decision_id"] = _decision_id(trade)
    trade["trade_enabled"] = False
    trade["alters_orders"] = False
    trade["paper_status"] = trade.get("paper_status") or "closed"
    if "target_price" not in trade:
        trade["target_price"] = trade.get("exit_price")


def _pending_entry_from_candidate(
    row: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    return {
        **row,
        "status": "pending_entry",
        "signal_date": row.get("date"),
        "created_at": utc_now_iso(),
        "entry_semantics": "next_open_paper_only",
        "hold_days": int(config["hold_days"]),
    }


def _fill_pending_entries(
    state: dict[str, Any],
    snapshot: dict[str, list[dict[str, Any]]],
    as_of: str,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    filled: list[dict[str, Any]] = []
    remaining: list[dict[str, Any]] = []
    for pending in state.get("pending_entries") or []:
        if not isinstance(pending, dict):
            continue
        signal_date = str(pending.get("signal_date") or pending.get("date") or "")[:10]
        if as_of <= signal_date:
            remaining.append(pending)
            continue
        ticker = str(pending.get("ticker") or "").upper()
        row = _row_for_date(snapshot.get(ticker) or [], as_of)
        raw_open = _positive_float((row or {}).get("Open"))
        if raw_open is None:
            remaining.append(pending)
            continue
        notional = _positive_float(pending.get("paper_notional_usd")) or float(
            config["paper_notional_usd"]
        )
        adv = _positive_float(pending.get("candidate_avg_dollar_volume_20d"))
        entry_price = apply_entry_fill(raw_open, adv_dollar=adv, notional=notional)
        opened = {
            **pending,
            "status": "open",
            "entry_date": as_of,
            "entry_raw_open": _round(raw_open, 4),
            "entry_price": _round(entry_price, 4),
            "days_held": 0,
        }
        state["open_positions"].append(opened)
        filled.append(opened)
    state["pending_entries"] = remaining
    return filled


def _advance_open_positions(
    state: dict[str, Any],
    snapshot: dict[str, list[dict[str, Any]]],
    as_of: str,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    closed_today: list[dict[str, Any]] = []
    still_open: list[dict[str, Any]] = []
    for position in state.get("open_positions") or []:
        if not isinstance(position, dict):
            continue
        ticker = str(position.get("ticker") or "").upper()
        row = _row_for_date(snapshot.get(ticker) or [], as_of)
        if row is None:
            still_open.append(position)
            continue
        days_held = int(position.get("days_held") or 0) + 1
        if days_held < int(config["hold_days"]):
            position["days_held"] = days_held
            still_open.append(position)
            continue
        close_raw = _positive_float(row.get("Close"))
        entry_price = _positive_float(position.get("entry_price"))
        notional = _positive_float(position.get("paper_notional_usd")) or float(
            config["paper_notional_usd"]
        )
        adv = _positive_float(position.get("candidate_avg_dollar_volume_20d"))
        if close_raw is None or entry_price is None:
            position["days_held"] = days_held
            still_open.append(position)
            continue
        exit_price = apply_slippage(
            close_raw,
            SLIPPAGE_BPS_TARGET,
            "sell",
            adv_dollar=adv,
            notional=notional,
        )
        pnl_pct_net = exit_price / entry_price - 1.0 - ROUND_TRIP_COST_PCT
        closed = {
            **position,
            "status": "closed",
            "exit_date": as_of,
            "exit_raw_close": _round(close_raw, 4),
            "exit_price": _round(exit_price, 4),
            "days_held": days_held,
            "pnl_pct_net": _round(pnl_pct_net, 6),
            "pnl": _round(notional * pnl_pct_net, 2),
            "target_price": _round(exit_price, 4),
        }
        state["closed_positions"].append(closed)
        closed_today.append(closed)
    state["open_positions"] = still_open
    return closed_today


def _snapshot_payload(
    state: dict[str, Any],
    *,
    as_of: str,
    candidates: list[dict[str, Any]],
    selected_rows: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
    scan: dict[str, Any],
    quality_summary: dict[str, Any],
    new_pending_entries: list[dict[str, Any]],
    filled_today: list[dict[str, Any]],
    closed_today: list[dict[str, Any]],
    candidate_universe: dict[str, Any] | list[str] | None,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    config: dict[str, Any],
) -> dict[str, Any]:
    closed = [row for row in state.get("closed_positions") or [] if isinstance(row, dict)]
    pending = [row for row in state.get("pending_entries") or [] if isinstance(row, dict)]
    open_positions = [row for row in state.get("open_positions") or [] if isinstance(row, dict)]
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "risk_rule_version": RISK_RULE_VERSION,
        "asof_date": as_of,
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": bool(config.get("paper_enabled", True)),
        "trade_enabled": False,
        "trade_enabled_reason": "default_off_until_forward_gate_and_trade_adapter_pass",
        "candidate_count": len(selected_rows),
        "raw_candidate_count": len(candidates),
        "rejected_candidate_count": len(rejected),
        "candidate": selected_rows[0] if selected_rows else None,
        "candidates": selected_rows,
        "rejected_candidates": rejected[:50],
        "supplier_financing_debt_relief_context": {
            **scan,
            "read_only": True,
            "trade_enabled": False,
            "alters_orders": False,
        },
        "context_scan": scan,
        "quality_index_summary": quality_summary,
        "candidate_universe": _candidate_universe_summary(candidate_universe, rows_by_ticker),
        "new_pending_entries": new_pending_entries,
        "new_pending_count": len(new_pending_entries),
        "pending_entries": pending,
        "pending_count": len(pending),
        "filled_today": filled_today,
        "filled_count": len(filled_today),
        "opened_positions_this_run": filled_today,
        "open_positions": open_positions,
        "open_position_count": len(open_positions),
        "closed_today": closed_today,
        "closed_positions_today": closed_today,
        "closed_positions_this_run": closed_today,
        "closed_count_today": len(closed_today),
        "closed_positions": closed,
        "closed_position_count": len(closed),
        "realized_pnl_to_date": _round(sum(_float_or_none(row.get("pnl")) or 0.0 for row in closed), 2),
        "unrealized_pnl": _unrealized_pnl(open_positions, rows_by_ticker, as_of),
        "forward_paper_gate": _forward_paper_gate(closed, config),
        "parameters": _parameter_summary(config),
        "production_impact": _production_impact(),
        "next_action": "paper_observe_forward_outcomes_only_no_orders",
    }


def _framework_snapshot(ohlcv_by_ticker: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in (ohlcv_by_ticker or {}).items():
        normalised = _normalise_rows(rows)
        if normalised:
            out[str(ticker).upper()] = normalised
    return out


def _normalise_rows(rows: Any) -> list[dict[str, Any]]:
    if rows is None:
        return []
    out: list[dict[str, Any]] = []
    if hasattr(rows, "iterrows"):
        iterator = ((raw, idx) for idx, raw in rows.iterrows())
    elif isinstance(rows, list):
        iterator = ((raw, None) for raw in rows)
    else:
        iterator = ()
    for raw, idx in iterator:
        if not isinstance(raw, dict):
            try:
                raw = raw.to_dict()
            except AttributeError:
                continue
        date_value = raw.get("Date", raw.get("date", idx))
        date_text = _date10(date_value)
        open_ = _float_or_none(raw.get("Open", raw.get("open")))
        high = _float_or_none(raw.get("High", raw.get("high")))
        low = _float_or_none(raw.get("Low", raw.get("low")))
        close = _float_or_none(raw.get("Close", raw.get("close")))
        volume = _float_or_none(raw.get("Volume", raw.get("volume")))
        if not date_text or None in (open_, high, low, close, volume):
            continue
        out.append(
            {
                "Date": date_text,
                "Open": float(open_),
                "High": float(high),
                "Low": float(low),
                "Close": float(close),
                "Volume": float(volume),
            }
        )
    out.sort(key=lambda row: row["Date"])
    return out


def _resolve_sector_entries(
    *,
    sector_entries: dict[str, dict[str, Any]] | None,
    candidate_universe: dict[str, Any] | list[str] | None,
    snapshot: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    if sector_entries:
        raw_entries = sector_entries
    elif isinstance(candidate_universe, dict) and isinstance(candidate_universe.get("records"), dict):
        raw_entries = candidate_universe["records"]
    elif isinstance(candidate_universe, dict) and isinstance(candidate_universe.get("entries"), dict):
        raw_entries = candidate_universe["entries"]
    else:
        cache = broad_market_sector_map.load_cache()
        raw_entries = cache.get("entries", {}) if isinstance(cache, dict) else {}
        if not raw_entries:
            raw_entries = source.base.framework._load_sector_entries()

    allowed = _candidate_universe_tickers(candidate_universe, snapshot)
    out: dict[str, dict[str, Any]] = {}
    for ticker, meta in raw_entries.items():
        ticker_u = str(ticker).upper()
        if ticker_u in _excluded_tickers() or "." in ticker_u or "-" in ticker_u:
            continue
        if ticker_u not in snapshot or ticker_u not in allowed:
            continue
        if not isinstance(meta, dict):
            continue
        sector = meta.get("sector") or meta.get("gics_sector")
        status = meta.get("status") or meta.get("sector_coverage_status") or "ok"
        if not sector or status != "ok":
            continue
        out[ticker_u] = {
            "sector": sector,
            "industry": meta.get("industry"),
            "sector_coverage_status": status,
        }
    return out


def _candidate_universe_tickers(
    candidate_universe: dict[str, Any] | list[str] | None,
    snapshot: dict[str, list[dict[str, Any]]],
) -> set[str]:
    if isinstance(candidate_universe, list):
        return {str(ticker).upper() for ticker in candidate_universe}
    if isinstance(candidate_universe, dict) and candidate_universe.get("tickers"):
        return {str(ticker).upper() for ticker in candidate_universe.get("tickers") or []}
    return set(snapshot)


def _excluded_tickers() -> set[str]:
    return set(getattr(source.base.framework.shadow, "EXCLUDED_TICKERS", set()))


def _candidate_sort_tuple(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row["date"],
        -float(row.get("candidate_score") or 0.0),
        -float(row.get("debt_debt_ratio_improvement") or 0.0),
        -float(row.get("payables_dpo_extension_days") or 0.0),
        float(row.get("debt_debt_growth_minus_revenue_growth") or 0.0),
        -float(row.get("candidate_ret20_excess_spy") or 0.0),
        -float(row.get("candidate_avg_dollar_volume_20d") or 0.0),
        row["ticker"],
    )


def _normalise_state(state: dict[str, Any]) -> None:
    state.setdefault("schema_version", STATE_SCHEMA_VERSION)
    state.setdefault("sleeve", SLEEVE_NAME)
    for key in ("pending_entries", "open_positions", "closed_positions", "skipped_days"):
        if not isinstance(state.get(key), list):
            state[key] = []


def _state_cooldown_map(
    *,
    existing_state: dict[str, Any] | None,
    date_pos: dict[str, int],
    config: dict[str, Any],
) -> dict[str, int]:
    next_allowed_pos_by_ticker: dict[str, int] = {}
    if not existing_state:
        return next_allowed_pos_by_ticker
    for bucket in ("pending_entries", "open_positions", "closed_positions"):
        for row in existing_state.get(bucket) or []:
            if not isinstance(row, dict):
                continue
            ticker = str(row.get("ticker") or "").upper()
            date_value = str(row.get("signal_date") or row.get("date") or "")[:10]
            pos = date_pos.get(date_value)
            if ticker and pos is not None:
                next_allowed_pos_by_ticker[ticker] = max(
                    next_allowed_pos_by_ticker.get(ticker, -1),
                    pos + int(config["same_ticker_cooldown_days"]),
                )
    return next_allowed_pos_by_ticker


def _has_pending_open_or_closed_decision(state: dict[str, Any], decision_id: str) -> bool:
    for bucket in ("pending_entries", "open_positions", "closed_positions"):
        for row in state.get(bucket) or []:
            if isinstance(row, dict) and row.get("decision_id") == decision_id:
                return True
    return False


def _append_skip_once(state: dict[str, Any], row: dict[str, Any]) -> None:
    existing = {
        str(item.get("decision_id") or "")
        for item in state.get("skipped_days") or []
        if isinstance(item, dict)
    }
    if row["decision_id"] not in existing:
        state["skipped_days"].append(row)


def _skip_payload(as_of: str, reason: str) -> dict[str, Any]:
    return {
        "decision_id": f"{SLEEVE_NAME}:{RULE_VERSION}:{as_of}:SKIP:{reason}",
        "date": as_of,
        "reason": reason,
        "trade_enabled": False,
        "alters_orders": False,
    }


def _decision_id(row: dict[str, Any]) -> str:
    signal_date = str(row.get("date") or row.get("signal_date") or "")[:10]
    ticker = str(row.get("ticker") or "").upper()
    return f"{SLEEVE_NAME}:{SOURCE_RULE_VERSION}:{RISK_RULE_VERSION}:{signal_date}:{ticker}"


def _date10(value: Any) -> str:
    text = str(value or "")[:10]
    return text if len(text) == 10 and text[4] == "-" and text[7] == "-" else ""


def _row_for_date(rows: list[dict[str, Any]], as_of: str) -> dict[str, Any] | None:
    target = _date10(as_of)
    for row in rows:
        if _date10(row.get("Date", row.get("date"))) == target:
            return row
    return None


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def _positive_float(value: Any) -> float | None:
    out = _float_or_none(value)
    if out is None or out <= 0.0:
        return None
    return out


def _round(value: Any, digits: int = 6) -> float | None:
    number = _float_or_none(value)
    if number is None:
        return None
    return round(number, digits)


def _unrealized_pnl(
    open_positions: list[dict[str, Any]],
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    as_of: str,
) -> float:
    total = 0.0
    for position in open_positions:
        ticker = str(position.get("ticker") or "").upper()
        row = _row_for_date(rows_by_ticker.get(ticker) or [], as_of)
        entry = _positive_float(position.get("entry_price"))
        close = _positive_float((row or {}).get("Close"))
        notional = _float_or_none(position.get("paper_notional_usd")) or 0.0
        if entry is None or close is None:
            continue
        total += notional * (close / entry - 1.0)
    return round(total, 2)


def _forward_paper_gate(closed: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    closed_count = len(closed)
    min_closed = int(config["forward_gate_min_closed_trades"])
    if closed_count < min_closed:
        reasons.append(f"closed_trades_below_min:{closed_count}/{min_closed}")
    pnl = sum(_float_or_none(row.get("pnl")) or 0.0 for row in closed)
    if config.get("forward_gate_positive_net_pnl", True) and pnl <= 0.0:
        reasons.append("net_pnl_not_positive")
    wins = [row for row in closed if (_float_or_none(row.get("pnl")) or 0.0) > 0.0]
    win_rate = len(wins) / closed_count if closed_count else 0.0
    if closed_count and win_rate < float(config["forward_gate_min_win_rate"]):
        reasons.append("win_rate_below_min")
    positive_by_ticker: Counter[str] = Counter()
    for row in wins:
        positive_by_ticker[str(row.get("ticker") or "").upper()] += float(row.get("pnl") or 0.0)
    positive_total = sum(positive_by_ticker.values())
    max_share = (
        max(positive_by_ticker.values()) / positive_total
        if positive_total > 0.0 and positive_by_ticker
        else None
    )
    hhi = (
        sum((value / positive_total) ** 2 for value in positive_by_ticker.values())
        if positive_total > 0.0
        else None
    )
    if max_share is not None and max_share > float(config["forward_gate_max_single_ticker_positive_share"]):
        reasons.append("single_ticker_positive_share_too_high")
    if hhi is not None and hhi > float(config["forward_gate_max_positive_hhi"]):
        reasons.append("positive_pnl_hhi_too_high")
    return {
        "passed": not reasons,
        "status": "passed" if not reasons else "blocked",
        "reasons": reasons,
        "closed_trade_count": closed_count,
        "net_pnl": round(pnl, 2),
        "win_rate": round(win_rate, 4),
        "min_closed_trades": min_closed,
        "max_single_positive_pnl_share": _round(max_share, 6),
        "positive_pnl_hhi": _round(hhi, 6),
    }


def _candidate_universe_summary(
    candidate_universe: dict[str, Any] | list[str] | None,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    if isinstance(candidate_universe, dict):
        count = len(candidate_universe.get("tickers") or candidate_universe.get("records") or rows_by_ticker)
        status = candidate_universe.get("status") or "provided"
    elif isinstance(candidate_universe, list):
        count = len(candidate_universe)
        status = "provided_ticker_list"
    else:
        count = len(rows_by_ticker)
        status = "ohlcv_dict_or_sector_cache"
    return {
        "status": status,
        "ticker_count": count,
        "loaded_ohlcv_ticker_count": len(rows_by_ticker),
    }


def _parameter_summary(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "paper_notional_usd": config["paper_notional_usd"],
        "daily_entry_slots": config["daily_entry_slots"],
        "hold_days": config["hold_days"],
        "same_ticker_cooldown_days": config["same_ticker_cooldown_days"],
        "target_realized_vol_20d": risk_lead.TARGET_REALIZED_VOL_20D,
        "liquidity_full_size_adv20": risk_lead.LIQUIDITY_FULL_SIZE_ADV20,
        "min_vol_scalar": risk_lead.MIN_VOL_SCALAR,
        "min_liquidity_scalar": risk_lead.MIN_LIQUIDITY_SCALAR,
        "min_total_scalar": risk_lead.MIN_TOTAL_SCALAR,
        "max_total_scalar": risk_lead.MAX_TOTAL_SCALAR,
        "source_rule_version": SOURCE_RULE_VERSION,
        "risk_rule_version": RISK_RULE_VERSION,
    }


def _config(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    if overrides:
        cfg.update({key: value for key, value in overrides.items() if value is not None})
    cfg["enabled"] = False
    cfg["trade_enabled"] = False
    return cfg


def _production_impact() -> dict[str, Any]:
    return {
        "shared_policy_changed": True,
        "shared_policy_note": "default-off paper attribution module only; core trading policy unchanged",
        "backtester_adapter_changed": True,
        "run_adapter_changed": True,
        "replay_only": False,
        "default_off_paper_only": True,
        "daily_snapshot_exposed": True,
        "trade_enabled": False,
        "alters_orders": False,
        "production_signal_path_changed": False,
        "production_orders_changed": False,
        "production_watchlist_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "uses_llm": False,
        "uses_free_sec_companyfacts": True,
        "uses_raw_companyfacts_cache": True,
        "uses_free_ohlcv": True,
        "adapter_status": "shared_default_off_paper_helper",
        "scope": "default_off_supplier_financing_debt_relief_paper_attribution",
    }


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value
