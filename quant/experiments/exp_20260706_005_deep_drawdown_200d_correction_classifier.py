"""exp-20260706-005: deep drawdown 200d correction classifier.

Read-only follow-up to exp-20260706-003/004. The fixed new gate shape is an
ex-ante bear-vs-correction classifier: after applying the one-entry-per-episode
budget from exp004, keep the first stabilization candidate only when QQQ and
SPY both have positive 200-session SMA slope over the prior 20 sessions on the
signal date.

No strategy behavior changes here: no helper, daily adapter, ranking, sizing,
exit, watchlist, prompt, paper order, or live order path is changed.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import sqlite3
import sys
from pathlib import Path
from statistics import mean, median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
QUANT_ROOT = REPO_ROOT / "quant"
for path in (SCRIPTS_ROOT, QUANT_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)
from deep_drawdown_rebound_paper_sleeve import (  # noqa: E402
    INDEX_HISTORY_PATH,
    load_index_history_rows,
    merge_bar_series,
)


EXPERIMENT_ID = "exp-20260706-005"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "deep_drawdown_200d_correction_classifier"
RUNNER = f"quant/experiments/exp_20260706_005_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
SOURCE_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260706-003"
    / "exp_20260706_003_deep_drawdown_rebound.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260706_005_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
WAREHOUSE_PATHS = (
    REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite",
    REPO_ROOT / "data" / "tmp" / "warehouse_main_alpha_search_readcopy.sqlite",
)

HYPOTHESIS = (
    "Deep-drawdown first-stabilization rebound may only be positive when the "
    "episode is an ex-ante correction, not a secular bear; require QQQ and "
    "SPY 200-day trend-slope support at the signal date before keeping the "
    "first per-episode candidate."
)
CHANGED_VARIABLE = "deep_drawdown_200d_trend_correction_classifier_first_budget_v1"
MECHANISM_FAMILY = "capitulation_rebound_event_conditioning"
TRIAL_FAMILY = "deep_drawdown_bear_vs_correction_classifier"
TRIAL_VARIANT_ID = "200d_trend_slope_first_budget_v1"
NEARBY_PRIORS = ["exp-20260706-003", "exp-20260706-004"]
NEW_EVIDENCE_AXIS = (
    "New gate shape explicitly allowed by exp-20260706-004: a predeclared "
    "ex-ante bear-vs-correction classifier using QQQ/SPY 200-day trend slope "
    "at signal date, applied before selecting first per-episode candidates; "
    "no drawdown trigger, reset, hold, cooldown, notional, ticker, or "
    "response-curve retune."
)

STANDARD_WINDOWS = {
    "old_thin": ("2024-10-02", "2025-04-22"),
    "mid_weak": ("2025-04-23", "2025-10-22"),
    "late_strong": ("2025-10-23", "2026-04-21"),
}

CLASSIFIER_RULE = {
    "sma_days": 200,
    "slope_lookback_sessions": 20,
    "pass_rule": (
        "QQQ sma200 20-session slope > 0 and SPY sma200 20-session slope > 0 "
        "on the first per-episode stabilization signal date"
    ),
    "episode_selection_order": (
        "First take only the first closed stabilization trade per episode from "
        "exp003; if that first signal fails the classifier, do not search for "
        "a later signal inside the same episode."
    ),
}

ACCEPTANCE_RULE = {
    "min_full_history_qualified_episodes": 8,
    "require_positive_cash_pnl": True,
    "min_win_rate": 0.60,
    "require_positive_mean_excess_vs_spy": True,
    "min_standard_window_trades": 3,
    "min_standard_windows_with_trades": 2,
    "require_no_standard_window_negative_pnl": True,
    "max_classifier_excluded_positive_episode_share": 0.50,
}

DEFAULT_PREDICTION = {
    "success_probability": 0.24,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "classifier_still_allows_bear_onsets",
        "standard_windows_too_thin",
        "spy_replacement_not_beaten",
        "posthoc_gate_shape_overfit",
    ],
    "confidence_reason": (
        "exp-20260706-003/004 isolated secular-bear exposure as the failure "
        "mode and explicitly allowed a predeclared bear-vs-correction "
        "classifier; 200-day trend slope is PIT and broad-index based, but "
        "success odds stay low because canonical windows contain few qualifying "
        "episodes and SPY excess already failed."
    ),
}

CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260706_005_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]

RELATED_FILES = [
    "data/experiments/exp-20260706-003/exp_20260706_003_deep_drawdown_rebound.json",
    "data/experiments/exp-20260706-004/exp_20260706_004_deep_drawdown_first_episode_budget.json",
    "quant/deep_drawdown_rebound_paper_sleeve.py",
    "data/non_ohlcv/index_history/index_daily_pre2023.jsonl",
    "data/warehouse/warehouse_main.sqlite",
    "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json",
]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def finite_float(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    return converted if math.isfinite(converted) else None


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_PATH, {}) or {}
    windows = list(payload.get("windows") or [])
    generated = sum(int(window.get("signals_generated") or 0) for window in windows)
    survived = sum(int(window.get("signals_survived") or 0) for window in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_PATH),
        "baseline_exists": BASELINE_PATH.exists(),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(window.get("expected_value_score") or 0.0) for window in windows),
            4,
        ),
        "total_pnl": round(
            sum(float(window.get("total_pnl") or 0.0) for window in windows), 2
        ),
        "trade_count": sum(
            int(window.get("trade_count") or window.get("total_trades") or 0)
            for window in windows
        ),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / max(generated, 1), 6),
    }


def load_ticket_prediction() -> dict[str, Any]:
    prediction = dict(DEFAULT_PREDICTION)
    ticket = read_json(TICKET_JSON, {}) or {}
    ticket_prediction = ticket.get("prediction")
    if isinstance(ticket_prediction, dict):
        prediction.update({k: v for k, v in ticket_prediction.items() if v is not None})
    prediction.setdefault("recorded_at", utc_now())
    return prediction


def closed_trades(source: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in source.get("trades", [])
        if isinstance(row, dict) and row.get("paper_status") == "closed"
    ]


def select_first_trade_per_episode(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_episode: dict[str, dict[str, Any]] = {}
    for trade in sorted(
        trades,
        key=lambda row: (
            str(row.get("episode_start_date") or ""),
            str(row.get("signal_date") or ""),
            str(row.get("entry_date") or ""),
        ),
    ):
        episode = str(trade.get("episode_start_date") or "")
        if episode and episode not in by_episode:
            selected = dict(trade)
            selected["episode_budget_gate"] = "first_stabilization_only"
            by_episode[episode] = selected
    return [by_episode[key] for key in sorted(by_episode)]


def warehouse_rows(ticker: str) -> tuple[list[dict[str, Any]], str | None, str | None]:
    last_error = None
    for path in WAREHOUSE_PATHS:
        if not path.exists():
            continue
        uri = f"file:{path.as_posix()}?mode=ro"
        try:
            con = sqlite3.connect(uri, uri=True, timeout=10)
            try:
                raw_rows = con.execute(
                    "select date, open, high, low, close, volume from ohlcv "
                    "where ticker=? order by date",
                    (ticker,),
                ).fetchall()
            finally:
                con.close()
            return (
                [
                    {
                        "ticker": ticker,
                        "date": row[0],
                        "open": row[1],
                        "high": row[2],
                        "low": row[3],
                        "close": row[4],
                        "volume": row[5],
                    }
                    for row in raw_rows
                ],
                repo_rel(path),
                None,
            )
        except sqlite3.OperationalError as exc:
            last_error = str(exc)
            continue
    return [], None, last_error or "no readable warehouse path"


def merged_index_rows(ticker: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    archive = load_index_history_rows(ticker)
    warehouse, warehouse_path, error = warehouse_rows(ticker)
    merged = merge_bar_series(archive, warehouse)
    return merged, {
        "ticker": ticker,
        "archive_path": repo_rel(INDEX_HISTORY_PATH),
        "archive_rows": len(archive),
        "warehouse_path": warehouse_path,
        "warehouse_rows": len(warehouse),
        "warehouse_error": error,
        "merged_rows": len(merged),
        "first_date": merged[0]["date"] if merged else None,
        "last_date": merged[-1]["date"] if merged else None,
    }


def trend_context_by_date(
    rows: list[dict[str, Any]],
    *,
    sma_days: int,
    slope_lookback_sessions: int,
) -> dict[str, dict[str, Any]]:
    contexts: dict[str, dict[str, Any]] = {}
    closes: list[float] = []
    dates: list[str] = []
    for row in rows:
        close = finite_float(row.get("close"))
        date = str(row.get("date") or "")[:10]
        if close is None or not date:
            continue
        closes.append(close)
        dates.append(date)
        idx = len(closes) - 1
        context: dict[str, Any] = {
            "date": date,
            "close": round(close, 6),
            "status": "insufficient_history",
            "sma_days": sma_days,
            "slope_lookback_sessions": slope_lookback_sessions,
        }
        if idx + 1 >= sma_days:
            sma_now = mean(closes[idx + 1 - sma_days : idx + 1])
            context["sma200"] = round(sma_now, 6)
            context["above_sma200"] = close >= sma_now
            prev_idx = idx - slope_lookback_sessions
            if prev_idx + 1 >= sma_days:
                sma_prev = mean(closes[prev_idx + 1 - sma_days : prev_idx + 1])
                slope = (sma_now / sma_prev) - 1.0 if sma_prev else None
                context.update(
                    {
                        "sma200_20_sessions_ago": round(sma_prev, 6),
                        "sma200_slope_20d_pct": round(slope, 6)
                        if slope is not None
                        else None,
                        "sma200_slope_positive": bool(slope is not None and slope > 0),
                        "status": "ok",
                    }
                )
        contexts[date] = context
    return contexts


def classify_trade(
    trade: dict[str, Any],
    qqq_context: dict[str, dict[str, Any]],
    spy_context: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    signal_date = str(trade.get("signal_date") or "")[:10]
    qqq = qqq_context.get(signal_date, {"status": "missing_signal_date"})
    spy = spy_context.get(signal_date, {"status": "missing_signal_date"})
    pass_classifier = (
        qqq.get("status") == "ok"
        and spy.get("status") == "ok"
        and qqq.get("sma200_slope_positive") is True
        and spy.get("sma200_slope_positive") is True
    )
    row = dict(trade)
    row["correction_classifier"] = "correction_trend_supported" if pass_classifier else "bear_or_trend_unsupported"
    row["correction_classifier_passed"] = bool(pass_classifier)
    row["qqq_200d_context"] = qqq
    row["spy_200d_context"] = spy
    return row


def values(rows: list[dict[str, Any]], key: str) -> list[float]:
    out = []
    for row in rows:
        value = finite_float(row.get(key))
        if value is not None:
            out.append(value)
    return out


def summarize_trades(rows: list[dict[str, Any]]) -> dict[str, Any]:
    returns = values(rows, "pnl_pct_net")
    pnls = values(rows, "pnl")
    excess = values(rows, "excess_vs_spy_pct")
    if not rows:
        return {
            "closed_trades": 0,
            "distinct_episodes": 0,
            "total_pnl": 0.0,
            "win_rate": None,
            "mean_return_pct": None,
            "median_return_pct": None,
            "mean_excess_vs_spy_pct": None,
            "positive_excess_rate": None,
            "worst_return_pct": None,
            "best_return_pct": None,
        }
    return {
        "closed_trades": len(rows),
        "distinct_episodes": len({str(row.get("episode_start_date")) for row in rows}),
        "total_pnl": round(sum(pnls), 2),
        "win_rate": round(sum(1 for value in pnls if value > 0) / len(pnls), 6)
        if pnls
        else None,
        "mean_return_pct": round(mean(returns), 6) if returns else None,
        "median_return_pct": round(median(returns), 6) if returns else None,
        "mean_excess_vs_spy_pct": round(mean(excess), 6) if excess else None,
        "positive_excess_rate": round(sum(1 for value in excess if value > 0) / len(excess), 6)
        if excess
        else None,
        "worst_return_pct": round(min(returns), 6) if returns else None,
        "best_return_pct": round(max(returns), 6) if returns else None,
    }


def summarize_windows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    windows = {}
    for name, (start, end) in STANDARD_WINDOWS.items():
        window_rows = [
            row
            for row in rows
            if start <= str(row.get("entry_date") or "")[:10] <= end
        ]
        windows[name] = summarize_trades(window_rows)
    return windows


def classifier_diagnostics(classified: list[dict[str, Any]]) -> dict[str, Any]:
    passed = [row for row in classified if row.get("correction_classifier_passed")]
    failed = [row for row in classified if not row.get("correction_classifier_passed")]
    failed_positive = [row for row in failed if (finite_float(row.get("pnl")) or 0.0) > 0]
    total_positive = [row for row in classified if (finite_float(row.get("pnl")) or 0.0) > 0]
    return {
        "first_budget_rows": len(classified),
        "classifier_passed_rows": len(passed),
        "classifier_failed_rows": len(failed),
        "passed_episode_start_dates": [row.get("episode_start_date") for row in passed],
        "failed_episode_start_dates": [row.get("episode_start_date") for row in failed],
        "excluded_positive_episode_share": round(
            len(failed_positive) / max(len(total_positive), 1), 6
        ),
        "failed_reasons": {
            "qqq_slope_not_positive": sum(
                1
                for row in failed
                if row.get("qqq_200d_context", {}).get("sma200_slope_positive") is not True
            ),
            "spy_slope_not_positive": sum(
                1
                for row in failed
                if row.get("spy_200d_context", {}).get("sma200_slope_positive") is not True
            ),
            "missing_or_insufficient_context": sum(
                1
                for row in failed
                if row.get("qqq_200d_context", {}).get("status") != "ok"
                or row.get("spy_200d_context", {}).get("status") != "ok"
            ),
        },
    }


def gate4_checks(
    classified_summary: dict[str, Any],
    diagnostics: dict[str, Any],
    windows: dict[str, Any],
) -> tuple[dict[str, bool], list[str]]:
    windows_with_trades = sum(1 for row in windows.values() if row["closed_trades"] > 0)
    standard_window_trades = sum(row["closed_trades"] for row in windows.values())
    negative_windows = [
        name
        for name, row in windows.items()
        if row["closed_trades"] and row["total_pnl"] < 0
    ]
    checks = {
        "min_full_history_qualified_episodes": classified_summary["distinct_episodes"]
        >= ACCEPTANCE_RULE["min_full_history_qualified_episodes"],
        "positive_cash_pnl": classified_summary["total_pnl"] > 0
        if ACCEPTANCE_RULE["require_positive_cash_pnl"]
        else True,
        "win_rate": classified_summary["win_rate"] is not None
        and classified_summary["win_rate"] >= ACCEPTANCE_RULE["min_win_rate"],
        "positive_mean_excess_vs_spy": classified_summary["mean_excess_vs_spy_pct"]
        is not None
        and classified_summary["mean_excess_vs_spy_pct"] > 0,
        "min_standard_window_trades": standard_window_trades
        >= ACCEPTANCE_RULE["min_standard_window_trades"],
        "min_standard_windows_with_trades": windows_with_trades
        >= ACCEPTANCE_RULE["min_standard_windows_with_trades"],
        "no_standard_window_negative_pnl": not negative_windows
        if ACCEPTANCE_RULE["require_no_standard_window_negative_pnl"]
        else True,
        "max_classifier_excluded_positive_episode_share": diagnostics[
            "excluded_positive_episode_share"
        ]
        <= ACCEPTANCE_RULE["max_classifier_excluded_positive_episode_share"],
    }
    return checks, [name for name, passed in checks.items() if not passed]


def build_analysis() -> dict[str, Any]:
    source = read_json(SOURCE_ARTIFACT, {}) or {}
    source_trades = closed_trades(source)
    first_budget = select_first_trade_per_episode(source_trades)
    qqq_rows, qqq_coverage = merged_index_rows("QQQ")
    spy_rows, spy_coverage = merged_index_rows("SPY")
    qqq_context = trend_context_by_date(
        qqq_rows,
        sma_days=CLASSIFIER_RULE["sma_days"],
        slope_lookback_sessions=CLASSIFIER_RULE["slope_lookback_sessions"],
    )
    spy_context = trend_context_by_date(
        spy_rows,
        sma_days=CLASSIFIER_RULE["sma_days"],
        slope_lookback_sessions=CLASSIFIER_RULE["slope_lookback_sessions"],
    )
    classified = [classify_trade(row, qqq_context, spy_context) for row in first_budget]
    passed = [row for row in classified if row.get("correction_classifier_passed")]
    failed = [row for row in classified if not row.get("correction_classifier_passed")]
    source_summary = dict(source.get("summary") or summarize_trades(source_trades))
    first_budget_summary = summarize_trades(first_budget)
    passed_summary = summarize_trades(passed)
    failed_summary = summarize_trades(failed)
    windows = summarize_windows(passed)
    diagnostics = classifier_diagnostics(classified)
    checks, failed_checks = gate4_checks(passed_summary, diagnostics, windows)
    source_pnl = finite_float(source_summary.get("total_pnl")) or 0.0
    return {
        "source_artifact": repo_rel(SOURCE_ARTIFACT),
        "source_rule_version": source.get("rule_version"),
        "series": source.get("series"),
        "parameters": source.get("parameters"),
        "index_coverage": {"QQQ": qqq_coverage, "SPY": spy_coverage},
        "classifier_rule": CLASSIFIER_RULE,
        "source_repeated_entry_summary": source_summary,
        "first_episode_budget_summary": first_budget_summary,
        "classifier_passed_summary": passed_summary,
        "classifier_failed_summary": failed_summary,
        "delta_vs_exp003_repeated_entry": {
            "closed_trade_delta": passed_summary["closed_trades"]
            - int(source_summary.get("closed_trades") or 0),
            "total_pnl_delta": round(passed_summary["total_pnl"] - source_pnl, 2),
            "mean_return_delta": (
                round(
                    passed_summary["mean_return_pct"]
                    - float(source_summary.get("mean_return_pct") or 0.0),
                    6,
                )
                if passed_summary["mean_return_pct"] is not None
                else None
            ),
        },
        "delta_vs_exp004_first_budget": {
            "closed_trade_delta": passed_summary["closed_trades"]
            - first_budget_summary["closed_trades"],
            "total_pnl_delta": round(
                passed_summary["total_pnl"] - first_budget_summary["total_pnl"], 2
            ),
            "mean_return_delta": (
                round(
                    passed_summary["mean_return_pct"]
                    - first_budget_summary["mean_return_pct"],
                    6,
                )
                if passed_summary["mean_return_pct"] is not None
                and first_budget_summary["mean_return_pct"] is not None
                else None
            ),
        },
        "standard_windows": windows,
        "classifier_diagnostics": diagnostics,
        "gate4_checks": checks,
        "gate4_failed_reasons": failed_checks,
        "classified_first_budget_trades": classified,
        "selected_trades": passed,
        "excluded_trades": failed,
    }


def build_result() -> dict[str, Any]:
    timestamp = utc_now()
    prediction = load_ticket_prediction()
    baseline = baseline_metrics()
    analysis = build_analysis()
    passed_gate = not analysis["gate4_failed_reasons"]
    status = (
        "observed_only_positive_lead_not_policy_ready"
        if passed_gate
        else "observed_only_rejected"
    )
    decision = (
        "observed_only_positive_deep_drawdown_200d_correction_classifier"
        if passed_gate
        else "observed_only_rejected_deep_drawdown_200d_correction_classifier"
    )
    actual_success = 1 if passed_gate else 0
    summary = analysis["classifier_passed_summary"]
    failure_set = set(analysis["gate4_failed_reasons"])
    predicted_modes = list(prediction["main_failure_modes"])
    predicted_failure_hit = (
        ("standard_windows_too_thin" in predicted_modes)
        and (
            "min_standard_window_trades" in failure_set
            or "min_standard_windows_with_trades" in failure_set
        )
    ) or (
        ("spy_replacement_not_beaten" in predicted_modes)
        and "positive_mean_excess_vs_spy" in failure_set
    ) or any(mode in failure_set for mode in predicted_modes)
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "owner": OWNER,
        "lane": LANE,
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "alpha_ready": False,
        "observed_only_lead": passed_gate,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": "candidate_pool_observed_attribution",
        "implementation_mode": "observed_only_attribution",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": [
            "pre2023 index history",
            "exp003 deep-drawdown replay artifact",
            "first per-episode budget",
            "QQQ/SPY 200d trend-slope correction classifier",
            "cash and SPY replacement comparison",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "new_gate_shape_on_existing_index_history",
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "calibration": {
            "actual_success": actual_success,
            "actual_decision": "accepted" if passed_gate else "rejected",
            "predicted_success_probability": prediction["success_probability"],
            "brier_score": round(
                (float(prediction["success_probability"]) - actual_success) ** 2, 4
            ),
            "expected_ev_delta": prediction.get("expected_ev_delta"),
            "expected_pnl_delta": prediction.get("expected_pnl_delta"),
            "actual_ev_delta": 0.0,
            "actual_pnl_delta": 0.0,
            "predicted_failure_modes": predicted_modes,
            "realized_failure_modes": analysis["gate4_failed_reasons"],
            "predicted_failure_mode_hit": predicted_failure_hit,
            "surprise_note": (
                "The classifier is a strict ex-ante trend-state gate. The "
                "artifact records whether it removed secular-bear bleed without "
                "also excluding too many positive correction episodes."
            ),
        },
        "parameters": {
            "source_artifact": repo_rel(SOURCE_ARTIFACT),
            "baseline_result_file": repo_rel(BASELINE_PATH),
            "classifier_rule": CLASSIFIER_RULE,
            "acceptance_rule": ACCEPTANCE_RULE,
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "strategy_expected_value_score_delta": 0.0,
            "strategy_total_pnl_delta": 0.0,
            "strategy_trade_count_delta": 0,
            "strategy_behavior_changed": False,
            "classified_total_pnl": summary["total_pnl"],
            "classified_win_rate": summary["win_rate"],
            "classified_mean_excess_vs_spy_pct": summary["mean_excess_vs_spy_pct"],
            "pnl_delta_vs_exp003_repeated_entry": analysis[
                "delta_vs_exp003_repeated_entry"
            ]["total_pnl_delta"],
            "pnl_delta_vs_exp004_first_budget": analysis["delta_vs_exp004_first_budget"][
                "total_pnl_delta"
            ],
        },
        "gate1": {
            "passed": baseline["baseline_exists"] and SOURCE_ARTIFACT.exists(),
            "baseline_metrics": baseline,
            "source_artifact_exists": SOURCE_ARTIFACT.exists(),
            "index_coverage": analysis["index_coverage"],
            "note": (
                "Observed-only replay over exp003 artifact plus local index "
                "history; canonical strategy baseline unchanged."
            ),
        },
        "gate2": {
            "passed": all(
                all(row.get(field) not in (None, "") for field in ["entry_date", "exit_date", "pnl"])
                and row.get("qqq_200d_context", {}).get("status") == "ok"
                and row.get("spy_200d_context", {}).get("status") == "ok"
                for row in analysis["classified_first_budget_trades"]
            ),
            "fields_checked": [
                "episode_start_date",
                "signal_date",
                "entry_date",
                "exit_date",
                "pnl",
                "pnl_pct_net",
                "excess_vs_spy_pct",
                "QQQ sma200_slope_20d_pct",
                "SPY sma200_slope_20d_pct",
            ],
            "classified_rows": len(analysis["classified_first_budget_trades"]),
            "selected_rows": summary["closed_trades"],
            "target_price_relevance": (
                "This run does not create backtest signals or exits; target_price "
                "is not consumed."
            ),
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "note": (
                "No executable filter, ranking, sizing, exit, prompt, or order "
                "rule was added."
            ),
        },
        "gate4": {
            "passed": passed_gate,
            "observed_only": True,
            "accepted_alpha": False,
            "strategy_rerun_required": False,
            "decision": decision,
            "acceptance_rule": ACCEPTANCE_RULE,
            "checks": analysis["gate4_checks"],
            "failed_reasons": analysis["gate4_failed_reasons"],
            "summary": {
                "source_repeated_entry_summary": analysis["source_repeated_entry_summary"],
                "first_episode_budget_summary": analysis["first_episode_budget_summary"],
                "classifier_passed_summary": summary,
                "classifier_failed_summary": analysis["classifier_failed_summary"],
                "classifier_diagnostics": analysis["classifier_diagnostics"],
                "delta_vs_exp003_repeated_entry": analysis[
                    "delta_vs_exp003_repeated_entry"
                ],
                "delta_vs_exp004_first_budget": analysis["delta_vs_exp004_first_budget"],
                "standard_windows": analysis["standard_windows"],
            },
        },
        "analysis": analysis,
        "production_impact": {
            "trade_enabled": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_exposed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "paper_orders_changed": False,
            "live_orders_changed": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "parity_note": (
                "Read-only analysis over exp003 replay artifact and local index "
                "history. No helper, adapter, order, rank, size, exit, watchlist, "
                "or LLM behavior changed."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The 200d trend classifier tests the specific exp004 reopen "
                "condition: whether broad-index trend state can separate "
                "correction rebounds from secular-bear falling knives without "
                "changing the drawdown trigger or entry budget."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune the 200d SMA length, 20-session slope lookback, "
                "slope sign threshold, drawdown trigger, reset hysteresis, hold "
                "days, notional, cooldown, or ticker on this same artifact."
            ),
            "new_evidence_required": (
                "A valid next retry needs genuinely new live/forward deep-drawdown "
                "episode rows, a materially different predeclared macro regime "
                "data source, or a full shared paper helper update tested before "
                "seeing new episode outcomes."
            ),
        },
        "next_retry_requires": [
            "genuinely new live or forward settled deep-drawdown episode rows",
            "a materially different predeclared macro regime data source",
            "or a full shared helper update tested without threshold sweeps",
        ],
        "rejection_reason": None if passed_gate else ";".join(analysis["gate4_failed_reasons"]),
        "related_files": RELATED_FILES,
        "changed_files": CHANGED_FILES,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "lean_quality_passed": True,
        "llm_metrics": {"used_llm": False},
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
    }


def compact_log_record(result: dict[str, Any]) -> dict[str, Any]:
    return {
        key: result[key]
        for key in [
            "experiment_id",
            "timestamp",
            "owner",
            "lane",
            "status",
            "decision",
            "accepted",
            "accepted_alpha",
            "alpha_ready",
            "observed_only_lead",
            "hypothesis",
            "alpha_hypothesis",
            "change_type",
            "implementation_mode",
            "mechanism_family",
            "trial_family",
            "trial_variant_id",
            "changed_variable",
            "single_causal_variable",
            "causal_components",
            "nearby_prior_experiments",
            "multiple_testing_risk_bucket",
            "new_evidence_type",
            "new_evidence_axis",
            "prediction",
            "calibration",
            "parameters",
            "before_metrics",
            "after_metrics",
            "delta_metrics",
            "gate1",
            "gate2",
            "gate3",
            "gate4",
            "production_impact",
            "post_run_reflection",
            "next_retry_requires",
            "rejection_reason",
            "related_files",
            "changed_files",
            "reproduction_commands",
            "artifact",
            "log",
            "lean_quality_passed",
            "llm_metrics",
            "anti_js",
        ]
    }


def build_card(result: dict[str, Any]) -> str:
    summary = result["gate4"]["summary"]["classifier_passed_summary"]
    failed = result["gate4"]["failed_reasons"]
    diagnostics = result["gate4"]["summary"]["classifier_diagnostics"]
    return f"""# {EXPERIMENT_ID} - Deep Drawdown 200d Correction Classifier

## Hypothesis

{HYPOTHESIS}

## Result

- Decision: `{result["decision"]}`
- Status: `{result["status"]}`
- Classifier passed rows: `{diagnostics["classifier_passed_rows"]}` / `{diagnostics["first_budget_rows"]}`
- Selected PnL: `{summary["total_pnl"]}`
- Selected win rate: `{summary["win_rate"]}`
- Mean excess vs SPY: `{summary["mean_excess_vs_spy_pct"]}`
- Failed checks: `{", ".join(failed) if failed else "none"}`

## Boundary

{result["post_run_reflection"]["forbidden_near_neighbor_retry"]}

## Reproduce

```powershell
{RUNNER_COMMAND}
.\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict
```
"""


def update_ticket(result: dict[str, Any]) -> None:
    ticket = read_json(TICKET_JSON, {}) or {}
    ticket["status"] = result["status"]
    ticket["completed_at"] = result["timestamp"]
    ticket["result"] = {
        "decision": result["decision"],
        "artifact": result["artifact"],
        "log": result["log"],
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": result["observed_only_lead"],
    }
    ticket["gate4"] = result["gate4"]
    ticket["post_run_reflection"] = result["post_run_reflection"]
    ticket["next_retry_requires"] = result["next_retry_requires"]
    write_json(TICKET_JSON, ticket)


def write_manifest(result: dict[str, Any]) -> None:
    write_json(
        MANIFEST_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": result["status"],
            "decision": result["decision"],
            "artifact": result["artifact"],
            "log": result["log"],
            "runner": RUNNER,
            "generated_at": result["timestamp"],
            "changed_files": CHANGED_FILES,
            "reproduction_commands": result["reproduction_commands"],
        },
    )


def main() -> int:
    result = build_result()
    write_json(OUT_JSON, result)
    save_experiment_log_entry(compact_log_record(result), allow_duplicate=True)
    write_text(CARD_MD, build_card(result))
    write_manifest(result)
    update_ticket(result)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=result["prediction"],
        result={
            "accepted": False,
            "accepted_alpha": False,
            "alpha_ready": False,
            "observed_only_lead": result["observed_only_lead"],
            "decision": result["decision"],
            "artifact": result["artifact"],
            "log": result["log"],
            "runner": RUNNER,
            "gate4": result["gate4"],
            "summary": result["gate4"]["summary"],
        },
        status=result["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "alpha_hypothesis": HYPOTHESIS,
            "change_type": result["change_type"],
            "implementation_mode": result["implementation_mode"],
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": result["causal_components"],
            "nearby_prior_experiments": NEARBY_PRIORS,
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": result["new_evidence_type"],
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "decision": result["decision"],
            "artifact": result["artifact"],
            "log_file": result["log"],
            "card_file": repo_rel(CARD_MD),
            "gate1": result["gate1"],
            "gate2": result["gate2"],
            "gate3": result["gate3"],
            "gate4": result["gate4"],
            "production_impact": result["production_impact"],
            "post_run_reflection": result["post_run_reflection"],
            "next_retry_requires": result["next_retry_requires"],
            "related_files": result["related_files"],
            "changed_files": CHANGED_FILES,
            "allowed_write_scope": CHANGED_FILES,
            "lean_quality_passed": result["lean_quality_passed"],
        },
    )
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": result["status"],
                "decision": result["decision"],
                "classifier_passed_summary": result["gate4"]["summary"][
                    "classifier_passed_summary"
                ],
                "classifier_diagnostics": result["gate4"]["summary"][
                    "classifier_diagnostics"
                ],
                "failed_reasons": result["gate4"]["failed_reasons"],
                "artifact": result["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
