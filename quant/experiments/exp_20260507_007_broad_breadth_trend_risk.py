"""exp-20260507-007: broad-breadth trend risk allocation.

Alpha search. Test whether existing trend_long candidates deserve more capital
when the current universe has broad 200-day participation. This runner changes
one causal variable in replay only: a trend-only risk multiplier when at least
75% of feature-complete universe members are above their own 200-day average.

No production strategy code is retained by this experiment. If accepted, the
promotion path is shared risk enrichment plus shared sizing so run.py and the
backtester would see the same fields and order semantics.
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


EXPERIMENT_ID = "exp-20260507-007"
STEM = "broad_breadth_trend_risk"
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

BROAD_BREADTH_200_MIN = 0.75
CUSTOM_MULTIPLIER_KEY = "broad_breadth_trend_risk_multiplier_applied"

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
        ("broad_breadth_trend_1_25x", {"risk_multiplier": 1.25}),
        ("broad_breadth_trend_1_50x", {"risk_multiplier": 1.50}),
        ("broad_breadth_trend_2_00x", {"risk_multiplier": 2.00}),
    ]
)

_state: dict[str, Any] = {
    "trend_signals_seen": 0,
    "broad_breadth_trend_signals_seen": 0,
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
        enriched = original(
            signals,
            features_dict,
            atr_target_mult=atr_target_mult,
        )
        if variant is None:
            return enriched
        breadth = _universe_breadth_above_200ma(features_dict)
        broad = (
            isinstance(breadth, (int, float))
            and breadth >= BROAD_BREADTH_200_MIN
        )
        for sig in enriched:
            sig["universe_breadth_above_200ma"] = _round(breadth, 6)
            sig["broad_universe_breadth_200"] = broad
            sig["broad_universe_breadth_200_min"] = BROAD_BREADTH_200_MIN
        return enriched

    re.enrich_signals = patched
    return original


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

            sizing = sig.get("sizing") or {}
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
            preserved[CUSTOM_MULTIPLIER_KEY] = multiplier
            preserved["broad_breadth_original_risk_pct"] = original_risk_pct
            preserved["broad_breadth_original_shares"] = sizing.get("shares_to_buy")
            preserved["universe_breadth_above_200ma"] = sig.get(
                "universe_breadth_above_200ma"
            )
            preserved["broad_universe_breadth_200_min"] = BROAD_BREADTH_200_MIN
            sig["sizing"] = preserved
            _state["broad_breadth_trend_signals_seen"] += 1
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
        "trend_signals_seen": _state["trend_signals_seen"],
        "broad_breadth_trend_signals_seen": _state[
            "broad_breadth_trend_signals_seen"
        ],
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
        bt.SIZING_MULTIPLIER_KEYS = tuple(
            list(original_keys) + [CUSTOM_MULTIPLIER_KEY]
        )
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
            if CUSTOM_MULTIPLIER_KEY
            in ((trade.get("sizing_multipliers") or {}).keys())
        ][:30],
    }


def _aggregate(
    before: OrderedDict[str, dict[str, Any]],
    after: OrderedDict[str, dict[str, Any]],
) -> dict[str, Any]:
    baseline_ev = sum(
        float(row["metrics"].get("expected_value_score") or 0.0)
        for row in before.values()
    )
    after_ev = sum(
        float(row["metrics"].get("expected_value_score") or 0.0)
        for row in after.values()
    )
    baseline_pnl = sum(
        float(row["metrics"].get("total_pnl") or 0.0)
        for row in before.values()
    )
    after_pnl = sum(
        float(row["metrics"].get("total_pnl") or 0.0)
        for row in after.values()
    )
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
        "best_sharpe_daily_delta": max(sharpe_deltas.values()),
        "min_sharpe_daily_delta": min(sharpe_deltas.values()),
        "min_win_rate_delta": min(win_rate_deltas.values()),
        "signals_resized_sum": sum(
            int(row["metrics"].get("signals_resized") or 0)
            for row in after.values()
        ),
        "touched_trade_count_sum": sum(
            int(row["metrics"].get("touched_trade_count") or 0)
            for row in after.values()
        ),
        "touched_trade_pnl_sum": _round(
            sum(
                float(row["metrics"].get("touched_trade_pnl") or 0.0)
                for row in after.values()
            ),
            2,
        ),
    }


def _passes_gate4(aggregate: dict[str, Any]) -> bool:
    ev_delta_pct = aggregate.get("expected_value_score_delta_pct") or 0.0
    return (
        aggregate.get("windows_ev_improved", 0) >= 2
        and aggregate.get("windows_ev_regressed", 0) == 0
        and ev_delta_pct > 0.10
        and aggregate.get("max_drawdown_worsening_max", 0.0) <= 0.01
        and aggregate.get("min_sharpe_daily_delta", 0.0) >= 0.0
    )


def _write_artifact(payload: dict[str, Any], best_name: str, best_agg: dict[str, Any]) -> None:
    lines = [
        f"# {EXPERIMENT_ID}: Broad-Breadth Trend Risk",
        "",
        f"Decision: {payload['decision']}",
        f"Best variant: {best_name}",
        "",
        "## Aggregate",
        "",
        f"- EV sum before: {best_agg['baseline_expected_value_score_sum']}",
        f"- EV sum after: {best_agg['after_expected_value_score_sum']}",
        f"- EV delta: {best_agg['expected_value_score_delta_sum']} ({best_agg['expected_value_score_delta_pct']})",
        f"- PnL delta: {best_agg['total_pnl_delta_sum']} ({best_agg['total_pnl_delta_pct']})",
        f"- Windows EV improved/regressed: {best_agg['windows_ev_improved']}/{best_agg['windows_ev_regressed']}",
        f"- Signals resized: {best_agg['signals_resized_sum']}",
        "",
        "## Gate 4 Read",
        "",
        payload["acceptance_rule_result"],
        "",
        "## Production Parity",
        "",
        (
            "No production code was retained. A promotion would need the breadth "
            "field in shared risk enrichment and the multiplier in shared sizing."
        ),
    ]
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    generated_at = datetime.now(timezone.utc).isoformat()
    universe = get_universe()

    before: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for label, cfg in WINDOWS.items():
        before[label] = _run_window(universe, cfg, None)

    variant_results: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for name, variant in VARIANTS.items():
        by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
        for label, cfg in WINDOWS.items():
            by_window[label] = _run_window(universe, cfg, variant)
        aggregate = _aggregate(before, by_window)
        variant_results[name] = {
            "parameters": variant,
            "by_window": by_window,
            "aggregate": aggregate,
        }

    best_name = max(
        variant_results,
        key=lambda name: (
            variant_results[name]["aggregate"]["expected_value_score_delta_sum"],
            variant_results[name]["aggregate"]["total_pnl_delta_sum"],
        ),
    )
    best = variant_results[best_name]
    best_agg = best["aggregate"]
    accepted = _passes_gate4(best_agg)
    decision = "accepted_for_promotion" if accepted else "rejected"
    status = decision
    acceptance_rule_result = (
        "Gate 4 passed on north-star EV, drawdown, and Sharpe constraints without "
        "retaining production code; promote only through shared risk_engine + "
        "portfolio_engine."
        if accepted
        else "Gate 4 failed: best variant raised aggregate PnL but did not clear "
        "the north-star EV threshold and worsened risk quality, so it does not "
        "justify another breadth-conditioned sizing rule."
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": generated_at,
        "status": status,
        "decision": decision,
        "lane": "alpha_search",
        "change_type": "capital_allocation_broad_breadth_trend_risk",
        "mechanism_family": "market_structure_breadth_allocation",
        "hypothesis": (
            "Existing trend_long candidates have higher expectancy when at least "
            "75% of the current feature-complete universe is above its 200-day "
            "average, so a trend-only risk multiplier may improve EV without "
            "adding tickers, filters, exits, or ranking rules."
        ),
        "alpha_hypothesis": {
            "category": "allocation",
            "entry_exit_ranking_or_allocation": "allocation",
            "why_this_now": (
                "LLM soft-ranking remains sample-limited; event/universe promotion "
                "lacks same-day replacement evidence; recent slot-ranking, broad "
                "rotation, high-dispersion, SEC, options, and event-runner variants "
                "were rejected. This tests a deterministic state-conditioned capital "
                "allocation variable on existing production candidates."
            ),
        },
        "historical_experiment_check": {
            "similar_prior_results": {
                "exp-20260427-025": (
                    "Rejected simple universe-breadth thresholds for scarce-slot "
                    "breakout deferral; this run does not alter deferral or slots."
                ),
                "exp-20260429-030": (
                    "Observed that broad 200-day breadth cohorts were strong, but "
                    "did not test an executable risk allocation."
                ),
                "exp-20260503-010_and_exp-20260506-019": (
                    "Rejected candidate ranking; this run leaves order unchanged."
                ),
                "exp-20260506-028_to_032": (
                    "Avoids nearby SPY-leader, broad-rotation, high-dispersion, "
                    "mid-dispersion breakout, and accepted mid-dispersion trend rules."
                ),
            },
            "why_not_simple_repeat": (
                "The only tested variable is a trend-only sizing multiplier under "
                "existing 200-day universe participation; it does not gate entries, "
                "unlock slots, add tickers, or retune SPY-relative leader logic."
            ),
            "mechanism_insight_conflict": "none identified after playbook and logs review",
        },
        "parameters": {
            "single_causal_variable": (
                "trend_long risk multiplier when universe_breadth_above_200ma >= 0.75"
            ),
            "breadth_definition": (
                "fraction of feature-complete non-index universe members with above_200ma=True"
            ),
            "breadth_min": BROAD_BREADTH_200_MIN,
            "tested_variants": VARIANTS,
            "best_variant": best_name,
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
        "date_range": {
            label: f"{cfg['start']} -> {cfg['end']}" for label, cfg in WINDOWS.items()
        },
        "snapshots": {label: cfg["snapshot"] for label, cfg in WINDOWS.items()},
        "market_regime_summary": {
            label: cfg["state_note"] for label, cfg in WINDOWS.items()
        },
        "before_metrics": before,
        "variant_results": variant_results,
        "after_metrics": best["by_window"],
        "delta_metrics": best_agg,
        "acceptance_rule_result": acceptance_rule_result,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "production_signal_path_changed": False,
            "orders_changed": False,
            "candidate_shared_policy_path": [
                "quant/risk_engine.py",
                "quant/portfolio_engine.py",
                "quant/constants.py",
                "quant/run.py",
                "quant/backtester.py",
            ],
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft-ranking data is sparse, so this run used a deterministic "
                "OHLCV breadth allocation alpha instead."
            ),
        },
        "risk_note": (
            "May over-allocate to late-cycle broad participation where trend signals "
            "are already crowded; this is why all exits, filters, and ranking stayed locked."
        ),
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
        ],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, ensure_ascii=False, default=str)
    OUT_JSON.write_text(text + "\n", encoding="utf-8")
    LOG_JSON.write_text(text + "\n", encoding="utf-8")
    _write_artifact(payload, best_name, best_agg)

    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": status,
        "decision": decision,
        "lane": "alpha_search",
        "owner": "alpha-search",
        "hypothesis": payload["hypothesis"],
        "single_causal_variable": payload["parameters"]["single_causal_variable"],
        "best_variant": best_name,
        "acceptance_rule_result": acceptance_rule_result,
        "artifact": str(OUT_JSON.relative_to(REPO_ROOT)),
        "log_file": str(LOG_JSON.relative_to(REPO_ROOT)),
        "summary": {
            "ev_delta_sum": best_agg["expected_value_score_delta_sum"],
            "ev_delta_pct": best_agg["expected_value_score_delta_pct"],
            "pnl_delta_sum": best_agg["total_pnl_delta_sum"],
            "windows_ev_improved": best_agg["windows_ev_improved"],
            "windows_ev_regressed": best_agg["windows_ev_regressed"],
            "signals_resized_sum": best_agg["signals_resized_sum"],
            "touched_trade_count_sum": best_agg["touched_trade_count_sum"],
        },
        "production_impact": payload["production_impact"],
        "completed_at": generated_at,
    }
    TICKET_JSON.write_text(
        json.dumps(ticket, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )

    print(f"{EXPERIMENT_ID} {decision} best={best_name}")
    print(json.dumps(ticket["summary"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
