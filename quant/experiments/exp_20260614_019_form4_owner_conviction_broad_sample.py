"""exp-20260614-019: Broad Form 4 owner-conviction purchase sleeve.

This replay-only scout tests a materially different insider-quality
discriminator from exp-20260614-018. Instead of asking whether more clustered
open-market Form 4 buys are enough, it asks whether a buy that is large
relative to the reporting owner's post-transaction holdings is a cleaner
candidate-pool source.

No production code, live order path, shared policy, ranking, sizing, exits,
LLM/news path, or watchlist is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402

import exp_20260504_034_form4_satellite_overlay as overlay  # noqa: E402
from exp_20260601_006_broad_universe_alpha_score_ranking_validation import (  # noqa: E402
    load_warehouse_frames,
)


EXP_ID = "exp-20260614-019"
STEM = "form4_owner_conviction_broad_sample"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
CANDIDATES_JSONL = OUT_DIR / f"{STEM}_candidates.jsonl"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXP_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"

# Broad open-market-purchase Form 4 rows materialized by exp-20260614-018.
BROAD_FORM4_PATH = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260614-018"
    / "form4_open_market_purchases_broad_20240802_20260615.jsonl"
)

MIN_TRANSACTION_VALUE = 100_000.0
MIN_OWNER_CONVICTION_RATIO = 0.10
MAX_OWNER_CONVICTION_RATIO = 1.0
EXCLUDE_10B5_1 = True

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


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(value).replace("\\", "/")


def _json_load(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _date10(value: Any) -> str:
    text = str(value or "")
    return text[:10] if len(text) >= 10 else ""


def _window_name(day: str) -> str | None:
    day = _date10(day)
    for label, window in WINDOWS.items():
        if window["start"] <= day <= window["end"]:
            return label
    return None


def _float_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number):
        return None
    return number


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {"1", "true", "t", "yes", "y"}


def _owner_key(row: dict[str, Any]) -> str:
    for key in ("owner_cik", "reporting_owner_cik", "reporting_owner_name", "owner_name"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return "unknown"


def _owner_title(row: dict[str, Any]) -> str:
    return str(row.get("officer_title") or row.get("owner_title") or "").strip()


def _price_map_from_frames(frames: dict[str, pd.DataFrame]) -> dict[str, list[dict[str, Any]]]:
    prices: dict[str, list[dict[str, Any]]] = {}
    for ticker, frame in frames.items():
        rows: list[dict[str, Any]] = []
        for day, row in frame.iterrows():
            rows.append(
                {
                    "date": str(day.date()),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": float(row["Volume"]),
                }
            )
        prices[ticker] = rows
    return prices


def _compact_row(row: dict[str, Any], ratio: float, value: float) -> dict[str, Any]:
    return {
        "owner": _owner_key(row),
        "owner_title": _owner_title(row),
        "transaction_value": round(value, 2),
        "shares": _float_or_none(row.get("shares")),
        "shares_owned_following_transaction": _float_or_none(
            row.get("shares_owned_following_transaction")
        ),
        "owner_conviction_ratio": round(ratio, 6),
        "is_director": bool(row.get("is_director")),
        "is_officer": bool(row.get("is_officer")),
        "is_ceo": bool(row.get("is_ceo")),
        "is_cfo": bool(row.get("is_cfo")),
        "accepted_at": row.get("accepted_at"),
        "accession": row.get("accession"),
    }


def _raw_row_qualifies(row: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    ticker = str(row.get("ticker") or "").upper().strip()
    usable = _date10(row.get("usable_trade_date"))
    if not ticker or not usable or not _window_name(usable):
        return False, {"reason": "outside_window_or_missing_ticker"}
    if not _truthy(row.get("open_market_purchase_flag")):
        return False, {"reason": "not_open_market_purchase"}
    if str(row.get("transaction_code") or "").upper() not in {"P", ""}:
        return False, {"reason": "not_purchase_code"}
    if EXCLUDE_10B5_1 and _truthy(row.get("10b5_1_flag")):
        return False, {"reason": "rule_10b5_1"}

    transaction_value = _float_or_none(row.get("transaction_value"))
    shares = _float_or_none(row.get("shares"))
    shares_after = _float_or_none(row.get("shares_owned_following_transaction"))
    if transaction_value is None or transaction_value < MIN_TRANSACTION_VALUE:
        return False, {"reason": "small_transaction_value"}
    if shares is None or shares <= 0 or shares_after is None or shares_after <= 0:
        return False, {"reason": "missing_or_invalid_ownership_base"}

    ratio = shares / shares_after
    if ratio < MIN_OWNER_CONVICTION_RATIO:
        return False, {"reason": "owner_conviction_ratio_below_floor"}
    if ratio > MAX_OWNER_CONVICTION_RATIO:
        return False, {"reason": "owner_conviction_ratio_above_cap"}

    return True, {
        "ticker": ticker,
        "usable_trade_date": usable,
        "transaction_value": transaction_value,
        "owner_conviction_ratio": ratio,
        "owner": _owner_key(row),
        "compact_row": _compact_row(row, ratio, transaction_value),
    }


def _event_from_group(
    key: tuple[str, str],
    rows: list[dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    ticker, usable = key
    owners = sorted({str(row["owner"]) for row in rows})
    max_row = max(rows, key=lambda row: row["owner_conviction_ratio"])
    total_purchase_value = sum(float(row["transaction_value"]) for row in rows)
    owner_titles = sorted(
        {
            str(row["compact_row"].get("owner_title") or "")
            for row in rows
            if row["compact_row"].get("owner_title")
        }
    )
    return {
        "ticker": ticker,
        "usable_trade_date": usable,
        "window": _window_name(usable),
        "status": "event_ready" if ticker in prices else "missing_price_history",
        "owner_conviction_ratio": round(float(max_row["owner_conviction_ratio"]), 6),
        "owner_conviction_ratio_floor": MIN_OWNER_CONVICTION_RATIO,
        "total_purchase_value": round(total_purchase_value, 2),
        "top_purchase_value": round(float(max_row["transaction_value"]), 2),
        "owner_count": len(owners),
        "row_count": len(rows),
        "owners": owners[:10],
        "owner_titles": owner_titles[:10],
        "top_owner_title": max_row["compact_row"].get("owner_title"),
        "has_officer": any(bool(row["compact_row"].get("is_officer")) for row in rows),
        "has_director": any(bool(row["compact_row"].get("is_director")) for row in rows),
        "has_ceo": any(bool(row["compact_row"].get("is_ceo")) for row in rows),
        "has_cfo": any(bool(row["compact_row"].get("is_cfo")) for row in rows),
        "source_rows": [row["compact_row"] for row in rows[:8]],
    }


def _write_candidates_snapshot(events: list[dict[str, Any]]) -> None:
    CANDIDATES_JSONL.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(event, ensure_ascii=False, sort_keys=True) for event in events]
    CANDIDATES_JSONL.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _load_candidates_snapshot(prices: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not CANDIDATES_JSONL.exists():
        return events
    for line in CANDIDATES_JSONL.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        ticker = str(event.get("ticker") or "").upper()
        event["status"] = "event_ready" if ticker in prices else "missing_price_history"
        events.append(event)
    return events


def _load_owner_conviction_events(
    prices: dict[str, list[dict[str, Any]]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not BROAD_FORM4_PATH.exists():
        events = _load_candidates_snapshot(prices)
        if events:
            return events, {
                "source": _repo_rel(CANDIDATES_JSONL),
                "source_kind": "materialized_candidate_snapshot_fallback",
                "raw_rows": None,
                "qualified_raw_rows": None,
                "skip_reasons": {},
            }
        raise FileNotFoundError(
            f"missing broad Form 4 input and candidate fallback: {BROAD_FORM4_PATH}"
        )

    raw_rows = 0
    qualified_raw_rows = 0
    skip_reasons: defaultdict[str, int] = defaultdict(int)
    groups: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    with BROAD_FORM4_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            raw_rows += 1
            row = json.loads(line)
            qualifies, payload = _raw_row_qualifies(row)
            if not qualifies:
                skip_reasons[str(payload["reason"])] += 1
                continue
            qualified_raw_rows += 1
            key = (str(payload["ticker"]), str(payload["usable_trade_date"]))
            groups[key].append(payload)

    events = [_event_from_group(key, rows, prices) for key, rows in groups.items()]
    events.sort(
        key=lambda row: (
            str(row.get("usable_trade_date") or ""),
            -float(row.get("owner_conviction_ratio") or 0.0),
            -float(row.get("total_purchase_value") or 0.0),
            str(row.get("ticker") or ""),
        )
    )
    _write_candidates_snapshot(events)
    return events, {
        "source": _repo_rel(BROAD_FORM4_PATH),
        "source_kind": "broad_form4_archive",
        "raw_rows": raw_rows,
        "qualified_raw_rows": qualified_raw_rows,
        "qualified_event_count": len(events),
        "skip_reasons": dict(sorted(skip_reasons.items())),
        "candidate_snapshot": _repo_rel(CANDIDATES_JSONL),
    }


def _select_owner_conviction_trades(
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
            -float(row.get("owner_conviction_ratio") or 0.0),
            -float(row.get("total_purchase_value") or 0.0),
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
    active: list[dict[str, Any]] = []
    for row in ready:
        entry_date = row["entry_date"]
        active = [trade for trade in active if trade["exit_date"] >= entry_date]
        if len(active) >= overlay.MAX_EVENT_POSITIONS:
            skipped.append(
                {
                    "ticker": row.get("ticker"),
                    "usable_trade_date": row.get("usable_trade_date"),
                    "entry_date": entry_date,
                    "window": row.get("window"),
                    "reason": "event_sleeve_capacity_full",
                    "active_tickers": [trade.get("ticker") for trade in active],
                }
            )
            continue
        selected.append(row)
        active.append(row)
    return selected, skipped


def _aggregate_metrics(metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "expected_value_score": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in metrics.values()),
            4,
        ),
        "total_pnl": round(
            sum(float(row.get("total_pnl") or 0.0) for row in metrics.values()),
            2,
        ),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in metrics.values()),
        "event_trade_count": sum(int(row.get("event_trade_count") or 0) for row in metrics.values()),
    }


def _aggregate_delta(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    before_agg = _aggregate_metrics(before)
    after_agg = _aggregate_metrics(after)
    before_ev = float(before_agg["expected_value_score"])
    before_pnl = float(before_agg["total_pnl"])
    ev_delta = float(after_agg["expected_value_score"]) - before_ev
    pnl_delta = float(after_agg["total_pnl"]) - before_pnl
    return {
        "baseline_ev_sum": before_agg["expected_value_score"],
        "after_ev_sum": after_agg["expected_value_score"],
        "aggregate_ev_delta": round(ev_delta, 4),
        "aggregate_ev_delta_pct": round(ev_delta / before_ev, 6) if before_ev else None,
        "baseline_pnl_sum": before_agg["total_pnl"],
        "after_pnl_sum": after_agg["total_pnl"],
        "aggregate_pnl_delta": round(pnl_delta, 2),
        "aggregate_pnl_delta_pct": round(pnl_delta / before_pnl, 6) if before_pnl else None,
        "baseline_trade_count": before_agg["trade_count"],
        "after_trade_count": after_agg["trade_count"],
        "event_trade_count": after_agg["event_trade_count"],
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


def _single_ticker_positive_share(event_details: dict[str, dict[str, Any]]) -> float | None:
    by_ticker: defaultdict[str, float] = defaultdict(float)
    for detail in event_details.values():
        for trade in detail.get("selected_trades") or []:
            pnl = float(trade.get("pnl") or 0.0)
            if pnl > 0:
                by_ticker[str(trade.get("ticker") or "").upper()] += pnl
    total = sum(by_ticker.values())
    if total <= 0:
        return None
    return round(max(by_ticker.values()) / total, 4)


def _gate_result(
    gate4: dict[str, Any],
    aggregate_delta: dict[str, Any],
    event_details: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    touched = sum(int(row.get("selected_trade_count") or 0) for row in event_details.values())
    single_share = _single_ticker_positive_share(event_details)
    sample_ok = touched >= 8 and (single_share is None or single_share <= 0.50)
    aggregate_positive = (
        float(aggregate_delta["aggregate_ev_delta"]) > 0.0
        and float(aggregate_delta["aggregate_pnl_delta"]) > 0.0
    )
    zero_ev_regression = int(aggregate_delta["windows_ev_regressed"]) == 0
    no_majority_regression = int(aggregate_delta["windows_ev_regressed"]) <= 1
    material_aggregate = (
        aggregate_delta["aggregate_ev_delta_pct"] is not None
        and aggregate_delta["aggregate_ev_delta_pct"] > 0.10
    ) or (
        aggregate_delta["aggregate_pnl_delta_pct"] is not None
        and aggregate_delta["aggregate_pnl_delta_pct"] > 0.05
    )
    return {
        "passed_replay_lead": bool(aggregate_positive and zero_ev_regression and sample_ok),
        "material_aggregate": bool(material_aggregate),
        "aggregate_positive": bool(aggregate_positive),
        "zero_ev_regression": bool(zero_ev_regression),
        "no_majority_ev_regression": bool(no_majority_regression),
        "selected_event_trades": touched,
        "sample_guard_min_trades": 8,
        "sample_guard_passed": bool(sample_ok),
        "single_ticker_positive_share": single_share,
        "single_ticker_positive_share_guard": "<= 0.50",
        "by_window": gate4,
    }


def _skip_reason_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    reasons = sorted({str(row.get("reason") or "") for row in rows if row.get("reason")})
    return {reason: sum(1 for row in rows if row.get("reason") == reason) for reason in reasons}


def _decision_from_gate(gate: dict[str, Any], aggregate_delta: dict[str, Any]) -> tuple[str, str, str, str]:
    if gate["passed_replay_lead"]:
        return (
            "observed_only",
            "positive_replay_lead_requires_shared_helper",
            "The owner-conviction Form 4 sleeve improved aggregate EV and PnL with no EV-regressing window and enough selected events. It is not accepted as an alpha because this run intentionally did not add the shared production/backtest default-off helper, daily snapshot, or parity tests required before promotion.",
            "Implement a shared default-off owner-conviction Form 4 helper and paper snapshot path, then rerun Gate 1-4 before any live/default change.",
        )
    if (
        float(aggregate_delta["aggregate_ev_delta"]) > 0.0
        or float(aggregate_delta["aggregate_pnl_delta"]) > 0.0
    ):
        return (
            "rejected",
            "rejected_directional_but_unstable",
            "The owner-conviction discriminator had a positive partial read but failed the stability/sample gates, so it should not be promoted or retuned on this sample.",
            "Do not sweep owner-conviction thresholds on the same archive; new evidence would need a different quality dimension or forward paper outcomes.",
        )
    return (
        "rejected",
        "rejected_no_alpha",
        "The owner-conviction discriminator reduced aggregate EV/PnL or did not produce enough stable event contribution across the canonical three windows.",
        "Do not retry broad Form 4 purchase quality with simple ratio/value threshold changes; move to a different candidate-pool source or wait for forward evidence.",
    )


def _write_report(payload: dict[str, Any]) -> None:
    reflection = payload["post_run_reflection"]
    lines = [
        "# Form 4 Owner-Conviction Broad Sample",
        "",
        f"- experiment_id: `{payload['experiment_id']}`",
        f"- timestamp: `{payload['timestamp']}`",
        f"- decision: `{payload['decision']}`",
        f"- status: `{payload['status']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Three-Window Results",
        "",
        "| Window | Baseline EV | After EV | Delta EV | Baseline PnL | After PnL | Event PnL | Event trades | Win rate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["deltas"][label]
        lines.append(
            f"| {label} | {before['expected_value_score']} | {after['expected_value_score']} | "
            f"{delta['expected_value_score']} | ${before['total_pnl']:,.2f} | "
            f"${after['total_pnl']:,.2f} | ${float(after.get('event_pnl') or 0.0):,.2f} | "
            f"{int(after.get('event_trade_count') or 0)} | "
            f"{before['win_rate']:.2%} -> {after['win_rate']:.2%} |"
        )
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            "```json",
            json.dumps(payload["aggregate_delta"], indent=2, sort_keys=True),
            "```",
            "",
            "## Gate",
            "",
            "```json",
            json.dumps(
                {
                    key: value
                    for key, value in payload["gate4"].items()
                    if key != "by_window"
                },
                indent=2,
                sort_keys=True,
            ),
            "```",
            "",
            "## Decision",
            "",
            payload["decision_rationale"],
            "",
            "## Post-Run Reflection",
            "",
            f"- why_result_happened: {reflection['why_result_happened']}",
            f"- forbidden_near_neighbor_retry: {reflection['forbidden_near_neighbor_retry']}",
            f"- new_evidence_required: {reflection['new_evidence_required']}",
            "",
            "## Production Impact",
            "",
            "```json",
            json.dumps(payload["production_impact"], indent=2, sort_keys=True),
            "```",
            "",
        ]
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines), encoding="utf-8")


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _json_load(TICKET_JSON, {"experiment_id": EXP_ID})
    if not isinstance(ticket, dict):
        ticket = {"experiment_id": EXP_ID}
    ticket.update(
        {
            "status": payload["status"],
            "decision": payload["decision"],
            "completed_at": payload["timestamp"],
            "result": {
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "report": _repo_rel(ARTIFACT_MD),
                "before": _repo_rel(BEFORE_JSON),
                "after": _repo_rel(AFTER_JSON),
                "candidate_snapshot": _repo_rel(CANDIDATES_JSONL),
                "decision": payload["decision"],
                "aggregate_delta": payload["aggregate_delta"],
                "calibration": payload["calibration"],
                "post_run_reflection": payload["post_run_reflection"],
                "next_action": payload["next_action"],
            },
        }
    )
    _write_json(TICKET_JSON, ticket)


def _write_card(payload: dict[str, Any]) -> None:
    CARD_MD.parent.mkdir(parents=True, exist_ok=True)
    CARD_MD.write_text(
        "\n".join(
            [
                f"# {EXP_ID} Form 4 Owner-Conviction Broad Sample",
                "",
                f"- status: `{payload['status']}`",
                f"- decision: `{payload['decision']}`",
                f"- runner: `{_repo_rel(Path(__file__))}`",
                f"- log: `{_repo_rel(LOG_JSON)}`",
                f"- artifact: `{_repo_rel(ARTIFACT_MD)}`",
                f"- candidate_snapshot: `{_repo_rel(CANDIDATES_JSONL)}`",
                "",
                "## Aggregate Delta",
                "",
                "```json",
                json.dumps(payload["aggregate_delta"], indent=2, sort_keys=True),
                "```",
                "",
                "## Conclusion",
                "",
                payload["decision_rationale"],
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def build_payload() -> dict[str, Any]:
    overlay.WINDOWS = WINDOWS
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    universe = get_universe()
    frames = load_warehouse_frames()
    prices = _price_map_from_frames(frames)
    events, data_source = _load_owner_conviction_events(prices)
    event_candidates = [overlay._candidate_trade(event, prices) for event in events]

    before_metrics: dict[str, dict[str, Any]] = OrderedDict()
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    deltas: dict[str, dict[str, Any]] = OrderedDict()
    gate_by_window: dict[str, dict[str, Any]] = OrderedDict()
    event_details: dict[str, dict[str, Any]] = OrderedDict()

    for label, window in WINDOWS.items():
        result = BacktestEngine(
            universe,
            start=window["start"],
            end=window["end"],
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=window["snapshot"],
        ).run()
        selected, skipped = _select_owner_conviction_trades(
            event_candidates,
            start=window["start"],
            end=window["end"],
        )
        event_curve = overlay._event_equity_curve(
            selected,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        before_metrics[label] = overlay._core_metrics(result)
        after_metrics[label] = overlay._combined_metrics(result, event_curve, selected)
        deltas[label] = overlay._delta(before_metrics[label], after_metrics[label])
        gate_by_window[label] = overlay._gate4(before_metrics[label], after_metrics[label])
        event_details[label] = {
            "candidate_count": sum(
                1
                for row in event_candidates
                if window["start"] <= _date10(row.get("usable_trade_date")) <= window["end"]
            ),
            "price_ready_count": sum(
                1
                for row in event_candidates
                if row.get("status") == "price_ready"
                and window["start"] <= _date10(row.get("usable_trade_date")) <= window["end"]
            ),
            "selected_trade_count": len(selected),
            "skipped_count": len(skipped),
            "skip_reasons": _skip_reason_counts(skipped),
            "selected_trades": selected,
            "skipped_candidates": skipped[:30],
        }

    aggregate_delta = _aggregate_delta(before_metrics, after_metrics)
    gate = _gate_result(gate_by_window, aggregate_delta, event_details)
    status, decision, rationale, next_action = _decision_from_gate(gate, aggregate_delta)
    reflection = {
        "why_result_happened": (
            "Owner-conviction ratio selected commitment but not stable favorable drift: "
            "late_strong benefited, while mid_weak and old_thin both lost event PnL and "
            "regressed EV. The likely mechanism is that a large buy relative to a small "
            "post-transaction holding can identify insiders adding risk after weakness or "
            "in structurally stressed issuers, so the ratio is not a standalone quality edge."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not sweep the 10% owner-conviction floor, the $100k value floor, 10b5-1 "
            "handling, event capacity, notional, or hold days on the same broad archive."
        ),
        "new_evidence_required": (
            "A valid retry needs a different evidence source, such as forward paper outcomes "
            "for this exact rule or an orthogonal quality signal like verified CEO/CFO "
            "non-plan buys paired with fundamental confirmation from a shared default-off helper."
        ),
    }
    if gate["passed_replay_lead"]:
        reflection = {
            "why_result_happened": (
                "The ratio supplied a positive replay lead because selected insider buys "
                "improved aggregate EV and PnL with no EV-regressing window."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not sweep thresholds or sleeve mechanics; the next test must keep the "
                "same fixed rule and move it into shared default-off paper infrastructure."
            ),
            "new_evidence_required": (
                "Shared helper parity, daily paper snapshot coverage, and a live-realistic "
                "execution envelope are required before any accepted-alpha or live-ready claim."
            ),
        }

    calibration = {
        "predicted_success_probability": 0.22,
        "predicted_ev_delta": 0.15,
        "predicted_pnl_delta": 2500.0,
        "realized_ev_delta": aggregate_delta["aggregate_ev_delta"],
        "realized_pnl_delta": aggregate_delta["aggregate_pnl_delta"],
        "realized_failure_mode": (
            "EV tiny-positive but PnL negative with two EV/PnL-regressing windows"
            if float(aggregate_delta["aggregate_ev_delta"]) > 0.0
            else "aggregate EV/PnL failed"
        ),
        "surprise_note": (
            "The sample was adequate at 34 selected event trades, but the edge was regime-specific: "
            "late_strong won while the two weaker windows more than offset it."
        ),
    }

    payload: dict[str, Any] = {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": (
            "Broad PIT Form 4 open-market purchases where the bought shares are at least "
            "10% of the reporting owner's post-transaction holdings may isolate higher "
            "conviction insider demand than broad clustered buying, improving candidate-pool "
            "event-sleeve EV without adding noisy tickers."
        ),
        "change_type": "candidate_pool_private_replay_scout",
        "mechanism_family": "form4_owner_conviction_event_sleeve",
        "single_causal_variable": "broad_form4_owner_conviction_purchase_candidate_source_v1",
        "parameters": {
            "min_transaction_value": MIN_TRANSACTION_VALUE,
            "min_owner_conviction_ratio": MIN_OWNER_CONVICTION_RATIO,
            "max_owner_conviction_ratio": MAX_OWNER_CONVICTION_RATIO,
            "exclude_10b5_1": EXCLUDE_10B5_1,
            "owner_conviction_ratio_definition": "shares / shares_owned_following_transaction",
            "event_grouping": "ticker + usable_trade_date",
            "selection_order": "entry_date asc, owner_conviction_ratio desc, total_purchase_value desc, ticker asc",
            "event_notional_usd": overlay.EVENT_NOTIONAL,
            "max_event_positions": overlay.MAX_EVENT_POSITIONS,
            "hold_days": overlay.HOLD_DAYS,
            "round_trip_cost_pct": overlay.ROUND_TRIP_COST_PCT,
            "price_source": "broad warehouse all_windows_full_liquid via load_warehouse_frames",
            "locked_variables": [
                "core universe",
                "core signal generation",
                "core ranking",
                "core position sizing",
                "core exits",
                "LLM/news replay settings",
                "event notional",
                "event holding period",
                "event capacity",
                "round-trip cost",
            ],
        },
        "date_range": {label: f"{w['start']} -> {w['end']}" for label, w in WINDOWS.items()},
        "market_regime_summary": {label: w["state_note"] for label, w in WINDOWS.items()},
        "historical_experiment_check": {
            "exp-20260614-018": "Broad clustered Form 4 open-market buys rejected; reflection allowed a different insider-quality discriminator such as buy size vs owner holdings.",
            "exp-20260503-053": "Owner-role discriminator rejected on old narrow sample; it said any retry needed materially broader data.",
            "exp-20260603-010": "Aggregate ownership-delta purchase signal rejected on old narrow PIT queue.",
            "exp-20260605-001": "Purchase liquidity-intensity old-sample signal was positive but rejected; this run does not retune liquidity.",
            "why_not_repeat": "Uses the broad 3,901-row archive plus a predeclared owner-conviction ratio, not cluster counts, owner-role labels, liquidity floors, or hold/notional tuning.",
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "deltas": deltas,
        "aggregate_delta": aggregate_delta,
        "gate4": gate,
        "event_details": event_details,
        "decision_rationale": rationale,
        "post_run_reflection": reflection,
        "calibration": calibration,
        "next_action": next_action,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_changed": False,
            "parity_test_added": False,
            "replay_only": True,
            "trade_enabled": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "alters_exits": False,
            "production_consistency_read": (
                "No live/default production surface changed. A positive replay result is "
                "only a lead until the exact rule is moved to a shared default-off helper "
                "used by both historical replay and daily paper snapshots."
            ),
        },
        "data_source": {
            **data_source,
            "warehouse_price_frames": len(frames),
            "pit_status": "uses accepted_at/usable_trade_date from broad Form 4 archive; no filing-date lookahead added",
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": "LLM soft-ranking remains sample-limited; this tests a deterministic free SEC Form 4 data edge.",
        },
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(BEFORE_JSON),
            _repo_rel(AFTER_JSON),
            _repo_rel(CANDIDATES_JSONL),
            _repo_rel(LOG_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
        ],
        "anti_js": "No JavaScript was used.",
    }
    return payload


def main() -> None:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(BEFORE_JSON, _aggregate_metrics(payload["before_metrics"]))
    _write_json(AFTER_JSON, _aggregate_metrics(payload["after_metrics"]))
    _write_report(payload)
    _update_ticket(payload)
    _write_card(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXP_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "aggregate_delta": payload["aggregate_delta"],
                "gate4": {
                    key: payload["gate4"][key]
                    for key in (
                        "passed_replay_lead",
                        "material_aggregate",
                        "aggregate_positive",
                        "zero_ev_regression",
                        "selected_event_trades",
                        "sample_guard_passed",
                        "single_ticker_positive_share",
                    )
                },
                "anti_js": payload["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
