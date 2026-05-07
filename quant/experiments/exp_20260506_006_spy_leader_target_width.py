"""Replay SPY-relative leader target-width variants.

The accepted stack already uses `spy_relative_leader` as a production-visible
risk-on quality discriminator. This experiment tests one independent variable:
whether otherwise-default SPY-relative leaders should use a wider ATR target.
Signals with existing special target policies, such as Technology trend and
gold/commodity trend targets, are intentionally left unchanged.
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

try:  # noqa: E402
    from data_layer import get_universe
except Exception:  # pragma: no cover - fallback mirrors backtester CLI.
    from filter import WATCHLIST

    def get_universe():
        return list(WATCHLIST)


EXPERIMENT_ID = "exp-20260506-006"

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
    "spy_leader_default_target_5_0atr": 5.0,
    "spy_leader_default_target_5_5atr": 5.5,
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


def _is_default_target_spy_leader(signal: dict) -> bool:
    return (
        signal.get("spy_relative_leader") is True
        and signal.get("target_width_applied") is None
    )


def _make_enricher(target_mult: float | None):
    original = risk_engine.enrich_signals

    def _patched(signals, features_dict, atr_target_mult=None):
        enriched = original(signals, features_dict, atr_target_mult=atr_target_mult)
        if target_mult is None:
            return enriched

        out = []
        for signal in enriched:
            if not _is_default_target_spy_leader(signal):
                out.append(signal)
                continue

            ticker = signal.get("ticker")
            features = features_dict.get(ticker, {}) if ticker else {}
            atr = features.get("atr")
            if not isinstance(atr, (int, float)) or atr <= 0:
                out.append(signal)
                continue

            retargeted = risk_engine._retarget_signal_with_atr_mult(
                signal,
                atr,
                target_mult,
            )
            retargeted["spy_leader_default_target_width_applied"] = target_mult
            out.append(retargeted)
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

    touched_trades = []
    for trade in result.get("trades", []):
        multipliers = trade.get("sizing_multipliers") or {}
        is_spy_leader_trade = (
            multipliers.get("spy_relative_leader_risk_on_multiplier_applied")
            is not None
        )
        if not is_spy_leader_trade:
            continue
        if target_mult is not None and trade.get("target_mult_used") != target_mult:
            continue
        if target_mult is None and trade.get("target_mult_used") not in (None, 4.5):
            continue
        if is_spy_leader_trade:
            touched_trades.append(trade)

    touched_pnl = round(sum(float(t.get("pnl") or 0.0) for t in touched_trades), 2)
    return {
        "metrics": _metric_snapshot(result),
        "touched_trade_count": len(touched_trades),
        "touched_pnl": touched_pnl,
        "touched_trades": [
            {
                "ticker": t.get("ticker"),
                "strategy": t.get("strategy"),
                "sector": t.get("sector"),
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
        a_value = after.get(field)
        b_value = before.get(field)
        if isinstance(a_value, (int, float)) and isinstance(b_value, (int, float)):
            out[field] = round(a_value - b_value, 6)
    return out


def _summarize(results: dict) -> tuple[str, dict]:
    baseline = {
        label: payload["baseline"]["metrics"]
        for label, payload in results.items()
    }
    baseline_ev_sum = sum(
        float(metrics.get("expected_value_score") or 0.0)
        for metrics in baseline.values()
    )
    baseline_pnl_sum = sum(
        float(metrics.get("total_pnl") or 0.0)
        for metrics in baseline.values()
    )

    summaries = {}
    for variant, target_mult in VARIANTS.items():
        if variant == "baseline":
            continue

        by_window = {}
        ev_delta_sum = 0.0
        pnl_delta_sum = 0.0
        ev_improved = 0
        ev_regressed = 0
        drawdown_deltas = []
        sharpe_deltas = []
        win_rate_deltas = []
        touched_trade_sum = 0

        for label, payload in results.items():
            metrics = payload[variant]["metrics"]
            delta = _delta(metrics, baseline[label])
            touched_trade_sum += payload[variant]["touched_trade_count"]
            by_window[label] = {
                "after": metrics,
                "before": baseline[label],
                "delta": delta,
                "touched_trade_count": payload[variant]["touched_trade_count"],
                "touched_pnl": payload[variant]["touched_pnl"],
                "touched_trades": payload[variant]["touched_trades"],
            }

            ev_delta = float(delta.get("expected_value_score") or 0.0)
            pnl_delta = float(delta.get("total_pnl") or 0.0)
            ev_delta_sum += ev_delta
            pnl_delta_sum += pnl_delta
            if ev_delta > 0:
                ev_improved += 1
            elif ev_delta < 0:
                ev_regressed += 1
            if isinstance(delta.get("max_drawdown_pct"), (int, float)):
                drawdown_deltas.append(delta["max_drawdown_pct"])
            if isinstance(delta.get("sharpe_daily"), (int, float)):
                sharpe_deltas.append(delta["sharpe_daily"])
            if isinstance(delta.get("win_rate"), (int, float)):
                win_rate_deltas.append(delta["win_rate"])

        summaries[variant] = {
            "target_mult": target_mult,
            "by_window": by_window,
            "aggregate": {
                "expected_value_score_before_sum": round(baseline_ev_sum, 4),
                "expected_value_score_delta_sum": round(ev_delta_sum, 4),
                "expected_value_score_delta_pct": (
                    round(ev_delta_sum / baseline_ev_sum, 6)
                    if baseline_ev_sum
                    else None
                ),
                "total_pnl_before_sum": round(baseline_pnl_sum, 2),
                "total_pnl_delta_sum": round(pnl_delta_sum, 2),
                "total_pnl_delta_pct": (
                    round(pnl_delta_sum / baseline_pnl_sum, 6)
                    if baseline_pnl_sum
                    else None
                ),
                "ev_windows_improved": ev_improved,
                "ev_windows_regressed": ev_regressed,
                "max_drawdown_delta_max": (
                    max(drawdown_deltas) if drawdown_deltas else None
                ),
                "max_sharpe_daily_delta": (
                    max(sharpe_deltas) if sharpe_deltas else None
                ),
                "min_win_rate_delta": (
                    min(win_rate_deltas) if win_rate_deltas else None
                ),
                "touched_trade_count_sum": touched_trade_sum,
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


def _append_playbook_note(path: Path, note: str) -> None:
    text = path.read_text(encoding="utf-8")
    marker = "## Recent mechanism insights\n"
    if marker in text:
        text = text.replace(marker, marker + note + "\n", 1)
    else:
        text = text.rstrip() + "\n\n" + marker + note + "\n"
    path.write_text(text, encoding="utf-8")


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
            or (aggregate["max_drawdown_delta_max"] or 0.0) < -1.0
        )
    )
    decision = "accepted_candidate" if gate4_passed else "rejected"
    timestamp = datetime.now(timezone.utc).isoformat()

    before_metrics = {
        label: results[label]["baseline"]["metrics"]
        for label in WINDOWS
    }
    after_metrics = {
        label: best_summary["by_window"][label]["after"]
        for label in WINDOWS
    }
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": timestamp,
        "status": decision,
        "decision": decision,
        "lane": "alpha_search",
        "change_type": "exit_lifecycle_target_width_sweep",
        "mechanism_family": "spy_relative_leader_winner_capture",
        "hypothesis": (
            "Otherwise-default SPY-relative leaders may deserve a wider ATR "
            "target because the accepted stack already treats the cohort as "
            "higher-expectancy risk-on leadership. Test only target width, "
            "leaving existing Technology and commodity/gold target policies unchanged."
        ),
        "alpha_hypothesis": {
            "category": "exit / lifecycle winner capture",
            "why_this_now": (
                "LLM soft-ranking and event-overlay promotion are sample-limited; "
                "static universe expansion and simple ranking gates have failed. "
                "This uses an existing production-visible quality field instead "
                "of adding noisy tickers or new entry filters."
            ),
        },
        "historical_experiment_check": {
            "blocked_repeats": {
                "llm_soft_ranking": "Blocked by sparse production-aligned samples.",
                "event_overlay_bundle": "Blocked by lack of closed forward paper outcomes.",
                "static_baskets": "Rejected repeatedly across infra, cybersecurity, quality, industrial/defense.",
                "nearby_addon_cap_or_sector_cap": "Rejected or immaterial without new discriminator.",
                "financials_target_width": "Sector-local target width failed; this tests a cross-sector SPY leadership field and excludes existing special target policies.",
            },
            "why_not_simple_repeat": (
                "The changed variable is a cross-sector target width for the "
                "already accepted SPY-relative leader field, not another ticker "
                "basket, sector cap, add-on cap, slot ranking rule, or LLM ranking retry."
            ),
            "mechanism_insight_check": (
                "Does not enter recent no-go zones: static ticker baskets, event "
                "same-sample retuning, broad universe expansion, active-position "
                "sector caps, breakout-only slot ranking, or sparse LLM soft-ranking."
            ),
        },
        "parameters": {
            "single_causal_variable": (
                "ATR target width for otherwise-default SPY-relative leader signals"
            ),
            "variants": VARIANTS,
            "best_variant": best_variant,
            "touched_signal_definition": (
                "spy_relative_leader is True and target_width_applied is absent"
            ),
            "locked_variables": [
                "candidate universe",
                "signal generation",
                "entry filters",
                "entry ordering",
                "risk sizing multipliers",
                "position caps",
                "add-ons",
                "Technology trend target width",
                "commodity/gold trend target width",
                "LLM replay",
                "news replay",
                "event sleeves",
            ],
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
                "Requires EV improvement in at least two windows plus material "
                "EV, PnL, Sharpe, or drawdown improvement."
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
                "If accepted, implement in risk_engine.enrich_signals so run.py "
                "and backtester.py share the same target policy, then add tests."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": "Production-aligned LLM soft-ranking samples remain sparse.",
        },
        "why_not_other_attractive_points": [
            "Event overlay needs closed forward paper outcomes before live promotion.",
            "LLM soft-ranking lacks enough production-aligned training/replay samples.",
            "Static universe expansion has repeatedly increased noise.",
            "Nearby add-on cap, target cap, and sector cap tuning lacks new evidence.",
        ],
        "unchanged_modules": [
            "signal_engine",
            "production entry filters",
            "risk sizing multipliers",
            "follow-through add-ons",
            "LLM/news veto layers",
            "universe registry",
        ],
        "risk_of_change": (
            "A wider target can let profitable SPY leaders round-trip before "
            "hitting target, especially in weaker or rotation-heavy tapes."
        ),
        "decision_rationale": (
            "Promote only if the best variant clears canonical three-window Gate 4; "
            "otherwise record as a non-repeat target-width failure."
        ),
        "rejection_reason": None if gate4_passed else (
            "Best variant failed material three-window Gate 4 for default-target SPY-relative leaders."
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
        / f"{EXPERIMENT_ID}_spy_leader_target_width.md"
    )
    result_path = exp_dir / "spy_leader_target_width.json"

    related_files = [
        str(result_path.relative_to(REPO_ROOT)).replace("\\", "/"),
        str(log_path.relative_to(REPO_ROOT)).replace("\\", "/"),
        str(ticket_path.relative_to(REPO_ROOT)).replace("\\", "/"),
        str(artifact_path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "quant/experiments/exp_20260506_006_spy_leader_target_width.py",
    ]
    payload["related_files"] = related_files

    _write_json(result_path, payload)
    _write_json(log_path, payload)
    _write_json(
        ticket_path,
        {
            "experiment_id": EXPERIMENT_ID,
            "lane": "alpha_search",
            "status": decision,
            "hypothesis": payload["hypothesis"],
            "best_variant": best_variant,
            "aggregate": aggregate,
            "next_action": (
                "Promote through shared risk_engine policy and tests."
                if gate4_passed
                else "Do not repeat nearby SPY-leader target widths without new forward or event/news evidence."
            ),
        },
    )

    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    with artifact_path.open("w", encoding="utf-8") as handle:
        handle.write(f"# {EXPERIMENT_ID}: SPY-Relative Leader Target Width\n\n")
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
            f"`{aggregate['ev_windows_improved']}` / `{aggregate['ev_windows_regressed']}`\n"
        )
        handle.write(
            "- Touched trades across windows: "
            f"`{aggregate['touched_trade_count_sum']}`\n\n"
        )
        handle.write("| Window | EV delta | PnL delta | Sharpe daily delta | Max DD delta | Touched trades |\n")
        handle.write("| --- | ---: | ---: | ---: | ---: | ---: |\n")
        for label in WINDOWS:
            window_payload = best_summary["by_window"][label]
            delta = window_payload["delta"]
            handle.write(
                f"| `{label}` | `{delta.get('expected_value_score')}` | "
                f"`{delta.get('total_pnl')}` | `{delta.get('sharpe_daily')}` | "
                f"`{delta.get('max_drawdown_pct')}` | "
                f"`{window_payload['touched_trade_count']}` |\n"
            )
        handle.write("\n")
        if gate4_passed:
            handle.write(
                "Promotion requires moving the override into shared risk_engine "
                "policy used by both production and backtester.\n"
            )
        else:
            handle.write(
                "Do not repeat nearby default-target SPY-relative leader "
                "target-width variants without new forward or event/news evidence.\n"
            )

    _append_jsonl(REPO_ROOT / "docs" / "experiment_log.jsonl", payload)

    note = (
        f"- {EXPERIMENT_ID}: default-target SPY-relative leader target-width "
        f"{decision}; best `{best_variant}` had aggregate EV delta "
        f"`{aggregate['expected_value_score_delta_sum']}` and PnL delta "
        f"`${aggregate['total_pnl_delta_sum']}` across the canonical three windows. "
        + (
            "Promote only through shared risk_engine policy."
            if gate4_passed
            else "Do not repeat nearby SPY-leader target widths without new forward or event/news evidence."
        )
    )
    _append_playbook_note(REPO_ROOT / "docs" / "alpha-optimization-playbook.md", note)

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": decision,
                "best_variant": best_variant,
                "aggregate": aggregate,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
