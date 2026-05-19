"""exp-20260507-001 mid-dispersion breakout risk.

Alpha search. Test whether the accepted mid-sector-dispersion market state
also improves `breakout_long` capital allocation. This keeps universe, entries,
ranking, exits, add-ons, LLM/news replay, and the accepted trend mid-dispersion
policy fixed, then applies a breakout-only risk multiplier on those candidate
days.
"""

from __future__ import annotations

import inspect
import json
import math
import statistics
import sys
from collections import OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import backtester as bt  # noqa: E402
import portfolio_engine as pe  # noqa: E402
import risk_engine  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260507-001"
STEM = "mid_dispersion_breakout_risk"
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
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

MID_DISPERSION_MIN = 0.035
MID_DISPERSION_MAX = 0.08
CUSTOM_MULTIPLIER_KEY = "breakout_mid_sector_dispersion_risk_multiplier_applied"

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
        ("mid_dispersion_breakout_1_25x", {"risk_multiplier": 1.25}),
        ("mid_dispersion_breakout_1_50x", {"risk_multiplier": 1.50}),
        ("mid_dispersion_breakout_2_00x", {"risk_multiplier": 2.00}),
    ]
)

_state: dict[str, Any] = {
    "breakout_signals_seen": 0,
    "mid_dispersion_breakout_signals_seen": 0,
    "signals_resized": 0,
    "mid_dispersion_sizing_days": set(),
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


def _runtime_context() -> tuple[pd.Timestamp | None, dict[str, pd.DataFrame] | None]:
    for frame_info in inspect.stack():
        local_vars = frame_info.frame.f_locals
        today = local_vars.get("today")
        ohlcv_all = local_vars.get("ohlcv_all")
        if today is not None and isinstance(ohlcv_all, dict):
            return pd.Timestamp(today), ohlcv_all
    return None, None


def _ret20(df: pd.DataFrame | None, today: pd.Timestamp) -> float | None:
    if df is None or df.empty or "Close" not in df.columns or today not in df.index:
        return None
    pos = df.index.get_loc(today)
    if isinstance(pos, slice) or pos < 20:
        return None
    start = float(df.iloc[pos - 20]["Close"])
    end = float(df.iloc[pos]["Close"])
    if start <= 0:
        return None
    return end / start - 1.0


def _sector_ret20_dispersion(
    today: pd.Timestamp,
    ohlcv_all: dict[str, pd.DataFrame],
    universe: list[str],
    ret_cache: dict[tuple[str, str], float | None],
) -> float | None:
    date_key = str(today.date())
    by_sector: dict[str, list[float]] = defaultdict(list)
    for ticker in universe:
        symbol = ticker.upper()
        key = (date_key, symbol)
        if key not in ret_cache:
            ret_cache[key] = _ret20(ohlcv_all.get(symbol), today)
        ret = ret_cache[key]
        if ret is None:
            continue
        by_sector[risk_engine.SECTOR_MAP.get(symbol, "Unknown")].append(ret)

    sector_returns = [sum(values) / len(values) for values in by_sector.values() if values]
    if len(sector_returns) < 2:
        return None
    return statistics.pstdev(sector_returns)


def _patch_size_signals(variant: dict[str, float] | None, universe: list[str]):
    original = pe.size_signals
    ret_cache: dict[tuple[str, str], float | None] = {}
    dispersion_cache: dict[str, float | None] = {}

    def patched(signals, portfolio_value, risk_pct=None):
        sized = original(signals, portfolio_value, risk_pct=risk_pct)
        if variant is None:
            return sized

        today, ohlcv_all = _runtime_context()
        if today is None or ohlcv_all is None:
            return sized

        date_key = str(today.date())
        if date_key not in dispersion_cache:
            dispersion_cache[date_key] = _sector_ret20_dispersion(
                today,
                ohlcv_all,
                universe,
                ret_cache,
            )
        dispersion = dispersion_cache[date_key]
        mid_dispersion = (
            isinstance(dispersion, (int, float))
            and MID_DISPERSION_MIN < dispersion < MID_DISPERSION_MAX
        )
        multiplier = variant["risk_multiplier"]

        for sig in sized:
            if sig.get("strategy") != "breakout_long":
                continue
            _state["breakout_signals_seen"] += 1
            if not mid_dispersion:
                continue

            sizing = sig.get("sizing") or {}
            entry = sizing.get("entry_price") or sig.get("entry_price")
            stop = sizing.get("stop_price") or sig.get("stop_price")
            original_risk_pct = sizing.get("risk_pct")
            if not sizing or not entry or not stop or original_risk_pct is None:
                continue
            if float(original_risk_pct) <= 0:
                continue

            _state["mid_dispersion_breakout_signals_seen"] += 1
            _state["mid_dispersion_sizing_days"].add(date_key)
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
            preserved["mid_dispersion_original_risk_pct"] = original_risk_pct
            preserved["mid_dispersion_original_shares"] = sizing.get("shares_to_buy")
            preserved["sector_ret20_dispersion"] = _round(dispersion, 6)
            preserved["sector_ret20_dispersion_min"] = MID_DISPERSION_MIN
            preserved["sector_ret20_dispersion_max"] = MID_DISPERSION_MAX
            sig["sizing"] = preserved
            _state["signals_resized"] += 1
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
        "breakout_signals_seen": _state["breakout_signals_seen"],
        "mid_dispersion_breakout_signals_seen": _state[
            "mid_dispersion_breakout_signals_seen"
        ],
        "signals_resized": _state["signals_resized"],
        "mid_dispersion_sizing_days": len(_state["mid_dispersion_sizing_days"]),
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
    for key in _state:
        _state[key] = set() if key.endswith("_days") else 0

    original_size = _patch_size_signals(variant, universe)
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
        "max_drawdown_improvement_min": min(drawdown_deltas.values()),
        "best_sharpe_daily_delta": max(sharpe_deltas.values()),
        "min_win_rate_delta": min(win_rate_deltas.values()),
        "signals_resized_sum": sum(
            int(row["metrics"].get("signals_resized") or 0) for row in after.values()
        ),
        "touched_trade_count_sum": sum(
            int(row["metrics"].get("touched_trade_count") or 0) for row in after.values()
        ),
        "touched_trade_pnl_sum": _round(
            sum(float(row["metrics"].get("touched_trade_pnl") or 0.0) for row in after.values()),
            2,
        ),
    }


def _passes_gate4(aggregate: dict[str, Any]) -> bool:
    ev_delta_pct = aggregate.get("expected_value_score_delta_pct") or 0.0
    pnl_delta_pct = aggregate.get("total_pnl_delta_pct") or 0.0
    max_drawdown_worsening = aggregate.get("max_drawdown_worsening_max") or 0.0
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
        and max_drawdown_worsening <= 0.01
    )
    return bool(material and stability)


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID}: Mid-Dispersion Breakout Risk",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Baseline",
        "",
        "| Window | EV | PnL | SharpeD | DD | Win rate | Trades | Survival |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, row in payload["before_metrics"].items():
        metrics = row["metrics"]
        lines.append(
            "| {label} | {ev} | {pnl} | {sharpe} | {dd} | {wr} | {trades} | {survival} |".format(
                label=label,
                ev=metrics["expected_value_score"],
                pnl=metrics["total_pnl"],
                sharpe=metrics["sharpe_daily"],
                dd=metrics["max_drawdown_pct"],
                wr=metrics["win_rate"],
                trades=metrics["trade_count"],
                survival=metrics["survival_rate"],
            )
        )

    lines.extend(
        [
            "",
            "## Variant Summary",
            "",
            "| Variant | Gate 4 | EV Delta Sum | PnL Delta Sum | EV Windows + / - | PnL Windows + / - | Resized Signals | Touched Trades |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for name, row in payload["variant_results"].items():
        aggregate = row["aggregate"]
        lines.append(
            "| {name} | {gate} | {ev_delta} | {pnl_delta} | {ev_plus}/{ev_minus} | {pnl_plus}/{pnl_minus} | {resized} | {touched} |".format(
                name=name,
                gate=row["gate4_pass"],
                ev_delta=aggregate["expected_value_score_delta_sum"],
                pnl_delta=aggregate["total_pnl_delta_sum"],
                ev_plus=aggregate["windows_ev_improved"],
                ev_minus=aggregate["windows_ev_regressed"],
                pnl_plus=aggregate["windows_pnl_improved"],
                pnl_minus=aggregate["windows_pnl_regressed"],
                resized=aggregate["signals_resized_sum"],
                touched=aggregate["touched_trade_count_sum"],
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
            f"- shared_policy_changed: {str(payload['production_impact']['shared_policy_changed']).lower()}",
            f"- backtester_adapter_changed: {str(payload['production_impact']['backtester_adapter_changed']).lower()}",
            f"- run_adapter_changed: {str(payload['production_impact']['run_adapter_changed']).lower()}",
            f"- replay_only: {str(payload['production_impact']['replay_only']).lower()}",
            f"- parity_test_added: {str(payload['production_impact']['parity_test_added']).lower()}",
            "",
            "No trading rule was promoted by this replay script. A passing result must move the mid-dispersion breakout feature and sizing overlay into shared production/backtest policy before live behavior changes.",
        ]
    )
    return "\n".join(lines) + "\n"


def _write_outputs(payload: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)

    text = json.dumps(payload, indent=2, ensure_ascii=False)
    OUT_JSON.write_text(text + "\n", encoding="utf-8")
    LOG_JSON.write_text(text + "\n", encoding="utf-8")
    TICKET_JSON.write_text(
        json.dumps(payload["ticket"], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    ARTIFACT_MD.write_text(_markdown(payload), encoding="utf-8")
    with EXPERIMENT_LOG_JSONL.open("a", encoding="utf-8") as handle:
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

    passing_variants = [
        name for name, row in variant_results.items() if row["gate4_pass"]
    ]
    ranking_pool = passing_variants or list(variant_results)
    best_variant_name = max(
        ranking_pool,
        key=lambda name: variant_results[name]["aggregate"][
            "expected_value_score_delta_sum"
        ],
    )
    best = variant_results[best_variant_name]
    any_pass = any(row["gate4_pass"] for row in variant_results.values())
    decision = "accepted_requires_shared_policy_promotion" if any_pass else "rejected"

    if any_pass:
        interpretation = (
            f"The best variant `{best_variant_name}` passed the three-window Gate 4 screen. "
            "This replay did not change production behavior; promotion requires a shared "
            "sector-dispersion feature and shared breakout sizing policy used by both "
            "run.py and the backtester."
        )
    else:
        interpretation = (
            "Mid-sector-dispersion breakout risk expansion did not pass the three-window "
            "promotion gate. The best EV variant "
            f"`{best_variant_name}` changed aggregate EV by "
            f"{best['aggregate']['expected_value_score_delta_sum']} and PnL by "
            f"{best['aggregate']['total_pnl_delta_sum']}; this does not justify a new "
            "breakout state-aware sizing branch."
        )

    timestamp = datetime.now(timezone.utc).isoformat()
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "change_type": "capital_allocation_mid_dispersion_breakout_risk",
        "alpha_hypothesis_category": "capital_allocation_meta_routing",
        "hypothesis": (
            "If sector 20-day return dispersion is moderate, existing breakout_long "
            "candidates may deserve more risk because breakouts have enough cross-sector "
            "participation to follow through without relying on a crowded single-sector move."
        ),
        "why_not_llm_soft_ranking": (
            "Production-aligned LLM soft-ranking samples remain too thin; this uses a "
            "deterministic, replayable market-structure feature instead."
        ),
        "history_guardrails": {
            "not_trend_mid_dispersion_retry": True,
            "not_broad_rotation_breakout_retry": True,
            "not_spy_leader_multiplier_retry": True,
            "not_universe_expansion_retry": True,
            "why_not_simple_repeat": (
                "This tests breakout_long under the already-observed mid-sector-dispersion "
                "state. It does not change the accepted trend mid-dispersion multiplier, "
                "does not use IWM-vs-SPY broad-rotation qualification, and does not retune "
                "SPY-relative leader sizing."
            ),
        },
        "parameters": {
            "mid_dispersion_definition": (
                "population stddev of equal-weight sector 20-day returns over the existing "
                "universe, with 0.035 < dispersion < 0.08"
            ),
            "mid_dispersion_min": MID_DISPERSION_MIN,
            "mid_dispersion_max": MID_DISPERSION_MAX,
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
                "gap cancels",
                "add-ons",
                "all exits",
                "accepted trend mid-dispersion policy",
                "LLM/news replay",
                "earnings strategy",
            ],
            "windows": WINDOWS,
        },
        "before_metrics": before,
        "variant_results": variant_results,
        "best_variant": best_variant_name,
        "best_variant_gate4": best["gate4_pass"],
        "decision": decision,
        "interpretation": interpretation,
        "rejection_reason": None if any_pass else interpretation,
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": (
                "LLM data limits were bypassed by selecting another alpha branch."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, compute or reuse sector-dispersion state in shared "
                "production/backtest enrichment and consume it from shared breakout sizing."
            ),
        },
        "ticket": {
            "experiment_id": EXPERIMENT_ID,
            "title": "Mid-dispersion breakout allocation",
            "decision": decision,
            "best_variant": best_variant_name,
            "next_action": (
                "Promote only through shared policy plus parity tests."
                if any_pass
                else "Do not promote; seek a different allocation discriminator."
            ),
        },
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "quant/experiments/exp_20260507_001_mid_dispersion_breakout_risk.py",
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
        "date_range": {
            "primary": "2025-10-23 -> 2026-04-21",
            "secondary": [
                "2025-04-23 -> 2025-10-22",
                "2024-10-02 -> 2025-04-22",
            ],
        },
        "market_regime_summary": {
            label: cfg["state_note"] for label, cfg in WINDOWS.items()
        },
        "before_metrics": {
            label: row["metrics"] for label, row in before.items()
        },
        "after_metrics": {
            name: {
                label: row["metrics"]
                for label, row in variant["by_window"].items()
            }
            for name, variant in variant_results.items()
        },
        "delta_metrics": {
            name: row["aggregate"] for name, row in variant_results.items()
        },
        "best_variant": best_variant_name,
        "best_variant_gate4": best["gate4_pass"],
        "decision": decision,
        "rejection_reason": payload["rejection_reason"],
        "llm_metrics": payload["llm_metrics"],
        "production_impact": payload["production_impact"],
        "history_guardrails": payload["history_guardrails"],
        "next_retry_requires": [
            "Do not retry nearby mid-dispersion breakout-only multipliers on the same bucket if this run fails.",
            "A valid retry needs an orthogonal breakout quality discriminator or forward evidence.",
            "If promoted later, implement the dispersion field and sizing branch through shared production/backtest policy.",
        ],
        "related_files": payload["related_files"],
        "status": "rejected" if not any_pass else "needs_promotion",
    }

    _write_outputs(payload)
    print(json.dumps(payload["experiment_log_entry"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
