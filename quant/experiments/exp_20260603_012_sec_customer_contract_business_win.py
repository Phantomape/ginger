"""exp-20260603-012: SEC customer-contract / demand-backlog candidate pool.

Alpha search on one free, production-visible SEC text field. The experiment
tests whether 8-K filing text that contains customer demand, backlog, bookings,
or customer-win language can form a cleaner default-off event candidate pool.

No production adapter, live order path, ranking, sizing, exits, thresholds,
LLM/news path, or shared sleeve code is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import re
import statistics
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from backtester import BacktestEngine  # noqa: E402
from constants import ROUND_TRIP_COST_PCT  # noqa: E402
from data_layer import get_universe  # noqa: E402
from sec_event_queue import (  # noqa: E402
    language_features,
    load_sec_filing_text_rows,
    semantic_text,
)

import exp_20260504_034_form4_satellite_overlay as overlay  # noqa: E402


EXP_ID = "exp-20260603-012"
STEM = "sec_customer_contract_business_win"
TRIAL_FAMILY = "sec_customer_contract_business_win_candidate_pool"
CHANGED_VARIABLE = "sec_customer_contract_business_win_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

SEC_TEXT_PATH = (
    REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_text_20241002_20260421.jsonl"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXP_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

INITIAL_CAPITAL = 100_000.0
EVENT_NOTIONAL = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.30

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
                "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)

BUSINESS_WIN_PATTERNS: tuple[str, ...] = (
    r"\bbacklog\b",
    r"\border backlog\b",
    r"\bbookings\b",
    r"\bcustomer demand\b",
    r"\bnew customers?\b",
    r"\bcustomer wins?\b",
    r"\bdemand remains strong\b",
    r"\bstrong demand\b",
    r"\brobust demand\b",
    r"\brecord backlog\b",
    r"\bcontract award(?:ed)?\b",
    r"\bawarded (?:a |an )?contract\b",
    r"\bcommercial agreement\b",
    r"\bsupply agreement\b",
    r"\bdistribution agreement\b",
    r"\bmaster services agreement\b",
    r"\bpurchase order\b",
)
EXCLUSION_PATTERNS: tuple[str, ...] = (
    r"\btermination\b",
    r"\bterminated\b",
    r"\blawsuit\b",
    r"\bbankruptcy\b",
    r"\boffering\b",
    r"\bat[- ]the[- ]market\b",
    r"\bwarrant\b",
    r"\bconvertible\b",
    r"\bgoing concern\b",
    r"\brestatement\b",
)
NEGATIVE_LANGUAGE_BUCKET = "negative_language"

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_no_live_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "parity_note": (
        "This experiment changes no production code. A retained result would need "
        "a shared default-off SEC text adapter with the same semantic field and "
        "parity tests before any daily report, candidate queue, or order surface "
        "could change."
    ),
}


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return value.as_posix()


def _pattern_count(text: str, patterns: tuple[str, ...]) -> int:
    return sum(
        len(re.findall(pattern, text, flags=re.IGNORECASE | re.DOTALL))
        for pattern in patterns
    )


def _window_name(value: str) -> str | None:
    for label, window in WINDOWS.items():
        if window["start"] <= value <= window["end"]:
            return label
    return None


def _configure_overlay_module() -> None:
    overlay.WINDOWS = WINDOWS
    overlay.INITIAL_CAPITAL = INITIAL_CAPITAL
    overlay.EVENT_NOTIONAL = EVENT_NOTIONAL
    overlay.HOLD_DAYS = HOLD_DAYS


def _candidate_from_row(row: dict[str, Any]) -> dict[str, Any] | None:
    usable = str(row.get("usable_trade_date") or "")[:10]
    window = _window_name(usable)
    ticker = str(row.get("ticker") or "").upper()
    if not ticker or not usable or window is None:
        return None
    form_type = str(row.get("form_type") or row.get("form_base") or "").upper()
    if "8-K" not in form_type:
        return None

    text = semantic_text(row)
    if not text:
        return None
    lowered = text.lower()
    business_win_hits = _pattern_count(lowered, BUSINESS_WIN_PATTERNS)
    exclusion_hits = _pattern_count(lowered, EXCLUSION_PATTERNS)
    features = language_features(row)
    if business_win_hits <= 0:
        return None
    if exclusion_hits > 0:
        return None
    if str(features.get("language_bucket") or "") == NEGATIVE_LANGUAGE_BUCKET:
        return None

    score = business_win_hits
    score += 0.25 * int(features.get("positive_phrase_hits") or 0)
    score += 0.50 * int(features.get("guidance_raise_hits") or 0)
    return {
        "ticker": ticker,
        "usable_trade_date": usable,
        "filing_date": str(row.get("filing_date") or "")[:10],
        "window": window,
        "form_type": form_type,
        "accession_number": row.get("accession_number"),
        "primary_document": row.get("primary_document"),
        "status": "event_ready",
        "rule_version": RULE_VERSION,
        "strategy": STEM,
        "business_win_hits": business_win_hits,
        "exclusion_hits": exclusion_hits,
        "candidate_selection_score": round(score, 6),
        "text_event_type": features.get("text_event_type"),
        "language_bucket": features.get("language_bucket"),
        "language_score": features.get("language_score"),
        "positive_phrase_hits": features.get("positive_phrase_hits"),
        "negative_phrase_hits": features.get("negative_phrase_hits"),
        "guidance_raise_hits": features.get("guidance_raise_hits"),
        "guidance_cut_hits": features.get("guidance_cut_hits"),
        "known_at": "after_8k_filing_usable_trade_date_before_next_open_paper_entry",
        "trade_enabled": False,
        "alters_orders": False,
    }


def _load_candidate_events() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = load_sec_filing_text_rows(SEC_TEXT_PATH)
    events = []
    by_window_all = Counter()
    for row in rows:
        usable = str(row.get("usable_trade_date") or "")[:10]
        window = _window_name(usable)
        if window:
            by_window_all[window] += 1
        event = _candidate_from_row(row)
        if event is not None:
            events.append(event)
    events.sort(
        key=lambda row: (
            row["usable_trade_date"],
            -float(row.get("candidate_selection_score") or 0.0),
            str(row.get("ticker") or ""),
        )
    )
    return events, {
        "sec_text_file": _repo_rel(SEC_TEXT_PATH),
        "source_row_count": len(rows),
        "source_rows_by_window": dict(sorted(by_window_all.items())),
        "candidate_count": len(events),
        "candidate_count_by_window": dict(
            sorted(Counter(row["window"] for row in events).items())
        ),
        "candidate_ticker_count": len({row["ticker"] for row in events}),
        "candidate_tickers": sorted({row["ticker"] for row in events}),
    }


def _price_candidates(
    events: list[dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    return [overlay._candidate_trade(event, prices) for event in events]


def _select_event_trades(
    candidates: list[dict[str, Any]],
    *,
    start: str,
    end: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    scoped = [
        row
        for row in candidates
        if start <= str(row.get("usable_trade_date") or "")[:10] <= end
    ]
    ready = [row for row in scoped if row.get("status") == "price_ready"]
    ready.sort(
        key=lambda row: (
            row["entry_date"],
            -float(row.get("candidate_selection_score") or 0.0),
            -float(row.get("business_win_hits") or 0.0),
            str(row.get("ticker") or ""),
        )
    )

    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = [
        {
            "ticker": row.get("ticker"),
            "usable_trade_date": row.get("usable_trade_date"),
            "window": row.get("window"),
            "reason": row.get("status"),
        }
        for row in scoped
        if row.get("status") != "price_ready"
    ]
    trades_by_day: Counter[str] = Counter()
    for row in ready:
        entry_date = str(row.get("entry_date") or "")
        if trades_by_day[entry_date] >= MAX_PAPER_TRADES_PER_DAY:
            skipped.append(
                {
                    "ticker": row.get("ticker"),
                    "usable_trade_date": row.get("usable_trade_date"),
                    "entry_date": entry_date,
                    "window": row.get("window"),
                    "reason": "max_paper_trades_per_day_full",
                    "candidate_selection_score": row.get("candidate_selection_score"),
                }
            )
            continue
        selected.append(row)
        trades_by_day[entry_date] += 1
    return selected, skipped


def _aggregate_metrics(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "expected_value_score": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in rows.values()),
            4,
        ),
        "strategy_total_pnl": round(
            sum(float(row.get("total_pnl") or 0.0) for row in rows.values()),
            2,
        ),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in rows.values()),
        "survival_rate_min": min(
            float(row.get("survival_rate") or 0.0) for row in rows.values()
        ),
        "max_drawdown_pct_max": max(
            float(row.get("max_drawdown_pct") or 0.0) for row in rows.values()
        ),
    }


def _comparison(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    ev_before = float(before.get("expected_value_score") or 0.0)
    pnl_before = float(before.get("strategy_total_pnl") or 0.0)
    ev_after = float(after.get("expected_value_score") or 0.0)
    pnl_after = float(after.get("strategy_total_pnl") or 0.0)
    return {
        "expected_value_score_delta": round(ev_after - ev_before, 4),
        "expected_value_score_delta_pct": round((ev_after - ev_before) / ev_before, 6)
        if ev_before
        else None,
        "strategy_total_pnl_delta": round(pnl_after - pnl_before, 2),
        "strategy_total_pnl_delta_pct": round((pnl_after - pnl_before) / pnl_before, 6)
        if pnl_before
        else None,
        "trade_count_delta": int(after.get("trade_count") or 0)
        - int(before.get("trade_count") or 0),
        "survival_rate_min_delta": round(
            float(after.get("survival_rate_min") or 0.0)
            - float(before.get("survival_rate_min") or 0.0),
            6,
        ),
        "max_drawdown_delta": round(
            float(after.get("max_drawdown_pct_max") or 0.0)
            - float(before.get("max_drawdown_pct_max") or 0.0),
            6,
        ),
    }


def _target_summary(
    target_trades_by_window: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    trades = [trade for rows in target_trades_by_window.values() for trade in rows]
    positive_by_ticker: Counter[str] = Counter()
    for trade in trades:
        pnl = float(trade.get("pnl") or 0.0)
        if pnl > 0.0:
            positive_by_ticker[str(trade.get("ticker") or "missing")] += pnl
    total_positive = sum(positive_by_ticker.values())
    shares = [
        value / total_positive for value in positive_by_ticker.values()
    ] if total_positive else []
    return {
        "target_trade_count": len(trades),
        "target_trade_count_by_window": {
            label: len(rows) for label, rows in target_trades_by_window.items()
        },
        "target_trade_pnl_usd": round(
            sum(float(trade.get("pnl") or 0.0) for trade in trades),
            2,
        ),
        "target_trade_pnl_by_window": {
            label: round(sum(float(trade.get("pnl") or 0.0) for trade in rows), 2)
            for label, rows in target_trades_by_window.items()
        },
        "positive_pnl_by_ticker": {
            ticker: round(value, 2)
            for ticker, value in sorted(positive_by_ticker.items())
        },
        "max_single_positive_share": round(max(shares), 6) if shares else 0.0,
        "positive_pnl_hhi": round(sum(share * share for share in shares), 6),
    }


def _gate4_decision(
    aggregate: dict[str, Any],
    results: list[dict[str, Any]],
    target_summary: dict[str, Any],
) -> dict[str, Any]:
    comparison = aggregate["comparison"]
    ev_delta = float(comparison.get("expected_value_score_delta") or 0.0)
    pnl_delta = float(comparison.get("strategy_total_pnl_delta") or 0.0)
    ev_windows_improved = [
        row["label"]
        for row in results
        if float(row["comparison"].get("expected_value_score_delta") or 0.0) > 0.0
    ]
    pnl_windows_improved = [
        row["label"]
        for row in results
        if float(row["comparison"].get("strategy_total_pnl_delta") or 0.0) > 0.0
    ]
    max_drawdown_delta = max(
        float(row["comparison"].get("max_drawdown_delta") or 0.0)
        for row in results
    )
    min_survival_rate = min(
        float(row["after"].get("survival_rate") or 0.0) for row in results
    )
    target_trade_count = int(target_summary["target_trade_count"])

    gates = {
        "aggregate_expected_value_positive": ev_delta > 0.0,
        "aggregate_pnl_positive": pnl_delta > 0.0,
        "all_windows_expected_value_improved": len(ev_windows_improved) == len(results),
        "all_windows_pnl_improved": len(pnl_windows_improved) == len(results),
        "target_trade_count_passed": target_trade_count >= MIN_TARGET_TRADES,
        "target_window_count_passed": sum(
            1 for row in results if int(row["target_trade_count"]) > 0
        )
        >= MIN_TARGET_WINDOWS,
        "drawdown_drift_passed": max_drawdown_delta <= MAX_DRAWDOWN_WORSE,
        "survival_floor_passed": min_survival_rate >= 0.05,
        "concentration_guard_passed": (
            float(target_summary["max_single_positive_share"])
            <= MAX_SINGLE_POSITIVE_SHARE
            and float(target_summary["positive_pnl_hhi"]) <= MAX_POSITIVE_HHI
        ),
    }
    passed = all(gates.values())
    if passed:
        decision = "positive_replay_lead_not_promoted_requires_shared_sec_text_adapter"
        rationale = (
            "The replay improved aggregate EV and PnL across all canonical windows "
            "while staying inside sample, drawdown, survival, and concentration "
            "guards. No production behavior changed; promotion requires a shared "
            "default-off SEC text adapter and parity tests."
        )
        status = "observed_only"
    else:
        decision = "rejected_sec_customer_contract_business_win_candidate_pool"
        rationale = (
            "One or more Gate 4 checks failed, so the SEC customer-contract / "
            "demand-backlog candidate source is not retained."
        )
        status = "rejected"
    return {
        "decision": decision,
        "status": status,
        "passed": passed,
        "rationale": rationale,
        "gates": gates,
        "ev_windows_improved": ev_windows_improved,
        "pnl_windows_improved": pnl_windows_improved,
        "max_drawdown_delta": max_drawdown_delta,
        "min_survival_rate": min_survival_rate,
        "requires_parity_before_promotion": passed,
    }


def _daily_sharpe_from_combined_curve(
    metrics: dict[str, Any],
) -> dict[str, Any]:
    curve = metrics.get("combined_equity_curve") or []
    returns = []
    for (_, prev), (_, curr) in zip(curve, curve[1:]):
        if float(prev) > 0:
            returns.append(float(curr) / float(prev) - 1.0)
    if len(returns) < 2:
        return {"daily_return_mean": None, "daily_return_stdev": None}
    stdev = statistics.stdev(returns)
    return {
        "daily_return_mean": round(sum(returns) / len(returns), 8),
        "daily_return_stdev": round(stdev, 8),
    }


def _window_table(results: list[dict[str, Any]]) -> str:
    lines = [
        "| Window | Target trades | Target PnL | EV before | EV after | EV delta | PnL delta | DD delta |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in results:
        lines.append(
            "| {label} | {count} | ${target_pnl:,.2f} | {before_ev:.4f} | {after_ev:.4f} | {ev_delta:+.4f} | ${pnl_delta:+,.2f} | {dd_delta:+.4f} |".format(
                label=row["label"],
                count=row["target_trade_count"],
                target_pnl=float(row["target_trade_pnl_usd"]),
                before_ev=float(row["before"]["expected_value_score"]),
                after_ev=float(row["after"]["expected_value_score"]),
                ev_delta=float(row["comparison"]["expected_value_score_delta"]),
                pnl_delta=float(row["comparison"]["strategy_total_pnl_delta"]),
                dd_delta=float(row["comparison"]["max_drawdown_delta"]),
            )
        )
    return "\n".join(lines)


def _write_artifact(payload: dict[str, Any]) -> None:
    aggregate = payload["aggregate"]
    comparison = aggregate["comparison"]
    lines = [
        f"# {EXP_ID} SEC Customer-Contract Business-Win Candidate Pool",
        "",
        f"- Trial family: `{TRIAL_FAMILY}`",
        f"- Changed variable: `{CHANGED_VARIABLE}`",
        f"- Decision: `{payload['gate4']['decision']}`",
        f"- Aggregate EV delta: {float(comparison['expected_value_score_delta']):+.4f}",
        f"- Aggregate PnL delta: ${float(comparison['strategy_total_pnl_delta']):+,.2f}",
        f"- Target trades: {payload['target_summary']['target_trade_count']}",
        f"- Production impact: `{PRODUCTION_IMPACT['adapter_status']}`",
        "",
        "## Gate 1-4",
        "",
        _window_table(payload["results"]),
        "",
        "## Gate 4 Checks",
        "",
    ]
    for key, value in payload["gate4"]["gates"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            "",
            "## Decision Rationale",
            "",
            payload["gate4"]["rationale"],
            "",
            "## Production / Backtest Parity",
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "## Reproducibility",
            "",
            (
                ".\\.venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260603_012_sec_customer_contract_business_win.py"
            ),
        ]
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _load_json(TICKET_JSON, {"experiment_id": EXP_ID})
    if not isinstance(ticket, dict):
        ticket = {"experiment_id": EXP_ID}
    prediction = ticket.get("prediction") or {}
    actual_success = 1 if payload["gate4"]["passed"] else 0
    if isinstance(prediction, dict):
        prediction.update(
            {
                "actual_success": actual_success,
                "actual_ev_delta": payload["aggregate"]["comparison"][
                    "expected_value_score_delta"
                ],
                "actual_pnl_delta": payload["aggregate"]["comparison"][
                    "strategy_total_pnl_delta"
                ],
                "brier_score": round((float(prediction.get("success_probability") or 0.0) - actual_success) ** 2, 6),
            }
        )
    ticket.update(
        {
            "status": payload["gate4"]["status"],
            "decision": payload["gate4"]["decision"],
            "completed_at": payload["completed_at"],
            "prediction": prediction,
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "production_impact": PRODUCTION_IMPACT,
            "gate4": payload["gate4"],
            "result": {
                "decision": payload["gate4"]["decision"],
                "aggregate_expected_value_delta": payload["aggregate"]["comparison"][
                    "expected_value_score_delta"
                ],
                "aggregate_strategy_total_pnl_delta": payload["aggregate"]["comparison"][
                    "strategy_total_pnl_delta"
                ],
                "artifact": _repo_rel(ARTIFACT_MD),
                "log": _repo_rel(LOG_JSON),
            },
        }
    )
    _write_json(TICKET_JSON, ticket)


def _update_registry(payload: dict[str, Any]) -> None:
    registry = _load_json(REGISTRY_JSON, {"schema_version": 1, "experiments": []})
    if not isinstance(registry, dict):
        return
    experiments = registry.setdefault("experiments", [])
    for item in experiments:
        if isinstance(item, dict) and item.get("experiment_id") == EXP_ID:
            item["status"] = payload["gate4"]["status"]
            item["decision"] = payload["gate4"]["decision"]
            item["updated_at"] = payload["completed_at"]
            item["completed_at"] = payload["completed_at"]
            item["artifact"] = _repo_rel(OUT_JSON)
            item["log"] = _repo_rel(LOG_JSON)
            item["aggregate_expected_value_delta"] = payload["aggregate"]["comparison"][
                "expected_value_score_delta"
            ]
            item["aggregate_strategy_total_pnl_delta"] = payload["aggregate"]["comparison"][
                "strategy_total_pnl_delta"
            ]
            break
    registry["updated_at"] = payload["completed_at"]
    _write_json(REGISTRY_JSON, registry)


def _experiment_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    comparison = payload["aggregate"]["comparison"]
    actual_success = 1 if payload["gate4"]["passed"] else 0
    return {
        "experiment_id": EXP_ID,
        "timestamp": payload["completed_at"],
        "lane": "alpha_search",
        "trial_family": TRIAL_FAMILY,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["preflight"]["alpha_hypothesis"],
        "decision": payload["gate4"]["decision"],
        "accepted": bool(payload["gate4"]["passed"]),
        "production_impact": PRODUCTION_IMPACT,
        "requires_parity_before_promotion": bool(
            payload["gate4"]["requires_parity_before_promotion"]
        ),
        "metrics": {
            "aggregate_expected_value_before": payload["aggregate"]["before"][
                "expected_value_score"
            ],
            "aggregate_expected_value_after": payload["aggregate"]["after"][
                "expected_value_score"
            ],
            "aggregate_expected_value_delta": comparison["expected_value_score_delta"],
            "aggregate_strategy_total_pnl_before": payload["aggregate"]["before"][
                "strategy_total_pnl"
            ],
            "aggregate_strategy_total_pnl_after": payload["aggregate"]["after"][
                "strategy_total_pnl"
            ],
            "aggregate_strategy_total_pnl_delta": comparison[
                "strategy_total_pnl_delta"
            ],
            "target_trade_count": payload["target_summary"]["target_trade_count"],
            "target_trade_pnl_usd": payload["target_summary"][
                "target_trade_pnl_usd"
            ],
            "max_drawdown_delta": payload["gate4"]["max_drawdown_delta"],
            "max_single_positive_share": payload["target_summary"][
                "max_single_positive_share"
            ],
            "positive_pnl_hhi": payload["target_summary"]["positive_pnl_hhi"],
        },
        "windows": [
            {
                "label": row["label"],
                "expected_value_before": row["before"]["expected_value_score"],
                "expected_value_after": row["after"]["expected_value_score"],
                "expected_value_delta": row["comparison"][
                    "expected_value_score_delta"
                ],
                "strategy_total_pnl_delta": row["comparison"][
                    "strategy_total_pnl_delta"
                ],
                "target_trade_count": row["target_trade_count"],
                "target_trade_pnl_usd": row["target_trade_pnl_usd"],
            }
            for row in payload["results"]
        ],
        "prediction": {
            **(payload.get("prediction") or {}),
            "actual_success": actual_success,
            "actual_ev_delta": comparison["expected_value_score_delta"],
            "actual_pnl_delta": comparison["strategy_total_pnl_delta"],
            "brier_score": round(
                (float((payload.get("prediction") or {}).get("success_probability") or 0.0) - actual_success) ** 2,
                6,
            ),
        },
        "next_action": payload["next_action"],
    }


def _append_experiment_log(record: dict[str, Any]) -> None:
    compact = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    if not EXPERIMENT_LOG.exists():
        EXPERIMENT_LOG.write_text(compact + "\n", encoding="utf-8")
        return
    lines = EXPERIMENT_LOG.read_text(
        encoding="utf-8", errors="replace"
    ).splitlines()
    lines = [
        line
        for line in lines
        if f'"experiment_id":"{EXP_ID}"' not in line
        and f'"experiment_id": "{EXP_ID}"' not in line
    ]
    lines.append(compact)
    EXPERIMENT_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_payload() -> dict[str, Any]:
    _configure_overlay_module()
    completed_at = _utc_now()
    universe = get_universe()
    prices = overlay._load_price_map()
    events, data_audit = _load_candidate_events()
    priced_candidates = _price_candidates(events, prices)

    before_metrics: dict[str, dict[str, Any]] = {}
    after_metrics: dict[str, dict[str, Any]] = {}
    results: list[dict[str, Any]] = []
    event_details: dict[str, dict[str, Any]] = {}
    target_trades_by_window: dict[str, list[dict[str, Any]]] = {}
    core_run_audit: dict[str, dict[str, Any]] = {}

    for label, window in WINDOWS.items():
        result = BacktestEngine(
            universe,
            start=window["start"],
            end=window["end"],
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=window["snapshot"],
        ).run()
        selected, skipped = _select_event_trades(
            priced_candidates,
            start=window["start"],
            end=window["end"],
        )
        target_trades_by_window[label] = selected
        event_curve = overlay._event_equity_curve(
            selected,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        before = overlay._core_metrics(result)
        after = overlay._combined_metrics(result, event_curve, selected)
        before_metrics[label] = before
        after_metrics[label] = after
        comp = {
            "expected_value_score_delta": round(
                float(after.get("expected_value_score") or 0.0)
                - float(before.get("expected_value_score") or 0.0),
                4,
            ),
            "strategy_total_pnl_delta": round(
                float(after.get("total_pnl") or 0.0)
                - float(before.get("total_pnl") or 0.0),
                2,
            ),
            "max_drawdown_delta": round(
                float(after.get("max_drawdown_pct") or 0.0)
                - float(before.get("max_drawdown_pct") or 0.0),
                6,
            ),
        }
        results.append(
            {
                "label": label,
                "window": window,
                "before": before,
                "after": after,
                "comparison": comp,
                "target_trade_count": len(selected),
                "target_trade_pnl_usd": round(
                    sum(float(trade.get("pnl") or 0.0) for trade in selected), 2
                ),
                "return_diagnostics": _daily_sharpe_from_combined_curve(after),
            }
        )
        event_details[label] = {
            "candidate_count": sum(
                1
                for row in priced_candidates
                if window["start"]
                <= str(row.get("usable_trade_date") or "")[:10]
                <= window["end"]
            ),
            "price_ready_count": sum(
                1
                for row in priced_candidates
                if row.get("status") == "price_ready"
                and window["start"]
                <= str(row.get("usable_trade_date") or "")[:10]
                <= window["end"]
            ),
            "selected_trade_count": len(selected),
            "skipped_count": len(skipped),
            "skip_reasons": dict(
                sorted(Counter(row["reason"] for row in skipped).items())
            ),
            "selected_trades": selected,
            "skipped_candidates": skipped[:100],
            "event_equity_curve": event_curve,
        }
        core_run_audit[label] = {
            "converged": bool((result.get("convergence") or {}).get("converged")),
            "known_biases": result.get("known_biases"),
            "signals_generated": result.get("signals_generated"),
            "signals_survived": result.get("signals_survived"),
            "survival_rate": result.get("survival_rate"),
        }

    before_aggregate = _aggregate_metrics(before_metrics)
    after_aggregate = _aggregate_metrics(after_metrics)
    aggregate = {
        "before": before_aggregate,
        "after": after_aggregate,
        "comparison": _comparison(before_aggregate, after_aggregate),
    }
    target_summary = _target_summary(target_trades_by_window)
    gate4 = _gate4_decision(aggregate, results, target_summary)
    prediction = {
        "success_probability": 0.24,
        "expected_ev_delta": 0.20,
        "expected_pnl_delta": 3000.0,
        "main_failure_modes": [
            "thin_sample",
            "window_regression",
            "concentration_failed",
            "semantic_false_positive",
        ],
        "confidence_reason": (
            "SEC filing text is free and three-window replayable. The field is "
            "distinct from prior SEC tone/guidance scalars, but business-demand "
            "semantics can be noisy."
        ),
        "recorded_at": "2026-06-03T11:10:04Z",
    }

    return {
        "experiment_id": EXP_ID,
        "completed_at": completed_at,
        "lane": "alpha_search",
        "trial_family": TRIAL_FAMILY,
        "changed_variable": CHANGED_VARIABLE,
        "rule_version": RULE_VERSION,
        "preflight": {
            "alpha_hypothesis": (
                "SEC 8-K text that carries customer demand, backlog, bookings, "
                "or customer-win language may identify cleaner event-driven "
                "entry candidates than generic SEC positive tone."
            ),
            "category": "entry / candidate_pool",
            "playbook_alignment": (
                "Uses a free, production-visible context layer and tests a new "
                "candidate source instead of LLM soft-ranking, state-surface "
                "thresholds, or already-rejected SEC tone/guidance scalars."
            ),
            "nearby_prior_experiments": {
                "exp-20260506-013": "SEC guidance-raise selloff recovery was a different guidance/reaction family.",
                "exp-20260516-034": "SEC guidance-raise notional scalar was a production scalar test, not a new demand/backlog source.",
                "exp-20260520-015": "Clean-positive earnings notional tested generic positive language on accepted SEC rows.",
                "exp-20260603-005": "Post-earnings peer transfer was rejected for stability/concentration; this run uses direct SEC issuer text.",
            },
            "single_causal_variable": CHANGED_VARIABLE,
            "acceptance_criteria": {
                "canonical_windows": list(WINDOWS.keys()),
                "aggregate_expected_value_delta": "> 0",
                "aggregate_pnl_delta": "> 0",
                "per_window_expected_value_delta": "3 of 3 windows > 0",
                "per_window_pnl_delta": "3 of 3 windows > 0",
                "minimum_target_trades": MIN_TARGET_TRADES,
                "minimum_target_windows": MIN_TARGET_WINDOWS,
                "max_drawdown_drift": MAX_DRAWDOWN_WORSE,
                "survival_rate_floor": 0.05,
                "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
                "positive_pnl_hhi_max": MAX_POSITIVE_HHI,
            },
        },
        "parameters": {
            "sec_text_path": _repo_rel(SEC_TEXT_PATH),
            "business_win_patterns": BUSINESS_WIN_PATTERNS,
            "exclusion_patterns": EXCLUSION_PATTERNS,
            "excluded_language_bucket": NEGATIVE_LANGUAGE_BUCKET,
            "event_notional": EVENT_NOTIONAL,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "initial_capital": INITIAL_CAPITAL,
            "selection_order": (
                "entry_date asc, candidate_selection_score desc, "
                "business_win_hits desc, ticker asc"
            ),
        },
        "data_availability": data_audit,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "results": results,
        "aggregate": aggregate,
        "target_summary": target_summary,
        "gate4": gate4,
        "event_candidate_details": event_details,
        "core_run_audit": core_run_audit,
        "prediction": prediction,
        "production_impact": PRODUCTION_IMPACT,
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "note": "LLM soft-ranking data remains sparse, so this run uses a deterministic free-data SEC text field.",
        },
        "next_action": (
            "If positive, build a shared default-off SEC text adapter with the "
            "same semantic field and run parity before promotion; if rejected, "
            "do not retune nearby SEC demand/backlog phrases on this sample."
        )
        if gate4["passed"]
        else (
            "Do not retune nearby SEC demand/backlog phrases on this sample; "
            "move to a different free-data candidate-pool mechanism."
        ),
    }


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(BEFORE_JSON, payload["aggregate"]["before"])
    _write_json(AFTER_JSON, payload["aggregate"]["after"])
    _write_json(LOG_JSON, payload)
    _write_artifact(payload)
    CARD_MD.write_text(ARTIFACT_MD.read_text(encoding="utf-8"), encoding="utf-8")
    _update_ticket(payload)
    _update_registry(payload)
    _append_experiment_log(_experiment_log_record(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["gate4"]["decision"],
                "aggregate": payload["aggregate"]["comparison"],
                "target_summary": payload["target_summary"],
                "gate4": payload["gate4"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
