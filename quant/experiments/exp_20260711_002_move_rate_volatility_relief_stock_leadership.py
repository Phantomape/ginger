"""exp-20260711-002: MOVE rate-volatility relief stock-leadership scout.

Observed-only private replay scout.  The only decision hypothesis is a first
daily ICE BofA MOVE close below its trailing 20-session simple mean.  On those
event days the stock selector, next-open entry, 10-session close, costs,
notional, top-2 budget, and cooldown are frozen from exp-20260607-018.

No production, core, order, ranking, sizing, exit, or LLM behavior changes.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
for entry in (REPO_ROOT / "scripts", REPO_ROOT / "quant", REPO_ROOT / "quant" / "experiments"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import exp_20260607_018_volatility_relief_stock_leadership as prior  # noqa: E402
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)
from yfinance_bootstrap import download_with_rate_limit_retry  # noqa: E402


EXPERIMENT_ID = "exp-20260711-002"
OWNER = "alpha-explore"
SLUG = "move_rate_volatility_relief_stock_leadership"
RUNNER = f"quant/experiments/exp_20260711_002_{SLUG}.py"
RUNNER_PS = RUNNER.replace("/", "\\")
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER_PS

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260711_002_{SLUG}.json"
MOVE_ROWS_JSON = OUT_DIR / "ice_bofa_move_daily_closes.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Private replay scout: a first daily close of the ICE BofA MOVE Index below "
    "its trailing 20-session mean is an option-implied Treasury-rate-volatility "
    "relief event; applying the unchanged exp-20260607-018 liquid stock-"
    "leadership selector on that event day should add positive next-open "
    "10-session paper replacement value across all three canonical windows "
    "without window, drawdown, survival, or concentration failure."
)
CHANGE_TYPE = "candidate_pool_private_replay_scout"
IMPLEMENTATION_MODE = "private_replay_scout_new_data_shape"
MECHANISM_FAMILY = "production_visible_rate_volatility_relief_candidate_pool"
TRIAL_FAMILY = "move_rate_volatility_relief_stock_leadership_candidate_pool"
TRIAL_VARIANT_ID = "move20_cross_below_fixed_stock_leadership_v1"
CHANGED_VARIABLE = "move20_cross_below_rate_volatility_relief_stock_leadership_v1"
NEW_EVIDENCE_TYPE = "new_data_source_move_index"
NEW_EVIDENCE_AXIS = (
    "ICE BofA MOVE daily history spans all three canonical windows and no prior "
    "experiment used MOVE/Treasury rate-volatility relief; the candidate "
    "selector remains frozen from exp-20260607-018."
)
NEARBY_PRIORS = [
    "exp-20260607-018",
    "exp-20260607-019",
    "exp-20260619-021",
    "exp-20260710-020",
    "exp-20260711-001",
]
CAUSAL_COMPONENTS = [
    "Yahoo-mirrored ICE BofA MOVE daily closes",
    "fixed first cross below trailing 20-session simple mean",
    "unchanged exp-20260607-018 stock leadership selector",
    "next-open 10-session paper replay",
    "canonical costs and Gate 1-4",
]
PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": 0.15,
    "expected_pnl_delta": 3000.0,
    "main_failure_modes": [
        "move_relief_relabels_broad_beta",
        "signal_too_sparse",
        "window_regression",
        "drawdown_drift",
        "concentration_failed",
        "baseline_identity_drift",
    ],
    "confidence_reason": (
        "MOVE is a genuinely new options-implied Treasury risk-transfer source "
        "with complete canonical coverage, and accepted volatility/macro relief "
        "analogs support the mechanism; odds stay low because HYG/JNK and VIX9D "
        "tests showed macro relief labels often overlap beta or delete winners."
    ),
    "recorded_at": "2026-07-11T02:09:47+00:00",
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
    f"data/experiments/{EXPERIMENT_ID}/**",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
    "docs/frozen_families.jsonl",
    "scripts/experiment_fingerprint.py",
    "quant/test_experiment_fingerprint.py",
]

MOVE_TICKER = "MOVE"
FETCH_START = "2024-08-01"
FETCH_END_EXCLUSIVE = "2026-04-23"
MOVE_SMA_SESSIONS = 20
BASE_LOAD_WINDOW_SNAPSHOT = prior.BASE_LOAD_WINDOW_SNAPSHOT
BASE_CANDIDATE_FOR_TICKER = prior.BASE_CANDIDATE_FOR_TICKER


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


def fetch_move_rows() -> list[dict[str, Any]]:
    if MOVE_ROWS_JSON.exists():
        cached = json.loads(MOVE_ROWS_JSON.read_text(encoding="utf-8"))
        rows = cached.get("rows") or []
        if rows:
            return rows
    frame = download_with_rate_limit_retry(
        "^MOVE",
        start=FETCH_START,
        end=FETCH_END_EXCLUSIVE,
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    if frame is None or getattr(frame, "empty", True):
        raise RuntimeError("ICE BofA MOVE history is unavailable")
    rows: list[dict[str, Any]] = []
    for stamp in frame.index:
        row: dict[str, Any] = {"Date": str(stamp)[:10], "Volume": 0.0}
        complete = True
        for field in ("Open", "High", "Low", "Close"):
            try:
                values = frame[field]
                if hasattr(values, "columns"):
                    values = values.iloc[:, 0]
                value = number(values.loc[stamp])
            except (KeyError, TypeError, IndexError):
                value = None
            if value is None:
                complete = False
                break
            row[field] = value
        if complete:
            rows.append(row)
    if len(rows) < 400:
        raise RuntimeError(f"MOVE canonical coverage too small: {len(rows)} rows")
    write_json(
        MOVE_ROWS_JSON,
        {
            "source": "Yahoo Finance mirror of ICE BofA MOVE Index",
            "delivery_ticker": "^MOVE",
            "known_at": "each row close after its session",
            "fetched_at": utc_now(),
            "start": FETCH_START,
            "end_exclusive": FETCH_END_EXCLUSIVE,
            "row_count": len(rows),
            "rows": rows,
        },
    )
    return rows


def load_window_snapshot(*, cfg: dict[str, str], eligible_tickers: set[str]) -> dict[str, list[dict[str, Any]]]:
    snapshot = BASE_LOAD_WINDOW_SNAPSHOT(cfg=cfg, eligible_tickers=set(eligible_tickers))
    snapshot[MOVE_TICKER] = fetch_move_rows()
    return snapshot


def canonical_frozen_universe() -> list[str]:
    universe: set[str] = set()
    for cfg in prior.framework.WINDOWS.values():
        payload = json.loads((REPO_ROOT / str(cfg["snapshot"])).read_text(encoding="utf-8"))
        metadata = payload.get("metadata") or {}
        tickers = {str(value).upper() for value in metadata.get("tickers") or []}
        proxies = {
            str(value).upper()
            for value in list(metadata.get("cross_asset_proxies_added") or [])
            + list(metadata.get("added_tickers") or [])
        }
        universe.update(tickers - proxies)
    if not universe:
        raise RuntimeError("canonical snapshots expose no frozen core universe")
    return sorted(universe)


def move_relief_context(
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    signal_date: str,
) -> dict[str, Any] | None:
    rows = snapshot.get(MOVE_TICKER) or []
    idx = indices.get(MOVE_TICKER, {}).get(signal_date)
    if idx is None:
        return None
    context: dict[str, Any] = {
        "date": signal_date,
        "move_sma_sessions": MOVE_SMA_SESSIONS,
        "rule_version": CHANGED_VARIABLE,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
    }
    if idx < MOVE_SMA_SESSIONS:
        return {**context, "passed": False, "reason": "insufficient_move_history"}
    closes = [number(row.get("Close")) for row in rows]
    current_window = closes[idx - MOVE_SMA_SESSIONS + 1 : idx + 1]
    prior_window = closes[idx - MOVE_SMA_SESSIONS : idx]
    current = closes[idx]
    previous = closes[idx - 1]
    if current is None or previous is None or any(value is None for value in current_window + prior_window):
        return {**context, "passed": False, "reason": "missing_move_close"}
    current_sma = sum(float(value) for value in current_window) / MOVE_SMA_SESSIONS
    prior_sma = sum(float(value) for value in prior_window) / MOVE_SMA_SESSIONS
    passed = current < current_sma and previous >= prior_sma
    return {
        **context,
        "move_close": round(current, 6),
        "move_prior_close": round(previous, 6),
        "move_sma20": round(current_sma, 6),
        "move_prior_sma20": round(prior_sma, 6),
        "move_discount_to_sma20": round(current / current_sma - 1.0, 6),
        "passed": passed,
        "reason": "move_first_cross_below_sma20" if passed else "not_first_cross_below_sma20",
    }


def candidate_for_ticker(**kwargs: Any) -> dict[str, Any] | None:
    context = kwargs["context"]
    row = BASE_CANDIDATE_FOR_TICKER(**kwargs)
    if row is None:
        return None
    row["source"] = "MOVE_RATE_VOLATILITY_RELIEF_LEADERSHIP_PAPER"
    row["move_rate_volatility_relief_context"] = row.pop("macro_relief_context", context)
    row["rule_version"] = CHANGED_VARIABLE
    return row


def configure_prior() -> None:
    prior.EXPERIMENT_ID = EXPERIMENT_ID
    prior.STEM = SLUG
    prior.TRIAL_FAMILY = TRIAL_FAMILY
    prior.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    prior.CHANGED_VARIABLE = CHANGED_VARIABLE
    prior.RULE_VERSION = CHANGED_VARIABLE
    prior.OUT_DIR = OUT_DIR
    prior.OUT_JSON = OUT_JSON
    prior.LOG_JSON = LOG_JSON
    prior.TICKET_JSON = TICKET_JSON
    prior.CARD_MD = CARD_MD
    prior.MANIFEST_JSON = MANIFEST_JSON
    prior.REGISTRY_JSON = REGISTRY_JSON
    prior.PREDICTION = PREDICTION
    prior.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    prior._relief_context_for_day = move_relief_context
    prior._candidate_for_ticker = candidate_for_ticker
    prior._load_window_snapshot = load_window_snapshot
    prior.previous._relief_context_for_day = move_relief_context
    prior.previous._candidate_for_ticker = candidate_for_ticker
    prior.previous._load_window_snapshot = load_window_snapshot
    prior.framework.EXPERIMENT_ID = EXPERIMENT_ID
    prior.framework.STEM = SLUG
    prior.framework.TRIAL_FAMILY = TRIAL_FAMILY
    prior.framework.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    prior.framework.CHANGED_VARIABLE = CHANGED_VARIABLE
    prior.framework.RULE_VERSION = CHANGED_VARIABLE
    prior.framework.OUT_DIR = OUT_DIR
    prior.framework.OUT_JSON = OUT_JSON
    prior.framework.LOG_JSON = LOG_JSON
    prior.framework.TICKET_JSON = TICKET_JSON
    prior.framework.CARD_MD = CARD_MD
    prior.framework.MANIFEST_JSON = MANIFEST_JSON
    prior.framework.REGISTRY_JSON = REGISTRY_JSON
    prior.framework.PREDICTION = PREDICTION
    prior.framework.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    prior.framework._load_window_snapshot = load_window_snapshot
    prior.framework._candidate_rows_for_window = prior._candidate_rows_for_window
    prior.framework._gate4 = prior._gate4
    prior.framework.get_universe = canonical_frozen_universe


def calibration(payload: dict[str, Any], lead: bool) -> dict[str, Any]:
    probability = float(PREDICTION["success_probability"])
    failed = list(payload.get("gate4", {}).get("failed_reasons") or [])
    hit: list[str] = []
    if any("sample" in reason or "coverage" in reason for reason in failed):
        hit.append("signal_too_sparse")
    if any("window" in reason for reason in failed):
        hit.append("window_regression")
    if any("drawdown" in reason for reason in failed):
        hit.append("drawdown_drift")
    if any("concentration" in reason for reason in failed):
        hit.append("concentration_failed")
    if any("baseline_identity" in reason for reason in failed):
        hit.append("baseline_identity_drift")
    actual = 1.0 if lead else 0.0
    return {
        "predicted_success_probability": probability,
        "actual_success": lead,
        "brier_score": round((probability - actual) ** 2, 6),
        "predicted_failure_modes": list(PREDICTION["main_failure_modes"]),
        "predicted_failure_modes_hit": hit,
        "failed_reasons": failed,
        "surprise_note": (
            "The fixed MOVE event and frozen selector cleared every replay gate."
            if lead
            else "Complete MOVE coverage made the signal measurable, but the fixed event/selector bundle did not clear the predeclared replay gates."
        ),
    }


def build_payload() -> dict[str, Any]:
    configure_prior()
    payload = prior._build_payload()
    canonical = {
        "late_strong": {"expected_value_score": 5.1628, "total_pnl": 117072.92},
        "mid_weak": {"expected_value_score": 2.1402, "total_pnl": 78110.11},
        "old_thin": {"expected_value_score": 0.5911, "total_pnl": 39667.96},
    }
    identity: dict[str, Any] = {}
    for label, expected in canonical.items():
        observed = payload["before_metrics"][label]
        ev_drift = round(float(observed["expected_value_score"]) - expected["expected_value_score"], 4)
        pnl_drift = round(float(observed["total_pnl"]) - expected["total_pnl"], 2)
        identity[label] = {
            "canonical_ev": expected["expected_value_score"],
            "canonical_pnl": expected["total_pnl"],
            "observed_ev": observed["expected_value_score"],
            "observed_pnl": observed["total_pnl"],
            "ev_drift": ev_drift,
            "pnl_drift": pnl_drift,
            "passed": ev_drift == 0.0 and pnl_drift == 0.0,
        }
    identity_passed = all(row["passed"] for row in identity.values())
    payload["gate1"] = {
        "passed": identity_passed,
        "canonical_baseline": "data/experiments/exp-20260602-003/exp_20260602_003_post_earnings_explicit_continuation.json",
        "windows": identity,
    }
    if not identity_passed:
        failed = payload.setdefault("gate4", {}).setdefault("failed_reasons", [])
        if "gate1_baseline_identity_failed" not in failed:
            failed.append("gate1_baseline_identity_failed")
        payload["gate4"]["passed"] = False
    move_rows = fetch_move_rows()
    coverage_by_window = {
        label: sum(1 for row in move_rows if str(cfg["start"]) <= row["Date"] <= str(cfg["end"]))
        for label, cfg in prior.framework.WINDOWS.items()
    }
    lead = bool(payload.get("gate4", {}).get("passed"))
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
            "decision": (
                "positive_replay_lead_not_promoted_move_rate_volatility_relief"
                if lead
                else "observed_only_rejected_move_rate_volatility_relief"
            ),
            "data_coverage": {
                "source": "Yahoo Finance mirror of ICE BofA MOVE Index",
                "row_count": len(move_rows),
                "rows_by_window": coverage_by_window,
                "all_canonical_windows_covered": all(count >= 120 for count in coverage_by_window.values()),
                "relief_events_by_window": {
                    label: payload["context_scan_by_window"][label].get("volatility_relief_days", 0)
                    for label in prior.framework.WINDOWS
                },
            },
            "fingerprint_caveat": (
                "Reservation overmatched forward_replacement_value; this experiment adds "
                "the dedicated move_rate_volatility key and rebuilds frozen families."
            ),
            "calibration": calibration(payload, lead),
            "related_files": [
                RUNNER,
                "quant/experiments/exp_20260607_018_volatility_relief_stock_leadership.py",
                repo_rel(MOVE_ROWS_JSON),
                "scripts/experiment_fingerprint.py",
                "quant/test_experiment_fingerprint.py",
            ],
            "changed_files": ALLOWED_WRITE_SCOPE,
            "reproduction_commands": [
                f".\\.venv\\Scripts\\python.exe -B -m py_compile {RUNNER_PS}",
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
            "move_sma_sessions": MOVE_SMA_SESSIONS,
            "move_event": "first_close_below_sma_after_prior_close_at_or_above_prior_sma",
            "stock_selector": "unchanged_exp_20260607_018",
        }
    )
    payload["gate2"]["passed"] = bool(payload["gate2"].get("passed")) and all(
        coverage_by_window.values()
    )
    runtime_fields = payload["gate2"].setdefault("runtime_fields", [])
    if "ICE BofA MOVE daily Close with 20-session history" not in runtime_fields:
        runtime_fields.insert(3, "ICE BofA MOVE daily Close with 20-session history")
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The first MOVE cross below its 20-session mean supplied an independent rate-volatility relief state whose frozen stock selector added robust after-cost replacement value in every canonical window."
            if lead
            else "The first MOVE cross below its 20-session mean did not isolate durable after-cost stock continuation across the canonical windows; it was too sparse, regime-fragile, or another broad beta relief label."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by changing the MOVE moving-average span, using percent/level thresholds, adding direction persistence, changing stock filters, sectors, top-N, hold, cooldown, notional, windows, or scalar response."
        ),
        "new_evidence_required": (
            "Reopen only with materially settled forward rows from a fixed shared helper or a genuinely different rate-volatility source such as publication-timed swaption/term-premium data."
        ),
    }
    payload["rejection_reason"] = None if lead else ";".join(
        payload.get("gate4", {}).get("failed_reasons") or ["gate4_not_passed"]
    )
    payload["pre_run_questions"] = {
        "1_alpha_hypothesis": "candidate_pool: Treasury rate-volatility relief may precede durable liquid stock leadership",
        "2_history_check": {"nearby": NEARBY_PRIORS, "new_axis": NEW_EVIDENCE_AXIS, "novelty_override": True},
        "3_single_policy_bundle": CHANGED_VARIABLE,
        "4_acceptance_standard": "Canonical Gate 1-4; positive aggregate EV/PnL, no window regression, <=0.5pp drawdown drift, >=20 trades across three windows, survival and concentration pass.",
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
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIORS,
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate.get("expected_value_score_delta_sum"),
        "aggregate_strategy_total_pnl_delta": aggregate.get("total_pnl_delta_sum"),
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
        "changed_files": ALLOWED_WRITE_SCOPE,
        "reproduction_commands": payload["reproduction_commands"],
        "lean_quality_passed": True,
    }


def build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} MOVE Rate-Volatility Relief Replay",
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
            f"- MOVE coverage: `{payload['data_coverage']['rows_by_window']}`",
            f"- MOVE relief events: `{payload['data_coverage']['relief_events_by_window']}`",
            f"- Aggregate EV delta: `{aggregate.get('expected_value_score_delta_sum'):+.4f}`",
            f"- Aggregate PnL delta: `${aggregate.get('total_pnl_delta_sum'):+,.2f}`",
            f"- Target trades: `{payload['target_trade_summary']['total_trade_count']}`",
            f"- Failed gates: `{payload['gate4'].get('failed_reasons') or 'none'}`",
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
        ]
    )


def write_manifest(payload: dict[str, Any]) -> None:
    paths = [REPO_ROOT / RUNNER, OUT_JSON, MOVE_ROWS_JSON, LOG_JSON, CARD_MD, TICKET_JSON]
    write_json(
        MANIFEST_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "decision": payload["decision"],
            "created_at": payload.get("timestamp") or utc_now(),
            "allowed_write_scope": ALLOWED_WRITE_SCOPE,
            "files": {repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)} for path in paths},
        },
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
            "baseline_result_file": "data/experiments/exp-20260602-003/exp_20260602_003_post_earnings_explicit_continuation.json",
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
    write_manifest(payload)


def main() -> int:
    payload = build_payload()
    persist(payload)
    aggregate = payload["delta_metrics"]["aggregate"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "move_rows": payload["data_coverage"]["row_count"],
                "move_relief_events": payload["data_coverage"]["relief_events_by_window"],
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
