"""exp-20260514-022: core token-risk floor allocation scout.

Alpha search. Tests one production-visible capital-allocation variable: after
all shared sizing helpers have run, skip core trend/breakout entries whose
positive actual risk is only a token-sized residual. This is a replay-only
scout until a passing result is promoted into shared portfolio sizing.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import exp_20260512_106_signal_day_sector_tape_risk as base


EXPERIMENT_ID = "exp-20260514-022"
EXPERIMENT_SLUG = "core_token_risk_floor"
MULTIPLIER_KEY = "core_token_risk_floor_applied"
RISK_FLOORS = [0.001, 0.0025, 0.005]

CURRENT_RISK_FLOOR = 0.0025


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(base._safe(payload), ensure_ascii=False, sort_keys=True)
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


def _zero_token_sizing(
    sig: dict[str, Any],
    sizing: dict[str, Any],
    risk_floor: float,
) -> dict[str, Any]:
    shares = int(sizing.get("shares_to_buy") or 0)
    risk_pct = sizing.get("risk_pct")
    if shares <= 0 or not isinstance(risk_pct, (int, float)):
        return sizing
    risk_pct = float(risk_pct)
    if risk_pct <= 0.0 or risk_pct >= risk_floor:
        return sizing

    out = dict(sizing)
    out["core_token_risk_floor_before_risk_pct"] = risk_pct
    out["core_token_risk_floor_before_shares"] = shares
    out["core_token_risk_floor_before_position_value_usd"] = sizing.get(
        "position_value_usd"
    )
    out["core_token_risk_floor_before_risk_amount_usd"] = sizing.get(
        "risk_amount_usd"
    )
    out["shares_to_buy"] = 0
    out["position_value_usd"] = 0.0
    out["position_pct_of_portfolio"] = 0.0
    out["risk_amount_usd"] = 0.0
    out["risk_pct"] = 0.0
    out[MULTIPLIER_KEY] = risk_floor
    return out


def _make_size_wrapper(
    original: Callable[..., list[dict[str, Any]]],
) -> Callable[..., list[dict[str, Any]]]:
    def wrapped(
        signals: list[dict[str, Any]],
        portfolio_value: float,
        risk_pct: float | None = None,
    ) -> list[dict[str, Any]]:
        sized = original(signals, portfolio_value, risk_pct=risk_pct)
        out = []
        for sig in sized:
            sizing = sig.get("sizing") or {}
            if sig.get("strategy") in {"trend_long", "breakout_long"}:
                adjusted = _zero_token_sizing(sig, sizing, CURRENT_RISK_FLOOR)
                if adjusted is not sizing:
                    base.ADJUSTMENTS.append(
                        {
                            "ticker": sig.get("ticker"),
                            "strategy": sig.get("strategy"),
                            "sector": sig.get("sector"),
                            "risk_floor": CURRENT_RISK_FLOOR,
                            "before_risk_pct": sizing.get("risk_pct"),
                            "before_shares": sizing.get("shares_to_buy"),
                            "before_position_value_usd": sizing.get(
                                "position_value_usd"
                            ),
                            "trade_quality_score": sig.get("trade_quality_score"),
                            "regime_exit_bucket": sig.get("regime_exit_bucket"),
                            "regime_exit_score": sig.get("regime_exit_score"),
                            "sizing_multipliers_before": {
                                key: value
                                for key, value in sizing.items()
                                if key.endswith("_multiplier_applied")
                                and value not in (None, 1.0)
                            },
                        }
                    )
                    sig = {**sig, "sizing": adjusted}
            out.append(sig)
        return out

    return wrapped


def _run_variant_window(label: str, risk_floor: float) -> dict[str, Any]:
    global CURRENT_RISK_FLOOR
    CURRENT_RISK_FLOOR = risk_floor

    original_size = base.portfolio_engine.size_signals
    original_keys = base.backtester_module.SIZING_MULTIPLIER_KEYS
    try:
        base.portfolio_engine.size_signals = _make_size_wrapper(original_size)
        if MULTIPLIER_KEY not in base.backtester_module.SIZING_MULTIPLIER_KEYS:
            base.backtester_module.SIZING_MULTIPLIER_KEYS = (
                *base.backtester_module.SIZING_MULTIPLIER_KEYS,
                MULTIPLIER_KEY,
            )
        return base._run_window(label, variant=False)
    finally:
        base.portfolio_engine.size_signals = original_size
        base.backtester_module.SIZING_MULTIPLIER_KEYS = original_keys


def _removed_trade_outcome(
    before_trades: list[dict[str, Any]],
    after_trades: list[dict[str, Any]],
) -> dict[str, Any]:
    before_by_key = {base._trade_key(row): row for row in before_trades}
    after_keys = {base._trade_key(row) for row in after_trades}
    removed = [before_by_key[key] for key in sorted(set(before_by_key) - after_keys)]
    pnl = round(sum(float(row.get("pnl") or 0.0) for row in removed), 2)
    return {
        "removed_trade_count": len(removed),
        "removed_trade_pnl": pnl,
        "removed_trade_win_rate": (
            round(
                sum(1 for row in removed if float(row.get("pnl") or 0.0) > 0)
                / len(removed),
                4,
            )
            if removed
            else None
        ),
        "removed_trades": [
            {
                "ticker": row.get("ticker"),
                "strategy": row.get("strategy"),
                "sector": row.get("sector"),
                "entry_date": row.get("entry_date"),
                "exit_date": row.get("exit_date"),
                "pnl": row.get("pnl"),
                "pnl_pct_net": row.get("pnl_pct_net"),
                "actual_risk_pct": row.get("actual_risk_pct"),
                "sizing_multipliers": row.get("sizing_multipliers"),
            }
            for row in removed
        ],
    }


def _candidate_payload(
    risk_floor: float,
    before_runs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    before_metrics = {label: before_runs[label]["metrics"] for label in base.WINDOWS}
    after_metrics: dict[str, dict[str, Any]] = {}
    adjustments: dict[str, list[dict[str, Any]]] = {}
    changed_trades: dict[str, dict[str, Any]] = {}
    removed_trade_outcome: dict[str, dict[str, Any]] = {}
    sizing_attribution: dict[str, Any] = {}

    for label in base.WINDOWS:
        variant = _run_variant_window(label, risk_floor)
        after_metrics[label] = variant["metrics"]
        adjustments[label] = variant["adjustments"]
        changed_trades[label] = base._changed_trades(
            before_runs[label]["trades"],
            variant["trades"],
        )
        removed_trade_outcome[label] = _removed_trade_outcome(
            before_runs[label]["trades"],
            variant["trades"],
        )
        sizing_attribution[label] = {
            "signal": variant["sizing_rule_signal_attribution"].get(MULTIPLIER_KEY),
            "trade": variant["sizing_rule_trade_attribution"].get(MULTIPLIER_KEY),
        }

    by_window_delta = {
        label: base._delta(after_metrics[label], before_metrics[label])
        for label in base.WINDOWS
    }
    aggregate_before = base._aggregate(before_metrics)
    aggregate_after = base._aggregate(after_metrics)
    aggregate_delta = base._aggregate_delta(aggregate_after, aggregate_before)
    improved = [
        label
        for label in base.WINDOWS
        if after_metrics[label]["expected_value_score"]
        > before_metrics[label]["expected_value_score"]
    ]
    regressed = [
        label
        for label in base.WINDOWS
        if after_metrics[label]["expected_value_score"]
        < before_metrics[label]["expected_value_score"]
    ]
    adjusted_count = sum(len(rows) for rows in adjustments.values())
    max_drawdown_worse = max(
        float(by_window_delta[label].get("max_drawdown_pct") or 0.0)
        for label in base.WINDOWS
    )
    trade_count_after = int(aggregate_after["trade_count_sum"])
    passed = (
        aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] > 0
        and len(improved) >= 2
        and not regressed
        and aggregate_after["survival_rate_min"] >= 0.05
        and trade_count_after >= 50
        and max_drawdown_worse <= 0.005
        and adjusted_count > 0
    )
    return {
        "risk_floor": risk_floor,
        "passed": passed,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": by_window_delta,
            "aggregate_before": aggregate_before,
            "aggregate_after": aggregate_after,
            "aggregate_delta": aggregate_delta,
        },
        "gate4": {
            "passed": passed,
            "improved_windows": improved,
            "regressed_windows": regressed,
            "adjusted_signal_count": adjusted_count,
            "trade_count_after": trade_count_after,
            "max_drawdown_worse": round(max_drawdown_worse, 6),
        },
        "adjustments": adjustments,
        "changed_trades": changed_trades,
        "removed_trade_outcome": removed_trade_outcome,
        "sizing_attribution": sizing_attribution,
        "expected_value_score_delta": aggregate_delta["expected_value_score_sum"],
        "total_pnl_delta": aggregate_delta["total_pnl_sum"],
    }


def _select_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    passed = [row for row in candidates if row["passed"]]
    pool = passed if passed else candidates
    return max(
        pool,
        key=lambda row: (
            1 if row["passed"] else 0,
            float(row["expected_value_score_delta"]),
            float(row["total_pnl_delta"]),
        ),
    )


def _sweep_summary(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "risk_floor": row["risk_floor"],
            "passed": row["passed"],
            "expected_value_score_delta": row["expected_value_score_delta"],
            "total_pnl_delta": row["total_pnl_delta"],
            "improved_windows": row["gate4"]["improved_windows"],
            "regressed_windows": row["gate4"]["regressed_windows"],
            "adjusted_signal_count": row["gate4"]["adjusted_signal_count"],
            "trade_count_after": row["gate4"]["trade_count_after"],
            "max_drawdown_worse": row["gate4"]["max_drawdown_worse"],
        }
        for row in candidates
    ]


def _markdown(payload: dict[str, Any]) -> str:
    sweep_rows = [
        "| Risk floor | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Trades after | Max DD worse |",
        "|---:|:---:|---:|---:|---|---|---:|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        sweep_rows.append(
            "| {floor:.4f} | {passed} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {adj} | {trades} | {dd:+.4f} |".format(
                floor=row["risk_floor"],
                passed="PASS" if row["passed"] else "FAIL",
                dev=row["expected_value_score_delta"],
                dpnl=row["total_pnl_delta"],
                improved=", ".join(row["improved_windows"]) or "-",
                regressed=", ".join(row["regressed_windows"]) or "-",
                adj=row["adjusted_signal_count"],
                trades=row["trade_count_after"],
                dd=row["max_drawdown_worse"],
            )
        )

    window_rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Survival | Adjusted |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        window_rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {trades} | {surv:.4f} | {adj} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                trades=after["trade_count"],
                surv=after["survival_rate"],
                adj=len(payload["adjustments"][label]),
            )
        )

    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Core Token-Risk Floor",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: minimum post-sizing actual `risk_pct` for core `trend_long`/`breakout_long` entries. Positive but token-sized residual risk below the floor is set to zero shares after existing shared sizing helpers run. Entries, ranking, exits, targets, universe, LLM/news, caps, and heat are locked.",
            "",
            "## Sweep",
            "",
            *sweep_rows,
            "",
            f"Selected risk floor: `{payload['parameters']['selected_risk_floor']}`.",
            "",
            "## Selected Three-Window Result",
            "",
            *window_rows,
            "",
            "Production impact: replay-only scout unless Gate 4 passes and the same floor is promoted into shared `portfolio_engine` sizing with attribution parity.",
        ]
    )


def run() -> dict[str, Any]:
    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    before_runs = {
        label: base._run_window(label, variant=False)
        for label in base.WINDOWS
    }
    candidates = [
        _candidate_payload(risk_floor, before_runs)
        for risk_floor in RISK_FLOORS
    ]
    selected = _select_candidate(candidates)
    passed = selected["passed"]
    decision = (
        "accepted_for_shared_policy_implementation"
        if passed
        else "rejected_core_token_risk_floor"
    )
    interpretation = (
        "The token-risk floor cleared the canonical three-window gate and should be promoted through shared sizing before production use."
        if passed
        else "The token-risk floor did not clear the canonical three-window gate; keep the accepted sizing stack unchanged and avoid token-position zeroing without a new discriminator."
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "Very small positive-risk core entries created after stacked haircuts "
            "may be bad slot/cost allocation: they keep residual downside and "
            "can occupy entry planning attention without enough upside. A "
            "minimum actual-risk floor may improve EV by skipping only those "
            "token-sized residual positions."
        ),
        "change_type": "risk_allocation_shadow",
        "changed_variable": "core_post_sizing_actual_risk_floor",
        "single_causal_variable": (
            "minimum positive post-sizing risk_pct for core trend_long/breakout_long entries"
        ),
        "parameters": {
            "risk_floor_sweep": RISK_FLOORS,
            "selected_risk_floor": selected["risk_floor"],
            "condition": "0 < sizing.risk_pct < selected_risk_floor",
            "action": "set shares_to_buy and risk_pct to zero after existing sizing helpers run",
            "locked_variables": [
                "core universe",
                "entry filters",
                "candidate ranking",
                "stop and target logic",
                "all existing sizing multipliers",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "add-ons",
                "LLM/news replay",
                "pilot/event sleeves",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": "capital allocation / slot quality using production-visible post-sizing risk units",
            "2_history_check": {
                "exp-20260514-001": "Rejected high actual-risk ceiling; this tests the opposite tail, token residual risk, not a broad risk cap.",
                "exp-20260505-005": "Rejected removing pre-planning non-positionable candidates; this keeps planning unchanged and only zeroes post-sizing token residuals.",
                "exp-20260510-021": "Rejected effective risk-slot accounting; this does not change slot accounting or capacity.",
                "recent_rs_own_candle_clean_leader": "Nearby positive-confirmation retunes are avoided.",
                "llm_sec_space": "LLM soft-ranking, SEC semantics, and Space forward cohorts are field/outcome limited for a new three-window decision.",
            },
            "3_single_causal_variable": "core_post_sizing_actual_risk_floor",
            "4_acceptance_standard": "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, at least two EV-improved windows, no EV-regressed windows, survival >= 5%, aggregate trades >= 50, max drawdown drift <= 0.5 pp.",
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\exp_20260514_022_core_token_risk_floor.py"
            ),
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical fixed-snapshot three-window replay",
            "windows": base.WINDOWS,
            "config": {"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
        },
        "gate1": {
            "baseline_metrics": selected["before_metrics"],
            "baseline_aggregate": selected["delta_metrics"]["aggregate_before"],
        },
        "gate2": {
            "open_positions": gate2,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "portfolio_engine sizing risk_pct",
                "portfolio_engine sizing shares_to_buy",
                "portfolio_engine sizing position_value_usd",
                "portfolio_engine sizing risk_amount_usd",
            ],
            "passed": gate2["passed"],
        },
        "gate3": {
            "new_filter_added": False,
            "signals_generated_delta": selected["delta_metrics"]["aggregate_delta"][
                "signals_generated_sum"
            ],
            "signals_survived_delta": selected["delta_metrics"]["aggregate_delta"][
                "signals_survived_sum"
            ],
            "minimum_after_survival_rate": selected["delta_metrics"][
                "aggregate_after"
            ]["survival_rate_min"],
            "passed": selected["delta_metrics"]["aggregate_after"][
                "survival_rate_min"
            ]
            >= 0.05,
        },
        "gate4": selected["gate4"],
        "before_metrics": selected["before_metrics"],
        "after_metrics": selected["after_metrics"],
        "delta_metrics": selected["delta_metrics"],
        "adjustments": selected["adjustments"],
        "changed_trades": selected["changed_trades"],
        "removed_trade_outcome": selected["removed_trade_outcome"],
        "sizing_attribution": selected["sizing_attribution"],
        "sweep_summary": _sweep_summary(candidates),
        "expected_value_score_delta": selected["expected_value_score_delta"],
        "total_pnl_delta": selected["total_pnl_delta"],
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm_soft_ranking": "LLM soft-ranking remains data-limited; this deterministic allocation test is replayable on fixed OHLCV snapshots.",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
        },
        "interpretation": interpretation,
        "rejection_reason": None if passed else interpretation,
        "next_evidence_needed": None
        if passed
        else "Use a new production-visible discriminator for token residuals, or forward slot/cost attribution, before retrying.",
        "related_files": [
            "quant/experiments/exp_20260514_022_core_token_risk_floor.py",
            "data/experiments/exp-20260514-022/core_token_risk_floor.json",
            "experiments/logs/exp-20260514-022.json",
            "experiments/tickets/exp-20260514-022.json",
            "experiments/artifacts/exp-20260514-022_core_token_risk_floor.md",
            "docs/experiment_log.jsonl",
        ],
        "why_not_other_changes": (
            "This avoids LLM/SEC/estimate-revision/options branches that lack "
            "closed three-window decision-grade data, avoids recent Space "
            "same-sample retunes, and avoids nearby RS20/RS60/own-candle/"
            "clean-SPY scalar tuning. It tests one production-visible capital "
            "allocation variable from the current core sizing surface."
        ),
    }
    return payload


def persist(payload: dict[str, Any]) -> None:
    artifact_path = (
        base.REPO_ROOT
        / "data"
        / "experiments"
        / EXPERIMENT_ID
        / f"{EXPERIMENT_SLUG}.json"
    )
    log_path = (
        base.REPO_ROOT
        / "experiments"
        / "logs"
        / f"{EXPERIMENT_ID}.json"
    )
    ticket_path = (
        base.REPO_ROOT
        / "experiments"
        / "tickets"
        / f"{EXPERIMENT_ID}.json"
    )
    md_path = (
        base.REPO_ROOT
        / "experiments"
        / "artifacts"
        / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
    )
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "changed_variable": payload["changed_variable"],
        "selected_risk_floor": payload["parameters"]["selected_risk_floor"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["total_pnl_delta"],
        "gate4_passed": payload["gate4"]["passed"],
        "summary": payload["interpretation"],
        "artifact": str(artifact_path.relative_to(base.REPO_ROOT)),
    }
    base._write_json(artifact_path, payload)
    base._write_json(log_path, payload)
    base._write_json(ticket_path, ticket)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_markdown(payload) + "\n", encoding="utf-8")
    _upsert_jsonl(base.REPO_ROOT / "docs" / "experiment_log.jsonl", payload)


if __name__ == "__main__":
    result = run()
    persist(result)
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "decision": result["decision"],
                "expected_value_score_delta": result["expected_value_score_delta"],
                "total_pnl_delta": result["total_pnl_delta"],
                "gate4_passed": result["gate4"]["passed"],
                "improved_windows": result["gate4"]["improved_windows"],
                "regressed_windows": result["gate4"]["regressed_windows"],
                "adjusted_signal_count": result["gate4"]["adjusted_signal_count"],
                "selected_risk_floor": result["parameters"]["selected_risk_floor"],
                "sweep_summary": result["sweep_summary"],
            },
            indent=2,
            sort_keys=True,
        )
    )
