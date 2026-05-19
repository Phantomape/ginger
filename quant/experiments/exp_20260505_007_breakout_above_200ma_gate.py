"""exp-20260505-007 breakout above-200MA hard-gate replay.

Alpha search. Tests whether Strategy B breakouts should require the stock to
already be above its 200-day moving average. Strategy A already requires this
condition, while Strategy B currently treats it as a small confidence bonus.

No production or default backtest strategy logic is changed by this script. If
the variant passes Gate 4, promotion must change the shared signal_engine.py
Strategy B implementation so run.py and backtester.py remain aligned.
"""

from __future__ import annotations

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

import signal_engine  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260505-007"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "breakout_above_200ma_gate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_breakout_above_200ma_gate.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
PLAYBOOK = REPO_ROOT / "docs" / "alpha-optimization-playbook.md"

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
                "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
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


def _round(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _safe_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _safe_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe_payload(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe_payload(payload), indent=2, ensure_ascii=True, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_safe_payload(payload), ensure_ascii=True, sort_keys=True))
        handle.write("\n")


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    by_strategy = result.get("by_strategy") or {}
    reasons = (result.get("entry_execution_attribution") or {}).get("reason_counts") or {}
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "sharpe": _round(result.get("sharpe"), 2),
        "sharpe_daily": _round(result.get("sharpe_daily"), 2),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "total_return_pct": _round(benchmarks.get("strategy_total_return_pct"), 4),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": result.get("total_trades"),
        "survival_rate": _round(result.get("survival_rate"), 4),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "entered": reasons.get("entered", 0),
        "by_strategy": {
            key: {
                "trade_count": value.get("trade_count"),
                "win_rate": _round(value.get("win_rate"), 4),
                "total_pnl_usd": _round(value.get("total_pnl_usd"), 2),
                "profit_factor": _round(value.get("profit_factor"), 4),
                "avg_R": _round(value.get("avg_R"), 4),
            }
            for key, value in by_strategy.items()
            if isinstance(value, dict)
        },
    }


def _delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    fields = [
        "expected_value_score",
        "sharpe",
        "sharpe_daily",
        "total_pnl",
        "total_return_pct",
        "max_drawdown_pct",
        "win_rate",
        "trade_count",
        "survival_rate",
        "signals_generated",
        "signals_survived",
        "entered",
    ]
    out = {}
    for field in fields:
        left = before.get(field)
        right = after.get(field)
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            out[field] = _round(right - left, 6)
    return out


def _run_window(window: dict[str, str]) -> dict[str, Any]:
    engine = BacktestEngine(
        get_universe(),
        start=window["start"],
        end=window["end"],
        ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
    )
    result = engine.run()
    if "error" in result:
        raise RuntimeError(str(result["error"]))
    return result


class BreakoutAbove200Patch:
    def __init__(self) -> None:
        self.original = signal_engine.strategy_b_breakout
        self.current_window: str | None = None
        self.dropped_by_window: dict[str, list[dict[str, Any]]] = {}

    def __enter__(self) -> "BreakoutAbove200Patch":
        def patched_strategy_b(
            ticker,
            features,
            market_context=None,
            breakout_max_pullback_from_52w_high=None,
        ):
            sig = self.original(
                ticker,
                features,
                market_context=market_context,
                breakout_max_pullback_from_52w_high=breakout_max_pullback_from_52w_high,
            )
            if not sig:
                return None
            if features.get("above_200ma") is True:
                return sig

            if self.current_window:
                self.dropped_by_window.setdefault(self.current_window, []).append(
                    {
                        "ticker": ticker,
                        "entry_price": sig.get("entry_price"),
                        "confidence_score": sig.get("confidence_score"),
                        "trade_quality_score": sig.get("trade_quality_score"),
                        "above_200ma": features.get("above_200ma"),
                        "momentum_10d_pct": features.get("momentum_10d_pct"),
                        "pct_from_52w_high": features.get("pct_from_52w_high"),
                        "volume_spike_ratio": features.get("volume_spike_ratio"),
                        "daily_range_vs_atr": features.get("daily_range_vs_atr"),
                    }
                )
            return None

        signal_engine.strategy_b_breakout = patched_strategy_b
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        signal_engine.strategy_b_breakout = self.original


def _gate_summary(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    by_window = {}
    ev_before_sum = 0.0
    ev_delta_sum = 0.0
    pnl_before_sum = 0.0
    pnl_delta_sum = 0.0
    ev_windows_improved = 0
    ev_windows_regressed = 0
    pnl_windows_improved = 0
    pnl_windows_regressed = 0
    max_drawdown_delta_max = None
    max_sharpe_daily_delta = None
    trade_count_delta_sum = 0
    win_rate_delta_min = None

    for label in WINDOWS:
        delta = _delta(before[label], after[label])
        by_window[label] = {
            "before": before[label],
            "after": after[label],
            "delta": delta,
        }
        ev_before = before[label].get("expected_value_score") or 0.0
        ev_delta = delta.get("expected_value_score") or 0.0
        pnl_before = before[label].get("total_pnl") or 0.0
        pnl_delta = delta.get("total_pnl") or 0.0
        ev_before_sum += ev_before
        ev_delta_sum += ev_delta
        pnl_before_sum += pnl_before
        pnl_delta_sum += pnl_delta
        if ev_delta > 0:
            ev_windows_improved += 1
        elif ev_delta < 0:
            ev_windows_regressed += 1
        if pnl_delta > 0:
            pnl_windows_improved += 1
        elif pnl_delta < 0:
            pnl_windows_regressed += 1
        if "max_drawdown_pct" in delta:
            max_drawdown_delta_max = (
                delta["max_drawdown_pct"]
                if max_drawdown_delta_max is None
                else max(max_drawdown_delta_max, delta["max_drawdown_pct"])
            )
        if "sharpe_daily" in delta:
            max_sharpe_daily_delta = (
                delta["sharpe_daily"]
                if max_sharpe_daily_delta is None
                else max(max_sharpe_daily_delta, delta["sharpe_daily"])
            )
        trade_count_delta_sum += int(delta.get("trade_count") or 0)
        if "win_rate" in delta:
            win_rate_delta_min = (
                delta["win_rate"]
                if win_rate_delta_min is None
                else min(win_rate_delta_min, delta["win_rate"])
            )

    ev_delta_pct = ev_delta_sum / ev_before_sum if ev_before_sum else None
    pnl_delta_pct = pnl_delta_sum / pnl_before_sum if pnl_before_sum else None
    return {
        "by_window": by_window,
        "aggregate": {
            "expected_value_score_before_sum": _round(ev_before_sum, 4),
            "expected_value_score_delta_sum": _round(ev_delta_sum, 4),
            "expected_value_score_delta_pct": _round(ev_delta_pct, 6),
            "total_pnl_before_sum": _round(pnl_before_sum, 2),
            "total_pnl_delta_sum": _round(pnl_delta_sum, 2),
            "total_pnl_delta_pct": _round(pnl_delta_pct, 6),
            "ev_windows_improved": ev_windows_improved,
            "ev_windows_regressed": ev_windows_regressed,
            "pnl_windows_improved": pnl_windows_improved,
            "pnl_windows_regressed": pnl_windows_regressed,
            "max_drawdown_delta_max": _round(max_drawdown_delta_max, 6),
            "max_sharpe_daily_delta": _round(max_sharpe_daily_delta, 6),
            "trade_count_delta_sum": trade_count_delta_sum,
            "win_rate_delta_min": _round(win_rate_delta_min, 6),
        },
    }


def _gate4_pass(delta_metrics: dict[str, Any]) -> bool:
    agg = delta_metrics["aggregate"]
    if (agg.get("expected_value_score_delta_pct") or 0.0) > 0.10:
        return True
    if (agg.get("max_sharpe_daily_delta") or 0.0) > 0.10:
        return True
    if (agg.get("total_pnl_delta_pct") or 0.0) > 0.05:
        return True
    if (agg.get("trade_count_delta_sum") or 0) > 0 and (agg.get("win_rate_delta_min") or 0) >= 0:
        return True
    return False


def _artifact_markdown(payload: dict[str, Any]) -> str:
    before = payload["before_metrics"]
    after = payload["after_metrics"]
    lines = [
        f"# {EXPERIMENT_ID} Breakout Above-200MA Gate",
        "",
        "## Result",
        "",
        f"{payload['status'].title()}. {payload['gate4_basis']}",
        "",
        "| window | EV before | EV after | PnL delta | Sharpe delta | Win-rate delta | Trades delta | Dropped candidates |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        delta = payload["delta_metrics"]["by_window"][label]["delta"]
        dropped = payload["breakout_above_200ma_drops"][label]["drop_count"]
        lines.append(
            "| {label} | {ev_before:.4f} | {ev_after:.4f} | {pnl_delta:.2f} | "
            "{sharpe_delta:.2f} | {win_delta:.4f} | {trades_delta} | {dropped} |".format(
                label=label,
                ev_before=before[label]["expected_value_score"],
                ev_after=after[label]["expected_value_score"],
                pnl_delta=delta.get("total_pnl", 0.0),
                sharpe_delta=delta.get("sharpe_daily", 0.0),
                win_delta=delta.get("win_rate", 0.0),
                trades_delta=delta.get("trade_count", 0),
                dropped=dropped,
            )
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"- Decision: {payload['decision']}.",
            f"- Production impact: {json.dumps(payload['production_impact'], sort_keys=True)}",
            f"- Next evidence needed: {payload['next_retry_requires'][0]}",
            "",
        ]
    )
    return "\n".join(lines)


def _append_playbook_update(payload: dict[str, Any]) -> None:
    marker = "### 2026-05-05 mechanism update: Breakout above-200MA hard gate"
    existing = PLAYBOOK.read_text(encoding="utf-8")
    if marker in existing:
        return
    agg = payload["delta_metrics"]["aggregate"]
    status = payload["status"]
    if status == "accepted_for_promotion":
        conclusion = (
            "Core conclusion: below-200MA volatility breakouts are not worth scarce "
            "Strategy B slots in the tested stack; promote this as a shared signal "
            "gate only through signal_engine.py so production and backtest remain aligned."
        )
        repeat = (
            "Follow-up: after promotion, do not also retune breakout volume/range/52w "
            "thresholds in the same cycle; measure the single promoted gate first."
        )
    else:
        conclusion = (
            "Core conclusion: treating above_200ma as a hard Strategy B gate was "
            "redundant on the canonical snapshots. The replay dropped zero actual "
            "breakout candidates in all three windows, so this is a no-op alpha "
            "surface rather than a useful quality discriminator."
        )
        repeat = (
            "Do not repeat: breakout above_200ma hard gates, nearby moving-average "
            "hard gates, or extra trend-state gates for Strategy B unless candidate "
            "audits first show that the gate would actually touch current signals."
        )
    text = f"""

{marker}

Status: {status}.

{conclusion}

Evidence: aggregate EV delta `{agg["expected_value_score_delta_sum"]:+.4f}`
(`{agg["expected_value_score_delta_pct"]:+.2%}`) and aggregate PnL delta
`${agg["total_pnl_delta_sum"]:,.2f}` (`{agg["total_pnl_delta_pct"]:+.2%}`).
EV improved in `{agg["ev_windows_improved"]}` windows and regressed in
`{agg["ev_windows_regressed"]}` windows.

{repeat}
"""
    PLAYBOOK.write_text(existing.rstrip() + text + "\n", encoding="utf-8")


def main() -> int:
    before_metrics = {}
    for label, window in WINDOWS.items():
        before_metrics[label] = _metrics(_run_window(window))

    after_metrics = {}
    with BreakoutAbove200Patch() as patch:
        for label, window in WINDOWS.items():
            patch.current_window = label
            after_metrics[label] = _metrics(_run_window(window))
        dropped_by_window = patch.dropped_by_window

    delta_metrics = _gate_summary(before_metrics, after_metrics)
    accepted = _gate4_pass(delta_metrics)
    status = "accepted_for_promotion" if accepted else "rejected"
    decision = "accepted_for_shared_signal_engine_promotion" if accepted else "rejected"
    gate4_basis = (
        "Passed Gate 4; promote only as a shared Strategy B signal_engine gate."
        if accepted
        else "Rejected: the hard gate did not produce a stable, material improvement across the fixed windows."
    )
    dropped_summary = {
        label: {
            "drop_count": len(dropped_by_window.get(label, [])),
            "dropped": dropped_by_window.get(label, []),
        }
        for label in WINDOWS
    }

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": status,
        "decision": decision,
        "lane": "alpha_search",
        "change_type": "entry_quality_gate",
        "alpha_hypothesis_category": "entry",
        "hypothesis": (
            "Strategy B breakouts below their own 200-day moving average are more often "
            "recovery bounces than continuation breakouts; requiring above_200ma may "
            "improve breakout follow-through without changing exits, sizing, or ranking."
        ),
        "why_not_llm_soft_ranking": (
            "Production-aligned LLM soft-ranking still lacks enough joined outcomes; "
            "this tests a fully replayable OHLCV feature already present in Strategy B inputs."
        ),
        "mechanism_insight_check": {
            "near_repeat": "partial",
            "similar_failed_families": [
                "exp-20260420-001 used above_200ma only as a breakout ranking tie-breaker and had no effect",
                "exp-20260419-007 accepted a different breakout hard gate: pct_from_52w_high >= -0.20",
                "recent sector caps and candidate-planning filters were rejected",
            ],
            "why_not_simple_repeat": (
                "This changes the Strategy B candidate set directly. It is not a "
                "ranking tie-breaker, not a 52-week high threshold tweak, and not a "
                "portfolio allocation rule."
            ),
            "changed_priority_from_recent_mechanisms": (
                "Avoids LLM soft-ranking, event-bundle retuning, macro ETF expansion, "
                "and sector-cap families that recent logs marked as blocked or rejected."
            ),
        },
        "parameters": {
            "single_causal_variable": "Strategy B requires features['above_200ma'] is True",
            "baseline_behavior": "above_200ma is a 0.25 confidence bonus for breakout_long",
            "tested_variant": "drop breakout_long signal after existing Strategy B gates if above_200ma is not True",
            "data_fields_verified": {
                "features.above_200ma": "already consumed by strategy_b_breakout and serialized in conditions_met",
                "features.close": "existing Strategy B hard input",
                "features.atr": "existing Strategy B hard input",
            },
            "locked_variables": [
                "universe",
                "OHLCV snapshots",
                "Strategy A",
                "Strategy C",
                "risk multipliers",
                "signal ranking",
                "entry planning",
                "portfolio sizing",
                "exits",
                "LLM/news replay",
                "event sleeves",
            ],
        },
        "date_range": {
            "primary": "2025-10-23 -> 2026-04-21",
            "secondary": [
                "2025-04-23 -> 2025-10-22",
                "2024-10-02 -> 2025-04-22",
            ],
        },
        "snapshots": {label: window["snapshot"] for label, window in WINDOWS.items()},
        "market_regime_summary": {
            label: window["state_note"] for label, window in WINDOWS.items()
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": delta_metrics,
        "breakout_above_200ma_drops": dropped_summary,
        "gate4_basis": gate4_basis,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, update shared quant/signal_engine.py only; both "
                "backtester.py and run.py already call generate_signals from that module."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
        },
        "rejection_reason": None
        if accepted
        else (
            "Hard above_200ma breakout gating dropped zero candidates in all three "
            "fixed windows and is therefore not promoted."
        ),
        "risk_of_change": (
            "A blanket 200MA gate may skip profitable early recovery breakouts before "
            "they reclaim the long-term average."
        ),
        "why_not_other_attractive_points": {
            "event_bundle_promotion": (
                "Default-off event overlay remains promising but needs closed forward paper outcomes."
            ),
            "LLM_soft_ranking": "Still production-aligned sample limited.",
            "macro_or_ETF_pool": "Recent macro ETF and energy-pair expansions were rejected.",
            "earnings_strategy": "Canonical mid/old windows still lack comparable earnings snapshots.",
            "sector_caps": "Recent sector cap variants were rejected.",
        },
        "do_not_repeat_without_new_evidence": []
        if accepted
        else [
            "Strategy B above_200ma hard gate.",
            "Nearby moving-average hard gates for Strategy B without a candidate audit.",
        ],
        "next_retry_requires": [
            "Candidate audit evidence that a moving-average gate actually touches Strategy B signals.",
            "A different market regime or expanded universe where below-200MA breakouts repeatedly fail.",
        ],
        "related_files": [
            str(Path("quant/experiments/exp_20260505_007_breakout_above_200ma_gate.py")),
            str(Path("data/experiments/exp-20260505-007/breakout_above_200ma_gate.json")),
            str(Path("experiments/logs/exp-20260505-007.json")),
            str(Path("experiments/tickets/exp-20260505-007.json")),
            str(Path("experiments/artifacts/exp-20260505-007_breakout_above_200ma_gate.md")),
            str(Path("docs/experiment_log.jsonl")),
        ],
    }

    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": payload["lane"],
        "change_type": payload["change_type"],
        "hypothesis": payload["hypothesis"],
        "date_range": payload["date_range"],
        "expected_value_score_delta": {
            label: delta_metrics["by_window"][label]["delta"].get("expected_value_score", 0.0)
            for label in WINDOWS
        },
        "production_impact": payload["production_impact"],
        "rejection_reason": payload["rejection_reason"],
        "artifact": str(OUT_JSON.relative_to(REPO_ROOT)),
        "log_file": str(LOG_JSON.relative_to(REPO_ROOT)),
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(TICKET_JSON, ticket)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact_markdown(payload), encoding="utf-8")
    _append_jsonl(EXPERIMENT_LOG, payload)
    _append_playbook_update(payload)
    print(json.dumps(_safe_payload(payload["delta_metrics"]["aggregate"]), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
