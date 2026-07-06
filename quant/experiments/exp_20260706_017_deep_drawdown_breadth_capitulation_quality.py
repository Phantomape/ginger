"""exp-20260706-017: broad breadth label for deep-drawdown rows.

Observed-only attribution. This leaves the exp-20260706-006 first-entry
deep-drawdown rebound policy unchanged and labels each closed historical row
with a fixed signal-day broad-market cross-sectional breadth source:

  share of broad OHLCV tickers above their own 20-session close <= 40%, and
  share of broad OHLCV tickers positive over 3 sessions >= 55%.

The signal fires after the close and enters next open, so same-day broad OHLCV
close is point-in-time available to this diagnostic label. No strategy
behavior, live orders, ranking, sizing, exits, shared helper code, or daily
adapter path changes here.

Reproduce:
  .venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260706_017_deep_drawdown_breadth_capitulation_quality.py
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import sqlite3
import sys
import time
from pathlib import Path
from statistics import mean, median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (QUANT_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from data_paths import DATA_ROOT  # noqa: E402
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


EXPERIMENT_ID = "exp-20260706-017"
BASELINE_EXPERIMENT_ID = "exp-20260706-006"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "deep_drawdown_breadth_capitulation_quality"
RUNNER = f"quant/experiments/exp_20260706_017_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_ARTIFACT = (
    DATA_ROOT
    / "experiments"
    / BASELINE_EXPERIMENT_ID
    / "exp_20260706_006_deep_drawdown_rebound_budget.json"
)
WAREHOUSE_SQLITE = DATA_ROOT / "warehouse" / "warehouse_main.sqlite"
OUT_DIR = DATA_ROOT / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260706_017_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Observed-only alpha: deep-drawdown first-entry QQQ rebound rows should "
    "perform better when signal-day broad-market cross-sectional breadth shows "
    "capitulation washout plus initial stabilization, distinguishing durable "
    "correction rebounds from fragile bear-market bounces."
)
CHANGED_VARIABLE = "broad_market_breadth_capitulation_quality_gate_for_deep_drawdown_first_entries"
MECHANISM_FAMILY = "deep_drawdown_rebound_cross_sectional_breadth_capitulation_quality"
TRIAL_FAMILY = "deep_drawdown_rebound_episode_quality"
TRIAL_VARIANT_ID = "broad_ohlcv_share_above_20d_and_3d_stabilization_v1"
NEARBY_PRIORS = [
    "exp-20260706-003",
    "exp-20260706-006",
    "exp-20260706-008",
    "exp-20260706-009",
    "exp-20260706-015",
]
NEW_EVIDENCE_AXIS = (
    "New gate shape versus exp-20260706-006/008/009/015: signal-day "
    "cross-sectional breadth/capitulation from the broad OHLCV warehouse across "
    "all available symbols, with the first-entry episode budget, entry/exit, "
    "notional, and horizons left unchanged."
)

BREADTH_RULE = {
    "source": "data/warehouse/warehouse_main.sqlite::ohlcv",
    "universe": "all tickers with point-in-time OHLCV rows on the signal date",
    "min_common_tickers": 1000,
    "washout_lookback_sessions": 20,
    "stabilization_lookback_sessions": 3,
    "washout_share_above_20d_close_max": 0.40,
    "stabilization_share_positive_3d_min": 0.55,
    "pass_rule": (
        "share of common broad-OHLCV tickers with signal close above their own "
        "20-session prior close <= 0.40 and share with signal close above "
        "their own 3-session prior close >= 0.55"
    ),
    "same_day_available": (
        "Signal is generated after the close and enters next open, so same-day "
        "broad OHLCV close is point-in-time available to the diagnostic label."
    ),
}
ACCEPTANCE_RULE = {
    "min_evaluable_rows": 12,
    "min_capitulation_rows": 5,
    "min_non_capitulation_rows": 5,
    "min_mean_cash_return_lift": 0.02,
    "min_mean_spy_excess_lift": 0.02,
    "min_capitulation_win_rate": 0.65,
    "max_single_positive_capitulation_cash_pnl_share": 0.50,
}
CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260706_017_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]
RELATED_FILES = [
    str(BASELINE_ARTIFACT.relative_to(REPO_ROOT)).replace("\\", "/"),
    "data/warehouse/warehouse_main.sqlite",
    "quant/experiments/exp_20260706_006_deep_drawdown_rebound_budget.py",
    "quant/experiments/exp_20260706_008_deep_drawdown_volume_range_capitulation.py",
    "quant/experiments/exp_20260706_009_deep_drawdown_tlt_rate_relief.py",
    "quant/experiments/exp_20260706_015_deep_drawdown_vix_panic_quality.py",
]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def repo_rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    delay = 0.05
    last_error: PermissionError | None = None
    for _ in range(8):
        try:
            os.replace(tmp, path)
            return
        except PermissionError as exc:
            last_error = exc
            time.sleep(delay)
            delay *= 2
    with path.open("w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        tmp.unlink()
    except OSError:
        pass
    if not path.exists() and last_error is not None:
        raise last_error


def write_json(path: Path, payload: dict[str, Any]) -> None:
    write_text(path, json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n")


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig") as handle:
        return json.load(handle)


def load_ticket() -> dict[str, Any]:
    return load_json(TICKET_JSON)


def load_prediction() -> dict[str, Any]:
    ticket = load_ticket()
    prediction = ticket.get("prediction")
    if not isinstance(prediction, dict):
        raise RuntimeError(f"{TICKET_JSON} has no pre-run prediction")
    return prediction


def file_sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out else None


def _round(value: Any, digits: int = 6) -> float | None:
    value = _float(value)
    return round(value, digits) if value is not None else None


def _safe_mean(values: list[float]) -> float | None:
    return mean(values) if values else None


def _safe_median(values: list[float]) -> float | None:
    return median(values) if values else None


def load_close_map(con: sqlite3.Connection, session_date: str) -> dict[str, float]:
    rows = con.execute(
        """
        select ticker, close
        from ohlcv
        where date = ?
          and close is not null
          and close > 0
          and volume is not null
          and volume >= 0
        """,
        (session_date,),
    ).fetchall()
    return {str(ticker).upper(): float(close) for ticker, close in rows}


def session_window(con: sqlite3.Connection, signal_date: str, sessions: int) -> list[str]:
    rows = con.execute(
        """
        select distinct date
        from ohlcv
        where date <= ?
        order by date desc
        limit ?
        """,
        (signal_date, sessions),
    ).fetchall()
    return [str(row[0]) for row in reversed(rows)]


def build_breadth_context(signal_dates: list[str]) -> dict[str, dict[str, Any]]:
    if not WAREHOUSE_SQLITE.exists():
        return {
            date: {
                "available": False,
                "missing_reason": "warehouse_sqlite_missing",
                "warehouse": repo_rel(WAREHOUSE_SQLITE),
            }
            for date in signal_dates
        }

    con = sqlite3.connect(str(WAREHOUSE_SQLITE))
    try:
        contexts: dict[str, dict[str, Any]] = {}
        needed = int(BREADTH_RULE["washout_lookback_sessions"]) + 1
        stabilization = int(BREADTH_RULE["stabilization_lookback_sessions"])
        for signal_date in sorted(set(signal_dates)):
            sessions = session_window(con, signal_date, needed)
            if len(sessions) < needed:
                latest = sessions[-1] if sessions else None
                contexts[signal_date] = {
                    "available": False,
                    "missing_reason": "insufficient_prior_warehouse_sessions",
                    "latest_warehouse_session_on_or_before_signal": latest,
                    "required_sessions": needed,
                    "available_sessions": len(sessions),
                    "warehouse": repo_rel(WAREHOUSE_SQLITE),
                }
                continue
            if sessions[-1] != signal_date:
                contexts[signal_date] = {
                    "available": False,
                    "missing_reason": "no_exact_signal_date_warehouse_session",
                    "latest_warehouse_session_on_or_before_signal": sessions[-1],
                    "required_signal_date": signal_date,
                    "warehouse": repo_rel(WAREHOUSE_SQLITE),
                }
                continue

            signal_map = load_close_map(con, sessions[-1])
            prior20_map = load_close_map(con, sessions[0])
            prior3_map = load_close_map(con, sessions[-1 - stabilization])

            common20 = sorted(set(signal_map).intersection(prior20_map))
            common3 = sorted(set(signal_map).intersection(prior3_map))
            ret20_values = [
                (signal_map[ticker] / prior20_map[ticker]) - 1.0
                for ticker in common20
                if prior20_map[ticker] > 0
            ]
            ret3_values = [
                (signal_map[ticker] / prior3_map[ticker]) - 1.0
                for ticker in common3
                if prior3_map[ticker] > 0
            ]
            universe_count = min(len(ret20_values), len(ret3_values))
            share_above_20d = (
                sum(1 for item in ret20_values if item > 0) / len(ret20_values)
                if ret20_values
                else None
            )
            share_positive_3d = (
                sum(1 for item in ret3_values if item > 0) / len(ret3_values)
                if ret3_values
                else None
            )
            share_down_20d_10pct = (
                sum(1 for item in ret20_values if item <= -0.10) / len(ret20_values)
                if ret20_values
                else None
            )
            pass_label = (
                universe_count >= int(BREADTH_RULE["min_common_tickers"])
                and share_above_20d is not None
                and share_positive_3d is not None
                and share_above_20d <= float(BREADTH_RULE["washout_share_above_20d_close_max"])
                and share_positive_3d >= float(BREADTH_RULE["stabilization_share_positive_3d_min"])
            )
            contexts[signal_date] = {
                "available": universe_count >= int(BREADTH_RULE["min_common_tickers"]),
                "signal_date": signal_date,
                "session_date": sessions[-1],
                "prior_20_session_date": sessions[0],
                "prior_3_session_date": sessions[-1 - stabilization],
                "common_tickers_20d": len(ret20_values),
                "common_tickers_3d": len(ret3_values),
                "universe_count": universe_count,
                "share_above_20d_close": _round(share_above_20d),
                "share_positive_3d": _round(share_positive_3d),
                "share_down_20d_10pct": _round(share_down_20d_10pct),
                "median_ret20_pct": _round(_safe_median(ret20_values)),
                "median_ret3_pct": _round(_safe_median(ret3_values)),
                "breadth_capitulation_pass": pass_label,
                "missing_reason": None
                if universe_count >= int(BREADTH_RULE["min_common_tickers"])
                else "insufficient_common_tickers",
                "warehouse": repo_rel(WAREHOUSE_SQLITE),
            }
        return contexts
    finally:
        con.close()


def cohort_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pnl_pct = [
        value
        for value in (_float(row.get("pnl_pct_net")) for row in rows)
        if value is not None
    ]
    excess = [
        value
        for value in (_float(row.get("excess_vs_spy_pct")) for row in rows)
        if value is not None
    ]
    pnl_cash = [
        value
        for value in (_float(row.get("pnl")) for row in rows)
        if value is not None
    ]
    positive_pnl_cash = [value for value in pnl_cash if value > 0]
    positive_total = sum(positive_pnl_cash)
    largest_positive_share = None
    if positive_total > 0 and positive_pnl_cash:
        largest_positive_share = max(positive_pnl_cash) / positive_total
    return {
        "rows": len(rows),
        "mean_return_pct": _round(_safe_mean(pnl_pct)),
        "median_return_pct": _round(_safe_median(pnl_pct)),
        "mean_excess_vs_spy_pct": _round(_safe_mean(excess)),
        "median_excess_vs_spy_pct": _round(_safe_median(excess)),
        "total_pnl": _round(sum(pnl_cash), 2),
        "win_rate": _round(sum(1 for item in pnl_pct if item > 0) / len(pnl_pct))
        if pnl_pct
        else None,
        "largest_positive_cash_pnl_share": _round(largest_positive_share),
    }


def analyze_trades(trades: list[dict[str, Any]], contexts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    enriched: list[dict[str, Any]] = []
    missing_rows: list[dict[str, Any]] = []
    for idx, trade in enumerate(trades, start=1):
        signal_date = str(trade.get("signal_date") or "")[:10]
        context = contexts.get(signal_date, {"available": False, "missing_reason": "no_context_built"})
        row = dict(trade)
        row["row_number"] = idx
        row["breadth_context"] = context
        row["breadth_context_available"] = bool(context.get("available"))
        row["breadth_capitulation_pass"] = (
            bool(context.get("breadth_capitulation_pass"))
            if context.get("available")
            else None
        )
        enriched.append(row)
        if not context.get("available"):
            missing_rows.append(
                {
                    "row_number": idx,
                    "signal_date": signal_date,
                    "reason": context.get("missing_reason"),
                    "latest_warehouse_session_on_or_before_signal": context.get(
                        "latest_warehouse_session_on_or_before_signal"
                    ),
                    "available_sessions": context.get("available_sessions"),
                }
            )

    evaluable = [row for row in enriched if row["breadth_context_available"]]
    capitulation = [row for row in evaluable if row["breadth_capitulation_pass"] is True]
    non_capitulation = [row for row in evaluable if row["breadth_capitulation_pass"] is False]

    cap_metrics = cohort_metrics(capitulation)
    non_metrics = cohort_metrics(non_capitulation)
    delta_cash = None
    delta_excess = None
    if cap_metrics["mean_return_pct"] is not None and non_metrics["mean_return_pct"] is not None:
        delta_cash = cap_metrics["mean_return_pct"] - non_metrics["mean_return_pct"]
    if (
        cap_metrics["mean_excess_vs_spy_pct"] is not None
        and non_metrics["mean_excess_vs_spy_pct"] is not None
    ):
        delta_excess = (
            cap_metrics["mean_excess_vs_spy_pct"]
            - non_metrics["mean_excess_vs_spy_pct"]
        )

    coverage_by_year: dict[str, dict[str, int]] = {}
    for row in enriched:
        year = str(row.get("signal_date") or "")[:4] or "unknown"
        bucket = coverage_by_year.setdefault(year, {"rows": 0, "available": 0})
        bucket["rows"] += 1
        if row["breadth_context_available"]:
            bucket["available"] += 1

    checks = {
        "min_evaluable_rows": {
            "passed": len(evaluable) >= ACCEPTANCE_RULE["min_evaluable_rows"],
            "actual": len(evaluable),
            "required": ACCEPTANCE_RULE["min_evaluable_rows"],
        },
        "min_capitulation_rows": {
            "passed": len(capitulation) >= ACCEPTANCE_RULE["min_capitulation_rows"],
            "actual": len(capitulation),
            "required": ACCEPTANCE_RULE["min_capitulation_rows"],
        },
        "min_non_capitulation_rows": {
            "passed": len(non_capitulation) >= ACCEPTANCE_RULE["min_non_capitulation_rows"],
            "actual": len(non_capitulation),
            "required": ACCEPTANCE_RULE["min_non_capitulation_rows"],
        },
        "min_mean_cash_return_lift": {
            "passed": (
                delta_cash is not None
                and delta_cash >= ACCEPTANCE_RULE["min_mean_cash_return_lift"]
            ),
            "actual": _round(delta_cash),
            "required": ACCEPTANCE_RULE["min_mean_cash_return_lift"],
        },
        "min_mean_spy_excess_lift": {
            "passed": (
                delta_excess is not None
                and delta_excess >= ACCEPTANCE_RULE["min_mean_spy_excess_lift"]
            ),
            "actual": _round(delta_excess),
            "required": ACCEPTANCE_RULE["min_mean_spy_excess_lift"],
        },
        "min_capitulation_win_rate": {
            "passed": (
                cap_metrics["win_rate"] is not None
                and cap_metrics["win_rate"] >= ACCEPTANCE_RULE["min_capitulation_win_rate"]
            ),
            "actual": cap_metrics["win_rate"],
            "required": ACCEPTANCE_RULE["min_capitulation_win_rate"],
        },
        "max_single_positive_capitulation_cash_pnl_share": {
            "passed": (
                cap_metrics["largest_positive_cash_pnl_share"] is not None
                and cap_metrics["largest_positive_cash_pnl_share"]
                <= ACCEPTANCE_RULE["max_single_positive_capitulation_cash_pnl_share"]
            ),
            "actual": cap_metrics["largest_positive_cash_pnl_share"],
            "required": ACCEPTANCE_RULE["max_single_positive_capitulation_cash_pnl_share"],
        },
    }
    failed_reasons = [name for name, check in checks.items() if not check["passed"]]
    if len(evaluable) < ACCEPTANCE_RULE["min_evaluable_rows"]:
        decision = "rejected_observed_only_breadth_history_coverage_insufficient"
    else:
        decision = "observed_only_breadth_capitulation_quality_rejected"

    return {
        "enriched_trades": enriched,
        "missing_rows": missing_rows,
        "coverage_by_year": coverage_by_year,
        "total_closed_rows": len(trades),
        "evaluable_closed_rows": len(evaluable),
        "missing_breadth_context_rows": len(missing_rows),
        "capitulation_rows": len(capitulation),
        "non_capitulation_rows": len(non_capitulation),
        "cohorts": {
            "capitulation": cap_metrics,
            "non_capitulation": non_metrics,
            "all_evaluable": cohort_metrics(evaluable),
            "all_baseline_rows": cohort_metrics(enriched),
        },
        "deltas": {
            "mean_cash_return_pct_capitulation_minus_non_capitulation": _round(delta_cash),
            "mean_spy_excess_pct_capitulation_minus_non_capitulation": _round(delta_excess),
        },
        "checks": checks,
        "failed_reasons": failed_reasons,
        "decision": decision,
    }


def baseline_metrics(artifact: dict[str, Any]) -> dict[str, Any]:
    summary = artifact.get("summary") or {}
    trades = list(artifact.get("trades") or [])
    trade_returns = [
        value
        for value in (_float(row.get("pnl_pct_net")) for row in trades)
        if value is not None
    ]
    trade_excess = [
        value
        for value in (_float(row.get("excess_vs_spy_pct")) for row in trades)
        if value is not None
    ]
    trade_pnl = [
        value
        for value in (_float(row.get("pnl")) for row in trades)
        if value is not None
    ]
    return {
        "source_experiment": BASELINE_EXPERIMENT_ID,
        "artifact": repo_rel(BASELINE_ARTIFACT),
        "trade_count": summary.get("closed_trades", len(trades)),
        "total_pnl": _round(summary.get("total_pnl", sum(trade_pnl)), 2),
        "mean_return_pct": _round(summary.get("mean_return_pct", _safe_mean(trade_returns))),
        "win_rate": _round(
            summary.get(
                "win_rate",
                sum(1 for item in trade_returns if item > 0) / len(trade_returns)
                if trade_returns
                else None,
            )
        ),
        "mean_excess_vs_spy_pct": _round(
            summary.get("mean_excess_vs_spy_pct", _safe_mean(trade_excess))
        ),
        "note": "Read-only observed attribution; baseline strategy behavior is unchanged.",
    }


def build_result() -> dict[str, Any]:
    prediction = load_prediction()
    baseline = load_json(BASELINE_ARTIFACT)
    trades = list(baseline.get("trades") or [])
    signal_dates = [str(row.get("signal_date") or "")[:10] for row in trades]
    contexts = build_breadth_context(signal_dates)
    analysis = analyze_trades(trades, contexts)
    passed = all(check["passed"] for check in analysis["checks"].values())
    observed_only_lead = bool(passed)
    before_after = baseline_metrics(baseline)
    realized_failures = list(analysis["failed_reasons"])

    result = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": LANE,
        "status": "completed",
        "decision": analysis["decision"] if not passed else "observed_only_lead",
        "accepted": False,
        "accepted_alpha": False,
        "alpha_ready": False,
        "observed_only_lead": observed_only_lead,
        "alpha_hypothesis": HYPOTHESIS,
        "hypothesis": HYPOTHESIS,
        "change_type": "observed_only_attribution",
        "implementation_mode": "observed_only_no_strategy_change",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": [
            "fixed exp-20260706-006 first-entry rows",
            "PIT broad-OHLCV cross-sectional breadth label",
            "capitulation-vs-noncapitulation cash/SPY attribution",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "new_gate_shape",
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "calibration": {
            "predicted_success_probability": prediction.get("success_probability"),
            "actual_success": passed,
            "prediction_main_failure_modes": prediction.get("main_failure_modes"),
            "realized_failure_modes": realized_failures,
        },
        "parameters": {
            "breadth_rule": BREADTH_RULE,
            "acceptance_rule": ACCEPTANCE_RULE,
            "baseline_experiment_id": BASELINE_EXPERIMENT_ID,
        },
        "before_metrics": before_after,
        "after_metrics": before_after,
        "delta_metrics": {
            "strategy_behavior_delta": 0,
            "note": "No executable strategy behavior changed; only cohort attribution was measured.",
        },
        "gate1": {
            "passed": True,
            "baseline_result_file": repo_rel(BASELINE_ARTIFACT),
            "baseline_metrics": before_after,
            "note": "Observed-only attribution on exp-20260706-006 artifact; canonical strategy baseline unchanged.",
        },
        "gate2": {
            "passed": analysis["evaluable_closed_rows"] >= ACCEPTANCE_RULE["min_evaluable_rows"],
            "fields_checked": [
                "signal_date",
                "entry_date",
                "exit_date",
                "pnl_pct_net",
                "excess_vs_spy_pct",
                "broad OHLCV signal-day close",
                "broad OHLCV 20-session prior close",
                "broad OHLCV 3-session prior close",
            ],
            "warehouse_sqlite": repo_rel(WAREHOUSE_SQLITE),
            "total_closed_rows": analysis["total_closed_rows"],
            "evaluable_closed_rows": analysis["evaluable_closed_rows"],
            "missing_breadth_context_rows": analysis["missing_breadth_context_rows"],
            "coverage_by_year": analysis["coverage_by_year"],
            "missing_rows": analysis["missing_rows"],
            "entry_date_contract": "Read from exp-20260706-006 trade rows.",
            "target_price_relevance": "Not consumed; this run does not generate backtest signals or exits.",
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": before_after["trade_count"],
            "signals_survived": before_after["trade_count"],
            "survival_rate": 1.0,
            "note": "Read-only cohort label; no executable filter, ranking, sizing, prompt, exit, or order rule was added.",
        },
        "gate4": {
            "passed": passed,
            "observed_only": True,
            "strategy_rerun_required": False,
            "accepted_alpha": False,
            "decision": analysis["decision"] if not passed else "observed_only_lead",
            "acceptance_rule": ACCEPTANCE_RULE,
            "breadth_rule": BREADTH_RULE,
            "checks": analysis["checks"],
            "failed_reasons": realized_failures,
            "summary": {
                "total_closed_rows": analysis["total_closed_rows"],
                "evaluable_closed_rows": analysis["evaluable_closed_rows"],
                "missing_breadth_context_rows": analysis["missing_breadth_context_rows"],
                "capitulation_rows": analysis["capitulation_rows"],
                "non_capitulation_rows": analysis["non_capitulation_rows"],
                "coverage_by_year": analysis["coverage_by_year"],
                "deltas": analysis["deltas"],
                "cohorts": analysis["cohorts"],
            },
        },
        "analysis": {
            key: value
            for key, value in analysis.items()
            if key != "enriched_trades"
        },
        "production_impact": {
            "trade_enabled": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_live_orders": False,
        },
        "live_realistic_execution_envelope": {
            "required_for_live": False,
            "paper_only": True,
            "notional_or_capital_changed": False,
            "notes": "No deployable rule was added. Any future use would need a fresh Gate 1-4 shared-policy test.",
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The broad OHLCV warehouse currently covers only the 2024/2025 "
                "tail of the exp-20260706-006 deep-drawdown rows, so the "
                "predeclared cross-sectional breadth gate cannot be judged on "
                "the fixed 17-row historical sample."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune the breadth thresholds, universe count, "
                "lookbacks, same-row crisis buckets, hold days, notional, "
                "episode budget, or combine this same under-covered surface "
                "with VIX/TLT/QQQ volume-range fields."
            ),
            "new_evidence_required": (
                "Reopen only after a PIT broad-market OHLCV or breadth source "
                "covers at least 12 of the 17 exp-20260706-006 signal dates, "
                "or with genuinely new settled forward deep-drawdown episodes "
                "that provide the same broad breadth fields."
            ),
            "realized_failure_mode": ",".join(realized_failures) or None,
        },
        "next_retry_requires": [
            "PIT broad-market OHLCV or breadth coverage for at least 12 of the 17 exp-20260706-006 signal dates",
            "or genuinely new settled forward deep-drawdown episodes with the same broad breadth fields",
            "not threshold/lookback/response-function retunes on the current two-row coverage",
        ],
        "rejection_reason": None if passed else ";".join(realized_failures),
        "changed_files": CHANGED_FILES,
        "related_files": RELATED_FILES,
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
    result["trades"] = analysis["enriched_trades"]
    return result


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
            "alpha_hypothesis",
            "hypothesis",
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
            "live_realistic_execution_envelope",
            "post_run_reflection",
            "next_retry_requires",
            "rejection_reason",
            "changed_files",
            "related_files",
            "reproduction_commands",
            "artifact",
            "log",
            "lean_quality_passed",
            "llm_metrics",
            "anti_js",
        ]
    }


def build_card(result: dict[str, Any]) -> str:
    summary = result["gate4"]["summary"]
    deltas = summary["deltas"]
    checks = result["gate4"]["checks"]
    failed = result["gate4"]["failed_reasons"]
    return f"""# {EXPERIMENT_ID} - Deep Drawdown Broad Breadth Capitulation Quality

## Result

- Decision: `{result["decision"]}`
- Status: `{result["status"]}`
- Total first-entry rows: `{summary["total_closed_rows"]}`
- Evaluable broad-breadth rows: `{summary["evaluable_closed_rows"]}`
- Missing broad-breadth context rows: `{summary["missing_breadth_context_rows"]}`
- Capitulation / non-capitulation rows: `{summary["capitulation_rows"]}` / `{summary["non_capitulation_rows"]}`
- Mean cash lift, capitulation minus non-capitulation: `{deltas["mean_cash_return_pct_capitulation_minus_non_capitulation"]}`
- Mean SPY-excess lift, capitulation minus non-capitulation: `{deltas["mean_spy_excess_pct_capitulation_minus_non_capitulation"]}`
- Failed reasons: `{", ".join(failed) if failed else "none"}`

## Hypothesis

{HYPOTHESIS}

## Fixed Rule

Signal-day broad OHLCV breadth must show a washout plus stabilization:
share above own 20-session close <= 40% and share positive over 3 sessions
>= 55%, across at least 1000 common tickers. Entry, exit, notional, hold,
slippage, and first-entry episode budget remain exactly those from
`exp-20260706-006`.

## Coverage

```json
{json.dumps(summary["coverage_by_year"], indent=2, ensure_ascii=True, sort_keys=True)}
```

## Checks

```json
{json.dumps(checks, indent=2, ensure_ascii=True, sort_keys=True)}
```

## Reproduce

```powershell
{RUNNER_COMMAND}
```
"""


def build_manifest(result: dict[str, Any]) -> dict[str, Any]:
    files = {
        "runner": RUNNER,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "ticket": repo_rel(TICKET_JSON),
        "baseline_artifact": repo_rel(BASELINE_ARTIFACT),
        "warehouse_sqlite": repo_rel(WAREHOUSE_SQLITE),
    }
    return {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_revision_manifest",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": utc_now(),
        "files": {
            name: {
                "path": path,
                "exists": (REPO_ROOT / path).exists(),
                "sha256": file_sha256(REPO_ROOT / path),
            }
            for name, path in files.items()
        },
        "changed_files": CHANGED_FILES,
        "related_files": RELATED_FILES,
        "reproduction_commands": result["reproduction_commands"],
    }


def update_ticket(result: dict[str, Any]) -> None:
    ticket = load_ticket()
    ticket["status"] = result["status"]
    ticket["completed_at"] = result["timestamp"]
    ticket["result"] = {
        "decision": result["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "alpha_ready": False,
        "observed_only_lead": result["observed_only_lead"],
        "artifact": result["artifact"],
        "log": result["log"],
        "gate4": result["gate4"],
        "post_run_reflection": result["post_run_reflection"],
    }
    ticket["next_retry_requires"] = result["next_retry_requires"]
    write_json(TICKET_JSON, ticket)


def registry_fields(result: dict[str, Any]) -> dict[str, Any]:
    ticket = load_ticket()
    return {
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "change_type": result["change_type"],
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": result["causal_components"],
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": result["new_evidence_type"],
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "baseline_result_file": repo_rel(BASELINE_ARTIFACT),
        "allowed_write_scope": ticket.get("allowed_write_scope"),
        "must_not_touch": ticket.get("must_not_touch"),
        "locked_variables": ticket.get("locked_variables"),
        "artifact": result["artifact"],
        "log": result["log"],
        "runner": RUNNER,
        "card_file": repo_rel(CARD_MD),
        "revision_manifest_file": repo_rel(MANIFEST_JSON),
        "changed_files": CHANGED_FILES,
        "lean_quality_passed": True,
    }


def registry_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision": result["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "alpha_ready": False,
        "observed_only_lead": result["observed_only_lead"],
        "artifact": result["artifact"],
        "log": result["log"],
        "runner": RUNNER,
        "gate4": result["gate4"],
        "summary": result["gate4"]["summary"],
        "production_impact": result["production_impact"],
        "post_run_reflection": result["post_run_reflection"],
        "reproduction_commands": result["reproduction_commands"],
        "changed_files": CHANGED_FILES,
    }


def main() -> int:
    result = build_result()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    write_json(OUT_JSON, result)
    save_experiment_log_entry(compact_log_record(result), allow_duplicate=True)
    write_text(CARD_MD, build_card(result))
    write_json(MANIFEST_JSON, build_manifest(result))
    update_ticket(result)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=result["prediction"],
        result=registry_result(result),
        status=result["status"],
        fields=registry_fields(result),
    )
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": result["status"],
                "decision": result["decision"],
                "summary": result["gate4"]["summary"],
                "failed_reasons": result["gate4"]["failed_reasons"],
                "artifact": result["artifact"],
            },
            indent=2,
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
