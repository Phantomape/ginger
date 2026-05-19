"""Replay single-owner Form 4 events with 5d pre-entry RS confirmation.

This alpha-search experiment keeps the core stack and the existing Form 4
forward-queue threshold fixed. It changes one event-quality variable on top of
the latest single-owner replay: a selected single-owner event must have
positive 5-trading-day pre-entry excess return versus SPY.
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

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
from experiments.exp_20260504_034_form4_satellite_overlay import (  # noqa: E402
    EVENT_NOTIONAL,
    HOLD_DAYS,
    MAX_EVENT_POSITIONS,
    ROUND_TRIP_COST_PCT,
    WINDOWS,
    _candidate_trade,
    _combined_metrics,
    _core_metrics,
    _delta,
    _event_equity_curve,
    _gate4,
    _load_price_map,
    _pnl_from_trade,
    _repo_rel,
    _select_event_trades,
    _write_json,
)
from experiments.exp_20260512_901_form4_single_owner_forward_queue import (  # noqa: E402
    FORM4_TRANSACTIONS_PATH,
    _load_forward_events,
    _position_field_check,
    _single_owner,
)
from form4_event_queue import (  # noqa: E402
    FORWARD_QUEUE_MIN_PURCHASE_VALUE,
    QUEUE_NAME,
    RULE_VERSION,
)


EXP_ID = "exp-20260512-108"
STEM = "form4_single_owner_preentry_rs"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
LOOKBACK_DAYS = 5


def _date10(value: Any) -> str:
    return str(value or "")[:10]


def _idx_before(rows: list[dict[str, Any]], date_value: str) -> int | None:
    out: int | None = None
    for idx, row in enumerate(rows):
        row_date = str(row.get("date") or "")[:10]
        if row_date and row_date < date_value:
            out = idx
        if row_date >= date_value:
            break
    return out


def _preentry_excess_return(
    *,
    ticker: str,
    entry_date: str,
    prices: dict[str, list[dict[str, Any]]],
    lookback_days: int = LOOKBACK_DAYS,
) -> float | None:
    rows = prices.get(str(ticker).upper()) or []
    spy_rows = prices.get("SPY") or []
    ticker_idx = _idx_before(rows, entry_date)
    spy_idx = _idx_before(spy_rows, entry_date)
    if (
        ticker_idx is None
        or spy_idx is None
        or ticker_idx - lookback_days < 0
        or spy_idx - lookback_days < 0
    ):
        return None
    ticker_start = rows[ticker_idx - lookback_days].get("close")
    ticker_end = rows[ticker_idx].get("close")
    spy_start = spy_rows[spy_idx - lookback_days].get("close")
    spy_end = spy_rows[spy_idx].get("close")
    if not ticker_start or not ticker_end or not spy_start or not spy_end:
        return None
    return (float(ticker_end) / float(ticker_start) - 1.0) - (
        float(spy_end) / float(spy_start) - 1.0
    )


def _single_owner_candidates(
    prices: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    events = [event for event in _load_forward_events() if _single_owner(event)]
    candidates = [_candidate_trade(event, prices) for event in events]
    out: list[dict[str, Any]] = []
    for candidate in candidates:
        entry_date = _date10(candidate.get("entry_date") or candidate.get("usable_trade_date"))
        excess = None
        status = "not_price_ready"
        if candidate.get("status") == "price_ready":
            excess = _preentry_excess_return(
                ticker=str(candidate.get("ticker") or ""),
                entry_date=entry_date,
                prices=prices,
            )
            status = "ready" if excess is not None else "missing_preentry_history"
        out.append(
            {
                **candidate,
                "preentry_rs_status": status,
                "preentry_lookback_days": LOOKBACK_DAYS,
                "preentry_excess_return_5d": round(excess, 6) if excess is not None else None,
                "preentry_rs_confirmed": bool(excess is not None and excess > 0.0),
            }
        )
    return out


def _aggregate_delta(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    before_ev = sum(float(row.get("expected_value_score") or 0.0) for row in before.values())
    after_ev = sum(float(row.get("expected_value_score") or 0.0) for row in after.values())
    before_pnl = sum(float(row.get("total_pnl") or 0.0) for row in before.values())
    after_pnl = sum(float(row.get("total_pnl") or 0.0) for row in after.values())
    return {
        "before_ev_sum": round(before_ev, 4),
        "after_ev_sum": round(after_ev, 4),
        "aggregate_ev_delta": round(after_ev - before_ev, 4),
        "aggregate_ev_delta_pct": round((after_ev - before_ev) / before_ev, 6) if before_ev else None,
        "before_pnl_sum": round(before_pnl, 2),
        "after_pnl_sum": round(after_pnl, 2),
        "aggregate_pnl_delta": round(after_pnl - before_pnl, 2),
        "aggregate_pnl_delta_pct": round((after_pnl - before_pnl) / before_pnl, 6) if before_pnl else None,
        "windows_ev_improved": sum(
            1
            for label in before
            if float(after[label].get("expected_value_score") or 0.0)
            > float(before[label].get("expected_value_score") or 0.0)
        ),
        "windows_ev_regressed": sum(
            1
            for label in before
            if float(after[label].get("expected_value_score") or 0.0)
            < float(before[label].get("expected_value_score") or 0.0)
        ),
        "windows_pnl_improved": sum(
            1
            for label in before
            if float(after[label].get("total_pnl") or 0.0)
            > float(before[label].get("total_pnl") or 0.0)
        ),
        "windows_pnl_regressed": sum(
            1
            for label in before
            if float(after[label].get("total_pnl") or 0.0)
            < float(before[label].get("total_pnl") or 0.0)
        ),
    }


def _single_ticker_positive_share(details: dict[str, dict[str, Any]]) -> float | None:
    by_ticker: defaultdict[str, float] = defaultdict(float)
    for detail in details.values():
        for trade in detail.get("confirmed_selected_trades") or []:
            pnl = float(trade.get("pnl") or 0.0)
            if pnl > 0:
                by_ticker[str(trade.get("ticker") or "").upper()] += pnl
    total = sum(by_ticker.values())
    if total <= 0:
        return None
    return round(max(by_ticker.values()) / total, 4)


def _risk_distribution(
    result: dict[str, Any],
    event_trades: list[dict[str, Any]],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for trade in result.get("trades") or []:
        rows.append(
            {
                "exit_date": _date10(trade.get("exit_date") or trade.get("entry_date")),
                "pnl": _pnl_from_trade(trade),
                "return_pct": trade.get("pnl_pct_net") or trade.get("return_pct"),
            }
        )
    for trade in event_trades:
        rows.append(
            {
                "exit_date": _date10(trade.get("exit_date")),
                "pnl": float(trade.get("pnl") or 0.0),
                "return_pct": float(trade.get("net_return_pct") or 0.0) / 100.0,
            }
        )
    rows.sort(key=lambda row: row["exit_date"])
    streak = 0
    max_streak = 0
    for row in rows:
        if float(row.get("pnl") or 0.0) < 0:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
    pct_values = [
        float(row["return_pct"])
        for row in rows
        if row.get("return_pct") not in (None, "")
        and math.isfinite(float(row.get("return_pct") or 0.0))
    ]
    losses = sorted([-float(row.get("pnl") or 0.0) for row in rows if float(row.get("pnl") or 0.0) < 0], reverse=True)
    total_loss = sum(losses)
    return {
        "worst_trade_pct": round(min(pct_values), 6) if pct_values else result.get("worst_trade_pct"),
        "max_consecutive_losses": max_streak or result.get("max_consecutive_losses"),
        "tail_loss_share": round(sum(losses[:3]) / total_loss, 6) if total_loss > 0 else None,
        "event_worst_trade_pct": round(
            min((float(trade.get("net_return_pct") or 0.0) / 100.0 for trade in event_trades), default=0.0),
            6,
        ),
    }


def _gate_result(
    core_delta: dict[str, Any],
    single_owner_delta: dict[str, Any],
    core_gate_by_window: dict[str, dict[str, Any]],
    single_owner_gate_by_window: dict[str, dict[str, Any]],
    details: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    selected = sum(int(row.get("confirmed_selected_trade_count") or 0) for row in details.values())
    single_share = _single_ticker_positive_share(details)
    material_vs_core = (
        core_delta["aggregate_ev_delta_pct"] is not None
        and core_delta["aggregate_ev_delta_pct"] > 0.10
    ) or (
        core_delta["aggregate_pnl_delta_pct"] is not None
        and core_delta["aggregate_pnl_delta_pct"] > 0.05
    )
    improves_single_owner = (
        single_owner_delta["aggregate_ev_delta"] > 0.0
        and single_owner_delta["aggregate_pnl_delta"] > 0.0
        and single_owner_delta["windows_ev_regressed"] == 0
    )
    no_core_ev_regression = core_delta["windows_ev_regressed"] == 0
    sample_ok = selected >= 8 and (single_share is None or single_share <= 0.50)
    return {
        "passed": bool(material_vs_core and no_core_ev_regression and improves_single_owner and sample_ok),
        "material_vs_core": bool(material_vs_core),
        "no_core_ev_regression": bool(no_core_ev_regression),
        "improves_vs_single_owner": bool(improves_single_owner),
        "confirmed_selected_event_trades": selected,
        "sample_guard_min_trades": 8,
        "single_ticker_positive_share": single_share,
        "single_ticker_positive_share_guard": "<= 0.50",
        "sample_guard_passed": bool(sample_ok),
        "by_window_vs_core": core_gate_by_window,
        "by_window_vs_single_owner": single_owner_gate_by_window,
    }


def _append_experiment_log(payload: dict[str, Any]) -> None:
    compact = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    if EXPERIMENT_LOG.exists():
        lines = EXPERIMENT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        lines = [
            line
            for line in lines
            if f'"experiment_id":"{EXP_ID}"' not in line
            and f'"experiment_id": "{EXP_ID}"' not in line
        ]
        lines.append(compact)
        EXPERIMENT_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return
    EXPERIMENT_LOG.write_text(compact + "\n", encoding="utf-8")


def _write_report(payload: dict[str, Any]) -> None:
    lines = [
        "# Form 4 Single-Owner Pre-Entry RS",
        "",
        f"- experiment_id: `{payload['experiment_id']}`",
        f"- timestamp: `{payload['timestamp']}`",
        f"- decision: `{payload['decision']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Three-Window Results",
        "",
        "| Window | Core EV | Single-owner EV | Confirmed EV | Delta vs single | Delta vs core | Core PnL | Confirmed PnL | Event PnL | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        core = payload["core_baseline_metrics"][label]
        before = payload["single_owner_baseline_metrics"][label]
        after = payload["after_metrics"][label]
        single_delta = payload["deltas_vs_single_owner"][label]
        core_delta = payload["deltas_vs_core"][label]
        lines.append(
            f"| {label} | {core['expected_value_score']} | {before['expected_value_score']} | "
            f"{after['expected_value_score']} | {single_delta['expected_value_score']} | "
            f"{core_delta['expected_value_score']} | ${core['total_pnl']:,.2f} | "
            f"${after['total_pnl']:,.2f} | ${float(after.get('event_pnl') or 0.0):,.2f} | "
            f"{core['trade_count']} -> {after['trade_count']} |"
        )
    lines.extend(
        [
            "",
            "## Aggregate Vs Single-Owner",
            "",
            "```json",
            json.dumps(payload["aggregate_delta_vs_single_owner"], indent=2, sort_keys=True),
            "```",
            "",
            "## Aggregate Vs Core",
            "",
            "```json",
            json.dumps(payload["aggregate_delta_vs_core"], indent=2, sort_keys=True),
            "```",
            "",
            "## Gate",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Decision",
            "",
            payload["decision_rationale"],
            "",
            "## Production Impact",
            "",
            json.dumps(payload["production_impact"], indent=2, sort_keys=True),
            "",
        ]
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_ticket(payload: dict[str, Any]) -> None:
    ticket = {
        "experiment_id": EXP_ID,
        "title": "Form 4 single-owner pre-entry RS",
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": payload["lane"],
        "mechanism_family": payload["mechanism_family"],
        "created_at": payload["timestamp"],
        "completed_at": payload["timestamp"],
        "result": {
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "report": _repo_rel(ARTIFACT_MD),
            "aggregate_delta_vs_core": payload["aggregate_delta_vs_core"],
            "aggregate_delta_vs_single_owner": payload["aggregate_delta_vs_single_owner"],
            "decision": payload["decision"],
        },
    }
    _write_json(TICKET_JSON, ticket)


def build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    universe = get_universe()
    prices = _load_price_map()
    candidates = _single_owner_candidates(prices)
    confirmed_candidates = [row for row in candidates if bool(row.get("preentry_rs_confirmed"))]

    core_baseline: dict[str, dict[str, Any]] = OrderedDict()
    single_owner_metrics: dict[str, dict[str, Any]] = OrderedDict()
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    deltas_vs_single_owner: dict[str, dict[str, Any]] = OrderedDict()
    deltas_vs_core: dict[str, dict[str, Any]] = OrderedDict()
    gate_vs_core: dict[str, dict[str, Any]] = OrderedDict()
    gate_vs_single_owner: dict[str, dict[str, Any]] = OrderedDict()
    risk_distribution: dict[str, dict[str, Any]] = OrderedDict()
    details: dict[str, dict[str, Any]] = OrderedDict()

    for label, window in WINDOWS.items():
        result = BacktestEngine(
            universe,
            start=window["start"],
            end=window["end"],
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=window["snapshot"],
        ).run()
        single_selected, single_skipped = _select_event_trades(
            candidates,
            start=window["start"],
            end=window["end"],
        )
        confirmed_selected, confirmed_skipped = _select_event_trades(
            confirmed_candidates,
            start=window["start"],
            end=window["end"],
        )
        single_curve = _event_equity_curve(
            single_selected,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        confirmed_curve = _event_equity_curve(
            confirmed_selected,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        core_baseline[label] = _core_metrics(result)
        single_owner_metrics[label] = (
            _combined_metrics(result, single_curve, single_selected)
            if single_selected
            else dict(core_baseline[label])
        )
        after_metrics[label] = (
            _combined_metrics(result, confirmed_curve, confirmed_selected)
            if confirmed_selected
            else dict(core_baseline[label])
        )
        deltas_vs_single_owner[label] = _delta(single_owner_metrics[label], after_metrics[label])
        deltas_vs_core[label] = _delta(core_baseline[label], after_metrics[label])
        gate_vs_core[label] = _gate4(core_baseline[label], after_metrics[label])
        gate_vs_single_owner[label] = _gate4(single_owner_metrics[label], after_metrics[label])
        risk_distribution[label] = {
            "core": {
                "worst_trade_pct": result.get("worst_trade_pct"),
                "max_consecutive_losses": result.get("max_consecutive_losses"),
                "tail_loss_share": result.get("tail_loss_share"),
            },
            "after": _risk_distribution(result, confirmed_selected),
        }

        scoped = [
            row
            for row in candidates
            if window["start"] <= _date10(row.get("usable_trade_date")) <= window["end"]
        ]
        details[label] = {
            "single_owner_event_count": len(scoped),
            "preentry_ready_count": sum(1 for row in scoped if row.get("preentry_rs_status") == "ready"),
            "preentry_confirmed_event_count": sum(1 for row in scoped if row.get("preentry_rs_confirmed")),
            "preentry_rejected_event_count": sum(
                1
                for row in scoped
                if row.get("preentry_rs_status") == "ready" and not row.get("preentry_rs_confirmed")
            ),
            "preentry_status_counts": dict(
                sorted(
                    {
                        status: sum(1 for row in scoped if row.get("preentry_rs_status") == status)
                        for status in {row.get("preentry_rs_status") for row in scoped}
                    }.items()
                )
            ),
            "single_owner_selected_trade_count": len(single_selected),
            "confirmed_selected_trade_count": len(confirmed_selected),
            "single_owner_skipped_count": len(single_skipped),
            "confirmed_skipped_count": len(confirmed_skipped),
            "confirmed_selected_trades": confirmed_selected,
            "single_owner_selected_trades": single_selected,
            "confirmed_skipped_candidates": confirmed_skipped[:20],
        }

    aggregate_vs_single = _aggregate_delta(single_owner_metrics, after_metrics)
    aggregate_vs_core = _aggregate_delta(core_baseline, after_metrics)
    gate = _gate_result(
        aggregate_vs_core,
        aggregate_vs_single,
        gate_vs_core,
        gate_vs_single_owner,
        details,
    )

    if gate["passed"]:
        decision = "accepted_default_off_form4_single_owner_preentry_rs"
        status = "accepted_default_off"
        rationale = (
            "Single-owner Form 4 events with 5d pre-entry relative-strength confirmation "
            "improved the prior single-owner replay and cleared the core materiality, "
            "sample, and concentration gates. Promotion would still require shared "
            "default-off queue/sleeve wiring before any trade-enabled use."
        )
    elif (
        aggregate_vs_core["aggregate_ev_delta"] > 0
        and aggregate_vs_core["aggregate_pnl_delta"] > 0
        and aggregate_vs_core["windows_ev_regressed"] == 0
    ):
        decision = "rejected_positive_vs_core_but_not_single_owner"
        status = "rejected"
        rationale = (
            "The 5d pre-entry RS qualifier stayed positive versus core but failed to "
            "improve the latest single-owner Form 4 baseline enough to justify a new "
            "event qualification rule."
        )
    else:
        decision = "rejected_form4_single_owner_preentry_rs"
        status = "rejected"
        rationale = (
            "The 5d pre-entry RS qualifier introduced EV/PnL regression or insufficient "
            "sample versus the canonical three-window baselines."
        )

    payload: dict[str, Any] = {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": (
            "PIT-safe single-owner Form 4 forward-queue events may be higher-quality "
            "when the ticker already outperformed SPY over the 5 trading days before "
            "the paper entry; this can separate informed accumulation from stale "
            "insider purchases without adding noisy tickers or LLM ranking."
        ),
        "change_type": "event_qualification_replay",
        "mechanism_family": "form4_single_owner_insider_buy_event_satellite",
        "single_causal_variable": "positive 5-trading-day pre-entry ticker excess return versus SPY for single-owner Form 4 events",
        "gate_questions": {
            "alpha_hypothesis": "Entry/candidate overlay: Form 4 single-owner event quality via PIT-safe pre-entry relative strength.",
            "prior_similar_experiments": [
                "exp-20260512-901: single-owner Form 4 positive in 3/3 windows but not material.",
                "exp-20260512-017: clustered Form 4 + 1-session pre-entry RS positive but not material.",
                "exp-20260507-022: broad event-bundle 5d pre-entry momentum tilt rejected versus full bundle.",
            ],
            "single_causal_variable": "Only the pre-entry RS confirmation is added; owner_count, purchase threshold, event notional, capacity, holding period, core stack, and LLM/news remain locked.",
            "acceptance_standard": "Must beat the single-owner baseline and core under docs/backtesting.md three windows, with no core EV regression and sample/concentration guards.",
            "reproducibility": "This script reruns core, single-owner, and confirmed single-owner overlays across the three fixed snapshots.",
        },
        "parameters": {
            "queue_name": QUEUE_NAME,
            "rule_version": RULE_VERSION,
            "forward_queue_min_total_purchase_value": FORWARD_QUEUE_MIN_PURCHASE_VALUE,
            "owner_count_required": 1,
            "preentry_rs_lookback_trading_days": LOOKBACK_DAYS,
            "preentry_rs_threshold_excess_vs_spy": "> 0.0",
            "event_notional_usd": EVENT_NOTIONAL,
            "max_event_positions": MAX_EVENT_POSITIONS,
            "hold_days": HOLD_DAYS,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "fields_checked": [
                "Form 4 ticker",
                "Form 4 usable_trade_date",
                "Form 4 total_purchase_value",
                "Form 4 owner_count",
                "ticker OHLCV close before entry_date",
                "SPY OHLCV close before entry_date",
            ],
            "locked_variables": [
                "core universe",
                "core signal generation",
                "core candidate ranking",
                "core position sizing",
                "core exits",
                "core add-ons",
                "LLM/news replay settings",
                "Form 4 transaction parser",
                "Form 4 purchase-value threshold",
                "Form 4 owner-count qualifier",
                "event notional",
                "event holding period",
                "event capacity",
            ],
        },
        "date_range": {label: f"{window['start']} -> {window['end']}" for label, window in WINDOWS.items()},
        "backtest_protocol": "docs/backtesting.md canonical three fixed windows",
        "market_regime_summary": {label: window["state_note"] for label, window in WINDOWS.items()},
        "gate1": {
            "protocol": "docs/backtesting.md canonical three fixed windows",
            "core_baseline_metrics": core_baseline,
            "single_owner_baseline_metrics": single_owner_metrics,
        },
        "gate2": _position_field_check(),
        "gate3": {
            "new_core_filter_added": False,
            "min_survival_rate": min(float(row.get("survival_rate") or 0.0) for row in core_baseline.values()),
            "passed": min(float(row.get("survival_rate") or 0.0) for row in core_baseline.values()) >= 0.05,
        },
        "core_baseline_metrics": core_baseline,
        "single_owner_baseline_metrics": single_owner_metrics,
        "after_metrics": after_metrics,
        "deltas_vs_single_owner": deltas_vs_single_owner,
        "deltas_vs_core": deltas_vs_core,
        "aggregate_delta_vs_single_owner": aggregate_vs_single,
        "aggregate_delta_vs_core": aggregate_vs_core,
        "gate4": gate,
        "risk_distribution": risk_distribution,
        "event_details": details,
        "decision_rationale": rationale,
        "expected_value_score_delta": {label: deltas_vs_core[label]["expected_value_score"] for label in WINDOWS},
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": "LLM soft-ranking remains sample-limited; this tests replayable PIT-safe Form 4 and OHLCV metadata.",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": True,
            "production_signal_path_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "live_slots_changed": False,
            "promotion_blocker_if_positive": (
                "A shared default-off Form 4 pre-entry RS queue/paper adapter must be "
                "wired in run.py and replay before any trade-enabled promotion."
            ),
        },
        "data_source": {
            "form4_transactions_path": _repo_rel(FORM4_TRANSACTIONS_PATH),
            "pit_status": "uses Form 4 usable_trade_date and OHLCV closes before paper entry",
        },
        "related_files": [
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(Path(__file__)),
        ],
    }
    return payload


def main() -> None:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_ticket(payload)
    _write_report(payload)
    _append_experiment_log(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXP_ID,
                "decision": payload["decision"],
                "aggregate_delta_vs_single_owner": payload["aggregate_delta_vs_single_owner"],
                "aggregate_delta_vs_core": payload["aggregate_delta_vs_core"],
                "gate4": {
                    key: payload["gate4"][key]
                    for key in (
                        "passed",
                        "material_vs_core",
                        "no_core_ev_regression",
                        "improves_vs_single_owner",
                        "confirmed_selected_event_trades",
                        "sample_guard_passed",
                        "single_ticker_positive_share",
                    )
                },
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
