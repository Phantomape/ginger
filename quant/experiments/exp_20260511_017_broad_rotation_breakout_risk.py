"""exp-20260511-017 broad-rotation breakout risk.

Alpha search. Test one capital-allocation variable: whether existing
`breakout_long` candidates deserve different risk when small-cap breadth is
leading the broad tape, defined as IWM 20-day return minus SPY 20-day return
greater than 2 percentage points.

Replay only unless Gate 4 clears. If promoted, the broad-rotation field must be
computed in shared enrichment and consumed by shared sizing so production and
backtest stay aligned.
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

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import backtester as bt  # noqa: E402
import portfolio_engine as pe  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260511-017"
STEM = "broad_rotation_breakout_risk"
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

BROAD_ROTATION_IWM_MINUS_SPY_20D_MIN = 0.02
CUSTOM_MULTIPLIER_KEY = "broad_rotation_breakout_risk_multiplier_applied"

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
        ("broad_rotation_breakout_0_50x", {"risk_multiplier": 0.50}),
        ("broad_rotation_breakout_1_25x", {"risk_multiplier": 1.25}),
        ("broad_rotation_breakout_1_50x", {"risk_multiplier": 1.50}),
        ("broad_rotation_breakout_2_00x", {"risk_multiplier": 2.00}),
    ]
)

_state: dict[str, Any] = {
    "breakout_signals_seen": 0,
    "broad_rotation_breakout_signals_seen": 0,
    "signals_resized": 0,
    "broad_rotation_sizing_days": set(),
}


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(out) or math.isinf(out):
        return None
    return round(out, digits)


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_safe(item) for item in value]
    if isinstance(value, set):
        return sorted(_safe(item) for item in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload_line = json.dumps(_safe(payload), ensure_ascii=False, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                rows.append(line)
                continue
            if row.get("experiment_id") == payload["experiment_id"]:
                if not replaced:
                    rows.append(payload_line)
                    replaced = True
                continue
            rows.append(line)
    if not replaced:
        rows.append(payload_line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


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


def _iwm_minus_spy_ret20(
    today: pd.Timestamp,
    ohlcv_all: dict[str, pd.DataFrame],
    ret_cache: dict[tuple[str, str], float | None],
) -> float | None:
    date_key = str(today.date())
    for ticker in ("IWM", "SPY"):
        key = (date_key, ticker)
        if key not in ret_cache:
            ret_cache[key] = _ret20(ohlcv_all.get(ticker), today)
    iwm_ret = ret_cache[(date_key, "IWM")]
    spy_ret = ret_cache[(date_key, "SPY")]
    if iwm_ret is None or spy_ret is None:
        return None
    return iwm_ret - spy_ret


def _patch_size_signals(variant: dict[str, float] | None):
    original = pe.size_signals
    ret_cache: dict[tuple[str, str], float | None] = {}
    rotation_cache: dict[str, float | None] = {}

    def patched(signals, portfolio_value, risk_pct=None):
        sized = original(signals, portfolio_value, risk_pct=risk_pct)
        if variant is None:
            return sized

        today, ohlcv_all = _runtime_context()
        if today is None or ohlcv_all is None:
            return sized

        date_key = str(today.date())
        if date_key not in rotation_cache:
            rotation_cache[date_key] = _iwm_minus_spy_ret20(
                today,
                ohlcv_all,
                ret_cache,
            )
        iwm_minus_spy = rotation_cache[date_key]
        broad_rotation = (
            isinstance(iwm_minus_spy, (int, float))
            and iwm_minus_spy > BROAD_ROTATION_IWM_MINUS_SPY_20D_MIN
        )
        multiplier = float(variant["risk_multiplier"])

        for sig in sized:
            if sig.get("strategy") != "breakout_long":
                continue
            _state["breakout_signals_seen"] += 1
            if not broad_rotation:
                continue

            sizing = sig.get("sizing") or {}
            if not sizing:
                continue
            entry = sizing.get("entry_price") or sig.get("entry_price")
            stop = sizing.get("stop_price") or sig.get("stop_price")
            original_risk_pct = sizing.get("risk_pct")
            if not entry or not stop or original_risk_pct is None:
                continue
            if float(original_risk_pct) <= 0:
                continue

            _state["broad_rotation_breakout_signals_seen"] += 1
            _state["broad_rotation_sizing_days"].add(date_key)
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
            preserved["broad_rotation_breakout_original_risk_pct"] = (
                original_risk_pct
            )
            preserved["broad_rotation_breakout_original_shares"] = sizing.get(
                "shares_to_buy"
            )
            preserved["iwm_minus_spy_ret20"] = _round(iwm_minus_spy, 6)
            preserved["iwm_minus_spy_ret20_threshold"] = (
                BROAD_ROTATION_IWM_MINUS_SPY_20D_MIN
            )
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
        "strategy_vs_spy_pct": _round(benchmarks.get("strategy_vs_spy_pct"), 4),
        "strategy_vs_qqq_pct": _round(benchmarks.get("strategy_vs_qqq_pct"), 4),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": result.get("total_trades"),
        "survival_rate": _round(result.get("survival_rate"), 4),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "tail_loss_share": _round(result.get("tail_loss_share"), 4),
        "worst_trade_pct": _round(result.get("worst_trade_pct"), 4),
        "max_consecutive_losses": result.get("max_consecutive_losses"),
        "breakout_signals_seen": _state["breakout_signals_seen"],
        "broad_rotation_breakout_signals_seen": _state[
            "broad_rotation_breakout_signals_seen"
        ],
        "signals_resized": _state["signals_resized"],
        "broad_rotation_sizing_days": len(_state["broad_rotation_sizing_days"]),
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
                "pnl_pct": trade.get("pnl_pct"),
                "sizing_multipliers": trade.get("sizing_multipliers"),
            }
            for trade in (result.get("trades") or [])
            if CUSTOM_MULTIPLIER_KEY
            in ((trade.get("sizing_multipliers") or {}).keys())
        ][:25],
    }


def _aggregate(
    before: OrderedDict[str, dict[str, Any]],
    after: OrderedDict[str, dict[str, Any]],
) -> dict[str, Any]:
    ev_deltas = {}
    pnl_deltas = {}
    sharpe_deltas = {}
    drawdown_deltas = {}
    win_rate_deltas = {}
    survival_deltas = {}
    for label in before:
        b = before[label]["metrics"]
        a = after[label]["metrics"]
        ev_deltas[label] = _round(
            (a.get("expected_value_score") or 0.0)
            - (b.get("expected_value_score") or 0.0),
            6,
        )
        pnl_deltas[label] = _round(
            (a.get("total_pnl") or 0.0) - (b.get("total_pnl") or 0.0),
            2,
        )
        sharpe_deltas[label] = _round(
            (a.get("sharpe_daily") or 0.0) - (b.get("sharpe_daily") or 0.0),
            6,
        )
        drawdown_deltas[label] = _round(
            (a.get("max_drawdown_pct") or 0.0) - (b.get("max_drawdown_pct") or 0.0),
            6,
        )
        win_rate_deltas[label] = _round(
            (a.get("win_rate") or 0.0) - (b.get("win_rate") or 0.0),
            6,
        )
        survival_deltas[label] = _round(
            (a.get("survival_rate") or 0.0) - (b.get("survival_rate") or 0.0),
            6,
        )

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
        "by_window_survival_rate_delta": survival_deltas,
        "trade_count_delta_sum": sum(
            int(after[label]["metrics"].get("trade_count") or 0)
            - int(before[label]["metrics"].get("trade_count") or 0)
            for label in before
        ),
        "max_drawdown_worsening_max": max(drawdown_deltas.values()),
        "max_drawdown_improvement_min": min(drawdown_deltas.values()),
        "best_sharpe_daily_delta": max(sharpe_deltas.values()),
        "min_win_rate_delta": min(win_rate_deltas.values()),
        "min_survival_rate": min(
            float(after[label]["metrics"].get("survival_rate") or 0.0)
            for label in before
        ),
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
    pnl_delta_pct = aggregate.get("total_pnl_delta_pct") or 0.0
    max_drawdown_worsening = aggregate.get("max_drawdown_worsening_max") or 0.0
    material = (
        ev_delta_pct > 0.10
        or pnl_delta_pct > 0.05
        or (aggregate.get("best_sharpe_daily_delta") or 0.0) > 0.10
        or (aggregate.get("max_drawdown_improvement_min") or 0.0) < -0.01
        or (
            aggregate.get("touched_trade_count_sum", 0) >= 3
            and (aggregate.get("min_win_rate_delta") or 0.0) >= 0
            and ev_delta_pct > 0
        )
    )
    stability = (
        aggregate.get("windows_ev_improved", 0) >= 2
        and aggregate.get("windows_ev_regressed", 0) == 0
        and max_drawdown_worsening <= 0.01
        and (aggregate.get("min_survival_rate") or 0.0) >= 0.05
    )
    return bool(material and stability)


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID}: Broad-Rotation Breakout Risk",
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
            "## Gate Answers",
            "",
            f"- Hypothesis: {payload['hypothesis']}",
            "- Changed variable: broad-rotation breakout risk multiplier only.",
            "- Prior near experiment: broad-rotation trend risk was rejected; this tests breakout_long, not trend_long.",
            "- Fields checked: entry_date and target_price exist in open_positions; IWM/SPY OHLCV exists in canonical snapshots.",
            "- Production note: no production policy promoted by this replay-only runner.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    universe = sorted(get_universe())
    before: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for label, cfg in WINDOWS.items():
        print(f"baseline {label}")
        before[label] = _run_window(universe, cfg, None)

    variant_results: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for name, variant in VARIANTS.items():
        print(f"variant {name}")
        after: OrderedDict[str, dict[str, Any]] = OrderedDict()
        for label, cfg in WINDOWS.items():
            after[label] = _run_window(universe, cfg, variant)
        aggregate = _aggregate(before, after)
        rows = OrderedDict(
            (
                label,
                {
                    "window": label,
                    "start": WINDOWS[label]["start"],
                    "end": WINDOWS[label]["end"],
                    "snapshot": WINDOWS[label]["snapshot"],
                    "state_note": WINDOWS[label]["state_note"],
                    "before": before[label]["metrics"],
                    "after": after[label]["metrics"],
                    "delta": _delta(after[label]["metrics"], before[label]["metrics"]),
                    "touched_trades": after[label]["touched_trades"],
                },
            )
            for label in WINDOWS
        )
        variant_results[name] = {
            "parameters": variant,
            "after_metrics": after,
            "rows": rows,
            "aggregate": aggregate,
            "gate4_pass": _passes_gate4(aggregate),
        }

    best_variant = max(
        variant_results,
        key=lambda name: variant_results[name]["aggregate"][
            "expected_value_score_delta_sum"
        ],
    )
    best = variant_results[best_variant]
    any_pass = any(row["gate4_pass"] for row in variant_results.values())
    decision = "accepted_candidate_needs_shared_promotion" if any_pass else "rejected"
    rejection_reason = None
    if not any_pass:
        rejection_reason = (
            "No broad-rotation breakout risk variant passed Gate 4 across the "
            "three canonical windows."
        )

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "lane": "alpha_search",
        "change_type": "capital_allocation_broad_rotation_breakout_risk",
        "alpha_hypothesis_category": "capital_allocation",
        "hypothesis": (
            "Existing breakout_long candidates may deserve a state-aware risk "
            "budget when IWM 20-day momentum leads SPY by more than 2pp, because "
            "broad participation can confirm breakout follow-through."
        ),
        "why_not_llm_soft_ranking": (
            "LLM soft-ranking samples remain too thin; this uses a deterministic, "
            "production-replayable market-state feature instead."
        ),
        "parameters": {
            "single_causal_variable": "breakout_long risk multiplier when IWM 20d return minus SPY 20d return > 0.02",
            "broad_rotation_definition": "IWM 20-day return minus SPY 20-day return greater than 0.02",
            "broad_rotation_iwm_minus_spy_20d_min": BROAD_ROTATION_IWM_MINUS_SPY_20D_MIN,
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
        "gate_preregistration": {
            "gate1_baseline_protocol": "docs/backtesting.md canonical fixed three-window snapshots",
            "gate2_fields": {
                "entry_date": "present in operator_inputs/open_positions.json",
                "target_price": "present in operator_inputs/open_positions.json",
                "IWM_OHLCV": "required from snapshots/watchlist",
                "SPY_OHLCV": "required from snapshots/watchlist",
            },
            "gate3_filter_survival_rule": "No entry filter added; survival_rate still must remain >= 5%.",
            "gate4_acceptance": "Majority-window EV improvement, no EV-regressed windows, survival >= 5%, and controlled drawdown damage.",
        },
        "before_metrics": before,
        "variant_results": variant_results,
        "aggregate_by_variant": {
            name: row["aggregate"] for name, row in variant_results.items()
        },
        "best_variant": best_variant,
        "best_variant_gate4": best["gate4_pass"],
        "decision": decision,
        "rejection_reason": rejection_reason,
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": "LLM data limits were bypassed by selecting another alpha branch.",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, compute broad_rotation_state in shared enrichment "
                "from features_dict and consume it from shared portfolio sizing."
            ),
        },
        "history_guardrails": {
            "not_broad_rotation_trend_retry": True,
            "not_high_dispersion_retry": True,
            "not_space_static_pool_retry": True,
            "not_sec_feature_queue_retry": True,
            "why_not_simple_repeat": (
                "This uses the broad-rotation state on breakout_long only. The "
                "prior broad-rotation experiment tested trend_long and failed "
                "because of drawdown/Sharpe damage."
            ),
        },
        "next_retry_requires": [
            "Do not retry nearby broad-rotation breakout multipliers on the same threshold if rejected.",
            "A valid retry needs event/news context, candidate replacement value, or a richer breadth discriminator.",
            "If promoted, implement the state field and sizing branch through shared production/backtest policy.",
        ],
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            str(Path(__file__).relative_to(REPO_ROOT)),
        ],
        "status": decision,
    }

    experiment_log_entry = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "status": decision,
        "decision": decision,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "changed_variable": payload["parameters"]["single_causal_variable"],
        "parameters": payload["parameters"],
        "date_range": {
            "primary": f"{WINDOWS['late_strong']['start']} -> {WINDOWS['late_strong']['end']}",
            "secondary": [
                f"{WINDOWS['mid_weak']['start']} -> {WINDOWS['mid_weak']['end']}",
                f"{WINDOWS['old_thin']['start']} -> {WINDOWS['old_thin']['end']}",
            ],
        },
        "backtest_protocol": "docs/backtesting.md canonical three fixed snapshot windows",
        "before_metrics": {
            label: row["metrics"] for label, row in before.items()
        },
        "after_metrics": {
            name: {
                label: row["metrics"]
                for label, row in variant_results[name]["after_metrics"].items()
            }
            for name in variant_results
        },
        "expected_value_score_delta": {
            name: row["aggregate"]["expected_value_score_delta_sum"]
            for name, row in variant_results.items()
        },
        "best_variant": best_variant,
        "decision_reason": rejection_reason
        or "At least one replay variant passed Gate 4 and needs shared-policy promotion before any live use.",
        "production_impact": payload["production_impact"],
        "llm_metrics": payload["llm_metrics"],
        "rejection_reason": rejection_reason,
        "next_evidence_needed": payload["next_retry_requires"],
        "related_files": payload["related_files"],
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(TICKET_JSON, experiment_log_entry)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG, experiment_log_entry)

    print(json.dumps(_safe({
        "experiment_id": EXPERIMENT_ID,
        "decision": decision,
        "best_variant": best_variant,
        "best_aggregate": best["aggregate"],
        "artifact": str(OUT_JSON.relative_to(REPO_ROOT)),
    }), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
