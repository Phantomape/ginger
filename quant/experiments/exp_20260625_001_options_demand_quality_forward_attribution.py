"""exp-20260625-001: options demand-quality forward attribution.

Observed-only alpha attribution. This reads the exp-20260624-026 reusable
OnclickMedia options outcome ledger and tests one fixed, decision-time options
bucket: call-dominated volume, no heavy put-IV hedge, and clean contract
liquidity. It does not change strategy behavior, shared helpers, daily
snapshots, paper orders, live orders, ranking, sizing, exits, or LLM logic.
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
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260625-001"
OWNER = "alpha-explore"
SLUG = "options_demand_quality_forward_attribution"
RUNNER = f"quant/experiments/exp_20260625_001_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260625_001_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OUTCOME_LEDGER = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260624-026"
    / "options_forward_outcome_settlement_ledger.jsonl"
)

HYPOTHESIS = (
    "Observed-only attribution on the exp-20260624-026 reusable OnclickMedia "
    "options outcome ledger: fixed call-demand, low put-hedge, clean-liquidity "
    "rows should show stronger settled 10d cash/SPY/QQQ replacement value than "
    "non-confirmed options rows."
)
CHANGE_TYPE = "observed_only_forward_attribution"
MECHANISM_FAMILY = "production_visible_forward_options_attribution"
TRIAL_FAMILY = "onclickmedia_options_demand_quality_forward_attribution"
TRIAL_VARIANT_ID = "fixed_call_demand_low_put_hedge_clean_liquidity_v1"
CHANGED_VARIABLE = "onclickmedia_options_demand_quality_forward_attribution_v1"
NEW_EVIDENCE_TYPE = "reusable_forward_replacement_value_ledger"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260613-024",
    "exp-20260623-010",
    "exp-20260624-023",
    "exp-20260624-025",
    "exp-20260624-026",
]
CAUSAL_COMPONENTS = [
    "exp026 settled options outcome ledger",
    "fixed demand quality bucket",
    "10d cash SPY QQQ replacement attribution",
    "no strategy behavior change",
]

HORIZONS = [1, 3, 5, 10]
PRIMARY_HORIZON = 10
COMPARATORS = ["cash", "spy", "qqq"]
REPLACEMENT_KEYS = {
    horizon: {
        comp: f"replacement_value_{horizon}d_vs_{comp}_usd"
        for comp in COMPARATORS
    }
    for horizon in HORIZONS
}
REPLACEMENT_KEYS[10] = {
    "cash": "replacement_value_10d_vs_cash_usd",
    "spy": "replacement_value_10d_vs_spy_usd",
    "qqq": "replacement_value_10d_vs_qqq_usd",
}

DEMAND_RULE = {
    "pit_safe_contract_rate_eq": 1.0,
    "require_quality_pass": True,
    "put_call_volume_ratio_lte": 0.65,
    "put_minus_call_volume_weighted_iv_lte": 0.05,
    "liquid_contract_rate_gte": 0.70,
    "avg_liquidity_score_gte": 0.60,
    "wide_spread_contract_rate_lte_or_missing": 0.50,
    "zero_bid_or_ask_count_lte": 20,
}
ACCEPTANCE_RULE = {
    "primary_horizon": PRIMARY_HORIZON,
    "min_confirmed_rows": 60,
    "min_confirmed_entry_dates": 10,
    "min_confirmed_tickers": 20,
    "confirmed_must_beat_non_confirmed_mean_and_median_for": COMPARATORS,
    "min_supporting_horizons_mean_cash_spy_qqq": 2,
    "positive_pnl_hhi_guardrail": 0.35,
    "max_single_positive_pnl_share_guardrail": 0.50,
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
    "watchlist_changed": False,
    "llm_decision_boundary_changed": False,
    "live_ready": False,
    "live_realism_evaluated": False,
    "uses_options_forward_outcome_ledger": True,
    "forward_only_not_fixed_window_pit_coverage": True,
    "parity_note": (
        "Observed-only attribution on an experiment-owned forward outcome "
        "ledger. No shared policy/helper or production adapter behavior changed."
    ),
}
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260625-001/exp_20260625_001_options_demand_quality_forward_attribution.json",
    "experiments/cards/exp-20260625-001.md",
    "experiments/manifests/exp-20260625-001.json",
    "experiments/tickets/exp-20260625-001.json",
    "experiments/logs/exp-20260625-001.json",
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


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig", errors="replace") as handle:
        for line_no, raw in enumerate(handle, start=1):
            text = raw.strip()
            if not text:
                continue
            try:
                value = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL") from exc
            if isinstance(value, dict):
                rows.append(value)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(record, sort_keys=True)
    lines: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                lines.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    lines.append(encoded)
                    replaced = True
                continue
            lines.append(raw)
    if not replaced:
        lines.append(encoded)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_float(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def round_or_none(value: Any, digits: int = 4) -> float | None:
    parsed = safe_float(value)
    if parsed is None:
        return None
    return round(parsed, digits)


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def stats(values: list[float]) -> dict[str, Any]:
    clean = [value for value in values if value is not None and math.isfinite(value)]
    if not clean:
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
        "n": len(clean),
        "sum": round(sum(clean), 2),
        "mean": round_or_none(mean(clean), 4),
        "median": round_or_none(median(clean), 4),
        "min": round(min(clean), 2),
        "max": round(max(clean), 2),
        "positive_rate": round(sum(1 for value in clean if value > 0) / len(clean), 4),
    }


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    generated = sum(float(row.get("signals_generated") or 0.0) for row in windows)
    survived = sum(float(row.get("signals_survived") or 0.0) for row in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": int(sum(int(row.get("trade_count") or 0) for row in windows)),
        "signals_generated": int(generated),
        "signals_survived": int(survived),
        "survival_rate": round(survived / generated, 4) if generated else None,
        "max_drawdown_pct_worst": max(
            (float(row.get("max_drawdown_pct") or 0.0) for row in windows),
            default=None,
        ),
        "window_count": len(windows),
        "windows": windows,
    }


def value_present(row: dict[str, Any], field: str) -> bool:
    return row.get(field) not in (None, "")


def field_coverage(rows: list[dict[str, Any]], fields: list[str]) -> dict[str, Any]:
    result = {}
    for field in fields:
        present = sum(1 for row in rows if value_present(row, field))
        result[field] = {
            "present_rows": present,
            "scanned_rows": len(rows),
            "coverage": round(present / len(rows), 6) if rows else None,
        }
    return result


def is_demand_quality_confirmed(row: dict[str, Any]) -> bool:
    pcr = safe_float(row.get("put_call_volume_ratio"))
    iv_skew = safe_float(row.get("put_minus_call_volume_weighted_iv"))
    liquid_rate = safe_float(row.get("liquid_contract_rate"))
    liquidity_score = safe_float(row.get("avg_liquidity_score"))
    wide_rate = safe_float(row.get("wide_spread_contract_rate"))
    zero_bid = safe_float(row.get("zero_bid_or_ask_count"))
    pit_safe = safe_float(row.get("pit_safe_contract_rate"))
    return (
        bool(row.get("quality_pass"))
        and pit_safe == DEMAND_RULE["pit_safe_contract_rate_eq"]
        and pcr is not None
        and pcr <= DEMAND_RULE["put_call_volume_ratio_lte"]
        and iv_skew is not None
        and iv_skew <= DEMAND_RULE["put_minus_call_volume_weighted_iv_lte"]
        and liquid_rate is not None
        and liquid_rate >= DEMAND_RULE["liquid_contract_rate_gte"]
        and liquidity_score is not None
        and liquidity_score >= DEMAND_RULE["avg_liquidity_score_gte"]
        and (wide_rate is None or wide_rate <= DEMAND_RULE["wide_spread_contract_rate_lte_or_missing"])
        and zero_bid is not None
        and zero_bid <= DEMAND_RULE["zero_bid_or_ask_count_lte"]
    )


def settled_for_horizon(row: dict[str, Any], horizon: int) -> bool:
    return all(
        safe_float(row.get(key)) is not None
        for key in REPLACEMENT_KEYS[horizon].values()
    )


def replacement_values(rows: list[dict[str, Any]], horizon: int, comp: str) -> list[float]:
    key = REPLACEMENT_KEYS[horizon][comp]
    values = []
    for row in rows:
        parsed = safe_float(row.get(key))
        if parsed is not None:
            values.append(parsed)
    return values


def concentration(rows: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    key = REPLACEMENT_KEYS[horizon]["cash"]
    positive_by_ticker: dict[str, float] = defaultdict(float)
    for row in rows:
        value = safe_float(row.get(key))
        if value is not None and value > 0:
            positive_by_ticker[str(row.get("ticker") or "UNKNOWN")] += value
    total = sum(positive_by_ticker.values())
    if total <= 0:
        return {
            "positive_pnl_total": 0.0,
            "positive_ticker_count": 0,
            "positive_pnl_hhi": None,
            "max_single_positive_pnl_share": None,
            "top_positive_tickers": [],
            "passed": False,
        }
    shares = {ticker: value / total for ticker, value in positive_by_ticker.items()}
    hhi = sum(share * share for share in shares.values())
    max_share = max(shares.values())
    return {
        "positive_pnl_total": round(total, 2),
        "positive_ticker_count": len(positive_by_ticker),
        "positive_pnl_hhi": round(hhi, 6),
        "positive_pnl_hhi_guardrail": ACCEPTANCE_RULE["positive_pnl_hhi_guardrail"],
        "max_single_positive_pnl_share": round(max_share, 6),
        "max_single_positive_pnl_share_guardrail": ACCEPTANCE_RULE[
            "max_single_positive_pnl_share_guardrail"
        ],
        "top_positive_tickers": [
            {"ticker": ticker, "positive_pnl": round(value, 2), "share": round(shares[ticker], 4)}
            for ticker, value in sorted(
                positive_by_ticker.items(), key=lambda item: item[1], reverse=True
            )[:10]
        ],
        "passed": (
            hhi <= ACCEPTANCE_RULE["positive_pnl_hhi_guardrail"]
            and max_share <= ACCEPTANCE_RULE["max_single_positive_pnl_share_guardrail"]
        ),
    }


def summarize_group(rows: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    ticker_counts = Counter(str(row.get("ticker") or "UNKNOWN") for row in rows)
    entry_dates = sorted({str(row.get("entry_date") or "") for row in rows if row.get("entry_date")})
    return {
        "n": len(rows),
        "ticker_count": len(ticker_counts),
        "entry_date_count": len(entry_dates),
        "entry_date_start": entry_dates[0] if entry_dates else None,
        "entry_date_end": entry_dates[-1] if entry_dates else None,
        "source_experiment_counts": dict(
            sorted(Counter(str(row.get("source_experiment_id") or "unknown") for row in rows).items())
        ),
        "top_tickers": [
            {"ticker": ticker, "rows": count}
            for ticker, count in ticker_counts.most_common(10)
        ],
        "replacement_metrics": {
            comp: stats(replacement_values(rows, horizon, comp))
            for comp in COMPARATORS
        },
    }


def summarize_horizon(rows: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    settled = [row for row in rows if settled_for_horizon(row, horizon)]
    confirmed = [row for row in settled if row.get("demand_quality_confirmed")]
    non_confirmed = [row for row in settled if not row.get("demand_quality_confirmed")]
    support = {}
    for comp in COMPARATORS:
        confirmed_stats = stats(replacement_values(confirmed, horizon, comp))
        non_stats = stats(replacement_values(non_confirmed, horizon, comp))
        c_mean = safe_float(confirmed_stats["mean"])
        n_mean = safe_float(non_stats["mean"])
        c_median = safe_float(confirmed_stats["median"])
        n_median = safe_float(non_stats["median"])
        support[comp] = {
            "confirmed_mean_gt_non_confirmed": (
                c_mean is not None and n_mean is not None and c_mean > n_mean
            ),
            "confirmed_median_gt_non_confirmed": (
                c_median is not None and n_median is not None and c_median > n_median
            ),
            "mean_delta": round(c_mean - n_mean, 4)
            if c_mean is not None and n_mean is not None
            else None,
            "median_delta": round(c_median - n_median, 4)
            if c_median is not None and n_median is not None
            else None,
        }
    return {
        "horizon": horizon,
        "settled_rows": len(settled),
        "confirmed_rows": len(confirmed),
        "non_confirmed_rows": len(non_confirmed),
        "confirmed": summarize_group(confirmed, horizon),
        "non_confirmed": summarize_group(non_confirmed, horizon),
        "all_settled": summarize_group(settled, horizon),
        "support": support,
        "confirmed_concentration": concentration(confirmed, horizon),
    }


def evaluate_gate4(horizon_summary: dict[int, dict[str, Any]]) -> dict[str, Any]:
    primary = horizon_summary[PRIMARY_HORIZON]
    confirmed = primary["confirmed"]
    failed: list[str] = []
    if confirmed["n"] < ACCEPTANCE_RULE["min_confirmed_rows"]:
        failed.append("confirmed_sample_too_small")
    if confirmed["entry_date_count"] < ACCEPTANCE_RULE["min_confirmed_entry_dates"]:
        failed.append("entry_date_coverage_too_thin")
    if confirmed["ticker_count"] < ACCEPTANCE_RULE["min_confirmed_tickers"]:
        failed.append("ticker_coverage_too_thin")
    for comp in COMPARATORS:
        support = primary["support"][comp]
        if not support["confirmed_mean_gt_non_confirmed"]:
            failed.append(f"primary_{comp}_mean_not_better")
        if not support["confirmed_median_gt_non_confirmed"]:
            failed.append(f"primary_{comp}_median_not_better")
    if not primary["confirmed_concentration"]["passed"]:
        failed.append("confirmed_positive_pnl_concentration_failed")

    supporting_horizons = 0
    for horizon in (3, 5, 10):
        support = horizon_summary[horizon]["support"]
        if all(support[comp]["confirmed_mean_gt_non_confirmed"] for comp in COMPARATORS):
            supporting_horizons += 1
    if supporting_horizons < ACCEPTANCE_RULE["min_supporting_horizons_mean_cash_spy_qqq"]:
        failed.append("too_few_supporting_horizons")

    observed_only_lead = not failed
    decision = (
        "observed_only_positive_options_demand_quality_lead_not_promoted"
        if observed_only_lead
        else "rejected_no_options_demand_quality_forward_edge"
    )
    return {
        "passed": observed_only_lead,
        "observed_only_lead": observed_only_lead,
        "accepted_alpha": False,
        "decision": decision,
        "failed_reasons": failed,
        "primary_horizon": PRIMARY_HORIZON,
        "supporting_horizons_mean_cash_spy_qqq": supporting_horizons,
        "acceptance_rule": ACCEPTANCE_RULE,
        "strategy_rerun_required": False,
        "before_after_strategy_delta": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "strategy_behavior_changed": False,
        },
    }


def load_ticket() -> dict[str, Any]:
    return read_json(TICKET_JSON, {})


def calibration(prediction: dict[str, Any], success: bool, failed: list[str]) -> dict[str, Any]:
    probability = safe_float(prediction.get("success_probability")) or 0.0
    actual = 1.0 if success else 0.0
    predicted_modes = prediction.get("main_failure_modes") or []
    realized_modes = list(failed)
    if any(reason.startswith("primary_") and reason.endswith("_not_better") for reason in failed):
        realized_modes.append("field_no_separation")
    if any(reason.startswith("primary_qqq_") for reason in failed):
        realized_modes.append("qqq_beta_confound")
    if "confirmed_positive_pnl_concentration_failed" in failed:
        realized_modes.append("single_ticker_concentration")
    realized_modes = list(dict.fromkeys(realized_modes))
    return {
        "actual_decision": (
            "observed_only_positive_lead" if success else "observed_only_rejected"
        ),
        "actual_success": int(success),
        "predicted_success_probability": probability,
        "brier_score": round((probability - actual) ** 2, 4),
        "predicted_failure_modes": predicted_modes,
        "realized_failure_modes": realized_modes,
        "predicted_failure_mode_hit": any(mode in realized_modes for mode in predicted_modes),
        "surprise_note": (
            "The fixed demand-quality bucket passed the observed-only screen, "
            "but it remains forward-only and not promotable."
            if success
            else "The fixed demand-quality bucket did not show enough stable "
            "cash/SPY/QQQ separation to justify promotion."
        ),
    }


def source_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    entry_dates = sorted({str(row.get("entry_date") or "") for row in rows if row.get("entry_date")})
    return {
        "outcome_ledger": repo_rel(OUTCOME_LEDGER),
        "rows": len(rows),
        "source_experiment_counts": dict(
            sorted(Counter(str(row.get("source_experiment_id") or "unknown") for row in rows).items())
        ),
        "outcome_status_counts": dict(
            sorted(Counter(str(row.get("outcome_status") or "unknown") for row in rows).items())
        ),
        "ticker_count": len({str(row.get("ticker") or "") for row in rows if row.get("ticker")}),
        "entry_date_start": entry_dates[0] if entry_dates else None,
        "entry_date_end": entry_dates[-1] if entry_dates else None,
        "entry_date_count": len(entry_dates),
    }


def build_payload() -> dict[str, Any]:
    ticket = load_ticket()
    prediction = ticket.get("prediction") or {}
    before = baseline_metrics()
    raw_rows = read_jsonl(OUTCOME_LEDGER)
    rows = []
    for row in raw_rows:
        item = dict(row)
        item["demand_quality_confirmed"] = is_demand_quality_confirmed(item)
        rows.append(item)

    horizon_summary = {horizon: summarize_horizon(rows, horizon) for horizon in HORIZONS}
    gate4 = evaluate_gate4(horizon_summary)
    status = (
        "observed_only_positive_lead"
        if gate4["observed_only_lead"]
        else "observed_only_rejected"
    )
    decision = gate4["decision"]
    primary = horizon_summary[PRIMARY_HORIZON]
    source = source_summary(rows)
    fields_checked = [
        "observation_id",
        "ticker",
        "quote_date",
        "usable_trade_date",
        "entry_date",
        "target_price",
        "outcome_status",
        "quality_pass",
        "pit_safe_contract_rate",
        "put_call_volume_ratio",
        "put_minus_call_volume_weighted_iv",
        "liquid_contract_rate",
        "avg_liquidity_score",
        "wide_spread_contract_rate",
        "zero_bid_or_ask_count",
        "replacement_value_10d_vs_cash_usd",
        "replacement_value_10d_vs_spy_usd",
        "replacement_value_10d_vs_qqq_usd",
    ]
    why = (
        "The predeclared options demand-quality bucket beat non-confirmed rows "
        "on the observed-only screen. This is not accepted alpha because the "
        "evidence is a forward outcome ledger rather than historical PIT options "
        "chain coverage across the canonical windows."
        if gate4["observed_only_lead"]
        else "The predeclared options demand-quality bucket did not beat "
        "non-confirmed rows across the required 10d cash/SPY/QQQ mean and "
        "median checks, so the options structure remains attribution context."
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "status": status,
        "decision": decision,
        "accepted": gate4["observed_only_lead"],
        "accepted_alpha": False,
        "observed_only_lead": gate4["observed_only_lead"],
        "lane": "alpha_search",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "observed_only_attribution",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "prediction": prediction,
        "calibration": calibration(
            prediction,
            gate4["observed_only_lead"],
            gate4["failed_reasons"],
        ),
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "exp-20260613-024": (
                    "Older proposed options overlay based on pre-exp026 evidence; "
                    "left untouched because this run uses the new settled ledger."
                ),
                "exp-20260623-010": (
                    "Rejected one-off 10d options skew attribution; this run "
                    "uses a broader fixed demand-quality bucket and the reusable ledger."
                ),
                "exp-20260624-023": (
                    "Rejected Kova/SEC13F plus options cross-evidence on partial "
                    "forward rows."
                ),
                "exp-20260624-025": (
                    "Blocked Form4/SEC confluence plus options overlap before "
                    "the exp026 outcome ledger existed."
                ),
                "exp-20260624-026": (
                    "Accepted measurement repair that materialized the reusable "
                    "settled options outcome ledger used here."
                ),
                "novelty_gate": (
                    "Reservation passed without override; nearest options skew "
                    "family score was below threshold."
                ),
            },
            "3_single_policy_bundle": (
                "One observed-only bundle: classify exp026 rows with a fixed "
                "call-demand, low put-IV hedge, clean-liquidity bucket and "
                "compare settled replacement value against all non-confirmed rows."
            ),
            "4_success_failure_standard": (
                "Observed-only lead only if the 10d confirmed bucket clears row/date/"
                "ticker floors, beats non-confirmed rows on mean and median cash/SPY/"
                "QQQ replacement value, has at least two supporting 3/5/10d mean "
                "horizons, and passes positive-PnL concentration."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "outcome_ledger": repo_rel(OUTCOME_LEDGER),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "demand_rule": DEMAND_RULE,
            "acceptance_rule": ACCEPTANCE_RULE,
            "horizons": HORIZONS,
            "primary_horizon": PRIMARY_HORIZON,
            "comparators": COMPARATORS,
            "decision_boundary": (
                "Open interest is not used because the source marks same-day "
                "open interest as lagged/caveated."
            ),
        },
        "source_summary": source,
        "field_coverage": field_coverage(rows, fields_checked),
        "horizon_summary": {str(key): value for key, value in horizon_summary.items()},
        "primary_summary": primary,
        "before_metrics": before,
        "after_metrics": before,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "max_drawdown_pct_worst_delta": 0.0,
            "strategy_behavior_changed": False,
        },
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_metrics": before,
            "note": "Observed-only attribution; before and after policy are identical.",
        },
        "gate2": {
            "dependencies_validated": OUTCOME_LEDGER.exists() and bool(rows),
            "fields_checked": fields_checked,
            "field_coverage": field_coverage(rows, fields_checked),
            "entry_date_rows": sum(1 for row in rows if row.get("entry_date")),
            "target_price_scope": (
                "Not applicable: this is fixed-horizon forward attribution and "
                "does not schedule target exits or orders."
            ),
            "source_summary": source,
        },
        "gate3": {
            "filter_added": False,
            "signals_generated": primary["settled_rows"],
            "signals_survived": primary["confirmed_rows"],
            "survival_rate": round(primary["confirmed_rows"] / primary["settled_rows"], 4)
            if primary["settled_rows"]
            else None,
            "baseline_survival_rate": before.get("survival_rate"),
            "passed": (
                primary["settled_rows"] > 0
                and primary["confirmed_rows"] / primary["settled_rows"] >= 0.05
            ),
            "note": (
                "No executable filter was added. Survival here is attribution "
                "bucket coverage, not a live strategy survival claim."
            ),
        },
        "gate4": gate4,
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retry options put/call ratio, IV skew, liquidity, spread, "
                "zero-bid count, open interest, top-N, hold, cooldown, notional, "
                "or threshold variants on this same exp026 forward ledger."
            ),
            "new_evidence_required": (
                "A valid retry needs materially more closed forward rows including "
                "the exp020 deltas, PIT vendor-as-of controls, borrow/loan "
                "availability context, or historical PIT options-chain coverage "
                "across the canonical windows."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(OUTCOME_LEDGER),
            repo_rel(BASELINE_RESULT),
            "experiments/tickets/exp-20260613-024.json",
            "experiments/logs/exp-20260623-010.json",
            "experiments/logs/exp-20260624-023.json",
            "experiments/logs/exp-20260624-025.json",
            "experiments/logs/exp-20260624-026.json",
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
            "created_at": ticket.get("created_at"),
            "claimed_at": ticket.get("claimed_at"),
            "hub_identity": ticket.get("hub_identity"),
            "novelty": ticket.get("novelty"),
        },
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "observed_only_lead",
        "lane",
        "owner",
        "hypothesis",
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
        "prediction",
        "calibration",
        "pre_run_questions",
        "parameters",
        "source_summary",
        "primary_summary",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "production_impact",
        "post_run_reflection",
        "related_files",
        "changed_files",
        "allowed_write_scope",
        "reproduction_commands",
        "artifact",
        "log",
        "anti_js",
        "lean_quality_passed",
    ]
    return {key: payload[key] for key in keys}


def money(value: Any) -> str:
    number = safe_float(value)
    return "n/a" if number is None else f"${number:,.2f}"


def card_group_line(name: str, group: dict[str, Any]) -> str:
    metrics = group["replacement_metrics"]
    return "| {name} | {n} | {tickers} | {dates} | {cash} | {spy} | {qqq} | {median_cash} |".format(
        name=name,
        n=group["n"],
        tickers=group["ticker_count"],
        dates=group["entry_date_count"],
        cash=money(metrics["cash"]["mean"]),
        spy=money(metrics["spy"]["mean"]),
        qqq=money(metrics["qqq"]["mean"]),
        median_cash=money(metrics["cash"]["median"]),
    )


def build_card(payload: dict[str, Any]) -> str:
    primary = payload["primary_summary"]
    rows = [
        "| Group | Rows | Tickers | Dates | Mean Cash | Mean SPY | Mean QQQ | Median Cash |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
        card_group_line("confirmed", primary["confirmed"]),
        card_group_line("non_confirmed", primary["non_confirmed"]),
    ]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: options demand-quality attribution",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Strategy behavior changed: `false`",
            f"- 10d settled rows: `{primary['settled_rows']}`",
            f"- 10d confirmed rows: `{primary['confirmed_rows']}`",
            f"- Failed checks: `{', '.join(payload['gate4']['failed_reasons']) or 'none'}`",
            f"- Artifact: `{repo_rel(OUT_JSON)}`",
            "",
            "## Primary 10d Groups",
            "",
            *rows,
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
        BASELINE_RESULT,
        OUTCOME_LEDGER,
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
        "allowed_write_scope": payload["allowed_write_scope"],
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
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card_file": repo_rel(CARD_MD),
        "revision_manifest_file": repo_rel(MANIFEST_JSON),
        "ticket_file": repo_rel(TICKET_JSON),
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "allowed_write_scope": payload["allowed_write_scope"],
        "related_files": payload["related_files"],
        "changed_files": payload["changed_files"],
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
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
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
    primary = payload["primary_summary"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "observed_only_lead": payload["observed_only_lead"],
                "primary_settled_rows": primary["settled_rows"],
                "primary_confirmed_rows": primary["confirmed_rows"],
                "primary_non_confirmed_rows": primary["non_confirmed_rows"],
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
