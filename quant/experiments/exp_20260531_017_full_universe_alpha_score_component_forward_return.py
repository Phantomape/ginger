"""exp-20260531-017: alpha_score component forward-return attribution.

Lane: alpha_search.
Change type: read_only_full_universe_component_forward_return_attribution.
Single causal variable: full_universe_alpha_score_component_quantile_forward_return.

This is the follow-up to exp-20260531-006. The composite alpha_score had a
small top-vs-bottom full-universe forward-return edge, but no clean monotonic
quintile ladder. This runner keeps the same PIT full-universe sample and tests
only the existing alpha_score component scores. It does not add a feature,
change score weights, emit candidates, alter ranking, change sizing, or touch
orders.

No JavaScript was used.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
_QUANT_DIR = str(REPO_ROOT / "quant")
if _QUANT_DIR not in sys.path:
    sys.path.insert(0, _QUANT_DIR)

from entry_day_ranking_attribution import (  # noqa: E402
    _context_for_asof,
    load_ohlcv_snapshot,
)

EXPERIMENT_ID = "exp-20260531-017"
STEM = "full_universe_alpha_score_component_forward_return"
RULE_VERSION = "full_universe_alpha_score_components_quintile_forward_return_v1"
TRIAL_FAMILY = "cross_sectional_ranking_component_attribution"
CHANGED_VARIABLE = "full_universe_alpha_score_component_quantile_forward_return"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260531_017_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

WINDOWS = {
    "late_strong": ("2025-10-23", "2026-04-21", "ohlcv_snapshot_20251023_20260421.json"),
    "mid_weak": ("2025-04-23", "2025-10-22", "ohlcv_snapshot_20250423_20251022.json"),
    "old_thin": ("2024-10-02", "2025-04-22", "ohlcv_snapshot_20241002_20250422.json"),
}

COMPONENTS = (
    "trend",
    "relative_strength",
    "expectation_revision",
    "post_earnings_drift",
    "theme_participation",
    "breadth_alignment",
)
EXISTING_OHLCV_COMPONENTS = {"trend", "relative_strength"}

SAMPLE_STEP = 5
FORWARD_HORIZONS = (5, 10, 20)
PRIMARY_HORIZON = 5
QUINTILE = 5
MIN_BUCKET_OBS = 30
MIN_UNIQUE_COMPONENT_SCORES = 5
EDGE_FLOOR = 0.005

ACCEPTED_CORE_BASELINE = {
    "accepted_core_expected_value_score_sum": 7.8941,
    "accepted_core_total_pnl_sum": 234850.99,
    "late_strong": {
        "expected_value_score": 5.1628,
        "total_pnl": 117072.92,
        "trade_count": 18,
        "survival_rate": 0.8039,
    },
    "mid_weak": {
        "expected_value_score": 2.1402,
        "total_pnl": 78110.11,
        "trade_count": 21,
        "survival_rate": 0.7925,
    },
    "old_thin": {
        "expected_value_score": 0.5911,
        "total_pnl": 39667.96,
        "trade_count": 22,
        "survival_rate": 0.8667,
    },
    "source": "docs/backtesting.md accepted core stack after exp-20260517-009",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _forward_returns(frame: pd.DataFrame, asof_ts: pd.Timestamp) -> dict[int, float]:
    idx = frame.index
    pos = idx.searchsorted(asof_ts)
    if pos >= len(idx) or idx[pos] != asof_ts:
        return {}
    base_close = float(frame["Close"].iloc[pos])
    if base_close <= 0:
        return {}
    out: dict[int, float] = {}
    for horizon in FORWARD_HORIZONS:
        fpos = pos + horizon
        if fpos < len(idx):
            fwd_close = float(frame["Close"].iloc[fpos])
            if fwd_close > 0:
                out[horizon] = fwd_close / base_close - 1.0
    return out


def _sample_trading_days(ohlcv: dict[str, pd.DataFrame], start: str, end: str) -> list[pd.Timestamp]:
    all_dates: set[pd.Timestamp] = set()
    for frame in ohlcv.values():
        all_dates.update(frame.loc[start:end].index)
    ordered = sorted(all_dates)
    if not ordered:
        return []
    buffer = max(FORWARD_HORIZONS)
    eligible = ordered[:-buffer] if len(ordered) > buffer else []
    return eligible[::SAMPLE_STEP]


def collect_observations(ohlcv: dict[str, pd.DataFrame], start: str, end: str) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for asof_ts in _sample_trading_days(ohlcv, start, end):
        context = _context_for_asof(ohlcv, asof_ts)
        rank_map = context.get("rank_map") or {}
        for ticker, info in rank_map.items():
            components = info.get("alpha_score_components") or {}
            if not components:
                continue
            frame = ohlcv.get(ticker)
            if frame is None:
                continue
            fwd = _forward_returns(frame, asof_ts)
            if not fwd:
                continue
            component_scores = {
                component: float(value)
                for component, value in components.items()
                if component in COMPONENTS and value is not None
            }
            if not component_scores:
                continue
            observations.append(
                {
                    "asof_date": context["asof_date"],
                    "ticker": ticker,
                    "alpha_score": float(info.get("alpha_score", 0.0)),
                    "component_scores": component_scores,
                    "forward_returns": fwd,
                }
            )
    return observations


def _component_value(obs: dict[str, Any], component: str) -> float | None:
    value = (obs.get("component_scores") or {}).get(component)
    return float(value) if value is not None else None


def _component_obs(obs: list[dict[str, Any]], component: str) -> list[dict[str, Any]]:
    return [row for row in obs if _component_value(row, component) is not None]


def _quantile_buckets(obs: list[dict[str, Any]], component: str, n_buckets: int) -> list[list[dict[str, Any]]]:
    ordered = sorted(obs, key=lambda row: (_component_value(row, component), row["ticker"]))
    total = len(ordered)
    return [
        ordered[(i * total) // n_buckets : ((i + 1) * total) // n_buckets]
        for i in range(n_buckets)
    ]


def _bucket_stats(bucket: list[dict[str, Any]], component: str, horizon: int) -> dict[str, Any]:
    rets = [row["forward_returns"][horizon] for row in bucket if horizon in row["forward_returns"]]
    scores = [_component_value(row, component) for row in bucket]
    clean_scores = [score for score in scores if score is not None]
    if not rets:
        return {"obs": 0, "avg_return": None, "median_return": None, "win_rate": None}
    pos = sorted((ret for ret in rets if ret > 0), reverse=True)
    pos_total = sum(pos)
    top5_share = round(sum(pos[:5]) / pos_total, 4) if pos_total > 0 else None
    return {
        "obs": len(rets),
        "avg_return": round(sum(rets) / len(rets), 6),
        "median_return": round(statistics.median(rets), 6),
        "win_rate": round(sum(1 for ret in rets if ret > 0) / len(rets), 4),
        "top5_positive_share": top5_share,
        "component_score_lo": round(min(clean_scores), 6) if clean_scores else None,
        "component_score_hi": round(max(clean_scores), 6) if clean_scores else None,
    }


def component_quantile_attribution(
    observations: list[dict[str, Any]],
    component: str,
    n_buckets: int = QUINTILE,
) -> dict[str, Any]:
    obs = _component_obs(observations, component)
    buckets = _quantile_buckets(obs, component, n_buckets) if obs else [[] for _ in range(n_buckets)]
    per_bucket = []
    for i, bucket in enumerate(buckets):
        entry = {"bucket": f"q_{i + 1}", "n_obs": len(bucket)}
        for horizon in FORWARD_HORIZONS:
            entry[f"h{horizon}"] = _bucket_stats(bucket, component, horizon)
        per_bucket.append(entry)

    spreads: dict[str, float | None] = {}
    monotonic: dict[str, bool] = {}
    for horizon in FORWARD_HORIZONS:
        avgs = [bucket[f"h{horizon}"]["avg_return"] for bucket in per_bucket]
        top, bottom = avgs[-1], avgs[0]
        spreads[f"h{horizon}"] = (
            round(top - bottom, 6) if top is not None and bottom is not None else None
        )
        clean = all(avg is not None for avg in avgs)
        monotonic[f"h{horizon}"] = bool(
            clean and all(avgs[i + 1] >= avgs[i] for i in range(len(avgs) - 1))
        )

    values = [_component_value(row, component) for row in obs]
    clean_values = [value for value in values if value is not None]
    rounded_unique = {round(value, 8) for value in clean_values}
    return {
        "component": component,
        "observations": len(obs),
        "unique_component_score_count": len(rounded_unique),
        "component_score_lo": round(min(clean_values), 6) if clean_values else None,
        "component_score_hi": round(max(clean_values), 6) if clean_values else None,
        "buckets": per_bucket,
        "top_minus_bottom_spread": spreads,
        "monotonic_increasing_ladder": monotonic,
    }


def aggregate(per_window_obs: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    pooled: list[dict[str, Any]] = []
    for observations in per_window_obs.values():
        pooled.extend(observations)

    components: dict[str, Any] = {}
    for component in COMPONENTS:
        pooled_attr = component_quantile_attribution(pooled, component)
        per_window_5d_spread: dict[str, float | None] = {}
        per_window_monotonic_5d: dict[str, bool] = {}
        for window, observations in per_window_obs.items():
            attr = component_quantile_attribution(observations, component)
            per_window_5d_spread[window] = attr["top_minus_bottom_spread"].get(f"h{PRIMARY_HORIZON}")
            per_window_monotonic_5d[window] = attr["monotonic_increasing_ladder"].get(
                f"h{PRIMARY_HORIZON}", False
            )
        components[component] = {
            "pooled_quintile": pooled_attr,
            "per_window_5d_top_minus_bottom_spread": per_window_5d_spread,
            "per_window_5d_monotonic_ladder": per_window_monotonic_5d,
        }

    return {
        "total_observations": len(pooled),
        "observations_by_window": {window: len(obs) for window, obs in per_window_obs.items()},
        "component_attribution": components,
    }


def judge_component(component: str, attr: dict[str, Any]) -> dict[str, Any]:
    pooled = attr["pooled_quintile"]
    min_bucket_obs = min((bucket["n_obs"] for bucket in pooled["buckets"]), default=0)
    unique_scores = pooled["unique_component_score_count"]
    spread_5d = pooled["top_minus_bottom_spread"].get(f"h{PRIMARY_HORIZON}")
    monotonic_5d = pooled["monotonic_increasing_ladder"].get(f"h{PRIMARY_HORIZON}", False)
    window_spreads = attr["per_window_5d_top_minus_bottom_spread"]
    positive_windows = sum(1 for value in window_spreads.values() if value is not None and value > 0)
    measured_windows = sum(1 for value in window_spreads.values() if value is not None)
    majority_positive = measured_windows > 0 and positive_windows > measured_windows / 2
    eligible = min_bucket_obs >= MIN_BUCKET_OBS and unique_scores >= MIN_UNIQUE_COMPONENT_SCORES
    statistical_pass = bool(
        eligible
        and spread_5d is not None
        and spread_5d >= EDGE_FLOOR
        and monotonic_5d
        and majority_positive
    )

    if not eligible:
        status = "insufficient_component_bucket_coverage"
    elif statistical_pass and component in EXISTING_OHLCV_COMPONENTS:
        status = "statistical_pass_existing_ohlcv_remix"
    elif statistical_pass:
        status = "statistical_pass_component_candidate"
    elif spread_5d is not None and spread_5d >= EDGE_FLOOR and majority_positive:
        status = "top_bottom_edge_without_clean_ladder"
    elif spread_5d is not None and spread_5d <= -EDGE_FLOOR:
        status = "inverted_component_ladder"
    else:
        status = "no_component_edge"

    return {
        "component": component,
        "status": status,
        "eligible": eligible,
        "statistical_pass": statistical_pass,
        "existing_ohlcv_remix": component in EXISTING_OHLCV_COMPONENTS,
        "min_bucket_obs": min_bucket_obs,
        "unique_component_score_count": unique_scores,
        "pooled_5d_top_minus_bottom_spread": spread_5d,
        "pooled_5d_monotonic_ladder": monotonic_5d,
        "per_window_5d_spread": window_spreads,
        "positive_windows": positive_windows,
        "measured_windows": measured_windows,
    }


def judge(aggregate_payload: dict[str, Any]) -> dict[str, Any]:
    component_results = [
        judge_component(component, attr)
        for component, attr in aggregate_payload["component_attribution"].items()
    ]
    non_ohlcv_passes = [
        result for result in component_results
        if result["statistical_pass"] and not result["existing_ohlcv_remix"]
    ]
    ohlcv_passes = [
        result for result in component_results
        if result["statistical_pass"] and result["existing_ohlcv_remix"]
    ]
    edge_no_ladder = [
        result for result in component_results
        if result["status"] == "top_bottom_edge_without_clean_ladder"
    ]
    inverted = [
        result for result in component_results
        if result["status"] == "inverted_component_ladder"
    ]

    if non_ohlcv_passes:
        status = "observed_only_component_monotonic_candidate"
        realized_failure_mode = None
    elif ohlcv_passes:
        status = "observed_only_component_edge_existing_ohlcv_remix"
        realized_failure_mode = "component_edge_is_beta_or_trend_remix"
    elif edge_no_ladder:
        status = "observed_only_component_edge_without_clean_ladder"
        realized_failure_mode = "no_component_monotonic_ladder"
    elif inverted:
        status = "rejected_component_ladder_inverted"
        realized_failure_mode = "no_component_monotonic_ladder"
    else:
        status = "rejected_no_component_monotonic_ladder"
        realized_failure_mode = "no_component_monotonic_ladder"

    gate1 = {
        "name": "accepted_core_baseline_known_and_full_universe_observations_collected",
        "passed": aggregate_payload["total_observations"] > 0,
        "baseline": ACCEPTED_CORE_BASELINE,
        "total_observations": aggregate_payload["total_observations"],
        "observations_by_window": aggregate_payload["observations_by_window"],
    }
    gate2 = {
        "name": "component_fields_present_and_bucketable",
        "passed": any(result["eligible"] for result in component_results),
        "components": {
            result["component"]: {
                "min_bucket_obs": result["min_bucket_obs"],
                "unique_component_score_count": result["unique_component_score_count"],
                "eligible": result["eligible"],
            }
            for result in component_results
        },
    }
    gate3 = {
        "name": "survival_rate_not_affected_read_only_attribution",
        "passed": True,
        "adds_filter": False,
        "candidate_pool_changed": False,
    }
    gate4 = {
        "name": "component_level_full_universe_monotonicity",
        "passed": bool(non_ohlcv_passes),
        "status": status,
        "decision_rule": (
            "Observed-only pass requires at least one existing non-OHLCV component "
            "to show pooled 5d top-bottom spread >= 0.005, a monotonic quintile "
            "ladder, 2 of 3 positive windows, and every quintile >= 30 observations. "
            "Trend/relative_strength passes are explicitly treated as existing "
            "OHLCV remix evidence, not a new promotable alpha source."
        ),
        "component_results": component_results,
        "realized_failure_mode": realized_failure_mode,
    }
    return {
        "gate1": gate1,
        "gate2": gate2,
        "gate3": gate3,
        "gate4": gate4,
        "all_passed": bool(non_ohlcv_passes),
    }


def _component_table_lines(gates: dict[str, Any]) -> list[str]:
    lines = [
        "| Component | Status | 5d Q5-Q1 | Monotonic | Positive windows | Min bucket obs | Unique scores |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for result in gates["gate4"]["component_results"]:
        spread = result["pooled_5d_top_minus_bottom_spread"]
        spread_text = "n/a" if spread is None else f"{spread:.4f}"
        lines.append(
            "| {component} | {status} | {spread} | {mono} | {pos}/{measured} | {obs} | {uniq} |".format(
                component=result["component"],
                status=result["status"],
                spread=spread_text,
                mono=str(result["pooled_5d_monotonic_ladder"]),
                pos=result["positive_windows"],
                measured=result["measured_windows"],
                obs=result["min_bucket_obs"],
                uniq=result["unique_component_score_count"],
            )
        )
    return lines


def _build_log_record(payload: dict[str, Any], timestamp: str) -> dict[str, Any]:
    gates = payload["gates"]
    gate4 = gates["gate4"]
    after_metrics = {
        "accepted_core_expected_value_score_sum": ACCEPTED_CORE_BASELINE[
            "accepted_core_expected_value_score_sum"
        ],
        "accepted_core_total_pnl_sum": ACCEPTED_CORE_BASELINE["accepted_core_total_pnl_sum"],
        "strategy_behavior_changed": False,
        "total_observations": payload["aggregate"]["total_observations"],
        "observations_by_window": payload["aggregate"]["observations_by_window"],
        "gate4_status": gate4["status"],
        "component_results": gate4["component_results"],
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": "observed_only" if not gate4["status"].startswith("rejected") else "rejected",
        "decision": gate4["status"],
        "lane": "alpha_search",
        "hypothesis": (
            "Existing alpha_score components may reveal a durable full-universe "
            "monotonic ranking ladder even though the composite alpha_score failed "
            "clean monotonicity."
        ),
        "change_summary": (
            "Read-only decomposition of the existing full-universe PIT alpha_score "
            "sample by component quintile forward returns across the canonical three windows."
        ),
        "change_type": "read_only_full_universe_component_forward_return_attribution",
        "mechanism_family": "continuous_cross_sectional_ranking",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": RULE_VERSION,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "prior_trial_count": 7,
        "nearby_prior_experiments": [
            "exp-20260530-022",
            "exp-20260531-005",
            "exp-20260531-006",
            "exp-20260531-007",
            "exp-20260531-008",
            "exp-20260531-009",
            "exp-20260531-011",
            "exp-20260531-014",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "component_level_full_universe_quantile_forward_return",
        "component": "quant/experiments/exp_20260531_017_full_universe_alpha_score_component_forward_return.py",
        "date_range": {window: f"{start} -> {end}" for window, (start, end, _) in WINDOWS.items()},
        "before_metrics": {
            **ACCEPTED_CORE_BASELINE,
            "strategy_behavior_changed": False,
        },
        "after_metrics": after_metrics,
        "delta_metrics": {
            "expected_value_score_delta": 0.0,
            "total_pnl_delta": 0.0,
            "strategy_behavior_delta": 0,
        },
        "gate1": gates["gate1"],
        "gate2": gates["gate2"],
        "gate3": gates["gate3"],
        "gate4": gates["gate4"],
        "gate_questions": {
            "1_alpha_hypothesis": (
                "Existing alpha_score components may show durable full-universe "
                "monotonic forward-return evidence where the composite score did not."
            ),
            "2_history_check": (
                "exp-20260531-006 found composite top-bottom edge but no clean ladder; "
                "exp-20260531-005/007/008/009/011/014 failed candidate-pool or state-gate promotion."
            ),
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": gate4["decision_rule"],
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260531_017_full_universe_alpha_score_component_forward_return.py "
                "--write-records"
            ),
        },
        "parameters": {
            "anti_js": "No JavaScript was used.",
            "components": list(COMPONENTS),
            "existing_ohlcv_components": sorted(EXISTING_OHLCV_COMPONENTS),
            "sample_step_trading_days": SAMPLE_STEP,
            "forward_horizons": list(FORWARD_HORIZONS),
            "primary_horizon": PRIMARY_HORIZON,
            "quintile": QUINTILE,
            "min_bucket_obs": MIN_BUCKET_OBS,
            "min_unique_component_scores": MIN_UNIQUE_COMPONENT_SCORES,
            "edge_floor": EDGE_FLOOR,
        },
        "prediction": {
            "success_probability": 0.25,
            "expected_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "main_failure_modes": [
                "no_component_monotonic_ladder",
                "one_window_negative",
                "component_edge_is_beta_or_trend_remix",
                "top_bucket_concentration",
            ],
            "confidence_reason": (
                "Composite alpha_score had a small top-vs-bottom edge but no clean ladder; "
                "decomposing existing components is evidence-dense and avoids adding features."
            ),
        },
        "calibration": {
            "actual_decision": gate4["status"],
            "actual_success": 1 if gates["all_passed"] else 0,
            "predicted_success_probability": 0.25,
            "brier_score": 0.0625 if not gates["all_passed"] else 0.5625,
            "calibration_direction": "directionally_calibrated" if not gates["all_passed"] else "underconfident",
            "realized_failure_mode": gate4.get("realized_failure_mode"),
            "predicted_failure_mode_hit": gate4.get("realized_failure_mode")
            in {
                "no_component_monotonic_ladder",
                "one_window_negative",
                "component_edge_is_beta_or_trend_remix",
                "top_bucket_concentration",
            },
        },
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "read_only_attribution": True,
            "trade_enabled": False,
        },
        "rejection_reason": (
            None if gates["all_passed"] else gate4.get("realized_failure_mode") or gate4["status"]
        ),
        "next_retry_requires": [
            "Do not promote raw alpha_score top-N, score weights, or component gates from this run alone.",
            "A valid retry needs non-OHLCV component monotonicity, replacement value versus same-day alternatives, and regime/cost controls.",
        ],
        "related_files": [
            "quant/experiments/exp_20260531_017_full_universe_alpha_score_component_forward_return.py",
            "quant/test_exp_20260531_017_full_universe_component_forward_return.py",
            "data/experiments/exp-20260531-017/exp_20260531_017_full_universe_alpha_score_component_forward_return.json",
            "experiments/artifacts/exp-20260531-017_full_universe_alpha_score_component_forward_return.md",
            "experiments/logs/exp-20260531-017.json",
            "experiments/tickets/exp-20260531-017.json",
            "docs/experiment_log.jsonl",
        ],
        "anti_js": "No JavaScript was used.",
    }


def _write_artifact(log_record: dict[str, Any]) -> None:
    lines = [
        f"# {EXPERIMENT_ID} {STEM}",
        "",
        f"- timestamp: {log_record['timestamp']}",
        f"- decision: `{log_record['decision']}`",
        "- strategy impact: none; read-only attribution only",
        "- baseline: accepted core aggregate EV `7.8941`, PnL `$234,850.99`",
        "- windows: `late_strong`, `mid_weak`, `old_thin` from `docs/backtesting.md`",
        "",
        "## Component Readout",
        "",
        *_component_table_lines(log_record),
        "",
        "## Interpretation",
        "",
        (
            "This experiment decomposes an existing ranking surface. It does not add "
            "a new information source and does not justify any production ranking, "
            "sizing, entry, exit, LLM prompt, paper sleeve, or order change by itself."
        ),
    ]
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_jsonl_once(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _write_records(payload: dict[str, Any], log_record: dict[str, Any]) -> None:
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    LOG_JSON.write_text(json.dumps(log_record, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    _write_artifact(log_record)
    _append_jsonl_once(EXPERIMENT_LOG, log_record)

    if CARD_MD.exists():
        card = CARD_MD.read_text(encoding="utf-8")
        if "## Result" not in card:
            CARD_MD.write_text(
                card.rstrip()
                + "\n\n## Result\n\n"
                + f"- decision: `{log_record['decision']}`\n"
                + "- summary: read-only component monotonicity attribution completed.\n",
                encoding="utf-8",
            )


def run(
    output: Path = OUT_JSON,
    *,
    snapshot_dir: Path | None = None,
    write_records: bool = False,
) -> dict[str, Any]:
    snapshot_dir = snapshot_dir or (REPO_ROOT / "data" / "ohlcv")
    per_window_obs: dict[str, list[dict[str, Any]]] = {}
    for window, (start, end, snapshot) in WINDOWS.items():
        ohlcv = load_ohlcv_snapshot(str(snapshot_dir / snapshot))
        per_window_obs[window] = collect_observations(ohlcv, start, end)

    aggregate_payload = aggregate(per_window_obs)
    gates = judge(aggregate_payload)
    timestamp = utc_now()
    payload = {
        "anti_js": "No JavaScript was used.",
        "experiment_id": EXPERIMENT_ID,
        "rule_version": RULE_VERSION,
        "decision": gates["gate4"]["status"],
        "windows": {window: {"start": start, "end": end} for window, (start, end, _) in WINDOWS.items()},
        "sample_step_trading_days": SAMPLE_STEP,
        "forward_horizons": list(FORWARD_HORIZONS),
        "components": list(COMPONENTS),
        "accepted_core_baseline": ACCEPTED_CORE_BASELINE,
        "aggregate": aggregate_payload,
        "gates": gates,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    log_record = _build_log_record(payload, timestamp)
    if write_records:
        _write_records(payload, log_record)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT_JSON)
    parser.add_argument("--write-records", action="store_true")
    args = parser.parse_args()

    result = run(args.output, write_records=args.write_records)
    summary = {
        "anti_js": result["anti_js"],
        "experiment_id": result["experiment_id"],
        "decision": result["decision"],
        "total_observations": result["aggregate"]["total_observations"],
        "observations_by_window": result["aggregate"]["observations_by_window"],
        "component_statuses": {
            row["component"]: row["status"]
            for row in result["gates"]["gate4"]["component_results"]
        },
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
