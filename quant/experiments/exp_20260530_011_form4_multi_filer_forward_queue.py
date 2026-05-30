"""Replay multi-filer Form 4 purchases as a bounded event overlay.

This alpha-search experiment keeps the core stack and raw Form 4 forward queue
fixed. The single tested variable is whether a PIT-safe meaningful-purchase
event has at least two distinct reporting owners on the same ticker/date.
"""

from __future__ import annotations

import json
import math
from collections import OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260530_003_form4_ownership_delta_forward_queue as prior


EXP_ID = "exp-20260530-011"
STEM = "form4_multi_filer_forward_queue"
OUT_DIR = prior.REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"exp_20260530_011_{STEM}.json"
LOG_JSON = prior.REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = prior.REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
CARD_MD = prior.REPO_ROOT / "experiments" / "cards" / f"{EXP_ID}.md"
MANIFEST_JSON = prior.REPO_ROOT / "experiments" / "manifests" / f"{EXP_ID}.json"
EXPERIMENT_LOG = prior.REPO_ROOT / "docs" / "experiment_log.jsonl"

MIN_OWNER_COUNT = 2


def _multi_filer(event: dict[str, Any]) -> bool:
    try:
        return int(event.get("owner_count") or 0) >= MIN_OWNER_COUNT
    except (TypeError, ValueError):
        return False


def _event_candidates(
    events: list[dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
    *,
    multi_filer_only: bool,
) -> list[dict[str, Any]]:
    return [
        prior._candidate_trade(event, prices)
        for event in events
        if not multi_filer_only or _multi_filer(event)
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


def _positive_pnl_concentration(details: dict[str, dict[str, Any]]) -> dict[str, Any]:
    by_ticker: defaultdict[str, float] = defaultdict(float)
    for detail in details.values():
        for trade in detail.get("multi_filer_selected_trades") or []:
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
    selected = sum(int(row.get("multi_filer_selected_trade_count") or 0) for row in details.values())
    target_windows = [
        label
        for label, row in details.items()
        if int(row.get("multi_filer_selected_trade_count") or 0) > 0
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
        "multi_filer_selected_event_trades": selected,
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
    compact = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
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
        "# Form 4 Multi-Filer Forward Queue",
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
        "| Window | Core EV | Raw Form4 EV | Multi-filer EV | Delta vs raw | Delta vs core | Core PnL | Multi-filer PnL | Event PnL | Trades |",
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
            "## Production Impact",
            "",
            "```json",
            json.dumps(payload["production_impact"], indent=2, sort_keys=True),
            "```",
            "",
            "No JavaScript was used.",
        ]
    )
    CARD_MD.parent.mkdir(parents=True, exist_ok=True)
    CARD_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_ticket(payload: dict[str, Any]) -> None:
    ticket = prior._json_load(TICKET_JSON, {})
    if not isinstance(ticket, dict):
        ticket = {}
    ticket.update(
        {
            "status": payload["status"],
            "decision": payload["decision"],
            "completed_at": payload["timestamp"],
            "result": {
                "artifact": prior._repo_rel(OUT_JSON),
                "log": prior._repo_rel(LOG_JSON),
                "report": prior._repo_rel(CARD_MD),
                "aggregate_delta_vs_core": payload["aggregate_delta_vs_core"],
                "aggregate_delta_vs_raw_form4": payload["aggregate_delta_vs_raw_form4"],
                "decision": payload["decision"],
            },
        }
    )
    prior._write_json(TICKET_JSON, ticket)


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
                prior._repo_rel(LOG_JSON),
                prior._repo_rel(CARD_MD),
            ],
        }
    )
    prior._write_json(MANIFEST_JSON, manifest)


def build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    universe = prior.get_universe()
    prices = prior._load_price_map()
    events, source_diagnostics = prior._load_forward_events()
    raw_candidates = _event_candidates(events, prices, multi_filer_only=False)
    multi_filer_candidates = _event_candidates(events, prices, multi_filer_only=True)

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
        multi_selected, multi_skipped = prior._select_event_trades(
            multi_filer_candidates,
            start=window["start"],
            end=window["end"],
        )
        raw_curve = prior._event_equity_curve(
            raw_selected,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        multi_curve = prior._event_equity_curve(
            multi_selected,
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
            prior._combined_metrics(result, multi_curve, multi_selected)
            if multi_selected
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
            "multi_filer_event_count": sum(1 for row in scoped_events if _multi_filer(row)),
            "raw_price_ready_count": sum(
                1
                for row in raw_candidates
                if row.get("status") == "price_ready"
                and window["start"] <= prior._date10(row.get("usable_trade_date")) <= window["end"]
            ),
            "multi_filer_price_ready_count": sum(
                1
                for row in multi_filer_candidates
                if row.get("status") == "price_ready"
                and window["start"] <= prior._date10(row.get("usable_trade_date")) <= window["end"]
            ),
            "raw_selected_trade_count": len(raw_selected),
            "multi_filer_selected_trade_count": len(multi_selected),
            "raw_skipped_count": len(raw_skipped),
            "multi_filer_skipped_count": len(multi_skipped),
            "multi_filer_selected_trades": multi_selected,
            "raw_selected_trades": raw_selected,
            "multi_filer_skipped_candidates": multi_skipped[:20],
        }

    aggregate_vs_raw = _aggregate_delta(raw_metrics, after_metrics)
    aggregate_vs_core = _aggregate_delta(core_baseline, after_metrics)
    gate = _gate_result(aggregate_vs_core, aggregate_vs_raw, details)
    actual_success = 1 if gate["passed"] else 0

    if gate["passed"]:
        decision = "accepted_default_off_form4_multi_filer_forward_queue"
        status = "accepted_default_off"
        rationale = (
            "The multi-filer Form 4 qualifier improved both core and raw Form 4 "
            "overlays while clearing materiality, drawdown, sample, and concentration "
            "gates. A shared default-off adapter would still be required before any "
            "production use."
        )
    elif aggregate_vs_core["aggregate_ev_delta"] > 0 and aggregate_vs_core["aggregate_pnl_delta"] > 0:
        decision = "rejected_positive_not_promotable"
        status = "rejected"
        rationale = (
            "The multi-filer Form 4 slice was positive versus core, but failed the "
            "full Gate 4 standard once raw Form 4 replacement value, materiality, "
            "window stability, sample, and concentration were considered."
        )
    else:
        decision = "rejected_form4_multi_filer_forward_queue"
        status = "rejected"
        rationale = (
            "The multi-filer Form 4 slice did not produce positive, stable "
            "three-window EV/PnL evidence versus the core baseline."
        )

    return {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": (
            "PIT-safe Form 4 meaningful purchase events with multiple distinct "
            "reporting owners may be a cleaner free SEC candidate-pool alpha than "
            "the raw meaningful-purchase queue."
        ),
        "change_type": "event_qualification_replay",
        "mechanism_family": "form4_multi_filer_event_satellite",
        "trial_family": "form4_multi_filer_event_satellite",
        "trial_variant_id": EXP_ID,
        "changed_variable": "form4_owner_count_gte_2_forward_queue_v1",
        "single_causal_variable": "owner_count >= 2 on the existing PIT-safe Form 4 forward queue",
        "prior_trial_count": 5,
        "nearby_prior_experiments": [
            "exp-20260512-101",
            "exp-20260512-901",
            "exp-20260529-002",
            "exp-20260529-024",
            "exp-20260530-003",
        ],
        "multiple_testing_risk_bucket": "moderate_high",
        "new_evidence_type": "production_visible_free_sec_form4_multi_filer_field",
        "prediction": {
            "success_probability": 0.20,
            "expected_ev_delta": None,
            "expected_pnl_delta": None,
            "main_failure_modes": [
                "sample_too_thin",
                "does_not_improve_raw_form4_queue",
                "window_regression",
                "concentration",
            ],
            "confidence_reason": (
                "Multi-filer buying is a stronger insider-accumulation provenance "
                "field than single-role metadata, but prior Form 4 slices were thin "
                "and often concentrated."
            ),
            "recorded_at": "2026-05-30T06:18:31+00:00",
            "brier_score": round((0.20 - actual_success) ** 2, 6),
        },
        "calibration": {
            "actual_decision": decision,
            "actual_success": actual_success,
            "predicted_success_probability": 0.20,
            "brier_score": round((0.20 - actual_success) ** 2, 6),
            "predicted_failure_modes": [
                "sample_too_thin",
                "does_not_improve_raw_form4_queue",
                "window_regression",
                "concentration",
            ],
            "realized_failure_mode": ",".join(gate["failed_reasons"]) if gate["failed_reasons"] else None,
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
                "candidate-pool / entry: multiple distinct reporting owners in a "
                "meaningful Form 4 purchase event may indicate broader insider "
                "accumulation than a single-role purchase."
            ),
            "2_history_check": {
                "exp-20260512-101": (
                    "Older multi-owner cluster shadow existed; this run retests the "
                    "current PIT-safe Form 4 forward queue with the canonical three-window "
                    "core/raw replacement gate."
                ),
                "exp-20260512-901": "single-owner queue was positive but not material.",
                "exp-20260529-002": "executive-role Form 4 slice was positive versus core but not raw and too concentrated.",
                "exp-20260529-024": "first-buy inactivity slice was positive but failed window/sample/concentration gates.",
                "exp-20260530-003": "ownership-delta slice tested a different provenance field.",
            },
            "3_single_causal_variable": "form4_owner_count_gte_2_forward_queue_v1",
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; must improve aggregate EV/PnL "
                "versus core and raw Form 4, avoid window EV/PnL regressions, pass "
                "drawdown, survival, target sample, and concentration guards."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260530_011_form4_multi_filer_forward_queue.py"
            ),
        },
        "parameters": {
            "queue_name": prior.QUEUE_NAME,
            "rule_version": prior.RULE_VERSION,
            "forward_queue_min_total_purchase_value": prior.FORWARD_QUEUE_MIN_PURCHASE_VALUE,
            "min_owner_count": MIN_OWNER_COUNT,
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
        "source_diagnostics": source_diagnostics,
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": (
                "The tested field is deterministic and replayable from free SEC "
                "Form 4 transaction data; LLM soft-ranking remains sample-limited."
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
                "A shared default-off Form 4 multi-filer queue/paper adapter must "
                "be wired through production and replay before any trade-enabled use."
            ),
        },
        "production_parity": {
            "alters_production_orders": False,
            "alters_live_watchlists": False,
            "alters_core_backtester": False,
            "default_enabled": False,
            "replay_only": True,
            "parity_note": (
                "No production path changed. A positive result would require a "
                "shared default-off Form 4 adapter and parity tests before retention."
            ),
        },
        "data_source": {
            "form4_transactions_path": prior._repo_rel(prior.FORM4_TRANSACTIONS_PATH),
            "pit_status": "uses Form 4 accepted_at/usable_trade_date and fixed OHLCV snapshots",
        },
        "related_files": [
            prior._repo_rel(OUT_JSON),
            prior._repo_rel(LOG_JSON),
            prior._repo_rel(TICKET_JSON),
            prior._repo_rel(CARD_MD),
            prior._repo_rel(MANIFEST_JSON),
            prior._repo_rel(Path(__file__)),
            prior._repo_rel(EXPERIMENT_LOG),
        ],
        "anti_js": "No JavaScript was used.",
    }


def main() -> None:
    payload = build_payload()
    prior._write_json(OUT_JSON, payload)
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
                        "multi_filer_selected_event_trades",
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
    if not math.isfinite(1.0):
        raise SystemExit("unexpected math failure")
    main()
