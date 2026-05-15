"""exp-20260514-010: SEC buyback credibility sleeve replay.

Alpha search on one causal variable: add a fixed-notional, replay-only event
overlay for PIT-proxy SEC text disclosures that show buyback credibility rather
than generic repurchase keywords.
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from constants import ROUND_TRIP_COST_PCT  # noqa: E402
from data_layer import get_universe  # noqa: E402
from experiments.exp_20260504_034_form4_satellite_overlay import (  # noqa: E402
    EVENT_NOTIONAL,
    HOLD_DAYS,
    _combined_metrics,
    _core_metrics,
    _delta,
    _event_equity_curve,
    _gate4,
    _load_price_map,
)
from sec_event_queue import (  # noqa: E402
    evaluate_first_reaction,
    load_sec_filing_text_rows,
    semantic_text,
)


EXP_ID = "exp-20260514-010"
TITLE = "SEC Buyback Credibility Sleeve"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / "sec_buyback_credibility_sleeve.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXP_ID}.json"
AUDIT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXP_ID}_sec_buyback_credibility_sleeve.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
SEC_TEXT_PATH = REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_text_20241002_20260421.jsonl"
INITIAL_CAPITAL = 100_000.0
MAX_EVENT_POSITIONS = 1

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
                "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
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

BUYBACK_TERMS_RE = re.compile(
    r"\b("
    r"share repurchase|stock repurchase|common stock repurchase|"
    r"repurchase program|repurchase authorization|authorized repurchase|"
    r"buyback|accelerated share repurchase|issuer purchases of equity securities"
    r")\b",
    re.IGNORECASE,
)
EXECUTION_RE = re.compile(
    r"\b(repurchased|purchased|retired)\b.{0,120}\b(shares|common stock|class a|class b)\b"
    r"|\b(shares|common stock|class a|class b)\b.{0,120}\b(repurchased|purchased|retired)\b",
    re.IGNORECASE | re.DOTALL,
)
AUTHORIZATION_RE = re.compile(
    r"\b(authoriz(?:e|ed|es|ation)|approv(?:e|ed|es)|increas(?:e|ed|es|ing)|expand(?:ed|s|ing))\b"
    r".{0,160}\b(repurchase program|share repurchase|stock repurchase|common stock repurchase|buyback)\b"
    r"|\b(repurchase program|share repurchase|stock repurchase|common stock repurchase|buyback)\b"
    r".{0,160}\b(authoriz(?:e|ed|es|ation)|approv(?:e|ed|es)|increas(?:e|ed|es|ing)|expand(?:ed|s|ing))\b",
    re.IGNORECASE | re.DOTALL,
)
ASR_RE = re.compile(r"\b(accelerated share repurchase|ASR)\b", re.IGNORECASE)
CASH_RE = re.compile(
    r"\b(cash|cash equivalents|investments|free cash flow|cash flow|fund(?:ed|s|ing)?|liquidity)\b",
    re.IGNORECASE,
)
PERIOD_RE = re.compile(
    r"\b(during the|for the|three months|six months|nine months|year ended|quarter ended|month ended|fiscal year)\b",
    re.IGNORECASE,
)
MONEY_RE = re.compile(r"\$\s?\d|\b\d+(?:\.\d+)?\s?(million|billion)\b", re.IGNORECASE)


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _json_load(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(value).replace("\\", "/")


def _round(value: Any, digits: int = 6) -> Any:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return round(float(value), digits)
    return value


def _float_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _window_name(date_value: str) -> str | None:
    value = str(date_value)[:10]
    for label, window in WINDOWS.items():
        if window["start"] <= value <= window["end"]:
            return label
    return None


def _index_on_date(rows: list[dict[str, Any]], date_value: str) -> int | None:
    target = str(date_value)[:10]
    for idx, row in enumerate(rows):
        if str(row.get("date") or "")[:10] == target:
            return idx
    return None


def _first_index_on_or_after(rows: list[dict[str, Any]], date_value: str) -> int | None:
    target = str(date_value)[:10]
    for idx, row in enumerate(rows):
        if str(row.get("date") or "")[:10] >= target:
            return idx
    return None


def _buyback_credibility(text: str) -> tuple[str | None, dict[str, Any]]:
    if not BUYBACK_TERMS_RE.search(text):
        return None, {"buyback_term": False}

    signals = {
        "buyback_term": True,
        "asr": bool(ASR_RE.search(text)),
        "execution": bool(EXECUTION_RE.search(text)),
        "authorization": bool(AUTHORIZATION_RE.search(text)),
        "cash_support": bool(CASH_RE.search(text)),
        "period_context": bool(PERIOD_RE.search(text)),
        "amount_context": bool(MONEY_RE.search(text)),
    }
    if signals["asr"]:
        return "accelerated_share_repurchase", signals
    if signals["execution"] and signals["period_context"] and signals["amount_context"]:
        return "actual_execution_update", signals
    if signals["authorization"] and signals["cash_support"] and signals["amount_context"]:
        return "authorization_increase_cash_funded", signals
    return None, signals


def _slim_event(event: dict[str, Any]) -> dict[str, Any]:
    keep = [
        "ticker",
        "cik",
        "accession_number",
        "form_type",
        "form_base",
        "filing_date",
        "usable_trade_date",
        "accepted_at",
        "eight_k_item_codes",
        "primary_document",
        "index_url",
        "buyback_credibility_bucket",
        "buyback_credibility_signals",
        "price_status",
        "reaction_date",
        "reaction_return",
        "spy_reaction_return",
        "reaction_excess_return",
        "reaction_bucket",
        "pit_caveat",
    ]
    return {key: event.get(key) for key in keep if key in event}


def _build_candidate_events(
    rows: list[dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    min_start = min(window["start"] for window in WINDOWS.values())
    max_end = max(window["end"] for window in WINDOWS.values())
    spy_rows = prices.get("SPY") or []
    skipped = Counter()
    buckets = Counter()
    candidates: list[dict[str, Any]] = []
    evaluated_rows = 0

    for row in rows:
        usable = str(row.get("usable_trade_date") or "")[:10]
        if not usable or usable < min_start or usable > max_end:
            continue
        if str(row.get("status") or "ok") != "ok":
            skipped["status_not_ok"] += 1
            continue

        evaluated_rows += 1
        text = semantic_text(row)
        bucket, signals = _buyback_credibility(text)
        if bucket is None:
            if signals.get("buyback_term"):
                skipped["buyback_keyword_not_credible"] += 1
            else:
                skipped["no_buyback_term"] += 1
            continue

        event = {
            **row,
            "buyback_credibility_bucket": bucket,
            "buyback_credibility_signals": signals,
            **evaluate_first_reaction(row, prices, spy_rows),
        }
        if event.get("price_status") != "covered":
            skipped[f"price_{event.get('price_status')}"] += 1
            continue

        buckets[bucket] += 1
        candidates.append({**_slim_event(event), "window": _window_name(usable)})

    return sorted(
        candidates,
        key=lambda event: (
            str(event.get("usable_trade_date") or ""),
            str(event.get("ticker") or ""),
            str(event.get("accession_number") or ""),
        ),
    ), {
        "raw_rows": len(rows),
        "evaluated_rows_in_windows": evaluated_rows,
        "qualified_event_count": len(candidates),
        "qualified_bucket_counts": dict(sorted(buckets.items())),
        "skipped_counts": dict(sorted(skipped.items())),
    }


def _candidate_trade(
    event: dict[str, Any],
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    ticker = str(event.get("ticker") or "").upper()
    rows = prices.get(ticker) or []
    reaction_date = str(event.get("reaction_date") or event.get("usable_trade_date") or "")[:10]
    if not ticker or not rows or not reaction_date:
        return {**event, "status": "missing_price_history"}

    reaction_idx = _index_on_date(rows, reaction_date)
    if reaction_idx is None:
        reaction_idx = _first_index_on_or_after(rows, reaction_date)
    if reaction_idx is None:
        return {**event, "status": "missing_reaction_date"}

    entry_idx = reaction_idx + 1
    exit_idx = entry_idx + HOLD_DAYS
    if exit_idx >= len(rows):
        return {**event, "status": "missing_exit_price"}

    entry = rows[entry_idx]
    exit_row = rows[exit_idx]
    entry_open = _float_or_none(entry.get("open"))
    exit_close = _float_or_none(exit_row.get("close"))
    if entry_open is None or exit_close is None or entry_open <= 0:
        return {**event, "status": "missing_open_or_close"}

    gross_return = exit_close / entry_open - 1.0
    net_return = gross_return - ROUND_TRIP_COST_PCT
    return {
        **event,
        "status": "price_ready",
        "entry_date": str(entry["date"])[:10],
        "exit_date": str(exit_row["date"])[:10],
        "entry_open": round(entry_open, 6),
        "exit_close": round(exit_close, 6),
        "gross_return_pct": round(gross_return * 100.0, 6),
        "net_return_pct": round(net_return * 100.0, 6),
        "notional": EVENT_NOTIONAL,
        "shares": EVENT_NOTIONAL / entry_open,
        "pnl": round(EVENT_NOTIONAL * net_return, 2),
        "source": "sec_buyback_credibility_sleeve",
    }


def _overlaps(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_start = str(left.get("entry_date") or "")[:10]
    left_end = str(left.get("exit_date") or "")[:10]
    right_start = str(right.get("entry_date") or "")[:10]
    right_end = str(right.get("exit_date") or "")[:10]
    return left_start <= right_end and right_start <= left_end


def _select_event_trades(
    trades: list[dict[str, Any]],
    *,
    start: str,
    end: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    scoped = [
        trade
        for trade in trades
        if trade.get("status") == "price_ready"
        and start <= str(trade.get("entry_date") or "")[:10] <= end
    ]
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for trade in sorted(
        scoped,
        key=lambda item: (
            str(item.get("entry_date") or ""),
            str(item.get("ticker") or ""),
            str(item.get("accession_number") or ""),
        ),
    ):
        active = [existing for existing in selected if _overlaps(existing, trade)]
        if len(active) >= MAX_EVENT_POSITIONS:
            skipped.append(
                {
                    "ticker": trade.get("ticker"),
                    "entry_date": trade.get("entry_date"),
                    "exit_date": trade.get("exit_date"),
                    "pnl": trade.get("pnl"),
                    "buyback_credibility_bucket": trade.get("buyback_credibility_bucket"),
                    "reason": "max_event_positions_overlap",
                }
            )
            continue
        selected.append(trade)
    return selected, skipped


def _load_core_result(window: dict[str, str]) -> dict[str, Any]:
    result = BacktestEngine(
        get_universe(),
        start=window["start"],
        end=window["end"],
        config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
        ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
    ).run()
    if "error" in result:
        raise RuntimeError(str(result["error"]))
    return result


def _aggregate_delta(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
    gate_by_window: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    before_ev = sum(float(row.get("expected_value_score") or 0.0) for row in before.values())
    after_ev = sum(float(row.get("expected_value_score") or 0.0) for row in after.values())
    before_pnl = sum(float(row.get("total_pnl") or 0.0) for row in before.values())
    after_pnl = sum(float(row.get("total_pnl") or 0.0) for row in after.values())
    return {
        "baseline_ev_sum": round(before_ev, 4),
        "overlay_ev_sum": round(after_ev, 4),
        "ev_delta_sum": round(after_ev - before_ev, 4),
        "ev_delta_pct": round((after_ev - before_ev) / before_ev, 6) if before_ev else None,
        "baseline_pnl_sum": round(before_pnl, 2),
        "overlay_pnl_sum": round(after_pnl, 2),
        "pnl_delta": round(after_pnl - before_pnl, 2),
        "pnl_delta_pct": round((after_pnl - before_pnl) / before_pnl, 6) if before_pnl else None,
        "windows_ev_improved": sum(
            1
            for label in WINDOWS
            if float(after[label].get("expected_value_score") or 0.0)
            > float(before[label].get("expected_value_score") or 0.0)
        ),
        "windows_ev_regressed": sum(
            1
            for label in WINDOWS
            if float(after[label].get("expected_value_score") or 0.0)
            < float(before[label].get("expected_value_score") or 0.0)
        ),
        "windows_material_ev_or_pnl": sum(
            1
            for label in WINDOWS
            if gate_by_window[label]["passes_material_ev"] or gate_by_window[label]["passes_pnl"]
        ),
        "windows_trade_count_win_rate_gate": sum(
            1 for label in WINDOWS if gate_by_window[label]["passes_trade_count"]
        ),
        "max_drawdown_delta_max": round(
            max(
                float(after[label].get("max_drawdown_pct") or 0.0)
                - float(before[label].get("max_drawdown_pct") or 0.0)
                for label in WINDOWS
            ),
            6,
        ),
    }


def _decision(aggregate: dict[str, Any]) -> tuple[str, str, str, str]:
    material = (
        int(aggregate["windows_material_ev_or_pnl"]) >= 2
        and int(aggregate["windows_ev_regressed"]) == 0
    )
    stable_positive = (
        int(aggregate["windows_ev_improved"]) >= 2
        and int(aggregate["windows_ev_regressed"]) == 0
        and float(aggregate["pnl_delta"] or 0.0) > 0.0
    )
    if material:
        return (
            "accepted_requires_followup",
            "positive_replay_only_requires_shared_buyback_sleeve",
            "The SEC buyback credibility overlay cleared material majority-window checks. It remains default-off until a shared queue/sleeve adapter exists.",
            "Promote only as shared default-off buyback queue/sleeve with production and backtest parity, then rerun the same windows.",
        )
    if stable_positive:
        return (
            "rejected",
            "positive_sample_not_material_no_promotion",
            "The buyback credibility overlay was directionally positive but not material enough for another default-off event surface.",
            "Keep the credibility taxonomy as evidence; retry only with new closed forward outcomes or stronger execution/disclosure fields.",
        )
    return (
        "rejected",
        "rejected_no_stable_alpha",
        "The buyback credibility overlay did not improve the fixed three windows without regression.",
        "Do not promote this SEC buyback credibility sleeve on the frozen sample; next buyback work needs richer credibility fields or forward evidence.",
    )


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _json_load(TICKET_JSON, {"experiment_id": EXP_ID})
    if not isinstance(ticket, dict):
        ticket = {"experiment_id": EXP_ID}
    ticket.update(
        {
            "title": TITLE,
            "status": payload["status"],
            "decision": payload["decision"],
            "completed_at": payload["timestamp"],
            "result": {
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "audit_report": _repo_rel(AUDIT_MD),
                "decision": payload["decision"],
                "aggregate_delta": payload["aggregate_delta"],
                "next_action": payload["next_action"],
            },
        }
    )
    _write_json(TICKET_JSON, ticket)


def _update_registry(payload: dict[str, Any]) -> None:
    registry = _json_load(REGISTRY_JSON, {"schema_version": 1, "experiments": []})
    if not isinstance(registry, dict):
        registry = {"schema_version": 1, "experiments": []}
    experiments = registry.setdefault("experiments", [])
    for entry in experiments:
        if entry.get("experiment_id") == EXP_ID:
            entry.update(
                {
                    "status": payload["status"],
                    "updated_at": payload["timestamp"],
                    "completed_at": payload["timestamp"],
                    "result": {
                        "decision": payload["decision"],
                        "aggregate_delta": payload["aggregate_delta"],
                        "log_file": _repo_rel(LOG_JSON),
                    },
                }
            )
            break
    else:
        experiments.append(
            {
                "experiment_id": EXP_ID,
                "title": TITLE,
                "status": payload["status"],
                "created_at": payload["timestamp"],
                "updated_at": payload["timestamp"],
                "completed_at": payload["timestamp"],
                "lane": payload["lane"],
                "mechanism_family": payload["mechanism_family"],
                "result": {
                    "decision": payload["decision"],
                    "aggregate_delta": payload["aggregate_delta"],
                    "log_file": _repo_rel(LOG_JSON),
                },
            }
        )
    registry["updated_at"] = payload["timestamp"]
    _write_json(REGISTRY_JSON, registry)


def _append_experiment_log(payload: dict[str, Any]) -> None:
    compact = json.dumps(_safe(payload), ensure_ascii=False, separators=(",", ":"))
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
        f"# {EXP_ID} SEC Buyback Credibility Sleeve",
        "",
        f"- decision: `{payload['decision']}`",
        f"- status: `{payload['status']}`",
        f"- expected_value_score_delta: `{payload['aggregate_delta']['ev_delta_sum']}`",
        f"- total_pnl_delta: `{payload['aggregate_delta']['pnl_delta']}`",
        f"- qualified_events: `{payload['data_availability']['qualified_event_count']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Three-Window Result",
        "",
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | Event PnL | Event Trades | Win Rate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["deltas"][label]
        lines.append(
            "| {label} | {bev} | {aev} | {dev} | {bpnl} | {apnl} | {epnl} | {etrades} | {wr} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                epnl=after.get("event_pnl"),
                etrades=after.get("event_trade_count"),
                wr=after.get("win_rate"),
            )
        )

    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            "```json",
            json.dumps(payload["aggregate_delta"], indent=2, ensure_ascii=True, sort_keys=True),
            "```",
            "",
            "## Data Availability",
            "",
            "```json",
            json.dumps(payload["data_availability"], indent=2, ensure_ascii=True, sort_keys=True),
            "```",
            "",
            "## Decision",
            "",
            payload["decision_rationale"],
            "",
            "## Production Impact",
            "",
            (
                "No default backtest strategy path or live order path changed. "
                "Any positive result requires a shared default-off buyback queue/sleeve before promotion."
            ),
            "",
            "## Next Action",
            "",
            payload["next_action"],
            "",
        ]
    )
    _write_text(AUDIT_MD, "\n".join(lines))


def build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if not SEC_TEXT_PATH.exists():
        raise FileNotFoundError(str(SEC_TEXT_PATH))

    prices = _load_price_map()
    rows = load_sec_filing_text_rows(SEC_TEXT_PATH)
    candidate_events, event_audit = _build_candidate_events(rows, prices)
    event_trade_candidates = [_candidate_trade(event, prices) for event in candidate_events]

    before_metrics: dict[str, dict[str, Any]] = {}
    after_metrics: dict[str, dict[str, Any]] = {}
    event_details: dict[str, dict[str, Any]] = {}
    core_run_audit: dict[str, dict[str, Any]] = {}

    for label, window in WINDOWS.items():
        result = _load_core_result(window)
        selected, skipped = _select_event_trades(
            event_trade_candidates,
            start=window["start"],
            end=window["end"],
        )
        event_curve = _event_equity_curve(
            selected,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        before_metrics[label] = _core_metrics(result)
        after_metrics[label] = _combined_metrics(result, event_curve, selected)
        unready = [
            trade
            for trade in event_trade_candidates
            if window["start"] <= str(trade.get("usable_trade_date") or "")[:10] <= window["end"]
            and trade.get("status") != "price_ready"
        ]
        event_details[label] = {
            "candidate_event_count": sum(
                1
                for event in candidate_events
                if window["start"] <= str(event.get("usable_trade_date") or "")[:10] <= window["end"]
            ),
            "price_ready_count": sum(
                1
                for trade in event_trade_candidates
                if window["start"] <= str(trade.get("usable_trade_date") or "")[:10] <= window["end"]
                and trade.get("status") == "price_ready"
            ),
            "selected_trade_count": len(selected),
            "selected_trade_pnl": round(sum(float(trade.get("pnl") or 0.0) for trade in selected), 2),
            "selected_win_rate": round(
                sum(1 for trade in selected if float(trade.get("pnl") or 0.0) > 0) / len(selected),
                4,
            )
            if selected
            else None,
            "selected_trades": selected,
            "skipped_capacity": skipped,
            "unready_candidates": [
                {
                    "ticker": trade.get("ticker"),
                    "usable_trade_date": trade.get("usable_trade_date"),
                    "reaction_date": trade.get("reaction_date"),
                    "status": trade.get("status"),
                }
                for trade in unready
            ],
            "event_equity_curve": event_curve,
        }
        core_run_audit[label] = {
            "converged": bool((result.get("convergence") or {}).get("converged")),
            "known_biases": result.get("known_biases"),
            "ohlcv_source": (result.get("known_biases") or {}).get("ohlcv_source"),
        }

    deltas = {label: _delta(before_metrics[label], after_metrics[label]) for label in WINDOWS}
    gate_by_window = {label: _gate4(before_metrics[label], after_metrics[label]) for label in WINDOWS}
    aggregate = _aggregate_delta(before_metrics, after_metrics, gate_by_window)
    status, decision, rationale, next_action = _decision(aggregate)

    payload = {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "title": TITLE,
        "status": status,
        "decision": decision,
        "lane": "alpha_search",
        "mechanism_family": "sec_buyback_credibility_event_sleeve",
        "change_type": "event_overlay_experiment",
        "run_mode": "three_window_backtest_plus_replay_only_sec_event_overlay",
        "hypothesis": (
            "SEC text disclosures that show buyback credibility through actual execution, "
            "cash-supported authorization increases, or accelerated share repurchase language "
            "may carry a higher-quality capital-return signal than generic repurchase keywords."
        ),
        "alpha_hypothesis": {
            "category": "entry / external event overlay",
            "text": "Enter a bounded paper event sleeve after credible SEC buyback disclosures and hold for 10 trading days.",
            "playbook_alignment": "Matches the current top priority: buyback credibility sleeve, not generic authorization drift.",
            "why_not_llm": "LLM soft-ranking remains attribution/sample limited; this uses fixed SEC text fields and frozen OHLCV snapshots.",
        },
        "historical_experiment_check": {
            "prior_blocker": (
                "exp-20260514-006 marked generic buyback authorization drift blocked because only keyword references were found. "
                "This run adds a credibility taxonomy and tests only execution/cash-supported/ASR disclosures."
            ),
            "not_repeating_guidance_raise": "Does not use Item 2.02 guidance-raise selloff recovery from exp-20260506-013.",
            "not_repeating_sec_text_severity": "Does not retune language_score or negative_phrase_hits from exp-20260507-015.",
            "not_broad_universe_expansion": "Adds no noisy tickers; only event-timed paper exposure for covered SEC text rows.",
        },
        "parameters": {
            "sec_text_file": _repo_rel(SEC_TEXT_PATH),
            "included_credibility_buckets": [
                "actual_execution_update",
                "authorization_increase_cash_funded",
                "accelerated_share_repurchase",
            ],
            "entry_rule": "next trading day's open after first reaction date",
            "hold_days": HOLD_DAYS,
            "event_notional": EVENT_NOTIONAL,
            "max_event_positions": MAX_EVENT_POSITIONS,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "core_initial_capital": INITIAL_CAPITAL,
            "selection_order": "entry_date asc, ticker asc, accession_number asc",
        },
        "single_causal_variable": "add fixed SEC buyback credibility event PnL as a replay-only satellite overlay",
        "date_range": {
            "windows": WINDOWS,
            "combined": {
                "start": min(window["start"] for window in WINDOWS.values()),
                "end": max(window["end"] for window in WINDOWS.values()),
            },
        },
        "market_regime_summary": {label: window["state_note"] for label, window in WINDOWS.items()},
        "data_availability": {
            **event_audit,
            "qualified_tickers": sorted({str(event.get("ticker") or "").upper() for event in candidate_events}),
            "pit_status": (
                "Uses SEC accepted_at/usable_trade_date and fixed OHLCV snapshots. "
                "Public archive text is replayable PIT proxy, not proof the production pipeline observed it live."
            ),
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "deltas": deltas,
        "aggregate_delta": aggregate,
        "gate4": {
            "rule": "EV first; material if EV >10%, Sharpe >0.1, DD -1pp, PnL >5%, or trade count rises with win rate not down",
            "by_window": gate_by_window,
            "material_windows": aggregate["windows_material_ev_or_pnl"],
            "trade_count_win_rate_windows": aggregate["windows_trade_count_win_rate_gate"],
            "decision": decision,
        },
        "event_overlay": event_details,
        "core_run_audit": core_run_audit,
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "note": "LLM authority was not expanded; this is deterministic SEC text classification.",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "production_signal_path_changed": False,
            "production_orders_changed": False,
            "production_impact": "experiment_only_replay_overlay_no_live_or_default_backtest_strategy_change",
            "promotion_blocker_if_accepted": "requires shared default-off buyback event queue/sleeve in production and backtest before any order impact",
        },
        "decision_rationale": rationale,
        "next_action": next_action,
        "risk_note": (
            "The taxonomy can still confuse historical execution disclosures with fresh authorization news; "
            "promotion would require richer disclosure-type fields and default-off parity."
        ),
        "anti_js": "No JavaScript was used.",
    }
    return payload


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _update_ticket(payload)
    _update_registry(payload)
    _write_report(payload)
    _append_experiment_log(payload)


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "status": payload["status"],
                "aggregate_delta": payload["aggregate_delta"],
                "gate4": payload["gate4"],
                "data_availability": payload["data_availability"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
