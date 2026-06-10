"""Default-off FINRA short-pressure IWM-confirmed paper sleeve.

This shared helper promotes the accepted exp-20260530-007 replay lead into a
production-visible forward observation boundary. It emits paper candidates and
ledger state only; it never emits live orders and never changes core signal
generation, ranking, sizing, exits, heat, LLM, or news behavior.
"""

from __future__ import annotations

import csv
import io
import json
import math
import sys
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

_QUANT_DIR = Path(__file__).resolve().parent
if str(_QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(_QUANT_DIR))

try:
    from constants import ROUND_TRIP_COST_PCT
    from data_paths import data_artifact_path
    from fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage
    from volume_breadth_breakout_paper_sleeve import (
        _close_location_value,
        _close_return,
        _date10,
        _float_or_none,
        _index_on_date,
        _money,
        _normalise_ohlcv_rows,
        _pnl,
        _prior_average,
        _prior_high,
        _return_pct,
        _round,
        _safe,
        _single_ticker_positive_share,
        _top5_positive_share,
    )
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant.constants import ROUND_TRIP_COST_PCT
    from quant.data_paths import data_artifact_path
    from quant.fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage
    from quant.volume_breadth_breakout_paper_sleeve import (
        _close_location_value,
        _close_return,
        _date10,
        _float_or_none,
        _index_on_date,
        _money,
        _normalise_ohlcv_rows,
        _pnl,
        _prior_average,
        _prior_high,
        _return_pct,
        _round,
        _safe,
        _single_ticker_positive_share,
        _top5_positive_share,
    )


SLEEVE_NAME = "FINRA_IWM_CONFIRMED_PAPER"
RULE_VERSION = "finra_iwm_borrow_pressure_shared_v1"
SOURCE_RULE_VERSION = "finra_days_to_cover_positive_short_change_borrow_pressure_source_v1"
MARKET_CONFIRMATION_RULE_VERSION = "iwm_spy_20d_risk_appetite_v1"
COOLDOWN_RULE_VERSION = "finra_iwm_same_ticker_signal_cooldown_v1"
REPLACEMENT_VALUE_RULE_VERSION = "finra_iwm_forward_replacement_value_v1"
COST_LIQUIDITY_SUPPORT_RULE_VERSION = "finra_iwm_cost_liquidity_support_v1"
BORROW_PRESSURE_ADMISSION_RULE_VERSION = (
    "finra_days_to_cover_positive_short_change_borrow_pressure_source_v1"
)
STATE_SCHEMA_VERSION = 1

FINRA_CSV_URL = "https://cdn.finra.org/equity/otcmarket/biweekly/shrt{yyyymmdd}.csv"

DEFAULT_FINRA_ROWS_PATH = data_artifact_path("finra_short_interest_rows")
DEFAULT_FINRA_FILES_PATH = data_artifact_path("finra_short_interest_files")
DEFAULT_STATE_PATH = data_artifact_path("finra_iwm_paper_state")
DEFAULT_SNAPSHOT_LOG_PATH = data_artifact_path("finra_iwm_paper_snapshots")

US_MARKET_HOLIDAYS = {
    date(2025, 1, 1),
    date(2025, 1, 20),
    date(2025, 2, 17),
    date(2025, 4, 18),
    date(2025, 5, 26),
    date(2025, 6, 19),
    date(2025, 7, 4),
    date(2025, 9, 1),
    date(2025, 11, 27),
    date(2025, 12, 25),
    date(2026, 1, 1),
    date(2026, 1, 19),
    date(2026, 2, 16),
    date(2026, 4, 3),
    date(2026, 5, 25),
    date(2026, 6, 19),
    date(2026, 7, 3),
    date(2026, 9, 7),
    date(2026, 11, 26),
    date(2026, 12, 25),
    # 2027 full-day closures per the NYSE Group official holiday calendar.
    # Weekend observances: Juneteenth (Sat 6/19 -> Fri 6/18), Independence Day
    # (Sun 7/4 -> Mon 7/5), Christmas (Sat 12/25 -> Fri 12/24).
    date(2027, 1, 1),
    date(2027, 1, 18),
    date(2027, 2, 15),
    date(2027, 3, 26),
    date(2027, 5, 31),
    date(2027, 6, 18),
    date(2027, 7, 5),
    date(2027, 9, 6),
    date(2027, 11, 25),
    date(2027, 12, 24),
}

# Auto-extend with the rule-generated NYSE calendar through next year so
# business-day math never silently goes stale. The pinned set above stays
# authoritative for verified years (tests assert generator == pins for
# 2025-2027), so replay over frozen windows is unaffected.
try:
    try:
        from market_calendar import nyse_holidays_through as _nyse_holidays_through
    except ImportError:  # pragma: no cover - package-style imports in tests
        from quant.market_calendar import nyse_holidays_through as _nyse_holidays_through
    US_MARKET_HOLIDAYS = frozenset(
        US_MARKET_HOLIDAYS | _nyse_holidays_through(date.today().year + 1)
    )
except Exception:  # pragma: no cover - generator failure falls back to pins
    US_MARKET_HOLIDAYS = frozenset(US_MARKET_HOLIDAYS)

PUBLICATION_OVERRIDES = {
    date(2025, 11, 14): date(2025, 11, 25),
    date(2025, 11, 28): date(2025, 12, 9),
    date(2025, 12, 15): date(2025, 12, 24),
    date(2025, 12, 31): date(2026, 1, 12),
    date(2026, 1, 15): date(2026, 1, 27),
    date(2026, 1, 30): date(2026, 2, 10),
    date(2026, 2, 13): date(2026, 2, 25),
    date(2026, 2, 27): date(2026, 3, 10),
    date(2026, 3, 13): date(2026, 3, 24),
    date(2026, 3, 31): date(2026, 4, 10),
    date(2026, 4, 15): date(2026, 4, 24),
    date(2026, 4, 30): date(2026, 5, 11),
}

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
    "breakout_lookback_days": 20,
    "moving_average_days": 50,
    "relative_strength_days": 20,
    "volume_ratio_days": 20,
    "min_close": 5.0,
    "min_dollar_volume": 30_000_000.0,
    "min_volume_ratio_20d": 1.10,
    "min_signal_close_location": 0.60,
    "min_rs20_vs_spy": 0.0,
    "min_short_pressure_score": 0.70,
    "borrow_pressure_admission_enabled": True,
    "min_finra_days_to_cover": 3.0,
    "min_finra_short_interest_change_pct": 0.0,
    "market_confirmation_days": 20,
    "min_iwm_minus_spy_ret20": 0.003,
    "same_ticker_cooldown_calendar_days": 7,
    "cost_liquidity_support_enabled": True,
    "cost_liquidity_min_dollar_volume": 200_000_000.0,
    "cost_liquidity_max_signal_day_range_pct": 0.10,
    "cost_liquidity_notional_scalar": 1.05,
    "daily_entry_slots": 1,
    "max_active_positions": 5,
    "hold_days": 10,
    "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
    "fetch_lookback_days": 150,
    "allow_network_fetch": True,
    "forward_gate_min_closed_trades": 20,
    "forward_gate_positive_net_pnl": True,
    "forward_gate_min_win_rate": 0.50,
    "forward_gate_max_single_ticker_positive_share": 0.40,
    "forward_gate_max_top5_positive_share": 0.70,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def empty_finra_iwm_paper_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "updated_at": None,
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "skipped_entries": [],
    }


def load_finra_iwm_paper_state(path: Path | str = DEFAULT_STATE_PATH) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_finra_iwm_paper_state()
    with state_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    state = empty_finra_iwm_paper_state()
    if isinstance(payload, dict):
        state.update(payload)
    _normalise_state(state)
    return state


def save_finra_iwm_paper_state(
    state: dict[str, Any],
    path: Path | str = DEFAULT_STATE_PATH,
) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now_iso()
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(_safe(state), handle, indent=2, sort_keys=True)
        handle.write("\n")


def append_finra_iwm_paper_snapshot(
    snapshot: dict[str, Any],
    path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_safe(snapshot), sort_keys=True) + "\n")


def load_finra_short_interest_rows(
    path: Path | str = DEFAULT_FINRA_ROWS_PATH,
) -> list[dict[str, Any]]:
    rows_path = Path(path)
    if not rows_path.exists():
        return []
    with rows_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict):
        payload = payload.get("rows") or []
    return _normalise_finra_rows(payload if isinstance(payload, list) else [])


def save_finra_short_interest_archive(
    *,
    rows: list[dict[str, Any]],
    files: list[dict[str, Any]],
    rows_path: Path | str = DEFAULT_FINRA_ROWS_PATH,
    files_path: Path | str = DEFAULT_FINRA_FILES_PATH,
) -> None:
    rows_out = Path(rows_path)
    files_out = Path(files_path)
    rows_out.parent.mkdir(parents=True, exist_ok=True)
    files_out.parent.mkdir(parents=True, exist_ok=True)
    with rows_out.open("w", encoding="utf-8") as handle:
        json.dump({"rows": _safe(rows), "updated_at": utc_now_iso()}, handle, indent=2, sort_keys=True)
        handle.write("\n")
    with files_out.open("w", encoding="utf-8") as handle:
        json.dump({"files": _safe(files), "updated_at": utc_now_iso()}, handle, indent=2, sort_keys=True)
        handle.write("\n")


def fetch_finra_short_interest_rows(
    *,
    tickers: set[str],
    as_of: str,
    lookback_days: int = 150,
    cache_dir: Path | str | None = None,
    timeout: int = 20,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    as_of_day = _parse_day(as_of)
    if as_of_day is None:
        return [], [{"error": "invalid_as_of_date", "as_of": as_of}]
    start = as_of_day - timedelta(days=max(45, int(lookback_days)))
    settlements = settlement_dates(start, as_of_day)
    cache_root = Path(cache_dir) if cache_dir else DEFAULT_FINRA_ROWS_PATH.parent / "source_cache"
    cache_root.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "ginger-finra-iwm-paper-sleeve/1.0 "
                "default-off-forward-observation"
            )
        }
    )

    rows: list[dict[str, Any]] = []
    files: list[dict[str, Any]] = []
    wanted = {str(ticker).upper() for ticker in tickers if ticker}
    for settlement in settlements:
        yyyymmdd = settlement.strftime("%Y%m%d")
        url = FINRA_CSV_URL.format(yyyymmdd=yyyymmdd)
        cache_path = cache_root / f"shrt{yyyymmdd}.csv"
        status_code: int | str | None = None
        source = "cache"
        try:
            if cache_path.exists():
                text = cache_path.read_text(encoding="utf-8-sig")
                status_code = "cached"
            else:
                source = "network"
                response = session.get(url, timeout=timeout)
                status_code = response.status_code
                if response.status_code != 200:
                    files.append(
                        {
                            "settlement_date": settlement.isoformat(),
                            "url": url,
                            "status_code": response.status_code,
                            "matched_rows": 0,
                            "source": source,
                        }
                    )
                    continue
                text = response.content.decode("utf-8-sig")
                cache_path.write_text(text, encoding="utf-8")
        except Exception as exc:  # pragma: no cover - network can vary.
            files.append(
                {
                    "settlement_date": settlement.isoformat(),
                    "url": url,
                    "status_code": status_code,
                    "error": str(exc),
                    "matched_rows": 0,
                    "source": source,
                }
            )
            continue

        publication, pub_method = publication_date_for(settlement)
        matched = 0
        reader = csv.DictReader(io.StringIO(text), delimiter="|")
        for raw in reader:
            ticker = str(raw.get("symbolCode") or "").upper().strip()
            if ticker not in wanted:
                continue
            matched += 1
            rows.append(
                {
                    "ticker": ticker,
                    "settlement_date": settlement.isoformat(),
                    "publication_date": publication.isoformat(),
                    "usable_trade_date": publication.isoformat(),
                    "publication_date_method": pub_method,
                    "pit_safe": True,
                    "short_interest": _to_int(raw.get("currentShortPositionQuantity")),
                    "previous_short_interest": _to_int(raw.get("previousShortPositionQuantity")),
                    "short_interest_change": _to_int(raw.get("changePreviousNumber")),
                    "short_interest_change_pct": _to_float(raw.get("changePercent")),
                    "days_to_cover": _to_float(raw.get("daysToCoverQuantity")),
                    "average_daily_volume": _to_int(raw.get("averageDailyVolumeQuantity")),
                    "issuer_exchange_code": raw.get("issuerServicesGroupExchangeCode"),
                    "market_class_code": raw.get("marketClassCode"),
                    "issue_name": raw.get("issueName"),
                    "source_url": url,
                }
            )
        files.append(
            {
                "settlement_date": settlement.isoformat(),
                "publication_date": publication.isoformat(),
                "url": url,
                "status_code": status_code,
                "matched_rows": matched,
                "source": source,
                "cache_path": str(cache_path),
            }
        )
    return _normalise_finra_rows(rows), files


def empty_finra_iwm_paper_sleeve_snapshot(as_of: str, reason: str) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
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
        "data_source": {"status": reason, "row_count": 0},
        "market_confirmation": {
            "rule_version": MARKET_CONFIRMATION_RULE_VERSION,
            "passed": False,
            "reason": reason,
            "trade_enabled": False,
            "alters_orders": False,
        },
        "same_ticker_cooldown": {
            "rule_version": COOLDOWN_RULE_VERSION,
            "calendar_days": DEFAULT_CONFIG["same_ticker_cooldown_calendar_days"],
            "rejected_count": 0,
            "trade_enabled": False,
            "alters_orders": False,
        },
        "borrow_pressure_admission": {
            "rule_version": BORROW_PRESSURE_ADMISSION_RULE_VERSION,
            "enabled": True,
            "min_finra_days_to_cover": DEFAULT_CONFIG["min_finra_days_to_cover"],
            "min_finra_short_interest_change_pct": DEFAULT_CONFIG[
                "min_finra_short_interest_change_pct"
            ],
            "admitted_candidate_count": 0,
            "rejected_count": 0,
            "trade_enabled": False,
            "alters_orders": False,
        },
        "candidate_universe": {"status": reason, "ticker_count": 0},
        "forward_paper_gate": {"passed": False, "status": "blocked", "reasons": [reason]},
        "production_impact": _production_impact(),
        "error": reason,
    }


def build_finra_iwm_paper_sleeve_snapshot(
    *,
    as_of: str,
    ohlcv_by_ticker: dict[str, Any] | None = None,
    candidate_universe: dict[str, Any] | list[str] | None = None,
    finra_rows: list[dict[str, Any]] | None = None,
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
        return empty_finra_iwm_paper_sleeve_snapshot(as_of_date, "missing_ohlcv")

    candidate_source = _normalise_candidate_universe(candidate_universe, rows_by_ticker)
    candidate_tickers = set(candidate_source.get("tickers") or [])
    candidate_tickers = {
        ticker
        for ticker in candidate_tickers
        if ticker in rows_by_ticker and ticker not in EXCLUDED_TICKERS
    }

    source_status = "provided"
    source_files: list[dict[str, Any]] = []
    if finra_rows is None:
        finra_rows = load_finra_short_interest_rows()
        source_status = "local_archive" if finra_rows else "missing_local_archive"
        if not finra_rows and cfg.get("allow_network_fetch", True):
            finra_rows, source_files = fetch_finra_short_interest_rows(
                tickers=candidate_tickers,
                as_of=as_of_date,
                lookback_days=int(cfg["fetch_lookback_days"]),
            )
            source_status = "network_fetch" if finra_rows else "network_fetch_empty"
            if finra_rows:
                save_finra_short_interest_archive(rows=finra_rows, files=source_files)

    finra_rows = _normalise_finra_rows(finra_rows or [])
    finra_by_ticker = _finra_rows_by_ticker(finra_rows)
    if not finra_rows:
        return empty_finra_iwm_paper_sleeve_snapshot(
            as_of_date,
            "missing_finra_short_interest_rows",
        )

    working_state = deepcopy(
        state if state is not None else load_finra_iwm_paper_state(state_path)
    )
    _normalise_state(working_state)

    current, opens = _exact_asof_price_maps(
        rows_by_ticker,
        as_of=as_of_date,
        current_prices=current_prices,
        open_prices=open_prices,
    )
    benchmark_ready = (
        _index_on_date(rows_by_ticker.get("SPY") or [], as_of_date) is not None
        and _index_on_date(rows_by_ticker.get("IWM") or [], as_of_date) is not None
    )

    closed_today: list[dict[str, Any]] = []
    filled_today: list[dict[str, Any]] = []
    skipped_today: list[dict[str, Any]] = []
    if benchmark_ready:
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

    candidates, reject_counts, market_context = _build_candidates(
        rows_by_ticker=rows_by_ticker,
        finra_by_ticker=finra_by_ticker,
        tickers=sorted(candidate_tickers),
        as_of=as_of_date,
        config=cfg,
    )
    filtered_candidates, cooldown_audit = _apply_same_ticker_cooldown(
        candidates,
        working_state,
        as_of=as_of_date,
        config=cfg,
    )
    filtered_candidates = filtered_candidates[: int(cfg["daily_entry_slots"])]

    open_positions = working_state.get("open_positions") or []
    existing_open_tickers = {str(row.get("ticker") or "").upper() for row in open_positions}
    new_pending: list[dict[str, Any]] = []
    room = max(0, int(cfg["max_active_positions"]) - len(open_positions))
    for candidate in filtered_candidates[:room]:
        ticker = str(candidate.get("ticker") or "").upper()
        if ticker in existing_open_tickers:
            reject_counts["already_open_in_finra_iwm_paper"] = reject_counts.get(
                "already_open_in_finra_iwm_paper",
                0,
            ) + 1
            continue
        entry = _pending_entry_from_candidate(candidate, as_of=as_of_date, config=cfg)
        working_state["pending_entries"].append(entry)
        new_pending.append(entry)

    closed = working_state.get("closed_positions") or []
    open_positions = working_state.get("open_positions") or []
    gate = _forward_paper_gate(closed, cfg)

    snapshot = {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "market_confirmation_rule_version": MARKET_CONFIRMATION_RULE_VERSION,
        "same_ticker_cooldown_rule_version": COOLDOWN_RULE_VERSION,
        "replacement_value_rule_version": REPLACEMENT_VALUE_RULE_VERSION,
        "asof_date": as_of_date,
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": bool(cfg["paper_enabled"]),
        "trade_enabled": False,
        "candidate_count": len(filtered_candidates),
        "raw_candidate_count": len(candidates),
        "rejected_candidate_count": sum(reject_counts.values()) + int(cooldown_audit["rejected_count"]),
        "new_pending_count": len(new_pending),
        "filled_count": len(filled_today),
        "closed_count_today": len(closed_today),
        "pending_count": len(working_state.get("pending_entries") or []),
        "open_position_count": len(open_positions),
        "closed_position_count": len(closed),
        "realized_pnl_to_date": round(sum(_money(row.get("pnl")) for row in closed), 2),
        "unrealized_pnl": round(sum(_money(row.get("unrealized_pnl")) for row in open_positions), 2),
        "data_source": {
            "status": source_status,
            "row_count": len(finra_rows),
            "covered_ticker_count": len(finra_by_ticker),
            "files": source_files[:20],
            "pit_policy": "FINRA row eligible only when publication_date <= signal_date",
        },
        "candidate_universe": {
            "status": candidate_source.get("status"),
            "ticker_count": len(candidate_tickers),
        },
        "market_confirmation": market_context,
        "same_ticker_cooldown": cooldown_audit,
        "borrow_pressure_admission": _borrow_pressure_admission_summary(
            candidates,
            reject_counts,
            cfg,
        ),
        "cost_liquidity_support": _cost_liquidity_support_summary(filtered_candidates, cfg),
        "candidate_reject_counts": dict(sorted(reject_counts.items())),
        "candidates": deepcopy(filtered_candidates),
        "raw_candidates_sample": deepcopy(candidates[:10]),
        "new_pending_entries": deepcopy(new_pending),
        "filled_entries": deepcopy(filled_today),
        "closed_positions_today": deepcopy(closed_today),
        "skipped_entries_today": deepcopy(skipped_today),
        "pending_entries": deepcopy(working_state["pending_entries"]),
        "open_positions": deepcopy(open_positions),
        "closed_positions_sample": deepcopy(closed[-20:]),
        "forward_paper_gate": gate,
        "production_impact": _production_impact(),
        "notes": (
            "Default-off paper only. FINRA publication-date rows, IWM/SPY "
            "confirmation, borrow-pressure admission, same-ticker cooldown, "
            "and cost-liquidity support are surfaced for forward replacement-"
            "value evidence; live/core orders remain unchanged."
        ),
    }

    if persist:
        save_finra_iwm_paper_state(working_state, state_path)
        append_finra_iwm_paper_snapshot(snapshot, snapshot_log_path)
    return _safe(snapshot)


def _build_candidates(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    finra_by_ticker: dict[str, list[dict[str, Any]]],
    tickers: list[str],
    as_of: str,
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, int], dict[str, Any]]:
    rejects: dict[str, int] = {}
    market = _market_confirmation(rows_by_ticker, as_of, config)
    if not market["passed"]:
        return [], {"market_confirmation_failed": len(tickers)}, market

    spy_rows = rows_by_ticker.get("SPY") or []
    spy_idx = _index_on_date(spy_rows, as_of)
    min_idx = max(
        int(config["breakout_lookback_days"]),
        int(config["moving_average_days"]),
        int(config["relative_strength_days"]),
    )
    short_scores = _same_day_short_scores(tickers, finra_by_ticker, as_of)
    candidates: list[dict[str, Any]] = []
    for ticker in tickers:
        rows = rows_by_ticker.get(ticker) or []
        idx = _index_on_date(rows, as_of)
        if idx is None or spy_idx is None or idx < min_idx or spy_idx < int(config["relative_strength_days"]):
            _inc(rejects, "insufficient_history")
            continue

        close = _value(rows[idx], "close")
        high = _value(rows[idx], "high")
        low = _value(rows[idx], "low")
        volume = _value(rows[idx], "volume")
        if close is None or high is None or low is None or volume is None or close < float(config["min_close"]):
            _inc(rejects, "missing_or_low_price_volume")
            continue
        dollar_volume = close * volume
        if dollar_volume < float(config["min_dollar_volume"]):
            _inc(rejects, "low_dollar_volume")
            continue

        prior_high = _prior_high(rows, idx, int(config["breakout_lookback_days"]))
        ma50 = _prior_average(rows, idx, int(config["moving_average_days"]), "close")
        if prior_high is None or ma50 is None:
            _inc(rejects, "missing_price_context")
            continue
        if close <= prior_high or close <= ma50:
            _inc(rejects, "not_price_breakout_or_above_ma50")
            continue

        avg_volume = _avg_volume(rows, idx, int(config["volume_ratio_days"]))
        if avg_volume is None or avg_volume <= 0:
            _inc(rejects, "missing_volume_context")
            continue
        volume_ratio_20d = volume / avg_volume
        if volume_ratio_20d < float(config["min_volume_ratio_20d"]):
            _inc(rejects, "volume_ratio_too_low")
            continue

        close_location = _close_location_value(close=close, high=high, low=low)
        if close_location is None or close_location < float(config["min_signal_close_location"]):
            _inc(rejects, "weak_signal_close_location")
            continue

        ret_days = int(config["relative_strength_days"])
        ret20 = _close_return(rows, idx - ret_days, idx)
        spy_ret20 = _close_return(spy_rows, spy_idx - ret_days, spy_idx)
        if ret20 is None or spy_ret20 is None:
            _inc(rejects, "missing_relative_strength")
            continue
        rs20_vs_spy = ret20 - spy_ret20
        if rs20_vs_spy <= float(config["min_rs20_vs_spy"]):
            _inc(rejects, "rs20_not_positive_vs_spy")
            continue

        short_score = short_scores.get(ticker)
        if short_score is None:
            _inc(rejects, "missing_published_finra_row")
            continue
        if short_score["finra_short_pressure_score"] < float(config["min_short_pressure_score"]):
            _inc(rejects, "short_pressure_score_too_low")
            continue

        finra_row = short_score["finra_row"]
        borrow_pressure = _borrow_pressure_admission_context(finra_row, config)
        if borrow_pressure["finra_borrow_pressure_pass_v1"] is not True:
            _inc(rejects, borrow_pressure["finra_borrow_pressure_status"])
            continue

        selection_score = (
            float(short_score["finra_short_pressure_score"])
            + min(rs20_vs_spy, 0.50)
            + min(volume_ratio_20d / 10.0, 0.25)
            + min(close_location / 10.0, 0.10)
        )
        base_notional = float(config["paper_notional_usd"])
        cost_liquidity = _cost_liquidity_support_context(
            close=close,
            high=high,
            low=low,
            dollar_volume=dollar_volume,
            base_notional=base_notional,
            config=config,
        )
        candidates.append(
            {
                "sleeve": SLEEVE_NAME,
                "ticker": ticker,
                "date": as_of,
                "strategy": "finra_borrow_pressure_candidate_pool",
                "rule_version": RULE_VERSION,
                "source_rule_version": SOURCE_RULE_VERSION,
                "market_confirmation_rule_version": MARKET_CONFIRMATION_RULE_VERSION,
                "same_ticker_cooldown_rule_version": COOLDOWN_RULE_VERSION,
                "borrow_pressure_admission_rule_version": BORROW_PRESSURE_ADMISSION_RULE_VERSION,
                "close": _round(close, 4),
                "volume": _round(volume, 2),
                "dollar_volume": _round(dollar_volume, 2),
                "ma50": _round(ma50, 4),
                "price_prior_high_20d": _round(prior_high, 4),
                "distance_above_price_high_20d": _round((close / prior_high) - 1.0, 6),
                "volume_ratio_20d": _round(volume_ratio_20d, 6),
                "signal_close_location": _round(close_location, 6),
                "ret20": _round(ret20, 6),
                "spy_ret20": _round(spy_ret20, 6),
                "rs20_vs_spy": _round(rs20_vs_spy, 6),
                "iwm_ret20": market.get("iwm_ret20"),
                "iwm_minus_spy_ret20": market.get("iwm_minus_spy_ret20"),
                "finra_settlement_date": finra_row.get("settlement_date"),
                "finra_publication_date": finra_row.get("publication_date"),
                "finra_publication_date_method": finra_row.get("publication_date_method"),
                "finra_days_to_cover": finra_row.get("days_to_cover"),
                "finra_short_interest": finra_row.get("short_interest"),
                "finra_previous_short_interest": finra_row.get("previous_short_interest"),
                "finra_short_interest_change": finra_row.get("short_interest_change"),
                "finra_short_interest_change_pct": finra_row.get("short_interest_change_pct"),
                "finra_average_daily_volume": finra_row.get("average_daily_volume"),
                "finra_short_crowding_score": short_score.get("short_crowding_score"),
                "finra_short_change_score": short_score.get("short_change_score"),
                "finra_short_pressure_score": short_score["finra_short_pressure_score"],
                "same_day_finra_covered_count": short_score["same_day_finra_covered_count"],
                "finra_source_url": finra_row.get("source_url"),
                "candidate_selection_score": _round(selection_score, 6),
                "known_at": "after_signal_date_close_with_latest_published_finra_before_next_open_paper_entry",
                "base_paper_notional_usd": base_notional,
                "intended_notional": cost_liquidity["finra_iwm_cost_liquidity_supported_notional_usd"],
                "trade_enabled": False,
                "alters_orders": False,
                **borrow_pressure,
                **cost_liquidity,
            }
        )

    candidates.sort(
        key=lambda row: (
            -float(row["candidate_selection_score"]),
            -float(row["finra_short_pressure_score"]),
            -float(row["rs20_vs_spy"]),
            -float(row["volume_ratio_20d"]),
            -float(row["dollar_volume"]),
            row["ticker"],
        )
    )
    return candidates, rejects, market


def _borrow_pressure_admission_context(
    finra_row: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    enabled = bool(config.get("borrow_pressure_admission_enabled", True))
    min_days_to_cover = float(config["min_finra_days_to_cover"])
    min_short_change = float(config["min_finra_short_interest_change_pct"])
    days_to_cover = _float_or_none(finra_row.get("days_to_cover"))
    short_change_pct = _float_or_none(finra_row.get("short_interest_change_pct"))
    if not enabled:
        status = "disabled"
        passed = True
    elif days_to_cover is None:
        status = "missing_finra_days_to_cover"
        passed = False
    elif short_change_pct is None:
        status = "missing_finra_short_interest_change_pct"
        passed = False
    elif days_to_cover < min_days_to_cover:
        status = "days_to_cover_below_threshold"
        passed = False
    elif short_change_pct <= min_short_change:
        status = "short_interest_change_not_positive"
        passed = False
    else:
        status = "passed"
        passed = True
    return {
        "finra_borrow_pressure_rule_version": BORROW_PRESSURE_ADMISSION_RULE_VERSION,
        "finra_borrow_pressure_known_at": (
            "after_signal_date_close_with_latest_published_finra_before_next_open_paper_entry"
        ),
        "finra_borrow_pressure_trade_enabled": False,
        "finra_borrow_pressure_alters_orders": False,
        "finra_borrow_pressure_enabled": enabled,
        "finra_borrow_pressure_status": status,
        "finra_borrow_pressure_pass_v1": passed,
        "min_finra_days_to_cover": min_days_to_cover,
        "min_finra_short_interest_change_pct": min_short_change,
    }


def _borrow_pressure_admission_summary(
    candidates: list[dict[str, Any]],
    reject_counts: dict[str, int],
    config: dict[str, Any],
) -> dict[str, Any]:
    reject_keys = (
        "missing_finra_days_to_cover",
        "missing_finra_short_interest_change_pct",
        "days_to_cover_below_threshold",
        "short_interest_change_not_positive",
    )
    rejects = {
        key: int(reject_counts.get(key, 0))
        for key in reject_keys
        if reject_counts.get(key, 0)
    }
    return {
        "rule_version": BORROW_PRESSURE_ADMISSION_RULE_VERSION,
        "enabled": bool(config.get("borrow_pressure_admission_enabled", True)),
        "min_finra_days_to_cover": float(config["min_finra_days_to_cover"]),
        "min_finra_short_interest_change_pct": float(
            config["min_finra_short_interest_change_pct"]
        ),
        "admitted_candidate_count": len(candidates),
        "rejected_count": sum(rejects.values()),
        "reject_counts": rejects,
        "trade_enabled": False,
        "alters_orders": False,
    }


def _cost_liquidity_support_context(
    *,
    close: float,
    high: float,
    low: float,
    dollar_volume: float,
    base_notional: float,
    config: dict[str, Any],
) -> dict[str, Any]:
    range_pct = max(0.0, (high - low) / close) if close > 0 else None
    support_enabled = bool(config.get("cost_liquidity_support_enabled", True))
    min_dollar_volume = float(config["cost_liquidity_min_dollar_volume"])
    max_range_pct = float(config["cost_liquidity_max_signal_day_range_pct"])
    support_scalar = float(config["cost_liquidity_notional_scalar"])
    passed = (
        support_enabled
        and range_pct is not None
        and dollar_volume >= min_dollar_volume
        and range_pct <= max_range_pct
    )
    if not support_enabled:
        status = "disabled"
    elif passed:
        status = "supported"
    elif dollar_volume < min_dollar_volume:
        status = "dollar_volume_below_threshold"
    else:
        status = "range_above_threshold"
    scalar = support_scalar if passed else 1.0
    return {
        "finra_iwm_cost_liquidity_rule_version": COST_LIQUIDITY_SUPPORT_RULE_VERSION,
        "finra_iwm_cost_liquidity_known_at": "signal-day OHLCV known after close before next-open paper entry",
        "finra_iwm_cost_liquidity_trade_enabled": False,
        "finra_iwm_cost_liquidity_alters_orders": False,
        "finra_iwm_cost_liquidity_status": status,
        "finra_iwm_cost_liquidity_pass_v1": passed,
        "finra_iwm_cost_liquidity_min_dollar_volume": min_dollar_volume,
        "finra_iwm_cost_liquidity_max_range_pct": max_range_pct,
        "finra_iwm_cost_liquidity_dollar_volume": _round(dollar_volume, 2),
        "finra_iwm_cost_liquidity_signal_day_range_pct": _round(range_pct, 6),
        "finra_iwm_cost_liquidity_support_scalar": scalar,
        "finra_iwm_cost_liquidity_base_notional_usd": _round(base_notional, 2),
        "finra_iwm_cost_liquidity_supported_notional_usd": _round(base_notional * scalar, 2),
    }


def _cost_liquidity_support_summary(
    candidates: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    supported = [
        row for row in candidates
        if row.get("finra_iwm_cost_liquidity_pass_v1") is True
    ]
    return {
        "rule_version": COST_LIQUIDITY_SUPPORT_RULE_VERSION,
        "enabled": bool(config.get("cost_liquidity_support_enabled", True)),
        "supported_candidate_count": len(supported),
        "candidate_count": len(candidates),
        "min_dollar_volume": float(config["cost_liquidity_min_dollar_volume"]),
        "max_signal_day_range_pct": float(config["cost_liquidity_max_signal_day_range_pct"]),
        "notional_scalar": float(config["cost_liquidity_notional_scalar"]),
        "trade_enabled": False,
        "alters_orders": False,
    }


def _market_confirmation(
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    as_of: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    days = int(config["market_confirmation_days"])
    iwm_rows = rows_by_ticker.get("IWM") or []
    spy_rows = rows_by_ticker.get("SPY") or []
    iwm_idx = _index_on_date(iwm_rows, as_of)
    spy_idx = _index_on_date(spy_rows, as_of)
    base = {
        "rule_version": MARKET_CONFIRMATION_RULE_VERSION,
        "market_confirmation_days": days,
        "min_iwm_minus_spy_ret20": float(config["min_iwm_minus_spy_ret20"]),
        "trade_enabled": False,
        "alters_orders": False,
    }
    if iwm_idx is None or spy_idx is None or iwm_idx < days or spy_idx < days:
        return {**base, "passed": False, "reason": "missing_iwm_or_spy_market_context"}
    iwm_ret20 = _close_return(iwm_rows, iwm_idx - days, iwm_idx)
    spy_ret20 = _close_return(spy_rows, spy_idx - days, spy_idx)
    if iwm_ret20 is None or spy_ret20 is None:
        return {**base, "passed": False, "reason": "missing_iwm_or_spy_ret20"}
    spread = iwm_ret20 - spy_ret20
    passed = spread >= float(config["min_iwm_minus_spy_ret20"])
    return {
        **base,
        "passed": passed,
        "reason": "iwm_spy_confirmation_passed" if passed else "iwm_not_leading_spy_enough",
        "iwm_ret20": _round(iwm_ret20, 6),
        "market_spy_ret20": _round(spy_ret20, 6),
        "iwm_minus_spy_ret20": _round(spread, 6),
    }


def _apply_same_ticker_cooldown(
    candidates: list[dict[str, Any]],
    state: dict[str, Any],
    *,
    as_of: str,
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cooldown_days = int(config["same_ticker_cooldown_calendar_days"])
    prior_by_ticker = _prior_admitted_dates_by_ticker(state)
    admitted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    as_of_day = _parse_day(as_of)
    for candidate in candidates:
        ticker = str(candidate.get("ticker") or "").upper()
        prior_dates = prior_by_ticker.get(ticker) or []
        last_day = max(prior_dates) if prior_dates else None
        days_since = (as_of_day - last_day).days if as_of_day and last_day else None
        if days_since is not None and 0 <= days_since <= cooldown_days:
            rejected.append(
                {
                    "ticker": ticker,
                    "date": as_of,
                    "prior_admitted_date": last_day.isoformat(),
                    "days_since_prior_admitted": days_since,
                    "candidate_selection_score": candidate.get("candidate_selection_score"),
                }
            )
            continue
        enriched = dict(candidate)
        enriched.update(
            {
                "same_ticker_cooldown_calendar_days": cooldown_days,
                "same_ticker_cooldown_known_at": "after_signal_date_close_using_prior_admitted_default_off_candidates",
                "same_ticker_cooldown_trade_enabled": False,
                "same_ticker_cooldown_alters_orders": False,
                "prior_same_ticker_admitted_date": last_day.isoformat() if last_day else None,
                "days_since_prior_same_ticker_admitted": days_since,
            }
        )
        admitted.append(enriched)
    return admitted, {
        "rule_version": COOLDOWN_RULE_VERSION,
        "calendar_days": cooldown_days,
        "candidate_count_before_same_ticker_cooldown": len(candidates),
        "candidate_count_after_same_ticker_cooldown": len(admitted),
        "rejected_count": len(rejected),
        "rejected_examples": rejected[:20],
        "trade_enabled": False,
        "alters_orders": False,
    }


def _prior_admitted_dates_by_ticker(state: dict[str, Any]) -> dict[str, list[date]]:
    out: dict[str, list[date]] = {}
    containers = (
        state.get("pending_entries") or [],
        state.get("open_positions") or [],
        state.get("closed_positions") or [],
    )
    for rows in containers:
        for row in rows:
            if not isinstance(row, dict):
                continue
            ticker = str(row.get("ticker") or "").upper()
            raw_day = (
                row.get("created_asof")
                or row.get("entry_date")
                or ((row.get("candidate") or {}).get("date") if isinstance(row.get("candidate"), dict) else None)
            )
            parsed = _parse_day(str(raw_day)[:10] if raw_day else None)
            if ticker and parsed:
                out.setdefault(ticker, []).append(parsed)
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
        if current_price is None:
            still_open.append(position)
            continue
        observed_days = int(position.get("observed_trading_days") or 0) + 1
        position["observed_trading_days"] = observed_days
        exit_mark = apply_slippage(current_price, SLIPPAGE_BPS_TARGET, "sell")
        position["last_price"] = current_price
        position["last_price_asof"] = as_of
        position["unrealized_pnl"] = _pnl(
            position.get("entry_price"),
            exit_mark,
            position.get("notional"),
            float(config["round_trip_cost_pct"]),
        )
        if observed_days >= int(config["hold_days"]):
            closed = deepcopy(position)
            closed.update(
                {
                    "status": "closed",
                    "exit_date": as_of,
                    "exit_price": exit_mark,
                    "exit_reason": "max_hold_days",
                    "pnl": _pnl(
                        position.get("entry_price"),
                        exit_mark,
                        position.get("notional"),
                        float(config["round_trip_cost_pct"]),
                    ),
                    "return_pct_net": _return_pct(
                        position.get("entry_price"),
                        exit_mark,
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
        notional = _positive_float(entry.get("notional")) or float(config["paper_notional_usd"])
        candidate = entry.get("candidate") or {}
        position = {
            "decision_id": entry.get("decision_id"),
            "sleeve": SLEEVE_NAME,
            "ticker": ticker,
            "strategy": "finra_iwm_same_ticker_cooldown_candidate_pool",
            "entry_date": as_of,
            "entry_price": entry_price,
            "decision_close_price": candidate.get("close"),
            "notional": notional,
            "shares": round(notional / entry_price, 6) if entry_price else None,
            "observed_trading_days": 0,
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


def _forward_paper_gate(
    closed_positions: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    realized = round(sum(_money(row.get("pnl")) for row in closed_positions), 2)
    wins = sum(1 for row in closed_positions if _money(row.get("pnl")) > 0)
    win_rate = round(wins / len(closed_positions), 4) if closed_positions else None
    single_share = _single_ticker_positive_share(closed_positions)
    top5_share = _top5_positive_share(closed_positions)
    checks = {
        "min_closed_trades": len(closed_positions) >= int(config["forward_gate_min_closed_trades"]),
        "positive_net_pnl": realized > 0 if config.get("forward_gate_positive_net_pnl", True) else True,
        "min_win_rate": win_rate is not None and win_rate >= float(config["forward_gate_min_win_rate"]),
        "max_single_ticker_positive_share": single_share is not None
        and single_share <= float(config["forward_gate_max_single_ticker_positive_share"]),
        "max_top5_positive_share": top5_share is not None
        and top5_share <= float(config["forward_gate_max_top5_positive_share"]),
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
            "top5_positive_share": top5_share,
        },
        "trade_enabled_after_gate": False,
    }


def _same_day_short_scores(
    tickers: list[str],
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    signal_date: str,
) -> dict[str, dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for ticker in tickers:
        row = _latest_finra_row(rows_by_ticker, ticker, signal_date)
        if row is None:
            continue
        records.append(
            {
                "ticker": ticker,
                "row": row,
                "days_to_cover": row.get("days_to_cover"),
                "short_interest_change_pct": row.get("short_interest_change_pct"),
            }
        )

    crowding_scores = _percentiles(
        [
            float(record["days_to_cover"])
            if isinstance(record.get("days_to_cover"), (int, float))
            else None
            for record in records
        ]
    )
    change_scores = _percentiles(
        [
            float(record["short_interest_change_pct"])
            if isinstance(record.get("short_interest_change_pct"), (int, float))
            else None
            for record in records
        ]
    )

    out: dict[str, dict[str, Any]] = {}
    for record, crowding, change in zip(records, crowding_scores, change_scores):
        crowding_for_score = 0.0 if crowding is None else crowding
        change_for_score = 0.0 if change is None else change
        score = round(0.70 * crowding_for_score + 0.30 * change_for_score, 6)
        out[record["ticker"]] = {
            "finra_row": record["row"],
            "short_crowding_score": crowding,
            "short_change_score": change,
            "finra_short_pressure_score": score,
            "same_day_finra_covered_count": len(records),
            "score_weights": {
                "days_to_cover_percentile": 0.70,
                "change_percentile": 0.30,
            },
        }
    return out


def _latest_finra_row(
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    ticker: str,
    signal_date: str,
) -> dict[str, Any] | None:
    rows = rows_by_ticker.get(ticker.upper()) or []
    eligible = [row for row in rows if str(row.get("publication_date") or "") <= signal_date]
    if not eligible:
        return None
    return eligible[-1]


def _percentiles(values: list[float | None]) -> list[float | None]:
    present = sorted(value for value in values if value is not None and math.isfinite(value))
    if not present:
        return [None for _ in values]
    if len(present) == 1:
        return [0.5 if value is not None else None for value in values]
    out: list[float | None] = []
    denom = len(present) - 1
    for value in values:
        if value is None or not math.isfinite(value):
            out.append(None)
            continue
        below_or_equal = sum(1 for other in present if other <= value)
        out.append(round((below_or_equal - 1) / denom, 6))
    return out


def _avg_volume(rows: list[dict[str, Any]], idx: int, days: int) -> float | None:
    if idx < days:
        return None
    values = [_value(row, "volume") for row in rows[idx - days:idx]]
    clean = [float(value) for value in values if isinstance(value, (int, float))]
    if len(clean) < days:
        return None
    return sum(clean) / len(clean)


def _normalise_finra_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or row.get("symbolCode") or "").upper().strip()
        publication = _date10(
            row.get("publication_date")
            or row.get("usable_trade_date")
            or row.get("publicationDate")
        )
        settlement = _date10(row.get("settlement_date") or row.get("settlementDate"))
        if not ticker or not publication:
            continue
        out.append(
            {
                **row,
                "ticker": ticker,
                "publication_date": publication,
                "usable_trade_date": row.get("usable_trade_date") or publication,
                "settlement_date": settlement,
                "short_interest": _to_int(row.get("short_interest")),
                "previous_short_interest": _to_int(row.get("previous_short_interest")),
                "short_interest_change": _to_int(row.get("short_interest_change")),
                "short_interest_change_pct": _to_float(row.get("short_interest_change_pct")),
                "days_to_cover": _to_float(row.get("days_to_cover")),
                "average_daily_volume": _to_int(row.get("average_daily_volume")),
            }
        )
    out.sort(key=lambda item: (item["ticker"], item["publication_date"], item.get("settlement_date") or ""))
    return out


def _finra_rows_by_ticker(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for row in _normalise_finra_rows(rows):
        out.setdefault(row["ticker"], []).append(row)
    for ticker_rows in out.values():
        ticker_rows.sort(key=lambda row: (row["publication_date"], row.get("settlement_date") or ""))
    return out


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


def _exact_asof_price_maps(
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    *,
    as_of: str,
    current_prices: dict[str, Any] | None,
    open_prices: dict[str, Any] | None,
) -> tuple[dict[str, float], dict[str, float]]:
    current: dict[str, float] = {}
    opens: dict[str, float] = {}
    for ticker, rows in rows_by_ticker.items():
        idx = _index_on_date(rows, as_of)
        if idx is None:
            continue
        row = rows[idx]
        close = _value(row, "close")
        open_price = _value(row, "open")
        override_current = _float_or_none((current_prices or {}).get(ticker))
        override_open = _float_or_none((open_prices or {}).get(ticker))
        if override_current is not None:
            current[ticker] = override_current
        elif close is not None:
            current[ticker] = close
        if override_open is not None:
            opens[ticker] = override_open
        elif open_price is not None:
            opens[ticker] = open_price
    return current, opens


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


def _production_impact() -> dict[str, Any]:
    return {
        "shared_policy_changed": True,
        "backtester_adapter_changed": False,
        "run_adapter_changed": True,
        "replay_only": False,
        "default_off_paper_only": True,
        "production_orders_changed": False,
        "production_watchlist_changed": False,
        "trade_enabled": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "parity_rule": "shared_finra_iwm_paper_adapter_v1",
    }


def _pending_sort_key(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("created_asof") or ""), str(row.get("ticker") or ""))


def _positive_float(value: Any) -> float | None:
    numeric = _float_or_none(value)
    if numeric is None or numeric <= 0:
        return None
    return numeric


def _value(row: dict[str, Any], key: str) -> float | None:
    return _float_or_none(row.get(key) if key in row else row.get(key.capitalize()))


def _inc(counter: dict[str, int], key: str) -> None:
    counter[key] = counter.get(key, 0) + 1


def _to_float(value: Any) -> float | None:
    if value in (None, "", "N/A"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    if value in (None, "", "N/A"):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _parse_day(value: Any) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def is_business_day(day: date) -> bool:
    return day.weekday() < 5 and day not in US_MARKET_HOLIDAYS


def previous_business_day(day: date) -> date:
    while not is_business_day(day):
        day -= timedelta(days=1)
    return day


def last_business_day(year: int, month: int) -> date:
    if month == 12:
        day = date(year, 12, 31)
    else:
        day = date(year, month + 1, 1) - timedelta(days=1)
    return previous_business_day(day)


def seventh_business_day_after(settlement: date) -> date:
    day = settlement
    count = 0
    while count < 7:
        day += timedelta(days=1)
        if is_business_day(day):
            count += 1
    return day


def publication_date_for(settlement: date) -> tuple[date, str]:
    if settlement in PUBLICATION_OVERRIDES:
        return PUBLICATION_OVERRIDES[settlement], "finra_schedule_override"
    return seventh_business_day_after(settlement), "finra_7th_business_day_rule"


def settlement_dates(start: date, end: date) -> list[date]:
    dates: set[date] = set()
    cursor = date(start.year, start.month, 1)
    while cursor <= end:
        dates.add(previous_business_day(date(cursor.year, cursor.month, 15)))
        dates.add(last_business_day(cursor.year, cursor.month))
        if cursor.month == 12:
            cursor = date(cursor.year + 1, 1, 1)
        else:
            cursor = date(cursor.year, cursor.month + 1, 1)
    return sorted(d for d in dates if d <= end)
