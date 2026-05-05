"""exp-20260504-010 deterministic SEC event-sleeve backtest.

This upgrades the shadow-promising exp-20260504-008 packet into a small
portfolio-level event-sleeve simulation. It does not change production entries,
ranking, sizing, exits, or the core backtester.
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
DATA_DIR = REPO_ROOT / "data"
DOCS_DIR = REPO_ROOT / "docs"

if str(REPO_ROOT / "quant") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "quant"))

from constants import ROUND_TRIP_COST_PCT  # noqa: E402
from experiments.exp_20260504_008_sec_negative_reaction_absorption import (  # noqa: E402
    BASELINE_METRICS,
    SNAPSHOT_FILES,
    TEXT_PATH,
    WINDOWS,
    evaluate_price,
    language_features,
    load_snapshot,
    reaction_bucket,
    window_for_date,
)


EXPERIMENT_ID = "exp-20260504-010"
OUT_DIR = DATA_DIR / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "sec_event_sleeve_backtest.json"
LOG_JSON = DOCS_DIR / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = DOCS_DIR / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REPORT_MD = DOCS_DIR / "non_ohlcv_data_audit" / "sec_event_sleeve_backtest_20260504.md"
EXPERIMENT_LOG = DOCS_DIR / "experiment_log.jsonl"

INITIAL_CAPITAL = 100_000.0
PRIMARY_HORIZON = 10
PRIMARY_MAX_POSITIONS = 1
HORIZONS = (10, 20)
MAX_POSITIONS_VARIANTS = (1, 2)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_safe(payload), indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _safe(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {key: _safe(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_safe(value) for value in payload]
    if isinstance(payload, float) and not math.isfinite(payload):
        return None
    return payload


def _round(value: float | None, digits: int = 6) -> float | None:
    return None if value is None else round(value, digits)


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(value).replace("\\", "/")


def _merge_snapshots(snapshot_map: dict[str, dict[str, list[dict[str, Any]]]]) -> dict[str, list[dict[str, Any]]]:
    by_ticker_date: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for snapshot in snapshot_map.values():
        for ticker, rows in snapshot.items():
            for row in rows:
                by_ticker_date[str(ticker).upper()][row["date"]] = dict(row)
    return {
        ticker: sorted(rows.values(), key=lambda item: item["date"])
        for ticker, rows in by_ticker_date.items()
    }


def _idx_on_or_after(rows: list[dict[str, Any]], target: str) -> int | None:
    for idx, row in enumerate(rows):
        if row["date"] >= target:
            return idx
    return None


def _row_by_date(price_map: dict[str, list[dict[str, Any]]], ticker: str, date_value: str) -> dict[str, Any] | None:
    for row in price_map.get(str(ticker).upper(), []):
        if row["date"] == date_value:
            return row
    return None


def _price_return(price_map: dict[str, list[dict[str, Any]]], ticker: str, start: str, end: str) -> float | None:
    start_row = _row_by_date(price_map, ticker, start)
    end_row = _row_by_date(price_map, ticker, end)
    if not start_row or not end_row:
        return None
    entry = start_row.get("open")
    close = end_row.get("close")
    if not entry or not close:
        return None
    return close / entry - 1.0


def build_primary_candidates() -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    text_rows = _load_jsonl(TEXT_PATH)
    snapshots = {label: load_snapshot(path) for label, path in SNAPSHOT_FILES.items()}
    candidates: list[dict[str, Any]] = []

    for row in text_rows:
        event = {**row, **language_features(row)}
        window = window_for_date(str(event.get("usable_trade_date") or ""))
        if not window:
            continue
        priced = evaluate_price(event, snapshots[window], window)
        priced["reaction_bucket"] = reaction_bucket(priced)
        reaction = priced.get("reaction_excess_return")
        if (
            priced.get("price_status") == "covered"
            and priced.get("language_bucket") == "negative_language"
            and isinstance(reaction, (int, float))
            and reaction < 0
        ):
            candidates.append(
                {
                    "ticker": str(priced.get("ticker") or "").upper(),
                    "window": priced.get("window"),
                    "accession_number": priced.get("accession_number"),
                    "usable_trade_date": priced.get("usable_trade_date"),
                    "reaction_date": priced.get("reaction_date"),
                    "entry_date": priced.get("entry_date"),
                    "reaction_excess_return": reaction,
                    "reaction_bucket": priced.get("reaction_bucket"),
                    "language_score": priced.get("language_score"),
                    "negative_phrase_hits": priced.get("negative_phrase_hits"),
                    "text_event_type": priced.get("text_event_type"),
                }
            )

    candidates.sort(key=lambda row: (row["entry_date"], row["reaction_excess_return"], row["ticker"]))
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for candidate in candidates:
        key = (candidate["ticker"], candidate["entry_date"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped, _merge_snapshots(snapshots)


def _equity_at_open(cash: float, positions: list[dict[str, Any]], price_map: dict[str, list[dict[str, Any]]], date_value: str) -> float:
    equity = cash
    for position in positions:
        row = _row_by_date(price_map, position["ticker"], date_value)
        price = row.get("open") if row else position.get("last_price")
        equity += position["shares"] * float(price or 0.0)
    return equity


def _equity_at_close(cash: float, positions: list[dict[str, Any]], price_map: dict[str, list[dict[str, Any]]], date_value: str) -> float:
    equity = cash
    for position in positions:
        row = _row_by_date(price_map, position["ticker"], date_value)
        price = row.get("close") if row else position.get("last_price")
        if price:
            position["last_price"] = price
        equity += position["shares"] * float(price or 0.0)
    return equity


def _max_drawdown(equity_curve: list[dict[str, Any]]) -> float | None:
    if not equity_curve:
        return None
    peak = equity_curve[0]["equity"]
    max_dd = 0.0
    for row in equity_curve:
        equity = row["equity"]
        if equity > peak:
            peak = equity
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak)
    return max_dd


def _daily_sharpe(equity_curve: list[dict[str, Any]]) -> float | None:
    returns: list[float] = []
    for prev, cur in zip(equity_curve, equity_curve[1:]):
        if prev["equity"] > 0:
            returns.append(cur["equity"] / prev["equity"] - 1.0)
    if len(returns) < 2:
        return None
    stdev = statistics.stdev(returns)
    if stdev <= 0:
        return None
    return statistics.mean(returns) / stdev * math.sqrt(252)


def _distribution(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "avg": None, "median": None, "min": None, "max": None, "win_rate": None}
    return {
        "count": len(values),
        "avg": _round(statistics.mean(values)),
        "median": _round(statistics.median(values)),
        "min": _round(min(values)),
        "max": _round(max(values)),
        "win_rate": _round(sum(1 for value in values if value > 0) / len(values), 4),
    }


def _summarize_trades(trades: list[dict[str, Any]]) -> dict[str, Any]:
    net_returns = [trade["net_return_pct"] for trade in trades]
    winners = [trade["pnl"] for trade in trades if trade["pnl"] > 0]
    losers = [trade["pnl"] for trade in trades if trade["pnl"] < 0]
    total_pnl = sum(trade["pnl"] for trade in trades)
    top_trade = max(trades, key=lambda trade: trade["pnl"], default=None)
    by_window: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        by_window[str(trade.get("window") or "unknown")].append(trade)
    return {
        "net_return_distribution": _distribution(net_returns),
        "gross_return_distribution": _distribution([trade["gross_return_pct"] for trade in trades]),
        "profit_factor": _round(sum(winners) / abs(sum(losers)) if losers else None),
        "top_trade_concentration": {
            "ticker": top_trade.get("ticker") if top_trade else None,
            "pnl": _round(top_trade["pnl"], 2) if top_trade else None,
            "share_of_total_pnl": _round(top_trade["pnl"] / total_pnl, 4) if top_trade and total_pnl else None,
            "total_pnl_without_top_trade": _round(total_pnl - top_trade["pnl"], 2) if top_trade else None,
        },
        "by_window": {
            label: {
                "trade_count": len(rows),
                "net_return_distribution": _distribution([row["net_return_pct"] for row in rows]),
                "total_pnl": _round(sum(row["pnl"] for row in rows), 2),
            }
            for label, rows in sorted(by_window.items())
        },
    }


def simulate_sleeve(
    candidates: list[dict[str, Any]],
    price_map: dict[str, list[dict[str, Any]]],
    *,
    holding_days: int,
    max_positions: int,
    initial_capital: float = INITIAL_CAPITAL,
    round_trip_cost_pct: float = ROUND_TRIP_COST_PCT,
) -> dict[str, Any]:
    trading_dates = [row["date"] for row in price_map.get("SPY", [])]
    candidates_by_entry: dict[str, list[dict[str, Any]]] = defaultdict(list)
    skipped: list[dict[str, Any]] = []
    for candidate in candidates:
        entry_date = str(candidate.get("entry_date") or "")
        if entry_date:
            candidates_by_entry[entry_date].append(candidate)
    for rows in candidates_by_entry.values():
        rows.sort(key=lambda row: (row.get("reaction_excess_return", 0), row.get("ticker", "")))

    cash = float(initial_capital)
    active: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []
    equity_curve: list[dict[str, Any]] = []

    for date_value in trading_dates:
        day_candidates = candidates_by_entry.get(date_value) or []
        for candidate in day_candidates:
            if any(position["ticker"] == candidate["ticker"] for position in active):
                skipped.append({**candidate, "skip_reason": "ticker_already_active"})
                continue
            if len(active) >= max_positions:
                skipped.append({**candidate, "skip_reason": "slot_full"})
                continue
            ticker_rows = price_map.get(candidate["ticker"]) or []
            entry_idx = _idx_on_or_after(ticker_rows, date_value)
            if entry_idx is None:
                skipped.append({**candidate, "skip_reason": "missing_entry_price"})
                continue
            exit_idx = entry_idx + holding_days - 1
            if exit_idx >= len(ticker_rows):
                skipped.append({**candidate, "skip_reason": "insufficient_forward_days"})
                continue
            entry_row = ticker_rows[entry_idx]
            exit_row = ticker_rows[exit_idx]
            entry_price = entry_row.get("open")
            if not entry_price or entry_price <= 0:
                skipped.append({**candidate, "skip_reason": "missing_entry_price"})
                continue
            equity_open = _equity_at_open(cash, active, price_map, date_value)
            notional = min(cash, equity_open / max_positions)
            if notional <= 0:
                skipped.append({**candidate, "skip_reason": "no_cash"})
                continue
            shares = notional / entry_price
            cash -= notional
            active.append(
                {
                    **candidate,
                    "entry_price": entry_price,
                    "entry_notional": notional,
                    "shares": shares,
                    "planned_exit_date": exit_row["date"],
                    "planned_exit_idx": exit_idx,
                    "last_price": entry_price,
                }
            )

        remaining: list[dict[str, Any]] = []
        for position in active:
            if position["planned_exit_date"] != date_value:
                remaining.append(position)
                continue
            exit_row = _row_by_date(price_map, position["ticker"], date_value)
            exit_price = exit_row.get("close") if exit_row else None
            if not exit_price:
                remaining.append(position)
                continue
            gross_proceeds = position["shares"] * exit_price
            net_proceeds = gross_proceeds * (1.0 - round_trip_cost_pct)
            pnl = net_proceeds - position["entry_notional"]
            gross_return = exit_price / position["entry_price"] - 1.0
            net_return = net_proceeds / position["entry_notional"] - 1.0
            cash += net_proceeds
            trades.append(
                {
                    "ticker": position["ticker"],
                    "window": position.get("window"),
                    "accession_number": position.get("accession_number"),
                    "entry_date": position["entry_date"],
                    "exit_date": date_value,
                    "holding_days": holding_days,
                    "entry_price": _round(position["entry_price"], 4),
                    "exit_price": _round(exit_price, 4),
                    "entry_notional": _round(position["entry_notional"], 2),
                    "pnl": _round(pnl, 2),
                    "gross_return_pct": _round(gross_return, 6),
                    "net_return_pct": _round(net_return, 6),
                    "reaction_excess_return": position.get("reaction_excess_return"),
                    "reaction_bucket": position.get("reaction_bucket"),
                    "language_score": position.get("language_score"),
                    "negative_phrase_hits": position.get("negative_phrase_hits"),
                }
            )
        active = remaining
        equity = _equity_at_close(cash, active, price_map, date_value)
        equity_curve.append({"date": date_value, "equity": _round(equity, 2), "active_positions": len(active)})

    final_equity = equity_curve[-1]["equity"] if equity_curve else initial_capital
    total_return = final_equity / initial_capital - 1.0
    sharpe = _daily_sharpe(equity_curve)
    max_dd = _max_drawdown(equity_curve)
    exposure_days = sum(1 for row in equity_curve if row["active_positions"] > 0)
    return {
        "holding_days": holding_days,
        "max_positions": max_positions,
        "initial_capital": initial_capital,
        "final_equity": _round(final_equity, 2),
        "total_pnl": _round(final_equity - initial_capital, 2),
        "total_return_pct": _round(total_return, 6),
        "sharpe_daily": _round(sharpe, 4),
        "expected_value_score": _round(total_return * sharpe if sharpe is not None else None, 6),
        "max_drawdown_pct": _round(max_dd, 6),
        "trade_count": len(trades),
        "win_rate": _round(sum(1 for trade in trades if trade["pnl"] > 0) / len(trades), 4) if trades else None,
        "exposure_days": exposure_days,
        "exposure_rate": _round(exposure_days / len(equity_curve), 4) if equity_curve else None,
        "skipped_count": len(skipped),
        "skipped_by_reason": dict(Counter(row["skip_reason"] for row in skipped)),
        "trade_summary": _summarize_trades(trades),
        "trades": trades,
        "skipped_events": skipped,
        "equity_curve_tail": equity_curve[-30:],
    }


def _buy_hold_metrics(price_map: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    start = WINDOWS["old_thin"]["start"]
    end = WINDOWS["late_strong"]["end"]
    return {
        "start": start,
        "end": end,
        "spy_return_pct": _round(_price_return(price_map, "SPY", start, end), 6),
        "qqq_return_pct": _round(_price_return(price_map, "QQQ", start, end), 6),
    }


def build_payload() -> dict[str, Any]:
    candidates, price_map = build_primary_candidates()
    variants: dict[str, Any] = OrderedDict()
    for holding_days in HORIZONS:
        for max_positions in MAX_POSITIONS_VARIANTS:
            label = f"{holding_days}d_max{max_positions}"
            variants[label] = simulate_sleeve(
                candidates,
                price_map,
                holding_days=holding_days,
                max_positions=max_positions,
            )

    primary_label = f"{PRIMARY_HORIZON}d_max{PRIMARY_MAX_POSITIONS}"
    primary = variants[primary_label]
    gate_promising = (
        primary["trade_count"] >= 10
        and (primary["total_return_pct"] or 0) > 0
        and (primary["sharpe_daily"] or 0) >= 0.5
        and (primary["max_drawdown_pct"] or 1) <= 0.20
    )
    status = "sleeve_promising_not_promoted" if gate_promising else "sleeve_rejected"
    decision_rationale = (
        "The fixed SEC negative-language + negative-reaction packet remains positive after portfolio-level "
        "event-sleeve simulation with costs; it is eligible for a default-off production queue / replacement-value test."
        if gate_promising
        else "The fixed SEC negative-language + negative-reaction packet did not survive portfolio-level sleeve simulation."
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "lane": "alpha_search",
        "status": status,
        "decision": status,
        "hypothesis": (
            "The fixed, replayable SEC negative-language + negative first-reaction packet can make money as a small "
            "deterministic event sleeve after capacity limits and round-trip costs."
        ),
        "alpha_hypothesis": {
            "category": "event_sleeve_backtest",
            "entry_or_ranking": "entry",
            "text": (
                "8-K Item 2.02 events with negative filing language and negative first reaction versus SPY can form "
                "a small mean-reversion/recoverable-pressure event sleeve."
            ),
        },
        "change_type": "non_ohlcv_event_sleeve_backtest",
        "single_causal_variable": "promote exp-20260504-008 primary packet into deterministic sleeve simulation",
        "historical_experiment_check": {
            "prior_same_family": {
                "exp-20260504-002": "raw positive SEC results-8K reaction failed",
                "exp-20260504-004": "Companyfacts point score was nonmonotonic",
                "exp-20260504-007": "positive filing text failed; negative language was shadow-positive",
                "exp-20260504-008": "negative_language + reaction_excess_return < 0 was shadow-promising",
            },
            "why_this_is_not_repeat": (
                "This freezes the exp-008 packet and changes only the measurement layer from forward-return "
                "distribution to capital/capacity/cost portfolio simulation."
            ),
            "mechanism_insight_check": (
                "Recent playbook requires no phrase tuning and no direct production promotion; this run tests "
                "whether the fixed packet survives a real sleeve backtest."
            ),
        },
        "parameters": {
            "packet_rule": "8-K Item 2.02 AND language_bucket == negative_language AND reaction_excess_return < 0",
            "language_proxy_version": "fixed_keyword_proxy_v0_from_exp_20260504_007",
            "reaction_metric": "ticker open-to-close return on usable trade date minus SPY open-to-close return",
            "entry_timing": "next trading-day open after reaction close",
            "exit_variants_trading_days": list(HORIZONS),
            "max_positions_variants": list(MAX_POSITIONS_VARIANTS),
            "primary_variant": primary_label,
            "initial_capital": INITIAL_CAPITAL,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "capital_model": (
                "standalone event-sleeve capital, compounding available sleeve equity; this does not consume core A/B slots"
            ),
            "same_day_candidate_ordering": "most negative reaction_excess_return first, then ticker",
            "locked_variables": [
                "keyword phrase list",
                "reaction threshold at < 0",
                "production universe",
                "core A/B entries",
                "core ranking",
                "core sizing",
                "core exits",
                "LLM/news replay",
            ],
        },
        "date_range": {
            "primary": "2025-10-23 -> 2026-04-21",
            "secondary": ["2025-04-23 -> 2025-10-22", "2024-10-02 -> 2025-04-22"],
        },
        "market_regime_summary": {label: cfg["state_note"] for label, cfg in WINDOWS.items()},
        "before_metrics": BASELINE_METRICS,
        "after_metrics": BASELINE_METRICS,
        "expected_value_score_delta": 0.0,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "production_impact": "shadow_sleeve_backtest_only_no_core_strategy_logic_changed",
        },
        "gate4": {
            "passed": False,
            "basis": "No production/core strategy change was promoted; this is a standalone sleeve simulation.",
        },
        "coverage": {
            "candidate_events": len(candidates),
            "candidate_by_window": dict(Counter(row.get("window") for row in candidates)),
            "candidate_by_reaction_bucket": dict(Counter(row.get("reaction_bucket") for row in candidates)),
            "dedupe_key": "ticker + entry_date",
        },
        "buy_hold": _buy_hold_metrics(price_map),
        "sleeve_metrics": {
            "primary_variant": primary_label,
            "primary": primary,
            "variants": variants,
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
        },
        "decision_rationale": decision_rationale,
        "rejection_reason": None if gate_promising else decision_rationale,
        "next_retry_requires": [
            "Do not tune keywords or reaction thresholds around this result.",
            "Next valid step is a replacement-value test versus same-day A/B accepted and skipped candidates.",
            "If replacement value is positive, add a default-off production queue using shared packet policy.",
        ],
        "related_files": [
            _repo_rel(__file__),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(REPORT_MD),
            _repo_rel(TEXT_PATH),
            "quant/experiments/exp_20260504_008_sec_negative_reaction_absorption.py",
        ],
    }
    return _safe(payload)


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.2f}%"


def build_report(payload: dict[str, Any]) -> str:
    lines = [
        "# SEC Event-Sleeve Backtest",
        "",
        f"Experiment: `{EXPERIMENT_ID}`",
        f"Status: `{payload['status']}`",
        "",
        "## Headline",
        "",
        payload["decision_rationale"],
        "",
        "## Variants",
        "",
        "| Variant | Trades | Total return | Sharpe daily | Max DD | Win rate | Exposure | Skipped |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, variant in payload["sleeve_metrics"]["variants"].items():
        lines.append(
            f"| {label} | {variant['trade_count']} | {_fmt_pct(variant['total_return_pct'])} | "
            f"{variant['sharpe_daily']} | {_fmt_pct(variant['max_drawdown_pct'])} | "
            f"{_fmt_pct(variant['win_rate'])} | {_fmt_pct(variant['exposure_rate'])} | "
            f"{variant['skipped_count']} |"
        )
    primary = payload["sleeve_metrics"]["primary"]
    top_concentration = primary["trade_summary"]["top_trade_concentration"]
    lines.extend(
        [
            "",
            "## Primary Trades By Window",
            "",
            "| Window | Trades | Avg net return | Win rate | Total PnL |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for window, data in primary["trade_summary"]["by_window"].items():
        dist = data["net_return_distribution"]
        lines.append(
            f"| {window} | {data['trade_count']} | {_fmt_pct(dist['avg'])} | "
            f"{_fmt_pct(dist['win_rate'])} | {data['total_pnl']} |"
        )
    lines.extend(
        [
            "",
            "## Caveat",
            "",
            "- This is a standalone event-sleeve simulation, not a core A/B backtest change.",
            (
                f"- Top-trade concentration: {top_concentration['ticker']} contributed "
                f"{top_concentration['pnl']} PnL "
                f"({_fmt_pct(top_concentration['share_of_total_pnl'])} of primary total PnL); "
                "replacement-value testing must verify this is not a one-name artifact."
            ),
            "- Gate 4 is not passed for production because no shared production/backtest event policy changed.",
            "- The packet rule is frozen from exp-20260504-008; nearby keyword or reaction-threshold tuning is explicitly out of scope.",
            "",
            "## Next",
            "",
            "Run replacement-value testing versus same-day accepted/skipped A/B candidates. If that survives, add a default-off production queue.",
            "",
        ]
    )
    return "\n".join(lines)


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "title": "SEC negative reaction event-sleeve backtest",
        "summary": payload["decision_rationale"],
        "primary_variant": payload["sleeve_metrics"]["primary_variant"],
        "primary_metrics": {
            key: payload["sleeve_metrics"]["primary"][key]
            for key in (
                "trade_count",
                "total_return_pct",
                "sharpe_daily",
                "max_drawdown_pct",
                "win_rate",
                "exposure_rate",
            )
        },
        "production_impact": payload["production_impact"],
        "next_retry_requires": payload["next_retry_requires"],
    }
    _write_json(TICKET_JSON, ticket)
    _write_text(REPORT_MD, build_report(payload))

    compact = dict(payload)
    compact["sleeve_metrics"] = {
        "primary_variant": payload["sleeve_metrics"]["primary_variant"],
        "primary": {
            key: payload["sleeve_metrics"]["primary"][key]
            for key in (
                "holding_days",
                "max_positions",
                "final_equity",
                "total_pnl",
                "total_return_pct",
                "sharpe_daily",
                "expected_value_score",
                "max_drawdown_pct",
                "trade_count",
                "win_rate",
                "exposure_rate",
                "skipped_count",
                "skipped_by_reason",
                "trade_summary",
            )
        },
        "variant_summary": {
            label: {
                key: variant[key]
                for key in (
                    "total_return_pct",
                    "sharpe_daily",
                    "max_drawdown_pct",
                    "trade_count",
                    "win_rate",
                    "exposure_rate",
                    "skipped_count",
                )
            }
            for label, variant in payload["sleeve_metrics"]["variants"].items()
        },
    }
    existing_lines = (
        EXPERIMENT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        if EXPERIMENT_LOG.exists()
        else []
    )
    kept_lines = [
        line
        for line in existing_lines
        if f'"experiment_id":"{EXPERIMENT_ID}"' not in line
        and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
    ]
    kept_lines.append(json.dumps(compact, ensure_ascii=False, separators=(",", ":")))
    EXPERIMENT_LOG.write_text("\n".join(kept_lines) + "\n", encoding="utf-8")


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "status": payload["status"],
                "decision": payload["decision"],
                "coverage": payload["coverage"],
                "primary_variant": payload["sleeve_metrics"]["primary_variant"],
                "primary": {
                    key: payload["sleeve_metrics"]["primary"][key]
                    for key in (
                        "trade_count",
                        "total_return_pct",
                        "sharpe_daily",
                        "expected_value_score",
                        "max_drawdown_pct",
                        "win_rate",
                        "exposure_rate",
                        "skipped_count",
                        "skipped_by_reason",
                    )
                },
                "variant_summary": {
                    label: {
                        key: variant[key]
                        for key in (
                            "trade_count",
                            "total_return_pct",
                            "sharpe_daily",
                            "max_drawdown_pct",
                            "win_rate",
                            "exposure_rate",
                            "skipped_count",
                        )
                    }
                    for label, variant in payload["sleeve_metrics"]["variants"].items()
                },
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    print(f"wrote: {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
