"""exp-20260714-002: official product-safety event response batch scout.

This private replay consumes frozen NHTSA defect-investigation and CPSC recall
source bundles.  NHTSA, CPSC, and pooled policies all use one locked recipe:
first strictly subsequent session green and ahead of SPY, top one per day,
ten-session ticker cooldown, next-open entry, tenth-session close, 4,000 USD
paper notional, and 35 bps round-trip cost.  Only pooled Gate 4 is binding.

Even a numerical pass is an observed-only positive lead.  Gate 5 fails closed
because the complete return panel for six earlier same-lane trials cannot be
reconstructed from their retained artifacts.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
for import_path in (REPO_ROOT, REPO_ROOT / "quant", REPO_ROOT / "scripts"):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from deflated_sharpe import build_report as build_dsr_report  # noqa: E402
from quant.evaluator_gates import ExperimentGateThresholds  # noqa: E402
from quant.full_stack_candidate_pool import (  # noqa: E402
    ExecutionEnvelope,
    evaluate_gate4,
    evaluate_live_readiness,
    full_stack_verdict,
)
from quant.experiments.exp_20260713_010_fda_device_class1_report_green_spy_relative_top1_10d_v1 import (  # noqa: E402
    combine_window,
    _target_summary,
)


EXPERIMENT_ID = "exp-20260714-002"
RULE_VERSION = "official_safety_event_response_batch_green_spy_top1_10d_v1"
BASE_NOTIONAL_USD = 4_000.0
ROUND_TRIP_COST_PCT = 0.0035
HOLD_SESSIONS = 10
SAME_TICKER_COOLDOWN_SESSIONS = 10
MIN_TARGET_TRADES = 20
MIN_TARGET_TICKERS = 3
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
PRIOR_LANE_ATTEMPT_COUNT = 6
CURRENT_POLICY_ATTEMPT_COUNT = 3

BASELINE_SUMMARY = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_post_mtm_20260712.json"
)
WAREHOUSE = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
AUX_OHLCV_PATH = OUT_DIR / "auxiliary_ohlcv.json"
EXPECTED_AUX_OHLCV_ROWSET_SHA256 = (
    "8aeec1341d79ea7ca2023e65bc57c7f1dbea11867def2b91472403af5ba32fb1"
)
RESULT_PATH = OUT_DIR / "official_safety_event_response_batch_replay.json"
BEFORE_PATH = OUT_DIR / "before.json"
AFTER_PATH = OUT_DIR / "after.json"
DSR_PANEL_PATH = OUT_DIR / "deflated_sharpe_panel.json"
DSR_REPORT_PATH = OUT_DIR / "deflated_sharpe_report.json"
ARTIFACT_PATH = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_official_safety_event_response_batch.md"
)

SOURCE_SPECS = OrderedDict(
    (
        (
            "nhtsa",
            {
                "directory": REPO_ROOT
                / "data"
                / "non_ohlcv"
                / "nhtsa_defect_investigations",
                "availability_field": "ODATE",
                "official_surface": "NHTSA defect-investigation openings",
            },
        ),
        (
            "cpsc",
            {
                "directory": REPO_ROOT / "data" / "non_ohlcv" / "cpsc_recalls",
                "availability_field": "max(RecallDate, LastPublishDate)",
                "official_surface": "CPSC recall publications",
            },
        ),
    )
)

# Frozen before outcome inspection.  The source manifests bind the complete
# official responses; these hashes additionally bind the exact normalized
# rows, issuer maps, and manifests consumed by this runner.
EXPECTED_SOURCE_FILE_SHA256 = {
    "nhtsa": {
        "events.json": "a8aec5085d087270cfc0e32cbad7a1575048fe6453099e080be17a01d7f26b8f",
        "issuer_map.json": "869c39f2e932121e47ad12279b45f0023a005e8996624a6deef4523377927447",
        "selected_raw_rows.json": "191136f72feb501b5e425bf66dccce4864f2122e81c3ae5ba91cac996d4439eb",
        "source_manifest.json": "bde9ec1f1aec5f29ae541722a7500045820c2c3fd0059ec4aeb5c15eac1fedbe",
    },
    "cpsc": {
        "events.json": "16424e384d1eeabb0ab7e26efc991a18daaa78c83aca091bc53b89891f958b8a",
        "issuer_map.json": "86fed44cea4728275c0b07d0f62bf8897279e39c09b24d123bb0cd33fe16c413",
        "selected_raw_rows.json": "e76533ec7539c2428ec1e52f7a6b8cc11f24cee308e3f4124703fc73bcc90e9d",
        "source_manifest.json": "d0b7328f9d33151bcdd21eca18ee58396fdded98da4b69deb336cf1c98a3399d",
    },
}

WINDOWS = OrderedDict(
    (
        ("late_strong", ("2025-10-23", "2026-04-21")),
        ("mid_weak", ("2025-04-23", "2025-10-22")),
        ("old_thin", ("2024-10-02", "2025-04-22")),
    )
)

COMPARATOR = {
    "experiment_id": "exp-20260611-007",
    "expected_value_score_delta_sum": 0.5286,
    "total_pnl_delta_sum": 10432.91,
}

PREDICTION = {
    "success_probability": 0.10,
    "expected_ev_delta": 0.10,
    "expected_pnl_delta": 1000.0,
    "main_failure_modes": [
        "window_regression",
        "accepted_comparator_not_beaten",
        "source_shards_too_small",
        "parent_mapping_survivorship",
        "incomplete_historical_dsr_panel",
    ],
}

CALCULATION_FILES = OrderedDict(
    (
        ("runner", Path(__file__).resolve()),
        (
            "daily_mtm_overlay_helper",
            REPO_ROOT
            / "quant"
            / "experiments"
            / "exp_20260713_010_fda_device_class1_report_green_spy_relative_top1_10d_v1.py",
        ),
        ("evaluator_gates", REPO_ROOT / "quant" / "evaluator_gates.py"),
        (
            "full_stack_candidate_pool",
            REPO_ROOT / "quant" / "full_stack_candidate_pool.py",
        ),
        ("deflated_sharpe", REPO_ROOT / "scripts" / "deflated_sharpe.py"),
    )
)


def _read_json(path: Path) -> Any:
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


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _return_series_sha(rows: list[dict[str, Any]]) -> str:
    return _canonical_sha(
        {"schema": "dated_periodic_return_series_v1", "rows": rows}
    )


def _calculation_identity() -> dict[str, Any]:
    missing = [name for name, path in CALCULATION_FILES.items() if not path.exists()]
    if missing:
        raise RuntimeError(f"missing calculation files: {missing}")
    return {
        name: {
            "path": str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
            "sha256": _file_sha(path),
        }
        for name, path in CALCULATION_FILES.items()
    }


def _iso_date(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    text = text[:10]
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _event_id(source: str, row: dict[str, Any]) -> str:
    fields = (
        ("event_id", "action_number", "ActionNumber")
        if source == "nhtsa"
        else ("event_id", "recall_number", "RecallID", "RecallNumber")
    )
    for field in fields:
        value = str(row.get(field) or "").strip()
        if value:
            return value
    return ""


def _issuer_name(source: str, row: dict[str, Any]) -> str:
    fields = (
        ("manufacturer", "MFR_NAME", "manufacturer_name")
        if source == "nhtsa"
        else ("issuer_name", "Manufacturer", "manufacturer")
    )
    for field in fields:
        value = str(row.get(field) or "").strip()
        if value:
            return value
    return ""


def _availability_date(source: str, row: dict[str, Any]) -> str | None:
    supplied = _iso_date(row.get("availability_date"))
    if source == "nhtsa":
        raw = _iso_date(
            row.get("ODATE") or row.get("odate") or row.get("open_date")
        )
        if supplied and raw and supplied != raw:
            raise RuntimeError(
                f"NHTSA availability/ODATE mismatch for {_event_id(source, row)}"
            )
        return supplied or raw
    recall = _iso_date(row.get("recall_date") or row.get("RecallDate"))
    published = _iso_date(
        row.get("last_publish_date") or row.get("LastPublishDate")
    )
    values = [value for value in (recall, published) if value]
    derived = max(values) if values else None
    if supplied and derived and supplied != derived:
        raise RuntimeError(
            f"CPSC availability/max-date mismatch for {_event_id(source, row)}"
        )
    return supplied or derived


def _claimed_sha(manifest: dict[str, Any], filename: str) -> str | None:
    for key in (
        f"{filename.replace('.', '_')}_sha256",
        f"{Path(filename).stem}_sha256",
    ):
        value = str(manifest.get(key) or "").strip().lower()
        if len(value) == 64:
            return value
    files = manifest.get("files")
    if isinstance(files, dict):
        row = files.get(filename)
        if isinstance(row, str) and len(row.strip()) == 64:
            return row.strip().lower()
        if isinstance(row, dict):
            value = str(row.get("sha256") or "").strip().lower()
            if len(value) == 64:
                return value
    if isinstance(files, list):
        for row in files:
            if not isinstance(row, dict):
                continue
            if str(row.get("path") or row.get("file") or "") != filename:
                continue
            value = str(row.get("sha256") or "").strip().lower()
            if len(value) == 64:
                return value
    return None


def load_source_bundle(
    source: str, spec: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    directory = Path(spec["directory"])
    required = {
        name: directory / name
        for name in (
            "source_manifest.json",
            "issuer_map.json",
            "selected_raw_rows.json",
            "events.json",
        )
    }
    missing = [
        str(path.relative_to(REPO_ROOT)).replace("\\", "/")
        for path in required.values()
        if not path.exists()
    ]
    if missing:
        raise RuntimeError(f"{source} source bundle is incomplete: {missing}")

    manifest = _read_json(required["source_manifest.json"])
    map_payload = _read_json(required["issuer_map.json"])
    raw_payload = _read_json(required["selected_raw_rows.json"])
    event_payload = _read_json(required["events.json"])
    if not all(
        isinstance(payload, dict)
        for payload in (manifest, map_payload, raw_payload, event_payload)
    ):
        raise RuntimeError(f"{source} source bundle payloads must be objects")

    file_identity: dict[str, Any] = {}
    for filename, path in required.items():
        actual = _file_sha(path)
        frozen = EXPECTED_SOURCE_FILE_SHA256.get(source, {}).get(filename)
        if not frozen or actual != frozen:
            raise RuntimeError(
                f"{source} frozen source hash mismatch: {filename}"
            )
        expected = _claimed_sha(manifest, filename)
        if expected and expected != actual:
            raise RuntimeError(f"{source} bundle hash mismatch: {filename}")
        file_identity[filename] = {
            "path": str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
            "sha256": actual,
            "frozen_sha256_verified": True,
            "manifest_sha256_verified": bool(expected),
        }

    exact_map = map_payload.get("exact_name_to_ticker")
    if not isinstance(exact_map, dict) or not exact_map:
        raise RuntimeError(f"{source} exact issuer map is empty")
    exact_map = {
        str(name).strip(): str(ticker).strip().upper()
        for name, ticker in exact_map.items()
        if str(name).strip() and str(ticker).strip()
    }

    raw_rows = raw_payload.get("rows")
    if not isinstance(raw_rows, list):
        raise RuntimeError(f"{source} selected_raw_rows.json has no rows")
    if (
        raw_payload.get("row_count") is not None
        and int(raw_payload["row_count"]) != len(raw_rows)
    ):
        raise RuntimeError(f"{source} selected raw row count drift")

    rows = event_payload.get("events")
    if not isinstance(rows, list):
        raise RuntimeError(f"{source} events.json has no events")
    if (
        event_payload.get("event_count") is not None
        and int(event_payload["event_count"]) != len(rows)
    ):
        raise RuntimeError(f"{source} event count drift")

    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for raw_event in rows:
        if not isinstance(raw_event, dict):
            raise RuntimeError(f"{source} event row is not an object")
        event_id = _event_id(source, raw_event)
        issuer_name = _issuer_name(source, raw_event)
        ticker = str(raw_event.get("ticker") or "").strip().upper()
        availability = _availability_date(source, raw_event)
        source_url = str(
            raw_event.get("source_url") or raw_event.get("url") or ""
        ).strip()
        if (
            not event_id
            or not issuer_name
            or not ticker
            or not availability
            or not source_url
        ):
            raise RuntimeError(f"{source} event lacks PIT/provenance fields")
        if exact_map.get(issuer_name) != ticker:
            raise RuntimeError(
                f"{source} exact issuer-map violation: {issuer_name} -> {ticker}"
            )
        if source == "nhtsa":
            source_zip_sha = str(
                raw_event.get("source_zip_sha256")
                or manifest.get("source_zip_sha256")
                or ""
            ).strip()
            if len(source_zip_sha) != 64:
                raise RuntimeError(
                    f"NHTSA event lacks ZIP provenance: {event_id}"
                )
        key = (event_id, ticker, availability)
        if key in seen:
            raise RuntimeError(f"{source} duplicated event key: {key}")
        seen.add(key)
        normalized.append(
            {
                **raw_event,
                "source": source,
                "event_id": event_id,
                "issuer_name": issuer_name,
                "ticker": ticker,
                "availability_date": availability,
                "source_url": source_url,
                "source_event_sha256": _canonical_sha(raw_event),
            }
        )

    normalized.sort(
        key=lambda row: (
            row["availability_date"],
            row["ticker"],
            row["event_id"],
        )
    )
    return normalized, {
        "source": source,
        "official_surface": spec["official_surface"],
        "availability_field": spec["availability_field"],
        "directory": str(directory.relative_to(REPO_ROOT)).replace("\\", "/"),
        "file_identity": file_identity,
        "bundle_sha256": _canonical_sha(file_identity),
        "event_count": len(normalized),
        "raw_row_count": len(raw_rows),
        "ticker_count": len({row["ticker"] for row in normalized}),
        "tickers": sorted({row["ticker"] for row in normalized}),
        "exact_issuer_count": len(exact_map),
        "exact_name_to_ticker": dict(sorted(exact_map.items())),
        "retrieved_at": manifest.get("fetched_at_utc")
        or manifest.get("retrieved_at")
        or manifest.get("generated_at"),
        "pit_contract": (
            "availability_date is the only clock; confirmation begins on the "
            "first strictly later trading session"
        ),
    }


def _baseline_window_map(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row["label"]): row for row in summary["windows"]}


def load_ohlcv(
    tickers: Iterable[str], start: str, end: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    required_tickers = sorted({str(ticker).upper() for ticker in tickers} | {"SPY"})
    if AUX_OHLCV_PATH.exists():
        payload = _read_json(AUX_OHLCV_PATH)
        output = payload.get("ohlcv") or {}
        actual = _canonical_sha(output)
        if (
            payload.get("start") != start
            or payload.get("end") != end
            or payload.get("tickers") != required_tickers
            or payload.get("rowset_sha256") != actual
        ):
            raise RuntimeError("frozen auxiliary OHLCV identity drift")
        if actual != EXPECTED_AUX_OHLCV_ROWSET_SHA256:
            raise RuntimeError("frozen auxiliary OHLCV rowset hash drift")
        return output, {
            "path": str(AUX_OHLCV_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
            "rowset_sha256": actual,
            "source_at_freeze": payload.get("source_at_freeze"),
        }

    placeholders = ",".join("?" for _ in required_tickers)
    query = f"""
        SELECT ticker, date, open, high, low, close
        FROM ohlcv
        WHERE ticker IN ({placeholders}) AND date >= ? AND date <= ?
        ORDER BY ticker, date
    """
    output: dict[str, list[dict[str, Any]]] = {
        ticker: [] for ticker in required_tickers
    }
    with sqlite3.connect(str(WAREHOUSE)) as connection:
        for ticker, day, open_, high, low, close in connection.execute(
            query, [*required_tickers, start, end]
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
        raise RuntimeError(f"required safety-event OHLCV missing: {missing}")
    rowset_sha = _canonical_sha(output)
    source_at_freeze = str(WAREHOUSE.relative_to(REPO_ROOT)).replace("\\", "/")
    _write_json(
        AUX_OHLCV_PATH,
        {
            "schema": "official_safety_event_auxiliary_ohlcv_v1",
            "source_at_freeze": source_at_freeze,
            "start": start,
            "end": end,
            "tickers": required_tickers,
            "rowset_sha256": rowset_sha,
            "ohlcv": output,
        },
    )
    if rowset_sha != EXPECTED_AUX_OHLCV_ROWSET_SHA256:
        raise RuntimeError("new auxiliary OHLCV does not match frozen rowset")
    return output, {
        "path": str(AUX_OHLCV_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
        "rowset_sha256": rowset_sha,
        "source_at_freeze": source_at_freeze,
    }


def _window_ohlcv(
    broad: dict[str, Any],
    baseline_window: dict[str, Any],
    required_tickers: Iterable[str],
    auxiliary_source: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    snapshot_path = REPO_ROOT / baseline_window["source"]
    snapshot = (_read_json(snapshot_path).get("ohlcv") or {})
    output = {ticker: list(rows) for ticker, rows in broad.items()}
    exact_tickers: list[str] = []
    for ticker in sorted({str(value).upper() for value in required_tickers} | {"SPY"}):
        if snapshot.get(ticker):
            output[ticker] = list(snapshot[ticker])
            exact_tickers.append(ticker)
    missing = [ticker for ticker, rows in output.items() if not rows]
    if missing:
        raise RuntimeError(f"required window OHLCV missing: {missing}")
    return output, {
        "gate1_snapshot": str(snapshot_path.relative_to(REPO_ROOT)).replace(
            "\\", "/"
        ),
        "exact_snapshot_tickers": exact_tickers,
        "frozen_auxiliary_fill_tickers": sorted(
            set(output) - set(exact_tickers)
        ),
        "frozen_auxiliary_source": auxiliary_source,
    }


def _normalise_bars(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for row in rows or []:
        day = _iso_date(row.get("date") or row.get("Date"))
        close = row.get("close") if "close" in row else row.get("Close")
        open_ = row.get("open") if "open" in row else row.get("Open")
        high = row.get("high") if "high" in row else row.get("High")
        low = row.get("low") if "low" in row else row.get("Low")
        if day and close not in (None, 0):
            output[day] = {
                "date": day,
                "open": float(open_) if open_ not in (None, "") else None,
                "high": float(high) if high not in (None, "") else None,
                "low": float(low) if low not in (None, "") else None,
                "close": float(close),
            }
    return [output[day] for day in sorted(output)]


def _atr_target(
    rows: list[dict[str, Any]], signal_idx: int, entry_price: float
) -> float:
    true_ranges: list[float] = []
    for idx in range(max(0, signal_idx - 13), signal_idx + 1):
        row = rows[idx]
        high, low = row.get("high"), row.get("low")
        if high is None or low is None:
            continue
        previous = rows[idx - 1]["close"] if idx > 0 else row["close"]
        true_ranges.append(
            max(high - low, abs(high - previous), abs(low - previous))
        )
    atr = sum(true_ranges) / len(true_ranges) if true_ranges else entry_price * 0.02
    return round(entry_price + 3.5 * atr, 4)


def build_candidates(
    *,
    events: Iterable[dict[str, Any]],
    ohlcv_by_ticker: dict[str, Any],
    start: str,
    end: str,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    bars = {
        str(ticker).upper(): _normalise_bars(rows)
        for ticker, rows in ohlcv_by_ticker.items()
    }
    spy = bars.get("SPY") or []
    spy_dates = [row["date"] for row in spy]
    spy_pos = {day: idx for idx, day in enumerate(spy_dates)}
    ticker_pos = {
        ticker: {row["date"]: idx for idx, row in enumerate(rows)}
        for ticker, rows in bars.items()
    }
    rejects: Counter[str] = Counter()
    deduped: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for event in events:
        source = str(event.get("source") or "")
        event_id = str(event.get("event_id") or "")
        ticker = str(event.get("ticker") or "").upper()
        availability = _iso_date(event.get("availability_date"))
        if (
            source not in SOURCE_SPECS
            or not event_id
            or not ticker
            or not availability
            or not event.get("source_url")
            or not event.get("source_event_sha256")
        ):
            rejects["invalid_or_unprovenanced_event"] += 1
            continue
        key = (source, event_id, ticker, availability)
        if key in deduped:
            rejects["duplicate_event_key"] += 1
            continue
        deduped[key] = dict(event)

    confirmed: list[dict[str, Any]] = []
    for event in deduped.values():
        ticker = event["ticker"]
        availability = event["availability_date"]
        signal_date = next((day for day in spy_dates if day > availability), None)
        if not signal_date or signal_date < start or signal_date > end:
            rejects["outside_signal_window"] += 1
            continue
        issuer_idx = ticker_pos.get(ticker, {}).get(signal_date)
        market_idx = spy_pos.get(signal_date)
        issuer = bars.get(ticker) or []
        if issuer_idx is None or market_idx is None or issuer_idx < 1 or market_idx < 1:
            rejects["missing_price_confirmation"] += 1
            continue
        issuer_return = (
            issuer[issuer_idx]["close"] / issuer[issuer_idx - 1]["close"] - 1.0
        )
        spy_return = spy[market_idx]["close"] / spy[market_idx - 1]["close"] - 1.0
        excess = issuer_return - spy_return
        if issuer_return <= 0:
            rejects["issuer_not_green"] += 1
            continue
        if excess <= 0:
            rejects["not_spy_relative_positive"] += 1
            continue
        confirmed.append(
            {
                **event,
                "signal_date": signal_date,
                "issuer_signal_return": round(issuer_return, 10),
                "spy_signal_return": round(spy_return, 10),
                "excess_signal_return": round(excess, 10),
                "score": round(excess, 10),
                "rule_version": RULE_VERSION,
                "trade_enabled": False,
                "alters_orders": False,
            }
        )

    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in confirmed:
        by_day[row["signal_date"]].append(row)
    selected: list[dict[str, Any]] = []
    next_allowed: dict[str, int] = {}
    for signal_date in sorted(by_day):
        day_rows = sorted(
            by_day[signal_date],
            key=lambda row: (
                -float(row["score"]),
                row["ticker"],
                row["source"],
                row["event_id"],
            ),
        )
        admitted = 0
        for row in day_rows:
            ticker = row["ticker"]
            position = spy_pos[signal_date]
            if position < next_allowed.get(ticker, -1):
                rejects["same_ticker_cooldown"] += 1
                continue
            if admitted >= 1:
                rejects["daily_top1_limit"] += 1
                continue
            selected.append(row)
            next_allowed[ticker] = (
                position + SAME_TICKER_COOLDOWN_SESSIONS
            )
            admitted += 1
    return selected, dict(sorted(rejects.items()))


def replay_policy(
    *,
    events: Iterable[dict[str, Any]],
    ohlcv_by_ticker: dict[str, Any],
    start: str,
    end: str,
) -> dict[str, Any]:
    event_rows = [dict(row) for row in events]
    bars = {
        str(ticker).upper(): _normalise_bars(rows)
        for ticker, rows in ohlcv_by_ticker.items()
    }
    selected, rejects = build_candidates(
        events=event_rows,
        ohlcv_by_ticker=bars,
        start=start,
        end=end,
    )
    trades: list[dict[str, Any]] = []
    unsettled: list[dict[str, Any]] = []
    for candidate in selected:
        ticker = candidate["ticker"]
        rows = bars.get(ticker) or []
        index = {row["date"]: idx for idx, row in enumerate(rows)}
        signal_idx = index.get(candidate["signal_date"])
        if signal_idx is None:
            unsettled.append(
                {**candidate, "unsettled_reason": "missing_signal_bar"}
            )
            continue
        entry_idx = signal_idx + 1
        exit_idx = entry_idx + HOLD_SESSIONS - 1
        if entry_idx >= len(rows) or rows[entry_idx]["date"] > end:
            unsettled.append(
                {**candidate, "unsettled_reason": "entry_outside_window"}
            )
            continue
        if exit_idx >= len(rows) or rows[exit_idx]["date"] > end:
            unsettled.append(
                {
                    **candidate,
                    "unsettled_reason": "tenth_close_outside_window",
                }
            )
            continue
        entry_price = rows[entry_idx].get("open")
        exit_price = rows[exit_idx].get("close")
        if not entry_price or not exit_price:
            unsettled.append(
                {
                    **candidate,
                    "unsettled_reason": "missing_entry_or_exit_price",
                }
            )
            continue
        net_return = exit_price / entry_price - 1.0 - ROUND_TRIP_COST_PCT
        trades.append(
            {
                **candidate,
                "entry_date": rows[entry_idx]["date"],
                "exit_date": rows[exit_idx]["date"],
                "entry_price": round(entry_price, 4),
                "exit_price": round(exit_price, 4),
                "target_price": _atr_target(rows, signal_idx, entry_price),
                "hold_days": HOLD_SESSIONS,
                "hold_sessions_realized": HOLD_SESSIONS,
                "scheduled_exit_date": rows[exit_idx]["date"],
                "exit_reason": "scheduled_10_session_horizon_close",
                "paper_notional_usd": BASE_NOTIONAL_USD,
                "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
                "pnl_pct_net": round(net_return, 10),
                "pnl": round(BASE_NOTIONAL_USD * net_return, 2),
            }
        )
    return {
        "trades": trades,
        "unsettled": unsettled,
        "selected_candidates": selected,
        "reject_totals": rejects,
        "signals_generated": len(event_rows),
        "signals_survived": len(selected),
        "survival_rate": (
            round(len(selected) / len(event_rows), 6) if event_rows else 0.0
        ),
    }


def _aggregate_policy(rows: dict[str, Any]) -> dict[str, Any]:
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


def _evaluate_gate4(
    aggregate: dict[str, Any],
    target: dict[str, Any],
    trades_by_window: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    metrics = {
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
        min_adjusted_trades=MIN_TARGET_TRADES,
        min_adjusted_windows=MIN_TARGET_WINDOWS,
        min_ev_improved_windows=MIN_TARGET_WINDOWS,
        max_ev_regressed_windows=0,
        max_drawdown_worse=MAX_DRAWDOWN_WORSE,
        require_tail_concentration_not_worse=False,
    )
    canonical = evaluate_gate4(
        metrics, thresholds=thresholds, check_materiality=False
    )
    strict = evaluate_gate4(
        metrics, thresholds=thresholds, check_materiality=True
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
    failures = list(dict.fromkeys(failures))
    return {
        "passed": not failures,
        "status": "passed" if not failures else "blocked",
        "hard_failures": failures,
        "canonical": canonical,
        "strict_materiality": strict,
        "metrics": metrics,
    }


def evaluate_policy(
    *,
    policy: str,
    events: list[dict[str, Any]],
    baseline_windows: dict[str, dict[str, Any]],
    ohlcv_by_window: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    rows: dict[str, Any] = {}
    trades_by_window: dict[str, list[dict[str, Any]]] = {}
    generated_total = 0
    survived_total = 0
    for label, (start, end) in WINDOWS.items():
        replay = replay_policy(
            events=events,
            ohlcv_by_ticker=ohlcv_by_window[label],
            start=start,
            end=end,
        )
        trades = replay["trades"]
        before, after, combined_curve = combine_window(
            baseline_windows[label], trades, ohlcv_by_window[label]
        )
        generated = sum(
            start <= row["availability_date"] <= end for row in events
        )
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
                "total_pnl": round(
                    after["total_pnl"] - before["total_pnl"], 2
                ),
                "max_drawdown_pct": round(
                    after["max_drawdown_pct"]
                    - before["max_drawdown_pct"],
                    4,
                ),
            },
            "signals_generated": generated,
            "signals_survived": survived,
            "survival_rate": (
                round(survived / generated, 6) if generated else 0.0
            ),
            "selected_candidates": replay["selected_candidates"],
            "target_trades": trades,
            "unsettled": replay["unsettled"],
            "reject_totals": replay["reject_totals"],
            "combined_curve_sha256": _canonical_sha(combined_curve),
        }
    target = _target_summary(trades_by_window)
    aggregate = _aggregate_policy(rows)
    gate3_rate = survived_total / generated_total if generated_total else 0.0
    return {
        "policy": policy,
        "binding_gate4": policy == "pooled",
        "windows": rows,
        "aggregate": aggregate,
        "target_summary": target,
        "gate3": {
            "passed": generated_total > 0 and gate3_rate >= 0.05,
            "signals_generated": generated_total,
            "signals_survived": survived_total,
            "survival_rate": round(gate3_rate, 6),
        },
        "gate4": _evaluate_gate4(aggregate, target, trades_by_window),
    }


def _policy_return_series(result: dict[str, Any]) -> list[dict[str, Any]]:
    combined: list[dict[str, Any]] = []
    for label in sorted(WINDOWS, key=lambda value: WINDOWS[value][0]):
        combined.extend(result["windows"][label]["after"]["return_series"])
    dates = [row["date"] for row in combined]
    if dates != sorted(dates) or len(dates) != len(set(dates)):
        raise RuntimeError("DSR current-policy dates are not strictly aligned")
    return combined


def _build_dsr(
    policies: dict[str, Any],
    sources: dict[str, Any],
    auxiliary: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    series = {
        policy: _policy_return_series(result)
        for policy, result in policies.items()
    }
    date_vectors = {
        tuple(row["date"] for row in rows) for rows in series.values()
    }
    if len(date_vectors) != 1:
        raise RuntimeError("DSR current-policy date vectors are not aligned")
    context = {
        "selection_scope": "official-event-green-spy-response-top1-10d-lane",
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
            "id": "post_mtm_gate1_plus_private_fixed_notional_v1",
            "rule_version": RULE_VERSION,
        },
        "data": {
            "baseline_summary_sha256": _file_sha(BASELINE_SUMMARY),
            "source_bundle_sha256": {
                key: value["bundle_sha256"] for key, value in sources.items()
            },
            "auxiliary_ohlcv_sha256": auxiliary["rowset_sha256"],
        },
        "cost": {"round_trip_cost_pct": ROUND_TRIP_COST_PCT},
    }
    trials = [
        {
            "config_id": f"current_{policy}_on",
            "config": {"policy": policy, "rule_version": RULE_VERSION},
            "attempted": True,
            **context,
            "return_series": rows,
            "return_series_sha256": _return_series_sha(rows),
            "return_series_source": (
                f"{RESULT_PATH.relative_to(REPO_ROOT).as_posix()}"
                f"#policies.{policy}.windows.*.after.return_series"
            ),
        }
        for policy, rows in series.items()
    ]
    panel = {
        "selected_config_id": "current_pooled_on",
        "expected_attempt_count": (
            PRIOR_LANE_ATTEMPT_COUNT + CURRENT_POLICY_ATTEMPT_COUNT
        ),
        "selection_pool_complete": False,
        "expected_return_dates": list(next(iter(date_vectors))),
        "periods_per_year": 252,
        "trials": trials,
        "unavailable_historical_attempt_count": PRIOR_LANE_ATTEMPT_COUNT,
        "reconstruction_note": (
            "Complete return series for six earlier same-lane experiments "
            "cannot be reconstructed; Gate 5 fails closed."
        ),
    }
    report = build_dsr_report(panel)
    if report.get("status") == "computable":
        raise RuntimeError("incomplete historical DSR panel computed unexpectedly")
    report["fail_closed_reason"] = (
        "complete_historical_same_lane_return_panel_not_reconstructable"
    )
    report["gate4_independence"] = True
    _write_json(DSR_PANEL_PATH, panel)
    _write_json(DSR_REPORT_PATH, report)
    return panel, report


def build_payload() -> dict[str, Any]:
    baseline_windows = _baseline_window_map(_read_json(BASELINE_SUMMARY))
    events_by_source: dict[str, list[dict[str, Any]]] = {}
    source_identity: dict[str, Any] = {}
    for source, spec in SOURCE_SPECS.items():
        events_by_source[source], source_identity[source] = load_source_bundle(
            source, spec
        )
    pooled_events = [
        row for source in SOURCE_SPECS for row in events_by_source[source]
    ]
    tickers = sorted({row["ticker"] for row in pooled_events})
    broad, auxiliary = load_ohlcv(tickers, "2024-09-01", "2026-05-15")
    ohlcv_by_window: dict[str, dict[str, Any]] = {}
    auxiliary_identity: dict[str, Any] = {}
    for label in WINDOWS:
        ohlcv_by_window[label], auxiliary_identity[label] = _window_ohlcv(
            broad, baseline_windows[label], tickers, auxiliary
        )
    policy_events = OrderedDict(
        (
            ("nhtsa", events_by_source["nhtsa"]),
            ("cpsc", events_by_source["cpsc"]),
            ("pooled", pooled_events),
        )
    )
    policies = {
        policy: evaluate_policy(
            policy=policy,
            events=events,
            baseline_windows=baseline_windows,
            ohlcv_by_window=ohlcv_by_window,
        )
        for policy, events in policy_events.items()
    }
    pooled = policies["pooled"]
    pooled_trades = [
        trade
        for row in pooled["windows"].values()
        for trade in row["target_trades"]
    ]
    event_contract = bool(pooled_events) and all(
        row.get("event_id")
        and row.get("availability_date")
        and row.get("ticker")
        and row.get("issuer_name")
        and row.get("source_url")
        and row.get("source_event_sha256")
        for row in pooled_events
    )
    signal_contract = bool(pooled_trades) and all(
        row.get("entry_date") and row.get("target_price")
        for row in pooled_trades
    )
    gate2_passed = event_contract and signal_contract
    failures = list(pooled["gate4"]["hard_failures"])
    if not gate2_passed:
        failures.append("gate2_signal_contract_failed")
    if not pooled["gate3"]["passed"]:
        failures.append("gate3_survival_below_5pct")
    failures = list(dict.fromkeys(failures))
    pooled["gate4"] = {
        **pooled["gate4"],
        "passed": not failures,
        "status": "passed" if not failures else "blocked",
        "hard_failures": failures,
    }

    panel, dsr_report = _build_dsr(policies, source_identity, auxiliary)
    reason_codes = list(
        dsr_report["gate5_dsr_report"].get("reason_codes")
        or dsr_report.get("panel_result", {}).get("reason_codes")
        or ["selection_pool_incomplete"]
    )
    gate5 = {
        "passed": False,
        "status": "not_computable",
        "fail_closed": True,
        "probability": None,
        "selection_pool_complete": False,
        "expected_attempt_count": panel["expected_attempt_count"],
        "available_attempt_count": len(panel["trials"]),
        "missing_historical_attempt_count": PRIOR_LANE_ATTEMPT_COUNT,
        "reason_codes": reason_codes,
        "reason": (
            "Complete same-lane return series for six prior experiments cannot "
            "be reconstructed; DSR cannot be computed honestly."
        ),
        "panel_path": str(DSR_PANEL_PATH.relative_to(REPO_ROOT)).replace(
            "\\", "/"
        ),
        "report_path": str(DSR_REPORT_PATH.relative_to(REPO_ROOT)).replace(
            "\\", "/"
        ),
        "gate4_independent": True,
    }
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
        notes="Private replay; pooled top1/day; 35bps round trip.",
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
        gate4=pooled["gate4"], live_readiness=live, envelope=envelope
    )
    lead = bool(pooled["gate4"]["passed"])
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "lane": "alpha_search",
        "status": "observed_only_positive_lead" if lead else "rejected",
        "decision": (
            "observed_only_positive_lead_private_scout"
            if lead
            else "rejected_official_safety_event_response_batch"
        ),
        "accepted_alpha": False,
        "observed_only_positive_lead": lead,
        "hypothesis": (
            "Official safety events followed by a green, SPY-relative first "
            "subsequent session continue from next open to tenth close."
        ),
        "rule_version": RULE_VERSION,
        "locked_policy": {
            "availability": "NHTSA ODATE; CPSC max(RecallDate, LastPublishDate)",
            "confirmation": "green and SPY-relative first subsequent session",
            "rank": "top1 per day",
            "cooldown_sessions": SAME_TICKER_COOLDOWN_SESSIONS,
            "entry": "next_open",
            "exit": "tenth_session_close",
            "notional_usd": BASE_NOTIONAL_USD,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
        },
        "source_bundles": source_identity,
        "source_scope_status": (
            "curated_current_snapshot_hash_bound_not_full_raw_offline_reconstructable"
        ),
        "calculation_identity": _calculation_identity(),
        "auxiliary_ohlcv_frozen_identity": {
            "path": str(AUX_OHLCV_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
            "rowset_sha256": EXPECTED_AUX_OHLCV_ROWSET_SHA256,
            "file_sha256": _file_sha(AUX_OHLCV_PATH),
        },
        "policies": policies,
        "binding_policy": "pooled",
        "aggregate": pooled["aggregate"],
        "target_summary": pooled["target_summary"],
        "accepted_comparator": COMPARATOR,
        "nearby_prior_experiments": [
            "exp-20260711-019",
            "exp-20260711-020",
            "exp-20260711-023",
            "exp-20260712-009",
            "exp-20260713-008",
            "exp-20260713-010",
        ],
        "gate1": {
            "passed": True,
            "baseline": str(BASELINE_SUMMARY.relative_to(REPO_ROOT)).replace(
                "\\", "/"
            ),
            "baseline_sha256": _file_sha(BASELINE_SUMMARY),
            "active_reference": "2026-07-12 post-MTM standard windows",
            "auxiliary_bar_identity": auxiliary_identity,
        },
        "gate2": {
            "passed": gate2_passed,
            "event_contract_passed": event_contract,
            "signal_contract_passed": signal_contract,
            "sentinel_fields": ["entry_date", "target_price"],
        },
        "gate3": pooled["gate3"],
        "gate4": pooled["gate4"],
        "gate5": gate5,
        "deflated_sharpe": gate5,
        "full_stack": {
            "verdict": verdict,
            "daily_candidate_parity_complete": False,
            "daily_observer_only": False,
            "daily_parity_reason": (
                "Private replay only; no shared helper or daily snapshot."
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
            "daily_wiring_retained": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "shared_helper": None,
        },
        "post_run_reflection": {
            "why_result_happened": (
                "; ".join(failures)
                if failures
                else "Pooled Gate 4 passed, but private scout remains a lead."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune maps, PIT dates, confirmation, source weights, "
                "rank, cooldown, hold, notional, costs, or windows."
            ),
            "new_evidence_required": (
                "Park this fixed official-source recipe. Reopen only for one "
                "predeclared batch containing at least three newly audit-ready "
                "official sources with canonical PIT coverage and an expected "
                "minimum of 20 settled trades per source, or for a materially "
                "different gate shape. Do not consume another source one ID at "
                "a time."
            ),
        },
        "reopen_condition": (
            "At least three newly audit-ready official sources, each with all "
            "three canonical windows and at least 20 expected settled trades, "
            "must be frozen before one additional batch ID; alternatively use "
            "a materially different gate shape."
        ),
        "residual_unknowns": [
            (
                "The current NHTSA flat archive can contain revisions made after "
                "ODATE; no historical as-of archive proves the exact bytes visible "
                "on each opening date. Strict next-session use is conservative but "
                "does not reconstruct report-date versions."
            ),
            (
                "The complete NHTSA ZIP and CPSC API response are identified by "
                "SHA256 but are not stored in the repository. The 78 curated source "
                "rows are reproducible and hard-bound, while full-response omission "
                "checks cannot be repeated offline from this checkout alone."
            ),
            (
                "Exact issuer maps are predeclared and exclude fuzzy parent joins, "
                "but historical issuer-ownership provenance is not independently "
                "versioned for every event date."
            ),
        ],
        "changed_files": [
            "quant/experiments/exp_20260714_002_official_safety_event_response_batch.py",
            "data/non_ohlcv/nhtsa_defect_investigations/",
            "data/non_ohlcv/cpsc_recalls/",
            "data/experiments/exp-20260714-002/",
            "experiments/artifacts/exp-20260714-002_official_safety_event_response_batch.md",
            "scripts/experiment_fingerprint.py",
            "quant/test_experiment_fingerprint.py",
            "docs/frozen_families.jsonl",
        ],
        "reproduction_command": (
            f".\\.venv\\Scripts\\python.exe -B "
            f"quant\\experiments\\{Path(__file__).name}"
        ),
    }


def _write_outputs(payload: dict[str, Any]) -> None:
    _write_json(RESULT_PATH, payload)
    rows = payload["policies"]["pooled"]["windows"]
    for path, side in ((BEFORE_PATH, "before"), (AFTER_PATH, "after")):
        aggregate = payload["aggregate"]
        _write_json(
            path,
            {
                "schema": f"official_safety_batch_gate4_{side}_v1",
                "expected_value_score": aggregate[
                    f"{side}_expected_value_score_sum"
                ],
                "total_pnl": aggregate[f"{side}_total_pnl_sum"],
                "max_drawdown_pct": max(
                    row[side]["max_drawdown_pct"] for row in rows.values()
                ),
                "total_trades": sum(
                    row[side]["total_trades"] for row in rows.values()
                ),
                "survival_rate": (
                    payload["gate3"]["survival_rate"]
                    if side == "after"
                    else min(
                        row["before"]["survival_rate"]
                        for row in rows.values()
                    )
                ),
                "benchmarks": {
                    "strategy_total_return_pct": round(
                        aggregate[f"{side}_total_pnl_sum"] / 100_000.0, 4
                    )
                },
            },
        )
    lines = [
        f"# {EXPERIMENT_ID} Official Safety Event Response Batch",
        "",
        f"- Decision: {payload['decision']}",
        "- Binding policy: pooled NHTSA + CPSC",
        (
            "- Pooled trades / tickers / windows: "
            f"{payload['target_summary']['total_trade_count']} / "
            f"{payload['target_summary']['ticker_count']} / "
            f"{payload['target_summary']['window_count']}"
        ),
        (
            "- Aggregate EV / PnL delta: "
            f"{payload['aggregate']['expected_value_score_delta_sum']} / USD "
            f"{payload['aggregate']['total_pnl_delta_sum']:,.2f}"
        ),
        f"- Gate 3 survival: {payload['gate3']['survival_rate']:.2%}",
        f"- Gate 4 failures: {', '.join(payload['gate4']['hard_failures']) or 'none'}",
        (
            "- Gate 5: not_computable, fail-closed because six prior "
            "same-lane return series cannot be reconstructed."
        ),
        "",
        "## Diagnostic shards",
        "",
    ]
    for source in ("nhtsa", "cpsc"):
        result = payload["policies"][source]
        lines.append(
            f"- {source.upper()}: events="
            f"{payload['source_bundles'][source]['event_count']}, trades="
            f"{result['target_summary']['total_trade_count']}, EV delta="
            f"{result['aggregate']['expected_value_score_delta_sum']}, PnL="
            f"USD {result['aggregate']['total_pnl_delta_sum']:,.2f}."
        )
    lines.extend(
        [
            "",
            (
                "NHTSA uses ODATE and CPSC uses max(RecallDate, "
                "LastPublishDate). Both use exact issuer maps and the same "
                "strict-after/top1/cooldown/next-open/tenth-close policy."
            ),
            (
                "Any pass remains an observed-only lead: no shared helper, "
                "daily snapshot, adapter, or live order path changed."
            ),
            (
                "Preflight selected 25 candidates; 22 are settled inside their "
                "canonical windows. NHTSA GM on 2025-10-22 enters outside mid_weak; "
                "CPSC RH on 2025-10-20 and GNRC on 2026-04-20 have tenth closes "
                "outside their windows. Gate 3 uses 25 selected rows; Gate 4 uses "
                "22 settled trades."
            ),
            (
                "Residual source caveat: the 78 curated rows and their calculation "
                "inputs are hash-bound, but the complete official responses are "
                "represented only by response hashes, not stored raw bytes; NHTSA "
                "report-date version history is therefore unknown."
            ),
            "",
            "## Window deltas",
            "",
        ]
    )
    for label in WINDOWS:
        row = payload["policies"]["pooled"]["windows"][label]
        lines.append(
            f"- {label}: trades={len(row['target_trades'])}, EV delta="
            f"{row['delta']['expected_value_score']:+.4f}, PnL delta=USD "
            f"{row['delta']['total_pnl']:+,.2f}, drawdown delta="
            f"{row['delta']['max_drawdown_pct']:+.4f}."
        )
    lines.extend(
        [
            "",
            "## Closeout",
            "",
            (
                "Related trials: exp-20260711-019, exp-20260711-020, "
                "exp-20260711-023, exp-20260712-009, exp-20260713-008, "
                "exp-20260713-010."
            ),
            (
                "Decision: reject and park this fixed recipe. Reopen only "
                "after at least three newly audit-ready official sources each "
                "have all three canonical windows and at least 20 expected "
                "settled trades, then consume them in one batch; a materially "
                "different gate shape is the other legal exit."
            ),
            (
                "Reproduce: .\\.venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260714_002_official_safety_event_response_batch.py"
            ),
        ]
    )
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    payload = build_payload()
    _write_outputs(payload)
    print(
        json.dumps(
            {
                "decision": payload["decision"],
                "pooled_target_summary": payload["target_summary"],
                "pooled_aggregate": payload["aggregate"],
                "gate4_failures": payload["gate4"]["hard_failures"],
                "gate5": payload["gate5"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
