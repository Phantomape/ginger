"""Replay Financials sector-leader trend target-width variants.

The accepted stack already sizes `trend_long` Financials sector-relative
leaders differently. This experiment tests only whether that same existing
leader discriminator should also receive a wider ATR target.
"""

from __future__ import annotations

import json
import logging
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import risk_engine  # noqa: E402
from backtester import BacktestEngine, DEFAULT_CONFIG  # noqa: E402
from constants import ATR_STOP_MULT  # noqa: E402

try:  # noqa: E402
    from data_layer import get_universe
except Exception:  # pragma: no cover - fallback mirrors backtester CLI.
    from filter import WATCHLIST

    def get_universe():
        return list(WATCHLIST)


EXPERIMENT_ID = "exp-20260506-005"

WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
        "state_note": "slow-melt bull / accepted-stack dominant tape",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
        "state_note": "rotation-heavy bull where strategy profits but lags indexes",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "state_note": "mixed-to-weak older tape with lower win rate",
    },
}

VARIANTS = {
    "baseline": None,
    "financials_leader_target_5_0atr": 5.0,
    "financials_leader_target_5_5atr": 5.5,
    "financials_leader_target_6_0atr": 6.0,
}


def _metric_snapshot(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    convergence = result.get("convergence") or {}
    return {
        "expected_value_score": result.get("expected_value_score"),
        "total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "total_pnl": result.get("total_pnl"),
        "sharpe_daily": result.get("sharpe_daily"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": result.get("survival_rate"),
        "converged": convergence.get("converged"),
    }


def _retarget_signal(signal: dict, target_mult: float) -> dict:
    entry = signal.get("entry_price")
    stop = signal.get("stop_price")
    if not isinstance(entry, (int, float)) or not isinstance(stop, (int, float)):
        return signal
    risk_per_share = entry - stop
    if risk_per_share <= 0:
        return signal
    atr = risk_per_share / ATR_STOP_MULT
    target_price = round(entry + target_mult * atr, 2)
    reward_per_share = round(target_price - entry, 2)
    risk_per_share = round(risk_per_share, 2)
    rr_ratio = round(reward_per_share / risk_per_share, 2) if risk_per_share > 0 else None
    return {
        **signal,
        "target_price": target_price,
        "reward_per_share": reward_per_share,
        "risk_reward_ratio": rr_ratio,
        "target_mult_used": target_mult,
        "target_width_applied": target_mult,
        "financials_leader_target_width_applied": target_mult,
    }


def _make_enricher(target_mult: float | None):
    original = risk_engine.enrich_signals

    def _patched(signals, features_dict, atr_target_mult=None):
        enriched = original(signals, features_dict, atr_target_mult=atr_target_mult)
        if target_mult is None:
            return enriched
        out = []
        for signal in enriched:
            if (
                signal.get("strategy") == "trend_long"
                and signal.get("sector") == "Financials"
                and signal.get("financials_sector_leader") is True
            ):
                out.append(_retarget_signal(signal, target_mult))
            else:
                out.append(signal)
        return out

    return _patched


def _run_window(window: dict, target_mult: float | None) -> dict:
    patched = _make_enricher(target_mult)
    original_risk_enrich = risk_engine.enrich_signals
    risk_engine.enrich_signals = patched
    try:
        engine = BacktestEngine(
            universe=get_universe(),
            start=window["start"],
            end=window["end"],
            config=deepcopy(DEFAULT_CONFIG),
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
        )
        result = engine.run()
    finally:
        risk_engine.enrich_signals = original_risk_enrich

    touched_trades = [
        trade
        for trade in result.get("trades", [])
        if trade.get("financials_leader_target_width_applied") is not None
        or (
            trade.get("strategy") == "trend_long"
            and trade.get("sector") == "Financials"
            and (trade.get("sizing_multipliers") or {}).get(
                "financials_sector_leader_risk_multiplier_applied"
            )
        )
    ]
    touched_pnl = round(sum(float(t.get("pnl") or 0.0) for t in touched_trades), 2)
    return {
        "metrics": _metric_snapshot(result),
        "touched_trade_count": len(touched_trades),
        "touched_pnl": touched_pnl,
        "touched_trades": [
            {
                "ticker": t.get("ticker"),
                "entry_date": t.get("entry_date"),
                "exit_date": t.get("exit_date"),
                "exit_reason": t.get("exit_reason"),
                "pnl": t.get("pnl"),
                "pnl_pct_net": t.get("pnl_pct_net"),
                "target_mult_used": t.get("target_mult_used"),
                "addon_count": t.get("addon_count"),
            }
            for t in touched_trades
        ],
    }


def _delta(after: dict, before: dict) -> dict:
    fields = (
        "expected_value_score",
        "total_return_pct",
        "total_pnl",
        "sharpe_daily",
        "max_drawdown_pct",
        "win_rate",
        "trade_count",
        "signals_generated",
        "signals_survived",
        "survival_rate",
    )
    out = {}
    for field in fields:
        a = after.get(field)
        b = before.get(field)
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            out[field] = round(a - b, 6)
    return out


def _summarize(results: dict) -> tuple[str, dict]:
    baseline = {label: payload["baseline"]["metrics"] for label, payload in results.items()}
    variants = [name for name in VARIANTS if name != "baseline"]
    summaries = {}
    for variant in variants:
        by_window = {}
        ev_delta_sum = 0.0
        pnl_delta_sum = 0.0
        ev_improved = 0
        ev_regressed = 0
        max_drawdown_delta = None
        max_sharpe_delta = None
        min_win_rate_delta = None
        for label, payload in results.items():
            metrics = payload[variant]["metrics"]
            delta = _delta(metrics, baseline[label])
            by_window[label] = {
                "after": metrics,
                "before": baseline[label],
                "delta": delta,
                "touched_trade_count": payload[variant]["touched_trade_count"],
                "touched_pnl": payload[variant]["touched_pnl"],
            }
            ev_delta = delta.get("expected_value_score", 0.0)
            pnl_delta = delta.get("total_pnl", 0.0)
            ev_delta_sum += ev_delta
            pnl_delta_sum += pnl_delta
            if ev_delta > 0:
                ev_improved += 1
            elif ev_delta < 0:
                ev_regressed += 1
            dd_delta = delta.get("max_drawdown_pct")
            if dd_delta is not None:
                max_drawdown_delta = dd_delta if max_drawdown_delta is None else max(max_drawdown_delta, dd_delta)
            sharpe_delta = delta.get("sharpe_daily")
            if sharpe_delta is not None:
                max_sharpe_delta = sharpe_delta if max_sharpe_delta is None else max(max_sharpe_delta, sharpe_delta)
            win_delta = delta.get("win_rate")
            if win_delta is not None:
                min_win_rate_delta = win_delta if min_win_rate_delta is None else min(min_win_rate_delta, win_delta)

        baseline_ev_sum = sum(
            float(metrics.get("expected_value_score") or 0.0)
            for metrics in baseline.values()
        )
        baseline_pnl_sum = sum(
            float(metrics.get("total_pnl") or 0.0)
            for metrics in baseline.values()
        )
        summaries[variant] = {
            "target_mult": VARIANTS[variant],
            "by_window": by_window,
            "aggregate": {
                "expected_value_score_before_sum": round(baseline_ev_sum, 4),
                "expected_value_score_delta_sum": round(ev_delta_sum, 4),
                "expected_value_score_delta_pct": (
                    round(ev_delta_sum / baseline_ev_sum, 6)
                    if baseline_ev_sum else None
                ),
                "total_pnl_before_sum": round(baseline_pnl_sum, 2),
                "total_pnl_delta_sum": round(pnl_delta_sum, 2),
                "total_pnl_delta_pct": (
                    round(pnl_delta_sum / baseline_pnl_sum, 6)
                    if baseline_pnl_sum else None
                ),
                "ev_windows_improved": ev_improved,
                "ev_windows_regressed": ev_regressed,
                "max_drawdown_delta_max": max_drawdown_delta,
                "max_sharpe_daily_delta": max_sharpe_delta,
                "win_rate_delta_min": min_win_rate_delta,
            },
        }

    best = max(
        summaries,
        key=lambda name: (
            summaries[name]["aggregate"]["expected_value_score_delta_sum"],
            summaries[name]["aggregate"]["total_pnl_delta_sum"],
        ),
    )
    return best, summaries


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> int:
    logging.basicConfig(level=logging.WARNING)

    results: dict[str, dict] = {}
    for label, window in WINDOWS.items():
        results[label] = {}
        for variant, target_mult in VARIANTS.items():
            results[label][variant] = _run_window(window, target_mult)

    best_variant, summaries = _summarize(results)
    best_summary = summaries[best_variant]
    aggregate = best_summary["aggregate"]
    gate4_passed = (
        aggregate["ev_windows_improved"] >= 2
        and (
            (aggregate["expected_value_score_delta_pct"] or 0.0) > 0.10
            or (aggregate["total_pnl_delta_pct"] or 0.0) > 0.05
            or (aggregate["max_sharpe_daily_delta"] or 0.0) > 0.1
            or (aggregate["max_drawdown_delta_max"] or 0.0) < -0.01
        )
    )
    decision = "accepted_candidate" if gate4_passed else "rejected"

    before_metrics = {
        label: results[label]["baseline"]["metrics"]
        for label in WINDOWS
    }
    after_metrics = {
        label: best_summary["by_window"][label]["after"]
        for label in WINDOWS
    }
    timestamp = datetime.now(timezone.utc).isoformat()
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": timestamp,
        "status": decision,
        "decision": decision,
        "lane": "alpha_search",
        "change_type": "exit_lifecycle_target_width_sweep",
        "mechanism_family": "financials_sector_leader_winner_capture",
        "hypothesis": (
            "Existing trend_long Financials sector-relative leaders may deserve "
            "a wider target because the accepted sizing policy already identifies "
            "them as higher-expectancy winners; test target width only for that "
            "pre-existing leader cohort."
        ),
        "alpha_hypothesis": {
            "category": "exit / lifecycle winner capture",
            "why_this_now": (
                "LLM soft-ranking and event-bundle promotion remain data-limited; "
                "static universe expansion has repeatedly failed. This reuses an "
                "accepted production-visible discriminator instead of adding entry noise."
            ),
        },
        "historical_experiment_check": {
            "blocked_repeats": {
                "broad_financials_target_width": (
                    "Rejected because broad Financials trend widening hurt mid/old windows."
                ),
                "financials_multiplier": (
                    "Nearby Financials risk multipliers are already blocked."
                ),
                "financials_addon_cap": (
                    "exp-20260505-017 was no-op; this test changes exits, not add-ons."
                ),
            },
            "why_not_simple_repeat": (
                "The variable is restricted to the existing sector-relative leader "
                "cohort, not all Financials trend trades and not another risk multiplier."
            ),
            "mechanism_insight_check": (
                "Does not touch recent no-go zones: static ticker baskets, event "
                "same-sample retuning, simple slot ranking, active sector caps, or LLM ranking."
            ),
        },
        "parameters": {
            "single_causal_variable": (
                "ATR target width for trend_long Financials sector-relative leaders"
            ),
            "variants": VARIANTS,
            "locked_variables": [
                "candidate universe",
                "signal generation",
                "entry filters",
                "entry ordering",
                "risk sizing multipliers",
                "position caps",
                "add-ons",
                "LLM replay",
                "news replay",
                "event sleeves",
            ],
            "best_variant": best_variant,
        },
        "date_range": {
            label: f"{window['start']} -> {window['end']}"
            for label, window in WINDOWS.items()
        },
        "market_regime_summary": {
            label: window["state_note"]
            for label, window in WINDOWS.items()
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": best_summary,
        "all_variant_summaries": summaries,
        "gate4": {
            "passed": gate4_passed,
            "basis": (
                "Requires EV improvement in at least two windows plus a material "
                "EV/PnL/Sharpe/drawdown gate."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "promotion_requirement": (
                "If accepted, implement the target override in risk_engine.enrich_signals "
                "so run.py and backtester.py share the same policy, then add tests."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": "Production-aligned LLM soft-ranking samples remain sparse.",
        },
        "risk_of_change": (
            "A wider target can turn current full-target winners into later stop-outs "
            "or end-of-window open risk, especially in weaker tapes."
        ),
        "decision_rationale": (
            "Accepted for promotion only if the best variant clears three-window Gate 4; "
            "otherwise record as a non-repeat target-width failure."
        ),
        "rejection_reason": None if gate4_passed else (
            "Best variant failed material three-window Gate 4 for Financials leader target width."
        ),
    }

    exp_dir = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
    log_path = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    ticket_path = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
    artifact_path = (
        REPO_ROOT
        / "docs"
        / "experiments"
        / "artifacts"
        / f"{EXPERIMENT_ID}_financials_leader_target_width.md"
    )
    result_path = exp_dir / "financials_leader_target_width.json"

    _write_json(result_path, payload)
    _write_json(log_path, payload)
    _write_json(ticket_path, {
        "experiment_id": EXPERIMENT_ID,
        "lane": "alpha_search",
        "status": decision,
        "hypothesis": payload["hypothesis"],
        "next_action": (
            "Promote through shared risk_engine policy and tests."
            if gate4_passed
            else "Do not repeat nearby Financials sector-leader target widths without new event or forward evidence."
        ),
    })
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    with artifact_path.open("w", encoding="utf-8") as handle:
        handle.write(f"# {EXPERIMENT_ID}: Financials Leader Target Width\n\n")
        handle.write(f"- Decision: `{decision}`\n")
        handle.write(f"- Best variant: `{best_variant}`\n")
        handle.write(
            "- Aggregate EV delta: "
            f"`{aggregate['expected_value_score_delta_sum']}` "
            f"(`{aggregate['expected_value_score_delta_pct']}`)\n"
        )
        handle.write(
            "- Aggregate PnL delta: "
            f"`${aggregate['total_pnl_delta_sum']}` "
            f"(`{aggregate['total_pnl_delta_pct']}`)\n"
        )
        handle.write(
            "- EV improved/regressed windows: "
            f"`{aggregate['ev_windows_improved']}` / `{aggregate['ev_windows_regressed']}`\n\n"
        )
        if gate4_passed:
            handle.write(
                "Promotion requires moving the override into shared risk_engine "
                "policy used by both production and backtester.\n"
            )
        else:
            handle.write(
                "Do not repeat nearby Financials sector-leader target-width "
                "variants without new event/news or forward evidence.\n"
            )

    payload["related_files"] = [
        str(result_path.relative_to(REPO_ROOT)).replace("\\", "/"),
        str(log_path.relative_to(REPO_ROOT)).replace("\\", "/"),
        str(ticket_path.relative_to(REPO_ROOT)).replace("\\", "/"),
        str(artifact_path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "quant/experiments/exp_20260506_005_financials_leader_target_width.py",
    ]
    _write_json(result_path, payload)
    _write_json(log_path, payload)
    _append_jsonl(REPO_ROOT / "docs" / "experiment_log.jsonl", payload)

    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "decision": decision,
        "best_variant": best_variant,
        "aggregate": aggregate,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
