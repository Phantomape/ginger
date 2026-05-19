"""exp-20260519-034: broad-market leadership candidate-pool shadow.

Alpha search. Uses the broad-market OHLCV warehouse from exp-20260519-030 to
test one default-off paper candidate-pool variable: non-current-tradeable,
all-window liquid equities that show trend leadership versus SPY may add replacement value to the
accepted stack from exp-20260519-033.

Core entries, exits, filters, ranking, sizing, LLM/news, and live/default order
paths are unchanged. This is a paper/shadow replay only.

No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sqlite3
import statistics
import sys
from collections import OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260519-034"
EXPERIMENT_SLUG = "broad_market_leadership_candidate_pool_shadow"
BASELINE_EXPERIMENT_ID = "exp-20260519-033"
WAREHOUSE_EXPERIMENT_ID = "exp-20260519-030"
RULE_VERSION = "broad_market_leadership_candidate_pool_shadow_v1"

INITIAL_CAPITAL = 100_000.0
PAPER_NOTIONAL = 7_500.0
MAX_ACTIVE_POSITIONS = 5
DAILY_ENTRY_SLOTS = 3
HOLD_DAYS = 20
MIN_SELECTED_TRADES = 30
MIN_SELECTED_WINDOWS = 3
MIN_EV_IMPROVED_WINDOWS = 2
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_TICKER_POSITIVE_SHARE = 0.50
MAX_TOP5_POSITIVE_SHARE = 0.70

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from constants import ROUND_TRIP_COST_PCT  # noqa: E402


WINDOWS = OrderedDict(
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

LEADERSHIP_PROFILES: OrderedDict[str, dict[str, Any]] = OrderedDict(
    [
        (
            "leadership_strict",
            {
                "ret20_excess_spy_min": 0.07,
                "ret60_min": 0.15,
                "near_high_60_min": 0.97,
                "volume_ratio_20_min": 1.20,
                "description": "strict trend leadership, breakout proximity, and volume confirmation",
                "aggression_order": 1,
            },
        ),
        (
            "leadership_balanced",
            {
                "ret20_excess_spy_min": 0.05,
                "ret60_min": 0.10,
                "near_high_60_min": 0.95,
                "volume_ratio_20_min": 1.10,
                "description": "balanced trend leadership profile",
                "aggression_order": 2,
            },
        ),
        (
            "leadership_broad",
            {
                "ret20_excess_spy_min": 0.035,
                "ret60_min": 0.08,
                "near_high_60_min": 0.93,
                "volume_ratio_20_min": 1.00,
                "description": "broader leadership profile with weaker volume confirmation",
                "aggression_order": 3,
            },
        ),
    ]
)

TITLE_EXCLUSION_KEYWORDS = (
    " ETF",
    " FUND",
    " TRUST",
    " WARRANT",
    " RIGHTS",
    " UNIT",
    " ACQUISITION",
    " SPAC",
    " PREFERRED",
    " DEPOSITARY",
)

BASELINE_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / BASELINE_EXPERIMENT_ID
    / "state_surface_rank_depth_score_volume_notional.json"
)
WAREHOUSE_SQLITE = (
    REPO_ROOT
    / "data"
    / "experiments"
    / WAREHOUSE_EXPERIMENT_ID
    / "warehouse_main.sqlite"
)
WAREHOUSE_MANIFEST = (
    REPO_ROOT
    / "data"
    / "experiments"
    / WAREHOUSE_EXPERIMENT_ID
    / "broad_market_ohlcv_warehouse_manifest.json"
)
OPEN_POSITIONS_JSON = REPO_ROOT / "operator_inputs" / "open_positions.json"
UNIVERSE_STATE_JSON = (
    REPO_ROOT / "data" / "daily" / "universe" / "universe_state_20260518.json"
)
OUT_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / EXPERIMENT_ID
    / f"{EXPERIMENT_SLUG}.json"
)
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"


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


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


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


def _json_load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _round(value: Any, digits: int = 6) -> float | None:
    number = _float(value)
    if number is None:
        return None
    return round(number, digits)


def _excluded_title(title: str | None) -> bool:
    upper = f" {str(title or '').upper()} "
    return any(keyword in upper for keyword in TITLE_EXCLUSION_KEYWORDS)


def _audit_open_positions() -> dict[str, Any]:
    payload = _json_load(OPEN_POSITIONS_JSON)
    rows: list[dict[str, Any]] = []
    for section in ("positions", "observations"):
        rows.extend([row for row in payload.get(section, []) if isinstance(row, dict)])
    missing = []
    for row in rows:
        for field in ("entry_date", "target_price"):
            if row.get(field) in (None, ""):
                missing.append({"ticker": row.get("ticker"), "field": field})
    return {
        "path": _repo_rel(OPEN_POSITIONS_JSON),
        "checked_rows": len(rows),
        "required_fields": ["entry_date", "target_price"],
        "missing_required_fields": missing,
        "passed": not missing,
    }


def _load_tradeable_universe() -> dict[str, Any]:
    payload = _json_load(UNIVERSE_STATE_JSON)
    core = {
        str(ticker).upper()
        for ticker in payload.get("core_trade_universe", [])
        if ticker
    }
    governance = {
        str(ticker).upper()
        for ticker in payload.get("governance_tradeable_universe", [])
        if ticker
    }
    pilot = {
        str(ticker).upper()
        for ticker in payload.get("pilot_trade_universe", [])
        if ticker
    }
    open_positions = set()
    if OPEN_POSITIONS_JSON.exists():
        positions = _json_load(OPEN_POSITIONS_JSON)
        for section in ("positions", "observations"):
            for row in positions.get(section, []) or []:
                if isinstance(row, dict) and row.get("ticker"):
                    open_positions.add(str(row["ticker"]).upper())
    tradeable = core | governance | pilot | open_positions
    return {
        "path": _repo_rel(UNIVERSE_STATE_JSON),
        "as_of": payload.get("as_of"),
        "core_trade_universe": sorted(core),
        "governance_tradeable_universe": sorted(governance),
        "pilot_trade_universe": sorted(pilot),
        "open_positions_universe": sorted(open_positions),
        "excluded_tradeable_universe": sorted(tradeable),
        "excluded_tradeable_count": len(tradeable),
    }


def _warehouse_audit() -> dict[str, Any]:
    if not WAREHOUSE_SQLITE.exists():
        raise RuntimeError(f"Missing warehouse: {_repo_rel(WAREHOUSE_SQLITE)}")
    with sqlite3.connect(WAREHOUSE_SQLITE) as con:
        counts = {
            "ticker_universe": con.execute(
                "select count(*) from ticker_universe"
            ).fetchone()[0],
            "coverage_summary": con.execute(
                "select count(*) from coverage_summary"
            ).fetchone()[0],
            "ohlcv": con.execute("select count(*) from ohlcv").fetchone()[0],
            "all_windows_full_liquid": con.execute(
                "select count(*) from coverage_summary where all_windows_full_liquid = 1"
            ).fetchone()[0],
            "any_window_full_liquid": con.execute(
                "select count(*) from coverage_summary where any_window_full_liquid = 1"
            ).fetchone()[0],
        }
    manifest = _json_load(WAREHOUSE_MANIFEST) if WAREHOUSE_MANIFEST.exists() else {}
    return {
        "warehouse_experiment_id": WAREHOUSE_EXPERIMENT_ID,
        "warehouse_path": _repo_rel(WAREHOUSE_SQLITE),
        "manifest_path": _repo_rel(WAREHOUSE_MANIFEST),
        "sqlite_counts": counts,
        "manifest_status": manifest.get("status"),
        "manifest_loaded_ticker_count": manifest.get("loaded_ticker_count"),
        "manifest_note": (
            "Partial warehouse is acceptable for this paper scout because the "
            "candidate set is restricted to all-window full-liquid rows."
        ),
    }


def _candidate_universe(tradeable_universe: set[str]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    with sqlite3.connect(WAREHOUSE_SQLITE) as con:
        con.row_factory = sqlite3.Row
        for row in con.execute(
            """
            select
                u.ticker,
                u.title,
                u.hygiene_pass,
                u.tags_json,
                c.row_count,
                c.first_date,
                c.last_date,
                c.all_windows_full_liquid,
                c.full_liquid_window_count,
                c.windows_json
            from ticker_universe u
            join coverage_summary c on c.ticker = u.ticker
            where u.hygiene_pass = 1 and c.all_windows_full_liquid = 1
            order by u.ticker
            """
        ):
            ticker = str(row["ticker"]).upper()
            reasons: list[str] = []
            if ticker in tradeable_universe:
                reasons.append("current_tradeable_universe")
            if ticker in {"SPY", "QQQ"}:
                reasons.append("benchmark")
            if _excluded_title(row["title"]):
                reasons.append("title_exclusion")
            item = {
                "ticker": ticker,
                "title": row["title"],
                "row_count": row["row_count"],
                "first_date": row["first_date"],
                "last_date": row["last_date"],
                "full_liquid_window_count": row["full_liquid_window_count"],
                "windows_json": row["windows_json"],
                "exclusion_reasons": reasons,
            }
            if reasons:
                excluded.append(item)
            else:
                rows.append(item)
    return {
        "source": "warehouse all_windows_full_liquid non-current-tradeable common-stock proxy",
        "excluded_tradeable_universe_count": len(tradeable_universe),
        "candidate_count": len(rows),
        "excluded_count": len(excluded),
        "title_exclusion_keywords": TITLE_EXCLUSION_KEYWORDS,
        "sample_candidates": rows[:50],
        "sample_excluded": excluded[:50],
        "tickers": [row["ticker"] for row in rows],
    }


def _load_price_rows(tickers: list[str]) -> dict[str, list[dict[str, Any]]]:
    wanted = sorted(set(tickers) | {"SPY", "QQQ"})
    placeholders = ",".join("?" for _ in wanted)
    query = (
        "select ticker, date, open, high, low, close, volume "
        f"from ohlcv where ticker in ({placeholders}) order by ticker, date"
    )
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with sqlite3.connect(WAREHOUSE_SQLITE) as con:
        con.row_factory = sqlite3.Row
        for row in con.execute(query, wanted):
            by_ticker[str(row["ticker"]).upper()].append(
                {
                    "date": str(row["date"])[:10],
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["volume"]),
                }
            )
    return dict(by_ticker)


def _trading_days(
    prices: dict[str, list[dict[str, Any]]],
    start: str,
    end: str,
) -> list[str]:
    spy_rows = prices.get("SPY") or []
    days = [
        row["date"]
        for row in spy_rows
        if start <= str(row.get("date") or "") <= end
    ]
    if days:
        return days
    return sorted(
        {
            str(row.get("date") or "")
            for rows in prices.values()
            for row in rows
            if start <= str(row.get("date") or "") <= end
        }
    )


def _close_on_or_before(
    prices: dict[str, list[dict[str, Any]]],
    ticker: str,
    day: str,
) -> float | None:
    close = None
    for row in prices.get(str(ticker).upper()) or []:
        row_day = str(row.get("date") or "")
        if row_day > day:
            break
        value = row.get("close")
        if value is not None:
            close = float(value)
    return close


def _index_by_date(prices: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, int]]:
    return {
        ticker: {row["date"]: idx for idx, row in enumerate(rows)}
        for ticker, rows in prices.items()
    }


def _feature_row(
    *,
    ticker: str,
    rows: list[dict[str, Any]],
    idx: int,
    spy_rows: list[dict[str, Any]],
    spy_index: dict[str, int],
) -> dict[str, Any] | None:
    if idx < 60:
        return None
    row = rows[idx]
    day = row["date"]
    spy_idx = spy_index.get(day)
    if spy_idx is None or spy_idx < 20:
        return None
    close = float(row["close"])
    if close <= 0:
        return None
    close_20 = float(rows[idx - 20]["close"])
    close_60 = float(rows[idx - 60]["close"])
    spy_close = float(spy_rows[spy_idx]["close"])
    spy_close_20 = float(spy_rows[spy_idx - 20]["close"])
    if close_20 <= 0 or close_60 <= 0 or spy_close_20 <= 0:
        return None

    volume_slice = rows[idx - 20 : idx]
    avg_volume_20 = sum(float(item["volume"]) for item in volume_slice) / len(
        volume_slice
    )
    if avg_volume_20 <= 0:
        return None
    high_60 = max(float(item["high"]) for item in rows[idx - 59 : idx + 1])
    if high_60 <= 0:
        return None

    ret20 = close / close_20 - 1.0
    spy_ret20 = spy_close / spy_close_20 - 1.0
    ret60 = close / close_60 - 1.0
    volume_ratio_20 = float(row["volume"]) / avg_volume_20
    near_high_60 = close / high_60
    score = (
        ret20 - spy_ret20
        + 0.50 * ret60
        + 0.04 * min(volume_ratio_20, 5.0)
        + 0.20 * (near_high_60 - 0.90)
    )
    return {
        "ticker": ticker,
        "date": day,
        "index": idx,
        "close": round(close, 6),
        "ret20": round(ret20, 6),
        "spy_ret20": round(spy_ret20, 6),
        "ret20_excess_spy": round(ret20 - spy_ret20, 6),
        "ret60": round(ret60, 6),
        "volume_ratio_20": round(volume_ratio_20, 6),
        "near_high_60": round(near_high_60, 6),
        "score": round(score, 6),
    }


def _qualifies(feature: dict[str, Any], profile: dict[str, Any]) -> bool:
    return bool(
        float(feature["ret20_excess_spy"]) >= float(profile["ret20_excess_spy_min"])
        and float(feature["ret60"]) >= float(profile["ret60_min"])
        and float(feature["near_high_60"]) >= float(profile["near_high_60_min"])
        and float(feature["volume_ratio_20"]) >= float(profile["volume_ratio_20_min"])
    )


def _make_trade(
    *,
    feature: dict[str, Any],
    prices: dict[str, list[dict[str, Any]]],
    window_end: str,
    profile_name: str,
    rank: int,
) -> dict[str, Any] | None:
    ticker = str(feature["ticker"]).upper()
    rows = prices.get(ticker) or []
    entry_idx = int(feature["index"]) + 1
    exit_idx = entry_idx + HOLD_DAYS - 1
    if exit_idx >= len(rows):
        return None
    entry = rows[entry_idx]
    exit_ = rows[exit_idx]
    if entry["date"] > window_end or exit_["date"] > window_end:
        return None
    entry_open = float(entry["open"])
    exit_close = float(exit_["close"])
    if entry_open <= 0 or exit_close <= 0:
        return None
    shares = PAPER_NOTIONAL / entry_open
    net_return = exit_close / entry_open - 1.0 - ROUND_TRIP_COST_PCT
    return {
        "ticker": ticker,
        "decision_date": feature["date"],
        "entry_date": entry["date"],
        "exit_date": exit_["date"],
        "entry_open": round(entry_open, 6),
        "exit_close": round(exit_close, 6),
        "shares": round(shares, 8),
        "notional": PAPER_NOTIONAL,
        "pnl": round(PAPER_NOTIONAL * net_return, 2),
        "net_return_pct": round(net_return, 6),
        "hold_days": HOLD_DAYS,
        "profile": profile_name,
        "rank": rank,
        "rule_version": RULE_VERSION,
        "ret20_excess_spy": feature["ret20_excess_spy"],
        "ret60": feature["ret60"],
        "volume_ratio_20": feature["volume_ratio_20"],
        "near_high_60": feature["near_high_60"],
        "score": feature["score"],
    }


def _simulate_window(
    *,
    label: str,
    profile_name: str,
    profile: dict[str, Any],
    candidate_tickers: list[str],
    prices: dict[str, list[dict[str, Any]]],
    indexes: dict[str, dict[str, int]],
) -> dict[str, Any]:
    spec = WINDOWS[label]
    days = _trading_days(prices, spec["start"], spec["end"])
    spy_rows = prices.get("SPY") or []
    spy_index = indexes.get("SPY") or {}
    active: list[dict[str, str]] = []
    trades: list[dict[str, Any]] = []
    daily_counts: dict[str, int] = {}

    for day in days:
        active = [row for row in active if row["exit_date"] > day]
        capacity = MAX_ACTIVE_POSITIONS - len(active)
        if capacity <= 0:
            continue
        active_tickers = {row["ticker"] for row in active}
        candidates = []
        for ticker in candidate_tickers:
            if ticker in active_tickers:
                continue
            rows = prices.get(ticker) or []
            idx = (indexes.get(ticker) or {}).get(day)
            if idx is None:
                continue
            feature = _feature_row(
                ticker=ticker,
                rows=rows,
                idx=idx,
                spy_rows=spy_rows,
                spy_index=spy_index,
            )
            if feature and _qualifies(feature, profile):
                candidates.append(feature)
        candidates.sort(
            key=lambda row: (
                float(row["score"]),
                float(row["ret20_excess_spy"]),
                float(row["volume_ratio_20"]),
                row["ticker"],
            ),
            reverse=True,
        )
        entries = 0
        for rank, feature in enumerate(candidates, start=1):
            if entries >= min(DAILY_ENTRY_SLOTS, capacity):
                break
            if str(feature["ticker"]).upper() in active_tickers:
                continue
            trade = _make_trade(
                feature=feature,
                prices=prices,
                window_end=spec["end"],
                profile_name=profile_name,
                rank=rank,
            )
            if trade is None:
                continue
            trade["window"] = label
            trades.append(trade)
            active.append({"ticker": trade["ticker"], "exit_date": trade["exit_date"]})
            active_tickers.add(trade["ticker"])
            entries += 1
        daily_counts[day] = len(candidates)

    return {
        "window": label,
        "profile": profile_name,
        "trades": trades,
        "candidate_signal_days": sum(1 for count in daily_counts.values() if count > 0),
        "candidate_signal_count": sum(daily_counts.values()),
        "max_daily_candidate_count": max(daily_counts.values()) if daily_counts else 0,
        "sample_daily_candidate_counts": dict(list(daily_counts.items())[:20]),
    }


def _event_equity_curve(
    *,
    trades: list[dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
    start: str,
    end: str,
) -> list[dict[str, Any]]:
    days = _trading_days(prices, start, end)
    entries_by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    exits_by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        entries_by_day[str(trade["entry_date"])].append(trade)
        exits_by_day[str(trade["exit_date"])].append(trade)

    cash = INITIAL_CAPITAL
    active: list[dict[str, Any]] = []
    curve: list[dict[str, Any]] = []
    for day in days:
        for trade in entries_by_day.get(day, []):
            cash -= float(trade["notional"])
            active.append(trade)

        exiting = exits_by_day.get(day, [])
        for trade in exiting:
            close = _close_on_or_before(prices, str(trade["ticker"]), day)
            if close is None:
                continue
            notional = float(trade["notional"])
            cash += float(trade["shares"]) * close - notional * ROUND_TRIP_COST_PCT
        if exiting:
            exit_keys = {
                (trade["ticker"], trade["entry_date"], trade["exit_date"])
                for trade in exiting
            }
            active = [
                trade
                for trade in active
                if (trade["ticker"], trade["entry_date"], trade["exit_date"])
                not in exit_keys
            ]

        market_value = 0.0
        for trade in active:
            close = _close_on_or_before(prices, str(trade["ticker"]), day)
            if close is not None:
                market_value += float(trade["shares"]) * close
        equity = cash + market_value
        curve.append(
            {
                "date": day,
                "event_equity": round(equity, 2),
                "event_pnl": round(equity - INITIAL_CAPITAL, 2),
                "active_event_positions": len(active),
            }
        )
    return curve


def _daily_sharpe(curve: list[tuple[str, float]]) -> float | None:
    returns = []
    for (_, previous), (_, current) in zip(curve, curve[1:]):
        if previous > 0:
            returns.append(current / previous - 1.0)
    if len(returns) < 2:
        return None
    stdev = statistics.stdev(returns)
    if stdev <= 0:
        return None
    return round((sum(returns) / len(returns)) / stdev * math.sqrt(252), 2)


def _max_drawdown(curve: list[tuple[str, float]]) -> float:
    peak = 0.0
    max_dd = 0.0
    for _, equity in curve:
        if equity > peak:
            peak = equity
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak)
    return round(max_dd, 4)


def _event_risk(trades: list[dict[str, Any]]) -> dict[str, Any]:
    if not trades:
        return {
            "worst_trade_pct": None,
            "max_consecutive_losses": 0,
            "tail_loss_share": None,
        }
    ordered = sorted(trades, key=lambda row: (row["exit_date"], row["entry_date"], row["ticker"]))
    returns = [float(row.get("net_return_pct") or 0.0) for row in ordered]
    worst = min(returns) if returns else None
    current_loss_streak = 0
    max_loss_streak = 0
    for row in ordered:
        if float(row.get("pnl") or 0.0) <= 0:
            current_loss_streak += 1
            max_loss_streak = max(max_loss_streak, current_loss_streak)
        else:
            current_loss_streak = 0
    losses_abs = sorted(
        [abs(float(row.get("pnl") or 0.0)) for row in ordered if float(row.get("pnl") or 0.0) < 0],
        reverse=True,
    )
    if losses_abs:
        tail_count = max(1, math.ceil(len(losses_abs) * 0.10))
        tail_share = sum(losses_abs[:tail_count]) / sum(losses_abs)
    else:
        tail_share = None
    return {
        "worst_trade_pct": round(worst, 6) if worst is not None else None,
        "max_consecutive_losses": max_loss_streak,
        "tail_loss_share": round(tail_share, 4) if tail_share is not None else None,
    }


def _single_ticker_positive_share(trades: list[dict[str, Any]]) -> float | None:
    positive = [row for row in trades if float(row.get("pnl") or 0.0) > 0]
    total_positive = sum(float(row.get("pnl") or 0.0) for row in positive)
    if total_positive <= 0:
        return None
    by_ticker: dict[str, float] = defaultdict(float)
    for row in positive:
        by_ticker[str(row.get("ticker") or "").upper()] += float(row.get("pnl") or 0.0)
    return round(max(by_ticker.values()) / total_positive, 6) if by_ticker else None


def _top5_positive_share(trades: list[dict[str, Any]]) -> float | None:
    positive = [row for row in trades if float(row.get("pnl") or 0.0) > 0]
    total_positive = sum(float(row.get("pnl") or 0.0) for row in positive)
    if total_positive <= 0:
        return None
    by_ticker: dict[str, float] = defaultdict(float)
    for row in positive:
        by_ticker[str(row.get("ticker") or "").upper()] += float(row.get("pnl") or 0.0)
    top5 = sorted(by_ticker.values(), reverse=True)[:5]
    return round(sum(top5) / total_positive, 6)


def _metrics_from_overlay(
    *,
    baseline_metrics: dict[str, Any],
    event_curve: list[dict[str, Any]],
    event_trades: list[dict[str, Any]],
) -> dict[str, Any]:
    baseline_curve = [
        (str(day), float(equity))
        for day, equity in baseline_metrics["combined_equity_curve"]
    ]
    event_by_day = {row["date"]: float(row["event_pnl"]) for row in event_curve}
    combined_curve = [
        (day, round(baseline_equity + event_by_day.get(day, 0.0), 2))
        for day, baseline_equity in baseline_curve
    ]
    final_equity = combined_curve[-1][1] if combined_curve else INITIAL_CAPITAL
    total_pnl = final_equity - INITIAL_CAPITAL
    total_return = total_pnl / INITIAL_CAPITAL
    sharpe = _daily_sharpe(combined_curve)
    expected_value = total_return * sharpe if sharpe is not None else None
    event_wins = sum(1 for trade in event_trades if float(trade.get("pnl") or 0.0) > 0)
    baseline_wins = int(baseline_metrics.get("winning_trades") or 0)
    baseline_trade_count = int(baseline_metrics.get("trade_count") or 0)
    trade_count = baseline_trade_count + len(event_trades)
    baseline_return = float(baseline_metrics.get("total_return_pct") or 0.0)
    spy_ret = (
        baseline_return - float(baseline_metrics["vs_spy_pct"])
        if baseline_metrics.get("vs_spy_pct") is not None
        else None
    )
    qqq_ret = (
        baseline_return - float(baseline_metrics["vs_qqq_pct"])
        if baseline_metrics.get("vs_qqq_pct") is not None
        else None
    )
    risk = _event_risk(event_trades)
    return {
        "expected_value_score": round(expected_value, 4)
        if expected_value is not None
        else None,
        "sharpe_daily": sharpe,
        "total_pnl": round(total_pnl, 2),
        "total_return_pct": round(total_return, 4),
        "max_drawdown_pct": _max_drawdown(combined_curve),
        "win_rate": round((baseline_wins + event_wins) / trade_count, 4)
        if trade_count
        else None,
        "trade_count": trade_count,
        "signals_generated": baseline_metrics.get("signals_generated"),
        "signals_survived": baseline_metrics.get("signals_survived"),
        "survival_rate": baseline_metrics.get("survival_rate"),
        "vs_spy_pct": round(total_return - float(spy_ret), 4)
        if spy_ret is not None
        else None,
        "vs_qqq_pct": round(total_return - float(qqq_ret), 4)
        if qqq_ret is not None
        else None,
        "winning_trades": baseline_wins + event_wins,
        "baseline_stack_trade_count": baseline_trade_count,
        "broad_market_event_trade_count": len(event_trades),
        "broad_market_event_pnl": round(
            sum(float(trade.get("pnl") or 0.0) for trade in event_trades),
            2,
        ),
        "broad_market_event_worst_trade_pct": risk["worst_trade_pct"],
        "broad_market_event_max_consecutive_losses": risk["max_consecutive_losses"],
        "broad_market_event_tail_loss_share": risk["tail_loss_share"],
        "combined_equity_curve": combined_curve,
    }


def _delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "expected_value_score",
        "sharpe_daily",
        "total_pnl",
        "total_return_pct",
        "max_drawdown_pct",
        "win_rate",
        "trade_count",
        "survival_rate",
    ]
    return {
        key: round(float(after.get(key) or 0.0) - float(before.get(key) or 0.0), 6)
        for key in keys
    }


def _aggregate(metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in metrics.values()),
            6,
        ),
        "total_pnl_sum": round(
            sum(float(row.get("total_pnl") or 0.0) for row in metrics.values()),
            2,
        ),
        "trade_count_sum": int(sum(int(row.get("trade_count") or 0) for row in metrics.values())),
        "signals_generated_sum": int(
            sum(int(row.get("signals_generated") or 0) for row in metrics.values())
        ),
        "signals_survived_sum": int(
            sum(int(row.get("signals_survived") or 0) for row in metrics.values())
        ),
        "max_drawdown_pct_max": round(
            max(float(row.get("max_drawdown_pct") or 0.0) for row in metrics.values()),
            6,
        ),
        "survival_rate_min": round(
            min(float(row.get("survival_rate") or 0.0) for row in metrics.values()),
            6,
        ),
    }


def _aggregate_delta(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    by_window = OrderedDict((label, _delta(before[label], after[label])) for label in WINDOWS)
    baseline_ev = sum(float(before[label]["expected_value_score"] or 0.0) for label in WINDOWS)
    after_ev = sum(float(after[label]["expected_value_score"] or 0.0) for label in WINDOWS)
    baseline_pnl = sum(float(before[label]["total_pnl"] or 0.0) for label in WINDOWS)
    after_pnl = sum(float(after[label]["total_pnl"] or 0.0) for label in WINDOWS)
    drawdown_delta = {
        label: round(
            float(after[label].get("max_drawdown_pct") or 0.0)
            - float(before[label].get("max_drawdown_pct") or 0.0),
            6,
        )
        for label in WINDOWS
    }
    return {
        "by_window": by_window,
        "baseline_ev_sum": round(baseline_ev, 6),
        "after_ev_sum": round(after_ev, 6),
        "aggregate_ev_delta": round(after_ev - baseline_ev, 6),
        "aggregate_ev_delta_pct": round((after_ev - baseline_ev) / baseline_ev, 6)
        if baseline_ev
        else None,
        "baseline_pnl_sum": round(baseline_pnl, 2),
        "after_pnl_sum": round(after_pnl, 2),
        "aggregate_pnl_delta": round(after_pnl - baseline_pnl, 2),
        "aggregate_pnl_delta_pct": round((after_pnl - baseline_pnl) / baseline_pnl, 6)
        if baseline_pnl
        else None,
        "windows_ev_improved": sum(
            1
            for label in WINDOWS
            if (after[label].get("expected_value_score") or 0)
            > (before[label].get("expected_value_score") or 0)
        ),
        "windows_ev_regressed": sum(
            1
            for label in WINDOWS
            if (after[label].get("expected_value_score") or 0)
            < (before[label].get("expected_value_score") or 0)
        ),
        "windows_pnl_improved": sum(
            1
            for label in WINDOWS
            if (after[label].get("total_pnl") or 0)
            > (before[label].get("total_pnl") or 0)
        ),
        "windows_pnl_regressed": sum(
            1
            for label in WINDOWS
            if (after[label].get("total_pnl") or 0)
            < (before[label].get("total_pnl") or 0)
        ),
        "by_window_max_drawdown_delta": drawdown_delta,
        "max_drawdown_worse_max": max(drawdown_delta.values()) if drawdown_delta else 0.0,
    }


def _trade_rows(trades: list[dict[str, Any]], limit: int = 50) -> list[dict[str, Any]]:
    rows = []
    for trade in sorted(trades, key=lambda row: (row["entry_date"], row["ticker"]))[:limit]:
        rows.append(
            {
                "ticker": trade["ticker"],
                "window": trade["window"],
                "profile": trade["profile"],
                "decision_date": trade["decision_date"],
                "entry_date": trade["entry_date"],
                "exit_date": trade["exit_date"],
                "pnl": trade["pnl"],
                "net_return_pct": trade["net_return_pct"],
                "rank": trade["rank"],
                "score": trade["score"],
                "ret20_excess_spy": trade["ret20_excess_spy"],
                "ret60": trade["ret60"],
                "volume_ratio_20": trade["volume_ratio_20"],
                "near_high_60": trade["near_high_60"],
            }
        )
    return rows


def _window_sleeve_summary(
    trades: list[dict[str, Any]],
    scout: dict[str, Any],
) -> dict[str, Any]:
    pnl = round(sum(float(row.get("pnl") or 0.0) for row in trades), 2)
    wins = sum(1 for row in trades if float(row.get("pnl") or 0.0) > 0)
    by_ticker: dict[str, dict[str, Any]] = {}
    for trade in trades:
        ticker = str(trade.get("ticker") or "").upper()
        rec = by_ticker.setdefault(
            ticker,
            {"trades": 0, "wins": 0, "losses": 0, "pnl": 0.0},
        )
        rec["trades"] += 1
        rec["wins"] += 1 if float(trade.get("pnl") or 0.0) > 0 else 0
        rec["losses"] += 1 if float(trade.get("pnl") or 0.0) <= 0 else 0
        rec["pnl"] += float(trade.get("pnl") or 0.0)
    for rec in by_ticker.values():
        rec["pnl"] = round(float(rec["pnl"]), 2)
        rec["win_rate"] = round(rec["wins"] / rec["trades"], 4) if rec["trades"] else None
    return {
        "trade_count": len(trades),
        "pnl": pnl,
        "win_rate": round(wins / len(trades), 4) if trades else None,
        "candidate_signal_days": scout["candidate_signal_days"],
        "candidate_signal_count": scout["candidate_signal_count"],
        "max_daily_candidate_count": scout["max_daily_candidate_count"],
        "single_ticker_positive_share": _single_ticker_positive_share(trades),
        "top5_positive_share": _top5_positive_share(trades),
        "event_risk": _event_risk(trades),
        "by_ticker": dict(sorted(by_ticker.items())),
        "sample_trades": _trade_rows(trades, limit=25),
    }


def _variant_payload(
    *,
    profile_name: str,
    profile: dict[str, Any],
    baseline_metrics: dict[str, dict[str, Any]],
    candidate_tickers: list[str],
    prices: dict[str, list[dict[str, Any]]],
    indexes: dict[str, dict[str, int]],
) -> dict[str, Any]:
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    sleeve: dict[str, dict[str, Any]] = OrderedDict()
    all_trades: list[dict[str, Any]] = []
    for label, spec in WINDOWS.items():
        scout = _simulate_window(
            label=label,
            profile_name=profile_name,
            profile=profile,
            candidate_tickers=candidate_tickers,
            prices=prices,
            indexes=indexes,
        )
        trades = scout["trades"]
        all_trades.extend(trades)
        event_curve = _event_equity_curve(
            trades=trades,
            prices=prices,
            start=spec["start"],
            end=spec["end"],
        )
        after_metrics[label] = _metrics_from_overlay(
            baseline_metrics=baseline_metrics[label],
            event_curve=event_curve,
            event_trades=trades,
        )
        sleeve[label] = _window_sleeve_summary(trades, scout)

    aggregate_delta = _aggregate_delta(baseline_metrics, after_metrics)
    selected_windows = sum(1 for row in sleeve.values() if row["trade_count"] > 0)
    single_share = _single_ticker_positive_share(all_trades)
    top5_share = _top5_positive_share(all_trades)
    sample_guard_passed = len(all_trades) >= MIN_SELECTED_TRADES
    window_guard_passed = selected_windows >= MIN_SELECTED_WINDOWS
    concentration_guard_passed = (
        (single_share is None or single_share <= MAX_SINGLE_TICKER_POSITIVE_SHARE)
        and (top5_share is None or top5_share <= MAX_TOP5_POSITIVE_SHARE)
    )
    drawdown_guard_passed = (
        aggregate_delta["max_drawdown_worse_max"] <= MAX_DRAWDOWN_WORSE
    )
    gate4_passed = bool(
        aggregate_delta["aggregate_ev_delta"] > 0
        and aggregate_delta["aggregate_pnl_delta"] > 0
        and aggregate_delta["windows_ev_improved"] >= MIN_EV_IMPROVED_WINDOWS
        and aggregate_delta["windows_ev_regressed"] == 0
        and aggregate_delta["windows_pnl_regressed"] == 0
        and sample_guard_passed
        and window_guard_passed
        and concentration_guard_passed
        and drawdown_guard_passed
    )
    return {
        "variant_name": profile_name,
        "variant_type": "broad_market_leadership_candidate_pool_profile",
        "profile": profile,
        "after_metrics": after_metrics,
        "delta_metrics": aggregate_delta,
        "broad_market_sleeve": sleeve,
        "selected_trade_count": len(all_trades),
        "selected_windows": selected_windows,
        "selected_ticker_count": len({row["ticker"] for row in all_trades}),
        "selected_pnl": round(sum(float(row.get("pnl") or 0.0) for row in all_trades), 2),
        "selected_win_rate": round(
            sum(1 for row in all_trades if float(row.get("pnl") or 0.0) > 0)
            / len(all_trades),
            4,
        )
        if all_trades
        else None,
        "single_ticker_positive_share": single_share,
        "top5_positive_share": top5_share,
        "event_risk": _event_risk(all_trades),
        "selected_trades_sample": _trade_rows(all_trades, limit=50),
        "gate4": {
            "passed": gate4_passed,
            "aggregate_ev_delta": aggregate_delta["aggregate_ev_delta"],
            "aggregate_pnl_delta": aggregate_delta["aggregate_pnl_delta"],
            "windows_ev_improved": aggregate_delta["windows_ev_improved"],
            "windows_ev_regressed": aggregate_delta["windows_ev_regressed"],
            "windows_pnl_improved": aggregate_delta["windows_pnl_improved"],
            "windows_pnl_regressed": aggregate_delta["windows_pnl_regressed"],
            "selected_trade_count": len(all_trades),
            "minimum_selected_trades": MIN_SELECTED_TRADES,
            "sample_guard_passed": sample_guard_passed,
            "selected_windows": selected_windows,
            "minimum_selected_windows": MIN_SELECTED_WINDOWS,
            "window_guard_passed": window_guard_passed,
            "single_ticker_positive_share": single_share,
            "max_single_ticker_positive_share": MAX_SINGLE_TICKER_POSITIVE_SHARE,
            "top5_positive_share": top5_share,
            "max_top5_positive_share": MAX_TOP5_POSITIVE_SHARE,
            "concentration_guard_passed": concentration_guard_passed,
            "max_drawdown_worse_max": aggregate_delta["max_drawdown_worse_max"],
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
            "drawdown_guard_passed": drawdown_guard_passed,
        },
    }


def _choose_best(rows: list[dict[str, Any]]) -> dict[str, Any]:
    passing = [row for row in rows if row["gate4"]["passed"]]
    if passing:
        return max(
            passing,
            key=lambda row: (
                row["gate4"]["aggregate_ev_delta"],
                row["gate4"]["aggregate_pnl_delta"],
                -row["gate4"]["max_drawdown_worse_max"],
                -row["profile"]["aggression_order"],
            ),
        )
    return max(
        rows,
        key=lambda row: (
            row["gate4"]["aggregate_ev_delta"],
            row["gate4"]["aggregate_pnl_delta"],
            row["gate4"]["windows_ev_improved"],
            -row["gate4"]["windows_ev_regressed"],
        ),
    )


def _sweep_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "variant_name": row["variant_name"],
            "passed": row["gate4"]["passed"],
            "description": row["profile"]["description"],
            "thresholds": {
                key: row["profile"][key]
                for key in (
                    "ret20_excess_spy_min",
                    "ret60_min",
                    "near_high_60_min",
                    "volume_ratio_20_min",
                )
            },
            "selected_trade_count": row["selected_trade_count"],
            "selected_windows": row["selected_windows"],
            "selected_ticker_count": row["selected_ticker_count"],
            "selected_pnl": row["selected_pnl"],
            "selected_win_rate": row["selected_win_rate"],
            "aggregate_ev_delta": row["gate4"]["aggregate_ev_delta"],
            "aggregate_pnl_delta": row["gate4"]["aggregate_pnl_delta"],
            "windows_ev_improved": row["gate4"]["windows_ev_improved"],
            "windows_ev_regressed": row["gate4"]["windows_ev_regressed"],
            "windows_pnl_regressed": row["gate4"]["windows_pnl_regressed"],
            "max_drawdown_worse_max": row["gate4"]["max_drawdown_worse_max"],
            "single_ticker_positive_share": row["single_ticker_positive_share"],
            "top5_positive_share": row["top5_positive_share"],
            "event_risk": row["event_risk"],
        }
        for row in rows
    ]


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Broad-Market Leadership Candidate-Pool Shadow",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Single causal variable: default-off broad-market leadership candidate-pool membership from the exp-20260519-030 OHLCV warehouse.",
        "",
        "## Sweep",
        "",
        "| Variant | Gate 4 | Trades | Tickers | dEV | dPnL | EV Improved | EV Regressed | Max DD Worse | Single Share | Top5 Share |",
        "|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        single = row["single_ticker_positive_share"]
        top5 = row["top5_positive_share"]
        lines.append(
            "| {variant} | {gate} | {trades} | {tickers} | {ev:+.4f} | ${pnl:+,.2f} | {wi} | {wr} | {dd:+.4%} | {single} | {top5} |".format(
                variant=row["variant_name"],
                gate="PASS" if row["passed"] else "FAIL",
                trades=row["selected_trade_count"],
                tickers=row["selected_ticker_count"],
                ev=float(row["aggregate_ev_delta"] or 0.0),
                pnl=float(row["aggregate_pnl_delta"] or 0.0),
                wi=row["windows_ev_improved"],
                wr=row["windows_ev_regressed"],
                dd=float(row["max_drawdown_worse_max"] or 0.0),
                single=f"{single:.2%}" if single is not None else "n/a",
                top5=f"{top5:.2%}" if top5 is not None else "n/a",
            )
        )
    selected = payload["selected_variant"]
    lines.extend(
        [
            "",
            "## Selected Profile",
            "",
            f"Selected variant: `{selected['variant_name']}`.",
            "",
            "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Broad Trades | Broad PnL |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        sleeve = payload["broad_market_sleeve"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {trades} | ${spnl:+,.2f} |".format(
                label=label,
                bev=float(before["expected_value_score"]),
                aev=float(after["expected_value_score"]),
                dev=float(delta["expected_value_score"]),
                bpnl=float(before["total_pnl"]),
                apnl=float(after["total_pnl"]),
                dpnl=float(delta["total_pnl"]),
                trades=sleeve["trade_count"],
                spnl=float(sleeve["pnl"]),
            )
        )
    lines.extend(
        [
            "",
            "## Production Impact",
            "",
            "```json",
            json.dumps(payload["production_impact"], indent=2, sort_keys=True),
            "```",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def _compact_metrics(metrics: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        label: {
            key: value
            for key, value in row.items()
            if key != "combined_equity_curve"
        }
        for label, row in metrics.items()
    }


def _experiment_log_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "changed_variable": payload["changed_variable"],
        "parameters": payload["parameters"],
        "date_range": payload["date_range"],
        "backtest_protocol": payload["backtest_protocol"],
        "before_metrics": _compact_metrics(payload["before_metrics"]),
        "after_metrics": _compact_metrics(payload["after_metrics"]),
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["total_pnl_delta"],
        "gate4": payload["gate4"],
        "decision": payload["decision"],
        "rejection_reason": payload["rejection_reason"],
        "next_evidence_needed": payload["next_evidence_needed"],
        "production_impact": payload["production_impact"],
        "related_files": payload["related_files"],
    }


def build_payload() -> dict[str, Any]:
    if not BASELINE_JSON.exists():
        raise RuntimeError(f"Missing baseline artifact: {_repo_rel(BASELINE_JSON)}")
    gate2 = _audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    baseline_payload = _json_load(BASELINE_JSON)
    baseline_metrics = baseline_payload["after_metrics"]
    if baseline_payload.get("decision") != "accepted_default_off_state_surface_rank_depth_score_volume_notional":
        raise RuntimeError(
            f"Unexpected baseline decision: {baseline_payload.get('decision')}"
        )
    universe_state = _load_tradeable_universe()
    tradeable_universe = set(universe_state["excluded_tradeable_universe"])
    warehouse = _warehouse_audit()
    candidate_universe = _candidate_universe(tradeable_universe)
    candidate_tickers = candidate_universe["tickers"]
    prices = _load_price_rows(candidate_tickers)
    indexes = _index_by_date(prices)

    missing_price_tickers = sorted(
        ticker for ticker in candidate_tickers if ticker not in prices
    )
    if missing_price_tickers:
        raise RuntimeError(f"Missing candidate OHLCV rows: {missing_price_tickers[:10]}")

    variants = [
        _variant_payload(
            profile_name=name,
            profile=profile,
            baseline_metrics=baseline_metrics,
            candidate_tickers=candidate_tickers,
            prices=prices,
            indexes=indexes,
        )
        for name, profile in LEADERSHIP_PROFILES.items()
    ]
    selected = _choose_best(variants)
    accepted = [row for row in variants if row["gate4"]["passed"]]
    decision = (
        "observed_promising_default_off_broad_market_leadership_candidate_pool"
        if accepted
        else "rejected_broad_market_leadership_candidate_pool_shadow"
    )
    status = "observed_only" if accepted else "rejected"
    interpretation = (
        "At least one broad-market leadership profile improved the accepted paper stack across the canonical three-window replay, but it remains default-off paper only until a shared production-visible paper adapter is added."
        if accepted
        else "No broad-market leadership profile cleared the canonical three-window replacement-value gate; do not promote this candidate-pool profile without new evidence."
    )

    before_metrics = baseline_metrics
    after_metrics = selected["after_metrics"]
    delta_metrics = selected["delta_metrics"]
    aggregate_before = _aggregate(before_metrics)
    aggregate_after = _aggregate(after_metrics)
    gate3 = {
        "signals_generated": {
            label: before_metrics[label].get("signals_generated") for label in WINDOWS
        },
        "signals_survived": {
            label: before_metrics[label].get("signals_survived") for label in WINDOWS
        },
        "survival_rate": {
            label: before_metrics[label].get("survival_rate") for label in WINDOWS
        },
        "survival_rate_min": aggregate_before["survival_rate_min"],
        "passed": aggregate_before["survival_rate_min"] >= 0.05,
        "note": "No new core filter was added; broad-market sleeve is default-off paper overlay only.",
    }
    gate1 = {
        "passed": True,
        "baseline_experiment_id": BASELINE_EXPERIMENT_ID,
        "baseline_artifact": _repo_rel(BASELINE_JSON),
        "standard_protocol": "docs/backtesting.md canonical three fixed windows",
        "before_aggregate": aggregate_before,
        "known_measurement_boundary": (
            "Broad-market overlay uses exp-20260519-030 warehouse and is "
            "restricted to all-window full-liquid names. It is not a live "
            "universe promotion."
        ),
    }
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
            "+00:00",
            "Z",
        ),
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": (
            "Non-core equities from the broad-market warehouse that show "
            "20-day relative strength versus SPY, positive 60-day trend, "
            "near-60-day-high price action, and volume confirmation may add "
            "default-off paper replacement value to the accepted event-enhanced "
            "trend/breakout stack."
        ),
        "alpha_hypothesis": {
            "category": "entry / candidate_pool",
            "playbook_alignment": (
                "Uses the playbook's default-off candidate-pool and all-market "
                "discovery direction after state-surface adjacent retunes and "
                "LLM soft-ranking were deprioritized by recent evidence."
            ),
            "why_now": (
                "exp-20260519-030 created enough all-window full-liquid warehouse "
                "coverage to test a real broad-market shadow instead of adding "
                "hand-picked noisy tickers."
            ),
        },
        "history_check": {
            "nearby_experiments": [
                {
                    "experiment_id": "exp-20260519-011",
                    "lesson": "governed non-core expansion was data-limited to cached augmented snapshots",
                },
                {
                    "experiment_id": "exp-20260519-030",
                    "lesson": "warehouse now has enough all-window full-liquid OHLCV rows for a paper scout",
                },
                {
                    "experiment_id": "exp-20260519-033",
                    "lesson": "latest accepted stack; avoid adjacent queue/score/volume state-surface retunes",
                },
            ],
            "anti_repeat": (
                "This is not a nearby state-surface scalar retune, SEC T+1 "
                "threshold retry, or sparse LLM soft-ranking experiment."
            ),
        },
        "change_type": "default_off_paper_candidate_pool",
        "changed_variable": "broad_market_leadership_candidate_pool_profile",
        "single_causal_variable": (
            "membership in a default-off paper sleeve selected from broad-market "
            "non-current-tradeable all-window full-liquid leadership candidates"
        ),
        "parameters": {
            "warehouse_experiment_id": WAREHOUSE_EXPERIMENT_ID,
            "baseline_experiment_id": BASELINE_EXPERIMENT_ID,
            "profiles": LEADERSHIP_PROFILES,
            "notional": PAPER_NOTIONAL,
            "max_active_positions": MAX_ACTIVE_POSITIONS,
            "daily_entry_slots": DAILY_ENTRY_SLOTS,
            "hold_days": HOLD_DAYS,
            "candidate_universe_definition": candidate_universe["source"],
            "candidate_count": candidate_universe["candidate_count"],
            "excluded_count": candidate_universe["excluded_count"],
            "locked_variables": [
                "core signal generation",
                "core entry filters",
                "core ranking",
                "core exits",
                "core sizing",
                "portfolio heat",
                "LLM/news decisions",
                "live/default orders",
                "accepted state-surface paper baseline",
            ],
            "acceptance": {
                "aggregate_ev_delta_gt": 0,
                "aggregate_pnl_delta_gt": 0,
                "min_ev_improved_windows": MIN_EV_IMPROVED_WINDOWS,
                "max_ev_regressed_windows": 0,
                "max_pnl_regressed_windows": 0,
                "minimum_selected_trades": MIN_SELECTED_TRADES,
                "minimum_selected_windows": MIN_SELECTED_WINDOWS,
                "max_drawdown_worse": MAX_DRAWDOWN_WORSE,
                "max_single_ticker_positive_share": MAX_SINGLE_TICKER_POSITIVE_SHARE,
                "max_top5_positive_share": MAX_TOP5_POSITIVE_SHARE,
            },
            "anti_js": "No JavaScript was used.",
        },
        "date_range": {label: {"start": row["start"], "end": row["end"]} for label, row in WINDOWS.items()},
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows; accepted "
            "exp-20260519-033 after_metrics baseline plus default-off "
            "broad-market paper overlay replay from exp-20260519-030 warehouse."
        ),
        "gate1": gate1,
        "gate2": gate2,
        "gate3": gate3,
        "gate4": selected["gate4"],
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": delta_metrics,
        "aggregate_before": aggregate_before,
        "aggregate_after": aggregate_after,
        "expected_value_score_delta": {
            label: delta_metrics["by_window"][label]["expected_value_score"]
            for label in WINDOWS
        },
        "total_pnl_delta": {
            label: delta_metrics["by_window"][label]["total_pnl"] for label in WINDOWS
        },
        "sweep_summary": _sweep_summary(variants),
        "selected_variant": {
            "variant_name": selected["variant_name"],
            "profile": selected["profile"],
            "gate4": selected["gate4"],
            "selected_trade_count": selected["selected_trade_count"],
            "selected_ticker_count": selected["selected_ticker_count"],
            "selected_windows": selected["selected_windows"],
            "selected_pnl": selected["selected_pnl"],
            "selected_win_rate": selected["selected_win_rate"],
            "single_ticker_positive_share": selected["single_ticker_positive_share"],
            "top5_positive_share": selected["top5_positive_share"],
            "event_risk": selected["event_risk"],
            "selected_trades_sample": selected["selected_trades_sample"],
        },
        "broad_market_sleeve": selected["broad_market_sleeve"],
        "candidate_universe": candidate_universe,
        "universe_state": universe_state,
        "warehouse_audit": warehouse,
        "llm_metrics": {
            "changed": False,
            "reason": "This run avoids sparse LLM soft-ranking and does not alter LLM prompts, boundaries, or decisions.",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "default_off_paper_only": True,
            "parity_test_added": False,
            "live_order_path_changed": False,
            "note": (
                "No core production behavior changed. A positive result is only "
                "a research lead until implemented through a shared default-off "
                "paper adapter visible to both backtest and production."
            ),
        },
        "protocol_answers": {
            "1_alpha_hypothesis": "entry/candidate_pool: broad-market relative-strength leaders may add default-off replacement value.",
            "2_past_similar_experiments": "exp-20260519-011 was data-limited; exp-20260519-030 created warehouse coverage; exp-20260519-033 is latest accepted baseline.",
            "3_single_variable": "Only the default-off broad-market leadership candidate-pool profile changes.",
            "4_acceptance": "Gate 4 requires positive aggregate EV/PnL, no EV/PnL regression windows, sufficient sample, concentration guard, and <=0.5pp max drawdown worsening.",
            "5_reproducibility": "Script, JSON artifact, log, ticket, markdown artifact, and docs JSONL entry identify data source, baseline, windows, parameters, and metrics.",
        },
        "interpretation": interpretation,
        "rejection_reason": None
        if accepted
        else "Best broad-market leadership profile failed one or more Gate 4 replacement-value constraints.",
        "next_evidence_needed": (
            "Add a shared default-off paper adapter and forward-paper audit before any promotion; monitor concentration and tail loss."
            if accepted
            else "Try a different candidate-pool alpha source such as event replacement value or sector/industry leadership, not a nearby threshold retry."
        ),
        "why_not_other_changes": [
            "LLM soft-ranking remains sparse and was not used.",
            "State-surface queue/score/volume adjacency was just accepted in exp-20260519-033 and should not be retuned immediately.",
            "SEC earnings-release T+1 strength was rejected in exp-20260519-032 without new semantic fields.",
            "This run uses warehouse coverage rather than adding noisy hand-picked tickers.",
        ],
        "known_risks": [
            "Warehouse is partial, though this replay restricts to all-window full-liquid rows.",
            "Broad-market sleeve is paper-only and lacks a shared production adapter.",
            "Candidate-pool profile is technical-only and does not yet include event semantics.",
        ],
        "component": "default_off_paper_candidate_pool",
        "related_files": {
            "script": _repo_rel(Path(__file__)),
            "output": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "ticket": _repo_rel(TICKET_JSON),
            "artifact": _repo_rel(ARTIFACT_MD),
            "experiment_log": _repo_rel(EXPERIMENT_LOG),
            "baseline": _repo_rel(BASELINE_JSON),
            "warehouse": _repo_rel(WAREHOUSE_SQLITE),
        },
    }
    return payload


def main() -> None:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "lane": payload["lane"],
        "status": payload["status"],
        "decision": payload["decision"],
        "hypothesis": payload["hypothesis"],
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "next_evidence_needed": payload["next_evidence_needed"],
        "related_files": payload["related_files"],
    }
    _write_json(TICKET_JSON, ticket)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG, _experiment_log_payload(payload))
    print(json.dumps(_safe(payload["sweep_summary"]), indent=2, sort_keys=True))
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "selected_variant": payload["selected_variant"]["variant_name"],
                "gate4": payload["gate4"],
                "aggregate_ev_delta": payload["delta_metrics"]["aggregate_ev_delta"],
                "aggregate_pnl_delta": payload["delta_metrics"]["aggregate_pnl_delta"],
                "output": payload["related_files"]["output"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
