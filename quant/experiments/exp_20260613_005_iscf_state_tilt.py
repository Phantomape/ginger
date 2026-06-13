"""exp-20260613-005: industry_stable_core_flow sleeve state-conditioned tilt.

Alpha search (regime router). Final step of the regime-router line:
exp-20260612-027 isolated `industry_stable_core_flow x mixed|balanced|normal`
as the single source x state cell surviving the ex-top-ticker robustness
screen (n=32, 31 unique tickers, top ticker TOST only 20.9% of in-cell
positive PnL, in-cell +2.93%/trade vs -0.22% in other states, positive all
three windows raw and ex-top).

Landing point is the SLEEVE itself, not the allocator: exp-20260611-005 selects
ZERO industry_stable_core_flow rows because the accepted allocator daily-top1
priority crowds the source out entirely. The sleeve nonetheless runs default-off
with all 47 rows, so the tilt is tested as a sleeve-level overlay change.

Tested decision variable (single): rows of this sleeve entered in
mixed|balanced|normal get a bounded notional tilt (1.25x / 1.5x); every other
row, entry, exit, and live order is unchanged. Comparator is the sleeve's own
unconditional overlay (identity variant). Dual concentration guards (in-cell and
tilt-incremental single-ticker positive share) carry over from exp-20260612-020.

Circularity disclosure: the cell and the windows were screened together
(exp-20260612-027), so any pass caps at accepted_paper_pending_forward.

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


EXPERIMENT_ID = "exp-20260613-005"
STEM = "iscf_state_tilt"
TRIAL_FAMILY = "market_state_conditioned_sleeve_router"
TRIAL_VARIANT_ID = "industry_stable_core_flow_state_tilt_v1"
CHANGED_VARIABLE = "industry_stable_core_flow_sleeve_state_conditioned_notional_tilt"
RULE_VERSION = "iscf_state_tilt_mixed_balanced_normal_v1"

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
LEGACY_DIR = EXPERIMENT_DIR / "legacy"
for path in (QUANT_DIR, EXPERIMENT_DIR, LEGACY_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260611_005_lagged_consensus_shared_allocator_source as alloc  # noqa: E402
import exp_20260612_018_state_router_consensus_tilt as r18  # noqa: E402
from industry_stable_core_flow_paper_sleeve import (  # noqa: E402
    build_industry_stable_core_flow_historical_trades,
)
from data_layer import get_universe  # noqa: E402

framework = alloc.framework
exp008 = alloc.exp008
statemod = r18.statemod
WINDOWS = framework.WINDOWS

ROUTER_CELL = "mixed|balanced|normal"
TILT_SCALARS = (1.25, 1.5)
BASELINE_VARIANT = "unconditional_iscf_sleeve"

MIN_IN_CELL_TRADES_TOTAL = 18
MIN_IN_CELL_WINDOWS = 3
MIN_EV_IMPROVED_WINDOWS = 2
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_TICKER_POSITIVE_SHARE = 0.50

CANONICAL_SNAPSHOTS = {
    "late_strong": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
    "mid_weak": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
    "old_thin": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
}

OUT_JSON = (
    REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"exp_20260613_005_{STEM}.json"
)
BEFORE_AGG_JSON = OUT_JSON.parent / f"exp_20260613_005_{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_JSON.parent / f"exp_20260613_005_{STEM}_after_aggregate.json"


def _float(value: Any) -> float | None:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


def _entry_date(row: dict[str, Any], window_dates: list[str]) -> str | None:
    entry = str(row.get("entry_date") or "")[:10]
    if entry:
        return entry
    signal = str(row.get("signal_date") or row.get("date") or "")[:10]
    if not signal:
        return None
    for day in window_dates:
        if day > signal:
            return day
    return None


def _annotate(trades: list[dict[str, Any]], *, label: str) -> list[dict[str, Any]]:
    snapshot = statemod._load_snapshot(CANONICAL_SNAPSHOTS[label])
    dates = statemod._trading_dates(snapshot)
    out = []
    for trade in trades:
        row = dict(trade)
        entry = _entry_date(row, dates)
        state = (
            statemod._state_for_entry_date(
                snapshot=snapshot, trading_dates=dates, entry_date=entry
            )
            if entry
            else None
        )
        cs = state.get("combined_state") if state else None
        row["combined_state"] = cs
        row["state_router_cell_match"] = cs == ROUTER_CELL
        out.append(row)
    return out


def _apply_tilt(trades: list[dict[str, Any]], *, scalar: float | None) -> list[dict[str, Any]]:
    adjusted = []
    for trade in trades:
        row = dict(trade)
        applies = bool(scalar is not None and row.get("state_router_cell_match"))
        row["state_router_rule_version"] = RULE_VERSION
        row["state_router_scalar"] = scalar if applies else None
        row["state_router_applied"] = applies
        base_pnl = _float(row.get("pnl")) or 0.0
        base_notional = _float(row.get("paper_notional_usd")) or 0.0
        if applies:
            row["state_router_base_pnl"] = base_pnl
            row["state_router_incremental_pnl"] = round(base_pnl * (scalar - 1.0), 2)
            row["pnl"] = round(base_pnl * scalar, 2)
            row["paper_notional_usd"] = round(base_notional * scalar, 2)
        adjusted.append(row)
    return adjusted


def _incremental_share(trades: list[dict[str, Any]]) -> float | None:
    rows = [
        r
        for r in trades
        if r.get("state_router_applied")
        and (_float(r.get("state_router_incremental_pnl")) or 0.0) > 0
    ]
    total = sum(_float(r.get("state_router_incremental_pnl")) or 0.0 for r in rows)
    if total <= 0:
        return None
    by_ticker: dict[str, float] = defaultdict(float)
    for r in rows:
        by_ticker[str(r.get("ticker") or "").upper()] += (
            _float(r.get("state_router_incremental_pnl")) or 0.0
        )
    return round(max(by_ticker.values()) / total, 6) if by_ticker else None


def _run_variant(
    *,
    scalar: float | None,
    baselines: dict[str, dict[str, Any]],
    annotated_by_window: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    per_window = OrderedDict()
    all_trades: list[dict[str, Any]] = []
    for label in WINDOWS:
        trades = _apply_tilt(annotated_by_window[label], scalar=scalar)
        before_result = baselines[label]["result"]
        before = baselines[label]["metrics"]
        overlay = framework.sleeve._overlay_from_paper_trades(before_result, trades)
        after = framework.overlay_helper._metrics_with_overlay(before_result, overlay)
        in_cell = [r for r in trades if r.get("state_router_cell_match")]
        applied = [r for r in trades if r.get("state_router_applied")]
        per_window[label] = {
            "before": before,
            "after": after,
            "trade_count": len(trades),
            "in_cell_trade_count": len(in_cell),
            "tilted_trade_count": len(applied),
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "trades": [
                {
                    "ticker": r.get("ticker"),
                    "entry_date": r.get("entry_date"),
                    "exit_date": r.get("exit_date"),
                    "combined_state": r.get("combined_state"),
                    "state_router_applied": r.get("state_router_applied"),
                    "paper_notional_usd": r.get("paper_notional_usd"),
                    "pnl": r.get("pnl"),
                }
                for r in trades
            ],
        }
        all_trades.extend(trades)
    in_cell_all = [r for r in all_trades if r.get("state_router_cell_match")]
    tilted_all = [r for r in all_trades if r.get("state_router_applied")]
    return {
        "variant_name": (
            BASELINE_VARIANT if scalar is None else f"cell_tilt_{str(scalar).replace('.', 'p')}x"
        ),
        "scalar": scalar,
        "per_window": per_window,
        "aggregate_after_ev": round(
            sum(_float(per_window[l]["after"]["expected_value_score"]) or 0.0 for l in WINDOWS), 6
        ),
        "aggregate_after_pnl": round(
            sum(_float(per_window[l]["after"]["total_pnl"]) or 0.0 for l in WINDOWS), 2
        ),
        "in_cell_trade_count_total": len(in_cell_all),
        "tilted_trade_count_total": len(tilted_all),
        "in_cell_windows": sorted({l for l in WINDOWS if per_window[l]["in_cell_trade_count"] > 0}),
        "in_cell_single_ticker_positive_share": r18._single_ticker_positive_share(in_cell_all),
        "incremental_single_ticker_positive_share": _incremental_share(all_trades),
    }


def _gate4(variant: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    ev_delta = {
        l: round(
            (_float(variant["per_window"][l]["after"]["expected_value_score"]) or 0.0)
            - (_float(identity["per_window"][l]["after"]["expected_value_score"]) or 0.0),
            6,
        )
        for l in WINDOWS
    }
    pnl_delta = {
        l: round(
            (_float(variant["per_window"][l]["after"]["total_pnl"]) or 0.0)
            - (_float(identity["per_window"][l]["after"]["total_pnl"]) or 0.0),
            2,
        )
        for l in WINDOWS
    }
    dd_delta = {
        l: round(
            (_float(variant["per_window"][l]["after"]["max_drawdown_pct"]) or 0.0)
            - (_float(identity["per_window"][l]["after"]["max_drawdown_pct"]) or 0.0),
            6,
        )
        for l in WINDOWS
    }
    agg_ev = round(sum(ev_delta.values()), 6)
    agg_pnl = round(sum(pnl_delta.values()), 2)
    improved = sum(1 for v in ev_delta.values() if v > 0)
    regressed = sum(1 for v in ev_delta.values() if v < 0)
    max_dd_worse = max(dd_delta.values()) if dd_delta else 0.0
    in_cell_share = variant["in_cell_single_ticker_positive_share"]
    incr_share = variant["incremental_single_ticker_positive_share"]
    sample_guard = (
        variant["in_cell_trade_count_total"] >= MIN_IN_CELL_TRADES_TOTAL
        and len(variant["in_cell_windows"]) >= MIN_IN_CELL_WINDOWS
    )
    in_cell_conc = in_cell_share is None or in_cell_share <= MAX_SINGLE_TICKER_POSITIVE_SHARE
    incr_conc = incr_share is None or incr_share <= MAX_SINGLE_TICKER_POSITIVE_SHARE
    dd_guard = max_dd_worse <= MAX_DRAWDOWN_WORSE
    passed = (
        agg_ev > 0
        and agg_pnl > 0
        and improved >= MIN_EV_IMPROVED_WINDOWS
        and regressed == 0
        and sample_guard
        and in_cell_conc
        and incr_conc
        and dd_guard
    )
    return {
        "passed": passed,
        "comparator": "unconditional industry_stable_core_flow sleeve overlay (identity variant)",
        "aggregate_ev_delta": agg_ev,
        "aggregate_ev_delta_pct": round(agg_ev / identity["aggregate_after_ev"], 6)
        if identity["aggregate_after_ev"]
        else None,
        "aggregate_pnl_delta": agg_pnl,
        "ev_delta_by_window": ev_delta,
        "pnl_delta_by_window": pnl_delta,
        "max_drawdown_delta_by_window": dd_delta,
        "windows_ev_improved": improved,
        "windows_ev_regressed": regressed,
        "minimum_ev_improved_windows": MIN_EV_IMPROVED_WINDOWS,
        "in_cell_trade_count_total": variant["in_cell_trade_count_total"],
        "tilted_trade_count_total": variant["tilted_trade_count_total"],
        "in_cell_windows": variant["in_cell_windows"],
        "minimum_in_cell_trades_total": MIN_IN_CELL_TRADES_TOTAL,
        "minimum_in_cell_windows": MIN_IN_CELL_WINDOWS,
        "sample_guard_passed": sample_guard,
        "in_cell_single_ticker_positive_share": in_cell_share,
        "in_cell_concentration_guard_passed": in_cell_conc,
        "incremental_single_ticker_positive_share": incr_share,
        "incremental_concentration_guard_passed": incr_conc,
        "max_single_ticker_positive_share": MAX_SINGLE_TICKER_POSITIVE_SHARE,
        "max_drawdown_worse_max": max_dd_worse,
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "drawdown_guard_passed": dd_guard,
    }


def build_payload() -> dict[str, Any]:
    universe = sorted(get_universe())
    sector_entries = framework._load_sector_entries()
    baselines: dict[str, dict[str, Any]] = OrderedDict()
    annotated_by_window: dict[str, list[dict[str, Any]]] = OrderedDict()
    sleeve_audit: dict[str, Any] = OrderedDict()

    for label, cfg in WINDOWS.items():
        print(f"[{label}] core baseline + iscf sleeve trades")
        before_result = framework.shadow._run_baseline(universe, cfg)
        baselines[label] = {
            "result": before_result,
            "metrics": framework.overlay_helper._metrics(before_result),
        }
        core_entries = framework.shadow._baseline_entries(before_result)
        deep_snapshot = exp008._load_window_snapshot_deep(
            cfg=cfg, eligible_tickers=set(sector_entries)
        )
        window_sector_entries = {
            t: m for t, m in sector_entries.items() if t in deep_snapshot
        }
        candidate_universe = alloc._candidate_universe_from_sector_entries(
            window_sector_entries
        )
        trades, audit = build_industry_stable_core_flow_historical_trades(
            ohlcv_by_ticker=deep_snapshot,
            core_entries_by_date=core_entries,
            windows=OrderedDict([(label, cfg)]),
            candidate_universe=candidate_universe,
            sector_entries=window_sector_entries,
        )
        annotated = _annotate(trades, label=label)
        annotated_by_window[label] = annotated
        sleeve_audit[label] = {
            "sleeve_trade_count": len(annotated),
            "in_cell_count": sum(1 for r in annotated if r.get("state_router_cell_match")),
            "state_counts": dict(
                sorted(
                    {
                        s: sum(1 for r in annotated if r.get("combined_state") == s)
                        for s in {r.get("combined_state") for r in annotated}
                        if s
                    }.items()
                )
            ),
        }

    identity = _run_variant(scalar=None, baselines=baselines, annotated_by_window=annotated_by_window)
    variants = [identity] + [
        _run_variant(scalar=s, baselines=baselines, annotated_by_window=annotated_by_window)
        for s in TILT_SCALARS
    ]
    sweep = []
    for v in variants:
        g4 = None if v["variant_name"] == BASELINE_VARIANT else _gate4(v, identity)
        sweep.append(
            {
                "variant_name": v["variant_name"],
                "scalar": v["scalar"],
                "is_identity_control": v["variant_name"] == BASELINE_VARIANT,
                "aggregate_after_ev": v["aggregate_after_ev"],
                "aggregate_after_pnl": v["aggregate_after_pnl"],
                "in_cell_trade_count_total": v["in_cell_trade_count_total"],
                "in_cell_single_ticker_positive_share": v["in_cell_single_ticker_positive_share"],
                "incremental_single_ticker_positive_share": v["incremental_single_ticker_positive_share"],
                "gate4": g4,
            }
        )

    candidates = [r for r in sweep if not r["is_identity_control"]]
    passing = [r for r in candidates if r["gate4"]["passed"]]
    best = max(
        passing if passing else candidates,
        key=lambda r: (
            r["gate4"]["aggregate_ev_delta"],
            r["gate4"]["aggregate_pnl_delta"],
            -r["gate4"]["max_drawdown_worse_max"],
        ),
    )
    best_variant = next(v for v in variants if v["variant_name"] == best["variant_name"])
    passed = bool(best["gate4"]["passed"])
    decision = (
        "accepted_iscf_state_tilt_paper_pending_forward"
        if passed
        else "rejected_iscf_state_tilt"
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "lane": "alpha_search",
        "status": "accepted" if passed else "rejected",
        "decision": decision,
        "hypothesis": (
            "The accepted industry_stable_core_flow default-off paper sleeve earns "
            "its edge in the mixed|balanced|normal market state; a bounded notional "
            "tilt on its in-state rows raises its overlay EV without changing "
            "entries, exits, or live orders."
        ),
        "alpha_hypothesis": {
            "category": "capital allocation / regime router",
            "entry_exit_ranking_or_allocation": "default-off paper allocation",
            "playbook_alignment": (
                "Final step of the exp-20260606-022 -> 027 regime-router line; the "
                "cell survived the ex-top-ticker robustness screen, and the tilt "
                "lands on the sleeve itself because the source is crowded out of "
                "the accepted allocator (exp-20260611-005 selected 0 rows)."
            ),
        },
        "change_type": "default_off_paper_allocation",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "rule_version": RULE_VERSION,
        "parameters": {
            "router_cell": ROUTER_CELL,
            "tilt_scalars_tested": list(TILT_SCALARS),
            "best_variant": best["variant_name"],
            "best_scalar": best["scalar"],
            "landing_point": "industry_stable_core_flow sleeve overlay (not allocator)",
            "landing_point_reason": (
                "exp-20260611-005 accepted allocator selected 0 "
                "industry_stable_core_flow rows; daily-top1 priority crowds the "
                "source out, so the sleeve's own default-off overlay is the only "
                "place its rows exist"
            ),
            "state_classifier": "exp-20260606-022 _state_for_entry_date, prior-close PIT",
            "locked_variables": [
                "sleeve candidate generation and gates",
                "sleeve entry/exit timing and hold days",
                "state classifier thresholds",
                "core entries/exits/sizing",
                "all other sleeves and the allocator",
                "live/default orders",
            ],
        },
        "circularity_disclosure": (
            "The cell and windows were screened together in exp-20260612-027, so a "
            "positive Gate 4 is partially in-sample; verdict caps at "
            "accepted_paper_pending_forward and activation evidence must come from "
            "closed forward replacement-value rows."
        ),
        "sleeve_audit": sleeve_audit,
        "gate1": {
            "comparator": "unconditional industry_stable_core_flow sleeve (identity variant)",
            "note": (
                "Identity overlay is the sleeve's own accepted default-off behavior "
                "(exp-20260608-007); the tilt is the only change."
            ),
        },
        "gate2": {
            "runtime_fields": [
                "entry_date",
                "exit_date",
                "pnl",
                "paper_notional_usd",
                "SPY/QQQ OHLCV at prior close (state features)",
            ],
            "passed": True,
        },
        "gate3": {
            "new_filter_added": False,
            "note": "No candidate gate changed; only paper notional of in-cell rows changes.",
        },
        "gate4": best["gate4"],
        "sweep_summary": sweep,
        "best_variant_detail": {
            "per_window": {
                l: {
                    "after": best_variant["per_window"][l]["after"],
                    "in_cell_trade_count": best_variant["per_window"][l]["in_cell_trade_count"],
                    "tilted_trade_count": best_variant["per_window"][l]["tilted_trade_count"],
                    "trades": best_variant["per_window"][l]["trades"],
                }
                for l in WINDOWS
            }
        },
        "history_check": {
            "exp-20260612-027": "Isolated this cell as the sole ex-top-ticker survivor.",
            "exp-20260612-018/020": "Consensus-cell tilt rejected on APP concentration; this cell's top ticker TOST is 20.9%.",
            "exp-20260608-007": "Accepted the unconditional industry_stable_core_flow sleeve (identity comparator).",
            "exp-20260611-005": "Accepted allocator selects 0 rows from this source -> landing point is the sleeve.",
            "anti_repeat": (
                "Not an allocator source-priority retune (those are frozen/rejected); "
                "single new variable is the sleeve-level state-conditional notional tilt."
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
                "quant/industry_stable_core_flow_paper_sleeve.py with a daily "
                "market-state field and a focused parity test; if rejected, nothing changes."
            ),
        },
        "execution_envelope": {
            "scope": "default-off paper only, trade_enabled=False",
            "notional": "in-cell rows scale from $4,000 to at most $6,000; other rows unchanged",
            "capital_cap": "sleeve max 8 active / daily 1 admission unchanged",
            "liquidity_slippage": "fill model and round-trip costs unchanged",
            "portfolio_displacement": "same rows, different paper weight",
            "kill_switch": "sleeve paper config; no live orders exist",
            "live_readiness": "not live-eligible; forward rows + Gate 5 required",
        },
        "protocol_answers": {
            "1_alpha_hypothesis": "capital allocation / regime router: tilt iscf sleeve notional toward its mixed|balanced|normal rows.",
            "2_history_check": "exp-20260612-027 isolated the cell; exp-20260611-005 forced the sleeve landing point; consensus-cell concentration failure does not apply (TOST 20.9%).",
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "vs unconditional sleeve overlay: aggregate EV/PnL delta > 0, >=2 EV-improved "
                "windows, zero regressed, in-cell tilted trades >=18 across all 3 windows, BOTH "
                "in-cell and incremental single-ticker positive shares <=50%, max DD drift <=0.5pp; "
                "verdict caps at accepted_paper_pending_forward."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260613_005_iscf_state_tilt.py"
            ),
        },
        "anti_js": "No JavaScript was used.",
        "related_files": [
            "quant/experiments/exp_20260613_005_iscf_state_tilt.py",
            "data/experiments/exp-20260613-005/exp_20260613_005_iscf_state_tilt.json",
            "quant/industry_stable_core_flow_paper_sleeve.py",
            "quant/experiments/exp_20260612_027_broad_state_source_attribution.py",
        ],
    }
    return r18._safe(payload)


def main() -> None:
    payload = build_payload()
    r18._write_json(OUT_JSON, payload)
    identity = next(r for r in payload["sweep_summary"] if r["is_identity_control"])
    best_name = payload["parameters"]["best_variant"]
    best_row = next(r for r in payload["sweep_summary"] if r["variant_name"] == best_name)
    r18._write_json(
        BEFORE_AGG_JSON,
        {
            "expected_value_score": identity["aggregate_after_ev"],
            "total_pnl": identity["aggregate_after_pnl"],
            "note": "aggregate unconditional iscf sleeve overlay across three fixed windows",
        },
    )
    r18._write_json(
        AFTER_AGG_JSON,
        {
            "expected_value_score": best_row["aggregate_after_ev"],
            "total_pnl": best_row["aggregate_after_pnl"],
            "note": "aggregate best state-tilted iscf sleeve overlay across three fixed windows",
        },
    )
    print(json.dumps(payload["gate4"], indent=2, sort_keys=True))
    print(json.dumps(payload["sleeve_audit"], indent=2, sort_keys=True))
    print(
        f"{EXPERIMENT_ID} {payload['decision']} best={best_name} "
        f"dEV={payload['gate4']['aggregate_ev_delta']:+.4f} "
        f"dPnL=${payload['gate4']['aggregate_pnl_delta']:+,.2f} "
        f"inCell={payload['gate4']['in_cell_single_ticker_positive_share']} "
        f"incr={payload['gate4']['incremental_single_ticker_positive_share']}"
    )


if __name__ == "__main__":
    main()
