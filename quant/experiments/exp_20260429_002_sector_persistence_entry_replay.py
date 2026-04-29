"""exp-20260429-002: sector-persistence entry replay.

Alpha search. Prior shadow work found sector-relative persistence candidates
with positive mid/old forward returns, but those marks were not slot-aware
portfolio trades. This runner tests one fixed production-like entry source
through the real BacktestEngine mechanics without changing production defaults.
"""

from __future__ import annotations

import json
import logging
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import feature_layer as fl_module  # noqa: E402
import signal_engine as se_module  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from constants import ATR_STOP_MULT  # noqa: E402
from data_layer import get_universe  # noqa: E402
from risk_engine import SECTOR_MAP  # noqa: E402


EXPERIMENT_ID = "exp-20260429-002"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260429_002_sector_persistence_entry_replay.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"

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

STRATEGY = "sector_persistence_long"
MIN_SECTOR_RS_20D = 0.015
MIN_SECTOR_RS_60D = 0.025
MIN_TICKER_RS_VS_SECTOR_20D = 0.0
MIN_VOLUME_RATIO = 0.85
TOP_SECTORS_PER_DAY = 2


_original_compute_features = fl_module.compute_features
_original_generate_signals = se_module.generate_signals


def _safe_float(value):
    if value is None:
        return None
    if hasattr(value, "item"):
        value = value.item()
    try:
        return float(value)
    except Exception:
        return None


def _compute_features_with_sector_persistence(ticker, ohlcv_data, earnings_data):
    features = _original_compute_features(ticker, ohlcv_data, earnings_data)
    if features is None or ohlcv_data is None or len(ohlcv_data) < 61:
        return features

    close = _safe_float(ohlcv_data["Close"].iloc[-1])
    close_20 = _safe_float(ohlcv_data["Close"].iloc[-21])
    close_60 = _safe_float(ohlcv_data["Close"].iloc[-61])
    ma50 = _safe_float(ohlcv_data["Close"].rolling(50).mean().iloc[-1])
    avg_vol_20 = _safe_float(ohlcv_data["Volume"].iloc[-21:-1].mean())
    volume = _safe_float(ohlcv_data["Volume"].iloc[-1])
    if not close:
        return features

    features["sector_persistence_ret20"] = (
        round(close / close_20 - 1.0, 6) if close_20 else None
    )
    features["sector_persistence_ret60"] = (
        round(close / close_60 - 1.0, 6) if close_60 else None
    )
    features["sector_persistence_above_50ma"] = bool(ma50 and close > ma50)
    features["sector_persistence_volume_ratio"] = (
        round(volume / avg_vol_20, 4) if volume and avg_vol_20 else None
    )
    return features


def _avg(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def _generate_with_sector_persistence(
    features_dict,
    market_context=None,
    enabled_strategies=None,
    breakout_max_pullback_from_52w_high=None,
):
    base = _original_generate_signals(
        features_dict,
        market_context=market_context,
        enabled_strategies=enabled_strategies,
        breakout_max_pullback_from_52w_high=breakout_max_pullback_from_52w_high,
    )
    existing_tickers = {sig.get("ticker") for sig in base}

    spy = features_dict.get("SPY") or {}
    spy_ret20 = spy.get("sector_persistence_ret20")
    spy_ret60 = spy.get("sector_persistence_ret60")
    if spy_ret20 is None or spy_ret60 is None:
        return base

    by_sector = {}
    for ticker, features in (features_dict or {}).items():
        sector = SECTOR_MAP.get(ticker, "Unknown")
        if sector in {"Unknown", "ETF", "Commodities"}:
            continue
        by_sector.setdefault(sector, []).append(features)

    sector_rows = []
    for sector, rows in by_sector.items():
        ret20 = _avg([row.get("sector_persistence_ret20") for row in rows])
        ret60 = _avg([row.get("sector_persistence_ret60") for row in rows])
        if ret20 is None or ret60 is None:
            continue
        rs20 = ret20 - spy_ret20
        rs60 = ret60 - spy_ret60
        if rs20 >= MIN_SECTOR_RS_20D and rs60 >= MIN_SECTOR_RS_60D:
            sector_rows.append((sector, rs20, rs60, ret20))
    sector_rows.sort(key=lambda row: (row[1], row[2]), reverse=True)
    active_sectors = {
        sector for sector, _rs20, _rs60, _ret20 in sector_rows[:TOP_SECTORS_PER_DAY]
    }
    if not active_sectors:
        return base

    sector_ret20 = {
        sector: _avg([
            row.get("sector_persistence_ret20")
            for row in rows
            if row.get("sector_persistence_ret20") is not None
        ])
        for sector, rows in by_sector.items()
    }

    extra = []
    for ticker, features in (features_dict or {}).items():
        if ticker in existing_tickers:
            continue
        sector = SECTOR_MAP.get(ticker, "Unknown")
        if sector not in active_sectors:
            continue
        close = features.get("close")
        atr = features.get("atr")
        ret20 = features.get("sector_persistence_ret20")
        vol_ratio = features.get("sector_persistence_volume_ratio")
        if not close or not atr or ret20 is None:
            continue
        ticker_vs_sector = ret20 - (sector_ret20.get(sector) or 0.0)
        if ticker_vs_sector < MIN_TICKER_RS_VS_SECTOR_20D:
            continue
        if not features.get("sector_persistence_above_50ma"):
            continue
        if vol_ratio is None or vol_ratio < MIN_VOLUME_RATIO:
            continue
        dte = features.get("days_to_earnings")
        if dte is not None and dte <= 3:
            continue
        if atr / close > 0.07:
            continue

        confidence = 0.89
        if ticker_vs_sector >= 0.03:
            confidence = 0.94
        if ticker_vs_sector >= 0.06:
            confidence = 1.0
        extra.append({
            "ticker": ticker,
            "strategy": STRATEGY,
            "entry_price": round(close, 2),
            "stop_price": round(close - ATR_STOP_MULT * atr, 2),
            "confidence_score": confidence,
            "entry_note": (
                "Execute next-day open; cancel if open > entry_price x 1.015 "
                "or open < entry_price x 0.980"
            ),
            "conditions_met": {
                "sector": sector,
                "sector_rs_20d": round(
                    (sector_ret20.get(sector) or 0.0) - spy_ret20, 6
                ),
                "sector_rs_60d": next(
                    round(row[2], 6) for row in sector_rows if row[0] == sector
                ),
                "ticker_rs_vs_sector_20d": round(ticker_vs_sector, 6),
                "volume_ratio": vol_ratio,
                "above_50ma": True,
                "pct_from_52w_high": features.get("pct_from_52w_high"),
            },
        })

    return sorted(base + extra, key=lambda sig: sig.get("confidence_score", 0), reverse=True)


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    entry = result.get("entry_execution_attribution") or {}
    cap_eff = result.get("capital_efficiency") or {}
    by_strategy = result.get("by_strategy", {})
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "strategy_vs_spy_pct": benchmarks.get("strategy_vs_spy_pct"),
        "strategy_vs_qqq_pct": benchmarks.get("strategy_vs_qqq_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
        "tail_loss_share": result.get("tail_loss_share"),
        "pnl_per_trade_usd": cap_eff.get("pnl_per_trade_usd"),
        "pnl_per_calendar_slot_day_usd": cap_eff.get("pnl_per_calendar_slot_day_usd"),
        "entry_reason_counts": entry.get("reason_counts", {}),
        "sector_persistence_strategy": by_strategy.get(STRATEGY, {}),
        "by_strategy": by_strategy,
    }


def _delta(after: dict, before: dict) -> dict:
    out = {}
    for key, before_value in before.items():
        after_value = after.get(key)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            out[key] = round(after_value - before_value, 6)
        else:
            out[key] = None
    return out


def _run_window(universe: list[str], cfg: dict, enabled: bool) -> dict:
    if enabled:
        fl_module.compute_features = _compute_features_with_sector_persistence
        se_module.generate_signals = _generate_with_sector_persistence
    else:
        fl_module.compute_features = _original_compute_features
        se_module.generate_signals = _original_generate_signals
    try:
        result = BacktestEngine(
            universe=universe,
            start=cfg["start"],
            end=cfg["end"],
            config={"REGIME_AWARE_EXIT": True},
            replay_llm=False,
            replay_news=False,
            data_dir=str(REPO_ROOT / "data"),
            ohlcv_snapshot_path=str(REPO_ROOT / cfg["snapshot"]),
        ).run()
    finally:
        fl_module.compute_features = _original_compute_features
        se_module.generate_signals = _original_generate_signals
    if "error" in result:
        raise RuntimeError(result["error"])
    return _metrics(result)


def run_experiment() -> dict:
    logging.getLogger().setLevel(logging.WARNING)
    universe = sorted(get_universe())
    rows = []
    by_window = OrderedDict()
    for window, cfg in WINDOWS.items():
        before = _run_window(universe, cfg, enabled=False)
        after = _run_window(universe, cfg, enabled=True)
        delta = _delta(after, before)
        by_window[window] = {"before": before, "after": after, "delta": delta}
        rows.append({
            "window": window,
            "start": cfg["start"],
            "end": cfg["end"],
            "snapshot": cfg["snapshot"],
            "state_note": cfg["state_note"],
            "before": before,
            "after": after,
            "delta": delta,
        })
        print(
            f"[{window}] EV {before['expected_value_score']} -> "
            f"{after['expected_value_score']} delta={delta['expected_value_score']} "
            f"PnL {before['total_pnl']} -> {after['total_pnl']} "
            f"trades {before['trade_count']} -> {after['trade_count']} "
            f"sector_trades={after['sector_persistence_strategy'].get('trade_count', 0)}"
        )

    baseline_total_pnl = round(sum(v["before"]["total_pnl"] for v in by_window.values()), 2)
    total_pnl_delta = round(sum(v["delta"]["total_pnl"] for v in by_window.values()), 2)
    aggregate = {
        "expected_value_score_delta_sum": round(
            sum(v["delta"]["expected_value_score"] for v in by_window.values()),
            6,
        ),
        "total_pnl_delta_sum": total_pnl_delta,
        "baseline_total_pnl_sum": baseline_total_pnl,
        "total_pnl_delta_pct": (
            round(total_pnl_delta / baseline_total_pnl, 6)
            if baseline_total_pnl else None
        ),
        "windows_improved": sum(
            1 for v in by_window.values() if v["delta"]["expected_value_score"] > 0
        ),
        "windows_regressed": sum(
            1 for v in by_window.values() if v["delta"]["expected_value_score"] < 0
        ),
        "max_drawdown_delta_max": max(
            v["delta"]["max_drawdown_pct"] for v in by_window.values()
        ),
        "trade_count_delta_sum": sum(v["delta"]["trade_count"] for v in by_window.values()),
        "win_rate_delta_min": min(v["delta"]["win_rate"] for v in by_window.values()),
        "sector_persistence_trade_count": sum(
            (v["after"].get("sector_persistence_strategy") or {}).get("trade_count", 0)
            for v in by_window.values()
        ),
    }
    accepted = (
        aggregate["windows_improved"] >= 2
        and aggregate["windows_regressed"] == 0
        and (
            aggregate["expected_value_score_delta_sum"] > 0.10
            or aggregate["total_pnl_delta_pct"] > 0.05
            or aggregate["max_drawdown_delta_max"] < -0.01
            or (aggregate["trade_count_delta_sum"] > 0 and aggregate["win_rate_delta_min"] >= 0)
        )
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "accepted" if accepted else "rejected",
        "decision": "accepted" if accepted else "rejected",
        "lane": "alpha_search",
        "change_type": "entry_source_replay",
        "hypothesis": (
            "Sector-relative persistence candidates may add executable alpha "
            "when replayed through real slot, gap-cancel, sizing, add-on, and exit mechanics."
        ),
        "why_tested": (
            "LLM soft ranking remains sample-limited, and recent global allocation "
            "and simple universe-expansion attempts were rejected. Prior shadow "
            "audit showed positive mid/old 10-20 day forward marks, but no "
            "slot-aware portfolio replay."
        ),
        "parameters": {
            "single_causal_variable": "enable sector_persistence_long entry source",
            "strategy": STRATEGY,
            "sector_persistence_trigger": {
                "top_sectors_per_day": TOP_SECTORS_PER_DAY,
                "sector_equal_weight_20d_return_minus_spy_gte": MIN_SECTOR_RS_20D,
                "sector_equal_weight_60d_return_minus_spy_gte": MIN_SECTOR_RS_60D,
                "ticker_20d_return_minus_sector_20d_gte": MIN_TICKER_RS_VS_SECTOR_20D,
                "close_above_50d_ma": True,
                "volume_ratio_gte": MIN_VOLUME_RATIO,
            },
            "locked_variables": [
                "production A/B signal generation",
                "risk multipliers",
                "MAX_POSITION_PCT=0.40",
                "MAX_POSITIONS=5",
                "MAX_PORTFOLIO_HEAT=0.08",
                "MAX_PER_SECTOR=2",
                "upside/adverse gap cancels",
                "day-2 add-on trigger/fraction/cap",
                "all existing exits",
                "scarce-slot breakout deferral",
                "LLM/news replay",
                "earnings strategy",
            ],
        },
        "date_range": {
            "start": WINDOWS["late_strong"]["start"],
            "end": WINDOWS["late_strong"]["end"],
        },
        "secondary_windows": [
            {"start": WINDOWS["mid_weak"]["start"], "end": WINDOWS["mid_weak"]["end"]},
            {"start": WINDOWS["old_thin"]["start"], "end": WINDOWS["old_thin"]["end"]},
        ],
        "market_regime_summary": {
            window: cfg["state_note"] for window, cfg in WINDOWS.items()
        },
        "before_metrics": {
            window: values["before"] for window, values in by_window.items()
        },
        "after_metrics": {
            window: values["after"] for window, values in by_window.items()
        },
        "delta_metrics": {
            **{window: values["delta"] for window, values in by_window.items()},
            "aggregate": aggregate,
            "gate4_basis": (
                "Accepted only if majority windows improve without regression and "
                "one materiality gate passes."
                if accepted else
                "Rejected because the executable sector-persistence entry source "
                "did not improve a majority of fixed windows without regression."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft-ranking data is still insufficient, so this tested a "
                "deterministic, production-replayable entry alpha instead."
            ),
        },
        "history_guardrails": {
            "not_repeating_addon_threshold_tuning": True,
            "not_repeating_global_slot_count": True,
            "not_repeating_simple_etf_expansion": True,
            "not_repeating_ohlcv_only_pullback_reclaim": True,
            "mechanism_family": "sector-relative persistence entry replay",
        },
        "rows": rows,
        "rejection_reason": (
            None if accepted else
            "Sector-relative persistence did not survive slot-aware portfolio replay."
        ),
        "next_retry_requires": [
            "Do not promote sector-persistence as an entry source unless a future replay has an orthogonal state discriminator.",
            "A valid retry needs external universe breadth or event context, not nearby threshold nudges.",
            "If accepted in a later run, implement as shared production/backtest policy before promotion.",
        ],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    for path in (OUT_JSON, LOG_JSON, TICKET_JSON):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    return payload


if __name__ == "__main__":
    result = run_experiment()
    agg = result["delta_metrics"]["aggregate"]
    print(
        f"{EXPERIMENT_ID} {result['decision']} "
        f"EV_delta_sum={agg['expected_value_score_delta_sum']} "
        f"PnL_delta={agg['total_pnl_delta_sum']} "
        f"windows={agg['windows_improved']}/{len(WINDOWS)}"
    )
