"""exp-20260616-020: FINRA short-interest coverage registration and backfill.

Measurement repair. FINRA short-interest is a production-visible default-off
paper data source, but the central non-OHLCV coverage manifest did not record
its archive freshness and the local archive started at 2025-12-15. That makes
FINRA alpha searches structurally unreliable across the canonical old_thin and
mid_weak windows.

This runner:

* summarizes the current FINRA short-interest archive and source-cache coverage;
* attempts one broad-universe historical backfill for missing pre-2025-12
  biweekly settlement files;
* appends a data-source-level coverage row to data/non_ohlcv/coverage_manifest.jsonl;
* records that no entry, exit, ranking, sizing, risk, LLM, watchlist, or order
  behavior changed.

No JavaScript is used.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260616-020"
STEM = "finra_short_interest_coverage_and_backfill"
LANE = "measurement_repair"
CHANGED_VARIABLE = "finra_short_interest_coverage_manifest_registration_plus_historical_backfill"
OWNER = "alpha-search-automation"

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "quant"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import finra_iwm_paper_sleeve as finra
from experiment_registry import persist_self_registered_result
from non_ohlcv_coverage import append_manifest_record


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260616_020_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
COVERAGE_MANIFEST = REPO_ROOT / "data" / "non_ohlcv" / "coverage_manifest.jsonl"
BASELINE_JSON = REPO_ROOT / "data" / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
WAREHOUSE_JSON_PLACEHOLDER = REPO_ROOT / "data" / "experiments" / "exp-20260519-030" / "warehouse_main.sqlite"
ACTIVE_WAREHOUSE = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"

BACKFILL_START = date(2024, 9, 1)
BACKFILL_AS_OF = date(2025, 12, 14)
FETCH_TIMEOUT_SECONDS = 30

WINDOWS = {
    "old_thin": {"start": "2024-10-02", "end": "2025-04-22"},
    "mid_weak": {"start": "2025-04-23", "end": "2025-10-22"},
    "late_strong": {"start": "2025-10-23", "end": "2026-04-21"},
}

PRODUCTION_IMPACT = {
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": False,
    "default_off_attribution_only": True,
    "trade_enabled": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "alters_orders": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "parity_note": (
        "Data coverage and archive freshness only. FINRA/IWM and SEC FTD+FINRA "
        "candidate rules, ranks, notional, holds, cooldowns, exits, and live "
        "trade flags are unchanged."
    ),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def parse_day(value: Any) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def load_ticket() -> dict[str, Any]:
    payload = load_json(TICKET_JSON)
    return payload if isinstance(payload, dict) else {}


def baseline_metrics() -> dict[str, Any]:
    payload = load_json(BASELINE_JSON)
    doc = payload if isinstance(payload, dict) else {}
    windows = doc.get("windows") if isinstance(doc.get("windows"), list) else []
    totals = {
        "expected_value_score": 0.0,
        "total_pnl": 0.0,
        "trade_count": 0,
        "signals_generated": 0,
        "signals_survived": 0,
    }
    max_dd = None
    min_survival = None
    by_window: dict[str, Any] = {}
    for row in windows:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label") or "")
        by_window[label] = {
            "expected_value_score": row.get("expected_value_score"),
            "sharpe_daily": row.get("sharpe_daily"),
            "total_pnl": row.get("total_pnl"),
            "max_drawdown_pct": row.get("max_drawdown_pct"),
            "trade_count": row.get("trade_count"),
            "signals_generated": row.get("signals_generated"),
            "signals_survived": row.get("signals_survived"),
            "survival_rate": row.get("survival_rate"),
        }
        totals["expected_value_score"] += float(row.get("expected_value_score") or 0.0)
        totals["total_pnl"] += float(row.get("total_pnl") or 0.0)
        totals["trade_count"] += int(row.get("trade_count") or 0)
        totals["signals_generated"] += int(row.get("signals_generated") or 0)
        totals["signals_survived"] += int(row.get("signals_survived") or 0)
        dd = row.get("max_drawdown_pct")
        if isinstance(dd, (int, float)):
            max_dd = dd if max_dd is None else max(max_dd, dd)
        survival = row.get("survival_rate")
        if isinstance(survival, (int, float)):
            min_survival = survival if min_survival is None else min(min_survival, survival)
    return {
        "baseline_result_file": repo_path(BASELINE_JSON),
        "aggregate_expected_value_score": round(totals["expected_value_score"], 4),
        "aggregate_total_pnl": round(totals["total_pnl"], 2),
        "aggregate_trade_count": totals["trade_count"],
        "aggregate_signals_generated": totals["signals_generated"],
        "aggregate_signals_survived": totals["signals_survived"],
        "minimum_survival_rate": min_survival,
        "worst_window_max_drawdown_pct": max_dd,
        "windows": by_window,
    }


def load_broad_universe() -> dict[str, Any]:
    path = ACTIVE_WAREHOUSE if ACTIVE_WAREHOUSE.exists() and ACTIVE_WAREHOUSE.stat().st_size else WAREHOUSE_JSON_PLACEHOLDER
    tickers: list[str] = []
    error = None
    try:
        con = sqlite3.connect(path)
        cur = con.cursor()
        table_count = cur.execute(
            "select count(*) from sqlite_master where type='table' and name='coverage_summary'"
        ).fetchone()[0]
        if table_count:
            tickers = [
                str(row[0]).upper()
                for row in cur.execute(
                    "select ticker from coverage_summary where all_windows_full_liquid=1 order by ticker"
                ).fetchall()
                if row and row[0]
            ]
        con.close()
    except Exception as exc:  # noqa: BLE001 - artifact should record the data gap.
        error = str(exc)
    existing = sorted({str(row.get("ticker") or "").upper() for row in finra.load_finra_short_interest_rows() if row.get("ticker")})
    if not tickers:
        tickers = existing
    return {
        "warehouse_path": repo_path(path),
        "placeholder_path": repo_path(WAREHOUSE_JSON_PLACEHOLDER),
        "active_warehouse_path": repo_path(ACTIVE_WAREHOUSE),
        "ticker_count": len(tickers),
        "tickers": tickers,
        "fallback_used": path == WAREHOUSE_JSON_PLACEHOLDER or not tickers,
        "error": error,
    }


def archive_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    publications = sorted(day for day in (parse_day(row.get("publication_date")) for row in rows) if day)
    settlements = sorted(day for day in (parse_day(row.get("settlement_date")) for row in rows) if day)
    tickers = sorted({str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")})
    return {
        "row_count": len(rows),
        "ticker_count": len(tickers),
        "sample_tickers": tickers[:20],
        "publication_date_min": publications[0].isoformat() if publications else None,
        "publication_date_max": publications[-1].isoformat() if publications else None,
        "settlement_date_min": settlements[0].isoformat() if settlements else None,
        "settlement_date_max": settlements[-1].isoformat() if settlements else None,
        "settlement_count": len(settlements),
        "unique_settlement_count": len(set(settlements)),
    }


def expected_settlements_for_window(start: date, end: date) -> list[date]:
    # Include settlements whose official publication date lands in the window.
    first_candidate = start - timedelta(days=40)
    last_candidate = end
    out = []
    for settlement in finra.settlement_dates(first_candidate, last_candidate):
        publication, _method = finra.publication_date_for(settlement)
        if start <= publication <= end:
            out.append(settlement)
    return out


def window_coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    available_settlements = {
        parse_day(row.get("settlement_date"))
        for row in rows
        if parse_day(row.get("settlement_date")) is not None
    }
    out: dict[str, Any] = {}
    for label, spec in WINDOWS.items():
        start = parse_day(spec["start"])
        end = parse_day(spec["end"])
        assert start is not None and end is not None
        expected = expected_settlements_for_window(start, end)
        available = sorted(day for day in expected if day in available_settlements)
        missing = sorted(day for day in expected if day not in available_settlements)
        published_rows = [
            row
            for row in rows
            if (day := parse_day(row.get("publication_date"))) is not None
            and start <= day <= end
        ]
        out[label] = {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "expected_settlement_count": len(expected),
            "available_settlement_count": len(available),
            "coverage_fraction": round(len(available) / len(expected), 4) if expected else 0.0,
            "available_settlements": [day.isoformat() for day in available],
            "missing_settlements": [day.isoformat() for day in missing],
            "published_row_count": len(published_rows),
            "published_ticker_count": len({str(row.get("ticker") or "").upper() for row in published_rows}),
            "status": "complete" if expected and not missing else "missing_history",
        }
    return out


def source_cache_manifest(tickers: set[str]) -> list[dict[str, Any]]:
    cache_root = finra.DEFAULT_FINRA_ROWS_PATH.parent / "source_cache"
    records: list[dict[str, Any]] = []
    wanted = {str(ticker).upper() for ticker in tickers if ticker}
    for path in sorted(cache_root.glob("shrt*.csv")):
        token = path.stem.replace("shrt", "")
        if len(token) != 8 or not token.isdigit():
            continue
        settlement = date(int(token[:4]), int(token[4:6]), int(token[6:8]))
        publication, method = finra.publication_date_for(settlement)
        matched = 0
        total = 0
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle, delimiter="|")
                for raw in reader:
                    total += 1
                    ticker = str(raw.get("symbolCode") or "").upper().strip()
                    if ticker in wanted:
                        matched += 1
            status_code: int | str = "cached"
            error = None
        except Exception as exc:  # noqa: BLE001 - coverage artifact records parse errors.
            status_code = "cache_parse_error"
            error = str(exc)
        row = {
            "settlement_date": settlement.isoformat(),
            "publication_date": publication.isoformat(),
            "publication_date_method": method,
            "url": finra.FINRA_CSV_URL.format(yyyymmdd=token),
            "status_code": status_code,
            "matched_rows": matched,
            "total_rows": total,
            "source": "cache_manifest",
            "cache_path": str(path),
        }
        if error:
            row["error"] = error
        records.append(row)
    return records


def merge_file_records(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for group in groups:
        for row in group:
            if not isinstance(row, dict):
                continue
            key = (str(row.get("settlement_date") or ""), str(row.get("url") or ""))
            prior = merged.get(key)
            if prior is None:
                merged[key] = dict(row)
                continue
            prior_ok = prior.get("status_code") in (200, "cached")
            row_ok = row.get("status_code") in (200, "cached")
            if row_ok and not prior_ok:
                merged[key] = dict(row)
    return sorted(
        merged.values(),
        key=lambda row: (str(row.get("settlement_date") or ""), str(row.get("url") or "")),
    )


def merge_rows(existing_rows: list[dict[str, Any]], new_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for row in finra._normalise_finra_rows(existing_rows):
        merged[(str(row.get("ticker")), str(row.get("settlement_date")))] = row
    added = 0
    for row in finra._normalise_finra_rows(new_rows):
        key = (str(row.get("ticker")), str(row.get("settlement_date")))
        if key not in merged:
            added += 1
        merged[key] = row
    return finra._normalise_finra_rows(list(merged.values())), added


def fetch_historical_backfill(tickers: set[str]) -> dict[str, Any]:
    lookback_days = (BACKFILL_AS_OF - BACKFILL_START).days + 1
    try:
        rows, files = finra.fetch_finra_short_interest_rows(
            tickers=tickers,
            as_of=BACKFILL_AS_OF.isoformat(),
            lookback_days=lookback_days,
            timeout=FETCH_TIMEOUT_SECONDS,
        )
        error = None
    except Exception as exc:  # noqa: BLE001 - runner should close with evidence.
        rows = []
        files = []
        error = str(exc)
    files_ok = [row for row in files if row.get("status_code") in (200, "cached")]
    files_failed = [row for row in files if row.get("status_code") not in (200, "cached")]
    return {
        "requested_start": BACKFILL_START.isoformat(),
        "requested_as_of": BACKFILL_AS_OF.isoformat(),
        "lookback_days": lookback_days,
        "timeout_seconds": FETCH_TIMEOUT_SECONDS,
        "rows": rows,
        "files": files,
        "files_attempted": len(files),
        "files_ok": len(files_ok),
        "files_failed": len(files_failed),
        "failure_examples": files_failed[:10],
        "error": error,
    }


def coverage_manifest_record(
    *,
    rows: list[dict[str, Any]],
    file_records: list[dict[str, Any]],
    coverage: dict[str, Any],
    backfill: dict[str, Any],
    appended_from_experiment: str,
) -> dict[str, Any]:
    summary = archive_summary(rows)
    cache_files = [row for row in file_records if row.get("status_code") in (200, "cached")]
    failures = [row for row in file_records if row.get("status_code") not in (200, "cached")]
    complete = all(row.get("status") == "complete" for row in coverage.values())
    status = "complete" if complete else "partial"
    return {
        "schema_version": 2,
        "record_type": "data_source_coverage",
        "source_name": "finra_short_interest",
        "experiment_id": appended_from_experiment,
        "trade_date": "2026-06-16",
        "date_key": "20260616",
        "mode": "measurement_repair",
        "generated_at": utc_now(),
        "status": status,
        "artifact_status": {
            "finra_short_interest_rows": {
                "path": repo_path(finra.DEFAULT_FINRA_ROWS_PATH),
                "kind": "json",
                "required": False,
                "status": "present" if rows else "missing",
                "row_count": len(rows),
            },
            "finra_short_interest_source_files": {
                "path": repo_path(finra.DEFAULT_FINRA_FILES_PATH),
                "kind": "json",
                "required": False,
                "status": "present" if file_records else "missing",
                "row_count": len(file_records),
            },
            "finra_short_interest_source_cache": {
                "path": repo_path(finra.DEFAULT_FINRA_ROWS_PATH.parent / "source_cache"),
                "kind": "csv_dir",
                "required": False,
                "status": "present" if cache_files else "missing",
                "row_count": len(cache_files),
            },
        },
        "row_counts": {
            "finra_short_interest_rows": len(rows),
            "finra_source_file_records": len(file_records),
            "finra_source_files_ok_or_cached": len(cache_files),
            "finra_source_files_failed": len(failures),
        },
        "source_watermarks": {
            "publication_date_max": summary["publication_date_max"],
            "settlement_date_max": summary["settlement_date_max"],
            "updated_at": utc_now(),
        },
        "pit_status": {
            "overall": "finra_historical_coverage_complete" if complete else "finra_historical_coverage_partial",
            "canonical_window_coverage": coverage,
            "publication_lag_policy": "FINRA schedule overrides or seventh business day after settlement",
            "pit_safe": True,
        },
        "finra_archive_summary": summary,
        "historical_backfill_attempt": {
            key: value
            for key, value in backfill.items()
            if key not in {"rows", "files"}
        },
        "errors": failures[:20],
        "required_missing": [],
        "invalid_required": [],
        "production_impact": PRODUCTION_IMPACT,
    }


def latest_exp020_manifest_status() -> str | None:
    """Latest recorded status of this source's manifest row, or None.

    The manifest is append-only with latest-wins semantics, so a re-run that
    materially improves coverage (e.g. a network-blocked backfill that later
    succeeds) should append a fresh record reflecting the new status instead of
    leaving the stale partial row as the visible truth.
    """
    if not COVERAGE_MANIFEST.exists():
        return None
    latest: str | None = None
    for line in COVERAGE_MANIFEST.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("experiment_id") == EXPERIMENT_ID and row.get("source_name") == "finra_short_interest":
            latest = str(row.get("status"))
    return latest


def append_coverage_record_once(record: dict[str, Any]) -> dict[str, Any]:
    prior_status = latest_exp020_manifest_status()
    if prior_status is not None and prior_status == record.get("status"):
        return {"appended": False, "path": repo_path(COVERAGE_MANIFEST), "reason": "record_already_current"}
    append_manifest_record(record, non_ohlcv_dir=REPO_ROOT / "data" / "non_ohlcv")
    reason = "appended" if prior_status is None else "appended_status_change"
    return {"appended": True, "path": repo_path(COVERAGE_MANIFEST), "reason": reason}


def existing_experiment_log_ids() -> set[str]:
    ids: set[str] = set()
    if not EXPERIMENT_LOG.exists():
        return ids
    for line in EXPERIMENT_LOG.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("experiment_id"):
            ids.add(str(row["experiment_id"]))
    return ids


def append_experiment_log_once(record: dict[str, Any]) -> bool:
    if EXPERIMENT_ID in existing_experiment_log_ids():
        return False
    with EXPERIMENT_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return True


def update_card(record: dict[str, Any]) -> None:
    gate = record["gate4"]
    readiness = record["readiness"]
    text = f"""---
experiment_id: "{EXPERIMENT_ID}"
status: "{record['status']}"
lane: "{LANE}"
change_type: "identity_or_measurement_repair"
mechanism_family: "data_accumulation_integrity"
trial_family: "identity_or_measurement_repair"
trial_variant_id: "{EXPERIMENT_ID}"
changed_variable: "{CHANGED_VARIABLE}"
created_at: "{load_ticket().get('created_at') or record['timestamp']}"
completed_at: "{record['timestamp']}"
tags:
  - "measurement_repair"
  - "{record['status']}"
  - "finra_short_interest"
---

# Experiment Card: {EXPERIMENT_ID}

## Summary

Registered FINRA short-interest archive freshness in the central non-OHLCV coverage manifest and attempted a one-time historical backfill for the missing canonical windows.

## Result

- Decision: `{record['decision']}`
- Coverage manifest: `{record['coverage_manifest_append']['path']}` ({record['coverage_manifest_append']['reason']})
- Rows after repair: `{record['finra_archive_after']['row_count']}`
- Publication range after repair: `{record['finra_archive_after']['publication_date_min']}` to `{record['finra_archive_after']['publication_date_max']}`
- Gate 4: `{gate['reason']}`
- Readiness: `{readiness['status']}`

## Blocked Alpha Hypothesis

{record['alpha_hypothesis_blocked']['hypothesis']}

## Post-Run Reflection

- Why: {record['post_run_reflection']['why_result_happened']}
- No near retry: {record['post_run_reflection']['forbidden_near_neighbor_retry']}
- New evidence required: {record['post_run_reflection']['new_evidence_required']}

## Reproduce

```powershell
.\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260616_020_finra_short_interest_coverage_and_backfill.py
```
"""
    CARD_MD.write_text(text, encoding="utf-8")


def sha256_file(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def update_manifest(record: dict[str, Any]) -> None:
    files = {}
    for name, path in {
        "runner": Path(__file__),
        "artifact": OUT_JSON,
        "log": LOG_JSON,
        "ticket": TICKET_JSON,
        "card": CARD_MD,
        "coverage_manifest": COVERAGE_MANIFEST,
        "finra_rows": finra.DEFAULT_FINRA_ROWS_PATH,
        "finra_source_files": finra.DEFAULT_FINRA_FILES_PATH,
    }.items():
        files[name] = {
            "path": repo_path(path),
            "exists": path.exists(),
            "sha256": sha256_file(path),
        }
    payload = {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_revision_manifest",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": utc_now(),
        "decision": record["decision"],
        "files": files,
        "coverage_manifest_append": record["coverage_manifest_append"],
        "finra_archive_after": record["finra_archive_after"],
    }
    write_json(MANIFEST_JSON, payload)


def build_record() -> dict[str, Any]:
    ticket = load_ticket()
    before_rows = finra.load_finra_short_interest_rows()
    before_summary = archive_summary(before_rows)
    universe = load_broad_universe()
    tickers = set(universe["tickers"])

    backfill = fetch_historical_backfill(tickers)
    merged_rows, added_rows = merge_rows(before_rows, backfill["rows"])
    cache_records = source_cache_manifest(tickers)
    existing_source_files_payload = load_json(finra.DEFAULT_FINRA_FILES_PATH)
    existing_source_files = (
        existing_source_files_payload.get("files")
        if isinstance(existing_source_files_payload, dict)
        and isinstance(existing_source_files_payload.get("files"), list)
        else []
    )
    file_records = merge_file_records(existing_source_files, cache_records, backfill["files"])
    # Persist even when no new rows were fetched so source_files.json becomes a
    # durable cache manifest rather than only the last refresh attempt.
    finra.save_finra_short_interest_archive(rows=merged_rows, files=file_records)

    after_rows = finra.load_finra_short_interest_rows()
    after_summary = archive_summary(after_rows)
    coverage = window_coverage(after_rows)
    coverage_record = coverage_manifest_record(
        rows=after_rows,
        file_records=file_records,
        coverage=coverage,
        backfill=backfill,
        appended_from_experiment=EXPERIMENT_ID,
    )
    append_result = append_coverage_record_once(coverage_record)

    all_windows_complete = all(row.get("status") == "complete" for row in coverage.values())
    if all_windows_complete:
        backfill_status = "historical_backfill_complete"
    elif added_rows > 0:
        backfill_status = "historical_backfill_partial"
    else:
        backfill_status = "historical_backfill_blocked_or_no_new_rows"

    decision = f"accepted_measurement_repair_finra_coverage_registered_{backfill_status}"
    now = utc_now()
    metrics = baseline_metrics()
    record = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": "accepted",
        "lane": LANE,
        "decision": decision,
        "hypothesis": ticket.get("hypothesis")
        or (
            "Register FINRA short-interest archive coverage centrally and attempt "
            "historical backfill so future short-interest alpha tests can see "
            "whether canonical-window coverage is real or structurally missing."
        ),
        "alpha_hypothesis_blocked": {
            "category": "candidate_pool",
            "hypothesis": (
                "A PIT FINRA short-interest borrow-pressure or covering-relief "
                "field could improve candidate-pool replacement value, but this "
                "cannot be evaluated credibly while old_thin and mid_weak have "
                "no official short-interest rows in the local archive."
            ),
            "blocked_reason": (
                "FINRA archive coverage is a direct Gate 2 measurement blocker "
                "for any three-window FINRA alpha comparison."
            ),
        },
        "change_summary": (
            "Registered FINRA short-interest as a data-source-level coverage "
            "record in coverage_manifest.jsonl, attempted a broad-universe "
            "historical backfill for pre-2025-12 biweekly files, and persisted "
            "a source-cache manifest without changing strategy behavior."
        ),
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "measurement_repair",
        "mechanism_family": "data_accumulation_integrity",
        "trial_family": "identity_or_measurement_repair",
        "trial_variant_id": EXPERIMENT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": [
            "finra archive coverage audit",
            "broad universe historical backfill attempt",
            "central coverage manifest append",
            "source cache manifest normalization",
            "closeout artifact",
        ],
        "prior_trial_count": 1,
        "nearby_prior_experiments": [
            "exp-20260612-003",
            "exp-20260613-029",
            "exp-20260529-018",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "measurement_surface_repair",
        "component": "quant/experiments/exp_20260616_020_finra_short_interest_coverage_and_backfill.py",
        "prediction": ticket.get("prediction"),
        "calibration": {
            "actual_decision": decision,
            "actual_success": 1,
            "predicted_success_probability": None,
            "brier_score": None,
            "predicted_failure_modes": [],
            "realized_failure_mode": None if all_windows_complete else backfill_status,
            "predicted_failure_mode_hit": None,
            "surprise_note": (
                "The central manifest gap was repairable locally; historical "
                "FINRA completeness depends on whether the official CDN returns "
                "older settlement files during the backfill attempt."
            ),
        },
        "before_metrics": metrics,
        "after_metrics": metrics,
        "delta_metrics": {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "trade_count": 0,
            "signals_generated": 0,
            "signals_survived": 0,
            "survival_rate": 0.0,
        },
        "baseline_result_file": repo_path(BASELINE_JSON),
        "finra_archive_before": before_summary,
        "finra_archive_after": after_summary,
        "finra_rows_added": added_rows,
        "broad_universe": {
            key: value for key, value in universe.items() if key != "tickers"
        },
        "canonical_window_coverage": coverage,
        "historical_backfill_attempt": {
            key: value for key, value in backfill.items() if key not in {"rows", "files"}
        },
        "source_cache": {
            "cache_file_count": len(cache_records),
            "source_file_record_count": len(file_records),
            "source_files_ok_or_cached": sum(
                1 for row in file_records if row.get("status_code") in (200, "cached")
            ),
            "source_files_failed": sum(
                1 for row in file_records if row.get("status_code") not in (200, "cached")
            ),
        },
        "coverage_manifest_record": coverage_record,
        "coverage_manifest_append": append_result,
        "readiness": {
            "status": "finra_historical_alpha_ready" if all_windows_complete else "finra_alpha_still_coverage_blocked",
            "historical_backfill_status": backfill_status,
            "ready_for_three_window_finra_alpha": all_windows_complete,
            "next_step": (
                "Use this coverage record as the gate before any FINRA alpha "
                "retry. If old/mid coverage remains incomplete, do not run "
                "short-interest alpha on the canonical windows until official "
                "older files are acquired or a different PIT borrow/availability "
                "source covers all windows."
            ),
        },
        "gate2": {
            "entry_date_target_price_minimum_check": "not_applicable_no_strategy_positions_changed",
            "finra_runtime_fields_checked": [
                "ticker",
                "settlement_date",
                "publication_date",
                "usable_trade_date",
                "short_interest",
                "previous_short_interest",
                "short_interest_change_pct",
                "days_to_cover",
            ],
            "canonical_window_coverage_checked": True,
        },
        "gate3": {
            "survival_rate": metrics.get("minimum_survival_rate"),
            "reason": "No filter or strategy behavior changed; canonical baseline survival unchanged.",
        },
        "gate4": {
            "applicable": False,
            "reason": "Measurement repair only; no buy, sell, filter, rank, sizing, exit, risk, LLM, watchlist, or order behavior changed.",
            "baseline_unchanged": True,
        },
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": {
            "why_result_happened": (
                "The FINRA sleeve already persisted rows and source files, but "
                "the central coverage manifest only tracked daily non-OHLCV SEC "
                "and event artifacts. Adding a data-source-level row makes the "
                "short-interest archive's settlement and publication range visible "
                "to future agents before they start another FINRA alpha test."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry FINRA short-pressure, covering-relief, IWM confirmation, "
                "FTD+FINRA, allocator insertion, threshold, top-N, cooldown, hold, or "
                "notional variants while old_thin or mid_weak FINRA coverage is missing."
            ),
            "new_evidence_required": (
                "A valid FINRA alpha retry needs central coverage showing official "
                "publication-date-safe short-interest rows across all canonical "
                "windows, or a materially different PIT borrow-cost, hard-to-borrow, "
                "loan availability, or forward replacement-value data source."
            ),
        },
        "next_retry_requires": [
            "official FINRA older settlement files covering old_thin and mid_weak",
            "or a materially different PIT borrow availability/cost source",
            "or forward replacement-value rows independent of the missing historical windows",
        ],
        "related_files": [
            repo_path(Path(__file__)),
            repo_path(OUT_JSON),
            repo_path(LOG_JSON),
            repo_path(COVERAGE_MANIFEST),
            repo_path(finra.DEFAULT_FINRA_ROWS_PATH),
            repo_path(finra.DEFAULT_FINRA_FILES_PATH),
            repo_path(TICKET_JSON),
            repo_path(MANIFEST_JSON),
            repo_path(CARD_MD),
        ],
        "notes": (
            "No strategy behavior changed. The repaired surface is measurement "
            "visibility and source-cache persistence only."
        ),
    }
    return record


def close_record(record: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_json(OUT_JSON, record)
    write_json(LOG_JSON, record)
    appended_log = append_experiment_log_once(record)
    record["experiment_log_appended"] = appended_log
    write_json(OUT_JSON, record)
    write_json(LOG_JSON, record)
    update_card(record)
    update_manifest(record)

    ticket = load_ticket()
    fields = {
        key: ticket.get(key)
        for key in (
            "experiment_uid",
            "hub_identity",
            "owner",
            "hypothesis",
            "change_type",
            "mechanism_family",
            "trial_family",
            "trial_variant_id",
            "single_causal_variable",
            "changed_variable",
            "causal_components",
            "prior_trial_count",
            "nearby_prior_experiments",
            "multiple_testing_risk_bucket",
            "new_evidence_type",
            "baseline_result_file",
            "allowed_write_scope",
            "must_not_touch",
            "locked_variables",
            "evaluation_windows",
            "acceptance_rule",
            "ticket_file",
            "card_file",
            "revision_manifest_file",
            "created_at",
            "claimed_at",
        )
    }
    fields.update(
        {
            "change_type": record["change_type"],
            "mechanism_family": record["mechanism_family"],
            "trial_family": record["trial_family"],
            "trial_variant_id": record["trial_variant_id"],
            "single_causal_variable": record["single_causal_variable"],
            "changed_variable": record["changed_variable"],
            "decision": record["decision"],
            "lane": LANE,
            "owner": OWNER,
        }
    )
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=record.get("prediction"),
        result={
            "decision": record["decision"],
            "artifact": repo_path(OUT_JSON),
            "log": repo_path(LOG_JSON),
            "coverage_manifest": repo_path(COVERAGE_MANIFEST),
            "finra_rows_after": record["finra_archive_after"]["row_count"],
            "finra_publication_date_min": record["finra_archive_after"]["publication_date_min"],
            "finra_publication_date_max": record["finra_archive_after"]["publication_date_max"],
            "finra_rows_added": record["finra_rows_added"],
            "ready_for_three_window_finra_alpha": record["readiness"]["ready_for_three_window_finra_alpha"],
            "accepted": True,
        },
        status=record["status"],
        fields=fields,
    )
    # persist_self_registered_result writes the ticket before the final manifest
    # update exists; update result fields on the materialized ticket afterward.
    ticket = load_ticket()
    ticket.update(
        {
            "status": record["status"],
            "completed_at": record["timestamp"],
            "result": {
                "decision": record["decision"],
                "artifact": repo_path(OUT_JSON),
                "log": repo_path(LOG_JSON),
                "coverage_manifest": repo_path(COVERAGE_MANIFEST),
                "ready_for_three_window_finra_alpha": record["readiness"][
                    "ready_for_three_window_finra_alpha"
                ],
            },
        }
    )
    write_json(TICKET_JSON, ticket)
    update_manifest(record)


def main() -> int:
    record = build_record()
    close_record(record)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": record["decision"],
                "finra_rows_added": record["finra_rows_added"],
                "finra_archive_after": record["finra_archive_after"],
                "canonical_window_coverage": record["canonical_window_coverage"],
                "coverage_manifest_append": record["coverage_manifest_append"],
                "readiness": record["readiness"],
                "production_impact": PRODUCTION_IMPACT,
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
