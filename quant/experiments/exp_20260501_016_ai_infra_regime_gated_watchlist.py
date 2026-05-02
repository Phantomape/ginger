"""exp-20260501-016 regime-gated AI infra watchlist.

Alpha search. Prior AI infrastructure universe tests found real replacement
pressure, but raw watchlist promotion was too fragile in old_thin. This tests
one causal variable: whether added AI infra candidates should be active only
when the market tape is supportive. Signal rules, ranking, sizing, exits,
add-ons, LLM/news replay, and existing production tickers stay locked.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
import risk_engine  # noqa: E402
import signal_engine  # noqa: E402


EXPERIMENT_ID = "exp-20260501-016"
SOURCE_EXPERIMENT_ID = "exp-20260501-008"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "ai_infra_regime_gated_watchlist.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
PLAYBOOK = REPO_ROOT / "docs" / "alpha-optimization-playbook.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": (
            f"data/experiments/{SOURCE_EXPERIMENT_ID}/"
            "ohlcv_aug_20251023_20260421.json"
        ),
        "state_note": "slow-melt bull / accepted-stack dominant tape",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": (
            f"data/experiments/{SOURCE_EXPERIMENT_ID}/"
            "ohlcv_aug_20250423_20251022.json"
        ),
        "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": (
            f"data/experiments/{SOURCE_EXPERIMENT_ID}/"
            "ohlcv_aug_20241002_20250422.json"
        ),
        "state_note": "mixed-to-weak older tape with lower win rate",
    }),
])

BASELINE = {
    "late_strong": {
        "expected_value_score": 2.7000,
        "sharpe_daily": 4.30,
        "total_pnl": 62788.03,
        "total_return_pct": 0.6279,
        "max_drawdown_pct": 0.0439,
        "win_rate": 0.7895,
        "trade_count": 19,
        "survival_rate": 0.8039,
        "tail_loss_share": 0.5045,
    },
    "mid_weak": {
        "expected_value_score": 1.2036,
        "sharpe_daily": 2.58,
        "total_pnl": 46654.10,
        "total_return_pct": 0.4665,
        "max_drawdown_pct": 0.0799,
        "win_rate": 0.5238,
        "trade_count": 21,
        "survival_rate": 0.7925,
        "tail_loss_share": 0.4839,
    },
    "old_thin": {
        "expected_value_score": 0.2563,
        "sharpe_daily": 1.27,
        "total_pnl": 20181.65,
        "total_return_pct": 0.2018,
        "max_drawdown_pct": 0.0688,
        "win_rate": 0.4091,
        "trade_count": 22,
        "survival_rate": 0.9167,
        "tail_loss_share": 0.4234,
    },
}

VARIANTS = OrderedDict([
    ("be_intc_bull_positive", {
        "added": ["BE", "INTC"],
        "gate": "market_regime == BULL and spy_10d_return > 0",
    }),
    ("be_intc_bull_indices_positive", {
        "added": ["BE", "INTC"],
        "gate": (
            "market_regime == BULL and spy_10d_return > 0 "
            "and qqq_pct_from_ma > 0"
        ),
    }),
    ("be_only_bull_positive", {
        "added": ["BE"],
        "gate": "market_regime == BULL and spy_10d_return > 0",
    }),
])

SECTOR_PATCH = {
    "BE": "Energy",
    "INTC": "Technology",
}

_state = {
    "filtered_signals": 0,
    "allowed_signals": 0,
    "gate_name": "",
}


def _metrics(result: dict) -> dict:
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": (result.get("benchmarks") or {}).get(
            "strategy_total_return_pct"
        ),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
        "tail_loss_share": result.get("tail_loss_share"),
        "ai_infra_allowed_signals": _state["allowed_signals"],
        "ai_infra_filtered_signals": _state["filtered_signals"],
    }


def _delta(after: dict, before: dict) -> dict:
    out = {}
    for key, before_val in before.items():
        after_val = after.get(key)
        out[key] = (
            round(after_val - before_val, 6)
            if isinstance(after_val, (int, float))
            and isinstance(before_val, (int, float))
            else None
        )
    return out


def _candidate_trade_summary(result: dict, added: set[str]) -> dict:
    trades = [t for t in result.get("trades", []) if t.get("ticker") in added]
    by_ticker = {}
    for trade in trades:
        ticker = trade.get("ticker")
        rec = by_ticker.setdefault(ticker, {"trades": 0, "pnl": 0.0, "wins": 0})
        rec["trades"] += 1
        rec["pnl"] += float(trade.get("pnl") or 0.0)
        if (trade.get("pnl") or 0) > 0:
            rec["wins"] += 1
    for rec in by_ticker.values():
        rec["pnl"] = round(rec["pnl"], 2)
        rec["win_rate"] = (
            round(rec["wins"] / rec["trades"], 4) if rec["trades"] else None
        )
    return {
        "candidate_trade_count": len(trades),
        "candidate_pnl": round(sum(float(t.get("pnl") or 0.0) for t in trades), 2),
        "by_ticker": by_ticker,
    }


def _passes_gate(gate_name: str, market_context: dict) -> bool:
    if (market_context or {}).get("market_regime") != "BULL":
        return False
    if ((market_context or {}).get("spy_10d_return") or 0) <= 0:
        return False
    if gate_name == "be_intc_bull_indices_positive":
        qqq_pct = (market_context or {}).get("qqq_pct_from_ma")
        if qqq_pct is None or qqq_pct <= 0:
            return False
    return True


def _install_signal_gate(added: set[str], gate_name: str):
    original = signal_engine.generate_signals

    def gated_generate_signals(
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
        out = []
        allow_added = _passes_gate(gate_name, market_context or {})
        for sig in signals:
            if sig.get("ticker") not in added:
                out.append(sig)
                continue
            if allow_added:
                _state["allowed_signals"] += 1
                sig.setdefault("conditions_met", {})[
                    "ai_infra_regime_gate"
                ] = gate_name
                out.append(sig)
            else:
                _state["filtered_signals"] += 1
        return out

    signal_engine.generate_signals = gated_generate_signals
    return original


def _run_window(universe: list[str], window: dict, added: set[str], gate_name: str) -> dict:
    _state["filtered_signals"] = 0
    _state["allowed_signals"] = 0
    _state["gate_name"] = gate_name
    original_generate = _install_signal_gate(added, gate_name)
    try:
        result = BacktestEngine(
            universe,
            start=window["start"],
            end=window["end"],
            ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
        ).run()
    finally:
        signal_engine.generate_signals = original_generate
    if "error" in result:
        raise RuntimeError(result["error"])
    return result


def _aggregate(rows: list[dict]) -> dict:
    pnl_delta_sum = round(sum(r["delta"]["total_pnl"] for r in rows), 2)
    baseline_pnl_sum = round(sum(BASELINE[r["window"]]["total_pnl"] for r in rows), 2)
    candidate_pnl_sum = round(
        sum(r["candidate_trades"]["candidate_pnl"] for r in rows), 2
    )
    return {
        "expected_value_score_delta_sum": round(
            sum(r["delta"]["expected_value_score"] for r in rows), 4
        ),
        "total_pnl_delta_sum": pnl_delta_sum,
        "baseline_total_pnl_sum": baseline_pnl_sum,
        "total_pnl_delta_pct": (
            round(pnl_delta_sum / baseline_pnl_sum, 6) if baseline_pnl_sum else None
        ),
        "ev_windows_improved": sum(
            1 for r in rows if r["delta"]["expected_value_score"] > 0
        ),
        "ev_windows_regressed": sum(
            1 for r in rows if r["delta"]["expected_value_score"] < 0
        ),
        "pnl_windows_improved": sum(
            1 for r in rows if r["delta"]["total_pnl"] > 0
        ),
        "pnl_windows_regressed": sum(
            1 for r in rows if r["delta"]["total_pnl"] < 0
        ),
        "max_drawdown_delta_max": round(
            max(r["delta"]["max_drawdown_pct"] for r in rows), 6
        ),
        "trade_count_delta_sum": sum(r["delta"]["trade_count"] for r in rows),
        "win_rate_delta_min": round(min(r["delta"]["win_rate"] for r in rows), 6),
        "candidate_trade_count_sum": sum(
            r["candidate_trades"]["candidate_trade_count"] for r in rows
        ),
        "candidate_pnl_sum": candidate_pnl_sum,
        "interaction_pnl_sum": round(pnl_delta_sum - candidate_pnl_sum, 2),
        "allowed_signals_sum": sum(
            r["metrics"]["ai_infra_allowed_signals"] for r in rows
        ),
        "filtered_signals_sum": sum(
            r["metrics"]["ai_infra_filtered_signals"] for r in rows
        ),
    }


def _gate4_passed(agg: dict) -> bool:
    return (
        agg["total_pnl_delta_pct"] is not None
        and agg["total_pnl_delta_pct"] > 0.05
        and agg["ev_windows_improved"] >= 2
        and agg["ev_windows_regressed"] == 0
        and agg["win_rate_delta_min"] >= 0
    )


def _ranked(summary: dict) -> list[dict]:
    rows = []
    for name, rec in summary.items():
        agg = rec["aggregate"]
        rows.append({
            "variant": name,
            "added": rec["added"],
            "gate": rec["gate"],
            "ev_delta_sum": agg["expected_value_score_delta_sum"],
            "pnl_delta_sum": agg["total_pnl_delta_sum"],
            "pnl_delta_pct": agg["total_pnl_delta_pct"],
            "ev_windows_improved": agg["ev_windows_improved"],
            "ev_windows_regressed": agg["ev_windows_regressed"],
            "win_rate_delta_min": agg["win_rate_delta_min"],
            "max_drawdown_delta_max": agg["max_drawdown_delta_max"],
            "candidate_trade_count_sum": agg["candidate_trade_count_sum"],
            "candidate_pnl_sum": agg["candidate_pnl_sum"],
            "allowed_signals_sum": agg["allowed_signals_sum"],
            "filtered_signals_sum": agg["filtered_signals_sum"],
        })
    return sorted(
        rows,
        key=lambda r: (
            r["ev_windows_improved"] - r["ev_windows_regressed"],
            r["ev_delta_sum"],
            r["pnl_delta_sum"],
            r["win_rate_delta_min"],
        ),
        reverse=True,
    )


def _append_once(path: Path, marker: str, text: str) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker not in existing:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(text)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)

    baseline_universe = sorted(get_universe())
    original_sector_map = dict(risk_engine.SECTOR_MAP)
    risk_engine.SECTOR_MAP.update(SECTOR_PATCH)

    summary = {}
    try:
        for variant, cfg in VARIANTS.items():
            added = set(cfg["added"])
            universe = sorted(set(baseline_universe) | added)
            variant_rows = []
            for label, window in WINDOWS.items():
                result = _run_window(universe, window, added, variant)
                metrics = _metrics(result)
                delta = _delta(metrics, BASELINE[label])
                row = {
                    "window": label,
                    "variant": variant,
                    "added": sorted(added),
                    "gate": cfg["gate"],
                    "metrics": metrics,
                    "delta": delta,
                    "candidate_trades": _candidate_trade_summary(result, added),
                }
                variant_rows.append(row)
                print(
                    f"[{label} {variant}] EV={metrics['expected_value_score']} "
                    f"PnL={metrics['total_pnl']} SharpeD={metrics['sharpe_daily']} "
                    f"WR={metrics['win_rate']} allowed={metrics['ai_infra_allowed_signals']} "
                    f"filtered={metrics['ai_infra_filtered_signals']}"
                )
            summary[variant] = {
                "added": sorted(added),
                "gate": cfg["gate"],
                "by_window": {
                    r["window"]: {
                        "before": BASELINE[r["window"]],
                        "after": r["metrics"],
                        "delta": r["delta"],
                        "candidate_trades": r["candidate_trades"],
                    }
                    for r in variant_rows
                },
                "aggregate": _aggregate(variant_rows),
            }
    finally:
        risk_engine.SECTOR_MAP.clear()
        risk_engine.SECTOR_MAP.update(original_sector_map)

    ranked = _ranked(summary)
    best_variant = ranked[0]["variant"]
    best = summary[best_variant]["aggregate"]
    gate4_passed = _gate4_passed(best)
    decision = "accepted_candidate" if gate4_passed else "rejected"

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": decision,
        "decision": decision,
        "lane": "alpha_search",
        "change_type": "candidate_universe_regime_gated_ai_infra",
        "hypothesis": (
            "AI infrastructure individual names may be profitable replacement "
            "candidates only when the broad tape is supportive; a market-regime "
            "activation gate may preserve the BE/INTC mid/late upside while "
            "avoiding the old_thin fragility that blocked raw promotion."
        ),
        "alpha_hypothesis_category": "candidate_universe_entry_gating",
        "parameters": {
            "single_causal_variable": "AI infra added-candidate activation gate",
            "source_experiment": SOURCE_EXPERIMENT_ID,
            "tested_variants": VARIANTS,
            "sector_map_patch": SECTOR_PATCH,
            "locked_variables": [
                "existing production universe",
                "signal generation rules for all tickers",
                "candidate ranking",
                "position sizing",
                "position caps",
                "portfolio heat",
                "add-ons",
                "exits",
                "LLM/news replay",
                "earnings strategy",
            ],
        },
        "date_range": {
            "primary": "2025-10-23 -> 2026-04-21",
            "secondary": [
                "2025-04-23 -> 2025-10-22",
                "2024-10-02 -> 2025-04-22",
            ],
        },
        "market_regime_summary": {
            label: window["state_note"] for label, window in WINDOWS.items()
        },
        "before_metrics": BASELINE,
        "after_metrics": summary,
        "ranking": ranked,
        "best_variant": best_variant,
        "best_variant_gate4_passed": gate4_passed,
        "gate4_basis": (
            "Acceptance requires aggregate PnL > +5%, EV improvement in at "
            "least two windows without any EV regression, and no win-rate "
            "decline because this would add production watchlist exposure."
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, add selected tickers and the activation gate to a "
                "shared production/backtest policy before promotion."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft-ranking remains sample-limited, so this tests an "
                "alternate deterministic candidate-pool alpha."
            ),
        },
        "history_guardrails": {
            "builds_on_exp_20260501_008": True,
            "builds_on_exp_20260501_009": True,
            "builds_on_exp_20260501_010": True,
            "builds_on_exp_20260501_015": True,
            "not_raw_be_intc_promotion": True,
            "not_raw_intc_lite_promotion": True,
            "why_not_simple_repeat": (
                "This does not add another raw watchlist subset. It tests a "
                "specific market-state activation rule for the previously "
                "positive-but-fragile AI infra pool."
            ),
        },
        "rejection_reason": None if gate4_passed else (
            "No regime-gated AI infra variant satisfied the fixed-window "
            "production promotion gate."
        ),
        "next_retry_requires": [] if gate4_passed else [
            "Forward evidence for the AI infra pool, or a point-in-time "
            "event/news discriminator.",
            "A gate that improves at least two fixed windows without EV or "
            "win-rate regression.",
        ],
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            "quant/experiments/exp_20260501_016_ai_infra_regime_gated_watchlist.py",
        ],
    }

    for path in (OUT_JSON, LOG_JSON):
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    TICKET_JSON.write_text(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "status": decision,
        "title": "Regime-gated AI infra watchlist",
        "summary": (
            f"Best {best_variant} Gate4={gate4_passed} "
            f"PnL={best['total_pnl_delta_sum']:+.2f}"
        ),
        "best_variant": best_variant,
        "best_aggregate": best,
        "production_impact": payload["production_impact"],
    }, indent=2) + "\n", encoding="utf-8")

    compact = {k: v for k, v in payload.items() if k not in ("after_metrics",)}
    compact["after_metrics"] = {
        name: rec["aggregate"] for name, rec in summary.items()
    }
    _append_once(
        EXPERIMENT_LOG,
        f'"experiment_id": "{EXPERIMENT_ID}"',
        json.dumps(compact, ensure_ascii=False) + "\n",
    )

    if not gate4_passed:
        playbook_text = f"""

### 2026-05-01 mechanism update: Regime-gated AI infra watchlist

Status: rejected.

Core conclusion: `{EXPERIMENT_ID}` tested whether the positive-but-fragile AI
infrastructure watchlist lead could be rescued by enabling added `BE` / `INTC`
candidates only in supportive broad-market states. It should not be promoted.

Evidence: best variant `{best_variant}` produced aggregate PnL delta
`${best['total_pnl_delta_sum']:,.2f}` / `{best['total_pnl_delta_pct']:.2%}` and
aggregate EV delta `{best['expected_value_score_delta_sum']:+.4f}`. Fixed-window
gate status: EV improved in `{best['ev_windows_improved']}` windows, regressed
in `{best['ev_windows_regressed']}`, and minimum win-rate delta was
`{best['win_rate_delta_min']:+.4f}`.

Mechanism insight: a simple broad-tape activation gate is not enough to turn AI
infra names into a production-ready universe addition. The pool still needs
forward evidence or point-in-time event/news confirmation, not another raw
subset or broad BULL-only switch.

Do not repeat: raw `BE + INTC`, raw `INTC`, raw `INTC + LITE`, or simple
BULL/positive-SPY activation gates for these AI infra candidates without new
forward or event/news evidence.
"""
        _append_once(PLAYBOOK, f"`{EXPERIMENT_ID}`", playbook_text)

    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "decision": decision,
        "best_variant": best_variant,
        "best_aggregate": best,
        "ranking": ranked,
    }, indent=2))


if __name__ == "__main__":
    main()
