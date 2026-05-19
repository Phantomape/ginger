"""exp-20260506-029 high-sector-dispersion trend risk.

Alpha search. Test one capital-allocation variable suggested by the
meta-allocation state map: trend entries may be fragile when 20-day sector
return dispersion is high. This experiment keeps entries, exits, ranking,
universe, LLM/news replay, and all existing cohort rules fixed, then applies a
trend-only risk multiplier on high-dispersion candidate days.
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
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
from risk_engine import SECTOR_MAP  # noqa: E402


EXPERIMENT_ID = "exp-20260506-029"
STEM = "high_dispersion_trend_risk"
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
PLAYBOOK = REPO_ROOT / "docs" / "alpha-optimization-playbook.md"

DISPERSION_THRESHOLD = 0.08
CUSTOM_MULTIPLIER_KEY = "high_dispersion_trend_risk_multiplier_applied"

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
        ("trend_high_dispersion_0_50x", {"risk_multiplier": 0.50}),
        ("trend_high_dispersion_0_25x", {"risk_multiplier": 0.25}),
        ("trend_high_dispersion_0_00x", {"risk_multiplier": 0.00}),
    ]
)

_state = {
    "trend_signals_seen": 0,
    "high_dispersion_trend_signals_seen": 0,
    "signals_resized": 0,
    "high_dispersion_sizing_days": set(),
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


def _sector_dispersion20(
    today: pd.Timestamp,
    ohlcv_all: dict[str, pd.DataFrame],
    universe: list[str],
    ret_cache: dict[tuple[str, str], float | None],
) -> float | None:
    by_sector: dict[str, list[float]] = defaultdict(list)
    date_key = str(today.date())
    for ticker in universe:
        sector = SECTOR_MAP.get(ticker, "Unknown")
        if sector == "Unknown":
            continue
        cache_key = (date_key, ticker)
        if cache_key not in ret_cache:
            ret_cache[cache_key] = _ret20(ohlcv_all.get(ticker), today)
        value = ret_cache[cache_key]
        if isinstance(value, (int, float)):
            by_sector[sector].append(value)

    sector_returns = [
        sum(values) / len(values)
        for values in by_sector.values()
        if values
    ]
    if len(sector_returns) < 2:
        return None
    return statistics.pstdev(sector_returns)


def _zero_risk_sizing(base_risk_pct: float | None, entry: float, stop: float) -> dict:
    if hasattr(pe, "_zero_risk_sizing"):
        return pe._zero_risk_sizing(base_risk_pct or 0.0, entry, stop)  # noqa: SLF001
    return {
        "portfolio_value_usd": 0.0,
        "risk_pct": 0.0,
        "risk_amount_usd": 0.0,
        "entry_price": round(entry, 2),
        "stop_price": round(stop, 2),
        "risk_per_share": round(entry - stop, 2),
        "net_risk_per_share": None,
        "shares_to_buy": 0,
        "position_value_usd": 0.0,
        "position_pct_of_portfolio": 0.0,
        "base_risk_pct": base_risk_pct,
    }


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
            dispersion_cache[date_key] = _sector_dispersion20(
                today,
                ohlcv_all,
                universe,
                ret_cache,
            )
        dispersion = dispersion_cache[date_key]
        high_dispersion = (
            isinstance(dispersion, (int, float))
            and dispersion >= DISPERSION_THRESHOLD
        )

        multiplier = variant["risk_multiplier"]
        for sig in sized:
            if sig.get("strategy") != "trend_long":
                continue
            _state["trend_signals_seen"] += 1
            if not high_dispersion:
                continue

            sizing = sig.get("sizing") or {}
            if not sizing:
                continue
            entry = sizing.get("entry_price") or sig.get("entry_price")
            stop = sizing.get("stop_price") or sig.get("stop_price")
            original_risk_pct = sizing.get("risk_pct")
            if not entry or not stop or original_risk_pct is None:
                continue

            _state["high_dispersion_trend_signals_seen"] += 1
            _state["high_dispersion_sizing_days"].add(date_key)
            if multiplier <= 0:
                new_sizing = _zero_risk_sizing(
                    sizing.get("base_risk_pct") or risk_pct,
                    float(entry),
                    float(stop),
                )
            else:
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
            preserved["high_dispersion_trend_original_risk_pct"] = original_risk_pct
            preserved["high_dispersion_trend_original_shares"] = sizing.get(
                "shares_to_buy"
            )
            preserved["sector_ret20_dispersion"] = _round(dispersion, 6)
            preserved["sector_ret20_dispersion_threshold"] = DISPERSION_THRESHOLD
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
        "total_return_pct": _round(
            benchmarks.get("strategy_total_return_pct"),
            4,
        ),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": result.get("total_trades"),
        "survival_rate": _round(result.get("survival_rate"), 4),
        "tail_loss_share": _round(result.get("tail_loss_share"), 4),
        "trend_signals_seen": _state["trend_signals_seen"],
        "high_dispersion_trend_signals_seen": (
            _state["high_dispersion_trend_signals_seen"]
        ),
        "signals_resized": _state["signals_resized"],
        "high_dispersion_sizing_days": len(_state["high_dispersion_sizing_days"]),
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
        pe.size_signals = original_size
        bt.SIZING_MULTIPLIER_KEYS = original_keys

    if "error" in result:
        raise RuntimeError(result["error"])
    return {
        "metrics": _metrics(result),
        "trades": [
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
        ][:20],
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
        "trade_count_delta_sum": sum(
            int(after[label]["metrics"].get("trade_count") or 0)
            - int(before[label]["metrics"].get("trade_count") or 0)
            for label in before
        ),
    }


def _passes_gate4(aggregate: dict[str, Any]) -> bool:
    ev_delta_pct = aggregate.get("expected_value_score_delta_pct") or 0.0
    pnl_delta_pct = aggregate.get("total_pnl_delta_pct") or 0.0
    majority_ev = aggregate.get("windows_ev_improved", 0) >= 2
    majority_pnl = aggregate.get("windows_pnl_improved", 0) >= 2
    return bool(
        majority_ev
        and majority_pnl
        and (
            ev_delta_pct > 0.10
            or pnl_delta_pct > 0.05
        )
    )


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID}: High-Dispersion Trend Risk",
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
        resized = sum(
            int(window["metrics"].get("signals_resized") or 0)
            for window in row["by_window"].values()
        )
        touched = sum(
            int(window["metrics"].get("touched_trade_count") or 0)
            for window in row["by_window"].values()
        )
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
                resized=resized,
                touched=touched,
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
            "- shared_policy_changed: false",
            "- backtester_adapter_changed: false",
            "- run_adapter_changed: false",
            "- replay_only: false",
            "- parity_test_added: false",
            "",
            "No trading rule was promoted. If a future retry passes Gate 4, the dispersion feature must move into shared enrichment before production use.",
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
    with EXPERIMENT_LOG_JSONL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload["experiment_log_entry"], ensure_ascii=False) + "\n")

    playbook_note = (
        "\n"
        f"### 2026-05-06 mechanism update: high-dispersion trend de-risk\n\n"
        f"Experiment: `{EXPERIMENT_ID}`\n\n"
        f"Decision: `{payload['decision']}`.\n\n"
        f"Finding: {payload['interpretation']}\n\n"
        "Do not repeat: nearby trend-only high-sector-dispersion multipliers "
        "using the same 8% dispersion threshold unless a new discriminator "
        "or forward evidence explains why the touched trades should differ.\n"
    )
    PLAYBOOK.write_text(PLAYBOOK.read_text(encoding="utf-8") + playbook_note, encoding="utf-8")


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

    best_variant_name = max(
        variant_results,
        key=lambda name: variant_results[name]["aggregate"][
            "expected_value_score_delta_sum"
        ],
    )
    best = variant_results[best_variant_name]
    any_pass = any(row["gate4_pass"] for row in variant_results.values())
    decision = "accepted_requires_shared_policy_promotion" if any_pass else "rejected"

    if any_pass:
        interpretation = (
            "At least one high-sector-dispersion trend multiplier passed the "
            "three-window Gate 4 screen, but no production/backtest policy was "
            "changed in this script. Promotion requires a shared market-state "
            "feature and a shared sizing rule."
        )
    else:
        interpretation = (
            "High-sector-dispersion trend de-risking did not pass Gate 4. "
            f"The best variant `{best_variant_name}` changed aggregate EV by "
            f"{best['aggregate']['expected_value_score_delta_sum']} and PnL by "
            f"{best['aggregate']['total_pnl_delta_sum']}; it does not justify a "
            "new state-aware trend sizing branch."
        )

    timestamp = datetime.now(timezone.utc).isoformat()
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "alpha_hypothesis_category": "capital_allocation_meta_routing",
        "hypothesis": (
            "If trend entries lose edge when sector leadership is fragmented, "
            "then shrinking trend risk only when equal-weight sector 20-day "
            "return dispersion is at least 8% should improve old/thin tapes "
            "without harming the stronger windows."
        ),
        "why_not_llm_soft_ranking": (
            "Production-aligned LLM soft-ranking samples remain too thin; this "
            "uses a deterministic, replayable market-structure feature instead."
        ),
        "history_guardrails": {
            "not_mfe_exit_retry": True,
            "not_broad_rotation_spy_leader_retry": True,
            "not_universe_expansion_retry": True,
            "why_not_simple_repeat": (
                "This tests the specific high-dispersion trend cohort surfaced "
                "by exp-20260506-024, not another protective stop, broad "
                "breakout de-prioritization, or SPY-leader multiplier retune."
            ),
        },
        "parameters": {
            "dispersion_definition": (
                "population stddev of equal-weight sector 20-day returns over "
                "the existing universe"
            ),
            "dispersion_threshold": DISPERSION_THRESHOLD,
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
                "If accepted later, compute sector dispersion in shared "
                "production/backtest enrichment and consume it from shared sizing."
            ),
        },
        "ticket": {
            "experiment_id": EXPERIMENT_ID,
            "title": "High-dispersion trend risk allocation",
            "decision": decision,
            "best_variant": best_variant_name,
            "next_action": (
                "Do not promote; use a different alpha branch unless new "
                "dispersion evidence appears."
                if not any_pass
                else "Promote only through shared policy plus parity tests."
            ),
        },
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "docs/experiment_log.jsonl",
            "docs/alpha-optimization-playbook.md",
        ],
    }

    payload["experiment_log_entry"] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": payload["lane"],
        "change_type": "capital_allocation_high_dispersion_trend_risk",
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
            label: cfg["state_note"]
            for label, cfg in WINDOWS.items()
        },
        "before_metrics": {
            label: row["metrics"]
            for label, row in before.items()
        },
        "after_metrics": {
            name: {
                label: row["metrics"]
                for label, row in variant["by_window"].items()
            }
            for name, variant in variant_results.items()
        },
        "delta_metrics": {
            name: row["aggregate"]
            for name, row in variant_results.items()
        },
        "best_variant": best_variant_name,
        "best_variant_gate4": best["gate4_pass"],
        "decision": decision,
        "rejection_reason": payload["rejection_reason"],
        "llm_metrics": payload["llm_metrics"],
        "production_impact": payload["production_impact"],
        "history_guardrails": payload["history_guardrails"],
        "next_retry_requires": [
            "Do not retry nearby trend-only high-dispersion multipliers at the same 8% threshold.",
            "A valid retry needs a new discriminator such as event/news context or forward evidence.",
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
