"""exp-20260506-004: quality compounder basket replay.

Alpha search. Tests a narrow, non-LLM candidate-pool extension after recent
broad universe and high-beta sub-basket additions failed. The replay adds only
three liquid quality/defensive-growth names from the fresh OHLCV archive and
patches sector metadata inside the experiment. It does not alter production
universe, ranking, sizing, exits, LLM, news, event sleeves, or thresholds.
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

import risk_engine  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260506-004"
SUB_BASKET = ["COST", "IDXX", "LRN"]
SECTOR_OVERRIDES = {
    "COST": "Consumer Staples",
    "IDXX": "Healthcare",
    "LRN": "Consumer Discretionary",
}
SOURCE_EXPERIMENT_ID = "exp-20260505-009"

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/experiments/exp-20260505-009/ohlcv/exp-20260505-009_late_strong_fresh_ohlcv.json",
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/experiments/exp-20260505-009/ohlcv/exp-20260505-009_mid_weak_fresh_ohlcv.json",
                "state_note": "rotation-heavy bull where strategy profits but lags indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/experiments/exp-20260505-009/ohlcv/exp-20260505-009_old_thin_fresh_ohlcv.json",
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "quality_compounder_basket.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_quality_compounder_basket.md"
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
            out[key] = (
                int(after_value - before_value)
                if key in {"trade_count", "signals_generated", "signals_survived"}
                else _round(after_value - before_value, 6)
            )
    return out


def _patch_sector_map() -> dict[str, str | None]:
    previous = {ticker: risk_engine.SECTOR_MAP.get(ticker) for ticker in SUB_BASKET}
    risk_engine.SECTOR_MAP.update(SECTOR_OVERRIDES)
    return previous


def _restore_sector_map(previous: dict[str, str | None]) -> None:
    for ticker, old_value in previous.items():
        if old_value is None:
            risk_engine.SECTOR_MAP.pop(ticker, None)
        else:
            risk_engine.SECTOR_MAP[ticker] = old_value


def _run_engine(universe: list[str], window: dict[str, str]) -> dict[str, Any]:
    snapshot = REPO_ROOT / window["snapshot"]
    if not snapshot.exists():
        raise FileNotFoundError(
            f"Required snapshot missing: {snapshot}. Run {SOURCE_EXPERIMENT_ID} first."
        )
    previous = _patch_sector_map()
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
        _restore_sector_map(previous)
    if "error" in result:
        raise RuntimeError(result["error"])
    return result


def _trade_stats(trades: list[dict[str, Any]], tickers: set[str]) -> dict[str, Any]:
    rows = [trade for trade in trades if str(trade.get("ticker") or "").upper() in tickers]
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
        "subbasket_trade_count_sum": sum(
            row["subbasket_trade_stats"]["trade_count"] for row in rows.values()
        ),
        "subbasket_pnl_sum": _round(
            sum(row["subbasket_trade_stats"]["total_pnl"] or 0.0 for row in rows.values()), 2
        ),
    }


def _accepted(aggregate: dict[str, Any]) -> bool:
    majority_ev = aggregate["ev_windows_improved"] >= 2
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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_artifact(payload: dict[str, Any]) -> None:
    aggregate = payload["delta_metrics"]["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} Quality Compounder Basket",
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
            "| `{label}` | {ev:+.4f} | {pnl:+.2f} | {sharpe:+.2f} | "
            "{dd:+.4f} | {wr:+.4f} | {trades:+d} | {basket_trades:d} | "
            "{basket_pnl:+.2f} |".format(
                label=label,
                ev=delta.get("expected_value_score", 0.0),
                pnl=delta.get("total_pnl", 0.0),
                sharpe=delta.get("sharpe_daily", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                wr=delta.get("win_rate", 0.0),
                trades=delta.get("trade_count", 0),
                basket_trades=stats["trade_count"],
                basket_pnl=stats["total_pnl"] or 0.0,
            )
        )
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            f"- EV delta sum: `{aggregate['expected_value_score_delta_sum']:+.4f}` ({aggregate['expected_value_score_delta_pct']:+.2%})",
            f"- PnL delta sum: `${aggregate['total_pnl_delta_sum']:+.2f}` ({aggregate['total_pnl_delta_pct']:+.2%})",
            f"- EV windows improved/regressed: `{aggregate['ev_windows_improved']}` / `{aggregate['ev_windows_regressed']}`",
            f"- PnL windows improved/regressed: `{aggregate['pnl_windows_improved']}` / `{aggregate['pnl_windows_regressed']}`",
            f"- Sub-basket trade count / PnL: `{aggregate['subbasket_trade_count_sum']}` / `${aggregate['subbasket_pnl_sum']:+.2f}`",
            "",
            "## Mechanism Read",
            "",
            payload["mechanism_read"],
            "",
            "## Parity",
            "",
            payload["production_impact"]["promotion_requirement"],
        ]
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_payload() -> dict[str, Any]:
    base_universe = sorted(set(get_universe()))
    subbasket = sorted(set(SUB_BASKET))
    expanded_universe = sorted(set(base_universe) | set(subbasket))
    added_tickers = sorted(set(expanded_universe) - set(base_universe))

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
        "mechanism_family": "quality_compounder_universe_subbasket",
        "hypothesis": (
            "A small quality/defensive-growth basket may improve the universe "
            "without repeating broad ticker growth: COST, IDXX, and LRN have "
            "full fresh-snapshot OHLCV coverage, liquid single-name behavior, "
            "and cleaner business quality than recent rejected high-beta "
            "consumer, cyber, or enterprise-infra baskets."
        ),
        "alpha_hypothesis": {
            "category": "entry / universe governance",
            "why_this_now": (
                "LLM soft-ranking remains sample-limited, and event-bundle "
                "promotion still needs closed forward paper outcomes. The "
                "test therefore moves to a distinct non-LLM alpha surface: "
                "small candidate-pool quality expansion under existing A/B rules."
            ),
        },
        "historical_experiment_check": {
            "blocked_repeats": {
                "exp-20260505-009": "Rejected broad historical attention-list expansion.",
                "exp-20260505-011": "Rejected consumer digital platform sub-basket.",
                "exp-20260505-032": "Rejected enterprise infrastructure incumbent basket.",
                "exp-20260505-033": "Rejected cybersecurity infrastructure basket.",
                "exp-20260506-002": "Industrial infrastructure/defense basket produced no usable trade impact.",
            },
            "mechanism_insight_check": (
                "Recent insights block noisy broad ticker growth and same-sample "
                "event retuning. This is a three-name, full-coverage, "
                "mechanism-labeled basket with all strategy rules held constant."
            ),
            "why_not_simple_repeat": (
                "The variable is not broad watchlist growth, consumer platform "
                "momentum, enterprise/cyber infra, industrials, thresholds, "
                "ranking, LLM, or event overlay behavior."
            ),
        },
        "parameters": {
            "single_causal_variable": "candidate universe includes COST/IDXX/LRN sub-basket",
            "subbasket_tickers": subbasket,
            "sector_overrides": SECTOR_OVERRIDES,
            "source_experiment": SOURCE_EXPERIMENT_ID,
            "base_universe_count": len(base_universe),
            "expanded_universe_count": len(expanded_universe),
            "added_tickers": added_tickers,
            "fresh_snapshots_reused": {label: row["snapshot"] for label, row in WINDOWS.items()},
            "locked_variables": [
                "signal_engine",
                "risk_engine shared policy behavior",
                "portfolio_engine",
                "production parity entry planning",
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
                "Requires material aggregate EV/PnL/Sharpe/drawdown/trade-count "
                "improvement and EV improvement in at least two of three fixed windows."
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
                "No production universe or order path changed. Any positive "
                "future retry must be promoted through universe governance or "
                "a default-off pilot adapter with run/backtester parity."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": "Production-aligned LLM soft-ranking samples remain sparse.",
        },
        "mechanism_read": (
            "The basket did not add stabilizing quality alpha. COST/IDXX/LRN "
            "generated mostly stop-loss entries and consumed scarce slots; EV, "
            "PnL, and win rate regressed in all three windows."
        ),
        "rejection_reason": (
            None
            if accepted
            else (
                "EV and PnL regressed in all three windows, max drawdown worsened "
                "in mid_weak and old_thin, and win rate fell in every window."
            )
        ),
        "next_action": (
            "Do not repeat static quality/defensive-growth sub-basket mining "
            "without event/news replacement-value evidence or a stronger "
            "ex-ante discriminator."
        ),
        "risk_of_change": (
            "The sub-basket can consume scarce slots with lower-momentum stop-outs, "
            "especially in mid/old windows; it also introduces cross-sector "
            "exposure without a proven ranking edge."
        ),
        "why_not_other_attractive_points": {
            "LLM_soft_ranking": "Still sample-limited.",
            "event_bundle_promotion": "Needs closed forward paper outcomes.",
            "options_overlay": "Harness exists but overlay scoring needs joined historical/forward data.",
            "threshold_tuning": "Blocked by recent no-go history and would be less attributable.",
        },
        "related_files": [
            "quant/experiments/exp_20260506_004_quality_compounder_basket.py",
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
        ],
    }


def main() -> int:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": payload["generated_at"],
        "decision": payload["decision"],
        "title": "Quality compounder basket",
        "summary": payload["next_action"],
        "gate4": payload["gate4"],
        "delta_metrics": payload["delta_metrics"]["aggregate"],
        "log_file": str(LOG_JSON.relative_to(REPO_ROOT)),
    }
    _write_json(TICKET_JSON, ticket)
    _write_artifact(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "aggregate": payload["delta_metrics"]["aggregate"],
                "out_json": str(OUT_JSON.relative_to(REPO_ROOT)),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
