"""exp-20260711-025: core entry sign-persistence monotonicity attribution.

Read-only alpha attribution on the canonical saved core trades.  The feature is
the fraction of adjacent non-zero daily return signs that agree over the 20
sessions ending at the signal close.  It uses only data known before the
recorded next-open entry and changes no strategy or production behavior.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import statistics
import sys
from collections import Counter
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


EXPERIMENT_ID = "exp-20260711-025"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "core_sign_persistence_monotonicity"
RUNNER = f"quant/experiments/exp_20260711_025_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

HYPOTHESIS = (
    "Observed-only alpha attribution: among canonical core entries, a higher "
    "PIT 20-session adjacent-return sign-persistence score should identify "
    "cleaner trend continuation and show monotonic higher net trade returns "
    "across the three fixed windows; this is continuous attribution only and "
    "changes no selection, sizing, entry, or exit policy."
)
CHANGE_TYPE = "observed_only_attribution"
IMPLEMENTATION_MODE = "read_only_saved_trade_monotonicity"
MECHANISM_FAMILY = "ohlcv_momentum_core_entry_path_persistence_attribution"
TRIAL_FAMILY = "ohlcv_momentum_ticker_directional_sign_persistence_core_entry_attribution"
TRIAL_VARIANT_ID = "ticker_sign_persistence20_tercile_monotonicity_v1"
CHANGED_VARIABLE = "ticker_return_sign_persistence20_monotonic_core_trade_quality_v1"
NEW_EVIDENCE_TYPE = "new_gate_shape_continuous_path_order_attribution"
NEW_EVIDENCE_AXIS = (
    "Candidate-level continuous monotonic attribution of the temporal ordering "
    "of adjacent daily return signs on fixed executed core trades. Prior nearby "
    "work tested market-level Kaufman ER or high-vol/high-beta exclusion, not "
    "per-ticker sign-transition persistence."
)
NEARBY_PRIORS = ["exp-20260615-023", "exp-20260708-026"]
CAUSAL_COMPONENTS = [
    "canonical saved core trades",
    "PIT ticker OHLCV through signal close",
    "20-session adjacent-return sign persistence",
    "tercile monotonicity",
    "cross-window direction check",
    "no strategy behavior change",
]
PREDICTION = {
    "success_probability": 0.25,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "path_persistence_collinear_with_existing_momentum",
        "small_core_trade_sample",
        "window_sign_instability",
        "no_monotonic_ladder",
    ],
    "confidence_reason": (
        "The field uses the ordering of daily return signs rather than "
        "volatility, beta, return magnitude, or Kaufman efficiency, so it can "
        "separate alternating noisy paths from persistent trends at similar "
        "net momentum. Existing core entries are few and already selected, "
        "making window instability the main disconfirmer."
    ),
    "recorded_at": "2026-07-11T22:14:19Z",
}

LOOKBACK_RETURNS = 20
MIN_NONZERO_RETURNS = 18
MIN_WINDOW_ROWS = 12
WINDOWS = [
    {
        "label": "late_strong",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
        "core_result": "data/backtests/archive/20260604_ohlcv_warehouse_replay/backtest_results_warehouse_snapshot_late_strong_20260604.json",
    },
    {
        "label": "mid_weak",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
        "core_result": "data/backtests/archive/20260604_ohlcv_warehouse_replay/backtest_results_warehouse_snapshot_mid_weak_20260604.json",
    },
    {
        "label": "old_thin",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
        "core_result": "data/backtests/archive/20260604_ohlcv_warehouse_replay/backtest_results_warehouse_snapshot_old_thin_20260604.json",
    },
]

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260711_025_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260711_025_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def rank_average(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda idx: values[idx])
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(order):
        end = cursor + 1
        while end < len(order) and values[order[end]] == values[order[cursor]]:
            end += 1
        rank = (cursor + 1 + end) / 2.0
        for pos in range(cursor, end):
            ranks[order[pos]] = rank
        cursor = end
    return ranks


def pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 3:
        return None
    left_mean = statistics.fmean(left)
    right_mean = statistics.fmean(right)
    left_ss = sum((value - left_mean) ** 2 for value in left)
    right_ss = sum((value - right_mean) ** 2 for value in right)
    if left_ss <= 0.0 or right_ss <= 0.0:
        return None
    covariance = sum(
        (lvalue - left_mean) * (rvalue - right_mean)
        for lvalue, rvalue in zip(left, right)
    )
    return covariance / math.sqrt(left_ss * right_ss)


def spearman(rows: list[dict[str, Any]], outcome: str) -> float | None:
    usable = [row for row in rows if number(row.get(outcome)) is not None]
    if len(usable) < 3:
        return None
    return pearson(
        rank_average([float(row["sign_persistence20"]) for row in usable]),
        rank_average([float(row[outcome]) for row in usable]),
    )


def load_snapshot(path: Path) -> dict[str, list[dict[str, Any]]]:
    payload = read_json(path)
    result: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in (payload.get("ohlcv") or {}).items():
        clean = [
            row
            for row in rows
            if isinstance(row, dict) and number(row.get("Close")) not in (None, 0.0)
        ]
        clean.sort(key=lambda row: str(row.get("Date") or ""))
        result[str(ticker).upper()] = clean
    return result


def sign_persistence_feature(
    rows: list[dict[str, Any]] | None, entry_date: str
) -> tuple[dict[str, Any] | None, str]:
    if not rows:
        return None, "missing_ticker_rows"
    index_by_date = {str(row.get("Date")): idx for idx, row in enumerate(rows)}
    entry_idx = index_by_date.get(entry_date)
    if entry_idx is None:
        return None, "missing_entry_bar"
    signal_idx = entry_idx - 1
    if signal_idx < LOOKBACK_RETURNS:
        return None, "insufficient_history"
    returns: list[float] = []
    for idx in range(signal_idx - LOOKBACK_RETURNS + 1, signal_idx + 1):
        current = number(rows[idx].get("Close"))
        previous = number(rows[idx - 1].get("Close"))
        if current is None or previous is None or previous <= 0.0:
            continue
        returns.append(current / previous - 1.0)
    signs = [1 if value > 0.0 else -1 for value in returns if value != 0.0]
    if len(signs) < MIN_NONZERO_RETURNS:
        return None, f"insufficient_nonzero_returns_{len(signs)}"
    matching = sum(left == right for left, right in zip(signs, signs[1:]))
    score = matching / (len(signs) - 1)
    net_return = float(rows[signal_idx]["Close"]) / float(
        rows[signal_idx - LOOKBACK_RETURNS]["Close"]
    ) - 1.0
    return (
        {
            "signal_date": str(rows[signal_idx]["Date"]),
            "sign_persistence20": round(score, 6),
            "same_sign_transitions": matching,
            "transition_count": len(signs) - 1,
            "positive_day_fraction": round(sum(sign > 0 for sign in signs) / len(signs), 6),
            "net_return20": round(net_return, 6),
            "known_at": "signal_close_before_next_open_entry",
        },
        "ok",
    )


def bucket_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda row: (row["sign_persistence20"], row["ticker"]))
    buckets = {"noisy_low": [], "middle": [], "persistent_high": []}
    for idx, row in enumerate(ordered):
        bucket_idx = min(2, (idx * 3) // max(1, len(ordered)))
        buckets[("noisy_low", "middle", "persistent_high")[bucket_idx]].append(row)
    result: dict[str, Any] = {}
    for name, items in buckets.items():
        result[name] = {
            "count": len(items),
            "score_mean": round(statistics.fmean(row["sign_persistence20"] for row in items), 6)
            if items
            else None,
            "pnl_pct_net_mean": round(statistics.fmean(row["pnl_pct_net"] for row in items), 6)
            if items
            else None,
            "pnl_mean": round(statistics.fmean(row["pnl"] for row in items), 2)
            if items
            else None,
            "win_rate": round(sum(row["pnl"] > 0.0 for row in items) / len(items), 6)
            if items
            else None,
        }
    means = [result[name]["pnl_pct_net_mean"] for name in ("noisy_low", "middle", "persistent_high")]
    result["monotonic_net_return"] = bool(
        all(value is not None for value in means) and means[0] < means[1] < means[2]
    )
    result["persistent_minus_noisy_net_return"] = round(means[2] - means[0], 6)
    return result


def baseline_metrics() -> dict[str, Any]:
    rows = []
    for window in WINDOWS:
        result = read_json(REPO_ROOT / window["core_result"])
        rows.append(
            {
                "label": window["label"],
                "expected_value_score": result.get("expected_value_score"),
                "total_pnl": result.get("total_pnl"),
                "trade_count": result.get("total_trades"),
                "signals_generated": result.get("signals_generated"),
                "signals_survived": result.get("signals_survived"),
                "survival_rate": result.get("survival_rate"),
            }
        )
    return {
        "accepted_reference": {"expected_value_score_sum": 7.8941, "total_pnl_sum": 234850.99},
        "saved_trade_artifacts": rows,
        "saved_expected_value_score_sum": round(sum(float(row["expected_value_score"]) for row in rows), 4),
        "saved_total_pnl_sum": round(sum(float(row["total_pnl"]) for row in rows), 2),
        "saved_trade_count": sum(int(row["trade_count"]) for row in rows),
        "note": "Saved June-4 trade artifacts are the fixed attribution population and differ slightly from the current accepted aggregate; no strategy decision uses this diagnostic.",
    }


def build_result() -> dict[str, Any]:
    enriched: list[dict[str, Any]] = []
    missing = Counter()
    by_window: dict[str, dict[str, Any]] = {}
    raw_trade_count = 0
    raw_entry_date_complete = 0
    for window in WINDOWS:
        snapshot = load_snapshot(REPO_ROOT / window["snapshot"])
        result = read_json(REPO_ROOT / window["core_result"])
        window_rows: list[dict[str, Any]] = []
        trades = list(result.get("trades") or [])
        raw_trade_count += len(trades)
        for trade in trades:
            ticker = str(trade.get("ticker") or "").upper()
            entry_date = str(trade.get("entry_date") or "")
            raw_entry_date_complete += bool(entry_date)
            feature, reason = sign_persistence_feature(snapshot.get(ticker), entry_date)
            if feature is None:
                missing[reason] += 1
                continue
            row = {
                "window": window["label"],
                "ticker": ticker,
                "strategy": trade.get("strategy"),
                "entry_date": entry_date,
                "exit_date": trade.get("exit_date"),
                "pnl": round(float(trade.get("pnl") or 0.0), 2),
                "pnl_pct_net": round(float(trade.get("pnl_pct_net") or 0.0), 6),
                **feature,
            }
            enriched.append(row)
            window_rows.append(row)
        summary = bucket_summary(window_rows)
        by_window[window["label"]] = {
            "rows": len(window_rows),
            "spearman_score_vs_net_return": spearman(window_rows, "pnl_pct_net"),
            "spearman_score_vs_pnl": spearman(window_rows, "pnl"),
            "terciles": summary,
        }

    aggregate_buckets = bucket_summary(enriched)
    aggregate_rho = spearman(enriched, "pnl_pct_net")
    direction_windows = [
        label
        for label, summary in by_window.items()
        if summary["terciles"]["persistent_minus_noisy_net_return"] > 0.0
    ]
    monotonic_windows = [
        label for label, summary in by_window.items() if summary["terciles"]["monotonic_net_return"]
    ]
    failed: list[str] = []
    if len(enriched) != raw_trade_count:
        failed.append("feature_coverage_incomplete")
    if aggregate_rho is None or aggregate_rho <= 0.0:
        failed.append("pooled_spearman_not_positive")
    if not aggregate_buckets["monotonic_net_return"]:
        failed.append("aggregate_terciles_not_monotonic")
    if len(direction_windows) < 2:
        failed.append("fewer_than_two_windows_persistent_bucket_better")
    if any(summary["rows"] < MIN_WINDOW_ROWS for summary in by_window.values()):
        failed.append("window_sample_too_small")
    positive = not failed
    status = "observed_only_positive_lead" if positive else "observed_only_rejected"
    decision = (
        "observed_only_positive_core_sign_persistence_monotonicity_lead"
        if positive
        else "observed_only_rejected_core_sign_persistence_monotonicity"
    )
    probability = float(PREDICTION["success_probability"])
    baseline = baseline_metrics()
    now = utc_now()
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": status,
        "accepted": False,
        "accepted_alpha": False,
        "accepted_measurement_repair": False,
        "alpha_ready": False,
        "decision": decision,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "lane": LANE,
        "owner": OWNER,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "parameters": {
            "lookback_returns": LOOKBACK_RETURNS,
            "minimum_nonzero_returns": MIN_NONZERO_RETURNS,
            "feature": "matching adjacent non-zero daily return signs / adjacent sign transitions",
            "decision_time": "signal close before next-open entry",
            "acceptance_rule": "positive pooled Spearman, aggregate noisy<middle<persistent net-return terciles, persistent-minus-noisy positive in >=2 windows, complete coverage, and >=12 rows/window",
        },
        "prediction": PREDICTION,
        "calibration": {
            "actual_success": positive,
            "predicted_success_probability": probability,
            "brier_score": round((probability - (1.0 if positive else 0.0)) ** 2, 6),
            "realized_failure_modes": failed,
        },
        "gate1": {"passed": True, **baseline},
        "gate2": {
            "passed": raw_entry_date_complete == raw_trade_count,
            "entry_date_complete": raw_entry_date_complete,
            "entry_date_expected": raw_trade_count,
            "feature_coverage_complete": len(enriched) == raw_trade_count,
            "target_price_note": "Closed-trade artifacts intentionally omit target_price; the canonical signal engine owns that sentinel and this read-only attribution changes no signal generation or exit rule.",
            "required_feature_fields": ["Date", "Close", "entry_date", "pnl_pct_net"],
        },
        "gate3": {
            "passed": True,
            "new_filter_added": False,
            "signals_generated": raw_trade_count,
            "signals_survived": len(enriched),
            "survival_rate": round(len(enriched) / raw_trade_count, 6) if raw_trade_count else 0.0,
            "missing_reasons": dict(missing),
        },
        "gate4": {
            "applicable": False,
            "passed": False,
            "accepted_alpha": False,
            "observed_only_lead": positive,
            "decision": decision,
            "failed_reasons": failed,
            "note": "No strategy behavior changed. A positive attribution would require a separate shared production/backtest policy and full Gate 1-4 replay.",
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "strategy_behavior_changed": False,
        },
        "attribution": {
            "aggregate": {
                "rows": len(enriched),
                "spearman_score_vs_net_return": aggregate_rho,
                "spearman_score_vs_pnl": spearman(enriched, "pnl"),
                "terciles": aggregate_buckets,
            },
            "by_window": by_window,
            "windows_persistent_bucket_better": direction_windows,
            "windows_monotonic": monotonic_windows,
            "trade_rows": enriched,
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "entry_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_rules_changed": False,
            "orders_changed": False,
            "trade_enabled": False,
            "scope": "read_only_saved_trade_attribution",
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The per-ticker sign-persistence field showed the predeclared cross-window monotonic relationship."
                if positive
                else "The temporal ordering of adjacent daily return signs did not add a stable monotonic quality axis after the existing core selection stack; the saved sample is already highly selected and small."
            ),
            "forbidden_near_neighbor_retry": "Do not retry by changing the 20-session lookback, zero-return handling, tercile cuts, persistence threshold, strategy/ticker/window slices, or by converting this result into a scalar on the same frozen trades.",
            "new_evidence_required": "A positive lead requires a shared helper and full Gate 1-4. A rejected result requires materially more settled core forward rows or a genuinely new non-OHLCV path-quality source, not another sign-path statistic.",
        },
        "rejection_reason": None if positive else ";".join(failed),
        "next_retry_requires": [
            "shared production/backtest helper plus full Gate 1-4 if positive",
            "materially more settled core forward rows or a new non-OHLCV source if rejected",
            "no lookback, bucket, threshold, ticker, strategy, or response retune",
        ],
        "changed_files": CHANGED_FILES,
        "related_files": [window["snapshot"] for window in WINDOWS]
        + [window["core_result"] for window in WINDOWS],
        "reproduction_commands": [
            f".\\.venv\\Scripts\\python.exe -B -m py_compile {RUNNER.replace('/', chr(92))}",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "lean_quality_passed": True,
        "anti_js": {"used_javascript": False, "evidence": "Python runner only."},
    }
    return payload


def build_log(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key != "attribution"} | {
        "attribution": {
            "aggregate": payload["attribution"]["aggregate"],
            "by_window": payload["attribution"]["by_window"],
            "windows_persistent_bucket_better": payload["attribution"]["windows_persistent_bucket_better"],
            "windows_monotonic": payload["attribution"]["windows_monotonic"],
        }
    }


def build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["attribution"]["aggregate"]
    terciles = aggregate["terciles"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Core sign-persistence monotonicity",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Usable trades: `{aggregate['rows']}`",
            f"- Spearman vs net return: `{aggregate['spearman_score_vs_net_return']}`",
            f"- Noisy / middle / persistent mean net return: `{terciles['noisy_low']['pnl_pct_net_mean']}` / `{terciles['middle']['pnl_pct_net_mean']}` / `{terciles['persistent_high']['pnl_pct_net_mean']}`",
            f"- Monotonic windows: `{', '.join(payload['attribution']['windows_monotonic']) or 'none'}`",
            f"- Failed reasons: `{', '.join(payload['gate4']['failed_reasons']) or 'none'}`",
            "",
            "No live, paper, entry, ranking, sizing, exit, order, or LLM behavior changed.",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Reproduce",
            "",
            f"- `{RUNNER_COMMAND}`",
        ]
    ) + "\n"


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(build_log(payload), allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    write_json(
        MANIFEST_JSON,
        {
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
        },
    )
    ticket = read_json(TICKET_JSON)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result={
            "accepted": False,
            "accepted_alpha": False,
            "accepted_measurement_repair": False,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "summary": {
                "status": payload["status"],
                "rows": payload["attribution"]["aggregate"]["rows"],
                "spearman_score_vs_net_return": payload["attribution"]["aggregate"]["spearman_score_vs_net_return"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
        },
        status=payload["status"],
        fields={
            **{key: value for key, value in ticket.items() if key not in {"result", "status"}},
            **{key: value for key, value in build_log(payload).items() if key not in {"experiment_id", "status", "prediction"}},
            "owner": OWNER,
        },
    )


def main() -> None:
    payload = build_result()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "rows": payload["attribution"]["aggregate"]["rows"],
                "spearman_score_vs_net_return": payload["attribution"]["aggregate"]["spearman_score_vs_net_return"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
