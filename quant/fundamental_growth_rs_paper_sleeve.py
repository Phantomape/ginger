"""Default-off Companyfacts growth plus RS paper sleeve.

This shared helper turns the accepted exp-20260528-008 replay lead into a
production-visible forward observation boundary. It emits paper candidates and
ledger state only; it never emits live orders and never changes core signal
generation, ranking, sizing, exits, heat, LLM, or news behavior.
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from constants import ROUND_TRIP_COST_PCT
    from data_paths import DATA_ROOT, data_artifact_path
    from fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage
    from risk_engine import SECTOR_MAP
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant.constants import ROUND_TRIP_COST_PCT
    from quant.data_paths import DATA_ROOT, data_artifact_path
    from quant.fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage
    from quant.risk_engine import SECTOR_MAP


SLEEVE_NAME = "FUNDAMENTAL_GROWTH_RS_PAPER"
RULE_VERSION = "fundamental_growth_rs_low_volume_participation_shared_adapter_v1"
SOURCE_RULE_VERSION = "fundamental_growth_rs_operating_profit_quality_v1"
GOVERNOR_RULE_VERSION = "operating_profit_quality_closed_ledger_governor_v1"
LOW_VOLUME_PARTICIPATION_RULE_VERSION = "fundamental_growth_rs_low_volume_participation_support_v1"
REPLACEMENT_VALUE_RULE_VERSION = "fundamental_growth_rs_forward_replacement_value_v1"
STATE_SCHEMA_VERSION = 1

DEFAULT_STATE_PATH = data_artifact_path("fundamental_growth_rs_paper_state")
DEFAULT_SNAPSHOT_LOG_PATH = data_artifact_path("fundamental_growth_rs_paper_snapshots")
DEFAULT_NON_OHLCV_DIR = DATA_ROOT / "non_ohlcv"

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

DEFAULT_CONFIG = {
    "enabled": False,
    "paper_enabled": True,
    "trade_enabled": False,
    "paper_notional_usd": 10_000.0,
    "daily_entry_slots": 1,
    "max_active_positions": 6,
    "hold_days": 10,
    "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
    "eps_growth_threshold": 0.25,
    "revenue_growth_threshold": 0.20,
    "min_fundamental_points": 1,
    "min_rs_proxy_score": 0.75,
    "min_available_rs_windows": 2,
    "rs_windows": (20, 60, 120),
    "trend_ma_days": 50,
    "volume_lookback_days": 20,
    "min_avg_dollar_volume_20": 40_000_000.0,
    "min_ret20_excess_spy": 0.0,
    "min_signal_day_rs_vs_spy": -0.015,
    "quarterly_duration_min": 60,
    "quarterly_duration_max": 130,
    "ticker_closed_profit_cap_usd": 9_000.0,
    "ticker_profit_cap_scalar": 0.05,
    "global_closed_drawdown_trigger_usd": 7_500.0,
    "global_drawdown_scalar": 0.25,
    "low_volume_ratio_20_max": 0.90,
    "low_volume_notional_scalar": 1.10,
    "forward_gate_min_closed_trades": 30,
    "forward_gate_positive_net_pnl": True,
    "forward_gate_min_win_rate": 0.50,
    "forward_gate_max_single_ticker_positive_share": 0.40,
    "forward_gate_max_positive_hhi": 0.30,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def empty_fundamental_growth_rs_paper_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "updated_at": None,
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "skipped_entries": [],
    }


def load_fundamental_growth_rs_paper_state(
    path: Path | str = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_fundamental_growth_rs_paper_state()
    with state_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    state = empty_fundamental_growth_rs_paper_state()
    if isinstance(payload, dict):
        state.update(payload)
    _normalise_state(state)
    return state


def save_fundamental_growth_rs_paper_state(
    state: dict[str, Any],
    path: Path | str = DEFAULT_STATE_PATH,
) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now_iso()
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(_safe(state), handle, indent=2, sort_keys=True)
        handle.write("\n")


def append_fundamental_growth_rs_paper_snapshot(
    snapshot: dict[str, Any],
    path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_safe(snapshot), sort_keys=True) + "\n")


def empty_fundamental_growth_rs_paper_sleeve_snapshot(
    as_of: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "governor_rule_version": GOVERNOR_RULE_VERSION,
        "asof_date": _date10(as_of),
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": False,
        "trade_enabled": False,
        "candidate_count": 0,
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
        "fundamental_data": {"status": reason, "row_count": 0},
        "low_volume_participation": {
            "rule_version": LOW_VOLUME_PARTICIPATION_RULE_VERSION,
            "read_only": True,
            "trade_enabled": False,
            "alters_orders": False,
            "supported_candidate_count": 0,
        },
        "forward_paper_gate": {"passed": False, "status": "blocked", "reasons": [reason]},
        "production_impact": _production_impact(),
        "error": reason,
    }


def build_fundamental_growth_rs_paper_sleeve_snapshot(
    *,
    as_of: str,
    ohlcv_by_ticker: dict[str, Any] | None = None,
    candidate_universe: dict[str, Any] | list[str] | None = None,
    companyfacts_rows: list[dict[str, Any]] | None = None,
    non_ohlcv_dir: Path | str = DEFAULT_NON_OHLCV_DIR,
    current_core_tickers: set[str] | list[str] | None = None,
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
    rows_by_ticker = {
        str(ticker).upper(): _normalise_ohlcv_rows(rows)
        for ticker, rows in (ohlcv_by_ticker or {}).items()
    }
    if not rows_by_ticker:
        return empty_fundamental_growth_rs_paper_sleeve_snapshot(as_of_date, "missing_ohlcv")

    universe = _normalise_candidate_universe(candidate_universe, rows_by_ticker)
    facts = (
        [dict(row) for row in companyfacts_rows]
        if companyfacts_rows is not None
        else load_companyfacts_rows(
            max_filed=as_of_date,
            tickers=universe["tickers"],
            non_ohlcv_dir=non_ohlcv_dir,
        )
    )

    working_state = deepcopy(
        state
        if state is not None
        else load_fundamental_growth_rs_paper_state(state_path)
    )
    _normalise_state(working_state)

    current = _normalise_prices(current_prices)
    opens = _normalise_prices(open_prices)
    if not current:
        current = {
            ticker: rows[idx]["close"]
            for ticker, rows in rows_by_ticker.items()
            for idx in [_latest_index_on_or_before(rows, as_of_date)]
            if idx is not None and _positive_float(rows[idx].get("close")) is not None
        }
    if not opens:
        opens = {
            ticker: rows[idx]["open"]
            for ticker, rows in rows_by_ticker.items()
            for idx in [_latest_index_on_or_before(rows, as_of_date)]
            if idx is not None and _positive_float(rows[idx].get("open")) is not None
        }

    closed_today = _advance_open_positions(
        working_state,
        as_of=as_of_date,
        current_prices=current,
        config=cfg,
    )
    filled_today, skipped_today = _fill_pending_entries(
        working_state,
        as_of=as_of_date,
        open_prices=opens,
        current_prices=current,
        config=cfg,
    )

    active_tickers = {
        str(row.get("ticker") or "").upper()
        for row in working_state.get("open_positions") or []
        if isinstance(row, dict)
    }
    pending_tickers = {
        str(row.get("ticker") or "").upper()
        for row in working_state.get("pending_entries") or []
        if isinstance(row, dict)
    }
    core_tickers = {str(ticker).upper() for ticker in (current_core_tickers or []) if ticker}
    candidates, rejected = build_fundamental_growth_rs_candidates(
        as_of=as_of_date,
        ohlcv_by_ticker=rows_by_ticker,
        companyfacts_rows=facts,
        candidate_universe=universe,
        open_position_tickers=active_tickers,
        pending_tickers=pending_tickers,
        current_core_tickers=core_tickers,
        closed_positions=working_state.get("closed_positions") or [],
        config=cfg,
    )

    open_positions = working_state.get("open_positions") or []
    room = max(0, int(cfg["max_active_positions"]) - len(open_positions))
    new_pending: list[dict[str, Any]] = []
    if room > 0 and cfg.get("paper_enabled", True):
        capacity = min(room, int(cfg["daily_entry_slots"]))
        for candidate in candidates[:capacity]:
            entry = _pending_entry_from_candidate(candidate, as_of=as_of_date, config=cfg)
            working_state["pending_entries"].append(entry)
            new_pending.append(entry)
    for candidate in candidates[len(new_pending):]:
        rejected.append({**candidate, "reasons": ["daily_top1_or_capacity_limit"]})

    closed = working_state.get("closed_positions") or []
    open_positions = working_state.get("open_positions") or []
    replacement_value_report = build_fundamental_growth_rs_replacement_value_report(
        candidates=candidates,
        pending_entries=working_state.get("pending_entries") or [],
        open_positions=open_positions,
        closed_positions=closed,
        skipped_entries=working_state.get("skipped_entries") or [],
        config=cfg,
    )
    gate = _forward_paper_gate(closed, cfg)
    governor_state = _closed_ledger_governor_state(closed, cfg)

    snapshot = {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "governor_rule_version": GOVERNOR_RULE_VERSION,
        "replacement_value_rule_version": REPLACEMENT_VALUE_RULE_VERSION,
        "asof_date": as_of_date,
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": bool(cfg.get("paper_enabled", True)),
        "trade_enabled": False,
        "trade_enabled_reason": "default_off_until_forward_gate_and_live_adapter_pass",
        "candidate_count": len(candidates),
        "rejected_candidate_count": len(rejected),
        "new_pending_count": len(new_pending),
        "filled_count": len(filled_today),
        "closed_count_today": len(closed_today),
        "pending_count": len(working_state.get("pending_entries") or []),
        "open_position_count": len(open_positions),
        "closed_position_count": len(closed),
        "realized_pnl_to_date": round(sum(_money(row.get("pnl")) for row in closed), 2),
        "unrealized_pnl": round(sum(_money(row.get("unrealized_pnl")) for row in open_positions), 2),
        "candidate_universe": {
            "status": universe["status"],
            "ticker_count": len(universe["tickers"]),
        },
        "fundamental_data": {
            "status": "ok" if facts else "missing_companyfacts_rows",
            "row_count": len(facts),
        },
        "closed_ledger_governor": governor_state,
        "low_volume_participation": {
            "rule_version": LOW_VOLUME_PARTICIPATION_RULE_VERSION,
            "read_only": True,
            "trade_enabled": False,
            "alters_orders": False,
            "volume_ratio_20_max": float(cfg["low_volume_ratio_20_max"]),
            "paper_notional_scalar": float(cfg["low_volume_notional_scalar"]),
            "supported_candidate_count": sum(
                1 for row in candidates if row.get("low_volume_participation_pass_v1")
            ),
        },
        "candidates": deepcopy(candidates),
        "rejected_candidates": deepcopy(rejected[:50]),
        "new_pending_entries": deepcopy(new_pending),
        "filled_entries": deepcopy(filled_today),
        "closed_positions_today": deepcopy(closed_today),
        "pending_entries": deepcopy(working_state["pending_entries"]),
        "open_positions": deepcopy(open_positions),
        "closed_positions": deepcopy(closed),
        "skipped_entries_today": deepcopy(skipped_today),
        "replacement_value_report": replacement_value_report,
        "forward_paper_gate": gate,
        "production_impact": _production_impact(),
        "next_action": "paper_observe_forward_replacement_value_no_orders",
    }

    if persist:
        save_fundamental_growth_rs_paper_state(working_state, state_path)
        append_fundamental_growth_rs_paper_snapshot(snapshot, snapshot_log_path)
    return _safe(snapshot)


def build_fundamental_growth_rs_candidates(
    *,
    as_of: str,
    ohlcv_by_ticker: dict[str, Any],
    companyfacts_rows: list[dict[str, Any]],
    candidate_universe: dict[str, Any] | list[str] | None = None,
    open_position_tickers: set[str] | None = None,
    pending_tickers: set[str] | None = None,
    current_core_tickers: set[str] | None = None,
    closed_positions: list[dict[str, Any]] | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cfg = _config(config)
    as_of_date = _date10(as_of)
    rows_by_ticker = {
        str(ticker).upper(): _normalise_ohlcv_rows(rows)
        for ticker, rows in (ohlcv_by_ticker or {}).items()
    }
    universe = _normalise_candidate_universe(candidate_universe, rows_by_ticker)
    tickers = [
        ticker
        for ticker in universe["tickers"]
        if ticker in rows_by_ticker
        and ticker not in EXCLUDED_TICKERS
        and SECTOR_MAP.get(ticker, "Unknown") not in {"Unknown", "ETF", "Commodities"}
    ]
    fundamentals = CompanyfactsFundamentalIndex(companyfacts_rows, config=cfg)
    rs_by_ticker = _rs_context_by_ticker(
        rows_by_ticker,
        tickers=tickers,
        date=as_of_date,
        config=cfg,
    )
    active = {str(value).upper() for value in (open_position_tickers or set())}
    pending = {str(value).upper() for value in (pending_tickers or set())}
    core = {str(value).upper() for value in (current_core_tickers or set())}
    governor = _closed_ledger_governor_state(closed_positions or [], cfg)

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for ticker in tickers:
        candidate = _candidate_for_ticker(
            rows_by_ticker=rows_by_ticker,
            ticker=ticker,
            as_of=as_of_date,
            fundamentals=fundamentals,
            rs_by_ticker=rs_by_ticker,
            governor=governor,
            config=cfg,
        )
        if candidate is None:
            continue
        reasons: list[str] = []
        if ticker in active:
            reasons.append("already_open_in_paper_sleeve")
        if ticker in pending:
            reasons.append("already_pending_in_paper_sleeve")
        if ticker in core:
            reasons.append("same_ticker_core_overlap")
        if reasons:
            rejected.append({**candidate, "reasons": reasons})
            continue
        accepted.append(candidate)

    accepted.sort(
        key=lambda row: (
            row["date"],
            -float(row["fundamental_growth_rs_score_v1"]),
            -float(row["rs_proxy_score_v1"]),
            -int(row["fundamental_growth_points_v1"]),
            -float(row["avg_dollar_volume_20"]),
            row["ticker"],
        )
    )
    for rank, candidate in enumerate(accepted, start=1):
        candidate["fundamental_growth_rs_candidate_rank_on_signal_date"] = rank
        candidate["max_paper_trades_per_day"] = int(cfg["daily_entry_slots"])
    return accepted, rejected


def build_fundamental_growth_rs_replacement_value_report(
    *,
    candidates: list[dict[str, Any]],
    pending_entries: list[dict[str, Any]],
    open_positions: list[dict[str, Any]],
    closed_positions: list[dict[str, Any]],
    skipped_entries: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = _config(config)
    closed = [row for row in closed_positions or [] if isinstance(row, dict)]
    open_rows = [row for row in open_positions or [] if isinstance(row, dict)]
    pending = [row for row in pending_entries or [] if isinstance(row, dict)]
    skipped = [row for row in skipped_entries or [] if isinstance(row, dict)]
    positive_closed = [row for row in closed if _money(row.get("pnl")) > 0.0]
    positive_pnl = round(sum(_money(row.get("pnl")) for row in positive_closed), 2)
    by_ticker: dict[str, dict[str, Any]] = {}
    for bucket, rows in (
        ("candidate", candidates or []),
        ("pending", pending),
        ("open", open_rows),
        ("closed", closed),
        ("skipped", skipped),
    ):
        for row in rows:
            ticker = str(row.get("ticker") or "").upper()
            if not ticker and isinstance(row.get("candidate"), dict):
                ticker = str(row["candidate"].get("ticker") or "").upper()
            if not ticker:
                continue
            rec = by_ticker.setdefault(
                ticker,
                {
                    "candidate_count": 0,
                    "pending_count": 0,
                    "open_count": 0,
                    "closed_count": 0,
                    "skipped_count": 0,
                    "closed_pnl": 0.0,
                    "positive_closed_pnl": 0.0,
                },
            )
            rec[f"{bucket}_count"] += 1
            if bucket == "closed":
                pnl = _money(row.get("pnl"))
                rec["closed_pnl"] = round(float(rec["closed_pnl"]) + pnl, 2)
                if pnl > 0:
                    rec["positive_closed_pnl"] = round(float(rec["positive_closed_pnl"]) + pnl, 2)
    for rec in by_ticker.values():
        rec["positive_pnl_share"] = (
            round(float(rec["positive_closed_pnl"]) / positive_pnl, 6)
            if positive_pnl > 0
            else None
        )
    return {
        "schema_version": 1,
        "rule_version": REPLACEMENT_VALUE_RULE_VERSION,
        "read_only": True,
        "forward_outcome_horizon_days": int(cfg["hold_days"]),
        "displaced_resource_default": "paper_cash_slot",
        "candidate_count": len(candidates or []),
        "pending_count": len(pending),
        "open_count": len(open_rows),
        "closed_count": len(closed),
        "skipped_count": len(skipped),
        "closed_pnl": round(sum(_money(row.get("pnl")) for row in closed), 2),
        "open_unrealized_pnl": round(sum(_money(row.get("unrealized_pnl")) for row in open_rows), 2),
        "positive_closed_pnl": positive_pnl,
        "single_ticker_positive_share": _single_ticker_positive_share(closed),
        "positive_pnl_hhi": _positive_pnl_hhi(closed),
        "by_ticker": dict(sorted(by_ticker.items())),
        "promotion_blockers": [
            blocker
            for blocker in (
                "needs_closed_forward_outcomes"
                if len(closed) < int(cfg["forward_gate_min_closed_trades"])
                else None,
                "needs_replacement_value_vs_core_or_cash",
            )
            if blocker
        ],
        "trade_enabled": False,
        "alters_orders": False,
    }


class CompanyfactsFundamentalIndex:
    def __init__(self, rows: list[dict[str, Any]], *, config: dict[str, Any]) -> None:
        self.config = config
        by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for raw in rows:
            ticker = str(raw.get("ticker") or "").upper()
            canonical = str(raw.get("canonical") or "")
            filed = str(raw.get("filed") or raw.get("asof_date") or "")[:10]
            value = _float_or_none(raw.get("value") if "value" in raw else raw.get("current_value"))
            if canonical not in {"eps_diluted", "eps_basic", "revenue", "operating_income"}:
                continue
            if not ticker or not filed or value is None:
                continue
            if not _is_quarterly_fact(raw, config):
                continue
            row = {
                **raw,
                "ticker": ticker,
                "canonical": canonical,
                "filed": filed,
                "value": value,
                "fy_int": _int_or_none(raw.get("fy") if "fy" in raw else raw.get("current_fy")),
                "fp_norm": str(raw.get("fp") if "fp" in raw else raw.get("current_fp") or "").upper(),
                "end": raw.get("end") if raw.get("end") else raw.get("current_period_end"),
                "form": raw.get("form") if raw.get("form") else raw.get("current_form"),
            }
            by_key[(ticker, canonical)].append(row)
        for bucket in by_key.values():
            bucket.sort(key=_fact_sort_key)
        self.by_key = by_key

    def current_fact(self, ticker: str, canonical: str, asof_date: str) -> dict[str, Any]:
        rows = [
            row
            for row in self.by_key.get((ticker.upper(), canonical), [])
            if str(row.get("filed") or "")[:10] <= asof_date
        ]
        if not rows:
            return {"canonical": canonical, "available": False, "status": f"missing_{canonical}_quarter_fact"}
        current = rows[-1]
        return {
            "canonical": canonical,
            "available": True,
            "status": "ok",
            "current_value": _round(current.get("value"), 6),
            "current_filed": current.get("filed"),
            "current_period_end": current.get("end"),
            "current_form": current.get("form"),
            "current_fp": current.get("fp_norm"),
            "current_fy": current.get("fy_int"),
            "known_at": "SEC Companyfacts filed date <= signal_date",
        }

    def growth(self, ticker: str, canonical: str, asof_date: str) -> dict[str, Any]:
        rows = [
            row
            for row in self.by_key.get((ticker.upper(), canonical), [])
            if str(row.get("filed") or "")[:10] <= asof_date
        ]
        if not rows:
            return {"canonical": canonical, "available": False, "status": "missing_current_quarter_fact"}
        current = rows[-1]
        fy = current.get("fy_int")
        fp = current.get("fp_norm")
        if fy is None or not fp:
            return {
                "canonical": canonical,
                "available": False,
                "status": "missing_fiscal_period_key",
                "current_filed": current.get("filed"),
                "current_period_end": current.get("end"),
            }
        priors = [
            row
            for row in self.by_key.get((ticker.upper(), canonical), [])
            if row.get("fy_int") == fy - 1
            and row.get("fp_norm") == fp
            and str(row.get("filed") or "")[:10] <= asof_date
        ]
        if not priors:
            return {
                "canonical": canonical,
                "available": False,
                "status": "missing_prior_year_same_quarter_fact",
                "current_filed": current.get("filed"),
                "current_period_end": current.get("end"),
                "current_value": _round(current.get("value"), 6),
                "current_fp": fp,
                "current_fy": fy,
            }
        prior = sorted(priors, key=_fact_sort_key)[-1]
        current_value = _float_or_none(current.get("value"))
        prior_value = _float_or_none(prior.get("value"))
        if current_value is None or prior_value is None:
            status = "missing_current_or_prior_value"
            growth = None
        elif prior_value <= 0:
            status = "non_positive_prior_value"
            growth = None
        else:
            status = "ok"
            growth = current_value / prior_value - 1.0
        return {
            "canonical": canonical,
            "available": growth is not None,
            "status": status,
            "yoy_growth": _round(growth, 6),
            "current_value": _round(current_value, 6),
            "current_filed": current.get("filed"),
            "current_period_end": current.get("end"),
            "current_form": current.get("form"),
            "current_fp": fp,
            "current_fy": fy,
            "prior_value": _round(prior_value, 6),
            "prior_filed": prior.get("filed"),
            "prior_period_end": prior.get("end"),
            "known_at": "SEC Companyfacts filed date <= signal_date",
        }

    def fundamental_context(self, ticker: str, signal_date: str) -> dict[str, Any]:
        diluted = self.growth(ticker, "eps_diluted", signal_date)
        basic = self.growth(ticker, "eps_basic", signal_date)
        eps = diluted if diluted.get("available") else basic
        revenue = self.growth(ticker, "revenue", signal_date)
        eps_growth = _float_or_none(eps.get("yoy_growth"))
        revenue_growth = _float_or_none(revenue.get("yoy_growth"))
        eps_pass = (
            eps_growth is not None
            and eps_growth >= float(self.config["eps_growth_threshold"])
        )
        revenue_pass = (
            revenue_growth is not None
            and revenue_growth >= float(self.config["revenue_growth_threshold"])
        )
        points = int(eps_pass) + int(revenue_pass)
        return {
            "fundamental_growth_rule_version": SOURCE_RULE_VERSION,
            "fundamental_growth_known_at": "SEC Companyfacts filed date <= signal_date",
            "fundamental_growth_trade_enabled": False,
            "fundamental_growth_alters_orders": False,
            "eps_growth_source": eps.get("canonical"),
            "eps_growth_status": eps.get("status"),
            "eps_yoy_growth": _round(eps_growth, 6),
            "eps_growth_pass": eps_pass,
            "eps_current_filed": eps.get("current_filed"),
            "eps_current_period_end": eps.get("current_period_end"),
            "eps_prior_filed": eps.get("prior_filed"),
            "revenue_growth_status": revenue.get("status"),
            "revenue_yoy_growth": _round(revenue_growth, 6),
            "revenue_growth_pass": revenue_pass,
            "revenue_current_filed": revenue.get("current_filed"),
            "revenue_current_period_end": revenue.get("current_period_end"),
            "revenue_prior_filed": revenue.get("prior_filed"),
            "fundamental_growth_pair_available": (
                eps_growth is not None and revenue_growth is not None
            ),
            "fundamental_growth_points_v1": points,
            "fundamental_growth_pass_v1": points >= int(self.config["min_fundamental_points"]),
        }

    def operating_quality(self, ticker: str, asof_date: str) -> dict[str, Any]:
        operating_income = self.current_fact(ticker, "operating_income", asof_date)
        revenue = self.current_fact(ticker, "revenue", asof_date)
        op_value = _float_or_none(operating_income.get("current_value"))
        rev_value = _float_or_none(revenue.get("current_value"))
        margin = op_value / rev_value if op_value is not None and rev_value and rev_value > 0 else None
        quality_pass = op_value is not None and op_value > 0.0
        return {
            "operating_profit_quality_rule_version": SOURCE_RULE_VERSION,
            "operating_profit_quality_known_at": "SEC Companyfacts filed date <= signal_date",
            "operating_profit_quality_trade_enabled": False,
            "operating_profit_quality_alters_orders": False,
            "operating_income_status": operating_income.get("status"),
            "operating_income_current_value": _round(op_value, 6),
            "operating_income_current_filed": operating_income.get("current_filed"),
            "operating_income_current_period_end": operating_income.get("current_period_end"),
            "operating_income_current_form": operating_income.get("current_form"),
            "operating_income_positive_pass_v1": quality_pass,
            "operating_quality_revenue_status": revenue.get("status"),
            "operating_quality_revenue_current_value": _round(rev_value, 6),
            "operating_margin_current": _round(margin, 6),
            "operating_profit_quality_pass_v1": quality_pass,
        }


def load_companyfacts_rows(
    *,
    max_filed: str,
    tickers: list[str],
    non_ohlcv_dir: Path | str = DEFAULT_NON_OHLCV_DIR,
) -> list[dict[str, Any]]:
    ticker_set = {ticker.upper() for ticker in tickers}
    rows: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for path in sorted(Path(non_ohlcv_dir).glob("sec_companyfacts_selected_*.jsonl")):
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                ticker = str(row.get("ticker") or "").upper()
                filed = str(row.get("filed") or "")[:10]
                if ticker not in ticker_set or not filed or filed > max_filed:
                    continue
                key = (
                    ticker,
                    row.get("canonical"),
                    row.get("concept"),
                    row.get("unit"),
                    row.get("value"),
                    row.get("start"),
                    row.get("end"),
                    filed,
                    row.get("form"),
                    row.get("accession_number"),
                    row.get("duration_days"),
                )
                if key in seen:
                    continue
                seen.add(key)
                rows.append(row)
    return rows


def _candidate_for_ticker(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    ticker: str,
    as_of: str,
    fundamentals: CompanyfactsFundamentalIndex,
    rs_by_ticker: dict[str, dict[str, Any]],
    governor: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any] | None:
    rows = rows_by_ticker.get(ticker) or []
    idx = _index_on_date(rows, as_of)
    spy_rows = rows_by_ticker.get("SPY") or []
    spy_idx = _index_on_date(spy_rows, as_of)
    ma_days = int(config["trend_ma_days"])
    volume_days = int(config["volume_lookback_days"])
    if idx is None or spy_idx is None or idx < max(ma_days, volume_days, 60):
        return None
    close = _positive_float(rows[idx].get("close"))
    volume = _positive_float(rows[idx].get("volume"))
    if not close or not volume:
        return None
    fundamental = fundamentals.fundamental_context(ticker, as_of)
    points = int(fundamental.get("fundamental_growth_points_v1") or 0)
    if points < int(config["min_fundamental_points"]):
        return None
    operating = fundamentals.operating_quality(ticker, as_of)
    if operating.get("operating_profit_quality_pass_v1") is not True:
        return None
    rs = rs_by_ticker.get(ticker) or {}
    rs_score = _float_or_none(rs.get("rs_proxy_score_v1"))
    available_rs = int(rs.get("rs_proxy_available_window_count") or 0)
    if (
        rs_score is None
        or rs_score < float(config["min_rs_proxy_score"])
        or available_rs < int(config["min_available_rs_windows"])
    ):
        return None
    avg_volume = _prior_average(rows, idx, volume_days, "volume")
    avg_close = _prior_average(rows, idx, volume_days, "close")
    ma50 = _prior_average(rows, idx, ma_days, "close")
    if not avg_volume or not avg_close or not ma50:
        return None
    avg_dollar_volume = avg_volume * avg_close
    if avg_dollar_volume < float(config["min_avg_dollar_volume_20"]) or close <= ma50:
        return None
    candidate_ret = _close_return(rows, idx - 1, idx)
    spy_ret = _close_return(spy_rows, spy_idx - 1, spy_idx)
    ret20_excess = _float_or_none(rs.get("excess_ret_20d_vs_spy"))
    if candidate_ret is None or spy_ret is None or ret20_excess is None:
        return None
    signal_day_rs = candidate_ret - spy_ret
    if (
        ret20_excess < float(config["min_ret20_excess_spy"])
        or signal_day_rs < float(config["min_signal_day_rs_vs_spy"])
    ):
        return None
    eps_growth = _float_or_none(fundamental.get("eps_yoy_growth")) or 0.0
    revenue_growth = _float_or_none(fundamental.get("revenue_yoy_growth")) or 0.0
    volume_ratio = float(volume) / float(avg_volume) if avg_volume else None
    score = (
        rs_score
        + 0.20 * points
        + min(max(eps_growth, 0.0), 2.0) * 0.06
        + min(max(revenue_growth, 0.0), 1.5) * 0.08
        + max(ret20_excess, 0.0) * 1.5
        + max(signal_day_rs, 0.0) * 2.0
        + min(max((volume_ratio or 1.0) - 1.0, 0.0), 2.0) * 0.04
    )
    ticker_pnl = _money((governor.get("ticker_closed_pnl") or {}).get(ticker))
    ticker_profit_scalar = (
        float(config["ticker_profit_cap_scalar"])
        if ticker_pnl >= float(config["ticker_closed_profit_cap_usd"])
        else 1.0
    )
    global_drawdown = _money(governor.get("global_closed_drawdown"))
    global_drawdown_scalar = (
        float(config["global_drawdown_scalar"])
        if global_drawdown >= float(config["global_closed_drawdown_trigger_usd"])
        else 1.0
    )
    low_volume_pass = volume_ratio is not None and volume_ratio <= float(config["low_volume_ratio_20_max"])
    low_volume_scalar = float(config["low_volume_notional_scalar"]) if low_volume_pass else 1.0
    notional_scalar = ticker_profit_scalar * global_drawdown_scalar * low_volume_scalar
    intended_notional = float(config["paper_notional_usd"]) * notional_scalar
    return {
        "date": as_of,
        "signal_date": as_of,
        "ticker": ticker,
        "sector": SECTOR_MAP.get(ticker, "Unknown"),
        "strategy": "fundamental_growth_rs_candidate_pool",
        "close": _round(close, 4),
        "avg_dollar_volume_20": _round(avg_dollar_volume, 2),
        "volume_ratio_20": _round(volume_ratio, 6),
        "pct_above_50d_ma": _round((close / ma50) - 1.0, 6),
        "candidate_day_return": _round(candidate_ret, 6),
        "candidate_day_spy_return": _round(spy_ret, 6),
        "candidate_day_rs_vs_spy": _round(signal_day_rs, 6),
        "fundamental_growth_rs_score_v1": _round(score, 6),
        **fundamental,
        **rs,
        **operating,
        "source_rule_version": SOURCE_RULE_VERSION,
        "rule_version": RULE_VERSION,
        "governor_rule_version": GOVERNOR_RULE_VERSION,
        "low_volume_participation_rule_version": LOW_VOLUME_PARTICIPATION_RULE_VERSION,
        "source_universe": "current_production_universe_with_sec_companyfacts_and_ohlcv",
        "known_at": "after_signal_date_close_before_next_open_paper_entry",
        "trade_enabled": False,
        "alters_orders": False,
        "base_paper_notional_usd": float(config["paper_notional_usd"]),
        "ticker_closed_pnl_before_entry": _round(ticker_pnl, 2),
        "ticker_closed_profit_cap_usd": float(config["ticker_closed_profit_cap_usd"]),
        "ticker_profit_cap_scalar": ticker_profit_scalar,
        "global_closed_pnl_before_entry": _round(governor.get("global_closed_pnl"), 2),
        "global_closed_peak_pnl_before_entry": _round(governor.get("global_closed_peak_pnl"), 2),
        "global_closed_drawdown_before_entry": _round(global_drawdown, 2),
        "global_closed_drawdown_trigger_usd": float(config["global_closed_drawdown_trigger_usd"]),
        "global_drawdown_scalar": global_drawdown_scalar,
        "low_volume_participation_known_at": "daily OHLCV volume ratio with date <= signal_date",
        "low_volume_participation_trade_enabled": False,
        "low_volume_participation_alters_orders": False,
        "low_volume_ratio_20_max": float(config["low_volume_ratio_20_max"]),
        "low_volume_participation_pass_v1": low_volume_pass,
        "low_volume_notional_scalar": low_volume_scalar,
        "closed_ledger_notional_scalar": _round(notional_scalar, 6),
        "intended_notional": _round(intended_notional, 2),
        "same_ticker_core_overlap": False,
    }


def _rs_context_by_ticker(
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    *,
    tickers: list[str],
    date: str,
    config: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    spy_rows = rows_by_ticker.get("SPY") or []
    spy_idx = _index_on_date(spy_rows, date)
    if spy_idx is None:
        return {}
    windows = tuple(int(value) for value in config["rs_windows"])
    benchmark_returns = {
        window: _close_return(spy_rows, spy_idx - window, spy_idx)
        for window in windows
    }
    raw_by_window: dict[int, dict[str, float]] = {window: {} for window in windows}
    row_inputs: dict[str, dict[str, Any]] = {}
    for ticker in tickers:
        rows = rows_by_ticker.get(ticker) or []
        idx = _index_on_date(rows, date)
        if idx is None:
            continue
        row_inputs[ticker] = {"ticker": ticker, "asof_price_date": date}
        for window in windows:
            ret = _close_return(rows, idx - window, idx)
            spy_ret = benchmark_returns.get(window)
            if ret is None or spy_ret is None:
                continue
            excess = ret - spy_ret
            raw_by_window[window][ticker] = excess
            row_inputs[ticker][f"ret_{window}d"] = _round(ret, 6)
            row_inputs[ticker][f"spy_ret_{window}d"] = _round(spy_ret, 6)
            row_inputs[ticker][f"excess_ret_{window}d_vs_spy"] = _round(excess, 6)
    ranks_by_window = {
        window: _percentile_rank(values)
        for window, values in raw_by_window.items()
    }
    out: dict[str, dict[str, Any]] = {}
    for ticker, row in row_inputs.items():
        ranks = []
        for window in windows:
            rank = ranks_by_window[window].get(ticker)
            row[f"rs_proxy_rank_pct_{window}d"] = rank
            if rank is not None:
                ranks.append(rank)
        score = sum(ranks) / len(ranks) if ranks else None
        out[ticker] = {
            **row,
            "rs_proxy_rule_version": SOURCE_RULE_VERSION,
            "rs_proxy_known_at": "daily OHLCV rows with date <= signal_date",
            "rs_proxy_trade_enabled": False,
            "rs_proxy_alters_orders": False,
            "rs_proxy_available_window_count": len(ranks),
            "rs_proxy_score_v1": _round(score, 6),
            "rs_proxy_leader_threshold": float(config["min_rs_proxy_score"]),
            "rs_proxy_leader_pass_v1": score is not None and score >= float(config["min_rs_proxy_score"]),
        }
    return out


def _advance_open_positions(
    state: dict[str, Any],
    *,
    as_of: str,
    current_prices: dict[str, float],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    still_open: list[dict[str, Any]] = []
    closed_today: list[dict[str, Any]] = []
    for position in state.get("open_positions") or []:
        if not isinstance(position, dict):
            continue
        ticker = str(position.get("ticker") or "").upper()
        current_price = current_prices.get(ticker)
        observed_days = int(position.get("observed_trading_days") or 0) + 1
        position["observed_trading_days"] = observed_days
        if current_price:
            exit_mark = apply_slippage(current_price, SLIPPAGE_BPS_TARGET, "sell")
            position["last_price"] = current_price
            position["last_price_asof"] = as_of
            position["unrealized_pnl"] = _pnl(
                position.get("entry_price"),
                exit_mark,
                position.get("notional"),
                float(config["round_trip_cost_pct"]),
            )
        exit_reason = "max_hold_days" if observed_days >= int(config["hold_days"]) else None
        if exit_reason and current_price:
            exit_price = apply_slippage(current_price, SLIPPAGE_BPS_TARGET, "sell")
            closed = deepcopy(position)
            closed.update(
                {
                    "status": "closed",
                    "exit_date": as_of,
                    "exit_price": exit_price,
                    "exit_reason": exit_reason,
                    "pnl": _pnl(
                        position.get("entry_price"),
                        exit_price,
                        position.get("notional"),
                        float(config["round_trip_cost_pct"]),
                    ),
                    "return_pct_net": _return_pct(
                        position.get("entry_price"),
                        exit_price,
                        float(config["round_trip_cost_pct"]),
                    ),
                    "trade_enabled": False,
                }
            )
            closed_today.append(closed)
            state["closed_positions"].append(closed)
        else:
            still_open.append(position)
    state["open_positions"] = still_open
    return closed_today


def _fill_pending_entries(
    state: dict[str, Any],
    *,
    as_of: str,
    open_prices: dict[str, float],
    current_prices: dict[str, float],
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    still_pending: list[dict[str, Any]] = []
    filled: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for entry in sorted(state.get("pending_entries") or [], key=_pending_sort_key):
        if not isinstance(entry, dict):
            continue
        ticker = str(entry.get("ticker") or "").upper()
        if str(entry.get("created_asof") or "") >= as_of:
            still_pending.append(entry)
            continue
        open_price = open_prices.get(ticker)
        if open_price is None:
            skipped_entry = deepcopy(entry)
            skipped_entry.update(
                {
                    "status": "skipped_missing_next_open",
                    "skipped_asof": as_of,
                    "trade_enabled": False,
                }
            )
            skipped.append(skipped_entry)
            state["skipped_entries"].append(skipped_entry)
            continue
        entry_price = apply_entry_fill(open_price)
        notional = _entry_notional(entry, config)
        candidate = entry.get("candidate") or {}
        position = {
            "decision_id": entry.get("decision_id"),
            "sleeve": SLEEVE_NAME,
            "ticker": ticker,
            "strategy": "fundamental_growth_rs_candidate_pool",
            "entry_date": as_of,
            "entry_price": entry_price,
            "decision_close_price": candidate.get("close"),
            "notional": notional,
            "shares": round(notional / entry_price, 6) if entry_price else None,
            "observed_trading_days": 1,
            "hold_days": int(config["hold_days"]),
            "last_price": current_prices.get(ticker),
            "status": "open",
            "candidate": deepcopy(candidate),
            "trade_enabled": False,
        }
        if current_prices.get(ticker) and entry_price:
            position["unrealized_pnl"] = _pnl(
                entry_price,
                apply_slippage(current_prices[ticker], SLIPPAGE_BPS_TARGET, "sell"),
                position["notional"],
                float(config["round_trip_cost_pct"]),
            )
        filled.append(position)
        state["open_positions"].append(position)
    state["pending_entries"] = still_pending
    return filled, skipped


def _pending_entry_from_candidate(
    candidate: dict[str, Any],
    *,
    as_of: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    ticker = str(candidate.get("ticker") or "").upper()
    notional = _positive_float(candidate.get("intended_notional"))
    if notional is None:
        notional = float(config["paper_notional_usd"])
    return {
        "decision_id": f"{SLEEVE_NAME}:{RULE_VERSION}:{as_of}:{ticker}",
        "sleeve": SLEEVE_NAME,
        "ticker": ticker,
        "created_asof": as_of,
        "status": "pending_next_open",
        "notional": notional,
        "candidate": deepcopy(candidate),
        "trade_enabled": False,
        "alters_orders": False,
    }


def _closed_ledger_governor_state(
    closed_positions: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    total = 0.0
    peak = 0.0
    ticker_pnl: defaultdict[str, float] = defaultdict(float)
    for row in sorted(closed_positions or [], key=lambda item: str(item.get("exit_date") or "")):
        pnl = _money(row.get("pnl"))
        total += pnl
        peak = max(peak, total)
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            ticker_pnl[ticker] += pnl
    drawdown = peak - total
    capped = {
        ticker: round(pnl, 2)
        for ticker, pnl in ticker_pnl.items()
        if pnl >= float(config["ticker_closed_profit_cap_usd"])
    }
    return {
        "rule_version": GOVERNOR_RULE_VERSION,
        "read_only": True,
        "trade_enabled": False,
        "alters_orders": False,
        "closed_trade_count": len(closed_positions or []),
        "global_closed_pnl": round(total, 2),
        "global_closed_peak_pnl": round(peak, 2),
        "global_closed_drawdown": round(drawdown, 2),
        "global_closed_drawdown_trigger_usd": float(config["global_closed_drawdown_trigger_usd"]),
        "global_drawdown_active": drawdown >= float(config["global_closed_drawdown_trigger_usd"]),
        "global_drawdown_scalar": (
            float(config["global_drawdown_scalar"])
            if drawdown >= float(config["global_closed_drawdown_trigger_usd"])
            else 1.0
        ),
        "ticker_closed_profit_cap_usd": float(config["ticker_closed_profit_cap_usd"]),
        "capped_tickers": sorted(capped),
        "ticker_closed_pnl": dict(sorted((ticker, round(pnl, 2)) for ticker, pnl in ticker_pnl.items())),
    }


def _forward_paper_gate(closed_positions: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    realized = round(sum(_money(row.get("pnl")) for row in closed_positions), 2)
    wins = sum(1 for row in closed_positions if _money(row.get("pnl")) > 0)
    win_rate = round(wins / len(closed_positions), 4) if closed_positions else None
    single_share = _single_ticker_positive_share(closed_positions)
    hhi = _positive_pnl_hhi(closed_positions)
    checks = {
        "min_closed_trades": len(closed_positions) >= int(config["forward_gate_min_closed_trades"]),
        "positive_net_pnl": realized > 0 if config.get("forward_gate_positive_net_pnl", True) else True,
        "min_win_rate": win_rate is not None and win_rate >= float(config["forward_gate_min_win_rate"]),
        "max_single_ticker_positive_share": single_share is not None
        and single_share <= float(config["forward_gate_max_single_ticker_positive_share"]),
        "max_positive_hhi": hhi is not None and hhi <= float(config["forward_gate_max_positive_hhi"]),
    }
    reasons = [name for name, passed in checks.items() if not passed]
    return {
        "passed": not reasons,
        "status": "passed" if not reasons else "blocked",
        "reasons": reasons,
        "checks": checks,
        "metrics": {
            "closed_trades": len(closed_positions),
            "realized_pnl": realized,
            "win_rate": win_rate,
            "single_ticker_positive_share": single_share,
            "positive_pnl_hhi": hhi,
        },
        "trade_enabled_after_gate": False,
    }


def _normalise_candidate_universe(
    value: dict[str, Any] | list[str] | None,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    if isinstance(value, list):
        return {
            "status": "provided",
            "tickers": sorted({str(item).upper() for item in value if item}),
            "records": {},
        }
    if isinstance(value, dict):
        records = value.get("records") if isinstance(value.get("records"), dict) else {}
        tickers = {str(item).upper() for item in value.get("tickers") or [] if item}
        tickers.update(str(key).upper() for key in records)
        return {
            "status": value.get("status") or "provided",
            "path": value.get("path"),
            "tickers": sorted(tickers),
            "records": {
                str(key).upper(): dict(row or {})
                for key, row in records.items()
                if key
            },
        }
    return {
        "status": "default_rows_by_ticker",
        "tickers": sorted(ticker for ticker in rows_by_ticker if ticker not in EXCLUDED_TICKERS),
        "records": {},
    }


def _normalise_state(state: dict[str, Any]) -> None:
    state.setdefault("schema_version", STATE_SCHEMA_VERSION)
    state.setdefault("sleeve", SLEEVE_NAME)
    state.setdefault("pending_entries", [])
    state.setdefault("open_positions", [])
    state.setdefault("closed_positions", [])
    state.setdefault("skipped_entries", [])


def _config(config: dict[str, Any] | None) -> dict[str, Any]:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    cfg["enabled"] = False
    cfg["trade_enabled"] = False
    return cfg


def _normalise_ohlcv_rows(data: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if data is None:
        return rows
    if hasattr(data, "iterrows"):
        for idx, row in data.iterrows():
            date_value = row.get("Date", idx)
            rows.append(
                {
                    "date": _date10(date_value),
                    "open": _float_or_none(row.get("Open")),
                    "high": _float_or_none(row.get("High")),
                    "low": _float_or_none(row.get("Low")),
                    "close": _float_or_none(row.get("Close")),
                    "volume": _float_or_none(row.get("Volume")),
                }
            )
    elif isinstance(data, list):
        for raw in data:
            if not isinstance(raw, dict):
                continue
            rows.append(
                {
                    "date": _date10(raw.get("Date") or raw.get("date")),
                    "open": _float_or_none(raw.get("Open") or raw.get("open")),
                    "high": _float_or_none(raw.get("High") or raw.get("high")),
                    "low": _float_or_none(raw.get("Low") or raw.get("low")),
                    "close": _float_or_none(raw.get("Close") or raw.get("close")),
                    "volume": _float_or_none(raw.get("Volume") or raw.get("volume")),
                }
            )
    return sorted(
        [row for row in rows if row.get("date") and row.get("close") is not None],
        key=lambda row: row["date"],
    )


def _normalise_prices(prices: dict[str, Any] | None) -> dict[str, float]:
    out: dict[str, float] = {}
    for ticker, value in (prices or {}).items():
        parsed = _positive_float(value)
        if parsed is not None:
            out[str(ticker).upper()] = parsed
    return out


def _latest_index_on_or_before(rows: list[dict[str, Any]], as_of: str) -> int | None:
    matches = [
        idx
        for idx, row in enumerate(rows or [])
        if str(row.get("date") or "")[:10] <= str(as_of)[:10]
    ]
    return max(matches) if matches else None


def _index_on_date(rows: list[dict[str, Any]], as_of: str) -> int | None:
    target = _date10(as_of)
    for idx, row in enumerate(rows or []):
        if str(row.get("date") or "")[:10] == target:
            return idx
    return None


def _close_return(rows: list[dict[str, Any]], start_idx: int, end_idx: int) -> float | None:
    if start_idx < 0 or end_idx >= len(rows):
        return None
    start_close = _positive_float(rows[start_idx].get("close"))
    end_close = _positive_float(rows[end_idx].get("close"))
    if not start_close or end_close is None:
        return None
    return (end_close / start_close) - 1.0


def _prior_average(rows: list[dict[str, Any]], idx: int, days: int, key: str) -> float | None:
    if idx < days:
        return None
    values = [_positive_float(row.get(key)) for row in rows[idx - days:idx]]
    clean = [value for value in values if value is not None]
    if len(clean) < days:
        return None
    return sum(clean) / len(clean)


def _percentile_rank(values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(values.items(), key=lambda item: item[1])
    count = len(ordered)
    if count <= 1:
        return {ticker: 1.0 for ticker, _ in ordered}
    return {ticker: round(idx / (count - 1), 6) for idx, (ticker, _) in enumerate(ordered)}


def _is_quarterly_fact(row: dict[str, Any], config: dict[str, Any]) -> bool:
    duration = _float_or_none(row.get("duration_days"))
    if duration is None:
        start = str(row.get("start") or "")
        end = str(row.get("end") or row.get("current_period_end") or "")
        duration = 91.0 if start and end else None
    if duration is not None and (
        duration < float(config["quarterly_duration_min"])
        or duration > float(config["quarterly_duration_max"])
    ):
        return False
    fp = str(row.get("fp") if "fp" in row else row.get("current_fp") or "").upper()
    return fp in {"Q1", "Q2", "Q3", "Q4"} or duration is not None


def _fact_sort_key(row: dict[str, Any]) -> tuple[str, str, int, float]:
    duration = _float_or_none(row.get("duration_days"))
    duration_proximity = -abs((duration or 999.0) - 91.0)
    form = str(row.get("form") or "").upper()
    form_priority = 1 if form == "10-Q" else 0
    return (
        str(row.get("end") or ""),
        str(row.get("filed") or "")[:10],
        form_priority,
        duration_proximity,
    )


def _entry_notional(entry: dict[str, Any], config: dict[str, Any]) -> float:
    notional = _positive_float(entry.get("notional"))
    if notional is not None:
        return notional
    candidate = entry.get("candidate") or {}
    candidate_notional = _positive_float(candidate.get("intended_notional"))
    if candidate_notional is not None:
        return candidate_notional
    return float(config["paper_notional_usd"])


def _pnl(entry_price: Any, exit_price: Any, notional: Any, cost_pct: float) -> float:
    entry = _positive_float(entry_price)
    exit_ = _positive_float(exit_price)
    amount = _positive_float(notional)
    if not entry or exit_ is None or amount is None:
        return 0.0
    return round(amount * ((exit_ / entry) - 1.0 - cost_pct), 2)


def _return_pct(entry_price: Any, exit_price: Any, cost_pct: float) -> float:
    entry = _positive_float(entry_price)
    exit_ = _positive_float(exit_price)
    if not entry or exit_ is None:
        return 0.0
    return round((exit_ / entry) - 1.0 - cost_pct, 6)


def _single_ticker_positive_share(rows: list[dict[str, Any]]) -> float | None:
    by_ticker: dict[str, float] = {}
    for row in rows:
        pnl = _money(row.get("pnl"))
        if pnl <= 0:
            continue
        ticker = str(row.get("ticker") or "").upper()
        by_ticker[ticker] = round(by_ticker.get(ticker, 0.0) + pnl, 2)
    total = sum(by_ticker.values())
    if total <= 0:
        return None
    return round(max(by_ticker.values()) / total, 6)


def _positive_pnl_hhi(rows: list[dict[str, Any]]) -> float | None:
    by_ticker: dict[str, float] = {}
    for row in rows:
        pnl = _money(row.get("pnl"))
        if pnl <= 0:
            continue
        ticker = str(row.get("ticker") or "").upper()
        by_ticker[ticker] = round(by_ticker.get(ticker, 0.0) + pnl, 2)
    total = sum(by_ticker.values())
    if total <= 0:
        return None
    return round(sum((value / total) ** 2 for value in by_ticker.values()), 6)


def _pending_sort_key(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("created_asof") or ""), str(row.get("ticker") or ""))


def _production_impact() -> dict[str, Any]:
    return {
        "shared_policy_changed": True,
        "run_adapter_changed": True,
        "backtester_adapter_changed": False,
        "parity_test_added": True,
        "replay_only": False,
        "default_off_paper_only": True,
        "production_signal_path_changed": False,
        "production_orders_changed": False,
        "production_watchlist_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "trade_enabled": False,
        "scope": "default_off_fundamental_growth_rs_paper_attribution",
    }


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
    parsed = _float_or_none(value)
    if parsed is None:
        return None
    return round(parsed, digits)


def _money(value: Any) -> float:
    parsed = _float_or_none(value)
    return parsed if parsed is not None else 0.0


def _positive_float(value: Any) -> float | None:
    parsed = _float_or_none(value)
    if parsed is None or parsed <= 0:
        return None
    return parsed


def _float_or_none(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _date10(value: Any) -> str:
    if value is None:
        return ""
    return str(value)[:10]
