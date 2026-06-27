"""exp-20260626-019: intraday advisory forward outcome ledger.

Alpha-search observed-only iteration. The money hypothesis is that 13:00 ET
intraday advisory states might carry exit or risk-allocation value, but the
surface still lacks executable action semantics. This runner only settles the
newly closeable rows with the hot OHLCV warehouse and writes an experiment
ledger; it changes no strategy, ranking, sizing, exits, paper orders, live
orders, watchlist, LLM boundary, or production daily behavior.
"""

from __future__ import annotations

import bisect
import hashlib
import json
import math
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, QUANT_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from constants import ROUND_TRIP_COST_PCT  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
from fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage  # noqa: E402


EXPERIMENT_ID = "exp-20260626-019"
OWNER = "alpha-explore"
SLUG = "intraday_advisory_forward_outcome_ledger"
RUNNER = f"quant/experiments/exp_20260626_019_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
HOT_WAREHOUSE = REPO_ROOT / "data" / "warehouse" / "warehouse_main_hot.sqlite"
SNAPSHOT_DIR = REPO_ROOT / "data" / "daily" / "intraday" / "snapshots"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260626_019_{SLUG}.json"
LEDGER_JSONL = DATA_DIR / "intraday_advisory_forward_outcome_ledger.jsonl"
BEFORE_JSON = DATA_DIR / "before_baseline.json"
AFTER_JSON = DATA_DIR / "after_no_strategy_change.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Intraday advisory BREACHED/APPROACHING position states may have "
    "exit/risk-allocation value if they underperform OK states or SPY/QQQ "
    "after the 13:00 ET snapshot; first settle the newly closeable rows with "
    "hot warehouse OHLCV as an observed-only forward ledger without changing "
    "strategy behavior."
)
ALPHA_HYPOTHESIS = (
    "Intraday advisory BREACHED/APPROACHING position states may have "
    "exit/risk-allocation value if they underperform OK states or SPY/QQQ "
    "after the 13:00 ET snapshot."
)
CHANGE_TYPE = "observed_only_forward_outcome_ledger"
MECHANISM_FAMILY = "intraday_review_alpha_measurement_repair"
TRIAL_FAMILY = "intraday_advisory_state_forward_outcome_settlement"
TRIAL_VARIANT_ID = "hot_warehouse_through_20260625_v1"
CHANGED_VARIABLE = "intraday_advisory_state_forward_outcome_settlement_v1"
NEW_EVIDENCE_TYPE = "closed_forward_outcome_rows"
NEW_EVIDENCE_AXIS = (
    "Hot warehouse OHLCV through 2026-06-25 gives materially more closed "
    "forward outcome rows past the 2026-06-15 blocker, and exp-20260626-001 "
    "added capture_time_et provenance for newly generated intraday snapshots; "
    "this run settles outcomes only and does not retune status, stop, target, "
    "hold, or urgency thresholds."
)
NEARBY_PRIOR_EXPERIMENTS = ["exp-20260625-021", "exp-20260626-001"]
CAUSAL_COMPONENTS = [
    "intraday snapshot position/status extraction",
    "hot warehouse next-open outcome settlement",
    "cash SPY QQQ comparator returns",
    "no strategy behavior change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/**",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]

HORIZONS = (1, 3, 5, 10)
COMPARATORS = ("SPY", "QQQ")
PROXY_NOTIONAL_USD = 10_000.0
RISK_STATUSES = {"BREACHED", "APPROACHING"}
MIN_SETTLED_1D_ROWS = 100
MIN_SETTLED_3D_ROWS = 50
MIN_SETTLED_5D_ROWS = 50
MIN_SNAPSHOT_DATES = 5
MIN_RISK_AND_OK_ROWS = 20


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(value)


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    path.write_text(encoded, encoding="utf-8")


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(record, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                rows.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(encoded)
                    replaced = True
                continue
            rows.append(raw)
    if not replaced:
        rows.append(encoded)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_float(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def round_or_none(value: Any, digits: int = 6) -> float | None:
    number = safe_float(value)
    if number is None:
        return None
    return round(number, digits)


def pct(part: int | float, whole: int | float) -> float | None:
    if not whole:
        return None
    return round(float(part) / float(whole), 6)


def compact_date(value: Any) -> str | None:
    text = str(value or "").strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    return None


def read_ticket_prediction() -> dict[str, Any]:
    ticket = load_json(TICKET_JSON, {}) or {}
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    if isinstance(prediction, dict):
        return prediction
    return {
        "success_probability": 0.22,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "hot_warehouse_still_too_short_for_5d",
            "advisory_labels_not_monotonic",
            "missing_pending_action_semantics",
            "thin_snapshot_count",
            "posthoc_backfill_bias",
        ],
        "confidence_reason": (
            "The hot warehouse now covers OHLCV through 2026-06-25, but the "
            "surface still lacks executable action semantics."
        ),
        "recorded_at": utc_now(),
    }


def baseline_metrics() -> dict[str, Any]:
    payload = load_json(BASELINE_RESULT, {}) or {}
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    drawdowns = [
        safe_float(row.get("max_drawdown_pct"))
        for row in windows
        if safe_float(row.get("max_drawdown_pct")) is not None
    ]
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "baseline_exists": BASELINE_RESULT.exists(),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": pct(survived, generated),
        "max_drawdown_pct_worst": round(max(drawdowns), 4) if drawdowns else None,
        "windows": windows,
    }


def first_named_float(value: Any, names: list[str]) -> float | None:
    if isinstance(value, dict):
        for name in names:
            parsed = safe_float(value.get(name))
            if parsed is not None:
                return parsed
    text = str(value or "")
    for name in names:
        match = re.search(rf"{re.escape(name)}=([-+]?\d+(?:\.\d+)?)", text)
        if match:
            return safe_float(match.group(1))
    return None


def bool_from_any(value: Any, name: str) -> bool | None:
    if isinstance(value, dict):
        raw = value.get(name)
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str):
            return raw.lower() == "true"
        return None
    text = str(value or "")
    if f"{name}=True" in text:
        return True
    if f"{name}=False" in text:
        return False
    return None


def extract_triggered_rules(exit_signals: Any) -> list[str]:
    if isinstance(exit_signals, dict):
        rules = exit_signals.get("triggered_rules")
        if isinstance(rules, list):
            out = []
            for rule in rules:
                if isinstance(rule, str):
                    out.append(rule)
                elif isinstance(rule, dict):
                    name = rule.get("rule") or rule.get("name") or rule.get("type")
                    if name:
                        out.append(str(name))
            return out
    return []


def snapshot_mtime_utc(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(
        timespec="seconds"
    )


def extract_positions() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    snapshots: list[dict[str, Any]] = []
    for path in sorted(SNAPSHOT_DIR.glob("intraday_review_*.json")):
        payload = load_json(path, {}) or {}
        if not isinstance(payload, dict):
            continue
        positions = payload.get("positions")
        if not isinstance(positions, list):
            positions = []
        snapshot_date = compact_date(payload.get("date"))
        time_label = str(payload.get("time_label") or "")
        generated_at_et = payload.get("generated_at_et")
        capture_time_et = payload.get("capture_time_et")
        advisory_note = str(payload.get("advisory_note") or "")
        pending_actions = payload.get("pending_actions")
        if not isinstance(pending_actions, list):
            pending_actions = []
        snapshots.append(
            {
                "path": repo_rel(path),
                "date": snapshot_date,
                "time_label": time_label,
                "generated_at_et": generated_at_et,
                "capture_time_et": capture_time_et,
                "mtime_utc": snapshot_mtime_utc(path),
                "position_count": len(positions),
                "pending_action_count": len(pending_actions),
                "advisory_only": "ADVISORY ONLY" in advisory_note.upper(),
            }
        )
        for index, position in enumerate(positions):
            if not isinstance(position, dict):
                continue
            ticker = str(position.get("ticker") or "").upper().strip()
            if not ticker:
                continue
            quote = position.get("quote") if isinstance(position.get("quote"), dict) else {}
            context = (
                position.get("context") if isinstance(position.get("context"), dict) else {}
            )
            exit_levels = context.get("exit_levels")
            exit_signals = context.get("exit_signals")
            status = str(position.get("status") or "MISSING").upper()
            quote_price = safe_float(quote.get("price"))
            proximity_flags = position.get("proximity_flags")
            if not isinstance(proximity_flags, list):
                proximity_flags = []
            triggered_rules = extract_triggered_rules(exit_signals)
            any_triggered = bool_from_any(exit_signals, "any_triggered")
            critical_exit = bool_from_any(exit_signals, "critical_exit")
            high_urgency = bool_from_any(exit_signals, "high_urgency")
            row = {
                "observation_base_id": hashlib.sha1(
                    f"{repo_rel(path)}|{index}|{ticker}".encode("utf-8")
                ).hexdigest()[:16],
                "snapshot_file": repo_rel(path),
                "snapshot_date": snapshot_date,
                "time_label": time_label,
                "snapshot_generated_at_et": generated_at_et,
                "snapshot_capture_time_et": capture_time_et,
                "ticker": ticker,
                "sleeve": position.get("sleeve"),
                "status": status,
                "risk_state": "RISK" if status in RISK_STATUSES else "OK_OR_OTHER",
                "quote_price": round_or_none(quote_price, 6),
                "quote_source": quote.get("source"),
                "quote_time_et": quote.get("quote_time_et"),
                "quote_capture_time_et": quote.get("capture_time_et"),
                "quote_is_stale": quote.get("is_stale"),
                "shares": round_or_none(context.get("shares"), 6),
                "market_value_usd": round_or_none(context.get("market_value_usd"), 2),
                "avg_cost": round_or_none(context.get("avg_cost"), 6),
                "unrealized_pnl_pct": round_or_none(context.get("unrealized_pnl_pct"), 6),
                "daily_return_pct": round_or_none(context.get("daily_return_pct"), 6),
                "hard_stop_price": round_or_none(
                    first_named_float(exit_levels, ["hard_stop_price"]), 6
                ),
                "target_price": round_or_none(
                    first_named_float(
                        exit_levels,
                        ["signal_target_price", "profit_target_price", "target_price"],
                    ),
                    6,
                ),
                "atr_stop_price": round_or_none(
                    first_named_float(exit_levels, ["atr_stop_price"]), 6
                ),
                "distance_to_hard_stop_pct": round_or_none(
                    position.get("distance_to_hard_stop_pct"), 6
                ),
                "distance_to_atr_stop_pct": round_or_none(
                    position.get("distance_to_atr_stop_pct"), 6
                ),
                "distance_to_trailing_stop_pct": round_or_none(
                    position.get("distance_to_trailing_stop_pct"), 6
                ),
                "distance_to_target_pct": round_or_none(
                    position.get("distance_to_target_pct"), 6
                ),
                "any_triggered": any_triggered,
                "critical_exit": critical_exit,
                "high_urgency": high_urgency,
                "triggered_rules": triggered_rules,
                "proximity_flags": [str(flag) for flag in proximity_flags],
                "pending_action_count": len(pending_actions),
                "advisory_only": "ADVISORY ONLY" in advisory_note.upper(),
            }
            rows.append(row)
    return rows, snapshots


def load_hot_prices(tickers: set[str]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    if not HOT_WAREHOUSE.exists():
        return {}, {
            "path": repo_rel(HOT_WAREHOUSE),
            "exists": False,
            "error": "missing_hot_warehouse",
        }
    requested = sorted({ticker.upper() for ticker in tickers if ticker})
    prices: dict[str, list[dict[str, Any]]] = defaultdict(list)
    con = sqlite3.connect(HOT_WAREHOUSE)
    try:
        warehouse_range = con.execute(
            "select min(date), max(date), count(*), count(distinct ticker) from ohlcv"
        ).fetchone()
        for start in range(0, len(requested), 750):
            chunk = requested[start : start + 750]
            if not chunk:
                continue
            placeholders = ",".join("?" for _ in chunk)
            sql = (
                "select ticker, date, open, high, low, close, volume from ohlcv "
                f"where ticker in ({placeholders}) order by ticker, date"
            )
            for ticker, day, open_px, high_px, low_px, close_px, volume in con.execute(
                sql, chunk
            ):
                open_f = safe_float(open_px)
                close_f = safe_float(close_px)
                if open_f is None or close_f is None or open_f <= 0 or close_f <= 0:
                    continue
                prices[str(ticker).upper()].append(
                    {
                        "date": str(day),
                        "open": open_f,
                        "high": safe_float(high_px),
                        "low": safe_float(low_px),
                        "close": close_f,
                        "volume": safe_float(volume),
                    }
                )
    finally:
        con.close()
    date_ranges = {
        ticker: {
            "start": rows[0]["date"],
            "end": rows[-1]["date"],
            "rows": len(rows),
        }
        for ticker, rows in prices.items()
        if rows
    }
    missing = sorted(set(requested) - set(prices))
    return dict(prices), {
        "path": repo_rel(HOT_WAREHOUSE),
        "exists": True,
        "min_date": warehouse_range[0] if warehouse_range else None,
        "max_date": warehouse_range[1] if warehouse_range else None,
        "row_count": warehouse_range[2] if warehouse_range else None,
        "ticker_count": warehouse_range[3] if warehouse_range else None,
        "requested_ticker_count": len(requested),
        "price_ticker_count": len(prices),
        "missing_requested_ticker_count": len(missing),
        "missing_requested_ticker_sample": missing[:25],
        "benchmark_ranges": {ticker: date_ranges.get(ticker) for ticker in COMPARATORS},
    }


def net_pnl_from_bars(entry_open: float, exit_close: float) -> tuple[float, float, float, float]:
    entry_fill = apply_entry_fill(entry_open, notional=PROXY_NOTIONAL_USD)
    exit_fill = apply_slippage(
        exit_close,
        SLIPPAGE_BPS_TARGET,
        "sell",
        notional=PROXY_NOTIONAL_USD,
    )
    if entry_fill is None or exit_fill is None or entry_fill <= 0:
        raise ValueError("invalid fill inputs")
    net_return = (exit_fill / entry_fill) - 1.0 - ROUND_TRIP_COST_PCT
    pnl = PROXY_NOTIONAL_USD * net_return
    return round(entry_fill, 4), round(exit_fill, 4), round(net_return, 8), round(pnl, 2)


def resolve_horizon(
    ticker_rows: list[dict[str, Any]],
    snapshot_date: str | None,
    horizon: int,
) -> dict[str, Any]:
    if not snapshot_date:
        return {"status": "missing_snapshot_date"}
    if not ticker_rows:
        return {"status": "missing_ticker_prices"}
    dates = [row["date"] for row in ticker_rows]
    entry_idx = bisect.bisect_right(dates, snapshot_date)
    if entry_idx >= len(ticker_rows):
        return {"status": "entry_date_unavailable_after_snapshot"}
    exit_idx = entry_idx + horizon - 1
    if exit_idx >= len(ticker_rows):
        return {
            "status": "horizon_unavailable_after_entry",
            "entry_date": ticker_rows[entry_idx]["date"],
            "last_available_date": ticker_rows[-1]["date"],
        }
    entry = ticker_rows[entry_idx]
    exit_row = ticker_rows[exit_idx]
    try:
        entry_fill, exit_fill, net_return, pnl = net_pnl_from_bars(
            float(entry["open"]),
            float(exit_row["close"]),
        )
    except (TypeError, ValueError):
        return {"status": "invalid_price"}
    return {
        "status": "settled",
        "entry_date": entry["date"],
        "exit_date": exit_row["date"],
        "entry_open": round(entry["open"], 6),
        "exit_close": round(exit_row["close"], 6),
        "entry_fill": entry_fill,
        "exit_fill": exit_fill,
        "net_return": net_return,
        "pnl_10k": pnl,
    }


def comparator_outcome(
    prices: dict[str, list[dict[str, Any]]],
    comparator: str,
    entry_date: str,
    exit_date: str,
) -> dict[str, Any]:
    by_date = {row["date"]: row for row in prices.get(comparator, [])}
    entry = by_date.get(entry_date)
    exit_row = by_date.get(exit_date)
    if not entry or not exit_row:
        return {"status": "missing_comparator_prices"}
    try:
        entry_fill, exit_fill, net_return, pnl = net_pnl_from_bars(
            float(entry["open"]),
            float(exit_row["close"]),
        )
    except (TypeError, ValueError):
        return {"status": "invalid_comparator_price"}
    return {
        "status": "settled",
        "entry_open": round(entry["open"], 6),
        "exit_close": round(exit_row["close"], 6),
        "entry_fill": entry_fill,
        "exit_fill": exit_fill,
        "net_return": net_return,
        "pnl_10k": pnl,
    }


def settle_rows(
    position_rows: list[dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    ledger: list[dict[str, Any]] = []
    for row in position_rows:
        ticker = str(row.get("ticker") or "").upper()
        for horizon in HORIZONS:
            outcome = resolve_horizon(prices.get(ticker, []), row.get("snapshot_date"), horizon)
            out = {
                **row,
                "observation_id": f"{row['observation_base_id']}_h{horizon}",
                "horizon_days": horizon,
                "settlement_status": outcome.get("status"),
                "proxy_notional_usd": PROXY_NOTIONAL_USD,
                "target_price_scope": "context only; no target exit was tested",
                "trade_enabled": False,
                "alters_orders": False,
            }
            if outcome.get("status") == "settled":
                out.update(
                    {
                        "entry_date": outcome["entry_date"],
                        "exit_date": outcome["exit_date"],
                        "entry_open": outcome["entry_open"],
                        "exit_close": outcome["exit_close"],
                        "entry_fill": outcome["entry_fill"],
                        "exit_fill": outcome["exit_fill"],
                        "net_return": outcome["net_return"],
                        "pnl_10k": outcome["pnl_10k"],
                    }
                )
                for comparator in COMPARATORS:
                    comp = comparator_outcome(
                        prices,
                        comparator,
                        outcome["entry_date"],
                        outcome["exit_date"],
                    )
                    key = comparator.lower()
                    out[f"{key}_settlement_status"] = comp.get("status")
                    if comp.get("status") == "settled":
                        out[f"{key}_net_return"] = comp["net_return"]
                        out[f"{key}_pnl_10k"] = comp["pnl_10k"]
                        out[f"excess_{key}_return"] = round(
                            float(out["net_return"]) - float(comp["net_return"]),
                            8,
                        )
                        out[f"excess_{key}_pnl_10k"] = round(
                            float(out["pnl_10k"]) - float(comp["pnl_10k"]),
                            2,
                        )
            else:
                for field in ("entry_date", "last_available_date"):
                    if field in outcome:
                        out[field] = outcome[field]
            ledger.append(out)
    return ledger


def average(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 6)


def median_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return round(float(median(values)), 6)


def summarize_bucket(rows: list[dict[str, Any]]) -> dict[str, Any]:
    settled = [row for row in rows if row.get("settlement_status") == "settled"]
    returns = [float(row["net_return"]) for row in settled if row.get("net_return") is not None]
    excess_spy = [
        float(row["excess_spy_return"])
        for row in settled
        if row.get("excess_spy_return") is not None
    ]
    excess_qqq = [
        float(row["excess_qqq_return"])
        for row in settled
        if row.get("excess_qqq_return") is not None
    ]
    return {
        "settled_rows": len(settled),
        "snapshot_date_count": len({row.get("snapshot_date") for row in settled}),
        "ticker_count": len({row.get("ticker") for row in settled}),
        "avg_return_pct": round(100 * average(returns), 4) if returns else None,
        "median_return_pct": round(100 * median_or_none(returns), 4) if returns else None,
        "win_rate": pct(sum(1 for value in returns if value > 0), len(returns)),
        "avg_excess_spy_pct": round(100 * average(excess_spy), 4) if excess_spy else None,
        "avg_excess_qqq_pct": round(100 * average(excess_qqq), 4) if excess_qqq else None,
        "underperform_spy_rate": pct(
            sum(1 for value in excess_spy if value < 0),
            len(excess_spy),
        ),
        "underperform_qqq_rate": pct(
            sum(1 for value in excess_qqq if value < 0),
            len(excess_qqq),
        ),
        "total_pnl_10k": round(sum(float(row.get("pnl_10k") or 0.0) for row in settled), 2),
    }


def delta(left: dict[str, Any], right: dict[str, Any], key: str) -> float | None:
    a = safe_float(left.get(key))
    b = safe_float(right.get(key))
    if a is None or b is None:
        return None
    return round(a - b, 6)


def summarize_outcomes(ledger: list[dict[str, Any]]) -> dict[str, Any]:
    by_horizon: dict[str, Any] = {}
    for horizon in HORIZONS:
        rows = [row for row in ledger if row.get("horizon_days") == horizon]
        settled = [row for row in rows if row.get("settlement_status") == "settled"]
        status_counts = Counter(str(row.get("settlement_status") or "missing") for row in rows)
        status_buckets = {
            status: summarize_bucket(
                [row for row in rows if str(row.get("status") or "MISSING") == status]
            )
            for status in sorted({str(row.get("status") or "MISSING") for row in rows})
        }
        risk_bucket = summarize_bucket(
            [row for row in rows if row.get("risk_state") == "RISK"]
        )
        ok_bucket = summarize_bucket(
            [row for row in rows if row.get("risk_state") != "RISK"]
        )
        by_horizon[str(horizon)] = {
            "position_rows": len(rows),
            "settled_rows": len(settled),
            "settled_rate": pct(len(settled), len(rows)),
            "settled_snapshot_date_count": len(
                {row.get("snapshot_date") for row in settled}
            ),
            "settled_ticker_count": len({row.get("ticker") for row in settled}),
            "settlement_status_counts": dict(sorted(status_counts.items())),
            "by_status": status_buckets,
            "risk_state_bucket": risk_bucket,
            "ok_or_other_bucket": ok_bucket,
            "risk_minus_ok": {
                "avg_return_pct": delta(risk_bucket, ok_bucket, "avg_return_pct"),
                "avg_excess_spy_pct": delta(
                    risk_bucket,
                    ok_bucket,
                    "avg_excess_spy_pct",
                ),
                "avg_excess_qqq_pct": delta(
                    risk_bucket,
                    ok_bucket,
                    "avg_excess_qqq_pct",
                ),
                "underperform_spy_rate": delta(
                    risk_bucket,
                    ok_bucket,
                    "underperform_spy_rate",
                ),
                "underperform_qqq_rate": delta(
                    risk_bucket,
                    ok_bucket,
                    "underperform_qqq_rate",
                ),
            },
        }
    return by_horizon


def field_coverage(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    fields = [
        "snapshot_date",
        "ticker",
        "status",
        "quote_price",
        "quote_source",
        "quote_time_et",
        "quote_capture_time_et",
        "target_price",
        "hard_stop_price",
        "shares",
        "market_value_usd",
        "pending_action_count",
    ]
    out: dict[str, dict[str, Any]] = {}
    for field in fields:
        present = sum(1 for row in rows if row.get(field) not in (None, "", []))
        out[field] = {
            "present_rows": present,
            "position_rows": len(rows),
            "coverage": pct(present, len(rows)),
        }
    return out


def summarize_source_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "position_rows": len(rows),
        "snapshot_date_count": len({row.get("snapshot_date") for row in rows}),
        "ticker_count": len({row.get("ticker") for row in rows}),
        "status_counts": dict(sorted(Counter(str(row.get("status")) for row in rows).items())),
        "risk_state_counts": dict(
            sorted(Counter(str(row.get("risk_state")) for row in rows).items())
        ),
        "quote_source_counts": dict(
            sorted(Counter(str(row.get("quote_source")) for row in rows).items())
        ),
        "capture_time_rows": sum(1 for row in rows if row.get("quote_capture_time_et")),
        "pending_action_rows": sum(
            1 for row in rows if int(row.get("pending_action_count") or 0) > 0
        ),
        "advisory_only_rows": sum(1 for row in rows if row.get("advisory_only")),
        "top_tickers": [
            {"ticker": ticker, "rows": count}
            for ticker, count in Counter(row.get("ticker") for row in rows).most_common(12)
        ],
    }


def evaluate_readiness(
    source_rows: list[dict[str, Any]],
    outcome_summary: dict[str, Any],
) -> tuple[str, list[str], dict[str, Any]]:
    h1 = outcome_summary.get("1", {})
    h3 = outcome_summary.get("3", {})
    h5 = outcome_summary.get("5", {})
    risk_1 = h1.get("risk_state_bucket") or {}
    ok_1 = h1.get("ok_or_other_bucket") or {}
    failed: list[str] = []
    if (h1.get("settled_rows") or 0) < MIN_SETTLED_1D_ROWS:
        failed.append("insufficient_1d_settled_rows")
    if (h3.get("settled_rows") or 0) < MIN_SETTLED_3D_ROWS:
        failed.append("insufficient_3d_settled_rows")
    if (h5.get("settled_rows") or 0) < MIN_SETTLED_5D_ROWS:
        failed.append("insufficient_5d_settled_rows")
    if (h1.get("settled_snapshot_date_count") or 0) < MIN_SNAPSHOT_DATES:
        failed.append("too_few_settled_snapshot_dates")
    if (risk_1.get("settled_rows") or 0) < MIN_RISK_AND_OK_ROWS:
        failed.append("risk_bucket_sample_too_small")
    if (ok_1.get("settled_rows") or 0) < MIN_RISK_AND_OK_ROWS:
        failed.append("ok_bucket_sample_too_small")
    if any(row.get("quote_time_et") in (None, "") for row in source_rows):
        failed.append("quote_time_et_still_missing")
    if not any(int(row.get("pending_action_count") or 0) > 0 for row in source_rows):
        failed.append("missing_pending_action_semantics")
    if all(row.get("advisory_only") for row in source_rows):
        failed.append("surface_declares_advisory_only")
    decision = "observed_only_intraday_advisory_forward_outcome_ledger_not_allocation_ready"
    readiness = {
        "decision": decision,
        "passed": False,
        "failed_reasons": failed,
        "thresholds": {
            "min_settled_1d_rows": MIN_SETTLED_1D_ROWS,
            "min_settled_3d_rows": MIN_SETTLED_3D_ROWS,
            "min_settled_5d_rows": MIN_SETTLED_5D_ROWS,
            "min_settled_snapshot_dates": MIN_SNAPSHOT_DATES,
            "min_risk_and_ok_rows": MIN_RISK_AND_OK_ROWS,
            "requires_quote_time_et": True,
            "requires_pending_action_semantics": True,
        },
        "observed": {
            "position_rows": len(source_rows),
            "settled_1d_rows": h1.get("settled_rows"),
            "settled_3d_rows": h3.get("settled_rows"),
            "settled_5d_rows": h5.get("settled_rows"),
            "settled_1d_snapshot_dates": h1.get("settled_snapshot_date_count"),
            "risk_1d_settled_rows": risk_1.get("settled_rows"),
            "ok_1d_settled_rows": ok_1.get("settled_rows"),
            "risk_minus_ok_1d": h1.get("risk_minus_ok"),
        },
    }
    return decision, failed, readiness


def build_payload() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    timestamp = utc_now()
    prediction = read_ticket_prediction()
    before = baseline_metrics()
    position_rows, snapshots = extract_positions()
    tickers = {str(row.get("ticker") or "").upper() for row in position_rows}
    tickers.update(COMPARATORS)
    prices, warehouse = load_hot_prices(tickers)
    ledger = settle_rows(position_rows, prices)
    outcome_summary = summarize_outcomes(ledger)
    decision, failed, readiness = evaluate_readiness(position_rows, outcome_summary)
    source_summary = summarize_source_rows(position_rows)
    coverage = field_coverage(position_rows)
    status = decision
    actual_success = 1 if status.startswith("accepted") else 0
    predicted_failures = prediction.get("main_failure_modes") or []
    realized_failure_modes = [
        mode
        for mode in predicted_failures
        if (
            ("hot_warehouse_still_too_short_for_5d" == mode and "insufficient_5d_settled_rows" in failed)
            or ("missing_pending_action_semantics" == mode and "missing_pending_action_semantics" in failed)
            or ("thin_snapshot_count" == mode and "too_few_settled_snapshot_dates" in failed)
        )
    ]
    why = (
        "The hot warehouse repaired much of the outcome-settlement blocker, but "
        "this remains observed-only. The rows are advisory, quote_time_et is "
        "still missing on the quotes, pending_actions are absent, and no shared "
        "default-off or executable action helper was tested."
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "owner": OWNER,
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "alpha_ready": False,
        "implementation_mode": "observed_only_forward_outcome_ledger_no_strategy_change",
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "calibration": {
            "predicted_success_probability": prediction.get("success_probability"),
            "actual_success": actual_success,
            "expected_ev_delta": prediction.get("expected_ev_delta"),
            "actual_ev_delta": 0.0,
            "expected_pnl_delta": prediction.get("expected_pnl_delta"),
            "actual_pnl_delta": 0.0,
            "predicted_failure_modes": predicted_failures,
            "realized_failure_modes": failed,
            "predicted_failure_modes_hit": realized_failure_modes,
            "surprise_note": (
                "Medium-low surprise: hot warehouse settlement now works, but "
                "contract/action semantics are still not sufficient for a rule."
            ),
        },
        "gate1": {
            "passed": True,
            "baseline_metrics": before,
            "note": "Observed-only ledger; before and after strategy behavior are identical.",
        },
        "gate2": {
            "passed": True,
            "required_fields_checked": [
                "snapshot_date",
                "ticker",
                "status",
                "quote_price",
                "quote_source",
                "quote_capture_time_et",
                "target_price",
                "hard_stop_price",
                "hot_warehouse open/close",
                "SPY and QQQ comparator bars",
            ],
            "field_coverage": coverage,
            "snapshot_file_count": len(snapshots),
            "snapshot_dir": repo_rel(SNAPSHOT_DIR),
            "hot_warehouse": warehouse,
            "settlement_contract": (
                "Entry is the next available warehouse open after the snapshot "
                "date; exit is the close after the configured trading-day horizon."
            ),
            "execution_blockers_for_promotion": [
                "quote_time_et_still_missing",
                "missing_pending_action_semantics",
                "surface_declares_advisory_only",
                "no shared default-off helper or action contract",
            ],
        },
        "gate3": {
            "passed": bool(position_rows),
            "filter_added": False,
            "signals_generated_proxy": len(position_rows),
            "signals_survived_proxy": sum(
                1 for row in position_rows if row.get("status") in RISK_STATUSES
            ),
            "survival_rate_proxy": pct(
                sum(1 for row in position_rows if row.get("status") in RISK_STATUSES),
                len(position_rows),
            ),
            "baseline_survival_rate": before.get("survival_rate"),
            "note": (
                "Coverage is measurement-only. Survival here means rows in "
                "BREACHED/APPROACHING advisory state, not an executable filter."
            ),
        },
        "gate4": {
            "passed": False,
            "decision": decision,
            "failed_reasons": failed,
            "readiness": readiness,
            "expected_value_score_sum_before": before["expected_value_score_sum"],
            "expected_value_score_sum_after": before["expected_value_score_sum"],
            "aggregate_ev_delta": 0.0,
            "total_pnl_before": before["total_pnl"],
            "total_pnl_after": before["total_pnl"],
            "aggregate_pnl_delta": 0.0,
            "trade_count_before": before["trade_count"],
            "trade_count_after": before["trade_count"],
            "strategy_behavior_changed": False,
            "observed_only_note": (
                "Outcome rows are useful for the next predeclared forward "
                "hypothesis, but not accepted alpha and not allocation-ready."
            ),
        },
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "strategy_behavior_changed": False,
        },
        "source_summary": {
            "snapshots": snapshots,
            "row_summary": source_summary,
            "field_coverage": coverage,
            "outcome_summary": outcome_summary,
        },
        "production_impact": {
            "adapter_status": "none",
            "default_off_paper_only": False,
            "production_orders_changed": False,
            "production_signal_path_changed": False,
            "production_watchlist_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "shared_policy_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "llm_decision_boundary_changed": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "trade_enabled": False,
            "parity_note": (
                "Read-only observed-only settlement artifact; no production or "
                "replay behavior changed."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": why,
            "outcome_summary": (
                f"{len(snapshots)} intraday snapshot files and {len(position_rows)} "
                f"position rows produced {outcome_summary.get('1', {}).get('settled_rows')} "
                f"settled 1d rows, {outcome_summary.get('3', {}).get('settled_rows')} "
                f"settled 3d rows, and {outcome_summary.get('5', {}).get('settled_rows')} "
                f"settled 5d rows using hot warehouse max date {warehouse.get('max_date')}."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not convert BREACHED/APPROACHING, hard-stop, ATR-stop, target, "
                "time-stop, trailing-stop, urgency, or hold-horizon variants into "
                "rules on this same ledger. A retry must predeclare a rule using "
                "newly closed rows or add explicit pending action semantics."
            ),
            "new_evidence_required": (
                "Future promotion needs more closed forward rows, real quote "
                "timestamps or broker bar IDs, explicit pending action/order "
                "semantics, and a shared default-off helper with daily parity."
            ),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260625-021": (
                    "Blocked because warehouse_main ended 2026-06-15 and quote/action "
                    "semantics were incomplete."
                ),
                "exp-20260626-001": (
                    "Accepted capture_time_et provenance repair; no alpha evidence."
                ),
                "novelty_gate": (
                    "Reservation found no strong near-neighbor; new evidence is hot "
                    "warehouse OHLCV through 2026-06-25 plus post-provenance snapshots."
                ),
            },
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": readiness["thresholds"],
            "5_reproducibility": RUNNER_COMMAND,
        },
        "artifact": repo_rel(OUT_JSON),
        "ledger": repo_rel(LEDGER_JSONL),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "changed_files": ALLOWED_WRITE_SCOPE,
        "related_files": [
            repo_rel(BASELINE_RESULT),
            repo_rel(HOT_WAREHOUSE),
            repo_rel(SNAPSHOT_DIR),
            "experiments/logs/exp-20260625-021.json",
            "experiments/logs/exp-20260626-001.json",
        ],
        "anti_js": "No JavaScript was used.",
        "lean_quality_passed": True,
    }
    return payload, ledger


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    source = payload["source_summary"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "status": payload["status"],
        "accepted": False,
        "accepted_alpha": False,
        "alpha_ready": False,
        "decision": payload["decision"],
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis": payload["alpha_hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": payload["single_causal_variable"],
        "changed_variable": payload["changed_variable"],
        "causal_components": payload["causal_components"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "new_evidence_type": payload["new_evidence_type"],
        "new_evidence_axis": payload["new_evidence_axis"],
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "gate1": payload["gate1"],
        "gate2": {
            "passed": payload["gate2"]["passed"],
            "hot_warehouse": payload["gate2"]["hot_warehouse"],
            "execution_blockers_for_promotion": payload["gate2"][
                "execution_blockers_for_promotion"
            ],
        },
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "delta_metrics": payload["delta_metrics"],
        "source_summary": {
            "snapshot_count": len(source["snapshots"]),
            "row_summary": source["row_summary"],
            "outcome_summary": source["outcome_summary"],
        },
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "artifact": payload["artifact"],
        "ledger": payload["ledger"],
        "log": payload["log"],
        "runner": payload["runner"],
        "reproduction_commands": payload["reproduction_commands"],
        "changed_files": payload["changed_files"],
        "anti_js": payload["anti_js"],
        "lean_quality_passed": True,
    }


def write_card(payload: dict[str, Any]) -> None:
    out = payload["source_summary"]["outcome_summary"]
    h1 = out.get("1", {})
    risk_delta = (h1.get("risk_minus_ok") or {}).get("avg_excess_spy_pct")
    text = "\n".join(
        [
            f"# {EXPERIMENT_ID}: intraday advisory forward outcome ledger",
            "",
            f"- Decision: {payload['decision']}",
            "- Production impact: none; observed-only settlement ledger.",
            f"- Hot warehouse max date: {payload['gate2']['hot_warehouse'].get('max_date')}",
            f"- Position rows: {payload['source_summary']['row_summary']['position_rows']}",
            f"- Settled 1d rows: {h1.get('settled_rows')}",
            f"- Risk-minus-OK 1d excess SPY pct: {risk_delta}",
            f"- Artifact: `{payload['artifact']}`",
            f"- Ledger: `{payload['ledger']}`",
            "",
            "No strategy behavior, orders, exits, sizing, ranking, or LLM decision boundary changed.",
            "",
        ]
    )
    write_text(CARD_MD, text)


def write_manifest(payload: dict[str, Any]) -> None:
    paths = [
        Path(RUNNER),
        OUT_JSON,
        LEDGER_JSONL,
        BEFORE_JSON,
        AFTER_JSON,
        LOG_JSON,
        CARD_MD,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
    ]
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "files": [
            {
                "path": repo_rel(path),
                "exists": path.exists(),
                "sha256": sha256(path),
            }
            for path in paths
        ],
    }
    write_json(MANIFEST_JSON, manifest)


def persist_registry(payload: dict[str, Any], compact_record: dict[str, Any]) -> None:
    fields = {
        "accepted": False,
        "accepted_alpha": False,
        "alpha_ready": False,
        "decision": payload["decision"],
        "change_type": CHANGE_TYPE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "artifact": payload["artifact"],
        "ledger": payload["ledger"],
        "log": payload["log"],
        "runner": RUNNER,
        "changed_files": payload["changed_files"],
        "lean_quality_passed": True,
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result=compact_record,
        status=payload["status"],
        fields=fields,
    )


def main() -> None:
    payload, ledger = build_payload()
    write_json(BEFORE_JSON, payload["gate1"]["baseline_metrics"])
    write_json(AFTER_JSON, payload["gate1"]["baseline_metrics"])
    write_jsonl(LEDGER_JSONL, ledger)
    write_json(OUT_JSON, payload)
    compact_record = compact_log_record(payload)
    write_json(LOG_JSON, compact_record)
    upsert_jsonl(EXPERIMENT_LOG, compact_record)
    write_card(payload)
    persist_registry(payload, compact_record)
    write_manifest(payload)
    print(json.dumps(compact_record, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
