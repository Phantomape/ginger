"""exp-20260502-024 old_thin last-slot breakout rescue replay.

Replay-only alpha search. exp-20260502-011 rejected candidate-vs-candidate
replacement: leadership-score replacement helped mid_weak but hurt old_thin.
This narrower test asks whether scarce-slot breakout deferral is too
conservative only when it leaves the final available core slot unused.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = REPO_ROOT / "quant" / "experiments"
for path in (QUANT_DIR, EXPERIMENT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import backtester as bt  # noqa: E402
import exp_20260502_011_old_thin_slot_routing_alpha as base  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260502-024"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "old_thin_last_slot_breakout_rescue.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"

WATCHLIST = {"APP", "SPOT", "GOOG", "DDOG"}


def _candidate_key(sig: dict) -> tuple:
    return ((sig.get("ticker") or "").upper(), sig.get("strategy"))


def _quality_score(sig: dict) -> float:
    return (
        base._num(sig.get("trade_quality_score"), 0.0)
        + base._num(sig.get("confidence_score"), 0.0)
    )


def _valid_rescue_candidate(sig: dict) -> tuple[bool, str | None]:
    if sig.get("strategy") != "breakout_long":
        return False, "not_breakout_long"
    entry = base._num(sig.get("entry_price"), None)
    stop = base._num(sig.get("stop_price"), None)
    target = base._num(sig.get("target_price"), None)
    if entry is None or stop is None or target is None:
        return False, "missing_entry_stop_or_target"
    if entry <= 5:
        return False, "entry_lte_5"
    if stop <= 0 or stop >= entry:
        return False, "invalid_stop"
    if target <= entry:
        return False, "invalid_target"
    initial_risk = (entry - stop) / entry
    if initial_risk > 0.12:
        return False, "initial_risk_gt_12pct"
    if sig.get("trade_quality_score") is None:
        return False, "missing_trade_quality_score"
    if sig.get("confidence_score") is None:
        return False, "missing_confidence_score"
    sizing = sig.get("sizing") or {}
    if not sizing.get("shares_to_buy"):
        return False, "no_sized_shares"
    return True, None


def _with_rescue_marker(sig: dict, rescue: dict) -> dict:
    out = dict(sig)
    out["last_slot_breakout_rescue"] = rescue
    sizing = dict(out.get("sizing") or {})
    sizing["last_slot_breakout_rescue_replay_marker"] = 1.0
    out["sizing"] = sizing
    return out


def _patched_plan_entry_candidates(original, state):
    def patched(signals, *args, **kwargs):
        planned, plan = original(signals, *args, **kwargs)
        available_slots = int(plan.get("available_slots") or 0)
        planned_count = int(plan.get("signals_after_entry_plan") or len(planned) or 0)
        if available_slots != 1 or planned_count != 0 or planned:
            return planned, plan

        input_lookup = {
            _candidate_key(sig): sig
            for sig in signals or []
        }
        rejected = []
        candidates = []
        for deferred in plan.get("deferred_breakout_signals") or []:
            if deferred.get("strategy") != "breakout_long":
                continue
            sig = input_lookup.get(_candidate_key(deferred)) or dict(deferred)
            ok, reason = _valid_rescue_candidate(sig)
            if ok:
                candidates.append(sig)
            else:
                rejected.append({
                    "ticker": (deferred.get("ticker") or "").upper(),
                    "strategy": deferred.get("strategy"),
                    "reject_reason": reason,
                })

        if not candidates:
            if rejected:
                state.setdefault("rejected_rescue_candidates", []).extend(rejected)
            return planned, plan

        best = max(candidates, key=_quality_score)
        rescue = {
            "ticker": (best.get("ticker") or "").upper(),
            "strategy": best.get("strategy"),
            "source": "scarce_slot_breakout_deferred",
            "available_slots": available_slots,
            "signals_after_entry_plan_before_rescue": planned_count,
            "trade_quality_score": base._round(best.get("trade_quality_score"), 6),
            "confidence_score": base._round(best.get("confidence_score"), 6),
            "quality_score": base._round(_quality_score(best), 6),
            "entry_price": base._round(best.get("entry_price"), 4),
            "stop_price": base._round(best.get("stop_price"), 4),
            "target_price": base._round(best.get("target_price"), 4),
            "initial_risk_pct": base._round(
                (base._num(best.get("entry_price")) - base._num(best.get("stop_price")))
                / base._num(best.get("entry_price")),
                6,
            ),
        }
        state.setdefault("rescues", []).append(rescue)

        best_key = _candidate_key(best)
        plan = dict(plan)
        plan["deferred_breakout_signals"] = [
            sig for sig in plan.get("deferred_breakout_signals") or []
            if _candidate_key(sig) != best_key
        ]
        plan.setdefault("last_slot_breakout_rescues", []).append(rescue)
        plan["signals_after_entry_plan"] = 1
        return [_with_rescue_marker(best, rescue)], plan

    return patched


def _run_backtest(window: dict, use_rescue: bool = False) -> tuple[dict, dict]:
    state = {"rescues": [], "rejected_rescue_candidates": []}
    original_summary = bt._summarize_entry_decision_events
    original_plan = bt.plan_entry_candidates
    bt._summarize_entry_decision_events = base._patched_entry_summary(original_summary)
    if use_rescue:
        bt.plan_entry_candidates = _patched_plan_entry_candidates(original_plan, state)
    try:
        engine = BacktestEngine(
            get_universe(),
            start=window["start"],
            end=window["end"],
            config=base.CONFIG,
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=window["snapshot"],
        )
        result = engine.run()
    finally:
        bt._summarize_entry_decision_events = original_summary
        bt.plan_entry_candidates = original_plan
    return result, state


def _matched_rescue_trade_rows(result: dict, rescues: list[dict]) -> list[dict]:
    remaining = list(result.get("trades") or [])
    rows = []
    for rescue in rescues:
        ticker = rescue.get("ticker")
        strategy = rescue.get("strategy")
        match_idx = None
        for idx, trade in enumerate(remaining):
            if (trade.get("ticker") or "").upper() == ticker and trade.get("strategy") == strategy:
                match_idx = idx
                break
        if match_idx is None:
            rows.append({
                **rescue,
                "entered": False,
                "pnl": None,
                "exit_reason": None,
            })
            continue
        trade = remaining.pop(match_idx)
        rows.append({
            **rescue,
            "entered": True,
            "entry_date": trade.get("entry_date"),
            "exit_date": trade.get("exit_date"),
            "exit_reason": trade.get("exit_reason"),
            "shares": trade.get("shares"),
            "pnl": base._round(trade.get("pnl"), 2),
            "pnl_pct_net": base._round(trade.get("pnl_pct_net"), 6),
        })
    return rows


def _variant_extra(result: dict, state: dict) -> dict:
    rescue_rows = _matched_rescue_trade_rows(result, state.get("rescues") or [])
    entered = [row for row in rescue_rows if row.get("entered")]
    pnl_by_ticker = {}
    for row in entered:
        ticker = row.get("ticker") or "UNKNOWN"
        pnl_by_ticker[ticker] = base._round(
            pnl_by_ticker.get(ticker, 0.0) + base._num(row.get("pnl"), 0.0),
            2,
        )
    return {
        "rescue_signals_seen": len(state.get("rescues") or []),
        "rescue_entries": len(entered),
        "rescue_entry_pnl": base._round(
            sum(base._num(row.get("pnl"), 0.0) for row in entered),
            2,
        ),
        "rescues": state.get("rescues") or [],
        "rejected_rescue_candidates": state.get("rejected_rescue_candidates") or [],
        "matched_rescue_trade_rows": rescue_rows,
        "pnl_by_ticker": pnl_by_ticker,
        "watchlist_rescues": [
            row for row in rescue_rows
            if row.get("ticker") in WATCHLIST
        ],
    }


def _delta_metrics(baseline: dict, rescue: dict) -> dict:
    by_window = {}
    ev_improved = 0
    ev_regressed = 0
    max_single_ticker_share = 0.0
    for label in base.WINDOWS:
        b = baseline[label]["metrics"]
        r = rescue[label]["metrics"]
        delta = {
            "expected_value_score_delta": base._round(
                base._num(r.get("expected_value_score")) - base._num(b.get("expected_value_score")),
                4,
            ),
            "total_pnl_delta": base._round(
                base._num(r.get("total_pnl")) - base._num(b.get("total_pnl")),
                2,
            ),
            "sharpe_daily_delta": base._round(
                base._num(r.get("sharpe_daily")) - base._num(b.get("sharpe_daily")),
                4,
            ),
            "max_drawdown_pct_delta": base._round(
                base._num(r.get("max_drawdown_pct")) - base._num(b.get("max_drawdown_pct")),
                4,
            ),
            "win_rate_delta": base._round(
                base._num(r.get("win_rate")) - base._num(b.get("win_rate")),
                4,
            ),
            "trade_count_delta": int(
                base._num(r.get("trade_count")) - base._num(b.get("trade_count"))
            ),
        }
        if delta["expected_value_score_delta"] > 0:
            ev_improved += 1
        if delta["expected_value_score_delta"] < 0:
            ev_regressed += 1
        by_window[label] = delta

    base_agg = base._aggregate({label: baseline[label]["metrics"] for label in base.WINDOWS})
    rescue_agg = base._aggregate({label: rescue[label]["metrics"] for label in base.WINDOWS})
    aggregate_pnl_delta = base._round(
        rescue_agg["total_pnl_sum"] - base_agg["total_pnl_sum"],
        2,
    )

    pnl_by_ticker = {}
    for label in base.WINDOWS:
        for ticker, pnl in (rescue[label]["replay_extra"].get("pnl_by_ticker") or {}).items():
            pnl_by_ticker[ticker] = base._round(pnl_by_ticker.get(ticker, 0.0) + base._num(pnl), 2)
    if aggregate_pnl_delta and aggregate_pnl_delta > 0:
        positive = {ticker: pnl for ticker, pnl in pnl_by_ticker.items() if pnl > 0}
        if positive:
            max_single_ticker_share = max(positive.values()) / aggregate_pnl_delta

    delta = {
        "baseline": base_agg,
        "last_slot_rescue": rescue_agg,
        "aggregate_ev_delta": base._round(
            rescue_agg["expected_value_score_sum"] - base_agg["expected_value_score_sum"],
            4,
        ),
        "aggregate_pnl_delta": aggregate_pnl_delta,
        "windows_ev_improved": ev_improved,
        "windows_ev_regressed": ev_regressed,
        "rescued_pnl_by_ticker": pnl_by_ticker,
        "max_single_ticker_share_of_aggregate_pnl_delta": base._round(max_single_ticker_share, 4),
        "single_ticker_concentration_over_70pct": max_single_ticker_share > 0.70,
        "by_window": by_window,
    }

    old_ok = (
        by_window["old_thin"]["expected_value_score_delta"] > 0
        and by_window["old_thin"]["total_pnl_delta"] > 0
    )
    aggregate_ok = delta["aggregate_ev_delta"] > 0 and delta["aggregate_pnl_delta"] > 0
    late_ok = by_window["late_strong"]["expected_value_score_delta"] >= 0
    mid_ok = (
        by_window["mid_weak"]["expected_value_score_delta"] >= -0.05
        and by_window["mid_weak"]["max_drawdown_pct_delta"] <= 0.01
    )
    delta["gate4_pass"] = bool(old_ok and aggregate_ok and late_ok and mid_ok)
    delta["production_ready_gate"] = bool(
        delta["gate4_pass"] and not delta["single_ticker_concentration_over_70pct"]
    )
    return delta


def build_payload() -> dict:
    snapshots = {
        label: base._load_snapshot(window["snapshot"])
        for label, window in base.WINDOWS.items()
    }
    baseline = {}
    rescue = {}
    audits = {}
    for label, window in base.WINDOWS.items():
        baseline_result, _ = _run_backtest(window, use_rescue=False)
        rescue_result, rescue_state = _run_backtest(window, use_rescue=True)
        baseline[label] = {
            "window": window,
            "metrics": base._metrics(baseline_result),
        }
        rescue[label] = {
            "window": window,
            "metrics": base._metrics(rescue_result),
            "replay_extra": _variant_extra(rescue_result, rescue_state),
        }
        audits[label] = base._audit_skips(baseline_result, snapshots[label])

    delta = _delta_metrics(baseline, rescue)
    if delta["production_ready_gate"]:
        status = "accepted_for_production_review"
    elif delta["gate4_pass"]:
        status = "observed_only_not_production_ready"
    else:
        status = "rejected"

    return {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "mode": "alpha_search_replay_only",
        "alpha_hypothesis": (
            "scarce-slot breakout deferral can be too conservative when it "
            "leaves the final available core slot unused; allowing one already "
            "qualified breakout to use that empty slot may recover old_thin alpha."
        ),
        "change_type": "entry_position_allocation_replay",
        "single_causal_variable": (
            "If available_slots == 1 and post-deferral signals_after_entry_plan == 0, "
            "allow one valid scarce_slot_breakout_deferred breakout_long to re-enter "
            "the plan. No replacement, no MAX_POSITIONS increase, no exit change."
        ),
        "replay_policy": {
            "name": "last_slot_breakout_rescue",
            "global_max_positions_changed": False,
            "replacement_used": False,
            "eligible_skip_reason": "scarce_slot_breakout_deferred",
            "required_conditions": [
                "available_slots == 1",
                "signals_after_entry_plan == 0",
                "strategy == breakout_long",
                "entry/stop/target valid",
                "entry > 5",
                "stop < entry",
                "target > entry",
                "initial risk <= 12%",
                "trade_quality_score present",
                "confidence_score present",
                "shares_to_buy > 0",
            ],
        },
        "windows": base.WINDOWS,
        "baseline": baseline,
        "opportunity_displacement_audit": audits,
        "last_slot_rescue": rescue,
        "delta_metrics": delta,
        "acceptance_rule": (
            "old_thin EV/PnL improves, aggregate EV/PnL improves, late_strong "
            "does not decline, mid_weak EV does not decline more than 0.05 and "
            "drawdown does not rise more than 1pp. If >70% of aggregate PnL "
            "delta comes from one ticker, record observed_only instead of "
            "production-ready."
        ),
        "best_variant_gate4": delta["gate4_pass"],
        "production_ready_gate": delta["production_ready_gate"],
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, move this into shared production_parity entry "
                "planning and expose the same audit fields in run.py/backtester.py."
            ),
        },
        "guardrails": {
            "not_global_max_positions_sweep": True,
            "not_replacement_retry": True,
            "not_gap_cancel_loosen": True,
            "not_exit_change": True,
            "not_low_quality_position_release": True,
        },
        "decision": status,
        "rejection_reason": None if delta["gate4_pass"] else (
            "Last-slot breakout rescue did not satisfy the fixed-window Gate 4 bar."
        ),
        "next_action": (
            "Promote through shared production parity module in a separate commit."
            if delta["production_ready_gate"] else
            "Do not productionize from this replay. Use rescued-trade attribution "
            "and skip audit for the next mechanism search."
        ),
        "related_files": [
            "quant/experiments/exp_20260502_024_old_thin_last_slot_breakout_rescue.py",
            "data/experiments/exp-20260502-024/old_thin_last_slot_breakout_rescue.json",
            "docs/experiments/logs/exp-20260502-024.json",
            "docs/experiments/tickets/exp-20260502-024.json",
        ],
    }


def main() -> int:
    payload = build_payload()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2)
    OUT_JSON.write_text(text + "\n", encoding="utf-8")
    LOG_JSON.write_text(text + "\n", encoding="utf-8")
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "title": "Old thin last-slot breakout rescue replay",
        "summary": payload["alpha_hypothesis"],
        "best_variant_gate4": payload["best_variant_gate4"],
        "production_ready_gate": payload["production_ready_gate"],
        "delta_metrics": payload["delta_metrics"],
        "next_action": payload["next_action"],
    }
    TICKET_JSON.write_text(json.dumps(ticket, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "best_variant_gate4": payload["best_variant_gate4"],
        "production_ready_gate": payload["production_ready_gate"],
        "delta_metrics": payload["delta_metrics"],
        "artifact": str(OUT_JSON),
        "log": str(LOG_JSON),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
