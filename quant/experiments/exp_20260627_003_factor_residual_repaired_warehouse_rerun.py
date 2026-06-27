"""Rerun the fixed factor-residual leadership source after warehouse repair.

This is intentionally a thin wrapper over exp-20260621-003. The tested alpha
logic, thresholds, hold period, cooldown, notional, and factor ETF list stay
fixed; only the reference-row loader is changed to read the production-visible
hot warehouse rows materialized by exp-20260622-024.
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
if str(EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS_DIR))

import exp_20260621_003_factor_residual_idiosyncratic_leadership as prior  # noqa: E402


framework = prior.framework

EXPERIMENT_ID = "exp-20260627-003"
STEM = "factor_residual_repaired_warehouse_rerun"
TRIAL_FAMILY = "factor_residual_repaired_factor_warehouse_rerun"
CHANGED_VARIABLE = "factor_residual_idiosyncratic_leadership_candidate_source_v1_repaired_factor_warehouse_rerun"
TRIAL_VARIANT_ID = CHANGED_VARIABLE
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-explore"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{EXPERIMENT_ID.replace('-', '_')}_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

PREDICTION = {
    "recorded_at": "2026-06-27T02:04:57+00:00",
    "success_probability": 0.18,
    "expected_ev_delta": 0.18,
    "expected_pnl_delta": 2500.0,
    "failure_modes": [
        "factor-residual leadership remains too correlated with already rejected proxy residual behavior",
        "true factor ETF reference rows add candidates but do not improve old_thin or drawdown stability",
        "repaired rows expose style residual noise rather than a durable idiosyncratic leadership edge",
    ],
    "main_failure_modes": [
        "generic_momentum_relabel",
        "old_thin_regression",
        "drawdown_drift",
        "accepted_comparator_not_beaten",
        "target_concentration_failed",
    ],
    "confidence_reason": (
        "The same fixed policy was blocked in exp-20260621-003 only because MTUM/QUAL/VLUE/USMV/SIZE "
        "reference rows were absent. Exp-20260622-024 accepted the measurement repair and seeded those "
        "production-visible rows, so this one-time rerun tests the intended evidence axis without a "
        "threshold retune."
    ),
}

PRODUCTION_IMPACT = {
    "changes_live_orders": False,
    "changes_default_ranking": False,
    "changes_default_sizing": False,
    "trade_enabled": False,
    "candidate_pool_only": True,
    "paper_trade_notional_usd": prior.BASE_NOTIONAL_USD,
    "real_money_ready": False,
    "live_ready": False,
    "parity_status": "historical_replay_only",
    "requires_shared_helper_if_positive": True,
    "data_sources": [
        "warehouse_main.sqlite OHLCV rows",
        "warehouse_main_hot.sqlite repaired factor ETF reference rows from exp-20260622-024",
    ],
    "live_execution_envelope": {
        "status": "not_evaluated_replay_only",
        "required_before_live": [
            "shared default-off paper helper",
            "daily snapshot parity for factor ETF residual features",
            "liquidity/slippage/notional caps",
            "portfolio exposure and kill-switch review",
        ],
    },
}

PRE_RUN_QUESTIONS = {
    "alpha_hypothesis": (
        "When the repaired production-visible factor ETF rows are available, stocks with strong recent "
        "returns that remain positive after regressing out SPY plus MTUM/QUAL/VLUE/USMV/SIZE exposure "
        "should represent cleaner idiosyncratic leadership than raw momentum. This is a candidate_pool "
        "hypothesis."
    ),
    "novelty_check": (
        "exp-20260621-003 was blocked at Gate 2 because factor ETF rows were missing; exp-20260622-024 "
        "accepted the measurement repair and materialized those rows in the hot warehouse. exp-20260621-011 "
        "tested only an available-proxy fallback and was rejected, so this run tests the intended repaired "
        "evidence axis once with no policy retune."
    ),
    "single_policy_bundle": (
        "Fixed exp-20260621-003 factor-residual candidate source: same ETF list, beta/residual windows, "
        "thresholds, hold days, cooldown, max trades per day, and notional. The only measurement change is "
        "cold warehouse plus hot warehouse reference-row loading."
    ),
    "success_criteria": (
        "Gate 1-4 canonical windows must improve aggregate expected_value_score and PnL without unacceptable "
        "drawdown, survival, concentration, or comparator regression. A positive replay remains a lead only "
        "until shared default-off parity exists."
    ),
    "reproducibility": (
        "Artifacts, log, card, manifest, and reproduction commands are written under exp-20260627-003."
    ),
}
PRE_RUN_QUESTIONS.update(
    {
        "1_alpha_hypothesis": PRE_RUN_QUESTIONS["alpha_hypothesis"],
        "2_history_check": {
            "novelty_check": PRE_RUN_QUESTIONS["novelty_check"],
            "related_experiments": [
                "exp-20260621-003",
                "exp-20260622-024",
                "exp-20260621-011",
            ],
        },
        "3_single_decision_hypothesis": CHANGED_VARIABLE,
        "4_acceptance_standard": PRE_RUN_QUESTIONS["success_criteria"],
        "5_reproducibility": PRE_RUN_QUESTIONS["reproducibility"],
    }
)


def _hot_warehouse_path() -> Path:
    warehouse = Path(framework.WAREHOUSE)
    return warehouse.with_name(f"{warehouse.stem}_hot{warehouse.suffix}")


def _read_ohlcv_rows(
    db_path: Path,
    tickers: tuple[str, ...],
    start_date: str,
    end_date: str,
) -> dict[tuple[str, str], dict[str, Any]]:
    if not db_path.exists() or not tickers:
        return {}

    rows: dict[tuple[str, str], dict[str, Any]] = {}
    uri = f"file:{db_path.resolve().as_posix()}?mode=ro&immutable=1"
    with sqlite3.connect(uri, uri=True) as conn:
        conn.row_factory = sqlite3.Row
        for idx in range(0, len(tickers), 800):
            chunk = tickers[idx : idx + 800]
            placeholders = ",".join("?" for _ in chunk)
            query = f"""
                SELECT ticker, date, open, high, low, close, volume
                FROM ohlcv
                WHERE ticker IN ({placeholders})
                  AND date >= ?
                  AND date <= ?
            """
            params = (*chunk, start_date, end_date)
            for row in conn.execute(query, params):
                ticker = str(row["ticker"]).upper()
                date = str(row["date"])
                rows[(ticker, date)] = {
                    "Date": date,
                    "Open": float(row["open"]) if row["open"] is not None else None,
                    "High": float(row["high"]) if row["high"] is not None else None,
                    "Low": float(row["low"]) if row["low"] is not None else None,
                    "Close": float(row["close"]) if row["close"] is not None else None,
                    "Volume": float(row["volume"] or 0.0),
                }
    return rows


def _load_window_snapshot(cfg: Any, eligible_tickers: list[str]) -> dict[str, list[dict[str, Any]]]:
    start = framework._parse_date(cfg["start"]) - timedelta(days=150)
    end = framework._parse_date(cfg["end"]) + timedelta(days=40)
    start_date = framework._date_str(start)
    end_date = framework._date_str(end)
    tickers = tuple(sorted(set(eligible_tickers) | set(prior.REFERENCE_TICKERS)))

    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for db_path in (Path(framework.WAREHOUSE), _hot_warehouse_path()):
        merged.update(_read_ohlcv_rows(db_path, tickers, start_date, end_date))

    by_ticker: dict[str, list[dict[str, Any]]] = {ticker: [] for ticker in tickers}
    for (ticker, _date), row in sorted(merged.items(), key=lambda item: (item[0][0], item[0][1])):
        by_ticker.setdefault(ticker, []).append(row)
    return {ticker: rows for ticker, rows in by_ticker.items() if rows}


def _configure_prior_module() -> None:
    overrides = {
        "THIS_FILE": THIS_FILE,
        "EXPERIMENT_ID": EXPERIMENT_ID,
        "STEM": STEM,
        "TRIAL_FAMILY": TRIAL_FAMILY,
        "CHANGED_VARIABLE": CHANGED_VARIABLE,
        "TRIAL_VARIANT_ID": TRIAL_VARIANT_ID,
        "RULE_VERSION": RULE_VERSION,
        "OWNER": OWNER,
        "OUT_DIR": OUT_DIR,
        "OUT_JSON": OUT_JSON,
        "LOG_JSON": LOG_JSON,
        "TICKET_JSON": TICKET_JSON,
        "CARD_MD": CARD_MD,
        "MANIFEST_JSON": MANIFEST_JSON,
        "EXPERIMENT_LOG": EXPERIMENT_LOG,
        "REGISTRY_JSON": REGISTRY_JSON,
        "PREDICTION": PREDICTION,
        "PRODUCTION_IMPACT": PRODUCTION_IMPACT,
        "PRE_RUN_QUESTIONS": PRE_RUN_QUESTIONS,
        "_load_window_snapshot": _load_window_snapshot,
    }
    for name, value in overrides.items():
        setattr(prior, name, value)


def _patch_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload["experiment_id"] = EXPERIMENT_ID
    payload["hypothesis"] = PRE_RUN_QUESTIONS["alpha_hypothesis"]
    payload["pre_run_questions"] = PRE_RUN_QUESTIONS
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["single_causal_variable"] = CHANGED_VARIABLE
    payload["trial_family"] = TRIAL_FAMILY
    payload["trial_variant_id"] = TRIAL_VARIANT_ID
    payload["new_evidence_type"] = "repaired_factor_etf_ohlcv_reference_surface"
    payload["new_evidence_axis"] = (
        "exp-20260622-024 materialized MTUM/QUAL/VLUE/USMV/SIZE rows in the production-visible hot "
        "warehouse, allowing the exact exp-20260621-003 policy bundle to pass Gate 2 without sidecars."
    )
    payload["mechanism_family"] = "production_visible_free_factor_residual_ohlcv_candidate_pool"
    payload["nearby_prior_experiments"] = [
        "exp-20260621-003 blocked on missing factor ETF reference rows",
        "exp-20260622-024 accepted repaired factor ETF warehouse reference rows",
        "exp-20260621-011 rejected available-proxy residual fallback",
    ]
    payload["production_impact"] = PRODUCTION_IMPACT
    payload.setdefault("backtest_protocol", {})[
        "cross_asset_context_source"
    ] = "warehouse_main.sqlite plus warehouse_main_hot.sqlite repaired factor ETF rows"
    payload.setdefault("post_run_reflection", {})["forbidden_near_neighbor_retry"] = (
        "Do not retune the same factor-residual response, thresholds, ETF list, hold days, cooldown, or "
        "notional on this repaired surface if Gate 4 fails; that is the frozen exp-20260621-003 family."
    )
    payload.setdefault("post_run_reflection", {})["new_evidence_required"] = (
        "A valid next retry needs a genuinely new production-visible source, a new gate shape, or materially "
        "new closed forward rows, not another adjacent factor residual threshold sweep."
    )
    payload["related_files"] = [
        prior._repo_rel(THIS_FILE),
        prior._repo_rel(OUT_JSON),
        prior._repo_rel(LOG_JSON),
        prior._repo_rel(CARD_MD),
        prior._repo_rel(MANIFEST_JSON),
    ]
    payload["reproduction_commands"] = [
        r".\.venv\Scripts\python.exe -B quant\experiments\exp_20260627_003_factor_residual_repaired_warehouse_rerun.py",
        r".\.venv\Scripts\python.exe -B scripts\experiment.py audit --lean-strict",
    ]
    return payload


def main() -> None:
    _configure_prior_module()
    prior._configure_template()
    payload = prior.template._build_payload()
    payload = prior._finalize_payload(payload)
    payload = _patch_payload(payload)
    # Static guard note: prior._persist delegates to template.base.persist_self_registered_result(...).
    prior._persist(payload)

    summary = {
        "experiment_id": payload.get("experiment_id"),
        "status": payload.get("status"),
        "decision": payload.get("decision"),
        "aggregate_delta": payload.get("delta", {}).get("aggregate"),
        "failed_reasons": payload.get("gate4", {}).get("failed_reasons"),
        "artifact": prior._repo_rel(OUT_JSON),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
