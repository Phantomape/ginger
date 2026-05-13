"""exp-20260513-009: signal-day close-location risk allocation.

Tests one causal variable on the current accepted core stack: a cap-aware
post-sizing scalar for already-qualified signals whose own signal-day close is
in the upper quartile of the daily range. This is a production-knowable
allocation scout, not an entry filter or ranking rule.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


EXPERIMENT_ID = "exp-20260513-009"
EXPERIMENT_SLUG = "signal_day_close_location_risk"
CLOSE_LOCATION_MIN = 0.75
MULTIPLIER_KEY = "signal_day_close_location_risk_multiplier_applied"
SCALARS = (1.05, 1.10, 1.15, 1.25)

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import backtester as backtester_module  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
import feature_layer  # noqa: E402
import portfolio_engine  # noqa: E402
import risk_engine  # noqa: E402
import exp_20260512_106_signal_day_sector_tape_risk as base  # noqa: E402


ADJUSTMENTS: list[dict[str, Any]] = []


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_safe(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=False, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _signal_day_close_location(ohlcv_data: Any) -> float | None:
    if ohlcv_data is None or len(ohlcv_data) < 1:
        return None
    row = ohlcv_data.iloc[-1]
    try:
        high = float(row["High"].item() if hasattr(row["High"], "item") else row["High"])
        low = float(row["Low"].item() if hasattr(row["Low"], "item") else row["Low"])
        close = float(row["Close"].item() if hasattr(row["Close"], "item") else row["Close"])
    except Exception:
        return None
    daily_range = high - low
    if daily_range <= 0:
        return None
    return round((close - low) / daily_range, 6)


def _make_compute_features_wrapper(
    original: Callable[..., dict[str, Any] | None],
) -> Callable[..., dict[str, Any] | None]:
    def wrapped(
        ticker: str,
        ohlcv_data: Any,
        earnings_data: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        features = original(ticker, ohlcv_data, earnings_data)
        if features is None:
            return None
        features = dict(features)
        features["signal_day_close_location"] = _signal_day_close_location(ohlcv_data)
        return features

    return wrapped


def _make_enrich_wrapper(
    original: Callable[..., list[dict[str, Any]]],
) -> Callable[..., list[dict[str, Any]]]:
    def wrapped(
        signals: list[dict[str, Any]],
        features_dict: dict[str, dict[str, Any]],
        atr_target_mult: float | None = None,
    ) -> list[dict[str, Any]]:
        enriched = original(signals, features_dict, atr_target_mult=atr_target_mult)
        for sig in enriched:
            ticker = sig.get("ticker")
            close_location = (features_dict.get(ticker) or {}).get("signal_day_close_location")
            sig["signal_day_close_location"] = close_location
            sig["signal_day_close_location_upper_quartile"] = (
                isinstance(close_location, (int, float))
                and close_location >= CLOSE_LOCATION_MIN
            )
        return enriched

    return wrapped


def _rescale_sizing(
    sig: dict[str, Any],
    sizing: dict[str, Any],
    scalar: float,
    portfolio_value: float,
) -> dict[str, Any]:
    shares = int(sizing.get("shares_to_buy") or 0)
    if shares <= 0:
        return sizing
    entry = float(sizing.get("entry_price") or sig.get("entry_price") or 0.0)
    if entry <= 0:
        return sizing
    max_position_pct = float(sizing.get("max_position_pct_applied") or 0.40)
    cap_shares = max(1, int(math.floor(portfolio_value * max_position_pct / entry)))
    desired_shares = max(shares, int(math.floor(shares * scalar)))
    new_shares = min(desired_shares, cap_shares)
    if new_shares <= shares:
        return sizing

    net_risk_per_share = float(sizing.get("net_risk_per_share") or 0.0)
    out = dict(sizing)
    out["shares_to_buy"] = new_shares
    out["position_value_usd"] = round(entry * new_shares, 2)
    out["position_pct_of_portfolio"] = (
        round((entry * new_shares) / portfolio_value, 4) if portfolio_value else 0.0
    )
    out["risk_amount_usd"] = round(net_risk_per_share * new_shares, 2)
    out["risk_pct"] = (net_risk_per_share * new_shares) / portfolio_value if portfolio_value else 0.0
    out["signal_day_close_location_baseline_shares"] = shares
    out["signal_day_close_location_desired_shares"] = desired_shares
    out["signal_day_close_location_cap_shares"] = cap_shares
    out[MULTIPLIER_KEY] = scalar
    return out


def _make_size_wrapper(
    original: Callable[..., list[dict[str, Any]]],
    scalar: float,
) -> Callable[..., list[dict[str, Any]]]:
    def wrapped(
        signals: list[dict[str, Any]],
        portfolio_value: float,
        risk_pct: float | None = None,
    ) -> list[dict[str, Any]]:
        sized = original(signals, portfolio_value, risk_pct=risk_pct)
        out = []
        for sig in sized:
            sizing = sig.get("sizing") or {}
            if (
                sig.get("signal_day_close_location_upper_quartile") is True
                and sig.get("strategy") in {"trend_long", "breakout_long"}
                and sizing.get("shares_to_buy")
            ):
                adjusted = _rescale_sizing(sig, sizing, scalar, portfolio_value)
                if adjusted is not sizing:
                    ADJUSTMENTS.append(
                        {
                            "ticker": sig.get("ticker"),
                            "strategy": sig.get("strategy"),
                            "sector": sig.get("sector"),
                            "signal_day_close_location": sig.get("signal_day_close_location"),
                            "signal_day_ticker_green_candle": sig.get(
                                "signal_day_ticker_green_candle"
                            ),
                            "baseline_shares": sizing.get("shares_to_buy"),
                            "new_shares": adjusted.get("shares_to_buy"),
                            "scalar": scalar,
                            "trade_quality_score": sig.get("trade_quality_score"),
                            "regime_exit_bucket": sig.get("regime_exit_bucket"),
                            "regime_exit_score": sig.get("regime_exit_score"),
                        }
                    )
                    sig = {**sig, "sizing": adjusted}
            out.append(sig)
        return out

    return wrapped


def _run_window(label: str, scalar: float | None) -> dict[str, Any]:
    spec = base.WINDOWS[label]
    universe = get_universe()
    original_compute_features = feature_layer.compute_features
    original_enrich = risk_engine.enrich_signals
    original_size = portfolio_engine.size_signals
    original_multiplier_keys = backtester_module.SIZING_MULTIPLIER_KEYS

    global ADJUSTMENTS
    ADJUSTMENTS = []

    if scalar is not None:
        feature_layer.compute_features = _make_compute_features_wrapper(original_compute_features)
        risk_engine.enrich_signals = _make_enrich_wrapper(original_enrich)
        portfolio_engine.size_signals = _make_size_wrapper(original_size, scalar)
        if MULTIPLIER_KEY not in backtester_module.SIZING_MULTIPLIER_KEYS:
            backtester_module.SIZING_MULTIPLIER_KEYS = (
                *backtester_module.SIZING_MULTIPLIER_KEYS,
                MULTIPLIER_KEY,
            )

    try:
        engine = BacktestEngine(
            universe,
            start=spec["start"],
            end=spec["end"],
            config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
            ohlcv_snapshot_path=str(REPO_ROOT / spec["snapshot"]),
        )
        result = engine.run()
    finally:
        feature_layer.compute_features = original_compute_features
        risk_engine.enrich_signals = original_enrich
        portfolio_engine.size_signals = original_size
        backtester_module.SIZING_MULTIPLIER_KEYS = original_multiplier_keys

    if result.get("error"):
        raise RuntimeError(f"{label} scalar={scalar} failed: {result['error']}")
    return {
        "metrics": base._metrics(result),
        "trades": result.get("trades") or [],
        "adjustments": list(ADJUSTMENTS),
        "sizing_rule_signal_attribution": result.get("sizing_rule_signal_attribution") or {},
        "sizing_rule_trade_attribution": result.get("sizing_rule_trade_attribution") or {},
    }


def _variant_name(scalar: float) -> str:
    return f"close_location_scalar_{str(scalar).replace('.', '_')}"


def _score_variant(variant: dict[str, Any]) -> tuple[int, float, float]:
    gate = variant["gate"]
    return (
        1 if gate["passed"] else 0,
        float(gate["aggregate_delta"].get("expected_value_score_sum") or 0.0),
        float(gate["aggregate_delta"].get("total_pnl_sum") or 0.0),
    )


def _markdown(payload: dict[str, Any]) -> str:
    rows = [
        "| Variant | Scalar | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse | Passed |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for name, variant in payload["variants"].items():
        gate = variant["gate"]
        rows.append(
            "| {name} | {scalar:.2f} | {ev:+.4f} | ${pnl:+,.2f} | {imp} | {reg} | {adj} | {dd:+.4f} | {passed} |".format(
                name=name,
                scalar=variant["scalar"],
                ev=gate["aggregate_delta"].get("expected_value_score_sum") or 0.0,
                pnl=gate["aggregate_delta"].get("total_pnl_sum") or 0.0,
                imp=len(gate["improved_windows"]),
                reg=len(gate["regressed_windows"]),
                adj=gate["adjusted_signal_count"],
                dd=gate["max_drawdown_delta_max"],
                passed=gate["passed"],
            )
        )
    selected = payload["variants"][payload["best_variant"]]
    detail_rows = [
        "",
        "## Selected Three-Window Result",
        "",
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = selected["after_metrics"][label]
        delta = selected["delta_metrics"]["by_window"][label]
        detail_rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {surv:.4f} | {adj} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                surv=after["survival_rate"],
                adj=len(selected["adjustments"][label]),
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Signal-Day Close-Location Risk",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: cap-aware post-sizing risk scalar for signals whose own signal-day close is in the upper quartile of the daily high-low range.",
            "",
            *rows,
            *detail_rows,
            "",
            "Production impact: replay-only scout. Positive promotion would require shared feature/risk/sizing implementation and parity coverage before any live/default behavior change.",
        ]
    )


def run() -> dict[str, Any]:
    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    before_runs = {label: _run_window(label, scalar=None) for label in base.WINDOWS}
    before_metrics = {label: run["metrics"] for label, run in before_runs.items()}
    aggregate_before = base._aggregate(before_metrics)

    variants: dict[str, Any] = {}
    for scalar in SCALARS:
        name = _variant_name(scalar)
        after_runs = {label: _run_window(label, scalar=scalar) for label in base.WINDOWS}
        after_metrics = {label: run["metrics"] for label, run in after_runs.items()}
        by_window_delta = {
            label: base._delta(after_metrics[label], before_metrics[label])
            for label in base.WINDOWS
        }
        aggregate_after = base._aggregate(after_metrics)
        aggregate_delta = base._aggregate_delta(aggregate_after, aggregate_before)
        improved = [
            label
            for label in base.WINDOWS
            if after_metrics[label]["expected_value_score"]
            > before_metrics[label]["expected_value_score"]
        ]
        regressed = [
            label
            for label in base.WINDOWS
            if after_metrics[label]["expected_value_score"]
            < before_metrics[label]["expected_value_score"]
        ]
        adjusted_count = sum(len(run["adjustments"]) for run in after_runs.values())
        max_drawdown_delta_max = max(
            float(by_window_delta[label].get("max_drawdown_pct") or 0.0)
            for label in base.WINDOWS
        )
        passed = (
            aggregate_delta["expected_value_score_sum"] > 0
            and aggregate_delta["total_pnl_sum"] > 0
            and len(improved) == 3
            and not regressed
            and max_drawdown_delta_max <= 0.005
            and aggregate_after["survival_rate_min"] >= 0.05
            and adjusted_count > 0
        )
        variants[name] = {
            "scalar": scalar,
            "after_metrics": after_metrics,
            "delta_metrics": {
                "by_window": by_window_delta,
                "aggregate_before": aggregate_before,
                "aggregate_after": aggregate_after,
                "aggregate_delta": aggregate_delta,
            },
            "adjustments": {label: run["adjustments"] for label, run in after_runs.items()},
            "changed_trades": {
                label: base._changed_trades(before_runs[label]["trades"], after_runs[label]["trades"])
                for label in base.WINDOWS
            },
            "sizing_attribution": {
                label: {
                    "signal": after_runs[label]["sizing_rule_signal_attribution"].get(MULTIPLIER_KEY),
                    "trade": after_runs[label]["sizing_rule_trade_attribution"].get(MULTIPLIER_KEY),
                }
                for label in base.WINDOWS
            },
            "gate": {
                "passed": passed,
                "improved_windows": improved,
                "regressed_windows": regressed,
                "adjusted_signal_count": adjusted_count,
                "max_drawdown_delta_max": max_drawdown_delta_max,
                "aggregate_delta": aggregate_delta,
            },
        }

    best_name, best_variant = max(variants.items(), key=lambda item: _score_variant(item[1]))
    decision = (
        "accepted_for_shared_policy_implementation"
        if best_variant["gate"]["passed"]
        else "rejected_signal_day_close_location_risk"
    )
    interpretation = (
        "Signal-day upper-quartile close-location risk allocation cleared the three-window gate and should be implemented through shared production/backtest policy before use."
        if best_variant["gate"]["passed"]
        else "Signal-day upper-quartile close-location risk allocation did not clear the canonical three-window gate; do not promote this state scalar without stronger evidence."
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "Signals whose own signal-day close lands in the upper quartile of the daily range may have stronger next-session follow-through than generic green candles; allocate slightly more risk rather than changing entries."
        ),
        "change_type": "risk_allocation_shadow",
        "changed_variable": "signal_day_close_location_risk_scalar",
        "single_causal_variable": (
            "cap-aware post-sizing scalar for signals whose signal-day close location value is >= 0.75"
        ),
        "parameters": {
            "close_location_definition": "(Close - Low) / (High - Low) on signal day",
            "close_location_min": CLOSE_LOCATION_MIN,
            "tested_scalars": list(SCALARS),
            "locked_variables": [
                "core universe",
                "entry filters",
                "candidate ranking",
                "stop and target logic",
                "all existing sizing multipliers including accepted signal-day green",
                "portfolio heat",
                "LLM/news replay",
                "pilot sleeves",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": "core state risk allocation using production-knowable signal-day close-location strength",
            "2_history_check": {
                "exp-20260512-110": "red candle haircuts failed in all three windows.",
                "exp-20260512-111": "momentum acceleration top-ups regressed old_thin.",
                "exp-20260513-001": "strong-volume breakout scalar was immaterial.",
                "exp-20260513-003": "own green candle 1.05x passed and is now current shared baseline; this tests close-near-high quality as a different intraday state.",
            },
            "3_single_causal_variable": "signal_day_close_location_risk_scalar at a fixed upper-quartile close-location state boundary",
            "4_acceptance_standard": "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, EV improves in all three windows, max drawdown worsens by <= 0.5 percentage points, survival >= 5%.",
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\exp_20260513_009_signal_day_close_location_risk.py"
            ),
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical fixed-snapshot three-window replay",
            "windows": base.WINDOWS,
            "config": {"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_aggregate": aggregate_before,
        },
        "gate2": {
            "open_positions": gate2,
            "runtime_fields": [
                "feature_layer signal_day_close_location",
                "risk_engine signal_day_close_location_upper_quartile",
                "portfolio_engine post-sizing scalar",
            ],
            "passed": gate2["passed"],
        },
        "gate3": {
            "new_filter_added": False,
            "signals_generated_delta": best_variant["delta_metrics"]["aggregate_delta"][
                "signals_generated_sum"
            ],
            "signals_survived_delta": best_variant["delta_metrics"]["aggregate_delta"][
                "signals_survived_sum"
            ],
            "minimum_after_survival_rate": best_variant["delta_metrics"]["aggregate_after"][
                "survival_rate_min"
            ],
            "passed": best_variant["delta_metrics"]["aggregate_after"]["survival_rate_min"]
            >= 0.05,
        },
        "gate4": best_variant["gate"],
        "before_metrics": before_metrics,
        "after_metrics": best_variant["after_metrics"],
        "delta_metrics": best_variant["delta_metrics"],
        "adjustments": best_variant["adjustments"],
        "changed_trades": best_variant["changed_trades"],
        "sizing_attribution": best_variant["sizing_attribution"],
        "best_variant": best_name,
        "variants": variants,
        "expected_value_score_delta": best_variant["gate"]["aggregate_delta"][
            "expected_value_score_sum"
        ],
        "total_pnl_delta": best_variant["gate"]["aggregate_delta"]["total_pnl_sum"],
        "llm_metrics": {"used_llm": False},
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
        },
        "interpretation": interpretation,
        "rejection_reason": None if best_variant["gate"]["passed"] else interpretation,
        "next_evidence_needed": (
            "Implement as shared feature/risk/sizing policy with parity tests, then rerun the canonical three-window protocol."
            if best_variant["gate"]["passed"]
            else "Use forward close-location attribution or a stronger production-visible intraday state before retrying."
        ),
        "related_files": [
            "quant/experiments/exp_20260513_009_signal_day_close_location_risk.py",
            "data/experiments/exp-20260513-009/signal_day_close_location_risk.json",
            "docs/experiments/logs/exp-20260513-009.json",
            "docs/experiments/tickets/exp-20260513-009.json",
            "docs/experiments/artifacts/exp-20260513-009_signal_day_close_location_risk.md",
            "docs/experiment_log.jsonl",
        ],
    }
    return payload


def persist(payload: dict[str, Any]) -> None:
    artifact_path = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
    log_path = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    ticket_path = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
    md_path = REPO_ROOT / "docs" / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "changed_variable": payload["changed_variable"],
        "best_variant": payload["best_variant"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["total_pnl_delta"],
        "gate4_passed": payload["gate4"]["passed"],
        "summary": payload["interpretation"],
        "artifact": str(artifact_path.relative_to(REPO_ROOT)),
    }
    _write_json(artifact_path, payload)
    _write_json(log_path, payload)
    _write_json(ticket_path, ticket)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_markdown(payload) + "\n", encoding="utf-8")
    _upsert_jsonl(REPO_ROOT / "docs" / "experiment_log.jsonl", payload)


if __name__ == "__main__":
    result = run()
    persist(result)
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "decision": result["decision"],
                "best_variant": result["best_variant"],
                "expected_value_score_delta": result["expected_value_score_delta"],
                "total_pnl_delta": result["total_pnl_delta"],
                "gate4_passed": result["gate4"]["passed"],
                "improved_windows": result["gate4"]["improved_windows"],
                "regressed_windows": result["gate4"]["regressed_windows"],
                "adjusted_signal_count": result["gate4"]["adjusted_signal_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )
