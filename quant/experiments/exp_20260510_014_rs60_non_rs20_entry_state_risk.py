"""exp-20260510-014: RS60 non-RS20 entry-state risk replay.

Alpha search, replay-only. This tests whether already-entered A/B trades with
medium-term ticker-vs-SPY leadership, but without the accepted RS20 top-up,
deserve the same modest cap-aware 1.10x post-sizing top-up.

The point is to test a medium-term relative-strength allocation surface without
retesting the accepted RS20 scalar. Entries, filters, ranking, exits, add-ons,
LLM/news, event sleeves, and universe membership stay locked.
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
EXPERIMENT_DIR = Path(__file__).resolve().parent
for path in (QUANT_DIR, EXPERIMENT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260507_033_far_earnings_entry_state_risk as base  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260510-014"
STEM = "rs60_non_rs20_entry_state_risk"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

RS60_PERIOD = 60
RS60_REL_THRESHOLD = 0.0
RS60_TOPUP_MULTIPLIER = 1.10
RS20_MULTIPLIER_KEY = "rs20_entry_state_risk_multiplier_applied"

WINDOWS = base.WINDOWS


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(out) or math.isinf(out):
        return None
    return round(out, digits)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload_line = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if not path.exists():
        path.write_text(payload_line + "\n", encoding="utf-8")
        return

    out: list[str] = []
    replaced = False
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            out.append(line)
            continue
        if row.get("experiment_id") == payload["experiment_id"]:
            if not replaced:
                out.append(payload_line)
                replaced = True
            continue
        out.append(line)
    if not replaced:
        out.append(payload_line)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def _risk_distribution(trades: list[dict[str, Any]]) -> dict[str, Any]:
    closed = [trade for trade in trades if trade.get("entry_date") and trade.get("exit_date")]
    pnl_pct_series = [
        trade.get("pnl_pct_net")
        for trade in closed
        if trade.get("pnl_pct_net") is not None
    ]
    worst_trade_pct = round(min(pnl_pct_series), 6) if pnl_pct_series else None

    max_consecutive_losses = 0
    current_loss_streak = 0
    for trade in closed:
        pnl_pct = trade.get("pnl_pct_net")
        if pnl_pct is not None and pnl_pct < 0:
            current_loss_streak += 1
            max_consecutive_losses = max(max_consecutive_losses, current_loss_streak)
        else:
            current_loss_streak = 0

    losses_abs = sorted(
        [
            -float(trade["pnl"])
            for trade in closed
            if trade.get("pnl") is not None and float(trade["pnl"]) < 0
        ],
        reverse=True,
    )
    total_loss_abs = sum(losses_abs)
    tail_loss_share = None
    if total_loss_abs > 0:
        tail_count = max(1, math.ceil(len(losses_abs) * 0.2))
        tail_loss_share = round(sum(losses_abs[:tail_count]) / total_loss_abs, 4)

    return {
        "worst_trade_pct": worst_trade_pct,
        "max_consecutive_losses": max_consecutive_losses,
        "tail_loss_share": tail_loss_share,
    }


def _official_metrics(result: dict[str, Any]) -> dict[str, Any]:
    metrics = base._window_metrics(result)
    metrics.update(
        {
            "worst_trade_pct": _round(result.get("worst_trade_pct"), 6),
            "max_consecutive_losses": result.get("max_consecutive_losses"),
            "tail_loss_share": _round(result.get("tail_loss_share"), 4),
        }
    )
    return metrics


def _proxy_metrics(
    trades: list[dict[str, Any]],
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    spy_rows: list[dict[str, Any]],
    spec: dict[str, Any],
    signal_metrics: dict[str, Any],
) -> dict[str, Any]:
    metrics = base._daily_equity_metrics(
        trades,
        rows_by_ticker,
        spy_rows,
        spec["start"],
        spec["end"],
    )
    metrics.update(_risk_distribution(trades))
    for key in ("signals_generated", "signals_survived", "survival_rate"):
        metrics[key] = signal_metrics.get(key)
    return metrics


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, before_value in before.items():
        after_value = after.get(key)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            if key in {
                "trade_count",
                "signals_generated",
                "signals_survived",
                "max_consecutive_losses",
            }:
                out[key] = int(after_value - before_value)
            else:
                out[key] = _round(after_value - before_value, 6)
    return out


def _run_backtest(spec: dict[str, Any]) -> dict[str, Any]:
    result = BacktestEngine(
        sorted(get_universe()),
        start=spec["start"],
        end=spec["end"],
        config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
        replay_llm=False,
        replay_news=False,
        ohlcv_snapshot_path=str(REPO_ROOT / spec["snapshot"]),
    ).run()
    if "error" in result:
        raise RuntimeError(str(result["error"]))
    return result


def _signal_date_index(rows: list[dict[str, Any]], entry_date: str | None) -> int | None:
    entry_idx = base._idx_for_date(rows, entry_date)
    if entry_idx is None or entry_idx <= 0:
        return None
    return entry_idx - 1


def _period_return(rows: list[dict[str, Any]], end_idx: int, period: int) -> float | None:
    if end_idx < period:
        return None
    start_close = base._float(rows[end_idx - period].get("Close"))
    end_close = base._float(rows[end_idx].get("Close"))
    if not start_close or end_close is None:
        return None
    return (end_close / start_close) - 1.0


def _rs60_state(
    trade: dict[str, Any],
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    spy_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    ticker = str(trade.get("ticker") or "").upper()
    ticker_rows = rows_by_ticker.get(ticker) or []
    signal_idx = _signal_date_index(ticker_rows, str(trade.get("entry_date") or "")[:10])
    if signal_idx is None:
        return {"eligible": False, "reason": "missing_signal_date"}

    signal_date = str(ticker_rows[signal_idx].get("Date"))[:10]
    spy_idx = base._idx_for_date(spy_rows, signal_date)
    if spy_idx is None:
        return {"eligible": False, "reason": "missing_spy_signal_date"}

    ticker_ret60 = _period_return(ticker_rows, signal_idx, RS60_PERIOD)
    spy_ret60 = _period_return(spy_rows, spy_idx, RS60_PERIOD)
    if ticker_ret60 is None or spy_ret60 is None:
        return {
            "eligible": False,
            "reason": "missing_rs60_history",
            "signal_date": signal_date,
        }

    rel_ret60 = ticker_ret60 - spy_ret60
    sizing = trade.get("sizing_multipliers") or {}
    rs20_already_boosted = (
        isinstance(sizing.get(RS20_MULTIPLIER_KEY), (int, float))
        and sizing.get(RS20_MULTIPLIER_KEY) > 1.0
    )
    eligible = (
        trade.get("strategy") in {"trend_long", "breakout_long"}
        and rel_ret60 > RS60_REL_THRESHOLD
        and not rs20_already_boosted
    )
    return {
        "eligible": eligible,
        "signal_date": signal_date,
        "ticker_ret60": _round(ticker_ret60, 6),
        "spy_ret60": _round(spy_ret60, 6),
        "ticker_ret60_minus_spy": _round(rel_ret60, 6),
        "rs20_already_boosted": rs20_already_boosted,
        "reason": (
            "rs60_non_rs20_leader"
            if eligible
            else (
                "already_rs20_boosted"
                if rs20_already_boosted
                else "not_rs60_leader"
            )
        ),
    }


def _resize_trade(
    trade: dict[str, Any],
    *,
    new_shares: int,
    cap_pct: float,
    cap_source: str,
    entry_equity: float,
    rs_state: dict[str, Any],
) -> dict[str, Any]:
    old_shares = int(trade.get("shares") or 0)
    old_pnl = base._float(trade.get("pnl")) or 0.0
    pnl_per_share = old_pnl / old_shares if old_shares else 0.0
    out = dict(trade)
    out.update(
        {
            "shares": int(new_shares),
            "pnl": _round(pnl_per_share * new_shares, 2),
            "entry_state_risk_replay": {
                "reason": "rs60_non_rs20_entry_state_risk_multiplier",
                "baseline_shares": old_shares,
                "replay_shares": int(new_shares),
                "shares_delta": int(new_shares - old_shares),
                "position_cap_pct": cap_pct,
                "position_cap_source": cap_source,
                "entry_proxy_equity": _round(entry_equity, 2),
                "signal_date": rs_state.get("signal_date"),
                "ticker_ret60_minus_spy": rs_state.get("ticker_ret60_minus_spy"),
                "ticker_ret60": rs_state.get("ticker_ret60"),
                "spy_ret60": rs_state.get("spy_ret60"),
            },
        }
    )
    return out


def _variant_trades(
    trades: list[dict[str, Any]],
    baseline_equity: OrderedDict[str, float],
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    spy_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    out: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    pnl_delta_by_ticker: defaultdict[str, float] = defaultdict(float)
    eligible_count = 0
    changed_count = 0

    for trade in trades:
        rs_state = _rs60_state(trade, rows_by_ticker, spy_rows)
        if not rs_state.get("eligible"):
            status_counts[rs_state.get("reason") or "ineligible"] += 1
            out.append(trade)
            continue

        eligible_count += 1
        old_shares = int(trade.get("shares") or 0)
        entry_price = base._float(trade.get("entry_price"))
        entry_date = str(trade.get("entry_date") or "")[:10]
        entry_equity = baseline_equity.get(entry_date)
        cap_pct, cap_source = base._position_cap_pct(trade)
        if old_shares <= 0 or entry_price is None or entry_equity is None:
            status = "missing_resize_inputs"
            status_counts[status] += 1
            out.append(trade)
            continue

        desired_shares = max(
            old_shares,
            int(math.floor(old_shares * RS60_TOPUP_MULTIPLIER)),
        )
        cap_shares = int(math.floor((entry_equity * cap_pct) / entry_price))
        replay_shares = min(desired_shares, cap_shares)
        if replay_shares <= old_shares:
            status = "cap_bound_no_headroom"
            status_counts[status] += 1
            out.append(trade)
            details.append(
                {
                    "ticker": trade.get("ticker"),
                    "strategy": trade.get("strategy"),
                    "entry_date": entry_date,
                    "signal_date": rs_state.get("signal_date"),
                    "baseline_shares": old_shares,
                    "desired_shares": desired_shares,
                    "cap_shares": cap_shares,
                    "status": status,
                    "pnl_delta": 0.0,
                    "ticker_ret60_minus_spy": rs_state.get("ticker_ret60_minus_spy"),
                }
            )
            continue

        replacement = _resize_trade(
            trade,
            new_shares=replay_shares,
            cap_pct=cap_pct,
            cap_source=cap_source,
            entry_equity=entry_equity,
            rs_state=rs_state,
        )
        old_pnl = base._float(trade.get("pnl")) or 0.0
        new_pnl = base._float(replacement.get("pnl")) or 0.0
        pnl_delta = new_pnl - old_pnl
        changed_count += 1
        status = "resized"
        status_counts[status] += 1
        pnl_delta_by_ticker[str(trade.get("ticker") or "").upper()] += pnl_delta
        out.append(replacement)
        details.append(
            {
                "ticker": trade.get("ticker"),
                "strategy": trade.get("strategy"),
                "entry_date": entry_date,
                "exit_date": trade.get("exit_date"),
                "exit_reason": trade.get("exit_reason"),
                "signal_date": rs_state.get("signal_date"),
                "baseline_shares": old_shares,
                "desired_shares": desired_shares,
                "cap_shares": cap_shares,
                "replay_shares": replay_shares,
                "status": status,
                "baseline_pnl": _round(old_pnl, 2),
                "variant_pnl": _round(new_pnl, 2),
                "pnl_delta": _round(pnl_delta, 2),
                "ticker_ret60_minus_spy": rs_state.get("ticker_ret60_minus_spy"),
                "ticker_ret60": rs_state.get("ticker_ret60"),
                "spy_ret60": rs_state.get("spy_ret60"),
            }
        )

    return out, {
        "eligible_treatment_trades": eligible_count,
        "changed_treatment_trades": changed_count,
        "status_counts": dict(sorted(status_counts.items())),
        "pnl_delta_by_ticker": {
            ticker: _round(value, 2)
            for ticker, value in sorted(pnl_delta_by_ticker.items())
        },
        "details": details,
    }


def _positive_share(pnl_delta_by_ticker: dict[str, float]) -> float | None:
    positives = [value for value in pnl_delta_by_ticker.values() if value > 0]
    total = sum(positives)
    if total <= 0:
        return None
    return max(positives) / total


def _run_window(label: str, spec: dict[str, Any]) -> dict[str, Any]:
    snapshot = base._load_json(REPO_ROOT / spec["snapshot"])
    rows_by_ticker = base._load_ohlcv(REPO_ROOT / spec["snapshot"])
    spy_rows = rows_by_ticker.get("SPY") or []
    result = _run_backtest(spec)
    trades = [dict(trade) for trade in (result.get("trades") or [])]
    official_before = _official_metrics(result)
    baseline_equity = base._daily_equity_series(
        trades,
        rows_by_ticker,
        spy_rows,
        spec["start"],
        spec["end"],
    )
    proxy_before = _proxy_metrics(
        trades,
        rows_by_ticker,
        spy_rows,
        spec,
        official_before,
    )
    variant_trades, meta = _variant_trades(
        trades,
        baseline_equity,
        rows_by_ticker,
        spy_rows,
    )
    proxy_after = _proxy_metrics(
        variant_trades,
        rows_by_ticker,
        spy_rows,
        spec,
        official_before,
    )
    return {
        "window": label,
        "window_spec": spec,
        "snapshot_tickers": len(snapshot.get("ohlcv") or {}),
        "official_before_metrics": official_before,
        "proxy_before_metrics": proxy_before,
        "proxy_after_metrics": proxy_after,
        "delta_vs_proxy_before": _delta(proxy_after, proxy_before),
        **meta,
    }


def _aggregate(by_window: dict[str, Any]) -> dict[str, Any]:
    before_ev = sum(
        (row["proxy_before_metrics"].get("expected_value_score") or 0.0)
        for row in by_window.values()
    )
    after_ev = sum(
        (row["proxy_after_metrics"].get("expected_value_score") or 0.0)
        for row in by_window.values()
    )
    before_pnl = sum(
        (row["proxy_before_metrics"].get("total_pnl") or 0.0)
        for row in by_window.values()
    )
    after_pnl = sum(
        (row["proxy_after_metrics"].get("total_pnl") or 0.0)
        for row in by_window.values()
    )
    improved = 0
    regressed = 0
    max_dd_worsening = 0.0
    status_counts: Counter[str] = Counter()
    pnl_delta_by_ticker: defaultdict[str, float] = defaultdict(float)
    for row in by_window.values():
        ev_delta = row["delta_vs_proxy_before"].get("expected_value_score") or 0.0
        if ev_delta > 0:
            improved += 1
        elif ev_delta < 0:
            regressed += 1
        max_dd_worsening = max(
            max_dd_worsening,
            row["delta_vs_proxy_before"].get("max_drawdown_pct") or 0.0,
        )
        status_counts.update(row.get("status_counts") or {})
        for ticker, value in (row.get("pnl_delta_by_ticker") or {}).items():
            pnl_delta_by_ticker[ticker] += float(value or 0.0)

    ev_delta = after_ev - before_ev
    pnl_delta = after_pnl - before_pnl
    positive_share = _positive_share(dict(pnl_delta_by_ticker))
    return {
        "baseline_proxy_expected_value_score_sum": _round(before_ev, 4),
        "after_proxy_expected_value_score_sum": _round(after_ev, 4),
        "expected_value_score_delta_sum": _round(ev_delta, 4),
        "expected_value_score_delta_pct": _round(ev_delta / abs(before_ev) if before_ev else None, 6),
        "baseline_proxy_total_pnl_sum": _round(before_pnl, 2),
        "after_proxy_total_pnl_sum": _round(after_pnl, 2),
        "total_pnl_delta_sum": _round(pnl_delta, 2),
        "total_pnl_delta_pct": _round(pnl_delta / before_pnl if before_pnl else None, 6),
        "windows_ev_improved": improved,
        "windows_ev_regressed": regressed,
        "max_drawdown_worsening_max": _round(max_dd_worsening, 4),
        "eligible_treatment_trades": sum(
            row.get("eligible_treatment_trades") or 0 for row in by_window.values()
        ),
        "changed_treatment_trades": sum(
            row.get("changed_treatment_trades") or 0 for row in by_window.values()
        ),
        "status_counts": dict(sorted(status_counts.items())),
        "max_single_ticker_positive_share": _round(positive_share, 4),
        "pnl_delta_by_ticker": {
            ticker: _round(value, 2)
            for ticker, value in sorted(pnl_delta_by_ticker.items())
        },
    }


def _gate4(aggregate: dict[str, Any]) -> dict[str, Any]:
    strong_passed = (
        (aggregate.get("expected_value_score_delta_pct") or 0.0) > 0.10
        and (aggregate.get("total_pnl_delta_pct") or 0.0) > 0.05
        and aggregate.get("windows_ev_improved") >= 2
        and aggregate.get("windows_ev_regressed") == 0
        and (aggregate.get("max_drawdown_worsening_max") or 0.0) <= 0.01
        and (aggregate.get("eligible_treatment_trades") or 0) >= 8
        and (aggregate.get("changed_treatment_trades") or 0) >= 3
        and (
            aggregate.get("max_single_ticker_positive_share") is None
            or aggregate.get("max_single_ticker_positive_share") <= 0.50
        )
    )
    directional_passed = (
        (aggregate.get("expected_value_score_delta_sum") or 0.0) > 0
        and (aggregate.get("total_pnl_delta_sum") or 0.0) > 0
        and aggregate.get("windows_ev_improved") == 3
        and aggregate.get("windows_ev_regressed") == 0
        and (aggregate.get("max_drawdown_worsening_max") or 0.0) <= 0.01
        and (aggregate.get("changed_treatment_trades") or 0) >= 3
    )
    return {
        "strong_passed": strong_passed,
        "directional_passed": directional_passed,
        "basis": (
            "Three fixed windows from docs/backtesting.md. Metrics use a replay "
            "proxy because no shared policy was changed."
        ),
    }


def _artifact(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} RS60 Non-RS20 Entry-State Risk",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Aggregate",
        "",
        "| EV before | EV after | EV delta | PnL delta | EV windows +/- | Eligible | Changed | DD drift | Single ticker share |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        "| {evb} | {eva} | {evd} | {pnld} | {up}/{down} | {eligible} | {changed} | {dd} | {share} |".format(
            evb=aggregate["baseline_proxy_expected_value_score_sum"],
            eva=aggregate["after_proxy_expected_value_score_sum"],
            evd=aggregate["expected_value_score_delta_sum"],
            pnld=aggregate["total_pnl_delta_sum"],
            up=aggregate["windows_ev_improved"],
            down=aggregate["windows_ev_regressed"],
            eligible=aggregate["eligible_treatment_trades"],
            changed=aggregate["changed_treatment_trades"],
            dd=aggregate["max_drawdown_worsening_max"],
            share=aggregate["max_single_ticker_positive_share"],
        ),
        "",
        "## Windows",
        "",
        "| Window | EV before | EV after | EV delta | PnL delta | Sharpe delta | DD delta | Changed |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, row in payload["windows"].items():
        delta = row["delta_vs_proxy_before"]
        lines.append(
            "| {label} | {evb} | {eva} | {evd} | {pnld} | {sharpe} | {dd} | {changed} |".format(
                label=label,
                evb=row["proxy_before_metrics"]["expected_value_score"],
                eva=row["proxy_after_metrics"]["expected_value_score"],
                evd=delta.get("expected_value_score"),
                pnld=delta.get("total_pnl"),
                sharpe=delta.get("sharpe_daily"),
                dd=delta.get("max_drawdown_pct"),
                changed=row.get("changed_treatment_trades"),
            )
        )
    lines.extend(
        [
            "",
            "## Production Impact",
            "",
            "Replay only. No shared policy, run adapter, backtester adapter, live/default orders, ranking, exits, add-ons, LLM/news, or universe behavior changed.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    run_at = datetime.now(timezone.utc).isoformat()
    windows: dict[str, Any] = OrderedDict(
        (label, _run_window(label, spec)) for label, spec in WINDOWS.items()
    )
    aggregate = _aggregate(windows)
    gate4 = _gate4(aggregate)
    if gate4["strong_passed"]:
        decision = "accepted_replay_only_not_promoted"
        rejection_reason = None
        rationale = (
            "Replay passed the strong three-window guard, but no production "
            "behavior changes were retained because a shared policy and parity "
            "tests are required before promotion."
        )
    elif gate4["directional_passed"]:
        decision = "promising_replay_only_not_promoted"
        rejection_reason = None
        rationale = (
            "Replay was directionally positive, but promotion is blocked until "
            "the rule is implemented as shared production/backtest policy and "
            "validated with the canonical CLI path."
        )
    else:
        decision = "rejected"
        rejection_reason = (
            "The RS60 non-RS20 top-up did not improve the three-window north-star "
            "metrics cleanly enough to justify shared policy work."
        )
        rationale = rejection_reason

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": run_at,
        "run_at": run_at,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "Already-entered A/B trades with positive 60-day ticker-vs-SPY "
            "relative return, excluding trades that already received the RS20 "
            "entry-state top-up, may deserve a modest cap-aware 1.10x post-sizing "
            "top-up because medium-term leadership can persist even when the "
            "20-day burst is absent."
        ),
        "change_type": "replay_only_capital_allocation",
        "changed_variable": "rs60_non_rs20_entry_state_topup",
        "component": "replay script only",
        "single_causal_variable": "rs60_non_rs20_leader_1_10x_cap_aware_topup",
        "backtest_protocol": "Three fixed windows from docs/backtesting.md using canonical snapshots.",
        "date_range": {
            label: {
                "start": spec["start"],
                "end": spec["end"],
                "snapshot": spec["snapshot"],
            }
            for label, spec in WINDOWS.items()
        },
        "parameters": {
            "rs60_period": RS60_PERIOD,
            "rs60_relative_threshold": RS60_REL_THRESHOLD,
            "topup_multiplier": RS60_TOPUP_MULTIPLIER,
            "exclude_existing_rs20_topup": True,
            "locked_variables": [
                "core universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "base sizing multipliers including accepted RS20",
                "exits",
                "add-ons",
                "event sleeves",
                "LLM/news replay",
            ],
        },
        "gate1_baseline": {
            "source": "Current accepted core stack rerun inside this script before replay.",
            "official_window_metrics": {
                label: row["official_before_metrics"] for label, row in windows.items()
            },
        },
        "gate2_field_audit": {
            "path": "operator_inputs/open_positions.json",
            "required_fields": ["entry_date", "target_price"],
            "result": "current production positions checked by prior exp-20260510-013 and unchanged for this replay; rule itself uses snapshot OHLCV and executed trade rows",
        },
        "gate3": {
            "new_filter_added": False,
            "note": "No entry filter or candidate filter was added; survival is unchanged.",
            "survival_rates": {
                label: row["proxy_after_metrics"].get("survival_rate")
                for label, row in windows.items()
            },
        },
        "gate4": gate4,
        "before_metrics": {
            "official": {
                label: row["official_before_metrics"] for label, row in windows.items()
            },
            "proxy": {
                label: row["proxy_before_metrics"] for label, row in windows.items()
            },
        },
        "after_metrics": {
            "proxy": {
                label: row["proxy_after_metrics"] for label, row in windows.items()
            }
        },
        "delta_metrics": {
            "aggregate": aggregate,
            "windows": {
                label: row["delta_vs_proxy_before"] for label, row in windows.items()
            },
        },
        "windows": windows,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": "LLM soft-ranking data is not needed for this deterministic medium-term relative-strength allocation test.",
        },
        "historical_experiment_check": {
            "exp-20260503-008": "Medium-term 60-day relative strength had better support than a short pullback overlay in rank diagnostics.",
            "exp-20260510-012": "Accepted RS20 1.10x shared top-up; this experiment explicitly excludes those already-boosted trades.",
            "exp-20260510-013": "RS20 fragility guard failed; this is not another RS20 scalar or guard.",
            "blocked_routes": "LLM soft-ranking and SEC filing shock remain data-limited; ETF/event/state surfaces are waiting on forward paper outcomes.",
        },
        "decision_rationale": rationale,
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "If rejected, do not retry RS60 non-RS20 top-up without forward "
            "evidence or a materially different medium-term leadership semantic."
        ),
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            str(Path(__file__).relative_to(REPO_ROOT)),
            str(EXPERIMENT_LOG.relative_to(REPO_ROOT)),
        ],
        "why_not_other_changes": {
            "LLM_soft_ranking": "Still sample-limited.",
            "SEC_filing_shock": "Still missing directional joined fields.",
            "ETF_overlay": "Already default-off and waiting on forward paper outcomes.",
            "RS20_scalars": "Nearby accepted RS20 scalar work is explicitly disallowed without new evidence.",
            "candidate_pool": "MRVL-only static expansion was just rejected; broad static expansion adds noise.",
        },
    }

    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": decision,
        "lane": "alpha_search",
        "changed_variable": payload["changed_variable"],
        "decision": decision,
        "expected_value_score_delta_sum": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta_sum": aggregate["total_pnl_delta_sum"],
        "artifact": str(ARTIFACT_MD.relative_to(REPO_ROOT)),
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(TICKET_JSON, ticket)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG, payload)
    print(json.dumps(ticket, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
