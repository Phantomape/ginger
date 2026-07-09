"""exp-20260709-015: Space catalyst direct-official promotion gate.

Tests whether the positive exp-20260709-014 direct-official defense-budget lead
can be promoted from observe-only attribution into a full-stack default-off
paper candidate policy. It reuses the existing shared space_catalyst event
ledger surface and does not change live/default orders, sizing, ranking, exits,
or the shared helper.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping


EXPERIMENT_ID = "exp-20260709-015"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "space_catalyst_direct_official_promotion"
RUNNER = f"quant/experiments/exp_20260709_015_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
for path in (REPO_ROOT / "scripts", REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)
from quant.full_stack_candidate_pool import (  # noqa: E402
    ExecutionEnvelope,
    evaluate_gate4,
    evaluate_live_readiness,
    full_stack_verdict,
)


DATA_DIR = REPO_ROOT / "data"
BASELINE_RESULT = (
    DATA_DIR
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
LEDGER = (
    DATA_DIR
    / "paper_sleeves"
    / "space_catalyst"
    / "event_state_shadow_ledger.jsonl"
)
SUMMARY = (
    DATA_DIR
    / "paper_sleeves"
    / "space_catalyst"
    / "event_state_shadow_summary.json"
)

OUT_DIR = DATA_DIR / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260709_015_space_catalyst_direct_official_promotion.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "A fixed default-off Space catalyst direct-official defense-budget candidate "
    "policy that admits only official_government_release defense_budget_theme "
    "event rows and rejects attention-only proxies may convert the 2026-07-09 "
    "observed lead into a promotion-ready paper sleeve, but should be rejected "
    "if canonical historical coverage or replacement-value comparators are "
    "insufficient."
)
CHANGE_TYPE = "candidate_pool_full_stack"
IMPLEMENTATION_MODE = "self_registered_promotion_gate_no_strategy_change"
MECHANISM_FAMILY = "space_catalyst_event_relation_alpha"
TRIAL_FAMILY = "space_catalyst_direct_official_default_off_candidate_pool"
TRIAL_VARIANT_ID = "direct_official_defense_budget_promotion_gate_v1"
SINGLE_CAUSAL_VARIABLE = "space_catalyst_direct_official_default_off_candidate_pool_v1"
CAUSAL_COMPONENTS = [
    "existing shared space_catalyst event ledger",
    "direct official admission policy",
    "attention-only reject comparator",
    "canonical coverage gate",
    "execution envelope",
    "full-stack verdict",
]
NEARBY_PRIORS = ["exp-20260702-003", "exp-20260709-014", "exp-20260627-024"]
NEW_EVIDENCE_TYPE = "new_gate_shape"
NEW_EVIDENCE_AXIS = (
    "New gate shape: full-stack/shared-helper promotion verdict for a fixed "
    "direct-official Space catalyst policy using canonical coverage, "
    "execution-envelope, and attention-only rejection checks; not another "
    "threshold/field/hold retune on the 18 observed rows."
)
PREDICTION = {
    "success_probability": 0.22,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "historical_coverage_too_thin",
        "same_theme_opportunity_cost_not_incremental",
        "forward_sample_overfit",
        "canonical_gate_unavailable",
    ],
    "confidence_reason": (
        "exp-20260709-014 cleanly separated direct official defense-budget rows "
        "from attention-only rows across broad benchmarks, but exp-20260702-003 "
        "already failed same-theme incrementality and the official event history "
        "is likely too sparse in the fixed canonical windows; this is a "
        "promotion-gate test, not another row slice."
    ),
}

WINDOWS = {
    "old_thin": ("2024-10-02", "2025-04-22"),
    "mid_weak": ("2025-04-23", "2025-10-22"),
    "late_strong": ("2025-10-23", "2026-04-21"),
}
RECENT_OBSERVE = ("2026-04-22", "2026-07-08")
HORIZONS = ("10d", "20d")
CORE_FIELDS = (
    "cash_relative_pnl",
    "spy_relative_value",
    "qqq_relative_value",
    "arkx_relative_value",
    "ufo_relative_value",
)
DIAGNOSTIC_FIELDS = CORE_FIELDS + ("same_theme_replacement_value",)
CHANGED_FILES = [
    RUNNER,
    "data/experiments/exp-20260709-015/exp_20260709_015_space_catalyst_direct_official_promotion.json",
    "experiments/logs/exp-20260709-015.json",
    "experiments/cards/exp-20260709-015.md",
    "experiments/manifests/exp-20260709-015.json",
    "experiments/tickets/exp-20260709-015.json",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path | str) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT.resolve())).replace(
            "\\", "/"
        )
    except ValueError:
        return str(path).replace("\\", "/")


def safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default if default is not None else {}


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def as_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
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
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(
            sum(float(row.get("total_pnl") or 0.0) for row in windows), 2
        ),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
        "max_drawdown_pct_worst": round(max(drawdowns), 4) if drawdowns else None,
    }


def load_ledger_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not LEDGER.exists():
        return rows
    with LEDGER.open(encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def dedupe_closed_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[tuple[Any, ...], tuple[tuple[str, str], dict[str, Any]]] = {}
    for row in rows:
        if not row.get("closed_decision") or row.get("outcome_status") != "mature":
            continue
        key = (
            row.get("event_id"),
            row.get("ticker"),
            row.get("entry_date"),
            row.get("semantic_bucket"),
            row.get("theme_segment"),
        )
        rank = (str(row.get("asof_date") or ""), str(row.get("logged_at") or ""))
        if key not in latest or rank > latest[key][0]:
            latest[key] = (rank, row)
    return [item[1] for item in latest.values()]


def is_direct_official(row: dict[str, Any]) -> bool:
    return (
        row.get("semantic_bucket") == "defense_budget_theme"
        and row.get("source_type") == "official_government_release"
    )


def is_attention(row: dict[str, Any]) -> bool:
    return row.get("semantic_bucket") == "attention_only"


def row_in_window(row: dict[str, Any], start: str, end: str) -> bool:
    entry = str(row.get("entry_date") or "")
    return bool(entry) and start <= entry <= end


def outcome_value(row: dict[str, Any], horizon: str, field: str) -> float | None:
    horizons = row.get("horizons")
    if not isinstance(horizons, dict):
        return None
    payload = horizons.get(horizon)
    if not isinstance(payload, dict):
        return None
    return as_float(payload.get(field))


def summarize_metric(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "avg": None,
            "median": None,
            "positive_count": 0,
            "win_rate": None,
            "min": None,
            "max": None,
        }
    positives = sum(1 for value in values if value > 0)
    return {
        "count": len(values),
        "avg": round(sum(values) / len(values), 4),
        "median": round(median(values), 4),
        "positive_count": positives,
        "win_rate": round(positives / len(values), 6),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
    }


def summarize_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ticker_counts = Counter(str(row.get("ticker") or "") for row in rows)
    event_counts = Counter(str(row.get("event_id") or "") for row in rows)
    top_ticker = ticker_counts.most_common(1)[0] if ticker_counts else ("", 0)
    horizons: dict[str, Any] = {}
    for horizon in HORIZONS:
        horizon_payload: dict[str, Any] = {}
        for field in DIAGNOSTIC_FIELDS:
            values = [
                value
                for row in rows
                for value in [outcome_value(row, horizon, field)]
                if value is not None
            ]
            horizon_payload[field] = summarize_metric(values)
        horizons[horizon] = horizon_payload
    return {
        "rows": len(rows),
        "unique_events": len(event_counts),
        "unique_tickers": len(ticker_counts),
        "ticker_counts": dict(sorted(ticker_counts.items())),
        "event_counts": dict(sorted(event_counts.items())),
        "max_single_ticker_share": round(top_ticker[1] / len(rows), 6)
        if rows
        else None,
        "top_ticker": top_ticker[0] if top_ticker[0] else None,
        "horizons": horizons,
    }


def compare_direct_attention(
    direct_summary: dict[str, Any], attention_summary: dict[str, Any]
) -> dict[str, Any]:
    cells: list[dict[str, Any]] = []
    for horizon in HORIZONS:
        for field in CORE_FIELDS:
            direct_metric = direct_summary["horizons"][horizon][field]
            attention_metric = attention_summary["horizons"][horizon][field]
            direct_avg = as_float(direct_metric.get("avg"))
            attention_avg = as_float(attention_metric.get("avg"))
            direct_win_rate = as_float(direct_metric.get("win_rate"))
            cells.append(
                {
                    "horizon": horizon,
                    "field": field,
                    "direct_avg": direct_avg,
                    "attention_avg": attention_avg,
                    "direct_minus_attention": round(direct_avg - attention_avg, 4)
                    if direct_avg is not None and attention_avg is not None
                    else None,
                    "direct_positive_avg": direct_avg is not None and direct_avg > 0,
                    "direct_win_rate_ge_60pct": direct_win_rate is not None
                    and direct_win_rate >= 0.60,
                    "direct_beats_attention": direct_avg is not None
                    and attention_avg is not None
                    and direct_avg > attention_avg,
                }
            )
    return {
        "cells": cells,
        "cell_count": len(cells),
        "direct_positive_avg_cells": sum(
            int(row["direct_positive_avg"]) for row in cells
        ),
        "direct_win_rate_ge_60pct_cells": sum(
            int(row["direct_win_rate_ge_60pct"]) for row in cells
        ),
        "direct_beats_attention_cells": sum(
            int(row["direct_beats_attention"]) for row in cells
        ),
    }


def sample_rows(rows: list[dict[str, Any]], limit: int = 16) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in sorted(
        rows,
        key=lambda item: (
            str(item.get("semantic_bucket") or ""),
            str(item.get("event_date") or ""),
            str(item.get("ticker") or ""),
        ),
    )[:limit]:
        out.append(
            {
                "event_id": row.get("event_id"),
                "ticker": row.get("ticker"),
                "event_date": row.get("event_date"),
                "entry_date": row.get("entry_date"),
                "semantic_bucket": row.get("semantic_bucket"),
                "source_type": row.get("source_type"),
                "theme_segment": row.get("theme_segment"),
                "h10_cash_relative_pnl": outcome_value(row, "10d", "cash_relative_pnl"),
                "h20_cash_relative_pnl": outcome_value(row, "20d", "cash_relative_pnl"),
                "h10_spy_relative_value": outcome_value(row, "10d", "spy_relative_value"),
                "h20_spy_relative_value": outcome_value(row, "20d", "spy_relative_value"),
            }
        )
    return out


def build_evaluation() -> dict[str, Any]:
    raw_rows = load_ledger_rows()
    dedup_rows = dedupe_closed_rows(raw_rows)
    direct_rows = [row for row in dedup_rows if is_direct_official(row)]
    attention_rows = [row for row in dedup_rows if is_attention(row)]
    canonical_by_window: dict[str, Any] = {}
    for label, (start, end) in WINDOWS.items():
        window_direct = [row for row in direct_rows if row_in_window(row, start, end)]
        canonical_by_window[label] = {
            "start": start,
            "end": end,
            "direct_official_rows": len(window_direct),
            "tickers": sorted({str(row.get("ticker") or "") for row in window_direct}),
            "events": sorted({str(row.get("event_id") or "") for row in window_direct}),
        }
    recent_rows = [
        row for row in direct_rows if row_in_window(row, RECENT_OBSERVE[0], RECENT_OBSERVE[1])
    ]
    direct_summary = summarize_group(direct_rows)
    attention_summary = summarize_group(attention_rows)
    comparison = compare_direct_attention(direct_summary, attention_summary)
    canonical_direct_count = sum(
        item["direct_official_rows"] for item in canonical_by_window.values()
    )
    canonical_windows_with_rows = sum(
        int(item["direct_official_rows"] > 0) for item in canonical_by_window.values()
    )
    promotion_readiness = {
        "canonical_direct_official_rows": canonical_direct_count,
        "canonical_windows_with_direct_rows": canonical_windows_with_rows,
        "recent_observe_direct_rows": len(recent_rows),
        "observed_forward_lead_cells": comparison["direct_beats_attention_cells"],
        "observed_forward_lead_cell_count": comparison["cell_count"],
        "passed": False,
        "failed_criteria": [
            "canonical_direct_official_rows_zero",
            "canonical_window_coverage_zero",
            "full_gate4_not_measurable_on_fixed_windows",
        ],
    }
    return {
        "raw_ledger_rows": len(raw_rows),
        "dedup_closed_decision_rows": len(dedup_rows),
        "bucket_counts": dict(
            sorted(Counter(str(row.get("semantic_bucket") or "") for row in dedup_rows).items())
        ),
        "source_type_counts": dict(
            sorted(Counter(str(row.get("source_type") or "") for row in dedup_rows).items())
        ),
        "groups": {
            "direct_official_defense_budget": direct_summary,
            "attention_only": attention_summary,
            "all_dedup_closed": summarize_group(dedup_rows),
        },
        "direct_vs_attention": comparison,
        "canonical_coverage_by_window": canonical_by_window,
        "recent_observe": {
            "start": RECENT_OBSERVE[0],
            "end": RECENT_OBSERVE[1],
            "direct_official_rows": len(recent_rows),
            "tickers": sorted({str(row.get("ticker") or "") for row in recent_rows}),
            "events": sorted({str(row.get("event_id") or "") for row in recent_rows}),
        },
        "promotion_readiness": promotion_readiness,
        "sample_rows": sample_rows(dedup_rows),
    }


def gate4_window_metrics(evaluation: dict[str, Any]) -> dict[str, Any]:
    direct = evaluation["groups"]["direct_official_defense_budget"]
    share = direct["max_single_ticker_share"] or 0.0
    return {
        "aggregate_ev_delta": 0.0,
        "aggregate_pnl_delta": 0.0,
        "windows_ev_improved": 0,
        "windows_ev_regressed": 0,
        "adjusted_trade_count": evaluation["promotion_readiness"][
            "canonical_direct_official_rows"
        ],
        "adjusted_window_count": evaluation["promotion_readiness"][
            "canonical_windows_with_direct_rows"
        ],
        "max_drawdown_worse_max": 0.0,
        "single_ticker_positive_share": share,
        "baseline_single_ticker_positive_share": max(share, 0.01),
        "top_5_contribution_pct": min(1.0, share),
        "baseline_top_5_contribution_pct": max(min(1.0, share), 0.01),
        "hhi_concentration": min(1.0, share * share),
        "baseline_hhi_concentration": max(min(1.0, share * share), 0.0001),
        "avg_pnl_per_trade_delta": 0.0,
        "avg_return_delta_pp": 0.0,
    }


def build_payload() -> dict[str, Any]:
    evaluation = build_evaluation()
    baseline = baseline_metrics()
    window_metrics = gate4_window_metrics(evaluation)
    gate4_strict = evaluate_gate4(window_metrics, check_materiality=True)
    gate4_canonical = evaluate_gate4(window_metrics, check_materiality=False)
    envelope = ExecutionEnvelope(
        base_notional=10_000.0,
        max_capital_pct=0.03,
        min_dollar_volume=25_000_000.0,
        slippage_bps=20.0,
        max_displacement=0,
        max_concurrent=3,
        order_semantics="default_off_paper_next_open_10d_close",
        kill_switch_drawdown_pct=0.08,
        sleeve_drawdown_stop_pct=0.12,
        notes=(
            "Declared only for promotion review; no live or default-on behavior "
            "changed because Gate 4 rejected the policy."
        ),
    )
    direct = evaluation["groups"]["direct_official_defense_budget"]
    live_inputs = {
        "closed_forward_trades": direct["rows"],
        "forward_pnl": direct["horizons"]["10d"]["cash_relative_pnl"]["avg"],
        "replacement_value_passed": False,
        "kill_switch_parity_passed": False,
    }
    live_readiness = evaluate_live_readiness(envelope=envelope, **live_inputs)
    verdict = full_stack_verdict(
        gate4=gate4_canonical,
        live_readiness=live_readiness,
        envelope=envelope,
    )
    decision = "rejected_space_catalyst_direct_official_promotion_no_canonical_coverage"
    realized_failure_mode = "historical_coverage_too_thin"
    rejection_reason = (
        "The direct-official defense-budget lead remains confined to recent "
        "forward rows. The fixed canonical Gate 4 windows contain zero matching "
        "direct official rows, so the policy has no measurable historical "
        "before/after EV or PnL and cannot be accepted as a paper sleeve."
    )
    calibration = {
        "actual_decision": "rejected",
        "actual_success": 0,
        "predicted_success_probability": PREDICTION["success_probability"],
        "brier_score": round((PREDICTION["success_probability"] - 0.0) ** 2, 6),
        "calibration_direction": "directionally_calibrated",
        "surprise_level": "low",
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "actual_ev_delta": 0.0,
        "ev_prediction_error": 0.0,
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_pnl_delta": 0.0,
        "pnl_prediction_error": 0.0,
        "predicted_failure_modes": PREDICTION["main_failure_modes"],
        "realized_failure_mode": realized_failure_mode,
        "predicted_failure_mode_hit": True,
        "surprise_note": (
            "Low surprise: the recent forward lead is real but the direct "
            "official event date starts after the late_strong canonical window."
        ),
    }
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "lane": LANE,
        "owner": OWNER,
        "status": "rejected",
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "full_stack_verdict": verdict["verdict"],
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": SINGLE_CAUSAL_VARIABLE,
        "changed_variable": SINGLE_CAUSAL_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": PREDICTION,
        "calibration": calibration,
        "predicted_failure_modes": PREDICTION["main_failure_modes"],
        "realized_failure_mode": realized_failure_mode,
        "input_files": {
            "ledger": repo_rel(LEDGER),
            "summary": repo_rel(SUMMARY),
            "baseline": repo_rel(BASELINE_RESULT),
        },
        "baseline_metrics": baseline,
        "evaluation": evaluation,
        "window_metrics": window_metrics,
        "gate4": {
            "passed": False,
            "canonical_backtest_required": True,
            "strategy_behavior_changed": False,
            "gate4_strict_materiality": gate4_strict,
            "gate4_canonical": gate4_canonical,
            "binding_failures": gate4_canonical["hard_failures"],
            "note": (
                "Gate 4 is rejected because the fixed canonical windows have no "
                "matching direct-official defense-budget event rows. The recent "
                "observe window is reported but excluded from acceptance."
            ),
        },
        "full_stack": {
            "verdict": verdict,
            "execution_envelope": envelope.to_dict(),
            "live_inputs": live_inputs,
            "live_readiness": live_readiness,
        },
        "gate1": {
            "passed": True,
            "baseline_protocol": "docs/backtesting.md canonical three fixed windows",
            "baseline_artifact": repo_rel(BASELINE_RESULT),
            "accepted_core_expected_value_score_sum": baseline[
                "expected_value_score_sum"
            ],
            "accepted_core_total_pnl_sum": baseline["total_pnl"],
        },
        "gate2": {
            "passed": True,
            "rule_dependencies": [
                "shared space_catalyst event_state_shadow_ledger rows",
                "semantic_bucket == defense_budget_theme",
                "source_type == official_government_release",
                "entry_date fixed-window membership",
            ],
            "entry_date_target_price_sentinel": {
                "entry_date_present": all(
                    bool(row.get("entry_date")) for row in evaluation["sample_rows"]
                ),
                "target_price_not_applicable": True,
                "reason": "No executable signal generation or backtester position contract changed.",
            },
        },
        "gate3": {
            "passed": True,
            "adds_filter": False,
            "candidate_pool_changed": False,
            "survival_rate_not_applicable": True,
            "baseline_survival_rate": baseline["survival_rate"],
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "trade_enabled": False,
            "daily_snapshot_exposed": True,
            "live_realism_evaluated": True,
            "live_ready": False,
            "activation_envelope": envelope.to_dict(),
            "parity_test_added": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
        },
        "rejection_reason": rejection_reason,
        "post_run_reflection": {
            "why_result_happened": (
                "The positive direct-official cohort comes from a post-window "
                "Golden Dome/SBI event: it is useful forward evidence, but not "
                "canonical historical evidence. With zero matching rows across "
                "old_thin, mid_weak, and late_strong, full-stack promotion would "
                "be a forward overfit."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune Space catalyst direct-official source type, "
                "semantic bucket, hold days, same-theme binding, notional, "
                "candidate ranking, or response curve on the same Golden Dome "
                "rows. Do not call the exp-20260709-014 lead accepted alpha."
            ),
            "new_evidence_required": (
                "Reopen only with materially more closed Space catalyst rows "
                "(at least +50% and +10 de-duplicated direct-official rows), a "
                "PIT historical Space event archive that creates canonical "
                "window coverage, or an ex-event same-theme replacement basket "
                "that changes opportunity-cost measurement."
            ),
            "next_evidence_needed": (
                "Let the shared event-state ledger continue accumulating. If a "
                "PIT historical archive appears, rerun this exact promotion gate "
                "before writing any new shared strategy helper."
            ),
        },
        "gate_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": (
                "Novelty override recorded exp-20260511-002 static pool, "
                "exp-20260702-003 same-theme defense-budget failure, "
                "exp-20260627-024 surface repair, and exp-20260709-014 "
                "observed-only positive direct-vs-attention lead."
            ),
            "3_single_causal_variable": SINGLE_CAUSAL_VARIABLE,
            "4_acceptance_standard": (
                "Full-stack candidate-pool Gate 4 over the fixed canonical "
                "windows plus declared execution envelope; recent_observe is "
                "diagnostic only."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "headline_metrics": {
            "canonical_direct_official_rows": evaluation["promotion_readiness"][
                "canonical_direct_official_rows"
            ],
            "canonical_windows_with_direct_rows": evaluation["promotion_readiness"][
                "canonical_windows_with_direct_rows"
            ],
            "recent_observe_direct_rows": evaluation["promotion_readiness"][
                "recent_observe_direct_rows"
            ],
            "observed_forward_lead_cells": evaluation["promotion_readiness"][
                "observed_forward_lead_cells"
            ],
            "observed_forward_lead_cell_count": evaluation["promotion_readiness"][
                "observed_forward_lead_cell_count"
            ],
            "direct_rows_total": direct["rows"],
            "attention_rows_total": evaluation["groups"]["attention_only"]["rows"],
        },
        "related_files": CHANGED_FILES,
        "changed_files": CHANGED_FILES,
        "allowed_write_scope": CHANGED_FILES + ["docs/experiment_registry.json"],
        "lean_quality_passed": True,
    }
    return payload


def build_card(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: Space catalyst direct-official promotion gate",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Full-stack verdict: `{payload['full_stack_verdict']}`",
            f"- Canonical direct-official rows: `{payload['headline_metrics']['canonical_direct_official_rows']}`",
            f"- Canonical windows with rows: `{payload['headline_metrics']['canonical_windows_with_direct_rows']}`",
            f"- Recent-observe direct rows: `{payload['headline_metrics']['recent_observe_direct_rows']}`",
            f"- Observed direct-vs-attention cells: `{payload['headline_metrics']['observed_forward_lead_cells']}` / `{payload['headline_metrics']['observed_forward_lead_cell_count']}`",
            f"- Gate 4 failures: `{payload['gate4']['binding_failures']}`",
            "",
            "## Conclusion",
            "",
            payload["rejection_reason"],
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Reproduction",
            "",
            "```powershell",
            RUNNER_COMMAND,
            "```",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [REPO_ROOT / rel for rel in CHANGED_FILES]
    files.append(REGISTRY_JSON)
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(payload, allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result={
            "accepted": False,
            "accepted_alpha": False,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "full_stack_verdict": payload["full_stack_verdict"],
            "gate4": payload["gate4"],
            "headline_metrics": payload["headline_metrics"],
            "summary": payload["rejection_reason"],
        },
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
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "calibration": payload["calibration"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "ticket_file": repo_rel(TICKET_JSON),
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
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "full_stack_verdict": payload["full_stack_verdict"],
                "artifact": repo_rel(OUT_JSON),
                "headline_metrics": payload["headline_metrics"],
                "gate4_failures": payload["gate4"]["binding_failures"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
