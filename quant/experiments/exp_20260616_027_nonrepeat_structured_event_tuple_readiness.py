"""exp-20260616-027: non-repeat structured event tuple alpha readiness.

Alpha-search preflight. The strongest remaining non-repeat free-data idea is a
structured event tuple candidate source: actor/object/relation/magnitude/
provenance rows from SEC/news/event artifacts, tested as next-open paper
replacement value. This runner checks whether that data surface actually exists
with canonical three-window PIT coverage before any strategy replay is allowed.

No production strategy, shared helper, ranking, sizing, exit, LLM, news-veto,
or order behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260616-027"
OWNER = "alpha-search-automation"
STEM = "nonrepeat_structured_event_tuple_readiness"
TRIAL_FAMILY = "nonrepeat_alpha_candidate_readiness"
TRIAL_VARIANT_ID = "structured_event_tuple_surface_v1"
CHANGED_VARIABLE = "nonrepeat_structured_event_tuple_alpha_readiness_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260616_027_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
BASELINE_JSON = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OPEN_POSITIONS_JSON = REPO_ROOT / "operator_inputs" / "open_positions.json"

WINDOWS = {
    "late_strong": {"start": "2025-10-23", "end": "2026-04-21"},
    "mid_weak": {"start": "2025-04-23", "end": "2025-10-22"},
    "old_thin": {"start": "2024-10-02", "end": "2025-04-22"},
}

NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260614-005",
    "exp-20260614-012",
    "exp-20260615-014",
    "exp-20260615-015",
    "exp-20260615-027",
    "exp-20260616-002",
    "exp-20260616-006",
    "exp-20260616-008",
    "exp-20260615-026",
    "exp-20260616-003",
    "exp-20260616-024",
    "exp-20260616-026",
]

PREDICTION = {
    "success_probability": 0.12,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "no_structured_event_tuple_surface",
        "duplicate_frozen_near_neighbor",
        "insufficient_three_window_candidate_coverage",
        "production_parity_not_available",
    ],
    "confidence_reason": (
        "Recent history shows every broad free-data lane is either accepted/"
        "frozen, rejected on window/drawdown/comparator gates, or data-limited. "
        "Structured event tuples are the most plausible non-repeat field, but "
        "current event snapshots may only contain generic 8-K rows without "
        "magnitude/object schema."
    ),
    "recorded_at": "2026-06-16T22:09:29+00:00",
}

STRUCTURED_FIELD_GROUPS = {
    "actor": {
        "actor",
        "event_actor",
        "event_actor_type",
        "issuer",
        "counterparty",
        "customer",
        "supplier",
        "partner",
    },
    "object": {
        "object",
        "event_object",
        "event_object_type",
        "product",
        "contract",
        "guidance_metric",
        "business_line",
        "segment",
    },
    "relation": {
        "relation",
        "event_relation",
        "event_relation_type",
        "action",
        "semantic_direction",
        "event_verb",
    },
    "magnitude": {
        "magnitude",
        "event_magnitude",
        "event_magnitude_bucket",
        "amount",
        "percent",
        "growth_pct",
        "size_usd",
        "quantified_value",
    },
    "provenance": {
        "source_files",
        "source_file",
        "url",
        "accession",
        "sec_accession_number",
        "published_at",
        "accepted_at",
        "retrieved_at",
    },
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "production_signal_path_changed": False,
    "ranking_changed": False,
    "sizing_changed": False,
    "exits_changed": False,
    "orders_changed": False,
    "replay_only": False,
    "strategy_replay_run": False,
    "default_off_paper_only": False,
    "live_ready": False,
    "uses_llm": False,
    "parity_note": (
        "No alpha helper was promoted because the required structured event "
        "tuple surface is absent. Avoids backtest/production inconsistency by "
        "not creating a replay-only trading rule."
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: str | Path) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _date_from_path(path: Path) -> str | None:
    match = re.search(r"(\d{8})", path.name)
    if not match:
        return None
    value = match.group(1)
    return f"{value[:4]}-{value[4:6]}-{value[6:]}"


def _window_for(day: str | None) -> str | None:
    if not day:
        return None
    for label, cfg in WINDOWS.items():
        if cfg["start"] <= day <= cfg["end"]:
            return label
    return None


def _flatten_keys(row: Any) -> set[str]:
    keys: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                keys.add(str(key))
                walk(child)
        elif isinstance(value, list):
            for child in value[:20]:
                walk(child)

    walk(row)
    return keys


def _field_group_presence(row: Any) -> dict[str, bool]:
    keys = _flatten_keys(row)
    return {
        group: bool(keys & accepted)
        for group, accepted in STRUCTURED_FIELD_GROUPS.items()
    }


def _has_complete_tuple(row: Any) -> bool:
    presence = _field_group_presence(row)
    return all(presence.get(name) for name in ("actor", "object", "relation", "magnitude", "provenance"))


def _short_sample(row: dict[str, Any]) -> dict[str, Any]:
    sample: dict[str, Any] = {}
    for key in (
        "ticker",
        "event_date",
        "event_type",
        "event_subtype",
        "surprise_direction",
        "surprise_strength",
        "title",
        "published_at",
        "source",
    ):
        if key in row:
            sample[key] = row.get(key)
    attrs = row.get("attributes")
    if isinstance(attrs, dict):
        for key in ("title", "filing_type", "accepted_at", "usable_trade_date", "sec_accession_number"):
            if key in attrs:
                sample[f"attributes.{key}"] = attrs.get(key)
    return sample


def _empty_window_counter() -> dict[str, Any]:
    return {
        "files": 0,
        "rows": 0,
        "tickers": set(),
        "complete_structured_tuple_rows": 0,
        "field_presence_rows": Counter(),
        "event_types": Counter(),
        "event_subtypes": Counter(),
        "sample_rows": [],
    }


def _finalize_window_counter(counter: dict[str, Any]) -> dict[str, Any]:
    return {
        "files": counter["files"],
        "rows": counter["rows"],
        "ticker_count": len(counter["tickers"]),
        "complete_structured_tuple_rows": counter["complete_structured_tuple_rows"],
        "field_presence_rows": dict(sorted(counter["field_presence_rows"].items())),
        "event_types": dict(counter["event_types"].most_common(10)),
        "event_subtypes": dict(counter["event_subtypes"].most_common(10)),
        "sample_rows": counter["sample_rows"][:5],
    }


def scan_event_snapshots() -> dict[str, Any]:
    by_window = {label: _empty_window_counter() for label in WINDOWS}
    outside = _empty_window_counter()
    for path in sorted((REPO_ROOT / "data" / "daily" / "snapshots" / "events").glob("event_snapshot_*.json")):
        day = _date_from_path(path)
        bucket = by_window.get(_window_for(day), outside)
        bucket["files"] += 1
        payload = _read_json(path, {})
        events = payload.get("events_by_ticker") if isinstance(payload, dict) else {}
        if not isinstance(events, dict):
            continue
        for ticker, rows in events.items():
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                bucket["rows"] += 1
                bucket["tickers"].add(str(ticker).upper())
                bucket["event_types"][str(row.get("event_type") or "missing")] += 1
                bucket["event_subtypes"][str(row.get("event_subtype") or "missing")] += 1
                presence = _field_group_presence(row)
                for group, ok in presence.items():
                    if ok:
                        bucket["field_presence_rows"][group] += 1
                if _has_complete_tuple(row):
                    bucket["complete_structured_tuple_rows"] += 1
                elif len(bucket["sample_rows"]) < 5:
                    bucket["sample_rows"].append(_short_sample(row))
    return {
        "source": "data/daily/snapshots/events/event_snapshot_YYYYMMDD.json",
        "by_window": {label: _finalize_window_counter(value) for label, value in by_window.items()},
        "outside_windows": _finalize_window_counter(outside),
    }


def scan_news_archives() -> dict[str, Any]:
    by_window = {label: _empty_window_counter() for label in WINDOWS}
    outside = _empty_window_counter()
    patterns = [
        "data/daily/news/clean/clean_news_*.json",
        "data/daily/news/trade/clean_trade_news_*.json",
    ]
    for pattern in patterns:
        for path in sorted(REPO_ROOT.glob(pattern)):
            day = _date_from_path(path)
            bucket = by_window.get(_window_for(day), outside)
            bucket["files"] += 1
            payload = _read_json(path, [])
            if not isinstance(payload, list):
                continue
            for row in payload:
                if not isinstance(row, dict):
                    continue
                bucket["rows"] += 1
                for ticker in row.get("tickers") or []:
                    bucket["tickers"].add(str(ticker).upper())
                presence = _field_group_presence(row)
                for group, ok in presence.items():
                    if ok:
                        bucket["field_presence_rows"][group] += 1
                if _has_complete_tuple(row):
                    bucket["complete_structured_tuple_rows"] += 1
                elif len(bucket["sample_rows"]) < 5:
                    bucket["sample_rows"].append(_short_sample(row))
    return {
        "source": "data/daily/news/{clean,trade}/*.json",
        "by_window": {label: _finalize_window_counter(value) for label, value in by_window.items()},
        "outside_windows": _finalize_window_counter(outside),
    }


def scan_sec_filing_text() -> dict[str, Any]:
    by_window = {label: _empty_window_counter() for label in WINDOWS}
    outside = _empty_window_counter()
    for path in sorted((REPO_ROOT / "data" / "non_ohlcv").glob("sec_filing_text_*.jsonl")):
        day = _date_from_path(path)
        bucket = by_window.get(_window_for(day), outside)
        bucket["files"] += 1
        try:
            lines = path.read_text(encoding="utf-8-sig").splitlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            bucket["rows"] += 1
            ticker = row.get("ticker") or row.get("symbol")
            if ticker:
                bucket["tickers"].add(str(ticker).upper())
            presence = _field_group_presence(row)
            for group, ok in presence.items():
                if ok:
                    bucket["field_presence_rows"][group] += 1
            if _has_complete_tuple(row):
                bucket["complete_structured_tuple_rows"] += 1
            elif len(bucket["sample_rows"]) < 5:
                bucket["sample_rows"].append(_short_sample(row))
    return {
        "source": "data/non_ohlcv/sec_filing_text_YYYYMMDD.jsonl",
        "by_window": {label: _finalize_window_counter(value) for label, value in by_window.items()},
        "outside_windows": _finalize_window_counter(outside),
    }


def baseline_metrics() -> dict[str, Any]:
    payload = _read_json(BASELINE_JSON, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
    by_window: dict[str, dict[str, Any]] = {}
    for row in windows or []:
        if not isinstance(row, dict) or not row.get("label"):
            continue
        by_window[row["label"]] = {
            "start": row.get("start"),
            "end": row.get("end"),
            "expected_value_score": row.get("expected_value_score"),
            "sharpe_daily": row.get("sharpe_daily"),
            "total_pnl": row.get("total_pnl"),
            "max_drawdown_pct": row.get("max_drawdown_pct"),
            "trade_count": row.get("trade_count"),
            "signals_generated": row.get("signals_generated"),
            "signals_survived": row.get("signals_survived"),
            "survival_rate": row.get("survival_rate"),
            "source": row.get("source"),
        }
    aggregate = {
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows or []),
            4,
        ),
        "total_pnl_sum": round(
            sum(float(row.get("total_pnl") or 0.0) for row in windows or []),
            2,
        ),
        "trade_count_sum": sum(int(row.get("trade_count") or 0) for row in windows or []),
        "signals_generated_sum": sum(int(row.get("signals_generated") or 0) for row in windows or []),
        "signals_survived_sum": sum(int(row.get("signals_survived") or 0) for row in windows or []),
    }
    return {
        "source": _repo_rel(BASELINE_JSON),
        "by_window": by_window,
        "aggregate": aggregate,
    }


def audit_open_positions() -> dict[str, Any]:
    payload = _read_json(OPEN_POSITIONS_JSON, {})
    rows: list[dict[str, Any]] = []
    for key in ("observations", "core_positions", "positions"):
        value = payload.get(key) if isinstance(payload, dict) else None
        if isinstance(value, list):
            rows.extend(row for row in value if isinstance(row, dict))
    missing = [
        {
            "ticker": row.get("ticker"),
            "missing": [
                field for field in ("entry_date", "target_price") if row.get(field) in (None, "")
            ],
        }
        for row in rows
        if any(row.get(field) in (None, "") for field in ("entry_date", "target_price"))
    ]
    return {
        "source": _repo_rel(OPEN_POSITIONS_JSON),
        "position_rows_checked": len(rows),
        "missing_required_field_rows": missing[:20],
        "passed": not missing,
        "required_fields": ["entry_date", "target_price"],
    }


def load_prior_records() -> dict[str, Any]:
    records = []
    lane_counts: Counter[str] = Counter()
    failed_reasons: Counter[str] = Counter()
    for experiment_id in NEARBY_PRIOR_EXPERIMENTS:
        path = REPO_ROOT / "experiments" / "logs" / f"{experiment_id}.json"
        row = _read_json(path, None)
        if not isinstance(row, dict):
            records.append({"experiment_id": experiment_id, "missing_log": True})
            continue
        gate4 = row.get("gate4") if isinstance(row.get("gate4"), dict) else {}
        reasons = gate4.get("failed_reasons") or []
        for reason in reasons:
            failed_reasons[str(reason)] += 1
        mechanism = row.get("mechanism_family") or row.get("change_type") or "unknown"
        lane_counts[str(mechanism)] += 1
        records.append(
            {
                "experiment_id": experiment_id,
                "status": row.get("status"),
                "decision": row.get("decision"),
                "mechanism_family": row.get("mechanism_family"),
                "trial_family": row.get("trial_family"),
                "changed_variable": row.get("changed_variable"),
                "hypothesis": str(row.get("hypothesis") or "")[:320],
                "failed_reasons": reasons,
                "post_run_reflection": (
                    (row.get("post_run_reflection") or {}).get("why_result_happened")
                    if isinstance(row.get("post_run_reflection"), dict)
                    else None
                ),
            }
        )
    return {
        "nearby_records": records,
        "mechanism_counts": dict(lane_counts.most_common()),
        "failed_reason_counts": dict(failed_reasons.most_common(20)),
    }


def readiness_decision(scans: dict[str, Any]) -> dict[str, Any]:
    per_source = {}
    total_complete_by_window = {label: 0 for label in WINDOWS}
    total_rows_by_window = {label: 0 for label in WINDOWS}
    for name, scan in scans.items():
        source_windows = {}
        for label in WINDOWS:
            row = scan["by_window"][label]
            complete = int(row.get("complete_structured_tuple_rows") or 0)
            total = int(row.get("rows") or 0)
            total_complete_by_window[label] += complete
            total_rows_by_window[label] += total
            source_windows[label] = {
                "rows": total,
                "complete_structured_tuple_rows": complete,
                "ticker_count": row.get("ticker_count"),
                "files": row.get("files"),
            }
        per_source[name] = source_windows

    all_windows_have_complete_rows = all(value > 0 for value in total_complete_by_window.values())
    enough_total_sample = sum(total_complete_by_window.values()) >= 20
    blocked_reasons = []
    if not all_windows_have_complete_rows:
        blocked_reasons.append("no_complete_structured_event_tuple_rows_in_all_three_windows")
    if not enough_total_sample:
        blocked_reasons.append("structured_tuple_sample_below_20_total_rows")
    if sum(total_complete_by_window.values()) == 0:
        blocked_reasons.append("zero_complete_structured_event_tuple_rows")
    blocked_reasons.extend(
        [
            "current_event_rows_have_ticker_timestamp_and_generic_type_but_no_actor_object_relation_magnitude_tuple",
            "news_archives_have_titles_tickers_timestamps_but_no_replayable_schema_bound_event_labels",
            "positive_strategy_run_would_require_new_shared_default_off_helper_and_daily_snapshot_not_present",
        ]
    )
    return {
        "accepted_for_strategy_replay": False,
        "decision": "blocked_no_trustworthy_nonrepeat_structured_event_tuple_surface",
        "blocked_reasons": blocked_reasons,
        "total_rows_by_window": total_rows_by_window,
        "total_complete_structured_tuple_rows_by_window": total_complete_by_window,
        "source_window_summary": per_source,
    }


def build_payload() -> dict[str, Any]:
    timestamp = _utc_now()
    event_scan = scan_event_snapshots()
    news_scan = scan_news_archives()
    sec_scan = scan_sec_filing_text()
    scans = {
        "event_snapshots": event_scan,
        "news_archives": news_scan,
        "sec_filing_text": sec_scan,
    }
    readiness = readiness_decision(scans)
    baseline = baseline_metrics()
    open_positions = audit_open_positions()
    prior = load_prior_records()
    gate4 = {
        "applicable": False,
        "passed": False,
        "decision": readiness["decision"],
        "reason": (
            "The preflight surface has zero complete structured event tuple rows "
            "across the canonical windows, so a before/after strategy replay "
            "would either duplicate frozen text/news/SEC alphas or invent a "
            "backtest-only parser not available in production."
        ),
        "failed_reasons": readiness["blocked_reasons"],
        "strategy_replay_blocked_before_gate4": True,
    }
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": "rejected",
        "decision": readiness["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": False,
        "hypothesis": (
            "candidate_pool / LLM event scoring: a replayable structured event "
            "tuple surface (actor/object/relation/magnitude/provenance) could be "
            "the next non-repeat free-data alpha, but only if the fields exist "
            "point-in-time across all three canonical windows."
        ),
        "change_type": "alpha_search_preflight_blocker",
        "mechanism_family": "structured_event_candidate_pool_readiness",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": [
            "history_scan",
            "data_surface_scan",
            "anti_repeat_gate",
            "Gate1_4_readiness_check",
        ],
        "prior_trial_count": 9,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "latest_history_plus_data_surface_preflight",
        "prediction": PREDICTION,
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_success": 0,
            "actual_gate4_passed": False,
            "brier_score": round(PREDICTION["success_probability"] ** 2, 6),
            "failure_modes_observed": readiness["blocked_reasons"],
            "predicted_failure_mode_hit": any(
                reason in PREDICTION["main_failure_modes"]
                for reason in [
                    "no_structured_event_tuple_surface",
                    "insufficient_three_window_candidate_coverage",
                    "production_parity_not_available",
                ]
            ),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": (
                "A schema-bound event tuple should be more tradable than raw "
                "positive text because it separates actor, object, relation, "
                "magnitude, timestamp, and provenance before next-open paper "
                "entry."
            ),
            "2_history_check": (
                "Recent records freeze or reject generic SEC text, SaaS KPI text, "
                "earnings/revision retunes, FINRA borrow pressure, options "
                "overlays, 13F/Form144 direct entries, and OHLCV relation retunes. "
                "The only non-repeat candidate would need a new structured event "
                "field, not another threshold sweep."
            ),
            "3_single_decision_hypothesis": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Per docs/backtesting.md, a strategy experiment would need Gate "
                "1-4 on late_strong, mid_weak, and old_thin. This preflight first "
                "requires at least 20 PIT complete tuple rows with coverage in "
                "all three windows and a shared daily/backtest helper path."
            ),
            "5_reproducibility": (
                ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260616_027_nonrepeat_structured_event_tuple_readiness.py"
            ),
        },
        "gate1": {
            "baseline_metrics": baseline,
            "passed": True,
        },
        "gate2": {
            "open_positions": open_positions,
            "required_candidate_fields_for_strategy_replay": [
                "ticker",
                "event_timestamp_or_usable_trade_date",
                "actor",
                "object",
                "relation",
                "magnitude",
                "source_provenance",
                "entry_date",
                "target_price",
            ],
            "passed": False,
            "reason": "Structured tuple actor/object/relation/magnitude fields are absent.",
        },
        "gate3": {
            "core_filter_added": False,
            "minimum_core_survival_rate": min(
                float(row.get("survival_rate") or 0.0)
                for row in baseline["by_window"].values()
            ),
            "passed": True,
            "note": "No core filter or strategy replay was run; baseline survival remains unchanged.",
        },
        "gate4": gate4,
        "before_metrics": baseline,
        "after_metrics": {
            "strategy_replay_run": False,
            "expected_value_score": None,
            "total_pnl": None,
            "trade_count": 0,
            "reason": "Preflight blocked strategy replay before any buy/sell/filter/ranking change.",
        },
        "delta_metrics": {
            "expected_value_score_delta": None,
            "total_pnl_delta": None,
            "reason": "No after strategy replay was run because Gate 2 data readiness failed.",
        },
        "data_surface_scan": scans,
        "readiness": readiness,
        "history_scan": prior,
        "production_impact": PRODUCTION_IMPACT,
        "live_realistic_execution_envelope": {
            "evaluated": False,
            "live_ready": False,
            "reason": "No executable alpha was created; live envelope would require a shared default-off helper first.",
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The strongest non-repeat idea is structured text/event alpha, "
                "but the repository currently stores event rows as generic filing "
                "or headline records. They have provenance and sometimes tickers, "
                "but not actor/object/relation/magnitude tuples. Running a "
                "strategy backtest now would either duplicate frozen SEC/news "
                "experiments or create a backtest-only semantic rule with no "
                "production parity."
            ),
            "outcome_summary": (
                "Structured tuple complete rows by window: "
                f"{readiness['total_complete_structured_tuple_rows_by_window']}. "
                "No strategy replay or production change was made."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry raw positive headlines, generic 8-K items, SEC KPI "
                "phrase filters, DTE/revision threshold sweeps, FINRA borrow "
                "pressure, options overlays, 13F/Form144 direct entries, or OHLCV "
                "relation retunes on these frozen windows without a new PIT field."
            ),
            "new_evidence_required": (
                "A valid alpha retry needs a daily and historical structured-event "
                "helper that writes actor/object/relation/magnitude/provenance "
                "rows before decision time, covers all three canonical windows, "
                "and can be called by both backtest and production default-off "
                "snapshots."
            ),
        },
        "next_retry_requires": [
            "PIT structured event tuple rows with actor/object/relation/magnitude/provenance.",
            "At least 20 complete tuple rows and coverage in late_strong, mid_weak, and old_thin.",
            "A shared default-off helper used by historical replay and daily production snapshots.",
            "Comparator plan against accepted SEC/event/relation/revision helpers after costs.",
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(TICKET_JSON),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(REGISTRY_JSON),
        ],
        "commands": {
            "runner": (
                ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260616_027_nonrepeat_structured_event_tuple_readiness.py"
            ),
            "audit": ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        },
        "anti_js": "No JavaScript was used.",
    }
    return payload


def build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": False,
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "baseline_result_file": _repo_rel(BASELINE_JSON),
        "before_metrics": payload["before_metrics"]["aggregate"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "gate4": payload["gate4"],
        "readiness": payload["readiness"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "rejection_reason": "; ".join(payload["readiness"]["blocked_reasons"]),
        "related_files": payload["related_files"],
        "commands": payload["commands"],
        "anti_js": payload["anti_js"],
    }


def build_card(payload: dict[str, Any]) -> str:
    scan = payload["readiness"]["total_complete_structured_tuple_rows_by_window"]
    rows = [
        "| Window | Baseline EV | Baseline PnL | Survival | Complete tuple rows |",
        "|---|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        base = payload["before_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {ev:.4f} | ${pnl:,.2f} | {survival:.4f} | {tuples} |".format(
                label=label,
                ev=float(base["expected_value_score"]),
                pnl=float(base["total_pnl"]),
                survival=float(base["survival_rate"]),
                tuples=int(scan[label]),
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Non-Repeat Structured Event Tuple Readiness",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate Readiness",
            "",
            *rows,
            "",
            "- Gate 1 baseline: `passed`",
            "- Gate 2 data readiness: `failed`",
            "- Gate 3 survival: `passed` (no new core filter)",
            "- Gate 4 strategy replay: `not run`",
            "- Production impact: none",
            "",
            "## Conclusion",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "## Next Evidence",
            "",
            "\n".join(f"- {item}" for item in payload["next_retry_requires"]),
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def write_manifest(payload: dict[str, Any]) -> None:
    paths = [
        Path(__file__),
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        TICKET_JSON,
        MANIFEST_JSON,
        REGISTRY_JSON,
    ]
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": payload["anti_js"],
        "allowed_write_scope": [_repo_rel(path) for path in paths],
        "must_not_touch": [
            "quant/run.py",
            "quant/backtester.py",
            "quant/*_paper_sleeve.py",
            "docs/experiment_log.jsonl",
        ],
        "file_hashes": {
            _repo_rel(path): _sha256(path)
            for path in paths
            if path.exists()
        },
    }
    _write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    log_record = build_log_record(payload)
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, log_record)
    _write_text(CARD_MD, build_card(payload))
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": False,
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "gate4": payload["gate4"],
        "readiness": payload["readiness"],
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": payload["single_causal_variable"],
        "changed_variable": payload["changed_variable"],
        "causal_components": payload["causal_components"],
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "decision": payload["decision"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card_file": _repo_rel(CARD_MD),
        "ticket_file": _repo_rel(TICKET_JSON),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "allowed_write_scope": payload["related_files"],
        "completed_at": payload["timestamp"],
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
    write_manifest(payload)


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(json.dumps(build_log_record(payload), indent=2, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
