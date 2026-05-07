"""exp-20260507-003 recent SEC filing breakout risk.

Alpha search. Test one event-confirmed capital-allocation variable: existing
`breakout_long` candidates with a PIT-safe recent SEC filing may deserve more
risk because the filing can act as an event-confirmation source for technical
breakouts. This runner keeps universe, signal generation, entry filters,
ranking, exits, add-ons, LLM/news replay, and all non-tested sizing rules fixed.
"""

from __future__ import annotations

import inspect
import json
import math
import sys
from collections import OrderedDict, defaultdict
from datetime import datetime, timedelta, timezone
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


EXPERIMENT_ID = "exp-20260507-003"
STEM = "recent_sec_breakout_risk"
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

RECENT_FILING_LOOKBACK_TRADING_DAYS = 20
CUSTOM_MULTIPLIER_KEY = "breakout_recent_sec_filing_risk_multiplier_applied"

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
        ("recent_sec_breakout_1_25x", {"risk_multiplier": 1.25}),
        ("recent_sec_breakout_1_50x", {"risk_multiplier": 1.50}),
        ("recent_sec_breakout_2_00x", {"risk_multiplier": 2.00}),
    ]
)

_state: dict[str, Any] = {
    "breakout_signals_seen": 0,
    "recent_sec_breakout_signals_seen": 0,
    "signals_resized": 0,
    "recent_sec_sizing_days": set(),
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


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        out = float(value)
        return out if math.isfinite(out) else None
    if isinstance(value, str) and value.strip():
        try:
            out = float(value)
        except ValueError:
            return None
        return out if math.isfinite(out) else None
    return None


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def _date_from_feature_file(path: Path) -> str | None:
    suffix = path.stem.rsplit("_", 1)[-1]
    if len(suffix) != 8 or not suffix.isdigit():
        return None
    return f"{suffix[:4]}-{suffix[4:6]}-{suffix[6:]}"


def _load_sec_features(start: str, end: str, lookback_calendar_days: int = 45) -> list[dict[str, Any]]:
    min_date = (datetime.fromisoformat(start) - timedelta(days=lookback_calendar_days)).date().isoformat()
    rows: list[dict[str, Any]] = []
    for path in sorted((REPO_ROOT / "data" / "non_ohlcv").glob("sec_filing_features_*.jsonl")):
        file_date = _date_from_feature_file(path)
        if not file_date or file_date < min_date or file_date > end:
            continue
        for row in _load_jsonl(path):
            accepted = row.get("accepted_datetime") or row.get("accepted_at")
            usable = row.get("usable_trade_date")
            row["ticker"] = str(row.get("ticker") or "").upper()
            row["pit_safe"] = bool(accepted and usable and row.get("ticker"))
            if row["ticker"]:
                rows.append(row)
    return rows


def _runtime_context() -> tuple[pd.Timestamp | None, dict[str, pd.DataFrame] | None]:
    for frame_info in inspect.stack():
        local_vars = frame_info.frame.f_locals
        today = local_vars.get("today")
        ohlcv_all = local_vars.get("ohlcv_all")
        if today is not None and isinstance(ohlcv_all, dict):
            return pd.Timestamp(today), ohlcv_all
    return None, None


def _market_trading_day_distance(
    ohlcv_all: dict[str, pd.DataFrame],
    earlier: str,
    later: str,
) -> int | None:
    spy = ohlcv_all.get("SPY")
    if spy is None or spy.empty:
        return None
    index = pd.DatetimeIndex(spy.index)
    left = index.searchsorted(pd.Timestamp(earlier), side="left")
    right = index.searchsorted(pd.Timestamp(later), side="left")
    if left >= len(index) or right >= len(index):
        return None
    return int(right - left)


def _build_events_by_ticker(sec_features: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in sec_features:
        ticker = str(row.get("ticker") or "").upper()
        usable = str(row.get("usable_trade_date") or "")[:10]
        if ticker and usable and row.get("pit_safe", False):
            out[ticker].append(row)
    for ticker in out:
        out[ticker].sort(
            key=lambda item: (
                str(item.get("usable_trade_date") or ""),
                str(item.get("accepted_datetime") or item.get("accepted_at") or ""),
            ),
            reverse=True,
        )
    return out


def _latest_recent_event(
    events_by_ticker: dict[str, list[dict[str, Any]]],
    ohlcv_all: dict[str, pd.DataFrame],
    ticker: str,
    date_value: str,
) -> tuple[dict[str, Any] | None, int | None]:
    best: dict[str, Any] | None = None
    best_distance: int | None = None
    for row in events_by_ticker.get(ticker.upper(), []):
        usable = str(row.get("usable_trade_date") or "")[:10]
        if not usable or usable > date_value:
            continue
        distance = _market_trading_day_distance(ohlcv_all, usable, date_value)
        if distance is None or distance < 0 or distance > RECENT_FILING_LOOKBACK_TRADING_DAYS:
            continue
        if best is None or distance < (best_distance or 10**9):
            best = row
            best_distance = distance
    return best, best_distance


def _patch_size_signals(
    variant: dict[str, float] | None,
    events_by_ticker: dict[str, list[dict[str, Any]]],
):
    original = pe.size_signals

    def patched(signals, portfolio_value, risk_pct=None):
        sized = original(signals, portfolio_value, risk_pct=risk_pct)
        if variant is None:
            return sized

        today, ohlcv_all = _runtime_context()
        if today is None or ohlcv_all is None:
            return sized

        date_key = str(today.date())
        multiplier = variant["risk_multiplier"]

        for sig in sized:
            if sig.get("strategy") != "breakout_long":
                continue
            _state["breakout_signals_seen"] += 1
            event, distance = _latest_recent_event(
                events_by_ticker,
                ohlcv_all,
                str(sig.get("ticker") or ""),
                date_key,
            )
            if event is None:
                continue

            sizing = sig.get("sizing") or {}
            entry = sizing.get("entry_price") or sig.get("entry_price")
            stop = sizing.get("stop_price") or sig.get("stop_price")
            original_risk_pct = sizing.get("risk_pct")
            if not sizing or not entry or not stop or original_risk_pct is None:
                continue
            if float(original_risk_pct) <= 0:
                continue

            _state["recent_sec_breakout_signals_seen"] += 1
            _state["recent_sec_sizing_days"].add(date_key)
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
            preserved["recent_sec_original_risk_pct"] = original_risk_pct
            preserved["recent_sec_original_shares"] = sizing.get("shares_to_buy")
            preserved["recent_sec_filing_distance_trading_days"] = distance
            preserved["recent_sec_filing_form_type"] = event.get("form_type")
            preserved["recent_sec_filing_item_type"] = event.get("eight_k_item_type")
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
        "recent_sec_breakout_signals_seen": _state["recent_sec_breakout_signals_seen"],
        "signals_resized": _state["signals_resized"],
        "recent_sec_sizing_days": len(_state["recent_sec_sizing_days"]),
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


def _run_window(cfg: dict[str, str], variant: dict[str, float] | None) -> dict[str, Any]:
    for key in _state:
        _state[key] = set() if key.endswith("_days") else 0

    events_by_ticker = _build_events_by_ticker(_load_sec_features(cfg["start"], cfg["end"]))
    original_size = _patch_size_signals(variant, events_by_ticker)
    original_keys = bt.SIZING_MULTIPLIER_KEYS
    if CUSTOM_MULTIPLIER_KEY not in original_keys:
        bt.SIZING_MULTIPLIER_KEYS = tuple(list(original_keys) + [CUSTOM_MULTIPLIER_KEY])
    try:
        result = BacktestEngine(
            universe=sorted(get_universe()),
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
                "pnl_pct_net": trade.get("pnl_pct_net"),
                "sizing_multipliers": trade.get("sizing_multipliers"),
            }
            for trade in (result.get("trades") or [])
            if CUSTOM_MULTIPLIER_KEY in ((trade.get("sizing_multipliers") or {}).keys())
        ][:40],
    }


def _aggregate(before: OrderedDict[str, dict[str, Any]], after: OrderedDict[str, dict[str, Any]]) -> dict[str, Any]:
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
        "expected_value_score_delta_pct": _round((after_ev - baseline_ev) / abs(baseline_ev) if baseline_ev else None, 6),
        "baseline_total_pnl_sum": _round(baseline_pnl, 2),
        "after_total_pnl_sum": _round(after_pnl, 2),
        "total_pnl_delta_sum": _round(after_pnl - baseline_pnl, 2),
        "total_pnl_delta_pct": _round((after_pnl - baseline_pnl) / abs(baseline_pnl) if baseline_pnl else None, 6),
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


def _append_or_replace_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if path.exists():
        for raw in path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                lines.append(raw)
                continue
            if existing.get("experiment_id") == record.get("experiment_id"):
                continue
            lines.append(json.dumps(existing, ensure_ascii=False))
    lines.append(json.dumps(record, ensure_ascii=False))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID}: Recent SEC Filing Breakout Risk",
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
            f"| {label} | {metrics['expected_value_score']} | {metrics['total_pnl']} | "
            f"{metrics['sharpe_daily']} | {metrics['max_drawdown_pct']} | "
            f"{metrics['win_rate']} | {metrics['trade_count']} | {metrics['survival_rate']} |"
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
            "| {name} | {gate} | {ev} | {pnl} | {evw}/{evr} | {pnlw}/{pnlr} | {resized} | {touched} |".format(
                name=name,
                gate=row["gate4_pass"],
                ev=aggregate["expected_value_score_delta_sum"],
                pnl=aggregate["total_pnl_delta_sum"],
                evw=aggregate["windows_ev_improved"],
                evr=aggregate["windows_ev_regressed"],
                pnlw=aggregate["windows_pnl_improved"],
                pnlr=aggregate["windows_pnl_regressed"],
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
            f"- shared_policy_changed: {payload['production_impact']['shared_policy_changed']}",
            f"- backtester_adapter_changed: {payload['production_impact']['backtester_adapter_changed']}",
            f"- run_adapter_changed: {payload['production_impact']['run_adapter_changed']}",
            f"- replay_only: {payload['production_impact']['replay_only']}",
            f"- parity_test_added: {payload['production_impact']['parity_test_added']}",
            "",
        ]
    )
    return "\n".join(lines)


def _write_outputs(payload: dict[str, Any]) -> None:
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    OUT_JSON.write_text(text + "\n", encoding="utf-8")
    LOG_JSON.write_text(text + "\n", encoding="utf-8")
    TICKET_JSON.write_text(json.dumps(payload["ticket"], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    ARTIFACT_MD.write_text(_markdown(payload), encoding="utf-8")
    _append_or_replace_jsonl(EXPERIMENT_LOG, payload["experiment_log_entry"])


def main() -> int:
    before: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for label, cfg in WINDOWS.items():
        before[label] = _run_window(cfg, None)

    variant_results: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for name, variant in VARIANTS.items():
        by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
        for label, cfg in WINDOWS.items():
            row = _run_window(cfg, variant)
            row["delta"] = _delta(row["metrics"], before[label]["metrics"])
            by_window[label] = row
        aggregate = _aggregate(before, by_window)
        variant_results[name] = {
            "parameters": variant,
            "by_window": by_window,
            "aggregate": aggregate,
            "gate4_pass": _passes_gate4(aggregate),
        }

    passing_variants = [name for name, row in variant_results.items() if row["gate4_pass"]]
    ranking_pool = passing_variants or list(variant_results)
    best_variant_name = max(
        ranking_pool,
        key=lambda name: variant_results[name]["aggregate"]["expected_value_score_delta_sum"],
    )
    best = variant_results[best_variant_name]
    any_pass = any(row["gate4_pass"] for row in variant_results.values())
    decision = "accepted_requires_shared_policy_promotion" if any_pass else "rejected"

    if any_pass:
        interpretation = (
            f"The best variant `{best_variant_name}` passed the three-window Gate 4 screen. "
            "This replay did not change production behavior; promotion would require a shared "
            "SEC-event context field and shared sizing policy used by both run.py and the backtester."
        )
    else:
        interpretation = (
            "Recent SEC filing breakout risk expansion did not pass the three-window promotion gate. "
            f"The best EV variant `{best_variant_name}` changed aggregate EV by "
            f"{best['aggregate']['expected_value_score_delta_sum']} and PnL by "
            f"{best['aggregate']['total_pnl_delta_sum']}; this does not justify adding an "
            "event-confirmed breakout sizing branch."
        )

    timestamp = datetime.now(timezone.utc).isoformat()
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "change_type": "capital_allocation_recent_sec_breakout_risk",
        "alpha_hypothesis_category": "event_confirmed_capital_allocation",
        "hypothesis": (
            "If a `breakout_long` candidate has a PIT-safe SEC filing within the last "
            f"{RECENT_FILING_LOOKBACK_TRADING_DAYS} trading days, the event context may confirm "
            "the technical breakout and justify a larger risk budget."
        ),
        "why_not_llm_soft_ranking": (
            "Production-aligned LLM soft-ranking samples remain too thin; this uses complete "
            "PIT-safe non-OHLCV SEC coverage from exp-20260507-002 instead."
        ),
        "history_guardrails": {
            "not_mid_dispersion_breakout_retry": True,
            "not_broad_universe_expansion": True,
            "not_sec_threshold_reaction_retry": True,
            "why_not_simple_repeat": (
                "This tests event-confirmed sizing on existing breakout signals. It does not retry "
                "mid-sector-dispersion breakout sizing, SEC negative-reaction sleeves, simple guidance "
                "raise reaction rules, or broad watchlist expansion."
            ),
        },
        "parameters": {
            "recent_event_definition": (
                "latest PIT-safe row from data/non_ohlcv/sec_filing_features_YYYYMMDD.jsonl "
                f"with usable_trade_date no more than {RECENT_FILING_LOOKBACK_TRADING_DAYS} "
                "trading days before the signal date"
            ),
            "strategy_scope": "breakout_long only",
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
                "all non-tested sizing rules",
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
            "blocker_relation": "LLM data limits were bypassed by selecting another alpha branch.",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, compute recent SEC filing context in shared production/backtest "
                "enrichment and consume it from shared sizing before live behavior changes."
            ),
        },
        "ticket": {
            "experiment_id": EXPERIMENT_ID,
            "status": "needs_promotion" if any_pass else "rejected",
            "lane": "alpha_search",
            "title": "Recent SEC filing breakout risk",
            "decision": decision,
            "best_variant": best_variant_name,
            "created_at": timestamp,
            "completed_at": timestamp,
            "result": {
                "decision": decision,
                "expected_value_score_delta_sum": best["aggregate"]["expected_value_score_delta_sum"],
                "total_pnl_delta_sum": best["aggregate"]["total_pnl_delta_sum"],
                "gate4_passed": bool(best["gate4_pass"]),
            },
        },
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "quant/experiments/exp_20260507_003_recent_sec_breakout_risk.py",
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
        "market_regime_summary": {label: cfg["state_note"] for label, cfg in WINDOWS.items()},
        "before_metrics": {label: row["metrics"] for label, row in before.items()},
        "after_metrics": {
            name: {label: row["metrics"] for label, row in variant["by_window"].items()}
            for name, variant in variant_results.items()
        },
        "delta_metrics": {name: row["aggregate"] for name, row in variant_results.items()},
        "best_variant": best_variant_name,
        "best_variant_gate4": best["gate4_pass"],
        "decision": decision,
        "rejection_reason": payload["rejection_reason"],
        "llm_metrics": payload["llm_metrics"],
        "production_impact": payload["production_impact"],
        "history_guardrails": payload["history_guardrails"],
        "next_retry_requires": [
            "Do not retry nearby recent-SEC breakout multipliers on the same 20-trading-day filing definition if this run fails.",
            "A valid retry needs a richer event-quality discriminator, not just a wider lookback or bigger risk scalar.",
            "If promoted later, implement SEC event context and sizing in shared production/backtest policy with parity tests.",
        ],
        "related_files": payload["related_files"],
        "status": "needs_promotion" if any_pass else "rejected",
    }

    _write_outputs(payload)
    print(json.dumps(payload["experiment_log_entry"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
