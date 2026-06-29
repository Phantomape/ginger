"""exp-20260628-013: accepted-core style factor tape attribution.

Read-only alpha attribution over the current accepted core stack. The tested
field is point-in-time factor ETF style leadership at entry, joined to already
accepted trades. This runner does not alter candidate pools, entries, exits,
ranking, sizing, or order behavior.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
import sys
from collections import OrderedDict
from datetime import date, datetime, timezone
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


EXPERIMENT_ID = "exp-20260628-013"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "accepted_core_style_factor_tape_attribution"
RUNNER = f"quant/experiments/exp_20260628_013_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

CHANGED_VARIABLE = "accepted_core_entry_style_factor_tape_loss_tail_attribution_v1"
TRIAL_FAMILY = "accepted_core_style_factor_tape_risk_attribution"
TRIAL_VARIANT_ID = "accepted_stack_factor_etf_style_tape_v1"
MECHANISM_FAMILY = "production_visible_factor_etf_style_tape_risk_attribution"
CHANGE_TYPE = "observed_only_attribution"
IMPLEMENTATION_MODE = "observed_only_attribution"
NEW_EVIDENCE_TYPE = "new_gate_shape_pit_factor_etf_style_tape_attribution"
NEW_EVIDENCE_AXIS = (
    "New gate shape: PIT factor ETF style tape joined only to already accepted "
    "core trades for observed-only loss-tail attribution; not a factor-residual "
    "candidate pool, allocator source, cross-sectional ranking, or threshold retune."
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
            REPO_ROOT / "data" / "experiments" / "exp-20260602-003" / "late_strong_after.json",
        ),
        (
            "mid_weak",
            REPO_ROOT / "data" / "experiments" / "exp-20260602-003" / "mid_weak_after.json",
        ),
        (
            "old_thin",
            REPO_ROOT / "data" / "experiments" / "exp-20260602-003" / "old_thin_after.json",
        ),
    ]
)
FACTOR_CACHE_JSON = REPO_ROOT / "data" / "experiments" / "exp-20260620-027" / "factor_etf_daily.json"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260628_013_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Accepted core trades entered when defensive factor ETF leadership dominates "
    "momentum factor leadership carry worse loss-tail and lower PnL than risk-on "
    "style tape entries, giving a production-visible risk-allocation candidate "
    "without changing entries, exits, ranking, sizing, or orders."
)
CAUSAL_COMPONENTS = [
    "canonical accepted-stack trade replay",
    "PIT factor ETF close cache",
    "fixed risk-on/risk-off style tape buckets",
    "loss-tail attribution",
    "no strategy behavior change",
]
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260620-027",
    "exp-20260627-003",
    "exp-20260628-006",
]

FACTOR_TICKERS = ["SPY", "MTUM", "USMV", "QUAL", "SIZE", "VLUE"]
LOOKBACK_DAYS = 20
STYLE_SPREAD_THRESHOLD = 0.015
LOSS_TAIL_PNL_PCT = -0.02
MIN_JOINED_ROWS = 50
MIN_DEFENSIVE_ROWS = 10
MIN_RISK_ON_ROWS = 10
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


def load_factor_closes() -> tuple[dict[str, list[tuple[date, float]]], dict[str, Any]]:
    payload = read_json(FACTOR_CACHE_JSON, {})
    closes = payload.get("closes") if isinstance(payload, dict) else None
    out: dict[str, list[tuple[date, float]]] = {}
    audit: dict[str, Any] = {
        "factor_cache": repo_rel(FACTOR_CACHE_JSON),
        "tickers_required": FACTOR_TICKERS,
        "tickers_present": {},
    }
    if not isinstance(closes, dict):
        return out, audit
    for ticker in FACTOR_TICKERS:
        series = closes.get(ticker)
        rows: list[tuple[date, float]] = []
        if isinstance(series, dict):
            for day_text, close_value in series.items():
                day = parse_day(day_text)
                close = as_float(close_value)
                if day is not None and close is not None and close > 0:
                    rows.append((day, close))
        rows.sort(key=lambda item: item[0])
        out[ticker] = rows
        audit["tickers_present"][ticker] = {
            "present": bool(rows),
            "rows": len(rows),
            "first_date": rows[0][0].isoformat() if rows else None,
            "last_date": rows[-1][0].isoformat() if rows else None,
        }
    return out, audit


def trailing_return(
    series: list[tuple[date, float]], entry_day: date | None, lookback_days: int
) -> float | None:
    if entry_day is None:
        return None
    prior = [(day, close) for day, close in series if day < entry_day]
    if len(prior) < lookback_days + 1:
        return None
    start = prior[-(lookback_days + 1)][1]
    end = prior[-1][1]
    if start <= 0:
        return None
    return end / start - 1.0


def style_metrics(
    closes: dict[str, list[tuple[date, float]]], entry_day: date | None
) -> dict[str, Any]:
    returns = {
        ticker: trailing_return(closes.get(ticker, []), entry_day, LOOKBACK_DAYS)
        for ticker in FACTOR_TICKERS
    }
    mtum = returns.get("MTUM")
    usmv = returns.get("USMV")
    spy = returns.get("SPY")
    mtum_minus_usmv = mtum - usmv if mtum is not None and usmv is not None else None
    usmv_minus_mtum = usmv - mtum if mtum is not None and usmv is not None else None
    mtum_excess_spy = mtum - spy if mtum is not None and spy is not None else None
    usmv_excess_spy = usmv - spy if usmv is not None and spy is not None else None
    bucket = "unknown"
    if mtum_minus_usmv is not None and mtum_minus_usmv >= STYLE_SPREAD_THRESHOLD:
        bucket = "risk_on_momentum"
    elif usmv_minus_mtum is not None and usmv_minus_mtum >= STYLE_SPREAD_THRESHOLD:
        bucket = "defensive_leadership"
    elif mtum_minus_usmv is not None:
        bucket = "balanced_or_mixed"
    return {
        "factor_returns_20d": {ticker: round_float(value, 8) for ticker, value in returns.items()},
        "mtum_minus_usmv_20d": round_float(mtum_minus_usmv, 8),
        "usmv_minus_mtum_20d": round_float(usmv_minus_mtum, 8),
        "mtum_excess_spy_20d": round_float(mtum_excess_spy, 8),
        "usmv_excess_spy_20d": round_float(usmv_excess_spy, 8),
        "style_bucket": bucket,
        "style_tape_joined": bucket != "unknown",
    }


def enrich_trade(
    label: str, trade: dict[str, Any], closes: dict[str, list[tuple[date, float]]]
) -> dict[str, Any]:
    ticker = str(trade.get("ticker") or "").upper()
    entry_day = parse_day(trade.get("entry_date"))
    pnl = as_float(trade.get("pnl")) or 0.0
    pnl_pct = as_float(trade.get("pnl_pct_net")) or 0.0
    entry_price = as_float(trade.get("entry_price"))
    shares = as_float(trade.get("shares"))
    entry_notional = entry_price * shares if entry_price is not None and shares is not None else None
    metrics = style_metrics(closes, entry_day)
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
        **metrics,
    }


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pnls = [float(row["pnl"]) for row in rows if row.get("pnl") is not None]
    pnl_pcts = [
        float(row["pnl_pct_net"]) for row in rows if row.get("pnl_pct_net") is not None
    ]
    mtum_minus_usmv = [
        float(row["mtum_minus_usmv_20d"])
        for row in rows
        if row.get("mtum_minus_usmv_20d") is not None
    ]
    return {
        "n": len(rows),
        "joined_n": sum(1 for row in rows if row.get("style_tape_joined")),
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
        "avg_mtum_minus_usmv_20d": mean(mtum_minus_usmv),
        "median_mtum_minus_usmv_20d": median(mtum_minus_usmv),
    }


def summarize_by_bucket(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for bucket in (
        "defensive_leadership",
        "balanced_or_mixed",
        "risk_on_momentum",
        "unknown",
    ):
        bucket_rows = [row for row in rows if row.get("style_bucket") == bucket]
        if bucket_rows or bucket != "unknown":
            out[bucket] = summarize_rows(bucket_rows)
    return out


def compare_defensive_risk_on(summary: dict[str, Any]) -> dict[str, Any]:
    defensive = summary.get("defensive_leadership") or {}
    risk_on = summary.get("risk_on_momentum") or {}
    if not defensive.get("n") or not risk_on.get("n"):
        return {"available": False}
    return {
        "available": True,
        "defensive_minus_risk_on_avg_pnl": round_float(
            (defensive.get("avg_pnl") or 0.0) - (risk_on.get("avg_pnl") or 0.0),
            6,
        ),
        "defensive_minus_risk_on_median_pnl": round_float(
            (defensive.get("median_pnl") or 0.0) - (risk_on.get("median_pnl") or 0.0),
            6,
        ),
        "defensive_minus_risk_on_win_rate": round_float(
            (defensive.get("win_rate") or 0.0) - (risk_on.get("win_rate") or 0.0),
            6,
        ),
        "defensive_minus_risk_on_loss_tail_rate": round_float(
            (defensive.get("loss_tail_rate") or 0.0)
            - (risk_on.get("loss_tail_rate") or 0.0),
            6,
        ),
        "defensive_rows": defensive.get("n"),
        "risk_on_rows": risk_on.get("n"),
    }


def load_baseline_summary() -> dict[str, Any]:
    baseline = read_json(STANDARD_WINDOW_RESULT, {})
    if not isinstance(baseline, dict):
        return {"standard_window_result": repo_rel(STANDARD_WINDOW_RESULT), "loaded": False}
    windows = baseline.get("windows") or baseline.get("by_window") or {}
    return {
        "standard_window_result": repo_rel(STANDARD_WINDOW_RESULT),
        "loaded": True,
        "total_expected_value_score": baseline.get("total_expected_value_score")
        or baseline.get("expected_value_score_sum"),
        "total_pnl": baseline.get("total_pnl"),
        "windows": windows,
    }


def load_rows(
    closes: dict[str, list[tuple[date, float]]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    source_audit: dict[str, Any] = {}
    for label, path in WINDOW_FILES.items():
        payload = read_json(path, {})
        trades = payload.get("trades") if isinstance(payload, dict) else None
        if not isinstance(trades, list):
            trades = []
        window_rows = [enrich_trade(label, trade, closes) for trade in trades]
        rows.extend(window_rows)
        source_audit[label] = {
            "path": repo_rel(path),
            "trade_rows": len(window_rows),
            "rows_with_entry_date": sum(1 for row in window_rows if row.get("entry_date")),
            "rows_with_target_price_reconstructed": sum(
                1 for row in window_rows if row.get("target_price_reconstructed") is not None
            ),
            "rows_with_style_tape": sum(1 for row in window_rows if row.get("style_tape_joined")),
            "style_bucket_counts": {
                bucket: sum(1 for row in window_rows if row.get("style_bucket") == bucket)
                for bucket in (
                    "defensive_leadership",
                    "balanced_or_mixed",
                    "risk_on_momentum",
                    "unknown",
                )
            },
        }
    return rows, source_audit


def build_attribution(
    rows: list[dict[str, Any]], source_audit: dict[str, Any], factor_audit: dict[str, Any]
) -> dict[str, Any]:
    joined_rows = [row for row in rows if row.get("style_tape_joined")]
    by_window: dict[str, Any] = {}
    for label in WINDOW_FILES:
        window_rows = [row for row in joined_rows if row.get("window") == label]
        buckets = summarize_by_bucket(window_rows)
        by_window[label] = {
            "all": summarize_rows(window_rows),
            "buckets": buckets,
            "defensive_vs_risk_on": compare_defensive_risk_on(buckets),
        }
    buckets = summarize_by_bucket(joined_rows)
    return {
        "parameters": {
            "factor_tickers": FACTOR_TICKERS,
            "lookback_days": LOOKBACK_DAYS,
            "style_spread_threshold": STYLE_SPREAD_THRESHOLD,
            "loss_tail_pnl_pct": LOSS_TAIL_PNL_PCT,
            "bucket_rule": (
                "risk_on_momentum if MTUM-USMV 20d >= threshold; defensive_leadership "
                "if USMV-MTUM 20d >= threshold; otherwise balanced_or_mixed."
            ),
        },
        "pooled": {
            "all": summarize_rows(joined_rows),
            "buckets": buckets,
            "defensive_vs_risk_on": compare_defensive_risk_on(buckets),
        },
        "by_window": by_window,
        "rows": rows,
        "source_audit": source_audit,
        "factor_audit": factor_audit,
    }


def evaluate_gate4(attribution: dict[str, Any]) -> dict[str, Any]:
    pooled = attribution["pooled"]
    buckets = pooled["buckets"]
    all_summary = pooled["all"]
    defensive = buckets.get("defensive_leadership") or {}
    risk_on = buckets.get("risk_on_momentum") or {}
    comparison = pooled["defensive_vs_risk_on"]
    supporting = []
    for label, row in attribution["by_window"].items():
        comp = row["defensive_vs_risk_on"]
        if (
            comp.get("available")
            and (comp.get("defensive_minus_risk_on_avg_pnl") or 0.0) < 0
            and (comp.get("defensive_minus_risk_on_win_rate") or 0.0) < 0
            and (comp.get("defensive_minus_risk_on_loss_tail_rate") or 0.0) > 0
        ):
            supporting.append(label)

    failures: list[str] = []
    if (all_summary.get("joined_n") or 0) < MIN_JOINED_ROWS:
        failures.append("joined_sample_too_small")
    if (defensive.get("n") or 0) < MIN_DEFENSIVE_ROWS:
        failures.append("defensive_bucket_sample_too_small")
    if (risk_on.get("n") or 0) < MIN_RISK_ON_ROWS:
        failures.append("risk_on_bucket_sample_too_small")
    if not comparison.get("available"):
        failures.append("defensive_risk_on_comparison_unavailable")
    else:
        if (comparison.get("defensive_minus_risk_on_avg_pnl") or 0.0) >= 0:
            failures.append("defensive_avg_pnl_not_worse")
        if (comparison.get("defensive_minus_risk_on_win_rate") or 0.0) >= 0:
            failures.append("defensive_win_rate_not_worse")
        if (comparison.get("defensive_minus_risk_on_loss_tail_rate") or 0.0) <= 0:
            failures.append("defensive_loss_tail_not_worse")
    if len(supporting) < MIN_SUPPORTING_WINDOWS:
        failures.append("insufficient_window_support")

    observed_only_lead = not failures
    return {
        "passed": observed_only_lead,
        "observed_only_lead": observed_only_lead,
        "decision": (
            "observed_only_positive_style_factor_tape_loss_tail_edge"
            if observed_only_lead
            else "rejected_no_style_factor_tape_loss_tail_edge"
        ),
        "acceptance_rule": (
            "Observed-only lead only if joined sample >=50, defensive bucket >=10, "
            "risk-on bucket >=10, pooled defensive bucket has lower average PnL, "
            "lower win rate, and higher 2pct loss-tail rate than risk-on, with "
            "at least two standard windows supporting the same direction. No "
            "strategy acceptance is possible in this run."
        ),
        "failed_reasons": failures,
        "supporting_windows": supporting,
        "pooled_defensive_vs_risk_on": comparison,
        "minimums": {
            "min_joined_rows": MIN_JOINED_ROWS,
            "min_defensive_rows": MIN_DEFENSIVE_ROWS,
            "min_risk_on_rows": MIN_RISK_ON_ROWS,
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
            "PIT style factor tape did not produce a robust defensive-vs-risk-on "
            "loss-tail separation on the accepted stack."
            if not gate4.get("observed_only_lead")
            else "PIT style factor tape separated accepted-stack loss tail and needs prospective logging."
        ),
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") or {}
    closes, factor_audit = load_factor_closes()
    rows, source_audit = load_rows(closes)
    attribution = build_attribution(rows, source_audit, factor_audit)
    gate4 = evaluate_gate4(attribution)
    baseline = load_baseline_summary()
    status = "observed_only" if gate4["observed_only_lead"] else "rejected"
    why = (
        "The fixed PIT style tape split did not satisfy the loss-tail rule on "
        "accepted core trades: defensive leadership failed at least one pooled "
        "direction check, bucket-size check, or window-support check. This should "
        "not be retuned on the same frozen accepted-stack windows."
        if not gate4["observed_only_lead"]
        else (
            "Defensive factor leadership separated lower PnL and heavier loss tail "
            "from risk-on momentum leadership across the fixed accepted-stack "
            "checks. This remains observed-only and needs default-off prospective "
            "logging before any risk policy use."
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
                    "experiment.py new blocked the initial reservation as an "
                    "allocator_source/ohlcv_momentum near-neighbor; override was "
                    "used only for a new gate shape that joins PIT factor ETF "
                    "style tape to already accepted trades for read-only attribution."
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
                for row in source_audit.values()
            )
            and all(
                item.get("present")
                for item in factor_audit.get("tickers_present", {}).values()
            )
            and (attribution["pooled"]["all"].get("joined_n") or 0) > 0,
            "dependency_fields_checked": [
                "entry_date",
                "entry_price",
                "stop_price",
                "target_mult_used",
                "target_price_reconstructed",
                "pnl",
                "pnl_pct_net",
                "SPY_20d_return",
                "MTUM_20d_return",
                "USMV_20d_return",
                "MTUM_minus_USMV_20d",
            ],
            "target_price_note": (
                "Closed trade rows omit original target_price; runner reconstructs "
                "entry_price + (entry_price - stop_price) * target_mult_used and "
                "does not schedule executable orders."
            ),
            "source_audit": source_audit,
            "factor_audit": factor_audit,
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
            "Do not retune style spread thresholds, ETF list, lookback length, or "
            "notional response curves on the same accepted-stack windows. A retry "
            "needs prospectively closed forward rows with a shared style-tape logger "
            "or a materially different source beyond ETF style tape."
        ),
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not rerun this accepted-stack style factor attribution by "
                "changing MTUM/USMV spread cuts, adding adjacent factor ETFs, "
                "changing lookback days, or converting the same field into a "
                "risk-scaling response curve."
            ),
            "new_evidence_required": (
                "Prospective forward rows tagged by a shared default-off style "
                "tape logger, or an independent source such as options/flows that "
                "is not merely another ETF-style threshold."
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
            repo_rel(FACTOR_CACHE_JSON),
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
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {
            "strategy_behavior_changed": False,
            "threshold_scan": False,
            "uses_future_factor_closes": False,
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
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "single_causal_variable",
        "changed_variable",
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
            "defensive_vs_risk_on": payload["attribution"]["pooled"][
                "defensive_vs_risk_on"
            ],
        },
        "by_window": payload["attribution"]["by_window"],
        "source_audit": payload["attribution"]["source_audit"],
        "factor_audit": payload["attribution"]["factor_audit"],
    }
    return row


def build_card(payload: dict[str, Any]) -> str:
    pooled = payload["attribution"]["pooled"]
    gate4 = payload["gate4"]
    comp = pooled["defensive_vs_risk_on"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Accepted-Core Style Factor Tape Attribution",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Status: `{payload['status']}`",
            f"- Observed-only lead: `{payload['observed_only_lead']}`",
            f"- Joined rows: `{pooled['all'].get('joined_n')}`",
            f"- Defensive rows: `{pooled['buckets']['defensive_leadership'].get('n')}`",
            f"- Risk-on rows: `{pooled['buckets']['risk_on_momentum'].get('n')}`",
            f"- Defensive minus risk-on avg PnL: `{comp.get('defensive_minus_risk_on_avg_pnl')}`",
            f"- Defensive minus risk-on win rate: `{comp.get('defensive_minus_risk_on_win_rate')}`",
            f"- Defensive minus risk-on loss-tail rate: `{comp.get('defensive_minus_risk_on_loss_tail_rate')}`",
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
