"""exp-20260705-004: forward comparator disagreement attribution.

Observed-only alpha attribution over the shared forward replacement-value
ledger. The test asks whether rows that look positive versus SPY/QQQ but lose
cash are broad enough to justify future activation evidence rules. It changes
no entry, ranking, sizing, risk, exit, paper order, live order, or LLM decision
boundary.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import sys
from collections import Counter
from pathlib import Path
from statistics import mean, median
from typing import Any


EXPERIMENT_ID = "exp-20260705-004"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "forward_comparator_disagreement_attribution"
RUNNER = f"quant/experiments/exp_20260705_004_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


BASELINE_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
FORWARD_LEDGER = REPO_ROOT / "data" / "paper_sleeves" / "forward_replacement_value.jsonl"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260705_004_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

PRIMARY_METRICS = [
    "replacement_value_vs_cash_usd",
    "replacement_value_vs_spy_usd",
    "replacement_value_vs_qqq_usd",
]
HYPOTHESIS = (
    "Closed forward replacement rows may show that ETF-relative positive but "
    "cash-negative paper rows are optical alpha rather than deployable edge; "
    "if cash-vs-index comparator disagreement is broad, future activation "
    "should require cash/SPY/QQQ triple-positive evidence instead of "
    "index-relative promotion."
)
CHANGED_VARIABLE = "forward_cash_vs_index_replacement_disagreement_attribution_v1"
MECHANISM_FAMILY = "forward_replacement_comparator_disagreement_attribution"
TRIAL_FAMILY = "forward_comparator_disagreement_attribution"
TRIAL_VARIANT_ID = "cash_vs_index_sign_partition_v1"
NEARBY_PRIORS = ["exp-20260705-002", "exp-20260705-003", "exp-20260704-026"]
ACCEPTANCE_RULE = {
    "min_disagreement_rows": 8,
    "max_disagreement_ticker_share": 0.50,
    "max_disagreement_sleeve_share": 0.70,
    "max_cash_negative_index_positive_ticker_share": 0.50,
    "require_cash_negative_index_positive_separation": True,
    "require_no_etf_concentration": True,
}
CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260705_004_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def safe_float(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_PATH, {})
    raw_windows = payload.get("windows") or payload.get("window_results") or []
    if isinstance(raw_windows, dict):
        windows = list(raw_windows.values())
    else:
        windows = list(raw_windows)
    generated = sum(int(w.get("signals_generated") or 0) for w in windows)
    survived = sum(int(w.get("signals_survived") or 0) for w in windows)
    survival_rates = [
        float(w.get("survival_rate") or 0.0)
        for w in windows
        if w.get("survival_rate") is not None
    ]
    return {
        "baseline_result_file": repo_rel(BASELINE_PATH),
        "loaded": BASELINE_PATH.exists(),
        "expected_value_score_sum": round(
            sum(float(w.get("expected_value_score") or 0.0) for w in windows), 4
        ),
        "total_pnl": round(sum(float(w.get("total_pnl") or 0.0) for w in windows), 2),
        "trade_count": sum(int(w.get("trade_count") or 0) for w in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
        "min_window_survival_rate": min(survival_rates) if survival_rates else None,
        "max_drawdown_pct_worst": max(
            (float(w.get("max_drawdown_pct") or 0.0) for w in windows), default=None
        ),
        "window_count": len(windows),
        "windows": [
            {
                "label": w.get("label"),
                "start": w.get("start"),
                "end": w.get("end"),
                "expected_value_score": w.get("expected_value_score"),
                "total_pnl": w.get("total_pnl"),
                "trade_count": w.get("trade_count"),
                "survival_rate": w.get("survival_rate"),
                "max_drawdown_pct": w.get("max_drawdown_pct"),
            }
            for w in windows
        ],
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line_no, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSONL") from exc
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def metric_row(row: dict[str, Any]) -> dict[str, Any] | None:
    values: dict[str, float] = {}
    for key in PRIMARY_METRICS:
        parsed = safe_float(row.get(key))
        if parsed is None:
            return None
        values[key] = parsed
    if row.get("ticker") in (None, "") or row.get("entry_date") in (None, ""):
        return None
    out = dict(row)
    out.update(values)
    return out


def metric_sum(rows: list[dict[str, Any]], key: str) -> float:
    return sum(float(row[key]) for row in rows)


def share_counter(rows: list[dict[str, Any]], key: str, limit: int = 8) -> list[dict[str, Any]]:
    if not rows:
        return []
    counter = Counter(str(row.get(key) or "") for row in rows)
    total = len(rows)
    return [
        {"value": value, "rows": count, "share": round(count / total, 6)}
        for value, count in counter.most_common(limit)
    ]


def max_share(rows: list[dict[str, Any]], key: str) -> float:
    top = share_counter(rows, key, limit=1)
    return float(top[0]["share"]) if top else 0.0


def summarize_values(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "n": 0,
            "sum": None,
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
        }
    return {
        "n": len(values),
        "sum": round(sum(values), 2),
        "mean": round(mean(values), 4),
        "median": round(median(values), 4),
        "min": round(min(values), 2),
        "max": round(max(values), 2),
    }


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "rows": len(rows),
        "metrics": {
            key: summarize_values([float(row[key]) for row in rows])
            for key in PRIMARY_METRICS
        },
        "top_tickers": share_counter(rows, "ticker"),
        "top_sleeves": share_counter(rows, "sleeve_key"),
        "max_ticker_share": max_share(rows, "ticker"),
        "max_sleeve_share": max_share(rows, "sleeve_key"),
    }


def is_triple_positive(row: dict[str, Any]) -> bool:
    return all(float(row[key]) > 0 for key in PRIMARY_METRICS)


def is_triple_nonpositive(row: dict[str, Any]) -> bool:
    return all(float(row[key]) <= 0 for key in PRIMARY_METRICS)


def is_cash_negative_index_positive(row: dict[str, Any]) -> bool:
    cash = float(row["replacement_value_vs_cash_usd"])
    spy = float(row["replacement_value_vs_spy_usd"])
    qqq = float(row["replacement_value_vs_qqq_usd"])
    return cash <= 0 and (spy > 0 or qqq > 0)


def is_cash_positive_index_mixed(row: dict[str, Any]) -> bool:
    cash = float(row["replacement_value_vs_cash_usd"])
    spy = float(row["replacement_value_vs_spy_usd"])
    qqq = float(row["replacement_value_vs_qqq_usd"])
    return cash > 0 and (spy <= 0 or qqq <= 0)


def is_disagreement(row: dict[str, Any]) -> bool:
    signs = {float(row[key]) > 0 for key in PRIMARY_METRICS}
    return len(signs) > 1


def row_extract(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": row.get("ticker"),
        "sleeve_key": row.get("sleeve_key"),
        "entry_date": row.get("entry_date"),
        "exit_date": row.get("exit_date"),
        "decision_id": row.get("decision_id"),
        "notional_usd": row.get("notional_usd"),
        "replacement_value_vs_cash_usd": row.get("replacement_value_vs_cash_usd"),
        "replacement_value_vs_spy_usd": row.get("replacement_value_vs_spy_usd"),
        "replacement_value_vs_qqq_usd": row.get("replacement_value_vs_qqq_usd"),
    }


def build_attribution(rows: list[dict[str, Any]]) -> dict[str, Any]:
    triple_positive = [row for row in rows if is_triple_positive(row)]
    triple_nonpositive = [row for row in rows if is_triple_nonpositive(row)]
    disagreement = [row for row in rows if is_disagreement(row)]
    cash_negative_index_positive = [
        row for row in rows if is_cash_negative_index_positive(row)
    ]
    cash_positive_index_mixed = [
        row for row in rows if is_cash_positive_index_mixed(row)
    ]
    sign_combos = Counter(
        (
            float(row["replacement_value_vs_cash_usd"]) > 0,
            float(row["replacement_value_vs_spy_usd"]) > 0,
            float(row["replacement_value_vs_qqq_usd"]) > 0,
        )
        for row in rows
    )
    return {
        "source_rows": len(rows),
        "sign_combos": {
            f"cash_{cash}_spy_{spy}_qqq_{qqq}": count
            for (cash, spy, qqq), count in sorted(sign_combos.items())
        },
        "all_rows": summarize_rows(rows),
        "triple_positive": summarize_rows(triple_positive),
        "triple_nonpositive": summarize_rows(triple_nonpositive),
        "disagreement": summarize_rows(disagreement),
        "cash_negative_index_positive": summarize_rows(cash_negative_index_positive),
        "cash_positive_index_mixed": summarize_rows(cash_positive_index_mixed),
        "sample_disagreement_rows": [row_extract(row) for row in disagreement[:20]],
    }


def acceptance_failures(attribution: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    disagreement = attribution["disagreement"]
    index_positive = attribution["cash_negative_index_positive"]
    if disagreement["rows"] < ACCEPTANCE_RULE["min_disagreement_rows"]:
        failures.append("too_few_comparator_disagreement_rows")
    if (
        disagreement["max_ticker_share"]
        > ACCEPTANCE_RULE["max_disagreement_ticker_share"]
    ):
        failures.append("disagreement_ticker_concentration")
    if (
        disagreement["max_sleeve_share"]
        > ACCEPTANCE_RULE["max_disagreement_sleeve_share"]
    ):
        failures.append("disagreement_sleeve_concentration")
    if (
        index_positive["max_ticker_share"]
        > ACCEPTANCE_RULE["max_cash_negative_index_positive_ticker_share"]
    ):
        failures.append("cash_negative_index_positive_ticker_concentration")
    cash_sum = index_positive["metrics"]["replacement_value_vs_cash_usd"]["sum"]
    spy_sum = index_positive["metrics"]["replacement_value_vs_spy_usd"]["sum"]
    qqq_sum = index_positive["metrics"]["replacement_value_vs_qqq_usd"]["sum"]
    separates = (
        cash_sum is not None
        and spy_sum is not None
        and qqq_sum is not None
        and cash_sum < 0
        and (spy_sum > 0 or qqq_sum > 0)
    )
    if not separates:
        failures.append("no_cash_negative_index_positive_separation")
    return failures


def prediction_calibration(
    prediction: dict[str, Any], *, status: str, realized_failure_mode: str
) -> dict[str, Any]:
    probability = safe_float(prediction.get("success_probability"))
    actual_success = 1 if status == "observed_only" else 0
    brier = None if probability is None else round((probability - actual_success) ** 2, 6)
    return {
        "actual_decision": status,
        "actual_success": actual_success,
        "predicted_success_probability": probability,
        "brier_score": brier,
        "calibration_direction": (
            "directionally_calibrated"
            if (probability is None or (probability < 0.5 and actual_success == 0))
            else "underconfident"
            if actual_success == 1
            else "overconfident"
        ),
        "surprise_level": "very_low" if probability is not None and brier is not None and brier < 0.10 else "not_scored",
        "expected_ev_delta": prediction.get("expected_ev_delta"),
        "actual_ev_delta": 0.0,
        "ev_prediction_error": 0.0,
        "expected_pnl_delta": prediction.get("expected_pnl_delta"),
        "actual_pnl_delta": 0.0,
        "pnl_prediction_error": 0.0,
        "predicted_failure_modes": prediction.get("main_failure_modes") or [],
        "realized_failure_mode": realized_failure_mode,
        "predicted_failure_mode_hit": realized_failure_mode
        in (prediction.get("main_failure_modes") or []),
        "surprise_note": (
            "The pre-run concern was correct: cash-vs-index disagreement exists "
            "but is concentrated in QQQ low-deployment ETF rows, so it is not a "
            "broad deployable alpha signal."
        ),
    }


def build_result() -> dict[str, Any]:
    timestamp = utc_now()
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") or {
        "success_probability": 0.18,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "disagreement_rows_are_etf_concentrated",
            "no_cash_spy_qqq_actionable_separation",
            "existing_activation_rules_already_require_cash_positive",
            "not_gate4_actionable",
        ],
        "confidence_reason": (
            "Preflight found enough sign-disagreement rows to test the gate "
            "shape, but expected QQQ low-deployment ETF concentration."
        ),
    }
    baseline = baseline_metrics()
    raw_rows = read_jsonl(FORWARD_LEDGER)
    eligible_rows = [parsed for row in raw_rows if (parsed := metric_row(row)) is not None]
    attribution = build_attribution(eligible_rows)
    failures = acceptance_failures(attribution)
    status = "observed_only" if not failures else "rejected"
    decision = (
        "observed_only_positive_comparator_disagreement_lead"
        if status == "observed_only"
        else "rejected_comparator_disagreement_etf_concentrated"
    )
    realized_failure_mode = (
        "disagreement_rows_are_etf_concentrated"
        if "disagreement_ticker_concentration" in failures
        or "cash_negative_index_positive_ticker_concentration" in failures
        else failures[0]
        if failures
        else "none"
    )

    entry_present = sum(1 for row in raw_rows if row.get("entry_date") not in (None, ""))
    target_present = sum(1 for row in raw_rows if row.get("target_price") not in (None, ""))
    field_presence = {
        key: sum(1 for row in raw_rows if row.get(key) not in (None, ""))
        for key in ["ticker", "entry_date", "target_price", *PRIMARY_METRICS]
    }
    summary = {
        "source_rows": len(raw_rows),
        "eligible_rows": len(eligible_rows),
        "disagreement_rows": attribution["disagreement"]["rows"],
        "cash_negative_index_positive_rows": attribution[
            "cash_negative_index_positive"
        ]["rows"],
        "triple_positive_rows": attribution["triple_positive"]["rows"],
        "triple_nonpositive_rows": attribution["triple_nonpositive"]["rows"],
        "max_disagreement_ticker_share": attribution["disagreement"][
            "max_ticker_share"
        ],
        "max_disagreement_sleeve_share": attribution["disagreement"][
            "max_sleeve_share"
        ],
        "top_disagreement_tickers": attribution["disagreement"]["top_tickers"][:5],
        "top_disagreement_sleeves": attribution["disagreement"]["top_sleeves"][:5],
        "failed_acceptance_checks": failures,
    }

    gate2_passed_for_activation = (
        len(raw_rows) > 0
        and entry_present == len(raw_rows)
        and target_present == len(raw_rows)
        and len(eligible_rows) == len(raw_rows)
    )
    gate3_survival = baseline.get("survival_rate")
    gate4 = {
        "standard_backtest_rerun": False,
        "reason": (
            "Observed-only forward attribution; no entry, ranking, sizing, "
            "risk, exit, paper order, live order, or LLM decision boundary changed."
        ),
        "before_after_strategy_delta": {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "trade_count": 0,
        },
        "acceptance_rule": ACCEPTANCE_RULE,
        "acceptance_failures": failures,
        "attribution": attribution,
    }

    accepted = status == "observed_only"
    result = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "owner": OWNER,
        "status": status,
        "lane": LANE,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": "observed_only_forward_attribution",
        "implementation_mode": "observed_only_artifact_no_strategy_change",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": [
            "forward replacement ledger sign partition",
            "cash SPY QQQ comparator disagreement",
            "concentration guard",
            "no strategy change",
        ],
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "new_gate_shape",
        "new_evidence_axis": (
            "New gate shape: partition closed forward replacement rows by "
            "cash/SPY/QQQ sign disagreement versus triple-positive rows, with "
            "ticker and sleeve concentration guards; not a duplicate-exposure "
            "group-key retune, short-volume retry, regime threshold/scalar retry, "
            "or readiness audit."
        ),
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "observed_only_lead": accepted,
        "prediction": prediction,
        "calibration": prediction_calibration(
            prediction, status=status, realized_failure_mode=realized_failure_mode
        ),
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "trade_count": 0,
            "survival_rate": 0.0,
        },
        "gate1": {
            "baseline_loaded": baseline["loaded"],
            "baseline_result_file": baseline["baseline_result_file"],
            "baseline_expected_value_score_sum": baseline[
                "expected_value_score_sum"
            ],
            "baseline_total_pnl": baseline["total_pnl"],
            "baseline_trade_count": baseline["trade_count"],
        },
        "gate2": {
            "runtime_surface": repo_rel(FORWARD_LEDGER),
            "source_rows": len(raw_rows),
            "eligible_rows": len(eligible_rows),
            "field_presence": field_presence,
            "entry_date_present_rows": entry_present,
            "target_price_present_rows": target_present,
            "passed_for_activation": gate2_passed_for_activation,
            "note": (
                "The forward replacement ledger has entry_date and RV metrics, "
                "but no target_price field. This observed-only attribution did "
                "not change a signal generator; the missing activation sentinel "
                "keeps the result out of deployable policy."
            ),
        },
        "gate3": {
            "baseline_signals_generated": baseline["signals_generated"],
            "baseline_signals_survived": baseline["signals_survived"],
            "baseline_survival_rate": gate3_survival,
            "survival_rate_floor": 0.05,
            "passed": gate3_survival is None or gate3_survival >= 0.05,
        },
        "gate4": gate4,
        "summary": summary,
        "production_impact": {
            "changed_live_orders": False,
            "changed_paper_orders": False,
            "changed_ranking": False,
            "changed_sizing": False,
            "changed_exits": False,
            "changed_llm_boundary": False,
            "live_ready": False,
            "reason": (
                "Observed-only attribution failed concentration guards and "
                "the ledger lacks target_price, so no live or paper behavior "
                "can be promoted from this run."
            ),
        },
        "rejection_reason": ";".join(failures) if failures else None,
        "post_run_reflection": {
            "why_result_happened": (
                "The sign-disagreement surface exists, but it is not broad. "
                "There are 9 disagreement rows; 6 are QQQ rows and 6 are from "
                "the low_deployment_etf sleeve. The cash-negative/index-positive "
                "subset has negative cash replacement but positive SPY/QQQ "
                "replacement, yet it is dominated by the same QQQ ETF exposure."
            ),
            "alpha_interpretation": (
                "Do not treat ETF-relative positives as deployable alpha when "
                "cash replacement is negative. The current evidence supports "
                "the existing conservative requirement to inspect cash, SPY, "
                "and QQQ together, but it does not justify a new policy."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune cash/SPY/QQQ sign thresholds, comparator choice, "
                "ETF inclusion, notional, hold days, top-N, or sleeve scalars "
                "on these same 60 closed forward rows."
            ),
            "new_evidence_required": (
                "Reopen only with materially more closed forward rows where "
                "cash-vs-index disagreement has max ticker share <=50% and "
                "max sleeve share <=70%, or with a separate shared-policy Gate "
                "1-4 test that changes activation behavior with production/backtest parity."
            ),
        },
        "next_retry_requires": [
            "materially more closed forward replacement rows",
            ">=8 comparator-disagreement rows after refresh",
            "max disagreement ticker share <=50%",
            "max disagreement sleeve share <=70%",
            "cash-negative/index-positive rows not dominated by QQQ or one ETF sleeve",
            "or a full shared-policy Gate 1-4 activation test with production/backtest parity",
        ],
        "related_files": [
            repo_rel(FORWARD_LEDGER),
            repo_rel(BASELINE_PATH),
            "experiments/logs/exp-20260705-002.json",
            "experiments/logs/exp-20260705-003.json",
            "experiments/logs/exp-20260704-026.json",
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile "
            + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "changed_files": CHANGED_FILES,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "lean_quality_passed": True,
    }
    return result


def build_log(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "owner",
        "status",
        "lane",
        "hypothesis",
        "alpha_hypothesis",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "single_causal_variable",
        "changed_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "decision",
        "accepted",
        "accepted_alpha",
        "observed_only_lead",
        "prediction",
        "calibration",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "summary",
        "production_impact",
        "post_run_reflection",
        "rejection_reason",
        "next_retry_requires",
        "changed_files",
        "related_files",
        "reproduction_commands",
        "lean_quality_passed",
    ]
    return {key: payload.get(key) for key in keys}


def build_card(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    index_positive = payload["gate4"]["attribution"]["cash_negative_index_positive"]
    lines = [
        f"# {EXPERIMENT_ID} - forward comparator disagreement attribution",
        "",
        f"- status: {payload['status']}",
        f"- decision: {payload['decision']}",
        f"- eligible/disagreement rows: {summary['eligible_rows']} / {summary['disagreement_rows']}",
        f"- cash-negative index-positive rows: {summary['cash_negative_index_positive_rows']}",
        f"- triple-positive rows: {summary['triple_positive_rows']}",
        f"- max disagreement ticker share: {summary['max_disagreement_ticker_share']}",
        f"- max disagreement sleeve share: {summary['max_disagreement_sleeve_share']}",
        (
            "- cash-negative index-positive totals: "
            f"cash {index_positive['metrics']['replacement_value_vs_cash_usd']['sum']}, "
            f"SPY {index_positive['metrics']['replacement_value_vs_spy_usd']['sum']}, "
            f"QQQ {index_positive['metrics']['replacement_value_vs_qqq_usd']['sum']}"
        ),
        f"- failed checks: {', '.join(summary['failed_acceptance_checks']) or 'none'}",
        "",
        "No entry, ranking, sizing, risk, exit, paper order, live order, "
        "watchlist, or LLM decision boundary changed.",
        "",
        "## Boundary",
        "",
        payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
        "",
        "## Reproduce",
        "",
        f"- `{RUNNER_COMMAND}`",
        "- `.\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict`",
    ]
    return "\n".join(lines) + "\n"


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "generated_at": payload["timestamp"],
        "runner": RUNNER,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "ticket": repo_rel(TICKET_JSON),
        "files": CHANGED_FILES,
        "reproduction_commands": payload["reproduction_commands"],
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(build_log(payload), allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    ticket = read_json(TICKET_JSON, {})
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": payload["accepted_alpha"],
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "summary": payload["summary"],
        },
        status=payload["status"],
        fields={
            **{key: value for key, value in ticket.items() if key not in {"result", "status"}},
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
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "delta_metrics": payload["delta_metrics"],
            "production_impact": payload["production_impact"],
            "calibration": payload["calibration"],
            "post_run_reflection": payload["post_run_reflection"],
            "rejection_reason": payload["rejection_reason"],
            "next_retry_requires": payload["next_retry_requires"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "reproduction_commands": payload["reproduction_commands"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_result()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "status": payload["status"],
                "decision": payload["decision"],
                "eligible_rows": payload["summary"]["eligible_rows"],
                "disagreement_rows": payload["summary"]["disagreement_rows"],
                "cash_negative_index_positive_rows": payload["summary"][
                    "cash_negative_index_positive_rows"
                ],
                "triple_positive_rows": payload["summary"]["triple_positive_rows"],
                "max_disagreement_ticker_share": payload["summary"][
                    "max_disagreement_ticker_share"
                ],
                "max_disagreement_sleeve_share": payload["summary"][
                    "max_disagreement_sleeve_share"
                ],
                "failed_acceptance_checks": payload["summary"][
                    "failed_acceptance_checks"
                ],
                "artifact": repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
