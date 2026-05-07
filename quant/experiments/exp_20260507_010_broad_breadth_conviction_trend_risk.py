"""exp-20260507-010 broad-breadth conviction trend risk.

Alpha search. exp-20260507-007 showed that broad 200-day universe breadth
can lift trend_long PnL, but the simple broad-breadth multiplier damaged
risk quality. This replay tests one refinement: apply the broad-breadth
allocation only when the existing shared sizing stack already expresses high
conviction and no accepted haircut is present.

No production strategy code is changed by this script. If a variant passes
Gate 4, promotion must move the same rule into shared risk/portfolio policy
and add parity tests before live behavior changes.
"""

from __future__ import annotations

import inspect
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
import risk_engine as re  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260507-010"
STEM = "broad_breadth_conviction_trend_risk"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

BROAD_BREADTH_200_MIN = 0.75
POSITIVE_MULTIPLIER_MIN_COUNT = 3
CUSTOM_MULTIPLIER_KEY = "broad_breadth_conviction_trend_risk_multiplier_applied"

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
        ("conviction_breadth_trend_1_50x", {"risk_multiplier": 1.50}),
        ("conviction_breadth_trend_2_00x", {"risk_multiplier": 2.00}),
    ]
)

_state: dict[str, Any] = {
    "trend_signals_seen": 0,
    "broad_breadth_trend_signals_seen": 0,
    "conviction_qualified_signals_seen": 0,
    "signals_resized": 0,
    "broad_breadth_sizing_days": set(),
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


def _universe_breadth_above_200ma(features_dict: dict[str, dict[str, Any]]) -> float | None:
    seen = 0
    above = 0
    for ticker, features in (features_dict or {}).items():
        if ticker in {"SPY", "QQQ", "IWM"}:
            continue
        if not features or features.get("above_200ma") is None:
            continue
        seen += 1
        above += int(bool(features.get("above_200ma")))
    return above / seen if seen else None


def _patch_enrich_signals(variant: dict[str, float] | None):
    original = re.enrich_signals

    def patched(signals, features_dict, atr_target_mult=None):
        enriched = original(signals, features_dict, atr_target_mult=atr_target_mult)
        if variant is None:
            return enriched
        breadth = _universe_breadth_above_200ma(features_dict)
        broad = isinstance(breadth, (int, float)) and breadth >= BROAD_BREADTH_200_MIN
        for sig in enriched:
            sig["universe_breadth_above_200ma"] = _round(breadth, 6)
            sig["broad_universe_breadth_200"] = broad
            sig["broad_universe_breadth_200_min"] = BROAD_BREADTH_200_MIN
        return enriched

    re.enrich_signals = patched
    return original


def _active_multiplier_counts(sizing: dict[str, Any]) -> tuple[int, int]:
    positive = 0
    haircut = 0
    for key, value in sizing.items():
        if not key.endswith("_risk_multiplier_applied"):
            continue
        if key == CUSTOM_MULTIPLIER_KEY:
            continue
        if not isinstance(value, (int, float)):
            continue
        if value > 1.0:
            positive += 1
        elif value < 1.0:
            haircut += 1
    return positive, haircut


def _patch_size_signals(variant: dict[str, float] | None):
    original = pe.size_signals

    def patched(signals, portfolio_value, risk_pct=None):
        sized = original(signals, portfolio_value, risk_pct=risk_pct)
        if variant is None:
            return sized

        today_key = ""
        for frame_info in inspect.stack():
            today = frame_info.frame.f_locals.get("today")
            if today is not None:
                today_key = str(getattr(today, "date", lambda: today)())
                break

        multiplier = variant["risk_multiplier"]
        for sig in sized:
            if sig.get("strategy") != "trend_long":
                continue
            _state["trend_signals_seen"] += 1
            if sig.get("broad_universe_breadth_200") is not True:
                continue
            _state["broad_breadth_trend_signals_seen"] += 1

            sizing = sig.get("sizing") or {}
            positive_count, haircut_count = _active_multiplier_counts(sizing)
            sig["conviction_positive_multiplier_count"] = positive_count
            sig["conviction_haircut_multiplier_count"] = haircut_count
            if positive_count < POSITIVE_MULTIPLIER_MIN_COUNT or haircut_count:
                continue
            _state["conviction_qualified_signals_seen"] += 1

            entry = sizing.get("entry_price") or sig.get("entry_price")
            stop = sizing.get("stop_price") or sig.get("stop_price")
            original_risk_pct = sizing.get("risk_pct")
            if not sizing or not entry or not stop or original_risk_pct is None:
                continue
            if float(original_risk_pct) <= 0:
                continue

            new_sizing = pe.compute_position_size(
                portfolio_value,
                float(entry),
                float(stop),
                risk_pct=float(original_risk_pct) * multiplier,
                max_position_pct=sizing.get("max_position_pct_applied", pe.MAX_POSITION_PCT),
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
            preserved[CUSTOM_MULTIPLIER_KEY] = multiplier
            preserved["broad_breadth_conviction_original_risk_pct"] = original_risk_pct
            preserved["broad_breadth_conviction_original_shares"] = sizing.get("shares_to_buy")
            preserved["conviction_positive_multiplier_count"] = positive_count
            preserved["conviction_haircut_multiplier_count"] = haircut_count
            preserved["universe_breadth_above_200ma"] = sig.get("universe_breadth_above_200ma")
            preserved["broad_universe_breadth_200_min"] = BROAD_BREADTH_200_MIN
            sig["sizing"] = preserved
            _state["signals_resized"] += 1
            if today_key:
                _state["broad_breadth_sizing_days"].add(today_key)
        return sized

    pe.size_signals = patched
    return original


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    touched_trades = 0
    touched_pnl = 0.0
    touched_wins = 0
    for trade in result.get("trades") or []:
        multipliers = trade.get("sizing_multipliers") or {}
        if CUSTOM_MULTIPLIER_KEY not in multipliers:
            continue
        touched_trades += 1
        pnl = float(trade.get("pnl") or 0.0)
        touched_pnl += pnl
        touched_wins += int(pnl > 0)

    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "sharpe_daily": _round(result.get("sharpe_daily"), 2),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "total_return_pct": _round(benchmarks.get("strategy_total_return_pct"), 4),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": result.get("total_trades"),
        "survival_rate": _round(result.get("survival_rate"), 4),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "tail_loss_share": _round(result.get("tail_loss_share"), 4),
        "trend_signals_seen": _state["trend_signals_seen"],
        "broad_breadth_trend_signals_seen": _state["broad_breadth_trend_signals_seen"],
        "conviction_qualified_signals_seen": _state["conviction_qualified_signals_seen"],
        "signals_resized": _state["signals_resized"],
        "broad_breadth_sizing_days": len(_state["broad_breadth_sizing_days"]),
        "touched_trade_count": touched_trades,
        "touched_trade_pnl": _round(touched_pnl, 2),
        "touched_trade_win_rate": _round(
            touched_wins / touched_trades if touched_trades else 0.0,
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
    variant: dict[str, float] | None,
) -> dict[str, Any]:
    _reset_state()
    original_enrich = _patch_enrich_signals(variant)
    original_size = _patch_size_signals(variant)
    original_keys = bt.SIZING_MULTIPLIER_KEYS
    if CUSTOM_MULTIPLIER_KEY not in original_keys:
        bt.SIZING_MULTIPLIER_KEYS = tuple(list(original_keys) + [CUSTOM_MULTIPLIER_KEY])
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
        re.enrich_signals = original_enrich
        pe.size_signals = original_size
        bt.SIZING_MULTIPLIER_KEYS = original_keys

    if "error" in result:
        raise RuntimeError(result["error"])
    return {
        "metrics": _metrics(result),
        "touched_trades": [
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
            if CUSTOM_MULTIPLIER_KEY in ((trade.get("sizing_multipliers") or {}).keys())
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
        "min_sharpe_daily_delta": min(sharpe_deltas.values()),
        "min_win_rate_delta": min(win_rate_deltas.values()),
        "signals_resized_sum": sum(int(row["metrics"].get("signals_resized") or 0) for row in after.values()),
        "touched_trade_count_sum": sum(int(row["metrics"].get("touched_trade_count") or 0) for row in after.values()),
        "touched_trade_pnl_sum": _round(
            sum(float(row["metrics"].get("touched_trade_pnl") or 0.0) for row in after.values()),
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
    risk_ok = (
        (aggregate.get("max_drawdown_worsening_max") or 0.0) <= 0.01
        and (aggregate.get("min_sharpe_daily_delta") or 0.0) >= 0.0
    )
    return bool(material and stability and risk_ok)


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID}: Broad-Breadth Conviction Trend Risk",
        "",
        f"Decision: `{payload['decision']}`",
        f"Best variant: `{payload['best_variant']}`",
        "",
        "## Variant Summary",
        "",
        "| Variant | Gate 4 | EV Delta Sum | PnL Delta Sum | EV Windows + / - | Resized Signals | Touched Trades | DD Max Delta | Min Sharpe Delta |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, row in payload["variant_results"].items():
        aggregate = row["aggregate"]
        lines.append(
            "| {name} | {gate} | {ev_delta} | {pnl_delta} | {ev_plus}/{ev_minus} | {resized} | {trades} | {dd} | {sharpe} |".format(
                name=name,
                gate=row["gate4_pass"],
                ev_delta=aggregate["expected_value_score_delta_sum"],
                pnl_delta=aggregate["total_pnl_delta_sum"],
                ev_plus=aggregate["windows_ev_improved"],
                ev_minus=aggregate["windows_ev_regressed"],
                resized=aggregate["signals_resized_sum"],
                trades=aggregate["touched_trade_count_sum"],
                dd=aggregate["max_drawdown_worsening_max"],
                sharpe=aggregate["min_sharpe_daily_delta"],
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
            "- If accepted later, the breadth field and conviction rule must live in shared policy consumed by run.py and backtester.py.",
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
    accepted = bool(passing)
    decision = "accepted_requires_shared_policy_promotion" if accepted else "rejected"
    if accepted:
        interpretation = (
            f"`{best_name}` passed Gate 4 as a cleaner broad-breadth allocation "
            "rule. This runner did not alter production; promotion requires shared "
            "risk/portfolio policy plus parity tests."
        )
    else:
        interpretation = (
            f"Best variant `{best_name}` did not pass Gate 4. The existing accepted "
            "stack should remain unchanged; do not retry nearby broad-breadth "
            "conviction multipliers without new forward evidence or a materially "
            "different discriminator."
        )

    timestamp = datetime.now(timezone.utc).isoformat()
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "change_type": "capital_allocation_broad_breadth_conviction_trend_risk",
        "mechanism_family": "market_structure_breadth_allocation",
        "alpha_hypothesis_category": "allocation",
        "hypothesis": (
            "When broad universe participation is high, trend_long trades should "
            "receive extra risk only if the existing shared sizing stack already "
            "shows high conviction: at least three positive accepted multipliers "
            "and no accepted risk haircut."
        ),
        "history_guardrails": {
            "similar_prior_results": {
                "exp-20260507-007": (
                    "Rejected simple broad-breadth trend risk: PnL rose but EV "
                    "materiality, Sharpe, and drawdown quality failed."
                ),
                "exp-20260507-009": (
                    "Rejected haircut-count guard on accepted mid-dispersion trend "
                    "boost; this run tests a positive-conviction qualifier for a "
                    "different, unaccepted broad-breadth allocation idea."
                ),
                "exp-20260505-012": (
                    "Rejected compound severe-haircut skip; this run does not skip "
                    "or zero-size candidates and does not stack on haircuts."
                ),
            },
            "why_not_simple_repeat": (
                "This is not another broad-breadth threshold or multiplier-only "
                "retry. The causal variable is the conviction qualifier: broad "
                "breadth must coincide with an existing no-haircut, 3-positive-"
                "multiplier sizing stack before extra risk is applied."
            ),
            "mechanism_insight_conflict": (
                "No direct conflict. It avoids LLM soft-ranking, simple universe "
                "expansion, SEC broad recency, short-pressure, options, and "
                "fragility-count retry lanes that recent logs rejected."
            ),
        },
        "parameters": {
            "single_causal_variable": "conviction-qualified broad-breadth trend risk multiplier",
            "breadth_definition": "fraction of feature-complete non-index universe members with above_200ma=True",
            "breadth_min": BROAD_BREADTH_200_MIN,
            "positive_multiplier_min_count": POSITIVE_MULTIPLIER_MIN_COUNT,
            "haircut_multiplier_count_required": 0,
            "tested_variants": VARIANTS,
            "locked_variables": [
                "universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "MAX_PER_SECTOR",
                "scarce-slot breakout deferral",
                "gap cancels",
                "add-ons",
                "all exits",
                "LLM/news replay",
                "earnings strategy",
            ],
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
        "rejection_reason": None if accepted else interpretation,
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": (
                "LLM soft-ranking remains sample-limited; this run tests a "
                "deterministic existing-candidate allocation surface instead."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, implement the breadth field and conviction multiplier "
                "in shared risk/portfolio policy and add run/backtester parity tests."
            ),
        },
        "ticket": {
            "experiment_id": EXPERIMENT_ID,
            "title": "Broad breadth conviction risk",
            "decision": decision,
            "best_variant": best_name,
            "next_action": (
                "Promote through shared policy plus parity tests."
                if accepted
                else "Do not promote; leave accepted allocation unchanged."
            ),
        },
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "quant/experiments/exp_20260507_010_broad_breadth_conviction_trend_risk.py",
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
            "Do not retry nearby broad-breadth conviction multipliers on the same qualifier if this fails.",
            "A valid retry needs new forward evidence or an orthogonal event/news/state discriminator.",
        ],
        "related_files": payload["related_files"],
        "status": "needs_promotion" if accepted else "rejected",
    }

    _write_outputs(payload)
    print(json.dumps(payload["experiment_log_entry"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
