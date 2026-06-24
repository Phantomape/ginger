"""exp-20260623-024: non-OHLCV cross-source attention confluence.

Observed-only candidate-pool attribution. This runner asks whether a same
usable-trade-date ticker hit across Form 4 activity and SEC filing event/text
coverage, with fixed liquid same-day price confirmation, has better next-10
trading-day replacement value than single-source event days. It changes no
entry, ranking, sizing, exit, paper ledger, live ledger, or order behavior.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, QUANT_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from constants import ROUND_TRIP_COST_PCT  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
from fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage  # noqa: E402


EXPERIMENT_ID = "exp-20260623-024"
SLUG = "non_ohlcv_attention_confluence"
RUNNER = f"quant/experiments/exp_20260623_024_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
OWNER = "alpha-explore"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260623_024_{SLUG}.json"
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
NON_OHLCV_ROOT = REPO_ROOT / "data" / "non_ohlcv"
FORM4_SOURCE_FILES = [
    NON_OHLCV_ROOT / "form4_transactions_20241002_20260502.jsonl",
]
SEC_EVENT_SOURCE_FILES = [
    NON_OHLCV_ROOT / "sec_filing_events_20241002_20260421.jsonl",
]
SEC_TEXT_SOURCE_FILES = [
    NON_OHLCV_ROOT / "sec_filing_text_20241002_20260421.jsonl",
]

WINDOWS = {
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20241002_20250422.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20250423_20251022.json",
    },
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20251023_20260421.json",
    },
}

HYPOTHESIS = (
    "Production-visible non-OHLCV cross-source attention confluence where a "
    "ticker has same usable-trade-date Form 4 activity plus SEC filing "
    "event/text coverage and fixed same-day liquid price confirmation may "
    "identify better next-10-trading-day replacement value than single-source "
    "event days."
)
CHANGE_TYPE = "candidate_pool_full_stack"
MECHANISM_FAMILY = "production_visible_non_ohlcv_cross_source_attention_candidate_pool"
TRIAL_FAMILY = "non_ohlcv_cross_source_attention_confluence_candidate_pool"
TRIAL_VARIANT_ID = "form4_sec_event_text_same_day_price_confirmed_v1"
CHANGED_VARIABLE = "non_ohlcv_cross_source_attention_confluence_candidate_pool_v1"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260623-008",
    "exp-20260621-016",
    "exp-20260620-004",
]
NEW_EVIDENCE_TYPE = "cross_source_non_ohlcv_attention_confluence"
NEW_EVIDENCE_AXIS = (
    "Same usable-trade-date confluence across independent archived Form 4 and "
    "SEC filing event/text sources, plus fixed liquid same-day price "
    "confirmation. This is not a retune of single-source SEC text, Form 4, "
    "options, or short-volume threshold families."
)
CAUSAL_COMPONENTS = [
    "historical replay",
    "source confluence attribution",
    "execution envelope",
    "observed-only verdict",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260623-024/exp_20260623_024_non_ohlcv_attention_confluence.json",
    "experiments/cards/exp-20260623-024.md",
    "experiments/manifests/exp-20260623-024.json",
    "experiments/tickets/exp-20260623-024.json",
    "experiments/logs/exp-20260623-024.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]

DEFAULT_PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "sec_form4_sources_saturated",
        "sample_too_thin",
        "not_incremental_vs_price_momentum",
        "concentration_failed",
    ],
    "confidence_reason": (
        "Novelty gate does not find a strong near-neighbor because this tests "
        "cross-source non-OHLCV attention confluence rather than a single SEC "
        "text, Form4, options, or short-volume threshold. The mechanism is "
        "plausible but high-risk because the individual SEC and Form4 sources "
        "are saturated."
    ),
    "recorded_at": "2026-06-23T20:05:37+00:00",
}

CONFIG = {
    "hold_days": 10,
    "paper_notional_usd": 4000.0,
    "min_price": 10.0,
    "min_avg_dollar_volume_20d": 50_000_000.0,
    "min_close_location": 0.50,
    "min_same_day_return_excess_spy": 0.0,
    "diagnostic_target_return": 0.10,
}
ACCEPTANCE_RULE = {
    "min_confluence_rows": 20,
    "min_confluence_distinct_tickers": 5,
    "max_single_ticker_row_share": 0.50,
    "min_positive_confluence_windows": 2,
    "requires_positive_total_and_mean_vs_cash_spy_qqq": True,
    "requires_mean_and_median_cash_beats_single_source": True,
}
SOURCE_BUCKETS = ["confluence", "form4_only", "sec_only", "any_single_source"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
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


def as_float(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def safe_round(value: Any, digits: int = 4) -> float | None:
    number = as_float(value)
    if number is None:
        return None
    return round(number, digits)


def load_ticket_prediction() -> dict[str, Any]:
    if not TICKET_JSON.exists():
        return dict(DEFAULT_PREDICTION)
    ticket = read_json(TICKET_JSON)
    prediction = ticket.get("prediction")
    if isinstance(prediction, dict) and prediction.get("confidence_reason"):
        return prediction
    return dict(DEFAULT_PREDICTION)


def existing_files(paths: list[Path], fallback_glob: str) -> list[Path]:
    found = [path for path in paths if path.exists()]
    if found:
        return found
    return sorted(NON_OHLCV_ROOT.glob(fallback_glob))


def valid_day(value: Any) -> str | None:
    day = str(value or "")[:10]
    if len(day) != 10 or day[4] != "-" or day[7] != "-":
        return None
    return day


def in_any_window(day: str) -> bool:
    return any(cfg["start"] <= day <= cfg["end"] for cfg in WINDOWS.values())


def clean_ticker(value: Any) -> str | None:
    ticker = str(value or "").strip().upper()
    if not ticker or ticker in {"N/A", "NA", "NONE", "NULL"}:
        return None
    return ticker.replace(".", "-")


def list_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    return [item.strip() for item in text.replace(";", ",").split(",") if item.strip()]


def new_attention_row(ticker: str, day: str) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "activity_date": day,
        "form4_present": False,
        "sec_event_present": False,
        "sec_text_present": False,
        "form4_count": 0,
        "sec_event_count": 0,
        "sec_text_count": 0,
        "form4_transaction_value_abs": 0.0,
        "form4_purchase_count": 0,
        "form4_sale_count": 0,
        "form4_open_market_purchase_count": 0,
        "form4_10b5_1_count": 0,
        "sec_text_word_count": 0,
        "sec_form_types": set(),
        "sec_item_codes": set(),
        "form4_accessions": set(),
        "sec_accessions": set(),
        "source_files": set(),
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig") as handle:
        for raw in handle:
            if not raw.strip():
                continue
            try:
                rows.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
    return rows


def load_attention_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    aggregates: dict[tuple[str, str], dict[str, Any]] = {}
    seen_keys: set[tuple[Any, ...]] = set()
    audit: dict[str, Any] = {
        "source_files": {},
        "raw_rows_seen": defaultdict(int),
        "rows_in_windows": defaultdict(int),
        "unique_source_rows": defaultdict(int),
        "duplicate_rows": defaultdict(int),
        "invalid_rows": defaultdict(int),
    }

    def item(ticker: str, day: str) -> dict[str, Any]:
        return aggregates.setdefault((ticker, day), new_attention_row(ticker, day))

    for path in existing_files(FORM4_SOURCE_FILES, "form4_transactions_*.jsonl"):
        label = "form4"
        audit["source_files"].setdefault(label, []).append(repo_rel(path))
        with path.open(encoding="utf-8-sig") as handle:
            for raw in handle:
                if not raw.strip():
                    continue
                audit["raw_rows_seen"][label] += 1
                try:
                    row = json.loads(raw)
                except json.JSONDecodeError:
                    audit["invalid_rows"][label] += 1
                    continue
                ticker = clean_ticker(
                    row.get("issuer_trading_symbol")
                    or row.get("ticker")
                    or row.get("submission_ticker")
                )
                day = valid_day(row.get("usable_trade_date"))
                if not ticker or not day or not in_any_window(day):
                    continue
                audit["rows_in_windows"][label] += 1
                key = (
                    label,
                    ticker,
                    day,
                    row.get("accession_number"),
                    row.get("transaction_date"),
                    row.get("transaction_code"),
                    row.get("acquired_disposed_code"),
                    row.get("security_title"),
                    row.get("owner_cik"),
                    row.get("shares"),
                    row.get("price"),
                )
                if key in seen_keys:
                    audit["duplicate_rows"][label] += 1
                    continue
                seen_keys.add(key)
                audit["unique_source_rows"][label] += 1
                out = item(ticker, day)
                out["form4_present"] = True
                out["form4_count"] += 1
                out["source_files"].add(repo_rel(path))
                if row.get("accession_number"):
                    out["form4_accessions"].add(str(row.get("accession_number")))
                transaction_value = as_float(row.get("transaction_value"))
                if transaction_value is not None:
                    out["form4_transaction_value_abs"] += abs(transaction_value)
                code = str(row.get("transaction_code") or "").upper()
                acquired = str(row.get("acquired_disposed_code") or "").upper()
                if code == "P" or acquired == "A":
                    out["form4_purchase_count"] += 1
                if code == "S" or acquired == "D":
                    out["form4_sale_count"] += 1
                if bool(row.get("open_market_purchase_flag")):
                    out["form4_open_market_purchase_count"] += 1
                if bool(row.get("10b5_1_flag")):
                    out["form4_10b5_1_count"] += 1

    for path in existing_files(SEC_EVENT_SOURCE_FILES, "sec_filing_events_*.jsonl"):
        label = "sec_event"
        audit["source_files"].setdefault(label, []).append(repo_rel(path))
        with path.open(encoding="utf-8-sig") as handle:
            for raw in handle:
                if not raw.strip():
                    continue
                audit["raw_rows_seen"][label] += 1
                try:
                    row = json.loads(raw)
                except json.JSONDecodeError:
                    audit["invalid_rows"][label] += 1
                    continue
                ticker = clean_ticker(row.get("ticker"))
                day = valid_day(row.get("usable_trade_date"))
                if not ticker or not day or not in_any_window(day):
                    continue
                audit["rows_in_windows"][label] += 1
                key = (
                    label,
                    ticker,
                    day,
                    row.get("accession_number"),
                    row.get("form_type"),
                    row.get("primary_document"),
                )
                if key in seen_keys:
                    audit["duplicate_rows"][label] += 1
                    continue
                seen_keys.add(key)
                audit["unique_source_rows"][label] += 1
                out = item(ticker, day)
                out["sec_event_present"] = True
                out["sec_event_count"] += 1
                out["source_files"].add(repo_rel(path))
                if row.get("accession_number"):
                    out["sec_accessions"].add(str(row.get("accession_number")))
                if row.get("form_type"):
                    out["sec_form_types"].add(str(row.get("form_type")))
                for code in list_values(row.get("eight_k_item_codes") or row.get("items_raw")):
                    out["sec_item_codes"].add(code)

    for path in existing_files(SEC_TEXT_SOURCE_FILES, "sec_filing_text_*.jsonl"):
        label = "sec_text"
        audit["source_files"].setdefault(label, []).append(repo_rel(path))
        with path.open(encoding="utf-8-sig") as handle:
            for raw in handle:
                if not raw.strip():
                    continue
                audit["raw_rows_seen"][label] += 1
                try:
                    row = json.loads(raw)
                except json.JSONDecodeError:
                    audit["invalid_rows"][label] += 1
                    continue
                if str(row.get("status") or "").lower() not in {"ok", "success", ""}:
                    continue
                ticker = clean_ticker(row.get("ticker"))
                day = valid_day(row.get("usable_trade_date"))
                if not ticker or not day or not in_any_window(day):
                    continue
                audit["rows_in_windows"][label] += 1
                key = (
                    label,
                    ticker,
                    day,
                    row.get("accession_number"),
                    row.get("form_type"),
                    row.get("primary_document"),
                )
                if key in seen_keys:
                    audit["duplicate_rows"][label] += 1
                    continue
                seen_keys.add(key)
                audit["unique_source_rows"][label] += 1
                out = item(ticker, day)
                out["sec_text_present"] = True
                out["sec_text_count"] += 1
                out["source_files"].add(repo_rel(path))
                if row.get("accession_number"):
                    out["sec_accessions"].add(str(row.get("accession_number")))
                if row.get("form_type"):
                    out["sec_form_types"].add(str(row.get("form_type")))
                for code in list_values(row.get("eight_k_item_codes")):
                    out["sec_item_codes"].add(code)
                word_count = as_float(row.get("text_word_count"))
                if word_count is not None:
                    out["sec_text_word_count"] += int(word_count)

    rows: list[dict[str, Any]] = []
    for out in aggregates.values():
        sec_present = bool(out["sec_event_present"] or out["sec_text_present"])
        if out["form4_present"] and sec_present:
            bucket = "confluence"
        elif out["form4_present"]:
            bucket = "form4_only"
        elif sec_present:
            bucket = "sec_only"
        else:
            continue
        rows.append(
            {
                **out,
                "sec_present": sec_present,
                "source_bucket": bucket,
                "sec_form_types": sorted(out["sec_form_types"]),
                "sec_item_codes": sorted(out["sec_item_codes"]),
                "form4_accession_count": len(out["form4_accessions"]),
                "sec_accession_count": len(out["sec_accessions"]),
                "source_files": sorted(out["source_files"]),
                "form4_accessions": sorted(out["form4_accessions"])[:20],
                "sec_accessions": sorted(out["sec_accessions"])[:20],
                "form4_transaction_value_abs": round(out["form4_transaction_value_abs"], 2),
            }
        )
    rows.sort(key=lambda row: (row["activity_date"], row["ticker"], row["source_bucket"]))
    audit["raw_rows_seen"] = dict(audit["raw_rows_seen"])
    audit["rows_in_windows"] = dict(audit["rows_in_windows"])
    audit["unique_source_rows"] = dict(audit["unique_source_rows"])
    audit["duplicate_rows"] = dict(audit["duplicate_rows"])
    audit["invalid_rows"] = dict(audit["invalid_rows"])
    audit["unique_ticker_date_rows"] = len(rows)
    audit["source_bucket_counts"] = dict(Counter(row["source_bucket"] for row in rows))
    return rows, audit


def load_ohlcv(path: Path) -> dict[str, list[dict[str, Any]]]:
    payload = read_json(path)
    raw = payload.get("ohlcv") if isinstance(payload, dict) else payload
    out: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in (raw or {}).items():
        normalised: list[dict[str, Any]] = []
        for row in rows or []:
            day = str(row.get("Date") or row.get("date") or "")[:10]
            open_ = as_float(row.get("Open") if "Open" in row else row.get("open"))
            high = as_float(row.get("High") if "High" in row else row.get("high"))
            low = as_float(row.get("Low") if "Low" in row else row.get("low"))
            close = as_float(row.get("Close") if "Close" in row else row.get("close"))
            volume = as_float(row.get("Volume") if "Volume" in row else row.get("volume"))
            if len(day) != 10 or open_ is None or high is None or low is None or close is None:
                continue
            normalised.append(
                {
                    "Date": day,
                    "Open": open_,
                    "High": high,
                    "Low": low,
                    "Close": close,
                    "Volume": volume or 0.0,
                }
            )
        if normalised:
            normalised.sort(key=lambda item: item["Date"])
            out[str(ticker).upper()] = normalised
    return out


def row_index(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {str(row.get("Date")): index for index, row in enumerate(rows)}


def value(row: dict[str, Any], key: str) -> float | None:
    return as_float(row.get(key))


def daily_return(rows: list[dict[str, Any]], index: int) -> float | None:
    if index < 1:
        return None
    prior = value(rows[index - 1], "Close")
    close = value(rows[index], "Close")
    if prior is None or prior <= 0 or close is None:
        return None
    return close / prior - 1.0


def avg_dollar_volume(rows: list[dict[str, Any]], index: int, lookback: int = 20) -> float | None:
    if index < lookback - 1:
        return None
    values: list[float] = []
    for row in rows[index - lookback + 1 : index + 1]:
        close = value(row, "Close")
        volume = value(row, "Volume")
        if close is None or volume is None:
            return None
        values.append(close * volume)
    return sum(values) / len(values)


def close_location(row: dict[str, Any]) -> float | None:
    high = value(row, "High")
    low = value(row, "Low")
    close = value(row, "Close")
    if high is None or low is None or close is None:
        return None
    span = high - low
    if span <= 0:
        return 0.5
    return (close - low) / span


def paper_leg_pnl(
    rows: list[dict[str, Any]],
    signal_index: int,
    *,
    adv20: float | None,
) -> tuple[dict[str, Any] | None, str | None]:
    hold_days = int(CONFIG["hold_days"])
    if signal_index + 1 >= len(rows) or signal_index + hold_days >= len(rows):
        return None, "missing_entry_or_exit_bar"
    entry_raw = value(rows[signal_index + 1], "Open")
    exit_raw = value(rows[signal_index + hold_days], "Close")
    if entry_raw is None or entry_raw <= 0 or exit_raw is None or exit_raw <= 0:
        return None, "missing_entry_or_exit_price"
    notional = float(CONFIG["paper_notional_usd"])
    entry_price = apply_entry_fill(entry_raw, adv_dollar=adv20, notional=notional)
    exit_price = apply_slippage(
        exit_raw,
        SLIPPAGE_BPS_TARGET,
        "sell",
        adv_dollar=adv20,
        notional=notional,
    )
    pnl_pct_net = exit_price / entry_price - 1.0 - ROUND_TRIP_COST_PCT
    return (
        {
            "entry_date": rows[signal_index + 1]["Date"],
            "exit_date": rows[signal_index + hold_days]["Date"],
            "entry_price": round(entry_price, 4),
            "exit_price": round(exit_price, 4),
            "pnl_pct_net": round(pnl_pct_net, 6),
            "pnl_usd": round(notional * pnl_pct_net, 2),
        },
        None,
    )


def outcome_from_attention(
    *,
    window_label: str,
    attention: dict[str, Any],
    ohlcv: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
) -> tuple[dict[str, Any] | None, str | None]:
    ticker = attention["ticker"]
    signal_date = attention["activity_date"]
    rows = ohlcv.get(ticker)
    spy_rows = ohlcv.get("SPY")
    qqq_rows = ohlcv.get("QQQ")
    if not rows or not spy_rows or not qqq_rows:
        return None, "missing_ohlcv"
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    qqq_idx = indices.get("QQQ", {}).get(signal_date)
    if idx is None or spy_idx is None or qqq_idx is None:
        return None, "activity_date_missing_from_ohlcv"
    if idx < 20 or spy_idx < 1 or qqq_idx < 1:
        return None, "insufficient_ohlcv_history"

    close = value(rows[idx], "Close")
    if close is None or close < CONFIG["min_price"]:
        return None, "price_floor"
    adv20 = avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < CONFIG["min_avg_dollar_volume_20d"]:
        return None, "liquidity_floor"
    loc = close_location(rows[idx])
    signal_return = daily_return(rows, idx)
    spy_signal_return = daily_return(spy_rows, spy_idx)
    if loc is None or signal_return is None or spy_signal_return is None:
        return None, "missing_price_confirmation_fields"
    signal_return_excess_spy = signal_return - spy_signal_return
    if loc < CONFIG["min_close_location"]:
        return None, "close_location_floor"
    if signal_return_excess_spy < CONFIG["min_same_day_return_excess_spy"]:
        return None, "same_day_return_excess_spy_floor"

    trade_leg, reason = paper_leg_pnl(rows, idx, adv20=adv20)
    if trade_leg is None:
        return None, str(reason)
    spy_adv20 = avg_dollar_volume(spy_rows, spy_idx)
    qqq_adv20 = avg_dollar_volume(qqq_rows, qqq_idx)
    spy_leg, reason = paper_leg_pnl(spy_rows, spy_idx, adv20=spy_adv20)
    if spy_leg is None:
        return None, "missing_spy_benchmark_" + str(reason)
    qqq_leg, reason = paper_leg_pnl(qqq_rows, qqq_idx, adv20=qqq_adv20)
    if qqq_leg is None:
        return None, "missing_qqq_benchmark_" + str(reason)

    entry_price = float(trade_leg["entry_price"])
    pnl_usd = float(trade_leg["pnl_usd"])
    spy_pnl = float(spy_leg["pnl_usd"])
    qqq_pnl = float(qqq_leg["pnl_usd"])
    return (
        {
            "window": window_label,
            "ticker": ticker,
            "activity_date": signal_date,
            "entry_date": trade_leg["entry_date"],
            "exit_date": trade_leg["exit_date"],
            "entry_price": trade_leg["entry_price"],
            "exit_price": trade_leg["exit_price"],
            "target_price": round(entry_price * (1.0 + CONFIG["diagnostic_target_return"]), 4),
            "target_price_source": "diagnostic_contract_only_not_exit_rule",
            "pnl_pct_net": trade_leg["pnl_pct_net"],
            "pnl_usd": round(pnl_usd, 2),
            "spy_pnl_usd": round(spy_pnl, 2),
            "qqq_pnl_usd": round(qqq_pnl, 2),
            "replacement_value_vs_cash_usd": round(pnl_usd, 2),
            "replacement_value_vs_spy_usd": round(pnl_usd - spy_pnl, 2),
            "replacement_value_vs_qqq_usd": round(pnl_usd - qqq_pnl, 2),
            "same_day_return": round(signal_return, 6),
            "same_day_return_spy": round(spy_signal_return, 6),
            "same_day_return_excess_spy": round(signal_return_excess_spy, 6),
            "close_location": round(loc, 6),
            "avg_dollar_volume_20d": round(adv20, 2),
            "paper_notional_usd": CONFIG["paper_notional_usd"],
            "hold_days": CONFIG["hold_days"],
            "source_bucket": attention["source_bucket"],
            "form4_present": attention["form4_present"],
            "sec_present": attention["sec_present"],
            "sec_event_present": attention["sec_event_present"],
            "sec_text_present": attention["sec_text_present"],
            "form4_count": attention["form4_count"],
            "sec_event_count": attention["sec_event_count"],
            "sec_text_count": attention["sec_text_count"],
            "form4_transaction_value_abs": attention["form4_transaction_value_abs"],
            "form4_purchase_count": attention["form4_purchase_count"],
            "form4_sale_count": attention["form4_sale_count"],
            "form4_open_market_purchase_count": attention["form4_open_market_purchase_count"],
            "form4_10b5_1_count": attention["form4_10b5_1_count"],
            "sec_text_word_count": attention["sec_text_word_count"],
            "sec_form_types": attention["sec_form_types"],
            "sec_item_codes": attention["sec_item_codes"],
            "form4_accession_count": attention["form4_accession_count"],
            "sec_accession_count": attention["sec_accession_count"],
            "trade_enabled": False,
            "known_at": "after_usable_trade_date_close_before_next_open_paper_entry",
        },
        None,
    )


def build_outcome_rows(
    attention_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    outcome_rows: list[dict[str, Any]] = []
    audit: dict[str, Any] = {"by_window": {}, "reject_reasons": defaultdict(int)}
    for label, cfg in WINDOWS.items():
        ohlcv = load_ohlcv(cfg["snapshot"])
        indices = {ticker: row_index(rows) for ticker, rows in ohlcv.items()}
        window_source_rows = [
            row for row in attention_rows if cfg["start"] <= row["activity_date"] <= cfg["end"]
        ]
        window_rejects: dict[str, int] = defaultdict(int)
        before_count = len(outcome_rows)
        for attention in window_source_rows:
            row, reason = outcome_from_attention(
                window_label=label,
                attention=attention,
                ohlcv=ohlcv,
                indices=indices,
            )
            if row is None:
                window_rejects[str(reason)] += 1
                audit["reject_reasons"][str(reason)] += 1
                continue
            outcome_rows.append(row)
        audit["by_window"][label] = {
            "source_ticker_date_rows": len(window_source_rows),
            "outcome_rows": len(outcome_rows) - before_count,
            "source_bucket_counts": dict(Counter(row["source_bucket"] for row in window_source_rows)),
            "outcome_bucket_counts": dict(
                Counter(row["source_bucket"] for row in outcome_rows[before_count:])
            ),
            "reject_reasons": dict(window_rejects),
            "snapshot": repo_rel(cfg["snapshot"]),
        }
    audit["reject_reasons"] = dict(audit["reject_reasons"])
    return outcome_rows, audit


def load_baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT)
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
            float(window.get("max_drawdown_pct") or 0.0) for window in windows
        )
        if windows
        else None,
        "windows": windows,
    }


def metric_values(rows: list[dict[str, Any]], key: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        number = as_float(row.get(key))
        if number is not None:
            values.append(number)
    return values


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ticker_counts = Counter(str(row.get("ticker")) for row in rows)

    def mean_for(key: str) -> float | None:
        values = metric_values(rows, key)
        return round(sum(values) / len(values), 2) if values else None

    def median_for(key: str) -> float | None:
        values = metric_values(rows, key)
        return round(float(median(values)), 2) if values else None

    def total_for(key: str) -> float:
        return round(sum(metric_values(rows, key)), 2)

    def win_rate_for(key: str) -> float | None:
        values = metric_values(rows, key)
        return round(sum(1 for value in values if value > 0) / len(values), 4) if values else None

    return {
        "n": len(rows),
        "distinct_tickers": len(ticker_counts),
        "max_single_ticker_row_share": round(max(ticker_counts.values()) / len(rows), 4)
        if rows
        else None,
        "top_tickers": [
            {"ticker": ticker, "rows": count, "row_share": round(count / len(rows), 4)}
            for ticker, count in ticker_counts.most_common(10)
        ]
        if rows
        else [],
        "total_replacement_value_vs_cash_usd": total_for("replacement_value_vs_cash_usd"),
        "mean_replacement_value_vs_cash_usd": mean_for("replacement_value_vs_cash_usd"),
        "median_replacement_value_vs_cash_usd": median_for("replacement_value_vs_cash_usd"),
        "win_rate_vs_cash": win_rate_for("replacement_value_vs_cash_usd"),
        "total_replacement_value_vs_spy_usd": total_for("replacement_value_vs_spy_usd"),
        "mean_replacement_value_vs_spy_usd": mean_for("replacement_value_vs_spy_usd"),
        "median_replacement_value_vs_spy_usd": median_for("replacement_value_vs_spy_usd"),
        "win_rate_vs_spy": win_rate_for("replacement_value_vs_spy_usd"),
        "total_replacement_value_vs_qqq_usd": total_for("replacement_value_vs_qqq_usd"),
        "mean_replacement_value_vs_qqq_usd": mean_for("replacement_value_vs_qqq_usd"),
        "median_replacement_value_vs_qqq_usd": median_for("replacement_value_vs_qqq_usd"),
        "win_rate_vs_qqq": win_rate_for("replacement_value_vs_qqq_usd"),
        "mean_same_day_return_excess_spy": safe_round(
            sum(metric_values(rows, "same_day_return_excess_spy"))
            / len(metric_values(rows, "same_day_return_excess_spy"))
            if metric_values(rows, "same_day_return_excess_spy")
            else None,
            6,
        ),
    }


def analyze(outcome_rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_bucket: dict[str, Any] = {}
    for bucket in SOURCE_BUCKETS:
        if bucket == "any_single_source":
            bucket_rows = [row for row in outcome_rows if row["source_bucket"] != "confluence"]
        else:
            bucket_rows = [row for row in outcome_rows if row["source_bucket"] == bucket]
        by_bucket[bucket] = summarize(bucket_rows)

    by_window: dict[str, Any] = {}
    for label in WINDOWS:
        window_rows = [row for row in outcome_rows if row["window"] == label]
        by_window[label] = {
            "all": summarize(window_rows),
            "by_bucket": {
                bucket: summarize(
                    [row for row in window_rows if row["source_bucket"] == bucket]
                    if bucket != "any_single_source"
                    else [row for row in window_rows if row["source_bucket"] != "confluence"]
                )
                for bucket in SOURCE_BUCKETS
            },
        }

    return {
        "all_rows": summarize(outcome_rows),
        "by_bucket": by_bucket,
        "by_window": by_window,
        "ticker_contribution": contribution(outcome_rows, "ticker"),
        "sec_form_type_contribution": contribution_list_field(outcome_rows, "sec_form_types"),
        "sec_item_code_contribution": contribution_list_field(outcome_rows, "sec_item_codes"),
    }


def contribution(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        value_key = str(row.get(key) or "unknown")
        item = grouped.setdefault(
            value_key,
            {
                "value": value_key,
                "n": 0,
                "replacement_value_vs_cash_usd": 0.0,
                "replacement_value_vs_spy_usd": 0.0,
                "replacement_value_vs_qqq_usd": 0.0,
            },
        )
        item["n"] += 1
        item["replacement_value_vs_cash_usd"] += float(row["replacement_value_vs_cash_usd"])
        item["replacement_value_vs_spy_usd"] += float(row["replacement_value_vs_spy_usd"])
        item["replacement_value_vs_qqq_usd"] += float(row["replacement_value_vs_qqq_usd"])
    out = [
        {
            "value": item["value"],
            "n": item["n"],
            "replacement_value_vs_cash_usd": round(item["replacement_value_vs_cash_usd"], 2),
            "replacement_value_vs_spy_usd": round(item["replacement_value_vs_spy_usd"], 2),
            "replacement_value_vs_qqq_usd": round(item["replacement_value_vs_qqq_usd"], 2),
        }
        for item in grouped.values()
    ]
    out.sort(key=lambda item: (-abs(float(item["replacement_value_vs_cash_usd"])), item["value"]))
    return out[:20]


def contribution_list_field(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []
    for row in rows:
        values = row.get(key) or ["none"]
        if not isinstance(values, list):
            values = [str(values)]
        for item in values or ["none"]:
            expanded.append({**row, key: item})
    return contribution(expanded, key)


def acceptance_checks(analysis: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    confluence = analysis["by_bucket"]["confluence"]
    single = analysis["by_bucket"]["any_single_source"]
    positive_confluence_windows = 0
    per_window_confluence: dict[str, Any] = {}
    for label, item in analysis["by_window"].items():
        summary = item["by_bucket"]["confluence"]
        per_window_confluence[label] = summary
        mean_cash = summary.get("mean_replacement_value_vs_cash_usd")
        if mean_cash is not None and mean_cash > 0:
            positive_confluence_windows += 1

    checks = {
        "min_confluence_rows_passed": confluence["n"] >= ACCEPTANCE_RULE["min_confluence_rows"],
        "confluence_distinct_tickers_passed": (
            confluence["distinct_tickers"] >= ACCEPTANCE_RULE["min_confluence_distinct_tickers"]
        ),
        "confluence_concentration_passed": (
            confluence["max_single_ticker_row_share"] is not None
            and confluence["max_single_ticker_row_share"]
            <= ACCEPTANCE_RULE["max_single_ticker_row_share"]
        ),
        "confluence_total_cash_positive": (
            confluence["total_replacement_value_vs_cash_usd"] > 0
        ),
        "confluence_mean_cash_positive": (
            confluence["mean_replacement_value_vs_cash_usd"] is not None
            and confluence["mean_replacement_value_vs_cash_usd"] > 0
        ),
        "confluence_total_spy_positive": (
            confluence["total_replacement_value_vs_spy_usd"] > 0
        ),
        "confluence_mean_spy_positive": (
            confluence["mean_replacement_value_vs_spy_usd"] is not None
            and confluence["mean_replacement_value_vs_spy_usd"] > 0
        ),
        "confluence_total_qqq_positive": (
            confluence["total_replacement_value_vs_qqq_usd"] > 0
        ),
        "confluence_mean_qqq_positive": (
            confluence["mean_replacement_value_vs_qqq_usd"] is not None
            and confluence["mean_replacement_value_vs_qqq_usd"] > 0
        ),
        "mean_cash_beats_single_source": (
            confluence["mean_replacement_value_vs_cash_usd"] is not None
            and single["mean_replacement_value_vs_cash_usd"] is not None
            and confluence["mean_replacement_value_vs_cash_usd"]
            > single["mean_replacement_value_vs_cash_usd"]
        ),
        "median_cash_beats_single_source": (
            confluence["median_replacement_value_vs_cash_usd"] is not None
            and single["median_replacement_value_vs_cash_usd"] is not None
            and confluence["median_replacement_value_vs_cash_usd"]
            > single["median_replacement_value_vs_cash_usd"]
        ),
        "positive_confluence_window_count": positive_confluence_windows,
        "positive_confluence_windows_passed": (
            positive_confluence_windows >= ACCEPTANCE_RULE["min_positive_confluence_windows"]
        ),
        "per_window_confluence": per_window_confluence,
    }
    failed: list[str] = []
    for key, value in checks.items():
        if key.endswith("_passed") and not value:
            failed.append(key.replace("_passed", "_failed"))
    for key in [
        "confluence_total_cash_positive",
        "confluence_mean_cash_positive",
        "confluence_total_spy_positive",
        "confluence_mean_spy_positive",
        "confluence_total_qqq_positive",
        "confluence_mean_qqq_positive",
        "mean_cash_beats_single_source",
        "median_cash_beats_single_source",
    ]:
        if not checks[key]:
            failed.append(key + "_failed")
    return checks, failed


def calibration(prediction: dict[str, Any], decision_passed: bool, failed: list[str]) -> dict[str, Any]:
    predicted = float(prediction.get("success_probability") or 0.0)
    actual = 1 if decision_passed else 0
    return {
        "actual_success": actual,
        "actual_decision": (
            "observed_only_positive_non_ohlcv_confluence_lead_not_promoted"
            if decision_passed
            else "rejected_no_non_ohlcv_attention_confluence_edge"
        ),
        "predicted_success_probability": predicted,
        "brier_score": round((predicted - actual) ** 2, 6),
        "predicted_failure_modes": prediction.get("main_failure_modes") or [],
        "realized_failure_modes": failed,
        "predicted_failure_mode_hit": bool(failed),
        "surprise_note": (
            "Cross-source attention confluence did not pass the sample, "
            "benchmark, concentration, and single-source comparison screen."
            if failed
            else "The confluence screen passed observed-only lead criteria but remains non-promoted."
        ),
    }


def build_payload() -> dict[str, Any]:
    prediction = load_ticket_prediction()
    attention_rows, source_audit = load_attention_rows()
    outcome_rows, outcome_audit = build_outcome_rows(attention_rows)
    analysis = analyze(outcome_rows)
    checks, failed = acceptance_checks(analysis)
    observed_lead = not failed
    status = "observed_only_positive_lead" if observed_lead else "observed_only_rejected"
    decision = (
        "observed_only_positive_non_ohlcv_confluence_lead_not_promoted"
        if observed_lead
        else "rejected_no_non_ohlcv_attention_confluence_edge"
    )
    baseline = load_baseline_metrics()
    now = utc_now()
    why = (
        "The fixed cross-source confluence screen did not clear the full "
        "observed-only acceptance bar. Either the confluence sample was too "
        "thin/concentrated or its next-10-trading-day replacement value failed "
        "to beat cash, SPY, QQQ, and single-source event days at the same time."
        if failed
        else "The fixed cross-source confluence screen produced a positive observed-only lead, but no shared helper or production path was promoted."
    )
    source_files = (
        source_audit.get("source_files", {}).get("form4", [])
        + source_audit.get("source_files", {}).get("sec_event", [])
        + source_audit.get("source_files", {}).get("sec_text", [])
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": status,
        "lane": "alpha_search",
        "owner": OWNER,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": observed_lead,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "observed_only_candidate_pool_attribution_runner",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": "Passed reservation novelty gate without override.",
                "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
                "important_boundary": (
                    "Prior SEC text, Form4, options, and short-volume families "
                    "do not test same ticker/date cross-source confluence."
                ),
            },
            "3_single_policy_bundle": (
                "Same usable-trade-date Form4 plus SEC event/text confluence "
                "with fixed price/liquidity confirmation and next-open/10-day "
                "replacement attribution. No strategy behavior changed."
            ),
            "4_success_failure_standard": (
                "Observed-only lead only if confluence rows meet minimum sample "
                "and ticker dispersion, avoid single-ticker concentration, have "
                "positive total and mean replacement versus cash/SPY/QQQ, beat "
                "single-source event days on mean and median cash replacement, "
                "and are positive in at least two standard windows."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "source_files": source_files,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "windows": {
                label: {
                    "start": cfg["start"],
                    "end": cfg["end"],
                    "snapshot": repo_rel(cfg["snapshot"]),
                }
                for label, cfg in WINDOWS.items()
            },
            "config": CONFIG,
            "acceptance_rule": ACCEPTANCE_RULE,
            "source_bucket_definition": {
                "confluence": "form4_present and (sec_event_present or sec_text_present)",
                "form4_only": "form4_present and not sec_present",
                "sec_only": "sec_present and not form4_present",
                "any_single_source": "form4_only or sec_only",
            },
        },
        "gate1": {
            "baseline_loaded": True,
            "baseline_metrics": baseline,
            "note": "Observed-only attribution; before and after policy are identical.",
        },
        "gate2": {
            "dependencies_validated": True,
            "source_ticker_date_rows": len(attention_rows),
            "outcome_rows": len(outcome_rows),
            "source_audit": source_audit,
            "outcome_audit": outcome_audit,
            "fields_checked": [
                "activity_date",
                "entry_date",
                "target_price",
                "replacement_value_vs_cash_usd",
                "replacement_value_vs_spy_usd",
                "replacement_value_vs_qqq_usd",
                "form4_present",
                "sec_present",
                "source_bucket",
            ],
            "entry_date_present": all(bool(row.get("entry_date")) for row in outcome_rows),
            "target_price_present": all(row.get("target_price") is not None for row in outcome_rows),
            "target_price_contract": (
                "Diagnostic only; the observed-only exit is fixed at close "
                "after 10 trading days and target_price is not an exit rule."
            ),
        },
        "gate3": {
            "filter_added": False,
            "signals_generated": len(attention_rows),
            "signals_survived": len(outcome_rows),
            "survival_rate": round(len(outcome_rows) / len(attention_rows), 4)
            if attention_rows
            else None,
            "baseline_survival_rate": baseline["survival_rate"],
            "note": (
                "No executable filter was added. Price/liquidity confirmation "
                "is part of observed-only attribution and did not change live "
                "or paper candidate generation."
            ),
        },
        "gate4": {
            "observed_only_lead": observed_lead,
            "failed_reasons": failed,
            "acceptance_checks": checks,
            "decision": decision,
            "strategy_rerun_required": False,
            "before_after_strategy_delta": {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "max_drawdown_pct": 0.0,
            },
            "lead_limitations": [
                "Observed-only, not shared-paper-first.",
                "No shared helper or daily default-off snapshot promoted.",
                "Confluence uses replayable public-PIT proxies, not proof of live observation.",
            ],
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "max_drawdown_pct_worst_delta": 0.0,
        },
        "attribution": {
            "n_source_rows": len(attention_rows),
            "n_outcome_rows": len(outcome_rows),
            "analysis": analysis,
            "sample_source_rows": attention_rows[:100],
            "sample_outcome_rows": outcome_rows[:200],
        },
        "production_impact": {
            "trade_enabled": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "entry_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_rules_changed": False,
            "shared_helper_promoted": False,
            "daily_snapshot_exposed": False,
            "uses_non_ohlcv_sources": True,
            "live_realistic_execution_envelope": (
                "Not live-ready. The measured paper envelope is $4,000 notional, "
                "price >= $10, ADV20 >= $50M, next-open entry, 10-trading-day "
                "close exit, shared slippage helper, and round-trip cost. No "
                "capital cap, live order semantics, kill switch, or portfolio "
                "displacement path was promoted."
            ),
        },
        "calibration": calibration(prediction, observed_lead, failed),
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retry this by sweeping Form4 transaction code, SEC form "
                "type, close-location, ADV, same-day return, hold-day, notional, "
                "or benchmark thresholds on the same archived sources. That "
                "would convert a confluence scout into source-threshold mining."
            ),
            "new_evidence_required": (
                "A valid retry needs a materially new evidence axis such as "
                "parsed filing surprise semantics, named customer/supplier "
                "entities, borrow/options structure joined to the same events, "
                "or closed forward replacement rows from a shared default-off "
                "helper."
            ),
        },
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "related_files": [
            RUNNER,
            *source_files,
            repo_rel(BASELINE_RESULT),
            "docs/production_backtest_parity.md",
            "docs/backtesting.md",
        ],
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "lane": payload["lane"],
        "owner": payload["owner"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "observed_only_lead": payload["observed_only_lead"],
        "hypothesis": payload["hypothesis"],
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
        "pre_run_questions": payload["pre_run_questions"],
        "parameters": payload["parameters"],
        "gate1": payload["gate1"],
        "gate2": {
            **payload["gate2"],
            "source_audit": "<see artifact>",
            "outcome_audit": "<see artifact>",
        },
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "attribution": {
            "n_source_rows": payload["attribution"]["n_source_rows"],
            "n_outcome_rows": payload["attribution"]["n_outcome_rows"],
            "analysis": payload["attribution"]["analysis"],
        },
        "production_impact": payload["production_impact"],
        "calibration": payload["calibration"],
        "post_run_reflection": payload["post_run_reflection"],
        "related_files": payload["related_files"],
        "anti_js": payload["anti_js"],
    }


def fmt_money(value: Any) -> str:
    number = as_float(value)
    if number is None:
        return "n/a"
    return f"${number:,.2f}"


def fmt_pct(value: Any) -> str:
    number = as_float(value)
    if number is None:
        return "n/a"
    return f"{number:.2%}"


def build_card(payload: dict[str, Any]) -> str:
    by_bucket = payload["attribution"]["analysis"]["by_bucket"]
    rows = [
        "| Bucket | Rows | Tickers | Max ticker share | Mean cash | Median cash | Mean vs SPY | Mean vs QQQ | Win cash |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for bucket in SOURCE_BUCKETS:
        item = by_bucket[bucket]
        rows.append(
            "| {bucket} | {n} | {tickers} | {share} | {mean_cash} | {median_cash} | {mean_spy} | {mean_qqq} | {win} |".format(
                bucket=bucket,
                n=item["n"],
                tickers=item["distinct_tickers"],
                share=fmt_pct(item["max_single_ticker_row_share"]),
                mean_cash=fmt_money(item["mean_replacement_value_vs_cash_usd"]),
                median_cash=fmt_money(item["median_replacement_value_vs_cash_usd"]),
                mean_spy=fmt_money(item["mean_replacement_value_vs_spy_usd"]),
                mean_qqq=fmt_money(item["mean_replacement_value_vs_qqq_usd"]),
                win=fmt_pct(item["win_rate_vs_cash"]),
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: non-OHLCV attention confluence",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Production orders changed: no",
            "- Shared helper promoted: no",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Replacement Summary",
            "",
            *rows,
            "",
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "- Source rows: `{}`".format(payload["attribution"]["n_source_rows"]),
            "- Outcome rows: `{}`".format(payload["attribution"]["n_outcome_rows"]),
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)} for path in files},
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)

    registry_result = {
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": payload["observed_only_lead"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "attribution": {
            "n_source_rows": payload["attribution"]["n_source_rows"],
            "n_outcome_rows": payload["attribution"]["n_outcome_rows"],
            "by_bucket": payload["attribution"]["analysis"]["by_bucket"],
        },
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result=registry_result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "change_type": payload["change_type"],
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
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "allowed_write_scope": ALLOWED_WRITE_SCOPE,
            "related_files": payload["related_files"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    by_bucket = payload["attribution"]["analysis"]["by_bucket"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "source_rows": payload["attribution"]["n_source_rows"],
                "outcome_rows": payload["attribution"]["n_outcome_rows"],
                "confluence": by_bucket["confluence"],
                "single_source": by_bucket["any_single_source"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
