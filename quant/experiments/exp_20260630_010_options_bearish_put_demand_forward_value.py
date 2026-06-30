"""exp-20260630-010: bearish options put-demand forward attribution.

Observed-only alpha search. This reads the refreshed exp-20260630-008
OnclickMedia options forward outcome ledger and tests one fixed risk-allocation
context: liquid rows with high put/call volume and positive put IV skew should
have weaker settled 10d cash/SPY/QQQ replacement value than the remaining
quality options rows.

No strategy behavior, shared helper, daily snapshot, paper order, live order,
ranking, sizing, exit, watchlist, or LLM behavior changes.
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
from typing import Any, Iterable, Mapping


EXPERIMENT_ID = "exp-20260630-010"
OWNER = "alpha-explore"
SLUG = "options_bearish_put_demand_forward_value"
RUNNER = f"quant/experiments/exp_20260630_010_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


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
    / "exp-20260630-008"
    / "options_forward_outcome_refresh_all_current_sources.jsonl"
)

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260630_010_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Refreshed closed OnclickMedia options forward rows may reveal that liquid "
    "high put-demand / high put-IV pressure marks weaker 10-day replacement "
    "value and can become a future risk-allocation context."
)
CHANGE_TYPE = "observed_only_forward_attribution"
MECHANISM_FAMILY = "production_visible_forward_options_attribution"
TRIAL_FAMILY = "onclickmedia_options_bearish_put_demand_forward_value"
TRIAL_VARIANT_ID = "fixed_liquid_put_volume_iv_pressure_v1"
CHANGED_VARIABLE = "onclickmedia_options_bearish_put_demand_forward_value_v1"
NEW_EVIDENCE_TYPE = "materially_more_closed_options_forward_rows"
NEW_EVIDENCE_AXIS = (
    "exp-20260630-008 materially expanded and re-settled the OnclickMedia "
    "options forward ledger to 1544 closed 10d rows from 2026-05/06, beyond "
    "the exp-20260625-001 outcome sample; this is not a threshold retune on "
    "unchanged rows."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260625-001",
    "exp-20260630-008",
]
CAUSAL_COMPONENTS = [
    "fixed bearish put-demand predicate",
    "refreshed closed outcome ledger",
    "cash SPY QQQ replacement-value attribution",
    "no strategy behavior change",
]

HORIZONS = [1, 3, 5, 10]
PRIMARY_HORIZON = 10
COMPARATORS = ["cash", "spy", "qqq"]
REPLACEMENT_KEYS = {
    horizon: {
        "cash": f"replacement_value_{horizon}d_vs_cash_usd",
        "spy": f"replacement_value_{horizon}d_vs_spy_usd",
        "qqq": f"replacement_value_{horizon}d_vs_qqq_usd",
    }
    for horizon in HORIZONS
}

BEARISH_RULE = {
    "require_quality_pass": True,
    "pit_safe_contract_rate_eq": 1.0,
    "put_call_volume_ratio_gte": 0.90,
    "put_minus_call_volume_weighted_iv_gte": 0.015,
    "liquid_contract_rate_gte": 0.70,
    "avg_liquidity_score_gte": 0.60,
    "zero_bid_or_ask_count_lte": 20,
    "wide_spread_contract_rate_lte_or_missing": 0.50,
    "open_interest_not_used": "open interest is caveated as lagged by the source",
}
ACCEPTANCE_RULE = {
    "primary_horizon": PRIMARY_HORIZON,
    "min_bearish_rows": 60,
    "min_bearish_entry_dates": 10,
    "min_bearish_tickers": 20,
    "bearish_must_underperform_non_bearish_mean_and_median_for": COMPARATORS,
    "min_supporting_horizons_mean_cash_spy_qqq": 2,
    "max_single_negative_pnl_share_guardrail": 0.50,
    "negative_pnl_hhi_guardrail": 0.35,
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
    "data/experiments/exp-20260630-010/exp_20260630_010_options_bearish_put_demand_forward_value.json",
    "experiments/cards/exp-20260630-010.md",
    "experiments/manifests/exp-20260630-010.json",
    "experiments/tickets/exp-20260630-010.json",
    "experiments/logs/exp-20260630-010.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default if default is not None else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8-sig") as handle:
            for line_number, raw in enumerate(handle, start=1):
                text = raw.strip()
                if not text:
                    continue
                try:
                    item = json.loads(text)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{path}:{line_number}: invalid JSONL") from exc
                if isinstance(item, dict):
                    rows.append(item)
    except OSError:
        pass
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def as_float(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def round_or_none(value: Any, digits: int = 4) -> float | None:
    number = as_float(value)
    return None if number is None else round(number, digits)


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def stats(values: list[float]) -> dict[str, Any]:
    clean = [value for value in values if math.isfinite(value)]
    if not clean:
        return {
            "n": 0,
            "sum": 0.0,
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
            "positive_rate": None,
            "negative_rate": None,
        }
    return {
        "n": len(clean),
        "sum": round(sum(clean), 2),
        "mean": round_or_none(mean(clean), 4),
        "median": round_or_none(median(clean), 4),
        "min": round(min(clean), 2),
        "max": round(max(clean), 2),
        "positive_rate": round(sum(1 for value in clean if value > 0) / len(clean), 4),
        "negative_rate": round(sum(1 for value in clean if value < 0) / len(clean), 4),
    }


def load_ticket() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    return ticket if isinstance(ticket, dict) else {}


def load_baseline_metrics() -> dict[str, Any]:
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
        "windows": windows,
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 4) if generated else None,
        "max_drawdown_pct_worst": round(max(drawdowns), 4) if drawdowns else None,
    }


def field_coverage(rows: list[dict[str, Any]], fields: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for field in fields:
        present = sum(1 for row in rows if row.get(field) not in (None, ""))
        result[field] = {
            "present_rows": present,
            "scanned_rows": len(rows),
            "coverage": round(present / len(rows), 6) if rows else None,
        }
    return result


def settled_for_horizon(row: Mapping[str, Any], horizon: int) -> bool:
    return all(
        as_float(row.get(key)) is not None
        for key in REPLACEMENT_KEYS[horizon].values()
    )


def is_bearish_put_pressure(row: Mapping[str, Any]) -> bool:
    pcr = as_float(row.get("put_call_volume_ratio"))
    iv_skew = as_float(row.get("put_minus_call_volume_weighted_iv"))
    liquid_rate = as_float(row.get("liquid_contract_rate"))
    liquidity_score = as_float(row.get("avg_liquidity_score"))
    zero_bid = as_float(row.get("zero_bid_or_ask_count"))
    wide = as_float(row.get("wide_spread_contract_rate"))
    pit_safe = as_float(row.get("pit_safe_contract_rate"))
    return (
        bool(row.get("quality_pass"))
        and pit_safe == BEARISH_RULE["pit_safe_contract_rate_eq"]
        and pcr is not None
        and pcr >= BEARISH_RULE["put_call_volume_ratio_gte"]
        and iv_skew is not None
        and iv_skew >= BEARISH_RULE["put_minus_call_volume_weighted_iv_gte"]
        and liquid_rate is not None
        and liquid_rate >= BEARISH_RULE["liquid_contract_rate_gte"]
        and liquidity_score is not None
        and liquidity_score >= BEARISH_RULE["avg_liquidity_score_gte"]
        and zero_bid is not None
        and zero_bid <= BEARISH_RULE["zero_bid_or_ask_count_lte"]
        and (wide is None or wide <= BEARISH_RULE["wide_spread_contract_rate_lte_or_missing"])
    )


def is_quality_control(row: Mapping[str, Any]) -> bool:
    return (
        bool(row.get("quality_pass"))
        and as_float(row.get("pit_safe_contract_rate")) == 1.0
    )


def replacement_values(rows: list[dict[str, Any]], horizon: int, comp: str) -> list[float]:
    key = REPLACEMENT_KEYS[horizon][comp]
    values = []
    for row in rows:
        parsed = as_float(row.get(key))
        if parsed is not None:
            values.append(parsed)
    return values


def loss_concentration(rows: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    key = REPLACEMENT_KEYS[horizon]["cash"]
    loss_by_ticker: dict[str, float] = defaultdict(float)
    for row in rows:
        value = as_float(row.get(key))
        if value is not None and value < 0:
            loss_by_ticker[str(row.get("ticker") or "UNKNOWN")] += abs(value)
    total = sum(loss_by_ticker.values())
    if total <= 0:
        return {
            "negative_pnl_total_abs": 0.0,
            "negative_ticker_count": 0,
            "negative_pnl_hhi": None,
            "max_single_negative_pnl_share": None,
            "top_negative_tickers": [],
            "passed": False,
        }
    shares = {ticker: value / total for ticker, value in loss_by_ticker.items()}
    hhi = sum(share * share for share in shares.values())
    max_share = max(shares.values())
    return {
        "negative_pnl_total_abs": round(total, 2),
        "negative_ticker_count": len(loss_by_ticker),
        "negative_pnl_hhi": round(hhi, 6),
        "negative_pnl_hhi_guardrail": ACCEPTANCE_RULE["negative_pnl_hhi_guardrail"],
        "max_single_negative_pnl_share": round(max_share, 6),
        "max_single_negative_pnl_share_guardrail": ACCEPTANCE_RULE[
            "max_single_negative_pnl_share_guardrail"
        ],
        "top_negative_tickers": [
            {"ticker": ticker, "abs_loss": round(value, 2), "share": round(shares[ticker], 4)}
            for ticker, value in sorted(loss_by_ticker.items(), key=lambda item: item[1], reverse=True)[:10]
        ],
        "passed": (
            hhi <= ACCEPTANCE_RULE["negative_pnl_hhi_guardrail"]
            and max_share <= ACCEPTANCE_RULE["max_single_negative_pnl_share_guardrail"]
        ),
    }


def summarize_group(rows: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    tickers = Counter(str(row.get("ticker") or "UNKNOWN") for row in rows)
    entry_dates = sorted({str(row.get("entry_date") or "") for row in rows if row.get("entry_date")})
    return {
        "n": len(rows),
        "ticker_count": len(tickers),
        "entry_date_count": len(entry_dates),
        "entry_date_start": entry_dates[0] if entry_dates else None,
        "entry_date_end": entry_dates[-1] if entry_dates else None,
        "source_experiment_counts": dict(
            sorted(Counter(str(row.get("source_experiment_id") or "unknown") for row in rows).items())
        ),
        "top_tickers": [
            {"ticker": ticker, "rows": count}
            for ticker, count in tickers.most_common(10)
        ],
        "replacement_metrics": {
            comp: stats(replacement_values(rows, horizon, comp))
            for comp in COMPARATORS
        },
    }


def summarize_horizon(rows: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    settled_quality = [
        row for row in rows if row.get("quality_control") and settled_for_horizon(row, horizon)
    ]
    bearish = [row for row in settled_quality if row.get("bearish_put_pressure")]
    non_bearish = [row for row in settled_quality if not row.get("bearish_put_pressure")]
    support: dict[str, Any] = {}
    for comp in COMPARATORS:
        b_stats = stats(replacement_values(bearish, horizon, comp))
        n_stats = stats(replacement_values(non_bearish, horizon, comp))
        b_mean = as_float(b_stats["mean"])
        n_mean = as_float(n_stats["mean"])
        b_median = as_float(b_stats["median"])
        n_median = as_float(n_stats["median"])
        support[comp] = {
            "bearish_mean_lt_non_bearish": (
                b_mean is not None and n_mean is not None and b_mean < n_mean
            ),
            "bearish_median_lt_non_bearish": (
                b_median is not None and n_median is not None and b_median < n_median
            ),
            "mean_delta_bearish_minus_non": round(b_mean - n_mean, 4)
            if b_mean is not None and n_mean is not None
            else None,
            "median_delta_bearish_minus_non": round(b_median - n_median, 4)
            if b_median is not None and n_median is not None
            else None,
        }
    return {
        "horizon": horizon,
        "settled_quality_rows": len(settled_quality),
        "bearish_rows": len(bearish),
        "non_bearish_rows": len(non_bearish),
        "bearish": summarize_group(bearish, horizon),
        "non_bearish": summarize_group(non_bearish, horizon),
        "all_quality": summarize_group(settled_quality, horizon),
        "support": support,
        "bearish_loss_concentration": loss_concentration(bearish, horizon),
    }


def summarize_source(rows: list[dict[str, Any]]) -> dict[str, Any]:
    dates = sorted({str(row.get("entry_date") or "") for row in rows if row.get("entry_date")})
    quote_dates = sorted({str(row.get("quote_date") or "") for row in rows if row.get("quote_date")})
    return {
        "outcome_ledger": repo_rel(OUTCOME_LEDGER),
        "rows": len(rows),
        "outcome_status_counts": dict(
            sorted(Counter(str(row.get("outcome_status") or "unknown") for row in rows).items())
        ),
        "source_experiment_counts": dict(
            sorted(Counter(str(row.get("source_experiment_id") or "unknown") for row in rows).items())
        ),
        "ticker_count": len({str(row.get("ticker") or "") for row in rows if row.get("ticker")}),
        "entry_date_count": len(dates),
        "entry_date_start": dates[0] if dates else None,
        "entry_date_end": dates[-1] if dates else None,
        "quote_date_count": len(quote_dates),
        "quote_date_start": quote_dates[0] if quote_dates else None,
        "quote_date_end": quote_dates[-1] if quote_dates else None,
    }


def evaluate_gate4(horizon_summary: dict[int, dict[str, Any]]) -> dict[str, Any]:
    primary = horizon_summary[PRIMARY_HORIZON]
    bearish = primary["bearish"]
    failed: list[str] = []
    if bearish["n"] < ACCEPTANCE_RULE["min_bearish_rows"]:
        failed.append("bearish_sample_too_small")
    if bearish["entry_date_count"] < ACCEPTANCE_RULE["min_bearish_entry_dates"]:
        failed.append("entry_date_coverage_too_thin")
    if bearish["ticker_count"] < ACCEPTANCE_RULE["min_bearish_tickers"]:
        failed.append("ticker_coverage_too_thin")
    for comp in COMPARATORS:
        support = primary["support"][comp]
        if not support["bearish_mean_lt_non_bearish"]:
            failed.append(f"primary_{comp}_mean_not_weaker")
        if not support["bearish_median_lt_non_bearish"]:
            failed.append(f"primary_{comp}_median_not_weaker")
    if not primary["bearish_loss_concentration"]["passed"]:
        failed.append("bearish_loss_concentration_failed")

    supporting_horizons = 0
    for horizon in (3, 5, 10):
        support = horizon_summary[horizon]["support"]
        if all(support[comp]["bearish_mean_lt_non_bearish"] for comp in COMPARATORS):
            supporting_horizons += 1
    if supporting_horizons < ACCEPTANCE_RULE["min_supporting_horizons_mean_cash_spy_qqq"]:
        failed.append("too_few_supporting_horizons")

    observed_only_lead = not failed
    decision = (
        "observed_only_positive_options_bearish_put_demand_risk_lead_not_promoted"
        if observed_only_lead
        else "rejected_no_options_bearish_put_demand_forward_edge"
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


def calibration(prediction: Mapping[str, Any], success: bool, failed: list[str]) -> dict[str, Any]:
    probability = as_float(prediction.get("success_probability")) or 0.0
    actual = 1.0 if success else 0.0
    predicted_modes = list(prediction.get("main_failure_modes") or [])
    realized: list[str] = []
    if any("mean_not_weaker" in item or "median_not_weaker" in item for item in failed):
        realized.append("no_monotonic_edge")
    if "bearish_loss_concentration_failed" in failed:
        realized.append("single_ticker_concentration")
    if any("qqq" in item for item in failed):
        realized.append("market_beta_not_options_pressure")
    if "bearish_sample_too_small" in failed or "ticker_coverage_too_thin" in failed:
        realized.append("quality_flags_dominate")
    realized = list(dict.fromkeys(realized))
    return {
        "actual_decision": "observed_only_positive_lead" if success else "observed_only_rejected",
        "actual_success": int(success),
        "predicted_success_probability": round(probability, 4),
        "brier_score": round((probability - actual) ** 2, 6),
        "predicted_failure_modes": predicted_modes,
        "realized_failure_modes": realized,
        "predicted_failure_mode_hit": any(mode in realized for mode in predicted_modes),
        "surprise_note": (
            "The fixed bearish options bucket separated weaker forward value, "
            "but it remains a forward-only lead and is not promotable."
            if success
            else "The fixed bearish options bucket did not show stable weaker "
            "cash/SPY/QQQ replacement value versus non-bearish quality rows."
        ),
    }


def build_payload() -> dict[str, Any]:
    ticket = load_ticket()
    prediction = ticket.get("prediction") or {}
    before = load_baseline_metrics()
    raw_rows = read_jsonl(OUTCOME_LEDGER)
    rows: list[dict[str, Any]] = []
    for row in raw_rows:
        item = dict(row)
        item["quality_control"] = is_quality_control(item)
        item["bearish_put_pressure"] = is_bearish_put_pressure(item)
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
        "The fixed bearish put-demand bucket separated weak forward replacement "
        "value in the refreshed options outcome ledger. It remains observed-only "
        "because this is current forward evidence, not historical PIT options "
        "coverage across the canonical windows."
        if gate4["observed_only_lead"]
        else "The fixed bearish put-demand bucket did not consistently "
        "underperform non-bearish quality rows across 10d cash/SPY/QQQ mean and "
        "median checks, so options pressure remains attribution context."
    )
    source_summary = summarize_source(rows)
    now = utc_now()
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": gate4["observed_only_lead"],
        "lane": "alpha_search",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "observed_only_forward_attribution",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "calibration": calibration(prediction, gate4["observed_only_lead"], gate4["failed_reasons"]),
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "exp-20260625-001": (
                    "Rejected options demand-quality attribution on the older "
                    "exp-20260624-026 ledger; valid retry required materially "
                    "more closed rows, PIT vendor/asof controls, borrow context, "
                    "or historical PIT options-chain coverage."
                ),
                "exp-20260630-008": (
                    "Accepted measurement repair that refreshed all current "
                    "options observation ledgers and created 1544 closed 10d rows."
                ),
                "novelty_gate": (
                    "Reservation passed with no strong near-neighbor; the ticket "
                    "records exp-20260630-008 materially more closed rows as the "
                    "new evidence axis."
                ),
            },
            "3_single_policy_bundle": (
                "One fixed observed-only risk context: liquid quality rows with "
                "put_call_volume_ratio >= 0.90 and put_minus_call_volume_weighted_iv "
                ">= 0.015 are compared with all remaining quality rows."
            ),
            "4_success_failure_standard": ACCEPTANCE_RULE,
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "outcome_ledger": repo_rel(OUTCOME_LEDGER),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "bearish_rule": BEARISH_RULE,
            "acceptance_rule": ACCEPTANCE_RULE,
            "horizons": HORIZONS,
            "primary_horizon": PRIMARY_HORIZON,
            "comparators": COMPARATORS,
        },
        "source_summary": source_summary,
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
            "source_rows": source_summary["rows"],
            "quality_control_10d_rows": primary["settled_quality_rows"],
            "bearish_10d_rows": primary["bearish_rows"],
        },
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_metrics": before,
            "note": "Observed-only attribution; before and after policy metrics are identical.",
        },
        "gate2": {
            "dependencies_validated": OUTCOME_LEDGER.exists() and bool(rows),
            "fields_checked": fields_checked,
            "field_coverage": field_coverage(rows, fields_checked),
            "entry_date_rows": sum(1 for row in rows if row.get("entry_date")),
            "target_price_scope": (
                "Not applicable: options forward attribution uses fixed horizons "
                "and does not schedule target exits or orders."
            ),
            "source_summary": source_summary,
        },
        "gate3": {
            "filter_added": False,
            "signals_generated": primary["settled_quality_rows"],
            "signals_survived": primary["bearish_rows"],
            "survival_rate": round(primary["bearish_rows"] / primary["settled_quality_rows"], 4)
            if primary["settled_quality_rows"]
            else None,
            "baseline_survival_rate": before.get("survival_rate"),
            "passed": (
                primary["settled_quality_rows"] > 0
                and primary["bearish_rows"] / primary["settled_quality_rows"] >= 0.05
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
                "or threshold variants on this same exp-20260630-008 forward ledger."
            ),
            "new_evidence_required": (
                "A valid retry needs materially more closed forward rows beyond "
                "exp-20260630-008, PIT vendor/as-of controls, borrow/loan "
                "availability context, or historical PIT options-chain coverage "
                "across the canonical windows."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(OUTCOME_LEDGER),
            repo_rel(BASELINE_RESULT),
            "experiments/logs/exp-20260625-001.json",
            "experiments/logs/exp-20260630-008.json",
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
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
    return payload


def compact_log(payload: Mapping[str, Any]) -> dict[str, Any]:
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
        "new_evidence_axis",
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
    number = as_float(value)
    return "n/a" if number is None else f"${number:,.2f}"


def build_card(payload: Mapping[str, Any]) -> str:
    primary = payload["primary_summary"]
    bearish = primary["bearish"]["replacement_metrics"]
    non_bearish = primary["non_bearish"]["replacement_metrics"]
    support = primary["support"]
    rows = [
        "| Cohort | Rows | Tickers | Dates | Mean cash | Mean SPY | Mean QQQ | Median cash |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
        "| bearish_put_pressure | {n} | {tickers} | {dates} | {cash} | {spy} | {qqq} | {median} |".format(
            n=primary["bearish"]["n"],
            tickers=primary["bearish"]["ticker_count"],
            dates=primary["bearish"]["entry_date_count"],
            cash=money(bearish["cash"]["mean"]),
            spy=money(bearish["spy"]["mean"]),
            qqq=money(bearish["qqq"]["mean"]),
            median=money(bearish["cash"]["median"]),
        ),
        "| non_bearish_quality | {n} | {tickers} | {dates} | {cash} | {spy} | {qqq} | {median} |".format(
            n=primary["non_bearish"]["n"],
            tickers=primary["non_bearish"]["ticker_count"],
            dates=primary["non_bearish"]["entry_date_count"],
            cash=money(non_bearish["cash"]["mean"]),
            spy=money(non_bearish["spy"]["mean"]),
            qqq=money(non_bearish["qqq"]["mean"]),
            median=money(non_bearish["cash"]["median"]),
        ),
    ]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: options bearish put-demand forward value",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Strategy behavior changed: `false`",
            "- Accepted alpha: `false`",
            f"- Failed checks: `{', '.join(payload['gate4']['failed_reasons']) or 'none'}`",
            f"- Artifact: `{repo_rel(OUT_JSON)}`",
            "",
            "## Primary 10d Groups",
            "",
            *rows,
            "",
            "## 10d Deltas",
            "",
            f"- Cash mean delta bearish minus non: `{money(support['cash']['mean_delta_bearish_minus_non'])}`",
            f"- SPY mean delta bearish minus non: `{money(support['spy']['mean_delta_bearish_minus_non'])}`",
            f"- QQQ mean delta bearish minus non: `{money(support['qqq']['mean_delta_bearish_minus_non'])}`",
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


def build_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
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
        "manifest": repo_rel(MANIFEST_JSON),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256_file(path)}
            for path in files
        },
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log(payload)
    save_experiment_log_entry(log_record, allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    registry_result = {
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": payload["observed_only_lead"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    ticket_before = payload.get("ticket_before") or {}
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result=registry_result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "change_type": CHANGE_TYPE,
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
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
        },
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
                "quality_10d_rows": primary["settled_quality_rows"],
                "bearish_10d_rows": primary["bearish_rows"],
                "non_bearish_10d_rows": primary["non_bearish_rows"],
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
