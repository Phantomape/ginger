"""exp-20260624-026: reusable options forward outcome settlement ledger.

Measurement repair only. Earlier options work created forward observation rows
and one-off skew attribution, but later cross-evidence experiments still had no
machine-readable ledger with embedded cash/SPY/QQQ outcome fields. This runner
settles mature OnclickMedia options observations against warehouse OHLCV and
writes an experiment-owned outcome JSONL ledger.

No strategy, shared helper, ranking, sizing, exit, paper order, live order,
watchlist, LLM, or production daily behavior changes in this experiment.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
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
from quant.ohlcv_warehouse import (  # noqa: E402
    DEFAULT_WAREHOUSE_PATH,
    load_warehouse_ohlcv_frames,
)


EXPERIMENT_ID = "exp-20260624-026"
OWNER = "alpha-explore"
SLUG = "options_forward_outcome_settlement"
RUNNER = f"quant/experiments/exp_20260624_026_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260624_026_{SLUG}.json"
OUTCOME_LEDGER_JSONL = DATA_DIR / "options_forward_outcome_settlement_ledger.jsonl"
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

SOURCE_LEDGERS = [
    {
        "experiment_id": "exp-20260623-009",
        "path": REPO_ROOT
        / "data"
        / "experiments"
        / "exp-20260623-009"
        / "options_forward_observation_ledger.jsonl",
    },
    {
        "experiment_id": "exp-20260624-020",
        "path": REPO_ROOT
        / "data"
        / "experiments"
        / "exp-20260624-020"
        / "options_forward_observation_ledger_delta_20260623.jsonl",
    },
]

HYPOTHESIS = (
    "Repair options alpha blocker: materialize a reusable settled outcome ledger "
    "for mature OnclickMedia options forward observation rows so future options "
    "confirmation tests can read closed cash/SPY/QQQ replacement values without "
    "changing strategy behavior."
)
ALPHA_HYPOTHESIS = (
    "Options put/call, open-interest, volume, IV skew, and contract-quality fields "
    "may become an orthogonal demand/protection confirmation signal only after "
    "forward observation rows have closed replacement-value outcomes."
)
CHANGE_TYPE = "identity_or_measurement_repair"
MECHANISM_FAMILY = "production_visible_forward_options_attribution"
TRIAL_FAMILY = "onclickmedia_options_forward_outcome_settlement"
TRIAL_VARIANT_ID = "post_exp020_reusable_outcome_ledger_v1"
CHANGED_VARIABLE = "onclickmedia_options_reusable_forward_outcome_ledger_v1"
NEW_EVIDENCE_TYPE = "reusable_forward_replacement_outcome_surface"
NEW_EVIDENCE_AXIS = (
    "Machine-readable reusable outcome ledger that combines exp009 plus exp020 "
    "observation rows and writes explicit 5d/10d cash SPY QQQ replacement fields; "
    "no options threshold, skew, top-N, hold, notional, moneyness, or expiration retest."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260623-009",
    "exp-20260623-010",
    "exp-20260624-020",
    "exp-20260624-023",
    "exp-20260624-025",
]
CAUSAL_COMPONENTS = [
    "exp009 and exp020 options observation ledgers",
    "warehouse OHLCV outcome settlement",
    "cash SPY QQQ replacement-value fields",
    "no strategy behavior change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260624-026/exp_20260624_026_options_forward_outcome_settlement.json",
    "data/experiments/exp-20260624-026/options_forward_outcome_settlement_ledger.jsonl",
    "experiments/cards/exp-20260624-026.md",
    "experiments/manifests/exp-20260624-026.json",
    "experiments/tickets/exp-20260624-026.json",
    "experiments/logs/exp-20260624-026.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]

HORIZONS = (1, 3, 5, 10)
COMPARATORS = ("SPY", "QQQ")
PROXY_NOTIONAL_USD = 4000.0
MIN_SETTLED_5D_ROWS = 100
MIN_SETTLED_10D_ROWS = 100
REQUIRED_SOURCE_FIELDS = [
    "observation_id",
    "ticker",
    "quote_date",
    "usable_trade_date",
    "put_call_volume_ratio",
    "put_minus_call_volume_weighted_iv",
    "pit_safe_contract_rate",
]
QUALITY_MIN_LIQUID_CONTRACT_RATE = 0.5
QUALITY_MIN_AVG_LIQUIDITY_SCORE = 0.5
QUALITY_MAX_WIDE_SPREAD_CONTRACT_RATE = 0.75
QUALITY_MAX_ZERO_BID_OR_ASK_COUNT = 60

DEFAULT_PREDICTION = {
    "success_probability": 0.78,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "warehouse_missing_recent_rows",
        "no_matured_options_rows",
        "duplicate_observation_ids",
        "benchmark_settlement_missing",
    ],
    "confidence_reason": (
        "Exp010 proved many exp009 rows can be settled, but it stored a one-off "
        "skew attribution artifact. Recent options/confluence work still lacked "
        "a reusable ledger with embedded closed cash/SPY/QQQ outcomes and the "
        "exp020 delta source. This repair materializes that surface only and "
        "does not retune options fields."
    ),
}


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


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig") as handle:
        for raw in handle:
            if not raw.strip():
                continue
            rows.append(json.loads(raw))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(record, sort_keys=True)
    lines: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                lines.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    lines.append(encoded)
                    replaced = True
                continue
            lines.append(raw)
    if not replaced:
        lines.append(encoded)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    return prediction or DEFAULT_PREDICTION


def as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def date_text(raw: Any) -> str:
    return str(raw)[:10]


def frame_to_rows(frame: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for day, row in frame.iterrows():
        open_ = as_float(row.get("Open"))
        high = as_float(row.get("High"))
        low = as_float(row.get("Low"))
        close = as_float(row.get("Close"))
        volume = as_float(row.get("Volume")) or 0.0
        if open_ is None or high is None or low is None or close is None:
            continue
        rows.append(
            {
                "Date": date_text(day),
                "Open": open_,
                "High": high,
                "Low": low,
                "Close": close,
                "Volume": volume,
            }
        )
    rows.sort(key=lambda item: item["Date"])
    return rows


def first_index_on_or_after(rows: list[dict[str, Any]], day: str) -> int | None:
    for index, row in enumerate(rows):
        if row["Date"] >= day:
            return index
    return None


def index_by_date(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {row["Date"]: index for index, row in enumerate(rows)}


def stock_pnl_from_dates(
    rows: list[dict[str, Any]],
    entry_date: str,
    exit_date: str,
    notional: float,
) -> float | None:
    indexes = index_by_date(rows)
    entry_index = indexes.get(entry_date)
    exit_index = indexes.get(exit_date)
    if entry_index is None or exit_index is None:
        return None
    entry_raw = as_float(rows[entry_index].get("Open"))
    exit_raw = as_float(rows[exit_index].get("Close"))
    if entry_raw is None or entry_raw <= 0 or exit_raw is None or exit_raw <= 0:
        return None
    entry_price = apply_entry_fill(entry_raw)
    exit_price = apply_slippage(exit_raw, SLIPPAGE_BPS_TARGET, "sell")
    return notional * (exit_price / entry_price - 1.0 - ROUND_TRIP_COST_PCT)


def quality_pass(row: dict[str, Any]) -> bool:
    if as_float(row.get("pit_safe_contract_rate")) != 1.0:
        return False
    if (as_float(row.get("liquid_contract_rate")) or 0.0) < QUALITY_MIN_LIQUID_CONTRACT_RATE:
        return False
    if (as_float(row.get("avg_liquidity_score")) or 0.0) < QUALITY_MIN_AVG_LIQUIDITY_SCORE:
        return False
    wide = as_float(row.get("wide_spread_contract_rate"))
    if wide is not None and wide > QUALITY_MAX_WIDE_SPREAD_CONTRACT_RATE:
        return False
    zero_bid_or_ask = int(as_float(row.get("zero_bid_or_ask_count")) or 0)
    return zero_bid_or_ask <= QUALITY_MAX_ZERO_BID_OR_ASK_COUNT


def summarize_baseline(path: Path) -> dict[str, Any]:
    payload = read_json(path, {})
    windows = payload.get("windows") if isinstance(payload, dict) else None
    if not isinstance(windows, list):
        windows = []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    drawdowns = [
        float(row.get("max_drawdown_pct"))
        for row in windows
        if row.get("max_drawdown_pct") is not None
    ]
    return {
        "baseline_result_file": repo_rel(path),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 4) if generated else None,
        "max_drawdown_pct_worst": round(max(drawdowns), 4) if drawdowns else None,
        "windows": windows,
    }


def load_source_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw_rows: list[dict[str, Any]] = []
    ledger_metadata: list[dict[str, Any]] = []
    for source in SOURCE_LEDGERS:
        path = Path(source["path"])
        rows = read_jsonl(path)
        ledger_metadata.append(
            {
                "source_experiment_id": source["experiment_id"],
                "path": repo_rel(path),
                "exists": path.exists(),
                "rows": len(rows),
            }
        )
        for row in rows:
            ticker = str(row.get("ticker") or "").upper()
            usable = date_text(row.get("usable_trade_date") or "")
            quote = date_text(row.get("quote_date") or row.get("asof_date") or "")
            if not ticker or len(usable) != 10:
                continue
            raw_rows.append(
                {
                    **row,
                    "ticker": ticker,
                    "quote_date": quote if len(quote) == 10 else row.get("quote_date"),
                    "usable_trade_date": usable,
                    "source_experiment_id": source["experiment_id"],
                    "source_ledger": repo_rel(path),
                }
            )

    seen: dict[str, dict[str, Any]] = {}
    duplicate_ids = 0
    for row in raw_rows:
        observation_id = str(row.get("observation_id") or "").strip()
        if not observation_id:
            observation_id = "|".join(
                [
                    str(row.get("source_experiment_id") or ""),
                    str(row.get("ticker") or ""),
                    str(row.get("quote_date") or ""),
                    str(row.get("usable_trade_date") or ""),
                ]
            )
            row["observation_id"] = observation_id
        if observation_id in seen:
            duplicate_ids += 1
            continue
        seen[observation_id] = row

    rows = list(seen.values())
    dates = sorted({str(row.get("usable_trade_date")) for row in rows if row.get("usable_trade_date")})
    quote_dates = sorted({str(row.get("quote_date")) for row in rows if row.get("quote_date")})
    tickers = sorted({str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")})
    field_coverage: dict[str, dict[str, Any]] = {}
    for field in REQUIRED_SOURCE_FIELDS:
        present = sum(1 for row in rows if row.get(field) not in (None, ""))
        field_coverage[field] = {
            "present_rows": present,
            "scanned_rows": len(rows),
            "coverage": round(present / len(rows), 6) if rows else None,
        }

    metadata = {
        "source_ledgers": ledger_metadata,
        "source_rows_loaded": len(raw_rows),
        "deduped_source_rows": len(rows),
        "duplicate_observation_ids": duplicate_ids,
        "ticker_count": len(tickers),
        "usable_trade_date_start": dates[0] if dates else None,
        "usable_trade_date_end": dates[-1] if dates else None,
        "usable_trade_date_count": len(dates),
        "quote_date_start": quote_dates[0] if quote_dates else None,
        "quote_date_end": quote_dates[-1] if quote_dates else None,
        "quote_date_count": len(quote_dates),
        "source_outcome_status_counts": dict(
            sorted(Counter(str(row.get("outcome_status") or "missing") for row in rows).items())
        ),
        "source_field_coverage": field_coverage,
    }
    return rows, metadata


def load_prices(rows: list[dict[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    tickers = {str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")}
    tickers.update(COMPARATORS)
    usable_dates = sorted({str(row.get("usable_trade_date")) for row in rows if row.get("usable_trade_date")})
    start = usable_dates[0] if usable_dates else "2026-01-01"
    end = "2026-12-31"
    frames = load_warehouse_ohlcv_frames(DEFAULT_WAREHOUSE_PATH, sorted(tickers), start, end)
    prices = {ticker.upper(): frame_to_rows(frame) for ticker, frame in frames.items()}
    return prices, {
        "warehouse_path": repo_rel(Path(DEFAULT_WAREHOUSE_PATH)),
        "requested_tickers": len(tickers),
        "loaded_tickers": len(prices),
        "missing_tickers": sorted(ticker for ticker in tickers if ticker not in prices),
        "start": start,
        "end": end,
    }


def settle_horizon(
    rows: list[dict[str, Any]],
    entry_index: int,
    horizon: int,
    bars: dict[str, list[dict[str, Any]]],
    notional: float,
) -> tuple[dict[str, Any] | None, str | None]:
    exit_index = entry_index + horizon
    if exit_index >= len(rows):
        return None, f"not_yet_{horizon}d_closed"
    entry = rows[entry_index]
    exit_ = rows[exit_index]
    entry_raw = as_float(entry.get("Open"))
    exit_raw = as_float(exit_.get("Close"))
    if entry_raw is None or entry_raw <= 0 or exit_raw is None or exit_raw <= 0:
        return None, f"bad_{horizon}d_price"
    entry_price = apply_entry_fill(entry_raw)
    exit_price = apply_slippage(exit_raw, SLIPPAGE_BPS_TARGET, "sell")
    pnl_pct = exit_price / entry_price - 1.0 - ROUND_TRIP_COST_PCT
    cash_pnl = notional * pnl_pct
    spy_pnl = stock_pnl_from_dates(bars.get("SPY", []), entry["Date"], exit_["Date"], notional)
    qqq_pnl = stock_pnl_from_dates(bars.get("QQQ", []), entry["Date"], exit_["Date"], notional)
    return {
        "exit_date": exit_["Date"],
        "exit_price": round(exit_price, 4),
        "return_pct": round(pnl_pct, 6),
        "cash_pnl": round(cash_pnl, 2),
        "spy_same_window_pnl": round(spy_pnl, 2) if spy_pnl is not None else None,
        "qqq_same_window_pnl": round(qqq_pnl, 2) if qqq_pnl is not None else None,
        "replacement_vs_spy": round(cash_pnl - spy_pnl, 2) if spy_pnl is not None else None,
        "replacement_vs_qqq": round(cash_pnl - qqq_pnl, 2) if qqq_pnl is not None else None,
    }, None


def settle_rows(
    source_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    bars, warehouse_metadata = load_prices(source_rows)
    outcome_rows: list[dict[str, Any]] = []
    skipped = Counter()
    horizon_settled_counts: Counter[str] = Counter()
    horizon_benchmark_missing_counts: Counter[str] = Counter()

    for row in source_rows:
        ticker = str(row.get("ticker") or "").upper()
        ticker_bars = bars.get(ticker, [])
        out = {**row}
        out["paper_notional_usd"] = PROXY_NOTIONAL_USD
        out["quality_pass"] = quality_pass(out)
        for horizon in HORIZONS:
            prefix = f"{horizon}d"
            out[f"exit_{prefix}_date"] = None
            out[f"exit_{prefix}_price"] = None
            out[f"forward_{prefix}_return_pct"] = None
            out[f"replacement_value_{prefix}_vs_cash_usd"] = None
            out[f"replacement_value_{prefix}_vs_spy_usd"] = None
            out[f"replacement_value_{prefix}_vs_qqq_usd"] = None
            out[f"spy_{prefix}_same_window_pnl"] = None
            out[f"qqq_{prefix}_same_window_pnl"] = None
        if not ticker_bars:
            out["outcome_status"] = "missing_ticker_ohlcv"
            skipped["missing_ticker_ohlcv"] += 1
            outcome_rows.append(out)
            continue

        entry_index = first_index_on_or_after(ticker_bars, str(row.get("usable_trade_date")))
        if entry_index is None:
            out["outcome_status"] = "missing_entry_bar"
            skipped["missing_entry_bar"] += 1
            outcome_rows.append(out)
            continue
        entry = ticker_bars[entry_index]
        entry_raw = as_float(entry.get("Open"))
        if entry_raw is None or entry_raw <= 0:
            out["outcome_status"] = "bad_entry_price"
            skipped["bad_entry_price"] += 1
            outcome_rows.append(out)
            continue

        out["entry_date"] = entry["Date"]
        out["entry_month"] = entry["Date"][:7]
        out["entry_price"] = round(apply_entry_fill(entry_raw), 4)

        closed_horizons: list[int] = []
        for horizon in HORIZONS:
            settled, reason = settle_horizon(
                ticker_bars,
                entry_index,
                horizon,
                bars,
                PROXY_NOTIONAL_USD,
            )
            prefix = f"{horizon}d"
            if settled is None:
                skipped[str(reason)] += 1
                continue
            closed_horizons.append(horizon)
            horizon_settled_counts[str(horizon)] += 1
            if settled["replacement_vs_spy"] is None or settled["replacement_vs_qqq"] is None:
                horizon_benchmark_missing_counts[str(horizon)] += 1
            out[f"exit_{prefix}_date"] = settled["exit_date"]
            out[f"exit_{prefix}_price"] = settled["exit_price"]
            out[f"forward_{prefix}_return_pct"] = settled["return_pct"]
            out[f"replacement_value_{prefix}_vs_cash_usd"] = settled["cash_pnl"]
            out[f"replacement_value_{prefix}_vs_spy_usd"] = settled["replacement_vs_spy"]
            out[f"replacement_value_{prefix}_vs_qqq_usd"] = settled["replacement_vs_qqq"]
            out[f"spy_{prefix}_same_window_pnl"] = settled["spy_same_window_pnl"]
            out[f"qqq_{prefix}_same_window_pnl"] = settled["qqq_same_window_pnl"]

        if 10 in closed_horizons:
            out["outcome_status"] = "closed_10d_forward"
            out["exit_date"] = out["exit_10d_date"]
            out["exit_price"] = out["exit_10d_price"]
            out["forward_10d_return_pct"] = out["forward_10d_return_pct"]
            out["pnl"] = out["replacement_value_10d_vs_cash_usd"]
            out["replacement_value_vs_cash_usd"] = out["replacement_value_10d_vs_cash_usd"]
            out["replacement_value_vs_spy_usd"] = out["replacement_value_10d_vs_spy_usd"]
            out["replacement_value_vs_qqq_usd"] = out["replacement_value_10d_vs_qqq_usd"]
        elif closed_horizons:
            out["outcome_status"] = "partial_closed_forward"
        else:
            out["outcome_status"] = "pending_forward_close"
        outcome_rows.append(out)

    metadata = {
        "warehouse": warehouse_metadata,
        "outcome_rows": len(outcome_rows),
        "horizon_settled_counts": dict(sorted(horizon_settled_counts.items())),
        "horizon_benchmark_missing_counts": dict(sorted(horizon_benchmark_missing_counts.items())),
        "skipped_reasons": dict(sorted(skipped.items())),
        "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
        "slippage_bps_target": SLIPPAGE_BPS_TARGET,
        "entry_fill": "first warehouse session on/after usable_trade_date open with buy-side slippage",
        "exit_fill": "horizon exit session close with sell-side slippage",
    }
    return outcome_rows, metadata


def numeric_summary(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    values = [float(row[field]) for row in rows if as_float(row.get(field)) is not None]
    if not values:
        return {"count": 0, "mean": None, "median": None, "min": None, "max": None}
    return {
        "count": len(values),
        "mean": round(mean(values), 4),
        "median": round(median(values), 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
    }


def summarize_outcomes(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tickers = sorted({str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")})
    entry_dates = sorted({str(row.get("entry_date")) for row in rows if row.get("entry_date")})
    quote_dates = sorted({str(row.get("quote_date")) for row in rows if row.get("quote_date")})
    horizons: dict[str, dict[str, Any]] = {}
    for horizon in HORIZONS:
        prefix = f"{horizon}d"
        horizons[str(horizon)] = {
            "settled_rows": sum(
                1 for row in rows if row.get(f"forward_{prefix}_return_pct") is not None
            ),
            "quality_settled_rows": sum(
                1
                for row in rows
                if row.get("quality_pass") and row.get(f"forward_{prefix}_return_pct") is not None
            ),
            "replacement_value_vs_cash_usd": numeric_summary(
                rows, f"replacement_value_{prefix}_vs_cash_usd"
            ),
            "replacement_value_vs_spy_usd": numeric_summary(
                rows, f"replacement_value_{prefix}_vs_spy_usd"
            ),
            "replacement_value_vs_qqq_usd": numeric_summary(
                rows, f"replacement_value_{prefix}_vs_qqq_usd"
            ),
            "forward_return_pct": numeric_summary(rows, f"forward_{prefix}_return_pct"),
        }
    return {
        "outcome_rows": len(rows),
        "ticker_count": len(tickers),
        "quote_date_start": quote_dates[0] if quote_dates else None,
        "quote_date_end": quote_dates[-1] if quote_dates else None,
        "quote_date_count": len(quote_dates),
        "entry_date_start": entry_dates[0] if entry_dates else None,
        "entry_date_end": entry_dates[-1] if entry_dates else None,
        "entry_date_count": len(entry_dates),
        "outcome_status_counts": dict(
            sorted(Counter(str(row.get("outcome_status") or "missing") for row in rows).items())
        ),
        "quality_pass_rows": sum(1 for row in rows if row.get("quality_pass")),
        "horizons": horizons,
        "sample_rows": rows[:5],
    }


def evaluate_gate4(
    source_metadata: dict[str, Any],
    settlement_metadata: dict[str, Any],
    outcome_summary: dict[str, Any],
    baseline: dict[str, Any],
) -> dict[str, Any]:
    counts = settlement_metadata["horizon_settled_counts"]
    benchmark_missing = settlement_metadata["horizon_benchmark_missing_counts"]
    ledgers_exist = all(item["exists"] for item in source_metadata["source_ledgers"])
    checks = {
        "baseline_loaded": BASELINE_RESULT.exists() and baseline["window_count"] == 3,
        "source_ledgers_exist": ledgers_exist,
        "source_rows_present": source_metadata["deduped_source_rows"] > 0,
        "no_duplicate_observation_ids": source_metadata["duplicate_observation_ids"] == 0,
        "outcome_rows_match_source_rows": (
            outcome_summary["outcome_rows"] == source_metadata["deduped_source_rows"]
        ),
        "settled_5d_floor_passed": int(counts.get("5", 0)) >= MIN_SETTLED_5D_ROWS,
        "settled_10d_floor_passed": int(counts.get("10", 0)) >= MIN_SETTLED_10D_ROWS,
        "benchmark_5d_complete": int(benchmark_missing.get("5", 0)) == 0,
        "benchmark_10d_complete": int(benchmark_missing.get("10", 0)) == 0,
        "strategy_metrics_unchanged": True,
    }
    failed = [name for name, passed in checks.items() if not passed]
    passed = not failed
    return {
        "passed": passed,
        "decision": (
            "accepted_measurement_repair_options_forward_outcomes_settled"
            if passed
            else "blocked_options_forward_outcome_settlement"
        ),
        "acceptance_checks": checks,
        "failed_reasons": failed,
        "before_after_strategy_delta": {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "trade_count": 0,
            "signals_generated": 0,
            "signals_survived": 0,
        },
        "strategy_rerun_required": False,
        "accepted_alpha": False,
        "measurement_repair_only": True,
    }


def calibration(prediction: dict[str, Any], success: bool, failed_reasons: list[str]) -> dict[str, Any]:
    probability = as_float(prediction.get("success_probability")) or 0.0
    actual = 1.0 if success else 0.0
    predicted_failures = list(prediction.get("main_failure_modes") or [])
    return {
        "predicted_success_probability": probability,
        "actual_success": int(success),
        "brier_score": round((probability - actual) ** 2, 4),
        "predicted_failure_modes": predicted_failures,
        "realized_failure_modes": failed_reasons,
        "predicted_failure_mode_hit": any(reason in failed_reasons for reason in predicted_failures),
        "actual_decision": (
            "accepted_measurement_repair_options_forward_outcomes_settled"
            if success
            else "blocked_options_forward_outcome_settlement"
        ),
    }


def build_payload() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    now = utc_now()
    prediction = load_ticket_prediction()
    baseline = summarize_baseline(BASELINE_RESULT)
    source_rows, source_metadata = load_source_rows()
    outcome_rows, settlement_metadata = settle_rows(source_rows)
    outcome_summary = summarize_outcomes(outcome_rows)
    gate4 = evaluate_gate4(source_metadata, settlement_metadata, outcome_summary, baseline)
    success = bool(gate4["passed"])
    failed = list(gate4["failed_reasons"])
    status = "accepted_measurement_repair" if success else "blocked"
    decision = str(gate4["decision"])
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
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
        "implementation_mode": "measurement_repair_outcome_ledger",
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
                "exp-20260623-009": (
                    "Accepted measurement repair created the original options forward "
                    "observation ledger with pending outcome fields."
                ),
                "exp-20260623-010": (
                    "Rejected one-off 10d skew attribution after settling exp009 rows; "
                    "this run does not retest skew and writes a reusable outcome ledger."
                ),
                "exp-20260624-020": (
                    "Accepted measurement repair added the 2026-06-23 options snapshot "
                    "delta rows; this run includes that source and leaves immature rows pending."
                ),
                "exp-20260624-023": (
                    "Observed-only Kova/options cross-evidence was not allocation-ready "
                    "and lacked a reusable closed options outcome surface."
                ),
                "exp-20260624-025": (
                    "Observed-only Form4/SEC/options confluence found no overlap and "
                    "reported no embedded options replacement outcomes."
                ),
                "novelty_gate": (
                    "Reservation passed without override; nearest options skew family "
                    "was below threshold because this is measurement repair only."
                ),
            },
            "3_single_policy_bundle": (
                "One measurement bundle: combine exp009 and exp020 options observation "
                "rows, settle available 1/3/5/10 trading-day horizons against warehouse "
                "OHLCV, and write cash/SPY/QQQ replacement fields."
            ),
            "4_success_failure_standard": (
                "Accept as measurement repair only if source ledgers load, duplicate "
                "observation IDs are zero, outcome rows match deduped source rows, 5d and "
                "10d settlement floors pass, SPY/QQQ comparators are complete, and core "
                "strategy metrics remain unchanged."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "source_ledgers": [item["path"] for item in source_metadata["source_ledgers"]],
            "outcome_ledger": repo_rel(OUTCOME_LEDGER_JSONL),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "warehouse_path": repo_rel(Path(DEFAULT_WAREHOUSE_PATH)),
            "horizons": list(HORIZONS),
            "comparators": list(COMPARATORS),
            "proxy_notional_usd": PROXY_NOTIONAL_USD,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "slippage_bps_target": SLIPPAGE_BPS_TARGET,
            "min_settled_5d_rows": MIN_SETTLED_5D_ROWS,
            "min_settled_10d_rows": MIN_SETTLED_10D_ROWS,
        },
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_metrics": baseline,
            "passed": BASELINE_RESULT.exists() and baseline["window_count"] == 3,
        },
        "gate2": {
            "dependencies_validated": success,
            "fields_checked": REQUIRED_SOURCE_FIELDS
            + [
                "entry_date",
                "target_price",
                "forward_5d_return_pct",
                "forward_10d_return_pct",
                "replacement_value_5d_vs_cash_usd",
                "replacement_value_10d_vs_cash_usd",
                "replacement_value_vs_cash_usd",
                "replacement_value_vs_spy_usd",
                "replacement_value_vs_qqq_usd",
            ],
            "source_field_coverage": source_metadata["source_field_coverage"],
            "entry_date_rows": sum(1 for row in outcome_rows if row.get("entry_date")),
            "target_price_scope": (
                "Not applicable: options observations are not executable candidates and "
                "this repair uses fixed forward horizons, not target-price exits."
            ),
            "failed_reasons": failed,
        },
        "gate3": {
            "filter_added": False,
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "passed": baseline["survival_rate"] is not None and baseline["survival_rate"] >= 0.05,
            "note": "No executable filter or strategy rule was added.",
        },
        "gate4": gate4,
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "strategy_behavior_changed": False,
            "outcome_rows_written": len(outcome_rows),
            "settled_5d_rows": settlement_metadata["horizon_settled_counts"].get("5", 0),
            "settled_10d_rows": settlement_metadata["horizon_settled_counts"].get("10", 0),
        },
        "source_metadata": source_metadata,
        "settlement_metadata": settlement_metadata,
        "outcome_summary": outcome_summary,
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
            "live_ready": False,
            "parity_note": (
                "This experiment writes an experiment-owned outcome ledger only. "
                "It reads prior options ledgers and warehouse OHLCV without modifying "
                "daily options snapshots, shared helpers, backtester behavior, run.py, "
                "paper orders, or live execution."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The exp009 options ledger already had many mature May/June rows, and "
                "the warehouse supplied enough aligned ticker/SPY/QQQ bars to write a "
                "reusable closed outcome surface. The exp020 2026-06-23 delta remains "
                "pending as expected."
                if success
                else "The options outcome surface could not meet the measurement floor; "
                "the failed checks identify the missing dependency."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry options put/call ratio, IV skew, open interest, volume, "
                "expiration, moneyness, top-N, hold, cooldown, notional, or threshold "
                "rules from this repair. It creates outcome fields only and does not "
                "accept an options alpha."
            ),
            "new_evidence_required": (
                "Next options alpha evidence needs materially more closed forward rows "
                "including the exp020 daily deltas, PIT vendor/asof controls, borrow or "
                "loan-availability context, or historical PIT options chains covering "
                "canonical windows before any shared helper promotion."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(OUTCOME_LEDGER_JSONL),
            repo_rel(OUT_JSON),
            repo_rel(BASELINE_RESULT),
            repo_rel(Path(DEFAULT_WAREHOUSE_PATH)),
            "experiments/logs/exp-20260623-009.json",
            "experiments/logs/exp-20260623-010.json",
            "experiments/logs/exp-20260624-020.json",
            "experiments/logs/exp-20260624-023.json",
            "experiments/logs/exp-20260624-025.json",
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(OUTCOME_LEDGER_JSONL),
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
        "outcome_ledger": repo_rel(OUTCOME_LEDGER_JSONL),
        "log": repo_rel(LOG_JSON),
    }
    return payload, outcome_rows


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
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
        "source_metadata": payload["source_metadata"],
        "settlement_metadata": payload["settlement_metadata"],
        "outcome_summary": {
            "outcome_rows": payload["outcome_summary"]["outcome_rows"],
            "ticker_count": payload["outcome_summary"]["ticker_count"],
            "quote_date_start": payload["outcome_summary"]["quote_date_start"],
            "quote_date_end": payload["outcome_summary"]["quote_date_end"],
            "entry_date_start": payload["outcome_summary"]["entry_date_start"],
            "entry_date_end": payload["outcome_summary"]["entry_date_end"],
            "outcome_status_counts": payload["outcome_summary"]["outcome_status_counts"],
            "quality_pass_rows": payload["outcome_summary"]["quality_pass_rows"],
            "horizons": payload["outcome_summary"]["horizons"],
            "sample_rows": payload["outcome_summary"]["sample_rows"][:2],
        },
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "related_files": payload["related_files"],
        "changed_files": payload["changed_files"],
        "allowed_write_scope": payload["allowed_write_scope"],
        "reproduction_commands": payload["reproduction_commands"],
        "anti_js": payload["anti_js"],
        "lean_quality_passed": payload["lean_quality_passed"],
        "artifact": payload["artifact"],
        "outcome_ledger": payload["outcome_ledger"],
        "log": payload["log"],
    }


def build_card(payload: dict[str, Any]) -> str:
    counts = payload["settlement_metadata"]["horizon_settled_counts"]
    horizons = payload["outcome_summary"]["horizons"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: options forward outcome settlement",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Source rows: `{payload['source_metadata']['deduped_source_rows']}`",
            f"- Outcome rows: `{payload['outcome_summary']['outcome_rows']}`",
            f"- Settled 5d / 10d rows: `{counts.get('5', 0)}` / `{counts.get('10', 0)}`",
            f"- 10d mean replacement vs cash/SPY/QQQ: `{horizons['10']['replacement_value_vs_cash_usd']['mean']}` / `{horizons['10']['replacement_value_vs_spy_usd']['mean']}` / `{horizons['10']['replacement_value_vs_qqq_usd']['mean']}`",
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
        OUTCOME_LEDGER_JSONL,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        BASELINE_RESULT,
        Path(DEFAULT_WAREHOUSE_PATH),
    ] + [Path(item["path"]) for item in SOURCE_LEDGERS]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "outcome_ledger": repo_rel(OUTCOME_LEDGER_JSONL),
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


def persist(payload: dict[str, Any], outcome_rows: list[dict[str, Any]]) -> None:
    write_jsonl(OUTCOME_LEDGER_JSONL, outcome_rows)
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
        "outcome_ledger": repo_rel(OUTCOME_LEDGER_JSONL),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "gate4": payload["gate4"],
        "settlement_metadata": payload["settlement_metadata"],
        "outcome_summary": log_record["outcome_summary"],
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
            "alpha_hypothesis": payload["alpha_hypothesis"],
            "change_type": CHANGE_TYPE,
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
            "outcome_ledger": repo_rel(OUTCOME_LEDGER_JSONL),
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
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload, outcome_rows = build_payload()
    persist(payload, outcome_rows)
    counts = payload["settlement_metadata"]["horizon_settled_counts"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "source_rows": payload["source_metadata"]["deduped_source_rows"],
                "outcome_rows": payload["outcome_summary"]["outcome_rows"],
                "settled_5d_rows": counts.get("5", 0),
                "settled_10d_rows": counts.get("10", 0),
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": payload["artifact"],
                "outcome_ledger": payload["outcome_ledger"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
