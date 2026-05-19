"""Replay a SEC guidance-raise selloff recovery event sleeve.

Alpha hypothesis:
    When an Item 2.02 8-K explicitly raises guidance but the first tradeable
    day underperforms SPY, the market may be underreacting to a positive
    forward-looking disclosure. This tests a fixed event packet as a small
    replay-only overlay; it does not change the core strategy or production
    order path.
"""

from __future__ import annotations

import json
import math
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
    REQUIRED_ITEM_CODE,
    evaluate_first_reaction,
    language_features,
    load_sec_filing_text_rows,
)


EXP_ID = "exp-20260506-013"
TITLE = "SEC guidance-raise selloff recovery"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / "sec_guidance_raise_selloff_recovery.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
AUDIT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXP_ID}_sec_guidance_raise_selloff_recovery.md"
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
    if not math.isfinite(number):
        return None
    return number


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


def _qualifies_guidance_raise_selloff(event: dict[str, Any]) -> bool:
    item_codes = {str(item) for item in event.get("eight_k_item_codes") or []}
    reaction = event.get("reaction_excess_return")
    return (
        event.get("status") == "ok"
        and str(event.get("form_base") or event.get("form_type") or "").upper() == "8-K"
        and REQUIRED_ITEM_CODE in item_codes
        and int(event.get("guidance_raise_hits") or 0) > 0
        and int(event.get("guidance_cut_hits") or 0) == 0
        and event.get("price_status") == "covered"
        and isinstance(reaction, (int, float))
        and float(reaction) <= 0.0
    )


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
        "text_event_type",
        "language_score",
        "language_bucket",
        "positive_phrase_hits",
        "negative_phrase_hits",
        "guidance_raise_hits",
        "guidance_cut_hits",
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
    evaluated = 0
    skipped = Counter()
    candidates: list[dict[str, Any]] = []

    for row in rows:
        usable = str(row.get("usable_trade_date") or "")[:10]
        if not usable or usable < min_start or usable > max_end:
            continue
        if str(row.get("form_base") or row.get("form_type") or "").upper() != "8-K":
            skipped["not_8k"] += 1
            continue
        item_codes = {str(item) for item in row.get("eight_k_item_codes") or []}
        if REQUIRED_ITEM_CODE not in item_codes:
            skipped["missing_item_2_02"] += 1
            continue
        evaluated += 1
        event = {
            **row,
            **language_features(row),
            **evaluate_first_reaction(row, prices, spy_rows),
        }
        if not _qualifies_guidance_raise_selloff(event):
            if int(event.get("guidance_raise_hits") or 0) <= 0:
                skipped["no_guidance_raise_hit"] += 1
            elif int(event.get("guidance_cut_hits") or 0) != 0:
                skipped["has_guidance_cut_hit"] += 1
            elif event.get("price_status") != "covered":
                skipped[f"price_{event.get('price_status')}"] += 1
            elif _float_or_none(event.get("reaction_excess_return")) is not None:
                skipped["reaction_not_weak"] += 1
            else:
                skipped["other_not_qualified"] += 1
            continue
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
        "evaluated_item_2_02_8k_rows": evaluated,
        "qualified_event_count": len(candidates),
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
        "source": "sec_guidance_raise_selloff_recovery",
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
                    "reaction_excess_return": trade.get("reaction_excess_return"),
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
        replay_llm=False,
        replay_news=False,
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
    baseline_ev_sum = sum(float(row.get("expected_value_score") or 0.0) for row in before.values())
    overlay_ev_sum = sum(float(row.get("expected_value_score") or 0.0) for row in after.values())
    baseline_pnl_sum = sum(float(row.get("total_pnl") or 0.0) for row in before.values())
    overlay_pnl_sum = sum(float(row.get("total_pnl") or 0.0) for row in after.values())
    aggregate = {
        "baseline_ev_sum": round(baseline_ev_sum, 4),
        "overlay_ev_sum": round(overlay_ev_sum, 4),
        "ev_delta_sum": round(overlay_ev_sum - baseline_ev_sum, 4),
        "ev_delta_pct": round((overlay_ev_sum - baseline_ev_sum) / baseline_ev_sum, 6)
        if baseline_ev_sum
        else None,
        "baseline_pnl_sum": round(baseline_pnl_sum, 2),
        "overlay_pnl_sum": round(overlay_pnl_sum, 2),
        "pnl_delta": round(overlay_pnl_sum - baseline_pnl_sum, 2),
        "pnl_delta_pct": round((overlay_pnl_sum - baseline_pnl_sum) / baseline_pnl_sum, 6)
        if baseline_pnl_sum
        else None,
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
    }
    return aggregate


def _decision(aggregate: dict[str, Any]) -> tuple[str, str, str, str]:
    material = (
        int(aggregate["windows_material_ev_or_pnl"]) >= 2
        and int(aggregate["windows_ev_regressed"]) == 0
    )
    sample_positive = (
        int(aggregate["windows_ev_improved"]) >= 2
        and int(aggregate["windows_ev_regressed"]) == 0
    )
    if material:
        return (
            "accepted_requires_followup",
            "positive_replay_only_requires_shared_event_sleeve",
            "The fixed SEC guidance-raise selloff sleeve cleared material EV/PnL checks in the majority of windows. It is not production-ready until implemented through a shared default-off event sleeve.",
            "Build a shared default-off SEC guidance event sleeve adapter and parity test, then rerun the same three windows before any production exposure.",
        )
    if sample_positive:
        return (
            "rejected",
            "positive_sample_not_material_no_promotion",
            "The fixed event sleeve improved the majority EV read but not enough to justify live capital or added complexity.",
            "Keep this as an observed mechanism; retry only after new forward samples or a stronger non-tuned discriminator.",
        )
    return (
        "rejected",
        "rejected_no_stable_alpha",
        "The fixed event sleeve did not improve the majority of fixed windows without regression.",
        "Do not retry guidance-raise selloff recovery on the same sample; look for a different event source or new forward evidence.",
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
        "# SEC Guidance-Raise Selloff Recovery",
        "",
        f"- experiment_id: `{payload['experiment_id']}`",
        f"- timestamp: `{payload['timestamp']}`",
        f"- decision: `{payload['decision']}`",
        f"- production_impact: `{payload['production_impact']['production_impact']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Three-Window Results",
        "",
        "| Window | Baseline EV | Overlay EV | Delta EV | Baseline PnL | Overlay PnL | Event PnL | Trades | Win rate | Gate read |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["deltas"][label]
        gate = payload["gate4"]["by_window"][label]
        gate_bits = [
            name
            for name in [
                "passes_material_ev",
                "passes_pnl",
                "passes_sharpe",
                "passes_drawdown",
                "passes_trade_count",
            ]
            if gate[name]
        ]
        lines.append(
            "| {label} | {bev} | {aev} | {dev} | {bpnl} | {apnl} | {epnl} | {trades} | {wr} | {gate} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                epnl=after.get("event_pnl"),
                trades=after["trade_count"],
                wr=after["win_rate"],
                gate=", ".join(gate_bits) if gate_bits else "none",
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
            "## Decision Rationale",
            "",
            payload["decision_rationale"],
            "",
            "## Production Parity",
            "",
            "No production or default backtester strategy path changed in this run. Any positive result requires a shared default-off event sleeve adapter before it can affect live orders.",
            "",
            "## Do-Not-Repeat Note",
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
        missing_or_unready = [
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
                for trade in missing_or_unready
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
        "mechanism_family": "sec_guidance_raise_selloff_event_sleeve",
        "change_type": "event_overlay_experiment",
        "run_mode": "three_window_backtest_plus_replay_only_sec_event_overlay",
        "hypothesis": (
            "A fixed Item 2.02 SEC event packet where the company explicitly raises guidance but "
            "the first tradeable day underperforms SPY may capture underreaction and improve "
            "portfolio expected value as a bounded 10k-notional event sleeve."
        ),
        "alpha_hypothesis": {
            "category": "entry / external event overlay",
            "text": "Enter after guidance-raise 8-K disclosures that sell off relative to SPY, then hold for 10 trading days.",
            "why_this_not_llm": (
                "LLM soft-ranking remains sample-limited; this uses replayable SEC filing text and fixed OHLCV snapshots."
            ),
            "why_not_candidate_pool_expansion": (
                "Recent broad and narrow static universe expansions were rejected; this tests event timing on existing covered tickers."
            ),
        },
        "historical_experiment_check": {
            "exp-20260504-007": (
                "Broad positive SEC filing-text language underperformed; this is not a positive-language score retune. "
                "It requires explicit guidance-raise syntax plus a non-positive SPY-relative first reaction."
            ),
            "exp-20260504-049": (
                "Default-off event overlay bundle was replay-positive but parity blocked; this run tests one fixed new packet separately."
            ),
            "exp-20260505-031": "One-day event follow-through confirmation was rejected; this run tests a contrarian weak-reaction packet instead.",
            "mechanism_no_go_check": (
                "Does not change LLM ranking, does not tune thresholds, does not broaden the universe, and does not promote any event sleeve live."
            ),
        },
        "parameters": {
            "sec_text_file": _repo_rel(SEC_TEXT_PATH),
            "form_base": "8-K",
            "required_item_code": REQUIRED_ITEM_CODE,
            "guidance_raise_hits_min": 1,
            "guidance_cut_hits_required": 0,
            "reaction_excess_return_max": 0.0,
            "entry_rule": "next trading day's open after first reaction date",
            "hold_days": HOLD_DAYS,
            "event_notional": EVENT_NOTIONAL,
            "max_event_positions": MAX_EVENT_POSITIONS,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "core_initial_capital": INITIAL_CAPITAL,
            "selection_order": "entry_date asc, ticker asc, accession_number asc",
        },
        "single_causal_variable": "add fixed SEC guidance-raise selloff recovery event PnL as a replay-only satellite overlay",
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
                "Uses SEC accepted_at/usable_trade_date fields and fixed OHLCV snapshots; "
                "public archive text is replayable but not proof of live-pipeline observation."
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
            "note": "This does not treat LLM as the problem; LLM ranking was skipped because current replay samples are insufficient.",
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
            "promotion_blocker_if_accepted": "requires shared default-off event sleeve adapter in production and backtest before any order impact",
        },
        "decision_rationale": rationale,
        "next_action": next_action,
        "risk_note": (
            "This could miss profitable guidance-raise names that rally immediately and keep trending; "
            "the experiment intentionally tests only the weak-reaction subset."
        ),
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
