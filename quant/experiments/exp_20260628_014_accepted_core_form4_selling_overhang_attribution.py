"""exp-20260628-014: accepted-core Form 4 selling-overhang attribution.

Read-only alpha attribution over the current accepted core stack. The tested
field is point-in-time SEC Form 4 selling and 10b5-1 activity in the 10 calendar
days before entry, joined to already accepted trades. This runner does not
alter candidate pools, entries, exits, ranking, sizing, or order behavior.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
import sys
from collections import OrderedDict, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


EXPERIMENT_ID = "exp-20260628-014"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "accepted_core_form4_selling_overhang_attribution"
RUNNER = f"quant/experiments/exp_20260628_014_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

CHANGED_VARIABLE = "accepted_core_pit_form4_selling_overhang_loss_tail_attribution_v1"
TRIAL_FAMILY = "accepted_core_form4_selling_overhang_risk_attribution"
TRIAL_VARIANT_ID = "accepted_stack_daily_form4_sale_10b5_overhang_v1"
MECHANISM_FAMILY = "production_visible_form4_selling_overhang_risk_attribution"
CHANGE_TYPE = "observed_only_attribution"
IMPLEMENTATION_MODE = "observed_only_attribution"
NEW_EVIDENCE_TYPE = "new_gate_shape_pit_form4_accepted_core_risk_attribution"
NEW_EVIDENCE_AXIS = (
    "New gate shape: PIT daily Form 4 transaction archive joined only to already "
    "accepted core trades for read-only loss-tail attribution; not a Form4 "
    "candidate-pool source, code-list sweep, forward-row reslice, or risk response "
    "retune."
)

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260602-003"
    / "exp_20260602_003_post_earnings_explicit_continuation.json"
)
STANDARD_WINDOW_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
WINDOW_FILES: "OrderedDict[str, Path]" = OrderedDict(
    [
        (
            "late_strong",
            REPO_ROOT
            / "data"
            / "experiments"
            / "exp-20260602-003"
            / "late_strong_after.json",
        ),
        (
            "mid_weak",
            REPO_ROOT
            / "data"
            / "experiments"
            / "exp-20260602-003"
            / "mid_weak_after.json",
        ),
        (
            "old_thin",
            REPO_ROOT
            / "data"
            / "experiments"
            / "exp-20260602-003"
            / "old_thin_after.json",
        ),
    ]
)
NON_OHLCV_DIR = REPO_ROOT / "data" / "non_ohlcv"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260628_014_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Read-only risk-allocation attribution: accepted core trades with high PIT "
    "Form 4 selling and 10b5-1 activity in the 10 days before entry may carry "
    "worse loss-tail and lower PnL than accepted trades without insider-sale "
    "overhang."
)
CAUSAL_COMPONENTS = [
    "canonical accepted-stack trade replay",
    "PIT daily Form 4 transaction join",
    "fixed sale-overhang buckets",
    "loss-tail attribution",
    "no strategy behavior change",
]
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260625-013",
    "exp-20260620-004",
    "exp-20260503-017",
    "exp-20260628-012",
    "exp-20260628-013",
]

# Fixed before seeing the run result. The intent is not to tune Form 4 codes;
# it is to ask whether obviously material sale pressure is an accepted-core
# loss-tail context field.
LOOKBACK_CALENDAR_DAYS = 10
HIGH_SALE_VALUE_USD = 5_000_000.0
HIGH_OFFICER_SALE_VALUE_USD = 1_000_000.0
HIGH_TEN_B5_SALE_ROWS = 1
LOSS_TAIL_PNL_PCT = -0.02
MIN_COVERED_ROWS = 50
MIN_HIGH_BUCKET_ROWS = 8
MIN_CLEAN_BUCKET_ROWS = 10
MIN_SUPPORTING_WINDOWS = 2


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


def mean(values: list[float]) -> float | None:
    return round_float(statistics.fmean(values)) if values else None


def median(values: list[float]) -> float | None:
    return round_float(statistics.median(values)) if values else None


def parse_day(value: Any) -> date | None:
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
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def target_price_from_trade(trade: dict[str, Any]) -> float | None:
    target = as_float(trade.get("target_price"))
    if target is not None:
        return round_float(target, 4)
    entry = as_float(trade.get("entry_price"))
    stop = as_float(trade.get("stop_price"))
    mult = as_float(trade.get("target_mult_used"))
    if entry is None or stop is None or mult is None:
        return None
    risk_per_share = max(entry - stop, 0.0)
    if risk_per_share <= 0:
        return None
    return round_float(entry + risk_per_share * mult, 4)


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
    transaction_code_counts: dict[str, int] = defaultdict(int)

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
            value = as_float(row.get("transaction_value"))
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
                "transaction_value": value,
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


def entry_snapshot_path(entry_day: date | None) -> Path | None:
    if entry_day is None:
        return None
    return NON_OHLCV_DIR / f"daily_non_ohlcv_snapshot_{entry_day:%Y%m%d}.json"


def form4_rows_for_entry(
    index: dict[str, list[dict[str, Any]]], ticker: str, entry_day: date | None
) -> list[dict[str, Any]]:
    if entry_day is None:
        return []
    start = entry_day - timedelta(days=LOOKBACK_CALENDAR_DAYS)
    rows = []
    for row in index.get(ticker.upper(), []):
        usable_day = row["usable_trade_date"]
        if start <= usable_day <= entry_day:
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
        "bucket": bucket,
        "form4_rows": len(rows),
        "sale_rows": len(sale_rows),
        "tax_withholding_rows": len(tax_rows),
        "purchase_rows": len(purchase_rows),
        "option_exercise_rows": len(exercise_rows),
        "ten_b5_sale_rows": len(ten_b5_sale_rows),
        "officer_sale_rows": len(officer_sale_rows),
        "sale_value_usd": round_float(sale_value, 2),
        "tax_withholding_value_usd": round_float(tax_value, 2),
        "purchase_value_usd": round_float(purchase_value, 2),
        "officer_sale_value_usd": round_float(officer_sale_value, 2),
        "ten_b5_sale_value_usd": round_float(ten_b5_sale_value, 2),
        "net_sale_value_usd": round_float(sale_value - purchase_value, 2),
        "unique_owners": len({row.get("owner_cik") for row in rows if row.get("owner_cik")}),
        "latest_usable_trade_date": (
            max(row["usable_trade_date"] for row in rows).isoformat() if rows else None
        ),
        "sample_accessions": sorted(
            {str(row.get("accession_number")) for row in rows if row.get("accession_number")}
        )[:8],
    }


def enrich_trade(
    label: str, trade: dict[str, Any], form4_index: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    ticker = str(trade.get("ticker") or "").upper()
    entry_day = parse_day(trade.get("entry_date"))
    snapshot_path = entry_snapshot_path(entry_day)
    context_rows = form4_rows_for_entry(form4_index, ticker, entry_day)
    context = summarize_form4_context(context_rows)
    pnl = as_float(trade.get("pnl")) or 0.0
    pnl_pct = as_float(trade.get("pnl_pct_net")) or 0.0
    entry_price = as_float(trade.get("entry_price"))
    shares = as_float(trade.get("shares"))
    entry_notional = entry_price * shares if entry_price is not None and shares is not None else None
    return {
        "window": label,
        "ticker": ticker or None,
        "strategy": trade.get("strategy"),
        "sector": trade.get("sector"),
        "entry_date": trade.get("entry_date"),
        "exit_date": trade.get("exit_date"),
        "exit_reason": trade.get("exit_reason"),
        "entry_price": round_float(entry_price, 4),
        "target_price_reconstructed": target_price_from_trade(trade),
        "shares": round_float(shares, 4),
        "entry_notional": round_float(entry_notional, 2),
        "pnl": round_float(pnl, 2),
        "pnl_pct_net": round_float(pnl_pct, 8),
        "is_loss": pnl < 0,
        "is_loss_tail": pnl_pct <= LOSS_TAIL_PNL_PCT,
        "form4_archive_covered": bool(snapshot_path and snapshot_path.exists()),
        "form4_snapshot_path": repo_rel(snapshot_path) if snapshot_path and snapshot_path.exists() else None,
        **context,
    }


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pnls = [float(row["pnl"]) for row in rows if row.get("pnl") is not None]
    pnl_pcts = [
        float(row["pnl_pct_net"]) for row in rows if row.get("pnl_pct_net") is not None
    ]
    sale_values = [
        float(row["sale_value_usd"]) for row in rows if row.get("sale_value_usd") is not None
    ]
    return {
        "n": len(rows),
        "covered_n": sum(1 for row in rows if row.get("form4_archive_covered")),
        "total_pnl": round_float(sum(pnls), 2),
        "avg_pnl": mean(pnls),
        "median_pnl": median(pnls),
        "avg_pnl_pct_net": mean(pnl_pcts),
        "median_pnl_pct_net": median(pnl_pcts),
        "win_rate": round_float(
            sum(1 for row in rows if (row.get("pnl") or 0) > 0) / len(rows)
            if rows
            else None,
            6,
        ),
        "loss_rate": round_float(
            sum(1 for row in rows if row.get("is_loss")) / len(rows) if rows else None,
            6,
        ),
        "loss_tail_rate": round_float(
            sum(1 for row in rows if row.get("is_loss_tail")) / len(rows)
            if rows
            else None,
            6,
        ),
        "avg_sale_value_usd": mean(sale_values),
        "median_sale_value_usd": median(sale_values),
        "total_sale_value_usd": round_float(sum(sale_values), 2),
        "rows_with_sales": sum(1 for row in rows if (row.get("sale_rows") or 0) > 0),
        "rows_with_10b5_sales": sum(
            1 for row in rows if (row.get("ten_b5_sale_rows") or 0) > 0
        ),
        "rows_with_officer_sales": sum(
            1 for row in rows if (row.get("officer_sale_rows") or 0) > 0
        ),
    }


def summarize_by_bucket(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for bucket in (
        "no_sale_overhang",
        "moderate_or_routine_disposal",
        "high_sale_overhang",
    ):
        bucket_rows = [row for row in rows if row.get("bucket") == bucket]
        out[bucket] = summarize_rows(bucket_rows)
    return out


def compare_high_clean(summary: dict[str, Any]) -> dict[str, Any]:
    high = summary.get("high_sale_overhang") or {}
    clean = summary.get("no_sale_overhang") or {}
    if not high.get("n") or not clean.get("n"):
        return {"available": False}
    return {
        "available": True,
        "high_minus_clean_avg_pnl": round_float(
            (high.get("avg_pnl") or 0.0) - (clean.get("avg_pnl") or 0.0),
            6,
        ),
        "high_minus_clean_median_pnl": round_float(
            (high.get("median_pnl") or 0.0) - (clean.get("median_pnl") or 0.0),
            6,
        ),
        "high_minus_clean_win_rate": round_float(
            (high.get("win_rate") or 0.0) - (clean.get("win_rate") or 0.0),
            6,
        ),
        "high_minus_clean_loss_tail_rate": round_float(
            (high.get("loss_tail_rate") or 0.0)
            - (clean.get("loss_tail_rate") or 0.0),
            6,
        ),
        "high_rows": high.get("n"),
        "clean_rows": clean.get("n"),
    }


def load_baseline_summary() -> dict[str, Any]:
    baseline = read_json(STANDARD_WINDOW_RESULT, {})
    if not isinstance(baseline, dict):
        return {"standard_window_result": repo_rel(STANDARD_WINDOW_RESULT), "loaded": False}
    return {
        "standard_window_result": repo_rel(STANDARD_WINDOW_RESULT),
        "accepted_stack_artifact": repo_rel(BASELINE_RESULT),
        "loaded": True,
        "expected_value_score_sum": baseline.get("expected_value_score_sum")
        or baseline.get("total_expected_value_score"),
        "total_pnl": baseline.get("total_pnl"),
        "trade_count": baseline.get("trade_count"),
        "windows": baseline.get("windows") or baseline.get("by_window") or {},
    }


def load_rows(
    form4_index: dict[str, list[dict[str, Any]]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    source_audit: dict[str, Any] = {}
    for label, path in WINDOW_FILES.items():
        payload = read_json(path, {})
        trades = payload.get("trades") if isinstance(payload, dict) else None
        if not isinstance(trades, list):
            trades = []
        window_rows = [enrich_trade(label, trade, form4_index) for trade in trades]
        rows.extend(window_rows)
        source_audit[label] = {
            "path": repo_rel(path),
            "trade_rows": len(window_rows),
            "rows_with_entry_date": sum(1 for row in window_rows if row.get("entry_date")),
            "rows_with_target_price_reconstructed": sum(
                1 for row in window_rows if row.get("target_price_reconstructed") is not None
            ),
            "rows_with_form4_archive_coverage": sum(
                1 for row in window_rows if row.get("form4_archive_covered")
            ),
            "bucket_counts": {
                bucket: sum(1 for row in window_rows if row.get("bucket") == bucket)
                for bucket in (
                    "no_sale_overhang",
                    "moderate_or_routine_disposal",
                    "high_sale_overhang",
                )
            },
        }
    return rows, source_audit


def build_attribution(
    rows: list[dict[str, Any]],
    source_audit: dict[str, Any],
    form4_audit: dict[str, Any],
) -> dict[str, Any]:
    covered_rows = [row for row in rows if row.get("form4_archive_covered")]
    by_window: dict[str, Any] = {}
    for label in WINDOW_FILES:
        window_rows = [row for row in covered_rows if row.get("window") == label]
        buckets = summarize_by_bucket(window_rows)
        by_window[label] = {
            "all": summarize_rows(window_rows),
            "buckets": buckets,
            "high_vs_clean": compare_high_clean(buckets),
        }
    buckets = summarize_by_bucket(covered_rows)
    return {
        "parameters": {
            "lookback_calendar_days": LOOKBACK_CALENDAR_DAYS,
            "high_sale_value_usd": HIGH_SALE_VALUE_USD,
            "high_officer_sale_value_usd": HIGH_OFFICER_SALE_VALUE_USD,
            "high_10b5_sale_rows": HIGH_TEN_B5_SALE_ROWS,
            "loss_tail_pnl_pct": LOSS_TAIL_PNL_PCT,
            "bucket_rule": (
                "high_sale_overhang if sale_value >= $5M, officer sale value >= "
                "$1M, or any 10b5-1 sale row in the 10 calendar days before entry; "
                "moderate_or_routine_disposal for other sale/tax-withholding rows; "
                "otherwise no_sale_overhang."
            ),
            "uses_realized_exit_information": False,
            "alters_strategy_behavior": False,
        },
        "pooled": {
            "all": summarize_rows(covered_rows),
            "buckets": buckets,
            "high_vs_clean": compare_high_clean(buckets),
        },
        "by_window": by_window,
        "source_audit": source_audit,
        "form4_audit": form4_audit,
        "sample_high_bucket_rows": [
            row for row in covered_rows if row.get("bucket") == "high_sale_overhang"
        ][:25],
        "sample_clean_bucket_rows": [
            row for row in covered_rows if row.get("bucket") == "no_sale_overhang"
        ][:25],
    }


def evaluate_gate4(attribution: dict[str, Any]) -> dict[str, Any]:
    pooled = attribution["pooled"]
    buckets = pooled["buckets"]
    all_summary = pooled["all"]
    high = buckets.get("high_sale_overhang") or {}
    clean = buckets.get("no_sale_overhang") or {}
    comparison = pooled["high_vs_clean"]
    supporting = []
    for label, row in attribution["by_window"].items():
        comp = row["high_vs_clean"]
        if (
            comp.get("available")
            and (comp.get("high_minus_clean_avg_pnl") or 0.0) < 0
            and (comp.get("high_minus_clean_win_rate") or 0.0) < 0
            and (comp.get("high_minus_clean_loss_tail_rate") or 0.0) > 0
        ):
            supporting.append(label)

    failures: list[str] = []
    if (all_summary.get("covered_n") or 0) < MIN_COVERED_ROWS:
        failures.append("form4_archive_coverage_too_small")
    if (high.get("n") or 0) < MIN_HIGH_BUCKET_ROWS:
        failures.append("high_sale_bucket_sample_too_small")
    if (clean.get("n") or 0) < MIN_CLEAN_BUCKET_ROWS:
        failures.append("clean_bucket_sample_too_small")
    if not comparison.get("available"):
        failures.append("high_clean_comparison_unavailable")
    else:
        if (comparison.get("high_minus_clean_avg_pnl") or 0.0) >= 0:
            failures.append("high_sale_avg_pnl_not_worse")
        if (comparison.get("high_minus_clean_win_rate") or 0.0) >= 0:
            failures.append("high_sale_win_rate_not_worse")
        if (comparison.get("high_minus_clean_loss_tail_rate") or 0.0) <= 0:
            failures.append("high_sale_loss_tail_not_worse")
    if len(supporting) < MIN_SUPPORTING_WINDOWS:
        failures.append("insufficient_window_support")

    observed_only_lead = not failures
    return {
        "passed": observed_only_lead,
        "observed_only_lead": observed_only_lead,
        "decision": (
            "observed_only_positive_form4_sale_overhang_loss_tail_edge"
            if observed_only_lead
            else "rejected_no_form4_sale_overhang_loss_tail_edge"
        ),
        "acceptance_rule": (
            "Observed-only lead only if Form4 archive-covered accepted-core rows "
            ">=50, high-sale bucket >=8, clean bucket >=10, pooled high-sale "
            "bucket has lower average PnL, lower win rate, and higher 2pct "
            "loss-tail rate than clean rows, with at least two standard windows "
            "supporting the same direction. No strategy acceptance is possible."
        ),
        "failed_reasons": failures,
        "supporting_windows": supporting,
        "pooled_high_vs_clean": comparison,
        "minimums": {
            "min_covered_rows": MIN_COVERED_ROWS,
            "min_high_bucket_rows": MIN_HIGH_BUCKET_ROWS,
            "min_clean_bucket_rows": MIN_CLEAN_BUCKET_ROWS,
            "min_supporting_windows": MIN_SUPPORTING_WINDOWS,
        },
    }


def calibration(gate4: dict[str, Any], prediction: dict[str, Any]) -> dict[str, Any]:
    actual_success = 1 if gate4.get("observed_only_lead") else 0
    prob = float(prediction.get("success_probability") or 0.0)
    return {
        "actual_decision": gate4["decision"],
        "actual_success": actual_success,
        "predicted_success_probability": prob,
        "brier_score": round((prob - actual_success) ** 2, 6),
        "expected_ev_delta": prediction.get("expected_ev_delta"),
        "actual_ev_delta": 0.0,
        "expected_pnl_delta": prediction.get("expected_pnl_delta"),
        "actual_pnl_delta": 0.0,
        "predicted_failure_modes": prediction.get("main_failure_modes") or [],
        "realized_failure_mode": ";".join(gate4.get("failed_reasons") or []),
        "predicted_failure_mode_hit": bool(gate4.get("failed_reasons")),
        "surprise_note": (
            "PIT Form 4 sale overhang did not produce a robust high-vs-clean "
            "loss-tail separation on the accepted stack."
            if not gate4.get("observed_only_lead")
            else "PIT Form 4 sale overhang separated accepted-stack loss tail and needs prospective logging."
        ),
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") or {}
    form4_index, form4_audit = load_form4_index()
    rows, source_audit = load_rows(form4_index)
    attribution = build_attribution(rows, source_audit, form4_audit)
    gate4 = evaluate_gate4(attribution)
    baseline = load_baseline_summary()
    status = "observed_only" if gate4["observed_only_lead"] else "rejected"
    why = (
        "The fixed PIT Form 4 sale-overhang split did not satisfy the loss-tail "
        "rule on accepted core trades: high-sale rows failed at least one pooled "
        "direction check, bucket-size check, or window-support check. This should "
        "not be retuned on the same frozen accepted-stack windows."
        if not gate4["observed_only_lead"]
        else (
            "High PIT Form 4 sale overhang separated lower PnL and heavier loss "
            "tail from clean accepted-core entries across the fixed checks. This "
            "remains observed-only and needs default-off prospective logging before "
            "any risk policy use."
        )
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": gate4["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": gate4["observed_only_lead"],
        "lane": LANE,
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "calibration": calibration(gate4, prediction),
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": (
                    "experiment.py new reported no blocking matches. The nearest "
                    "families were Form4 candidate-pool or forward-context attempts; "
                    "this run uses a new gate shape over already accepted trades."
                ),
                "new_evidence_axis": NEW_EVIDENCE_AXIS,
                "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            },
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": gate4["acceptance_rule"],
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": attribution["parameters"],
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "strategy_behavior_changed": False,
        },
        "gate1": {
            "passed": True,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "standard_window_result": repo_rel(STANDARD_WINDOW_RESULT),
            "window_files": {label: repo_rel(path) for label, path in WINDOW_FILES.items()},
        },
        "gate2": {
            "passed": all(
                row["trade_rows"] == row["rows_with_entry_date"]
                and row["trade_rows"] == row["rows_with_target_price_reconstructed"]
                and row["trade_rows"] == row["rows_with_form4_archive_coverage"]
                for row in source_audit.values()
            )
            and form4_audit["deduped_rows_loaded"] > 0
            and (attribution["pooled"]["all"].get("covered_n") or 0) > 0,
            "dependency_fields_checked": [
                "entry_date",
                "entry_price",
                "stop_price",
                "target_mult_used",
                "target_price_reconstructed",
                "pnl",
                "pnl_pct_net",
                "daily_non_ohlcv_snapshot_YYYYMMDD",
                "Form4 usable_trade_date",
                "Form4 transaction_code",
                "Form4 transaction_value",
                "Form4 10b5_1_flag",
                "Form4 is_officer",
            ],
            "target_price_note": (
                "Closed trade rows omit original target_price; runner reconstructs "
                "entry_price + (entry_price - stop_price) * target_mult_used and "
                "does not schedule executable orders."
            ),
            "source_audit": source_audit,
            "form4_audit": form4_audit,
        },
        "gate3": {
            "passed": True,
            "note": "No executable filter was added; core survival is unchanged.",
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "survival_rate_delta": 0.0,
        },
        "gate4": gate4,
        "attribution": attribution,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "trade_enabled": False,
            "daily_snapshot_exposed": False,
            "parity_test_added": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "uses_llm": False,
            "parity_note": (
                "Read-only attribution over accepted backtest trade rows. No "
                "production or backtest decision path changed."
            ),
        },
        "rejection_reason": ";".join(gate4["failed_reasons"]) if gate4["failed_reasons"] else None,
        "next_retry_requires": (
            "Do not retune Form4 transaction-code lists, sale-value thresholds, "
            "10b5 handling, owner roles, lookback days, or a notional response "
            "curve on the same accepted-stack windows. A retry needs explicit "
            "Form 144 plan/float context, executive ownership/compensation "
            "provenance, or prospective forward rows tagged by a shared Form4 "
            "context logger."
        ),
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not rerun this accepted-stack Form4 attribution by changing "
                "S/F/P code handling, sale-value buckets, 10b5-1 treatment, owner "
                "roles, lookback length, or converting the same field into a risk "
                "scalar response curve."
            ),
            "new_evidence_required": (
                "Explicit Form 144 plan/float context, executive ownership and "
                "compensation provenance, or prospectively closed forward rows from "
                "a shared default-off Form4 context logger."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(BASELINE_RESULT),
            repo_rel(STANDARD_WINDOW_RESULT),
            repo_rel(NON_OHLCV_DIR),
            *[repo_rel(path) for path in WINDOW_FILES.values()],
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
        "anti_js": {
            "strategy_behavior_changed": False,
            "threshold_scan": False,
            "uses_future_form4_rows": False,
            "entry_day_close_used": False,
        },
    }


def compact_log(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "observed_only_lead",
        "lane",
        "owner",
        "hypothesis",
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
        "new_evidence_axis",
        "prediction",
        "calibration",
        "parameters",
        "delta_metrics",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "production_impact",
        "rejection_reason",
        "next_retry_requires",
        "post_run_reflection",
        "related_files",
        "reproduction_commands",
        "anti_js",
    ]
    row = {key: payload[key] for key in keys if key in payload}
    row["attribution_summary"] = {
        "pooled": {
            "all": payload["attribution"]["pooled"]["all"],
            "buckets": payload["attribution"]["pooled"]["buckets"],
            "high_vs_clean": payload["attribution"]["pooled"]["high_vs_clean"],
        },
        "by_window": payload["attribution"]["by_window"],
        "source_audit": payload["attribution"]["source_audit"],
        "form4_audit": payload["attribution"]["form4_audit"],
    }
    return row


def build_card(payload: dict[str, Any]) -> str:
    pooled = payload["attribution"]["pooled"]
    gate4 = payload["gate4"]
    comp = pooled["high_vs_clean"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Accepted-Core Form4 Selling Overhang Attribution",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Status: `{payload['status']}`",
            f"- Observed-only lead: `{payload['observed_only_lead']}`",
            f"- Covered rows: `{pooled['all'].get('covered_n')}`",
            f"- High-sale rows: `{pooled['buckets']['high_sale_overhang'].get('n')}`",
            f"- Clean rows: `{pooled['buckets']['no_sale_overhang'].get('n')}`",
            f"- High minus clean avg PnL: `{comp.get('high_minus_clean_avg_pnl')}`",
            f"- High minus clean win rate: `{comp.get('high_minus_clean_win_rate')}`",
            f"- High minus clean loss-tail rate: `{comp.get('high_minus_clean_loss_tail_rate')}`",
            f"- Failed reasons: `{gate4['failed_reasons']}`",
            "",
            "## Hypothesis",
            "",
            HYPOTHESIS,
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
    ]
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
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": payload["observed_only_lead"],
        "gate4_passed": payload["gate4"]["passed"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    fields = {
        key: payload[key]
        for key in [
            "owner",
            "hypothesis",
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
            "new_evidence_axis",
            "parameters",
            "pre_run_questions",
            "gate1",
            "gate2",
            "gate3",
            "gate4",
            "production_impact",
            "post_run_reflection",
            "rejection_reason",
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
        prediction=payload["prediction"],
        result=result,
        status=payload["status"],
        fields=fields,
    )
    write_json(MANIFEST_JSON, build_manifest(payload, log_row))


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(json.dumps(safe(compact_log(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
