"""exp-20260624-016: Kova forward SEC13F sponsorship ledger.

Measurement repair for the Kova multi-source forward observation surface.
exp-20260623-013 produced replayable Kova rows, but every SEC13F field was
skipped. exp-20260624-015 repaired the local PIT SEC13F holdings fallback.
This runner rebuilds an experiment-owned ledger with holder/value fields so
future closed rows can test institutional sponsorship without re-scanning.

No strategy, ranking, sizing, exit, order, paper fill, watchlist, LLM, or
production daily behavior changes in this experiment.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
QUANT_ROOT = REPO_ROOT / "quant"
for entry in (REPO_ROOT, SCRIPTS_ROOT, QUANT_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import kova_data_sidecar as sidecar  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260624-016"
OWNER = "alpha-explore"
SLUG = "kova_forward_sec13f_sponsorship_ledger"
RUNNER = f"quant/experiments/exp_20260624_016_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260624_016_{SLUG}.json"
LEDGER_JSONL = DATA_DIR / "kova_forward_sec13f_sponsorship_ledger.jsonl"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
KOVA_ROOT = REPO_ROOT / "data" / "kova"
SNAPSHOT_DIR = KOVA_ROOT / "snapshots"
RS_DIR = KOVA_ROOT / "rs_proxy"
FUNDAMENTALS_DIR = KOVA_ROOT / "fundamentals"
INSTITUTIONAL_DIR = KOVA_ROOT / "institutional"
INTRADAY_DIR = KOVA_ROOT / "intraday"
NON_OHLCV_DIR = REPO_ROOT / "data" / "non_ohlcv"

OBSERVATION_START = "2026-06-13"
MIN_SEC13F_OK_COVERAGE = 0.50
SELECTED_FUNDAMENTAL_COMPONENTS = (
    "revenue",
    "gross_profit",
    "operating_income",
    "net_income",
    "eps_diluted",
)

HYPOTHESIS = (
    "Kova multi-source alpha cannot use institutional sponsorship until forward "
    "observation rows store PIT-safe holder/value fields; rebuild an "
    "experiment-owned Kova forward ledger with the exp-20260624-015 local SEC13F "
    "holdings fallback while leaving entries, ranking, sizing, exits, paper "
    "fills, live orders, and shared policy unchanged."
)
ALPHA_HYPOTHESIS = (
    "Institutional sponsorship may become an orthogonal Kova ranking or "
    "candidate-pool evidence axis only after Kova RS/fundamental forward rows "
    "carry PIT holder_count and total_value_usd fields that can later close with "
    "cash/SPY/QQQ replacement value."
)
CHANGE_TYPE = "identity_or_measurement_repair"
MECHANISM_FAMILY = "kova_multisource_forward_observation"
TRIAL_FAMILY = "kova_forward_sec13f_sponsorship_ledger"
TRIAL_VARIANT_ID = "post_exp015_local_sec13f_fallback_rows_v1"
CHANGED_VARIABLE = "kova_forward_sec13f_sponsorship_observation_ledger_v1"
NEW_EVIDENCE_TYPE = "pit_sec13f_sponsorship_forward_observation_rows"
NEW_EVIDENCE_AXIS = (
    "exp-20260624-015 local SEC13F holdings fallback with source_asof_date "
    "2026-06-11 joined to Kova 2026-06-13+ forward observation rows; no 13F "
    "threshold, holder-type, rank, top-N, hold, cooldown, notional, or live "
    "policy change."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260623-013",
    "exp-20260624-015",
    "exp-20260623-014",
]
CAUSAL_COMPONENTS = [
    "PIT local SEC13F holdings fallback",
    "Kova forward observation rows",
    "holder/value field capture",
    "no strategy behavior change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260624-016/exp_20260624_016_kova_forward_sec13f_sponsorship_ledger.json",
    "data/experiments/exp-20260624-016/kova_forward_sec13f_sponsorship_ledger.jsonl",
    "experiments/cards/exp-20260624-016.md",
    "experiments/manifests/exp-20260624-016.json",
    "experiments/tickets/exp-20260624-016.json",
    "experiments/logs/exp-20260624-016.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]
REQUIRED_LEDGER_FIELDS = [
    "observation_id",
    "asof_date",
    "ticker",
    "rs_proxy_status",
    "rs_proxy_rank_pct_20d",
    "companyfacts_growth_row_count",
    "sec13f_status",
    "sec13f_holder_count",
    "sec13f_total_value_usd",
    "sec13f_source_asof_date",
    "outcome_status",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default if default is not None else {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                rows.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(raw)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_id(parts: list[Any]) -> str:
    return hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:24]


def as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def round_or_none(value: Any, digits: int = 6) -> float | None:
    number = as_float(value)
    if number is None:
        return None
    return round(number, digits)


def date_from_filename(path: Path) -> str | None:
    match = re.search(r"(20\d{6})", path.name)
    if not match:
        return None
    raw = match.group(1)
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"


def iter_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    bad_json = 0
    if not path.exists():
        return rows, bad_json
    with path.open(encoding="utf-8-sig", errors="replace") as handle:
        for raw in handle:
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                bad_json += 1
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows, bad_json


def rows_by_ticker(path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    rows, bad_json = iter_jsonl(path)
    out: dict[str, dict[str, Any]] = {}
    status_counts: Counter[str] = Counter()
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            continue
        status = str(row.get("status") or row.get("growth_status") or "unknown")
        status_counts[status] += 1
        out[ticker] = row
    return out, {
        "path": repo_rel(path),
        "exists": path.exists(),
        "row_count": len(rows),
        "bad_json_rows": bad_json,
        "status_counts": dict(sorted(status_counts.items())),
    }


def summarize_companyfacts(path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    rows, bad_json = iter_jsonl(path)
    ticker_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "companyfacts_growth_row_count": 0,
            "companyfacts_growth_ok_raw_rows": 0,
            "latest_component_asof": {},
            "latest_component_yoy_growth": {},
        }
    )
    status_counts: Counter[str] = Counter()
    canonical_counts: Counter[str] = Counter()
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            continue
        canonical = str(row.get("canonical") or "")
        status = str(row.get("growth_status") or "unknown")
        status_counts[status] += 1
        if canonical:
            canonical_counts[canonical] += 1
        stats = ticker_stats[ticker]
        stats["companyfacts_growth_row_count"] += 1
        if status == "ok":
            stats["companyfacts_growth_ok_raw_rows"] += 1
        if canonical not in SELECTED_FUNDAMENTAL_COMPONENTS or status != "ok":
            continue
        yoy = round_or_none(row.get("yoy_growth"), 6)
        if yoy is None:
            continue
        asof_date = str(row.get("asof_date") or "")[:10]
        prev_asof = str(stats["latest_component_asof"].get(canonical) or "")
        if not prev_asof or asof_date >= prev_asof:
            stats["latest_component_asof"][canonical] = asof_date
            stats["latest_component_yoy_growth"][canonical] = yoy
    compact: dict[str, dict[str, Any]] = {}
    for ticker, stats in ticker_stats.items():
        growth = dict(sorted(stats["latest_component_yoy_growth"].items()))
        compact[ticker] = {
            "companyfacts_growth_row_count": stats["companyfacts_growth_row_count"],
            "companyfacts_growth_ok_raw_rows": stats["companyfacts_growth_ok_raw_rows"],
            "companyfacts_selected_ok_component_count": len(growth),
            "companyfacts_selected_positive_yoy_count": sum(
                1 for value in growth.values() if value is not None and value > 0
            ),
            "companyfacts_latest_component_yoy_growth": growth,
            "companyfacts_latest_component_asof": dict(
                sorted(stats["latest_component_asof"].items())
            ),
        }
    return compact, {
        "path": repo_rel(path),
        "exists": path.exists(),
        "row_count": len(rows),
        "bad_json_rows": bad_json,
        "status_counts": dict(sorted(status_counts.items())),
        "selected_components": list(SELECTED_FUNDAMENTAL_COMPONENTS),
        "selected_component_row_counts": {
            key: int(canonical_counts[key]) for key in SELECTED_FUNDAMENTAL_COMPONENTS
        },
    }


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = list(payload.get("windows") or [])
    generated = sum(int(window.get("signals_generated") or 0) for window in windows)
    survived = sum(int(window.get("signals_survived") or 0) for window in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(window.get("expected_value_score") or 0.0) for window in windows),
            4,
        ),
        "total_pnl": round(sum(float(window.get("total_pnl") or 0.0) for window in windows), 2),
        "trade_count": sum(int(window.get("trade_count") or 0) for window in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 4) if generated else None,
        "max_drawdown_pct_worst": max(
            (float(window.get("max_drawdown_pct") or 0.0) for window in windows),
            default=None,
        ),
        "windows": windows,
    }


def source_file_for(directory: Path, stem: str, asof_date: str) -> Path:
    return directory / f"{stem}_{asof_date.replace('-', '')}.jsonl"


def snapshot_files() -> list[Path]:
    files: list[Path] = []
    for path in sorted(SNAPSHOT_DIR.glob("kova_data_snapshot_*.json")):
        asof_date = date_from_filename(path)
        if asof_date and asof_date >= OBSERVATION_START:
            files.append(path)
    return files


def sec13f_rows_for(asof_date: str, tickers: list[str]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    rows, summary = sidecar.load_sec13f_holdings_summary_rows(
        non_ohlcv_dir=NON_OHLCV_DIR,
        asof_date=asof_date,
        tickers=tickers,
    )
    by_ticker = {str(row.get("ticker") or "").upper(): row for row in rows if row.get("ticker")}
    status_counts = Counter(str(row.get("status") or "unknown") for row in rows)
    return by_ticker, {
        "query_asof_date": asof_date,
        "row_count": len(rows),
        "status_counts": dict(sorted(status_counts.items())),
        "summary": summary,
    }


def quality_flags(
    rs_row: dict[str, Any] | None,
    fundamental_stats: dict[str, Any] | None,
    sec13f_row: dict[str, Any] | None,
    intraday_row: dict[str, Any] | None,
) -> list[str]:
    flags = ["pending_forward_close", "no_entry_date_target_price_by_design"]
    if not rs_row or rs_row.get("status") != "ok":
        flags.append("rs_proxy_not_ok")
    if not fundamental_stats or not fundamental_stats.get("companyfacts_selected_ok_component_count"):
        flags.append("no_companyfacts_growth_ok_components")
    if not sec13f_row or sec13f_row.get("status") != "ok":
        flags.append("sec13f_unavailable_or_skipped")
    if not intraday_row or intraday_row.get("status") != "ok":
        flags.append("intraday_unavailable_or_skipped")
    return flags


def build_observation_ledger() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ledger: list[dict[str, Any]] = []
    file_audit: dict[str, Any] = {
        "snapshot_files": [],
        "rs_proxy": [],
        "companyfacts_growth": [],
        "sec13f_fallback": [],
        "stale_sec13f_files": [],
        "intraday_ohlcv": [],
    }
    for snapshot_path in snapshot_files():
        snapshot = read_json(snapshot_path, {})
        asof_date = str(snapshot.get("asof_date") or date_from_filename(snapshot_path) or "")[:10]
        if not asof_date:
            continue
        rs_path = source_file_for(RS_DIR, "rs_proxy", asof_date)
        fundamentals_path = source_file_for(FUNDAMENTALS_DIR, "companyfacts_growth", asof_date)
        stale_sec13f_path = source_file_for(INSTITUTIONAL_DIR, "sec13f_ownership", asof_date)
        intraday_path = source_file_for(INTRADAY_DIR, "intraday_ohlcv", asof_date)

        snapshot_tickers = sorted(
            {str(ticker).upper() for ticker in snapshot.get("tickers") or [] if str(ticker).strip()}
        )
        rs_by_ticker, rs_audit = rows_by_ticker(rs_path)
        stale_sec13f_by_ticker, stale_sec13f_audit = rows_by_ticker(stale_sec13f_path)
        intraday_by_ticker, intraday_audit = rows_by_ticker(intraday_path)
        fundamentals_by_ticker, fundamentals_audit = summarize_companyfacts(fundamentals_path)
        tickers = sorted(set(snapshot_tickers) | set(rs_by_ticker))
        sec13f_by_ticker, sec13f_audit = sec13f_rows_for(asof_date, tickers)

        file_audit["snapshot_files"].append(
            {
                "path": repo_rel(snapshot_path),
                "asof_date": asof_date,
                "ticker_count": len(snapshot_tickers),
                "status": snapshot.get("status"),
                "schema_version": snapshot.get("schema_version"),
            }
        )
        file_audit["rs_proxy"].append(rs_audit)
        file_audit["companyfacts_growth"].append(fundamentals_audit)
        file_audit["sec13f_fallback"].append(sec13f_audit)
        file_audit["stale_sec13f_files"].append(stale_sec13f_audit)
        file_audit["intraday_ohlcv"].append(intraday_audit)

        for ticker in tickers:
            rs_row = rs_by_ticker.get(ticker)
            stale_sec13f_row = stale_sec13f_by_ticker.get(ticker)
            sec13f_row = sec13f_by_ticker.get(ticker)
            intraday_row = intraday_by_ticker.get(ticker)
            fundamental_stats = fundamentals_by_ticker.get(ticker)
            flags = quality_flags(rs_row, fundamental_stats, sec13f_row, intraday_row)
            source_asof = (sec13f_row or {}).get("asof_date") or (
                sec13f_audit.get("summary") or {}
            ).get("source_asof_date")
            ledger.append(
                {
                    "schema_version": 1,
                    "experiment_id": EXPERIMENT_ID,
                    "rule_version": CHANGED_VARIABLE,
                    "observation_id": stable_id([CHANGED_VARIABLE, asof_date, ticker]),
                    "source": "kova_multisource_forward_snapshot",
                    "alpha_candidate_state": "observation_only_pending_outcome",
                    "asof_date": asof_date,
                    "symbol": ticker,
                    "ticker": ticker,
                    "source_snapshot_file": repo_rel(snapshot_path),
                    "rs_proxy_source_file": repo_rel(rs_path),
                    "companyfacts_growth_source_file": repo_rel(fundamentals_path),
                    "stale_sec13f_source_file": repo_rel(stale_sec13f_path),
                    "sec13f_source_file": (sec13f_row or {}).get("source_snapshot")
                    or (sec13f_audit.get("summary") or {}).get("source_snapshot"),
                    "intraday_source_file": repo_rel(intraday_path),
                    "rs_proxy_status": (rs_row or {}).get("status"),
                    "rs_proxy_rank_pct_20d": round_or_none((rs_row or {}).get("rs_proxy_rank_pct_20d"), 6),
                    "rs_proxy_rank_pct_60d": round_or_none((rs_row or {}).get("rs_proxy_rank_pct_60d"), 6),
                    "rs_proxy_rank_pct_120d": round_or_none((rs_row or {}).get("rs_proxy_rank_pct_120d"), 6),
                    "excess_ret_20d_vs_spy": round_or_none((rs_row or {}).get("excess_ret_20d_vs_spy"), 6),
                    "excess_ret_60d_vs_spy": round_or_none((rs_row or {}).get("excess_ret_60d_vs_spy"), 6),
                    "excess_ret_120d_vs_spy": round_or_none((rs_row or {}).get("excess_ret_120d_vs_spy"), 6),
                    "available_window_count": (rs_row or {}).get("available_window_count"),
                    "companyfacts_growth_row_count": (fundamental_stats or {}).get(
                        "companyfacts_growth_row_count", 0
                    ),
                    "companyfacts_growth_ok_raw_rows": (fundamental_stats or {}).get(
                        "companyfacts_growth_ok_raw_rows", 0
                    ),
                    "companyfacts_selected_ok_component_count": (fundamental_stats or {}).get(
                        "companyfacts_selected_ok_component_count", 0
                    ),
                    "companyfacts_selected_positive_yoy_count": (fundamental_stats or {}).get(
                        "companyfacts_selected_positive_yoy_count", 0
                    ),
                    "companyfacts_latest_component_yoy_growth": (fundamental_stats or {}).get(
                        "companyfacts_latest_component_yoy_growth", {}
                    ),
                    "companyfacts_latest_component_asof": (fundamental_stats or {}).get(
                        "companyfacts_latest_component_asof", {}
                    ),
                    "stale_sec13f_status": (stale_sec13f_row or {}).get("status"),
                    "stale_sec13f_reason": (stale_sec13f_row or {}).get("reason"),
                    "sec13f_status": (sec13f_row or {}).get("status"),
                    "sec13f_reason": (sec13f_row or {}).get("reason"),
                    "sec13f_provider": (sec13f_row or {}).get("provider"),
                    "sec13f_holder_count": (sec13f_row or {}).get("holder_count"),
                    "sec13f_position_row_count": (sec13f_row or {}).get("position_row_count"),
                    "sec13f_total_shares": round_or_none((sec13f_row or {}).get("total_shares"), 2),
                    "sec13f_total_value_usd": round_or_none((sec13f_row or {}).get("total_value_usd"), 2),
                    "sec13f_report_period": (sec13f_row or {}).get("report_period"),
                    "sec13f_window_label": (sec13f_row or {}).get("window_label"),
                    "sec13f_source_asof_date": source_asof,
                    "sec13f_query_asof_date": (sec13f_row or {}).get("query_asof_date") or asof_date,
                    "sec13f_ticker_mapping_status": (sec13f_row or {}).get("ticker_mapping_status"),
                    "intraday_status": (intraday_row or {}).get("status"),
                    "intraday_reason": (intraday_row or {}).get("reason"),
                    "entry_date": None,
                    "target_price": None,
                    "planned_entry_date": None,
                    "planned_exit_date": None,
                    "entry_date_resolution": "not_scheduled_observation_only",
                    "target_price_resolution": "not_scheduled_observation_only",
                    "outcome_status": "pending_forward_close",
                    "forward_5d_return_pct": None,
                    "forward_10d_return_pct": None,
                    "replacement_value_vs_cash_usd": None,
                    "replacement_value_vs_spy_usd": None,
                    "replacement_value_vs_qqq_usd": None,
                    "quality_flags": flags,
                    "trade_enabled": False,
                    "alters_orders": False,
                }
            )
    return ledger, file_audit


def field_coverage(rows: list[dict[str, Any]], fields: list[str]) -> dict[str, dict[str, Any]]:
    total = len(rows)
    out: dict[str, dict[str, Any]] = {}
    for field in fields:
        present = sum(1 for row in rows if row.get(field) not in (None, ""))
        out[field] = {
            "present_rows": present,
            "scanned_rows": total,
            "coverage": round(present / total, 6) if total else 0.0,
        }
    return out


def num_summary(values: list[float]) -> dict[str, Any]:
    clean = [value for value in values if math.isfinite(value)]
    if not clean:
        return {"n": 0, "min": None, "median": None, "mean": None, "max": None}
    return {
        "n": len(clean),
        "min": round(min(clean), 4),
        "median": round(median(clean), 4),
        "mean": round(sum(clean) / len(clean), 4),
        "max": round(max(clean), 4),
    }


def ledger_summary(ledger: list[dict[str, Any]], file_audit: dict[str, Any]) -> dict[str, Any]:
    dates = sorted({str(row["asof_date"]) for row in ledger})
    tickers = sorted({str(row["ticker"]) for row in ledger})
    ids = [str(row.get("observation_id") or "") for row in ledger]
    flags: Counter[str] = Counter()
    sec13f_status: Counter[str] = Counter()
    stale_sec13f_status: Counter[str] = Counter()
    intraday_status: Counter[str] = Counter()
    source_asof_violations = 0
    for row in ledger:
        for flag in row.get("quality_flags") or []:
            flags[str(flag)] += 1
        sec13f_status[str(row.get("sec13f_status") or "missing")] += 1
        stale_sec13f_status[str(row.get("stale_sec13f_status") or "missing")] += 1
        intraday_status[str(row.get("intraday_status") or "missing")] += 1
        source_asof = str(row.get("sec13f_source_asof_date") or "")
        if source_asof and source_asof > str(row.get("asof_date") or ""):
            source_asof_violations += 1
    sec13f_ok = [row for row in ledger if row.get("sec13f_status") == "ok"]
    holder_values = [as_float(row.get("sec13f_holder_count")) for row in sec13f_ok]
    value_usd = [as_float(row.get("sec13f_total_value_usd")) for row in sec13f_ok]
    holder_values = [value for value in holder_values if value is not None]
    value_usd = [value for value in value_usd if value is not None]
    return {
        "ledger_rows": len(ledger),
        "ticker_count": len(tickers),
        "asof_date_start": dates[0] if dates else None,
        "asof_date_end": dates[-1] if dates else None,
        "asof_date_count": len(dates),
        "duplicate_observation_ids": len(ids) - len(set(ids)),
        "pending_outcome_rows": sum(
            1 for row in ledger if row.get("outcome_status") == "pending_forward_close"
        ),
        "rs_proxy_ok_rows": sum(1 for row in ledger if row.get("rs_proxy_status") == "ok"),
        "companyfacts_with_selected_components": sum(
            1 for row in ledger if row.get("companyfacts_selected_ok_component_count", 0) > 0
        ),
        "companyfacts_with_any_positive_yoy": sum(
            1 for row in ledger if row.get("companyfacts_selected_positive_yoy_count", 0) > 0
        ),
        "sec13f_ok_rows": len(sec13f_ok),
        "sec13f_ok_coverage": round(len(sec13f_ok) / len(ledger), 6) if ledger else 0.0,
        "sec13f_status_counts": dict(sorted(sec13f_status.items())),
        "stale_sec13f_status_counts": dict(sorted(stale_sec13f_status.items())),
        "sec13f_source_asof_dates": sorted(
            {str(row.get("sec13f_source_asof_date")) for row in sec13f_ok if row.get("sec13f_source_asof_date")}
        ),
        "sec13f_source_asof_violations": source_asof_violations,
        "sec13f_holder_count_summary": num_summary(holder_values),
        "sec13f_total_value_usd_summary": num_summary(value_usd),
        "intraday_status_counts": dict(sorted(intraday_status.items())),
        "quality_flag_counts": dict(sorted(flags.items())),
        "field_coverage": field_coverage(ledger, REQUIRED_LEDGER_FIELDS),
        "source_file_audit": file_audit,
        "sample_observations": ledger[:10],
    }


def load_ticket_prediction() -> dict[str, Any] | None:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    return prediction if isinstance(prediction, dict) else None


def calibration(prediction: dict[str, Any] | None, success: bool, failed: list[str]) -> dict[str, Any]:
    probability = as_float((prediction or {}).get("success_probability"))
    actual = 1 if success else 0
    return {
        "actual_success": actual,
        "actual_decision": (
            "accepted_measurement_repair_kova_forward_sec13f_sponsorship_ledger"
            if success
            else "blocked_kova_forward_sec13f_sponsorship_ledger"
        ),
        "predicted_success_probability": probability,
        "brier_score": round((probability - actual) ** 2, 6) if probability is not None else None,
        "predicted_failure_modes": (prediction or {}).get("main_failure_modes") or [],
        "realized_failure_modes": failed,
        "surprise_note": (
            "The local SEC13F fallback produced PIT-valid holder/value coverage for "
            "Kova forward rows, matching the pre-run measurement-repair expectation."
            if success
            else "The repaired SEC13F fallback did not produce enough PIT-valid Kova "
            "forward rows to support later attribution."
        ),
    }


def build_payload() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    baseline = baseline_metrics()
    ledger, file_audit = build_observation_ledger()
    summary = ledger_summary(ledger, file_audit)
    failed: list[str] = []
    if summary["ledger_rows"] <= 0:
        failed.append("no_ledger_rows")
    if summary["duplicate_observation_ids"] != 0:
        failed.append("duplicate_observation_ids")
    if summary["asof_date_count"] < 5:
        failed.append("too_few_forward_asof_dates")
    if summary["sec13f_ok_rows"] <= 0:
        failed.append("no_sec13f_ok_rows")
    if summary["sec13f_ok_coverage"] < MIN_SEC13F_OK_COVERAGE:
        failed.append("sec13f_ok_coverage_below_floor")
    if summary["sec13f_source_asof_violations"] != 0:
        failed.append("sec13f_source_asof_after_observation_date")
    for field, coverage in summary["field_coverage"].items():
        if coverage["coverage"] < 0.50:
            failed.append(f"field_{field}_coverage_below_50pct")
    success = not failed
    decision = (
        "accepted_measurement_repair_kova_forward_sec13f_sponsorship_ledger"
        if success
        else "blocked_kova_forward_sec13f_sponsorship_ledger"
    )
    status = "accepted_measurement_repair" if success else "blocked"
    prediction = load_ticket_prediction()
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "status": status,
        "decision": decision,
        "accepted": success,
        "accepted_alpha": False,
        "alpha_ready": False,
        "observed_only_lead": False,
        "lane": "measurement_repair",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "measurement_repair",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "calibration": calibration(prediction, success, failed),
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260623-013": (
                    "Accepted Kova forward observation ledger but all SEC13F rows "
                    "were skipped because no ZIP/year-quarter/local fallback was available."
                ),
                "exp-20260624-015": (
                    "Accepted measurement repair proving the local SEC13F holdings "
                    "summary can provide non-skipped rows with source_asof_date 2026-06-11."
                ),
                "exp-20260623-014": (
                    "Rejected RS+growth closed-forward monotonicity. This run does "
                    "not retry RS/growth thresholds or use pre-2026-06-11 rows."
                ),
                "novelty_gate": (
                    "Reservation passed: nearest 13F/Kova neighbors were below "
                    "the blocking threshold and this is measurement repair, not a "
                    "candidate-pool scan."
                ),
            },
            "3_single_policy_bundle": (
                "One measurement bundle: rebuild an experiment-owned Kova forward "
                "observation ledger with PIT-valid SEC13F holder_count, "
                "position_row_count, total_value_usd, total_shares, source_asof, "
                "and source snapshot fields."
            ),
            "4_acceptance_standard": (
                "Accept only if the ledger has multi-date rows, duplicate IDs are "
                "zero, SEC13F ok coverage is at least 50%, all SEC13F source_asof "
                "dates are <= observation asof dates, and strategy delta remains zero."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "observation_start": OBSERVATION_START,
            "min_sec13f_ok_coverage": MIN_SEC13F_OK_COVERAGE,
            "kova_root": repo_rel(KOVA_ROOT),
            "non_ohlcv_dir": repo_rel(NON_OHLCV_DIR),
            "ledger_output": repo_rel(LEDGER_JSONL),
            "required_ledger_fields": REQUIRED_LEDGER_FIELDS,
            "selected_fundamental_components": list(SELECTED_FUNDAMENTAL_COMPONENTS),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
        },
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_metrics": baseline,
        },
        "gate2": {
            "dependencies_validated": success,
            "fields_checked": REQUIRED_LEDGER_FIELDS
            + ["entry_date", "target_price", "planned_entry_date", "planned_exit_date"],
            "field_coverage": summary["field_coverage"],
            "entry_date_present": False,
            "target_price_present": False,
            "entry_date_target_price_note": (
                "Kova observations are not executable candidates. entry_date and "
                "target_price stay null; future settlement will define diagnostic "
                "entry/exit dates without scheduling orders."
            ),
            "ledger_rows": summary["ledger_rows"],
            "asof_date_range": {
                "start": summary["asof_date_start"],
                "end": summary["asof_date_end"],
                "count": summary["asof_date_count"],
            },
            "ticker_count": summary["ticker_count"],
            "failed_reasons": failed,
        },
        "gate3": {
            "filter_added": False,
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "note": "No executable filter or strategy rule was added.",
        },
        "gate4": {
            "passed": success,
            "decision": decision,
            "failed_reasons": failed,
            "acceptance_checks": {
                "ledger_rows_positive": summary["ledger_rows"] > 0,
                "duplicate_observation_ids_zero": summary["duplicate_observation_ids"] == 0,
                "multi_date_forward_surface": summary["asof_date_count"] >= 5,
                "sec13f_ok_rows_present": summary["sec13f_ok_rows"] > 0,
                "sec13f_ok_coverage_floor": summary["sec13f_ok_coverage"] >= MIN_SEC13F_OK_COVERAGE,
                "sec13f_source_asof_valid": summary["sec13f_source_asof_violations"] == 0,
                "strategy_behavior_changed": False,
            },
            "before_after_strategy_delta": {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "max_drawdown_pct": 0.0,
            },
            "strategy_rerun_required": False,
            "measurement_repair": True,
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "ledger_rows_created": summary["ledger_rows"],
            "pending_outcome_rows": summary["pending_outcome_rows"],
            "sec13f_ok_rows_delta_vs_exp013": summary["sec13f_ok_rows"],
        },
        "ledger_summary": summary,
        "production_impact": {
            "trade_enabled": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_exposed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "watchlist_changed": False,
            "llm_decision_boundary_changed": False,
            "replay_only": False,
            "live_ready": False,
            "parity_note": (
                "This experiment writes an experiment-owned observation ledger only. "
                "It reads the repaired Kova sidecar helper and does not modify "
                "data/kova daily files or any execution path."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The exp-20260624-015 fallback can now attach PIT-valid SEC13F "
                "holder/value context to Kova 2026-06-13+ observation rows. This "
                "repairs the exp-20260623-013 all-skipped SEC13F caveat but does "
                "not prove alpha because the rows are still pending forward close."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry Kova 13F holder_count, total_value_usd, ownership, "
                "RS, Companyfacts, top-N, hold, cooldown, notional, or allocator "
                "thresholds from this open ledger. The next alpha step must use "
                "closed replacement-value rows or materially richer PIT manager/"
                "flow provenance."
            ),
            "new_evidence_required": (
                "Close Kova 2026-06-13+ rows with cash/SPY/QQQ replacement value, "
                "then test a predeclared sponsorship monotonicity or interaction "
                "hypothesis. Historical canonical-window promotion requires a "
                "separate shared helper with PIT 13F coverage."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(LEDGER_JSONL),
            repo_rel(OUT_JSON),
            repo_rel(BASELINE_RESULT),
            "experiments/logs/exp-20260623-013.json",
            "experiments/logs/exp-20260624-015.json",
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LEDGER_JSONL),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
        ],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "lean_quality_passed": success,
        "artifact": repo_rel(OUT_JSON),
        "ledger": repo_rel(LEDGER_JSONL),
        "log": repo_rel(LOG_JSON),
    }
    return payload, ledger


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload["ledger_summary"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "alpha_ready": False,
        "observed_only_lead": False,
        "lane": payload["lane"],
        "owner": payload["owner"],
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis": payload["alpha_hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "single_causal_variable": payload["single_causal_variable"],
        "causal_components": payload["causal_components"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "new_evidence_axis": payload["new_evidence_axis"],
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "pre_run_questions": payload["pre_run_questions"],
        "parameters": payload["parameters"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "ledger_summary": {
            "ledger_rows": summary["ledger_rows"],
            "asof_date_start": summary["asof_date_start"],
            "asof_date_end": summary["asof_date_end"],
            "asof_date_count": summary["asof_date_count"],
            "ticker_count": summary["ticker_count"],
            "duplicate_observation_ids": summary["duplicate_observation_ids"],
            "pending_outcome_rows": summary["pending_outcome_rows"],
            "rs_proxy_ok_rows": summary["rs_proxy_ok_rows"],
            "companyfacts_with_selected_components": summary[
                "companyfacts_with_selected_components"
            ],
            "sec13f_ok_rows": summary["sec13f_ok_rows"],
            "sec13f_ok_coverage": summary["sec13f_ok_coverage"],
            "sec13f_status_counts": summary["sec13f_status_counts"],
            "stale_sec13f_status_counts": summary["stale_sec13f_status_counts"],
            "sec13f_source_asof_dates": summary["sec13f_source_asof_dates"],
            "sec13f_source_asof_violations": summary["sec13f_source_asof_violations"],
            "sec13f_holder_count_summary": summary["sec13f_holder_count_summary"],
            "sec13f_total_value_usd_summary": summary["sec13f_total_value_usd_summary"],
            "intraday_status_counts": summary["intraday_status_counts"],
            "quality_flag_counts": summary["quality_flag_counts"],
            "sample_observations": summary["sample_observations"][:3],
        },
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "related_files": payload["related_files"],
        "changed_files": payload["changed_files"],
        "allowed_write_scope": payload["allowed_write_scope"],
        "reproduction_commands": payload["reproduction_commands"],
        "anti_js": payload["anti_js"],
        "lean_quality_passed": payload["lean_quality_passed"],
        "artifact": repo_rel(OUT_JSON),
        "ledger": repo_rel(LEDGER_JSONL),
        "log": repo_rel(LOG_JSON),
    }


def build_card(payload: dict[str, Any]) -> str:
    summary = payload["ledger_summary"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: Kova forward SEC13F sponsorship ledger",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Ledger rows: `{summary['ledger_rows']}`",
            f"- As-of dates: `{summary['asof_date_start']}` to `{summary['asof_date_end']}`",
            f"- Tickers: `{summary['ticker_count']}`",
            f"- SEC13F ok rows: `{summary['sec13f_ok_rows']}`",
            f"- SEC13F coverage: `{summary['sec13f_ok_coverage']:.2%}`",
            f"- SEC13F source as-of dates: `{', '.join(summary['sec13f_source_asof_dates'])}`",
            "- Strategy behavior changed: `false`",
            "- Production orders changed: `false`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Next Evidence",
            "",
            payload["post_run_reflection"]["new_evidence_required"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LEDGER_JSONL,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        BASELINE_RESULT,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "ledger": repo_rel(LEDGER_JSONL),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any], ledger: list[dict[str, Any]]) -> None:
    write_jsonl(LEDGER_JSONL, ledger)
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)
    registry_result = {
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "alpha_ready": False,
        "observed_only_lead": False,
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "ledger": repo_rel(LEDGER_JSONL),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "gate4": payload["gate4"],
        "ledger_summary": log_record["ledger_summary"],
        "calibration": payload["calibration"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=payload["prediction"],
        result=registry_result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "change_type": payload["change_type"],
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": payload["single_causal_variable"],
            "changed_variable": payload["changed_variable"],
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "new_evidence_axis": payload["new_evidence_axis"],
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "ledger": repo_rel(LEDGER_JSONL),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "related_files": payload["related_files"],
            "changed_files": payload["changed_files"],
            "allowed_write_scope": ALLOWED_WRITE_SCOPE,
            "lean_quality_passed": payload["lean_quality_passed"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload, ledger = build_payload()
    persist(payload, ledger)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "ledger_rows": payload["ledger_summary"]["ledger_rows"],
                "asof_date_start": payload["ledger_summary"]["asof_date_start"],
                "asof_date_end": payload["ledger_summary"]["asof_date_end"],
                "ticker_count": payload["ledger_summary"]["ticker_count"],
                "sec13f_ok_rows": payload["ledger_summary"]["sec13f_ok_rows"],
                "sec13f_ok_coverage": payload["ledger_summary"]["sec13f_ok_coverage"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": payload["artifact"],
                "ledger": repo_rel(LEDGER_JSONL),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
