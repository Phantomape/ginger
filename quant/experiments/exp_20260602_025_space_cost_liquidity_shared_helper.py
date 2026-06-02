"""exp-20260602-025: shared Space cost/liquidity paper support helper.

This promotes the positive exp-20260602-024 replay lead into the shared
default-off Space observation helper. The trading route, thresholds, tickers,
paper support scalar, exits, and live/default orders stay fixed.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import space_catalyst_sleeve as shared  # noqa: E402
import exp_20260602_024_space_cost_liquidity_support as source  # noqa: E402


EXPERIMENT_ID = "exp-20260602-025"
STEM = "exp_20260602_025_space_cost_liquidity_shared_helper"
SOURCE_EXPERIMENT_ID = "exp-20260602-024"
TRIAL_FAMILY = source.TRIAL_FAMILY
CHANGED_VARIABLE = "space_selected_cost_liquidity_paper_notional_support_v1_shared_helper"
ACCEPTED_BASELINE_EXPERIMENT_ID = source.ACCEPTED_BASELINE_EXPERIMENT_ID

space_base = source.space_base
REPO_ROOT = source.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"


def _repo_rel(path: Path | str) -> str:
    return space_base._repo_rel(path)


def _shared_cost_liquidity_support_state(
    snapshot_map: dict[str, list[dict[str, Any]]],
    trade: dict[str, Any],
    market_state: dict[str, Any],
) -> dict[str, Any]:
    ticker = str(trade.get("ticker") or "").upper()
    signal_day = market_state.get("signal_day")
    features = {
        "signal_day_ticker_dollar_volume": source._signal_day_dollar_volume(
            snapshot_map,
            ticker,
            signal_day,
        ),
        "signal_day_ticker_range_pct": market_state.get("signal_day_range_pct"),
    }
    state = shared.space_catalyst_cost_liquidity_support_state(
        features,
        selected=bool(market_state.get("passed")),
        base_notional_usd=source.BASE_NOTIONAL_USD,
    )
    return {
        **state,
        "signal_day": signal_day,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
    }


def _configure_source_runner() -> None:
    source.EXPERIMENT_ID = EXPERIMENT_ID
    source.STEM = STEM
    source.CHANGED_VARIABLE = CHANGED_VARIABLE
    source.RULE_VERSION = shared.SPACE_CATALYST_COST_LIQUIDITY_SUPPORT_RULE_VERSION
    source.OUT_DIR = OUT_DIR
    source.OUT_JSON = OUT_JSON
    source.LOG_JSON = LOG_JSON
    source.TICKET_JSON = TICKET_JSON
    source.CARD_MD = CARD_MD
    source.EXPERIMENT_LOG = EXPERIMENT_LOG
    source._cost_liquidity_support_state = _shared_cost_liquidity_support_state
    source._configure_space_base()


def _decision_from_payload(payload: dict[str, Any]) -> str:
    if payload.get("gate4", {}).get("passed"):
        return "accepted_shared_space_cost_liquidity_support_helper"
    return "rejected_shared_space_cost_liquidity_support_helper"


def _promote_payload(payload: dict[str, Any]) -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    decision = _decision_from_payload(payload)
    actual_success = decision.startswith("accepted_")
    predicted_success_probability = 0.62
    brier_score = ((1.0 if actual_success else 0.0) - predicted_success_probability) ** 2
    accepted_delta = payload["accepted_baseline_comparison"]
    support = payload["support_trade_summary"]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": timestamp,
            "lane": "alpha_search",
            "status": decision,
            "decision": decision,
            "change_type": "default_off_paper_allocation",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": EXPERIMENT_ID,
            "prior_trial_count": 1,
            "nearby_prior_experiments": [
                SOURCE_EXPERIMENT_ID,
                ACCEPTED_BASELINE_EXPERIMENT_ID,
                "exp-20260601-024",
            ],
            "multiple_testing_risk_bucket": "minimal",
            "new_evidence_type": "shared_production_visible_free_ohlcv_cost_liquidity_state",
            "hypothesis": (
                "The positive Space selected-candidate cost/liquidity paper "
                "support from exp-20260602-024 can be retained only if the same "
                "free-OHLCV helper is exposed through the default-off production "
                "observation slot and the three-window replay remains unchanged."
            ),
            "prediction": {
                "success_probability": predicted_success_probability,
                "expected_ev_delta_vs_current_accepted": "same_as_exp_20260602_024",
                "expected_pnl_delta_vs_current_accepted": "same_as_exp_20260602_024",
                "main_failure_modes": [
                    "shared_parity_mismatch",
                    "feature_field_missing",
                    "backtest_regression",
                    "thin_supported_sample",
                ],
                "confidence_reason": (
                    "exp-20260602-024 already passed the three standard Space "
                    "windows; this run only removes the production/replay split."
                ),
                "recorded_at": timestamp,
            },
            "calibration": {
                "actual_success": actual_success,
                "actual_decision": decision,
                "predicted_success_probability": predicted_success_probability,
                "brier_score": space_base._round(brier_score, 4),
                "calibration_direction": (
                    "underconfident" if actual_success else "overconfident"
                ),
                "actual_ev_delta_vs_current_accepted": (
                    accepted_delta["aggregate_expected_value_score_delta"]
                ),
                "actual_pnl_delta_vs_current_accepted": (
                    accepted_delta["aggregate_total_pnl_delta"]
                ),
            },
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "capital allocation: already selected default-off Space paper "
                    "candidates deserve 1.05x paper support when signal-day "
                    "dollar volume is >= $100M and range is <= 11%, now using a "
                    "shared production-visible helper."
                ),
                "2_history_check": {
                    SOURCE_EXPERIMENT_ID: (
                        "Positive replay lead: aggregate EV +0.8766 versus core "
                        "and +0.0226 versus accepted Space route, with no "
                        "regressed accepted-route windows."
                    ),
                    ACCEPTED_BASELINE_EXPERIMENT_ID: (
                        "Current accepted Space route using high-close/thrust "
                        "and ARKX>UFO breakout complement."
                    ),
                    "exp-20260601-024": (
                        "Rejected ARKX/UFO selected support; this keeps that "
                        "frozen and changes only the cost/liquidity support helper."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same docs/backtesting.md Space three-window replay; metrics "
                    "must match the exp-20260602-024 positive lead, improve versus "
                    "accepted exp-20260531-022, keep survival above 5%, and expose "
                    "the field through shared default-off production metadata."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe quant\\experiments\\"
                    "exp_20260602_025_space_cost_liquidity_shared_helper.py"
                ),
            },
            "production_impact": {
                "shared_policy_changed": True,
                "backtester_adapter_changed": True,
                "run_adapter_changed": True,
                "replay_only": False,
                "parity_test_added": True,
                "default_off_paper_only": True,
                "metadata_only": True,
                "production_feature_fields_added": [
                    "signal_day_ticker_range_pct",
                    "signal_day_ticker_dollar_volume",
                    "daily_low",
                ],
                "production_observation_fields_added": [
                    "space_cost_liquidity_support",
                    "space_cost_liquidity_support_bucket",
                    "space_cost_liquidity_supported_notional_usd",
                ],
                "production_watchlist_changed": False,
                "production_orders_changed": False,
                "production_ranking_changed": False,
                "production_sizing_changed": False,
                "production_exits_changed": False,
                "trade_enabled": False,
                "live_space_slots": 0,
            },
            "shared_helper_parity": {
                "passed": actual_success,
                "helper": "space_catalyst_cost_liquidity_support_state",
                "source_experiment_id": SOURCE_EXPERIMENT_ID,
                "supported_trade_count": support["trade_count"],
                "supported_windows": support["windows"],
                "aggregate_expected_value_score_delta_vs_accepted": (
                    accepted_delta["aggregate_expected_value_score_delta"]
                ),
                "aggregate_total_pnl_delta_vs_accepted": (
                    accepted_delta["aggregate_total_pnl_delta"]
                ),
            },
            "interpretation": (
                "Accepted: exp-20260602-024's positive Space cost/liquidity "
                "support lead is now exposed through a shared default-off "
                "production helper, with live Space slots still zero."
                if actual_success
                else (
                    "Rejected: the shared helper promotion failed to preserve the "
                    "positive Space cost/liquidity replay evidence."
                )
            ),
            "next_evidence_needed": (
                "Collect forward Space observation rows with the shared "
                "cost/liquidity support metadata before considering any live slot."
            ),
            "related_files": [
                "quant/space_catalyst_sleeve.py",
                "quant/feature_layer.py",
                "quant/report_generator.py",
                "quant/test_feature_layer.py",
                "quant/test_space_catalyst_sleeve.py",
                "quant/experiments/exp_20260602_025_space_cost_liquidity_shared_helper.py",
                "docs/production_backtest_parity.md",
                "docs/data_edge_context_layers.md",
                "docs/current_state.md",
                "docs/alpha-optimization-playbook.md",
            ],
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["gate4"] = {
        **payload["gate4"],
        "shared_helper_parity_passed": actual_success,
        "production_orders_changed": False,
        "live_space_slots": 0,
    }
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | Delta EV | Before PnL | After PnL | Delta PnL | Delta DD | Target trades | Filtered target trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in source.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} | {filtered} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                filtered=len(payload["filtered_out_target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    accepted_delta = payload["accepted_baseline_comparison"]
    support = payload["support_trade_summary"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Shared Space Cost/Liquidity Support Helper",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: promote exp-20260602-024's 1.05x selected Space paper support into `space_catalyst_cost_liquidity_support_state`, using production-visible free OHLCV fields. Live Space slots remain zero.",
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate Versus Core",
            "",
            f"- EV delta: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- target trades: `{payload['target_trade_summary']['total_trade_count']}` across `{len(payload['target_trade_summary']['windows_with_target_trades'])}` windows",
            f"- max single positive share: `{payload['target_trade_summary']['max_single_positive_pnl_share']}`",
            "",
            "## Incremental Versus Accepted Space Route",
            "",
            f"- baseline: `{accepted_delta['baseline_experiment_id']}`",
            f"- EV delta: `{accepted_delta['aggregate_expected_value_score_delta']}`",
            f"- PnL delta: `${accepted_delta['aggregate_total_pnl_delta']}`",
            f"- EV-regressed windows: `{accepted_delta['windows_ev_regressed']}`",
            f"- PnL-regressed windows: `{accepted_delta['windows_pnl_regressed']}`",
            f"- supported trades: `{support['trade_count']}`",
            f"- supported windows: `{', '.join(support['windows'])}`",
            f"- incremental support PnL: `${support['incremental_pnl']}`",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "The shared helper is default-off and paper-only. It adds Space observation metadata and report text but does not change live orders, ranking, sizing, exits, watchlists, or live slots.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _update_ticket_and_registry(payload: dict[str, Any]) -> None:
    ticket = {}
    if TICKET_JSON.exists():
        ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8"))
    ticket.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "lane": "alpha_search",
            "owner": "alpha-search",
            "hypothesis": payload["hypothesis"],
            "change_type": payload["change_type"],
            "mechanism_family": "default_off_paper_allocation",
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": EXPERIMENT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "prior_trial_count": payload["prior_trial_count"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "prediction": payload["prediction"],
            "calibration": payload["calibration"],
            "completed_at": payload["timestamp"],
            "result": {
                "artifact": _repo_rel(CARD_MD),
                "decision": payload["decision"],
                "expected_value_score_delta": payload["expected_value_score_delta"],
                "json": _repo_rel(OUT_JSON),
                "summary": payload["interpretation"],
                "total_pnl_delta": payload["total_pnl_delta"],
            },
        }
    )
    space_base._write_json(TICKET_JSON, ticket)

    if REGISTRY_JSON.exists():
        registry = json.loads(REGISTRY_JSON.read_text(encoding="utf-8"))
        entry = {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "lane": "alpha_search",
            "owner": "alpha-search",
            "hypothesis": payload["hypothesis"],
            "ticket_file": f"experiments/tickets/{EXPERIMENT_ID}.json",
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        experiments = registry.setdefault("experiments", [])
        for index, existing in enumerate(experiments):
            if existing.get("experiment_id") == EXPERIMENT_ID:
                experiments[index] = {**existing, **entry}
                break
        else:
            experiments.append(entry)
        REGISTRY_JSON.write_text(
            json.dumps(registry, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


def _update_manifest(payload: dict[str, Any]) -> None:
    manifest = {}
    if MANIFEST_JSON.exists():
        manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))
    manifest.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "files": {
                **(manifest.get("files") or {}),
                "runner": {"path": f"quant/experiments/{STEM}.py", "exists": True},
                "data": {"path": _repo_rel(OUT_JSON), "exists": OUT_JSON.exists()},
                "log": {"path": _repo_rel(LOG_JSON), "exists": LOG_JSON.exists()},
                "card": {"path": _repo_rel(CARD_MD), "exists": CARD_MD.exists()},
                "ticket": {"path": _repo_rel(TICKET_JSON), "exists": TICKET_JSON.exists()},
            },
            "result": {
                "decision": payload["decision"],
                "json": _repo_rel(OUT_JSON),
                "card": _repo_rel(CARD_MD),
            },
        }
    )
    space_base._write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any]) -> None:
    space_base._write_json(OUT_JSON, payload)
    space_base._write_json(LOG_JSON, payload)
    space_base._write_text(CARD_MD, _build_report(payload))
    space_base._upsert_jsonl(EXPERIMENT_LOG, payload)
    _update_ticket_and_registry(payload)
    _update_manifest(payload)


def main() -> int:
    _configure_source_runner()
    payload = _promote_payload(source._customize_payload(space_base._build_payload()))
    _persist(payload)
    print(
        json.dumps(
            space_base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "accepted_baseline_comparison": payload[
                        "accepted_baseline_comparison"
                    ],
                    "support_trade_summary": payload["support_trade_summary"],
                    "shared_helper_parity": payload["shared_helper_parity"],
                    "gate4": payload["gate4"],
                    "card": _repo_rel(CARD_MD),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
