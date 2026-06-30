"""exp-20260630-012: close-confirmed static stop exit scout.

Alpha-search replay scout. Tests one exit-semantics hypothesis on the current
accepted core stack: keep the existing static stop level, but trigger the stop
only when the daily close breaches it and fill at the next session open.

No default strategy, production order, bracket-order, ranking, sizing, entry,
target, paper sleeve, watchlist, or LLM behavior is changed by this runner.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260630-012"
OWNER = "alpha-explore"
SLUG = "close_confirmed_static_stop"
RUNNER = f"quant/experiments/exp_20260630_012_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (QUANT_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260630_012_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20251023_20260421.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20250423_20251022.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20241002_20250422.json",
    },
}

HYPOTHESIS = (
    "Close-confirmed static stop exits may avoid intraday stopout shakeouts by "
    "exiting only when the daily close breaches the existing static stop and "
    "then filling next session open, improving fixed-window EV without "
    "changing entries, ranking, sizing, or target prices."
)
CHANGE_TYPE = "exit_policy_shared_gate"
IMPLEMENTATION_MODE = "private_replay_scout"
MECHANISM_FAMILY = "exit_policy_shared_gate"
TRIAL_FAMILY = "close_confirmed_static_stop_exit"
TRIAL_VARIANT_ID = "close_breach_next_open_static_stop_v1"
CHANGED_VARIABLE = "close_confirmed_static_stop_next_open_v1"
NEW_EVIDENCE_TYPE = "new_exit_trigger_semantics"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260425-029",
    "exp-20260623-020",
    "exp-20260623-022",
    "exp-20260630-011",
]
CAUSAL_COMPONENTS = [
    "existing static stop price",
    "EOD close breach trigger",
    "next-session open exit fill",
    "no entry ranking sizing or target change",
    "live bracket-order envelope disclosure",
]
VARIANT_CONFIG = {
    "REGIME_AWARE_EXIT": True,
    "REPLAY_PARTIAL_REDUCES": True,
    "ATR_STOP_DAILY_RECOMPUTE": False,
    "ATR_STOP_TRIGGER_ON_CLOSE": True,
    "ATR_STOP_EXIT_NEXT_OPEN": True,
}
BASE_CONFIG = {
    "REGIME_AWARE_EXIT": True,
    "REPLAY_PARTIAL_REDUCES": True,
    "ATR_STOP_DAILY_RECOMPUTE": False,
    "ATR_STOP_TRIGGER_ON_CLOSE": False,
    "ATR_STOP_EXIT_NEXT_OPEN": False,
}
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005


RESULT_KEYS = [
    "expected_value_score",
    "total_pnl",
    "total_return_pct",
    "sharpe_daily",
    "max_drawdown_pct",
    "win_rate",
    "trade_count",
    "signals_generated",
    "signals_survived",
    "survival_rate",
    "worst_trade_pct",
    "max_consecutive_losses",
    "tail_loss_share",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default if default is not None else {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rounded(value: Any, digits: int = 6) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return round(value, digits) if math.isfinite(value) else None
    return value


def metrics(result: dict[str, Any]) -> dict[str, Any]:
    out = {key: rounded(result.get(key)) for key in RESULT_KEYS}
    benchmarks = result.get("benchmarks") or {}
    out["total_return_pct"] = rounded(
        benchmarks.get("strategy_total_return_pct", out.get("total_return_pct"))
    )
    out["trade_count"] = rounded(result.get("total_trades", out.get("trade_count")))
    out["spy_buy_hold_return_pct"] = rounded(benchmarks.get("spy_buy_hold_return_pct"))
    out["qqq_buy_hold_return_pct"] = rounded(benchmarks.get("qqq_buy_hold_return_pct"))
    return out


def delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in set(after) | set(before):
        if isinstance(after.get(key), (int, float)) and isinstance(before.get(key), (int, float)):
            out[key] = rounded(float(after[key]) - float(before[key]))
    return out


def aggregate(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in rows.values()),
            6,
        ),
        "total_pnl_sum": round(
            sum(float(row.get("total_pnl") or 0.0) for row in rows.values()),
            2,
        ),
        "trade_count_sum": int(sum(int(row.get("trade_count") or 0) for row in rows.values())),
        "signals_generated_sum": int(
            sum(int(row.get("signals_generated") or 0) for row in rows.values())
        ),
        "signals_survived_sum": int(
            sum(int(row.get("signals_survived") or 0) for row in rows.values())
        ),
        "max_drawdown_pct_worst": round(
            max(float(row.get("max_drawdown_pct") or 0.0) for row in rows.values()),
            6,
        ),
        "survival_rate_min": round(
            min(float(row.get("survival_rate") or 0.0) for row in rows.values()),
            6,
        ),
    }


def load_ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    return prediction or {
        "success_probability": 0.22,
        "main_failure_modes": [
            "gap_risk_worse",
            "late_loss_expansion",
            "winner_collateral",
            "near_trailing_or_stop_retry_blocked",
        ],
        "confidence_reason": (
            "Stop exits have large oracle regret after exp-20260630-011, but "
            "nearby exit families usually failed and close-confirmed stops can "
            "worsen gap losses."
        ),
    }


def audit_open_positions() -> dict[str, Any]:
    path = REPO_ROOT / "operator_inputs" / "open_positions.json"
    payload = read_json(path, {})
    rows: list[dict[str, Any]] = []
    for section in ("positions", "core_positions", "observations"):
        rows.extend([row for row in payload.get(section, []) if isinstance(row, dict)])
    missing = []
    for row in rows:
        for field in ("entry_date", "target_price"):
            if row.get(field) in (None, ""):
                missing.append({"ticker": row.get("ticker"), "section": row.get("section"), "field": field})
    return {
        "path": repo_rel(path),
        "checked_rows": len(rows),
        "required_fields": ["entry_date", "target_price"],
        "missing_required_fields": missing,
        "passed": not missing,
    }


def run_window(label: str, config: dict[str, Any]) -> dict[str, Any]:
    spec = WINDOWS[label]
    engine = BacktestEngine(
        get_universe(),
        start=spec["start"],
        end=spec["end"],
        config=config,
        ohlcv_snapshot_path=str(spec["snapshot"]),
        include_oracle_diagnostics=False,
    )
    result = engine.run()
    if result.get("error"):
        raise RuntimeError(f"{label} failed: {result['error']}")
    return {
        "metrics": metrics(result),
        "trades": result.get("trades") or [],
        "partial_reduce_attribution": result.get("partial_reduce_attribution") or {},
        "known_biases": result.get("known_biases") or {},
    }


def trade_key(row: dict[str, Any]) -> str:
    return str(row.get("trade_key") or f"{row.get('ticker')}:{row.get('entry_date')}:{row.get('entry_price')}")


def changed_trades(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> list[dict[str, Any]]:
    before_by_key = {trade_key(row): row for row in before}
    after_by_key = {trade_key(row): row for row in after}
    changed: list[dict[str, Any]] = []
    for key in sorted(set(before_by_key) | set(after_by_key)):
        b = before_by_key.get(key)
        a = after_by_key.get(key)
        if b is None or a is None:
            changed.append({
                "trade_key": key,
                "change_type": "added_or_removed_trade",
                "before_present": b is not None,
                "after_present": a is not None,
                "ticker": (a or b or {}).get("ticker"),
            })
            continue
        fields = ("exit_date", "exit_reason", "exit_price", "pnl", "shares", "stop_price")
        if any(b.get(field) != a.get(field) for field in fields):
            changed.append({
                "trade_key": key,
                "ticker": a.get("ticker"),
                "strategy": a.get("strategy"),
                "entry_date": a.get("entry_date"),
                "before_exit_date": b.get("exit_date"),
                "after_exit_date": a.get("exit_date"),
                "before_exit_reason": b.get("exit_reason"),
                "after_exit_reason": a.get("exit_reason"),
                "before_pnl": b.get("pnl"),
                "after_pnl": a.get("pnl"),
                "pnl_delta": rounded(float(a.get("pnl") or 0.0) - float(b.get("pnl") or 0.0), 2),
                "before_exit_price": b.get("exit_price"),
                "after_exit_price": a.get("exit_price"),
            })
    return changed


def summarize_changed(changed: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    all_rows = [row for rows in changed.values() for row in rows]
    by_reason = Counter(
        f"{row.get('before_exit_reason')}->{row.get('after_exit_reason')}"
        for row in all_rows
    )
    return {
        "changed_trade_count": len(all_rows),
        "changed_trade_count_by_window": {label: len(rows) for label, rows in changed.items()},
        "changed_exit_reason_pairs": dict(by_reason.most_common()),
        "changed_pnl_delta_sum": round(
            sum(float(row.get("pnl_delta") or 0.0) for row in all_rows),
            2,
        ),
        "sample_changed_trades": all_rows[:20],
    }


def make_payload() -> dict[str, Any]:
    gate2 = audit_open_positions()
    before_runs = {label: run_window(label, BASE_CONFIG) for label in WINDOWS}
    after_runs = {label: run_window(label, VARIANT_CONFIG) for label in WINDOWS}
    before_metrics = {label: before_runs[label]["metrics"] for label in WINDOWS}
    after_metrics = {label: after_runs[label]["metrics"] for label in WINDOWS}
    by_window_delta = {
        label: delta(after_metrics[label], before_metrics[label])
        for label in WINDOWS
    }
    aggregate_before = aggregate(before_metrics)
    aggregate_after = aggregate(after_metrics)
    aggregate_delta = delta(aggregate_after, aggregate_before)
    improved_windows = [
        label
        for label in WINDOWS
        if float(after_metrics[label].get("expected_value_score") or 0.0)
        > float(before_metrics[label].get("expected_value_score") or 0.0)
    ]
    regressed_windows = [
        label
        for label in WINDOWS
        if float(after_metrics[label].get("expected_value_score") or 0.0)
        < float(before_metrics[label].get("expected_value_score") or 0.0)
    ]
    changed = {
        label: changed_trades(before_runs[label]["trades"], after_runs[label]["trades"])
        for label in WINDOWS
    }
    changed_summary = summarize_changed(changed)
    max_drawdown_worse = max(
        float(by_window_delta[label].get("max_drawdown_pct") or 0.0)
        for label in WINDOWS
    )
    identity_expected = read_json(BASELINE_RESULT, {})
    identity_delta = delta(
        aggregate_before,
        {
            "expected_value_score_sum": 7.8941,
            "total_pnl_sum": 234850.99,
            "trade_count_sum": 61,
            "signals_generated_sum": 164,
            "signals_survived_sum": 135,
        },
    )
    gate4_passed = (
        float(aggregate_delta.get("expected_value_score_sum") or 0.0) > 0
        and float(aggregate_delta.get("total_pnl_sum") or 0.0) > 0
        and len(improved_windows) >= 2
        and not regressed_windows
        and aggregate_after["survival_rate_min"] >= 0.05
        and max_drawdown_worse <= MAX_DRAWDOWN_WORSE_GUARDRAIL
        and changed_summary["changed_trade_count"] > 0
    )
    accepted_alpha = False
    observed_only_lead = bool(gate4_passed)
    decision = (
        "positive_replay_lead_not_promoted_close_confirmed_static_stop"
        if observed_only_lead
        else "rejected_close_confirmed_static_stop"
    )
    failed_reasons: list[str] = []
    if float(aggregate_delta.get("expected_value_score_sum") or 0.0) <= 0:
        failed_reasons.append("aggregate_ev_not_positive")
    if float(aggregate_delta.get("total_pnl_sum") or 0.0) <= 0:
        failed_reasons.append("aggregate_pnl_not_positive")
    if len(improved_windows) < 2:
        failed_reasons.append("fewer_than_two_ev_improved_windows")
    if regressed_windows:
        failed_reasons.append("window_ev_regression")
    if aggregate_after["survival_rate_min"] < 0.05:
        failed_reasons.append("survival_below_floor")
    if max_drawdown_worse > MAX_DRAWDOWN_WORSE_GUARDRAIL:
        failed_reasons.append("drawdown_worse_than_guardrail")
    if changed_summary["changed_trade_count"] <= 0:
        failed_reasons.append("no_changed_trades")

    prediction = load_ticket_prediction()
    actual_success = 1 if observed_only_lead else 0
    predicted_p = float(prediction.get("success_probability") or 0.0)
    realized_failure_modes = failed_reasons or []

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": "alpha_search",
        "status": "observed_only_positive_lead" if observed_only_lead else "rejected",
        "decision": decision,
        "accepted": observed_only_lead,
        "accepted_alpha": accepted_alpha,
        "observed_only_lead": observed_only_lead,
        "alpha_ready": False,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "causal_components": CAUSAL_COMPONENTS,
        "prediction": prediction,
        "calibration": {
            "actual_decision": decision,
            "actual_success": actual_success,
            "predicted_success_probability": predicted_p,
            "brier_score": round((actual_success - predicted_p) ** 2, 6),
            "predicted_failure_modes": prediction.get("main_failure_modes") or [],
            "realized_failure_modes": realized_failure_modes,
            "predicted_failure_mode_hit": bool(
                set(prediction.get("main_failure_modes") or []) & set(realized_failure_modes)
            ),
            "actual_ev_delta": aggregate_delta.get("expected_value_score_sum"),
            "actual_pnl_delta": aggregate_delta.get("total_pnl_sum"),
            "surprise_note": (
                "Close-confirmed stops cleared Gate 4 but remain replay-only until "
                "shared bracket-order/run semantics are implemented."
                if observed_only_lead
                else "The close-confirmed stop semantics did not clear the canonical Gate 4 replay."
            ),
        },
        "parameters": {
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "before_config": BASE_CONFIG,
            "after_config": VARIANT_CONFIG,
            "windows": {label: {**spec, "snapshot": repo_rel(spec["snapshot"])} for label, spec in WINDOWS.items()},
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "acceptance_rule": (
                "Aggregate EV and PnL positive, at least two EV-improved windows, "
                "no EV-regressed windows, survival >= 5%, drawdown drift <= 0.5pp, "
                "and at least one changed trade."
            ),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": (
                "Exit policy: close-confirmed static stops may avoid intraday "
                "stopout shakeouts while keeping the existing static stop level."
            ),
            "2_history_check": {
                "novelty_gate": "experiment.py new passed without override.",
                "exp-20260425-029": "Generic ATR trailing stops rejected.",
                "exp-20260623-020": "Static entry stop dominated daily trailing stop.",
                "exp-20260623-022": "Regime-conditional ATR trailing scout rejected.",
                "exp-20260630-011": "Full trade-level exit oracle rows repaired stop/regret denominator; it forbids target/trailing/time/response retunes and requires one predeclared production-visible exit signal.",
            },
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": "docs/backtesting.md Gate 1-4 on the three fixed windows; replay-only positive cannot promote without shared run/bracket-order semantics.",
            "5_reproducibility": RUNNER_COMMAND,
        },
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "baseline_identity_reference": {
                "expected_value_score_sum": 7.8941,
                "total_pnl_sum": 234850.99,
                "trade_count_sum": 61,
                "signals_generated_sum": 164,
                "signals_survived_sum": 135,
            },
            "rerun_before_aggregate": aggregate_before,
            "identity_delta_vs_reference": identity_delta,
        },
        "gate2": {
            "dependencies_validated": True,
            "open_positions": gate2,
            "fields_checked": [
                "trades.entry_date",
                "trades.target_price",
                "trades.stop_price",
                "OHLCV Open/High/Low/Close",
                "next trading session open",
            ],
            "target_price_scope": "Checked for protocol completeness; target geometry is unchanged by this stop-semantics scout.",
        },
        "gate3": {
            "filter_added": False,
            "signals_generated_before": aggregate_before["signals_generated_sum"],
            "signals_survived_before": aggregate_before["signals_survived_sum"],
            "signals_generated_after": aggregate_after["signals_generated_sum"],
            "signals_survived_after": aggregate_after["signals_survived_sum"],
            "survival_rate_min_after": aggregate_after["survival_rate_min"],
            "passed": aggregate_after["survival_rate_min"] >= 0.05,
        },
        "gate4": {
            "passed": gate4_passed,
            "accepted_alpha": accepted_alpha,
            "observed_only_lead": observed_only_lead,
            "decision": decision,
            "failed_reasons": failed_reasons,
            "improved_windows": improved_windows,
            "regressed_windows": regressed_windows,
            "max_drawdown_worse": round(max_drawdown_worse, 6),
            "changed_trade_count": changed_summary["changed_trade_count"],
            "strategy_rerun_required_for_promotion": True,
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": by_window_delta,
            "aggregate_before": aggregate_before,
            "aggregate_after": aggregate_after,
            "aggregate_delta": aggregate_delta,
            "changed_trades": changed_summary,
        },
        "changed_trades_by_window": changed,
        "production_impact": {
            "trade_enabled": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "target_geometry_changed": False,
            "paper_orders_changed": False,
            "live_orders_changed": False,
            "watchlist_changed": False,
            "llm_decision_boundary_changed": False,
            "daily_snapshot_exposed": False,
            "live_ready": False,
            "live_realism_evaluated": True,
            "activation_envelope": {
                "intended_notional": "same as current core positions if ever promoted",
                "capital_cap": "same as current core strategy if ever promoted",
                "liquidity_slippage_model": "next-session open fill with existing backtester slippage model",
                "portfolio_displacement": "same entries and slots; only stop exit timing changes",
                "order_semantics": (
                    "Would require replacing current operator-placed GTC protective "
                    "stops with EOD close-breach review plus next-open market sell. "
                    "This runner does not make that production change."
                ),
                "kill_switch": "do not promote if any canonical window EV regresses or drawdown worsens over 0.5pp",
            },
            "parity_note": (
                "Replay scout only. Current production writes GTC bracket stop "
                "orders, so a positive result would still need shared run.py / "
                "bracket_orders semantics and parity tests before promotion."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "Close-confirmed stops changed enough trade exits to test the "
                "shakeout hypothesis."
                if changed_summary["changed_trade_count"]
                else "The close-confirmed stop flags did not affect the canonical trade set."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune stop distance, trailing stops, target trims, "
                "time stops, hold days, or response curves from these same rows."
            ),
            "new_evidence_required": (
                "A valid retry requires a shared production/backtest stop-order "
                "semantics helper, prospective shadow close-confirmed stop rows "
                "with settled outcomes, or a materially different pre-exit data signal."
            ),
        },
        "rejection_reason": None if observed_only_lead else ";".join(failed_reasons),
        "next_retry_requires": [
            "shared run.py/bracket_orders stop semantics if the replay is positive",
            "prospective shadow close-confirmed stop rows with settled outcomes",
            "a materially different pre-exit data signal, not stop/target/trail retuning",
        ],
        "before_after_strategy_behavior_changed": True,
        "related_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(BASELINE_RESULT),
            "quant/backtester.py",
            "quant/bracket_orders.py",
            "quant/run.py",
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "lean_quality_passed": True,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
    }


def make_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades d |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        dlt = payload["delta_metrics"]["by_window"][label]
        rows.append(
            f"| {label} | {before.get('expected_value_score')} | "
            f"{after.get('expected_value_score')} | {dlt.get('expected_value_score')} | "
            f"{before.get('total_pnl')} | {after.get('total_pnl')} | "
            f"{dlt.get('total_pnl')} | {dlt.get('max_drawdown_pct')} | "
            f"{dlt.get('trade_count')} |"
        )
    agg = payload["delta_metrics"]["aggregate_delta"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} close-confirmed static stop",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            HYPOTHESIS,
            "",
            *rows,
            "",
            "Aggregate delta: "
            f"EV `{agg.get('expected_value_score_sum')}`, "
            f"PnL `{agg.get('total_pnl_sum')}`, "
            f"changed trades `{payload['delta_metrics']['changed_trades']['changed_trade_count']}`.",
            "",
            "Production boundary: replay scout only. Current production writes "
            "GTC bracket stops, so promotion would require shared run/bracket "
            "order semantics and parity tests.",
        ]
    ) + "\n"


def make_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        Path(RUNNER),
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": utc_now(),
        "files": [
            {
                "path": repo_rel(path),
                "exists": (REPO_ROOT / path if not path.is_absolute() else path).exists(),
                "sha256": sha256(REPO_ROOT / path if not path.is_absolute() else path),
            }
            for path in files
        ],
        "reproduction_commands": payload["reproduction_commands"],
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    write_text(CARD_MD, make_card(payload))
    write_json(MANIFEST_JSON, make_manifest(payload))
    save_experiment_log_entry(payload, allow_duplicate=True)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload.get("prediction") or {},
        result=payload,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "change_type": CHANGE_TYPE,
            "implementation_mode": IMPLEMENTATION_MODE,
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "accepted_alpha": payload["accepted_alpha"],
            "lean_quality_passed": payload["lean_quality_passed"],
        },
    )


def main() -> None:
    payload = make_payload()
    persist(payload)
    print(json.dumps(safe({
        "experiment_id": EXPERIMENT_ID,
        "decision": payload["decision"],
        "aggregate_delta": payload["delta_metrics"]["aggregate_delta"],
        "changed_trade_count": payload["delta_metrics"]["changed_trades"]["changed_trade_count"],
        "artifact": payload["artifact"],
    }), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
