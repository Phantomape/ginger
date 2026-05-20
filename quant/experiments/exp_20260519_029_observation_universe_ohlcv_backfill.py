"""exp-20260519-029: observation-universe OHLCV backfill.

This is a measurement-repair artifact builder. It copies the canonical
three-window OHLCV snapshots and appends the current core, observation, and
pilot universe tickers so future core-expansion replays can be run against a
single reproducible snapshot set. It does not mutate canonical snapshots or
change production strategy behavior.
"""

from __future__ import annotations

import argparse
import json
import math
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ID = "exp-20260519-029"

WINDOWS: dict[str, dict[str, str]] = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "source_snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
        "cache_snapshot": "data/experiments/exp-20260501-008/ohlcv_aug_20251023_20260421.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "source_snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
        "cache_snapshot": "data/experiments/exp-20260501-008/ohlcv_aug_20250423_20251022.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "source_snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
        "cache_snapshot": "data/experiments/exp-20260501-008/ohlcv_aug_20241002_20250422.json",
    },
}

UNIVERSE_STATE_PATH = REPO_ROOT / "data" / "daily" / "universe" / "universe_state_20260518.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def _repo_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("/", "\\")


def _parse_date(raw: str) -> datetime:
    return datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def _snapshot_fetch_bounds(snapshot: dict[str, Any]) -> tuple[str, str]:
    metadata = snapshot.get("metadata") or {}
    start = metadata.get("download_start")
    end = metadata.get("download_end")
    if start and end:
        return str(start), str(end)

    dates: list[str] = []
    for rows in (snapshot.get("ohlcv") or {}).values():
        for row in rows or []:
            date = row.get("Date")
            if date:
                dates.append(str(date))
    if not dates:
        raise ValueError("snapshot has no metadata download bounds or row dates")
    return min(dates), max(dates)


def _finite_float(raw: Any) -> float | None:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    return value


def _normalise_ticker(raw: Any) -> str:
    return str(raw).strip().upper()


def _load_universe_state() -> dict[str, Any]:
    if not UNIVERSE_STATE_PATH.exists():
        raise FileNotFoundError(f"missing universe state: {UNIVERSE_STATE_PATH}")
    state = _load_json(UNIVERSE_STATE_PATH)
    records = {
        _normalise_ticker(ticker): record
        for ticker, record in (state.get("records") or {}).items()
        if isinstance(record, dict)
    }
    target_tickers = sorted(
        {
            _normalise_ticker(ticker)
            for key in (
                "core_trade_universe",
                "observation_universe",
                "pilot_trade_universe",
                "governance_tradeable_universe",
            )
            for ticker in (state.get(key) or [])
        }
    )
    return {
        "path": _repo_rel(UNIVERSE_STATE_PATH),
        "as_of": state.get("as_of"),
        "mode": state.get("mode"),
        "core_trade_universe": sorted(map(_normalise_ticker, state.get("core_trade_universe") or [])),
        "observation_universe": sorted(map(_normalise_ticker, state.get("observation_universe") or [])),
        "pilot_trade_universe": sorted(map(_normalise_ticker, state.get("pilot_trade_universe") or [])),
        "governance_tradeable_universe": sorted(
            map(_normalise_ticker, state.get("governance_tradeable_universe") or [])
        ),
        "records": records,
        "target_tickers": target_tickers,
    }


def _row_date(row: dict[str, Any]) -> str | None:
    raw = row.get("Date")
    return str(raw) if raw else None


def _clean_rows(rows: Any, start: str, end: str) -> list[dict[str, Any]]:
    cleaned: dict[str, dict[str, Any]] = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        date = _row_date(row)
        if not date or date < start or date > end:
            continue
        open_ = _finite_float(row.get("Open"))
        high = _finite_float(row.get("High"))
        low = _finite_float(row.get("Low"))
        close = _finite_float(row.get("Close"))
        if open_ is None or high is None or low is None or close is None:
            continue
        volume = _finite_float(row.get("Volume"))
        cleaned[date] = {
            "Date": date,
            "Open": float(open_),
            "High": float(high),
            "Low": float(low),
            "Close": float(close),
            "Volume": float(volume or 0.0),
        }
    return [cleaned[date] for date in sorted(cleaned)]


def _fetch_yahoo_adjusted_rows(ticker: str, start: str, end: str) -> list[dict[str, Any]]:
    start_dt = _parse_date(start)
    # Yahoo chart period2 is exclusive. Add one day so a weekday end is included.
    end_dt = _parse_date(end) + timedelta(days=1)
    period1 = int(start_dt.timestamp())
    period2 = int(end_dt.timestamp())
    encoded = urllib.parse.quote(ticker)
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}"
        f"?period1={period1}&period2={period2}&interval=1d"
        "&events=history&includeAdjustedClose=true"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    chart = payload.get("chart") or {}
    error = chart.get("error")
    if error:
        raise RuntimeError(error)
    result = (chart.get("result") or [None])[0]
    if not result:
        return []

    timestamps = result.get("timestamp") or []
    indicators = result.get("indicators") or {}
    quote = (indicators.get("quote") or [{}])[0]
    adj = (indicators.get("adjclose") or [{}])[0].get("adjclose") or []

    rows: list[dict[str, Any]] = []
    for idx, ts in enumerate(timestamps):
        raw_close = _finite_float((quote.get("close") or [None])[idx])
        adj_close = _finite_float(adj[idx] if idx < len(adj) else None)
        open_ = _finite_float((quote.get("open") or [None])[idx])
        high = _finite_float((quote.get("high") or [None])[idx])
        low = _finite_float((quote.get("low") or [None])[idx])
        volume = _finite_float((quote.get("volume") or [None])[idx])
        if raw_close is None or adj_close is None or open_ is None or high is None or low is None:
            continue
        ratio = adj_close / raw_close if raw_close else 1.0
        rows.append(
            {
                "Date": datetime.fromtimestamp(int(ts), tz=timezone.utc).date().isoformat(),
                "Open": float(open_ * ratio),
                "High": float(high * ratio),
                "Low": float(low * ratio),
                "Close": float(adj_close),
                "Volume": float(volume or 0.0),
            }
        )
    rows.sort(key=lambda row: row["Date"])
    return rows


def _expected_dates(snapshot: dict[str, Any], start: str, end: str) -> set[str]:
    ohlcv = snapshot.get("ohlcv") or {}
    reference_rows = ohlcv.get("SPY") or next(iter(ohlcv.values()), [])
    return {
        date
        for date in (_row_date(row) for row in reference_rows or [])
        if date and start <= date <= end
    }


def _coverage(rows: list[dict[str, Any]], expected_dates: set[str]) -> dict[str, Any]:
    dates = {_row_date(row) for row in rows if _row_date(row)}
    covered = len(dates & expected_dates)
    expected = len(expected_dates)
    fraction = covered / expected if expected else 0.0
    status = "zero_rows"
    if rows:
        status = "full" if fraction >= 0.95 else "partial"
    return {
        "row_count": len(rows),
        "first_date": min(dates) if dates else None,
        "last_date": max(dates) if dates else None,
        "expected_trading_dates": expected,
        "covered_expected_trading_dates": covered,
        "coverage_fraction": round(fraction, 4),
        "coverage_status": status,
    }


def _is_post_window_universe_record(universe: dict[str, Any], ticker: str, fetch_end: str) -> bool:
    record = (universe.get("records") or {}).get(ticker) or {}
    for key in ("data_available_as_of", "discovered_as_of", "eligible_as_of", "decision_as_of"):
        raw = record.get(key)
        if raw and str(raw) > fetch_end:
            return True
    return False


def _output_snapshot_path(label: str) -> Path:
    return (
        REPO_ROOT
        / "data"
        / "experiments"
        / EXPERIMENT_ID
        / "ohlcv"
        / f"{EXPERIMENT_ID}_{label}_current_universe_ohlcv.json"
    )


def _window_before_metrics(source_ohlcv: dict[str, Any], target_tickers: list[str]) -> dict[str, Any]:
    present = [ticker for ticker in target_tickers if source_ohlcv.get(ticker)]
    return {
        "source_ticker_count": len(source_ohlcv),
        "target_ticker_count": len(target_tickers),
        "target_present_before": len(present),
        "target_missing_before": len(target_tickers) - len(present),
    }


def build_backfill(*, no_network: bool, sleep_seconds: float, generated_at: str) -> dict[str, Any]:
    universe = _load_universe_state()
    target_tickers: list[str] = universe["target_tickers"]
    manifest: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": generated_at,
        "status": "running",
        "change_type": "measurement_repair",
        "changed_variable": "append_current_core_observation_pilot_universe_tickers_to_snapshot_copies",
        "data_source_priority": [
            "canonical fixed-window OHLCV snapshot",
            "exp-20260501-008 cached augmented OHLCV snapshot",
            "Yahoo Finance chart API adjusted OHLC",
        ],
        "network_enabled": not no_network,
        "source_universe_state": universe,
        "tickers_requested": target_tickers,
        "windows": {},
        "before_metrics": {},
        "after_metrics": {},
        "delta_metrics": {},
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
        },
        "notes": [
            "Canonical snapshots under data/ohlcv are not modified.",
            "This artifact only expands OHLCV coverage for future replay experiments.",
            "Zero-row tickers are tracked separately from provider/network failures; recent listings can legitimately have no older-window rows.",
        ],
    }

    aggregate = {
        "target_ticker_count": len(target_tickers),
        "requested_window_slots": len(target_tickers) * len(WINDOWS),
        "already_present": 0,
        "added_from_cache": 0,
        "added_from_yahoo": 0,
        "zero_rows": 0,
        "post_window_zero_rows": 0,
        "provider_or_network_failures": 0,
        "full_coverage": 0,
        "partial_coverage": 0,
    }

    for label, spec in WINDOWS.items():
        source_path = REPO_ROOT / spec["source_snapshot"]
        cache_path = REPO_ROOT / spec["cache_snapshot"]
        source_snapshot = _load_json(source_path)
        source_ohlcv = source_snapshot.get("ohlcv") or {}
        before_metrics = _window_before_metrics(source_ohlcv, target_tickers)

        snapshot = json.loads(json.dumps(source_snapshot))
        ohlcv = snapshot.setdefault("ohlcv", {})
        fetch_start, fetch_end = _snapshot_fetch_bounds(snapshot)
        expected_dates = _expected_dates(snapshot, fetch_start, fetch_end)
        cache_snapshot = _load_json(cache_path) if cache_path.exists() else {}
        cache_ohlcv = cache_snapshot.get("ohlcv") or {}

        already_present: list[str] = []
        added_from_cache: list[str] = []
        added_from_yahoo: list[str] = []
        zero_rows: list[str] = []
        post_window_zero_rows: list[str] = []
        failures: dict[str, str] = {}
        ticker_coverage: dict[str, dict[str, Any]] = {}

        for ticker in target_tickers:
            source = "missing"
            rows = _clean_rows(ohlcv.get(ticker), fetch_start, fetch_end)
            if rows:
                already_present.append(ticker)
                source = "canonical"
            else:
                rows = _clean_rows(cache_ohlcv.get(ticker), fetch_start, fetch_end)
                if rows:
                    ohlcv[ticker] = rows
                    added_from_cache.append(ticker)
                    source = "exp-20260501-008-cache"
                elif not no_network:
                    try:
                        rows = _clean_rows(
                            _fetch_yahoo_adjusted_rows(ticker, fetch_start, fetch_end),
                            fetch_start,
                            fetch_end,
                        )
                    except Exception as exc:  # pragma: no cover - provider/network behavior
                        if _is_post_window_universe_record(universe, ticker, fetch_end):
                            post_window_zero_rows.append(ticker)
                        else:
                            failures[ticker] = str(exc)
                        rows = []
                    if rows:
                        ohlcv[ticker] = rows
                        added_from_yahoo.append(ticker)
                        source = "yahoo-chart-api"
                    else:
                        zero_rows.append(ticker)
                        if ticker in post_window_zero_rows:
                            source = "post_window_universe_record_zero_rows"
                        elif ticker in failures:
                            source = "fetch_failed"
                        else:
                            source = "zero_rows"
                    if sleep_seconds > 0:
                        time.sleep(sleep_seconds)
                else:
                    zero_rows.append(ticker)
                    if _is_post_window_universe_record(universe, ticker, fetch_end):
                        post_window_zero_rows.append(ticker)
                        source = "post_window_universe_record_zero_rows"
                    else:
                        source = "not_fetched_no_network"

            coverage = _coverage(rows, expected_dates)
            coverage["source"] = source
            ticker_coverage[ticker] = coverage

        metadata = snapshot.setdefault("metadata", {})
        prior_augments = metadata.get("observation_universe_ohlcv_augments") or []
        metadata.update(
            {
                "observation_universe_ohlcv_backfilled": True,
                "observation_universe_ohlcv_backfilled_at": generated_at,
                "observation_universe_ohlcv_experiment_id": EXPERIMENT_ID,
                "observation_universe_ohlcv_source_snapshot": spec["source_snapshot"],
                "observation_universe_ohlcv_cache_snapshot": spec["cache_snapshot"],
                "observation_universe_ohlcv_added_from_cache": added_from_cache,
                "observation_universe_ohlcv_added_from_yahoo": added_from_yahoo,
                "observation_universe_ohlcv_zero_rows": zero_rows,
                "observation_universe_ohlcv_post_window_zero_rows": post_window_zero_rows,
                "observation_universe_ohlcv_failures": failures,
                "ticker_count": len(ohlcv),
                "tickers": sorted(ohlcv),
                "observation_universe_ohlcv_augments": [
                    *prior_augments,
                    {
                        "experiment_id": EXPERIMENT_ID,
                        "generated_at": generated_at,
                        "tickers_requested": target_tickers,
                        "network_enabled": not no_network,
                    },
                ],
            }
        )

        output_path = _output_snapshot_path(label)
        _write_json(output_path, snapshot)

        full = [
            ticker
            for ticker, coverage in ticker_coverage.items()
            if coverage["coverage_status"] == "full"
        ]
        partial = [
            ticker
            for ticker, coverage in ticker_coverage.items()
            if coverage["coverage_status"] == "partial"
        ]
        zero = [
            ticker
            for ticker, coverage in ticker_coverage.items()
            if coverage["coverage_status"] == "zero_rows"
        ]

        after_metrics = {
            "output_ticker_count": len(ohlcv),
            "target_ticker_count": len(target_tickers),
            "target_with_rows_after": len(full) + len(partial),
            "target_zero_rows_after": len(zero),
            "target_fetch_failures_after": len(failures),
            "full_coverage_count": len(full),
            "partial_coverage_count": len(partial),
        }
        delta_metrics = {
            "target_present_delta": after_metrics["target_with_rows_after"]
            - before_metrics["target_present_before"],
            "output_ticker_count_delta": after_metrics["output_ticker_count"]
            - before_metrics["source_ticker_count"],
        }
        manifest["before_metrics"][label] = before_metrics
        manifest["after_metrics"][label] = after_metrics
        manifest["delta_metrics"][label] = delta_metrics
        manifest["windows"][label] = {
            "date_range": {"start": spec["start"], "end": spec["end"]},
            "source_snapshot": spec["source_snapshot"],
            "cache_snapshot": spec["cache_snapshot"],
            "output_snapshot": _repo_rel(output_path),
            "fetch_range": {"start": fetch_start, "end": fetch_end},
            "expected_trading_dates": len(expected_dates),
            "source_ticker_count": before_metrics["source_ticker_count"],
            "output_ticker_count": len(ohlcv),
            "already_present_tickers": already_present,
            "added_from_cache_tickers": added_from_cache,
            "added_from_yahoo_tickers": added_from_yahoo,
            "zero_row_tickers": zero_rows,
            "post_window_zero_row_tickers": post_window_zero_rows,
            "provider_or_network_failures": failures,
            "coverage_summary": {
                "full_coverage_count": len(full),
                "partial_coverage_count": len(partial),
                "zero_rows_count": len(zero),
                "full_coverage_tickers": full,
                "partial_coverage_tickers": partial,
                "zero_row_tickers": zero,
            },
            "ticker_coverage": ticker_coverage,
        }

        aggregate["already_present"] += len(already_present)
        aggregate["added_from_cache"] += len(added_from_cache)
        aggregate["added_from_yahoo"] += len(added_from_yahoo)
        aggregate["zero_rows"] += len(zero)
        aggregate["post_window_zero_rows"] += len(set(post_window_zero_rows))
        aggregate["provider_or_network_failures"] += len(failures)
        aggregate["full_coverage"] += len(full)
        aggregate["partial_coverage"] += len(partial)

    manifest["aggregate_coverage"] = aggregate
    manifest["status"] = (
        "completed_with_provider_failures"
        if aggregate["provider_or_network_failures"]
        else "completed_with_explicit_zero_rows"
        if aggregate["zero_rows"]
        else "completed_full_coverage"
    )
    manifest["decision"] = (
        "accepted_measurement_repair_with_provider_failures"
        if aggregate["provider_or_network_failures"]
        else "accepted_measurement_repair"
    )
    manifest["next_step"] = (
        "Rerun with network access or a different provider for failed tickers."
        if aggregate["provider_or_network_failures"]
        else "Use output_snapshot paths for the next core-expansion replay; do not replace canonical snapshots."
    )
    return manifest


def _artifact_markdown(manifest: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Observation-Universe OHLCV Backfill",
        "",
        "## Summary",
        "",
        f"- Status: `{manifest['status']}`",
        f"- Network enabled: `{manifest['network_enabled']}`",
        f"- Target tickers: `{len(manifest['tickers_requested'])}`",
        f"- Added from cache: `{manifest['aggregate_coverage']['added_from_cache']}` window-ticker slots",
        f"- Added from Yahoo: `{manifest['aggregate_coverage']['added_from_yahoo']}` window-ticker slots",
        f"- Provider/network failures: `{manifest['aggregate_coverage']['provider_or_network_failures']}`",
        f"- Explicit zero-row slots: `{manifest['aggregate_coverage']['zero_rows']}`",
        f"- Post-window zero-row slots: `{manifest['aggregate_coverage']['post_window_zero_rows']}`",
        "",
        "## Window Outputs",
        "",
        "| Window | Output snapshot | Output tickers | With rows | Full | Partial | Zero rows | Failures |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, window in manifest["windows"].items():
        after = manifest["after_metrics"][label]
        coverage = window["coverage_summary"]
        lines.append(
            "| {label} | `{snapshot}` | {output_tickers} | {with_rows} | {full} | {partial} | {zero} | {failures} |".format(
                label=label,
                snapshot=window["output_snapshot"],
                output_tickers=after["output_ticker_count"],
                with_rows=after["target_with_rows_after"],
                full=coverage["full_coverage_count"],
                partial=coverage["partial_coverage_count"],
                zero=coverage["zero_rows_count"],
                failures=len(window["provider_or_network_failures"]),
            )
        )
    lines.extend(
        [
            "",
            "## Production Impact",
            "",
            "- No shared policy change.",
            "- No backtester or production adapter change.",
            "- Canonical OHLCV snapshots under `data/ohlcv` were not modified.",
            "- These snapshots are replay inputs for future core-expansion experiments only.",
            "",
        ]
    )
    return "\n".join(lines)


def _ticket(manifest: dict[str, Any], manifest_path: Path, artifact_path: Path) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": manifest["status"],
        "artifact": _repo_rel(artifact_path),
        "json": _repo_rel(manifest_path),
        "summary": "Observation/core/pilot universe OHLCV backfill snapshot set for future replay-only core expansion tests.",
        "next_step": manifest["next_step"],
    }


def _experiment_log_record(manifest: dict[str, Any], manifest_path: Path, artifact_path: Path) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": manifest["generated_at"],
        "status": "accepted",
        "hypothesis": (
            "Core-expansion alpha research is currently blocked by OHLCV coverage; building snapshot copies "
            "with current core, observation, and pilot tickers makes the next replay measurable without changing policy."
        ),
        "change_summary": "Copy canonical three-window OHLCV snapshots and append current universe tickers from cache/Yahoo where available.",
        "change_type": "measurement_repair",
        "component": "quant/experiments/exp_20260519_029_observation_universe_ohlcv_backfill.py",
        "changed_variable": "append_current_core_observation_pilot_universe_tickers_to_snapshot_copies",
        "parameters": {
            "network_enabled": manifest["network_enabled"],
            "target_ticker_count": len(manifest["tickers_requested"]),
            "data_source_priority": manifest["data_source_priority"],
            "source_universe_state": manifest["source_universe_state"]["path"],
        },
        "date_range": {
            label: window["date_range"] for label, window in manifest["windows"].items()
        },
        "before_metrics": manifest["before_metrics"],
        "after_metrics": manifest["after_metrics"],
        "delta_metrics": manifest["delta_metrics"],
        "aggregate_coverage": manifest["aggregate_coverage"],
        "expected_value_score_delta": None,
        "production_impact": manifest["production_impact"],
        "decision": manifest["decision"],
        "rejection_reason": None,
        "next_retry_requires": [
            "Provider/network failures must be resolved before using affected tickers in a strict all-current core-expansion replay."
        ]
        if manifest["aggregate_coverage"]["provider_or_network_failures"]
        else [],
        "related_files": [
            "quant/experiments/exp_20260519_029_observation_universe_ohlcv_backfill.py",
            _repo_rel(manifest_path),
            _repo_rel(artifact_path),
            "docs/experiment_log.jsonl",
        ],
        "notes": (
            "Data artifact only. Canonical snapshots are unchanged; zero-row slots are explicit and may correspond to recent listings."
        ),
    }


def persist_outputs(manifest: dict[str, Any], *, record_log: bool) -> dict[str, str]:
    manifest_path = (
        REPO_ROOT
        / "data"
        / "experiments"
        / EXPERIMENT_ID
        / "observation_universe_ohlcv_backfill.json"
    )
    artifact_path = (
        REPO_ROOT
        / "experiments"
        / "artifacts"
        / f"{EXPERIMENT_ID}_observation_universe_ohlcv_backfill.md"
    )
    log_path = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    ticket_path = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"

    _write_json(manifest_path, manifest)
    _write_json(log_path, manifest)
    _write_json(ticket_path, _ticket(manifest, manifest_path, artifact_path))
    _write_text(artifact_path, _artifact_markdown(manifest))

    if record_log:
        record = _experiment_log_record(manifest, manifest_path, artifact_path)
        experiment_log_path = REPO_ROOT / "docs" / "experiment_log.jsonl"
        record_line = json.dumps(record, ensure_ascii=False, sort_keys=True)
        existing_lines = []
        if experiment_log_path.exists():
            for line in experiment_log_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    existing_lines.append(line)
                    continue
                if payload.get("experiment_id") != EXPERIMENT_ID:
                    existing_lines.append(line)
        experiment_log_path.write_text(
            "\n".join([*existing_lines, record_line]) + "\n",
            encoding="utf-8",
        )

    return {
        "manifest": _repo_rel(manifest_path),
        "log": _repo_rel(log_path),
        "ticket": _repo_rel(ticket_path),
        "artifact": _repo_rel(artifact_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-network",
        action="store_true",
        help="Use only canonical snapshots and cached augmented snapshots.",
    )
    parser.add_argument(
        "--record-log",
        action="store_true",
        help="Append the final measurement-repair record to docs/experiment_log.jsonl.",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.15,
        help="Delay between Yahoo chart API requests when network is enabled.",
    )
    args = parser.parse_args()

    generated_at = _utc_now()
    manifest = build_backfill(
        no_network=args.no_network,
        sleep_seconds=max(args.sleep_seconds, 0.0),
        generated_at=generated_at,
    )
    outputs = persist_outputs(manifest, record_log=args.record_log)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": manifest["status"],
                "aggregate_coverage": manifest["aggregate_coverage"],
                "outputs": outputs,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
