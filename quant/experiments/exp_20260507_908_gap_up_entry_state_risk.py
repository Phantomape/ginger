"""exp-20260507-908: gap-up entry-state risk replay.

Alpha search, replay-only. The accepted stack already cancels some extreme gap
cases, but the entry-state oracle still shows a sizeable group of accepted A/B
trades whose signal-day open gapped at least 3%. This experiment tests one
causal variable: whether those already-entered gap-up trades deserve less or
more cap-aware risk.

No signal generation, ranking, entry filter, exit, add-on, universe, LLM/news,
or production order path is changed. Any positive result would still require a
shared run.py/backtester.py risk policy plus parity tests before promotion.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = Path(__file__).resolve().parent
for path in (str(QUANT_DIR), str(EXPERIMENT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import exp_20260507_027_core_platform_cap_aware_risk_replay as base  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
from oracle_diagnostics import (  # noqa: E402
    _entry_row_index,
    _entry_state_candidate_events,
    _entry_timing_tags,
    _ticker_rows,
)


EXPERIMENT_ID = "exp-20260507-908"
STEM = "gap_up_entry_state_risk"
SOURCE_EXPERIMENTS = ("exp-20260507-032",)
TREATMENT_TAG = "gap_up_3pct"

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

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
                "state_note": "rotation-heavy bull where strategy profits but can lag indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)

VARIANTS = OrderedDict(
    [
        ("gap_up_0_50x", {"risk_multiplier": 0.50}),
        ("gap_up_0_75x", {"risk_multiplier": 0.75}),
        ("gap_up_1_25x_cap_aware", {"risk_multiplier": 1.25}),
        ("gap_up_1_50x_cap_aware", {"risk_multiplier": 1.50}),
    ]
)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _run_backtest(spec: dict[str, Any]) -> dict[str, Any]:
    engine = BacktestEngine(
        get_universe(),
        start=spec["start"],
        end=spec["end"],
        config={
            "REGIME_AWARE_EXIT": True,
            "REPLAY_PARTIAL_REDUCES": True,
        },
        ohlcv_snapshot_path=str(REPO_ROOT / spec["snapshot"]),
        include_entry_candidate_events=True,
    )
    result = engine.run()
    if result.get("error"):
        raise RuntimeError(str(result["error"]))
    return result


def _entry_state_rows(
    backtest_result: dict[str, Any],
    snapshot: dict[str, Any],
) -> list[dict[str, Any]]:
    rows_by_ticker = _ticker_rows(snapshot)
    spy_rows = rows_by_ticker.get("SPY")
    events = _entry_state_candidate_events(
        backtest_result,
        {"candidate_events": backtest_result.get("entry_candidate_events") or []},
    )

    out: list[dict[str, Any]] = []
    seen = set()
    for event in events:
        signal_date = event["signal_date"]
        ticker = event["ticker"]
        key = (
            signal_date,
            ticker,
            event.get("source"),
            event.get("candidate_rank"),
            event.get("decision"),
        )
        if key in seen:
            continue
        seen.add(key)

        rows = rows_by_ticker.get(ticker)
        if not rows:
            continue
        signal_idx = None
        for idx, row in enumerate(rows):
            if row.get("Date") == signal_date:
                signal_idx = idx
                break
        entry_idx = _entry_row_index(rows, signal_date, event.get("details"))
        if signal_idx is None or entry_idx is None:
            continue

        tags, metrics = _entry_timing_tags(rows, signal_idx, spy_rows, signal_date, {})
        out.append(
            {
                "signal_date": signal_date,
                "entry_date": rows[entry_idx].get("Date"),
                "ticker": ticker,
                "strategy": event.get("strategy"),
                "decision": event.get("decision") or "unknown",
                "candidate_rank": event.get("candidate_rank"),
                "tags": tags,
                "timing_metrics": metrics,
            }
        )
    return out


def _tag_lookup(rows: list[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
    out = {}
    for row in rows:
        if row.get("decision") != "entered":
            continue
        out[
            (
                str(row.get("entry_date") or "")[:10],
                str(row.get("ticker") or "").upper(),
                str(row.get("strategy") or ""),
            )
        ] = row
    return out


def _resize_trade(
    trade: dict[str, Any],
    *,
    new_shares: int,
    reason: str,
    cap_pct: float,
    cap_source: str,
    entry_equity: float,
    tags: list[str],
) -> dict[str, Any]:
    old_shares = int(trade.get("shares") or 0)
    old_pnl = base._float(trade.get("pnl")) or 0.0
    old_pnl_pct = base._float(trade.get("pnl_pct_net"))
    pnl_per_share = old_pnl / old_shares if old_shares else 0.0
    out = dict(trade)
    out.update(
        {
            "shares": int(new_shares),
            "pnl": base._round(pnl_per_share * new_shares, 2),
            "pnl_pct_net": base._round(old_pnl_pct, 6),
            "entry_state_risk_replay": {
                "reason": reason,
                "treatment_tag": TREATMENT_TAG,
                "tags": tags,
                "baseline_shares": old_shares,
                "replay_shares": int(new_shares),
                "shares_delta": int(new_shares - old_shares),
                "position_cap_pct": cap_pct,
                "position_cap_source": cap_source,
                "entry_proxy_equity": base._round(entry_equity, 2),
            },
        }
    )
    return out


def _variant_trades(
    trades: list[dict[str, Any]],
    baseline_equity: OrderedDict[str, float],
    tag_by_trade: dict[tuple[str, str, str], dict[str, Any]],
    *,
    risk_multiplier: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    out: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    pnl_delta_by_ticker: defaultdict[str, float] = defaultdict(float)
    touched = 0
    changed = 0
    tagged_entered = 0

    for trade in trades:
        ticker = str(trade.get("ticker") or "").upper()
        entry_date = str(trade.get("entry_date") or "")[:10]
        strategy = str(trade.get("strategy") or "")
        tag_row = tag_by_trade.get((entry_date, ticker, strategy))
        tags = list((tag_row or {}).get("tags") or [])
        if tag_row is not None:
            tagged_entered += 1
        if TREATMENT_TAG not in tags:
            out.append(trade)
            continue

        touched += 1
        old_shares = int(trade.get("shares") or 0)
        entry_price = base._float(trade.get("entry_price"))
        entry_equity = baseline_equity.get(entry_date)
        cap_pct, cap_source = base._position_cap_pct(trade)

        if old_shares <= 0 or entry_price is None or entry_equity is None:
            status_counts["missing_resize_inputs"] += 1
            out.append(trade)
            continue

        desired_shares = max(1, int(math.floor(old_shares * risk_multiplier)))
        if risk_multiplier >= 1.0:
            cap_shares = int(math.floor((entry_equity * cap_pct) / entry_price))
            replay_shares = min(desired_shares, cap_shares)
            if replay_shares <= old_shares:
                status = "cap_bound_no_headroom"
                status_counts[status] += 1
                out.append(trade)
                details.append(
                    {
                        "ticker": ticker,
                        "strategy": strategy,
                        "entry_date": entry_date,
                        "baseline_shares": old_shares,
                        "desired_shares": desired_shares,
                        "cap_shares": cap_shares,
                        "replay_shares": old_shares,
                        "status": status,
                        "baseline_pnl": base._round(trade.get("pnl"), 2),
                        "pnl_delta": 0.0,
                        "tags": tags,
                    }
                )
                continue
            status = "resized_up"
        else:
            replay_shares = desired_shares
            cap_shares = None
            if replay_shares >= old_shares:
                status_counts["rounding_no_change"] += 1
                out.append(trade)
                continue
            status = "resized_down"

        replacement = _resize_trade(
            trade,
            new_shares=replay_shares,
            reason="gap_up_3pct_entry_state_risk_multiplier",
            cap_pct=cap_pct,
            cap_source=cap_source,
            entry_equity=entry_equity,
            tags=tags,
        )
        old_pnl = base._float(trade.get("pnl")) or 0.0
        new_pnl = base._float(replacement.get("pnl")) or 0.0
        pnl_delta = new_pnl - old_pnl
        changed += 1
        status_counts[status] += 1
        pnl_delta_by_ticker[ticker] += pnl_delta
        out.append(replacement)
        details.append(
            {
                "ticker": ticker,
                "strategy": strategy,
                "entry_date": entry_date,
                "exit_date": trade.get("exit_date"),
                "exit_reason": trade.get("exit_reason"),
                "baseline_shares": old_shares,
                "desired_shares": desired_shares,
                "cap_shares": cap_shares,
                "replay_shares": replay_shares,
                "status": status,
                "baseline_pnl": base._round(old_pnl, 2),
                "variant_pnl": base._round(new_pnl, 2),
                "pnl_delta": base._round(pnl_delta, 2),
                "tags": tags,
                "cap_pct": cap_pct,
                "cap_source": cap_source,
                "entry_proxy_equity": base._round(entry_equity, 2),
            }
        )

    return out, {
        "entered_trades_with_entry_state_tags": tagged_entered,
        "touched_treatment_trades": touched,
        "changed_treatment_trades": changed,
        "status_counts": dict(sorted(status_counts.items())),
        "pnl_delta_by_ticker": {
            ticker: base._round(value, 2)
            for ticker, value in sorted(pnl_delta_by_ticker.items())
        },
        "details": details,
    }


def _replay_window(name: str, spec: dict[str, Any]) -> dict[str, Any]:
    snapshot = base._load_json(REPO_ROOT / spec["snapshot"])
    ohlcv = base._load_ohlcv(REPO_ROOT / spec["snapshot"])
    result = _run_backtest(spec)
    entry_rows = _entry_state_rows(result, snapshot)
    tag_by_trade = _tag_lookup(entry_rows)
    trades = [
        dict(trade)
        for trade in result.get("trades") or []
        if trade.get("entry_date") and trade.get("exit_date")
    ]
    spy_rows = ohlcv["SPY"]
    baseline_equity = base._daily_equity_series(
        trades,
        ohlcv,
        spy_rows,
        spec["start"],
        spec["end"],
    )
    proxy_before = base._daily_equity_metrics(
        trades,
        ohlcv,
        spy_rows,
        spec["start"],
        spec["end"],
    )

    tag_counts: dict[str, int] = {}
    entered_tag_counts: dict[str, int] = {}
    for row in entry_rows:
        for tag in row.get("tags") or []:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
            if row.get("decision") == "entered":
                entered_tag_counts[tag] = entered_tag_counts.get(tag, 0) + 1

    variant_results: dict[str, Any] = {}
    for variant_name, params in VARIANTS.items():
        variant_trades, meta = _variant_trades(
            trades,
            baseline_equity,
            tag_by_trade,
            risk_multiplier=float(params["risk_multiplier"]),
        )
        proxy_after = base._daily_equity_metrics(
            variant_trades,
            ohlcv,
            spy_rows,
            spec["start"],
            spec["end"],
        )
        ev_delta = None
        if (
            proxy_after.get("expected_value_score") is not None
            and proxy_before.get("expected_value_score") is not None
        ):
            ev_delta = (
                proxy_after["expected_value_score"]
                - proxy_before["expected_value_score"]
            )
        variant_results[variant_name] = {
            "metrics": proxy_after,
            "delta_vs_proxy_before": {
                "expected_value_score": base._round(ev_delta, 4),
                "total_pnl": base._round(
                    proxy_after["total_pnl"] - proxy_before["total_pnl"],
                    2,
                ),
                "sharpe_daily": base._round(
                    proxy_after["sharpe_daily"] - proxy_before["sharpe_daily"],
                    2,
                ),
                "max_drawdown_pct": base._round(
                    proxy_after["max_drawdown_pct"]
                    - proxy_before["max_drawdown_pct"],
                    4,
                ),
                "trade_count": proxy_after["trade_count"] - proxy_before["trade_count"],
            },
            **meta,
        }

    return {
        "window": name,
        "window_spec": spec,
        "official_baseline_metrics": base._window_metrics(result),
        "proxy_before_metrics": proxy_before,
        "baseline_trade_count": len(trades),
        "entry_state_candidate_count": len(entry_rows),
        "entry_state_tag_counts": dict(sorted(tag_counts.items())),
        "entered_entry_state_tag_counts": dict(sorted(entered_tag_counts.items())),
        "treatment_entered_trade_count": entered_tag_counts.get(TREATMENT_TAG, 0),
        "variant_results": variant_results,
    }


def _positive_share(pnl_delta_by_ticker: dict[str, float]) -> float | None:
    positives = [value for value in pnl_delta_by_ticker.values() if value > 0]
    total = sum(positives)
    if total <= 0:
        return None
    return max(positives) / total


def _aggregate(by_window: dict[str, Any]) -> dict[str, Any]:
    baseline_ev_sum = sum(
        (window.get("proxy_before_metrics") or {}).get("expected_value_score") or 0.0
        for window in by_window.values()
    )
    baseline_pnl_sum = sum(
        (window.get("proxy_before_metrics") or {}).get("total_pnl") or 0.0
        for window in by_window.values()
    )
    out: dict[str, Any] = {}
    for variant_name in VARIANTS:
        after_ev_sum = 0.0
        after_pnl_sum = 0.0
        touched_sum = 0
        changed_sum = 0
        improved = 0
        regressed = 0
        max_dd_worsening = 0.0
        by_window_delta: dict[str, Any] = {}
        status_counts: Counter[str] = Counter()
        pnl_delta_by_ticker: defaultdict[str, float] = defaultdict(float)
        for window_name, window in by_window.items():
            variant = window["variant_results"][variant_name]
            metrics = variant["metrics"]
            delta = variant["delta_vs_proxy_before"]
            after_ev_sum += metrics.get("expected_value_score") or 0.0
            after_pnl_sum += metrics.get("total_pnl") or 0.0
            touched_sum += variant.get("touched_treatment_trades") or 0
            changed_sum += variant.get("changed_treatment_trades") or 0
            ev_delta = delta.get("expected_value_score") or 0.0
            if ev_delta > 0:
                improved += 1
            elif ev_delta < 0:
                regressed += 1
            max_dd_worsening = max(
                max_dd_worsening,
                delta.get("max_drawdown_pct") or 0.0,
            )
            by_window_delta[window_name] = delta
            status_counts.update(variant.get("status_counts") or {})
            for ticker, value in (variant.get("pnl_delta_by_ticker") or {}).items():
                pnl_delta_by_ticker[ticker] += float(value or 0.0)

        ev_delta_sum = after_ev_sum - baseline_ev_sum
        pnl_delta_sum = after_pnl_sum - baseline_pnl_sum
        ev_delta_pct = ev_delta_sum / abs(baseline_ev_sum) if baseline_ev_sum else None
        pnl_delta_pct = pnl_delta_sum / baseline_pnl_sum if baseline_pnl_sum else None
        max_single_share = _positive_share(dict(pnl_delta_by_ticker))
        gate_passed = (
            ev_delta_pct is not None
            and ev_delta_pct > 0.10
            and pnl_delta_pct is not None
            and pnl_delta_pct > 0.05
            and improved >= 2
            and regressed == 0
            and max_dd_worsening <= 0.01
            and touched_sum >= 8
            and changed_sum >= 3
            and (max_single_share is None or max_single_share <= 0.50)
        )
        out[variant_name] = {
            "baseline_proxy_expected_value_score_sum": base._round(baseline_ev_sum, 4),
            "after_proxy_expected_value_score_sum": base._round(after_ev_sum, 4),
            "expected_value_score_delta_sum": base._round(ev_delta_sum, 4),
            "expected_value_score_delta_pct": base._round(ev_delta_pct, 6),
            "baseline_proxy_total_pnl_sum": base._round(baseline_pnl_sum, 2),
            "after_proxy_total_pnl_sum": base._round(after_pnl_sum, 2),
            "total_pnl_delta_sum": base._round(pnl_delta_sum, 2),
            "total_pnl_delta_pct": base._round(pnl_delta_pct, 6),
            "windows_ev_improved": improved,
            "windows_ev_regressed": regressed,
            "max_drawdown_worsening_max": base._round(max_dd_worsening, 4),
            "touched_treatment_trades": touched_sum,
            "changed_treatment_trades": changed_sum,
            "status_counts": dict(sorted(status_counts.items())),
            "max_single_ticker_positive_share": base._round(max_single_share, 4),
            "pnl_delta_by_ticker": {
                ticker: base._round(value, 2)
                for ticker, value in sorted(pnl_delta_by_ticker.items())
            },
            "by_window_delta": by_window_delta,
            "proxy_gate4_passed": gate_passed,
        }
    return out


def _choose_best(aggregate: dict[str, Any]) -> str:
    return max(
        aggregate,
        key=lambda name: (
            aggregate[name].get("expected_value_score_delta_sum") or -10**9,
            aggregate[name].get("total_pnl_delta_sum") or -10**9,
        ),
    )


def _official_baseline_sum(by_window: dict[str, Any]) -> dict[str, Any]:
    return {
        "expected_value_score_sum": base._round(
            sum(
                (window.get("official_baseline_metrics") or {}).get("expected_value_score")
                or 0.0
                for window in by_window.values()
            ),
            4,
        ),
        "total_pnl_sum": base._round(
            sum(
                (window.get("official_baseline_metrics") or {}).get("total_pnl") or 0.0
                for window in by_window.values()
            ),
            2,
        ),
        "trade_count_sum": sum(
            int((window.get("official_baseline_metrics") or {}).get("trade_count") or 0)
            for window in by_window.values()
        ),
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Gap-Up Entry-State Risk Replay",
        "",
        f"Decision: `{payload['decision']}`",
        f"Best variant: `{payload['best_variant']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Baseline",
        "",
        "| EV sum | PnL sum | Trades |",
        "|---:|---:|---:|",
        "| {ev} | {pnl} | {trades} |".format(
            ev=payload["official_baseline_metrics"]["expected_value_score_sum"],
            pnl=payload["official_baseline_metrics"]["total_pnl_sum"],
            trades=payload["official_baseline_metrics"]["trade_count_sum"],
        ),
        "",
        "## Aggregate Replay",
        "",
        "| Variant | EV delta | EV delta % | PnL delta | PnL delta % | Windows EV +/- | Touched | Changed | DD worsening | Single ticker share | Gate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for name, metrics in payload["aggregate"].items():
        lines.append(
            "| {name} | {ev} | {ev_pct} | {pnl} | {pnl_pct} | {up}/{down} | {touched} | {changed} | {dd} | {share} | {gate} |".format(
                name=name,
                ev=metrics["expected_value_score_delta_sum"],
                ev_pct=metrics["expected_value_score_delta_pct"],
                pnl=metrics["total_pnl_delta_sum"],
                pnl_pct=metrics["total_pnl_delta_pct"],
                up=metrics["windows_ev_improved"],
                down=metrics["windows_ev_regressed"],
                touched=metrics["touched_treatment_trades"],
                changed=metrics["changed_treatment_trades"],
                dd=metrics["max_drawdown_worsening_max"],
                share=metrics["max_single_ticker_positive_share"],
                gate="PASS" if metrics["proxy_gate4_passed"] else "FAIL",
            )
        )
    lines.extend(
        [
            "",
            "## Window Deltas",
            "",
            "| Variant | Window | EV delta | PnL delta | Sharpe delta | DD delta |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for name, metrics in payload["aggregate"].items():
        for window, delta in metrics["by_window_delta"].items():
            lines.append(
                "| {name} | {window} | {ev} | {pnl} | {sharpe} | {dd} |".format(
                    name=name,
                    window=window,
                    ev=delta["expected_value_score"],
                    pnl=delta["total_pnl"],
                    sharpe=delta["sharpe_daily"],
                    dd=delta["max_drawdown_pct"],
                )
            )
    if payload.get("rejection_reason"):
        lines.extend(["", "## Rejection Reason", "", payload["rejection_reason"]])
    lines.extend(
        [
            "",
            "## Production Impact",
            "",
            "Replay-only diagnostic. No production orders, shared policy, default backtest strategy, LLM/news boundary, or universe changed.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    by_window = OrderedDict(
        (name, _replay_window(name, spec)) for name, spec in WINDOWS.items()
    )
    aggregate = _aggregate(by_window)
    best_variant = _choose_best(aggregate)
    best = aggregate[best_variant]
    decision = "accepted_replay_only" if best["proxy_gate4_passed"] else "rejected"
    rejection_reason = None
    if decision == "rejected":
        rejection_reason = (
            f"Best variant `{best_variant}` failed Gate 4: EV delta "
            f"{best['expected_value_score_delta_sum']} "
            f"({best['expected_value_score_delta_pct']}), PnL delta "
            f"{best['total_pnl_delta_sum']} ({best['total_pnl_delta_pct']}), "
            f"windows improved/regressed {best['windows_ev_improved']}/"
            f"{best['windows_ev_regressed']}, changed trades "
            f"{best['changed_treatment_trades']} of {best['touched_treatment_trades']} "
            f"touched, max DD worsening {best['max_drawdown_worsening_max']}, "
            f"single ticker positive share {best['max_single_ticker_positive_share']}."
        )

    timestamp = datetime.now(timezone.utc).isoformat()
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "source_experiments": SOURCE_EXPERIMENTS,
        "hypothesis": (
            "Accepted A/B trades with a signal-day open gap of at least 3% may "
            "have a different payoff distribution than normal entries; a bounded "
            "risk multiplier could improve expected value without changing entries."
        ),
        "alpha_hypothesis_category": "capital_allocation",
        "change_type": "cap_aware_entry_state_risk_replay",
        "mechanism_family": "gap_up_entry_state_lifecycle_allocation",
        "single_causal_variable": "gap_up_3pct_entry_state_risk_multiplier",
        "date_range": {
            name: f"{spec['start']} -> {spec['end']}"
            for name, spec in WINDOWS.items()
        },
        "market_regime_summary": {
            name: spec["state_note"] for name, spec in WINDOWS.items()
        },
        "historical_experiment_check": {
            "nearby_rejected": {
                "exp-20260428-021": (
                    "Upside-gap entry cancellation was rejected; this does not "
                    "cancel entries and instead only resizes already-entered trades."
                ),
                "exp-20260428-022": (
                    "Upside-gap momentum exception did not justify a live entry rule; "
                    "this run stays replay-only and capital-allocation scoped."
                ),
                "exp-20260507-024": (
                    "Event SMA20/SMA50 price-structure tilt failed versus the full "
                    "event bundle; this is core A/B signal-day gap state, not event "
                    "source notional tuning."
                ),
                "exp-20260507-032": (
                    "Entry-state oracle was accepted only as diagnostic; this run "
                    "converts one sufficiently populated tag into a candidate-level replay."
                ),
            },
            "mechanism_insight_conflict": (
                "No conflict with LLM soft-ranking, C-sleeve, event-source pruning, "
                "runner exit, broad universe refresh, or platform RS20 concentration do-not-repeat zones."
            ),
            "why_not_simple_repeat": (
                "The treatment changes risk size only for existing entered trades "
                "tagged gap_up_3pct. It does not retest gap entry cancellation, "
                "entry timing, event-source pruning, or universe expansion."
            ),
        },
        "parameters": {
            "treatment_tag": TREATMENT_TAG,
            "variants": VARIANTS,
            "position_cap_policy": {
                "default_initial_cap": base.MAX_POSITION_PCT,
                "spy_relative_leader_cap": base.RISK_ON_SPY_RELATIVE_LEADER_MAX_POSITION_PCT,
                "entry_equity_source": "baseline proxy daily equity at entry date",
                "if_cap_has_no_headroom": "leave baseline shares unchanged",
                "haircut_floor": "minimum one share for already-entered treatment trades",
            },
            "locked_variables": [
                "core universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "exits",
                "add-ons",
                "event sleeves",
                "LLM/news replay",
                "earnings_event_long enablement",
            ],
            "gate4": {
                "expected_value_score_delta_pct": "> 10%",
                "total_pnl_delta_pct": "> 5%",
                "windows_ev_improved": ">= 2 of 3",
                "windows_ev_regressed": "0",
                "max_drawdown_worsening": "<= 1pp",
                "touched_treatment_trades": ">= 8",
                "changed_treatment_trades": ">= 3",
                "single_ticker_positive_contribution": "<= 50%",
            },
        },
        "official_baseline_metrics": _official_baseline_sum(by_window),
        "before_metrics": {
            name: window["official_baseline_metrics"]
            for name, window in by_window.items()
        },
        "proxy_before_metrics": {
            name: window["proxy_before_metrics"] for name, window in by_window.items()
        },
        "after_metrics": {
            variant: {
                name: by_window[name]["variant_results"][variant]["metrics"]
                for name in by_window
            }
            for variant in VARIANTS
        },
        "by_window": by_window,
        "aggregate": aggregate,
        "delta_metrics": aggregate,
        "best_variant": best_variant,
        "expected_value_score_delta": best["expected_value_score_delta_sum"],
        "gate4": {
            "passed": bool(best["proxy_gate4_passed"]),
            "basis": (
                "Replay-only cap-aware resize of baseline entered trades. "
                "Promotion would require shared run.py/backtester.py risk policy."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": "LLM/news replay is locked out of this deterministic entry-state replay.",
        },
        "rejection_reason": rejection_reason,
        "next_retry_requires": [
            "Do not retry nearby gap-up risk scalars on this same sample if rejected.",
            "A valid retry needs forward gap-up entry-state outcomes or an orthogonal news/event quality discriminator.",
            "Any promotion must move the rule into a shared risk policy consumed by run.py and backtester.py with parity tests.",
        ],
        "risk_of_change": (
            "May underweight valid momentum gaps or overweight exhaustion gaps; "
            "single-name contribution and three-window stability are the primary guards."
        ),
        "why_not_other_attractive_points": {
            "llm_soft_ranking": "Replay/outcome join coverage remains too sparse.",
            "earnings_c_sleeve": "Revalidated after snapshot repair and regressed all three windows.",
            "event_bundle_tuning": "State-surface add-on is already default-off for forward evidence; more same-sample tuning risks overfit.",
            "sma20_reclaim": "Only seven entered trades in the oracle aggregate, below the touched-trade gate.",
            "universe_expansion": "Recent event-sensitive liquidity refresh did not prove scarce-slot replacement value.",
        },
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            str(Path(__file__).relative_to(REPO_ROOT)),
        ],
    }
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "title": "Gap-up entry-state risk replay",
        "decision": decision,
        "best_variant": best_variant,
        "expected_value_score_delta_sum": best["expected_value_score_delta_sum"],
        "expected_value_score_delta_pct": best["expected_value_score_delta_pct"],
        "total_pnl_delta_sum": best["total_pnl_delta_sum"],
        "total_pnl_delta_pct": best["total_pnl_delta_pct"],
        "windows_ev_improved": best["windows_ev_improved"],
        "windows_ev_regressed": best["windows_ev_regressed"],
        "next_action": (
            "Do not promote; avoid nearby gap-up risk scalars without new evidence."
            if decision == "rejected"
            else "Promote only after shared policy and parity tests."
        ),
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(TICKET_JSON, ticket)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact_markdown(payload), encoding="utf-8")
    print(json.dumps(ticket, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
