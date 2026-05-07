"""exp-20260505-012: compound severe-haircut skip replay.

Alpha search. This tests one allocation variable: when existing shared sizing
rules have already stacked multiple severe 0.25x risk haircuts on the same
candidate, should that candidate be treated as no-trade rather than consuming
a small entry slot.

The experiment deliberately does not change production policy. If it passes,
the follow-up must move the rule into shared production/backtest policy before
orders can change.
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

import portfolio_engine as pe  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260505-012"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "compound_haircut_skip.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_compound_haircut_skip.md"
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

VARIANTS = OrderedDict([
    ("compound_2plus_025x_skip", {"min_severe_haircuts": 2}),
    ("compound_3plus_025x_skip", {"min_severe_haircuts": 3}),
])

NEUTRAL_SIZING_KEYS = {
    "portfolio_value_usd",
    "risk_pct",
    "risk_amount_usd",
    "entry_price",
    "stop_price",
    "risk_per_share",
    "net_risk_per_share",
    "shares_to_buy",
    "position_value_usd",
    "position_pct_of_portfolio",
    "base_risk_pct",
    "max_position_pct_applied",
    "trade_quality_score",
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


def _severe_haircut_keys(sizing: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    for key, value in sizing.items():
        if key in NEUTRAL_SIZING_KEYS or not key.endswith("_multiplier_applied"):
            continue
        try:
            value = float(value)
        except (TypeError, ValueError):
            continue
        if 0 < value <= 0.25:
            keys.append(key)
    return sorted(keys)


def _zero_sizing(original: dict[str, Any], severe_keys: list[str]) -> dict[str, Any]:
    zeroed = dict(original)
    zeroed["compound_haircut_skip_applied"] = 0.0
    zeroed["compound_haircut_skip_key_count"] = len(severe_keys)
    zeroed["compound_haircut_skip_keys"] = severe_keys
    zeroed["risk_pct"] = 0.0
    zeroed["risk_amount_usd"] = 0.0
    zeroed["shares_to_buy"] = 0
    zeroed["position_value_usd"] = 0.0
    zeroed["position_pct_of_portfolio"] = 0.0
    return zeroed


def _make_size_signals(original_size_signals, min_severe_haircuts: int):
    touched: list[dict[str, Any]] = []

    def size_signals(signals, portfolio_value, risk_pct=None):
        sized = original_size_signals(signals, portfolio_value, risk_pct=risk_pct)
        for sig in sized:
            sizing = sig.get("sizing") or {}
            if (sizing.get("shares_to_buy") or 0) <= 0:
                continue
            severe_keys = _severe_haircut_keys(sizing)
            if len(severe_keys) < min_severe_haircuts:
                continue
            touched.append({
                "ticker": sig.get("ticker"),
                "strategy": sig.get("strategy"),
                "sector": sig.get("sector"),
                "signal_date": sig.get("signal_date") or sig.get("date"),
                "entry_price": sig.get("entry_price"),
                "stop_price": sig.get("stop_price"),
                "risk_pct_before": sizing.get("risk_pct"),
                "shares_before": sizing.get("shares_to_buy"),
                "severe_haircut_keys": severe_keys,
            })
            sig["sizing"] = _zero_sizing(sizing, severe_keys)
        return sized

    size_signals.touched = touched  # type: ignore[attr-defined]
    return size_signals


def _run_window(window: dict[str, str], variant: dict[str, Any] | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    original_size_signals = pe.size_signals
    touched: list[dict[str, Any]] = []
    if variant is not None:
        patched = _make_size_signals(
            original_size_signals,
            int(variant["min_severe_haircuts"]),
        )
        pe.size_signals = patched
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
        if variant is not None:
            touched = list(getattr(pe.size_signals, "touched", []))
        return result, touched
    finally:
        pe.size_signals = original_size_signals


def _run_baselines() -> OrderedDict[str, dict[str, Any]]:
    rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for label, window in WINDOWS.items():
        print(f"[{label}] baseline")
        result, _ = _run_window(window)
        rows[label] = {"raw": result, "metrics": _metrics(result)}
    return rows


def _run_variant(name: str, variant: dict[str, Any], baselines: OrderedDict[str, dict[str, Any]]) -> dict[str, Any]:
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
            "compound_skip_candidate_count": len(touched),
            "compound_skip_candidates": touched,
        }
        print(
            f"[{label}] {name} EV={delta['expected_value_score']:+.4f} "
            f"PnL={delta['total_pnl']:+.2f} skipped={len(touched)}"
        )
    aggregate = _aggregate(rows)
    return {
        "parameters": variant,
        "rows": rows,
        "aggregate": aggregate,
        "gate4_passed": _gate4_passed(aggregate),
    }


def _aggregate(rows: OrderedDict[str, dict[str, Any]]) -> dict[str, Any]:
    ev_before = sum(float(row["before"]["expected_value_score"] or 0.0) for row in rows.values())
    ev_delta = sum(float(row["delta"]["expected_value_score"] or 0.0) for row in rows.values())
    pnl_before = sum(float(row["before"]["total_pnl"] or 0.0) for row in rows.values())
    pnl_delta = sum(float(row["delta"]["total_pnl"] or 0.0) for row in rows.values())
    return {
        "baseline_expected_value_score_sum": _round(ev_before, 6),
        "expected_value_score_delta_sum": _round(ev_delta, 6),
        "expected_value_score_delta_pct": _round(ev_delta / ev_before if ev_before else 0.0, 6),
        "baseline_total_pnl_sum": _round(pnl_before, 2),
        "total_pnl_delta_sum": _round(pnl_delta, 2),
        "total_pnl_delta_pct": _round(pnl_delta / pnl_before if pnl_before else 0.0, 6),
        "ev_windows_improved": sum(
            1 for row in rows.values() if row["delta"].get("expected_value_score", 0) > 0
        ),
        "ev_windows_regressed": sum(
            1 for row in rows.values() if row["delta"].get("expected_value_score", 0) < 0
        ),
        "pnl_windows_improved": sum(
            1 for row in rows.values() if row["delta"].get("total_pnl", 0) > 0
        ),
        "pnl_windows_regressed": sum(
            1 for row in rows.values() if row["delta"].get("total_pnl", 0) < 0
        ),
        "max_drawdown_delta_max": _round(
            max(row["delta"].get("max_drawdown_pct", 0.0) for row in rows.values()), 6
        ),
        "max_drawdown_delta_min": _round(
            min(row["delta"].get("max_drawdown_pct", 0.0) for row in rows.values()), 6
        ),
        "sharpe_daily_delta_max": _round(
            max(row["delta"].get("sharpe_daily", 0.0) for row in rows.values()), 6
        ),
        "trade_count_delta_sum": sum(row["delta"].get("trade_count", 0) for row in rows.values()),
        "win_rate_delta_min": _round(
            min(row["delta"].get("win_rate", 0.0) for row in rows.values()), 6
        ),
        "compound_skip_candidate_count_sum": sum(
            row["compound_skip_candidate_count"] for row in rows.values()
        ),
    }


def _gate4_passed(aggregate: dict[str, Any]) -> bool:
    material = (
        aggregate["expected_value_score_delta_pct"] > 0.10
        or aggregate["sharpe_daily_delta_max"] > 0.10
        or aggregate["max_drawdown_delta_max"] < -0.01
        or aggregate["total_pnl_delta_pct"] > 0.05
        or (
            aggregate["trade_count_delta_sum"] > 0
            and aggregate["win_rate_delta_min"] >= 0
        )
    )
    return (
        bool(material)
        and aggregate["ev_windows_improved"] >= 2
        and aggregate["ev_windows_regressed"] == 0
    )


def _make_payload(
    baselines: OrderedDict[str, dict[str, Any]],
    variants: OrderedDict[str, dict[str, Any]],
) -> dict[str, Any]:
    ranked = sorted(
        variants.items(),
        key=lambda item: (
            item[1]["aggregate"]["expected_value_score_delta_sum"],
            item[1]["aggregate"]["total_pnl_delta_sum"],
        ),
        reverse=True,
    )
    best_name, best = ranked[0]
    accepted = bool(best["gate4_passed"])
    generated_at = datetime.now(timezone.utc).isoformat()
    return {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": generated_at,
        "status": "accepted" if accepted else "rejected",
        "decision": "accepted" if accepted else "rejected",
        "lane": "alpha_search",
        "change_type": "allocation_entry_quality_existing_risk_tags",
        "mechanism_family": "compound_severe_haircut_skip",
        "hypothesis": (
            "Candidates with multiple independent severe 0.25x risk haircuts "
            "may be too low quality for scarce entry slots. Treating only the "
            "compound severe-haircut cohort as no-trade could improve EV while "
            "preserving single-haircut winners that prior audits kept alive."
        ),
        "alpha_hypothesis": {
            "category": "entry / allocation",
            "why_this_now": (
                "LLM soft-ranking and event-bundle promotion are sample-limited. "
                "This uses existing shared risk tags, not new ticker noise, "
                "and directly tests allocation inside the current A/B stack."
            ),
        },
        "historical_experiment_check": {
            "similar_prior_results": {
                "trend_tech_gap_0x_family": (
                    "Earlier full bans of single Technology gap-risk pockets were "
                    "worse than 0.25x. This retry is narrower: it skips only when "
                    "multiple severe risk tags stack on the same candidate."
                ),
                "exp-20260505-005": (
                    "Dropping zero-share candidates before planning failed. This "
                    "does not target non-positionable rows; it tests already "
                    "positionable candidates with compound severe risk evidence."
                ),
                "exp-20260505-009/011": (
                    "Broad and narrow ticker-pool growth failed. This does not "
                    "add universe names."
                ),
            },
            "mechanism_insight_check": (
                "Does not violate recent bans on broad universe expansion, "
                "sector caps, event-bundle retuning, LLM prompt tweaks, or "
                "nearby add-on/target sweeps."
            ),
        },
        "parameters": {
            "single_causal_variable": "minimum count of existing severe 0.25x sizing haircuts required to zero-size a signal",
            "variants": VARIANTS,
            "best_variant": best_name,
            "severe_haircut_definition": "sizing key ending in _multiplier_applied with 0 < value <= 0.25",
            "locked_variables": [
                "universe",
                "signal generation",
                "risk tag definitions",
                "numeric risk multipliers",
                "entry ordering",
                "entry open cancels",
                "exits",
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
                "Requires material EV/PnL/Sharpe/drawdown/trade-count improvement, "
                "EV improvement in at least two fixed windows, and no EV-regressed window."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": True,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted later, implement through shared portfolio/production "
                "policy and expose the skip reason in run.py before changing orders."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "blocker_relation": (
                "LLM ranking remains sample-limited; this tests deterministic "
                "allocation without treating LLM as the problem."
            ),
        },
        "rejection_reason": None if accepted else (
            "Compound severe-haircut skipping did not clear the three-window "
            "materiality and stability gate."
        ),
        "next_retry_requires": [
            "Do not retry nearby severe-haircut count thresholds without candidate-level replacement evidence.",
            "A valid retry needs an orthogonal discriminator showing compound haircut rows displace better candidates.",
            "Any positive retry must be implemented as shared run/backtester policy before promotion.",
        ],
        "risk_of_change": (
            "May skip small-position winners that previous experiments intentionally "
            "kept alive, especially single-name Technology momentum rebounds."
        ),
        "why_not_other_attractive_points": {
            "LLM_soft_ranking": "Still production-sample limited.",
            "event_bundle_promotion": "Needs closed forward paper outcomes.",
            "universe_expansion": "Broad and narrow static expansions just failed.",
            "add_on_or_target_tuning": "Recent mechanism insights explicitly ban nearby sweeps without new evidence.",
        },
        "related_files": [
            "quant/experiments/exp_20260505_012_compound_haircut_skip.py",
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
        f"# {EXPERIMENT_ID} Compound Severe-haircut Skip",
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
        f"- skipped candidate count: `{aggregate['compound_skip_candidate_count_sum']}`",
        "",
        "## Three-window Deltas",
        "",
        "| Window | EV delta | PnL delta | SharpeD delta | DD delta | WR delta | Trades delta | Skipped |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, row in payload["variants"][payload["best_variant"]]["rows"].items():
        delta = row["delta"]
        lines.append(
            f"| `{label}` | {delta['expected_value_score']:+.4f} | "
            f"{delta['total_pnl']:+.2f} | {delta['sharpe_daily']:+.2f} | "
            f"{delta['max_drawdown_pct']:+.4f} | {delta['win_rate']:+.4f} | "
            f"{delta['trade_count']:+d} | {row['compound_skip_candidate_count']} |"
        )
    lines.extend([
        "",
        "## Production Parity",
        "",
        "No production order path changed. A positive retry would need a shared policy helper, a run.py adapter that exposes the skip reason, and a parity test.",
        "",
    ])
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines), encoding="utf-8")


def _update_playbook(payload: dict[str, Any]) -> None:
    marker = "## Recent mechanism insights"
    aggregate = payload["delta_metrics"]["aggregate"]
    entry = (
        "\n"
        f"- `{EXPERIMENT_ID}` ({payload['decision']}): Compound severe-haircut "
        "skip was tested by zero-sizing signals with multiple existing 0.25x "
        f"risk tags. Best `{payload['best_variant']}` aggregate EV delta "
        f"{aggregate['expected_value_score_delta_sum']} "
        f"({aggregate['expected_value_score_delta_pct']:.2%}), PnL delta "
        f"${aggregate['total_pnl_delta_sum']}. Do not retry nearby severe-tag "
        "count thresholds without candidate-level replacement evidence.\n"
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
    import backtester as bt

    if "compound_haircut_skip_applied" not in bt.SIZING_MULTIPLIER_KEYS:
        bt.SIZING_MULTIPLIER_KEYS = (
            *bt.SIZING_MULTIPLIER_KEYS,
            "compound_haircut_skip_applied",
        )

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
        "title": "Compound haircut skip",
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
