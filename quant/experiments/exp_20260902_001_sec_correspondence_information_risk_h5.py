"""Evaluate the frozen SEC CORRESP H5 avoid-long scout exactly once."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
for entry in (ROOT, ROOT / "scripts"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import (  # noqa: E402
    _validate_file_backed_reservation_anchors,
    persist_self_registered_result,
)
from scripts.prepare_v2_sec_correspondence_scout import (  # noqa: E402
    EXPECTED_SESSION_DATES,
    evaluate_avoid_long_h5,
)


EXPERIMENT_ID = "exp-20260902-001"
OWNER = "codex-edge-v2"
SCOUT_DIR = ROOT / "data/v2/scouts/sec_correspondence_information_risk_h5_20260902"
TICKET = ROOT / f"experiments/tickets/{EXPERIMENT_ID}.json"
LOG = ROOT / f"experiments/logs/{EXPERIMENT_ID}.json"
REGISTRY = ROOT / "docs/experiment_registry.json"
POOL = SCOUT_DIR / "candidate_pool.json"
DECISION = SCOUT_DIR / "decision_record.json"
RECIPE = SCOUT_DIR / "market_data_recipe.json"
DISPOSITION = SCOUT_DIR / "source_disposition_manifest.json"
ARTIFACT = ROOT / (
    "data/experiments/exp-20260902-001/"
    "exp_20260902_001_sec_correspondence_information_risk_h5.json"
)
RUNNER_REL = (
    "quant/experiments/exp_20260902_001_sec_correspondence_information_risk_h5.py"
)
PREPARATION_REL = "scripts/prepare_v2_sec_correspondence_scout.py"
PREPARATION_SHA256 = (
    "3aae21dae50eba23b203854c0107327bd883d64a6938b2b112ec8287bed48d93"
)
EXPECTED_SNAPSHOT_LOCATORS = {
    "data/v2/scouts/sec_correspondence_information_risk_h5_20260902/candidate_pool.json",
    "data/v2/scouts/sec_correspondence_information_risk_h5_20260902/decision_record.json",
    "data/v2/scouts/sec_correspondence_information_risk_h5_20260902/market_data_recipe.json",
    "data/v2/scouts/sec_correspondence_information_risk_h5_20260902/source_disposition_manifest.json",
    "data/v2/source_bundles/sec_edgar_8k/20260820/20260821T125627Z/bundle.json",
    "data/v2/source_bundles/sec_edgar_8k/20260820/20260821T125627Z/company_tickers_exchange.json",
    "data/v2/source_bundles/sec_edgar_8k/20260820/20260821T125627Z/form.20260820.idx",
}
EXPECTED_LOCKED_VARIABLES = [
    "form_type_exact_CORRESP",
    "complete_4183_row_disposition",
    "single_supported_exchange_CIK_mapping",
    "known_before_2026_08_21_open",
    "all_17_mapped_deduplicated_issuers",
    "next_session_open",
    "h5_exact_five_sessions",
    "window_2026_08_21_to_2026_08_27",
    "round_trip_cost_10bps",
    "cash_comparator",
    "observed_only",
    "trade_enabled_false",
]


class ContaminationError(RuntimeError):
    """A claim-bound identity or frozen evaluation degree of freedom drifted."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _stable_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ContaminationError(f"expected JSON object: {path}")
    return value


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _verify_claimed_ticket_state(ticket: dict[str, Any]) -> None:
    if ticket.get("experiment_id") != EXPERIMENT_ID:
        raise ContaminationError("ticket experiment identity drifted")
    if ticket.get("status") != "claimed" or ticket.get("owner") != OWNER:
        raise ContaminationError("ticket is not an active claim by the frozen owner")
    if ticket.get("completed_at") is not None or ticket.get("result") is not None:
        raise ContaminationError("ticket already carries terminal result state")


def _verify_strict_claim_anchors(ticket: dict[str, Any]) -> None:
    try:
        _validate_file_backed_reservation_anchors(REGISTRY, ticket)
    except (OSError, TypeError, ValueError) as exc:
        raise ContaminationError(
            "ticket/manifest/registry claim anchors are not complete 111"
        ) from exc


def _verify_single_run_state(ticket: dict[str, Any]) -> None:
    _verify_claimed_ticket_state(ticket)
    existing = [str(path) for path in (ARTIFACT, LOG) if path.exists()]
    if existing:
        raise ContaminationError(
            "single-run output already exists: " + ", ".join(existing)
        )
    _verify_strict_claim_anchors(ticket)


def _reserve_run_attempt():
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    try:
        return ARTIFACT.open("x", encoding="utf-8", newline="")
    except FileExistsError as exc:
        raise ContaminationError(
            f"single-run output already exists: {ARTIFACT}"
        ) from exc


def _revalidate_reserved_run_state() -> dict[str, Any]:
    ticket = _read_json(TICKET)
    _verify_claimed_ticket_state(ticket)
    if LOG.exists():
        raise ContaminationError(f"single-run output already exists: {LOG}")
    _verify_strict_claim_anchors(ticket)
    return ticket


def _write_reserved_json(handle, payload: Any) -> None:
    handle.write(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    )
    handle.flush()


def _finite_positive(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number <= 0:
        return None
    return number


def _verify_claim_bound_inputs(
    ticket: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, str]]:
    _verify_claimed_ticket_state(ticket)
    promotion = ticket.get("alpha_promotion") or {}
    expected_promotion = {
        "admission_class": "research_replay",
        "candidate_id": "cand-e5c03e685c6831c92e4b",
        "promotion_hash": "9b43a88ceed173c6ddc7591ef01ecb7bbdaf85ad3e0afb303c01938799220415",
        "result_ceiling": "observed_only",
        "selected_evidence_grade": "lead",
        "paper_live_eligible": False,
    }
    if any(promotion.get(key) != value for key, value in expected_promotion.items()):
        raise ContaminationError("alpha promotion identity drifted")
    if ticket.get("locked_variables") != EXPECTED_LOCKED_VARIABLES:
        raise ContaminationError("locked evaluation variables drifted")
    if ticket.get("evaluation_windows") != [
        {"start": "2026-08-21", "end": "2026-08-27"}
    ]:
        raise ContaminationError("evaluation window drifted")

    snapshot_rows = (
        (ticket.get("alpha_promotion_claim_receipt") or {}).get(
            "research_artifact_snapshots"
        )
        or []
    )
    snapshots = {row.get("locator"): row.get("sha256") for row in snapshot_rows}
    if len(snapshots) != len(snapshot_rows) or set(snapshots) != EXPECTED_SNAPSHOT_LOCATORS:
        raise ContaminationError("claim receipt research artifact set drifted")
    identities: dict[str, str] = {}
    for locator in sorted(EXPECTED_SNAPSHOT_LOCATORS):
        actual = _sha256(ROOT / locator)
        if actual != snapshots[locator]:
            raise ContaminationError(f"claim-bound artifact drifted: {locator}")
        identities[locator] = actual

    if _sha256(ROOT / PREPARATION_REL) != PREPARATION_SHA256:
        raise ContaminationError("frozen evaluator implementation drifted")
    identities[PREPARATION_REL] = PREPARATION_SHA256
    identities[RUNNER_REL] = _sha256(ROOT / RUNNER_REL)

    disposition = _read_json(DISPOSITION)
    pool = _read_json(POOL)
    recipe = _read_json(RECIPE)
    decision = _read_json(DECISION)
    expected_counts = {
        "excluded": 2,
        "mapped": 20,
        "non_target_form": 4116,
        "unmapped": 45,
    }
    if any(
        (
            disposition.get("source_reported_row_count") != 4183,
            disposition.get("target_form_row_count") != 67,
            disposition.get("disposition_counts") != expected_counts,
            disposition.get("row_count_conserved") is not True,
            disposition.get("outcome_blind") is not True,
            disposition.get("trade_enabled") is not False,
            len(disposition.get("rows") or []) != 4183,
        )
    ):
        raise ContaminationError("source disposition contract drifted")
    source_hashes = disposition.get("source_artifact_snapshot_hashes") or {}
    if len(source_hashes) != 5:
        raise ContaminationError("source authorization/identity set drifted")
    for locator, expected in source_hashes.items():
        actual = _sha256(ROOT / locator)
        if actual != expected:
            raise ContaminationError(f"source artifact drifted: {locator}")
        identities[locator] = actual

    candidates = pool.get("candidates") or []
    codes = [f"US.{row.get('symbol')}" for row in candidates]
    expected_recipe = {
        "provider": "moomoo OpenAPI via local authenticated OpenD",
        "opend_endpoint": "127.0.0.1:11111",
        "codes": codes,
        "start_date": "2026-08-21",
        "end_date": "2026-08-27",
        "expected_session_dates": EXPECTED_SESSION_DATES,
        "bar_type": "K_DAY",
        "adjustment": "NONE",
        "session": "RTH",
        "entry_field": "first_session_open",
        "exit_field": "fifth_session_close",
        "horizon_sessions": 5,
        "round_trip_cost_bps": 10.0,
        "baseline": "equal_weight_next_session_open_long_held_h5",
        "treatment": "avoid_long_and_hold_cash",
        "comparators": ["cash"],
        "minimum_evaluable_security_count": 10,
        "minimum_positive_lead_security_count": 30,
        "result_ceiling": "observed_only",
        "paper_live_eligible": False,
        "trade_enabled": False,
        "order_intent_count": 0,
        "outcomes_accessed_before_freeze": False,
    }
    if any(recipe.get(key) != value for key, value in expected_recipe.items()):
        raise ContaminationError("frozen market-data recipe drifted")
    if ticket.get("acceptance_rule") != recipe.get("acceptance_rule"):
        raise ContaminationError("ticket/recipe acceptance rule split")
    if len(candidates) != 17 or len(codes) != len(set(codes)):
        raise ContaminationError("candidate population drifted")
    if any(
        (
            pool.get("candidate_count") != 17,
            pool.get("mapped_source_row_count") != 20,
            pool.get("source_row_count") != 4183,
            pool.get("candidate_security_set_equals_mapped_deduplicated_set")
            is not True,
            pool.get("outcome_blind") is not True,
            pool.get("trade_enabled") is not False,
            decision.get("candidate_pool_hash") != pool.get("candidate_pool_hash"),
            decision.get("market_data_recipe_hash") != recipe.get("recipe_hash"),
            decision.get("selection_count") != 17,
            decision.get("selected_security_ids")
            != [row.get("security_id") for row in candidates],
            decision.get("entry_at") != "2026-08-21T13:30:00Z",
            decision.get("exit_at") != "2026-08-27T20:00:00Z",
            decision.get("outcome_blind") is not True,
            decision.get("outcome_values_read") is not False,
            decision.get("order_intent_count") != 0,
            decision.get("trade_enabled") is not False,
        )
    ):
        raise ContaminationError("candidate pool or decision contract drifted")
    return pool, recipe, decision, identities


def _fetch_bars(codes: list[str], recipe: dict[str, Any]) -> dict[str, Any]:
    queried_at = _now()
    rows: list[dict[str, Any]] = []
    host, port_text = str(recipe["opend_endpoint"]).rsplit(":", 1)
    context = None
    sdk_version = "unavailable"
    setup_error: str | None = None
    try:
        import moomoo
        from moomoo import AuType, KLType, OpenQuoteContext, RET_OK, Session

        sdk_version = str(getattr(moomoo, "__version__", "unknown"))
        context = OpenQuoteContext(host=host, port=int(port_text))
    except Exception as exc:
        setup_error = f"provider setup failed: {type(exc).__name__}: {exc}"

    try:
        for code in codes:
            row: dict[str, Any] = {"code": code}
            if context is None:
                row.update({"status": "provider_error", "error": setup_error})
                rows.append(row)
                continue
            try:
                ret, data, page_key = context.request_history_kline(
                    code,
                    start=recipe["start_date"],
                    end=recipe["end_date"],
                    ktype=KLType.K_DAY,
                    autype=AuType.NONE,
                    max_count=10,
                    extended_time=False,
                    session=Session.RTH,
                )
            except Exception as exc:
                row.update(
                    {
                        "status": "provider_error",
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                rows.append(row)
                continue
            row["provider_return_code"] = int(ret)
            if ret != RET_OK:
                row.update({"status": "provider_error", "error": str(data)})
                rows.append(row)
                continue
            if page_key not in (None, ""):
                row.update(
                    {
                        "status": "invalid_response",
                        "error": "unexpected pagination for the frozen five-session range",
                    }
                )
                rows.append(row)
                continue
            if getattr(data, "empty", True):
                row.update({"status": "missing", "error": "empty response"})
                rows.append(row)
                continue

            bars_by_date: dict[str, dict[str, Any]] = {}
            duplicate_date = False
            for _, record in data.iterrows():
                day = str(record.get("time_key"))[:10]
                if day in bars_by_date:
                    duplicate_date = True
                bars_by_date[day] = {
                    "date": day,
                    "open": _finite_positive(record.get("open")),
                    "close": _finite_positive(record.get("close")),
                }
            observed_dates = sorted(bars_by_date)
            if duplicate_date or observed_dates != EXPECTED_SESSION_DATES:
                row.update(
                    {
                        "status": "missing",
                        "error": "response did not match the exact frozen H5 sessions",
                        "observed_session_dates": observed_dates,
                    }
                )
                rows.append(row)
                continue
            bars = [bars_by_date[day] for day in EXPECTED_SESSION_DATES]
            if any(bar["open"] is None or bar["close"] is None for bar in bars):
                row.update(
                    {
                        "status": "invalid_bar",
                        "error": "non-finite or non-positive price in frozen sessions",
                    }
                )
                rows.append(row)
                continue
            row.update(
                {
                    "status": "usable",
                    "session_dates": list(EXPECTED_SESSION_DATES),
                    "entry_date": EXPECTED_SESSION_DATES[0],
                    "exit_date": EXPECTED_SESSION_DATES[-1],
                    "entry_open": bars[0]["open"],
                    "exit_close": bars[-1]["close"],
                    "bars": bars,
                }
            )
            rows.append(row)
    finally:
        if context is not None:
            context.close()

    identity_payload = {
        "provider": recipe["provider"],
        "sdk_version": sdk_version,
        "opend_endpoint": recipe["opend_endpoint"],
        "start_date": recipe["start_date"],
        "end_date": recipe["end_date"],
        "expected_session_dates": EXPECTED_SESSION_DATES,
        "adjustment": recipe["adjustment"],
        "session": recipe["session"],
        "rows": rows,
    }
    return {
        "schema_version": 1,
        "record_type": "v2_private_replay_exact_evaluation_input",
        "experiment_id": EXPERIMENT_ID,
        **identity_payload,
        "queried_at": queried_at,
        "completed_at": _now(),
        "query_count": len(codes),
        "input_identity": _stable_hash(identity_payload),
        "trade_enabled": False,
        "order_intent_count": 0,
    }


def _status_and_disposition(evaluation: dict[str, Any]) -> tuple[str, str, bool]:
    diagnostic = evaluation["diagnostic_disposition"]
    if diagnostic == "positive_replay_lead_not_promoted":
        return "observed_only", diagnostic, False
    if diagnostic not in {
        "rejected",
        "inconclusive_insufficient_sample",
        "invalid_contaminated",
    }:
        raise ContaminationError(f"unsupported diagnostic disposition: {diagnostic}")
    return "rejected", diagnostic, diagnostic == "invalid_contaminated"


def _why_result_happened(evaluation: dict[str, Any]) -> str:
    diagnostic = evaluation["diagnostic_disposition"]
    usable = evaluation.get("usable_security_count")
    checks = evaluation.get("directional_checks") or {}
    if diagnostic == "invalid_contaminated":
        return (
            "The run failed closed because a claim-bound identity or frozen evaluation "
            "contract drifted before valid evidence could be established."
        )
    if diagnostic == "inconclusive_insufficient_sample" and usable is not None:
        if usable < 10:
            return (
                f"Only {usable} frozen issuers had the exact five required sessions, "
                "below the predeclared ten-security evaluation floor."
            )
        return (
            f"All directional checks passed for {usable} usable issuers, but the "
            "predeclared thirty-security positive-lead floor was unreachable."
        )
    if diagnostic == "positive_replay_lead_not_promoted":
        return (
            "Every predeclared direction and coverage check passed, producing only an "
            "observed replay lead under the frozen research-only ceiling."
        )
    failed = sorted(key for key, passed in checks.items() if not passed)
    return (
        "The complete frozen basket failed the predeclared directional hypothesis; "
        f"the failed checks were {', '.join(failed) or 'not recorded'}."
    )


def _artifact_payload(
    *,
    ticket: dict[str, Any],
    status: str,
    disposition: str,
    evidence_invalid: bool,
    identities: dict[str, str],
    raw: dict[str, Any] | None,
    evaluation: dict[str, Any],
    contamination_reason: str | None,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "record_type": "v2_private_replay_scout_result",
        "experiment_id": EXPERIMENT_ID,
        "lane": "alpha_search",
        "status": status,
        "decision": status,
        "disposition": disposition,
        "artifact_disposition": disposition,
        "evidence_invalid": evidence_invalid,
        "hypothesis": ticket["hypothesis"],
        "acceptance_rule": ticket["acceptance_rule"],
        "completed_at": _now(),
        "frozen_input_identities": identities,
        "raw_evaluation_input": raw,
        "raw_input_identity": raw.get("input_identity") if raw is not None else None,
        "evaluation": evaluation,
        "contamination_reason": contamination_reason,
        "result_ceiling": "observed_only",
        "paper_live_eligible": False,
        "production_impact": {
            "research_only": True,
            "orders_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_levels_changed": False,
            "shared_policy_changed": False,
            "trade_enabled": False,
        },
        "post_run_reflection": {
            "why_result_happened": _why_result_happened(evaluation),
            "failure_mode_audit": ticket["prediction"]["main_failure_modes"],
            "forbidden_near_neighbor_retry": (
                "Do not retune CORRESP subsets, the source date, mapping, H5 horizon, "
                "cash comparator, or 10 bps cost on these consumed outcomes."
            ),
            "new_evidence_required": (
                "Require a separately frozen later complete SEC daily index under the "
                "unchanged policy or a genuinely distinct causal source."
            ),
        },
        "reproduction_command": (
            ".\\.venv\\Scripts\\python.exe -B " + RUNNER_REL.replace("/", "\\")
        ),
        "trade_enabled": False,
        "order_intent_count": 0,
    }


def main() -> int:
    ticket = _read_json(TICKET)
    artifact_handle = None
    try:
        _verify_single_run_state(ticket)
        artifact_handle = _reserve_run_attempt()
        ticket = _revalidate_reserved_run_state()
    except ContaminationError as exc:
        if artifact_handle is not None:
            artifact_handle.close()
        print(
            json.dumps(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "status": "refused",
                    "reason": str(exc),
                    "trade_enabled": False,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2

    identities: dict[str, str] = {}
    raw: dict[str, Any] | None = None
    contamination_reason: str | None = None
    try:
        pool, recipe, _decision, identities = _verify_claim_bound_inputs(ticket)
        codes = [f"US.{row['symbol']}" for row in pool["candidates"]]
        raw = _fetch_bars(codes, recipe)
        evaluation = evaluate_avoid_long_h5(
            raw["rows"],
            candidate_codes=codes,
            cost_bps=float(recipe["round_trip_cost_bps"]),
            expected_session_dates=list(recipe["expected_session_dates"]),
        )
    except Exception as exc:
        contamination_reason = f"{type(exc).__name__}: {exc}"
        evaluation = {
            "candidate_count": 17,
            "usable_security_count": 0,
            "missing_or_error_count": 17,
            "diagnostic_disposition": "invalid_contaminated",
            "scientific_classification": "invalid_contaminated",
            "directional_checks": {},
            "acceptance_checks": {},
            "candidate_outcomes": [],
        }
    status, disposition, evidence_invalid = _status_and_disposition(evaluation)
    payload = _artifact_payload(
        ticket=ticket,
        status=status,
        disposition=disposition,
        evidence_invalid=evidence_invalid,
        identities=identities,
        raw=raw,
        evaluation=evaluation,
        contamination_reason=contamination_reason,
    )
    try:
        _write_reserved_json(artifact_handle, payload)
    finally:
        artifact_handle.close()
    artifact_sha = _sha256(ARTIFACT)
    summary = {
        key: value
        for key, value in evaluation.items()
        if key != "candidate_outcomes"
    }
    persist_self_registered_result(
        REGISTRY,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=ticket["prediction"],
        result={
            "decision": status,
            "artifact": _relative(ARTIFACT),
            "artifact_sha256": artifact_sha,
            "disposition": disposition,
            "artifact_disposition": disposition,
            "evidence_invalid": evidence_invalid,
            "summary": summary,
            "result_ceiling": "observed_only",
            "paper_live_eligible": False,
            "trade_enabled": False,
        },
        status=status,
    )
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": status,
                "disposition": disposition,
                "summary": summary,
                "trade_enabled": False,
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
