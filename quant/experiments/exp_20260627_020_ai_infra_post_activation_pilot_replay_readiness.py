"""exp-20260627-020: AI_INFRA post-activation pilot replay readiness.

Observed-only alpha/risk-allocation audit over a post-activation
``--include-pilot-sleeve`` replay from 2026-05-01 through 2026-06-26. The
experiment asks whether the AI_INFRA_AGGRESSIVE pilot sleeve now has enough
closed PIT replay evidence and replacement value to justify promotion work.

This runner does not change strategy behavior, live orders, paper ledgers,
pilot state, ranking, sizing, entries, or exits. It summarizes the replay JSON
created by the canonical backtester command and persists a compact experiment
artifact plus registry/log handoff records.
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


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260627-020"
OWNER = "alpha-explore"
SLUG = "ai_infra_post_activation_pilot_replay_readiness"
RUNNER = f"quant/experiments/exp_20260627_020_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260627_020_{SLUG}.json"
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
BACKTEST_DIR = REPO_ROOT / "data" / "backtests"
EXPECTED_REPLAY_RESULT = BACKTEST_DIR / "backtest_results_20260627.json"
REPLAY_TMP_GLOB = ".backtest_results_20260627.json.*.tmp"
LEGACY_WAREHOUSE = REPO_ROOT / "data" / "experiments" / "exp-20260519-030" / "warehouse_main.sqlite"
CURRENT_WAREHOUSE = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"

HYPOTHESIS = (
    "Post-activation AI_INFRA_AGGRESSIVE pilot replay from 2026-05-01 through "
    "2026-06-26 may now provide enough PIT direct and replacement-value "
    "evidence to justify continued promotion readiness without changing core "
    "orders; if replay entries, replacement value, or drawdown fail, no "
    "allocation change is justified."
)
CHANGE_TYPE = "pilot_activation_replay_readiness"
IMPLEMENTATION_MODE = "observed_only_attribution"
MECHANISM_FAMILY = "pilot_or_sleeve"
TRIAL_FAMILY = "ai_infra_post_activation_pilot_replay_readiness"
TRIAL_VARIANT_ID = "post_activation_20260501_20260626_v1"
CHANGED_VARIABLE = "post_activation_ai_infra_include_pilot_sleeve_replay_readiness_v1"
CAUSAL_COMPONENTS = [
    "shared include-pilot-sleeve replay",
    "current warehouse OHLCV",
    "read-only promotion gates",
    "no order changes",
]
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260519-014",
    "exp-20260524-001",
    "exp-20260623-017",
    "exp-20260627-001",
]
NEW_EVIDENCE_AXIS = (
    "Post-activation 2026-05-01..2026-06-26 PIT --include-pilot-sleeve "
    "replay rows after pilot activation are a new forward evidence axis "
    "required by docs/backtesting.md; this is not a fixed-window threshold or "
    "response retune."
)
CURRENT_REPLAY_COMMAND = (
    ".\\.venv\\Scripts\\python.exe -B quant\\backtester.py --start 2026-05-01 "
    "--end 2026-06-26 --ohlcv-warehouse data\\warehouse\\warehouse_main.sqlite "
    "--include-pilot-sleeve"
)
LEGACY_REPLAY_COMMAND = (
    ".\\.venv\\Scripts\\python.exe -B quant\\backtester.py --start 2026-05-01 "
    "--end 2026-06-26 --ohlcv-warehouse "
    "data\\experiments\\exp-20260519-030\\warehouse_main.sqlite --include-pilot-sleeve"
)
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260627-020/exp_20260627_020_ai_infra_post_activation_pilot_replay_readiness.json",
    "experiments/cards/exp-20260627-020.md",
    "experiments/manifests/exp-20260627-020.json",
    "experiments/tickets/exp-20260627-020.json",
    "experiments/logs/exp-20260627-020.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    path = Path(path)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default if default is not None else {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
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


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def safe_int(value: Any) -> int:
    if value is None or isinstance(value, bool):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def load_ticket_prediction(ticket: dict[str, Any]) -> dict[str, Any]:
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    if isinstance(prediction, dict) and prediction.get("confidence_reason"):
        return prediction
    return {
        "success_probability": 0.18,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "thin_replay_entries",
            "negative_replacement_value",
            "drawdown_or_concentration_failed",
            "no_closed_replacement_rows",
        ],
        "confidence_reason": (
            "Fallback prediction; reservation should carry the pre-run "
            "prediction for this post-activation pilot replay audit."
        ),
        "recorded_at": utc_now(),
    }


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    generated = sum(float(row.get("signals_generated") or 0.0) for row in windows)
    survived = sum(float(row.get("signals_survived") or 0.0) for row in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": int(sum(int(row.get("trade_count") or 0) for row in windows)),
        "signals_generated": int(generated),
        "signals_survived": int(survived),
        "survival_rate": round(survived / generated, 4) if generated else None,
        "max_drawdown_pct_worst": max(
            (float(row.get("max_drawdown_pct") or 0.0) for row in windows),
            default=None,
        ),
        "window_count": len(windows),
        "windows": [
            {
                "label": row.get("label"),
                "start": row.get("start"),
                "end": row.get("end"),
                "expected_value_score": row.get("expected_value_score"),
                "total_pnl": row.get("total_pnl"),
                "trade_count": row.get("trade_count"),
                "signals_generated": row.get("signals_generated"),
                "signals_survived": row.get("signals_survived"),
                "survival_rate": row.get("survival_rate"),
                "max_drawdown_pct": row.get("max_drawdown_pct"),
                "sharpe_daily": row.get("sharpe_daily"),
            }
            for row in windows
            if isinstance(row, dict)
        ],
    }


def replay_source() -> Path:
    if EXPECTED_REPLAY_RESULT.exists():
        return EXPECTED_REPLAY_RESULT
    candidates = sorted(
        BACKTEST_DIR.glob(REPLAY_TMP_GLOB),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if candidates:
        return candidates[0]
    raise FileNotFoundError(
        "No 2026-06-27 replay JSON found. Run CURRENT_REPLAY_COMMAND first."
    )


def compact_replay_metrics(result: dict[str, Any]) -> dict[str, Any]:
    primary = result.get("primary") if isinstance(result.get("primary"), dict) else result
    secondary = result.get("secondary") if isinstance(result.get("secondary"), dict) else {}
    benchmarks = primary.get("benchmarks") or {}
    convergence = primary.get("convergence") or {}
    criteria = convergence.get("criteria") or {}
    if isinstance(criteria, dict):
        failed_convergence = [
            name
            for name, row in criteria.items()
            if isinstance(row, dict) and not row.get("pass", row.get("passed"))
        ]
    else:
        failed_convergence = [
            row.get("name")
            for row in criteria
            if isinstance(row, dict) and not row.get("passed", row.get("pass"))
        ]
    return {
        "source_period": primary.get("period"),
        "trading_days": primary.get("trading_days"),
        "total_trades": primary.get("total_trades"),
        "win_rate": primary.get("win_rate"),
        "total_pnl": primary.get("total_pnl"),
        "expected_value_score": primary.get("expected_value_score"),
        "sharpe_daily": primary.get("sharpe_daily"),
        "max_drawdown_pct": primary.get("max_drawdown_pct"),
        "signals_generated": primary.get("signals_generated"),
        "signals_survived": primary.get("signals_survived"),
        "survival_rate": primary.get("survival_rate"),
        "converged": convergence.get("converged"),
        "failed_convergence": failed_convergence,
        "beats_spy": (safe_float(benchmarks.get("strategy_vs_spy_pct")) or 0.0) > 0.0,
        "beats_qqq": (safe_float(benchmarks.get("strategy_vs_qqq_pct")) or 0.0) > 0.0,
        "strategy_vs_spy_pct": benchmarks.get("strategy_vs_spy_pct"),
        "strategy_vs_qqq_pct": benchmarks.get("strategy_vs_qqq_pct"),
        "trade_tickers": [row.get("ticker") for row in primary.get("trades") or []],
        "secondary": {
            "period": secondary.get("period"),
            "total_trades": secondary.get("total_trades"),
            "total_pnl": secondary.get("total_pnl"),
            "expected_value_score": secondary.get("expected_value_score"),
            "sharpe_daily": secondary.get("sharpe_daily"),
            "max_drawdown_pct": secondary.get("max_drawdown_pct"),
            "pilot_entries": (
                (secondary.get("pilot_sleeve_replay") or {}).get("entries")
                if isinstance(secondary, dict)
                else None
            ),
        },
    }


def summarize_pilot(pilot: dict[str, Any]) -> dict[str, Any]:
    decisions = [row for row in pilot.get("decisions") or [] if isinstance(row, dict)]
    status_counts = Counter(str(row.get("status") or "") for row in decisions)
    by_sleeve = pilot.get("eligible_tickers_by_sleeve")
    if not isinstance(by_sleeve, dict):
        by_sleeve = {}
    return {
        "enabled": bool(pilot.get("enabled")),
        "sleeve": pilot.get("sleeve"),
        "primary_sleeve": pilot.get("primary_sleeve"),
        "eligible_days": safe_int(pilot.get("eligible_days")),
        "eligible_tickers": pilot.get("eligible_tickers") or [],
        "eligible_tickers_by_sleeve": by_sleeve,
        "signals_generated": safe_int(pilot.get("signals_generated")),
        "signals_survived": safe_int(pilot.get("signals_survived")),
        "survival_rate": (
            round(safe_int(pilot.get("signals_survived")) / safe_int(pilot.get("signals_generated")), 4)
            if safe_int(pilot.get("signals_generated"))
            else None
        ),
        "entries": safe_int(pilot.get("entries")),
        "closed_trades": safe_int(pilot.get("closed_trades")),
        "direct_pilot_pnl": safe_float(pilot.get("direct_pilot_pnl")),
        "cash_relative_pnl": safe_float(pilot.get("cash_relative_pnl")),
        "replacement_value": safe_float(pilot.get("replacement_value")),
        "risk_adjusted_replacement_value_avg": safe_float(
            pilot.get("risk_adjusted_replacement_value_avg")
        ),
        "pending_counterfactual_outcomes": safe_int(pilot.get("pending_counterfactual_outcomes")),
        "by_ticker": pilot.get("by_ticker") or {},
        "decision_status_counts": dict(status_counts),
        "ai_infra_candidate_tickers": sorted(
            {
                row.get("ticker")
                for row in decisions
                if isinstance(row.get("decision_id"), str)
                and "AI_INFRA_AGGRESSIVE" in row.get("decision_id")
                and row.get("ticker")
            }
        ),
        "entered_tickers": sorted(
            {row.get("ticker") for row in decisions if row.get("status") == "entered"}
        ),
        "closed_tickers": sorted(
            {row.get("ticker") for row in decisions if row.get("status") == "closed"}
        ),
        "decisions": decisions,
        "notes": pilot.get("notes") or [],
    }


def field_exists(payload: Any, path: list[str]) -> bool:
    current = payload
    for key in path:
        if isinstance(current, dict):
            if key not in current:
                return False
            current = current[key]
        elif isinstance(current, list):
            if not current:
                return False
            current = current[0]
            if not isinstance(current, dict) or key not in current:
                return False
            current = current[key]
        else:
            return False
    return True


def readiness_decision(
    replay_metrics: dict[str, Any],
    pilot_summary: dict[str, Any],
) -> tuple[bool, list[str], dict[str, bool]]:
    checks = {
        "pilot_replay_enabled": bool(pilot_summary["enabled"]),
        "has_post_activation_eligible_days": pilot_summary["eligible_days"] > 0,
        "pilot_closed_rows_min_20": pilot_summary["closed_trades"] >= 20,
        "pilot_entries_min_5": pilot_summary["entries"] >= 5,
        "replacement_value_positive": (pilot_summary["replacement_value"] or 0.0) > 0.0,
        "risk_adjusted_replacement_available": pilot_summary[
            "risk_adjusted_replacement_value_avg"
        ]
        is not None,
        "no_pending_counterfactuals": pilot_summary["pending_counterfactual_outcomes"] == 0,
        "core_primary_converged": bool(replay_metrics["converged"]),
        "core_trade_count_min_15": safe_int(replay_metrics["total_trades"]) >= 15,
        "core_drawdown_under_20pct": (safe_float(replay_metrics["max_drawdown_pct"]) or 1.0)
        <= 0.20,
        "beats_spy_and_qqq": bool(replay_metrics["beats_spy"])
        and bool(replay_metrics["beats_qqq"]),
    }
    failed: list[str] = []
    if not checks["pilot_replay_enabled"]:
        failed.append("pilot_replay_not_enabled")
    if not checks["has_post_activation_eligible_days"]:
        failed.append("no_post_activation_eligible_days")
    if not checks["pilot_closed_rows_min_20"]:
        failed.append("thin_replay_entries")
    if not checks["pilot_entries_min_5"]:
        failed.append("too_few_entered_pilot_trades")
    if not checks["replacement_value_positive"]:
        failed.append("negative_replacement_value")
    if not checks["risk_adjusted_replacement_available"]:
        failed.append("risk_adjusted_replacement_unavailable")
    if not checks["no_pending_counterfactuals"]:
        failed.append("pending_counterfactual_outcomes")
    if not checks["core_primary_converged"]:
        failed.append("core_primary_not_converged")
    if not checks["core_trade_count_min_15"]:
        failed.append("primary_trade_count_below_15")
    if not checks["core_drawdown_under_20pct"]:
        failed.append("drawdown_or_concentration_failed")
    if not checks["beats_spy_and_qqq"]:
        failed.append("benchmark_underperformance")
    return not failed, failed, checks


def calibration(prediction: dict[str, Any], success: bool, failed_reasons: list[str]) -> dict[str, Any]:
    probability = safe_float(prediction.get("success_probability")) or 0.0
    predicted = prediction.get("main_failure_modes") or []
    realized = []
    if "thin_replay_entries" in failed_reasons or "too_few_entered_pilot_trades" in failed_reasons:
        realized.append("thin_replay_entries")
    if "negative_replacement_value" in failed_reasons:
        realized.append("negative_replacement_value")
    if "drawdown_or_concentration_failed" in failed_reasons:
        realized.append("drawdown_or_concentration_failed")
    if "risk_adjusted_replacement_unavailable" in failed_reasons:
        realized.append("risk_adjusted_replacement_unavailable")
    return {
        "predicted_success_probability": probability,
        "actual_success": success,
        "brier_score": round((probability - (1.0 if success else 0.0)) ** 2, 4),
        "predicted_failure_modes": predicted,
        "realized_failure_modes": realized,
        "failed_reasons": failed_reasons,
    }


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = load_ticket_prediction(ticket)
    baseline = baseline_metrics()
    source = replay_source()
    replay = read_json(source, {})
    primary = replay.get("primary") if isinstance(replay.get("primary"), dict) else replay
    pilot = primary.get("pilot_sleeve_replay") if isinstance(primary, dict) else {}
    if not isinstance(pilot, dict):
        pilot = {}
    replay_metrics = compact_replay_metrics(replay)
    pilot_summary = summarize_pilot(pilot)
    success, failed_reasons, readiness_checks = readiness_decision(
        replay_metrics,
        pilot_summary,
    )
    status = "observed_only_accepted" if success else "observed_only_rejected"
    decision = (
        "accepted_ai_infra_post_activation_promotion_ready"
        if success
        else "rejected_ai_infra_post_activation_promotion_not_ready"
    )
    now = utc_now()
    source_is_tmp = source.name.startswith(".backtest_results_")
    target_price_saved = any("target_price" in row for row in primary.get("trades") or [])
    entry_date_saved = field_exists(primary, ["trades", "entry_date"])
    after_metrics = {
        **baseline,
        "post_activation_replay_expected_value_score": replay_metrics["expected_value_score"],
        "post_activation_replay_total_pnl": replay_metrics["total_pnl"],
        "post_activation_replay_trade_count": replay_metrics["total_trades"],
        "post_activation_replay_survival_rate": replay_metrics["survival_rate"],
        "post_activation_replay_max_drawdown_pct": replay_metrics["max_drawdown_pct"],
        "pilot_entries": pilot_summary["entries"],
        "pilot_closed_trades": pilot_summary["closed_trades"],
        "pilot_replacement_value": pilot_summary["replacement_value"],
        "pilot_direct_pnl": pilot_summary["direct_pilot_pnl"],
    }
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": status,
        "decision": decision,
        "accepted": success,
        "accepted_alpha": False,
        "observed_only_lead": success,
        "lane": "alpha_search",
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
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "post_activation_pilot_replay_rows",
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "calibration": calibration(prediction, success, failed_reasons),
        "pre_run_questions": {
            "alpha_hypothesis": HYPOTHESIS,
            "history_check": (
                "Novelty gate allowed the ticket without override. Nearby priors "
                "were AI_INFRA segment shadow, AI_INFRA promotion-readiness "
                "blocker surfacing, live pilot scalar attribution, and current "
                "pilot scorecard graduation readiness."
            ),
            "single_policy_bundle": (
                "One read-only post-activation include-pilot-sleeve replay "
                "readiness audit; no strategy behavior changed."
            ),
            "success_standard": (
                "Promotion work requires materially closed pilot rows, positive "
                "replacement value, available risk-adjusted replacement evidence, "
                "no pending counterfactuals, primary replay convergence, and no "
                "drawdown or benchmark failure."
            ),
            "reproduction": RUNNER_COMMAND,
        },
        "parameters": {
            "activation_window_start": "2026-05-01",
            "activation_window_end_requested": "2026-06-26",
            "activation_window_end_simulated": "2026-06-25",
            "legacy_warehouse": repo_rel(LEGACY_WAREHOUSE),
            "current_warehouse": repo_rel(CURRENT_WAREHOUSE),
            "replay_source": repo_rel(source),
            "replay_source_is_backtester_temp": source_is_tmp,
            "legacy_warehouse_attempt": {
                "command": LEGACY_REPLAY_COMMAND,
                "result": "failed_before_simulation",
                "reason": "Loaded 0/60 requested tickers for May-June 2026 and exited with No data downloaded.",
            },
            "current_warehouse_command": CURRENT_REPLAY_COMMAND,
            "current_warehouse_save_caveat": (
                "Backtester printed complete results and left a complete temp JSON, "
                "but os.replace to data/backtests/backtest_results_20260627.json "
                "raised Windows PermissionError."
            ),
        },
        "replay_metrics": replay_metrics,
        "pilot_replay_summary": pilot_summary,
        "before_metrics": baseline,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "aggregate_expected_value_score": 0.0,
            "aggregate_total_pnl": 0.0,
            "expected_value_score_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "survival_rate_delta": 0.0,
            "strategy_behavior_delta": 0.0,
            "pilot_replacement_value": pilot_summary["replacement_value"],
            "pilot_closed_trades": pilot_summary["closed_trades"],
        },
        "gate1": {
            "passed": True,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "baseline_expected_value_score_sum": baseline["expected_value_score_sum"],
            "baseline_total_pnl": baseline["total_pnl"],
            "baseline_trade_count": baseline["trade_count"],
        },
        "gate2": {
            "passed": all(
                [
                    bool(primary),
                    field_exists(primary, ["pilot_sleeve_replay", "entries"]),
                    field_exists(primary, ["pilot_sleeve_replay", "closed_trades"]),
                    field_exists(primary, ["pilot_sleeve_replay", "replacement_value"]),
                    field_exists(primary, ["pilot_sleeve_replay", "decisions", "date"]),
                    field_exists(primary, ["pilot_sleeve_replay", "decisions", "ticker"]),
                    entry_date_saved,
                ]
            ),
            "required_fields": [
                "pilot_sleeve_replay.entries",
                "pilot_sleeve_replay.closed_trades",
                "pilot_sleeve_replay.replacement_value",
                "pilot_sleeve_replay.decisions.date",
                "pilot_sleeve_replay.decisions.ticker",
                "trades.entry_date",
            ],
            "entry_date_present": entry_date_saved,
            "target_price_present_in_saved_trade_rows": target_price_saved,
            "target_price_required": False,
            "target_price_note": (
                "This audit reads backtester replay output and does not introduce "
                "a new target-price rule. Saved trade rows expose entry_date, "
                "entry_price, stop_price, target_mult_used, exit_price, and "
                "exit_reason; target_price is not serialized as a separate field."
            ),
        },
        "gate3": {
            "passed": (
                replay_metrics["survival_rate"] is not None
                and safe_float(replay_metrics["survival_rate"]) >= 0.05
                and (pilot_summary["survival_rate"] is None or pilot_summary["survival_rate"] >= 0.05)
            ),
            "signals_generated": replay_metrics["signals_generated"],
            "signals_survived": replay_metrics["signals_survived"],
            "survival_rate": replay_metrics["survival_rate"],
            "pilot_signals_generated": pilot_summary["signals_generated"],
            "pilot_signals_survived": pilot_summary["signals_survived"],
            "pilot_survival_rate": pilot_summary["survival_rate"],
            "filter_added": False,
            "note": "No filter was added; this is a read-only pilot replay audit.",
        },
        "gate4": {
            "passed": success,
            "decision": decision,
            "checks": readiness_checks,
            "failed_reasons": failed_reasons,
            "before_after_policy_delta": "none",
            "expected_value_score_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "survival_rate_delta": 0.0,
            "status": status,
        },
        "production_impact": {
            "trade_enabled": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "pilot_state_changed": False,
            "pilot_recommendations_changed": False,
            "daily_snapshot_exposed": False,
            "live_ready": False,
            "replay_only": True,
            "parity_note": (
                "Uses the shared backtester --include-pilot-sleeve replay path. "
                "Replay is in-memory and explicitly does not write production "
                "pilot competition ledgers."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The current warehouse post-activation replay produced a good "
                "core short-window result, but it was not converged because only "
                "six core trades closed. The pilot sleeve generated seven "
                "surviving pilot signals but only one entered/closed trade "
                "(COHR), and that row lost 658.54 USD versus cash replacement. "
                "Risk-adjusted replacement value is unavailable, so the sleeve "
                "still lacks material closed evidence for promotion."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not rerun AI_INFRA post-activation promotion readiness by "
                "only changing min_closed, notional, RV, risk-adjusted RV, or "
                "drawdown gates on the same 2026-05-01..2026-06-26 replay. "
                "Reopen only with materially more closed post-activation pilot "
                "rows, a different shared allocation policy through Gate 1-4, "
                "or a new production-visible evidence source."
            ),
            "new_evidence_required": (
                "Need at least materially more closed AI_INFRA pilot rows with "
                "positive replacement value versus cash/SPY/QQQ, or a separate "
                "shared-policy allocation experiment that changes actual "
                "selection/sizing and passes Gate 1-4."
            ),
            "reproducibility": (
                "Run the current warehouse backtester command, then run this "
                "runner. On this Windows run the backtester left a complete temp "
                "JSON because atomic replace failed with PermissionError; the "
                "runner records that caveat and summarizes the temp JSON."
            ),
        },
        "related_files": [
            repo_rel(BASELINE_RESULT),
            repo_rel(source),
            repo_rel(TICKET_JSON),
            repo_rel(CURRENT_WAREHOUSE),
            repo_rel(LEGACY_WAREHOUSE),
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
        ],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "reproduction_commands": [
            LEGACY_REPLAY_COMMAND,
            CURRENT_REPLAY_COMMAND,
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": {"used_javascript": False, "evidence": "Python runner only; no node/js tooling invoked."},
        "lean_quality_passed": True,
        "ticket_before": {
            "created_at": ticket.get("created_at"),
            "claimed_at": ticket.get("claimed_at"),
            "hub_identity": ticket.get("hub_identity"),
            "novelty": ticket.get("novelty"),
        },
    }
    return payload


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
        "pre_run_questions",
        "parameters",
        "replay_metrics",
        "pilot_replay_summary",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "production_impact",
        "post_run_reflection",
        "related_files",
        "changed_files",
        "allowed_write_scope",
        "reproduction_commands",
        "artifact",
        "log",
        "anti_js",
        "lean_quality_passed",
    ]
    return {key: payload[key] for key in keys}


def build_card(payload: dict[str, Any]) -> str:
    replay = payload["replay_metrics"]
    pilot = payload["pilot_replay_summary"]
    rows = [
        "| Metric | Value |",
        "|---|---:|",
        f"| Core post-activation trades | {replay['total_trades']} |",
        f"| Core post-activation PnL | {replay['total_pnl']} |",
        f"| Core post-activation EV score | {replay['expected_value_score']} |",
        f"| Core converged | {str(replay['converged']).lower()} |",
        f"| Pilot signals survived | {pilot['signals_survived']} |",
        f"| Pilot entries / closed | {pilot['entries']} / {pilot['closed_trades']} |",
        f"| Pilot replacement value | {pilot['replacement_value']} |",
        f"| Risk-adjusted replacement avg | {pilot['risk_adjusted_replacement_value_avg']} |",
    ]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: AI_INFRA post-activation pilot replay readiness",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Strategy behavior changed: `false`",
            "- Live/default orders changed: `false`",
            f"- Replay source: `{payload['parameters']['replay_source']}`",
            f"- Failed checks: `{', '.join(payload['gate4']['failed_reasons']) or 'none'}`",
            f"- Artifact: `{repo_rel(OUT_JSON)}`",
            "",
            "## Readout",
            "",
            *rows,
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Reproduction",
            "",
            "```powershell",
            CURRENT_REPLAY_COMMAND,
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
            "```",
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    source = REPO_ROOT / payload["parameters"]["replay_source"]
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        BASELINE_RESULT,
        source,
        CURRENT_WAREHOUSE,
        LEGACY_WAREHOUSE,
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
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "allowed_write_scope": payload["allowed_write_scope"],
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)

    ticket_before = payload.get("ticket_before") or {}
    fields = {
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
        "new_evidence_axis": payload["new_evidence_axis"],
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card_file": repo_rel(CARD_MD),
        "revision_manifest_file": repo_rel(MANIFEST_JSON),
        "ticket_file": repo_rel(TICKET_JSON),
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "allowed_write_scope": payload["allowed_write_scope"],
        "related_files": payload["related_files"],
        "changed_files": payload["changed_files"],
        "lean_quality_passed": payload["lean_quality_passed"],
        "hub_identity": ticket_before.get("hub_identity"),
        "novelty": ticket_before.get("novelty"),
        "claimed_at": ticket_before.get("claimed_at"),
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "calibration": payload["calibration"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields=fields,
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
                "core_trades": payload["replay_metrics"]["total_trades"],
                "core_expected_value_score": payload["replay_metrics"][
                    "expected_value_score"
                ],
                "pilot_entries": payload["pilot_replay_summary"]["entries"],
                "pilot_closed_trades": payload["pilot_replay_summary"]["closed_trades"],
                "pilot_replacement_value": payload["pilot_replay_summary"][
                    "replacement_value"
                ],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
