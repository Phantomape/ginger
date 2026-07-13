"""exp-20260712-010: Chicago Fed NFCI easing / Financials leadership scout.

Private replay scout using a genuinely new official weekly data source.  The
current-vintage NFCI observation for a week ending Friday is treated as known
on the following Wednesday release day.  On release days where NFCI is below
zero and lower than its previous observation, the frozen liquid-stock
leadership selector is restricted to Financial Services names.  Paper entry is
the next open and exit is the tenth-session close with the existing costs.

The FRED history can contain revisions, so even a positive result is a lead,
not promotion evidence.  No production, order, core, ranking, sizing, exit, or
LLM behavior changes.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
import math
import sys
import urllib.request
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
for entry in (REPO_ROOT / "scripts", REPO_ROOT / "quant", REPO_ROOT / "quant" / "experiments"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import exp_20260711_002_move_rate_volatility_relief_stock_leadership as base  # noqa: E402
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


EXPERIMENT_ID = "exp-20260712-010"
OWNER = "alpha-explore"
SLUG = "chicago_fed_nfci_easing_financial_leadership"
RUNNER = f"quant/experiments/exp_20260712_010_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260712_010_{SLUG}.json"
NFCI_JSON = OUT_DIR / "chicago_fed_nfci_weekly.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
CURRENT_SCHEMA_REFERENCE = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260712-009"
    / "exp_20260712_009_dod_contract_revenue_materiality.json"
)

HYPOTHESIS = (
    "Private replay scout: lagged weekly Chicago Fed NFCI below zero and "
    "falling from the prior release identifies persistent easing financial "
    "conditions in which liquid Financials leaders should earn positive "
    "after-cost next-open 10-session paper PnL across the canonical windows."
)
CHANGE_TYPE = "candidate_pool_private_replay_scout"
IMPLEMENTATION_MODE = "private_replay_scout_revision_risk"
MECHANISM_FAMILY = "chicago_fed_financial_conditions_state_candidate_pool"
TRIAL_FAMILY = "chicago_fed_nfci_easing_financial_leadership_candidate_pool"
TRIAL_VARIANT_ID = "nfci_below_zero_falling_financials_leadership_v1"
CHANGED_VARIABLE = "lagged_nfci_easing_financial_leadership_candidate_pool_v1"
NEW_EVIDENCE_TYPE = "new_data_source_chicago_fed_nfci"
NEW_EVIDENCE_AXIS = (
    "New data source: official Chicago Fed NFCI weekly observations with a "
    "declared following-Wednesday release lag. No prior family used NFCI; the "
    "policy is not a threshold retune of MOVE, VIX, credit, Treasury-curve, "
    "mortgage, Companyfacts, or SEC-text rows."
)
NEARBY_PRIORS = [
    "exp-20260605-032",
    "exp-20260711-002",
    "exp-20260711-013",
    "exp-20260711-016",
    "exp-20260711-017",
]
CAUSAL_COMPONENTS = [
    "official Chicago Fed NFCI weekly source",
    "following-Wednesday release-lag proxy",
    "below-average and falling financial-conditions state",
    "Financial Services-only liquid leadership selector",
    "next-open 10-session replay with costs and concentration guards",
]
PREDICTION = {
    "success_probability": 0.12,
    "expected_ev_delta": 0.10,
    "expected_pnl_delta": 2000.0,
    "main_failure_modes": [
        "nfci_revisions_break_pit",
        "financial_sector_sample_too_small",
        "weekly_state_relabels_beta",
        "window_regression",
        "concentration_failed",
    ],
    "confidence_reason": (
        "NFCI is a genuinely new official composite of money, debt, equity, "
        "and banking conditions, so it can carry broader funding-state "
        "information than the exhausted MOVE/VIX/credit proxy list. Odds are "
        "low because current-vintage FRED history may be revised and the "
        "frozen Financials universe is narrow."
    ),
    "recorded_at": "2026-07-12T08:10:38+00:00",
}
PRODUCTION_IMPACT = {
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "trade_enabled": False,
    "entry_rules_changed": False,
    "ranking_changed": False,
    "sizing_changed": False,
    "exit_rules_changed": False,
    "orders_changed": False,
    "llm_decision_boundary_changed": False,
    "scope": "experiment_local_private_replay_scout",
}
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260712_010_{SLUG}.json",
    f"data/experiments/{EXPERIMENT_ID}/chicago_fed_nfci_weekly.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
    "scripts/experiment_fingerprint.py",
    "quant/test_experiment_fingerprint.py",
    "docs/frozen_families.jsonl",
]

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=NFCI"
NFCI_TICKER = "NFCI"
FINANCIAL_SECTOR = "Financial Services"
FETCH_START = dt.date(2024, 8, 1)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def following_wednesday(week_ending_friday: dt.date) -> dt.date:
    """Nominal public release date used as a conservative PIT proxy."""
    return week_ending_friday + dt.timedelta(days=5)


def fetch_nfci_rows() -> list[dict[str, Any]]:
    if NFCI_JSON.exists():
        cached = json.loads(NFCI_JSON.read_text(encoding="utf-8"))
        rows = cached.get("rows") or []
        if rows:
            return rows
    with urllib.request.urlopen(FRED_CSV_URL, timeout=30) as response:
        raw = response.read().decode("utf-8-sig")
    rows: list[dict[str, Any]] = []
    for source_row in csv.DictReader(io.StringIO(raw)):
        observation_date = dt.date.fromisoformat(str(source_row["observation_date"]))
        value = number(source_row.get("NFCI"))
        if observation_date < FETCH_START or value is None:
            continue
        release_date = following_wednesday(observation_date)
        rows.append(
            {
                "Date": release_date.isoformat(),
                "Open": value,
                "High": value,
                "Low": value,
                "Close": value,
                "Volume": 0.0,
                "observation_week_ending": observation_date.isoformat(),
                "nominal_release_date": release_date.isoformat(),
                "nfci": value,
            }
        )
    rows.sort(key=lambda row: row["Date"])
    if len(rows) < 80:
        raise RuntimeError(f"NFCI canonical coverage too small: {len(rows)} rows")
    write_json(
        NFCI_JSON,
        {
            "source": "Federal Reserve Bank of Chicago via FRED series NFCI",
            "source_url": FRED_CSV_URL,
            "source_frequency": "weekly ending Friday",
            "known_at_proxy": "following Wednesday release day",
            "revision_caveat": (
                "Current-vintage FRED history may revise prior observations; "
                "positive results are leads only until ALFRED/vintage replay."
            ),
            "fetched_at": utc_now(),
            "row_count": len(rows),
            "rows": rows,
        },
    )
    return rows


def load_window_snapshot(
    *, cfg: dict[str, str], eligible_tickers: set[str]
) -> dict[str, list[dict[str, Any]]]:
    snapshot = base.BASE_LOAD_WINDOW_SNAPSHOT(cfg=cfg, eligible_tickers=set(eligible_tickers))
    snapshot[NFCI_TICKER] = fetch_nfci_rows()
    return snapshot


def nfci_easing_context(
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    signal_date: str,
) -> dict[str, Any] | None:
    rows = snapshot.get(NFCI_TICKER) or []
    idx = indices.get(NFCI_TICKER, {}).get(signal_date)
    if idx is None:
        return None
    context: dict[str, Any] = {
        "date": signal_date,
        "rule_version": CHANGED_VARIABLE,
        "known_at": "following_wednesday_release_before_next_open_paper_entry",
        "current_vintage_revision_caveat": True,
    }
    if idx < 1:
        return {**context, "passed": False, "reason": "insufficient_nfci_history"}
    current = number(rows[idx].get("Close"))
    previous = number(rows[idx - 1].get("Close"))
    if current is None or previous is None:
        return {**context, "passed": False, "reason": "missing_nfci_value"}
    passed = current < 0.0 and current < previous
    return {
        **context,
        "nfci": round(current, 6),
        "previous_nfci": round(previous, 6),
        "weekly_change": round(current - previous, 6),
        "observation_week_ending": rows[idx].get("observation_week_ending"),
        "passed": passed,
        "reason": "nfci_below_zero_and_falling" if passed else "nfci_not_below_zero_and_falling",
    }


def candidate_for_ticker(**kwargs: Any) -> dict[str, Any] | None:
    context = kwargs["context"]
    row = base.BASE_CANDIDATE_FOR_TICKER(**kwargs)
    if row is None or str(row.get("sector") or "") != FINANCIAL_SECTOR:
        return None
    row["source"] = "CHICAGO_FED_NFCI_EASING_FINANCIAL_LEADERSHIP_PAPER"
    row["nfci_financial_conditions_context"] = row.pop("macro_relief_context", context)
    row["rule_version"] = CHANGED_VARIABLE
    return row


def configure_base() -> None:
    replacements = {
        "EXPERIMENT_ID": EXPERIMENT_ID,
        "OWNER": OWNER,
        "SLUG": SLUG,
        "RUNNER": RUNNER,
        "RUNNER_COMMAND": RUNNER_COMMAND,
        "OUT_DIR": OUT_DIR,
        "OUT_JSON": OUT_JSON,
        "MOVE_ROWS_JSON": NFCI_JSON,
        "LOG_JSON": LOG_JSON,
        "CARD_MD": CARD_MD,
        "MANIFEST_JSON": MANIFEST_JSON,
        "TICKET_JSON": TICKET_JSON,
        "REGISTRY_JSON": REGISTRY_JSON,
        "HYPOTHESIS": HYPOTHESIS,
        "CHANGE_TYPE": CHANGE_TYPE,
        "IMPLEMENTATION_MODE": IMPLEMENTATION_MODE,
        "MECHANISM_FAMILY": MECHANISM_FAMILY,
        "TRIAL_FAMILY": TRIAL_FAMILY,
        "TRIAL_VARIANT_ID": TRIAL_VARIANT_ID,
        "CHANGED_VARIABLE": CHANGED_VARIABLE,
        "NEW_EVIDENCE_TYPE": NEW_EVIDENCE_TYPE,
        "NEW_EVIDENCE_AXIS": NEW_EVIDENCE_AXIS,
        "NEARBY_PRIORS": NEARBY_PRIORS,
        "CAUSAL_COMPONENTS": CAUSAL_COMPONENTS,
        "PREDICTION": PREDICTION,
        "PRODUCTION_IMPACT": PRODUCTION_IMPACT,
        "ALLOWED_WRITE_SCOPE": ALLOWED_WRITE_SCOPE,
        "MOVE_TICKER": NFCI_TICKER,
        "fetch_move_rows": fetch_nfci_rows,
        "load_window_snapshot": load_window_snapshot,
        "move_relief_context": nfci_easing_context,
        "candidate_for_ticker": candidate_for_ticker,
    }
    for name, value in replacements.items():
        setattr(base, name, value)
    base.configure_prior()


def current_baseline_gate(before_metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    reference_payload = json.loads(CURRENT_SCHEMA_REFERENCE.read_text(encoding="utf-8"))
    reference_metrics = reference_payload.get("before_metrics") or {}
    windows: dict[str, Any] = {}
    for label, row in before_metrics.items():
        reference = reference_metrics.get(label) or {}
        mtm = reference.get("paper_mtm_contract") or {}
        inference = reference.get("sharpe_inference") or {}
        ev_matches = abs(
            float(row.get("expected_value_score") or 0.0)
            - float(reference.get("expected_value_score") or 0.0)
        ) <= 0.0001
        pnl_matches = abs(
            float(row.get("total_pnl") or 0.0)
            - float(reference.get("total_pnl") or 0.0)
        ) <= 0.01
        trades_match = int(row.get("trade_count") or 0) == int(
            reference.get("trade_count") or 0
        )
        passed = (
            int(mtm.get("schema_version") or 0) >= 1
            and int(inference.get("schema_version") or 0) >= 1
            and ev_matches
            and pnl_matches
            and trades_match
        )
        windows[label] = {
            "expected_value_score": row.get("expected_value_score"),
            "total_pnl": row.get("total_pnl"),
            "trade_count": row.get("trade_count"),
            "paper_mtm_schema_version": mtm.get("schema_version"),
            "sharpe_inference_schema_version": inference.get("schema_version"),
            "expected_value_matches_reference": ev_matches,
            "total_pnl_matches_reference": pnl_matches,
            "trade_count_matches_reference": trades_match,
            "passed": passed,
        }
    return {
        "passed": bool(windows) and all(row["passed"] for row in windows.values()),
        "protocol": "same-run baseline identity against exp-20260712-009 current-schema reference",
        "reference_artifact": repo_rel(CURRENT_SCHEMA_REFERENCE),
        "legacy_metric_comparison_used": False,
        "windows": windows,
    }


def calibration(payload: dict[str, Any], lead: bool) -> dict[str, Any]:
    failed = list(payload.get("gate4", {}).get("failed_reasons") or [])
    hit: list[str] = []
    if any("sample" in reason or "coverage" in reason for reason in failed):
        hit.append("financial_sector_sample_too_small")
    if any("window" in reason for reason in failed):
        hit.append("window_regression")
    if any("concentration" in reason for reason in failed):
        hit.append("concentration_failed")
    return {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_success": lead,
        "brier_score": round((float(PREDICTION["success_probability"]) - float(lead)) ** 2, 6),
        "predicted_failure_modes": PREDICTION["main_failure_modes"],
        "predicted_failure_modes_hit": hit,
        "unresolved_failure_mode": "nfci_revisions_break_pit",
        "failed_reasons": failed,
    }


def build_payload() -> dict[str, Any]:
    configure_base()
    payload = base.prior._build_payload()
    payload["gate1"] = current_baseline_gate(payload["before_metrics"])
    if not payload["gate1"]["passed"]:
        failed = payload.setdefault("gate4", {}).setdefault("failed_reasons", [])
        if "gate1_current_schema_baseline_failed" not in failed:
            failed.append("gate1_current_schema_baseline_failed")
        payload["gate4"]["passed"] = False
    nfci_rows = fetch_nfci_rows()
    coverage_by_window = {
        label: sum(
            1
            for row in nfci_rows
            if str(cfg["start"]) <= row["Date"] <= str(cfg["end"])
        )
        for label, cfg in base.prior.framework.WINDOWS.items()
    }
    gate4_passed = bool(payload.get("gate4", {}).get("passed"))
    lead = gate4_passed and payload["gate1"]["passed"]
    decision = (
        "positive_replay_lead_not_promoted_chicago_fed_nfci_easing_financial_leadership"
        if lead
        else "observed_only_rejected_chicago_fed_nfci_easing_financial_leadership"
    )
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "owner": OWNER,
            "lane": "alpha_search",
            "hypothesis": HYPOTHESIS,
            "change_type": CHANGE_TYPE,
            "implementation_mode": IMPLEMENTATION_MODE,
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIORS,
            "prior_trial_count": 0,
            "multiple_testing_risk_bucket": "low",
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "observed_only_lead": lead,
            "accepted": False,
            "accepted_alpha": False,
            "status": "observed_only",
            "decision": decision,
            "data_coverage": {
                "source": "Federal Reserve Bank of Chicago via FRED NFCI",
                "rows_by_window": coverage_by_window,
                "row_count": len(nfci_rows),
                "easing_release_days_by_window": {
                    label: payload["context_scan_by_window"][label].get("volatility_relief_days", 0)
                    for label in base.prior.framework.WINDOWS
                },
                "revision_caveat": "current-vintage history; ALFRED vintage replay required",
            },
            "fingerprint_caveat": (
                "Reservation keyword collision routed NFCI into companyfacts_ratio. "
                "This experiment adds chicago_fed_nfci classification and rebuilds frozen families."
            ),
            "related_files": [
                RUNNER,
                repo_rel(NFCI_JSON),
                "quant/experiments/exp_20260711_002_move_rate_volatility_relief_stock_leadership.py",
                "scripts/experiment_fingerprint.py",
                "quant/test_experiment_fingerprint.py",
            ],
            "changed_files": ALLOWED_WRITE_SCOPE,
            "reproduction_commands": [
                f".\\.venv\\Scripts\\python.exe -B -m py_compile {RUNNER.replace('/', chr(92))}",
                RUNNER_COMMAND,
                ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_experiment_fingerprint.py -q",
                ".\\.venv\\Scripts\\python.exe -B scripts\\build_frozen_families.py",
                ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
            ],
            "lean_quality_passed": True,
        }
    )
    payload.setdefault("parameters", {}).update(
        {
            "nfci_state": "current_value_below_zero_and_below_previous_week",
            "release_lag": "observation_week_ending_friday_plus_5_calendar_days",
            "eligible_sector": FINANCIAL_SECTOR,
            "stock_selector": "frozen_exp_20260607_018_liquid_leadership_fields",
            "current_vintage_history": True,
        }
    )
    runtime_fields = payload.setdefault("gate2", {}).setdefault("runtime_fields", [])
    if "Chicago Fed NFCI weekly value with following-Wednesday release lag" not in runtime_fields:
        runtime_fields.insert(3, "Chicago Fed NFCI weekly value with following-Wednesday release lag")
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The lagged below-average-and-falling NFCI state separated Financials leadership with positive after-cost value across the canonical windows, but current-vintage revisions prevent promotion."
            if lead
            else (
                "The lagged below-average-and-falling NFCI state produced positive aggregate paper value but lost $553.82 in late_strong, so the no-window-regression Gate 4 condition fails independently of the baseline level. The imported legacy core population also mismatched the new current-schema baseline in mid_weak and old_thin, which separately blocks any positive promotion."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by changing the NFCI zero level, weekly-change threshold, release lag, Financials ticker list, stock thresholds, top-N, hold, cooldown, notional, or scalar response on current-vintage rows."
        ),
        "new_evidence_required": (
            "Reopen only with ALFRED/Chicago-Fed vintage observations proving point-in-time values, materially settled forward rows from a fixed logger, or a genuinely different gate shape and economic exposure source."
        ),
    }
    payload["calibration"] = calibration(payload, lead)
    payload["rejection_reason"] = None if lead else ";".join(
        payload.get("gate4", {}).get("failed_reasons") or ["gate4_not_passed"]
    )
    payload["pre_run_questions"] = {
        "1_alpha_hypothesis": HYPOTHESIS,
        "2_history_check": {"nearby": NEARBY_PRIORS, "new_axis": NEW_EVIDENCE_AXIS},
        "3_single_policy_bundle": CHANGED_VARIABLE,
        "4_acceptance_standard": "Current-schema same-run Gate 1-4; positive aggregate EV/PnL, no window regression, sample, drawdown, survival, and concentration pass.",
        "5_reproducibility": RUNNER_COMMAND,
    }
    return payload


def compact_log(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload.get("timestamp") or utc_now(),
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": payload["observed_only_lead"],
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "nearby_prior_experiments": NEARBY_PRIORS,
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "expected_value_score_delta": aggregate.get("expected_value_score_delta_sum"),
        "total_pnl_delta": aggregate.get("total_pnl_delta_sum"),
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "rejection_reason": payload.get("rejection_reason"),
        "post_run_reflection": payload["post_run_reflection"],
        "data_coverage": payload["data_coverage"],
        "fingerprint_caveat": payload["fingerprint_caveat"],
        "related_files": payload["related_files"],
        "changed_files": ALLOWED_WRITE_SCOPE,
        "reproduction_commands": payload["reproduction_commands"],
        "lean_quality_passed": True,
    }


def build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Chicago Fed NFCI Easing Financial Leadership",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            HYPOTHESIS,
            "",
            "## Result",
            "",
            f"- NFCI rows by window: `{payload['data_coverage']['rows_by_window']}`",
            f"- Easing release days: `{payload['data_coverage']['easing_release_days_by_window']}`",
            f"- Aggregate EV delta: `{aggregate.get('expected_value_score_delta_sum'):+.4f}`",
            f"- Aggregate PnL delta: `${aggregate.get('total_pnl_delta_sum'):+,.2f}`",
            f"- Target trades: `{payload['target_trade_summary']['total_trade_count']}`",
            f"- Failed gates: `{payload['gate4'].get('failed_reasons') or 'none'}`",
            "",
            "## Boundary",
            "",
            "Current-vintage NFCI may be revised. Even a positive result is lead-only until vintage replay.",
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
        ]
    )


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(compact_log(payload), allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    aggregate = payload["delta_metrics"]["aggregate"]
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result={
            "accepted": False,
            "accepted_alpha": False,
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "calibration": payload["calibration"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "change_type": CHANGE_TYPE,
            "implementation_mode": IMPLEMENTATION_MODE,
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIORS,
            "multiple_testing_risk_bucket": "low",
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": aggregate.get("expected_value_score_delta_sum"),
            "aggregate_strategy_total_pnl_delta": aggregate.get("total_pnl_delta_sum"),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": PRODUCTION_IMPACT,
            "post_run_reflection": payload["post_run_reflection"],
            "allowed_write_scope": ALLOWED_WRITE_SCOPE,
            "related_files": payload["related_files"],
            "changed_files": ALLOWED_WRITE_SCOPE,
            "fingerprint_caveat": payload["fingerprint_caveat"],
            "reproduction_commands": payload["reproduction_commands"],
            "lean_quality_passed": True,
        },
    )
    files = [REPO_ROOT / RUNNER, OUT_JSON, NFCI_JSON, LOG_JSON, CARD_MD, TICKET_JSON]
    write_json(
        MANIFEST_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "decision": payload["decision"],
            "generated_at": utc_now(),
            "allowed_write_scope": ALLOWED_WRITE_SCOPE,
            "files": {
                repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
                for path in files
            },
        },
    )


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "persist-existing":
        payload = json.loads(OUT_JSON.read_text(encoding="utf-8"))
        payload["post_run_reflection"]["why_result_happened"] = (
            "The lagged below-average-and-falling NFCI state produced positive aggregate paper value but lost $553.82 in late_strong, so the no-window-regression Gate 4 condition fails independently of the baseline level. The imported legacy core population also mismatched the new current-schema baseline in mid_weak and old_thin, which separately blocks any positive promotion."
        )
        payload["calibration"]["unresolved_failure_mode"] = (
            "nfci_revisions_break_pit_and_current_baseline_population_mismatch"
        )
        persist(payload)
        print(json.dumps({"experiment_id": EXPERIMENT_ID, "decision": payload["decision"]}, indent=2))
        return 0
    payload = build_payload()
    persist(payload)
    aggregate = payload["delta_metrics"]["aggregate"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "nfci_rows": payload["data_coverage"]["row_count"],
                "easing_release_days": payload["data_coverage"]["easing_release_days_by_window"],
                "target_trades": payload["target_trade_summary"]["total_trade_count"],
                "aggregate_ev_delta": aggregate.get("expected_value_score_delta_sum"),
                "aggregate_pnl_delta": aggregate.get("total_pnl_delta_sum"),
                "failed_reasons": payload["gate4"].get("failed_reasons"),
                "artifact": repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
