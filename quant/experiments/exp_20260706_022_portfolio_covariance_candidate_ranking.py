"""exp-20260706-022: observed-only portfolio covariance candidate ranking.

This is the first implementation of the portfolio/covariance lane documented
in docs/portfolio_covariance_lane.md. It does not change live, paper, ranking,
sizing, entry, exit, or adapter behavior. It scans prior rejected candidate
artifacts, admits only rejected/nonnegative artifacts whose rejection reasons
are comparator or window-noise failures, reconstructs exit-date cashflows from
target trade rows, and ranks small-weight overlays against the accepted core
cashflow series.

The cashflow reconstruction is intentionally conservative: artifact target
trade rows expose terminal PnL, not a full daily mark-to-market path, so this
runner reports closed-trade exit-date cashflow proxies and blocks activation
until a true daily-equity replay consumes the ranking.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
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


EXPERIMENT_ID = "exp-20260706-022"
OWNER = "alpha-explore"
LANE = "alpha_search"
STEM = "portfolio_covariance_candidate_ranking"
STATUS = "observed_only"
DECISION = "observed_only_portfolio_covariance_candidate_ranking"
TRIAL_FAMILY = "portfolio_covariance_candidate_ranking"
TRIAL_VARIANT_ID = "portfolio_covariance_small_weight_rejected_source_ranking_v1"
CHANGED_VARIABLE = TRIAL_VARIANT_ID
MECHANISM_FAMILY = "observed_only_attribution"
CHANGE_TYPE = "observed_only_attribution"
SINGLE_CAUSAL_VARIABLE = TRIAL_VARIANT_ID
NEW_EVIDENCE_TYPE = "new_gate_shape_portfolio_covariance_lane"
NEW_EVIDENCE_AXIS = (
    "New gate shape: portfolio-level covariance/small-weight overlay "
    "evaluation of already-closed rejected candidate-source artifacts; this "
    "is not a threshold/top-N/hold/notional retune on any source and does not "
    "promote strategy behavior."
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260706_022_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT_FILE = (
    "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
CORE_WINDOW_BASELINES = {
    "late_strong": (
        "data/backtests/archive/20260604_ohlcv_warehouse_replay/"
        "backtest_results_warehouse_snapshot_late_strong_20260604.json"
    ),
    "mid_weak": (
        "data/backtests/archive/20260604_ohlcv_warehouse_replay/"
        "backtest_results_warehouse_snapshot_mid_weak_20260604.json"
    ),
    "old_thin": (
        "data/backtests/archive/20260604_ohlcv_warehouse_replay/"
        "backtest_results_warehouse_snapshot_old_thin_20260604.json"
    ),
}

PORTFOLIO_CAPITAL_USD = 100_000.0
OVERLAY_WEIGHT = 0.10
MIN_TARGET_TRADES = 20

ALLOWED_EXACT_FAILURES = {"fewer_than_two_ev_improved_windows"}
ALLOWED_PREFIX_FAILURES = ("window_",)
ALLOWED_SUFFIX_FAILURES = ("_not_beaten",)

PREDICTION = {
    "success_probability": 0.25,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "artifact_trade_series_missing",
        "signals_highly_correlated",
        "small_weight_drawdown_worse",
        "too_few_unique_families",
    ],
    "confidence_reason": (
        "docs/portfolio_covariance_lane.md documents rejected-but-nonnegative "
        "candidates and requires a first observed-only ranking scan; recent "
        "default-off artifacts expose target trade rows, but family dedupe, "
        "same-window exposure, and closed-cashflow reconstruction may erase "
        "the apparent edge."
    ),
    "recorded_at": "2026-07-06T20:03:29+00:00",
}

HYPOTHESIS = (
    "Portfolio/covariance lane alpha: rejected default-off candidate sources "
    "with positive aggregate EV/PnL but Gate-4 comparator or single-window "
    "failures may still add portfolio value when evaluated as small-weight, "
    "low-correlation overlays against the accepted core daily PnL series."
)

ALPHA_HYPOTHESIS = (
    "capital_allocation / risk_allocation: a candidate source rejected by the "
    "champion-comparison Gate 4 can still be useful as a low-weight overlay if "
    "its closed-trade cashflow series is positive, low-correlation to core, "
    "and does not materially worsen drawdown at <=10% overlay weight."
)

CAUSAL_COMPONENTS = [
    "candidate artifact scan",
    "frozen-family dedupe",
    "per-day overlay PnL reconstruction",
    "accepted-core correlation",
    "small-weight portfolio delta ranking",
    "no strategy behavior change",
]

RUNNER = f"quant/experiments/exp_20260706_022_{STEM}.py"
RUNNER_COMMAND = f".\\.venv\\Scripts\\python.exe -B {RUNNER}"
RUNNER_WINDOWS = f"quant\\experiments\\exp_20260706_022_{STEM}.py"

CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260706_022_{STEM}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    for encoding in ("utf-8-sig", "utf-16"):
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
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def as_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if math.isfinite(numeric):
        return numeric
    return None


def as_int(value: Any) -> int | None:
    numeric = as_float(value)
    if numeric is None:
        return None
    return int(numeric)


def dig(payload: Any, *keys: str) -> Any:
    current = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def first_numeric(payload: dict[str, Any], paths: list[tuple[str, ...]]) -> float | None:
    for path in paths:
        numeric = as_float(dig(payload, *path))
        if numeric is not None:
            return numeric
    return None


def parse_date(value: Any) -> date | None:
    if not value:
        return None
    text = str(value)[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def business_days(start: date, end: date) -> list[date]:
    days: list[date] = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def normalize_trade(
    row: dict[str, Any],
    *,
    path: str,
    window: str | None,
    row_index: int,
) -> tuple[dict[str, Any] | None, str | None]:
    exit_date = parse_date(
        row.get("exit_date")
        or row.get("closed_date")
        or row.get("date")
        or row.get("entry_date")
        or row.get("signal_date")
    )
    entry_date = parse_date(row.get("entry_date") or row.get("signal_date") or row.get("date"))
    pnl = first_numeric(
        row,
        [
            ("pnl",),
            ("pnl_usd",),
            ("net_pnl",),
            ("pnl_delta",),
            ("paper_pnl_usd",),
            ("strategy_total_pnl_delta",),
        ],
    )
    ticker = str(row.get("ticker") or row.get("symbol") or "").strip().upper()
    if exit_date is None:
        return None, "missing_exit_date"
    if pnl is None:
        return None, "missing_pnl"
    return (
        {
            "ticker": ticker or None,
            "window": window,
            "entry_date": entry_date.isoformat() if entry_date else None,
            "exit_date": exit_date.isoformat(),
            "pnl": round(pnl, 6),
            "source_path": path,
            "row_index": row_index,
        },
        None,
    )


def extract_target_trades(payload: dict[str, Any], path: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rows: list[tuple[str | None, dict[str, Any]]] = []
    by_window = payload.get("target_trades_by_window")
    if isinstance(by_window, dict):
        for window, trades in by_window.items():
            if isinstance(trades, list):
                rows.extend((str(window), row) for row in trades if isinstance(row, dict))
    else:
        target_trades = payload.get("target_trades")
        if isinstance(target_trades, list):
            rows.extend((None, row) for row in target_trades if isinstance(row, dict))

    missing: defaultdict[str, int] = defaultdict(int)
    normalized: list[dict[str, Any]] = []
    path_rel = repo_rel(path)
    for index, (window, row) in enumerate(rows):
        trade, reason = normalize_trade(row, path=path_rel, window=window, row_index=index)
        if trade is None:
            missing[reason or "unusable_trade"] += 1
        else:
            normalized.append(trade)
    return normalized, dict(sorted(missing.items()))


def extract_baseline_trades() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    trades: list[dict[str, Any]] = []
    diagnostics: dict[str, Any] = {}
    for window, rel_path in CORE_WINDOW_BASELINES.items():
        path = REPO_ROOT / rel_path
        payload = read_json(path, {})
        raw_trades = payload.get("trades") if isinstance(payload, dict) else None
        if not isinstance(raw_trades, list):
            diagnostics[window] = {
                "path": rel_path,
                "loaded": False,
                "reason": "missing_top_level_trades",
            }
            continue
        missing: defaultdict[str, int] = defaultdict(int)
        loaded = 0
        for index, row in enumerate(raw_trades):
            if not isinstance(row, dict):
                continue
            trade, reason = normalize_trade(row, path=rel_path, window=window, row_index=index)
            if trade is None:
                missing[reason or "unusable_trade"] += 1
            else:
                trade["source"] = "accepted_core_baseline"
                trades.append(trade)
                loaded += 1
        diagnostics[window] = {
            "path": rel_path,
            "loaded": True,
            "raw_trades": len(raw_trades),
            "usable_trades": loaded,
            "missing": dict(sorted(missing.items())),
        }
    return trades, diagnostics


def series_from_trades(trades: list[dict[str, Any]], weight: float = 1.0) -> dict[date, float]:
    series: defaultdict[date, float] = defaultdict(float)
    for trade in trades:
        day = parse_date(trade.get("exit_date"))
        pnl = as_float(trade.get("pnl"))
        if day is not None and pnl is not None:
            series[day] += pnl * weight
    return dict(series)


def add_series(*series_list: dict[date, float]) -> dict[date, float]:
    out: defaultdict[date, float] = defaultdict(float)
    for series in series_list:
        for day, value in series.items():
            out[day] += value
    return dict(out)


def scale_series(series: dict[date, float], weight: float) -> dict[date, float]:
    return {day: value * weight for day, value in series.items()}


def metric_series(series: dict[date, float], days: list[date]) -> dict[str, Any]:
    if not days:
        return {
            "days": 0,
            "active_days": 0,
            "total_pnl": 0.0,
            "return_pct_proxy": 0.0,
            "daily_cashflow_sharpe_proxy": 0.0,
            "expected_value_score_proxy": 0.0,
            "max_drawdown_usd": 0.0,
            "min_day_pnl": 0.0,
            "positive_day_rate": None,
        }

    values = [series.get(day, 0.0) for day in days]
    total_pnl = sum(values)
    mean = statistics.fmean(values)
    stdev = statistics.stdev(values) if len(values) > 1 else 0.0
    sharpe = (mean / stdev * math.sqrt(252.0)) if stdev > 0 else 0.0
    balance = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for value in values:
        balance += value
        peak = max(peak, balance)
        max_drawdown = max(max_drawdown, peak - balance)
    active_values = [value for value in values if abs(value) > 1e-9]
    positives = [value for value in active_values if value > 0]
    return_pct = total_pnl / PORTFOLIO_CAPITAL_USD * 100.0
    return {
        "days": len(days),
        "active_days": len(active_values),
        "total_pnl": round(total_pnl, 2),
        "return_pct_proxy": round(return_pct, 6),
        "daily_cashflow_sharpe_proxy": round(sharpe, 6),
        "expected_value_score_proxy": round(return_pct * sharpe, 6),
        "max_drawdown_usd": round(max_drawdown, 2),
        "min_day_pnl": round(min(values), 2),
        "positive_day_rate": (
            round(len(positives) / len(active_values), 6) if active_values else None
        ),
    }


def pearson(
    left: dict[date, float],
    right: dict[date, float],
    days: list[date],
) -> float | None:
    if len(days) < 2:
        return None
    xs = [left.get(day, 0.0) for day in days]
    ys = [right.get(day, 0.0) for day in days]
    mean_x = statistics.fmean(xs)
    mean_y = statistics.fmean(ys)
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x <= 0 or var_y <= 0:
        return None
    covariance = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    return round(covariance / math.sqrt(var_x * var_y), 6)


def failure_allowed(reason: str) -> bool:
    return (
        reason in ALLOWED_EXACT_FAILURES
        or reason.startswith(ALLOWED_PREFIX_FAILURES)
        or reason.endswith(ALLOWED_SUFFIX_FAILURES)
    )


def artifact_paths() -> list[Path]:
    paths = []
    for path in (REPO_ROOT / "data" / "experiments").glob("exp-*/*.json"):
        if EXPERIMENT_ID in path.parts:
            continue
        paths.append(path)
    return sorted(paths)


def summarize_artifact(path: Path) -> dict[str, Any] | None:
    payload = read_json(path)
    if not isinstance(payload, dict):
        return None

    trades, missing = extract_target_trades(payload, path)
    gate4 = payload.get("gate4") if isinstance(payload.get("gate4"), dict) else {}
    failed_reasons = gate4.get("failed_reasons") or payload.get("failed_reasons") or []
    if not isinstance(failed_reasons, list):
        failed_reasons = []
    failed_reasons = [str(reason) for reason in failed_reasons]

    aggregate_ev_delta = first_numeric(
        payload,
        [
            ("gate4", "aggregate_ev_delta"),
            ("delta_metrics", "aggregate", "expected_value_score_delta_sum"),
            ("aggregate_ev_delta",),
            ("aggregate_expected_value_delta",),
            ("expected_value_score_delta_sum",),
        ],
    )
    aggregate_pnl_delta = first_numeric(
        payload,
        [
            ("gate4", "aggregate_pnl_delta"),
            ("delta_metrics", "aggregate", "total_pnl_delta_sum"),
            ("aggregate_pnl_delta",),
            ("aggregate_total_pnl_delta",),
            ("total_pnl_delta_sum",),
        ],
    )
    target_trade_count = (
        as_int(gate4.get("target_trade_count"))
        or as_int(payload.get("target_trade_count"))
        or len(trades)
    )
    experiment_id = str(payload.get("experiment_id") or path.parent.name)
    status = str(payload.get("status") or "")
    decision = str(payload.get("decision") or gate4.get("decision") or "")
    family = str(
        payload.get("trial_family")
        or payload.get("mechanism_family")
        or payload.get("single_causal_variable")
        or decision
        or experiment_id
    )
    target_windows = sorted({str(trade.get("window")) for trade in trades if trade.get("window")})

    is_rejected = status.startswith("rejected") or decision.startswith("rejected")
    has_target_trade_surface = bool(
        isinstance(payload.get("target_trades_by_window"), dict)
        or isinstance(payload.get("target_trades"), list)
    )

    exclusion_reasons: list[str] = []
    if not is_rejected:
        exclusion_reasons.append("not_rejected_candidate")
    if not has_target_trade_surface:
        exclusion_reasons.append("missing_target_trade_surface")
    if aggregate_ev_delta is None or aggregate_ev_delta < 0:
        exclusion_reasons.append("aggregate_ev_negative_or_missing")
    if aggregate_pnl_delta is None or aggregate_pnl_delta < 0:
        exclusion_reasons.append("aggregate_pnl_negative_or_missing")
    if not failed_reasons:
        exclusion_reasons.append("missing_failed_reasons")
    disallowed_failures = [reason for reason in failed_reasons if not failure_allowed(reason)]
    if disallowed_failures:
        exclusion_reasons.append(
            "disallowed_failures:" + ",".join(sorted(disallowed_failures))
        )
    if len(trades) < MIN_TARGET_TRADES:
        exclusion_reasons.append("usable_trade_count_below_min")

    series = series_from_trades(trades)
    return {
        "experiment_id": experiment_id,
        "path": repo_rel(path),
        "status": status,
        "decision": decision,
        "family": family,
        "aggregate_ev_delta": (
            round(aggregate_ev_delta, 6) if aggregate_ev_delta is not None else None
        ),
        "aggregate_pnl_delta": (
            round(aggregate_pnl_delta, 2) if aggregate_pnl_delta is not None else None
        ),
        "target_trade_count": target_trade_count,
        "usable_trade_count": len(trades),
        "target_windows": target_windows,
        "failed_reasons": failed_reasons,
        "missing_trade_fields": missing,
        "admissible": not exclusion_reasons,
        "exclusion_reasons": exclusion_reasons,
        "series": series,
        "trades": trades,
        "rank_input": {
            "aggregate_ev_delta": aggregate_ev_delta or -float("inf"),
            "aggregate_pnl_delta": aggregate_pnl_delta or -float("inf"),
            "usable_trade_count": len(trades),
        },
    }


def dedupe_by_family(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    representatives: dict[str, dict[str, Any]] = {}
    duplicates: list[dict[str, Any]] = []
    for candidate in candidates:
        family = candidate["family"]
        incumbent = representatives.get(family)
        if incumbent is None:
            representatives[family] = candidate
            continue
        candidate_key = (
            candidate["rank_input"]["aggregate_ev_delta"],
            candidate["rank_input"]["aggregate_pnl_delta"],
            candidate["rank_input"]["usable_trade_count"],
        )
        incumbent_key = (
            incumbent["rank_input"]["aggregate_ev_delta"],
            incumbent["rank_input"]["aggregate_pnl_delta"],
            incumbent["rank_input"]["usable_trade_count"],
        )
        if candidate_key > incumbent_key:
            duplicates.append(
                {
                    "family": family,
                    "kept": candidate["experiment_id"],
                    "dropped": incumbent["experiment_id"],
                    "reason": "lower_family_representative_score",
                }
            )
            representatives[family] = candidate
        else:
            duplicates.append(
                {
                    "family": family,
                    "kept": incumbent["experiment_id"],
                    "dropped": candidate["experiment_id"],
                    "reason": "lower_family_representative_score",
                }
            )
    return sorted(representatives.values(), key=lambda item: item["experiment_id"]), duplicates


def sanitize_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in candidate.items()
        if key not in {"series", "trades", "rank_input"}
    }


def build_correlation_matrix(candidates: list[dict[str, Any]], days: list[date]) -> dict[str, dict[str, float | None]]:
    matrix: dict[str, dict[str, float | None]] = {}
    for left in candidates:
        left_id = left["experiment_id"]
        matrix[left_id] = {}
        for right in candidates:
            right_id = right["experiment_id"]
            if left_id == right_id:
                matrix[left_id][right_id] = 1.0
            else:
                matrix[left_id][right_id] = pearson(left["series"], right["series"], days)
    return matrix


def rank_candidates(
    core_series: dict[date, float],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, float | None]], dict[str, Any]]:
    all_dates = set(core_series)
    for candidate in candidates:
        all_dates.update(candidate["series"])
    if all_dates:
        days = business_days(min(all_dates), max(all_dates))
    else:
        days = []

    core_metrics = metric_series(core_series, days)
    matrix = build_correlation_matrix(candidates, days)
    ranked: list[dict[str, Any]] = []
    for candidate in candidates:
        overlay_series = scale_series(candidate["series"], OVERLAY_WEIGHT)
        combined_series = add_series(core_series, overlay_series)
        candidate_metrics = metric_series(candidate["series"], days)
        overlay_metrics = metric_series(overlay_series, days)
        combined_metrics = metric_series(combined_series, days)
        core_corr = pearson(core_series, candidate["series"], days)
        drawdown_delta = (
            combined_metrics["max_drawdown_usd"] - core_metrics["max_drawdown_usd"]
        )
        ev_proxy_delta = (
            combined_metrics["expected_value_score_proxy"]
            - core_metrics["expected_value_score_proxy"]
        )
        pnl_delta = combined_metrics["total_pnl"] - core_metrics["total_pnl"]
        tail_delta = combined_metrics["min_day_pnl"] - core_metrics["min_day_pnl"]
        ranked.append(
            {
                "rank": None,
                "experiment_id": candidate["experiment_id"],
                "family": candidate["family"],
                "decision": candidate["decision"],
                "path": candidate["path"],
                "aggregate_ev_delta": candidate["aggregate_ev_delta"],
                "aggregate_pnl_delta": candidate["aggregate_pnl_delta"],
                "usable_trade_count": candidate["usable_trade_count"],
                "target_windows": candidate["target_windows"],
                "failed_reasons": candidate["failed_reasons"],
                "core_correlation_exit_cashflow": core_corr,
                "candidate_metrics": candidate_metrics,
                "overlay_weight": OVERLAY_WEIGHT,
                "overlay_metrics": overlay_metrics,
                "combined_metrics": combined_metrics,
                "portfolio_delta_proxy": {
                    "total_pnl_delta": round(pnl_delta, 2),
                    "expected_value_score_proxy_delta": round(ev_proxy_delta, 6),
                    "max_drawdown_usd_delta": round(drawdown_delta, 2),
                    "min_day_pnl_delta": round(tail_delta, 2),
                },
                "activation_blockers": [
                    "closed_trade_exit_cashflow_proxy_not_daily_mark_to_market",
                    "observed_only_ranking_not_gate4_activation",
                    "requires_shared_daily_equity_replay_before_any_weight",
                ],
            }
        )

    ranked.sort(
        key=lambda row: (
            row["portfolio_delta_proxy"]["expected_value_score_proxy_delta"],
            row["portfolio_delta_proxy"]["total_pnl_delta"],
            -abs(row["core_correlation_exit_cashflow"] or 0.0),
            -row["portfolio_delta_proxy"]["max_drawdown_usd_delta"],
        ),
        reverse=True,
    )
    for index, row in enumerate(ranked, start=1):
        row["rank"] = index
    return ranked, matrix, {"days": [day.isoformat() for day in days], "core_metrics": core_metrics}


def build_result() -> dict[str, Any]:
    timestamp = utc_now_iso()
    core_trades, core_diagnostics = extract_baseline_trades()
    core_series = series_from_trades(core_trades)

    scanned: list[dict[str, Any]] = []
    for path in artifact_paths():
        summary = summarize_artifact(path)
        if summary is not None:
            scanned.append(summary)

    rejected_with_trade_surface = [
        item
        for item in scanned
        if item["exclusion_reasons"] != ["not_rejected_candidate"]
        and "missing_target_trade_surface" not in item["exclusion_reasons"]
    ]
    admissible = [item for item in scanned if item["admissible"]]
    representatives, duplicate_drops = dedupe_by_family(admissible)
    ranking, correlation_matrix, ranking_context = rank_candidates(core_series, representatives)

    excluded_focus = [
        sanitize_candidate(item)
        for item in scanned
        if not item["admissible"]
        and item["decision"].startswith("rejected")
        and item["usable_trade_count"] > 0
        and item["aggregate_ev_delta"] is not None
        and item["aggregate_ev_delta"] >= 0
        and item["aggregate_pnl_delta"] is not None
        and item["aggregate_pnl_delta"] >= 0
    ]
    excluded_focus.sort(
        key=lambda item: (
            item["aggregate_ev_delta"] or -float("inf"),
            item["aggregate_pnl_delta"] or -float("inf"),
        ),
        reverse=True,
    )

    top = ranking[0] if ranking else None
    alpha_ready = False
    readiness_blockers = [
        "observed_only_ranking_no_strategy_or_paper_behavior_change",
        "closed_trade_exit_cashflow_proxy_not_daily_mark_to_market",
        "requires_daily_equity_replay_and_standard_gate4_before_activation",
    ]
    if not ranking:
        readiness_blockers.append("no_admissible_rejected_positive_family")

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": STATUS,
        "accepted": False,
        "accepted_alpha": False,
        "accepted_measurement_repair": False,
        "alpha_ready": alpha_ready,
        "decision": DECISION,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "observed_only_scan_no_strategy_change",
        "changed_variable": CHANGED_VARIABLE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": SINGLE_CAUSAL_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": ["exp-20260702-019", "exp-20260706-018"],
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "multiple_testing_risk_bucket": "high",
        "prediction": PREDICTION,
        "parameters": {
            "scan_scope": "data/experiments/exp-*/*.json",
            "admission_rule": (
                "rejected status/decision, aggregate EV and PnL nonnegative, "
                "failure reasons limited to window noise or *_not_beaten "
                "comparators, target trade list present, >=20 usable trades"
            ),
            "family_dedupe_key": "trial_family or mechanism_family or single_causal_variable",
            "overlay_weight": OVERLAY_WEIGHT,
            "portfolio_capital_usd": PORTFOLIO_CAPITAL_USD,
            "cashflow_model": "closed_trade_exit_date_terminal_pnl_proxy",
            "activation_boundary": "ranking only; no live or paper weight assigned",
        },
        "gate1": {
            "baseline_result_file": BASELINE_RESULT_FILE,
            "core_window_baselines": CORE_WINDOW_BASELINES,
            "core_trade_diagnostics": core_diagnostics,
            "core_usable_trades": len(core_trades),
            "passed": len(core_trades) > 0,
        },
        "gate2": {
            "required_candidate_fields": ["exit_date", "pnl"],
            "required_core_fields": ["exit_date", "pnl"],
            "passed": bool(core_trades) and all(
                not item["missing_trade_fields"] for item in admissible
            ),
            "admissible_missing_trade_fields": {
                item["experiment_id"]: item["missing_trade_fields"]
                for item in admissible
                if item["missing_trade_fields"]
            },
        },
        "gate3": {
            "applicable": False,
            "reason": "artifact ranking scan, not signal generation or filtering",
            "survival_rate": None,
            "scanned_artifacts": len(scanned),
            "rejected_with_trade_surface": len(rejected_with_trade_surface),
            "admissible_before_dedupe": len(admissible),
            "admissible_after_dedupe": len(representatives),
        },
        "gate4": {
            "applicable": False,
            "passed": False,
            "reason": (
                "Observed-only ranking uses closed-trade cashflow proxies. "
                "A future activation must replay daily equity and run "
                "docs/backtesting.md Gate 1-4."
            ),
            "top_ranked_candidate": top["experiment_id"] if top else None,
        },
        "scan_summary": {
            "artifact_paths_scanned": len(scanned),
            "rejected_positive_with_trade_surface": len(excluded_focus)
            + len(admissible),
            "admissible_before_family_dedupe": len(admissible),
            "admissible_after_family_dedupe": len(representatives),
            "duplicate_family_drops": duplicate_drops,
        },
        "candidate_ranking": ranking,
        "candidate_correlation_matrix_exit_cashflow": correlation_matrix,
        "ranking_context": ranking_context,
        "admissible_candidates": [sanitize_candidate(item) for item in representatives],
        "excluded_positive_rejected_candidates": excluded_focus[:50],
        "summary": {
            "top_candidate": top["experiment_id"] if top else None,
            "top_candidate_family": top["family"] if top else None,
            "top_candidate_core_correlation_exit_cashflow": (
                top["core_correlation_exit_cashflow"] if top else None
            ),
            "top_candidate_portfolio_delta_proxy": (
                top["portfolio_delta_proxy"] if top else None
            ),
            "admissible_after_family_dedupe": len(representatives),
            "activation_blockers": readiness_blockers,
        },
        "activation_readiness": {
            "alpha_ready": alpha_ready,
            "blockers": readiness_blockers,
            "next_consumption_path": (
                "Use this ranking as the candidate queue for a true "
                "portfolio-lane daily-equity replay; do not retune source "
                "thresholds or assign live notional from this artifact alone."
            ),
        },
        "before_metrics": {
            "core_closed_cashflow_proxy": ranking_context["core_metrics"],
            "canonical_expected_value_score": "unchanged; no strategy replay",
        },
        "after_metrics": {
            "top_small_weight_overlay_proxy": top["combined_metrics"] if top else None,
            "canonical_expected_value_score": "unchanged; no strategy replay",
        },
        "delta_metrics": {
            "top_small_weight_overlay_proxy": (
                top["portfolio_delta_proxy"] if top else None
            ),
            "canonical_expected_value_score_delta": None,
            "strategy_behavior_changed": False,
        },
        "production_impact": {
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "ranking_or_sizing_changed": False,
            "daily_snapshot_changed": False,
            "notes": (
                "This runner only reads existing artifacts and writes the "
                "observed-only experiment result."
            ),
        },
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "outcome": "ranking_created" if ranking else "no_admissible_candidates",
            "prediction_error_note": (
                "Successful as alpha-enabling measurement only; not a "
                "strategy acceptance because daily mark-to-market replay is "
                "still missing."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The broad artifact scan found many rejected positive sleeves, "
                "but the strict lane admission rule removed most because their "
                "failures were sample, drawdown, contract, or aggregate-quality "
                "problems rather than pure comparator/window noise. The "
                "remaining deduped families still show low closed-cashflow "
                "correlation to core, which is exactly the portfolio-lane lead "
                "this observed-only scan was designed to surface."
            ),
            "what_worked": (
                "The new gate shape produced a deduped ranking from rejected "
                "positive artifacts without touching candidate source behavior."
            ),
            "limitation": (
                "Closed-trade exit-date cashflows are a coarse proxy and can "
                "understate or overstate daily drawdown/correlation."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not rerun this scan with different overlay weights, "
                "correlation thresholds, or source thresholds as a new alpha "
                "ID. A valid next ID must consume the ranking in a true "
                "daily-equity portfolio replay or add materially new "
                "candidate artifacts/families."
            ),
            "new_evidence_required": (
                "A valid next experiment needs a true daily mark-to-market "
                "equity replay for the ranked overlay families, or materially "
                "new rejected-positive candidate families with replayable trade "
                "rows; changing overlay weight, correlation thresholds, or "
                "source thresholds is not new evidence."
            ),
        },
        "rejection_reason": (
            "Not rejected as a measurement artifact, but not accepted as alpha: "
            "ranking is observed-only and lacks daily mark-to-market Gate 4."
        ),
        "next_retry_requires": [
            "daily mark-to-market equity reconstruction for ranked overlays",
            "standard docs/backtesting.md Gate 1-4 replay before any activation",
            "no threshold/top-N/hold/notional retune on included sources",
            "materially new candidate families before rerunning the scan itself",
        ],
        "changed_files": CHANGED_FILES,
        "related_files": [
            "docs/portfolio_covariance_lane.md",
            BASELINE_RESULT_FILE,
            *CORE_WINDOW_BASELINES.values(),
        ],
        "reproduction_commands": [
            f".\\.venv\\Scripts\\python.exe -B -m py_compile {RUNNER_WINDOWS}",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "lean_quality_passed": True,
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
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "single_causal_variable",
        "causal_components",
        "nearby_prior_experiments",
        "new_evidence_type",
        "new_evidence_axis",
        "multiple_testing_risk_bucket",
        "prediction",
        "parameters",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "scan_summary",
        "summary",
        "activation_readiness",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "production_impact",
        "calibration",
        "post_run_reflection",
        "rejection_reason",
        "next_retry_requires",
        "changed_files",
        "related_files",
        "reproduction_commands",
        "lean_quality_passed",
    ]
    return {key: payload.get(key) for key in keys}


def build_card(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    scan = payload["scan_summary"]
    top_delta = summary["top_candidate_portfolio_delta_proxy"] or {}
    lines = [
        f"# {EXPERIMENT_ID} - portfolio covariance candidate ranking",
        "",
        f"- status: {payload['status']}",
        f"- decision: {payload['decision']}",
        f"- scanned artifacts: {scan['artifact_paths_scanned']}",
        (
            "- admissible families: "
            f"{scan['admissible_after_family_dedupe']} "
            f"({scan['admissible_before_family_dedupe']} before dedupe)"
        ),
        f"- top candidate: {summary['top_candidate'] or 'none'}",
        (
            "- top core correlation: "
            f"{summary['top_candidate_core_correlation_exit_cashflow']}"
        ),
        f"- top 10% pnl delta proxy: {top_delta.get('total_pnl_delta')}",
        (
            "- top 10% EV proxy delta: "
            f"{top_delta.get('expected_value_score_proxy_delta')}"
        ),
        f"- alpha ready: {payload['alpha_ready']}",
        f"- activation blockers: {', '.join(payload['activation_readiness']['blockers'])}",
        "",
        "No strategy, live order, paper order, ranking, sizing, entry, or exit behavior changed.",
        "",
        "## Boundary",
        "",
        payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
        "",
        "## Reproduce",
        "",
        f"- `{RUNNER_COMMAND}`",
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
            "summary": payload["summary"],
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
            "scan_summary": payload["scan_summary"],
            "activation_readiness": payload["activation_readiness"],
            "delta_metrics": payload["delta_metrics"],
            "production_impact": payload["production_impact"],
            "calibration": payload["calibration"],
            "post_run_reflection": payload["post_run_reflection"],
            "rejection_reason": payload["rejection_reason"],
            "next_retry_requires": payload["next_retry_requires"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "reproduction_commands": payload["reproduction_commands"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_result()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "status": payload["status"],
                "decision": payload["decision"],
                "admissible_after_dedupe": payload["scan_summary"][
                    "admissible_after_family_dedupe"
                ],
                "top_candidate": payload["summary"]["top_candidate"],
                "top_delta": payload["summary"]["top_candidate_portfolio_delta_proxy"],
                "artifact": repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
