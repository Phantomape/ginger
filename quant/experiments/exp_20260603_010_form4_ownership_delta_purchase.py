"""Test aggregate Form 4 ownership-delta purchases as a candidate-pool scout.

This replay-only alpha experiment keeps the frozen Form 4 meaningful-purchase
queue fixed and changes one qualifier: event-level aggregate purchase shares
divided by aggregate reported after-transaction shares must be at least 10%.
This differs from exp-20260530-003, which used the max single-transaction
ownership delta.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
from experiments import exp_20260530_003_form4_ownership_delta_forward_queue as prior  # noqa: E402


EXP_ID = "exp-20260603-010"
STEM = "form4_aggregate_ownership_delta_purchase"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_core_aggregate.json"
RAW_FORM4_AGG_JSON = OUT_DIR / f"{STEM}_raw_form4_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_qualified_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXP_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXP_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXP_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

AGGREGATE_OWNERSHIP_DELTA_FLOOR = 0.10
MAX_SINGLE_POSITIVE_SHARE = 0.75
MAX_POSITIVE_HHI = 0.60

WINDOWS = prior.WINDOWS
FORM4_TRANSACTIONS_PATH = prior.FORM4_TRANSACTIONS_PATH


def _date10(value: Any) -> str:
    return str(value or "")[:10]


def _window_name(value: str) -> str | None:
    for label, window in WINDOWS.items():
        if window["start"] <= value <= window["end"]:
            return label
    return None


def _aggregate_metrics(metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in metrics.values()),
            4,
        ),
        "total_pnl_sum": round(
            sum(float(row.get("total_pnl") or 0.0) for row in metrics.values()),
            2,
        ),
        "trade_count_sum": sum(int(row.get("trade_count") or 0) for row in metrics.values()),
        "min_survival_rate": min(float(row.get("survival_rate") or 0.0) for row in metrics.values()),
        "windows": metrics,
    }


def _load_forward_events() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not FORM4_TRANSACTIONS_PATH.exists():
        return [], {"source_status": "missing_form4_transactions"}
    rows = prior.load_form4_transaction_rows(FORM4_TRANSACTIONS_PATH)
    ownership = prior._ownership_delta_index(rows)
    start = min(window["start"] for window in WINDOWS.values())
    end = max(window["end"] for window in WINDOWS.values())
    raw_events = [
        event
        for event in prior.aggregate_purchase_events(rows, start=start, end=end)
        if prior.qualifies_forward_queue_event(event)
    ]
    events: list[dict[str, Any]] = []
    for event in raw_events:
        ticker = str(event.get("ticker") or "").upper()
        usable = _date10(event.get("usable_trade_date"))
        window = _window_name(usable)
        if not window:
            continue
        delta = ownership.get((ticker, usable), {})
        aggregate_delta = prior._float_or_none(
            delta.get("aggregate_ownership_delta_fraction")
        ) or 0.0
        max_delta = prior._float_or_none(delta.get("max_ownership_delta_fraction")) or 0.0
        events.append(
            {
                **event,
                **delta,
                "ticker": ticker,
                "usable_trade_date": usable,
                "window": window,
                "aggregate_ownership_delta_ge_10pct": (
                    aggregate_delta >= AGGREGATE_OWNERSHIP_DELTA_FLOOR
                ),
                "max_ownership_delta_ge_10pct": (
                    max_delta >= AGGREGATE_OWNERSHIP_DELTA_FLOOR
                ),
            }
        )
    diagnostics = {
        "source_status": "loaded",
        "transaction_rows": len(rows),
        "raw_forward_event_count": len(events),
        "events_with_ownership_delta": sum(
            1 for event in events if event.get("ownership_delta_transaction_count")
        ),
        "aggregate_ownership_delta_floor": AGGREGATE_OWNERSHIP_DELTA_FLOOR,
        "aggregate_ownership_delta_floor_event_count": sum(
            1 for event in events if event.get("aggregate_ownership_delta_ge_10pct")
        ),
        "prior_max_delta_floor_event_count": sum(
            1 for event in events if event.get("max_ownership_delta_ge_10pct")
        ),
    }
    return sorted(events, key=lambda row: (row["usable_trade_date"], row["ticker"])), diagnostics


def _event_candidates(
    events: list[dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
    *,
    aggregate_delta_only: bool,
) -> list[dict[str, Any]]:
    return [
        prior._candidate_trade(event, prices)
        for event in events
        if not aggregate_delta_only or event.get("aggregate_ownership_delta_ge_10pct")
    ]


def _append_experiment_log(payload: dict[str, Any]) -> None:
    compact = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
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


def _write_report(payload: dict[str, Any]) -> None:
    lines = [
        "# Form 4 Aggregate Ownership-Delta Purchase Scout",
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
        "| Window | Core EV | Raw Form4 EV | Aggregate-delta EV | Delta vs raw | Delta vs core | Core PnL | Aggregate-delta PnL | Event PnL | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
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
            "## Gate 4",
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
        ]
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    CARD_MD.parent.mkdir(parents=True, exist_ok=True)
    CARD_MD.write_text("\n".join(lines[:45]) + "\n", encoding="utf-8")


def _ticket(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXP_ID,
        "title": "Form 4 aggregate ownership-delta purchase scout",
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": payload["lane"],
        "mechanism_family": payload["mechanism_family"],
        "created_at": payload["timestamp"],
        "completed_at": payload["timestamp"],
        "result": {
            "artifact": prior._repo_rel(OUT_JSON),
            "log": prior._repo_rel(LOG_JSON),
            "report": prior._repo_rel(ARTIFACT_MD),
            "before_aggregate": prior._repo_rel(BEFORE_AGG_JSON),
            "raw_form4_aggregate": prior._repo_rel(RAW_FORM4_AGG_JSON),
            "after_aggregate": prior._repo_rel(AFTER_AGG_JSON),
            "aggregate_delta_vs_core": payload["aggregate_delta_vs_core"],
            "aggregate_delta_vs_raw_form4": payload["aggregate_delta_vs_raw_form4"],
            "decision": payload["decision"],
        },
    }


def _write_tickets(payload: dict[str, Any]) -> None:
    ticket = _ticket(payload)
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
                prior._repo_rel(LOG_JSON),
                prior._repo_rel(ARTIFACT_MD),
                prior._repo_rel(BEFORE_AGG_JSON),
                prior._repo_rel(RAW_FORM4_AGG_JSON),
                prior._repo_rel(AFTER_AGG_JSON),
            ],
        }
    )
    prior._write_json(MANIFEST_JSON, manifest)


def _update_registry(payload: dict[str, Any]) -> None:
    registry = prior._json_load(REGISTRY_JSON, {"schema_version": 1, "experiments": []})
    if not isinstance(registry, dict):
        registry = {"schema_version": 1, "experiments": []}
    experiments = registry.setdefault("experiments", [])
    if not isinstance(experiments, list):
        registry["experiments"] = []
        experiments = registry["experiments"]
    for item in experiments:
        if isinstance(item, dict) and item.get("experiment_id") == EXP_ID:
            item.update(
                {
                    "status": payload["status"],
                    "completed_at": payload["timestamp"],
                    "result": {
                        "decision": payload["decision"],
                        "aggregate_delta_vs_core": payload["aggregate_delta_vs_core"],
                        "aggregate_delta_vs_raw_form4": payload["aggregate_delta_vs_raw_form4"],
                    },
                }
            )
            break
    registry["updated_at"] = payload["timestamp"]
    prior._write_json(REGISTRY_JSON, registry)


def build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    universe = get_universe()
    prices = prior._load_price_map()
    events, source_diagnostics = _load_forward_events()
    raw_candidates = _event_candidates(events, prices, aggregate_delta_only=False)
    aggregate_candidates = _event_candidates(events, prices, aggregate_delta_only=True)

    core_baseline: dict[str, dict[str, Any]] = OrderedDict()
    raw_metrics: dict[str, dict[str, Any]] = OrderedDict()
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    deltas_vs_raw: dict[str, dict[str, Any]] = OrderedDict()
    deltas_vs_core: dict[str, dict[str, Any]] = OrderedDict()
    details: dict[str, dict[str, Any]] = OrderedDict()

    for label, window in WINDOWS.items():
        result = BacktestEngine(
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
        aggregate_selected, aggregate_skipped = prior._select_event_trades(
            aggregate_candidates,
            start=window["start"],
            end=window["end"],
        )
        raw_curve = prior._event_equity_curve(
            raw_selected,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        aggregate_curve = prior._event_equity_curve(
            aggregate_selected,
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
            prior._combined_metrics(result, aggregate_curve, aggregate_selected)
            if aggregate_selected
            else dict(core_baseline[label])
        )
        deltas_vs_raw[label] = prior._delta(raw_metrics[label], after_metrics[label])
        deltas_vs_core[label] = prior._delta(core_baseline[label], after_metrics[label])

        scoped_events = [
            row
            for row in events
            if window["start"] <= _date10(row.get("usable_trade_date")) <= window["end"]
        ]
        details[label] = {
            "raw_forward_event_count": len(scoped_events),
            "ownership_delta_event_count": sum(
                1 for row in scoped_events if row.get("aggregate_ownership_delta_ge_10pct")
            ),
            "raw_price_ready_count": sum(
                1
                for row in raw_candidates
                if row.get("status") == "price_ready"
                and window["start"] <= _date10(row.get("usable_trade_date")) <= window["end"]
            ),
            "ownership_delta_price_ready_count": sum(
                1
                for row in aggregate_candidates
                if row.get("status") == "price_ready"
                and window["start"] <= _date10(row.get("usable_trade_date")) <= window["end"]
            ),
            "raw_selected_trade_count": len(raw_selected),
            "ownership_delta_selected_trade_count": len(aggregate_selected),
            "raw_skipped_count": len(raw_skipped),
            "ownership_delta_skipped_count": len(aggregate_skipped),
            "ownership_delta_selected_trades": aggregate_selected,
            "raw_selected_trades": raw_selected,
            "ownership_delta_skipped_candidates": aggregate_skipped[:20],
        }

    aggregate_vs_raw = prior._aggregate_delta(raw_metrics, after_metrics)
    aggregate_vs_core = prior._aggregate_delta(core_baseline, after_metrics)
    gate = prior._gate_result(aggregate_vs_core, aggregate_vs_raw, details)

    if gate["passed"]:
        decision = "accepted_research_form4_aggregate_delta_requires_shared_adapter"
        status = "accepted_default_off"
        rationale = (
            "The aggregate ownership-delta Form 4 qualifier improved both core and "
            "raw Form 4 overlays while passing materiality, drawdown, sample, and "
            "concentration gates. It remains replay-only until implemented as a "
            "shared default-off adapter with parity coverage."
        )
    elif (
        aggregate_vs_core["aggregate_ev_delta"] > 0.0
        and aggregate_vs_core["aggregate_pnl_delta"] > 0.0
    ):
        decision = "rejected_positive_not_promotable"
        status = "rejected"
        rationale = (
            "The aggregate ownership-delta slice was positive versus core, but it "
            "failed the full Gate 4 standard after raw Form 4 replacement, "
            "materiality, sample, window, drawdown, and concentration checks."
        )
    else:
        decision = "rejected_form4_aggregate_delta_no_stable_alpha"
        status = "rejected"
        rationale = (
            "The aggregate ownership-delta slice did not produce positive, stable "
            "three-window EV/PnL evidence versus the core baseline."
        )

    min_survival = min(float(row.get("survival_rate") or 0.0) for row in core_baseline.values())
    actual_success = 1 if gate["passed"] else 0
    payload: dict[str, Any] = {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": (
            "PIT-safe Form 4 meaningful-purchase events with aggregate purchase "
            "shares / aggregate reported after-transaction shares >= 10% may be a "
            "cleaner free SEC candidate source than raw meaningful-purchase events."
        ),
        "change_type": "event_qualification_replay",
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "trial_family": "form4_ownership_intensity_candidate_pool",
        "trial_variant_id": EXP_ID,
        "changed_variable": "form4_aggregate_ownership_delta_ge_10pct_candidate_v1",
        "single_causal_variable": (
            "aggregate purchase shares / aggregate shares owned following transaction "
            ">= 0.10 on the existing PIT-safe Form 4 forward queue"
        ),
        "prediction": {
            "success_probability": 0.18,
            "expected_ev_delta": None,
            "expected_pnl_delta": None,
            "main_failure_modes": [
                "sample_too_thin",
                "does_not_improve_raw_form4_queue",
                "window_regression",
                "concentration",
            ],
            "confidence_reason": (
                "This is adjacent to exp-20260530-003 but tests aggregate event-level "
                "ownership intensity rather than max single-transaction ownership delta."
            ),
            "recorded_at": "2026-06-03T09:07:56+00:00",
            "brier_score": round((0.18 - actual_success) ** 2, 6),
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "candidate_pool/ranking: cluster-level Form 4 ownership intensity "
                "should separate material insider commitment from token open-market buys."
            ),
            "2_history_check": {
                "exp-20260530-003": (
                    "Max single-transaction ownership delta >= 10% was rejected; "
                    "this run changes the denominator to aggregate event-level "
                    "purchase shares / aggregate reported after shares."
                ),
                "exp-20260531-002": "Purchase-value-to-ADV floor failed raw queue replacement.",
                "exp-20260602-031": "Pre-event underpriced qualifier was positive vs core but failed raw replacement.",
                "exp-20260603-008": "Post-drawdown qualifier was positive vs core but failed raw replacement/sample.",
                "exp-20260603-009": "Form4 + FINRA overlap had no accepted FINRA overlap events.",
            },
            "3_single_causal_variable": (
                "Only the aggregate ownership-delta event qualifier changes; core "
                "strategy, raw Form4 queue, event notional, capacity, hold, LLM/news, "
                "ranking, sizing, and exits stay fixed."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; must improve aggregate "
                "EV/PnL versus core and raw Form4, avoid window EV/PnL regressions, "
                "and pass drawdown, survival, sample, and concentration guards."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260603_010_form4_ownership_delta_purchase.py"
            ),
        },
        "parameters": {
            "form4_queue_name": prior.QUEUE_NAME,
            "form4_rule_version": prior.RULE_VERSION,
            "forward_queue_min_total_purchase_value": prior.FORWARD_QUEUE_MIN_PURCHASE_VALUE,
            "aggregate_ownership_delta_floor": AGGREGATE_OWNERSHIP_DELTA_FLOOR,
            "aggregate_ownership_delta_definition": (
                "sum purchase shares / sum shares owned following transaction"
            ),
            "event_notional_usd": prior.EVENT_NOTIONAL,
            "max_event_positions": prior.MAX_EVENT_POSITIONS,
            "hold_days": prior.HOLD_DAYS,
            "locked_variables": [
                "core universe",
                "core signal generation",
                "core candidate ranking",
                "core position sizing",
                "core exits",
                "LLM/news replay settings",
                "Form 4 parser",
                "Form 4 purchase-value threshold",
                "event notional",
                "event holding period",
                "event capacity",
                "production orders",
                "production watchlists",
            ],
        },
        "date_range": {
            label: f"{window['start']} -> {window['end']}"
            for label, window in WINDOWS.items()
        },
        "backtest_protocol": "docs/backtesting.md canonical three fixed windows",
        "market_regime_summary": {
            label: window["state_note"]
            for label, window in WINDOWS.items()
        },
        "gate1": {
            "protocol": "docs/backtesting.md canonical three fixed windows",
            "core_baseline_metrics": core_baseline,
        },
        "gate2": prior._position_field_check(),
        "gate3": {
            "new_core_filter_added": False,
            "min_survival_rate": round(min_survival, 4),
            "passed": min_survival >= 0.05,
        },
        "core_baseline_metrics": core_baseline,
        "raw_form4_metrics": raw_metrics,
        "after_metrics": after_metrics,
        "before_aggregate": _aggregate_metrics(core_baseline),
        "raw_form4_aggregate": _aggregate_metrics(raw_metrics),
        "after_aggregate": _aggregate_metrics(after_metrics),
        "deltas_vs_raw_form4": deltas_vs_raw,
        "deltas_vs_core": deltas_vs_core,
        "aggregate_delta_vs_raw_form4": aggregate_vs_raw,
        "aggregate_delta_vs_core": aggregate_vs_core,
        "gate4": gate,
        "event_details": details,
        "decision_rationale": rationale,
        "source_diagnostics": source_diagnostics,
        "why_not_other_alpha": (
            "Skipped LLM soft-ranking because replay attribution remains sparse. "
            "Skipped Companyfacts, post-earnings, VBB, VCP, state-surface, and "
            "FINRA threshold retunes per playbook freeze guidance. Options/13F "
            "were skipped because current coverage is not PIT-safe and dense "
            "across the three windows."
        ),
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": (
                "This run uses deterministic free SEC Form 4 rows plus fixed OHLCV "
                "snapshots; LLM soft-ranking remains sample-blocked."
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
                "A shared default-off Form 4 aggregate ownership-delta adapter and "
                "parity test are required before production use."
            ),
        },
        "data_source": {
            "form4_transactions_path": prior._repo_rel(FORM4_TRANSACTIONS_PATH),
            "pit_status": "uses Form 4 accepted_at/usable_trade_date and fixed OHLCV snapshots",
        },
        "related_files": [
            prior._repo_rel(OUT_JSON),
            prior._repo_rel(BEFORE_AGG_JSON),
            prior._repo_rel(RAW_FORM4_AGG_JSON),
            prior._repo_rel(AFTER_AGG_JSON),
            prior._repo_rel(LOG_JSON),
            prior._repo_rel(TICKET_JSON),
            prior._repo_rel(DOC_TICKET_JSON),
            prior._repo_rel(ARTIFACT_MD),
            prior._repo_rel(Path(__file__)),
        ],
    }
    return payload


def persist(payload: dict[str, Any]) -> None:
    prior._write_json(OUT_JSON, payload)
    prior._write_json(BEFORE_AGG_JSON, payload["before_aggregate"])
    prior._write_json(RAW_FORM4_AGG_JSON, payload["raw_form4_aggregate"])
    prior._write_json(AFTER_AGG_JSON, payload["after_aggregate"])
    prior._write_json(LOG_JSON, payload)
    _write_tickets(payload)
    _write_manifest(payload)
    _write_report(payload)
    _append_experiment_log(payload)
    _update_registry(payload)


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "aggregate_delta_vs_core": payload["aggregate_delta_vs_core"],
                "aggregate_delta_vs_raw_form4": payload["aggregate_delta_vs_raw_form4"],
                "gate4": {
                    key: payload["gate4"][key]
                    for key in (
                        "passed",
                        "material_vs_core",
                        "improves_core_cleanly",
                        "improves_vs_raw_form4",
                        "drawdown_guard_passed",
                        "ownership_delta_selected_event_trades",
                        "sample_guard_passed",
                        "single_ticker_positive_share",
                        "positive_pnl_hhi",
                        "failed_reasons",
                    )
                },
                "source_diagnostics": payload["source_diagnostics"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
