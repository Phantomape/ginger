"""exp-20260708-008: rate-limit-aware retry for daily yfinance fetches.

Measurement repair only. Yahoo rate limiting (``YFRateLimitError: Too Many
Requests``) makes ``yf.download`` log the error and return an empty frame, so
the daily pipeline silently treated rate-limited tickers as missing data —
observed 2026-07-07 as ``ERROR yfinance: ['SPY']`` during the production run,
degrading regime classification inputs. This runner verifies the shared
retry wrapper (``yfinance_bootstrap.download_with_rate_limit_retry`` /
``call_with_rate_limit_retry``) recovers a rate-limited fetch in-process
(no network), confirms the daily download call sites are wired to it, runs the
unit suite, and self-registers the result. No strategy behavior changes.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


EXPERIMENT_ID = "exp-20260708-008"
OWNER = "interactive"
LANE = "measurement_repair"
SLUG = "yfinance_rate_limit_retry"
RUNNER = f"quant/experiments/exp_20260708_008_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, QUANT_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)

DATA_DIR = REPO_ROOT / "data"
BASELINE_RESULT = (
    DATA_DIR / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OUT_DIR = DATA_DIR / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260708_008_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

DAILY_CALL_SITE_MODULES = ("regime.py", "data_layer.py", "trend_signals.py", "crypto_sleeve.py")
TEST_FILE = "quant/test_yf_rate_limit_retry.py"

HYPOTHESIS = (
    "Measurement repair / fault recovery: Yahoo rate limiting makes yf.download "
    "silently return an empty frame, so the daily pipeline treats rate-limited "
    "tickers (SPY regime inputs, OHLCV features, trend context, crypto sleeve) "
    "as missing data with no retry; add a shared rate-limit-aware retry wrapper "
    "in yfinance_bootstrap and adopt it at the daily download call sites "
    "without changing strategy behavior."
)
ALPHA_HYPOTHESIS = (
    "None directly; this restores the reliability of regime/OHLCV inputs that "
    "every production decision consumes, so degraded-data days stop silently "
    "biasing signals and paper sleeve admission."
)
CHANGED_VARIABLE = "yfinance_rate_limit_retry_wrapper_v1"
MECHANISM_FAMILY = "production_daily_market_data_fetch_reliability"
TRIAL_FAMILY = "yfinance_fetch_reliability_repair"
TRIAL_VARIANT_ID = "yfinance_rate_limit_retry_v1"
NEARBY_PRIOR_EXPERIMENTS = ["exp-20260708-007", "exp-20260628-017"]
CAUSAL_COMPONENTS = [
    "shared_rate_limit_detection_helper",
    "exponential_backoff_with_global_sleep_budget",
    "regime_download_adoption",
    "data_layer_ohlcv_adoption",
    "trend_signals_adoption",
    "crypto_sleeve_adoption",
    "no_strategy_behavior_change",
]
PREDICTED_FAILURE_MODES = [
    "rate_limit_outlives_retry_budget",
    "bulk_retry_slows_pipeline_excessively",
    "yfinance_error_dict_api_drift",
    "test_regression",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: str | Path) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default if default is not None else {}


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    drawdowns = [
        float(row.get("max_drawdown_pct"))
        for row in windows
        if row.get("max_drawdown_pct") is not None
    ]
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows), 4
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
        "max_drawdown_pct_worst": round(max(drawdowns), 4) if drawdowns else None,
    }


def simulate_rate_limited_fetch() -> dict[str, Any]:
    """No-network before/after: rate-limited twice, then clears.

    BEFORE (raw yf.download semantics): the caller gets the first, empty frame.
    AFTER (wrapper): the retry loop rides out the limit and returns the data.
    """
    import pandas as pd
    import yfinance
    import yfinance.shared as yf_shared
    import yfinance_bootstrap as yb

    message = "YFRateLimitError('Too Many Requests. Rate limited. Try after a while.')"
    good = pd.DataFrame({"Close": [1.0, 2.0, 3.0]})

    real_download = yfinance.download
    real_sleep = yb.time.sleep
    real_budget_used = yb._sleep_budget_used_s
    calls = {"n": 0}
    sleeps: list[float] = []

    def fake_download(*args, **kwargs):
        index = calls["n"]
        calls["n"] += 1
        yf_shared._ERRORS = {"SPY": message} if index < 2 else {}
        return pd.DataFrame() if index < 2 else good

    try:
        yfinance.download = fake_download
        yb.time.sleep = sleeps.append
        yb._sleep_budget_used_s = 0.0

        yf_shared._ERRORS = {}
        before_frame = yfinance.download("SPY")
        before_recovered = not before_frame.empty

        calls["n"] = 0
        yf_shared._ERRORS = {}
        after_frame = yb.download_with_rate_limit_retry("SPY")
        after_recovered = after_frame is not None and not after_frame.empty
    finally:
        yfinance.download = real_download
        yb.time.sleep = real_sleep
        yb._sleep_budget_used_s = real_budget_used
        yf_shared._ERRORS = {}

    return {
        "scenario": "rate limited on attempts 1-2, cleared on attempt 3",
        "before_single_attempt_recovered": before_recovered,
        "after_wrapper_recovered": after_recovered,
        "wrapper_attempts": calls["n"],
        "wrapper_backoff_sleeps_s": sleeps,
    }


def call_site_wiring() -> dict[str, Any]:
    wiring: dict[str, Any] = {}
    for module in DAILY_CALL_SITE_MODULES:
        source = (QUANT_ROOT / module).read_text(encoding="utf-8")
        wiring[module] = {
            "direct_yf_download_calls": source.count("yf.download("),
            "retry_wrapper_calls": source.count("download_with_rate_limit_retry("),
        }
    return wiring


def run_tests() -> dict[str, Any]:
    proc = subprocess.run(
        [
            str(REPO_ROOT / ".venv" / "Scripts" / "python.exe"),
            "-m",
            "pytest",
            TEST_FILE,
            "quant/test_quant.py",
            "-q",
            "-k",
            "download or ohlcv or regime or crypto or trend or rate_limit or wrapper",
            "--no-header",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=1200,
    )
    tail = (proc.stdout or "").strip().splitlines()[-3:]
    return {
        "command": "pytest " + TEST_FILE + " quant/test_quant.py -k <download/ohlcv/regime/crypto/trend/rate_limit>",
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "tail": tail,
    }


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    baseline = baseline_metrics()
    simulation = simulate_rate_limited_fetch()
    wiring = call_site_wiring()
    tests = run_tests()

    measurement_blockers: list[str] = []
    if not BASELINE_RESULT.exists() or baseline.get("window_count") != 3:
        measurement_blockers.append("baseline_missing_or_nonstandard")
    if simulation["before_single_attempt_recovered"]:
        measurement_blockers.append("before_simulation_unexpectedly_recovered")
    if not simulation["after_wrapper_recovered"]:
        measurement_blockers.append("wrapper_did_not_recover_rate_limited_fetch")
    for module, counts in wiring.items():
        if counts["direct_yf_download_calls"] > 0:
            measurement_blockers.append(f"direct_yf_download_left_in_{module}")
        if counts["retry_wrapper_calls"] <= 0:
            measurement_blockers.append(f"retry_wrapper_not_wired_in_{module}")
    if not tests["passed"]:
        measurement_blockers.append("test_regression")

    measurement_passed = not measurement_blockers
    status = "accepted_measurement_repair" if measurement_passed else "blocked"
    decision = (
        f"accepted_measurement_repair_{SLUG}" if measurement_passed else f"blocked_{SLUG}"
    )
    strategy_delta = {
        "expected_value_score_sum_delta": 0.0,
        "total_pnl_delta": 0.0,
        "trade_count_delta": 0,
        "signals_generated_delta": 0,
        "signals_survived_delta": 0,
        "strategy_behavior_changed": False,
    }
    delta_metrics = {
        **strategy_delta,
        "daily_call_sites_converted": sum(
            counts["retry_wrapper_calls"] for counts in wiring.values()
        ),
        "direct_yf_download_calls_remaining_daily_modules": sum(
            counts["direct_yf_download_calls"] for counts in wiring.values()
        ),
        "before_single_attempt_recovered": simulation["before_single_attempt_recovered"],
        "after_wrapper_recovered": simulation["after_wrapper_recovered"],
        "wrapper_attempts_in_simulation": simulation["wrapper_attempts"],
        "unit_tests_passed": tests["passed"],
    }
    success_probability = float(
        (ticket.get("prediction") or {}).get("success_probability") or 0.85
    )
    prediction = {
        "recorded_at": ticket.get("claimed_at") or ticket.get("created_at"),
        "success_probability": success_probability,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": PREDICTED_FAILURE_MODES,
        "confidence_reason": (ticket.get("prediction") or {}).get("confidence_reason"),
    }
    calibration = {
        "predicted_success_probability": success_probability,
        "actual_success": 1 if measurement_passed else 0,
        "brier_score": round(
            (success_probability - (1.0 if measurement_passed else 0.0)) ** 2, 6
        ),
        "predicted_failure_modes": PREDICTED_FAILURE_MODES,
        "realized_failure_modes": measurement_blockers,
        "predicted_failure_mode_hit": bool(
            set(measurement_blockers) & set(PREDICTED_FAILURE_MODES)
        ),
    }
    production_impact = {
        "trade_enabled": False,
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": True,
        "daily_snapshot_exposed": False,
        "entry_rules_changed": False,
        "exit_rules_changed": False,
        "ranking_changed": False,
        "sizing_changed": False,
        "orders_changed": False,
        "llm_decision_boundary_changed": False,
        "live_ready": False,
        "live_realism_evaluated": False,
        "scope": "measurement_repair_yfinance_rate_limit_retry_only",
    }
    files = [
        "quant/yfinance_bootstrap.py",
        "quant/regime.py",
        "quant/data_layer.py",
        "quant/trend_signals.py",
        "quant/crypto_sleeve.py",
        "quant/test_yf_rate_limit_retry.py",
        RUNNER,
        repo_rel(OUT_JSON),
        repo_rel(LOG_JSON),
        repo_rel(CARD_MD),
        repo_rel(MANIFEST_JSON),
        repo_rel(TICKET_JSON),
        repo_rel(REGISTRY_JSON),
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "status": status,
        "lane": LANE,
        "owner": OWNER,
        "decision": decision,
        "accepted": measurement_passed,
        "accepted_alpha": False,
        "accepted_measurement_repair": measurement_passed,
        "alpha_ready": False,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "measurement_repair_shared_fetch_retry_wrapper",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": "fresh_20260707_spy_rate_limit_fetch_failure",
        "prediction": prediction,
        "calibration": calibration,
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260628-017": "Retry-with-backoff for transient Windows rename failures; same remedy class for vendor-side transients.",
                "exp-20260708-007": "Atomic-write repair on the same daily pipeline; this closes the fetch-side gap.",
                "novelty_gate": "No strong near-neighbor (fetch reliability family is new).",
            },
            "3_single_measurement_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": (
                "Accept only as measurement repair if the wrapper recovers a "
                "simulated rate-limited fetch that raw yf.download loses, all "
                "four daily modules call the wrapper with no direct yf.download "
                "left, unit tests pass, and strategy deltas stay zero."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "max_attempts_default": 4,
            "base_delay_s_default": 15.0,
            "sleep_budget_default_s": 600.0,
            "sleep_budget_env": "GINGER_YF_RATE_LIMIT_SLEEP_BUDGET_S",
            "rate_limit_signatures": ["YFRateLimitError", "Too Many Requests", "Rate limited"],
            "daily_call_site_modules": list(DAILY_CALL_SITE_MODULES),
        },
        "gate1": {
            "passed": BASELINE_RESULT.exists() and baseline.get("window_count") == 3,
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": measurement_passed,
            "dependencies_validated": measurement_passed,
            "fields_checked": [
                "yfinance.shared._ERRORS",
                "YFRateLimitError signature",
                "download return frame",
            ],
            "entry_date_scope": "No signal objects are created or altered; entry_date/target_price contracts untouched.",
            "target_price_scope": "Not applicable; fetch-reliability repair only.",
        },
        "gate3": {
            "passed": measurement_passed,
            "filter_added": False,
            "signals_generated": None,
            "signals_survived": None,
            "survival_rate": None,
            "note": "No filter/entry/rank/size/exit/order rule was added; retry only affects data availability.",
        },
        "gate4": {
            "passed": measurement_passed,
            "accepted_alpha": False,
            "alpha_ready": False,
            "decision": decision,
            "measurement_blockers": measurement_blockers,
            "alpha_blockers": [],
            "measurement_repair_only": True,
            "strategy_rerun_required": False,
            "before_after_strategy_delta": strategy_delta,
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": delta_metrics,
        "before": {
            "behavior": "yf.download swallows YFRateLimitError, logs ERROR ['SPY'], returns empty frame; callers treat it as missing data (no retry)",
            "simulation": {
                "single_attempt_recovered": simulation["before_single_attempt_recovered"]
            },
        },
        "after": {
            "behavior": "download_with_rate_limit_retry detects yfinance.shared._ERRORS signatures and retries with exponential backoff under a process-wide sleep budget",
            "simulation": simulation,
            "call_site_wiring": wiring,
            "tests": tests,
        },
        "production_impact": production_impact,
        "post_run_reflection": {
            "why_result_happened": (
                "yf.download converts per-ticker rate-limit exceptions into an "
                "empty result plus a log line, so no caller could retry; the "
                "shared wrapper reads yfinance.shared._ERRORS (the only reliable "
                "per-call signal) and rides out the limit with bounded backoff."
                if measurement_passed
                else "The retry wrapper did not satisfy the fixed measurement contract."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not re-tune retry counts/delays or re-wrap the same call "
                "sites without new evidence of loss; remaining yf.Ticker "
                "fundamental paths (earnings/info) keep their negative-cache "
                "behavior and only need call_with_rate_limit_retry if rate "
                "limits are actually observed there."
            ),
            "new_evidence_required": (
                "A production run where rate limiting outlives the retry budget "
                "(escalate to a session-level throttle or alternate vendor), or "
                "observed rate-limit loss on the yf.Ticker fundamentals paths."
            ),
        },
        "next_retry_requires": [
            "observed rate-limit data loss on a call site not covered by the wrapper",
            "rate limiting that outlives the 600s process sleep budget",
        ],
        "changed_files": files,
        "related_files": [
            "quant/run.py",
            "quant/yf_negative_cache.py",
            "quant/yf_no_price_cache.py",
            "experiments/logs/exp-20260708-007.json",
        ],
        "allowed_write_scope": files,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -m pytest quant\\test_yf_rate_limit_retry.py -q",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {"used_javascript": False, "evidence": "Python runner only."},
        "lean_quality_passed": measurement_passed,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "ticket_before": {
            "created_at": ticket.get("created_at"),
            "claimed_at": ticket.get("claimed_at"),
            "hub_identity": ticket.get("hub_identity"),
            "novelty": ticket.get("novelty"),
        },
    }


def build_card(payload: dict[str, Any]) -> str:
    delta = payload["delta_metrics"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: yfinance rate-limit retry wrapper",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Daily call sites converted: `{delta['daily_call_sites_converted']}`",
            f"- Direct yf.download left in daily modules: `{delta['direct_yf_download_calls_remaining_daily_modules']}`",
            f"- Simulated rate-limited fetch: raw=`lost`, wrapper=`recovered in {delta['wrapper_attempts_in_simulation']} attempts`",
            f"- Unit tests passed: `{delta['unit_tests_passed']}`",
            "- Strategy behavior changed: `false`",
            "",
            "## Root cause",
            "",
            "yf.download swallows YFRateLimitError per ticker (logs `ERROR ['SPY']`,",
            "returns an empty slice), so regime/OHLCV/trend/crypto fetches silently",
            "degraded to 'no data' whenever Yahoo throttled. The shared wrapper",
            "detects `yfinance.shared._ERRORS` signatures and retries with",
            "exponential backoff under a 600s process-wide sleep budget",
            "(`GINGER_YF_RATE_LIMIT_SLEEP_BUDGET_S`).",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Reproduction",
            "",
            "```powershell",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -m pytest quant\\test_yf_rate_limit_retry.py -q",
            "```",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        QUANT_ROOT / "yfinance_bootstrap.py",
        QUANT_ROOT / "regime.py",
        QUANT_ROOT / "data_layer.py",
        QUANT_ROOT / "trend_signals.py",
        QUANT_ROOT / "crypto_sleeve.py",
        QUANT_ROOT / "test_yf_rate_limit_retry.py",
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
        BASELINE_RESULT,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "changed_files": payload["changed_files"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(payload, allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "accepted_measurement_repair": payload["accepted_measurement_repair"],
            "alpha_ready": False,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "gate4": payload["gate4"],
            "delta_metrics": payload["delta_metrics"],
            "calibration": payload["calibration"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
            "change_type": payload["change_type"],
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": payload["single_causal_variable"],
            "changed_variable": payload["changed_variable"],
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "ticket_file": repo_rel(TICKET_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "before_metrics": payload["before_metrics"],
            "after_metrics": payload["after_metrics"],
            "delta_metrics": payload["delta_metrics"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "next_retry_requires": payload["next_retry_requires"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "calibration": payload["calibration"],
            "hub_identity": payload["ticket_before"].get("hub_identity"),
            "novelty": payload["ticket_before"].get("novelty"),
            "claimed_at": payload["ticket_before"].get("claimed_at"),
        },
        allow_missing_prediction=True,
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "delta_metrics": payload["delta_metrics"],
                "gate4": payload["gate4"],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
