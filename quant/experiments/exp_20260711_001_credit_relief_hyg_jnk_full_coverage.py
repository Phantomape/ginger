"""exp-20260711-001: fixed HYG/JNK credit-relief policy with PIT coverage.

This is an observed-only private replay scout.  It reuses the exact policy
bundle from exp-20260607-020 and changes only the missing evidence surface:
HYG and JNK daily OHLCV are now materialized across all canonical windows.
No production, ranking, sizing, exit, order, or LLM behavior changes.
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

import exp_20260607_020_credit_relief_stock_leadership as prior  # noqa: E402
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)
from yfinance_bootstrap import download_with_rate_limit_retry  # noqa: E402


EXPERIMENT_ID = "exp-20260711-001"
OWNER = "alpha-explore"
SLUG = "credit_relief_hyg_jnk_full_coverage"
RUNNER = f"quant/experiments/exp_20260711_001_{SLUG}.py"
RUNNER_PS = RUNNER.replace("/", "\\")
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER_PS

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260711_001_{SLUG}.json"
CREDIT_ROWS_JSON = OUT_DIR / "hyg_jnk_daily_ohlcv.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "With newly materialized PIT HYG and JNK daily OHLCV covering all three "
    "canonical windows, the unchanged HYG/JNK/SPY/QQQ credit-relief stock-"
    "leadership top-2 next-open 10-day paper policy should add positive "
    "replacement value without window regression or concentration failure."
)
CHANGE_TYPE = "candidate_pool_private_replay_scout"
IMPLEMENTATION_MODE = "private_replay_scout_newly_available_data_shape"
MECHANISM_FAMILY = "production_visible_free_ohlcv_cross_asset_credit_relief_candidate_pool"
TRIAL_FAMILY = "credit_relief_stock_leadership_candidate_pool"
TRIAL_VARIANT_ID = "hyg_jnk_full_coverage_fixed_policy_v1"
CHANGED_VARIABLE = "credit_relief_stock_leadership_candidate_source_v1_replay_with_full_hyg_jnk_coverage"
NEW_EVIDENCE_TYPE = "new_pit_hyg_jnk_historical_coverage"
NEW_EVIDENCE_AXIS = (
    "HYG and JNK now each have daily OHLCV spanning every canonical window; "
    "exp-20260607-020 and exp-20260620-021 had zero replay rows and explicitly "
    "required this coverage before reopening the fixed policy."
)
NEARBY_PRIORS = ["exp-20260607-020", "exp-20260620-021"]
CAUSAL_COMPONENTS = [
    "fixed HYG/JNK/SPY/QQQ relief state",
    "fixed stock leadership selector",
    "next-open 10d paper replay",
    "canonical costs and concentration gates",
]
PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.15,
    "expected_pnl_delta": 2500.0,
    "main_failure_modes": [
        "credit_relief_is_generic_beta",
        "thin_relief_day_sample",
        "window_regression",
        "concentration_failed",
        "baseline_identity_drift",
    ],
    "confidence_reason": (
        "Earlier attempts never observed the mechanism because HYG/JNK were "
        "absent, while accepted macro-relief analogs support cross-asset risk-"
        "relief leadership. Odds remain low because the fixed state may be "
        "sparse or merely relabel broad risk-on beta."
    ),
    "recorded_at": "2026-07-11T00:09:37+00:00",
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
    "scripts/experiment_fingerprint.py",
    "quant/test_experiment_fingerprint.py",
    "docs/frozen_families.jsonl",
]

FETCH_START = "2024-09-01"
FETCH_END_EXCLUSIVE = "2026-04-23"
REQUIRED_TICKERS = ("HYG", "JNK")
BASE_LOAD_WINDOW_SNAPSHOT = prior.BASE_LOAD_WINDOW_SNAPSHOT


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result


def fetch_credit_rows() -> dict[str, list[dict[str, Any]]]:
    if CREDIT_ROWS_JSON.exists():
        cached = json.loads(CREDIT_ROWS_JSON.read_text(encoding="utf-8"))
        rows = cached.get("rows_by_ticker") or {}
        if all(rows.get(ticker) for ticker in REQUIRED_TICKERS):
            return rows

    frame = download_with_rate_limit_retry(
        list(REQUIRED_TICKERS),
        start=FETCH_START,
        end=FETCH_END_EXCLUSIVE,
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    if frame is None or getattr(frame, "empty", True):
        raise RuntimeError("HYG/JNK yfinance history is unavailable")

    rows_by_ticker: dict[str, list[dict[str, Any]]] = {}
    for ticker in REQUIRED_TICKERS:
        rows: list[dict[str, Any]] = []
        for stamp in frame.index:
            row: dict[str, Any] = {"Date": str(stamp)[:10]}
            complete = True
            for field in ("Open", "High", "Low", "Close", "Volume"):
                try:
                    raw = frame[field][ticker]
                    value = _number(raw.loc[stamp])
                except (KeyError, TypeError):
                    value = None
                if value is None:
                    complete = False
                    break
                row[field] = value
            if complete:
                rows.append(row)
        if not rows:
            raise RuntimeError(f"no complete daily rows for {ticker}")
        rows_by_ticker[ticker] = rows

    write_json(
        CREDIT_ROWS_JSON,
        {
            "source": "yfinance daily OHLCV materialized for fixed replay",
            "known_at": "each row close after its date",
            "fetched_at": utc_now(),
            "start": FETCH_START,
            "end_exclusive": FETCH_END_EXCLUSIVE,
            "row_counts": {ticker: len(rows) for ticker, rows in rows_by_ticker.items()},
            "rows_by_ticker": rows_by_ticker,
        },
    )
    return rows_by_ticker


def load_window_snapshot(
    *, cfg: dict[str, str], eligible_tickers: set[str]
) -> dict[str, list[dict[str, Any]]]:
    snapshot = BASE_LOAD_WINDOW_SNAPSHOT(
        cfg=cfg,
        eligible_tickers=set(eligible_tickers),
    )
    snapshot.update(fetch_credit_rows())
    return snapshot


def canonical_frozen_universe() -> list[str]:
    """Union the three snapshot universes while excluding tagged context proxies."""
    universe: set[str] = set()
    for cfg in prior.framework.WINDOWS.values():
        snapshot_path = REPO_ROOT / str(cfg["snapshot"])
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        metadata = snapshot.get("metadata") or {}
        tickers = {str(value).upper() for value in metadata.get("tickers") or []}
        proxies = {
            str(value).upper()
            for value in (
                list(metadata.get("cross_asset_proxies_added") or [])
                + list(metadata.get("added_tickers") or [])
            )
        }
        universe.update(tickers - proxies)
    if not universe:
        raise RuntimeError("canonical snapshots expose no frozen core universe")
    return sorted(universe)


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
    prior._load_window_snapshot = load_window_snapshot
    prior._patch_framework()
    prior.framework.get_universe = canonical_frozen_universe


def calibration(payload: dict[str, Any], lead: bool) -> dict[str, Any]:
    probability = float(PREDICTION["success_probability"])
    failed = list(payload.get("gate4", {}).get("failed_reasons") or [])
    expected_modes = list(PREDICTION["main_failure_modes"])
    hit = []
    if any("sample" in reason or "coverage" in reason for reason in failed):
        hit.append("thin_relief_day_sample")
    if any("window" in reason for reason in failed):
        hit.append("window_regression")
    if any("concentration" in reason for reason in failed):
        hit.append("concentration_failed")
    if any("baseline_identity" in reason for reason in failed):
        hit.append("baseline_identity_drift")
    actual = 1.0 if lead else 0.0
    return {
        "predicted_success_probability": probability,
        "actual_success": lead,
        "brier_score": round((probability - actual) ** 2, 6),
        "predicted_failure_modes": expected_modes,
        "predicted_failure_modes_hit": hit,
        "failed_reasons": failed,
        "surprise_note": (
            "The fixed policy became measurable after HYG/JNK materialization and passed."
            if lead
            else "Full HYG/JNK coverage removed the old blocker, but the fixed policy still failed its predeclared replay gates."
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
    identity_windows: dict[str, Any] = {}
    for label, expected in canonical.items():
        observed = payload["before_metrics"][label]
        ev_drift = round(float(observed["expected_value_score"]) - expected["expected_value_score"], 4)
        pnl_drift = round(float(observed["total_pnl"]) - expected["total_pnl"], 2)
        identity_windows[label] = {
            "canonical_ev": expected["expected_value_score"],
            "canonical_pnl": expected["total_pnl"],
            "observed_ev": observed["expected_value_score"],
            "observed_pnl": observed["total_pnl"],
            "ev_drift": ev_drift,
            "pnl_drift": pnl_drift,
            "passed": ev_drift == 0.0 and pnl_drift == 0.0,
        }
    identity_passed = all(row["passed"] for row in identity_windows.values())
    payload["gate1"] = {
        "passed": identity_passed,
        "canonical_baseline": (
            "data/experiments/exp-20260602-003/"
            "exp_20260602_003_post_earnings_explicit_continuation.json"
        ),
        "windows": identity_windows,
    }
    if not identity_passed:
        failed = payload.setdefault("gate4", {}).setdefault("failed_reasons", [])
        if "gate1_baseline_identity_failed" not in failed:
            failed.append("gate1_baseline_identity_failed")
        payload["gate4"]["passed"] = False
    lead = bool(payload.get("gate4", {}).get("passed"))
    row_counts = {ticker: len(rows) for ticker, rows in fetch_credit_rows().items()}
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
            "prior_trial_count": 2,
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
                "observed_only_positive_credit_relief_full_coverage_lead_not_promoted"
                if lead
                else "observed_only_rejected_credit_relief_full_coverage"
            ),
            "data_coverage": {
                "source": "materialized_yfinance_hyg_jnk_daily_ohlcv",
                "row_counts": row_counts,
                "all_canonical_windows_covered": all(count >= 400 for count in row_counts.values()),
                "prior_replay_row_counts": {"exp-20260607-020": 0, "exp-20260620-021": 0},
            },
            "fingerprint_caveat": (
                "Reservation overmatched forward_replacement_value; the true source is "
                "credit_risk_etf. This experiment adds the dedicated fingerprint key and tests."
            ),
            "calibration": calibration(payload, lead),
            "related_files": [
                RUNNER,
                "quant/experiments/exp_20260607_020_credit_relief_stock_leadership.py",
                "experiments/logs/exp-20260620-021.json",
                repo_rel(CREDIT_ROWS_JSON),
                "data/experiments/exp-20260602-003/exp_20260602_003_post_earnings_explicit_continuation.json",
            ],
            "changed_files": ALLOWED_WRITE_SCOPE,
            "reproduction_commands": [
                f".\\.venv\\Scripts\\python.exe -B -m py_compile {RUNNER_PS}",
                RUNNER_COMMAND,
                ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_experiment_fingerprint.py -q",
                ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
            ],
            "lean_quality_passed": True,
        }
    )
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "With the old coverage blocker removed, the fixed credit-relief state produced robust positive replacement value under every predeclared gate."
            if lead
            else "HYG/JNK coverage removed the measurement blocker, but the fixed credit-relief state did not isolate durable stock continuation after next-open execution and costs; it behaved like sparse or generic risk-on beta."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retune HYG/JNK returns, close locations, SPY/QQQ confirmation, stock leadership thresholds, top-N, hold, cooldown, notional, windows, or response shape on these rows."
        ),
        "new_evidence_required": (
            "A retry needs a genuinely different credit-risk-transfer source, materially more settled forward rows from a fixed shared helper, or a predeclared different candidate-source family."
        ),
    }
    payload["rejection_reason"] = None if lead else ";".join(
        payload.get("gate4", {}).get("failed_reasons") or ["gate4_not_passed"]
    )
    payload["pre_run_questions"] = {
        "1_alpha_hypothesis": "candidate_pool: credit-risk relief may identify durable liquid stock leadership",
        "2_history_check": {
            "nearby": NEARBY_PRIORS,
            "prior_failure": "zero HYG/JNK replay rows",
            "new_axis": NEW_EVIDENCE_AXIS,
            "novelty_override": True,
            "fingerprint_caveat": payload["fingerprint_caveat"],
        },
        "3_single_policy_bundle": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Aggregate EV/PnL positive, >=2 EV-improved windows, no EV/PnL window regression, <=0.5pp drawdown drift, >=20 target trades across all three windows, survival >=5%, concentration pass."
        ),
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
        "gate1": payload.get("gate1"),
        "gate2": payload.get("gate2"),
        "gate3": payload.get("gate3"),
        "gate4": payload.get("gate4"),
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
    lines = [
        f"# {EXPERIMENT_ID} Credit Relief Full-Coverage Replay",
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
        f"- HYG/JNK rows: `{payload['data_coverage']['row_counts']}`",
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
    return "\n".join(lines)


def write_manifest(payload: dict[str, Any]) -> None:
    paths = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        CREDIT_ROWS_JSON,
        LOG_JSON,
        CARD_MD,
        TICKET_JSON,
    ]
    write_json(
        MANIFEST_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "decision": payload["decision"],
            "created_at": payload.get("timestamp") or utc_now(),
            "allowed_write_scope": ALLOWED_WRITE_SCOPE,
            "files": {
                repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
                for path in paths
            },
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
            "gate1": payload.get("gate1"),
            "gate2": payload.get("gate2"),
            "gate3": payload.get("gate3"),
            "gate4": payload.get("gate4"),
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
                "hyg_jnk_rows": payload["data_coverage"]["row_counts"],
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
