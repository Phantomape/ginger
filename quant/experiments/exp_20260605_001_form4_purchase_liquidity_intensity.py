"""Replay liquidity-normalized Form 4 purchases as a candidate-pool scout.

This keeps the core strategy and raw Form 4 forward queue fixed. The single
tested variable is whether the event's aggregate open-market purchase value is
at least 0.50% of the issuer's trailing 20-trading-day dollar volume, measured
strictly before the Form 4 usable trade date.
"""

from __future__ import annotations

import json
from collections import OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260530_003_form4_ownership_delta_forward_queue as prior


EXP_ID = "exp-20260605-001"
STEM = "form4_purchase_liquidity_intensity"
OUT_DIR = prior.REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
RAW_AGG_JSON = OUT_DIR / f"{STEM}_raw_form4_aggregate.json"
LOG_JSON = prior.REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = prior.REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
DOC_TICKET_JSON = prior.REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXP_ID}.json"
CARD_MD = prior.REPO_ROOT / "experiments" / "cards" / f"{EXP_ID}.md"
MANIFEST_JSON = prior.REPO_ROOT / "experiments" / "manifests" / f"{EXP_ID}.json"
ARTIFACT_MD = prior.REPO_ROOT / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"
EXPERIMENT_LOG = prior.REPO_ROOT / "docs" / "experiment_log.jsonl"

ADV_LOOKBACK_DAYS = 20
MIN_ADV_LOOKBACK_DAYS = 20
PURCHASE_VALUE_TO_ADV20_FLOOR = 0.005
INITIAL_CAPITAL = 100_000.0


def _round(value: Any, digits: int = 6) -> Any:
    if isinstance(value, (int, float)):
        return round(float(value), digits)
    return value


def _load_price_map_with_volume() -> dict[str, list[dict[str, Any]]]:
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
                close = prior._float_or_none(row.get("Close"))
                volume = prior._float_or_none(row.get("Volume"))
                date_key = str(row["Date"])[:10]
                by_ticker_date[ticker_key][date_key] = {
                    "date": date_key,
                    "open": prior._float_or_none(row.get("Open")),
                    "close": close,
                    "volume": volume,
                    "dollar_volume": close * volume
                    if close is not None and volume is not None
                    else None,
                }
    return {
        ticker: sorted(rows.values(), key=lambda row: row["date"])
        for ticker, rows in by_ticker_date.items()
    }


def _trailing_adv20(
    prices: dict[str, list[dict[str, Any]]],
    ticker: str,
    usable_date: str,
) -> dict[str, Any]:
    rows = [
        row
        for row in prices.get(str(ticker).upper(), [])
        if row.get("date") and row["date"] < usable_date and row.get("dollar_volume") is not None
    ]
    window = rows[-ADV_LOOKBACK_DAYS:]
    if len(window) < MIN_ADV_LOOKBACK_DAYS:
        return {
            "adv20_status": "insufficient_pre_event_ohlcv",
            "adv20_dollar_volume": None,
            "adv20_days": len(window),
        }
    adv = sum(float(row["dollar_volume"]) for row in window) / len(window)
    return {
        "adv20_status": "ready",
        "adv20_dollar_volume": round(adv, 2),
        "adv20_days": len(window),
        "adv20_start": window[0]["date"],
        "adv20_end": window[-1]["date"],
    }


def _event_with_liquidity_intensity(
    event: dict[str, Any],
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    ticker = str(event.get("ticker") or "").upper()
    usable = prior._date10(event.get("usable_trade_date"))
    adv = _trailing_adv20(prices, ticker, usable)
    purchase_value = prior._float_or_none(event.get("total_purchase_value")) or 0.0
    adv20 = prior._float_or_none(adv.get("adv20_dollar_volume"))
    ratio = purchase_value / adv20 if adv20 and adv20 > 0.0 else None
    return {
        **event,
        **adv,
        "ticker": ticker,
        "usable_trade_date": usable,
        "purchase_value_to_adv20": _round(ratio) if ratio is not None else None,
        "purchase_value_to_adv20_ge_floor": bool(
            ratio is not None and ratio >= PURCHASE_VALUE_TO_ADV20_FLOOR
        ),
    }


def _load_liquidity_events(
    prices: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw_events, diagnostics = prior._load_forward_events()
    events = [_event_with_liquidity_intensity(event, prices) for event in raw_events]
    qualified = [event for event in events if event.get("purchase_value_to_adv20_ge_floor")]
    diagnostics.update(
        {
            "adv_lookback_days": ADV_LOOKBACK_DAYS,
            "min_adv_lookback_days": MIN_ADV_LOOKBACK_DAYS,
            "purchase_value_to_adv20_floor": PURCHASE_VALUE_TO_ADV20_FLOOR,
            "events_with_adv20": sum(1 for row in events if row.get("adv20_status") == "ready"),
            "liquidity_intensity_event_count": len(qualified),
            "liquidity_intensity_events_by_window": dict(
                sorted(
                    {
                        label: sum(1 for row in qualified if row.get("window") == label)
                        for label in prior.WINDOWS
                    }.items()
                )
            ),
        }
    )
    return sorted(events, key=lambda row: (row["usable_trade_date"], row["ticker"])), diagnostics


def _event_candidates(
    events: list[dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
    *,
    liquidity_intensity_only: bool,
) -> list[dict[str, Any]]:
    return [
        prior._candidate_trade(event, prices)
        for event in events
        if not liquidity_intensity_only or event.get("purchase_value_to_adv20_ge_floor")
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
        "benchmarks": {"strategy_total_return_pct": round(pnl_sum / INITIAL_CAPITAL, 6)},
    }


def _positive_pnl_concentration(details: dict[str, dict[str, Any]]) -> dict[str, Any]:
    by_ticker: defaultdict[str, float] = defaultdict(float)
    for detail in details.values():
        for trade in detail.get("liquidity_intensity_selected_trades") or []:
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


def _gate_result(
    core_delta: dict[str, Any],
    raw_delta: dict[str, Any],
    details: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    selected = sum(int(row.get("liquidity_intensity_selected_trade_count") or 0) for row in details.values())
    target_windows = [
        label
        for label, row in details.items()
        if int(row.get("liquidity_intensity_selected_trade_count") or 0) > 0
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
        "liquidity_intensity_selected_event_trades": selected,
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


def _metrics_for_log(metrics: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        label: {key: value for key, value in row.items() if key != "combined_equity_curve"}
        for label, row in metrics.items()
    }


def _position_field_check() -> dict[str, Any]:
    if not prior.OPEN_POSITIONS_JSON.exists():
        return {"passed": False, "reason": "operator_inputs/open_positions.json missing"}
    payload = json.loads(prior.OPEN_POSITIONS_JSON.read_text(encoding="utf-8"))
    positions = payload.get("positions") if isinstance(payload, dict) else payload
    if not isinstance(positions, list):
        return {"passed": False, "reason": "open_positions payload is not a list/object with positions"}
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
            missing.append(
                {
                    "index": idx,
                    "ticker": position.get("ticker"),
                    "missing_fields": absent,
                }
            )
    return {
        "passed": not missing,
        "path": prior._repo_rel(prior.OPEN_POSITIONS_JSON),
        "position_count": len(positions),
        "missing_entry_date_or_target_price": missing,
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
        "# Form 4 Purchase Liquidity Intensity",
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
        "| Window | Core EV | Raw Form4 EV | Liquidity EV | Delta vs raw | Delta vs core | Core PnL | Liquidity PnL | Event PnL | Trades |",
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
    prices = _load_price_map_with_volume()
    events, source_diagnostics = _load_liquidity_events(prices)
    raw_candidates = _event_candidates(events, prices, liquidity_intensity_only=False)
    liquidity_candidates = _event_candidates(events, prices, liquidity_intensity_only=True)

    core_baseline: dict[str, dict[str, Any]] = OrderedDict()
    raw_metrics: dict[str, dict[str, Any]] = OrderedDict()
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    deltas_vs_raw: dict[str, dict[str, Any]] = OrderedDict()
    deltas_vs_core: dict[str, dict[str, Any]] = OrderedDict()
    core_gate_by_window: dict[str, dict[str, Any]] = OrderedDict()
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
        liquidity_selected, liquidity_skipped = prior._select_event_trades(
            liquidity_candidates,
            start=window["start"],
            end=window["end"],
        )
        raw_curve = prior._event_equity_curve(
            raw_selected,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        liquidity_curve = prior._event_equity_curve(
            liquidity_selected,
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
            prior._combined_metrics(result, liquidity_curve, liquidity_selected)
            if liquidity_selected
            else dict(core_baseline[label])
        )
        deltas_vs_raw[label] = prior._delta(raw_metrics[label], after_metrics[label])
        deltas_vs_core[label] = prior._delta(core_baseline[label], after_metrics[label])
        core_gate_by_window[label] = prior._gate4(core_baseline[label], after_metrics[label])

        scoped_events = [
            row
            for row in events
            if window["start"] <= prior._date10(row.get("usable_trade_date")) <= window["end"]
        ]
        details[label] = {
            "raw_forward_event_count": len(scoped_events),
            "events_with_adv20": sum(1 for row in scoped_events if row.get("adv20_status") == "ready"),
            "liquidity_intensity_event_count": sum(
                1 for row in scoped_events if row.get("purchase_value_to_adv20_ge_floor")
            ),
            "raw_price_ready_count": sum(
                1
                for row in raw_candidates
                if row.get("status") == "price_ready"
                and window["start"] <= prior._date10(row.get("usable_trade_date")) <= window["end"]
            ),
            "liquidity_intensity_price_ready_count": sum(
                1
                for row in liquidity_candidates
                if row.get("status") == "price_ready"
                and window["start"] <= prior._date10(row.get("usable_trade_date")) <= window["end"]
            ),
            "raw_selected_trade_count": len(raw_selected),
            "liquidity_intensity_selected_trade_count": len(liquidity_selected),
            "raw_skipped_count": len(raw_skipped),
            "liquidity_intensity_skipped_count": len(liquidity_skipped),
            "liquidity_intensity_selected_trades": liquidity_selected,
            "raw_selected_trades": raw_selected,
            "liquidity_intensity_skipped_candidates": liquidity_skipped[:20],
        }

    aggregate_vs_raw = _aggregate_delta(raw_metrics, after_metrics)
    aggregate_vs_core = _aggregate_delta(core_baseline, after_metrics)
    gate = _gate_result(aggregate_vs_core, aggregate_vs_raw, details)

    if gate["passed"]:
        decision = "accepted_default_off_form4_purchase_liquidity_intensity"
        status = "accepted_default_off"
        rationale = (
            "The liquidity-normalized Form 4 qualifier improved both core and raw Form 4 "
            "overlays while clearing materiality, drawdown, sample, and concentration "
            "gates. It remains replay-only here; a shared default-off production/replay "
            "adapter would be required before any trade-enabled use."
        )
    elif aggregate_vs_core["aggregate_ev_delta"] > 0 and aggregate_vs_core["aggregate_pnl_delta"] > 0:
        decision = "rejected_positive_not_promotable"
        status = "rejected"
        rationale = (
            "The liquidity-normalized Form 4 slice was positive versus core, but it failed "
            "the full Gate 4 standard once raw Form 4 replacement value, materiality, "
            "window stability, sample, and concentration were considered."
        )
    else:
        decision = "rejected_form4_purchase_liquidity_intensity"
        status = "rejected"
        rationale = (
            "The liquidity-normalized Form 4 slice did not produce positive, stable "
            "three-window EV/PnL evidence versus the core baseline."
        )

    payload: dict[str, Any] = {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": (
            "PIT-safe Form 4 meaningful purchases whose total insider purchase value "
            "is unusually large relative to the issuer's pre-event 20-day dollar volume "
            "may create a cleaner free-data candidate-pool overlay than the raw Form 4 queue."
        ),
        "change_type": "event_qualification_replay",
        "mechanism_family": "form4_liquidity_normalized_insider_purchase_event_satellite",
        "trial_family": "form4_liquidity_normalized_event_satellite",
        "trial_variant_id": "form4_purchase_value_to_adv20_ge_0p50pct_v1",
        "changed_variable": "form4_purchase_value_to_adv20_ge_0p50pct_forward_queue_v1",
        "single_causal_variable": (
            "total_purchase_value / trailing_20d_avg_dollar_volume >= 0.005 on the "
            "existing PIT-safe Form 4 forward queue"
        ),
        "prediction": {
            "success_probability": 0.18,
            "expected_ev_delta": 0.2,
            "expected_pnl_delta": 3000.0,
            "main_failure_modes": [
                "sample_too_small",
                "does_not_beat_raw_form4_queue",
                "window_regression",
                "single_ticker_concentration",
            ],
            "confidence_reason": (
                "Form 4 has weak but occasionally positive free-data signal; liquidity "
                "normalization is materially different from prior cost-basis and ownership-delta "
                "tests but sample risk is high."
            ),
        },
        "calibration": {
            "pre_run_probability": 0.18,
            "pre_run_expected_ev_delta": 0.2,
            "pre_run_expected_pnl_delta": 3000.0,
            "actual_gate4_passed": gate["passed"],
        },
        "gate_questions": {
            "alpha_hypothesis": (
                "Candidate-pool/entry overlay: use free SEC Form 4 purchase pressure "
                "normalized by pre-event dollar volume to identify unusual insider conviction."
            ),
            "prior_similar_experiments": [
                "exp-20260504-034: raw >=500k Form 4 satellite positive but not enough for promotion.",
                "exp-20260530-003: ownership-delta qualifier tested a different owner-position relation.",
                "exp-20260604-022: cost-basis entry alignment failed raw replacement/sample/concentration gates.",
                "exp-20260604-024: Form4+FTD overlap failed or remained non-promotable.",
            ],
            "single_causal_variable": (
                "Only the purchase-value-to-ADV20 qualifier changes; core entries, raw Form 4 "
                "queue threshold, event notional, capacity, hold, LLM/news, and exits stay fixed."
            ),
            "acceptance_standard": (
                "docs/backtesting.md three fixed windows; must improve aggregate EV/PnL "
                "versus core and raw Form 4, avoid window EV/PnL regressions, pass "
                "drawdown, survival, target sample, and concentration guards."
            ),
            "reproducibility": (
                "This runner rebuilds the core, raw Form 4, and liquidity-normalized Form 4 "
                "overlays from fixed snapshots and the local PIT-safe Form 4 transaction file."
            ),
        },
        "parameters": {
            "queue_name": prior.QUEUE_NAME,
            "rule_version": prior.RULE_VERSION,
            "forward_queue_min_total_purchase_value": prior.FORWARD_QUEUE_MIN_PURCHASE_VALUE,
            "purchase_value_to_adv20_floor": PURCHASE_VALUE_TO_ADV20_FLOOR,
            "adv_lookback_days": ADV_LOOKBACK_DAYS,
            "min_adv_lookback_days": MIN_ADV_LOOKBACK_DAYS,
            "adv_window_definition": "strictly before usable_trade_date; no same-day volume",
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
        "gate2": _position_field_check(),
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_overlay_only": True,
            "min_survival_rate": min(float(row.get("survival_rate") or 0.0) for row in core_baseline.values()),
            "passed": min(float(row.get("survival_rate") or 0.0) for row in core_baseline.values()) >= 0.05,
        },
        "core_baseline_metrics": core_baseline,
        "raw_form4_metrics": raw_metrics,
        "after_metrics": after_metrics,
        "deltas_vs_raw_form4": deltas_vs_raw,
        "deltas_vs_core": deltas_vs_core,
        "core_gate_by_window": core_gate_by_window,
        "aggregate_delta_vs_raw_form4": aggregate_vs_raw,
        "aggregate_delta_vs_core": aggregate_vs_core,
        "gate4": gate,
        "event_details": details,
        "decision_rationale": rationale,
        "source_diagnostics": source_diagnostics,
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": (
                "LLM soft-ranking data is not required here; the tested field is deterministic "
                "and replayable from free SEC Form 4 transaction data and OHLCV snapshots."
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
                "A shared default-off Form 4 liquidity-intensity queue/paper adapter must "
                "be wired through production and replay before any trade-enabled use."
            ),
        },
        "data_source": {
            "form4_transactions_path": prior._repo_rel(prior.FORM4_TRANSACTIONS_PATH),
            "ohlcv_snapshots": [
                window["snapshot"]
                for window in prior.WINDOWS.values()
            ],
            "pit_status": (
                "uses Form 4 accepted_at/usable_trade_date plus OHLCV rows strictly before "
                "usable_trade_date"
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
            prior._repo_rel(ARTIFACT_MD),
            prior._repo_rel(Path(__file__)),
        ],
    }
    return payload


def main() -> None:
    payload = build_payload()
    prior._write_json(OUT_JSON, payload)
    prior._write_json(BEFORE_AGG_JSON, _aggregate_for_close(payload["core_baseline_metrics"]))
    prior._write_json(AFTER_AGG_JSON, _aggregate_for_close(payload["after_metrics"]))
    prior._write_json(RAW_AGG_JSON, _aggregate_for_close(payload["raw_form4_metrics"]))
    prior._write_json(LOG_JSON, payload)
    _write_report(payload)
    _write_ticket(payload)
    _write_manifest(payload)
    _append_experiment_log(payload)
    print(json.dumps(payload["gate4"], indent=2, sort_keys=True))
    print(json.dumps(payload["aggregate_delta_vs_core"], indent=2, sort_keys=True))
    print(json.dumps(payload["aggregate_delta_vs_raw_form4"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
