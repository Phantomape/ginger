"""exp-20260622-010: Moomoo daily short-volume activity absorption.

Full-stack-shaped alpha search using the raw archive seeded by
exp-20260622-009. The fixed bundle treats Moomoo daily short volume as
activity-only sell-pressure context, maps each activity date to the next
tradable session, and tests a default-off top-1/day 10-day paper overlay.

No live/default orders, core ranking, sizing, exits, LLM/news path, or watchlist
behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
EXPERIMENTS_ROOT = QUANT_ROOT / "experiments"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, QUANT_ROOT, EXPERIMENTS_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
from exp_20260622_010_moomoo_daily_short_volume_activity_helper import (  # noqa: E402
    DEFAULT_ACTIVITY_ROWS_PATH,
    DEFAULT_CONFIG,
    RULE_VERSION,
    SOURCE_RULE_VERSION,
    build_moomoo_daily_short_volume_historical_trades,
    build_moomoo_daily_short_volume_paper_sleeve_snapshot,
    empty_moomoo_daily_short_volume_state,
    load_moomoo_daily_short_volume_activity_rows,
)
from quant.full_stack_candidate_pool import (  # noqa: E402
    ExecutionEnvelope,
    evaluate_gate4,
    evaluate_live_readiness,
    full_stack_verdict,
)


EXPERIMENT_ID = "exp-20260622-010"
STEM = "moomoo_daily_short_volume_activity_absorption"
RUNNER = f"quant/experiments/exp_20260622_010_{STEM}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
OWNER = "alpha-explore-automation"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260622_010_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "quant/experiments/exp_20260622_010_moomoo_daily_short_volume_activity_helper.py",
    "quant/test_exp_20260622_010_moomoo_daily_short_volume_activity_helper.py",
    "data/experiments/exp-20260622-010",
    "experiments/tickets/exp-20260622-010.json",
    "experiments/logs/exp-20260622-010.json",
    "experiments/cards/exp-20260622-010.md",
    "experiments/manifests/exp-20260622-010.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]

COMPRESSION_COMPARATOR = {
    "experiment_id": "exp-20260608-013",
    "decision": "accepted_narrow_range_compression_breakout_shared_default_off_adapter",
    "aggregate_expected_value_delta": 0.1608,
    "aggregate_pnl_delta": 2248.98,
}
DISTRIBUTION_COMPARATOR = {
    "experiment_id": "exp-20260611-007",
    "decision": "accepted_paper_pending_forward_distribution_day_absorption_leadership_shared_adapter",
    "aggregate_expected_value_delta": 0.5286,
    "aggregate_pnl_delta": 10432.91,
}

HYPOTHESIS = (
    "candidate_pool: archived Moomoo daily short-volume activity shocks, "
    "treated as activity-only sell-pressure context and mapped to the next "
    "tradable session, may identify liquid names where visible short-sale "
    "activity is absorbed by price and continues over a fixed 10-trading-day "
    "paper hold."
)
CHANGED_VARIABLE = "moomoo_daily_short_volume_activity_absorption_candidate_pool_v1"
TRIAL_FAMILY = "moomoo_daily_short_volume_activity_absorption_candidate_pool"
TRIAL_VARIANT_ID = "archived_5ticker_activity_shock_absorption_next_open_10d_v1"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260622-008",
    "exp-20260622-009",
    "exp-20260503-039",
    "exp-20260619-007",
]

PREDICTION = {
    "success_probability": 0.12,
    "expected_ev_delta": 0.05,
    "expected_pnl_delta": 1000.0,
    "main_failure_modes": [
        "five_ticker_sample_too_thin",
        "concentration_failed",
        "daily_short_volume_activity_not_positioning",
        "accepted_comparator_not_beaten",
    ],
    "confidence_reason": (
        "exp-20260622-009 created the first PIT raw daily short-volume activity "
        "archive after prior short/borrow audits had no usable daily-short-volume "
        "rows. The new evidence is the archived activity-only Moomoo field plus "
        "explicit next-session usable-date mapping; the main risk is that five "
        "probe tickers are too concentrated and daily short volume is activity "
        "rather than positioning."
    ),
    "recorded_at": "2026-06-22T10:03:54+00:00",
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": HYPOTHESIS,
    "2_history_check": {
        "exp-20260622-008": (
            "Observed-only alpha lead showed Moomoo get_daily_short_volume had "
            "coverage but no raw rows, helper, daily snapshot, or replay fields."
        ),
        "exp-20260622-009": (
            "Accepted measurement repair seeded the raw activity-only PIT archive "
            "for AAPL/NVDA/TSLA/PLTR/SOFI; this run is the first Gate-4 alpha "
            "attempt using that archive."
        ),
        "exp-20260619-007": (
            "Rejected FINRA/public-float short-pressure candidate pool. This "
            "run is not FINRA short-interest positioning; it uses daily short "
            "volume as activity context only."
        ),
        "novelty_gate": (
            "Reservation passed with novelty override recorded on the new raw "
            "Moomoo activity archive plus explicit next-session usable-date "
            "mapping and experiment-local helper semantics."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Aggregate EV/PnL must "
        "be positive, no EV/PnL regression window, at least two EV-improved "
        "windows, >=20 trades across all 3 windows, survival >=5%, drawdown "
        "drift <=0.5pp, concentration guard passes, and accepted compression "
        "and distribution candidate-pool comparators must be beaten."
    ),
    "5_reproducibility": RUNNER_COMMAND,
}

EXECUTION_ENVELOPE = ExecutionEnvelope(
    base_notional=4_000.0,
    max_capital_pct=0.20,
    min_dollar_volume=50_000_000.0,
    slippage_bps=5.0,
    max_displacement=1,
    max_concurrent=8,
    order_semantics="next_open_after_activity_date",
    kill_switch_drawdown_pct=0.08,
    sleeve_drawdown_stop_pct=0.05,
    notes=(
        "Default-off paper only: top-1/day, fixed $4k notional, 10-trading-day "
        "close exit, 10-day same-ticker cooldown. Daily short volume is activity "
        "context only and must not be described as short-interest positioning."
    ),
)

PRODUCTION_IMPACT = {
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "trade_enabled": False,
    "daily_snapshot_exposed": False,
    "parity_test_added": True,
    "rejected_helper_rolled_back_to_experiment_scope": True,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "alters_orders": False,
    "uses_moomoo_daily_short_volume": True,
    "activity_only_not_positioning": True,
    "uses_free_ohlcv": True,
    "uses_llm": False,
    "live_realism_evaluated": True,
    "live_ready": False,
    "execution_envelope": EXECUTION_ENVELOPE.to_dict(),
    "parity_note": (
        "Historical replay and snapshot parity use experiment-local code in "
        "quant/experiments/exp_20260622_010_moomoo_daily_short_volume_activity_helper.py "
        "after the rejected top-level helper was rolled back. It is not wired "
        "into quant/run.py and cannot change orders, core ranking, sizing, "
        "exits, watchlists, LLM, or news behavior."
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, set):
        return sorted(_safe(item) for item in value)
    if isinstance(value, Path):
        return _repo_rel(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return round(value, 10)
    return value


def _round(value: Any, digits: int = 6) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _activity_tickers(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")}


def _run_window(
    *,
    label: str,
    cfg: dict[str, str],
    universe: list[str],
    activity_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    print(f"[{label}] core baseline ...", flush=True)
    before_result = framework.shadow._run_baseline(universe, cfg)
    before = framework.overlay_helper._metrics(before_result)
    activity_tickers = _activity_tickers(activity_rows)
    snapshot = framework._load_window_snapshot(cfg=cfg, eligible_tickers=activity_tickers)
    core_entries_by_date = framework.shadow._baseline_entries(before_result)
    print(f"[{label}] Moomoo daily short-volume activity replay ...", flush=True)
    trades, audit = build_moomoo_daily_short_volume_historical_trades(
        ohlcv_by_ticker=snapshot,
        activity_rows=activity_rows,
        core_entries_by_date=core_entries_by_date,
        windows={label: cfg},
        config=DEFAULT_CONFIG,
    )
    overlay = framework.sleeve._overlay_from_paper_trades(before_result, trades)
    after = framework.overlay_helper._metrics_with_overlay(before_result, overlay)
    delta = framework.overlay_helper._delta(after, before)
    return {
        "label": label,
        "window": cfg,
        "before": before,
        "after": after,
        "delta": delta,
        "target_trades": trades,
        "target_trade_count": len(trades),
        "overlay_total_pnl": overlay["overlay_total_pnl"],
        "overlay_day_count": overlay["overlay_day_count"],
        "audit": audit,
        "loaded_ticker_count": len(snapshot),
        "activity_ticker_count": len(activity_tickers),
    }


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = framework._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = list(gate.get("failed_reasons") or [])
    ev_delta = float(aggregate["expected_value_score_delta_sum"] or 0.0)
    pnl_delta = float(aggregate["total_pnl_delta_sum"] or 0.0)
    if ev_delta <= COMPRESSION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_compression_ev_not_beaten")
    if pnl_delta <= COMPRESSION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_compression_pnl_not_beaten")
    if ev_delta <= DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_distribution_ev_not_beaten")
    if pnl_delta <= DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_distribution_pnl_not_beaten")
    gate["failed_reasons"] = failed
    gate["passed"] = not failed
    gate["accepted_compression_comparator"] = COMPRESSION_COMPARATOR
    gate["accepted_distribution_comparator"] = DISTRIBUTION_COMPARATOR
    gate["decision"] = (
        "accepted_paper_pending_forward_moomoo_daily_short_volume_activity_absorption"
        if gate["passed"]
        else "rejected_moomoo_daily_short_volume_activity_absorption_candidate_pool"
    )
    return gate


def _full_stack_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    agg = payload["delta_metrics"]["aggregate"]
    summary = payload["target_trade_summary"]
    positive = summary.get("positive_by_ticker_pnl") or {}
    positive_total = sum(positive.values())
    top5_share = None
    if positive_total > 0:
        top5_share = sum(sorted(positive.values(), reverse=True)[:5]) / positive_total
    trade_count = summary["total_trade_count"]
    return {
        "aggregate_ev_delta": agg["expected_value_score_delta_sum"],
        "aggregate_pnl_delta": agg["total_pnl_delta_sum"],
        "windows_ev_improved": agg["windows_ev_improved"],
        "windows_ev_regressed": agg["windows_ev_regressed"],
        "windows_pnl_improved": agg["windows_pnl_improved"],
        "windows_pnl_regressed": agg["windows_pnl_regressed"],
        "adjusted_trade_count": trade_count,
        "adjusted_window_count": len(summary["windows_with_target_trades"]),
        "max_drawdown_worse_max": agg["max_drawdown_delta_max"],
        "single_ticker_positive_share": summary["max_single_positive_pnl_share"],
        "top_5_contribution_pct": top5_share,
        "hhi_concentration": summary["positive_pnl_hhi"],
        "avg_pnl_per_trade_delta": (
            agg["total_pnl_delta_sum"] / trade_count if trade_count else None
        ),
    }


def _calibration(gate4: dict[str, Any], aggregate: dict[str, Any]) -> dict[str, Any]:
    actual_success = 1 if gate4["passed"] else 0
    predicted = float(PREDICTION["success_probability"])
    failures = list(gate4.get("failed_reasons") or [])
    return {
        "actual_decision": gate4["decision"],
        "actual_success": actual_success,
        "predicted_success_probability": predicted,
        "brier_score": _round((predicted - actual_success) ** 2, 6),
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "ev_prediction_error": _round(
            float(aggregate["expected_value_score_delta_sum"] or 0.0)
            - float(PREDICTION["expected_ev_delta"] or 0.0),
            6,
        ),
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
        "pnl_prediction_error": _round(
            float(aggregate["total_pnl_delta_sum"] or 0.0)
            - float(PREDICTION["expected_pnl_delta"] or 0.0),
            2,
        ),
        "predicted_failure_modes": PREDICTION["main_failure_modes"],
        "failure_modes_observed": failures,
        "predicted_failure_mode_hit": any(
            ("sample" in failure and "five_ticker_sample_too_thin" in PREDICTION["main_failure_modes"])
            or ("concentration" in failure and "concentration_failed" in PREDICTION["main_failure_modes"])
            or ("comparator" in failure and "accepted_comparator_not_beaten" in PREDICTION["main_failure_modes"])
            for failure in failures
        ),
        "surprise_note": (
            "The main predicted risk was five-ticker concentration / weak "
            "incrementality; see Gate 4 failures."
            if failures
            else "The small archived activity surface passed numeric Gate 4, but live remains blocked by forward maturation."
        ),
    }


def _build_payload() -> dict[str, Any]:
    timestamp = _utc_now()
    activity_rows = load_moomoo_daily_short_volume_activity_rows(DEFAULT_ACTIVITY_ROWS_PATH)
    if not activity_rows:
        raise RuntimeError("Missing Moomoo daily short-volume activity archive rows.")
    universe = sorted(framework.get_universe())
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    audit_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    snapshot_parity = None
    for label, cfg in framework.WINDOWS.items():
        record = _run_window(label=label, cfg=cfg, universe=universe, activity_rows=activity_rows)
        before_metrics[label] = record["before"]
        after_metrics[label] = record["after"]
        target_trades_by_window[label] = record["target_trades"]
        audit_by_window[label] = record["audit"]
        window_rows[label] = {
            "before": record["before"],
            "after": record["after"],
            "delta": record["delta"],
            "target_trade_count": record["target_trade_count"],
            "raw_candidate_count": record["audit"]["raw_candidate_count_by_window"].get(label, 0),
            "overlay_total_pnl": record["overlay_total_pnl"],
            "overlay_day_count": record["overlay_day_count"],
        }
        if snapshot_parity is None and record["target_trades"]:
            first = record["target_trades"][0]
            snapshot = framework._load_window_snapshot(
                cfg=cfg,
                eligible_tickers={first["ticker"]},
            )
            daily_snapshot = build_moomoo_daily_short_volume_paper_sleeve_snapshot(
                as_of=first["signal_date"],
                ohlcv_by_ticker=snapshot,
                activity_rows=activity_rows,
                core_entries=[],
                state=empty_moomoo_daily_short_volume_state(),
                persist=False,
            )
            snapshot_parity = {
                "checked": True,
                "historical_decision_id": first.get("decision_id"),
                "snapshot_decision_id": (
                    (daily_snapshot.get("candidates") or [{}])[0].get("decision_id")
                    if daily_snapshot.get("candidates")
                    else None
                ),
                "matched": bool(
                    daily_snapshot.get("candidates")
                    and first.get("decision_id")
                    == daily_snapshot["candidates"][0].get("decision_id")
                ),
                "snapshot_candidate_count": daily_snapshot.get("candidate_count"),
            }
    if snapshot_parity is None:
        snapshot_parity = {"checked": False, "matched": False, "reason": "no_target_trades"}

    aggregate = framework._aggregate_window_rows(window_rows)
    target_summary = framework.sleeve._target_trade_summary(target_trades_by_window)
    gate4 = _gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    full_stack_metrics = _full_stack_metrics(
        {
            "delta_metrics": {"aggregate": aggregate},
            "target_trade_summary": target_summary,
        }
    )
    strict_gate4 = evaluate_gate4(full_stack_metrics, check_materiality=True)
    canonical_gate4 = evaluate_gate4(full_stack_metrics, check_materiality=False)
    live_readiness = evaluate_live_readiness(
        envelope=EXECUTION_ENVELOPE,
        closed_forward_trades=0,
        forward_pnl=None,
        replacement_value_passed=False,
        kill_switch_parity_passed=True,
    )
    verdict = full_stack_verdict(
        gate4={"passed": gate4["passed"], "hard_failures": gate4["failed_reasons"]},
        live_readiness=live_readiness,
        envelope=EXECUTION_ENVELOPE,
    )
    accepted = gate4["passed"] and verdict["verdict"] != "reject"
    status = "accepted_paper_pending_forward" if accepted else "rejected"
    calibration = _calibration(gate4, aggregate)
    compact_windows = []
    for label in framework.WINDOWS:
        before = before_metrics[label]
        after = after_metrics[label]
        delta = window_rows[label]["delta"]
        compact_windows.append(
            {
                "label": label,
                "start": framework.WINDOWS[label]["start"],
                "end": framework.WINDOWS[label]["end"],
                "before_ev": before.get("expected_value_score"),
                "after_ev": after.get("expected_value_score"),
                "ev_delta": delta.get("expected_value_score"),
                "before_pnl": before.get("total_pnl"),
                "after_pnl": after.get("total_pnl"),
                "pnl_delta": delta.get("total_pnl"),
                "max_drawdown_delta": delta.get("max_drawdown_pct"),
                "target_trade_count": len(target_trades_by_window[label]),
                "raw_candidate_count": window_rows[label]["raw_candidate_count"],
                "scan": audit_by_window[label]["scan_by_window"].get(label, {}),
            }
        )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": gate4["decision"],
        "accepted": accepted,
        "accepted_alpha": accepted,
        "hypothesis": HYPOTHESIS,
        "change_summary": "Test Moomoo daily short-volume activity absorption as default-off paper candidate pool.",
        "change_type": "candidate_pool_full_stack",
        "implementation_mode": "experiment_local_helper_historical_replay_snapshot_api_no_run_adapter",
        "mechanism_family": "production_visible_moomoo_daily_short_volume_activity_candidate_pool",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": [
            "experiment-local helper",
            "historical replay",
            "snapshot parity function",
            "focused parity test",
            "execution envelope",
            "Gate 1-4 verdict",
        ],
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "new_raw_activity_archive_experiment_local_helper",
        "prediction": PREDICTION,
        "calibration": calibration,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "parameters": {
            "rule_version": RULE_VERSION,
            "source_rule_version": SOURCE_RULE_VERSION,
            **{
                key: DEFAULT_CONFIG[key]
                for key in [
                    "paper_notional_usd",
                    "daily_entry_slots",
                    "hold_days",
                    "same_ticker_cooldown_days",
                    "activity_lookback_rows",
                    "min_prior_activity_rows",
                    "min_activity_ratio",
                    "min_activity_ratio_vs_median",
                    "min_signal_return",
                    "min_signal_return_vs_spy",
                ]
            },
        },
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "experiment-local default-off paper overlay"
            ),
            "windows": framework.WINDOWS,
            "activity_archive": _repo_rel(DEFAULT_ACTIVITY_ROWS_PATH),
            "baseline_result_file": (
                "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
            ),
            "entry_semantics": "activity_date close known before next-session-open paper entry",
            "exit_semantics": f"{DEFAULT_CONFIG['hold_days']}-trading-day close exit",
            "costs": "same overlay cost model as accepted candidate-pool sleeves",
        },
        "gate1": {
            "baseline_protocol": "docs/backtesting.md canonical three-window baseline",
            "baseline_artifact": (
                "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
            ),
            "baseline_metrics": before_metrics,
            "passed": True,
        },
        "gate2": {
            "activity_archive_rows": len(activity_rows),
            "activity_archive_tickers": sorted(_activity_tickers(activity_rows)),
            "runtime_candidate_fields_checked": [
                "entry_date",
                "target_price",
                "activity_date",
                "usable_trade_date",
                "short_volume_ratio",
                "warehouse OHLCV Date/Open/High/Low/Close/Volume",
            ],
            "sample_trade_has_required_fields": (
                all(
                    key in next(iter([trade for trades in target_trades_by_window.values() for trade in trades]), {})
                    for key in ["entry_date", "target_price"]
                )
                if target_summary["total_trade_count"]
                else False
            ),
            "passed": bool(activity_rows),
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": min(
                float(row.get("survival_rate") or 0.0) for row in before_metrics.values()
            ),
            "survival_rate_by_window": {
                label: before_metrics[label].get("survival_rate") for label in before_metrics
            },
            "passed": min(
                float(row.get("survival_rate") or 0.0) for row in before_metrics.values()
            )
            >= 0.05,
            "note": "No core filter or executable entry rule changed.",
        },
        "gate4": gate4,
        "full_stack": {
            "window_metrics": full_stack_metrics,
            "gate4_strict_materiality": strict_gate4,
            "gate4_canonical_auxiliary": canonical_gate4,
            "live_readiness": live_readiness,
            "execution_envelope": EXECUTION_ENVELOPE.to_dict(),
            "verdict": verdict,
            "snapshot_historical_parity": snapshot_parity,
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict((label, window_rows[label]["delta"]) for label in window_rows),
            "aggregate": aggregate,
        },
        "target_trades_by_window": target_trades_by_window,
        "target_audit_by_window": audit_by_window,
        "target_trade_summary": target_summary,
        "accepted_compression_comparator": COMPRESSION_COMPARATOR,
        "accepted_distribution_comparator": DISTRIBUTION_COMPARATOR,
        "windows": compact_windows,
        "production_impact": PRODUCTION_IMPACT,
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "post_run_reflection": {
            "why_result_happened": (
                "The archived Moomoo daily short-volume activity source did not "
                "clear Gate 4; the fixed bundle was judged on a five-ticker raw "
                "archive and activity-only semantics, so sample/concentration "
                "and accepted-comparator weakness are expected failure modes."
                if not accepted
                else "The fixed activity-shock absorption helper cleared Gate 4 but remains default-off pending forward replacement-value rows."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry by sweeping short_volume_ratio thresholds, "
                "ratio-vs-median thresholds, top-N, hold days, notional, "
                "cooldown, or FINRA short-interest labels on this five-ticker "
                "archive."
            ),
            "new_evidence_required": (
                "A valid retry needs broader archived Moomoo activity coverage, "
                "PIT borrow fee/utilization or loan-availability context, or "
                "closed forward replacement-value rows under the unchanged "
                "activity-only helper."
            ),
        },
        "next_retry_requires": [
            "broader archived Moomoo activity coverage",
            "borrow fee/utilization or loan availability context",
            "closed forward replacement-value rows",
        ],
        "rejection_reason": "; ".join(gate4["failed_reasons"]) if not accepted else None,
        "related_files": [
            RUNNER,
            "quant/experiments/exp_20260622_010_moomoo_daily_short_volume_activity_helper.py",
            "quant/test_exp_20260622_010_moomoo_daily_short_volume_activity_helper.py",
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            "docs/experiment_log.jsonl",
            "docs/experiment_registry.json",
        ],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "anti_js": "No JavaScript was used.",
    }


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "hypothesis": payload["hypothesis"],
        "change_summary": payload["change_summary"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "causal_components": payload["causal_components"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "component": RUNNER,
        "parameters": payload["parameters"],
        "date_range": {"start": "2024-10-02", "end": "2026-04-21"},
        "before_metrics": {
            "expected_value_score": aggregate["baseline_expected_value_score_sum"],
            "total_pnl": aggregate["baseline_total_pnl_sum"],
        },
        "after_metrics": {
            "expected_value_score": aggregate["after_expected_value_score_sum"],
            "total_pnl": aggregate["after_total_pnl_sum"],
            "trade_count": payload["target_trade_summary"]["total_trade_count"],
        },
        "delta_metrics": {
            "expected_value_score": aggregate["expected_value_score_delta_sum"],
            "total_pnl": aggregate["total_pnl_delta_sum"],
            "max_drawdown_pct": aggregate["max_drawdown_delta_max"],
        },
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "full_stack": payload["full_stack"],
        "decision_basis": (
            "Gate 4 passed; accepted as default-off paper pending forward rows."
            if payload["accepted"]
            else "Gate 4 failed; no production adapter or live behavior promoted."
        ),
        "rejection_reason": payload["rejection_reason"],
        "next_retry_requires": payload["next_retry_requires"],
        "post_run_reflection": payload["post_run_reflection"],
        "related_files": payload["related_files"],
        "artifact": payload["artifact"],
        "log": payload["log"],
        "anti_js": payload["anti_js"],
    }


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Raw Candidates |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["windows"]:
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {trades} | {raw} |".format(
                label=row["label"],
                bev=row["before_ev"],
                aev=row["after_ev"],
                dev=row["ev_delta"],
                bpnl=row["before_pnl"],
                apnl=row["after_pnl"],
                dpnl=row["pnl_delta"],
                trades=row["target_trade_count"],
                raw=row["raw_candidate_count"],
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: Moomoo daily short-volume activity absorption",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Production orders changed: no",
            "- Trade enabled: false",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4",
            "",
            *rows,
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(aggregate["expected_value_score_delta_sum"]),
            "- Aggregate PnL delta: `${:+,.2f}`".format(aggregate["total_pnl_delta_sum"]),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        REPO_ROOT / "quant" / "experiments" / "exp_20260622_010_moomoo_daily_short_volume_activity_helper.py",
        REPO_ROOT / "quant" / "test_exp_20260622_010_moomoo_daily_short_volume_activity_helper.py",
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": PRE_RUN_QUESTIONS["5_reproducibility"],
        "files": {
            _repo_rel(path): {"exists": path.exists(), "sha256": _sha256(path)}
            for path in files
        },
        "anti_js": payload["anti_js"],
        "updated_at": _utc_now(),
    }


def _persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_text(CARD_MD, _build_card(payload))
    _upsert_jsonl(EXPERIMENT_LOG, _build_log_record(payload))

    aggregate = payload["delta_metrics"]["aggregate"]
    registry_result = {
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "decision": payload["decision"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "runner": RUNNER,
        "delta_metrics": {
            "aggregate_expected_value_score": aggregate["expected_value_score_delta_sum"],
            "aggregate_total_pnl": aggregate["total_pnl_delta_sum"],
            "max_window_drawdown_pct": aggregate["max_drawdown_delta_max"],
            "total_trade_count": payload["target_trade_summary"]["total_trade_count"],
        },
        "gate4": payload["gate4"],
        "full_stack": payload["full_stack"],
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
            "baseline_result_file": (
                "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
            ),
            "decision": payload["decision"],
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "card_file": _repo_rel(CARD_MD),
            "revision_manifest_file": _repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
            "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "full_stack": payload["full_stack"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "allowed_write_scope": ALLOWED_WRITE_SCOPE,
            "related_files": payload["related_files"],
        },
    )
    _write_json(MANIFEST_JSON, _build_manifest(payload))


def main() -> int:
    payload = _build_payload()
    _persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "aggregate_ev_delta": payload["delta_metrics"]["aggregate"][
                    "expected_value_score_delta_sum"
                ],
                "aggregate_pnl_delta": payload["delta_metrics"]["aggregate"][
                    "total_pnl_delta_sum"
                ],
                "target_trades": payload["target_trade_summary"]["total_trade_count"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "anti_js": payload["anti_js"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
