"""Replay Form 4 purchase-pressure events as a bounded candidate-pool overlay.

This experiment keeps the core strategy and the raw Form 4 forward queue fixed.
The single tested variable is whether a PIT-safe meaningful purchase is large
relative to the ticker's prior 20-trading-day dollar volume.
"""

from __future__ import annotations

import json
import math
from collections import OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260530_003_form4_ownership_delta_forward_queue as prior


EXP_ID = "exp-20260531-002"
STEM = "form4_purchase_pressure_forward_queue"
OUT_DIR = prior.REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"exp_20260531_002_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / "form4_purchase_pressure_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / "form4_purchase_pressure_after_aggregate.json"
RAW_AGG_JSON = OUT_DIR / "form4_purchase_pressure_raw_form4_aggregate.json"
LOG_JSON = prior.REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = prior.REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
DOC_TICKET_JSON = prior.REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXP_ID}.json"
CARD_MD = prior.REPO_ROOT / "experiments" / "cards" / f"{EXP_ID}.md"
MANIFEST_JSON = prior.REPO_ROOT / "experiments" / "manifests" / f"{EXP_ID}.json"
ARTIFACT_MD = prior.REPO_ROOT / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"
EXPERIMENT_LOG = prior.REPO_ROOT / "docs" / "experiment_log.jsonl"

LOOKBACK_DAYS = 20
MIN_LOOKBACK_DAYS = 10
PURCHASE_PRESSURE_FLOOR = 0.0001
INITIAL_CAPITAL = 100_000.0


def _load_liquidity_map() -> dict[str, list[dict[str, Any]]]:
    by_ticker_date: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for window in prior.WINDOWS.values():
        payload = prior._json_load(prior.REPO_ROOT / window["snapshot"], {})
        ohlcv = payload.get("ohlcv") if isinstance(payload, dict) else {}
        if not isinstance(ohlcv, dict):
            continue
        for ticker, rows in ohlcv.items():
            if not isinstance(rows, list):
                continue
            ticker_key = str(ticker).upper()
            for row in rows:
                if not isinstance(row, dict) or not row.get("Date"):
                    continue
                date_key = str(row["Date"])[:10]
                close = prior._float_or_none(row.get("Close"))
                volume = prior._float_or_none(row.get("Volume"))
                if close is None or volume is None or volume <= 0.0:
                    continue
                by_ticker_date[ticker_key][date_key] = {
                    "date": date_key,
                    "close": close,
                    "volume": volume,
                    "dollar_volume": close * volume,
                }
    return {
        ticker: sorted(rows.values(), key=lambda row: row["date"])
        for ticker, rows in by_ticker_date.items()
    }


def _prior_adv(
    liquidity: dict[str, list[dict[str, Any]]],
    ticker: str,
    usable_trade_date: str,
) -> dict[str, Any]:
    rows = [
        row
        for row in liquidity.get(str(ticker).upper(), [])
        if row["date"] < usable_trade_date
    ][-LOOKBACK_DAYS:]
    if len(rows) < MIN_LOOKBACK_DAYS:
        return {
            "prior_20d_avg_dollar_volume": None,
            "prior_20d_dollar_volume_days": len(rows),
            "purchase_pressure_status": "insufficient_prior_liquidity_history",
        }
    average = sum(float(row["dollar_volume"]) for row in rows) / len(rows)
    return {
        "prior_20d_avg_dollar_volume": round(average, 2),
        "prior_20d_dollar_volume_days": len(rows),
        "purchase_pressure_status": "ready",
    }


def _annotate_purchase_pressure(
    events: list[dict[str, Any]],
    liquidity: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    annotated: list[dict[str, Any]] = []
    for event in events:
        ticker = str(event.get("ticker") or "").upper()
        usable = prior._date10(event.get("usable_trade_date"))
        row = {**event, "ticker": ticker, "usable_trade_date": usable}
        adv = _prior_adv(liquidity, ticker, usable)
        row.update(adv)
        average = prior._float_or_none(row.get("prior_20d_avg_dollar_volume"))
        purchase_value = prior._float_or_none(row.get("total_purchase_value")) or 0.0
        if average and average > 0.0:
            pressure = purchase_value / average
            row["purchase_value_to_prior_20d_dollar_volume"] = round(pressure, 8)
            row["purchase_pressure_ge_floor"] = pressure >= PURCHASE_PRESSURE_FLOOR
        else:
            row["purchase_value_to_prior_20d_dollar_volume"] = None
            row["purchase_pressure_ge_floor"] = False
        annotated.append(row)
    return annotated


def _event_candidates(
    events: list[dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
    *,
    purchase_pressure_only: bool,
) -> list[dict[str, Any]]:
    return [
        prior._candidate_trade(event, prices)
        for event in events
        if not purchase_pressure_only or event.get("purchase_pressure_ge_floor")
    ]


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
        "benchmarks": {
            "strategy_total_return_pct": round(pnl_sum / INITIAL_CAPITAL, 6),
        },
    }


def _positive_pnl_concentration(details: dict[str, dict[str, Any]]) -> dict[str, Any]:
    by_ticker: defaultdict[str, float] = defaultdict(float)
    for detail in details.values():
        for trade in detail.get("purchase_pressure_selected_trades") or []:
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
        label: {
            key: value
            for key, value in row.items()
            if key != "combined_equity_curve"
        }
        for label, row in metrics.items()
    }


def _gate_result(
    core_delta: dict[str, Any],
    raw_delta: dict[str, Any],
    details: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    selected = sum(
        int(row.get("purchase_pressure_selected_trade_count") or 0)
        for row in details.values()
    )
    target_windows = [
        label
        for label, row in details.items()
        if int(row.get("purchase_pressure_selected_trade_count") or 0) > 0
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
        "purchase_pressure_selected_event_trades": selected,
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
        "# Form 4 Purchase-Pressure Forward Queue",
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
        "| Window | Core EV | Raw Form4 EV | Pressure EV | Delta vs raw | Delta vs core | Core PnL | Pressure PnL | Event PnL | Trades |",
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
            "## Event Diagnostics",
            "",
            "```json",
            json.dumps(payload["source_diagnostics"], indent=2, sort_keys=True),
            "```",
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
    liquidity = _load_liquidity_map()
    raw_events, source_diagnostics = prior._load_forward_events()
    events = _annotate_purchase_pressure(raw_events, liquidity)
    raw_candidates = _event_candidates(events, prices, purchase_pressure_only=False)
    pressure_candidates = _event_candidates(events, prices, purchase_pressure_only=True)

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
        pressure_selected, pressure_skipped = prior._select_event_trades(
            pressure_candidates,
            start=window["start"],
            end=window["end"],
        )
        raw_curve = prior._event_equity_curve(
            raw_selected,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        pressure_curve = prior._event_equity_curve(
            pressure_selected,
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
            prior._combined_metrics(result, pressure_curve, pressure_selected)
            if pressure_selected
            else dict(core_baseline[label])
        )
        deltas_vs_raw[label] = prior._delta(raw_metrics[label], after_metrics[label])
        deltas_vs_core[label] = prior._delta(core_baseline[label], after_metrics[label])

        scoped_events = [
            row
            for row in events
            if window["start"] <= prior._date10(row.get("usable_trade_date")) <= window["end"]
        ]
        details[label] = {
            "raw_forward_event_count": len(scoped_events),
            "purchase_pressure_event_count": sum(
                1 for row in scoped_events if row.get("purchase_pressure_ge_floor")
            ),
            "pressure_ready_event_count": sum(
                1
                for row in scoped_events
                if row.get("purchase_pressure_status") == "ready"
            ),
            "raw_price_ready_count": sum(
                1
                for row in raw_candidates
                if row.get("status") == "price_ready"
                and window["start"] <= prior._date10(row.get("usable_trade_date")) <= window["end"]
            ),
            "purchase_pressure_price_ready_count": sum(
                1
                for row in pressure_candidates
                if row.get("status") == "price_ready"
                and window["start"] <= prior._date10(row.get("usable_trade_date")) <= window["end"]
            ),
            "raw_selected_trade_count": len(raw_selected),
            "purchase_pressure_selected_trade_count": len(pressure_selected),
            "raw_skipped_count": len(raw_skipped),
            "purchase_pressure_skipped_count": len(pressure_skipped),
            "purchase_pressure_selected_trades": pressure_selected,
            "raw_selected_trades": raw_selected,
            "purchase_pressure_skipped_candidates": pressure_skipped[:20],
        }

    aggregate_vs_raw = _aggregate_delta(raw_metrics, after_metrics)
    aggregate_vs_core = _aggregate_delta(core_baseline, after_metrics)
    gate = _gate_result(aggregate_vs_core, aggregate_vs_raw, details)
    actual_success = 1 if gate["passed"] else 0

    if gate["passed"]:
        decision = "observed_positive_requires_shared_default_off_adapter"
        status = "observed_only"
        rationale = (
            "The purchase-pressure Form 4 slice passed the replay gate, but no "
            "production path was changed. It must be promoted through a shared "
            "default-off adapter and parity tests before any trade-enabled use."
        )
    elif aggregate_vs_core["aggregate_ev_delta"] > 0 and aggregate_vs_core["aggregate_pnl_delta"] > 0:
        decision = "rejected_positive_not_promotable"
        status = "rejected"
        rationale = (
            "The purchase-pressure Form 4 slice was positive versus core, but failed "
            "the full Gate 4 standard once raw Form 4 replacement value, materiality, "
            "window stability, sample, and concentration were considered."
        )
    else:
        decision = "rejected_form4_purchase_pressure_forward_queue"
        status = "rejected"
        rationale = (
            "The purchase-pressure Form 4 slice did not produce positive, stable "
            "three-window EV/PnL evidence versus the core baseline."
        )

    realized_failure = ",".join(gate["failed_reasons"]) if gate["failed_reasons"] else None
    prediction = {
        "success_probability": 0.18,
        "expected_ev_delta": 0.05,
        "expected_pnl_delta": 1500.0,
        "main_failure_modes": [
            "sample_too_thin",
            "does_not_improve_raw_form4_queue",
            "window_regression",
            "concentration",
        ],
        "confidence_reason": (
            "Prior Form 4 slices were often positive versus core but not raw; "
            "liquidity-normalized purchase pressure is a new ownership-intensity "
            "field but sample risk remains high."
        ),
        "recorded_at": "2026-05-31T01:09:56+00:00",
    }

    payload: dict[str, Any] = {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": (
            "PIT-safe SEC Form 4 meaningful purchases with unusually high purchase "
            "value versus prior 20-day dollar volume may identify cleaner "
            "candidate-pool entries than the raw Form 4 queue."
        ),
        "change_type": "event_qualification_replay",
        "mechanism_family": "form4_purchase_pressure_event_satellite",
        "trial_family": "form4_purchase_pressure_event_satellite",
        "trial_variant_id": EXP_ID,
        "changed_variable": "form4_purchase_value_to_prior_adv_floor_v1",
        "single_causal_variable": "total_purchase_value / prior_20d_avg_dollar_volume >= 0.0001",
        "prior_trial_count": 8,
        "nearby_prior_experiments": [
            "exp-20260504-034",
            "exp-20260508-028",
            "exp-20260529-002",
            "exp-20260529-024",
            "exp-20260530-003",
            "exp-20260530-011",
        ],
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "free_sec_form4_purchase_value_normalized_by_prior_ohlcv_liquidity",
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
                )
            ),
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "candidate-pool / entry: large insider purchase value relative to "
                "prior 20-day dollar volume may be more informative than raw purchase dollars."
            ),
            "2_history_check": {
                "exp-20260504-034": "raw Form 4 satellite was directionally positive but not promotable.",
                "exp-20260508-028": "clustered Form 4 buying was positive but too thin/concentrated.",
                "exp-20260529-002": "role-quality Form 4 slice was positive versus core but not raw.",
                "exp-20260529-024": "inactivity slice failed window/sample/concentration gates.",
                "exp-20260530-003": "ownership-delta slice was positive versus core but not raw and not material.",
                "exp-20260530-011": "multi-filer slice was a different provenance field.",
            },
            "3_single_causal_variable": "form4_purchase_value_to_prior_adv_floor_v1",
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; must improve aggregate EV/PnL "
                "versus core and raw Form 4, avoid window EV/PnL regressions, pass "
                "drawdown, survival, target sample, and concentration guards."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260531_002_form4_purchase_pressure_forward_queue.py"
            ),
        },
        "parameters": {
            "queue_name": prior.QUEUE_NAME,
            "rule_version": prior.RULE_VERSION,
            "forward_queue_min_total_purchase_value": prior.FORWARD_QUEUE_MIN_PURCHASE_VALUE,
            "lookback_trading_days": LOOKBACK_DAYS,
            "min_lookback_trading_days": MIN_LOOKBACK_DAYS,
            "purchase_pressure_floor": PURCHASE_PRESSURE_FLOOR,
            "purchase_pressure_definition": "total_purchase_value / average(close * volume) over prior trading days",
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
            "purchase_pressure_floor": PURCHASE_PRESSURE_FLOOR,
            "lookback_trading_days": LOOKBACK_DAYS,
            "min_lookback_trading_days": MIN_LOOKBACK_DAYS,
            "events_with_purchase_pressure_ready": sum(
                1 for row in events if row.get("purchase_pressure_status") == "ready"
            ),
            "events_passing_purchase_pressure_floor": sum(
                1 for row in events if row.get("purchase_pressure_ge_floor")
            ),
            "pressure_distribution_sample": [
                {
                    "ticker": row.get("ticker"),
                    "usable_trade_date": row.get("usable_trade_date"),
                    "total_purchase_value": row.get("total_purchase_value"),
                    "prior_20d_avg_dollar_volume": row.get("prior_20d_avg_dollar_volume"),
                    "purchase_value_to_prior_20d_dollar_volume": row.get(
                        "purchase_value_to_prior_20d_dollar_volume"
                    ),
                }
                for row in sorted(
                    events,
                    key=lambda event: float(
                        event.get("purchase_value_to_prior_20d_dollar_volume") or 0.0
                    ),
                    reverse=True,
                )[:12]
            ],
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": (
                "The tested field is deterministic and replayable from free SEC "
                "Form 4 transaction data plus fixed OHLCV snapshots; LLM soft-ranking "
                "remains sample-limited."
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
                "A shared default-off Form 4 purchase-pressure queue/paper adapter "
                "must be wired through production and replay before any trade-enabled use."
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
            "pit_status": "uses Form 4 accepted_at/usable_trade_date and fixed OHLCV snapshots",
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
                        "purchase_pressure_selected_event_trades",
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
