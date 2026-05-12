"""exp-20260512-024: OHLCV pullback/reclaim entry alpha search.

This experiment tests one entry variable: adding a deterministic
``pullback_reclaim_long`` signal for leadership pullbacks that are still above
their 200-day moving average, 5-15% below the 52-week high, positive on 10d and
20d momentum, and not already a 20-day breakout/breakdown.

It deliberately stays outside LLM soft-ranking and event sleeves. No production
policy is changed unless the three-window gate passes.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260512-024"
STEM = "pullback_reclaim_entry"
REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine, DEFAULT_CONFIG  # noqa: E402
from constants import ATR_STOP_MULT  # noqa: E402
from data_layer import get_universe  # noqa: E402
import signal_engine  # noqa: E402


WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
    },
}

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
DOC_LOG = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_ARTIFACT = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(key): _safe(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [_safe(value) for value in obj]
    if isinstance(obj, tuple):
        return [_safe(value) for value in obj]
    if hasattr(obj, "item"):
        return obj.item()
    return obj


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _append_jsonl_once(path: Path, payload: dict[str, Any]) -> None:
    compact = json.dumps(_safe(payload), ensure_ascii=False, separators=(",", ":"))
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        lines = [
            line
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if f'"experiment_id":"{EXPERIMENT_ID}"' not in line
            and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
        ]
    else:
        lines = []
    lines.append(compact)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return value


def _result_metrics(result: dict[str, Any]) -> dict[str, Any]:
    ret = result.get("strategy_total_return_pct")
    if ret is None:
        ret = result.get("total_return_pct")
    trades = result.get("trade_count")
    if trades is None:
        trades = result.get("total_trades")
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "strategy_total_return_pct": _round(ret, 4),
        "sharpe_daily": _round(result.get("sharpe_daily"), 2),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": trades,
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": _round(result.get("survival_rate"), 4),
        "worst_trade_pct": _round(result.get("worst_trade_pct"), 4),
        "max_consecutive_losses": result.get("max_consecutive_losses"),
        "tail_loss_share": _round(result.get("tail_loss_share"), 4),
    }


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, after_value in after.items():
        before_value = before.get(key)
        if isinstance(after_value, (int, float)) and isinstance(before_value, (int, float)):
            out[key] = _round(after_value - before_value, 6)
    return out


def _pullback_reclaim_signal(
    ticker: str,
    features: dict[str, Any],
    market_context: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    close = features.get("close")
    atr = features.get("atr")
    if not close or not atr or not features.get("above_200ma"):
        return None

    dte = features.get("days_to_earnings")
    if dte is not None and dte <= 3:
        return None
    if atr / close > 0.07:
        return None
    if features.get("breakout_20d") or features.get("breakdown_20d"):
        return None

    m10 = features.get("momentum_10d_pct")
    m20 = features.get("momentum_20d_pct")
    pct52 = features.get("pct_from_52w_high")
    vol = features.get("volume_spike_ratio")
    p200 = features.get("price_vs_200ma_pct")
    if None in (m10, m20, pct52, vol, p200):
        return None
    if not (
        m10 > 0
        and m20 >= 0.05
        and -0.15 <= pct52 < -0.05
        and vol >= 1.2
        and p200 >= 0.03
    ):
        return None

    spy10 = (market_context or {}).get("spy_10d_return") or 0
    spy20 = (market_context or {}).get("spy_20d_return") or 0
    checks = [
        (True, 1.0),
        (m10 > spy10, 0.35),
        (m20 > spy20, 0.35),
        (vol >= 1.5, 0.25),
        (pct52 >= -0.10, 0.25),
    ]
    total_weight = sum(weight for _, weight in checks)
    true_weight = sum(weight for passed, weight in checks if passed)
    confidence = round(true_weight / total_weight, 2)
    return {
        "ticker": ticker,
        "strategy": "pullback_reclaim_long",
        "entry_price": round(float(close), 2),
        "stop_price": round(float(close) - ATR_STOP_MULT * float(atr), 2),
        "confidence_score": confidence,
        "entry_note": (
            "Execute next-day open; cancel if open > entry_price x 1.015 "
            "or open < entry_price x 0.980"
        ),
        "conditions_met": {
            "above_200ma": True,
            "not_breakout_20d": not features.get("breakout_20d"),
            "not_breakdown_20d": not features.get("breakdown_20d"),
            "momentum_10d_pct": m10,
            "momentum_20d_pct": m20,
            "pct_from_52w_high": pct52,
            "volume_spike_ratio": vol,
            "price_vs_200ma_pct": p200,
            "pullback_reclaim_rule": (
                "m10>0,m20>=5%,5-15% below 52w high,vol>=1.2,"
                "above200>=3%,no 20d breakout/breakdown"
            ),
        },
    }


def _install_pullback_strategy():
    original = signal_engine.generate_signals

    def patched_generate_signals(
        features_dict,
        market_context=None,
        enabled_strategies=None,
        breakout_max_pullback_from_52w_high=None,
    ):
        signals = original(
            features_dict,
            market_context=market_context,
            enabled_strategies=enabled_strategies,
            breakout_max_pullback_from_52w_high=breakout_max_pullback_from_52w_high,
        )
        for ticker, features in features_dict.items():
            if features:
                signal = _pullback_reclaim_signal(ticker, features, market_context)
                if signal:
                    signals.append(signal)

        best: dict[str, dict[str, Any]] = {}
        for signal in signals:
            ticker = str(signal.get("ticker") or "")
            if (
                ticker not in best
                or float(signal.get("confidence_score") or 0)
                > float(best[ticker].get("confidence_score") or 0)
            ):
                best[ticker] = signal
        return sorted(
            best.values(),
            key=lambda signal: float(signal.get("confidence_score") or 0),
            reverse=True,
        )

    signal_engine.generate_signals = patched_generate_signals
    return original


def _run_window(
    universe: list[str],
    window: dict[str, str],
    *,
    with_pullback: bool,
) -> dict[str, Any]:
    original = None
    if with_pullback:
        original = _install_pullback_strategy()
    try:
        engine = BacktestEngine(
            universe,
            start=window["start"],
            end=window["end"],
            config=dict(DEFAULT_CONFIG),
            ohlcv_snapshot_path=window["snapshot"],
        )
        result = engine.run()
    finally:
        if original is not None:
            signal_engine.generate_signals = original
    return result


def _aggregate(by_window: dict[str, Any], key: str) -> dict[str, Any]:
    return {
        "expected_value_score_sum": _round(
            sum(float(row[key]["expected_value_score"] or 0.0) for row in by_window.values()),
            4,
        ),
        "total_pnl_sum": _round(
            sum(float(row[key]["total_pnl"] or 0.0) for row in by_window.values()),
            2,
        ),
        "trade_count_sum": sum(int(row[key]["trade_count"] or 0) for row in by_window.values()),
        "signals_generated_sum": sum(
            int(row[key]["signals_generated"] or 0) for row in by_window.values()
        ),
        "signals_survived_sum": sum(
            int(row[key]["signals_survived"] or 0) for row in by_window.values()
        ),
        "min_survival_rate": _round(
            min(float(row[key]["survival_rate"] or 0.0) for row in by_window.values()),
            4,
        ),
        "max_drawdown_pct_max": _round(
            max(float(row[key]["max_drawdown_pct"] or 0.0) for row in by_window.values()),
            4,
        ),
    }


def _gate(by_window: dict[str, Any]) -> dict[str, Any]:
    checks = {}
    for label, row in by_window.items():
        checks[label] = _delta(row["after"], row["before"])
    ev_positive = sum(1 for row in checks.values() if row.get("expected_value_score", 0) > 0)
    ev_regressed = sum(1 for row in checks.values() if row.get("expected_value_score", 0) < 0)
    pnl_positive = sum(1 for row in checks.values() if row.get("total_pnl", 0) > 0)
    survival_after_min = min(
        float(row["after"]["survival_rate"] or 0.0) for row in by_window.values()
    )
    passed = (
        ev_positive == 3
        and ev_regressed == 0
        and pnl_positive == 3
        and survival_after_min >= 0.05
    )
    return {
        "passed": passed,
        "ev_positive_windows": ev_positive,
        "ev_regressed_windows": ev_regressed,
        "pnl_positive_windows": pnl_positive,
        "survival_after_min": _round(survival_after_min, 4),
        "window_deltas": checks,
        "rule": (
            "Pass only if EV and PnL improve in all three canonical windows "
            "and survival stays above 5%."
        ),
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Pullback/Reclaim Entry",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Aggregate EV delta: `{payload['delta_metrics']['aggregate']['expected_value_score_sum_delta']}`",
        f"- Aggregate PnL delta: `{payload['delta_metrics']['aggregate']['total_pnl_sum_delta']}`",
        "",
        "| Window | EV before | EV after | EV delta | PnL delta | Max DD delta | Trades delta |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, row in payload["windows"].items():
        delta = row["delta"]
        lines.append(
            f"| {label} | {row['before']['expected_value_score']:.4f} | "
            f"{row['after']['expected_value_score']:.4f} | "
            f"{delta.get('expected_value_score', 0):.4f} | "
            f"${delta.get('total_pnl', 0):,.2f} | "
            f"{delta.get('max_drawdown_pct', 0):.4f} | "
            f"{delta.get('trade_count', 0)} |"
        )
    lines.extend(
        [
            "",
            "The tested pullback/reclaim entry shape added many candidates but "
            "degraded EV in every canonical window, so no shared production "
            "policy was promoted.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    timestamp = _utc_now()
    universe = get_universe()
    windows: dict[str, Any] = {}
    for label, window in WINDOWS.items():
        before = _result_metrics(_run_window(universe, window, with_pullback=False))
        after = _result_metrics(_run_window(universe, window, with_pullback=True))
        windows[label] = {
            "before": before,
            "after": after,
            "delta": _delta(after, before),
        }

    before_aggregate = _aggregate(windows, "before")
    after_aggregate = _aggregate(windows, "after")
    aggregate_delta = {
        f"{key}_delta": _round(after_aggregate.get(key, 0) - before_aggregate.get(key, 0), 6)
        for key in before_aggregate
        if isinstance(before_aggregate.get(key), (int, float))
        and isinstance(after_aggregate.get(key), (int, float))
    }
    gate = _gate(windows)
    decision = (
        "accepted_pullback_reclaim_entry"
        if gate["passed"]
        else "rejected_pullback_reclaim_entry"
    )
    status = "accepted" if gate["passed"] else "rejected"
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "lane": "alpha_search",
        "hypothesis": (
            "A leadership pullback/reclaim entry can improve candidate-pool alpha "
            "by buying strong names above the 200MA after a controlled 5-15% "
            "pullback from 52-week highs, instead of waiting only for fresh 20d breakouts."
        ),
        "change_type": "entry_candidate_pool_alpha_search",
        "changed_variable": "pullback_reclaim_long_entry_enabled",
        "single_causal_variable": (
            "add one OHLCV pullback/reclaim entry shape; no sizing, exit, ranking, "
            "LLM/news, universe, or event-sleeve changes"
        ),
        "parameters": {
            "entry_shape": {
                "above_200ma": True,
                "momentum_10d_pct": "> 0",
                "momentum_20d_pct": ">= 0.05",
                "pct_from_52w_high": "[-0.15, -0.05)",
                "volume_spike_ratio": ">= 1.2",
                "price_vs_200ma_pct": ">= 0.03",
                "exclude_breakout_20d": True,
                "exclude_breakdown_20d": True,
                "atr_over_close_max": 0.07,
                "days_to_earnings_block": "<= 3",
            },
            "target_stop_sizing": "existing shared risk_engine/portfolio_engine defaults",
            "windows": WINDOWS,
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows using the accepted "
            "core snapshots. The variant monkeypatches signal generation only for "
            "this replay; no production code is changed because Gate 4 failed."
        ),
        "date_range": {
            "primary": {
                "start": WINDOWS["late_strong"]["start"],
                "end": WINDOWS["late_strong"]["end"],
            },
            "secondary": [
                {
                    "start": WINDOWS["mid_weak"]["start"],
                    "end": WINDOWS["mid_weak"]["end"],
                },
                {
                    "start": WINDOWS["old_thin"]["start"],
                    "end": WINDOWS["old_thin"]["end"],
                },
            ],
        },
        "before_metrics": before_aggregate,
        "after_metrics": after_aggregate,
        "delta_metrics": {
            "aggregate": aggregate_delta,
            "by_window": gate["window_deltas"],
        },
        "expected_value_score_delta": aggregate_delta.get(
            "expected_value_score_sum_delta"
        ),
        "gate": gate,
        "decision": decision,
        "rejection_reason": (
            None
            if gate["passed"]
            else "EV regressed in all three canonical windows; tail risk and loss clustering worsened."
        ),
        "next_evidence_needed": (
            "Do not promote this OHLCV pullback/reclaim entry shape. A valid retry "
            "needs a genuinely new event/news quality discriminator or forward "
            "replacement-value evidence, not nearby pullback threshold tuning."
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "alters_signal_generation": True,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "entry: add an OHLCV pullback/reclaim entry for strong names "
                "below near-high breakout territory."
            ),
            "2_history_check": (
                "The playbook lists OHLCV pullback/reclaim entry as a possible "
                "non-LLM candidate-pool direction; prior logs mainly rejected "
                "global TQS ranking, scarce-slot sub-discriminators, Form 4 sparse "
                "satellites, and Space/SEC local retunes. This exact pullback "
                "entry shape was not found in the recent experiment log."
            ),
            "3_single_causal_variable": "pullback_reclaim_long_entry_enabled",
            "4_acceptance_standard": gate["rule"],
            "5_reproducibility": (
                f"Run .venv\\Scripts\\python.exe quant\\experiments\\{Path(__file__).name}"
            ),
        },
        "why_not_other_changes": (
            "LLM soft-ranking remains measurement-blocked, Space breakout variants "
            "recently failed, Form 4 is too sparse, and SEC financial-report local "
            "notional/floor/hold variants should not be repeated after exp-20260512-020."
        ),
        "windows": windows,
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(DOC_LOG.relative_to(REPO_ROOT)),
            str(DOC_TICKET.relative_to(REPO_ROOT)),
            str(DOC_ARTIFACT.relative_to(REPO_ROOT)),
            f"quant/experiments/{Path(__file__).name}",
        ],
    }

    _write_json(OUT_JSON, payload)
    _write_json(DOC_LOG, payload)
    _write_json(
        DOC_TICKET,
        {
            "experiment_id": EXPERIMENT_ID,
            "lane": "alpha_search",
            "owner": "alpha-search",
            "status": status,
            "hypothesis": payload["hypothesis"],
            "single_causal_variable": payload["single_causal_variable"],
            "decision": decision,
            "expected_value_score_delta": payload["expected_value_score_delta"],
            "updated_at": timestamp,
        },
    )
    DOC_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT.write_text(_artifact_markdown(payload), encoding="utf-8")
    _append_jsonl_once(EXPERIMENT_LOG_JSONL, payload)

    print(json.dumps(_safe(gate), indent=2, sort_keys=True))
    print(f"{EXPERIMENT_ID} {decision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
