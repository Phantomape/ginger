"""exp-20260716-005: PCAOB partner-change peer substitution full stack.

This evaluator is deliberately offline and default-off.  The shared helper
owns the source filters, partner-change event, exact-CIK share-class mapping,
peer selection, entry clock, and twenty-session trade.  This runner owns only
the frozen input assembly and the preregistered Gate 1-5 evaluation.

It does not close the experiment ticket or write registry, log, card, or live
configuration state.
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


EXPERIMENT_ID = "exp-20260716-005"
REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (REPO_ROOT, QUANT_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from deflated_sharpe import build_report as build_dsr_report  # noqa: E402
from experiment_fingerprint import infer_fingerprint  # noqa: E402
from pcaob_form_ap_partner_change_peer_substitution_paper_sleeve import (  # noqa: E402
    BASE_NOTIONAL_USD,
    HOLD_SESSIONS,
    ROUND_TRIP_COST_PCT,
    RULE_VERSION,
    build_pcaob_form_ap_partner_change_peer_substitution_historical,
    build_pcaob_form_ap_partner_change_peer_substitution_paper_snapshot,
)
from quant.evaluator_gates import ExperimentGateThresholds  # noqa: E402
from quant.full_stack_candidate_pool import (  # noqa: E402
    ExecutionEnvelope,
    evaluate_gate4,
    evaluate_live_readiness,
    full_stack_verdict,
)


SOURCE_ARCHIVE_PATH = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / "pcaob_form_ap"
    / "source"
    / "FirmFilings_20260716.zip"
)
SOURCE_MANIFEST_PATH = (
    REPO_ROOT / "data" / "non_ohlcv" / "pcaob_form_ap" / "source_manifest.json"
)
EXPECTED_SOURCE_SHA256 = (
    "0f51a6b213da6dff8087d41a251545a5280143429492233d0ee798f00e4d1396"
)
EXPECTED_SOURCE_BYTES = 13_109_236
WAREHOUSE_PATH = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"
SEC_TICKERS_PATH = REPO_ROOT / "data" / "reference" / "sec_company_tickers.json"
SECTOR_MAP_PATH = REPO_ROOT / "data" / "reference" / "broad_market_sector_map.json"
BASELINE_SUMMARY_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_cash_feasible_20260715.json"
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
RESULT_PATH = OUT_DIR / "result.json"
BEFORE_PATH = OUT_DIR / "before.json"
AFTER_PATH = OUT_DIR / "after.json"
DSR_PANEL_PATH = OUT_DIR / "deflated_sharpe_panel.json"
DSR_REPORT_PATH = OUT_DIR / "deflated_sharpe_report.json"
PAPER_SNAPSHOT_PATH = (
    REPO_ROOT
    / "data"
    / "paper_sleeves"
    / "pcaob_form_ap_partner_change_peer_substitution"
    / "latest_snapshot.json"
)

WINDOWS = OrderedDict(
    (
        ("old_thin", ("2024-10-02", "2025-04-22")),
        ("mid_weak", ("2025-04-23", "2025-10-22")),
        ("late_strong", ("2025-10-23", "2026-04-21")),
    )
)
OHLCV_QUERY_START = "2024-06-01"
MIN_WINDOW_OHLCV_ROWS = 80
MIN_SETTLED_DECISIONS_PER_WINDOW = 20
MIN_TARGET_TICKERS_PER_WINDOW = 10
MIN_PEER_TICKERS_PER_WINDOW = 10
MAX_TARGET_OR_PEER_TOP1_SHARE = 0.30
MAX_DRAWDOWN_WORSE = 0.005
MAX_TOP5_POSITIVE_PNL_SHARE = 0.60
REFERENCE_TICKER = "QQQ"
EXPECTED_DSR_ATTEMPTS = 1
EXPECTED_FINGERPRINT = {
    "data_source": "pcaob_form_ap",
    "gate_shape": "peer_substitution_candidate_pool_top1_20d",
}
ACCEPTED_CANDIDATE_COMPARATOR = {
    "experiment_id": "exp-20260611-007",
    "expected_value_score_delta_sum": 0.5286,
    "total_pnl_delta_sum": 10_432.91,
}
PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": 0.25,
    "expected_pnl_delta": 5_000.0,
    "main_failure_modes": [
        "audit_uncertainty_is_industry_wide_not_substitution",
        "liquidity_rank_is_generic_beta",
        "current_industry_map_survivorship",
        "next_open_absorbs_signal",
        "window_regression",
        "accepted_comparator_not_beaten",
        "positive_pnl_concentration",
    ],
}


class EvaluationContractError(RuntimeError):
    """Raised when a frozen input or evaluator invariant fails closed."""


def _repo_rel(path: Path) -> str:
    return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _canonical_sha(payload: Any) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
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
    values = [_number(row.get(field)) for field in ("open", "high", "low", "close")]
    volume = _number(row.get("volume"))
    return bool(
        all(value is not None and value > 0 for value in values)
        and volume is not None
        and volume >= 0
    )


def _chunks(values: list[str], size: int = 500) -> Iterable[list[str]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def _load_ohlcv(tickers: Iterable[str]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    if not WAREHOUSE_PATH.exists():
        raise EvaluationContractError(f"warehouse missing: {WAREHOUSE_PATH}")
    requested = sorted({str(ticker).strip().upper() for ticker in tickers if ticker})
    rows_by_ticker: dict[str, list[dict[str, Any]]] = {ticker: [] for ticker in requested}
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
            for source in connection.execute(query, (*group, OHLCV_QUERY_START)):
                item = dict(source)
                ticker = str(item.pop("ticker")).upper()
                rows_by_ticker.setdefault(ticker, []).append(item)
                identity = (
                    ticker,
                    item.get("date"),
                    item.get("open"),
                    item.get("high"),
                    item.get("low"),
                    item.get("close"),
                    item.get("volume"),
                    item.get("source"),
                    item.get("updated_at"),
                )
                rowset_digest.update(
                    (json.dumps(identity, separators=(",", ":")) + "\n").encode("utf-8")
                )
    missing_reference = [ticker for ticker in ("SPY", REFERENCE_TICKER) if not rows_by_ticker.get(ticker)]
    if missing_reference:
        raise EvaluationContractError(f"reference OHLCV missing: {missing_reference}")
    return rows_by_ticker, {
        "warehouse": _repo_rel(WAREHOUSE_PATH),
        "warehouse_sha256": _file_sha(WAREHOUSE_PATH),
        "query_start": OHLCV_QUERY_START,
        "requested_ticker_count": len(requested),
        "covered_ticker_count": sum(bool(rows) for rows in rows_by_ticker.values()),
        "row_count": sum(len(rows) for rows in rows_by_ticker.values()),
        "rowset_sha256": rowset_digest.hexdigest(),
    }


def _build_security_inputs() -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]], dict[str, Any]]:
    sec_payload = _read_json(SEC_TICKERS_PATH)
    sector_payload = _read_json(SECTOR_MAP_PATH)
    sector_entries = sector_payload.get("entries") or {}
    tradable_sector_tickers = sorted(
        ticker.upper()
        for ticker, row in sector_entries.items()
        if str((row or {}).get("status") or "").lower() == "ok"
        and str((row or {}).get("industry") or "").strip()
    )
    ohlcv, ohlcv_identity = _load_ohlcv(
        [*tradable_sector_tickers, "SPY", REFERENCE_TICKER]
    )

    coverage: dict[str, dict[str, Any]] = {}
    for ticker in tradable_sector_tickers:
        rows = ohlcv.get(ticker) or []
        valid = [row for row in rows if _valid_bar(row)]
        counts = {
            label: sum(start <= _bar_date(row) <= end for row in valid)
            for label, (start, end) in WINDOWS.items()
        }
        relevant = [
            row
            for row in rows
            if OHLCV_QUERY_START <= _bar_date(row) <= max(end for _, end in WINDOWS.values())
        ]
        coverage[ticker] = {
            "window_counts": counts,
            "warehouse_hygiene_status": (
                "ok"
                if relevant
                and len({_bar_date(row) for row in relevant}) == len(relevant)
                and all(_valid_bar(row) for row in relevant)
                else "failed"
            ),
            "all_windows_status": (
                "ok"
                if all(count >= MIN_WINDOW_OHLCV_ROWS for count in counts.values())
                else "failed"
            ),
        }

    security_master: list[dict[str, Any]] = []
    for raw in sec_payload.values() if isinstance(sec_payload, dict) else sec_payload:
        ticker = str((raw or {}).get("ticker") or "").strip().upper()
        sector = sector_entries.get(ticker) or {}
        if ticker not in coverage or str(sector.get("status") or "").lower() != "ok":
            continue
        security_master.append(
            {
                "ticker": ticker,
                "cik": raw.get("cik_str"),
                "issuer_name": str(raw.get("title") or "").strip(),
                "sector": str(sector.get("sector") or "").strip(),
                "industry": str(sector.get("industry") or "").strip(),
                "warehouse_hygiene_status": coverage[ticker]["warehouse_hygiene_status"],
                "all_windows_status": coverage[ticker]["all_windows_status"],
                "sector_status": "ok",
            }
        )
    security_master.sort(key=lambda row: (str(row["ticker"]), str(row["cik"])))
    identity = {
        "sec_company_tickers": _repo_rel(SEC_TICKERS_PATH),
        "sec_company_tickers_sha256": _file_sha(SEC_TICKERS_PATH),
        "sector_map": _repo_rel(SECTOR_MAP_PATH),
        "sector_map_sha256": _file_sha(SECTOR_MAP_PATH),
        "sector_map_rule_version": sector_payload.get("rule_version"),
        "sector_map_generated_at": sector_payload.get("generated_at"),
        "security_master_count": len(security_master),
        "security_master_sha256": _canonical_sha(security_master),
        "all_window_eligible_count": sum(
            row["all_windows_status"] == "ok"
            and row["warehouse_hygiene_status"] == "ok"
            for row in security_master
        ),
        "min_rows_per_standard_window": MIN_WINDOW_OHLCV_ROWS,
        "ohlcv": ohlcv_identity,
        "current_industry_map_survivorship_disclosed": True,
    }
    return security_master, ohlcv, identity


def _validate_source_manifest() -> dict[str, Any]:
    manifest = _read_json(SOURCE_MANIFEST_PATH)
    failures: list[str] = []
    if manifest.get("schema") != "pcaob_form_ap_source_manifest_v1":
        failures.append("source_manifest_schema_mismatch")
    if str(manifest.get("archive_sha256") or "") != EXPECTED_SOURCE_SHA256:
        failures.append("source_manifest_hash_mismatch")
    if int(manifest.get("archive_bytes") or 0) != EXPECTED_SOURCE_BYTES:
        failures.append("source_manifest_size_mismatch")
    if not SOURCE_ARCHIVE_PATH.exists():
        failures.append("source_archive_missing")
        actual_hash = None
        actual_bytes = None
    else:
        actual_hash = _file_sha(SOURCE_ARCHIVE_PATH)
        actual_bytes = SOURCE_ARCHIVE_PATH.stat().st_size
        if actual_hash != EXPECTED_SOURCE_SHA256:
            failures.append("source_archive_hash_mismatch")
        if actual_bytes != EXPECTED_SOURCE_BYTES:
            failures.append("source_archive_size_mismatch")
    return {
        "passed": not failures,
        "hard_failures": failures,
        "manifest": _repo_rel(SOURCE_MANIFEST_PATH),
        "manifest_sha256": _file_sha(SOURCE_MANIFEST_PATH),
        "archive": _repo_rel(SOURCE_ARCHIVE_PATH),
        "expected_archive_sha256": EXPECTED_SOURCE_SHA256,
        "actual_archive_sha256": actual_hash,
        "expected_archive_bytes": EXPECTED_SOURCE_BYTES,
        "actual_archive_bytes": actual_bytes,
        "manifest_payload": manifest,
    }


def _fingerprint_audit() -> dict[str, Any]:
    fingerprint = infer_fingerprint(
        "pcaob_form_ap_partner_change_peer_substitution shared-paper-first ",
        "pcaob_partner_change_unaffected_industry_peer_candidate_source_v1 ",
        "peer_substitution_candidate_pool_top1_20d",
    )
    failures = [
        f"fingerprint_{key}_mismatch"
        for key, expected in EXPECTED_FINGERPRINT.items()
        if fingerprint.get(key) != expected
    ]
    return {
        "passed": not failures,
        "hard_failures": failures,
        "expected": EXPECTED_FINGERPRINT,
        "actual": fingerprint,
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
    output: dict[str, dict[str, dict[str, float]]] = {}
    for ticker, rows in ohlcv.items():
        output[ticker] = {}
        for row in rows:
            day = _bar_date(row)
            open_price = _number(row.get("open"))
            close = _number(row.get("close"))
            if day and open_price is not None and close is not None:
                output[ticker][day] = {"open": open_price, "close": close}
    return output


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
        gross = close_row["close"] / float(trade["entry_price"]) - 1.0
        mark += float(trade["paper_notional_usd"]) * (
            gross - ROUND_TRIP_COST_PCT / 2.0
        )
    return mark


def _return_series_sha(rows: list[dict[str, Any]]) -> str:
    return _canonical_sha({"schema": "dated_periodic_return_series_v1", "rows": rows})


def _curve_metrics(
    curve: list[tuple[str, float]], *, trade_count: int
) -> dict[str, Any]:
    previous = 100_000.0
    returns: list[dict[str, Any]] = []
    peak = 100_000.0
    drawdown = 0.0
    for day, equity in curve:
        periodic_return = equity / previous - 1.0 if previous else 0.0
        returns.append({"date": day, "return": periodic_return})
        previous = equity
        peak = max(peak, equity)
        drawdown = max(drawdown, (peak - equity) / peak)
    samples = [float(row["return"]) for row in returns]
    sharpe_full = None
    if len(samples) >= 2:
        mean = sum(samples) / len(samples)
        variance = sum((value - mean) ** 2 for value in samples) / (len(samples) - 1)
        if variance > 0:
            sharpe_full = mean / math.sqrt(variance) * math.sqrt(252)
    total_pnl = curve[-1][1] - 100_000.0
    public_return = round(total_pnl / 100_000.0, 4)
    public_sharpe = round(sharpe_full, 2) if sharpe_full is not None else None
    return {
        "total_pnl": round(total_pnl, 2),
        "benchmarks": {"strategy_total_return_pct": public_return},
        "sharpe_daily": public_sharpe,
        "sharpe_daily_full_precision": sharpe_full,
        "expected_value_score": (
            round(public_return * public_sharpe, 4)
            if public_sharpe is not None
            else None
        ),
        "max_drawdown_pct": round(drawdown, 4),
        "total_trades": trade_count,
        "return_series": returns,
        "return_series_sha256": _return_series_sha(returns),
    }


def _combine_window(
    baseline: dict[str, Any],
    trades: list[dict[str, Any]],
    ohlcv: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, Any], dict[str, Any], list[tuple[str, float]]]:
    base_curve = _baseline_curve(baseline)
    bars = _bar_index(ohlcv)
    combined = [
        (day, equity + _target_mark_on_date(trades, bars, day))
        for day, equity in base_curve
    ]
    before = {
        "total_pnl": baseline["total_pnl"],
        "benchmarks": {
            "strategy_total_return_pct": round(
                float(baseline["total_pnl"]) / 100_000.0, 4
            )
        },
        "sharpe_daily": baseline["sharpe_daily"],
        "sharpe_daily_full_precision": baseline["sharpe_daily_full_precision"],
        "expected_value_score": baseline["expected_value_score"],
        "max_drawdown_pct": baseline["max_drawdown_pct"],
        "total_trades": baseline["trade_count"],
        "signals_generated": baseline["signals_generated"],
        "signals_survived": baseline["signals_survived"],
        "survival_rate": baseline["survival_rate"],
    }
    after = _curve_metrics(
        combined, trade_count=int(baseline["trade_count"]) + len(trades)
    )
    return before, after, combined


def _aggregate_windows(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "before_expected_value_score_sum": round(
            sum(row["before"]["expected_value_score"] for row in rows.values()), 4
        ),
        "after_expected_value_score_sum": round(
            sum(row["after"]["expected_value_score"] for row in rows.values()), 4
        ),
        "expected_value_score_delta_sum": round(
            sum(row["delta"]["expected_value_score"] for row in rows.values()), 4
        ),
        "before_total_pnl_sum": round(
            sum(row["before"]["total_pnl"] for row in rows.values()), 2
        ),
        "after_total_pnl_sum": round(
            sum(row["after"]["total_pnl"] for row in rows.values()), 2
        ),
        "total_pnl_delta_sum": round(
            sum(row["delta"]["total_pnl"] for row in rows.values()), 2
        ),
        "windows_ev_improved": sum(
            row["delta"]["expected_value_score"] > 0 for row in rows.values()
        ),
        "windows_ev_regressed": sum(
            row["delta"]["expected_value_score"] < 0 for row in rows.values()
        ),
        "windows_pnl_improved": sum(
            row["delta"]["total_pnl"] > 0 for row in rows.values()
        ),
        "windows_pnl_regressed": sum(
            row["delta"]["total_pnl"] < 0 for row in rows.values()
        ),
        "max_drawdown_worse_max": max(
            row["delta"]["max_drawdown_pct"] for row in rows.values()
        ),
    }


def _standalone_diagnostics(
    trades: list[dict[str, Any]],
    bars: dict[str, dict[str, dict[str, float]]],
) -> dict[str, Any]:
    target_pnl = round(sum(float(trade["pnl"]) for trade in trades), 2)
    qqq_pnl = 0.0
    missing: list[str] = []
    for trade in trades:
        entry = bars.get(REFERENCE_TICKER, {}).get(str(trade["entry_date"]))
        exit_row = bars.get(REFERENCE_TICKER, {}).get(str(trade["exit_date"]))
        if entry is None or exit_row is None:
            missing.append(str(trade.get("candidate_id") or trade.get("event_id")))
            continue
        qqq_return = exit_row["close"] / entry["open"] - 1.0 - ROUND_TRIP_COST_PCT
        qqq_pnl += float(trade["paper_notional_usd"]) * qqq_return
    available = bool(trades) and not missing
    qqq_pnl_value = round(qqq_pnl, 2) if available else None
    return {
        "settled_decision_count": len(trades),
        "standalone_net_pnl": target_pnl,
        "cash_matched_pnl": 0.0 if trades else None,
        "cash_replacement_value": target_pnl if trades else None,
        "qqq_matched_pnl": qqq_pnl_value,
        "qqq_replacement_value": (
            round(target_pnl - qqq_pnl_value, 2)
            if qqq_pnl_value is not None
            else None
        ),
        "qqq_missing_decision_ids": missing,
        "benchmark_entry_exit": "same peer entry open to same session-20 close",
        "benchmark_round_trip_cost_pct": ROUND_TRIP_COST_PCT,
        "passed": bool(
            trades
            and target_pnl > 0
            and available
            and qqq_pnl_value is not None
            and target_pnl - qqq_pnl_value > 0
        ),
    }


def _target_summary(trades_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    by_ticker_pnl: Counter[str] = Counter()
    by_ticker_count: Counter[str] = Counter()
    for trades in trades_by_window.values():
        for trade in trades:
            ticker = str(trade["peer_ticker"])
            by_ticker_pnl[ticker] += float(trade["pnl"])
            by_ticker_count[ticker] += 1
    positive = {ticker: pnl for ticker, pnl in by_ticker_pnl.items() if pnl > 0}
    positive_total = sum(positive.values())
    shares = (
        sorted((pnl / positive_total for pnl in positive.values()), reverse=True)
        if positive_total > 0
        else []
    )
    return {
        "settled_decision_count": sum(len(rows) for rows in trades_by_window.values()),
        "by_window_settled_decision_count": {
            label: len(trades_by_window.get(label) or []) for label in WINDOWS
        },
        "peer_ticker_count": len(by_ticker_count),
        "peer_tickers": sorted(by_ticker_count),
        "by_peer_ticker_count": dict(sorted(by_ticker_count.items())),
        "by_peer_ticker_pnl": {
            ticker: round(pnl, 2) for ticker, pnl in sorted(by_ticker_pnl.items())
        },
        "standalone_net_pnl": round(sum(by_ticker_pnl.values()), 2),
        "single_ticker_positive_share": round(shares[0], 6) if shares else None,
        "top_5_positive_pnl_share": round(sum(shares[:5]), 6) if shares else None,
        "hhi_positive_pnl_concentration": (
            round(sum(share * share for share in shares), 6) if shares else None
        ),
    }


def _share_class_usage(
    trades: list[dict[str, Any]], universe_audit: dict[str, Any]
) -> dict[str, Any]:
    counts = universe_audit.get("share_class_candidate_counts") or {}
    target_rows = [
        trade for trade in trades if int(counts.get(str(trade["target_cik"]), 1)) > 1
    ]
    peer_rows = [
        trade for trade in trades if int(counts.get(str(trade["peer_cik"]), 1)) > 1
    ]
    return {
        "resolved_multiple_share_class_cik_count": universe_audit.get(
            "multi_share_class_cik_count",
            universe_audit.get("multiple_share_class_cik_count"),
        ),
        "selected_target_multi_share_trade_count": len(target_rows),
        "selected_target_multi_share_ciks": sorted(
            {str(row["target_cik"]) for row in target_rows}
        ),
        "selected_peer_multi_share_trade_count": len(peer_rows),
        "selected_peer_multi_share_ciks": sorted(
            {str(row["peer_cik"]) for row in peer_rows}
        ),
        "peer_pit_blocker": bool(peer_rows),
        "reason": (
            "Selected peer share class was chosen with the frozen three-window "
            "minimum-median ADV rule, which uses future windows relative to early events."
            if peer_rows
            else None
        ),
    }


def _build_dsr(
    windows: dict[str, dict[str, Any]], source_audit: dict[str, Any]
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
        "selected_config_id": "pcaob_partner_change_peer_substitution_on",
        "expected_attempt_count": EXPECTED_DSR_ATTEMPTS,
        "selection_pool_complete": False,
        "expected_return_dates": dates,
        "periods_per_year": 252,
        "trials": [
            {
                "config_id": "pcaob_partner_change_peer_substitution_on",
                "config": {
                    "rule_version": RULE_VERSION,
                    "hold_sessions": HOLD_SESSIONS,
                    "paper_notional_usd": BASE_NOTIONAL_USD,
                },
                "attempted": True,
                "selection_scope": "pcaob_form_ap_partner_change_peer_substitution",
                "window": {
                    "segments": [
                        {"label": label, "start": start, "end": end}
                        for label, (start, end) in WINDOWS.items()
                    ]
                },
                "frequency": "daily",
                "return_basis": "cash_feasible_core_plus_pcaob_peer_daily_mtm_post_cost",
                "risk_free_assumption": "zero",
                "protocol": {
                    "id": "cash_feasible_gate1_plus_pcaob_partner_peer_v1",
                    "rule_version": RULE_VERSION,
                },
                "data": {
                    "baseline_summary_sha256": _file_sha(BASELINE_SUMMARY_PATH),
                    "source_manifest_sha256": source_audit["manifest_sha256"],
                    "source_archive_sha256": source_audit["actual_archive_sha256"],
                },
                "cost": {"round_trip_cost_pct": ROUND_TRIP_COST_PCT},
                "return_series": series,
                "return_series_sha256": _return_series_sha(series),
                "return_series_source": f"{_repo_rel(RESULT_PATH)}#windows.*.after.return_series",
            }
        ],
    }
    report = build_dsr_report(panel)
    report["gate4_independence"] = True
    report["live_only"] = True
    report["fail_closed_reason"] = "declared_selection_pool_incomplete"
    _atomic_write_json(DSR_PANEL_PATH, panel)
    _atomic_write_json(DSR_REPORT_PATH, report)
    return panel, report


def _build_evaluation_payload() -> dict[str, Any]:
    source_audit = _validate_source_manifest()
    fingerprint_audit = _fingerprint_audit()
    if not source_audit["passed"]:
        raise EvaluationContractError(
            "source contract failed: " + ", ".join(source_audit["hard_failures"])
        )
    if not fingerprint_audit["passed"]:
        raise EvaluationContractError(
            "fingerprint contract failed: "
            + ", ".join(fingerprint_audit["hard_failures"])
        )

    security_master, ohlcv, input_identity = _build_security_inputs()
    baseline_summary = _read_json(BASELINE_SUMMARY_PATH)
    baseline_windows = _baseline_window_map(baseline_summary)
    if set(baseline_windows) != set(WINDOWS):
        raise EvaluationContractError("active baseline window labels drifted")
    standard_windows = [
        {"name": label, "start": start, "end": end}
        for label, (start, end) in WINDOWS.items()
    ]
    market_calendar = [_bar_date(row) for row in ohlcv["SPY"]]
    historical = build_pcaob_form_ap_partner_change_peer_substitution_historical(
        source_zip_path=SOURCE_ARCHIVE_PATH,
        expected_sha256=EXPECTED_SOURCE_SHA256,
        security_master=security_master,
        ohlcv_by_ticker=ohlcv,
        standard_windows=standard_windows,
        market_calendar=market_calendar,
    )
    if historical.get("rule_version") != RULE_VERSION:
        raise EvaluationContractError("shared helper rule-version drift")
    provenance = historical.get("source_provenance") or {}
    if provenance.get("source_archive_sha256") != EXPECTED_SOURCE_SHA256:
        raise EvaluationContractError("shared helper source hash drift")

    bars = _bar_index(ohlcv)
    windows: dict[str, dict[str, Any]] = {}
    trades_by_window: dict[str, list[dict[str, Any]]] = {}
    generated_total = 0
    survived_total = 0
    for label, (start, end) in WINDOWS.items():
        replay = historical["windows"][label]
        trades = [dict(row, window=label) for row in replay["trades"]]
        before, after, combined_curve = _combine_window(
            baseline_windows[label], trades, ohlcv
        )
        standalone = _standalone_diagnostics(trades, bars)
        coverage = replay["coverage_audit"]
        generated_total += int(replay["signals_generated"])
        survived_total += int(replay["signals_survived"])
        trades_by_window[label] = trades
        windows[label] = {
            "start": start,
            "end": end,
            "before": before,
            "after": after,
            "delta": {
                "expected_value_score": round(
                    after["expected_value_score"] - before["expected_value_score"], 4
                ),
                "total_pnl": round(after["total_pnl"] - before["total_pnl"], 2),
                "max_drawdown_pct": round(
                    after["max_drawdown_pct"] - before["max_drawdown_pct"], 4
                ),
            },
            "signals_generated": replay["signals_generated"],
            "signals_survived": replay["signals_survived"],
            "survival_rate": replay["survival_rate"],
            "coverage_audit": coverage,
            "standalone_diagnostics": standalone,
            "selected_candidates": replay["selected_candidates"],
            "trades": trades,
            "unsettled": replay["unsettled"],
            "orders": replay["orders"],
            "combined_curve_sha256": _canonical_sha(combined_curve),
        }

    all_trades = [trade for label in WINDOWS for trade in trades_by_window[label]]
    target = _target_summary(trades_by_window)
    aggregate = _aggregate_windows(windows)
    share_class = _share_class_usage(all_trades, historical["universe_audit"])

    sentinel_fields = [
        "entry_date",
        "target_price",
        "entry_price",
        "exit_date",
        "exit_price",
    ]
    missing_sentinel_rows = [
        str(trade.get("candidate_id") or trade.get("event_id"))
        for trade in all_trades
        if any(trade.get(field) in (None, "") for field in sentinel_fields)
    ]
    gate2_failures: list[str] = []
    if not all_trades:
        gate2_failures.append("no_settled_shared_helper_trades")
    if missing_sentinel_rows:
        gate2_failures.append("signal_contract_sentinel_missing")
    if any(windows[label]["orders"] for label in WINDOWS):
        gate2_failures.append("default_off_helper_emitted_orders")
    if share_class["peer_pit_blocker"]:
        gate2_failures.append("selected_peer_multi_share_class_mapping_not_pit")
    gate2 = {
        "passed": not gate2_failures,
        "hard_failures": gate2_failures,
        "sentinel_fields": sentinel_fields,
        "missing_sentinel_decision_ids": missing_sentinel_rows,
        "share_class_usage": share_class,
        "current_industry_map_survivorship_disclosed": True,
    }
    gate3_rate = survived_total / generated_total if generated_total else 0.0
    gate3 = {
        "passed": generated_total > 0 and gate3_rate >= 0.05,
        "unit": "PCAOB partner-change target event",
        "signals_generated": generated_total,
        "signals_survived": survived_total,
        "survival_rate": round(gate3_rate, 6),
    }

    gate_metrics = {
        "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
        "windows_ev_improved": aggregate["windows_ev_improved"],
        "windows_ev_regressed": aggregate["windows_ev_regressed"],
        "adjusted_trade_count": target["settled_decision_count"],
        "adjusted_windows": list(WINDOWS),
        "adjusted_window_count": len(WINDOWS),
        "max_drawdown_worse_max": aggregate["max_drawdown_worse_max"],
        "single_ticker_positive_share": target["single_ticker_positive_share"],
        "top_5_contribution_pct": target["top_5_positive_pnl_share"],
        "hhi_concentration": target["hhi_positive_pnl_concentration"],
        "avg_pnl_per_trade_delta": (
            aggregate["total_pnl_delta_sum"] / target["settled_decision_count"]
            if target["settled_decision_count"]
            else None
        ),
    }
    thresholds = ExperimentGateThresholds(
        min_adjusted_trades=MIN_SETTLED_DECISIONS_PER_WINDOW * len(WINDOWS),
        min_adjusted_windows=len(WINDOWS),
        min_ev_improved_windows=2,
        max_ev_regressed_windows=0,
        max_drawdown_worse=MAX_DRAWDOWN_WORSE,
        max_single_ticker_positive_share=1.0,
        max_top_5_contribution_pct=MAX_TOP5_POSITIVE_PNL_SHARE,
        max_hhi_concentration=1.0,
        require_tail_concentration_evidence=False,
        require_tail_concentration_not_worse=False,
    )
    canonical = evaluate_gate4(
        gate_metrics, thresholds=thresholds, check_materiality=False
    )
    materiality_diagnostic = evaluate_gate4(
        gate_metrics, thresholds=thresholds, check_materiality=True
    )
    failures = list(canonical["hard_failures"])
    failures.extend(gate2["hard_failures"])
    if not gate3["passed"]:
        failures.append("gate3_survival_below_5pct")
    if not source_audit["passed"]:
        failures.extend(source_audit["hard_failures"])
    if not fingerprint_audit["passed"]:
        failures.extend(fingerprint_audit["hard_failures"])
    for label in WINDOWS:
        coverage = windows[label]["coverage_audit"]
        standalone = windows[label]["standalone_diagnostics"]
        if int(coverage["settled_trade_count"]) < MIN_SETTLED_DECISIONS_PER_WINDOW:
            failures.append(f"settled_decisions_below_20:{label}")
        if int(coverage["target_ticker_count"]) < MIN_TARGET_TICKERS_PER_WINDOW:
            failures.append(f"target_tickers_below_10:{label}")
        if int(coverage["peer_ticker_count"]) < MIN_PEER_TICKERS_PER_WINDOW:
            failures.append(f"peer_tickers_below_10:{label}")
        if float(coverage["target_top1_share"]) > MAX_TARGET_OR_PEER_TOP1_SHARE:
            failures.append(f"target_top1_share_above_30pct:{label}")
        if float(coverage["peer_top1_share"]) > MAX_TARGET_OR_PEER_TOP1_SHARE:
            failures.append(f"peer_top1_share_above_30pct:{label}")
        if not standalone["passed"]:
            failures.append(f"standalone_cash_or_qqq_replacement_failed:{label}")
    if (
        aggregate["expected_value_score_delta_sum"]
        <= ACCEPTED_CANDIDATE_COMPARATOR["expected_value_score_delta_sum"]
    ):
        failures.append("accepted_candidate_pool_ev_comparator_not_beaten")
    if (
        aggregate["total_pnl_delta_sum"]
        <= ACCEPTED_CANDIDATE_COMPARATOR["total_pnl_delta_sum"]
    ):
        failures.append("accepted_candidate_pool_pnl_comparator_not_beaten")
    failures = list(dict.fromkeys(failures))
    gate4 = {
        "passed": not failures,
        "status": "passed" if not failures else "blocked",
        "hard_failures": failures,
        "canonical": canonical,
        "materiality_diagnostic_nonbinding": materiality_diagnostic,
        "metrics": gate_metrics,
        "accepted_candidate_comparator": ACCEPTED_CANDIDATE_COMPARATOR,
        "source_contract": source_audit,
        "fingerprint_contract": fingerprint_audit,
    }

    panel, dsr_report = _build_dsr(windows, source_audit)
    envelope = ExecutionEnvelope(
        base_notional=BASE_NOTIONAL_USD,
        max_capital_pct=0.80,
        min_dollar_volume=0.0,
        slippage_bps=17.5,
        max_displacement=0,
        max_concurrent=HOLD_SESSIONS,
        order_semantics="strictly_later_regular_session_open_then_session20_close",
        kill_switch_drawdown_pct=0.08,
        sleeve_drawdown_stop_pct=0.05,
        notes=(
            "Default-off, top1/day, $4k per peer, up to twenty overlapping "
            "positions, 35bps round trip, and no core displacement. Peer rank "
            "has no separately preregistered absolute ADV floor."
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
    verdict = full_stack_verdict(
        gate4=gate4, live_readiness=live, envelope=envelope
    )

    as_of_date = max(market_calendar)
    snapshot = build_pcaob_form_ap_partner_change_peer_substitution_paper_snapshot(
        source_zip_path=SOURCE_ARCHIVE_PATH,
        expected_sha256=EXPECTED_SOURCE_SHA256,
        security_master=security_master,
        ohlcv_by_ticker=ohlcv,
        standard_windows=standard_windows,
        as_of_date=as_of_date,
        market_calendar=market_calendar,
    )
    snapshot = {
        **snapshot,
        "experiment_id": EXPERIMENT_ID,
        "source_manifest_sha256": source_audit["manifest_sha256"],
        "one_shot_parity_artifact": True,
        "daily_wiring_retained": False,
        "live_orders_changed": False,
    }
    _atomic_write_json(PAPER_SNAPSHOT_PATH, snapshot)

    accepted = bool(gate4["passed"])
    return {
        "schema": "pcaob_partner_change_peer_substitution_full_stack_result_v1",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lane": "alpha_search",
        "status": "accepted_paper_pending_forward" if accepted else "rejected",
        "decision": (
            "accepted_paper_pending_forward_pcaob_partner_change_peer_substitution"
            if accepted
            else "rejected_pcaob_partner_change_peer_substitution"
        ),
        "accepted_alpha": accepted,
        "hypothesis": (
            "When official PCAOB Form AP first reports an engagement-partner "
            "change, buy the unchanged same-industry peer with the highest "
            "trailing 60-session dollar volume at the next open for 20 sessions."
        ),
        "rule_version": RULE_VERSION,
        "locked_policy": historical["policy"],
        "source": {
            "contract": source_audit,
            "helper_provenance": historical["source_provenance"],
            "event_audit": historical["event_audit"],
            "universe_audit": historical["universe_audit"],
        },
        "input_identity": input_identity,
        "windows": windows,
        "aggregate": aggregate,
        "target_summary": target,
        "share_class_usage": share_class,
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
            "shared_helper": (
                "quant/pcaob_form_ap_partner_change_peer_substitution_paper_sleeve.py"
            ),
            "historical_and_daily_selection_share_helper": True,
        },
        "residual_unknowns": [
            "The current yfinance-derived industry map is survivorship-prone and is not point-in-time membership.",
            "The exact-CIK share-class tie-break uses three-window liquidity; any selected multi-share peer is therefore blocked as non-PIT.",
            "The single selected trial declares an incomplete selection pool, so DSR fails closed for live eligibility only.",
            "No prospectively settled forward rows, replacement-value proof, or kill-switch parity exist.",
            "A historical association cannot establish that audit uncertainty causes demand substitution rather than an industry-wide risk response.",
        ],
        "post_run_reflection": {
            "why_result_happened": (
                "; ".join(gate4["hard_failures"])
                if gate4["hard_failures"]
                else "The locked PCAOB peer-substitution source cleared every Gate-4 bar."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune filing scope, fiscal gap, share mapping, industry map, "
                "peer pool, rank, daily top1, entry clock, hold, notional, or costs."
            ),
            "next_retry_requires": (
                "A genuinely new source/gate shape or materially more prospectively "
                "settled PCAOB rows with replacement-value evidence."
            ),
        },
        "reproduction_commands": [
            f".\\.venv\\Scripts\\python.exe -B quant\\experiments\\{Path(__file__).name} --evaluate"
        ],
    }


def _write_outputs(payload: dict[str, Any]) -> None:
    _atomic_write_json(RESULT_PATH, payload)
    for path, side in ((BEFORE_PATH, "before"), (AFTER_PATH, "after")):
        _atomic_write_json(
            path,
            {
                "schema": f"pcaob_partner_change_peer_substitution_gate4_{side}_v1",
                "experiment_id": EXPERIMENT_ID,
                "expected_value_score": payload["aggregate"][
                    f"{side}_expected_value_score_sum"
                ],
                "total_pnl": payload["aggregate"][f"{side}_total_pnl_sum"],
                "max_drawdown_pct": max(
                    row[side]["max_drawdown_pct"]
                    for row in payload["windows"].values()
                ),
                "total_trades": sum(
                    row[side]["total_trades"] for row in payload["windows"].values()
                ),
                "survival_rate": (
                    payload["gate3"]["survival_rate"]
                    if side == "after"
                    else min(
                        row["before"]["survival_rate"]
                        for row in payload["windows"].values()
                    )
                ),
                "benchmarks": {
                    "strategy_total_return_pct": round(
                        payload["aggregate"][f"{side}_total_pnl_sum"] / 100_000.0,
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
    payload = _build_evaluation_payload()
    _write_outputs(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "aggregate": payload["aggregate"],
                "window_standalone": {
                    label: row["standalone_diagnostics"]
                    for label, row in payload["windows"].items()
                },
                "window_coverage": {
                    label: row["coverage_audit"]
                    for label, row in payload["windows"].items()
                },
                "gate2": payload["gate2"],
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
