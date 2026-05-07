"""exp-20260505-020 consumer platform governance gate replay.

Alpha search. exp-20260505-011 showed the HOOD/RBLX/SOFI sub-basket had
positive aggregate PnL but unstable window behavior. This tests whether a
shared signal-field governance gate can keep the sub-basket only when the
existing setup context is strong enough, instead of promoting noisy universe
growth directly.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import backtester as bt  # noqa: E402
import portfolio_engine as pe  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260505-020"
SOURCE_EXPERIMENT_ID = "exp-20260505-011"
SNAPSHOT_EXPERIMENT_ID = "exp-20260505-009"
SUB_BASKET = ("HOOD", "RBLX", "SOFI")
MULTIPLIER_KEY = "consumer_platform_governance_gate_multiplier_applied"

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/experiments/exp-20260505-009/ohlcv/exp-20260505-009_late_strong_fresh_ohlcv.json",
        "state_note": "slow-melt bull / accepted-stack dominant tape",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/experiments/exp-20260505-009/ohlcv/exp-20260505-009_mid_weak_fresh_ohlcv.json",
        "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/experiments/exp-20260505-009/ohlcv/exp-20260505-009_old_thin_fresh_ohlcv.json",
        "state_note": "mixed-to-weak older tape with lower win rate",
    }),
])

VARIANTS = OrderedDict([
    ("risk_on_only", {
        "required_bucket": "risk_on",
        "require_spy_relative_leader": False,
        "min_regime_exit_score": None,
        "min_trade_quality_score": None,
    }),
    ("spy_leader_only", {
        "required_bucket": None,
        "require_spy_relative_leader": True,
        "min_regime_exit_score": None,
        "min_trade_quality_score": None,
    }),
    ("risk_on_spy_leader_only", {
        "required_bucket": "risk_on",
        "require_spy_relative_leader": True,
        "min_regime_exit_score": None,
        "min_trade_quality_score": None,
    }),
    ("risk_on_score_ge_0_10", {
        "required_bucket": "risk_on",
        "require_spy_relative_leader": False,
        "min_regime_exit_score": 0.10,
        "min_trade_quality_score": None,
    }),
    ("risk_on_tqs_ge_0_90", {
        "required_bucket": "risk_on",
        "require_spy_relative_leader": False,
        "min_regime_exit_score": None,
        "min_trade_quality_score": 0.90,
    }),
])

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "consumer_platform_governance_gate.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "docs" / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_consumer_platform_governance_gate.md"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

_state = {
    "candidate_signals": 0,
    "passed_signals": 0,
    "zeroed_signals": 0,
}


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


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
        "candidate_signals": _state["candidate_signals"],
        "passed_signals": _state["passed_signals"],
        "zeroed_signals": _state["zeroed_signals"],
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
        "candidate_signals",
        "passed_signals",
        "zeroed_signals",
    )
    out: dict[str, Any] = {}
    for key in keys:
        before_value = before.get(key)
        after_value = after.get(key)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            if key in {"trade_count", "signals_generated", "signals_survived", "candidate_signals", "passed_signals", "zeroed_signals"}:
                out[key] = int(after_value - before_value)
            else:
                out[key] = _round(after_value - before_value, 6)
    return out


def _variant_allows(sig: dict[str, Any], variant: dict[str, Any]) -> bool:
    required_bucket = variant.get("required_bucket")
    if required_bucket and sig.get("regime_exit_bucket") != required_bucket:
        return False
    if variant.get("require_spy_relative_leader") and sig.get("spy_relative_leader") is not True:
        return False
    min_score = variant.get("min_regime_exit_score")
    score = sig.get("regime_exit_score")
    if min_score is not None and (score is None or score < min_score):
        return False
    min_tqs = variant.get("min_trade_quality_score")
    tqs = sig.get("trade_quality_score")
    if min_tqs is not None and (tqs is None or tqs < min_tqs):
        return False
    return True


def _zero_risk_sizing(sig: dict[str, Any], sizing: dict[str, Any]) -> dict[str, Any]:
    out = dict(sizing)
    out["risk_pct_before_consumer_platform_gate"] = sizing.get("risk_pct")
    out["risk_amount_before_consumer_platform_gate"] = sizing.get("risk_amount_usd")
    out["risk_pct"] = 0.0
    out["risk_amount_usd"] = 0.0
    out["shares_to_buy"] = 0
    out["position_value_usd"] = 0.0
    out["position_pct_of_portfolio"] = 0.0
    out["consumer_platform_gate_ticker"] = sig.get("ticker")
    out["consumer_platform_gate_bucket"] = sig.get("regime_exit_bucket")
    out["consumer_platform_gate_score"] = sig.get("regime_exit_score")
    out["consumer_platform_gate_spy_leader"] = sig.get("spy_relative_leader")
    out[MULTIPLIER_KEY] = 0.0
    return out


def _make_variant_sizer(original_size_signals, variant: dict[str, Any]):
    subbasket = set(SUB_BASKET)

    def size_signals(signals, portfolio_value, risk_pct=None):
        sized = original_size_signals(signals, portfolio_value, risk_pct=risk_pct)
        for sig in sized:
            ticker = str(sig.get("ticker") or "").upper()
            if ticker not in subbasket:
                continue
            sizing = sig.get("sizing") or {}
            if not sizing:
                continue
            _state["candidate_signals"] += 1
            if _variant_allows(sig, variant):
                _state["passed_signals"] += 1
                continue
            sig["sizing"] = _zero_risk_sizing(sig, sizing)
            _state["zeroed_signals"] += 1
        return sized

    return size_signals


def _run_engine(universe: list[str], window: dict[str, str], variant: dict[str, Any] | None = None) -> dict[str, Any]:
    snapshot = REPO_ROOT / window["snapshot"]
    if not snapshot.exists():
        raise FileNotFoundError(
            f"Required snapshot missing: {snapshot}. Run {SNAPSHOT_EXPERIMENT_ID} first."
        )
    original_size_signals = pe.size_signals
    original_multiplier_keys = bt.SIZING_MULTIPLIER_KEYS
    _state["candidate_signals"] = 0
    _state["passed_signals"] = 0
    _state["zeroed_signals"] = 0
    if variant is not None:
        pe.size_signals = _make_variant_sizer(original_size_signals, variant)
        if MULTIPLIER_KEY not in bt.SIZING_MULTIPLIER_KEYS:
            bt.SIZING_MULTIPLIER_KEYS = bt.SIZING_MULTIPLIER_KEYS + (MULTIPLIER_KEY,)
    try:
        result = BacktestEngine(
            universe=universe,
            start=window["start"],
            end=window["end"],
            config={"REGIME_AWARE_EXIT": True},
            replay_llm=False,
            replay_news=False,
            data_dir=str(REPO_ROOT / "data"),
            ohlcv_snapshot_path=str(snapshot),
        ).run()
    finally:
        pe.size_signals = original_size_signals
        bt.SIZING_MULTIPLIER_KEYS = original_multiplier_keys
    if "error" in result:
        raise RuntimeError(result["error"])
    return result


def _trade_stats(trades: list[dict[str, Any]], tickers: set[str]) -> dict[str, Any]:
    rows = [
        trade for trade in trades
        if str(trade.get("ticker") or "").upper() in tickers
    ]
    return {
        "trade_count": len(rows),
        "wins": sum(1 for trade in rows if float(trade.get("pnl") or 0.0) > 0),
        "losses": sum(1 for trade in rows if float(trade.get("pnl") or 0.0) <= 0),
        "total_pnl": _round(sum(float(trade.get("pnl") or 0.0) for trade in rows), 2),
        "trades": [
            {
                "ticker": trade.get("ticker"),
                "strategy": trade.get("strategy"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "pnl": _round(trade.get("pnl"), 2),
                "pnl_pct_net": _round(trade.get("pnl_pct_net"), 6),
                "exit_reason": trade.get("exit_reason"),
                "regime_exit_bucket": trade.get("regime_exit_bucket"),
                "regime_exit_score": trade.get("regime_exit_score"),
                "spy_relative_leader": trade.get("spy_relative_leader"),
                "sizing_multipliers": trade.get("sizing_multipliers") or {},
            }
            for trade in rows
        ],
    }


def _aggregate(rows: OrderedDict[str, dict[str, Any]]) -> dict[str, Any]:
    ev_before = sum(float(row["before"]["expected_value_score"] or 0.0) for row in rows.values())
    ev_delta = sum(float(row["delta"]["expected_value_score"] or 0.0) for row in rows.values())
    pnl_before = sum(float(row["before"]["total_pnl"] or 0.0) for row in rows.values())
    pnl_delta = sum(float(row["delta"]["total_pnl"] or 0.0) for row in rows.values())
    return {
        "expected_value_score_before_sum": _round(ev_before, 6),
        "expected_value_score_delta_sum": _round(ev_delta, 6),
        "expected_value_score_delta_pct": _round(ev_delta / ev_before if ev_before else 0.0, 6),
        "total_pnl_before_sum": _round(pnl_before, 2),
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
        "max_sharpe_daily_delta": _round(
            max(row["delta"].get("sharpe_daily", 0.0) for row in rows.values()), 6
        ),
        "trade_count_delta_sum": sum(row["delta"].get("trade_count", 0) for row in rows.values()),
        "win_rate_delta_min": _round(
            min(row["delta"].get("win_rate", 0.0) for row in rows.values()), 6
        ),
        "subbasket_trade_count_sum": sum(row["subbasket_trade_stats"]["trade_count"] for row in rows.values()),
        "subbasket_pnl_sum": _round(
            sum(row["subbasket_trade_stats"]["total_pnl"] or 0.0 for row in rows.values()), 2
        ),
        "candidate_signals_sum": sum(row["after"]["candidate_signals"] for row in rows.values()),
        "passed_signals_sum": sum(row["after"]["passed_signals"] for row in rows.values()),
        "zeroed_signals_sum": sum(row["after"]["zeroed_signals"] for row in rows.values()),
    }


def _accepted(aggregate: dict[str, Any]) -> bool:
    majority_ev = aggregate["ev_windows_improved"] >= 2 and aggregate["ev_windows_regressed"] == 0
    material = (
        (aggregate["expected_value_score_delta_pct"] or 0.0) > 0.10
        or (aggregate["total_pnl_delta_pct"] or 0.0) > 0.05
        or aggregate["max_drawdown_delta_max"] < -0.01
        or aggregate["max_sharpe_daily_delta"] > 0.10
        or (
            aggregate["trade_count_delta_sum"] > 0
            and aggregate["win_rate_delta_min"] >= 0
        )
    )
    return bool(majority_ev and material)


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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_artifact(payload: dict[str, Any]) -> None:
    best = payload["variants"][payload["best_variant"]]
    aggregate = best["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} Consumer Platform Governance Gate",
        "",
        f"Decision: `{payload['decision']}`",
        f"Best variant: `{payload['best_variant']}`",
        "",
        "## Aggregate",
        "",
        f"- EV delta sum: `{aggregate['expected_value_score_delta_sum']:+.4f}` "
        f"({aggregate['expected_value_score_delta_pct']:+.2%})",
        f"- PnL delta sum: `${aggregate['total_pnl_delta_sum']:+,.2f}` "
        f"({aggregate['total_pnl_delta_pct']:+.2%})",
        f"- EV windows improved/regressed: `{aggregate['ev_windows_improved']}` / `{aggregate['ev_windows_regressed']}`",
        f"- Candidate/passed/zeroed signals: `{aggregate['candidate_signals_sum']}` / "
        f"`{aggregate['passed_signals_sum']}` / `{aggregate['zeroed_signals_sum']}`",
        "",
        "## Three-window best deltas",
        "",
        "| Window | EV delta | PnL delta | SharpeD delta | DD delta | WR delta | Trades delta | Basket trades | Basket PnL |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, row in best["by_window"].items():
        delta = row["delta"]
        stats = row["subbasket_trade_stats"]
        lines.append(
            f"| {label} | {delta['expected_value_score']:+.4f} | "
            f"{delta['total_pnl']:+.2f} | {delta['sharpe_daily']:+.2f} | "
            f"{delta['max_drawdown_pct']:+.4f} | {delta['win_rate']:+.4f} | "
            f"{delta['trade_count']:+d} | {stats['trade_count']} | "
            f"{stats['total_pnl']:+.2f} |"
        )
    lines.extend([
        "",
        "## Parity",
        "",
        "No production universe or order path changed in this replay. If accepted, promotion must use a shared universe-governance gate or default-off pilot path so run.py and backtester.py consume the same rule.",
        "",
    ])
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines), encoding="utf-8")


def build_payload() -> dict[str, Any]:
    base_universe = sorted(set(get_universe()))
    subbasket = sorted(set(SUB_BASKET))
    expanded_universe = sorted(set(base_universe) | set(subbasket))
    added_tickers = sorted(set(expanded_universe) - set(base_universe))
    if added_tickers != subbasket:
        raise RuntimeError(f"Expected all sub-basket tickers to be new: {added_tickers}")

    baseline: OrderedDict[str, dict[str, Any]] = OrderedDict()
    subbasket_set = set(subbasket)
    for label, window in WINDOWS.items():
        print(f"[{label}] baseline on {window['snapshot']}")
        before_result = _run_engine(base_universe, window)
        baseline[label] = {
            "result": before_result,
            "metrics": _metrics(before_result),
        }

    variants: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for variant_name, variant in VARIANTS.items():
        rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
        for label, window in WINDOWS.items():
            print(f"[{label}] expanded {','.join(subbasket)} variant={variant_name}")
            after_result = _run_engine(expanded_universe, window, variant)
            before = baseline[label]["metrics"]
            after = _metrics(after_result)
            delta = _delta(after, before)
            stats = _trade_stats(after_result.get("trades") or [], subbasket_set)
            rows[label] = {
                "window": {
                    "start": window["start"],
                    "end": window["end"],
                    "snapshot": window["snapshot"],
                    "state_note": window["state_note"],
                },
                "before": before,
                "after": after,
                "delta": delta,
                "subbasket_trade_stats": stats,
                "entry_reason_counts_before": (
                    baseline[label]["result"].get("entry_execution_attribution", {}).get("reason_counts", {})
                ),
                "entry_reason_counts_after": (
                    after_result.get("entry_execution_attribution", {}).get("reason_counts", {})
                ),
            }
            print(
                f"[{label}] {variant_name} EV={delta['expected_value_score']:+.4f} "
                f"PnL={delta['total_pnl']:+.2f} trades={delta['trade_count']:+d} "
                f"basket_pnl={stats['total_pnl']:+.2f} "
                f"passed={after['passed_signals']} zeroed={after['zeroed_signals']}"
            )
        aggregate = _aggregate(rows)
        variants[variant_name] = {
            "parameters": variant,
            "by_window": rows,
            "aggregate": aggregate,
            "gate4_passed": _accepted(aggregate),
        }

    best_variant = max(
        variants,
        key=lambda name: variants[name]["aggregate"]["expected_value_score_delta_sum"],
    )
    best = variants[best_variant]
    accepted = bool(best["gate4_passed"])
    decision = "accepted_candidate" if accepted else "rejected"
    generated_at = datetime.now(timezone.utc).isoformat()
    return {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": generated_at,
        "status": decision,
        "decision": decision,
        "lane": "alpha_search",
        "change_type": "governed_candidate_pool_expansion",
        "mechanism_family": "consumer_digital_platform_universe_subbasket",
        "hypothesis": (
            "The HOOD/RBLX/SOFI sub-basket may add alpha only when existing "
            "signal context confirms a strong tape or relative leadership. A "
            "shared governance gate should preserve the mid-window winners from "
            "exp-20260505-011 while blocking weak-tape slot consumption."
        ),
        "alpha_hypothesis": {
            "category": "entry / universe governance",
            "why_this_now": (
                "LLM soft-ranking and event-bundle promotion are waiting for "
                "forward samples. The broad attention-list expansion failed, "
                "but exp-20260505-011 left a smaller positive-PnL sub-basket "
                "whose instability can be tested with existing production fields."
            ),
        },
        "historical_experiment_check": {
            "blocked_repeats": {
                "exp-20260505-009": "Rejected broad historical attention-list expansion.",
                "exp-20260505-011": (
                    "Rejected ungated HOOD/RBLX/SOFI core promotion. This tests "
                    "only shared governance gates for that same sub-basket."
                ),
                "exp-20260505-018": "Rejected breakout subsequence ranking; this does not alter ranking.",
            },
            "mechanism_insight_check": (
                "Recent insights prohibit broad noisy ticker growth. This keeps "
                "the basket fixed and changes only the governance condition."
            ),
            "why_not_simple_repeat": (
                "The prior variable was adding the basket unconditionally. This "
                "variable is the gate that determines whether basket candidates "
                "are allowed to carry risk."
            ),
        },
        "parameters": {
            "single_causal_variable": "consumer platform sub-basket governance gate",
            "subbasket_tickers": subbasket,
            "source_experiment": SOURCE_EXPERIMENT_ID,
            "snapshot_source": SNAPSHOT_EXPERIMENT_ID,
            "base_universe_count": len(base_universe),
            "expanded_universe_count": len(expanded_universe),
            "tested_variants": VARIANTS,
            "fresh_snapshots_reused": {label: row["snapshot"] for label, row in WINDOWS.items()},
            "locked_variables": [
                "signal_engine",
                "risk_engine",
                "portfolio_engine baseline sizing",
                "production_parity entry planning",
                "entry ordering",
                "exits",
                "add-ons",
                "LLM replay",
                "news replay",
                "event sleeves",
                "all numeric thresholds outside this gate",
            ],
        },
        "date_range": {label: f"{row['start']} -> {row['end']}" for label, row in WINDOWS.items()},
        "market_regime_summary": {label: row["state_note"] for label, row in WINDOWS.items()},
        "before_metrics": {label: row["metrics"] for label, row in baseline.items()},
        "variants": variants,
        "best_variant": best_variant,
        "after_metrics": {
            label: row["after"]
            for label, row in best["by_window"].items()
        },
        "delta_metrics": {
            "by_window": best["by_window"],
            "aggregate": best["aggregate"],
        },
        "gate4": {
            "passed": accepted,
            "basis": (
                "Requires material aggregate EV/PnL/Sharpe/drawdown/trade-count "
                "improvement, EV improvement in at least two of three fixed windows, "
                "and no EV-regressed window."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "production_watchlist_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "promotion_requirement": (
                "If accepted, promote only through a shared universe-governance "
                "gate or default-off pilot sleeve used by both run.py and "
                "backtester.py."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": "Production-aligned LLM soft-ranking samples remain sparse.",
        },
        "rejection_reason": None if accepted else (
            "Did not clear three-window materiality and stability gate."
        ),
        "next_retry_requires": [] if accepted else [
            "Do not retry the HOOD/RBLX/SOFI basket with simple risk_on/SPY-leader/TQS gates.",
            "A valid retry needs forward replacement-value evidence or a different ex-ante basket mechanism.",
        ],
        "risk_of_change": (
            "The sub-basket can add high-beta consumer/platform exposure and may "
            "consume scarce slots during weak tapes; production promotion needs "
            "shared governance and forward replacement-value evidence."
        ),
        "why_not_other_attractive_points": {
            "LLM_soft_ranking": "Still sample-limited.",
            "event_bundle_promotion": "Needs closed forward paper outcomes.",
            "broad_watchlist": "Rejected by exp-20260505-009.",
            "nearby_breakout_ranking": "Rejected by exp-20260505-018.",
        },
        "related_files": [
            "quant/experiments/exp_20260505_020_consumer_platform_governance_gate.py",
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "docs/experiment_log.jsonl",
        ],
    }


def main() -> int:
    payload = build_payload()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": payload["generated_at"],
        "decision": payload["decision"],
        "title": "Consumer platform governance gate",
        "summary": (
            "Accepted candidate; promote only through shared governance."
            if payload["gate4"]["passed"]
            else "Rejected; gate did not stabilize the sub-basket."
        ),
        "best_variant": payload["best_variant"],
        "gate4": payload["gate4"],
        "delta_metrics": payload["delta_metrics"]["aggregate"],
        "log_file": str(LOG_JSON.relative_to(REPO_ROOT)),
    }
    _write_json(TICKET_JSON, ticket)
    _write_artifact(payload)
    _append_jsonl(EXPERIMENT_LOG_JSONL, payload)
    print(json.dumps({
        "experiment_id": payload["experiment_id"],
        "decision": payload["decision"],
        "best_variant": payload["best_variant"],
        "aggregate": payload["delta_metrics"]["aggregate"],
        "out_json": str(OUT_JSON.relative_to(REPO_ROOT)),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
