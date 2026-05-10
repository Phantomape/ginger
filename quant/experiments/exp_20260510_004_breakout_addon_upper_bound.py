"""exp-20260510-004 breakout follow-through add-on upper-bound replay.

Alpha search, not a production policy change. Recent add-on work showed that
raw add-on heat-cap removal is positive but production-unsafe, while generic
entry-heat reserve and same-day add-on ordering do not unlock value. This
experiment tests the next allowed question from the playbook: whether a
state-specific add-on value discriminator is large enough to justify a future
shared production/backtest policy.

The single tested discriminator is existing `breakout_long` positions that
already passed the accepted day-2 follow-through add-on checkpoint. The replay
adds a best-case upper-bound PnL for unfilled requested add-on shares, booked
at the matched parent trade's exit. If this optimistic upper bound cannot pass
Gate 4 across the canonical windows, a real shared cap/heat adapter is not
worth implementing for this cohort.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import DEFAULT_CONFIG, BacktestEngine  # noqa: E402
from constants import EXEC_LAG_PCT  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260510-004"
STEM = "breakout_addon_upper_bound"
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{STEM}.json"
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

TARGET_STRATEGY = "breakout_long"

WINDOWS: "OrderedDict[str, dict[str, Any]]" = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": REPO_ROOT / "data" / "ohlcv_snapshot_20251023_20260421.json",
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": REPO_ROOT / "data" / "ohlcv_snapshot_20250423_20251022.json",
                "state_note": "rotation-heavy bull where strategy profits but can lag indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": REPO_ROOT / "data" / "ohlcv_snapshot_20241002_20250422.json",
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, set):
        return sorted(_safe(item) for item in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        try:
            return _safe(value.item())
        except (TypeError, ValueError):
            return str(value)
    return value


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
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
    kept.append(json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True))
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def _round(value: Any, digits: int = 6) -> Any:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _repo_rel(path: Path) -> str:
    return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _metric_slice(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "total_pnl": result.get("total_pnl"),
        "strategy_total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "win_rate": result.get("win_rate"),
        "total_trades": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": result.get("survival_rate"),
    }


def _deltas(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, before_value in before.items():
        after_value = after.get(key)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            out[key] = round(float(after_value) - float(before_value), 6)
    return out


def _match_parent_trade(event: dict[str, Any], trades: list[dict[str, Any]]) -> dict[str, Any] | None:
    checkpoint_date = str(event.get("checkpoint_date") or "")
    fill_date = str(event.get("scheduled_fill_date") or "")
    candidates: list[dict[str, Any]] = []
    for trade in trades:
        if str(trade.get("ticker") or "") != str(event.get("ticker") or ""):
            continue
        if str(trade.get("strategy") or "") != str(event.get("strategy") or ""):
            continue
        if str(trade.get("entry_date") or "") <= checkpoint_date and str(trade.get("exit_date") or "") >= fill_date:
            candidates.append(trade)
    candidates.sort(key=lambda trade: str(trade.get("entry_date") or ""), reverse=True)
    return candidates[0] if candidates else None


def _extra_pnl_for_event(
    event: dict[str, Any],
    parent: dict[str, Any] | None,
) -> dict[str, Any]:
    requested = int(event.get("requested_shares") or 0)
    executed = int(event.get("addon_shares") or 0) if event.get("status") == "executed" else 0
    unfilled = max(0, requested - executed)
    raw_open = float(event.get("raw_open") or 0.0)
    fill = float(event.get("entry_fill") or (raw_open * (1.0 + EXEC_LAG_PCT)))
    if parent is None or unfilled <= 0:
        return {
            "unfilled_shares": unfilled,
            "extra_pnl_upper_bound": 0.0,
            "matched": bool(parent),
            "exit_date": None if parent is None else parent.get("exit_date"),
            "parent_trade_key": None if parent is None else parent.get("trade_key"),
        }
    pnl_per_share = float(parent.get("exit_price") or 0.0) - fill
    return {
        "unfilled_shares": unfilled,
        "extra_pnl_upper_bound": round(unfilled * pnl_per_share, 2),
        "matched": True,
        "exit_date": parent.get("exit_date"),
        "parent_trade_key": parent.get("trade_key"),
    }


def _adjusted_equity_curve(
    equity_curve: list[list[Any]] | list[tuple[Any, Any]],
    extras_by_exit_date: dict[str, float],
) -> list[tuple[str, float]]:
    cumulative = 0.0
    adjusted: list[tuple[str, float]] = []
    for date_value, equity in equity_curve:
        date = str(date_value)
        cumulative += extras_by_exit_date.get(date, 0.0)
        adjusted.append((date, round(float(equity) + cumulative, 2)))
    return adjusted


def _curve_metrics(
    baseline: dict[str, Any],
    adjusted_curve: list[tuple[str, float]],
    extra_pnl: float,
) -> dict[str, Any]:
    equity_values = [float(eq) for _, eq in adjusted_curve]
    daily_returns = []
    for idx in range(1, len(equity_values)):
        prev = equity_values[idx - 1]
        if prev > 0:
            daily_returns.append((equity_values[idx] / prev) - 1)

    sharpe_daily = None
    if len(daily_returns) >= 2:
        mean_r = sum(daily_returns) / len(daily_returns)
        var_r = sum((ret - mean_r) ** 2 for ret in daily_returns) / (len(daily_returns) - 1)
        std_r = math.sqrt(var_r) if var_r > 0 else 0.0
        sharpe_daily = round((mean_r / std_r) * math.sqrt(252), 2) if std_r > 0 else None

    peak = 0.0
    max_dd = 0.0
    for equity in equity_values:
        peak = max(peak, equity)
        dd = (peak - equity) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, dd)

    total_pnl = float(baseline.get("total_pnl") or 0.0) + extra_pnl
    initial_capital = float(DEFAULT_CONFIG.get("INITIAL_CAPITAL") or 100_000.0)
    strategy_return = total_pnl / initial_capital
    expected_value_score = None
    if sharpe_daily is not None:
        expected_value_score = round(strategy_return * sharpe_daily, 4)

    return {
        **baseline,
        "expected_value_score": expected_value_score,
        "sharpe_daily": sharpe_daily,
        "max_drawdown_pct": round(max_dd, 4),
        "total_pnl": round(total_pnl, 2),
        "strategy_total_return_pct": round(strategy_return, 4),
    }


def _gate4_window(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_ev = float(before.get("expected_value_score") or 0.0)
    after_ev = float(after.get("expected_value_score") or 0.0)
    before_pnl = float(before.get("total_pnl") or 0.0)
    after_pnl = float(after.get("total_pnl") or 0.0)
    before_sharpe = float(before.get("sharpe_daily") or 0.0)
    after_sharpe = float(after.get("sharpe_daily") or 0.0)
    before_dd = float(before.get("max_drawdown_pct") or 0.0)
    after_dd = float(after.get("max_drawdown_pct") or 0.0)
    before_win = float(before.get("win_rate") or 0.0)
    after_win = float(after.get("win_rate") or 0.0)
    before_trades = int(before.get("total_trades") or 0)
    after_trades = int(after.get("total_trades") or 0)
    ev_delta_pct = ((after_ev - before_ev) / before_ev) if before_ev else None
    pnl_delta_pct = ((after_pnl - before_pnl) / before_pnl) if before_pnl else None
    checks = {
        "ev_gt_10pct": ev_delta_pct is not None and ev_delta_pct > 0.10,
        "pnl_gt_5pct": pnl_delta_pct is not None and pnl_delta_pct > 0.05,
        "sharpe_gt_0_1": after_sharpe - before_sharpe > 0.10,
        "drawdown_down_gt_1pp": before_dd - after_dd > 0.01,
        "trades_up_win_not_down": after_trades > before_trades and after_win >= before_win,
    }
    return {
        "passed": any(checks.values()),
        "checks": checks,
        "ev_delta_pct": _round(ev_delta_pct),
        "pnl_delta_pct": _round(pnl_delta_pct),
    }


def _aggregate(rows: dict[str, Any]) -> dict[str, Any]:
    baseline_ev = sum(float(row["before"]["expected_value_score"] or 0.0) for row in rows.values())
    after_ev = sum(float(row["after"]["expected_value_score"] or 0.0) for row in rows.values())
    baseline_pnl = sum(float(row["before"]["total_pnl"] or 0.0) for row in rows.values())
    after_pnl = sum(float(row["after"]["total_pnl"] or 0.0) for row in rows.values())
    return {
        "baseline_expected_value_score_sum": round(baseline_ev, 6),
        "after_expected_value_score_sum": round(after_ev, 6),
        "expected_value_score_delta_sum": round(after_ev - baseline_ev, 6),
        "expected_value_score_delta_pct": _round((after_ev - baseline_ev) / baseline_ev if baseline_ev else None),
        "baseline_total_pnl_sum": round(baseline_pnl, 2),
        "after_total_pnl_sum": round(after_pnl, 2),
        "total_pnl_delta_sum": round(after_pnl - baseline_pnl, 2),
        "total_pnl_delta_pct": _round((after_pnl - baseline_pnl) / baseline_pnl if baseline_pnl else None),
        "windows_ev_improved": sum(
            1
            for row in rows.values()
            if float(row["after"].get("expected_value_score") or 0.0)
            > float(row["before"].get("expected_value_score") or 0.0)
        ),
        "windows_ev_regressed": sum(
            1
            for row in rows.values()
            if float(row["after"].get("expected_value_score") or 0.0)
            < float(row["before"].get("expected_value_score") or 0.0)
        ),
        "window_gate4_passes": sum(1 for row in rows.values() if row["gate4"]["passed"]),
    }


def _eligible_events(result: dict[str, Any]) -> list[dict[str, Any]]:
    events = (result.get("addon_attribution") or {}).get("events") or []
    trades = result.get("trades") or []
    out: list[dict[str, Any]] = []
    for event in events:
        if str(event.get("strategy") or "") != TARGET_STRATEGY:
            continue
        parent = _match_parent_trade(event, trades)
        extra = _extra_pnl_for_event(event, parent)
        if extra["unfilled_shares"] <= 0:
            continue
        out.append(
            {
                "ticker": event.get("ticker"),
                "strategy": event.get("strategy"),
                "sector": event.get("sector"),
                "status": event.get("status"),
                "checkpoint_date": event.get("checkpoint_date"),
                "scheduled_fill_date": event.get("scheduled_fill_date"),
                "requested_shares": event.get("requested_shares"),
                "executed_addon_shares": event.get("addon_shares"),
                "addon_position_cap": event.get("addon_position_cap"),
                "unrealized_pct": event.get("unrealized_pct"),
                "rs_vs_spy": event.get("rs_vs_spy"),
                **extra,
            }
        )
    return out


def _window_payload(label: str, spec: dict[str, Any], universe: list[str]) -> dict[str, Any]:
    engine = BacktestEngine(
        universe,
        start=spec["start"],
        end=spec["end"],
        config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
        ohlcv_snapshot_path=str(spec["snapshot"]),
    )
    result = engine.run()
    if "error" in result:
        raise RuntimeError(f"{label} backtest failed: {result['error']}")

    before = _metric_slice(result)
    eligible = _eligible_events(result)
    extras_by_exit_date: defaultdict[str, float] = defaultdict(float)
    for event in eligible:
        exit_date = event.get("exit_date")
        if exit_date:
            extras_by_exit_date[str(exit_date)] += float(event.get("extra_pnl_upper_bound") or 0.0)

    adjusted_curve = _adjusted_equity_curve(result.get("equity_curve") or [], extras_by_exit_date)
    extra_pnl = sum(float(event.get("extra_pnl_upper_bound") or 0.0) for event in eligible)
    after = _curve_metrics(before, adjusted_curve, extra_pnl)
    sector_summary: dict[str, dict[str, Any]] = {}
    for event in eligible:
        sector = str(event.get("sector") or "unknown")
        row = sector_summary.setdefault(
            sector,
            {"event_count": 0, "unfilled_shares": 0, "extra_pnl_upper_bound": 0.0},
        )
        row["event_count"] += 1
        row["unfilled_shares"] += int(event.get("unfilled_shares") or 0)
        row["extra_pnl_upper_bound"] += float(event.get("extra_pnl_upper_bound") or 0.0)
    for row in sector_summary.values():
        row["extra_pnl_upper_bound"] = round(row["extra_pnl_upper_bound"], 2)

    return {
        "window": {
            "start": spec["start"],
            "end": spec["end"],
            "snapshot": _repo_rel(spec["snapshot"]),
            "state_note": spec["state_note"],
        },
        "before": before,
        "after": after,
        "delta": _deltas(before, after),
        "gate4": _gate4_window(before, after),
        "eligible_event_count": len(eligible),
        "extra_pnl_upper_bound": round(extra_pnl, 2),
        "eligible_events": eligible,
        "eligible_sector_summary": sector_summary,
    }


def _top_positive_share(rows: dict[str, Any]) -> float | None:
    positive = []
    for row in rows.values():
        for event in row["eligible_events"]:
            pnl = float(event.get("extra_pnl_upper_bound") or 0.0)
            if pnl > 0:
                positive.append(pnl)
    total = sum(positive)
    if total <= 0:
        return None
    return round(max(positive) / total, 4)


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID}: Breakout Add-on Upper Bound",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Gate 4",
        "",
        f"- Passed: `{payload['gate4']['passed']}`",
        f"- Aggregate EV delta: `{payload['aggregate']['expected_value_score_delta_sum']}`",
        f"- Aggregate PnL delta: `${payload['aggregate']['total_pnl_delta_sum']}`",
        f"- EV improved/regressed windows: `{payload['aggregate']['windows_ev_improved']}` / `{payload['aggregate']['windows_ev_regressed']}`",
        f"- Single-event positive contribution share: `{payload['sample_guard']['max_single_positive_share']}`",
        "",
        "## Window Results",
        "",
        "| Window | EV before | EV upper-bound | PnL upper-bound delta | Sharpe delta | DD delta | Eligible add-ons |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label, row in payload["windows"].items():
        lines.append(
            "| {label} | {before_ev} | {after_ev} | {pnl_delta} | {sharpe_delta} | {dd_delta} | {events} |".format(
                label=label,
                before_ev=row["before"]["expected_value_score"],
                after_ev=row["after"]["expected_value_score"],
                pnl_delta=row["delta"].get("total_pnl"),
                sharpe_delta=row["delta"].get("sharpe_daily"),
                dd_delta=row["delta"].get("max_drawdown_pct"),
                events=row["eligible_event_count"],
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            payload["decision_rationale"],
            "",
            "Production impact: no production/default strategy path changed. A positive future version would require a shared run/backtester policy; this upper-bound failed before that step.",
            "",
        ]
    )
    return "\n".join(lines)


def build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    universe = sorted(get_universe())
    rows: dict[str, Any] = OrderedDict(
        (label, _window_payload(label, spec, universe)) for label, spec in WINDOWS.items()
    )
    aggregate = _aggregate(rows)
    max_single_share = _top_positive_share(rows)
    sample_guard_passed = (
        sum(row["eligible_event_count"] for row in rows.values()) >= 6
        and sum(1 for row in rows.values() if row["eligible_event_count"] > 0) == 3
        and (max_single_share is None or max_single_share <= 0.50)
    )
    materiality_passed = bool(
        (aggregate["expected_value_score_delta_pct"] or 0.0) > 0.10
        or (aggregate["total_pnl_delta_pct"] or 0.0) > 0.05
        or aggregate["window_gate4_passes"] >= 2
    )
    gate_passed = bool(
        materiality_passed
        and aggregate["windows_ev_improved"] >= 2
        and aggregate["windows_ev_regressed"] == 0
        and sample_guard_passed
    )
    decision = "promising_upper_bound_requires_shared_policy" if gate_passed else "rejected_upper_bound"

    if gate_passed:
        rationale = (
            "The optimistic breakout add-on full-fill upper bound cleared the "
            "three-window materiality and sample gates. This is not production "
            "approval; the next step would be a shared run/backtester policy that "
            "keeps hard risk caps explicit."
        )
        rejection_reason = None
        next_action = (
            "Implement only as a default-off shared policy with run.py visibility "
            "and parity tests before any live/default capital."
        )
    else:
        rationale = (
            "Rejected: even the optimistic upper bound for filling all unfilled "
            "breakout_long follow-through add-on shares did not clear the EV-first "
            "three-window Gate 4 and/or sample concentration guard. Do not build a "
            "production adapter for this cohort without new forward evidence."
        )
        rejection_reason = rationale
        next_action = (
            "Keep the existing add-on cap/heat policy unchanged; prioritize event "
            "forward replacement value or a different add-on discriminator."
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "addon_breakout_upper_bound_replay",
        "mechanism_family": "followthrough_addon_materiality_ceiling",
        "hypothesis": (
            "Existing breakout_long positions that already pass the accepted day-2 "
            "follow-through add-on checkpoint may have higher marginal add-on value "
            "than trend_long add-ons, so a breakout-specific future cap/heat policy "
            "should first pass an optimistic three-window upper-bound replay."
        ),
        "alpha_hypothesis": {
            "category": "allocation/lifecycle",
            "entry_exit_ranking_or_allocation": "allocation",
            "why_this_now": (
                "The playbook's current highest unblocked alpha task is add-on "
                "materiality ceiling. LLM ranking, earnings/revisions, raw heat "
                "relaxation, generic reserve, same-day add-on ordering, and nearby "
                "add-on trigger retunes are blocked or rejected."
            ),
        },
        "single_causal_variable": (
            "breakout_long existing-position cohort as the add-on value discriminator; "
            "trigger, fraction, exits, hard production defaults, universe, and LLM/news stay locked"
        ),
        "parameters": {
            "target_strategy": TARGET_STRATEGY,
            "upper_bound_assumption": (
                "All unfilled requested add-on shares for eligible events are filled "
                "at the original scheduled add-on fill price and exit with the matched "
                "parent trade. This is intentionally optimistic and does not alter "
                "future entry ordering or production risk controls."
            ),
            "locked_variables": [
                "signal generation",
                "candidate ranking",
                "entry gates",
                "position sizing",
                "ADDON_CHECKPOINT_DAYS",
                "ADDON_MIN_UNREALIZED_PCT",
                "ADDON_MIN_RS_VS_SPY",
                "ADDON_FRACTION_OF_ORIGINAL_SHARES",
                "ADDON_MAX_POSITION_PCT",
                "ADDON_SPY_RELATIVE_LEADER_MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "exits",
                "LLM/news replay",
                "universe",
            ],
        },
        "historical_experiment_check": {
            "exp-20260508-017": (
                "Raw add-on heat cap removal was positive but rejected as production-unsafe; "
                "this run does not relax hard caps and only measures a cohort upper bound."
            ),
            "exp-20260509-004": (
                "Generic entry-heat reserves were rejected; this run is not another reserve threshold."
            ),
            "exp-20260508-018": "Same-day add-on ordering was inert.",
            "exp-20260506-015": (
                "SPY-leader add-on heat room was directionally positive but below Gate 4; "
                "this run tests whether the breakout subset has enough theoretical materiality."
            ),
        },
        "mechanism_insight_check": {
            "checked": True,
            "recent_ban_hit": False,
            "why_not_simple_repeat": (
                "It is not a trigger threshold retune, heat-cap relaxation, same-day ordering key, "
                "generic reserve, second add-on, or broad add-on cap sweep. It is a pre-policy "
                "upper-bound screen for one existing-position cohort."
            ),
        },
        "date_range": {label: f"{spec['start']} -> {spec['end']}" for label, spec in WINDOWS.items()},
        "market_regime_summary": {label: spec["state_note"] for label, spec in WINDOWS.items()},
        "before_metrics": {label: row["before"] for label, row in rows.items()},
        "after_metrics": {label: row["after"] for label, row in rows.items()},
        "delta_metrics": {label: row["delta"] for label, row in rows.items()},
        "windows": rows,
        "aggregate": aggregate,
        "sample_guard": {
            "min_eligible_events": 6,
            "requires_all_three_windows_touched": True,
            "max_single_positive_share_cap": 0.50,
            "eligible_event_count": sum(row["eligible_event_count"] for row in rows.values()),
            "windows_touched": sum(1 for row in rows.values() if row["eligible_event_count"] > 0),
            "max_single_positive_share": max_single_share,
            "passed": sample_guard_passed,
        },
        "gate4": {
            "passed": gate_passed,
            "materiality_passed": materiality_passed,
            "basis": (
                "Three canonical backtesting.md windows. Because this is an optimistic upper-bound "
                "screen, acceptance requires material aggregate improvement or at least two window "
                "Gate 4 passes, no EV regression, and the sample concentration guard."
            ),
        },
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "decision_rationale": rationale,
        "rejection_reason": rejection_reason,
        "next_action": next_action,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "production_orders_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement_if_positive": (
                "A passing future version must be implemented as a shared run/backtester "
                "policy with explicit daily JSON exposure and parity tests."
            ),
        },
        "why_not_other_attractive_points": (
            "Skipped LLM soft-ranking, earnings/revisions, AI infra pool promotion, event source pruning, "
            "rotation-surface scalar retunes, raw add-on heat relaxation, and generic entry reserve because "
            "recent records mark them data-limited, accepted-forward-only, rejected, or saturated."
        ),
        "risk_of_change": (
            "If promoted without a real shared policy, this would overstate performance by ignoring "
            "cash/heat interactions and might over-concentrate breakout winners. The failed upper bound "
            "prevents that production risk."
        ),
        "artifacts": {
            "data": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "ticket": _repo_rel(TICKET_JSON),
            "artifact": _repo_rel(ARTIFACT_MD),
        },
    }
    return payload


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": payload["experiment_id"],
            "status": payload["decision"],
            "hypothesis": payload["hypothesis"],
            "gate4": payload["gate4"],
            "aggregate": payload["aggregate"],
            "next_action": payload["next_action"],
            "artifacts": payload["artifacts"],
        },
    )
    _write_text(ARTIFACT_MD, _artifact_markdown(payload))
    _append_jsonl_dedup(
        EXPERIMENT_LOG,
        {
            "experiment_id": payload["experiment_id"],
            "timestamp": payload["timestamp"],
            "lane": payload["lane"],
            "change_type": payload["change_type"],
            "hypothesis": payload["hypothesis"],
            "parameters": payload["parameters"],
            "date_range": payload["date_range"],
            "market_regime_summary": payload["market_regime_summary"],
            "before_metrics": payload["before_metrics"],
            "after_metrics": payload["after_metrics"],
            "expected_value_score_delta": payload["expected_value_score_delta"],
            "decision": payload["decision"],
            "rejection_reason": payload["rejection_reason"],
            "production_impact": payload["production_impact"],
            "artifacts": payload["artifacts"],
        },
    )


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        f"{payload['experiment_id']} {payload['decision']} "
        f"gate4={payload['gate4']['passed']} "
        f"ev_delta={payload['aggregate']['expected_value_score_delta_sum']} "
        f"pnl_delta={payload['aggregate']['total_pnl_delta_sum']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
