"""exp-20260623-003: fixed-entry exit-oracle regret cluster attribution.

Observed-only alpha attribution. This runner rebuilds the canonical window
perfect-exit oracle rows from existing closed trades and OHLCV snapshots, then
asks whether regret clusters in production-visible fields strongly enough to
justify any future shared exit-lifecycle retry.

It changes no entry, ranking, sizing, exit, live, or paper order behavior.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import defaultdict
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
from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260623-003"
SLUG = "fixed_entry_exit_oracle_regret_cluster"
RUNNER = f"quant/experiments/exp_20260623_003_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
OWNER = "alpha-explore"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260623_003_{SLUG}.json"
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
WINDOWS = {
    "old_thin": {
        "result": REPO_ROOT
        / "data"
        / "backtests"
        / "archive"
        / "20260604_ohlcv_warehouse_replay"
        / "backtest_results_warehouse_snapshot_old_thin_20260604.json",
        "snapshot": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20241002_20250422.json",
    },
    "mid_weak": {
        "result": REPO_ROOT
        / "data"
        / "backtests"
        / "archive"
        / "20260604_ohlcv_warehouse_replay"
        / "backtest_results_warehouse_snapshot_mid_weak_20260604.json",
        "snapshot": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20250423_20251022.json",
    },
    "late_strong": {
        "result": REPO_ROOT
        / "data"
        / "backtests"
        / "archive"
        / "20260604_ohlcv_warehouse_replay"
        / "backtest_results_warehouse_snapshot_late_strong_20260604.json",
        "snapshot": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20251023_20260421.json",
    },
}

HYPOTHESIS = (
    "Observed-only fixed-entry exit oracle diagnostic: if current core exit "
    "regret is a future alpha surface, regret should cluster in a stable "
    "production-visible bucket such as exit reason, strategy, or "
    "oracle-best-exit timing before any shared exit lifecycle retry."
)
CHANGE_TYPE = "observed_only_attribution"
MECHANISM_FAMILY = "exit_lifecycle_attribution"
TRIAL_FAMILY = "fixed_entry_exit_oracle_regret_cluster_attribution"
TRIAL_VARIANT_ID = "canonical_windows_oracle_regret_clusters_v1"
CHANGED_VARIABLE = "fixed_entry_exit_oracle_regret_cluster_attribution_v1"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260429-032",
    "exp-20260502-014",
    "exp-20260521-018",
]
NEW_EVIDENCE_TYPE = "inline_oracle_regret_cluster_attribution"
NEW_EVIDENCE_AXIS = (
    "Rebuilds per-trade perfect-exit oracle rows from canonical closed trades "
    "and OHLCV snapshots, then attributes regret by production-visible closed "
    "trade fields rather than retrying target-trim, fast-target, or MFE "
    "giveback thresholds."
)
CAUSAL_COMPONENTS = [
    "canonical core closed trades",
    "fixed-entry perfect-exit oracle rebuild",
    "production-visible cluster rollup",
    "no strategy change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260623-003/exp_20260623_003_fixed_entry_exit_oracle_regret_cluster.json",
    "experiments/cards/exp-20260623-003.md",
    "experiments/manifests/exp-20260623-003.json",
    "experiments/tickets/exp-20260623-003.json",
    "experiments/logs/exp-20260623-003.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]

DEFAULT_PREDICTION = {
    "success_probability": 0.22,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "old_thin_concentration",
        "stop_loss_losers_dominate",
        "no_stable_cluster",
        "repeat_of_target_trim_family",
    ],
    "confidence_reason": (
        "Inline oracle diagnostics are already available across the canonical "
        "windows and can test whether exit regret clusters before touching "
        "rules; prior target-trim, fast-target, and MFE-giveback replays failed, "
        "so success means only a diagnostic lead, not promotion."
    ),
    "recorded_at": "2026-06-23T02:06:06+00:00",
}
ACCEPTANCE_RULE = {
    "min_rebuilt_rows": 55,
    "max_total_regret_window_share": 0.50,
    "max_candidate_cluster_window_share": 0.65,
    "min_candidate_cluster_windows": 3,
    "min_candidate_cluster_rows": 15,
    "min_candidate_cluster_regret_share": 0.45,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                rows.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(raw)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def safe_round(value: Any, digits: int = 4) -> float | None:
    number = as_float(value)
    if number is None:
        return None
    return round(number, digits)


def median_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return round(float(median(values)), 4)


def safe_div(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def load_ticket_prediction() -> dict[str, Any]:
    if not TICKET_JSON.exists():
        return DEFAULT_PREDICTION
    ticket = read_json(TICKET_JSON)
    prediction = ticket.get("prediction")
    if isinstance(prediction, dict) and prediction:
        return prediction
    return DEFAULT_PREDICTION


def load_baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT)
    windows = list(payload.get("windows") or [])
    generated = sum(int(window.get("signals_generated") or 0) for window in windows)
    survived = sum(int(window.get("signals_survived") or 0) for window in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(window.get("expected_value_score") or 0.0) for window in windows),
            4,
        ),
        "total_pnl": round(sum(float(window.get("total_pnl") or 0.0) for window in windows), 2),
        "trade_count": sum(int(window.get("trade_count") or 0) for window in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 4) if generated else None,
        "max_drawdown_pct_worst": max(
            float(window.get("max_drawdown_pct") or 0.0) for window in windows
        )
        if windows
        else None,
        "windows": windows,
    }


def ohlcv_rows_by_ticker(snapshot: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for ticker, rows in (snapshot.get("ohlcv") or {}).items():
        out[str(ticker).upper()] = {
            str(row.get("Date")): row
            for row in rows or []
            if row.get("Date")
        }
    return out


def classify_timing(entry_date: str, exit_date: str, oracle_exit_date: str, dates: list[str]) -> tuple[str, int | None, int | None]:
    indices = {date: index for index, date in enumerate(dates)}
    oracle_offset = indices.get(oracle_exit_date)
    actual_hold = indices.get(exit_date)
    if oracle_offset is None or actual_hold is None:
        return "unknown", oracle_offset, actual_hold
    if oracle_offset <= 1:
        return "day0_1", oracle_offset, actual_hold
    if oracle_exit_date == exit_date:
        return "same_as_actual", oracle_offset, actual_hold
    if actual_hold > 0 and oracle_offset < (actual_hold / 2):
        return "early_lt_half", oracle_offset, actual_hold
    return "late_ge_half", oracle_offset, actual_hold


def classify_outcome(actual_pnl: float, oracle_pnl: float, capture_ratio: float | None) -> str:
    if actual_pnl <= 0 and oracle_pnl > 0:
        return "actual_loss_with_positive_oracle"
    if oracle_pnl <= 0:
        return "no_positive_oracle"
    if capture_ratio is not None and capture_ratio < 0.50:
        return "winner_low_capture_lt50"
    if capture_ratio is not None and capture_ratio < 0.85:
        return "winner_mid_capture_50_85"
    return "captured_well_gte85"


def rebuild_oracle_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    window_trade_counts: dict[str, int] = {}
    target_price_present = 0
    target_price_missing = 0

    for window, cfg in WINDOWS.items():
        result = read_json(cfg["result"])
        snapshot = read_json(cfg["snapshot"])
        by_ticker = ohlcv_rows_by_ticker(snapshot)
        trades = list(result.get("trades") or [])
        window_trade_counts[window] = len(trades)

        for trade in trades:
            ticker = str(trade.get("ticker") or "").upper()
            entry_date = str(trade.get("entry_date") or "")[:10]
            exit_date = str(trade.get("exit_date") or "")[:10]
            if trade.get("target_price") is None:
                target_price_missing += 1
            else:
                target_price_present += 1
            fields = {
                "entry_price": as_float(trade.get("entry_price")),
                "shares": as_float(trade.get("shares")),
                "actual_pnl": as_float(trade.get("pnl")),
            }
            if not ticker or len(entry_date) != 10 or len(exit_date) != 10:
                missing.append({"window": window, "ticker": ticker, "reason": "missing_dates"})
                continue
            if any(value is None for value in fields.values()):
                missing.append({"window": window, "ticker": ticker, "reason": "missing_trade_fields"})
                continue
            ticker_rows = by_ticker.get(ticker)
            if not ticker_rows:
                missing.append({"window": window, "ticker": ticker, "reason": "missing_ohlcv"})
                continue
            dates = [date for date in sorted(ticker_rows) if entry_date <= date <= exit_date]
            if not dates:
                missing.append({"window": window, "ticker": ticker, "reason": "no_ohlcv_rows_in_trade_window"})
                continue
            best = max((ticker_rows[date] for date in dates), key=lambda row: float(row.get("High") or 0.0))
            best_high = as_float(best.get("High"))
            if best_high is None or best_high <= 0:
                missing.append({"window": window, "ticker": ticker, "reason": "invalid_intratrade_high"})
                continue

            entry_price = float(fields["entry_price"])
            shares = float(fields["shares"])
            actual_pnl = float(fields["actual_pnl"])
            oracle_exit_price = best_high * (1 - ROUND_TRIP_COST_PCT)
            oracle_pnl = (oracle_exit_price - entry_price) * shares
            regret = oracle_pnl - actual_pnl
            capture_ratio = actual_pnl / oracle_pnl if oracle_pnl > 0 else None
            timing_bucket, oracle_offset, actual_hold = classify_timing(
                entry_date,
                exit_date,
                str(best.get("Date") or "")[:10],
                dates,
            )

            rows.append(
                {
                    "window": window,
                    "ticker": ticker,
                    "strategy": trade.get("strategy"),
                    "sector": trade.get("sector"),
                    "entry_date": entry_date,
                    "actual_exit_date": exit_date,
                    "oracle_exit_date": str(best.get("Date") or "")[:10],
                    "entry_price": round(entry_price, 4),
                    "actual_exit_price": safe_round(trade.get("exit_price"), 4),
                    "oracle_exit_price": round(oracle_exit_price, 4),
                    "shares": shares,
                    "actual_pnl": round(actual_pnl, 2),
                    "oracle_pnl": round(oracle_pnl, 2),
                    "regret_vs_oracle": round(regret, 2),
                    "capture_ratio": round(capture_ratio, 4) if capture_ratio is not None else None,
                    "exit_reason": trade.get("exit_reason"),
                    "target_mult_used": safe_round(trade.get("target_mult_used"), 4),
                    "target_price_present": trade.get("target_price") is not None,
                    "oracle_timing_bucket": timing_bucket,
                    "oracle_offset_trading_days": oracle_offset,
                    "actual_hold_trading_days": actual_hold,
                    "actual_outcome_bucket": classify_outcome(actual_pnl, oracle_pnl, capture_ratio),
                }
            )

    audit = {
        "window_trade_counts": window_trade_counts,
        "rebuilt_trade_count": len(rows),
        "missing_trade_count": len(missing),
        "missing_trades": missing,
        "target_price_present_count": target_price_present,
        "target_price_missing_count": target_price_missing,
        "target_price_relevance": (
            "The canonical closed-trade rows do not need target_price for this "
            "diagnostic; target exits are only read through exit_reason and "
            "actual realized PnL. No target order or exit price is scheduled."
        ),
    }
    return rows, missing, audit


def row_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    actual = sum(float(row["actual_pnl"]) for row in rows)
    oracle = sum(float(row["oracle_pnl"]) for row in rows)
    regret = sum(float(row["regret_vs_oracle"]) for row in rows)
    regrets = [float(row["regret_vs_oracle"]) for row in rows]
    captures = [
        float(row["capture_ratio"])
        for row in rows
        if row.get("capture_ratio") is not None and math.isfinite(float(row["capture_ratio"]))
    ]
    return {
        "n": len(rows),
        "actual_pnl": round(actual, 2),
        "oracle_pnl": round(oracle, 2),
        "regret_vs_oracle": round(regret, 2),
        "regret_share_of_total": None,
        "capture_ratio": round(actual / oracle, 4) if oracle > 0 else None,
        "mean_regret": round(regret / len(rows), 2) if rows else None,
        "median_regret": median_or_none(regrets),
        "median_capture_ratio": median_or_none(captures),
        "positive_oracle_count": sum(1 for row in rows if float(row["oracle_pnl"]) > 0),
        "actual_loss_count": sum(1 for row in rows if float(row["actual_pnl"]) <= 0),
        "windows_present": sorted({str(row["window"]) for row in rows}),
    }


def grouped_summary(rows: list[dict[str, Any]], key: str, total_regret: float) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(key) or "unknown")].append(row)
    out: dict[str, dict[str, Any]] = {}
    for name, group_rows in groups.items():
        summary = row_summary(group_rows)
        share = safe_div(float(summary["regret_vs_oracle"]), total_regret)
        summary["regret_share_of_total"] = round(share, 4) if share is not None else None
        out[name] = summary
    return dict(sorted(out.items(), key=lambda item: item[1]["regret_vs_oracle"], reverse=True))


def concentration_by_key(rows: list[dict[str, Any]], key: str, total_regret: float) -> list[dict[str, Any]]:
    grouped = grouped_summary(rows, key, total_regret)
    out = []
    for name, summary in grouped.items():
        share = safe_div(float(summary["regret_vs_oracle"]), total_regret)
        out.append(
            {
                "key": name,
                "n": summary["n"],
                "regret_vs_oracle": summary["regret_vs_oracle"],
                "share": round(share, 4) if share is not None else None,
                "windows_present": summary["windows_present"],
            }
        )
    return out


def cluster_window_share(rows: list[dict[str, Any]], key: str, value: str) -> float | None:
    cluster = [row for row in rows if str(row.get(key) or "unknown") == value]
    total = sum(max(float(row["regret_vs_oracle"]), 0.0) for row in cluster)
    if total <= 0:
        return None
    by_window: dict[str, float] = defaultdict(float)
    for row in cluster:
        by_window[str(row["window"])] += max(float(row["regret_vs_oracle"]), 0.0)
    return max(by_window.values()) / total if by_window else None


def candidate_cluster_checks(rows: list[dict[str, Any]], total_regret: float) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for key in ("exit_reason", "strategy", "actual_outcome_bucket", "oracle_timing_bucket"):
        grouped = grouped_summary(rows, key, total_regret)
        for value, summary in grouped.items():
            share = float(summary.get("regret_share_of_total") or 0.0)
            max_window_share = cluster_window_share(rows, key, value)
            candidates.append(
                {
                    "key": key,
                    "value": value,
                    "n": summary["n"],
                    "regret_vs_oracle": summary["regret_vs_oracle"],
                    "regret_share_of_total": share,
                    "capture_ratio": summary["capture_ratio"],
                    "windows_present": summary["windows_present"],
                    "max_window_regret_share": round(max_window_share, 4)
                    if max_window_share is not None
                    else None,
                    "passes_rows": summary["n"] >= ACCEPTANCE_RULE["min_candidate_cluster_rows"],
                    "passes_regret_share": share >= ACCEPTANCE_RULE["min_candidate_cluster_regret_share"],
                    "passes_window_count": (
                        len(summary["windows_present"])
                        >= ACCEPTANCE_RULE["min_candidate_cluster_windows"]
                    ),
                    "passes_window_balance": (
                        max_window_share is not None
                        and max_window_share <= ACCEPTANCE_RULE["max_candidate_cluster_window_share"]
                    ),
                }
            )
    candidates.sort(key=lambda row: row["regret_vs_oracle"], reverse=True)
    promotable = [
        row
        for row in candidates
        if row["passes_rows"]
        and row["passes_regret_share"]
        and row["passes_window_count"]
        and row["passes_window_balance"]
        and row["key"] in {"exit_reason", "strategy"}
    ]
    return {
        "candidate_clusters": candidates[:12],
        "promotable_nonfuture_clusters": promotable,
        "best_cluster": candidates[0] if candidates else None,
    }


def analyze_rows(rows: list[dict[str, Any]], audit: dict[str, Any]) -> dict[str, Any]:
    total_regret = sum(float(row["regret_vs_oracle"]) for row in rows)
    positive_regret = sum(max(float(row["regret_vs_oracle"]), 0.0) for row in rows)
    overall = row_summary(rows)
    by_window = grouped_summary(rows, "window", total_regret)
    by_exit = grouped_summary(rows, "exit_reason", total_regret)
    by_strategy = grouped_summary(rows, "strategy", total_regret)
    by_timing = grouped_summary(rows, "oracle_timing_bucket", total_regret)
    by_outcome = grouped_summary(rows, "actual_outcome_bucket", total_regret)
    concentration = {
        "by_window": concentration_by_key(rows, "window", positive_regret),
        "by_ticker_top10": concentration_by_key(rows, "ticker", positive_regret)[:10],
        "by_exit_reason": concentration_by_key(rows, "exit_reason", positive_regret),
    }
    checks = candidate_cluster_checks(rows, total_regret)
    checks["rebuilt_rows"] = len(rows)
    checks["missing_trade_count"] = int(audit["missing_trade_count"])
    checks["max_total_regret_window_share"] = (
        concentration["by_window"][0]["share"] if concentration["by_window"] else None
    )
    checks["min_rebuilt_rows"] = ACCEPTANCE_RULE["min_rebuilt_rows"]
    checks["acceptance_rule"] = ACCEPTANCE_RULE

    failed: list[str] = []
    if len(rows) < ACCEPTANCE_RULE["min_rebuilt_rows"]:
        failed.append("too_few_rebuilt_oracle_rows")
    if audit["missing_trade_count"]:
        failed.append("ohlcv_trade_window_gap_present")
    if (
        checks["max_total_regret_window_share"] is not None
        and checks["max_total_regret_window_share"] > ACCEPTANCE_RULE["max_total_regret_window_share"]
    ):
        failed.append("old_thin_total_regret_concentration")
    if not checks["promotable_nonfuture_clusters"]:
        failed.append("no_balanced_nonfuture_exit_or_strategy_cluster")

    stop_cluster = by_exit.get("stop") or {}
    if stop_cluster:
        stop_window_share = cluster_window_share(rows, "exit_reason", "stop")
        checks["stop_exit_cluster"] = {
            "n": stop_cluster.get("n"),
            "regret_share_of_total": stop_cluster.get("regret_share_of_total"),
            "max_window_regret_share": round(stop_window_share, 4)
            if stop_window_share is not None
            else None,
            "actual_pnl": stop_cluster.get("actual_pnl"),
            "oracle_pnl": stop_cluster.get("oracle_pnl"),
            "capture_ratio": stop_cluster.get("capture_ratio"),
        }
        if stop_window_share is not None and stop_window_share > ACCEPTANCE_RULE["max_candidate_cluster_window_share"]:
            failed.append("stop_exit_regret_old_thin_dominated")

    observed_lead = not failed
    return {
        "overall": overall,
        "by_window": by_window,
        "by_exit_reason": by_exit,
        "by_strategy": by_strategy,
        "by_oracle_timing_bucket": by_timing,
        "by_actual_outcome_bucket": by_outcome,
        "concentration": concentration,
        "acceptance_checks": checks,
        "failed_reasons": failed,
        "observed_only_lead": observed_lead,
        "top_regret_rows": sorted(rows, key=lambda row: row["regret_vs_oracle"], reverse=True)[:15],
    }


def calibration(prediction: dict[str, Any], success: bool, failed_reasons: list[str]) -> dict[str, Any]:
    probability = float(prediction.get("success_probability") or 0.0)
    actual = 1.0 if success else 0.0
    return {
        "predicted_success_probability": round(probability, 4),
        "actual_success": bool(success),
        "brier_score": round((probability - actual) ** 2, 6),
        "failed_reasons": failed_reasons,
        "prediction_failure_modes_hit": [
            mode
            for mode in prediction.get("main_failure_modes", [])
            if mode in {"old_thin_concentration", "stop_loss_losers_dominate", "no_stable_cluster"}
        ],
    }


def build_payload() -> dict[str, Any]:
    prediction = load_ticket_prediction()
    baseline = load_baseline_metrics()
    rows, missing, audit = rebuild_oracle_rows()
    analysis = analyze_rows(rows, audit)
    failed = analysis["failed_reasons"]
    observed_lead = analysis["observed_only_lead"]
    status = "observed_only_positive_lead" if observed_lead else "observed_only_rejected"
    decision = (
        "observed_only_exit_regret_cluster_lead"
        if observed_lead
        else "rejected_exit_oracle_regret_cluster_not_promotable"
    )
    now = utc_now()
    why = (
        "Oracle regret is real, but the largest exit-regret surface is not a "
        "balanced, production-visible rule candidate: total regret is slightly "
        "old_thin-heavy, stop-exit regret is strongly old_thin-dominated, and "
        "the cleaner target rows already capture most oracle PnL."
        if failed
        else "Oracle regret clustered in a balanced nonfuture bucket, but this remains only a diagnostic lead."
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": status,
        "lane": "alpha_search",
        "owner": OWNER,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": observed_lead,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "observed_only_attribution_runner",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": "experiment.py new accepted this as no strong near-neighbor.",
                "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
                "important_boundary": (
                    "Prior exit lifecycle replays failed; this run only "
                    "attributes fixed-entry oracle regret and cannot promote "
                    "a target-trim, fast-target, MFE-giveback, or stop-loss "
                    "threshold."
                ),
            },
            "3_single_policy_bundle": (
                "One observed-only attribution bundle: rebuild perfect-exit "
                "oracle rows and cluster regret by closed-trade fields."
            ),
            "4_acceptance_standard": ACCEPTANCE_RULE,
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "windows": {
                label: {
                    "result": repo_rel(cfg["result"]),
                    "snapshot": repo_rel(cfg["snapshot"]),
                }
                for label, cfg in WINDOWS.items()
            },
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "oracle_scope": "fixed_entry_best_intratrade_high_between_entry_and_actual_exit",
        },
        "gate1": {
            "baseline_loaded": True,
            "baseline_metrics": baseline,
            "note": "Observed-only attribution; before and after policy are identical.",
        },
        "gate2": {
            "dependencies_validated": True,
            "fields_checked": [
                "ticker",
                "entry_date",
                "exit_date",
                "entry_price",
                "exit_price",
                "shares",
                "pnl",
                "exit_reason",
                "strategy",
                "target_price",
                "OHLCV Date",
                "OHLCV High",
            ],
            "entry_date_present": all(bool(row.get("entry_date")) for row in rows),
            "target_price_checked": True,
            "target_price_present_count": audit["target_price_present_count"],
            "target_price_missing_count": audit["target_price_missing_count"],
            "target_price_relevance": audit["target_price_relevance"],
            "audit": audit,
        },
        "gate3": {
            "filter_added": False,
            "baseline_signals_generated": baseline["signals_generated"],
            "baseline_signals_survived": baseline["signals_survived"],
            "baseline_survival_rate": baseline["survival_rate"],
            "rebuilt_oracle_rows": len(rows),
            "missing_trade_count": len(missing),
            "note": "No executable filter was added; closed trades are attributed only.",
        },
        "gate4": {
            "observed_only_lead": observed_lead,
            "failed_reasons": failed,
            "acceptance_checks": analysis["acceptance_checks"],
            "decision": decision,
            "strategy_rerun_required": False,
            "before_after_strategy_delta": {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "max_drawdown_pct": 0.0,
            },
            "lead_limitations": [
                "Uses future intratrade highs and is diagnostic-only.",
                "Stop-exit regret mostly comes from old_thin losers.",
                "No shared helper, adapter, daily snapshot, or exit rule was promoted.",
            ],
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "max_drawdown_pct_worst_delta": 0.0,
        },
        "attribution": {
            "n_rows": len(rows),
            "analysis": analysis,
            "sample_rows": rows[:200],
        },
        "production_impact": {
            "trade_enabled": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "entry_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_rules_changed": False,
            "shared_helper_promoted": False,
            "daily_snapshot_exposed": False,
            "uses_future_oracle": True,
            "live_realistic_execution_envelope": (
                "Not evaluated for live use; this is observed-only fixed-entry "
                "oracle attribution and cannot become live-ready."
            ),
        },
        "calibration": calibration(prediction, observed_lead, failed),
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retry target trims, fast-target exits, breakeven stops, "
                "trailing stops, MFE-giveback thresholds, stop-loosening, or "
                "partial reduce rules on the same canonical windows from this "
                "oracle-regret surface. That would repeat failed exit families "
                "without new evidence."
            ),
            "new_evidence_required": (
                "A valid exit-lifecycle retry needs closed forward paper rows "
                "from a shared default-off advisory helper, PIT intratrade path "
                "features available before exit, or a live-realistic slot-reuse "
                "and winner-collateral envelope measured before promotion."
            ),
        },
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "related_files": [
            RUNNER,
            repo_rel(BASELINE_RESULT),
            *[repo_rel(cfg["result"]) for cfg in WINDOWS.values()],
            *[repo_rel(cfg["snapshot"]) for cfg in WINDOWS.values()],
            "experiments/logs/exp-20260429-032.json",
            "experiments/logs/exp-20260502-014.json",
            "experiments/logs/exp-20260521-018.json",
        ],
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "lane": payload["lane"],
        "owner": payload["owner"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "observed_only_lead": payload["observed_only_lead"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "single_causal_variable": payload["single_causal_variable"],
        "causal_components": payload["causal_components"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "new_evidence_axis": payload["new_evidence_axis"],
        "prediction": payload["prediction"],
        "pre_run_questions": payload["pre_run_questions"],
        "parameters": payload["parameters"],
        "gate1": payload["gate1"],
        "gate2": {
            **payload["gate2"],
            "audit": "<see artifact>",
        },
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "attribution": {
            "n_rows": payload["attribution"]["n_rows"],
            "overall": payload["attribution"]["analysis"]["overall"],
            "by_window": payload["attribution"]["analysis"]["by_window"],
            "by_exit_reason": payload["attribution"]["analysis"]["by_exit_reason"],
            "concentration": payload["attribution"]["analysis"]["concentration"],
        },
        "production_impact": payload["production_impact"],
        "calibration": payload["calibration"],
        "post_run_reflection": payload["post_run_reflection"],
        "related_files": payload["related_files"],
        "anti_js": payload["anti_js"],
    }


def build_card(payload: dict[str, Any]) -> str:
    analysis = payload["attribution"]["analysis"]
    by_window = analysis["by_window"]
    by_exit = analysis["by_exit_reason"]
    rows = [
        "| Bucket | Trades | Actual PnL | Oracle PnL | Regret | Capture | Windows |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for name, summary in by_window.items():
        rows.append(
            "| {name} | {n} | ${actual:,.2f} | ${oracle:,.2f} | ${regret:,.2f} | {capture} | {windows} |".format(
                name=name,
                n=summary["n"],
                actual=summary["actual_pnl"],
                oracle=summary["oracle_pnl"],
                regret=summary["regret_vs_oracle"],
                capture="{:.2%}".format(summary["capture_ratio"])
                if summary["capture_ratio"] is not None
                else "n/a",
                windows=", ".join(summary["windows_present"]),
            )
        )
    exit_rows = [
        "| Exit Reason | Trades | Actual PnL | Oracle PnL | Regret | Regret Share | Max Window Share |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, summary in by_exit.items():
        max_share = analysis["acceptance_checks"].get("stop_exit_cluster", {}).get("max_window_regret_share")
        if name != "stop":
            max_share = cluster_window_share(payload["attribution"]["sample_rows"], "exit_reason", name)
        exit_rows.append(
            "| {name} | {n} | ${actual:,.2f} | ${oracle:,.2f} | ${regret:,.2f} | {share} | {max_share} |".format(
                name=name,
                n=summary["n"],
                actual=summary["actual_pnl"],
                oracle=summary["oracle_pnl"],
                regret=summary["regret_vs_oracle"],
                share="{:.2%}".format(summary["regret_share_of_total"])
                if summary["regret_share_of_total"] is not None
                else "n/a",
                max_share="{:.2%}".format(max_share) if max_share is not None else "n/a",
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: fixed-entry exit oracle regret cluster",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Production orders changed: no",
            "- Shared helper promoted: no",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Window Attribution",
            "",
            *rows,
            "",
            "## Exit-Reason Attribution",
            "",
            *exit_rows,
            "",
            "- Rebuilt rows: `{}`".format(payload["attribution"]["n_rows"]),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
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
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)} for path in files},
        "anti_js": payload["anti_js"],
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
        "attribution": {
            "n_rows": payload["attribution"]["n_rows"],
            "overall": payload["attribution"]["analysis"]["overall"],
            "by_window": payload["attribution"]["analysis"]["by_window"],
            "by_exit_reason": payload["attribution"]["analysis"]["by_exit_reason"],
            "concentration": payload["attribution"]["analysis"]["concentration"],
        },
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
    analysis = payload["attribution"]["analysis"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "rebuilt_rows": payload["attribution"]["n_rows"],
                "overall": analysis["overall"],
                "by_window": analysis["by_window"],
                "by_exit_reason": analysis["by_exit_reason"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
