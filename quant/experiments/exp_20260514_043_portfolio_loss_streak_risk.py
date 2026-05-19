"""exp-20260514-043: portfolio loss-streak risk allocation scout.

Tests one causal variable on the accepted core stack: whether recently closed
portfolio-level losses identify an unfavorable entry state. This is a
post-sizing risk scalar, not an entry filter. Entries, exits, ranking,
candidate universe, slots, LLM/news behavior, event sleeves, and all existing
rules stay unchanged.
"""

from __future__ import annotations

import inspect
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import exp_20260512_106_signal_day_sector_tape_risk as base


EXPERIMENT_ID = "exp-20260514-043"
EXPERIMENT_SLUG = "portfolio_loss_streak_risk"
MULTIPLIER_KEY = "portfolio_loss_streak_risk_multiplier_applied"
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005

SWEEP = [
    {"name": "loss2_050x", "lookback_losses": 2, "risk_multiplier": 0.50},
    {"name": "loss2_075x", "lookback_losses": 2, "risk_multiplier": 0.75},
    {"name": "loss3_050x", "lookback_losses": 3, "risk_multiplier": 0.50},
    {"name": "loss3_075x", "lookback_losses": 3, "risk_multiplier": 0.75},
]

ADJUSTMENTS: list[dict[str, Any]] = []


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(base._safe(payload), indent=2, ensure_ascii=False, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(base._safe(payload), ensure_ascii=False, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _closed_core_trades(closed: Any) -> list[dict[str, Any]]:
    if not isinstance(closed, list):
        return []
    out = []
    for row in closed:
        if not isinstance(row, dict):
            continue
        if row.get("sleeve") not in (None, "", "core"):
            continue
        if not isinstance(row.get("pnl"), (int, float)):
            continue
        out.append(row)
    return out


def _active_loss_streak(closed: Any, lookback_losses: int) -> tuple[bool, list[dict[str, Any]]]:
    trades = _closed_core_trades(closed)
    if lookback_losses <= 0 or len(trades) < lookback_losses:
        return False, trades[-lookback_losses:] if lookback_losses else []
    recent = trades[-lookback_losses:]
    active = all(float(row.get("pnl") or 0.0) < 0.0 for row in recent)
    return active, recent


def _frame_state(lookback_losses: int) -> dict[str, Any]:
    frame = inspect.currentframe()
    caller = frame.f_back if frame else None
    run_frame = caller.f_back if caller and caller.f_back else None
    locals_ = run_frame.f_locals if run_frame else {}
    active, recent = _active_loss_streak(locals_.get("closed"), lookback_losses)
    today = locals_.get("today")
    return {
        "active": active,
        "recent": recent,
        "closed_count": len(_closed_core_trades(locals_.get("closed"))),
        "date": str(today.date()) if hasattr(today, "date") else str(today),
    }


def _scale_sizing(
    sig: dict[str, Any],
    sizing: dict[str, Any],
    portfolio_value: float,
    *,
    lookback_losses: int,
    risk_multiplier: float,
    state: dict[str, Any],
) -> dict[str, Any]:
    shares = int(sizing.get("shares_to_buy") or 0)
    if shares <= 0:
        return sizing
    new_shares = max(1, int(math.floor(shares * risk_multiplier)))
    if new_shares >= shares:
        return sizing

    entry = float(sizing.get("entry_price") or sig.get("entry_price") or 0.0)
    net_risk_per_share = float(sizing.get("net_risk_per_share") or 0.0)
    out = dict(sizing)
    out["portfolio_loss_streak_baseline_shares"] = shares
    out["portfolio_loss_streak_new_shares"] = new_shares
    out["portfolio_loss_streak_closed_trade_count"] = state["closed_count"]
    out["portfolio_loss_streak_lookback_losses"] = lookback_losses
    out["portfolio_loss_streak_recent_pnls"] = [
        round(float(row.get("pnl") or 0.0), 2) for row in state["recent"]
    ]
    out["shares_to_buy"] = new_shares
    out["position_value_usd"] = round(entry * new_shares, 2)
    out["position_pct_of_portfolio"] = (
        round((entry * new_shares) / portfolio_value, 4) if portfolio_value else 0.0
    )
    out["risk_amount_usd"] = round(net_risk_per_share * new_shares, 2)
    out["risk_pct"] = (
        (net_risk_per_share * new_shares) / portfolio_value if portfolio_value else 0.0
    )
    out[MULTIPLIER_KEY] = risk_multiplier
    return out


def _make_size_wrapper(
    original: Callable[..., list[dict[str, Any]]],
    *,
    lookback_losses: int,
    risk_multiplier: float,
) -> Callable[..., list[dict[str, Any]]]:
    def wrapped(
        signals: list[dict[str, Any]],
        portfolio_value: float,
        risk_pct: float | None = None,
    ) -> list[dict[str, Any]]:
        sized = original(signals, portfolio_value, risk_pct=risk_pct)
        state = _frame_state(lookback_losses)
        if not state["active"]:
            return sized
        out = []
        for sig in sized:
            sizing = sig.get("sizing") or {}
            adjusted_sizing = _scale_sizing(
                sig,
                sizing,
                portfolio_value,
                lookback_losses=lookback_losses,
                risk_multiplier=risk_multiplier,
                state=state,
            )
            if adjusted_sizing is not sizing:
                ADJUSTMENTS.append(
                    {
                        "date": state["date"],
                        "ticker": sig.get("ticker"),
                        "strategy": sig.get("strategy"),
                        "sector": sig.get("sector"),
                        "lookback_losses": lookback_losses,
                        "risk_multiplier": risk_multiplier,
                        "closed_trade_count": state["closed_count"],
                        "recent_pnls": adjusted_sizing.get(
                            "portfolio_loss_streak_recent_pnls"
                        ),
                        "baseline_shares": sizing.get("shares_to_buy"),
                        "new_shares": adjusted_sizing.get("shares_to_buy"),
                        "trade_quality_score": sig.get("trade_quality_score"),
                        "regime_exit_bucket": sig.get("regime_exit_bucket"),
                        "regime_exit_score": sig.get("regime_exit_score"),
                        "rs20_entry_state_leader": sig.get("rs20_entry_state_leader"),
                        "rs60_top_quintile_state": sig.get("rs60_top_quintile_state"),
                        "signal_day_ticker_green_candle": sig.get(
                            "signal_day_ticker_green_candle"
                        ),
                    }
                )
                sig = {**sig, "sizing": adjusted_sizing}
            out.append(sig)
        return out

    return wrapped


def _run_window(label: str, variant: dict[str, Any] | None) -> dict[str, Any]:
    spec = base.WINDOWS[label]
    universe = base.get_universe()
    original_size = base.portfolio_engine.size_signals
    original_multiplier_keys = base.backtester_module.SIZING_MULTIPLIER_KEYS

    global ADJUSTMENTS
    ADJUSTMENTS = []

    if variant:
        base.portfolio_engine.size_signals = _make_size_wrapper(
            original_size,
            lookback_losses=int(variant["lookback_losses"]),
            risk_multiplier=float(variant["risk_multiplier"]),
        )
        if MULTIPLIER_KEY not in base.backtester_module.SIZING_MULTIPLIER_KEYS:
            base.backtester_module.SIZING_MULTIPLIER_KEYS = (
                *base.backtester_module.SIZING_MULTIPLIER_KEYS,
                MULTIPLIER_KEY,
            )

    try:
        engine = base.BacktestEngine(
            universe,
            start=spec["start"],
            end=spec["end"],
            config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
            ohlcv_snapshot_path=str(base.REPO_ROOT / spec["snapshot"]),
        )
        result = engine.run()
    finally:
        base.portfolio_engine.size_signals = original_size
        base.backtester_module.SIZING_MULTIPLIER_KEYS = original_multiplier_keys

    if result.get("error"):
        kind = "baseline" if variant is None else variant["name"]
        raise RuntimeError(f"{label} {kind} failed: {result['error']}")
    return {
        "metrics": base._metrics(result),
        "trades": result.get("trades") or [],
        "adjustments": list(ADJUSTMENTS),
        "sizing_rule_signal_attribution": result.get("sizing_rule_signal_attribution")
        or {},
        "sizing_rule_trade_attribution": result.get("sizing_rule_trade_attribution")
        or {},
    }


def _candidate_payload(
    variant: dict[str, Any],
    before_runs: dict[str, dict[str, Any]],
    *,
    include_details: bool = False,
) -> dict[str, Any]:
    before_metrics = {label: before_runs[label]["metrics"] for label in base.WINDOWS}
    after_runs = {label: _run_window(label, variant) for label in base.WINDOWS}
    after_metrics = {label: after_runs[label]["metrics"] for label in base.WINDOWS}
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
    adjusted_count = sum(len(after_runs[label]["adjustments"]) for label in base.WINDOWS)
    max_drawdown_worse = max(
        float(by_window_delta[label].get("max_drawdown_pct") or 0.0)
        for label in base.WINDOWS
    )
    drawdown_guardrail_passed = max_drawdown_worse <= MAX_DRAWDOWN_WORSE_GUARDRAIL
    passed = (
        aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] > 0
        and len(improved) >= 2
        and not regressed
        and aggregate_after["survival_rate_min"] >= 0.05
        and adjusted_count > 0
        and drawdown_guardrail_passed
    )
    return {
        "variant": variant,
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
            "max_drawdown_worse": round(max_drawdown_worse, 6),
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "drawdown_guardrail_passed": drawdown_guardrail_passed,
        },
        "adjustments": {
            label: after_runs[label]["adjustments"] for label in base.WINDOWS
        }
        if include_details
        else None,
        "changed_trades": {
            label: base._changed_trades(
                before_runs[label]["trades"],
                after_runs[label]["trades"],
            )
            for label in base.WINDOWS
        }
        if include_details
        else None,
        "sizing_attribution": {
            label: {
                "signal": after_runs[label]["sizing_rule_signal_attribution"].get(
                    MULTIPLIER_KEY
                ),
                "trade": after_runs[label]["sizing_rule_trade_attribution"].get(
                    MULTIPLIER_KEY
                ),
            }
            for label in base.WINDOWS
        }
        if include_details
        else None,
        "expected_value_score_delta": aggregate_delta["expected_value_score_sum"],
        "total_pnl_delta": aggregate_delta["total_pnl_sum"],
    }


def _select_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [row for row in candidates if row["passed"]] or candidates
    return max(
        rows,
        key=lambda row: (
            1 if row["passed"] else 0,
            row["delta_metrics"]["aggregate_delta"]["expected_value_score_sum"],
            row["delta_metrics"]["aggregate_delta"]["total_pnl_sum"],
        ),
    )


def _sweep_summary(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in candidates:
        agg = row["delta_metrics"]["aggregate_delta"]
        out.append(
            {
                "variant": row["variant"]["name"],
                "lookback_losses": row["variant"]["lookback_losses"],
                "risk_multiplier": row["variant"]["risk_multiplier"],
                "passed": row["passed"],
                "expected_value_score_delta": agg["expected_value_score_sum"],
                "total_pnl_delta": agg["total_pnl_sum"],
                "improved_windows": row["gate4"]["improved_windows"],
                "regressed_windows": row["gate4"]["regressed_windows"],
                "adjusted_signal_count": row["gate4"]["adjusted_signal_count"],
                "max_drawdown_worse": row["gate4"]["max_drawdown_worse"],
            }
        )
    return out


def _markdown(payload: dict[str, Any]) -> str:
    sweep_rows = [
        "| Variant | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |",
        "|---|:---:|---:|---:|---|---|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        sweep_rows.append(
            "| {name} | {passed} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {adj} | {dd:+.4f} |".format(
                name=row["variant"],
                passed="PASS" if row["passed"] else "FAIL",
                dev=row["expected_value_score_delta"],
                dpnl=row["total_pnl_delta"],
                improved=", ".join(row["improved_windows"]) or "-",
                regressed=", ".join(row["regressed_windows"]) or "-",
                adj=row["adjusted_signal_count"],
                dd=row["max_drawdown_worse"],
            )
        )
    window_rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        window_rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {ddd:+.4f} | {surv:.4f} | {adj} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                ddd=delta.get("max_drawdown_pct", 0.0),
                surv=after["survival_rate"],
                adj=len(payload["adjustments"][label]),
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Portfolio Loss-Streak Risk",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: post-sizing risk multiplier after the last N closed core trades were all losses. No entry filter, ranking, exit, target, universe, LLM/news, event sleeve, slot, or existing sizing rule changed.",
            "",
            "## Sweep",
            "",
            *sweep_rows,
            "",
            f"Selected variant: `{payload['parameters']['selected_variant']}`.",
            "",
            "## Selected Three-Window Result",
            "",
            *window_rows,
            "",
            "Production impact: replay-only scout. Positive promotion requires shared production-visible closed-trade state, a shared sizing policy, and parity tests before any live/default behavior change.",
        ]
    )


def run() -> dict[str, Any]:
    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    before_runs = {label: _run_window(label, None) for label in base.WINDOWS}
    sweep_results = [_candidate_payload(variant, before_runs) for variant in SWEEP]
    selected_summary = _select_candidate(sweep_results)
    selected = _candidate_payload(
        selected_summary["variant"],
        before_runs,
        include_details=True,
    )
    selected_variant = selected["variant"]["name"]
    decision = (
        "positive_shadow_requires_shared_policy_before_retention"
        if selected["passed"]
        else "rejected_portfolio_loss_streak_risk"
    )
    interpretation = (
        "Portfolio loss-streak risk scaling cleared the canonical three-window gate as a shadow scout; it is not retained until the same state and sizing policy are implemented in shared production/backtest code."
        if selected["passed"]
        else "Portfolio loss-streak risk scaling did not clear the canonical three-window gate; recent closed losses are not a sufficient allocator on this sample."
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "After multiple consecutive closed core losses, the accepted strategy "
            "may be in a locally unfavorable state. Reducing post-sizing risk on "
            "subsequent entries may improve expected value without adding a filter."
        ),
        "change_type": "risk_allocation_shadow",
        "changed_variable": "portfolio_loss_streak_post_sizing_risk_multiplier",
        "single_causal_variable": (
            "post-sizing risk multiplier applied when the latest N closed core trades are losses"
        ),
        "parameters": {
            "sweep": SWEEP,
            "selected_variant": selected_variant,
            "selected_lookback_losses": selected["variant"]["lookback_losses"],
            "selected_risk_multiplier": selected["variant"]["risk_multiplier"],
            "locked_variables": [
                "core universe",
                "candidate pool",
                "entry filters",
                "candidate ranking",
                "stop and target logic",
                "all existing sizing multipliers",
                "portfolio heat",
                "slot limits",
                "LLM/news replay",
                "Space sleeves",
                "event sleeves",
            ],
            "anti_js": "No JavaScript was used.",
        },
        "historical_experiment_check": {
            "similar_prior_results": {
                "exp-20260422-014": (
                    "Rejected breakout-only self-cooldown; this run tests a "
                    "portfolio-level all-entry risk scalar rather than a "
                    "breakout-only entry cooldown."
                ),
                "exp-20260510-018": (
                    "Rejected effective-slot scout; this run does not change "
                    "slot accounting or entry eligibility."
                ),
                "exp-20260514-030": (
                    "Latest accepted core allocation stack; used unchanged as baseline."
                ),
            },
            "blocked_higher_priority_surfaces": {
                "LLM_soft_ranking": "insufficient historical structured prompt/output attribution for a reliable alpha replay",
                "SEC_earnings_semantics": "current state blocks same-sample queue/lifecycle retunes; next step needs new fields or forward replacement outcomes",
                "Space_forward_replacement": "current state requires new closed outcomes before more nearby same-sample retunes",
                "short_interest_index_rebalance": "no complete PIT-safe structured fields found for a direct three-window alpha test",
            },
        },
        "gate_questions": {
            "1_alpha_hypothesis": "portfolio-level realized loss streak as a risk-allocation state variable",
            "2_history_check": "nearest prior was breakout-only cooldown, not all-entry portfolio risk scaling; repeated nearby RS/cap/top-up retunes are avoided",
            "3_single_causal_variable": "loss-streak-triggered post-sizing risk multiplier only",
            "4_acceptance_standard": "docs/backtesting.md fixed three-window replay; aggregate EV/PnL positive, at least two EV-improved windows, no EV-regressed windows, survival >= 5%, max DD worsening <= 0.5pp",
            "5_reproducibility": "Run .venv\\Scripts\\python.exe quant\\experiments\\exp_20260514_043_portfolio_loss_streak_risk.py",
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
                "closed core trade pnl",
                "closed core trade exit_date",
                "sizing shares_to_buy",
                "sizing entry_price",
                "sizing net_risk_per_share",
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
            "minimum_after_survival_rate": selected["delta_metrics"]["aggregate_after"][
                "survival_rate_min"
            ],
            "passed": selected["delta_metrics"]["aggregate_after"]["survival_rate_min"]
            >= 0.05,
        },
        "gate4": selected["gate4"],
        "before_metrics": selected["before_metrics"],
        "after_metrics": selected["after_metrics"],
        "delta_metrics": selected["delta_metrics"],
        "sweep_summary": _sweep_summary(sweep_results),
        "adjustments": selected["adjustments"],
        "changed_trades": selected["changed_trades"],
        "sizing_attribution": selected["sizing_attribution"],
        "expected_value_score_delta": selected["expected_value_score_delta"],
        "total_pnl_delta": selected["total_pnl_delta"],
        "llm_metrics": {"used_llm": False},
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
        },
        "interpretation": interpretation,
        "rejection_reason": None if selected["passed"] else interpretation,
        "next_evidence_needed": (
            "Implement shared production-visible closed-trade state and parity tests before retaining this positive shadow candidate."
            if selected["passed"]
            else "Try a different alpha surface; this portfolio-level loss-streak allocator does not justify production policy work."
        ),
        "related_files": [
            "quant/experiments/exp_20260514_043_portfolio_loss_streak_risk.py",
            "data/experiments/exp-20260514-043/portfolio_loss_streak_risk.json",
            "experiments/logs/exp-20260514-043.json",
            "experiments/tickets/exp-20260514-043.json",
            "experiments/artifacts/exp-20260514-043_portfolio_loss_streak_risk.md",
            "docs/experiment_log.jsonl",
        ],
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
        base.REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    )
    ticket_path = (
        base.REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
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
        "selected_variant": payload["parameters"]["selected_variant"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["total_pnl_delta"],
        "gate4_passed": payload["gate4"]["passed"],
        "summary": payload["interpretation"],
        "artifact": str(artifact_path.relative_to(base.REPO_ROOT)),
    }
    _write_json(artifact_path, payload)
    _write_json(log_path, payload)
    _write_json(ticket_path, ticket)
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
                "selected_variant": result["parameters"]["selected_variant"],
                "gate4_passed": result["gate4"]["passed"],
                "expected_value_score_delta": result["expected_value_score_delta"],
                "total_pnl_delta": result["total_pnl_delta"],
                "sweep_summary": result["sweep_summary"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
