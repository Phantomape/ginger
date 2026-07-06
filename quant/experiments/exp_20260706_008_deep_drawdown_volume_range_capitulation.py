"""exp-20260706-008: QQQ volume/range capitulation label for deep drawdown rows.

Observed-only attribution. This leaves the exp-20260706-006 first-entry
deep-drawdown rebound policy unchanged and labels each closed historical row
with a fixed point-in-time QQQ volume/range climax test:

  signal-day QQQ volume percentile over the trailing 252 sessions >= 0.90
  and signal-day QQQ daily range percentile over the trailing 252 sessions >= 0.90

The signal fires at the close and enters next open, so same-day volume and range
are available to this diagnostic label. No strategy behavior, live orders,
ranking, sizing, exits, or shared paper helper code changes here.

Reproduce:
  .venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260706_008_deep_drawdown_volume_range_capitulation.py
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from statistics import mean, median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
EXPERIMENTS_ROOT = REPO_ROOT / "quant" / "experiments"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (QUANT_ROOT, EXPERIMENTS_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from data_paths import DATA_ROOT  # noqa: E402
from deep_drawdown_rebound_paper_sleeve import (  # noqa: E402
    BUDGET_CONFIG,
    load_index_history_rows,
    merge_bar_series,
)
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)
from exp_20260706_003_deep_drawdown_rebound import (  # noqa: E402
    _warehouse_rows,
)


EXPERIMENT_ID = "exp-20260706-008"
BASELINE_EXPERIMENT_ID = "exp-20260706-006"
OWNER = "codex-alpha-explore"
LANE = "alpha_search"
SLUG = "deep_drawdown_volume_range_capitulation"
RUNNER = f"quant/experiments/exp_20260706_008_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_ARTIFACT = (
    DATA_ROOT
    / "experiments"
    / BASELINE_EXPERIMENT_ID
    / "exp_20260706_006_deep_drawdown_rebound_budget.json"
)
OUT_DIR = DATA_ROOT / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260706_008_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Observed-only alpha: deep-drawdown first-entry QQQ rebound rows with PIT "
    "index volume/range capitulation quality should have materially higher cash "
    "and SPY replacement value than non-climax first entries, distinguishing "
    "true washouts from bear-trap rebounds."
)
CHANGED_VARIABLE = "pit_index_volume_range_capitulation_gate_for_deep_drawdown_first_entries"
MECHANISM_FAMILY = "deep_drawdown_rebound_capitulation_quality"
TRIAL_FAMILY = "deep_drawdown_rebound_episode_quality"
TRIAL_VARIANT_ID = "qqq_trailing_volume_range_climax_v1"
NEARBY_PRIORS = [
    "exp-20260706-003",
    "exp-20260706-004",
    "exp-20260706-005",
    "exp-20260706-006",
]
NEW_EVIDENCE_AXIS = (
    "New gate shape/data axis versus exp-20260706-003/006: trailing "
    "point-in-time QQQ volume and daily-range percentile climax fields from "
    "the index OHLCV archive/warehouse, with entry/exit/budget left unchanged."
)

CAPITULATION_RULE = {
    "ticker": "QQQ",
    "lookback_sessions": 252,
    "volume_percentile_min": 0.90,
    "range_percentile_min": 0.90,
    "range_metric": "(high - low) / close",
    "same_day_available": (
        "Signal is generated after the close and enters next open, so same-day "
        "volume and range are point-in-time available."
    ),
}
ACCEPTANCE_RULE = {
    "required_evaluable_rows": 17,
    "min_climax_rows": 5,
    "min_non_climax_rows": 5,
    "min_mean_cash_return_lift": 0.03,
    "min_mean_spy_excess_lift": 0.03,
    "min_climax_win_rate": 0.60,
    "max_single_positive_climax_cash_pnl_share": 0.50,
}
CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260706_008_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]
RELATED_FILES = [
    str(BASELINE_ARTIFACT.relative_to(REPO_ROOT)).replace("\\", "/"),
    "data/non_ohlcv/index_history/index_daily_pre2023.jsonl",
    "quant/deep_drawdown_rebound_paper_sleeve.py",
    "quant/experiments/exp_20260706_003_deep_drawdown_rebound.py",
    "quant/experiments/exp_20260706_006_deep_drawdown_rebound_budget.py",
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
    # This runner writes single-owner experiment artifacts. If Windows keeps the
    # temp rename locked, prefer a complete truncating write to dropping the run.
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
    write_text(path, json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n")


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


def percentile_rank(values: list[float], current: float | None) -> float | None:
    if current is None or not values:
        return None
    return sum(1 for value in values if value <= current) / len(values)


def qqq_bar_series() -> tuple[list[dict[str, Any]], str]:
    ticker = str(BUDGET_CONFIG["ticker"]).upper()
    archive_rows = load_index_history_rows(ticker)
    warehouse_rows, warehouse_path = _warehouse_rows(ticker)
    return merge_bar_series(archive_rows, warehouse_rows), warehouse_path


def build_capitulation_context(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookback = int(CAPITULATION_RULE["lookback_sessions"])
    by_date: dict[str, dict[str, Any]] = {}
    volumes: list[float | None] = []
    ranges: list[float | None] = []

    for idx, row in enumerate(rows):
        date = str(row.get("date") or "")[:10]
        close = _float(row.get("close"))
        high = _float(row.get("high"))
        low = _float(row.get("low"))
        volume = _float(row.get("volume"))
        range_pct = None
        close_location = None
        if close and high is not None and low is not None and high >= low:
            range_pct = (high - low) / close
            if high > low:
                close_location = (close - low) / (high - low)

        volumes.append(volume)
        ranges.append(range_pct)
        start = max(0, idx - lookback + 1)
        trailing_volumes = [v for v in volumes[start : idx + 1] if v is not None]
        trailing_ranges = [v for v in ranges[start : idx + 1] if v is not None]
        volume_pct = percentile_rank(trailing_volumes, volume)
        range_pctile = percentile_rank(trailing_ranges, range_pct)
        is_climax = bool(
            volume_pct is not None
            and range_pctile is not None
            and volume_pct >= float(CAPITULATION_RULE["volume_percentile_min"])
            and range_pctile >= float(CAPITULATION_RULE["range_percentile_min"])
        )
        by_date[date] = {
            "date": date,
            "volume": _round(volume, 2),
            "range_pct": _round(range_pct, 6),
            "close_location": _round(close_location, 4),
            "trailing_history_sessions": len(trailing_ranges),
            "volume_percentile": _round(volume_pct, 4),
            "range_percentile": _round(range_pctile, 4),
            "volume_range_capitulation_climax": is_climax,
        }
    return by_date


def enrich_trades(trades: list[dict[str, Any]], context: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for trade in trades:
        row = dict(trade)
        signal_date = str(row.get("signal_date") or "")[:10]
        cap = context.get(signal_date)
        row["capitulation_context"] = cap
        row["volume_range_capitulation_climax"] = bool(
            cap and cap.get("volume_range_capitulation_climax")
        )
        row["capitulation_context_available"] = cap is not None
        enriched.append(row)
    return enriched


def cohort_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    returns = [
        _float(row.get("pnl_pct_net"))
        for row in rows
        if _float(row.get("pnl_pct_net")) is not None
    ]
    spy_excess = [
        _float(row.get("excess_vs_spy_pct"))
        for row in rows
        if _float(row.get("excess_vs_spy_pct")) is not None
    ]
    pnl_values = [_float(row.get("pnl")) for row in rows if _float(row.get("pnl")) is not None]
    positives = [value for value in pnl_values if value is not None and value > 0]
    positive_total = sum(positives)
    max_positive_share = None
    if positive_total > 0:
        max_positive_share = max(positives) / positive_total
    return {
        "rows": len(rows),
        "win_count": sum(1 for value in returns if value is not None and value > 0),
        "win_rate": _round(
            sum(1 for value in returns if value is not None and value > 0) / len(returns)
            if returns
            else None,
            4,
        ),
        "mean_cash_return_pct": _round(mean(returns), 6) if returns else None,
        "median_cash_return_pct": _round(median(returns), 6) if returns else None,
        "mean_spy_excess_pct": _round(mean(spy_excess), 6) if spy_excess else None,
        "median_spy_excess_pct": _round(median(spy_excess), 6) if spy_excess else None,
        "total_pnl": _round(sum(pnl_values), 2) if pnl_values else None,
        "positive_pnl_total": _round(positive_total, 2),
        "max_single_positive_cash_pnl_share": _round(max_positive_share, 4),
        "episodes": sorted(
            {
                str(row.get("episode_start_date"))
                for row in rows
                if row.get("episode_start_date")
            }
        ),
    }


def build_analysis(enriched: list[dict[str, Any]]) -> dict[str, Any]:
    closed = [
        row
        for row in enriched
        if row.get("paper_status") == "closed"
        and row.get("capitulation_context_available")
        and _float(row.get("pnl_pct_net")) is not None
        and _float(row.get("excess_vs_spy_pct")) is not None
    ]
    climax = [row for row in closed if row.get("volume_range_capitulation_climax")]
    non_climax = [row for row in closed if not row.get("volume_range_capitulation_climax")]
    cohorts = {
        "all_evaluable": cohort_summary(closed),
        "climax": cohort_summary(climax),
        "non_climax": cohort_summary(non_climax),
    }

    climax_mean_cash = cohorts["climax"]["mean_cash_return_pct"]
    non_mean_cash = cohorts["non_climax"]["mean_cash_return_pct"]
    climax_mean_spy = cohorts["climax"]["mean_spy_excess_pct"]
    non_mean_spy = cohorts["non_climax"]["mean_spy_excess_pct"]
    cash_lift = (
        round(climax_mean_cash - non_mean_cash, 6)
        if climax_mean_cash is not None and non_mean_cash is not None
        else None
    )
    spy_lift = (
        round(climax_mean_spy - non_mean_spy, 6)
        if climax_mean_spy is not None and non_mean_spy is not None
        else None
    )
    concentration = cohorts["climax"]["max_single_positive_cash_pnl_share"]

    checks = {
        "required_evaluable_rows": len(closed) == ACCEPTANCE_RULE["required_evaluable_rows"],
        "min_climax_rows": len(climax) >= ACCEPTANCE_RULE["min_climax_rows"],
        "min_non_climax_rows": len(non_climax) >= ACCEPTANCE_RULE["min_non_climax_rows"],
        "mean_cash_return_lift": (
            cash_lift is not None
            and cash_lift >= ACCEPTANCE_RULE["min_mean_cash_return_lift"]
        ),
        "mean_spy_excess_lift": (
            spy_lift is not None
            and spy_lift >= ACCEPTANCE_RULE["min_mean_spy_excess_lift"]
        ),
        "climax_win_rate": (
            cohorts["climax"]["win_rate"] is not None
            and cohorts["climax"]["win_rate"] >= ACCEPTANCE_RULE["min_climax_win_rate"]
        ),
        "positive_pnl_concentration": (
            concentration is not None
            and concentration
            <= ACCEPTANCE_RULE["max_single_positive_climax_cash_pnl_share"]
        ),
    }
    failure_mode_map = {
        "required_evaluable_rows": "evaluable_row_count_changed",
        "min_climax_rows": "too_few_climax_rows",
        "min_non_climax_rows": "too_few_non_climax_rows",
        "mean_cash_return_lift": "posthoc_capitulation_proxy_not_discriminative",
        "mean_spy_excess_lift": "no_spy_excess_lift",
        "climax_win_rate": "posthoc_capitulation_proxy_not_discriminative",
        "positive_pnl_concentration": "sample_dominated_by_one_crisis",
    }
    failed_reasons = list(dict.fromkeys(
        failure_mode_map[name] for name, passed in checks.items() if not passed
    ))
    return {
        "evaluable_closed_rows": len(closed),
        "climax_rows": len(climax),
        "non_climax_rows": len(non_climax),
        "cohorts": cohorts,
        "deltas": {
            "mean_cash_return_pct_climax_minus_non_climax": cash_lift,
            "mean_spy_excess_pct_climax_minus_non_climax": spy_lift,
        },
        "checks": checks,
        "failed_reasons": failed_reasons,
        "sample_rows": [
            {
                "signal_date": row.get("signal_date"),
                "entry_date": row.get("entry_date"),
                "exit_date": row.get("exit_date"),
                "episode_start_date": row.get("episode_start_date"),
                "pnl_pct_net": row.get("pnl_pct_net"),
                "excess_vs_spy_pct": row.get("excess_vs_spy_pct"),
                "pnl": row.get("pnl"),
                "volume_range_capitulation_climax": row.get(
                    "volume_range_capitulation_climax"
                ),
                "capitulation_context": row.get("capitulation_context"),
            }
            for row in closed
        ],
    }


def baseline_metrics(baseline: dict[str, Any]) -> dict[str, Any]:
    summary = baseline.get("summary") or {}
    spy = baseline.get("spy_replacement") or {}
    return {
        "baseline_experiment_id": BASELINE_EXPERIMENT_ID,
        "baseline_result_file": repo_rel(BASELINE_ARTIFACT),
        "trade_count": summary.get("closed_trades"),
        "total_pnl": summary.get("total_pnl"),
        "win_rate": summary.get("win_rate"),
        "mean_return_pct": summary.get("mean_return_pct"),
        "mean_excess_vs_spy_pct": spy.get("mean_excess_vs_spy_pct"),
        "strategy_behavior_changed": False,
    }


def build_result() -> dict[str, Any]:
    timestamp = utc_now()
    prediction = load_prediction()
    baseline = load_json(BASELINE_ARTIFACT)
    qqq_rows, warehouse_path = qqq_bar_series()
    context = build_capitulation_context(qqq_rows)
    enriched = enrich_trades(list(baseline.get("trades") or []), context)
    analysis = build_analysis(enriched)
    passed = not analysis["failed_reasons"]
    status = "observed_only" if passed else "observed_only_rejected"
    decision = (
        "observed_only_positive_deep_drawdown_capitulation_quality_lead"
        if passed
        else "observed_only_rejected_volume_range_capitulation_no_stable_edge"
    )
    before_after = baseline_metrics(baseline)
    predicted_failures = prediction.get("main_failure_modes") or []
    realized_failures = list(dict.fromkeys(analysis["failed_reasons"]))
    predicted_hit = any(failure in predicted_failures for failure in realized_failures)

    result = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "owner": OWNER,
        "lane": LANE,
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "alpha_ready": False,
        "observed_only_lead": passed,
        "alpha_hypothesis": HYPOTHESIS,
        "hypothesis": HYPOTHESIS,
        "change_type": "observed_only_attribution",
        "implementation_mode": "read_only_observed_only_attribution",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": [
            "fixed exp-20260706-006 first-entry rows",
            "PIT QQQ trailing volume percentile label",
            "PIT QQQ trailing daily-range percentile label",
            "climax vs non-climax cash/SPY attribution",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "new_pit_index_volume_range_capitulation_fields",
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "calibration": {
            "actual_success": 1 if passed else 0,
            "predicted_success_probability": prediction.get("success_probability"),
            "brier_score": (
                round((float(prediction.get("success_probability", 0.0)) - (1 if passed else 0)) ** 2, 4)
                if prediction.get("success_probability") is not None
                else None
            ),
            "expected_ev_delta": prediction.get("expected_ev_delta"),
            "expected_pnl_delta": prediction.get("expected_pnl_delta"),
            "actual_ev_delta": 0.0,
            "actual_pnl_delta": 0.0,
            "predicted_failure_modes": predicted_failures,
            "realized_failure_modes": realized_failures,
            "predicted_failure_mode_hit": predicted_hit,
            "surprise_note": (
                "Low surprise: the ticket predicted weak power and either too few "
                "climax rows or no SPY-excess lift would be the likely failure."
            ),
        },
        "parameters": {
            "baseline_artifact": repo_rel(BASELINE_ARTIFACT),
            "capitulation_rule": CAPITULATION_RULE,
            "acceptance_rule": ACCEPTANCE_RULE,
            "qqq_merged_rows": len(qqq_rows),
            "qqq_warehouse_path": warehouse_path,
            "early_history_note": (
                "The trailing 252-session window uses all prior in-repo sessions "
                "when fewer than 252 are available, matching the PIT convention "
                "used by the deep-drawdown archive."
            ),
        },
        "before_metrics": before_after,
        "after_metrics": before_after,
        "delta_metrics": {
            "expected_value_score_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "strategy_behavior_changed": False,
            **analysis["deltas"],
        },
        "gate1": {
            "passed": BASELINE_ARTIFACT.exists(),
            "baseline_metrics": before_after,
            "note": "Observed-only attribution on exp-20260706-006 artifact; canonical strategy baseline unchanged.",
        },
        "gate2": {
            "passed": all(row.get("capitulation_context_available") for row in enriched),
            "fields_checked": [
                "signal_date",
                "entry_date",
                "exit_date",
                "pnl_pct_net",
                "excess_vs_spy_pct",
                "QQQ signal-day volume",
                "QQQ signal-day high/low/close",
            ],
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
            "decision": decision,
            "acceptance_rule": ACCEPTANCE_RULE,
            "capitulation_rule": CAPITULATION_RULE,
            "checks": analysis["checks"],
            "failed_reasons": analysis["failed_reasons"],
            "summary": {
                "evaluable_closed_rows": analysis["evaluable_closed_rows"],
                "climax_rows": analysis["climax_rows"],
                "non_climax_rows": analysis["non_climax_rows"],
                "deltas": analysis["deltas"],
                "cohorts": analysis["cohorts"],
            },
        },
        "analysis": analysis,
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
                "The fixed volume/range climax label did not meet all pre-run "
                "cohort and replacement-value requirements."
                if not passed
                else "The fixed volume/range climax label separated a positive observed-only cohort, but it remains non-deployable without fresh shared-policy testing."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune volume/range percentile thresholds, use only one "
                "of the two fields, add VIX/SPY confirmations, change hold days, "
                "or reslice the same 17 first-entry rows by crisis/decade/depth."
            ),
            "new_evidence_required": (
                "Reopen only with genuinely new settled forward deep-drawdown "
                "episodes, a predeclared cross-sectional breadth/capitulation "
                "source, or a different ex-ante gate shape fixed before replay."
            ),
            "realized_failure_mode": ",".join(realized_failures) or None,
        },
        "changed_files": CHANGED_FILES,
        "related_files": RELATED_FILES,
        "reproduction_commands": [RUNNER_COMMAND],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "lean_quality_passed": True,
        "llm_metrics": {"used_llm": False},
        "anti_js": {
            "strategy_behavior_changed": False,
            "not_a_threshold_retune": True,
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
        },
    }
    result["trades"] = enriched
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
    return f"""# {EXPERIMENT_ID} - Deep Drawdown Volume/Range Capitulation

## Result

- Decision: `{result["decision"]}`
- Status: `{result["status"]}`
- Evaluable first-entry rows: `{summary["evaluable_closed_rows"]}`
- Climax / non-climax rows: `{summary["climax_rows"]}` / `{summary["non_climax_rows"]}`
- Mean cash lift, climax minus non-climax: `{deltas["mean_cash_return_pct_climax_minus_non_climax"]}`
- Mean SPY-excess lift, climax minus non-climax: `{deltas["mean_spy_excess_pct_climax_minus_non_climax"]}`
- Failed reasons: `{", ".join(failed) if failed else "none"}`

## Hypothesis

{HYPOTHESIS}

## Fixed Rule

Signal-day QQQ trailing volume percentile >= 0.90 and trailing daily-range
percentile >= 0.90 over the in-repo trailing 252-session window. Entry, exit,
notional, hold, slippage, and first-entry episode budget remain exactly those
from `exp-20260706-006`.

## Checks

```json
{json.dumps(checks, indent=2, ensure_ascii=False, sort_keys=True)}
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
            compact_log_record(result),
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
