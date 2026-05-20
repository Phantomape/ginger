"""exp-20260520-039: SEC buyback remaining-capacity signal.

Alpha search on one causal variable: require a replayable buyback disclosure to
include explicit remaining/available authorization capacity, instead of using
the broader rejected buyback credibility sleeve.
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from experiments.exp_20260514_010_sec_buyback_credibility_sleeve import (  # noqa: E402
    EVENT_NOTIONAL,
    HOLD_DAYS,
    INITIAL_CAPITAL,
    MAX_EVENT_POSITIONS,
    SEC_TEXT_PATH,
    _buyback_credibility,
    _candidate_trade,
    _combined_metrics as _combined_metrics_from_overlay,
    _core_metrics,
    _delta,
    _event_equity_curve,
    _gate4,
    _load_core_result,
    _load_price_map,
    _repo_rel,
    _safe,
    _select_event_trades,
    _slim_event,
    _write_json,
    _write_text,
    _window_name,
)
from sec_event_queue import evaluate_first_reaction, load_sec_filing_text_rows, semantic_text  # noqa: E402


EXP_ID = "exp-20260520-039"
STEM = "sec_buyback_remaining_capacity_signal"
TITLE = "SEC Buyback Remaining Capacity Signal"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
OPEN_POSITIONS_JSON = REPO_ROOT / "operator_inputs" / "open_positions.json"

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

REMAINING_CAPACITY_RE = re.compile(
    r"\b(remaining|available|availability|unused|unutilized|unutilised|left|capacity)\b"
    r".{0,180}\b(repurchase|buyback|authorization|authorisation|program|shares|dollars?)\b"
    r"|"
    r"\b(repurchase|buyback|authorization|authorisation|program)\b"
    r".{0,180}\b(remaining|available|availability|unused|unutilized|unutilised|left|capacity)\b",
    re.IGNORECASE | re.DOTALL,
)
MONEY_OR_SHARE_RE = re.compile(
    r"\$\s?\d|\b\d+(?:\.\d+)?\s?(million|billion|shares)\b",
    re.IGNORECASE,
)
PROGRAM_END_RE = re.compile(
    r"\b(expired|terminated|suspend(?:ed|s|ing)?|no remaining authorization|no amounts? remaining)\b",
    re.IGNORECASE,
)


def _float(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if math.isfinite(number) else 0.0


def _round(value: Any, digits: int = 6) -> Any:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return round(float(value), digits)
    return value


def _remaining_capacity_signal(text: str) -> dict[str, Any]:
    remaining = bool(REMAINING_CAPACITY_RE.search(text))
    amount = bool(MONEY_OR_SHARE_RE.search(text))
    ended = bool(PROGRAM_END_RE.search(text))
    return {
        "remaining_capacity_language": remaining,
        "amount_or_share_context": amount,
        "program_end_or_suspend_language": ended,
        "buyback_remaining_capacity_signal": bool(remaining and amount and not ended),
    }


def _position_field_check() -> dict[str, Any]:
    if not OPEN_POSITIONS_JSON.exists():
        return {"passed": False, "reason": "operator_inputs/open_positions.json missing"}
    payload = json.loads(OPEN_POSITIONS_JSON.read_text(encoding="utf-8"))
    positions = payload.get("positions") if isinstance(payload, dict) else payload
    if not isinstance(positions, list):
        return {"passed": False, "reason": "open_positions payload is not a list"}
    missing = []
    for idx, position in enumerate(positions):
        if not isinstance(position, dict):
            missing.append({"index": idx, "reason": "not_object"})
            continue
        absent = [
            field
            for field in ("entry_date", "target_price")
            if position.get(field) in (None, "")
        ]
        if absent:
            missing.append({
                "index": idx,
                "ticker": position.get("ticker"),
                "missing_fields": absent,
            })
    return {
        "passed": not missing,
        "path": _repo_rel(OPEN_POSITIONS_JSON),
        "position_count": len(positions),
        "missing_entry_date_or_target_price": missing,
    }


def _candidate_events(
    rows: list[dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    min_start = min(window["start"] for window in WINDOWS.values())
    max_end = max(window["end"] for window in WINDOWS.values())
    spy_rows = prices.get("SPY") or []
    skipped = Counter()
    full_buckets = Counter()
    capacity_buckets = Counter()
    full_candidates: list[dict[str, Any]] = []
    capacity_candidates: list[dict[str, Any]] = []
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
        bucket, credibility_signals = _buyback_credibility(text)
        if bucket is None:
            if credibility_signals.get("buyback_term"):
                skipped["buyback_keyword_not_credible"] += 1
            else:
                skipped["no_buyback_term"] += 1
            continue

        capacity_signals = _remaining_capacity_signal(text)
        event = {
            **row,
            "buyback_credibility_bucket": bucket,
            "buyback_credibility_signals": credibility_signals,
            "buyback_remaining_capacity_signals": capacity_signals,
            **evaluate_first_reaction(row, prices, spy_rows),
        }
        if event.get("price_status") != "covered":
            skipped[f"price_{event.get('price_status')}"] += 1
            continue

        slim = {**_slim_event(event), "buyback_remaining_capacity_signals": capacity_signals}
        slim["window"] = _window_name(usable)
        full_buckets[bucket] += 1
        full_candidates.append(slim)
        if capacity_signals["buyback_remaining_capacity_signal"]:
            capacity_buckets[bucket] += 1
            capacity_candidates.append(slim)
        else:
            skipped["credible_buyback_without_remaining_capacity"] += 1

    return (
        sorted(full_candidates, key=_event_sort_key),
        sorted(capacity_candidates, key=_event_sort_key),
        {
            "raw_rows": len(rows),
            "evaluated_rows_in_windows": evaluated_rows,
            "full_credibility_event_count": len(full_candidates),
            "remaining_capacity_event_count": len(capacity_candidates),
            "full_credibility_bucket_counts": dict(sorted(full_buckets.items())),
            "remaining_capacity_bucket_counts": dict(sorted(capacity_buckets.items())),
            "skipped_counts": dict(sorted(skipped.items())),
        },
    )


def _event_sort_key(event: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(event.get("usable_trade_date") or ""),
        str(event.get("ticker") or ""),
        str(event.get("accession_number") or ""),
    )


def _aggregate_delta(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
    gate_by_window: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    before_ev = sum(_float(row.get("expected_value_score")) for row in before.values())
    after_ev = sum(_float(row.get("expected_value_score")) for row in after.values())
    before_pnl = sum(_float(row.get("total_pnl")) for row in before.values())
    after_pnl = sum(_float(row.get("total_pnl")) for row in after.values())
    return {
        "baseline_ev_sum": round(before_ev, 4),
        "after_ev_sum": round(after_ev, 4),
        "ev_delta_sum": round(after_ev - before_ev, 4),
        "ev_delta_pct": round((after_ev - before_ev) / before_ev, 6) if before_ev else None,
        "baseline_pnl_sum": round(before_pnl, 2),
        "after_pnl_sum": round(after_pnl, 2),
        "pnl_delta": round(after_pnl - before_pnl, 2),
        "pnl_delta_pct": round((after_pnl - before_pnl) / before_pnl, 6) if before_pnl else None,
        "windows_ev_improved": sum(
            1
            for label in WINDOWS
            if _float(after[label].get("expected_value_score"))
            > _float(before[label].get("expected_value_score"))
        ),
        "windows_ev_regressed": sum(
            1
            for label in WINDOWS
            if _float(after[label].get("expected_value_score"))
            < _float(before[label].get("expected_value_score"))
        ),
        "windows_pnl_improved": sum(
            1
            for label in WINDOWS
            if _float(after[label].get("total_pnl")) > _float(before[label].get("total_pnl"))
        ),
        "windows_pnl_regressed": sum(
            1
            for label in WINDOWS
            if _float(after[label].get("total_pnl")) < _float(before[label].get("total_pnl"))
        ),
        "windows_material_ev_or_pnl": sum(
            1
            for label in WINDOWS
            if gate_by_window[label]["passes_material_ev"] or gate_by_window[label]["passes_pnl"]
        ),
        "max_drawdown_delta_max": round(
            max(
                _float(after[label].get("max_drawdown_pct"))
                - _float(before[label].get("max_drawdown_pct"))
                for label in WINDOWS
            ),
            6,
        ),
    }


def _single_ticker_positive_share(details: dict[str, dict[str, Any]]) -> float | None:
    by_ticker: defaultdict[str, float] = defaultdict(float)
    for detail in details.values():
        for trade in detail.get("capacity_selected_trades") or []:
            pnl = _float(trade.get("pnl"))
            if pnl > 0:
                by_ticker[str(trade.get("ticker") or "").upper()] += pnl
    total = sum(by_ticker.values())
    if total <= 0:
        return None
    return round(max(by_ticker.values()) / total, 4)


def _combined_metrics(
    result: dict[str, Any],
    event_curve: list[dict[str, Any]],
    event_trades: list[dict[str, Any]],
) -> dict[str, Any]:
    if not event_trades and not any(_float(row.get("event_pnl")) for row in event_curve):
        metrics = dict(_core_metrics(result))
        metrics.update(
            {
                "core_trade_count": len(result.get("trades") or []),
                "event_trade_count": 0,
                "event_pnl": 0.0,
                "combined_equity_curve": [
                    (str(day), _float(equity)) for day, equity in result.get("equity_curve", [])
                ],
            }
        )
        return metrics
    return _combined_metrics_from_overlay(result, event_curve, event_trades)


def _aggregate_gate4(
    aggregate_vs_core: dict[str, Any],
    aggregate_vs_full: dict[str, Any],
    details: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    selected = sum(int(row.get("capacity_selected_trade_count") or 0) for row in details.values())
    single_share = _single_ticker_positive_share(details)
    no_core_regression = aggregate_vs_core["windows_ev_regressed"] == 0
    improves_full = (
        aggregate_vs_full["ev_delta_sum"] > 0.0
        and aggregate_vs_full["pnl_delta"] > 0.0
        and aggregate_vs_full["windows_ev_regressed"] == 0
    )
    material = (
        aggregate_vs_core["ev_delta_pct"] is not None
        and aggregate_vs_core["ev_delta_pct"] > 0.10
    ) or (
        aggregate_vs_core["pnl_delta_pct"] is not None
        and aggregate_vs_core["pnl_delta_pct"] > 0.05
    )
    sample_ok = selected >= 5 and (single_share is None or single_share <= 0.60)
    drawdown_ok = aggregate_vs_core["max_drawdown_delta_max"] <= 0.005
    return {
        "passed": bool(no_core_regression and improves_full and material and sample_ok and drawdown_ok),
        "no_core_ev_regression": bool(no_core_regression),
        "improves_vs_full_buyback_credibility": bool(improves_full),
        "material_vs_core": bool(material),
        "sample_guard_passed": bool(sample_ok),
        "drawdown_guard_passed": bool(drawdown_ok),
        "capacity_selected_event_trades": selected,
        "sample_guard_min_trades": 5,
        "single_ticker_positive_share": single_share,
        "single_ticker_positive_share_guard": "<= 0.60",
    }


def _append_experiment_log(payload: dict[str, Any]) -> None:
    compact = json.dumps(_safe(payload), ensure_ascii=True, separators=(",", ":"))
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
    else:
        EXPERIMENT_LOG.write_text(compact + "\n", encoding="utf-8")


def _write_ticket(payload: dict[str, Any]) -> None:
    ticket = {
        "experiment_id": EXP_ID,
        "title": TITLE,
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
            "aggregate_delta_vs_full_buyback": payload["aggregate_delta_vs_full_buyback"],
            "gate4": payload["gate4"],
        },
    }
    _write_json(TICKET_JSON, ticket)


def _write_report(payload: dict[str, Any]) -> None:
    lines = [
        f"# {EXP_ID} SEC Buyback Remaining Capacity Signal",
        "",
        f"- decision: `{payload['decision']}`",
        f"- status: `{payload['status']}`",
        f"- aggregate EV delta vs core: `{payload['aggregate_delta_vs_core']['ev_delta_sum']}`",
        f"- aggregate PnL delta vs core: `{payload['aggregate_delta_vs_core']['pnl_delta']}`",
        f"- aggregate EV delta vs full buyback: `{payload['aggregate_delta_vs_full_buyback']['ev_delta_sum']}`",
        f"- selected capacity trades: `{payload['gate4']['capacity_selected_event_trades']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Three-Window Result",
        "",
        "| Window | Core EV | Full buyback EV | Capacity EV | dEV vs core | dEV vs full | Core PnL | Capacity PnL | Event PnL | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        core = payload["before_metrics"][label]
        full = payload["full_buyback_metrics"][label]
        after = payload["after_metrics"][label]
        d_core = payload["deltas_vs_core"][label]
        d_full = payload["deltas_vs_full_buyback"][label]
        lines.append(
            f"| {label} | {core['expected_value_score']} | {full['expected_value_score']} | "
            f"{after['expected_value_score']} | {d_core['expected_value_score']} | "
            f"{d_full['expected_value_score']} | ${core['total_pnl']:,.2f} | "
            f"${after['total_pnl']:,.2f} | ${_float(after.get('event_pnl')):,.2f} | "
            f"{core['trade_count']} -> {after['trade_count']} |"
        )
    lines.extend(
        [
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Data Availability",
            "",
            "```json",
            json.dumps(payload["data_availability"], indent=2, sort_keys=True),
            "```",
            "",
            "## Decision",
            "",
            payload["decision_rationale"],
            "",
            "## Production Impact",
            "",
            "No shared policy, backtester adapter, run adapter, order path, or live/default strategy behavior changed.",
            "",
        ]
    )
    _write_text(ARTIFACT_MD, "\n".join(lines) + "\n")


def build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    prices = _load_price_map()
    rows = load_sec_filing_text_rows(SEC_TEXT_PATH)
    full_events, capacity_events, data_availability = _candidate_events(rows, prices)
    full_trade_candidates = [_candidate_trade(event, prices) for event in full_events]
    capacity_trade_candidates = [_candidate_trade(event, prices) for event in capacity_events]

    before_metrics: dict[str, dict[str, Any]] = OrderedDict()
    full_metrics: dict[str, dict[str, Any]] = OrderedDict()
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    details: dict[str, dict[str, Any]] = OrderedDict()
    core_run_audit: dict[str, dict[str, Any]] = OrderedDict()

    for label, window in WINDOWS.items():
        result = _load_core_result(window)
        full_selected, full_skipped = _select_event_trades(
            full_trade_candidates,
            start=window["start"],
            end=window["end"],
        )
        capacity_selected, capacity_skipped = _select_event_trades(
            capacity_trade_candidates,
            start=window["start"],
            end=window["end"],
        )
        full_curve = _event_equity_curve(
            full_selected,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        capacity_curve = _event_equity_curve(
            capacity_selected,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        before_metrics[label] = _core_metrics(result)
        full_metrics[label] = _combined_metrics(result, full_curve, full_selected)
        after_metrics[label] = _combined_metrics(result, capacity_curve, capacity_selected)
        details[label] = {
            "full_candidate_event_count": sum(
                1
                for event in full_events
                if window["start"] <= str(event.get("usable_trade_date") or "")[:10] <= window["end"]
            ),
            "capacity_candidate_event_count": sum(
                1
                for event in capacity_events
                if window["start"] <= str(event.get("usable_trade_date") or "")[:10] <= window["end"]
            ),
            "full_selected_trade_count": len(full_selected),
            "capacity_selected_trade_count": len(capacity_selected),
            "full_selected_pnl": round(sum(_float(trade.get("pnl")) for trade in full_selected), 2),
            "capacity_selected_pnl": round(sum(_float(trade.get("pnl")) for trade in capacity_selected), 2),
            "full_skipped_capacity": full_skipped,
            "capacity_skipped_capacity": capacity_skipped,
            "capacity_selected_trades": capacity_selected,
        }
        core_run_audit[label] = {
            "converged": bool((result.get("convergence") or {}).get("converged")),
            "known_biases": result.get("known_biases"),
            "ohlcv_source": (result.get("known_biases") or {}).get("ohlcv_source"),
        }

    deltas_vs_core = {label: _delta(before_metrics[label], after_metrics[label]) for label in WINDOWS}
    deltas_vs_full = {label: _delta(full_metrics[label], after_metrics[label]) for label in WINDOWS}
    gate_by_window_core = {label: _gate4(before_metrics[label], after_metrics[label]) for label in WINDOWS}
    gate_by_window_full = {label: _gate4(full_metrics[label], after_metrics[label]) for label in WINDOWS}
    aggregate_vs_core = _aggregate_delta(before_metrics, after_metrics, gate_by_window_core)
    aggregate_vs_full = _aggregate_delta(full_metrics, after_metrics, gate_by_window_full)
    gate = _aggregate_gate4(aggregate_vs_core, aggregate_vs_full, details)

    if gate["passed"]:
        status = "promising_replay_only"
        decision = "positive_replay_only_requires_shared_buyback_adapter"
        rationale = (
            "Remaining-capacity buyback disclosures cleared the replay gate, but no "
            "shared production/backtest buyback adapter was changed. Treat as a "
            "candidate for a separate default-off adapter experiment, not live alpha."
        )
    elif aggregate_vs_core["ev_delta_sum"] > 0 and aggregate_vs_core["windows_ev_regressed"] == 0:
        status = "rejected"
        decision = "rejected_positive_not_material"
        rationale = (
            "Remaining-capacity buyback disclosures were directionally positive versus "
            "core but did not clear materiality/sample/tail gates."
        )
    else:
        status = "rejected"
        decision = "rejected_buyback_remaining_capacity_signal"
        rationale = (
            "Remaining-capacity buyback disclosures did not improve the canonical "
            "three-window evidence enough to justify a new default-off sleeve branch."
        )

    payload = {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "title": TITLE,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": (
            "SEC buyback disclosures with explicit remaining or available repurchase "
            "authorization capacity may be a cleaner capital-return alpha than broad "
            "buyback credibility, because remaining capacity can represent continuing "
            "corporate demand rather than only stale historical execution."
        ),
        "change_type": "event_field_replay",
        "mechanism_family": "sec_buyback_remaining_capacity_event_sleeve",
        "trial_family": "sec_buyback_remaining_capacity_signal",
        "changed_variable": "buyback_remaining_capacity_signal",
        "single_causal_variable": (
            "require amount-backed remaining/available buyback capacity language "
            "inside already credible SEC buyback disclosures"
        ),
        "prior_trial_count": 2,
        "nearby_prior_experiments": [
            "exp-20260514-006",
            "exp-20260514-010",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "new_production_visible_field",
        "gate_questions": {
            "1_alpha_hypothesis": "entry / external event overlay: buyback remaining-capacity field",
            "2_history_check": (
                "Generic buyback authorization drift was blocked, and the broader "
                "buyback credibility overlay regressed one fixed window."
            ),
            "3_single_variable": "Only the remaining-capacity qualifier changes.",
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; EV first, no core EV "
                "regression, improvement versus full buyback credibility, material "
                "aggregate lift, drawdown <= 0.5pp, sample/tail guards."
            ),
            "5_reproducibility": f".venv\\Scripts\\python.exe quant\\experiments\\{Path(__file__).name}",
        },
        "parameters": {
            "sec_text_file": _repo_rel(SEC_TEXT_PATH),
            "base_buyback_credibility_baseline": "exp-20260514-010 full credibility taxonomy",
            "field_definition": {
                "requires_remaining_capacity_language": True,
                "requires_amount_or_share_context": True,
                "excludes_program_end_or_suspend_language": True,
            },
            "entry_rule": "next trading day's open after first reaction date",
            "hold_days": HOLD_DAYS,
            "event_notional": EVENT_NOTIONAL,
            "max_event_positions": MAX_EVENT_POSITIONS,
            "core_initial_capital": INITIAL_CAPITAL,
            "locked_variables": [
                "core universe",
                "core signal generation",
                "core candidate ranking",
                "core position sizing",
                "core exits",
                "LLM/news replay",
                "SEC text source",
                "buyback credibility taxonomy",
                "event notional",
                "event holding period",
                "event capacity",
            ],
        },
        "date_range": {
            label: f"{window['start']} -> {window['end']}"
            for label, window in WINDOWS.items()
        },
        "backtest_protocol": "docs/backtesting.md canonical three fixed windows",
        "market_regime_summary": {label: window["state_note"] for label, window in WINDOWS.items()},
        "gate1": {
            "protocol": "docs/backtesting.md canonical three fixed windows",
            "baseline_artifact": "data/experiments/exp-20260517-009/#core accepted baseline; rerun in this script",
        },
        "gate2": _position_field_check(),
        "gate3": {
            "new_core_filter_added": False,
            "min_survival_rate": min(_float(row.get("survival_rate")) for row in before_metrics.values()),
            "passed": min(_float(row.get("survival_rate")) for row in before_metrics.values()) >= 0.05,
        },
        "before_metrics": before_metrics,
        "full_buyback_metrics": full_metrics,
        "after_metrics": after_metrics,
        "deltas_vs_core": deltas_vs_core,
        "deltas_vs_full_buyback": deltas_vs_full,
        "aggregate_delta_vs_core": aggregate_vs_core,
        "aggregate_delta_vs_full_buyback": aggregate_vs_full,
        "gate4": gate,
        "gate4_by_window_vs_core": gate_by_window_core,
        "gate4_by_window_vs_full_buyback": gate_by_window_full,
        "event_details": details,
        "data_availability": {
            **data_availability,
            "remaining_capacity_tickers": sorted(
                {str(event.get("ticker") or "").upper() for event in capacity_events}
            ),
            "pit_status": (
                "Uses SEC accepted_at/usable_trade_date and fixed OHLCV snapshots; "
                "archive text is a replayable public-PIT proxy, not proof production saw it live."
            ),
        },
        "core_run_audit": core_run_audit,
        "expected_value_score_delta": aggregate_vs_core["ev_delta_sum"],
        "total_pnl_delta": aggregate_vs_core["pnl_delta"],
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": "LLM soft-ranking remains replay-limited; this uses deterministic SEC text fields.",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": True,
            "production_signal_path_changed": False,
            "production_orders_changed": False,
            "live_slots_changed": False,
            "promotion_blocker_if_positive": (
                "Requires a shared default-off buyback queue/sleeve surfaced by run.py "
                "and replayed by backtester before any trade-enabled behavior."
            ),
        },
        "why_not_other_changes": (
            "State-surface and broad-market scalar retunes are anti-repeat/strict-gated; "
            "Form 4/options remains forward-data limited; DTE/payment-network core "
            "governance just failed. This tests one new SEC buyback field."
        ),
        "known_risks": [
            "SEC archive text is a public-PIT proxy, not proof of historical production ingestion.",
            "The regex field can confuse boilerplate remaining-authority disclosures with fresh capital return intent.",
            "If positive, replay-only evidence still needs a shared default-off adapter before promotion.",
        ],
        "decision_rationale": rationale,
        "rejection_reason": None if gate["passed"] else rationale,
        "next_evidence_needed": (
            "If rejected, do not retry nearby buyback keyword/capacity slices without "
            "forward closed outcomes or richer issuer-level buyback transparency fields."
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
        ],
        "anti_js": "No JavaScript was used.",
    }
    return payload


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_ticket(payload)
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
                "aggregate_delta_vs_core": payload["aggregate_delta_vs_core"],
                "aggregate_delta_vs_full_buyback": payload["aggregate_delta_vs_full_buyback"],
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
