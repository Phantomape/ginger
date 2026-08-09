"""exp-20260718-007: formal same-issuer dual-class spread evaluator.

The runner owns measurement only.  All signal, arbitration, sizing, cooldown,
entry, exit, cost, carry, and window-settlement behavior lives in the shared
default-off helper.  Candidate bars are read cold-only from the broad SQLite
warehouse table, hash-bound in the single output artifact, and truncated at
each independently replayed fixed-window end.

Usage:

    python -B quant/experiments/exp_20260718_007_sec_same_issuer_dual_class_spread.py evaluate
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd


EXPERIMENT_ID = "exp-20260718-007"
SLUG = "sec_same_issuer_dual_class_spread"
REPO_ROOT = Path(__file__).resolve().parents[2]
for import_path in (REPO_ROOT, REPO_ROOT / "quant"):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import sec_same_issuer_dual_class_spread_paper_sleeve as sleeve  # noqa: E402
from data_paths import atomic_write_json  # noqa: E402
from portfolio_contribution_batch import (  # noqa: E402
    core_calendar_and_returns,
    return_metrics,
)


ACTIVE_BASELINE = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_cash_feasible_20260715.json"
)
WAREHOUSE_PATH = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"
SEC_MAPPING_PATH = REPO_ROOT / "data" / "reference" / "sec_company_tickers.json"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260718_007_{SLUG}.json"

EXPECTED_SOURCE_HASHES = {
    "baseline": "4e9ef413126c947b9712fd0879b83c74160f787898860987d204bfc9d60f7731",
    "warehouse": "d66b3f05983b35517ea2bef57e43092d6ddb04a0162d6d82ef2499b02960ff86",
    "sec_mapping": "d55f2195f33c1baea171e73042ef209bd2c233c5df425a6edad50f7d5511aba2",
}

WINDOWS: dict[str, dict[str, str]] = {
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
        "snapshot_sha256": "8554e47aa1a5d36a21c40052e0d69f062cbc8915600867363f66b31377efb6ee",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
        "snapshot_sha256": "7cae08e8c957a81831f37bc289379644d979d863cdb4fc51a39536822d570379",
    },
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
        "snapshot_sha256": "7f7d018f8a3ea4074fb7f3284be1106387b8fbba5bb98e0f29d8a91afa8468b0",
    },
}

WAREHOUSE_QUERY_START = "2023-08-29"
CORE_WEIGHT = 0.90
CANDIDATE_WEIGHT = 0.10
CORE_CAPITAL_USD = 100_000.0
CANDIDATE_INITIAL_NAV_USD = 10_000.0
BASELINE_EV = 6.2057
BASELINE_PNL_USD = 130_992.36
MIN_FUNDED_CLOSED_PAIRS = 30
MIN_PAIR_IDENTITIES = 3
MIN_NONNEGATIVE_WINDOWS = 2
MIN_SURVIVAL_RATE = 0.05
MAX_ABS_SPY_BETA = 0.10
MAX_STANDALONE_DRAWDOWN = 0.05
MAX_PAIR_CLOSE_SHARE = 0.50
MAX_PAIR_CLOSE_HHI = 0.35
MAX_MATERIAL_REGRESSED_WINDOWS = 1
WINDOW_EV_MATERIALITY_FRACTION = 0.01
MAX_DRAWDOWN_DRIFT = 0.005
FLOAT_TOLERANCE = 1e-7

HYPOTHESIS = (
    "For five price-provenance-admitted, official-SEC same-CIK dual-class "
    "pairs, a class premium far from its strictly-prior robust anchor should "
    "converge after two-leg costs and short carry."
)

PIT_CAVEAT = (
    "The official SEC company-tickers input is a current snapshot, not an "
    "effective-dated historical identity surface. Historical results are "
    "conditional on the frozen identity whitelist and exact cold OHLCV panel."
)
LIVE_BLOCKERS = [
    "effective_dated_sec_identity_missing",
    "broker_locate_missing",
    "broker_short_size_missing",
]


class EvaluationContractError(RuntimeError):
    """A frozen source, helper, or measurement invariant failed closed."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _repo_rel(path: str | Path) -> str:
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(resolved).replace("\\", "/")


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_sha(payload: Any) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=lambda value: (
            value.isoformat()
            if isinstance(value, (date, datetime, pd.Timestamp))
            else value.item()
            if isinstance(value, np.generic)
            else str(value)
        ),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise EvaluationContractError(f"expected JSON object: {path}")
    return payload


def _finite(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _serializable_metrics(values: Sequence[float], *, capital: float) -> dict[str, Any]:
    """Apply the active display-compatible EV contract to dated returns."""
    result = dict(return_metrics(np.asarray(values, dtype=float), capital=capital))
    total_return = float(result["total_return_fraction"])
    sharpe = float(result["sharpe_daily"])
    pnl = float(result["total_pnl"])
    drawdown = float(result["max_drawdown_pct"])
    result["total_pnl_full_precision"] = pnl
    result["total_pnl"] = round(pnl, 2)
    result["sharpe_daily_full_precision"] = sharpe
    result["sharpe_daily"] = round(sharpe, 2)
    result["max_drawdown_full_precision"] = drawdown
    result["max_drawdown_pct"] = round(drawdown, 4)
    result["expected_value_score_full_precision"] = total_return * abs(sharpe)
    result["strategy_total_return_public"] = round(total_return, 4)
    result["expected_value_score"] = round(
        result["strategy_total_return_public"] * abs(result["sharpe_daily"]), 4
    )
    return {
        key: int(value)
        if isinstance(value, (int, np.integer))
        else float(value)
        if isinstance(value, (float, np.floating))
        else value
        for key, value in result.items()
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


def _baseline_window_map(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("windows")
    if not isinstance(rows, list):
        raise EvaluationContractError("active baseline has no windows list")
    result = {
        str(row.get("label")): dict(row)
        for row in rows
        if isinstance(row, Mapping) and row.get("label")
    }
    if set(result) != set(WINDOWS):
        raise EvaluationContractError(f"baseline window drift: {sorted(result)}")
    return result


def _load_baseline() -> dict[str, Any]:
    baseline_hash = _sha256_file(ACTIVE_BASELINE)
    if baseline_hash != EXPECTED_SOURCE_HASHES["baseline"]:
        raise EvaluationContractError("active baseline hash drift")
    baseline = _read_json(ACTIVE_BASELINE)
    aggregate = baseline.get("aggregate") or {}
    if not (
        baseline.get("experiment_id") == "exp-20260715-010"
        and _finite(aggregate.get("expected_value_score_sum")) == BASELINE_EV
        and _finite(aggregate.get("total_pnl_sum")) == BASELINE_PNL_USD
    ):
        raise EvaluationContractError("active baseline anchor drift")
    baseline_windows = _baseline_window_map(baseline)
    core_dates: dict[str, list[date]] = {}
    core_returns: dict[str, np.ndarray] = {}
    core_identity: dict[str, Any] = {}
    curve_checks: dict[str, Any] = {}
    for label, spec in WINDOWS.items():
        row = baseline_windows[label]
        if (
            str(row.get("start")) != spec["start"]
            or str(row.get("end")) != spec["end"]
            or str(row.get("source")) != spec["snapshot"]
        ):
            raise EvaluationContractError(f"baseline identity drift: {label}")
        snapshot_path = REPO_ROOT / spec["snapshot"]
        if _sha256_file(snapshot_path) != spec["snapshot_sha256"]:
            raise EvaluationContractError(f"snapshot hash drift: {label}")
        artifact_path = REPO_ROOT / str(row["path"])
        artifact_hash = _sha256_file(artifact_path)
        if artifact_hash != str(row.get("artifact_sha256")):
            raise EvaluationContractError(f"core artifact hash drift: {label}")
        artifact = _read_json(artifact_path)
        calendar, returns = core_calendar_and_returns(artifact)
        replay_metrics = _serializable_metrics(returns, capital=CORE_CAPITAL_USD)
        checks = {
            "pnl_within_2c": abs(replay_metrics["total_pnl"] - float(row["total_pnl"])) <= 0.02,
            "sharpe_roundtrip": replay_metrics["sharpe_daily"] == float(row["sharpe_daily"]),
            "ev_roundtrip": replay_metrics["expected_value_score"] == float(row["expected_value_score"]),
            "drawdown_roundtrip": replay_metrics["max_drawdown_pct"] == float(row["max_drawdown_pct"]),
            "return_hash_declared": artifact.get("sharpe_inference", {}).get(
                "return_series_sha256"
            )
            == row.get("daily_return_series_sha256"),
        }
        if not all(checks.values()):
            raise EvaluationContractError(f"baseline curve drift {label}: {checks}")
        core_dates[label] = calendar
        core_returns[label] = returns
        curve_checks[label] = checks
        core_identity[label] = {
            "path": _repo_rel(artifact_path),
            "sha256": artifact_hash,
            "daily_return_series_sha256": row.get("daily_return_series_sha256"),
        }
    return {
        "payload": baseline,
        "windows": baseline_windows,
        "core_dates": core_dates,
        "core_returns": core_returns,
        "core_identity": core_identity,
        "curve_checks": curve_checks,
        "sha256": baseline_hash,
    }


def _warehouse_rows(end: str) -> list[dict[str, Any]]:
    tickers = sorted({*sleeve.FROZEN_IDENTITY_TICKERS, "SPY"})
    placeholders = ",".join("?" for _ in tickers)
    sql = f"""
        SELECT ticker, date, open, high, low, close, volume, source, updated_at
        FROM ohlcv
        WHERE ticker IN ({placeholders}) AND date >= ? AND date <= ?
        ORDER BY ticker, date
    """
    uri = f"file:{WAREHOUSE_PATH.resolve().as_posix()}?mode=ro"
    rows: list[dict[str, Any]] = []
    with sqlite3.connect(uri, uri=True) as conn:
        for raw in conn.execute(sql, [*tickers, WAREHOUSE_QUERY_START, end]):
            rows.append(
                {
                    "ticker": str(raw[0]),
                    "date": str(raw[1])[:10],
                    "open": float(raw[2]),
                    "high": float(raw[3]),
                    "low": float(raw[4]),
                    "close": float(raw[5]),
                    "volume": float(raw[6]),
                    "source": str(raw[7]),
                    "updated_at": str(raw[8]),
                }
            )
    return rows


def _rows_to_frames(rows: Sequence[Mapping[str, Any]]) -> dict[str, pd.DataFrame]:
    by_ticker: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_ticker[str(row["ticker"])].append(
            {
                "Date": row["date"],
                "Open": row["open"],
                "High": row["high"],
                "Low": row["low"],
                "Close": row["close"],
                "Volume": row["volume"],
            }
        )
    result: dict[str, pd.DataFrame] = {}
    for ticker, ticker_rows in by_ticker.items():
        frame = pd.DataFrame(ticker_rows)
        frame["Date"] = pd.to_datetime(frame["Date"])
        frame = frame.set_index("Date").sort_index()
        frame.index.name = None
        result[ticker] = frame[["Open", "High", "Low", "Close", "Volume"]]
    return result


def _ticker_identity(rows: Sequence[Mapping[str, Any]], start: str) -> dict[str, Any]:
    sources = Counter(str(row["source"]) for row in rows)
    updated = Counter(str(row["updated_at"]) for row in rows)
    prior = [row for row in rows if str(row["date"]) < start]
    within = [row for row in rows if str(row["date"]) >= start]
    return {
        "row_count": len(rows),
        "warmup_row_count": len(prior),
        "window_row_count": len(within),
        "date_min": rows[0]["date"] if rows else None,
        "date_max": rows[-1]["date"] if rows else None,
        "sources": dict(sorted(sources.items())),
        "updated_at_counts": dict(sorted(updated.items())),
        "ticker_date_sha256": _canonical_sha(
            [[row["ticker"], row["date"]] for row in rows]
        ),
        "ohlcv_sha256": _canonical_sha(
            [
                [
                    row["ticker"],
                    row["date"],
                    row["open"],
                    row["high"],
                    row["low"],
                    row["close"],
                    row["volume"],
                ]
                for row in rows
            ]
        ),
        "source_rowset_sha256": _canonical_sha(list(rows)),
    }


def _pair_dependency_audit(
    rows_by_ticker: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    start: str,
    end: str,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    economic_ids = {str(row["pair_id"]) for row in sleeve.FROZEN_PAIRS}
    for pair in sleeve.FROZEN_IDENTITY_PAIRS:
        pair_id = str(pair["pair_id"])
        left = str(pair["left_ticker"])
        right = str(pair["right_ticker"])
        left_rows = list(rows_by_ticker.get(left, ()))
        right_rows = list(rows_by_ticker.get(right, ()))
        left_dates = {str(row["date"]) for row in left_rows}
        right_dates = {str(row["date"]) for row in right_rows}
        common = left_dates & right_dates
        common_prior = sorted(day for day in common if day < start)
        common_window = sorted(day for day in common if start <= day <= end)
        reasons: list[str] = []
        if pair_id not in economic_ids:
            reasons.append("outcome_blind_price_provenance_exclusion")
        if len(common_prior) < sleeve.ROBUST_LOOKBACK_SESSIONS:
            reasons.append("insufficient_pair_common_warmup")
        if not common_window:
            reasons.append("no_pair_common_window_rows")
        left_sources = sorted({str(row["source"]) for row in left_rows})
        right_sources = sorted({str(row["source"]) for row in right_rows})
        left_updated = sorted({str(row["updated_at"]) for row in left_rows})
        right_updated = sorted({str(row["updated_at"]) for row in right_rows})
        if pair_id in economic_ids:
            if left_sources != ["yfinance"] or right_sources != ["yfinance"]:
                reasons.append("admitted_pair_not_same_yfinance_cold_source")
            if pair_id != "Z/ZG" and left_updated != right_updated:
                reasons.append("admitted_pair_adjustment_vintage_mismatch")
        result[pair_id] = {
            "cik": int(pair["cik"]),
            "left_ticker": left,
            "right_ticker": right,
            "identity_audited": True,
            "economically_admitted": pair_id in economic_ids and not reasons,
            "dependency_passed": pair_id in economic_ids and not reasons,
            "exclusion_reasons": reasons,
            "strictly_prior_common_session_count": len(common_prior),
            "window_common_session_count": len(common_window),
            "left_sources": left_sources,
            "right_sources": right_sources,
            "left_updated_at": left_updated,
            "right_updated_at": right_updated,
            "same_exact_updated_at": left_updated == right_updated,
            "provenance_caveat": (
                "same_vendor_fetches_approximately_12h_apart_hash_bound_panel"
                if pair_id == "Z/ZG"
                else "GOOG_mixed_snapshot_vintages_vs_GOOGL_yfinance"
                if pair_id == "GOOG/GOOGL"
                else None
            ),
        }
    return result


def _dated_candidate_returns(
    replay: Mapping[str, Any],
    calendar: Sequence[date],
) -> tuple[np.ndarray, list[dict[str, Any]], dict[str, Any]]:
    raw_rows = replay.get("daily_returns")
    if not isinstance(raw_rows, list):
        raise EvaluationContractError("helper daily_returns is not a list")
    by_date: dict[str, float] = {}
    duplicates: list[str] = []
    for row in raw_rows:
        if not isinstance(row, Mapping):
            raise EvaluationContractError("helper daily return row is not an object")
        day = str(row.get("as_of") or "")[:10]
        value = _finite(row.get("daily_return"))
        if not day or value is None or value <= -1.0:
            raise EvaluationContractError(f"invalid helper return row: {row}")
        if day in by_date:
            duplicates.append(day)
        by_date[day] = value
    if duplicates:
        raise EvaluationContractError(f"duplicate helper return dates: {duplicates}")
    dates = [value.isoformat() for value in calendar]
    missing = [day for day in dates if day not in by_date]
    if missing:
        raise EvaluationContractError(f"candidate return dates missing: {missing[:5]}")
    values = np.asarray([by_date[day] for day in dates], dtype=float)
    rows = [
        {"date": day, "return": float(value)}
        for day, value in zip(dates, values)
    ]
    return values, rows, {
        "helper_row_count": len(raw_rows),
        "core_calendar_count": len(dates),
        "missing_candidate_dates": missing,
        "extra_helper_dates_ignored": sorted(set(by_date) - set(dates)),
        "aligned_by_exact_date": True,
    }


def _spy_returns(frame: pd.DataFrame, calendar: Sequence[date]) -> np.ndarray:
    if frame is None or frame.empty:
        raise EvaluationContractError("cold SPY frame is missing")
    closes = {
        str(index.date()): float(row["Close"])
        for index, row in frame.sort_index().iterrows()
    }
    ordered = sorted(closes)
    previous = {current: prior for prior, current in zip(ordered, ordered[1:])}
    result: list[float] = []
    for value in calendar:
        day = value.isoformat()
        prior = previous.get(day)
        if prior is None or day not in closes:
            raise EvaluationContractError(f"cold SPY return unavailable: {day}")
        result.append(closes[day] / closes[prior] - 1.0)
    return np.asarray(result, dtype=float)


def _beta_corr(values: np.ndarray, benchmark: np.ndarray) -> dict[str, float | None]:
    if len(values) != len(benchmark) or len(values) < 3:
        return {"beta": None, "correlation": None}
    variance = float(np.var(benchmark, ddof=1))
    beta = (
        float(np.cov(values, benchmark, ddof=1)[0, 1] / variance)
        if variance > 0.0
        else None
    )
    correlation = (
        float(np.corrcoef(values, benchmark)[0, 1])
        if float(np.std(values)) > 0.0 and float(np.std(benchmark)) > 0.0
        else None
    )
    return {"beta": beta, "correlation": correlation}


def _gate2_trade_contract(trades: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    required = (
        "entry_date",
        "target_price",
        "target_price_role",
        "exit_date",
        "pair_id",
        "long_ticker",
        "short_ticker",
        "long_entry_open",
        "short_entry_open",
        "long_exit_close",
        "short_exit_close",
        "gross_pnl_usd",
        "total_trade_cost_usd",
        "short_carry_usd",
        "net_pnl_usd",
        "entry_dollar_imbalance",
    )
    failures: list[str] = []
    for index, trade in enumerate(trades):
        trade_id = f"{trade.get('pair_id', index)}:{trade.get('entry_date', '')}"
        missing = [field for field in required if field not in trade]
        if missing:
            failures.append(f"missing_fields:{trade_id}:{','.join(missing)}")
            continue
        if not str(trade.get("entry_date") or ""):
            failures.append(f"empty_entry_date:{trade_id}")
        if not (
            trade.get("target_price") is None
            and trade.get("target_price_role") == "not_applicable_pair_spread_exit"
        ):
            failures.append(f"target_price_contract:{trade_id}")
        imbalance = _finite(trade.get("entry_dollar_imbalance"))
        if imbalance is None or imbalance > sleeve.MAX_ENTRY_DOLLAR_IMBALANCE + 1e-12:
            failures.append(f"entry_imbalance:{trade_id}:{imbalance}")
        expected_net = (
            float(trade["gross_pnl_usd"])
            - float(trade["total_trade_cost_usd"])
            - float(trade["short_carry_usd"])
        )
        if abs(expected_net - float(trade["net_pnl_usd"])) > 1e-7:
            failures.append(f"pnl_identity:{trade_id}")
        if str(trade.get("pair_id")) not in {
            str(row["pair_id"]) for row in sleeve.FROZEN_PAIRS
        }:
            failures.append(f"ineligible_pair_funded:{trade_id}")
    return {
        "passed": not failures,
        "trade_count": len(trades),
        "required_fields": list(required),
        "entry_date_and_target_price_checked": True,
        "failures": failures,
    }


def _aggregate_metrics(
    windows: Mapping[str, Mapping[str, Any]], key: str
) -> dict[str, Any]:
    return {
        "expected_value_score_sum": round(
            sum(float(row[key]["expected_value_score"]) for row in windows.values()),
            4,
        ),
        "total_pnl_sum": round(
            sum(float(row[key]["total_pnl"]) for row in windows.values()), 2
        ),
        "worst_max_drawdown_pct": max(
            float(row[key]["max_drawdown_pct"]) for row in windows.values()
        ),
    }


def evaluate() -> dict[str, Any]:
    if sleeve.MAX_ENTRY_DOLLAR_IMBALANCE != 0.05:
        raise EvaluationContractError("helper sizing contract drift")
    source_hashes = {
        "baseline": _sha256_file(ACTIVE_BASELINE),
        "warehouse": _sha256_file(WAREHOUSE_PATH),
        "sec_mapping": _sha256_file(SEC_MAPPING_PATH),
        "helper": _sha256_file(Path(sleeve.__file__)),
        "runner": _sha256_file(Path(__file__)),
    }
    source_hash_checks = {
        key: source_hashes[key] == expected
        for key, expected in EXPECTED_SOURCE_HASHES.items()
    }
    if not all(source_hash_checks.values()):
        raise EvaluationContractError(f"frozen source hash drift: {source_hash_checks}")

    baseline = _load_baseline()
    identity = sleeve.assert_frozen_sec_identities(SEC_MAPPING_PATH)
    if identity.get("source_sha256") != EXPECTED_SOURCE_HASHES["sec_mapping"]:
        raise EvaluationContractError("helper SEC source hash drift")
    if identity.get("admitted_pair_count") != 5:
        raise EvaluationContractError("economic pair whitelist count drift")
    if [row.get("pair_id") for row in identity.get("excluded_identity_candidates", [])] != [
        "GOOG/GOOGL"
    ]:
        raise EvaluationContractError("price-provenance exclusion drift")

    all_rows = _warehouse_rows(max(spec["end"] for spec in WINDOWS.values()))
    if not all_rows:
        raise EvaluationContractError("cold warehouse query returned no rows")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    panel_path = OUT_DIR / "cold_ohlcv_panel.json"
    panel_payload = {
        "schema": "exp_20260718_007_cold_ohlcv_panel_v1",
        "query_start": WAREHOUSE_QUERY_START,
        "query_end": max(spec["end"] for spec in WINDOWS.values()),
        "hot_overlay_used": False,
        "rows": all_rows,
    }
    atomic_write_json(panel_payload, panel_path, indent=2, ensure_ascii=True)
    panel_file_hash = _sha256_file(panel_path)
    panel_rowset_hash = _canonical_sha(all_rows)

    rows_by_ticker_all: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in all_rows:
        rows_by_ticker_all[str(row["ticker"])].append(dict(row))

    windows: dict[str, Any] = {}
    all_trades: list[dict[str, Any]] = []
    candidate_vectors: list[np.ndarray] = []
    spy_vectors: list[np.ndarray] = []
    gate2_failures: list[str] = []
    for label, spec in WINDOWS.items():
        rows = [row for row in all_rows if str(row["date"]) <= spec["end"]]
        rows_by_ticker: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            rows_by_ticker[str(row["ticker"])].append(dict(row))
        pair_audit = _pair_dependency_audit(
            rows_by_ticker,
            start=spec["start"],
            end=spec["end"],
        )
        expected_core_dates = {
            value.isoformat() for value in baseline["core_dates"][label]
        }
        for pair_id in {str(row["pair_id"]) for row in sleeve.FROZEN_PAIRS}:
            audit = pair_audit[pair_id]
            if not audit["dependency_passed"]:
                gate2_failures.append(f"{label}:pair_dependency:{pair_id}")
            left_dates = {
                str(row["date"])
                for row in rows_by_ticker[audit["left_ticker"]]
            }
            right_dates = {
                str(row["date"])
                for row in rows_by_ticker[audit["right_ticker"]]
            }
            if not expected_core_dates.issubset(left_dates & right_dates):
                gate2_failures.append(f"{label}:core_calendar_coverage:{pair_id}")

        frames = _rows_to_frames(rows)
        replay = sleeve.replay_sec_same_issuer_dual_class_spread_sleeve(
            SEC_MAPPING_PATH,
            frames,
            spec["start"],
            spec["end"],
        )
        candidate_values, candidate_rows, alignment = _dated_candidate_returns(
            replay, baseline["core_dates"][label]
        )
        core_values = baseline["core_returns"][label]
        if len(candidate_values) != len(core_values):
            raise EvaluationContractError(f"return length drift: {label}")
        spy_values = _spy_returns(frames["SPY"], baseline["core_dates"][label])
        blend_values = CORE_WEIGHT * core_values + CANDIDATE_WEIGHT * candidate_values
        cash_values = CORE_WEIGHT * core_values

        before = _serializable_metrics(core_values, capital=CORE_CAPITAL_USD)
        candidate = _serializable_metrics(
            candidate_values, capital=CANDIDATE_INITIAL_NAV_USD
        )
        after = _serializable_metrics(blend_values, capital=CORE_CAPITAL_USD)
        cash_diagnostic = _serializable_metrics(cash_values, capital=CORE_CAPITAL_USD)
        delta = _metric_delta(after, before)
        delta_vs_cash = _metric_delta(after, cash_diagnostic)
        material_regression = (
            delta["expected_value_score"]
            < -WINDOW_EV_MATERIALITY_FRACTION
            * abs(float(before["expected_value_score"]))
            and delta["total_pnl"] < 0.0
        )
        trades = [dict(row) for row in replay.get("trades") or []]
        trade_gate = _gate2_trade_contract(trades)
        summary = dict(replay.get("summary") or {})
        cash_identity_error = float(summary.get("ending_cash_usd") or 0.0) - (
            CANDIDATE_INITIAL_NAV_USD
            + sum(float(row["net_pnl_usd"]) for row in trades)
        )
        window_failures: list[str] = list(trade_gate["failures"])
        if abs(cash_identity_error) > 1e-7:
            window_failures.append(f"cash_conservation:{cash_identity_error}")
        if not summary.get("cash_nonnegative"):
            window_failures.append("negative_cash")
        if not summary.get("open_or_pending_invariant_passed"):
            window_failures.append("open_or_pending_invariant")
        if not summary.get("entry_marked_gross_limit_passed"):
            window_failures.append("entry_gross_limit")
        if int(summary.get("missing_exact_open_pair_mark_count") or 0) != 0:
            window_failures.append("missing_exact_open_pair_mark")
        if int(summary.get("open_pair_count") or 0) != 0:
            window_failures.append("unsettled_open_pair")
        if int(summary.get("pending_pair_count") or 0) != 0:
            window_failures.append("unsettled_pending_pair")
        if window_failures:
            gate2_failures.extend(f"{label}:{value}" for value in window_failures)

        windows[label] = {
            "start": spec["start"],
            "end": spec["end"],
            "before": before,
            "candidate": candidate,
            "after": after,
            "delta": delta,
            "diagnostic_90_core_10_cash": cash_diagnostic,
            "diagnostic_delta_vs_90_core_10_cash": delta_vs_cash,
            "material_regression": material_regression,
            "candidate_spy_beta_correlation": _beta_corr(candidate_values, spy_values),
            "signals_generated": int(summary.get("signals_generated") or 0),
            "signals_survived": int(summary.get("signals_survived") or 0),
            "survival_rate": summary.get("survival_rate"),
            "funded_closed_pair_count": len(trades),
            "gate2": {
                "passed": not window_failures,
                "trade_contract": trade_gate,
                "cash_conservation_error": cash_identity_error,
                "failures": window_failures,
            },
            "pair_dependency_audit": pair_audit,
            "ticker_input_identity": {
                ticker: _ticker_identity(ticker_rows, spec["start"])
                for ticker, ticker_rows in sorted(rows_by_ticker.items())
            },
            "return_alignment": alignment,
            "candidate_daily_returns": candidate_rows,
            "candidate_daily_equity": replay.get("daily_equity"),
            "trades": trades,
            "helper_summary": summary,
            "helper_audit": (replay.get("state") or {}).get("audit"),
            "window_boundary_contract": replay.get("window_boundary_contract"),
        }
        all_trades.extend(trades)
        candidate_vectors.append(candidate_values)
        spy_vectors.append(spy_values)

    before_agg = _aggregate_metrics(windows, "before")
    candidate_agg = _aggregate_metrics(windows, "candidate")
    after_agg = _aggregate_metrics(windows, "after")
    material_windows = [
        label for label, row in windows.items() if row["material_regression"]
    ]
    aggregate_candidate = np.concatenate(candidate_vectors)
    aggregate_spy = np.concatenate(spy_vectors)
    beta_corr = _beta_corr(aggregate_candidate, aggregate_spy)
    counts = Counter(str(row["pair_id"]) for row in all_trades)
    shares = {
        pair_id: count / len(all_trades)
        for pair_id, count in sorted(counts.items())
    } if all_trades else {}
    concentration = {
        "closed_pair_counts": dict(sorted(counts.items())),
        "closed_pair_shares": shares,
        "pair_identity_count": len(counts),
        "maximum_pair_identity_share": max(shares.values(), default=None),
        "pair_identity_hhi": sum(value * value for value in shares.values()),
    }
    signals_generated = sum(int(row["signals_generated"]) for row in windows.values())
    signals_survived = sum(int(row["signals_survived"]) for row in windows.values())
    survival_rate = (
        signals_survived / signals_generated if signals_generated else None
    )
    nonnegative_windows = [
        label
        for label, row in windows.items()
        if float(row["candidate"]["expected_value_score"]) >= 0.0
        and float(row["candidate"]["total_pnl"]) >= 0.0
    ]
    gate2 = {
        "passed": not gate2_failures,
        "failures": gate2_failures,
        "identity_candidate_count": identity.get("identity_candidate_count"),
        "economic_admitted_pair_count": identity.get("admitted_pair_count"),
        "GOOG_GOOGL_funded_count": counts.get("GOOG/GOOGL", 0),
        "cold_only_panel": True,
        "hot_overlay_used": False,
        "all_windows_settled": all(
            int(row["helper_summary"].get("open_pair_count") or 0) == 0
            and int(row["helper_summary"].get("pending_pair_count") or 0) == 0
            for row in windows.values()
        ),
    }
    gate3 = {
        "passed": (
            signals_generated > 0
            and survival_rate is not None
            and survival_rate >= MIN_SURVIVAL_RATE
        ),
        "signals_generated": signals_generated,
        "signals_survived": signals_survived,
        "survival_rate": survival_rate,
        "minimum_survival_rate": MIN_SURVIVAL_RATE,
    }
    economics = {
        "gross_pnl_usd": sum(float(row["gross_pnl_usd"]) for row in all_trades),
        "trade_cost_usd": sum(
            float(row["total_trade_cost_usd"]) for row in all_trades
        ),
        "short_carry_usd": sum(float(row["short_carry_usd"]) for row in all_trades),
        "net_trade_pnl_usd": sum(float(row["net_pnl_usd"]) for row in all_trades),
        "winning_trade_count": sum(float(row["net_pnl_usd"]) > 0.0 for row in all_trades),
        "win_rate": (
            sum(float(row["net_pnl_usd"]) > 0.0 for row in all_trades)
            / len(all_trades)
            if all_trades
            else None
        ),
        "mean_net_pnl_usd": (
            sum(float(row["net_pnl_usd"]) for row in all_trades) / len(all_trades)
            if all_trades
            else None
        ),
        "exit_reason_counts": dict(
            sorted(Counter(str(row["exit_reason"]) for row in all_trades).items())
        ),
    }
    signal_funnel = {
        key: sum(
            int((row.get("helper_audit") or {}).get(key) or 0)
            for row in windows.values()
        )
        for key in (
            "raw_threshold_signals",
            "data_provenance_excluded_threshold_signals",
            "signals_discarded_open_or_pending",
            "signals_blocked_cooldown",
            "signals_generated",
            "signals_selected",
            "entries_funded",
            "pairs_closed",
        )
    }
    standalone_checks = {
        "gate2_passed": gate2["passed"],
        "gate3_passed": gate3["passed"],
        "minimum_30_funded_closed_pairs": len(all_trades) >= MIN_FUNDED_CLOSED_PAIRS,
        "minimum_3_pair_identities": len(counts) >= MIN_PAIR_IDENTITIES,
        "aggregate_ev_positive": candidate_agg["expected_value_score_sum"] > 0.0,
        "aggregate_pnl_positive": candidate_agg["total_pnl_sum"] > 0.0,
        "two_of_three_windows_nonnegative_ev_and_pnl": (
            len(nonnegative_windows) >= MIN_NONNEGATIVE_WINDOWS
        ),
        "absolute_spy_beta_lte_0_10": (
            beta_corr["beta"] is not None
            and abs(float(beta_corr["beta"])) <= MAX_ABS_SPY_BETA
        ),
        "standalone_drawdown_lte_5pct": (
            candidate_agg["worst_max_drawdown_pct"] <= MAX_STANDALONE_DRAWDOWN
        ),
        "maximum_pair_share_lte_50pct": (
            concentration["maximum_pair_identity_share"] is not None
            and float(concentration["maximum_pair_identity_share"])
            <= MAX_PAIR_CLOSE_SHARE
        ),
        "pair_hhi_lte_0_35": concentration["pair_identity_hhi"] <= MAX_PAIR_CLOSE_HHI,
        "cash_and_entry_gross_invariants": all(
            bool(row["helper_summary"].get("cash_nonnegative"))
            and bool(row["helper_summary"].get("entry_marked_gross_limit_passed"))
            and bool(row["helper_summary"].get("open_or_pending_invariant_passed"))
            for row in windows.values()
        ),
    }
    standalone_passed = all(standalone_checks.values())
    dd_drift = (
        float(after_agg["worst_max_drawdown_pct"])
        - float(before_agg["worst_max_drawdown_pct"])
    )
    portfolio_checks = {
        "standalone_candidate_passed": standalone_passed,
        "aggregate_ev_improved_vs_100pct_core": (
            after_agg["expected_value_score_sum"] > before_agg["expected_value_score_sum"]
        ),
        "aggregate_pnl_improved_vs_100pct_core": (
            after_agg["total_pnl_sum"] > before_agg["total_pnl_sum"]
        ),
        "at_most_one_material_window_regression": (
            len(material_windows) <= MAX_MATERIAL_REGRESSED_WINDOWS
        ),
        "drawdown_drift_lte_0_5pp": dd_drift <= MAX_DRAWDOWN_DRIFT,
    }
    portfolio_passed = all(portfolio_checks.values())
    if portfolio_passed:
        decision = "accepted_capital_promoted_default_off_paper_engine"
    elif standalone_passed:
        decision = "accepted_default_off_candidate_not_capital_promoted"
    else:
        decision = "rejected_same_issuer_dual_class_spread_economics"

    payload = {
        "schema": "exp_20260718_007_sec_same_issuer_dual_class_spread_v1",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": _utc_now(),
        "lane": "alpha_search",
        "status": "completed",
        "decision": decision,
        "accepted_alpha": standalone_passed,
        "independent_engine_counted": portfolio_passed,
        "live_ready": False,
        "hypothesis": HYPOTHESIS,
        "policy_bundle": {
            "rule_version": sleeve.RULE_VERSION,
            "identity_contract": identity,
            "price_provenance_contract": sleeve.price_provenance_contract(),
            "selection_contract": sleeve.selection_contract(),
            "cooldown_contract": sleeve.cooldown_contract(),
            "execution_sizing_contract": sleeve.execution_sizing_contract(),
            "window_boundary": {
                "pending": "cancel_without_fill",
                "open": "force_close_at_final_exact_close_with_cost_and_carry",
                "daily_policy_affected": False,
            },
        },
        "source_identity": {
            "hashes": source_hashes,
            "expected_hash_checks": source_hash_checks,
            "cold_panel": {
                "path": _repo_rel(panel_path),
                "file_sha256": panel_file_hash,
                "canonical_rowset_sha256": panel_rowset_hash,
                "row_count": len(all_rows),
                "query_start": WAREHOUSE_QUERY_START,
                "query_end": max(spec["end"] for spec in WINDOWS.values()),
                "hot_overlay_used": False,
            },
            "core_artifacts": baseline["core_identity"],
            "baseline_curve_checks": baseline["curve_checks"],
        },
        "windows": windows,
        "aggregate": {
            "before": before_agg,
            "candidate": {
                **candidate_agg,
                "funded_closed_pair_count": len(all_trades),
                "signals_generated": signals_generated,
                "signals_survived": signals_survived,
                "survival_rate": survival_rate,
                "nonnegative_ev_and_pnl_windows": nonnegative_windows,
                "spy_beta_correlation": beta_corr,
                "concentration": concentration,
                "economics": economics,
                "signal_funnel": signal_funnel,
            },
            "after": after_agg,
            "delta": {
                "expected_value_score": round(
                    after_agg["expected_value_score_sum"]
                    - before_agg["expected_value_score_sum"],
                    4,
                ),
                "total_pnl": round(
                    after_agg["total_pnl_sum"] - before_agg["total_pnl_sum"], 2
                ),
                "worst_max_drawdown_drift": dd_drift,
                "material_regressed_windows": material_windows,
                "material_regressed_window_count": len(material_windows),
            },
        },
        "gate1": {
            "passed": True,
            "baseline_experiment_id": "exp-20260715-010",
            "baseline_expected_value_score": BASELINE_EV,
            "baseline_total_pnl_usd": BASELINE_PNL_USD,
        },
        "gate2": gate2,
        "gate3": gate3,
        "standalone_acceptance": {
            "passed": standalone_passed,
            "checks": standalone_checks,
        },
        "portfolio_promotion": {
            "passed": portfolio_passed,
            "checks": portfolio_checks,
            "weight_contract": "90pct_core_plus_10pct_candidate_constant_mix",
        },
        "production_impact": {
            **sleeve.production_impact(),
            "live_blockers": LIVE_BLOCKERS,
            "pit_caveat": PIT_CAVEAT,
            "run_py_wiring_retained_only_if_standalone_passes": standalone_passed,
        },
        "post_run_interpretation": {
            "engine_claim": (
                "capital_promoted_default_off_paper_engine"
                if portfolio_passed
                else "positive_default_off_candidate_not_engine"
                if standalone_passed
                else "not_an_engine"
            ),
            "parameter_retune_allowed": False,
            "reopen_condition": (
                "new effective-dated identity/borrow evidence or a genuinely new "
                "economic-anchor linkage; do not retune the frozen z/exit/cost policy"
            ),
        },
        "reproduction_command": (
            ".\\.venv\\Scripts\\python.exe -B "
            "quant\\experiments\\exp_20260718_007_sec_same_issuer_dual_class_spread.py "
            "evaluate"
        ),
    }
    atomic_write_json(payload, OUT_JSON, indent=2, ensure_ascii=True)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=("evaluate",), default="evaluate")
    args = parser.parse_args()
    if args.command == "evaluate":
        result = evaluate()
        print(json.dumps({
            "experiment_id": result["experiment_id"],
            "decision": result["decision"],
            "candidate": result["aggregate"]["candidate"],
            "after": result["aggregate"]["after"],
            "delta": result["aggregate"]["delta"],
            "artifact": _repo_rel(OUT_JSON),
        }, ensure_ascii=False, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
