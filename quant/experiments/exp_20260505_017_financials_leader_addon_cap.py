"""exp-20260505-017: Financials leader first-add-on cap replay.

Alpha search. Tests one lifecycle allocation variable: whether accepted
`trend_long | Financials` sector leaders that pass the existing day-2
follow-through add-on gate deserve the same higher first-add-on cap that the
accepted SPY-relative leader sleeve already receives.

This runner is replay-only. A positive result must be promoted through shared
backtester/production follow-through policy before live orders can change.
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

import backtester as bt  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260505-017"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "financials_leader_addon_cap.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_financials_leader_addon_cap.md"
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

VARIANTS = OrderedDict([
    ("financials_leader_addon_cap_60pct", {"first_addon_cap_pct": 0.60}),
])

FINANCIALS_LEADER_KEY = "financials_sector_leader_risk_multiplier_applied"
SPY_LEADER_ADDON_KEY = "spy_relative_leader_addon_cap"


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
    kept: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                existing = json.loads(line)
            except json.JSONDecodeError:
                kept.append(line)
                continue
            if existing.get("experiment_id") != payload["experiment_id"]:
                kept.append(line)
    kept.append(json.dumps(_safe_payload(payload), sort_keys=True))
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    addon = result.get("addon_attribution") or {}
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
        "addon_scheduled": addon.get("scheduled", 0),
        "addon_executed": addon.get("executed", 0),
        "addon_skipped": addon.get("skipped", 0),
        "addon_checkpoint_rejected": addon.get("checkpoint_rejected", 0),
        "entered": reason_counts.get("entered", 0),
        "no_shares": reason_counts.get("no_shares", 0),
        "slot_sliced": reason_counts.get("slot_sliced", 0),
        "converged": bool((result.get("convergence") or {}).get("converged")),
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
        "addon_scheduled",
        "addon_executed",
        "addon_skipped",
        "addon_checkpoint_rejected",
        "entered",
        "no_shares",
        "slot_sliced",
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
                "addon_scheduled",
                "addon_executed",
                "addon_skipped",
                "addon_checkpoint_rejected",
                "entered",
                "no_shares",
                "slot_sliced",
            }:
                out[field] = int(after_value - before_value)
            else:
                out[field] = _round(after_value - before_value, 6)
    return out


def _is_financials_leader_candidate(candidate: dict[str, Any]) -> bool:
    multipliers = candidate.get("sizing_multipliers") or {}
    value = multipliers.get(FINANCIALS_LEADER_KEY)
    try:
        return float(value) > 1.0
    except (TypeError, ValueError):
        return False


class FinancialsLeaderAddonCapPatch:
    def __init__(self, cap_pct: float):
        self.cap_pct = cap_pct
        self.original = bt.position_was_spy_relative_leader

    def __enter__(self) -> "FinancialsLeaderAddonCapPatch":
        original = self.original

        def patched_position_was_spy_relative_leader(
            candidate: dict[str, Any],
            *,
            ticker_df=None,
            spy_df=None,
            entry_idx=None,
            spy_entry_idx=None,
        ) -> bool:
            if original(
                candidate,
                ticker_df=ticker_df,
                spy_df=spy_df,
                entry_idx=entry_idx,
                spy_entry_idx=spy_entry_idx,
            ):
                return True
            return _is_financials_leader_candidate(candidate)

        bt.position_was_spy_relative_leader = patched_position_was_spy_relative_leader
        bt.ADDON_SPY_RELATIVE_LEADER_MAX_POSITION_PCT = self.cap_pct
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        bt.position_was_spy_relative_leader = self.original
        bt.ADDON_SPY_RELATIVE_LEADER_MAX_POSITION_PCT = (
            bt.DEFAULT_CONFIG["ADDON_SPY_RELATIVE_LEADER_MAX_POSITION_PCT"]
        )


def _run_window(window: dict[str, str], cap_pct: float | None = None) -> dict[str, Any]:
    context = (
        FinancialsLeaderAddonCapPatch(cap_pct)
        if cap_pct is not None
        else None
    )
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


def _financials_leader_addon_events(result: dict[str, Any]) -> list[dict[str, Any]]:
    addon = result.get("addon_attribution") or {}
    events = []
    for event in addon.get("events") or []:
        trade = _trade_for_addon_event(result, event)
        if not trade:
            continue
        multipliers = trade.get("sizing_multipliers") or {}
        if not _is_financials_leader_candidate({"sizing_multipliers": multipliers}):
            continue
        events.append({
            "ticker": event.get("ticker"),
            "strategy": event.get("strategy"),
            "sector": event.get("sector"),
            "checkpoint_date": event.get("checkpoint_date"),
            "scheduled_fill_date": event.get("scheduled_fill_date"),
            "status": event.get("status"),
            "requested_shares": event.get("requested_shares"),
            "addon_shares": event.get("addon_shares"),
            "addon_position_cap": event.get("addon_position_cap"),
            "unrealized_pct": event.get("unrealized_pct"),
            "rs_vs_spy": event.get("rs_vs_spy"),
            "baseline_spy_relative_label": event.get(SPY_LEADER_ADDON_KEY),
            "trade_pnl": _round(trade.get("pnl"), 2),
            "trade_pnl_pct_net": _round(trade.get("pnl_pct_net"), 6),
            "exit_reason": trade.get("exit_reason"),
            "sizing_multipliers": {
                FINANCIALS_LEADER_KEY: multipliers.get(FINANCIALS_LEADER_KEY),
                "trend_financials_risk_multiplier_applied": multipliers.get(
                    "trend_financials_risk_multiplier_applied"
                ),
                "spy_relative_leader_risk_on_multiplier_applied": multipliers.get(
                    "spy_relative_leader_risk_on_multiplier_applied"
                ),
            },
        })
    return events


def _trade_for_addon_event(result: dict[str, Any], event: dict[str, Any]) -> dict[str, Any] | None:
    ticker = event.get("ticker")
    for trade in result.get("trades") or []:
        if trade.get("ticker") != ticker:
            continue
        entry_date = trade.get("entry_date")
        exit_date = trade.get("exit_date")
        checkpoint_date = event.get("checkpoint_date")
        if entry_date and checkpoint_date and str(entry_date) <= str(checkpoint_date):
            if not exit_date or str(checkpoint_date) <= str(exit_date):
                return trade
    return None


def _run_baselines() -> OrderedDict[str, dict[str, Any]]:
    rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for label, window in WINDOWS.items():
        print(f"[{label}] baseline")
        result = _run_window(window)
        rows[label] = {
            "window": window,
            "raw": result,
            "metrics": _metrics(result),
            "financials_leader_addon_events": _financials_leader_addon_events(result),
        }
    return rows


def _run_variant(
    name: str,
    variant: dict[str, Any],
    baselines: OrderedDict[str, dict[str, Any]],
) -> dict[str, Any]:
    rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for label, window in WINDOWS.items():
        cap_pct = float(variant["first_addon_cap_pct"])
        print(f"[{label}] {name}")
        result = _run_window(window, cap_pct=cap_pct)
        before = baselines[label]["metrics"]
        after = _metrics(result)
        events = _financials_leader_addon_events(result)
        rows[label] = {
            "window": window,
            "before": before,
            "after": after,
            "delta": _delta(after, before),
            "financials_leader_addon_events_before": baselines[label]["financials_leader_addon_events"],
            "financials_leader_addon_events_after": events,
            "financials_leader_addon_event_count": len(events),
        }
        print(
            f"[{label}] {name} EV={rows[label]['delta']['expected_value_score']:+.4f} "
            f"PnL={rows[label]['delta']['total_pnl']:+.2f} events={len(events)}"
        )
    aggregate = _aggregate(rows)
    return {
        "parameters": variant,
        "rows": rows,
        "aggregate": aggregate,
        "gate4_passed": _gate4_passed(aggregate),
    }


def _aggregate(rows: OrderedDict[str, dict[str, Any]]) -> dict[str, Any]:
    before_ev = sum(row["before"]["expected_value_score"] for row in rows.values())
    after_ev = sum(row["after"]["expected_value_score"] for row in rows.values())
    before_pnl = sum(row["before"]["total_pnl"] for row in rows.values())
    after_pnl = sum(row["after"]["total_pnl"] for row in rows.values())
    deltas = [row["delta"] for row in rows.values()]
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
        "ev_windows_improved": sum(
            1 for delta in deltas if delta.get("expected_value_score", 0) > 0
        ),
        "ev_windows_regressed": sum(
            1 for delta in deltas if delta.get("expected_value_score", 0) < 0
        ),
        "pnl_windows_improved": sum(
            1 for delta in deltas if delta.get("total_pnl", 0) > 0
        ),
        "pnl_windows_regressed": sum(
            1 for delta in deltas if delta.get("total_pnl", 0) < 0
        ),
        "sharpe_delta_max": _round(
            max(delta.get("sharpe_daily", 0) for delta in deltas),
            6,
        ),
        "drawdown_delta_min": _round(
            min(delta.get("max_drawdown_pct", 0) for delta in deltas),
            6,
        ),
        "drawdown_delta_max": _round(
            max(delta.get("max_drawdown_pct", 0) for delta in deltas),
            6,
        ),
        "trade_count_delta_sum": sum(delta.get("trade_count", 0) for delta in deltas),
        "win_rate_delta_min": _round(
            min(delta.get("win_rate", 0) for delta in deltas),
            6,
        ),
        "addon_executed_delta_sum": sum(delta.get("addon_executed", 0) for delta in deltas),
        "financials_leader_addon_event_count_sum": sum(
            row["financials_leader_addon_event_count"] for row in rows.values()
        ),
    }


def _gate4_passed(aggregate: dict[str, Any]) -> bool:
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
    return bool(material and majority_stable)


def _best_variant(variants: OrderedDict[str, dict[str, Any]]) -> str:
    return max(
        variants,
        key=lambda name: (
            variants[name]["aggregate"]["expected_value_score_delta_sum"],
            variants[name]["aggregate"]["total_pnl_delta_sum"],
            -variants[name]["aggregate"]["drawdown_delta_max"],
        ),
    )


def _make_payload(
    baselines: OrderedDict[str, dict[str, Any]],
    variants: OrderedDict[str, dict[str, Any]],
) -> dict[str, Any]:
    best_name = _best_variant(variants)
    best = variants[best_name]
    accepted = bool(best["gate4_passed"])
    timestamp = datetime.now(timezone.utc).isoformat()
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "generated_at": timestamp,
        "status": "accepted" if accepted else "rejected",
        "decision": "accepted" if accepted else "rejected",
        "lane": "alpha_search",
        "change_type": "capital_allocation_followthrough_addon_cap",
        "hypothesis": (
            "Accepted trend_long Financials sector leaders already receive a "
            "2.5x risk budget, but initial-cap increases were too small and "
            "riskier. If a Financials leader survives to the existing day-2 "
            "follow-through checkpoint, raising only the first add-on cap may "
            "increase convex winner capture without changing entry, exit, "
            "ranking, universe, or LLM/news behavior."
        ),
        "alpha_hypothesis": {
            "category": "capital_allocation / lifecycle",
            "statement": (
                "Financials leader alpha may be better monetized after confirmed "
                "follow-through than at initial entry."
            ),
            "why_now": (
                "LLM soft-ranking remains sample-limited, event sleeves need "
                "forward outcomes, broad universe expansion failed, and recent "
                "mechanism notes ban nearby Financials multipliers and initial "
                "cap scalars but not follow-through lifecycle cap tests."
            ),
        },
        "historical_experiment_check": {
            "similar_prior_results": {
                "exp-20260501-006": (
                    "Accepted Financials sector-leader total risk budget at 2.5x."
                ),
                "exp-20260503-050": (
                    "Financials leader initial position cap was positive but too "
                    "small; this tests confirmed follow-through add-on capacity, "
                    "not initial entry cap."
                ),
                "exp-20260502-022": (
                    "Accepted SPY-relative leader first-add-on cap at 60%; this "
                    "tests whether a different accepted leader sleeve has similar "
                    "post-entry capacity."
                ),
            },
            "mechanism_insight_check": (
                "Avoids recent no-repeat zones: no Financials multiplier retry, "
                "no Financials target-width retry, no SPY-relative cap retry, no "
                "broad add-on cap change, no sector cap, no universe expansion, "
                "and no event/LLM threshold changes."
            ),
        },
        "parameters": {
            "single_causal_variable": (
                "first add-on max position cap for positions whose entry sizing "
                "carried financials_sector_leader_risk_multiplier_applied"
            ),
            "baseline_addon_cap_pct": bt.DEFAULT_CONFIG["ADDON_MAX_POSITION_PCT"],
            "tested_variants": VARIANTS,
            "best_variant": best_name,
            "financials_leader_key": FINANCIALS_LEADER_KEY,
            "locked_variables": [
                "universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "initial position sizing",
                "Financials risk multipliers",
                "all exits and target widths",
                "follow-through thresholds",
                "add-on fraction",
                "second add-on",
                "MAX_POSITIONS",
                "MAX_PORTFOLIO_HEAT",
                "LLM/news replay",
                "event sleeves",
            ],
        },
        "date_range": {
            label: f"{window['start']} -> {window['end']}"
            for label, window in WINDOWS.items()
        },
        "snapshots": {label: window["snapshot"] for label, window in WINDOWS.items()},
        "market_regime_summary": {
            label: window["state_note"] for label, window in WINDOWS.items()
        },
        "before_metrics": {
            label: row["metrics"] for label, row in baselines.items()
        },
        "after_metrics": {
            label: row["after"] for label, row in best["rows"].items()
        },
        "delta_metrics": {
            "by_window": {label: row["delta"] for label, row in best["rows"].items()},
            "aggregate": best["aggregate"],
        },
        "variants": variants,
        "best_variant": best_name,
        "gate4": {
            "passed": accepted,
            "basis": (
                "Requires Gate 4 materiality plus EV improvement in at least "
                "two fixed windows and zero EV-regressed windows."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": True,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, add a shared Financials-leader add-on cap helper "
                "to production_parity/backtester plus a parity test before live "
                "orders change."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "blocker_relation": (
                "This avoids the current LLM soft-ranking data limit by testing "
                "a deterministic lifecycle allocation lever."
            ),
        },
        "rejection_reason": None if accepted else (
            "Financials leader first-add-on cap did not clear the three-window "
            "Gate 4 materiality and stability standard."
        ),
        "next_retry_requires": [] if accepted else [
            "Do not retry nearby Financials leader add-on cap levels without forward evidence.",
            "A valid retry needs candidate-level replacement value or event/news context explaining which Financials leaders deserve more post-entry capacity.",
        ],
        "risk_of_change": (
            "May over-concentrate Financials winners after short-term strength "
            "and amplify reversals in GS/JPM/COIN-like crowded legs."
        ),
        "why_not_other_attractive_points": {
            "LLM_soft_ranking": "Insufficient closed attribution sample.",
            "event_bundle_promotion": "Needs closed forward paper outcomes.",
            "universe_expansion": "Recent broad and narrow expansions failed.",
            "Financials_multiplier_or_initial_cap": "Recent mechanism notes explicitly ban nearby retries.",
            "target_width": "Financials leader target-width sweeps were rejected.",
        },
        "related_files": [
            "quant/experiments/exp_20260505_017_financials_leader_addon_cap.py",
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "docs/experiment_log.jsonl",
            "docs/alpha-optimization-playbook.md",
        ],
    }


def _artifact(payload: dict[str, Any]) -> str:
    agg = payload["delta_metrics"]["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} Financials Leader Add-on Cap",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Gate 4",
        "",
        f"- passed: `{payload['gate4']['passed']}`",
        f"- best_variant: `{payload['best_variant']}`",
        f"- EV delta sum: `{agg['expected_value_score_delta_sum']:+.4f}` "
        f"({agg['expected_value_score_delta_pct']:+.2%})",
        f"- PnL delta sum: `${agg['total_pnl_delta_sum']:+,.2f}` "
        f"({agg['total_pnl_delta_pct']:+.2%})",
        f"- EV windows improved/regressed: `{agg['ev_windows_improved']}` / `{agg['ev_windows_regressed']}`",
        f"- Financials leader add-on events: `{agg['financials_leader_addon_event_count_sum']}`",
        "",
        "## Three-window Deltas",
        "",
        "| Window | EV delta | PnL delta | SharpeD delta | DD delta | WR delta | Trades delta | Add-on exec delta | Events |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, row in payload["variants"][payload["best_variant"]]["rows"].items():
        delta = row["delta"]
        lines.append(
            f"| `{label}` | {delta['expected_value_score']:+.4f} | "
            f"{delta['total_pnl']:+.2f} | {delta['sharpe_daily']:+.2f} | "
            f"{delta['max_drawdown_pct']:+.4f} | {delta['win_rate']:+.4f} | "
            f"{delta['trade_count']:+d} | {delta['addon_executed']:+d} | "
            f"{row['financials_leader_addon_event_count']} |"
        )
    lines.extend([
        "",
        "## Production Parity",
        "",
        (
            "Replay-only. A positive result requires a shared Financials-leader "
            "add-on cap helper and parity test before production orders change."
        ),
        "",
    ])
    return "\n".join(lines)


def _update_playbook(payload: dict[str, Any]) -> None:
    text = PLAYBOOK.read_text(encoding="utf-8")
    if f"`{EXPERIMENT_ID}`" in text:
        return
    aggregate = payload["delta_metrics"]["aggregate"]
    note = f"""

### 2026-05-05 mechanism update: Financials leader add-on cap

Status: {payload['decision']}.

Core conclusion: `{EXPERIMENT_ID}` tested whether accepted `trend_long`
Financials sector leaders should receive a higher first follow-through add-on
cap after passing the existing day-2 checkpoint. This was a lifecycle
allocation test, not a Financials multiplier, initial-cap, target-width,
universe, LLM, or event-threshold retry.

Evidence: best variant `{payload['best_variant']}` moved aggregate EV by
`{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)
and aggregate PnL by `${aggregate['total_pnl_delta_sum']}`
(`{aggregate['total_pnl_delta_pct']}`). Window EV improved/regressed counts
were `{aggregate['ev_windows_improved']}` / `{aggregate['ev_windows_regressed']}`.

Do not repeat: nearby Financials leader add-on cap levels without forward
evidence or a richer post-entry quality discriminator.
"""
    with PLAYBOOK.open("a", encoding="utf-8") as handle:
        handle.write(note)


def main() -> int:
    baselines = _run_baselines()
    variants: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for name, variant in VARIANTS.items():
        variants[name] = _run_variant(name, variant, baselines)

    payload = _make_payload(baselines, variants)
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(TICKET_JSON, {
        "experiment_id": EXPERIMENT_ID,
        "title": "Financials leader add-on cap",
        "status": payload["decision"],
        "decision": payload["decision"],
        "summary": payload["rejection_reason"] or "Gate 4 passed; promote through shared follow-through policy.",
        "best_variant": payload["best_variant"],
        "delta_metrics": payload["delta_metrics"]["aggregate"],
        "related_log": str(LOG_JSON.relative_to(REPO_ROOT)),
    })
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact(payload), encoding="utf-8")
    _append_jsonl(EXPERIMENT_LOG_JSONL, payload)
    _update_playbook(payload)

    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "decision": payload["decision"],
        "best_variant": payload["best_variant"],
        "gate4": payload["gate4"],
        "aggregate": payload["delta_metrics"]["aggregate"],
        "out_json": str(OUT_JSON.relative_to(REPO_ROOT)),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
