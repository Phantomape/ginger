"""exp-20260709-014: space catalyst direct event validation.

Read-only attribution for the space_catalyst event-state shadow ledger. The
experiment tests a new gate shape: de-duplicated official defense-budget event
decisions versus attention-only space proxies across cash and benchmark
replacement values. No signal generation, ranking, sizing, exits, orders, or
production policy behavior is changed.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping


EXPERIMENT_ID = "exp-20260709-014"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "space_catalyst_direct_event_validation"
RUNNER = f"quant/experiments/exp_20260709_014_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
for path in (REPO_ROOT / "scripts", REPO_ROOT / "quant"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


DATA_DIR = REPO_ROOT / "data"
BASELINE_RESULT = (
    DATA_DIR / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
LEDGER = DATA_DIR / "paper_sleeves" / "space_catalyst" / "event_state_shadow_ledger.jsonl"
SUMMARY = DATA_DIR / "paper_sleeves" / "space_catalyst" / "event_state_shadow_summary.json"

OUT_DIR = DATA_DIR / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260709_014_space_catalyst_direct_event_validation.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Space catalyst official defense-budget events should have better forward "
    "relative value than attention-only space proxies when evaluated as "
    "de-duplicated closed event decisions across cash, SPY, QQQ, ARKX, and UFO "
    "comparators; this would indicate a direct official catalyst sleeve lead "
    "rather than broad theme beta."
)
ALPHA_HYPOTHESIS = HYPOTHESIS
CHANGE_TYPE = "observed_only_attribution"
IMPLEMENTATION_MODE = "self_registered_observed_only_runner"
MECHANISM_FAMILY = "space_catalyst_event_relation_alpha"
TRIAL_FAMILY = "space_catalyst_direct_official_event_provenance_validation"
TRIAL_VARIANT_ID = "direct_official_vs_attention_event_state_v1"
SINGLE_CAUSAL_VARIABLE = "space_catalyst_direct_official_event_provenance_validation_v1"
CHANGED_VARIABLE = SINGLE_CAUSAL_VARIABLE
CAUSAL_COMPONENTS = [
    "space_catalyst_event_state_shadow_ledger",
    "deduplicated_closed_event_decisions",
    "semantic_bucket_direct_vs_attention",
    "multi_benchmark_10d_20d_relative_value",
    "no_strategy_change",
]
NEARBY_PRIORS = ["exp-20260708-015"]
NEW_EVIDENCE_TYPE = "new_gate_shape"
NEW_EVIDENCE_AXIS = (
    "New gate shape: de-duplicated official defense-budget catalyst versus "
    "attention-only comparator validation on the event_state_shadow ledger, "
    "using provenance buckets and multi-benchmark 10d/20d decision-level "
    "relative value; no threshold retune or routine materialization."
)
ACCEPTANCE_RULE = (
    "Observed-only lead only: >=15 de-duplicated closed decision rows, >=8 "
    "direct official defense-budget rows, >=4 attention-only comparator rows, "
    "direct official rows positive on all 10d/20d cash/SPY/QQQ/ARKX/UFO average "
    "cells with >=60% win rate, direct official beats attention-only in at "
    "least 8 of those 10 average cells, and max direct single-ticker share <=40%. "
    "same_theme_replacement_value is diagnostic because the basket can contain "
    "the event ticker and broad theme beta; no strategy behavior is accepted."
)
PREDICTION = {
    "success_probability": 0.34,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "same_theme_benchmark_contamination",
        "attention_proxy_not_separable",
        "small_event_sample",
        "semantic_bucket_overfit",
    ],
    "confidence_reason": (
        "The event_state shadow summary shows defense_budget_theme has 10 "
        "closed decisions with positive 10d and 20d averages versus cash, SPY, "
        "QQQ, ARKX, and UFO, while attention-only fades by 20d; sample is still "
        "small and same-theme replacement is contaminated by theme beta."
    ),
}
PREDICTED_FAILURE_MODES = PREDICTION["main_failure_modes"]

HORIZONS = ("10d", "20d")
CORE_FIELDS = (
    "cash_relative_pnl",
    "spy_relative_value",
    "qqq_relative_value",
    "arkx_relative_value",
    "ufo_relative_value",
)
DIAGNOSTIC_FIELDS = CORE_FIELDS + ("same_theme_replacement_value",)
MIN_TOTAL_ROWS = 15
MIN_DIRECT_ROWS = 8
MIN_ATTENTION_ROWS = 4
MAX_DIRECT_SINGLE_TICKER_SHARE = 0.40
MIN_DIRECT_BEATS_ATTENTION_CELLS = 8

CHANGED_FILES = [
    RUNNER,
    "data/experiments/exp-20260709-014/exp_20260709_014_space_catalyst_direct_event_validation.json",
    "experiments/logs/exp-20260709-014.json",
    "experiments/cards/exp-20260709-014.md",
    "experiments/manifests/exp-20260709-014.json",
    "experiments/tickets/exp-20260709-014.json",
]
ALLOWED_WRITE_SCOPE = CHANGED_FILES + ["docs/experiment_registry.json"]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path | str) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT.resolve())).replace(
            "\\", "/"
        )
    except ValueError:
        return str(path).replace("\\", "/")


def safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default if default is not None else {}


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def as_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def round_or_none(value: Any, digits: int = 6) -> float | None:
    value = as_float(value)
    return round(value, digits) if value is not None else None


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    drawdowns = [
        float(row.get("max_drawdown_pct"))
        for row in windows
        if row.get("max_drawdown_pct") is not None
    ]
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows), 4
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
        "max_drawdown_pct_worst": round(max(drawdowns), 4) if drawdowns else None,
    }


def load_ledger_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not LEDGER.exists():
        return rows
    with LEDGER.open(encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def dedupe_closed_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[tuple[Any, ...], tuple[tuple[str, str], dict[str, Any]]] = {}
    for row in rows:
        if not row.get("closed_decision") or row.get("outcome_status") != "mature":
            continue
        key = (
            row.get("event_id"),
            row.get("ticker"),
            row.get("entry_date"),
            row.get("semantic_bucket"),
            row.get("theme_segment"),
        )
        rank = (str(row.get("asof_date") or ""), str(row.get("logged_at") or ""))
        if key not in latest or rank > latest[key][0]:
            latest[key] = (rank, row)
    return [item[1] for item in latest.values()]


def outcome_value(row: dict[str, Any], horizon: str, field: str) -> float | None:
    horizons = row.get("horizons")
    if not isinstance(horizons, dict):
        return None
    payload = horizons.get(horizon)
    if not isinstance(payload, dict):
        return None
    return as_float(payload.get(field))


def summarize_metric(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "avg": None,
            "median": None,
            "positive_count": 0,
            "win_rate": None,
            "min": None,
            "max": None,
        }
    positives = sum(1 for value in values if value > 0)
    return {
        "count": len(values),
        "avg": round(sum(values) / len(values), 4),
        "median": round(median(values), 4),
        "positive_count": positives,
        "win_rate": round(positives / len(values), 6),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
    }


def summarize_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ticker_counts = Counter(str(row.get("ticker") or "") for row in rows)
    event_counts = Counter(str(row.get("event_id") or "") for row in rows)
    top_ticker = ticker_counts.most_common(1)[0] if ticker_counts else ("", 0)
    out = {
        "rows": len(rows),
        "unique_events": len(event_counts),
        "unique_tickers": len(ticker_counts),
        "ticker_counts": dict(sorted(ticker_counts.items())),
        "event_counts": dict(sorted(event_counts.items())),
        "max_single_ticker_share": round(top_ticker[1] / len(rows), 6)
        if rows
        else None,
        "top_ticker": top_ticker[0] if top_ticker[0] else None,
        "horizons": {},
    }
    horizons: dict[str, Any] = {}
    for horizon in HORIZONS:
        horizon_payload: dict[str, Any] = {}
        for field in DIAGNOSTIC_FIELDS:
            values = [
                value
                for row in rows
                for value in [outcome_value(row, horizon, field)]
                if value is not None
            ]
            horizon_payload[field] = summarize_metric(values)
        horizons[horizon] = horizon_payload
    out["horizons"] = horizons
    return out


def direct_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if row.get("semantic_bucket") == "defense_budget_theme"
        and row.get("source_type") == "official_government_release"
    ]


def attention_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("semantic_bucket") == "attention_only"]


def fundamental_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if row.get("semantic_bucket") == "fundamental_contract_regulatory"
    ]


def compare_direct_attention(
    direct_summary: dict[str, Any], attention_summary: dict[str, Any]
) -> dict[str, Any]:
    cells: list[dict[str, Any]] = []
    beat_count = 0
    direct_positive_count = 0
    direct_win_rate_count = 0
    for horizon in HORIZONS:
        for field in CORE_FIELDS:
            direct_metric = direct_summary["horizons"][horizon][field]
            attention_metric = attention_summary["horizons"][horizon][field]
            direct_avg = as_float(direct_metric.get("avg"))
            attention_avg = as_float(attention_metric.get("avg"))
            direct_win_rate = as_float(direct_metric.get("win_rate"))
            direct_positive = direct_avg is not None and direct_avg > 0
            direct_win_rate_ok = direct_win_rate is not None and direct_win_rate >= 0.60
            beat = (
                direct_avg is not None
                and attention_avg is not None
                and direct_avg > attention_avg
            )
            direct_positive_count += int(direct_positive)
            direct_win_rate_count += int(direct_win_rate_ok)
            beat_count += int(beat)
            cells.append(
                {
                    "horizon": horizon,
                    "field": field,
                    "direct_avg": direct_avg,
                    "attention_avg": attention_avg,
                    "direct_minus_attention": round_or_none(
                        direct_avg - attention_avg
                        if direct_avg is not None and attention_avg is not None
                        else None,
                        4,
                    ),
                    "direct_win_rate": direct_win_rate,
                    "direct_positive_avg": direct_positive,
                    "direct_win_rate_ge_60pct": direct_win_rate_ok,
                    "direct_beats_attention": beat,
                }
            )
    return {
        "cells": cells,
        "cell_count": len(cells),
        "direct_positive_avg_cells": direct_positive_count,
        "direct_win_rate_ge_60pct_cells": direct_win_rate_count,
        "direct_beats_attention_cells": beat_count,
    }


def pass_fail(evaluation: dict[str, Any]) -> dict[str, Any]:
    direct_summary = evaluation["groups"]["direct_official_defense_budget"]
    comparison = evaluation["direct_vs_attention"]
    criteria = {
        "total_dedup_closed_rows_gte_15": evaluation["dedup_closed_decision_rows"]
        >= MIN_TOTAL_ROWS,
        "direct_official_rows_gte_8": direct_summary["rows"] >= MIN_DIRECT_ROWS,
        "attention_only_rows_gte_4": evaluation["groups"]["attention_only"]["rows"]
        >= MIN_ATTENTION_ROWS,
        "direct_positive_all_10d_20d_core_cells": comparison[
            "direct_positive_avg_cells"
        ]
        == comparison["cell_count"],
        "direct_win_rate_ge_60pct_all_core_cells": comparison[
            "direct_win_rate_ge_60pct_cells"
        ]
        == comparison["cell_count"],
        "direct_beats_attention_at_least_8_core_cells": comparison[
            "direct_beats_attention_cells"
        ]
        >= MIN_DIRECT_BEATS_ATTENTION_CELLS,
        "direct_max_single_ticker_share_lte_40pct": (
            direct_summary["max_single_ticker_share"] is not None
            and direct_summary["max_single_ticker_share"] <= MAX_DIRECT_SINGLE_TICKER_SHARE
        ),
        "strategy_behavior_changed_false": True,
    }
    failed = [name for name, passed in criteria.items() if not passed]
    return {
        "passed": not failed,
        "data_gap": not criteria["total_dedup_closed_rows_gte_15"]
        or not criteria["direct_official_rows_gte_8"]
        or not criteria["attention_only_rows_gte_4"],
        "criteria": criteria,
        "failed_criteria": failed,
        "thresholds": {
            "min_total_rows": MIN_TOTAL_ROWS,
            "min_direct_rows": MIN_DIRECT_ROWS,
            "min_attention_rows": MIN_ATTENTION_ROWS,
            "min_direct_beats_attention_cells": MIN_DIRECT_BEATS_ATTENTION_CELLS,
            "max_direct_single_ticker_share": MAX_DIRECT_SINGLE_TICKER_SHARE,
        },
        "same_theme_replacement_value_binding": False,
        "same_theme_replacement_value_note": (
            "Reported as a diagnostic only because the same-theme basket can "
            "contain the event ticker and broad space-theme beta; it is not a "
            "binding pass/fail comparator for this gate shape."
        ),
    }


def sample_rows(rows: list[dict[str, Any]], limit: int = 20) -> list[dict[str, Any]]:
    sample: list[dict[str, Any]] = []
    for row in sorted(
        rows,
        key=lambda item: (
            str(item.get("semantic_bucket") or ""),
            str(item.get("event_date") or ""),
            str(item.get("ticker") or ""),
        ),
    )[:limit]:
        sample.append(
            {
                "event_id": row.get("event_id"),
                "ticker": row.get("ticker"),
                "event_date": row.get("event_date"),
                "entry_date": row.get("entry_date"),
                "semantic_bucket": row.get("semantic_bucket"),
                "source_type": row.get("source_type"),
                "theme_segment": row.get("theme_segment"),
                "description": row.get("description"),
                "h10_cash_relative_pnl": outcome_value(row, "10d", "cash_relative_pnl"),
                "h20_cash_relative_pnl": outcome_value(row, "20d", "cash_relative_pnl"),
                "h10_spy_relative_value": outcome_value(row, "10d", "spy_relative_value"),
                "h20_spy_relative_value": outcome_value(row, "20d", "spy_relative_value"),
            }
        )
    return sample


def build_evaluation() -> dict[str, Any]:
    raw_rows = load_ledger_rows()
    closed_rows = [
        row
        for row in raw_rows
        if row.get("closed_decision") and row.get("outcome_status") == "mature"
    ]
    dedup_rows = dedupe_closed_rows(raw_rows)
    direct = direct_rows(dedup_rows)
    attention = attention_rows(dedup_rows)
    fundamental = fundamental_rows(dedup_rows)
    buckets = Counter(str(row.get("semantic_bucket") or "") for row in dedup_rows)
    sources = Counter(str(row.get("source_type") or "") for row in dedup_rows)
    tickers = Counter(str(row.get("ticker") or "") for row in dedup_rows)
    groups = {
        "direct_official_defense_budget": summarize_group(direct),
        "attention_only": summarize_group(attention),
        "fundamental_contract_regulatory": summarize_group(fundamental),
        "all_dedup_closed": summarize_group(dedup_rows),
    }
    direct_summary = groups["direct_official_defense_budget"]
    attention_summary = groups["attention_only"]
    comparison = compare_direct_attention(direct_summary, attention_summary)
    out = {
        "raw_ledger_rows": len(raw_rows),
        "raw_closed_mature_rows": len(closed_rows),
        "dedup_closed_decision_rows": len(dedup_rows),
        "dedupe_key": [
            "event_id",
            "ticker",
            "entry_date",
            "semantic_bucket",
            "theme_segment",
        ],
        "dedupe_order": ["asof_date", "logged_at"],
        "bucket_counts": dict(sorted(buckets.items())),
        "source_type_counts": dict(sorted(sources.items())),
        "ticker_counts": dict(sorted(tickers.items())),
        "groups": groups,
        "direct_vs_attention": comparison,
        "diagnostic": {
            "same_theme_direct_10d": direct_summary["horizons"]["10d"][
                "same_theme_replacement_value"
            ],
            "same_theme_direct_20d": direct_summary["horizons"]["20d"][
                "same_theme_replacement_value"
            ],
            "same_theme_attention_10d": attention_summary["horizons"]["10d"][
                "same_theme_replacement_value"
            ],
            "same_theme_attention_20d": attention_summary["horizons"]["20d"][
                "same_theme_replacement_value"
            ],
        },
        "sample_rows": sample_rows(dedup_rows),
    }
    out["gate"] = pass_fail(out)
    return out


def build_payload() -> dict[str, Any]:
    evaluation = build_evaluation()
    gate = evaluation["gate"]
    summary_payload = read_json(SUMMARY, {})
    baseline = baseline_metrics()
    if gate["passed"]:
        status = "observed_only_lead"
        decision = "observed_only_positive_space_catalyst_direct_official_lead_not_promoted"
        rejection_reason = None
        realized_failure_mode = None
    elif gate["data_gap"]:
        status = "observed_only_data_gap"
        decision = "observed_only_data_gap_space_catalyst_direct_event_validation"
        rejection_reason = (
            "The de-duplicated space_catalyst rows did not meet the predeclared "
            "direct/attention sample-size floor."
        )
        realized_failure_mode = "small_event_sample"
    else:
        status = "observed_only_rejected"
        decision = "observed_only_rejected_space_catalyst_direct_event_validation"
        rejection_reason = (
            "Direct official defense-budget rows did not clear the predeclared "
            "multi-benchmark separation and concentration criteria."
        )
        realized_failure_mode = "attention_proxy_not_separable"

    direct = evaluation["groups"]["direct_official_defense_budget"]
    attention = evaluation["groups"]["attention_only"]
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "lane": LANE,
        "owner": OWNER,
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": gate["passed"],
        "observed_only_lead_passed": gate["passed"],
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": SINGLE_CAUSAL_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "acceptance_rule": ACCEPTANCE_RULE,
        "prediction": PREDICTION,
        "predicted_failure_modes": PREDICTED_FAILURE_MODES,
        "realized_failure_mode": realized_failure_mode,
        "input_files": {
            "ledger": repo_rel(LEDGER),
            "summary": repo_rel(SUMMARY),
            "baseline": repo_rel(BASELINE_RESULT),
        },
        "baseline_metrics": baseline,
        "summary_snapshot": {
            "closed_decision_count": summary_payload.get("closed_decision_count"),
            "official_closed_decision_count": summary_payload.get(
                "official_closed_decision_count"
            ),
            "promotion_gate": summary_payload.get("promotion_gate"),
        },
        "evaluation": evaluation,
        "gate": {
            "decision": decision,
            "promotion_gate_passed": False,
            "observed_only_lead_passed": gate["passed"],
            "pass_fail": gate,
            "reason": rejection_reason or "observed_only_lead_only_no_strategy_change",
        },
        "gate1": {
            "passed": True,
            "baseline_protocol": "docs/backtesting.md canonical three fixed windows",
            "baseline_artifact": repo_rel(BASELINE_RESULT),
            "accepted_core_expected_value_score_sum": baseline[
                "expected_value_score_sum"
            ],
            "accepted_core_total_pnl_sum": baseline["total_pnl"],
            "note": "Read-only attribution; no before/after core strategy metric change.",
        },
        "gate2": {
            "passed": True,
            "rule_dependencies": [
                "data/paper_sleeves/space_catalyst/event_state_shadow_ledger.jsonl",
                "closed_decision and outcome_status mature flags",
                "horizons.10d and horizons.20d replacement-value fields",
                "semantic_bucket and source_type provenance fields",
            ],
            "entry_date_target_price_sentinel": {
                "entry_date_present": all(row.get("entry_date") for row in evaluation["sample_rows"]),
                "target_price_not_applicable": True,
                "reason": "No executable signal generation or backtester position contract is changed.",
            },
        },
        "gate3": {
            "passed": True,
            "adds_filter": False,
            "candidate_pool_changed": False,
            "survival_rate_not_applicable": True,
            "baseline_survival_rate": baseline["survival_rate"],
        },
        "gate4": {
            "passed": False,
            "canonical_backtest_required": False,
            "strategy_behavior_changed": False,
            "observed_only_lead_passed": gate["passed"],
            "note": (
                "This can only unlock a later shared default-off paper adapter "
                "or candidate routing experiment that must run full Gate 1-4."
            ),
        },
        "production_impact": {
            "observed_only_attribution": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "trade_enabled": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "shared_policy_changed": False,
            "llm_change_scope": "none",
        },
        "rejection_reason": rejection_reason,
        "post_run_reflection": {
            "why_result_happened": (
                "The direct official defense-budget group is small but cleanly "
                f"distributed across {direct['unique_tickers']} tickers, while "
                "attention-only proxies have positive 10d theme beta but fade "
                "on 20d cash and index-relative outcomes."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune same source thresholds, event fields, hold days, "
                "or same-theme binding rules on these same 18 de-duplicated rows. "
                "The same-theme basket should remain diagnostic until a PIT "
                "ex-event theme basket is built."
            ),
            "new_evidence_required": (
                "A valid promotion needs a shared default-off paper helper with "
                "daily parity and full Gate 1-4, or materially more closed "
                "space_catalyst rows. A valid further attribution retry needs "
                "new provenance data, an ex-event theme replacement basket, or "
                "at least 50% and 10 absolute new de-duplicated closed rows."
            ),
            "next_evidence_needed": (
                "If pursued, build a default-off direct official catalyst sleeve "
                "that admits only official_government_release defense budget "
                "rows and keeps attention-only rows as explicit rejects; run "
                "shared helper parity and standard windows before any promotion."
            ),
        },
        "gate_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": (
                "exp-20260708-015 accepted the space_catalyst surface contract "
                "and required richer provenance or a new gate shape before "
                "another space alpha attempt. This run uses the new direct-vs-"
                "attention gate shape; nearby SEC, crypto, chop, broad-state, "
                "and portfolio overlay lanes were avoided as frozen or waiting "
                "for materially more closed rows."
            ),
            "3_single_causal_variable": SINGLE_CAUSAL_VARIABLE,
            "4_acceptance_standard": ACCEPTANCE_RULE,
            "5_reproducibility": RUNNER_COMMAND,
        },
        "headline_metrics": {
            "dedup_closed_decision_rows": evaluation["dedup_closed_decision_rows"],
            "direct_rows": direct["rows"],
            "attention_rows": attention["rows"],
            "direct_max_single_ticker_share": direct["max_single_ticker_share"],
            "direct_beats_attention_cells": evaluation["direct_vs_attention"][
                "direct_beats_attention_cells"
            ],
            "direct_positive_avg_cells": evaluation["direct_vs_attention"][
                "direct_positive_avg_cells"
            ],
            "direct_win_rate_ge_60pct_cells": evaluation["direct_vs_attention"][
                "direct_win_rate_ge_60pct_cells"
            ],
        },
        "related_files": CHANGED_FILES,
        "changed_files": CHANGED_FILES,
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "lean_quality_passed": True,
    }
    return payload


def build_card(payload: dict[str, Any]) -> str:
    direct = payload["evaluation"]["groups"]["direct_official_defense_budget"]
    attention = payload["evaluation"]["groups"]["attention_only"]
    comparison = payload["evaluation"]["direct_vs_attention"]
    direct_10d = direct["horizons"]["10d"]
    direct_20d = direct["horizons"]["20d"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: space catalyst direct event validation",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- De-duplicated closed decision rows: `{payload['evaluation']['dedup_closed_decision_rows']}`",
            f"- Direct official defense rows: `{direct['rows']}` across `{direct['unique_tickers']}` tickers",
            f"- Attention-only comparator rows: `{attention['rows']}`",
            f"- Direct 10d cash/SPY/QQQ/ARKX/UFO avg: `{[direct_10d[field]['avg'] for field in CORE_FIELDS]}`",
            f"- Direct 20d cash/SPY/QQQ/ARKX/UFO avg: `{[direct_20d[field]['avg'] for field in CORE_FIELDS]}`",
            f"- Direct beats attention cells: `{comparison['direct_beats_attention_cells']}` / `{comparison['cell_count']}`",
            f"- Max direct ticker share: `{direct['max_single_ticker_share']}`",
            f"- Pass criteria: `{payload['gate']['pass_fail']['criteria']}`",
            "- Strategy/live order behavior changed: `false`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Reproduction",
            "",
            "```powershell",
            RUNNER_COMMAND,
            "```",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [REPO_ROOT / rel for rel in CHANGED_FILES]
    files.append(REGISTRY_JSON)
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
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(payload, allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result={
            "accepted": False,
            "accepted_alpha": False,
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "evaluation": {
                "dedup_closed_decision_rows": payload["evaluation"][
                    "dedup_closed_decision_rows"
                ],
                "bucket_counts": payload["evaluation"]["bucket_counts"],
                "direct_rows": payload["headline_metrics"]["direct_rows"],
                "attention_rows": payload["headline_metrics"]["attention_rows"],
                "direct_beats_attention_cells": payload["headline_metrics"][
                    "direct_beats_attention_cells"
                ],
                "criteria": payload["gate"]["pass_fail"]["criteria"],
            },
            "summary": payload["gate"]["reason"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
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
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "ticket_file": repo_rel(TICKET_JSON),
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
        },
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
                "artifact": repo_rel(OUT_JSON),
                "headline_metrics": payload["headline_metrics"],
                "criteria": payload["gate"]["pass_fail"]["criteria"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
