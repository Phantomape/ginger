"""exp-20260605-012: Space same-theme activation readiness audit.

This read-only alpha-search audit checks whether the default-off Space
catalyst event-state shadow ledger contains a production-visible official
cohort that can pass the 10-day same-theme replacement-value activation
readiness gate even though the aggregate Space shadow universe currently
does not.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260605-012"
SLUG = "space_same_theme_activation_readiness"
STEM = f"exp_20260605_012_{SLUG}"

LEDGER_JSONL = (
    REPO_ROOT
    / "data"
    / "paper_sleeves"
    / "space_catalyst"
    / "event_state_shadow_ledger.jsonl"
)
SUMMARY_JSON = (
    REPO_ROOT
    / "data"
    / "paper_sleeves"
    / "space_catalyst"
    / "event_state_shadow_summary.json"
)
OBSERVATION_SLOT_SUMMARY_JSON = (
    REPO_ROOT
    / "data"
    / "paper_sleeves"
    / "space_catalyst"
    / "observation_slot_summary.json"
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{SLUG}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

MIN_CLOSED_ROWS = 5
MIN_AVG_SAME_THEME_VALUE = 0.01
MIN_SAME_THEME_WIN_RATE = 0.50
MAX_SINGLE_TICKER_POSITIVE_SHARE = 0.50

OFFICIAL_SOURCE_TYPES = {
    "official_government_release",
    "official_or_primary_release",
    "official_regulatory_release",
}
OFFICIAL_SEMANTIC_BUCKETS = {
    "defense_budget_theme",
    "fundamental_contract_regulatory",
}
COHORT_FIELDS = (
    ("semantic_bucket",),
    ("theme_segment",),
    ("source_type",),
    ("semantic_bucket", "theme_segment"),
    ("semantic_bucket", "source_type"),
    ("source_type", "theme_segment"),
    ("semantic_bucket", "source_type", "theme_segment"),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    experiment_id = str(payload["experiment_id"])
    rows: list[str] = []
    if path.exists():
        with path.open("r", encoding="utf-8-sig") as handle:
            for line in handle:
                raw = line.rstrip("\n")
                if not raw.strip():
                    continue
                try:
                    row = json.loads(raw)
                except json.JSONDecodeError:
                    rows.append(raw)
                    continue
                if isinstance(row, dict) and row.get("experiment_id") == experiment_id:
                    continue
                rows.append(raw)
    rows.append(json.dumps(payload, sort_keys=True))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write("\n".join(rows))
        handle.write("\n")


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: Any, digits: int = 6) -> Any:
    if isinstance(value, (int, float)):
        return round(float(value), digits)
    return value


def _closed_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("event_id") or ""),
        str(row.get("ticker") or "").upper(),
        str(row.get("entry_date") or ""),
    )


def _latest_closed_10d_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        horizon = (row.get("horizons") or {}).get("10d") or {}
        if not row.get("closed_decision") or horizon.get("status") != "mature":
            continue
        cash_pnl = _as_float(horizon.get("cash_relative_pnl"))
        same_theme = _as_float(horizon.get("same_theme_replacement_value"))
        if cash_pnl is None or same_theme is None:
            continue
        key = _closed_key(row)
        previous = latest.get(key)
        if previous is None or str(row.get("asof_date") or "") >= str(
            previous.get("asof_date") or ""
        ):
            latest[key] = row
    return sorted(
        latest.values(),
        key=lambda row: (
            str(row.get("entry_date") or ""),
            str(row.get("event_id") or ""),
            str(row.get("ticker") or ""),
        ),
    )


def _h10(row: dict[str, Any]) -> dict[str, Any]:
    horizon = (row.get("horizons") or {}).get("10d")
    return horizon if isinstance(horizon, dict) else {}


def _is_official_row(row: dict[str, Any]) -> bool:
    source_type = str(row.get("source_type") or "")
    semantic_bucket = str(row.get("semantic_bucket") or "")
    event_fields = row.get("event_fields") if isinstance(row.get("event_fields"), list) else []
    return (
        source_type in OFFICIAL_SOURCE_TYPES
        or semantic_bucket in OFFICIAL_SEMANTIC_BUCKETS
        or "government_space_contract" in event_fields
        or "customer_win" in event_fields
    )


def _positive_concentration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_ticker: dict[str, float] = defaultdict(float)
    for row in rows:
        cash_pnl = _as_float(_h10(row).get("cash_relative_pnl")) or 0.0
        if cash_pnl > 0:
            by_ticker[str(row.get("ticker") or "").upper()] += cash_pnl
    total = sum(by_ticker.values())
    ranked = [
        {"ticker": ticker, "positive_pnl": _round(value, 2), "share": _round(value / total, 6)}
        for ticker, value in sorted(by_ticker.items(), key=lambda item: item[1], reverse=True)
        if total > 0
    ]
    hhi = sum((value / total) ** 2 for value in by_ticker.values()) if total > 0 else 0.0
    return {
        "positive_pnl_total": _round(total, 2),
        "top_ticker": ranked[0]["ticker"] if ranked else None,
        "top_ticker_positive_share": ranked[0]["share"] if ranked else 0.0,
        "positive_pnl_hhi": _round(hhi, 6),
        "by_ticker": ranked,
    }


def _cohort_key(row: dict[str, Any], fields: tuple[str, ...]) -> tuple[Any, ...]:
    return tuple(row.get(field) for field in fields)


def _cohort_label(fields: tuple[str, ...], key: tuple[Any, ...]) -> str:
    return "|".join(f"{field}={value}" for field, value in zip(fields, key))


def _cohort_summary(
    rows: list[dict[str, Any]],
    fields: tuple[str, ...] | None = None,
    key: tuple[Any, ...] | None = None,
) -> dict[str, Any]:
    cash_values = [_as_float(_h10(row).get("cash_relative_pnl")) for row in rows]
    same_theme_values = [
        _as_float(_h10(row).get("same_theme_replacement_value")) for row in rows
    ]
    arkx_values = [_as_float(_h10(row).get("arkx_relative_value")) for row in rows]
    ufo_values = [_as_float(_h10(row).get("ufo_relative_value")) for row in rows]
    qqq_values = [_as_float(_h10(row).get("qqq_relative_value")) for row in rows]
    spy_values = [_as_float(_h10(row).get("spy_relative_value")) for row in rows]
    clean_cash = [value for value in cash_values if value is not None]
    clean_same = [value for value in same_theme_values if value is not None]
    clean_arkx = [value for value in arkx_values if value is not None]
    clean_ufo = [value for value in ufo_values if value is not None]
    clean_qqq = [value for value in qqq_values if value is not None]
    clean_spy = [value for value in spy_values if value is not None]
    tickers = [str(row.get("ticker") or "").upper() for row in rows]
    event_ids = [str(row.get("event_id") or "") for row in rows]
    concentration = _positive_concentration(rows)
    same_win_rate = (
        sum(1 for value in clean_same if value > 0) / len(clean_same)
        if clean_same
        else None
    )
    cash_win_rate = (
        sum(1 for value in clean_cash if value > 0) / len(clean_cash)
        if clean_cash
        else None
    )
    passed = (
        len(rows) >= MIN_CLOSED_ROWS
        and clean_same
        and mean(clean_same) > MIN_AVG_SAME_THEME_VALUE
        and median(clean_same) >= 0
        and same_win_rate is not None
        and same_win_rate >= MIN_SAME_THEME_WIN_RATE
        and clean_cash
        and mean(clean_cash) > 0
        and clean_arkx
        and mean(clean_arkx) > 0
        and clean_ufo
        and mean(clean_ufo) > 0
        and concentration["top_ticker_positive_share"] <= MAX_SINGLE_TICKER_POSITIVE_SHARE
    )
    failed_reasons: list[str] = []
    if len(rows) < MIN_CLOSED_ROWS:
        failed_reasons.append("thin_official_subcohort")
    if not clean_same or mean(clean_same) <= MIN_AVG_SAME_THEME_VALUE:
        failed_reasons.append("same_theme_value_nonpositive")
    if not clean_same or median(clean_same) < 0:
        failed_reasons.append("same_theme_median_negative")
    if same_win_rate is None or same_win_rate < MIN_SAME_THEME_WIN_RATE:
        failed_reasons.append("same_theme_win_rate_below_floor")
    if not clean_cash or mean(clean_cash) <= 0:
        failed_reasons.append("cash_pnl_nonpositive")
    if not clean_arkx or mean(clean_arkx) <= 0:
        failed_reasons.append("arkx_relative_nonpositive")
    if not clean_ufo or mean(clean_ufo) <= 0:
        failed_reasons.append("ufo_relative_nonpositive")
    if concentration["top_ticker_positive_share"] > MAX_SINGLE_TICKER_POSITIVE_SHARE:
        failed_reasons.append("single_ticker_concentration")
    return {
        "fields": list(fields or []),
        "key": list(key or []),
        "label": _cohort_label(fields, key) if fields and key else "overall",
        "closed_10d_rows": len(rows),
        "unique_tickers": len(set(tickers)),
        "unique_events": len(set(event_ids)),
        "ticker_counts": dict(Counter(tickers).most_common()),
        "avg_10d_cash_pnl": _round(mean(clean_cash), 6) if clean_cash else None,
        "median_10d_cash_pnl": _round(median(clean_cash), 6) if clean_cash else None,
        "total_10d_cash_pnl": _round(sum(clean_cash), 6) if clean_cash else 0.0,
        "10d_cash_win_rate": _round(cash_win_rate, 6) if cash_win_rate is not None else None,
        "avg_10d_same_theme_replacement_value": (
            _round(mean(clean_same), 6) if clean_same else None
        ),
        "median_10d_same_theme_replacement_value": (
            _round(median(clean_same), 6) if clean_same else None
        ),
        "total_10d_same_theme_replacement_value": (
            _round(sum(clean_same), 6) if clean_same else 0.0
        ),
        "10d_same_theme_win_rate": (
            _round(same_win_rate, 6) if same_win_rate is not None else None
        ),
        "avg_10d_arkx_relative_value": _round(mean(clean_arkx), 6) if clean_arkx else None,
        "avg_10d_ufo_relative_value": _round(mean(clean_ufo), 6) if clean_ufo else None,
        "avg_10d_qqq_relative_value": _round(mean(clean_qqq), 6) if clean_qqq else None,
        "avg_10d_spy_relative_value": _round(mean(clean_spy), 6) if clean_spy else None,
        "positive_concentration": concentration,
        "passed": bool(passed),
        "failed_reasons": failed_reasons,
    }


def _build_cohorts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cohorts: list[dict[str, Any]] = []
    official_rows = [row for row in rows if _is_official_row(row)]
    for fields in COHORT_FIELDS:
        grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
        for row in official_rows:
            grouped[_cohort_key(row, fields)].append(row)
        for key, cohort_rows in grouped.items():
            cohorts.append(_cohort_summary(cohort_rows, fields=fields, key=key))
    return sorted(
        cohorts,
        key=lambda row: (
            not bool(row["passed"]),
            -int(row["closed_10d_rows"]),
            -float(row.get("avg_10d_same_theme_replacement_value") or -10**9),
            str(row["label"]),
        ),
    )


def _sample_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sample = []
    for row in rows:
        horizon = _h10(row)
        sample.append(
            {
                "asof_date": row.get("asof_date"),
                "entry_date": row.get("entry_date"),
                "event_id": row.get("event_id"),
                "ticker": row.get("ticker"),
                "semantic_bucket": row.get("semantic_bucket"),
                "theme_segment": row.get("theme_segment"),
                "source_type": row.get("source_type"),
                "10d_cash_pnl": horizon.get("cash_relative_pnl"),
                "10d_same_theme_value": horizon.get("same_theme_replacement_value"),
                "10d_arkx_relative_value": horizon.get("arkx_relative_value"),
                "10d_ufo_relative_value": horizon.get("ufo_relative_value"),
            }
        )
    return sample


def _payload() -> dict[str, Any]:
    timestamp = _now()
    raw_rows = _load_jsonl(LEDGER_JSONL)
    summary = _load_json(SUMMARY_JSON)
    observation_summary = _load_json(OBSERVATION_SLOT_SUMMARY_JSON)
    closed_rows = _latest_closed_10d_rows(raw_rows)
    official_rows = [row for row in closed_rows if _is_official_row(row)]
    overall = _cohort_summary(closed_rows)
    official_overall = _cohort_summary(official_rows)
    cohorts = _build_cohorts(closed_rows)
    passing_cohorts = [row for row in cohorts if row["passed"]]
    best_cohort = passing_cohorts[0] if passing_cohorts else None
    summary_gate = summary.get("promotion_gate") or {}
    summary_overall = ((summary.get("aggregate") or {}).get("overall") or {})
    decision = (
        "observed_only_space_same_theme_activation_cohort_found"
        if passing_cohorts
        else "rejected_space_same_theme_activation_readiness"
    )
    status = "observed_only" if passing_cohorts else "rejected"
    activation_blockers = []
    if not passing_cohorts:
        gate4_failed = ["no_official_cohort_passed_same_theme_replacement_gate"]
    else:
        gate4_failed = []
    if summary_gate.get("passed") is not True:
        activation_blockers.append("aggregate_space_promotion_gate_not_passed")
    if observation_summary.get("selected_count", 0) == 0:
        activation_blockers.append("production_observation_slot_has_zero_selected_candidates")
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "lane": "alpha_search",
        "hypothesis": (
            "Official Space catalyst forward rows may contain a production-visible "
            "sub-cohort that passes 10d same-theme replacement value even though "
            "the aggregate Space shadow universe does not."
        ),
        "change_summary": (
            "Read-only activation-readiness audit of official Space closed forward "
            "rows by production-visible cohort; no strategy behavior changed."
        ),
        "change_type": "read_only_activation_readiness_audit",
        "mechanism_family": "pilot_or_sleeve",
        "trial_family": "space_forward_same_theme_activation_readiness",
        "trial_variant_id": "official_cohort_10d_same_theme_scope_v1",
        "single_causal_variable": (
            "space_official_cohort_10d_same_theme_replacement_activation_scope_v1"
        ),
        "changed_variable": (
            "space_official_cohort_10d_same_theme_replacement_activation_scope_v1"
        ),
        "prior_trial_count": 6,
        "nearby_prior_experiments": [
            "exp-20260528-026",
            "exp-20260529-020",
            "exp-20260531-022",
            "exp-20260602-025",
            "exp-20260513-113",
            "exp-20260514-009",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "closed_forward_same_theme_replacement_rows",
        "parameters": {
            "ledger": _repo_rel(LEDGER_JSONL),
            "summary": _repo_rel(SUMMARY_JSON),
            "dedupe_key": ["event_id", "ticker", "entry_date"],
            "horizon": "10d",
            "cohort_fields": [list(fields) for fields in COHORT_FIELDS],
            "min_closed_rows": MIN_CLOSED_ROWS,
            "min_avg_same_theme_value": MIN_AVG_SAME_THEME_VALUE,
            "min_same_theme_win_rate": MIN_SAME_THEME_WIN_RATE,
            "max_single_ticker_positive_share": MAX_SINGLE_TICKER_POSITIVE_SHARE,
            "official_source_types": sorted(OFFICIAL_SOURCE_TYPES),
            "official_semantic_buckets": sorted(OFFICIAL_SEMANTIC_BUCKETS),
        },
        "date_range": {
            "start": min((str(row.get("entry_date")) for row in closed_rows), default=None),
            "end": max((str(row.get("entry_date")) for row in closed_rows), default=None),
            "asof": summary.get("asof_date"),
        },
        "before_metrics": {
            "aggregate_space_shadow_summary": summary_gate,
            "overall_10d_same_theme_value": summary_overall.get("10d_same_theme_value"),
            "overall_10d_cash_pnl": summary_overall.get("10d_cash_pnl"),
        },
        "after_metrics": {
            "overall": overall,
            "official_overall": official_overall,
            "best_passing_cohort": best_cohort,
            "passing_cohort_count": len(passing_cohorts),
        },
        "delta_metrics": {
            "strategy_logic_changed": False,
            "expected_value_score_delta": 0.0,
            "total_pnl_delta": 0.0,
            "deduped_closed_10d_rows": len(closed_rows),
            "official_closed_10d_rows": len(official_rows),
            "passing_cohort_count": len(passing_cohorts),
        },
        "gate1": {
            "passed": True,
            "baseline_artifact": _repo_rel(SUMMARY_JSON),
            "accepted_core_aggregate_ev": 7.8941,
            "accepted_core_aggregate_pnl": 234850.99,
            "summary_promotion_gate": summary_gate,
        },
        "gate2": {
            "passed": bool(closed_rows),
            "required_runtime_fields": [
                "event_state_shadow_ledger[].event_id",
                "event_state_shadow_ledger[].ticker",
                "event_state_shadow_ledger[].entry_date",
                "event_state_shadow_ledger[].source_type",
                "event_state_shadow_ledger[].semantic_bucket",
                "event_state_shadow_ledger[].theme_segment",
                "event_state_shadow_ledger[].horizons.10d.cash_relative_pnl",
                "event_state_shadow_ledger[].horizons.10d.same_theme_replacement_value",
                "event_state_shadow_ledger[].horizons.10d.arkx_relative_value",
                "event_state_shadow_ledger[].horizons.10d.ufo_relative_value",
            ],
            "raw_ledger_rows": len(raw_rows),
            "deduped_closed_10d_rows": len(closed_rows),
            "official_closed_10d_rows": len(official_rows),
            "llm_dependency": "none",
        },
        "gate3": {
            "passed": True,
            "new_core_filter_added": False,
            "core_survival_changed": False,
            "survival_audit": (
                "Read-only forward cohort audit; no entry, filter, ranking, sizing, "
                "exit, or order behavior changed."
            ),
        },
        "gate4": {
            "passed": bool(passing_cohorts),
            "status": status,
            "promotion_grade": False,
            "strategy_behavior_changed": False,
            "failed_reasons": gate4_failed,
            "acceptance_rule": (
                "Observed-only pass requires at least one production-visible "
                "official/primary Space cohort with >=5 closed mature 10d rows, "
                "avg 10d same-theme replacement value > $0.01, median >= 0, "
                "same-theme win rate >= 50%, avg 10d cash PnL > 0, avg 10d "
                "ARKX/UFO relative value > 0, and max single ticker positive "
                "PnL share <= 50%; no live slots or trade adapter may change."
            ),
            "activation_blockers": activation_blockers,
            "passing_cohorts": passing_cohorts,
        },
        "activation_blockers": activation_blockers,
        "cohorts": cohorts,
        "sample_closed_rows": _sample_rows(closed_rows),
        "prediction": {
            "success_probability": 0.24,
            "expected_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "main_failure_modes": [
                "same_theme_value_nonpositive",
                "thin_official_subcohort",
                "single_ticker_concentration",
                "missing_core_replacement_value",
            ],
            "confidence_reason": (
                "The aggregate Space gate already fails same-theme replacement; "
                "defense_budget_theme is near breakeven but sample is thin and "
                "same-theme win rate is only about 50%, so a scoped pass is "
                "possible but not likely."
            ),
            "recorded_at": "2026-06-05T06:12:13+00:00",
        },
        "calibration": {
            "actual_decision": decision,
            "actual_success": 1 if passing_cohorts else 0,
            "predicted_success_probability": 0.24,
            "brier_score": _round((0.24 - (1 if passing_cohorts else 0)) ** 2, 6),
            "predicted_failure_modes": [
                "same_theme_value_nonpositive",
                "thin_official_subcohort",
                "single_ticker_concentration",
                "missing_core_replacement_value",
            ],
            "realized_failure_mode": ";".join(gate4_failed) if gate4_failed else "none",
            "predicted_failure_mode_hit": any(
                reason
                in {
                    "same_theme_value_nonpositive",
                    "thin_official_subcohort",
                    "single_ticker_concentration",
                }
                for cohort in cohorts
                for reason in cohort.get("failed_reasons", [])
            ),
            "surprise_level": "low" if not passing_cohorts else "medium",
        },
        "preflight_questions": {
            "1_alpha_hypothesis": (
                "candidate-pool / pilot-sleeve activation readiness: official Space "
                "forward rows may contain a production-visible sub-cohort whose "
                "10d returns beat the same-theme replacement basket."
            ),
            "2_history_check": (
                "Prior Space work accepted observe-only OHLCV/cost-liquidity "
                "metadata in exp-20260528-026, exp-20260529-020, exp-20260531-022, "
                "and exp-20260602-025, while live Space slots remain zero. Earlier "
                "forward-replacement profiles exp-20260513-113 and exp-20260514-009 "
                "created metadata helpers only, not a live activation."
            ),
            "3_single_causal_variable": (
                "space_official_cohort_10d_same_theme_replacement_activation_scope_v1"
            ),
            "4_acceptance_standard": (
                "Observed-only pass requires at least one official/primary cohort "
                "with >=5 closed mature 10d rows, positive average and non-negative "
                "median same-theme replacement value after a cent-level positivity "
                "floor, same-theme win rate >=50%, positive cash and ARKX/UFO "
                "relative averages, and concentration inside the 50% top-ticker "
                "share guardrail."
            ),
            "5_reproducibility": (
                ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260605_012_space_same_theme_activation_readiness.py"
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": False,
            "default_off_attribution_only": True,
            "trade_enabled": False,
            "live_slots_changed": False,
            "live_slots": 0,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
        },
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "rejection_reason": ";".join(gate4_failed) if gate4_failed else None,
        "next_retry_requires": [
            "more closed official Space forward rows if no cohort passes",
            "positive same-theme replacement value at the cohort level",
            "closed core replacement-value rows before live-slot activation",
            "a separate Gate 1-4 pilot trade-adapter experiment before production orders",
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(LEDGER_JSONL),
            _repo_rel(SUMMARY_JSON),
            _repo_rel(OBSERVATION_SLOT_SUMMARY_JSON),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(TICKET_JSON),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "anti_js": "No JavaScript was used.",
        "summary": (
            "Observed-only Space activation readiness audit found a passing "
            "official same-theme cohort."
            if passing_cohorts
            else "Rejected activation readiness: no production-visible official "
            "Space cohort passed the 10d same-theme replacement-value gate."
        ),
    }


def _build_artifact(payload: dict[str, Any]) -> str:
    top_cohorts = payload["cohorts"][:12]
    rows = [
        "| Cohort | Rows | Avg same-theme | Median same-theme | Same-theme win | Avg cash | Avg ARKX rel | Avg UFO rel | Top ticker share | Verdict |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for cohort in top_cohorts:
        rows.append(
            "| {label} | {count} | ${avg_same:,.2f} | ${median_same:,.2f} | "
            "{same_win:.2%} | ${avg_cash:,.2f} | ${arkx:,.2f} | ${ufo:,.2f} | "
            "{top_share:.2%} | {verdict} |".format(
                label=str(cohort["label"]).replace("|", " / "),
                count=int(cohort["closed_10d_rows"]),
                avg_same=float(cohort.get("avg_10d_same_theme_replacement_value") or 0.0),
                median_same=float(
                    cohort.get("median_10d_same_theme_replacement_value") or 0.0
                ),
                same_win=float(cohort.get("10d_same_theme_win_rate") or 0.0),
                avg_cash=float(cohort.get("avg_10d_cash_pnl") or 0.0),
                arkx=float(cohort.get("avg_10d_arkx_relative_value") or 0.0),
                ufo=float(cohort.get("avg_10d_ufo_relative_value") or 0.0),
                top_share=float(
                    (cohort.get("positive_concentration") or {}).get(
                        "top_ticker_positive_share", 0.0
                    )
                ),
                verdict="pass" if cohort["passed"] else "fail",
            )
        )
    return "\n".join(
        [
            "# exp-20260605-012 Space Same-Theme Activation Readiness",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "This is a read-only activation-readiness audit. It does not enable Space production slots.",
            "",
            "## Preflight",
            "",
            f"- Hypothesis: {payload['hypothesis']}",
            f"- Single causal variable: `{payload['single_causal_variable']}`",
            f"- Prior experiments: `{', '.join(payload['nearby_prior_experiments'])}`",
            f"- Repro command: `{payload['preflight_questions']['5_reproducibility']}`",
            "",
            "## Baseline Gate",
            "",
            f"- Current aggregate Space promotion gate passed: `{payload['gate1']['summary_promotion_gate'].get('passed')}`",
            f"- Gate reason: `{payload['gate1']['summary_promotion_gate'].get('reason')}`",
            f"- Deduped mature 10d closed rows: `{payload['gate2']['deduped_closed_10d_rows']}`",
            f"- Official/primary mature 10d rows: `{payload['gate2']['official_closed_10d_rows']}`",
            "",
            "## Official Cohort Readout",
            "",
            *rows,
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "No shared policy, backtester adapter, run adapter, live slot, ranking, sizing, exit, LLM/news, or order behavior changed.",
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def _build_card(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "---",
            f'experiment_id: "{EXPERIMENT_ID}"',
            f'status: "{payload["status"]}"',
            f'lane: "{payload["lane"]}"',
            f'change_type: "{payload["change_type"]}"',
            f'mechanism_family: "{payload["mechanism_family"]}"',
            f'trial_family: "{payload["trial_family"]}"',
            f'trial_variant_id: "{payload["trial_variant_id"]}"',
            f'changed_variable: "{payload["changed_variable"]}"',
            f'new_evidence_type: "{payload["new_evidence_type"]}"',
            f'completed_at: "{payload["timestamp"]}"',
            "tags:",
            '  - "alpha_search"',
            '  - "read_only_activation_readiness_audit"',
            '  - "space_catalyst"',
            "---",
            "",
            f"# Experiment Card: {EXPERIMENT_ID}",
            "",
            "## Summary",
            "",
            payload["summary"],
            "",
            "## Closeout",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Passing cohorts: `{payload['delta_metrics']['passing_cohort_count']}`",
            f"- Deduped mature 10d rows: `{payload['gate2']['deduped_closed_10d_rows']}`",
            f"- Official mature 10d rows: `{payload['gate2']['official_closed_10d_rows']}`",
            f"- Result JSON: `{_repo_rel(OUT_JSON)}`",
            f"- Artifact: `{_repo_rel(ARTIFACT_MD)}`",
            "",
        ]
    )


def _record_for_jsonl(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": payload["experiment_id"],
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "hypothesis": payload["hypothesis"],
        "change_summary": payload["change_summary"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "parameters": payload["parameters"],
        "date_range": payload["date_range"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": {
            "passed": payload["gate4"]["passed"],
            "failed_reasons": payload["gate4"]["failed_reasons"],
            "strategy_behavior_changed": False,
            "promotion_grade": False,
            "activation_blockers": payload["gate4"]["activation_blockers"],
        },
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
        "rejection_reason": payload["rejection_reason"],
        "next_retry_requires": payload["next_retry_requires"],
        "related_files": payload["related_files"],
        "anti_js": payload["anti_js"],
        "notes": payload["summary"],
    }


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _load_json(TICKET_JSON)
    ticket["status"] = payload["status"]
    ticket["completed_at"] = payload["timestamp"]
    ticket["result"] = {
        "decision": payload["decision"],
        "json": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "artifact": _repo_rel(ARTIFACT_MD),
        "passed": payload["gate4"]["passed"],
        "failed_reasons": payload["gate4"]["failed_reasons"],
        "passing_cohort_count": payload["delta_metrics"]["passing_cohort_count"],
    }
    _write_json(TICKET_JSON, ticket)


def _update_manifest(payload: dict[str, Any]) -> None:
    manifest = _load_json(MANIFEST_JSON)
    manifest["completed_at"] = payload["timestamp"]
    manifest["result_files"] = {
        "json": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "artifact": _repo_rel(ARTIFACT_MD),
    }
    _write_json(MANIFEST_JSON, manifest)


def _update_registry(payload: dict[str, Any]) -> None:
    registry = _load_json(REGISTRY_JSON)
    experiments = registry.get("experiments")
    if not isinstance(experiments, list):
        return
    for experiment in experiments:
        if isinstance(experiment, dict) and experiment.get("experiment_id") == EXPERIMENT_ID:
            experiment["status"] = payload["status"]
            experiment["completed_at"] = payload["timestamp"]
            experiment["result"] = {
                "decision": payload["decision"],
                "json": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "card": _repo_rel(CARD_MD),
                "artifact": _repo_rel(ARTIFACT_MD),
                "passed": payload["gate4"]["passed"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "passing_cohort_count": payload["delta_metrics"]["passing_cohort_count"],
            }
            break
    registry["updated_at"] = payload["timestamp"]
    _write_json(REGISTRY_JSON, registry)


def _persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_text(CARD_MD, _build_card(payload))
    _write_text(ARTIFACT_MD, _build_artifact(payload))
    _update_ticket(payload)
    _update_manifest(payload)
    _update_registry(payload)
    _upsert_jsonl(EXPERIMENT_LOG, _record_for_jsonl(payload))


def main() -> int:
    payload = _payload()
    _persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "passed": payload["gate4"]["passed"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "deduped_closed_10d_rows": payload["gate2"]["deduped_closed_10d_rows"],
                "official_closed_10d_rows": payload["gate2"]["official_closed_10d_rows"],
                "passing_cohort_count": payload["delta_metrics"]["passing_cohort_count"],
                "json": _repo_rel(OUT_JSON),
                "artifact": _repo_rel(ARTIFACT_MD),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
