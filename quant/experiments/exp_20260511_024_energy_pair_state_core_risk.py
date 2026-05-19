"""exp-20260511-024: energy pair-state core risk routing.

Alpha search. Test one capital-allocation variable: whether existing Energy
core A/B signals deserve a different risk budget only when the already-studied
XLE/USO pair-confirmed state is present.

This does not add XLE/USO as tradeable tickers. It uses them only as reference
state from fixed OHLCV snapshots. Replay only unless Gate 4 clears; any positive
candidate must be promoted through shared run/backtester data plumbing before
live orders change.
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


EXPERIMENT_ID = "exp-20260511-024"
STEM = "energy_pair_state_core_risk"
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

CUSTOM_MULTIPLIER_KEY = "energy_pair_state_core_risk_multiplier_applied"
ENERGY_REFERENCE_TICKERS = ("XLE", "USO")
ENERGY_SIGNAL_STRATEGIES = ("trend_long", "breakout_long")

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
        ("energy_pair_state_core_0_50x", {"risk_multiplier": 0.50}),
        ("energy_pair_state_core_0_75x", {"risk_multiplier": 0.75}),
        ("energy_pair_state_core_1_25x", {"risk_multiplier": 1.25}),
        ("energy_pair_state_core_1_50x", {"risk_multiplier": 1.50}),
    ]
)

_state: dict[str, Any] = {
    "energy_signals_seen": 0,
    "energy_pair_state_signals_seen": 0,
    "signals_resized": 0,
    "energy_pair_state_sizing_days": set(),
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


def _gate2_open_positions() -> dict[str, Any]:
    path = REPO_ROOT / "operator_inputs" / "open_positions.json"
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "passed": False,
            "missing_entry_date_or_target_price": ["file_missing"],
        }

    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    positions = payload.get("positions") if isinstance(payload, dict) else []
    missing = []
    for pos in positions or []:
        missing_fields = [
            field for field in ("entry_date", "target_price") if not pos.get(field)
        ]
        if missing_fields:
            missing.append(
                {
                    "ticker": pos.get("ticker"),
                    "missing_fields": missing_fields,
                }
            )
    return {
        "path": str(path),
        "exists": True,
        "position_count": len(positions or []),
        "missing_entry_date_or_target_price": missing,
        "passed": not missing,
    }


def _runtime_context() -> tuple[pd.Timestamp | None, dict[str, pd.DataFrame] | None]:
    for frame_info in inspect.stack():
        local_vars = frame_info.frame.f_locals
        today = local_vars.get("today")
        ohlcv_all = local_vars.get("ohlcv_all")
        if today is not None and isinstance(ohlcv_all, dict):
            return pd.Timestamp(today), ohlcv_all
    return None, None


def _close_at(df: pd.DataFrame | None, today: pd.Timestamp) -> tuple[int, float] | None:
    if df is None or df.empty or "Close" not in df.columns or today not in df.index:
        return None
    pos = df.index.get_loc(today)
    if isinstance(pos, slice):
        return None
    close = float(df.iloc[int(pos)]["Close"])
    if close <= 0:
        return None
    return int(pos), close


def _ret(df: pd.DataFrame | None, today: pd.Timestamp, days: int) -> float | None:
    at = _close_at(df, today)
    if at is None:
        return None
    pos, end = at
    if pos < days:
        return None
    start = float(df.iloc[pos - days]["Close"])
    if start <= 0:
        return None
    return end / start - 1.0


def _above_sma(df: pd.DataFrame | None, today: pd.Timestamp, days: int) -> bool | None:
    at = _close_at(df, today)
    if at is None:
        return None
    pos, close = at
    if pos < days - 1:
        return None
    window = df.iloc[pos - days + 1 : pos + 1]["Close"]
    if len(window) < days:
        return None
    sma = float(window.mean())
    if sma <= 0:
        return None
    return close > sma


def _energy_pair_state(
    today: pd.Timestamp,
    ohlcv_all: dict[str, pd.DataFrame],
    cache: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    date_key = str(today.date())
    if date_key in cache:
        return cache[date_key]

    by_ticker: dict[str, dict[str, Any]] = {}
    confirmed = True
    for ticker in ENERGY_REFERENCE_TICKERS:
        df = ohlcv_all.get(ticker)
        ret10 = _ret(df, today, 10)
        ret20 = _ret(df, today, 20)
        above200 = _above_sma(df, today, 200)
        ticker_state = {
            "above_200ma": above200,
            "momentum_10d_pct": _round(ret10, 6),
            "momentum_20d_pct": _round(ret20, 6),
        }
        by_ticker[ticker] = ticker_state
        confirmed = confirmed and (
            above200 is True
            and isinstance(ret10, (int, float))
            and ret10 > 0
            and isinstance(ret20, (int, float))
            and ret20 > 0
        )

    state = {
        "confirmed": bool(confirmed),
        "condition": (
            "XLE and USO both above 200-day SMA with positive 10d and 20d "
            "momentum"
        ),
        "tickers": by_ticker,
    }
    cache[date_key] = state
    return state


def _patch_size_signals(variant: dict[str, float] | None):
    original = pe.size_signals
    state_cache: dict[str, dict[str, Any]] = {}

    def patched(signals, portfolio_value, risk_pct=None):
        sized = original(signals, portfolio_value, risk_pct=risk_pct)
        if variant is None:
            return sized

        today, ohlcv_all = _runtime_context()
        if today is None or ohlcv_all is None:
            return sized

        date_key = str(today.date())
        pair_state = _energy_pair_state(today, ohlcv_all, state_cache)
        multiplier = float(variant["risk_multiplier"])

        for sig in sized:
            if sig.get("sector") != "Energy":
                continue
            if sig.get("strategy") not in ENERGY_SIGNAL_STRATEGIES:
                continue
            _state["energy_signals_seen"] += 1
            if pair_state["confirmed"] is not True:
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

            _state["energy_pair_state_signals_seen"] += 1
            _state["energy_pair_state_sizing_days"].add(date_key)
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
            preserved["energy_pair_state_original_risk_pct"] = original_risk_pct
            preserved["energy_pair_state_original_shares"] = sizing.get(
                "shares_to_buy"
            )
            preserved["energy_pair_state_date"] = date_key
            preserved["energy_pair_state"] = pair_state
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
        "energy_signals_seen": _state["energy_signals_seen"],
        "energy_pair_state_signals_seen": _state["energy_pair_state_signals_seen"],
        "signals_resized": _state["signals_resized"],
        "energy_pair_state_sizing_days": len(_state["energy_pair_state_sizing_days"]),
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
                "exit_reason": trade.get("exit_reason"),
                "sector": trade.get("sector"),
                "pnl": trade.get("pnl"),
                "pnl_pct_net": trade.get("pnl_pct_net"),
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
        f"# {EXPERIMENT_ID}: Energy Pair-State Core Risk",
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
            "- Changed variable: risk multiplier for existing Energy trend/breakout signals only when the fixed XLE/USO pair-confirmed state is true.",
            "- Prior near experiment: simple Energy breakout risk boosts and XLE/USO tradeable ETF expansion were rejected; this does not add ETF candidates and requires the documented state discriminator.",
            "- Gate 2 fields: entry_date and target_price are present in open_positions; XLE/USO OHLCV is present in canonical snapshots for replay state only.",
            "- Gate 3: no filter was added, so survival is unchanged except for normal replay path accounting.",
            "- Production note: no production policy was promoted by this replay-only runner. Any positive candidate must add shared reference-feature plumbing to both run.py and backtester.py before orders change.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    gate2 = _gate2_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

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
                    "delta": _delta(
                        after[label]["metrics"],
                        before[label]["metrics"],
                    ),
                    "touched_trades": after[label]["touched_trades"],
                },
            )
            for label in WINDOWS
        )
        variant_results[name] = {
            "parameters": variant,
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
            "The Energy pair-state risk routing did not clear the three-window "
            "stability/materiality gate, so no production policy is promoted."
        )

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "change_type": "capital_allocation",
        "alpha_hypothesis_category": "capital_allocation",
        "hypothesis": (
            "Existing Energy trend/breakout signals may deserve more or less risk "
            "only when Energy equities and oil both confirm continuation through "
            "XLE/USO 200-day and 10/20-day momentum state."
        ),
        "changed_variable": (
            "Energy core A/B risk multiplier under fixed XLE/USO pair-confirmed "
            "state"
        ),
        "single_causal_variable": (
            "Energy core A/B risk multiplier under fixed XLE/USO pair-confirmed "
            "state"
        ),
        "backtest_protocol": {
            "source": "docs/backtesting.md",
            "windows": WINDOWS,
        },
        "date_range": {
            label: f"{window['start']} -> {window['end']}"
            for label, window in WINDOWS.items()
        },
        "why_this_is_not_a_blocked_retry": (
            "The playbook blocks simple Energy breakout boosts and adding XLE/USO "
            "as tradeable ETF candidates. This run does neither: it uses the "
            "previously documented pair-confirmed state as a fixed discriminator "
            "and tests only risk routing for already-selected native Energy "
            "signals."
        ),
        "why_not_llm_soft_ranking": (
            "LLM soft-ranking remains production-sample limited, so this run uses "
            "deterministic OHLCV reference state instead."
        ),
        "parameters": {
            "energy_reference_tickers": ENERGY_REFERENCE_TICKERS,
            "energy_pair_state_condition": (
                "XLE and USO both above 200-day SMA with positive 10d and 20d "
                "momentum"
            ),
            "eligible_signals": {
                "sector": "Energy",
                "strategies": ENERGY_SIGNAL_STRATEGIES,
            },
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
        "gate_results": {
            "gate1": {
                "protocol": "docs/backtesting.md canonical three-window fixed snapshots",
                "baseline_metrics": {
                    label: row["metrics"] for label, row in before.items()
                },
            },
            "gate2": gate2,
            "gate3": {
                "new_filter_added": False,
                "minimum_survival_rate_after": min(
                    float(
                        variant_results[best_variant]["rows"][label]["after"].get(
                            "survival_rate",
                            0.0,
                        )
                    )
                    for label in WINDOWS
                ),
                "passed": True,
            },
            "gate4": {
                "best_variant": best_variant,
                "best_variant_gate4_pass": best["gate4_pass"],
                "aggregate": best["aggregate"],
                "passed": any_pass,
            },
        },
        "before_metrics": before,
        "after_metrics": {
            label: row["after"] for label, row in best["rows"].items()
        },
        "variant_results": variant_results,
        "aggregate_by_variant": {
            name: row["aggregate"] for name, row in variant_results.items()
        },
        "expected_value_score_delta": best["aggregate"][
            "expected_value_score_delta_sum"
        ],
        "best_variant": best_variant,
        "best_variant_gate4": best["gate4_pass"],
        "decision": decision,
        "rejection_reason": rejection_reason,
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": "LLM branch avoided because it remains sample-limited.",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": True,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, add non-tradeable XLE/USO reference-state feature "
                "plumbing and the sizing branch to shared production/backtest "
                "modules before orders change."
            ),
        },
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            str(EXPERIMENT_LOG.relative_to(REPO_ROOT)),
        ],
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Energy pair-state core risk routing",
            "decision": decision,
            "best_variant": best_variant,
            "summary": best["aggregate"],
            "artifact": str(OUT_JSON.relative_to(REPO_ROOT)),
            "single_causal_variable": payload["single_causal_variable"],
        },
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG, payload)

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": decision,
                "best_variant": best_variant,
                "best_aggregate": best["aggregate"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
