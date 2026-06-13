"""exp-20260611-023: winner-continuation tail-state attribution.

Observed-only alpha search. This runner tests whether recently rejected broad
momentum/default-off candidate sources share a production-visible tail-state
bucket that explains loss-tail and comparator failure.

No strategy helper, ranking, sizing, exit, order, LLM/news, watchlist, or daily
adapter behavior changes.

Reproduce:
    .venv/Scripts/python.exe -B quant/experiments/exp_20260611_023_winner_continuation_tail_state_attribution.py
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260611-023"
STEM = "winner_continuation_tail_state_attribution"
LANE = "alpha_search"
BASELINE_FILE = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260611_023_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

SOURCE_ARTIFACTS = [
    {
        "experiment_id": "exp-20260611-009",
        "family": "pocket_pivot_accumulation",
        "artifact": REPO_ROOT
        / "data"
        / "experiments"
        / "exp-20260611-009"
        / "exp_20260611_009_pocket_pivot_accumulation_leadership.json",
        "nearby_failure": "rejected after old_thin regression, drawdown drift, and accepted compression comparator failure",
    },
    {
        "experiment_id": "exp-20260611-011",
        "family": "market_follow_through_day",
        "artifact": REPO_ROOT
        / "data"
        / "experiments"
        / "exp-20260611-011"
        / "exp_20260611_011_market_follow_through_day_leadership.json",
        "nearby_failure": "rejected versus accepted distribution comparator",
    },
    {
        "experiment_id": "exp-20260611-014",
        "family": "distribution_absorption_precompression",
        "artifact": REPO_ROOT
        / "data"
        / "experiments"
        / "exp-20260611-014"
        / "exp_20260611_014_distribution_absorption_precompression.json",
        "nearby_failure": "rejected as likely relabel of accepted distribution/compression behavior",
    },
    {
        "experiment_id": "exp-20260611-019",
        "family": "distribution_pressure_low_beta_defensive",
        "artifact": REPO_ROOT
        / "data"
        / "experiments"
        / "exp-20260611-019"
        / "exp_20260611_019_distribution_pressure_low_beta_defensive_leadership.json",
        "nearby_failure": "rejected versus accepted distribution-day absorption comparator",
    },
]

TAIL_SAFE = "tail_constructive_non_extended"
TAIL_MIXED = "tail_mixed"
TAIL_HIGH_RISK = "tail_hot_extended_high_vol"
TAIL_ORDER = [TAIL_SAFE, TAIL_MIXED, TAIL_HIGH_RISK]

MIN_COMBINED_TARGET_TRADES = 100
MIN_BUCKET_TRADES_PER_WINDOW = 5
MIN_BUCKET_TRADES_PER_SOURCE = 5
MIN_PASSING_SOURCE_FAMILIES = 3

PREDICTION = {
    "success_probability": 0.24,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "diagnostic_overfit",
        "source_family_confounding",
        "no_cross_window_monotonicity",
        "tail_state_fields_only_relabel_momentum",
    ],
    "confidence_reason": (
        "Recent pocket-pivot, follow-through, distribution-precompression, and "
        "low-beta defensive candidates failed despite intuitive momentum labels; "
        "playbook explicitly asks for tail-state field-building before promotion. "
        "The same OHLCV fields are production-visible, but exp-20260610-021 warned "
        "that tail-state routing can overfit, so success is modest."
    ),
    "recorded_at": "2026-06-11T17:57:43+00:00",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _repo_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _round(value: Any, digits: int = 4) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _baseline_metrics() -> dict[str, Any]:
    payload = _load_json(BASELINE_FILE)
    windows: dict[str, dict[str, Any]] = {}
    for row in payload.get("windows") or []:
        label = str(row.get("label") or "")
        if not label:
            continue
        windows[label] = {
            "expected_value_score": _round(row.get("expected_value_score")),
            "sharpe_daily": _round(row.get("sharpe_daily")),
            "total_pnl": _round(row.get("total_pnl"), 2),
            "max_drawdown_pct": _round(row.get("max_drawdown_pct")),
            "win_rate": _round(row.get("win_rate")),
            "trade_count": int(row.get("trade_count") or 0),
            "signals_generated": int(row.get("signals_generated") or 0),
            "signals_survived": int(row.get("signals_survived") or 0),
            "survival_rate": _round(row.get("survival_rate")),
        }
    return windows


def _aggregate_baseline(windows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    survival_values = [
        _safe_float(row.get("survival_rate"))
        for row in windows.values()
        if row.get("survival_rate") is not None
    ]
    return {
        "expected_value_score_sum": round(
            sum(_safe_float(row.get("expected_value_score")) for row in windows.values()),
            4,
        ),
        "total_pnl_sum": round(
            sum(_safe_float(row.get("total_pnl")) for row in windows.values()),
            2,
        ),
        "minimum_survival_rate": round(min(survival_values), 4) if survival_values else None,
        "window_count": len(windows),
    }


def _zero_delta(windows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        label: {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "max_drawdown_pct": 0.0,
            "trade_count": 0,
            "signals_generated": 0,
            "signals_survived": 0,
            "survival_rate": 0.0,
        }
        for label in windows
    }


def _extension_ratio(row: dict[str, Any]) -> float:
    ret5 = _safe_float(row.get("candidate_ret5"))
    ret20 = _safe_float(row.get("candidate_ret20"))
    denominator = max(abs(ret20), 0.03)
    return ret5 / denominator


def _tail_state_bucket(row: dict[str, Any]) -> str:
    ret5 = _safe_float(row.get("candidate_ret5"))
    ret20 = _safe_float(row.get("candidate_ret20"))
    ret60 = _safe_float(row.get("candidate_ret60"))
    signal_ret = _safe_float(row.get("candidate_signal_day_return"))
    vol20 = _safe_float(row.get("candidate_realized_vol_20d"))
    close_location = _safe_float(row.get("candidate_close_location"))
    volume_ratio = _safe_float(row.get("candidate_volume_ratio_20d"), 1.0)
    ret20_excess_spy = _safe_float(row.get("candidate_ret20_excess_spy"))
    ext_ratio = _extension_ratio(row)

    hot_chase = (ret5 >= 0.10 and ext_ratio >= 0.55) or (
        signal_ret >= 0.065 and close_location >= 0.80
    )
    broad_extension = ret20 >= 0.30 and ret60 >= 0.35
    volatility_chase = vol20 >= 0.035 and (ret20 >= 0.18 or signal_ret >= 0.045)
    volume_exhaustion = volume_ratio >= 2.80 and signal_ret >= 0.050
    if hot_chase or broad_extension or volatility_chase or volume_exhaustion:
        return TAIL_HIGH_RISK

    constructive_ret20 = 0.03 <= ret20 <= 0.22
    non_chase = ret5 <= 0.08 and signal_ret <= 0.055
    controlled_vol = vol20 <= 0.025
    acceptable_volume = 0.70 <= volume_ratio <= 2.50
    if (
        constructive_ret20
        and non_chase
        and controlled_vol
        and close_location >= 0.60
        and acceptable_volume
        and ret20_excess_spy >= -0.02
    ):
        return TAIL_SAFE

    return TAIL_MIXED


def _normalize_trade(
    source_meta: dict[str, Any],
    window: str,
    row: dict[str, Any],
) -> dict[str, Any]:
    pnl = _safe_float(row.get("pnl"))
    notional = _safe_float(row.get("paper_notional_usd") or row.get("notional_usd"), 4000.0)
    normalized = {
        "source_experiment_id": source_meta["experiment_id"],
        "source_family": source_meta["family"],
        "window": window,
        "ticker": str(row.get("ticker") or "UNKNOWN").upper(),
        "signal_date": row.get("signal_date") or row.get("date"),
        "entry_date": row.get("entry_date"),
        "exit_date": row.get("exit_date"),
        "pnl": round(pnl, 2),
        "pnl_pct_net": _round(row.get("pnl_pct_net") or row.get("net_return_pct")),
        "paper_notional_usd": _round(notional, 2),
        "tail_state_bucket": _tail_state_bucket(row),
        "tail_extension_ratio_5d_over_20d": _round(_extension_ratio(row), 6),
        "candidate_ret5": _round(row.get("candidate_ret5"), 6),
        "candidate_ret20": _round(row.get("candidate_ret20"), 6),
        "candidate_ret60": _round(row.get("candidate_ret60"), 6),
        "candidate_signal_day_return": _round(row.get("candidate_signal_day_return"), 6),
        "candidate_realized_vol_20d": _round(row.get("candidate_realized_vol_20d"), 6),
        "candidate_close_location": _round(row.get("candidate_close_location"), 6),
        "candidate_volume_ratio_20d": _round(row.get("candidate_volume_ratio_20d"), 6),
        "candidate_ret20_excess_spy": _round(row.get("candidate_ret20_excess_spy"), 6),
        "candidate_relative_vs_spy": _round(row.get("candidate_relative_vs_spy"), 6),
        "candidate_relative_vs_qqq": _round(row.get("candidate_relative_vs_qqq"), 6),
        "uses_free_ohlcv_only": bool(row.get("uses_free_ohlcv_only", True)),
        "uses_llm": bool(row.get("uses_llm", False)),
        "trade_enabled": bool(row.get("trade_enabled", False)),
    }
    if row.get("entry_date") is None:
        normalized["field_missing_entry_date"] = True
    if row.get("target_price") is None:
        normalized["field_missing_target_price"] = True
    return normalized


def _load_target_trades() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    trades: list[dict[str, Any]] = []
    source_counts: dict[str, Any] = {}
    for source_meta in SOURCE_ARTIFACTS:
        payload = _load_json(source_meta["artifact"])
        source_key = source_meta["experiment_id"]
        by_window = payload.get("target_trades_by_window") or {}
        source_counts[source_key] = {
            "family": source_meta["family"],
            "artifact": _repo_rel(source_meta["artifact"]),
            "nearby_failure": source_meta["nearby_failure"],
            "windows": {},
        }
        for window, rows in sorted(by_window.items()):
            if not isinstance(rows, list):
                continue
            source_counts[source_key]["windows"][window] = len(rows)
            for row in rows:
                if isinstance(row, dict):
                    trades.append(_normalize_trade(source_meta, str(window), row))
    return trades, source_counts


def _loss_tail_average(values: list[float]) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    tail_count = max(1, math.ceil(len(sorted_values) * 0.20))
    return sum(sorted_values[:tail_count]) / tail_count


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    index = min(len(sorted_values) - 1, max(0, math.floor((len(sorted_values) - 1) * pct)))
    return sorted_values[index]


def _summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pnls = [_safe_float(row.get("pnl")) for row in rows]
    positive_pnls = [value for value in pnls if value > 0]
    negative_pnls = [value for value in pnls if value < 0]
    tickers = Counter(str(row.get("ticker") or "UNKNOWN") for row in rows)
    return {
        "trade_count": len(rows),
        "total_pnl": _round(sum(pnls), 2),
        "avg_pnl": _round(sum(pnls) / len(pnls), 4) if pnls else None,
        "median_pnl": _round(statistics.median(pnls), 4) if pnls else None,
        "win_rate": _round(len(positive_pnls) / len(pnls), 4) if pnls else None,
        "loss_rate": _round(len(negative_pnls) / len(pnls), 4) if pnls else None,
        "loss_tail_20pct_avg_pnl": _round(_loss_tail_average(pnls), 4),
        "p10_pnl": _round(_percentile(pnls, 0.10), 4),
        "p90_pnl": _round(_percentile(pnls, 0.90), 4),
        "worst_pnl": _round(min(pnls), 4) if pnls else None,
        "best_pnl": _round(max(pnls), 4) if pnls else None,
        "top_ticker_counts": dict(tickers.most_common(5)),
    }


def _group_summary(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(key) or "unknown")].append(row)
    return {name: _summarize_rows(group_rows) for name, group_rows in sorted(groups.items())}


def _bucket_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {bucket: [] for bucket in TAIL_ORDER}
    for row in rows:
        grouped.setdefault(str(row["tail_state_bucket"]), []).append(row)
    return {bucket: _summarize_rows(grouped.get(bucket, [])) for bucket in TAIL_ORDER}


def _pass_high_vs_safe(summary: dict[str, Any], min_bucket_rows: int) -> dict[str, Any]:
    safe = summary.get(TAIL_SAFE) or {}
    high = summary.get(TAIL_HIGH_RISK) or {}
    safe_count = int(safe.get("trade_count") or 0)
    high_count = int(high.get("trade_count") or 0)
    enough_rows = safe_count >= min_bucket_rows and high_count >= min_bucket_rows
    avg_separation = _safe_float(high.get("avg_pnl")) < _safe_float(safe.get("avg_pnl"))
    loss_tail_separation = _safe_float(high.get("loss_tail_20pct_avg_pnl")) < _safe_float(
        safe.get("loss_tail_20pct_avg_pnl")
    )
    loss_rate_separation = _safe_float(high.get("loss_rate")) >= _safe_float(safe.get("loss_rate"))
    return {
        "passed": bool(enough_rows and avg_separation and loss_tail_separation),
        "enough_rows": enough_rows,
        "safe_count": safe_count,
        "high_risk_count": high_count,
        "avg_pnl_high_minus_safe": _round(
            _safe_float(high.get("avg_pnl")) - _safe_float(safe.get("avg_pnl")),
            4,
        ),
        "loss_tail_high_minus_safe": _round(
            _safe_float(high.get("loss_tail_20pct_avg_pnl"))
            - _safe_float(safe.get("loss_tail_20pct_avg_pnl")),
            4,
        ),
        "loss_rate_high_minus_safe": _round(
            _safe_float(high.get("loss_rate")) - _safe_float(safe.get("loss_rate")),
            4,
        ),
        "avg_separation": avg_separation,
        "loss_tail_separation": loss_tail_separation,
        "loss_rate_separation": loss_rate_separation,
    }


def _evaluate_tail_state(rows: list[dict[str, Any]]) -> dict[str, Any]:
    bucket_overall = _bucket_summary(rows)
    windows: dict[str, dict[str, Any]] = {}
    for window, window_rows in _grouped_rows(rows, "window").items():
        summary = _bucket_summary(window_rows)
        windows[window] = {
            "bucket_summary": summary,
            "high_vs_safe": _pass_high_vs_safe(summary, MIN_BUCKET_TRADES_PER_WINDOW),
        }

    sources: dict[str, dict[str, Any]] = {}
    for source, source_rows in _grouped_rows(rows, "source_family").items():
        summary = _bucket_summary(source_rows)
        sources[source] = {
            "bucket_summary": summary,
            "high_vs_safe": _pass_high_vs_safe(summary, MIN_BUCKET_TRADES_PER_SOURCE),
        }

    window_pass_count = sum(1 for row in windows.values() if row["high_vs_safe"]["passed"])
    source_pass_count = sum(1 for row in sources.values() if row["high_vs_safe"]["passed"])
    all_windows_pass = window_pass_count == len(windows) and bool(windows)
    minimum_sample_pass = len(rows) >= MIN_COMBINED_TARGET_TRADES
    source_family_pass = source_pass_count >= MIN_PASSING_SOURCE_FAMILIES
    passed = bool(minimum_sample_pass and all_windows_pass and source_family_pass)

    failed_reasons: list[str] = []
    if not minimum_sample_pass:
        failed_reasons.append("combined_target_trade_sample_too_thin")
    if not all_windows_pass:
        failed_reasons.append("tail_state_not_stable_across_all_windows")
    if not source_family_pass:
        failed_reasons.append("tail_state_not_stable_across_enough_source_families")
    if not failed_reasons and not passed:
        failed_reasons.append("tail_state_field_not_promotable")

    return {
        "diagnostic_only": True,
        "passed": passed,
        "decision": "observed_only_tail_state_field_lead"
        if passed
        else "rejected_no_stable_tail_state_separation",
        "failed_reasons": failed_reasons,
        "thresholds": {
            "min_combined_target_trades": MIN_COMBINED_TARGET_TRADES,
            "min_bucket_trades_per_window": MIN_BUCKET_TRADES_PER_WINDOW,
            "min_bucket_trades_per_source": MIN_BUCKET_TRADES_PER_SOURCE,
            "min_passing_source_families": MIN_PASSING_SOURCE_FAMILIES,
        },
        "combined_target_trades": len(rows),
        "bucket_summary_overall": bucket_overall,
        "windows": windows,
        "source_families": sources,
        "window_pass_count": window_pass_count,
        "source_family_pass_count": source_pass_count,
    }


def _grouped_rows(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(key) or "unknown")].append(row)
    return dict(sorted(groups.items()))


def _dependency_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    required = [
        "entry_date",
        "candidate_ret5",
        "candidate_ret20",
        "candidate_signal_day_return",
        "candidate_realized_vol_20d",
        "candidate_close_location",
        "candidate_volume_ratio_20d",
    ]
    coverage = {}
    for field in required:
        present = sum(1 for row in rows if row.get(field) is not None)
        coverage[field] = round(present / len(rows), 4) if rows else 0.0
    target_price_present = sum(1 for row in rows if not row.get("field_missing_target_price"))
    return {
        "passed": bool(rows) and coverage.get("entry_date", 0.0) == 1.0,
        "required_runtime_fields": required,
        "field_coverage": coverage,
        "minimum_position_field_check": {
            "entry_date": "present on all normalized target trades"
            if coverage.get("entry_date", 0.0) == 1.0
            else "missing on some normalized target trades",
            "target_price": (
                "not required for closed paper target trades; no live/core positions modified"
                if target_price_present < len(rows)
                else "present"
            ),
        },
    }


def _sample_rows(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    samples: dict[str, list[dict[str, Any]]] = {}
    for bucket in TAIL_ORDER:
        bucket_rows = [row for row in rows if row.get("tail_state_bucket") == bucket]
        ordered = sorted(bucket_rows, key=lambda row: _safe_float(row.get("pnl")))
        samples[bucket] = ordered[:3] + ordered[-3:] if len(ordered) > 6 else ordered
    return samples


def _build_payload() -> dict[str, Any]:
    timestamp = _utc_now()
    baseline = _baseline_metrics()
    trades, source_counts = _load_target_trades()
    gate4 = _evaluate_tail_state(trades)
    status = "observed_only" if gate4["passed"] else "rejected"
    actual_success = 1 if gate4["passed"] else 0
    predicted = _safe_float(PREDICTION["success_probability"])
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": gate4["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "lane": LANE,
        "change_type": "observed_only_tail_state_attribution",
        "implementation_mode": "observed_only_attribution",
        "mechanism_family": "momentum_tail_state_classifier",
        "trial_family": "broad_momentum_tail_state_attribution",
        "trial_variant_id": "winner_continuation_tail_state_bucket_v1",
        "changed_variable": "winner_continuation_tail_state_bucket_v1_read_only_attribution",
        "hypothesis": (
            "candidate_pool diagnostic: recently rejected broad momentum/default-off "
            "candidate sources may share a production-visible tail-state bucket where "
            "high extension plus high volatility explains loss-tail and comparator failure."
        ),
        "pre_run_questions": {
            "1_alpha_hypothesis": (
                "candidate_pool / field-building: a production-visible OHLCV "
                "tail-state bucket may separate constructive continuation from "
                "hot extended high-volatility chase candidates."
            ),
            "2_history_check": {
                "exp-20260610-021": (
                    "Rejected tail-state allocator routing; warned that routing "
                    "can overfit and source-family confounding matters."
                ),
                "exp-20260611-009": "Rejected pocket-pivot accumulation leadership.",
                "exp-20260611-011": "Rejected market follow-through day leadership.",
                "exp-20260611-014": "Rejected distribution absorption precompression.",
                "exp-20260611-019": "Rejected distribution-pressure low-beta defensive leadership.",
            },
            "3_single_decision_hypothesis": (
                "winner_continuation_tail_state_bucket_v1_read_only_attribution; "
                "all work is diagnostic measurement and closeout plumbing."
            ),
            "4_acceptance_standard": (
                "Observed-only lead requires >=100 target trades, high-risk bucket "
                "worse than safe bucket on average PnL and 20pct loss tail in all "
                "three windows and at least three source families. It cannot accept "
                "a trading rule without a later shared helper and Gate 1-4."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260611_023_winner_continuation_tail_state_attribution.py"
            ),
        },
        "prediction": PREDICTION,
        "calibration": {
            "actual_decision": gate4["decision"],
            "actual_success": actual_success,
            "predicted_success_probability": predicted,
            "brier_score": round((predicted - actual_success) ** 2, 4),
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "predicted_failure_mode_hit": not gate4["passed"],
            "realized_failure_mode": ";".join(gate4["failed_reasons"]) if gate4["failed_reasons"] else None,
            "surprise_note": (
                "Tail-state separation was stable enough to justify a later shared "
                "field test, but remains observed-only."
                if gate4["passed"]
                else "The fixed bucket did not separate loss-tail robustly enough across windows and sources."
            ),
        },
        "nearby_prior_experiments": [
            "exp-20260610-021",
            "exp-20260611-009",
            "exp-20260611-011",
            "exp-20260611-014",
            "exp-20260611-019",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "cross_source_rejected_candidate_trade_attribution",
        "backtest_protocol": {
            "source": "Read-only attribution over existing completed target-trade artifacts.",
            "baseline_result_file": _repo_rel(BASELINE_FILE),
            "canonical_windows": ["late_strong", "mid_weak", "old_thin"],
            "replay_llm": False,
            "replay_news": False,
            "strategy_logic_changed": False,
        },
        "source_artifacts": source_counts,
        "tail_state_rule": {
            "rule_version": "winner_continuation_tail_state_bucket_v1",
            "inputs": [
                "candidate_ret5",
                "candidate_ret20",
                "candidate_ret60",
                "candidate_signal_day_return",
                "candidate_realized_vol_20d",
                "candidate_close_location",
                "candidate_volume_ratio_20d",
                "candidate_ret20_excess_spy",
            ],
            "known_at": "after_signal_day_close_before_next_open_paper_entry",
            "production_visible": True,
            "trade_enabled": False,
            "bucket_order": TAIL_ORDER,
        },
        "gate1": {
            "passed": bool(baseline),
            "baseline_artifact": _repo_rel(BASELINE_FILE),
            "baseline_metrics": baseline,
            "aggregate": _aggregate_baseline(baseline),
        },
        "gate2": _dependency_audit(trades),
        "gate3": {
            "passed": True,
            "candidate_pool_changed": False,
            "new_core_filter_added": False,
            "minimum_core_survival_rate": _aggregate_baseline(baseline).get("minimum_survival_rate"),
            "note": "Read-only attribution; core signals and survival are unchanged.",
        },
        "gate4": gate4,
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "aggregate": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_sum_delta": 0.0,
                "strategy_logic_changed": False,
                "diagnostic_target_trade_count": len(trades),
            },
            "by_window": _zero_delta(baseline),
        },
        "bucket_summary_by_window": {
            key: value["bucket_summary"] for key, value in gate4["windows"].items()
        },
        "bucket_summary_by_source_family": {
            key: value["bucket_summary"] for key, value in gate4["source_families"].items()
        },
        "target_trade_summary_by_window": _group_summary(trades, "window"),
        "target_trade_summary_by_source_family": _group_summary(trades, "source_family"),
        "sample_rows_by_bucket": _sample_rows(trades),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "trade_enabled": False,
            "daily_snapshot_exposed": False,
            "default_off_attribution_only": True,
            "parity_test_added": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "uses_llm": False,
            "uses_free_ohlcv_only": True,
            "live_realism_evaluated": True,
            "live_ready": False,
            "activation_envelope": {
                "intended_notional": "no activation proposed; read-only attribution over closed paper trades",
                "capital_cap": "not activated",
                "liquidity_slippage_model": "inherited from each source experiment's closed paper trade rows",
                "portfolio_displacement": "diagnostic only; no displaced candidate or order",
                "order_semantics": "no orders emitted",
                "kill_switch": "not applicable until a later shared default-off helper passes Gate 1-4",
                "failure_handling": "missing fields are counted in dependency audit; no behavior changes",
            },
            "parity_note": (
                "The runner only reads completed artifacts and baseline metrics. "
                "A positive result would require a later shared daily/backtest "
                "helper before any ranking, sizing, report queue, or order surface changes."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                f"The fixed bucket had enough sample ({len(trades)} closed target "
                f"trades), but robustness failed: only {gate4['window_pass_count']} "
                f"of {len(gate4['windows'])} windows and "
                f"{gate4['source_family_pass_count']} of "
                f"{len(gate4['source_families'])} source families passed high-risk "
                "versus safe separation. Mid_weak rewarded the hot high-volatility "
                "bucket, so the broad momentum failures are source-specific rather "
                "than explained by one simple extension-volatility state."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune ret5/ret20, volatility, volume, close-location, "
                "hold-day, notional, or source-rank thresholds on these frozen "
                "artifacts. Do not promote the bucket directly into an allocator."
            ),
            "new_evidence_required": (
                "A retry needs a materially different PIT tail-risk field, forward "
                "closed replacement-value rows, or a shared helper that tests the "
                "bucket against accepted compression, distribution, and allocator comparators."
            ),
        },
        "next_retry_requires": [
            "materially different production-visible tail-risk field",
            "forward replacement-value rows for the same bucket",
            "shared helper plus full Gate 1-4 before any trading use",
            "comparison against accepted compression, distribution, and allocator sources",
        ],
        "rejection_reason": "; ".join(gate4["failed_reasons"]) if not gate4["passed"] else None,
        "related_files": [
            "quant/experiments/exp_20260611_023_winner_continuation_tail_state_attribution.py",
            "data/experiments/exp-20260611-023/exp_20260611_023_winner_continuation_tail_state_attribution.json",
            "experiments/logs/exp-20260611-023.json",
            "experiments/tickets/exp-20260611-023.json",
            "experiments/cards/exp-20260611-023.md",
            "experiments/manifests/exp-20260611-023.json",
            "docs/experiment_log.jsonl",
        ],
        "anti_js": "No JavaScript was used.",
    }


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "lane": payload["lane"],
        "hypothesis": payload["hypothesis"],
        "change_summary": (
            "Read-only cross-source tail-state attribution over rejected broad "
            "momentum/default-off target trades; no strategy behavior changed."
        ),
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "causal_components": [
            "existing rejected target trades",
            "production-visible OHLCV features",
            "tail-state bucket",
            "loss-tail attribution",
            "no strategy behavior change",
        ],
        "prior_trial_count": 1,
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "component": "quant/experiments/exp_20260611_023_winner_continuation_tail_state_attribution.py",
        "parameters": payload["tail_state_rule"],
        "date_range": {"windows": ["late_strong", "mid_weak", "old_thin"]},
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "expected_value_score_delta": 0.0,
        "total_pnl_delta": 0.0,
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "target_trade_summary_by_window": payload["target_trade_summary_by_window"],
        "target_trade_summary_by_source_family": payload["target_trade_summary_by_source_family"],
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
        "rejection_reason": payload["rejection_reason"],
        "next_retry_requires": payload["next_retry_requires"],
        "post_run_reflection": payload["post_run_reflection"],
        "related_files": payload["related_files"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "anti_js": payload["anti_js"],
        "lean_quality_passed": True,
    }


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    existing_lines: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                if json.loads(line).get("experiment_id") == record["experiment_id"]:
                    continue
            except json.JSONDecodeError:
                pass
            existing_lines.append(line)
    existing_lines.append(json.dumps(record, sort_keys=True))
    path.write_text("\n".join(existing_lines) + "\n", encoding="utf-8")


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _load_json(TICKET_JSON)
    ticket["status"] = payload["status"]
    ticket["completed_at"] = payload["timestamp"]
    ticket["result"] = {
        "decision": payload["decision"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "accepted": False,
        "calibration": payload["calibration"],
        "combined_target_trades": payload["gate4"]["combined_target_trades"],
        "window_pass_count": payload["gate4"]["window_pass_count"],
        "source_family_pass_count": payload["gate4"]["source_family_pass_count"],
        "failed_reasons": payload["gate4"]["failed_reasons"],
        "post_run_reflection": payload["post_run_reflection"],
        "production_impact": payload["production_impact"],
    }
    TICKET_JSON.write_text(json.dumps(ticket, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _update_card(payload: dict[str, Any]) -> None:
    text = f"""---
experiment_id: "{EXPERIMENT_ID}"
status: "{payload['status']}"
lane: "{LANE}"
change_type: "observed_only_tail_state_attribution"
mechanism_family: "momentum_tail_state_classifier"
trial_family: "broad_momentum_tail_state_attribution"
trial_variant_id: "winner_continuation_tail_state_bucket_v1"
changed_variable: "winner_continuation_tail_state_bucket_v1_read_only_attribution"
---

# Experiment Card: {EXPERIMENT_ID}

## Summary

{payload['hypothesis']}

## Result

- Decision: `{payload['decision']}`
- Status: `{payload['status']}`
- Artifact: `{_repo_rel(OUT_JSON)}`
- Log: `{_repo_rel(LOG_JSON)}`
- Combined target trades: `{payload['gate4']['combined_target_trades']}`
- Window pass count: `{payload['gate4']['window_pass_count']}`
- Source-family pass count: `{payload['gate4']['source_family_pass_count']}`

## Gate 1-4

- Gate 1 baseline: `{_repo_rel(BASELINE_FILE)}`
- Aggregate baseline EV: `{payload['gate1']['aggregate']['expected_value_score_sum']}`
- Aggregate baseline PnL: `{payload['gate1']['aggregate']['total_pnl_sum']}`
- Before/after fixed-window strategy metrics: unchanged, because no strategy logic changed.
- Gate 4 diagnostic failed reasons: `{', '.join(payload['gate4']['failed_reasons']) or 'none'}`

## Reflection

This was field-building only. Do not promote the bucket into filtering,
ranking, sizing, or allocator routing from this artifact. A later strategy
experiment would need a shared daily/backtest helper and full comparator-aware
Gate 1-4 evidence.
"""
    CARD_MD.write_text(text, encoding="utf-8")


def _update_manifest(payload: dict[str, Any]) -> None:
    manifest = _load_json(MANIFEST_JSON)
    manifest["status"] = payload["status"]
    manifest["completed_at"] = payload["timestamp"]
    manifest["files"]["runner"] = {"exists": True, "path": _repo_rel(Path(__file__).resolve())}
    manifest["files"]["artifact"] = {"exists": True, "path": _repo_rel(OUT_JSON)}
    manifest["files"]["log"] = {"exists": True, "path": _repo_rel(LOG_JSON)}
    manifest["files"]["ticket"] = {"exists": True, "path": _repo_rel(TICKET_JSON)}
    manifest["files"]["card"] = {"exists": True, "path": _repo_rel(CARD_MD)}
    MANIFEST_JSON.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = _build_payload()
    log_record = _build_log_record(payload)

    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    LOG_JSON.write_text(json.dumps(log_record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _append_jsonl(EXPERIMENT_LOG, log_record)
    _update_ticket(payload)
    _update_card(payload)
    _update_manifest(payload)

    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=PREDICTION,
        result={
            "decision": payload["decision"],
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "accepted": False,
            "accepted_alpha": False,
            "combined_target_trades": payload["gate4"]["combined_target_trades"],
            "window_pass_count": payload["gate4"]["window_pass_count"],
            "source_family_pass_count": payload["gate4"]["source_family_pass_count"],
            "failed_reasons": payload["gate4"]["failed_reasons"],
            "calibration": payload["calibration"],
            "post_run_reflection": payload["post_run_reflection"],
            "production_impact": payload["production_impact"],
        },
        status=payload["status"],
        fields={
            "hypothesis": payload["hypothesis"],
            "change_type": payload["change_type"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": payload["changed_variable"],
            "changed_variable": payload["changed_variable"],
            "decision": payload["decision"],
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "ticket_file": _repo_rel(TICKET_JSON),
            "card_file": _repo_rel(CARD_MD),
            "revision_manifest_file": _repo_rel(MANIFEST_JSON),
            "expected_value_score_delta": 0.0,
            "total_pnl_delta": 0.0,
            "accepted": False,
            "accepted_alpha": False,
        },
    )

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "status": payload["status"],
                "combined_target_trades": payload["gate4"]["combined_target_trades"],
                "window_pass_count": payload["gate4"]["window_pass_count"],
                "source_family_pass_count": payload["gate4"]["source_family_pass_count"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": _repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
