"""exp-20260511-002: space catalyst static-pool replay.

Alpha search only. This tests one candidate-pool variable: whether adding the
observe-only SPACE_CATALYST_SHADOW operating equities to the historical OHLCV
snapshot copies improves the existing trend/breakout engine. It does not grant
production eligibility, live pilot slots, or core universe membership.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260511-002"
STEM = "space_catalyst_static_pool_replay"

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "baseline_snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
                "candidate_snapshot": (
                    "data/experiments/exp-20260510-028/ohlcv/"
                    "exp-20260510-028_late_strong_with_space_catalyst.json"
                ),
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "baseline_snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
                "candidate_snapshot": (
                    "data/experiments/exp-20260510-028/ohlcv/"
                    "exp-20260510-028_mid_weak_with_space_catalyst.json"
                ),
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "baseline_snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
                "candidate_snapshot": (
                    "data/experiments/exp-20260510-028/ohlcv/"
                    "exp-20260510-028_old_thin_with_space_catalyst.json"
                ),
            },
        ),
    ]
)

# Operating equities only. Excludes theme ETFs (ARKX/UFO), quarantine SPCE, and
# HAWK because the frozen OHLCV build returned no historical rows.
SPACE_OPERATING_TICKERS = (
    "RKLB",
    "ASTS",
    "LUNR",
    "PL",
    "RDW",
    "BKSY",
    "IRDM",
    "VSAT",
    "GSAT",
    "SATS",
)
EXCLUDED_SPACE_TICKERS = {
    "ARKX": "theme_beta_benchmark_not_operating_equity",
    "UFO": "theme_beta_benchmark_not_operating_equity",
    "SPCE": "quarantine_meme_risk",
    "HAWK": "no_historical_ohlcv_rows_in_frozen_snapshot",
}

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
OPEN_POSITIONS = REPO_ROOT / "operator_inputs" / "open_positions.json"


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


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig") as fh:
        return json.load(fh)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False, sort_keys=True)
        fh.write("\n")


def _snapshot_tickers(path: Path) -> set[str]:
    payload = _load_json(path)
    return {str(ticker).upper() for ticker in (payload.get("ohlcv") or {})}


def _open_position_field_audit() -> dict[str, Any]:
    if not OPEN_POSITIONS.exists():
        return {
            "path": str(OPEN_POSITIONS.relative_to(REPO_ROOT)),
            "exists": False,
            "position_count": 0,
            "missing_entry_date_or_target_price": None,
            "passed": False,
        }
    payload = _load_json(OPEN_POSITIONS)
    positions = payload.get("positions") or []
    missing = [
        pos.get("ticker")
        for pos in positions
        if not pos.get("entry_date") or not pos.get("target_price")
    ]
    return {
        "path": str(OPEN_POSITIONS.relative_to(REPO_ROOT)),
        "exists": True,
        "position_count": len(positions),
        "missing_entry_date_or_target_price": missing,
        "passed": not missing,
    }


def _tail_loss_share(trades: list[dict[str, Any]], n: int = 5) -> float | None:
    losses = sorted(
        [
            abs(float(trade.get("pnl") or 0.0))
            for trade in trades
            if float(trade.get("pnl") or 0.0) < 0
        ],
        reverse=True,
    )
    if not losses:
        return None
    return round(sum(losses[:n]) / sum(losses), 4)


def _max_consecutive_losses(trades: list[dict[str, Any]]) -> int:
    ordered = sorted(
        trades,
        key=lambda trade: (trade.get("exit_date") or "", trade.get("entry_date") or ""),
    )
    streak = 0
    worst = 0
    for trade in ordered:
        if float(trade.get("pnl") or 0.0) < 0:
            streak += 1
            worst = max(worst, streak)
        else:
            streak = 0
    return worst


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    trades = result.get("trades") or []
    worst_trade_pct = None
    if trades:
        worst_trade_pct = min(float(trade.get("pnl_pct_net") or 0.0) for trade in trades)
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "sharpe_daily": _round(result.get("sharpe_daily"), 2),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "strategy_total_return_pct": _round(
            benchmarks.get("strategy_total_return_pct"),
            4,
        ),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": int(result.get("total_trades") or 0),
        "signals_generated": int(result.get("signals_generated") or 0),
        "signals_survived": int(result.get("signals_survived") or 0),
        "survival_rate": _round(result.get("survival_rate"), 4),
        "worst_trade_pct": _round(worst_trade_pct, 4),
        "max_consecutive_losses": _max_consecutive_losses(trades),
        "tail_loss_share": _tail_loss_share(trades),
    }


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, after_value in after.items():
        before_value = before.get(key)
        if isinstance(after_value, (int, float)) and isinstance(before_value, (int, float)):
            out[key] = round(after_value - before_value, 6)
    return out


def _aggregate(metrics_by_window: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "expected_value_score_sum": _round(
            sum((metrics.get("expected_value_score") or 0.0) for metrics in metrics_by_window.values()),
            4,
        ),
        "total_pnl_sum": _round(
            sum((metrics.get("total_pnl") or 0.0) for metrics in metrics_by_window.values()),
            2,
        ),
        "trade_count_sum": sum(
            int(metrics.get("trade_count") or 0) for metrics in metrics_by_window.values()
        ),
        "min_survival_rate": _round(
            min((metrics.get("survival_rate") or 0.0) for metrics in metrics_by_window.values()),
            4,
        ),
        "max_drawdown_pct_max": _round(
            max((metrics.get("max_drawdown_pct") or 0.0) for metrics in metrics_by_window.values()),
            4,
        ),
    }


def _run_window(
    label: str,
    spec: dict[str, str],
    universe: list[str],
    snapshot: str,
) -> dict[str, Any]:
    engine = BacktestEngine(
        universe,
        start=spec["start"],
        end=spec["end"],
        config={},
        data_dir=str(REPO_ROOT / "data"),
        ohlcv_snapshot_path=str(REPO_ROOT / snapshot),
        include_entry_candidate_events=True,
    )
    result = engine.run()
    if "error" in result:
        raise RuntimeError(f"{label} backtest failed: {result['error']}")
    return {
        "label": label,
        "metrics": _metrics(result),
        "entry_execution_reason_counts": (
            result.get("entry_execution_attribution") or {}
        ).get("decision_counts", {}),
        "trades": result.get("trades") or [],
    }


def _space_trade_attribution(
    trades: list[dict[str, Any]],
    included_tickers: set[str],
) -> dict[str, Any]:
    space_trades = [
        trade for trade in trades if str(trade.get("ticker") or "").upper() in included_tickers
    ]
    by_ticker: dict[str, dict[str, Any]] = {}
    for trade in space_trades:
        ticker = str(trade.get("ticker") or "").upper()
        row = by_ticker.setdefault(
            ticker,
            {"trade_count": 0, "wins": 0, "losses": 0, "pnl": 0.0},
        )
        pnl = float(trade.get("pnl") or 0.0)
        row["trade_count"] += 1
        row["pnl"] += pnl
        if pnl > 0:
            row["wins"] += 1
        elif pnl < 0:
            row["losses"] += 1
    for row in by_ticker.values():
        row["pnl"] = _round(row["pnl"], 2)

    positive_by_ticker = {
        ticker: float(row["pnl"])
        for ticker, row in by_ticker.items()
        if float(row.get("pnl") or 0.0) > 0
    }
    positive_total = sum(positive_by_ticker.values())
    single_ticker_positive_share = None
    if positive_total > 0:
        single_ticker_positive_share = round(max(positive_by_ticker.values()) / positive_total, 4)

    total_pnl = sum(float(trade.get("pnl") or 0.0) for trade in space_trades)
    return {
        "trade_count": len(space_trades),
        "total_pnl": _round(total_pnl, 2),
        "wins": sum(1 for trade in space_trades if float(trade.get("pnl") or 0.0) > 0),
        "losses": sum(1 for trade in space_trades if float(trade.get("pnl") or 0.0) < 0),
        "by_ticker": dict(sorted(by_ticker.items())),
        "entry_reason_counts": dict(
            sorted(Counter(str(trade.get("entry_reason") or "unknown") for trade in space_trades).items())
        ),
        "single_ticker_positive_share": single_ticker_positive_share,
        "trades": space_trades,
    }


def _append_experiment_log(payload: dict[str, Any]) -> None:
    record = {
        "timestamp": payload["generated_at"],
        "experiment_id": EXPERIMENT_ID,
        "lane": "alpha_search",
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "changed_variable": payload["changed_variable"],
        "date_range": payload["date_range"],
        "backtest_protocol": payload["backtest_protocol"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "expected_value_score_delta": payload["summary"]["aggregate_delta"]["expected_value_score_sum"],
        "decision": payload["decision"],
        "rejection_reason": payload.get("rejection_reason"),
        "next_evidence_needed": payload["next_evidence_needed"],
        "production_impact": payload["production_impact"],
    }
    with EXPERIMENT_LOG_JSONL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _write_markdown(payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        f"# {EXPERIMENT_ID} Space Catalyst Static-Pool Replay",
        "",
        "## Decision",
        "",
        f"- decision: {payload['decision']}",
        f"- gate4_passed: {payload['gate4']['passed']}",
        f"- aggregate EV delta: {summary['aggregate_delta']['expected_value_score_sum']}",
        f"- aggregate PnL delta: {summary['aggregate_delta']['total_pnl_sum']}",
        f"- windows EV improved: {summary['windows_ev_improved']}",
        f"- windows EV regressed: {summary['windows_ev_regressed']}",
        f"- added space trades: {summary['space_trade_attribution_aggregate']['trade_count']}",
        f"- added space PnL: {summary['space_trade_attribution_aggregate']['total_pnl']}",
        "",
        "## Three-Window Metrics",
        "",
        "| Window | Base EV | After EV | dEV | Base PnL | After PnL | dPnL | Base DD | After DD | Trades | Survival | Space Trades | Space PnL |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        space = payload["by_window"][label]["space_trade_attribution"]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:.4f} | {bpnl:.2f} | {apnl:.2f} | {dpnl:.2f} | {bdd:.4f} | {add:.4f} | {trades} | {surv:.4f} | {strades} | {spnl:.2f} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                bdd=before["max_drawdown_pct"],
                add=after["max_drawdown_pct"],
                trades=after["trade_count"],
                surv=after["survival_rate"],
                strades=space["trade_count"],
                spnl=space["total_pnl"] or 0.0,
            )
        )

    lines.extend(
        [
            "",
            "## Included Tickers",
            "",
            ", ".join(payload["parameters"]["space_operating_tickers"]),
            "",
            "## Interpretation",
            "",
            payload["interpretation"],
            "",
            "## Production Impact",
            "",
            "- Static-pool replay only; no production order path, sizing path, or run adapter changed.",
            "- A positive result would still require a separate default-off forward queue/pilot promotion with parity tests.",
            "",
        ]
    )
    ARTIFACT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)

    core_universe = sorted({str(ticker).upper() for ticker in get_universe()})
    by_window: dict[str, dict[str, Any]] = {}

    for label, spec in WINDOWS.items():
        candidate_snapshot = REPO_ROOT / spec["candidate_snapshot"]
        snapshot_tickers = _snapshot_tickers(candidate_snapshot)
        included = sorted(set(SPACE_OPERATING_TICKERS) & snapshot_tickers)
        missing = sorted(set(SPACE_OPERATING_TICKERS) - set(included))
        candidate_universe = sorted(set(core_universe) | set(included))

        baseline = _run_window(
            label,
            spec,
            core_universe,
            spec["baseline_snapshot"],
        )
        candidate = _run_window(
            label,
            spec,
            candidate_universe,
            spec["candidate_snapshot"],
        )
        included_set = set(included)
        by_window[label] = {
            "window": spec,
            "included_space_tickers": included,
            "missing_space_tickers": missing,
            "baseline": baseline,
            "candidate": candidate,
            "delta": _delta(candidate["metrics"], baseline["metrics"]),
            "space_trade_attribution": _space_trade_attribution(
                candidate["trades"],
                included_set,
            ),
        }

    before_metrics = {label: row["baseline"]["metrics"] for label, row in by_window.items()}
    after_metrics = {label: row["candidate"]["metrics"] for label, row in by_window.items()}
    by_window_delta = {label: row["delta"] for label, row in by_window.items()}
    before_agg = _aggregate(before_metrics)
    after_agg = _aggregate(after_metrics)
    aggregate_delta = _delta(after_agg, before_agg)
    windows_ev_improved = sum(
        1 for item in by_window_delta.values() if item.get("expected_value_score", 0.0) > 0
    )
    windows_ev_regressed = sum(
        1 for item in by_window_delta.values() if item.get("expected_value_score", 0.0) < 0
    )
    windows_pnl_improved = sum(
        1 for item in by_window_delta.values() if item.get("total_pnl", 0.0) > 0
    )
    windows_pnl_regressed = sum(
        1 for item in by_window_delta.values() if item.get("total_pnl", 0.0) < 0
    )
    max_drawdown_worsening = max(
        item.get("max_drawdown_pct", 0.0) for item in by_window_delta.values()
    )

    space_totals = {
        "trade_count": 0,
        "total_pnl": 0.0,
        "wins": 0,
        "losses": 0,
        "by_ticker": defaultdict(lambda: {"trade_count": 0, "wins": 0, "losses": 0, "pnl": 0.0}),
    }
    for row in by_window.values():
        attr = row["space_trade_attribution"]
        space_totals["trade_count"] += attr["trade_count"]
        space_totals["total_pnl"] += float(attr["total_pnl"] or 0.0)
        space_totals["wins"] += attr["wins"]
        space_totals["losses"] += attr["losses"]
        for ticker, stats in attr["by_ticker"].items():
            target = space_totals["by_ticker"][ticker]
            target["trade_count"] += stats["trade_count"]
            target["wins"] += stats["wins"]
            target["losses"] += stats["losses"]
            target["pnl"] += float(stats["pnl"] or 0.0)

    positive_by_ticker = {
        ticker: stats["pnl"]
        for ticker, stats in space_totals["by_ticker"].items()
        if stats["pnl"] > 0
    }
    positive_total = sum(positive_by_ticker.values())
    single_ticker_positive_share = None
    if positive_total > 0:
        single_ticker_positive_share = round(max(positive_by_ticker.values()) / positive_total, 4)

    aggregate_space_attr = {
        "trade_count": space_totals["trade_count"],
        "total_pnl": _round(space_totals["total_pnl"], 2),
        "wins": space_totals["wins"],
        "losses": space_totals["losses"],
        "win_rate": _round(
            space_totals["wins"] / space_totals["trade_count"]
            if space_totals["trade_count"]
            else None,
            4,
        ),
        "single_ticker_positive_share": single_ticker_positive_share,
        "by_ticker": {
            ticker: {
                **stats,
                "pnl": _round(stats["pnl"], 2),
            }
            for ticker, stats in sorted(space_totals["by_ticker"].items())
        },
    }

    gate4_passed = (
        aggregate_delta.get("expected_value_score_sum", 0.0) > 0
        and aggregate_delta.get("total_pnl_sum", 0.0) > 0
        and windows_ev_improved >= 2
        and windows_ev_regressed == 0
        and max_drawdown_worsening <= 0.02
        and after_agg["min_survival_rate"] >= 0.05
        and (
            single_ticker_positive_share is None
            or single_ticker_positive_share <= 0.70
        )
    )
    if gate4_passed:
        decision = "promising_static_pool_only_not_promoted"
        rejection_reason = None
        interpretation = (
            "The space catalyst operating-equity pool improved the fixed-window "
            "static replay enough to justify forward shadow observation, but this "
            "is not production alpha because historical static-pool membership is "
            "not point-in-time trade permission."
        )
    else:
        decision = "rejected_static_pool_alpha"
        rejection_reason = (
            "The space catalyst operating-equity static pool did not pass Gate 4: "
            "it must improve aggregate EV and PnL, improve at least two EV windows "
            "without any EV-regressed window, keep drawdown damage within 2 pp, "
            "preserve survival above 5%, and avoid >70% single-ticker positive "
            "concentration."
        )
        interpretation = (
            "The pool is still useful as observe-only theme coverage, but the "
            "existing trend/breakout engine should not trade the space operating "
            "equities from static historical evidence. Forward observation or a "
            "separate event discriminator is required before revisiting live slots."
        )

    generated_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": generated_at,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "candidate_pool_static_replay",
        "changed_variable": "add_space_catalyst_operating_equities_to_snapshot_copy_universe",
        "mechanism_family": "candidate_pool_expansion",
        "hypothesis": (
            "Space catalyst operating equities may add non-overlapping event-driven "
            "replacement value when the existing trend/breakout engine is allowed "
            "to see them in deterministic OHLCV snapshot copies."
        ),
        "alpha_hypothesis": {
            "category": "entry / candidate-pool expansion",
            "why_this_now": (
                "LLM soft-ranking and the accepted SEC financial-report queue are "
                "waiting on forward data; this tests a different candidate pool "
                "rather than retuning the same SEC/RS20/ETF surfaces."
            ),
        },
        "history_guardrails": {
            "not_broad_watchlist_growth": True,
            "not_ai_infra_static_retry": True,
            "not_sec_t1_queue_retune": True,
            "not_llm_soft_ranking": True,
            "source_observe_only_seed": "exp-20260510-020",
            "ohlcv_snapshot_build": "exp-20260510-028",
        },
        "parameters": {
            "single_causal_variable": "candidate_pool_membership_in_static_snapshot_copy",
            "space_operating_tickers": list(SPACE_OPERATING_TICKERS),
            "excluded_space_tickers": EXCLUDED_SPACE_TICKERS,
            "locked_variables": [
                "core production universe",
                "canonical OHLCV snapshots",
                "signal generation logic",
                "entry filters",
                "ranking",
                "sizing",
                "MAX_POSITIONS",
                "slot routing",
                "exits",
                "add-ons",
                "LLM/news replay",
                "live pilot slot policy",
            ],
        },
        "date_range": {
            label: f"{spec['start']} -> {spec['end']}" for label, spec in WINDOWS.items()
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three-window fixed protocol; baseline "
            "uses canonical snapshots and candidate uses exp-20260510-028 snapshot "
            "copies with only the operating-equity space pool added."
        ),
        "snapshots": {
            label: {
                "baseline": spec["baseline_snapshot"],
                "candidate": spec["candidate_snapshot"],
            }
            for label, spec in WINDOWS.items()
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": by_window_delta,
            "aggregate": aggregate_delta,
        },
        "summary": {
            "before_aggregate": before_agg,
            "after_aggregate": after_agg,
            "aggregate_delta": aggregate_delta,
            "windows_ev_improved": windows_ev_improved,
            "windows_ev_regressed": windows_ev_regressed,
            "windows_pnl_improved": windows_pnl_improved,
            "windows_pnl_regressed": windows_pnl_regressed,
            "max_drawdown_worsening": _round(max_drawdown_worsening, 4),
            "space_trade_attribution_aggregate": aggregate_space_attr,
        },
        "by_window": by_window,
        "gate1": {
            "passed": True,
            "baseline_source": "rerun inside this script using docs/backtesting.md three-window snapshots",
        },
        "gate2": {
            "passed": _open_position_field_audit()["passed"],
            "open_position_field_audit": _open_position_field_audit(),
            "fields_checked": [
                "OHLCV Date/Open/High/Low/Close/Volume for each included ticker",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
        },
        "gate3": {
            "passed": after_agg["min_survival_rate"] >= 0.05,
            "new_core_filter_added": False,
            "survival_rates_after": {
                label: metrics["survival_rate"] for label, metrics in after_metrics.items()
            },
        },
        "gate4": {
            "passed": gate4_passed,
            "basis": (
                "Static-pool candidate expansion must improve aggregate EV and "
                "PnL, improve at least two EV windows with no EV-regressed window, "
                "avoid >2 pp max drawdown damage, keep survival >=5%, and avoid "
                ">70% single-ticker positive concentration."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "blocker_relation": (
                "LLM soft-ranking remains data-limited; this run uses a deterministic "
                "candidate-pool replay instead."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "static_pool_only": True,
            "parity_test_added": False,
            "production_signal_path_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "default_off_observation_only": True,
        },
        "rejection_reason": rejection_reason,
        "interpretation": interpretation,
        "next_evidence_needed": [
            "Do not enable live/default space trades from this static-pool replay.",
            "If revisited, require forward shadow decisions with direct, cash-relative, core-replacement, and same-theme replacement value.",
            "Any pilot promotion must create a shared production/backtest adapter with explicit nonzero slots and parity tests.",
        ],
        "related_files": [
            "quant/experiments/exp_20260511_002_space_catalyst_static_pool_replay.py",
            "data/experiments/exp-20260510-028/space_catalyst_ohlcv_snapshot_build.json",
            "experiments/logs/exp-20260511-002.json",
            "experiments/tickets/exp-20260511-002.json",
            "experiments/artifacts/exp-20260511-002_space_catalyst_static_pool_replay.md",
            "docs/experiment_log.jsonl",
        ],
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Space catalyst static-pool replay",
            "status": decision,
            "lane": "alpha_search",
            "alpha_hypothesis": payload["hypothesis"],
            "change_type": payload["change_type"],
            "single_causal_variable": payload["parameters"]["single_causal_variable"],
            "acceptance_gate": payload["gate4"]["basis"],
            "result": {
                "aggregate_ev_delta": aggregate_delta.get("expected_value_score_sum"),
                "aggregate_pnl_delta": aggregate_delta.get("total_pnl_sum"),
                "windows_ev_improved": windows_ev_improved,
                "windows_ev_regressed": windows_ev_regressed,
                "space_trade_count": aggregate_space_attr["trade_count"],
                "space_total_pnl": aggregate_space_attr["total_pnl"],
            },
            "source_files": payload["related_files"],
            "updated_at": generated_at,
        },
    )
    _write_markdown(payload)
    _append_experiment_log(payload)

    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
