"""exp-20260626-017: recency placebo control ledger.

This is an alpha-enabling measurement repair. The alpha hypothesis is that
future Kova/LLM/multi-source candidate-pool claims must prove incremental
value over simple recency/momentum controls. This run only materializes that
control surface for the current estimate-revision observations.

No strategy, ranking, sizing, exit, order, LLM, daily snapshot, paper ledger, or
live behavior is changed.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260626-017"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "recency_placebo_control_ledger"
RUNNER = f"quant/experiments/exp_20260626_017_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

CHANGED_VARIABLE = "recency_placebo_control_ledger_v1"
MECHANISM_FAMILY = "recency_placebo_measurement_repair"
TRIAL_FAMILY = "estimate_revision_rs_placebo_control"
TRIAL_VARIANT_ID = "current_daily_20260625_v1"

DAILY_TAG = "20260625"
BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
ESTIMATE_REVISION_LEDGER = (
    REPO_ROOT / "data" / "non_ohlcv" / f"estimate_revision_ledger_{DAILY_TAG}.jsonl"
)
RS_PROXY_LEDGER = REPO_ROOT / "data" / "kova" / "rs_proxy" / f"rs_proxy_{DAILY_TAG}.jsonl"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260626_017_{SLUG}.json"
LEDGER_JSONL = OUT_DIR / f"{SLUG}_{DAILY_TAG}.jsonl"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

WINDOWS: "OrderedDict[str, dict[str, str]]" = OrderedDict(
    [
        ("late_strong", {"start": "2025-10-23", "end": "2026-04-21"}),
        ("mid_weak", {"start": "2025-04-23", "end": "2025-10-22"}),
        ("old_thin", {"start": "2024-10-02", "end": "2025-04-22"}),
    ]
)

ALLOWED_WRITE_SCOPE = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260626_017_{SLUG}.json",
    f"data/experiments/{EXPERIMENT_ID}/{SLUG}_{DAILY_TAG}.jsonl",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]

HYPOTHESIS = (
    "measurement_repair/alpha_blocker: Kova, LLM, and multi-source "
    "candidate-pool alpha claims remain untrustworthy unless estimate-revision "
    "observations carry a machine-readable recency/RS placebo control surface "
    "so future experiments must beat simple recent-return baselines instead of "
    "rediscovering momentum."
)
ALPHA_HYPOTHESIS = (
    "candidate_pool / LLM event scoring: future Kova or LLM-assisted "
    "multi-source ranking alpha should add information beyond simple PIT "
    "recent-return strength. If a proposed score only selects the same "
    "20/60/120-day RS buckets, the apparent edge is likely a momentum placebo, "
    "not a new alpha source."
)
PREDICTION = {
    "success_probability": 0.85,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "rs_proxy_missing",
        "estimate_revision_schema_gap",
        "coverage_below_95_pct",
    ],
    "confidence_reason": (
        "The 20260625 estimate-revision ledger and Kova RS proxy both contain "
        "ticker/asof fields; this is a network-free join/control artifact, not "
        "a new alpha filter."
    ),
    "recorded_at": "2026-06-26T16:09:06+00:00",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return value.as_posix()


def safe(value: Any) -> Any:
    if isinstance(value, OrderedDict):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, Counter):
        return dict(value)
    if isinstance(value, dict):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [safe(item) for item in value]
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return round(value, 10)
    return value


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def iter_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    errors = 0
    if not path.exists():
        return rows, errors
    for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if not raw.strip():
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            errors += 1
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows, errors


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(safe(row), ensure_ascii=True, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def upsert_jsonl(path: Path, row: dict[str, Any]) -> None:
    encoded = json.dumps(safe(row), ensure_ascii=True, sort_keys=True)
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
                rows.append(encoded)
                replaced = True
            else:
                rows.append(raw)
    if not replaced:
        rows.append(encoded)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def coerce_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def day_lag(later: Any, earlier: Any) -> int | None:
    later_date = parse_date(later)
    earlier_date = parse_date(earlier)
    if later_date is None or earlier_date is None:
        return None
    return (later_date - earlier_date).days


def rank_bucket(value: Any) -> str:
    rank = coerce_float(value)
    if rank is None:
        return "missing"
    if rank >= 0.8:
        return "q5_top_20"
    if rank >= 0.6:
        return "q4_60_80"
    if rank >= 0.4:
        return "q3_40_60"
    if rank >= 0.2:
        return "q2_20_40"
    return "q1_bottom_20"


def sign_bucket(value: Any) -> str:
    number = coerce_float(value)
    if number is None:
        return "missing"
    if number > 0:
        return "positive"
    if number < 0:
        return "negative"
    return "zero"


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {}) or {}
    windows = payload.get("windows") or []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "max_drawdown_pct_worst": max(
            (float(row.get("max_drawdown_pct") or 0.0) for row in windows),
            default=0.0,
        ),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / max(generated, 1), 4),
        "windows": windows,
    }


def compact_rs(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {}
    return {
        "status": row.get("status"),
        "asof_date": row.get("asof_date"),
        "asof_price_date": row.get("asof_price_date"),
        "benchmark": row.get("benchmark"),
        "ret_20d": coerce_float(row.get("ret_20d")),
        "ret_60d": coerce_float(row.get("ret_60d")),
        "ret_120d": coerce_float(row.get("ret_120d")),
        "excess_ret_20d_vs_spy": coerce_float(row.get("excess_ret_20d_vs_spy")),
        "excess_ret_60d_vs_spy": coerce_float(row.get("excess_ret_60d_vs_spy")),
        "excess_ret_120d_vs_spy": coerce_float(row.get("excess_ret_120d_vs_spy")),
        "rs_proxy_rank_pct_20d": coerce_float(row.get("rs_proxy_rank_pct_20d")),
        "rs_proxy_rank_pct_60d": coerce_float(row.get("rs_proxy_rank_pct_60d")),
        "rs_proxy_rank_pct_120d": coerce_float(row.get("rs_proxy_rank_pct_120d")),
        "available_window_count": int(row.get("available_window_count") or 0),
        "row_count": int(row.get("row_count") or 0),
        "known_at": row.get("known_at"),
        "source_snapshot": row.get("source_snapshot"),
        "alters_orders": bool(row.get("alters_orders")),
    }


def build_ledger() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    estimate_rows, estimate_errors = iter_jsonl(ESTIMATE_REVISION_LEDGER)
    rs_rows, rs_errors = iter_jsonl(RS_PROXY_LEDGER)
    rs_ok_by_ticker = {
        str(row.get("ticker") or "").upper(): row
        for row in rs_rows
        if str(row.get("ticker") or "").strip()
        and str(row.get("status") or "").lower() == "ok"
    }

    ledger: list[dict[str, Any]] = []
    coverage_counts: Counter[str] = Counter()
    direction_counts: Counter[str] = Counter()
    candidate_gap_counts: Counter[str] = Counter()
    bucket_counts_20d: Counter[str] = Counter()
    bucket_counts_60d: Counter[str] = Counter()
    bucket_counts_120d: Counter[str] = Counter()
    stale_lag_counts: Counter[str] = Counter()
    price_date_after_asof = 0
    usable_estimate_rows = 0
    usable_joined_rows = 0
    all_bucket_rows = 0

    for estimate in estimate_rows:
        ticker = str(estimate.get("ticker") or "").upper().strip()
        rs = rs_ok_by_ticker.get(ticker)
        rs_fields = compact_rs(rs)
        estimate_usable = bool(estimate.get("estimate_revision_usable"))
        if estimate_usable:
            usable_estimate_rows += 1
        matched = bool(rs)
        if estimate_usable and matched:
            usable_joined_rows += 1

        buckets = {
            "rank_20d": rank_bucket(rs_fields.get("rs_proxy_rank_pct_20d")),
            "rank_60d": rank_bucket(rs_fields.get("rs_proxy_rank_pct_60d")),
            "rank_120d": rank_bucket(rs_fields.get("rs_proxy_rank_pct_120d")),
            "excess_ret_20d": sign_bucket(rs_fields.get("excess_ret_20d_vs_spy")),
            "excess_ret_60d": sign_bucket(rs_fields.get("excess_ret_60d_vs_spy")),
            "excess_ret_120d": sign_bucket(rs_fields.get("excess_ret_120d_vs_spy")),
        }
        has_all_rank_buckets = all(
            buckets[key] != "missing" for key in ("rank_20d", "rank_60d", "rank_120d")
        )
        if estimate_usable and has_all_rank_buckets:
            all_bucket_rows += 1

        lag_days = day_lag(estimate.get("as_of_date"), rs_fields.get("asof_price_date"))
        if lag_days is None:
            stale_lag_bucket = "missing"
        elif lag_days < 0:
            stale_lag_bucket = "price_after_asof"
            price_date_after_asof += 1
        elif lag_days == 0:
            stale_lag_bucket = "same_day"
        elif lag_days <= 2:
            stale_lag_bucket = "one_to_two_days"
        elif lag_days <= 5:
            stale_lag_bucket = "three_to_five_days"
        else:
            stale_lag_bucket = "over_five_days"

        coverage_counts["matched_rs_proxy" if matched else "missing_rs_proxy"] += 1
        direction_counts[str(estimate.get("revision_direction_prev") or "missing")] += 1
        candidate_gap_counts[str(estimate.get("candidate_match_gap_reason") or "missing")] += 1
        bucket_counts_20d[buckets["rank_20d"]] += 1
        bucket_counts_60d[buckets["rank_60d"]] += 1
        bucket_counts_120d[buckets["rank_120d"]] += 1
        stale_lag_counts[stale_lag_bucket] += 1

        ledger.append(
            {
                "schema_version": 1,
                "ticker": ticker,
                "as_of_date": estimate.get("as_of_date"),
                "next_earnings_date": estimate.get("next_earnings_date"),
                "source_snapshot_path": estimate.get("source_snapshot_path"),
                "source_snapshot_timestamp": estimate.get("source_snapshot_timestamp"),
                "pit_safe_flag": bool(estimate.get("pit_safe_flag")),
                "estimate_revision_usable": estimate_usable,
                "revision_direction_prev": estimate.get("revision_direction_prev"),
                "eps_estimate_delta_prev": coerce_float(estimate.get("eps_estimate_delta_prev")),
                "eps_estimate_delta_7d": coerce_float(estimate.get("eps_estimate_delta_7d")),
                "same_event_history_count": int(estimate.get("same_event_history_count") or 0),
                "matched_candidate_today": bool(estimate.get("matched_candidate_today")),
                "matched_selected_signal_today": bool(estimate.get("matched_selected_signal_today")),
                "candidate_match_gap_reason": estimate.get("candidate_match_gap_reason"),
                "rs_proxy_joined": matched,
                "rs_proxy_source": repo_rel(RS_PROXY_LEDGER),
                "rs_proxy": rs_fields,
                "placebo_controls": {
                    **buckets,
                    "asof_price_lag_days": lag_days,
                    "asof_price_lag_bucket": stale_lag_bucket,
                    "has_all_rank_buckets": has_all_rank_buckets,
                },
                "future_alpha_requirement": (
                    "Any estimate/Kova/LLM alpha using this ticker-date must report "
                    "performance by these recency buckets and beat the simple RS "
                    "placebo under the same PIT and execution envelope."
                ),
                "alpha_use_allowed": estimate_usable and matched and has_all_rank_buckets,
                "alters_orders": False,
            }
        )

    join_coverage = usable_joined_rows / max(usable_estimate_rows, 1)
    bucket_coverage = all_bucket_rows / max(usable_estimate_rows, 1)
    summary = {
        "daily_tag": DAILY_TAG,
        "estimate_revision_source": repo_rel(ESTIMATE_REVISION_LEDGER),
        "rs_proxy_source": repo_rel(RS_PROXY_LEDGER),
        "estimate_revision_rows": len(estimate_rows),
        "estimate_revision_json_errors": estimate_errors,
        "rs_proxy_rows": len(rs_rows),
        "rs_proxy_json_errors": rs_errors,
        "rs_proxy_ok_rows": len(rs_ok_by_ticker),
        "usable_estimate_rows": usable_estimate_rows,
        "usable_joined_rows": usable_joined_rows,
        "usable_join_coverage": round(join_coverage, 6),
        "usable_all_bucket_rows": all_bucket_rows,
        "usable_bucket_coverage": round(bucket_coverage, 6),
        "price_date_after_asof_rows": price_date_after_asof,
        "coverage_counts": dict(sorted(coverage_counts.items())),
        "revision_direction_counts": dict(sorted(direction_counts.items())),
        "candidate_match_gap_counts": dict(sorted(candidate_gap_counts.items())),
        "rank_20d_bucket_counts": dict(sorted(bucket_counts_20d.items())),
        "rank_60d_bucket_counts": dict(sorted(bucket_counts_60d.items())),
        "rank_120d_bucket_counts": dict(sorted(bucket_counts_120d.items())),
        "asof_price_lag_counts": dict(sorted(stale_lag_counts.items())),
        "sample_missing_rs_proxy_tickers": [
            row["ticker"] for row in ledger if not row["rs_proxy_joined"]
        ][:20],
    }
    return ledger, summary


def build_payload() -> dict[str, Any]:
    baseline = baseline_metrics()
    ledger_rows, ledger_summary = build_ledger()
    failed_reasons: list[str] = []
    if not ESTIMATE_REVISION_LEDGER.exists():
        failed_reasons.append("estimate_revision_ledger_missing")
    if not RS_PROXY_LEDGER.exists():
        failed_reasons.append("rs_proxy_ledger_missing")
    if ledger_summary["estimate_revision_json_errors"]:
        failed_reasons.append("estimate_revision_json_errors")
    if ledger_summary["rs_proxy_json_errors"]:
        failed_reasons.append("rs_proxy_json_errors")
    if ledger_summary["estimate_revision_rows"] <= 0:
        failed_reasons.append("no_estimate_revision_rows")
    if ledger_summary["usable_join_coverage"] < 0.95:
        failed_reasons.append("coverage_below_95_pct")
    if ledger_summary["usable_bucket_coverage"] < 0.95:
        failed_reasons.append("bucket_coverage_below_95_pct")
    if ledger_summary["price_date_after_asof_rows"] > 0:
        failed_reasons.append("rs_proxy_price_date_after_asof")
    accepted = not failed_reasons
    decision = (
        "accepted_measurement_repair_recency_placebo_control_ledger"
        if accepted
        else "rejected_measurement_repair_recency_placebo_control_ledger_incomplete"
    )
    production_impact = {
        "strategy_behavior_changed": False,
        "daily_snapshot_behavior_changed": False,
        "trade_enabled_changed": False,
        "orders_changed": False,
        "ranking_changed": False,
        "sizing_changed": False,
        "paper_only": False,
        "live_ready": False,
        "impact": (
            "No production behavior changes. The artifact is a replayable "
            "placebo-control ledger future alpha runs can join for falsification."
        ),
    }
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "lane": LANE,
        "owner": OWNER,
        "status": "accepted" if accepted else "rejected",
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_summary": (
            "Joined the current estimate-revision ledger to the PIT Kova RS proxy "
            "and emitted fixed 20/60/120-day recency placebo buckets without "
            "changing strategy behavior."
        ),
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "network_free_artifact_ledger",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": [
            "estimate_revision_to_rs_proxy_join",
            "recency_rank_bucket_controls",
            "no_strategy_behavior_change",
        ],
        "nearby_prior_experiments": [
            "exp-20260625-017",
            "exp-20260625-020",
            "exp-20260626-015",
            "exp-20260626-016",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "measurement_repair",
        "new_evidence_axis": (
            "Not an alpha override; this builds a placebo-control measurement "
            "surface so future Kova/LLM candidate-pool experiments cannot claim "
            "incremental alpha without beating simple recency buckets."
        ),
        "prediction": PREDICTION,
        "gate1": {
            "passed": True,
            "strategy_behavior_changed": False,
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": accepted,
            "strategy_behavior_changed": False,
            "runtime_fields_checked": [
                "estimate_revision.ticker",
                "estimate_revision.as_of_date",
                "estimate_revision.revision_direction_prev",
                "estimate_revision.estimate_revision_usable",
                "rs_proxy.ticker",
                "rs_proxy.asof_date",
                "rs_proxy.asof_price_date",
                "rs_proxy.rs_proxy_rank_pct_20d",
                "rs_proxy.rs_proxy_rank_pct_60d",
                "rs_proxy.rs_proxy_rank_pct_120d",
            ],
            "minimum_strategy_fields": {
                "entry_date": "not_applicable_no_strategy_signal_or_filter_added",
                "target_price": "not_applicable_no_strategy_signal_or_filter_added",
            },
            "blocking_reason": "; ".join(failed_reasons),
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "baseline_survival_rate": baseline["survival_rate"],
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "note": "No executable filter was added; survival and trade count are unchanged.",
        },
        "gate4": {
            "passed": accepted,
            "decision": decision,
            "strategy_behavior_changed": False,
            "before_after_strategy_delta": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
                "survival_rate_delta": 0.0,
            },
            "failed_reasons": failed_reasons,
            "accepted_basis": (
                "Accepted as measurement repair only: current estimate-revision "
                "rows now carry PIT RS recency-placebo controls with >=95% usable "
                "coverage, and strategy metrics are unchanged."
            )
            if accepted
            else None,
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "survival_rate_delta": 0.0,
            "estimate_revision_rows": ledger_summary["estimate_revision_rows"],
            "usable_join_coverage": ledger_summary["usable_join_coverage"],
            "usable_bucket_coverage": ledger_summary["usable_bucket_coverage"],
            "price_date_after_asof_rows": ledger_summary["price_date_after_asof_rows"],
        },
        "ledger_summary": ledger_summary,
        "ledger_rows": ledger_rows,
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_success": 1 if accepted else 0,
            "brier_score": round((PREDICTION["success_probability"] - (1 if accepted else 0)) ** 2, 6),
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "realized_failure_mode": None if accepted else "; ".join(failed_reasons),
            "predicted_failure_mode_hit": not accepted,
            "surprise_note": (
                "Coverage matched expectation: the current daily estimate-revision "
                "surface joins cleanly to the PIT RS proxy."
            )
            if accepted
            else "One or more required current control surfaces was incomplete.",
        },
        "production_impact": production_impact,
        "post_run_reflection": {
            "why_result_happened": (
                "The 20260625 estimate-revision ledger and Kova RS proxy share a "
                "ticker/asof universe, so a network-free control ledger can assign "
                "20/60/120-day RS placebo buckets before any new candidate-pool "
                "score is trusted."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not use this artifact to re-slice the same open forward rows, "
                "or to retune an estimate/RS threshold on observed-only outcomes. "
                "It is a falsification control, not an accepted trading edge."
            ),
            "new_evidence_required": (
                "A future alpha run must add materially new closed forward rows, "
                "a new production-visible data field, or a shared default-off "
                "candidate-pool helper, and must report incremental performance "
                "versus these recency buckets under the same PIT envelope."
            ),
        },
        "next_retry_requires": [
            "materially more closed forward replacement rows or a genuinely new production-visible field",
            "future Kova/LLM score evaluated against this 20/60/120-day RS placebo ledger",
            "same PIT/execution envelope and explicit displacement versus simple recency buckets",
        ],
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260625-017": "Blocked: Kova intraday surface missing OHLCV settlement for estimate-revision outcomes.",
                "exp-20260626-015": "Accepted evidence-gap ledger; same-row forward attribution and saturated sources remain no-go.",
                "exp-20260626-016": "Accepted SEC periodic materialization blocker; no strategy alpha promoted.",
                "novelty_gate": "Reservation warned on a measurement-repair near-neighbor, but this lane did not run an alpha replay or override saturated source rules.",
            },
            "3_single_decision_hypothesis": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Accept as measurement repair only if the current estimate-revision "
                "ledger joins to PIT RS proxy with >=95% usable coverage, emits "
                "fixed 20/60/120-day recency buckets, and preserves zero strategy delta."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "related_files": [
            repo_rel(ESTIMATE_REVISION_LEDGER),
            repo_rel(RS_PROXY_LEDGER),
            repo_rel(BASELINE_RESULT),
            repo_rel(Path(__file__)),
        ],
        "changed_files": [
            repo_rel(Path(__file__)),
            repo_rel(OUT_JSON),
            repo_rel(LEDGER_JSONL),
            repo_rel(LOG_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
        ],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {"used_javascript": False, "evidence": "Python runner only."},
    }


def compact_log_row(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "lane",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "hypothesis",
        "alpha_hypothesis",
        "change_summary",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "changed_variable",
        "single_causal_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "prediction",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "ledger_summary",
        "calibration",
        "production_impact",
        "post_run_reflection",
        "next_retry_requires",
        "related_files",
        "changed_files",
        "allowed_write_scope",
        "reproduction_commands",
        "anti_js",
    ]
    row = {key: payload[key] for key in keys}
    row["artifact"] = repo_rel(OUT_JSON)
    row["ledger"] = repo_rel(LEDGER_JSONL)
    row["log"] = repo_rel(LOG_JSON)
    return row


def build_card(payload: dict[str, Any]) -> str:
    summary = payload["ledger_summary"]
    delta = payload["delta_metrics"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: Recency Placebo Control Ledger",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Changed variable: `{CHANGED_VARIABLE}`",
            "",
            "## Result",
            "",
            f"- Estimate-revision rows: `{delta['estimate_revision_rows']}`",
            f"- Usable join coverage: `{delta['usable_join_coverage']}`",
            f"- Usable bucket coverage: `{delta['usable_bucket_coverage']}`",
            f"- Price-date-after-asof rows: `{delta['price_date_after_asof_rows']}`",
            "",
            "## Bucket Counts",
            "",
            f"- 20d: `{summary['rank_20d_bucket_counts']}`",
            f"- 60d: `{summary['rank_60d_bucket_counts']}`",
            f"- 120d: `{summary['rank_120d_bucket_counts']}`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Next Evidence",
            "",
            payload["post_run_reflection"]["new_evidence_required"],
            "",
            "## Reproduce",
            "",
            "```powershell",
            *payload["reproduction_commands"],
            "```",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any], log_row: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LEDGER_JSONL,
        LOG_JSON,
        TICKET_JSON,
        CARD_MD,
        MANIFEST_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        ESTIMATE_REVISION_LEDGER,
        RS_PROXY_LEDGER,
        BASELINE_RESULT,
    ]
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "ledger": repo_rel(LEDGER_JSONL),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256_file(path)}
            for path in files
        },
        "log_row_sha256": hashlib.sha256(
            json.dumps(safe(log_row), sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    log_row = compact_log_row(payload)
    write_json(OUT_JSON, payload)
    write_jsonl(LEDGER_JSONL, payload["ledger_rows"])
    write_json(LOG_JSON, log_row)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_row)
    result = {
        "accepted": bool(payload["accepted"]),
        "accepted_alpha": False,
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "ledger": repo_rel(LEDGER_JSONL),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "delta_metrics": payload["delta_metrics"],
        "ledger_summary": payload["ledger_summary"],
        "calibration": payload["calibration"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "alpha_hypothesis": ALPHA_HYPOTHESIS,
            "change_type": payload["change_type"],
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "new_evidence_axis": payload["new_evidence_axis"],
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "evaluation_windows": [{"label": label, **cfg} for label, cfg in WINDOWS.items()],
            "acceptance_rule": payload["pre_run_questions"]["4_acceptance_standard"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "decision": payload["decision"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
            "artifact": repo_rel(OUT_JSON),
            "ledger": repo_rel(LEDGER_JSONL),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "post_run_reflection": payload["post_run_reflection"],
            "production_impact": payload["production_impact"],
            "reproduction_commands": payload["reproduction_commands"],
            "changed_files": payload["changed_files"],
            "anti_js": payload["anti_js"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload, log_row))


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(json.dumps(safe(compact_log_row(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
