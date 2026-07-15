"""exp-20260715-004: FDA Orange Book fresh-NEWA release basket.

This runner evaluates exactly one preregistered policy.  It consumes the
hash-bound official monthly Additions/Deletions PDF archive through the shared
default-off paper helper, maps each official release to every eligible exact-
mapped issuer, allocates a fixed $16,000 equally across those issuer legs, and
holds from the next regular-session open through the tenth-session close.

The three active standard windows are evaluated with daily mark-to-market in
both standalone and core-plus-sleeve form.  Gate 1-4 remain independent from
the complete fixed-policy off/on Deflated-Sharpe panel used only for Gate 5.
There are no CLI policy parameters, threshold sweeps, subtype variants, or
top-N variants in this module.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import sys
import tempfile
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Any, Iterable


EXPERIMENT_ID = "exp-20260715-004"
REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (REPO_ROOT, QUANT_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from deflated_sharpe import build_report as build_dsr_report  # noqa: E402
from orange_book_newa_release_basket_paper_sleeve import (  # noqa: E402
    DEFAULT_MANIFEST_PATH,
    HOLD_SESSIONS,
    LANDING_URL,
    RELEASE_BUDGET_USD,
    ROUND_TRIP_COST_PCT,
    RULE_VERSION,
    build_historical_release_legs,
    load_and_verify_source,
    replay_orange_book_newa_release_basket_paper_trades,
)
from quant.evaluator_gates import ExperimentGateThresholds  # noqa: E402
from quant.full_stack_candidate_pool import (  # noqa: E402
    ExecutionEnvelope,
    evaluate_gate4,
    evaluate_live_readiness,
    full_stack_verdict,
)


BASELINE_SUMMARY_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_post_mtm_20260712.json"
)
WAREHOUSE_PATH = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"
SOURCE_DIR = REPO_ROOT / "data" / "non_ohlcv" / "fda_orange_book_newa"
SOURCE_MANIFEST_PATH = SOURCE_DIR / "source_manifest.json"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
AUXILIARY_OHLCV_PATH = OUT_DIR / "auxiliary_ohlcv.json"
RESULT_PATH = OUT_DIR / "fda_orange_book_newa_release_basket_replay.json"
BEFORE_PATH = OUT_DIR / "before.json"
AFTER_PATH = OUT_DIR / "after.json"
STANDALONE_PATH = OUT_DIR / "standalone.json"
DSR_PANEL_PATH = OUT_DIR / "deflated_sharpe_panel.json"
DSR_REPORT_PATH = OUT_DIR / "deflated_sharpe_report.json"
ARTIFACT_PATH = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_fda_orange_book_newa_release_basket.md"
)

WINDOWS = OrderedDict(
    (
        ("old_thin", ("2024-10-02", "2025-04-22")),
        ("mid_weak", ("2025-04-23", "2025-10-22")),
        ("late_strong", ("2025-10-23", "2026-04-21")),
    )
)

AUXILIARY_START = "2024-09-01"
AUXILIARY_END = "2026-05-15"
REFERENCE_TICKERS = ("SPY", "QQQ")
INITIAL_EQUITY_USD = 100_000.0

# Locked ticket policy and acceptance bars.  The explicit runtime assertions
# below fail closed if the shared helper drifts from these preregistered values.
LOCKED_RELEASE_BUDGET_USD = 16_000.0
LOCKED_HOLD_SESSIONS = 10
LOCKED_ROUND_TRIP_COST_PCT = 0.0035
MIN_ISSUER_RELEASE_LEGS_PER_WINDOW = 20
MIN_TICKERS_PER_WINDOW = 10
MAX_TOP1_LEG_SHARE = 0.30
MIN_SURVIVAL_RATE = 0.05
MAX_DRAWDOWN_WORSE = 0.005
MAX_TOP5_POSITIVE_SHARE = 0.60
MAX_SINGLE_POSITIVE_SHARE = 0.50
EXPECTED_DSR_ATTEMPTS = 2
COMPARATOR = {
    "experiment_id": "exp-20260611-007",
    "expected_value_score_delta_sum": 0.5286,
    "total_pnl_delta_sum": 10432.91,
}
PREDICTION = {
    "success_probability": 0.25,
    "expected_ev_delta": 0.65,
    "expected_pnl_delta": 12000.0,
    "main_failure_modes": [
        "monthly_publication_lag_erases_drift",
        "generic_product_additions_are_immaterial",
        "event_date_parent_mapping_survivorship",
        "release_basket_capital_concentration",
        "accepted_candidate_comparator_not_beaten",
    ],
}


class RunnerContractError(RuntimeError):
    """Raised when a frozen input or shared-policy contract drifts."""


def _repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _json_bytes(payload: Any) -> bytes:
    return (
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = _json_bytes(payload)
    with tempfile.NamedTemporaryFile(
        mode="wb",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(raw)
        handle.flush()
        temporary = Path(handle.name)
    temporary.replace(path)


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = text.encode("utf-8")
    with tempfile.NamedTemporaryFile(
        mode="wb",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(raw)
        handle.flush()
        temporary = Path(handle.name)
    temporary.replace(path)


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


def _return_series_sha(rows: list[dict[str, Any]]) -> str:
    return _canonical_sha(
        {"schema": "dated_periodic_return_series_v1", "rows": rows}
    )


def _assert_locked_policy() -> None:
    checks = {
        "manifest_path": Path(DEFAULT_MANIFEST_PATH).resolve()
        == SOURCE_MANIFEST_PATH.resolve(),
        "release_budget": math.isclose(
            float(RELEASE_BUDGET_USD), LOCKED_RELEASE_BUDGET_USD
        ),
        "hold_sessions": int(HOLD_SESSIONS) == LOCKED_HOLD_SESSIONS,
        "round_trip_cost": math.isclose(
            float(ROUND_TRIP_COST_PCT), LOCKED_ROUND_TRIP_COST_PCT
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise RunnerContractError(
            f"shared Orange Book helper drifted from locked policy: {failed}"
        )


def _verify_manifest_bytes() -> dict[str, Any]:
    """Independently bind Gate 2 to every official PDF and derived input."""
    if not SOURCE_MANIFEST_PATH.is_file():
        raise RunnerContractError("Orange Book source manifest is missing")
    manifest = _read_json(SOURCE_MANIFEST_PATH)
    documents = list(manifest.get("documents") or [])
    integrity = dict(manifest.get("integrity") or {})
    if manifest.get("experiment_id") != EXPERIMENT_ID:
        raise RunnerContractError("Orange Book manifest experiment id drifted")
    if integrity.get("status") != "all_verified":
        raise RunnerContractError("Orange Book manifest is not all_verified")
    if int(integrity.get("document_count") or 0) != len(documents):
        raise RunnerContractError("Orange Book manifest document count drifted")
    if len(documents) != 19:
        raise RunnerContractError("Orange Book archive must contain 19 PDFs")

    verified: list[dict[str, Any]] = []
    months: list[str] = []
    media_ids: list[int] = []
    total_bytes = 0
    for row in documents:
        relative = Path(str(row.get("relative_path") or ""))
        path = (SOURCE_DIR / relative).resolve()
        try:
            path.relative_to(SOURCE_DIR.resolve())
        except ValueError as error:
            raise RunnerContractError("manifest path escaped source root") from error
        if not path.is_file():
            raise RunnerContractError(f"manifest file missing: {relative.as_posix()}")
        expected_bytes = int(row.get("bytes") or -1)
        expected_sha = str(row.get("sha256") or "").lower()
        actual_bytes = path.stat().st_size
        actual_sha = _file_sha(path)
        if actual_bytes != expected_bytes or actual_sha != expected_sha:
            raise RunnerContractError(
                f"Orange Book raw byte/hash drift: {relative.as_posix()}"
            )
        month = str(row.get("month") or "")
        media_id = int(row.get("media_id"))
        publication_utc = str(
            row.get("official_http_last_modified_utc") or ""
        )
        if len(month) != 7 or not publication_utc.endswith("Z"):
            raise RunnerContractError("Orange Book document PIT metadata drifted")
        months.append(month)
        media_ids.append(media_id)
        total_bytes += actual_bytes
        verified.append(
            {
                "month": month,
                "media_id": media_id,
                "relative_path": relative.as_posix(),
                "official_http_last_modified_utc": publication_utc,
                "bytes": actual_bytes,
                "sha256": actual_sha,
                "verified": True,
            }
        )
    if months != sorted(set(months)) or len(media_ids) != len(set(media_ids)):
        raise RunnerContractError("Orange Book manifest documents are not unique/sorted")
    if total_bytes != int(integrity.get("total_bytes") or -1):
        raise RunnerContractError("Orange Book manifest total byte count drifted")

    derived_verified: list[dict[str, Any]] = []
    for row in manifest.get("derived_artifacts") or []:
        relative = Path(str(row.get("relative_path") or ""))
        path = (SOURCE_DIR / relative).resolve()
        if not path.is_file():
            raise RunnerContractError(f"derived source input missing: {relative}")
        expected_sha = row.get("sha256")
        expected_bytes = row.get("bytes")
        actual_sha = _file_sha(path)
        actual_bytes = path.stat().st_size
        # A derived manifest row without an expected identity cannot support
        # Gate 2.  It is allowed only when it is not consumed by the helper.
        consumed = relative.as_posix() in {
            "preflight_detail.json",
            "preflight_summary.json",
        }
        if consumed and (not expected_sha or expected_bytes is None):
            raise RunnerContractError(
                f"consumed derived input lacks hash/size: {relative.as_posix()}"
            )
        if expected_sha and actual_sha != str(expected_sha).lower():
            raise RunnerContractError(f"derived input hash drift: {relative}")
        if expected_bytes is not None and actual_bytes != int(expected_bytes):
            raise RunnerContractError(f"derived input size drift: {relative}")
        derived_verified.append(
            {
                "relative_path": relative.as_posix(),
                "bytes": actual_bytes,
                "sha256": actual_sha,
                "verified": bool(expected_sha and expected_bytes is not None),
            }
        )

    semantics = dict(manifest.get("point_in_time_semantics") or {})
    expected_semantics = {
        "addition_marker": ">A>",
        "terminal_change_reason": "NEWA",
        "event_timestamp": "official PDF HTTP Last-Modified UTC",
    }
    for field, expected in expected_semantics.items():
        if semantics.get(field) != expected:
            raise RunnerContractError(f"Orange Book PIT semantic drift: {field}")
    if "45 calendar days" not in str(semantics.get("freshness_rule") or ""):
        raise RunnerContractError("Orange Book freshness rule drifted")
    if "no fuzzy matching" not in str(semantics.get("mapping_rule") or ""):
        raise RunnerContractError("Orange Book exact mapping rule drifted")

    return {
        "path": _repo_rel(SOURCE_MANIFEST_PATH),
        "sha256": _file_sha(SOURCE_MANIFEST_PATH),
        "document_count": len(verified),
        "total_bytes": total_bytes,
        "all_official_documents_verified": all(
            row["verified"] for row in verified
        ),
        "all_consumed_derived_inputs_verified": all(
            row["verified"] for row in derived_verified
        ),
        "documents": verified,
        "derived_artifacts": derived_verified,
        "point_in_time_semantics": semantics,
        "latest_official_publication_utc": max(
            row["official_http_last_modified_utc"] for row in verified
        ),
    }


def _validate_decisions(
    decisions: list[dict[str, Any]], manifest_audit: dict[str, Any]
) -> dict[str, Any]:
    documents = {
        int(row["media_id"]): row for row in manifest_audit["documents"]
    }
    application_event_ids: set[str] = set()
    by_ticker: Counter[str] = Counter()
    by_month: Counter[str] = Counter()
    for row in decisions:
        ticker = str(row.get("ticker") or "")
        month = str(row.get("month") or "")
        media_id = int(row.get("media_id"))
        publication_utc = str(
            row.get("official_http_last_modified_utc") or ""
        )
        signal_timestamp = str(row.get("signal_timestamp") or "")
        signal_date = str(row.get("signal_date") or "")
        approval_date = str(row.get("approval_date") or "")
        approval_age_days = int(row.get("approval_age_days"))
        application_number = str(row.get("application_number") or "")
        application_event_id = str(row.get("application_event_id") or "")
        document = documents.get(media_id)
        if document is None or document["month"] != month:
            raise RunnerContractError("decision is not bound to a manifest document")
        if publication_utc != document["official_http_last_modified_utc"]:
            raise RunnerContractError("decision publication clock is not manifest PIT")
        if signal_timestamp != publication_utc or signal_date != publication_utc[:10]:
            raise RunnerContractError("decision signal clock is not HTTP Last-Modified")
        if (
            not ticker
            or not approval_date
            or not application_number
            or not application_event_id
            or not 0 <= approval_age_days <= 45
        ):
            raise RunnerContractError("decision freshness/mapping contract drifted")
        if row.get("row_filter") != "addition_marker_and_terminal_NEWA":
            raise RunnerContractError("non-NEWA row reached Orange Book decisions")
        if row.get("mapping_rule") != "exact_event_date_holder_alias_no_fuzzy":
            raise RunnerContractError("non-exact mapping reached Orange Book decisions")
        if row.get("source_pdf_sha256") != document["sha256"]:
            raise RunnerContractError("decision source PDF hash is not manifest-bound")
        if not row.get("source_line_sha256s"):
            raise RunnerContractError("decision lacks source-line provenance")
        if application_event_id in application_event_ids:
            raise RunnerContractError("duplicate application-level decision")
        application_event_ids.add(application_event_id)
        by_ticker[ticker] += 1
        by_month[month] += 1
    if not decisions:
        raise RunnerContractError("Orange Book helper returned no decisions")
    return {
        "decision_count": len(decisions),
        "ticker_count": len(by_ticker),
        "month_count": len(by_month),
        "by_ticker": dict(sorted(by_ticker.items())),
        "by_month": dict(sorted(by_month.items())),
        "decisions_sha256": _canonical_sha(decisions),
    }


def _baseline_window_map(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row["label"]): row for row in summary["windows"]}


def _baseline_return_series(window: dict[str, Any]) -> list[dict[str, Any]]:
    artifact = _read_json(REPO_ROOT / str(window["path"]))
    rows = list(artifact["sharpe_inference"]["return_series"])
    actual = _return_series_sha(rows)
    expected = str(window.get("daily_return_series_sha256") or "")
    if expected and actual != expected:
        raise RunnerContractError(
            f"baseline return-series hash drift for {window['label']}"
        )
    return rows


def _baseline_curve(window: dict[str, Any]) -> list[tuple[str, float]]:
    equity = INITIAL_EQUITY_USD
    curve: list[tuple[str, float]] = []
    for row in _baseline_return_series(window):
        equity *= 1.0 + float(row["return"])
        curve.append((str(row["date"]), equity))
    expected = INITIAL_EQUITY_USD + float(window["total_pnl"])
    if not curve or abs(curve[-1][1] - expected) > 0.02:
        raise RunnerContractError(
            f"baseline return reconstruction drift for {window['label']}"
        )
    return curve


def _materialize_auxiliary_ohlcv(tickers: Iterable[str]) -> dict[str, Any]:
    expected_tickers = sorted(set(tickers) | set(REFERENCE_TICKERS))
    if AUXILIARY_OHLCV_PATH.exists():
        payload = _read_json(AUXILIARY_OHLCV_PATH)
        rows = dict(payload.get("ohlcv") or {})
        if payload.get("start") != AUXILIARY_START:
            raise RunnerContractError("frozen auxiliary OHLCV start drifted")
        if payload.get("end") != AUXILIARY_END:
            raise RunnerContractError("frozen auxiliary OHLCV end drifted")
        if list(payload.get("tickers") or []) != expected_tickers:
            raise RunnerContractError("frozen auxiliary OHLCV ticker set drifted")
        if payload.get("rowset_sha256") != _canonical_sha(rows):
            raise RunnerContractError("frozen auxiliary OHLCV hash drifted")
        return payload

    if not WAREHOUSE_PATH.is_file():
        raise RunnerContractError("broad OHLCV warehouse is missing")
    placeholders = ",".join("?" for _ in expected_tickers)
    query = f"""
        SELECT ticker, date, open, high, low, close, volume
        FROM ohlcv
        WHERE ticker IN ({placeholders}) AND date >= ? AND date <= ?
        ORDER BY ticker, date
    """
    rows_by_ticker: dict[str, list[dict[str, Any]]] = {
        ticker: [] for ticker in expected_tickers
    }
    with sqlite3.connect(str(WAREHOUSE_PATH)) as connection:
        for ticker, day, open_, high, low, close, volume in connection.execute(
            query, [*expected_tickers, AUXILIARY_START, AUXILIARY_END]
        ):
            rows_by_ticker[str(ticker)].append(
                {
                    "date": str(day),
                    "open": open_,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": volume,
                }
            )
    if not rows_by_ticker.get("SPY") or not rows_by_ticker.get("QQQ"):
        raise RunnerContractError("required SPY/QQQ auxiliary OHLCV is missing")
    payload = {
        "schema": "fda_orange_book_newa_auxiliary_ohlcv_v1",
        "source_at_freeze": _repo_rel(WAREHOUSE_PATH),
        "start": AUXILIARY_START,
        "end": AUXILIARY_END,
        "tickers": expected_tickers,
        "missing_tickers": sorted(
            ticker for ticker, rows in rows_by_ticker.items() if not rows
        ),
        "ticker_row_counts": {
            ticker: len(rows_by_ticker[ticker]) for ticker in expected_tickers
        },
        "rowset_sha256": _canonical_sha(rows_by_ticker),
        "ohlcv": rows_by_ticker,
    }
    _atomic_write_json(AUXILIARY_OHLCV_PATH, payload)
    return payload


def _window_ohlcv(
    broad: dict[str, list[dict[str, Any]]],
    baseline: dict[str, Any],
    tickers: Iterable[str],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    expected_tickers = sorted(set(tickers) | set(REFERENCE_TICKERS))
    snapshot_path = REPO_ROOT / str(baseline["source"])
    snapshot = dict((_read_json(snapshot_path).get("ohlcv") or {}))
    output = {ticker: list(broad.get(ticker) or []) for ticker in expected_tickers}
    exact: list[str] = []
    for ticker in expected_tickers:
        if snapshot.get(ticker):
            output[ticker] = list(snapshot[ticker])
            exact.append(ticker)
    missing = sorted(ticker for ticker in expected_tickers if not output[ticker])
    if "SPY" in missing:
        raise RunnerContractError("required SPY window OHLCV is missing")
    return output, {
        "gate1_snapshot": _repo_rel(snapshot_path),
        "gate1_snapshot_sha256": _file_sha(snapshot_path),
        "exact_snapshot_tickers": sorted(exact),
        "frozen_auxiliary_fill_tickers": sorted(
            set(expected_tickers) - set(exact)
        ),
        "missing_tickers": missing,
    }


def _metric_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _bar_date(row: dict[str, Any]) -> str:
    return str(row.get("date") or row.get("Date") or "")[:10]


def _bar_index(
    ohlcv: dict[str, list[dict[str, Any]]]
) -> dict[str, dict[str, dict[str, float]]]:
    output: dict[str, dict[str, dict[str, float]]] = {}
    for ticker, rows in ohlcv.items():
        output[ticker] = {}
        for row in rows:
            day = _bar_date(row)
            open_ = _metric_number(
                row.get("open") if "open" in row else row.get("Open")
            )
            close = _metric_number(
                row.get("close") if "close" in row else row.get("Close")
            )
            if day and open_ is not None and close is not None:
                output[ticker][day] = {"open": open_, "close": close}
    return output


def _target_mark_on_date(
    trades: list[dict[str, Any]],
    bars: dict[str, dict[str, dict[str, float]]],
    day: str,
) -> float:
    mark = 0.0
    for trade in trades:
        entry_date = str(trade["entry_date"])
        exit_date = str(trade["exit_date"])
        if day < entry_date:
            continue
        if day >= exit_date:
            mark += float(trade["pnl"])
            continue
        close_row = bars.get(str(trade["ticker"]), {}).get(day)
        if close_row is None:
            raise RunnerContractError(
                f"missing Orange Book MTM close for {trade['ticker']} on {day}"
            )
        gross = close_row["close"] / float(trade["entry_price"]) - 1.0
        mark += float(trade["paper_notional_usd"]) * (
            gross - float(ROUND_TRIP_COST_PCT) / 2.0
        )
    return mark


def _curve_metrics(
    curve: list[tuple[str, float]], *, trade_count: int
) -> dict[str, Any]:
    if not curve:
        raise RunnerContractError("cannot calculate metrics from an empty curve")
    previous = INITIAL_EQUITY_USD
    peak = INITIAL_EQUITY_USD
    drawdown = 0.0
    returns: list[dict[str, Any]] = []
    for day, equity in curve:
        if not math.isfinite(equity) or equity <= 0:
            raise RunnerContractError("daily MTM equity became invalid")
        periodic_return = equity / previous - 1.0
        returns.append({"date": day, "return": periodic_return})
        previous = equity
        peak = max(peak, equity)
        drawdown = max(drawdown, (peak - equity) / peak)
    samples = [float(row["return"]) for row in returns]
    sharpe_full = None
    if len(samples) >= 2:
        mean = sum(samples) / len(samples)
        variance = sum((value - mean) ** 2 for value in samples) / (
            len(samples) - 1
        )
        if variance > 0:
            sharpe_full = mean / math.sqrt(variance) * math.sqrt(252)
    total_pnl = curve[-1][1] - INITIAL_EQUITY_USD
    total_return = round(total_pnl / INITIAL_EQUITY_USD, 4)
    sharpe_public = round(sharpe_full, 2) if sharpe_full is not None else None
    return {
        "total_pnl": round(total_pnl, 2),
        "benchmarks": {"strategy_total_return_pct": total_return},
        "sharpe_daily": sharpe_public,
        "sharpe_daily_full_precision": sharpe_full,
        "expected_value_score": (
            round(total_return * sharpe_public, 4)
            if sharpe_public is not None
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
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    base_curve = _baseline_curve(baseline)
    bars = _bar_index(ohlcv)
    marks = [
        (day, _target_mark_on_date(trades, bars, day))
        for day, _ in base_curve
    ]
    combined_curve = [
        (day, equity + mark)
        for (day, equity), (_, mark) in zip(base_curve, marks)
    ]
    standalone_curve = [
        (day, INITIAL_EQUITY_USD + mark) for day, mark in marks
    ]
    before = {
        "total_pnl": float(baseline["total_pnl"]),
        "benchmarks": {
            "strategy_total_return_pct": round(
                float(baseline["total_pnl"]) / INITIAL_EQUITY_USD, 4
            )
        },
        "sharpe_daily": baseline["sharpe_daily"],
        "sharpe_daily_full_precision": baseline[
            "sharpe_daily_full_precision"
        ],
        "expected_value_score": baseline["expected_value_score"],
        "max_drawdown_pct": baseline["max_drawdown_pct"],
        "total_trades": baseline["trade_count"],
        "signals_generated": baseline["signals_generated"],
        "signals_survived": baseline["signals_survived"],
        "survival_rate": baseline["survival_rate"],
        "return_series": _baseline_return_series(baseline),
    }
    before["return_series_sha256"] = _return_series_sha(
        before["return_series"]
    )
    after = _curve_metrics(
        combined_curve, trade_count=int(baseline["trade_count"]) + len(trades)
    )
    standalone = _curve_metrics(standalone_curve, trade_count=len(trades))
    closed_trade_pnl = round(sum(float(row["pnl"]) for row in trades), 2)
    if abs(float(standalone["total_pnl"]) - closed_trade_pnl) > 0.02:
        raise RunnerContractError("daily MTM endpoint does not reconcile to trades")
    return before, after, standalone


def _leg_identity(row: dict[str, Any]) -> tuple[str, str]:
    release = str(
        row.get("release_id")
        or row.get("decision_id")
        or row.get("publication_utc")
        or row.get("publication_date")
        or row.get("month")
        or ""
    )
    ticker = str(row.get("ticker") or "")
    if not release or not ticker:
        raise RunnerContractError("historical leg lacks release/ticker identity")
    return release, ticker


def _density_summary(legs: list[dict[str, Any]]) -> dict[str, Any]:
    identities = [_leg_identity(row) for row in legs]
    if len(identities) != len(set(identities)):
        raise RunnerContractError("historical release legs are not deduplicated")
    by_ticker = Counter(ticker for _, ticker in identities)
    by_release = Counter(release for release, _ in identities)
    total = len(identities)
    top1 = max(by_ticker.values(), default=0) / total if total else 0.0
    return {
        "issuer_release_leg_count": total,
        "ticker_count": len(by_ticker),
        "release_count": len(by_release),
        "top1_leg_share": round(top1, 6),
        "by_ticker": dict(sorted(by_ticker.items())),
        "by_release": dict(sorted(by_release.items())),
        "legs_sha256": _canonical_sha(legs),
        "passes": {
            "issuer_release_legs_gte_20": total
            >= MIN_ISSUER_RELEASE_LEGS_PER_WINDOW,
            "tickers_gte_10": len(by_ticker) >= MIN_TICKERS_PER_WINDOW,
            "top1_lte_30pct": top1 <= MAX_TOP1_LEG_SHARE,
        },
    }


def _validate_preflight_density(
    density_by_window: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Require the live PDF parser to reproduce the corrected preflight."""
    path = SOURCE_DIR / "preflight_summary.json"
    summary = _read_json(path)
    if summary.get("experiment_id") != EXPERIMENT_ID:
        raise RunnerContractError("preflight summary experiment id drifted")
    if summary.get("discrepancies"):
        raise RunnerContractError("preflight summary contains unresolved discrepancies")
    expected_windows = dict(summary.get("windows") or {})
    if set(expected_windows) != set(WINDOWS):
        raise RunnerContractError("preflight summary window labels drifted")
    comparisons: dict[str, Any] = {}
    for label, (start, end) in WINDOWS.items():
        expected = expected_windows[label]
        actual = density_by_window[label]
        checks = {
            "window_dates": expected.get("start") == start
            and expected.get("end") == end,
            "issuer_release_count": int(
                expected.get("issuer_release_count") or -1
            )
            == actual["issuer_release_leg_count"],
            "ticker_count": int(expected.get("ticker_count") or -1)
            == actual["ticker_count"],
            "top1_share": math.isclose(
                float(expected.get("top1_share")),
                float(actual["top1_leg_share"]),
                abs_tol=1e-6,
            ),
            "by_ticker": dict(expected.get("by_ticker") or {})
            == actual["by_ticker"],
            "corrected_fms_mapping_absent": "FMS"
            not in dict(expected.get("by_ticker") or {})
            and "FMS" not in actual["by_ticker"],
            "preregistered_gates_passed": bool(
                (expected.get("gates") or {}).get("all_passed")
            ),
            "corrected_live_gates_passed": all(actual["passes"].values()),
        }
        failed = [name for name, passed in checks.items() if not passed]
        if failed:
            raise RunnerContractError(
                f"PDF parser/preflight density disagreement in {label}: {failed}"
            )
        comparisons[label] = {
            "passed": True,
            "checks": checks,
        }
    derived_from = dict(summary.get("derived_from") or {})
    detail_path = SOURCE_DIR / str(derived_from.get("relative_path") or "")
    if not detail_path.is_file() or _file_sha(detail_path) != derived_from.get(
        "sha256"
    ):
        raise RunnerContractError("preflight summary is not bound to its detail input")
    return {
        "passed": True,
        "path": _repo_rel(path),
        "sha256": _file_sha(path),
        "detail_path": _repo_rel(detail_path),
        "detail_sha256": _file_sha(detail_path),
        "pdf_parser_matches_corrected_preflight": True,
        "mapping_corrections": list(summary.get("mapping_corrections") or []),
        "windows": comparisons,
    }


def _target_summary(
    trades_by_window: dict[str, list[dict[str, Any]]],
    density_by_window: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    pnl: Counter[str] = Counter()
    counts: Counter[str] = Counter()
    by_release_pnl: Counter[str] = Counter()
    for trades in trades_by_window.values():
        for trade in trades:
            ticker = str(trade["ticker"])
            release, _ = _leg_identity(trade)
            pnl[ticker] += float(trade["pnl"])
            counts[ticker] += 1
            by_release_pnl[release] += float(trade["pnl"])
    positive = {ticker: value for ticker, value in pnl.items() if value > 0}
    positive_total = sum(positive.values())
    shares = (
        sorted(
            (value / positive_total for value in positive.values()),
            reverse=True,
        )
        if positive_total
        else []
    )
    return {
        "total_trade_count": sum(counts.values()),
        "eligible_issuer_release_leg_count": sum(
            row["issuer_release_leg_count"] for row in density_by_window.values()
        ),
        "ticker_count": len(counts),
        "tickers": sorted(counts),
        "window_count": sum(bool(rows) for rows in trades_by_window.values()),
        "by_window_trade_count": {
            label: len(trades_by_window[label]) for label in WINDOWS
        },
        "by_window_eligible_leg_count": {
            label: density_by_window[label]["issuer_release_leg_count"]
            for label in WINDOWS
        },
        "by_ticker_count": dict(sorted(counts.items())),
        "by_ticker_pnl": {
            ticker: round(value, 2) for ticker, value in sorted(pnl.items())
        },
        "by_release_pnl": {
            release: round(value, 2)
            for release, value in sorted(by_release_pnl.items())
        },
        "total_pnl": round(sum(pnl.values()), 2),
        "single_ticker_positive_share": round(shares[0], 6) if shares else None,
        "hhi_concentration": (
            round(sum(share * share for share in shares), 6) if shares else None
        ),
        "top_5_contribution_pct": (
            round(sum(shares[:5]), 6) if shares else None
        ),
    }


def _aggregate_windows(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "before_expected_value_score_sum": round(
            sum(float(row["before"]["expected_value_score"]) for row in rows.values()),
            4,
        ),
        "after_expected_value_score_sum": round(
            sum(float(row["after"]["expected_value_score"]) for row in rows.values()),
            4,
        ),
        "expected_value_score_delta_sum": round(
            sum(float(row["delta"]["expected_value_score"]) for row in rows.values()),
            4,
        ),
        "standalone_expected_value_score_sum": round(
            sum(float(row["standalone"]["expected_value_score"]) for row in rows.values()),
            4,
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
        "standalone_total_pnl_sum": round(
            sum(float(row["standalone"]["total_pnl"]) for row in rows.values()), 2
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
            float(row["delta"]["max_drawdown_pct"]) for row in rows.values()
        ),
    }


def _concatenate_return_series(
    rows: dict[str, Any], side: str
) -> list[dict[str, Any]]:
    combined = [
        point
        for label in sorted(WINDOWS, key=lambda item: WINDOWS[item][0])
        for point in rows[label][side]["return_series"]
    ]
    dates = [str(row["date"]) for row in combined]
    if dates != sorted(dates) or len(dates) != len(set(dates)):
        raise RunnerContractError(f"{side} DSR return dates are not unique/sorted")
    return combined


def _build_dsr_evidence(
    rows: dict[str, Any],
    source: dict[str, Any],
    auxiliary: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    before = _concatenate_return_series(rows, "before")
    after = _concatenate_return_series(rows, "after")
    if [row["date"] for row in before] != [row["date"] for row in after]:
        raise RunnerContractError("DSR off/on dates are not exactly aligned")
    ordered_windows = sorted(WINDOWS, key=lambda item: WINDOWS[item][0])
    context = {
        "selection_scope": (
            "fda_orange_book_monthly_fresh_newa_equal_weight_release_basket"
        ),
        "window": {
            "segments": [
                {"label": label, "start": WINDOWS[label][0], "end": WINDOWS[label][1]}
                for label in ordered_windows
            ]
        },
        "frequency": "daily",
        "return_basis": "strategy_equity_return_post_cost_daily_mtm",
        "risk_free_assumption": "zero",
        "protocol": {
            "id": "post_mtm_gate1_plus_orange_book_newa_release_basket_v1",
            "baseline": _repo_rel(BASELINE_SUMMARY_PATH),
            "rule_version": RULE_VERSION,
            "fixed_policy_only": True,
            "threshold_sweeps": 0,
        },
        "data": {
            "baseline_summary_sha256": _file_sha(BASELINE_SUMMARY_PATH),
            "source_manifest_sha256": source["manifest_audit"]["sha256"],
            "decisions_sha256": source["decision_audit"]["decisions_sha256"],
            "auxiliary_ohlcv_sha256": auxiliary["rowset_sha256"],
        },
        "cost": {
            "core": "pinned_post_mtm_gate1_cost_model",
            "orange_book_round_trip_cost_pct": ROUND_TRIP_COST_PCT,
        },
    }
    configs = (
        (
            "core_orange_book_newa_off",
            {"core": "active_post_mtm", "orange_book_newa_sleeve": False},
            before,
            f"{_repo_rel(RESULT_PATH)}#windows.*.before.return_series",
        ),
        (
            "core_orange_book_newa_on",
            {
                "core": "active_post_mtm",
                "orange_book_newa_sleeve": True,
                "locked_policy": RULE_VERSION,
            },
            after,
            f"{_repo_rel(RESULT_PATH)}#windows.*.after.return_series",
        ),
    )
    trials = [
        {
            "config_id": config_id,
            "config": config,
            "attempted": True,
            **context,
            "return_series": series,
            "return_series_sha256": _return_series_sha(series),
            "return_series_source": locator,
        }
        for config_id, config, series, locator in configs
    ]
    panel = {
        "selected_config_id": "core_orange_book_newa_on",
        "expected_attempt_count": EXPECTED_DSR_ATTEMPTS,
        "selection_pool_complete": True,
        "expected_return_dates": [row["date"] for row in before],
        "periods_per_year": 252,
        "trials": trials,
    }
    report = build_dsr_report(panel)
    report["gate4_independence"] = True
    _atomic_write_json(DSR_PANEL_PATH, panel)
    _atomic_write_json(DSR_REPORT_PATH, report)
    return panel, report


def _safe_le(value: float | None, maximum: float) -> bool:
    return value is not None and float(value) <= maximum


def build_payload() -> dict[str, Any]:
    _assert_locked_policy()
    manifest_audit = _verify_manifest_bytes()
    decisions, helper_source_identity = load_and_verify_source(
        manifest_path=SOURCE_MANIFEST_PATH
    )
    decisions = [dict(row) for row in decisions]
    decision_audit = _validate_decisions(decisions, manifest_audit)
    source = {
        "landing_url": LANDING_URL,
        "rule_version": RULE_VERSION,
        "manifest_audit": manifest_audit,
        "helper_source_identity": helper_source_identity,
        "decision_audit": decision_audit,
    }

    all_legs = build_historical_release_legs(decisions)
    tickers = sorted({str(row["ticker"]) for row in all_legs})
    if not tickers:
        raise RunnerContractError("shared helper returned no historical issuer legs")
    auxiliary = _materialize_auxiliary_ohlcv(tickers)
    broad = {
        ticker: list(rows)
        for ticker, rows in dict(auxiliary.get("ohlcv") or {}).items()
    }
    baseline_summary = _read_json(BASELINE_SUMMARY_PATH)
    baseline_windows = _baseline_window_map(baseline_summary)
    if set(baseline_windows) != set(WINDOWS):
        raise RunnerContractError("active Gate-1 baseline window labels drifted")

    windows: dict[str, Any] = {}
    trades_by_window: dict[str, list[dict[str, Any]]] = {}
    density_by_window: dict[str, dict[str, Any]] = {}
    bar_identity: dict[str, Any] = {}
    generated_total = 0
    survived_total = 0
    for label, (start, end) in WINDOWS.items():
        ohlcv, bar_identity[label] = _window_ohlcv(
            broad, baseline_windows[label], tickers
        )
        legs = [
            dict(row)
            for row in build_historical_release_legs(
                decisions, start=start, end=end
            )
        ]
        density = _density_summary(legs)
        replay = replay_orange_book_newa_release_basket_paper_trades(
            decisions=decisions,
            ohlcv_by_ticker=ohlcv,
            start=start,
            end=end,
        )
        candidate_legs = [dict(row) for row in replay["candidate_legs"]]
        if sorted(_leg_identity(row) for row in candidate_legs) != sorted(
            _leg_identity(row) for row in legs
        ):
            raise RunnerContractError(
                f"historical leg builder/replay disagreement in {label}"
            )
        trades = [dict(row, window=label) for row in replay["trades"]]
        before, after, standalone = _combine_window(
            baseline_windows[label], trades, ohlcv
        )
        generated = int(replay["signals_generated"])
        survived = int(replay["signals_survived"])
        survival_rate = float(replay["survival_rate"])
        if generated != len(candidate_legs):
            raise RunnerContractError(f"signal/leg count disagreement in {label}")
        if generated and not math.isclose(
            survival_rate, survived / generated, abs_tol=1e-6
        ):
            raise RunnerContractError(f"survival-rate arithmetic drift in {label}")
        generated_total += generated
        survived_total += survived
        trades_by_window[label] = trades
        density_by_window[label] = density
        windows[label] = {
            "start": start,
            "end": end,
            "before": before,
            "after": after,
            "standalone": standalone,
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
            "density": density,
            "signals_generated": generated,
            "signals_survived": survived,
            "survival_rate": round(survival_rate, 6),
            "candidate_legs": candidate_legs,
            "target_trades": trades,
            "unsettled": replay["unsettled"],
            "reject_totals": replay["reject_totals"],
            "bar_identity": bar_identity[label],
        }

    preflight_audit = _validate_preflight_density(density_by_window)
    source["preflight_audit"] = preflight_audit
    target = _target_summary(trades_by_window, density_by_window)
    aggregate = _aggregate_windows(windows)
    if abs(aggregate["total_pnl_delta_sum"] - target["total_pnl"]) > 0.03:
        raise RunnerContractError("aggregate core delta does not reconcile to sleeve PnL")
    if abs(aggregate["standalone_total_pnl_sum"] - target["total_pnl"]) > 0.03:
        raise RunnerContractError("standalone endpoint does not reconcile to sleeve PnL")

    gate2_source_hashes_passed = bool(
        manifest_audit["all_official_documents_verified"]
        and manifest_audit["all_consumed_derived_inputs_verified"]
        and preflight_audit["pdf_parser_matches_corrected_preflight"]
    )
    gate2_sentinels_passed = bool(target["total_trade_count"]) and all(
        trade.get("entry_date") and trade.get("target_price")
        for trades in trades_by_window.values()
        for trade in trades
    )
    gate2_passed = gate2_source_hashes_passed and gate2_sentinels_passed
    aggregate_survival_rate = (
        survived_total / generated_total if generated_total else 0.0
    )
    gate3_passed = bool(generated_total) and all(
        float(windows[label]["survival_rate"]) >= MIN_SURVIVAL_RATE
        for label in WINDOWS
    )

    gate_metrics = {
        "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
        "windows_ev_improved": aggregate["windows_ev_improved"],
        "windows_ev_regressed": aggregate["windows_ev_regressed"],
        "adjusted_trade_count": target["total_trade_count"],
        "adjusted_windows": [
            label for label, rows in trades_by_window.items() if rows
        ],
        "adjusted_window_count": target["window_count"],
        "max_drawdown_worse_max": aggregate["max_drawdown_worse_max"],
        "single_ticker_positive_share": target[
            "single_ticker_positive_share"
        ],
        "hhi_concentration": target["hhi_concentration"],
        "top_5_contribution_pct": target["top_5_contribution_pct"],
        "avg_pnl_per_trade_delta": (
            aggregate["total_pnl_delta_sum"] / target["total_trade_count"]
            if target["total_trade_count"]
            else None
        ),
    }
    thresholds = ExperimentGateThresholds(
        min_adjusted_trades=MIN_ISSUER_RELEASE_LEGS_PER_WINDOW,
        min_adjusted_windows=len(WINDOWS),
        min_ev_improved_windows=0,
        max_ev_regressed_windows=len(WINDOWS),
        min_aggregate_ev_delta=COMPARATOR["expected_value_score_delta_sum"],
        min_aggregate_pnl_delta=COMPARATOR["total_pnl_delta_sum"],
        max_drawdown_worse=MAX_DRAWDOWN_WORSE,
        max_single_ticker_positive_share=MAX_SINGLE_POSITIVE_SHARE,
        max_top_5_contribution_pct=MAX_TOP5_POSITIVE_SHARE,
        max_hhi_concentration=1.0,
        require_tail_concentration_evidence=False,
        require_tail_concentration_not_worse=False,
    )
    canonical = evaluate_gate4(
        gate_metrics, thresholds=thresholds, check_materiality=False
    )
    strict = evaluate_gate4(
        gate_metrics, thresholds=thresholds, check_materiality=True
    )
    failures = list(canonical["hard_failures"])
    if not gate2_passed:
        failures.append("gate2_hash_or_signal_contract_failed")
    if not gate3_passed:
        failures.append("gate3_window_survival_below_5pct")
    for label, density in density_by_window.items():
        for check, passed in density["passes"].items():
            if not passed:
                failures.append(f"density_failed:{label}:{check}")
    old_thin = windows["old_thin"]["delta"]
    if old_thin["expected_value_score"] < 0:
        failures.append("old_thin_ev_negative")
    if old_thin["total_pnl"] < 0:
        failures.append("old_thin_pnl_negative")
    if aggregate["expected_value_score_delta_sum"] <= COMPARATOR[
        "expected_value_score_delta_sum"
    ]:
        failures.append("accepted_candidate_pool_ev_comparator_not_beaten")
    if aggregate["total_pnl_delta_sum"] <= COMPARATOR["total_pnl_delta_sum"]:
        failures.append("accepted_candidate_pool_pnl_comparator_not_beaten")
    if not _safe_le(
        target["single_ticker_positive_share"], MAX_SINGLE_POSITIVE_SHARE
    ):
        failures.append("single_ticker_positive_contribution_above_50pct")
    if not _safe_le(
        target["top_5_contribution_pct"], MAX_TOP5_POSITIVE_SHARE
    ):
        failures.append("top5_positive_contribution_above_60pct")
    failures = list(dict.fromkeys(failures))
    gate4 = {
        "passed": not failures,
        "status": "passed" if not failures else "blocked",
        "hard_failures": failures,
        "canonical": canonical,
        "strict_materiality": strict,
        "metrics": gate_metrics,
        "accepted_comparator": COMPARATOR,
    }

    panel, dsr_report = _build_dsr_evidence(windows, source, auxiliary)
    gate5_report = dict(dsr_report.get("gate5_dsr_report") or {})
    max_concurrent = max(
        (len(row["by_release"]) and max(row["by_release"].values()))
        for row in density_by_window.values()
    )
    envelope = ExecutionEnvelope(
        base_notional=RELEASE_BUDGET_USD,
        max_capital_pct=0.16,
        min_dollar_volume=None,
        slippage_bps=17.5,
        max_displacement=0,
        max_concurrent=max_concurrent,
        order_semantics="next_open_then_tenth_session_close",
        kill_switch_drawdown_pct=0.08,
        sleeve_drawdown_stop_pct=0.05,
        notes=(
            "Default-off official monthly release basket; fixed $16k total "
            "equally divided across all exact-mapped eligible issuers, 35bps "
            "round trip, no core slot displacement. Liquidity floor remains "
            "unset, so this evidence is not live-ready."
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
    decision = (
        "accepted_paper_pending_forward_fda_orange_book_newa_release_basket"
        if gate4["passed"]
        else "rejected_fda_orange_book_newa_release_basket"
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": manifest_audit["latest_official_publication_utc"],
        "lane": "alpha_search",
        "status": (
            "accepted_paper_pending_forward" if gate4["passed"] else "rejected"
        ),
        "decision": decision,
        "accepted_alpha": gate4["passed"],
        "hypothesis": (
            "When an official FDA Orange Book monthly PDF first publishes "
            "fresh NEWA additions, a fixed-capital equal-weight basket of every "
            "exact-mapped listed issuer drifts positively from the next open "
            "through the tenth-session close."
        ),
        "rule_version": RULE_VERSION,
        "locked_policy": {
            "row_filter": "addition marker >A> and terminal reason NEWA",
            "approval_freshness_calendar_days": [0, 45],
            "signal_clock": "official PDF HTTP Last-Modified UTC",
            "mapping": "exact event-date listed economic parent; no fuzzy",
            "dedupe": "one ticker x PDF-month decision",
            "eligible_issuers": "all; no top-N",
            "release_budget_usd": RELEASE_BUDGET_USD,
            "allocation": "equal weight across eligible issuer-release legs",
            "entry": "next regular-session open",
            "hold_sessions": HOLD_SESSIONS,
            "exit": "tenth-session close",
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "threshold_or_subtype_sweeps": 0,
        },
        "source": source,
        "windows": windows,
        "gate1": {
            "passed": True,
            "baseline": _repo_rel(BASELINE_SUMMARY_PATH),
            "baseline_sha256": _file_sha(BASELINE_SUMMARY_PATH),
            "auxiliary_ohlcv": {
                "path": _repo_rel(AUXILIARY_OHLCV_PATH),
                "rowset_sha256": auxiliary["rowset_sha256"],
                "source_at_freeze": auxiliary["source_at_freeze"],
                "missing_tickers": auxiliary["missing_tickers"],
            },
            "bar_identity": bar_identity,
        },
        "gate2": {
            "passed": gate2_passed,
            "source_hashes_passed": gate2_source_hashes_passed,
            "signal_sentinel_fields_passed": gate2_sentinels_passed,
            "sentinel_fields": ["entry_date", "target_price"],
            "source_fields": [
                "month",
                "media_id",
                "official_http_last_modified_utc",
                "signal_timestamp",
                "signal_date",
                "approval_date",
                "approval_age_days",
                "ticker",
                "application_number",
                "source_pdf_sha256",
                "source_line_sha256s",
            ],
        },
        "gate3": {
            "passed": gate3_passed,
            "unit": "eligible issuer-release leg",
            "signals_generated": generated_total,
            "signals_survived": survived_total,
            "survival_rate": round(aggregate_survival_rate, 6),
            "minimum_per_window": MIN_SURVIVAL_RATE,
        },
        "aggregate": aggregate,
        "target_summary": target,
        "accepted_comparator": COMPARATOR,
        "gate4": gate4,
        "deflated_sharpe": {
            "panel_path": _repo_rel(DSR_PANEL_PATH),
            "report_path": _repo_rel(DSR_REPORT_PATH),
            "selection_scope": panel["trials"][0]["selection_scope"],
            "expected_attempt_count": panel["expected_attempt_count"],
            "selection_pool_complete": panel["selection_pool_complete"],
            "panel_sha256": _canonical_sha(panel),
            "engine_panel_hash": gate5_report.get("panel_hash"),
            "report_sha256": _canonical_sha(dsr_report),
            "status": gate5_report.get("status"),
            "probability": gate5_report.get("dsr_probability"),
            "reason_codes": list(gate5_report.get("reason_codes") or []),
            "gate4_independent": True,
        },
        "full_stack": {
            "verdict": verdict,
            "shared_policy_parity_complete": True,
            "daily_candidate_parity_complete": gate4["passed"],
            "daily_observer_only": True,
            "daily_parity_reason": (
                "Historical replay and the default-off snapshot callable consume "
                "the same hash-verified source loader and fixed shared helper; "
                + (
                    "daily run wiring may be retained because Gate 4 passed."
                    if gate4["passed"]
                    else "production daily run wiring is not retained after Gate 4 rejection."
                )
            ),
            "execution_envelope": envelope.to_dict(),
            "live_readiness": live,
        },
        "prediction": PREDICTION,
        "production_impact": {
            "trade_enabled": False,
            "live_orders_changed": False,
            "core_ranking_changed": False,
            "core_sizing_changed": False,
            "core_exits_changed": False,
            "daily_wiring_retained": gate4["passed"],
            "run_adapter_changed": gate4["passed"],
            "replay_only": not gate4["passed"],
            "shared_helper": "quant/orange_book_newa_release_basket_paper_sleeve.py",
        },
        "post_run_reflection": {
            "why_result_happened": (
                "; ".join(failures)
                if failures
                else "The single locked monthly-release policy cleared every preregistered Gate-4 bar."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune freshness, exact aliases, NEWA subtypes, top-N, "
                "release budget, hold, costs, or fixed windows."
            ),
            "new_evidence_required": (
                "A genuinely new official product-commercialization source or "
                "at least 30 closed forward replacement-value issuer-release legs."
            ),
        },
        "reproduction_command": (
            f".\\.venv\\Scripts\\python.exe -B quant\\experiments\\{Path(__file__).name}"
        ),
    }


def _write_close_artifacts(payload: dict[str, Any]) -> None:
    windows = payload["windows"]
    before = {
        "schema": "fda_orange_book_newa_gate4_aggregate_before_v1",
        "expected_value_score": payload["aggregate"][
            "before_expected_value_score_sum"
        ],
        "total_pnl": payload["aggregate"]["before_total_pnl_sum"],
        "max_drawdown_pct": max(
            row["before"]["max_drawdown_pct"] for row in windows.values()
        ),
        "total_trades": sum(
            row["before"]["total_trades"] for row in windows.values()
        ),
        "survival_rate": min(
            row["before"]["survival_rate"] for row in windows.values()
        ),
        "benchmarks": {
            "strategy_total_return_pct": round(
                payload["aggregate"]["before_total_pnl_sum"]
                / INITIAL_EQUITY_USD,
                4,
            )
        },
    }
    after = {
        "schema": "fda_orange_book_newa_gate4_aggregate_after_v1",
        "expected_value_score": payload["aggregate"][
            "after_expected_value_score_sum"
        ],
        "total_pnl": payload["aggregate"]["after_total_pnl_sum"],
        "max_drawdown_pct": max(
            row["after"]["max_drawdown_pct"] for row in windows.values()
        ),
        "total_trades": sum(
            row["after"]["total_trades"] for row in windows.values()
        ),
        "survival_rate": payload["gate3"]["survival_rate"],
        "benchmarks": {
            "strategy_total_return_pct": round(
                payload["aggregate"]["after_total_pnl_sum"]
                / INITIAL_EQUITY_USD,
                4,
            )
        },
    }
    standalone = {
        "schema": "fda_orange_book_newa_standalone_daily_mtm_v1",
        "expected_value_score": payload["aggregate"][
            "standalone_expected_value_score_sum"
        ],
        "total_pnl": payload["aggregate"]["standalone_total_pnl_sum"],
        "total_trades": payload["target_summary"]["total_trade_count"],
        "by_window": {
            label: row["standalone"] for label, row in windows.items()
        },
    }
    _atomic_write_json(BEFORE_PATH, before)
    _atomic_write_json(AFTER_PATH, after)
    _atomic_write_json(STANDALONE_PATH, standalone)


def _pct(value: Any) -> str:
    return "n/a" if value is None else f"{float(value):.2%}"


def _write_artifact(payload: dict[str, Any]) -> None:
    dsr = payload["deflated_sharpe"]
    lines = [
        f"# {EXPERIMENT_ID} FDA Orange Book fresh-NEWA release basket",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Full-stack verdict: `{payload['full_stack']['verdict']['verdict']}`",
        f"- Official PDFs / decisions: `{payload['source']['manifest_audit']['document_count']}` / `{payload['source']['decision_audit']['decision_count']}`",
        f"- Eligible issuer-release legs / settled trades: `{payload['target_summary']['eligible_issuer_release_leg_count']}` / `{payload['target_summary']['total_trade_count']}`",
        f"- Core+sleeve aggregate EV delta: `{payload['aggregate']['expected_value_score_delta_sum']}`",
        f"- Core+sleeve aggregate PnL delta: `${payload['aggregate']['total_pnl_delta_sum']:,.2f}`",
        f"- Standalone aggregate EV / PnL: `{payload['aggregate']['standalone_expected_value_score_sum']}` / `${payload['aggregate']['standalone_total_pnl_sum']:,.2f}`",
        f"- Gate 2 source hashes + sentinels: `{'passed' if payload['gate2']['passed'] else 'failed'}`",
        f"- Gate 3 survival: `{payload['gate3']['survival_rate']:.2%}`",
        f"- Single / top-5 positive contribution: `{_pct(payload['target_summary']['single_ticker_positive_share'])}` / `{_pct(payload['target_summary']['top_5_contribution_pct'])}`",
        f"- Gate 4 failures: `{', '.join(payload['gate4']['hard_failures']) or 'none'}`",
        f"- DSR: `{dsr['status']}` / `{dsr['probability']}` (Gate 5 only; reasons: `{', '.join(dsr['reason_codes']) or 'none'}`)",
        "",
        "## Three-window daily-MTM result",
        "",
        "| Window | Eligible legs | Tickers | Top1 | Generated | Survived | Trades | Standalone EV | Standalone PnL | Core EV delta | Core PnL delta | DD delta |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        *[
            f"| {label} | {row['density']['issuer_release_leg_count']} | {row['density']['ticker_count']} | {row['density']['top1_leg_share']:.2%} | {row['signals_generated']} | {row['signals_survived']} | {len(row['target_trades'])} | {row['standalone']['expected_value_score']:.4f} | ${row['standalone']['total_pnl']:,.2f} | {row['delta']['expected_value_score']:.4f} | ${row['delta']['total_pnl']:,.2f} | {row['delta']['max_drawdown_pct']:.4f} |"
            for label, row in payload["windows"].items()
        ],
        "",
        "## Point-in-time and integrity contract",
        "",
        f"- Official landing page: {LANDING_URL}",
        "- Every consumed PDF is frozen byte-for-byte and verified against the source manifest's byte count and SHA-256 before evaluation.",
        "- The official HTTP `Last-Modified` UTC timestamp is the signal clock; approval date is freshness metadata only and must be 0-45 calendar days earlier.",
        "- Only `>A>` rows with terminal reason `NEWA` are eligible. Mapping is exact and event-date-aware; fuzzy holder matching is forbidden.",
        "- Mapping audit repair: Fresenius Kabi USA is not economically represented by FMS (Fresenius Medical Care), so all former FMS legs were removed before evaluation; the corrected PDF parser and preflight agree exactly.",
        "- One ticker x PDF-month decision is retained, every eligible issuer is used, and the fixed $16,000 release budget is divided equally. There is no top-N or threshold sweep.",
        f"- Source manifest SHA-256: `{payload['source']['manifest_audit']['sha256']}`",
        f"- Canonical decisions SHA-256: `{payload['source']['decision_audit']['decisions_sha256']}`",
        "",
        "Historical replay and the default-off snapshot callable share one policy helper. "
        + (
            "Gate 4 passed, so production daily wiring may be retained. "
            if payload["gate4"]["passed"]
            else "Gate 4 rejected the policy, so production daily wiring is not retained. "
        )
        + "The complete date-aligned off/on panel is persisted for Deflated-Sharpe evidence, but DSR affects Gate 5 only and never changes this Gate-4 decision.",
    ]
    _atomic_write_text(ARTIFACT_PATH, "\n".join(lines) + "\n")


def main() -> None:
    payload = build_payload()
    _atomic_write_json(RESULT_PATH, payload)
    _write_close_artifacts(payload)
    _write_artifact(payload)
    print(
        json.dumps(
            {
                "decision": payload["decision"],
                "source": {
                    "document_count": payload["source"]["manifest_audit"][
                        "document_count"
                    ],
                    "decision_count": payload["source"]["decision_audit"][
                        "decision_count"
                    ],
                    "manifest_sha256": payload["source"]["manifest_audit"][
                        "sha256"
                    ],
                },
                "density": {
                    label: row["density"] for label, row in payload["windows"].items()
                },
                "target_summary": payload["target_summary"],
                "aggregate": payload["aggregate"],
                "gate4_failures": payload["gate4"]["hard_failures"],
                "deflated_sharpe": payload["deflated_sharpe"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
