"""exp-20260612-018: market-state-conditioned consensus sleeve notional tilt.

Alpha search (regime router). This is the frozen Gate 1-4 follow-up that
exp-20260606-022 queued: the accepted lagged cross-source consensus default-off
paper sleeve (exp-20260604-008/009) earns most of its per-trade edge when the
prior-trading-day-close market state is `mixed|balanced|normal`. This run tests
ONE predeclared router rule: paper rows entered in that single state cell get a
bounded notional tilt; every other row, sleeve, candidate, exit, and live order
is unchanged.

Frozen inputs:
- accepted sleeve rows: exp-20260604-008 artifact target_trades_by_window;
- state classifier: exp-20260606-022 `_state_for_entry_date` (reused via
  import, identical thresholds, prior-close PIT semantics);
- predeclared cell: `mixed|balanced|normal` only;
- predeclared scalars: 1.25 and 1.5 only.

Circularity disclosure: exp-20260606-022 screened this cell on the same three
canonical windows, so a positive Gate 4 here is partially in-sample. The
verdict is therefore capped at accepted_paper_pending_forward; live-eligible
evidence must come from closed forward replacement-value rows.

No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260612-018"
STEM = "state_router_consensus_tilt"
TRIAL_FAMILY = "market_state_conditioned_sleeve_router"
TRIAL_VARIANT_ID = "consensus_sleeve_mixed_balanced_normal_tilt_v1"
CHANGED_VARIABLE = "market_state_conditioned_consensus_notional_tilt_single_cell"
RULE_VERSION = "consensus_state_router_mixed_balanced_normal_v1"

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260604_008_lagged_independent_source_consensus as lagged  # noqa: E402
import exp_20260606_022_market_state_accepted_sleeve_replacement_value_attribution as statemod  # noqa: E402

same_day = lagged.same_day
base = same_day.prior.base
overlay_helper = base.overlay_helper

WINDOWS = base.WINDOWS
ROUTER_CELL = "mixed|balanced|normal"
ROUTER_SCALARS = (1.25, 1.5)
BASELINE_VARIANT = "accepted_unconditional_consensus_sleeve"

MIN_IN_CELL_TRADES_TOTAL = 30
MIN_IN_CELL_WINDOWS = 3
MIN_EV_IMPROVED_WINDOWS = 2
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_TICKER_POSITIVE_SHARE = 0.50
IDENTITY_EV_TOLERANCE = 0.0005
IDENTITY_PNL_TOLERANCE = 1.0

OUT_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / EXPERIMENT_ID
    / f"exp_20260612_018_{STEM}.json"
)
BEFORE_AGG_JSON = OUT_JSON.parent / f"exp_20260612_018_{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_JSON.parent / f"exp_20260612_018_{STEM}_after_aggregate.json"


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(row) for key, row in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(row) for row in value]
    if isinstance(value, set):
        return sorted(_safe(row) for row in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _round(value: Any, digits: int = 6) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _annotate_state(
    trades: list[dict[str, Any]],
    *,
    snapshot: dict[str, Any],
) -> list[dict[str, Any]]:
    trading_dates = statemod._trading_dates(snapshot)
    annotated = []
    for trade in trades:
        row = dict(trade)
        state = statemod._state_for_entry_date(
            snapshot=snapshot,
            trading_dates=trading_dates,
            entry_date=str(row.get("entry_date") or ""),
        )
        row["market_state"] = state
        row["combined_state"] = state.get("combined_state") if state else None
        row["state_router_cell_match"] = bool(
            state and state.get("combined_state") == ROUTER_CELL
        )
        annotated.append(row)
    return annotated


def _apply_tilt(
    trades: list[dict[str, Any]],
    *,
    scalar: float | None,
) -> list[dict[str, Any]]:
    adjusted = []
    for trade in trades:
        row = dict(trade)
        applies = bool(scalar is not None and row.get("state_router_cell_match"))
        row["state_router_rule_version"] = RULE_VERSION
        row["state_router_cell"] = ROUTER_CELL
        row["state_router_scalar"] = scalar if applies else None
        row["state_router_applied"] = applies
        if applies:
            base_notional = float(row.get("paper_notional_usd") or 0.0)
            base_pnl = float(row.get("pnl") or 0.0)
            row["state_router_base_notional"] = base_notional
            row["state_router_base_pnl"] = base_pnl
            row["paper_notional_usd"] = round(base_notional * float(scalar), 2)
            row["pnl"] = round(base_pnl * float(scalar), 2)
        adjusted.append(row)
    return adjusted


def _single_ticker_positive_share(trades: list[dict[str, Any]]) -> float | None:
    positive = [row for row in trades if float(row.get("pnl") or 0.0) > 0]
    total = sum(float(row.get("pnl") or 0.0) for row in positive)
    if total <= 0:
        return None
    by_ticker: dict[str, float] = defaultdict(float)
    for row in positive:
        by_ticker[str(row.get("ticker") or "").upper()] += float(row.get("pnl") or 0.0)
    return round(max(by_ticker.values()) / total, 6) if by_ticker else None


def _run_variant(
    *,
    scalar: float | None,
    baselines: dict[str, dict[str, Any]],
    annotated_by_window: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    per_window = OrderedDict()
    for label, cfg in WINDOWS.items():
        trades = _apply_tilt(annotated_by_window[label], scalar=scalar)
        before_result = baselines[label]["result"]
        before = baselines[label]["metrics"]
        overlay = base._overlay_from_paper_trades(before_result, trades)
        after = overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = overlay_helper._delta(after, before)
        in_cell = [row for row in trades if row.get("state_router_cell_match")]
        applied = [row for row in trades if row.get("state_router_applied")]
        per_window[label] = {
            "before": before,
            "after": after,
            "delta_vs_core": delta,
            "trade_count": len(trades),
            "in_cell_trade_count": len(in_cell),
            "applied_trade_count": len(applied),
            "in_cell_pnl": round(sum(float(r.get("pnl") or 0.0) for r in in_cell), 2),
            "sleeve_pnl": round(sum(float(r.get("pnl") or 0.0) for r in trades), 2),
            "trades": [
                {
                    "ticker": row.get("ticker"),
                    "entry_date": row.get("entry_date"),
                    "exit_date": row.get("exit_date"),
                    "combined_state": row.get("combined_state"),
                    "state_router_applied": row.get("state_router_applied"),
                    "paper_notional_usd": row.get("paper_notional_usd"),
                    "pnl": row.get("pnl"),
                    "pnl_pct_net": row.get("pnl_pct_net"),
                }
                for row in trades
            ],
        }
    all_trades = [
        row
        for label in WINDOWS
        for row in _apply_tilt(annotated_by_window[label], scalar=scalar)
    ]
    in_cell_all = [row for row in all_trades if row.get("state_router_cell_match")]
    return {
        "variant_name": (
            BASELINE_VARIANT
            if scalar is None
            else f"cell_tilt_{str(scalar).replace('.', 'p')}x"
        ),
        "scalar": scalar,
        "per_window": per_window,
        "aggregate_after_ev": round(
            sum(float(per_window[l]["after"]["expected_value_score"] or 0.0) for l in WINDOWS),
            6,
        ),
        "aggregate_after_pnl": round(
            sum(float(per_window[l]["after"]["total_pnl"] or 0.0) for l in WINDOWS),
            2,
        ),
        "in_cell_trade_count_total": len(in_cell_all),
        "in_cell_windows": sorted(
            {l for l in WINDOWS if per_window[l]["in_cell_trade_count"] > 0}
        ),
        "in_cell_single_ticker_positive_share": _single_ticker_positive_share(
            in_cell_all
        ),
    }


def _gate4(
    variant: dict[str, Any],
    identity: dict[str, Any],
) -> dict[str, Any]:
    ev_delta_by_window = {
        label: round(
            float(variant["per_window"][label]["after"]["expected_value_score"] or 0.0)
            - float(identity["per_window"][label]["after"]["expected_value_score"] or 0.0),
            6,
        )
        for label in WINDOWS
    }
    pnl_delta_by_window = {
        label: round(
            float(variant["per_window"][label]["after"]["total_pnl"] or 0.0)
            - float(identity["per_window"][label]["after"]["total_pnl"] or 0.0),
            2,
        )
        for label in WINDOWS
    }
    dd_delta_by_window = {
        label: round(
            float(variant["per_window"][label]["after"]["max_drawdown_pct"] or 0.0)
            - float(identity["per_window"][label]["after"]["max_drawdown_pct"] or 0.0),
            6,
        )
        for label in WINDOWS
    }
    aggregate_ev_delta = round(sum(ev_delta_by_window.values()), 6)
    aggregate_pnl_delta = round(sum(pnl_delta_by_window.values()), 2)
    windows_ev_improved = sum(1 for v in ev_delta_by_window.values() if v > 0)
    windows_ev_regressed = sum(1 for v in ev_delta_by_window.values() if v < 0)
    max_dd_worse = max(dd_delta_by_window.values()) if dd_delta_by_window else 0.0
    share = variant["in_cell_single_ticker_positive_share"]
    sample_guard = (
        variant["in_cell_trade_count_total"] >= MIN_IN_CELL_TRADES_TOTAL
        and len(variant["in_cell_windows"]) >= MIN_IN_CELL_WINDOWS
    )
    concentration_guard = share is None or share <= MAX_SINGLE_TICKER_POSITIVE_SHARE
    drawdown_guard = max_dd_worse <= MAX_DRAWDOWN_WORSE
    passed = (
        aggregate_ev_delta > 0
        and aggregate_pnl_delta > 0
        and windows_ev_improved >= MIN_EV_IMPROVED_WINDOWS
        and windows_ev_regressed == 0
        and sample_guard
        and concentration_guard
        and drawdown_guard
    )
    return {
        "passed": passed,
        "comparator": (
            "accepted unconditional consensus sleeve (exp-20260604-008/009 "
            "after metrics, reproduced by the identity variant)"
        ),
        "aggregate_ev_delta": aggregate_ev_delta,
        "aggregate_ev_delta_pct": round(
            aggregate_ev_delta / identity["aggregate_after_ev"], 6
        )
        if identity["aggregate_after_ev"]
        else None,
        "aggregate_pnl_delta": aggregate_pnl_delta,
        "ev_delta_by_window": ev_delta_by_window,
        "pnl_delta_by_window": pnl_delta_by_window,
        "max_drawdown_delta_by_window": dd_delta_by_window,
        "windows_ev_improved": windows_ev_improved,
        "windows_ev_regressed": windows_ev_regressed,
        "minimum_ev_improved_windows": MIN_EV_IMPROVED_WINDOWS,
        "in_cell_trade_count_total": variant["in_cell_trade_count_total"],
        "in_cell_windows": variant["in_cell_windows"],
        "minimum_in_cell_trades_total": MIN_IN_CELL_TRADES_TOTAL,
        "minimum_in_cell_windows": MIN_IN_CELL_WINDOWS,
        "sample_guard_passed": sample_guard,
        "in_cell_single_ticker_positive_share": share,
        "max_single_ticker_positive_share": MAX_SINGLE_TICKER_POSITIVE_SHARE,
        "concentration_guard_passed": concentration_guard,
        "max_drawdown_worse_max": max_dd_worse,
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "drawdown_guard_passed": drawdown_guard,
    }


def _identity_parity_check(identity: dict[str, Any]) -> dict[str, Any]:
    artifact = json.loads(
        (REPO_ROOT / "data/experiments/exp-20260604-008/lagged_independent_source_consensus.json")
        .read_text(encoding="utf-8")
    )
    recorded = {row["label"]: row for row in artifact["results"]}
    mismatches = []
    for label in WINDOWS:
        rec_after = recorded[label]["after"]
        run_after = identity["per_window"][label]["after"]
        ev_diff = abs(
            float(rec_after["expected_value_score"]) - float(run_after["expected_value_score"])
        )
        pnl_diff = abs(float(rec_after["total_pnl"]) - float(run_after["total_pnl"]))
        if ev_diff > IDENTITY_EV_TOLERANCE or pnl_diff > IDENTITY_PNL_TOLERANCE:
            mismatches.append(
                {
                    "window": label,
                    "recorded_ev": rec_after["expected_value_score"],
                    "reproduced_ev": run_after["expected_value_score"],
                    "recorded_pnl": rec_after["total_pnl"],
                    "reproduced_pnl": run_after["total_pnl"],
                }
            )
    return {
        "tolerances": {
            "expected_value_score": IDENTITY_EV_TOLERANCE,
            "total_pnl_usd": IDENTITY_PNL_TOLERANCE,
        },
        "mismatches": mismatches,
        "passed": not mismatches,
    }


def build_payload() -> dict[str, Any]:
    artifact = json.loads(
        (REPO_ROOT / "data/experiments/exp-20260604-008/lagged_independent_source_consensus.json")
        .read_text(encoding="utf-8")
    )
    trades_by_window = artifact["target_trades_by_window"]

    baselines = same_day.prior._load_baselines()
    annotated_by_window: dict[str, list[dict[str, Any]]] = OrderedDict()
    state_coverage = OrderedDict()
    for label, cfg in WINDOWS.items():
        snapshot = base.shadow._load_snapshot(cfg["snapshot"])
        annotated = _annotate_state(trades_by_window[label], snapshot=snapshot)
        annotated_by_window[label] = annotated
        state_coverage[label] = {
            "trade_count": len(annotated),
            "missing_state_count": sum(1 for r in annotated if not r.get("combined_state")),
            "in_cell_count": sum(1 for r in annotated if r.get("state_router_cell_match")),
            "state_counts": dict(
                sorted(
                    {
                        state: sum(
                            1 for r in annotated if r.get("combined_state") == state
                        )
                        for state in {r.get("combined_state") for r in annotated}
                        if state
                    }.items()
                )
            ),
        }

    identity = _run_variant(
        scalar=None, baselines=baselines, annotated_by_window=annotated_by_window
    )
    parity = _identity_parity_check(identity)
    if not parity["passed"]:
        raise RuntimeError(f"Identity parity failed: {json.dumps(parity, indent=2)}")

    variants = [identity] + [
        _run_variant(
            scalar=scalar, baselines=baselines, annotated_by_window=annotated_by_window
        )
        for scalar in ROUTER_SCALARS
    ]
    sweep = []
    for variant in variants:
        gate4 = (
            None
            if variant["variant_name"] == BASELINE_VARIANT
            else _gate4(variant, identity)
        )
        sweep.append(
            {
                "variant_name": variant["variant_name"],
                "scalar": variant["scalar"],
                "is_identity_control": variant["variant_name"] == BASELINE_VARIANT,
                "aggregate_after_ev": variant["aggregate_after_ev"],
                "aggregate_after_pnl": variant["aggregate_after_pnl"],
                "in_cell_trade_count_total": variant["in_cell_trade_count_total"],
                "in_cell_single_ticker_positive_share": variant[
                    "in_cell_single_ticker_positive_share"
                ],
                "gate4": gate4,
            }
        )

    candidates = [row for row in sweep if not row["is_identity_control"]]
    passing = [row for row in candidates if row["gate4"]["passed"]]
    best = max(
        passing if passing else candidates,
        key=lambda row: (
            row["gate4"]["aggregate_ev_delta"],
            row["gate4"]["aggregate_pnl_delta"],
            -row["gate4"]["max_drawdown_worse_max"],
        ),
    )
    best_variant = next(v for v in variants if v["variant_name"] == best["variant_name"])
    passed = bool(best["gate4"]["passed"])
    decision = (
        "accepted_state_router_consensus_tilt_paper_pending_forward"
        if passed
        else "rejected_state_router_consensus_tilt"
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "lane": "alpha_search",
        "status": "accepted" if passed else "rejected",
        "decision": decision,
        "hypothesis": (
            "The accepted lagged cross-source consensus paper sleeve earns most "
            "of its edge when the prior-close market state is "
            "mixed|balanced|normal; a frozen single-cell paper notional tilt "
            "toward that state raises combined EV without changing entries, "
            "exits, candidates, or live orders."
        ),
        "alpha_hypothesis": {
            "category": "capital allocation / regime router",
            "entry_exit_ranking_or_allocation": "default-off paper allocation",
            "playbook_alignment": (
                "Direct follow-up queued by exp-20260606-022; conditions an "
                "accepted sleeve on a new production-visible PIT market-state "
                "field instead of retuning thresholds or hold days."
            ),
        },
        "change_type": "default_off_paper_allocation",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "rule_version": RULE_VERSION,
        "parameters": {
            "router_cell": ROUTER_CELL,
            "router_scalars_tested": list(ROUTER_SCALARS),
            "best_variant": best["variant_name"],
            "best_scalar": best["scalar"],
            "state_classifier": (
                "exp-20260606-022 _state_for_entry_date, prior-trading-day-close "
                "PIT, thresholds frozen by import"
            ),
            "state_timing": "evaluated once per trade at entry; no daily switching",
            "locked_variables": [
                "consensus sleeve candidate generation",
                "consensus sleeve entry/exit timing and hold days",
                "all other sleeves and sources",
                "core entries/exits/sizing",
                "state classifier thresholds",
                "live/default orders",
            ],
        },
        "circularity_disclosure": (
            "The router cell was screened by exp-20260606-022 on the same three "
            "canonical windows. A positive Gate 4 here is partially in-sample; "
            "the verdict is capped at accepted_paper_pending_forward and "
            "activation evidence must come from closed forward "
            "replacement-value rows."
        ),
        "state_coverage": state_coverage,
        "identity_parity_check": parity,
        "gate1": {
            "baseline_artifact": (
                "data/experiments/exp-20260604-008/lagged_independent_source_consensus.json"
            ),
            "baseline_note": (
                "Accepted unconditional consensus sleeve after-metrics, "
                "reproduced bit-close by the identity variant before any tilt."
            ),
        },
        "gate2": {
            "runtime_fields": [
                "entry_date",
                "exit_date",
                "pnl",
                "pnl_pct_net",
                "paper_notional_usd",
                "SPY/QQQ OHLCV at prior close (state features)",
            ],
            "identity_parity_check": parity,
            "passed": parity["passed"],
        },
        "gate3": {
            "new_filter_added": False,
            "note": (
                "No candidate filter or survival-affecting rule changed; only "
                "paper notional of already-selected rows changes."
            ),
        },
        "gate4": best["gate4"],
        "sweep_summary": sweep,
        "best_variant_detail": {
            "per_window": {
                label: {
                    "after": best_variant["per_window"][label]["after"],
                    "in_cell_trade_count": best_variant["per_window"][label][
                        "in_cell_trade_count"
                    ],
                    "sleeve_pnl": best_variant["per_window"][label]["sleeve_pnl"],
                    "trades": best_variant["per_window"][label]["trades"],
                }
                for label in WINDOWS
            },
        },
        "history_check": {
            "exp-20260606-022": (
                "Found this exact cell router-ready (39 rows, 3 windows, "
                "+5.7pp edge, 4.5% overlap) and queued this frozen Gate 1-4."
            ),
            "exp-20260606-021": "Core-family state attribution too thin; not retried here.",
            "exp-20260604-008/009": "Accepted unconditional sleeve = Gate 1 baseline and comparator.",
            "anti_repeat": (
                "Not a consensus source-set/timing/notional retune on price "
                "fields: the discriminator is a new production-visible "
                "market-state bucket, the sanctioned exception in the frozen "
                "zone. Single predeclared cell, two predeclared scalars, no "
                "other sweeps."
            ),
        },
        "llm_metrics": {"used_llm": False, "why_not_llm": "Deterministic OHLCV state fields."},
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "live_default_orders_changed": False,
            "default_off_paper_only": True,
            "note": (
                "Replay verdict only. If accepted, the tilt must be added to "
                "quant/free_data_cross_source_consensus_paper_sleeve.py with a "
                "daily market-state field and a focused parity test before the "
                "helper change is retained; if rejected, nothing changes."
            ),
        },
        "execution_envelope": {
            "scope": "default-off paper only, trade_enabled=False",
            "notional": (
                "in-cell rows scale from $4,000 to at most $6,000 paper "
                "notional; all other rows unchanged"
            ),
            "capital_cap": "per-day admission caps of the accepted sleeve unchanged",
            "liquidity_slippage": "fill model and round-trip costs unchanged",
            "portfolio_displacement": "no displacement change; same rows, different paper weight",
            "kill_switch": "sleeve paper config; no live orders exist",
            "live_readiness": "not live-eligible; forward rows + Gate 5 required",
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "capital allocation / regime router: tilt accepted consensus "
                "sleeve paper notional toward the mixed|balanced|normal "
                "prior-close state cell."
            ),
            "2_history_check": (
                "exp-20260606-022 queued exactly this; consensus notional "
                "retunes are frozen unless conditioned on a materially "
                "different production-visible field, which the state bucket is."
            ),
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "vs accepted unconditional sleeve: aggregate EV/PnL delta > 0, "
                ">=2 EV-improved windows, zero regressed, in-cell trades >=30 "
                "across all 3 windows, in-cell single-ticker positive share "
                "<=50%, max DD drift <=0.5pp; verdict capped at "
                "accepted_paper_pending_forward due to in-sample cell screening."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260612_018_state_router_consensus_tilt.py"
            ),
        },
        "anti_js": "No JavaScript was used.",
        "related_files": [
            "quant/experiments/exp_20260612_018_state_router_consensus_tilt.py",
            "data/experiments/exp-20260612-018/exp_20260612_018_state_router_consensus_tilt.json",
            "data/experiments/exp-20260604-008/lagged_independent_source_consensus.json",
            "quant/experiments/exp_20260606_022_market_state_accepted_sleeve_replacement_value_attribution.py",
            "quant/free_data_cross_source_consensus_paper_sleeve.py",
        ],
    }
    return _safe(payload)


def main() -> None:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    identity = next(
        row for row in payload["sweep_summary"] if row["is_identity_control"]
    )
    _write_json(
        BEFORE_AGG_JSON,
        {
            "expected_value_score": identity["aggregate_after_ev"],
            "total_pnl": identity["aggregate_after_pnl"],
            "note": (
                "aggregate accepted unconditional consensus sleeve (identity "
                "variant) across docs/backtesting.md three fixed windows"
            ),
        },
    )
    _write_json(
        AFTER_AGG_JSON,
        {
            "expected_value_score": payload["sweep_summary"][0]["aggregate_after_ev"]
            if payload["parameters"]["best_variant"] == BASELINE_VARIANT
            else next(
                row["aggregate_after_ev"]
                for row in payload["sweep_summary"]
                if row["variant_name"] == payload["parameters"]["best_variant"]
            ),
            "total_pnl": next(
                row["aggregate_after_pnl"]
                for row in payload["sweep_summary"]
                if row["variant_name"] == payload["parameters"]["best_variant"]
            ),
            "note": (
                "aggregate best router variant across docs/backtesting.md "
                "three fixed windows"
            ),
        },
    )
    print(json.dumps(payload["gate4"], indent=2, sort_keys=True))
    print(
        f"{EXPERIMENT_ID} {payload['decision']} best={payload['parameters']['best_variant']} "
        f"dEV={payload['gate4']['aggregate_ev_delta']:+.4f} "
        f"dPnL=${payload['gate4']['aggregate_pnl_delta']:+,.2f}"
    )


if __name__ == "__main__":
    main()
