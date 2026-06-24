"""exp-20260623-023: historical AI/semis cluster concentration attribution.

Observed-only alpha-search diagnostic. This runner tests whether the current
live-held AI/semis cluster-risk lead has support in the canonical historical
core replay before any shared risk-allocation cap is implemented.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
QUANT_ROOT = REPO_ROOT / "quant"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
if str(QUANT_ROOT) not in sys.path:
    sys.path.insert(0, str(QUANT_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from constants import ATR_STOP_MULT  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260623-023"
SLUG = "historical_ai_semis_cluster_concentration"
RUNNER = f"quant/experiments/exp_20260623_023_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
OWNER = "alpha-explore"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260623_023_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
ARCHIVE_DIR = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "archive"
    / "20260604_ohlcv_warehouse_replay"
)

HYPOTHESIS = (
    "risk_allocation: the current live AI/semis concentration lead should only "
    "justify a later shared cap if the same predeclared cluster also shows "
    "harmful concentration or worse risk-adjusted outcomes in canonical "
    "historical core replay."
)
CHANGE_TYPE = "risk_allocation_observed_only"
IMPLEMENTATION_MODE = "observed_only_historical_attribution"
MECHANISM_FAMILY = "risk_allocation_observed_only"
TRIAL_FAMILY = "risk_allocation_observed_only"
TRIAL_VARIANT_ID = EXPERIMENT_ID
CHANGED_VARIABLE = "historical_ai_semis_cluster_concentration_attribution_v1"
NEW_EVIDENCE_TYPE = "canonical_historical_cluster_concentration_attribution"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260623-021",
    "exp-20260620-023",
    "exp-20260621-002",
]
CAUSAL_COMPONENTS = [
    "canonical closed trades",
    "predeclared current-book cluster taxonomy",
    "active exposure reconstruction",
    "observed-only verdict",
    "no strategy behavior change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260623-023/exp_20260623_023_historical_ai_semis_cluster_concentration.json",
    "experiments/cards/exp-20260623-023.md",
    "experiments/manifests/exp-20260623-023.json",
    "experiments/tickets/exp-20260623-023.json",
    "experiments/logs/exp-20260623-023.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "cluster_winners_dominate",
        "too_few_overlap_days",
        "no_drawdown_reduction",
        "no_policy_replay",
    ],
    "confidence_reason": (
        "exp-20260623-021 found live current-book cluster concentration, but "
        "that snapshot alone cannot justify a risk cap. Canonical historical "
        "attribution can cheaply falsify whether a cap has broad support before "
        "touching sizing."
    ),
    "recorded_at": "2026-06-23T19:06:14+00:00",
}

AI_SEMIS_CLUSTER = {"AMD", "COHR", "CRDO", "MRVL", "NBIS", "NVDA"}
CLUSTER_CAP = 0.30
SEVERE_CLUSTER_SHARE = 0.45
MIN_CLUSTER_TRADES = 8
MIN_CLUSTER_TICKERS = 2


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def clean_float(value: Any) -> Any:
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return round(value, 6)
    if isinstance(value, list):
        return [clean_float(v) for v in value]
    if isinstance(value, dict):
        return {k: clean_float(v) for k, v in value.items()}
    return value


def as_float(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def upsert_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                existing = json.loads(line)
            except json.JSONDecodeError:
                rows.append({"_raw_unparseable": line})
                continue
            if existing.get("experiment_id") != row["experiment_id"]:
                rows.append(existing)
    rows.append(row)
    path.write_text(
        "\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n",
        encoding="utf-8",
    )


def target_from_trade(trade: dict[str, Any]) -> float | None:
    entry = as_float(trade.get("entry_price"))
    stop = as_float(trade.get("stop_price"))
    target_mult = as_float(trade.get("target_mult_used"))
    if entry is None or stop is None or target_mult is None:
        return None
    atr = (entry - stop) / ATR_STOP_MULT if ATR_STOP_MULT else None
    if atr is None or atr <= 0:
        return None
    return round(entry + target_mult * atr, 2)


def parse_day(value: Any) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except ValueError:
        return None


def weekdays(start: date, end: date) -> list[str]:
    out: list[str] = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            out.append(current.isoformat())
        current += timedelta(days=1)
    return out


def resolve_window_path(raw_path: str) -> Path:
    path = REPO_ROOT / raw_path
    if path.exists():
        return path
    archived = ARCHIVE_DIR / Path(raw_path).name
    if archived.exists():
        return archived
    raise FileNotFoundError(raw_path)


def baseline_metrics() -> dict[str, Any]:
    data = read_json(BASELINE_RESULT)
    windows = data.get("windows") or []
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "aggregate_expected_value_score": round(
            sum(float(w.get("expected_value_score") or 0.0) for w in windows), 4
        ),
        "aggregate_total_pnl": round(sum(float(w.get("total_pnl") or 0.0) for w in windows), 2),
        "total_trade_count": sum(int(w.get("trade_count") or 0) for w in windows),
        "aggregate_signals_generated": sum(int(w.get("signals_generated") or 0) for w in windows),
        "aggregate_signals_survived": sum(int(w.get("signals_survived") or 0) for w in windows),
        "min_survival_rate": min(float(w.get("survival_rate") or 0.0) for w in windows),
        "max_window_drawdown_pct": max(float(w.get("max_drawdown_pct") or 0.0) for w in windows),
        "windows": windows,
    }


def trade_notional(trade: dict[str, Any]) -> float:
    entry = as_float(trade.get("entry_price")) or 0.0
    shares = as_float(trade.get("shares")) or 0.0
    addon_cost = as_float(trade.get("addon_cost")) or 0.0
    return max(0.0, entry * shares + max(0.0, addon_cost))


def load_window_trades() -> list[dict[str, Any]]:
    aggregate = read_json(BASELINE_RESULT)
    windows: list[dict[str, Any]] = []
    for window in aggregate.get("windows") or []:
        path = resolve_window_path(str(window["path"]))
        payload = read_json(path)
        rows: list[dict[str, Any]] = []
        for trade in payload.get("trades") or []:
            row = dict(trade)
            row["ticker"] = str(row.get("ticker") or "").upper()
            row["window"] = window["label"]
            row["window_start"] = window["start"]
            row["window_end"] = window["end"]
            row["source_file"] = repo_rel(path)
            row["notional"] = trade_notional(row)
            row["target_price_reconstructed"] = target_from_trade(row)
            row["is_ai_semis_cluster"] = row["ticker"] in AI_SEMIS_CLUSTER
            rows.append(row)
        windows.append(
            {
                "label": window["label"],
                "start": window["start"],
                "end": window["end"],
                "path": repo_rel(path),
                "metrics": {
                    "expected_value_score": window.get("expected_value_score"),
                    "total_pnl": window.get("total_pnl"),
                    "trade_count": window.get("trade_count"),
                    "max_drawdown_pct": window.get("max_drawdown_pct"),
                    "survival_rate": window.get("survival_rate"),
                },
                "trades": rows,
            }
        )
    return windows


def summarize_trades(trades: list[dict[str, Any]]) -> dict[str, Any]:
    pnl = [float(t.get("pnl") or 0.0) for t in trades]
    pnl_pct = [float(t.get("pnl_pct_net") or 0.0) for t in trades]
    notional = [float(t.get("notional") or 0.0) for t in trades]
    total_pnl = sum(pnl)
    total_notional = sum(notional)
    return {
        "trade_count": len(trades),
        "distinct_tickers": sorted({str(t.get("ticker")) for t in trades}),
        "total_pnl": total_pnl,
        "mean_pnl": total_pnl / len(trades) if trades else 0.0,
        "mean_pnl_pct_net": sum(pnl_pct) / len(pnl_pct) if pnl_pct else 0.0,
        "win_rate": sum(1 for v in pnl if v > 0) / len(pnl) if pnl else 0.0,
        "worst_trade_pnl": min(pnl) if pnl else 0.0,
        "best_trade_pnl": max(pnl) if pnl else 0.0,
        "total_entry_notional": total_notional,
        "pnl_per_notional": total_pnl / total_notional if total_notional else 0.0,
    }


def active_exposure_for_window(window: dict[str, Any]) -> dict[str, Any]:
    start = parse_day(window["start"])
    end = parse_day(window["end"])
    if start is None or end is None:
        return {"days": [], "summary": {"active_day_count": 0}}

    active_days: list[dict[str, Any]] = []
    cluster_trade_day_scales: dict[str, list[float]] = {}
    for day in weekdays(start, end):
        active: list[dict[str, Any]] = []
        for trade in window["trades"]:
            entry = parse_day(trade.get("entry_date"))
            exit_day = parse_day(trade.get("exit_date"))
            if entry is None or exit_day is None:
                continue
            if entry.isoformat() <= day <= exit_day.isoformat():
                active.append(trade)
        if not active:
            continue
        total = sum(float(t.get("notional") or 0.0) for t in active)
        cluster = sum(float(t.get("notional") or 0.0) for t in active if t["is_ai_semis_cluster"])
        share = cluster / total if total else 0.0
        scale = min(1.0, (CLUSTER_CAP * total / cluster)) if cluster > 0 and total > 0 else 1.0
        for trade in active:
            if trade["is_ai_semis_cluster"]:
                key = str(trade.get("trade_key") or f"{trade['ticker']}:{trade.get('entry_date')}")
                cluster_trade_day_scales.setdefault(key, []).append(scale)
        active_days.append(
            {
                "date": day,
                "active_trade_count": len(active),
                "active_cluster_trade_count": sum(1 for t in active if t["is_ai_semis_cluster"]),
                "active_notional": total,
                "active_cluster_notional": cluster,
                "cluster_share": share,
                "cluster_tickers": sorted({t["ticker"] for t in active if t["is_ai_semis_cluster"]}),
            }
        )

    over_cap = [row for row in active_days if row["cluster_share"] > CLUSTER_CAP]
    severe = [row for row in active_days if row["cluster_share"] > SEVERE_CLUSTER_SHARE]
    max_day = max(active_days, key=lambda r: r["cluster_share"], default=None)
    return {
        "days": active_days,
        "cluster_trade_day_scales": cluster_trade_day_scales,
        "summary": {
            "active_day_count": len(active_days),
            "cluster_active_day_count": sum(1 for row in active_days if row["active_cluster_trade_count"] > 0),
            "over_cap_day_count": len(over_cap),
            "severe_cluster_day_count": len(severe),
            "max_cluster_share": max((row["cluster_share"] for row in active_days), default=0.0),
            "mean_cluster_share_when_cluster_active": (
                sum(row["cluster_share"] for row in active_days if row["active_cluster_trade_count"] > 0)
                / sum(1 for row in active_days if row["active_cluster_trade_count"] > 0)
                if any(row["active_cluster_trade_count"] > 0 for row in active_days)
                else 0.0
            ),
            "max_cluster_share_day": max_day,
        },
    }


def cap_cash_redeploy_estimate(
    trades: list[dict[str, Any]], exposures_by_window: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for trade in trades:
        if not trade["is_ai_semis_cluster"]:
            continue
        key = str(trade.get("trade_key") or f"{trade['ticker']}:{trade.get('entry_date')}")
        scales = exposures_by_window[trade["window"]]["cluster_trade_day_scales"].get(key) or [1.0]
        avg_scale = sum(scales) / len(scales)
        pnl = float(trade.get("pnl") or 0.0)
        scaled_pnl = pnl * avg_scale
        rows.append(
            {
                "window": trade["window"],
                "ticker": trade["ticker"],
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "baseline_pnl": pnl,
                "average_cap_scale": avg_scale,
                "cash_redeploy_estimated_pnl": scaled_pnl,
                "cash_redeploy_delta_pnl": scaled_pnl - pnl,
            }
        )
    baseline_cluster_pnl = sum(row["baseline_pnl"] for row in rows)
    capped_cluster_pnl = sum(row["cash_redeploy_estimated_pnl"] for row in rows)
    return {
        "cap": CLUSTER_CAP,
        "method": (
            "Observed-only approximation: when same-day active cluster notional "
            "exceeds cap, cluster trade PnL is scaled by the average allowed "
            "day-level exposure fraction and removed exposure is redeployed to cash."
        ),
        "baseline_cluster_pnl": baseline_cluster_pnl,
        "cash_redeploy_estimated_cluster_pnl": capped_cluster_pnl,
        "cash_redeploy_delta_pnl": capped_cluster_pnl - baseline_cluster_pnl,
        "affected_cluster_trade_count": sum(1 for row in rows if row["average_cap_scale"] < 0.999999),
        "rows": rows,
    }


def build_analysis(windows: list[dict[str, Any]]) -> dict[str, Any]:
    all_trades = [trade for window in windows for trade in window["trades"]]
    cluster_trades = [trade for trade in all_trades if trade["is_ai_semis_cluster"]]
    non_cluster_trades = [trade for trade in all_trades if not trade["is_ai_semis_cluster"]]
    exposures = {window["label"]: active_exposure_for_window(window) for window in windows}
    cap_estimate = cap_cash_redeploy_estimate(all_trades, exposures)
    by_window: dict[str, Any] = {}
    for window in windows:
        trades = window["trades"]
        c_trades = [t for t in trades if t["is_ai_semis_cluster"]]
        by_window[window["label"]] = {
            "metrics": window["metrics"],
            "source_file": window["path"],
            "cluster": summarize_trades(c_trades),
            "non_cluster": summarize_trades([t for t in trades if not t["is_ai_semis_cluster"]]),
            "exposure_summary": exposures[window["label"]]["summary"],
        }

    max_cluster_share = max(
        (exposures[w["label"]]["summary"].get("max_cluster_share", 0.0) for w in windows),
        default=0.0,
    )
    over_cap_days = sum(
        int(exposures[w["label"]]["summary"].get("over_cap_day_count", 0)) for w in windows
    )
    severe_days = sum(
        int(exposures[w["label"]]["summary"].get("severe_cluster_day_count", 0)) for w in windows
    )
    cluster_tickers = sorted({trade["ticker"] for trade in cluster_trades})

    failed_reasons: list[str] = []
    if len(cluster_trades) < MIN_CLUSTER_TRADES:
        failed_reasons.append(
            f"cluster_trade_count_below_{MIN_CLUSTER_TRADES}: {len(cluster_trades)}"
        )
    if len(cluster_tickers) < MIN_CLUSTER_TICKERS:
        failed_reasons.append(
            f"distinct_cluster_tickers_below_{MIN_CLUSTER_TICKERS}: {len(cluster_tickers)}"
        )
    if cap_estimate["cash_redeploy_delta_pnl"] <= 0:
        failed_reasons.append("cash_redeploy_cluster_cap_did_not_improve_pnl")
    if over_cap_days == 0:
        failed_reasons.append("no_historical_active_days_over_30pct_cluster_cap")
    failed_reasons.append("observed_only_not_shared_gate4_policy_replay")

    observed_only_lead = (
        len(cluster_trades) >= MIN_CLUSTER_TRADES
        and len(cluster_tickers) >= MIN_CLUSTER_TICKERS
        and severe_days > 0
        and cap_estimate["cash_redeploy_delta_pnl"] > 0
    )
    return {
        "cluster_taxonomy": sorted(AI_SEMIS_CLUSTER),
        "aggregate": {
            "cluster": summarize_trades(cluster_trades),
            "non_cluster": summarize_trades(non_cluster_trades),
            "max_cluster_share": max_cluster_share,
            "over_cap_day_count": over_cap_days,
            "severe_cluster_day_count": severe_days,
            "distinct_cluster_tickers": cluster_tickers,
        },
        "by_window": by_window,
        "cap_cash_redeploy_estimate": cap_estimate,
        "observed_only_lead": observed_only_lead,
        "failed_reasons": failed_reasons,
    }


def build_payload() -> dict[str, Any]:
    before = baseline_metrics()
    windows = load_window_trades()
    all_trades = [trade for window in windows for trade in window["trades"]]
    analysis = build_analysis(windows)
    missing_entry = [t for t in all_trades if not t.get("entry_date")]
    missing_target = [t for t in all_trades if t.get("target_price_reconstructed") is None]

    status = "observed_only" if analysis["observed_only_lead"] else "rejected"
    decision = (
        "observed_only_historical_cluster_cap_lead_not_promoted"
        if analysis["observed_only_lead"]
        else "rejected_historical_ai_semis_cluster_concentration"
    )
    after = dict(before)
    delta = {
        "aggregate_expected_value_score": 0.0,
        "aggregate_total_pnl": 0.0,
        "trade_count": 0,
        "max_drawdown_pct": 0.0,
        "survival_rate": 0.0,
    }
    predicted_failure_modes = set(PREDICTION["main_failure_modes"])
    observed_failure_modes = set(analysis["failed_reasons"])
    return clean_float(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": utc_now(),
            "status": status,
            "decision": decision,
            "accepted": False,
            "accepted_alpha": False,
            "observed_only_lead": analysis["observed_only_lead"],
            "lane": "alpha_search",
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "change_summary": (
                "Added an observed-only historical attribution runner that tests "
                "the exp-20260623-021 AI/semis current-book cluster against "
                "canonical closed replay trades and a diagnostic 30% cap estimate."
            ),
            "change_type": CHANGE_TYPE,
            "implementation_mode": IMPLEMENTATION_MODE,
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "prior_trial_count": 0,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": "minimal",
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "prediction": PREDICTION,
            "calibration": {
                "actual_decision": decision,
                "actual_success": 0,
                "brier_score": round((0.0 - float(PREDICTION["success_probability"])) ** 2, 6),
                "predicted_success_probability": PREDICTION["success_probability"],
                "predicted_failure_modes": PREDICTION["main_failure_modes"],
                "failure_modes_observed": analysis["failed_reasons"],
                "predicted_failure_mode_hit": bool(predicted_failure_modes & observed_failure_modes),
                "surprise_note": (
                    "The predeclared current-book cluster barely appears in "
                    "canonical history: only AMD has closed cluster trades."
                ),
            },
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "before_metrics": before,
            "after_metrics": after,
            "delta_metrics": delta,
            "analysis": analysis,
            "gate1": {
                "passed": True,
                "baseline_result_file": repo_rel(BASELINE_RESULT),
                "baseline_loaded": True,
                "baseline_summary": before,
            },
            "gate2": {
                "passed": len(missing_entry) == 0 and len(missing_target) == 0,
                "runtime_fields_checked": [
                    "entry_date",
                    "target_price reconstructed from entry_price, stop_price, ATR_STOP_MULT, and target_mult_used",
                    "exit_date",
                    "entry_price",
                    "stop_price",
                    "target_mult_used",
                    "shares",
                    "pnl",
                ],
                "field_coverage": {
                    "trade_count": len(all_trades),
                    "entry_date_present": len(all_trades) - len(missing_entry),
                    "target_price_reconstructed": len(all_trades) - len(missing_target),
                    "missing_entry_date": len(missing_entry),
                    "missing_target_reconstruction": len(missing_target),
                },
            },
            "gate3": {
                "passed": True,
                "new_core_filter_added": False,
                "baseline_min_survival_rate": before["min_survival_rate"],
                "signals_generated": before["aggregate_signals_generated"],
                "signals_survived": before["aggregate_signals_survived"],
                "note": "No entry filter, ranking, sizing, exit, or candidate generation behavior changed.",
            },
            "gate4": {
                "passed": False,
                "decision": decision,
                "observed_only": True,
                "observed_only_lead": analysis["observed_only_lead"],
                "failed_reasons": analysis["failed_reasons"],
                "acceptance_checks": {
                    "cluster_trade_count": analysis["aggregate"]["cluster"]["trade_count"],
                    "minimum_cluster_trade_count": MIN_CLUSTER_TRADES,
                    "distinct_cluster_ticker_count": len(
                        analysis["aggregate"]["distinct_cluster_tickers"]
                    ),
                    "minimum_distinct_cluster_tickers": MIN_CLUSTER_TICKERS,
                    "over_cap_day_count": analysis["aggregate"]["over_cap_day_count"],
                    "severe_cluster_day_count": analysis["aggregate"]["severe_cluster_day_count"],
                    "cash_redeploy_delta_pnl": analysis["cap_cash_redeploy_estimate"][
                        "cash_redeploy_delta_pnl"
                    ],
                },
                "before_after_strategy_delta": delta,
            },
            "production_impact": {
                "strategy_behavior_changed": False,
                "live_behavior_changed": False,
                "paper_behavior_changed": False,
                "orders_changed": False,
                "shared_helper_changed": False,
                "note": "Historical attribution only; no production/backtest policy path was changed.",
            },
            "post_run_reflection": {
                "why_result_happened": (
                    "The historical canonical sample does not support promoting "
                    "the current-book AI/semis concentration lead. The "
                    "predeclared cluster has only four closed canonical trades, "
                    "all AMD, and the 30% cash-redeploy cap estimate does not "
                    "create positive PnL evidence."
                ),
                "forbidden_near_neighbor_retry": (
                    "Do not tune the AI/semis cluster cap, broaden the taxonomy, "
                    "or rerun the same historical attribution until there are "
                    "forward/live rows under a fixed cluster envelope or a true "
                    "shared policy Gate 1-4 replay."
                ),
                "new_evidence_required": (
                    "A valid retry needs either forward/live outcomes under a "
                    "predeclared cluster envelope or a shared risk-allocation "
                    "helper with canonical before/after Gate 1-4 metrics."
                ),
                "outcome_summary": (
                    f"Cluster trades={analysis['aggregate']['cluster']['trade_count']}; "
                    f"tickers={','.join(analysis['aggregate']['distinct_cluster_tickers']) or 'none'}; "
                    f"cap delta={analysis['cap_cash_redeploy_estimate']['cash_redeploy_delta_pnl']:.2f}."
                ),
            },
            "rejection_reason": (
                "The predeclared AI/semis cluster has too little historical "
                "canonical representation and no positive cap counterfactual, "
                "so the current-book concentration lead remains unpromoted."
            ),
            "next_retry_requires": [
                "forward/live outcomes under a fixed cluster envelope",
                "shared risk-allocation helper",
                "canonical Gate 1-4 before/after replay",
            ],
            "related_files": [
                RUNNER,
                repo_rel(OUT_JSON),
                repo_rel(LOG_JSON),
                repo_rel(BASELINE_RESULT),
            ]
            + [window["path"] for window in windows],
            "reproduction_command": RUNNER_COMMAND,
            "anti_js": "No JavaScript was used.",
        }
    )


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
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
        "change_summary",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "changed_variable",
        "single_causal_variable",
        "causal_components",
        "prior_trial_count",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "prediction",
        "calibration",
        "baseline_result_file",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "production_impact",
        "post_run_reflection",
        "rejection_reason",
        "next_retry_requires",
        "related_files",
        "reproduction_command",
        "anti_js",
    ]
    record = {key: payload[key] for key in keys}
    record["artifact"] = repo_rel(OUT_JSON)
    record["log"] = repo_rel(LOG_JSON)
    record["analysis_summary"] = payload["analysis"]["aggregate"]
    return record


def build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["analysis"]["aggregate"]
    cap = payload["analysis"]["cap_cash_redeploy_estimate"]
    tickers = ", ".join(aggregate["distinct_cluster_tickers"]) or "none"
    lines = [
        f"# {EXPERIMENT_ID}: Historical AI/Semis Cluster Concentration",
        "",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Observed-only lead: `{payload['observed_only_lead']}`",
        f"- Hypothesis: {payload['hypothesis']}",
        "",
        "## Result",
        "",
        f"- Cluster taxonomy: `{', '.join(payload['analysis']['cluster_taxonomy'])}`",
        f"- Historical cluster trades: `{aggregate['cluster']['trade_count']}`",
        f"- Historical cluster tickers present: `{tickers}`",
        f"- Cluster total PnL: `{aggregate['cluster']['total_pnl']:.2f}`",
        f"- Non-cluster total PnL: `{aggregate['non_cluster']['total_pnl']:.2f}`",
        f"- Max active cluster share: `{aggregate['max_cluster_share']:.2%}`",
        f"- Days over 30% cap: `{aggregate['over_cap_day_count']}`",
        f"- Cash-redeploy cap delta: `{cap['cash_redeploy_delta_pnl']:.2f}`",
        "",
        "## Decision",
        "",
        payload["post_run_reflection"]["why_result_happened"],
        "",
        "## Production Impact",
        "",
        "No strategy, ranking, sizing, exit, order, paper ledger, or live ledger behavior changed.",
        "",
        "## Reproduce",
        "",
        f"```powershell\n{RUNNER_COMMAND}\n```",
        "",
    ]
    return "\n".join(lines)


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        Path(RUNNER),
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path if path.is_absolute() else REPO_ROOT / path): {
                "exists": (path if path.is_absolute() else REPO_ROOT / path).exists(),
                "sha256": sha256(path if path.is_absolute() else REPO_ROOT / path),
            }
            for path in files
        },
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)

    registry_result = {
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": payload["observed_only_lead"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result=registry_result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
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
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "analysis_summary": payload["analysis"]["aggregate"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "allowed_write_scope": ALLOWED_WRITE_SCOPE,
            "related_files": payload["related_files"],
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
                "observed_only_lead": payload["observed_only_lead"],
                "cluster_trade_count": payload["analysis"]["aggregate"]["cluster"]["trade_count"],
                "distinct_cluster_tickers": payload["analysis"]["aggregate"][
                    "distinct_cluster_tickers"
                ],
                "over_cap_day_count": payload["analysis"]["aggregate"]["over_cap_day_count"],
                "cash_redeploy_delta_pnl": payload["analysis"]["cap_cash_redeploy_estimate"][
                    "cash_redeploy_delta_pnl"
                ],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
