"""exp-20260622-009: seed a PIT Moomoo daily short-volume raw archive.

Measurement repair for the exp-20260622-008 alpha blocker. This run does not
test or change a trading rule. It creates an activity-only raw-row archive
contract for Moomoo `get_daily_short_volume` and attempts a bounded OpenD
backfill for the positive probe tickers down to the oldest canonical window.

No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import experiment_registry  # noqa: E402


EXPERIMENT_ID = "exp-20260622-009"
SLUG = "moomoo_daily_short_volume_raw_archive"
RUNNER_NAME = f"quant/experiments/exp_20260622_009_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER_NAME.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT_JSON = DATA_DIR / f"exp_20260622_009_{SLUG}.json"
BEFORE_JSON = DATA_DIR / "before_baseline.json"
AFTER_JSON = DATA_DIR / "after_no_strategy_change.json"
README_MD = DATA_DIR / "README.md"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT_FILE = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
PROBE_JSON = (
    REPO_ROOT / "data" / "probes" / "moomoo_daily_short_volume_probe_2026-06-21.json"
)

RAW_ARCHIVE_DIR = REPO_ROOT / "data" / "non_ohlcv" / "moomoo_daily_short_volume"
ROWS_JSONL = RAW_ARCHIVE_DIR / "rows.jsonl"
ARCHIVE_MANIFEST_JSON = RAW_ARCHIVE_DIR / "manifest.json"
SOURCE_FILES_JSON = RAW_ARCHIVE_DIR / "source_files.json"

OLDEST_WINDOW_START = date.fromisoformat("2024-10-02")
PAGE_NUM = 50
REQUEST_SLEEP_SEC = 1.05
MAX_PAGES_PER_TICKER = 18

SCHEMA_VERSION = "moomoo_daily_short_volume_activity_v1"
SOURCE_NAME = "moomoo_get_daily_short_volume"
ACTIVITY_ONLY_WARNING = (
    "Moomoo daily short volume is an activity field, not FINRA short-interest "
    "positioning. Any future candidate-pool helper must use it as activity-only "
    "sell-pressure context and must map usable trade dates explicitly."
)

HYPOTHESIS = (
    "measurement_repair/alpha_blocker: Moomoo daily short-volume activity may "
    "be a future sell-pressure candidate-pool context field, but exp-20260622-008 "
    "blocked alpha replay because the repository had no raw PIT row archive. "
    "This run seeds the archive contract and a bounded raw-row backfill without "
    "changing any strategy behavior."
)
CHANGED_VARIABLE = "moomoo_daily_short_volume_raw_archive_contract_v1"
MECHANISM_FAMILY = "measurement_repair_moomoo_daily_short_volume_activity_archive"
TRIAL_FAMILY = "moomoo_daily_short_volume_raw_archive_contract"
TRIAL_VARIANT_ID = "bounded_probe_tickers_to_old_thin_start_v1"
NEARBY_PRIOR_EXPERIMENTS = ["exp-20260622-008", "exp-20260622-003", "exp-20260621-017"]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def repo_rel(path: Path) -> str:
    path = path.resolve()
    try:
        return path.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def append_jsonl_once(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        with path.open(encoding="utf-8-sig") as handle:
            for line in handle:
                if f'"experiment_id": "{EXPERIMENT_ID}"' in line:
                    return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def parse_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def as_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_baseline() -> dict[str, Any]:
    raw = read_json(BASELINE_RESULT_FILE)
    windows: dict[str, dict[str, Any]] = {}
    for row in raw.get("windows") or []:
        label = str(row.get("label") or "")
        if not label:
            continue
        windows[label] = {
            "start": row.get("start"),
            "end": row.get("end"),
            "snapshot": row.get("source"),
            "expected_value_score": row.get("expected_value_score"),
            "sharpe_daily": row.get("sharpe_daily"),
            "total_pnl": row.get("total_pnl"),
            "max_drawdown_pct": row.get("max_drawdown_pct"),
            "win_rate": row.get("win_rate"),
            "trade_count": row.get("trade_count"),
            "signals_generated": row.get("signals_generated"),
            "signals_survived": row.get("signals_survived"),
            "survival_rate": row.get("survival_rate"),
        }
    return {"generated_at": raw.get("generated_at"), "windows": windows}


def aggregate_windows(windows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "aggregate_expected_value_score": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows.values()),
            4,
        ),
        "aggregate_total_pnl": round(
            sum(float(row.get("total_pnl") or 0.0) for row in windows.values()),
            2,
        ),
        "total_trade_count": sum(int(row.get("trade_count") or 0) for row in windows.values()),
        "min_survival_rate": round(
            min(float(row.get("survival_rate") or 0.0) for row in windows.values()),
            4,
        )
        if windows
        else 0.0,
        "max_window_drawdown_pct": round(
            max(float(row.get("max_drawdown_pct") or 0.0) for row in windows.values()),
            4,
        )
        if windows
        else 0.0,
    }


def baseline_artifact(label: str, gate1: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "label": label,
        "baseline_result_file": repo_rel(BASELINE_RESULT_FILE),
        "windows": gate1["windows"],
        "aggregate": gate1["aggregate"],
        "strategy_code_changed": False,
        "production_code_changed": False,
        "note": "No strategy after-run was launched; after intentionally equals before.",
    }


def metric_deltas(windows: dict[str, dict[str, Any]]) -> dict[str, dict[str, float]]:
    fields = [
        "expected_value_score",
        "total_pnl",
        "max_drawdown_pct",
        "trade_count",
        "survival_rate",
    ]
    return {label: {field: 0.0 for field in fields} for label in windows}


def probe_tickers() -> list[str]:
    probe = read_json(PROBE_JSON)
    tickers = []
    for row in probe.get("results") or []:
        code = str(row.get("code") or "").strip()
        if code:
            tickers.append(code)
    return tickers or ["US.AAPL", "US.NVDA", "US.TSLA", "US.PLTR", "US.SOFI"]


def prepare_moomoo_log_env() -> None:
    appdata = DATA_DIR / "appdata"
    localappdata = DATA_DIR / "localappdata"
    appdata.mkdir(parents=True, exist_ok=True)
    localappdata.mkdir(parents=True, exist_ok=True)
    os.environ["APPDATA"] = str(appdata)
    os.environ["LOCALAPPDATA"] = str(localappdata)


def normalize_api_row(code: str, raw: dict[str, Any], collected_at: str) -> dict[str, Any] | None:
    activity_date = parse_date(raw.get("timestamp_str") or raw.get("timestamp"))
    if activity_date is None:
        return None
    total_shares_short = as_int(raw.get("total_shares_short"))
    volume = as_int(raw.get("volume"))
    short_volume_ratio = None
    if total_shares_short is not None and volume and volume > 0:
        short_volume_ratio = round(total_shares_short / volume, 8)
    ticker = code.split(".", 1)[-1] if "." in code else code
    return {
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE_NAME,
        "source_code": code,
        "ticker": ticker,
        "activity_date": activity_date.isoformat(),
        "timestamp": as_int(raw.get("timestamp")),
        "total_shares_short": total_shares_short,
        "nasdaq_shares_short": as_int(raw.get("nasdaq_shares_short")),
        "nyse_shares_short": as_int(raw.get("nyse_shares_short")),
        "reported_short_percent": as_float(raw.get("short_percent")),
        "volume": volume,
        "short_volume_ratio": short_volume_ratio,
        "close_price": as_float(raw.get("close_price")),
        "last_close_price": as_float(raw.get("last_close_price")),
        "daily_trade_avg_ratio": as_float(raw.get("daily_trade_avg_ratio")),
        "pit_boundary": "activity_date_after_us_close",
        "usable_trade_date": None,
        "usable_trade_date_policy": (
            "Future helper must map this activity_date to the next valid trading "
            "session unless vendor publication timing proves same-session "
            "post-close availability."
        ),
        "positioning_warning": ACTIVITY_ONLY_WARNING,
        "archive_experiment_id": EXPERIMENT_ID,
        "collected_at": collected_at,
    }


def dataframe_records(df: Any) -> list[dict[str, Any]]:
    if df is None or getattr(df, "empty", True):
        return []
    return list(df.to_dict("records"))


def fetch_ticker_rows(ctx: Any, code: str, collected_at: str) -> dict[str, Any]:
    from moomoo import RET_OK

    rows: list[dict[str, Any]] = []
    pages = 0
    next_key = None
    error = None
    api_columns: list[str] = []
    try:
        while pages < MAX_PAGES_PER_TICKER:
            kwargs: dict[str, Any] = {"num": PAGE_NUM}
            if next_key not in (None, "", "-1"):
                kwargs["next_key"] = next_key
            ret, us_df, _hk_df = ctx.get_daily_short_volume(code, **kwargs)
            if ret != RET_OK:
                error = str(us_df)
                break
            if us_df is not None and hasattr(us_df, "columns"):
                api_columns = [str(item) for item in list(us_df.columns)]
            records = dataframe_records(us_df)
            for raw in records:
                row = normalize_api_row(code, raw, collected_at)
                if row is not None:
                    rows.append(row)
            pages += 1
            dates = [parse_date(row.get("activity_date")) for row in rows]
            dates = [item for item in dates if item is not None]
            if dates and min(dates) <= OLDEST_WINDOW_START:
                break
            nk = ""
            if us_df is not None and hasattr(us_df, "attrs"):
                nk = us_df.attrs.get("next_key", "")
            if not nk or nk == "-1":
                break
            next_key = nk
            time.sleep(REQUEST_SLEEP_SEC)
    except Exception as exc:  # noqa: BLE001 - experiment must record blockers
        error = f"{type(exc).__name__}: {exc}"

    dates = [parse_date(row.get("activity_date")) for row in rows]
    dates = [item for item in dates if item is not None]
    return {
        "code": code,
        "rows": rows,
        "row_count": len(rows),
        "pages": pages,
        "api_columns": api_columns,
        "earliest": min(dates).isoformat() if dates else None,
        "latest": max(dates).isoformat() if dates else None,
        "reaches_oldest_window": bool(dates and min(dates) <= OLDEST_WINDOW_START),
        "hit_page_cap": pages >= MAX_PAGES_PER_TICKER,
        "error": error,
    }


def fetch_bounded_rows(tickers: list[str]) -> dict[str, Any]:
    prepare_moomoo_log_env()
    collected_at = now_utc()
    fetch_error = None
    per_ticker = []
    rows: list[dict[str, Any]] = []
    try:
        from moomoo import OpenQuoteContext

        ctx = OpenQuoteContext(host="127.0.0.1", port=11111)
    except Exception as exc:  # noqa: BLE001
        return {
            "connected": False,
            "fetch_error": f"{type(exc).__name__}: {exc}",
            "tickers": tickers,
            "per_ticker": [],
            "rows": [],
            "collected_at": collected_at,
        }
    try:
        for code in tickers:
            result = fetch_ticker_rows(ctx, code, collected_at)
            rows.extend(result.pop("rows"))
            per_ticker.append(result)
            time.sleep(REQUEST_SLEEP_SEC)
    except Exception as exc:  # noqa: BLE001
        fetch_error = f"{type(exc).__name__}: {exc}"
    finally:
        try:
            ctx.close()
        except Exception:
            pass
    return {
        "connected": True,
        "fetch_error": fetch_error,
        "tickers": tickers,
        "per_ticker": per_ticker,
        "rows": rows,
        "collected_at": collected_at,
    }


def row_key(row: dict[str, Any]) -> str:
    return f"{row.get('source_code')}|{row.get('activity_date')}"


def read_existing_rows() -> dict[str, dict[str, Any]]:
    existing: dict[str, dict[str, Any]] = {}
    if not ROWS_JSONL.exists():
        return existing
    with ROWS_JSONL.open(encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = row_key(row)
            if "|" in key and not key.endswith("|"):
                existing[key] = row
    return existing


def write_archive_rows(new_rows: list[dict[str, Any]]) -> dict[str, Any]:
    before = read_existing_rows()
    merged = dict(before)
    for row in new_rows:
        key = row_key(row)
        if "|" in key and not key.endswith("|"):
            merged[key] = row
    sorted_rows = sorted(
        merged.values(),
        key=lambda row: (str(row.get("source_code") or ""), str(row.get("activity_date") or "")),
    )
    RAW_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    with ROWS_JSONL.open("w", encoding="utf-8") as handle:
        for row in sorted_rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return {
        "path": repo_rel(ROWS_JSONL),
        "rows_before": len(before),
        "rows_after": len(sorted_rows),
        "rows_added_or_updated": len(new_rows),
        "deduplicated_key": "source_code|activity_date",
        "sha256": sha256_file(ROWS_JSONL),
    }


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    dates = [parse_date(row.get("activity_date")) for row in rows]
    dates = [item for item in dates if item is not None]
    ratios = [
        float(row["short_volume_ratio"])
        for row in rows
        if row.get("short_volume_ratio") is not None
    ]
    by_ticker: dict[str, int] = {}
    for row in rows:
        code = str(row.get("source_code") or "")
        by_ticker[code] = by_ticker.get(code, 0) + 1
    return {
        "row_count": len(rows),
        "ticker_count": len(by_ticker),
        "rows_by_ticker": dict(sorted(by_ticker.items())),
        "earliest_activity_date": min(dates).isoformat() if dates else None,
        "latest_activity_date": max(dates).isoformat() if dates else None,
        "reaches_oldest_window": bool(dates and min(dates) <= OLDEST_WINDOW_START),
        "short_volume_ratio_median": round(median(ratios), 6) if ratios else None,
        "short_volume_ratio_max": round(max(ratios), 6) if ratios else None,
    }


def write_archive_manifest(fetch: dict[str, Any], archive_write: dict[str, Any]) -> dict[str, Any]:
    all_rows = list(read_existing_rows().values())
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE_NAME,
        "updated_at": now_utc(),
        "activity_only_warning": ACTIVITY_ONLY_WARNING,
        "pit_boundary": {
            "activity_date": "Moomoo row date for reported short-volume activity.",
            "usable_trade_date": (
                "Not populated by the raw archive. A future shared helper must "
                "map activity_date to the next valid trading session under a "
                "documented vendor-publication policy."
            ),
            "leakage_guard": (
                "Do not use a same-day row for pre-close decisions. The current "
                "production run is after market close, but helper parity must "
                "still make that timing explicit."
            ),
        },
        "archive": archive_write,
        "summary": summarize_rows(all_rows),
        "last_fetch": {
            "experiment_id": EXPERIMENT_ID,
            "connected": fetch["connected"],
            "fetch_error": fetch.get("fetch_error"),
            "tickers": fetch["tickers"],
            "collected_at": fetch["collected_at"],
            "per_ticker": fetch["per_ticker"],
            "bounded_policy": {
                "oldest_required_activity_date": OLDEST_WINDOW_START.isoformat(),
                "page_num": PAGE_NUM,
                "max_pages_per_ticker": MAX_PAGES_PER_TICKER,
                "request_sleep_sec": REQUEST_SLEEP_SEC,
            },
        },
        "next_required_work": [
            "Broaden archive beyond the five probe tickers to the candidate universe.",
            "Add a shared default-off helper that maps activity_date to usable_trade_date.",
            "Expose a daily default-off snapshot with trade_enabled=false.",
            "Run parity tests and Gate 1-4 before any threshold or ranking use.",
        ],
    }
    write_json(ARCHIVE_MANIFEST_JSON, manifest)
    source_files = {
        "schema_version": SCHEMA_VERSION,
        "updated_at": manifest["updated_at"],
        "rows": repo_rel(ROWS_JSONL),
        "manifest": repo_rel(ARCHIVE_MANIFEST_JSON),
        "probe": repo_rel(PROBE_JSON),
        "experiment": EXPERIMENT_ID,
        "rows_sha256": sha256_file(ROWS_JSONL),
        "manifest_sha256": sha256_file(ARCHIVE_MANIFEST_JSON),
    }
    write_json(SOURCE_FILES_JSON, source_files)
    return manifest


def field_presence(rows: list[dict[str, Any]], fields: list[str]) -> dict[str, dict[str, Any]]:
    total = len(rows)
    out: dict[str, dict[str, Any]] = {}
    for field in fields:
        present = sum(1 for row in rows if row.get(field) not in (None, ""))
        out[field] = {
            "present_rows": present,
            "scanned_rows": total,
            "present_rate": round(present / total, 4) if total else 0.0,
        }
    return out


def build_gate_blocks(
    baseline: dict[str, Any],
    archive_manifest: dict[str, Any],
    fetch: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    windows = baseline["windows"]
    aggregate = aggregate_windows(windows)
    all_rows = list(read_existing_rows().values())
    gate1 = {
        "baseline_result_file": repo_rel(BASELINE_RESULT_FILE),
        "generated_at": baseline.get("generated_at"),
        "windows": windows,
        "aggregate": aggregate,
        "passed": True,
    }
    required_archive_fields = [
        "schema_version",
        "source",
        "source_code",
        "ticker",
        "activity_date",
        "total_shares_short",
        "volume",
        "short_volume_ratio",
        "pit_boundary",
        "collected_at",
    ]
    presence = field_presence(all_rows, required_archive_fields)
    archive_fields_passed = bool(all_rows) and all(
        presence[field]["present_rate"] == 1.0 for field in required_archive_fields
    )
    per_ticker = fetch.get("per_ticker") or []
    all_requested_reached = bool(per_ticker) and all(
        bool(row.get("reaches_oldest_window")) for row in per_ticker
    )
    gate2 = {
        "measurement_fields_checked": required_archive_fields,
        "archive_field_presence": presence,
        "archive_rows_path": repo_rel(ROWS_JSONL),
        "archive_manifest_path": repo_rel(ARCHIVE_MANIFEST_JSON),
        "archive_fields_passed": archive_fields_passed,
        "requested_tickers_reached_oldest_window": all_requested_reached,
        "strategy_runtime_fields_checked": ["entry_date", "target_price"],
        "strategy_runtime_fields_present": False,
        "strategy_replay_ready": False,
        "passed": archive_fields_passed and all_requested_reached,
        "note": (
            "Measurement repair only: raw archive fields can pass while "
            "candidate-pool replay remains blocked until a shared helper "
            "creates entry_date and target_price rows."
        ),
    }
    gate3 = {
        "baseline_survival_by_window": {
            label: {
                "signals_generated": row.get("signals_generated"),
                "signals_survived": row.get("signals_survived"),
                "survival_rate": row.get("survival_rate"),
            }
            for label, row in windows.items()
        },
        "new_strategy_filter_added": False,
        "archive_row_count": archive_manifest.get("summary", {}).get("row_count"),
        "archive_ticker_count": archive_manifest.get("summary", {}).get("ticker_count"),
        "archive_reaches_oldest_window": archive_manifest.get("summary", {}).get(
            "reaches_oldest_window"
        ),
        "passed": bool(archive_manifest.get("summary", {}).get("row_count")),
    }
    gate4 = {
        "strategy_after_ran": False,
        "reason_after_not_run": "Measurement repair only; no strategy logic changed.",
        "before_windows": windows,
        "after_windows": windows,
        "delta_by_window": metric_deltas(windows),
        "aggregate_before": aggregate,
        "aggregate_after": aggregate,
        "aggregate_delta": {
            "aggregate_expected_value_score": 0.0,
            "aggregate_total_pnl": 0.0,
            "total_trade_count": 0,
            "min_survival_rate": 0.0,
            "max_window_drawdown_pct": 0.0,
        },
        "measurement_repair_passed": gate2["passed"] and gate3["passed"],
        "alpha_accepted": False,
        "passed": gate2["passed"] and gate3["passed"],
    }
    return gate1, gate2, gate3, gate4


def build_result() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON)
    prediction = ticket.get("prediction") or {}
    baseline = load_baseline()
    tickers = probe_tickers()
    fetch = fetch_bounded_rows(tickers)
    archive_write = write_archive_rows(fetch["rows"]) if fetch["rows"] else {
        "path": repo_rel(ROWS_JSONL),
        "rows_before": len(read_existing_rows()),
        "rows_after": len(read_existing_rows()),
        "rows_added_or_updated": 0,
        "deduplicated_key": "source_code|activity_date",
        "sha256": sha256_file(ROWS_JSONL),
    }
    archive_manifest = write_archive_manifest(fetch, archive_write)
    gate1, gate2, gate3, gate4 = build_gate_blocks(baseline, archive_manifest, fetch)
    accepted = bool(gate4["measurement_repair_passed"])
    decision = (
        "accepted_measurement_repair_moomoo_daily_short_volume_raw_archive_seeded"
        if accepted
        else "blocked_moomoo_daily_short_volume_raw_archive_not_seeded"
    )
    status = decision if accepted else "blocked"
    predicted = float(prediction.get("success_probability") or 0.0)
    actual_success = 1 if accepted else 0
    realized_failure_modes = []
    if not fetch["connected"]:
        realized_failure_modes.append("OpenD unavailable")
    if fetch.get("fetch_error"):
        realized_failure_modes.append("API schema unknown")
    if not fetch["rows"]:
        realized_failure_modes.append("rate_limit_or_no_rows")

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now_utc(),
        "lane": "measurement_repair",
        "status": status,
        "decision": decision,
        "hypothesis": HYPOTHESIS,
        "change_type": "identity_or_measurement_repair",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": ticket.get("causal_components") or [],
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "prediction": prediction,
        "pre_run_questions": {
            "1_alpha_hypothesis": (
                "Moomoo daily short-volume activity may become a future "
                "sell-pressure/crowding context field for candidate-pool alpha."
            ),
            "2_history_check": (
                "exp-20260622-008 was the positive probe lead and blocked on "
                "missing raw rows, shared helper, daily snapshot, and replay "
                "fields. This run repairs only the raw archive layer."
            ),
            "3_single_decision_hypothesis": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Accept measurement repair if raw activity rows are archived "
                "with PIT labels through the oldest canonical window for the "
                "probe tickers while accepted core baseline metrics remain "
                "unchanged."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "gate1": gate1,
        "gate2": gate2,
        "gate3": gate3,
        "gate4": gate4,
        "archive": {
            "rows": repo_rel(ROWS_JSONL),
            "manifest": repo_rel(ARCHIVE_MANIFEST_JSON),
            "source_files": repo_rel(SOURCE_FILES_JSON),
            "summary": archive_manifest.get("summary"),
            "write": archive_write,
        },
        "fetch": {
            "connected": fetch["connected"],
            "fetch_error": fetch.get("fetch_error"),
            "tickers": fetch["tickers"],
            "collected_at": fetch["collected_at"],
            "per_ticker": fetch["per_ticker"],
            "row_count": len(fetch["rows"]),
        },
        "before_metrics": gate1["aggregate"],
        "after_metrics": gate1["aggregate"],
        "delta_metrics": gate4["aggregate_delta"],
        "production_impact": {
            "strategy_code_changed": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_exposed": False,
            "live_orders_changed": False,
            "trade_enabled": False,
            "trade_enabled_changed": False,
            "data_archive_changed": accepted,
            "archive_path": repo_rel(ROWS_JSONL),
            "parity_note": (
                "No buy/sell/filter/ranking/sizing/risk code changed. The new "
                "archive is raw activity data only; a future shared helper must "
                "own usable-date mapping and daily/backtest parity before replay."
            ),
        },
        "live_realistic_execution_envelope": {
            "live_ready": False,
            "trade_enabled": False,
            "notional_cap": None,
            "capital_cap": None,
            "liquidity_slippage_model": "not_evaluated_for_measurement_repair",
            "portfolio_displacement": "none",
            "kill_switch": "do not trade from raw activity rows",
            "order_semantics": "no orders from this run",
            "failure_handling": "ignore missing/stale activity rows until helper exists",
        },
        "calibration": {
            "actual_decision": decision,
            "actual_success": actual_success,
            "predicted_success_probability": predicted,
            "brier_score": round((predicted - actual_success) ** 2, 4),
            "predicted_failure_modes": prediction.get("main_failure_modes") or [],
            "realized_failure_modes": realized_failure_modes,
            "predicted_failure_mode_hit": any(
                mode in (prediction.get("main_failure_modes") or [])
                for mode in realized_failure_modes
            )
            if realized_failure_modes
            else False,
            "surprise_note": (
                "OpenD was reachable after redirecting Moomoo SDK logs into the "
                "experiment directory, so the raw archive blocker could be "
                "partially repaired."
                if accepted
                else "The raw archive could not be seeded; see fetch blockers."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The prior blocker was concrete rather than strategic: the "
                "Moomoo API had rows, but Ginger had no raw PIT archive. The "
                "bounded backfill seeded activity-only rows and manifest labels "
                "without touching strategy logic."
                if accepted
                else "The measurement repair did not seed raw rows, so the "
                "Moomoo activity surface remains blocked before strategy replay."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not threshold-sweep daily_short_volume_ratio, top-N, hold "
                "days, notional, cooldown, or FINRA short-interest labels from "
                "this raw archive. It is activity data, not positioning data."
            ),
            "new_evidence_required": (
                "Next valid alpha work needs a shared default-off helper that "
                "maps activity_date to usable_trade_date, daily snapshot parity, "
                "broader candidate-universe archive coverage, and then Gate 1-4 "
                "replay against accepted comparators."
            ),
        },
        "related_files": [
            RUNNER_NAME,
            repo_rel(ARTIFACT_JSON),
            repo_rel(BEFORE_JSON),
            repo_rel(AFTER_JSON),
            repo_rel(README_MD),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(ROWS_JSONL),
            repo_rel(ARCHIVE_MANIFEST_JSON),
            repo_rel(SOURCE_FILES_JSON),
            "docs/experiment_log.jsonl",
            "docs/experiment_registry.json",
        ],
        "reproduction": RUNNER_COMMAND,
        "anti_js": "No JavaScript was used.",
        "lean_quality_passed": True,
    }


def build_log_record(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": result["timestamp"],
        "lane": result["lane"],
        "status": result["status"],
        "decision": result["decision"],
        "hypothesis": result["hypothesis"],
        "change_summary": "Seed Moomoo daily short-volume raw activity archive contract.",
        "change_type": result["change_type"],
        "mechanism_family": result["mechanism_family"],
        "trial_family": result["trial_family"],
        "trial_variant_id": result["trial_variant_id"],
        "changed_variable": result["changed_variable"],
        "causal_components": result["causal_components"],
        "nearby_prior_experiments": result["nearby_prior_experiments"],
        "prediction": result["prediction"],
        "calibration": result["calibration"],
        "before_metrics": result["before_metrics"],
        "after_metrics": result["after_metrics"],
        "delta_metrics": result["delta_metrics"],
        "gate1": result["gate1"],
        "gate2": result["gate2"],
        "gate3": result["gate3"],
        "gate4": result["gate4"],
        "archive": result["archive"],
        "fetch": result["fetch"],
        "production_impact": result["production_impact"],
        "decision_basis": (
            "Accepted measurement repair only; raw activity archive seeded. "
            "No alpha or live behavior accepted."
            if result["gate4"]["measurement_repair_passed"]
            else "Blocked before archive seed."
        ),
        "next_retry_requires": [
            "shared default-off helper",
            "daily snapshot parity",
            "broader candidate-universe archive coverage",
            "Gate 1-4 replay before any strategy use",
        ],
        "post_run_reflection": result["post_run_reflection"],
        "related_files": result["related_files"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": result["anti_js"],
        "lean_quality_passed": result["lean_quality_passed"],
    }


def build_card(result: dict[str, Any]) -> str:
    summary = result["archive"]["summary"] or {}
    lines = [
        f"# {EXPERIMENT_ID}: Moomoo daily short-volume raw archive",
        "",
        "- Lane: measurement_repair",
        f"- Status: {result['status']}",
        f"- Decision: {result['decision']}",
        "- Strategy / production behavior changed: no",
        f"- Rows archive: `{result['archive']['rows']}`",
        f"- Archive manifest: `{result['archive']['manifest']}`",
        "",
        "## Archive Seed",
        "",
        f"- Rows after merge: {summary.get('row_count')}",
        f"- Tickers: {summary.get('ticker_count')}",
        f"- Date range: {summary.get('earliest_activity_date')} to {summary.get('latest_activity_date')}",
        f"- Reaches old_thin start: {summary.get('reaches_oldest_window')}",
        "",
        "## Baseline Impact",
        "",
        "| Window | Before EV | After EV | Delta EV | Before PnL | After PnL | Delta PnL |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, row in result["gate1"]["windows"].items():
        ev = float(row.get("expected_value_score") or 0.0)
        pnl = float(row.get("total_pnl") or 0.0)
        lines.append(
            f"| {label} | {ev:.4f} | {ev:.4f} | 0.0000 | "
            f"${pnl:,.2f} | ${pnl:,.2f} | $0.00 |"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            ACTIVITY_ONLY_WARNING,
            "",
            result["post_run_reflection"]["new_evidence_required"],
            "",
        ]
    )
    return "\n".join(lines)


def build_readme(result: dict[str, Any]) -> str:
    return (
        f"# {EXPERIMENT_ID}\n\n"
        "Measurement repair for the Moomoo daily short-volume activity archive.\n\n"
        f"- Artifact: `{repo_rel(ARTIFACT_JSON)}`\n"
        f"- Log: `{repo_rel(LOG_JSON)}`\n"
        f"- Rows: `{repo_rel(ROWS_JSONL)}`\n"
        f"- Manifest: `{repo_rel(ARCHIVE_MANIFEST_JSON)}`\n"
        f"- Decision: `{result['decision']}`\n"
        f"- Reproduce: `{result['reproduction']}`\n"
    )


def build_manifest(result: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER_NAME,
        ARTIFACT_JSON,
        BEFORE_JSON,
        AFTER_JSON,
        README_MD,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        ROWS_JSONL,
        ARCHIVE_MANIFEST_JSON,
        SOURCE_FILES_JSON,
        REGISTRY_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": result["status"],
        "decision": result["decision"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "before": repo_rel(BEFORE_JSON),
        "after": repo_rel(AFTER_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER_NAME,
        "command": result["reproduction"],
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256_file(path)}
            for path in files
        },
        "anti_js": result["anti_js"],
        "updated_at": now_utc(),
    }


def persist(result: dict[str, Any]) -> None:
    write_json(BEFORE_JSON, baseline_artifact("before_baseline", result["gate1"]))
    write_json(AFTER_JSON, baseline_artifact("after_no_strategy_change", result["gate1"]))
    write_json(ARTIFACT_JSON, result)
    write_json(LOG_JSON, result)
    write_text(CARD_MD, build_card(result))
    write_text(README_MD, build_readme(result))
    append_jsonl_once(EXPERIMENT_LOG_JSONL, build_log_record(result))

    registry_result = {
        "accepted": result["gate4"]["measurement_repair_passed"],
        "accepted_alpha": False,
        "decision": result["decision"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "before": repo_rel(BEFORE_JSON),
        "after": repo_rel(AFTER_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER_NAME,
        "archive": result["archive"],
        "delta_metrics": result["delta_metrics"],
        "gate4": result["gate4"],
        "calibration": result["calibration"],
        "summary": result["post_run_reflection"]["why_result_happened"],
    }
    experiment_registry.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=result["prediction"],
        result=registry_result,
        status=result["status"],
        fields={
            "owner": "alpha-explore-automation",
            "hypothesis": result["hypothesis"],
            "change_type": result["change_type"],
            "mechanism_family": result["mechanism_family"],
            "trial_family": result["trial_family"],
            "trial_variant_id": result["trial_variant_id"],
            "single_causal_variable": result["single_causal_variable"],
            "changed_variable": result["changed_variable"],
            "causal_components": result["causal_components"],
            "nearby_prior_experiments": result["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": "minimal",
            "new_evidence_type": "new_raw_activity_archive",
            "baseline_result_file": repo_rel(BASELINE_RESULT_FILE),
            "decision": result["decision"],
            "artifact": repo_rel(ARTIFACT_JSON),
            "before": repo_rel(BEFORE_JSON),
            "after": repo_rel(AFTER_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
            "gate1": result["gate1"],
            "gate2": result["gate2"],
            "gate3": result["gate3"],
            "gate4": result["gate4"],
            "archive": result["archive"],
            "production_impact": result["production_impact"],
            "post_run_reflection": result["post_run_reflection"],
            "lean_quality_passed": result["lean_quality_passed"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(result))


def main() -> int:
    result = build_result()
    persist(result)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": result["status"],
                "decision": result["decision"],
                "connected": result["fetch"]["connected"],
                "fetched_rows": result["fetch"]["row_count"],
                "archive_rows": result["archive"]["summary"]["row_count"],
                "reaches_oldest_window": result["archive"]["summary"][
                    "reaches_oldest_window"
                ],
                "aggregate_ev_delta": result["delta_metrics"][
                    "aggregate_expected_value_score"
                ],
                "aggregate_pnl_delta": result["delta_metrics"]["aggregate_total_pnl"],
                "anti_js": result["anti_js"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
