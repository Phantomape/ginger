"""Default-off deep index drawdown rebound paper sleeve (exp-20260706-003).

Policy bundle (fixed, predeclared on the ticket): when QQQ closes 12% or more
below its rolling 252-session close high, an episode opens; the first
stabilization day inside the episode (up close finishing in the upper half of
the daily range) is a paper entry signal, executed at the next session open
with a fixed 5-trading-day hold and a single active position. The episode
closes when the drawdown recovers to -5% (hysteresis) and can re-trigger later.

Historical replay and the daily default-off snapshot share the same episode
flags and the same fill/exit arithmetic as the accepted leadership sleeves
(next-open entry with buy slippage, close exit with sell slippage and
round-trip cost), so replay and production observation stay in parity.

The sleeve is paper-only. It never changes core signal generation, ranking,
sizing, exits, heat, LLM/news behavior, watchlists, or orders.
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import macro_relief_leadership_paper_sleeve as leader
    from constants import ROUND_TRIP_COST_PCT
    from data_paths import DATA_ROOT, atomic_write_json
    from fill_model import SLIPPAGE_BPS_ENTRY, SLIPPAGE_BPS_TARGET, apply_slippage
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant import macro_relief_leadership_paper_sleeve as leader
    from quant.constants import ROUND_TRIP_COST_PCT
    from quant.data_paths import DATA_ROOT, atomic_write_json
    from quant.fill_model import SLIPPAGE_BPS_ENTRY, SLIPPAGE_BPS_TARGET, apply_slippage


SLEEVE_NAME = "DEEP_DRAWDOWN_REBOUND_PAPER"
RULE_VERSION = "deep_drawdown_episode_etf_rebound_shared_default_off_adapter_v1"
SOURCE_RULE_VERSION = "deep_drawdown_episode_trigger_v1"
STATE_SCHEMA_VERSION = 1

DEFAULT_STATE_PATH = DATA_ROOT / "paper_sleeves" / "deep_drawdown_rebound" / "state.json"
DEFAULT_SNAPSHOT_LOG_PATH = (
    DATA_ROOT / "paper_sleeves" / "deep_drawdown_rebound" / "snapshots.jsonl"
)
INDEX_HISTORY_PATH = DATA_ROOT / "non_ohlcv" / "index_history" / "index_daily_pre2023.jsonl"

DEFAULT_CONFIG = {
    "enabled": False,
    "paper_enabled": True,
    "trade_enabled": False,
    "ticker": "QQQ",
    "paper_notional_usd": 10_000.0,
    "hold_days": 5,
    "max_active_positions": 1,
    "rolling_high_days": 252,
    "trigger_drawdown_pct": -0.12,
    "episode_reset_drawdown_pct": -0.05,
    "min_close_location": 0.50,
    "min_history_days": 260,
    # None = unlimited re-entry (the exp-20260706-003 shape, rejected on
    # secular-bear bleed). exp-20260706-006 ships max_entries_per_episode=1
    # via BUDGET_CONFIG: only the first stabilization day of an episode is
    # eligible, episode identity = episode_start_date.
    "max_entries_per_episode": None,
    "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
    # Single-instrument sleeve: the concentration axis is episode diversity,
    # not ticker share, so the forward gate asks for distinct episodes instead
    # of the leadership sleeves' per-ticker HHI checks.
    "forward_gate_min_closed_trades": 8,
    "forward_gate_min_distinct_episodes": 3,
    "forward_gate_positive_net_pnl": True,
    "forward_gate_min_win_rate": 0.50,
}

# The exp-20260706-006 shipping bundle: first stabilization day per episode only.
BUDGET_CONFIG = {**DEFAULT_CONFIG, "max_entries_per_episode": 1}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _config(config: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(DEFAULT_CONFIG)
    if isinstance(config, dict):
        merged.update(config)
    return merged


def _round(value: Any, digits: int) -> float | None:
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out else None


# ---------------------------------------------------------------------------
# Pure episode policy


def compute_episode_flags(
    rows: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Per-session episode flags for a normalized OHLCV row list.

    Deterministic and point-in-time: day ``i`` uses only closes up to ``i``.
    The rolling high window uses the trailing ``rolling_high_days`` sessions
    including today (shorter early in the series, by design: pre-2000 highs are
    unknowable from the archive anyway).
    """
    cfg = _config(config)
    window_days = int(cfg["rolling_high_days"])
    trigger = float(cfg["trigger_drawdown_pct"])
    reset = float(cfg["episode_reset_drawdown_pct"])
    min_close_location = float(cfg["min_close_location"])

    flags: list[dict[str, Any]] = []
    closes: list[float] = []
    prev_close: float | None = None
    in_episode = False
    episode_start: str | None = None

    for row in rows:
        date = str(row.get("date") or "")[:10]
        close = _float_or_none(row.get("close"))
        high = _float_or_none(row.get("high"))
        low = _float_or_none(row.get("low"))
        flag: dict[str, Any] = {
            "date": date,
            "close": close,
            "rolling_high": None,
            "drawdown_pct": None,
            "in_episode": in_episode,
            "episode_start_date": episode_start,
            "stabilization": False,
        }
        if close is None:
            flags.append(flag)
            continue

        closes.append(close)
        window = closes[-window_days:]
        rolling_high = max(window)
        drawdown = (close / rolling_high) - 1.0 if rolling_high > 0 else None
        flag["rolling_high"] = _round(rolling_high, 4)
        flag["drawdown_pct"] = _round(drawdown, 6)

        if drawdown is not None:
            if in_episode and drawdown >= reset:
                in_episode = False
                episode_start = None
            elif not in_episode and drawdown <= trigger:
                in_episode = True
                episode_start = date

        close_location = None
        if high is not None and low is not None and high > low:
            close_location = (close - low) / (high - low)
        stabilization = bool(
            in_episode
            and prev_close is not None
            and close > prev_close
            and close_location is not None
            and close_location >= min_close_location
        )

        flag["in_episode"] = in_episode
        flag["episode_start_date"] = episode_start
        flag["close_location"] = _round(close_location, 4)
        flag["stabilization"] = stabilization
        flags.append(flag)
        prev_close = close

    return flags


def build_deep_drawdown_rebound_candidate(
    as_of: str,
    rows: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Candidate row (or None) plus the episode context for ``as_of``."""
    cfg = _config(config)
    as_of_date = leader._date10(as_of)
    flags = compute_episode_flags(rows, cfg)
    flag = next((item for item in flags if item["date"] == as_of_date), None)
    if flag is None:
        return None, {"date": as_of_date, "status": "no_bar_for_asof"}
    context = {
        "date": as_of_date,
        "status": "ok",
        "ticker": str(cfg["ticker"]).upper(),
        "drawdown_pct": flag.get("drawdown_pct"),
        "rolling_high": flag.get("rolling_high"),
        "in_episode": bool(flag.get("in_episode")),
        "episode_start_date": flag.get("episode_start_date"),
        "close_location": flag.get("close_location"),
        "stabilization": bool(flag.get("stabilization")),
    }
    if not flag.get("stabilization"):
        return None, context
    candidate = {
        "ticker": str(cfg["ticker"]).upper(),
        "signal_date": as_of_date,
        "signal_close": flag.get("close"),
        "drawdown_pct": flag.get("drawdown_pct"),
        "episode_start_date": flag.get("episode_start_date"),
        "close_location": flag.get("close_location"),
        "source_rule_version": SOURCE_RULE_VERSION,
    }
    return candidate, context


def _decision_id(signal_date: str) -> str:
    return f"deep_drawdown_rebound:QQQ:{signal_date}"


def _episode_entry_count(state: dict[str, Any], episode_start_date: Any) -> int:
    """Entries (pending + open + closed) already attributed to an episode."""
    wanted = str(episode_start_date or "")
    count = 0
    for key in ("pending_entries", "open_positions", "closed_positions"):
        for row in state.get(key) or []:
            if isinstance(row, dict) and str(row.get("episode_start_date") or "") == wanted:
                count += 1
    return count


def _pending_entry_from_candidate(
    candidate: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    return {
        "decision_id": _decision_id(candidate["signal_date"]),
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "ticker": candidate["ticker"],
        "signal_date": candidate["signal_date"],
        "episode_start_date": candidate.get("episode_start_date"),
        "signal_drawdown_pct": candidate.get("drawdown_pct"),
        "signal_close_location": candidate.get("close_location"),
        "notional_usd": float(config["paper_notional_usd"]),
        "hold_days": int(config["hold_days"]),
        "paper_status": "pending",
        "created_at": utc_now_iso(),
    }


# ---------------------------------------------------------------------------
# Historical replay (same arithmetic as the daily lifecycle helpers)


def replay_deep_drawdown_rebound_trades(
    rows: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """Replay the fixed policy bundle over a normalized row list.

    Mirrors ``leader._fill_pending_entries`` / ``leader._advance_open_positions``:
    entry at next-session open with buy slippage, observed_trading_days counts
    the entry session as day 1, exit at the close of session ``hold_days`` with
    sell slippage and round-trip cost. One position at a time; a new signal is
    eligible from the exit session onward (flat at that close).
    """
    cfg = _config(config)
    hold_days = int(cfg["hold_days"])
    notional = float(cfg["paper_notional_usd"])
    cost = float(cfg["round_trip_cost_pct"])
    flags = compute_episode_flags(rows, cfg)

    budget = cfg.get("max_entries_per_episode")
    budget = int(budget) if budget is not None else None
    entries_by_episode: dict[str, int] = {}
    trades: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    next_allowed_signal_idx = 0
    for i, flag in enumerate(flags):
        if not flag.get("stabilization"):
            continue
        date = flag["date"]
        if start_date and date < str(start_date)[:10]:
            continue
        if end_date and date > str(end_date)[:10]:
            break
        if i < next_allowed_signal_idx:
            continue
        episode_key = str(flag.get("episode_start_date"))
        if budget is not None and entries_by_episode.get(episode_key, 0) >= budget:
            continue
        entry_idx = i + 1
        if entry_idx >= len(rows):
            unresolved.append({"signal_date": date, "reason": "no_next_session_yet"})
            continue
        entry_open = _float_or_none(rows[entry_idx].get("open"))
        if entry_open is None or entry_open <= 0:
            unresolved.append({"signal_date": date, "reason": "missing_entry_open"})
            continue
        exit_idx = entry_idx + hold_days - 1
        entry_price = apply_slippage(entry_open, SLIPPAGE_BPS_ENTRY, "buy")
        entries_by_episode[episode_key] = entries_by_episode.get(episode_key, 0) + 1
        trade = {
            "decision_id": _decision_id(date),
            "ticker": str(cfg["ticker"]).upper(),
            "signal_date": date,
            "episode_start_date": flag.get("episode_start_date"),
            "signal_drawdown_pct": flag.get("drawdown_pct"),
            "entry_date": str(rows[entry_idx].get("date"))[:10],
            "entry_raw_open": _round(entry_open, 4),
            "entry_price": _round(entry_price, 4),
            "notional_usd": notional,
            "hold_days": hold_days,
        }
        if exit_idx >= len(rows):
            trade["paper_status"] = "open_at_series_end"
            unresolved.append(trade)
            next_allowed_signal_idx = len(rows)
            continue
        exit_close = _float_or_none(rows[exit_idx].get("close"))
        if exit_close is None or exit_close <= 0:
            trade["paper_status"] = "missing_exit_close"
            unresolved.append(trade)
            next_allowed_signal_idx = exit_idx
            continue
        exit_price = apply_slippage(exit_close, SLIPPAGE_BPS_TARGET, "sell")
        pnl_pct_net = (exit_price / entry_price) - 1.0 - cost
        trade.update(
            {
                "exit_date": str(rows[exit_idx].get("date"))[:10],
                "exit_raw_close": _round(exit_close, 4),
                "exit_price": _round(exit_price, 4),
                "pnl_pct_net": _round(pnl_pct_net, 6),
                "net_return_pct": _round(pnl_pct_net, 6),
                "pnl": _round(notional * pnl_pct_net, 2),
                "paper_status": "closed",
            }
        )
        trades.append(trade)
        next_allowed_signal_idx = exit_idx

    return {
        "rule_version": RULE_VERSION,
        "parameters": {k: cfg[k] for k in sorted(cfg) if not k.startswith("forward_gate")},
        "trades": trades,
        "unresolved": unresolved,
        "summary": summarize_replay_trades(trades),
    }


def summarize_replay_trades(trades: list[dict[str, Any]]) -> dict[str, Any]:
    closed = [t for t in trades if t.get("paper_status") == "closed"]
    returns = [t["pnl_pct_net"] for t in closed if t.get("pnl_pct_net") is not None]
    episodes: dict[str, list[dict[str, Any]]] = {}
    for trade in closed:
        episodes.setdefault(str(trade.get("episode_start_date")), []).append(trade)
    episode_rows = [
        {
            "episode_start_date": key,
            "trades": len(rows),
            "total_pnl": _round(sum(t.get("pnl") or 0.0 for t in rows), 2),
            "total_return_pct": _round(sum(t.get("pnl_pct_net") or 0.0 for t in rows), 6),
        }
        for key, rows in sorted(episodes.items())
    ]
    wins = sum(1 for r in returns if r > 0)
    sorted_returns = sorted(returns)
    median = None
    if sorted_returns:
        mid = len(sorted_returns) // 2
        if len(sorted_returns) % 2:
            median = sorted_returns[mid]
        else:
            median = (sorted_returns[mid - 1] + sorted_returns[mid]) / 2.0
    return {
        "closed_trades": len(closed),
        "distinct_episodes": len(episodes),
        "win_rate": round(wins / len(returns), 4) if returns else None,
        "total_pnl": _round(sum(t.get("pnl") or 0.0 for t in closed), 2),
        "mean_return_pct": _round(sum(returns) / len(returns), 6) if returns else None,
        "median_return_pct": _round(median, 6) if median is not None else None,
        "worst_return_pct": _round(min(returns), 6) if returns else None,
        "best_return_pct": _round(max(returns), 6) if returns else None,
        "positive_episode_count": sum(1 for e in episode_rows if (e["total_pnl"] or 0) > 0),
        "episodes": episode_rows,
    }


# ---------------------------------------------------------------------------
# Daily default-off snapshot (shared lifecycle with the leadership sleeves)


def empty_deep_drawdown_rebound_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "updated_at": None,
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "skipped_days": [],
    }


def empty_deep_drawdown_rebound_snapshot(as_of: str, reason: str) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "asof_date": leader._date10(as_of),
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": False,
        "trade_enabled": False,
        "candidate_count": 0,
        "new_pending_count": 0,
        "filled_count": 0,
        "closed_count_today": 0,
        "pending_count": 0,
        "open_position_count": 0,
        "closed_position_count": 0,
        "realized_pnl_to_date": 0.0,
        "unrealized_pnl": 0.0,
        "episode_context": {"status": reason},
        "forward_paper_gate": {"passed": False, "status": "blocked", "reasons": [reason]},
        "production_impact": leader._production_impact(),
        "error": reason,
    }


def load_deep_drawdown_rebound_state(
    path: Path | str = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_deep_drawdown_rebound_state()
    with state_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    state = empty_deep_drawdown_rebound_state()
    if isinstance(payload, dict):
        state.update(payload)
    for key in ("pending_entries", "open_positions", "closed_positions", "skipped_days"):
        if not isinstance(state.get(key), list):
            state[key] = []
    return state


def save_deep_drawdown_rebound_state(
    state: dict[str, Any],
    path: Path | str = DEFAULT_STATE_PATH,
) -> None:
    state["updated_at"] = utc_now_iso()
    atomic_write_json(leader._safe(state), Path(path), indent=2)


def append_deep_drawdown_rebound_snapshot(
    snapshot: dict[str, Any],
    path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(leader._safe(snapshot), sort_keys=True) + "\n")


def _forward_paper_gate(
    closed_positions: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    closed = [row for row in closed_positions if isinstance(row, dict)]
    realized = sum(_float_or_none(row.get("pnl")) or 0.0 for row in closed)
    wins = sum(1 for row in closed if (_float_or_none(row.get("pnl")) or 0.0) > 0)
    win_rate = round(wins / len(closed), 4) if closed else None
    episodes = {str(row.get("episode_start_date")) for row in closed}
    checks = {
        "min_closed_trades": len(closed) >= int(config["forward_gate_min_closed_trades"]),
        "min_distinct_episodes": len(episodes)
        >= int(config["forward_gate_min_distinct_episodes"]),
        "positive_net_pnl": realized > 0
        if config.get("forward_gate_positive_net_pnl")
        else True,
        "min_win_rate": win_rate is not None
        and win_rate >= float(config["forward_gate_min_win_rate"]),
    }
    reasons = [key for key, passed in checks.items() if not passed]
    return {
        "passed": not reasons,
        "status": "passed" if not reasons else "blocked",
        "reasons": reasons,
        "checks": checks,
        "metrics": {
            "closed_trades": len(closed),
            "distinct_episodes": len(episodes),
            "realized_pnl": _round(realized, 2),
            "win_rate": win_rate,
        },
    }


def prep_and_build_deep_drawdown_rebound_snapshot(
    *,
    as_of: str,
    qqq_ohlcv: Any = None,
    ohlcv_dict: dict[str, Any] | None = None,
    cached_ohlcv_fn: Any = None,
    state: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    persist: bool = True,
    state_path: Path | str = DEFAULT_STATE_PATH,
    snapshot_log_path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> dict[str, Any]:
    cfg = _config(config)
    as_of_date = leader._date10(as_of)
    ticker = str(cfg["ticker"]).upper()

    source = qqq_ohlcv
    if source is None:
        source = leader._lookup_ohlcv_source(ohlcv_dict, ticker, cached_ohlcv_fn)
    rows = leader._normalise_ohlcv_rows(source)
    if len(rows) < int(cfg["min_history_days"]):
        return empty_deep_drawdown_rebound_snapshot(as_of_date, "insufficient_history")

    working_state = deepcopy(
        state if state is not None else load_deep_drawdown_rebound_state(state_path)
    )
    rows_by_ticker = {ticker: rows}

    filled_today = leader._fill_pending_entries(working_state, rows_by_ticker, as_of_date, cfg)
    closed_today = leader._advance_open_positions(working_state, rows_by_ticker, as_of_date, cfg)

    candidate, context = build_deep_drawdown_rebound_candidate(as_of_date, rows, cfg)
    new_pending_entries: list[dict[str, Any]] = []
    active = len(working_state.get("pending_entries") or []) + len(
        working_state.get("open_positions") or []
    )
    budget = cfg.get("max_entries_per_episode")
    within_episode_budget = True
    if candidate is not None and budget is not None:
        within_episode_budget = (
            _episode_entry_count(working_state, candidate.get("episode_start_date"))
            < int(budget)
        )
    if (
        candidate is not None
        and cfg.get("paper_enabled", True)
        and active < int(cfg["max_active_positions"])
        and within_episode_budget
    ):
        pending = _pending_entry_from_candidate(candidate, cfg)
        if not leader._has_pending_open_or_closed_decision(
            working_state, pending["decision_id"]
        ):
            working_state["pending_entries"].append(pending)
            new_pending_entries.append(pending)

    closed = [
        row for row in working_state.get("closed_positions") or [] if isinstance(row, dict)
    ]
    pending_rows = [
        row for row in working_state.get("pending_entries") or [] if isinstance(row, dict)
    ]
    open_rows = [
        row for row in working_state.get("open_positions") or [] if isinstance(row, dict)
    ]
    snapshot = {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "asof_date": as_of_date,
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": bool(cfg.get("paper_enabled", True)),
        "trade_enabled": False,
        "trade_enabled_reason": "default_off_until_forward_gate_and_trade_adapter_pass",
        "candidate_count": 1 if candidate else 0,
        "candidate": candidate,
        "episode_context": context,
        "new_pending_entries": new_pending_entries,
        "new_pending_count": len(new_pending_entries),
        "pending_entries": pending_rows,
        "pending_count": len(pending_rows),
        "filled_today": filled_today,
        "filled_count": len(filled_today),
        "open_positions": open_rows,
        "open_position_count": len(open_rows),
        "closed_today": closed_today,
        "closed_count_today": len(closed_today),
        "closed_positions": closed,
        "closed_position_count": len(closed),
        "realized_pnl_to_date": _round(
            sum(_float_or_none(row.get("pnl")) or 0.0 for row in closed), 2
        ),
        "unrealized_pnl": _round(
            sum(_float_or_none(row.get("unrealized_pnl")) or 0.0 for row in open_rows), 2
        ),
        "forward_paper_gate": _forward_paper_gate(closed, cfg),
        "parameters": dict(cfg),
        "production_impact": leader._production_impact(),
        "next_action": "paper_observe_forward_outcomes_only_no_orders",
    }
    if persist:
        save_deep_drawdown_rebound_state(working_state, state_path)
        append_deep_drawdown_rebound_snapshot(snapshot, snapshot_log_path)
    return snapshot


# ---------------------------------------------------------------------------
# Archive helpers (pre-2023 index history + warehouse continuation)


def load_index_history_rows(
    ticker: str,
    archive_path: Path | str = INDEX_HISTORY_PATH,
) -> list[dict[str, Any]]:
    """Load one ticker's rows from the pre-2023 index history JSONL archive."""
    path = Path(archive_path)
    if not path.exists():
        return []
    wanted = str(ticker).upper()
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(row.get("ticker") or "").upper() == wanted:
                rows.append(row)
    return sorted(rows, key=lambda row: str(row.get("date") or ""))


def merge_bar_series(
    archive_rows: list[dict[str, Any]],
    warehouse_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Concatenate archive + warehouse rows; warehouse wins on date overlap."""
    by_date: dict[str, dict[str, Any]] = {}
    for row in archive_rows:
        by_date[str(row.get("date") or "")[:10]] = row
    for row in warehouse_rows:
        by_date[str(row.get("date") or "")[:10]] = row
    return [by_date[key] for key in sorted(by_date) if key]
