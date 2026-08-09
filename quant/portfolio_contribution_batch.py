"""Capital-conserving portfolio-contribution batch evaluator.

This module implements the owner-authorized Gate 4-P measurement for
``exp-20260715-002``.  It deliberately does not alter the existing champion
replacement gate or any production strategy behavior.  Every candidate is
funded by replacing 10% of the active core portfolio:

    combined_return = 0.90 * core_return + 0.10 * candidate_return

The diagnostic cash comparator is ``0.90 * core_return``.  The formal
comparison remains the stricter ``combined`` versus ``1.00 * core`` contract.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import sqlite3
import statistics
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from quant.evaluator_gates import evaluate_portfolio_contribution_gate


EXPERIMENT_ID = "exp-20260715-002"
WINDOWS = ("late_strong", "mid_weak", "old_thin")
DEFAULT_RANKING = Path(
    "data/experiments/exp-20260706-022/"
    "exp_20260706_022_portfolio_covariance_candidate_ranking.json"
)
DEFAULT_CORE_ARTIFACTS = {
    window: Path(
        f"data/backtests/post_mtm_20260712/{window}_exp-20260712-015.json"
    )
    for window in WINDOWS
}
DEFAULT_WAREHOUSE = Path("data/warehouse/warehouse_main.sqlite")
DEFAULT_OUTPUT_DIR = Path(f"data/experiments/{EXPERIMENT_ID}")
DEFAULT_BOOTSTRAP_REPLICATES = 10_000
DEFAULT_BOOTSTRAP_SEED = 2_026_071_502
DEFAULT_BLOCK_LENGTH = 20
PORTFOLIO_CAPITAL_USD = 100_000.0
CORE_WEIGHT = 0.90
CANDIDATE_WEIGHT = 0.10
CANDIDATE_SLEEVE_CAPITAL_USD = PORTFOLIO_CAPITAL_USD * CANDIDATE_WEIGHT
ONE_WAY_COST_FRACTION = 0.00175
FORCED_EXIT_SLIPPAGE_FRACTION = 0.0005


def _repo_path(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else REPO_ROOT / value


def _display_path(path: str | Path) -> str:
    resolved = _repo_path(path)
    try:
        value = resolved.relative_to(REPO_ROOT)
    except ValueError:
        value = resolved
    return str(value).replace("\\", "/")


def _read_json(path: str | Path) -> dict[str, Any]:
    resolved = _repo_path(path)
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {resolved}")
    return payload


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with _repo_path(path).open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if value is None:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def core_calendar_and_returns(
    artifact: Mapping[str, Any],
) -> tuple[list[date], np.ndarray]:
    """Extract the immutable dated core return series from an artifact."""

    inference = artifact.get("sharpe_inference")
    rows = inference.get("return_series") if isinstance(inference, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError("core artifact has no sharpe_inference.return_series")
    calendar: list[date] = []
    returns: list[float] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("invalid core return row")
        day = _parse_date(row.get("date"))
        value = _as_float(row.get("return"))
        if day is None or value is None:
            raise ValueError(f"invalid core return row: {row!r}")
        calendar.append(day)
        returns.append(value)
    if calendar != sorted(set(calendar)):
        raise ValueError("core return dates are not unique and increasing")
    return calendar, np.asarray(returns, dtype=float)


def _price_close(
    price_map: Mapping[str, Mapping[date, Mapping[str, float]]],
    ticker: str,
    day: date,
) -> float | None:
    row = price_map.get(ticker, {}).get(day)
    return _as_float(row.get("close")) if isinstance(row, Mapping) else None


def trade_required_price_dates(
    row: Mapping[str, Any], calendar: Sequence[date]
) -> set[tuple[str, date]]:
    """Return the exact warehouse close rows consumed by one replay.

    A normal exit uses the source artifact's exit price, so its booking date is
    not a warehouse dependency.  A cross-boundary exit uses the final calendar
    day's warehouse close and therefore does require that row.
    """

    if not calendar:
        return set()
    ticker = str(row.get("ticker") or "").strip().upper()
    entry = _parse_date(row.get("entry_date"))
    exit_day = _parse_date(row.get("exit_date"))
    if not ticker or entry is None or exit_day is None:
        return set()
    if entry > calendar[-1] or exit_day < calendar[0]:
        return set()
    forced = exit_day > calendar[-1]
    booking = calendar[-1] if forced else max(
        (day for day in calendar if day <= exit_day), default=None
    )
    if booking is None:
        return set()
    active = [day for day in calendar if max(entry, calendar[0]) <= day <= booking]
    return {
        (ticker, day)
        for day in active
        if forced or day != booking
    }


def allocate_sleeve_capital(
    rows: Sequence[Mapping[str, Any]],
    calendar: Sequence[date],
    *,
    sleeve_capital: float = CANDIDATE_SLEEVE_CAPITAL_USD,
    price_map: Mapping[str, Mapping[date, Mapping[str, float]]] | None = None,
    one_way_cost_fraction: float = ONE_WAY_COST_FRACTION,
    forced_exit_slippage_fraction: float = FORCED_EXIT_SLIPPAGE_FRACTION,
) -> dict[str, Any]:
    """Fund a no-leverage sleeve with a real entry/exit cash ledger.

    Prior-day exits return actual proceeds before the next morning's entries.
    Same-day exits settle only after that morning and therefore cannot fund
    same-day entries.  All requests sharing an entry date receive one common
    pro-rata fill ratio (including entry fees), making allocation invariant to
    source order.  Profits increase later buying power; losses and costs reduce
    it.  Source ``paper_notional_usd`` and reported ``pnl`` are scaled to the
    funded principal before MTM replay.

    ``price_map`` is only needed to finalize a force-close at the last window
    date.  Such a close cannot affect an earlier entry allocation, so a first
    pass without prices is safe when selecting the reproducibility snapshot.
    """

    if sleeve_capital <= 0.0 or not math.isfinite(sleeve_capital):
        raise ValueError("sleeve_capital must be finite and positive")
    if not calendar:
        raise ValueError("calendar must not be empty")
    first_day = calendar[0]
    last_day = calendar[-1]
    prepared: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    source_requested = 0.0
    for source_order, raw_row in enumerate(rows):
        row = dict(raw_row)
        ticker = str(row.get("ticker") or "").strip().upper()
        entry = _parse_date(row.get("entry_date"))
        source_exit = _parse_date(row.get("exit_date"))
        requested = _as_float(row.get("paper_notional_usd"))
        entry_price = _as_float(row.get("entry_price"))
        source_exit_price = _as_float(row.get("exit_price"))
        if requested is not None and requested > 0.0:
            source_requested += requested
        if (
            not ticker
            or entry is None
            or source_exit is None
            or requested is None
            or requested <= 0.0
            or entry_price is None
            or entry_price <= 0.0
            or source_exit_price is None
        ):
            diagnostics.append(
                {
                    "source_order": source_order,
                    "status": "invalid",
                    "reason": "allocation_missing_required_fields",
                    "requested_notional_usd": requested,
                    "filled_notional_usd": 0.0,
                }
            )
            continue
        if entry > last_day:
            diagnostics.append(
                {
                    "source_order": source_order,
                    "status": "excluded",
                    "reason": "entry_after_window_end",
                    "entry_date": entry.isoformat(),
                    "requested_notional_usd": requested,
                    "filled_notional_usd": 0.0,
                }
            )
            continue
        if source_exit < first_day:
            diagnostics.append(
                {
                    "source_order": source_order,
                    "status": "excluded",
                    "reason": "exit_before_window_start",
                    "entry_date": entry.isoformat(),
                    "requested_notional_usd": requested,
                    "filled_notional_usd": 0.0,
                }
            )
            continue
        effective_entry = max(entry, first_day)
        if source_exit > last_day:
            effective_exit = last_day
        else:
            effective_exit = max(
                (day for day in calendar if day <= source_exit), default=None
            )
        if effective_exit is None or effective_entry > effective_exit:
            diagnostics.append(
                {
                    "source_order": source_order,
                    "status": "excluded",
                    "reason": "no_active_calendar_days",
                    "entry_date": entry.isoformat(),
                    "requested_notional_usd": requested,
                    "filled_notional_usd": 0.0,
                }
            )
            continue
        prepared.append(
            {
                "source_order": source_order,
                "row": row,
                "ticker": ticker,
                "entry": effective_entry,
                "exit": effective_exit,
                "requested": requested,
                "entry_price": entry_price,
                "source_exit_price": source_exit_price,
                "forced_close": source_exit > last_day,
            }
        )

    prepared.sort(key=lambda item: (item["entry"], item["source_order"]))
    active: list[dict[str, Any]] = []
    allocated_rows: list[dict[str, Any]] = []
    allocation_requested = 0.0
    filled_total = 0.0
    peak_invested = 0.0
    full_fill_count = 0
    partial_fill_count = 0
    zero_fill_count = 0
    cash = float(sleeve_capital)
    min_cash = cash
    exit_settlement_count = 0
    cash_events: list[dict[str, Any]] = []

    def exit_price(position: Mapping[str, Any]) -> float | None:
        if not position["forced_close"]:
            return float(position["source_exit_price"])
        if price_map is None:
            return None
        raw_close = _price_close(
            price_map, str(position["ticker"]), position["exit"]
        )
        return (
            raw_close * (1.0 - forced_exit_slippage_fraction)
            if raw_close is not None
            else None
        )

    def settle(positions: Sequence[dict[str, Any]], settlement_day: date) -> bool:
        nonlocal cash, min_cash, exit_settlement_count
        for position in sorted(
            positions, key=lambda value: (value["exit"], value["source_order"])
        ):
            price = exit_price(position)
            if price is None:
                return False
            exit_cost = one_way_cost_fraction * float(position["filled"])
            proceeds = float(position["shares"]) * price - exit_cost
            cash += proceeds
            exit_settlement_count += 1
            cash_events.append(
                {
                    "date": settlement_day.isoformat(),
                    "type": "exit_settlement",
                    "source_order": int(position["source_order"]),
                    "principal_usd": float(position["filled"]),
                    "exit_price": price,
                    "exit_cost_usd": exit_cost,
                    "cash_delta_usd": proceeds,
                    "cash_after_usd": cash,
                }
            )
            min_cash = min(min_cash, cash)
        return True

    prepared_by_day: defaultdict[date, list[dict[str, Any]]] = defaultdict(list)
    for item in prepared:
        prepared_by_day[item["entry"]].append(item)
    final_settlement_complete = True
    for entry_day in sorted(prepared_by_day):
        prior_exits = [position for position in active if position["exit"] < entry_day]
        if prior_exits and not settle(prior_exits, entry_day):
            raise AssertionError("a pre-entry exit price must be known")
        active = [position for position in active if position["exit"] >= entry_day]

        day_items = sorted(
            prepared_by_day[entry_day], key=lambda item: item["source_order"]
        )
        total_requested = sum(float(item["requested"]) for item in day_items)
        allocation_requested += total_requested
        total_cash_required = total_requested * (1.0 + one_way_cost_fraction)
        pro_rata_ratio = (
            min(1.0, cash / total_cash_required)
            if total_cash_required > 0.0
            else 0.0
        )
        cash_before_entries = cash
        total_entry_debit = 0.0
        for item in day_items:
            requested = float(item["requested"])
            filled = requested * pro_rata_ratio
            entry_cost = filled * one_way_cost_fraction
            total_entry_debit += filled + entry_cost
            ratio = filled / requested
            base_diag = {
                "source_order": int(item["source_order"]),
                "entry_date": entry_day.isoformat(),
                "effective_exit_date": item["exit"].isoformat(),
                "requested_notional_usd": requested,
                "filled_notional_usd": filled,
                "fill_ratio": ratio,
                "day_total_requested_notional_usd": total_requested,
                "day_pro_rata_fill_ratio": pro_rata_ratio,
                "cash_before_day_entries_usd": cash_before_entries,
            }
            if filled <= 1e-12:
                zero_fill_count += 1
                diagnostics.append(
                    {
                        **base_diag,
                        "status": "excluded",
                        "reason": "sleeve_cap_no_cash",
                    }
                )
                continue

            scaled = dict(item["row"])
            scaled["_sleeve_source_order"] = int(item["source_order"])
            scaled["_sleeve_requested_notional_usd"] = requested
            scaled["_sleeve_filled_notional_usd"] = filled
            scaled["_sleeve_fill_ratio"] = ratio
            scaled["paper_notional_usd"] = filled
            reported_pnl = _as_float(scaled.get("pnl"))
            if reported_pnl is not None:
                scaled["pnl"] = reported_pnl * ratio
            allocated_rows.append(scaled)
            active.append(
                {
                    **item,
                    "filled": filled,
                    "shares": filled / float(item["entry_price"]),
                }
            )
            filled_total += filled
            if ratio < 1.0 - 1e-12:
                partial_fill_count += 1
                status = "partial_fill"
            else:
                full_fill_count += 1
                status = "full_fill"
            diagnostics.append(
                {**base_diag, "status": status, "reason": None}
            )

        cash = max(0.0, cash - total_entry_debit)
        min_cash = min(min_cash, cash)
        invested = sum(float(position["filled"]) for position in active)
        peak_invested = max(peak_invested, invested)
        cash_events.append(
            {
                "date": entry_day.isoformat(),
                "type": "pro_rata_entry_batch",
                "request_count": len(day_items),
                "requested_notional_usd": total_requested,
                "pro_rata_fill_ratio": pro_rata_ratio,
                "principal_plus_entry_cost_debit_usd": total_entry_debit,
                "cash_before_usd": cash_before_entries,
                "cash_after_usd": cash,
                "invested_principal_after_usd": invested,
            }
        )

    if active:
        final_settlement_complete = settle(active, last_day)
    ending_cash = cash if final_settlement_complete else None

    diagnostics.sort(key=lambda item: int(item["source_order"]))
    invalid_count = sum(item["status"] == "invalid" for item in diagnostics)
    boundary_excluded_count = sum(
        item["status"] == "excluded"
        and item.get("reason") != "sleeve_cap_no_cash"
        for item in diagnostics
    )
    if min_cash < -1e-9:
        raise AssertionError("cash allocator created leverage")
    return {
        "allocated_rows": allocated_rows,
        "diagnostics": diagnostics,
        "sleeve_capital_usd": sleeve_capital,
        "source_trade_count": len(rows),
        "source_requested_notional_usd": source_requested,
        "allocation_requested_notional_usd": allocation_requested,
        "filled_notional_usd": filled_total,
        "full_fill_count": full_fill_count,
        "partial_fill_count": partial_fill_count,
        "zero_fill_count": zero_fill_count,
        "invalid_count": invalid_count,
        "boundary_excluded_count": boundary_excluded_count,
        "entry_fee_fraction": one_way_cost_fraction,
        "exit_fee_fraction": one_way_cost_fraction,
        "min_cash_usd": min_cash,
        "peak_invested_notional_usd": peak_invested,
        "ending_cash_usd": ending_cash,
        "cash_ledger_net_pnl_usd": (
            ending_cash - sleeve_capital if ending_cash is not None else None
        ),
        "ending_all_positions_settled": final_settlement_complete,
        "exit_settlement_count": exit_settlement_count,
        "cash_nonnegative": min_cash >= -1e-9,
        "cash_events": cash_events,
        "same_day_exit_reuse": False,
        "same_day_entry_allocation": "pro_rata_including_entry_fee",
    }


def reconstruct_trade_daily_pnl(
    row: Mapping[str, Any],
    calendar: Sequence[date],
    price_map: Mapping[str, Mapping[date, Mapping[str, float]]],
    *,
    one_way_cost_fraction: float = ONE_WAY_COST_FRACTION,
    forced_exit_slippage_fraction: float = FORCED_EXIT_SLIPPAGE_FRACTION,
) -> tuple[dict[date, float], dict[str, Any]]:
    """Reconstruct one trade on a fixed calendar with explicit split costs.

    Entries after the fixed window are excluded.  Exits beyond the fixed
    boundary are force-closed at the final calendar day's warehouse close.
    Intermediate missing closes are carried at the previous mark, matching a
    non-trading/halted security rather than fabricating a price.
    """

    ticker = str(row.get("ticker") or "").strip().upper()
    entry = _parse_date(row.get("entry_date"))
    source_exit = _parse_date(row.get("exit_date"))
    entry_price = _as_float(row.get("entry_price"))
    source_exit_price = _as_float(row.get("exit_price"))
    notional = _as_float(row.get("paper_notional_usd"))
    reported_pnl = _as_float(row.get("pnl"))
    required_ok = (
        bool(ticker)
        and entry is not None
        and source_exit is not None
        and entry_price is not None
        and entry_price > 0.0
        and source_exit_price is not None
        and notional is not None
        and notional > 0.0
        and bool(calendar)
    )
    if not required_ok:
        return {}, {
            "usable": False,
            "excluded": False,
            "reason": "missing_required_trade_fields",
            "ticker": ticker,
        }
    assert entry is not None
    assert source_exit is not None
    assert entry_price is not None
    assert source_exit_price is not None
    assert notional is not None

    first_day = calendar[0]
    last_day = calendar[-1]
    if entry > last_day:
        return {}, {
            "usable": False,
            "excluded": True,
            "reason": "entry_after_window_end",
            "ticker": ticker,
            "entry_date": entry.isoformat(),
            "window_end": last_day.isoformat(),
        }
    if source_exit < first_day:
        return {}, {
            "usable": False,
            "excluded": True,
            "reason": "exit_before_window_start",
            "ticker": ticker,
        }

    forced_close = source_exit > last_day
    forced_exit_raw_close: float | None = None
    if forced_close:
        booking_day = last_day
        forced_exit_raw_close = _price_close(price_map, ticker, booking_day)
        if forced_exit_raw_close is None:
            return {}, {
                "usable": False,
                "excluded": False,
                "reason": "missing_forced_exit_close",
                "ticker": ticker,
                "forced_exit_date": booking_day.isoformat(),
            }
        effective_exit_price = forced_exit_raw_close * (
            1.0 - forced_exit_slippage_fraction
        )
    else:
        booking_day = max(
            (day for day in calendar if day <= source_exit), default=None
        )
        effective_exit_price = source_exit_price
        if booking_day is None:
            return {}, {
                "usable": False,
                "excluded": True,
                "reason": "exit_before_window_start",
                "ticker": ticker,
            }

    active_days = [
        day for day in calendar if max(entry, first_day) <= day <= booking_day
    ]
    if not active_days:
        return {}, {
            "usable": False,
            "excluded": True,
            "reason": "no_active_calendar_days",
            "ticker": ticker,
        }

    shares = notional / entry_price
    entry_cost = one_way_cost_fraction * notional
    exit_cost = one_way_cost_fraction * notional
    previous_mark = entry_price
    pnl_by_day: dict[date, float] = {}
    missing_intermediate_closes: list[str] = []
    for index, day in enumerate(active_days):
        if day == booking_day:
            mark = effective_exit_price
        else:
            mark = _price_close(price_map, ticker, day)
            if mark is None:
                mark = previous_mark
                missing_intermediate_closes.append(day.isoformat())
        pnl = (mark - previous_mark) * shares
        if index == 0:
            pnl -= entry_cost
        if day == booking_day:
            pnl -= exit_cost
        pnl_by_day[day] = pnl_by_day.get(day, 0.0) + pnl
        previous_mark = mark

    net_pnl = sum(pnl_by_day.values())
    expected_net = shares * (effective_exit_price - entry_price) - entry_cost - exit_cost
    reconciliation_error = (
        net_pnl - reported_pnl
        if reported_pnl is not None and not forced_close
        else None
    )
    return pnl_by_day, {
        "usable": True,
        "excluded": False,
        "ticker": ticker,
        "entry_date": entry.isoformat(),
        "source_exit_date": source_exit.isoformat(),
        "effective_exit_date": booking_day.isoformat(),
        "forced_close": forced_close,
        "entry_before_window_start": entry < first_day,
        "entry_price": entry_price,
        "effective_exit_price": effective_exit_price,
        "forced_exit_raw_close": forced_exit_raw_close,
        "forced_exit_sell_slippage_fraction": (
            forced_exit_slippage_fraction if forced_close else None
        ),
        "paper_notional_usd": notional,
        "shares": shares,
        "entry_cost_usd": entry_cost,
        "exit_cost_usd": exit_cost,
        "net_pnl": net_pnl,
        "formula_net_pnl": expected_net,
        "reported_pnl": reported_pnl,
        "normal_exit_reconciliation_error": reconciliation_error,
        "missing_intermediate_closes": missing_intermediate_closes,
    }


def pnl_to_returns(
    pnl_by_day: Mapping[date, float],
    calendar: Sequence[date],
    *,
    initial_capital: float = PORTFOLIO_CAPITAL_USD,
) -> np.ndarray:
    """Convert dollar MTM into a self-financing equity return series."""

    equity = float(initial_capital)
    values: list[float] = []
    for day in calendar:
        pnl = float(pnl_by_day.get(day, 0.0))
        if equity <= 0.0:
            raise ValueError("candidate equity is non-positive")
        values.append(pnl / equity)
        equity += pnl
    return np.asarray(values, dtype=float)


def return_metrics(
    returns: Sequence[float] | np.ndarray,
    *,
    capital: float = PORTFOLIO_CAPITAL_USD,
) -> dict[str, float | int]:
    """Compute the standard daily-equity metrics used by Gate 4-P."""

    values = np.asarray(returns, dtype=float)
    if values.ndim != 1 or not len(values):
        return {
            "days": 0,
            "total_return_fraction": 0.0,
            "total_pnl": 0.0,
            "sharpe_daily": 0.0,
            "expected_value_score": 0.0,
            "max_drawdown_pct": 0.0,
            "expected_shortfall_95": 0.0,
        }
    if np.any(values <= -1.0) or not np.all(np.isfinite(values)):
        raise ValueError("returns must be finite and greater than -100%")
    total_return = float(np.prod(1.0 + values) - 1.0)
    std = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
    sharpe = float(np.mean(values) / std * math.sqrt(252.0)) if std > 0 else 0.0
    equity = np.concatenate(([1.0], np.cumprod(1.0 + values)))
    peaks = np.maximum.accumulate(equity)
    max_drawdown = float(np.max((peaks - equity) / peaks))
    tail_count = max(1, int(math.ceil(0.05 * len(values))))
    worst = np.partition(values, tail_count - 1)[:tail_count]
    es95 = max(0.0, -float(np.mean(worst)))
    return {
        "days": int(len(values)),
        "total_return_fraction": total_return,
        "total_pnl": capital * total_return,
        "sharpe_daily": sharpe,
        "expected_value_score": total_return * sharpe,
        "max_drawdown_pct": max_drawdown,
        "expected_shortfall_95": es95,
    }


def _metric_delta(after: Mapping[str, Any], before: Mapping[str, Any]) -> dict[str, float]:
    keys = (
        "total_return_fraction",
        "total_pnl",
        "sharpe_daily",
        "expected_value_score",
        "max_drawdown_pct",
        "expected_shortfall_95",
    )
    return {key: float(after[key]) - float(before[key]) for key in keys}


def _pearson(left: np.ndarray, right: np.ndarray) -> float | None:
    if len(left) < 2 or len(left) != len(right):
        return None
    if float(np.std(left)) <= 0.0 or float(np.std(right)) <= 0.0:
        return None
    return float(np.corrcoef(left, right)[0, 1])


def circular_block_indices(
    length: int,
    *,
    replicates: int,
    block_length: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Draw deterministic circular block-bootstrap indices."""

    if length <= 0 or replicates <= 0 or block_length <= 0:
        raise ValueError("length, replicates, and block_length must be positive")
    blocks = int(math.ceil(length / block_length))
    starts = rng.integers(0, length, size=(replicates, blocks), endpoint=False)
    offsets = np.arange(block_length, dtype=np.int64)
    indices = (starts[:, :, None] + offsets[None, None, :]) % length
    return indices.reshape(replicates, blocks * block_length)[:, :length]


def _bootstrap_ev(values: np.ndarray) -> np.ndarray:
    """Vectorized EV for rows of bootstrap return sequences."""

    total_return = np.expm1(np.log1p(values).sum(axis=1))
    means = values.mean(axis=1)
    stds = values.std(axis=1, ddof=1)
    sharpes = np.divide(
        means * math.sqrt(252.0),
        stds,
        out=np.zeros_like(means),
        where=stds > 0.0,
    )
    return total_return * sharpes


def max_t_lower_bounds(
    observed: Sequence[float] | np.ndarray,
    bootstrap_estimates: np.ndarray,
    *,
    confidence: float = 0.90,
) -> tuple[np.ndarray, np.ndarray, float]:
    """Return simultaneous one-sided lower bounds and their max-T inputs.

    For a lower confidence bound the adverse bootstrap error is an upward
    estimation error, ``bootstrap_estimate - observed``.  We therefore use
    the *upper* quantile of that standardized error and subtract it from the
    observed estimate.  Reversing the numerator would select the wrong tail
    for skewed bootstrap distributions.
    """

    point = np.asarray(observed, dtype=float)
    boot = np.asarray(bootstrap_estimates, dtype=float)
    if boot.ndim != 2 or point.ndim != 1 or boot.shape[1] != len(point):
        raise ValueError("bootstrap estimates must have shape (replicates, candidates)")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must lie strictly between zero and one")
    standard_errors = np.std(boot, axis=0, ddof=1)
    standardized = np.zeros_like(boot)
    nonzero = standard_errors > 1e-15
    standardized[:, nonzero] = (
        boot[:, nonzero] - point[None, nonzero]
    ) / standard_errors[None, nonzero]
    max_t = np.max(standardized, axis=1)
    critical_value = float(np.quantile(max_t, confidence))
    lower_bounds = point - critical_value * standard_errors
    return lower_bounds, standard_errors, critical_value


def simultaneous_max_t_bounds(
    core_returns_by_window: Mapping[str, Sequence[float] | np.ndarray],
    candidate_returns_by_id: Mapping[
        str, Mapping[str, Sequence[float] | np.ndarray]
    ],
    *,
    candidate_weight: float = CANDIDATE_WEIGHT,
    replicates: int = DEFAULT_BOOTSTRAP_REPLICATES,
    block_length: int = DEFAULT_BLOCK_LENGTH,
    seed: int = DEFAULT_BOOTSTRAP_SEED,
    confidence: float = 0.90,
) -> dict[str, Any]:
    """Paired, window-stratified circular bootstrap with max-T bounds.

    A single index matrix per window is shared across all candidates, preserving
    the panel dependence needed by the simultaneous family-wise bound.
    """

    candidate_ids = sorted(candidate_returns_by_id)
    if not candidate_ids:
        raise ValueError("candidate panel is empty")
    rng = np.random.default_rng(seed)
    indices_by_window: dict[str, np.ndarray] = {}
    core_arrays: dict[str, np.ndarray] = {}
    bootstrap_core_ev: dict[str, np.ndarray] = {}
    for window in WINDOWS:
        core = np.asarray(core_returns_by_window[window], dtype=float)
        indices = circular_block_indices(
            len(core),
            replicates=replicates,
            block_length=block_length,
            rng=rng,
        )
        indices_by_window[window] = indices
        core_arrays[window] = core
        bootstrap_core_ev[window] = _bootstrap_ev(core[indices])

    observed = np.zeros(len(candidate_ids), dtype=float)
    boot = np.zeros((replicates, len(candidate_ids)), dtype=float)
    for column, candidate_id in enumerate(candidate_ids):
        for window in WINDOWS:
            core = core_arrays[window]
            candidate = np.asarray(
                candidate_returns_by_id[candidate_id][window], dtype=float
            )
            if len(candidate) != len(core):
                raise ValueError(
                    f"calendar mismatch for {candidate_id}/{window}: "
                    f"{len(candidate)} != {len(core)}"
                )
            combined = (1.0 - candidate_weight) * core + candidate_weight * candidate
            observed[column] += (
                float(return_metrics(combined)["expected_value_score"])
                - float(return_metrics(core)["expected_value_score"])
            )
            indices = indices_by_window[window]
            boot[:, column] += (
                _bootstrap_ev(combined[indices]) - bootstrap_core_ev[window]
            )

    lower_bounds, standard_errors, critical_value = max_t_lower_bounds(
        observed,
        boot,
        confidence=confidence,
    )
    return {
        "candidate_ids": candidate_ids,
        "observed_aggregate_ev_delta": observed.tolist(),
        "bootstrap_standard_error": standard_errors.tolist(),
        "simultaneous_lower_bound": lower_bounds.tolist(),
        "critical_max_t": critical_value,
        "confidence": confidence,
        "replicates": replicates,
        "block_length": block_length,
        "seed": seed,
        "bootstrap_matrix_shape": [int(value) for value in boot.shape],
    }


def _concentration(
    rows: Iterable[tuple[str, float]],
) -> dict[str, float | int | None]:
    by_ticker: defaultdict[str, float] = defaultdict(float)
    for ticker, pnl in rows:
        if pnl > 0.0:
            by_ticker[ticker] += pnl
    positive = sorted(by_ticker.values(), reverse=True)
    total = sum(positive)
    if total <= 0.0:
        return {
            "positive_ticker_count": 0,
            "positive_pnl_usd": 0.0,
            "single_ticker_positive_share": None,
            "top_5_contribution_pct": None,
            "hhi_concentration": None,
        }
    shares = [value / total for value in positive]
    return {
        "positive_ticker_count": len(positive),
        "positive_pnl_usd": total,
        "single_ticker_positive_share": shares[0],
        "top_5_contribution_pct": sum(shares[:5]),
        "hhi_concentration": sum(value * value for value in shares),
    }


def _required_pairs_for_panel(
    candidate_payloads: Sequence[Mapping[str, Any]],
    calendars: Mapping[str, Sequence[date]],
) -> set[tuple[str, date]]:
    pairs: set[tuple[str, date]] = set()
    for payload in candidate_payloads:
        by_window = payload.get("target_trades_by_window")
        if not isinstance(by_window, dict):
            continue
        for window in WINDOWS:
            rows = by_window.get(window)
            if not isinstance(rows, list):
                continue
            for row in rows:
                if isinstance(row, dict):
                    pairs.update(trade_required_price_dates(row, calendars[window]))
    return pairs


def load_exact_ohlcv_rows(
    warehouse: str | Path,
    required_pairs: set[tuple[str, date]],
) -> tuple[list[dict[str, Any]], set[tuple[str, date]]]:
    """Load only OHLCV rows that the fixed-calendar replay can consume."""

    if not required_pairs:
        return [], set()
    pairs_by_ticker: defaultdict[str, set[date]] = defaultdict(set)
    for ticker, day in required_pairs:
        pairs_by_ticker[ticker].add(day)
    tickers = sorted(pairs_by_ticker)
    min_day = min(day for _, day in required_pairs).isoformat()
    max_day = max(day for _, day in required_pairs).isoformat()
    rows: list[dict[str, Any]] = []
    found: set[tuple[str, date]] = set()
    with sqlite3.connect(_repo_path(warehouse)) as connection:
        for start in range(0, len(tickers), 500):
            chunk = tickers[start : start + 500]
            placeholders = ",".join("?" for _ in chunk)
            query = (
                "select ticker, date, open, high, low, close, volume from ohlcv "
                f"where ticker in ({placeholders}) and date >= ? and date <= ? "
                "order by ticker, date"
            )
            for raw in connection.execute(query, [*chunk, min_day, max_day]):
                ticker = str(raw[0]).upper()
                day = _parse_date(raw[1])
                if day is None or day not in pairs_by_ticker[ticker]:
                    continue
                found.add((ticker, day))
                rows.append(
                    {
                        "ticker": ticker,
                        "date": day.isoformat(),
                        "open": _as_float(raw[2]),
                        "high": _as_float(raw[3]),
                        "low": _as_float(raw[4]),
                        "close": _as_float(raw[5]),
                        "volume": _as_float(raw[6]),
                    }
                )
    rows.sort(key=lambda row: (row["ticker"], row["date"]))
    return rows, required_pairs - found


def _price_map_from_rows(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, dict[date, dict[str, float]]]:
    result: defaultdict[str, dict[date, dict[str, float]]] = defaultdict(dict)
    for row in rows:
        day = _parse_date(row.get("date"))
        close = _as_float(row.get("close"))
        ticker = str(row.get("ticker") or "").upper()
        if ticker and day is not None and close is not None:
            result[ticker][day] = {"close": close}
    return dict(result)


def _write_snapshot(
    output_dir: Path,
    *,
    rows: Sequence[Mapping[str, Any]],
    potential_pairs: set[tuple[str, date]],
    actual_consumed_pairs: set[tuple[str, date]],
    missing_potential_pairs: set[tuple[str, date]],
    missing_actual_pairs: set[tuple[str, date]],
) -> dict[str, Any]:
    payload = {
        "schema": "ginger.portfolio_contribution_ohlcv_rowset.v1",
        "experiment_id": EXPERIMENT_ID,
        "selection_contract": (
            "reproducibility superset of potential fixed-calendar OHLCV rows; "
            "actual_consumed_pair_count reflects cash-funded rows"
        ),
        "potential_requested_pair_count": len(potential_pairs),
        "actual_consumed_pair_count": len(actual_consumed_pairs),
        "unused_superset_pair_count": len(potential_pairs - actual_consumed_pairs),
        "row_count": len(rows),
        "missing_pairs": [
            {"ticker": ticker, "date": day.isoformat()}
            for ticker, day in sorted(missing_potential_pairs)
        ],
        "missing_actual_consumed_pairs": [
            {"ticker": ticker, "date": day.isoformat()}
            for ticker, day in sorted(missing_actual_pairs)
        ],
        "rows": list(rows),
    }
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    compressed = gzip.compress(raw, compresslevel=9, mtime=0)
    snapshot_path = output_dir / "candidate_ohlcv_rowset.json.gz"
    snapshot_path.write_bytes(compressed)
    gzip_sha = _sha256_bytes(compressed)
    canonical_sha = _sha256_bytes(raw)
    sha_path = output_dir / "candidate_ohlcv_rowset.json.gz.sha256"
    sha_path.write_text(f"{gzip_sha}  {snapshot_path.name}\n", encoding="ascii")
    return {
        "path": str(snapshot_path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "sha256_path": str(sha_path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "gzip_sha256": gzip_sha,
        "canonical_json_sha256": canonical_sha,
        "selection_contract": payload["selection_contract"],
        "potential_requested_pair_count": len(potential_pairs),
        "actual_consumed_pair_count": len(actual_consumed_pairs),
        "unused_superset_pair_count": len(potential_pairs - actual_consumed_pairs),
        "row_count": len(rows),
        "missing_pair_count": len(missing_potential_pairs),
        "missing_actual_consumed_pair_count": len(missing_actual_pairs),
        "mode": "warehouse_materialization",
    }


def load_ohlcv_snapshot(
    snapshot_path: str | Path,
    *,
    expected_sha256: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load and authenticate a frozen OHLCV snapshot without warehouse I/O."""

    path = _repo_path(snapshot_path)
    compressed = path.read_bytes()
    actual_sha = _sha256_bytes(compressed)
    sidecar = Path(f"{path}.sha256")
    expected = str(expected_sha256 or "").strip().lower() or None
    hash_source = "explicit"
    if expected is None:
        if not sidecar.exists():
            raise ValueError(
                "frozen snapshot requires --ohlcv-snapshot-sha256 or adjacent .sha256"
            )
        fields = sidecar.read_text(encoding="ascii").strip().split()
        if not fields:
            raise ValueError(f"empty snapshot hash sidecar: {sidecar}")
        expected = fields[0].lower()
        hash_source = "adjacent_sidecar"
    if actual_sha.lower() != expected:
        raise ValueError(
            f"OHLCV snapshot sha256 mismatch: expected {expected}, got {actual_sha}"
        )
    try:
        payload = json.loads(gzip.decompress(compressed).decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid gzip OHLCV snapshot: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("OHLCV snapshot payload must be an object")
    if payload.get("schema") != "ginger.portfolio_contribution_ohlcv_rowset.v1":
        raise ValueError(f"unsupported OHLCV snapshot schema: {payload.get('schema')!r}")
    rows = payload.get("rows")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("OHLCV snapshot rows must be a list of objects")
    if int(payload.get("row_count", -1)) != len(rows):
        raise ValueError("OHLCV snapshot row_count does not match rows")
    missing_pairs = payload.get("missing_pairs")
    if not isinstance(missing_pairs, list) or missing_pairs:
        raise ValueError("OHLCV snapshot declares missing potential rows")
    missing_actual = payload.get("missing_actual_consumed_pairs")
    if not isinstance(missing_actual, list) or missing_actual:
        raise ValueError("OHLCV snapshot declares missing consumed rows")
    return rows, {
        "path": _display_path(path),
        "sha256_path": (
            _display_path(sidecar)
            if sidecar.exists()
            else None
        ),
        "gzip_sha256": actual_sha,
        "canonical_json_sha256": _sha256_bytes(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ),
        "selection_contract": payload.get("selection_contract"),
        "potential_requested_pair_count": payload.get(
            "potential_requested_pair_count"
        ),
        "actual_consumed_pair_count": payload.get("actual_consumed_pair_count"),
        "unused_superset_pair_count": payload.get("unused_superset_pair_count"),
        "row_count": len(rows),
        "missing_pair_count": 0,
        "missing_actual_consumed_pair_count": 0,
        "mode": "frozen_snapshot_replay",
        "hash_verification": hash_source,
    }


def _serializable_metrics(metrics: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in metrics.items():
        if isinstance(value, (float, np.floating)):
            result[key] = round(float(value), 12)
        elif isinstance(value, (int, np.integer)):
            result[key] = int(value)
        else:
            result[key] = value
    return result


def run_batch(
    *,
    ranking_path: str | Path = DEFAULT_RANKING,
    core_artifact_paths: Mapping[str, str | Path] = DEFAULT_CORE_ARTIFACTS,
    warehouse_path: str | Path = DEFAULT_WAREHOUSE,
    ohlcv_snapshot_path: str | Path | None = None,
    ohlcv_snapshot_sha256: str | None = None,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    bootstrap_replicates: int = DEFAULT_BOOTSTRAP_REPLICATES,
    bootstrap_seed: int = DEFAULT_BOOTSTRAP_SEED,
    block_length: int = DEFAULT_BLOCK_LENGTH,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run the complete 31-family Gate 4-P panel and write no registry state."""

    output = _repo_path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    ranking = _read_json(ranking_path)
    ranking_rows = ranking.get("candidate_ranking")
    if not isinstance(ranking_rows, list) or len(ranking_rows) != 31:
        raise ValueError(
            f"complete family panel requires exactly 31 candidates; got "
            f"{len(ranking_rows) if isinstance(ranking_rows, list) else 'invalid'}"
        )

    core_payloads: dict[str, dict[str, Any]] = {}
    calendars: dict[str, list[date]] = {}
    core_returns: dict[str, np.ndarray] = {}
    for window in WINDOWS:
        payload = _read_json(core_artifact_paths[window])
        core_payloads[window] = payload
        calendars[window], core_returns[window] = core_calendar_and_returns(payload)

    candidate_payloads: list[dict[str, Any]] = []
    candidate_input_rows: list[tuple[dict[str, Any], dict[str, Any], Path]] = []
    for ranking_row in ranking_rows:
        if not isinstance(ranking_row, dict):
            raise ValueError("invalid ranking row")
        source = _repo_path(str(ranking_row.get("path") or ""))
        payload = _read_json(source)
        by_window = payload.get("target_trades_by_window")
        if not isinstance(by_window, dict) or any(
            not isinstance(by_window.get(window), list) for window in WINDOWS
        ):
            raise ValueError(f"candidate lacks complete target trade surface: {source}")
        candidate_payloads.append(payload)
        candidate_input_rows.append((ranking_row, payload, source))

    potential_pairs = _required_pairs_for_panel(candidate_payloads, calendars)
    if ohlcv_snapshot_path is not None:
        ohlcv_rows, snapshot = load_ohlcv_snapshot(
            ohlcv_snapshot_path,
            expected_sha256=ohlcv_snapshot_sha256,
        )
        available_pairs = {
            (str(row.get("ticker") or "").upper(), _parse_date(row.get("date")))
            for row in ohlcv_rows
        }
        available_pairs = {
            (ticker, day)
            for ticker, day in available_pairs
            if ticker and day is not None
        }
        missing_potential_pairs = potential_pairs - available_pairs
        if missing_potential_pairs:
            raise ValueError(
                "frozen OHLCV snapshot does not cover the current potential panel"
            )
    else:
        ohlcv_rows, missing_potential_pairs = load_exact_ohlcv_rows(
            warehouse_path, potential_pairs
        )
        available_pairs = {
            (str(row.get("ticker") or "").upper(), _parse_date(row.get("date")))
            for row in ohlcv_rows
        }
        available_pairs = {
            (ticker, day)
            for ticker, day in available_pairs
            if ticker and day is not None
        }
        if missing_potential_pairs:
            raise ValueError("warehouse is missing potential panel OHLCV rows")
    price_map = _price_map_from_rows(ohlcv_rows)

    capital_allocations: dict[str, dict[str, dict[str, Any]]] = {}
    allocated_payloads: list[dict[str, Any]] = []
    for ranking_row, payload, _ in candidate_input_rows:
        candidate_id = str(ranking_row.get("experiment_id") or "")
        if not candidate_id or candidate_id in capital_allocations:
            raise ValueError(f"invalid or duplicate candidate id: {candidate_id!r}")
        by_window = payload["target_trades_by_window"]
        window_allocations = {
            window: allocate_sleeve_capital(
                by_window[window],
                calendars[window],
                sleeve_capital=CANDIDATE_SLEEVE_CAPITAL_USD,
                price_map=price_map,
            )
            for window in WINDOWS
        }
        capital_allocations[candidate_id] = window_allocations
        allocated_payloads.append(
            {
                "target_trades_by_window": {
                    window: window_allocations[window]["allocated_rows"]
                    for window in WINDOWS
                }
            }
        )
    actual_consumed_pairs = _required_pairs_for_panel(
        allocated_payloads, calendars
    )
    missing_actual_pairs = actual_consumed_pairs - available_pairs
    if missing_actual_pairs:
        raise ValueError("OHLCV source is missing cash-funded consumed rows")
    if ohlcv_snapshot_path is None:
        snapshot = _write_snapshot(
            output,
            rows=ohlcv_rows,
            potential_pairs=potential_pairs,
            actual_consumed_pairs=actual_consumed_pairs,
            missing_potential_pairs=missing_potential_pairs,
            missing_actual_pairs=missing_actual_pairs,
        )
    else:
        embedded_actual = snapshot.get("actual_consumed_pair_count")
        if embedded_actual is not None and int(embedded_actual) != len(
            actual_consumed_pairs
        ):
            raise ValueError(
                "frozen OHLCV snapshot actual consumed count does not match replay"
            )
        snapshot["potential_requested_pair_count"] = len(potential_pairs)
        snapshot["actual_consumed_pair_count"] = len(actual_consumed_pairs)
        snapshot["unused_superset_pair_count"] = len(
            potential_pairs - actual_consumed_pairs
        )

    core_trade_contributions: list[tuple[str, float]] = []
    for window in WINDOWS:
        for row in core_payloads[window].get("trades") or []:
            if isinstance(row, dict):
                ticker = str(row.get("ticker") or "").upper()
                pnl = _as_float(row.get("pnl"))
                if ticker and pnl is not None:
                    core_trade_contributions.append((ticker, pnl))
    baseline_concentration = _concentration(core_trade_contributions)

    candidates: list[dict[str, Any]] = []
    candidate_return_panel: dict[str, dict[str, np.ndarray]] = {}
    candidate_trade_contributions: dict[str, list[tuple[str, float]]] = {}
    for ranking_row, payload, source_path in candidate_input_rows:
        candidate_id = str(ranking_row.get("experiment_id") or "")
        if not candidate_id:
            raise ValueError(f"ranking row has no experiment_id: {ranking_row!r}")
        by_window = payload["target_trades_by_window"]
        window_results: dict[str, Any] = {}
        return_by_window: dict[str, np.ndarray] = {}
        trade_contributions: list[tuple[str, float]] = []
        total_usable = 0
        total_excluded = 0
        total_unusable = 0
        normal_errors: list[float] = []
        forced_count = 0
        for window in WINDOWS:
            pnl_by_day: defaultdict[date, float] = defaultdict(float)
            diagnostics: list[dict[str, Any]] = []
            allocation = capital_allocations[candidate_id][window]
            allocation_excluded = int(allocation["zero_fill_count"]) + int(
                allocation["boundary_excluded_count"]
            )
            allocation_invalid = int(allocation["invalid_count"])
            total_excluded += allocation_excluded
            total_unusable += allocation_invalid
            for row in allocation["allocated_rows"]:
                series, diagnostic = reconstruct_trade_daily_pnl(
                    row,
                    calendars[window],
                    price_map,
                )
                diagnostics.append(diagnostic)
                if diagnostic.get("usable"):
                    total_usable += 1
                    forced_count += int(bool(diagnostic.get("forced_close")))
                    ticker = str(diagnostic["ticker"])
                    net_pnl = float(diagnostic["net_pnl"])
                    trade_contributions.append((ticker, net_pnl))
                    error = diagnostic.get("normal_exit_reconciliation_error")
                    if error is not None:
                        normal_errors.append(float(error))
                    for day, value in series.items():
                        pnl_by_day[day] += value
                elif diagnostic.get("excluded"):
                    total_excluded += 1
                else:
                    total_unusable += 1
            candidate = pnl_to_returns(
                pnl_by_day,
                calendars[window],
                initial_capital=CANDIDATE_SLEEVE_CAPITAL_USD,
            )
            core = core_returns[window]
            combined = CORE_WEIGHT * core + CANDIDATE_WEIGHT * candidate
            cash_funded = CORE_WEIGHT * core
            core_metrics = return_metrics(core)
            candidate_metrics = return_metrics(
                candidate, capital=CANDIDATE_SLEEVE_CAPITAL_USD
            )
            combined_metrics = return_metrics(combined)
            cash_metrics = return_metrics(cash_funded)
            ending_equity = CANDIDATE_SLEEVE_CAPITAL_USD + sum(
                pnl_by_day.values()
            )
            ending_cash = allocation.get("ending_cash_usd")
            cash_equity_error = (
                ending_equity - float(ending_cash)
                if ending_cash is not None
                else None
            )
            allocation_report = {
                key: value
                for key, value in allocation.items()
                if key != "allocated_rows"
            }
            allocation_report["ending_mtm_equity_usd"] = ending_equity
            allocation_report["mtm_net_pnl_usd"] = sum(pnl_by_day.values())
            allocation_report["ending_cash_equity_reconciliation_error_usd"] = (
                cash_equity_error
            )
            allocation_report["ending_cash_equity_reconciled"] = (
                cash_equity_error is not None and abs(cash_equity_error) <= 1e-6
            )
            window_results[window] = {
                "calendar_start": calendars[window][0].isoformat(),
                "calendar_end": calendars[window][-1].isoformat(),
                "calendar_days": len(calendars[window]),
                "source_trade_count": len(by_window[window]),
                "usable_trade_count": sum(
                    1 for item in diagnostics if item.get("usable")
                ),
                "excluded_trade_count": allocation_excluded
                + sum(1 for item in diagnostics if item.get("excluded")),
                "unusable_trade_count": allocation_invalid
                + sum(
                    1
                    for item in diagnostics
                    if not item.get("usable") and not item.get("excluded")
                ),
                "capital_allocation": allocation_report,
                "forced_close_count": sum(
                    1 for item in diagnostics if item.get("forced_close")
                ),
                "core_metrics": _serializable_metrics(core_metrics),
                "candidate_metrics": _serializable_metrics(candidate_metrics),
                "combined_metrics": _serializable_metrics(combined_metrics),
                "formal_delta_vs_full_core": _serializable_metrics(
                    _metric_delta(combined_metrics, core_metrics)
                ),
                "cash_funded_metrics": _serializable_metrics(cash_metrics),
                "diagnostic_delta_vs_90_core_10_cash": _serializable_metrics(
                    _metric_delta(combined_metrics, cash_metrics)
                ),
                "core_candidate_daily_return_correlation": _pearson(
                    core, candidate
                ),
                "candidate_return_series": [round(float(value), 14) for value in candidate],
                "trade_diagnostics": diagnostics,
            }
            return_by_window[window] = candidate

        candidate_return_panel[candidate_id] = return_by_window
        candidate_trade_contributions[candidate_id] = trade_contributions
        if not all(
            bool(
                window_results[window]["capital_allocation"]["cash_nonnegative"]
            )
            for window in WINDOWS
        ):
            raise AssertionError(
                f"cash ledger created leverage for candidate {candidate_id}"
            )
        if not all(
            bool(
                window_results[window]["capital_allocation"][
                    "ending_cash_equity_reconciled"
                ]
            )
            for window in WINDOWS
        ):
            raise AssertionError(
                f"cash/MTM ending equity mismatch for candidate {candidate_id}"
            )
        candidates.append(
            {
                "rank": int(ranking_row.get("rank") or 0),
                "experiment_id": candidate_id,
                "family": ranking_row.get("family"),
                "source_artifact": str(source_path.relative_to(REPO_ROOT)).replace(
                    "\\", "/"
                ),
                "source_artifact_sha256": _sha256_file(source_path),
                "source_trade_count": sum(
                    len(by_window[window]) for window in WINDOWS
                ),
                "usable_trade_count": total_usable,
                "excluded_trade_count": total_excluded,
                "unusable_trade_count": total_unusable,
                "forced_close_count": forced_count,
                "capital_allocation": {
                    "sleeve_initial_capital_usd_per_window": (
                        CANDIDATE_SLEEVE_CAPITAL_USD
                    ),
                    "source_requested_notional_usd": sum(
                        float(
                            window_results[window]["capital_allocation"][
                                "source_requested_notional_usd"
                            ]
                        )
                        for window in WINDOWS
                    ),
                    "allocation_requested_notional_usd": sum(
                        float(
                            window_results[window]["capital_allocation"][
                                "allocation_requested_notional_usd"
                            ]
                        )
                        for window in WINDOWS
                    ),
                    "filled_notional_usd": sum(
                        float(
                            window_results[window]["capital_allocation"][
                                "filled_notional_usd"
                            ]
                        )
                        for window in WINDOWS
                    ),
                    "partial_fill_count": sum(
                        int(
                            window_results[window]["capital_allocation"][
                                "partial_fill_count"
                            ]
                        )
                        for window in WINDOWS
                    ),
                    "zero_fill_count": sum(
                        int(
                            window_results[window]["capital_allocation"][
                                "zero_fill_count"
                            ]
                        )
                        for window in WINDOWS
                    ),
                    "minimum_cash_usd": min(
                        float(
                            window_results[window]["capital_allocation"][
                                "min_cash_usd"
                            ]
                        )
                        for window in WINDOWS
                    ),
                    "peak_invested_notional_usd": max(
                        float(
                            window_results[window]["capital_allocation"][
                                "peak_invested_notional_usd"
                            ]
                        )
                        for window in WINDOWS
                    ),
                    "all_windows_cash_nonnegative": all(
                        bool(
                            window_results[window]["capital_allocation"][
                                "cash_nonnegative"
                            ]
                        )
                        for window in WINDOWS
                    ),
                    "all_windows_ending_cash_equity_reconciled": all(
                        bool(
                            window_results[window]["capital_allocation"][
                                "ending_cash_equity_reconciled"
                            ]
                        )
                        for window in WINDOWS
                    ),
                },
                "normal_exit_cost_reconciliation": {
                    "count": len(normal_errors),
                    "max_abs_error_usd": max(map(abs, normal_errors), default=0.0),
                    "mean_abs_error_usd": statistics.fmean(map(abs, normal_errors))
                    if normal_errors
                    else 0.0,
                    "tolerance_note": "source pnl is rounded to cents",
                },
                "windows": window_results,
            }
        )

    statistics_result = simultaneous_max_t_bounds(
        core_returns,
        candidate_return_panel,
        replicates=bootstrap_replicates,
        block_length=block_length,
        seed=bootstrap_seed,
    )
    statistic_index = {
        candidate_id: index
        for index, candidate_id in enumerate(statistics_result["candidate_ids"])
    }

    for candidate in candidates:
        candidate_id = candidate["experiment_id"]
        index = statistic_index[candidate_id]
        aggregate_ev_delta = sum(
            float(candidate["windows"][window]["formal_delta_vs_full_core"]["expected_value_score"])
            for window in WINDOWS
        )
        aggregate_pnl_delta = sum(
            float(candidate["windows"][window]["formal_delta_vs_full_core"]["total_pnl"])
            for window in WINDOWS
        )
        diagnostic_ev_delta = sum(
            float(candidate["windows"][window]["diagnostic_delta_vs_90_core_10_cash"]["expected_value_score"])
            for window in WINDOWS
        )
        diagnostic_pnl_delta = sum(
            float(candidate["windows"][window]["diagnostic_delta_vs_90_core_10_cash"]["total_pnl"])
            for window in WINDOWS
        )
        aggregate_core_ev = sum(
            float(candidate["windows"][window]["core_metrics"]["expected_value_score"])
            for window in WINDOWS
        )
        aggregate_combined_ev = sum(
            float(candidate["windows"][window]["combined_metrics"]["expected_value_score"])
            for window in WINDOWS
        )
        aggregate_core_pnl = sum(
            float(candidate["windows"][window]["core_metrics"]["total_pnl"])
            for window in WINDOWS
        )
        aggregate_combined_pnl = sum(
            float(candidate["windows"][window]["combined_metrics"]["total_pnl"])
            for window in WINDOWS
        )
        combined_concentration = _concentration(
            [(ticker, CORE_WEIGHT * pnl) for ticker, pnl in core_trade_contributions]
            + [
                # Candidate PnL already comes from the actual $10k sleeve.
                # Multiplying it by 10% again would recreate the former
                # ~$400-per-trade double-scaling bug.
                (ticker, pnl)
                for ticker, pnl in candidate_trade_contributions[candidate_id]
            ]
        )
        drawdown_worse = max(
            float(candidate["windows"][window]["formal_delta_vs_full_core"]["max_drawdown_pct"])
            for window in WINDOWS
        )
        es_worsening: list[float] = []
        for window in WINDOWS:
            core_es = float(
                candidate["windows"][window]["core_metrics"]["expected_shortfall_95"]
            )
            combined_es = float(
                candidate["windows"][window]["combined_metrics"]["expected_shortfall_95"]
            )
            if core_es > 0.0:
                es_worsening.append((combined_es - core_es) / core_es)
            elif combined_es <= 0.0:
                es_worsening.append(0.0)
            else:
                es_worsening.append(float("inf"))
        lower_bound = float(statistics_result["simultaneous_lower_bound"][index])
        multiple_testing_passed = lower_bound > 0.0
        gate_metrics = {
            "capital_neutral": True,
            "core_weight": CORE_WEIGHT,
            "candidate_weight": CANDIDATE_WEIGHT,
            "portfolio_weight_sum": CORE_WEIGHT + CANDIDATE_WEIGHT,
            "family_batch_complete": len(candidates) == 31,
            "expected_family_count": 31,
            "observed_family_count": len(candidates),
            "aggregate_ev_delta": aggregate_ev_delta,
            "aggregate_pnl_delta": aggregate_pnl_delta,
            "affected_trade_count": candidate["usable_trade_count"],
            "affected_window_count": len(WINDOWS),
            "window_contributions": {
                window: {
                    "core_ev": candidate["windows"][window]["core_metrics"]["expected_value_score"],
                    "ev_delta": candidate["windows"][window]["formal_delta_vs_full_core"]["expected_value_score"],
                    "pnl_delta": candidate["windows"][window]["formal_delta_vs_full_core"]["total_pnl"],
                }
                for window in WINDOWS
            },
            "max_drawdown_worse": drawdown_worse,
            "es95_worsening_fraction": max(es_worsening),
            "single_ticker_positive_share": combined_concentration[
                "single_ticker_positive_share"
            ],
            "top_5_contribution_pct": combined_concentration[
                "top_5_contribution_pct"
            ],
            "hhi_concentration": combined_concentration["hhi_concentration"],
            "selection_panel_complete": False,
            "multiple_testing_passed": multiple_testing_passed,
            "simultaneous_ev_delta_lower_bound": lower_bound,
        }
        gate_report = evaluate_portfolio_contribution_gate(gate_metrics)
        candidate["aggregate"] = {
            "formal_vs_full_core": {
                "core_expected_value_score_sum": aggregate_core_ev,
                "combined_expected_value_score_sum": aggregate_combined_ev,
                "aggregate_ev_delta": aggregate_ev_delta,
                "core_total_pnl_sum": aggregate_core_pnl,
                "combined_total_pnl_sum": aggregate_combined_pnl,
                "aggregate_pnl_delta": aggregate_pnl_delta,
            },
            "diagnostic_vs_90_core_10_cash": {
                "aggregate_ev_delta": diagnostic_ev_delta,
                "aggregate_pnl_delta": diagnostic_pnl_delta,
            },
            "worst_max_drawdown_worse": drawdown_worse,
            "worst_es95_worsening_fraction": max(es_worsening),
            "core_concentration_proxy": baseline_concentration,
            "combined_concentration_proxy": combined_concentration,
            "simultaneous_inference": {
                "observed_aggregate_ev_delta": statistics_result[
                    "observed_aggregate_ev_delta"
                ][index],
                "bootstrap_standard_error": statistics_result[
                    "bootstrap_standard_error"
                ][index],
                "simultaneous_90pct_lower_bound": lower_bound,
                "multiple_testing_passed": multiple_testing_passed,
            },
        }
        candidate["gate_metrics"] = gate_metrics
        candidate["gate_report"] = gate_report
        candidate["strict_verdict"] = gate_report["portfolio_verdict"]

    candidates.sort(
        key=lambda row: (
            -float(row["aggregate"]["formal_vs_full_core"]["aggregate_ev_delta"]),
            int(row["rank"]),
            str(row["experiment_id"]),
        )
    )
    best = candidates[0]
    verdict_counts: defaultdict[str, int] = defaultdict(int)
    for candidate in candidates:
        verdict_counts[str(candidate["strict_verdict"])] += 1
    best_formal = best["aggregate"]["formal_vs_full_core"]
    best_worst_drawdown = max(
        float(best["windows"][window]["combined_metrics"]["max_drawdown_pct"])
        for window in WINDOWS
    )
    best_combined_return_sum = sum(
        float(best["windows"][window]["combined_metrics"]["total_return_fraction"])
        for window in WINDOWS
    )
    core_trade_count = sum(
        len(core_payloads[window].get("trades") or []) for window in WINDOWS
    )
    core_window_metrics = {
        window: return_metrics(core_returns[window]) for window in WINDOWS
    }
    core_return_sum = sum(
        float(core_window_metrics[window]["total_return_fraction"])
        for window in WINDOWS
    )
    core_ev_sum = sum(
        float(core_window_metrics[window]["expected_value_score"])
        for window in WINDOWS
    )
    core_pnl_sum = sum(
        float(core_window_metrics[window]["total_pnl"]) for window in WINDOWS
    )
    core_worst_drawdown = max(
        float(core_window_metrics[window]["max_drawdown_pct"])
        for window in WINDOWS
    )
    core_synthetic_sharpe = core_ev_sum / core_return_sum if core_return_sum else 0.0
    best_synthetic_sharpe = (
        float(best_formal["combined_expected_value_score_sum"])
        / best_combined_return_sum
        if best_combined_return_sum
        else 0.0
    )
    closeout_survival_rate = min(
        float(core_payloads[window].get("survival_rate") or 0.0)
        for window in WINDOWS
    )

    panel_note = (
        "selection_panel_complete=false: the preserved ranking contains all 31 "
        "family representatives, but the approximately 264 historical "
        "rejected-positive selection candidates used to choose those "
        "representatives were not persisted as a complete simultaneous panel"
    )
    payload: dict[str, Any] = {
        "schema": "ginger.portfolio_contribution_complete_panel.v1",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "evaluation_mode": "portfolio_contribution",
        "formal_comparison": "0.90*active_core + 0.10*candidate versus 1.00*active_core",
        "diagnostic_comparison": "0.90*active_core + 0.10*candidate versus 0.90*active_core + 0.10*cash",
        "candidate_weight": CANDIDATE_WEIGHT,
        "capital_neutral": True,
        "capital_allocation_contract": {
            "candidate_sleeve_initial_cash_usd_per_window": (
                CANDIDATE_SLEEVE_CAPITAL_USD
            ),
            "no_leverage": True,
            "entry_principal_constraint": "cash/(1+entry_fee)",
            "same_day_entry_allocation": "pro_rata_including_entry_fee",
            "prior_day_exit_cash_reuse": True,
            "same_day_exit_cash_reuse": False,
            "exit_cashflow": "shares*effective_exit_price-exit_fee",
            "profit_and_loss_affect_later_cash": True,
            "candidate_return_initial_capital_usd": (
                CANDIDATE_SLEEVE_CAPITAL_USD
            ),
            "portfolio_return_formula": "0.90*core_return+0.10*candidate_sleeve_return",
            "double_scaling_prohibited": True,
        },
        "selection_panel_complete": False,
        "selection_panel_caveat": panel_note,
        "family_batch_complete": len(candidates) == 31,
        "expected_family_count": 31,
        "observed_family_count": len(candidates),
        "candidate_count": len(candidates),
        "input_identity": {
            "ranking_artifact": str(_repo_path(ranking_path).relative_to(REPO_ROOT)).replace("\\", "/"),
            "ranking_sha256": _sha256_file(ranking_path),
            "core_artifacts": {
                window: {
                    "path": str(_repo_path(core_artifact_paths[window]).relative_to(REPO_ROOT)).replace("\\", "/"),
                    "sha256": _sha256_file(core_artifact_paths[window]),
                    "return_series_sha256": core_payloads[window]
                    .get("sharpe_inference", {})
                    .get("return_series_sha256"),
                }
                for window in WINDOWS
            },
            "warehouse": str(_repo_path(warehouse_path).relative_to(REPO_ROOT)).replace("\\", "/"),
            "warehouse_consulted": ohlcv_snapshot_path is None,
            "ohlcv_source_mode": snapshot["mode"],
            "materialized_ohlcv_snapshot": snapshot,
        },
        "cost_contract": {
            "all_in_roundtrip_fraction_of_filled_notional": (
                2.0 * FORCED_EXIT_SLIPPAGE_FRACTION
                + 2.0 * ONE_WAY_COST_FRACTION
            ),
            "roundtrip_fraction_of_filled_notional": 2.0
            * ONE_WAY_COST_FRACTION,
            "entry_fraction_of_filled_notional": ONE_WAY_COST_FRACTION,
            "exit_fraction_of_filled_notional": ONE_WAY_COST_FRACTION,
            "source_entry_price_includes_buy_slippage_fraction": 0.0005,
            "source_normal_exit_price_includes_sell_slippage_fraction": 0.0005,
            "forced_exit_warehouse_raw_close_sell_slippage_fraction": (
                FORCED_EXIT_SLIPPAGE_FRACTION
            ),
            "forced_exit_effective_price_formula": (
                "warehouse_raw_close*(1-forced_exit_sell_slippage_fraction)"
            ),
        },
        "boundary_contract": {
            "calendar_source": "active post-MTM core return_series dates",
            "entry_after_window_end": "excluded",
            "exit_after_window_end": "force close at final calendar warehouse close",
            "normal_exit": "source artifact exit_price",
        },
        "simultaneous_inference": statistics_result,
        "verdict_counts": dict(sorted(verdict_counts.items())),
        "best_candidate": {
            "experiment_id": best["experiment_id"],
            "family": best["family"],
            "strict_verdict": best["strict_verdict"],
            "aggregate": best["aggregate"],
            "hard_failures": best["gate_report"]["hard_failures"],
            "evidence_blockers": best["gate_report"]["evidence_blockers"],
        },
        "strict_verdict": best["strict_verdict"],
        "reproduction_commands": {
            "materialize_from_warehouse": (
                ".\\.venv\\Scripts\\python.exe -B "
                "quant\\portfolio_contribution_batch.py"
            ),
            "frozen_snapshot_replay": (
                ".\\.venv\\Scripts\\python.exe -B "
                "quant\\portfolio_contribution_batch.py "
                "--ohlcv-snapshot "
                f"{snapshot['path']} --ohlcv-snapshot-sha256 "
                f"{snapshot['gzip_sha256']}"
            ),
        },
        "candidates": candidates,
        # Generic closeout compatibility fields, intentionally representing
        # the highest formal aggregate-EV combined candidate.
        "expected_value_score": best_formal["combined_expected_value_score_sum"],
        "sharpe_daily": best_synthetic_sharpe,
        "total_pnl": best_formal["combined_total_pnl_sum"],
        "max_drawdown_pct": best_worst_drawdown,
        "total_trades": core_trade_count + int(best["usable_trade_count"]),
        "survival_rate": closeout_survival_rate,
        "synthetic_closeout_only": True,
        "synthetic_sharpe_definition": "aggregate_window_ev_sum/aggregate_window_return_fraction_sum",
        "benchmarks": {
            # Despite the historical ``_pct`` suffix, backtest artifacts store
            # this as a return fraction (1.0 == +100%).
            "strategy_total_return_pct": best_combined_return_sum,
        },
    }
    summary: dict[str, Any] = {
        "schema": "ginger.portfolio_contribution_complete_panel_summary.v1",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": payload["generated_at"],
        "candidate_count": len(candidates),
        "family_batch_complete": payload["family_batch_complete"],
        "expected_family_count": payload["expected_family_count"],
        "observed_family_count": payload["observed_family_count"],
        "selection_panel_complete": False,
        "selection_panel_caveat": panel_note,
        "formal_comparison": payload["formal_comparison"],
        "diagnostic_comparison": payload["diagnostic_comparison"],
        "verdict_counts": payload["verdict_counts"],
        "best_candidate": payload["best_candidate"],
        "strict_verdict": payload["strict_verdict"],
        "capital_allocation_contract": payload["capital_allocation_contract"],
        "materialized_ohlcv_snapshot": snapshot,
        "bootstrap": {
            key: statistics_result[key]
            for key in (
                "confidence",
                "replicates",
                "block_length",
                "seed",
                "critical_max_t",
                "bootstrap_matrix_shape",
            )
        },
        "expected_value_score": payload["expected_value_score"],
        "sharpe_daily": payload["sharpe_daily"],
        "total_pnl": payload["total_pnl"],
        "max_drawdown_pct": payload["max_drawdown_pct"],
        "total_trades": payload["total_trades"],
        "survival_rate": payload["survival_rate"],
        "synthetic_closeout_only": payload["synthetic_closeout_only"],
        "synthetic_sharpe_definition": payload["synthetic_sharpe_definition"],
        "benchmarks": payload["benchmarks"],
    }
    core_close_summary: dict[str, Any] = {
        "schema": "ginger.portfolio_contribution_core_close_summary.v1",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": payload["generated_at"],
        "role": "before_active_core",
        "synthetic_closeout_only": True,
        "synthetic_sharpe_definition": (
            "aggregate_window_ev_sum/aggregate_window_return_fraction_sum"
        ),
        "windows": {
            window: _serializable_metrics(core_window_metrics[window])
            for window in WINDOWS
        },
        "expected_value_score": core_ev_sum,
        "sharpe_daily": core_synthetic_sharpe,
        "total_pnl": core_pnl_sum,
        "max_drawdown_pct": core_worst_drawdown,
        "total_trades": core_trade_count,
        "survival_rate": closeout_survival_rate,
        "benchmarks": {"strategy_total_return_pct": core_return_sum},
    }
    main_path = output / "portfolio_contribution_complete_panel.json"
    summary_path = output / "portfolio_contribution_complete_panel_summary.json"
    core_summary_path = output / "portfolio_contribution_core_close_summary.json"
    main_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    core_summary_path.write_text(
        json.dumps(core_close_summary, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return payload, summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ranking-artifact", default=str(DEFAULT_RANKING))
    parser.add_argument("--warehouse", default=str(DEFAULT_WAREHOUSE))
    parser.add_argument("--ohlcv-snapshot")
    parser.add_argument("--ohlcv-snapshot-sha256")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument(
        "--bootstrap-replicates",
        type=int,
        default=DEFAULT_BOOTSTRAP_REPLICATES,
    )
    parser.add_argument("--bootstrap-seed", type=int, default=DEFAULT_BOOTSTRAP_SEED)
    parser.add_argument("--block-length", type=int, default=DEFAULT_BLOCK_LENGTH)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    _, summary = run_batch(
        ranking_path=args.ranking_artifact,
        warehouse_path=args.warehouse,
        ohlcv_snapshot_path=args.ohlcv_snapshot,
        ohlcv_snapshot_sha256=args.ohlcv_snapshot_sha256,
        output_dir=args.output_dir,
        bootstrap_replicates=args.bootstrap_replicates,
        bootstrap_seed=args.bootstrap_seed,
        block_length=args.block_length,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
