"""exp-20260713-010: FDA Device Class-I Enforcement Report full stack.

The fixed candidate policy uses only the official ``report_date`` availability
field, an exact recalling-firm map, Class-I eligibility, event-level dedupe,
the first trading session strictly after the report, green and SPY-relative
price confirmation, top one per day, a ten-session ticker cooldown, next-open
entry, tenth-session close, $4k paper notional, and 35 bps round-trip cost.

Official API pages and normalized events are frozen as canonical JSON and
hashed because openFDA can revise historical rows in later weekly releases.
The target sleeve is daily marked to market against the active July-12
post-MTM Gate-1 reference.  A complete two-config, date-aligned return panel
is persisted for Deflated-Sharpe Gate-5 evidence; DSR never changes Gate 4.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (REPO_ROOT, QUANT_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from deflated_sharpe import build_report as build_dsr_report  # noqa: E402
from fda_device_class1_enforcement_paper_sleeve import (  # noqa: E402
    BASE_NOTIONAL_USD,
    FIRM_TO_TICKER,
    ROUND_TRIP_COST_PCT,
    RULE_VERSION,
    load_fda_device_class1_enforcement_archive,
    refresh_fda_device_class1_enforcement_archive,
    replay_fda_device_class1_enforcement_paper_trades,
    save_fda_device_class1_enforcement_archive,
)
from quant.evaluator_gates import ExperimentGateThresholds  # noqa: E402
from quant.full_stack_candidate_pool import (  # noqa: E402
    ExecutionEnvelope,
    evaluate_gate4,
    evaluate_live_readiness,
    full_stack_verdict,
)


EXPERIMENT_ID = "exp-20260713-010"
BASELINE_SUMMARY = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_post_mtm_20260712.json"
)
WAREHOUSE = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"
SOURCE_DIR = REPO_ROOT / "data" / "non_ohlcv" / "fda_device_class1_enforcement"
RAW_DIR = SOURCE_DIR / "raw"
RAW_MANIFEST_PATH = RAW_DIR / "openfda_fetch_manifest.json"
ARCHIVE_PATH = SOURCE_DIR / "events.json"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
AUX_OHLCV_PATH = OUT_DIR / "auxiliary_ohlcv.json"
RESULT_PATH = OUT_DIR / "fda_device_class1_enforcement_replay.json"
BEFORE_PATH = OUT_DIR / "before.json"
AFTER_PATH = OUT_DIR / "after.json"
DSR_PANEL_PATH = OUT_DIR / "deflated_sharpe_panel.json"
DSR_REPORT_PATH = OUT_DIR / "deflated_sharpe_report.json"
ARTIFACT_PATH = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_fda_device_class1_enforcement.md"
)

OFFICIAL_API_URL = "https://open.fda.gov/apis/device/enforcement/"
OFFICIAL_FIELDS_URL = (
    "https://open.fda.gov/apis/device/enforcement/searchable-fields/"
)
EXPECTED_SOURCE_EVENTS = 86
EXPECTED_SOURCE_TICKERS = 19
MIN_TARGET_TRADES = 20
MIN_TARGET_TICKERS = 3
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
COMPARATOR = {
    "experiment_id": "exp-20260611-007",
    "expected_value_score_delta_sum": 0.5286,
    "total_pnl_delta_sum": 10432.91,
}

WINDOWS = OrderedDict(
    (
        ("late_strong", ("2025-10-23", "2026-04-21")),
        ("mid_weak", ("2025-04-23", "2025-10-22")),
        ("old_thin", ("2024-10-02", "2025-04-22")),
    )
)

PREDICTION = {
    "success_probability": 0.25,
    "expected_ev_delta": 0.25,
    "expected_pnl_delta": 4500.0,
    "main_failure_modes": [
        "recall_report_delay",
        "medical_device_ticker_concentration",
        "accepted_comparator_not_beaten",
        "parent_mapping_survivorship",
    ],
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _canonical_sha(payload: Any) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _return_series_sha(rows: list[dict[str, Any]]) -> str:
    return _canonical_sha(
        {"schema": "dated_periodic_return_series_v1", "rows": rows}
    )


def _verify_frozen_source() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    archive = _read_json(ARCHIVE_PATH)
    events = load_fda_device_class1_enforcement_archive(ARCHIVE_PATH)
    actual_events_sha = _canonical_sha(events)
    if archive.get("events_sha256") != actual_events_sha:
        raise RuntimeError("FDA normalized event archive failed SHA256 verification")
    if not RAW_MANIFEST_PATH.exists():
        raise RuntimeError("FDA raw API fetch manifest is missing")

    manifest = _read_json(RAW_MANIFEST_PATH)
    pages = manifest.get("pages") or []
    if not pages:
        raise RuntimeError("FDA raw API fetch manifest contains no pages")
    verified_pages: list[dict[str, Any]] = []
    for index, row in enumerate(pages):
        rel = row.get("path") or row.get("file") or row.get("filename")
        expected_sha = row.get("sha256") or row.get("payload_sha256")
        if not rel or not expected_sha:
            raise RuntimeError(f"FDA raw page manifest row {index} is incomplete")
        path = Path(rel)
        if not path.is_absolute():
            path = RAW_DIR / path
        if not path.exists():
            raise RuntimeError(f"FDA raw API page is missing: {path}")
        actual_sha = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_sha != expected_sha:
            raise RuntimeError(f"FDA raw API page failed SHA256 verification: {path}")
        verified_pages.append(
            {
                "path": str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
                "sha256": actual_sha,
                "record_count": row.get("record_count"),
            }
        )

    if len(events) != EXPECTED_SOURCE_EVENTS:
        raise RuntimeError(
            f"FDA frozen event count drifted: {len(events)} != {EXPECTED_SOURCE_EVENTS}"
        )
    tickers = sorted({str(row["ticker"]) for row in events})
    if len(tickers) != EXPECTED_SOURCE_TICKERS:
        raise RuntimeError(
            "FDA frozen ticker count drifted: "
            f"{len(tickers)} != {EXPECTED_SOURCE_TICKERS}"
        )
    for row in events:
        if row.get("classification") != "Class I":
            raise RuntimeError("non-Class-I row reached the FDA frozen archive")
        if not row.get("report_date"):
            raise RuntimeError("FDA event date contract is not report_date-only")
        if not row.get("source_record_sha256"):
            raise RuntimeError("FDA event is missing raw source-record provenance")

    return events, {
        "path": str(ARCHIVE_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
        "archive_sha256": hashlib.sha256(ARCHIVE_PATH.read_bytes()).hexdigest(),
        "events_sha256": actual_events_sha,
        "generated_at": archive.get("generated_at"),
        "retrieved_at": manifest.get("retrieved_at"),
        "query_urls": [row.get("url") for row in pages],
        "raw_manifest_path": str(RAW_MANIFEST_PATH.relative_to(REPO_ROOT)).replace(
            "\\", "/"
        ),
        "raw_manifest_sha256": hashlib.sha256(
            RAW_MANIFEST_PATH.read_bytes()
        ).hexdigest(),
        "raw_pages": verified_pages,
        "raw_pages_verified": True,
        "event_count": len(events),
        "ticker_count": len(tickers),
        "tickers": tickers,
        "official_api_url": OFFICIAL_API_URL,
        "official_fields_url": OFFICIAL_FIELDS_URL,
        "availability_field": "report_date",
        "availability_definition": "date FDA issued the enforcement report",
        "update_cadence": "weekly",
        "excluded_dates": ["recall_initiation_date", "classification_date"],
        "historical_revision_boundary": (
            "openFDA historical records can change; the exact canonical API "
            "pages and normalized records above are the audit boundary"
        ),
    }


def materialize_source(start: str, end: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not ARCHIVE_PATH.exists() or not RAW_MANIFEST_PATH.exists():
        refresh_fda_device_class1_enforcement_archive(
            ARCHIVE_PATH,
            start=start,
            end=end,
            timeout=30.0,
            archive_payload_dir=RAW_DIR,
        )
    else:
        archive = _read_json(ARCHIVE_PATH)
        if not archive.get("raw_payload_manifest_sha256"):
            # The first freeze happened while the helper's raw-binding field
            # was being hardened. Upgrade that archive once from its already
            # frozen normalized events + raw manifest; never refetch history.
            events = load_fda_device_class1_enforcement_archive(ARCHIVE_PATH)
            save_fda_device_class1_enforcement_archive(
                ARCHIVE_PATH,
                events,
                archive_payload_dir=RAW_DIR,
            )
    return _verify_frozen_source()


def load_ohlcv(start: str, end: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if AUX_OHLCV_PATH.exists():
        payload = _read_json(AUX_OHLCV_PATH)
        output = payload.get("ohlcv") or {}
        actual = _canonical_sha(output)
        if payload.get("start") != start or payload.get("end") != end:
            raise RuntimeError("frozen auxiliary OHLCV range drift")
        if payload.get("rowset_sha256") != actual:
            raise RuntimeError("frozen auxiliary OHLCV failed hash verification")
        return output, {
            "path": str(AUX_OHLCV_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
            "rowset_sha256": actual,
            "source_at_freeze": payload.get("source_at_freeze"),
        }

    tickers = sorted(set(FIRM_TO_TICKER.values()) | {"SPY"})
    placeholders = ",".join("?" for _ in tickers)
    query = f"""
        SELECT ticker, date, open, high, low, close
        FROM ohlcv
        WHERE ticker IN ({placeholders}) AND date >= ? AND date <= ?
        ORDER BY ticker, date
    """
    output: dict[str, list[dict[str, Any]]] = {ticker: [] for ticker in tickers}
    with sqlite3.connect(str(WAREHOUSE)) as connection:
        for ticker, day, open_, high, low, close in connection.execute(
            query, [*tickers, start, end]
        ):
            output[str(ticker)].append(
                {
                    "date": str(day),
                    "open": open_,
                    "high": high,
                    "low": low,
                    "close": close,
                }
            )
    missing = [ticker for ticker, rows in output.items() if not rows]
    if missing:
        raise RuntimeError(f"required FDA auxiliary OHLCV is missing: {missing}")
    rowset_sha = _canonical_sha(output)
    _write_json(
        AUX_OHLCV_PATH,
        {
            "schema": "fda_device_class1_auxiliary_ohlcv_v1",
            "source_at_freeze": str(WAREHOUSE.relative_to(REPO_ROOT)).replace(
                "\\", "/"
            ),
            "start": start,
            "end": end,
            "rowset_sha256": rowset_sha,
            "ohlcv": output,
        },
    )
    return output, {
        "path": str(AUX_OHLCV_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
        "rowset_sha256": rowset_sha,
        "source_at_freeze": str(WAREHOUSE.relative_to(REPO_ROOT)).replace(
            "\\", "/"
        ),
    }


def _baseline_window_map(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row["label"]): row for row in summary["windows"]}


def _window_ohlcv(
    broad: dict[str, Any],
    baseline_window: dict[str, Any],
    auxiliary_source: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    snapshot_path = REPO_ROOT / baseline_window["source"]
    snapshot = (_read_json(snapshot_path).get("ohlcv") or {})
    output = {ticker: list(rows) for ticker, rows in broad.items()}
    exact_tickers: list[str] = []
    for ticker in sorted(set(FIRM_TO_TICKER.values()) | {"SPY"}):
        if snapshot.get(ticker):
            output[ticker] = list(snapshot[ticker])
            exact_tickers.append(ticker)
    missing = [ticker for ticker, rows in output.items() if not rows]
    if missing:
        raise RuntimeError(f"required FDA window OHLCV is missing: {missing}")
    return output, {
        "gate1_snapshot": str(snapshot_path.relative_to(REPO_ROOT)).replace(
            "\\", "/"
        ),
        "exact_snapshot_tickers": exact_tickers,
        "frozen_auxiliary_fill_tickers": sorted(set(output) - set(exact_tickers)),
        "frozen_auxiliary_source": auxiliary_source,
    }


def _baseline_return_series(window: dict[str, Any]) -> list[dict[str, Any]]:
    artifact = _read_json(REPO_ROOT / window["path"])
    return artifact["sharpe_inference"]["return_series"]


def _baseline_curve(window: dict[str, Any]) -> list[tuple[str, float]]:
    equity = 100_000.0
    curve: list[tuple[str, float]] = []
    for row in _baseline_return_series(window):
        equity *= 1.0 + float(row["return"])
        curve.append((str(row["date"]), equity))
    expected = 100_000.0 + float(window["total_pnl"])
    if not curve or abs(curve[-1][1] - expected) > 0.02:
        raise RuntimeError(f"baseline return reconstruction drift: {window['label']}")
    return curve


def _bar_index(ohlcv: dict[str, Any]) -> dict[str, dict[str, float]]:
    return {
        ticker: {
            str(row.get("date") or row.get("Date")): float(
                row["close"] if "close" in row else row["Close"]
            )
            for row in rows
            if (row.get("close") if "close" in row else row.get("Close"))
            not in (None, 0)
        }
        for ticker, rows in ohlcv.items()
    }


def _target_mark(
    trades: list[dict[str, Any]],
    close_by_ticker: dict[str, dict[str, float]],
    day: str,
) -> float:
    mark = 0.0
    for trade in trades:
        if day < trade["entry_date"]:
            continue
        if day >= trade["exit_date"]:
            mark += float(trade["pnl"])
            continue
        close = close_by_ticker.get(trade["ticker"], {}).get(day)
        if close is None:
            raise RuntimeError(f"missing FDA MTM close for {trade['ticker']} on {day}")
        gross = close / float(trade["entry_price"]) - 1.0
        mark += float(trade["paper_notional_usd"]) * (
            gross - ROUND_TRIP_COST_PCT / 2.0
        )
    return mark


def _curve_metrics(
    curve: list[tuple[str, float]], *, trade_count: int
) -> dict[str, Any]:
    previous = 100_000.0
    returns: list[dict[str, Any]] = []
    for day, equity in curve:
        returns.append({"date": day, "return": equity / previous - 1.0})
        previous = equity
    samples = [float(row["return"]) for row in returns]
    mean = sum(samples) / len(samples)
    variance = sum((value - mean) ** 2 for value in samples) / (len(samples) - 1)
    sharpe_full = mean / math.sqrt(variance) * math.sqrt(252) if variance > 0 else None
    peak = 100_000.0
    drawdown = 0.0
    for _, equity in curve:
        peak = max(peak, equity)
        drawdown = max(drawdown, (peak - equity) / peak)
    total_pnl = curve[-1][1] - 100_000.0
    total_return = round(total_pnl / 100_000.0, 4)
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


def combine_window(
    baseline: dict[str, Any],
    trades: list[dict[str, Any]],
    ohlcv: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[tuple[str, float]]]:
    base_curve = _baseline_curve(baseline)
    close_index = _bar_index(ohlcv)
    combined = [
        (day, equity + _target_mark(trades, close_index, day))
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
        "return_series": _baseline_return_series(baseline),
    }
    before["return_series_sha256"] = _return_series_sha(before["return_series"])
    after = _curve_metrics(
        combined, trade_count=int(baseline["trade_count"]) + len(trades)
    )
    return before, after, combined


def _target_summary(by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    pnl: Counter[str] = Counter()
    counts: Counter[str] = Counter()
    for trades in by_window.values():
        for trade in trades:
            pnl[trade["ticker"]] += float(trade["pnl"])
            counts[trade["ticker"]] += 1
    positive = {ticker: value for ticker, value in pnl.items() if value > 0}
    positive_total = sum(positive.values())
    shares = (
        sorted((value / positive_total for value in positive.values()), reverse=True)
        if positive_total
        else []
    )
    return {
        "total_trade_count": sum(counts.values()),
        "ticker_count": len(counts),
        "tickers": sorted(counts),
        "window_count": sum(bool(rows) for rows in by_window.values()),
        "by_window_count": {label: len(rows) for label, rows in by_window.items()},
        "by_ticker_count": dict(sorted(counts.items())),
        "by_ticker_pnl": {
            ticker: round(value, 2) for ticker, value in sorted(pnl.items())
        },
        "total_pnl": round(sum(pnl.values()), 2),
        "single_ticker_positive_share": round(shares[0], 6) if shares else None,
        "hhi_concentration": (
            round(sum(share * share for share in shares), 6) if shares else None
        ),
        "top_5_contribution_pct": round(sum(shares[:5]), 6) if shares else None,
    }


def _concatenate_return_series(
    rows: dict[str, Any], side: str
) -> list[dict[str, Any]]:
    combined: list[dict[str, Any]] = []
    for label in sorted(WINDOWS, key=lambda value: WINDOWS[value][0]):
        combined.extend(rows[label][side]["return_series"])
    dates = [str(row["date"]) for row in combined]
    if dates != sorted(dates) or len(dates) != len(set(dates)):
        raise RuntimeError(f"{side} DSR return dates are not strictly aligned")
    return combined


def _build_dsr_evidence(
    rows: dict[str, Any], source: dict[str, Any], auxiliary: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    before = _concatenate_return_series(rows, "before")
    after = _concatenate_return_series(rows, "after")
    if [row["date"] for row in before] != [row["date"] for row in after]:
        raise RuntimeError("before/after DSR date vectors are not exactly aligned")

    context = {
        "selection_scope": f"{EXPERIMENT_ID}-fda-class1-off-vs-on",
        "window": {
            "segments": [
                {"label": label, "start": start, "end": end}
                for label, (start, end) in sorted(
                    WINDOWS.items(), key=lambda item: item[1][0]
                )
            ]
        },
        "frequency": "daily",
        "return_basis": "strategy_equity_return_post_cost_daily_mtm",
        "risk_free_assumption": "zero",
        "protocol": {
            "id": "post_mtm_gate1_plus_default_off_fixed_notional_v1",
            "baseline": str(BASELINE_SUMMARY.relative_to(REPO_ROOT)).replace(
                "\\", "/"
            ),
            "rule_version": RULE_VERSION,
        },
        "data": {
            "baseline_summary_sha256": hashlib.sha256(
                BASELINE_SUMMARY.read_bytes()
            ).hexdigest(),
            "fda_events_sha256": source["events_sha256"],
            "auxiliary_ohlcv_sha256": auxiliary["rowset_sha256"],
        },
        "cost": {
            "core": "pinned_post_mtm_gate1_cost_model",
            "fda_round_trip_cost_pct": ROUND_TRIP_COST_PCT,
        },
    }
    configs = (
        (
            "core_fda_class1_off",
            {"core": "active_post_mtm", "fda_device_class1_sleeve": False},
            before,
            f"{RESULT_PATH.relative_to(REPO_ROOT).as_posix()}#windows.*.before.return_series",
        ),
        (
            "core_fda_class1_on",
            {
                "core": "active_post_mtm",
                "fda_device_class1_sleeve": True,
                "locked_policy": RULE_VERSION,
            },
            after,
            f"{RESULT_PATH.relative_to(REPO_ROOT).as_posix()}#windows.*.after.return_series",
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
        "selected_config_id": "core_fda_class1_on",
        "expected_attempt_count": 2,
        "selection_pool_complete": True,
        "expected_return_dates": [row["date"] for row in before],
        "periods_per_year": 252,
        "trials": trials,
    }
    report = build_dsr_report(panel)
    # A complete two-config panel can still be statistically not computable
    # (for example when near-perfect correlation makes the expected-maximum
    # approximation invalid).  Preserve that honest result and fail closed in
    # Gate 5; it must never suppress or modify the independently defined Gate 4.
    _write_json(DSR_PANEL_PATH, panel)
    _write_json(DSR_REPORT_PATH, report)
    return panel, report


def build_payload() -> dict[str, Any]:
    baseline_summary = _read_json(BASELINE_SUMMARY)
    baseline_windows = _baseline_window_map(baseline_summary)
    broad, auxiliary_source = load_ohlcv("2024-09-01", "2026-05-15")
    ohlcv_by_window: dict[str, dict[str, Any]] = {}
    auxiliary_identity: dict[str, Any] = {}
    for label in WINDOWS:
        ohlcv_by_window[label], auxiliary_identity[label] = _window_ohlcv(
            broad, baseline_windows[label], auxiliary_source
        )
    events, source = materialize_source("2024-10-02", "2026-04-21")

    rows: dict[str, Any] = {}
    trades_by_window: dict[str, list[dict[str, Any]]] = {}
    generated_total = 0
    survived_total = 0
    for label, (start, end) in WINDOWS.items():
        ohlcv = ohlcv_by_window[label]
        replay = replay_fda_device_class1_enforcement_paper_trades(
            events=events,
            ohlcv_by_ticker=ohlcv,
            start=start,
            end=end,
        )
        trades = replay["trades"]
        before, after, combined_curve = combine_window(
            baseline_windows[label], trades, ohlcv
        )
        generated = sum(start <= row["report_date"] <= end for row in events)
        survived = len(replay["selected_candidates"])
        generated_total += generated
        survived_total += survived
        trades_by_window[label] = trades
        rows[label] = {
            "start": start,
            "end": end,
            "before": before,
            "after": after,
            "delta": {
                "expected_value_score": round(
                    after["expected_value_score"]
                    - before["expected_value_score"],
                    4,
                ),
                "total_pnl": round(after["total_pnl"] - before["total_pnl"], 2),
                "max_drawdown_pct": round(
                    after["max_drawdown_pct"] - before["max_drawdown_pct"], 4
                ),
            },
            "signals_generated": generated,
            "signals_survived": survived,
            "survival_rate": round(survived / generated, 6) if generated else 0.0,
            "target_trades": trades,
            "unsettled": replay["unsettled"],
            "reject_totals": replay["reject_totals"],
            "combined_curve_sha256": _canonical_sha(combined_curve),
        }

    target = _target_summary(trades_by_window)
    aggregate = {
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
    gate_metrics = {
        "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
        "windows_ev_improved": aggregate["windows_ev_improved"],
        "windows_ev_regressed": aggregate["windows_ev_regressed"],
        "adjusted_trade_count": target["total_trade_count"],
        "adjusted_windows": [
            label for label, trades in trades_by_window.items() if trades
        ],
        "adjusted_window_count": target["window_count"],
        "max_drawdown_worse_max": aggregate["max_drawdown_worse_max"],
        "single_ticker_positive_share": target["single_ticker_positive_share"],
        "hhi_concentration": target["hhi_concentration"],
        "top_5_contribution_pct": target["top_5_contribution_pct"],
        "avg_pnl_per_trade_delta": (
            aggregate["total_pnl_delta_sum"] / target["total_trade_count"]
            if target["total_trade_count"]
            else None
        ),
    }
    thresholds = ExperimentGateThresholds(
        min_adjusted_trades=MIN_TARGET_TRADES,
        min_adjusted_windows=MIN_TARGET_WINDOWS,
        min_ev_improved_windows=MIN_TARGET_WINDOWS,
        max_ev_regressed_windows=0,
        max_drawdown_worse=MAX_DRAWDOWN_WORSE,
        require_tail_concentration_not_worse=False,
    )
    strict = evaluate_gate4(gate_metrics, thresholds=thresholds, check_materiality=True)
    canonical = evaluate_gate4(
        gate_metrics, thresholds=thresholds, check_materiality=False
    )
    failures = list(canonical["hard_failures"])
    if target["ticker_count"] < MIN_TARGET_TICKERS:
        failures.append("ticket_target_ticker_count_below_3")
    if aggregate["windows_pnl_regressed"] > 0:
        failures.append("window_pnl_regression")
    if (
        aggregate["expected_value_score_delta_sum"]
        <= COMPARATOR["expected_value_score_delta_sum"]
    ):
        failures.append("accepted_distribution_ev_comparator_not_beaten")
    if aggregate["total_pnl_delta_sum"] <= COMPARATOR["total_pnl_delta_sum"]:
        failures.append("accepted_distribution_pnl_comparator_not_beaten")
    gate2_passed = bool(target["total_trade_count"]) and all(
        trade.get("entry_date") and trade.get("target_price")
        for trades in trades_by_window.values()
        for trade in trades
    )
    gate3_rate = survived_total / generated_total if generated_total else 0.0
    if not gate2_passed:
        failures.append("gate2_signal_contract_failed")
    if generated_total <= 0 or gate3_rate < 0.05:
        failures.append("gate3_survival_below_5pct")
    gate4 = {
        "passed": not failures,
        "status": "passed" if not failures else "blocked",
        "hard_failures": list(dict.fromkeys(failures)),
        "canonical": canonical,
        "strict_materiality": strict,
        "metrics": gate_metrics,
    }

    panel, dsr_report = _build_dsr_evidence(rows, source, auxiliary_source)
    envelope = ExecutionEnvelope(
        base_notional=BASE_NOTIONAL_USD,
        max_capital_pct=0.44,
        min_dollar_volume=None,
        slippage_bps=17.5,
        max_displacement=0,
        max_concurrent=11,
        order_semantics="next_open_then_10_session_horizon_close",
        kill_switch_drawdown_pct=0.08,
        sleeve_drawdown_stop_pct=0.05,
        notes="Default-off top1/day; 35bps all-in round trip; no core displacement.",
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
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": source["generated_at"],
        "lane": "alpha_search",
        "status": "accepted_paper_pending_forward" if gate4["passed"] else "rejected",
        "decision": (
            "accepted_paper_pending_forward_fda_device_class1_enforcement"
            if gate4["passed"]
            else "rejected_fda_device_class1_enforcement_candidate_pool"
        ),
        "accepted_alpha": gate4["passed"],
        "hypothesis": (
            "After an FDA Device Class-I Enforcement Report, an issuer green "
            "and ahead of SPY on the first strictly later session continues "
            "from the next open through the tenth close."
        ),
        "rule_version": RULE_VERSION,
        "source": source,
        "windows": rows,
        "gate1": {
            "passed": True,
            "baseline": str(BASELINE_SUMMARY.relative_to(REPO_ROOT)).replace(
                "\\", "/"
            ),
            "auxiliary_bar_identity": auxiliary_identity,
        },
        "gate2": {
            "passed": gate2_passed,
            "sentinel_fields": ["entry_date", "target_price"],
            "source_fields": [
                "event_id",
                "ticker",
                "recalling_firm",
                "classification",
                "report_date",
                "source_record_sha256",
            ],
        },
        "gate3": {
            "passed": generated_total > 0 and gate3_rate >= 0.05,
            "signals_generated": generated_total,
            "signals_survived": survived_total,
            "survival_rate": round(gate3_rate, 6),
        },
        "aggregate": aggregate,
        "target_summary": target,
        "accepted_comparator": COMPARATOR,
        "gate4": gate4,
        "deflated_sharpe": {
            "panel_path": str(DSR_PANEL_PATH.relative_to(REPO_ROOT)).replace(
                "\\", "/"
            ),
            "report_path": str(DSR_REPORT_PATH.relative_to(REPO_ROOT)).replace(
                "\\", "/"
            ),
            "selection_scope": panel["trials"][0]["selection_scope"],
            "expected_attempt_count": panel["expected_attempt_count"],
            "selection_pool_complete": panel["selection_pool_complete"],
            "panel_sha256": dsr_report["gate5_dsr_report"].get("panel_hash"),
            "status": dsr_report["gate5_dsr_report"]["status"],
            "probability": dsr_report["gate5_dsr_report"].get(
                "dsr_probability"
            ),
            "reason_codes": list(
                dsr_report.get("panel_result", {}).get("reason_codes") or []
            ),
        },
        "full_stack": {
            "verdict": verdict,
            "daily_candidate_parity_complete": False,
            "daily_observer_only": True,
            "daily_parity_reason": (
                "The shared daily helper persists source observations but does not "
                "advance strict-after OHLCV confirmation into candidate/open/closed "
                "lifecycle rows; rejected production wiring was rolled back."
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
            "shared_helper": "quant/fda_device_class1_enforcement_paper_sleeve.py",
        },
        "post_run_reflection": {
            "why_result_happened": (
                "; ".join(gate4["hard_failures"])
                if failures
                else "The frozen source cleared every preregistered historical Gate-4 check."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune firm aliases, Class-I filters, confirmation "
                "thresholds, rank, cooldown, hold, notional, costs, or windows."
            ),
            "new_evidence_required": (
                "A genuinely new official recall-risk source/direction or at "
                "least 30 closed forward replacement-value trades; map and "
                "threshold sweeps are not new evidence."
            ),
        },
        "reproduction_command": (
            f".\\.venv\\Scripts\\python.exe -B quant\\experiments\\{Path(__file__).name}"
        ),
    }


def _write_close_artifacts(payload: dict[str, Any]) -> None:
    rows = payload["windows"]
    before = {
        "schema": "fda_device_class1_gate4_aggregate_before_v1",
        "expected_value_score": payload["aggregate"][
            "before_expected_value_score_sum"
        ],
        "total_pnl": payload["aggregate"]["before_total_pnl_sum"],
        "max_drawdown_pct": max(
            row["before"]["max_drawdown_pct"] for row in rows.values()
        ),
        "total_trades": sum(
            row["before"]["total_trades"] for row in rows.values()
        ),
        "survival_rate": min(
            row["before"]["survival_rate"] for row in rows.values()
        ),
        "benchmarks": {
            "strategy_total_return_pct": round(
                payload["aggregate"]["before_total_pnl_sum"] / 100_000.0, 4
            )
        },
    }
    after = {
        "schema": "fda_device_class1_gate4_aggregate_after_v1",
        "expected_value_score": payload["aggregate"][
            "after_expected_value_score_sum"
        ],
        "total_pnl": payload["aggregate"]["after_total_pnl_sum"],
        "max_drawdown_pct": max(
            row["after"]["max_drawdown_pct"] for row in rows.values()
        ),
        "total_trades": sum(
            row["after"]["total_trades"] for row in rows.values()
        ),
        "survival_rate": payload["gate3"]["survival_rate"],
        "benchmarks": {
            "strategy_total_return_pct": round(
                payload["aggregate"]["after_total_pnl_sum"] / 100_000.0, 4
            )
        },
    }
    _write_json(BEFORE_PATH, before)
    _write_json(AFTER_PATH, after)


def _write_artifact(payload: dict[str, Any]) -> None:
    dsr = payload["deflated_sharpe"]
    lines = [
        f"# {EXPERIMENT_ID} FDA Device Class-I Enforcement Reports",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Full-stack verdict: `{payload['full_stack']['verdict']['verdict']}`",
        f"- Source events / tickers: `{payload['source']['event_count']}` / `{payload['source']['ticker_count']}`",
        f"- Target trades / tickers / windows: `{payload['target_summary']['total_trade_count']}` / `{payload['target_summary']['ticker_count']}` / `{payload['target_summary']['window_count']}`",
        f"- Aggregate EV delta: `{payload['aggregate']['expected_value_score_delta_sum']}`",
        f"- Aggregate PnL delta: `${payload['aggregate']['total_pnl_delta_sum']:,.2f}`",
        f"- Gate 3 survival: `{payload['gate3']['survival_rate']:.2%}`",
        f"- Gate 4 failures: `{', '.join(payload['gate4']['hard_failures']) or 'none'}`",
        f"- DSR: `{dsr['status']}` / `{dsr['probability']}` (Gate 5 only; reasons: `{', '.join(dsr['reason_codes']) or 'none'}`)",
        "",
        "## Point-in-time source contract",
        "",
        f"- Official API: {OFFICIAL_API_URL}",
        f"- Searchable fields: {OFFICIAL_FIELDS_URL}",
        "- `report_date` is the FDA enforcement-report issue date and is the only historical availability date used.",
        "- `recall_initiation_date` and `classification_date` are excluded from policy timing.",
        "- openFDA updates weekly and historical rows may change, so exact canonical API pages, normalized records, SHA256 hashes, and retrieval UTC are frozen.",
        "",
        "The historical helper is retained only for replay evidence; the rejected daily production wiring was rolled back and daily candidate parity remains incomplete. DSR is persisted from the complete aligned off-vs-on panel and affects only Gate 5, never the historical Gate-4 decision.",
    ]
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    payload = build_payload()
    _write_json(RESULT_PATH, payload)
    _write_close_artifacts(payload)
    _write_artifact(payload)
    print(
        json.dumps(
            {
                "decision": payload["decision"],
                "source": payload["source"],
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
