"""exp-20260505-032: enterprise infrastructure incumbent basket replay.

Alpha search. This tests a tiny, mechanism-grounded candidate-pool extension
after the broad historical-watchlist expansion failed. It does not alter
production universe, ranking, sizing, exits, LLM, news, or event sleeves.
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

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260505-032"
SUB_BASKET = ["AKAM", "ORCL"]
SOURCE_EXPERIMENT_ID = "exp-20260505-009"

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

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "enterprise_infra_incumbent_basket.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_enterprise_infra_incumbent_basket.md"
)


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


def _run_engine(universe: list[str], window: dict[str, str]) -> dict[str, Any]:
    snapshot = REPO_ROOT / window["snapshot"]
    if not snapshot.exists():
        raise FileNotFoundError(
            f"Required snapshot missing: {snapshot}. Run {SOURCE_EXPERIMENT_ID} first."
        )
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
                "return_pct": _round(trade.get("return_pct"), 4),
                "exit_reason": trade.get("exit_reason"),
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
    }


def _accepted(aggregate: dict[str, Any]) -> bool:
    majority_ev = aggregate["ev_windows_improved"] >= 2
    material_primary = (aggregate["expected_value_score_delta_pct"] or 0.0) > 0.10
    material_pnl = (
        (aggregate["total_pnl_delta_pct"] or 0.0) > 0.05
        and (aggregate["expected_value_score_delta_sum"] or 0.0) > 0.0
    )
    return bool(majority_ev and (material_primary or material_pnl))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_artifact(payload: dict[str, Any]) -> None:
    aggregate = payload["delta_metrics"]["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} Enterprise Infrastructure Incumbent Basket",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Sub-basket",
        "",
        ", ".join(f"`{ticker}`" for ticker in payload["parameters"]["subbasket_tickers"]),
        "",
        "## Three-window deltas",
        "",
        "| Window | EV delta | PnL delta | SharpeD delta | DD delta | WR delta | Trades delta | Basket trades | Basket PnL |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, row in payload["delta_metrics"]["by_window"].items():
        delta = row["delta"]
        stats = row["subbasket_trade_stats"]
        lines.append(
            f"| `{label}` | {delta['expected_value_score']:+.4f} | "
            f"{delta['total_pnl']:+.2f} | {delta['sharpe_daily']:+.2f} | "
            f"{delta['max_drawdown_pct']:+.4f} | {delta['win_rate']:+.4f} | "
            f"{delta['trade_count']:+d} | {stats['trade_count']} | "
            f"{stats['total_pnl']:+.2f} |"
        )
    lines.extend([
        "",
        "## Aggregate",
        "",
        f"- EV delta sum: `{aggregate['expected_value_score_delta_sum']:+.4f}` "
        f"({aggregate['expected_value_score_delta_pct']:+.2%})",
        f"- PnL delta sum: `${aggregate['total_pnl_delta_sum']:+,.2f}` "
        f"({aggregate['total_pnl_delta_pct']:+.2%})",
        f"- EV windows improved/regressed: `{aggregate['ev_windows_improved']}` / `{aggregate['ev_windows_regressed']}`",
        f"- Sub-basket trade count / PnL: `{aggregate['subbasket_trade_count_sum']}` / `${aggregate['subbasket_pnl_sum']:+,.2f}`",
        "",
        "## Parity",
        "",
        "No production universe or order path changed. A promotion would need universe governance or a default-off pilot adapter before live orders.",
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

    rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    subbasket_set = set(subbasket)
    for label, window in WINDOWS.items():
        print(f"[{label}] baseline on {window['snapshot']}")
        before_result = _run_engine(base_universe, window)
        print(f"[{label}] expanded with {','.join(subbasket)}")
        after_result = _run_engine(expanded_universe, window)
        before = _metrics(before_result)
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
                before_result.get("entry_execution_attribution", {}).get("reason_counts", {})
            ),
            "entry_reason_counts_after": (
                after_result.get("entry_execution_attribution", {}).get("reason_counts", {})
            ),
        }
        print(
            f"[{label}] EV={delta['expected_value_score']:+.4f} "
            f"PnL={delta['total_pnl']:+.2f} trades={delta['trade_count']:+d} "
            f"basket_pnl={stats['total_pnl']:+.2f}"
        )

    aggregate = _aggregate(rows)
    accepted = _accepted(aggregate)
    decision = "accepted_for_governance_review" if accepted else "rejected"
    generated_at = datetime.now(timezone.utc).isoformat()
    return {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": generated_at,
        "status": decision,
        "decision": decision,
        "lane": "alpha_search",
        "change_type": "narrow_candidate_pool_expansion",
        "mechanism_family": "enterprise_infra_incumbent_universe_subbasket",
        "hypothesis": (
            "A tiny enterprise infrastructure incumbent basket may extend the "
            "existing A/B trend and breakout engine without adding noisy "
            "short-history, leveraged, macro ETF, or speculative event tickers. "
            "AKAM and ORCL are liquid mature infrastructure names tied to cloud, "
            "edge delivery, and database/platform spend, so their signals should "
            "compete more like existing core large caps than like broad watchlist "
            "noise."
        ),
        "alpha_hypothesis": {
            "category": "entry / universe governance",
            "why_this_now": (
                "LLM soft-ranking and event-bundle promotion remain forward-sample "
                "limited. Broad watchlist expansion and the consumer platform "
                "sub-basket were rejected, so this tests a smaller mature "
                "infrastructure sub-basket with the same fixed three-window protocol."
            ),
        },
        "historical_experiment_check": {
            "blocked_repeats": {
                "exp-20260505-009": (
                    "Rejected broad historical attention-list expansion. This "
                    "does not repeat the broad list; it tests two mature liquid "
                    "infrastructure incumbents with the same fresh snapshots."
                ),
                "exp-20260505-011": (
                    "Rejected consumer digital platform basket. This uses a "
                    "different mechanism: enterprise infrastructure incumbents, "
                    "not high-beta consumer platforms."
                ),
                "exp-20260501-008": (
                    "AI power/pilot universe path is governed separately. This "
                    "does not include pilot/specialist names such as INTC, LITE, "
                    "BE, VST, miners, or short-history names."
                ),
                "exp-20260505-018": "Rejected breakout slot ranking.",
                "exp-20260505-031": "Rejected event-bundle follow-through delay.",
            },
            "mechanism_insight_check": (
                "Recent notes prohibit broad noisy ticker growth, LLM soft-ranking "
                "without samples, and direct event-bundle retunes. This test keeps "
                "production unchanged and changes only a two-name candidate basket."
            ),
            "why_not_simple_repeat": (
                "The variable is not broad universe growth, a macro ETF basket, "
                "a sector cap, a ranking retune, or a threshold retune; it is a "
                "two-name governance candidate replay."
            ),
        },
        "parameters": {
            "single_causal_variable": "candidate universe includes AKAM/ORCL sub-basket",
            "subbasket_tickers": subbasket,
            "source_experiment": SOURCE_EXPERIMENT_ID,
            "base_universe_count": len(base_universe),
            "expanded_universe_count": len(expanded_universe),
            "fresh_snapshots_reused": {label: row["snapshot"] for label, row in WINDOWS.items()},
            "data_fields_verified": {
                "ohlcv": ["Open", "High", "Low", "Close", "Volume"],
                "sector": "existing risk_engine sector map when known; Unknown fallback otherwise",
                "entry_date": "simulated by backtester Position",
                "target_price": "computed by shared signal/risk path",
            },
            "locked_variables": [
                "signal_engine",
                "risk_engine",
                "portfolio_engine",
                "production_parity entry planning",
                "position sizing",
                "entry ordering",
                "exits",
                "add-ons",
                "LLM replay",
                "news replay",
                "event sleeves",
                "all numeric thresholds",
            ],
        },
        "date_range": {label: f"{row['start']} -> {row['end']}" for label, row in WINDOWS.items()},
        "market_regime_summary": {label: row["state_note"] for label, row in WINDOWS.items()},
        "before_metrics": {label: row["before"] for label, row in rows.items()},
        "after_metrics": {label: row["after"] for label, row in rows.items()},
        "delta_metrics": {
            "by_window": rows,
            "aggregate": aggregate,
        },
        "gate4": {
            "passed": accepted,
            "basis": (
                "Requires EV improvement in at least two of three fixed windows "
                "plus either aggregate EV improvement above 10% or aggregate PnL "
                "improvement above 5% with positive aggregate EV. Single-window "
                "Sharpe improvement is not enough when aggregate PnL regresses."
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
                "If retained, promote only through universe governance or a "
                "default-off pilot sleeve with run/backtester parity and forward "
                "replacement-value attribution."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": "Production-aligned LLM soft-ranking samples remain sparse.",
        },
        "rejection_reason": None if accepted else "Did not clear three-window materiality and stability gate.",
        "next_action": (
            "If accepted, build a default-off governance queue before any live "
            "core promotion. If rejected, do not mine more broad-watchlist subsets "
            "without a stronger ex-ante discriminator."
        ),
        "risk_of_change": (
            "The basket may add mature tech/platform exposure that competes with "
            "existing Technology winners and consumes scarce slots; production "
            "promotion needs forward replacement-value evidence."
        ),
        "why_not_other_attractive_points": {
            "LLM_soft_ranking": "Still sample-limited.",
            "event_bundle_promotion": "Needs closed forward paper outcomes.",
            "broad_watchlist": "Rejected by exp-20260505-009.",
            "consumer_platform_basket": "Rejected by exp-20260505-011.",
            "AI_power_pilot_names": "Governed by separate pilot path and forward replacement-value protocol.",
            "same_sample_event_retuning": "Blocked by recent mechanism insights.",
        },
        "related_files": [
            "quant/experiments/exp_20260505_032_enterprise_infra_incumbent_basket.py",
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
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
        "title": "Enterprise infrastructure incumbent basket",
        "summary": payload["next_action"],
        "gate4": payload["gate4"],
        "delta_metrics": payload["delta_metrics"]["aggregate"],
        "log_file": str(LOG_JSON.relative_to(REPO_ROOT)),
    }
    _write_json(TICKET_JSON, ticket)
    _write_artifact(payload)
    print(json.dumps({
        "experiment_id": payload["experiment_id"],
        "decision": payload["decision"],
        "aggregate": payload["delta_metrics"]["aggregate"],
        "out_json": str(OUT_JSON.relative_to(REPO_ROOT)),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
