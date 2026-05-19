"""exp-20260505-016: breakout DTE residual zero-risk replay.

Alpha search. Tests one allocation variable: whether the already-haircut
Financials/Healthcare breakout event-proximity sleeve should be zero-risk
instead of 0.25x risk.

No production order path is changed by this runner. A positive result must be
promoted through shared run/backtester policy before it can affect live orders.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import portfolio_engine as pe  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260505-016"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "breakout_dte_zero_risk.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_breakout_dte_zero_risk.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
PLAYBOOK = REPO_ROOT / "docs" / "alpha-optimization-playbook.md"

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
        "state_note": "slow-melt bull / accepted-stack dominant tape",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
        "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "state_note": "mixed-to-weak older tape with lower win rate",
    }),
])

PATCHED_MULTIPLIERS = OrderedDict([
    ("BREAKOUT_FINANCIALS_DTE_RISK_MULTIPLIER", 0.0),
    ("BREAKOUT_HEALTHCARE_DTE_RISK_MULTIPLIER", 0.0),
])

AFFECTED_KEYS = (
    "breakout_financials_dte_risk_multiplier_applied",
    "breakout_healthcare_dte_risk_multiplier_applied",
)


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return round(value, digits)


def _safe_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe_payload(item) for item in value]
    if isinstance(value, tuple):
        return [_safe_payload(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe_payload(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_safe_payload(payload), sort_keys=True))
        handle.write("\n")


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    reason_counts = (
        result.get("entry_execution_attribution") or {}
    ).get("reason_counts") or {}
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "sharpe": _round(result.get("sharpe"), 2),
        "sharpe_daily": _round(result.get("sharpe_daily"), 2),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "total_return_pct": _round(benchmarks.get("strategy_total_return_pct"), 4),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": _round(result.get("survival_rate"), 4),
        "converged": bool((result.get("convergence") or {}).get("converged")),
        "entered": reason_counts.get("entered", 0),
        "no_shares": reason_counts.get("no_shares", 0),
        "slot_sliced": reason_counts.get("slot_sliced", 0),
        "scarce_slot_breakout_deferred": reason_counts.get(
            "scarce_slot_breakout_deferred",
            0,
        ),
        "gap_cancel": reason_counts.get("gap_cancel", 0),
        "adverse_gap_down_cancel": reason_counts.get("adverse_gap_down_cancel", 0),
        "entry_reason_counts": reason_counts,
    }


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "expected_value_score",
        "sharpe",
        "sharpe_daily",
        "total_pnl",
        "total_return_pct",
        "max_drawdown_pct",
        "win_rate",
        "trade_count",
        "signals_generated",
        "signals_survived",
        "survival_rate",
        "entered",
        "no_shares",
        "slot_sliced",
        "scarce_slot_breakout_deferred",
        "gap_cancel",
        "adverse_gap_down_cancel",
    )
    out: dict[str, Any] = {}
    for field in fields:
        before_value = before.get(field)
        after_value = after.get(field)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            if field in {
                "trade_count",
                "signals_generated",
                "signals_survived",
                "entered",
                "no_shares",
                "slot_sliced",
                "scarce_slot_breakout_deferred",
                "gap_cancel",
                "adverse_gap_down_cancel",
            }:
                out[field] = int(after_value - before_value)
            else:
                out[field] = _round(after_value - before_value, 6)
    return out


def _affected_trades(result: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for trade in result.get("trades") or []:
        multipliers = trade.get("sizing_multipliers") or {}
        touched = {
            key: multipliers.get(key)
            for key in AFFECTED_KEYS
            if multipliers.get(key) not in (None, 1, 1.0, False)
        }
        if not touched:
            continue
        rows.append({
            "trade_key": trade.get("trade_key"),
            "ticker": trade.get("ticker"),
            "strategy": trade.get("strategy"),
            "sector": trade.get("sector"),
            "entry_date": trade.get("entry_date"),
            "exit_date": trade.get("exit_date"),
            "exit_reason": trade.get("exit_reason"),
            "pnl": _round(trade.get("pnl"), 2),
            "pnl_pct_net": _round(trade.get("pnl_pct_net"), 6),
            "actual_risk_pct": _round(trade.get("actual_risk_pct"), 6),
            "regime_exit_bucket": trade.get("regime_exit_bucket"),
            "regime_exit_score": _round(trade.get("regime_exit_score"), 4),
            "sizing_multipliers": touched,
        })
    return rows


def _affected_signal_attribution(result: dict[str, Any]) -> dict[str, Any]:
    signal_attr = result.get("sizing_rule_signal_attribution") or {}
    trade_attr = result.get("sizing_rule_trade_attribution") or {}
    return {
        key: {
            "signals": signal_attr.get(key),
            "trades": trade_attr.get(key),
        }
        for key in AFFECTED_KEYS
    }


class MultiplierPatch:
    def __init__(self, values: OrderedDict[str, float]):
        self.values = values
        self.originals: dict[str, Any] = {}

    def __enter__(self) -> "MultiplierPatch":
        for name, value in self.values.items():
            self.originals[name] = getattr(pe, name)
            setattr(pe, name, value)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        for name, value in self.originals.items():
            setattr(pe, name, value)


def _run_window(window: dict[str, str], patch: bool = False) -> dict[str, Any]:
    context = MultiplierPatch(PATCHED_MULTIPLIERS) if patch else None
    if context is None:
        return BacktestEngine(
            sorted(get_universe()),
            start=window["start"],
            end=window["end"],
            config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
        ).run()
    with context:
        return BacktestEngine(
            sorted(get_universe()),
            start=window["start"],
            end=window["end"],
            config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
        ).run()


def _aggregate_delta(rows: OrderedDict[str, dict[str, Any]]) -> dict[str, Any]:
    before_ev = sum(row["before"]["expected_value_score"] for row in rows.values())
    after_ev = sum(row["after"]["expected_value_score"] for row in rows.values())
    before_pnl = sum(row["before"]["total_pnl"] for row in rows.values())
    after_pnl = sum(row["after"]["total_pnl"] for row in rows.values())
    deltas = {label: row["delta"] for label, row in rows.items()}
    ev_windows_improved = sum(
        1 for delta in deltas.values() if delta.get("expected_value_score", 0) > 0
    )
    ev_windows_regressed = sum(
        1 for delta in deltas.values() if delta.get("expected_value_score", 0) < 0
    )
    pnl_windows_improved = sum(
        1 for delta in deltas.values() if delta.get("total_pnl", 0) > 0
    )
    pnl_windows_regressed = sum(
        1 for delta in deltas.values() if delta.get("total_pnl", 0) < 0
    )
    max_drawdown_delta_max = max(
        delta.get("max_drawdown_pct", 0) for delta in deltas.values()
    )
    return {
        "baseline_expected_value_score_sum": _round(before_ev, 4),
        "after_expected_value_score_sum": _round(after_ev, 4),
        "expected_value_score_delta_sum": _round(after_ev - before_ev, 4),
        "expected_value_score_delta_pct": _round(
            (after_ev - before_ev) / abs(before_ev),
            6,
        ) if before_ev else None,
        "baseline_total_pnl_sum": _round(before_pnl, 2),
        "after_total_pnl_sum": _round(after_pnl, 2),
        "total_pnl_delta_sum": _round(after_pnl - before_pnl, 2),
        "total_pnl_delta_pct": _round(
            (after_pnl - before_pnl) / abs(before_pnl),
            6,
        ) if before_pnl else None,
        "ev_windows_improved": ev_windows_improved,
        "ev_windows_regressed": ev_windows_regressed,
        "pnl_windows_improved": pnl_windows_improved,
        "pnl_windows_regressed": pnl_windows_regressed,
        "sharpe_delta_max": max(delta.get("sharpe_daily", 0) for delta in deltas.values()),
        "drawdown_delta_max": _round(max_drawdown_delta_max, 6),
        "drawdown_delta_min": _round(
            min(delta.get("max_drawdown_pct", 0) for delta in deltas.values()),
            6,
        ),
        "trade_count_delta_sum": sum(delta.get("trade_count", 0) for delta in deltas.values()),
        "win_rate_delta_min": min(delta.get("win_rate", 0) for delta in deltas.values()),
    }


def _gate4(aggregate: dict[str, Any], rows: OrderedDict[str, dict[str, Any]]) -> dict[str, Any]:
    material = any([
        (aggregate.get("expected_value_score_delta_pct") or 0) > 0.10,
        aggregate.get("sharpe_delta_max", 0) > 0.10,
        aggregate.get("drawdown_delta_min", 0) < -0.01,
        (aggregate.get("total_pnl_delta_pct") or 0) > 0.05,
        (
            aggregate.get("trade_count_delta_sum", 0) > 0
            and aggregate.get("win_rate_delta_min", -1) >= 0
        ),
    ])
    majority_stable = (
        aggregate.get("ev_windows_improved", 0) >= 2
        and aggregate.get("ev_windows_regressed", 0) == 0
    )
    return {
        "passed": bool(material and majority_stable),
        "materiality_passed": bool(material),
        "multi_window_stability_passed": bool(majority_stable),
        "basis": (
            "Requires Gate 4 materiality plus majority-window EV improvement "
            "on the three fixed backtesting.md windows."
        ),
    }


def _artifact(payload: dict[str, Any]) -> str:
    agg = payload["delta_metrics"]["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} breakout DTE zero-risk replay",
        "",
        "## Decision",
        "",
        f"- decision: {payload['decision']}",
        f"- gate4_passed: {payload['gate4']['passed']}",
        f"- aggregate EV delta: {agg['expected_value_score_delta_sum']} ({agg['expected_value_score_delta_pct']})",
        f"- aggregate PnL delta: {agg['total_pnl_delta_sum']} ({agg['total_pnl_delta_pct']})",
        f"- windows improved/regressed: {agg['ev_windows_improved']} / {agg['ev_windows_regressed']}",
        "",
        "## Why This Was Tested",
        "",
        (
            "Financials and Healthcare breakout DTE trades were already reduced "
            "to 0.25x risk and appeared consistently negative in the current "
            "three-window attribution. This replay tests whether the residual "
            "event-proximity sleeve should be zero-risk."
        ),
        "",
        "## Window Deltas",
        "",
    ]
    for label, row in payload["rows"].items():
        delta = row["delta"]
        lines.append(
            f"- {label}: EV {delta.get('expected_value_score')} | "
            f"PnL {delta.get('total_pnl')} | SharpeD {delta.get('sharpe_daily')} | "
            f"trades {delta.get('trade_count')}"
        )
    lines.extend([
        "",
        "## Production Impact",
        "",
        (
            "Replay-only. If accepted, promotion would require changing the "
            "shared constants used by portfolio_engine so both backtester and "
            "run.py consume the same sizing policy."
        ),
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for label, window in WINDOWS.items():
        print(f"[{label}] baseline")
        before_result = _run_window(window, patch=False)
        print(f"[{label}] breakout_dte_zero")
        after_result = _run_window(window, patch=True)
        before = _metrics(before_result)
        after = _metrics(after_result)
        rows[label] = {
            "window": window,
            "before": before,
            "after": after,
            "delta": _delta(after, before),
            "affected_baseline_trades": _affected_trades(before_result),
            "affected_after_trades": _affected_trades(after_result),
            "affected_signal_attribution_before": _affected_signal_attribution(before_result),
            "affected_signal_attribution_after": _affected_signal_attribution(after_result),
        }

    aggregate = _aggregate_delta(rows)
    gate4 = _gate4(aggregate, rows)
    decision = "accepted" if gate4["passed"] else "rejected"
    timestamp = datetime.now(timezone.utc).isoformat()
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "generated_at": timestamp,
        "status": decision,
        "decision": decision,
        "lane": "alpha_search",
        "change_type": "capital_allocation_breakout_dte_residual",
        "hypothesis": (
            "The already-haircut Financials/Healthcare breakout DTE sleeve is "
            "negative enough that 0.25x still wastes scarce risk budget; moving "
            "only this residual event-proximity breakout family to 0x may improve "
            "EV without touching entries, exits, ranking, universe, add-ons, or LLM/news."
        ),
        "alpha_hypothesis": {
            "category": "capital_allocation",
            "statement": (
                "Residual breakout event-proximity risk should be zeroed only "
                "where the existing DTE haircut already identified a weak sleeve."
            ),
            "why_now": (
                "LLM soft-ranking remains sample-limited, event bundles need "
                "forward outcomes, and recent universe expansions failed. Current "
                "three-window attribution showed this small DTE breakout sleeve "
                "was consistently negative while already marked as fragile."
            ),
        },
        "mechanism_insight_check": {
            "near_repeat": "partial",
            "similar_failed_families": [
                "exp-20260421-024 trend Technology gap 0x retry failed because replacement value mattered",
                "exp-20260505-012 compound haircut skip failed and should not be repeated broadly",
            ],
            "why_not_simple_repeat": (
                "This is not a broad compound-haircut skip or a Technology trend "
                "haircut retry. It isolates only Financials/Healthcare breakout "
                "DTE rules that are already event-proximity haircuts."
            ),
        },
        "parameters": {
            "single_causal_variable": (
                "Financials/Healthcare breakout DTE residual risk multiplier"
            ),
            "baseline": {
                "BREAKOUT_FINANCIALS_DTE_RISK_MULTIPLIER": pe.BREAKOUT_FINANCIALS_DTE_RISK_MULTIPLIER,
                "BREAKOUT_HEALTHCARE_DTE_RISK_MULTIPLIER": pe.BREAKOUT_HEALTHCARE_DTE_RISK_MULTIPLIER,
            },
            "tested": PATCHED_MULTIPLIERS,
            "locked_variables": [
                "universe",
                "OHLCV snapshots",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "all other risk multipliers",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "MAX_PER_SECTOR",
                "gap cancels",
                "all target/stop exits",
                "follow-through add-ons",
                "LLM/news replay",
                "earnings strategy",
            ],
        },
        "date_range": {
            label: f"{window['start']} -> {window['end']}"
            for label, window in WINDOWS.items()
        },
        "market_regime_summary": {
            label: window["state_note"] for label, window in WINDOWS.items()
        },
        "before_metrics": {label: row["before"] for label, row in rows.items()},
        "after_metrics": {label: row["after"] for label, row in rows.items()},
        "delta_metrics": {
            "by_window": {label: row["delta"] for label, row in rows.items()},
            "aggregate": aggregate,
        },
        "rows": rows,
        "gate4": gate4,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_path_if_accepted": (
                "Change quant/constants.py only if Gate 4 passes; portfolio_engine "
                "is shared by backtester and production run.py sizing."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft-ranking remains production-sample limited, so this run "
                "tested deterministic allocation using existing audited DTE fields."
            ),
        },
        "why_not_other_attractive_points": {
            "LLM_soft_ranking": "Still production-sample limited.",
            "event_bundle_promotion": "Needs closed forward paper outcomes.",
            "universe_expansion": "Broad and narrow static expansions just failed.",
            "commodity_or_consumer_target_retry": "Recent nearby target/risk retries failed Gate 4.",
            "second_addon": "Repeatedly rejected or too small under the current stack.",
        },
        "rejection_reason": None if gate4["passed"] else (
            "Gate 4 failed: the effect did not meet materiality plus majority-window "
            "stability on the three fixed backtesting.md windows."
        ),
        "next_retry_requires": [] if gate4["passed"] else [
            "Do not retry nearby Financials/Healthcare breakout DTE zero-risk or 0.1x/0.5x scalars without new forward evidence.",
            "A valid retry needs a richer event-quality discriminator, not another residual DTE multiplier scalar.",
        ],
        "related_files": [
            "quant/experiments/exp_20260505_016_breakout_dte_zero_risk.py",
            "data/experiments/exp-20260505-016/breakout_dte_zero_risk.json",
            "experiments/logs/exp-20260505-016.json",
            "experiments/tickets/exp-20260505-016.json",
            "experiments/artifacts/exp-20260505-016_breakout_dte_zero_risk.md",
            "docs/experiment_log.jsonl",
            "docs/alpha-optimization-playbook.md",
        ],
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(TICKET_JSON, {
        "experiment_id": EXPERIMENT_ID,
        "title": "Breakout DTE residual zero-risk",
        "status": decision,
        "decision": decision,
        "summary": payload["rejection_reason"] or "Gate 4 passed; promote through shared sizing policy.",
        "next_action": (
            "Do not promote; avoid nearby scalar retries."
            if decision == "rejected"
            else "Promote via shared constants and parity tests."
        ),
        "related_log": str(LOG_JSON.relative_to(REPO_ROOT)),
    })
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact(payload), encoding="utf-8")
    _append_jsonl(EXPERIMENT_LOG_JSONL, payload)

    playbook_note = f"""

### 2026-05-05 mechanism update: Breakout DTE residual zero-risk

Core conclusion: {EXPERIMENT_ID} tested whether the already-haircut
Financials/Healthcare breakout event-proximity sleeve should move from 0.25x
risk to 0x. It was a deterministic alpha search, not an LLM or production
parity repair.

Evidence: aggregate EV delta was `{aggregate['expected_value_score_delta_sum']}`
(`{aggregate['expected_value_score_delta_pct']}`) and aggregate PnL delta was
`${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`).
Window EV improved/regressed counts were `{aggregate['ev_windows_improved']}` /
`{aggregate['ev_windows_regressed']}`.

Do not repeat: nearby Financials/Healthcare breakout DTE zero-risk, 0.1x, or
0.5x scalar retries without new forward evidence or a richer event-quality
discriminator.
"""
    with PLAYBOOK.open("a", encoding="utf-8") as handle:
        handle.write(playbook_note)

    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "decision": decision,
        "gate4": gate4,
        "aggregate": aggregate,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
