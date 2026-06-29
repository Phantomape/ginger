"""exp-20260629-003: Form 4 sale-overhang forward context logger.

This measurement-repair runner tags current accepted-core/default-off paper
rows with the fixed PIT Form 4 sale-overhang context from exp-20260628-014. It
does not change entry, exit, ranking, sizing, risk budget, or order behavior.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result, save_experiment_log_entry  # noqa: E402


EXPERIMENT_ID = "exp-20260629-003"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "form4_sale_overhang_forward_context_logger"
RUNNER = f"quant/experiments/exp_20260629_003_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

CHANGED_VARIABLE = "form4_sale_overhang_forward_context_logger_v1"
TRIAL_FAMILY = "form4_sale_overhang_forward_context_logger"
TRIAL_VARIANT_ID = "current_paper_rows_form4_context_v1"
MECHANISM_FAMILY = "production_visible_form4_selling_overhang_forward_context"
CHANGE_TYPE = "identity_or_measurement_repair"
IMPLEMENTATION_MODE = "experiment_owned_context_logger"
NEW_EVIDENCE_TYPE = "alpha_enabling_forward_context_logger"

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
NON_OHLCV_DIR = REPO_ROOT / "data" / "non_ohlcv"
PAPER_ROOT = REPO_ROOT / "data" / "paper_sleeves"
DAILY_TREND_DIR = REPO_ROOT / "data" / "daily" / "signals" / "trend"
FORWARD_REPLACEMENT_JSONL = PAPER_ROOT / "forward_replacement_value.jsonl"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260629_003_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

ALPHA_HYPOTHESIS = (
    "Risk allocation: fixed PIT Form 4 sale, 10b5-1, and officer-sale "
    "overhang may identify accepted-core/default-off entries with worse loss "
    "tail, but an alpha response needs prospective context rows and closed "
    "forward replacement value before any scalar, veto, or ranking change."
)

CAUSAL_COMPONENTS = [
    "current accepted-core/default-off paper row discovery",
    "fixed PIT 10-day Form4 sale-overhang context join",
    "experiment-owned forward context ledger",
    "machine-checkable reopen condition",
    "no strategy behavior change",
]

NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260628-014",
    "exp-20260625-013",
    "exp-20260620-004",
    "exp-20260503-017",
]

LOOKBACK_CALENDAR_DAYS = 10
HIGH_SALE_VALUE_USD = 5_000_000.0
HIGH_OFFICER_SALE_VALUE_USD = 1_000_000.0
HIGH_TEN_B5_SALE_ROWS = 1

ROW_LIST_KEYS = [
    "candidates",
    "new_pending_entries",
    "pending_entries",
    "open_positions",
    "opened_positions_this_run",
    "filled_today",
    "filled_entries",
    "closed_positions_today",
    "closed_positions_this_run",
    "closed_positions",
    "closed_today",
    "skipped_entries_today",
    "rejected_candidates",
]
ROW_SINGLE_KEYS = ["candidate", "selected_candidate", "entry", "position"]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def repo_rel(path: Path | str) -> str:
    p = Path(path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    return str(p.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(v) for v in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def as_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def round_float(value: Any, digits: int = 6) -> float | None:
    number = as_float(value)
    if number is None:
        return None
    return round(number, digits)


def parse_day(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except ValueError:
        return None


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def baseline_metrics() -> dict[str, Any]:
    raw = read_json(BASELINE_RESULT, {})
    if not isinstance(raw, dict):
        return {"baseline_result_file": repo_rel(BASELINE_RESULT), "loaded": False}
    windows: list[dict[str, Any]] = []
    for row in raw.get("windows") or []:
        if not isinstance(row, dict):
            continue
        windows.append(
            {
                "label": row.get("label"),
                "start": row.get("start"),
                "end": row.get("end"),
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
        )
    if not windows:
        return {"baseline_result_file": repo_rel(BASELINE_RESULT), "loaded": True}
    signals_generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    signals_survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "loaded": True,
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows), 6
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": signals_generated,
        "signals_survived": signals_survived,
        "survival_rate": (
            round(signals_survived / signals_generated, 6) if signals_generated else None
        ),
        "max_drawdown_pct": max(float(row.get("max_drawdown_pct") or 0.0) for row in windows),
        "windows": windows,
    }


def form4_row_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("accession_number"),
        row.get("ticker") or row.get("issuer_trading_symbol"),
        row.get("owner_cik"),
        row.get("transaction_date"),
        row.get("transaction_code"),
        row.get("acquired_disposed_code"),
        row.get("security_title"),
        row.get("table"),
        row.get("shares"),
        row.get("price"),
    )


def load_form4_index() -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen: set[tuple[Any, ...]] = set()
    files = sorted(NON_OHLCV_DIR.glob("form4_transactions_*.jsonl"))
    bad_json_rows = 0
    raw_rows = 0
    rows_loaded = 0
    usable_days: list[date] = []
    transaction_code_counts: Counter[str] = Counter()

    for path in files:
        try:
            lines = path.read_text(encoding="utf-8-sig").splitlines()
        except OSError:
            continue
        for line in lines:
            if not line.strip():
                continue
            raw_rows += 1
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                bad_json_rows += 1
                continue
            if not isinstance(row, dict):
                continue
            ticker = str(row.get("ticker") or row.get("issuer_trading_symbol") or "").upper()
            usable_trade_date = parse_day(row.get("usable_trade_date"))
            if not ticker or usable_trade_date is None:
                continue
            key = form4_row_key(row)
            if key in seen:
                continue
            seen.add(key)
            code = str(row.get("transaction_code") or "").upper()
            record = {
                "ticker": ticker,
                "usable_trade_date": usable_trade_date,
                "transaction_date": parse_day(row.get("transaction_date")),
                "accepted_at": row.get("accepted_at"),
                "accession_number": row.get("accession_number"),
                "owner_cik": row.get("owner_cik"),
                "owner_name": row.get("owner_name"),
                "transaction_code": code,
                "acquired_disposed_code": row.get("acquired_disposed_code"),
                "transaction_value": as_float(row.get("transaction_value")),
                "shares": as_float(row.get("shares")),
                "price": as_float(row.get("price")),
                "ten_b5_1_flag": bool(row.get("10b5_1_flag")),
                "is_officer": bool(row.get("is_officer")),
                "is_director": bool(row.get("is_director")),
                "is_10pct_owner": bool(row.get("is_10pct_owner")),
                "open_market_purchase_flag": bool(row.get("open_market_purchase_flag")),
                "option_exercise_flag": bool(row.get("option_exercise_flag")),
                "source_file": repo_rel(path),
            }
            by_ticker[ticker].append(record)
            transaction_code_counts[code] += 1
            usable_days.append(usable_trade_date)
            rows_loaded += 1

    for rows in by_ticker.values():
        rows.sort(key=lambda row: row["usable_trade_date"])

    return by_ticker, {
        "form4_dir": repo_rel(NON_OHLCV_DIR),
        "source_file_count": len(files),
        "raw_jsonl_rows": raw_rows,
        "deduped_rows_loaded": rows_loaded,
        "bad_json_rows": bad_json_rows,
        "ticker_count": len(by_ticker),
        "min_usable_trade_date": min(usable_days).isoformat() if usable_days else None,
        "max_usable_trade_date": max(usable_days).isoformat() if usable_days else None,
        "transaction_code_counts": dict(sorted(transaction_code_counts.items())),
    }


def form4_rows_for_context(
    index: dict[str, list[dict[str, Any]]], ticker: str, context_day: date | None
) -> list[dict[str, Any]]:
    if context_day is None:
        return []
    start = context_day - timedelta(days=LOOKBACK_CALENDAR_DAYS)
    rows = []
    for row in index.get(ticker.upper(), []):
        usable_day = row["usable_trade_date"]
        if start <= usable_day <= context_day:
            rows.append(row)
    return rows


def summarize_form4_context(rows: list[dict[str, Any]]) -> dict[str, Any]:
    sale_rows = [row for row in rows if row.get("transaction_code") == "S"]
    tax_rows = [row for row in rows if row.get("transaction_code") == "F"]
    purchase_rows = [
        row
        for row in rows
        if row.get("transaction_code") == "P" or row.get("open_market_purchase_flag")
    ]
    exercise_rows = [row for row in rows if row.get("option_exercise_flag")]
    ten_b5_sale_rows = [row for row in sale_rows if row.get("ten_b5_1_flag")]
    officer_sale_rows = [row for row in sale_rows if row.get("is_officer")]

    def value_sum(selected: list[dict[str, Any]]) -> float:
        return sum(float(row.get("transaction_value") or 0.0) for row in selected)

    sale_value = value_sum(sale_rows)
    tax_value = value_sum(tax_rows)
    purchase_value = value_sum(purchase_rows)
    officer_sale_value = value_sum(officer_sale_rows)
    ten_b5_sale_value = value_sum(ten_b5_sale_rows)

    high = (
        sale_value >= HIGH_SALE_VALUE_USD
        or officer_sale_value >= HIGH_OFFICER_SALE_VALUE_USD
        or len(ten_b5_sale_rows) >= HIGH_TEN_B5_SALE_ROWS
    )
    if high:
        bucket = "high_sale_overhang"
    elif sale_rows or tax_rows:
        bucket = "moderate_or_routine_disposal"
    else:
        bucket = "no_sale_overhang"

    return {
        "form4_sale_overhang_bucket": bucket,
        "form4_lookback_calendar_days": LOOKBACK_CALENDAR_DAYS,
        "form4_rows": len(rows),
        "form4_sale_rows": len(sale_rows),
        "form4_tax_withholding_rows": len(tax_rows),
        "form4_purchase_rows": len(purchase_rows),
        "form4_option_exercise_rows": len(exercise_rows),
        "form4_ten_b5_sale_rows": len(ten_b5_sale_rows),
        "form4_officer_sale_rows": len(officer_sale_rows),
        "form4_sale_value_usd": round_float(sale_value, 2),
        "form4_tax_withholding_value_usd": round_float(tax_value, 2),
        "form4_purchase_value_usd": round_float(purchase_value, 2),
        "form4_officer_sale_value_usd": round_float(officer_sale_value, 2),
        "form4_ten_b5_sale_value_usd": round_float(ten_b5_sale_value, 2),
        "form4_net_sale_value_usd": round_float(sale_value - purchase_value, 2),
        "form4_unique_owners": len({row.get("owner_cik") for row in rows if row.get("owner_cik")}),
        "form4_latest_usable_trade_date": (
            max(row["usable_trade_date"] for row in rows).isoformat() if rows else None
        ),
        "form4_sample_accessions": sorted(
            {str(row.get("accession_number")) for row in rows if row.get("accession_number")}
        )[:8],
    }


def latest_jsonl_row(path: Path) -> tuple[dict[str, Any] | None, int, int]:
    row_count = 0
    bad_rows = 0
    latest: dict[str, Any] | None = None
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row_count += 1
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError:
                    bad_rows += 1
                    continue
                if isinstance(parsed, dict):
                    latest = parsed
    except OSError:
        return None, 0, 0
    return latest, row_count, bad_rows


def target_price_from_row(row: dict[str, Any]) -> float | None:
    for key in ("target_price", "target_price_reconstructed", "signal_target_price"):
        target = round_float(row.get(key), 4)
        if target is not None:
            return target
    candidate = row.get("candidate")
    if isinstance(candidate, dict):
        target = target_price_from_row(candidate)
        if target is not None:
            return target
    exit_levels = row.get("exit_levels")
    if isinstance(exit_levels, dict):
        target = round_float(
            exit_levels.get("target_price") or exit_levels.get("signal_target_price"),
            4,
        )
        if target is not None:
            return target
    entry = as_float(row.get("entry_price"))
    stop = as_float(row.get("stop_price"))
    mult = as_float(row.get("target_mult_used"))
    if entry is None or stop is None or mult is None:
        return None
    risk_per_share = max(entry - stop, 0.0)
    if risk_per_share <= 0:
        return None
    return round_float(entry + risk_per_share * mult, 4)


def pick_str(row: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        if value is None or value == "":
            continue
        return str(value)
    return None


def row_date(row: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        day = parse_day(row.get(key))
        if day is not None:
            return day.isoformat()
    return None


def normalise_candidate_row(
    source_surface: str,
    source_path: Path,
    row_kind: str,
    payload_asof: str | None,
    row: dict[str, Any],
) -> dict[str, Any] | None:
    nested_candidate = row.get("candidate") if isinstance(row.get("candidate"), dict) else {}
    ticker = (
        pick_str(row, "ticker", "symbol")
        or pick_str(nested_candidate, "ticker", "symbol")
        or ""
    ).upper()
    if not ticker:
        return None

    signal_date = (
        row_date(row, "signal_date", "date", "asof_date", "as_of")
        or row_date(nested_candidate, "signal_date", "date", "asof_date", "as_of")
        or payload_asof
    )
    entry_date = row_date(row, "entry_date", "paper_entry_date", "fill_date")
    context_as_of = entry_date or signal_date or payload_asof
    if context_as_of is None:
        return None

    decision_id = (
        pick_str(row, "decision_id", "observation_id", "entry_id")
        or pick_str(nested_candidate, "decision_id", "observation_id", "entry_id")
        or f"{source_surface}:{row_kind}:{context_as_of}:{ticker}"
    )
    target_price = target_price_from_row(row)
    if target_price is None and isinstance(nested_candidate, dict):
        target_price = target_price_from_row(nested_candidate)

    trade_enabled_value = row.get("trade_enabled")
    if trade_enabled_value is None and isinstance(nested_candidate, dict):
        trade_enabled_value = nested_candidate.get("trade_enabled")

    return {
        "ticker": ticker,
        "source_surface": source_surface,
        "source_file": repo_rel(source_path),
        "row_kind": row_kind,
        "decision_id": decision_id,
        "signal_date": signal_date,
        "entry_date": entry_date,
        "context_as_of": context_as_of,
        "target_price": target_price,
        "entry_price": round_float(row.get("entry_price"), 4)
        or round_float(nested_candidate.get("entry_price"), 4),
        "stop_price": round_float(row.get("stop_price"), 4)
        or round_float(nested_candidate.get("stop_price"), 4),
        "notional_usd": round_float(
            row.get("notional")
            or row.get("paper_notional_usd")
            or row.get("safe_paper_notional_usd")
            or row.get("intended_notional")
            or nested_candidate.get("paper_notional_usd")
            or nested_candidate.get("safe_paper_notional_usd"),
            2,
        ),
        "status": pick_str(row, "status", "candidate_status", "paper_status") or row_kind,
        "strategy": pick_str(row, "strategy") or pick_str(nested_candidate, "strategy"),
        "sleeve": pick_str(row, "sleeve") or pick_str(nested_candidate, "sleeve") or source_surface,
        "trade_enabled": bool(trade_enabled_value) if trade_enabled_value is not None else False,
        "alters_orders": bool(row.get("alters_orders") or nested_candidate.get("alters_orders") or False),
    }


def append_candidate(
    rows: list[dict[str, Any]],
    seen: set[tuple[str, str, str, str, str]],
    candidate: dict[str, Any] | None,
) -> None:
    if not candidate:
        return
    key = (
        str(candidate.get("source_surface") or ""),
        str(candidate.get("row_kind") or ""),
        str(candidate.get("decision_id") or ""),
        str(candidate.get("ticker") or ""),
        str(candidate.get("context_as_of") or ""),
    )
    if key in seen:
        return
    seen.add(key)
    rows.append(candidate)


def collect_snapshot_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    file_summaries: list[dict[str, Any]] = []
    for path in sorted(PAPER_ROOT.glob("*/snapshots.jsonl")):
        source_surface = path.parent.name
        latest, row_count, bad_rows = latest_jsonl_row(path)
        summary = {
            "source_surface": source_surface,
            "path": repo_rel(path),
            "jsonl_rows": row_count,
            "bad_json_rows": bad_rows,
            "latest_loaded": isinstance(latest, dict),
            "extracted_rows": 0,
        }
        if not isinstance(latest, dict):
            file_summaries.append(summary)
            continue
        payload_asof = row_date(latest, "asof_date", "as_of", "date")
        for key in ROW_LIST_KEYS:
            value = latest.get(key)
            if not isinstance(value, list):
                continue
            for item in value:
                if not isinstance(item, dict):
                    continue
                candidate = normalise_candidate_row(source_surface, path, key, payload_asof, item)
                before = len(rows)
                append_candidate(rows, seen, candidate)
                summary["extracted_rows"] += len(rows) - before
        for key in ROW_SINGLE_KEYS:
            value = latest.get(key)
            if not isinstance(value, dict):
                continue
            candidate = normalise_candidate_row(source_surface, path, key, payload_asof, value)
            before = len(rows)
            append_candidate(rows, seen, candidate)
            summary["extracted_rows"] += len(rows) - before
        file_summaries.append(summary)
    return rows, {
        "paper_root": repo_rel(PAPER_ROOT),
        "snapshot_files_scanned": len(file_summaries),
        "extracted_rows": len(rows),
        "files_with_rows": [row for row in file_summaries if row["extracted_rows"]],
        "files_scanned_sample": file_summaries[:20],
    }


def collect_core_risk_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    path = PAPER_ROOT / "core_risk_intensity_forward_observation" / "snapshots.jsonl"
    rows: list[dict[str, Any]] = []
    bad_rows = 0
    raw_rows = 0
    seen: set[tuple[str, str, str, str, str]] = set()
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            for line in handle:
                if not line.strip():
                    continue
                raw_rows += 1
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError:
                    bad_rows += 1
                    continue
                if not isinstance(parsed, dict):
                    continue
                candidate = normalise_candidate_row(
                    "core_risk_intensity_forward_observation",
                    path,
                    "core_risk_intensity_forward_observation",
                    row_date(parsed, "as_of", "asof_date", "date"),
                    parsed,
                )
                append_candidate(rows, seen, candidate)
    except OSError:
        pass
    return rows, {
        "path": repo_rel(path),
        "exists": path.exists(),
        "jsonl_rows": raw_rows,
        "bad_json_rows": bad_rows,
        "extracted_rows": len(rows),
    }


def collect_trend_signal_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    files = sorted(DAILY_TREND_DIR.glob("trend_signals_*.json"))
    path = files[-1] if files else DAILY_TREND_DIR / "trend_signals_*.json"
    payload = read_json(path, {}) if files else {}
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    if isinstance(payload, dict):
        asof = row_date(payload, "asof_date", "as_of", "date")
        ranking = payload.get("ranking_surface")
        if isinstance(ranking, dict):
            for item in ranking.get("leaders") or []:
                if not isinstance(item, dict):
                    continue
                if as_float(item.get("alpha_score")) is None:
                    continue
                if as_float(item.get("alpha_score_rank")) and as_float(item.get("alpha_score_rank")) > 25:
                    continue
                candidate = normalise_candidate_row(
                    "daily_trend_signal",
                    path,
                    "ranking_surface_leader",
                    asof,
                    item,
                )
                append_candidate(rows, seen, candidate)
        for key in ("signals", "candidates", "universe_signals"):
            value = payload.get(key)
            if not isinstance(value, list):
                continue
            for item in value:
                if not isinstance(item, dict):
                    continue
                trend_score = as_float(item.get("trend_score"))
                if not bool(item.get("breakout")) and (trend_score is None or trend_score < 0.8):
                    continue
                candidate = normalise_candidate_row("daily_trend_signal", path, key, asof, item)
                append_candidate(rows, seen, candidate)
    return rows, {
        "path": repo_rel(path),
        "exists": path.exists(),
        "extracted_rows": len(rows),
    }


def collect_candidate_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    snapshot_rows, snapshot_summary = collect_snapshot_rows()
    core_rows, core_summary = collect_core_risk_rows()
    trend_rows, trend_summary = collect_trend_signal_rows()
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for candidate in snapshot_rows + core_rows + trend_rows:
        append_candidate(rows, seen, candidate)
    rows.sort(
        key=lambda row: (
            str(row.get("context_as_of") or ""),
            str(row.get("source_surface") or ""),
            str(row.get("ticker") or ""),
            str(row.get("row_kind") or ""),
        )
    )
    return rows, {
        "snapshot_scan": snapshot_summary,
        "core_risk_scan": core_summary,
        "daily_trend_scan": trend_summary,
        "deduped_candidate_rows": len(rows),
        "source_surface_counts": dict(Counter(str(row["source_surface"]) for row in rows)),
        "row_kind_counts": dict(Counter(str(row["row_kind"]) for row in rows)),
    }


def enrich_context_rows(
    candidate_rows: list[dict[str, Any]], form4_index: dict[str, list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in candidate_rows:
        ticker = str(row.get("ticker") or "").upper()
        context_day = parse_day(row.get("context_as_of"))
        rows = form4_rows_for_context(form4_index, ticker, context_day)
        context = summarize_form4_context(rows)
        start_day = context_day - timedelta(days=LOOKBACK_CALENDAR_DAYS) if context_day else None
        out.append(
            {
                **row,
                "form4_context_rule_version": CHANGED_VARIABLE,
                "form4_context_start": start_day.isoformat() if start_day else None,
                "form4_context_end": context_day.isoformat() if context_day else None,
                **context,
            }
        )
    return out


def row_mentions_form4(row: dict[str, Any]) -> bool:
    for key, value in row.items():
        text = str(key).lower()
        if "form4" in text or "sale_overhang" in text:
            return True
        if isinstance(value, str):
            value_text = value.lower()
            if "form4" in value_text or "sale_overhang" in value_text:
                return True
    return False


def scan_forward_replacement_rows() -> dict[str, Any]:
    total_rows = 0
    form4_rows = 0
    closed_rows = 0
    high_bucket_rows = 0
    ticker_counts: Counter[str] = Counter()
    sample: list[dict[str, Any]] = []
    if not FORWARD_REPLACEMENT_JSONL.exists():
        return {
            "path": repo_rel(FORWARD_REPLACEMENT_JSONL),
            "exists": False,
            "total_rows": 0,
            "form4_tagged_rows": 0,
            "closed_forward_rows_with_cash_spy_qqq_replacement_value": 0,
            "high_sale_overhang_forward_rows": 0,
            "single_ticker_closed_row_share": None,
            "ticker_counts": {},
            "sample_form4_rows": [],
        }
    with FORWARD_REPLACEMENT_JSONL.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            total_rows += 1
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict) or not row_mentions_form4(row):
                continue
            form4_rows += 1
            has_cash = row.get("replacement_value_vs_cash_usd") is not None
            has_spy = row.get("replacement_value_vs_spy_usd") is not None
            has_qqq = row.get("replacement_value_vs_qqq_usd") is not None
            status = str(row.get("status") or row.get("replacement_value_status") or "").lower()
            is_closed = status in {"enriched", "closed"} or bool(row.get("closed_forward_row"))
            if is_closed and has_cash and has_spy and has_qqq:
                closed_rows += 1
                ticker = str(row.get("ticker") or "")
                if ticker:
                    ticker_counts[ticker] += 1
            bucket = str(row.get("form4_sale_overhang_bucket") or row.get("bucket") or "").lower()
            if "high_sale_overhang" in bucket:
                high_bucket_rows += 1
            if len(sample) < 5:
                sample.append(
                    {
                        "ticker": row.get("ticker"),
                        "entry_date": row.get("entry_date"),
                        "status": row.get("status") or row.get("replacement_value_status"),
                        "form4_sale_overhang_bucket": row.get("form4_sale_overhang_bucket"),
                    }
                )
    single_ticker_share = None
    if closed_rows and ticker_counts:
        single_ticker_share = round(max(ticker_counts.values()) / closed_rows, 6)
    return {
        "path": repo_rel(FORWARD_REPLACEMENT_JSONL),
        "exists": True,
        "total_rows": total_rows,
        "form4_tagged_rows": form4_rows,
        "closed_forward_rows_with_cash_spy_qqq_replacement_value": closed_rows,
        "high_sale_overhang_forward_rows": high_bucket_rows,
        "single_ticker_closed_row_share": single_ticker_share,
        "ticker_counts": dict(ticker_counts.most_common(10)),
        "sample_form4_rows": sample,
    }


def summarize_context_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    bucket_counts = Counter(str(row.get("form4_sale_overhang_bucket") or "unknown") for row in rows)
    source_counts = Counter(str(row.get("source_surface") or "unknown") for row in rows)
    target_price_rows = sum(1 for row in rows if row.get("target_price") is not None)
    rows_with_context_day = sum(1 for row in rows if parse_day(row.get("context_as_of")) is not None)
    rows_with_form4_rows = sum(1 for row in rows if int(row.get("form4_rows") or 0) > 0)
    current_or_open_rows = sum(
        1
        for row in rows
        if str(row.get("row_kind") or "").lower()
        in {
            "open_positions",
            "new_pending_entries",
            "pending_entries",
            "core_risk_intensity_forward_observation",
            "ranking_surface_leader",
            "rejected_candidates",
        }
    )
    return {
        "context_rows": len(rows),
        "rows_with_target_price": target_price_rows,
        "rows_with_context_as_of": rows_with_context_day,
        "rows_with_form4_rows": rows_with_form4_rows,
        "current_or_prospective_rows": current_or_open_rows,
        "bucket_counts": dict(bucket_counts),
        "source_surface_counts": dict(source_counts),
        "ticker_counts": dict(Counter(str(row.get("ticker") or "") for row in rows).most_common(20)),
        "sample_rows": rows[:30],
    }


def build_reopen_condition(
    context_summary: dict[str, Any], forward_counts: dict[str, Any]
) -> dict[str, Any]:
    current_counts = {
        "prospective_context_rows_logged": int(context_summary.get("context_rows") or 0),
        "prospective_high_sale_overhang_rows_logged": int(
            (context_summary.get("bucket_counts") or {}).get("high_sale_overhang") or 0
        ),
        "rows_with_target_price": int(context_summary.get("rows_with_target_price") or 0),
        "rows_with_form4_rows": int(context_summary.get("rows_with_form4_rows") or 0),
        "forward_ledger_form4_tagged_rows": int(forward_counts.get("form4_tagged_rows") or 0),
        "closed_forward_rows_with_cash_spy_qqq_replacement_value": int(
            forward_counts.get("closed_forward_rows_with_cash_spy_qqq_replacement_value") or 0
        ),
        "high_sale_overhang_forward_rows": int(
            forward_counts.get("high_sale_overhang_forward_rows") or 0
        ),
        "single_ticker_closed_row_share": forward_counts.get("single_ticker_closed_row_share"),
    }
    return {
        "surface": "Form4 sale/10b5/officer overhang",
        "status": "forward_logging_open_not_alpha_ready",
        "blocking_reason": "closed_forward_replacement_rows_not_materialized",
        "current_counts": current_counts,
        "required_to_reopen": {
            "closed_forward_rows_min": 25,
            "high_sale_overhang_forward_rows_min": 8,
            "single_ticker_closed_row_share_max": 0.4,
            "required_replacement_values": ["cash", "SPY", "QQQ"],
            "required_context_rule_version": CHANGED_VARIABLE,
        },
        "reopen_rule": (
            "Do not reserve a Form4 sale-overhang risk scalar, notional haircut, "
            "ranking, veto, or candidate-pool experiment until prospectively "
            "logged context rows close with cash/SPY/QQQ replacement value and "
            "the required row counts advance. Do not retry by changing "
            "transaction codes, 10b5 handling, owner-role filters, sale-value "
            "thresholds, lookback days, or response curve."
        ),
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    ticket = read_json(TICKET_JSON, {})
    before = baseline_metrics()
    form4_index, form4_summary = load_form4_index()
    candidate_rows, candidate_summary = collect_candidate_rows()
    context_rows = enrich_context_rows(candidate_rows, form4_index)
    context_summary = summarize_context_rows(context_rows)
    forward_counts = scan_forward_replacement_rows()
    reopen_condition = build_reopen_condition(context_summary, forward_counts)

    gate2_passed = bool(
        form4_summary.get("deduped_rows_loaded")
        and context_summary["context_rows"] > 0
        and context_summary["rows_with_context_as_of"] > 0
        and context_summary["rows_with_target_price"] > 0
        and context_summary["current_or_prospective_rows"] > 0
    )
    repair_passed = bool(before.get("loaded") and gate2_passed)

    after = dict(before)
    delta = {
        "expected_value_score_sum_delta": 0.0,
        "total_pnl_delta": 0.0,
        "trade_count_delta": 0,
        "signals_generated_delta": 0,
        "signals_survived_delta": 0,
        "strategy_behavior_changed": False,
    }

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": "accepted_measurement_repair" if repair_passed else "blocked",
        "decision": (
            "accepted_measurement_repair_form4_sale_overhang_context_logger"
            if repair_passed
            else "blocked_form4_sale_overhang_context_logger"
        ),
        "accepted": repair_passed,
        "accepted_alpha": False,
        "accepted_measurement_repair": repair_passed,
        "alpha_ready": False,
        "lane": LANE,
        "owner": OWNER,
        "hypothesis": ticket.get("hypothesis") or ALPHA_HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "prediction": ticket.get("prediction") or {},
        "before_metrics": before,
        "after_metrics": after,
        "delta_metrics": delta,
        "form4_index_summary": form4_summary,
        "candidate_discovery_summary": candidate_summary,
        "context_logger_summary": context_summary,
        "context_rows": context_rows,
        "forward_replacement_scan": forward_counts,
        "reopen_condition": reopen_condition,
        "gate1": {
            "passed": bool(before.get("loaded")),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "baseline_expected_value_score_sum": before.get("expected_value_score_sum"),
            "baseline_total_pnl": before.get("total_pnl"),
            "strategy_metrics_unchanged": True,
        },
        "gate2": {
            "passed": gate2_passed,
            "runtime_fields_checked": [
                "entry_date",
                "target_price",
                "context_as_of",
                "ticker",
                "form4_latest_usable_trade_date",
                "form4_sale_overhang_bucket",
                "form4_sale_rows",
                "form4_ten_b5_sale_rows",
                "form4_officer_sale_rows",
            ],
            "field_status": {
                "entry_date": "present_for_open_paper_positions_or_context_as_of_fallback",
                "target_price": (
                    "present_on core_risk_intensity rows; missing values are logged "
                    "but not consumed by this repair"
                ),
                "context_as_of": "required_for_each_logged_row",
                "form4_archive": "loaded_from daily PIT form4_transactions jsonl files",
            },
            "counts": {
                "form4_rows_loaded": form4_summary.get("deduped_rows_loaded"),
                "context_rows": context_summary["context_rows"],
                "rows_with_target_price": context_summary["rows_with_target_price"],
                "rows_with_context_as_of": context_summary["rows_with_context_as_of"],
                "current_or_prospective_rows": context_summary["current_or_prospective_rows"],
            },
        },
        "gate3": {
            "passed": True,
            "not_applicable_reason": "No signal, filter, ranking, sizing, exit, or order rule changed.",
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "survival_rate_delta": 0.0,
        },
        "gate4": {
            "passed": repair_passed,
            "accepted_alpha": False,
            "measurement_repair_only": True,
            "decision": (
                "accepted_measurement_repair_form4_sale_overhang_context_logger"
                if repair_passed
                else "blocked_form4_sale_overhang_context_logger"
            ),
            "before_after_strategy_delta": delta,
            "reopen_condition": reopen_condition,
            "remaining_blocker": (
                "This run is experiment-owned. A future shared daily adapter can "
                "write the same fields to production-visible snapshots, but a "
                "risk response still stays blocked until closed forward rows exist."
            ),
            "failed_reasons": [] if repair_passed else ["context_logger_contract_not_met"],
        },
        "anti_js": {
            "used_javascript": False,
            "strategy_behavior_changed": False,
            "threshold_scan": False,
            "uses_future_form4_rows": False,
            "new_download_attempts": False,
            "response_curve_retune": False,
        },
        "production_impact": {
            "trade_enabled": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "production_orders_changed": False,
            "production_signal_path_changed": False,
            "production_watchlist_changed": False,
            "shared_policy_changed": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "risk_budget_changed": False,
            "daily_snapshot_exposed": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "parity_note": (
                "Experiment-owned context ledger only. It reads existing daily/default-off "
                "paper rows and Form4 PIT archives; no trading policy consumes this field."
            ),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": (
                "exp-20260628-014 found positive observed-only accepted-core "
                "loss-tail separation for high PIT Form4 sale overhang, but "
                "forbade threshold/role/10b5/lookback/response retunes without "
                "new prospective forward context rows."
            ),
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Accept only as measurement repair if baseline metrics are "
                "unchanged, current/default-off rows are logged with fixed Form4 "
                "context, and a machine-checkable reopen gate is recorded."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The fixed Form4 sale-overhang join can tag current paper/default-off "
                "rows using only PIT usable_trade_date data, including rows with "
                "entry_date and target_price. It still cannot justify a risk "
                "response because no Form4-tagged closed forward replacement-value "
                "sample exists yet."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry Form4 sale overhang by changing sale-value thresholds, "
                "transaction-code lists, 10b5 handling, owner roles, lookback days, "
                "or hard-exclusion/downweight/tilt/notional response shape on the "
                "same observed-only stack."
            ),
            "new_evidence_required": (
                "Prospectively logged Form4 context rows must close with cash/SPY/QQQ "
                "replacement value: at least 25 closed rows, at least 8 high-sale-"
                "overhang rows, and max single-ticker share <=40%."
            ),
        },
        "next_retry_requires": (
            "A future Form4 alpha response requires materially advanced closed "
            "forward rows under reopen_condition or a distinct new data source/gate shape."
        ),
        "related_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(BASELINE_RESULT),
            repo_rel(FORWARD_REPLACEMENT_JSONL),
            repo_rel(NON_OHLCV_DIR),
            repo_rel(PAPER_ROOT),
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(REGISTRY_JSON),
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
    }


def compact_log(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "lane",
        "owner",
        "hypothesis",
        "alpha_hypothesis",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "single_causal_variable",
        "changed_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "accepted",
        "accepted_alpha",
        "accepted_measurement_repair",
        "alpha_ready",
        "decision",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "reopen_condition",
        "production_impact",
        "pre_run_questions",
        "prediction",
        "post_run_reflection",
        "next_retry_requires",
        "related_files",
        "changed_files",
        "reproduction_commands",
        "anti_js",
    ]
    row = {key: payload[key] for key in keys if key in payload}
    row["artifact"] = repo_rel(OUT_JSON)
    row["log"] = repo_rel(LOG_JSON)
    row["lean_quality_passed"] = bool(payload["gate4"]["passed"])
    return row


def build_card(payload: dict[str, Any]) -> str:
    current = payload["reopen_condition"]["current_counts"]
    required = payload["reopen_condition"]["required_to_reopen"]
    buckets = payload["context_logger_summary"]["bucket_counts"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Form4 Sale-Overhang Context Logger",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Status: `{payload['status']}`",
            f"- Logged context rows: `{current['prospective_context_rows_logged']}`",
            f"- Rows with target_price: `{current['rows_with_target_price']}`",
            f"- Rows with Form4 rows: `{current['rows_with_form4_rows']}`",
            f"- Bucket counts: `{json.dumps(buckets, sort_keys=True)}`",
            f"- Closed Form4 forward rows: `{current['closed_forward_rows_with_cash_spy_qqq_replacement_value']}`",
            "",
            "## Reopen Condition",
            "",
            (
                "Reopen only after prospective rows close with cash/SPY/QQQ "
                f"replacement values: at least `{required['closed_forward_rows_min']}` "
                "closed rows, at least "
                f"`{required['high_sale_overhang_forward_rows_min']}` high-overhang "
                "rows, and max single-ticker closed-row share <= 40%."
            ),
            "",
            "## Interpretation",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "## Reproduce",
            "",
            "```powershell",
            RUNNER_COMMAND,
            "```",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any], log_row: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
        BASELINE_RESULT,
        FORWARD_REPLACEMENT_JSONL,
    ]
    files.extend(sorted(NON_OHLCV_DIR.glob("form4_transactions_*.jsonl"))[-5:])
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256_file(path)}
            for path in files
        },
        "log_row_sha256": hashlib.sha256(
            json.dumps(safe(log_row), sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    log_row = compact_log(payload)
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(log_row, allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    result = {
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "accepted_measurement_repair": payload["accepted_measurement_repair"],
        "alpha_ready": False,
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "delta_metrics": payload["delta_metrics"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "reopen_condition": payload["reopen_condition"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    fields = {
        key: payload[key]
        for key in [
            "owner",
            "hypothesis",
            "alpha_hypothesis",
            "change_type",
            "implementation_mode",
            "mechanism_family",
            "trial_family",
            "trial_variant_id",
            "single_causal_variable",
            "changed_variable",
            "causal_components",
            "nearby_prior_experiments",
            "multiple_testing_risk_bucket",
            "new_evidence_type",
            "pre_run_questions",
            "gate1",
            "gate2",
            "gate3",
            "gate4",
            "reopen_condition",
            "production_impact",
            "post_run_reflection",
            "next_retry_requires",
            "related_files",
            "changed_files",
            "reproduction_commands",
            "anti_js",
        ]
        if key in payload
    }
    fields.update(
        {
            "accepted_alpha": False,
            "accepted_measurement_repair": payload["accepted_measurement_repair"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
        }
    )
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload.get("prediction") or {},
        result=result,
        status=payload["status"],
        fields=fields,
        allow_missing_prediction=True,
    )
    write_json(MANIFEST_JSON, build_manifest(payload, log_row))


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(json.dumps(safe(compact_log(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
