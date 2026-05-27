"""exp-20260526-030..036: expectation-direction untried idea suite.

Observed-only alpha research. This runner executes the remaining ideas named in
docs/alpha_direction_expectation_residual_leadership.md as separate experiment
records, each with one changed variable. It does not alter entries, exits,
ranking, sizing, LLM/news prompts, paper sleeves, or orders.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS_DIR = Path(__file__).resolve().parent
if str(EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS_DIR))

from exp_20260525_017_expectation_residual_leadership_attribution import (  # noqa: E402
    FORWARD_HORIZONS,
    PAPER_NOTIONAL_USD,
)
from exp_20260525_034_expectation_revision_watchlist_attribution import (  # noqa: E402
    build_payload as build_watchlist_payload,
    summarize_rows,
)


MECHANISM_FAMILY = "expectation_drift_residual_pead"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
EXPERIMENT_REGISTRY = REPO_ROOT / "docs" / "experiment_registry.json"
ANTI_JS = "No JavaScript was used."
BASELINE = {
    "baseline_protocol": "docs/backtesting.md canonical three fixed windows",
    "baseline_artifact": "data/experiments/exp-20260517-009/",
    "accepted_core_expected_value_score_sum": 7.8941,
    "accepted_core_total_pnl_sum": 234850.99,
}
NEARBY_PRIORS = [
    "exp-20260524-012",
    "exp-20260525-017",
    "exp-20260525-021",
    "exp-20260525-023",
    "exp-20260525-025",
    "exp-20260525-031",
    "exp-20260525-034",
    "exp-20260526-006",
]
MIN_GROUP_5D_OUTCOMES = 8
MIN_TOTAL_USABLE_ROWS = 30
MAX_TOP5_POSITIVE_SHARE = 0.60
MAX_SINGLE_TICKER_POSITIVE_SHARE = 0.50

EXPERIMENT_SPECS = [
    {
        "experiment_id": "exp-20260526-030",
        "stem": "expectation_revision_velocity_attribution",
        "title": "Expectation Revision Velocity Attribution",
        "trial_family": "expectation_revision_velocity_attribution",
        "changed_variable": "expectation_revision_velocity_components_v1",
        "hypothesis": (
            "Strict PIT positive 7d EPS revision rows should be stronger when "
            "the estimate trajectory also has 30d support, EPS acceleration, "
            "revenue revision velocity, and analyst participation."
        ),
        "acceptance": (
            "Observed-only: velocity/acceleration buckets need enough closed "
            "5d/10d outcomes and the richer revenue/analyst fields must be "
            "present before any ranking or sleeve test."
        ),
    },
    {
        "experiment_id": "exp-20260526-031",
        "stem": "expectation_pead_readiness_probe",
        "title": "PEAD Paper Sleeve Readiness Probe",
        "trial_family": "short_horizon_pead_readiness_probe",
        "changed_variable": "short_horizon_pead_candidate_window_v1",
        "hypothesis": (
            "A T+2 to T+10 post-earnings paper sleeve may work only when "
            "positive revision/surprise context, no gap failure, and residual "
            "follow-through are all PIT-visible."
        ),
        "acceptance": (
            "Observed-only: an eligible PEAD bucket needs earnings-date "
            "coverage, market/gap-failure context, and enough closed 5d/10d "
            "outcomes; otherwise record a data gap."
        ),
    },
    {
        "experiment_id": "exp-20260526-032",
        "stem": "expectation_guidance_surprise_coverage",
        "title": "Guidance And Surprise Coverage Probe",
        "trial_family": "guidance_surprise_directional_context_probe",
        "changed_variable": "guidance_surprise_directional_context_v1",
        "hypothesis": (
            "Positive surprise history, current surprise, and non-negative "
            "guidance should separate higher-quality positive revision rows "
            "from revision-only rows."
        ),
        "acceptance": (
            "Observed-only: current surprise or guidance fields must be "
            "available in PIT snapshots before they can be used as PEAD or "
            "ranking inputs; historical surprise alone is a proxy only."
        ),
    },
    {
        "experiment_id": "exp-20260526-033",
        "stem": "expectation_ranking_replacement_probe",
        "title": "Ranking Replacement Proxy Probe",
        "trial_family": "expectation_residual_component_ranking_proxy",
        "changed_variable": "expectation_residual_component_ranking_replacement_proxy_v1",
        "hypothesis": (
            "An expectation/residual component should improve cross-sectional "
            "ordering if top-score rows beat bottom-score rows on 5d/10d "
            "outcomes and the effect is not concentration-only."
        ),
        "acceptance": (
            "Observed-only proxy: top-decile component rows must beat the "
            "bottom quintile on 5d and 10d; a true replacement test additionally "
            "requires PIT old alpha_score coverage."
        ),
    },
    {
        "experiment_id": "exp-20260526-034",
        "stem": "expectation_full_residual_dimension_probe",
        "title": "Full Residual Dimension Probe",
        "trial_family": "full_residual_leadership_dimension_probe",
        "changed_variable": "full_residual_leadership_dimension_coverage_v1",
        "hypothesis": (
            "Residual leadership should be cleaner when measured versus SPY, "
            "QQQ, sector, and theme, instead of only the current SPY/QQQ proxy."
        ),
        "acceptance": (
            "Observed-only: sector/theme residual fields must be present before "
            "full residual leadership can be promoted beyond the SPY/QQQ proxy."
        ),
    },
    {
        "experiment_id": "exp-20260526-035",
        "stem": "expectation_attribution_metric_completeness",
        "title": "Attribution Metric Completeness Probe",
        "trial_family": "expectation_attribution_metric_completeness_probe",
        "changed_variable": "expectation_attribution_metric_completeness_v1",
        "hypothesis": (
            "The expectation direction cannot graduate from attribution until "
            "avg_R, max-drawdown contribution, and replacement value can be "
            "measured, not just return and PnL proxy."
        ),
        "acceptance": (
            "Measurement gate: all promotion-critical metrics named in the "
            "direction memo must be available or explicitly blocked."
        ),
    },
    {
        "experiment_id": "exp-20260526-036",
        "stem": "expectation_breadth_theme_context_probe",
        "title": "Breadth And Theme Context Probe",
        "trial_family": "expectation_breadth_theme_context_probe",
        "changed_variable": "expectation_revision_breadth_theme_context_v1",
        "hypothesis": (
            "Breadth alignment and theme lifecycle should act as risk context "
            "for positive revision rows, not as the first alpha source."
        ),
        "acceptance": (
            "Observed-only: candidate-level breadth/theme fields must be joined "
            "to PIT revision rows before any risk-context experiment can run."
        ),
    },
]

SPEC_BY_ID = {spec["experiment_id"]: spec for spec in EXPERIMENT_SPECS}


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


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or value == "":
            return default
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if value == "":
        return False
    if isinstance(value, (list, tuple, set, dict)) and not value:
        return False
    return True


def field_coverage(rows: list[dict[str, Any]], fields: list[str]) -> dict[str, Any]:
    total = len(rows)
    coverage: dict[str, Any] = {}
    for field in fields:
        present = sum(1 for row in rows if _has_value(row.get(field)))
        coverage[field] = {
            "present_rows": present,
            "missing_rows": total - present,
            "coverage_ratio": round(present / total, 6) if total else None,
        }
    return coverage


def primary_positive_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if row.get("primary_expectation_positive") is True
        and (_float(row.get("eps_estimate_delta_7d"), 0.0) or 0.0) > 0
    ]


def _horizon_summaries(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {f"{horizon}d": summarize_rows(rows, f"{horizon}d") for horizon in FORWARD_HORIZONS}


def bucket_summary(
    rows: list[dict[str, Any]],
    bucket_key: str,
    bucket_order: list[str],
) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(bucket_key) or "missing")].append(row)
    ordered = list(bucket_order)
    for bucket in sorted(groups):
        if bucket not in ordered:
            ordered.append(bucket)
    summary: dict[str, Any] = {}
    for bucket in ordered:
        members = groups.get(bucket, [])
        summary[bucket] = {
            "row_count": len(members),
            "ticker_count": len({row.get("ticker") for row in members}),
            "tickers": sorted({str(row.get("ticker")) for row in members}),
            "ticker_row_counts": dict(Counter(str(row.get("ticker") or "missing") for row in members)),
            "horizons": _horizon_summaries(members),
        }
    return summary


def _total_pnl_proxy(rows: list[dict[str, Any]], horizon_key: str) -> float | None:
    values = []
    for row in rows:
        outcome = (row.get("forward_outcomes") or {}).get(horizon_key) or {}
        if outcome.get("closed") and outcome.get("pnl_proxy") is not None:
            values.append(float(outcome["pnl_proxy"]))
    return round(sum(values), 2) if values else None


def _avg_pnl_proxy(rows: list[dict[str, Any]], horizon_key: str) -> float | None:
    values = []
    for row in rows:
        outcome = (row.get("forward_outcomes") or {}).get(horizon_key) or {}
        if outcome.get("closed") and outcome.get("pnl_proxy") is not None:
            values.append(float(outcome["pnl_proxy"]))
    return round(sum(values) / len(values), 2) if values else None


def classify_revision_velocity_bucket(row: dict[str, Any]) -> str:
    if not (
        row.get("primary_expectation_positive") is True
        and (_float(row.get("eps_estimate_delta_7d"), 0.0) or 0.0) > 0
    ):
        return "not_primary_positive_7d"
    delta_7d = _float(row.get("eps_estimate_delta_7d"))
    delta_30d = _float(row.get("eps_estimate_delta_30d"))
    if delta_30d is None:
        return "primary_7d_missing_30d_velocity"
    if delta_30d <= 0:
        return "primary_7d_positive_30d_nonpositive"
    if delta_7d is not None and delta_7d - delta_30d > 0:
        return "primary_7d_30d_positive_accelerating"
    return "primary_7d_30d_positive_decelerating"


def classify_pead_bucket(row: dict[str, Any]) -> str:
    if not row.get("primary_expectation_positive"):
        return "not_primary_positive_7d"
    status = str(row.get("pead_status") or "missing_pead_status")
    if status == "inside_t2_t15_after_earnings":
        if row.get("residual_leader"):
            return "eligible_primary_positive_residual_leader"
        return "eligible_primary_positive_non_residual_leader"
    if status == "missing_last_earnings_date":
        return "blocked_missing_last_earnings_date"
    if status == "missing_effective_trade_date":
        return "blocked_missing_effective_trade_date"
    if status == "outside_t2_t15_after_earnings":
        return "blocked_outside_t2_t15_after_earnings"
    return f"blocked_{status}"


def _snapshot_paths_for_date(data_dir: Path, yyyymmdd: str) -> list[Path]:
    return [
        data_dir / "daily" / "snapshots" / "earnings" / f"earnings_snapshot_{yyyymmdd}.json",
        data_dir / f"earnings_snapshot_{yyyymmdd}.json",
        data_dir
        / "daily"
        / "snapshots"
        / "earnings"
        / "legacy_root"
        / f"earnings_snapshot_{yyyymmdd}.json",
    ]


def extract_earnings_snapshot_rows(payload: Any) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    earnings = payload.get("earnings") if isinstance(payload, dict) else payload
    if isinstance(earnings, dict):
        for ticker, data in earnings.items():
            if isinstance(data, dict):
                rows[str(ticker).upper()] = data
    elif isinstance(earnings, list):
        for item in earnings:
            if not isinstance(item, dict):
                continue
            ticker = str(item.get("ticker") or item.get("symbol") or "").upper()
            if ticker:
                rows[ticker] = item
    return rows


def load_earnings_snapshot_index(
    data_dir: Path,
    as_of_dates: set[str],
) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for as_of in sorted(as_of_dates):
        yyyymmdd = str(as_of).replace("-", "")
        chosen_path = None
        rows: dict[str, dict[str, Any]] = {}
        for path in _snapshot_paths_for_date(data_dir, yyyymmdd):
            if not path.exists():
                continue
            try:
                rows = extract_earnings_snapshot_rows(_read_json(path))
            except (OSError, json.JSONDecodeError):
                rows = {}
            if rows:
                chosen_path = path
                break
        index[as_of] = {
            "path": _repo_rel(chosen_path) if chosen_path else None,
            "rows": rows,
            "ticker_count": len(rows),
        }
    return index


CURRENT_SURPRISE_KEYS = (
    "eps_surprise_pct",
    "eps_surprise",
    "surprise_pct",
    "current_surprise_pct",
)
GUIDANCE_KEYS = (
    "guidance_sentiment",
    "guidance_tone",
    "guidance_bucket",
    "guidance",
)


def _first_present(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if _has_value(row.get(key)):
            return row.get(key)
    return None


def enrich_with_snapshot_context(
    rows: list[dict[str, Any]],
    snapshot_index: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    enriched_rows = []
    for row in rows:
        enriched = dict(row)
        as_of = str(row.get("as_of_date") or "")
        ticker = str(row.get("ticker") or "").upper()
        snapshot = snapshot_index.get(as_of) or {}
        snapshot_row = (snapshot.get("rows") or {}).get(ticker) or {}
        enriched["earnings_snapshot_path"] = snapshot.get("path")
        enriched["earnings_snapshot_matched"] = bool(snapshot_row)
        enriched["avg_historical_surprise_pct"] = _float(
            snapshot_row.get("avg_historical_surprise_pct")
        )
        hist = snapshot_row.get("historical_surprise_pct")
        enriched["historical_surprise_count"] = len(hist) if isinstance(hist, list) else 0
        enriched["current_surprise_value"] = _first_present(snapshot_row, CURRENT_SURPRISE_KEYS)
        enriched["guidance_value"] = _first_present(snapshot_row, GUIDANCE_KEYS)
        enriched["surprise_history_strength"] = snapshot_row.get("surprise_history_strength")
        enriched_rows.append(enriched)
    return enriched_rows


def classify_surprise_guidance_bucket(row: dict[str, Any]) -> str:
    if not row.get("primary_expectation_positive"):
        return "not_primary_positive_7d"
    if _has_value(row.get("guidance_value")):
        return "primary_positive_revision_guidance_available"
    surprise = _float(row.get("current_surprise_value"))
    if surprise is not None:
        return (
            "primary_positive_revision_current_surprise_positive"
            if surprise > 0
            else "primary_positive_revision_current_surprise_nonpositive"
        )
    avg_hist = _float(row.get("avg_historical_surprise_pct"))
    if avg_hist is not None:
        return (
            "primary_positive_revision_positive_surprise_history_proxy"
            if avg_hist > 0
            else "primary_positive_revision_nonpositive_surprise_history_proxy"
        )
    return "primary_positive_revision_missing_surprise_guidance"


def expectation_residual_component_score(row: dict[str, Any]) -> float:
    score = 0.0
    if row.get("primary_expectation_positive"):
        score += 1.0
    elif row.get("scout_prev_positive"):
        score += 0.35
    elif row.get("support_30d_positive"):
        score += 0.25
    if row.get("residual_leader"):
        score += 0.5
    return round(score, 6)


def assign_rank_buckets(
    rows: list[dict[str, Any]],
    score_key: str = "expectation_residual_component_score",
) -> list[dict[str, Any]]:
    ranked = [dict(row) for row in rows]
    ranked.sort(
        key=lambda row: (
            _float(row.get(score_key), -999.0) or -999.0,
            str(row.get("as_of_date") or ""),
            str(row.get("ticker") or ""),
        ),
        reverse=True,
    )
    total = len(ranked)
    if total == 0:
        return []
    for idx, row in enumerate(ranked):
        frac = (idx + 1) / total
        if frac <= 0.10:
            bucket = "top_decile"
        elif frac <= 0.20:
            bucket = "upper_quintile_ex_top_decile"
        elif frac <= 0.80:
            bucket = "middle_60pct"
        elif frac <= 0.90:
            bucket = "lower_quintile_ex_bottom"
        else:
            bucket = "bottom_quintile"
        row["expectation_residual_component_rank_bucket"] = bucket
        row["expectation_residual_component_rank"] = idx + 1
    return ranked


def classify_spy_qqq_residual_bucket(row: dict[str, Any]) -> str:
    spy = _float(row.get("ret20_excess_spy"))
    qqq = _float(row.get("ret20_excess_qqq"))
    if spy is None or qqq is None:
        return "missing_spy_or_qqq_residual"
    if spy > 0 and qqq > 0:
        return "spy_qqq_residual_positive"
    if spy > 0:
        return "spy_positive_qqq_nonpositive"
    if qqq > 0:
        return "qqq_positive_spy_nonpositive"
    return "spy_qqq_residual_nonpositive"


def attribution_metric_completeness(rows: list[dict[str, Any]]) -> dict[str, Any]:
    closed_5d = [
        row
        for row in rows
        if ((row.get("forward_outcomes") or {}).get("5d") or {}).get("closed")
    ]
    return {
        "available_metrics": {
            "win_rate": {"available": bool(closed_5d), "source": "forward_outcomes.*.return"},
            "avg_return": {"available": bool(closed_5d), "source": "forward_outcomes.*.return"},
            "avg_pnl_proxy": {"available": bool(closed_5d), "source": "forward_outcomes.*.pnl_proxy"},
            "total_pnl_proxy": {"available": bool(closed_5d), "source": "forward_outcomes.*.pnl_proxy"},
            "tail_loss": {"available": bool(closed_5d), "source": "forward_outcomes.*.return"},
            "worst_row": {"available": bool(closed_5d), "source": "forward_outcomes.*.return"},
            "top5_positive_contribution": {
                "available": bool(closed_5d),
                "source": "forward_outcomes.*.pnl_proxy",
            },
            "max_single_ticker_positive_contribution": {
                "available": bool(closed_5d),
                "source": "forward_outcomes.*.pnl_proxy",
            },
        },
        "missing_promotion_metrics": {
            "avg_R": {
                "available": False,
                "missing_fields": ["entry_price", "initial_stop", "initial_risk_per_share"],
            },
            "max_drawdown_contribution": {
                "available": False,
                "missing_fields": ["trade_equity_curve", "portfolio_drawdown_contribution"],
            },
            "replacement_value_vs_next_core_slot": {
                "available": False,
                "missing_fields": ["old_alpha_score_rank", "next_rejected_core_candidate", "slot_queue_state"],
            },
        },
    }


def _non_ohlcv_snapshot_coverage(data_dir: Path, as_of_dates: set[str]) -> dict[str, Any]:
    covered = []
    missing = []
    for as_of in sorted(as_of_dates):
        path = data_dir / "non_ohlcv" / f"daily_non_ohlcv_snapshot_{as_of.replace('-', '')}.json"
        if path.exists():
            covered.append(as_of)
        else:
            missing.append(as_of)
    total = len(as_of_dates)
    return {
        "dates_total": total,
        "covered_dates": len(covered),
        "missing_dates": len(missing),
        "coverage_ratio": round(len(covered) / total, 6) if total else None,
        "sample_covered_dates": covered[:10],
        "sample_missing_dates": missing[:10],
    }


def _paths(spec: dict[str, Any]) -> dict[str, Path]:
    exp_id = spec["experiment_id"]
    stem = spec["stem"]
    return {
        "out_dir": REPO_ROOT / "data" / "experiments" / exp_id,
        "json": REPO_ROOT / "data" / "experiments" / exp_id / f"{stem}.json",
        "log": REPO_ROOT / "experiments" / "logs" / f"{exp_id}.json",
        "ticket": REPO_ROOT / "experiments" / "tickets" / f"{exp_id}.json",
        "artifact": REPO_ROOT / "experiments" / "artifacts" / f"{exp_id}_{stem}.md",
    }


def _common_payload(
    *,
    spec: dict[str, Any],
    timestamp: str,
    status: str,
    decision: str,
    gate: dict[str, Any],
    watchlist_payload: dict[str, Any],
    parameters: dict[str, Any],
) -> dict[str, Any]:
    paths = _paths(spec)
    related_files = [
        _repo_rel(Path(__file__)),
        _repo_rel(paths["json"]),
        _repo_rel(paths["log"]),
        _repo_rel(paths["ticket"]),
        _repo_rel(paths["artifact"]),
        _repo_rel(EXPERIMENT_LOG_JSONL),
        _repo_rel(EXPERIMENT_REGISTRY),
    ]
    changed_variable = spec["changed_variable"]
    return {
        "experiment_id": spec["experiment_id"],
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "lane": "alpha_search",
        "hypothesis": spec["hypothesis"],
        "change_summary": (
            f"Read-only probe for {spec['title']} from the expectation direction memo. "
            "No production behavior changed."
        ),
        "change_type": "observed_only_expectation_direction_probe",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": spec["trial_family"],
        "trial_variant_id": changed_variable,
        "changed_variable": changed_variable,
        "single_causal_variable": changed_variable,
        "prior_trial_count": 8,
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "remaining_expectation_direction_memo_probe",
        "component": _repo_rel(Path(__file__)),
        "parameters": {
            "source_experiment": "exp-20260525-034",
            "source_rows": "PIT-usable estimate revision watchlist rows",
            "primary_positive_expectation_definition": "estimate_revision_usable && eps_estimate_delta_7d > 0",
            "forward_horizons": list(FORWARD_HORIZONS),
            "paper_notional_usd": PAPER_NOTIONAL_USD,
            **parameters,
            "anti_js": ANTI_JS,
        },
        "date_range": watchlist_payload.get("date_range"),
        "gate_questions": {
            "1_alpha_hypothesis": spec["hypothesis"],
            "2_history_check": (
                "The base expectation/residual attribution is exp-20260525-017; "
                "exp-20260525-034 expanded to a PIT-usable watchlist; "
                "exp-20260526-006 found non-overextended positive revisions "
                "directionally better but concentration/maturity blocked promotion."
            ),
            "3_single_causal_variable": changed_variable,
            "4_acceptance_standard": spec["acceptance"],
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260526_030_expectation_direction_untried_ideas_suite.py"
            ),
        },
        "gate1": {
            "passed": True,
            **BASELINE,
            "note": "Read-only attribution/probe; no before/after core strategy metrics change.",
        },
        "gate2": {
            "passed": True,
            "source_gate2": watchlist_payload.get("gate2"),
            "rule_dependencies": [
                "exp-20260525-034 PIT-safe annotated watchlist rows",
                "local OHLCV forward outcomes",
                "daily earnings snapshots when the probe needs surprise/guidance context",
            ],
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
            "note": "A passing read-only probe can only unlock a later default-off paper or ranking Gate 1-4 experiment.",
        },
        "gate": gate,
        "before_metrics": {
            "accepted_core_expected_value_score_sum": BASELINE["accepted_core_expected_value_score_sum"],
            "accepted_core_total_pnl_sum": BASELINE["accepted_core_total_pnl_sum"],
            "strategy_behavior_changed": False,
        },
        "after_metrics": {
            "accepted_core_expected_value_score_sum": BASELINE["accepted_core_expected_value_score_sum"],
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
        "related_files": related_files,
        "anti_js": ANTI_JS,
    }


def build_revision_velocity_payload(context: dict[str, Any], timestamp: str) -> dict[str, Any]:
    spec = SPEC_BY_ID["exp-20260526-030"]
    rows = context["primary_rows"]
    annotated = []
    for row in rows:
        enriched = dict(row)
        delta_7d = _float(row.get("eps_estimate_delta_7d"))
        delta_30d = _float(row.get("eps_estimate_delta_30d"))
        enriched["eps_revision_acceleration_proxy"] = (
            round(delta_7d - delta_30d, 6)
            if delta_7d is not None and delta_30d is not None
            else None
        )
        enriched["revision_velocity_bucket"] = classify_revision_velocity_bucket(row)
        annotated.append(enriched)
    summary = bucket_summary(
        annotated,
        "revision_velocity_bucket",
        [
            "primary_7d_30d_positive_accelerating",
            "primary_7d_30d_positive_decelerating",
            "primary_7d_positive_30d_nonpositive",
            "primary_7d_missing_30d_velocity",
        ],
    )
    coverage = {
        "primary_positive_7d_rows": len(rows),
        "field_coverage": field_coverage(
            annotated,
            [
                "eps_estimate_delta_7d",
                "eps_estimate_delta_30d",
                "eps_revision_acceleration_proxy",
                "revenue_revision_velocity_30d",
                "analyst_count_delta_30d",
            ],
        ),
        "bucket_counts": dict(Counter(row["revision_velocity_bucket"] for row in annotated)),
    }
    accel_rows = coverage["field_coverage"]["eps_revision_acceleration_proxy"]["present_rows"]
    revenue_rows = coverage["field_coverage"]["revenue_revision_velocity_30d"]["present_rows"]
    analyst_rows = coverage["field_coverage"]["analyst_count_delta_30d"]["present_rows"]
    data_gap_reasons = []
    if len(rows) < MIN_TOTAL_USABLE_ROWS:
        data_gap_reasons.append("primary_positive_7d_rows")
    if accel_rows < MIN_GROUP_5D_OUTCOMES:
        data_gap_reasons.append("eps_acceleration_proxy_rows")
    if revenue_rows == 0:
        data_gap_reasons.append("revenue_revision_velocity_30d")
    if analyst_rows == 0:
        data_gap_reasons.append("analyst_count_delta_30d")
    gate = {
        "promotion_gate_passed": False,
        "decision": "observed_only_data_gap" if data_gap_reasons else "observed_only_velocity_probe_ready",
        "reason": (
            "missing_velocity_components"
            if data_gap_reasons
            else "velocity_components_have_minimum_coverage_for_future_test"
        ),
        "data_gap_reasons": data_gap_reasons,
        "minimum_group_5d_outcomes": MIN_GROUP_5D_OUTCOMES,
    }
    payload = _common_payload(
        spec=spec,
        timestamp=timestamp,
        status="observed_only_data_gap" if data_gap_reasons else "observed_only",
        decision=gate["decision"],
        gate=gate,
        watchlist_payload=context["watchlist_payload"],
        parameters={
            "tested_components": [
                "eps_revision_velocity_7d",
                "eps_revision_velocity_30d",
                "eps_revision_acceleration",
                "revenue_revision_velocity_30d",
                "analyst_count_delta_30d",
            ],
        },
    )
    payload.update(
        {
            "coverage": coverage,
            "bucket_summary": summary,
            "sample_rows": annotated[:80],
            "rejection_reason": (
                "Required velocity components are sparse or absent, especially revenue velocity and analyst participation."
                if data_gap_reasons
                else None
            ),
            "next_evidence_needed": (
                "Persist revenue estimate deltas and analyst count deltas in the PIT ledger before promoting revision velocity."
            ),
        }
    )
    return payload


def build_pead_payload(context: dict[str, Any], timestamp: str) -> dict[str, Any]:
    spec = SPEC_BY_ID["exp-20260526-031"]
    annotated = []
    for row in context["rows"]:
        enriched = dict(row)
        enriched["pead_candidate_bucket"] = classify_pead_bucket(row)
        annotated.append(enriched)
    summary = bucket_summary(
        annotated,
        "pead_candidate_bucket",
        [
            "eligible_primary_positive_residual_leader",
            "eligible_primary_positive_non_residual_leader",
            "blocked_missing_last_earnings_date",
            "blocked_missing_effective_trade_date",
            "blocked_outside_t2_t15_after_earnings",
            "not_primary_positive_7d",
        ],
    )
    eligible = [
        row
        for row in annotated
        if row["pead_candidate_bucket"].startswith("eligible_primary_positive")
    ]
    eligible_5d = sum(
        1
        for row in eligible
        if ((row.get("forward_outcomes") or {}).get("5d") or {}).get("closed")
    )
    data_gap_reasons = []
    if not eligible:
        data_gap_reasons.append("no_t2_t15_last_earnings_date_rows")
    if eligible_5d < MIN_GROUP_5D_OUTCOMES:
        data_gap_reasons.append("eligible_closed_5d_outcomes")
    data_gap_reasons.extend(["market_risk_off_context", "post_earnings_gap_failure_context"])
    gate = {
        "promotion_gate_passed": False,
        "decision": "observed_only_data_gap",
        "reason": "pead_required_context_missing",
        "data_gap_reasons": data_gap_reasons,
        "eligible_rows": len(eligible),
        "eligible_closed_5d_outcomes": eligible_5d,
    }
    payload = _common_payload(
        spec=spec,
        timestamp=timestamp,
        status="observed_only_data_gap",
        decision=gate["decision"],
        gate=gate,
        watchlist_payload=context["watchlist_payload"],
        parameters={
            "candidate_window": "T+2 to T+10 after earnings",
            "hold": "5 to 15 trading days",
            "requires": [
                "positive surprise or positive revision",
                "residual strength threshold",
                "market not risk_off",
                "no immediate gap failure",
            ],
        },
    )
    payload.update(
        {
            "coverage": {
                "source_pead_status_counts": dict(Counter(row.get("pead_status") for row in context["rows"])),
                "pead_candidate_bucket_counts": dict(Counter(row["pead_candidate_bucket"] for row in annotated)),
                "eligible_rows": len(eligible),
                "eligible_closed_5d_outcomes": eligible_5d,
            },
            "bucket_summary": summary,
            "sample_rows": eligible[:50],
            "rejection_reason": "Missing last earnings date, market risk state, and gap-failure context block a PEAD sleeve.",
            "next_evidence_needed": "Add PIT last_earnings_date/report_date and post-earnings gap-failure fields to daily snapshots.",
        }
    )
    return payload


def build_guidance_surprise_payload(
    context: dict[str, Any],
    timestamp: str,
    data_dir: Path,
) -> dict[str, Any]:
    spec = SPEC_BY_ID["exp-20260526-032"]
    snapshot_index = load_earnings_snapshot_index(
        data_dir,
        {str(row.get("as_of_date")) for row in context["rows"] if row.get("as_of_date")},
    )
    enriched = enrich_with_snapshot_context(context["rows"], snapshot_index)
    for row in enriched:
        row["surprise_guidance_bucket"] = classify_surprise_guidance_bucket(row)
    primary = primary_positive_rows(enriched)
    summary = bucket_summary(
        primary,
        "surprise_guidance_bucket",
        [
            "primary_positive_revision_guidance_available",
            "primary_positive_revision_current_surprise_positive",
            "primary_positive_revision_current_surprise_nonpositive",
            "primary_positive_revision_positive_surprise_history_proxy",
            "primary_positive_revision_nonpositive_surprise_history_proxy",
            "primary_positive_revision_missing_surprise_guidance",
        ],
    )
    current_surprise_rows = sum(1 for row in primary if _has_value(row.get("current_surprise_value")))
    guidance_rows = sum(1 for row in primary if _has_value(row.get("guidance_value")))
    snapshot_matches = sum(1 for row in primary if row.get("earnings_snapshot_matched"))
    gate = {
        "promotion_gate_passed": False,
        "decision": (
            "observed_only_data_gap"
            if current_surprise_rows + guidance_rows == 0
            else "observed_only_surprise_guidance_probe"
        ),
        "reason": (
            "current_surprise_and_guidance_absent"
            if current_surprise_rows + guidance_rows == 0
            else "current_surprise_or_guidance_available_but_not_promoted"
        ),
        "current_surprise_rows": current_surprise_rows,
        "guidance_rows": guidance_rows,
        "snapshot_matched_primary_rows": snapshot_matches,
    }
    payload = _common_payload(
        spec=spec,
        timestamp=timestamp,
        status="observed_only_data_gap"
        if gate["decision"] == "observed_only_data_gap"
        else "observed_only",
        decision=gate["decision"],
        gate=gate,
        watchlist_payload=context["watchlist_payload"],
        parameters={
            "snapshot_sources": [
                "data/daily/snapshots/earnings/earnings_snapshot_YYYYMMDD.json",
                "data/earnings_snapshot_YYYYMMDD.json",
                "data/daily/snapshots/earnings/legacy_root/earnings_snapshot_YYYYMMDD.json",
            ],
            "current_surprise_keys": list(CURRENT_SURPRISE_KEYS),
            "guidance_keys": list(GUIDANCE_KEYS),
        },
    )
    payload.update(
        {
            "coverage": {
                "snapshot_date_count": len(snapshot_index),
                "snapshot_dates_with_rows": sum(1 for item in snapshot_index.values() if item["ticker_count"] > 0),
                "primary_positive_7d_rows": len(primary),
                "snapshot_matched_primary_rows": snapshot_matches,
                "current_surprise_rows": current_surprise_rows,
                "guidance_rows": guidance_rows,
                "avg_historical_surprise_rows": sum(
                    1 for row in primary if _float(row.get("avg_historical_surprise_pct")) is not None
                ),
                "bucket_counts": dict(Counter(row["surprise_guidance_bucket"] for row in primary)),
            },
            "bucket_summary": summary,
            "sample_rows": primary[:80],
            "rejection_reason": (
                "Historical surprise coverage exists for some rows, but current surprise and guidance fields are absent."
                if gate["decision"] == "observed_only_data_gap"
                else None
            ),
            "next_evidence_needed": "Persist current-quarter surprise/guidance direction in a PIT-safe earnings event ledger.",
        }
    )
    return payload


def build_ranking_payload(context: dict[str, Any], timestamp: str) -> dict[str, Any]:
    spec = SPEC_BY_ID["exp-20260526-033"]
    scored = []
    for row in context["rows"]:
        enriched = dict(row)
        enriched["expectation_residual_component_score"] = expectation_residual_component_score(row)
        scored.append(enriched)
    ranked = assign_rank_buckets(scored)
    summary = bucket_summary(
        ranked,
        "expectation_residual_component_rank_bucket",
        [
            "top_decile",
            "upper_quintile_ex_top_decile",
            "middle_60pct",
            "lower_quintile_ex_bottom",
            "bottom_quintile",
        ],
    )
    comparisons = []
    top = summary["top_decile"]
    bottom = summary["bottom_quintile"]
    directional_passed = True
    for horizon in ("5d", "10d"):
        top_h = top["horizons"][horizon]
        bottom_h = bottom["horizons"][horizon]
        passed = (
            top_h["avg_return"] is not None
            and bottom_h["avg_return"] is not None
            and top_h["avg_return"] > bottom_h["avg_return"]
        )
        directional_passed = directional_passed and passed
        comparisons.append(
            {
                "horizon": horizon,
                "top_decile_avg_return": top_h["avg_return"],
                "bottom_quintile_avg_return": bottom_h["avg_return"],
                "passed": passed,
            }
        )
    old_alpha_score_rows = field_coverage(ranked, ["alpha_score"])["alpha_score"]["present_rows"]
    concentration = {
        "top5_positive_contribution_share": top["horizons"]["5d"]["top5_positive_contribution_share"],
        "max_single_ticker_positive_share": top["horizons"]["5d"]["max_single_ticker_positive_share"],
        "top5_guardrail": MAX_TOP5_POSITIVE_SHARE,
        "single_ticker_guardrail": MAX_SINGLE_TICKER_POSITIVE_SHARE,
    }
    concentration["passed"] = (
        concentration["top5_positive_contribution_share"] is not None
        and concentration["max_single_ticker_positive_share"] is not None
        and concentration["top5_positive_contribution_share"] <= MAX_TOP5_POSITIVE_SHARE
        and concentration["max_single_ticker_positive_share"] <= MAX_SINGLE_TICKER_POSITIVE_SHARE
    )
    gate = {
        "promotion_gate_passed": False,
        "proxy_directional_passed": directional_passed,
        "decision": "observed_only_data_gap",
        "reason": "missing_old_alpha_score_for_true_replacement_test",
        "old_alpha_score_rows": old_alpha_score_rows,
        "comparisons": comparisons,
        "concentration": concentration,
    }
    payload = _common_payload(
        spec=spec,
        timestamp=timestamp,
        status="observed_only_data_gap",
        decision=gate["decision"],
        gate=gate,
        watchlist_payload=context["watchlist_payload"],
        parameters={
            "component_score": "1.0*primary_7d_positive + 0.35*prev_delta_positive + 0.25*30d_positive + 0.5*residual_leader",
            "true_replacement_requires": "old alpha_score PIT rank on the same candidate surface",
        },
    )
    payload.update(
        {
            "coverage": {
                "rows_scored": len(ranked),
                "old_alpha_score_rows": old_alpha_score_rows,
                "score_counts": dict(Counter(str(row["expectation_residual_component_score"]) for row in ranked)),
                "rank_bucket_counts": dict(
                    Counter(row["expectation_residual_component_rank_bucket"] for row in ranked)
                ),
            },
            "bucket_summary": summary,
            "sample_ranked_rows": ranked[:80],
            "rejection_reason": "This is only a component proxy because old alpha_score is absent from the PIT watchlist rows.",
            "next_evidence_needed": "Persist PIT old alpha_score/rank for the same rows, then rerun true old-vs-new ranking attribution.",
        }
    )
    return payload


def build_full_residual_payload(context: dict[str, Any], timestamp: str) -> dict[str, Any]:
    spec = SPEC_BY_ID["exp-20260526-034"]
    primary = []
    for row in context["primary_rows"]:
        enriched = dict(row)
        enriched["spy_qqq_residual_bucket"] = classify_spy_qqq_residual_bucket(row)
        primary.append(enriched)
    summary = bucket_summary(
        primary,
        "spy_qqq_residual_bucket",
        [
            "spy_qqq_residual_positive",
            "spy_positive_qqq_nonpositive",
            "qqq_positive_spy_nonpositive",
            "spy_qqq_residual_nonpositive",
            "missing_spy_or_qqq_residual",
        ],
    )
    coverage = {
        "primary_positive_7d_rows": len(primary),
        "field_coverage": field_coverage(
            primary,
            [
                "ret20_excess_spy",
                "ret20_excess_qqq",
                "ret20_excess_theme",
                "ret20_excess_sector",
            ],
        ),
        "bucket_counts": dict(Counter(row["spy_qqq_residual_bucket"] for row in primary)),
    }
    theme_rows = coverage["field_coverage"]["ret20_excess_theme"]["present_rows"]
    sector_rows = coverage["field_coverage"]["ret20_excess_sector"]["present_rows"]
    gate = {
        "promotion_gate_passed": False,
        "decision": "observed_only_data_gap" if theme_rows == 0 or sector_rows == 0 else "observed_only",
        "reason": (
            "missing_theme_or_sector_residual"
            if theme_rows == 0 or sector_rows == 0
            else "full_residual_fields_present_for_future_test"
        ),
        "theme_residual_rows": theme_rows,
        "sector_residual_rows": sector_rows,
    }
    payload = _common_payload(
        spec=spec,
        timestamp=timestamp,
        status="observed_only_data_gap" if gate["decision"] == "observed_only_data_gap" else "observed_only",
        decision=gate["decision"],
        gate=gate,
        watchlist_payload=context["watchlist_payload"],
        parameters={
            "required_residual_dimensions": [
                "ret20_excess_spy",
                "ret20_excess_qqq",
                "ret20_excess_theme",
                "ret20_excess_sector",
            ],
        },
    )
    payload.update(
        {
            "coverage": coverage,
            "bucket_summary": summary,
            "sample_rows": primary[:80],
            "rejection_reason": (
                "Only SPY/QQQ residual context is present; theme/sector residual leadership is not PIT-joined."
                if gate["decision"] == "observed_only_data_gap"
                else None
            ),
            "next_evidence_needed": "Persist sector/theme benchmark residual returns in the daily feature context.",
        }
    )
    return payload


def build_metric_completeness_payload(context: dict[str, Any], timestamp: str) -> dict[str, Any]:
    spec = SPEC_BY_ID["exp-20260526-035"]
    rows = context["primary_rows"]
    completeness = attribution_metric_completeness(rows)
    primary_summary = context["watchlist_payload"].get("primary_bucket_summary")
    available_proxy_metrics = {
        "5d_total_pnl_proxy": _total_pnl_proxy(rows, "5d"),
        "5d_avg_pnl_proxy": _avg_pnl_proxy(rows, "5d"),
        "10d_total_pnl_proxy": _total_pnl_proxy(rows, "10d"),
        "10d_avg_pnl_proxy": _avg_pnl_proxy(rows, "10d"),
    }
    missing = [
        metric
        for metric, info in completeness["missing_promotion_metrics"].items()
        if not info["available"]
    ]
    gate = {
        "promotion_gate_passed": False,
        "decision": "observed_only_data_gap",
        "reason": "promotion_critical_metrics_missing",
        "missing_promotion_metrics": missing,
    }
    payload = _common_payload(
        spec=spec,
        timestamp=timestamp,
        status="observed_only_data_gap",
        decision=gate["decision"],
        gate=gate,
        watchlist_payload=context["watchlist_payload"],
        parameters={
            "required_metrics_from_direction_memo": [
                "avg_R",
                "win_rate",
                "avg_pnl",
                "total_pnl",
                "tail_loss",
                "worst_trade",
                "top5_contribution",
                "max_drawdown_contribution",
                "replacement_value_vs_next_core_slot",
            ],
        },
    )
    payload.update(
        {
            "coverage": {
                "primary_positive_7d_rows": len(rows),
                "metric_completeness": completeness,
                "available_proxy_metrics": available_proxy_metrics,
            },
            "primary_bucket_summary_reference": primary_summary,
            "rejection_reason": "avg_R, max drawdown contribution, and replacement value are not measurable from current watchlist rows.",
            "next_evidence_needed": "Join watchlist rows to PIT entry risk, portfolio equity contribution, and next-core-slot queue state.",
        }
    )
    return payload


def build_breadth_theme_payload(
    context: dict[str, Any],
    timestamp: str,
    data_dir: Path,
) -> dict[str, Any]:
    spec = SPEC_BY_ID["exp-20260526-036"]
    rows = context["primary_rows"]
    coverage = {
        "primary_positive_7d_rows": len(rows),
        "row_field_coverage": field_coverage(
            rows,
            [
                "breadth_alignment",
                "market_breadth_state",
                "theme_lifecycle_state",
                "theme_density",
                "sector_breadth",
                "theme",
                "sector",
            ],
        ),
        "non_ohlcv_snapshot_date_coverage": _non_ohlcv_snapshot_coverage(
            data_dir,
            {str(row.get("as_of_date")) for row in context["rows"] if row.get("as_of_date")},
        ),
    }
    joined_rows = sum(
        coverage["row_field_coverage"][field]["present_rows"]
        for field in ("breadth_alignment", "theme_lifecycle_state", "theme_density", "sector_breadth")
    )
    gate = {
        "promotion_gate_passed": False,
        "decision": "observed_only_data_gap",
        "reason": "candidate_level_breadth_theme_fields_not_joined",
        "joined_context_field_instances": joined_rows,
    }
    payload = _common_payload(
        spec=spec,
        timestamp=timestamp,
        status="observed_only_data_gap",
        decision=gate["decision"],
        gate=gate,
        watchlist_payload=context["watchlist_payload"],
        parameters={
            "context_policy": "breadth/theme is risk context, not first alpha source",
            "required_joined_fields": [
                "breadth_alignment",
                "theme_lifecycle_state",
                "theme_density",
                "sector_breadth",
            ],
        },
    )
    payload.update(
        {
            "coverage": coverage,
            "rejection_reason": "Daily non-OHLCV context files may exist, but candidate-level breadth/theme fields are not joined to PIT revision rows.",
            "next_evidence_needed": "Add read-only candidate-level breadth/theme context to the watchlist attribution rows.",
        }
    )
    return payload


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
        "primary_bucket_summary_reference",
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


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    compact = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    exp_id = payload["experiment_id"]
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(compact + "\n", encoding="utf-8")
        return

    existing = False
    with path.open("r", encoding="utf-8", errors="replace") as src:
        for line in src:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("experiment_id") == exp_id:
                existing = True
                break

    if not existing:
        with path.open("a", encoding="utf-8") as dst:
            dst.write(compact + "\n")
        return

    tmp = path.with_suffix(path.suffix + f".{exp_id}.tmp")
    replaced = False
    with path.open("r", encoding="utf-8", errors="replace") as src, tmp.open(
        "w",
        encoding="utf-8",
    ) as dst:
        for line in src:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                dst.write(line.rstrip("\n") + "\n")
                continue
            if row.get("experiment_id") == exp_id:
                if not replaced:
                    dst.write(compact + "\n")
                    replaced = True
                continue
            dst.write(line.rstrip("\n") + "\n")
    try:
        tmp.replace(path)
    except PermissionError:
        # On this repo the large shared experiment log is often touched by
        # parallel agents. If atomic replacement is blocked, keep the audit
        # trail append-only instead of failing the read-only experiment run.
        try:
            tmp.unlink()
        except OSError:
            pass
        with path.open("a", encoding="utf-8") as dst:
            dst.write(compact + "\n")


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {payload['experiment_id']} {SPEC_BY_ID[payload['experiment_id']]['title']}",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Observed-only alpha research. No entries, exits, ranking, sizing, LLM/news, paper sleeves, or orders changed.",
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
        json.dumps(_safe(payload.get("coverage", {})), indent=2, sort_keys=True),
        "```",
    ]
    if payload.get("bucket_summary"):
        lines.extend(
            [
                "",
                "## Bucket Summary",
                "",
                "```json",
                json.dumps(_safe(payload["bucket_summary"]), indent=2, sort_keys=True),
                "```",
            ]
        )
    if payload.get("next_evidence_needed"):
        lines.extend(
            [
                "",
                "## Next Evidence Needed",
                "",
                payload["next_evidence_needed"],
            ]
        )
    lines.extend(["", ANTI_JS, ""])
    return "\n".join(lines)


def _upsert_registry(payload: dict[str, Any], paths: dict[str, Path]) -> None:
    if not EXPERIMENT_REGISTRY.exists():
        return
    registry = json.loads(EXPERIMENT_REGISTRY.read_text(encoding="utf-8"))
    entry = {
        "experiment_id": payload["experiment_id"],
        "status": payload["status"],
        "lane": "alpha_discovery",
        "owner": "codex-expectation-direction-suite",
        "hypothesis": payload["hypothesis"],
        "ticket_file": _repo_rel(paths["ticket"]),
        "log_file": _repo_rel(paths["log"]),
        "updated_at": payload["timestamp"],
        "result": {
            "decision": payload["decision"],
            "artifact": _repo_rel(paths["artifact"]),
            "json": _repo_rel(paths["json"]),
            "summary": payload["gate"].get("reason"),
        },
    }
    experiments = registry.setdefault("experiments", [])
    for idx, row in enumerate(experiments):
        if row.get("experiment_id") == payload["experiment_id"]:
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
    paths = _paths(SPEC_BY_ID[payload["experiment_id"]])
    _write_json(paths["json"], payload)
    _write_json(paths["log"], payload)
    _write_json(
        paths["ticket"],
        {
            "experiment_id": payload["experiment_id"],
            "lane": "alpha_search",
            "owner": "codex-expectation-direction-suite",
            "status": payload["status"],
            "decision": payload["decision"],
            "single_causal_variable": payload["single_causal_variable"],
            "artifact_file": _repo_rel(paths["json"]),
            "result_file": _repo_rel(paths["log"]),
            "updated_at": payload["timestamp"],
        },
    )
    paths["artifact"].parent.mkdir(parents=True, exist_ok=True)
    paths["artifact"].write_text(_artifact_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG_JSONL, _experiment_log_entry(payload))
    _upsert_registry(payload, paths)


def build_context(data_dir: Path | None = None) -> dict[str, Any]:
    data_dir = data_dir or (REPO_ROOT / "data")
    watchlist_payload = build_watchlist_payload(data_dir)
    rows = watchlist_payload.get("annotated_watchlist_rows") or []
    return {
        "data_dir": data_dir,
        "watchlist_payload": watchlist_payload,
        "rows": rows,
        "primary_rows": primary_positive_rows(rows),
    }


def build_all_payloads(data_dir: Path | None = None) -> list[dict[str, Any]]:
    timestamp = _utc_now()
    context = build_context(data_dir)
    data_dir = context["data_dir"]
    return [
        build_revision_velocity_payload(context, timestamp),
        build_pead_payload(context, timestamp),
        build_guidance_surprise_payload(context, timestamp, data_dir),
        build_ranking_payload(context, timestamp),
        build_full_residual_payload(context, timestamp),
        build_metric_completeness_payload(context, timestamp),
        build_breadth_theme_payload(context, timestamp, data_dir),
    ]


def main() -> int:
    payloads = build_all_payloads()
    for payload in payloads:
        persist_payload(payload)
    print(
        json.dumps(
            _safe(
                {
                    "suite": "expectation_direction_untried_ideas",
                    "experiment_ids": [payload["experiment_id"] for payload in payloads],
                    "results": [
                        {
                            "experiment_id": payload["experiment_id"],
                            "status": payload["status"],
                            "decision": payload["decision"],
                            "reason": payload["gate"].get("reason"),
                            "output": _repo_rel(_paths(SPEC_BY_ID[payload["experiment_id"]])["json"]),
                        }
                        for payload in payloads
                    ],
                    "anti_js": ANTI_JS,
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
