"""exp-20260630-005: structured daily-news event forward-value attribution.

Observed-only alpha search. This runner joins the structured event evidence
ledger from exp-20260630-004 to next-session 5d/10d outcomes and asks whether a
fixed positive relation-quality cohort separates replacement value better than
the broad explicit-news control population.

It changes no entry, exit, ranking, sizing, paper, live, LLM prompt, or news
archive behavior.
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
from typing import Any, Iterable, Mapping


EXPERIMENT_ID = "exp-20260630-005"
OWNER = "alpha-explore"
SLUG = "daily_news_structured_event_forward_value"
RUNNER = f"quant/experiments/exp_20260630_005_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
QUANT_ROOT = REPO_ROOT / "quant"
for root in (REPO_ROOT, SCRIPTS_ROOT, QUANT_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)
from quant.ohlcv_warehouse import DEFAULT_WAREHOUSE_PATH, load_warehouse_ohlcv_frames  # noqa: E402


BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
STRUCTURED_LEDGER = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260630-004"
    / "daily_news_structured_event_ledger.jsonl"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260630_005_{SLUG}.json"
SETTLED_LEDGER = OUT_DIR / "daily_news_structured_event_forward_value_rows.jsonl"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Structured daily-news actor/relation/magnitude evidence rows may identify "
    "production-visible LLM event-scoring alpha if a fixed relation-quality "
    "cohort has positive closed 5d/10d replacement value versus explicit-news "
    "controls without changing trading behavior."
)
CHANGE_TYPE = "llm_event_scoring_forward_attribution"
MECHANISM_FAMILY = "daily_news_llm_event_scoring_alpha"
TRIAL_FAMILY = "structured_daily_news_relation_magnitude_forward_value"
TRIAL_VARIANT_ID = "v1_relation_quality_closed_outcomes"
CHANGED_VARIABLE = "structured_daily_news_relation_magnitude_forward_value_v1"
NEW_EVIDENCE_TYPE = "structured_pit_event_relation_magnitude_closed_outcome_rows"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260630-001",
    "exp-20260630-002",
    "exp-20260630-004",
]
CAUSAL_COMPONENTS = [
    "structured event ledger",
    "closed OHLCV outcome join",
    "cash SPY QQQ replacement value",
    "no strategy behavior change",
]

TARGET_RELATIONS = {
    "financial_growth_or_beat",
    "guidance_or_rating_upgrade",
    "product_or_approval_catalyst",
    "customer_order_or_partnership",
}
EXCLUDED_POSITIVE_RELATIONS = {"capital_return"}
CONFIG = {
    "unit_notional_usd": 4000.0,
    "horizons": [5, 10],
    "target_relations": sorted(TARGET_RELATIONS),
    "excluded_positive_relations": sorted(EXCLUDED_POSITIVE_RELATIONS),
    "min_closed_10d_target_rows": 30,
    "min_target_event_dates": 12,
    "min_mean_10d_return_edge_vs_control": 0.005,
    "min_mean_10d_replacement_vs_spy_usd": 0.0,
    "min_mean_10d_replacement_vs_qqq_usd": 0.0,
    "max_single_ticker_target_share": 0.35,
    "dedupe_key": "event_date,ticker,relation_type,evidence_text_hash",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict):
                    rows.append(item)
    except OSError:
        pass
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(safe(row), ensure_ascii=True, sort_keys=True) + "\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def as_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def median_or_none(values: list[float]) -> float | None:
    return float(median(values)) if values else None


def pct(value: Any) -> str:
    number = as_float(value)
    return "n/a" if number is None else f"{number:.2%}"


def money(value: Any) -> str:
    number = as_float(value)
    return "n/a" if number is None else f"${number:,.2f}"


def load_ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    return (ticket.get("prediction") if isinstance(ticket, dict) else None) or {}


def load_baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = list(payload.get("windows") or [])
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "windows": windows,
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 4) if generated else None,
        "max_drawdown_pct_worst": max(
            (float(row.get("max_drawdown_pct") or 0.0) for row in windows),
            default=None,
        ),
    }


def event_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("event_date") or ""),
        str(row.get("ticker") or ""),
        str(row.get("relation_type") or ""),
        str(row.get("evidence_text_hash") or ""),
    )


def is_target_event(row: Mapping[str, Any]) -> bool:
    return (
        row.get("relation_polarity") == "positive"
        and str(row.get("relation_type") or "") in TARGET_RELATIONS
    )


def has_magnitude(row: Mapping[str, Any]) -> bool:
    magnitude = row.get("magnitude") or {}
    return bool(isinstance(magnitude, Mapping) and magnitude.get("has_numeric_magnitude"))


def load_event_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw = read_jsonl(STRUCTURED_LEDGER)
    deduped: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    duplicate_count = 0
    for row in raw:
        ticker = str(row.get("ticker") or "").upper().strip()
        event_date = str(row.get("event_date") or "").strip()
        if not ticker or not event_date:
            continue
        row = dict(row)
        row["ticker"] = ticker
        row["target_relation_quality"] = is_target_event(row)
        row["magnitude_qualified"] = has_magnitude(row)
        key = event_key(row)
        if key in deduped:
            duplicate_count += 1
            continue
        deduped[key] = row
    rows = sorted(deduped.values(), key=lambda row: (*event_key(row), str(row.get("event_id") or "")))
    dates = [str(row.get("event_date")) for row in rows if row.get("event_date")]
    relation_counts = Counter(str(row.get("relation_type") or "unknown") for row in rows)
    polarity_counts = Counter(str(row.get("relation_polarity") or "unknown") for row in rows)
    return rows, {
        "structured_ledger": repo_rel(STRUCTURED_LEDGER),
        "raw_rows": len(raw),
        "deduped_rows": len(rows),
        "duplicate_rows_removed": duplicate_count,
        "event_date_count": len(set(dates)),
        "date_range": {"start": min(dates) if dates else None, "end": max(dates) if dates else None},
        "relation_counts": dict(sorted(relation_counts.items())),
        "polarity_counts": dict(sorted(polarity_counts.items())),
        "target_rows_raw": sum(1 for row in rows if row["target_relation_quality"]),
        "magnitude_rows_raw": sum(1 for row in rows if row["magnitude_qualified"]),
    }


def frame_to_rows(frame: Any) -> list[dict[str, Any]]:
    out = []
    for day, row in frame.iterrows():
        open_ = as_float(row.get("Open"))
        close = as_float(row.get("Close"))
        if open_ is None or close is None:
            continue
        out.append({"date": str(day.date()), "open": open_, "close": close})
    out.sort(key=lambda item: item["date"])
    return out


def load_bars(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    tickers = {str(row["ticker"]) for row in rows}
    tickers.update({"SPY", "QQQ"})
    dates = sorted(str(row["event_date"]) for row in rows if row.get("event_date"))
    start = dates[0] if dates else "2026-01-01"
    frames = load_warehouse_ohlcv_frames(DEFAULT_WAREHOUSE_PATH, sorted(tickers), start, "2026-12-31")
    return {ticker: frame_to_rows(frame) for ticker, frame in frames.items()}


def next_index_after(bars: list[dict[str, Any]], date_text: str) -> int | None:
    for index, row in enumerate(bars):
        if row["date"] > date_text:
            return index
    return None


def return_between(bars: list[dict[str, Any]], entry_date: str, exit_date: str) -> float | None:
    by_date = {row["date"]: row for row in bars}
    entry = by_date.get(entry_date)
    exit_ = by_date.get(exit_date)
    if not entry or not exit_:
        return None
    if entry["open"] <= 0 or exit_["close"] <= 0:
        return None
    return exit_["close"] / entry["open"] - 1.0


def settle_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    bars = load_bars(rows)
    settled: list[dict[str, Any]] = []
    skipped: Counter[str] = Counter()
    notional = float(CONFIG["unit_notional_usd"])
    for row in rows:
        ticker_bars = bars.get(row["ticker"])
        if not ticker_bars:
            skipped["missing_ticker_bars"] += 1
            continue
        entry_index = next_index_after(ticker_bars, str(row["event_date"]))
        if entry_index is None:
            skipped["missing_next_session"] += 1
            continue
        entry = ticker_bars[entry_index]
        outcome = {
            "event_id": row.get("event_id"),
            "event_date": row.get("event_date"),
            "published_at": row.get("published_at"),
            "ticker": row["ticker"],
            "relation_type": row.get("relation_type"),
            "relation_polarity": row.get("relation_polarity"),
            "target_relation_quality": row["target_relation_quality"],
            "magnitude_qualified": row["magnitude_qualified"],
            "evidence_text_hash": row.get("evidence_text_hash"),
            "entry_date": entry["date"],
            "entry_open": round(entry["open"], 4),
            "target_price": None,
            "unit_notional_usd": notional,
        }
        closed_any = False
        for horizon in CONFIG["horizons"]:
            h = int(horizon)
            exit_index = entry_index + h
            prefix = f"forward_{h}d"
            if exit_index >= len(ticker_bars):
                outcome[f"{prefix}_closed"] = False
                skipped[f"not_yet_{h}d_closed"] += 1
                continue
            exit_ = ticker_bars[exit_index]
            if entry["open"] <= 0 or exit_["close"] <= 0:
                skipped[f"bad_{h}d_price"] += 1
                outcome[f"{prefix}_closed"] = False
                continue
            stock_return = exit_["close"] / entry["open"] - 1.0
            spy_return = return_between(bars.get("SPY", []), entry["date"], exit_["date"])
            qqq_return = return_between(bars.get("QQQ", []), entry["date"], exit_["date"])
            pnl = notional * stock_return
            spy_pnl = notional * spy_return if spy_return is not None else None
            qqq_pnl = notional * qqq_return if qqq_return is not None else None
            outcome.update(
                {
                    f"{prefix}_closed": True,
                    f"{prefix}_exit_date": exit_["date"],
                    f"{prefix}_exit_close": round(exit_["close"], 4),
                    f"{prefix}_return_pct": round(stock_return, 6),
                    f"{prefix}_pnl_usd": round(pnl, 2),
                    f"{prefix}_spy_return_pct": round(spy_return, 6) if spy_return is not None else None,
                    f"{prefix}_qqq_return_pct": round(qqq_return, 6) if qqq_return is not None else None,
                    f"{prefix}_replacement_value_vs_spy_usd": round(pnl - spy_pnl, 2)
                    if spy_pnl is not None
                    else None,
                    f"{prefix}_replacement_value_vs_qqq_usd": round(pnl - qqq_pnl, 2)
                    if qqq_pnl is not None
                    else None,
                }
            )
            closed_any = True
        if closed_any:
            settled.append(outcome)
    return settled, {
        "warehouse_path": repo_rel(DEFAULT_WAREHOUSE_PATH),
        "loaded_tickers": sorted(bars),
        "input_rows": len(rows),
        "settled_rows_any_horizon": len(settled),
        "skipped_reasons": dict(sorted(skipped.items())),
        "date_range": {
            "event_start": min((str(row["event_date"]) for row in rows if row.get("event_date")), default=None),
            "event_end": max((str(row["event_date"]) for row in rows if row.get("event_date")), default=None),
            "entry_start": min((row["entry_date"] for row in settled if row.get("entry_date")), default=None),
            "entry_end": max((row["entry_date"] for row in settled if row.get("entry_date")), default=None),
        },
    }


def rows_closed(rows: list[dict[str, Any]], horizon: int) -> list[dict[str, Any]]:
    return [row for row in rows if row.get(f"forward_{horizon}d_closed")]


def summarize(rows: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    prefix = f"forward_{horizon}d"
    closed = rows_closed(rows, horizon)
    returns = [float(row[f"{prefix}_return_pct"]) for row in closed]
    pnls = [float(row[f"{prefix}_pnl_usd"]) for row in closed]
    spy = [
        float(row[f"{prefix}_replacement_value_vs_spy_usd"])
        for row in closed
        if as_float(row.get(f"{prefix}_replacement_value_vs_spy_usd")) is not None
    ]
    qqq = [
        float(row[f"{prefix}_replacement_value_vs_qqq_usd"])
        for row in closed
        if as_float(row.get(f"{prefix}_replacement_value_vs_qqq_usd")) is not None
    ]
    return {
        "n": len(closed),
        "mean_return_pct": round(mean(returns), 6) if returns else None,
        "median_return_pct": round(median_or_none(returns), 6) if returns else None,
        "win_rate": round(sum(1 for value in returns if value > 0) / len(returns), 6) if returns else None,
        "mean_pnl_usd": round(mean(pnls), 2) if pnls else None,
        "total_pnl_usd": round(sum(pnls), 2) if pnls else 0.0,
        "mean_replacement_value_vs_spy_usd": round(mean(spy), 2) if spy else None,
        "total_replacement_value_vs_spy_usd": round(sum(spy), 2) if spy else 0.0,
        "mean_replacement_value_vs_qqq_usd": round(mean(qqq), 2) if qqq else None,
        "total_replacement_value_vs_qqq_usd": round(sum(qqq), 2) if qqq else 0.0,
    }


def single_ticker_share(rows: list[dict[str, Any]]) -> float | None:
    if not rows:
        return None
    counts = Counter(str(row["ticker"]) for row in rows)
    return round(max(counts.values()) / len(rows), 6)


def mean_value(summary: Mapping[str, Any], key: str) -> float | None:
    return as_float(summary.get(key))


def analyze(rows: list[dict[str, Any]]) -> dict[str, Any]:
    targets = [row for row in rows if row["target_relation_quality"]]
    controls = [row for row in rows if not row["target_relation_quality"]]
    magnitude_targets = [row for row in targets if row["magnitude_qualified"]]
    target_summary = {str(h): summarize(targets, int(h)) for h in CONFIG["horizons"]}
    control_summary = {str(h): summarize(controls, int(h)) for h in CONFIG["horizons"]}
    magnitude_target_summary = {
        str(h): summarize(magnitude_targets, int(h)) for h in CONFIG["horizons"]
    }
    relation_summary: dict[str, dict[str, Any]] = {}
    for relation in sorted({str(row.get("relation_type")) for row in rows}):
        relation_rows = [row for row in rows if row.get("relation_type") == relation]
        relation_summary[relation] = {str(h): summarize(relation_rows, int(h)) for h in CONFIG["horizons"]}

    target10 = rows_closed(targets, 10)
    control10 = rows_closed(controls, 10)
    target10_summary = target_summary["10"]
    control10_summary = control_summary["10"]
    target_mean = mean_value(target10_summary, "mean_return_pct")
    control_mean = mean_value(control10_summary, "mean_return_pct")
    target_edge = target_mean - control_mean if target_mean is not None and control_mean is not None else None
    checks = {
        "closed_10d_target_rows": len(target10),
        "closed_10d_control_rows": len(control10),
        "target_event_dates": len({row["event_date"] for row in target10}),
        "target_ticker_count": len({row["ticker"] for row in target10}),
        "target_single_ticker_share": single_ticker_share(target10),
        "mean_10d_return_edge_vs_control": round(target_edge, 6) if target_edge is not None else None,
        "target_mean_10d_replacement_vs_spy_usd": target10_summary.get(
            "mean_replacement_value_vs_spy_usd"
        ),
        "target_mean_10d_replacement_vs_qqq_usd": target10_summary.get(
            "mean_replacement_value_vs_qqq_usd"
        ),
        "magnitude_qualified_closed_10d_target_rows": len(rows_closed(magnitude_targets, 10)),
        "canonical_three_window_coverage": False,
    }
    failed = []
    if checks["closed_10d_target_rows"] < CONFIG["min_closed_10d_target_rows"]:
        failed.append("target_closed_10d_sample_too_small")
    if checks["target_event_dates"] < CONFIG["min_target_event_dates"]:
        failed.append("target_event_date_breadth_too_small")
    if target_edge is None or target_edge < CONFIG["min_mean_10d_return_edge_vs_control"]:
        failed.append("mean_10d_return_edge_vs_control_too_low")
    if (
        as_float(checks["target_mean_10d_replacement_vs_spy_usd"]) is None
        or float(checks["target_mean_10d_replacement_vs_spy_usd"])
        <= CONFIG["min_mean_10d_replacement_vs_spy_usd"]
    ):
        failed.append("target_mean_10d_spy_replacement_not_positive")
    if (
        as_float(checks["target_mean_10d_replacement_vs_qqq_usd"]) is None
        or float(checks["target_mean_10d_replacement_vs_qqq_usd"])
        <= CONFIG["min_mean_10d_replacement_vs_qqq_usd"]
    ):
        failed.append("target_mean_10d_qqq_replacement_not_positive")
    if (
        as_float(checks["target_single_ticker_share"]) is None
        or float(checks["target_single_ticker_share"]) > CONFIG["max_single_ticker_target_share"]
    ):
        failed.append("target_single_ticker_concentration_too_high")
    if not checks["canonical_three_window_coverage"]:
        failed.append("coverage_not_canonical_windows")
    observed_positive = bool(
        not set(failed).difference({"coverage_not_canonical_windows"})
        and "coverage_not_canonical_windows" in failed
    )
    return {
        "observed_only_positive_lead": observed_positive,
        "failed_reasons": failed,
        "checks": checks,
        "target_summary": target_summary,
        "control_summary": control_summary,
        "magnitude_target_summary": magnitude_target_summary,
        "relation_summary": relation_summary,
        "sample_target_rows": target10[:12],
    }


def calibration(prediction: dict[str, Any], observed_positive: bool, failed: list[str]) -> dict[str, Any]:
    probability = as_float(prediction.get("success_probability")) or 0.0
    actual = 1.0 if observed_positive else 0.0
    mode_map = {
        "no_structured_relation_edge": {
            "mean_10d_return_edge_vs_control_too_low",
            "target_mean_10d_spy_replacement_not_positive",
            "target_mean_10d_qqq_replacement_not_positive",
        },
        "coverage_not_canonical_windows": {"coverage_not_canonical_windows"},
        "current_forward_rows_too_thin": {
            "target_closed_10d_sample_too_small",
            "target_event_date_breadth_too_small",
        },
        "single_ticker_concentration": {"target_single_ticker_concentration_too_high"},
    }
    predicted_modes = list(prediction.get("main_failure_modes") or [])
    hit = [mode for mode in predicted_modes if set(failed) & mode_map.get(mode, set())]
    return {
        "predicted_success_probability": round(probability, 4),
        "actual_success": bool(observed_positive),
        "brier_score": round((probability - actual) ** 2, 6),
        "predicted_failure_modes": predicted_modes,
        "failed_reasons": failed,
        "predicted_failure_modes_hit": hit,
    }


def build_payload() -> dict[str, Any]:
    prediction = load_ticket_prediction()
    baseline = load_baseline_metrics()
    source_rows, source_audit = load_event_rows()
    settled_rows, settlement_audit = settle_rows(source_rows)
    analysis = analyze(settled_rows)
    observed_positive = bool(analysis["observed_only_positive_lead"])
    failed = list(analysis["failed_reasons"])
    decision = (
        "observed_only_positive_structured_daily_news_forward_lead_not_promoted"
        if observed_positive
        else "rejected_no_structured_daily_news_forward_value_edge"
    )
    status = "observed_only_positive_lead" if observed_positive else "rejected"
    why = (
        "The fixed structured relation-quality cohort separated current-forward "
        "replacement value, but the archive is 2026-forward only and does not span "
        "the canonical fixed windows, so no strategy, helper, or prompt behavior "
        "was promoted."
        if observed_positive
        else "The fixed structured relation-quality cohort did not clear the "
        "predeclared closed 10d edge and replacement-value checks versus other "
        "structured event rows; the ledger remains attribution evidence only."
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "status": status,
        "lane": "alpha_search",
        "owner": OWNER,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": observed_positive,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "observed_only_forward_attribution",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "prediction": prediction,
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": "experiment.py new passed with no strong near-neighbor and no saturated-source block.",
                "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
                "boundary": "This uses exp-20260630-004 structured event rows and does not retry exp-20260630-002 keyword buckets.",
            },
            "3_single_policy_bundle": (
                "One fixed structured relation-quality cohort: financial growth, "
                "guidance/rating upgrade, product/approval catalyst, and "
                "customer/partnership events; capital-return and negative "
                "relations are controls."
            ),
            "4_success_failure_standard": CONFIG,
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "structured_ledger": repo_rel(STRUCTURED_LEDGER),
            "warehouse_path": repo_rel(DEFAULT_WAREHOUSE_PATH),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "config": CONFIG,
        },
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_metrics": baseline,
            "note": "Observed-only attribution; before and after strategy metrics are identical.",
        },
        "gate2": {
            "dependencies_validated": bool(settled_rows),
            "fields_checked": [
                "event_date",
                "ticker",
                "relation_type",
                "relation_polarity",
                "magnitude.has_numeric_magnitude",
                "entry_date",
                "target_price",
                "forward_5d_return_pct",
                "forward_10d_return_pct",
                "forward_10d_replacement_value_vs_spy_usd",
                "forward_10d_replacement_value_vs_qqq_usd",
            ],
            "entry_date_present": all(bool(row.get("entry_date")) for row in settled_rows),
            "target_price_present_count": sum(1 for row in settled_rows if row.get("target_price")),
            "target_price_relevance": "Not applicable; no target exit is scheduled in this observed-only attribution.",
            "source_audit": source_audit,
            "settlement_audit": settlement_audit,
        },
        "gate3": {
            "filter_added": False,
            "signals_generated": source_audit["deduped_rows"],
            "signals_survived": len(rows_closed(settled_rows, 10)),
            "survival_rate": round(len(rows_closed(settled_rows, 10)) / source_audit["deduped_rows"], 4)
            if source_audit["deduped_rows"]
            else None,
            "target_candidate_rows_raw": source_audit["target_rows_raw"],
            "target_candidate_rows_settled_10d": analysis["checks"]["closed_10d_target_rows"],
            "note": "No executable filter was added; this measures a fixed observed-only cohort.",
        },
        "gate4": {
            "observed_only_lead": observed_positive,
            "failed_reasons": failed,
            "checks": analysis["checks"],
            "decision": decision,
            "strategy_rerun_required": False,
            "before_after_strategy_delta": {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "max_drawdown_pct": 0.0,
            },
            "lead_limitations": [
                "Daily news archive coverage starts in 2026 and does not cover all canonical fixed windows.",
                "No shared helper, daily paper sleeve, prompt rule, or live order behavior was promoted.",
                "The structured relation ledger is deterministic and not yet a live LLM semantic scorer.",
            ],
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "survival_rate_delta": 0.0,
            "structured_ledger_rows": source_audit["deduped_rows"],
            "target_relation_rows": source_audit["target_rows_raw"],
            "magnitude_rows": source_audit["magnitude_rows_raw"],
            "settled_10d_rows": len(rows_closed(settled_rows, 10)),
        },
        "attribution": {
            "source_audit": source_audit,
            "settlement_audit": settlement_audit,
            "analysis": analysis,
        },
        "production_impact": {
            "trade_enabled": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "entry_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_rules_changed": False,
            "llm_prompt_changed": False,
            "news_archives_changed": False,
            "shared_helper_promoted": False,
            "daily_snapshot_exposed": False,
            "live_ready": False,
        },
        "calibration": calibration(prediction, observed_positive, failed),
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retry by sweeping relation lists, polarity labels, "
                "magnitude requirements, hold days, top-N, notional, or response "
                "curves on the same structured news rows. A valid retry needs "
                "materially more closed rows, PIT LLM labels persisted with this "
                "schema, or canonical-window daily-news replay coverage."
            ),
            "new_evidence_required": (
                "More closed cash/SPY/QQQ replacement-value rows for structured "
                "events, a true PIT LLM scorer writing the same evidence-span "
                "schema, or historical daily-news coverage spanning the canonical "
                "fixed windows."
            ),
        },
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(SETTLED_LEDGER),
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
        "related_files": [
            RUNNER,
            repo_rel(STRUCTURED_LEDGER),
            repo_rel(SETTLED_LEDGER),
            repo_rel(BASELINE_RESULT),
            "experiments/logs/exp-20260630-002.json",
            "experiments/logs/exp-20260630-004.json",
        ],
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no JS tooling invoked.",
        },
        "_settled_rows_for_write": settled_rows,
    }


def compact_log(payload: dict[str, Any]) -> dict[str, Any]:
    analysis = payload["attribution"]["analysis"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "lane": payload["lane"],
        "owner": OWNER,
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": payload["observed_only_lead"],
        "hypothesis": payload["hypothesis"],
        "change_type": CHANGE_TYPE,
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "prediction": payload["prediction"],
        "pre_run_questions": payload["pre_run_questions"],
        "parameters": payload["parameters"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "attribution": {
            "target_summary": analysis["target_summary"],
            "control_summary": analysis["control_summary"],
            "magnitude_target_summary": analysis["magnitude_target_summary"],
            "relation_summary": analysis["relation_summary"],
            "checks": analysis["checks"],
        },
        "production_impact": payload["production_impact"],
        "calibration": payload["calibration"],
        "post_run_reflection": payload["post_run_reflection"],
        "changed_files": payload["changed_files"],
        "reproduction_commands": payload["reproduction_commands"],
        "related_files": payload["related_files"],
        "artifact": repo_rel(OUT_JSON),
        "settled_ledger": repo_rel(SETTLED_LEDGER),
        "log": repo_rel(LOG_JSON),
        "anti_js": payload["anti_js"],
    }


def build_card(payload: dict[str, Any]) -> str:
    analysis = payload["attribution"]["analysis"]
    target10 = analysis["target_summary"]["10"]
    control10 = analysis["control_summary"]["10"]
    mag10 = analysis["magnitude_target_summary"]["10"]
    checks = analysis["checks"]
    rows = [
        "| Cohort | 10d rows | Mean return | Mean PnL | Mean vs SPY | Mean vs QQQ | Win rate |",
        "|---|---:|---:|---:|---:|---:|---:|",
        "| target_relation_quality | {n} | {ret} | {pnl} | {spy} | {qqq} | {win} |".format(
            n=target10["n"],
            ret=pct(target10["mean_return_pct"]),
            pnl=money(target10["mean_pnl_usd"]),
            spy=money(target10["mean_replacement_value_vs_spy_usd"]),
            qqq=money(target10["mean_replacement_value_vs_qqq_usd"]),
            win=pct(target10["win_rate"]),
        ),
        "| non_target_structured_events | {n} | {ret} | {pnl} | {spy} | {qqq} | {win} |".format(
            n=control10["n"],
            ret=pct(control10["mean_return_pct"]),
            pnl=money(control10["mean_pnl_usd"]),
            spy=money(control10["mean_replacement_value_vs_spy_usd"]),
            qqq=money(control10["mean_replacement_value_vs_qqq_usd"]),
            win=pct(control10["win_rate"]),
        ),
        "| magnitude_qualified_target_attr | {n} | {ret} | {pnl} | {spy} | {qqq} | {win} |".format(
            n=mag10["n"],
            ret=pct(mag10["mean_return_pct"]),
            pnl=money(mag10["mean_pnl_usd"]),
            spy=money(mag10["mean_replacement_value_vs_spy_usd"]),
            qqq=money(mag10["mean_replacement_value_vs_qqq_usd"]),
            win=pct(mag10["win_rate"]),
        ),
    ]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: structured daily-news event forward value",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Production behavior changed: no",
            "- Accepted alpha: no",
            "",
            "## 10d Result",
            "",
            *rows,
            "",
            f"- Mean 10d return edge vs control: `{pct(checks['mean_10d_return_edge_vs_control'])}`",
            f"- Target dates: `{checks['target_event_dates']}`",
            f"- Target single-ticker share: `{pct(checks['target_single_ticker_share'])}`",
            f"- Failed reasons: `{', '.join(payload['gate4']['failed_reasons']) or 'none'}`",
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
        SETTLED_LEDGER,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "settled_ledger": repo_rel(SETTLED_LEDGER),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "manifest": repo_rel(MANIFEST_JSON),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {repo_rel(path): {"exists": path.exists(), "sha256": sha256_file(path)} for path in files},
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    settled_rows = payload.pop("_settled_rows_for_write")
    write_jsonl(SETTLED_LEDGER, settled_rows)
    write_json(OUT_JSON, payload)
    log_row = compact_log(payload)
    save_experiment_log_entry(log_row, allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    result = {
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": payload["observed_only_lead"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "settled_ledger": repo_rel(SETTLED_LEDGER),
        "log": repo_rel(LOG_JSON),
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result=result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "change_type": CHANGE_TYPE,
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "settled_ledger": repo_rel(SETTLED_LEDGER),
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
            "changed_files": payload["changed_files"],
            "reproduction_commands": payload["reproduction_commands"],
            "related_files": payload["related_files"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    analysis = payload["attribution"]["analysis"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "checks": analysis["checks"],
                "target_10d": analysis["target_summary"]["10"],
                "control_10d": analysis["control_summary"]["10"],
                "magnitude_target_10d": analysis["magnitude_target_summary"]["10"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
