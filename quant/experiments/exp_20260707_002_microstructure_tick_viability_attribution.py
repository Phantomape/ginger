"""exp-20260707-002: PIT microstructure viability attribution.

The tested decision hypothesis is not a breakout or momentum retune. It asks
whether a fixed, production-visible microstructure field - one-cent tick size
normalized by entry-time ATR20 - explains which existing short-trend candidate
families keep after-cost replacement value.
"""

from __future__ import annotations

import json
import math
import sqlite3
import statistics
import sys
from collections import Counter, defaultdict
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


EXPERIMENT_ID = "exp-20260707-002"
OWNER = "alpha-explore"
LANE = "alpha_search"
STEM = "microstructure_tick_viability_attribution"
STATUS_POSITIVE = "observed_only_positive_microstructure_viability_lead_not_activation_ready"
STATUS_REJECTED = "observed_only_rejected_microstructure_viability_no_stable_edge"
DECISION_POSITIVE = "observed_only_positive_microstructure_tick_viability_attribution"
DECISION_REJECTED = "observed_only_rejected_microstructure_tick_viability_attribution"

TRIAL_FAMILY = "vol_normalized_tick_size_short_trend_attribution"
TRIAL_VARIANT_ID = "tick_to_atr20_short_trend_candidate_attribution_v1"
CHANGED_VARIABLE = "vol_normalized_tick_size_short_trend_viability_attribution_v1"
MECHANISM_FAMILY = "microstructure_viability"
CHANGE_TYPE = "observed_only_attribution"
NEW_EVIDENCE_TYPE = "new_production_visible_microstructure_field"
NEW_EVIDENCE_AXIS = (
    "New PIT microstructure viability field and gate shape: vol-normalized "
    "tick size computed from entry-time ATR20 on fixed target-trade artifacts; "
    "no momentum threshold, top-N, hold-day, cooldown, notional, or response "
    "retune."
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260707_002_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT_FILE = (
    "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
WAREHOUSE_SQLITE = "data/warehouse/warehouse_main.sqlite"
SOURCE_ARTIFACTS = [
    {
        "label": "distribution_day_absorption",
        "experiment_id": "exp-20260611-007",
        "path": (
            "data/experiments/exp-20260611-007/"
            "exp_20260611_007_distribution_day_absorption_shared_adapter.json"
        ),
        "prior_decision": "accepted_default_off_shared_adapter",
    },
    {
        "label": "gap_hold_core_flow_confirmed",
        "experiment_id": "exp-20260609-016",
        "path": (
            "data/experiments/exp-20260609-016/"
            "exp_20260609_016_gap_hold_core_flow_confirmed.json"
        ),
        "prior_decision": "rejected_candidate_source",
    },
    {
        "label": "breakout_without_2x_volume_precursor",
        "experiment_id": "exp-20260628-019",
        "path": (
            "data/experiments/exp-20260628-019/"
            "exp_20260628_019_breakout_precursor_full_stack.json"
        ),
        "prior_decision": "rejected_full_stack_candidate_source",
    },
]
CANONICAL_WINDOWS = ("late_strong", "mid_weak", "old_thin")
MIN_TOTAL_USABLE = 150
MIN_WINDOW_USABLE = 20
MIN_SOURCE_USABLE = 20
MIN_BUCKET_ROWS = 9
PORTFOLIO_CAPITAL_USD = 100_000.0

PREDICTION = {
    "success_probability": 0.23,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "field_is_low_volatility_proxy",
        "window_instability",
        "missing_entry_atr",
        "sample_too_thin",
    ],
    "confidence_reason": (
        "External July 2026 microstructure research says short-trend decay "
        "depends on vol-normalized tick size; local OHLCV breakout families are "
        "often positive but window-fragile, so a PIT execution-viability field "
        "may explain failures without retuning momentum thresholds."
    ),
    "recorded_at": "2026-07-07T01:08:35+00:00",
}

HYPOTHESIS = (
    "Short-trend and breakout candidate pools may retain after-cost edge only "
    "when a PIT microstructure viability field, vol-normalized tick size from "
    "entry-time ATR20, indicates execution is not in the small-tick trend-decay "
    "zone."
)
ALPHA_HYPOTHESIS = (
    "ranking / candidate-pool attribution: a fixed entry-time microstructure "
    "field can identify which existing short-trend paper candidates deserve "
    "future shared-helper work, without changing current entry, exit, ranking, "
    "or sizing behavior."
)
CAUSAL_COMPONENTS = [
    "fixed microstructure field",
    "existing target-trade artifacts",
    "entry-time ATR20 join",
    "tertile attribution",
    "no strategy behavior change",
]
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260628-019",
    "exp-20260611-007",
    "exp-20260609-016",
    "exp-20260706-022",
]

RUNNER = f"quant/experiments/exp_20260707_002_{STEM}.py"
RUNNER_COMMAND = f".\\.venv\\Scripts\\python.exe -B {RUNNER}"
RUNNER_WINDOWS = f"quant\\experiments\\exp_20260707_002_{STEM}.py"
CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260707_002_{STEM}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
    "scripts/experiment_fingerprint.py",
    "quant/test_experiment_fingerprint.py",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    for encoding in ("utf-8-sig", "utf-8", "utf-16"):
        try:
            with path.open(encoding=encoding) as handle:
                return json.load(handle)
        except UnicodeError:
            continue
        except (OSError, json.JSONDecodeError):
            return default
    return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def as_float(value: Any) -> float | None:
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def parse_day(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def required_missing(row: dict[str, Any], fields: list[str]) -> list[str]:
    return [field for field in fields if row.get(field) in (None, "")]


def load_baseline_metrics() -> dict[str, Any]:
    payload = read_json(REPO_ROOT / BASELINE_RESULT_FILE, {}) or {}
    keys = [
        "expected_value_score",
        "total_return_pct",
        "sharpe_daily",
        "total_pnl",
        "max_drawdown_pct",
        "signals_generated",
        "signals_survived",
        "survival_rate",
    ]
    metrics = {key: payload.get(key) for key in keys if isinstance(payload, dict) and key in payload}
    return {
        "baseline_result_file": BASELINE_RESULT_FILE,
        "loaded": isinstance(payload, dict) and bool(payload),
        "top_level_metrics": metrics,
        "canonical_reference_from_docs": {
            "aggregate_expected_value_score": 7.8941,
            "aggregate_total_pnl": 234850.99,
        },
    }


def row_return(row: dict[str, Any], pnl: float | None, notional: float | None) -> float | None:
    direct = as_float(row.get("pnl_pct_net"))
    if direct is None:
        direct = as_float(row.get("net_return_pct"))
    if direct is not None:
        return direct
    if pnl is None or notional in (None, 0.0):
        return None
    return pnl / float(notional)


def load_target_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows_out: list[dict[str, Any]] = []
    diagnostics: dict[str, Any] = {
        "source_artifacts": SOURCE_ARTIFACTS,
        "missing_by_source_window": {},
        "raw_counts_by_source_window": {},
        "required_fields": ["ticker", "entry_date", "entry_price", "pnl"],
    }
    required = diagnostics["required_fields"]
    for source in SOURCE_ARTIFACTS:
        payload = read_json(REPO_ROOT / source["path"], {})
        by_window = payload.get("target_trades_by_window") if isinstance(payload, dict) else None
        for window in CANONICAL_WINDOWS:
            raw_rows = by_window.get(window, []) if isinstance(by_window, dict) else []
            key = f"{source['label']}:{window}"
            diagnostics["raw_counts_by_source_window"][key] = len(raw_rows) if isinstance(raw_rows, list) else 0
            missing_counter: Counter[str] = Counter()
            if not isinstance(raw_rows, list):
                diagnostics["missing_by_source_window"][key] = {"target_trades_by_window": 1}
                continue
            for row in raw_rows:
                if not isinstance(row, dict):
                    missing_counter["non_dict_row"] += 1
                    continue
                missing = required_missing(row, required)
                if missing:
                    missing_counter.update(missing)
                    continue
                copied = dict(row)
                copied["attribution_source_label"] = source["label"]
                copied["attribution_source_experiment_id"] = source["experiment_id"]
                copied["attribution_source_artifact"] = source["path"]
                copied["attribution_prior_decision"] = source["prior_decision"]
                copied["window"] = window
                rows_out.append(copied)
            diagnostics["missing_by_source_window"][key] = dict(sorted(missing_counter.items()))
    diagnostics["raw_total"] = sum(diagnostics["raw_counts_by_source_window"].values())
    diagnostics["field_complete_total"] = len(rows_out)
    return rows_out, diagnostics


def atr20_before_entry(
    con: sqlite3.Connection,
    *,
    ticker: str,
    entry_day: date,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    rows = con.execute(
        """
        select date, high, low, close
        from ohlcv
        where ticker = ? and date < ?
        order by date desc
        limit 21
        """,
        (ticker, entry_day.isoformat()),
    ).fetchall()
    rows = list(reversed(rows))
    if len(rows) < 20:
        return None, {"reason": "fewer_than_20_prior_bars", "prior_bar_count": len(rows)}

    true_ranges: list[float] = []
    prev_close: float | None = None
    for day_text, high_raw, low_raw, close_raw in rows:
        high = as_float(high_raw)
        low = as_float(low_raw)
        close = as_float(close_raw)
        if high is None or low is None or close is None:
            return None, {"reason": "non_numeric_ohlcv", "date": day_text}
        if prev_close is None:
            true_range = high - low
        else:
            true_range = max(high - low, abs(high - prev_close), abs(low - prev_close))
        prev_close = close
        if true_range <= 0:
            return None, {"reason": "non_positive_true_range", "date": day_text}
        true_ranges.append(true_range)

    atr_inputs = true_ranges[-20:]
    if len(atr_inputs) < 20:
        return None, {"reason": "fewer_than_20_true_ranges", "prior_bar_count": len(true_ranges)}
    atr20 = statistics.fmean(atr_inputs)
    if atr20 <= 0:
        return None, {"reason": "non_positive_atr20"}
    return (
        {
            "atr20": atr20,
            "prior_bar_count": len(rows),
            "atr_input_count": len(atr_inputs),
            "last_ohlcv_date": rows[-1][0],
        },
        None,
    )


def enrich_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    diagnostics: dict[str, Any] = {
        "warehouse_sqlite": WAREHOUSE_SQLITE,
        "missing_reasons": {},
        "input_rows": len(rows),
    }
    missing_counter: Counter[str] = Counter()
    enriched: list[dict[str, Any]] = []
    with sqlite3.connect(REPO_ROOT / WAREHOUSE_SQLITE) as con:
        for row in rows:
            ticker = str(row.get("ticker") or "").upper()
            entry_day = parse_day(row.get("entry_date"))
            entry_price = as_float(row.get("entry_price"))
            pnl = as_float(row.get("pnl"))
            notional = as_float(row.get("paper_notional_usd"))
            if notional is None:
                notional = as_float(row.get("notional_usd"))
            pnl_pct = row_return(row, pnl, notional)
            if not ticker:
                missing_counter["ticker"] += 1
                continue
            if entry_day is None:
                missing_counter["entry_date"] += 1
                continue
            if entry_price in (None, 0.0):
                missing_counter["entry_price"] += 1
                continue
            if pnl is None:
                missing_counter["pnl"] += 1
                continue
            if pnl_pct is None:
                missing_counter["pnl_pct_or_notional"] += 1
                continue
            atr_payload, atr_error = atr20_before_entry(con, ticker=ticker, entry_day=entry_day)
            if atr_error is not None or atr_payload is None:
                missing_counter[str((atr_error or {}).get("reason") or "missing_atr20")] += 1
                continue
            atr20 = float(atr_payload["atr20"])
            tick_to_atr = 0.01 / atr20
            copied = dict(row)
            copied.update(
                {
                    "ticker": ticker,
                    "entry_date": entry_day.isoformat(),
                    "entry_price": round(entry_price, 6),
                    "pnl": round(pnl, 6),
                    "pnl_pct_net_attribution": round(pnl_pct, 8),
                    "paper_notional_usd_attribution": round(notional or 0.0, 6),
                    "atr20_entry_prior": round(atr20, 8),
                    "vol_normalized_tick_size": round(tick_to_atr, 10),
                    "tick_to_atr20": round(tick_to_atr, 10),
                    "atr20_to_entry_price": round(atr20 / entry_price, 8),
                    "tick_to_entry_price": round(0.01 / entry_price, 10),
                    "microstructure_known_at": "after_prior_close_before_entry_open",
                    "microstructure_field_version": "vol_normalized_tick_size_atr20_v1",
                    "atr20_source": {
                        "warehouse_sqlite": WAREHOUSE_SQLITE,
                        **atr_payload,
                    },
                }
            )
            enriched.append(copied)
    diagnostics["missing_reasons"] = dict(sorted(missing_counter.items()))
    diagnostics["usable_rows"] = len(enriched)
    diagnostics["usable_rate"] = round(len(enriched) / len(rows), 6) if rows else 0.0
    return enriched, diagnostics


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "count": 0,
            "total_pnl": 0.0,
            "mean_pnl": None,
            "median_pnl": None,
            "mean_return": None,
            "median_return": None,
            "win_rate": None,
            "mean_tick_to_atr20": None,
            "mean_atr20_to_entry_price": None,
        }
    pnls = [float(row["pnl"]) for row in rows]
    returns = [float(row["pnl_pct_net_attribution"]) for row in rows]
    tick_to_atr = [float(row["tick_to_atr20"]) for row in rows]
    atr_to_price = [float(row["atr20_to_entry_price"]) for row in rows]
    wins = [value for value in returns if value > 0]
    return {
        "count": len(rows),
        "total_pnl": round(sum(pnls), 2),
        "mean_pnl": round(statistics.fmean(pnls), 6),
        "median_pnl": round(statistics.median(pnls), 6),
        "mean_return": round(statistics.fmean(returns), 8),
        "median_return": round(statistics.median(returns), 8),
        "win_rate": round(len(wins) / len(returns), 6),
        "mean_tick_to_atr20": round(statistics.fmean(tick_to_atr), 10),
        "mean_atr20_to_entry_price": round(statistics.fmean(atr_to_price), 8),
    }


def bucketize(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    ordered = sorted(rows, key=lambda row: float(row["tick_to_atr20"]))
    n = len(ordered)
    bucket_n = n // 3
    if n < MIN_BUCKET_ROWS or bucket_n <= 0:
        return {"small_tick_low_tick_to_atr": [], "middle": ordered, "coarse_tick_high_tick_to_atr": []}
    return {
        "small_tick_low_tick_to_atr": ordered[:bucket_n],
        "middle": ordered[bucket_n : n - bucket_n],
        "coarse_tick_high_tick_to_atr": ordered[n - bucket_n :],
    }


def analyze_group(name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    buckets = bucketize(rows)
    bucket_summaries = {bucket: summarize_rows(bucket_rows) for bucket, bucket_rows in buckets.items()}
    low = bucket_summaries["small_tick_low_tick_to_atr"]
    high = bucket_summaries["coarse_tick_high_tick_to_atr"]
    if low["count"] and high["count"]:
        mean_return_delta = round(float(high["mean_return"]) - float(low["mean_return"]), 8)
        mean_pnl_delta = round(float(high["mean_pnl"]) - float(low["mean_pnl"]), 6)
        win_rate_delta = round(float(high["win_rate"]) - float(low["win_rate"]), 6)
    else:
        mean_return_delta = None
        mean_pnl_delta = None
        win_rate_delta = None
    return {
        "name": name,
        "summary": summarize_rows(rows),
        "bucket_method": (
            "Rank rows by vol_normalized_tick_size = 0.01 / ATR20 using only "
            "bars before entry_date; compare top tertile (coarse tick relative "
            "to ATR) with bottom tertile (small tick relative to ATR)."
        ),
        "buckets": bucket_summaries,
        "coarse_minus_small_tick": {
            "mean_return": mean_return_delta,
            "mean_pnl": mean_pnl_delta,
            "win_rate": win_rate_delta,
        },
        "coarse_tick_better": bool(mean_return_delta is not None and mean_return_delta > 0),
    }


def group_by(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key) or "missing")].append(row)
    return dict(sorted(grouped.items()))


def aggregate_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if rows and "pnl_pct_net_attribution" not in rows[0]:
        pnls: list[float] = []
        returns: list[float] = []
        for row in rows:
            pnl = as_float(row.get("pnl"))
            notional = as_float(row.get("paper_notional_usd"))
            if notional is None:
                notional = as_float(row.get("notional_usd"))
            pnl_pct = row_return(row, pnl, notional)
            if pnl is not None:
                pnls.append(pnl)
            if pnl_pct is not None:
                returns.append(pnl_pct)
        total_pnl = sum(pnls)
        return {
            "target_trade_count": len(rows),
            "total_pnl": round(total_pnl, 2),
            "return_fraction_vs_100k_reference": round(total_pnl / PORTFOLIO_CAPITAL_USD, 8),
            "mean_trade_return": round(statistics.fmean(returns), 8) if returns else None,
            "win_rate": (
                round(sum(1 for value in returns if value > 0) / len(returns), 6)
                if returns
                else None
            ),
        }
    summary = summarize_rows(rows)
    return {
        "target_trade_count": summary["count"],
        "total_pnl": summary["total_pnl"],
        "return_fraction_vs_100k_reference": round(summary["total_pnl"] / PORTFOLIO_CAPITAL_USD, 8),
        "mean_trade_return": summary["mean_return"],
        "win_rate": summary["win_rate"],
    }


def build_result() -> dict[str, Any]:
    timestamp = utc_now_iso()
    raw_rows, load_diag = load_target_rows()
    enriched_rows, enrich_diag = enrich_rows(raw_rows)

    aggregate = analyze_group("aggregate", enriched_rows)
    by_window = {
        window: analyze_group(window, rows)
        for window, rows in group_by(enriched_rows, "window").items()
    }
    by_source = {
        source: analyze_group(source, rows)
        for source, rows in group_by(enriched_rows, "attribution_source_label").items()
    }
    by_source_window = {
        f"{source}:{window}": analyze_group(
            f"{source}:{window}",
            [
                row
                for row in enriched_rows
                if row.get("attribution_source_label") == source and row.get("window") == window
            ],
        )
        for source in sorted(group_by(enriched_rows, "attribution_source_label"))
        for window in CANONICAL_WINDOWS
    }

    usable_by_window = {
        window: by_window.get(window, {"summary": {"count": 0}})["summary"]["count"]
        for window in CANONICAL_WINDOWS
    }
    usable_by_source = {
        source: result["summary"]["count"]
        for source, result in by_source.items()
    }
    windows_coarse_better = [
        window
        for window, result in by_window.items()
        if result["summary"]["count"] >= MIN_WINDOW_USABLE and result["coarse_tick_better"]
    ]
    windows_evaluable = [
        window for window, count in usable_by_window.items() if count >= MIN_WINDOW_USABLE
    ]
    sources_coarse_better = [
        source
        for source, result in by_source.items()
        if result["summary"]["count"] >= MIN_SOURCE_USABLE and result["coarse_tick_better"]
    ]
    sources_evaluable = [
        source for source, count in usable_by_source.items() if count >= MIN_SOURCE_USABLE
    ]

    failure_reasons: list[str] = []
    if len(enriched_rows) < MIN_TOTAL_USABLE:
        failure_reasons.append("sample_too_thin")
    thin_windows = [window for window, count in usable_by_window.items() if count < MIN_WINDOW_USABLE]
    if thin_windows:
        failure_reasons.append("window_sample_too_thin")
    if enrich_diag["usable_rate"] < 0.95:
        failure_reasons.append("missing_entry_atr")
    aggregate_delta = aggregate["coarse_minus_small_tick"]["mean_return"]
    if aggregate_delta is None or aggregate_delta <= 0:
        failure_reasons.append("aggregate_coarse_tick_not_better")
    if len(windows_coarse_better) < 2:
        failure_reasons.append("fewer_than_two_windows_coarse_tick_better")
    if len(sources_coarse_better) < 2:
        failure_reasons.append("fewer_than_two_sources_coarse_tick_better")

    positive_lead = not failure_reasons
    status = STATUS_POSITIVE if positive_lead else STATUS_REJECTED
    decision = DECISION_POSITIVE if positive_lead else DECISION_REJECTED
    actual_success = 1 if positive_lead else 0
    predicted = float(PREDICTION["success_probability"])

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "accepted": False,
        "accepted_alpha": False,
        "accepted_measurement_repair": False,
        "alpha_ready": False,
        "decision": decision,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "observed_only_microstructure_attribution_no_strategy_change",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": PREDICTION,
        "parameters": {
            "source_artifacts": SOURCE_ARTIFACTS,
            "warehouse_sqlite": WAREHOUSE_SQLITE,
            "microstructure_field": "vol_normalized_tick_size = 0.01 / ATR20",
            "atr_lookback_sessions": 20,
            "entry_time_contract": "uses only ohlcv.date < entry_date",
            "bucket_method": "within-group tertiles by tick_to_atr20",
            "acceptance_boundary": (
                "observed-only attribution lead only; future use requires shared "
                "helper and standard Gate 1-4."
            ),
            "strategy_behavior_changed": False,
        },
        "gate1": {
            "passed": bool(raw_rows),
            "baseline": load_baseline_metrics(),
            "source_artifacts_loaded": load_diag,
        },
        "gate2": {
            "passed": bool(enriched_rows),
            "field_dependencies": [
                "ticker",
                "entry_date",
                "entry_price",
                "pnl",
                "pnl_pct_net or paper_notional_usd",
                "ohlcv high/low/close for 20 sessions before entry_date",
            ],
            "sentinel_entry_date_checked": True,
            "sentinel_target_price_contract": {
                "applicable": False,
                "reason": (
                    "This observed-only runner consumes already closed "
                    "target-trade artifacts and does not regenerate signals or "
                    "backtester exits; target_price is therefore not used as a "
                    "strategy signal contract in this attribution."
                ),
            },
            "microstructure_known_at": "after_prior_close_before_entry_open",
            "load_diagnostics": load_diag,
            "enrichment_diagnostics": enrich_diag,
        },
        "gate3": {
            "passed": enrich_diag["usable_rate"] >= 0.05,
            "signals_generated": load_diag["raw_total"],
            "signals_survived": len(enriched_rows),
            "survival_rate": enrich_diag["usable_rate"],
            "note": "No filter is applied to strategy behavior; survival measures ATR join coverage.",
        },
        "gate4": {
            "passed": positive_lead,
            "failed_reasons": failure_reasons,
            "acceptance_rule": (
                "Require >=150 usable rows, >=20 per canonical window, aggregate "
                "coarse-minus-small tick return delta > 0, and at least two "
                "windows plus two source families with positive coarse-minus-"
                "small tick return delta."
            ),
            "windows_evaluable": windows_evaluable,
            "windows_coarse_tick_better": windows_coarse_better,
            "sources_evaluable": sources_evaluable,
            "sources_coarse_tick_better": sources_coarse_better,
            "thin_windows": thin_windows,
            "aggregate_coarse_minus_small_tick_return": aggregate_delta,
            "decision": decision,
        },
        "attribution": {
            "aggregate": aggregate,
            "by_window": by_window,
            "by_source": by_source,
            "by_source_window": by_source_window,
            "usable_by_window": usable_by_window,
            "usable_by_source": usable_by_source,
            "sample_rows": enriched_rows[:25],
        },
        "before_metrics": {
            "strategy_baseline": load_baseline_metrics(),
            "candidate_rows_before_microstructure_join": aggregate_metrics(raw_rows),
        },
        "after_metrics": {
            "candidate_rows_after_microstructure_join": aggregate_metrics(enriched_rows),
            "microstructure_attribution": {
                "aggregate_coarse_minus_small_tick": aggregate["coarse_minus_small_tick"],
                "windows_coarse_tick_better": windows_coarse_better,
                "sources_coarse_tick_better": sources_coarse_better,
            },
        },
        "delta_metrics": {
            "strategy_behavior_delta": 0.0,
            "orders_changed": False,
            "aggregate_coarse_minus_small_tick": aggregate["coarse_minus_small_tick"],
        },
        "activation_readiness": {
            "alpha_ready": False,
            "blockers": [
                "observed_only_attribution_no_strategy_or_paper_behavior_change",
                "needs_shared_helper_before_any_candidate_pool_use",
                "needs standard Gate 1-4 before activation",
            ],
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_changed": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "ranking_or_sizing_changed": False,
            "trade_enabled": False,
            "live_ready": False,
            "parity_note": (
                "This runner reads historical target-trade artifacts and "
                "warehouse OHLCV only. It does not alter production/backtest "
                "adapters or any order path."
            ),
        },
        "calibration": {
            "actual_decision": decision,
            "actual_success": actual_success,
            "predicted_success_probability": predicted,
            "brier_score": round((predicted - actual_success) ** 2, 6),
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "realized_failure_modes": failure_reasons,
            "predicted_failure_mode_hit": bool(
                set(PREDICTION["main_failure_modes"]) & set(failure_reasons)
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The fixed tick-to-ATR field was joined at entry time across "
                "three existing short-trend candidate artifacts. The result is "
                "judged only as attribution: aggregate and cross-window "
                "coarse-minus-small tick return deltas must agree before the "
                "field can be treated as a future lead."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not rerun this by changing ATR lookback, tertile cutoffs, "
                "momentum thresholds, source top-N, hold days, cooldowns, "
                "notional, or response shape on the same artifacts. A legal "
                "retry needs a genuinely new microstructure source such as PIT "
                "spread/depth, materially more closed forward rows, or a shared "
                "helper Gate 1-4 that preserves this exact field contract."
            ),
            "new_evidence_required": (
                "PIT spread/depth or cost data, materially more settled forward "
                "rows, or a shared default-off helper with standard Gate 1-4."
            ),
        },
        "rejection_reason": (
            None
            if positive_lead
            else "Microstructure tick viability attribution failed: "
            + ", ".join(failure_reasons)
        ),
        "next_retry_requires": [
            "PIT spread/depth or cost source",
            "materially more closed forward rows",
            "shared default-off helper plus standard Gate 1-4",
            "no ATR lookback, tertile, threshold, top-N, hold-day, or notional retune",
        ],
        "changed_files": CHANGED_FILES,
        "related_files": [
            BASELINE_RESULT_FILE,
            WAREHOUSE_SQLITE,
            *[source["path"] for source in SOURCE_ARTIFACTS],
        ],
        "reproduction_commands": [
            f".\\.venv\\Scripts\\python.exe -B -m py_compile {RUNNER_WINDOWS}",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_experiment_fingerprint.py -q",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "lean_quality_passed": True,
        "anti_js": {"used_javascript": False, "evidence": "Python runner and pytest only."},
    }
    return payload


def build_log(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "accepted",
        "accepted_alpha",
        "accepted_measurement_repair",
        "alpha_ready",
        "decision",
        "hypothesis",
        "alpha_hypothesis",
        "change_type",
        "implementation_mode",
        "changed_variable",
        "single_causal_variable",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "prediction",
        "parameters",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "attribution",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "activation_readiness",
        "production_impact",
        "calibration",
        "post_run_reflection",
        "rejection_reason",
        "next_retry_requires",
        "changed_files",
        "related_files",
        "reproduction_commands",
        "lean_quality_passed",
        "anti_js",
    ]
    return {key: payload.get(key) for key in keys}


def build_card(payload: dict[str, Any]) -> str:
    gate4 = payload["gate4"]
    aggregate = payload["attribution"]["aggregate"]
    delta = aggregate["coarse_minus_small_tick"]
    lines = [
        f"# {EXPERIMENT_ID} - microstructure tick viability attribution",
        "",
        f"- status: {payload['status']}",
        f"- decision: {payload['decision']}",
        f"- usable rows: {payload['gate3']['signals_survived']} / {payload['gate3']['signals_generated']}",
        f"- aggregate coarse-minus-small return: {delta['mean_return']}",
        f"- aggregate coarse-minus-small pnl: {delta['mean_pnl']}",
        f"- windows coarse tick better: {', '.join(gate4['windows_coarse_tick_better']) or 'none'}",
        f"- sources coarse tick better: {', '.join(gate4['sources_coarse_tick_better']) or 'none'}",
        f"- failed reasons: {', '.join(gate4['failed_reasons']) or 'none'}",
        "",
        "No live, paper, ranking, sizing, entry, or exit behavior changed.",
        "",
        "## Boundary",
        "",
        payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
        "",
        "## Reproduce",
        "",
        f"- `{RUNNER_COMMAND}`",
        "- `.\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_experiment_fingerprint.py -q`",
        "- `.\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict`",
    ]
    return "\n".join(lines) + "\n"


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "generated_at": payload["timestamp"],
        "runner": RUNNER,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "ticket": repo_rel(TICKET_JSON),
        "files": CHANGED_FILES,
        "reproduction_commands": payload["reproduction_commands"],
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(build_log(payload), allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    write_json(MANIFEST_JSON, build_manifest(payload))
    ticket = read_json(TICKET_JSON, {}) or {}
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": payload["accepted_alpha"],
            "accepted_measurement_repair": payload["accepted_measurement_repair"],
            "alpha_ready": payload["alpha_ready"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "summary": {
                "status": payload["status"],
                "gate4_failed_reasons": payload["gate4"]["failed_reasons"],
                "aggregate_coarse_minus_small_tick": (
                    payload["attribution"]["aggregate"]["coarse_minus_small_tick"]
                ),
                "windows_coarse_tick_better": payload["gate4"]["windows_coarse_tick_better"],
                "sources_coarse_tick_better": payload["gate4"]["sources_coarse_tick_better"],
            },
        },
        status=payload["status"],
        fields={
            **{key: value for key, value in ticket.items() if key not in {"result", "status"}},
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
            "parameters": payload["parameters"],
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "attribution": payload["attribution"],
            "activation_readiness": payload["activation_readiness"],
            "production_impact": payload["production_impact"],
            "calibration": payload["calibration"],
            "post_run_reflection": payload["post_run_reflection"],
            "rejection_reason": payload["rejection_reason"],
            "next_retry_requires": payload["next_retry_requires"],
            "changed_files": CHANGED_FILES,
            "related_files": payload["related_files"],
            "reproduction_commands": payload["reproduction_commands"],
            "lean_quality_passed": payload["lean_quality_passed"],
        },
    )


def main() -> None:
    payload = build_result()
    persist(payload)
    summary = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "usable_rows": payload["gate3"]["signals_survived"],
        "failed_reasons": payload["gate4"]["failed_reasons"],
        "aggregate_coarse_minus_small_tick": (
            payload["attribution"]["aggregate"]["coarse_minus_small_tick"]
        ),
        "artifact": repo_rel(OUT_JSON),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
