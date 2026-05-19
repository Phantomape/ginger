"""exp-20260517-003: core-misfit short shadow backtest.

Replay-only follow-up to exp-20260516-043. It tests whether the
TSM/ISRG/V/DDOG core-misfit long signals have a tradable inverse edge, rather
than merely being signals to avoid.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260512_106_signal_day_sector_tape_risk as base
import exp_20260516_043_core_misfit_paper_sleeve as prior

from fill_model import (  # noqa: E402
    SLIPPAGE_BPS_ENTRY,
    SLIPPAGE_BPS_STOP,
    SLIPPAGE_BPS_TARGET,
    apply_slippage,
)
from portfolio_engine import ROUND_TRIP_COST_PCT  # noqa: E402


EXPERIMENT_ID = "exp-20260517-003"
EXPERIMENT_SLUG = "core_misfit_short_shadow_backtest"
PRIOR_EXPERIMENT_ID = "exp-20260516-043"
PRIOR_ARTIFACT = (
    base.REPO_ROOT
    / "data"
    / "experiments"
    / PRIOR_EXPERIMENT_ID
    / "core_misfit_paper_sleeve.json"
)

PRIMARY_MISFIT_TICKERS = ("TSM", "ISRG", "V", "DDOG")
TARGET_STRATEGIES = ("trend_long", "breakout_long")
SHORT_POLICY_NAMES = (
    "fixed_1d",
    "fixed_3d",
    "fixed_5d",
    "fixed_10d",
    "long_stop_target_mirror_10d",
    "symmetric_1r_stop_10d",
    "actual_long_exit",
)
MAX_HOLD_DAYS = 10
STARTING_CAPITAL = 100000.0


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_safe(v) for v in value]
    if isinstance(value, set):
        return sorted(_safe(v) for v in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
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


def _round(value: Any, digits: int = 6) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return round(value, digits)
    return value


def _money(value: Any) -> float:
    try:
        out = float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(out):
        return 0.0
    return round(out, 2)


def _load_prior_payload() -> dict[str, Any]:
    if PRIOR_ARTIFACT.exists():
        return json.loads(PRIOR_ARTIFACT.read_text(encoding="utf-8"))
    return prior.run()


def _primary_candidate_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    records = payload["paper_surfaces"]["paper_candidate_records"]
    out = []
    for row in records:
        ticker = str(row.get("ticker") or "").upper()
        strategy = str(row.get("strategy") or "")
        fill = row.get("fill") or {}
        if ticker not in PRIMARY_MISFIT_TICKERS:
            continue
        if strategy not in TARGET_STRATEGIES:
            continue
        if fill.get("status") != "filled":
            continue
        if int(row.get("shares") or 0) <= 0:
            continue
        out.append(row)
    return out


def _primary_actual_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    records = payload["paper_surfaces"]["actual_trade_records"]
    out = []
    for row in records:
        ticker = str(row.get("ticker") or "").upper()
        strategy = str(row.get("strategy") or "")
        if ticker in PRIMARY_MISFIT_TICKERS and strategy in TARGET_STRATEGIES:
            out.append(row)
    return out


def _row_index(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {str(row.get("date") or "")[:10]: idx for idx, row in enumerate(rows)}


def _short_net_return(short_entry_price: float, cover_raw_price: float, bps: int) -> float:
    cover = apply_slippage(cover_raw_price, bps, "buy")
    return (short_entry_price - cover) / short_entry_price - ROUND_TRIP_COST_PCT


def _outcome(
    source: dict[str, Any],
    *,
    policy: str,
    exit_date: str,
    exit_reason: str,
    short_entry_price: float,
    cover_raw_price: float,
    cover_bps: int,
) -> dict[str, Any]:
    shares = int(source.get("shares") or 0)
    net_return = _short_net_return(short_entry_price, cover_raw_price, cover_bps)
    pnl = short_entry_price * shares * net_return
    fill = source.get("fill") or {}
    return {
        "policy": policy,
        "window": source.get("window"),
        "ticker": str(source.get("ticker") or "").upper(),
        "strategy": source.get("strategy"),
        "decision": source.get("decision"),
        "signal_date": source.get("signal_date"),
        "entry_date": fill.get("fill_date") or source.get("entry_date"),
        "exit_date": exit_date,
        "exit_reason": exit_reason,
        "shares": shares,
        "short_entry_price": round(short_entry_price, 4),
        "cover_raw_price": round(cover_raw_price, 4),
        "net_return_pct": round(net_return, 6),
        "pnl": round(pnl, 2),
        "entry_notional": round(short_entry_price * shares, 2),
        "trade_enabled": False,
        "borrow_cost_included": False,
        "locate_constraint_included": False,
    }


def _fixed_horizon_outcomes(records: list[dict[str, Any]], horizon: int) -> list[dict[str, Any]]:
    out = []
    policy = f"fixed_{horizon}d"
    for row in records:
        values = (row.get("horizon") or {}).get(str(horizon)) or {}
        fill = row.get("fill") or {}
        if not values or not fill.get("short_entry_price"):
            continue
        out.append(
            {
                "policy": policy,
                "window": row.get("window"),
                "ticker": str(row.get("ticker") or "").upper(),
                "strategy": row.get("strategy"),
                "decision": row.get("decision"),
                "signal_date": row.get("signal_date"),
                "entry_date": fill.get("fill_date"),
                "exit_date": values.get("exit_date"),
                "exit_reason": f"fixed_{horizon}d_close",
                "shares": int(row.get("shares") or 0),
                "short_entry_price": fill.get("short_entry_price"),
                "cover_raw_price": None,
                "net_return_pct": values.get("inverse_short_net_return_pct"),
                "pnl": values.get("inverse_short_pnl"),
                "entry_notional": round(
                    float(fill.get("short_entry_price") or 0.0)
                    * int(row.get("shares") or 0),
                    2,
                ),
                "trade_enabled": False,
                "borrow_cost_included": False,
                "locate_constraint_included": False,
            }
        )
    return out


def _barrier_outcome(
    row: dict[str, Any],
    *,
    policy: str,
    short_target_raw: float,
    short_stop_raw: float,
    max_hold_days: int,
) -> dict[str, Any] | None:
    fill = row.get("fill") or {}
    short_entry = float(fill.get("short_entry_price") or 0.0)
    fill_idx = int(fill.get("fill_index") or -1)
    if short_entry <= 0 or fill_idx < 0:
        return None
    rows = prior._load_ohlcv_rows(prior.WINDOWS[row["window"]]["snapshot"], row["ticker"])
    if not rows:
        return None
    end_idx = min(fill_idx + max_hold_days, len(rows) - 1)
    for idx in range(fill_idx, end_idx + 1):
        bar = rows[idx]
        high = float(bar["high"])
        low = float(bar["low"])
        open_price = float(bar["open"])
        hit_stop = high >= short_stop_raw
        hit_target = low <= short_target_raw
        if hit_stop and hit_target:
            return _outcome(
                row,
                policy=policy,
                exit_date=bar["date"],
                exit_reason="conservative_same_day_short_stop",
                short_entry_price=short_entry,
                cover_raw_price=open_price if open_price >= short_stop_raw else short_stop_raw,
                cover_bps=SLIPPAGE_BPS_STOP,
            )
        if hit_stop:
            return _outcome(
                row,
                policy=policy,
                exit_date=bar["date"],
                exit_reason="short_stop",
                short_entry_price=short_entry,
                cover_raw_price=open_price if open_price >= short_stop_raw else short_stop_raw,
                cover_bps=SLIPPAGE_BPS_STOP,
            )
        if hit_target:
            return _outcome(
                row,
                policy=policy,
                exit_date=bar["date"],
                exit_reason="short_target",
                short_entry_price=short_entry,
                cover_raw_price=open_price if open_price <= short_target_raw else short_target_raw,
                cover_bps=SLIPPAGE_BPS_TARGET,
            )
    final = rows[end_idx]
    return _outcome(
        row,
        policy=policy,
        exit_date=final["date"],
        exit_reason=f"max_hold_{max_hold_days}d_close",
        short_entry_price=short_entry,
        cover_raw_price=float(final["close"]),
        cover_bps=SLIPPAGE_BPS_STOP,
    )


def _long_stop_target_mirror_outcomes(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in records:
        stop = float(row.get("stop_price") or 0.0)
        target = float(row.get("target_price") or 0.0)
        if stop <= 0 or target <= 0 or target <= stop:
            continue
        outcome = _barrier_outcome(
            row,
            policy="long_stop_target_mirror_10d",
            short_target_raw=stop,
            short_stop_raw=target,
            max_hold_days=MAX_HOLD_DAYS,
        )
        if outcome:
            out.append(outcome)
    return out


def _symmetric_1r_stop_outcomes(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in records:
        fill = row.get("fill") or {}
        entry = float(fill.get("raw_open") or row.get("entry_price") or 0.0)
        long_stop = float(row.get("stop_price") or 0.0)
        risk = max(entry - long_stop, 0.0)
        if entry <= 0 or risk <= 0:
            continue
        outcome = _barrier_outcome(
            row,
            policy="symmetric_1r_stop_10d",
            short_target_raw=entry - risk,
            short_stop_raw=entry + risk,
            max_hold_days=MAX_HOLD_DAYS,
        )
        if outcome:
            out.append(outcome)
    return out


def _actual_long_exit_outcomes(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in records:
        pnl = _money(row.get("inverse_actual_exit_pnl"))
        net_return = row.get("inverse_actual_exit_net_return_pct")
        shares = int(row.get("shares") or 0)
        entry = float(row.get("entry_short_price") or 0.0)
        out.append(
            {
                "policy": "actual_long_exit",
                "window": row.get("window"),
                "ticker": str(row.get("ticker") or "").upper(),
                "strategy": row.get("strategy"),
                "decision": "entered",
                "signal_date": row.get("entry_date"),
                "entry_date": row.get("entry_date"),
                "exit_date": row.get("exit_date"),
                "exit_reason": f"inverse_of_long_{row.get('exit_reason')}",
                "shares": shares,
                "short_entry_price": row.get("entry_short_price"),
                "cover_raw_price": row.get("exit_raw_price"),
                "net_return_pct": net_return,
                "pnl": pnl,
                "entry_notional": round(entry * shares, 2),
                "trade_enabled": False,
                "borrow_cost_included": False,
                "locate_constraint_included": False,
            }
        )
    return out


def _max_consecutive_losses(outcomes: list[dict[str, Any]]) -> int:
    max_losses = 0
    current = 0
    for row in sorted(outcomes, key=lambda item: (item.get("exit_date") or "", item.get("ticker") or "")):
        if _money(row.get("pnl")) < 0:
            current += 1
            max_losses = max(max_losses, current)
        else:
            current = 0
    return max_losses


def _max_drawdown_pct(outcomes: list[dict[str, Any]]) -> float:
    equity = STARTING_CAPITAL
    peak = STARTING_CAPITAL
    max_dd = 0.0
    for row in sorted(outcomes, key=lambda item: (item.get("exit_date") or "", item.get("ticker") or "")):
        equity += _money(row.get("pnl"))
        peak = max(peak, equity)
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak)
    return round(max_dd, 6)


def _trade_sharpe(outcomes: list[dict[str, Any]]) -> float | None:
    returns = [
        float(row.get("net_return_pct"))
        for row in outcomes
        if isinstance(row.get("net_return_pct"), (int, float))
    ]
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((value - mean) ** 2 for value in returns) / (len(returns) - 1)
    if variance <= 0:
        return None
    return round(mean / math.sqrt(variance) * math.sqrt(len(returns)), 6)


def _summarize_policy(outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    by_window: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"trade_count": 0, "pnl": 0.0, "wins": 0, "losses": 0}
    )
    by_ticker: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"trade_count": 0, "pnl": 0.0, "wins": 0, "losses": 0, "windows": set()}
    )
    by_exit_reason: dict[str, int] = defaultdict(int)
    total_pnl = 0.0
    positive = 0
    worst_return = None
    for row in outcomes:
        pnl = _money(row.get("pnl"))
        ret = row.get("net_return_pct")
        total_pnl += pnl
        positive += 1 if pnl > 0 else 0
        if isinstance(ret, (int, float)):
            worst_return = ret if worst_return is None else min(worst_return, ret)
        window = str(row.get("window") or "unknown")
        ticker = str(row.get("ticker") or "unknown")
        reason = str(row.get("exit_reason") or "unknown")
        by_exit_reason[reason] += 1
        by_window[window]["trade_count"] += 1
        by_window[window]["pnl"] = round(by_window[window]["pnl"] + pnl, 2)
        by_window[window]["wins"] += 1 if pnl > 0 else 0
        by_window[window]["losses"] += 1 if pnl <= 0 else 0
        by_ticker[ticker]["trade_count"] += 1
        by_ticker[ticker]["pnl"] = round(by_ticker[ticker]["pnl"] + pnl, 2)
        by_ticker[ticker]["wins"] += 1 if pnl > 0 else 0
        by_ticker[ticker]["losses"] += 1 if pnl <= 0 else 0
        by_ticker[ticker]["windows"].add(window)

    for row in by_window.values():
        count = int(row["trade_count"])
        row["win_rate"] = round(row["wins"] / count, 4) if count else None
    for row in by_ticker.values():
        count = int(row["trade_count"])
        row["win_rate"] = round(row["wins"] / count, 4) if count else None
        row["windows"] = sorted(row["windows"])

    windows_positive = [
        label for label, row in by_window.items() if float(row.get("pnl") or 0.0) > 0
    ]
    total_return = round(total_pnl / STARTING_CAPITAL, 6)
    sharpe = _trade_sharpe(outcomes)
    ev = round(total_return * sharpe, 6) if sharpe is not None else None
    return {
        "trade_count": len(outcomes),
        "total_pnl": round(total_pnl, 2),
        "total_return_pct": total_return,
        "shadow_trade_sharpe": sharpe,
        "shadow_expected_value_score": ev,
        "win_count": positive,
        "win_rate": round(positive / len(outcomes), 4) if outcomes else None,
        "worst_trade_pct": _round(worst_return),
        "max_consecutive_losses": _max_consecutive_losses(outcomes),
        "max_drawdown_pct": _max_drawdown_pct(outcomes),
        "windows": sorted(by_window),
        "positive_windows": sorted(windows_positive),
        "windows_positive_count": len(windows_positive),
        "by_window": dict(sorted(by_window.items())),
        "by_ticker": dict(sorted(by_ticker.items())),
        "by_exit_reason": dict(sorted(by_exit_reason.items())),
    }


def _build_policy_outcomes(
    candidates: list[dict[str, Any]],
    actuals: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for horizon in (1, 3, 5, 10):
        out[f"fixed_{horizon}d"] = _fixed_horizon_outcomes(candidates, horizon)
    out["long_stop_target_mirror_10d"] = _long_stop_target_mirror_outcomes(candidates)
    out["symmetric_1r_stop_10d"] = _symmetric_1r_stop_outcomes(candidates)
    out["actual_long_exit"] = _actual_long_exit_outcomes(actuals)
    return out


def _select_policy(summaries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    candidates = []
    for name, summary in summaries.items():
        if summary["trade_count"] < 4:
            continue
        candidates.append((float(summary["total_pnl"]), name, summary))
    candidates.sort(reverse=True)
    best_name = candidates[0][1] if candidates else None
    best = summaries[best_name] if best_name else {}
    passes_shadow_gate = bool(
        best
        and best.get("total_pnl", 0.0) > 0
        and best.get("windows_positive_count", 0) >= 2
        and best.get("trade_count", 0) >= 4
        and (best.get("worst_trade_pct") or 0.0) > -0.15
    )
    return {
        "best_policy": best_name,
        "best_policy_summary": best,
        "shadow_gate_passed": passes_shadow_gate,
        "live_short_promotable": False,
        "live_short_rejected_reason": (
            "historical inverse edge is sample-thin, ignores borrow/locate costs, "
            "and lacks the 20 closed forward 10-day CORE_MISFIT_PAPER outcomes "
            "required by exp-20260517-002"
        ),
    }


def _markdown(payload: dict[str, Any]) -> str:
    rows = [
        "| Policy | Trades | PnL | Win rate | Positive windows | Worst trade | Max DD |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name in SHORT_POLICY_NAMES:
        row = payload["short_policy_summaries"][name]
        rows.append(
            "| {name} | {trades} | ${pnl:,.2f} | {win:.2%} | {wins} | {worst:.2%} | {dd:.2%} |".format(
                name=name,
                trades=row["trade_count"],
                pnl=row["total_pnl"],
                win=float(row.get("win_rate") or 0.0),
                wins=row["windows_positive_count"],
                worst=float(row.get("worst_trade_pct") or 0.0),
                dd=float(row.get("max_drawdown_pct") or 0.0),
            )
        )
    selected = payload["selection"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Core Misfit Short Shadow Backtest",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "This is a replay-only historical short-shadow test. It does not change core, does not enable live shorting, and does not model borrow/locate constraints.",
            "",
            *rows,
            "",
            f"Best policy: `{selected['best_policy']}`.",
            f"Shadow gate passed: `{selected['shadow_gate_passed']}`.",
            f"Live short promotable: `{selected['live_short_promotable']}`.",
        ]
    )


def _persist(payload: dict[str, Any]) -> None:
    artifact_path = (
        base.REPO_ROOT
        / "data"
        / "experiments"
        / EXPERIMENT_ID
        / f"{EXPERIMENT_SLUG}.json"
    )
    log_path = base.REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    ticket_path = (
        base.REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
    )
    md_path = (
        base.REPO_ROOT
        / "experiments"
        / "artifacts"
        / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
    )
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "decision": payload["decision"],
        "gate4_passed": payload["gate4"]["passed"],
        "summary": payload["interpretation"],
        "artifact": str(artifact_path.relative_to(base.REPO_ROOT)),
    }
    _write_json(artifact_path, payload)
    _write_json(log_path, payload)
    _write_json(ticket_path, ticket)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_markdown(payload) + "\n", encoding="utf-8")
    _upsert_jsonl(base.REPO_ROOT / "docs" / "experiment_log.jsonl", payload)


def run() -> dict[str, Any]:
    prior_payload = _load_prior_payload()
    baseline_metrics = prior_payload["gate1"]["baseline_metrics"]
    baseline_aggregate = prior_payload["gate1"]["baseline_aggregate"]
    candidates = _primary_candidate_records(prior_payload)
    actuals = _primary_actual_records(prior_payload)
    policy_outcomes = _build_policy_outcomes(candidates, actuals)
    summaries = {
        name: _summarize_policy(policy_outcomes[name])
        for name in SHORT_POLICY_NAMES
    }
    selection = _select_policy(summaries)
    decision = (
        "promising_replay_only_short_shadow_not_live_promotable"
        if selection["shadow_gate_passed"]
        else "rejected_short_shadow"
    )
    interpretation = (
        "Historical short-shadow evidence is positive enough to keep observing "
        "CORE_MISFIT_PAPER as an inverse surface, but it is not live-promotable "
        "without forward closed outcomes and borrow/locate modelling."
        if selection["shadow_gate_passed"]
        else "The historical short-shadow did not clear even a paper-only gate."
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "If the TSM/ISRG/V/DDOG core-misfit long signals are not merely "
            "bad longs but true negative signals, then a replay-only short "
            "shadow should show positive PnL under at least one simple exit "
            "policy across multiple canonical windows."
        ),
        "change_type": "short_shadow_replay",
        "changed_variable": "short_exit_policy",
        "single_causal_variable": (
            "Only the replay-only short exit policy is swept. The source long "
            "signals, ticker cohort, sizing, candidate ranking, core exits, "
            "LLM/news, heat, slots, and production orders are locked."
        ),
        "parameters": {
            "prior_artifact": str(PRIOR_ARTIFACT.relative_to(base.REPO_ROOT)),
            "target_tickers": list(PRIMARY_MISFIT_TICKERS),
            "target_strategies": list(TARGET_STRATEGIES),
            "short_exit_policies": list(SHORT_POLICY_NAMES),
            "max_hold_days": MAX_HOLD_DAYS,
            "starting_capital": STARTING_CAPITAL,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "slippage_bps": {
                "entry": SLIPPAGE_BPS_ENTRY,
                "target_cover": SLIPPAGE_BPS_TARGET,
                "stop_cover": SLIPPAGE_BPS_STOP,
            },
            "borrow_cost_included": False,
            "locate_constraint_included": False,
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "exit/risk allocation: bad core-misfit long signals may contain "
                "a short-side inverse edge, but only as a shadow replay first."
            ),
            "2_history_check": {
                "exp-20260516-043": (
                    "Accepted default-off paper attribution; inverse horizons "
                    "were positive but explicitly not live-promotable."
                ),
                "exp-20260517-002": (
                    "Added daily production-visible paper ledger with a 20 "
                    "closed 10-day forward outcome gate before any live short."
                ),
            },
            "3_single_causal_variable": "short_exit_policy",
            "4_acceptance_standard": (
                "Paper-only shadow passes if best policy has positive PnL, at "
                "least two positive windows, >=4 trades, and worst trade better "
                "than -15%; live promotion remains blocked."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260517_003_core_misfit_short_shadow_backtest.py"
            ),
        },
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical fixed-snapshot three-window "
                "replay via exp-20260516-043 accepted artifact, followed by "
                "replay-only short-shadow exit-policy sweep"
            ),
            "windows": prior.WINDOWS,
            "config": {
                "REGIME_AWARE_EXIT": True,
                "REPLAY_PARTIAL_REDUCES": True,
                "include_entry_candidate_events": True,
            },
        },
        "gate1": {
            "baseline_metrics": baseline_metrics,
            "baseline_aggregate": baseline_aggregate,
            "baseline_artifact": str(PRIOR_ARTIFACT.relative_to(base.REPO_ROOT)),
        },
        "gate2": {
            "passed": bool(candidates and actuals),
            "runtime_fields": [
                "paper_candidate_records ticker/strategy",
                "paper_candidate_records fill.short_entry_price",
                "paper_candidate_records fill.fill_index",
                "paper_candidate_records shares",
                "paper_candidate_records stop_price",
                "paper_candidate_records target_price",
                "actual_trade_records inverse_actual_exit_pnl",
                "fixed-window OHLCV high/low/close",
            ],
            "candidate_count": len(candidates),
            "actual_trade_count": len(actuals),
        },
        "gate3": {
            "new_filter_added": False,
            "minimum_baseline_survival_rate": baseline_aggregate["survival_rate_min"],
            "passed": baseline_aggregate["survival_rate_min"] >= 0.05,
        },
        "gate4": {
            "passed": selection["shadow_gate_passed"],
            "basis": "paper-only short shadow; live short promotion is always false",
            "selected_policy": selection["best_policy"],
            "selected_policy_summary": selection["best_policy_summary"],
            "live_short_promotable": selection["live_short_promotable"],
            "live_short_rejected_reason": selection["live_short_rejected_reason"],
        },
        "before_metrics": baseline_metrics,
        "after_metrics": baseline_metrics,
        "delta_metrics": {
            "core_metrics_changed": False,
            "expected_value_score_delta": 0.0,
            "total_pnl_delta": 0.0,
        },
        "expected_value_score_delta": 0.0,
        "total_pnl_delta": 0.0,
        "short_policy_summaries": summaries,
        "short_policy_outcomes": policy_outcomes,
        "selection": selection,
        "llm_metrics": {"used_llm": False},
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "alters_orders": False,
            "live_short_enabled": False,
        },
        "known_risks": [
            "Only nine primary historical signals are available.",
            "Borrow fees, locate availability, buy-in risk, and hard-to-borrow constraints are not modelled.",
            "Fixed-horizon short exits can look good because the source is a known negative historical long cohort.",
            "A positive short shadow does not override the forward gate created in exp-20260517-002.",
        ],
        "interpretation": interpretation,
        "rejection_reason": (
            None
            if selection["shadow_gate_passed"]
            else "Best short policy failed the paper-only shadow gate."
        ),
        "next_evidence_needed": (
            "Collect >=20 closed 10-day forward CORE_MISFIT_PAPER outcomes, "
            "then rerun with borrow/locate and a true shared short adapter if "
            "inverse evidence remains positive."
        ),
        "why_not_other_changes": (
            "No core exclusion, no short order adapter, and no ticker expansion "
            "were added because this only tests whether the existing negative "
            "long cohort contains short-side evidence."
        ),
        "related_files": [
            "quant/experiments/exp_20260517_003_core_misfit_short_shadow_backtest.py",
            f"data/experiments/{EXPERIMENT_ID}/{EXPERIMENT_SLUG}.json",
            f"experiments/logs/{EXPERIMENT_ID}.json",
            f"experiments/tickets/{EXPERIMENT_ID}.json",
            f"experiments/artifacts/{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md",
            "docs/experiment_log.jsonl",
        ],
    }


if __name__ == "__main__":
    result = run()
    _persist(result)
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "decision": result["decision"],
                "best_policy": result["selection"]["best_policy"],
                "shadow_gate_passed": result["selection"]["shadow_gate_passed"],
                "live_short_promotable": result["selection"]["live_short_promotable"],
                "best_policy_pnl": result["selection"]["best_policy_summary"].get(
                    "total_pnl"
                ),
                "best_policy_win_rate": result["selection"]["best_policy_summary"].get(
                    "win_rate"
                ),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
