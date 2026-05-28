"""exp-20260528-005: join old alpha score onto expectation watchlist rows.

Observed-only measurement repair. This script does not alter signal
generation, ranking, sizing, exits, LLM/news, paper sleeves, or orders.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260528-005"
STEM = "expectation_watchlist_old_alpha_score_join"
MECHANISM_FAMILY = "expectation_residual_leadership"
TRIAL_FAMILY = "expectation_ranking_replacement_measurement_repair"
CHANGED_VARIABLE = "old_alpha_score_join_v1"

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS_DIR = Path(__file__).resolve().parent
QUANT_DIR = REPO_ROOT / "quant"
for path in (EXPERIMENTS_DIR, QUANT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from cross_sectional_ranking_surface import build_cross_sectional_ranking_surface  # noqa: E402
from daily_context_archive import (  # noqa: E402
    build_breadth_context,
    build_earnings_estimate_revision_context,
    build_theme_density_context,
)
from exp_20260525_017_expectation_residual_leadership_attribution import (  # noqa: E402
    FORWARD_HORIZONS,
    PAPER_NOTIONAL_USD,
    load_candidates,
)
from exp_20260526_030_expectation_direction_untried_ideas_suite import (  # noqa: E402
    ANTI_JS,
    BASELINE,
    build_context,
    bucket_summary,
    expectation_residual_component_score,
    field_coverage,
    _float,
)


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
DOC_LOG = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOCS_TICKET = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_ARTIFACT = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
EXPERIMENT_REGISTRY = REPO_ROOT / "docs" / "experiment_registry.json"

RANK_BUCKET_ORDER = [
    "top_decile",
    "top_quartile",
    "upper_mid",
    "lower_mid",
    "bottom_quartile",
    "missing_score",
]
MIN_OLD_ALPHA_SCORE_ROWS = 100
MIN_PRIMARY_JOINED_ROWS = 30
MIN_JOIN_COVERAGE_RATIO = 0.80

NEARBY_PRIORS = [
    {
        "experiment_id": "exp-20260526-033",
        "finding": "Ranking replacement probe was blocked because old_alpha_score_rows was 0.",
    },
    {
        "experiment_id": "exp-20260525-034",
        "finding": "PIT expectation watchlist rows exist with feature_context_date and forward outcomes.",
    },
    {
        "experiment_id": "exp-20260524-012",
        "finding": "Entry-day ranking attribution can rebuild alpha_score from point-in-time OHLCV features.",
    },
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00",
        "Z",
    )


def _repo_rel(path: Path | str) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, Path):
        return _repo_rel(value)
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    compact = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                rows.append(line)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(compact)
                    replaced = True
                continue
            rows.append(line)
    if not replaced:
        rows.append(compact)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _rank_bucket(rank_pct: float | None) -> str:
    if rank_pct is None:
        return "missing_score"
    if rank_pct <= 0.10:
        return "top_decile"
    if rank_pct <= 0.25:
        return "top_quartile"
    if rank_pct <= 0.50:
        return "upper_mid"
    if rank_pct <= 0.75:
        return "lower_mid"
    return "bottom_quartile"


def build_old_alpha_score_index(
    features_by_date: dict[str, dict[str, dict[str, Any]]],
) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[str, Any], dict[str, Any]]:
    rank_index: dict[tuple[str, str], dict[str, Any]] = {}
    date_summaries: dict[str, Any] = {}
    failures: dict[str, Any] = {}

    for feature_date, features in sorted(features_by_date.items()):
        try:
            breadth = build_breadth_context(features)
            theme_density = build_theme_density_context(features)
            expectation_context = build_earnings_estimate_revision_context(features)
            surface = build_cross_sectional_ranking_surface(
                features,
                breadth_context=breadth,
                theme_density_context=theme_density,
                expectation_context=expectation_context,
            )
        except Exception as exc:  # pragma: no cover - diagnostic surface only
            failures[feature_date] = {
                "error_type": type(exc).__name__,
                "message": str(exc),
            }
            continue

        ranked_rows = surface.get("rows") or []
        universe_count = len(ranked_rows)
        date_summaries[feature_date] = {
            "feature_ticker_count": len(features),
            "ranking_universe_count": universe_count,
            "distribution": surface.get("distribution") or {},
        }
        for idx, row in enumerate(ranked_rows):
            ticker = str(row.get("ticker") or "").upper()
            if not ticker:
                continue
            rank_pct = (idx + 1) / universe_count if universe_count else None
            rank_index[(feature_date, ticker)] = {
                "old_alpha_score": row.get("alpha_score"),
                "old_alpha_score_components": row.get("components"),
                "old_alpha_score_rank": idx + 1,
                "old_alpha_score_rank_pct": round(rank_pct, 6)
                if rank_pct is not None
                else None,
                "old_alpha_score_rank_bucket": _rank_bucket(rank_pct),
                "old_alpha_score_rank_scope": "daily_cross_sectional_surface",
                "old_alpha_score_themes": row.get("themes") or [],
                "old_alpha_score_universe_count": universe_count,
            }

    return rank_index, date_summaries, failures


def join_old_alpha_score(
    rows: list[dict[str, Any]],
    rank_index: dict[tuple[str, str], dict[str, Any]],
    features_by_date: dict[str, dict[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    annotated: list[dict[str, Any]] = []
    for row in rows:
        enriched = dict(row)
        ticker = str(enriched.get("ticker") or "").upper()
        feature_date = enriched.get("feature_context_date")
        if not feature_date:
            enriched["old_alpha_score_join_status"] = "missing_feature_context_date"
        elif str(feature_date) not in features_by_date:
            enriched["old_alpha_score_join_status"] = "missing_feature_snapshot"
        elif (str(feature_date), ticker) not in rank_index:
            enriched["old_alpha_score_join_status"] = "ticker_absent_from_feature_snapshot"
        else:
            enriched.update(rank_index[(str(feature_date), ticker)])
            enriched["old_alpha_score_join_status"] = "joined"
            enriched["old_alpha_score_join_source"] = (
                "recomputed_cross_sectional_ranking_surface_by_feature_context_date"
            )

        component_score = expectation_residual_component_score(enriched)
        enriched["expectation_residual_component_score"] = component_score
        old_score = _float(enriched.get("old_alpha_score"), None)
        if old_score is not None:
            enriched["combined_alpha_score"] = round(old_score + component_score, 6)
        else:
            enriched["combined_alpha_score"] = None
        annotated.append(enriched)
    return annotated


def assign_score_ranks(
    rows: list[dict[str, Any]],
    *,
    score_key: str,
    prefix: str,
) -> list[dict[str, Any]]:
    scored = [row for row in rows if _float(row.get(score_key), None) is not None]
    scored.sort(
        key=lambda row: (
            -(_float(row.get(score_key), -999.0) or -999.0),
            str(row.get("feature_context_date") or ""),
            str(row.get("ticker") or ""),
        )
    )
    total = len(scored)
    for idx, row in enumerate(scored):
        rank_pct = (idx + 1) / total if total else None
        row[f"{prefix}_rank"] = idx + 1
        row[f"{prefix}_rank_pct"] = round(rank_pct, 6) if rank_pct is not None else None
        row[f"{prefix}_rank_bucket"] = _rank_bucket(rank_pct)

    for row in rows:
        if _float(row.get(score_key), None) is None:
            row[f"{prefix}_rank"] = None
            row[f"{prefix}_rank_pct"] = None
            row[f"{prefix}_rank_bucket"] = "missing_score"
    return rows


def _closed_outcome_count(rows: list[dict[str, Any]], horizon_key: str) -> int:
    return sum(
        1
        for row in rows
        if ((row.get("forward_outcomes") or {}).get(horizon_key) or {}).get("closed")
    )


def _score_summary(rows: list[dict[str, Any]], score_key: str) -> dict[str, Any]:
    values = [
        _float(row.get(score_key), None)
        for row in rows
        if _float(row.get(score_key), None) is not None
    ]
    if not values:
        return {"count": 0, "min": None, "max": None, "avg": None}
    return {
        "count": len(values),
        "min": round(min(values), 6),
        "max": round(max(values), 6),
        "avg": round(sum(values) / len(values), 6),
    }


def _compact_outcomes(row: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for horizon in [f"{horizon}d" for horizon in FORWARD_HORIZONS]:
        outcome = (row.get("forward_outcomes") or {}).get(horizon) or {}
        compact[horizon] = {
            "closed": bool(outcome.get("closed")),
            "return": outcome.get("return"),
            "pnl_proxy": outcome.get("pnl_proxy"),
            "future_date": outcome.get("future_date"),
            "gap_reason": outcome.get("gap_reason"),
        }
    return compact


def _compact_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "as_of_date": row.get("as_of_date"),
        "feature_context_date": row.get("feature_context_date"),
        "ticker": row.get("ticker"),
        "primary_bucket": row.get("primary_bucket"),
        "primary_expectation_positive": row.get("primary_expectation_positive"),
        "residual_state": row.get("residual_state"),
        "old_alpha_score": row.get("old_alpha_score"),
        "old_alpha_score_rank": row.get("old_alpha_score_rank"),
        "old_alpha_score_rank_bucket": row.get("old_alpha_score_rank_bucket"),
        "old_alpha_score_rank_scope": row.get("old_alpha_score_rank_scope"),
        "old_watchlist_alpha_score_rank": row.get("old_watchlist_alpha_score_rank"),
        "old_watchlist_alpha_score_rank_bucket": row.get(
            "old_watchlist_alpha_score_rank_bucket"
        ),
        "old_alpha_score_components": row.get("old_alpha_score_components"),
        "expectation_residual_component_score": row.get(
            "expectation_residual_component_score"
        ),
        "combined_alpha_score": row.get("combined_alpha_score"),
        "combined_watchlist_alpha_score_rank": row.get(
            "combined_watchlist_alpha_score_rank"
        ),
        "combined_watchlist_alpha_score_rank_bucket": row.get(
            "combined_watchlist_alpha_score_rank_bucket"
        ),
        "watchlist_rank_improvement": row.get("watchlist_rank_improvement"),
        "old_alpha_score_join_status": row.get("old_alpha_score_join_status"),
        "forward_outcomes": _compact_outcomes(row),
    }


def build_movement_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    comparable = [
        row
        for row in rows
        if _float(row.get("old_alpha_score"), None) is not None
        and _float(row.get("combined_alpha_score"), None) is not None
    ]
    for row in comparable:
        old_rank = row.get("old_watchlist_alpha_score_rank")
        combined_rank = row.get("combined_watchlist_alpha_score_rank")
        if old_rank is not None and combined_rank is not None:
            row["watchlist_rank_improvement"] = old_rank - combined_rank
        else:
            row["watchlist_rank_improvement"] = None

    old_top = {
        id(row)
        for row in comparable
        if row.get("old_watchlist_alpha_score_rank_bucket") == "top_decile"
    }
    combined_top = {
        id(row)
        for row in comparable
        if row.get("combined_watchlist_alpha_score_rank_bucket") == "top_decile"
    }
    improvements = [
        _float(row.get("watchlist_rank_improvement"), None)
        for row in comparable
        if _float(row.get("watchlist_rank_improvement"), None) is not None
    ]
    top_up = sorted(
        comparable,
        key=lambda row: _float(row.get("watchlist_rank_improvement"), -999.0)
        or -999.0,
        reverse=True,
    )[:20]
    top_down = sorted(
        comparable,
        key=lambda row: _float(row.get("watchlist_rank_improvement"), 999.0)
        or 999.0,
    )[:20]
    return {
        "comparable_rows": len(comparable),
        "rank_scope": "watchlist_rows_only_not_full_daily_candidate_surface",
        "old_watchlist_top_decile_rows": len(old_top),
        "combined_watchlist_top_decile_rows": len(combined_top),
        "top_decile_retained_rows": len(old_top & combined_top),
        "new_combined_top_decile_rows": len(combined_top - old_top),
        "old_top_decile_dropped_rows": len(old_top - combined_top),
        "watchlist_rank_improvement_summary": {
            "count": len(improvements),
            "min": round(min(improvements), 6) if improvements else None,
            "max": round(max(improvements), 6) if improvements else None,
            "avg": round(sum(improvements) / len(improvements), 6)
            if improvements
            else None,
        },
        "top_rank_improvers_sample": [_compact_row(row) for row in top_up],
        "top_rank_decliners_sample": [_compact_row(row) for row in top_down],
    }


def evaluate_measurement_gate(rows: list[dict[str, Any]], failures: dict[str, Any]) -> dict[str, Any]:
    total = len(rows)
    joined_rows = [
        row for row in rows if row.get("old_alpha_score_join_status") == "joined"
    ]
    joined_count = len(joined_rows)
    primary_joined = sum(
        1 for row in joined_rows if row.get("primary_expectation_positive") is True
    )
    coverage_ratio = round(joined_count / total, 6) if total else 0.0
    data_gap_reasons = []
    if joined_count < MIN_OLD_ALPHA_SCORE_ROWS:
        data_gap_reasons.append("old_alpha_score_rows_below_minimum")
    if primary_joined < MIN_PRIMARY_JOINED_ROWS:
        data_gap_reasons.append("primary_positive_joined_rows_below_minimum")
    if coverage_ratio < MIN_JOIN_COVERAGE_RATIO:
        data_gap_reasons.append("old_alpha_score_join_coverage_below_minimum")
    if failures:
        data_gap_reasons.append("ranking_surface_rebuild_failures_present")

    passed = not data_gap_reasons
    return {
        "promotion_gate_passed": False,
        "measurement_gate_passed": passed,
        "decision": (
            "measurement_repair_passed_next_true_ranking_test"
            if passed
            else "observed_only_data_gap"
        ),
        "reason": (
            "old_alpha_score_join_ready_for_true_replacement_test"
            if passed
            else "old_alpha_score_join_not_ready"
        ),
        "data_gap_reasons": data_gap_reasons,
        "thresholds": {
            "min_old_alpha_score_rows": MIN_OLD_ALPHA_SCORE_ROWS,
            "min_primary_joined_rows": MIN_PRIMARY_JOINED_ROWS,
            "min_join_coverage_ratio": MIN_JOIN_COVERAGE_RATIO,
        },
        "old_alpha_score_rows": joined_count,
        "primary_positive_joined_rows": primary_joined,
        "join_coverage_ratio": coverage_ratio,
        "surface_rebuild_failure_count": len(failures),
    }


def _experiment_log_entry(payload: dict[str, Any]) -> dict[str, Any]:
    keep_keys = (
        "experiment_id",
        "timestamp",
        "status",
        "hypothesis",
        "change_summary",
        "change_type",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "changed_variable",
        "single_causal_variable",
        "prior_trial_count",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "component",
        "parameters",
        "date_range",
        "gate_questions",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "coverage",
        "bucket_summary",
        "movement_summary",
        "gate",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "expected_value_score_delta",
        "llm_metrics",
        "production_impact",
        "decision",
        "rejection_reason",
        "next_evidence_needed",
        "related_files",
        "anti_js",
    )
    return {key: payload[key] for key in keep_keys if key in payload}


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Expectation Watchlist Old Alpha Score Join",
        "",
        f"- status: `{payload['status']}`",
        f"- decision: `{payload['decision']}`",
        f"- changed_variable: `{payload['changed_variable']}`",
        f"- gate_reason: `{payload['gate']['reason']}`",
        "",
        "## Summary",
        "",
        payload["change_summary"],
        "",
        "## Gate",
        "",
        "```json",
        json.dumps(_safe(payload["gate"]), indent=2, sort_keys=True),
        "```",
        "",
        "## Coverage",
        "",
        "```json",
        json.dumps(_safe(payload["coverage"]), indent=2, sort_keys=True),
        "```",
        "",
        "## Movement Summary",
        "",
        "```json",
        json.dumps(_safe(payload["movement_summary"]), indent=2, sort_keys=True),
        "```",
        "",
        "## Next Evidence Needed",
        "",
        payload["next_evidence_needed"],
        "",
        ANTI_JS,
        "",
    ]
    return "\n".join(lines)


def _upsert_registry(payload: dict[str, Any]) -> None:
    if not EXPERIMENT_REGISTRY.exists():
        return
    registry = json.loads(EXPERIMENT_REGISTRY.read_text(encoding="utf-8"))
    entry = {
        "experiment_id": payload["experiment_id"],
        "status": payload["status"],
        "lane": "alpha_discovery",
        "owner": "codex-expectation-old-alpha-join",
        "hypothesis": payload["hypothesis"],
        "ticket_file": _repo_rel(DOC_TICKET),
        "log_file": _repo_rel(DOC_LOG),
        "updated_at": payload["timestamp"],
        "result": {
            "decision": payload["decision"],
            "artifact": _repo_rel(DOC_ARTIFACT),
            "json": _repo_rel(OUT_JSON),
            "summary": payload["gate"].get("reason"),
        },
    }
    experiments = registry.setdefault("experiments", [])
    for idx, row in enumerate(experiments):
        if row.get("experiment_id") == EXPERIMENT_ID:
            experiments[idx] = {**row, **entry}
            break
    else:
        experiments.append(entry)
    registry["updated_at"] = payload["timestamp"]
    EXPERIMENT_REGISTRY.write_text(
        json.dumps(_safe(registry), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def persist_payload(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(DOC_LOG, payload)
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "lane": "alpha_search",
        "owner": "codex-expectation-old-alpha-join",
        "status": payload["status"],
        "decision": payload["decision"],
        "single_causal_variable": payload["single_causal_variable"],
        "artifact_file": _repo_rel(OUT_JSON),
        "result_file": _repo_rel(DOC_LOG),
        "updated_at": payload["timestamp"],
    }
    _write_json(DOC_TICKET, ticket)
    _write_json(DOCS_TICKET, ticket)
    DOC_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT.write_text(_artifact_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG_JSONL, _experiment_log_entry(payload))
    _upsert_registry(payload)


def build_payload(data_dir: Path | None = None) -> dict[str, Any]:
    data_dir = data_dir or (REPO_ROOT / "data")
    timestamp = _utc_now()
    context = build_context(data_dir)
    _, features_by_date = load_candidates(data_dir)
    rank_index, date_summaries, failures = build_old_alpha_score_index(features_by_date)

    rows = join_old_alpha_score(context["rows"], rank_index, features_by_date)
    rows = assign_score_ranks(
        rows,
        score_key="old_alpha_score",
        prefix="old_watchlist_alpha_score",
    )
    rows = assign_score_ranks(
        rows,
        score_key="combined_alpha_score",
        prefix="combined_watchlist_alpha_score",
    )

    gate = evaluate_measurement_gate(rows, failures)
    status = "observed_only" if gate["measurement_gate_passed"] else "observed_only_data_gap"
    decision = gate["decision"]
    join_status_counts = dict(Counter(str(row.get("old_alpha_score_join_status")) for row in rows))
    comparable_rows = [
        row
        for row in rows
        if _float(row.get("old_alpha_score"), None) is not None
        and _float(row.get("combined_alpha_score"), None) is not None
    ]
    bucket_summaries = {
        "old_surface_alpha_score": bucket_summary(
            rows,
            "old_alpha_score_rank_bucket",
            RANK_BUCKET_ORDER,
        ),
        "old_watchlist_alpha_score": bucket_summary(
            rows,
            "old_watchlist_alpha_score_rank_bucket",
            RANK_BUCKET_ORDER,
        ),
        "combined_watchlist_alpha_score": bucket_summary(
            rows,
            "combined_watchlist_alpha_score_rank_bucket",
            RANK_BUCKET_ORDER,
        ),
    }
    movement_summary = build_movement_summary(comparable_rows)
    related_files = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(DOC_LOG),
        _repo_rel(DOC_TICKET),
        _repo_rel(DOCS_TICKET),
        _repo_rel(DOC_ARTIFACT),
        _repo_rel(EXPERIMENT_LOG_JSONL),
        _repo_rel(EXPERIMENT_REGISTRY),
    ]
    coverage = {
        "rows_total": len(rows),
        "primary_positive_7d_rows": sum(
            1 for row in rows if row.get("primary_expectation_positive") is True
        ),
        "old_alpha_score_rows": gate["old_alpha_score_rows"],
        "primary_positive_joined_rows": gate["primary_positive_joined_rows"],
        "join_coverage_ratio": gate["join_coverage_ratio"],
        "join_status_counts": join_status_counts,
        "field_coverage": field_coverage(
            rows,
            [
                "feature_context_date",
                "old_alpha_score",
                "old_alpha_score_rank",
                "old_alpha_score_rank_bucket",
                "old_watchlist_alpha_score_rank",
                "old_watchlist_alpha_score_rank_bucket",
                "combined_alpha_score",
                "combined_watchlist_alpha_score_rank",
                "combined_watchlist_alpha_score_rank_bucket",
                "forward_outcomes",
            ],
        ),
        "closed_forward_outcomes": {
            f"{horizon}d": _closed_outcome_count(comparable_rows, f"{horizon}d")
            for horizon in FORWARD_HORIZONS
        },
        "score_summary": {
            "old_alpha_score": _score_summary(rows, "old_alpha_score"),
            "expectation_residual_component_score": _score_summary(
                rows,
                "expectation_residual_component_score",
            ),
            "combined_alpha_score": _score_summary(rows, "combined_alpha_score"),
        },
        "rank_bucket_counts": {
            "old_surface_alpha_score": dict(
                Counter(str(row.get("old_alpha_score_rank_bucket")) for row in rows)
            ),
            "old_watchlist_alpha_score": dict(
                Counter(
                    str(row.get("old_watchlist_alpha_score_rank_bucket"))
                    for row in rows
                )
            ),
            "combined_watchlist_alpha_score": dict(
                Counter(
                    str(row.get("combined_watchlist_alpha_score_rank_bucket"))
                    for row in rows
                )
            ),
        },
        "feature_surface_date_count": len(date_summaries),
        "watchlist_feature_context_dates": sorted(
            {str(row.get("feature_context_date")) for row in rows if row.get("feature_context_date")}
        ),
        "surface_rebuild_failures": failures,
        "surface_date_summaries_sample": {
            day: date_summaries[day] for day in sorted(date_summaries)[-10:]
        },
    }

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "lane": "alpha_search",
        "hypothesis": (
            "If old alpha_score can be point-in-time joined to the expectation "
            "revision watchlist, then the blocked old-vs-old-plus-expectation "
            "ranking replacement test becomes measurable."
        ),
        "change_summary": (
            "Read-only measurement repair that rebuilds the existing "
            "cross-sectional ranking surface by feature_context_date and joins "
            "old_alpha_score/rank/bucket onto expectation watchlist rows. No "
            "production behavior changed."
        ),
        "change_type": "observed_only_measurement_repair",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "prior_trial_count": 3,
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "low_measurement_repair",
        "new_evidence_type": "old_alpha_score_join_coverage",
        "component": _repo_rel(Path(__file__)),
        "parameters": {
            "source_experiment": "exp-20260525-034",
            "blocked_prior_experiment": "exp-20260526-033",
            "source_rows": "PIT-usable estimate revision watchlist rows",
            "old_alpha_score_source": "recomputed quant/cross_sectional_ranking_surface.py",
            "join_key": ["feature_context_date", "ticker"],
            "combined_score_formula": "old_alpha_score + expectation_residual_component_score",
            "component_score_formula": "1.0*primary_7d_positive + 0.35*prev_delta_positive + 0.25*30d_positive + 0.5*residual_leader",
            "watchlist_rerank_scope": "diagnostic only; true replacement must rerank the full daily candidate surface",
            "forward_horizons": list(FORWARD_HORIZONS),
            "paper_notional_usd": PAPER_NOTIONAL_USD,
            "anti_js": ANTI_JS,
        },
        "date_range": context["watchlist_payload"].get("date_range"),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "old_alpha_score_join_v1 unlocks a true ranking replacement "
                "test for expectation/residual evidence."
            ),
            "2_history_check": (
                "exp-20260526-033 had old_alpha_score_rows=0 and could only "
                "run a component proxy. exp-20260525-034 provides watchlist "
                "rows; exp-20260524-012 proves PIT alpha_score rebuild is possible."
            ),
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Measurement repair passes if old_alpha_score coverage is at "
                "least 80%, joined rows >= 100, primary-positive joined rows "
                ">= 30, and no ranking-surface rebuild failures occur."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260528_005_expectation_watchlist_old_alpha_score_join.py"
            ),
        },
        "gate1": {
            "passed": True,
            **BASELINE,
            "note": "Read-only measurement repair; no before/after core strategy metrics change.",
        },
        "gate2": {
            "passed": True,
            "rule_dependencies": [
                "feature_context_date",
                "ticker",
                "daily quant feature snapshots",
                "quant/cross_sectional_ranking_surface.py",
                "forward_outcomes for attribution only",
            ],
            "source_gate2": context["watchlist_payload"].get("gate2"),
        },
        "gate3": {
            "adds_filter": False,
            "candidate_pool_changed": False,
            "survival_rate_not_applicable": True,
            "passed": True,
        },
        "gate4": {
            "strategy_behavior_changed": False,
            "canonical_backtest_required": False,
            "passed": False,
            "note": "This can only unlock a later true ranking Gate 1-4 experiment.",
        },
        "coverage": coverage,
        "bucket_summary": bucket_summaries,
        "movement_summary": movement_summary,
        "sample_rows": {
            "combined_top_decile_sample": [
                _compact_row(row)
                for row in sorted(
                    comparable_rows,
                    key=lambda item: item.get("combined_watchlist_alpha_score_rank")
                    or 999999,
                )[:80]
            ],
            "old_top_decile_sample": [
                _compact_row(row)
                for row in sorted(
                    comparable_rows,
                    key=lambda item: item.get("old_watchlist_alpha_score_rank")
                    or 999999,
                )[:80]
            ],
        },
        "gate": gate,
        "before_metrics": {
            "accepted_core_expected_value_score_sum": BASELINE[
                "accepted_core_expected_value_score_sum"
            ],
            "accepted_core_total_pnl_sum": BASELINE["accepted_core_total_pnl_sum"],
            "strategy_behavior_changed": False,
        },
        "after_metrics": {
            "accepted_core_expected_value_score_sum": BASELINE[
                "accepted_core_expected_value_score_sum"
            ],
            "accepted_core_total_pnl_sum": BASELINE["accepted_core_total_pnl_sum"],
            "strategy_behavior_changed": False,
        },
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_sum_delta": 0.0,
            "strategy_behavior_delta": 0,
        },
        "expected_value_score_delta": 0.0,
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "observed_only_attribution": True,
            "parity_test_added": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "trade_enabled": False,
        },
        "rejection_reason": None
        if gate["measurement_gate_passed"]
        else "old_alpha_score join coverage did not clear measurement thresholds.",
        "next_evidence_needed": (
            "Run a true observed-only ranking replacement experiment that "
            "compares old_alpha_score buckets against "
            "old_alpha_score + expectation_residual_component_score buckets "
            "on the full per-date ranking surface, then require a separate "
            "Gate 1-4 strategy experiment before any production ranking change."
        ),
        "related_files": related_files,
        "anti_js": ANTI_JS,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=str(REPO_ROOT / "data"))
    parser.add_argument("--no-persist", action="store_true")
    args = parser.parse_args()

    payload = build_payload(Path(args.data_dir))
    if not args.no_persist:
        persist_payload(payload)

    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "status": payload["status"],
                "decision": payload["decision"],
                "gate": payload["gate"],
                "coverage": {
                    "rows_total": payload["coverage"]["rows_total"],
                    "old_alpha_score_rows": payload["coverage"]["old_alpha_score_rows"],
                    "primary_positive_joined_rows": payload["coverage"][
                        "primary_positive_joined_rows"
                    ],
                    "join_coverage_ratio": payload["coverage"]["join_coverage_ratio"],
                },
                "output": _repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
