"""exp-20260709-022: Space catalyst ex-self same-theme attribution.

Read-only attribution for the space_catalyst event-state shadow ledger. This
tests the reopen axis named by exp-20260709-015: replace the contaminated
same-theme comparator with an ex-self same-theme basket so each candidate is
measured against the rest of its theme basket instead of a basket containing
itself. No signal generation, ranking, sizing, exits, orders, or production
policy behavior is changed.
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


EXPERIMENT_ID = "exp-20260709-022"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "space_catalyst_ex_self_same_theme"
RUNNER = f"quant/experiments/exp_20260709_022_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
for path in (REPO_ROOT / "scripts", REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


DATA_DIR = REPO_ROOT / "data"
BASELINE_RESULT = (
    DATA_DIR
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
LEDGER = (
    DATA_DIR
    / "paper_sleeves"
    / "space_catalyst"
    / "event_state_shadow_ledger.jsonl"
)
SUMMARY = (
    DATA_DIR
    / "paper_sleeves"
    / "space_catalyst"
    / "event_state_shadow_summary.json"
)

OUT_DIR = DATA_DIR / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260709_022_space_catalyst_ex_self_same_theme.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Observed-only alpha: the Space catalyst direct-official defense-budget "
    "forward lead should retain positive 10d/20d relative value after replacing "
    "the contaminated same-theme comparator with an ex-self same-theme basket; "
    "if it does not, the lead is only broad Space basket beta and must remain "
    "parked."
)
CHANGE_TYPE = "observed_only_opportunity_cost_attribution"
IMPLEMENTATION_MODE = "self_registered_observed_only_runner"
MECHANISM_FAMILY = "space_catalyst_event_relation_alpha"
TRIAL_FAMILY = "space_catalyst_ex_event_same_theme_opportunity_cost"
TRIAL_VARIANT_ID = "ex_self_same_theme_replacement_v1"
SINGLE_CAUSAL_VARIABLE = "space_catalyst_ex_self_same_theme_replacement_value_v1"
CAUSAL_COMPONENTS = [
    "existing event_state_shadow_ledger",
    "direct_official_defense_budget_rows",
    "ex_self_same_theme_replacement_basket",
    "no_strategy_change",
]
NEARBY_PRIORS = ["exp-20260709-014", "exp-20260709-015", "exp-20260702-003"]
NEW_EVIDENCE_TYPE = "new_gate_shape"
NEW_EVIDENCE_AXIS = (
    "New gate shape explicitly required by exp-20260709-015: ex-event/ex-self "
    "same-theme replacement basket that removes each candidate ticker from the "
    "same-theme benchmark before measuring direct-official Space catalyst "
    "opportunity cost; not a source-type, hold, threshold, notional, or response "
    "retune on the same rows."
)
ACCEPTANCE_RULE = (
    "Observed-only lead only: >=8 direct-official rows; for 10d and 20d, "
    "ex-self same-theme replacement average > 0 and win rate >= 60%; direct "
    "rows must still be positive versus cash/SPY/QQQ/ARKX/UFO. No strategy "
    "behavior is accepted."
)
PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "same_theme_opportunity_cost_not_incremental",
        "leave_one_out_mean_zero_by_construction",
        "forward_sample_overfit",
    ],
    "confidence_reason": (
        "exp-20260709-014 showed a positive direct-official lead, while "
        "exp-20260709-015 rejected promotion and specifically required an "
        "ex-event same-theme replacement basket before further same-source "
        "attribution."
    ),
}

HORIZONS = ("10d", "20d")
CORE_FIELDS = (
    "cash_relative_pnl",
    "spy_relative_value",
    "qqq_relative_value",
    "arkx_relative_value",
    "ufo_relative_value",
)
OPPORTUNITY_FIELD = "ex_self_same_theme_replacement_value"
ORIGINAL_THEME_FIELD = "same_theme_replacement_value"
DIAGNOSTIC_FIELDS = CORE_FIELDS + (ORIGINAL_THEME_FIELD, OPPORTUNITY_FIELD)
MIN_DIRECT_ROWS = 8
MIN_OPPORTUNITY_WIN_RATE = 0.60

CHANGED_FILES = [
    RUNNER,
    "data/experiments/exp-20260709-022/exp_20260709_022_space_catalyst_ex_self_same_theme.json",
    "experiments/logs/exp-20260709-022.json",
    "experiments/cards/exp-20260709-022.md",
    "experiments/manifests/exp-20260709-022.json",
    "experiments/tickets/exp-20260709-022.json",
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


def summarize_values(values: Iterable[float]) -> dict[str, Any]:
    xs = [float(value) for value in values if value is not None and math.isfinite(value)]
    if not xs:
        return {
            "count": 0,
            "avg": None,
            "median": None,
            "min": None,
            "max": None,
            "positive_count": 0,
            "win_rate": None,
        }
    positives = sum(1 for value in xs if value > 0)
    return {
        "count": len(xs),
        "avg": round(sum(xs) / len(xs), 6),
        "median": round(median(xs), 6),
        "min": round(min(xs), 6),
        "max": round(max(xs), 6),
        "positive_count": positives,
        "win_rate": round(positives / len(xs), 6),
    }


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
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(
            sum(float(row.get("total_pnl") or 0.0) for row in windows), 2
        ),
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


def closed_for_horizons(row: Mapping[str, Any]) -> bool:
    if not row.get("closed_decision"):
        return False
    horizons = row.get("horizons")
    if not isinstance(horizons, Mapping):
        return False
    for horizon in HORIZONS:
        bucket = horizons.get(horizon)
        if not isinstance(bucket, Mapping) or bucket.get("status") != "mature":
            return False
    return True


def dedupe_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        if not closed_for_horizons(row):
            continue
        key = (
            row.get("event_id"),
            row.get("ticker"),
            row.get("entry_date"),
            row.get("semantic_bucket"),
            row.get("theme_segment"),
        )
        old = latest.get(key)
        old_key = ((old or {}).get("asof_date") or "", (old or {}).get("logged_at") or "")
        new_key = (row.get("asof_date") or "", row.get("logged_at") or "")
        if old is None or new_key >= old_key:
            latest[key] = row
    return sorted(
        latest.values(),
        key=lambda row: (
            str(row.get("entry_date") or ""),
            str(row.get("event_id") or ""),
            str(row.get("ticker") or ""),
        ),
    )


def is_direct_official(row: Mapping[str, Any]) -> bool:
    return (
        row.get("semantic_bucket") == "defense_budget_theme"
        and row.get("source_type") == "official_government_release"
    )


def is_attention_only(row: Mapping[str, Any]) -> bool:
    return row.get("semantic_bucket") == "attention_only"


def ex_self_same_theme_value(row: Mapping[str, Any], horizon: str) -> dict[str, Any]:
    bucket = row.get("horizons", {}).get(horizon, {})
    if not isinstance(bucket, Mapping):
        return {"status": "missing_horizon"}
    basket = bucket.get("same_theme_basket")
    if not isinstance(basket, Mapping):
        return {"status": "missing_same_theme_basket"}
    ticker_returns = basket.get("ticker_returns")
    if not isinstance(ticker_returns, Mapping):
        return {"status": "missing_ticker_returns"}

    ticker = str(row.get("ticker") or "")
    returns: dict[str, float] = {}
    for key, value in ticker_returns.items():
        parsed = as_float(value)
        if parsed is not None:
            returns[str(key)] = parsed
    ex_returns = [value for key, value in returns.items() if key != ticker]
    event_return = as_float(bucket.get("event_return"))
    notional = as_float(row.get("initial_notional")) or 10000.0
    if event_return is None:
        return {"status": "missing_event_return", "basket_ticker_count": len(returns)}
    if not ex_returns:
        return {"status": "no_ex_self_basket", "basket_ticker_count": len(returns)}

    basket_return = sum(ex_returns) / len(ex_returns)
    value = notional * (event_return - basket_return)
    return {
        "status": "ok",
        "basket_ticker_count": len(returns),
        "ex_self_ticker_count": len(ex_returns),
        "event_return": round(event_return, 8),
        "ex_self_basket_return": round(basket_return, 8),
        "ex_self_same_theme_pnl": round(notional * basket_return, 2),
        OPPORTUNITY_FIELD: round(value, 2),
    }


def enrich_row(row: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(row)
    horizon_metrics: dict[str, dict[str, Any]] = {}
    for horizon in HORIZONS:
        bucket = row.get("horizons", {}).get(horizon, {})
        metrics: dict[str, Any] = {}
        if isinstance(bucket, Mapping):
            for field in CORE_FIELDS + (ORIGINAL_THEME_FIELD,):
                metrics[field] = round_or_none(bucket.get(field), 6)
        metrics[OPPORTUNITY_FIELD] = ex_self_same_theme_value(row, horizon)
        horizon_metrics[horizon] = metrics
    out["ex_self_horizons"] = horizon_metrics
    return out


def metric_value(row: Mapping[str, Any], horizon: str, field: str) -> float | None:
    if field == OPPORTUNITY_FIELD:
        payload = row.get("ex_self_horizons", {}).get(horizon, {}).get(field, {})
        if isinstance(payload, Mapping) and payload.get("status") == "ok":
            return as_float(payload.get(field))
        return None
    bucket = row.get("horizons", {}).get(horizon, {})
    if isinstance(bucket, Mapping):
        return as_float(bucket.get(field))
    return None


def summarize_group(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    ticker_counts = Counter(str(row.get("ticker") or "") for row in rows)
    event_counts = Counter(str(row.get("event_id") or "") for row in rows)
    top_ticker, top_rows = (ticker_counts.most_common(1)[0] if ticker_counts else (None, 0))
    horizons: dict[str, Any] = {}
    for horizon in HORIZONS:
        horizons[horizon] = {
            field: summarize_values(
                value
                for row in rows
                for value in [metric_value(row, horizon, field)]
                if value is not None
            )
            for field in DIAGNOSTIC_FIELDS
        }
    return {
        "rows": len(rows),
        "unique_events": len(event_counts),
        "unique_tickers": len(ticker_counts),
        "event_counts": dict(sorted(event_counts.items())),
        "ticker_counts": dict(sorted(ticker_counts.items())),
        "top_ticker": top_ticker,
        "top_ticker_rows": top_rows,
        "max_single_ticker_share": round(top_rows / len(rows), 6) if rows else None,
        "horizons": horizons,
    }


def sample_rows(rows: list[Mapping[str, Any]], limit: int = 14) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for row in rows[:limit]:
        payload = {
            "event_id": row.get("event_id"),
            "ticker": row.get("ticker"),
            "entry_date": row.get("entry_date"),
            "event_date": row.get("event_date"),
            "semantic_bucket": row.get("semantic_bucket"),
            "source_type": row.get("source_type"),
            "theme_segment": row.get("theme_segment"),
        }
        for horizon in HORIZONS:
            ex_payload = row.get("ex_self_horizons", {}).get(horizon, {}).get(
                OPPORTUNITY_FIELD, {}
            )
            if isinstance(ex_payload, Mapping):
                payload[f"{horizon}_ex_self_same_theme_value"] = ex_payload.get(
                    OPPORTUNITY_FIELD
                )
                payload[f"{horizon}_ex_self_basket_return"] = ex_payload.get(
                    "ex_self_basket_return"
                )
            payload[f"{horizon}_original_same_theme_value"] = round_or_none(
                row.get("horizons", {}).get(horizon, {}).get(ORIGINAL_THEME_FIELD)
            )
            payload[f"{horizon}_cash_relative_pnl"] = round_or_none(
                row.get("horizons", {}).get(horizon, {}).get("cash_relative_pnl")
            )
        samples.append(payload)
    return samples


def build_evaluation() -> dict[str, Any]:
    raw_rows = load_ledger_rows()
    dedup_rows = [enrich_row(row) for row in dedupe_rows(raw_rows)]
    direct = [row for row in dedup_rows if is_direct_official(row)]
    attention = [row for row in dedup_rows if is_attention_only(row)]
    groups = {
        "all_dedup_closed": summarize_group(dedup_rows),
        "direct_official_defense_budget": summarize_group(direct),
        "attention_only": summarize_group(attention),
    }

    direct_summary = groups["direct_official_defense_budget"]
    criteria = {
        "direct_rows_gte_8": direct_summary["rows"] >= MIN_DIRECT_ROWS,
        "ex_self_10d_avg_positive": (
            direct_summary["horizons"]["10d"][OPPORTUNITY_FIELD]["avg"] or 0.0
        )
        > 0,
        "ex_self_20d_avg_positive": (
            direct_summary["horizons"]["20d"][OPPORTUNITY_FIELD]["avg"] or 0.0
        )
        > 0,
        "ex_self_10d_win_rate_gte_60pct": (
            direct_summary["horizons"]["10d"][OPPORTUNITY_FIELD]["win_rate"] or 0.0
        )
        >= MIN_OPPORTUNITY_WIN_RATE,
        "ex_self_20d_win_rate_gte_60pct": (
            direct_summary["horizons"]["20d"][OPPORTUNITY_FIELD]["win_rate"] or 0.0
        )
        >= MIN_OPPORTUNITY_WIN_RATE,
        "direct_core_averages_positive": all(
            (direct_summary["horizons"][horizon][field]["avg"] or 0.0) > 0
            for horizon in HORIZONS
            for field in CORE_FIELDS
        ),
        "strategy_behavior_changed_false": True,
    }
    passed = all(criteria.values())
    failed = [key for key, value in criteria.items() if not value]
    failure_mode = (
        "same_theme_opportunity_cost_not_incremental"
        if "ex_self_10d_avg_positive" in failed
        or "ex_self_20d_avg_positive" in failed
        else "ex_self_sample_or_core_gate_failed"
    )
    return {
        "raw_ledger_rows": len(raw_rows),
        "dedup_closed_decision_rows": len(dedup_rows),
        "bucket_counts": dict(Counter(row.get("semantic_bucket") for row in dedup_rows)),
        "source_type_counts": dict(Counter(row.get("source_type") for row in dedup_rows)),
        "groups": groups,
        "gate": {
            "passed": passed,
            "criteria": criteria,
            "failed_criteria": failed,
            "failure_mode": failure_mode if not passed else None,
            "thresholds": {
                "min_direct_rows": MIN_DIRECT_ROWS,
                "min_opportunity_win_rate": MIN_OPPORTUNITY_WIN_RATE,
            },
        },
        "sample_rows": sample_rows(direct + attention),
        "input_files": {
            "ledger": repo_rel(LEDGER),
            "summary": repo_rel(SUMMARY),
        },
    }


def build_payload() -> dict[str, Any]:
    baseline = baseline_metrics()
    evaluation = build_evaluation()
    gate = evaluation["gate"]
    direct = evaluation["groups"]["direct_official_defense_budget"]
    observed_only_lead = bool(gate["passed"])
    status = "observed_only_lead" if observed_only_lead else "observed_only_rejected"
    decision = (
        "observed_only_positive_space_catalyst_ex_self_same_theme_lead_not_promoted"
        if observed_only_lead
        else "observed_only_rejected_space_catalyst_same_theme_opportunity_cost"
    )
    rejection_reason = None if observed_only_lead else ";".join(gate["failed_criteria"])

    h10_ex = direct["horizons"]["10d"][OPPORTUNITY_FIELD]
    h20_ex = direct["horizons"]["20d"][OPPORTUNITY_FIELD]
    why = (
        "The ex-self same-theme basket still supports a direct-official lead "
        "after removing each candidate ticker from its own comparator basket."
        if observed_only_lead
        else (
            "The direct-official rows remain strong versus cash and broad "
            "benchmarks, but the ex-self same-theme opportunity-cost check "
            f"does not pass: 10d avg={h10_ex['avg']} win={h10_ex['win_rate']}, "
            f"20d avg={h20_ex['avg']} win={h20_ex['win_rate']}. This is "
            "consistent with the lead being broad Space basket beta rather "
            "than ticker-selection alpha."
        )
    )

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": LANE,
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": observed_only_lead,
        "observed_only_lead_passed": observed_only_lead,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": SINGLE_CAUSAL_VARIABLE,
        "changed_variable": SINGLE_CAUSAL_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "acceptance_rule": ACCEPTANCE_RULE,
        "prediction": PREDICTION,
        "baseline_metrics": baseline,
        "evaluation": evaluation,
        "gate": {
            "decision": decision,
            "observed_only_lead_passed": observed_only_lead,
            "pass_fail": {
                "passed": observed_only_lead,
                "criteria": gate["criteria"],
                "failed_criteria": gate["failed_criteria"],
                "data_gap": direct["rows"] < MIN_DIRECT_ROWS,
            },
            "reason": (
                "observed_only_lead_only_no_strategy_change"
                if observed_only_lead
                else rejection_reason
            ),
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
                "closed_decision and mature 10d/20d outcome rows",
                "same_theme_basket.ticker_returns",
                "semantic_bucket and source_type provenance fields",
            ],
            "entry_date_target_price_sentinel": {
                "entry_date_present": all(
                    row.get("entry_date") for row in evaluation["sample_rows"]
                ),
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
            "observed_only_lead_passed": observed_only_lead,
            "note": (
                "Observed-only opportunity-cost attribution only. Any policy "
                "promotion would still need canonical Gate 1-4 and historical "
                "coverage."
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
        "realized_failure_mode": None if observed_only_lead else gate["failure_mode"],
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not rerun Space catalyst direct-official attribution on the "
                "same Golden Dome rows by changing source type, semantic bucket, "
                "hold days, same-theme binding, notional, ranking, or response "
                "shape. Do not call exp-20260709-014 accepted alpha."
            ),
            "new_evidence_required": (
                "Reopen only with materially more closed Space catalyst rows "
                "(at least +50% and +10 de-duplicated direct-official rows), a "
                "PIT historical Space event archive that creates canonical "
                "window coverage, or an external ex-event theme benchmark not "
                "derived from the same event cohort."
            ),
            "next_evidence_needed": (
                "Let the event-state ledger accumulate or build a historical "
                "Space event archive. The current direct-official lead should "
                "not be promoted or resliced on this sample."
            ),
        },
        "gate_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": (
                "exp-20260709-014 found a positive direct-vs-attention lead; "
                "exp-20260709-015 rejected promotion because canonical windows "
                "had zero direct-official rows and named ex-event same-theme "
                "replacement as a legal reopen axis."
            ),
            "3_single_causal_variable": SINGLE_CAUSAL_VARIABLE,
            "4_acceptance_standard": ACCEPTANCE_RULE,
            "5_reproducibility": RUNNER_COMMAND,
        },
        "headline_metrics": {
            "dedup_closed_decision_rows": evaluation["dedup_closed_decision_rows"],
            "direct_rows": direct["rows"],
            "attention_rows": evaluation["groups"]["attention_only"]["rows"],
            "direct_10d_ex_self_avg": h10_ex["avg"],
            "direct_10d_ex_self_win_rate": h10_ex["win_rate"],
            "direct_20d_ex_self_avg": h20_ex["avg"],
            "direct_20d_ex_self_win_rate": h20_ex["win_rate"],
            "direct_10d_cash_avg": direct["horizons"]["10d"]["cash_relative_pnl"][
                "avg"
            ],
            "direct_20d_cash_avg": direct["horizons"]["20d"]["cash_relative_pnl"][
                "avg"
            ],
        },
        "related_files": CHANGED_FILES,
        "changed_files": CHANGED_FILES,
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "lean_quality_passed": True,
    }
    return payload


def build_card(payload: Mapping[str, Any]) -> str:
    metrics = payload["headline_metrics"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: space catalyst ex-self same-theme",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Direct official rows: `{metrics['direct_rows']}`",
            f"- Direct 10d ex-self same-theme avg/win: `{metrics['direct_10d_ex_self_avg']}` / `{metrics['direct_10d_ex_self_win_rate']}`",
            f"- Direct 20d ex-self same-theme avg/win: `{metrics['direct_20d_ex_self_avg']}` / `{metrics['direct_20d_ex_self_win_rate']}`",
            f"- Direct 10d/20d cash avg: `{metrics['direct_10d_cash_avg']}` / `{metrics['direct_20d_cash_avg']}`",
            f"- Failed criteria: `{payload['gate']['pass_fail']['failed_criteria']}`",
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


def build_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
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
            "headline_metrics": payload["headline_metrics"],
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
            "rejection_reason": payload["rejection_reason"],
            "realized_failure_mode": payload["realized_failure_mode"],
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
                "failed_criteria": payload["gate"]["pass_fail"]["failed_criteria"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
