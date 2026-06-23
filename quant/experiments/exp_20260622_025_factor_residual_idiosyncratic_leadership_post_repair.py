"""exp-20260622-025: factor-residual leadership post-repair rerun.

Alpha search, replay-only. This intentionally reruns the fixed policy bundle
from blocked exp-20260621-003 after exp-20260622-024 repaired the factor ETF
reference surface. Thresholds, ETF list, notional, hold days, ranking, and
cooldown are inherited unchanged from exp-20260621-003.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any


THIS_FILE = Path(__file__).resolve()
REPO_ROOT = THIS_FILE.parents[2]
EXPERIMENTS_DIR = REPO_ROOT / "quant" / "experiments"
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS_DIR))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import exp_20260621_003_factor_residual_idiosyncratic_leadership as base  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
from quant import ohlcv_warehouse  # noqa: E402


EXPERIMENT_ID = "exp-20260622-025"
STEM = "factor_residual_idiosyncratic_leadership_post_repair"
TRIAL_VARIANT_ID = "factor_residual_leadership_top1_next_open_10d_post_repair_fixed_v1"
CHANGED_VARIABLE = "factor_residual_idiosyncratic_leadership_candidate_source_v1_post_repair_rerun"
OWNER = "alpha-explore"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260622_025_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
HOT_WAREHOUSE = ohlcv_warehouse.hot_path_for(base.framework.WAREHOUSE)

PREDICTION = {
    "success_probability": 0.13,
    "expected_ev_delta": 0.18,
    "expected_pnl_delta": 2500.0,
    "main_failure_modes": [
        "generic_momentum_relabel",
        "old_thin_regression",
        "drawdown_drift",
        "accepted_comparator_not_beaten",
        "production_overlay_mismatch",
    ],
    "confidence_reason": (
        "Prior exp-20260621-003 was blocked before alpha evaluation because "
        "factor ETF rows were missing from production-visible warehouse reads. "
        "exp-20260622-024 now provides PIT MTUM/QUAL/VLUE/USMV/SIZE rows "
        "through the hot overlay, but broad residual momentum remains high "
        "multiple-testing risk."
    ),
    "recorded_at": "2026-06-22T23:21:55+00:00",
}

PRODUCTION_IMPACT = {
    **base.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_post_repair_no_shared_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "default_off_paper_only": True,
    "daily_snapshot_exposed": False,
    "trade_enabled": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "uses_hot_warehouse_overlay": True,
    "parity_note": (
        "This experiment changes no production code. It reruns the previously "
        "blocked fixed factor-residual policy bundle using the official cold+hot "
        "OHLCV overlay reader. A positive result is only a replay lead until a "
        "shared default-off helper computes the same factor reference context, "
        "rolling beta fit, residual leadership gate, cooldown, next-open paper "
        "entry, 10-day exit, costs, and concentration controls in both daily "
        "and historical paths."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: after exp-20260622-024 repaired the production-visible "
        "MTUM/QUAL/VLUE/USMV/SIZE hot overlay, the fixed exp-20260621-003 "
        "factor-residual idiosyncratic leadership bundle can finally be "
        "evaluated. Liquid stocks with positive 20-session leadership after "
        "rolling residualization against SPY and factor ETF returns may capture "
        "idiosyncratic demand rather than generic market/style beta."
    ),
    "2_history_check": {
        "novelty_gate": (
            "Novelty gate was overridden only because exp-20260621-003 was "
            "blocked at Gate 2. The new evidence axis is exp-20260622-024's "
            "production-visible hot overlay factor ETF rows across all canonical "
            "windows, not any threshold, ETF-list, hold-day, notional, ranking, "
            "or cooldown change."
        ),
        "exp-20260621-003": (
            "Blocked factor-residual idiosyncratic leadership at Gate 2 because "
            "the factor ETF reference surface was absent from warehouse reads."
        ),
        "exp-20260622-024": (
            "Accepted measurement repair that seeded missing MTUM/QUAL/VLUE/"
            "USMV/SIZE close-only reference rows into the hot warehouse overlay."
        ),
        "exp-20260620-027": (
            "Diagnostic factor ETF sidecar that supplied the adjusted-close rows "
            "later materialized by exp-20260622-024."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": base.PRE_RUN_QUESTIONS["4_acceptance_standard"],
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260622_025_factor_residual_idiosyncratic_leadership_post_repair.py"
    ),
}


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _load_window_snapshot(
    *,
    cfg: dict[str, str],
    eligible_tickers: set[str],
) -> dict[str, list[dict[str, Any]]]:
    """Load the same rows exp003 needed, but through cold+hot overlay view."""

    start = base.framework._parse_date(cfg["start"]) - timedelta(days=150)
    end = base.framework._parse_date(cfg["end"]) + timedelta(days=40)
    tickers = sorted(set(eligible_tickers) | set(base.REFERENCE_TICKERS))
    snapshot: dict[str, dict[str, dict[str, Any]]] = {ticker: {} for ticker in tickers}

    with ohlcv_warehouse.connect_overlay_reader(base.framework.WAREHOUSE) as con:
        for chunk_start in range(0, len(tickers), 800):
            chunk = tickers[chunk_start : chunk_start + 800]
            placeholders = ",".join("?" for _ in chunk)
            sql = (
                "select ticker, date, open, high, low, close, volume "
                "from ohlcv_overlay "
                f"where ticker in ({placeholders}) and date >= ? and date <= ? "
                "order by ticker, date"
            )
            params = [*chunk, base.framework._date_str(start), base.framework._date_str(end)]
            for row in con.execute(sql, params):
                ticker, day, open_, high, low, close, volume = row
                snapshot[str(ticker).upper()][str(day)[:10]] = {
                    "Date": str(day)[:10],
                    "Open": float(open_),
                    "High": float(high),
                    "Low": float(low),
                    "Close": float(close),
                    "Volume": float(volume),
                }

    return {
        ticker: [rows[day] for day in sorted(rows)]
        for ticker, rows in snapshot.items()
        if rows
    }


def _patch_base_module() -> None:
    base.THIS_FILE = THIS_FILE
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.STEM = STEM
    base.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.RULE_VERSION = CHANGED_VARIABLE
    base.OWNER = OWNER
    base.OUT_DIR = OUT_DIR
    base.OUT_JSON = OUT_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.CARD_MD = CARD_MD
    base.MANIFEST_JSON = MANIFEST_JSON
    base.EXPERIMENT_LOG = EXPERIMENT_LOG
    base.REGISTRY_JSON = REGISTRY_JSON
    base.PREDICTION = PREDICTION
    base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    base.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    base._load_window_snapshot = _load_window_snapshot


def _post_repair_finalize(payload: dict[str, Any]) -> dict[str, Any]:
    gate4 = payload["gate4"]
    aggregate = payload["delta_metrics"]["aggregate"]
    target_summary = payload["target_trade_summary"]
    blocked = payload.get("status") == "blocked" or not payload["gate2"].get("passed", False)

    if blocked:
        decision = "blocked_factor_residual_post_repair_overlay_missing"
        payload["status"] = "blocked"
    elif gate4["passed"]:
        decision = "positive_replay_lead_not_promoted_factor_residual_post_repair"
        payload["status"] = "positive_replay_lead_not_promoted"
    else:
        decision = "rejected_factor_residual_post_repair_candidate_pool"
        payload["status"] = "rejected"

    payload["decision"] = decision
    payload["gate4"]["decision"] = decision
    payload["hypothesis"] = PRE_RUN_QUESTIONS["1_alpha_hypothesis"]
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["single_causal_variable"] = CHANGED_VARIABLE
    payload["trial_variant_id"] = TRIAL_VARIANT_ID
    payload["new_evidence_type"] = "post_repair_hot_overlay_factor_etf_reference_surface"
    payload["nearby_prior_experiments"] = [
        "exp-20260621-003",
        "exp-20260622-024",
        "exp-20260620-027",
        "exp-20260614-006",
        "exp-20260620-020",
        "exp-20260621-002",
    ]
    payload["prior_trial_count"] = 1
    payload["prediction"] = PREDICTION
    payload["pre_run_questions"] = PRE_RUN_QUESTIONS
    payload["production_impact"] = PRODUCTION_IMPACT
    payload["backtest_protocol"]["candidate_ohlcv_source"] = _repo_rel(base.framework.WAREHOUSE)
    payload["backtest_protocol"]["cross_asset_context_source"] = (
        f"{_repo_rel(base.framework.WAREHOUSE)} plus hot overlay {_repo_rel(HOT_WAREHOUSE)}"
    )
    payload["backtest_protocol"]["hot_overlay_source"] = _repo_rel(HOT_WAREHOUSE)
    payload["backtest_protocol"]["overlay_reader"] = "quant.ohlcv_warehouse.connect_overlay_reader"

    if blocked:
        why = (
            "Blocked after repair rerun: the official cold+hot overlay reader "
            "still did not expose complete factor ETF feature dates, so Gate 2 "
            "cannot support an alpha verdict."
        )
    elif gate4["passed"]:
        why = (
            "Gate 4 passed numerically after the repaired overlay made the "
            "fixed factor-residual bundle evaluable, but this remains a "
            "private replay lead because no shared default-off historical/daily "
            "helper was promoted."
        )
    else:
        why = (
            "Rejected after repair. Once the factor ETF surface was available, "
            "the fixed factor-residual leadership bundle did not add robust "
            "replacement value versus accepted compression/distribution "
            "candidate-pool comparators after next-open execution, costs, "
            "cooldown, drawdown, and concentration checks (failed: {})."
        ).format(", ".join(gate4["failed_reasons"]) or "none")

    payload["interpretation"] = why
    payload["next_evidence_needed"] = (
        "Need materially different PIT flow, ownership, borrow/options, "
        "event-quality, or closed forward replacement-value evidence before "
        "revisiting broad factor-residual leadership. Do not sweep factor ETF "
        "lists, beta lookbacks, residual thresholds, RS/close/volume/volatility "
        "guards, top-N, hold, cooldown, or notional on these frozen windows."
    )
    payload["post_run_reflection"] = {
        "why_result_happened": why,
        "outcome_summary": (
            "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}; "
            "max drawdown drift {:+.4f}; {} paper trades.".format(
                aggregate["expected_value_score_delta_sum"],
                aggregate["total_pnl_delta_sum"],
                float(aggregate["max_drawdown_delta_max"] or 0.0),
                target_summary["total_trade_count"],
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping factor ETF lists, beta lookbacks, residual "
            "thresholds, factor share/R2 caps, RS/close/volume/volatility "
            "guards, top-N, hold days, cooldown, or notional on these frozen "
            "windows."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
    }
    payload["related_files"] = [
        _repo_rel(THIS_FILE),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(EXPERIMENT_LOG),
        _repo_rel(REGISTRY_JSON),
    ]
    return payload


def _persist(payload: dict[str, Any]) -> None:
    log_record = base._build_log_record(payload)
    base.framework._write_json(OUT_JSON, payload)
    base.framework._write_json(LOG_JSON, payload)
    base.framework._write_text(CARD_MD, base._build_card(payload))
    base.framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": base.TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "decision": payload["decision"],
        "summary": payload["interpretation"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": log_record["aggregate_expected_value_delta"],
        "aggregate_strategy_total_pnl_delta": log_record["aggregate_strategy_total_pnl_delta"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )
    base._write_manifest(payload)


def main() -> None:
    _patch_base_module()
    base._configure_template()
    payload = base._finalize_payload(base.template._build_payload())
    payload = _post_repair_finalize(payload)
    _persist(payload)
    print(json.dumps(base.framework._safe(base._build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
