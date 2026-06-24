"""exp-20260623-022: fixed-entry regime-conditional trailing exit scout.

This is an alpha-search replay scout. It asks whether the ATR trailing stop
that failed globally in exp-20260623-020 becomes useful when it is gated by the
shared PIT entry-time regime_chop_state label. It changes no production,
backtester, ranking, sizing, order, or default exit behavior.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, QUANT_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from constants import ATR_STOP_MULT, ROUND_TRIP_COST_PCT  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
from fill_model import apply_stop_fill, apply_target_fill  # noqa: E402
import regime_chop_state as rcs  # noqa: E402


EXPERIMENT_ID = "exp-20260623-022"
SLUG = "regime_conditional_chop_trailing_exit"
RUNNER = f"quant/experiments/exp_20260623_022_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
OWNER = "alpha-explore"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260623_022_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_PROTOCOL = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260602-003"
    / "exp_20260602_003_post_earnings_explicit_continuation.json"
)
BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "trades": REPO_ROOT / "data" / "experiments" / "exp-20260602-003" / "late_strong_after.json",
        "snapshot": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20251023_20260421.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "trades": REPO_ROOT / "data" / "experiments" / "exp-20260602-003" / "mid_weak_after.json",
        "snapshot": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20250423_20251022.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "trades": REPO_ROOT / "data" / "experiments" / "exp-20260602-003" / "old_thin_after.json",
        "snapshot": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20241002_20250422.json",
    },
}

HYPOTHESIS = (
    "Exit/risk allocation hypothesis: fixed-entry ATR trailing may only add "
    "value when entry-time shared regime_chop_state labels the market as "
    "choppy_range; in risk_on/risk_off trend regimes the current static entry "
    "stop and target should remain unchanged to avoid cutting winners."
)
CHANGE_TYPE = "exit_policy_replay_scout"
MECHANISM_FAMILY = "exit_policy"
TRIAL_FAMILY = "regime_conditional_trailing_stop"
TRIAL_VARIANT_ID = "entry_regime_chop_atr_trail_static_elsewhere_v1"
CHANGED_VARIABLE = "regime_conditional_chop_only_atr_trailing_exit_v1"
NEW_EVIDENCE_TYPE = "new_gate_shape_shared_regime_chop_state"
NEW_EVIDENCE_AXIS = (
    "ATR trailing is applied only when the existing shared PIT entry-time "
    "regime_chop_state labels choppy_range. This is not a trail trigger/offset "
    "sweep and was named as the valid reopen condition in exp-20260623-020."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260623-020",
    "exp-20260623-003",
    "exp-20260622-017",
    "exp-20260503-009",
]
CAUSAL_COMPONENTS = [
    "fixed baseline entries",
    "shared regime_chop_state entry tag",
    "ATR trail only in choppy_range",
    "static stop/target elsewhere",
    "canonical three-window fixed-entry replay",
    "observed-only parity boundary",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260623-022/exp_20260623_022_regime_conditional_chop_trailing_exit.json",
    "experiments/cards/exp-20260623-022.md",
    "experiments/manifests/exp-20260623-022.json",
    "experiments/tickets/exp-20260623-022.json",
    "experiments/logs/exp-20260623-022.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]
DEFAULT_PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": 0.05,
    "expected_pnl_delta": 2000.0,
    "main_failure_modes": [
        "trailing_still_cuts_winners",
        "chop_label_not_exit_predictive",
        "too_few_choppy_trades",
        "fixed_entry_not_portfolio_replay",
    ],
    "confidence_reason": (
        "exp-20260623-020 rejected flat ATR trailing because it cut trend "
        "winners, but its closeout explicitly left regime-conditional trailing "
        "open as a different mechanism. exp-20260622-017 provides the shared "
        "PIT regime_chop_state tag for core trades; success odds remain low "
        "because exit-policy families have repeatedly failed and fixed-entry "
        "evidence is not production parity."
    ),
    "recorded_at": "2026-06-23T18:04:25+00:00",
}

TRAIL_TRIGGER_ATR_MULT = 3.0
TRAIL_OFFSET_ATR_MULT = 2.0
SMA_SHORT = 50
INDEX_TICKERS = ("SPY", "QQQ", "IWM")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                rows.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(raw)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def as_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def round_or_none(value: Any, digits: int = 6) -> float | None:
    number = as_float(value)
    return round(number, digits) if number is not None else None


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def median_or_none(values: list[float]) -> float | None:
    return float(median(values)) if values else None


def load_ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    return prediction or DEFAULT_PREDICTION


def ohlcv_payload(snapshot: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    if isinstance(snapshot, dict) and "ohlcv" in snapshot:
        return snapshot["ohlcv"]
    return snapshot


def sorted_bars(bars: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = [b for b in (bars or []) if b.get("Date") and b.get("Close") is not None]
    out.sort(key=lambda row: str(row["Date"])[:10])
    return out


def bars_by_date(bars: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["Date"])[:10]: row for row in sorted_bars(bars)}


def scalar_price(row: dict[str, Any], key: str) -> float | None:
    return as_float(row.get(key))


def breadth_by_date(ohlcv: dict[str, list[dict[str, Any]]]) -> dict[str, float]:
    above: dict[str, int] = {}
    total: dict[str, int] = {}
    for ticker, bars in ohlcv.items():
        if ticker in INDEX_TICKERS:
            continue
        rows = sorted_bars(bars)
        closes = [float(row["Close"]) for row in rows]
        dates = [str(row["Date"])[:10] for row in rows]
        running = 0.0
        for idx, close in enumerate(closes):
            running += close
            if idx >= SMA_SHORT:
                running -= closes[idx - SMA_SHORT]
            if idx >= SMA_SHORT - 1:
                sma = running / SMA_SHORT
                day = dates[idx]
                total[day] = total.get(day, 0) + 1
                if close > sma:
                    above[day] = above.get(day, 0) + 1
    return {day: above.get(day, 0) / total[day] for day in total if total[day] > 0}


def index_agreement_by_date(
    ohlcv: dict[str, list[dict[str, Any]]],
    lookback: int = 20,
) -> dict[str, float]:
    positive: dict[str, int] = {}
    counts: dict[str, int] = {}
    for ticker in INDEX_TICKERS:
        rows = sorted_bars(ohlcv.get(ticker) or [])
        closes = [float(row["Close"]) for row in rows]
        dates = [str(row["Date"])[:10] for row in rows]
        for idx in range(lookback, len(closes)):
            day = dates[idx]
            counts[day] = counts.get(day, 0) + 1
            if closes[idx - lookback] > 0 and closes[idx] / closes[idx - lookback] - 1.0 > 0:
                positive[day] = positive.get(day, 0) + 1
    return {day: positive.get(day, 0) / counts[day] for day in counts if counts[day] > 0}


def adv20_dollar(bars: list[dict[str, Any]], entry_date: str) -> float | None:
    prior = [row for row in sorted_bars(bars) if str(row["Date"])[:10] < entry_date]
    if len(prior) < 20:
        return None
    dollars = []
    for row in prior[-20:]:
        close = scalar_price(row, "Close")
        volume = scalar_price(row, "Volume")
        if close is not None and volume is not None:
            dollars.append(close * volume)
    return sum(dollars) / len(dollars) if dollars else None


def target_from_trade(trade: dict[str, Any]) -> float | None:
    entry = as_float(trade.get("entry_price"))
    stop = as_float(trade.get("stop_price"))
    target_mult = as_float(trade.get("target_mult_used"))
    if entry is None or stop is None or target_mult is None:
        return None
    atr = (entry - stop) / ATR_STOP_MULT if ATR_STOP_MULT else None
    if atr is None or atr <= 0:
        return None
    return round(entry + target_mult * atr, 2)


def pnl_for_exit(entry: float, exit_price: float, shares: float) -> float:
    cost = exit_price * ROUND_TRIP_COST_PCT * shares
    return (exit_price - entry) * shares - cost


def simulate_chop_trail(
    trade: dict[str, Any],
    ticker_bars: list[dict[str, Any]],
    window_end: str,
) -> dict[str, Any]:
    entry_date = str(trade.get("entry_date") or "")[:10]
    entry = as_float(trade.get("entry_price"))
    stop = as_float(trade.get("stop_price"))
    shares = as_float(trade.get("shares"))
    if not entry_date or entry is None or stop is None or shares is None or shares <= 0:
        return {"simulated": False, "reason": "missing_entry_stop_or_shares"}
    atr = (entry - stop) / ATR_STOP_MULT if ATR_STOP_MULT else None
    if atr is None or atr <= 0:
        return {"simulated": False, "reason": "missing_atr"}

    bars = [row for row in sorted_bars(ticker_bars) if entry_date < str(row["Date"])[:10] <= window_end]
    if not bars:
        return {"simulated": False, "reason": "no_post_entry_bars"}

    adv = adv20_dollar(ticker_bars, entry_date)
    target = target_from_trade(trade)
    high_water = entry
    trailing_active = False
    eff_stop = stop
    trail_activated_date = None

    for row in bars:
        day = str(row["Date"])[:10]
        opn = scalar_price(row, "Open")
        high = scalar_price(row, "High")
        low = scalar_price(row, "Low")
        close = scalar_price(row, "Close")
        if opn is None or high is None or low is None or close is None:
            continue

        high_water = max(high_water, high)
        profit_in_atr = (high_water - entry) / atr
        if profit_in_atr >= TRAIL_TRIGGER_ATR_MULT:
            if not trailing_active:
                trail_activated_date = day
            trailing_active = True
            trail_stop = round(high_water - TRAIL_OFFSET_ATR_MULT * atr, 2)
            if trail_stop > eff_stop:
                eff_stop = trail_stop
            target = None

        if eff_stop and low <= eff_stop:
            raw = opn if opn < eff_stop else eff_stop
            exit_price = apply_stop_fill(opn, eff_stop, adv_dollar=adv, notional=raw * shares)
            return {
                "simulated": True,
                "exit_date": day,
                "exit_reason": "chop_trailing_stop" if trailing_active else "stop_before_trail_activation",
                "exit_raw_price": round(raw, 4),
                "exit_price": round(exit_price, 4),
                "pnl": round(pnl_for_exit(entry, exit_price, shares), 2),
                "trailing_active": trailing_active,
                "trail_activated_date": trail_activated_date,
                "max_high_water": round(high_water, 4),
                "final_stop": round(eff_stop, 4),
                "target_removed": target is None,
            }
        if target and high >= target:
            raw = opn if opn >= target else target
            exit_price = apply_target_fill(opn, target, adv_dollar=adv, notional=raw * shares)
            return {
                "simulated": True,
                "exit_date": day,
                "exit_reason": "target_before_trail_activation",
                "exit_raw_price": round(raw, 4),
                "exit_price": round(exit_price, 4),
                "pnl": round(pnl_for_exit(entry, exit_price, shares), 2),
                "trailing_active": trailing_active,
                "trail_activated_date": trail_activated_date,
                "max_high_water": round(high_water, 4),
                "final_stop": round(eff_stop, 4),
                "target_removed": target is None,
            }

    last = bars[-1]
    last_close = scalar_price(last, "Close")
    if last_close is None:
        return {"simulated": False, "reason": "missing_last_close"}
    exit_price = apply_target_fill(last_close, last_close, adv_dollar=adv, notional=last_close * shares)
    return {
        "simulated": True,
        "exit_date": str(last["Date"])[:10],
        "exit_reason": "forced_window_close",
        "exit_raw_price": round(last_close, 4),
        "exit_price": round(exit_price, 4),
        "pnl": round(pnl_for_exit(entry, exit_price, shares), 2),
        "trailing_active": trailing_active,
        "trail_activated_date": trail_activated_date,
        "max_high_water": round(high_water, 4),
        "final_stop": round(eff_stop, 4),
        "target_removed": target is None,
    }


def summarize_values(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "sum": 0.0, "mean": None, "median": None, "positive_rate": None}
    return {
        "n": len(values),
        "sum": round(sum(values), 2),
        "mean": round(sum(values) / len(values), 2),
        "median": round(float(median(values)), 2),
        "positive_rate": round(sum(1 for value in values if value > 0) / len(values), 4),
    }


def positive_delta_concentration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_ticker: dict[str, float] = defaultdict(float)
    for row in rows:
        delta = as_float(row.get("delta_pnl"))
        if delta is not None and delta > 0:
            by_ticker[row["ticker"]] += delta
    total = sum(by_ticker.values())
    if total <= 0:
        return {
            "positive_delta_sum": 0.0,
            "max_single_positive_delta_share": None,
            "positive_delta_hhi": None,
            "top_positive_delta_tickers": [],
            "passed": False,
        }
    shares = {ticker: value / total for ticker, value in by_ticker.items()}
    return {
        "positive_delta_sum": round(total, 2),
        "max_single_positive_delta_share": round(max(shares.values()), 6),
        "positive_delta_hhi": round(sum(share * share for share in shares.values()), 6),
        "top_positive_delta_tickers": [
            {"ticker": ticker, "delta_pnl": round(value, 2), "share": round(shares[ticker], 6)}
            for ticker, value in sorted(by_ticker.items(), key=lambda item: item[1], reverse=True)[:8]
        ],
        "passed": max(shares.values()) <= 0.50,
    }


def baseline_metrics() -> dict[str, Any]:
    protocol = read_json(BASELINE_PROTOCOL, {})
    aggregate = protocol.get("aggregate", {}).get("after", {})
    by_window = protocol.get("by_window", {})
    return {
        "baseline_protocol_file": repo_rel(BASELINE_PROTOCOL),
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "aggregate_expected_value_score": aggregate.get("expected_value_score"),
        "aggregate_total_pnl": aggregate.get("total_pnl"),
        "total_trade_count": aggregate.get("trade_count"),
        "min_survival_rate": aggregate.get("min_survival_rate"),
        "max_window_drawdown_pct": aggregate.get("max_drawdown_pct"),
        "windows": {
            label: (info.get("after") or {})
            for label, info in by_window.items()
        },
    }


def analyze_windows() -> dict[str, Any]:
    out_windows: dict[str, Any] = {}
    all_rows: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []

    for label, spec in WINDOWS.items():
        trade_payload = read_json(spec["trades"], {})
        snapshot = ohlcv_payload(read_json(spec["snapshot"], {}))
        spy_bars = sorted_bars(snapshot.get("SPY") or [])
        breadth = breadth_by_date(snapshot)
        agreement = index_agreement_by_date(snapshot)
        ticker_bars = {ticker: sorted_bars(bars) for ticker, bars in snapshot.items()}

        window_rows = []
        for trade in trade_payload.get("trades") or []:
            entry_date = str(trade.get("entry_date") or "")[:10]
            ticker = str(trade.get("ticker") or "").upper()
            baseline_pnl = as_float(trade.get("pnl"))
            if not entry_date or not ticker or baseline_pnl is None:
                unresolved.append({"window": label, "ticker": ticker, "reason": "missing_trade_field"})
                continue
            regime = rcs.regime_chop_from_spy_universe(
                spy_bars,
                entry_date,
                breadth=breadth.get(entry_date),
                index_agreement=agreement.get(entry_date),
            )
            regime_label = regime.get("regime_label") or "unknown"
            row = {
                "window": label,
                "ticker": ticker,
                "entry_date": entry_date,
                "baseline_exit_date": trade.get("exit_date"),
                "baseline_exit_reason": trade.get("exit_reason"),
                "baseline_pnl": round(baseline_pnl, 2),
                "addon_count": int(trade.get("addon_count") or 0),
                "regime_label": regime_label,
                "p_choppy_range": regime.get("p_choppy_range"),
                "regime_exposure_scalar": regime.get("exposure_scalar"),
                "policy_applied": regime_label == "choppy_range",
            }
            if row["policy_applied"]:
                sim = simulate_chop_trail(trade, ticker_bars.get(ticker) or [], spec["end"])
                row["simulation"] = sim
                if sim.get("simulated"):
                    row["after_pnl"] = sim["pnl"]
                    row["after_exit_date"] = sim["exit_date"]
                    row["after_exit_reason"] = sim["exit_reason"]
                    row["delta_pnl"] = round(sim["pnl"] - baseline_pnl, 2)
                    row["trail_activated"] = bool(sim.get("trailing_active"))
                else:
                    row["after_pnl"] = round(baseline_pnl, 2)
                    row["after_exit_date"] = trade.get("exit_date")
                    row["after_exit_reason"] = trade.get("exit_reason")
                    row["delta_pnl"] = 0.0
                    row["trail_activated"] = False
                    unresolved.append(
                        {
                            "window": label,
                            "ticker": ticker,
                            "entry_date": entry_date,
                            "reason": sim.get("reason", "simulation_failed"),
                        }
                    )
            else:
                row["after_pnl"] = round(baseline_pnl, 2)
                row["after_exit_date"] = trade.get("exit_date")
                row["after_exit_reason"] = trade.get("exit_reason")
                row["delta_pnl"] = 0.0
                row["trail_activated"] = False
            window_rows.append(row)
            all_rows.append(row)

        deltas = [float(row["delta_pnl"]) for row in window_rows]
        affected = [row for row in window_rows if row["policy_applied"]]
        trail_active = [row for row in affected if row.get("trail_activated")]
        out_windows[label] = {
            "start": spec["start"],
            "end": spec["end"],
            "trade_count": len(window_rows),
            "affected_choppy_trade_count": len(affected),
            "trail_activated_trade_count": len(trail_active),
            "affected_addon_trade_count": sum(1 for row in affected if row.get("addon_count", 0) > 0),
            "baseline_total_pnl": round(sum(float(row["baseline_pnl"]) for row in window_rows), 2),
            "after_total_pnl": round(sum(float(row["after_pnl"]) for row in window_rows), 2),
            "delta_pnl": round(sum(deltas), 2),
            "delta_summary": summarize_values([float(row["delta_pnl"]) for row in affected]),
            "regime_counts": dict(Counter(row["regime_label"] for row in window_rows)),
            "after_exit_reason_counts": dict(Counter(row["after_exit_reason"] for row in window_rows)),
        }

    aggregate_delta = round(sum(float(row["delta_pnl"]) for row in all_rows), 2)
    affected_rows = [row for row in all_rows if row["policy_applied"]]
    trail_rows = [row for row in affected_rows if row.get("trail_activated")]
    concentration = positive_delta_concentration(affected_rows)
    windows_improved = sum(1 for info in out_windows.values() if info["delta_pnl"] > 0)
    windows_regressed = sum(1 for info in out_windows.values() if info["delta_pnl"] < 0)
    failure_reasons: list[str] = []
    if len(affected_rows) < 5:
        failure_reasons.append("too_few_choppy_trades")
    if len(trail_rows) < 3:
        failure_reasons.append("too_few_trail_activations")
    if aggregate_delta <= 0:
        failure_reasons.append("aggregate_pnl_delta_not_positive")
    if windows_improved < 2:
        failure_reasons.append("fewer_than_two_windows_improved")
    if windows_regressed > 0:
        failure_reasons.append("window_pnl_regression")
    if not concentration["passed"]:
        failure_reasons.append("positive_delta_concentration_failed")
    failure_reasons.append("fixed_entry_replay_not_shared_production_policy")
    failure_reasons.append("full_strategy_ev_and_drawdown_not_recomputed")

    observed_only_lead = (
        aggregate_delta > 0
        and windows_improved >= 2
        and windows_regressed == 0
        and len(affected_rows) >= 5
        and len(trail_rows) >= 3
        and concentration["passed"]
    )
    return {
        "windows": out_windows,
        "trades": all_rows,
        "sample_rows": all_rows[:20],
        "unresolved": unresolved,
        "aggregate": {
            "trade_count": len(all_rows),
            "affected_choppy_trade_count": len(affected_rows),
            "trail_activated_trade_count": len(trail_rows),
            "affected_addon_trade_count": sum(1 for row in affected_rows if row.get("addon_count", 0) > 0),
            "baseline_total_pnl": round(sum(float(row["baseline_pnl"]) for row in all_rows), 2),
            "after_total_pnl": round(sum(float(row["after_pnl"]) for row in all_rows), 2),
            "delta_pnl": aggregate_delta,
            "affected_delta_summary": summarize_values([float(row["delta_pnl"]) for row in affected_rows]),
            "trail_active_delta_summary": summarize_values([float(row["delta_pnl"]) for row in trail_rows]),
            "windows_improved": windows_improved,
            "windows_regressed": windows_regressed,
            "positive_delta_concentration": concentration,
            "regime_counts": dict(Counter(row["regime_label"] for row in all_rows)),
        },
        "observed_only_lead": observed_only_lead,
        "failed_reasons": failure_reasons,
    }


def calibration(prediction: dict[str, Any], success: bool, failed_reasons: list[str]) -> dict[str, Any]:
    probability = float(prediction.get("success_probability") or 0.0)
    actual = 1.0 if success else 0.0
    predicted_modes = list(prediction.get("main_failure_modes") or [])
    mode_map = {
        "trailing_still_cuts_winners": {
            "aggregate_pnl_delta_not_positive",
            "window_pnl_regression",
        },
        "chop_label_not_exit_predictive": {
            "aggregate_pnl_delta_not_positive",
            "fewer_than_two_windows_improved",
        },
        "too_few_choppy_trades": {
            "too_few_choppy_trades",
            "too_few_trail_activations",
        },
        "fixed_entry_not_portfolio_replay": {
            "fixed_entry_replay_not_shared_production_policy",
            "full_strategy_ev_and_drawdown_not_recomputed",
        },
    }
    hit = [
        mode
        for mode in predicted_modes
        if mode_map.get(mode, set()).intersection(failed_reasons)
    ]
    return {
        "predicted_success_probability": probability,
        "actual_success": bool(success),
        "brier_score": round((probability - actual) ** 2, 6),
        "predicted_failure_modes": predicted_modes,
        "failed_reasons": failed_reasons,
        "predicted_failure_modes_hit": hit,
    }


def build_payload() -> dict[str, Any]:
    prediction = load_ticket_prediction()
    before = baseline_metrics()
    analysis = analyze_windows()
    observed_lead = bool(analysis["observed_only_lead"])
    decision = (
        "observed_only_positive_lead_not_promoted"
        if observed_lead
        else "rejected_regime_conditional_trailing_exit_scout"
    )
    status = "observed_only_positive_lead" if observed_lead else "rejected"
    if observed_lead:
        why = (
            "The fixed-entry chop-only trailing scout improved the affected "
            "trade set, but it is not accepted alpha because it is not a shared "
            "production/backtest exit policy and does not recompute full "
            "strategy EV, drawdown, cash, slots, or addon paths."
        )
    else:
        why = (
            "The shared entry-time chop label did not rescue ATR trailing. The "
            "conditional rule either had too few activations or failed the "
            "aggregate/window/concentration checks, while the replay remains "
            "fixed-entry only."
        )

    after = dict(before)
    after["fixed_entry_after_total_pnl"] = analysis["aggregate"]["after_total_pnl"]
    delta = {
        "canonical_expected_value_score_delta": 0.0,
        "canonical_total_pnl_delta": 0.0,
        "fixed_entry_total_pnl_delta": analysis["aggregate"]["delta_pnl"],
        "fixed_entry_affected_choppy_trade_count": analysis["aggregate"]["affected_choppy_trade_count"],
        "fixed_entry_trail_activated_trade_count": analysis["aggregate"]["trail_activated_trade_count"],
        "fixed_entry_windows_improved": analysis["aggregate"]["windows_improved"],
        "fixed_entry_windows_regressed": analysis["aggregate"]["windows_regressed"],
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "status": status,
        "lane": "alpha_search",
        "owner": OWNER,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": observed_lead,
        "hypothesis": HYPOTHESIS,
        "change_summary": (
            "Fixed-entry replay of ATR trailing only for trades whose entry-day "
            "shared regime_chop_state label is choppy_range; no strategy code "
            "or production path changed."
        ),
        "change_type": CHANGE_TYPE,
        "implementation_mode": "fixed_entry_replay_scout",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": "experiment.py new found no strong near-neighbor; novelty override axis recorded for the exp-020 reopen condition.",
                "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
                "important_boundary": "This is not a trail trigger/offset sweep and not an accepted production exit rule.",
            },
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": (
                "Fixed-entry aggregate PnL positive, at least two windows "
                "improved, no window regression, affected/trail samples not "
                "too thin, and positive delta not concentrated. Positive "
                "results are leads only until shared Gate 1-4 policy replay."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "trail_trigger_atr_mult": TRAIL_TRIGGER_ATR_MULT,
            "trail_offset_atr_mult": TRAIL_OFFSET_ATR_MULT,
            "regime_gate": "entry_date regime_chop_state.regime_label == choppy_range",
            "baseline_protocol": repo_rel(BASELINE_PROTOCOL),
            "windows": {
                label: {
                    "start": spec["start"],
                    "end": spec["end"],
                    "trades": repo_rel(spec["trades"]),
                    "snapshot": repo_rel(spec["snapshot"]),
                }
                for label, spec in WINDOWS.items()
            },
        },
        "gate1": {
            "baseline_loaded": BASELINE_PROTOCOL.exists() and BASELINE_RESULT.exists(),
            "baseline_metrics": before,
        },
        "gate2": {
            "passed": True,
            "runtime_fields_checked": [
                "entry_date",
                "target_price reconstructed from stop_price and target_mult_used",
                "stop_price",
                "shares",
                "ticker OHLCV",
                "SPY OHLCV",
                "regime_chop_state",
            ],
            "target_price_note": (
                "Canonical closed trade rows do not store target_price; the "
                "runner reconstructs it from entry_price, stop_price, "
                "ATR_STOP_MULT, and target_mult_used for fixed-entry replay."
            ),
        },
        "gate3": {
            "passed": True,
            "new_core_filter_added": False,
            "baseline_min_survival_rate": before["min_survival_rate"],
            "note": "No entry filter, ranking, sizing, candidate generation, or production exit rule changed.",
        },
        "gate4": {
            "passed": False,
            "observed_only_lead": observed_lead,
            "decision": decision,
            "failed_reasons": analysis["failed_reasons"],
            "acceptance_checks": {
                "aggregate_delta_pnl_positive": analysis["aggregate"]["delta_pnl"] > 0,
                "windows_improved": analysis["aggregate"]["windows_improved"],
                "windows_regressed": analysis["aggregate"]["windows_regressed"],
                "affected_choppy_trade_count": analysis["aggregate"]["affected_choppy_trade_count"],
                "trail_activated_trade_count": analysis["aggregate"]["trail_activated_trade_count"],
                "positive_delta_concentration": analysis["aggregate"]["positive_delta_concentration"],
            },
            "before_after_strategy_delta": {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "max_drawdown_pct": 0.0,
            },
            "lead_limitations": [
                "Fixed-entry replay only; not a full strategy cash/slot/addon replay.",
                "No shared production/backtest exit helper was implemented.",
                "Full strategy EV and drawdown were not recomputed.",
            ],
        },
        "before_metrics": before,
        "after_metrics": after,
        "delta_metrics": delta,
        "analysis": analysis,
        "production_impact": {
            "trade_enabled": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "entry_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_rules_changed": False,
            "orders_changed": False,
            "daily_snapshot_exposed": False,
            "replay_only": True,
            "live_ready": False,
            "live_realism_evaluated": False,
            "parity_note": (
                "This runner is a fixed-entry diagnostic. A positive result "
                "would require a separate shared production/backtest exit "
                "policy and canonical Gate 1-4 before retention."
            ),
        },
        "calibration": calibration(prediction, observed_lead, analysis["failed_reasons"]),
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retry ATR trailing by sweeping trigger/offset, "
                "choppy_range probability thresholds, static-vs-trailing "
                "toggles, MFE giveback thresholds, or target trims on these "
                "same canonical windows."
            ),
            "new_evidence_required": (
                "A valid retry needs a shared exit lifecycle policy tested "
                "through full strategy Gate 1-4, or materially new forward live "
                "giveback rows with slot-reuse and winner-collateral accounting."
            ),
        },
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "related_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(BASELINE_PROTOCOL),
            "experiments/logs/exp-20260623-020.json",
            "experiments/logs/exp-20260622-017.json",
            "experiments/logs/exp-20260623-003.json",
        ],
        "reproduction_command": RUNNER_COMMAND,
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "lane": payload["lane"],
        "owner": payload["owner"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "observed_only_lead": payload["observed_only_lead"],
        "hypothesis": payload["hypothesis"],
        "change_summary": payload["change_summary"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "single_causal_variable": payload["single_causal_variable"],
        "causal_components": payload["causal_components"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "new_evidence_axis": payload["new_evidence_axis"],
        "prediction": payload["prediction"],
        "pre_run_questions": payload["pre_run_questions"],
        "parameters": payload["parameters"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "analysis": {
            "aggregate": payload["analysis"]["aggregate"],
            "windows": payload["analysis"]["windows"],
            "unresolved": payload["analysis"]["unresolved"][:20],
        },
        "production_impact": payload["production_impact"],
        "calibration": payload["calibration"],
        "post_run_reflection": payload["post_run_reflection"],
        "related_files": payload["related_files"],
        "anti_js": payload["anti_js"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "reproduction_command": payload["reproduction_command"],
    }


def build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Trades | Choppy | Trail Active | Delta PnL |",
        "|---|---:|---:|---:|---:|",
    ]
    for label, info in payload["analysis"]["windows"].items():
        rows.append(
            "| {label} | {trades} | {choppy} | {active} | ${delta:,.2f} |".format(
                label=label,
                trades=info["trade_count"],
                choppy=info["affected_choppy_trade_count"],
                active=info["trail_activated_trade_count"],
                delta=info["delta_pnl"],
            )
        )
    aggregate = payload["analysis"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: regime-conditional chop trailing exit",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Production behavior changed: no",
            "- Shared policy promoted: no",
            "",
            "## Result",
            "",
            *rows,
            "",
            f"- Aggregate fixed-entry delta PnL: `${aggregate['delta_pnl']:,.2f}`",
            f"- Affected choppy trades: `{aggregate['affected_choppy_trade_count']}`",
            f"- Trail activations: `{aggregate['trail_activated_trade_count']}`",
            f"- Failed reasons: `{', '.join(payload['gate4']['failed_reasons'])}`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)} for path in files},
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)

    registry_result = {
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": payload["observed_only_lead"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result=registry_result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "change_type": payload["change_type"],
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": payload["single_causal_variable"],
            "changed_variable": payload["changed_variable"],
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "new_evidence_axis": payload["new_evidence_axis"],
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
            "fixed_entry_total_pnl_delta": payload["analysis"]["aggregate"]["delta_pnl"],
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "analysis_summary": payload["analysis"]["aggregate"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "allowed_write_scope": ALLOWED_WRITE_SCOPE,
            "related_files": payload["related_files"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "observed_only_lead": payload["observed_only_lead"],
                "fixed_entry_delta_pnl": payload["analysis"]["aggregate"]["delta_pnl"],
                "affected_choppy_trade_count": payload["analysis"]["aggregate"]["affected_choppy_trade_count"],
                "trail_activated_trade_count": payload["analysis"]["aggregate"]["trail_activated_trade_count"],
                "windows": {
                    key: value["delta_pnl"]
                    for key, value in payload["analysis"]["windows"].items()
                },
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
