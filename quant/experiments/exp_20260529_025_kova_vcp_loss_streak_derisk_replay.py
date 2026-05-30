"""exp-20260529-025: Kova VCP loss-streak de-risking shadow replay.

This tests one Kova operator-risk idea on the accepted exp-20260526-007 VCP
top-2 paper sleeve: if the already-closed VCP paper ledger has two consecutive
losing trades before a new entry, halve the new trade's paper notional until a
closed winner resets the streak.

The replay is closed-ledger and ex-ante: only source trades with
``exit_date < entry_date`` are visible at each new paper entry. No production
strategy, backtester, ranking, entry, exit, universe, LLM/news, or live order
path changes here.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path
from statistics import mean, pstdev
from typing import Any


EXPERIMENTS_DIR = Path(__file__).resolve().parent
if str(EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS_DIR))

from exp_20260528_002_kova_high_volume_weak_close_exit_shadow_replay import (  # noqa: E402
    REPO_ROOT,
    SOURCE_VARIANT,
    _audit_open_positions,
    _load_source_rank_profile,
    _num,
    _repo_rel,
    _safe,
    _source_trade_rows,
    _write_json,
)
from exp_20260526_022_vcp_base_geometry_higher_low_attribution import (  # noqa: E402
    SOURCE_EXP007_JSON,
    WINDOWS,
    _load_json,
    _now,
    _write_text,
)


EXPERIMENT_ID = "exp-20260529-025"
STEM = "kova_vcp_loss_streak_derisk_replay"
TRIAL_FAMILY = "kova_vcp_loss_streak_derisk_replay"
TRIAL_VARIANT_ID = "kova_vcp_loss2_050x_until_reset_v1"
CHANGED_VARIABLE = "kova_vcp_closed_loss_streak_notional_scalar_v1"
RULE_VERSION = "kova_vcp_closed_loss_streak_notional_scalar_v1"

LOSS_STREAK_TRIGGER_COUNT = 2
RISK_SCALAR_AFTER_LOSS_STREAK = 0.50
MIN_SCALED_TRADES = 10
MAX_SINGLE_POSITIVE_DELTA_SHARE = 0.50
MAX_WINDOW_REGRESSIONS = 1

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOCS_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
EXPERIMENT_REGISTRY = REPO_ROOT / "docs" / "experiment_registry.json"

ANTI_JS = "No JavaScript was used."
BASELINE = {
    "accepted_core_expected_value_score_sum": 7.8941,
    "accepted_core_total_pnl_sum": 234850.99,
    "baseline_source": "docs/backtesting.md accepted aggregate core stack",
}


def _date10(value: Any) -> str:
    return str(value or "")[:10]


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _trade_sort_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        _date10(row.get("entry_date")),
        _date10(row.get("signal_date") or row.get("date")),
        str(row.get("ticker") or ""),
        _date10(row.get("exit_date")),
    )


def _closed_sort_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        _date10(row.get("exit_date")),
        _date10(row.get("entry_date")),
        str(row.get("ticker") or ""),
        _date10(row.get("signal_date") or row.get("date")),
    )


def _trade_field_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    required = [
        "ticker",
        "signal_date",
        "entry_date",
        "exit_date",
        "paper_notional_usd",
        "pnl",
    ]
    missing: dict[str, list[str]] = {}
    for field in required:
        tickers = [
            str(row.get("ticker") or "<unknown>")
            for row in rows
            if row.get(field) in (None, "")
        ]
        if tickers:
            missing[field] = tickers[:20]
    return {
        "passed": not missing,
        "required_trade_fields": required,
        "source_trade_count": len(rows),
        "missing_fields": missing,
    }


def _known_closed_before_entry(
    *,
    all_window_rows: list[dict[str, Any]],
    entry_date: str,
) -> list[dict[str, Any]]:
    return sorted(
        [
            row
            for row in all_window_rows
            if _date10(row.get("exit_date")) and _date10(row.get("exit_date")) < entry_date
        ],
        key=_closed_sort_key,
    )


def _loss_streak_from_closed_rows(closed_rows: list[dict[str, Any]]) -> int:
    streak = 0
    for row in reversed(closed_rows):
        pnl = _num(row.get("pnl")) or 0.0
        if pnl < 0:
            streak += 1
            continue
        break
    return streak


def _recent_closed_rows(closed_rows: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    out = []
    for row in closed_rows[-limit:]:
        out.append(
            {
                "ticker": str(row.get("ticker") or ""),
                "entry_date": _date10(row.get("entry_date")),
                "exit_date": _date10(row.get("exit_date")),
                "pnl": _round(row.get("pnl"), 4),
            }
        )
    return out


def _shadow_trade(
    *,
    trade: dict[str, Any],
    all_window_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    window = str(trade.get("window") or "")
    ticker = str(trade.get("ticker") or "").upper()
    signal_date = _date10(trade.get("signal_date") or trade.get("date"))
    entry_date = _date10(trade.get("entry_date"))
    exit_date = _date10(trade.get("exit_date"))
    base_notional = _num(trade.get("paper_notional_usd")) or 0.0
    base_pnl = _num(trade.get("pnl")) or 0.0
    base_return = base_pnl / base_notional if base_notional else None

    closed_rows = _known_closed_before_entry(
        all_window_rows=all_window_rows,
        entry_date=entry_date,
    )
    loss_streak = _loss_streak_from_closed_rows(closed_rows)
    scaled = loss_streak >= LOSS_STREAK_TRIGGER_COUNT
    scalar = RISK_SCALAR_AFTER_LOSS_STREAK if scaled else 1.0
    after_notional = base_notional * scalar
    after_pnl = base_pnl * scalar
    after_return = after_pnl / after_notional if after_notional else None
    delta_pnl = after_pnl - base_pnl

    return {
        "window": window,
        "ticker": ticker,
        "signal_date": signal_date,
        "entry_date": entry_date,
        "exit_date": exit_date,
        "vcp_candidate_rank_on_signal_date": trade.get("vcp_candidate_rank_on_signal_date"),
        "base_notional": _round(base_notional, 4),
        "base_pnl": _round(base_pnl, 4),
        "base_return": _round(base_return, 6),
        "known_closed_count": len(closed_rows),
        "active_loss_streak_count": loss_streak,
        "loss_streak_trigger_count": LOSS_STREAK_TRIGGER_COUNT,
        "notional_scalar": scalar,
        "scaled": scaled,
        "after_notional": _round(after_notional, 4),
        "after_pnl": _round(after_pnl, 4),
        "after_return": _round(after_return, 6),
        "delta_pnl": _round(delta_pnl, 4),
        "scaled_winner": scaled and base_pnl > 0,
        "scaled_loser": scaled and base_pnl < 0,
        "known_at": (
            "entry_date_open_after_prior_closed_vcp_paper_exits; only source "
            "trades with exit_date < entry_date are counted"
        ),
        "recent_closed_trades": _recent_closed_rows(closed_rows),
    }


def _metric_summary(
    rows: list[dict[str, Any]],
    *,
    pnl_key: str,
    notional_key: str,
) -> dict[str, Any]:
    pnls = [float(row.get(pnl_key) or 0.0) for row in rows]
    notionals = [float(row.get(notional_key) or 0.0) for row in rows]
    pct_returns = [
        pnl / notional
        for pnl, notional in zip(pnls, notionals)
        if notional and math.isfinite(pnl / notional)
    ]
    total_pnl = sum(pnls)
    total_notional = sum(notionals)
    return_on_notional = total_pnl / total_notional if total_notional else 0.0
    if len(pct_returns) >= 2 and pstdev(pct_returns) > 0:
        trade_sharpe_proxy = mean(pct_returns) / pstdev(pct_returns) * math.sqrt(len(pct_returns))
    else:
        trade_sharpe_proxy = 0.0
    return {
        "trade_count": len(rows),
        "total_pnl": _round(total_pnl, 4),
        "total_notional": _round(total_notional, 4),
        "return_on_notional": _round(return_on_notional, 6),
        "avg_pnl": _round(total_pnl / len(rows), 4) if rows else 0.0,
        "win_rate": _round(sum(1 for pnl in pnls if pnl > 0) / len(pnls), 6) if pnls else 0.0,
        "trade_sharpe_proxy": _round(trade_sharpe_proxy, 6),
        "expected_value_proxy": _round(return_on_notional * trade_sharpe_proxy, 6),
    }


def _drawdown_summary(
    rows: list[dict[str, Any]],
    *,
    pnl_key: str,
    notional_key: str,
) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda row: (_date10(row.get("exit_date")), _date10(row.get("entry_date")), str(row.get("ticker") or "")))
    cumulative = 0.0
    peak = 0.0
    max_drawdown = 0.0
    trough_date = None
    peak_date = None
    active_peak_date = None
    for row in ordered:
        cumulative += float(row.get(pnl_key) or 0.0)
        row_date = _date10(row.get("exit_date"))
        if cumulative > peak:
            peak = cumulative
            active_peak_date = row_date
        drawdown = peak - cumulative
        if drawdown > max_drawdown:
            max_drawdown = drawdown
            trough_date = row_date
            peak_date = active_peak_date
    total_notional = sum(float(row.get(notional_key) or 0.0) for row in rows)
    return {
        "max_drawdown_pnl": _round(max_drawdown, 4),
        "max_drawdown_on_total_notional": _round(max_drawdown / total_notional, 6)
        if total_notional
        else None,
        "peak_date": peak_date,
        "trough_date": trough_date,
        "ending_cumulative_pnl": _round(cumulative, 4),
    }


def _positive_delta_concentration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_ticker: defaultdict[str, float] = defaultdict(float)
    for row in rows:
        delta = float(row.get("delta_pnl") or 0.0)
        if delta > 0:
            by_ticker[str(row.get("ticker") or "")] += delta
    total = sum(by_ticker.values())
    ranked = [
        {
            "ticker": ticker,
            "positive_delta_pnl": _round(value, 4),
            "share": _round(value / total, 6) if total else None,
        }
        for ticker, value in sorted(by_ticker.items(), key=lambda item: item[1], reverse=True)
    ]
    return {
        "positive_delta_total": _round(total, 4),
        "top_ticker": ranked[0]["ticker"] if ranked else None,
        "top_ticker_positive_delta_share": ranked[0]["share"] if ranked else None,
        "by_ticker": ranked,
    }


def _summaries(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    window_regressions = []
    for window in WINDOWS:
        window_rows = [row for row in rows if row.get("window") == window]
        before = _metric_summary(window_rows, pnl_key="base_pnl", notional_key="base_notional")
        after = _metric_summary(window_rows, pnl_key="after_pnl", notional_key="after_notional")
        before_dd = _drawdown_summary(window_rows, pnl_key="base_pnl", notional_key="base_notional")
        after_dd = _drawdown_summary(window_rows, pnl_key="after_pnl", notional_key="after_notional")
        delta = {
            "total_pnl": _round(after["total_pnl"] - before["total_pnl"], 4),
            "expected_value_proxy": _round(
                after["expected_value_proxy"] - before["expected_value_proxy"],
                6,
            ),
            "return_on_notional": _round(
                after["return_on_notional"] - before["return_on_notional"],
                6,
            ),
            "max_drawdown_pnl": _round(
                after_dd["max_drawdown_pnl"] - before_dd["max_drawdown_pnl"],
                4,
            ),
        }
        regressed = delta["total_pnl"] < -1e-6 or delta["expected_value_proxy"] < -1e-9
        if regressed:
            window_regressions.append(window)
        by_window[window] = {
            "before": before,
            "after": after,
            "delta": delta,
            "drawdown_before": before_dd,
            "drawdown_after": after_dd,
            "scaled_count": sum(1 for row in window_rows if row.get("scaled")),
            "scaled_winner_count": sum(1 for row in window_rows if row.get("scaled_winner")),
            "scaled_loser_count": sum(1 for row in window_rows if row.get("scaled_loser")),
            "regressed": regressed,
        }

    before_all = _metric_summary(rows, pnl_key="base_pnl", notional_key="base_notional")
    after_all = _metric_summary(rows, pnl_key="after_pnl", notional_key="after_notional")
    before_dd_all = _drawdown_summary(rows, pnl_key="base_pnl", notional_key="base_notional")
    after_dd_all = _drawdown_summary(rows, pnl_key="after_pnl", notional_key="after_notional")
    scaled_rows = [row for row in rows if row.get("scaled")]
    deltas = [float(row.get("delta_pnl") or 0.0) for row in scaled_rows]
    concentration = _positive_delta_concentration(rows)
    return {
        "aggregate": {
            "before": before_all,
            "after": after_all,
            "delta": {
                "total_pnl": _round(after_all["total_pnl"] - before_all["total_pnl"], 4),
                "total_pnl_delta_pct": _round(
                    (after_all["total_pnl"] - before_all["total_pnl"])
                    / abs(before_all["total_pnl"]),
                    6,
                )
                if before_all["total_pnl"]
                else None,
                "expected_value_proxy": _round(
                    after_all["expected_value_proxy"] - before_all["expected_value_proxy"],
                    6,
                ),
                "return_on_notional": _round(
                    after_all["return_on_notional"] - before_all["return_on_notional"],
                    6,
                ),
                "max_drawdown_pnl": _round(
                    after_dd_all["max_drawdown_pnl"] - before_dd_all["max_drawdown_pnl"],
                    4,
                ),
            },
            "drawdown_before": before_dd_all,
            "drawdown_after": after_dd_all,
        },
        "by_window": by_window,
        "loss_streak": {
            "scaled_count": len(scaled_rows),
            "scaled_rate": _round(len(scaled_rows) / len(rows), 6) if rows else 0.0,
            "scaled_loser_count": sum(1 for row in scaled_rows if row.get("scaled_loser")),
            "scaled_winner_count": sum(1 for row in scaled_rows if row.get("scaled_winner")),
            "beneficial_scaled_count": sum(1 for delta in deltas if delta > 0),
            "harmful_scaled_count": sum(1 for delta in deltas if delta < 0),
            "total_scaled_delta_pnl": _round(sum(deltas), 4),
            "avg_scaled_delta_pnl": _round(sum(deltas) / len(deltas), 4) if deltas else 0.0,
            "max_loss_streak_seen": max(
                [int(row.get("active_loss_streak_count") or 0) for row in rows],
                default=0,
            ),
            "status_counts": dict(sorted(Counter("scaled" if row.get("scaled") else "unscaled" for row in rows).items())),
            "positive_delta_concentration": concentration,
        },
        "window_regressions": window_regressions,
    }


def _decision(summary: dict[str, Any]) -> tuple[str, str, dict[str, Any], str, str | None]:
    aggregate = summary["aggregate"]
    loss_streak = summary["loss_streak"]
    concentration = loss_streak["positive_delta_concentration"]
    aggregate_pnl_improved = aggregate["delta"]["total_pnl"] > 0
    aggregate_ev_improved = aggregate["delta"]["expected_value_proxy"] > 0
    scaled_count_ok = loss_streak["scaled_count"] >= MIN_SCALED_TRADES
    window_regression_ok = len(summary["window_regressions"]) <= MAX_WINDOW_REGRESSIONS
    drawdown_ok = aggregate["delta"]["max_drawdown_pnl"] <= 1e-6
    concentration_share = concentration["top_ticker_positive_delta_share"]
    concentration_ok = concentration_share is not None and concentration_share <= MAX_SINGLE_POSITIVE_DELTA_SHARE
    passed = (
        aggregate_pnl_improved
        and aggregate_ev_improved
        and scaled_count_ok
        and window_regression_ok
        and drawdown_ok
        and concentration_ok
    )
    evidence = {
        "shadow_gate_passed": passed,
        "aggregate_pnl_improved": aggregate_pnl_improved,
        "aggregate_ev_improved": aggregate_ev_improved,
        "scaled_count_ok": scaled_count_ok,
        "scaled_count": loss_streak["scaled_count"],
        "scaled_count_min": MIN_SCALED_TRADES,
        "window_regression_ok": window_regression_ok,
        "window_regressions": summary["window_regressions"],
        "window_regressions_max": MAX_WINDOW_REGRESSIONS,
        "drawdown_ok": drawdown_ok,
        "aggregate_drawdown_delta_pnl": aggregate["delta"]["max_drawdown_pnl"],
        "concentration_ok": concentration_ok,
        "top_ticker_positive_delta_share": concentration_share,
        "max_single_positive_delta_share_limit": MAX_SINGLE_POSITIVE_DELTA_SHARE,
        "beneficial_scaled_count": loss_streak["beneficial_scaled_count"],
        "harmful_scaled_count": loss_streak["harmful_scaled_count"],
    }
    if passed:
        return (
            "observed_only_candidate_not_promoted",
            "observed_only",
            evidence,
            (
                "The Kova VCP closed-ledger loss-streak de-risking replay improved "
                "aggregate PnL and EV proxy without violating the drawdown, sample, "
                "window-stability, or concentration checks. Treat as a candidate "
                "for a full slot/heat/replacement-value replay, not as a production "
                "capital rule."
            ),
            None,
        )

    failed = [
        name
        for name in [
            "aggregate_pnl_improved",
            "aggregate_ev_improved",
            "scaled_count_ok",
            "window_regression_ok",
            "drawdown_ok",
            "concentration_ok",
        ]
        if not evidence[name]
    ]
    reason = "failed checks: " + ", ".join(failed)
    return (
        "rejected_kova_vcp_loss_streak_derisk_replay",
        "rejected",
        evidence,
        (
            "The Kova VCP closed-ledger loss-streak de-risking replay failed "
            f"Gate 4 ({reason}). Do not promote this notional scalar from the "
            "closed paper ledger."
        ),
        reason,
    )


def _log_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if key not in {"shadow_rows"}
    }


def _build_payload() -> dict[str, Any]:
    created_at = _now()
    source = _load_source_rank_profile()
    trades_by_window = _source_trade_rows(source)
    source_rows_flat = [row for rows in trades_by_window.values() for row in rows]
    shadow_rows: list[dict[str, Any]] = []
    for window in WINDOWS:
        window_rows = sorted(trades_by_window.get(window, []), key=_trade_sort_key)
        for trade in window_rows:
            shadow_rows.append(_shadow_trade(trade=trade, all_window_rows=window_rows))

    summary = _summaries(shadow_rows)
    decision, status, evidence, summary_text, rejection_reason = _decision(summary)
    open_positions_audit = _audit_open_positions()
    source_field_audit = _trade_field_audit(source_rows_flat)
    source_variant = source["variant"]
    ticket = _existing_ticket()
    predicted_success_probability = (
        ticket.get("prediction", {}).get("success_probability")
        if isinstance(ticket.get("prediction"), dict)
        else None
    )
    if predicted_success_probability is None:
        predicted_success_probability = 0.20
    actual_success = 1 if evidence["shadow_gate_passed"] else 0
    related_files = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(DOCS_TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(ARTIFACT_MD),
        _repo_rel(SOURCE_EXP007_JSON),
    ]

    return {
        "experiment_id": EXPERIMENT_ID,
        "created_at": created_at,
        "timestamp": created_at,
        "status": status,
        "registry_lane": "alpha_discovery",
        "lane": "alpha_discovery",
        "decision": decision,
        "summary": summary_text,
        "alpha_hypothesis": (
            "Kova VCP paper trades may benefit from a closed-ledger loss-streak "
            "de-risking rule: after two already-closed losing VCP paper trades, "
            "halve subsequent VCP paper notional until the closed streak resets."
        ),
        "hypothesis": (
            "After two already-closed losing VCP paper trades, reducing the next "
            "VCP paper notional by 50% may lower drawdowns and improve expected "
            "value without discarding the accepted VCP source sleeve."
        ),
        "change_summary": (
            "Closed-ledger shadow replay over exp-20260526-007 VCP top-2 "
            "rank-notional paper trades; no production policy changed."
        ),
        "change_type": "closed_ledger_capital_allocation_shadow_replay",
        "mechanism_family": "kova_vcp_operator_risk_allocation",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "rule_version": RULE_VERSION,
        "prior_trial_count": 2,
        "nearby_prior_experiments": [
            "exp-20260514-043",
            "exp-20260527-909",
            "exp-20260528-002",
            "exp-20260528-031",
            "exp-20260529-006",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "closed_paper_ledger_state_replay",
        "component": _repo_rel(Path(__file__)),
        "parameters": {
            "source_artifact": _repo_rel(SOURCE_EXP007_JSON),
            "source_variant": SOURCE_VARIANT,
            "loss_streak_trigger_count": LOSS_STREAK_TRIGGER_COUNT,
            "risk_scalar_after_loss_streak": RISK_SCALAR_AFTER_LOSS_STREAK,
            "reset_condition": "next known closed VCP paper trade has pnl >= 0",
            "known_closed_boundary": "exit_date < entry_date",
            "min_scaled_trades": MIN_SCALED_TRADES,
            "max_window_regressions": MAX_WINDOW_REGRESSIONS,
            "max_single_positive_delta_share": MAX_SINGLE_POSITIVE_DELTA_SHARE,
            "anti_js": ANTI_JS,
        },
        "date_range": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": WINDOWS,
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "Risk allocation: a Kova-style pause/halve-after-repeated-stops "
                "operator rule may improve the VCP paper sleeve by reducing "
                "exposure during realized local loss streaks."
            ),
            "1_playbook_alignment": (
                "Drawn directly from docs/kova-research-directions.md "
                "streak-based de-risking. It uses closed-trade ledger state "
                "rather than a new per-trade entry filter."
            ),
            "2_history_check": (
                "exp-20260514-043 rejected a broader core portfolio realized loss "
                "streak risk scalar. This run is narrower: accepted VCP top-2 "
                "paper sleeve only, closed-ledger only, no production sizing."
            ),
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Aggregate PnL and EV proxy improve; scaled_count >= 10; no more "
                "than one canonical window regresses on PnL/EV proxy; drawdown "
                "proxy does not worsen; top positive delta ticker share <= 50%."
            ),
            "5_reproducibility": (
                ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260529_025_kova_vcp_loss_streak_derisk_replay.py"
            ),
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": WINDOWS,
            "source_population": _repo_rel(SOURCE_EXP007_JSON),
            "source_variant": SOURCE_VARIANT,
            "paper_entry": "next available open from exp-20260526-007 source sleeve",
            "paper_exit": "10 trading days after signal from exp-20260526-007 source sleeve",
            "rank_notional_profile": [1.0, 1.25],
            "changed_core_logic": False,
            "strategy_replacement_tested": False,
            "shadow_replay_only": True,
            "closed_ledger_ex_ante_boundary": "exit_date < entry_date",
        },
        "gate1": {
            "passed": True,
            **BASELINE,
            "baseline_result_file": _repo_rel(SOURCE_EXP007_JSON),
            "source_exp007_summary": {
                "expected_value_score_delta_vs_core": source_variant.get("expected_value_score_delta"),
                "total_pnl_delta_vs_core": source_variant.get("total_pnl_delta"),
                "target_trade_count": len(shadow_rows),
                "target_trade_summary": source_variant.get("target_trade_summary"),
            },
            "core_logic_changed": False,
        },
        "gate2": {
            "passed": open_positions_audit.get("passed") is True and source_field_audit["passed"],
            "open_positions": open_positions_audit,
            "source_trade_fields": source_field_audit,
            "required_runtime_fields": ["entry_date", "target_price"],
            "no_llm_prompt_dependency": True,
        },
        "gate3": {
            "passed": True,
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "source_trade_count": len(shadow_rows),
            "scaled_count": summary["loss_streak"]["scaled_count"],
            "core_survival_changed": False,
            "note": (
                "No filter is added and no trade is dropped; this only rescales "
                "paper notional in a closed-ledger shadow replay."
            ),
        },
        "gate4": {
            "passed": evidence["shadow_gate_passed"],
            "strategy_replacement_tested": False,
            "promotion_grade": False,
            "reason": "Closed-trade shadow replay only; no production strategy rule changed.",
            "decision_evidence": evidence,
        },
        "before_metrics": summary["aggregate"]["before"],
        "after_metrics": summary["aggregate"]["after"],
        "delta_metrics": summary["aggregate"]["delta"],
        "drawdown_before": summary["aggregate"]["drawdown_before"],
        "drawdown_after": summary["aggregate"]["drawdown_after"],
        "window_metrics": summary["by_window"],
        "loss_streak_metrics": summary["loss_streak"],
        "shadow_rows": shadow_rows,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "orders_changed": False,
            "live_capital_changed": False,
            "trade_enabled": False,
            "default_off_paper_only": True,
            "shadow_replay_only": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
        },
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "prediction": ticket.get("prediction")
        or {
            "success_probability": predicted_success_probability,
            "expected_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "main_failure_modes": [
                "cuts_recovering_winners",
                "sample_too_thin",
                "no_window_stability",
                "prior_loss_streak_failure_repeats",
            ],
            "confidence_reason": (
                "Kova process supports reducing risk after repeated stops, but "
                "the broader core portfolio loss-streak allocator failed and "
                "VCP winners can be convex."
            ),
            "recorded_at": created_at,
        },
        "calibration": {
            "actual_decision": decision,
            "actual_success": actual_success,
            "predicted_success_probability": predicted_success_probability,
            "brier_score": _round((predicted_success_probability - actual_success) ** 2, 6),
            "expected_ev_delta": 0.0,
            "actual_ev_delta": summary["aggregate"]["delta"]["expected_value_proxy"],
            "ev_prediction_error": summary["aggregate"]["delta"]["expected_value_proxy"],
            "expected_pnl_delta": 0.0,
            "actual_pnl_delta": summary["aggregate"]["delta"]["total_pnl"],
            "pnl_prediction_error": summary["aggregate"]["delta"]["total_pnl"],
            "predicted_failure_modes": [
                "cuts_recovering_winners",
                "sample_too_thin",
                "no_window_stability",
                "prior_loss_streak_failure_repeats",
            ],
            "realized_failure_mode": rejection_reason,
            "predicted_failure_mode_hit": actual_success == 0,
        },
        "expected_value_score_delta": summary["aggregate"]["delta"]["expected_value_proxy"],
        "total_pnl_delta": summary["aggregate"]["delta"]["total_pnl"],
        "rejection_reason": rejection_reason,
        "next_retry_requires": [
            "full_slot_heat_replacement_value_replay_before_any_sizing_change",
            "evidence_that_loss_streak_scaling_does_not_cut_convex_vcp_recoveries",
            "forward_closed_vcp_paper_rows_with_non_concentrated_positive_delta",
        ],
        "related_files": related_files,
        "repro_command": (
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260529_025_kova_vcp_loss_streak_derisk_replay.py"
        ),
        "artifacts": {
            "json": _repo_rel(OUT_JSON),
            "markdown": _repo_rel(ARTIFACT_MD),
            "log": _repo_rel(LOG_JSON),
            "ticket": _repo_rel(TICKET_JSON),
            "docs_ticket": _repo_rel(DOCS_TICKET_JSON),
            "card": _repo_rel(CARD_MD),
            "manifest": _repo_rel(MANIFEST_JSON),
        },
        "why_not_other_changes": (
            "Did not alter VCP entries, rank-notional profile, ranking, source "
            "candidate selection, exits, universe, LLM/news, backtester, run.py, "
            "or live/default orders."
        ),
        "anti_js": ANTI_JS,
    }


def _window_table(payload: dict[str, Any]) -> list[str]:
    lines = [
        "| window | scaled | before pnl | after pnl | delta pnl | delta EV proxy | drawdown delta | regressed |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for window, row in payload["window_metrics"].items():
        lines.append(
            "| {window} | {scaled} | {before} | {after} | {delta} | {ev_delta} | {dd_delta} | {regressed} |".format(
                window=window,
                scaled=row["scaled_count"],
                before=row["before"]["total_pnl"],
                after=row["after"]["total_pnl"],
                delta=row["delta"]["total_pnl"],
                ev_delta=row["delta"]["expected_value_proxy"],
                dd_delta=row["delta"]["max_drawdown_pnl"],
                regressed=row["regressed"],
            )
        )
    return lines


def _scaled_sample_table(payload: dict[str, Any]) -> list[str]:
    rows = sorted(
        [row for row in payload["shadow_rows"] if row.get("scaled")],
        key=lambda row: abs(float(row.get("delta_pnl") or 0.0)),
        reverse=True,
    )[:10]
    lines = [
        "| ticker | window | entry | exit | base pnl | scalar | delta pnl | prior loss streak |",
        "|---|---|---|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {ticker} | {window} | {entry} | {exit} | {base} | {scalar} | {delta} | {streak} |".format(
                ticker=row["ticker"],
                window=row["window"],
                entry=row["entry_date"],
                exit=row["exit_date"],
                base=row["base_pnl"],
                scalar=row["notional_scalar"],
                delta=row["delta_pnl"],
                streak=row["active_loss_streak_count"],
            )
        )
    return lines


def _build_report(payload: dict[str, Any]) -> str:
    loss = payload["loss_streak_metrics"]
    concentration = loss["positive_delta_concentration"]
    evidence = payload["gate4"]["decision_evidence"]
    lines = [
        f"# {EXPERIMENT_ID} Kova VCP Loss-Streak De-Risking Replay",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        payload["summary"],
        "",
        "## Aggregate",
        "",
        f"- Before PnL: `{payload['before_metrics']['total_pnl']}`.",
        f"- After PnL: `{payload['after_metrics']['total_pnl']}`.",
        f"- Delta PnL: `{payload['delta_metrics']['total_pnl']}`.",
        f"- Delta EV proxy: `{payload['delta_metrics']['expected_value_proxy']}`.",
        f"- Drawdown delta: `{payload['delta_metrics']['max_drawdown_pnl']}`.",
        f"- Scaled trades: `{loss['scaled_count']}`.",
        f"- Beneficial scaled trades: `{loss['beneficial_scaled_count']}`.",
        f"- Harmful scaled trades: `{loss['harmful_scaled_count']}`.",
        f"- Top positive delta ticker share: `{concentration['top_ticker_positive_delta_share']}`.",
        "",
        "## Windows",
        "",
        *_window_table(payload),
        "",
        "## Largest Scaled Trades",
        "",
        *_scaled_sample_table(payload),
        "",
        "## Gate 4",
        "",
        "```json",
        json.dumps(evidence, indent=2, sort_keys=True),
        "```",
        "",
        "## Repro",
        "",
        "```powershell",
        payload["repro_command"],
        "```",
        "",
        "## Related Files",
        "",
    ]
    lines.extend(f"- `{path}`" for path in payload["related_files"])
    lines.append("")
    return "\n".join(lines)


def _build_card(payload: dict[str, Any]) -> str:
    loss = payload["loss_streak_metrics"]
    lines = [
        "---",
        f'experiment_id: "{EXPERIMENT_ID}"',
        f'experiment_uid: "{_existing_ticket().get("experiment_uid")}"',
        f'status: "{payload["status"]}"',
        'lane: "alpha_discovery"',
        'change_type: "closed_ledger_capital_allocation_shadow_replay"',
        'mechanism_family: "kova_vcp_operator_risk_allocation"',
        f'trial_family: "{TRIAL_FAMILY}"',
        f'trial_variant_id: "{TRIAL_VARIANT_ID}"',
        f'changed_variable: "{CHANGED_VARIABLE}"',
        'new_evidence_type: "closed_paper_ledger_state_replay"',
        f'updated_at: "{payload["created_at"]}"',
        'hub_repo_id: "ginger/experiments/exp-20260529-025"',
        "---",
        "",
        f"# Experiment Card: {EXPERIMENT_ID}",
        "",
        "## Summary",
        "",
        payload["summary"],
        "",
        "## Decision",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Scaled trades: `{loss['scaled_count']}`",
        f"- Delta PnL: `{payload['delta_metrics']['total_pnl']}`",
        f"- Delta EV proxy: `{payload['delta_metrics']['expected_value_proxy']}`",
        f"- Drawdown delta: `{payload['delta_metrics']['max_drawdown_pnl']}`",
        "",
        "## Reserved Files",
        "",
    ]
    lines.extend(f"- `{path}`" for path in payload["related_files"])
    lines.append("")
    return "\n".join(lines)


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    experiment_id = str(payload.get("experiment_id") or EXPERIMENT_ID)
    line = json.dumps(_safe(_log_payload(payload)), ensure_ascii=True, sort_keys=True)
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
            if row.get("experiment_id") == experiment_id:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _existing_ticket() -> dict[str, Any]:
    if not TICKET_JSON.exists():
        return {}
    try:
        return _load_json(TICKET_JSON)
    except json.JSONDecodeError:
        return {}


def _update_registry(payload: dict[str, Any], ticket: dict[str, Any]) -> None:
    if EXPERIMENT_REGISTRY.exists():
        registry = _load_json(EXPERIMENT_REGISTRY)
    else:
        registry = {"schema_version": 1, "experiments": []}
    experiments = registry.setdefault("experiments", [])
    row = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "lane": payload["registry_lane"],
        "owner": ticket.get("owner") or "codex",
        "hypothesis": payload["alpha_hypothesis"],
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "log_file": _repo_rel(LOG_JSON),
        "updated_at": payload["created_at"],
        "result": {
            "decision": payload["decision"],
            "artifact": _repo_rel(ARTIFACT_MD),
            "json": _repo_rel(OUT_JSON),
            "summary": payload["summary"],
        },
    }
    replaced = False
    for idx, item in enumerate(experiments):
        if isinstance(item, dict) and item.get("experiment_id") == EXPERIMENT_ID:
            experiments[idx] = {**item, **row}
            replaced = True
            break
    if not replaced:
        experiments.append(row)
    registry["updated_at"] = payload["created_at"]
    _write_json(EXPERIMENT_REGISTRY, registry)


def _save_manifest(ticket: dict[str, Any]) -> None:
    scripts_dir = REPO_ROOT / "scripts"
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from scripts.experiment_registry import save_revision_manifest  # noqa: PLC0415

    save_revision_manifest(
        ticket,
        repo_root=REPO_ROOT,
        ticket_file=TICKET_JSON,
        card_file=CARD_MD,
        overwrite=True,
    )


def _persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, _log_payload(payload))
    existing = _existing_ticket()
    ticket = {
        **existing,
        "artifact_file": _repo_rel(OUT_JSON),
        "baseline_result_file": _repo_rel(SOURCE_EXP007_JSON),
        "change_type": payload["change_type"],
        "completed_at": payload["created_at"],
        "decision": payload["decision"],
        "experiment_id": EXPERIMENT_ID,
        "experiment_uid": existing.get("experiment_uid") or "expuid-ff9053a6fe52441f",
        "hypothesis": payload["alpha_hypothesis"],
        "lane": payload["lane"],
        "mechanism_family": payload["mechanism_family"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "new_evidence_type": payload["new_evidence_type"],
        "owner": existing.get("owner") or "codex",
        "prior_trial_count": payload["prior_trial_count"],
        "result_file": _repo_rel(LOG_JSON),
        "report_file": _repo_rel(ARTIFACT_MD),
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "status": payload["status"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "updated_at": payload["created_at"],
        "allowed_write_scope": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_DIR),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(DOCS_TICKET_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(EXPERIMENT_REGISTRY),
            "docs/kova-research-directions.md",
            "docs/alpha-optimization-playbook.md",
            "docs/current_state.md",
            "docs/data_edge_context_layers.md",
        ],
        "locked_variables": [CHANGED_VARIABLE],
        "acceptance_rule": (
            "Candidate only if aggregate EV proxy and PnL improve versus the "
            "accepted VCP source, at least 10 trades are scaled, no more than "
            "one canonical window regresses on EV proxy/PnL, drawdown proxy "
            "does not worsen, and positive delta is not concentrated above 50 "
            "percent in one ticker."
        ),
        "prediction": payload["prediction"],
        "result": {
            "decision": payload["decision"],
            "summary": payload["summary"],
            "artifact": _repo_rel(ARTIFACT_MD),
            "json": _repo_rel(OUT_JSON),
        },
        "summary": payload["summary"],
        "artifacts": payload["artifacts"],
        "repro_command": payload["repro_command"],
    }
    _write_json(TICKET_JSON, ticket)
    _write_json(DOCS_TICKET_JSON, ticket)
    _write_text(CARD_MD, _build_card(payload))
    _write_text(ARTIFACT_MD, _build_report(payload))
    _upsert_jsonl(EXPERIMENT_LOG, payload)
    _update_registry(payload, ticket)
    _save_manifest(ticket)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-persist", action="store_true")
    args = parser.parse_args()

    payload = _build_payload()
    if not args.no_persist:
        _persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "status": payload["status"],
                "aggregate": {
                    "before": payload["before_metrics"],
                    "after": payload["after_metrics"],
                    "delta": payload["delta_metrics"],
                },
                "loss_streak": payload["loss_streak_metrics"],
                "gate4": payload["gate4"],
                "artifact": payload["artifacts"]["markdown"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
