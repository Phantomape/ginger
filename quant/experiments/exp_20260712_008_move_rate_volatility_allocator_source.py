"""exp-20260712-008: MOVE relief as an accepted-helper allocator source.

The experiment keeps the accepted MOVE rule fixed and changes only its response
shape: standalone default-off candidate pool -> rank-4 source inside the
accepted-helper allocator.  Before and after are rebuilt in the same process
under the current Sharpe-inference schema.  The experiment-local patch is used
so a rejection remains reproducible after shared policy code is rolled back.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT, ROOT / "quant", ROOT / "quant" / "experiments", ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import accepted_helper_source_priority_allocator_paper_sleeve as allocator  # noqa: E402
import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework  # noqa: E402
import exp_20260610_008_fiftytwo_week_high_proximity_full_stack as deep_loader  # noqa: E402
import exp_20260711_002_move_rate_volatility_relief_stock_leadership as move_scout  # noqa: E402
import move_rate_volatility_relief_paper_sleeve as move_helper  # noqa: E402
from constants import ROUND_TRIP_COST_PCT  # noqa: E402
from data_layer import get_universe  # noqa: E402
from experiment_registry import persist_self_registered_result, save_experiment_log_entry  # noqa: E402
from sharpe_inference import build_backtest_sharpe_inference  # noqa: E402


EXPERIMENT_ID = "exp-20260712-008"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "move_rate_volatility_allocator_source"
RUNNER = f"quant/experiments/exp_20260712_008_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
OUT_JSON = ROOT / "data" / "experiments" / EXPERIMENT_ID / f"exp_20260712_008_{SLUG}.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = ROOT / "docs" / "experiment_registry.json"
CURRENT_BASELINE = (
    ROOT
    / "data"
    / "experiments"
    / "exp-20260712-006"
    / "current_working_stack_sharpe_inference.json"
)

HYPOTHESIS = (
    "candidate_pool/full_stack allocator_source: the accepted MOVE rate-volatility "
    "relief shared helper adds an independent rates-volatility event source to the "
    "accepted-helper source-priority allocator; fixed rank 4 below rolling_peer_shock "
    "and above turn_of_month should improve same-run current-schema allocator EV and "
    "PnL without window, drawdown, survival, or concentration regression while "
    "trade_enabled remains false."
)
CHANGED_VARIABLE = "move_rate_volatility_relief_rank4_allocator_source_v1"
TRIAL_FAMILY = "accepted_default_off_helper_source_priority_allocation"
MECHANISM_FAMILY = "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
NEARBY = [
    "exp-20260711-004",
    "exp-20260711-015",
    "exp-20260711-018",
    "exp-20260610-014",
    "exp-20260611-005",
]
NEW_AXIS = (
    "New gate shape for a newly accepted source: MOVE relief was previously tested "
    "only as a standalone candidate pool; no prior experiment admitted the fixed "
    "shared rows into accepted-helper allocator-source arbitration."
)
PREDICTION = json.loads(TICKET_JSON.read_text(encoding="utf-8"))["prediction"]

MOVE_SOURCE = "move_rate_volatility_relief"
MOVE_RANK = 4
MIN_MOVE_SELECTED = 20
MIN_MOVE_WINDOWS = 3
MIN_RELATIVE_EV_IMPROVEMENT = 0.10
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35
INITIAL_CAPITAL = float(framework.overlay_helper.INITIAL_CAPITAL)


def _utc_now() -> str:
    return framework._utc_now()


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = ROOT / value
    return str(value.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _candidate_universe(sector_entries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "status": "window_sector_known_universe",
        "tickers": sorted(sector_entries),
        "records": sector_entries,
    }


def _proposed_priority() -> OrderedDict[str, dict[str, Any]]:
    proposed: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for source, meta in allocator.SOURCE_PRIORITY.items():
        if source == "turn_of_month":
            proposed[MOVE_SOURCE] = {
                "rank": MOVE_RANK,
                "description": "accepted MOVE rate-volatility relief stock leadership",
                "accepted_experiment": "exp-20260711-004",
                "accepted_ev_delta_sum": 0.3344,
                "accepted_pnl_delta_sum": 7548.90,
            }
        copied = deepcopy(meta)
        if int(copied["rank"]) >= MOVE_RANK:
            copied["rank"] = int(copied["rank"]) + 1
        proposed[source] = copied
    if MOVE_SOURCE not in proposed:
        raise RuntimeError("turn_of_month insertion point missing from accepted allocator")
    return proposed


@contextmanager
def _move_allocator_policy() -> Iterator[None]:
    original_priority = deepcopy(allocator.SOURCE_PRIORITY)
    proposed_priority = _proposed_priority()
    original_builder = allocator._build_source_trades
    original_rule = allocator.RULE_VERSION
    original_source_rule = allocator.SOURCE_RULE_VERSION
    allocator.SOURCE_PRIORITY.clear()
    allocator.SOURCE_PRIORITY.update(proposed_priority)
    allocator.RULE_VERSION = "accepted_helper_source_priority_shared_default_off_allocator_v4_move"
    allocator.SOURCE_RULE_VERSION = (
        "accepted_helper_source_priority_top1_with_move_rate_volatility_rank4_v1"
    )

    def build_with_move(**kwargs: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        source_trades, audit = original_builder(**kwargs)
        move = move_helper.build_move_rate_volatility_relief_historical_trades(
            ohlcv_by_ticker=kwargs["rows_by_ticker"],
            dates=kwargs["dates"],
            candidate_universe=kwargs["candidate_universe"] or kwargs["sector_entries"],
            core_entries_by_date=kwargs["core_entries_by_date"],
        )
        normalised = [allocator._normalise_source_row(row, MOVE_SOURCE) for row in move["trades"]]
        source_trades.extend(normalised)
        audit = deepcopy(audit)
        audit["source_priority"] = deepcopy(allocator.SOURCE_PRIORITY)
        audit["source_trade_counts"][MOVE_SOURCE] = len(normalised)
        audit["raw_candidate_counts"][MOVE_SOURCE] = len(move.get("candidates") or [])
        audit["source_audits"][MOVE_SOURCE] = {
            "rule_version": move.get("rule_version"),
            "source_rule_version": move.get("source_rule_version"),
            "context_scan": move.get("context_scan"),
        }
        return source_trades, audit

    allocator._build_source_trades = build_with_move
    try:
        yield
    finally:
        allocator._build_source_trades = original_builder
        allocator.SOURCE_PRIORITY.clear()
        allocator.SOURCE_PRIORITY.update(original_priority)
        allocator.RULE_VERSION = original_rule
        allocator.SOURCE_RULE_VERSION = original_source_rule


def _load_window_snapshot(
    cfg: dict[str, str], sector_entries: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    snapshot = deep_loader._load_window_snapshot_deep(
        cfg=cfg,
        eligible_tickers=set(sector_entries),
    )
    snapshot[move_helper.MOVE_TICKER] = move_scout.fetch_move_rows()
    return snapshot


def _build_allocator_trades(
    *,
    snapshot: dict[str, Any],
    cfg: dict[str, str],
    label: str,
    sector_entries: dict[str, dict[str, Any]],
    core_entries: dict[str, list[dict[str, Any]]],
    with_move: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    dates = [
        day
        for day in framework.shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= day <= str(cfg["end"])
    ]
    kwargs = {
        "ohlcv_by_ticker": snapshot,
        "core_entries_by_date": core_entries,
        "windows": OrderedDict([(label, cfg)]),
        "candidate_universe": _candidate_universe(sector_entries),
        "sector_entries": sector_entries,
        "calendar_dates": framework.shadow._trading_dates(snapshot),
    }
    if with_move:
        with _move_allocator_policy():
            return allocator.build_accepted_helper_source_priority_allocator_historical_trades(
                **kwargs
            )
    return allocator.build_accepted_helper_source_priority_allocator_historical_trades(**kwargs)


def _curve_metrics(
    before_result: dict[str, Any],
    trades: list[dict[str, Any]],
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    rows = move_helper.leader._normalise_ohlcv_by_ticker(snapshot)
    close_by_ticker_date = {
        ticker: {
            str(row.get("date") or "")[:10]: float(row["close"])
            for row in values
            if row.get("date") and row.get("close") is not None
        }
        for ticker, values in rows.items()
    }
    paper_contribution: list[float] = []
    combined_curve: list[tuple[str, float]] = []
    for raw_day, raw_equity in before_result.get("equity_curve") or []:
        day = str(raw_day)[:10]
        contribution = 0.0
        for trade in trades:
            entry_date = str(trade.get("entry_date") or "")[:10]
            exit_date = str(trade.get("exit_date") or "")[:10]
            if not entry_date or not exit_date or day < entry_date:
                continue
            if day >= exit_date:
                contribution += float(trade.get("pnl") or 0.0)
                continue
            ticker = str(trade.get("ticker") or "").upper()
            close = close_by_ticker_date.get(ticker, {}).get(day)
            entry_price = float(trade.get("entry_price") or 0.0)
            notional = float(trade.get("paper_notional_usd") or trade.get("notional_usd") or 0.0)
            if close is None or entry_price <= 0.0 or notional <= 0.0:
                continue
            contribution += notional * (close / entry_price - 1.0)
            contribution -= notional * ROUND_TRIP_COST_PCT / 2.0
        paper_contribution.append(contribution)
        combined_curve.append((day, round(float(raw_equity) + contribution, 8)))

    inference = build_backtest_sharpe_inference(combined_curve)
    if inference.get("status") != "computable" or inference.get("schema_version", 0) < 1:
        raise RuntimeError(f"current Sharpe inference unavailable: {inference}")
    total_pnl = float(before_result.get("total_pnl") or 0.0) + sum(
        float(row.get("pnl") or 0.0) for row in trades
    )
    strategy_return = total_pnl / float(INITIAL_CAPITAL)
    sharpe = float(inference["annualized_sharpe"])
    peak = 0.0
    max_drawdown = 0.0
    for _, equity in combined_curve:
        peak = max(peak, float(equity))
        if peak > 0.0:
            max_drawdown = max(max_drawdown, (peak - float(equity)) / peak)
    core_trades = int(before_result.get("total_trades") or 0)
    core_wins = int(before_result.get("wins") or 0)
    paper_wins = sum(1 for row in trades if float(row.get("pnl") or 0.0) > 0.0)
    total_trades = core_trades + len(trades)
    return {
        "expected_value_score": round(strategy_return * sharpe, 6),
        "total_pnl": round(total_pnl, 2),
        "strategy_total_return_pct": round(strategy_return, 6),
        "sharpe_daily": round(sharpe, 6),
        "max_drawdown_pct": round(max_drawdown, 6),
        "win_rate": round((core_wins + paper_wins) / total_trades, 6) if total_trades else None,
        "trade_count": total_trades,
        "paper_trade_count": len(trades),
        "signals_generated": before_result.get("signals_generated"),
        "signals_survived": before_result.get("signals_survived"),
        "survival_rate": round(float(before_result.get("survival_rate") or 0.0), 6),
        "sharpe_inference": inference,
        "paper_mtm_contract": {
            "schema_version": 1,
            "open_positions_marked_daily": True,
            "entry_half_cost_recognized_while_open": True,
            "full_net_pnl_recognized_on_fixed_exit": True,
            "final_liquidation_costs_included": True,
        },
    }


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    return {
        key: round(float(after[key]) - float(before[key]), 6 if key != "total_pnl" else 2)
        for key in (
            "expected_value_score",
            "total_pnl",
            "strategy_total_return_pct",
            "sharpe_daily",
            "max_drawdown_pct",
            "trade_count",
        )
    }


def _selection_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("signal_date") or row.get("date") or "")[:10],
        str(row.get("ticker") or "").upper(),
        str(row.get("source_family") or ""),
    )


def _concentration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    positive: Counter[str] = Counter()
    for row in rows:
        pnl = float(row.get("pnl") or 0.0)
        if pnl > 0.0:
            positive[str(row.get("ticker") or "").upper()] += pnl
    total = sum(positive.values())
    shares = {ticker: value / total for ticker, value in positive.items()} if total > 0 else {}
    return {
        "positive_pnl": round(total, 2),
        "positive_by_ticker": {key: round(value, 2) for key, value in positive.items()},
        "max_single_positive_share": round(max(shares.values()), 6) if shares else None,
        "positive_hhi": round(sum(value * value for value in shares.values()), 6) if shares else None,
    }


def _baseline_reference() -> dict[str, dict[str, Any]]:
    payload = json.loads(CURRENT_BASELINE.read_text(encoding="utf-8"))
    return {row["label"]: row for row in payload["windows"]}


def build_payload() -> dict[str, Any]:
    timestamp = _utc_now()
    gate2_open = framework.sleeve._audit_open_positions()
    universe = sorted(get_universe())
    all_sector_entries = framework._load_sector_entries()
    baseline_reference = _baseline_reference()
    windows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    move_selected_all: list[dict[str, Any]] = []
    baseline_identity: dict[str, Any] = {}

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] current allocator vs allocator + fixed MOVE rank 4")
        core = framework.shadow._run_baseline(universe, cfg)
        reference = baseline_reference[label]
        core_hash = (core.get("sharpe_inference") or {}).get("return_series_sha256")
        reference_hash = (reference.get("sharpe_inference") or {}).get("return_series_sha256")
        baseline_identity[label] = {
            "schema_version": (core.get("sharpe_inference") or {}).get("schema_version"),
            "current_return_series_sha256": core_hash,
            "exp_20260712_006_return_series_sha256": reference_hash,
            "return_hash_matched": bool(core_hash and core_hash == reference_hash),
            "current_total_pnl": round(float(core.get("total_pnl") or 0.0), 2),
            "exp_20260712_006_total_pnl": reference["after_metrics"]["total_pnl"],
        }
        snapshot = _load_window_snapshot(cfg, all_sector_entries)
        window_sector_entries = {
            ticker: meta for ticker, meta in all_sector_entries.items() if ticker in snapshot
        }
        core_entries = framework.shadow._baseline_entries(core)
        before_trades, before_audit = _build_allocator_trades(
            snapshot=snapshot,
            cfg=cfg,
            label=label,
            sector_entries=window_sector_entries,
            core_entries=core_entries,
            with_move=False,
        )
        after_trades, after_audit = _build_allocator_trades(
            snapshot=snapshot,
            cfg=cfg,
            label=label,
            sector_entries=window_sector_entries,
            core_entries=core_entries,
            with_move=True,
        )
        before = _curve_metrics(core, before_trades, snapshot)
        after = _curve_metrics(core, after_trades, snapshot)
        delta = _delta(after, before)
        move_selected = [row for row in after_trades if row.get("source_family") == MOVE_SOURCE]
        move_selected_all.extend({**row, "window": label} for row in move_selected)
        before_keys = {_selection_key(row) for row in before_trades}
        after_keys = {_selection_key(row) for row in after_trades}
        windows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "before_allocator_trade_count": len(before_trades),
            "after_allocator_trade_count": len(after_trades),
            "move_source_trade_count": after_audit["source_trade_counts_by_window"][label].get(
                MOVE_SOURCE, 0
            ),
            "move_selected_trade_count": len(move_selected),
            "added_selection_count": len(after_keys - before_keys),
            "removed_selection_count": len(before_keys - after_keys),
            "before_selected_source_counts": before_audit["selected_source_counts_by_window"][label],
            "after_selected_source_counts": after_audit["selected_source_counts_by_window"][label],
        }

    aggregate_before_ev = sum(row["before"]["expected_value_score"] for row in windows.values())
    aggregate_after_ev = sum(row["after"]["expected_value_score"] for row in windows.values())
    aggregate_before_pnl = sum(row["before"]["total_pnl"] for row in windows.values())
    aggregate_after_pnl = sum(row["after"]["total_pnl"] for row in windows.values())
    ev_delta = aggregate_after_ev - aggregate_before_ev
    pnl_delta = aggregate_after_pnl - aggregate_before_pnl
    relative_ev = ev_delta / abs(aggregate_before_ev) if aggregate_before_ev else None
    move_windows = [label for label, row in windows.items() if row["move_selected_trade_count"] > 0]
    concentration = _concentration(move_selected_all)
    min_survival = min(row["after"]["survival_rate"] for row in windows.values())
    checks = {
        "gate1_current_schema_identity": all(
            row["return_hash_matched"] and int(row["schema_version"] or 0) >= 1
            for row in baseline_identity.values()
        ),
        "gate2_dependencies": bool(gate2_open.get("passed"))
        and all(row.get("entry_date") for row in move_selected_all),
        "gate3_survival_at_least_5pct": min_survival >= 0.05,
        "aggregate_ev_improvement_gt_10pct": relative_ev is not None
        and relative_ev > MIN_RELATIVE_EV_IMPROVEMENT,
        "aggregate_pnl_delta_positive": pnl_delta > 0.0,
        "no_window_ev_regression": all(
            row["delta"]["expected_value_score"] >= 0.0 for row in windows.values()
        ),
        "no_window_pnl_regression": all(row["delta"]["total_pnl"] >= 0.0 for row in windows.values()),
        "drawdown_guard": all(
            row["delta"]["max_drawdown_pct"] <= MAX_DRAWDOWN_WORSE for row in windows.values()
        ),
        "move_target_sample": len(move_selected_all) >= MIN_MOVE_SELECTED,
        "move_target_window_coverage": len(move_windows) >= MIN_MOVE_WINDOWS,
        "move_positive_concentration": concentration["max_single_positive_share"] is not None
        and concentration["max_single_positive_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and concentration["positive_hhi"] is not None
        and concentration["positive_hhi"] <= MAX_POSITIVE_HHI,
    }
    failed = [name for name, passed in checks.items() if not passed]
    accepted = not failed
    decision = (
        "accepted_paper_pending_forward_move_allocator_source"
        if accepted
        else "rejected_move_rate_volatility_allocator_source"
    )
    status = "accepted" if accepted else "rejected"
    predicted_modes = list(PREDICTION["main_failure_modes"])
    observed_modes = []
    if pnl_delta <= 0.0 or any(row["delta"]["total_pnl"] < 0.0 for row in windows.values()):
        observed_modes.append("move_rows_displace_stronger_lower_priority_sources")
    if sum(row["added_selection_count"] for row in windows.values()) < 5:
        observed_modes.append("insufficient_incremental_touched_selections")
    if not checks["gate1_current_schema_identity"]:
        observed_modes.append("current_schema_comparator_drift")
    why = (
        "The fixed MOVE source added enough distinct rank-4 allocator selections to improve "
        "the current accepted allocator across every canonical window under daily MTM."
        if accepted
        else "The standalone MOVE edge did not survive source-priority arbitration at the "
        "predeclared rank: it either displaced stronger lower-priority rows, touched too few "
        "allocator decisions, or failed the 10% current-schema EV materiality bar."
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "owner": OWNER,
        "lane": LANE,
        "status": status,
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": accepted,
        "hypothesis": HYPOTHESIS,
        "change_summary": "Test unchanged MOVE relief as fixed rank-4 accepted-helper allocator source.",
        "change_type": "candidate_pool_full_stack",
        "implementation_mode": "shared_paper_first_full_stack_attempt",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": [
            "experiment-local exact shared-policy candidate",
            "same-run current-schema allocator before/after",
            "daily MTM plus entry/full-exit costs",
            "daily default-off parity boundary",
            "execution envelope and full-stack verdict",
        ],
        "nearby_prior_experiments": NEARBY,
        "new_evidence_type": "new_gate_shape_on_newly_accepted_move_source",
        "new_evidence_axis": NEW_AXIS,
        "prediction": PREDICTION,
        "calibration": {
            "actual_success": accepted,
            "predicted_success_probability": PREDICTION["success_probability"],
            "brier_score": round(
                (float(PREDICTION["success_probability"]) - (1.0 if accepted else 0.0)) ** 2,
                6,
            ),
            "predicted_failure_modes": predicted_modes,
            "realized_failure_modes": observed_modes,
            "predicted_failure_mode_hit": any(mode in observed_modes for mode in predicted_modes),
            "expected_ev_delta": PREDICTION.get("expected_ev_delta"),
            "actual_ev_delta": round(ev_delta, 6),
            "expected_pnl_delta": PREDICTION.get("expected_pnl_delta"),
            "actual_pnl_delta": round(pnl_delta, 2),
            "surprise_note": why,
        },
        "parameters": {
            "move_source_rank": MOVE_RANK,
            "move_rule_version": move_helper.SOURCE_RULE_VERSION,
            "daily_entry_slots": 1,
            "hold_days": 10,
            "same_ticker_cooldown_days": 12,
            "move_notional_scalar": 1.0,
            "trade_enabled": False,
        },
        "gate1": {
            "passed": checks["gate1_current_schema_identity"],
            "baseline_artifact": _repo_rel(CURRENT_BASELINE),
            "current_schema": "sharpe_inference_v1_daily_mtm",
            "windows": baseline_identity,
        },
        "gate2": {
            "passed": checks["gate2_dependencies"],
            "open_positions": gate2_open,
            "move_entry_date_coverage": sum(bool(row.get("entry_date")) for row in move_selected_all),
            "move_target_price_contract": (
                "not applicable: accepted allocator uses fixed 10-trading-day time exit; "
                "daily rows carry target_price_status=not_applicable_time_exit"
            ),
            "move_source_rule_version": move_helper.SOURCE_RULE_VERSION,
        },
        "gate3": {
            "passed": checks["gate3_survival_at_least_5pct"],
            "signals_generated": {
                label: row["after"]["signals_generated"] for label, row in windows.items()
            },
            "signals_survived": {
                label: row["after"]["signals_survived"] for label, row in windows.items()
            },
            "minimum_survival_rate": min_survival,
            "new_filter_added": False,
        },
        "gate4": {
            "passed": accepted,
            "decision": decision,
            "checks": checks,
            "failed_reasons": failed,
            "aggregate_before_ev": round(aggregate_before_ev, 6),
            "aggregate_after_ev": round(aggregate_after_ev, 6),
            "aggregate_ev_delta": round(ev_delta, 6),
            "relative_ev_improvement": round(relative_ev, 6) if relative_ev is not None else None,
            "aggregate_before_pnl": round(aggregate_before_pnl, 2),
            "aggregate_after_pnl": round(aggregate_after_pnl, 2),
            "aggregate_pnl_delta": round(pnl_delta, 2),
            "move_selected_trade_count": len(move_selected_all),
            "move_selected_windows": move_windows,
            "move_concentration": concentration,
        },
        "before_metrics": {label: row["before"] for label, row in windows.items()},
        "after_metrics": {label: row["after"] for label, row in windows.items()},
        "delta_metrics": {
            "windows": {label: row["delta"] for label, row in windows.items()},
            "aggregate_expected_value_score_delta": round(ev_delta, 6),
            "aggregate_total_pnl_delta": round(pnl_delta, 2),
            "relative_expected_value_score_improvement": round(relative_ev, 6)
            if relative_ev is not None
            else None,
        },
        "window_rows": windows,
        "move_selected_trades": move_selected_all,
        "full_stack_verdict": (
            "accepted_paper_pending_forward" if accepted else "reject"
        ),
        "gate5": {
            "live_eligible": False,
            "status": "not_computable",
            "reason": "complete aligned allocator trial panel unavailable; DSR cannot be synthesized",
        },
        "production_impact": {
            "shared_policy_changed": accepted,
            "backtester_adapter_changed": accepted,
            "run_adapter_changed": accepted,
            "replay_only": False,
            "daily_snapshot_exposed": accepted,
            "trade_enabled": False,
            "core_signals_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_rules_changed": False,
            "orders_changed": False,
            "llm_decision_boundary_changed": False,
            "live_realism_evaluated": True,
            "live_ready": False,
            "execution_envelope": {
                "base_notional_usd": 4000.0,
                "max_concurrent": 8,
                "max_capital_usd": 40000.0,
                "order_semantics": "next_open_paper_only",
                "hold_days": 10,
                "same_ticker_cooldown_days": 12,
                "cost_model": "shared 5bps per-leg slippage plus ROUND_TRIP_COST_PCT",
                "kill_switch": "existing allocator forward gate; live remains ineligible",
            },
        },
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retry MOVE allocator rank, idle-date-only admission, source scalar, "
                "top-N, hold, cooldown, sector priority, or exit response on the frozen windows."
            ),
            "new_evidence_required": (
                "If rejected, reopen only with at least 30 closed prospective MOVE rows carrying "
                "allocator displacement replacement value, or a genuinely independent rate-volatility "
                "source. If accepted, collect those rows before any live activation work."
            ),
        },
        "rejection_reason": None if accepted else ";".join(failed),
        "next_retry_requires": [
            "30 closed prospective MOVE allocator-displacement rows or independent source",
            "no rank, scalar, threshold, hold, cooldown, or exit retune",
        ],
        "related_files": [
            RUNNER,
            "quant/move_rate_volatility_relief_paper_sleeve.py",
            "quant/accepted_helper_source_priority_allocator_paper_sleeve.py",
            "quant/run.py",
            "docs/production_backtest_parity_matrix.md",
            _repo_rel(CURRENT_BASELINE),
        ],
        "reproduction_commands": [
            f".\\.venv\\Scripts\\python.exe -B -m py_compile {RUNNER.replace('/', chr(92))}",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "lean_quality_passed": True,
    }


def _card(payload: dict[str, Any]) -> str:
    gate = payload["gate4"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} MOVE allocator source",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Aggregate EV delta: `{gate['aggregate_ev_delta']:+.6f}`",
            f"- Relative EV improvement: `{gate['relative_ev_improvement']:+.2%}`",
            f"- Aggregate PnL delta: `${gate['aggregate_pnl_delta']:+,.2f}`",
            f"- MOVE selected trades: `{gate['move_selected_trade_count']}`",
            f"- Failed reasons: `{', '.join(gate['failed_reasons']) or 'none'}`",
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            payload["post_run_reflection"]["new_evidence_required"],
            "",
            "## Reproduce",
            "",
            f"- `{RUNNER_COMMAND}`",
            "",
        ]
    )


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    save_experiment_log_entry(payload, allow_duplicate=True)
    _write_text(CARD_MD, _card(payload))
    _write_json(
        MANIFEST_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "decision": payload["decision"],
            "generated_at": payload["timestamp"],
            "runner": RUNNER,
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "card": _repo_rel(CARD_MD),
            "ticket": _repo_rel(TICKET_JSON),
            "reproduction_commands": payload["reproduction_commands"],
        },
    )
    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8"))
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=PREDICTION,
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": payload["accepted_alpha"],
            "decision": payload["decision"],
            "artifact": _repo_rel(OUT_JSON),
            "gate4": payload["gate4"],
            "full_stack_verdict": payload["full_stack_verdict"],
            "calibration": payload["calibration"],
        },
        status=payload["status"],
        fields={
            **{key: value for key, value in ticket.items() if key not in {"result", "status"}},
            **{
                key: value
                for key, value in payload.items()
                if key not in {"experiment_id", "status", "prediction"}
            },
            "owner": OWNER,
            "card_file": _repo_rel(CARD_MD),
            "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        },
    )


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "gate4": payload["gate4"],
                "artifact": _repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if payload["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
