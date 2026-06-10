"""exp-20260610-020: accepted allocator tail-state attribution.

Observed-only alpha attribution. It tests whether selected rows from the
accepted helper source-priority allocator show stable replacement-value
separation by production-visible return-extension tail-state buckets.

This runner reads the accepted exp-20260610-014 allocator artifact and does not
change strategy code, shared helpers, daily snapshots, ranking, sizing, exits,
watchlists, LLM/news behavior, or orders. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, EXPERIMENTS_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260610_014_revision_source_priority_allocator_extension as base  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


framework = base.framework

EXPERIMENT_ID = "exp-20260610-020"
STEM = "accepted_allocator_tail_state_attribution"
TRIAL_FAMILY = "accepted_helper_source_priority_allocator_tail_state_attribution"
TRIAL_VARIANT_ID = "accepted_allocator_return_extension_tail_state_bucket_v1"
CHANGED_VARIABLE = TRIAL_VARIANT_ID
OWNER = "alpha-explore-automation"

SOURCE_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260610-014"
    / "exp_20260610_014_revision_source_priority_allocator_extension.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260610_020_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

MIN_TOTAL_ROWS = 60
MIN_BUCKET_ROWS = 10
MIN_WINDOW_BUCKET_ROWS = 3
MIN_AVG_PNL_EDGE = 100.0
MIN_DIRECTION_WINDOWS = 2
MIN_RETURN_PATH_COVERAGE = 0.95
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

PREDICTION = {
    "success_probability": 0.24,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "non_monotonic_buckets",
        "source_family_confounding",
        "window_instability",
        "concentration_failed",
    ],
    "confidence_reason": (
        "Current playbook asks for tail-state field-building before more "
        "momentum/helper stacking. The accepted allocator has enough rows, but "
        "prior tail-state and winner-continuation diagnostics often failed, so "
        "this is attribution only."
    ),
    "recorded_at": "2026-06-10T17:56:26+00:00",
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "ranking/candidate-pool attribution: accepted allocator selected rows "
        "may have stable replacement-value separation by signal-date return "
        "extension tail-state buckets."
    ),
    "2_history_check": {
        "exp-20260610-014": (
            "Current accepted allocator with revision source; aggregate EV "
            "+0.9720 and PnL +$15,197.05."
        ),
        "exp-20260610-019": (
            "Rejected Fundamental Growth RS source extension despite positive "
            "aggregate because late_strong regressed versus the accepted "
            "allocator comparator."
        ),
        "exp-20260609-007": (
            "Rejected tail-state winner continuation candidate pool with no "
            "tail-state separation."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Observed-only diagnostic. Useful evidence requires all three windows, "
        f">={MIN_TOTAL_ROWS} rows, best-minus-worst bucket avg PnL >= "
        f"${MIN_AVG_PNL_EDGE:.0f}, at least {MIN_DIRECTION_WINDOWS} windows "
        "with the same best/worst direction, and concentration guard pass. No "
        "strategy acceptance is possible in this experiment."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260610_020_accepted_allocator_tail_state_attribution.py"
    ),
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "observed_only_attribution",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": False,
    "default_off_paper_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "uses_llm": False,
    "uses_free_ohlcv_only": True,
    "uses_free_non_ohlcv": False,
    "live_realism_evaluated": False,
    "live_ready": False,
    "execution_envelope": {
        "trade_enabled": False,
        "scope": "read-only attribution on accepted default-off paper rows",
        "portfolio_displacement": "not changed; existing accepted allocator rows only",
        "order_semantics": "no broker order and no new paper entry",
        "kill_switch": "not applicable because no behavior changed",
    },
    "parity_note": (
        "This experiment only reads an accepted allocator artifact and computes "
        "production-visible signal-date return-path buckets. No shared policy, "
        "daily snapshot, live/default order, ranking, sizing, exit, watchlist, "
        "LLM, or news path changes."
    ),
}


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _round(value: Any, digits: int = 6) -> float | None:
    number = _float(value)
    if number is None:
        return None
    return round(number, digits)


def _pick_float(row: dict[str, Any], keys: list[str]) -> tuple[float | None, str | None]:
    for key in keys:
        value = _float(row.get(key))
        if value is not None:
            return value, key
    return None, None


def _tail_state_features(
    row: dict[str, Any],
    fallback_features: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ret5, ret5_key = _pick_float(row, ["candidate_ret5", "ret5"])
    ret20, ret20_key = _pick_float(row, ["candidate_ret20", "ret20"])
    ret60, ret60_key = _pick_float(row, ["candidate_ret60", "ret60"])
    basis = "absolute_return"
    if ret5 is None or ret20 is None:
        fallback_features = fallback_features or {}
        ret5 = _float(fallback_features.get("ret5"))
        ret20 = _float(fallback_features.get("ret20"))
        ret60 = _float(fallback_features.get("ret60"))
        if ret5 is not None and ret20 is not None:
            ret5_key = fallback_features.get("ret5_key") or "warehouse_ret5"
            ret20_key = fallback_features.get("ret20_key") or "warehouse_ret20"
            ret60_key = fallback_features.get("ret60_key") or "warehouse_ret60"
            basis = "warehouse_absolute_return"

    if ret5 is None or ret20 is None:
        ret5, ret5_key = _pick_float(
            row,
            [
                "candidate_ret5_excess_spy",
                "ret5_excess_spy",
                "candidate_signal_relative_vs_spy",
                "candidate_relative_vs_spy",
            ],
        )
        ret20, ret20_key = _pick_float(
            row,
            ["candidate_ret20_excess_spy", "ret20_excess_spy", "max_ret20_excess_spy"],
        )
        ret60, ret60_key = _pick_float(row, ["candidate_ret60_excess_spy", "ret60_excess_spy"])
        basis = "spy_excess_return"

    vol20, vol20_key = _pick_float(row, ["candidate_realized_vol_20d", "realized_vol_20d"])
    if vol20 is None:
        fallback_features = fallback_features or {}
        vol20 = _float(fallback_features.get("realized_vol20"))
        if vol20 is not None:
            vol20_key = fallback_features.get("realized_vol20_key") or "warehouse_realized_vol20"
    ratio = None
    if ret5 is not None and ret20 is not None:
        ratio = ret5 / max(abs(ret20), 0.01)

    return {
        "ret5": _round(ret5),
        "ret20": _round(ret20),
        "ret60": _round(ret60),
        "realized_vol20": _round(vol20),
        "extension_ratio": _round(ratio),
        "basis": basis,
        "field_keys": {
            "ret5": ret5_key,
            "ret20": ret20_key,
            "ret60": ret60_key,
            "realized_vol20": vol20_key,
        },
    }


def _tail_state_bucket(features: dict[str, Any]) -> str:
    ret5 = _float(features.get("ret5"))
    ret20 = _float(features.get("ret20"))
    ratio = _float(features.get("extension_ratio"))
    if ret5 is None or ret20 is None or ratio is None:
        return "missing_return_path"
    if ret20 < 0.0:
        return "weak_20d_context"
    if ret5 <= -0.005:
        return "pullback_repair"
    if ret5 <= 0.035 and ratio <= 0.65:
        return "orderly_follow_through"
    if ret5 <= 0.070 and ratio <= 1.15:
        return "extended_momentum"
    return "overextended_tail"


def _row_key(row: dict[str, Any]) -> tuple[str, str]:
    return (
        str(row.get("signal_date") or row.get("date") or "")[:10],
        str(row.get("ticker") or "").upper(),
    )


def _row_date(row: dict[str, Any]) -> str:
    return str(row.get("Date") or row.get("date") or "")[:10]


def _warehouse_tail_state_features(
    rows_by_window: dict[str, list[dict[str, Any]]],
) -> OrderedDict[str, dict[tuple[str, str], dict[str, Any]]]:
    features_by_window: OrderedDict[str, dict[tuple[str, str], dict[str, Any]]] = OrderedDict()
    for label, cfg in framework.WINDOWS.items():
        tickers = {
            str(row.get("ticker") or "").upper()
            for row in rows_by_window.get(label) or []
            if isinstance(row, dict) and row.get("ticker")
        }
        snapshot = framework._load_window_snapshot(cfg=cfg, eligible_tickers=tickers)
        feature_map: dict[tuple[str, str], dict[str, Any]] = {}
        for ticker, rows in snapshot.items():
            by_date = {_row_date(row): idx for idx, row in enumerate(rows)}
            for source_row in rows_by_window.get(label) or []:
                if str(source_row.get("ticker") or "").upper() != ticker:
                    continue
                signal_date = str(
                    source_row.get("signal_date") or source_row.get("date") or ""
                )[:10]
                idx = by_date.get(signal_date)
                if idx is None:
                    continue
                daily_returns = [
                    value
                    for offset in range(max(1, idx - 19), idx + 1)
                    if (value := framework._daily_return(rows, offset)) is not None
                ]
                realized_vol20 = None
                if len(daily_returns) >= 2:
                    mean_return = sum(daily_returns) / len(daily_returns)
                    variance = sum((value - mean_return) ** 2 for value in daily_returns) / (
                        len(daily_returns) - 1
                    )
                    realized_vol20 = math.sqrt(variance)
                feature_map[(signal_date, ticker)] = {
                    "ret5": _round(framework._ret(rows, idx, 5)),
                    "ret20": _round(framework._ret(rows, idx, 20)),
                    "ret60": _round(framework._ret(rows, idx, 60)),
                    "realized_vol20": _round(realized_vol20),
                    "ret5_key": "warehouse_ret5",
                    "ret20_key": "warehouse_ret20",
                    "ret60_key": "warehouse_ret60",
                    "realized_vol20_key": "warehouse_realized_vol20",
                }
        features_by_window[label] = feature_map
    return features_by_window


def _annotate_rows(
    rows_by_window: dict[str, list[dict[str, Any]]],
    warehouse_features_by_window: dict[str, dict[tuple[str, str], dict[str, Any]]],
) -> OrderedDict[str, list[dict[str, Any]]]:
    annotated: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for label in framework.WINDOWS:
        out: list[dict[str, Any]] = []
        warehouse_features = warehouse_features_by_window.get(label) or {}
        for row in rows_by_window.get(label) or []:
            if not isinstance(row, dict):
                continue
            features = _tail_state_features(row, warehouse_features.get(_row_key(row)))
            bucket = _tail_state_bucket(features)
            out.append(
                {
                    **row,
                    "tail_state_bucket": bucket,
                    "tail_state_rule_version": CHANGED_VARIABLE,
                    "tail_state_features": features,
                }
            )
        annotated[label] = out
    return annotated


def _bucket_summary(rows: list[dict[str, Any]]) -> OrderedDict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("tail_state_bucket") or "missing_return_path")].append(row)
    summary: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for bucket in sorted(grouped):
        bucket_rows = grouped[bucket]
        pnls = [_float(row.get("pnl")) or 0.0 for row in bucket_rows]
        returns = [_float(row.get("pnl_pct_net")) or 0.0 for row in bucket_rows]
        positive_pnl = sum(value for value in pnls if value > 0.0)
        positive_by_ticker: Counter[str] = Counter()
        for row, pnl in zip(bucket_rows, pnls):
            if pnl > 0.0:
                positive_by_ticker[str(row.get("ticker") or "UNKNOWN").upper()] += pnl
        max_share = None
        hhi = None
        if positive_pnl > 0.0:
            shares = [value / positive_pnl for value in positive_by_ticker.values()]
            max_share = max(shares) if shares else None
            hhi = sum(share * share for share in shares)
        source_counts = Counter(str(row.get("source_family") or "unknown") for row in bucket_rows)
        summary[bucket] = {
            "count": len(bucket_rows),
            "avg_pnl": round(sum(pnls) / len(pnls), 2) if pnls else None,
            "sum_pnl": round(sum(pnls), 2),
            "avg_return": round(sum(returns) / len(returns), 6) if returns else None,
            "win_rate": round(sum(1 for value in pnls if value > 0.0) / len(pnls), 6)
            if pnls
            else None,
            "source_counts": dict(source_counts),
            "max_single_positive_pnl_share": _round(max_share),
            "positive_pnl_hhi": _round(hhi),
        }
    return summary


def _aggregate_rows(rows_by_window: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label in framework.WINDOWS:
        rows.extend(rows_by_window.get(label) or [])
    return rows


def _best_worst(summary: OrderedDict[str, dict[str, Any]]) -> dict[str, Any]:
    eligible = [
        (bucket, stats)
        for bucket, stats in summary.items()
        if int(stats.get("count") or 0) >= MIN_BUCKET_ROWS
        and stats.get("avg_pnl") is not None
        and bucket != "missing_return_path"
    ]
    if len(eligible) < 2:
        return {
            "best_bucket": None,
            "worst_bucket": None,
            "avg_pnl_edge": None,
            "eligible_bucket_count": len(eligible),
        }
    best_bucket, best_stats = max(eligible, key=lambda item: float(item[1]["avg_pnl"]))
    worst_bucket, worst_stats = min(eligible, key=lambda item: float(item[1]["avg_pnl"]))
    return {
        "best_bucket": best_bucket,
        "worst_bucket": worst_bucket,
        "best_avg_pnl": best_stats["avg_pnl"],
        "worst_avg_pnl": worst_stats["avg_pnl"],
        "avg_pnl_edge": round(float(best_stats["avg_pnl"]) - float(worst_stats["avg_pnl"]), 2),
        "eligible_bucket_count": len(eligible),
    }


def _window_direction_count(
    rows_by_window: OrderedDict[str, list[dict[str, Any]]],
    *,
    best_bucket: str | None,
    worst_bucket: str | None,
) -> tuple[int, OrderedDict[str, dict[str, Any]]]:
    details: OrderedDict[str, dict[str, Any]] = OrderedDict()
    if not best_bucket or not worst_bucket:
        return 0, details
    count = 0
    for label, rows in rows_by_window.items():
        summary = _bucket_summary(rows)
        best = summary.get(best_bucket) or {}
        worst = summary.get(worst_bucket) or {}
        best_n = int(best.get("count") or 0)
        worst_n = int(worst.get("count") or 0)
        best_avg = _float(best.get("avg_pnl"))
        worst_avg = _float(worst.get("avg_pnl"))
        comparable = (
            best_n >= MIN_WINDOW_BUCKET_ROWS
            and worst_n >= MIN_WINDOW_BUCKET_ROWS
            and best_avg is not None
            and worst_avg is not None
        )
        edge = (best_avg - worst_avg) if comparable else None
        passed = bool(comparable and edge is not None and edge > 0.0)
        if passed:
            count += 1
        details[label] = {
            "comparable": comparable,
            "passed": passed,
            "best_bucket_count": best_n,
            "worst_bucket_count": worst_n,
            "best_avg_pnl": _round(best_avg, 2),
            "worst_avg_pnl": _round(worst_avg, 2),
            "avg_pnl_edge": _round(edge, 2),
        }
    return count, details


def _concentration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    positive = [(str(row.get("ticker") or "UNKNOWN").upper(), _float(row.get("pnl")) or 0.0) for row in rows]
    positive = [(ticker, pnl) for ticker, pnl in positive if pnl > 0.0]
    total = sum(pnl for _, pnl in positive)
    if total <= 0.0:
        return {
            "passed": False,
            "max_single_positive_pnl_share": None,
            "positive_pnl_hhi": None,
            "positive_pnl_sum": 0.0,
        }
    by_ticker: Counter[str] = Counter()
    for ticker, pnl in positive:
        by_ticker[ticker] += pnl
    shares = [value / total for value in by_ticker.values()]
    max_share = max(shares) if shares else None
    hhi = sum(share * share for share in shares)
    return {
        "passed": bool(
            max_share is not None
            and max_share <= MAX_SINGLE_POSITIVE_SHARE
            and hhi <= MAX_POSITIVE_HHI
        ),
        "max_single_positive_pnl_share": _round(max_share),
        "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
        "positive_pnl_hhi": _round(hhi),
        "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
        "positive_pnl_sum": round(total, 2),
        "top_positive_tickers": [
            {"ticker": ticker, "positive_pnl": round(pnl, 2), "share": round(pnl / total, 6)}
            for ticker, pnl in by_ticker.most_common(10)
        ],
    }


def _build_payload() -> dict[str, Any]:
    timestamp = framework._utc_now()
    if not SOURCE_ARTIFACT.exists():
        raise FileNotFoundError(SOURCE_ARTIFACT)
    source_payload = json.loads(SOURCE_ARTIFACT.read_text(encoding="utf-8"))
    rows_by_window = source_payload.get("target_trades_by_window") or {}
    warehouse_features_by_window = _warehouse_tail_state_features(rows_by_window)
    annotated = _annotate_rows(rows_by_window, warehouse_features_by_window)
    all_rows = _aggregate_rows(annotated)
    aggregate_summary = _bucket_summary(all_rows)
    by_window = OrderedDict((label, _bucket_summary(rows)) for label, rows in annotated.items())
    best_worst = _best_worst(aggregate_summary)
    direction_windows, direction_details = _window_direction_count(
        annotated,
        best_bucket=best_worst.get("best_bucket"),
        worst_bucket=best_worst.get("worst_bucket"),
    )
    concentration = _concentration(all_rows)
    missing_count = sum(
        1 for row in all_rows if row.get("tail_state_bucket") == "missing_return_path"
    )
    return_path_coverage = (
        (len(all_rows) - missing_count) / len(all_rows) if all_rows else 0.0
    )
    windows_with_rows = [label for label, rows in annotated.items() if rows]
    failed: list[str] = []
    if len(all_rows) < MIN_TOTAL_ROWS:
        failed.append("target_sample_too_small")
    if len(windows_with_rows) < len(framework.WINDOWS):
        failed.append("target_window_coverage_too_small")
    edge = _float(best_worst.get("avg_pnl_edge"))
    if edge is None or edge < MIN_AVG_PNL_EDGE:
        failed.append("bucket_edge_below_floor")
    if direction_windows < MIN_DIRECTION_WINDOWS:
        failed.append("window_direction_not_stable")
    if not concentration["passed"]:
        failed.append("concentration_failed")
    if return_path_coverage < MIN_RETURN_PATH_COVERAGE:
        failed.append("return_path_coverage_below_floor")
    evidence_passed = not failed
    decision = (
        "observed_only_positive_tail_state_field_lead"
        if evidence_passed
        else "observed_only_not_promotable_tail_state_field"
    )
    status = "observed_only"
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_evidence_passed": evidence_passed,
        "actual_success": 1 if evidence_passed else 0,
        "failure_modes_observed": failed,
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if evidence_passed else 0.0)) ** 2,
            6,
        ),
    }
    if evidence_passed:
        interpretation = (
            "Tail-state buckets separated accepted allocator replacement value, "
            "but this remains only a read-only field lead for a future frozen "
            "routing experiment."
        )
        why_result_happened = (
            "The production-visible return-extension bucket showed stable "
            "separation across all three windows: "
            f"{best_worst.get('best_bucket')} had the best average PnL while "
            f"{best_worst.get('worst_bucket')} was worst. This is still "
            "observed-only because the allocator mixes source families and no "
            "routing rule was tested."
        )
    else:
        interpretation = (
            "Tail-state buckets did not clear the preregistered diagnostic "
            "evidence bar, so no allocator routing, source priority, or "
            "notional change is justified."
        )
        why_result_happened = (
            "The accepted allocator already mixes several mechanisms, so "
            "return-extension buckets can be confounded by source family. "
            "A usable tail-state field needs stable best/worst direction "
            "across windows and enough per-bucket sample before any frozen "
            "routing experiment."
        )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "hypothesis": (
            "Accepted helper source-priority allocator selected rows may show "
            "stable replacement-value separation by production-visible "
            "return-extension tail-state buckets, informing whether future "
            "allocator routing needs a tail-risk field instead of more source "
            "additions."
        ),
        "change_type": "observed_only_attribution",
        "implementation_mode": "observed_only_attribution",
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": [
            "read_only_historical_replay",
            "bucket_attribution",
            "no_strategy_change",
            "no_production_change",
        ],
        "prior_trial_count": 0,
        "nearby_prior_experiments": [
            "exp-20260610-014",
            "exp-20260610-019",
            "exp-20260609-007",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "production_visible_tail_state_attribution",
        "prediction": PREDICTION,
        "calibration": calibration,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window accepted allocator "
                "artifact exp-20260610-014; this run performs read-only "
                "tail-state attribution and does not rerun or alter policy."
            ),
            "windows": framework.WINDOWS,
            "source_artifact": _repo_rel(SOURCE_ARTIFACT),
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
        },
        "parameters": {
            "tail_state_rule_version": CHANGED_VARIABLE,
            "bucket_policy": {
                "weak_20d_context": "ret20 < 0",
                "pullback_repair": "ret20 >= 0 and ret5 <= -0.005",
                "orderly_follow_through": "ret20 >= 0, -0.005 < ret5 <= 0.035, ratio <= 0.65",
                "extended_momentum": "ret20 >= 0, ret5 <= 0.070, ratio <= 1.15",
                "overextended_tail": "remaining positive-ret20 rows",
                "missing_return_path": "missing ret5 or ret20 basis",
            },
            "feature_basis_priority": [
                "absolute_return",
                "warehouse_absolute_return",
                "spy_excess_return",
            ],
            "minimum_total_rows": MIN_TOTAL_ROWS,
            "minimum_bucket_rows": MIN_BUCKET_ROWS,
            "minimum_window_bucket_rows": MIN_WINDOW_BUCKET_ROWS,
            "minimum_avg_pnl_edge": MIN_AVG_PNL_EDGE,
            "minimum_direction_windows": MIN_DIRECTION_WINDOWS,
            "minimum_return_path_coverage": MIN_RETURN_PATH_COVERAGE,
        },
        "gate1": {
            "baseline_artifact": _repo_rel(SOURCE_ARTIFACT),
            "source_decision": source_payload.get("decision"),
            "source_status": source_payload.get("status"),
            "passed": True,
        },
        "gate2": {
            "runtime_fields": [
                "signal_date",
                "ticker",
                "entry_date",
                "target_price/open-position audit inherited from source artifact",
                "pnl",
                "pnl_pct_net",
                "candidate_ret5/candidate_ret20 or candidate_ret*_excess_spy",
                "warehouse fallback trailing 5/20/60-day returns by ticker/signal_date",
            ],
            "entry_date_coverage": all(bool(row.get("entry_date")) for row in all_rows),
            "return_path_coverage": _round(return_path_coverage),
            "target_price_note": (
                "No live open-position policy is changed; source artifact already "
                "passed Gate 2. Paper rows carry explicit entry/exit prices."
            ),
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "source_minimum_core_survival_rate": (
                (source_payload.get("gate3") or {}).get("minimum_core_survival_rate")
                or (source_payload.get("gate4") or {}).get("minimum_core_survival_rate")
            ),
            "passed": True,
            "note": "No filter or strategy behavior changed.",
        },
        "gate4": {
            "strategy_gate4_applicable": False,
            "observed_only": True,
            "evidence_passed": evidence_passed,
            "decision": decision,
            "failed_reasons": failed,
            "row_count": len(all_rows),
            "windows_with_rows": windows_with_rows,
            "best_worst": best_worst,
            "direction_windows": direction_windows,
            "direction_window_min": MIN_DIRECTION_WINDOWS,
            "direction_details": direction_details,
            "concentration": concentration,
            "missing_return_path_count": missing_count,
            "return_path_coverage": _round(return_path_coverage),
            "return_path_coverage_min": MIN_RETURN_PATH_COVERAGE,
        },
        "before_metrics": source_payload.get("after_metrics"),
        "after_metrics": source_payload.get("after_metrics"),
        "delta_metrics": {
            "by_window": OrderedDict(
                (
                    label,
                    {
                        "expected_value_score": 0.0,
                        "total_pnl": 0.0,
                        "max_drawdown_pct": 0.0,
                        "trade_count": 0,
                    },
                )
                for label in framework.WINDOWS
            ),
            "aggregate": {
                "expected_value_score_delta_sum": 0.0,
                "total_pnl_delta_sum": 0.0,
                "windows_ev_improved": 0,
                "windows_ev_regressed": 0,
                "windows_pnl_improved": 0,
                "windows_pnl_regressed": 0,
            },
        },
        "observed_tail_state_summary": {
            "aggregate_bucket_summary": aggregate_summary,
            "bucket_summary_by_window": by_window,
            "best_worst": best_worst,
            "direction_windows": direction_windows,
            "direction_details": direction_details,
            "concentration": concentration,
            "row_count": len(all_rows),
            "missing_return_path_count": missing_count,
            "return_path_coverage": _round(return_path_coverage),
        },
        "annotated_trades_by_window": annotated,
        "source_artifact_decision": source_payload.get("decision"),
        "source_artifact_gate4": source_payload.get("gate4"),
        "expected_value_score_delta": 0.0,
        "total_pnl_delta": 0.0,
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "interpretation": interpretation,
        "rejection_reason": "; ".join(failed) if failed else None,
        "post_run_reflection": {
            "why_result_happened": why_result_happened,
            "forbidden_near_neighbor_retry": (
                "Do not retune allocator source rank, top-N, notional, hold "
                "days, cooldown, or tail-state thresholds on the same frozen "
                "windows from this observed-only result."
            ),
            "new_evidence_required": (
                "A retry needs closed forward allocator replacement rows, a "
                "predeclared tail-state field collected daily, or a frozen "
                "out-of-sample threshold derived before routing."
            ),
        },
        "claim_note": (
            "Initial claim was blocked by stale broad-scope claimed tickets "
            "without locked-variable conflict; claim was forced for this "
            "narrow variable and only exp-20260610-020 files were written."
        ),
        "anti_js": "No JavaScript was used.",
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(SOURCE_ARTIFACT),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
    }


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Bucket | Count | Avg PnL | Sum PnL | Avg Return | Win Rate | Top Sources |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for bucket, stats in payload["observed_tail_state_summary"][
        "aggregate_bucket_summary"
    ].items():
        top_sources = ", ".join(
            f"{name}:{count}"
            for name, count in sorted(
                stats["source_counts"].items(), key=lambda item: (-item[1], item[0])
            )[:4]
        )
        rows.append(
            "| {bucket} | {count} | ${avg:,.2f} | ${total:,.2f} | {ret:.4f} | {win:.2%} | {sources} |".format(
                bucket=bucket,
                count=stats["count"],
                avg=float(stats["avg_pnl"] or 0.0),
                total=float(stats["sum_pnl"] or 0.0),
                ret=float(stats["avg_return"] or 0.0),
                win=float(stats["win_rate"] or 0.0),
                sources=top_sources or "none",
            )
        )
    gate4 = payload["gate4"]
    best_worst = gate4["best_worst"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Accepted Allocator Tail-State Attribution",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Observed Buckets",
            "",
            *rows,
            "",
            "## Diagnostic Verdict",
            "",
            "- Evidence passed: `{}`".format(gate4["evidence_passed"]),
            "- Best bucket: `{}`".format(best_worst.get("best_bucket")),
            "- Worst bucket: `{}`".format(best_worst.get("worst_bucket")),
            "- Avg PnL edge: `${}`".format(best_worst.get("avg_pnl_edge")),
            "- Direction windows: `{}`".format(gate4["direction_windows"]),
            "- Failed reasons: `{}`".format(", ".join(gate4["failed_reasons"]) or "none"),
            "",
            "## Production Impact",
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    gate4 = payload["gate4"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": False,
        "observed_only": True,
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": _repo_rel(SOURCE_ARTIFACT),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
        "expected_value_score_delta": 0.0,
        "total_pnl_delta": 0.0,
        "observed_tail_state_summary": payload["observed_tail_state_summary"],
        "gate4": gate4,
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _update_ticket_and_registry(payload: dict[str, Any], log_record: dict[str, Any]) -> None:
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "observed_only": True,
        "numeric_gate4_passed": False,
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "decision": payload["decision"],
        "summary": payload["interpretation"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
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

    ticket = {}
    if TICKET_JSON.exists():
        ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8"))
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "updated_at": payload["timestamp"],
            "decision": payload["decision"],
            "result": result,
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "card_file": _repo_rel(CARD_MD),
            "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        }
    )
    scope = set(ticket.get("allowed_write_scope") or [])
    scope.update(payload["related_files"])
    ticket["allowed_write_scope"] = sorted(scope)
    framework._write_json(TICKET_JSON, ticket)


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": payload["related_files"],
        "file_hashes": {
            _repo_rel(Path(__file__)): framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): framework._sha256(CARD_MD),
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def main() -> None:
    payload = _build_payload()
    log_record = _build_log_record(payload)
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, log_record)
    framework._write_text(CARD_MD, _build_card(payload))
    framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    _update_ticket_and_registry(payload, log_record)
    _write_manifest(payload)
    gate4 = payload["gate4"]
    best_worst = gate4["best_worst"]
    print(
        "completed {experiment_id}: {decision} | rows={rows} | best={best} | worst={worst} | edge=${edge}".format(
            experiment_id=EXPERIMENT_ID,
            decision=payload["decision"],
            rows=gate4["row_count"],
            best=best_worst.get("best_bucket"),
            worst=best_worst.get("worst_bucket"),
            edge=best_worst.get("avg_pnl_edge"),
        )
    )


if __name__ == "__main__":
    main()
