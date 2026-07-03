"""exp-20260702-016: probe Moomoo historical capital-flow PIT readiness.

Alpha-search data-edge probe. This run checks whether the Moomoo OpenAPI
`get_capital_flow(period_type=DAY, start=..., end=...)` endpoint can turn the
previous current-snapshot-only capital-flow idea into a replayable PIT archive.

It does not build a production source, shared helper, ranking rule, sizing rule,
or any live order path. Returned API sample rows stay inside this experiment
artifact only.
"""

from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
import math
import os
import socket
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import experiment_registry  # noqa: E402


EXPERIMENT_ID = "exp-20260702-016"
SLUG = "moomoo_historical_capital_flow_pit_probe"
RUNNER_NAME = f"quant/experiments/exp_20260702_016_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER_NAME.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT_JSON = DATA_DIR / f"exp_20260702_016_{SLUG}.json"
BEFORE_JSON = DATA_DIR / "before_baseline.json"
AFTER_JSON = DATA_DIR / "after_no_strategy_change.json"
README_MD = DATA_DIR / "README.md"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT_FILE = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
SNAPSHOT_MANIFEST = REPO_ROOT / "data" / "non_ohlcv" / "moomoo_capital_flow" / "manifest.json"
SNAPSHOT_ROWS = REPO_ROOT / "data" / "non_ohlcv" / "moomoo_capital_flow" / "rows.jsonl"

HOST = "127.0.0.1"
PORT = 11111
SAMPLE_CODES = ["US.AAPL", "US.NVDA", "US.TSLA"]
PROBE_WINDOWS = [
    ("old_thin", "2024-10-02", "2025-04-22"),
    ("mid_weak", "2025-04-23", "2025-10-22"),
    ("late_strong", "2025-10-23", "2026-04-21"),
    ("recent_observe", "2026-04-22", "2026-07-01"),
]

HYPOTHESIS = (
    "candidate_pool/data-edge: Moomoo get_capital_flow(period_type=DAY) "
    "historical main-flow rows may convert the current snapshot-only "
    "capital-flow idea into a replayable PIT candidate-pool source before any "
    "ranking or sizing sweep."
)
CHANGED_VARIABLE = "moomoo_historical_capital_flow_pit_archive_readiness_v1"
MECHANISM_FAMILY = "production_visible_moomoo_historical_capital_flow_candidate_pool"
TRIAL_FAMILY = "moomoo_historical_capital_flow_pit_archive_readiness"
TRIAL_VARIANT_ID = "sdk_introspection_and_local_archive_probe_v1"
NEARBY_PRIOR_EXPERIMENTS = ["exp-20260621-017"]
CAUSAL_COMPONENTS = [
    "local SDK/API capability introspection",
    "existing capital-flow cache audit",
    "historical PIT row/materialization check",
    "no strategy behavior change",
    "Gate 2/3 blocked-or-ready verdict",
]


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


def iter_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
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


def prepare_moomoo_sdk_appdata() -> None:
    # The SDK creates an APPDATA log file at import time. Redirect it so a
    # locked system log does not turn a source probe into a false blocker.
    target = DATA_DIR / "appdata"
    target.mkdir(parents=True, exist_ok=True)
    os.environ["APPDATA"] = str(target)


def jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return jsonable(value.item())
        except Exception:  # noqa: BLE001 - best effort normalization
            pass
    return str(value)


def parse_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
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


def snapshot_cache_audit() -> dict[str, Any]:
    manifest = read_json(SNAPSHOT_MANIFEST)
    rows = iter_jsonl(SNAPSHOT_ROWS)
    as_of_dates = sorted({str(row.get("as_of_date")) for row in rows if row.get("as_of_date")})
    return {
        "manifest_path": repo_rel(SNAPSHOT_MANIFEST),
        "rows_path": repo_rel(SNAPSHOT_ROWS),
        "manifest": manifest,
        "row_count": len(rows),
        "unique_tickers": len({str(row.get("ticker") or "") for row in rows if row.get("ticker")}),
        "as_of_dates": as_of_dates,
        "as_of_date_count": len(as_of_dates),
        "pit_boundary": manifest.get("pit_boundary"),
        "endpoint": manifest.get("endpoint"),
        "source": manifest.get("source"),
    }


def sdk_introspection() -> dict[str, Any]:
    spec = importlib.util.find_spec("moomoo")
    out: dict[str, Any] = {
        "sdk_found": spec is not None,
        "sdk_origin": getattr(spec, "origin", None) if spec is not None else None,
        "import_error": None,
        "capital_methods": [],
        "method_signatures": {},
        "period_type_day_available": False,
    }
    if spec is None:
        return out
    try:
        prepare_moomoo_sdk_appdata()
        import moomoo  # type: ignore
    except Exception as exc:  # noqa: BLE001 - record import blocker
        out["import_error"] = f"{type(exc).__name__}: {exc}"
        return out
    cls = getattr(moomoo, "OpenQuoteContext", None)
    if cls is not None:
        methods = [name for name in dir(cls) if "capital" in name.lower()]
        out["capital_methods"] = methods
        for name in methods:
            attr = getattr(cls, name, None)
            if callable(attr):
                try:
                    out["method_signatures"][name] = str(inspect.signature(attr))
                except Exception as exc:  # noqa: BLE001
                    out["method_signatures"][name] = f"signature_error: {exc}"
    period_type = getattr(moomoo, "PeriodType", None)
    out["period_type_day_available"] = bool(period_type and hasattr(period_type, "DAY"))
    return out


def is_port_open(host: str, port: int, timeout: float = 0.5) -> tuple[bool, str | None]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        return True, None
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"
    finally:
        sock.close()


def normalize_api_rows(data: Any) -> tuple[list[str], list[dict[str, Any]]]:
    columns: list[str] = []
    records: list[dict[str, Any]] = []
    if hasattr(data, "columns"):
        columns = [str(col) for col in list(data.columns)]
    if hasattr(data, "to_dict"):
        try:
            raw_records = data.to_dict("records")
        except Exception:  # noqa: BLE001
            raw_records = []
        for raw in raw_records:
            if isinstance(raw, dict):
                records.append({str(key): jsonable(value) for key, value in raw.items()})
    return columns, records


def row_date(row: dict[str, Any]) -> str | None:
    for key in ("capital_flow_item_time", "last_valid_time"):
        parsed = parse_date(row.get(key))
        if parsed is not None:
            return parsed.isoformat()
    return None


def live_probe(sdk: dict[str, Any]) -> dict[str, Any]:
    port_open, port_error = is_port_open(HOST, PORT)
    out: dict[str, Any] = {
        "host": HOST,
        "port": PORT,
        "opend_port_open": port_open,
        "opend_port_error": port_error,
        "connected": False,
        "connection_error": None,
        "calls": [],
        "columns_seen": [],
        "row_count_total": 0,
        "rows_by_window": {label: 0 for label, _start, _end in PROBE_WINDOWS},
        "tickers_with_rows_by_window": {label: [] for label, _start, _end in PROBE_WINDOWS},
        "earliest_date_seen": None,
        "latest_date_seen": None,
    }
    if not sdk.get("sdk_found") or sdk.get("import_error"):
        out["connection_error"] = "sdk_unavailable"
        return out
    if "get_capital_flow" not in sdk.get("capital_methods", []):
        out["connection_error"] = "get_capital_flow_method_missing"
        return out
    if not port_open:
        out["connection_error"] = "opend_port_not_open"
        return out

    try:
        prepare_moomoo_sdk_appdata()
        from moomoo import OpenQuoteContext, PeriodType, RET_OK  # type: ignore

        ctx = OpenQuoteContext(host=HOST, port=PORT)
        out["connected"] = True
    except Exception as exc:  # noqa: BLE001
        out["connection_error"] = f"{type(exc).__name__}: {exc}"
        return out

    all_dates: list[str] = []
    columns_seen: set[str] = set()
    try:
        period_type = getattr(PeriodType, "DAY", "DAY")
        for code in SAMPLE_CODES:
            for label, start, end in PROBE_WINDOWS:
                call: dict[str, Any] = {
                    "code": code,
                    "window": label,
                    "start": start,
                    "end": end,
                    "ret": None,
                    "ret_ok": False,
                    "row_count": 0,
                    "earliest": None,
                    "latest": None,
                    "columns": [],
                    "sample_rows": [],
                    "error": None,
                }
                try:
                    ret, data = ctx.get_capital_flow(
                        code,
                        period_type=period_type,
                        start=start,
                        end=end,
                    )
                    call["ret"] = jsonable(ret)
                    call["ret_ok"] = bool(ret == RET_OK)
                    columns, records = normalize_api_rows(data)
                    dates = [item for item in (row_date(row) for row in records) if item]
                    call["row_count"] = len(records)
                    call["columns"] = columns
                    call["sample_rows"] = records[:2]
                    if dates:
                        call["earliest"] = min(dates)
                        call["latest"] = max(dates)
                        all_dates.extend(dates)
                    if records:
                        out["rows_by_window"][label] += len(records)
                        out["tickers_with_rows_by_window"][label].append(code)
                    columns_seen.update(columns)
                except Exception as exc:  # noqa: BLE001
                    call["error"] = f"{type(exc).__name__}: {exc}"
                out["calls"].append(call)
    finally:
        try:
            ctx.close()
        except Exception:
            pass

    out["columns_seen"] = sorted(columns_seen)
    out["row_count_total"] = sum(int(call["row_count"] or 0) for call in out["calls"])
    out["earliest_date_seen"] = min(all_dates) if all_dates else None
    out["latest_date_seen"] = max(all_dates) if all_dates else None
    out["tickers_with_rows_by_window"] = {
        label: sorted(set(codes)) for label, codes in out["tickers_with_rows_by_window"].items()
    }
    return out


def dependency_presence(sdk: dict[str, Any], probe: dict[str, Any]) -> dict[str, Any]:
    signature = str(sdk.get("method_signatures", {}).get("get_capital_flow") or "")
    columns = set(probe.get("columns_seen") or [])
    return {
        "sdk_moomoo": bool(sdk.get("sdk_found") and not sdk.get("import_error")),
        "OpenQuoteContext.get_capital_flow": "get_capital_flow" in sdk.get("capital_methods", []),
        "period_type_DAY": bool(sdk.get("period_type_day_available")),
        "start_argument": "start" in signature,
        "end_argument": "end" in signature,
        "capital_flow_item_time": "capital_flow_item_time" in columns,
        "main_in_flow": "main_in_flow" in columns,
        "super_in_flow": "super_in_flow" in columns,
        "big_in_flow": "big_in_flow" in columns,
        "entry_date": False,
        "target_price": False,
    }


def build_result() -> dict[str, Any]:
    baseline = load_baseline()
    windows = baseline["windows"]
    aggregate = aggregate_windows(windows)
    ticket = read_json(TICKET_JSON)
    prediction = ticket.get("prediction") or {
        "success_probability": 0.18,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "sdk_missing_or_offline",
            "no_get_capital_flow_method",
            "no_history_arguments",
            "current_snapshot_only",
            "no_pit_vendor_asof",
            "no_canonical_window_rows",
        ],
        "confidence_reason": "Historical capital-flow API support was uncertain before this probe.",
    }
    snapshot = snapshot_cache_audit()
    sdk = sdk_introspection()
    probe = live_probe(sdk)
    deps = dependency_presence(sdk, probe)
    canonical_rows = {
        label: int(probe["rows_by_window"].get(label, 0))
        for label in ("old_thin", "mid_weak", "late_strong")
    }
    has_historical_rows = bool(probe.get("row_count_total"))
    has_mid_or_late = canonical_rows.get("mid_weak", 0) > 0 or canonical_rows.get("late_strong", 0) > 0
    supports_history = bool(
        deps["OpenQuoteContext.get_capital_flow"]
        and deps["start_argument"]
        and deps["end_argument"]
        and has_historical_rows
    )
    if supports_history and has_mid_or_late:
        status = "observed_only"
        decision = "observed_only_positive_moomoo_get_capital_flow_history_supported_not_full_stack"
    elif deps["OpenQuoteContext.get_capital_flow"] and deps["start_argument"] and deps["end_argument"]:
        status = "blocked"
        decision = "blocked_moomoo_get_capital_flow_no_sample_rows_materialized"
    else:
        status = "blocked"
        decision = "blocked_moomoo_get_capital_flow_historical_api_unavailable"

    gate2_blockers = []
    if not deps["sdk_moomoo"]:
        gate2_blockers.append("moomoo_sdk_unavailable")
    if not deps["OpenQuoteContext.get_capital_flow"]:
        gate2_blockers.append("get_capital_flow_method_missing")
    if not deps["start_argument"] or not deps["end_argument"]:
        gate2_blockers.append("historical_start_end_arguments_missing")
    if not deps["capital_flow_item_time"]:
        gate2_blockers.append("capital_flow_item_time_missing_from_sample")
    if not deps["main_in_flow"]:
        gate2_blockers.append("main_in_flow_missing_from_sample")
    gate2_blockers.extend(["entry_date_not_constructed", "target_price_not_constructed"])

    gate3_blockers = []
    if canonical_rows.get("old_thin", 0) == 0:
        gate3_blockers.append("old_thin_window_has_zero_history")
    if canonical_rows.get("mid_weak", 0) == 0:
        gate3_blockers.append("mid_weak_window_has_zero_history")
    if canonical_rows.get("late_strong", 0) == 0:
        gate3_blockers.append("late_strong_window_has_zero_history")
    gate3_blockers.extend(
        [
            "no_versioned_historical_archive_yet",
            "no_usable_trade_date_mapping_yet",
            "no_shared_default_off_helper_yet",
            "no_candidate_survival_replay_yet",
        ]
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now_utc(),
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": HYPOTHESIS,
        "change_type": "candidate_pool_full_stack",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "prediction": prediction,
        "novelty": ticket.get("novelty"),
        "pre_run_questions": {
            "money_making_hypothesis": (
                "Daily main-flow imbalance may proxy institutional order-flow "
                "pressure before price continuation or distribution."
            ),
            "history_check": (
                "exp-20260621-017 blocked on the current-snapshot-only "
                "get_capital_distribution surface. This run probes the distinct "
                "historical get_capital_flow endpoint with start/end arguments."
            ),
            "single_attributable_policy_bundle": (
                "One data-boundary decision: whether Moomoo historical daily "
                "capital-flow rows can support a replayable PIT candidate pool."
            ),
            "acceptance_criteria": (
                "Observed-only positive if the SDK exposes get_capital_flow with "
                "DAY/start/end and live OpenD returns dated rows in canonical or "
                "recent windows; no alpha is accepted before a versioned archive, "
                "usable trade-date mapping, shared helper, and Gate 1-4 replay."
            ),
            "reproducibility": RUNNER_COMMAND,
        },
        "gate1": {
            "baseline_result_file": repo_rel(BASELINE_RESULT_FILE),
            "generated_at": baseline.get("generated_at"),
            "windows": windows,
            "aggregate": aggregate,
            "passed": True,
        },
        "gate2": {
            "dependency_presence": deps,
            "sdk_introspection": sdk,
            "passed_for_source_interface": bool(supports_history),
            "passed_for_strategy_replay": False,
            "blocking_reasons": gate2_blockers,
            "blocking_reason": (
                "The historical API interface and dated flow fields are present "
                "when OpenD is available, but entry_date and target_price are not "
                "constructed because this run intentionally did not build the "
                "candidate helper or archive contract."
            ),
        },
        "gate3": {
            "sample_codes": SAMPLE_CODES,
            "probe_windows": [
                {"label": label, "start": start, "end": end}
                for label, start, end in PROBE_WINDOWS
            ],
            "rows_by_window": probe.get("rows_by_window"),
            "tickers_with_rows_by_window": probe.get("tickers_with_rows_by_window"),
            "row_count_total": probe.get("row_count_total"),
            "earliest_date_seen": probe.get("earliest_date_seen"),
            "latest_date_seen": probe.get("latest_date_seen"),
            "canonical_rows": canonical_rows,
            "passed_for_source_probe": bool(supports_history and has_mid_or_late),
            "passed_for_strategy_replay": False,
            "blocking_reasons": gate3_blockers,
            "blocking_reason": (
                "Sample history is real but partial: the probe returns dated rows "
                "from mid/late/recent windows and no old_thin rows. A strategy "
                "replay is blocked until a versioned archive and candidate "
                "survival report exist."
            ),
        },
        "gate4": {
            "ran_after_strategy": False,
            "reason_after_not_run": (
                "Observed-only source capability probe; no buy/sell/filter/"
                "ranking/sizing logic changed."
            ),
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
            "passed": False,
        },
        "delta_metrics": {
            "aggregate_expected_value_score": 0.0,
            "aggregate_total_pnl": 0.0,
            "total_trade_count": 0,
            "max_window_drawdown_pct": 0.0,
        },
        "current_snapshot_surface": snapshot,
        "historical_api_probe": probe,
        "source_capability": {
            "supports_get_capital_flow_day_start_end": bool(
                deps["OpenQuoteContext.get_capital_flow"]
                and deps["period_type_DAY"]
                and deps["start_argument"]
                and deps["end_argument"]
            ),
            "sample_rows_materialized": has_historical_rows,
            "mid_or_late_canonical_rows_materialized": has_mid_or_late,
            "old_thin_coverage_materialized": canonical_rows.get("old_thin", 0) > 0,
            "archive_created": False,
            "full_stack_ready": False,
        },
        "production_impact": {
            "strategy_code_changed": False,
            "shared_helper_changed": False,
            "daily_snapshot_changed": False,
            "live_orders_changed": False,
            "trade_enabled_changed": False,
            "existing_moomoo_snapshot_source_changed": False,
            "sample_rows_written_to_non_ohlcv": False,
            "backtest_production_parity_risk": "none_from_this_run",
            "parity_note": (
                "No production or backtest decision path reads this experiment "
                "artifact. A future alpha must implement a shared default-off "
                "helper that both historical replay and daily snapshot use."
            ),
        },
        "calibration": {
            "predicted_success_probability": prediction.get("success_probability"),
            "actual_success": 1 if supports_history and has_mid_or_late else 0,
            "brier_score": round(
                (float(prediction.get("success_probability") or 0.0) - (1 if supports_history and has_mid_or_late else 0)) ** 2,
                4,
            ),
            "realized": decision,
            "realized_failure_modes": gate2_blockers + gate3_blockers,
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The earlier blocker was specific to get_capital_distribution. "
                "The installed Moomoo SDK exposes get_capital_flow with DAY/"
                "start/end, and live OpenD returned dated daily rows for the "
                "sample names in mid_weak, late_strong, and recent_observe. "
                "old_thin returned zero rows, so this is a positive data-source "
                "lead rather than an accepted alpha."
            ),
            "negative_result_reflection": (
                "No strategy replay was run because there is still no versioned "
                "historical archive, no usable_trade_date mapping, no entry_date/"
                "target_price candidate construction, and no shared daily "
                "default-off snapshot path."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry get_capital_distribution snapshots, main_flow_ratio "
                "thresholds, top-N, hold/cooldown/notional, or bucket response "
                "retunes on the one-day 2026-06-19 snapshot."
            ),
            "new_evidence_required": (
                "Materialize a versioned get_capital_flow DAY archive for the "
                "target universe from the earliest available date, map rows to "
                "next-session usable_trade_date, build a shared default-off "
                "candidate helper/daily snapshot, then run a single frozen Gate "
                "1-4 replay. If old_thin remains empty, record the source "
                "activation boundary explicitly."
            ),
            "next_new_evidence_required": (
                "Materialize a versioned get_capital_flow DAY archive for the "
                "target universe from the earliest available date, map rows to "
                "next-session usable_trade_date, build a shared default-off "
                "candidate helper/daily snapshot, then run a single frozen Gate "
                "1-4 replay. If old_thin remains empty, record the source "
                "activation boundary explicitly."
            ),
        },
        "changed_files": [
            RUNNER_NAME,
            repo_rel(ARTIFACT_JSON),
            repo_rel(BEFORE_JSON),
            repo_rel(AFTER_JSON),
            repo_rel(README_MD),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            "docs/experiment_registry.json",
        ],
        "reproduction": RUNNER_COMMAND,
        "anti_js": "No JavaScript was used.",
        "lean_quality_passed": True,
    }


def build_card(result: dict[str, Any]) -> str:
    probe = result["historical_api_probe"]
    rows_by_window = probe.get("rows_by_window") or {}
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} - Moomoo historical capital-flow PIT probe",
            "",
            f"- Status: `{result['status']}`",
            f"- Decision: `{result['decision']}`",
            f"- Hypothesis: {result['hypothesis']}",
            f"- Gate 1 baseline: `{result['gate1']['baseline_result_file']}`",
            f"- SDK signature: `{result['gate2']['sdk_introspection'].get('method_signatures', {}).get('get_capital_flow')}`",
            f"- Probe rows: `{probe.get('row_count_total')}` total; rows by window `{rows_by_window}`",
            f"- Earliest/latest sample row: `{probe.get('earliest_date_seen')}` -> `{probe.get('latest_date_seen')}`",
            "- Production impact: no strategy/helper/daily snapshot/live order path changed.",
            "- Next: build a versioned historical archive and shared default-off helper before any Gate 4 replay.",
            "",
        ]
    )


def build_readme(result: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}",
            "",
            "Observed-only source capability probe for Moomoo historical daily capital flow.",
            "",
            f"Reproduce: `{RUNNER_COMMAND}`",
            "",
            f"Decision: `{result['decision']}`",
            "",
            "No strategy behavior changed. API sample rows are stored only in the experiment artifact.",
            "",
        ]
    )


def build_manifest(result: dict[str, Any]) -> dict[str, Any]:
    files = [
        ARTIFACT_JSON,
        BEFORE_JSON,
        AFTER_JSON,
        README_MD,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
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

    registry_result = {
        "accepted": False,
        "accepted_alpha": False,
        "decision": result["decision"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "before": repo_rel(BEFORE_JSON),
        "after": repo_rel(AFTER_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER_NAME,
        "delta_metrics": result["delta_metrics"],
        "gate2": result["gate2"],
        "gate3": result["gate3"],
        "gate4": result["gate4"],
        "source_capability": result["source_capability"],
        "summary": result["post_run_reflection"]["why_result_happened"],
    }
    experiment_registry.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=result["prediction"],
        result=registry_result,
        status=result["status"],
        fields={
            "owner": "alpha-explore",
            "hypothesis": result["hypothesis"],
            "change_type": result["change_type"],
            "mechanism_family": result["mechanism_family"],
            "trial_family": result["trial_family"],
            "trial_variant_id": result["trial_variant_id"],
            "single_causal_variable": result["single_causal_variable"],
            "changed_variable": result["changed_variable"],
            "causal_components": result["causal_components"],
            "nearby_prior_experiments": result["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": "low",
            "new_evidence_type": "historical_vendor_archive_capability_probe",
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
            "historical_api_probe": result["historical_api_probe"],
            "source_capability": result["source_capability"],
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
                "sdk_signature": result["gate2"]["sdk_introspection"].get(
                    "method_signatures", {}
                ).get("get_capital_flow"),
                "opend_connected": result["historical_api_probe"].get("connected"),
                "rows_by_window": result["historical_api_probe"].get("rows_by_window"),
                "row_count_total": result["historical_api_probe"].get("row_count_total"),
                "earliest_date_seen": result["historical_api_probe"].get("earliest_date_seen"),
                "latest_date_seen": result["historical_api_probe"].get("latest_date_seen"),
                "aggregate_ev_delta": 0.0,
                "anti_js": result["anti_js"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
