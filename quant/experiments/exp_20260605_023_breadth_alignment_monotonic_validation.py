"""exp-20260605-023: breadth_alignment monotonic validation.

This read-only alpha-search experiment asks whether the existing
``breadth_alignment`` component in the continuous cross-sectional ranking
surface has enough durable, monotonic broad-universe evidence to justify
remaining an alpha-bearing ranking input.

It changes no production policy, backtest policy, ranking, sizing, exits,
paper sleeves, LLM/news inputs, reports, watchlists, or orders.

No JavaScript was used.
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
for _path in (REPO_ROOT / "quant", REPO_ROOT / "quant" / "experiments"):
    text = str(_path)
    if text not in sys.path:
        sys.path.insert(0, text)

from exp_20260601_003_alpha_score_component_decomposition_forward_return import (  # noqa: E402
    EDGE_FLOOR,
    PRIMARY_HORIZON,
    _component_dispersion,
    _conditional_spread_vs_rs,
)
from exp_20260601_006_broad_universe_alpha_score_ranking_validation import (  # noqa: E402
    FORWARD_HORIZONS,
    SAMPLE_STEP,
    WAREHOUSE,
    WINDOWS,
    collect_observations,
    load_warehouse_frames,
)


EXPERIMENT_ID = "exp-20260605-023"
STEM = "breadth_alignment_monotonic_validation"
RULE_VERSION = "breadth_alignment_existing_component_monotonic_validation_v1"
COMPONENT = "breadth_alignment"
TRIAL_FAMILY = "breadth_alignment_component_monotonic_validation"
CHANGED_VARIABLE = "breadth_alignment_existing_component_score"
BASELINE_FILE = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260602-003"
    / "exp_20260602_003_post_earnings_explicit_continuation.json"
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260605_023_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

N_BUCKETS = 5
MIN_BUCKET_OBS = 30
MIN_MONOTONIC_WINDOWS = 2


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _repo_rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_head() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    return result.stdout.strip() or None


def _safe_float(value: Any) -> float | None:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if value != value:
        return None
    return value


def _bucket_stats(bucket: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    pairs: list[tuple[float, float]] = []
    for row in bucket:
        score = _safe_float((row.get("components") or {}).get(COMPONENT))
        ret = _safe_float((row.get("forward_returns") or {}).get(horizon))
        if score is not None and ret is not None:
            pairs.append((score, ret))
    if not pairs:
        return {
            "obs": 0,
            "avg_return": None,
            "median_return": None,
            "win_rate": None,
            "component_min": None,
            "component_max": None,
        }
    returns = [ret for _score, ret in pairs]
    scores = [score for score, _ret in pairs]
    return {
        "obs": len(pairs),
        "avg_return": round(sum(returns) / len(returns), 6),
        "median_return": round(statistics.median(returns), 6),
        "win_rate": round(sum(1 for ret in returns if ret > 0) / len(returns), 4),
        "component_min": round(min(scores), 6),
        "component_max": round(max(scores), 6),
    }


def _component_buckets(
    observations: list[dict[str, Any]],
    *,
    n_buckets: int = N_BUCKETS,
) -> list[list[dict[str, Any]]]:
    scored = [
        row
        for row in observations
        if _safe_float((row.get("components") or {}).get(COMPONENT)) is not None
    ]
    ordered = sorted(scored, key=lambda row: float(row["components"][COMPONENT]))
    total = len(ordered)
    return [
        ordered[(i * total) // n_buckets : ((i + 1) * total) // n_buckets]
        for i in range(n_buckets)
    ]


def _quantile_ladder(observations: list[dict[str, Any]]) -> dict[str, Any]:
    buckets = _component_buckets(observations)
    per_bucket: list[dict[str, Any]] = []
    for idx, bucket in enumerate(buckets, start=1):
        node: dict[str, Any] = {
            "bucket": f"q{idx}",
            "n_obs": len(bucket),
        }
        for horizon in FORWARD_HORIZONS:
            node[f"h{horizon}"] = _bucket_stats(bucket, horizon)
        per_bucket.append(node)

    spreads: dict[str, Any] = {}
    monotonic: dict[str, bool] = {}
    for horizon in FORWARD_HORIZONS:
        avgs = [node[f"h{horizon}"]["avg_return"] for node in per_bucket]
        top = avgs[-1] if avgs else None
        bottom = avgs[0] if avgs else None
        spreads[f"h{horizon}"] = (
            round(top - bottom, 6)
            if top is not None and bottom is not None
            else None
        )
        monotonic[f"h{horizon}"] = bool(
            avgs
            and all(avg is not None for avg in avgs)
            and all(avgs[i + 1] >= avgs[i] for i in range(len(avgs) - 1))
        )
    min_bucket_obs = min((node["n_obs"] for node in per_bucket), default=0)
    return {
        "buckets": per_bucket,
        "top_minus_bottom_spread": spreads,
        "monotonic_increasing_ladder": monotonic,
        "min_bucket_obs": min_bucket_obs,
    }


def _baseline_metrics() -> dict[str, Any]:
    baseline = _read_json(BASELINE_FILE)
    current_by_window: dict[str, Any] = {}
    for label, node in (baseline.get("by_window") or {}).items():
        current_by_window[label] = node.get("after") or {}
    return {
        "source": _repo_rel(BASELINE_FILE),
        "aggregate": (baseline.get("aggregate") or {}).get("after") or {},
        "by_window": current_by_window,
    }


def _field_coverage(observations: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(observations)
    with_component = sum(
        1
        for row in observations
        if _safe_float((row.get("components") or {}).get(COMPONENT)) is not None
    )
    with_fwd5 = sum(
        1
        for row in observations
        if _safe_float((row.get("forward_returns") or {}).get(PRIMARY_HORIZON)) is not None
    )
    return {
        "total_observations": total,
        "breadth_component_present": with_component,
        "breadth_component_coverage_ratio": round(with_component / total, 6) if total else 0.0,
        "forward_5d_present": with_fwd5,
        "forward_5d_coverage_ratio": round(with_fwd5 / total, 6) if total else 0.0,
    }


def _judge(
    baseline: dict[str, Any],
    pooled_ladder: dict[str, Any],
    per_window: dict[str, dict[str, Any]],
    dispersion: dict[str, Any],
    residual_vs_rs: float | None,
    field_coverage: dict[str, Any],
) -> dict[str, Any]:
    baseline_by_window = baseline.get("by_window") or {}
    survival_rates = {
        label: node.get("survival_rate")
        for label, node in baseline_by_window.items()
        if node.get("survival_rate") is not None
    }
    min_survival_rate = min(survival_rates.values()) if survival_rates else None
    per_window_primary = {
        label: node["top_minus_bottom_spread"].get(f"h{PRIMARY_HORIZON}")
        for label, node in per_window.items()
    }
    per_window_monotonic = {
        label: node["monotonic_increasing_ladder"].get(f"h{PRIMARY_HORIZON}", False)
        for label, node in per_window.items()
    }
    positive_windows = sum(
        1 for value in per_window_primary.values() if value is not None and value > 0
    )
    monotonic_windows = sum(1 for value in per_window_monotonic.values() if value)
    pooled_primary = pooled_ladder["top_minus_bottom_spread"].get(f"h{PRIMARY_HORIZON}")
    pooled_monotonic = pooled_ladder["monotonic_increasing_ladder"].get(
        f"h{PRIMARY_HORIZON}", False
    )

    failed_reasons: list[str] = []
    if field_coverage["breadth_component_coverage_ratio"] < 0.99:
        failed_reasons.append("breadth_component_incomplete")
    if pooled_ladder["min_bucket_obs"] < MIN_BUCKET_OBS:
        failed_reasons.append("bucket_obs_floor_failed")
    if pooled_primary is None or pooled_primary < EDGE_FLOOR:
        failed_reasons.append("pooled_5d_edge_below_floor")
    if residual_vs_rs is None or residual_vs_rs < EDGE_FLOOR:
        failed_reasons.append("rs_controlled_residual_edge_below_floor")
    if monotonic_windows < MIN_MONOTONIC_WINDOWS:
        failed_reasons.append("insufficient_monotonic_windows")
    if positive_windows < MIN_MONOTONIC_WINDOWS:
        failed_reasons.append("insufficient_positive_windows")
    if not pooled_monotonic:
        failed_reasons.append("pooled_ladder_not_monotonic")
    if not dispersion.get("cross_sectional"):
        failed_reasons.append("market_timing_not_cross_sectional")

    passed = not failed_reasons
    decision = (
        "observed_only_breadth_alignment_monotonic_edge"
        if passed
        else "rejected_breadth_alignment_component_edge"
    )
    return {
        "gate1": {
            "name": "canonical_three_window_baseline_loaded",
            "passed": bool(baseline.get("aggregate") and baseline_by_window),
            "baseline_source": baseline.get("source"),
            "baseline_aggregate": baseline.get("aggregate"),
            "baseline_by_window": baseline_by_window,
        },
        "gate2": {
            "name": "existing_component_field_reality",
            "passed": field_coverage["breadth_component_coverage_ratio"] >= 0.99,
            "field_coverage": field_coverage,
            "runtime_fields": [
                "warehouse OHLCV rows up to as-of date",
                "cross_sectional_ranking_surface.components.breadth_alignment",
                "forward close-to-close returns for observed-only attribution",
            ],
        },
        "gate3": {
            "name": "read_only_survival_audit",
            "passed": min_survival_rate is not None and min_survival_rate >= 0.05,
            "baseline_survival_rates": survival_rates,
            "min_survival_rate": min_survival_rate,
            "notes": "No filter, entry, sizing, or ranking behavior changed.",
        },
        "gate4": {
            "name": "breadth_alignment_monotonic_edge",
            "passed": passed,
            "decision": decision,
            "failed_reasons": failed_reasons,
            "edge_floor": EDGE_FLOOR,
            "primary_horizon": PRIMARY_HORIZON,
            "pooled_5d_top_minus_bottom": pooled_primary,
            "pooled_5d_monotonic": pooled_monotonic,
            "per_window_5d_top_minus_bottom": per_window_primary,
            "per_window_5d_monotonic": per_window_monotonic,
            "positive_windows": positive_windows,
            "monotonic_windows": monotonic_windows,
            "min_required_positive_windows": MIN_MONOTONIC_WINDOWS,
            "min_required_monotonic_windows": MIN_MONOTONIC_WINDOWS,
            "residual_5d_spread_vs_relative_strength": residual_vs_rs,
            "dispersion": dispersion,
            "decision_rule": (
                "Accept observed-only only if pooled 5d top-minus-bottom >= "
                "0.005, residual 5d spread after relative-strength control >= "
                "0.005, the pooled 5d bucket ladder is monotonic, and at least "
                "2/3 windows are both positive and monotonic. No production "
                "behavior can change from this observed-only result."
            ),
        },
        "all_passed": passed,
    }


def run() -> dict[str, Any]:
    started = _utc_now()
    frames = load_warehouse_frames(WAREHOUSE)
    per_window_obs: dict[str, list[dict[str, Any]]] = {}
    for label, (start, end) in WINDOWS.items():
        per_window_obs[label] = collect_observations(frames, start, end)
    pooled = [row for rows in per_window_obs.values() for row in rows]

    baseline = _baseline_metrics()
    pooled_ladder = _quantile_ladder(pooled)
    per_window_ladders = {
        label: _quantile_ladder(rows) for label, rows in per_window_obs.items()
    }
    dispersion = _component_dispersion(pooled, COMPONENT)
    residual_vs_rs = _conditional_spread_vs_rs(pooled, COMPONENT, PRIMARY_HORIZON)
    coverage = _field_coverage(pooled)
    gates = _judge(
        baseline,
        pooled_ladder,
        per_window_ladders,
        dispersion,
        residual_vs_rs,
        coverage,
    )
    actual_success = 1 if gates["all_passed"] else 0
    prediction = {
        "success_probability": 0.18,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "market_timing_not_cross_sectional",
            "not_monotonic",
            "rs_collinear",
            "edge_below_floor",
        ],
        "confidence_reason": (
            "Breadth alignment is an approved canonical vector, but broad "
            "universe alpha_score validation already found weak non-momentum "
            "component evidence; this is evidence-density validation."
        ),
        "recorded_at": "2026-06-05T16:03:37+00:00",
        "actual_success": actual_success,
        "brier_score": round((0.18 - actual_success) ** 2, 6),
    }
    decision = gates["gate4"]["decision"]
    payload = {
        "anti_js": "No JavaScript was used.",
        "experiment_id": EXPERIMENT_ID,
        "timestamp": _utc_now(),
        "started_at": started,
        "status": "observed_only" if gates["all_passed"] else "rejected",
        "lane": "alpha_search",
        "decision": decision,
        "accepted": False,
        "hypothesis": (
            "Existing breadth_alignment component should show durable monotonic "
            "broad-universe forward-return evidence before it remains a "
            "continuous ranking input."
        ),
        "change_summary": (
            "Validated the existing breadth_alignment component against "
            "broad-universe 5/10/20d forward returns without changing policy."
        ),
        "change_type": "read_only_broad_universe_component_monotonic_validation",
        "mechanism_family": "continuous_cross_sectional_ranking_system",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": "breadth_alignment_existing_component_broad_universe_v1",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": RULE_VERSION,
        "prior_trial_count": 1,
        "nearby_prior_experiments": [
            "exp-20260601-006",
            "exp-20260604-016",
            "exp-20260605-013",
        ],
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": "existing_canonical_component_broad_universe_monotonic_validation",
        "component": "quant/cross_sectional_ranking_surface.py",
        "parameters": {
            "component": COMPONENT,
            "universe": "exp-20260519-030 warehouse all_windows_full_liquid",
            "warehouse": _repo_rel(WAREHOUSE),
            "universe_size": len(frames),
            "sample_step_trading_days": SAMPLE_STEP,
            "forward_horizons": list(FORWARD_HORIZONS),
            "bucket_count": N_BUCKETS,
            "primary_horizon": PRIMARY_HORIZON,
            "edge_floor": EDGE_FLOOR,
            "min_bucket_obs": MIN_BUCKET_OBS,
            "acceptance_rule": gates["gate4"]["decision_rule"],
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three fixed windows; read-only ranking attribution, no strategy after-metrics",
            "baseline_file": _repo_rel(BASELINE_FILE),
            "windows": {
                label: {"start": start, "end": end}
                for label, (start, end) in WINDOWS.items()
            },
            "replay_llm": False,
            "replay_news": False,
            "strategy_behavior_changed": False,
        },
        "baseline_metrics": baseline,
        "observed_metrics": {
            "total_observations": len(pooled),
            "observations_by_window": {
                label: len(rows) for label, rows in per_window_obs.items()
            },
            "pooled_ladder": pooled_ladder,
            "per_window_ladders": per_window_ladders,
            "dispersion": dispersion,
            "residual_5d_spread_vs_relative_strength": residual_vs_rs,
        },
        "gates": gates,
        "prediction": prediction,
        "calibration": {
            "actual_decision": decision,
            "actual_success": actual_success,
            "predicted_success_probability": prediction["success_probability"],
            "brier_score": prediction["brier_score"],
            "predicted_failure_modes": prediction["main_failure_modes"],
            "realized_failure_modes": gates["gate4"]["failed_reasons"],
            "predicted_failure_mode_hit": bool(
                set(prediction["main_failure_modes"]) & set(gates["gate4"]["failed_reasons"])
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "read_only_attribution": True,
            "parity_test_added": False,
            "production_orders_changed": False,
            "production_watchlist_changed": False,
            "core_ranking_changed": False,
            "sizing_changed": False,
            "exits_changed": False,
            "trade_enabled": False,
            "parity_note": (
                "No executable behavior changed, so no production/backtest "
                "divergence was introduced. A future promotion would require "
                "a separate shared ranking policy and parity tests."
            ),
        },
        "interpretation": (
            "Reject breadth_alignment as a standalone alpha-bearing component "
            "for now if Gate 4 fails; keep it read-only/contextual until new "
            "forward or broader participation-quality evidence clears "
            "monotonic and RS-controlled gates."
        ),
        "rejection_reason": ";".join(gates["gate4"]["failed_reasons"])
        if not gates["all_passed"]
        else None,
        "next_retry_requires": [
            "new forward rows or a materially different participation-quality source",
            "monotonic bucket ladder across at least two canonical windows",
            "5d top-minus-bottom and RS-controlled residual spreads above 50bp",
            "shared production/backtest ranking policy before any strategy use",
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(TICKET_JSON),
        ],
    }
    return payload


def _build_artifact(payload: dict[str, Any]) -> str:
    gate4 = payload["gates"]["gate4"]
    rows = [
        "| Window | Obs | 5d Q5-Q1 | 5d monotonic | 10d Q5-Q1 | 20d Q5-Q1 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, ladder in payload["observed_metrics"]["per_window_ladders"].items():
        rows.append(
            "| {label} | {obs} | {h5} | {mono} | {h10} | {h20} |".format(
                label=label,
                obs=sum(bucket["n_obs"] for bucket in ladder["buckets"]),
                h5=ladder["top_minus_bottom_spread"].get("h5"),
                mono=ladder["monotonic_increasing_ladder"].get("h5"),
                h10=ladder["top_minus_bottom_spread"].get("h10"),
                h20=ladder["top_minus_bottom_spread"].get("h20"),
            )
        )
    pooled = payload["observed_metrics"]["pooled_ladder"]
    baseline = payload["baseline_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Breadth Alignment Monotonic Validation",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 1 Baseline",
            "",
            f"- baseline artifact: `{payload['baseline_metrics']['source']}`",
            f"- aggregate EV: `{baseline.get('expected_value_score')}`",
            f"- aggregate PnL: `${baseline.get('total_pnl')}`",
            f"- min survival: `{baseline.get('min_survival_rate')}`",
            f"- max drawdown: `{baseline.get('max_drawdown_pct')}`",
            "",
            "## Observed Ladder",
            "",
            *rows,
            "",
            "## Pooled",
            "",
            f"- observations: `{payload['observed_metrics']['total_observations']}`",
            f"- pooled 5d Q5-Q1: `{pooled['top_minus_bottom_spread'].get('h5')}`",
            f"- pooled 5d monotonic: `{pooled['monotonic_increasing_ladder'].get('h5')}`",
            f"- RS-controlled 5d residual spread: `{payload['observed_metrics']['residual_5d_spread_vs_relative_strength']}`",
            f"- within-day variance share: `{payload['observed_metrics']['dispersion'].get('within_day_variance_share')}`",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(gate4, indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "Read-only attribution only. No shared policy, run adapter, backtester adapter, ranking, sizing, exits, watchlists, reports, paper sleeves, LLM/news path, or orders changed.",
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def _experiment_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": payload["experiment_id"],
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "lane": payload["lane"],
        "hypothesis": payload["hypothesis"],
        "change_summary": payload["change_summary"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "component": payload["component"],
        "parameters": payload["parameters"],
        "date_range": {"start": "2025-10-23", "end": "2026-04-21"},
        "secondary_windows": [
            {"start": "2025-04-23", "end": "2025-10-22"},
            {"start": "2024-10-02", "end": "2025-04-22"},
        ],
        "before_metrics": payload["baseline_metrics"],
        "after_metrics": payload["observed_metrics"],
        "delta_metrics": {
            "strategy_behavior_changed": False,
            "expected_value_score_delta": 0.0,
            "total_pnl_delta": 0.0,
            "observed_pooled_5d_q5_q1": payload["observed_metrics"]["pooled_ladder"][
                "top_minus_bottom_spread"
            ].get("h5"),
            "observed_residual_5d_vs_rs": payload["observed_metrics"][
                "residual_5d_spread_vs_relative_strength"
            ],
        },
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
        "decision": payload["decision"],
        "rejection_reason": payload["rejection_reason"],
        "next_retry_requires": payload["next_retry_requires"],
        "related_files": payload["related_files"],
        "anti_js": payload["anti_js"],
    }


def _persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    artifact = _build_artifact(payload)
    _write_text(ARTIFACT_MD, artifact)
    _write_text(CARD_MD, artifact)

    ticket = _read_json(TICKET_JSON) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "result": {
                "decision": payload["decision"],
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "summary": payload["interpretation"],
                "rejection_reason": payload["rejection_reason"],
            },
        }
    )
    _write_json(TICKET_JSON, ticket)

    with EXPERIMENT_LOG_JSONL.open("a", encoding="utf-8") as handle:
        json.dump(_experiment_log_record(payload), handle, ensure_ascii=False, sort_keys=True)
        handle.write("\n")

    files = {
        "runner": Path(__file__),
        "result": OUT_JSON,
        "log": LOG_JSON,
        "ticket": TICKET_JSON,
        "card": CARD_MD,
        "artifact": ARTIFACT_MD,
        "manifest": MANIFEST_JSON,
    }
    manifest = {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_revision_manifest",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": _utc_now(),
        "git_head": _git_head(),
        "files": {
            label: {
                "path": _repo_rel(path),
                "exists": path.exists(),
                "sha256": _sha256(path),
            }
            for label, path in files.items()
        },
    }
    _write_json(MANIFEST_JSON, manifest)


def main() -> int:
    payload = run()
    _persist(payload)
    summary = {
        "anti_js": payload["anti_js"],
        "experiment_id": payload["experiment_id"],
        "decision": payload["decision"],
        "observations": payload["observed_metrics"]["total_observations"],
        "pooled_5d_top_minus_bottom": payload["gates"]["gate4"][
            "pooled_5d_top_minus_bottom"
        ],
        "pooled_5d_monotonic": payload["gates"]["gate4"]["pooled_5d_monotonic"],
        "residual_5d_spread_vs_relative_strength": payload["gates"]["gate4"][
            "residual_5d_spread_vs_relative_strength"
        ],
        "failed_reasons": payload["gates"]["gate4"]["failed_reasons"],
        "artifact": _repo_rel(ARTIFACT_MD),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
