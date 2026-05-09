"""exp-20260508-035 early-adverse no-reclaim exit replay.

Alpha search, replay-only.  The refreshed bad-trade taxonomy from
exp-20260508-027 found a repeated hold-quality loss family:
early adverse excursion with no meaningful reclaim.  This experiment tests one
causal variable: whether an already-open A/B trade should exit at the next open
after three trading days when it has drawn down at least 3% intratrade and has
not achieved a 2% favorable excursion.

This deliberately avoids the rejected exp-20260426-053 low-MFE exit shape.  It
does not exit merely because early MFE is low; it also requires a material
adverse move.  Entries, ranking, sizing, add-ons, universe, LLM/news behavior,
and production orders are locked.
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
from constants import EXEC_LAG_PCT  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260508-035"
STEM = "early_adverse_no_reclaim_exit"
SOURCE_EXPERIMENTS = ("exp-20260508-027", "exp-20260426-053")

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
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

CORE_STRATEGIES = {"trend_long", "breakout_long"}
CONFIRM_DAYS = 3
ADVERSE_MAE_PCT = -0.03
MAX_FAVORABLE_MFE_PCT = 0.02

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


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _append_jsonl_dedup(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    needle_compact = f'"experiment_id":"{EXPERIMENT_ID}"'
    needle_pretty = f'"experiment_id": "{EXPERIMENT_ID}"'
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines() if path.exists() else []
    kept = [line for line in lines if needle_compact not in line and needle_pretty not in line]
    kept.append(json.dumps(payload, ensure_ascii=True, sort_keys=True))
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def _update_registry(payload: dict[str, Any]) -> None:
    now = payload["timestamp"]
    if REGISTRY_JSON.exists():
        registry = json.loads(REGISTRY_JSON.read_text(encoding="utf-8-sig"))
    else:
        registry = {"schema_version": 1, "experiments": []}
    experiments = registry.setdefault("experiments", [])
    experiments[:] = [
        row for row in experiments
        if str(row.get("experiment_id") or "") != EXPERIMENT_ID
    ]
    experiments.append(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": payload["hypothesis"],
            "lane": "alpha_search",
            "owner": "codex_automation_alpha_search",
            "status": payload["decision"],
            "ticket_file": str(TICKET_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
            "updated_at": now,
        }
    )
    experiments.sort(key=lambda row: str(row.get("experiment_id") or ""))
    registry["updated_at"] = now
    _write_json(REGISTRY_JSON, registry)


def _run_backtest(spec: dict[str, Any]) -> dict[str, Any]:
    engine = BacktestEngine(
        get_universe(),
        start=spec["start"],
        end=spec["end"],
        config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
        ohlcv_snapshot_path=str(REPO_ROOT / spec["snapshot"]),
    )
    result = engine.run()
    if result.get("error"):
        raise RuntimeError(str(result["error"]))
    return result


def _rows_for_trade(
    trade: dict[str, Any],
    ohlcv: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    ticker = str(trade.get("ticker") or "").upper()
    entry_date = str(trade.get("entry_date") or "")[:10]
    exit_date = str(trade.get("exit_date") or "")[:10]
    rows = ohlcv.get(ticker) or []
    return [
        row for row in rows
        if entry_date <= str(row.get("Date") or "")[:10] <= exit_date
    ]


def _float(value: Any) -> float | None:
    return base._float(value)


def _early_path_stats(
    trade: dict[str, Any],
    rows: list[dict[str, Any]],
    confirm_days: int,
) -> dict[str, Any] | None:
    entry_price = _float(trade.get("entry_price"))
    if entry_price is None or entry_price <= 0 or len(rows) <= confirm_days:
        return None
    early = rows[:confirm_days]
    highs = [_float(row.get("High")) for row in early]
    lows = [_float(row.get("Low")) for row in early]
    closes = [_float(row.get("Close")) for row in early]
    highs = [value for value in highs if value is not None]
    lows = [value for value in lows if value is not None]
    closes = [value for value in closes if value is not None]
    if not highs or not lows or not closes:
        return None
    max_high = max(highs)
    min_low = min(lows)
    confirm_close = closes[-1]
    return {
        "confirm_date": str(early[-1].get("Date") or "")[:10],
        "replay_exit_row": rows[confirm_days],
        "early_mfe_pct": max_high / entry_price - 1.0,
        "early_mae_pct": min_low / entry_price - 1.0,
        "confirm_close_return_pct": confirm_close / entry_price - 1.0,
    }


def _replay_trade_exit(
    trade: dict[str, Any],
    rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if str(trade.get("strategy") or "") not in CORE_STRATEGIES:
        return trade, None
    if not trade.get("entry_date") or not trade.get("exit_date"):
        return trade, None

    stats = _early_path_stats(trade, rows, CONFIRM_DAYS)
    if stats is None:
        return trade, None
    if not (
        stats["early_mae_pct"] <= ADVERSE_MAE_PCT
        and stats["early_mfe_pct"] < MAX_FAVORABLE_MFE_PCT
    ):
        return trade, None

    replay_exit_row = stats["replay_exit_row"]
    replay_exit_date = str(replay_exit_row.get("Date") or "")[:10]
    original_exit_date = str(trade.get("exit_date") or "")[:10]
    if not replay_exit_date or replay_exit_date >= original_exit_date:
        return trade, None

    raw_open = _float(replay_exit_row.get("Open"))
    original_exit_price = _float(trade.get("exit_price"))
    old_pnl = _float(trade.get("pnl")) or 0.0
    shares = int(trade.get("shares") or 0)
    if raw_open is None or original_exit_price is None or shares <= 0:
        return trade, None

    replay_exit_price = raw_open * (1.0 - EXEC_LAG_PCT)
    new_pnl = old_pnl + shares * (replay_exit_price - original_exit_price)
    entry_price = _float(trade.get("entry_price")) or 0.0
    cost_basis = entry_price * shares
    new_trade = dict(trade)
    new_trade.update(
        {
            "exit_date": replay_exit_date,
            "exit_price": base._round(replay_exit_price, 4),
            "exit_reason": "early_adverse_no_reclaim_exit",
            "pnl": base._round(new_pnl, 2),
            "pnl_pct_net": base._round(new_pnl / cost_basis, 6) if cost_basis else None,
            "early_adverse_no_reclaim_replay": {
                "confirm_days": CONFIRM_DAYS,
                "confirm_date": stats["confirm_date"],
                "early_mae_pct": base._round(stats["early_mae_pct"], 6),
                "early_mfe_pct": base._round(stats["early_mfe_pct"], 6),
                "confirm_close_return_pct": base._round(stats["confirm_close_return_pct"], 6),
                "raw_exit_open": base._round(raw_open, 4),
                "replay_exit_price": base._round(replay_exit_price, 4),
                "original_exit_date": original_exit_date,
                "original_exit_reason": trade.get("exit_reason"),
                "original_exit_price": base._round(original_exit_price, 4),
            },
        }
    )
    event = {
        "ticker": trade.get("ticker"),
        "strategy": trade.get("strategy"),
        "sector": trade.get("sector"),
        "entry_date": trade.get("entry_date"),
        "confirm_date": stats["confirm_date"],
        "replay_exit_date": replay_exit_date,
        "original_exit_date": original_exit_date,
        "original_exit_reason": trade.get("exit_reason"),
        "old_pnl": base._round(old_pnl, 2),
        "new_pnl": base._round(new_pnl, 2),
        "pnl_delta": base._round(new_pnl - old_pnl, 2),
        "winner_truncated": old_pnl > 0 and new_pnl < old_pnl,
        "loser_improved": old_pnl < 0 and new_pnl > old_pnl,
        "early_mae_pct": base._round(stats["early_mae_pct"], 6),
        "early_mfe_pct": base._round(stats["early_mfe_pct"], 6),
        "confirm_close_return_pct": base._round(stats["confirm_close_return_pct"], 6),
    }
    return new_trade, event


def _daily_equity_metrics(
    trades: list[dict[str, Any]],
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    spy_rows: list[dict[str, Any]],
    start: str,
    end: str,
) -> dict[str, Any]:
    return base._daily_equity_metrics(trades, rows_by_ticker, spy_rows, start, end)


def _metric_delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in (
        "expected_value_score",
        "total_pnl",
        "total_return_pct",
        "sharpe_daily",
        "max_drawdown_pct",
        "win_rate",
        "trade_count",
    ):
        if isinstance(after.get(key), (int, float)) and isinstance(before.get(key), (int, float)):
            digits = 2 if key == "total_pnl" else 4
            out[key] = round(float(after[key]) - float(before[key]), digits)
    return out


def _replay_window(name: str, spec: dict[str, Any]) -> dict[str, Any]:
    ohlcv = base._load_ohlcv(REPO_ROOT / spec["snapshot"])
    result = _run_backtest(spec)
    trades = [
        dict(trade)
        for trade in result.get("trades") or []
        if trade.get("entry_date") and trade.get("exit_date")
    ]
    spy_rows = ohlcv.get("SPY") or []
    proxy_before = _daily_equity_metrics(
        trades,
        ohlcv,
        spy_rows,
        spec["start"],
        spec["end"],
    )

    replayed: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    for trade in trades:
        rows = _rows_for_trade(trade, ohlcv)
        replacement, event = _replay_trade_exit(trade, rows)
        replayed.append(replacement)
        if event is not None:
            events.append(event)

    proxy_after = _daily_equity_metrics(
        replayed,
        ohlcv,
        spy_rows,
        spec["start"],
        spec["end"],
    )
    status_counts = Counter(str(event.get("original_exit_reason") or "unknown") for event in events)
    pnl_delta_by_ticker: defaultdict[str, float] = defaultdict(float)
    for event in events:
        pnl_delta_by_ticker[str(event.get("ticker") or "").upper()] += float(
            event.get("pnl_delta") or 0.0
        )

    return {
        "window": name,
        "window_spec": spec,
        "official_baseline_metrics": base._window_metrics(result),
        "proxy_before_metrics": proxy_before,
        "after_metrics": proxy_after,
        "delta_vs_proxy_before": _metric_delta(proxy_after, proxy_before),
        "baseline_trade_count": len(trades),
        "trigger_count": len(events),
        "winner_truncation_count": sum(1 for event in events if event.get("winner_truncated")),
        "loser_improvement_count": sum(1 for event in events if event.get("loser_improved")),
        "trigger_original_exit_reason_counts": dict(sorted(status_counts.items())),
        "pnl_delta_by_ticker": {
            ticker: base._round(value, 2) for ticker, value in sorted(pnl_delta_by_ticker.items())
        },
        "events": events,
    }


def _positive_share(values: dict[str, float]) -> float | None:
    positives = [value for value in values.values() if value > 0]
    total = sum(positives)
    if total <= 0:
        return None
    return max(positives) / total


def _aggregate(by_window: dict[str, Any]) -> dict[str, Any]:
    before_ev = sum(
        float(row["proxy_before_metrics"].get("expected_value_score") or 0.0)
        for row in by_window.values()
    )
    after_ev = sum(
        float(row["after_metrics"].get("expected_value_score") or 0.0)
        for row in by_window.values()
    )
    before_pnl = sum(
        float(row["proxy_before_metrics"].get("total_pnl") or 0.0)
        for row in by_window.values()
    )
    after_pnl = sum(
        float(row["after_metrics"].get("total_pnl") or 0.0)
        for row in by_window.values()
    )
    improved = sum(
        1 for row in by_window.values()
        if float(row["delta_vs_proxy_before"].get("expected_value_score") or 0.0) > 0.0
    )
    regressed = sum(
        1 for row in by_window.values()
        if float(row["delta_vs_proxy_before"].get("expected_value_score") or 0.0) < 0.0
    )
    max_dd_worsening = max(
        float(row["delta_vs_proxy_before"].get("max_drawdown_pct") or 0.0)
        for row in by_window.values()
    )
    ticker_delta: defaultdict[str, float] = defaultdict(float)
    for row in by_window.values():
        for ticker, value in (row.get("pnl_delta_by_ticker") or {}).items():
            ticker_delta[ticker] += float(value or 0.0)

    ev_delta = after_ev - before_ev
    pnl_delta = after_pnl - before_pnl
    pnl_delta_pct = pnl_delta / before_pnl if before_pnl else None
    ev_delta_pct = ev_delta / abs(before_ev) if before_ev else None
    max_single_share = _positive_share(dict(ticker_delta))

    gate_reasons = []
    if ev_delta_pct is not None and ev_delta_pct > 0.10:
        gate_reasons.append("aggregate expected_value_score improved >10%")
    if pnl_delta_pct is not None and pnl_delta_pct > 0.05:
        gate_reasons.append("aggregate total PnL improved >5%")
    sharpe_windows = [
        name for name, row in by_window.items()
        if float(row["delta_vs_proxy_before"].get("sharpe_daily") or 0.0) > 0.10
    ]
    drawdown_windows = [
        name for name, row in by_window.items()
        if float(row["delta_vs_proxy_before"].get("max_drawdown_pct") or 0.0) < -0.01
    ]
    if len(sharpe_windows) >= 2:
        gate_reasons.append("daily Sharpe improved >0.1 in >=2 windows")
    if len(drawdown_windows) >= 2:
        gate_reasons.append("max drawdown improved >1pp in >=2 windows")

    gate_passed = (
        bool(gate_reasons)
        and improved >= 2
        and regressed == 0
        and max_dd_worsening <= 0.01
        and sum(int(row.get("trigger_count") or 0) for row in by_window.values()) >= 8
        and (max_single_share is None or max_single_share <= 0.50)
    )
    return {
        "baseline_proxy_expected_value_score_sum": base._round(before_ev, 4),
        "after_proxy_expected_value_score_sum": base._round(after_ev, 4),
        "expected_value_score_delta_sum": base._round(ev_delta, 4),
        "expected_value_score_delta_pct": base._round(ev_delta_pct, 6),
        "baseline_proxy_total_pnl_sum": base._round(before_pnl, 2),
        "after_proxy_total_pnl_sum": base._round(after_pnl, 2),
        "total_pnl_delta_sum": base._round(pnl_delta, 2),
        "total_pnl_delta_pct": base._round(pnl_delta_pct, 6),
        "windows_ev_improved": improved,
        "windows_ev_regressed": regressed,
        "max_drawdown_worsening_max": base._round(max_dd_worsening, 4),
        "trigger_count": sum(int(row.get("trigger_count") or 0) for row in by_window.values()),
        "winner_truncation_count": sum(
            int(row.get("winner_truncation_count") or 0) for row in by_window.values()
        ),
        "loser_improvement_count": sum(
            int(row.get("loser_improvement_count") or 0) for row in by_window.values()
        ),
        "max_single_ticker_positive_share": base._round(max_single_share, 4),
        "pnl_delta_by_ticker": {
            ticker: base._round(value, 2) for ticker, value in sorted(ticker_delta.items())
        },
        "gate_reasons": gate_reasons,
        "proxy_gate4_passed": gate_passed,
    }


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
        f"# {EXPERIMENT_ID} Early-Adverse No-Reclaim Exit Replay",
        "",
        f"Decision: `{payload['decision']}`",
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
        "## Three-Window Replay",
        "",
        "| Window | EV before | EV after | EV delta | PnL delta | Sharpe delta | Max DD delta | Triggers | Winner trunc. | Loser improved |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, row in payload["by_window"].items():
        before = row["proxy_before_metrics"]
        after = row["after_metrics"]
        delta = row["delta_vs_proxy_before"]
        lines.append(
            "| {name} | {bev} | {aev} | {dev} | {pnl} | {sharpe} | {dd} | {trig} | {win_trunc} | {loss_imp} |".format(
                name=name,
                bev=before.get("expected_value_score"),
                aev=after.get("expected_value_score"),
                dev=delta.get("expected_value_score"),
                pnl=delta.get("total_pnl"),
                sharpe=delta.get("sharpe_daily"),
                dd=delta.get("max_drawdown_pct"),
                trig=row.get("trigger_count"),
                win_trunc=row.get("winner_truncation_count"),
                loss_imp=row.get("loser_improvement_count"),
            )
        )
    aggregate = payload["aggregate"]
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            f"- EV delta sum: `{aggregate['expected_value_score_delta_sum']}` ({aggregate['expected_value_score_delta_pct']})",
            f"- PnL delta sum: `${aggregate['total_pnl_delta_sum']}` ({aggregate['total_pnl_delta_pct']})",
            f"- Windows EV improved/regressed: `{aggregate['windows_ev_improved']}/{aggregate['windows_ev_regressed']}`",
            f"- Triggers: `{aggregate['trigger_count']}`",
            f"- Winner truncations: `{aggregate['winner_truncation_count']}`",
            f"- Loser improvements: `{aggregate['loser_improvement_count']}`",
            f"- Max single-ticker positive share: `{aggregate['max_single_ticker_positive_share']}`",
            f"- Gate 4: `{'PASS' if aggregate['proxy_gate4_passed'] else 'FAIL'}`",
            "",
            "## Decision Rationale",
            "",
            payload["decision_rationale"],
            "",
            "## Production Impact",
            "",
            "Replay only. No production order path, shared policy, backtester default behavior, run adapter, universe, ranking, sizing, add-on, LLM, or news behavior changed.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    by_window = OrderedDict(
        (name, _replay_window(name, spec)) for name, spec in WINDOWS.items()
    )
    aggregate = _aggregate(by_window)
    decision = "accepted_for_productionization_review" if aggregate["proxy_gate4_passed"] else "rejected"
    if aggregate["proxy_gate4_passed"]:
        decision_rationale = (
            "The replay passed the proxy Gate 4 screen. Promotion is still blocked "
            "until the exit rule is implemented as shared production/backtest policy "
            "and covered by parity tests."
        )
        rejection_reason = None
    else:
        decision_rationale = (
            "Rejected. The early-adverse/no-reclaim exit did not satisfy the "
            "EV-first three-window Gate 4 robustness standard."
        )
        rejection_reason = decision_rationale

    production_impact = {
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
    }

    hypothesis = (
        "Already-open A/B trades that suffer a material early adverse move "
        "without a meaningful three-day reclaim may be lower-quality holds; "
        "exiting them at the next open could reduce tail losses without adding "
        "entry filters or weakening hard risk controls."
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "source_experiments": SOURCE_EXPERIMENTS,
        "hypothesis": hypothesis,
        "alpha_hypothesis_category": "exit_lifecycle",
        "change_type": "exit_lifecycle_replay",
        "single_causal_variable": "early_adverse_no_reclaim_exit_trigger",
        "parameters": {
            "confirm_days": CONFIRM_DAYS,
            "adverse_mae_pct_lte": ADVERSE_MAE_PCT,
            "max_favorable_mfe_pct_lt": MAX_FAVORABLE_MFE_PCT,
            "execution": "next open after confirmation, sell-side EXEC_LAG_PCT slippage",
            "core_strategies": sorted(CORE_STRATEGIES),
            "locked_variables": [
                "production universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "position sizing",
                "stops and targets",
                "add-ons",
                "LLM/news replay",
                "earnings_event_long enablement",
            ],
            "gate4": {
                "aggregate_expected_value_score_delta_pct": "> 10%",
                "aggregate_total_pnl_delta_pct": "> 5%",
                "daily_sharpe_delta": "> 0.1 in >=2 windows",
                "drawdown_delta": "> 1pp improvement in >=2 windows",
                "robustness": "EV improves in >=2 windows and regresses in 0",
                "sample_guard": ">=8 triggers and max single ticker positive contribution <=50%",
            },
        },
        "date_range": {
            name: f"{spec['start']} -> {spec['end']}" for name, spec in WINDOWS.items()
        },
        "market_regime_summary": {
            name: spec["state_note"] for name, spec in WINDOWS.items()
        },
        "historical_experiment_check": {
            "exp-20260426-053": (
                "Rejected generic low-MFE exit because it cut winners. This run "
                "is narrower: it requires both <=-3% early MAE and <+2% early MFE."
            ),
            "exp-20260508-027": (
                "Refreshed taxonomy found early_adverse_no_reclaim as the largest "
                "hold-quality loss cluster."
            ),
            "why_not_simple_repeat": (
                "The trigger is stricter and adverse-path based, not a low-MFE "
                "or close-below-entry-only exit."
            ),
            "mechanism_insight_conflict": (
                "No conflict with LLM soft-ranking, gap-cancel, add-on volume, "
                "staged-entry, Form 4, RS20, 10-K, or sector-cap do-not-repeat zones."
            ),
        },
        "official_baseline_metrics": _official_baseline_sum(by_window),
        "before_metrics": {
            name: row["official_baseline_metrics"] for name, row in by_window.items()
        },
        "proxy_before_metrics": {
            name: row["proxy_before_metrics"] for name, row in by_window.items()
        },
        "after_metrics": {
            name: row["after_metrics"] for name, row in by_window.items()
        },
        "delta_metrics": {
            name: row["delta_vs_proxy_before"] for name, row in by_window.items()
        },
        "by_window": by_window,
        "aggregate": aggregate,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "production_impact": production_impact,
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "why_no_llm_change": (
                "LLM soft-ranking and event grading remain data-limited; this "
                "deterministic exit replay does not weaken or expand LLM duties."
            ),
        },
        "decision_rationale": decision_rationale,
        "rejection_reason": rejection_reason,
        "risk_of_change": (
            "May cut early shakeouts that later become target winners; winner "
            "truncation is the main collateral-risk guard."
        ),
        "next_retry_requires": [
            "Do not retry nearby 3-day/3%/2% early-adverse exit thresholds on the same sample if rejected.",
            "A valid retry needs an orthogonal event/news/market-state discriminator that separates early shakeouts from true failed holds.",
            "Any positive promotion must move the exit trigger into shared production/backtest lifecycle policy with parity tests.",
        ],
        "related_files": [
            str(Path(__file__).relative_to(REPO_ROOT)).replace("\\", "/"),
            str(OUT_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
            str(LOG_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
            str(TICKET_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)).replace("\\", "/"),
        ],
    }

    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "title": "Early adverse no-reclaim exit",
        "status": decision,
        "decision": decision,
        "summary": decision_rationale,
        "created_at": timestamp,
        "artifact": str(ARTIFACT_MD.relative_to(REPO_ROOT)).replace("\\", "/"),
        "log": str(LOG_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
        "next_action": (
            "Promote only after shared lifecycle policy and parity tests."
            if aggregate["proxy_gate4_passed"]
            else "Do not promote; use only as failed lifecycle evidence."
        ),
    }
    log_payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": hypothesis,
        "change_type": payload["change_type"],
        "parameters": payload["parameters"],
        "date_range": payload["date_range"],
        "market_regime_summary": payload["market_regime_summary"],
        "before_metrics": payload["before_metrics"],
        "proxy_before_metrics": payload["proxy_before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "aggregate": aggregate,
        "production_impact": production_impact,
        "llm_metrics": payload["llm_metrics"],
        "rejection_reason": rejection_reason,
        "related_files": payload["related_files"],
        "next_retry_requires": payload["next_retry_requires"],
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, log_payload)
    _write_json(TICKET_JSON, ticket)
    _append_jsonl_dedup(EXPERIMENT_LOG, log_payload)
    _update_registry(payload)
    _write_text(ARTIFACT_MD, _artifact_markdown(payload))

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": decision,
                "aggregate": aggregate,
                "official_baseline": payload["official_baseline_metrics"],
                "artifact": str(ARTIFACT_MD),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
