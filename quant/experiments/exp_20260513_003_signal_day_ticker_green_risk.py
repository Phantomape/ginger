"""exp-20260513-003: signal-day own-green-candle risk allocation.

Alpha search. Tests one production-knowable core state variable: whether the
candidate's own signal-day close is above its signal-day open. The experiment
changes only a cap-aware post-sizing risk scalar for that state. It does not
change entry filters, ranking, exits, targets, LLM/news behavior, portfolio
heat, or universe membership.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


EXPERIMENT_ID = "exp-20260513-003"
EXPERIMENT_SLUG = "signal_day_ticker_green_risk"
MULTIPLIER_KEY = "signal_day_ticker_green_risk_multiplier_applied"
SCALARS = (1.05, 1.10, 1.15, 1.25, 1.50)

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = Path(__file__).resolve().parent
for path in (QUANT_DIR, EXPERIMENT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import backtester as backtester_module  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
import exp_20260512_106_signal_day_sector_tape_risk as base  # noqa: E402
import feature_layer  # noqa: E402
import portfolio_engine  # noqa: E402
import risk_engine  # noqa: E402


ADJUSTMENTS: list[dict[str, Any]] = []


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(base._safe(payload), ensure_ascii=False, sort_keys=True)
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


def _signal_day_open_close_return(ohlcv_data: Any) -> float | None:
    if ohlcv_data is None or len(ohlcv_data) < 1:
        return None
    row = ohlcv_data.iloc[-1]
    try:
        open_ = float(row["Open"].item() if hasattr(row["Open"], "item") else row["Open"])
        close = float(row["Close"].item() if hasattr(row["Close"], "item") else row["Close"])
    except Exception:
        return None
    if open_ <= 0:
        return None
    return round((close - open_) / open_, 6)


def _make_compute_features_wrapper(original: Callable[..., dict[str, Any] | None]) -> Callable[..., dict[str, Any] | None]:
    def wrapped(ticker: str, ohlcv_data: Any, earnings_data: dict[str, Any] | None) -> dict[str, Any] | None:
        features = original(ticker, ohlcv_data, earnings_data)
        if features is None:
            return None
        features = dict(features)
        features["signal_day_ticker_open_close_return_pct"] = _signal_day_open_close_return(ohlcv_data)
        return features

    return wrapped


def _make_enrich_wrapper(original: Callable[..., list[dict[str, Any]]]) -> Callable[..., list[dict[str, Any]]]:
    def wrapped(
        signals: list[dict[str, Any]],
        features_dict: dict[str, dict[str, Any]],
        atr_target_mult: float | None = None,
    ) -> list[dict[str, Any]]:
        enriched = original(signals, features_dict, atr_target_mult=atr_target_mult)
        for sig in enriched:
            ticker = str(sig.get("ticker") or "")
            own_ret = (features_dict.get(ticker) or {}).get("signal_day_ticker_open_close_return_pct")
            sig["signal_day_ticker_open_close_return_pct"] = own_ret
            sig["signal_day_ticker_green_candle"] = (
                isinstance(own_ret, (int, float)) and own_ret > 0
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
    new_shares = min(
        max(shares, int(math.floor(shares * scalar))),
        cap_shares,
    )
    if new_shares == shares:
        return sizing

    net_risk_per_share = float(sizing.get("net_risk_per_share") or 0.0)
    out = dict(sizing)
    out["signal_day_ticker_green_baseline_shares"] = shares
    out["signal_day_ticker_green_new_shares"] = new_shares
    out["shares_to_buy"] = new_shares
    out["position_value_usd"] = round(entry * new_shares, 2)
    out["position_pct_of_portfolio"] = round((entry * new_shares) / portfolio_value, 4) if portfolio_value else 0.0
    out["risk_amount_usd"] = round(net_risk_per_share * new_shares, 2)
    out["risk_pct"] = (net_risk_per_share * new_shares) / portfolio_value if portfolio_value else 0.0
    out[MULTIPLIER_KEY] = scalar
    return out


def _make_size_wrapper(original: Callable[..., list[dict[str, Any]]], scalar: float) -> Callable[..., list[dict[str, Any]]]:
    def wrapped(
        signals: list[dict[str, Any]],
        portfolio_value: float,
        risk_pct: float | None = None,
    ) -> list[dict[str, Any]]:
        sized = original(signals, portfolio_value, risk_pct=risk_pct)
        out = []
        for sig in sized:
            sizing = sig.get("sizing") or {}
            if sig.get("signal_day_ticker_green_candle") and sizing.get("shares_to_buy"):
                adjusted = _rescale_sizing(sig, sizing, scalar, portfolio_value)
                if adjusted is not sizing:
                    ADJUSTMENTS.append(
                        {
                            "ticker": sig.get("ticker"),
                            "strategy": sig.get("strategy"),
                            "sector": sig.get("sector"),
                            "own_open_close_return_pct": sig.get("signal_day_ticker_open_close_return_pct"),
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
        result = BacktestEngine(
            universe,
            start=spec["start"],
            end=spec["end"],
            config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
            ohlcv_snapshot_path=str(REPO_ROOT / spec["snapshot"]),
        ).run()
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
    return f"green_scalar_{str(scalar).replace('.', '_')}"


def _score_variant(variant: dict[str, Any]) -> tuple[int, float, float]:
    gate = variant["gate"]
    return (
        1 if gate["passed"] else 0,
        float(gate["aggregate_delta"]["expected_value_score_sum"]),
        float(gate["aggregate_delta"]["total_pnl_sum"]),
    )


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Signal-Day Ticker Green Risk",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Single variable: cap-aware post-sizing risk scalar for signals whose own signal-day close is above its open.",
        "",
        "| Variant | Scalar | dEV sum | dPnL sum | Improved | Regressed | Adjusted signals | Max DD worse | Passed |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for name, variant in payload["variants"].items():
        gate = variant["gate"]
        lines.append(
            "| {name} | {scalar:.2f} | {ev:+.4f} | ${pnl:+,.2f} | {imp} | {reg} | {adj} | {dd:+.4f} | {passed} |".format(
                name=name,
                scalar=variant["scalar"],
                ev=gate["aggregate_delta"]["expected_value_score_sum"],
                pnl=gate["aggregate_delta"]["total_pnl_sum"],
                imp=len(gate["improved_windows"]),
                reg=len(gate["regressed_windows"]),
                adj=gate["adjusted_signal_count"],
                dd=gate["max_drawdown_worse"],
                passed=gate["passed"],
            )
        )
    lines.extend(
        [
            "",
            "Production impact: replay-only scout. Positive promotion would require shared feature/risk/sizing implementation and parity coverage before any live/default behavior change.",
        ]
    )
    return "\n".join(lines)


def run() -> dict[str, Any]:
    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    before_runs = {label: _run_window(label, scalar=None) for label in base.WINDOWS}
    before_metrics = {label: row["metrics"] for label, row in before_runs.items()}
    aggregate_before = base._aggregate(before_metrics)
    variants: dict[str, Any] = {}

    for scalar in SCALARS:
        name = _variant_name(scalar)
        after_runs = {label: _run_window(label, scalar=scalar) for label in base.WINDOWS}
        after_metrics = {label: row["metrics"] for label, row in after_runs.items()}
        by_window_delta = {
            label: base._delta(after_metrics[label], before_metrics[label])
            for label in base.WINDOWS
        }
        aggregate_after = base._aggregate(after_metrics)
        aggregate_delta = base._aggregate_delta(aggregate_after, aggregate_before)
        improved = [
            label
            for label in base.WINDOWS
            if after_metrics[label]["expected_value_score"] > before_metrics[label]["expected_value_score"]
        ]
        regressed = [
            label
            for label in base.WINDOWS
            if after_metrics[label]["expected_value_score"] < before_metrics[label]["expected_value_score"]
        ]
        adjustments = {
            label: after_runs[label]["adjustments"]
            for label in base.WINDOWS
        }
        adjusted_count = sum(len(rows) for rows in adjustments.values())
        max_drawdown_worse = (
            aggregate_after["max_drawdown_pct_max"]
            - aggregate_before["max_drawdown_pct_max"]
        )
        passed = (
            aggregate_delta["expected_value_score_sum"] > 0
            and aggregate_delta["total_pnl_sum"] > 0
            and len(improved) >= 2
            and not regressed
            and aggregate_after["survival_rate_min"] >= 0.05
            and max_drawdown_worse <= 0.005
            and adjusted_count > 0
        )
        variants[name] = {
            "scalar": scalar,
            "after_metrics": after_metrics,
            "delta_metrics": {
                "by_window": by_window_delta,
                "aggregate_after": aggregate_after,
                "aggregate_delta": aggregate_delta,
            },
            "adjustments": adjustments,
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
                "aggregate_delta": aggregate_delta,
                "max_drawdown_worse": round(max_drawdown_worse, 6),
            },
        }

    best_name, best_variant = max(variants.items(), key=lambda item: _score_variant(item[1]))
    decision = (
        "accepted_for_shared_policy_implementation"
        if best_variant["gate"]["passed"]
        else "rejected_signal_day_ticker_green_risk"
    )
    interpretation = (
        "Own green-candle signal-day risk allocation cleared the three-window gate and should be implemented through shared production/backtest policy before use."
        if best_variant["gate"]["passed"]
        else "Own green-candle signal-day risk allocation did not clear the canonical three-window gate; do not promote this state scalar without a stronger production-visible discriminator."
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": _utc_now(),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "Signals whose own signal-day candle closes green may have stronger next-session follow-through; allocate slightly more risk rather than changing entry filters."
        ),
        "change_type": "risk_allocation_shadow",
        "changed_variable": "signal_day_ticker_green_candle_risk_scalar",
        "single_causal_variable": (
            "cap-aware post-sizing scalar for signals whose own signal-day open-to-close return is > 0"
        ),
        "parameters": {
            "signal_day_ticker_green_definition": "ticker open-to-close return > 0 on signal day",
            "tested_scalars": list(SCALARS),
            "locked_variables": [
                "core universe",
                "entry filters",
                "candidate ranking",
                "stop and target logic",
                "existing sizing multipliers",
                "portfolio heat",
                "LLM/news replay",
                "pilot/event sleeves",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": "core state risk allocation using production-knowable signal-day own-candle strength",
            "2_history_check": {
                "exp-20260512-106": "sector-proxy adverse tape haircut was rejected.",
                "exp-20260512-107": "positive sector-proxy tape top-up was underpowered and only improved old_thin.",
                "exp-20260512-110": "own red-candle haircut was rejected; this tests the complementary positive own-candle state, not a nearby red-candle retune.",
                "exp-20260513-001": "core strong-volume breakout scalar was immaterial; this run is strategy-agnostic own price action.",
            },
            "3_single_causal_variable": "signal_day_ticker_green_candle_risk_scalar",
            "4_acceptance_standard": "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, at least two EV-improved windows, no EV-regressed windows, survival >= 5%, max drawdown drift <= 0.5 pp.",
            "5_reproducibility": "Run .venv\\Scripts\\python.exe quant\\experiments\\exp_20260513_003_signal_day_ticker_green_risk.py",
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
                "feature_layer signal_day_ticker_open_close_return_pct",
                "risk_engine signal_day_ticker_green_candle",
                "portfolio_engine sizing shares_to_buy",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "passed": gate2["passed"],
        },
        "gate3": {
            "new_filter_added": False,
            "minimum_after_survival_rate": min(
                variant["delta_metrics"]["aggregate_after"]["survival_rate_min"]
                for variant in variants.values()
            ),
            "passed": all(
                variant["delta_metrics"]["aggregate_after"]["survival_rate_min"] >= 0.05
                for variant in variants.values()
            ),
        },
        "gate4": best_variant["gate"],
        "before_metrics": before_metrics,
        "before_aggregate": aggregate_before,
        "best_variant": best_name,
        "after_metrics": best_variant["after_metrics"],
        "delta_metrics": best_variant["delta_metrics"],
        "variants": variants,
        "expected_value_score_delta": best_variant["gate"]["aggregate_delta"]["expected_value_score_sum"],
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
        "next_evidence_needed": None
        if best_variant["gate"]["passed"]
        else "Forward/shadow hold-quality evidence or a narrower production-visible own-candle state before retrying.",
        "related_files": [
            "quant/experiments/exp_20260513_003_signal_day_ticker_green_risk.py",
            "data/experiments/exp-20260513-003/signal_day_ticker_green_risk.json",
            "experiments/logs/exp-20260513-003.json",
            "experiments/tickets/exp-20260513-003.json",
            "experiments/artifacts/exp-20260513-003_signal_day_ticker_green_risk.md",
            "docs/experiment_log.jsonl",
        ],
        "why_not_other_changes": (
            "LLM soft-ranking remains data-limited; SEC semantic fields are missing; Space frozen-sample profile scalars and noisy candidate additions have been over-mined or rejected. This tests a fresh core allocation state without changing entries or expanding the pool."
        ),
    }


def persist(payload: dict[str, Any]) -> None:
    artifact_path = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
    log_path = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    ticket_path = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
    md_path = (
        REPO_ROOT
        / "experiments"
        / "artifacts"
        / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
    )
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
    base._write_json(artifact_path, payload)
    base._write_json(log_path, payload)
    base._write_json(ticket_path, ticket)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_build_markdown(payload) + "\n", encoding="utf-8")
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
