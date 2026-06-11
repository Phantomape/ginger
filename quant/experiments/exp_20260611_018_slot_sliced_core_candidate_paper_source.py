"""exp-20260611-018: slot-sliced core candidate paper source.

Replay-only alpha search. This tests one internal, production-visible
candidate-pool variable: core entry candidates that pass all filters and sizing
but are deferred only because the entry plan has no available slot. The replay
admits the top slot-sliced candidate per signal day into a default-off paper
source with next-open entry, 10-trading-day exit, costs, and cooldown.

No production code, shared adapter, live/default orders, core ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Any

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework


EXPERIMENT_ID = "exp-20260611-018"
STEM = "slot_sliced_core_candidate_paper_source"
TRIAL_FAMILY = "slot_sliced_core_candidate_paper_source"
TRIAL_VARIANT_ID = "slot_sliced_top1_next_open_10d_v1"
CHANGED_VARIABLE = "slot_sliced_core_candidate_default_off_paper_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = framework.REPO_ROOT
QUANT_DIR = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from backtester import BacktestEngine  # noqa: E402
from convergence import compute_expected_value_score  # noqa: E402
from data_layer import get_universe  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


shadow = framework.shadow
overlay_helper = framework.overlay_helper
sleeve = framework.sleeve

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260611_018_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 12
ELIGIBLE_STRATEGIES = {"trend_long", "breakout_long", "earnings_event_long"}

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

ACCEPTED_ALLOCATOR_COMPARATOR = {
    "experiment_id": "exp-20260611-005",
    "decision": "accepted_lagged_consensus_shared_allocator_source_extension",
    "expected_value_score_delta_sum": 2.1849,
    "total_pnl_delta_sum": 40397.21,
    "by_window": {
        "late_strong": {"ev": 0.9092, "pnl": 9431.68},
        "mid_weak": {"ev": 0.6352, "pnl": 11133.95},
        "old_thin": {"ev": 0.6405, "pnl": 19831.58},
    },
}

PREDICTION = {
    "success_probability": 0.24,
    "expected_ev_delta": 0.25,
    "expected_pnl_delta": 4000.0,
    "main_failure_modes": [
        "already_correctly_ranked_out",
        "old_thin_regression",
        "drawdown_worse",
        "slot_pressure_overlap",
        "accepted_allocator_comparator_not_beaten",
    ],
    "confidence_reason": (
        "The source uses only candidates already passing core gates and "
        "production parity surfaces, so noise risk is lower than broad OHLCV "
        "mining. Prior slot/ranking work is crowded and the accepted allocator "
        "is a hard comparator, so odds remain moderate-low."
    ),
    "recorded_at": "2026-06-11T15:07:31+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_no_live_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "live_realism_evaluated": True,
    "live_ready": False,
    "uses_llm": False,
    "uses_free_internal_candidate_events": True,
    "execution_envelope": {
        "base_notional": BASE_NOTIONAL_USD,
        "max_capital_pct": 0.32,
        "max_concurrent": 8,
        "max_displacement": 0,
        "min_dollar_volume": None,
        "slippage_bps": 5.0,
        "order_semantics": "next_open_paper_only",
        "kill_switch_drawdown_pct": None,
        "sleeve_drawdown_stop_pct": None,
        "complete": False,
        "missing": [
            "min_dollar_volume",
            "kill_switch_drawdown_pct",
            "sleeve_drawdown_stop_pct",
            "shared_daily_snapshot_adapter",
        ],
        "notes": (
            "Default-off paper only. Source is one slot-sliced core candidate "
            "per day, fixed $4,000 notional, 10-trading-day hold, 12-trading-day "
            "same-ticker cooldown, and no displacement of live/core slots."
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result would "
        "remain only a replay lead until a shared default-off helper consumes "
        "the same production/backtest entry-candidate review surface, filters "
        "only decision=slot_sliced rows, uses identical top-1/day, next-open "
        "paper entry, 10-day exit, costs, cooldown, and exposes daily snapshots "
        "with trade_enabled=false."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool/allocation: core candidates that pass all entry gates "
        "and sizing but are slot-sliced may carry residual replacement value as "
        "a default-off paper source because they are already production-visible "
        "and ranked by the accepted core policy."
    ),
    "2_history_check": {
        "exp-20260503-012": (
            "Earlier slot-sliced collision ranking work predates the current "
            "accepted paper allocator and does not isolate a default-off paper "
            "source from current entry_candidate_events."
        ),
        "exp-20260505-005": (
            "Non-positionable candidate planning was a core entry-planning "
            "change; this run does not change core planning and uses only "
            "already positionable slot-sliced rows."
        ),
        "exp-20260517-009": (
            "Accepted ample-slot stock rank-1 top-up addressed live core "
            "capacity. This experiment tests the opposite state: no available "
            "slot, default-off paper only."
        ),
        "exp-20260611-005": (
            "Current binding accepted default-off allocator comparator: "
            "aggregate EV +2.1849 and PnL +$40,397.21."
        ),
        "exp-20260611-010": (
            "Allocator source pruning failed because source-level attribution "
            "lost old_thin coverage. This run avoids source rank/prune changes."
        ),
    },
    "3_single_causal_variable": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Pass only if "
        "aggregate EV/PnL improve, no EV/PnL window regresses, target sample "
        ">=20 across all 3 windows, survival >=5%, drawdown drift <=0.5pp, "
        "concentration passes, and the accepted exp-20260611-005 allocator "
        "aggregate plus per-window EV/PnL comparator is beaten. Positive "
        "replay-only evidence is not accepted production alpha."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260611_018_slot_sliced_core_candidate_paper_source.py"
    ),
}


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _safe(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {str(key): _safe(value) for key, value in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [_safe(value) for value in payload]
    if isinstance(payload, set):
        return sorted(_safe(value) for value in payload)
    if isinstance(payload, Counter):
        return dict(payload)
    if isinstance(payload, Path):
        return str(payload)
    if isinstance(payload, float):
        if math.isnan(payload) or math.isinf(payload):
            return None
        return round(payload, 10)
    return payload


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(_safe(payload), handle, ensure_ascii=True, indent=2, sort_keys=True)
        handle.write("\n")


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
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _round(value: Any, digits: int = 6) -> float | None:
    return framework._round(value, digits)


def _configure_sleeve_globals() -> None:
    sleeve.EXPERIMENT_ID = EXPERIMENT_ID
    sleeve.STEM = STEM
    sleeve.TRIAL_FAMILY = TRIAL_FAMILY
    sleeve.CHANGED_VARIABLE = CHANGED_VARIABLE
    sleeve.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    sleeve.HOLD_DAYS = HOLD_DAYS
    sleeve.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    sleeve.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    sleeve.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    sleeve.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    sleeve.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    sleeve.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    sleeve.OUT_DIR = OUT_DIR
    sleeve.OUT_JSON = OUT_JSON
    sleeve.LOG_JSON = LOG_JSON
    sleeve.TICKET_JSON = TICKET_JSON
    sleeve.CARD_MD = CARD_MD
    sleeve.EXPERIMENT_LOG = EXPERIMENT_LOG


def _run_baseline_with_candidate_events(universe: list[str], cfg: dict[str, str]) -> dict[str, Any]:
    engine = BacktestEngine(
        universe=universe,
        start=cfg["start"],
        end=cfg["end"],
        config={"REGIME_AWARE_EXIT": True},
        replay_llm=False,
        replay_news=False,
        data_dir=str(REPO_ROOT / "data"),
        ohlcv_snapshot_path=str(REPO_ROOT / cfg["snapshot"]),
        include_entry_candidate_events=True,
        include_oracle_diagnostics=False,
    )
    result = engine.run()
    result["expected_value_score"] = compute_expected_value_score(result)
    return result


def _candidate_score(event: dict[str, Any]) -> float:
    signal = event.get("signal_snapshot") or {}
    rank = float(event.get("candidate_rank") or 999.0)
    tqs = float(signal.get("trade_quality_score") or 0.0)
    confidence = float(signal.get("confidence_score") or 0.0)
    rr = float(signal.get("risk_reward_ratio") or 0.0)
    return round((1000.0 / max(rank, 1.0)) + 20.0 * tqs + 5.0 * confidence + rr, 6)


def _candidate_rows_for_window(
    *,
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = shadow._baseline_entries(before_result)
    candidates: list[dict[str, Any]] = []
    scan = {
        "entry_candidate_event_count": 0,
        "slot_sliced_event_count": 0,
        "eligible_slot_sliced_event_count": 0,
        "rejection_counts": Counter(),
        "strategy_counts": Counter(),
        "rule_version": RULE_VERSION,
    }
    for event in before_result.get("entry_candidate_events") or []:
        scan["entry_candidate_event_count"] += 1
        if event.get("decision") != "slot_sliced":
            continue
        scan["slot_sliced_event_count"] += 1
        strategy = str(event.get("strategy") or "")
        scan["strategy_counts"][strategy] += 1
        if strategy not in ELIGIBLE_STRATEGIES:
            scan["rejection_counts"]["ineligible_strategy"] += 1
            continue
        signal = event.get("signal_snapshot") or {}
        sizing = signal.get("sizing") or {}
        shares = sizing.get("shares_to_buy")
        try:
            shares_value = float(shares)
        except (TypeError, ValueError):
            shares_value = 0.0
        if shares_value <= 0:
            scan["rejection_counts"]["non_positionable"] += 1
            continue
        if signal.get("target_price") is None:
            scan["rejection_counts"]["missing_target_price"] += 1
            continue
        signal_date = str(event.get("date") or "")[:10]
        ticker = str(event.get("ticker") or "").upper()
        same_day_entries = entries_by_date.get(signal_date, [])
        row = {
            "date": signal_date,
            "ticker": ticker,
            "source": "SLOT_SLICED_CORE_CANDIDATE_PAPER",
            "candidate_score": _candidate_score(event),
            "candidate_rank": event.get("candidate_rank"),
            "strategy": strategy,
            "available_slots_at_entry_loop": event.get("available_slots_at_entry_loop"),
            "slot_sliced_reason": (event.get("details") or {}).get("reason", "slot_sliced"),
            "signal_entry_price": signal.get("entry_price"),
            "signal_stop_price": signal.get("stop_price"),
            "signal_target_price": signal.get("target_price"),
            "signal_risk_reward_ratio": signal.get("risk_reward_ratio"),
            "signal_trade_quality_score": signal.get("trade_quality_score"),
            "signal_confidence_score": signal.get("confidence_score"),
            "signal_target_mult_used": signal.get("target_mult_used"),
            "signal_regime_exit_bucket": signal.get("regime_exit_bucket"),
            "signal_regime_exit_score": signal.get("regime_exit_score"),
            "sizing_shares_to_buy": shares,
            "sizing_risk_pct": sizing.get("risk_pct"),
            "sizing_risk_multipliers": sizing.get("risk_multipliers"),
            "sector": signal.get("sector") or "Unknown",
            "same_day_ab_entry_count": len(same_day_entries),
            "same_day_ab_overlap": bool(same_day_entries),
            "same_ticker_ab_overlap": any(
                str(trade.get("ticker") or "").upper() == ticker
                for trade in same_day_entries
            ),
            "rule_version": RULE_VERSION,
            "known_at": "after_signal_day_close_before_next_open_paper_entry",
            "uses_llm": False,
            "trade_enabled": False,
        }
        candidates.append(row)
        scan["eligible_slot_sliced_event_count"] += 1
    candidates.sort(
        key=lambda row: (
            row["date"],
            int(row.get("candidate_rank") or 999999),
            -float(row.get("candidate_score") or 0.0),
            -float(row.get("signal_trade_quality_score") or 0.0),
            -float(row.get("signal_confidence_score") or 0.0),
            row["ticker"],
        )
    )
    scan["rejection_counts"] = dict(sorted(scan["rejection_counts"].items()))
    scan["strategy_counts"] = dict(sorted(scan["strategy_counts"].items()))
    return candidates, scan


def _select_paper_trades(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    used_date_counts: Counter[str] = Counter()
    dates = shadow._trading_dates(snapshot)
    date_pos = {date_value: idx for idx, date_value in enumerate(dates)}
    next_allowed_pos_by_ticker: dict[str, int] = {}
    for row in candidates:
        signal_date = str(row.get("date") or "")[:10]
        ticker = str(row.get("ticker") or "").upper()
        pos = date_pos.get(signal_date)
        if pos is None:
            filtered.append({**row, "filter_reason": "missing_signal_date_position"})
            continue
        if row.get("same_ticker_ab_overlap"):
            filtered.append({**row, "filter_reason": "same_ticker_core_overlap"})
            continue
        if used_date_counts[signal_date] >= MAX_PAPER_TRADES_PER_DAY:
            filtered.append({**row, "filter_reason": "daily_top1_limit"})
            continue
        next_allowed = next_allowed_pos_by_ticker.get(ticker, -1)
        if pos < next_allowed:
            filtered.append({**row, "filter_reason": "same_ticker_cooldown"})
            continue
        trade = sleeve._paper_trade_from_candidate(snapshot, row)
        if trade is None:
            filtered.append({**row, "filter_reason": "missing_next_open_or_exit"})
            continue
        selected.append(trade)
        used_date_counts[signal_date] += 1
        next_allowed_pos_by_ticker[ticker] = pos + SAME_TICKER_COOLDOWN_DAYS
    return selected, filtered


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
    window_rows: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = framework._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = list(gate.get("failed_reasons") or [])
    comparator_regressions: list[str] = []
    if (
        aggregate["expected_value_score_delta_sum"]
        <= ACCEPTED_ALLOCATOR_COMPARATOR["expected_value_score_delta_sum"]
    ):
        failed.append("accepted_allocator_ev_comparator_not_beaten")
    if (
        aggregate["total_pnl_delta_sum"]
        <= ACCEPTED_ALLOCATOR_COMPARATOR["total_pnl_delta_sum"]
    ):
        failed.append("accepted_allocator_pnl_comparator_not_beaten")
    for label, row in window_rows.items():
        comparator = ACCEPTED_ALLOCATOR_COMPARATOR["by_window"][label]
        delta = row["delta"]
        if delta.get("expected_value_score", 0.0) <= comparator["ev"]:
            comparator_regressions.append(f"{label}_ev")
        if delta.get("total_pnl", 0.0) <= comparator["pnl"]:
            comparator_regressions.append(f"{label}_pnl")
    if comparator_regressions:
        failed.append("accepted_allocator_window_comparator_regression")
    gate.update(
        {
            "passed": not failed,
            "decision": (
                "positive_replay_lead_not_promoted_slot_sliced_core_candidate_source"
                if not failed
                else "rejected_slot_sliced_core_candidate_paper_source"
            ),
            "failed_reasons": failed,
            "accepted_allocator_comparator": ACCEPTED_ALLOCATOR_COMPARATOR,
            "comparator_regressions": comparator_regressions,
            "parity_test_added": False,
            "shared_adapter_module": "runner_local_replay_variant",
        }
    )
    return gate


def _build_payload() -> dict[str, Any]:
    _configure_sleeve_globals()
    timestamp = framework._utc_now()
    gate2_open_positions = sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(get_universe())
    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    filtered_candidates_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    raw_candidate_counts: "OrderedDict[str, int]" = OrderedDict()
    candidate_scan_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] core baseline with entry-candidate events")
        before_result = _run_baseline_with_candidate_events(universe, cfg)
        before = overlay_helper._metrics(before_result)
        snapshot = shadow._load_snapshot(str(cfg["snapshot"]))
        candidates, scan = _candidate_rows_for_window(before_result=before_result)
        selected_trades, filtered_candidates = _select_paper_trades(
            snapshot=snapshot,
            candidates=candidates,
        )
        overlay = sleeve._overlay_from_paper_trades(before_result, selected_trades)
        after = overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = overlay_helper._delta(after, before)

        before_metrics[label] = before
        after_metrics[label] = after
        target_trades_by_window[label] = selected_trades
        filtered_candidates_by_window[label] = filtered_candidates[:200]
        raw_candidate_counts[label] = len(candidates)
        candidate_scan_by_window[label] = scan
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected_trades),
            "raw_candidate_count": len(candidates),
            "slot_sliced_event_count": scan["slot_sliced_event_count"],
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = sleeve._aggregate(window_rows)
    target_summary = sleeve._target_trade_summary(target_trades_by_window)
    gate4 = _gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
        window_rows=window_rows,
    )
    passed = bool(gate4["passed"])
    status = "positive_replay_lead_not_promoted" if passed else "rejected"
    decision = gate4["decision"]
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    rationale = (
        "The slot-sliced core candidate source beat the strict Gate 4 and "
        "accepted allocator comparator, but it remains replay-only because no "
        "shared daily paper adapter was implemented."
        if passed
        else (
            "The slot-sliced core candidate source did not clear Gate 4 or the "
            "accepted allocator comparator. The accepted core/allocator stack "
            "appears to be ranking out these candidates for good reason or the "
            "paper overlay adds crowded slot-pressure exposure."
        )
    )
    brier = round((PREDICTION["success_probability"] - (1.0 if passed else 0.0)) ** 2, 6)
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "change_type": "default_off_paper_candidate_pool_replay_scout",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "production_visible_default_off_internal_candidate_pool",
        "nearby_prior_experiments": list(PRE_RUN_QUESTIONS["2_history_check"].keys()),
        "prior_trial_count": 4,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "production_visible_internal_candidate_pool",
        "prediction": PREDICTION,
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_gate4_passed": passed,
            "failure_modes_observed": gate4["failed_reasons"],
            "brier_score": brier,
            "predicted_failure_mode_hit": bool(gate4["failed_reasons"]),
        },
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window replay using the "
                "fixed OHLCV snapshots plus entry_candidate_events emitted by "
                "the same BacktestEngine entry planner."
            ),
            "windows": framework.WINDOWS,
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "oracle_diagnostics": False,
            "execution_model": (
                "Source uses only decision-time entry_candidate_events with "
                "decision=slot_sliced. Paper entry is next available open; exit "
                "is the close 10 trading days after signal with target-side sell "
                "slippage and ROUND_TRIP_COST_PCT."
            ),
        },
        "parameters": {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "eligible_strategies": sorted(ELIGIBLE_STRATEGIES),
            "selection_order": [
                "date",
                "candidate_rank_ascending",
                "candidate_score_descending",
                "trade_quality_score_descending",
                "confidence_score_descending",
                "ticker",
            ],
        },
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": f"{_repo_rel(OUT_JSON)}#before_metrics",
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "entry_candidate_events.date",
                "entry_candidate_events.decision",
                "entry_candidate_events.candidate_rank",
                "entry_candidate_events.signal_snapshot.entry_price",
                "entry_candidate_events.signal_snapshot.target_price",
                "entry_candidate_events.signal_snapshot.sizing.shares_to_buy",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": round(min_survival, 6),
            "signals_generated": {
                label: before_metrics[label].get("signals_generated")
                for label in before_metrics
            },
            "signals_survived": {
                label: before_metrics[label].get("signals_survived")
                for label in before_metrics
            },
            "survival_rate": {
                label: before_metrics[label].get("survival_rate")
                for label in before_metrics
            },
            "passed": min_survival >= 0.05,
            "note": (
                "No new core filter or entry rule was added. This is additive "
                "default-off paper sourcing from already generated slot-sliced "
                "candidate events, so core survival is unchanged."
            ),
        },
        "gate4": gate4,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict((label, row["delta"]) for label, row in window_rows.items()),
            "aggregate": aggregate,
        },
        "candidate_scan_by_window": candidate_scan_by_window,
        "raw_candidate_counts": raw_candidate_counts,
        "target_trades_by_window": target_trades_by_window,
        "filtered_candidates_sample_by_window": filtered_candidates_by_window,
        "target_trade_summary": target_summary,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "interpretation": rationale,
        "rejection_reason": None if passed else "; ".join(gate4["failed_reasons"]),
        "accepted_allocator_comparator": ACCEPTED_ALLOCATOR_COMPARATOR,
        "post_run_reflection": {
            "why_result_happened": rationale,
            "forbidden_near_neighbor_retry": (
                "Do not retry by sweeping slot-sliced rank cutoffs, strategy "
                "sets, TQS/confidence thresholds, top-N, hold days, cooldown, "
                "or paper notional on the same frozen windows."
            ),
            "new_evidence_required": (
                "Retry only with closed forward replacement-value rows from a "
                "shared daily slot-sliced paper adapter or a materially new "
                "production-visible displacement field."
            ),
        },
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _build_card(payload: dict[str, Any]) -> str:
    rows = []
    for label in framework.WINDOWS:
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {ev:+.4f} | ${pnl:+,.2f} | {dd:+.4f} | {trades} | {raw} |".format(
                label=label,
                ev=float(delta.get("expected_value_score") or 0.0),
                pnl=float(delta.get("total_pnl") or 0.0),
                dd=float(delta.get("max_drawdown_pct") or 0.0),
                trades=payload["gate4"].get("target_trade_count")
                if False
                else len(payload["target_trades_by_window"][label]),
                raw=payload["raw_candidate_counts"][label],
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Slot-Sliced Core Candidate Paper Source",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4",
            "",
            "| Window | dEV | dPnL | DD d | Target trades | Raw candidates |",
            "|---|---:|---:|---:|---:|---:|",
            *rows,
            "",
            f"- Aggregate EV delta: `{aggregate['expected_value_score_delta_sum']:+.4f}`",
            f"- Aggregate PnL delta: `${aggregate['total_pnl_delta_sum']:+,.2f}`",
            f"- Target trades: `{payload['target_trade_summary']['total_trade_count']}`",
            f"- Failed reasons: `{', '.join(payload['gate4']['failed_reasons']) or 'none'}`",
            "",
            "## Production Impact",
            "",
            (
                "Replay-only/default-off paper scout. No production orders, "
                "candidate ranking, sizing, exits, watchlist, LLM/news path, "
                "shared allocator, or run adapter changed."
            ),
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "status": payload["status"],
        "decision": payload["decision"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": "private_replay_scout",
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": [
            "entry_candidate_events",
            "slot_sliced_only_source",
            "top1_per_day",
            "next_open_paper_entry",
            "10d_paper_exit",
            "cooldown",
            "costs",
            "execution_envelope",
            "three_window_gate4",
        ],
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "backtest_protocol": payload["backtest_protocol"],
        "parameters": payload["parameters"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "target_trade_count": payload["target_trade_summary"]["total_trade_count"],
        "production_impact": payload["production_impact"],
        "accepted_allocator_comparator": ACCEPTED_ALLOCATOR_COMPARATOR,
        "post_run_reflection": payload["post_run_reflection"],
        "rejection_reason": payload["rejection_reason"],
        "related_files": payload["related_files"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "anti_js": "No JavaScript was used.",
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "production_accepted": False,
    }


def _update_ticket_and_registry(payload: dict[str, Any], log_record: dict[str, Any]) -> None:
    aggregate = payload["delta_metrics"]["aggregate"]
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "decision": payload["decision"],
        "summary": payload["interpretation"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": log_record["aggregate_expected_value_delta"],
        "aggregate_strategy_total_pnl_delta": log_record[
            "aggregate_strategy_total_pnl_delta"
        ],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(Path(__file__)): _sha256(Path(__file__)),
            _repo_rel(OUT_JSON): _sha256(OUT_JSON),
            _repo_rel(LOG_JSON): _sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): _sha256(TICKET_JSON),
            _repo_rel(CARD_MD): _sha256(CARD_MD),
        },
    }
    _write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    log_record = _build_log_record(payload)
    _write_json(LOG_JSON, log_record)
    _write_text(CARD_MD, _build_card(payload))
    _upsert_jsonl(EXPERIMENT_LOG, log_record)
    _update_ticket_and_registry(payload, log_record)
    _write_manifest(payload)


def main() -> None:
    payload = _build_payload()
    persist(payload)
    aggregate = payload["delta_metrics"]["aggregate"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
                "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
                "target_trades": payload["target_trade_summary"]["total_trade_count"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": _repo_rel(OUT_JSON),
            },
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
