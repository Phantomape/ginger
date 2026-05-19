"""exp-20260507-009 mid-dispersion trend fragility guard.

Alpha search. The accepted mid-sector-dispersion trend allocation boost improves
EV across the fixed windows, but old_thin drawdown used nearly the full 1pp
guardrail. This replay tests one causal variable: whether that positive
allocation boost should avoid stacking onto signals that the shared sizing
policy has already marked fragile with risk haircuts.

No production strategy code is changed by this script. If a variant passes Gate
4, promotion must move the same guard into shared portfolio sizing and add a
parity-focused test before live behavior changes.
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
import portfolio_engine as pe  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260507-009"
STEM = "mid_dispersion_fragility_guard"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

MID_DISPERSION_KEY = "trend_mid_sector_dispersion_risk_multiplier_applied"
CUSTOM_GUARD_KEY = "mid_dispersion_fragility_guard_applied"

TECH_FRAGILITY_KEYS = (
    "trend_tech_tight_gap_risk_multiplier_applied",
    "trend_tech_gap_risk_multiplier_applied",
    "trend_tech_near_high_risk_multiplier_applied",
    "trend_tech_dte_risk_multiplier_applied",
)
ALL_FRAGILITY_KEYS = (
    "tqs_risk_multiplier_applied",
    "trend_industrials_risk_multiplier_applied",
    "trend_tech_tight_gap_risk_multiplier_applied",
    "trend_tech_gap_risk_multiplier_applied",
    "trend_tech_near_high_risk_multiplier_applied",
    "trend_tech_dte_risk_multiplier_applied",
    "trend_healthcare_dte_risk_multiplier_applied",
    "trend_consumer_near_high_dte_risk_multiplier_applied",
)

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
                "state_note": "rotation-heavy bull where strategy profits but can lag indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)

VARIANTS = OrderedDict(
    [
        (
            "no_tech_fragility_stack",
            {
                "mode": "tech_any",
                "description": (
                    "Remove the accepted mid-dispersion trend boost only from "
                    "Technology trend signals already carrying a tech fragility haircut."
                ),
            },
        ),
        (
            "no_multi_fragility_stack",
            {
                "mode": "multi_any",
                "description": (
                    "Remove the boost only when two or more accepted fragility haircuts "
                    "are already present."
                ),
            },
        ),
        (
            "no_any_fragility_stack",
            {
                "mode": "any",
                "description": (
                    "Remove the boost from any mid-dispersion trend signal already "
                    "carrying a sub-1.0 risk haircut."
                ),
            },
        ),
    ]
)

_state: dict[str, Any] = {
    "mid_dispersion_trend_signals_seen": 0,
    "fragile_mid_dispersion_signals_seen": 0,
    "signals_guarded": 0,
    "guard_sizing_days": set(),
}


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


def _reset_state() -> None:
    for key in _state:
        _state[key] = set() if key.endswith("_days") else 0


def _haircut_keys(sizing: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    out = []
    for key in keys:
        value = sizing.get(key, 1.0)
        if isinstance(value, (int, float)) and value < 1.0:
            out.append(key)
    return out


def _should_guard(sig: dict[str, Any], sizing: dict[str, Any], mode: str) -> tuple[bool, list[str]]:
    all_haircuts = _haircut_keys(sizing, ALL_FRAGILITY_KEYS)
    tech_haircuts = _haircut_keys(sizing, TECH_FRAGILITY_KEYS)
    if mode == "tech_any":
        return bool(sig.get("sector") == "Technology" and tech_haircuts), tech_haircuts
    if mode == "multi_any":
        return len(all_haircuts) >= 2, all_haircuts
    if mode == "any":
        return bool(all_haircuts), all_haircuts
    return False, []


def _patch_size_signals(variant: dict[str, str] | None):
    original = pe.size_signals

    def patched(signals, portfolio_value, risk_pct=None):
        sized = original(signals, portfolio_value, risk_pct=risk_pct)
        if variant is None:
            return sized

        mode = variant["mode"]
        for sig in sized:
            if sig.get("strategy") != "trend_long":
                continue
            sizing = sig.get("sizing") or {}
            mid_mult = sizing.get(MID_DISPERSION_KEY, 1.0)
            if not isinstance(mid_mult, (int, float)) or mid_mult <= 1.0:
                continue
            _state["mid_dispersion_trend_signals_seen"] += 1

            should_guard, fragility_keys = _should_guard(sig, sizing, mode)
            if not should_guard:
                continue
            _state["fragile_mid_dispersion_signals_seen"] += 1

            entry = sizing.get("entry_price") or sig.get("entry_price")
            stop = sizing.get("stop_price") or sig.get("stop_price")
            current_risk_pct = sizing.get("risk_pct")
            if not entry or not stop or current_risk_pct is None:
                continue
            guarded_risk_pct = float(current_risk_pct) / float(mid_mult)
            if guarded_risk_pct <= 0:
                continue

            new_sizing = pe.compute_position_size(
                portfolio_value,
                float(entry),
                float(stop),
                risk_pct=guarded_risk_pct,
                max_position_pct=sizing.get(
                    "max_position_pct_applied",
                    pe.MAX_POSITION_PCT,
                ),
            )
            if not new_sizing:
                continue

            preserved = dict(sizing)
            preserved.update(new_sizing)
            preserved["base_risk_pct"] = sizing.get("base_risk_pct")
            preserved["max_position_pct_applied"] = sizing.get(
                "max_position_pct_applied",
                pe.MAX_POSITION_PCT,
            )
            preserved[MID_DISPERSION_KEY] = 1.0
            preserved[CUSTOM_GUARD_KEY] = _round(1.0 / float(mid_mult), 6)
            preserved["fragility_guard_mode"] = mode
            preserved["fragility_guard_removed_multiplier"] = mid_mult
            preserved["fragility_guard_keys"] = fragility_keys
            preserved["fragility_guard_original_risk_pct"] = current_risk_pct
            preserved["fragility_guard_original_shares"] = sizing.get("shares_to_buy")
            sig["sizing"] = preserved
            _state["signals_guarded"] += 1
        return sized

    pe.size_signals = patched
    return original


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    guarded_trades = 0
    guarded_pnl = 0.0
    guarded_wins = 0
    for trade in result.get("trades") or []:
        multipliers = trade.get("sizing_multipliers") or {}
        if CUSTOM_GUARD_KEY not in multipliers:
            continue
        guarded_trades += 1
        pnl = float(trade.get("pnl") or 0.0)
        guarded_pnl += pnl
        guarded_wins += int(pnl > 0)

    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "sharpe_daily": _round(result.get("sharpe_daily"), 2),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "total_return_pct": _round(
            benchmarks.get("strategy_total_return_pct"),
            4,
        ),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": result.get("total_trades"),
        "survival_rate": _round(result.get("survival_rate"), 4),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "tail_loss_share": _round(result.get("tail_loss_share"), 4),
        "mid_dispersion_trend_signals_seen": _state[
            "mid_dispersion_trend_signals_seen"
        ],
        "fragile_mid_dispersion_signals_seen": _state[
            "fragile_mid_dispersion_signals_seen"
        ],
        "signals_guarded": _state["signals_guarded"],
        "guarded_trade_count": guarded_trades,
        "guarded_trade_pnl": _round(guarded_pnl, 2),
        "guarded_trade_win_rate": _round(
            guarded_wins / guarded_trades if guarded_trades else 0.0,
            4,
        ),
    }


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, before_value in before.items():
        after_value = after.get(key)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            out[key] = _round(after_value - before_value, 6)
        else:
            out[key] = None
    return out


def _run_window(
    universe: list[str],
    cfg: dict[str, str],
    variant: dict[str, str] | None,
) -> dict[str, Any]:
    _reset_state()
    original_size = _patch_size_signals(variant)
    original_keys = bt.SIZING_MULTIPLIER_KEYS
    if CUSTOM_GUARD_KEY not in original_keys:
        bt.SIZING_MULTIPLIER_KEYS = tuple(list(original_keys) + [CUSTOM_GUARD_KEY])
    try:
        result = BacktestEngine(
            universe=universe,
            start=cfg["start"],
            end=cfg["end"],
            config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
            replay_llm=False,
            replay_news=False,
            data_dir=str(REPO_ROOT / "data"),
            ohlcv_snapshot_path=str(REPO_ROOT / cfg["snapshot"]),
            include_pilot_sleeve=False,
        ).run()
    finally:
        pe.size_signals = original_size
        bt.SIZING_MULTIPLIER_KEYS = original_keys

    if "error" in result:
        raise RuntimeError(result["error"])
    return {
        "metrics": _metrics(result),
        "guarded_trades": [
            {
                "ticker": trade.get("ticker"),
                "strategy": trade.get("strategy"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "sector": trade.get("sector"),
                "pnl": trade.get("pnl"),
                "sizing_multipliers": trade.get("sizing_multipliers"),
            }
            for trade in (result.get("trades") or [])
            if CUSTOM_GUARD_KEY in ((trade.get("sizing_multipliers") or {}).keys())
        ][:40],
    }


def _aggregate(
    before: OrderedDict[str, dict[str, Any]],
    after: OrderedDict[str, dict[str, Any]],
) -> dict[str, Any]:
    baseline_ev = sum(float(row["metrics"].get("expected_value_score") or 0.0) for row in before.values())
    after_ev = sum(float(row["metrics"].get("expected_value_score") or 0.0) for row in after.values())
    baseline_pnl = sum(float(row["metrics"].get("total_pnl") or 0.0) for row in before.values())
    after_pnl = sum(float(row["metrics"].get("total_pnl") or 0.0) for row in after.values())
    ev_deltas = {
        label: _round(
            (after[label]["metrics"].get("expected_value_score") or 0.0)
            - (before[label]["metrics"].get("expected_value_score") or 0.0),
            6,
        )
        for label in before
    }
    pnl_deltas = {
        label: _round(
            (after[label]["metrics"].get("total_pnl") or 0.0)
            - (before[label]["metrics"].get("total_pnl") or 0.0),
            2,
        )
        for label in before
    }
    sharpe_deltas = {
        label: _round(
            (after[label]["metrics"].get("sharpe_daily") or 0.0)
            - (before[label]["metrics"].get("sharpe_daily") or 0.0),
            6,
        )
        for label in before
    }
    drawdown_deltas = {
        label: _round(
            (after[label]["metrics"].get("max_drawdown_pct") or 0.0)
            - (before[label]["metrics"].get("max_drawdown_pct") or 0.0),
            6,
        )
        for label in before
    }
    win_rate_deltas = {
        label: _round(
            (after[label]["metrics"].get("win_rate") or 0.0)
            - (before[label]["metrics"].get("win_rate") or 0.0),
            6,
        )
        for label in before
    }
    return {
        "baseline_expected_value_score_sum": _round(baseline_ev, 6),
        "after_expected_value_score_sum": _round(after_ev, 6),
        "expected_value_score_delta_sum": _round(after_ev - baseline_ev, 6),
        "expected_value_score_delta_pct": _round(
            (after_ev - baseline_ev) / abs(baseline_ev) if baseline_ev else None,
            6,
        ),
        "baseline_total_pnl_sum": _round(baseline_pnl, 2),
        "after_total_pnl_sum": _round(after_pnl, 2),
        "total_pnl_delta_sum": _round(after_pnl - baseline_pnl, 2),
        "total_pnl_delta_pct": _round(
            (after_pnl - baseline_pnl) / abs(baseline_pnl) if baseline_pnl else None,
            6,
        ),
        "windows_ev_improved": sum(1 for value in ev_deltas.values() if value > 0),
        "windows_ev_regressed": sum(1 for value in ev_deltas.values() if value < 0),
        "windows_pnl_improved": sum(1 for value in pnl_deltas.values() if value > 0),
        "windows_pnl_regressed": sum(1 for value in pnl_deltas.values() if value < 0),
        "by_window_ev_delta": ev_deltas,
        "by_window_pnl_delta": pnl_deltas,
        "by_window_sharpe_daily_delta": sharpe_deltas,
        "by_window_max_drawdown_delta": drawdown_deltas,
        "by_window_win_rate_delta": win_rate_deltas,
        "trade_count_delta_sum": sum(
            int(after[label]["metrics"].get("trade_count") or 0)
            - int(before[label]["metrics"].get("trade_count") or 0)
            for label in before
        ),
        "max_drawdown_worsening_max": max(drawdown_deltas.values()),
        "max_drawdown_improvement_min": min(drawdown_deltas.values()),
        "best_sharpe_daily_delta": max(sharpe_deltas.values()),
        "min_win_rate_delta": min(win_rate_deltas.values()),
        "signals_guarded_sum": sum(int(row["metrics"].get("signals_guarded") or 0) for row in after.values()),
        "guarded_trade_count_sum": sum(int(row["metrics"].get("guarded_trade_count") or 0) for row in after.values()),
        "guarded_trade_pnl_sum": _round(
            sum(float(row["metrics"].get("guarded_trade_pnl") or 0.0) for row in after.values()),
            2,
        ),
    }


def _passes_gate4(aggregate: dict[str, Any]) -> bool:
    ev_delta_pct = aggregate.get("expected_value_score_delta_pct") or 0.0
    pnl_delta_pct = aggregate.get("total_pnl_delta_pct") or 0.0
    material = (
        ev_delta_pct > 0.10
        or pnl_delta_pct > 0.05
        or (aggregate.get("best_sharpe_daily_delta") or 0.0) > 0.10
        or (aggregate.get("max_drawdown_improvement_min") or 0.0) < -0.01
        or (
            aggregate.get("trade_count_delta_sum", 0) > 0
            and (aggregate.get("min_win_rate_delta") or 0.0) >= 0
        )
    )
    stability = (
        aggregate.get("windows_ev_improved", 0) >= 2
        and aggregate.get("windows_ev_regressed", 0) == 0
    )
    return bool(material and stability)


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID}: Mid-Dispersion Fragility Guard",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Variant Summary",
        "",
        "| Variant | Gate 4 | EV Delta Sum | PnL Delta Sum | EV Windows + / - | Guarded Signals | Guarded Trades |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, row in payload["variant_results"].items():
        aggregate = row["aggregate"]
        lines.append(
            "| {name} | {gate} | {ev_delta} | {pnl_delta} | {ev_plus}/{ev_minus} | {guarded} | {trades} |".format(
                name=name,
                gate=row["gate4_pass"],
                ev_delta=aggregate["expected_value_score_delta_sum"],
                pnl_delta=aggregate["total_pnl_delta_sum"],
                ev_plus=aggregate["windows_ev_improved"],
                ev_minus=aggregate["windows_ev_regressed"],
                guarded=aggregate["signals_guarded_sum"],
                trades=aggregate["guarded_trade_count_sum"],
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            payload["interpretation"],
            "",
            "## Production Impact",
            "",
            "- No production code was changed by this replay.",
            "- If accepted later, the guard must live in shared portfolio sizing and be exposed to both run.py and backtester.py.",
        ]
    )
    return "\n".join(lines) + "\n"


def _write_outputs(payload: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)

    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    LOG_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    TICKET_JSON.write_text(json.dumps(payload["ticket"], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    ARTIFACT_MD.write_text(_markdown(payload), encoding="utf-8")
    with EXPERIMENT_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload["experiment_log_entry"], ensure_ascii=False) + "\n")


def main() -> int:
    universe = sorted(get_universe())
    before: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for label, cfg in WINDOWS.items():
        before[label] = _run_window(universe, cfg, None)

    variant_results: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for name, variant in VARIANTS.items():
        by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
        for label, cfg in WINDOWS.items():
            row = _run_window(universe, cfg, variant)
            row["delta"] = _delta(row["metrics"], before[label]["metrics"])
            by_window[label] = row
        aggregate = _aggregate(before, by_window)
        variant_results[name] = {
            "parameters": variant,
            "by_window": by_window,
            "aggregate": aggregate,
            "gate4_pass": _passes_gate4(aggregate),
        }

    passing = [name for name, row in variant_results.items() if row["gate4_pass"]]
    ranking_pool = passing or list(variant_results)
    best_name = max(
        ranking_pool,
        key=lambda name: (
            variant_results[name]["aggregate"]["expected_value_score_delta_sum"],
            variant_results[name]["aggregate"]["total_pnl_delta_sum"],
        ),
    )
    best = variant_results[best_name]
    any_pass = bool(passing)
    decision = "accepted_requires_shared_policy_promotion" if any_pass else "rejected"
    if any_pass:
        interpretation = (
            f"`{best_name}` passed Gate 4 as a drawdown-aware refinement of the "
            "accepted mid-dispersion trend allocation boost. No production behavior "
            "changed in this script; promotion requires shared sizing code and tests."
        )
    else:
        interpretation = (
            f"Best variant `{best_name}` did not improve the north-star EV enough "
            "or across enough windows to justify complicating the accepted "
            "mid-dispersion trend allocation rule."
        )

    timestamp = datetime.now(timezone.utc).isoformat()
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "change_type": "capital_allocation_mid_dispersion_fragility_guard",
        "alpha_hypothesis_category": "allocation_drawdown_discriminator",
        "hypothesis": (
            "The accepted mid-sector-dispersion trend boost should not necessarily "
            "stack onto signals that existing shared sizing rules already mark as "
            "fragile. Removing only the positive boost from those fragile pockets may "
            "preserve the accepted allocation alpha while reducing old_thin drawdown."
        ),
        "history_guardrails": {
            "not_nearby_multiplier_retry": True,
            "not_compound_skip_retry": True,
            "not_universe_expansion": True,
            "why_not_simple_repeat": (
                "This does not retune the accepted 1.25x multiplier, does not ban or "
                "skip fragile trades, and does not repeat the rejected compound severe "
                "haircut skip. It only tests whether the positive mid-dispersion boost "
                "should avoid stacking onto pre-existing haircut sleeves."
            ),
            "mechanism_insight_conflict": "No direct conflict; exp-20260506-032 explicitly requested a new drawdown discriminator before retrying this family.",
        },
        "parameters": {
            "single_causal_variable": "fragility-aware stacking guard for accepted mid-dispersion trend boost",
            "accepted_rule_under_test": MID_DISPERSION_KEY,
            "custom_guard_key": CUSTOM_GUARD_KEY,
            "tested_variants": VARIANTS,
            "locked_variables": [
                "universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "risk multiplier values",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "MAX_PER_SECTOR",
                "gap cancels",
                "add-ons",
                "all exits",
                "LLM/news replay",
                "earnings strategy",
            ],
            "windows": WINDOWS,
        },
        "date_range": {label: f"{cfg['start']} -> {cfg['end']}" for label, cfg in WINDOWS.items()},
        "snapshots": {label: cfg["snapshot"] for label, cfg in WINDOWS.items()},
        "market_regime_summary": {label: cfg["state_note"] for label, cfg in WINDOWS.items()},
        "before_metrics": before,
        "variant_results": variant_results,
        "best_variant": best_name,
        "best_variant_gate4": best["gate4_pass"],
        "decision": decision,
        "interpretation": interpretation,
        "rejection_reason": None if any_pass else interpretation,
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": "LLM soft-ranking remains sparse, so this run tested deterministic allocation instead.",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, implement the same guard in shared portfolio_engine sizing "
                "and add parity tests before production behavior changes."
            ),
        },
        "ticket": {
            "experiment_id": EXPERIMENT_ID,
            "title": "Mid-dispersion fragility guard",
            "decision": decision,
            "best_variant": best_name,
            "next_action": (
                "Promote through shared policy plus parity tests."
                if any_pass
                else "Do not promote; leave accepted allocation unchanged."
            ),
        },
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "quant/experiments/exp_20260507_009_mid_dispersion_fragility_guard.py",
            "docs/experiment_log.jsonl",
        ],
    }
    payload["experiment_log_entry"] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": payload["lane"],
        "change_type": payload["change_type"],
        "alpha_hypothesis_category": payload["alpha_hypothesis_category"],
        "hypothesis": payload["hypothesis"],
        "parameters": payload["parameters"],
        "date_range": payload["date_range"],
        "market_regime_summary": payload["market_regime_summary"],
        "before_metrics": {label: row["metrics"] for label, row in before.items()},
        "after_metrics": {
            name: {label: row["metrics"] for label, row in variant["by_window"].items()}
            for name, variant in variant_results.items()
        },
        "delta_metrics": {name: row["aggregate"] for name, row in variant_results.items()},
        "expected_value_score_delta": best["aggregate"]["expected_value_score_delta_sum"],
        "best_variant": best_name,
        "best_variant_gate4": best["gate4_pass"],
        "decision": decision,
        "rejection_reason": payload["rejection_reason"],
        "production_impact": payload["production_impact"],
        "llm_metrics": payload["llm_metrics"],
        "history_guardrails": payload["history_guardrails"],
        "next_retry_requires": [
            "Do not retry nearby mid-dispersion fragility stacking guards on the same accepted rule if this fails.",
            "A valid retry needs new forward evidence or a materially different discriminator, not another haircut-count variant.",
        ],
        "related_files": payload["related_files"],
        "status": "needs_promotion" if any_pass else "rejected",
    }

    _write_outputs(payload)
    print(json.dumps(payload["experiment_log_entry"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
