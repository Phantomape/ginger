"""exp-20260512-106: signal-day adverse sector-tape risk allocation.

Tests one causal variable on the accepted core stack: a post-sizing risk
haircut for signals whose production-knowable signal-day sector proxy return
is <= -1%. This is a risk-allocation scout, not an entry filter.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


EXPERIMENT_ID = "exp-20260512-106"
EXPERIMENT_SLUG = "signal_day_sector_tape_risk"
ADVERSE_TAPE_THRESHOLD = -0.01
ADVERSE_TAPE_RISK_MULTIPLIER = 0.5
MULTIPLIER_KEY = "signal_day_adverse_sector_tape_risk_multiplier_applied"

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import backtester as backtester_module  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
import feature_layer  # noqa: E402
import portfolio_engine  # noqa: E402
import risk_engine  # noqa: E402


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

SECTOR_PROXY = {
    "Technology": "QQQ",
    "Consumer Discretionary": "QQQ",
    "Communication Services": "QQQ",
    "Financials": "SPY",
    "Healthcare": "SPY",
    "Energy": "SPY",
    "Industrials": "SPY",
    "Commodities": "GLD",
}

RESULT_KEYS = [
    "expected_value_score",
    "total_pnl",
    "total_return_pct",
    "sharpe_daily",
    "max_drawdown_pct",
    "win_rate",
    "trade_count",
    "signals_generated",
    "signals_survived",
    "survival_rate",
    "worst_trade_pct",
    "max_consecutive_losses",
    "tail_loss_share",
]

ADJUSTMENTS: list[dict[str, Any]] = []


def _round(value: Any) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return round(value, 6)
    return value


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


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    summary = {key: _round(result.get(key)) for key in RESULT_KEYS}
    benchmarks = result.get("benchmarks") or {}
    summary["total_return_pct"] = _round(
        benchmarks.get("strategy_total_return_pct", summary.get("total_return_pct"))
    )
    summary["trade_count"] = _round(result.get("total_trades", summary.get("trade_count")))
    summary["spy_buy_hold_return_pct"] = _round(benchmarks.get("spy_buy_hold_return_pct"))
    summary["qqq_buy_hold_return_pct"] = _round(benchmarks.get("qqq_buy_hold_return_pct"))
    convergence = result.get("convergence") or {}
    if convergence:
        summary["converged"] = bool(convergence.get("converged", False))
    return summary


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in RESULT_KEYS:
        if isinstance(after.get(key), (int, float)) and isinstance(before.get(key), (int, float)):
            out[key] = _round(after[key] - before[key])
    return out


def _aggregate(metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in metrics.values()),
            6,
        ),
        "total_pnl_sum": round(sum(float(row.get("total_pnl") or 0.0) for row in metrics.values()), 2),
        "trade_count_sum": int(sum(int(row.get("trade_count") or 0) for row in metrics.values())),
        "signals_generated_sum": int(
            sum(int(row.get("signals_generated") or 0) for row in metrics.values())
        ),
        "signals_survived_sum": int(
            sum(int(row.get("signals_survived") or 0) for row in metrics.values())
        ),
        "max_drawdown_pct_max": round(
            max(float(row.get("max_drawdown_pct") or 0.0) for row in metrics.values()),
            6,
        ),
        "survival_rate_min": round(
            min(float(row.get("survival_rate") or 0.0) for row in metrics.values()),
            6,
        ),
    }


def _aggregate_delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in after.items():
        if isinstance(value, (int, float)) and isinstance(before.get(key), (int, float)):
            out[key] = _round(value - before[key])
    return out


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


def _audit_open_positions() -> dict[str, Any]:
    path = REPO_ROOT / "operator_inputs" / "open_positions.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for section in ("positions", "observations"):
        rows.extend([row for row in payload.get(section, []) if isinstance(row, dict)])
    missing = []
    for row in rows:
        for field in ("entry_date", "target_price"):
            if row.get(field) in (None, ""):
                missing.append({"ticker": row.get("ticker"), "field": field})
    return {
        "path": str(path.relative_to(REPO_ROOT)),
        "checked_rows": len(rows),
        "required_fields": ["entry_date", "target_price"],
        "missing_required_fields": missing,
        "passed": not missing,
    }


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
        features["signal_day_open_close_return_pct"] = _signal_day_open_close_return(ohlcv_data)
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
            sector = sig.get("sector")
            proxy = SECTOR_PROXY.get(str(sector or ""))
            proxy_ret = None
            if proxy:
                proxy_ret = (features_dict.get(proxy) or {}).get("signal_day_open_close_return_pct")
            sig["signal_day_sector_proxy"] = proxy
            sig["signal_day_sector_proxy_open_close_return_pct"] = proxy_ret
            sig["signal_day_adverse_sector_tape"] = (
                isinstance(proxy_ret, (int, float))
                and proxy_ret <= ADVERSE_TAPE_THRESHOLD
            )
        return enriched

    return wrapped


def _scale_sizing(sizing: dict[str, Any], scalar: float, portfolio_value: float) -> dict[str, Any]:
    shares = int(sizing.get("shares_to_buy") or 0)
    if shares <= 0:
        return sizing
    new_shares = max(1, int(math.floor(shares * scalar)))
    if new_shares >= shares:
        return sizing
    entry = float(sizing.get("entry_price") or 0.0)
    net_risk_per_share = float(sizing.get("net_risk_per_share") or 0.0)
    out = dict(sizing)
    out["signal_day_adverse_sector_tape_baseline_shares"] = shares
    out["signal_day_adverse_sector_tape_new_shares"] = new_shares
    out["shares_to_buy"] = new_shares
    out["position_value_usd"] = round(entry * new_shares, 2)
    out["position_pct_of_portfolio"] = round((entry * new_shares) / portfolio_value, 4) if portfolio_value else 0.0
    out["risk_amount_usd"] = round(net_risk_per_share * new_shares, 2)
    out["risk_pct"] = (net_risk_per_share * new_shares) / portfolio_value if portfolio_value else 0.0
    out[MULTIPLIER_KEY] = scalar
    return out


def _make_size_wrapper(original: Callable[..., list[dict[str, Any]]]) -> Callable[..., list[dict[str, Any]]]:
    def wrapped(
        signals: list[dict[str, Any]],
        portfolio_value: float,
        risk_pct: float | None = None,
    ) -> list[dict[str, Any]]:
        sized = original(signals, portfolio_value, risk_pct=risk_pct)
        out = []
        for sig in sized:
            sizing = sig.get("sizing") or {}
            if sig.get("signal_day_adverse_sector_tape") and sizing.get("shares_to_buy"):
                adjusted_sizing = _scale_sizing(sizing, ADVERSE_TAPE_RISK_MULTIPLIER, portfolio_value)
                if adjusted_sizing is not sizing:
                    ADJUSTMENTS.append(
                        {
                            "ticker": sig.get("ticker"),
                            "strategy": sig.get("strategy"),
                            "sector": sig.get("sector"),
                            "sector_proxy": sig.get("signal_day_sector_proxy"),
                            "sector_proxy_open_close_return_pct": sig.get(
                                "signal_day_sector_proxy_open_close_return_pct"
                            ),
                            "baseline_shares": sizing.get("shares_to_buy"),
                            "new_shares": adjusted_sizing.get("shares_to_buy"),
                            "trade_quality_score": sig.get("trade_quality_score"),
                            "regime_exit_bucket": sig.get("regime_exit_bucket"),
                            "regime_exit_score": sig.get("regime_exit_score"),
                        }
                    )
                    sig = {**sig, "sizing": adjusted_sizing}
            out.append(sig)
        return out

    return wrapped


def _run_window(label: str, *, variant: bool) -> dict[str, Any]:
    spec = WINDOWS[label]
    universe = get_universe()
    original_compute_features = feature_layer.compute_features
    original_enrich = risk_engine.enrich_signals
    original_size = portfolio_engine.size_signals
    original_multiplier_keys = backtester_module.SIZING_MULTIPLIER_KEYS

    global ADJUSTMENTS
    ADJUSTMENTS = []

    if variant:
        feature_layer.compute_features = _make_compute_features_wrapper(original_compute_features)
        risk_engine.enrich_signals = _make_enrich_wrapper(original_enrich)
        portfolio_engine.size_signals = _make_size_wrapper(original_size)
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
        raise RuntimeError(f"{label} {'variant' if variant else 'baseline'} failed: {result['error']}")
    return {
        "metrics": _metrics(result),
        "trades": result.get("trades") or [],
        "adjustments": list(ADJUSTMENTS),
        "sizing_rule_signal_attribution": result.get("sizing_rule_signal_attribution") or {},
        "sizing_rule_trade_attribution": result.get("sizing_rule_trade_attribution") or {},
    }


def _trade_key(trade: dict[str, Any]) -> str:
    return "|".join(
        [
            str(trade.get("ticker") or ""),
            str(trade.get("entry_date") or ""),
            str(trade.get("strategy") or ""),
            str(round(float(trade.get("entry_price") or 0.0), 4)),
        ]
    )


def _changed_trades(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> dict[str, Any]:
    before_by_key = {_trade_key(row): row for row in before}
    after_by_key = {_trade_key(row): row for row in after}
    common_changed = []
    for key in sorted(set(before_by_key) & set(after_by_key)):
        b = before_by_key[key]
        a = after_by_key[key]
        if round(float(b.get("pnl") or 0.0), 2) != round(float(a.get("pnl") or 0.0), 2):
            common_changed.append(
                {
                    "key": key,
                    "before": {
                        "ticker": b.get("ticker"),
                        "entry_date": b.get("entry_date"),
                        "exit_date": b.get("exit_date"),
                        "sector": b.get("sector"),
                        "shares": b.get("shares"),
                        "pnl": b.get("pnl"),
                        "sizing_multipliers": b.get("sizing_multipliers"),
                    },
                    "after": {
                        "ticker": a.get("ticker"),
                        "entry_date": a.get("entry_date"),
                        "exit_date": a.get("exit_date"),
                        "sector": a.get("sector"),
                        "shares": a.get("shares"),
                        "pnl": a.get("pnl"),
                        "sizing_multipliers": a.get("sizing_multipliers"),
                    },
                }
            )
    added = sorted(set(after_by_key) - set(before_by_key))
    removed = sorted(set(before_by_key) - set(after_by_key))
    return {
        "added_count": len(added),
        "removed_count": len(removed),
        "common_pnl_changed_count": len(common_changed),
        "added_keys": added,
        "removed_keys": removed,
        "common_pnl_changed": common_changed,
    }


def _markdown(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted signals |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {surv:.4f} | {adj} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                surv=after["survival_rate"],
                adj=len(payload["adjustments"][label]),
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Signal-Day Sector Tape Risk",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: 0.5x post-sizing risk multiplier when the signal-day sector proxy open-to-close return is <= -1%. No entry filter, ranking, exit, target, universe, LLM, or news behavior changed.",
            "",
            *rows,
            "",
            "Production impact: replay-only scout. Positive promotion would require shared `feature_layer`, `risk_engine`, and `portfolio_engine` code plus attribution key parity before live/default behavior changes.",
        ]
    )


def run() -> dict[str, Any]:
    gate2 = _audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    before_metrics: dict[str, dict[str, Any]] = {}
    after_metrics: dict[str, dict[str, Any]] = {}
    adjustments: dict[str, list[dict[str, Any]]] = {}
    changed_trades: dict[str, dict[str, Any]] = {}
    sizing_attribution: dict[str, Any] = {}

    for label in WINDOWS:
        baseline = _run_window(label, variant=False)
        variant = _run_window(label, variant=True)
        before_metrics[label] = baseline["metrics"]
        after_metrics[label] = variant["metrics"]
        adjustments[label] = variant["adjustments"]
        changed_trades[label] = _changed_trades(baseline["trades"], variant["trades"])
        sizing_attribution[label] = {
            "signal": variant["sizing_rule_signal_attribution"].get(MULTIPLIER_KEY),
            "trade": variant["sizing_rule_trade_attribution"].get(MULTIPLIER_KEY),
        }

    by_window_delta = {
        label: _delta(after_metrics[label], before_metrics[label])
        for label in WINDOWS
    }
    aggregate_before = _aggregate(before_metrics)
    aggregate_after = _aggregate(after_metrics)
    aggregate_delta = _aggregate_delta(aggregate_after, aggregate_before)
    improved = [
        label
        for label in WINDOWS
        if after_metrics[label]["expected_value_score"] > before_metrics[label]["expected_value_score"]
    ]
    regressed = [
        label
        for label in WINDOWS
        if after_metrics[label]["expected_value_score"] < before_metrics[label]["expected_value_score"]
    ]
    adjusted_count = sum(len(rows) for rows in adjustments.values())
    passed = (
        aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] > 0
        and len(improved) >= 2
        and not regressed
        and aggregate_after["survival_rate_min"] >= 0.05
        and adjusted_count > 0
    )
    decision = (
        "accepted_for_shared_policy_implementation"
        if passed
        else "rejected_signal_day_sector_tape_risk"
    )
    interpretation = (
        "Signal-day adverse sector tape improved the accepted core stack and should be implemented through shared feature/risk/sizing policy before any production-visible use."
        if passed
        else "The 0.5x signal-day adverse sector-tape risk haircut did not clear the canonical three-window gate; do not promote this fixed threshold/scalar without a new discriminator."
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "Signals fired on days when their sector proxy is already down <=1% open-to-close may have worse next-session follow-through; reduce risk rather than filter them."
        ),
        "change_type": "risk_allocation_shadow",
        "changed_variable": "signal_day_adverse_sector_tape_risk_multiplier",
        "single_causal_variable": (
            "0.5x post-sizing risk multiplier for signals whose signal-day sector proxy open-to-close return is <= -1%"
        ),
        "parameters": {
            "adverse_tape_threshold": ADVERSE_TAPE_THRESHOLD,
            "risk_multiplier": ADVERSE_TAPE_RISK_MULTIPLIER,
            "sector_proxy": SECTOR_PROXY,
            "locked_variables": [
                "core universe",
                "entry filters",
                "candidate ranking",
                "stop and target logic",
                "all existing sizing multipliers",
                "portfolio heat",
                "LLM/news replay",
                "pilot sleeves",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": "core state risk allocation using production-knowable signal-day sector tape",
            "2_history_check": {
                "exp-20260512-102": "observed late-window adverse tape loss taxonomy; this tests a production-knowable signal-day proxy state rather than entry-day hindsight.",
                "broad_filters": "historically weak; this run does not filter entries or reduce survival.",
            },
            "3_single_causal_variable": "signal_day_adverse_sector_tape_risk_multiplier at a fixed observed -1% state boundary",
            "4_acceptance_standard": "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, at least two EV-improved windows, no EV-regressed windows, survival >= 5%.",
            "5_reproducibility": "Run .venv\\Scripts\\python.exe quant\\experiments\\exp_20260512_106_signal_day_sector_tape_risk.py",
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical fixed-snapshot three-window replay",
            "windows": WINDOWS,
            "config": {"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_aggregate": aggregate_before,
        },
        "gate2": {
            "open_positions": gate2,
            "runtime_fields": [
                "feature_layer signal_day_open_close_return_pct",
                "risk_engine sector",
                "risk_engine signal_day_sector_proxy_open_close_return_pct",
            ],
            "passed": gate2["passed"],
        },
        "gate3": {
            "new_filter_added": False,
            "signals_generated_delta": aggregate_delta["signals_generated_sum"],
            "signals_survived_delta": aggregate_delta["signals_survived_sum"],
            "minimum_after_survival_rate": aggregate_after["survival_rate_min"],
            "passed": aggregate_after["survival_rate_min"] >= 0.05,
        },
        "gate4": {
            "passed": passed,
            "improved_windows": improved,
            "regressed_windows": regressed,
            "adjusted_signal_count": adjusted_count,
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": by_window_delta,
            "aggregate_before": aggregate_before,
            "aggregate_after": aggregate_after,
            "aggregate_delta": aggregate_delta,
        },
        "adjustments": adjustments,
        "changed_trades": changed_trades,
        "sizing_attribution": sizing_attribution,
        "expected_value_score_delta": aggregate_delta["expected_value_score_sum"],
        "total_pnl_delta": aggregate_delta["total_pnl_sum"],
        "llm_metrics": {"used_llm": False},
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
        },
        "interpretation": interpretation,
        "rejection_reason": None if passed else interpretation,
        "next_evidence_needed": None
        if passed
        else "Use forward/shadow sector-tape hold-quality attribution or a different production-visible state variable before retrying.",
        "related_files": [
            "quant/experiments/exp_20260512_106_signal_day_sector_tape_risk.py",
            "data/experiments/exp-20260512-106/signal_day_sector_tape_risk.json",
            "experiments/logs/exp-20260512-106.json",
            "experiments/tickets/exp-20260512-106.json",
            "experiments/artifacts/exp-20260512-106_signal_day_sector_tape_risk.md",
            "docs/experiment_log.jsonl",
        ],
    }
    return payload


def persist(payload: dict[str, Any]) -> None:
    artifact_path = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
    log_path = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    ticket_path = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
    md_path = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "changed_variable": payload["changed_variable"],
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
