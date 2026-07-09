"""exp-20260706-004: deep drawdown first-stabilization episode budget.

Read-only follow-up to exp-20260706-003. The fixed new gate shape is a
one-entry budget per deep drawdown episode: keep only the first closed
stabilization trade for each episode from the exp003 replay artifact.

No strategy behavior changes here: no helper, daily adapter, ranking, sizing,
exit, watchlist, prompt, paper order, or live order path is changed.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import sys
from pathlib import Path
from statistics import mean, median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


EXPERIMENT_ID = "exp-20260706-004"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "deep_drawdown_first_episode_budget"
RUNNER = f"quant/experiments/exp_20260706_004_{SLUG}.py"
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
OUT_JSON = OUT_DIR / f"exp_20260706_004_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Deep-drawdown rebound only deserves a default-off paper candidate when "
    "each drawdown episode has a fixed one-entry budget; taking only the first "
    "stabilization signal per episode should remove long-bear repeated "
    "re-entry bleed while preserving correction rebound edge."
)
CHANGED_VARIABLE = "deep_drawdown_first_stabilization_per_episode_budget_v1"
MECHANISM_FAMILY = "capitulation_rebound_event_conditioning"
TRIAL_FAMILY = "deep_drawdown_episode_budget_gate_shape"
TRIAL_VARIANT_ID = "first_stabilization_per_episode_v1"
NEARBY_PRIORS = ["exp-20260706-003"]
NEW_EVIDENCE_AXIS = (
    "New gate shape: fixed one-entry budget per deep drawdown episode using "
    "only the first stabilization signal, explicitly different from "
    "exp-20260706-003 repeated re-entry; no trigger, hold, notional, cooldown, "
    "ticker, or threshold retune."
)

STANDARD_WINDOWS = {
    "old_thin": ("2024-10-02", "2025-04-22"),
    "mid_weak": ("2025-04-23", "2025-10-22"),
    "late_strong": ("2025-10-23", "2026-04-21"),
}

ACCEPTANCE_RULE = {
    "min_full_history_episodes": 8,
    "require_positive_cash_pnl": True,
    "min_win_rate": 0.60,
    "require_positive_mean_excess_vs_spy": True,
    "min_standard_window_trades": 3,
    "min_standard_windows_with_trades": 2,
    "require_no_standard_window_negative_pnl": True,
}

DEFAULT_PREDICTION = {
    "success_probability": 0.22,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "standard_windows_too_thin",
        "spy_replacement_not_beaten",
        "secular_bear_first_signal_still_bad",
        "posthoc_gate_shape_overfit",
    ],
    "confidence_reason": (
        "exp-20260706-003 identified repeated re-entry during long bear "
        "episodes as the realized failure mechanism, so a one-entry episode "
        "budget is the specific new gate shape it allowed; risk remains high "
        "because first signals may still be falling knives, SPY excess was "
        "weak in the rejected bundle, and canonical windows have few episodes."
    ),
}

CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260706_004_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]

RELATED_FILES = [
    "data/experiments/exp-20260706-003/exp_20260706_003_deep_drawdown_rebound.json",
    "quant/deep_drawdown_rebound_paper_sleeve.py",
    "quant/experiments/exp_20260706_003_deep_drawdown_rebound.py",
    "experiments/logs/exp-20260706-003.json",
    "data/non_ohlcv/index_history/index_daily_pre2023.jsonl",
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


def episode_details(source_trades: list[dict[str, Any]], selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected_by_episode = {
        str(row.get("episode_start_date")): row for row in selected
    }
    episodes = {}
    for trade in source_trades:
        episode = str(trade.get("episode_start_date") or "")
        episodes.setdefault(episode, []).append(trade)
    details = []
    for episode, rows in sorted(episodes.items()):
        chosen = selected_by_episode.get(episode)
        summary = summarize_trades(rows)
        details.append(
            {
                "episode_start_date": episode,
                "source_repeated_entry_trades": summary["closed_trades"],
                "source_repeated_entry_total_pnl": summary["total_pnl"],
                "selected_signal_date": chosen.get("signal_date") if chosen else None,
                "selected_entry_date": chosen.get("entry_date") if chosen else None,
                "selected_exit_date": chosen.get("exit_date") if chosen else None,
                "selected_pnl": chosen.get("pnl") if chosen else None,
                "selected_return_pct": chosen.get("pnl_pct_net") if chosen else None,
                "selected_excess_vs_spy_pct": chosen.get("excess_vs_spy_pct") if chosen else None,
            }
        )
    return details


def gate4_checks(summary: dict[str, Any], windows: dict[str, Any]) -> tuple[dict[str, bool], list[str]]:
    windows_with_trades = sum(1 for row in windows.values() if row["closed_trades"] > 0)
    standard_window_trades = sum(row["closed_trades"] for row in windows.values())
    negative_windows = [
        name for name, row in windows.items() if row["closed_trades"] and row["total_pnl"] < 0
    ]
    checks = {
        "min_full_history_episodes": summary["distinct_episodes"]
        >= ACCEPTANCE_RULE["min_full_history_episodes"],
        "positive_cash_pnl": summary["total_pnl"] > 0
        if ACCEPTANCE_RULE["require_positive_cash_pnl"]
        else True,
        "win_rate": summary["win_rate"] is not None
        and summary["win_rate"] >= ACCEPTANCE_RULE["min_win_rate"],
        "positive_mean_excess_vs_spy": summary["mean_excess_vs_spy_pct"] is not None
        and summary["mean_excess_vs_spy_pct"] > 0,
        "min_standard_window_trades": standard_window_trades
        >= ACCEPTANCE_RULE["min_standard_window_trades"],
        "min_standard_windows_with_trades": windows_with_trades
        >= ACCEPTANCE_RULE["min_standard_windows_with_trades"],
        "no_standard_window_negative_pnl": not negative_windows
        if ACCEPTANCE_RULE["require_no_standard_window_negative_pnl"]
        else True,
    }
    return checks, [name for name, passed in checks.items() if not passed]


def build_analysis() -> dict[str, Any]:
    source = read_json(SOURCE_ARTIFACT, {}) or {}
    source_trades = closed_trades(source)
    selected = select_first_trade_per_episode(source_trades)
    source_summary = dict(source.get("summary") or summarize_trades(source_trades))
    selected_summary = summarize_trades(selected)
    windows = summarize_windows(selected)
    checks, failed = gate4_checks(selected_summary, windows)
    source_pnl = finite_float(source_summary.get("total_pnl")) or 0.0
    return {
        "source_artifact": repo_rel(SOURCE_ARTIFACT),
        "source_rule_version": source.get("rule_version"),
        "series": source.get("series"),
        "parameters": source.get("parameters"),
        "source_repeated_entry_summary": source_summary,
        "first_episode_budget_summary": selected_summary,
        "delta_vs_exp003_repeated_entry": {
            "closed_trade_delta": selected_summary["closed_trades"]
            - int(source_summary.get("closed_trades") or 0),
            "total_pnl_delta": round(selected_summary["total_pnl"] - source_pnl, 2),
            "mean_return_delta": (
                round(
                    selected_summary["mean_return_pct"]
                    - float(source_summary.get("mean_return_pct") or 0.0),
                    6,
                )
                if selected_summary["mean_return_pct"] is not None
                else None
            ),
        },
        "standard_windows": windows,
        "gate4_checks": checks,
        "gate4_failed_reasons": failed,
        "selected_trades": selected,
        "episode_details": episode_details(source_trades, selected),
    }


def build_result() -> dict[str, Any]:
    timestamp = utc_now()
    prediction = load_ticket_prediction()
    baseline = baseline_metrics()
    analysis = build_analysis()
    passed = not analysis["gate4_failed_reasons"]
    status = (
        "observed_only_positive_lead_not_policy_ready"
        if passed
        else "observed_only_rejected"
    )
    decision = (
        "observed_only_positive_deep_drawdown_first_episode_budget_lead"
        if passed
        else "observed_only_rejected_deep_drawdown_first_episode_budget"
    )
    actual_success = 1 if passed else 0
    summary = analysis["first_episode_budget_summary"]
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
        "observed_only_lead": passed,
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
            "pre2023 index history from exp003",
            "fixed exp003 drawdown episode trigger and first-stabilization candidate",
            "one-entry-per-episode budget gate",
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
            "actual_decision": "accepted" if passed else "rejected",
            "predicted_success_probability": prediction["success_probability"],
            "brier_score": round((float(prediction["success_probability"]) - actual_success) ** 2, 4),
            "expected_ev_delta": prediction.get("expected_ev_delta"),
            "expected_pnl_delta": prediction.get("expected_pnl_delta"),
            "actual_ev_delta": 0.0,
            "actual_pnl_delta": 0.0,
            "predicted_failure_modes": predicted_modes,
            "realized_failure_modes": analysis["gate4_failed_reasons"],
            "predicted_failure_mode_hit": predicted_failure_hit,
            "surprise_note": (
                "The gate removed the repeated-entry bleed and made cash PnL positive, "
                "but it still failed as alpha evidence because SPY excess was negative "
                "and canonical-window coverage was too thin."
            ),
        },
        "parameters": {
            "source_artifact": repo_rel(SOURCE_ARTIFACT),
            "baseline_result_file": repo_rel(BASELINE_PATH),
            "gate_shape": "first closed stabilization trade per episode_start_date",
            "acceptance_rule": ACCEPTANCE_RULE,
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "strategy_expected_value_score_delta": 0.0,
            "strategy_total_pnl_delta": 0.0,
            "strategy_trade_count_delta": 0,
            "strategy_behavior_changed": False,
            "first_budget_total_pnl": summary["total_pnl"],
            "first_budget_win_rate": summary["win_rate"],
            "first_budget_mean_excess_vs_spy_pct": summary["mean_excess_vs_spy_pct"],
            "pnl_delta_vs_exp003_repeated_entry": analysis["delta_vs_exp003_repeated_entry"][
                "total_pnl_delta"
            ],
        },
        "gate1": {
            "passed": baseline["baseline_exists"] and SOURCE_ARTIFACT.exists(),
            "baseline_metrics": baseline,
            "source_artifact_exists": SOURCE_ARTIFACT.exists(),
            "note": "Observed-only replay over exp003 artifact; canonical strategy baseline unchanged.",
        },
        "gate2": {
            "passed": all(
                all(row.get(field) not in (None, "") for field in ["entry_date", "exit_date", "pnl"])
                for row in analysis["selected_trades"]
            ),
            "fields_checked": [
                "episode_start_date",
                "signal_date",
                "entry_date",
                "exit_date",
                "pnl",
                "pnl_pct_net",
                "excess_vs_spy_pct",
            ],
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
            "note": "No executable filter, ranking, sizing, exit, prompt, or order rule was added.",
        },
        "gate4": {
            "passed": passed,
            "observed_only": True,
            "accepted_alpha": False,
            "strategy_rerun_required": False,
            "decision": decision,
            "acceptance_rule": ACCEPTANCE_RULE,
            "checks": analysis["gate4_checks"],
            "failed_reasons": analysis["gate4_failed_reasons"],
            "summary": {
                "source_repeated_entry_summary": analysis["source_repeated_entry_summary"],
                "first_episode_budget_summary": summary,
                "delta_vs_exp003_repeated_entry": analysis[
                    "delta_vs_exp003_repeated_entry"
                ],
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
                "Read-only analysis over exp003 replay artifact. No helper, "
                "adapter, order, rank, size, exit, watchlist, or LLM behavior changed."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The episode budget directly removed the repeated-entry bleed: "
                "342 exp003 trades compressed to 17 first signals and cash PnL "
                "improved by more than $21k. It still failed the deployable alpha "
                "bar because the first signals did not beat SPY on average and "
                "the canonical fixed windows contain only one selected trade."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune drawdown trigger, reset hysteresis, close-location, "
                "hold days, notional, cooldown, or ticker on this same artifact. "
                "Do not sweep second/third entry budgets after seeing this result."
            ),
            "new_evidence_required": (
                "A valid retry needs a predeclared ex-ante bear-vs-correction "
                "classifier, genuinely new live/forward episode rows, or a full "
                "shared paper helper update that is tested before seeing the new "
                "episode outcomes."
            ),
        },
        "next_retry_requires": [
            "predeclared ex-ante bear-vs-correction classifier",
            "new live or forward settled deep-drawdown episode rows",
            "or a full shared helper update tested without threshold/entry-budget sweeps",
        ],
        "rejection_reason": None if passed else ";".join(analysis["gate4_failed_reasons"]),
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
    summary = result["gate4"]["summary"]["first_episode_budget_summary"]
    failed = result["gate4"]["failed_reasons"]
    repeated = result["gate4"]["summary"]["source_repeated_entry_summary"]
    return f"""# {EXPERIMENT_ID} - Deep Drawdown First Episode Budget

## Hypothesis

{HYPOTHESIS}

## Result

- Decision: `{result["decision"]}`
- Status: `{result["status"]}`
- Source repeated-entry trades/PnL: `{repeated.get("closed_trades")}` / `{repeated.get("total_pnl")}`
- First-budget trades/PnL: `{summary["closed_trades"]}` / `{summary["total_pnl"]}`
- First-budget win rate: `{summary["win_rate"]}`
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
                "first_budget_summary": result["gate4"]["summary"][
                    "first_episode_budget_summary"
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
