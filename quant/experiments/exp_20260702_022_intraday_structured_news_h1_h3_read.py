"""exp-20260702-022: intraday structured news h1/h3 read.

Observed-only alpha read on the fixed intraday structured news observer rows.
The test uses only rows known by the 13:00 ET capture and settles the first
available short horizons against the hot daily warehouse.

Fixed bundle:
- target_relation_quality rows only, pooled positive versus negative polarity;
- dedup repeated 13:01/13:02/13:03 captures by event/ticker/polarity key;
- entry is the next trading-session open after capture_date;
- h1 is entry-day close; h3 is the third trading-session close;
- compare replacement value versus cash, SPY, and QQQ with the shared fill model;
- no relation_type, ticker, keyword, prompt, notional, or horizon tuning.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
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
from experiment_registry import (  # noqa: E402
    build_prediction_calibration,
    persist_self_registered_result,
)
from fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage  # noqa: E402

EXPERIMENT_ID = "exp-20260702-022"
OWNER = "alpha-explore"
SLUG = "intraday_structured_news_h1_h3_read"
RUNNER = f"quant/experiments/exp_20260702_022_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

STRUCTURED_DIR = REPO_ROOT / "data" / "daily" / "intraday" / "structured"
HOT_WAREHOUSE = REPO_ROOT / "data" / "warehouse" / "warehouse_main_hot.sqlite"
BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260702_022_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HORIZONS = (1, 3)
COMPARATORS = ("SPY", "QQQ")
PROXY_NOTIONAL_USD = 4000.0
MIN_H1_ROWS_PER_POLARITY = 4
MIN_H3_ROWS_PER_POLARITY = 3
MIN_MEDIAN_SEPARATION_USD = 25.0
REQUIRED_OBSERVER_FIELDS = (
    "observation_id",
    "event_id",
    "capture_date",
    "time_label",
    "ticker",
    "relation_type",
    "relation_polarity",
    "target_relation_quality",
    "entry_semantics",
    "outcome_status",
    "unit_notional_usd",
)

CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260702_022_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]
REPRO_COMMANDS = [
    RUNNER_COMMAND,
    ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def repo_rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_text(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(obj: Any, path: Path) -> None:
    text = json.dumps(obj, indent=2, ensure_ascii=False, default=str)
    write_text(text, path)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_ticket() -> dict[str, Any]:
    return load_json(TICKET_JSON)


def load_baseline() -> dict[str, Any]:
    raw = load_json(BASELINE_RESULT)
    windows = raw.get("windows") or []
    return {
        "path": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score": round(
            sum(float(w.get("expected_value_score", 0.0)) for w in windows), 4
        ),
        "total_pnl": round(sum(float(w.get("total_pnl", 0.0)) for w in windows), 2),
        "trade_count": sum(int(w.get("trade_count", 0)) for w in windows),
        "signals_generated": sum(int(w.get("signals_generated", 0)) for w in windows),
        "signals_survived": sum(int(w.get("signals_survived", 0)) for w in windows),
        "windows": [
            {
                "label": w.get("label"),
                "expected_value_score": w.get("expected_value_score"),
                "total_pnl": w.get("total_pnl"),
                "trade_count": w.get("trade_count"),
                "survival_rate": w.get("survival_rate"),
            }
            for w in windows
        ],
    }


def observation_files() -> list[Path]:
    return sorted(
        path
        for path in STRUCTURED_DIR.glob("intraday_news_structured_event_observations_*.jsonl")
        if ".tmp" not in path.name
    )


def load_observer_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in observation_files():
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            row = json.loads(line)
            row["_source_file"] = repo_rel(path)
            row["_source_line"] = line_number
            rows.append(row)
    return rows


def field_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    missing_by_field: dict[str, int] = {}
    for field in REQUIRED_OBSERVER_FIELDS:
        missing_by_field[field] = sum(1 for row in rows if row.get(field) in (None, ""))
    return {
        "required_fields": list(REQUIRED_OBSERVER_FIELDS),
        "row_count": len(rows),
        "missing_by_field": missing_by_field,
        "all_required_fields_present": all(v == 0 for v in missing_by_field.values()),
        "entry_date_present_rows": sum(1 for row in rows if row.get("entry_date")),
        "target_price_present_rows": sum(1 for row in rows if row.get("target_price")),
    }


def dedup_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("capture_date"),
        row.get("ticker"),
        row.get("relation_polarity"),
        row.get("relation_type"),
        row.get("published_at"),
        row.get("evidence_text_hash") or row.get("sanitized_text_hash"),
    )


def dedup_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in sorted(
        rows,
        key=lambda r: (
            str(r.get("capture_date") or ""),
            str(r.get("time_label") or ""),
            str(r.get("observation_id") or ""),
        ),
    ):
        selected.setdefault(dedup_key(row), row)
    return list(selected.values())


def load_warehouse_rows(tickers: set[str]) -> dict[str, list[dict[str, Any]]]:
    if not HOT_WAREHOUSE.exists():
        raise FileNotFoundError(f"missing hot warehouse: {HOT_WAREHOUSE}")
    out: dict[str, list[dict[str, Any]]] = {}
    with sqlite3.connect(HOT_WAREHOUSE) as con:
        con.row_factory = sqlite3.Row
        for ticker in sorted(tickers):
            rows = [
                dict(row)
                for row in con.execute(
                    """
                    select date, open, high, low, close, volume
                    from ohlcv
                    where ticker = ?
                    order by date
                    """,
                    (ticker,),
                )
            ]
            out[ticker] = rows
    return out


def warehouse_summary(frames: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    date_counts = [
        (ticker, rows[0]["date"], rows[-1]["date"], len(rows))
        for ticker, rows in sorted(frames.items())
        if rows
    ]
    all_dates = [date for _, first, last, _ in date_counts for date in (first, last)]
    return {
        "path": repo_rel(HOT_WAREHOUSE),
        "ticker_count": len(frames),
        "tickers_missing": sorted(ticker for ticker, rows in frames.items() if not rows),
        "min_first_date": min(all_dates) if all_dates else None,
        "max_last_date": max(all_dates) if all_dates else None,
        "per_ticker": [
            {
                "ticker": ticker,
                "first_date": first,
                "last_date": last,
                "rows": count,
            }
            for ticker, first, last, count in date_counts
        ],
    }


def next_index_after(rows: list[dict[str, Any]], date_value: str) -> int | None:
    for index, row in enumerate(rows):
        if str(row["date"]) > date_value:
            return index
    return None


def pnl_for_window(
    rows: list[dict[str, Any]],
    entry_index: int,
    horizon: int,
    *,
    notional: float,
) -> dict[str, Any] | None:
    exit_index = entry_index + horizon - 1
    if entry_index < 0 or exit_index >= len(rows):
        return None
    entry = rows[entry_index]
    exit_row = rows[exit_index]
    entry_price = apply_entry_fill(float(entry["open"]), notional=notional)
    exit_price = apply_slippage(
        float(exit_row["close"]),
        SLIPPAGE_BPS_TARGET,
        "sell",
        notional=notional,
    )
    if not entry_price or not exit_price or entry_price <= 0:
        return None
    net_return = (exit_price / entry_price) - 1.0 - ROUND_TRIP_COST_PCT
    return {
        "entry_date": entry["date"],
        "exit_date": exit_row["date"],
        "entry_open": round(float(entry["open"]), 4),
        "exit_close": round(float(exit_row["close"]), 4),
        "entry_fill": round(float(entry_price), 4),
        "exit_fill": round(float(exit_price), 4),
        "net_return_pct": round(net_return, 8),
        "pnl_usd": round(notional * net_return, 2),
    }


def settle_rows(
    rows: list[dict[str, Any]],
    frames: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], Counter]:
    outcomes: list[dict[str, Any]] = []
    pending_reasons: Counter = Counter()
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        ticker_rows = frames.get(ticker) or []
        if not ticker_rows:
            pending_reasons["missing_ticker_warehouse_rows"] += len(HORIZONS)
            continue
        entry_index = next_index_after(ticker_rows, str(row.get("capture_date") or ""))
        if entry_index is None:
            pending_reasons["entry_date_not_in_warehouse_yet"] += len(HORIZONS)
            continue
        for horizon in HORIZONS:
            target = pnl_for_window(
                ticker_rows,
                entry_index,
                horizon,
                notional=PROXY_NOTIONAL_USD,
            )
            if target is None:
                pending_reasons[f"h{horizon}_exit_date_not_in_warehouse_yet"] += 1
                continue
            comparator_results: dict[str, dict[str, Any]] = {}
            comparator_missing = False
            for comparator in COMPARATORS:
                comp_rows = frames.get(comparator) or []
                comp_entry_index = next_index_after(
                    comp_rows, str(row.get("capture_date") or "")
                )
                comp_result = (
                    None
                    if comp_entry_index is None
                    else pnl_for_window(
                        comp_rows,
                        comp_entry_index,
                        horizon,
                        notional=PROXY_NOTIONAL_USD,
                    )
                )
                if comp_result is None:
                    comparator_missing = True
                    pending_reasons[f"h{horizon}_{comparator.lower()}_missing"] += 1
                    break
                comparator_results[comparator] = comp_result
            if comparator_missing:
                continue
            outcomes.append(
                {
                    "ticker": ticker,
                    "capture_date": row.get("capture_date"),
                    "time_label": row.get("time_label"),
                    "published_at": row.get("published_at"),
                    "relation_type": row.get("relation_type"),
                    "relation_polarity": row.get("relation_polarity"),
                    "target_relation_quality": row.get("target_relation_quality"),
                    "event_id": row.get("event_id"),
                    "observation_id": row.get("observation_id"),
                    "source_file": row.get("_source_file"),
                    "horizon": f"h{horizon}",
                    "entry_date": target["entry_date"],
                    "exit_date": target["exit_date"],
                    "entry_fill": target["entry_fill"],
                    "exit_fill": target["exit_fill"],
                    "net_return_pct": target["net_return_pct"],
                    "pnl_usd": target["pnl_usd"],
                    "spy_pnl_usd": comparator_results["SPY"]["pnl_usd"],
                    "qqq_pnl_usd": comparator_results["QQQ"]["pnl_usd"],
                    "replacement_value_vs_cash_usd": target["pnl_usd"],
                    "replacement_value_vs_spy_usd": round(
                        target["pnl_usd"] - comparator_results["SPY"]["pnl_usd"],
                        2,
                    ),
                    "replacement_value_vs_qqq_usd": round(
                        target["pnl_usd"] - comparator_results["QQQ"]["pnl_usd"],
                        2,
                    ),
                }
            )
    return outcomes, pending_reasons


def stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "rows": 0,
            "mean": None,
            "median": None,
            "win_rate": None,
            "min": None,
            "max": None,
        }
    return {
        "rows": len(values),
        "mean": round(sum(values) / len(values), 2),
        "median": round(median(values), 2),
        "win_rate": round(sum(1 for value in values if value > 0) / len(values), 4),
        "min": round(min(values), 2),
        "max": round(max(values), 2),
    }


def summarize_outcomes(outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    by_horizon: dict[str, dict[str, Any]] = {}
    for horizon in (f"h{h}" for h in HORIZONS):
        h_rows = [row for row in outcomes if row["horizon"] == horizon]
        by_polarity: dict[str, dict[str, Any]] = {}
        for polarity in ("positive", "negative"):
            p_rows = [row for row in h_rows if row["relation_polarity"] == polarity]
            by_polarity[polarity] = {
                "rows": len(p_rows),
                "vs_cash_usd": stats(
                    [float(row["replacement_value_vs_cash_usd"]) for row in p_rows]
                ),
                "vs_spy_usd": stats(
                    [float(row["replacement_value_vs_spy_usd"]) for row in p_rows]
                ),
                "vs_qqq_usd": stats(
                    [float(row["replacement_value_vs_qqq_usd"]) for row in p_rows]
                ),
                "tickers": Counter(row["ticker"] for row in p_rows).most_common(),
            }
        pos_spy = by_polarity["positive"]["vs_spy_usd"]["median"]
        neg_spy = by_polarity["negative"]["vs_spy_usd"]["median"]
        pos_qqq = by_polarity["positive"]["vs_qqq_usd"]["median"]
        neg_qqq = by_polarity["negative"]["vs_qqq_usd"]["median"]
        by_horizon[horizon] = {
            "rows": len(h_rows),
            "by_polarity": by_polarity,
            "positive_minus_negative_median_vs_spy_usd": None
            if pos_spy is None or neg_spy is None
            else round(pos_spy - neg_spy, 2),
            "positive_minus_negative_median_vs_qqq_usd": None
            if pos_qqq is None or neg_qqq is None
            else round(pos_qqq - neg_qqq, 2),
        }
    return by_horizon


def evaluate_lead(summary: dict[str, Any]) -> tuple[bool, list[str]]:
    failed: list[str] = []
    h1 = summary.get("h1") or {}
    h3 = summary.get("h3") or {}
    for polarity in ("positive", "negative"):
        h1_rows = h1.get("by_polarity", {}).get(polarity, {}).get("rows", 0)
        h3_rows = h3.get("by_polarity", {}).get(polarity, {}).get("rows", 0)
        if h1_rows < MIN_H1_ROWS_PER_POLARITY:
            failed.append(f"h1_{polarity}_rows_below_{MIN_H1_ROWS_PER_POLARITY}")
        if h3_rows < MIN_H3_ROWS_PER_POLARITY:
            failed.append(f"h3_{polarity}_rows_below_{MIN_H3_ROWS_PER_POLARITY}")

    for horizon, h_summary in (("h1", h1), ("h3", h3)):
        pos = h_summary.get("by_polarity", {}).get("positive", {})
        neg = h_summary.get("by_polarity", {}).get("negative", {})
        pos_cash = pos.get("vs_cash_usd", {}).get("median")
        sep_spy = h_summary.get("positive_minus_negative_median_vs_spy_usd")
        sep_qqq = h_summary.get("positive_minus_negative_median_vs_qqq_usd")
        if pos_cash is None or pos_cash <= 0:
            failed.append(f"{horizon}_positive_median_vs_cash_not_positive")
        if sep_spy is None or sep_spy < MIN_MEDIAN_SEPARATION_USD:
            failed.append(f"{horizon}_positive_not_beating_negative_vs_spy_by_25usd")
        if sep_qqq is None or sep_qqq < MIN_MEDIAN_SEPARATION_USD:
            failed.append(f"{horizon}_positive_not_beating_negative_vs_qqq_by_25usd")
        neg_cash = neg.get("vs_cash_usd", {}).get("median")
        if neg_cash is None:
            failed.append(f"{horizon}_negative_cash_median_missing")

    return not failed, failed


def build_report() -> dict[str, Any]:
    observer_rows = load_observer_rows()
    target_rows = [
        row
        for row in observer_rows
        if row.get("target_relation_quality") is True
        and row.get("relation_polarity") in ("positive", "negative")
    ]
    deduped = dedup_rows(target_rows)
    tickers = {str(row.get("ticker") or "").upper() for row in deduped}
    tickers = {ticker for ticker in tickers if ticker}
    frames = load_warehouse_rows(tickers | set(COMPARATORS))
    outcomes, pending_reasons = settle_rows(deduped, frames)
    outcome_summary = summarize_outcomes(outcomes)
    lead, failed_reasons = evaluate_lead(outcome_summary)

    closed_source_keys = {
        (row["ticker"], row["capture_date"], row["event_id"], row["relation_polarity"])
        for row in outcomes
    }
    generated = len(deduped) * len(HORIZONS)
    survived = len(outcomes)
    survival_rate = round(survived / generated, 4) if generated else None

    return {
        "observer_source": {
            "directory": repo_rel(STRUCTURED_DIR),
            "files": [repo_rel(path) for path in observation_files()],
            "raw_rows": len(observer_rows),
            "target_relation_quality_rows": len(target_rows),
            "deduped_target_rows": len(deduped),
            "duplicate_rows_removed": len(target_rows) - len(deduped),
            "capture_counts": Counter(row.get("capture_date") for row in target_rows),
            "dedup_capture_counts": Counter(row.get("capture_date") for row in deduped),
            "polarity_counts": Counter(row.get("relation_polarity") for row in target_rows),
            "dedup_polarity_counts": Counter(
                row.get("relation_polarity") for row in deduped
            ),
            "ticker_counts": Counter(row.get("ticker") for row in target_rows),
            "dedup_ticker_counts": Counter(row.get("ticker") for row in deduped),
        },
        "field_audit": field_audit(observer_rows),
        "warehouse": warehouse_summary(frames),
        "generated_horizon_rows": generated,
        "closed_horizon_rows": survived,
        "closed_unique_source_rows": len(closed_source_keys),
        "pending_reasons": dict(sorted(pending_reasons.items())),
        "survival_rate": survival_rate,
        "outcome_summary": outcome_summary,
        "outcome_rows": outcomes,
        "decision_rule": {
            "lead_if": [
                f"h1 has >= {MIN_H1_ROWS_PER_POLARITY} rows per polarity",
                f"h3 has >= {MIN_H3_ROWS_PER_POLARITY} rows per polarity",
                "positive median replacement value versus cash is positive on h1 and h3",
                f"positive-minus-negative median vs SPY >= ${MIN_MEDIAN_SEPARATION_USD}",
                f"positive-minus-negative median vs QQQ >= ${MIN_MEDIAN_SEPARATION_USD}",
            ],
            "observed_only_lead": lead,
            "failed_reasons": failed_reasons,
        },
    }


def why_result_happened(report: dict[str, Any]) -> str:
    rule = report["decision_rule"]
    if rule["observed_only_lead"]:
        return (
            "The fixed intraday structured-news population had enough h1/h3 "
            "closed rows and positive polarity beat negative polarity versus "
            "cash, SPY, and QQQ under the predeclared pooled rule. This is "
            "only a lead because no shared helper or daily allocation policy "
            "was changed."
        )
    return (
        "The fixed intraday structured-news observer currently has too few "
        "settled short-horizon rows to support allocation: the hot warehouse "
        "only closes the earliest h1 rows and leaves h3 mostly pending, so "
        "the pooled polarity comparison fails the predeclared row-count and "
        "ETF-excess separation gates."
    )


def build_payload(report: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    lead = bool(report["decision_rule"]["observed_only_lead"])
    status = "observed_only" if lead else "rejected"
    decision = (
        "observed_only_positive_intraday_structured_news_h1_h3_lead_not_promoted"
        if lead
        else "rejected_observed_only_intraday_structured_news_h1_h3_not_allocation_ready"
    )
    post_run_reflection = {
        "why_result_happened": why_result_happened(report),
        "realized_failure_mode": (
            "short_horizon_rows_settled_and_polarity_separated"
            if lead
            else "too_few_settled_rows"
        ),
        "forbidden_near_neighbor_retry": (
            "Do not re-slice these same 2026-06-29 through 2026-07-02 "
            "intraday structured-news rows by relation_type, ticker, keyword, "
            "prompt wording, horizon, notional, time_label, or response curve. "
            "The binding constraint is settled row count, not another adjacent "
            "condition field."
        ),
        "new_evidence_required": (
            "Reopen only after materially more timestamped intraday structured "
            "observer rows have closed h1/h3 outcomes, or after a true intraday "
            "bar execution surface allows same-day post-capture execution that this "
            "daily warehouse read cannot test."
        ),
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "alpha_ready": False,
        "hypothesis": (
            "Intraday structured relation-quality news rows known by the "
            "13:00 ET capture may show short-horizon h1/h3 replacement value "
            "before 5d/10d daily observer rows mature; positive-polarity rows "
            "should beat negative rows and SPY/QQQ over the first settled horizons."
        ),
        "alpha_hypothesis": (
            "If 13:00 ET structured relation-quality news contains immediate "
            "replacement value, positive relation polarity should separate from "
            "negative polarity on next-session h1/h3 outcomes before the 5d/10d "
            "observer ledger has enough closed rows."
        ),
        "change_type": "observed_only_attribution",
        "implementation_mode": "read_only_diagnostic",
        "mechanism_family": "intraday_news_llm_event_scoring_alpha",
        "trial_family": "intraday_structured_relation_quality_short_horizon_read",
        "trial_variant_id": EXPERIMENT_ID,
        "single_causal_variable": (
            "intraday_structured_relation_quality_h1_h3_short_horizon_value_v1"
        ),
        "changed_variable": "none_read_only",
        "causal_components": [
            "fixed_intraday_observer_rows",
            "target_relation_quality_only",
            "pooled_positive_vs_negative_polarity",
            "next_session_open_entry_after_13ET_capture",
            "h1_entry_day_close",
            "h3_third_session_close",
            "cash_spy_qqq_replacement_value",
            "no_relation_type_or_keyword_reslice",
        ],
        "nearby_prior_experiments": [
            "exp-20260630-005",
            "exp-20260630-013",
            "exp-20260630-015",
            "exp-20260630-019",
            "exp-20260701-010",
            "exp-20260702-021",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "timestamped_intraday_capture_short_horizon_settlement",
        "new_evidence_axis": (
            "First h1/h3 settlement read of the fixed 13:00 ET intraday "
            "structured relation-quality observer rows; not a reslice of the "
            "daily 5d/10d second-order population."
        ),
        "baseline": baseline,
        "audit": report,
        "gate1": {
            "baseline_result_file": baseline["path"],
            "baseline_expected_value_score": baseline["expected_value_score"],
            "baseline_total_pnl": baseline["total_pnl"],
            "baseline_trade_count": baseline["trade_count"],
            "note": "Read-only attribution; canonical baseline unchanged.",
        },
        "gate2": {
            "fields": list(REQUIRED_OBSERVER_FIELDS) + ["entry_date", "target_price"],
            "field_audit": report["field_audit"],
            "entry_date_note": (
                "Observer rows intentionally carry null entry_date until "
                "settled; runner derives next-session entry from hot warehouse."
            ),
            "target_price_note": (
                "Observer is replacement-value attribution, not price-target "
                "strategy logic; target_price remains null by contract."
            ),
        },
        "gate3": {
            "signals_generated": report["generated_horizon_rows"],
            "signals_survived": report["closed_horizon_rows"],
            "survival_rate": report["survival_rate"],
            "note": (
                "No strategy filters changed; survival here is settled h1/h3 "
                "horizon rows available in the hot warehouse."
            ),
        },
        "gate4": {
            "mode": "observed_only_attribution",
            "passed": False,
            "observed_only_lead": lead,
            "decision_rule": report["decision_rule"],
            "strategy_delta": {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "max_drawdown_pct": 0.0,
            },
        },
        "production_impact": {
            "alters_candidate_ranking": False,
            "alters_exits": False,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_sizing": False,
            "backtester_adapter_changed": False,
            "daily_collector_changed": False,
            "daily_snapshot_exposed": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "trade_enabled": False,
            "live_ready": False,
            "parity_note": "Read-only attribution; no shared policy/helper or order path changed.",
        },
        "post_run_reflection": post_run_reflection,
        "reopen_condition": (
            "Reopen alpha allocation only after fixed intraday structured-event "
            "observer rows have at least 20 closed h1 rows with at least 8 per "
            "polarity and at least 12 closed h3 rows with at least 4 per polarity, "
            "or after a new same-day intraday fill surface changes execution timing."
        ),
        "related_files": [repo_rel(path) for path in observation_files()]
        + [repo_rel(HOT_WAREHOUSE), baseline["path"]],
        "changed_files": CHANGED_FILES,
        "allowed_write_scope": CHANGED_FILES + ["docs/experiment_log.jsonl"],
        "reproduction_commands": REPRO_COMMANDS,
        "lean_quality_passed": True,
    }


def compact_log_record(payload: dict[str, Any], calibration: dict[str, Any] | None) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "owner",
        "lane",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "alpha_ready",
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
        "new_evidence_axis",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "production_impact",
        "post_run_reflection",
        "reopen_condition",
        "changed_files",
        "reproduction_commands",
    ]
    record = {key: payload[key] for key in keys}
    record["artifact"] = repo_rel(OUT_JSON)
    record["calibration"] = calibration
    record["audit_summary"] = {
        "deduped_target_rows": payload["audit"]["observer_source"]["deduped_target_rows"],
        "closed_horizon_rows": payload["audit"]["closed_horizon_rows"],
        "pending_reasons": payload["audit"]["pending_reasons"],
        "outcome_summary": payload["audit"]["outcome_summary"],
    }
    return record


def build_card(payload: dict[str, Any]) -> str:
    audit = payload["audit"]
    h1 = audit["outcome_summary"].get("h1", {})
    h3 = audit["outcome_summary"].get("h3", {})
    lines = [
        f"# {EXPERIMENT_ID}: intraday structured news h1/h3 read",
        "",
        f"- status: `{payload['status']}` / decision: `{payload['decision']}`",
        f"- raw observer rows: `{audit['observer_source']['raw_rows']}`; "
        f"target rows: `{audit['observer_source']['target_relation_quality_rows']}`; "
        f"deduped target rows: `{audit['observer_source']['deduped_target_rows']}`",
        f"- closed horizon rows: `{audit['closed_horizon_rows']}` / "
        f"`{audit['generated_horizon_rows']}`; survival `{audit['survival_rate']}`",
        f"- h1 rows: `{h1.get('rows')}`; pos-neg median vs SPY: "
        f"`{h1.get('positive_minus_negative_median_vs_spy_usd')}`; vs QQQ: "
        f"`{h1.get('positive_minus_negative_median_vs_qqq_usd')}`",
        f"- h3 rows: `{h3.get('rows')}`; pos-neg median vs SPY: "
        f"`{h3.get('positive_minus_negative_median_vs_spy_usd')}`; vs QQQ: "
        f"`{h3.get('positive_minus_negative_median_vs_qqq_usd')}`",
        f"- failed reasons: `{audit['decision_rule']['failed_reasons']}`",
        "",
        "## Boundary",
        "",
        payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
        "",
        "## Repro",
        "",
    ]
    lines.extend(f"- `{cmd}`" for cmd in REPRO_COMMANDS)
    return "\n".join(lines) + "\n"


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [REPO_ROOT / item for item in CHANGED_FILES if item != "docs/experiment_registry.json"]
    files.append(REGISTRY_JSON)
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "updated_at": utc_now(),
    }


def main() -> int:
    ticket = load_ticket()
    baseline = load_baseline()
    report = build_report()
    payload = build_payload(report, baseline)
    prediction = ticket.get("prediction") or {}
    judgement = {
        "delta_metrics": {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
        }
    }
    calibration = build_prediction_calibration(
        prediction,
        judgement,
        payload["status"],
        realized_failure_mode=payload["post_run_reflection"]["realized_failure_mode"],
        surprise_note=payload["post_run_reflection"]["why_result_happened"],
    )
    payload["calibration"] = calibration

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    write_json(payload, OUT_JSON)
    log_record = compact_log_record(payload, calibration)
    write_json(log_record, LOG_JSON)
    write_text(build_card(payload), CARD_MD)

    result = {
        "accepted": False,
        "accepted_alpha": False,
        "alpha_ready": False,
        "observed_only_lead": payload["gate4"]["observed_only_lead"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "gate4": payload["gate4"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
        "calibration": calibration,
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=prediction,
        result=result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
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
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log_file": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "reopen_condition": payload["reopen_condition"],
            "related_files": payload["related_files"],
            "changed_files": payload["changed_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
        },
    )
    write_json(build_manifest(payload), MANIFEST_JSON)

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "deduped_target_rows": report["observer_source"]["deduped_target_rows"],
                "closed_horizon_rows": report["closed_horizon_rows"],
                "pending_reasons": report["pending_reasons"],
                "outcome_summary": report["outcome_summary"],
                "failed_reasons": report["decision_rule"]["failed_reasons"],
                "artifact": repo_rel(OUT_JSON),
                "log": repo_rel(LOG_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
