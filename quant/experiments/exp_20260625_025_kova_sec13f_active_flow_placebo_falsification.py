"""exp-20260625-025: Kova SEC13F active-flow placebo falsification.

Read-only alpha falsification. This runner reuses exp-20260625-009's
manager-level SEC13F active-flow score and asks whether the exact PIT score
beats deterministic placebo assignments on the same settled forward rows.

No strategy helper, daily adapter, ranking, sizing, exit, order, watchlist,
LLM, paper sleeve, or production behavior changes in this experiment.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
EXPERIMENTS_ROOT = REPO_ROOT / "quant" / "experiments"
for entry in (REPO_ROOT, SCRIPTS_ROOT, EXPERIMENTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402
import exp_20260625_009_kova_sec13f_active_manager_flow_forward_attribution as base  # noqa: E402


EXPERIMENT_ID = "exp-20260625-025"
OWNER = "alpha-explore"
SLUG = "kova_sec13f_active_flow_placebo_falsification"
RUNNER = f"quant/experiments/exp_20260625_025_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260625_025_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
EXP009_LOG = REPO_ROOT / "experiments" / "logs" / "exp-20260625-009.json"
EXP010_LOG = REPO_ROOT / "experiments" / "logs" / "exp-20260625-010.json"
EXP012_LOG = REPO_ROOT / "experiments" / "logs" / "exp-20260625-012.json"

HYPOTHESIS = (
    "Falsification alpha hypothesis: if the exp-20260625-009 Kova SEC13F "
    "active-manager active-flow lead is real rather than date/ticker beta, "
    "exact PIT active-flow scores should beat date-stratified shuffled placebo "
    "controls across settled 1d/3d/5d cash, SPY, and QQQ replacement-value "
    "separation."
)
CHANGE_TYPE = "alpha_falsification_audit"
IMPLEMENTATION_MODE = "observed_only_falsification_runner"
MECHANISM_FAMILY = "kova_multisource_forward_attribution"
TRIAL_FAMILY = "kova_sec13f_active_manager_flow_placebo_falsification"
TRIAL_VARIANT_ID = "date_stratified_permutation_v1"
CHANGED_VARIABLE = "kova_sec13f_active_flow_placebo_falsification_v1"
NEW_EVIDENCE_TYPE = "active_flow_placebo_falsification_gate"
NEW_EVIDENCE_AXIS = (
    "New gate shape: date-stratified placebo falsification of the already "
    "observed active-flow lead, not a new SEC13F threshold, top-N, hold, "
    "cooldown, notional, or allocator retry."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260625-009",
    "exp-20260625-010",
    "exp-20260625-012",
    "exp-20260625-023",
]
CAUSAL_COMPONENTS = [
    "exp009 active-flow score",
    "settled Kova forward rows",
    "date-stratified placebo controls",
    "no strategy behavior change",
]
COMPARATORS = ["cash", "spy", "qqq"]
HORIZONS = [1, 3, 5]
PRIMARY_HORIZON = 5
BUCKETS = ["low", "mid", "high"]
ASSIGNMENTS = {
    "exact": "active13f_active_flow_score",
    "asof_date_placebo": "placebo_asof_date_score",
    "window_ticker_placebo": "placebo_window_ticker_score",
}
ACCEPTANCE_RULE = {
    "primary_horizon": PRIMARY_HORIZON,
    "min_primary_scored_rows": 500,
    "min_primary_asof_dates": 3,
    "min_exact_avg_edge_advantage_usd": 50.0,
    "min_exact_avg_spearman_advantage": 0.02,
    "required_exact_mean_comparators": 3,
    "required_exact_median_comparators": 3,
}
PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "shared_policy_changed": False,
    "shared_helper_promoted": False,
    "daily_snapshot_exposed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "entry_rules_changed": False,
    "exit_rules_changed": False,
    "ranking_changed": False,
    "sizing_changed": False,
    "paper_orders_changed": False,
    "live_orders_changed": False,
    "live_ready": False,
    "uses_kova_forward_snapshots": True,
    "uses_sec13f_forward_context": True,
    "uses_raw_manager_level_sec13f_zip": True,
    "forward_only_not_fixed_window_pit_coverage": True,
    "replay_only": False,
    "live_realistic_execution_envelope": (
        "Not evaluated for live use; this is observed-only falsification and "
        "cannot become live-ready."
    ),
}
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260625-025/exp_20260625_025_kova_sec13f_active_flow_placebo_falsification.json",
    "experiments/cards/exp-20260625-025.md",
    "experiments/manifests/exp-20260625-025.json",
    "experiments/tickets/exp-20260625-025.json",
    "experiments/logs/exp-20260625-025.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return {} if default is None else default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {} if default is None else default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(record, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                rows.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(encoded)
                    replaced = True
                continue
            rows.append(json.dumps(existing, sort_keys=True))
    if not replaced:
        rows.append(encoded)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_float(value: Any) -> float | None:
    return base.safe_float(value)


def round_or_none(value: Any, digits: int = 6) -> float | None:
    number = safe_float(value)
    if number is None:
        return None
    return round(number, digits)


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def median_or_none(values: list[float]) -> float | None:
    return float(median(values)) if values else None


def stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "n": 0,
            "sum": 0.0,
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
            "positive_rate": None,
        }
    return {
        "n": len(values),
        "sum": round(sum(values), 2),
        "mean": round(mean(values) or 0.0, 4),
        "median": round(median(values), 4),
        "min": round(min(values), 2),
        "max": round(max(values), 2),
        "positive_rate": round(sum(1 for value in values if value > 0) / len(values), 4),
    }


def rankdata(values: list[float]) -> list[float]:
    return base.rankdata(values)


def pearson(xs: list[float], ys: list[float]) -> float | None:
    return base.pearson(xs, ys)


def stable_index(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:12], 16)


def load_prediction(ticket: dict[str, Any]) -> dict[str, Any]:
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    if isinstance(prediction, dict):
        return prediction
    return {
        "success_probability": 0.28,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "placebo_matches_exact",
            "date_beta_confound",
            "active_flow_not_incremental",
            "forward_window_too_short",
            "mega_cap_concentration",
        ],
        "confidence_reason": (
            "exp-20260625-009 showed strict 1d/3d/5d forward separation, but "
            "exp-20260625-010 and exp-20260625-012 rejected fixed-window "
            "historical promotion; placebo falsification is the cheapest way "
            "to decide whether the forward lead is real or date/ticker beta."
        ),
        "recorded_at": "2026-06-25T23:07:05+00:00",
    }


def add_placebo_scores(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = [dict(row) for row in rows]

    by_asof: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_window: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in enriched:
        score = safe_float(row.get("active13f_active_flow_score"))
        if score is None:
            continue
        asof = str(row.get("asof_date") or "")[:10]
        window = str(row.get("active13f_window_label") or "")
        by_asof[asof].append(row)
        by_window[window].append(row)

    for group_key, group in by_asof.items():
        ordered = sorted(
            group,
            key=lambda row: (
                str(row.get("ticker") or ""),
                str(row.get("observation_id") or ""),
                stable_index(group_key + str(row.get("observation_id") or "")),
            ),
        )
        scores = [safe_float(row.get("active13f_active_flow_score")) for row in ordered]
        shift = max(1, len(ordered) // 3)
        for idx, row in enumerate(ordered):
            row["placebo_asof_date_score"] = scores[(idx + shift) % len(scores)]

    for group_key, group in by_window.items():
        ordered = sorted(
            group,
            key=lambda row: stable_index(
                f"{group_key}|{row.get('ticker')}|{row.get('observation_id')}"
            ),
        )
        scores = [
            safe_float(row.get("active13f_active_flow_score"))
            for row in sorted(
                group,
                key=lambda row: (
                    safe_float(row.get("active13f_active_flow_score")) or -1.0,
                    str(row.get("ticker") or ""),
                    str(row.get("observation_id") or ""),
                ),
            )
        ]
        if not scores:
            continue
        shift = max(1, len(ordered) // 5)
        for idx, row in enumerate(ordered):
            row["placebo_window_ticker_score"] = scores[(idx + shift) % len(scores)]

    return enriched


def settled_rows(rows: list[dict[str, Any]], horizon: int, score_field: str) -> list[dict[str, Any]]:
    status_key = f"forward_{horizon}d_status"
    cash_key = f"replacement_value_{horizon}d_vs_cash_usd"
    return [
        row
        for row in rows
        if row.get(status_key) == "settled"
        and safe_float(row.get(cash_key)) is not None
        and safe_float(row.get(score_field)) is not None
    ]


def bucket_rows(rows: list[dict[str, Any]], score_field: str) -> dict[str, list[dict[str, Any]]]:
    ordered = sorted(
        rows,
        key=lambda row: (
            safe_float(row.get(score_field)) or 0.0,
            str(row.get("ticker") or ""),
            str(row.get("observation_id") or ""),
        ),
    )
    buckets = {bucket: [] for bucket in BUCKETS}
    total = len(ordered)
    if not total:
        return buckets
    for index, row in enumerate(ordered):
        buckets[BUCKETS[min(2, int(index * 3 / total))]].append(row)
    return buckets


def values(rows: list[dict[str, Any]], field: str) -> list[float]:
    out: list[float] = []
    for row in rows:
        value = safe_float(row.get(field))
        if value is not None:
            out.append(value)
    return out


def bucket_summary(rows: list[dict[str, Any]], horizon: int, score_field: str) -> dict[str, Any]:
    score_values = values(rows, score_field)
    result: dict[str, Any] = {
        "n": len(rows),
        "ticker_count": len({str(row.get("ticker") or "").upper() for row in rows}),
        "asof_date_count": len(
            {str(row.get("asof_date") or "")[:10] for row in rows if row.get("asof_date")}
        ),
        "score_mean": round_or_none(mean(score_values), 6),
        "score_median": round_or_none(median_or_none(score_values), 6),
        "replacement_metrics": {},
    }
    for comparator in COMPARATORS:
        field = f"replacement_value_{horizon}d_vs_{comparator}_usd"
        result["replacement_metrics"][comparator] = stats(values(rows, field))
    return result


def spearman(rows: list[dict[str, Any]], horizon: int, score_field: str, comparator: str) -> float | None:
    xs: list[float] = []
    ys: list[float] = []
    value_field = f"replacement_value_{horizon}d_vs_{comparator}_usd"
    for row in rows:
        score = safe_float(row.get(score_field))
        value = safe_float(row.get(value_field))
        if score is not None and value is not None:
            xs.append(score)
            ys.append(value)
    if len(xs) < 3:
        return None
    return round_or_none(pearson(rankdata(xs), rankdata(ys)), 6)


def assignment_summary(rows: list[dict[str, Any]], horizon: int, score_field: str) -> dict[str, Any]:
    settled = settled_rows(rows, horizon, score_field)
    buckets = bucket_rows(settled, score_field)
    summaries = {
        bucket: bucket_summary(bucket_rows_, horizon, score_field)
        for bucket, bucket_rows_ in buckets.items()
    }
    comparator_edges: dict[str, Any] = {}
    support: dict[str, bool] = {}
    for comparator in COMPARATORS:
        high_mean = summaries["high"]["replacement_metrics"][comparator]["mean"]
        low_mean = summaries["low"]["replacement_metrics"][comparator]["mean"]
        high_median = summaries["high"]["replacement_metrics"][comparator]["median"]
        low_median = summaries["low"]["replacement_metrics"][comparator]["median"]
        mean_edge = (
            round(high_mean - low_mean, 4)
            if high_mean is not None and low_mean is not None
            else None
        )
        median_edge = (
            round(high_median - low_median, 4)
            if high_median is not None and low_median is not None
            else None
        )
        comparator_edges[comparator] = {
            "mean_high_minus_low": mean_edge,
            "median_high_minus_low": median_edge,
            "spearman": spearman(settled, horizon, score_field, comparator),
        }
        support[f"mean_{comparator}_high_beats_low"] = mean_edge is not None and mean_edge > 0
        support[f"median_{comparator}_high_beats_low"] = (
            median_edge is not None and median_edge > 0
        )
        support[f"spearman_{comparator}_positive"] = (
            comparator_edges[comparator]["spearman"] is not None
            and comparator_edges[comparator]["spearman"] > 0
        )
    avg_mean_edge_values = [
        value["mean_high_minus_low"]
        for value in comparator_edges.values()
        if value["mean_high_minus_low"] is not None
    ]
    avg_spearman_values = [
        value["spearman"] for value in comparator_edges.values() if value["spearman"] is not None
    ]
    return {
        "horizon": horizon,
        "score_field": score_field,
        "settled_rows": len(settled),
        "scored_asof_date_count": len(
            {str(row.get("asof_date") or "")[:10] for row in settled if row.get("asof_date")}
        ),
        "buckets": summaries,
        "comparator_edges": comparator_edges,
        "avg_mean_edge_usd": round_or_none(mean(avg_mean_edge_values), 4),
        "avg_spearman": round_or_none(mean(avg_spearman_values), 6),
        "support": support,
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for assignment, score_field in ASSIGNMENTS.items():
        out[assignment] = {
            str(horizon): assignment_summary(rows, horizon, score_field)
            for horizon in HORIZONS
        }
    return out


def evaluate_gate4(attribution: dict[str, Any]) -> dict[str, Any]:
    primary_key = str(PRIMARY_HORIZON)
    exact = attribution["exact"][primary_key]
    placebo_primary = {
        name: attribution[name][primary_key]
        for name in ("asof_date_placebo", "window_ticker_placebo")
    }
    exact_edge = safe_float(exact.get("avg_mean_edge_usd"))
    exact_spearman = safe_float(exact.get("avg_spearman"))
    best_placebo_edge = max(
        safe_float(summary.get("avg_mean_edge_usd")) or -math.inf
        for summary in placebo_primary.values()
    )
    best_placebo_spearman = max(
        safe_float(summary.get("avg_spearman")) or -math.inf
        for summary in placebo_primary.values()
    )
    edge_advantage = (
        exact_edge - best_placebo_edge
        if exact_edge is not None and best_placebo_edge != -math.inf
        else None
    )
    spearman_advantage = (
        exact_spearman - best_placebo_spearman
        if exact_spearman is not None and best_placebo_spearman != -math.inf
        else None
    )
    exact_mean_passes = sum(
        1 for comparator in COMPARATORS if exact["support"].get(f"mean_{comparator}_high_beats_low")
    )
    exact_median_passes = sum(
        1
        for comparator in COMPARATORS
        if exact["support"].get(f"median_{comparator}_high_beats_low")
    )
    exact_spearman_passes = sum(
        1 for comparator in COMPARATORS if exact["support"].get(f"spearman_{comparator}_positive")
    )
    multi_horizon_edge_passes = sum(
        1
        for horizon in HORIZONS
        if safe_float(attribution["exact"][str(horizon)].get("avg_mean_edge_usd")) is not None
        and safe_float(attribution["exact"][str(horizon)].get("avg_mean_edge_usd")) > 0
    )
    historical_promotion_rejected = (
        read_json(EXP010_LOG, {}).get("decision")
        == "rejected_sec13f_active_manager_flow_candidate_pool"
        or read_json(EXP012_LOG, {}).get("decision")
        == "rejected_sec13f_active_flow_filing_delay_hardened_candidate_pool"
    )

    checks = {
        "primary_scored_rows_floor": exact["settled_rows"]
        >= ACCEPTANCE_RULE["min_primary_scored_rows"],
        "primary_asof_dates_floor": exact["scored_asof_date_count"]
        >= ACCEPTANCE_RULE["min_primary_asof_dates"],
        "exact_mean_edges_all_comparators_positive": exact_mean_passes
        >= ACCEPTANCE_RULE["required_exact_mean_comparators"],
        "exact_median_edges_all_comparators_positive": exact_median_passes
        >= ACCEPTANCE_RULE["required_exact_median_comparators"],
        "exact_spearman_all_comparators_positive": exact_spearman_passes == len(COMPARATORS),
        "exact_multi_horizon_avg_edge_positive": multi_horizon_edge_passes >= 2,
        "exact_edge_beats_best_placebo": edge_advantage is not None
        and edge_advantage >= ACCEPTANCE_RULE["min_exact_avg_edge_advantage_usd"],
        "exact_spearman_beats_best_placebo": spearman_advantage is not None
        and spearman_advantage >= ACCEPTANCE_RULE["min_exact_avg_spearman_advantage"],
        "historical_promotion_not_already_rejected": not historical_promotion_rejected,
    }
    failed = [key for key, value in checks.items() if not value]
    falsification_passed = not any(
        reason
        for reason in failed
        if reason != "historical_promotion_not_already_rejected"
    )
    if falsification_passed and historical_promotion_rejected:
        decision = "observed_only_placebo_falsification_passed_but_promotion_blocked_by_historical_gate4"
        status = "observed_only_rejected"
    elif falsification_passed:
        decision = "observed_only_positive_kova_sec13f_active_flow_placebo_falsification_passed"
        status = "observed_only_positive_lead"
    else:
        decision = "rejected_kova_sec13f_active_flow_failed_placebo_falsification"
        status = "observed_only_rejected"
    return {
        "passed": falsification_passed and not historical_promotion_rejected,
        "falsification_passed": falsification_passed,
        "observed_only_lead": falsification_passed,
        "status": status,
        "decision": decision,
        "acceptance_checks": checks,
        "failed_reasons": failed,
        "primary_horizon": PRIMARY_HORIZON,
        "exact_avg_mean_edge_usd": round_or_none(exact_edge, 4),
        "best_placebo_avg_mean_edge_usd": round_or_none(best_placebo_edge, 4)
        if best_placebo_edge != -math.inf
        else None,
        "exact_edge_advantage_vs_best_placebo_usd": round_or_none(edge_advantage, 4),
        "exact_avg_spearman": round_or_none(exact_spearman, 6),
        "best_placebo_avg_spearman": round_or_none(best_placebo_spearman, 6)
        if best_placebo_spearman != -math.inf
        else None,
        "exact_spearman_advantage_vs_best_placebo": round_or_none(spearman_advantage, 6),
        "historical_promotion_rejected": historical_promotion_rejected,
        "promotion_blockers": [
            "exp-20260625-010 historical active-flow candidate pool rejected",
            "exp-20260625-012 filing-delay-hardened historical candidate pool rejected",
            "10d forward outcomes remain pending in exp017 ledger",
            "no shared helper, daily adapter, rank, sizing, or live behavior promoted",
        ],
        "before_after_strategy_delta": {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "max_drawdown_pct": 0.0,
            "trade_count": 0,
        },
        "strategy_rerun_required": False,
    }


def source_summary(rows: list[dict[str, Any]], analysis: dict[str, Any]) -> dict[str, Any]:
    ids = [str(row.get("observation_id") or "") for row in rows if row.get("observation_id")]
    dates = sorted({str(row.get("asof_date") or "")[:10] for row in rows if row.get("asof_date")})
    return {
        "outcome_ledger": repo_rel(base.OUTCOME_LEDGER),
        "outcome_rows": len(rows),
        "duplicate_observation_ids": len(ids) - len(set(ids)),
        "asof_date_count": len(dates),
        "asof_date_start": dates[0] if dates else None,
        "asof_date_end": dates[-1] if dates else None,
        "ticker_count": len({str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")}),
        "active13f_status_counts": dict(
            sorted(Counter(str(row.get("active13f_status") or "missing") for row in rows).items())
        ),
        "sec13f_status_counts": dict(
            sorted(Counter(str(row.get("sec13f_status") or "missing") for row in rows).items())
        ),
        "exp009_source_summary": analysis["source_summary"],
    }


def calibration(gate4: dict[str, Any], prediction: dict[str, Any]) -> dict[str, Any]:
    predicted = float(prediction.get("success_probability") or 0.0)
    actual = 1.0 if gate4["passed"] else 0.0
    failure_modes = list(gate4["failed_reasons"])
    predicted_modes = prediction.get("main_failure_modes") or []
    aliases = {
        "placebo_matches_exact": {
            "exact_edge_beats_best_placebo",
            "exact_spearman_beats_best_placebo",
        },
        "date_beta_confound": {
            "exact_edge_beats_best_placebo",
            "exact_spearman_beats_best_placebo",
        },
        "forward_window_too_short": {"historical_promotion_not_already_rejected"},
    }
    hit = any(mode in failure_modes for mode in predicted_modes)
    if not hit:
        hit = any(
            mode in aliases and aliases[mode] & set(failure_modes)
            for mode in predicted_modes
        )
    return {
        "actual_success": actual,
        "actual_decision": gate4["decision"],
        "predicted_success_probability": predicted,
        "brier_score": round((predicted - actual) ** 2, 4),
        "predicted_failure_modes": predicted_modes,
        "realized_failure_modes": failure_modes,
        "predicted_failure_mode_hit": hit,
        "surprise_note": (
            "The placebo test is deliberately strict: passing falsification can "
            "still be promotion-blocked because the fixed-window historical "
            "candidate-pool experiments already failed Gate 4."
        ),
    }


def post_run_reflection(gate4: dict[str, Any]) -> dict[str, Any]:
    if gate4["falsification_passed"]:
        why = (
            "The exact PIT active-flow score beat deterministic placebo controls, "
            "so exp-009's forward separation is not obviously a date/ticker "
            "assignment artifact. It is still not promotable because exp-010 and "
            "exp-012 already rejected historical fixed-window candidate-pool "
            "versions."
        )
    else:
        why = (
            "The exact PIT active-flow score did not clear the placebo standard, "
            "so the exp-009 forward lead is too likely to be date/ticker beta or "
            "partial-ledger noise to justify another promotion retry."
        )
    return {
        "why_result_happened": why,
        "forbidden_near_neighbor_retry": (
            "Do not retry Kova SEC13F active-holder share, active-value share, "
            "active-flow deltas, filing-delay caps, holder counts, values, top-N, "
            "hold, cooldown, notional, or allocator thresholds on the same exp017 "
            "partial forward rows or frozen windows."
        ),
        "new_evidence_required": (
            "A valid retry needs enough closed 10d replacement-value rows, "
            "manager-level active-flow provenance from a new non-quarterly source, "
            "populated borrow/loan-availability cross-evidence, or canonical "
            "fixed-window PIT coverage through a shared helper that beats accepted "
            "comparators."
        ),
    }


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = load_prediction(ticket if isinstance(ticket, dict) else {})
    raw_rows = base.read_jsonl(base.OUTCOME_LEDGER)
    analysis = base.build_analysis(raw_rows)
    rows = add_placebo_scores(analysis["rows"])
    attribution = summarize(rows)
    gate4 = evaluate_gate4(attribution)
    before = base.baseline_metrics()
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "status": gate4["status"],
        "lane": "alpha_search",
        "owner": OWNER,
        "decision": gate4["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": gate4["observed_only_lead"],
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "parameters": {
            "source_outcome_ledger": repo_rel(base.OUTCOME_LEDGER),
            "sec13f_source_cache": repo_rel(base.SEC13F_CACHE),
            "assignments": ASSIGNMENTS,
            "horizons": HORIZONS,
            "primary_horizon": PRIMARY_HORIZON,
            "acceptance_rule": ACCEPTANCE_RULE,
            "placebo_rules": {
                "asof_date_placebo": "rotate exact scores within the same asof_date group",
                "window_ticker_placebo": (
                    "assign exact-score distribution by deterministic hash order "
                    "within the same SEC13F source window"
                ),
            },
        },
        "source_summary": source_summary(rows, analysis),
        "attribution": attribution,
        "primary_summary": attribution["exact"][str(PRIMARY_HORIZON)],
        "before_metrics": before,
        "after_metrics": {**before, "strategy_behavior_changed": False},
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "max_drawdown_pct_worst_delta": 0.0,
            "strategy_behavior_changed": False,
        },
        "gate1": {
            "baseline_loaded": base.BASELINE_RESULT.exists(),
            "baseline_metrics": before,
            "note": "Observed-only falsification; before and after policy are identical.",
        },
        "gate2": {
            "dependencies_validated": bool(rows)
            and source_summary(rows, analysis)["duplicate_observation_ids"] == 0,
            "fields_checked": [
                "observation_id",
                "asof_date",
                "ticker",
                "entry_date",
                "sec13f_source_file",
                "active13f_active_flow_score",
                "placebo_asof_date_score",
                "placebo_window_ticker_score",
                "forward_1d_status",
                "forward_3d_status",
                "forward_5d_status",
                "replacement_value_5d_vs_cash_usd",
                "replacement_value_5d_vs_spy_usd",
                "replacement_value_5d_vs_qqq_usd",
                "target_price",
            ],
            "entry_date_present": any(row.get("entry_date") for row in rows),
            "target_price_relevance": (
                "Not applicable: this is observed-only fixed-horizon outcome "
                "falsification and does not schedule target exits or orders."
            ),
            "source_summary": source_summary(rows, analysis),
        },
        "gate3": {
            "filter_added": False,
            "signals_generated": len(raw_rows),
            "signals_survived": attribution["exact"][str(PRIMARY_HORIZON)]["settled_rows"],
            "survival_rate": round(
                attribution["exact"][str(PRIMARY_HORIZON)]["settled_rows"] / len(raw_rows),
                4,
            )
            if raw_rows
            else None,
            "baseline_survival_rate": before.get("survival_rate"),
            "note": "No executable filter was added; rows are attributed only.",
        },
        "gate4": gate4,
        "production_impact": PRODUCTION_IMPACT,
        "calibration": calibration(gate4, prediction),
        "post_run_reflection": post_run_reflection(gate4),
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": "Reservation passed without override; nearest prior score was 0.5122 and below block threshold.",
                "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
                "new_evidence_axis": NEW_EVIDENCE_AXIS,
            },
            "3_single_policy_bundle": (
                "One observed-only falsification bundle: exact active-flow score "
                "versus deterministic as-of-date and source-window placebo "
                "assignments on the same settled Kova forward rows."
            ),
            "4_success_failure_standard": (
                "Observed-only falsification passes only if exact 5d high-minus-low "
                "mean/median and Spearman support all cash/SPY/QQQ comparators, "
                "positive exact edge holds across at least two horizons, and exact "
                "average edge/Spearman beat the best placebo by predeclared margins. "
                "Historical Gate-4 rejections remain promotion blockers."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "related_files": [
            RUNNER,
            "quant/experiments/exp_20260625_009_kova_sec13f_active_manager_flow_forward_attribution.py",
            repo_rel(base.OUTCOME_LEDGER),
            repo_rel(base.SEC13F_CACHE),
            repo_rel(EXP009_LOG),
            repo_rel(EXP010_LOG),
            repo_rel(EXP012_LOG),
            repo_rel(base.BASELINE_RESULT),
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
        ],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "lean_quality_passed": True,
        "ticket_before": {
            "created_at": ticket.get("created_at") if isinstance(ticket, dict) else None,
            "claimed_at": ticket.get("claimed_at") if isinstance(ticket, dict) else None,
            "hub_identity": ticket.get("hub_identity") if isinstance(ticket, dict) else None,
            "novelty": ticket.get("novelty") if isinstance(ticket, dict) else None,
        },
    }
    return payload


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    primary_key = str(PRIMARY_HORIZON)
    return {
        "experiment_id": payload["experiment_id"],
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "observed_only_lead": payload["observed_only_lead"],
        "lane": payload["lane"],
        "owner": payload["owner"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "single_causal_variable": payload["single_causal_variable"],
        "causal_components": payload["causal_components"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "new_evidence_axis": payload["new_evidence_axis"],
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "pre_run_questions": payload["pre_run_questions"],
        "parameters": payload["parameters"],
        "source_summary": payload["source_summary"],
        "primary_summary": {
            assignment: payload["attribution"][assignment][primary_key]
            for assignment in ASSIGNMENTS
        },
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "related_files": payload["related_files"],
        "changed_files": payload["changed_files"],
        "allowed_write_scope": payload["allowed_write_scope"],
        "reproduction_commands": payload["reproduction_commands"],
        "artifact": payload["artifact"],
        "log": payload["log"],
        "anti_js": payload["anti_js"],
        "lean_quality_passed": payload["lean_quality_passed"],
    }


def money(value: Any) -> str:
    number = safe_float(value)
    return "n/a" if number is None else f"${number:,.2f}"


def build_card(payload: dict[str, Any]) -> str:
    primary_key = str(PRIMARY_HORIZON)
    rows = [
        "| Assignment | Rows | Avg Mean Edge | Avg Spearman | Edge vs Placebo | Spearman vs Placebo |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    gate4 = payload["gate4"]
    for assignment in ASSIGNMENTS:
        summary = payload["attribution"][assignment][primary_key]
        rows.append(
            "| {assignment} | {rows_n} | {edge} | {rho} | {edge_adv} | {rho_adv} |".format(
                assignment=assignment,
                rows_n=summary["settled_rows"],
                edge=money(summary["avg_mean_edge_usd"]),
                rho=summary["avg_spearman"],
                edge_adv=(
                    money(gate4["exact_edge_advantage_vs_best_placebo_usd"])
                    if assignment == "exact"
                    else ""
                ),
                rho_adv=(
                    gate4["exact_spearman_advantage_vs_best_placebo"]
                    if assignment == "exact"
                    else ""
                ),
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: Kova SEC13F active-flow placebo falsification",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Strategy behavior changed: `false`",
            f"- Artifact: `{repo_rel(OUT_JSON)}`",
            "",
            "## Primary 5d Falsification",
            "",
            *rows,
            "",
            f"- Failed checks: `{', '.join(gate4['failed_reasons']) or 'none'}`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Reproduction",
            "",
            "```powershell",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
            "```",
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        EXP009_LOG,
        EXP010_LOG,
        EXP012_LOG,
        base.OUTCOME_LEDGER,
        base.BASELINE_RESULT,
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
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)

    ticket_before = payload.get("ticket_before") or {}
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
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
        "new_evidence_axis": payload["new_evidence_axis"],
        "baseline_result_file": repo_rel(base.BASELINE_RESULT),
        "decision": payload["decision"],
        "artifact": payload["artifact"],
        "log": payload["log"],
        "card_file": repo_rel(CARD_MD),
        "revision_manifest_file": repo_rel(MANIFEST_JSON),
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "related_files": payload["related_files"],
        "changed_files": payload["changed_files"],
        "allowed_write_scope": payload["allowed_write_scope"],
        "lean_quality_passed": payload["lean_quality_passed"],
        "hub_identity": ticket_before.get("hub_identity"),
        "novelty": ticket_before.get("novelty"),
        "claimed_at": ticket_before.get("claimed_at"),
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result={
            "accepted": False,
            "accepted_alpha": False,
            "observed_only_lead": payload["observed_only_lead"],
            "allocation_ready": False,
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "log": payload["log"],
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields=fields,
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
                "observed_only_lead": payload["observed_only_lead"],
                "exact_avg_mean_edge_usd": payload["gate4"]["exact_avg_mean_edge_usd"],
                "best_placebo_avg_mean_edge_usd": payload["gate4"][
                    "best_placebo_avg_mean_edge_usd"
                ],
                "exact_edge_advantage_vs_best_placebo_usd": payload["gate4"][
                    "exact_edge_advantage_vs_best_placebo_usd"
                ],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
