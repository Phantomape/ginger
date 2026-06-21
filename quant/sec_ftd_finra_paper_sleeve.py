"""Default-off SEC FTD + FINRA borrow-pressure paper sleeve.

This shared helper promotes the positive exp-20260604-026 replay lead into a
production-visible paper observation boundary. It emits candidates, paper
ledger state, and attribution metadata only; it never emits live orders and
never changes core signal generation, ranking, sizing, exits, LLM, or news.
"""

from __future__ import annotations

import csv
import io
import json
import math
import sys
import zipfile
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
    from finra_iwm_paper_sleeve import (
        _finra_rows_by_ticker,
        fetch_finra_short_interest_rows,
        load_finra_short_interest_rows,
        refresh_finra_short_interest_archive,
        save_finra_short_interest_archive,
    )
    from volume_breadth_breakout_paper_sleeve import (
        _close_location_value,
        _close_return,
        _date10,
        _exact_asof_price_maps,
        _float_or_none,
        _index_on_date,
        _money,
        _normalise_ohlcv_rows,
        _pnl,
        _prior_average,
        _prior_high,
        _return_pct,
        _safe,
        _single_ticker_positive_share,
        _top5_positive_share,
    )
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant.constants import ROUND_TRIP_COST_PCT
    from quant.data_paths import data_artifact_path
    from quant.fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage
    from quant.finra_iwm_paper_sleeve import (
        _finra_rows_by_ticker,
        fetch_finra_short_interest_rows,
        load_finra_short_interest_rows,
        refresh_finra_short_interest_archive,
        save_finra_short_interest_archive,
    )
    from quant.volume_breadth_breakout_paper_sleeve import (
        _close_location_value,
        _close_return,
        _date10,
        _exact_asof_price_maps,
        _float_or_none,
        _index_on_date,
        _money,
        _normalise_ohlcv_rows,
        _pnl,
        _prior_average,
        _prior_high,
        _return_pct,
        _safe,
        _single_ticker_positive_share,
        _top5_positive_share,
    )


SLEEVE_NAME = "SEC_FTD_FINRA_CONFIRMED_PAPER"
RULE_VERSION = "sec_ftd_finra_shared_default_off_adapter_v1"
FTD_SOURCE_RULE_VERSION = "sec_ftd_pressure_breakout_source_v1"
FINRA_CONFIRMATION_RULE_VERSION = (
    "sec_ftd_candidate_requires_latest_finra_borrow_pressure_confirmation_v1"
)
REPLACEMENT_VALUE_RULE_VERSION = "sec_ftd_finra_forward_replacement_value_v1"
STATE_SCHEMA_VERSION = 1

SEC_FTD_URL = "https://www.sec.gov/files/data/fails-deliver-data/cnsfails{year}{month:02d}{half}.zip"
SEC_FTD_PAGE = "https://www.sec.gov/data-research/sec-markets-data/fails-deliver-data"

DEFAULT_FTD_ROWS_PATH = data_artifact_path("sec_ftd_rows")
DEFAULT_FTD_FILES_PATH = data_artifact_path("sec_ftd_files")
DEFAULT_STATE_PATH = data_artifact_path("sec_ftd_finra_paper_state")
DEFAULT_SNAPSHOT_LOG_PATH = data_artifact_path("sec_ftd_finra_paper_snapshots")

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
    "paper_notional_usd": 4_000.0,
    "breakout_lookback_days": 20,
    "relative_strength_days": 20,
    "volume_ratio_days": 20,
    "min_close": 10.0,
    "min_avg_dollar_volume_20": 50_000_000.0,
    "min_volume_ratio_20": 1.0,
    "min_signal_close_location": 0.55,
    "min_ret20_excess_spy": 0.0,
    "min_ftd_shares": 100_000,
    "min_ftd_notional": 1_000_000.0,
    "min_ftd_notional_to_adv20": 0.006,
    "max_ftd_publication_age_days": 45,
    "min_finra_days_to_cover": 3.0,
    "min_finra_short_interest_change_pct": 0.0,
    "daily_entry_slots": 1,
    "max_active_positions": 5,
    "hold_days": 10,
    "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
    "fetch_lookback_days": 700,
    "max_ftd_archive_staleness_days": 21,
    "max_finra_archive_staleness_days": 16,
    "allow_network_fetch": True,
    "block_same_day_core_overlap": True,
    "forward_gate_min_closed_trades": 20,
    "forward_gate_positive_net_pnl": True,
    "forward_gate_min_win_rate": 0.50,
    "forward_gate_max_single_ticker_positive_share": 0.40,
    "forward_gate_max_top5_positive_share": 0.70,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def empty_sec_ftd_finra_paper_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "updated_at": None,
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "skipped_entries": [],
    }


def load_sec_ftd_finra_paper_state(
    path: Path | str = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_sec_ftd_finra_paper_state()
    with state_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    state = empty_sec_ftd_finra_paper_state()
    if isinstance(payload, dict):
        state.update(payload)
    _normalise_state(state)
    return state


def save_sec_ftd_finra_paper_state(
    state: dict[str, Any],
    path: Path | str = DEFAULT_STATE_PATH,
) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now_iso()
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(_safe(state), handle, indent=2, sort_keys=True)
        handle.write("\n")


def append_sec_ftd_finra_paper_snapshot(
    snapshot: dict[str, Any],
    path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_safe(snapshot), sort_keys=True) + "\n")


def load_sec_ftd_rows(path: Path | str = DEFAULT_FTD_ROWS_PATH) -> list[dict[str, Any]]:
    rows_path = Path(path)
    if not rows_path.exists():
        return []
    # An unreadable archive (for example an unsmudged git-LFS pointer left in
    # the worktree, see exp-20260611-027) must behave like a missing archive so
    # the builder can fall through to its SEC network rebuild instead of dying.
    try:
        with rows_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return []
    if isinstance(payload, dict):
        payload = payload.get("rows") or []
    return _normalise_ftd_rows(payload if isinstance(payload, list) else [])


def save_sec_ftd_archive(
    *,
    rows: list[dict[str, Any]],
    files: list[dict[str, Any]],
    rows_path: Path | str = DEFAULT_FTD_ROWS_PATH,
    files_path: Path | str = DEFAULT_FTD_FILES_PATH,
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


def refresh_sec_ftd_archive(
    *,
    existing_rows: list[dict[str, Any]],
    tickers: set[str],
    as_of: str,
    lookback_days: int = 700,
    max_staleness_days: int = 21,
    fetch_fn=None,
    save: bool = True,
) -> tuple[list[dict[str, Any]], str, list[dict[str, Any]]]:
    """Refresh the SEC fails-to-deliver archive when it has gone stale.

    The archive used to be fetched only when empty, so once populated it froze
    at its last settlement date (exp-20260612-003). The SEC publishes each
    half-month FTD file two to four weeks after the period ends, so an archive
    whose newest settlement is older than ``max_staleness_days`` calendar days
    is checked for newer files; already-cached month zips are read locally and
    only missing periods hit the network. On any fetch failure the stale
    archive is kept rather than discarded.
    """
    fetch = fetch_fn or fetch_sec_ftd_rows
    existing = _normalise_ftd_rows(existing_rows or [])
    as_of_day = _parse_day(as_of)
    if as_of_day is None:
        return existing, "invalid_as_of_date", []

    if not existing:
        rows, files = fetch(tickers=tickers, as_of=as_of, lookback_days=lookback_days)
        rows = _normalise_ftd_rows(rows)
        if rows and save:
            save_sec_ftd_archive(rows=rows, files=files)
        return rows, ("network_fetch" if rows else "network_fetch_empty"), files

    newest = max(_parse_day(str(row.get("settlement_date"))) or as_of_day for row in existing)
    staleness = (as_of_day - newest).days
    if staleness <= int(max_staleness_days):
        return existing, "local_archive_fresh", []

    refresh_lookback = min(int(lookback_days), staleness + 75)
    new_rows, files = fetch(tickers=tickers, as_of=as_of, lookback_days=refresh_lookback)
    new_rows = _normalise_ftd_rows(new_rows)
    merged = {}
    for row in existing:
        merged[(str(row.get("ticker")), str(row.get("settlement_date")))] = row
    added = 0
    for row in new_rows:
        key = (str(row.get("ticker")), str(row.get("settlement_date")))
        if key not in merged:
            added += 1
        merged[key] = row
    rows = _normalise_ftd_rows(list(merged.values()))
    if added:
        if save:
            save_sec_ftd_archive(rows=rows, files=files)
        return rows, "local_archive_refreshed", files
    return rows, "local_archive_stale_refresh_empty", files


def fetch_sec_ftd_rows(
    *,
    tickers: set[str],
    as_of: str,
    lookback_days: int = 700,
    cache_dir: Path | str | None = None,
    timeout: int = 30,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    as_of_day = _parse_day(as_of)
    if as_of_day is None:
        return [], [{"error": "invalid_as_of_date", "as_of": as_of}]
    start = as_of_day - timedelta(days=max(75, int(lookback_days)))
    cache_root = Path(cache_dir) if cache_dir else DEFAULT_FTD_ROWS_PATH.parent / "source_cache"
    cache_root.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "ginger-sec-ftd-finra-paper-sleeve/1.0 "
                "default-off-forward-observation"
            )
        }
    )

    wanted = {str(ticker).upper() for ticker in tickers if ticker}
    rows: list[dict[str, Any]] = []
    files: list[dict[str, Any]] = []
    for year, month, half in _month_iter(start, as_of_day):
        url = SEC_FTD_URL.format(year=year, month=month, half=half)
        cache_path = cache_root / f"cnsfails{year}{month:02d}{half}.zip"
        source = "cache"
        status_code: int | str | None = None
        try:
            if cache_path.exists():
                content = cache_path.read_bytes()
                status_code = "cached"
            else:
                source = "network"
                response = session.get(url, timeout=timeout)
                status_code = response.status_code
                if response.status_code != 200:
                    files.append(
                        {
                            "url": url,
                            "status_code": status_code,
                            "source": source,
                            "matched_rows": 0,
                        }
                    )
                    continue
                content = response.content
                cache_path.write_bytes(content)
        except Exception as exc:  # pragma: no cover - network can vary.
            files.append(
                {
                    "url": url,
                    "status_code": status_code,
                    "source": source,
                    "error": str(exc),
                    "matched_rows": 0,
                }
            )
            continue

        matched = 0
        parsed = 0
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                names = [name for name in archive.namelist() if not name.endswith("/")]
                if not names:
                    files.append(
                        {
                            "url": url,
                            "status_code": status_code,
                            "source": source,
                            "matched_rows": 0,
                            "error": "zip_has_no_data_member",
                        }
                    )
                    continue
                text = archive.read(names[0]).decode("latin-1")
        except Exception as exc:  # pragma: no cover - corrupt external cache.
            files.append(
                {
                    "url": url,
                    "status_code": status_code,
                    "source": source,
                    "matched_rows": 0,
                    "error": str(exc),
                }
            )
            continue

        reader = csv.DictReader(io.StringIO(text), delimiter="|")
        for raw in reader:
            parsed += 1
            ticker = str(raw.get("SYMBOL") or "").upper().strip()
            if ticker not in wanted:
                continue
            settlement = _date8(str(raw.get("SETTLEMENT DATE") or ""))
            fails = _to_int(raw.get("QUANTITY (FAILS)"))
            price = _to_float(raw.get("PRICE"))
            if settlement is None or fails is None or price is None:
                continue
            publication, policy = publication_date_for(settlement)
            matched += 1
            rows.append(
                {
                    "ticker": ticker,
                    "settlement_date": settlement.isoformat(),
                    "publication_date": publication.isoformat(),
                    "publication_date_policy": policy,
                    "pit_safe": True,
                    "ftd_shares": fails,
                    "ftd_price": round(price, 4),
                    "ftd_notional": round(fails * price, 2),
                    "cusip": str(raw.get("CUSIP") or "").strip(),
                    "description": str(raw.get("DESCRIPTION") or "").strip(),
                    "source_url": url,
                    "source_page": SEC_FTD_PAGE,
                }
            )
        files.append(
            {
                "url": url,
                "status_code": status_code,
                "source": source,
                "cache_path": str(cache_path),
                "parsed_rows": parsed,
                "matched_rows": matched,
            }
        )
    return _normalise_ftd_rows(rows), files


def empty_sec_ftd_finra_paper_sleeve_snapshot(as_of: str, reason: str) -> dict[str, Any]:
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
        "data_source": {
            "status": reason,
            "sec_ftd_row_count": 0,
            "finra_row_count": 0,
        },
        "ftd_pressure": _ftd_pressure_summary([], {}, DEFAULT_CONFIG),
        "finra_confirmation": _finra_confirmation_summary([], {}, DEFAULT_CONFIG),
        "candidate_universe": {"status": reason, "ticker_count": 0},
        "forward_paper_gate": {"passed": False, "status": "blocked", "reasons": [reason]},
        "production_impact": _production_impact(),
        "error": reason,
    }


def build_sec_ftd_finra_paper_sleeve_snapshot(
    *,
    as_of: str,
    ohlcv_by_ticker: dict[str, Any] | None = None,
    candidate_universe: dict[str, Any] | list[str] | None = None,
    ftd_rows: list[dict[str, Any]] | None = None,
    finra_rows: list[dict[str, Any]] | None = None,
    same_day_core_tickers: set[str] | list[str] | None = None,
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
    try:
        from us_market_calendar import is_us_equity_session
    except ImportError:  # pragma: no cover - package-style imports in tests
        from quant.us_market_calendar import is_us_equity_session

    if not is_us_equity_session(as_of_date):
        return empty_sec_ftd_finra_paper_sleeve_snapshot(
            as_of_date, "non_us_equity_session"
        )
    rows_by_ticker = {
        str(ticker).upper(): _normalise_ohlcv_rows(rows)
        for ticker, rows in (ohlcv_by_ticker or {}).items()
    }
    if not rows_by_ticker:
        return empty_sec_ftd_finra_paper_sleeve_snapshot(as_of_date, "missing_ohlcv")
    if _index_on_date(rows_by_ticker.get("SPY") or [], as_of_date) is None:
        return empty_sec_ftd_finra_paper_sleeve_snapshot(as_of_date, "missing_spy_asof")

    candidate_source = _normalise_candidate_universe(candidate_universe, rows_by_ticker)
    candidate_tickers = {
        ticker
        for ticker in set(candidate_source.get("tickers") or [])
        if ticker in rows_by_ticker and ticker not in EXCLUDED_TICKERS
    }

    ftd_source_status = "provided"
    ftd_files: list[dict[str, Any]] = []
    if ftd_rows is None:
        ftd_rows = load_sec_ftd_rows()
        ftd_source_status = "local_archive" if ftd_rows else "missing_local_archive"
        if cfg.get("allow_network_fetch", True):
            ftd_rows, ftd_source_status, ftd_files = refresh_sec_ftd_archive(
                existing_rows=ftd_rows,
                tickers=candidate_tickers,
                as_of=as_of_date,
                lookback_days=int(cfg["fetch_lookback_days"]),
                max_staleness_days=int(cfg["max_ftd_archive_staleness_days"]),
            )

    finra_source_status = "provided"
    finra_files: list[dict[str, Any]] = []
    if finra_rows is None:
        finra_rows = load_finra_short_interest_rows()
        finra_source_status = "local_archive" if finra_rows else "missing_local_archive"
        if cfg.get("allow_network_fetch", True):
            finra_rows, finra_source_status, finra_files = refresh_finra_short_interest_archive(
                existing_rows=finra_rows,
                tickers=candidate_tickers,
                as_of=as_of_date,
                lookback_days=int(cfg["fetch_lookback_days"]),
                max_staleness_days=int(cfg["max_finra_archive_staleness_days"]),
            )

    ftd_rows = _normalise_ftd_rows(ftd_rows or [])
    finra_rows = _normalise_finra_rows(finra_rows or [])
    if not ftd_rows:
        return empty_sec_ftd_finra_paper_sleeve_snapshot(
            as_of_date,
            "missing_sec_ftd_rows",
        )
    if not finra_rows:
        return empty_sec_ftd_finra_paper_sleeve_snapshot(
            as_of_date,
            "missing_finra_short_interest_rows",
        )

    working_state = deepcopy(
        state if state is not None else load_sec_ftd_finra_paper_state(state_path)
    )
    _normalise_state(working_state)

    current, opens = _exact_asof_price_maps(
        rows_by_ticker,
        as_of=as_of_date,
        current_prices=current_prices,
        open_prices=open_prices,
    )
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

    ftd_by_ticker = _ftd_rows_by_ticker(ftd_rows)
    finra_by_ticker = _finra_rows_by_ticker(finra_rows)
    core_tickers = {str(t).upper() for t in (same_day_core_tickers or []) if t}
    candidates, reject_counts = _build_candidates(
        rows_by_ticker=rows_by_ticker,
        ftd_by_ticker=ftd_by_ticker,
        finra_by_ticker=finra_by_ticker,
        tickers=sorted(candidate_tickers),
        as_of=as_of_date,
        same_day_core_tickers=core_tickers,
        config=cfg,
    )
    selected_candidates = candidates[: int(cfg["daily_entry_slots"])]

    open_positions = working_state.get("open_positions") or []
    existing_open_tickers = {str(row.get("ticker") or "").upper() for row in open_positions}
    new_pending: list[dict[str, Any]] = []
    room = max(0, int(cfg["max_active_positions"]) - len(open_positions))
    for candidate in selected_candidates[:room]:
        ticker = str(candidate.get("ticker") or "").upper()
        if ticker in existing_open_tickers:
            reject_counts["already_open_in_sec_ftd_finra_paper"] = reject_counts.get(
                "already_open_in_sec_ftd_finra_paper",
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
        "ftd_source_rule_version": FTD_SOURCE_RULE_VERSION,
        "finra_confirmation_rule_version": FINRA_CONFIRMATION_RULE_VERSION,
        "replacement_value_rule_version": REPLACEMENT_VALUE_RULE_VERSION,
        "asof_date": as_of_date,
        "generated_at": utc_now_iso(),
        "enabled": bool(cfg["paper_enabled"]),
        "paper_enabled": bool(cfg["paper_enabled"]),
        "trade_enabled": False,
        "candidate_count": len(selected_candidates),
        "raw_candidate_count": len(candidates),
        "rejected_candidate_count": sum(reject_counts.values()),
        "new_pending_count": len(new_pending),
        "filled_count": len(filled_today),
        "closed_count_today": len(closed_today),
        "pending_count": len(working_state.get("pending_entries") or []),
        "open_position_count": len(open_positions),
        "closed_position_count": len(closed),
        "realized_pnl_to_date": round(sum(_money(row.get("pnl")) for row in closed), 2),
        "unrealized_pnl": round(sum(_money(row.get("unrealized_pnl")) for row in open_positions), 2),
        "data_source": {
            "status": "ok",
            "sec_ftd_status": ftd_source_status,
            "sec_ftd_row_count": len(ftd_rows),
            "sec_ftd_file_count": len(ftd_files),
            "finra_status": finra_source_status,
            "finra_row_count": len(finra_rows),
            "finra_file_count": len(finra_files),
            "covered_ticker_count": len(candidate_tickers),
            "source_page": SEC_FTD_PAGE,
        },
        "candidate_universe": {
            "status": candidate_source.get("status"),
            "ticker_count": len(candidate_tickers),
            "tickers_sample": sorted(candidate_tickers)[:25],
        },
        "ftd_pressure": _ftd_pressure_summary(candidates, reject_counts, cfg),
        "finra_confirmation": _finra_confirmation_summary(candidates, reject_counts, cfg),
        "candidate_reject_counts": dict(sorted(reject_counts.items())),
        "candidates": _safe(selected_candidates),
        "new_pending_entries": _safe(new_pending),
        "filled_entries_today": _safe(filled_today),
        "skipped_entries_today": _safe(skipped_today),
        "closed_positions_today": _safe(closed_today),
        "open_positions": _safe(open_positions),
        "forward_paper_gate": gate,
        "production_impact": _production_impact(),
    }

    if persist:
        save_sec_ftd_finra_paper_state(working_state, state_path)
        append_sec_ftd_finra_paper_snapshot(snapshot, snapshot_log_path)
    return snapshot


def _build_candidates(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    ftd_by_ticker: dict[str, list[dict[str, Any]]],
    finra_by_ticker: dict[str, list[dict[str, Any]]],
    tickers: list[str],
    as_of: str,
    same_day_core_tickers: set[str],
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rejects: dict[str, int] = {}
    spy_rows = rows_by_ticker.get("SPY") or []
    spy_idx = _index_on_date(spy_rows, as_of)
    if spy_idx is None:
        return [], {"missing_spy_asof": len(tickers)}
    min_idx = max(
        int(config["breakout_lookback_days"]),
        int(config["relative_strength_days"]),
        int(config["volume_ratio_days"]),
    )
    candidates: list[dict[str, Any]] = []
    signal_day = _parse_day(as_of)
    for ticker in tickers:
        rows = rows_by_ticker.get(ticker) or []
        idx = _index_on_date(rows, as_of)
        if idx is None or idx < min_idx or spy_idx < int(config["relative_strength_days"]):
            _inc(rejects, "insufficient_history")
            continue

        ftd = _latest_row_by_publication(ftd_by_ticker, ticker, as_of)
        if ftd is None:
            _inc(rejects, "missing_published_sec_ftd_row")
            continue
        ftd_publication = _parse_day(ftd.get("publication_date"))
        if signal_day is None or ftd_publication is None:
            _inc(rejects, "missing_sec_ftd_publication_date")
            continue
        publication_age = (signal_day - ftd_publication).days
        if publication_age < 0 or publication_age > int(config["max_ftd_publication_age_days"]):
            _inc(rejects, "sec_ftd_publication_age_out_of_range")
            continue

        close = _value(rows[idx], "close")
        high = _value(rows[idx], "high")
        low = _value(rows[idx], "low")
        volume = _value(rows[idx], "volume")
        if close is None or high is None or low is None or volume is None:
            _inc(rejects, "missing_ohlcv_fields")
            continue
        if close < float(config["min_close"]):
            _inc(rejects, "price_below_threshold")
            continue

        avg_dollar_volume = _avg_dollar_volume(rows, idx, int(config["volume_ratio_days"]))
        if avg_dollar_volume is None or avg_dollar_volume < float(config["min_avg_dollar_volume_20"]):
            _inc(rejects, "avg_dollar_volume_below_threshold")
            continue

        prior_high = _prior_high(rows, idx, int(config["breakout_lookback_days"]))
        if prior_high is None or close <= prior_high:
            _inc(rejects, "not_20d_breakout")
            continue

        avg_volume = _prior_average(rows, idx, int(config["volume_ratio_days"]), "volume")
        if avg_volume is None or avg_volume <= 0:
            _inc(rejects, "missing_volume_context")
            continue
        volume_ratio = volume / avg_volume
        if volume_ratio < float(config["min_volume_ratio_20"]):
            _inc(rejects, "volume_ratio_below_threshold")
            continue

        close_location = _close_location_value(close=close, high=high, low=low)
        if close_location is None or close_location < float(config["min_signal_close_location"]):
            _inc(rejects, "close_location_below_threshold")
            continue

        ret_days = int(config["relative_strength_days"])
        ret20 = _close_return(rows, idx - ret_days, idx)
        spy_ret20 = _close_return(spy_rows, spy_idx - ret_days, spy_idx)
        if ret20 is None or spy_ret20 is None:
            _inc(rejects, "missing_relative_strength")
            continue
        ret20_excess_spy = ret20 - spy_ret20
        if ret20_excess_spy < float(config["min_ret20_excess_spy"]):
            _inc(rejects, "ret20_excess_spy_below_threshold")
            continue

        ftd_shares = _to_float(ftd.get("ftd_shares"))
        ftd_notional = _to_float(ftd.get("ftd_notional"))
        if ftd_shares is None or ftd_shares < float(config["min_ftd_shares"]):
            _inc(rejects, "sec_ftd_shares_below_threshold")
            continue
        if ftd_notional is None or ftd_notional < float(config["min_ftd_notional"]):
            _inc(rejects, "sec_ftd_notional_below_threshold")
            continue
        ftd_to_adv20 = ftd_notional / avg_dollar_volume
        if ftd_to_adv20 < float(config["min_ftd_notional_to_adv20"]):
            _inc(rejects, "sec_ftd_to_adv20_below_threshold")
            continue

        finra = _latest_row_by_publication(finra_by_ticker, ticker, as_of)
        if finra is None:
            _inc(rejects, "missing_published_finra_row")
            continue
        days_to_cover = _to_float(finra.get("days_to_cover"))
        short_change_pct = _to_float(finra.get("short_interest_change_pct"))
        if days_to_cover is None:
            _inc(rejects, "missing_finra_days_to_cover")
            continue
        if short_change_pct is None:
            _inc(rejects, "missing_finra_short_interest_change_pct")
            continue
        if days_to_cover < float(config["min_finra_days_to_cover"]):
            _inc(rejects, "finra_days_to_cover_below_threshold")
            continue
        if short_change_pct <= float(config["min_finra_short_interest_change_pct"]):
            _inc(rejects, "finra_short_interest_change_not_positive")
            continue

        same_ticker_core_overlap = ticker in same_day_core_tickers
        if config.get("block_same_day_core_overlap", True) and same_ticker_core_overlap:
            _inc(rejects, "same_ticker_core_overlap")
            continue

        score = (
            math.log1p(ftd_notional) * 0.45
            + min(ftd_to_adv20, 0.08) * 100.0
            + ret20_excess_spy * 2.0
            + min(volume_ratio, 4.0) * 0.25
            + close_location
        )
        candidates.append(
            {
                "sleeve": SLEEVE_NAME,
                "ticker": ticker,
                "date": as_of,
                "signal_date": as_of,
                "strategy": "sec_ftd_finra_confirmed_candidate_pool",
                "rule_version": RULE_VERSION,
                "ftd_source_rule_version": FTD_SOURCE_RULE_VERSION,
                "finra_confirmation_rule_version": FINRA_CONFIRMATION_RULE_VERSION,
                "score": _round(score, 6),
                "close": _round(close, 4),
                "signal_day_high": _round(high, 4),
                "signal_day_low": _round(low, 4),
                "volume": _round(volume, 2),
                "avg_dollar_volume_20": _round(avg_dollar_volume, 2),
                "volume_ratio_20": _round(volume_ratio, 6),
                "close_location": _round(close_location, 6),
                "ret20": _round(ret20, 6),
                "spy_ret20": _round(spy_ret20, 6),
                "ret20_excess_spy": _round(ret20_excess_spy, 6),
                "ftd_publication_date": ftd.get("publication_date"),
                "ftd_settlement_date": ftd.get("settlement_date"),
                "ftd_publication_age_days": publication_age,
                "ftd_shares": int(ftd_shares),
                "ftd_notional": _round(ftd_notional, 2),
                "ftd_notional_to_adv20": _round(ftd_to_adv20, 6),
                "ftd_source_url": ftd.get("source_url"),
                "source_page": SEC_FTD_PAGE,
                "finra_publication_date": finra.get("publication_date"),
                "finra_settlement_date": finra.get("settlement_date"),
                "finra_days_to_cover": _round(days_to_cover, 6),
                "finra_short_interest_change_pct": _round(short_change_pct, 6),
                "same_day_core_entry_count": len(same_day_core_tickers),
                "same_ticker_core_overlap": same_ticker_core_overlap,
                "known_at": "after_signal_date_close_with_published_sec_ftd_and_finra_before_next_open_paper_entry",
                "intended_notional": float(config["paper_notional_usd"]),
                "trade_enabled": False,
                "alters_orders": False,
                "ftd_finra_trade_enabled": False,
                "ftd_finra_alters_orders": False,
            }
        )

    candidates.sort(
        key=lambda row: (
            -float(row["score"]),
            -float(row["ftd_notional_to_adv20"]),
            -float(row["ret20_excess_spy"]),
            row["ticker"],
        )
    )
    return candidates, rejects


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
            "strategy": "sec_ftd_finra_confirmed_candidate_pool",
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
    return {
        "decision_id": f"{SLEEVE_NAME}:{RULE_VERSION}:{as_of}:{ticker}",
        "sleeve": SLEEVE_NAME,
        "ticker": ticker,
        "created_asof": as_of,
        "status": "pending_next_open",
        "notional": _positive_float(candidate.get("intended_notional"))
        or float(config["paper_notional_usd"]),
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


def _ftd_pressure_summary(
    candidates: list[dict[str, Any]],
    reject_counts: dict[str, int],
    config: dict[str, Any],
) -> dict[str, Any]:
    return {
        "rule_version": FTD_SOURCE_RULE_VERSION,
        "candidate_count": len(candidates),
        "min_ftd_shares": int(config["min_ftd_shares"]),
        "min_ftd_notional": float(config["min_ftd_notional"]),
        "min_ftd_notional_to_adv20": float(config["min_ftd_notional_to_adv20"]),
        "max_publication_age_days": int(config["max_ftd_publication_age_days"]),
        "reject_counts": {
            key: value
            for key, value in reject_counts.items()
            if key.startswith("sec_ftd") or key.startswith("missing_sec_ftd")
        },
        "trade_enabled": False,
        "alters_orders": False,
    }


def _finra_confirmation_summary(
    candidates: list[dict[str, Any]],
    reject_counts: dict[str, int],
    config: dict[str, Any],
) -> dict[str, Any]:
    return {
        "rule_version": FINRA_CONFIRMATION_RULE_VERSION,
        "admitted_candidate_count": len(candidates),
        "rejected_count": sum(
            value
            for key, value in reject_counts.items()
            if key.startswith("finra") or key.startswith("missing_finra")
        ),
        "reject_counts": {
            key: value
            for key, value in reject_counts.items()
            if key.startswith("finra") or key.startswith("missing_finra")
        },
        "min_finra_days_to_cover": float(config["min_finra_days_to_cover"]),
        "min_finra_short_interest_change_pct": float(
            config["min_finra_short_interest_change_pct"]
        ),
        "trade_enabled": False,
        "alters_orders": False,
    }


def _normalise_ftd_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or row.get("SYMBOL") or "").upper().strip()
        settlement = _date10(row.get("settlement_date") or row.get("SETTLEMENT DATE"))
        publication = _date10(row.get("publication_date") or row.get("usable_trade_date"))
        if not ticker or not settlement or not publication:
            continue
        ftd_shares = _to_int(row.get("ftd_shares") or row.get("QUANTITY (FAILS)"))
        ftd_price = _to_float(row.get("ftd_price") or row.get("PRICE"))
        ftd_notional = _to_float(row.get("ftd_notional"))
        if ftd_notional is None and ftd_shares is not None and ftd_price is not None:
            ftd_notional = ftd_shares * ftd_price
        out.append(
            {
                **row,
                "ticker": ticker,
                "settlement_date": settlement,
                "publication_date": publication,
                "usable_trade_date": row.get("usable_trade_date") or publication,
                "pit_safe": True,
                "ftd_shares": ftd_shares,
                "ftd_price": ftd_price,
                "ftd_notional": round(ftd_notional, 2) if ftd_notional is not None else None,
                "source_page": row.get("source_page") or SEC_FTD_PAGE,
            }
        )
    out.sort(key=lambda item: (item["ticker"], item["publication_date"], item["settlement_date"]))
    return out


def _normalise_finra_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ticker_rows in _finra_rows_by_ticker(rows).values():
        out.extend(ticker_rows)
    return out


def _ftd_rows_by_ticker(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for row in _normalise_ftd_rows(rows):
        out.setdefault(row["ticker"], []).append(row)
    for ticker_rows in out.values():
        ticker_rows.sort(key=lambda row: (row["publication_date"], row["settlement_date"]))
    return out


def _latest_row_by_publication(
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    ticker: str,
    signal_date: str,
) -> dict[str, Any] | None:
    rows = rows_by_ticker.get(ticker.upper()) or []
    eligible = [row for row in rows if str(row.get("publication_date") or "") <= signal_date]
    if not eligible:
        return None
    return eligible[-1]


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


def prep_and_build_sec_ftd_finra_paper_sleeve_snapshot(
    *,
    as_of: str,
    ohlcv_dict: dict,
    spy_ohlcv=None,
    same_day_core_tickers=None,
    open_prices=None,
    current_prices=None,
):
    ohlcv = dict(ohlcv_dict)
    if spy_ohlcv is not None:
        ohlcv["SPY"] = spy_ohlcv
    candidate_universe = {
        "status": "daily_data_universe",
        "tickers": sorted(
            t for t, f in ohlcv.items()
            if f is not None and str(t).upper() != "SPY"
        ),
    }
    return build_sec_ftd_finra_paper_sleeve_snapshot(
        as_of=as_of, ohlcv_by_ticker=ohlcv, candidate_universe=candidate_universe,
        same_day_core_tickers=same_day_core_tickers,
        open_prices=open_prices, current_prices=current_prices,
    )


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
        "parity_rule": "shared_sec_ftd_finra_paper_adapter_v1",
    }


def publication_date_for(settlement: date) -> tuple[date, str]:
    if settlement.day <= 15:
        if settlement.month == 12:
            return date(settlement.year + 1, 1, 1), "first_half_month_end_plus_one_day"
        return date(settlement.year, settlement.month + 1, 1), "first_half_month_end_plus_one_day"
    if settlement.month == 12:
        return date(settlement.year + 1, 1, 16), "second_half_next_month_15_plus_one_day"
    return date(settlement.year, settlement.month + 1, 16), "second_half_next_month_15_plus_one_day"


def _month_iter(start: date, end: date) -> list[tuple[int, int, str]]:
    months: list[tuple[int, int, str]] = []
    cursor = date(start.year, start.month, 1)
    stop = date(end.year, end.month, 1)
    while cursor <= stop:
        months.append((cursor.year, cursor.month, "a"))
        months.append((cursor.year, cursor.month, "b"))
        if cursor.month == 12:
            cursor = date(cursor.year + 1, 1, 1)
        else:
            cursor = date(cursor.year, cursor.month + 1, 1)
    return months


def _avg_dollar_volume(rows: list[dict[str, Any]], idx: int, days: int) -> float | None:
    if idx < days:
        return None
    values: list[float] = []
    for row in rows[idx - days:idx]:
        close = _positive_float(row.get("close"))
        volume = _positive_float(row.get("volume"))
        if close is None or volume is None:
            continue
        values.append(close * volume)
    if len(values) < days:
        return None
    return sum(values) / len(values)


def _date8(value: str) -> date | None:
    try:
        return datetime.strptime(str(value).strip(), "%Y%m%d").date()
    except (TypeError, ValueError):
        return None


def _parse_day(value: Any) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


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
    if value in (None, "", "N/A", "."):
        return None
    try:
        out = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _to_int(value: Any) -> int | None:
    number = _to_float(value)
    return int(number) if number is not None else None


def _round(value: Any, digits: int = 4) -> float | None:
    number = _to_float(value)
    return round(number, digits) if number is not None else None
