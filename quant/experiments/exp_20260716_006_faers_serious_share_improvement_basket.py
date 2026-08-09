"""exp-20260716-006: FAERS serious-share improvement basket full stack.

The shared helper owns every decision rule: point-in-time source parsing,
strict issuer identity, quarter-over-quarter serious-share comparison,
source-only ranking, entry/exit clocks, basket allocation, and costs.  This
runner owns only frozen-input validation and the preregistered three-window
evaluation against the active cash-feasible baseline.

The preflight artifact is used solely as an identity contract.  Its selected
rows and outcome summaries are deliberately not consumed here.  This runner
does not write experiment tickets, logs, cards, registry state, or live config.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sqlite3
import sys
import tempfile
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


EXPERIMENT_ID = "exp-20260716-006"
REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (REPO_ROOT, QUANT_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from deflated_sharpe import build_report as build_dsr_report  # noqa: E402
from faers_serious_share_improvement_paper_sleeve import (  # noqa: E402
    EVENT_NOTIONAL_USD,
    HOLD_SESSIONS,
    QUARTERS,
    ROUND_TRIP_COST_BPS,
    TRADE_ENABLED,
    build_historical_replay,
    build_paper_snapshot,
)
from quant.evaluator_gates import ExperimentGateThresholds  # noqa: E402
from quant.full_stack_candidate_pool import (  # noqa: E402
    ExecutionEnvelope,
    evaluate_gate4,
    evaluate_live_readiness,
    full_stack_verdict,
)


RAW_DIR = REPO_ROOT / "data" / "tmp" / "faers_preflight_raw"
PREFLIGHT_PATH = REPO_ROOT / "data" / "tmp" / "faers_improvement_candidate_preflight.json"
SOURCE_MANIFEST_PATH = (
    REPO_ROOT / "data" / "non_ohlcv" / "faers_quarterly" / "source_manifest.json"
)
WAREHOUSE_PATH = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"
BASELINE_SUMMARY_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_cash_feasible_20260715.json"
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
RESULT_PATH = OUT_DIR / "exp_20260716_006_faers_serious_share_improvement_basket.json"
BEFORE_PATH = OUT_DIR / "before.json"
AFTER_PATH = OUT_DIR / "after.json"
PREFLIGHT_OUTPUT_PATH = OUT_DIR / "preflight.json"
DSR_PANEL_PATH = OUT_DIR / "deflated_sharpe_panel.json"
DSR_REPORT_PATH = OUT_DIR / "deflated_sharpe_report.json"
PAPER_SNAPSHOT_PATH = (
    REPO_ROOT
    / "data"
    / "paper_sleeves"
    / "faers_serious_share_improvement"
    / "latest_snapshot.json"
)

WINDOWS = OrderedDict(
    (
        ("old_thin", ("2024-10-02", "2025-04-22")),
        ("mid_weak", ("2025-04-23", "2025-10-22")),
        ("late_strong", ("2025-10-23", "2026-04-21")),
    )
)
OHLCV_QUERY_START = "2024-09-01"
MIN_SETTLED_ROWS_PER_WINDOW = 10
MIN_UNIQUE_TICKERS_PER_WINDOW = 10
MAX_TOP1_ROW_SHARE = 0.20
MIN_INDEPENDENT_RELEASE_DECISIONS_PER_WINDOW = 10
MIN_SURVIVAL_RATE = 0.05
MAX_DRAWDOWN_WORSE = 0.005
ROUND_TRIP_COST_PCT = ROUND_TRIP_COST_BPS / 10_000.0
EXPECTED_DSR_ATTEMPTS = 1
PREDICTION = {
    "success_probability": 0.25,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "safety_reporting_mix_not_product_quality",
        "quarterly_signal_absorbed",
        "current_title_sector_survivorship",
        "small_release_count",
        "window_instability",
        "benchmark_underperformance",
    ],
}


class EvaluationContractError(RuntimeError):
    """Raised when a frozen input or evaluation invariant fails closed."""


def _repo_rel(path: Path) -> str:
    return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _canonical_sha(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(
                payload,
                handle,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _bar_date(row: dict[str, Any]) -> str:
    return str(row.get("date") or row.get("Date") or "")[:10]


def _valid_bar(row: dict[str, Any]) -> bool:
    prices = [_number(row.get(field)) for field in ("open", "high", "low", "close")]
    volume = _number(row.get("volume"))
    return bool(
        all(value is not None and value > 0 for value in prices)
        and volume is not None
        and volume >= 0
    )


def _chunks(values: list[str], size: int = 500) -> Iterable[list[str]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def _source_contract() -> tuple[dict[str, str], list[dict[str, Any]], dict[str, Any]]:
    if not PREFLIGHT_PATH.exists():
        raise EvaluationContractError(f"preflight identity missing: {PREFLIGHT_PATH}")
    preflight = _read_json(PREFLIGHT_PATH)
    contract = preflight.get("data_contract") or {}
    failures: list[str] = []

    expected_quarters = [str(value).lower() for value in contract.get("quarters") or []]
    helper_quarters = [str(value).lower() for value in QUARTERS]
    if expected_quarters != helper_quarters:
        failures.append("preflight_helper_quarters_mismatch")
    expected_hashes = {
        str(key).lower(): str(value)
        for key, value in (contract.get("zip_sha256") or {}).items()
    }
    if set(expected_hashes) != set(helper_quarters):
        failures.append("preflight_zip_hash_set_mismatch")

    if not SOURCE_MANIFEST_PATH.exists():
        failures.append("tracked_source_manifest_missing")
        source_manifest: dict[str, Any] = {}
    else:
        source_manifest = _read_json(SOURCE_MANIFEST_PATH)
        if source_manifest.get("schema_version") != 1:
            failures.append("tracked_source_manifest_schema_mismatch")
        manifest_files = {
            str(row.get("quarter") or "").lower(): row
            for row in source_manifest.get("files") or []
        }
        if set(manifest_files) != set(helper_quarters):
            failures.append("tracked_source_manifest_quarters_mismatch")
        for quarter in helper_quarters:
            row = manifest_files.get(quarter) or {}
            if str(row.get("sha256") or "") != expected_hashes.get(quarter):
                failures.append(f"tracked_source_manifest_hash_mismatch:{quarter}")
        if source_manifest.get("raw_files_tracked") is not False:
            failures.append("tracked_source_manifest_raw_cache_contract_mismatch")

    actual_hashes: dict[str, str | None] = {}
    actual_bytes: dict[str, int | None] = {}
    bundle = hashlib.sha256()
    for quarter in helper_quarters:
        path = RAW_DIR / f"faers_ascii_{quarter}.zip"
        if not path.exists():
            failures.append(f"source_zip_missing:{quarter}")
            actual_hashes[quarter] = None
            actual_bytes[quarter] = None
            continue
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
                digest.update(chunk)
                bundle.update(chunk)
        actual_hashes[quarter] = digest.hexdigest()
        actual_bytes[quarter] = path.stat().st_size
        if actual_hashes[quarter] != expected_hashes.get(quarter):
            failures.append(f"source_zip_hash_mismatch:{quarter}")
    actual_bundle = bundle.hexdigest()
    expected_bundle = str(contract.get("concatenated_bundle_sha256") or "")
    if actual_bundle != expected_bundle:
        failures.append("source_bundle_hash_mismatch")

    issuer_manifest = preflight.get("issuer_map") or []
    expected_map_hash = str(contract.get("issuer_map_sha256") or "")
    # This deliberately mirrors the zero-ID preflight serializer.
    actual_map_hash = hashlib.sha256(
        json.dumps(issuer_manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if actual_map_hash != expected_map_hash:
        failures.append("issuer_map_hash_mismatch")
    if len(issuer_manifest) != int(contract.get("issuer_map_entry_count") or -1):
        failures.append("issuer_map_count_mismatch")
    if contract.get("issuer_map_collisions"):
        failures.append("issuer_map_collisions_present")
    if contract.get("short_vertex_fail_closed") is not True:
        failures.append("short_vertex_fail_closed_missing")

    issuer_index: dict[str, str] = {}
    for row in issuer_manifest:
        key = str((row or {}).get("normalized_sender") or "").strip()
        ticker = str((row or {}).get("ticker") or "").strip().upper()
        if not key or not ticker or key in issuer_index:
            failures.append("issuer_map_invalid_or_duplicate_key")
            continue
        issuer_index[key] = ticker
    if "VERTEX" in issuer_index:
        failures.append("ambiguous_short_vertex_mapped")

    audit = {
        "passed": not failures,
        "hard_failures": list(dict.fromkeys(failures)),
        "preflight_identity_path": _repo_rel(PREFLIGHT_PATH),
        "preflight_identity_sha256": _file_sha(PREFLIGHT_PATH),
        "preflight_used_for": "source_and_issuer_identity_only",
        "preflight_outcome_rows_consumed": False,
        "tracked_source_manifest_path": _repo_rel(SOURCE_MANIFEST_PATH),
        "tracked_source_manifest_sha256": (
            _file_sha(SOURCE_MANIFEST_PATH) if SOURCE_MANIFEST_PATH.exists() else None
        ),
        "tracked_source_manifest_raw_files_tracked": source_manifest.get(
            "raw_files_tracked"
        ),
        "raw_dir": _repo_rel(RAW_DIR),
        "raw_dir_role": "untracked_reproducible_download_cache",
        "expected_zip_sha256": expected_hashes,
        "actual_zip_sha256": actual_hashes,
        "actual_zip_bytes": actual_bytes,
        "expected_concatenated_bundle_sha256": expected_bundle,
        "actual_concatenated_bundle_sha256": actual_bundle,
        "expected_issuer_map_sha256": expected_map_hash,
        "actual_issuer_map_sha256": actual_map_hash,
        "issuer_map_entry_count": len(issuer_index),
        "short_vertex_fail_closed": "VERTEX" not in issuer_index,
    }
    if failures:
        raise EvaluationContractError("source contract failed: " + ", ".join(audit["hard_failures"]))
    return issuer_index, issuer_manifest, audit


def _load_ohlcv(tickers: Iterable[str]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    if not WAREHOUSE_PATH.exists():
        raise EvaluationContractError(f"warehouse missing: {WAREHOUSE_PATH}")
    requested = sorted({str(ticker).strip().upper() for ticker in tickers if ticker})
    output: dict[str, list[dict[str, Any]]] = {ticker: [] for ticker in requested}
    rowset_digest = hashlib.sha256()
    with sqlite3.connect(
        f"file:{WAREHOUSE_PATH.as_posix()}?mode=ro", uri=True, timeout=30
    ) as connection:
        connection.row_factory = sqlite3.Row
        for group in _chunks(requested):
            placeholders = ",".join("?" for _ in group)
            query = (
                "SELECT ticker,date,open,high,low,close,volume,source,updated_at "
                f"FROM ohlcv WHERE ticker IN ({placeholders}) AND date>=? "
                "ORDER BY ticker,date"
            )
            for raw in connection.execute(query, (*group, OHLCV_QUERY_START)):
                item = dict(raw)
                ticker = str(item.pop("ticker")).upper()
                output.setdefault(ticker, []).append(item)
                rowset_digest.update(
                    (
                        json.dumps(
                            [ticker, *[item.get(key) for key in (
                                "date", "open", "high", "low", "close", "volume", "source", "updated_at"
                            )]],
                            separators=(",", ":"),
                        )
                        + "\n"
                    ).encode("utf-8")
                )
    missing_references = [ticker for ticker in ("SPY", "QQQ") if not output.get(ticker)]
    if missing_references:
        raise EvaluationContractError(f"reference OHLCV missing: {missing_references}")
    invalid_rows = sum(
        not _valid_bar(row)
        for rows in output.values()
        for row in rows
        if _bar_date(row) <= max(end for _, end in WINDOWS.values())
    )
    return output, {
        "warehouse": _repo_rel(WAREHOUSE_PATH),
        "query_start": OHLCV_QUERY_START,
        "requested_ticker_count": len(requested),
        "covered_ticker_count": sum(bool(rows) for rows in output.values()),
        "row_count": sum(len(rows) for rows in output.values()),
        "invalid_ohlcv_row_count": invalid_rows,
        "rowset_sha256": rowset_digest.hexdigest(),
    }


def _baseline_window_map(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row["label"]): row for row in summary["windows"]}


def _baseline_curve(window: dict[str, Any]) -> list[tuple[str, float]]:
    artifact = _read_json(REPO_ROOT / str(window["path"]))
    series = artifact["sharpe_inference"]["return_series"]
    equity = 100_000.0
    curve: list[tuple[str, float]] = []
    for row in series:
        equity *= 1.0 + float(row["return"])
        curve.append((str(row["date"]), equity))
    expected = 100_000.0 + float(window["total_pnl"])
    if not curve or abs(curve[-1][1] - expected) > 0.02:
        raise EvaluationContractError(
            f"baseline return-series reconstruction drift: {window['label']}"
        )
    return curve


def _bar_index(
    ohlcv: dict[str, list[dict[str, Any]]]
) -> dict[str, dict[str, dict[str, float]]]:
    index: dict[str, dict[str, dict[str, float]]] = {}
    for ticker, rows in ohlcv.items():
        index[ticker] = {}
        for row in rows:
            day = _bar_date(row)
            open_price = _number(row.get("open"))
            close_price = _number(row.get("close"))
            if day and open_price is not None and close_price is not None:
                index[ticker][day] = {"open": open_price, "close": close_price}
    return index


def _entry_price(trade: dict[str, Any]) -> float:
    price = _number(
        trade.get("entry_price")
        if trade.get("entry_price") is not None
        else trade.get("open")
    )
    if price is None or price <= 0:
        raise EvaluationContractError(f"invalid trade entry price: {trade}")
    return price


def _notional(trade: dict[str, Any]) -> float:
    value = _number(
        trade.get("notional_usd")
        if trade.get("notional_usd") is not None
        else trade.get("notional")
    )
    if value is None or value <= 0:
        raise EvaluationContractError(f"invalid trade notional: {trade}")
    return value


def _target_mark_on_date(
    trades: list[dict[str, Any]],
    bars: dict[str, dict[str, dict[str, float]]],
    day: str,
) -> float:
    mark = 0.0
    for trade in trades:
        if day < str(trade["entry_date"]):
            continue
        if day >= str(trade["exit_date"]):
            mark += float(trade["pnl"])
            continue
        close_row = bars.get(str(trade["ticker"]), {}).get(day)
        if close_row is None:
            raise EvaluationContractError(
                f"missing MTM close for {trade['ticker']} on {day}"
            )
        gross = close_row["close"] / _entry_price(trade) - 1.0
        mark += _notional(trade) * (gross - ROUND_TRIP_COST_PCT / 2.0)
    return mark


def _return_series_sha(rows: list[dict[str, Any]]) -> str:
    return _canonical_sha({"schema": "dated_periodic_return_series_v1", "rows": rows})


def _curve_metrics(curve: list[tuple[str, float]], *, trade_count: int) -> dict[str, Any]:
    previous = 100_000.0
    peak = previous
    max_drawdown = 0.0
    returns: list[dict[str, Any]] = []
    for day, equity in curve:
        periodic_return = equity / previous - 1.0 if previous else 0.0
        returns.append({"date": day, "return": periodic_return})
        previous = equity
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, (peak - equity) / peak)
    values = [float(row["return"]) for row in returns]
    sharpe = None
    if len(values) >= 2:
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
        if variance > 0:
            sharpe = mean / math.sqrt(variance) * math.sqrt(252)
    pnl = curve[-1][1] - 100_000.0
    strategy_return = round(pnl / 100_000.0, 4)
    public_sharpe = round(sharpe, 2) if sharpe is not None else None
    return {
        "total_pnl": round(pnl, 2),
        "benchmarks": {"strategy_total_return_pct": strategy_return},
        "sharpe_daily": public_sharpe,
        "sharpe_daily_full_precision": sharpe,
        "expected_value_score": (
            round(strategy_return * abs(public_sharpe), 4)
            if public_sharpe is not None
            else None
        ),
        "expected_value_score_formula": "strategy_total_return_pct * abs(sharpe_daily)",
        "max_drawdown_pct": round(max_drawdown, 4),
        "total_trades": trade_count,
        "return_series": returns,
        "return_series_sha256": _return_series_sha(returns),
    }


def _combine_window(
    baseline: dict[str, Any],
    trades: list[dict[str, Any]],
    bars: dict[str, dict[str, dict[str, float]]],
) -> tuple[dict[str, Any], dict[str, Any], list[tuple[str, float]]]:
    base_curve = _baseline_curve(baseline)
    combined = [
        (day, equity + _target_mark_on_date(trades, bars, day))
        for day, equity in base_curve
    ]
    strategy_return = round(float(baseline["total_pnl"]) / 100_000.0, 4)
    before = {
        "total_pnl": baseline["total_pnl"],
        "benchmarks": {"strategy_total_return_pct": strategy_return},
        "sharpe_daily": baseline["sharpe_daily"],
        "sharpe_daily_full_precision": baseline["sharpe_daily_full_precision"],
        "expected_value_score": round(
            strategy_return * abs(float(baseline["sharpe_daily"])), 4
        ),
        "expected_value_score_formula": "strategy_total_return_pct * abs(sharpe_daily)",
        "max_drawdown_pct": baseline["max_drawdown_pct"],
        "total_trades": baseline["trade_count"],
        "signals_generated": baseline["signals_generated"],
        "signals_survived": baseline["signals_survived"],
        "survival_rate": baseline["survival_rate"],
    }
    if abs(float(before["expected_value_score"]) - float(baseline["expected_value_score"])) > 0.0001:
        raise EvaluationContractError(f"baseline signed-EV drift: {baseline['label']}")
    after = _curve_metrics(combined, trade_count=int(baseline["trade_count"]) + len(trades))
    return before, after, combined


def _aggregate_windows(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "before_expected_value_score_sum": round(
            sum(float(row["before"]["expected_value_score"]) for row in rows.values()), 4
        ),
        "after_expected_value_score_sum": round(
            sum(float(row["after"]["expected_value_score"]) for row in rows.values()), 4
        ),
        "expected_value_score_delta_sum": round(
            sum(float(row["delta"]["expected_value_score"]) for row in rows.values()), 4
        ),
        "before_total_pnl_sum": round(
            sum(float(row["before"]["total_pnl"]) for row in rows.values()), 2
        ),
        "after_total_pnl_sum": round(
            sum(float(row["after"]["total_pnl"]) for row in rows.values()), 2
        ),
        "total_pnl_delta_sum": round(
            sum(float(row["delta"]["total_pnl"]) for row in rows.values()), 2
        ),
        "windows_ev_improved": sum(
            float(row["delta"]["expected_value_score"]) > 0 for row in rows.values()
        ),
        "windows_ev_regressed": sum(
            float(row["delta"]["expected_value_score"]) < 0 for row in rows.values()
        ),
        "windows_pnl_improved": sum(
            float(row["delta"]["total_pnl"]) > 0 for row in rows.values()
        ),
        "windows_pnl_regressed": sum(
            float(row["delta"]["total_pnl"]) < 0 for row in rows.values()
        ),
        "max_drawdown_worse_max": max(
            float(row["delta"]["max_drawdown_pct"]) for row in rows.values()
        ),
    }


def _matched_benchmark_pnl(
    trades: list[dict[str, Any]],
    bars: dict[str, dict[str, dict[str, float]]],
    ticker: str,
) -> tuple[float | None, list[str]]:
    pnl = 0.0
    missing: list[str] = []
    for trade in trades:
        entry = bars.get(ticker, {}).get(str(trade["entry_date"]))
        exit_row = bars.get(ticker, {}).get(str(trade["exit_date"]))
        trade_id = f"{trade.get('quarter')}:{trade.get('ticker')}"
        if entry is None or exit_row is None:
            missing.append(trade_id)
            continue
        benchmark_return = exit_row["close"] / entry["open"] - 1.0 - ROUND_TRIP_COST_PCT
        pnl += _notional(trade) * benchmark_return
    return (round(pnl, 2) if trades and not missing else None), missing


def _standalone_diagnostics(
    trades: list[dict[str, Any]],
    bars: dict[str, dict[str, dict[str, float]]],
) -> dict[str, Any]:
    strategy_pnl = round(sum(float(trade["pnl"]) for trade in trades), 2)
    spy_pnl, spy_missing = _matched_benchmark_pnl(trades, bars, "SPY")
    qqq_pnl, qqq_missing = _matched_benchmark_pnl(trades, bars, "QQQ")
    cash_rv = strategy_pnl if trades else None
    spy_rv = round(strategy_pnl - spy_pnl, 2) if spy_pnl is not None else None
    qqq_rv = round(strategy_pnl - qqq_pnl, 2) if qqq_pnl is not None else None
    checks = {
        "cash_replacement_value_positive": cash_rv is not None and cash_rv > 0,
        "spy_replacement_value_positive": spy_rv is not None and spy_rv > 0,
        "qqq_replacement_value_positive": qqq_rv is not None and qqq_rv > 0,
    }
    return {
        "settled_leg_count": len(trades),
        "independent_release_decision_count": len(
            {str(trade.get("quarter")) for trade in trades}
        ),
        "standalone_net_pnl": strategy_pnl,
        "cash_matched_pnl": 0.0 if trades else None,
        "cash_replacement_value": cash_rv,
        "spy_matched_pnl": spy_pnl,
        "spy_replacement_value": spy_rv,
        "qqq_matched_pnl": qqq_pnl,
        "qqq_replacement_value": qqq_rv,
        "spy_missing_trade_ids": spy_missing,
        "qqq_missing_trade_ids": qqq_missing,
        "benchmark_entry_exit": "same entry open to same session-20 close",
        "benchmark_round_trip_cost_bps": ROUND_TRIP_COST_BPS,
        "checks": checks,
        "passed": bool(trades) and all(checks.values()),
    }


def _selection_summary(trades_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    ticker_count: Counter[str] = Counter()
    ticker_pnl: Counter[str] = Counter()
    for trades in trades_by_window.values():
        for trade in trades:
            ticker = str(trade["ticker"])
            ticker_count[ticker] += 1
            ticker_pnl[ticker] += float(trade["pnl"])
    positive = {ticker: pnl for ticker, pnl in ticker_pnl.items() if pnl > 0}
    positive_total = sum(positive.values())
    shares = (
        sorted((pnl / positive_total for pnl in positive.values()), reverse=True)
        if positive_total > 0
        else []
    )
    releases_by_window = {
        label: sorted({str(row["quarter"]) for row in trades_by_window[label]})
        for label in WINDOWS
    }
    return {
        "statistical_unit": "one_equal_weight_quarterly_release_basket",
        "settled_leg_count": sum(len(rows) for rows in trades_by_window.values()),
        "independent_release_decision_count": sum(
            len(quarters) for quarters in releases_by_window.values()
        ),
        "by_window_settled_leg_count": {
            label: len(trades_by_window[label]) for label in WINDOWS
        },
        "by_window_independent_release_decision_count": {
            label: len(releases_by_window[label]) for label in WINDOWS
        },
        "release_decisions_by_window": releases_by_window,
        "unique_ticker_count": len(ticker_count),
        "tickers": sorted(ticker_count),
        "by_ticker_count": dict(sorted(ticker_count.items())),
        "by_ticker_pnl": {
            ticker: round(pnl, 2) for ticker, pnl in sorted(ticker_pnl.items())
        },
        "standalone_net_pnl": round(sum(ticker_pnl.values()), 2),
        "single_ticker_positive_pnl_share": round(shares[0], 6) if shares else None,
        "top_5_positive_pnl_share": round(sum(shares[:5]), 6) if shares else None,
        "hhi_positive_pnl_concentration": (
            round(sum(share * share for share in shares), 6) if shares else None
        ),
    }


def _build_dsr(
    windows: dict[str, dict[str, Any]], source_contract: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    series = [
        point
        for label in WINDOWS
        for point in windows[label]["after"]["return_series"]
    ]
    dates = [str(point["date"]) for point in series]
    if dates != sorted(dates) or len(dates) != len(set(dates)):
        raise EvaluationContractError("DSR return dates are not strictly aligned")
    panel = {
        "selected_config_id": "faers_serious_share_improvement_basket_on",
        "expected_attempt_count": EXPECTED_DSR_ATTEMPTS,
        "selection_pool_complete": False,
        "expected_return_dates": dates,
        "periods_per_year": 252,
        "trials": [
            {
                "config_id": "faers_serious_share_improvement_basket_on",
                "config": {
                    "event_notional_usd": EVENT_NOTIONAL_USD,
                    "hold_sessions": HOLD_SESSIONS,
                    "round_trip_cost_bps": ROUND_TRIP_COST_BPS,
                },
                "attempted": True,
                "selection_scope": "faers_serious_share_improvement_quarterly_candidate_pool",
                "window": {
                    "segments": [
                        {"label": label, "start": start, "end": end}
                        for label, (start, end) in WINDOWS.items()
                    ]
                },
                "frequency": "daily",
                "return_basis": "cash_feasible_core_plus_faers_basket_daily_mtm_post_cost",
                "capital_accounting": "additive_external_capital_diagnostic_not_cash_conserving",
                "risk_free_assumption": "zero",
                "protocol": {
                    "id": "cash_feasible_gate1_plus_faers_improvement_basket_v1",
                    "expected_value_score": "signed_return_times_absolute_sharpe",
                },
                "data": {
                    "baseline_summary_sha256": _file_sha(BASELINE_SUMMARY_PATH),
                    "source_bundle_sha256": source_contract[
                        "actual_concatenated_bundle_sha256"
                    ],
                    "issuer_map_sha256": source_contract["actual_issuer_map_sha256"],
                },
                "cost": {"round_trip_cost_bps": ROUND_TRIP_COST_BPS},
                "return_series": series,
                "return_series_sha256": _return_series_sha(series),
                "return_series_source": f"{_repo_rel(RESULT_PATH)}#windows.*.after.return_series",
            }
        ],
    }
    report = build_dsr_report(panel)
    report["gate4_independence"] = True
    report["gate4_selection_input"] = False
    report["live_only"] = True
    report["fail_closed_reason"] = "declared_selection_pool_incomplete"
    _atomic_write_json(DSR_PANEL_PATH, panel)
    _atomic_write_json(DSR_REPORT_PATH, report)
    return panel, report


def _build_evaluation_payload() -> tuple[dict[str, Any], dict[str, Any]]:
    issuer_index, issuer_manifest, source_contract = _source_contract()
    baseline_summary = _read_json(BASELINE_SUMMARY_PATH)
    baseline_windows = _baseline_window_map(baseline_summary)
    if set(baseline_windows) != set(WINDOWS):
        raise EvaluationContractError("active baseline window labels drifted")

    ohlcv, ohlcv_identity = _load_ohlcv([*issuer_index.values(), "SPY", "QQQ"])
    if ohlcv_identity["invalid_ohlcv_row_count"]:
        raise EvaluationContractError("warehouse OHLCV hygiene failed")
    market_calendar = sorted({_bar_date(row) for row in ohlcv["SPY"] if _bar_date(row)})
    standard_windows = [
        {"name": label, "start": start, "end": end}
        for label, (start, end) in WINDOWS.items()
    ]
    historical = build_historical_replay(
        raw_dir=RAW_DIR,
        expected_sha256_by_quarter=source_contract["expected_zip_sha256"],
        issuer_index=issuer_manifest,
        ohlcv_by_ticker=ohlcv,
        standard_windows=standard_windows,
        market_calendar=market_calendar,
    )
    helper_provenance = historical.get("source_provenance") or {}
    provenance_hashes = {
        str(key).lower(): str(value)
        for key, value in (
            helper_provenance.get("zip_sha256")
            or helper_provenance.get("source_sha256_by_quarter")
            or {}
        ).items()
    }
    if provenance_hashes and provenance_hashes != source_contract["expected_zip_sha256"]:
        raise EvaluationContractError("shared helper source provenance drift")
    if (
        helper_provenance.get("concatenated_bundle_sha256")
        != source_contract["actual_concatenated_bundle_sha256"]
    ):
        raise EvaluationContractError("shared helper bundle provenance drift")
    if (
        helper_provenance.get("issuer_map_sha256")
        != source_contract["actual_issuer_map_sha256"]
    ):
        raise EvaluationContractError("shared helper issuer-map provenance drift")
    if historical.get("orders"):
        raise EvaluationContractError("default-off historical helper emitted orders")

    bars = _bar_index(ohlcv)
    windows: dict[str, dict[str, Any]] = {}
    trades_by_window: dict[str, list[dict[str, Any]]] = {}
    generated_total = 0
    survived_total = 0
    for label, (start, end) in WINDOWS.items():
        replay = historical["windows"][label]
        trades = [dict(row, window=label) for row in replay.get("trades") or []]
        before, after, combined_curve = _combine_window(
            baseline_windows[label], trades, bars
        )
        counts = Counter(str(trade["ticker"]) for trade in trades)
        top1_share = max(counts.values(), default=0) / len(trades) if trades else 1.0
        coverage = dict(replay.get("coverage") or {})
        coverage.update(
            {
                "settled_leg_count": len(trades),
                "independent_release_decision_count": len(
                    {str(trade["quarter"]) for trade in trades}
                ),
                "unique_ticker_count": len(counts),
                "top1_row_share": round(top1_share, 6),
                "ticker_counts": dict(sorted(counts.items())),
            }
        )
        generated = int(replay.get("signals_generated") or 0)
        survived = int(replay.get("signals_survived") or 0)
        survival_rate = float(replay.get("survival_rate") or 0.0)
        generated_total += generated
        survived_total += survived
        trades_by_window[label] = trades
        windows[label] = {
            "start": start,
            "end": end,
            "before": before,
            "after": after,
            "delta": {
                "expected_value_score": round(
                    float(after["expected_value_score"])
                    - float(before["expected_value_score"]),
                    4,
                ),
                "total_pnl": round(
                    float(after["total_pnl"]) - float(before["total_pnl"]), 2
                ),
                "max_drawdown_pct": round(
                    float(after["max_drawdown_pct"])
                    - float(before["max_drawdown_pct"]),
                    4,
                ),
            },
            "signals_generated": generated,
            "signals_survived": survived,
            "survival_rate": round(survival_rate, 6),
            "coverage": coverage,
            "standalone_diagnostics": _standalone_diagnostics(trades, bars),
            "selected": replay.get("selected") or [],
            "trades": trades,
            "unsettled": replay.get("unsettled") or [],
            "orders": replay.get("orders") or [],
            "combined_curve_sha256": _canonical_sha(combined_curve),
        }

    all_trades = [trade for label in WINDOWS for trade in trades_by_window[label]]
    selection = _selection_summary(trades_by_window)
    aggregate = _aggregate_windows(windows)

    sentinel_fields = [
        "entry_date",
        "target_price",
        "exit_date",
        "entry_price",
        "exit_price",
    ]
    missing_sentinels = [
        f"{trade.get('quarter')}:{trade.get('ticker')}"
        for trade in all_trades
        if any(trade.get(field) in (None, "") for field in sentinel_fields)
    ]
    gate2_failures: list[str] = []
    if not all_trades:
        gate2_failures.append("no_settled_shared_helper_rows")
    if missing_sentinels:
        gate2_failures.append("signal_contract_sentinel_missing")
    if any(windows[label]["orders"] for label in WINDOWS):
        gate2_failures.append("default_off_helper_emitted_orders")
    if TRADE_ENABLED:
        gate2_failures.append("shared_helper_trade_enabled")
    gate2 = {
        "passed": not gate2_failures,
        "hard_failures": gate2_failures,
        "sentinel_fields": sentinel_fields,
        "minimum_required_sentinels": ["entry_date", "target_price"],
        "missing_sentinel_trade_ids": missing_sentinels,
        "orders_empty": not any(windows[label]["orders"] for label in WINDOWS),
        "trade_enabled": TRADE_ENABLED,
    }
    aggregate_survival = survived_total / generated_total if generated_total else 0.0
    gate3_window_checks = {
        label: windows[label]["signals_generated"] > 0
        and windows[label]["survival_rate"] >= MIN_SURVIVAL_RATE
        for label in WINDOWS
    }
    gate3 = {
        "passed": bool(generated_total)
        and aggregate_survival >= MIN_SURVIVAL_RATE
        and all(gate3_window_checks.values()),
        "unit": "FAERS adjacent-quarter mapped issuer signal",
        "signals_generated": generated_total,
        "signals_survived": survived_total,
        "survival_rate": round(aggregate_survival, 6),
        "minimum_survival_rate": MIN_SURVIVAL_RATE,
        "window_checks": gate3_window_checks,
    }

    gate_metrics = {
        "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
        "windows_ev_improved": aggregate["windows_ev_improved"],
        "windows_ev_regressed": aggregate["windows_ev_regressed"],
        "adjusted_trade_count": selection["independent_release_decision_count"],
        "adjusted_windows": list(WINDOWS),
        "adjusted_window_count": len(WINDOWS),
        "max_drawdown_worse_max": aggregate["max_drawdown_worse_max"],
        "single_ticker_positive_share": selection["single_ticker_positive_pnl_share"],
        "top_5_contribution_pct": selection["top_5_positive_pnl_share"],
        "hhi_concentration": selection["hhi_positive_pnl_concentration"],
    }
    thresholds = ExperimentGateThresholds(
        min_adjusted_trades=(
            MIN_INDEPENDENT_RELEASE_DECISIONS_PER_WINDOW * len(WINDOWS)
        ),
        min_adjusted_windows=len(WINDOWS),
        min_ev_improved_windows=2,
        max_ev_regressed_windows=0,
        min_aggregate_ev_delta=0.0,
        min_aggregate_pnl_delta=0.0,
        max_drawdown_worse=MAX_DRAWDOWN_WORSE,
        max_single_ticker_positive_share=0.50,
        max_top_5_contribution_pct=0.60,
        max_hhi_concentration=0.35,
        require_tail_concentration_evidence=True,
        require_tail_concentration_not_worse=False,
    )
    canonical_gate4 = evaluate_gate4(
        gate_metrics, thresholds=thresholds, check_materiality=False
    )
    failures = list(canonical_gate4["hard_failures"])
    failures.extend(gate2["hard_failures"])
    if not gate3["passed"]:
        failures.append("gate3_survival_below_5pct")
    # The after curve adds a $10k sleeve on top of a cash-feasible core without
    # specifying which core positions fund it.  It is useful attribution, but
    # not a cash-conserving promotion comparison and therefore fails closed.
    failures.append("capital_source_not_cash_conserving")
    for label in WINDOWS:
        coverage = windows[label]["coverage"]
        standalone = windows[label]["standalone_diagnostics"]
        if int(coverage["settled_leg_count"]) < MIN_SETTLED_ROWS_PER_WINDOW:
            failures.append(f"settled_legs_below_10:{label}")
        if (
            int(coverage["independent_release_decision_count"])
            < MIN_INDEPENDENT_RELEASE_DECISIONS_PER_WINDOW
        ):
            failures.append(f"independent_release_decisions_below_10:{label}")
        if int(coverage["unique_ticker_count"]) < MIN_UNIQUE_TICKERS_PER_WINDOW:
            failures.append(f"unique_tickers_below_10:{label}")
        if float(coverage["top1_row_share"]) > MAX_TOP1_ROW_SHARE:
            failures.append(f"top1_row_share_above_20pct:{label}")
        if not standalone["passed"]:
            failures.append(f"standalone_cash_spy_qqq_replacement_failed:{label}")
    failures = list(dict.fromkeys(failures))
    gate4 = {
        "passed": not failures,
        "status": "passed" if not failures else "blocked",
        "hard_failures": failures,
        "canonical": canonical_gate4,
        "metrics": gate_metrics,
        "window_bars": {
            "minimum_settled_legs": MIN_SETTLED_ROWS_PER_WINDOW,
            "minimum_independent_release_decisions": (
                MIN_INDEPENDENT_RELEASE_DECISIONS_PER_WINDOW
            ),
            "minimum_unique_tickers": MIN_UNIQUE_TICKERS_PER_WINDOW,
            "maximum_top1_row_share": MAX_TOP1_ROW_SHARE,
            "standalone_requires_positive_replacement_value_vs": ["cash", "SPY", "QQQ"],
        },
        "combined_after_curve_role": "diagnostic_only_additive_external_capital",
        "cash_conserving_capital_source_modeled": False,
        "dsr_used_for_selection": False,
    }

    panel, dsr_report = _build_dsr(windows, source_contract)
    envelope = ExecutionEnvelope(
        base_notional=EVENT_NOTIONAL_USD,
        max_capital_pct=0.10,
        min_dollar_volume=0.0,
        slippage_bps=ROUND_TRIP_COST_BPS / 2.0,
        max_displacement=0,
        max_concurrent=10,
        order_semantics="first_PIT_regular_session_open_then_session20_close",
        kill_switch_drawdown_pct=0.08,
        sleeve_drawdown_stop_pct=0.05,
        notes=(
            "Default-off, one equal-weight $10k event basket per quarterly release, "
            "at most ten issuer rows, 35bps round trip, and no core displacement."
        ),
    )
    live = evaluate_live_readiness(
        envelope=envelope,
        closed_forward_trades=0,
        forward_pnl=None,
        replacement_value_passed=False,
        kill_switch_parity_passed=False,
        dsr_report=dsr_report,
    )
    verdict = full_stack_verdict(gate4=gate4, live_readiness=live, envelope=envelope)

    snapshot = build_paper_snapshot(
        raw_dir=RAW_DIR,
        expected_sha256_by_quarter=source_contract["expected_zip_sha256"],
        issuer_index=issuer_manifest,
        ohlcv_by_ticker=ohlcv,
        as_of_date=max(market_calendar),
        market_calendar=market_calendar,
    )
    if snapshot.get("orders"):
        raise EvaluationContractError("default-off paper snapshot emitted orders")
    snapshot = {
        **snapshot,
        "experiment_id": EXPERIMENT_ID,
        "preflight_identity_sha256": source_contract["preflight_identity_sha256"],
        "one_shot_parity_artifact": True,
        "daily_wiring_retained": False,
        "live_orders_changed": False,
    }
    _atomic_write_json(PAPER_SNAPSHOT_PATH, snapshot)

    accepted = bool(gate4["passed"])
    result = {
        "schema": "faers_serious_share_improvement_basket_full_stack_result_v1",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lane": "alpha_search",
        "status": "accepted_paper_pending_forward" if accepted else "rejected",
        "decision": (
            "accepted_paper_pending_forward_faers_serious_share_improvement_basket"
            if accepted
            else "rejected_faers_serious_share_improvement_basket"
        ),
        "accepted_alpha": accepted,
        "hypothesis": (
            "Among strictly mapped liquid Healthcare issuers, a quarter-over-quarter "
            "decline in official FDA FAERS serious-outcome share is a safety-quality "
            "signal; rank improving issuers, hold an equal-weight $10k quarterly "
            "event basket from the first PIT session open through session 20 close."
        ),
        "locked_policy": historical.get("policy") or {},
        "source": {
            "contract": source_contract,
            "helper_provenance": helper_provenance,
        },
        "input_identity": {
            "baseline_summary": _repo_rel(BASELINE_SUMMARY_PATH),
            "baseline_summary_sha256": _file_sha(BASELINE_SUMMARY_PATH),
            "ohlcv": ohlcv_identity,
        },
        "windows": windows,
        "aggregate": aggregate,
        "selection_summary": selection,
        "gate1": {
            "passed": True,
            "baseline": _repo_rel(BASELINE_SUMMARY_PATH),
            "baseline_sha256": _file_sha(BASELINE_SUMMARY_PATH),
            "baseline_experiment_id": baseline_summary["experiment_id"],
        },
        "gate2": gate2,
        "gate3": gate3,
        "gate4": gate4,
        "gate5": {
            "passed": bool(live["ready"]),
            "status": "passed" if live["ready"] else "blocked",
            "gate4_independent": True,
            "honest_attempt_count": EXPECTED_DSR_ATTEMPTS,
            "declared_selection_pool_complete": False,
            "dsr_status": dsr_report.get("status"),
            "forward_live_readiness": live,
            "panel_path": _repo_rel(DSR_PANEL_PATH),
            "report_path": _repo_rel(DSR_REPORT_PATH),
        },
        "full_stack": {
            "verdict": verdict,
            "one_shot_helper_snapshot_parity": True,
            "daily_wiring_retained": False,
            "forward_collection_automatic": False,
            "paper_snapshot": _repo_rel(PAPER_SNAPSHOT_PATH),
            "execution_envelope": envelope.to_dict(),
            "live_readiness": live,
        },
        "dsr_panel_sha256": _canonical_sha(panel),
        "prediction": PREDICTION,
        "production_impact": {
            "trade_enabled": False,
            "live_orders_changed": False,
            "core_ranking_changed": False,
            "core_sizing_changed": False,
            "core_exits_changed": False,
            "run_adapter_changed": False,
            "shared_helper": "quant/faers_serious_share_improvement_paper_sleeve.py",
            "historical_and_snapshot_selection_share_helper": True,
            "combined_after_curve_cash_conserving": False,
        },
        "residual_unknowns": [
            "FAERS reporting mix and manufacturer submission behavior may change independently of product safety quality.",
            "The strict current Healthcare title map is auditable but still survivorship-prone rather than effective-dated.",
            "The single declared trial leaves Deflated Sharpe incomplete; DSR is reported only and never selects Gate 4.",
            "No prospectively settled forward rows, replacement-value proof, daily wiring, or kill-switch parity exist.",
            "The additive core-plus-sleeve curve does not identify which cash-feasible core holdings fund the $10k basket.",
        ],
        "post_run_reflection": {
            "why_result_happened": (
                "; ".join(gate4["hard_failures"])
                if gate4["hard_failures"]
                else "The locked FAERS improvement basket cleared every preregistered historical bar."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune issuer identity, serious outcome definition, minimum cases, "
                "volume ratio, rank, top-N, entry clock, hold, basket notional, or costs."
            ),
            "next_retry_requires": (
                "At least 30 independent prospectively settled unchanged-policy quarterly "
                "release decisions, an explicit cash-conserving funding contract, and an "
                "effective-dated sponsor/exposure relation; otherwise require a genuinely "
                "independent PIT safety/exposure data source or gate shape. Issuer legs do "
                "not count as independent release decisions."
            ),
        },
        "reproduction_commands": [
            f".\\.venv\\Scripts\\python.exe -B quant\\experiments\\{Path(__file__).name} --evaluate"
        ],
    }
    return result, source_contract


def _write_outputs(payload: dict[str, Any], source_contract: dict[str, Any]) -> None:
    _atomic_write_json(RESULT_PATH, payload)
    _atomic_write_json(PREFLIGHT_OUTPUT_PATH, source_contract)
    for path, side in ((BEFORE_PATH, "before"), (AFTER_PATH, "after")):
        _atomic_write_json(
            path,
            {
                "schema": f"faers_serious_share_improvement_basket_gate4_{side}_v1",
                "experiment_id": EXPERIMENT_ID,
                "expected_value_score": payload["aggregate"][
                    f"{side}_expected_value_score_sum"
                ],
                "expected_value_score_formula": "strategy_total_return_pct * abs(sharpe_daily)",
                "total_pnl": payload["aggregate"][f"{side}_total_pnl_sum"],
                "max_drawdown_pct": max(
                    float(row[side]["max_drawdown_pct"])
                    for row in payload["windows"].values()
                ),
                "total_trades": sum(
                    int(row[side]["total_trades"])
                    for row in payload["windows"].values()
                ),
                "survival_rate": (
                    payload["gate3"]["survival_rate"]
                    if side == "after"
                    else min(
                        float(row["before"]["survival_rate"])
                        for row in payload["windows"].values()
                    )
                ),
                "benchmarks": {
                    "strategy_total_return_pct": round(
                        float(payload["aggregate"][f"{side}_total_pnl_sum"])
                        / 100_000.0,
                        4,
                    )
                },
            },
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--evaluate",
        action="store_true",
        help="Run the evaluator (also the default when no flag is supplied).",
    )
    parser.parse_args()
    payload, source_contract = _build_evaluation_payload()
    _write_outputs(payload, source_contract)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "aggregate": payload["aggregate"],
                "window_coverage": {
                    label: row["coverage"] for label, row in payload["windows"].items()
                },
                "window_standalone": {
                    label: row["standalone_diagnostics"]
                    for label, row in payload["windows"].items()
                },
                "gate2": payload["gate2"],
                "gate3": payload["gate3"],
                "gate4_failures": payload["gate4"]["hard_failures"],
                "gate5": payload["gate5"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
