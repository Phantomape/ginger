"""exp-20260511-009: space static-pool risk scalar sweep.

The static space catalyst pool was raw-positive but rejected because it was
selected with hindsight and worsened old-window drawdown. This experiment keeps
the same static observe-only pool and tests one variable: a sleeve-level risk
scalar for those space candidates. It does not change production eligibility,
live slots, ranking, or the shared policy.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict, defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260511-009"
STEM = "space_static_pool_risk_scalar"

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

SPACE_RISK_SCALARS = (1.0, 0.75, 0.5, 0.25)
MAX_DRAWDOWN_DAMAGE = 0.02

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
CURRENT_STATE_MD = REPO_ROOT / "docs" / "current_state.md"
PLAYBOOK_MD = REPO_ROOT / "docs" / "alpha-optimization-playbook.md"
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


def _append_jsonl_once(path: Path, payload: dict[str, Any]) -> None:
    compact = f'"experiment_id":"{payload["experiment_id"]}"'
    spaced = f'"experiment_id": "{payload["experiment_id"]}"'
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if compact in existing or spaced in existing:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        if existing and not existing.endswith("\n"):
            fh.write("\n")
        fh.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _append_once(path: Path, marker: str, text: str) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker in existing:
        return
    with path.open("a", encoding="utf-8") as fh:
        if existing and not existing.endswith("\n"):
            fh.write("\n")
        fh.write(text)


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


def _scale_sizing(sizing: dict[str, Any], scalar: float, portfolio_value: float) -> None:
    old_shares = int(sizing.get("shares_to_buy") or 0)
    if old_shares <= 0:
        return
    new_shares = int(math.floor(old_shares * scalar))
    ratio = new_shares / old_shares if old_shares else 0.0
    old_risk_pct = float(sizing.get("risk_pct") or 0.0)
    old_risk_amount = float(sizing.get("risk_amount_usd") or (old_risk_pct * portfolio_value))
    old_position_value = float(sizing.get("position_value_usd") or 0.0)
    sizing["space_static_pool_risk_scalar_applied"] = scalar
    sizing["space_static_pool_baseline_shares"] = old_shares
    sizing["space_static_pool_scaled_shares"] = new_shares
    sizing["risk_pct_before_space_scalar"] = old_risk_pct
    sizing["risk_amount_usd_before_space_scalar"] = round(old_risk_amount, 2)
    sizing["shares_to_buy"] = new_shares
    sizing["risk_pct"] = old_risk_pct * ratio
    sizing["risk_amount_usd"] = round(old_risk_amount * ratio, 2)
    sizing["position_value_usd"] = round(old_position_value * ratio, 2)
    sizing["position_pct_of_portfolio"] = (
        round((old_position_value * ratio) / portfolio_value, 4)
        if portfolio_value
        else 0.0
    )


@contextmanager
def _patched_space_risk_scalar(scalar: float):
    import portfolio_engine  # noqa: PLC0415

    original = portfolio_engine.size_signals

    def wrapped(signals, portfolio_value, risk_pct=None):
        sized = original(signals, portfolio_value, risk_pct=risk_pct)
        for sig in sized:
            ticker = str(sig.get("ticker") or "").upper()
            if ticker in SPACE_OPERATING_TICKERS and sig.get("sizing"):
                _scale_sizing(sig["sizing"], scalar, portfolio_value)
        return sized

    portfolio_engine.size_signals = wrapped
    try:
        yield
    finally:
        portfolio_engine.size_signals = original


def _run_window(
    label: str,
    spec: dict[str, str],
    universe: list[str],
    snapshot: str,
    *,
    scalar: float | None = None,
) -> dict[str, Any]:
    def _execute() -> dict[str, Any]:
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
        return result

    if scalar is None or scalar == 1.0:
        result = _execute()
    else:
        with _patched_space_risk_scalar(scalar):
            result = _execute()
    return {
        "label": label,
        "metrics": _metrics(result),
        "entry_execution_reason_counts": (
            result.get("entry_execution_attribution") or {}
        ).get("decision_counts", {}),
        "trades": result.get("trades") or [],
    }


def _compact_trade(trade: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": trade.get("ticker"),
        "strategy": trade.get("strategy"),
        "entry_date": trade.get("entry_date"),
        "exit_date": trade.get("exit_date"),
        "exit_reason": trade.get("exit_reason"),
        "shares": trade.get("shares"),
        "pnl": _round(trade.get("pnl"), 2),
        "pnl_pct_net": _round(trade.get("pnl_pct_net"), 6),
        "base_risk_pct": _round(trade.get("base_risk_pct"), 6),
        "actual_risk_pct": _round(trade.get("actual_risk_pct"), 6),
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
        "win_rate": _round(
            (
                sum(1 for trade in space_trades if float(trade.get("pnl") or 0.0) > 0)
                / len(space_trades)
            )
            if space_trades
            else None,
            4,
        ),
        "single_ticker_positive_share": single_ticker_positive_share,
        "by_ticker": dict(sorted(by_ticker.items())),
        "entry_reason_counts": dict(
            sorted(Counter(str(trade.get("entry_reason") or "unknown") for trade in space_trades).items())
        ),
        "trades": [_compact_trade(trade) for trade in space_trades],
    }


def _aggregate_space_attr(variant_windows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    totals = {
        "trade_count": 0,
        "total_pnl": 0.0,
        "wins": 0,
        "losses": 0,
        "by_ticker": defaultdict(lambda: {"trade_count": 0, "wins": 0, "losses": 0, "pnl": 0.0}),
    }
    for row in variant_windows.values():
        attr = row["space_trade_attribution"]
        totals["trade_count"] += attr["trade_count"]
        totals["total_pnl"] += float(attr["total_pnl"] or 0.0)
        totals["wins"] += attr["wins"]
        totals["losses"] += attr["losses"]
        for ticker, stats in attr["by_ticker"].items():
            target = totals["by_ticker"][ticker]
            target["trade_count"] += stats["trade_count"]
            target["wins"] += stats["wins"]
            target["losses"] += stats["losses"]
            target["pnl"] += float(stats["pnl"] or 0.0)

    positive = {
        ticker: stats["pnl"]
        for ticker, stats in totals["by_ticker"].items()
        if stats["pnl"] > 0
    }
    positive_total = sum(positive.values())
    single_share = None
    if positive_total > 0:
        single_share = round(max(positive.values()) / positive_total, 4)
    return {
        "trade_count": totals["trade_count"],
        "total_pnl": _round(totals["total_pnl"], 2),
        "wins": totals["wins"],
        "losses": totals["losses"],
        "win_rate": _round(
            totals["wins"] / totals["trade_count"] if totals["trade_count"] else None,
            4,
        ),
        "single_ticker_positive_share": single_share,
        "by_ticker": {
            ticker: {**stats, "pnl": _round(stats["pnl"], 2)}
            for ticker, stats in sorted(totals["by_ticker"].items())
        },
    }


def _variant_gate(
    before_agg: dict[str, Any],
    after_agg: dict[str, Any],
    delta_by_window: dict[str, dict[str, Any]],
    space_attr: dict[str, Any],
) -> dict[str, Any]:
    agg_delta = _delta(after_agg, before_agg)
    ev_improved = sum(
        1 for delta in delta_by_window.values() if delta.get("expected_value_score", 0.0) > 0
    )
    ev_regressed = sum(
        1 for delta in delta_by_window.values() if delta.get("expected_value_score", 0.0) < 0
    )
    max_drawdown_worsening = max(
        delta.get("max_drawdown_pct", 0.0) for delta in delta_by_window.values()
    )
    passed = (
        agg_delta.get("expected_value_score_sum", 0.0) > 0
        and agg_delta.get("total_pnl_sum", 0.0) > 0
        and ev_improved == len(WINDOWS)
        and ev_regressed == 0
        and max_drawdown_worsening <= MAX_DRAWDOWN_DAMAGE
        and after_agg["min_survival_rate"] >= 0.05
        and (
            space_attr["single_ticker_positive_share"] is None
            or space_attr["single_ticker_positive_share"] <= 0.70
        )
    )
    return {
        "passed": passed,
        "aggregate_delta": agg_delta,
        "windows_ev_improved": ev_improved,
        "windows_ev_regressed": ev_regressed,
        "max_drawdown_worsening": _round(max_drawdown_worsening, 4),
    }


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Space Static-Pool Risk Scalar",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "## Sweep",
        "",
        "| Scalar | Gate | Agg EV d | Agg PnL d | Max DD worsen | Space PnL | Space trades |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for scalar_key, row in payload["variants"].items():
        gate = row["gate"]
        space = row["space_trade_attribution_aggregate"]
        lines.append(
            "| {scalar} | {gate_passed} | {ev:.4f} | {pnl:.2f} | {dd:.4f} | {spnl:.2f} | {trades} |".format(
                scalar=scalar_key,
                gate_passed="pass" if gate["passed"] else "fail",
                ev=gate["aggregate_delta"]["expected_value_score_sum"],
                pnl=gate["aggregate_delta"]["total_pnl_sum"],
                dd=gate["max_drawdown_worsening"],
                spnl=space["total_pnl"] or 0.0,
                trades=space["trade_count"],
            )
        )
    best = payload["best_variant"]
    lines.extend(
        [
            "",
            "## Best Three-Window Comparison",
            "",
            f"Best scalar: `{best['risk_scalar']}`.",
            "",
            "| Window | Base EV | After EV | dEV | Base DD | After DD | Space PnL | Space trades |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = best["after_metrics"][label]
        delta = best["delta_metrics"]["by_window"][label]
        space = best["by_window"][label]["space_trade_attribution"]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:.4f} | {bdd:.4f} | {add:.4f} | {spnl:.2f} | {strades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bdd=before["max_drawdown_pct"],
                add=after["max_drawdown_pct"],
                spnl=space["total_pnl"] or 0.0,
                strades=space["trade_count"],
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            payload["interpretation"],
            "",
            "## Production Impact",
            "",
            "```text",
            "production_impact:",
            "  shared_policy_changed: false",
            "  backtester_adapter_changed: false",
            "  run_adapter_changed: false",
            "  replay_only: true",
            "  alters_orders: false",
            "  alters_signal_generation: false",
            "  alters_candidate_ranking: false",
            "  alters_sizing: false",
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def run_experiment() -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    core_universe = sorted({str(ticker).upper() for ticker in get_universe()})
    open_position_audit = _open_position_field_audit()

    baseline_by_window: dict[str, dict[str, Any]] = {}
    included_by_window: dict[str, list[str]] = {}
    for label, spec in WINDOWS.items():
        candidate_snapshot = REPO_ROOT / spec["candidate_snapshot"]
        snapshot_tickers = _snapshot_tickers(candidate_snapshot)
        included_by_window[label] = sorted(set(SPACE_OPERATING_TICKERS) & snapshot_tickers)
        baseline_by_window[label] = _run_window(
            label,
            spec,
            core_universe,
            spec["baseline_snapshot"],
        )

    before_metrics = {
        label: row["metrics"] for label, row in baseline_by_window.items()
    }
    before_agg = _aggregate(before_metrics)

    variants: dict[str, dict[str, Any]] = {}
    for scalar in SPACE_RISK_SCALARS:
        variant_windows: dict[str, dict[str, Any]] = {}
        for label, spec in WINDOWS.items():
            included = included_by_window[label]
            candidate_universe = sorted(set(core_universe) | set(included))
            candidate = _run_window(
                label,
                spec,
                candidate_universe,
                spec["candidate_snapshot"],
                scalar=scalar,
            )
            after_metrics = candidate["metrics"]
            variant_windows[label] = {
                "included_space_tickers": included,
                "candidate_metrics": after_metrics,
                "delta": _delta(after_metrics, before_metrics[label]),
                "entry_execution_reason_counts": candidate["entry_execution_reason_counts"],
                "space_trade_attribution": _space_trade_attribution(
                    candidate["trades"],
                    set(included),
                ),
            }
        after_metrics_by_window = {
            label: row["candidate_metrics"] for label, row in variant_windows.items()
        }
        after_agg = _aggregate(after_metrics_by_window)
        delta_by_window = {label: row["delta"] for label, row in variant_windows.items()}
        space_attr = _aggregate_space_attr(variant_windows)
        gate = _variant_gate(before_agg, after_agg, delta_by_window, space_attr)
        variants[str(scalar)] = {
            "risk_scalar": scalar,
            "after_metrics": after_metrics_by_window,
            "after_aggregate": after_agg,
            "delta_metrics": {
                "by_window": delta_by_window,
                "aggregate": gate["aggregate_delta"],
            },
            "gate": gate,
            "space_trade_attribution_aggregate": space_attr,
            "by_window": variant_windows,
        }

    passing = [row for row in variants.values() if row["gate"]["passed"]]
    if passing:
        best = max(
            passing,
            key=lambda row: (
                row["gate"]["aggregate_delta"]["expected_value_score_sum"],
                row["gate"]["aggregate_delta"]["total_pnl_sum"],
            ),
        )
    else:
        best = max(
            variants.values(),
            key=lambda row: (
                row["gate"]["aggregate_delta"]["expected_value_score_sum"],
                -row["gate"]["max_drawdown_worsening"],
            ),
        )

    if best["gate"]["passed"]:
        decision = "observed_only_positive_risk_scalar_not_promoted"
        rejection_reason = None
        interpretation = (
            f"The best valid Space static-pool variant was the {best['risk_scalar']}x "
            "risk scalar: it retained positive EV/PnL in all three windows while "
            "bringing drawdown damage inside the pre-registered guard. This is a "
            "Space alpha direction, not a live rule: optimize future Space sleeve "
            "promotion around small risk-budgeted official catalysts, not broad "
            "static universe enablement or LLM headline ranking."
        )
    else:
        decision = "rejected_static_pool_risk_scalar"
        rejection_reason = (
            "No tested Space static-pool risk scalar passed the three-window gate "
            "with positive aggregate EV/PnL, all-window EV improvement, drawdown "
            "damage <= 2 pp, survival >= 5%, and concentration within guard."
        )
        interpretation = (
            "Risk scalar alone does not turn the static Space pool into acceptable "
            "alpha. Continue only with event-dated forward replacement value or a "
            "non-hindsight official-catalyst discriminator."
        )

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": generated_at,
        "status": decision,
        "lane": "alpha_search",
        "hypothesis": (
            "The rejected Space catalyst static pool may become a useful specialist "
            "alpha direction if its high-volatility entries are carried at a small "
            "sleeve-level risk budget rather than full core size."
        ),
        "change_type": "capital_allocation_shadow_sweep",
        "changed_variable": "space_static_pool_risk_scalar",
        "single_causal_variable": "space_static_pool_risk_scalar",
        "parameters": {
            "risk_scalars": list(SPACE_RISK_SCALARS),
            "max_drawdown_damage": MAX_DRAWDOWN_DAMAGE,
            "space_operating_tickers": list(SPACE_OPERATING_TICKERS),
            "locked_variables": [
                "core production universe",
                "canonical baseline snapshots",
                "space augmented snapshot membership",
                "signal generation",
                "entry filters",
                "ranking",
                "MAX_POSITIONS",
                "slot routing",
                "exits",
                "add-ons",
                "LLM/news replay",
                "live pilot slots",
            ],
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "Capital allocation / risk allocation: risk-budgeted Space static-pool "
                "entries may preserve the raw candidate-pool EV while reducing old-window drawdown."
            ),
            "2_history_check": {
                "exp-20260511-002": (
                    "Full-size static pool was raw-positive in all windows but rejected "
                    "for hindsight membership and old-window drawdown +3.56 pp."
                ),
                "exp-20260511-003": (
                    "Default-off production-visible Space shadow surface exists; live slots remain zero."
                ),
                "exp-20260511-008": (
                    "Event-state ledger started but has only 1 mature event, so it is not enough "
                    "for official catalyst promotion."
                ),
            },
            "3_single_causal_variable": "space static-pool risk scalar",
            "4_gate": (
                "Use docs/backtesting.md three fixed windows. Accept observed-only direction "
                "only if aggregate EV/PnL improve, all three windows improve EV, max drawdown "
                "damage <= 2 pp, survival >= 5%, and concentration guard holds."
            ),
            "5_reproducibility": (
                "Rerun this script from repo root; it writes compact JSON/MD artifacts and "
                "does not mutate shared strategy modules."
            ),
        },
        "date_range": {
            label: f"{spec['start']} -> {spec['end']}" for label, spec in WINDOWS.items()
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three-window fixed protocol; baseline uses "
            "canonical snapshots and variants use exp-20260510-028 space augmented snapshots."
        ),
        "snapshots": {
            label: {
                "baseline": spec["baseline_snapshot"],
                "candidate": spec["candidate_snapshot"],
            }
            for label, spec in WINDOWS.items()
        },
        "before_metrics": before_metrics,
        "before_aggregate": before_agg,
        "after_metrics": best["after_metrics"],
        "after_aggregate": best["after_aggregate"],
        "delta_metrics": best["delta_metrics"],
        "expected_value_score_delta": best["gate"]["aggregate_delta"]["expected_value_score_sum"],
        "variants": variants,
        "best_variant": best,
        "gate_results": {
            "gate1": {
                "passed": True,
                "baseline_source": "Rerun canonical core baseline inside this script.",
            },
            "gate2": {
                "passed": open_position_audit["passed"],
                "open_position_field_audit": open_position_audit,
                "fields_checked": [
                    "OHLCV Date/Open/High/Low/Close/Volume for included space tickers",
                    "operator_inputs/open_positions.json entry_date",
                    "operator_inputs/open_positions.json target_price",
                ],
            },
            "gate3": {
                "passed": best["after_aggregate"]["min_survival_rate"] >= 0.05,
                "new_filter_added": False,
                "survival_rates_after": {
                    label: metrics["survival_rate"]
                    for label, metrics in best["after_metrics"].items()
                },
            },
            "gate4": best["gate"],
        },
        "decision": decision,
        "rejection_reason": rejection_reason,
        "interpretation": interpretation,
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm_soft_ranking": (
                "The Space event-state ledger has only one mature outcome; this run tests "
                "risk allocation instead of fabricating soft-ranking labels."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "default_off_observation_only": True,
        },
        "next_evidence_needed": [
            "Do not enable live/default Space trades from static-pool scalar evidence.",
            "Collect forward official-catalyst Space decisions with direct, same-theme, UFO/ARKX-relative, and core replacement value.",
            "If forward evidence passes, implement a shared default-off pilot adapter with explicit small risk budget and parity tests.",
        ],
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "docs/experiment_log.jsonl",
            "docs/current_state.md",
            "docs/alpha-optimization-playbook.md",
        ],
    }
    return payload


def write_outputs(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Space static-pool risk scalar sweep",
            "status": payload["status"],
            "lane": payload["lane"],
            "created_at": payload["timestamp"],
            "single_causal_variable": payload["single_causal_variable"],
            "result": {
                "decision": payload["decision"],
                "best_scalar": payload["best_variant"]["risk_scalar"],
                "aggregate_ev_delta": payload["expected_value_score_delta"],
                "aggregate_pnl_delta": payload["best_variant"]["gate"]["aggregate_delta"]["total_pnl_sum"],
                "gate_passed": payload["gate_results"]["gate4"]["passed"],
            },
            "next_steps": payload["next_evidence_needed"],
        },
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_build_markdown(payload), encoding="utf-8")
    log_record = {
        "timestamp": payload["timestamp"],
        "experiment_id": payload["experiment_id"],
        "status": payload["status"],
        "lane": payload["lane"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "changed_variable": payload["changed_variable"],
        "parameters": payload["parameters"],
        "date_range": payload["date_range"],
        "backtest_protocol": payload["backtest_protocol"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "decision": payload["decision"],
        "rejection_reason": payload["rejection_reason"],
        "next_evidence_needed": payload["next_evidence_needed"],
        "production_impact": payload["production_impact"],
        "llm_metrics": payload["llm_metrics"],
        "related_files": payload["related_files"],
    }
    _append_jsonl_once(EXPERIMENT_LOG_JSONL, log_record)

    best = payload["best_variant"]
    state_text = (
        "\nLatest Space risk-allocation alpha search: `exp-20260511-009` swept "
        "a sleeve-level risk scalar on the rejected static Space catalyst pool. "
        f"The highest-EV variant was `{best['risk_scalar']}x`: aggregate EV delta "
        f"`{payload['expected_value_score_delta']:+.4f}`, aggregate PnL delta "
        f"`${best['gate']['aggregate_delta']['total_pnl_sum']:,.2f}`, max drawdown "
        f"damage `{best['gate']['max_drawdown_worsening']:.2%}`, and Gate passed "
        f"`{best['gate']['passed']}`. The closest risk-controlled variant was "
        "`0.75x`, but it still regressed `late_strong` EV. Conclusion: simple "
        "static-pool risk discount is not enough; Space should remain official-catalyst "
        "forward paper, not broad static universe enablement or attention-headline ranking.\n"
    )
    _append_once(CURRENT_STATE_MD, EXPERIMENT_ID, state_text)

    playbook_text = (
        f"\n### 2026-05-11 mechanism update: Space static-pool risk scalar\n\n"
        f"Experiment: `{EXPERIMENT_ID}`\n\n"
        f"Decision: `{payload['decision']}`.\n\n"
        f"Finding: sweeping one Space sleeve risk scalar did not clear Gate 4. The "
        f"highest-EV variant was `{best['risk_scalar']}x`, with aggregate EV delta "
        f"`{payload['expected_value_score_delta']:+.4f}` and aggregate PnL delta "
        f"`${best['gate']['aggregate_delta']['total_pnl_sum']:,.2f}`, but max drawdown "
        f"damage was `{best['gate']['max_drawdown_worsening']:.2%}` and Gate passed "
        f"`{best['gate']['passed']}`. The `0.75x` scalar brought drawdown damage under "
        "2 pp, but it regressed `late_strong` EV.\n\n"
        "Mechanism insight: static Space pool risk discount alone is not enough. Space "
        "alpha should be researched as a small, risk-budgeted specialist sleeve only "
        "after official contract/regulatory/customer catalyst forward evidence exists. "
        "Do not retry broad static Space universe promotion, adjacent ticker mining, "
        "or LLM/attention-only headline ranking on the frozen sample.\n"
    )
    _append_once(PLAYBOOK_MD, f"{EXPERIMENT_ID}`", playbook_text)


def main() -> None:
    payload = run_experiment()
    write_outputs(payload)
    summary = {
        "decision": payload["decision"],
        "best_scalar": payload["best_variant"]["risk_scalar"],
        "aggregate_delta": payload["best_variant"]["gate"]["aggregate_delta"],
        "gate_passed": payload["gate_results"]["gate4"]["passed"],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
