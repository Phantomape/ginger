"""exp-20260609-021: exact displacement audit for the consensus state lead.

Observed-only alpha_search. This rebuilds the accepted default-off sleeve rows
from exp-20260606-022 and tests one fixed follow-up question: whether the
ACCEPTED_FREE_DATA_CROSS_SOURCE_CONSENSUS_PAPER rows in the
mixed|balanced|normal state beat same-entry-date accepted-sleeve alternatives
or cash after normalizing to PnL per $10k.

No strategy, shared helper, report, ranking, sizing, exit, watchlist, or order
path is changed.
"""

from __future__ import annotations

import json
import math
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
for path in (
    REPO_ROOT / "quant",
    REPO_ROOT / "quant" / "experiments",
    REPO_ROOT / "scripts",
):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260606_022_market_state_accepted_sleeve_replacement_value_attribution as prior  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260609-021"
STEM = "consensus_state_exact_displacement"
TARGET_SLEEVE = "ACCEPTED_FREE_DATA_CROSS_SOURCE_CONSENSUS_PAPER"
TARGET_STATE = "mixed|balanced|normal"
TRIAL_FAMILY = "market_state_sleeve_exact_displacement"
TRIAL_VARIANT_ID = "consensus_mixed_balanced_normal_same_entry_displacement_v1"
CHANGED_VARIABLE = "accepted_consensus_mixed_balanced_normal_exact_displacement_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260609_021_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

MIN_TARGET_ROWS = 30
MIN_ALT_ROWS = 10
MIN_ALT_WINDOWS = 2
MIN_POSITIVE_WINDOWS = 2
MAX_SINGLE_TICKER_POSITIVE_SHARE = 0.50
MAX_TOP5_POSITIVE_SHARE = 0.60
MAX_POSITIVE_HHI = 0.35

PREDICTION = {
    "success_probability": 0.24,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "same_date_alternatives_beat_consensus",
        "thin_same_day_comparator",
        "single_ticker_concentration",
        "state_edge_already_captured_by_existing_sleeve",
    ],
    "confidence_reason": (
        "The exp-20260606-022 leading cell had 39 trades and positive 3-window "
        "state contrast, but it was observed-only and top ticker concentration "
        "around APP/MU may collapse under exact same-date displacement accounting."
    ),
    "recorded_at": "2026-06-09T18:01:10+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "diagnostic_only": True,
    "replay_only": True,
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "daily_snapshot_exposed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "alters_orders": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "parity_test_added": False,
    "parity_note": (
        "This run only rebuilds accepted historical default-off paper rows and "
        "compares normalized outcomes. Any router or allocation use would need a "
        "separate shared Gate 1-4 experiment."
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value]
    if isinstance(value, Counter):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, Path):
        return _repo_rel(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return round(value, 10)
    return value


def _repo_rel(path: Path | str) -> str:
    p = Path(path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    return p.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _sha(path: Path) -> str | None:
    if not path.exists():
        return None
    return sha256(path.read_bytes()).hexdigest()


def _upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(_safe(record), ensure_ascii=True, sort_keys=True)
    lines: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                lines.append(raw)
                continue
            if existing.get("experiment_id") == record["experiment_id"]:
                lines.append(encoded)
                replaced = True
            else:
                lines.append(json.dumps(existing, ensure_ascii=True, sort_keys=True))
    if not replaced:
        lines.append(encoded)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _mean(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


def _sum(values: list[float]) -> float:
    return float(sum(values))


def _load_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    snapshots = {
        label: prior._load_snapshot(cfg["snapshot"])
        for label, cfg in prior.WINDOWS.items()
    }
    trading_dates_by_window = {
        label: prior._trading_dates(snapshot)
        for label, snapshot in snapshots.items()
    }

    rows: list[dict[str, Any]] = []
    reports: list[dict[str, Any]] = []
    for spec in prior.SOURCE_SPECS:
        extracted, report = prior._extract_source_rows(
            spec, snapshots, trading_dates_by_window
        )
        rows.extend(extracted)
        reports.append(report)
    return rows, reports


def _positive_concentration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_ticker: dict[str, float] = defaultdict(float)
    for row in rows:
        delta = float(row.get("displacement_delta_per_10k") or 0.0)
        if delta > 0:
            by_ticker[str(row.get("ticker") or "")] += delta
    total = sum(by_ticker.values())
    if total <= 0:
        return {
            "positive_displacement_total": 0.0,
            "max_single_ticker_positive_share": None,
            "top5_positive_share": None,
            "positive_hhi": None,
            "top_tickers": [],
            "passed": False,
            "failed_reasons": ["no_positive_displacement"],
        }
    shares = sorted((value / total for value in by_ticker.values()), reverse=True)
    result = {
        "positive_displacement_total": round(total, 2),
        "max_single_ticker_positive_share": round(shares[0], 6),
        "top5_positive_share": round(sum(shares[:5]), 6),
        "positive_hhi": round(sum(share * share for share in shares), 6),
        "top_tickers": [
            [ticker, round(value, 2), round(value / total, 6)]
            for ticker, value in sorted(by_ticker.items(), key=lambda item: -item[1])[:10]
        ],
        "thresholds": {
            "max_single_ticker_positive_share": MAX_SINGLE_TICKER_POSITIVE_SHARE,
            "max_top5_positive_share": MAX_TOP5_POSITIVE_SHARE,
            "max_positive_hhi": MAX_POSITIVE_HHI,
        },
    }
    failed = []
    if result["max_single_ticker_positive_share"] > MAX_SINGLE_TICKER_POSITIVE_SHARE:
        failed.append("single_ticker_concentration")
    if result["top5_positive_share"] > MAX_TOP5_POSITIVE_SHARE:
        failed.append("top5_concentration")
    if result["positive_hhi"] > MAX_POSITIVE_HHI:
        failed.append("positive_hhi_concentration")
    result["failed_reasons"] = failed
    result["passed"] = not failed
    return result


def _summarize_displacement(rows: list[dict[str, Any]]) -> dict[str, Any]:
    target = [float(row["target_pnl_per_10k"]) for row in rows]
    comparator = [float(row["comparator_avg_pnl_per_10k"]) for row in rows]
    delta = [float(row["displacement_delta_per_10k"]) for row in rows]
    strict = [float(row["strict_best_alt_delta_per_10k"]) for row in rows]
    alt_rows = [row for row in rows if int(row.get("alternative_count") or 0) > 0]
    alt_delta = [float(row["displacement_delta_per_10k"]) for row in alt_rows]
    return {
        "rows": len(rows),
        "rows_with_same_entry_alternatives": len(alt_rows),
        "cash_comparator_rows": len(rows) - len(alt_rows),
        "avg_target_pnl_per_10k": round(_mean(target) or 0.0, 2),
        "avg_comparator_pnl_per_10k": round(_mean(comparator) or 0.0, 2),
        "avg_displacement_delta_per_10k": round(_mean(delta) or 0.0, 2),
        "total_displacement_delta_per_10k": round(_sum(delta), 2),
        "positive_displacement_rate": round(sum(1 for value in delta if value > 0) / len(delta), 6)
        if delta
        else None,
        "avg_alt_only_displacement_delta_per_10k": round(_mean(alt_delta) or 0.0, 2)
        if alt_delta
        else None,
        "positive_alt_only_rate": round(sum(1 for value in alt_delta if value > 0) / len(alt_delta), 6)
        if alt_delta
        else None,
        "avg_strict_best_alt_delta_per_10k": round(_mean(strict) or 0.0, 2),
        "top_tickers": Counter(str(row.get("ticker") or "") for row in rows).most_common(10),
    }


def _build_displacement_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_entry: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_entry[(str(row.get("window") or ""), str(row.get("entry_date") or ""))].append(row)

    target_rows = [
        row
        for row in rows
        if row.get("sleeve") == TARGET_SLEEVE
        and row.get("combined_state") == TARGET_STATE
    ]
    displacement_rows = []
    for row in target_rows:
        key = (str(row.get("window") or ""), str(row.get("entry_date") or ""))
        alternatives = [
            alt
            for alt in by_entry[key]
            if alt.get("sleeve") != TARGET_SLEEVE
        ]
        alt_values = [float(alt.get("pnl_per_10k") or 0.0) for alt in alternatives]
        comparator = statistics.mean(alt_values) if alt_values else 0.0
        best_alt = max(alt_values) if alt_values else 0.0
        target_value = float(row.get("pnl_per_10k") or 0.0)
        displacement_rows.append(
            {
                "window": row.get("window"),
                "ticker": row.get("ticker"),
                "entry_date": row.get("entry_date"),
                "exit_date": row.get("exit_date"),
                "signal_date": row.get("signal_date"),
                "target_sleeve": row.get("sleeve"),
                "target_state": row.get("combined_state"),
                "target_pnl_per_10k": round(target_value, 2),
                "target_pnl_pct_net": row.get("pnl_pct_net"),
                "alternative_count": len(alternatives),
                "alternative_sleeves": sorted({str(alt.get("sleeve") or "") for alt in alternatives}),
                "alternative_tickers": sorted({str(alt.get("ticker") or "") for alt in alternatives}),
                "comparator_avg_pnl_per_10k": round(comparator, 2),
                "strict_best_alt_pnl_per_10k": round(best_alt, 2),
                "displacement_delta_per_10k": round(target_value - comparator, 2),
                "strict_best_alt_delta_per_10k": round(target_value - best_alt, 2),
                "cash_comparator": not alternatives,
                "row_fingerprint": row.get("row_fingerprint"),
            }
        )
    return displacement_rows


def _evaluate(displacement_rows: list[dict[str, Any]]) -> dict[str, Any]:
    aggregate = _summarize_displacement(displacement_rows)
    by_window = {
        window: _summarize_displacement(
            [row for row in displacement_rows if row.get("window") == window]
        )
        for window in prior.WINDOWS
    }
    positive_windows = sum(
        1
        for summary in by_window.values()
        if float(summary.get("avg_displacement_delta_per_10k") or 0.0) > 0
    )
    alt_windows = sum(
        1
        for summary in by_window.values()
        if int(summary.get("rows_with_same_entry_alternatives") or 0) > 0
    )
    concentration = _positive_concentration(displacement_rows)

    failed: list[str] = []
    if int(aggregate["rows"]) < MIN_TARGET_ROWS:
        failed.append("target_rows_below_floor")
    if int(aggregate["rows_with_same_entry_alternatives"]) < MIN_ALT_ROWS:
        failed.append("same_entry_alternative_rows_below_floor")
    if alt_windows < MIN_ALT_WINDOWS:
        failed.append("same_entry_alternative_window_coverage_below_floor")
    if float(aggregate["avg_displacement_delta_per_10k"]) <= 0:
        failed.append("aggregate_displacement_not_positive")
    if positive_windows < MIN_POSITIVE_WINDOWS:
        failed.append("too_few_positive_displacement_windows")
    if not concentration["passed"]:
        failed.extend(concentration["failed_reasons"])

    return {
        "passed": not failed,
        "decision": (
            "observed_only_positive_exact_displacement_lead"
            if not failed
            else "rejected_exact_displacement_not_confirmed"
        ),
        "failed_reasons": failed,
        "thresholds": {
            "min_target_rows": MIN_TARGET_ROWS,
            "min_same_entry_alternative_rows": MIN_ALT_ROWS,
            "min_same_entry_alternative_windows": MIN_ALT_WINDOWS,
            "min_positive_displacement_windows": MIN_POSITIVE_WINDOWS,
        },
        "aggregate": aggregate,
        "by_window": by_window,
        "positive_displacement_windows": positive_windows,
        "same_entry_alternative_windows": alt_windows,
        "concentration": concentration,
    }


def _build_payload() -> dict[str, Any]:
    timestamp = _utc_now()
    all_rows, source_reports = _load_rows()
    displacement_rows = _build_displacement_rows(all_rows)
    evaluation = _evaluate(displacement_rows)
    baseline = prior._baseline_summary()
    field_reality = prior._field_reality(source_reports)
    success = bool(evaluation["passed"])
    brier = (float(success) - float(PREDICTION["success_probability"])) ** 2

    status = evaluation["decision"]
    interpretation = (
        "Observed-only exact displacement confirms the prior state-sleeve lead "
        "survives same-entry-date accepted-sleeve alternatives. This is still "
        "not accepted strategy logic; it only justifies a later frozen shared "
        "router experiment or forward replacement-value monitoring."
        if success
        else (
            "Observed-only exact displacement does not confirm the prior "
            "state-sleeve lead strongly enough for a router. Do not retune the "
            "state bucket or accepted consensus thresholds on the frozen windows."
        )
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": status,
        "accepted": False,
        "diagnostic_only": True,
        "hypothesis": (
            "Accepted free-data consensus paper rows in the exp-20260606-022 "
            "mixed balanced normal market-state cell may have true router "
            "replacement value only if they beat same-entry-date accepted-sleeve "
            "alternatives or cash after costs."
        ),
        "change_type": "observed_only_attribution",
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": [
            "row rebuild from accepted artifacts",
            "exact same-entry-date displacement comparator",
            "concentration audit",
            "observed-only artifact",
        ],
        "prior_trial_count": 1,
        "nearby_prior_experiments": [
            "exp-20260606-022",
            "exp-20260604-009",
            "exp-20260608-021",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "exact_displacement_accounting",
        "prediction": PREDICTION,
        "calibration": {
            "actual_success": int(success),
            "predicted_success_probability": PREDICTION["success_probability"],
            "brier_score": round(brier, 6),
            "failure_modes_observed": evaluation["failed_reasons"],
            "calibration_direction": (
                "underconfident" if success and PREDICTION["success_probability"] < 0.5
                else "directionally_calibrated"
            ),
            "surprise_note": (
                "The prior state cell survived exact same-date displacement."
                if success
                else "Exact displacement or concentration gates blocked the prior state-cell lead."
            ),
        },
        "production_impact": PRODUCTION_IMPACT,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical windows plus accepted default-off "
                "paper sleeve replay artifacts from exp-20260606-022 sources"
            ),
            "baseline_result_file": _repo_rel(prior.BASELINE_RESULT_FILE),
            "windows": prior.WINDOWS,
            "state_timing": "prior_trading_day_close_before_entry_open",
            "execution_impact": "none_observed_only_attribution",
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "risk/capital allocation precursor: the accepted free-data "
                "consensus sleeve may deserve a future state router only in "
                "mixed|balanced|normal if it beats exact same-entry alternatives."
            ),
            "2_history_check": (
                "exp-20260606-022 found this state-sleeve cell positive versus "
                "same-sleeve other states; exp-20260608-021 found current forward "
                "rows insufficient for activation, so this run adds exact "
                "historical displacement accounting."
            ),
            "3_single_policy_bundle": (
                "No strategy policy is changed. The single tested decision "
                "hypothesis is the fixed exact displacement readout for "
                "accepted consensus mixed|balanced|normal rows."
            ),
            "4_acceptance_standard": (
                "Observed-only positive lead requires >=30 target rows, >=10 "
                "same-entry alternative rows in >=2 windows, positive aggregate "
                "normalized displacement, >=2 positive windows, and concentration "
                "within 50/60/0.35 single/top5/HHI guards."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260609_021_consensus_state_exact_displacement.py"
            ),
        },
        "gate1_baseline": baseline,
        "gate2_field_reality": field_reality,
        "gate3_survival_audit": {
            "min_core_survival_rate": baseline["aggregate"]["min_survival_rate"],
            "adds_filter": False,
            "survival_guard_passed": (
                baseline["aggregate"]["min_survival_rate"] is not None
                and baseline["aggregate"]["min_survival_rate"] >= 0.05
            ),
        },
        "gate4_observed_only": {
            "changes_strategy_behavior": False,
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
            "accepted_strategy_change": False,
            "decision": status,
            "failed_reasons": evaluation["failed_reasons"],
        },
        "source_reports": source_reports,
        "source_evidence_quality": {
            "uses_forward_live_closed_rows": False,
            "uses_historical_accepted_replay_rows": True,
            "normalization": "pnl_per_10k",
            "primary_comparator": (
                "average normalized PnL of non-consensus accepted sleeves on the "
                "same window and entry date, else cash 0"
            ),
            "strict_secondary_comparator": "best non-consensus same-entry alternative",
            "activation_caveat": (
                "This is not live activation evidence. Activation still requires "
                "closed forward replacement-value rows or a separate shared "
                "router Gate 1-4 experiment."
            ),
        },
        "all_state_labeled_row_count": len(all_rows),
        "target_rows": displacement_rows,
        "evaluation": evaluation,
        "interpretation": interpretation,
        "post_run_reflection": {
            "why_result_happened": (
                "The prior state-cell average can be reinterpreted only after "
                "same-entry alternatives and concentration are accounted for. "
                f"This run found {evaluation['aggregate']['rows_with_same_entry_alternatives']} "
                "target rows with same-entry alternatives and "
                f"{evaluation['positive_displacement_windows']} positive displacement windows."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune the mixed/balanced/normal bucket, accepted consensus "
                "source thresholds, same-state sleeve sample floors, or notional "
                "allocation on these frozen windows."
            ),
            "new_evidence_required": (
                "Closed forward replacement-value rows, a shared deterministic "
                "router with exact displaced candidate accounting, or a materially "
                "new PIT state field."
            ),
        },
        "next_retry_requires": [
            "closed forward replacement-value rows",
            "shared deterministic router with exact displaced candidate accounting",
            "materially new PIT state field",
        ],
        "anti_js": "No JavaScript was used.",
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG_JSONL),
            _repo_rel(REGISTRY_JSON),
        ],
    }


def _log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "diagnostic_only": True,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": payload["causal_components"],
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "baseline_result_file": payload["backtest_protocol"]["baseline_result_file"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
        "target_row_count": payload["evaluation"]["aggregate"]["rows"],
        "same_entry_alternative_rows": payload["evaluation"]["aggregate"][
            "rows_with_same_entry_alternatives"
        ],
        "avg_displacement_delta_per_10k": payload["evaluation"]["aggregate"][
            "avg_displacement_delta_per_10k"
        ],
        "gate4_observed_only": payload["gate4_observed_only"],
        "evaluation": payload["evaluation"],
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "next_retry_requires": payload["next_retry_requires"],
        "anti_js": "No JavaScript was used.",
    }


def _card(payload: dict[str, Any]) -> str:
    evaluation = payload["evaluation"]
    aggregate = evaluation["aggregate"]
    rows = [
        "| Window | Rows | Alt Rows | Avg Target/10k | Avg Comparator/10k | Avg Delta/10k |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for window, summary in evaluation["by_window"].items():
        rows.append(
            "| {window} | {rows} | {alts} | {target:.2f} | {comp:.2f} | {delta:.2f} |".format(
                window=window,
                rows=int(summary["rows"]),
                alts=int(summary["rows_with_same_entry_alternatives"]),
                target=float(summary["avg_target_pnl_per_10k"]),
                comp=float(summary["avg_comparator_pnl_per_10k"]),
                delta=float(summary["avg_displacement_delta_per_10k"]),
            )
        )

    concentration = evaluation["concentration"]
    return "\n".join(
        [
            "---",
            f'experiment_id: "{EXPERIMENT_ID}"',
            f'status: "{payload["status"]}"',
            'lane: "alpha_search"',
            f'changed_variable: "{CHANGED_VARIABLE}"',
            "---",
            "",
            f"# Experiment Card: {EXPERIMENT_ID}",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Decision",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Target rows: `{aggregate['rows']}`",
            f"- Same-entry alternative rows: `{aggregate['rows_with_same_entry_alternatives']}`",
            f"- Avg displacement delta per $10k: `{aggregate['avg_displacement_delta_per_10k']}`",
            f"- Failed reasons: `{', '.join(evaluation['failed_reasons']) or 'none'}`",
            "",
            "## Window Displacement",
            "",
            *rows,
            "",
            "## Concentration",
            "",
            f"- Single ticker positive share: `{concentration['max_single_ticker_positive_share']}`",
            f"- Top-5 positive share: `{concentration['top5_positive_share']}`",
            f"- Positive HHI: `{concentration['positive_hhi']}`",
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def _manifest(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        git_rev = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip()
    except Exception:
        git_rev = None
    try:
        dirty = subprocess.check_output(
            ["git", "status", "--short"], cwd=REPO_ROOT, text=True
        ).splitlines()
    except Exception:
        dirty = []
    files = [
        Path(__file__),
        OUT_JSON,
        LOG_JSON,
        TICKET_JSON,
        CARD_MD,
        EXPERIMENT_LOG_JSONL,
        REGISTRY_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "git_rev": git_rev,
        "git_status_short": dirty,
        "files": { _repo_rel(path): _sha(path) for path in files },
        "anti_js": "No JavaScript was used.",
    }


def main() -> None:
    payload = _build_payload()
    log_record = _log_record(payload)

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, log_record)
    _write_text(CARD_MD, _card(payload))
    _write_json(MANIFEST_JSON, _manifest(payload))
    _upsert_jsonl(EXPERIMENT_LOG_JSONL, log_record)

    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8")) if TICKET_JSON.exists() else {}
    registry_result = {
        "decision": payload["decision"],
        "accepted": False,
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "target_row_count": payload["evaluation"]["aggregate"]["rows"],
        "same_entry_alternative_rows": payload["evaluation"]["aggregate"][
            "rows_with_same_entry_alternatives"
        ],
        "avg_displacement_delta_per_10k": payload["evaluation"]["aggregate"][
            "avg_displacement_delta_per_10k"
        ],
        "evaluation": payload["evaluation"],
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=ticket.get("prediction") or PREDICTION,
        result=registry_result,
        status=payload["status"],
        fields={
            "owner": "codex-alpha-explore",
            "hypothesis": payload["hypothesis"],
            "change_type": payload["change_type"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": payload["causal_components"],
            "prior_trial_count": payload["prior_trial_count"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "decision": payload["decision"],
            "summary": payload["interpretation"],
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "card_file": _repo_rel(CARD_MD),
            "revision_manifest_file": _repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
        },
    )

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "artifact": _repo_rel(OUT_JSON),
                "avg_displacement_delta_per_10k": payload["evaluation"]["aggregate"][
                    "avg_displacement_delta_per_10k"
                ],
                "failed_reasons": payload["evaluation"]["failed_reasons"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
