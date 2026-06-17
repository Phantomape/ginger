"""Default-off revision surprise low-extension paper sleeve.

Shared helper for the positive revision+surprise low-extension replay lead.
It builds the same selected-top1 candidate rows for historical replay and
daily paper snapshots, using replayable daily earnings snapshots plus OHLCV
known at the signal close.

The sleeve is paper-only. It never changes core signal generation, ranking,
sizing, exits, heat, LLM/news behavior, watchlists, or orders.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import macro_relief_leadership_paper_sleeve as leader
    from constants import ROUND_TRIP_COST_PCT
    from data_paths import DATA_ROOT
    from fill_model import (
        SLIPPAGE_BPS_TARGET,
        apply_entry_fill,
        apply_slippage,
    )
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant import macro_relief_leadership_paper_sleeve as leader
    from quant.constants import ROUND_TRIP_COST_PCT
    from quant.data_paths import DATA_ROOT
    from quant.fill_model import (
        SLIPPAGE_BPS_TARGET,
        apply_entry_fill,
        apply_slippage,
    )


SLEEVE_NAME = "REVISION_SURPRISE_LOW_EXTENSION_PAPER"
RULE_VERSION = "revision_surprise_low_extension_shared_default_off_adapter_v1"
SOURCE_RULE_VERSION = "positive_surprise_history_revision_low_extension_candidate_source_v1"
STATE_SCHEMA_VERSION = 1

DEFAULT_EARNINGS_SNAPSHOT_DIR = DATA_ROOT / "daily" / "snapshots" / "earnings"
DEFAULT_LEGACY_EARNINGS_SNAPSHOT_DIR = DATA_ROOT
DEFAULT_STATE_PATH = (
    DATA_ROOT / "paper_sleeves" / "revision_surprise_low_extension" / "state.json"
)
DEFAULT_SNAPSHOT_LOG_PATH = (
    DATA_ROOT / "paper_sleeves" / "revision_surprise_low_extension" / "snapshots.jsonl"
)

EXCLUDED_TICKERS = {
    "ARKX",
    "BIL",
    "CPER",
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
    "XLB",
    "XLE",
    "XLF",
    "XLI",
    "XLK",
    "XLP",
    "XLU",
    "XLV",
    "XLY",
}

DEFAULT_CONFIG = {
    "enabled": False,
    "paper_enabled": True,
    "trade_enabled": False,
    "paper_notional_usd": 4_000.0,
    "daily_entry_slots": 1,
    "max_active_positions": 8,
    "hold_days": 10,
    "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
    "revision_lookback_trading_days": 20,
    "min_eps_estimate_revision_20d_pct": 0.03,
    "min_days_to_earnings": 7.0,
    "max_days_to_earnings": 60.0,
    "min_surprise_history_count": 4,
    "min_positive_surprise_count": 3,
    "min_positive_surprise_ratio": 0.75,
    "min_avg_historical_surprise_pct": 0.0,
    "min_price": 10.0,
    "min_avg_dollar_volume_20d": 50_000_000.0,
    "min_volume_ratio_20d": 1.0,
    "min_close_location": 0.55,
    "min_ret20_excess_spy": 0.0,
    "max_ret20_excess_spy": 0.35,
    "forward_gate_min_closed_trades": 30,
    "forward_gate_positive_net_pnl": True,
    "forward_gate_min_win_rate": 0.0,
    "forward_gate_max_single_ticker_positive_share": 0.50,
    "forward_gate_max_positive_hhi": 0.30,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def empty_revision_surprise_low_extension_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "updated_at": None,
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "skipped_days": [],
    }


def empty_revision_surprise_low_extension_snapshot(
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
        "revision_surprise_low_extension_context": {"status": reason},
        "forward_paper_gate": {"passed": False, "status": "blocked", "reasons": [reason]},
        "production_impact": _production_impact(),
        "error": reason,
    }


def load_revision_surprise_low_extension_state(
    path: Path | str = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_revision_surprise_low_extension_state()
    with state_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    state = empty_revision_surprise_low_extension_state()
    if isinstance(payload, dict):
        state.update(payload)
    _normalise_state(state)
    return state


def save_revision_surprise_low_extension_state(
    state: dict[str, Any],
    path: Path | str = DEFAULT_STATE_PATH,
) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now_iso()
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(_safe(state), handle, indent=2, sort_keys=True)
        handle.write("\n")


def append_revision_surprise_low_extension_snapshot(
    snapshot: dict[str, Any],
    path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_safe(snapshot), sort_keys=True) + "\n")


def build_revision_surprise_low_extension_snapshot(
    *,
    as_of: str,
    ohlcv_by_ticker: dict[str, Any],
    earnings_snapshot_dir: Path | str = DEFAULT_EARNINGS_SNAPSHOT_DIR,
    core_entries: list[dict[str, Any]] | None = None,
    state: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    persist: bool = True,
    state_path: Path | str = DEFAULT_STATE_PATH,
    snapshot_log_path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> dict[str, Any]:
    cfg = _config(config)
    as_of_date = _date10(as_of)
    working_state = deepcopy(
        state
        if state is not None
        else load_revision_surprise_low_extension_state(state_path)
    )
    _normalise_state(working_state)
    rows_by_ticker = leader._normalise_ohlcv_by_ticker(ohlcv_by_ticker)
    if not rows_by_ticker:
        return empty_revision_surprise_low_extension_snapshot(as_of_date, "missing_ohlcv")
    if "SPY" not in rows_by_ticker:
        return empty_revision_surprise_low_extension_snapshot(as_of_date, "missing_spy_ohlcv")

    filled_today = leader._fill_pending_entries(
        working_state,
        rows_by_ticker,
        as_of_date,
        cfg,
    )
    closed_today = leader._advance_open_positions(
        working_state,
        rows_by_ticker,
        as_of_date,
        cfg,
    )
    candidates, contexts, scan = build_revision_surprise_low_extension_candidate_rows(
        ohlcv_by_ticker=rows_by_ticker,
        dates=[as_of_date],
        core_entries_by_date={as_of_date: list(core_entries or [])},
        earnings_snapshot_dir=earnings_snapshot_dir,
        config=cfg,
        require_future_bars=False,
    )
    selected_rows, rejected = select_revision_surprise_low_extension_signal_rows(
        candidates=candidates,
        config=cfg,
    )
    if len(working_state.get("pending_entries") or []) + len(
        working_state.get("open_positions") or []
    ) >= int(cfg["max_active_positions"]):
        rejected.extend({**row, "filter_reason": "max_active_positions"} for row in selected_rows)
        selected_rows = []

    new_pending_entries: list[dict[str, Any]] = []
    if cfg.get("paper_enabled", True):
        for row in selected_rows:
            pending = _pending_entry_from_candidate(row, cfg)
            if not leader._has_pending_open_or_closed_decision(
                working_state,
                pending["decision_id"],
            ):
                working_state["pending_entries"].append(pending)
                new_pending_entries.append(pending)

    if not selected_rows and not contexts:
        _append_skip_once(working_state, _skip_payload(as_of_date, "no_revision_context"))
    elif not selected_rows and contexts and not candidates:
        _append_skip_once(working_state, _skip_payload(as_of_date, "no_candidate"))

    snapshot = _snapshot_payload(
        working_state,
        as_of=as_of_date,
        candidates=candidates,
        selected_rows=selected_rows,
        rejected=rejected,
        contexts=contexts,
        scan=scan,
        new_pending_entries=new_pending_entries,
        filled_today=filled_today,
        closed_today=closed_today,
        rows_by_ticker=rows_by_ticker,
        config=cfg,
    )
    if persist:
        save_revision_surprise_low_extension_state(working_state, state_path)
        append_revision_surprise_low_extension_snapshot(snapshot, snapshot_log_path)
    return snapshot


def build_revision_surprise_low_extension_historical_trades(
    *,
    ohlcv_by_ticker: dict[str, Any],
    core_entries_by_date: dict[str, list[dict[str, Any]]] | None,
    windows: dict[str, dict[str, str]],
    earnings_snapshot_dir: Path | str = DEFAULT_EARNINGS_SNAPSHOT_DIR,
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cfg = _config(config)
    rows_by_ticker = leader._normalise_ohlcv_by_ticker(ohlcv_by_ticker)
    all_trades: list[dict[str, Any]] = []
    audit = {
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "selected_by_window": {},
        "raw_candidate_count_by_window": {},
        "candidate_day_count_by_window": {},
        "rejected_count_by_window": {},
        "scan_by_window": {},
        "contexts_by_window": {},
    }
    for label, window in windows.items():
        dates = [
            day
            for day in _trading_dates(rows_by_ticker)
            if str(window["start"]) <= day <= str(window["end"])
        ]
        candidates, contexts, scan = build_revision_surprise_low_extension_candidate_rows(
            ohlcv_by_ticker=rows_by_ticker,
            dates=dates,
            core_entries_by_date=core_entries_by_date or {},
            earnings_snapshot_dir=earnings_snapshot_dir,
            config=cfg,
            require_future_bars=True,
        )
        selected, rejected = select_revision_surprise_low_extension_paper_trades(
            rows_by_ticker=rows_by_ticker,
            candidates=candidates,
            config=cfg,
        )
        for trade in selected:
            trade["window"] = label
        all_trades.extend(selected)
        audit["selected_by_window"][label] = len(selected)
        audit["raw_candidate_count_by_window"][label] = len(candidates)
        audit["candidate_day_count_by_window"][label] = scan.get("candidate_day_count", 0)
        audit["rejected_count_by_window"][label] = len(rejected)
        audit["scan_by_window"][label] = scan
        audit["contexts_by_window"][label] = contexts[:25]
    audit["total_selected"] = len(all_trades)
    audit["total_raw_candidates"] = sum(audit["raw_candidate_count_by_window"].values())
    return all_trades, audit


def build_revision_surprise_low_extension_candidate_rows(
    *,
    ohlcv_by_ticker: dict[str, Any],
    dates: list[str],
    core_entries_by_date: dict[str, list[dict[str, Any]]] | None = None,
    earnings_snapshot_dir: Path | str = DEFAULT_EARNINGS_SNAPSHOT_DIR,
    config: dict[str, Any] | None = None,
    require_future_bars: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    cfg = _config(config)
    rows_by_ticker = leader._normalise_ohlcv_by_ticker(ohlcv_by_ticker)
    indices = {ticker: leader._row_index(rows) for ticker, rows in rows_by_ticker.items()}
    revision_context = _load_revision_context(
        universe=set(rows_by_ticker),
        signal_dates=dates,
        earnings_snapshot_dir=earnings_snapshot_dir,
        config=cfg,
    )
    rows_by_date_ticker = revision_context["rows_by_date_ticker"]
    entries_by_date = core_entries_by_date or {}
    candidates: list[dict[str, Any]] = []
    contexts: list[dict[str, Any]] = []
    raw_pass_counts: Counter[str] = Counter()
    reject_counts: Counter[str] = Counter()
    candidate_tickers: set[str] = set()

    for signal_date in sorted({_date10(day) for day in dates if _date10(day)}):
        day_rows: list[dict[str, Any]] = []
        for ticker in sorted(rows_by_ticker):
            row = _candidate_for_ticker(
                rows_by_ticker=rows_by_ticker,
                indices=indices,
                rows_by_date_ticker=rows_by_date_ticker,
                entries_by_date=entries_by_date,
                ticker=ticker,
                signal_date=signal_date,
                config=cfg,
                require_future_bars=require_future_bars,
                raw_pass_counts=raw_pass_counts,
                reject_counts=reject_counts,
            )
            if row is None:
                continue
            day_rows.append(row)
            candidate_tickers.add(ticker)
        if not day_rows:
            continue
        day_rows.sort(key=_candidate_sort_key)
        candidates.extend(day_rows)
        contexts.append(
            {
                "date": signal_date,
                "raw_candidate_count": len(day_rows),
                "top_candidate": day_rows[0]["ticker"],
                "top_candidate_score": day_rows[0]["score"],
                "top_candidate_ret20_excess_spy": day_rows[0]["ret20_excess_spy"],
                "top_candidate_eps_revision_20d": day_rows[0][
                    "eps_estimate_revision_20d_pct"
                ],
                "rule_version": SOURCE_RULE_VERSION,
            }
        )

    candidates.sort(key=lambda row: (row["date"], *_candidate_sort_key(row)))
    scan = {
        "scanned_trading_days": len({_date10(day) for day in dates if _date10(day)}),
        "candidate_day_count": len(contexts),
        "raw_candidate_count": len(candidates),
        "unique_candidate_tickers": len(candidate_tickers),
        "raw_pass_counts": dict(raw_pass_counts),
        "revision_reject_counts": dict(sorted(reject_counts.items())),
        "revision_source": revision_context.get("source"),
        "revision_source_caveat": revision_context.get("source_caveat"),
        "revision_file_count": len(revision_context.get("files") or []),
        "revision_row_count": len(revision_context.get("rows") or []),
        **_parameter_summary(cfg),
    }
    return candidates, contexts, scan


def select_revision_surprise_low_extension_signal_rows(
    *,
    candidates: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cfg = _config(config)
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    by_date: dict[str, list[dict[str, Any]]] = {}
    for row in candidates:
        by_date.setdefault(str(row.get("date") or "")[:10], []).append(row)
    for signal_date, rows in sorted(by_date.items()):
        ordered = sorted(rows, key=_candidate_sort_key)
        top_rows = ordered[: int(cfg["daily_entry_slots"])]
        for row in ordered[int(cfg["daily_entry_slots"]) :]:
            rejected.append({**row, "filter_reason": "daily_top1_limit"})
        for row in top_rows:
            ret20_excess = _float(row.get("ret20_excess_spy"))
            if ret20_excess is None:
                rejected.append({**row, "filter_reason": "missing_ret20_excess_spy"})
                continue
            if ret20_excess > float(cfg["max_ret20_excess_spy"]):
                rejected.append(
                    {
                        **row,
                        "filter_reason": "ret20_excess_spy_above_tail_cap",
                        "tail_state_policy": "selected_top1_gate_no_backup_substitution",
                    }
                )
                continue
            candidate = {
                **deepcopy(row),
                "decision_id": _decision_id(row),
                "sleeve": SLEEVE_NAME,
                "rule_version": RULE_VERSION,
                "source_rule_version": SOURCE_RULE_VERSION,
                "signal_date": signal_date,
                "low_extension_tail_state_passed": True,
                "max_ret20_excess_spy": float(cfg["max_ret20_excess_spy"]),
                "tail_state_policy": "selected_top1_gate_no_backup_substitution",
                "paper_status": "candidate",
                "trade_enabled": False,
                "alters_orders": False,
            }
            selected.append(candidate)
    return selected, rejected


def select_revision_surprise_low_extension_paper_trades(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cfg = _config(config)
    selected_rows, rejected = select_revision_surprise_low_extension_signal_rows(
        candidates=candidates,
        config=cfg,
    )
    trades: list[dict[str, Any]] = []
    for row in selected_rows:
        trade = replay_trade_from_candidate(
            rows_by_ticker=rows_by_ticker,
            candidate=row,
            config=cfg,
        )
        if trade is None:
            rejected.append({**row, "filter_reason": "missing_next_open_or_exit"})
            continue
        trades.append(trade)
    return trades, rejected


def replay_trade_from_candidate(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    candidate: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    cfg = _config(config)
    ticker = str(candidate.get("ticker") or "").upper()
    rows = rows_by_ticker.get(ticker) or []
    idx = leader._row_index(rows).get(str(candidate.get("date") or "")[:10])
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
    entry_price = apply_entry_fill(entry_raw)
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


def _candidate_for_ticker(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    rows_by_date_ticker: dict[str, dict[str, dict[str, Any]]],
    entries_by_date: dict[str, list[dict[str, Any]]],
    ticker: str,
    signal_date: str,
    config: dict[str, Any],
    require_future_bars: bool,
    raw_pass_counts: Counter[str],
    reject_counts: Counter[str],
) -> dict[str, Any] | None:
    ticker = ticker.upper()
    if ticker in EXCLUDED_TICKERS or "." in ticker or "-" in ticker:
        return None
    if ticker in {"SPY", "QQQ", "IWM"}:
        return None
    rows = rows_by_ticker.get(ticker) or []
    spy_rows = rows_by_ticker.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None:
        return None
    if require_future_bars and (
        idx + int(config["hold_days"]) >= len(rows) or idx + 1 >= len(rows)
    ):
        return None
    revision_row = rows_by_date_ticker.get(signal_date, {}).get(ticker)
    if revision_row is None:
        return None
    raw_pass_counts["snapshot_revision_row"] += 1

    revision = _float(revision_row.get("eps_estimate_revision_20d_pct"))
    days_to_earnings = _float(revision_row.get("days_to_earnings"))
    if revision is None or days_to_earnings is None:
        reject_counts["missing_revision_or_dte"] += 1
        return None
    if revision < float(config["min_eps_estimate_revision_20d_pct"]):
        reject_counts["revision_below_threshold"] += 1
        return None
    if not (
        float(config["min_days_to_earnings"])
        <= days_to_earnings
        <= float(config["max_days_to_earnings"])
    ):
        reject_counts["days_to_earnings_outside_window"] += 1
        return None
    raw_pass_counts["revision_velocity_passed"] += 1

    surprise_ok, surprise_reject = _surprise_confirmation_passed(revision_row, config)
    if not surprise_ok:
        reject_counts[str(surprise_reject)] += 1
        return None
    raw_pass_counts["surprise_history_confirmed"] += 1

    if idx < 20 or spy_idx < 20:
        return None
    row = rows[idx]
    close = _positive_float(row.get("close"))
    avg_dollar_volume = _avg_dollar_volume_prior(rows, idx)
    volume_ratio = _volume_ratio_prior(rows, idx)
    close_location = leader._close_location(row)
    ret20 = leader._ret(rows, idx, 20)
    spy_ret20 = leader._ret(spy_rows, spy_idx, 20)
    prior_20_high = _prior_high(rows, idx, 20)
    ret20_excess = (
        ret20 - spy_ret20 if ret20 is not None and spy_ret20 is not None else None
    )
    values = [close, avg_dollar_volume, volume_ratio, close_location, ret20_excess, prior_20_high]
    if any(value is None or not math.isfinite(float(value)) for value in values):
        return None
    assert close is not None
    assert avg_dollar_volume is not None
    assert volume_ratio is not None
    assert close_location is not None
    assert ret20_excess is not None
    assert prior_20_high is not None
    raw_pass_counts["fields_non_null"] += 1
    if close < float(config["min_price"]):
        return None
    if avg_dollar_volume < float(config["min_avg_dollar_volume_20d"]):
        return None
    raw_pass_counts["liquidity_passed"] += 1
    if close <= prior_20_high:
        return None
    raw_pass_counts["breakout_passed"] += 1
    if volume_ratio < float(config["min_volume_ratio_20d"]):
        return None
    if close_location < float(config["min_close_location"]):
        return None
    if ret20_excess < float(config["min_ret20_excess_spy"]):
        return None
    raw_pass_counts["price_action_passed"] += 1

    same_day_core = entries_by_date.get(signal_date, [])
    if any(str(entry.get("ticker") or "").upper() == ticker for entry in same_day_core):
        return None
    positive_count = _float(revision_row.get("positive_surprise_count")) or 0.0
    history_count = _float(revision_row.get("surprise_history_count")) or 0.0
    surprise_ratio = positive_count / history_count if history_count > 0 else 0.0
    avg_surprise = _float(revision_row.get("avg_historical_surprise_pct")) or 0.0
    score = (
        min(revision, 0.50) * 10.0
        + ret20_excess * 2.0
        + min(volume_ratio, 4.0) * 0.25
        + close_location
        + 0.10 * surprise_ratio
        + 0.005 * min(avg_surprise, 25.0)
    )
    return {
        "ticker": ticker,
        "date": signal_date,
        "signal_date": signal_date,
        "score": _round(score, 6),
        "prior_snapshot_date": revision_row.get("prior_snapshot_date"),
        "revision_lookback_trading_days": int(config["revision_lookback_trading_days"]),
        "eps_estimate_current": revision_row.get("eps_estimate_current"),
        "eps_estimate_prior": revision_row.get("eps_estimate_prior"),
        "eps_estimate_revision_20d_pct": _round(revision, 6),
        "days_to_earnings": _round(days_to_earnings, 2),
        "avg_historical_surprise_pct": revision_row.get("avg_historical_surprise_pct"),
        "positive_surprise_count": revision_row.get("positive_surprise_count"),
        "surprise_history_count": revision_row.get("surprise_history_count"),
        "positive_surprise_ratio": _round(surprise_ratio, 6),
        "avg_dollar_volume_20": _round(avg_dollar_volume, 2),
        "volume_ratio_20": _round(volume_ratio, 6),
        "close_location": _round(close_location, 6),
        "ret20_excess_spy": _round(ret20_excess, 6),
        "same_day_core_entry_count": len(same_day_core),
        "same_ticker_core_overlap": False,
        "rule_version": SOURCE_RULE_VERSION,
        "trade_enabled": False,
        "alters_orders": False,
        "source_caveat": revision_row.get("source_caveat"),
    }


def _load_revision_context(
    *,
    universe: set[str],
    signal_dates: list[str],
    earnings_snapshot_dir: Path | str,
    config: dict[str, Any],
) -> dict[str, Any]:
    snapshot_dir = Path(earnings_snapshot_dir)
    ticker_set = {
        str(ticker).upper()
        for ticker in universe
        if str(ticker).upper() not in EXCLUDED_TICKERS
        and str(ticker).upper() not in {"SPY", "QQQ", "IWM"}
    }
    desired_dates = sorted({_date10(day) for day in signal_dates if _date10(day)})
    all_paths = sorted(snapshot_dir.glob("earnings_snapshot_*.json"))
    path_by_date = {
        _date_from_snapshot_path(path): path
        for path in all_paths
        if _date_from_snapshot_path(path)
    }
    for signal_date in desired_dates:
        if signal_date not in path_by_date:
            fallback = _snapshot_path(signal_date, snapshot_dir)
            if fallback is not None:
                path_by_date[signal_date] = fallback
    all_dates = sorted(path_by_date)
    date_pos = {day: pos for pos, day in enumerate(all_dates)}
    snapshot_by_date: dict[str, dict[str, Any]] = {}
    files: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    rows_by_date_ticker: dict[str, dict[str, dict[str, Any]]] = {}
    lookback = int(config["revision_lookback_trading_days"])

    for signal_date in desired_dates:
        pos = date_pos.get(signal_date)
        if pos is None:
            files.append(
                {"date": signal_date, "status": "missing_signal_snapshot", "matched_revision_rows": 0}
            )
            continue
        if pos < lookback:
            files.append(
                {
                    "date": signal_date,
                    "status": "missing_prior_snapshot_window",
                    "matched_revision_rows": 0,
                }
            )
            continue
        prior_date = all_dates[pos - lookback]
        signal_path = path_by_date.get(signal_date) or _snapshot_path(signal_date, snapshot_dir)
        prior_path = path_by_date.get(prior_date) or _snapshot_path(prior_date, snapshot_dir)
        if signal_path is None or prior_path is None:
            files.append(
                {
                    "date": signal_date,
                    "prior_date": prior_date,
                    "status": "missing_snapshot_file",
                    "matched_revision_rows": 0,
                }
            )
            continue
        current = snapshot_by_date.setdefault(signal_date, _load_snapshot(signal_path))
        prior = snapshot_by_date.setdefault(prior_date, _load_snapshot(prior_path))
        valid_rows = 0
        qualified_rows = 0
        for raw_ticker, current_row in current.items():
            ticker = str(raw_ticker).upper()
            if ticker not in ticker_set:
                continue
            prior_row = prior.get(ticker)
            if not isinstance(current_row, dict) or not isinstance(prior_row, dict):
                continue
            current_estimate = _float(current_row.get("eps_estimate"))
            prior_estimate = _float(prior_row.get("eps_estimate"))
            days_to_earnings = _float(current_row.get("days_to_earnings"))
            if (
                current_estimate is None
                or prior_estimate is None
                or prior_estimate == 0
                or days_to_earnings is None
            ):
                continue
            revision = (current_estimate - prior_estimate) / abs(prior_estimate)
            if not math.isfinite(revision):
                continue
            valid_rows += 1
            surprise_history = current_row.get("historical_surprise_pct") or []
            if not isinstance(surprise_history, list):
                surprise_history = []
            positive_surprises = sum(
                1 for value in surprise_history if (_float(value) or 0.0) > 0.0
            )
            avg_surprise = _float(current_row.get("avg_historical_surprise_pct"))
            revision_row = {
                "ticker": ticker,
                "signal_date": signal_date,
                "current_snapshot": _repo_rel(signal_path),
                "prior_snapshot": _repo_rel(prior_path),
                "prior_snapshot_date": prior_date,
                "revision_lookback_trading_days": lookback,
                "eps_estimate_current": _round(current_estimate, 6),
                "eps_estimate_prior": _round(prior_estimate, 6),
                "eps_estimate_revision_20d_pct": _round(revision, 6),
                "days_to_earnings": _round(days_to_earnings, 2),
                "avg_historical_surprise_pct": _round(avg_surprise, 6),
                "positive_surprise_count": positive_surprises,
                "surprise_history_count": len(surprise_history),
                "source_caveat": (
                    "Daily snapshots are replayable, but historical EPS estimate "
                    "data remains proxy-grade until PIT vendor provenance is added."
                ),
            }
            rows.append(revision_row)
            rows_by_date_ticker.setdefault(signal_date, {})[ticker] = revision_row
            if (
                revision >= float(config["min_eps_estimate_revision_20d_pct"])
                and float(config["min_days_to_earnings"])
                <= days_to_earnings
                <= float(config["max_days_to_earnings"])
            ):
                qualified_rows += 1
        files.append(
            {
                "date": signal_date,
                "prior_date": prior_date,
                "status": "ok",
                "snapshot_path": _repo_rel(signal_path),
                "prior_snapshot_path": _repo_rel(prior_path),
                "valid_revision_rows": valid_rows,
                "matched_revision_rows": qualified_rows,
            }
        )

    return {
        "rows": rows,
        "files": files,
        "rows_by_date_ticker": rows_by_date_ticker,
        "source": "daily earnings snapshots",
        "source_caveat": (
            "Historical snapshots are replayable but EPS estimate provenance is "
            "proxy-grade; accepted results are default-off paper only until PIT "
            "source provenance and forward rows accumulate."
        ),
    }


def _surprise_confirmation_passed(
    revision_row: dict[str, Any],
    config: dict[str, Any],
) -> tuple[bool, str | None]:
    positive_count = _float(revision_row.get("positive_surprise_count"))
    history_count = _float(revision_row.get("surprise_history_count"))
    avg_surprise = _float(revision_row.get("avg_historical_surprise_pct"))
    if positive_count is None or history_count is None or avg_surprise is None:
        return False, "missing_surprise_history"
    if history_count < int(config["min_surprise_history_count"]):
        return False, "surprise_history_too_short"
    positive_ratio = positive_count / history_count if history_count > 0 else 0.0
    if positive_count < int(config["min_positive_surprise_count"]):
        return False, "positive_surprise_count_below_threshold"
    if positive_ratio < float(config["min_positive_surprise_ratio"]):
        return False, "positive_surprise_ratio_below_threshold"
    if avg_surprise < float(config["min_avg_historical_surprise_pct"]):
        return False, "avg_historical_surprise_negative"
    return True, None


def _pending_entry_from_candidate(row: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    pending = deepcopy(row)
    for key in (
        "entry_date",
        "entry_raw_open",
        "entry_price",
        "exit_date",
        "exit_raw_close",
        "exit_price",
        "pnl",
        "pnl_pct_net",
        "net_return_pct",
    ):
        pending.pop(key, None)
    pending.update(
        {
            "decision_id": _decision_id(row),
            "sleeve": SLEEVE_NAME,
            "rule_version": RULE_VERSION,
            "source_rule_version": SOURCE_RULE_VERSION,
            "paper_notional_usd": float(config["paper_notional_usd"]),
            "notional_usd": float(config["paper_notional_usd"]),
            "entry_timing": "next_session_open",
            "hold_days": int(config["hold_days"]),
            "paper_status": "pending_entry",
            "trade_enabled": False,
            "alters_orders": False,
        }
    )
    return pending


def _snapshot_payload(
    state: dict[str, Any],
    *,
    as_of: str,
    candidates: list[dict[str, Any]],
    selected_rows: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
    contexts: list[dict[str, Any]],
    scan: dict[str, Any],
    new_pending_entries: list[dict[str, Any]],
    filled_today: list[dict[str, Any]],
    closed_today: list[dict[str, Any]],
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
        "trade_enabled_reason": "default_off_until_forward_gate_and_source_provenance_pass",
        "candidate_count": len(selected_rows),
        "raw_candidate_count": len(candidates),
        "rejected_candidate_count": len(rejected),
        "candidate": selected_rows[0] if selected_rows else None,
        "candidates": selected_rows,
        "rejected_candidates": rejected[:50],
        "revision_surprise_low_extension_context": contexts[-1] if contexts else {"date": as_of, "passed": False},
        "context_scan": scan,
        "candidate_universe": _candidate_universe_summary(rows_by_ticker),
        "new_pending_entries": new_pending_entries,
        "new_pending_count": len(new_pending_entries),
        "pending_entries": pending,
        "pending_count": len(pending),
        "filled_today": filled_today,
        "filled_count": len(filled_today),
        "open_positions": open_positions,
        "open_position_count": len(open_positions),
        "closed_today": closed_today,
        "closed_positions_today": closed_today,
        "closed_count_today": len(closed_today),
        "closed_positions": closed,
        "closed_position_count": len(closed),
        "realized_pnl_to_date": _round(sum(_float(row.get("pnl")) or 0.0 for row in closed), 2),
        "unrealized_pnl": leader._unrealized_pnl(open_positions, rows_by_ticker, as_of),
        "forward_paper_gate": leader._forward_paper_gate(closed, config),
        "parameters": dict(config),
        "production_impact": _production_impact(),
        "next_action": "paper_observe_forward_outcomes_only_no_orders",
    }


def _avg_dollar_volume_prior(
    rows: list[dict[str, Any]],
    idx: int,
    lookback: int = 20,
) -> float | None:
    if idx < lookback:
        return None
    values: list[float] = []
    for row in rows[idx - lookback : idx]:
        close = _positive_float(row.get("close"))
        volume = _positive_float(row.get("volume"))
        if close is None or volume is None:
            return None
        values.append(close * volume)
    return sum(values) / len(values)


def _volume_ratio_prior(
    rows: list[dict[str, Any]],
    idx: int,
    lookback: int = 20,
) -> float | None:
    if idx < lookback:
        return None
    current = _positive_float(rows[idx].get("volume"))
    prior = [_positive_float(row.get("volume")) for row in rows[idx - lookback : idx]]
    if current is None or any(value is None for value in prior):
        return None
    avg = sum(float(value) for value in prior if value is not None) / len(prior)
    return current / avg if avg > 0 else None


def _prior_high(rows: list[dict[str, Any]], idx: int, lookback: int = 20) -> float | None:
    if idx < lookback:
        return None
    values = [_positive_float(row.get("high")) for row in rows[idx - lookback : idx]]
    if any(value is None for value in values):
        return None
    return max(float(value) for value in values if value is not None)


def _candidate_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        -float(row.get("score") or 0.0),
        -float(row.get("eps_estimate_revision_20d_pct") or 0.0),
        -float(row.get("ret20_excess_spy") or 0.0),
        str(row.get("ticker") or ""),
    )


def _decision_id(row: dict[str, Any]) -> str:
    signal_date = str(row.get("date") or row.get("signal_date") or "")[:10]
    ticker = str(row.get("ticker") or "").upper()
    return f"{SLEEVE_NAME}:{SOURCE_RULE_VERSION}:{signal_date}:{ticker}"


def _skip_payload(as_of: str, reason: str) -> dict[str, Any]:
    return {
        "decision_id": f"{SLEEVE_NAME}:{RULE_VERSION}:{as_of}:SKIP:{reason}",
        "date": as_of,
        "reason": reason,
        "trade_enabled": False,
        "alters_orders": False,
    }


def _append_skip_once(state: dict[str, Any], row: dict[str, Any]) -> None:
    existing = {
        str(item.get("decision_id") or "")
        for item in state.get("skipped_days") or []
        if isinstance(item, dict)
    }
    if row["decision_id"] not in existing:
        state["skipped_days"].append(row)


def _normalise_state(state: dict[str, Any]) -> None:
    state.setdefault("schema_version", STATE_SCHEMA_VERSION)
    state.setdefault("sleeve", SLEEVE_NAME)
    state.setdefault("pending_entries", [])
    state.setdefault("open_positions", [])
    state.setdefault("closed_positions", [])
    state.setdefault("skipped_days", [])


def _parameter_summary(config: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "paper_notional_usd",
        "daily_entry_slots",
        "hold_days",
        "revision_lookback_trading_days",
        "min_eps_estimate_revision_20d_pct",
        "min_days_to_earnings",
        "max_days_to_earnings",
        "min_surprise_history_count",
        "min_positive_surprise_count",
        "min_positive_surprise_ratio",
        "min_avg_historical_surprise_pct",
        "min_price",
        "min_avg_dollar_volume_20d",
        "min_volume_ratio_20d",
        "min_close_location",
        "min_ret20_excess_spy",
        "max_ret20_excess_spy",
    ]
    return {key: config[key] for key in keys}


def _config(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    if overrides:
        cfg.update({key: value for key, value in overrides.items() if value is not None})
    cfg["enabled"] = False
    cfg["trade_enabled"] = False
    return cfg


def _trading_dates(rows_by_ticker: dict[str, list[dict[str, Any]]]) -> list[str]:
    return sorted({row["date"] for rows in rows_by_ticker.values() for row in rows})


def _candidate_universe_summary(rows_by_ticker: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    return {
        "status": "ohlcv_dict",
        "ticker_count": len(rows_by_ticker),
        "loaded_ohlcv_ticker_count": len(rows_by_ticker),
    }


def _snapshot_path(iso_date: str, snapshot_dir: Path) -> Path | None:
    tag = iso_date.replace("-", "")
    organized = snapshot_dir / f"earnings_snapshot_{tag}.json"
    if organized.exists():
        return organized
    legacy = DEFAULT_LEGACY_EARNINGS_SNAPSHOT_DIR / f"earnings_snapshot_{tag}.json"
    if legacy.exists():
        return legacy
    return None


def _date_from_snapshot_path(path: Path) -> str:
    tag = path.stem[-8:]
    if len(tag) != 8 or not tag.isdigit():
        return ""
    return f"{tag[:4]}-{tag[4:6]}-{tag[6:]}"


def _load_snapshot(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    earnings = payload.get("earnings") if isinstance(payload, dict) else None
    return earnings if isinstance(earnings, dict) else {}


def _date10(value: Any) -> str:
    return leader._date10(value)


def _float(value: Any) -> float | None:
    return leader._float_or_none(value)


def _positive_float(value: Any) -> float | None:
    return leader._positive_float(value)


def _round(value: Any, digits: int = 4) -> Any:
    return leader._round(value, digits)


def _safe(value: Any) -> Any:
    return leader._safe(value)


def _repo_rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(DATA_ROOT.parent))
    except ValueError:
        return str(path)


def prep_and_build_revision_surprise_low_extension_snapshot(
    *,
    as_of: str,
    broad_market_ohlcv: dict,
    spy_ohlcv=None,
    core_entries=None,
):
    ohlcv = dict(broad_market_ohlcv)
    if "SPY" not in ohlcv and spy_ohlcv is not None:
        ohlcv["SPY"] = spy_ohlcv
    return build_revision_surprise_low_extension_snapshot(
        as_of=as_of, ohlcv_by_ticker=ohlcv, core_entries=core_entries,
    )


def _production_impact() -> dict[str, Any]:
    return {
        "shared_policy_changed": True,
        "shared_policy_note": "paper attribution module only; core trading policy unchanged",
        "backtester_adapter_changed": True,
        "run_adapter_changed": False,
        "replay_only": False,
        "default_off_paper_only": True,
        "daily_snapshot_exposed": True,
        "daily_snapshot_note": "helper API emits default-off snapshots; run.py wiring is intentionally unchanged",
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
        "uses_free_data_sources": True,
        "source_provenance_status": "daily_snapshot_proxy_grade_pending_pit_vendor_provenance",
        "adapter_status": "shared_default_off_paper_helper",
        "scope": "default_off_revision_surprise_low_extension_paper_attribution",
    }
