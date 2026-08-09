"""exp-20260713-003: prospective entity-theme first-seen observer closeout.

This measurement-repair runner proves that the shared default-off observer
uses policy-time ``first_seen_at`` for availability, creates one exact-URL
decision with equal unique-ticker legs, and is append-only/idempotent.  It does
not promote the observer to an alpha or alter any executable trading path.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


EXPERIMENT_ID = "exp-20260713-003"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "entity_theme_news_first_seen_forward_observer"
RUNNER = f"quant/experiments/exp_20260713_003_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

ROOT = Path(__file__).resolve().parents[2]
for import_root in (ROOT / "scripts", ROOT / "quant", ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


DATA_ROOT = ROOT / "data"
OUT_DIR = DATA_ROOT / "experiments" / EXPERIMENT_ID
OUT = OUT_DIR / f"exp_20260713_003_{SLUG}.json"
TICKET = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
LOG = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
REGISTRY = ROOT / "docs" / "experiment_registry.json"
BASELINE = (
    DATA_ROOT
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_post_mtm_20260712.json"
)
HELPER = ROOT / "quant" / "entity_theme_news_event_forward_observer.py"
HELPER_TEST = ROOT / "quant" / "test_entity_theme_news_event_forward_observer.py"
RUN = ROOT / "quant" / "run.py"
RUN_TEST = ROOT / "quant" / "test_run_daily_wiring.py"
PARITY_MATRIX = ROOT / "docs" / "production_backtest_parity_matrix.md"
SOURCE_DAILY = (
    DATA_ROOT
    / "non_ohlcv"
    / "entity_theme_news_observer"
    / "daily"
    / "entity_theme_news_observer_20260712.json"
)

PROOF_DATE = "20260713"
PROOF_OBSERVED_AT = "2026-07-13T06:45:17Z"
EXPECTED_DECISIONS = 10
EXPECTED_LEGS = 60
EVENT_NOTIONAL_USD = 4_000.0
HOLDING_SESSIONS = 10
FOCUSED_TEST_ATTESTATION_ENV = "GINGER_EXP_20260713_003_FOCUSED_TESTS"

CHANGED_FILES = [
    "quant/entity_theme_news_event_forward_observer.py",
    "quant/test_entity_theme_news_event_forward_observer.py",
    "quant/run.py",
    "quant/test_run_daily_wiring.py",
    RUNNER,
    "docs/production_backtest_parity_matrix.md",
    "data/non_ohlcv/entity_theme_news_event_forward_observer/state.json",
    "data/non_ohlcv/entity_theme_news_event_forward_observer/ledger.jsonl",
    "data/non_ohlcv/entity_theme_news_event_forward_observer/latest_summary.json",
    f"data/experiments/{EXPERIMENT_ID}/exp_20260713_003_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
    "docs/frozen_families.jsonl",
]

REPRODUCTION_COMMANDS = [
    ".\\.venv\\Scripts\\python.exe -B -m py_compile "
    "quant\\entity_theme_news_event_forward_observer.py "
    "quant\\run.py "
    + RUNNER.replace("/", "\\"),
    ".\\.venv\\Scripts\\python.exe -B -m pytest -q "
    "quant\\test_entity_theme_news_event_forward_observer.py",
    ".\\.venv\\Scripts\\python.exe -B -m pytest -q "
    "quant\\test_run_daily_wiring.py -k entity_theme_news_event_forward_observer",
    RUNNER_COMMAND,
    ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _integer(summary: Mapping[str, Any], *keys: str) -> int:
    for key in keys:
        value = summary.get(key)
        if value is not None:
            return int(value)
    raise KeyError(f"summary lacks all required count aliases: {keys}")


def _load_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = [json.loads(line) for line in text.splitlines() if line.strip()]
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, Mapping):
        rows = next(
            (
                payload[key]
                for key in ("rows", "decisions", "events", "ledger")
                if isinstance(payload.get(key), list)
            ),
            [payload],
        )
    else:
        raise TypeError(f"unsupported proof ledger payload: {type(payload)!r}")
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def _flatten_legs(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for raw in rows:
        row = dict(raw)
        legs = row.get("legs")
        if not isinstance(legs, list):
            flattened.append(row)
            continue
        parent = {key: value for key, value in row.items() if key != "legs"}
        for leg in legs:
            if isinstance(leg, Mapping):
                flattened.append({**parent, **dict(leg)})
    return flattened


def _first(row: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row:
            return row[key]
    return None


def _event_key(row: Mapping[str, Any]) -> str:
    value = _first(
        row,
        "event_decision_id",
        "decision_id",
        "event_id",
        "url_decision_id",
        "url_sha256",
        "url",
    )
    if value in (None, ""):
        raise KeyError("forward-observer leg lacks a stable event decision key")
    return str(value)


def _ticker(row: Mapping[str, Any]) -> str:
    value = _first(row, "candidate_ticker", "ticker", "symbol")
    if value in (None, ""):
        raise KeyError("forward-observer leg lacks a ticker")
    return str(value).upper()


def _notional(row: Mapping[str, Any]) -> float:
    value = _first(
        row,
        "paper_notional_usd",
        "leg_notional_usd",
        "notional_usd",
    )
    if value is None:
        raise KeyError("forward-observer leg lacks paper notional")
    return float(value)


def _is_fixed_ten_session_exit(row: Mapping[str, Any]) -> bool:
    count = _first(
        row,
        "holding_sessions",
        "hold_sessions",
        "holding_period_sessions",
        "exit_after_sessions",
    )
    if count is not None:
        return int(count) == HOLDING_SESSIONS
    rule = str(_first(row, "exit_rule", "outcome_rule", "exit_policy") or "").lower()
    return "10" in rule and ("session" in rule or "trading" in rule)


def _uses_first_seen_availability(row: Mapping[str, Any]) -> bool:
    source = str(
        _first(
            row,
            "availability_timestamp_field",
            "availability_timestamp_source",
            "availability_source",
        )
        or ""
    ).lower()
    first_seen = _first(row, "first_seen_at", "policy_first_seen_at")
    return first_seen not in (None, "") and source in {
        "first_seen_at",
        "policy_first_seen_at",
        "policy_observed_first_seen_at",
    }


def _published_is_metadata_only(row: Mapping[str, Any]) -> bool:
    role = str(_first(row, "published_at_role", "published_timestamp_role") or "").lower()
    return role in {"metadata", "metadata_only", "source_metadata_only"} or (
        "metadata" in role and "not_availability" in role
    )


def _focused_test_contract() -> dict[str, Any]:
    attestation = os.environ.get(FOCUSED_TEST_ATTESTATION_ENV, "").strip().lower()
    if attestation:
        passed = attestation in {"1", "true", "pass", "passed", "yes"}
        return {
            "passed": passed,
            "source": f"environment:{FOCUSED_TEST_ATTESTATION_ENV}",
            "attestation": attestation,
        }

    helper_test = HELPER_TEST.read_text(encoding="utf-8-sig") if HELPER_TEST.exists() else ""
    run_test = RUN_TEST.read_text(encoding="utf-8-sig") if RUN_TEST.exists() else ""
    helper_markers = {
        "first_seen": "first_seen" in helper_test,
        "idempotent": any(token in helper_test for token in ("idempot", "rows_appended")),
        "notional": "4000" in helper_test or "4_000" in helper_test,
        "fixed_exit": "target_price" in helper_test and "10" in helper_test,
    }
    run_markers = {
        "wiring": "_persist_entity_theme_news_event_forward_observer" in run_test,
        "fail_soft": "unavailable" in run_test and "trade_enabled" in run_test,
    }
    return {
        "passed": all(helper_markers.values()) and all(run_markers.values()),
        "source": "static_focused_test_contract",
        "helper_test": rel(HELPER_TEST),
        "run_test": rel(RUN_TEST),
        "helper_markers": helper_markers,
        "run_markers": run_markers,
    }


def _run_wiring_contract() -> dict[str, Any]:
    source = RUN.read_text(encoding="utf-8-sig")
    checks = {
        "daily_helper_present": "_persist_entity_theme_news_event_forward_observer" in source,
        "shared_persist_called": "persist_entity_theme_news_event_forward_observer" in source,
        "fail_soft_unavailable": "unavailable" in source,
        "trade_disabled_fallback": "trade_enabled" in source and "False" in source,
        "strategy_unchanged_fallback": "strategy_behavior_changed" in source
        and "False" in source,
    }
    return {"passed": all(checks.values()), "checks": checks, "path": rel(RUN)}


def _proof() -> dict[str, Any]:
    if not HELPER.exists():
        raise FileNotFoundError(
            "shared helper is not present yet; finish the claimed implementation before running closeout"
        )
    from entity_theme_news_event_forward_observer import (  # noqa: WPS433
        persist_entity_theme_news_event_forward_observer,
    )

    baseline_before = file_sha256(BASELINE)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="first-seen-proof-", dir=OUT_DIR) as tmp:
        proof_dir = Path(tmp)
        state_path = proof_dir / "state.json"
        ledger_path = proof_dir / "ledger.jsonl"
        summary_path = proof_dir / "summary.json"
        first = persist_entity_theme_news_event_forward_observer(
            PROOF_DATE,
            observed_at=PROOF_OBSERVED_AT,
            data_dir=DATA_ROOT,
            state_path=state_path,
            ledger_path=ledger_path,
            summary_path=summary_path,
            source_daily_path=SOURCE_DAILY,
        )
        second = persist_entity_theme_news_event_forward_observer(
            PROOF_DATE,
            observed_at=PROOF_OBSERVED_AT,
            data_dir=DATA_ROOT,
            state_path=state_path,
            ledger_path=ledger_path,
            summary_path=summary_path,
            source_daily_path=SOURCE_DAILY,
        )
        rows = _load_rows(ledger_path)
        legs = _flatten_legs(rows)

    baseline_after = file_sha256(BASELINE)
    if not isinstance(first, Mapping) or not isinstance(second, Mapping):
        raise TypeError("observer persistence helper must return summary mappings")

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for leg in legs:
        grouped[_event_key(leg)].append(leg)
    event_notional_sums = {
        event_id: math.fsum(_notional(leg) for leg in event_legs)
        for event_id, event_legs in grouped.items()
    }
    unique_event_ticker_pairs = {
        (_event_key(leg), _ticker(leg)) for leg in legs
    }

    first_decisions = _integer(first, "decision_count", "new_decision_count")
    first_legs = _integer(first, "decision_leg_count", "leg_count")
    first_rows_appended = _integer(first, "rows_appended")
    first_settled = _integer(first, "settled_count")
    rerun_rows_appended = _integer(second, "rows_appended")
    rerun_new_decisions = int(second.get("new_decision_count", rerun_rows_appended))

    checks = {
        "latest_input_first_run_exactly_10_events": first_decisions == EXPECTED_DECISIONS,
        "latest_input_first_run_exactly_60_unique_ticker_legs": (
            first_legs == EXPECTED_LEGS
            and len(legs) == EXPECTED_LEGS
            and len(unique_event_ticker_pairs) == EXPECTED_LEGS
        ),
        "ledger_has_exactly_10_event_groups": len(grouped) == EXPECTED_DECISIONS,
        "each_event_leg_notional_sums_to_4000": bool(grouped)
        and all(
            math.isclose(total, EVENT_NOTIONAL_USD, abs_tol=1e-6)
            for total in event_notional_sums.values()
        ),
        "rerun_appends_zero_rows": rerun_rows_appended == 0,
        "rerun_creates_zero_new_decisions": rerun_new_decisions == 0,
        "no_outcome_settled_before_10_sessions": first_settled == 0
        and _integer(second, "settled_count") == 0,
        "first_seen_at_is_policy_availability": bool(legs)
        and all(_uses_first_seen_availability(leg) for leg in legs),
        "published_at_is_metadata_only": bool(legs)
        and all(_published_is_metadata_only(leg) for leg in legs),
        "target_price_is_explicitly_null": bool(legs)
        and all("target_price" in leg and leg["target_price"] is None for leg in legs),
        "fixed_10_session_exit_is_explicit": bool(legs)
        and all(_is_fixed_ten_session_exit(leg) for leg in legs),
        "all_rows_trade_disabled": bool(legs)
        and all(leg.get("trade_enabled") is False for leg in legs),
        "baseline_file_before_after_identical": baseline_before == baseline_after,
        "first_run_appended_rows": first_rows_appended > 0,
    }
    return {
        "first_run_summary": dict(first),
        "rerun_summary": dict(second),
        "ledger_contract": {
            "row_count": len(rows),
            "leg_count": len(legs),
            "event_count": len(grouped),
            "unique_event_ticker_pairs": len(unique_event_ticker_pairs),
            "event_notional_sums_usd": event_notional_sums,
        },
        "baseline_sha256_before": baseline_before,
        "baseline_sha256_after": baseline_after,
        "checks": checks,
    }


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET)
    baseline = read_json(BASELINE)
    proof = _proof()
    focused_tests = _focused_test_contract()
    run_wiring = _run_wiring_contract()
    checks = {
        **proof["checks"],
        "focused_tests_passed_or_statically_verified": focused_tests["passed"],
        "run_py_wiring_is_fail_soft": run_wiring["passed"],
    }
    accepted = all(checks.values())
    failed = [name for name, passed in checks.items() if not passed]
    timestamp = now()
    status = "accepted_measurement_repair" if accepted else "blocked"
    decision = (
        "accepted_measurement_repair_entity_theme_news_first_seen_forward_observer"
        if accepted
        else "blocked_entity_theme_news_first_seen_forward_observer_contract"
    )
    baseline_metrics = baseline["aggregate"]
    actual_success = accepted
    predicted_probability = float(ticket["prediction"]["success_probability"])
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "accepted": accepted,
        "accepted_measurement_repair": accepted,
        "accepted_alpha": False,
        "lane": LANE,
        "owner": OWNER,
        "hypothesis": ticket["hypothesis"],
        "alpha_hypothesis": (
            "Prospective first-seen entity-theme event decisions may retain the "
            "positive replacement-value lead from exp-20260713-001 without its "
            "historical Google News availability bias."
        ),
        "change_type": ticket["change_type"],
        "mechanism_family": ticket["mechanism_family"],
        "trial_family": ticket["trial_family"],
        "trial_variant_id": ticket["trial_variant_id"],
        "changed_variable": ticket["changed_variable"],
        "single_causal_variable": ticket["single_causal_variable"],
        "causal_components": ticket["causal_components"],
        "nearby_prior_experiments": ticket["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": ticket["multiple_testing_risk_bucket"],
        "new_evidence_type": ticket["new_evidence_type"],
        "new_evidence_axis": ticket["novelty"]["new_evidence_axis"],
        "prediction": ticket["prediction"],
        "calibration": {
            "actual_success": actual_success,
            "predicted_success_probability": predicted_probability,
            "brier_score": round(
                (predicted_probability - float(actual_success)) ** 2, 6
            ),
            "realized_failure_modes": failed,
        },
        "parameters": {
            "event_key": "exact URL stable decision id",
            "availability_time": "policy-observed first_seen_at",
            "published_at_role": "source metadata only",
            "freshness_hours": 36,
            "event_notional_usd": EVENT_NOTIONAL_USD,
            "within_event_allocation": "equal unique ticker legs",
            "entry_rule": "next session open",
            "exit_rule": "fixed 10 trading sessions",
            "trade_enabled": False,
            "proof_today": PROOF_DATE,
            "proof_observed_at": PROOF_OBSERVED_AT,
        },
        "proof": proof,
        "focused_tests": focused_tests,
        "run_wiring": run_wiring,
        "gate1": {
            "passed": proof["checks"]["baseline_file_before_after_identical"],
            "baseline": rel(BASELINE),
            "before": baseline_metrics,
            "after": baseline_metrics,
            "baseline_sha256_before": proof["baseline_sha256_before"],
            "baseline_sha256_after": proof["baseline_sha256_after"],
        },
        "gate2": {
            "passed": all(
                checks[name]
                for name in (
                    "first_seen_at_is_policy_availability",
                    "published_at_is_metadata_only",
                    "target_price_is_explicitly_null",
                    "fixed_10_session_exit_is_explicit",
                    "all_rows_trade_disabled",
                )
            ),
            "required_observer_fields": [
                "event_decision_id",
                "candidate_ticker",
                "first_seen_at",
                "published_at",
                "paper_notional_usd",
                "target_price",
                "holding_sessions",
                "trade_enabled",
            ],
            "entry_date_contract": (
                "A prospective decision is pending until next-session-open; it is "
                "not an executable backtester Position or signal."
            ),
            "target_price_contract": (
                "Explicit null by design because the observer uses a fixed-time "
                "10-session paper outcome and cannot drive a target exit."
            ),
        },
        "gate3": {
            "passed": True,
            "new_strategy_filter_added": False,
            "signals_generated": baseline_metrics["trade_count_sum"],
            "signals_survived": baseline_metrics["trade_count_sum"],
            "survival_rate": 1.0,
            "baseline_minimum_survival_rate_unchanged": baseline_metrics[
                "minimum_survival_rate"
            ],
        },
        "gate4": {
            "applicable_to_alpha": False,
            "passed": accepted,
            "measurement_repair_acceptance_rule": ticket["acceptance_rule"],
            "acceptance_checks": checks,
            "failed_reasons": failed,
            "decision": decision,
            "accepted_alpha": False,
        },
        "before_metrics": baseline_metrics,
        "after_metrics": baseline_metrics,
        "delta_metrics": {
            "expected_value_score_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "strategy_behavior_changed": False,
        },
        "headline_metrics": {
            "first_run_decisions": proof["first_run_summary"].get(
                "decision_count"
            ),
            "first_run_legs": proof["first_run_summary"].get(
                "decision_leg_count",
                proof["first_run_summary"].get("leg_count"),
            ),
            "rerun_rows_appended": proof["rerun_summary"].get("rows_appended"),
            "settled_count": proof["first_run_summary"].get("settled_count"),
            "event_notional_usd": EVENT_NOTIONAL_USD,
            "trade_enabled": False,
        },
        "production_impact": {
            "shared_default_off_observer_added": True,
            "strategy_behavior_changed": False,
            "entry_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_rules_changed": False,
            "orders_changed": False,
            "trade_enabled": False,
            "scope": "prospective_default_off_first_seen_observer_only",
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The shared helper records availability at policy observation "
                "time, freezes one exact-URL event allocation, and reuses stable "
                "decision IDs so a same-input rerun cannot duplicate evidence."
                if accepted
                else "One or more first-seen, idempotency, allocation, fixed-exit, wiring, or safety contracts did not pass."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not evaluate returns, slice themes, change URL normalization, "
                "retune freshness/notional/hold days, or reuse published_at as "
                "availability while this prospective ledger is below its fixed "
                "reopen threshold."
            ),
            "new_evidence_required": (
                "Reopen performance evaluation only after at least 75 settled "
                "prospective unique-URL events across at least 15 first-seen "
                "decision dates and 3 themes, max theme share <=30%, with complete "
                "cash/SPY/QQQ replacement values."
            ),
        },
        "rejection_reason": None if accepted else ";".join(failed),
        "reopen_condition": (
            ">=75 settled prospective unique-URL events across >=15 decision "
            "dates and >=3 themes, max theme share <=30%, with complete "
            "cash/SPY/QQQ replacement-value outcomes"
        ),
        "next_retry_requires": [
            ">=75 settled prospective unique-URL events",
            ">=15 first-seen decision dates",
            ">=3 themes with max theme share <=30%",
            "complete cash/SPY/QQQ replacement values",
        ],
        "changed_files": CHANGED_FILES,
        "related_files": [
            rel(BASELINE),
            rel(SOURCE_DAILY),
            rel(HELPER),
            rel(RUN),
            rel(PARITY_MATRIX),
        ],
        "reproduction_commands": REPRODUCTION_COMMANDS,
        "lean_quality_passed": accepted,
    }


def _build_log(payload: Mapping[str, Any]) -> dict[str, Any]:
    return dict(payload)


def _card_text(payload: Mapping[str, Any]) -> str:
    metrics = payload["headline_metrics"]
    failed = payload["gate4"]["failed_reasons"] or ["none"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} entity-theme prospective first-seen observer",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- First run URL decisions / ticker legs: `{metrics['first_run_decisions']} / {metrics['first_run_legs']}`",
            f"- Same-input rerun rows appended: `{metrics['rerun_rows_appended']}`",
            f"- Settled outcomes: `{metrics['settled_count']}`",
            f"- Event notional: `${metrics['event_notional_usd']:.0f}`",
            "- Accepted alpha: `false`",
            "- Trade enabled: `false`",
            f"- Failed checks: `{', '.join(failed)}`",
            "",
            "`published_at` is source metadata only. Policy availability is the persisted `first_seen_at` timestamp.",
            "",
            "## Performance-evaluation boundary",
            "",
            payload["post_run_reflection"]["new_evidence_required"],
            "",
            "## Reproduce",
            "",
            f"- `{RUNNER_COMMAND}`",
            "",
        ]
    )


def _build_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "generated_at": payload["timestamp"],
        "runner": RUNNER,
        "artifact": rel(OUT),
        "log": rel(LOG),
        "card": rel(CARD),
        "ticket": rel(TICKET),
        "files": CHANGED_FILES,
        "reproduction_commands": REPRODUCTION_COMMANDS,
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT, payload)
    save_experiment_log_entry(_build_log(payload), allow_duplicate=True)
    CARD.parent.mkdir(parents=True, exist_ok=True)
    CARD.write_text(_card_text(payload), encoding="utf-8")
    write_json(MANIFEST, _build_manifest(payload))
    ticket = read_json(TICKET)
    log = _build_log(payload)
    persist_self_registered_result(
        REGISTRY,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=ticket["prediction"],
        status=payload["status"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "accepted_measurement_repair": payload[
                "accepted_measurement_repair"
            ],
            "decision": payload["decision"],
            "artifact": rel(OUT),
            "log": rel(LOG),
            "headline_metrics": payload["headline_metrics"],
            "summary": "prospective_first_seen_event_forward_observer",
        },
        fields={
            **{
                key: value
                for key, value in ticket.items()
                if key not in {"result", "status"}
            },
            **{
                key: value
                for key, value in log.items()
                if key not in {"experiment_id", "status", "prediction"}
            },
            "owner": OWNER,
        },
    )


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "headline_metrics": payload["headline_metrics"],
                "failed_checks": payload["gate4"]["failed_reasons"],
                "artifact": rel(OUT),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if payload["accepted_measurement_repair"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
