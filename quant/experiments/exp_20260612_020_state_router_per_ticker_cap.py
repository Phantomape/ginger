"""exp-20260612-020: state router consensus tilt with per-ticker repetition cap.

Alpha search (regime router). Successor to exp-20260612-018, which proved the
mixed|balanced|normal state tilt direction on the accepted lagged cross-source
consensus sleeve (+7.4% aggregate EV, zero window regression, improved
drawdown) and was rejected solely because APP carried 51.4% of in-cell
positive PnL -- a scalar-invariant property no uniform tilt could fix.

This run tests ONE new predeclared decision hypothesis: the 1.5x tilt applies
only to a ticker's first N in-cell entries within a trailing 60-trading-day
window (N in {2, 3}). Repetition-capped tilting dilutes single-name dependence
while keeping the diversified majority of the cell tilted. Everything else is
frozen exactly as in exp-20260612-018: the 606-022 state classifier, the
single cell, the accepted sleeve rows, entries, exits, and live orders.

Circularity disclosure: the cell was screened by exp-20260606-022 on the same
three canonical windows, so any pass is capped at
accepted_paper_pending_forward; activation evidence must come from closed
forward replacement-value rows.

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


EXPERIMENT_ID = "exp-20260612-020"
STEM = "state_router_per_ticker_cap"
TRIAL_FAMILY = "market_state_conditioned_sleeve_router"
TRIAL_VARIANT_ID = "consensus_tilt_per_ticker_repetition_cap_v1"
CHANGED_VARIABLE = "state_router_consensus_tilt_with_per_ticker_repetition_cap"
RULE_VERSION = "consensus_state_router_per_ticker_cap_v1"

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260612_018_state_router_consensus_tilt as prior  # noqa: E402

base = prior.base
same_day = prior.same_day
overlay_helper = prior.overlay_helper
statemod = prior.statemod

WINDOWS = prior.WINDOWS
ROUTER_CELL = prior.ROUTER_CELL
TILT_SCALAR = 1.5
PER_TICKER_CAPS = (2, 3)
CAP_LOOKBACK_TRADING_DAYS = 60
BASELINE_VARIANT = "accepted_unconditional_consensus_sleeve"

MIN_TILTED_TRADES_TOTAL = 18
MIN_TILTED_WINDOWS = 3
MIN_EV_IMPROVED_WINDOWS = 2
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_TICKER_POSITIVE_SHARE = 0.50

OUT_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / EXPERIMENT_ID
    / f"exp_20260612_020_{STEM}.json"
)
BEFORE_AGG_JSON = OUT_JSON.parent / f"exp_20260612_020_{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_JSON.parent / f"exp_20260612_020_{STEM}_after_aggregate.json"


def _apply_capped_tilt(
    trades: list[dict[str, Any]],
    *,
    cap: int | None,
    trading_dates: list[str],
) -> list[dict[str, Any]]:
    """Tilt only a ticker's first `cap` in-cell entries per trailing 60 sessions.

    The repetition count uses in-cell entry events (cell match, tilted or not)
    known at entry time, so the rule is PIT-safe and reproducible by a daily
    counter in production state.
    """
    date_pos = {value: idx for idx, value in enumerate(trading_dates)}
    ordered = sorted(trades, key=lambda row: (str(row.get("entry_date") or ""), str(row.get("ticker") or "")))
    in_cell_entries_by_ticker: dict[str, list[int]] = defaultdict(list)
    adjusted = []
    for trade in ordered:
        row = dict(trade)
        ticker = str(row.get("ticker") or "").upper()
        entry_pos = date_pos.get(str(row.get("entry_date") or ""))
        in_cell = bool(row.get("state_router_cell_match"))
        prior_in_cell = 0
        if in_cell and entry_pos is not None:
            prior_in_cell = sum(
                1
                for pos in in_cell_entries_by_ticker[ticker]
                if entry_pos - pos <= CAP_LOOKBACK_TRADING_DAYS
            )
        applies = bool(
            cap is not None
            and in_cell
            and entry_pos is not None
            and prior_in_cell < cap
        )
        row["state_router_rule_version"] = RULE_VERSION
        row["state_router_cell"] = ROUTER_CELL
        row["state_router_per_ticker_cap"] = cap
        row["state_router_cap_lookback_td"] = CAP_LOOKBACK_TRADING_DAYS
        row["state_router_prior_in_cell_entries_60td"] = prior_in_cell if in_cell else None
        row["state_router_scalar"] = TILT_SCALAR if applies else None
        row["state_router_applied"] = applies
        if in_cell and entry_pos is not None:
            in_cell_entries_by_ticker[ticker].append(entry_pos)
        if applies:
            base_notional = float(row.get("paper_notional_usd") or 0.0)
            base_pnl = float(row.get("pnl") or 0.0)
            row["state_router_base_notional"] = base_notional
            row["state_router_base_pnl"] = base_pnl
            row["state_router_incremental_pnl"] = round(base_pnl * (TILT_SCALAR - 1.0), 2)
            row["paper_notional_usd"] = round(base_notional * TILT_SCALAR, 2)
            row["pnl"] = round(base_pnl * TILT_SCALAR, 2)
        adjusted.append(row)
    return adjusted


def _incremental_positive_share(trades: list[dict[str, Any]]) -> float | None:
    rows = [
        row
        for row in trades
        if row.get("state_router_applied")
        and float(row.get("state_router_incremental_pnl") or 0.0) > 0
    ]
    total = sum(float(row.get("state_router_incremental_pnl") or 0.0) for row in rows)
    if total <= 0:
        return None
    by_ticker: dict[str, float] = defaultdict(float)
    for row in rows:
        by_ticker[str(row.get("ticker") or "").upper()] += float(
            row.get("state_router_incremental_pnl") or 0.0
        )
    return round(max(by_ticker.values()) / total, 6) if by_ticker else None


def _run_variant(
    *,
    cap: int | None,
    baselines: dict[str, dict[str, Any]],
    annotated_by_window: dict[str, list[dict[str, Any]]],
    trading_dates_by_window: dict[str, list[str]],
) -> dict[str, Any]:
    per_window = OrderedDict()
    all_trades: list[dict[str, Any]] = []
    for label in WINDOWS:
        trades = _apply_capped_tilt(
            annotated_by_window[label],
            cap=cap,
            trading_dates=trading_dates_by_window[label],
        )
        before_result = baselines[label]["result"]
        before = baselines[label]["metrics"]
        overlay = base._overlay_from_paper_trades(before_result, trades)
        after = overlay_helper._metrics_with_overlay(before_result, overlay)
        applied = [row for row in trades if row.get("state_router_applied")]
        in_cell = [row for row in trades if row.get("state_router_cell_match")]
        per_window[label] = {
            "before": before,
            "after": after,
            "trade_count": len(trades),
            "in_cell_trade_count": len(in_cell),
            "tilted_trade_count": len(applied),
            "tilted_by_ticker": dict(
                sorted(
                    {
                        t: sum(1 for r in applied if str(r.get("ticker") or "").upper() == t)
                        for t in {str(r.get("ticker") or "").upper() for r in applied}
                    }.items()
                )
            ),
            "sleeve_pnl": round(sum(float(r.get("pnl") or 0.0) for r in trades), 2),
            "trades": [
                {
                    "ticker": row.get("ticker"),
                    "entry_date": row.get("entry_date"),
                    "exit_date": row.get("exit_date"),
                    "combined_state": row.get("combined_state"),
                    "state_router_prior_in_cell_entries_60td": row.get(
                        "state_router_prior_in_cell_entries_60td"
                    ),
                    "state_router_applied": row.get("state_router_applied"),
                    "paper_notional_usd": row.get("paper_notional_usd"),
                    "pnl": row.get("pnl"),
                    "state_router_incremental_pnl": row.get("state_router_incremental_pnl"),
                }
                for row in trades
            ],
        }
        all_trades.extend(trades)
    in_cell_all = [row for row in all_trades if row.get("state_router_cell_match")]
    tilted_all = [row for row in all_trades if row.get("state_router_applied")]
    return {
        "variant_name": (
            BASELINE_VARIANT if cap is None else f"cap_{cap}_per_ticker_60td_1p5x"
        ),
        "per_ticker_cap": cap,
        "scalar": None if cap is None else TILT_SCALAR,
        "per_window": per_window,
        "aggregate_after_ev": round(
            sum(float(per_window[l]["after"]["expected_value_score"] or 0.0) for l in WINDOWS),
            6,
        ),
        "aggregate_after_pnl": round(
            sum(float(per_window[l]["after"]["total_pnl"] or 0.0) for l in WINDOWS),
            2,
        ),
        "tilted_trade_count_total": len(tilted_all),
        "tilted_windows": sorted(
            {l for l in WINDOWS if per_window[l]["tilted_trade_count"] > 0}
        ),
        "in_cell_single_ticker_positive_share": prior._single_ticker_positive_share(
            in_cell_all
        ),
        "incremental_single_ticker_positive_share": _incremental_positive_share(
            all_trades
        ),
    }


def _gate4(variant: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
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
    in_cell_share = variant["in_cell_single_ticker_positive_share"]
    incremental_share = variant["incremental_single_ticker_positive_share"]
    sample_guard = (
        variant["tilted_trade_count_total"] >= MIN_TILTED_TRADES_TOTAL
        and len(variant["tilted_windows"]) >= MIN_TILTED_WINDOWS
    )
    in_cell_concentration_guard = (
        in_cell_share is None or in_cell_share <= MAX_SINGLE_TICKER_POSITIVE_SHARE
    )
    incremental_concentration_guard = (
        incremental_share is None
        or incremental_share <= MAX_SINGLE_TICKER_POSITIVE_SHARE
    )
    drawdown_guard = max_dd_worse <= MAX_DRAWDOWN_WORSE
    passed = (
        aggregate_ev_delta > 0
        and aggregate_pnl_delta > 0
        and windows_ev_improved >= MIN_EV_IMPROVED_WINDOWS
        and windows_ev_regressed == 0
        and sample_guard
        and in_cell_concentration_guard
        and incremental_concentration_guard
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
        "tilted_trade_count_total": variant["tilted_trade_count_total"],
        "tilted_windows": variant["tilted_windows"],
        "minimum_tilted_trades_total": MIN_TILTED_TRADES_TOTAL,
        "minimum_tilted_windows": MIN_TILTED_WINDOWS,
        "sample_guard_passed": sample_guard,
        "in_cell_single_ticker_positive_share": in_cell_share,
        "in_cell_concentration_guard_passed": in_cell_concentration_guard,
        "incremental_single_ticker_positive_share": incremental_share,
        "incremental_concentration_guard_passed": incremental_concentration_guard,
        "max_single_ticker_positive_share": MAX_SINGLE_TICKER_POSITIVE_SHARE,
        "max_drawdown_worse_max": max_dd_worse,
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "drawdown_guard_passed": drawdown_guard,
    }


def build_payload() -> dict[str, Any]:
    artifact = json.loads(
        (
            REPO_ROOT
            / "data/experiments/exp-20260604-008/lagged_independent_source_consensus.json"
        ).read_text(encoding="utf-8")
    )
    trades_by_window = artifact["target_trades_by_window"]

    baselines = same_day.prior._load_baselines()
    annotated_by_window: dict[str, list[dict[str, Any]]] = OrderedDict()
    trading_dates_by_window: dict[str, list[str]] = OrderedDict()
    for label, cfg in WINDOWS.items():
        snapshot = base.shadow._load_snapshot(cfg["snapshot"])
        annotated_by_window[label] = prior._annotate_state(
            trades_by_window[label], snapshot=snapshot
        )
        trading_dates_by_window[label] = statemod._trading_dates(snapshot)

    identity = _run_variant(
        cap=None,
        baselines=baselines,
        annotated_by_window=annotated_by_window,
        trading_dates_by_window=trading_dates_by_window,
    )
    parity = prior._identity_parity_check(identity)
    if not parity["passed"]:
        raise RuntimeError(f"Identity parity failed: {json.dumps(parity, indent=2)}")

    variants = [identity] + [
        _run_variant(
            cap=cap,
            baselines=baselines,
            annotated_by_window=annotated_by_window,
            trading_dates_by_window=trading_dates_by_window,
        )
        for cap in PER_TICKER_CAPS
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
                "per_ticker_cap": variant["per_ticker_cap"],
                "scalar": variant["scalar"],
                "is_identity_control": variant["variant_name"] == BASELINE_VARIANT,
                "aggregate_after_ev": variant["aggregate_after_ev"],
                "aggregate_after_pnl": variant["aggregate_after_pnl"],
                "tilted_trade_count_total": variant["tilted_trade_count_total"],
                "in_cell_single_ticker_positive_share": variant[
                    "in_cell_single_ticker_positive_share"
                ],
                "incremental_single_ticker_positive_share": variant[
                    "incremental_single_ticker_positive_share"
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
        "accepted_state_router_per_ticker_cap_paper_pending_forward"
        if passed
        else "rejected_state_router_per_ticker_cap"
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
            "The mixed|balanced|normal state tilt on the accepted consensus "
            "sleeve becomes acceptable when only a ticker's first N in-cell "
            "entries per trailing 60 trading days receive the 1.5x tilt, "
            "diluting single-name dependence below the 50% concentration guard."
        ),
        "alpha_hypothesis": {
            "category": "capital allocation / regime router",
            "entry_exit_ranking_or_allocation": "default-off paper allocation",
            "playbook_alignment": (
                "Successor to exp-20260612-018 with the one new predeclared "
                "variable its closeout demanded: a per-ticker repetition cap."
            ),
        },
        "change_type": "default_off_paper_allocation",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "rule_version": RULE_VERSION,
        "parameters": {
            "router_cell": ROUTER_CELL,
            "tilt_scalar": TILT_SCALAR,
            "per_ticker_caps_tested": list(PER_TICKER_CAPS),
            "cap_lookback_trading_days": CAP_LOOKBACK_TRADING_DAYS,
            "cap_counting_rule": (
                "prior in-cell entries of the same ticker within the trailing "
                "60 trading days, counted at entry time (PIT)"
            ),
            "best_variant": best["variant_name"],
            "best_per_ticker_cap": best["per_ticker_cap"],
            "locked_variables": [
                "state classifier thresholds (frozen 606-022)",
                "router cell (mixed|balanced|normal)",
                "tilt scalar (1.5x, from exp-20260612-018 best variant)",
                "consensus sleeve candidate generation and exits",
                "all other sleeves and sources",
                "core entries/exits/sizing",
                "live/default orders",
            ],
        },
        "circularity_disclosure": (
            "The router cell was screened by exp-20260606-022 on the same "
            "three canonical windows; the tilt scalar was selected by "
            "exp-20260612-018 on the same windows. Any pass is capped at "
            "accepted_paper_pending_forward; activation evidence must come "
            "from closed forward replacement-value rows."
        ),
        "identity_parity_check": parity,
        "gate1": {
            "baseline_artifact": (
                "data/experiments/exp-20260604-008/lagged_independent_source_consensus.json"
            ),
            "baseline_note": (
                "Accepted unconditional consensus sleeve after-metrics, "
                "reproduced by the identity variant within tolerance."
            ),
        },
        "gate2": {
            "runtime_fields": [
                "entry_date",
                "exit_date",
                "pnl",
                "paper_notional_usd",
                "SPY/QQQ OHLCV at prior close (state features)",
                "per-ticker in-cell entry counter (trailing 60 trading days)",
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
                    "tilted_trade_count": best_variant["per_window"][label][
                        "tilted_trade_count"
                    ],
                    "tilted_by_ticker": best_variant["per_window"][label][
                        "tilted_by_ticker"
                    ],
                    "sleeve_pnl": best_variant["per_window"][label]["sleeve_pnl"],
                    "trades": best_variant["per_window"][label]["trades"],
                }
                for label in WINDOWS
            },
        },
        "history_check": {
            "exp-20260612-018": (
                "Uniform tilt rejected solely on APP 51.4% in-cell "
                "concentration; its closeout named the per-ticker cap as the "
                "allowed next hypothesis. Scalar frozen at its best variant."
            ),
            "exp-20260606-022": "Screened the cell; queued the router Gate 1-4.",
            "exp-20260604-008/009": "Accepted unconditional sleeve = baseline and comparator.",
            "anti_repeat": (
                "Not a rerun of the rejected uniform tilt: the per-ticker "
                "repetition cap is the single new decision variable; cell, "
                "scalar, classifier, and sleeve rows are all frozen."
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
                "Replay verdict only. If accepted, the capped tilt must be "
                "added to quant/free_data_cross_source_consensus_paper_sleeve.py "
                "with a daily market-state field, a per-ticker counter in "
                "sleeve state, and a focused parity test; if rejected, "
                "nothing changes."
            ),
        },
        "execution_envelope": {
            "scope": "default-off paper only, trade_enabled=False",
            "notional": (
                "capped in-cell rows scale from $4,000 to $6,000 paper "
                "notional; repeated-name and out-of-cell rows unchanged"
            ),
            "capital_cap": "per-day admission caps of the accepted sleeve unchanged",
            "liquidity_slippage": "fill model and round-trip costs unchanged",
            "portfolio_displacement": "same rows, different paper weight; no displacement change",
            "kill_switch": "sleeve paper config; no live orders exist",
            "live_readiness": "not live-eligible; forward rows + Gate 5 required",
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "capital allocation / regime router: repetition-capped "
                "state-conditional tilt fixes the single-name concentration "
                "that rejected exp-20260612-018."
            ),
            "2_history_check": (
                "exp-20260612-018 rejected on concentration only and "
                "predeclared this cap as the allowed retry; cell/scalar/"
                "classifier frozen from prior experiments."
            ),
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "vs accepted unconditional sleeve: aggregate EV/PnL delta > 0, "
                ">=2 EV-improved windows, zero regressed, tilted trades >=18 "
                "across all 3 windows, BOTH in-cell and tilt-incremental "
                "single-ticker positive shares <=50%, max DD drift <=0.5pp; "
                "verdict capped at accepted_paper_pending_forward."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260612_020_state_router_per_ticker_cap.py"
            ),
        },
        "anti_js": "No JavaScript was used.",
        "related_files": [
            "quant/experiments/exp_20260612_020_state_router_per_ticker_cap.py",
            "data/experiments/exp-20260612-020/exp_20260612_020_state_router_per_ticker_cap.json",
            "quant/experiments/exp_20260612_018_state_router_consensus_tilt.py",
            "data/experiments/exp-20260604-008/lagged_independent_source_consensus.json",
            "quant/free_data_cross_source_consensus_paper_sleeve.py",
        ],
    }
    return prior._safe(payload)


def main() -> None:
    payload = build_payload()
    prior._write_json(OUT_JSON, payload)
    identity = next(row for row in payload["sweep_summary"] if row["is_identity_control"])
    best_name = payload["parameters"]["best_variant"]
    best_row = next(
        row for row in payload["sweep_summary"] if row["variant_name"] == best_name
    )
    prior._write_json(
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
    prior._write_json(
        AFTER_AGG_JSON,
        {
            "expected_value_score": best_row["aggregate_after_ev"],
            "total_pnl": best_row["aggregate_after_pnl"],
            "note": (
                "aggregate best per-ticker-capped router variant across "
                "docs/backtesting.md three fixed windows"
            ),
        },
    )
    print(json.dumps(payload["gate4"], indent=2, sort_keys=True))
    print(
        f"{EXPERIMENT_ID} {payload['decision']} best={best_name} "
        f"dEV={payload['gate4']['aggregate_ev_delta']:+.4f} "
        f"dPnL=${payload['gate4']['aggregate_pnl_delta']:+,.2f} "
        f"inCellShare={payload['gate4']['in_cell_single_ticker_positive_share']} "
        f"incrShare={payload['gate4']['incremental_single_ticker_positive_share']}"
    )


if __name__ == "__main__":
    main()
