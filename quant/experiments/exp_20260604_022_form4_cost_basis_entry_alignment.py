"""Replay Form 4 cost-basis entry alignment as a candidate-pool scout.

This keeps the core strategy and raw Form 4 forward queue fixed. The single
tested variable is whether the next tradable entry open is no more than 5%
above the event's weighted insider open-market purchase price.
"""

from __future__ import annotations

import json
from collections import OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260530_003_form4_ownership_delta_forward_queue as prior


EXP_ID = "exp-20260604-022"
STEM = "form4_cost_basis_entry_alignment"
OUT_DIR = prior.REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / "form4_cost_basis_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / "form4_cost_basis_after_aggregate.json"
RAW_AGG_JSON = OUT_DIR / "form4_cost_basis_raw_form4_aggregate.json"
LOG_JSON = prior.REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = prior.REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
DOC_TICKET_JSON = prior.REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXP_ID}.json"
CARD_MD = prior.REPO_ROOT / "experiments" / "cards" / f"{EXP_ID}.md"
MANIFEST_JSON = prior.REPO_ROOT / "experiments" / "manifests" / f"{EXP_ID}.json"
ARTIFACT_MD = prior.REPO_ROOT / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"
EXPERIMENT_LOG = prior.REPO_ROOT / "docs" / "experiment_log.jsonl"

MAX_ENTRY_TO_COST_BASIS = 1.05
INITIAL_CAPITAL = 100_000.0


def _round(value: Any, digits: int = 6) -> Any:
    if isinstance(value, (int, float)):
        return round(float(value), digits)
    return value


def _eligible_purchase_row(row: dict[str, Any]) -> bool:
    value = prior._float_or_none(row.get("transaction_value")) or 0.0
    shares = prior._float_or_none(row.get("shares")) or 0.0
    price = prior._float_or_none(row.get("price"))
    return (
        bool(row.get("open_market_purchase_flag"))
        and bool(row.get("pit_safe_flag"))
        and str(row.get("acquired_disposed_code") or "").upper() == "A"
        and not bool(row.get("10b5_1_flag"))
        and not bool(row.get("option_exercise_flag"))
        and bool(row.get("is_officer") or row.get("is_director") or row.get("is_10pct_owner"))
        and value > 0.0
        and shares > 0.0
        and price is not None
        and price > 0.0
    )


def _cost_basis_index(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    by_event: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        if not _eligible_purchase_row(row):
            continue
        ticker = str(row.get("ticker") or "").upper()
        usable = prior._date10(row.get("usable_trade_date"))
        if not ticker or not usable:
            continue
        value = prior._float_or_none(row.get("transaction_value")) or 0.0
        shares = prior._float_or_none(row.get("shares")) or 0.0
        price = prior._float_or_none(row.get("price")) or 0.0
        event = by_event.setdefault(
            (ticker, usable),
            {
                "cost_basis_transaction_count": 0,
                "cost_basis_total_purchase_value": 0.0,
                "cost_basis_total_purchase_shares": 0.0,
                "min_reported_purchase_price": None,
                "max_reported_purchase_price": None,
                "sample_cost_basis_transactions": [],
            },
        )
        event["cost_basis_transaction_count"] += 1
        event["cost_basis_total_purchase_value"] += value
        event["cost_basis_total_purchase_shares"] += shares
        event["min_reported_purchase_price"] = (
            price
            if event["min_reported_purchase_price"] is None
            else min(float(event["min_reported_purchase_price"]), price)
        )
        event["max_reported_purchase_price"] = (
            price
            if event["max_reported_purchase_price"] is None
            else max(float(event["max_reported_purchase_price"]), price)
        )
        samples = event["sample_cost_basis_transactions"]
        if len(samples) < 5:
            samples.append(
                {
                    "owner_name": row.get("owner_name"),
                    "price": _round(price),
                    "shares": _round(shares, 4),
                    "transaction_value": _round(value, 2),
                }
            )
    for event in by_event.values():
        shares = float(event["cost_basis_total_purchase_shares"] or 0.0)
        value = float(event["cost_basis_total_purchase_value"] or 0.0)
        event["weighted_insider_purchase_price"] = _round(value / shares) if shares > 0 else None
        event["cost_basis_total_purchase_value"] = _round(value, 2)
        event["cost_basis_total_purchase_shares"] = _round(shares, 4)
        event["min_reported_purchase_price"] = _round(event["min_reported_purchase_price"])
        event["max_reported_purchase_price"] = _round(event["max_reported_purchase_price"])
    return by_event


def _load_cost_basis_events() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not prior.FORM4_TRANSACTIONS_PATH.exists():
        return [], {"source_status": "missing_form4_transactions"}
    rows = prior.load_form4_transaction_rows(prior.FORM4_TRANSACTIONS_PATH)
    basis = _cost_basis_index(rows)
    raw_events, diagnostics = prior._load_forward_events()
    events: list[dict[str, Any]] = []
    for event in raw_events:
        ticker = str(event.get("ticker") or "").upper()
        usable = prior._date10(event.get("usable_trade_date"))
        row = {
            **event,
            **basis.get((ticker, usable), {}),
            "ticker": ticker,
            "usable_trade_date": usable,
        }
        row["cost_basis_ready"] = row.get("weighted_insider_purchase_price") is not None
        events.append(row)
    diagnostics.update(
        {
            "transaction_rows": len(rows),
            "cost_basis_index_event_count": len(basis),
            "events_with_cost_basis": sum(1 for row in events if row.get("cost_basis_ready")),
            "max_entry_to_cost_basis": MAX_ENTRY_TO_COST_BASIS,
        }
    )
    return sorted(events, key=lambda row: (row["usable_trade_date"], row["ticker"])), diagnostics


def _candidate_with_cost_basis(
    event: dict[str, Any],
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    candidate = prior._candidate_trade(event, prices)
    entry_open = prior._float_or_none(candidate.get("entry_open"))
    purchase_price = prior._float_or_none(candidate.get("weighted_insider_purchase_price"))
    if candidate.get("status") != "price_ready":
        candidate["cost_basis_alignment_status"] = candidate.get("status")
        candidate["entry_to_weighted_purchase_price"] = None
        candidate["entry_aligned_to_insider_cost_basis"] = False
        return candidate
    if entry_open is None or purchase_price is None or purchase_price <= 0.0:
        candidate["cost_basis_alignment_status"] = "missing_cost_basis"
        candidate["entry_to_weighted_purchase_price"] = None
        candidate["entry_aligned_to_insider_cost_basis"] = False
        return candidate
    ratio = entry_open / purchase_price
    candidate["entry_to_weighted_purchase_price"] = _round(ratio)
    candidate["entry_aligned_to_insider_cost_basis"] = ratio <= MAX_ENTRY_TO_COST_BASIS
    candidate["cost_basis_alignment_status"] = (
        "aligned_to_cost_basis"
        if candidate["entry_aligned_to_insider_cost_basis"]
        else "entry_chased_above_cost_basis"
    )
    return candidate


def _event_candidates(
    events: list[dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
    *,
    aligned_only: bool,
) -> list[dict[str, Any]]:
    candidates = [_candidate_with_cost_basis(event, prices) for event in events]
    if not aligned_only:
        return candidates
    return [row for row in candidates if row.get("entry_aligned_to_insider_cost_basis")]


def _aggregate_delta(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    before_ev = sum(float(row.get("expected_value_score") or 0.0) for row in before.values())
    after_ev = sum(float(row.get("expected_value_score") or 0.0) for row in after.values())
    before_pnl = sum(float(row.get("total_pnl") or 0.0) for row in before.values())
    after_pnl = sum(float(row.get("total_pnl") or 0.0) for row in after.values())
    max_drawdown_drift = max(
        float(after[label].get("max_drawdown_pct") or 0.0)
        - float(before[label].get("max_drawdown_pct") or 0.0)
        for label in before
    )
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
        "max_drawdown_drift": round(max_drawdown_drift, 6),
    }


def _aggregate_for_close(metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ev_sum = sum(float(row.get("expected_value_score") or 0.0) for row in metrics.values())
    pnl_sum = sum(float(row.get("total_pnl") or 0.0) for row in metrics.values())
    trade_count = sum(int(row.get("trade_count") or 0) for row in metrics.values())
    wins = sum(int(row.get("winning_trades") or 0) for row in metrics.values())
    return {
        "expected_value_score": round(ev_sum, 4),
        "sharpe_daily": None,
        "total_pnl": round(pnl_sum, 2),
        "max_drawdown_pct": max(float(row.get("max_drawdown_pct") or 0.0) for row in metrics.values()),
        "win_rate": round(wins / trade_count, 6) if trade_count else None,
        "total_trades": trade_count,
        "survival_rate": min(float(row.get("survival_rate") or 0.0) for row in metrics.values()),
        "benchmarks": {"strategy_total_return_pct": round(pnl_sum / INITIAL_CAPITAL, 6)},
    }


def _positive_pnl_concentration(details: dict[str, dict[str, Any]]) -> dict[str, Any]:
    by_ticker: defaultdict[str, float] = defaultdict(float)
    for detail in details.values():
        for trade in detail.get("cost_basis_selected_trades") or []:
            pnl = float(trade.get("pnl") or 0.0)
            if pnl > 0:
                by_ticker[str(trade.get("ticker") or "").upper()] += pnl
    total = sum(by_ticker.values())
    if total <= 0.0:
        return {
            "single_ticker_positive_share": None,
            "positive_pnl_hhi": None,
            "positive_pnl_by_ticker": {},
        }
    shares = {ticker: value / total for ticker, value in by_ticker.items()}
    return {
        "single_ticker_positive_share": round(max(shares.values()), 6),
        "positive_pnl_hhi": round(sum(value * value for value in shares.values()), 6),
        "positive_pnl_by_ticker": {
            ticker: round(value, 2)
            for ticker, value in sorted(by_ticker.items())
        },
    }


def _metrics_for_log(metrics: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        label: {key: value for key, value in row.items() if key != "combined_equity_curve"}
        for label, row in metrics.items()
    }


def _gate_result(
    core_delta: dict[str, Any],
    raw_delta: dict[str, Any],
    details: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    selected = sum(int(row.get("cost_basis_selected_trade_count") or 0) for row in details.values())
    target_windows = [
        label for label, row in details.items() if int(row.get("cost_basis_selected_trade_count") or 0) > 0
    ]
    concentration = _positive_pnl_concentration(details)
    single_share = concentration["single_ticker_positive_share"]
    hhi = concentration["positive_pnl_hhi"]
    material = (
        core_delta["aggregate_ev_delta_pct"] is not None
        and core_delta["aggregate_ev_delta_pct"] > 0.10
    ) or (
        core_delta["aggregate_pnl_delta_pct"] is not None
        and core_delta["aggregate_pnl_delta_pct"] > 0.05
    )
    improves_core = (
        core_delta["aggregate_ev_delta"] > 0.0
        and core_delta["aggregate_pnl_delta"] > 0.0
        and core_delta["windows_ev_regressed"] == 0
        and core_delta["windows_pnl_regressed"] == 0
    )
    improves_raw = (
        raw_delta["aggregate_ev_delta"] > 0.0
        and raw_delta["aggregate_pnl_delta"] > 0.0
        and raw_delta["windows_ev_regressed"] == 0
        and raw_delta["windows_pnl_regressed"] == 0
    )
    drawdown_ok = core_delta["max_drawdown_drift"] <= 0.005
    sample_ok = (
        selected >= 8
        and len(target_windows) >= 3
        and (single_share is None or single_share <= 0.50)
        and (hhi is None or hhi <= 0.35)
    )
    failed = []
    if not improves_core:
        failed.append("does_not_improve_core_cleanly")
    if not improves_raw:
        failed.append("does_not_improve_raw_form4_queue")
    if not material:
        failed.append("not_material_vs_core")
    if not drawdown_ok:
        failed.append("drawdown_drift_too_high")
    if selected < 8:
        failed.append("target_sample_too_small")
    if len(target_windows) < 3:
        failed.append("target_window_coverage_too_small")
    if single_share is not None and single_share > 0.50:
        failed.append("single_ticker_concentration")
    if hhi is not None and hhi > 0.35:
        failed.append("positive_pnl_hhi_concentration")
    return {
        "passed": bool(material and improves_core and improves_raw and drawdown_ok and sample_ok),
        "failed_reasons": failed,
        "material_vs_core": bool(material),
        "improves_core_cleanly": bool(improves_core),
        "improves_vs_raw_form4": bool(improves_raw),
        "drawdown_guard_passed": bool(drawdown_ok),
        "max_drawdown_drift_guard": "<= 0.005",
        "cost_basis_selected_event_trades": selected,
        "target_trade_count_min": 8,
        "target_windows": target_windows,
        "target_window_count_min": 3,
        "single_ticker_positive_share": single_share,
        "single_ticker_positive_share_guard": "<= 0.50",
        "positive_pnl_hhi": hhi,
        "positive_pnl_hhi_guard": "<= 0.35",
        "sample_guard_passed": bool(sample_ok),
        "positive_pnl_by_ticker": concentration["positive_pnl_by_ticker"],
    }


def _append_experiment_log(payload: dict[str, Any]) -> None:
    row = {
        "experiment_id": EXP_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "status": payload["status"],
        "decision": payload["decision"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "changed_variable": payload["changed_variable"],
        "single_causal_variable": payload["single_causal_variable"],
        "hypothesis": payload["hypothesis"],
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "before_metrics": _metrics_for_log(payload["core_baseline_metrics"]),
        "raw_form4_metrics": _metrics_for_log(payload["raw_form4_metrics"]),
        "after_metrics": _metrics_for_log(payload["after_metrics"]),
        "aggregate_delta_vs_core": payload["aggregate_delta_vs_core"],
        "aggregate_delta_vs_raw_form4": payload["aggregate_delta_vs_raw_form4"],
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "artifact": prior._repo_rel(ARTIFACT_MD),
        "result_file": prior._repo_rel(OUT_JSON),
        "notes": payload["decision_rationale"],
    }
    compact = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    if EXPERIMENT_LOG.exists():
        lines = EXPERIMENT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        lines = [
            line
            for line in lines
            if f'"experiment_id":"{EXP_ID}"' not in line and f'"experiment_id": "{EXP_ID}"' not in line
        ]
        lines.append(compact)
        EXPERIMENT_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        EXPERIMENT_LOG.write_text(compact + "\n", encoding="utf-8")


def _write_report(payload: dict[str, Any]) -> None:
    lines = [
        "# Form 4 Cost-Basis Entry Alignment",
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
        "| Window | Core EV | Raw Form4 EV | Cost-Basis EV | Delta vs raw | Delta vs core | Core PnL | Cost-Basis PnL | Event PnL | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in prior.WINDOWS:
        core = payload["core_baseline_metrics"][label]
        raw = payload["raw_form4_metrics"][label]
        after = payload["after_metrics"][label]
        raw_delta = payload["deltas_vs_raw_form4"][label]
        core_delta = payload["deltas_vs_core"][label]
        lines.append(
            f"| {label} | {core['expected_value_score']} | {raw['expected_value_score']} | "
            f"{after['expected_value_score']} | {raw_delta['expected_value_score']} | "
            f"{core_delta['expected_value_score']} | ${core['total_pnl']:,.2f} | "
            f"${after['total_pnl']:,.2f} | ${float(after.get('event_pnl') or 0.0):,.2f} | "
            f"{core['trade_count']} -> {after['trade_count']} |"
        )
    lines.extend(
        [
            "",
            "## Aggregate vs Raw Form4",
            "",
            "```json",
            json.dumps(payload["aggregate_delta_vs_raw_form4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Aggregate vs Core",
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
            "```json",
            json.dumps(payload["production_impact"], indent=2, sort_keys=True),
            "```",
            "",
            "No JavaScript was used.",
        ]
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    CARD_MD.parent.mkdir(parents=True, exist_ok=True)
    CARD_MD.write_text("\n".join(lines[:55]) + "\n", encoding="utf-8")


def _write_ticket(payload: dict[str, Any]) -> None:
    ticket = prior._json_load(TICKET_JSON, {"experiment_id": EXP_ID})
    if not isinstance(ticket, dict):
        ticket = {"experiment_id": EXP_ID}
    ticket.update(
        {
            "status": payload["status"],
            "decision": payload["decision"],
            "completed_at": payload["timestamp"],
            "allowed_write_scope_actual": payload["related_files"],
            "result": {
                "artifact": prior._repo_rel(OUT_JSON),
                "before_aggregate": prior._repo_rel(BEFORE_AGG_JSON),
                "after_aggregate": prior._repo_rel(AFTER_AGG_JSON),
                "raw_form4_aggregate": prior._repo_rel(RAW_AGG_JSON),
                "log": prior._repo_rel(LOG_JSON),
                "report": prior._repo_rel(ARTIFACT_MD),
                "aggregate_delta_vs_core": payload["aggregate_delta_vs_core"],
                "aggregate_delta_vs_raw_form4": payload["aggregate_delta_vs_raw_form4"],
                "decision": payload["decision"],
            },
        }
    )
    prior._write_json(TICKET_JSON, ticket)
    prior._write_json(DOC_TICKET_JSON, ticket)


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = prior._json_load(MANIFEST_JSON, {})
    if not isinstance(manifest, dict):
        manifest = {}
    manifest.update(
        {
            "experiment_id": EXP_ID,
            "status": payload["status"],
            "decision": payload["decision"],
            "updated_at": payload["timestamp"],
            "result_files": [
                prior._repo_rel(OUT_JSON),
                prior._repo_rel(BEFORE_AGG_JSON),
                prior._repo_rel(AFTER_AGG_JSON),
                prior._repo_rel(RAW_AGG_JSON),
                prior._repo_rel(LOG_JSON),
                prior._repo_rel(ARTIFACT_MD),
            ],
        }
    )
    prior._write_json(MANIFEST_JSON, manifest)


def build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    universe = prior.get_universe()
    prices = prior._load_price_map()
    events, source_diagnostics = _load_cost_basis_events()
    raw_candidates = _event_candidates(events, prices, aligned_only=False)
    aligned_candidates = _event_candidates(events, prices, aligned_only=True)

    core_baseline: dict[str, dict[str, Any]] = OrderedDict()
    raw_metrics: dict[str, dict[str, Any]] = OrderedDict()
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    deltas_vs_raw: dict[str, dict[str, Any]] = OrderedDict()
    deltas_vs_core: dict[str, dict[str, Any]] = OrderedDict()
    details: dict[str, dict[str, Any]] = OrderedDict()

    for label, window in prior.WINDOWS.items():
        result = prior.BacktestEngine(
            universe,
            start=window["start"],
            end=window["end"],
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=window["snapshot"],
        ).run()
        raw_selected, raw_skipped = prior._select_event_trades(
            raw_candidates,
            start=window["start"],
            end=window["end"],
        )
        aligned_selected, aligned_skipped = prior._select_event_trades(
            aligned_candidates,
            start=window["start"],
            end=window["end"],
        )
        raw_curve = prior._event_equity_curve(
            raw_selected,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        aligned_curve = prior._event_equity_curve(
            aligned_selected,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        core_baseline[label] = prior._core_metrics(result)
        raw_metrics[label] = (
            prior._combined_metrics(result, raw_curve, raw_selected)
            if raw_selected
            else dict(core_baseline[label])
        )
        after_metrics[label] = (
            prior._combined_metrics(result, aligned_curve, aligned_selected)
            if aligned_selected
            else dict(core_baseline[label])
        )
        deltas_vs_raw[label] = prior._delta(raw_metrics[label], after_metrics[label])
        deltas_vs_core[label] = prior._delta(core_baseline[label], after_metrics[label])

        scoped_events = [
            row
            for row in events
            if window["start"] <= prior._date10(row.get("usable_trade_date")) <= window["end"]
        ]
        scoped_candidates = [
            row
            for row in raw_candidates
            if window["start"] <= prior._date10(row.get("usable_trade_date")) <= window["end"]
        ]
        details[label] = {
            "raw_forward_event_count": len(scoped_events),
            "cost_basis_ready_event_count": sum(1 for row in scoped_events if row.get("cost_basis_ready")),
            "raw_price_ready_count": sum(1 for row in scoped_candidates if row.get("status") == "price_ready"),
            "aligned_price_ready_count": sum(
                1
                for row in scoped_candidates
                if row.get("status") == "price_ready"
                and row.get("entry_aligned_to_insider_cost_basis")
            ),
            "entry_chased_above_cost_basis_count": sum(
                1
                for row in scoped_candidates
                if row.get("cost_basis_alignment_status") == "entry_chased_above_cost_basis"
            ),
            "raw_selected_trade_count": len(raw_selected),
            "cost_basis_selected_trade_count": len(aligned_selected),
            "raw_skipped_count": len(raw_skipped),
            "cost_basis_skipped_count": len(aligned_skipped),
            "cost_basis_selected_trades": aligned_selected,
            "raw_selected_trades": raw_selected,
            "cost_basis_skipped_candidates": aligned_skipped[:20],
        }

    aggregate_vs_raw = _aggregate_delta(raw_metrics, after_metrics)
    aggregate_vs_core = _aggregate_delta(core_baseline, after_metrics)
    gate = _gate_result(aggregate_vs_core, aggregate_vs_raw, details)
    actual_success = 1 if gate["passed"] else 0

    if gate["passed"]:
        decision = "observed_positive_requires_shared_default_off_adapter"
        status = "observed_only"
        rationale = (
            "Cost-basis entry alignment passed the three-window replay gate, but no "
            "production path changed. It must be promoted through a shared "
            "default-off adapter and parity tests before any trade-enabled use."
        )
    elif aggregate_vs_core["aggregate_ev_delta"] > 0 and aggregate_vs_core["aggregate_pnl_delta"] > 0:
        decision = "rejected_positive_not_promotable"
        status = "rejected"
        rationale = (
            "Cost-basis entry alignment was positive versus core, but failed the full "
            "Gate 4 standard once raw Form 4 replacement value, materiality, window "
            "stability, sample, and concentration were considered."
        )
    else:
        decision = "rejected_form4_cost_basis_entry_alignment"
        status = "rejected"
        rationale = (
            "Cost-basis entry alignment did not produce positive, stable three-window "
            "EV/PnL evidence versus the core baseline."
        )

    realized_failure = ",".join(gate["failed_reasons"]) if gate["failed_reasons"] else None
    prediction = {
        "success_probability": 0.14,
        "expected_ev_delta": 0.04,
        "expected_pnl_delta": 1200.0,
        "main_failure_modes": [
            "sample_too_thin",
            "does_not_improve_raw_form4_queue",
            "window_regression",
            "concentration",
        ],
        "confidence_reason": (
            "Raw Form 4 shadow outcomes were promising, but prior owner-count, "
            "ownership-delta, purchase-pressure, and overlap slices failed. "
            "Execution-time cost-basis alignment is a distinct free SEC field, "
            "but the event sample is thin."
        ),
        "recorded_at": "2026-06-04T18:07:30+00:00",
    }

    payload: dict[str, Any] = {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": (
            "PIT-safe SEC Form 4 meaningful-purchase candidates may have cleaner "
            "replacement value when the execution-time entry open remains within "
            "5% above the insider's disclosed weighted purchase cost basis."
        ),
        "change_type": "event_candidate_pool_replay",
        "mechanism_family": "form4_insider_cost_basis",
        "trial_family": "form4_cost_basis_alignment_event_satellite",
        "trial_variant_id": "cost_basis_entry_alignment_105",
        "changed_variable": "form4_entry_price_to_weighted_purchase_price_max_1_05",
        "single_causal_variable": "entry_open / weighted_insider_purchase_price <= 1.05",
        "prior_trial_count": 5,
        "nearby_prior_experiments": [
            "exp-20260529-002",
            "exp-20260530-003",
            "exp-20260530-011",
            "exp-20260531-002",
            "exp-20260602-016",
        ],
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "free_sec_form4_transaction_price_joined_to_execution_open",
        "prediction": prediction,
        "calibration": {
            "actual_decision": decision,
            "actual_success": actual_success,
            "predicted_success_probability": prediction["success_probability"],
            "brier_score": round((prediction["success_probability"] - actual_success) ** 2, 6),
            "predicted_failure_modes": prediction["main_failure_modes"],
            "realized_failure_mode": realized_failure,
            "predicted_failure_mode_hit": any(
                reason in gate["failed_reasons"]
                for reason in (
                    "target_sample_too_small",
                    "does_not_improve_raw_form4_queue",
                    "single_ticker_concentration",
                    "positive_pnl_hhi_concentration",
                    "window_regression",
                )
            ),
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "candidate-pool / entry: insider purchases should have better signal "
                "quality when the tradable entry has not already run far above the "
                "insider cost basis."
            ),
            "2_history_check": {
                "exp-20260529-002": "Form 4 role quality was positive versus core but not enough to promote.",
                "exp-20260530-003": "ownership-delta slice was positive versus core but not raw and not material.",
                "exp-20260530-011": "multi-filer owner-count slice failed replacement, sample, coverage, and concentration.",
                "exp-20260531-002": "purchase-pressure slice did not improve raw Form4 and had only 7 selected trades.",
                "exp-20260602-016": "Form 4 overlap/support side route failed raw/core comparator.",
                "exp-20260604-020": "revision-trajectory PEAD was observed-only due missing positive persistent rows.",
            },
            "3_single_causal_variable": "form4_entry_price_to_weighted_purchase_price_max_1_05",
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; must improve aggregate EV/PnL "
                "versus core and raw Form 4, avoid EV/PnL window regressions, pass "
                "drawdown, survival, target sample, and concentration guards."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260604_022_form4_cost_basis_entry_alignment.py"
            ),
        },
        "parameters": {
            "queue_name": prior.QUEUE_NAME,
            "rule_version": prior.RULE_VERSION,
            "forward_queue_min_total_purchase_value": prior.FORWARD_QUEUE_MIN_PURCHASE_VALUE,
            "max_entry_to_weighted_purchase_price": MAX_ENTRY_TO_COST_BASIS,
            "event_notional_usd": prior.EVENT_NOTIONAL,
            "max_event_positions": prior.MAX_EVENT_POSITIONS,
            "hold_days": prior.HOLD_DAYS,
            "round_trip_cost_pct": prior.ROUND_TRIP_COST_PCT,
            "locked_variables": [
                "core universe",
                "core signal generation",
                "core candidate ranking",
                "core position sizing",
                "core exits",
                "LLM/news replay settings",
                "Form 4 transaction parser",
                "Form 4 purchase-value threshold",
                "event notional",
                "event holding period",
                "event capacity",
            ],
        },
        "date_range": {
            label: f"{window['start']} -> {window['end']}"
            for label, window in prior.WINDOWS.items()
        },
        "backtest_protocol": "docs/backtesting.md canonical three fixed windows",
        "market_regime_summary": {
            label: window["state_note"]
            for label, window in prior.WINDOWS.items()
        },
        "gate1": {
            "protocol": "docs/backtesting.md canonical three fixed windows",
            "core_baseline_metrics": core_baseline,
        },
        "gate2": prior._position_field_check(),
        "gate3": {
            "new_core_filter_added": False,
            "min_survival_rate": min(float(row.get("survival_rate") or 0.0) for row in core_baseline.values()),
            "passed": min(float(row.get("survival_rate") or 0.0) for row in core_baseline.values()) >= 0.05,
        },
        "core_baseline_metrics": core_baseline,
        "raw_form4_metrics": raw_metrics,
        "after_metrics": after_metrics,
        "deltas_vs_raw_form4": deltas_vs_raw,
        "deltas_vs_core": deltas_vs_core,
        "aggregate_delta_vs_raw_form4": aggregate_vs_raw,
        "aggregate_delta_vs_core": aggregate_vs_core,
        "gate4": gate,
        "event_details": details,
        "decision_rationale": rationale,
        "source_diagnostics": {
            **source_diagnostics,
            "events_passing_cost_basis_alignment": sum(
                1
                for row in raw_candidates
                if row.get("status") == "price_ready"
                and row.get("entry_aligned_to_insider_cost_basis")
            ),
            "entry_to_cost_basis_distribution_sample": [
                {
                    "ticker": row.get("ticker"),
                    "usable_trade_date": row.get("usable_trade_date"),
                    "entry_open": row.get("entry_open"),
                    "weighted_insider_purchase_price": row.get("weighted_insider_purchase_price"),
                    "entry_to_weighted_purchase_price": row.get("entry_to_weighted_purchase_price"),
                    "status": row.get("cost_basis_alignment_status"),
                    "pnl": row.get("pnl"),
                }
                for row in sorted(
                    [row for row in raw_candidates if row.get("entry_to_weighted_purchase_price") is not None],
                    key=lambda event: float(event.get("entry_to_weighted_purchase_price") or 0.0),
                    reverse=True,
                )[:15]
            ],
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": (
                "The tested field is deterministic and replayable from free SEC "
                "Form 4 transaction data plus fixed OHLCV snapshots; recent "
                "LLM/revision soft-ranking lanes are data-limited."
            ),
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
                "A shared default-off Form 4 cost-basis queue/paper adapter must be "
                "wired through production and replay before any trade-enabled use."
            ),
        },
        "production_parity": {
            "alters_production_orders": False,
            "alters_live_watchlists": False,
            "alters_core_backtester": False,
            "default_enabled": False,
            "replay_only": True,
            "parity_note": (
                "No production path changed. A positive result is only an observed "
                "candidate until a shared default-off adapter and parity test exist."
            ),
        },
        "data_source": {
            "form4_transactions_path": prior._repo_rel(prior.FORM4_TRANSACTIONS_PATH),
            "pit_status": (
                "uses Form 4 accepted_at/usable_trade_date, transaction price, and "
                "fixed OHLCV snapshots; entry_open is evaluated only at execution time."
            ),
        },
        "related_files": [
            prior._repo_rel(OUT_JSON),
            prior._repo_rel(BEFORE_AGG_JSON),
            prior._repo_rel(AFTER_AGG_JSON),
            prior._repo_rel(RAW_AGG_JSON),
            prior._repo_rel(LOG_JSON),
            prior._repo_rel(TICKET_JSON),
            prior._repo_rel(DOC_TICKET_JSON),
            prior._repo_rel(CARD_MD),
            prior._repo_rel(MANIFEST_JSON),
            prior._repo_rel(ARTIFACT_MD),
            prior._repo_rel(Path(__file__)),
            prior._repo_rel(EXPERIMENT_LOG),
        ],
        "anti_js": "No JavaScript was used.",
    }
    return payload


def main() -> None:
    payload = build_payload()
    prior._write_json(OUT_JSON, payload)
    prior._write_json(BEFORE_AGG_JSON, _aggregate_for_close(payload["core_baseline_metrics"]))
    prior._write_json(AFTER_AGG_JSON, _aggregate_for_close(payload["after_metrics"]))
    prior._write_json(RAW_AGG_JSON, _aggregate_for_close(payload["raw_form4_metrics"]))
    prior._write_json(LOG_JSON, payload)
    _write_ticket(payload)
    _write_manifest(payload)
    _write_report(payload)
    _append_experiment_log(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "aggregate_delta_vs_raw_form4": payload["aggregate_delta_vs_raw_form4"],
                "aggregate_delta_vs_core": payload["aggregate_delta_vs_core"],
                "gate4": {
                    key: payload["gate4"][key]
                    for key in (
                        "passed",
                        "material_vs_core",
                        "improves_core_cleanly",
                        "improves_vs_raw_form4",
                        "drawdown_guard_passed",
                        "cost_basis_selected_event_trades",
                        "sample_guard_passed",
                        "single_ticker_positive_share",
                        "positive_pnl_hhi",
                        "failed_reasons",
                    )
                },
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
