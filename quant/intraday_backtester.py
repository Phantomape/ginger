"""Forward counterfactual backtester for finalized intraday triage decisions.

This is a separate advisory measurement surface.  It never changes orders,
positions, EOD signals, or the canonical daily backtester.  Finalized decision
rows are immutable inputs; dated outcome ledgers and scorecards are
regenerable measurements as future 5-minute bars become available.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
import hashlib
import json
import math
import os
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo

import pandas as pd

try:
    from data_paths import DATA_ROOT
    from intraday_moomoo import _history_pages
    from moomoo_open_positions import (
        _redirect_moomoo_sdk_appdata,
        _restore_moomoo_sdk_appdata,
    )
except ImportError:  # pragma: no cover - package-style imports
    from quant.data_paths import DATA_ROOT
    from quant.intraday_moomoo import _history_pages
    from quant.moomoo_open_positions import (
        _redirect_moomoo_sdk_appdata,
        _restore_moomoo_sdk_appdata,
    )


SCHEMA_VERSION = 1
OUTCOME_RULE_VERSION = "intraday_triage_counterfactual_outcome_v1"
EXECUTION_RULE_VERSION = "intraday_triage_next_5m_execution_v1"
AGGREGATION_RULE_VERSION = "intraday_triage_latest_pre_execution_cohort_v1"
HORIZONS = ("h1", "rth_close", "next_close", "d3_close")
NO_ADJUSTMENT_ACTIONS = frozenset({"NO_TRADE", "WAIT", "HOLD_ONLY"})
LONG_ACTIONS = frozenset({"ADD_SMALL", "OPEN_SMALL"})
SHORT_EXPOSURE_ACTIONS = frozenset({"REDUCE_RISK"})


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _round(value: Any, digits: int = 6) -> float | None:
    number = _number(value)
    return round(number, digits) if number is not None else None


def _date_tag(value: str | date | datetime | None) -> str:
    if value is None:
        return datetime.now(ZoneInfo("America/New_York")).strftime("%Y%m%d")
    if isinstance(value, datetime):
        return value.strftime("%Y%m%d")
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    text = str(value).strip()[:10].replace("-", "")
    if len(text) != 8 or not text.isdigit():
        raise ValueError(f"invalid as-of date: {value!r}")
    return text


def _parse_et_timestamp(value: Any) -> pd.Timestamp | None:
    text = str(value or "").strip().replace(" ET", "")
    if not text:
        return None
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return None
    return pd.Timestamp(parsed).tz_localize(None)


def _repo_relative(path: Path, data_root: Path) -> str:
    try:
        return path.resolve().relative_to(data_root.parent.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _observation_id(source_file: str, row: Mapping[str, Any]) -> str:
    raw = "|".join((
        source_file,
        str(row.get("timestamp_et") or ""),
        str(row.get("ticker") or "").upper(),
        str(row.get("action_label") or "").upper(),
    ))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def load_finalized_decisions(
    data_dir: str | Path | None = None,
    *,
    through_date: str | date | datetime | None = None,
) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]]]:
    """Load immutable finalized decision rows and preserve source provenance."""
    root = Path(data_dir or DATA_ROOT)
    through = _date_tag(through_date)
    decision_dir = root / "daily" / "intraday" / "decisions"
    rows: list[dict[str, Any]] = []
    source_files: list[str] = []
    skipped: list[dict[str, Any]] = []
    for path in sorted(decision_dir.glob("intraday_triage_*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            skipped.append({"file": str(path), "reason": f"read_error:{exc}"})
            continue
        if payload.get("status") != "finalized_discretionary_forward_decision":
            skipped.append({"file": str(path), "reason": "not_finalized"})
            continue
        rel = _repo_relative(path, root)
        accepted = 0
        for raw in payload.get("rows") or []:
            if not isinstance(raw, dict):
                continue
            ts = _parse_et_timestamp(raw.get("timestamp_et"))
            ticker = str(raw.get("ticker") or "").upper().strip()
            if ts is None or not ticker:
                skipped.append({"file": rel, "ticker": ticker, "reason": "missing_identity"})
                continue
            if ts.strftime("%Y%m%d") > through:
                continue
            row = dict(raw)
            row["ticker"] = ticker
            row["source_decision_file"] = rel
            row["observation_id"] = _observation_id(rel, row)
            row["decision_date"] = ts.strftime("%Y-%m-%d")
            row["decision_timestamp"] = ts.isoformat(sep=" ")
            row["batch_finalized_at_et"] = payload.get("finalized_at_et")
            row["portfolio_summary"] = payload.get("portfolio_summary")
            rows.append(row)
            accepted += 1
        if accepted:
            source_files.append(rel)

    rows.sort(key=lambda row: (
        str(row.get("decision_timestamp") or ""),
        str(row.get("ticker") or ""),
        str(row.get("observation_id") or ""),
    ))
    first_by_ticker_day: dict[tuple[str, str], str] = {}
    for row in rows:
        key = (str(row["decision_date"]), str(row["ticker"]))
        first_by_ticker_day.setdefault(key, str(row["observation_id"]))
    for row in rows:
        key = (str(row["decision_date"]), str(row["ticker"]))
        row["primary_ticker_day_decision"] = (
            first_by_ticker_day[key] == row["observation_id"]
        )
    return rows, source_files, skipped


def _normalize_bars(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if isinstance(raw, pd.DataFrame):
        records = raw.to_dict("records")
    else:
        records = list(raw)
    rows: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, Mapping):
            continue
        ts = _parse_et_timestamp(record.get("time_key") or record.get("timestamp"))
        open_ = _number(record.get("open"))
        high = _number(record.get("high"))
        low = _number(record.get("low"))
        close = _number(record.get("close"))
        if ts is None or any(value is None for value in (open_, high, low, close)):
            continue
        if not (pd.Timestamp(ts).time() >= pd.Timestamp("09:30").time()
                and pd.Timestamp(ts).time() < pd.Timestamp("16:00").time()):
            continue
        rows.append({
            "time": ts,
            "time_key": ts.isoformat(sep=" "),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
        })
    rows.sort(key=lambda row: row["time"])
    return rows


def fetch_opend_history(
    tickers: Iterable[str],
    *,
    start_date: str,
    end_date: str,
    host: str = "127.0.0.1",
    port: int = 11111,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Fetch split-adjusted RTH 5-minute history for outcome settlement."""
    requested = sorted({str(t).upper().strip() for t in tickers if t})
    bars: dict[str, list[dict[str, Any]]] = {}
    errors: dict[str, str] = {}
    if not requested:
        return bars, {"status": "empty", "requested_tickers": 0, "errors": {}}
    redirect_sdk_logs = not os.environ.get("GINGER_MOOMOO_USE_SYSTEM_APPDATA")
    previous_appdata = None
    redirected = False
    try:
        if redirect_sdk_logs:
            previous_appdata = _redirect_moomoo_sdk_appdata()
            redirected = True
        from moomoo import AuType, KLType, OpenQuoteContext, Session
    except Exception as exc:  # pragma: no cover - local SDK dependency
        return bars, {
            "status": "unavailable",
            "requested_tickers": len(requested),
            "errors": {"sdk": str(exc)},
        }
    finally:
        if redirected:
            _restore_moomoo_sdk_appdata(previous_appdata)

    context = None
    try:
        context = OpenQuoteContext(host=host, port=port)
        for ticker in requested:
            frame, error = _history_pages(
                context,
                code=f"US.{ticker}",
                start=start_date,
                end=end_date,
                ktype=KLType.K_5M,
                autype=AuType.QFQ,
                extended_time=False,
                session=Session.RTH,
            )
            bars[ticker] = _normalize_bars(frame)
            if error:
                errors[ticker] = error
    except Exception as exc:  # pragma: no cover - live connection failure
        errors["connection"] = str(exc)
    finally:
        if context is not None:
            try:
                context.close()
            except Exception:
                pass
    returned = sum(1 for rows in bars.values() if rows)
    status = "ok" if returned == len(requested) and not errors else (
        "partial" if returned else "unavailable"
    )
    return bars, {
        "status": status,
        "source": "moomoo_opend_request_history_kline_5m_rth_qfq",
        "requested_tickers": len(requested),
        "returned_tickers": returned,
        "returned_bars": sum(len(rows) for rows in bars.values()),
        "start_date": start_date,
        "end_date": end_date,
        "errors": errors,
    }


def _execution_bar(rows: Sequence[Mapping[str, Any]], decision_ts: pd.Timestamp):
    return next((row for row in rows if row["time"] > decision_ts), None)


def _session_rows(rows: Sequence[Mapping[str, Any]]) -> dict[date, list[Mapping[str, Any]]]:
    sessions: dict[date, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        sessions[pd.Timestamp(row["time"]).date()].append(row)
    return dict(sessions)


def _horizon_bar(
    rows: Sequence[Mapping[str, Any]],
    execution: Mapping[str, Any],
    horizon: str,
) -> Mapping[str, Any] | None:
    execution_ts = pd.Timestamp(execution["time"])
    sessions = _session_rows(rows)
    session_dates = sorted(sessions)
    execution_date = execution_ts.date()
    if execution_date not in sessions:
        return None
    session_index = session_dates.index(execution_date)
    if horizon == "h1":
        threshold = execution_ts + pd.Timedelta(hours=1)
        return next((
            row for row in sessions[execution_date]
            if pd.Timestamp(row["time"]) >= threshold
        ), None)
    if horizon == "rth_close":
        return sessions[execution_date][-1]
    offset = 1 if horizon == "next_close" else 3
    target_index = session_index + offset
    if target_index >= len(session_dates):
        return None
    return sessions[session_dates[target_index]][-1]


def _bars_between(
    rows: Sequence[Mapping[str, Any]],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> list[Mapping[str, Any]]:
    return [
        row for row in rows
        if start <= pd.Timestamp(row["time"]) <= end
    ]


def _add_exit(
    path: Sequence[Mapping[str, Any]],
    horizon_bar: Mapping[str, Any],
    invalidation: float | None,
) -> tuple[float, str, str]:
    if invalidation is not None and invalidation > 0:
        for bar in path:
            if _number(bar.get("low")) is not None and float(bar["low"]) <= invalidation:
                fill = min(float(bar["open"]), invalidation)
                return fill, str(bar["time_key"]), "invalidation_stop"
    return float(horizon_bar["close"]), str(horizon_bar["time_key"]), "fixed_horizon"


def _action_fraction(row: Mapping[str, Any], action: str) -> float:
    contract = row.get("paper_execution") or row.get("paper_execution_contract") or {}
    if action in LONG_ACTIONS:
        return _number(
            contract.get("max_add_fraction_existing_position")
            or contract.get("counterfactual_add_fraction_existing_position")
        ) or 0.0
    if action in SHORT_EXPOSURE_ACTIONS:
        return _number(contract.get("reduce_fraction_existing_position")) or 0.0
    return 0.0


def _action_notional(row: Mapping[str, Any], action: str) -> float | None:
    contract = row.get("paper_execution") or row.get("paper_execution_contract") or {}
    position_value = _number(contract.get("position_market_value_at_decision"))
    fraction = _action_fraction(row, action)
    if position_value is None:
        return None
    return position_value * fraction


def _cost_bps(row: Mapping[str, Any], action: str) -> float:
    contract = row.get("paper_execution") or row.get("paper_execution_contract") or {}
    if action in LONG_ACTIONS:
        return _number(contract.get("round_trip_cost_bps")) or 10.0
    if action in SHORT_EXPOSURE_ACTIONS:
        return _number(contract.get("one_way_cost_bps")) or 5.0
    return 0.0


def _simulate_action(
    row: Mapping[str, Any],
    action: str,
    *,
    entry_price: float,
    horizon_price: float,
    path: Sequence[Mapping[str, Any]],
    horizon_bar: Mapping[str, Any],
) -> dict[str, Any]:
    action = str(action or "").upper()
    notional = _action_notional(row, action) or 0.0
    cost_bps = _cost_bps(row, action)
    invalidation = _number(row.get("invalidation_level"))
    exit_price = horizon_price
    exit_time = str(horizon_bar["time_key"])
    exit_reason = "fixed_horizon"
    if action in LONG_ACTIONS:
        exit_price, exit_time, exit_reason = _add_exit(path, horizon_bar, invalidation)
        gross_return = exit_price / entry_price - 1.0
        net_return = gross_return - cost_bps / 10_000.0
    elif action in SHORT_EXPOSURE_ACTIONS:
        gross_return = -(horizon_price / entry_price - 1.0)
        net_return = gross_return - cost_bps / 10_000.0
    else:
        gross_return = 0.0
        net_return = 0.0
    return {
        "action": action,
        "fraction_existing_position": round(_action_fraction(row, action), 6),
        "paper_notional_usd": round(notional, 2),
        "cost_bps": round(cost_bps, 4),
        "gross_return_bps": round(gross_return * 10_000.0, 4),
        "net_return_bps": round(net_return * 10_000.0, 4),
        "paper_pnl_usd": round(notional * net_return, 4),
        "exit_price": round(exit_price, 6),
        "exit_time": exit_time,
        "exit_reason": exit_reason,
    }


def _counterfactual_add_row(row: Mapping[str, Any]) -> dict[str, Any]:
    copied = dict(row)
    contract = dict(row.get("paper_execution") or row.get("paper_execution_contract") or {})
    fraction = _number(contract.get("counterfactual_add_fraction_existing_position"))
    if fraction is None:
        fraction = _number(contract.get("max_add_fraction_existing_position")) or 0.10
    contract["max_add_fraction_existing_position"] = fraction
    copied["paper_execution"] = contract
    return copied


def _wait_trigger_result(
    row: Mapping[str, Any],
    ticker_rows: Sequence[Mapping[str, Any]],
    *,
    decision_ts: pd.Timestamp,
    horizon_bar: Mapping[str, Any],
) -> dict[str, Any]:
    condition = row.get("entry_condition") or {}
    level = _number(condition.get("confirmation_level"))
    if level is None:
        return {"status": "no_confirmation_level"}
    candidates = [
        bar for bar in ticker_rows
        if pd.Timestamp(bar["time"]) > decision_ts
        and pd.Timestamp(bar["time"]) <= pd.Timestamp(horizon_bar["time"])
    ]
    trigger_index = next((
        index for index, bar in enumerate(candidates)
        if index + 1 < len(candidates) and float(bar["close"]) >= level
    ), None)
    if trigger_index is None:
        return {"status": "not_triggered", "confirmation_level": round(level, 6)}
    if trigger_index + 1 >= len(candidates):
        return {"status": "triggered_no_next_bar", "confirmation_level": round(level, 6)}
    entry = candidates[trigger_index + 1]
    entry_ts = pd.Timestamp(entry["time"])
    path = _bars_between(ticker_rows, entry_ts, pd.Timestamp(horizon_bar["time"]))
    simulated = _simulate_action(
        _counterfactual_add_row(row),
        "ADD_SMALL",
        entry_price=float(entry["open"]),
        horizon_price=float(horizon_bar["close"]),
        path=path,
        horizon_bar=horizon_bar,
    )
    return {
        "status": "closed",
        "confirmation_level": round(level, 6),
        "trigger_bar_time": str(candidates[trigger_index]["time_key"]),
        "entry_time": str(entry["time_key"]),
        "entry_price": round(float(entry["open"]), 6),
        **simulated,
    }


def _proxy_return(
    rows: Sequence[Mapping[str, Any]],
    *,
    decision_ts: pd.Timestamp,
    target_time: pd.Timestamp,
) -> float | None:
    entry = _execution_bar(rows, decision_ts)
    if entry is None:
        return None
    eligible = [row for row in rows if pd.Timestamp(row["time"]) <= target_time]
    if not eligible:
        return None
    exit_bar = eligible[-1]
    exit_time = pd.Timestamp(exit_bar["time"])
    if exit_time.date() != target_time.date():
        return None
    if target_time - exit_time > pd.Timedelta(minutes=10):
        return None
    return float(exit_bar["close"]) / float(entry["open"]) - 1.0


def build_intraday_outcomes(
    decisions: Sequence[Mapping[str, Any]],
    bars_by_ticker: Mapping[str, Any],
    *,
    as_of_date: str,
) -> list[dict[str, Any]]:
    as_of_end = pd.Timestamp(as_of_date).normalize() + pd.Timedelta(days=1)
    bars = {
        str(ticker).upper(): [
            row for row in _normalize_bars(raw)
            if pd.Timestamp(row["time"]) < as_of_end
        ]
        for ticker, raw in bars_by_ticker.items()
    }
    outcomes: list[dict[str, Any]] = []
    for decision in decisions:
        ticker = str(decision.get("ticker") or "").upper()
        decision_ts = _parse_et_timestamp(
            decision.get("decision_timestamp") or decision.get("timestamp_et")
        )
        ticker_rows = bars.get(ticker) or []
        final_action = str(decision.get("action_label") or "").upper()
        default_action = str(
            decision.get("machine_default_action")
            or decision.get("action_label")
            or "WAIT"
        ).upper()
        contract = decision.get("paper_execution") or decision.get(
            "paper_execution_contract"
        ) or {}
        position_value = _number(contract.get("position_market_value_at_decision"))
        base = {
            "schema_version": SCHEMA_VERSION,
            "record_type": "intraday_triage_outcome",
            "outcome_rule_version": OUTCOME_RULE_VERSION,
            "execution_rule_version": EXECUTION_RULE_VERSION,
            "observation_id": decision.get("observation_id"),
            "source_decision_file": decision.get("source_decision_file"),
            "ticker": ticker,
            "decision_date": decision.get("decision_date"),
            "decision_timestamp": decision.get("decision_timestamp"),
            "primary_ticker_day_decision": bool(
                decision.get("primary_ticker_day_decision")
            ),
            "market_phase": decision.get("market_phase"),
            "final_action": final_action,
            "machine_default_action": default_action,
            "underlying": decision.get("underlying"),
            "sector_proxy": decision.get("sector_proxy"),
            "market_proxy": decision.get("market_proxy"),
            "confidence": decision.get("confidence"),
            "position_market_value_at_decision": _round(position_value, 2),
            "as_of_date": as_of_date,
            "trade_enabled": False,
            "strategy_behavior_changed": False,
        }
        if decision_ts is None:
            for horizon in HORIZONS:
                outcomes.append({**base, "horizon": horizon, "status": "invalid_decision_time"})
            continue
        execution = _execution_bar(ticker_rows, decision_ts)
        if execution is None:
            for horizon in HORIZONS:
                outcomes.append({**base, "horizon": horizon, "status": "pending_execution_bar"})
            continue
        entry_price = float(execution["open"])
        entry_ts = pd.Timestamp(execution["time"])
        for horizon in HORIZONS:
            horizon_bar = _horizon_bar(ticker_rows, execution, horizon)
            if horizon_bar is None:
                outcomes.append({
                    **base,
                    "horizon": horizon,
                    "status": "pending_horizon_bar",
                    "execution_time": str(execution["time_key"]),
                    "execution_price": round(entry_price, 6),
                })
                continue
            if position_value is None or position_value <= 0:
                outcomes.append({
                    **base,
                    "horizon": horizon,
                    "status": "missing_position_value",
                    "execution_time": str(execution["time_key"]),
                    "execution_price": round(entry_price, 6),
                    "horizon_time": str(horizon_bar["time_key"]),
                    "horizon_price": round(float(horizon_bar["close"]), 6),
                })
                continue
            horizon_ts = pd.Timestamp(horizon_bar["time"])
            horizon_price = float(horizon_bar["close"])
            path = _bars_between(ticker_rows, entry_ts, horizon_ts)
            final_result = _simulate_action(
                decision,
                final_action,
                entry_price=entry_price,
                horizon_price=horizon_price,
                path=path,
                horizon_bar=horizon_bar,
            )
            default_result = _simulate_action(
                decision,
                default_action,
                entry_price=entry_price,
                horizon_price=horizon_price,
                path=path,
                horizon_bar=horizon_bar,
            )
            always_add_result = _simulate_action(
                _counterfactual_add_row(decision),
                "ADD_SMALL",
                entry_price=entry_price,
                horizon_price=horizon_price,
                path=path,
                horizon_bar=horizon_bar,
            )
            incremental_pnl = float(final_result["paper_pnl_usd"])
            semantic_lift = incremental_pnl - float(
                default_result["paper_pnl_usd"]
            )
            final_vs_always_add = incremental_pnl - float(
                always_add_result["paper_pnl_usd"]
            )
            normalization = (
                10_000.0 / position_value
                if position_value is not None and position_value > 0
                else None
            )
            ticker_return = horizon_price / entry_price - 1.0
            highs = [_number(bar.get("high")) for bar in path]
            lows = [_number(bar.get("low")) for bar in path]
            valid_highs = [value for value in highs if value is not None]
            valid_lows = [value for value in lows if value is not None]
            mfe = max(valid_highs) / entry_price - 1.0 if valid_highs else None
            mae = min(valid_lows) / entry_price - 1.0 if valid_lows else None
            proxy_payload: dict[str, Any] = {}
            for label in ("underlying", "sector_proxy", "market_proxy"):
                proxy = str(decision.get(label) or "").upper()
                proxy_ret = _proxy_return(
                    bars.get(proxy) or [],
                    decision_ts=decision_ts,
                    target_time=horizon_ts,
                ) if proxy else None
                proxy_payload[f"{label}_return_bps"] = (
                    round(proxy_ret * 10_000.0, 4) if proxy_ret is not None else None
                )
                proxy_payload[f"ticker_excess_vs_{label}_bps"] = (
                    round((ticker_return - proxy_ret) * 10_000.0, 4)
                    if proxy_ret is not None else None
                )
            outcomes.append({
                **base,
                "horizon": horizon,
                "status": "closed",
                "execution_time": str(execution["time_key"]),
                "execution_price": round(entry_price, 6),
                "horizon_time": str(horizon_bar["time_key"]),
                "horizon_price": round(horizon_price, 6),
                "ticker_return_bps": round(ticker_return * 10_000.0, 4),
                "mfe_bps": round(mfe * 10_000.0, 4) if mfe is not None else None,
                "mae_bps": round(mae * 10_000.0, 4) if mae is not None else None,
                "final_result": final_result,
                "machine_default_result": default_result,
                "always_add_result": always_add_result,
                "incremental_pnl_vs_no_adjustment_usd": round(incremental_pnl, 4),
                "semantic_lift_vs_machine_default_usd": round(semantic_lift, 4),
                "final_vs_always_add_usd": round(final_vs_always_add, 4),
                "incremental_return_on_position_bps": (
                    round(incremental_pnl * normalization, 4)
                    if normalization is not None else None
                ),
                "semantic_lift_on_position_bps": (
                    round(semantic_lift * normalization, 4)
                    if normalization is not None else None
                ),
                "final_vs_always_add_on_position_bps": (
                    round(final_vs_always_add * normalization, 4)
                    if normalization is not None else None
                ),
                "wait_trigger_result": _wait_trigger_result(
                    decision,
                    ticker_rows,
                    decision_ts=decision_ts,
                    horizon_bar=horizon_bar,
                ) if final_action == "WAIT" else {"status": "not_applicable"},
                **proxy_payload,
            })
    outcomes.sort(key=lambda row: (
        str(row.get("decision_timestamp") or ""),
        str(row.get("ticker") or ""),
        HORIZONS.index(str(row.get("horizon"))) if row.get("horizon") in HORIZONS else 99,
    ))
    return outcomes


def _summary_stats(values: Sequence[float]) -> dict[str, Any]:
    clean = [float(value) for value in values if _number(value) is not None]
    return {
        "count": len(clean),
        "mean": round(mean(clean), 6) if clean else None,
        "median": round(median(clean), 6) if clean else None,
        "positive_rate": round(sum(value > 0 for value in clean) / len(clean), 6)
        if clean else None,
        "sum": round(sum(clean), 6) if clean else 0.0,
    }


def _daily_curve(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    daily: dict[str, float] = defaultdict(float)
    daily_base: dict[str, float] = defaultdict(float)
    for row in rows:
        day = str(row.get("decision_date"))
        daily[day] += float(
            row.get("incremental_pnl_vs_no_adjustment_usd") or 0.0
        )
        daily_base[day] += float(
            row.get("position_market_value_at_decision") or 0.0
        )
    cumulative = 0.0
    cumulative_bps = 0.0
    high_water = 0.0
    high_water_bps = 0.0
    max_drawdown = 0.0
    max_drawdown_bps = 0.0
    curve = []
    for day in sorted(daily):
        cumulative += daily[day]
        daily_return_bps = (
            daily[day] / daily_base[day] * 10_000.0
            if daily_base[day] > 0 else 0.0
        )
        cumulative_bps += daily_return_bps
        high_water = max(high_water, cumulative)
        high_water_bps = max(high_water_bps, cumulative_bps)
        drawdown = cumulative - high_water
        drawdown_bps = cumulative_bps - high_water_bps
        max_drawdown = min(max_drawdown, drawdown)
        max_drawdown_bps = min(max_drawdown_bps, drawdown_bps)
        curve.append({
            "date": day,
            "position_value_base_usd": round(daily_base[day], 2),
            "daily_pnl_usd": round(daily[day], 4),
            "daily_incremental_return_bps": round(daily_return_bps, 4),
            "cumulative_pnl_usd": round(cumulative, 4),
            "cumulative_incremental_return_bps": round(cumulative_bps, 4),
            "drawdown_usd": round(drawdown, 4),
            "drawdown_bps": round(drawdown_bps, 4),
        })
    return {
        "days": len(curve),
        "total_pnl_usd": round(cumulative, 4),
        "cumulative_incremental_return_bps": round(cumulative_bps, 4),
        "max_drawdown_usd": round(max_drawdown, 4),
        "max_drawdown_bps": round(max_drawdown_bps, 4),
        "curve": curve,
    }


def select_effective_economic_outcomes(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[list[Mapping[str, Any]], dict[str, Any]]:
    """Select one attributable decision for each executable economic cohort.

    Finalized snapshots are immutable and remain in the raw outcome ledger.  If
    multiple primary ticker-day decisions ultimately map to the same ticker,
    execution timestamp, and horizon (for example, repeated weekend reviews
    that can only execute on Monday), only the latest decision available before
    that execution is an independent policy observation.  Rows without an
    execution timestamp are kept separate because their eventual cohort is not
    yet known.
    """
    buckets: dict[tuple[str, ...], list[tuple[int, Mapping[str, Any]]]] = defaultdict(list)
    for index, row in enumerate(rows):
        execution_time = str(row.get("execution_time") or "").strip()
        horizon = str(row.get("horizon") or "").strip()
        ticker = str(row.get("ticker") or "").upper().strip()
        if execution_time and ticker:
            key = ("execution", ticker, execution_time, horizon)
        else:
            observation_id = str(row.get("observation_id") or f"row-{index}")
            key = ("observation", observation_id, horizon, str(index))
        buckets[key].append((index, row))

    selected: list[tuple[int, Mapping[str, Any]]] = []
    duplicate_groups = 0
    duplicate_rows_excluded = 0
    for group in buckets.values():
        if len(group) > 1:
            duplicate_groups += 1
            duplicate_rows_excluded += len(group) - 1
        selected.append(max(
            group,
            key=lambda item: (
                str(item[1].get("decision_timestamp") or ""),
                str(item[1].get("observation_id") or ""),
                item[0],
            ),
        ))
    selected.sort(key=lambda item: (
        str(item[1].get("decision_timestamp") or ""),
        str(item[1].get("ticker") or ""),
        HORIZONS.index(str(item[1].get("horizon")))
        if item[1].get("horizon") in HORIZONS else 99,
        item[0],
    ))
    effective = [row for _, row in selected]
    return effective, {
        "aggregation_rule_version": AGGREGATION_RULE_VERSION,
        "raw_rows": len(rows),
        "effective_rows": len(effective),
        "duplicate_economic_cohorts": duplicate_groups,
        "duplicate_rows_excluded": duplicate_rows_excluded,
    }


def build_scorecard(
    outcomes: Sequence[Mapping[str, Any]],
    *,
    decisions: Sequence[Mapping[str, Any]],
    source_files: Sequence[str],
    skipped_sources: Sequence[Mapping[str, Any]],
    as_of_date: str,
    price_source: Mapping[str, Any],
) -> dict[str, Any]:
    primary = [row for row in outcomes if row.get("primary_ticker_day_decision")]
    horizon_summary: dict[str, Any] = {}
    effective_by_horizon: dict[str, list[Mapping[str, Any]]] = {}
    for horizon in HORIZONS:
        raw_rows = [row for row in primary if row.get("horizon") == horizon]
        rows, cohort_diagnostics = select_effective_economic_outcomes(raw_rows)
        effective_by_horizon[horizon] = rows
        raw_closed = [row for row in raw_rows if row.get("status") == "closed"]
        closed = [row for row in rows if row.get("status") == "closed"]
        horizon_summary[horizon] = {
            "rows": len(rows),
            "raw_rows": len(raw_rows),
            "closed": len(closed),
            "raw_closed": len(raw_closed),
            "pending": len(rows) - len(closed),
            "duplicate_economic_cohorts": cohort_diagnostics[
                "duplicate_economic_cohorts"
            ],
            "duplicate_rows_excluded": cohort_diagnostics[
                "duplicate_rows_excluded"
            ],
            "action_counts": dict(Counter(row.get("final_action") for row in closed)),
            "semantic_action_override_count": sum(
                row.get("final_action") != row.get("machine_default_action")
                for row in closed
            ),
            "incremental_pnl_vs_no_adjustment_usd": _summary_stats([
                row.get("incremental_pnl_vs_no_adjustment_usd") for row in closed
            ]),
            "semantic_lift_vs_machine_default_usd": _summary_stats([
                row.get("semantic_lift_vs_machine_default_usd") for row in closed
            ]),
            "final_vs_always_add_usd": _summary_stats([
                row.get("final_vs_always_add_usd") for row in closed
            ]),
            "incremental_return_on_position_bps": _summary_stats([
                row.get("incremental_return_on_position_bps") for row in closed
            ]),
            "semantic_lift_on_position_bps": _summary_stats([
                row.get("semantic_lift_on_position_bps") for row in closed
            ]),
            "final_vs_always_add_on_position_bps": _summary_stats([
                row.get("final_vs_always_add_on_position_bps") for row in closed
            ]),
            "ticker_return_bps": _summary_stats([
                row.get("ticker_return_bps") for row in closed
            ]),
        }
    next_closed = [
        row for row in effective_by_horizon["next_close"]
        if row.get("status") == "closed"
    ]
    raw_next_closed = [
        row for row in primary
        if row.get("horizon") == "next_close" and row.get("status") == "closed"
    ]
    settled_decisions = len(next_closed)
    if settled_decisions < 20:
        evidence_stage = "case_review_only"
    elif settled_decisions < 50:
        evidence_stage = "observed_only_early"
    elif settled_decisions < 100:
        evidence_stage = "observed_only_stability_review"
    else:
        evidence_stage = "eligible_for_frozen_alpha_hypothesis_design"
    status = "no_finalized_decisions" if not decisions else (
        "awaiting_forward_outcomes" if settled_decisions == 0 else "observed_only"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "scorecard_type": "intraday_triage_counterfactual_scorecard",
        "outcome_rule_version": OUTCOME_RULE_VERSION,
        "execution_rule_version": EXECUTION_RULE_VERSION,
        "aggregation_rule_version": AGGREGATION_RULE_VERSION,
        "as_of_date": as_of_date,
        "status": status,
        "decision_rows": len(decisions),
        "primary_ticker_day_decisions": sum(
            bool(row.get("primary_ticker_day_decision")) for row in decisions
        ),
        "source_decision_files": list(source_files),
        "skipped_sources": list(skipped_sources),
        "price_source": dict(price_source),
        "horizons": horizon_summary,
        "daily_portfolio_curve_next_close": _daily_curve(next_closed),
        "readiness": {
            "settled_primary_next_close_decisions": settled_decisions,
            "raw_settled_primary_next_close_decisions": len(raw_next_closed),
            "duplicate_settled_economic_rows_excluded": (
                len(raw_next_closed) - settled_decisions
            ),
            "evidence_stage": evidence_stage,
            "alpha_claim_allowed": False,
            "promotion_note": (
                "This scorecard is forward measurement only. A production rule "
                "still requires a frozen attributable hypothesis and Gate 1-4."
            ),
        },
        "trade_enabled": False,
        "strategy_behavior_changed": False,
    }


def _artifact_paths(data_root: Path, date_tag: str) -> dict[str, Path]:
    root = data_root / "daily" / "intraday" / "backtests"
    return {
        "ledger": root / "outcome_ledgers" / f"intraday_triage_outcomes_{date_tag}.jsonl",
        "scorecard": root / "scorecards" / f"intraday_triage_scorecard_{date_tag}.json",
        "report": root / "reports" / f"intraday_triage_scorecard_{date_tag}.txt",
        "latest": root / "latest_scorecard.json",
    }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8")


def render_scorecard(scorecard: Mapping[str, Any]) -> str:
    lines = [
        "INTRADAY TRIAGE COUNTERFACTUAL SCORECARD",
        f"as_of={scorecard.get('as_of_date')} status={scorecard.get('status')}",
        f"decisions={scorecard.get('decision_rows')} primary={scorecard.get('primary_ticker_day_decisions')}",
        f"evidence_stage={(scorecard.get('readiness') or {}).get('evidence_stage')}",
        "",
    ]
    for horizon in HORIZONS:
        row = (scorecard.get("horizons") or {}).get(horizon) or {}
        pnl = row.get("incremental_pnl_vs_no_adjustment_usd") or {}
        lift = row.get("semantic_lift_vs_machine_default_usd") or {}
        always = row.get("final_vs_always_add_usd") or {}
        return_bps = row.get("incremental_return_on_position_bps") or {}
        lines.append(
            f"{horizon:<11} closed={row.get('closed', 0):<4} "
            f"raw_closed={row.get('raw_closed', row.get('closed', 0)):<4} "
            f"dup_excluded={row.get('duplicate_rows_excluded', 0):<4} "
            f"pending={row.get('pending', 0):<4} "
            f"pnl_sum={pnl.get('sum', 0):>10.2f} "
            f"return_bps={return_bps.get('sum', 0):>9.2f} "
            f"semantic_lift={lift.get('sum', 0):>10.2f} "
            f"vs_always_add={always.get('sum', 0):>10.2f}"
        )
    lines.extend((
        "",
        "ADVISORY FORWARD MEASUREMENT ONLY - NOT GATE 1-4 OR LIVE-READY ALPHA.",
    ))
    return "\n".join(lines) + "\n"


def run_intraday_backtest(
    as_of: str | date | datetime | None = None,
    *,
    data_dir: str | Path | None = None,
    bars_by_ticker: Mapping[str, Any] | None = None,
    fetch_prices: bool = True,
) -> dict[str, Any]:
    data_root = Path(data_dir or DATA_ROOT)
    date_tag = _date_tag(as_of)
    as_of_iso = f"{date_tag[:4]}-{date_tag[4:6]}-{date_tag[6:8]}"
    decisions, source_files, skipped = load_finalized_decisions(
        data_root,
        through_date=date_tag,
    )
    if bars_by_ticker is None:
        if decisions and fetch_prices:
            tickers = {
                str(value).upper()
                for row in decisions
                for value in (
                    row.get("ticker"), row.get("underlying"),
                    row.get("sector_proxy"), row.get("market_proxy"),
                )
                if value
            }
            start = min(str(row["decision_date"]) for row in decisions)
            bars, price_source = fetch_opend_history(
                tickers,
                start_date=start,
                end_date=as_of_iso,
            )
        else:
            bars = {}
            price_source = {
                "status": "not_requested" if not decisions else "disabled",
                "requested_tickers": 0,
                "errors": {},
            }
    else:
        bars = dict(bars_by_ticker)
        price_source = {
            "status": "provided",
            "requested_tickers": len(bars),
            "returned_tickers": sum(bool(_normalize_bars(rows)) for rows in bars.values()),
            "errors": {},
        }
    outcomes = build_intraday_outcomes(
        decisions,
        bars,
        as_of_date=as_of_iso,
    )
    scorecard = build_scorecard(
        outcomes,
        decisions=decisions,
        source_files=source_files,
        skipped_sources=skipped,
        as_of_date=as_of_iso,
        price_source=price_source,
    )
    paths = _artifact_paths(data_root, date_tag)
    _write_jsonl(paths["ledger"], outcomes)
    _write_json(paths["scorecard"], scorecard)
    _write_json(paths["latest"], scorecard)
    paths["report"].parent.mkdir(parents=True, exist_ok=True)
    paths["report"].write_text(render_scorecard(scorecard), encoding="utf-8")
    return {
        "scorecard": scorecard,
        "outcomes": outcomes,
        "paths": {key: str(value) for key, value in paths.items()},
    }
