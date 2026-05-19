"""exp-20260505-015: Consumer Discretionary trend target-width replay.

Alpha search. Tests one lifecycle variable: whether `trend_long | Consumer
Discretionary` entries are target-clipped by the current regime-aware target
path and should receive a modest wider ATR target.

No production order path is changed by this runner. A positive result must be
promoted through shared run/backtester policy before it can affect live orders.
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

import risk_engine as risk  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260505-015"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "consumer_trend_target_width.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_consumer_trend_target_width.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
PLAYBOOK = REPO_ROOT / "docs" / "alpha-optimization-playbook.md"

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

TARGET_FILTER = {
    "sector": "Consumer Discretionary",
    "strategy": "trend_long",
}

VARIANTS = OrderedDict([
    ("consumer_trend_target_5_0atr", {"target_atr_mult": 5.0}),
    ("consumer_trend_target_5_5atr", {"target_atr_mult": 5.5}),
])

TARGET_KEY = "consumer_trend_target_width_applied"


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


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "sharpe_daily": _round(result.get("sharpe_daily"), 2),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "total_return_pct": _round(benchmarks.get("strategy_total_return_pct"), 4),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": _round(result.get("survival_rate"), 4),
        "converged": bool((result.get("convergence") or {}).get("converged")),
        "entry_reason_counts": (
            result.get("entry_execution_attribution") or {}
        ).get("reason_counts") or {},
    }


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "expected_value_score",
        "sharpe_daily",
        "total_pnl",
        "total_return_pct",
        "max_drawdown_pct",
        "win_rate",
        "trade_count",
        "signals_generated",
        "signals_survived",
        "survival_rate",
    )
    out: dict[str, Any] = {}
    for key in keys:
        before_value = before.get(key)
        after_value = after.get(key)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            if key in {"trade_count", "signals_generated", "signals_survived"}:
                out[key] = int(after_value - before_value)
            else:
                out[key] = _round(after_value - before_value, 6)
    return out


def _candidate_matches(sig: dict[str, Any]) -> bool:
    return (
        sig.get("strategy") == TARGET_FILTER["strategy"]
        and sig.get("sector") == TARGET_FILTER["sector"]
    )


def _make_enrich_signals(original_enrich, target_mult: float):
    touched: list[dict[str, Any]] = []

    def enrich_signals(signals, features_dict, atr_target_mult=None):
        enriched = original_enrich(
            signals,
            features_dict,
            atr_target_mult=atr_target_mult,
        )
        for idx, sig in enumerate(enriched):
            if not _candidate_matches(sig):
                continue
            ticker = sig.get("ticker")
            features = (features_dict or {}).get(ticker) or {}
            atr = features.get("atr")
            if not isinstance(atr, (int, float)) or atr <= 0:
                continue
            before_target = sig.get("target_price")
            before_mult = sig.get("target_mult_used")
            retargeted = risk._retarget_signal_with_atr_mult(sig, atr, target_mult)
            retargeted[TARGET_KEY] = target_mult
            enriched[idx] = retargeted
            touched.append({
                "ticker": ticker,
                "strategy": sig.get("strategy"),
                "sector": sig.get("sector"),
                "signal_date": sig.get("signal_date") or sig.get("date"),
                "entry_price": sig.get("entry_price"),
                "stop_price": sig.get("stop_price"),
                "target_before": before_target,
                "target_after": retargeted.get("target_price"),
                "target_mult_before": before_mult,
                "target_mult_after": target_mult,
                "atr": _round(atr, 4),
                "trade_quality_score": sig.get("trade_quality_score"),
                "regime_exit_bucket": sig.get("regime_exit_bucket"),
                "regime_exit_score": sig.get("regime_exit_score"),
            })
        return enriched

    enrich_signals.touched = touched  # type: ignore[attr-defined]
    return enrich_signals


def _run_window(
    window: dict[str, str],
    variant: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    original_enrich = risk.enrich_signals
    if variant is not None:
        risk.enrich_signals = _make_enrich_signals(
            original_enrich,
            float(variant["target_atr_mult"]),
        )
    try:
        result = BacktestEngine(
            sorted(get_universe()),
            start=window["start"],
            end=window["end"],
            config={"REGIME_AWARE_EXIT": True},
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
        ).run()
        touched = (
            list(getattr(risk.enrich_signals, "touched", []))
            if variant is not None
            else []
        )
        return result, touched
    finally:
        risk.enrich_signals = original_enrich


def _consumer_trades(result: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for trade in result.get("trades") or []:
        if (
            trade.get("strategy") == TARGET_FILTER["strategy"]
            and trade.get("sector") == TARGET_FILTER["sector"]
        ):
            rows.append({
                "trade_key": trade.get("trade_key"),
                "ticker": trade.get("ticker"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "exit_reason": trade.get("exit_reason"),
                "pnl": _round(trade.get("pnl"), 2),
                "pnl_pct_net": _round(trade.get("pnl_pct_net"), 6),
                "target_mult_used": trade.get("target_mult_used"),
                "entry_price": trade.get("entry_price"),
                "exit_price": trade.get("exit_price"),
                "addon_count": trade.get("addon_count"),
                "sizing_multipliers": trade.get("sizing_multipliers") or {},
            })
    return rows


def _run_baselines() -> OrderedDict[str, dict[str, Any]]:
    rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for label, window in WINDOWS.items():
        print(f"[{label}] baseline")
        result, _ = _run_window(window)
        rows[label] = {
            "window": window,
            "metrics": _metrics(result),
            "consumer_trend_trades": _consumer_trades(result),
        }
    return rows


def _run_variant(
    name: str,
    variant: dict[str, Any],
    baselines: OrderedDict[str, dict[str, Any]],
) -> dict[str, Any]:
    rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for label, window in WINDOWS.items():
        print(f"[{label}] {name}")
        after_result, touched = _run_window(window, variant)
        before = baselines[label]["metrics"]
        after = _metrics(after_result)
        delta = _delta(after, before)
        rows[label] = {
            "window": window,
            "before": before,
            "after": after,
            "delta": delta,
            "consumer_trend_target_candidate_count": len(touched),
            "consumer_trend_target_candidates": touched,
            "consumer_trend_trades_before": baselines[label]["consumer_trend_trades"],
            "consumer_trend_trades_after": _consumer_trades(after_result),
        }
        print(
            f"[{label}] {name} EV={delta['expected_value_score']:+.4f} "
            f"PnL={delta['total_pnl']:+.2f} touched={len(touched)}"
        )
    return {"variant": variant, "rows": rows, "aggregate": _aggregate(rows)}


def _aggregate(rows: OrderedDict[str, dict[str, Any]]) -> dict[str, Any]:
    baseline_ev = sum(row["before"]["expected_value_score"] for row in rows.values())
    baseline_pnl = sum(row["before"]["total_pnl"] for row in rows.values())
    ev_delta = sum(row["delta"]["expected_value_score"] for row in rows.values())
    pnl_delta = sum(row["delta"]["total_pnl"] for row in rows.values())
    sharpe_delta_max = max(row["delta"]["sharpe_daily"] for row in rows.values())
    drawdown_delta_min = min(row["delta"]["max_drawdown_pct"] for row in rows.values())
    drawdown_delta_max = max(row["delta"]["max_drawdown_pct"] for row in rows.values())
    trade_delta = sum(row["delta"]["trade_count"] for row in rows.values())
    win_rate_delta_min = min(row["delta"]["win_rate"] for row in rows.values())
    return {
        "baseline_expected_value_score_sum": _round(baseline_ev, 4),
        "expected_value_score_delta_sum": _round(ev_delta, 4),
        "expected_value_score_delta_pct": _round(ev_delta / baseline_ev, 6)
        if baseline_ev else None,
        "baseline_total_pnl_sum": _round(baseline_pnl, 2),
        "total_pnl_delta_sum": _round(pnl_delta, 2),
        "total_pnl_delta_pct": _round(pnl_delta / baseline_pnl, 6)
        if baseline_pnl else None,
        "ev_windows_improved": sum(
            1 for row in rows.values() if row["delta"]["expected_value_score"] > 0
        ),
        "ev_windows_regressed": sum(
            1 for row in rows.values() if row["delta"]["expected_value_score"] < 0
        ),
        "pnl_windows_improved": sum(
            1 for row in rows.values() if row["delta"]["total_pnl"] > 0
        ),
        "pnl_windows_regressed": sum(
            1 for row in rows.values() if row["delta"]["total_pnl"] < 0
        ),
        "sharpe_delta_max": _round(sharpe_delta_max, 4),
        "drawdown_delta_min": _round(drawdown_delta_min, 4),
        "drawdown_delta_max": _round(drawdown_delta_max, 4),
        "trade_count_delta_sum": trade_delta,
        "win_rate_delta_min": _round(win_rate_delta_min, 4),
        "consumer_trend_target_candidate_count_sum": sum(
            row["consumer_trend_target_candidate_count"] for row in rows.values()
        ),
    }


def _gate4_passed(aggregate: dict[str, Any]) -> bool:
    ev_pct = aggregate.get("expected_value_score_delta_pct") or 0.0
    pnl_pct = aggregate.get("total_pnl_delta_pct") or 0.0
    multi_window_ok = (
        aggregate["ev_windows_improved"] >= 2
        and aggregate["ev_windows_regressed"] <= 1
        and aggregate["drawdown_delta_max"] <= 0.01
    )
    material = (
        ev_pct > 0.10
        or pnl_pct > 0.05
        or aggregate["sharpe_delta_max"] > 0.10
        or aggregate["drawdown_delta_min"] < -0.01
        or (
            aggregate["trade_count_delta_sum"] > 0
            and aggregate["win_rate_delta_min"] >= 0
        )
    )
    return bool(multi_window_ok and material)


def _best_variant(variants: OrderedDict[str, dict[str, Any]]) -> str:
    return max(
        variants,
        key=lambda name: (
            variants[name]["aggregate"]["expected_value_score_delta_sum"],
            variants[name]["aggregate"]["total_pnl_delta_sum"],
            -variants[name]["aggregate"]["drawdown_delta_max"],
        ),
    )


def _make_payload(
    baselines: OrderedDict[str, dict[str, Any]],
    variants: OrderedDict[str, dict[str, Any]],
) -> dict[str, Any]:
    best_name = _best_variant(variants)
    best = variants[best_name]
    accepted = _gate4_passed(best["aggregate"])
    return {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "accepted" if accepted else "rejected",
        "decision": "accepted" if accepted else "rejected",
        "hypothesis": (
            "`trend_long | Consumer Discretionary` winners may be target-clipped "
            "by the current regime-aware target path. A modest 5.0-5.5 ATR target "
            "could improve winner capture without changing entries, sizing, "
            "candidate pool, or LLM/news behavior."
        ),
        "alpha_hypothesis": {
            "category": "exit / lifecycle",
            "statement": (
                "Consumer Discretionary trend alpha may need slightly more room "
                "than the default target path, similar in shape to accepted "
                "Technology/Commodity trend target repairs but tested as its own "
                "sector-specific cohort."
            ),
            "why_now": (
                "LLM soft-ranking remains production-sample limited; event "
                "bundles need forward outcomes; broad and narrow universe "
                "expansions just failed. A cohort audit showed Consumer "
                "Discretionary trend winners in the older window, and no direct "
                "Consumer trend target-width experiment was found in the recent "
                "mechanism log."
            ),
        },
        "change_type": "alpha_search_exit_lifecycle_sweep",
        "component": "quant/experiments/exp_20260505_015_consumer_trend_target_width.py",
        "historical_experiment_check": {
            "similar_prior_results": {
                "exp-20260501-021": (
                    "Consumer near-high DTE window widening was rejected as inert; "
                    "this experiment changes target width, not event-distance "
                    "risk sizing."
                ),
                "exp-20260505-011": (
                    "Narrow consumer digital platform core expansion was rejected "
                    "for direct promotion; this experiment does not add tickers "
                    "or change universe governance."
                ),
                "exp-20260427-033 / exp-20260501-020": (
                    "Financials target widening failed, so this run does not "
                    "generalize target widening across sectors; it isolates "
                    "Consumer Discretionary trend only."
                ),
                "exp-20260502-023": (
                    "SPY-relative leader target floors failed, so this run avoids "
                    "leader-wide target floors and tests a fixed sector/strategy "
                    "cohort instead."
                ),
            },
            "mechanism_insight_check": (
                "Avoids current no-repeat zones: no LLM soft-ranking, no event "
                "bundle promotion, no broad/static universe expansion, no Form 4 "
                "overlay, no Financials/Energy/Commodity/Technology target retry, "
                "and no SPY-leader target floor."
            ),
        },
        "parameters": {
            "single_causal_variable": (
                "target ATR multiple for trend_long Consumer Discretionary signals"
            ),
            "target_filter": TARGET_FILTER,
            "variants": VARIANTS,
            "best_variant": best_name,
            "locked_variables": [
                "universe",
                "signal generation",
                "sector map",
                "entry ordering",
                "entry open cancels",
                "all sizing and risk multipliers",
                "add-ons",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "LLM/news replay",
                "event sleeves",
            ],
        },
        "date_range": {
            label: f"{window['start']} -> {window['end']}"
            for label, window in WINDOWS.items()
        },
        "snapshots": {label: window["snapshot"] for label, window in WINDOWS.items()},
        "market_regime_summary": {
            label: window["state_note"] for label, window in WINDOWS.items()
        },
        "before_metrics": {
            label: row["metrics"] for label, row in baselines.items()
        },
        "after_metrics": {
            label: row["after"] for label, row in best["rows"].items()
        },
        "delta_metrics": {
            "by_window": {label: row["delta"] for label, row in best["rows"].items()},
            "aggregate": best["aggregate"],
        },
        "variants": variants,
        "best_variant": best_name,
        "gate4": {
            "passed": accepted,
            "basis": (
                "Requires material Gate 4 improvement plus multi-window stability "
                "on the three fixed backtesting.md windows."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": True,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted for trading, add a shared target-width constant/helper "
                "inside risk_engine/constants and cover it from both run.py and "
                "backtester.py before live orders change."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "blocker_relation": (
                "LLM soft-ranking remains sample-limited; this tests deterministic "
                "exit lifecycle behavior without weakening or blaming the LLM layer."
            ),
        },
        "rejection_reason": None if accepted else (
            "Consumer Discretionary trend target widening did not clear the "
            "three-window materiality and stability gate."
        ),
        "next_retry_requires": [
            "Do not retry nearby Consumer Discretionary trend target widths without a new event/state discriminator.",
            "A valid retry needs forward evidence or a non-price lifecycle feature showing which Consumer trend winners deserve more room.",
            "Any positive retry must be promoted through shared run/backtester policy before live orders change.",
        ],
        "risk_of_change": (
            "May delay exits in rotation-heavy or consumer-specific drawdown paths, "
            "turning target winners into givebacks without adding new entry quality."
        ),
        "why_not_other_attractive_points": {
            "LLM_soft_ranking": "Still production-sample limited.",
            "event_bundle_promotion": "Needs closed forward paper outcomes.",
            "universe_expansion": "Broad and narrow static expansions just failed.",
            "Form4_overlay": "Recent sale-pressure and purchase-overlap work lacks enough touched trades.",
            "Financials_or_Energy_targets": "Recent mechanism insights explicitly reject nearby target-width retries.",
        },
        "related_files": [
            "quant/experiments/exp_20260505_015_consumer_trend_target_width.py",
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "docs/experiment_log.jsonl",
            "docs/alpha-optimization-playbook.md",
        ],
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    kept: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                existing = json.loads(line)
            except json.JSONDecodeError:
                kept.append(line)
                continue
            if existing.get("experiment_id") != payload["experiment_id"]:
                kept.append(line)
    kept.append(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def _write_artifact(payload: dict[str, Any]) -> None:
    aggregate = payload["delta_metrics"]["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} Consumer Trend Target Width",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Gate 4",
        "",
        f"- passed: `{payload['gate4']['passed']}`",
        f"- best_variant: `{payload['best_variant']}`",
        f"- EV delta sum: `{aggregate['expected_value_score_delta_sum']:+.4f}` "
        f"({aggregate['expected_value_score_delta_pct']:+.2%})",
        f"- PnL delta sum: `${aggregate['total_pnl_delta_sum']:+,.2f}` "
        f"({aggregate['total_pnl_delta_pct']:+.2%})",
        f"- EV windows improved/regressed: `{aggregate['ev_windows_improved']}` / `{aggregate['ev_windows_regressed']}`",
        f"- touched candidate count: `{aggregate['consumer_trend_target_candidate_count_sum']}`",
        "",
        "## Three-window Deltas",
        "",
        "| Window | EV delta | PnL delta | SharpeD delta | DD delta | WR delta | Trades delta | Touched |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, row in payload["variants"][payload["best_variant"]]["rows"].items():
        delta = row["delta"]
        lines.append(
            f"| `{label}` | {delta['expected_value_score']:+.4f} | "
            f"{delta['total_pnl']:+.2f} | {delta['sharpe_daily']:+.2f} | "
            f"{delta['max_drawdown_pct']:+.4f} | {delta['win_rate']:+.4f} | "
            f"{delta['trade_count']:+d} | {row['consumer_trend_target_candidate_count']} |"
        )
    lines.extend([
        "",
        "## Production Parity",
        "",
        "No production order path changed. A positive promotion requires a shared target-width constant/helper and a parity test before live orders can change.",
        "",
    ])
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines), encoding="utf-8")


def _update_playbook(payload: dict[str, Any]) -> None:
    marker = "## Recent mechanism insights"
    aggregate = payload["delta_metrics"]["aggregate"]
    entry = (
        "\n"
        f"- `{EXPERIMENT_ID}` ({payload['decision']}): Consumer Discretionary "
        "trend target-width replay tested 5.0ATR/5.5ATR targets for "
        f"`trend_long | Consumer Discretionary`. Best `{payload['best_variant']}` "
        f"aggregate EV delta {aggregate['expected_value_score_delta_sum']} "
        f"({aggregate['expected_value_score_delta_pct']:.2%}), PnL delta "
        f"${aggregate['total_pnl_delta_sum']}. Do not retry nearby Consumer "
        "trend target widths without a new event/state lifecycle discriminator "
        "or forward evidence.\n"
    )
    text = PLAYBOOK.read_text(encoding="utf-8")
    if f"`{EXPERIMENT_ID}`" in text:
        return
    if marker in text:
        text = text.replace(marker, marker + entry, 1)
    else:
        text = text + "\n" + marker + "\n" + entry
    PLAYBOOK.write_text(text, encoding="utf-8")


def main() -> int:
    baselines = _run_baselines()
    variants: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for name, variant in VARIANTS.items():
        variants[name] = _run_variant(name, variant, baselines)

    payload = _make_payload(baselines, variants)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(TICKET_JSON, {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": payload["generated_at"],
        "decision": payload["decision"],
        "title": "Consumer trend target width",
        "summary": f"Best {payload['best_variant']}; Gate4={payload['gate4']['passed']}",
        "best_variant": payload["best_variant"],
        "delta_metrics": payload["delta_metrics"]["aggregate"],
        "production_impact": payload["production_impact"],
        "log_file": str(LOG_JSON.relative_to(REPO_ROOT)),
    })
    _write_artifact(payload)
    _append_jsonl(EXPERIMENT_LOG_JSONL, payload)
    _update_playbook(payload)

    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "decision": payload["decision"],
        "best_variant": payload["best_variant"],
        "aggregate": payload["delta_metrics"]["aggregate"],
        "out_json": str(OUT_JSON.relative_to(REPO_ROOT)),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
