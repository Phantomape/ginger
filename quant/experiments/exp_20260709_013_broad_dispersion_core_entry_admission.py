"""exp-20260709-013: broad dispersion state on historical core entries.

Read-only alpha diagnostic. This promotes the exp-20260709-005 forward-row lead
to a different gate shape: canonical historical core trade outcomes. The state
join is point-in-time for an entry-at-open rule: every trade is tagged with the
latest broad dispersion/correlation feature date strictly before entry_date.

This runner does not change signal generation, ranking, sizing, exits, orders,
or production adapters.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

EXPERIMENT_ID = "exp-20260709-013"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "broad_dispersion_core_entry_admission"
RUNNER = f"quant/experiments/exp_20260709_013_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, QUANT_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from broad_dispersion_features import (  # noqa: E402
    FEATURES_RULE_VERSION,
    avg_pairwise_correlation,
    corr_t_stat,
    cross_sectional_dispersion,
    daily_returns,
    liquidity_mask,
    load_broad_panel,
    spearman,
)
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)

DATA_DIR = REPO_ROOT / "data"
BASELINE_RESULT = (
    DATA_DIR / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
BACKTEST_ARCHIVE = DATA_DIR / "backtests" / "archive" / "20260604_ohlcv_warehouse_replay"
WAREHOUSE_MAIN = DATA_DIR / "warehouse" / "warehouse_main.sqlite"

PANEL_START = "2024-06-01"
ANALYSIS_END = "2026-04-21"
MIN_ELIGIBLE_NAMES = 300
MIN_COVERED_TRADES = 45
MAX_SINGLE_TICKER_SHARE = 0.35
MIN_TOP_BOTTOM_WINDOW_WINS = 2
SEVERE_LOSS_USD = -1000.0

OUT_DIR = DATA_DIR / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260709_013_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Broad dispersion/correlation stock-picker regimes should identify "
    "higher-quality historical core entries: accepted core trades entered "
    "during high dispersion and low average-correlation states should have "
    "better PnL, win rate, and loss-tail than dead-chop/high-correlation "
    "entries."
)
CHANGED_VARIABLE = "broad_dispersion_correlation_core_entry_admission_diagnostic_v1"
MECHANISM_FAMILY = "core_entry_admission_gate"
TRIAL_FAMILY = "broad_dispersion_core_entry_admission_diagnostic"
TRIAL_VARIANT_ID = "core_trade_stock_picker_vs_dead_chop_v1"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260709-004",
    "exp-20260709-005",
    "exp-20260709-007",
    "exp-20260708-026",
]
CAUSAL_COMPONENTS = [
    "read-only core trade attribution",
    "broad dispersion/correlation state join",
    "canonical three-window trade outcomes",
    "no strategy behavior change",
]
PREDICTED_FAILURE_MODES = [
    "small_core_trade_sample",
    "state_signal_does_not_transfer_from_forward_rows",
    "late_strong_only_effect",
    "loss_tail_not_separated",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: str | Path) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
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


def finite_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def round_or_none(value: Any, digits: int = 6) -> float | None:
    value = finite_float(value)
    return round(value, digits) if value is not None else None


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
            sum(float(row.get("expected_value_score") or 0.0) for row in windows), 4
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
        "max_drawdown_pct_worst": round(max(drawdowns), 4) if drawdowns else None,
    }


def resolve_window_path(path_value: str) -> Path:
    path = REPO_ROOT / path_value
    if path.exists():
        return path
    archive_path = BACKTEST_ARCHIVE / Path(path_value).name
    if archive_path.exists():
        return archive_path
    return path


def load_core_trades() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    summary = read_json(BASELINE_RESULT, {})
    trades: list[dict[str, Any]] = []
    windows_loaded: list[dict[str, Any]] = []
    for window in summary.get("windows", []):
        path = resolve_window_path(str(window.get("path") or ""))
        payload = read_json(path, {})
        window_trades = payload.get("trades") if isinstance(payload, dict) else []
        if not isinstance(window_trades, list):
            window_trades = []
        for trade in window_trades:
            if not isinstance(trade, dict):
                continue
            row = dict(trade)
            row["window_label"] = window.get("label")
            row["window_start"] = window.get("start")
            row["window_end"] = window.get("end")
            row["window_artifact"] = repo_rel(path)
            trades.append(row)
        windows_loaded.append(
            {
                "label": window.get("label"),
                "path": repo_rel(path),
                "exists": path.exists(),
                "trade_count": len(window_trades),
            }
        )
    return trades, {"windows_loaded": windows_loaded, "trade_count": len(trades)}


def feature_frame() -> tuple[pd.DataFrame, dict[str, Any]]:
    closes, dollar = load_broad_panel(
        [str(WAREHOUSE_MAIN.resolve().as_posix())],
        PANEL_START,
        ANALYSIS_END,
    )
    if closes.empty:
        return pd.DataFrame(), {"panel_shape": [0, 0]}
    mask = liquidity_mask(closes, dollar)
    returns = daily_returns(closes)
    frame = pd.DataFrame(
        {
            "broad_dispersion": cross_sectional_dispersion(returns, mask),
            "avg_pairwise_correlation": avg_pairwise_correlation(returns, mask),
            "eligible_count": mask.sum(axis=1),
        }
    )
    frame["feature_date"] = frame.index.astype(str)
    usable = frame[
        (frame["eligible_count"] >= MIN_ELIGIBLE_NAMES)
        & frame["broad_dispersion"].notna()
        & frame["avg_pairwise_correlation"].notna()
    ]
    disp = pd.to_numeric(usable["broad_dispersion"], errors="coerce")
    corr = pd.to_numeric(usable["avg_pairwise_correlation"], errors="coerce")
    disp_std = float(disp.std(ddof=0) or 0.0)
    corr_std = float(corr.std(ddof=0) or 0.0)
    frame["dispersion_z"] = (frame["broad_dispersion"] - float(disp.mean())) / disp_std
    frame["avg_corr_z"] = (frame["avg_pairwise_correlation"] - float(corr.mean())) / corr_std
    frame["stock_picker_score"] = frame["dispersion_z"] - frame["avg_corr_z"]
    metadata = {
        "warehouse": repo_rel(WAREHOUSE_MAIN),
        "panel_start": PANEL_START,
        "panel_end": ANALYSIS_END,
        "panel_shape": [int(closes.shape[0]), int(closes.shape[1])],
        "feature_dates_total": int(len(frame)),
        "feature_dates_usable": int(len(usable)),
        "max_eligible_names_per_day": int(frame["eligible_count"].max()),
        "median_eligible_names_per_day": round_or_none(frame["eligible_count"].median(), 2),
        "score_normalization": "z-scores computed over usable historical feature dates, not over trade outcomes",
    }
    return frame, metadata


def previous_feature_date(entry_date: str, feature_dates: list[str]) -> str | None:
    candidates = [date for date in feature_dates if date < entry_date]
    return candidates[-1] if candidates else None


def missing_required_fields(rows: list[dict[str, Any]]) -> dict[str, int]:
    required = ["entry_date", "ticker", "pnl", "pnl_pct_net", "exit_date"]
    missing: dict[str, int] = {}
    for field in required:
        count = sum(1 for row in rows if row.get(field) in (None, ""))
        if count:
            missing[field] = count
    return missing


def join_trades_to_features(
    trades: list[dict[str, Any]],
    features: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if features.empty:
        return pd.DataFrame(), {
            "raw_trade_rows": len(trades),
            "covered_trade_rows": 0,
            "coverage_rate": 0.0 if trades else None,
            "uncovered_reason_counts": {"missing_features": len(trades)},
            "uncovered_examples": [],
        }
    feature_dates = sorted(features["feature_date"].astype(str).tolist())
    by_date = features.set_index("feature_date")
    joined_rows: list[dict[str, Any]] = []
    uncovered: list[dict[str, Any]] = []
    reasons: dict[str, int] = {}
    for trade in trades:
        entry_date = str(trade.get("entry_date") or "")[:10]
        reason = None
        feature_date = previous_feature_date(entry_date, feature_dates) if entry_date else None
        feat = by_date.loc[feature_date] if feature_date else None
        if not entry_date:
            reason = "missing_entry_date"
        elif feature_date is None or feat is None:
            reason = "missing_prior_feature_date"
        elif int(feat.get("eligible_count") or 0) < MIN_ELIGIBLE_NAMES:
            reason = "low_eligible_count"
        elif finite_float(feat.get("stock_picker_score")) is None:
            reason = "missing_stock_picker_score"

        if reason:
            reasons[reason] = reasons.get(reason, 0) + 1
            uncovered.append(
                {
                    "ticker": trade.get("ticker"),
                    "entry_date": entry_date,
                    "window_label": trade.get("window_label"),
                    "feature_date": feature_date,
                    "reason": reason,
                }
            )
            continue

        assert feat is not None
        joined_rows.append(
            {
                "trade_key": trade.get("trade_key"),
                "ticker": str(trade.get("ticker") or "").upper(),
                "strategy": trade.get("strategy"),
                "sector": trade.get("sector"),
                "window_label": trade.get("window_label"),
                "entry_date": entry_date,
                "entry_state_date": feature_date,
                "exit_date": trade.get("exit_date"),
                "pnl_usd": round_or_none(trade.get("pnl"), 4),
                "pnl_pct_net": round_or_none(trade.get("pnl_pct_net"), 6),
                "exit_reason": trade.get("exit_reason"),
                "actual_risk_pct": round_or_none(trade.get("actual_risk_pct"), 8),
                "broad_dispersion": round_or_none(feat.get("broad_dispersion"), 8),
                "avg_pairwise_correlation": round_or_none(
                    feat.get("avg_pairwise_correlation"), 8
                ),
                "dispersion_z": round_or_none(feat.get("dispersion_z"), 6),
                "avg_corr_z": round_or_none(feat.get("avg_corr_z"), 6),
                "stock_picker_score": round_or_none(feat.get("stock_picker_score"), 6),
                "eligible_count": int(feat.get("eligible_count") or 0),
            }
        )
    frame = pd.DataFrame(joined_rows)
    return frame, {
        "raw_trade_rows": len(trades),
        "covered_trade_rows": int(len(frame)),
        "coverage_rate": round(len(frame) / len(trades), 6) if trades else None,
        "uncovered_reason_counts": reasons,
        "uncovered_examples": uncovered[:15],
        "entry_state_date_rule": "latest usable feature date strictly before trade entry_date",
    }


def add_trade_state_buckets(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    out = frame.copy()
    ranked = out["stock_picker_score"].rank(method="first")
    out["state_quartile"] = pd.qcut(
        ranked,
        4,
        labels=["dead_chop_q1", "low_mid_q2", "high_mid_q3", "stock_picker_q4"],
    ).astype(str)
    return out


def group_summary(frame: pd.DataFrame) -> dict[str, Any]:
    values = pd.to_numeric(frame.get("pnl_usd", pd.Series(dtype=float)), errors="coerce").dropna()
    pct = pd.to_numeric(frame.get("pnl_pct_net", pd.Series(dtype=float)), errors="coerce").dropna()
    if values.empty:
        return {
            "count": 0,
            "sum_pnl": None,
            "mean_pnl": None,
            "median_pnl": None,
            "win_rate": None,
            "loss_rate": None,
            "severe_loss_rate": None,
            "mean_return_pct": None,
        }
    return {
        "count": int(len(values)),
        "sum_pnl": round(float(values.sum()), 2),
        "mean_pnl": round(float(values.mean()), 4),
        "median_pnl": round(float(values.median()), 4),
        "win_rate": round(float((values > 0).mean()), 6),
        "loss_rate": round(float((values < 0).mean()), 6),
        "severe_loss_rate": round(float((values <= SEVERE_LOSS_USD).mean()), 6),
        "mean_return_pct": round(float(pct.mean()), 6) if not pct.empty else None,
    }


def counts(frame: pd.DataFrame, field: str) -> dict[str, int]:
    if frame.empty or field not in frame:
        return {}
    return {
        str(key): int(value)
        for key, value in frame[field].fillna("missing").astype(str).value_counts().sort_index().items()
    }


def summarize_attribution(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {"state_rows": 0, "criteria": {}}
    top = frame[frame["state_quartile"] == "stock_picker_q4"]
    bottom = frame[frame["state_quartile"] == "dead_chop_q1"]
    top_summary = group_summary(top)
    bottom_summary = group_summary(bottom)
    all_summary = group_summary(frame)
    top_mean = top_summary["mean_pnl"]
    bottom_mean = bottom_summary["mean_pnl"]
    q4_minus_q1 = (
        round(float(top_mean) - float(bottom_mean), 4)
        if top_mean is not None and bottom_mean is not None
        else None
    )
    per_window: dict[str, Any] = {}
    positive_windows = 0
    for label, sub in frame.groupby("window_label"):
        sub_top = sub[sub["state_quartile"] == "stock_picker_q4"]
        sub_bottom = sub[sub["state_quartile"] == "dead_chop_q1"]
        t = group_summary(sub_top)
        b = group_summary(sub_bottom)
        diff = (
            round(float(t["mean_pnl"]) - float(b["mean_pnl"]), 4)
            if t["mean_pnl"] is not None and b["mean_pnl"] is not None
            else None
        )
        if diff is not None and diff > 0:
            positive_windows += 1
        per_window[str(label)] = {
            "all": group_summary(sub),
            "stock_picker_q4": t,
            "dead_chop_q1": b,
            "q4_minus_q1_mean_pnl": diff,
        }
    rho = spearman(
        pd.to_numeric(frame["stock_picker_score"], errors="coerce").tolist(),
        pd.to_numeric(frame["pnl_usd"], errors="coerce").tolist(),
    )
    rho_t = corr_t_stat(rho, int(len(frame)))
    by_ticker = counts(frame, "ticker")
    max_ticker_count = max(by_ticker.values()) if by_ticker else 0
    max_ticker_share = max_ticker_count / len(frame) if len(frame) else 0.0
    criteria = {
        "covered_trades_gte_min": len(frame) >= MIN_COVERED_TRADES,
        "q4_mean_pnl_gt_q1": q4_minus_q1 is not None and q4_minus_q1 > 0,
        "q4_win_rate_gt_q1": (
            top_summary["win_rate"] is not None
            and bottom_summary["win_rate"] is not None
            and float(top_summary["win_rate"]) > float(bottom_summary["win_rate"])
        ),
        "q4_severe_loss_rate_lt_q1": (
            top_summary["severe_loss_rate"] is not None
            and bottom_summary["severe_loss_rate"] is not None
            and float(top_summary["severe_loss_rate"])
            < float(bottom_summary["severe_loss_rate"])
        ),
        "spearman_positive": rho is not None and rho > 0,
        "positive_windows_gte_2": positive_windows >= MIN_TOP_BOTTOM_WINDOW_WINS,
        "max_ticker_share_lte_guard": max_ticker_share <= MAX_SINGLE_TICKER_SHARE,
    }
    return {
        "state_rows": int(len(frame)),
        "state_quartile_counts": counts(frame, "state_quartile"),
        "window_counts": counts(frame, "window_label"),
        "ticker_counts": by_ticker,
        "max_single_ticker_count": int(max_ticker_count),
        "max_single_ticker_share": round(float(max_ticker_share), 6),
        "all": all_summary,
        "stock_picker_q4": top_summary,
        "dead_chop_q1": bottom_summary,
        "q4_minus_q1_mean_pnl": q4_minus_q1,
        "stock_picker_score_spearman": round_or_none(rho, 6),
        "stock_picker_score_t_stat": round_or_none(rho_t, 4),
        "positive_window_count": int(positive_windows),
        "per_window": per_window,
        "criteria": criteria,
    }


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    baseline = baseline_metrics()
    trades, trade_load = load_core_trades()
    features, feature_meta = feature_frame()
    joined, coverage = join_trades_to_features(trades, features)
    scored = add_trade_state_buckets(joined)
    attribution = summarize_attribution(scored)
    missing_fields = missing_required_fields(trades)

    measurement_blockers: list[str] = []
    if not BASELINE_RESULT.exists() or baseline.get("window_count") != 3:
        measurement_blockers.append("baseline_missing_or_nonstandard")
    if trade_load["trade_count"] != baseline.get("trade_count"):
        measurement_blockers.append("trade_count_mismatch_vs_baseline_summary")
    if missing_fields:
        measurement_blockers.append("core_trade_required_fields_missing")
    if coverage["covered_trade_rows"] < MIN_COVERED_TRADES:
        measurement_blockers.append("too_few_feature_covered_core_trades")

    measurement_passed = not measurement_blockers
    criteria = attribution.get("criteria", {})
    lead_passed = measurement_passed and all(bool(value) for value in criteria.values())
    if not measurement_passed:
        status = "blocked"
        decision = "blocked_broad_dispersion_core_entry_admission_coverage"
    elif lead_passed:
        status = "observed_only"
        decision = "observed_only_lead_broad_dispersion_core_entry_admission"
    else:
        status = "observed_only"
        decision = "observed_only_rejected_broad_dispersion_core_entry_admission"

    strategy_delta = {
        "expected_value_score_sum_delta": 0.0,
        "total_pnl_delta": 0.0,
        "trade_count_delta": 0,
        "signals_generated_delta": 0,
        "signals_survived_delta": 0,
        "strategy_behavior_changed": False,
    }
    delta_metrics = {
        **strategy_delta,
        "raw_core_trades": trade_load["trade_count"],
        "covered_core_trades": coverage["covered_trade_rows"],
        "coverage_rate": coverage["coverage_rate"],
        "state_quartile_counts": attribution.get("state_quartile_counts", {}),
        "q4_minus_q1_mean_pnl": attribution.get("q4_minus_q1_mean_pnl"),
        "stock_picker_score_spearman": attribution.get("stock_picker_score_spearman"),
        "positive_window_count": attribution.get("positive_window_count"),
        "lead_passed": lead_passed,
        "criteria": criteria,
    }

    pred = ticket.get("prediction") or {}
    success_probability = float(pred.get("success_probability") or 0.32)
    actual_success = 1 if lead_passed else 0
    realized_failure_modes = list(measurement_blockers)
    if measurement_passed and not lead_passed:
        realized_failure_modes.extend(
            key for key, value in criteria.items() if not bool(value)
        )
    prediction = {
        "recorded_at": pred.get("recorded_at") or ticket.get("claimed_at") or ticket.get("created_at"),
        "success_probability": success_probability,
        "expected_ev_delta": pred.get("expected_ev_delta"),
        "expected_pnl_delta": pred.get("expected_pnl_delta"),
        "main_failure_modes": pred.get("main_failure_modes") or PREDICTED_FAILURE_MODES,
        "confidence_reason": pred.get("confidence_reason"),
    }
    calibration = {
        "predicted_success_probability": success_probability,
        "actual_success": actual_success,
        "brier_score": round((success_probability - float(actual_success)) ** 2, 6),
        "predicted_failure_modes": PREDICTED_FAILURE_MODES,
        "realized_failure_modes": realized_failure_modes,
        "predicted_failure_mode_hit": bool(realized_failure_modes),
    }
    production_impact = {
        "trade_enabled": False,
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "daily_snapshot_exposed": False,
        "entry_rules_changed": False,
        "exit_rules_changed": False,
        "ranking_changed": False,
        "sizing_changed": False,
        "orders_changed": False,
        "llm_decision_boundary_changed": False,
        "live_ready": False,
        "live_realism_evaluated": False,
        "scope": "read_only_canonical_core_trade_admission_diagnostic",
    }
    files = [
        RUNNER,
        repo_rel(OUT_JSON),
        repo_rel(LOG_JSON),
        repo_rel(CARD_MD),
        repo_rel(MANIFEST_JSON),
        repo_rel(TICKET_JSON),
        repo_rel(REGISTRY_JSON),
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "status": status,
        "lane": LANE,
        "owner": OWNER,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "accepted_measurement_repair": False,
        "alpha_ready": False,
        "observed_only_lead": bool(lead_passed),
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": "entry_admission_observed_attribution",
        "implementation_mode": "read_only_core_trade_admission_diagnostic",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "new_gate_shape_historical_core_trade_outcome",
        "prediction": prediction,
        "calibration": calibration,
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "exp-20260709-004": "Rejected broad dispersion/correlation on synthetic daily proxy spreads.",
                "exp-20260709-005": "Positive observed-only forward replacement-value lead on 23 state-covered rows.",
                "exp-20260709-007": "Stopped further same-row forward attribution on this broad-state lane.",
                "exp-20260708-026": "Rejected core high-vol/high-beta admission diagnostic; this uses independent broad cross-sectional state.",
                "novelty_gate": "Override accepted as new historical core-trade gate shape.",
            },
            "3_single_measurement_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": (
                "Observed-only lead requires >=45 covered core trades, q4 mean PnL "
                "> q1, q4 win rate > q1, q4 severe-loss rate < q1, positive "
                "Spearman(score,PnL), q4-q1 positive in >=2/3 windows, and max "
                "single ticker share <=35%. It cannot accept strategy behavior."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "features_rule_version": FEATURES_RULE_VERSION,
            "panel_start": PANEL_START,
            "analysis_end": ANALYSIS_END,
            "entry_state_date_rule": coverage.get("entry_state_date_rule"),
            "min_eligible_names": MIN_ELIGIBLE_NAMES,
            "min_covered_trades": MIN_COVERED_TRADES,
            "severe_loss_usd": SEVERE_LOSS_USD,
            "stock_picker_score": "z(broad_dispersion) - z(avg_pairwise_correlation)",
        },
        "gate1": {
            "passed": BASELINE_RESULT.exists() and baseline.get("window_count") == 3,
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": measurement_passed,
            "dependencies_validated": not missing_fields and not features.empty,
            "fields_checked": [
                "entry_date",
                "ticker",
                "pnl",
                "pnl_pct_net",
                "broad_dispersion",
                "avg_pairwise_correlation",
            ],
            "missing_required_core_trade_fields": missing_fields,
            "feature_coverage": coverage,
            "entry_date_scope": "Existing canonical core trade entry_date joined to previous feature date.",
            "target_price_scope": "Not applicable; existing closed trade attribution, no signal generation or position contract mutation.",
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": len(trades),
            "signals_survived": len(trades),
            "survival_rate": 1.0 if trades else None,
            "note": "No executable filter was added; this is closed-trade attribution only.",
        },
        "gate4": {
            "passed": measurement_passed,
            "accepted_alpha": False,
            "alpha_ready": False,
            "decision": decision,
            "measurement_blockers": measurement_blockers,
            "alpha_blockers": [] if lead_passed else ["predeclared_core_entry_state_lead_criteria_not_met"],
            "strategy_rerun_required": False,
            "before_after_strategy_delta": strategy_delta,
            "observed_only_lead_passed": bool(lead_passed),
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": delta_metrics,
        "trade_load": trade_load,
        "feature_metadata": feature_meta,
        "trade_state_coverage": coverage,
        "state_attribution": attribution,
        "analysis_rows": scored.sort_values(
            ["stock_picker_score", "entry_date"], ascending=[False, True]
        ).to_dict(orient="records")
        if not scored.empty
        else [],
        "production_impact": production_impact,
        "post_run_reflection": {
            "why_result_happened": None,
            "forbidden_near_neighbor_retry": (
                "Do not retune broad-dispersion thresholds, score formula, "
                "quartile boundaries, loss cutoff, ticker exclusions, or window "
                "slices on these same 61 historical core trades. If this is "
                "negative, move to a different admission field or wait for more "
                "settled forward rows; if positive, the next step is a shared "
                "helper Gate 1-4, not another diagnostic slice."
            ),
            "new_evidence_required": (
                "A shared production/backtest admission helper that passes Gate "
                "1-4, materially more settled forward rows tagged with this state, "
                "or a genuinely independent entry-time state source."
            ),
        },
        "next_retry_requires": [
            "shared helper Gate 1-4 if positive",
            "materially more settled forward rows tagged with this state",
            "or a genuinely independent entry-time state source",
        ],
        "changed_files": files,
        "related_files": [
            "quant/broad_dispersion_features.py",
            "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json",
            "data/backtests/archive/20260604_ohlcv_warehouse_replay/",
            "experiments/logs/exp-20260709-005.json",
        ],
        "allowed_write_scope": files,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_broad_dispersion_features.py -q",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {"used_javascript": False, "evidence": "Python runner only."},
        "lean_quality_passed": measurement_passed,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "ticket_before": {
            "created_at": ticket.get("created_at"),
            "claimed_at": ticket.get("claimed_at"),
            "hub_identity": ticket.get("hub_identity"),
            "novelty": ticket.get("novelty"),
        },
    }


def finalize_reflection(payload: dict[str, Any]) -> None:
    attr = payload["state_attribution"]
    if payload["status"] == "blocked":
        why = (
            f"The diagnostic was blocked by measurement coverage: "
            f"{payload['gate4']['measurement_blockers']} with "
            f"{payload['trade_state_coverage']['covered_trade_rows']}/"
            f"{payload['trade_state_coverage']['raw_trade_rows']} covered trades."
        )
    elif payload["observed_only_lead"]:
        why = (
            "The stock-picker state transferred to historical core trades: "
            f"q4 mean PnL {attr['stock_picker_q4']['mean_pnl']} beat q1 "
            f"{attr['dead_chop_q1']['mean_pnl']}, win rate improved, severe "
            f"loss rate fell, Spearman was {attr['stock_picker_score_spearman']}, "
            f"and {attr['positive_window_count']}/3 windows had positive q4-q1."
        )
    else:
        why = (
            "The forward-row stock-picker lead did not survive the historical "
            "core-entry diagnostic. "
            f"q4 mean PnL {attr.get('stock_picker_q4', {}).get('mean_pnl')} "
            f"vs q1 {attr.get('dead_chop_q1', {}).get('mean_pnl')}, "
            f"q4-q1 {attr.get('q4_minus_q1_mean_pnl')}, Spearman "
            f"{attr.get('stock_picker_score_spearman')}, positive windows "
            f"{attr.get('positive_window_count')}/3, criteria {attr.get('criteria')}."
        )
    payload["post_run_reflection"]["why_result_happened"] = why


def build_card(payload: dict[str, Any]) -> str:
    attr = payload["state_attribution"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: broad dispersion core-entry admission",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Covered core trades: `{payload['trade_state_coverage']['covered_trade_rows']}` / `{payload['trade_state_coverage']['raw_trade_rows']}`",
            f"- State quartiles: `{attr.get('state_quartile_counts', {})}`",
            f"- q4 mean PnL: `{attr.get('stock_picker_q4', {}).get('mean_pnl')}`",
            f"- q1 mean PnL: `{attr.get('dead_chop_q1', {}).get('mean_pnl')}`",
            f"- q4-q1 mean PnL: `{attr.get('q4_minus_q1_mean_pnl')}`",
            f"- Spearman(score, PnL): `{attr.get('stock_picker_score_spearman')}`",
            f"- Positive windows: `{attr.get('positive_window_count')}` / 3",
            f"- Criteria: `{attr.get('criteria', {})}`",
            "- Strategy behavior changed: `false`",
            "",
            "## Why",
            "",
            payload["post_run_reflection"]["why_result_happened"] or "",
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
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
        BASELINE_RESULT,
        QUANT_ROOT / "broad_dispersion_features.py",
    ]
    for row in payload["trade_load"].get("windows_loaded", []):
        files.append(REPO_ROOT / row["path"])
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
        "changed_files": payload["changed_files"],
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
            "accepted_measurement_repair": False,
            "alpha_ready": False,
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "gate4": payload["gate4"],
            "delta_metrics": payload["delta_metrics"],
            "calibration": payload["calibration"],
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
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "ticket_file": repo_rel(TICKET_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "before_metrics": payload["before_metrics"],
            "after_metrics": payload["after_metrics"],
            "delta_metrics": payload["delta_metrics"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "next_retry_requires": payload["next_retry_requires"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "calibration": payload["calibration"],
            "hub_identity": payload["ticket_before"].get("hub_identity"),
            "novelty": payload["ticket_before"].get("novelty"),
            "claimed_at": payload["ticket_before"].get("claimed_at"),
        },
        allow_missing_prediction=True,
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    finalize_reflection(payload)
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "delta_metrics": payload["delta_metrics"],
                "state_attribution": {
                    "stock_picker_q4": payload["state_attribution"].get("stock_picker_q4"),
                    "dead_chop_q1": payload["state_attribution"].get("dead_chop_q1"),
                    "per_window": payload["state_attribution"].get("per_window"),
                    "criteria": payload["state_attribution"].get("criteria"),
                },
            },
            indent=2,
            sort_keys=True,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
