"""exp-20260519-027: state-surface sleeve capacity notional.

Alpha search. Freezes the accepted state-surface paper stack through
exp-20260519-026, then tests one capital-allocation variable: all already
selected default-off state-surface paper candidates receive a bounded sleeve
capacity scalar.

Core entries, exits, candidate eligibility, queue ranking, hold days, active
capacity, LLM/news, and live/default orders are unchanged.

No JavaScript is used.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260519_026_state_surface_rank_queue_alignment_notional as prev


EXPERIMENT_ID = "exp-20260519-027"
EXPERIMENT_SLUG = "state_surface_sleeve_capacity_notional"

REPO_ROOT = prev.REPO_ROOT
WINDOWS = prev.WINDOWS
BASELINE_VARIANT = "accepted_rank_queue_alignment_notional"
MIN_SELECTED_TRADES = prev.MIN_SELECTED_TRADES
MIN_ADJUSTED_TRADES = 20
MIN_ADJUSTED_WINDOWS = 3
MIN_EV_IMPROVED_WINDOWS = 3
MAX_DRAWDOWN_WORSE = prev.MAX_DRAWDOWN_WORSE
MAX_SINGLE_TICKER_POSITIVE_SHARE = prev.MAX_SINGLE_TICKER_POSITIVE_SHARE
RULE_VERSION = "state_surface_sleeve_capacity_notional_v1"

CAPACITY_VARIANTS: OrderedDict[str, dict[str, Any]] = OrderedDict(
    [
        (
            BASELINE_VARIANT,
            {
                "scalar": None,
                "aggression_order": 0,
                "description": "accepted stack through rank/queue alignment",
            },
        ),
        (
            "sleeve_capacity_scalar_103",
            {
                "scalar": 1.03,
                "aggression_order": 1,
                "description": "all selected state-surface paper candidates receive 3% capacity support",
            },
        ),
        (
            "sleeve_capacity_scalar_105",
            {
                "scalar": 1.05,
                "aggression_order": 2,
                "description": "all selected state-surface paper candidates receive 5% capacity support",
            },
        ),
        (
            "sleeve_capacity_scalar_108",
            {
                "scalar": 1.08,
                "aggression_order": 3,
                "description": "all selected state-surface paper candidates receive 8% capacity support",
            },
        ),
        (
            "sleeve_capacity_scalar_110",
            {
                "scalar": 1.10,
                "aggression_order": 4,
                "description": "all selected state-surface paper candidates receive 10% capacity support",
            },
        ),
        (
            "sleeve_capacity_scalar_115",
            {
                "scalar": 1.15,
                "aggression_order": 5,
                "description": "all selected state-surface paper candidates receive 15% capacity support",
            },
        ),
        (
            "sleeve_capacity_scalar_120",
            {
                "scalar": 1.20,
                "aggression_order": 6,
                "description": "all selected state-surface paper candidates receive 20% capacity support",
            },
        ),
    ]
)

BASELINE_JSON = prev.OUT_JSON
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(prev._safe(payload), sort_keys=True)
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


def _profile_name(scalar: float) -> str:
    scalar_text = str(round(float(scalar), 6)).rstrip("0").rstrip(".")
    return f"sleeve_capacity_{scalar_text.replace('.', 'p')}x"


def _apply_sleeve_capacity(
    trades: list[dict[str, Any]],
    *,
    variant_name: str,
    variant: dict[str, Any],
) -> list[dict[str, Any]]:
    scalar = prev._float(variant.get("scalar"))
    adjusted: list[dict[str, Any]] = []
    for trade in trades:
        row = dict(trade)
        row["features"] = dict(row.get("features") or {})
        applies = variant_name != BASELINE_VARIANT and scalar is not None
        row["sleeve_capacity_variant"] = variant_name
        row["sleeve_capacity_rule_version"] = RULE_VERSION
        row["rank_notional_sleeve_capacity_rule_version"] = RULE_VERSION
        row["sleeve_capacity_applied"] = bool(applies)
        row["sleeve_capacity_configured_scalar"] = scalar
        row["sleeve_capacity_scalar"] = scalar if applies else None
        row["sleeve_capacity_profile_name"] = (
            _profile_name(scalar)
            if variant_name != BASELINE_VARIANT and scalar is not None
            else None
        )
        row["sleeve_capacity_base_multiplier"] = prev._float(
            row.get("rank_notional_multiplier")
        )
        if applies:
            base_notional = float(row.get("notional") or 0.0)
            new_notional = round(base_notional * float(scalar), 2)
            entry_open = float(row["entry_open"])
            net_return = float(row["net_return_pct"])
            row["sleeve_capacity_base_notional"] = base_notional
            row["notional"] = new_notional
            row["shares"] = new_notional / entry_open
            row["pnl"] = round(new_notional * net_return, 2)
            base_multiplier = prev._float(row.get("rank_notional_multiplier"))
            if base_multiplier is not None:
                row["rank_notional_multiplier"] = round(
                    base_multiplier * float(scalar),
                    6,
                )
        adjusted.append(row)
    return adjusted


def _selected_trade_rows(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = prev._selected_trade_rows(trades)
    for row, trade in zip(rows, trades):
        row["sleeve_capacity_applied"] = trade.get("sleeve_capacity_applied")
        row["sleeve_capacity_scalar"] = trade.get("sleeve_capacity_scalar")
        row["sleeve_capacity_base_multiplier"] = trade.get(
            "sleeve_capacity_base_multiplier"
        )
    return rows


def _variant_payload(
    *,
    variant_name: str,
    variant: dict[str, Any],
    baseline_payload: dict[str, Any],
    baseline_trades_by_window: dict[str, list[dict[str, Any]]],
    core_curves: dict[str, list[tuple[str, float]]],
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    metrics: dict[str, dict[str, Any]] = OrderedDict()
    surface_sleeve: dict[str, dict[str, Any]] = OrderedDict()
    selected_all: list[dict[str, Any]] = []
    for label, window in WINDOWS.items():
        baseline_trades = baseline_trades_by_window[label]
        selected = _apply_sleeve_capacity(
            baseline_trades,
            variant_name=variant_name,
            variant=variant,
        )
        if variant_name == BASELINE_VARIANT:
            metrics[label] = baseline_payload["after_metrics"][label]
        else:
            event_curve = prev._event_equity_curve_variable_notional(
                selected,
                prices=prices,
                start=window["start"],
                end=window["end"],
            )
            metrics[label] = prev._metrics_from_core_curve(
                baseline_metrics=baseline_payload["after_metrics"][label],
                core_curve=core_curves[label],
                event_curve=event_curve,
                event_trades=selected,
                baseline_event_trades=baseline_trades,
            )
        selected_all.extend(selected)
        applied = [row for row in selected if row.get("sleeve_capacity_applied")]
        surface_sleeve[label] = {
            "selected_trade_count": len(selected),
            "sleeve_capacity_adjusted_trade_count": len(applied),
            "sleeve_capacity_adjusted_pnl": round(
                sum(float(row.get("pnl") or 0.0) for row in applied),
                2,
            ),
            "selected_pnl": round(
                sum(float(row.get("pnl") or 0.0) for row in selected),
                2,
            ),
            "selected_win_rate": round(
                sum(1 for row in selected if float(row.get("pnl") or 0.0) > 0)
                / len(selected),
                4,
            )
            if selected
            else None,
            "selected_trades": _selected_trade_rows(selected),
        }
    applied_all = [row for row in selected_all if row.get("sleeve_capacity_applied")]
    applied_windows = {
        str(row.get("window")) for row in applied_all if row.get("window")
    }
    return {
        "variant_name": variant_name,
        "variant_type": "sleeve_capacity_notional_profile",
        "scalar": variant.get("scalar"),
        "aggression_order": variant.get("aggression_order"),
        "description": variant.get("description"),
        "metrics": metrics,
        "surface_sleeve": surface_sleeve,
        "selected_trades": selected_all,
        "selected_trade_count": len(selected_all),
        "sleeve_capacity_adjusted_trade_count": len(applied_all),
        "sleeve_capacity_adjusted_windows": sorted(applied_windows),
        "single_ticker_positive_share": prev._single_ticker_positive_share(
            selected_all
        ),
    }


def _gate4_for_variant(
    *,
    baseline_metrics: dict[str, dict[str, Any]],
    baseline_share: float | None,
    variant: dict[str, Any],
) -> dict[str, Any]:
    delta = prev._aggregate_delta(baseline_metrics, variant["metrics"])
    sample_guard_passed = variant["selected_trade_count"] >= MIN_SELECTED_TRADES
    adjusted_guard_passed = (
        variant["sleeve_capacity_adjusted_trade_count"] >= MIN_ADJUSTED_TRADES
        and len(variant["sleeve_capacity_adjusted_windows"]) >= MIN_ADJUSTED_WINDOWS
    )
    concentration_guard_passed = (
        variant["single_ticker_positive_share"] is None
        or variant["single_ticker_positive_share"]
        <= MAX_SINGLE_TICKER_POSITIVE_SHARE
    )
    drawdown_guard_passed = delta["max_drawdown_worse_max"] <= MAX_DRAWDOWN_WORSE
    passed = (
        delta["aggregate_ev_delta"] > 0
        and delta["aggregate_pnl_delta"] > 0
        and delta["windows_ev_improved"] >= MIN_EV_IMPROVED_WINDOWS
        and delta["windows_ev_regressed"] == 0
        and sample_guard_passed
        and adjusted_guard_passed
        and concentration_guard_passed
        and drawdown_guard_passed
    )
    share = variant["single_ticker_positive_share"]
    share_delta = (
        round(share - baseline_share, 6)
        if share is not None and baseline_share is not None
        else None
    )
    return {
        "passed": passed,
        "aggregate_ev_delta": delta["aggregate_ev_delta"],
        "aggregate_pnl_delta": delta["aggregate_pnl_delta"],
        "windows_ev_improved": delta["windows_ev_improved"],
        "windows_ev_regressed": delta["windows_ev_regressed"],
        "sleeve_capacity_adjusted_trade_count": variant[
            "sleeve_capacity_adjusted_trade_count"
        ],
        "sleeve_capacity_adjusted_windows": variant[
            "sleeve_capacity_adjusted_windows"
        ],
        "selected_trade_count": variant["selected_trade_count"],
        "sample_guard_passed": sample_guard_passed,
        "adjusted_guard_passed": adjusted_guard_passed,
        "single_ticker_positive_share": share,
        "baseline_single_ticker_positive_share": baseline_share,
        "single_ticker_positive_share_delta": share_delta,
        "concentration_guard_passed": concentration_guard_passed,
        "max_single_ticker_positive_share": MAX_SINGLE_TICKER_POSITIVE_SHARE,
        "max_drawdown_worse_max": delta["max_drawdown_worse_max"],
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "drawdown_guard_passed": drawdown_guard_passed,
        "minimum_selected_trades": MIN_SELECTED_TRADES,
        "minimum_adjusted_trades": MIN_ADJUSTED_TRADES,
        "minimum_adjusted_windows": MIN_ADJUSTED_WINDOWS,
        "minimum_ev_improved_windows": MIN_EV_IMPROVED_WINDOWS,
        "delta_metrics": delta,
    }


def _choose_best(rows: list[dict[str, Any]]) -> dict[str, Any]:
    passing = [
        row
        for row in rows
        if row["variant_name"] != BASELINE_VARIANT and row["gate4"]["passed"]
    ]
    if passing:
        return max(
            passing,
            key=lambda row: (
                row["gate4"]["aggregate_ev_delta"],
                row["gate4"]["aggregate_pnl_delta"],
                -row["gate4"]["max_drawdown_worse_max"],
                -row["aggression_order"],
            ),
        )
    return max(
        [row for row in rows if row["variant_name"] != BASELINE_VARIANT],
        key=lambda row: (
            row["gate4"]["aggregate_ev_delta"],
            row["gate4"]["aggregate_pnl_delta"],
            row["gate4"]["windows_ev_improved"],
            -row["gate4"]["windows_ev_regressed"],
        ),
    )


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} State-Surface Sleeve Capacity Notional",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Single causal variable: `sleeve_capacity_notional_profile` for the default-off rotation-only state-surface paper sleeve.",
        "",
        "## Sweep",
        "",
        "| Variant | Gate 4 | Scalar | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        share = row["single_ticker_positive_share"]
        lines.append(
            "| {variant} | {passed} | {scalar} | {ev:+.4f} | ${pnl:+,.2f} | {wi} | {wr} | {adj} | {dd:+.4%} | {share} |".format(
                variant=row["variant_name"],
                passed="PASS" if row["gate4"]["passed"] else "FAIL",
                scalar=row["scalar"] if row["scalar"] is not None else "n/a",
                ev=row["gate4"]["aggregate_ev_delta"],
                pnl=row["gate4"]["aggregate_pnl_delta"],
                wi=row["gate4"]["windows_ev_improved"],
                wr=row["gate4"]["windows_ev_regressed"],
                adj=row["gate4"]["sleeve_capacity_adjusted_trade_count"],
                dd=row["gate4"]["max_drawdown_worse_max"],
                share=f"{share:.2%}" if share is not None else "n/a",
            )
        )
    lines.extend(
        [
            "",
            "## Three-Window Best Variant",
            "",
            "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Adjusted trades |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        sleeve = payload["surface_sleeve"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {bdd:.2%} | {add:.2%} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                bdd=before["max_drawdown_pct"],
                add=after["max_drawdown_pct"],
                trades=sleeve["sleeve_capacity_adjusted_trade_count"],
            )
        )
    lines.extend(
        [
            "",
            "## Production Impact",
            "",
            "```json",
            json.dumps(payload["production_impact"], indent=2, sort_keys=True),
            "```",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def build_payload() -> dict[str, Any]:
    gate2 = prev._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    baseline_payload = prev._json_load(BASELINE_JSON)
    prices = prev._load_price_map()
    baseline_metrics = baseline_payload["after_metrics"]
    baseline_trades_by_window: dict[str, list[dict[str, Any]]] = OrderedDict()
    core_curves: dict[str, list[tuple[str, float]]] = OrderedDict()
    for label, window in WINDOWS.items():
        rows = baseline_payload["surface_sleeve"][label]["selected_trades"]
        prepared = [prev._prepare_trade({**row, "window": label}, prices) for row in rows]
        baseline_trades_by_window[label] = prepared
        baseline_event_curve = prev._event_equity_curve_variable_notional(
            prepared,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        event_by_day = {
            row["date"]: float(row["event_pnl"]) for row in baseline_event_curve
        }
        combined_curve = [
            (str(day), float(equity))
            for day, equity in baseline_metrics[label]["combined_equity_curve"]
        ]
        core_curves[label] = [
            (day, round(equity - event_by_day.get(day, 0.0), 2))
            for day, equity in combined_curve
        ]

    baseline_trades_all = [
        row for rows in baseline_trades_by_window.values() for row in rows
    ]
    baseline_share = prev._single_ticker_positive_share(baseline_trades_all)
    variants = [
        _variant_payload(
            variant_name=name,
            variant=variant,
            baseline_payload=baseline_payload,
            baseline_trades_by_window=baseline_trades_by_window,
            core_curves=core_curves,
            prices=prices,
        )
        for name, variant in CAPACITY_VARIANTS.items()
    ]
    sweep_summary = []
    for variant in variants:
        gate4 = _gate4_for_variant(
            baseline_metrics=baseline_metrics,
            baseline_share=baseline_share,
            variant=variant,
        )
        sweep_summary.append(
            {
                "variant_name": variant["variant_name"],
                "is_identity_control": variant["variant_name"] == BASELINE_VARIANT,
                "scalar": variant["scalar"],
                "aggression_order": variant["aggression_order"],
                "description": variant["description"],
                "selected_trade_count": variant["selected_trade_count"],
                "sleeve_capacity_adjusted_trade_count": variant[
                    "sleeve_capacity_adjusted_trade_count"
                ],
                "sleeve_capacity_adjusted_windows": variant[
                    "sleeve_capacity_adjusted_windows"
                ],
                "single_ticker_positive_share": variant[
                    "single_ticker_positive_share"
                ],
                "gate4": gate4,
            }
        )

    best = _choose_best(sweep_summary)
    best_payload = next(
        row for row in variants if row["variant_name"] == best["variant_name"]
    )
    delta = prev._aggregate_delta(baseline_metrics, best_payload["metrics"])
    passed = bool(best["gate4"]["passed"])
    decision = (
        "accepted_default_off_state_surface_sleeve_capacity_notional"
        if passed
        else "rejected_state_surface_sleeve_capacity_notional"
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
            "+00:00",
            "Z",
        ),
        "lane": "alpha_search",
        "status": "accepted" if passed else "rejected",
        "decision": decision,
        "hypothesis": "The accepted state-surface paper sleeve is under-allocated after multiple independent quality profiles, so a bounded global sleeve-capacity scalar should improve expectancy without changing candidate selection.",
        "alpha_hypothesis": {
            "category": "capital allocation",
            "entry_exit_ranking_or_allocation": "default-off paper allocation",
            "playbook_alignment": "Moves from additional filters to capital allocation on the accepted state-surface quality stack, keeping candidate eligibility and ranking fixed.",
        },
        "change_type": "default_off_paper_allocation",
        "changed_variable": "sleeve_capacity_notional_profile",
        "component": "quant/state_surface_sleeve.py",
        "parameters": {
            "best_variant": best["variant_name"],
            "best_scalar": best["scalar"],
            "profile_priority": "applies after the accepted rank/queue alignment stack and before recent-repeat paper metadata",
            "locked_variables": [
                "core entries",
                "core exits",
                "core sizing",
                "state-surface candidate eligibility",
                "state-surface queue ranking",
                "state-surface hold days",
                "state-surface active capacity",
                "rank/queue alignment scalar",
                "candidate pool",
                "LLM/news",
                "live/default orders",
            ],
        },
        "date_range": {
            label: {
                "start": window["start"],
                "end": window["end"],
                "snapshot": window["snapshot"],
            }
            for label, window in WINDOWS.items()
        },
        "backtest_protocol": "docs/backtesting.md canonical three fixed windows; accepted exp-20260519-026 baseline artifact plus default-off state-surface paper overlay replay.",
        "before_metrics": baseline_metrics,
        "after_metrics": best_payload["metrics"],
        "delta_metrics": delta,
        "expected_value_score_delta": {
            label: delta["by_window"][label]["expected_value_score"]
            for label in WINDOWS
        }
        | {"aggregate": delta["aggregate_ev_delta"]},
        "total_pnl_delta": {
            label: delta["by_window"][label]["total_pnl"] for label in WINDOWS
        }
        | {"aggregate": delta["aggregate_pnl_delta"]},
        "gate1": {
            "baseline_artifact": prev._repo_rel(BASELINE_JSON),
            "baseline_variant": BASELINE_VARIANT,
            "baseline_note": "Uses accepted exp-20260519-026 rank/queue alignment as Gate 1 baseline.",
        },
        "gate2": {
            "open_position_fields": gate2,
            "runtime_fields": [
                "rank_notional_multiplier",
                "event_notional_usd",
                "entry_open",
                "net_return_pct",
            ],
            "passed": True,
        },
        "gate3": {
            "new_filter_added": False,
            "minimum_baseline_survival_rate": min(
                float(row.get("survival_rate") or 0.0)
                for row in baseline_metrics.values()
            ),
            "after_survival_rate": {
                label: best_payload["metrics"][label].get("survival_rate")
                for label in WINDOWS
            },
            "hard_rule": "No filter, ranking, or candidate gate changed; only paper notional changes for existing selected trades.",
        },
        "gate4": best["gate4"],
        "surface_sleeve": best_payload["surface_sleeve"],
        "sweep_summary": sweep_summary,
        "history_check": {
            "exp-20260519-026": "Accepted rank/queue alignment; this experiment freezes it and tests global sleeve-capacity allocation.",
            "recent_rejections": "Avoids cached AI-infra pool expansion, core-misfit residual expansion, pure SPY T+1 SEC haircuts, rank4 volume no-sample, and LLM soft-ranking.",
            "anti_repeat": "Not a ret5/ret20/ret60, near-high, volume-threshold, sector-cohesion, score-gap, candidate-pool, SEC text, or LLM soft-ranking retry.",
        },
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm": "LLM soft-ranking data remains sparse/PIT-limited; this tests deterministic capital allocation on an already replayable paper sleeve.",
        },
        "production_impact": {
            "shared_policy_changed": passed,
            "backtester_adapter_changed": False,
            "run_adapter_changed": passed,
            "replay_only": False,
            "parity_test_added": passed,
            "live_default_orders_changed": False,
            "core_metrics_changed": False,
            "default_off_paper_only": True,
        },
        "interpretation": (
            "Sleeve-capacity support improved the default-off state-surface paper overlay without changing core trades, filters, ranking, or live/default orders."
            if passed
            else "Sleeve-capacity support did not clear Gate 4; keep the accepted rank/queue alignment stack unchanged."
        ),
        "rejection_reason": None
        if passed
        else "Failed Gate 4 under the canonical three-window state-surface paper protocol.",
        "next_evidence_needed": (
            "Promote only as shared default-off paper metadata; keep forward tail/concentration monitoring before any live adapter work."
            if passed
            else "Do not retry nearby global sleeve-capacity scalars without forward evidence or a distinct risk-budget field."
        ),
        "protocol_answers": {
            "1_alpha_hypothesis": "capital allocation: the accepted state-surface paper sleeve is under-allocated, so all already-selected paper candidates deserve bounded capacity support.",
            "2_history_check": "No prior experiment tested a global sleeve-capacity scalar after the accepted exp-20260519-026 stack. This avoids recent data-limited LLM/pool expansion lanes.",
            "3_single_causal_variable": "sleeve_capacity_notional_profile",
            "4_acceptance_standard": "docs/backtesting.md three fixed windows; positive aggregate EV/PnL, all three EV-improved windows, zero EV-regressed windows, adjusted trades >=20 across all 3 windows, max DD drift <=0.5pp, single-ticker positive share <=50%.",
            "5_reproducibility": f".venv\\Scripts\\python.exe quant\\experiments\\{Path(__file__).name}",
        },
        "anti_js": "No JavaScript was used.",
        "related_files": [
            prev._repo_rel(Path(__file__)),
            prev._repo_rel(OUT_JSON),
            prev._repo_rel(LOG_JSON),
            prev._repo_rel(TICKET_JSON),
            prev._repo_rel(ARTIFACT_MD),
            prev._repo_rel(EXPERIMENT_LOG),
            "quant/state_surface_sleeve.py",
            "quant/test_state_surface_sleeve.py",
        ],
    }
    return prev._safe(payload)


def main() -> None:
    payload = build_payload()
    prev._write_json(OUT_JSON, payload)
    prev._write_json(LOG_JSON, payload)
    prev._write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "State-surface sleeve capacity notional",
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": prev._repo_rel(OUT_JSON),
            "summary": (
                f"Sleeve-capacity profile {payload['parameters']['best_variant']} "
                f"changed aggregate EV {payload['delta_metrics']['aggregate_ev_delta']:+.4f} "
                f"and PnL ${payload['delta_metrics']['aggregate_pnl_delta']:+,.2f}."
            ),
        },
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG, payload)
    print(json.dumps(payload["gate4"], indent=2, sort_keys=True))
    print(f"{EXPERIMENT_ID} {payload['decision']}")


if __name__ == "__main__":
    main()
