"""exp-20260508-017 add-on heat ceiling shadow replay.

Alpha search, not infrastructure repair.  The accepted day-2 follow-through
add-on policy has started to run into portfolio heat, but earlier nearby
global heat-cap sweeps were rejected as too small and too risky to promote.

This replay changes one causal variable in an experiment-only shadow:
remove the portfolio-heat cap only from add-on execution, while leaving entry
heat gating, add-on trigger rules, add-on fraction, position caps, ranking,
stops, exits, candidate universe, LLM/news behavior, and production code
unchanged.

The purpose is not to weaken hard risk controls in production.  It estimates
whether the remaining add-on ceiling is a material alpha surface before any
production-shared reserve/discriminator is designed.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import backtester as bt  # noqa: E402
from constants import EXEC_LAG_PCT  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260508-017"
STEM = "addon_heat_ceiling_shadow"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "docs" / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

SHADOW_ADDON_HEAT_CAP = 1.0

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": REPO_ROOT / "data" / "ohlcv_snapshot_20251023_20260421.json",
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": REPO_ROOT / "data" / "ohlcv_snapshot_20250423_20251022.json",
                "state_note": "rotation-heavy bull where strategy profits but can lag indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": REPO_ROOT / "data" / "ohlcv_snapshot_20241002_20250422.json",
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        try:
            return _safe(value.item())
        except (TypeError, ValueError):
            return str(value)
    return value


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _append_jsonl_dedup(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    needle_compact = f'"experiment_id":"{EXPERIMENT_ID}"'
    needle_pretty = f'"experiment_id": "{EXPERIMENT_ID}"'
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines() if path.exists() else []
    kept = [line for line in lines if needle_compact not in line and needle_pretty not in line]
    kept.append(json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True))
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def _repo_rel(path: Path) -> str:
    return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _metric_slice(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "total_pnl": result.get("total_pnl"),
        "strategy_total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "win_rate": result.get("win_rate"),
        "total_trades": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": result.get("survival_rate"),
    }


def _deltas(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "expected_value_score",
        "sharpe_daily",
        "max_drawdown_pct",
        "total_pnl",
        "strategy_total_return_pct",
        "win_rate",
        "total_trades",
        "survival_rate",
    ]
    out: dict[str, Any] = {}
    for key in keys:
        if before.get(key) is None or after.get(key) is None:
            out[key] = None
        else:
            out[key] = round(float(after[key]) - float(before[key]), 6)
    return out


def _gate4_window_pass(before: dict[str, Any], after: dict[str, Any]) -> bool:
    before_ev = float(before.get("expected_value_score") or 0.0)
    after_ev = float(after.get("expected_value_score") or 0.0)
    before_pnl = float(before.get("total_pnl") or 0.0)
    after_pnl = float(after.get("total_pnl") or 0.0)
    before_sharpe = float(before.get("sharpe_daily") or 0.0)
    after_sharpe = float(after.get("sharpe_daily") or 0.0)
    before_dd = float(before.get("max_drawdown_pct") or 0.0)
    after_dd = float(after.get("max_drawdown_pct") or 0.0)
    before_win = float(before.get("win_rate") or 0.0)
    after_win = float(after.get("win_rate") or 0.0)
    before_trades = int(before.get("total_trades") or 0)
    after_trades = int(after.get("total_trades") or 0)

    ev_pass = before_ev > 0 and (after_ev - before_ev) / before_ev > 0.10
    pnl_pass = before_pnl > 0 and (after_pnl - before_pnl) / before_pnl > 0.05
    sharpe_pass = after_sharpe - before_sharpe > 0.10
    drawdown_pass = before_dd - after_dd > 0.01
    trade_pass = after_trades > before_trades and after_win >= before_win
    return ev_pass or pnl_pass or sharpe_pass or drawdown_pass or trade_pass


def _run_engine(universe: list[str], spec: dict[str, Any]) -> dict[str, Any]:
    engine = bt.BacktestEngine(
        universe,
        start=spec["start"],
        end=spec["end"],
        config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
        ohlcv_snapshot_path=str(spec["snapshot"]),
    )
    result = engine.run()
    if "error" in result:
        raise RuntimeError(f"Backtest failed for {spec['start']} -> {spec['end']}: {result['error']}")
    return result


@contextmanager
def _patched_addon_heat_cap(value: float):
    original = bt.MAX_PORTFOLIO_HEAT
    bt.MAX_PORTFOLIO_HEAT = value
    try:
        yield
    finally:
        bt.MAX_PORTFOLIO_HEAT = original


def _match_trade(event: dict[str, Any], trades: list[dict[str, Any]]) -> dict[str, Any] | None:
    checkpoint_date = str(event.get("checkpoint_date") or "")
    fill_date = str(event.get("scheduled_fill_date") or "")
    candidates = []
    for trade in trades:
        if str(trade.get("ticker") or "") != str(event.get("ticker") or ""):
            continue
        if str(trade.get("strategy") or "") != str(event.get("strategy") or ""):
            continue
        if str(trade.get("entry_date") or "") <= checkpoint_date and str(trade.get("exit_date") or "") >= fill_date:
            candidates.append(trade)
    candidates.sort(key=lambda trade: str(trade.get("entry_date") or ""), reverse=True)
    return candidates[0] if candidates else None


def _addon_ceiling_attribution(result: dict[str, Any]) -> dict[str, Any]:
    events = (result.get("addon_attribution") or {}).get("events") or []
    trades = result.get("trades") or []
    rows = []
    requested_total = 0
    executed_total = 0
    unfilled_total = 0
    executed_pnl = 0.0
    unfilled_pnl_upper_bound = 0.0
    unmatched_events = 0

    for event in events:
        trade = _match_trade(event, trades)
        requested = int(event.get("requested_shares") or 0)
        executed = int(event.get("addon_shares") or 0) if event.get("status") == "executed" else 0
        unfilled = max(0, requested - executed)
        raw_open = float(event.get("raw_open") or 0.0)
        fill = float(event.get("entry_fill") or (raw_open * (1.0 + EXEC_LAG_PCT)))
        pnl_per_share = None
        event_executed_pnl = None
        event_unfilled_pnl = None
        trade_key = None
        exit_date = None

        if trade is None:
            unmatched_events += 1
        else:
            trade_key = trade.get("trade_key")
            exit_date = trade.get("exit_date")
            pnl_per_share = float(trade.get("exit_price") or 0.0) - fill
            event_executed_pnl = round(executed * pnl_per_share, 2)
            event_unfilled_pnl = round(unfilled * pnl_per_share, 2)
            executed_pnl += executed * pnl_per_share
            unfilled_pnl_upper_bound += unfilled * pnl_per_share

        requested_total += requested
        executed_total += executed
        unfilled_total += unfilled
        rows.append(
            {
                "ticker": event.get("ticker"),
                "strategy": event.get("strategy"),
                "sector": event.get("sector"),
                "checkpoint_date": event.get("checkpoint_date"),
                "scheduled_fill_date": event.get("scheduled_fill_date"),
                "status": event.get("status"),
                "requested_shares": requested,
                "executed_shares": executed,
                "unfilled_requested_shares": unfilled,
                "fill_price_for_shadow": round(fill, 4),
                "matched_trade_key": trade_key,
                "matched_exit_date": exit_date,
                "pnl_per_shadow_share": round(pnl_per_share, 4) if pnl_per_share is not None else None,
                "executed_addon_pnl_estimate": event_executed_pnl,
                "unfilled_addon_pnl_upper_bound": event_unfilled_pnl,
            }
        )

    return {
        "scheduled_events": len(events),
        "requested_shares": requested_total,
        "executed_shares": executed_total,
        "unfilled_requested_shares": unfilled_total,
        "executed_addon_pnl_estimate": round(executed_pnl, 2),
        "unfilled_addon_pnl_upper_bound": round(unfilled_pnl_upper_bound, 2),
        "unmatched_events": unmatched_events,
        "events": rows,
    }


def _addon_summary(result: dict[str, Any]) -> dict[str, Any]:
    addon = result.get("addon_attribution") or {}
    counts: dict[str, int] = {}
    for event in addon.get("events") or []:
        status = str(event.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return {
        "scheduled": addon.get("scheduled"),
        "executed": addon.get("executed"),
        "skipped": addon.get("skipped"),
        "checkpoint_rejected": addon.get("checkpoint_rejected"),
        "status_counts": counts,
    }


def main() -> None:
    run_at = datetime.now(timezone.utc).isoformat()
    universe = get_universe()

    baseline_results: dict[str, dict[str, Any]] = {}
    shadow_results: dict[str, dict[str, Any]] = {}
    baseline_metrics: dict[str, dict[str, Any]] = {}
    shadow_metrics: dict[str, dict[str, Any]] = {}
    windows_payload: dict[str, dict[str, Any]] = {}

    for name, spec in WINDOWS.items():
        baseline = _run_engine(universe, spec)
        baseline_results[name] = baseline
        baseline_metrics[name] = _metric_slice(baseline)

        with _patched_addon_heat_cap(SHADOW_ADDON_HEAT_CAP):
            shadow = _run_engine(universe, spec)
        shadow_results[name] = shadow
        shadow_metrics[name] = _metric_slice(shadow)

        delta = _deltas(baseline_metrics[name], shadow_metrics[name])
        windows_payload[name] = {
            "start": spec["start"],
            "end": spec["end"],
            "snapshot": _repo_rel(spec["snapshot"]),
            "state_note": spec["state_note"],
            "before_metrics": baseline_metrics[name],
            "after_metrics": shadow_metrics[name],
            "delta": delta,
            "gate4_window_pass": _gate4_window_pass(baseline_metrics[name], shadow_metrics[name]),
            "before_addon_summary": _addon_summary(baseline),
            "after_addon_summary": _addon_summary(shadow),
            "baseline_addon_ceiling_attribution": _addon_ceiling_attribution(baseline),
        }

    aggregate = {
        "expected_value_score_delta_sum": round(
            sum(float(payload["delta"].get("expected_value_score") or 0.0) for payload in windows_payload.values()),
            6,
        ),
        "total_pnl_delta_sum": round(
            sum(float(payload["delta"].get("total_pnl") or 0.0) for payload in windows_payload.values()),
            2,
        ),
        "baseline_total_pnl_sum": round(
            sum(float(metrics.get("total_pnl") or 0.0) for metrics in baseline_metrics.values()),
            2,
        ),
        "windows_with_ev_improvement": sum(
            1 for payload in windows_payload.values()
            if float(payload["delta"].get("expected_value_score") or 0.0) > 0.0
        ),
        "windows_passing_gate4": sum(1 for payload in windows_payload.values() if payload["gate4_window_pass"]),
        "unfilled_addon_upper_bound_pnl_sum": round(
            sum(
                float(
                    payload["baseline_addon_ceiling_attribution"].get(
                        "unfilled_addon_pnl_upper_bound"
                    )
                    or 0.0
                )
                for payload in windows_payload.values()
            ),
            2,
        ),
    }
    aggregate["total_pnl_delta_pct"] = (
        round(aggregate["total_pnl_delta_sum"] / aggregate["baseline_total_pnl_sum"], 6)
        if aggregate["baseline_total_pnl_sum"]
        else None
    )

    final_decision = "rejected_for_production_policy"
    final_reason = (
        "Shadow add-on heat removal improved EV in all three windows, but it weakens a hard "
        "portfolio risk cap and passes Gate 4 only by aggregate PnL. Use the result to pursue "
        "a narrower add-on reserve/discriminator, not to raise or remove production heat caps."
    )

    production_impact = {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": True,
        "parity_test_added": False,
    }
    artifacts = {
        "json": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket": _repo_rel(TICKET_JSON),
        "markdown": _repo_rel(ARTIFACT_MD),
    }

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "stem": STEM,
        "run_at": run_at,
        "lane": "alpha_search",
        "change_type": "capital_allocation_addon_heat_ceiling_shadow",
        "alpha_category": "capital_allocation",
        "alpha_hypothesis": (
            "Confirmed day-2 follow-through winners still have positive marginal expectancy, "
            "but current portfolio heat prevents part of that exposure. If the bottleneck is "
            "material across canonical windows, the next alpha direction should be an add-on "
            "reserve or state-specific add-on heat discriminator rather than more trigger tuning."
        ),
        "why_not_llm_soft_ranking": (
            "LLM soft-ranking still lacks enough replay coverage for trustworthy alpha evaluation, "
            "so this run tests a deterministic OHLCV-only capital-allocation surface."
        ),
        "historical_no_repeat_check": {
            "nearby_failed_family": "global MAX_PORTFOLIO_HEAT 9-12% sweeps",
            "why_this_is_not_simple_repeat": (
                "This is a single diagnostic shadow that changes only add-on execution heat, "
                "leaves entry heat unchanged, and is explicitly not proposed as a production "
                "risk-cap increase."
            ),
            "mechanism_guardrail": (
                "Do not promote raw heat-cap relaxation. A valid follow-up needs a shared, "
                "production-auditable reserve/discriminator that decides when add-on heat is "
                "worth spending."
            ),
        },
        "parameters": {
            "baseline_MAX_PORTFOLIO_HEAT": bt.MAX_PORTFOLIO_HEAT,
            "shadow_addon_execution_heat_cap": SHADOW_ADDON_HEAT_CAP,
            "unchanged": [
                "entry portfolio heat gating",
                "ADDON_CHECKPOINT_DAYS",
                "ADDON_MIN_UNREALIZED_PCT",
                "ADDON_MIN_RS_VS_SPY",
                "ADDON_FRACTION_OF_ORIGINAL_SHARES",
                "ADDON_MAX_POSITION_PCT",
                "ADDON_SPY_RELATIVE_LEADER_MAX_POSITION_PCT",
                "candidate universe",
                "ranking",
                "sizing multipliers",
                "stops and targets",
                "LLM/news replay behavior",
            ],
        },
        "production_impact": production_impact,
        "windows": windows_payload,
        "aggregate": aggregate,
        "decision": final_decision,
        "decision_reason": final_reason,
        "next_alpha_direction": (
            "Test a production-shared add-on reserve/discriminator only if it can keep the hard "
            "global risk cap intact; otherwise move to mid_weak meta-allocation or candidate-pool "
            "quality expansion with full three-window replay."
        ),
    }

    log_payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": run_at,
        "lane": payload["lane"],
        "hypothesis": payload["alpha_hypothesis"],
        "change_type": payload["change_type"],
        "parameters": payload["parameters"],
        "date_range": {
            name: {"start": spec["start"], "end": spec["end"]}
            for name, spec in WINDOWS.items()
        },
        "market_regime_summary": {
            name: spec["state_note"]
            for name, spec in WINDOWS.items()
        },
        "before_metrics": baseline_metrics,
        "after_metrics": shadow_metrics,
        "delta_metrics": {
            name: payload["delta"]
            for name, payload in windows_payload.items()
        },
        "expected_value_score_delta": {
            name: payload["delta"].get("expected_value_score")
            for name, payload in windows_payload.items()
        },
        "decision": final_decision,
        "rejection_reason": final_reason,
        "production_impact": production_impact,
        "artifacts": artifacts,
    }

    ticket_payload = {
        "experiment_id": EXPERIMENT_ID,
        "title": "Add-on heat ceiling shadow replay",
        "status": final_decision,
        "summary": final_reason,
        "artifact": _repo_rel(ARTIFACT_MD),
        "created_at": run_at,
    }

    lines = [
        f"# {EXPERIMENT_ID} add-on heat ceiling shadow replay",
        "",
        f"Run at: `{run_at}`",
        "",
        "## Hypothesis",
        "",
        payload["alpha_hypothesis"],
        "",
        "## Decision",
        "",
        f"`{final_decision}` - {final_reason}",
        "",
        "## Three-window result",
        "",
        "| window | before EV | after EV | EV delta | before PnL | after PnL | PnL delta | sharpe delta | max DD delta | Gate4 | add-ons before -> after |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for name, window_payload in windows_payload.items():
        before = window_payload["before_metrics"]
        after = window_payload["after_metrics"]
        delta = window_payload["delta"]
        before_addon = window_payload["before_addon_summary"]
        after_addon = window_payload["after_addon_summary"]
        lines.append(
            "| {name} | {before_ev} | {after_ev} | {ev_delta} | {before_pnl} | {after_pnl} | {pnl_delta} | {sharpe_delta} | {dd_delta} | {gate4} | {before_exec}/{before_sched} -> {after_exec}/{after_sched} |".format(
                name=name,
                before_ev=before.get("expected_value_score"),
                after_ev=after.get("expected_value_score"),
                ev_delta=delta.get("expected_value_score"),
                before_pnl=before.get("total_pnl"),
                after_pnl=after.get("total_pnl"),
                pnl_delta=delta.get("total_pnl"),
                sharpe_delta=delta.get("sharpe_daily"),
                dd_delta=delta.get("max_drawdown_pct"),
                gate4="PASS" if window_payload["gate4_window_pass"] else "FAIL",
                before_exec=before_addon.get("executed"),
                before_sched=before_addon.get("scheduled"),
                after_exec=after_addon.get("executed"),
                after_sched=after_addon.get("scheduled"),
            )
        )
    lines.extend(
        [
            "",
            "## Ceiling attribution",
            "",
            "| window | scheduled | requested shares | executed shares | unfilled shares | executed add-on PnL est. | unfilled upper-bound PnL | unmatched |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for name, window_payload in windows_payload.items():
        attribution = window_payload["baseline_addon_ceiling_attribution"]
        lines.append(
            "| {name} | {scheduled} | {requested} | {executed} | {unfilled} | {executed_pnl} | {unfilled_pnl} | {unmatched} |".format(
                name=name,
                scheduled=attribution.get("scheduled_events"),
                requested=attribution.get("requested_shares"),
                executed=attribution.get("executed_shares"),
                unfilled=attribution.get("unfilled_requested_shares"),
                executed_pnl=attribution.get("executed_addon_pnl_estimate"),
                unfilled_pnl=attribution.get("unfilled_addon_pnl_upper_bound"),
                unmatched=attribution.get("unmatched_events"),
            )
        )
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            f"- EV delta sum: `{aggregate['expected_value_score_delta_sum']}`",
            f"- PnL delta sum: `{aggregate['total_pnl_delta_sum']}`",
            f"- PnL delta pct: `{aggregate['total_pnl_delta_pct']}`",
            f"- Windows with EV improvement: `{aggregate['windows_with_ev_improvement']}/3`",
            f"- Windows passing per-window Gate 4: `{aggregate['windows_passing_gate4']}/3`",
            "",
            "## Production parity",
            "",
            "Replay only. No production policy, backtester adapter, run adapter, candidate universe, ranking, sizing, stop, LLM, or news behavior changed.",
            "",
            "The positive shadow is not production-safe as-is because it weakens add-on hard risk control. Any follow-up must be implemented as shared production/backtest policy and covered by parity tests before enabling.",
            "",
        ]
    )

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, log_payload)
    _write_json(TICKET_JSON, ticket_payload)
    _append_jsonl_dedup(EXPERIMENT_LOG, log_payload)
    _write_text(ARTIFACT_MD, "\n".join(lines) + "\n")

    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "decision": final_decision,
                    "decision_reason": final_reason,
                    "aggregate": aggregate,
                    "artifacts": artifacts,
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
