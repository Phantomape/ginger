"""Default-off SBC burden-improvement paper sleeve.

Shared helper for the positive exp-20260616-014 replay lead. It uses filed-date
raw SEC Companyfacts annual stock-based compensation, revenue, and gross profit
facts plus liquid SPY-relative OHLCV confirmation to observe one default-off
paper candidate per day.

The sleeve never emits live orders and must not alter core signal generation,
ranking, sizing, exits, heat, LLM/news behavior, watchlists, or live orders.
"""

from __future__ import annotations

import json
import math
import sqlite3
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import broad_market_sector_map
    from constants import ROUND_TRIP_COST_PCT
    from data_paths import DATA_ROOT
    from fill_model import SLIPPAGE_BPS_ENTRY, SLIPPAGE_BPS_TARGET, apply_slippage
    from ohlcv_warehouse import DEFAULT_WAREHOUSE_PATH
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant import broad_market_sector_map
    from quant.constants import ROUND_TRIP_COST_PCT
    from quant.data_paths import DATA_ROOT
    from quant.fill_model import SLIPPAGE_BPS_ENTRY, SLIPPAGE_BPS_TARGET, apply_slippage
    from quant.ohlcv_warehouse import DEFAULT_WAREHOUSE_PATH


SLEEVE_NAME = "SBC_BURDEN_IMPROVEMENT_PAPER"
RULE_VERSION = "sbc_burden_improvement_shared_default_off_adapter_v1"
SOURCE_RULE_VERSION = "stock_based_compensation_burden_improvement_candidate_source_v1"
STATE_SCHEMA_VERSION = 1

DEFAULT_STATE_PATH = DATA_ROOT / "paper_sleeves" / "sbc_burden_improvement" / "state.json"
DEFAULT_SNAPSHOT_LOG_PATH = (
    DATA_ROOT / "paper_sleeves" / "sbc_burden_improvement" / "snapshots.jsonl"
)
RAW_COMPANYFACTS_CACHE = DATA_ROOT / "cache" / "sec" / "companyfacts"

FY_DURATION_MIN = 340
FY_DURATION_MAX = 380
MAX_ANNUAL_FACT_AGE_DAYS = 430
MIN_CURRENT_REVENUE = 250_000_000.0
MIN_CURRENT_GROSS_PROFIT = 20_000_000.0
MIN_CURRENT_SBC = 5_000_000.0
MIN_GROSS_MARGIN = 0.12
MAX_CURRENT_SBC_TO_REVENUE = 0.35
MIN_SBC_RATIO_IMPROVEMENT = 0.003
MIN_REVENUE_GROWTH = -0.05
MIN_GROSS_PROFIT_GROWTH = -0.10

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_RET20_EXCESS_SPY = 0.0
MIN_RET60_EXCESS_SPY = -0.05
MIN_SIGNAL_RETURN = -0.03
MAX_SIGNAL_RETURN = 0.06
MIN_CLOSE_LOCATION = 0.40
MAX_REALIZED_VOL_20D = 0.10

SBC_TAGS = ("ShareBasedCompensation", "AllocatedShareBasedCompensationExpense")
REVENUE_TAGS = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
)
GROSS_PROFIT_TAGS = ("GrossProfit",)

EXCLUDED_TICKERS = {
    "ARKX",
    "BIL",
    "DIA",
    "GLD",
    "IAU",
    "IBIT",
    "IEF",
    "IWM",
    "QQQ",
    "SHY",
    "SLV",
    "SPY",
    "TLT",
    "UFO",
    "UUP",
    "USO",
    "VIXM",
    "VIXY",
    "VXX",
}

DEFAULT_CONFIG = {
    "enabled": False,
    "paper_enabled": True,
    "trade_enabled": False,
    "paper_notional_usd": 4_000.0,
    "daily_entry_slots": 1,
    "max_active_positions": 10,
    "hold_days": 10,
    "same_ticker_cooldown_days": 10,
    "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
    "forward_gate_min_closed_trades": 30,
    "forward_gate_positive_net_pnl": True,
    "forward_gate_min_win_rate": 0.50,
    "forward_gate_max_single_ticker_positive_share": 0.50,
    "forward_gate_max_positive_hhi": 0.35,
}

_RAW_INDEX_CACHE: tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, Any]] | None = None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def empty_sbc_burden_improvement_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "updated_at": None,
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "skipped_days": [],
    }


def empty_sbc_burden_improvement_paper_sleeve_snapshot(
    as_of: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
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
        "sbc_burden_improvement_context": {"status": reason},
        "forward_paper_gate": {"passed": False, "status": "blocked", "reasons": [reason]},
        "production_impact": _production_impact(),
        "error": reason,
    }


def load_sbc_burden_improvement_state(
    path: Path | str = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_sbc_burden_improvement_state()
    with state_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    state = empty_sbc_burden_improvement_state()
    if isinstance(payload, dict):
        state.update(payload)
    _normalise_state(state)
    return state


def save_sbc_burden_improvement_state(
    state: dict[str, Any],
    path: Path | str = DEFAULT_STATE_PATH,
) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now_iso()
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(_safe(state), handle, indent=2, sort_keys=True)
        handle.write("\n")


def append_sbc_burden_improvement_snapshot(
    snapshot: dict[str, Any],
    path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_safe(snapshot), sort_keys=True) + "\n")


def build_sbc_burden_improvement_paper_sleeve_snapshot(
    *,
    as_of: str,
    ohlcv_by_ticker: dict[str, Any],
    candidate_universe: dict[str, Any] | list[str] | None = None,
    sector_entries: dict[str, dict[str, Any]] | None = None,
    quality_index: dict[str, dict[str, list[dict[str, Any]]]] | None = None,
    open_prices: dict[str, Any] | None = None,
    current_prices: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    persist: bool = True,
    state_path: Path | str = DEFAULT_STATE_PATH,
    snapshot_log_path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> dict[str, Any]:
    cfg = _config(config)
    as_of_date = _date10(as_of)
    rows_by_ticker = _normalise_ohlcv_by_ticker(ohlcv_by_ticker)
    if not rows_by_ticker:
        return empty_sbc_burden_improvement_paper_sleeve_snapshot(as_of_date, "missing_ohlcv")
    if "SPY" not in rows_by_ticker:
        return empty_sbc_burden_improvement_paper_sleeve_snapshot(as_of_date, "missing_spy_ohlcv")

    sector_map = _resolve_sector_entries(
        sector_entries=sector_entries,
        candidate_universe=candidate_universe,
        rows_by_ticker=rows_by_ticker,
    )
    quality = quality_index
    quality_summary: dict[str, Any] = {"source": "provided_quality_index", "ticker_count": len(quality or {})}
    if quality is None:
        quality, quality_summary = load_sbc_burden_companyfacts_index()

    working_state = deepcopy(
        state if state is not None else load_sbc_burden_improvement_state(state_path)
    )
    _normalise_state(working_state)

    filled_today = _fill_pending_entries(working_state, rows_by_ticker, as_of_date, cfg)
    closed_today = _advance_open_positions(working_state, rows_by_ticker, as_of_date, cfg)
    candidates, scan = build_sbc_burden_improvement_candidate_rows(
        ohlcv_by_ticker=rows_by_ticker,
        dates=[as_of_date],
        quality_index=quality,
        sector_entries=sector_map,
        candidate_universe=candidate_universe,
        config={**cfg, "require_future_exit": False},
    )
    selected_rows, rejected = select_sbc_burden_improvement_signal_rows(
        rows_by_ticker=rows_by_ticker,
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
        reason = "no_sbc_burden_improvement_candidate" if candidates else "no_raw_sbc_candidate"
        _append_skip_once(working_state, _skip_payload(as_of_date, reason))

    snapshot = _snapshot_payload(
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
        rows_by_ticker=rows_by_ticker,
        config=cfg,
    )
    if persist:
        save_sbc_burden_improvement_state(working_state, state_path)
        append_sbc_burden_improvement_snapshot(snapshot, snapshot_log_path)
    return snapshot


def build_sbc_burden_improvement_historical_trades(
    *,
    ohlcv_by_ticker: dict[str, Any],
    windows: dict[str, dict[str, str]],
    quality_index: dict[str, dict[str, list[dict[str, Any]]]] | None = None,
    candidate_universe: dict[str, Any] | list[str] | None = None,
    sector_entries: dict[str, dict[str, Any]] | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cfg = _config(config)
    rows_by_ticker = _normalise_ohlcv_by_ticker(ohlcv_by_ticker)
    sector_map = _resolve_sector_entries(
        sector_entries=sector_entries,
        candidate_universe=candidate_universe,
        rows_by_ticker=rows_by_ticker,
    )
    quality = quality_index
    quality_summary = {"source": "provided_quality_index", "ticker_count": len(quality or {})}
    if quality is None:
        quality, quality_summary = load_sbc_burden_companyfacts_index()

    all_trades: list[dict[str, Any]] = []
    audit: dict[str, Any] = {
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "quality_index_summary": quality_summary,
        "selected_by_window": {},
        "raw_candidate_count_by_window": {},
        "rejected_count_by_window": {},
        "scan_by_window": {},
    }
    dates = _trading_dates(rows_by_ticker)
    for label, window in windows.items():
        window_dates = [
            day
            for day in dates
            if str(window["start"]) <= day <= str(window["end"])
        ]
        candidates, scan = build_sbc_burden_improvement_candidate_rows(
            ohlcv_by_ticker=rows_by_ticker,
            dates=window_dates,
            quality_index=quality,
            sector_entries=sector_map,
            candidate_universe=candidate_universe,
            config=cfg,
        )
        selected, rejected = select_sbc_burden_improvement_paper_trades(
            rows_by_ticker=rows_by_ticker,
            candidates=candidates,
            config=cfg,
        )
        for trade in selected:
            trade["window"] = label
        all_trades.extend(selected)
        audit["selected_by_window"][label] = len(selected)
        audit["raw_candidate_count_by_window"][label] = len(candidates)
        audit["rejected_count_by_window"][label] = len(rejected)
        audit["scan_by_window"][label] = scan
    audit["total_selected"] = len(all_trades)
    audit["total_raw_candidates"] = sum(audit["raw_candidate_count_by_window"].values())
    return all_trades, audit


def build_sbc_burden_improvement_candidate_rows(
    *,
    ohlcv_by_ticker: dict[str, Any],
    dates: list[str],
    quality_index: dict[str, dict[str, list[dict[str, Any]]]],
    sector_entries: dict[str, dict[str, Any]] | None = None,
    candidate_universe: dict[str, Any] | list[str] | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cfg = _config(config)
    rows_by_ticker = _normalise_ohlcv_by_ticker(ohlcv_by_ticker)
    sector_map = sector_entries or {}
    if candidate_universe is not None and not sector_map:
        sector_map = _resolve_sector_entries(
            sector_entries=None,
            candidate_universe=candidate_universe,
            rows_by_ticker=rows_by_ticker,
        )
    indices = {ticker: _row_index(rows) for ticker, rows in rows_by_ticker.items()}
    allowed = _candidate_universe_tickers(candidate_universe, rows_by_ticker)
    eligible = sorted((set(quality_index) & set(rows_by_ticker) & allowed) - EXCLUDED_TICKERS)
    scan: Counter[str] = Counter()
    scan["scanned_trading_days"] = len(dates)
    scan["eligible_quality_tickers"] = len(eligible)
    candidates: list[dict[str, Any]] = []

    for signal_date in dates:
        signal_date = _date10(signal_date)
        for ticker in eligible:
            scan["ticker_day_evaluations"] += 1
            observation = _sbc_burden_observation(ticker, signal_date, quality_index[ticker])
            if observation is None:
                scan["failed_sbc_burden_gate"] += 1
                continue
            confirm = _price_confirmation(
                rows_by_ticker=rows_by_ticker,
                indices=indices,
                ticker=ticker,
                signal_date=signal_date,
                hold_days=int(cfg["hold_days"]),
                require_future_exit=bool(config.get("require_future_exit", True)) if config else True,
            )
            if confirm is None:
                scan["failed_price_confirmation"] += 1
                continue
            scan["qualified_candidate_rows"] += 1
            meta = sector_map.get(ticker, {})
            sbc_improvement = float(observation["sbc_ratio_improvement"] or 0.0)
            revenue_growth = float(observation["revenue_growth"] or 0.0)
            gross_growth = float(observation["gross_profit_growth"] or 0.0)
            score = (
                5.0 * min(sbc_improvement, 0.08)
                + 0.20 * max(min(revenue_growth, 0.60), -0.05)
                + 0.18 * max(min(gross_growth, 0.60), -0.10)
                + 0.55 * float(confirm["candidate_ret20_excess_spy"])
                + 0.14 * float(confirm["candidate_ret60_excess_spy"])
                + 0.10 * float(confirm["candidate_close_location"])
                + 0.035
                * math.log10(max(float(confirm["candidate_avg_dollar_volume_20d"]), 1.0) / 1_000_000.0)
            )
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": SLEEVE_NAME,
                    "candidate_score": _round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": SOURCE_RULE_VERSION,
                    "known_at": "raw_annual_companyfacts_filed_and_signal_close_before_next_open_paper_entry",
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "sector_coverage_status": meta.get("sector_coverage_status")
                    or meta.get("status"),
                    "uses_free_sec_companyfacts": True,
                    "uses_raw_companyfacts_cache": True,
                    "uses_free_ohlcv": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    "alters_orders": False,
                    **{f"sbc_{k}": value for k, value in observation.items()},
                    **confirm,
                }
            )

    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in candidates:
        key = (row["date"], row["ticker"])
        existing = deduped.get(key)
        if existing is None or float(row["candidate_score"]) > float(existing["candidate_score"]):
            deduped[key] = row
    rows = list(deduped.values())
    rows.sort(key=_candidate_sort_tuple)
    scan["deduped_candidate_rows"] = len(rows)
    scan["candidate_signal_days"] = len({row["date"] for row in rows})
    scan["candidate_tickers"] = len({row["ticker"] for row in rows})
    return rows, {
        **dict(scan),
        "rule_version": SOURCE_RULE_VERSION,
        "max_annual_fact_age_days": MAX_ANNUAL_FACT_AGE_DAYS,
        "min_current_revenue": MIN_CURRENT_REVENUE,
        "min_current_gross_profit": MIN_CURRENT_GROSS_PROFIT,
        "min_current_sbc": MIN_CURRENT_SBC,
        "min_gross_margin": MIN_GROSS_MARGIN,
        "max_current_sbc_to_revenue": MAX_CURRENT_SBC_TO_REVENUE,
        "min_sbc_ratio_improvement": MIN_SBC_RATIO_IMPROVEMENT,
        "min_revenue_growth": MIN_REVENUE_GROWTH,
        "min_gross_profit_growth": MIN_GROSS_PROFIT_GROWTH,
    }


def select_sbc_burden_improvement_signal_rows(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
    existing_state: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return _select_candidates(
        rows_by_ticker=rows_by_ticker,
        candidates=candidates,
        existing_state=existing_state,
        config=config,
        create_trades=False,
    )


def select_sbc_burden_improvement_paper_trades(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
    existing_state: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return _select_candidates(
        rows_by_ticker=rows_by_ticker,
        candidates=candidates,
        existing_state=existing_state,
        config=config,
        create_trades=True,
    )


def replay_trade_from_candidate(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    candidate: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    cfg = _config(config)
    ticker = str(candidate.get("ticker") or "").upper()
    rows = rows_by_ticker.get(ticker) or []
    idx = _row_index(rows).get(str(candidate.get("date") or "")[:10])
    if idx is None:
        return None
    entry_idx = idx + 1
    exit_idx = idx + int(cfg["hold_days"])
    if entry_idx >= len(rows) or exit_idx >= len(rows):
        return None
    entry_raw = _positive_float(rows[entry_idx].get("open"))
    exit_raw = _positive_float(rows[exit_idx].get("close"))
    if entry_raw is None or exit_raw is None:
        return None
    entry_price = apply_slippage(entry_raw, SLIPPAGE_BPS_ENTRY, "buy")
    exit_price = apply_slippage(exit_raw, SLIPPAGE_BPS_TARGET, "sell")
    notional = float(cfg["paper_notional_usd"])
    pnl_pct_net = (exit_price / entry_price) - 1.0 - float(cfg["round_trip_cost_pct"])
    signal_date = str(candidate["date"])[:10]
    return {
        **deepcopy(candidate),
        "decision_id": _decision_id(candidate),
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "signal_date": signal_date,
        "entry_date": rows[entry_idx]["date"],
        "entry_raw_open": _round(entry_raw, 4),
        "entry_price": _round(entry_price, 4),
        "exit_date": rows[exit_idx]["date"],
        "exit_raw_close": _round(exit_raw, 4),
        "exit_price": _round(exit_price, 4),
        "hold_days": int(cfg["hold_days"]),
        "paper_notional_usd": _round(notional, 2),
        "notional_usd": _round(notional, 2),
        "pnl_pct_net": _round(pnl_pct_net, 6),
        "net_return_pct": _round(pnl_pct_net, 6),
        "pnl": _round(notional * pnl_pct_net, 2),
        "paper_status": "closed",
        "trade_enabled": False,
        "alters_orders": False,
    }


def load_sbc_burden_companyfacts_index(
    *,
    warehouse_path: Path | str = DEFAULT_WAREHOUSE_PATH,
    raw_companyfacts_cache: Path | str = RAW_COMPANYFACTS_CACHE,
) -> tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, Any]]:
    global _RAW_INDEX_CACHE
    if _RAW_INDEX_CACHE is not None:
        return _RAW_INDEX_CACHE

    warehouse = Path(warehouse_path)
    cache_dir = Path(raw_companyfacts_cache)
    stats: Counter[str] = Counter()
    ticker_ciks: dict[str, int] = {}
    if warehouse.exists():
        warehouse_uri = f"file:{warehouse.resolve().as_posix()}?mode=ro&immutable=1"
        with sqlite3.connect(warehouse_uri, uri=True) as con:
            rows = con.execute(
                """
                select u.ticker, u.cik
                from ticker_universe u
                join coverage_summary c on c.ticker = u.ticker
                where u.hygiene_pass = 1
                  and c.all_windows_full_liquid = 1
                  and u.cik is not null
                order by u.ticker
                """
            ).fetchall()
        for ticker, cik in rows:
            try:
                ticker_ciks[str(ticker).upper()] = int(cik)
            except (TypeError, ValueError):
                stats["invalid_cik_rows"] += 1

    index: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for ticker, cik in ticker_ciks.items():
        stats["warehouse_tickers_with_cik"] += 1
        path = cache_dir / f"CIK{cik:010d}.json"
        if not path.exists():
            stats["missing_companyfacts_cache_file"] += 1
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            stats["unreadable_companyfacts_cache_file"] += 1
            continue
        usgaap = payload.get("facts", {}).get("us-gaap", {})
        sbc_facts = _raw_annual_facts(usgaap, SBC_TAGS)
        revenue_facts = _raw_annual_facts(usgaap, REVENUE_TAGS)
        gross_profit_facts = _raw_annual_facts(usgaap, GROSS_PROFIT_TAGS)
        if not sbc_facts:
            stats["tickers_missing_raw_annual_sbc"] += 1
            continue
        if not revenue_facts:
            stats["tickers_missing_raw_annual_revenue"] += 1
            continue
        if not gross_profit_facts:
            stats["tickers_missing_raw_annual_gross_profit"] += 1
            continue
        index[ticker] = {
            "sbc": sbc_facts,
            "revenue": revenue_facts,
            "gross_profit": gross_profit_facts,
        }
        stats["tickers_with_raw_annual_sbc_revenue_gross_profit"] += 1
        stats["raw_annual_sbc_fact_count"] += len(sbc_facts)
        stats["raw_annual_revenue_fact_count"] += len(revenue_facts)
        stats["raw_annual_gross_profit_fact_count"] += len(gross_profit_facts)

    summary = {
        "raw_companyfacts_cache": str(cache_dir),
        "warehouse_source": str(warehouse),
        "sbc_tags": list(SBC_TAGS),
        "revenue_tags": list(REVENUE_TAGS),
        "gross_profit_tags": list(GROSS_PROFIT_TAGS),
        **dict(stats),
    }
    _RAW_INDEX_CACHE = (index, summary)
    return _RAW_INDEX_CACHE


def _raw_annual_facts(usgaap: dict[str, Any], tags: tuple[str, ...]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for tag in tags:
        units = usgaap.get(tag, {}).get("units", {})
        for rows in units.values():
            if not isinstance(rows, list):
                continue
            for raw in rows:
                fp = str(raw.get("fp") or "").upper()
                form = str(raw.get("form") or "").upper()
                if fp != "FY" or form not in {"10-K", "10-K/A", "20-F", "20-F/A"}:
                    continue
                start = _date10(raw.get("start"))
                end = _date10(raw.get("end"))
                filed = _date10(raw.get("filed"))
                value = _float_or_none(raw.get("val"))
                if not start or not end or not filed or value is None:
                    continue
                duration = _days_between(end, start)
                if not (FY_DURATION_MIN <= duration <= FY_DURATION_MAX):
                    continue
                facts.append(
                    {
                        "tag": tag,
                        "start": start,
                        "end": end,
                        "filed": filed,
                        "value": value,
                        "duration_days": duration,
                    }
                )
    facts.sort(key=lambda row: (row["filed"], row["end"], row.get("tag") or ""))
    return facts


def _sbc_burden_observation(
    ticker: str,
    asof: str,
    facts: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    current_sbc = _latest_sbc_fact(facts["sbc"], asof=asof)
    if current_sbc is None:
        return None
    if _days_between(asof, current_sbc["filed"]) > MAX_ANNUAL_FACT_AGE_DAYS:
        return None

    current_revenue = _latest_period_fact(facts["revenue"], asof=asof, end=current_sbc["end"])
    current_gross_profit = _latest_period_fact(
        facts["gross_profit"], asof=asof, end=current_sbc["end"]
    )
    prior_sbc = _latest_sbc_fact(
        facts["sbc"],
        asof=asof,
        before_end=current_sbc["end"],
        tag=str(current_sbc.get("tag") or ""),
    )
    if current_revenue is None or current_gross_profit is None or prior_sbc is None:
        return None
    prior_revenue = _latest_period_fact(facts["revenue"], asof=asof, end=prior_sbc["end"])
    prior_gross_profit = _latest_period_fact(
        facts["gross_profit"], asof=asof, end=prior_sbc["end"]
    )
    if prior_revenue is None or prior_gross_profit is None:
        return None

    current_sbc_value = abs(float(current_sbc["value"]))
    prior_sbc_value = abs(float(prior_sbc["value"]))
    current_revenue_value = float(current_revenue["value"])
    prior_revenue_value = float(prior_revenue["value"])
    current_gross_profit_value = float(current_gross_profit["value"])
    prior_gross_profit_value = float(prior_gross_profit["value"])
    if (
        current_sbc_value < MIN_CURRENT_SBC
        or current_revenue_value < MIN_CURRENT_REVENUE
        or prior_revenue_value <= 0.0
        or current_gross_profit_value < MIN_CURRENT_GROSS_PROFIT
        or prior_gross_profit_value <= 0.0
    ):
        return None

    current_ratio = current_sbc_value / current_revenue_value
    prior_ratio = prior_sbc_value / prior_revenue_value
    ratio_improvement = prior_ratio - current_ratio
    gross_margin = current_gross_profit_value / current_revenue_value
    revenue_growth = (current_revenue_value - prior_revenue_value) / abs(prior_revenue_value)
    gross_profit_growth = (current_gross_profit_value - prior_gross_profit_value) / abs(
        prior_gross_profit_value
    )
    if current_ratio > MAX_CURRENT_SBC_TO_REVENUE:
        return None
    if ratio_improvement < MIN_SBC_RATIO_IMPROVEMENT:
        return None
    if gross_margin < MIN_GROSS_MARGIN:
        return None
    if revenue_growth < MIN_REVENUE_GROWTH:
        return None
    if gross_profit_growth < MIN_GROSS_PROFIT_GROWTH:
        return None

    return {
        "ticker": ticker,
        "current_period_end": current_sbc["end"],
        "current_sbc_filed": current_sbc["filed"],
        "current_sbc_tag": current_sbc.get("tag"),
        "current_sbc_value": _round(current_sbc_value, 2),
        "current_revenue_value": _round(current_revenue_value, 2),
        "current_gross_profit_value": _round(current_gross_profit_value, 2),
        "prior_period_end": prior_sbc["end"],
        "prior_sbc_value": _round(prior_sbc_value, 2),
        "prior_revenue_value": _round(prior_revenue_value, 2),
        "prior_gross_profit_value": _round(prior_gross_profit_value, 2),
        "current_sbc_to_revenue": _round(current_ratio, 6),
        "prior_sbc_to_revenue": _round(prior_ratio, 6),
        "sbc_ratio_improvement": _round(ratio_improvement, 6),
        "gross_margin": _round(gross_margin, 6),
        "revenue_growth": _round(revenue_growth, 6),
        "gross_profit_growth": _round(gross_profit_growth, 6),
        "fact_age_days": _days_between(asof, current_sbc["filed"]),
        "known_at": "raw_annual_companyfacts_filed_and_signal_close_before_next_open_paper_entry",
        "rule_version": SOURCE_RULE_VERSION,
    }


def _latest_sbc_fact(
    facts: list[dict[str, Any]],
    *,
    asof: str,
    before_end: str | None = None,
    tag: str | None = None,
) -> dict[str, Any] | None:
    candidates = []
    for fact in facts:
        if fact["filed"] > asof:
            continue
        if before_end is not None and fact["end"] >= before_end:
            continue
        if tag is not None and fact.get("tag") != tag:
            continue
        candidates.append(fact)
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda row: (
            row["end"],
            row["filed"],
            -_sbc_tag_priority(str(row.get("tag") or "")),
        ),
    )


def _latest_period_fact(
    facts: list[dict[str, Any]],
    *,
    asof: str,
    end: str,
) -> dict[str, Any] | None:
    candidates = [fact for fact in facts if fact["filed"] <= asof and fact["end"] == end]
    if not candidates:
        return None
    return max(candidates, key=lambda row: (row["filed"], row.get("tag") or ""))


def _price_confirmation(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    ticker: str,
    signal_date: str,
    hold_days: int,
    require_future_exit: bool,
) -> dict[str, Any] | None:
    rows = rows_by_ticker.get(ticker) or []
    spy_rows = rows_by_ticker.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None or idx < 60 or spy_idx < 60:
        return None
    if require_future_exit and idx + hold_days >= len(rows):
        return None
    close = _positive_float(rows[idx].get("close"))
    if close is None or close < MIN_PRICE:
        return None
    adv20 = _avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None
    signal_return = _daily_return(rows, idx)
    close_location = _close_location(rows[idx])
    ret20 = _ret(rows, idx, 20)
    ret60 = _ret(rows, idx, 60)
    spy_ret20 = _ret(spy_rows, spy_idx, 20)
    spy_ret60 = _ret(spy_rows, spy_idx, 60)
    realized_vol = _realized_vol(rows, idx, 20)
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
    if signal_return < MIN_SIGNAL_RETURN or signal_return > MAX_SIGNAL_RETURN:
        return None
    if close_location < MIN_CLOSE_LOCATION:
        return None
    if realized_vol > MAX_REALIZED_VOL_20D:
        return None
    ret20_excess_spy = ret20 - spy_ret20
    ret60_excess_spy = ret60 - spy_ret60
    if ret20_excess_spy < MIN_RET20_EXCESS_SPY:
        return None
    if ret60_excess_spy < MIN_RET60_EXCESS_SPY:
        return None
    volume_ratio = _volume_ratio(rows, idx) or 0.0
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


def _select_candidates(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
    existing_state: dict[str, Any] | None,
    config: dict[str, Any] | None,
    create_trades: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cfg = _config(config)
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    used_date_counts: Counter[str] = Counter()
    all_dates = _trading_dates(rows_by_ticker)
    date_pos = {day: idx for idx, day in enumerate(all_dates)}
    next_allowed_pos_by_ticker = _state_cooldown_map(
        existing_state=existing_state,
        date_pos=date_pos,
        config=cfg,
    )
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
        next_allowed = next_allowed_pos_by_ticker.get(ticker, -1)
        if pos < next_allowed:
            rejected.append({**row, "filter_reason": "same_ticker_cooldown"})
            continue
        if create_trades:
            trade = replay_trade_from_candidate(
                rows_by_ticker=rows_by_ticker,
                candidate=row,
                config=cfg,
            )
            if trade is None:
                rejected.append({**row, "filter_reason": "missing_next_open_or_exit"})
                continue
            selected.append(trade)
        else:
            selected.append(
                {
                    **deepcopy(row),
                    "decision_id": _decision_id(row),
                    "sleeve": SLEEVE_NAME,
                    "rule_version": RULE_VERSION,
                    "source_rule_version": SOURCE_RULE_VERSION,
                    "signal_date": signal_date,
                    "paper_status": "candidate",
                    "trade_enabled": False,
                    "alters_orders": False,
                }
            )
        used_date_counts[signal_date] += 1
        next_allowed_pos_by_ticker[ticker] = pos + int(cfg["same_ticker_cooldown_days"])
    return selected, rejected


def _pending_entry_from_candidate(candidate: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(candidate)
    out.update(
        {
            "decision_id": _decision_id(candidate),
            "sleeve": SLEEVE_NAME,
            "rule_version": RULE_VERSION,
            "source_rule_version": SOURCE_RULE_VERSION,
            "signal_date": str(candidate.get("date") or candidate.get("signal_date") or "")[:10],
            "paper_notional_usd": float(config["paper_notional_usd"]),
            "notional_usd": float(config["paper_notional_usd"]),
            "entry_timing": "next_session_open",
            "hold_days": int(config["hold_days"]),
            "paper_status": "pending_entry",
            "trade_enabled": False,
            "alters_orders": False,
        }
    )
    return out


def _fill_pending_entries(
    state: dict[str, Any],
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    as_of: str,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    filled: list[dict[str, Any]] = []
    remaining: list[dict[str, Any]] = []
    for pending in state.get("pending_entries") or []:
        if not isinstance(pending, dict):
            continue
        ticker = str(pending.get("ticker") or "").upper()
        rows = rows_by_ticker.get(ticker) or []
        signal_idx = _row_index(rows).get(str(pending.get("signal_date") or "")[:10])
        today_idx = _row_index(rows).get(as_of)
        if signal_idx is None or today_idx is None or today_idx <= signal_idx:
            remaining.append(pending)
            continue
        entry_raw = _positive_float(rows[today_idx].get("open"))
        if entry_raw is None:
            remaining.append(pending)
            continue
        entry_price = apply_slippage(entry_raw, SLIPPAGE_BPS_ENTRY, "buy")
        open_position = {
            **pending,
            "entry_date": as_of,
            "entry_raw_open": _round(entry_raw, 4),
            "entry_price": _round(entry_price, 4),
            "entry_trading_day_index": today_idx,
            "planned_exit_trading_day_index": signal_idx + int(config["hold_days"]),
            "paper_status": "open",
        }
        state["open_positions"].append(open_position)
        filled.append(open_position)
    state["pending_entries"] = remaining
    return filled


def _advance_open_positions(
    state: dict[str, Any],
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    as_of: str,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    closed_today: list[dict[str, Any]] = []
    still_open: list[dict[str, Any]] = []
    for position in state.get("open_positions") or []:
        if not isinstance(position, dict):
            continue
        ticker = str(position.get("ticker") or "").upper()
        rows = rows_by_ticker.get(ticker) or []
        idx = _row_index(rows).get(as_of)
        planned_exit = _int_or_none(position.get("planned_exit_trading_day_index"))
        if idx is None or planned_exit is None or idx < planned_exit:
            still_open.append(position)
            continue
        exit_raw = _positive_float(rows[idx].get("close"))
        entry_price = _positive_float(position.get("entry_price"))
        if exit_raw is None or entry_price is None:
            still_open.append(position)
            continue
        exit_price = apply_slippage(exit_raw, SLIPPAGE_BPS_TARGET, "sell")
        notional = float(position.get("paper_notional_usd") or config["paper_notional_usd"])
        pnl_pct_net = (exit_price / entry_price) - 1.0 - float(config["round_trip_cost_pct"])
        closed = {
            **position,
            "exit_date": as_of,
            "exit_raw_close": _round(exit_raw, 4),
            "exit_price": _round(exit_price, 4),
            "pnl_pct_net": _round(pnl_pct_net, 6),
            "net_return_pct": _round(pnl_pct_net, 6),
            "pnl": _round(notional * pnl_pct_net, 2),
            "paper_status": "closed",
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
        "sbc_burden_improvement_context": {
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


def _resolve_sector_entries(
    *,
    sector_entries: dict[str, dict[str, Any]] | None,
    candidate_universe: dict[str, Any] | list[str] | None,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
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

    allowed = _candidate_universe_tickers(candidate_universe, rows_by_ticker)
    out: dict[str, dict[str, Any]] = {}
    for ticker, meta in raw_entries.items():
        ticker_u = str(ticker).upper()
        if ticker_u in EXCLUDED_TICKERS or "." in ticker_u or "-" in ticker_u:
            continue
        if ticker_u not in rows_by_ticker or ticker_u not in allowed:
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
    rows_by_ticker: dict[str, list[dict[str, Any]]],
) -> set[str]:
    if isinstance(candidate_universe, list):
        return {str(ticker).upper() for ticker in candidate_universe}
    if isinstance(candidate_universe, dict) and candidate_universe.get("tickers"):
        return {str(ticker).upper() for ticker in candidate_universe.get("tickers") or []}
    return set(rows_by_ticker)


def _normalise_ohlcv_by_ticker(ohlcv_by_ticker: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return {
        str(ticker).upper(): _normalise_ohlcv_rows(rows)
        for ticker, rows in (ohlcv_by_ticker or {}).items()
        if _normalise_ohlcv_rows(rows)
    }


def _normalise_ohlcv_rows(rows: Any) -> list[dict[str, Any]]:
    if rows is None:
        return []
    if hasattr(rows, "to_dict"):
        try:
            rows = rows.to_dict("records")
        except TypeError:
            rows = rows.to_dict()
    out: list[dict[str, Any]] = []
    for raw in rows or []:
        if not isinstance(raw, dict):
            continue
        date_value = raw.get("date", raw.get("Date"))
        date_text = _date10(date_value)
        open_ = _float_or_none(raw.get("open", raw.get("Open")))
        high = _float_or_none(raw.get("high", raw.get("High")))
        low = _float_or_none(raw.get("low", raw.get("Low")))
        close = _float_or_none(raw.get("close", raw.get("Close")))
        volume = _float_or_none(raw.get("volume", raw.get("Volume")))
        if not date_text or None in (open_, high, low, close, volume):
            continue
        out.append(
            {
                "date": date_text,
                "open": float(open_),
                "high": float(high),
                "low": float(low),
                "close": float(close),
                "volume": float(volume),
            }
        )
    out.sort(key=lambda row: row["date"])
    return out


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
    return f"{SLEEVE_NAME}:{SOURCE_RULE_VERSION}:{signal_date}:{ticker}"


def _candidate_sort_tuple(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row["date"],
        -float(row.get("candidate_score") or 0.0),
        -float(row.get("sbc_sbc_ratio_improvement") or 0.0),
        -float(row.get("sbc_revenue_growth") or 0.0),
        -float(row.get("candidate_ret20_excess_spy") or 0.0),
        -float(row.get("candidate_avg_dollar_volume_20d") or 0.0),
        row["ticker"],
    )


def _sbc_tag_priority(tag: str) -> int:
    try:
        return SBC_TAGS.index(tag)
    except ValueError:
        return len(SBC_TAGS)


def _date10(value: Any) -> str:
    text = str(value or "")[:10]
    return text if len(text) == 10 and text[4] == "-" and text[7] == "-" else ""


def _days_between(later: str, earlier: str) -> int:
    try:
        return (datetime.fromisoformat(_date10(later)) - datetime.fromisoformat(_date10(earlier))).days
    except ValueError:
        return 0


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


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


def _row_index(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {str(row.get("date") or "")[:10]: idx for idx, row in enumerate(rows)}


def _trading_dates(rows_by_ticker: dict[str, list[dict[str, Any]]]) -> list[str]:
    return sorted({row["date"] for rows in rows_by_ticker.values() for row in rows})


def _ret(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < lookback:
        return None
    start = _positive_float(rows[idx - lookback].get("close"))
    end = _positive_float(rows[idx].get("close"))
    if start is None or end is None:
        return None
    return end / start - 1.0


def _daily_return(rows: list[dict[str, Any]], idx: int) -> float | None:
    if idx <= 0:
        return None
    prior = _positive_float(rows[idx - 1].get("close"))
    close = _positive_float(rows[idx].get("close"))
    if prior is None or close is None:
        return None
    return close / prior - 1.0


def _close_location(row: dict[str, Any]) -> float | None:
    high = _positive_float(row.get("high"))
    low = _positive_float(row.get("low"))
    close = _positive_float(row.get("close"))
    if high is None or low is None or close is None or high <= low:
        return None
    return (close - low) / (high - low)


def _avg_dollar_volume(rows: list[dict[str, Any]], idx: int, lookback: int = 20) -> float | None:
    if idx < lookback - 1:
        return None
    values: list[float] = []
    for row in rows[idx - lookback + 1 : idx + 1]:
        close = _positive_float(row.get("close"))
        volume = _positive_float(row.get("volume"))
        if close is None or volume is None:
            return None
        values.append(close * volume)
    return sum(values) / len(values)


def _volume_ratio(rows: list[dict[str, Any]], idx: int, lookback: int = 20) -> float | None:
    if idx < lookback:
        return None
    current = _positive_float(rows[idx].get("volume"))
    prior = [_positive_float(row.get("volume")) for row in rows[idx - lookback : idx]]
    if current is None or any(value is None for value in prior):
        return None
    avg = sum(float(value) for value in prior if value is not None) / len(prior)
    if avg <= 0.0:
        return None
    return current / avg


def _realized_vol(rows: list[dict[str, Any]], idx: int, lookback: int = 20) -> float | None:
    if idx < lookback:
        return None
    rets: list[float] = []
    for pos in range(idx - lookback + 1, idx + 1):
        daily = _daily_return(rows, pos)
        if daily is None:
            return None
        rets.append(daily)
    mean = sum(rets) / len(rets)
    variance = sum((ret - mean) ** 2 for ret in rets) / len(rets)
    return math.sqrt(variance)


def _unrealized_pnl(
    open_positions: list[dict[str, Any]],
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    as_of: str,
) -> float:
    total = 0.0
    for position in open_positions:
        ticker = str(position.get("ticker") or "").upper()
        rows = rows_by_ticker.get(ticker) or []
        idx = _row_index(rows).get(as_of)
        entry = _positive_float(position.get("entry_price"))
        close = _positive_float(rows[idx].get("close")) if idx is not None else None
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
    return {
        "passed": not reasons,
        "status": "passed" if not reasons else "blocked",
        "reasons": reasons,
        "closed_trade_count": closed_count,
        "net_pnl": round(pnl, 2),
        "win_rate": round(win_rate, 4),
        "min_closed_trades": min_closed,
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
        "max_annual_fact_age_days": MAX_ANNUAL_FACT_AGE_DAYS,
        "min_current_revenue": MIN_CURRENT_REVENUE,
        "min_current_gross_profit": MIN_CURRENT_GROSS_PROFIT,
        "min_current_sbc": MIN_CURRENT_SBC,
        "min_gross_margin": MIN_GROSS_MARGIN,
        "max_current_sbc_to_revenue": MAX_CURRENT_SBC_TO_REVENUE,
        "min_sbc_ratio_improvement": MIN_SBC_RATIO_IMPROVEMENT,
        "min_revenue_growth": MIN_REVENUE_GROWTH,
        "min_gross_profit_growth": MIN_GROSS_PROFIT_GROWTH,
        "min_price": MIN_PRICE,
        "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
        "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
        "min_ret60_excess_spy": MIN_RET60_EXCESS_SPY,
        "min_signal_return": MIN_SIGNAL_RETURN,
        "max_signal_return": MAX_SIGNAL_RETURN,
        "min_close_location": MIN_CLOSE_LOCATION,
        "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
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
        "scope": "default_off_sbc_burden_improvement_paper_attribution",
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
