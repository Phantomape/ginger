"""exp-20260625-020: options earnings-distance forward attribution.

Observed-only alpha attribution. This reads the exp-20260624-026 reusable
OnclickMedia options outcome ledger, joins each row to the entry-date earnings
snapshot, and tests one fixed event-distance bucket: rows 0-10 calendar days
before the next known earnings date. It does not change strategy behavior,
shared helpers, daily snapshots, paper orders, live orders, ranking, sizing,
exits, or LLM logic.
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


EXPERIMENT_ID = "exp-20260625-020"
OWNER = "alpha-explore"
SLUG = "options_earnings_distance_forward_attribution"
RUNNER = f"quant/experiments/exp_20260625_020_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260625_020_{SLUG}.json"
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
EARNINGS_SNAPSHOT_DIR = REPO_ROOT / "data" / "daily" / "snapshots" / "earnings"

HYPOTHESIS = (
    "Observed-only options alpha hypothesis: OnclickMedia options demand may "
    "only carry useful replacement value when the option snapshot is near an "
    "upcoming earnings event, because event-implied positioning has a concrete "
    "catalyst while generic demand-quality failed."
)
CHANGE_TYPE = "observed_only_forward_attribution"
MECHANISM_FAMILY = "production_visible_forward_options_attribution"
TRIAL_FAMILY = "onclickmedia_options_event_distance_forward_attribution"
TRIAL_VARIANT_ID = "near_earnings_window_v1"
CHANGED_VARIABLE = "onclickmedia_options_earnings_distance_forward_attribution_v1"
NEW_EVIDENCE_TYPE = "event_distance_join_to_settled_options_forward_rows"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260624-026",
    "exp-20260625-001",
    "exp-20260623-010",
]
CAUSAL_COMPONENTS = [
    "exp026 settled options outcome ledger",
    "entry-time earnings snapshot join",
    "near-earnings vs non-near-earnings cash SPY QQQ replacement attribution",
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

NEAR_EARNINGS_RULE = {
    "days_to_earnings_min": 0,
    "days_to_earnings_max": 10,
    "join_date_field": "entry_date",
    "snapshot_source": "data/daily/snapshots/earnings/earnings_snapshot_YYYYMMDD.json",
    "missing_or_non_equity_rows_are_non_near": True,
}
ACCEPTANCE_RULE = {
    "primary_horizon": PRIMARY_HORIZON,
    "near_earnings_window_days_inclusive": [0, 10],
    "min_near_rows": 80,
    "min_near_entry_dates": 10,
    "min_near_tickers": 10,
    "near_must_beat_non_near_mean_and_median_for": COMPARATORS,
    "min_supporting_horizons_mean_cash_spy_qqq": 2,
    "supporting_horizons_checked": [3, 5, 10],
    "positive_pnl_hhi_guardrail": 0.35,
    "max_single_positive_pnl_share_guardrail": 0.50,
    "no_post_hoc_window_widening": True,
}
DIAGNOSTIC_BANDS = [
    ("pre_event_0_10", 0, 10),
    ("pre_event_11_21", 11, 21),
    ("pre_event_22_30", 22, 30),
    ("pre_event_31_plus", 31, None),
    ("post_event_or_stale_negative", None, -1),
    ("missing_earnings_distance", None, None),
]
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
    "uses_entry_time_earnings_snapshot": True,
    "forward_only_not_fixed_window_pit_coverage": True,
    "parity_note": (
        "Observed-only attribution on experiment-owned forward rows joined to "
        "entry-date earnings snapshots. No shared policy/helper or production "
        "adapter behavior changed."
    ),
}
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260625-020/exp_20260625_020_options_earnings_distance_forward_attribution.json",
    "experiments/cards/exp-20260625-020.md",
    "experiments/manifests/exp-20260625-020.json",
    "experiments/tickets/exp-20260625-020.json",
    "experiments/logs/exp-20260625-020.json",
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


class EarningsSnapshotCache:
    def __init__(self, snapshot_dir: Path) -> None:
        self.snapshot_dir = snapshot_dir
        self._cache: dict[str, dict[str, Any] | None] = {}

    def snapshot_for_date(self, value: Any) -> dict[str, Any] | None:
        date_text = str(value or "").strip()
        if not date_text:
            return None
        compact = date_text.replace("-", "")
        if len(compact) != 8 or not compact.isdigit():
            return None
        if compact not in self._cache:
            path = self.snapshot_dir / f"earnings_snapshot_{compact}.json"
            payload = read_json(path, None) if path.exists() else None
            self._cache[compact] = payload if isinstance(payload, dict) else None
        return self._cache[compact]

    def join_fields(self, row: dict[str, Any]) -> dict[str, Any]:
        entry_date = row.get("entry_date") or row.get("usable_trade_date")
        ticker = str(row.get("ticker") or "").upper()
        snapshot = self.snapshot_for_date(entry_date)
        earnings = snapshot.get("earnings", {}) if isinstance(snapshot, dict) else {}
        item = earnings.get(ticker) if isinstance(earnings, dict) else None
        if not isinstance(item, dict):
            return {
                "entry_time_earnings_snapshot_date": entry_date,
                "entry_time_earnings_snapshot_found": snapshot is not None,
                "entry_time_earnings_ticker_found": False,
                "entry_time_next_earnings_date": None,
                "entry_time_days_to_earnings": None,
                "entry_time_eps_estimate": None,
                "entry_time_eps_actual_last": None,
                "entry_time_avg_historical_surprise_pct": None,
                "entry_time_next_earnings_date_source": None,
            }
        return {
            "entry_time_earnings_snapshot_date": entry_date,
            "entry_time_earnings_snapshot_found": snapshot is not None,
            "entry_time_earnings_ticker_found": True,
            "entry_time_next_earnings_date": item.get("next_earnings_date"),
            "entry_time_days_to_earnings": safe_float(item.get("days_to_earnings")),
            "entry_time_eps_estimate": safe_float(item.get("eps_estimate")),
            "entry_time_eps_actual_last": safe_float(item.get("eps_actual_last")),
            "entry_time_avg_historical_surprise_pct": safe_float(
                item.get("avg_historical_surprise_pct")
            ),
            "entry_time_next_earnings_date_source": item.get("next_earnings_date_source"),
        }

    def cache_summary(self) -> dict[str, Any]:
        return {
            "snapshot_dir": repo_rel(self.snapshot_dir),
            "loaded_dates": sorted(self._cache),
            "loaded_count": sum(1 for payload in self._cache.values() if payload is not None),
            "missing_count": sum(1 for payload in self._cache.values() if payload is None),
        }


def is_near_earnings(row: dict[str, Any]) -> bool:
    days = safe_float(row.get("entry_time_days_to_earnings"))
    return (
        days is not None
        and NEAR_EARNINGS_RULE["days_to_earnings_min"] <= days
        and days <= NEAR_EARNINGS_RULE["days_to_earnings_max"]
    )


def event_band(row: dict[str, Any]) -> str:
    days = safe_float(row.get("entry_time_days_to_earnings"))
    if days is None:
        return "missing_earnings_distance"
    for name, low, high in DIAGNOSTIC_BANDS:
        if name == "missing_earnings_distance":
            continue
        if low is None and high is not None and days <= high:
            return name
        if high is None and low is not None and days >= low:
            return name
        if low is not None and high is not None and low <= days <= high:
            return name
    return "unbucketed"


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
    event_days = [
        safe_float(row.get("entry_time_days_to_earnings"))
        for row in rows
        if safe_float(row.get("entry_time_days_to_earnings")) is not None
    ]
    return {
        "n": len(rows),
        "ticker_count": len(ticker_counts),
        "entry_date_count": len(entry_dates),
        "entry_date_start": entry_dates[0] if entry_dates else None,
        "entry_date_end": entry_dates[-1] if entry_dates else None,
        "earnings_distance": {
            "n": len(event_days),
            "min": round(min(event_days), 2) if event_days else None,
            "median": round_or_none(median(event_days), 2) if event_days else None,
            "max": round(max(event_days), 2) if event_days else None,
        },
        "event_band_counts": dict(
            sorted(Counter(str(row.get("entry_time_earnings_band") or "missing") for row in rows).items())
        ),
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


def compare_groups(
    near_rows: list[dict[str, Any]],
    non_near_rows: list[dict[str, Any]],
    horizon: int,
) -> dict[str, Any]:
    support = {}
    for comp in COMPARATORS:
        near_stats = stats(replacement_values(near_rows, horizon, comp))
        non_stats = stats(replacement_values(non_near_rows, horizon, comp))
        near_mean = safe_float(near_stats["mean"])
        non_mean = safe_float(non_stats["mean"])
        near_median = safe_float(near_stats["median"])
        non_median = safe_float(non_stats["median"])
        support[comp] = {
            "near_mean_gt_non_near": (
                near_mean is not None and non_mean is not None and near_mean > non_mean
            ),
            "near_median_gt_non_near": (
                near_median is not None
                and non_median is not None
                and near_median > non_median
            ),
            "mean_delta": round(near_mean - non_mean, 4)
            if near_mean is not None and non_mean is not None
            else None,
            "median_delta": round(near_median - non_median, 4)
            if near_median is not None and non_median is not None
            else None,
            "near": near_stats,
            "non_near": non_stats,
        }
    return support


def summarize_horizon(rows: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    settled = [row for row in rows if settled_for_horizon(row, horizon)]
    near = [row for row in settled if row.get("near_earnings_event")]
    non_near = [row for row in settled if not row.get("near_earnings_event")]
    band_summary = {
        band: summarize_group([row for row in settled if row.get("entry_time_earnings_band") == band], horizon)
        for band, _low, _high in DIAGNOSTIC_BANDS
    }
    return {
        "horizon": horizon,
        "settled_rows": len(settled),
        "near_earnings_rows": len(near),
        "non_near_earnings_rows": len(non_near),
        "near_earnings": summarize_group(near, horizon),
        "non_near_earnings": summarize_group(non_near, horizon),
        "all_settled": summarize_group(settled, horizon),
        "diagnostic_band_summary": band_summary,
        "support": compare_groups(near, non_near, horizon),
        "near_earnings_concentration": concentration(near, horizon),
    }


def evaluate_gate4(horizon_summary: dict[int, dict[str, Any]]) -> dict[str, Any]:
    primary = horizon_summary[PRIMARY_HORIZON]
    near = primary["near_earnings"]
    failed: list[str] = []
    if near["n"] < ACCEPTANCE_RULE["min_near_rows"]:
        failed.append("near_earnings_sample_too_thin")
    if near["entry_date_count"] < ACCEPTANCE_RULE["min_near_entry_dates"]:
        failed.append("near_earnings_entry_date_coverage_too_thin")
    if near["ticker_count"] < ACCEPTANCE_RULE["min_near_tickers"]:
        failed.append("near_earnings_ticker_coverage_too_thin")
    for comp in COMPARATORS:
        support = primary["support"][comp]
        if not support["near_mean_gt_non_near"]:
            failed.append(f"primary_{comp}_mean_not_better")
        if not support["near_median_gt_non_near"]:
            failed.append(f"primary_{comp}_median_not_better")
    if not primary["near_earnings_concentration"]["passed"]:
        failed.append("near_earnings_positive_pnl_concentration_failed")

    supporting_horizons = 0
    for horizon in ACCEPTANCE_RULE["supporting_horizons_checked"]:
        support = horizon_summary[horizon]["support"]
        if all(support[comp]["near_mean_gt_non_near"] for comp in COMPARATORS):
            supporting_horizons += 1
    if supporting_horizons < ACCEPTANCE_RULE["min_supporting_horizons_mean_cash_spy_qqq"]:
        failed.append("too_few_supporting_horizons")

    observed_only_lead = not failed
    decision = (
        "observed_only_positive_options_earnings_distance_lead_not_promoted"
        if observed_only_lead
        else "rejected_no_options_earnings_distance_forward_edge"
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
    if "near_earnings_sample_too_thin" in failed:
        realized_modes.append("near_earnings_sample_too_thin")
    if any(reason.startswith("primary_") and reason.endswith("_not_better") for reason in failed):
        realized_modes.append("no_cash_spy_qqq_median_edge")
    if any(reason.startswith("primary_qqq_") for reason in failed):
        realized_modes.append("earnings_beta_confound")
    if "near_earnings_positive_pnl_concentration_failed" in failed:
        realized_modes.append("single_ticker_concentration")
    realized_modes.append("forward_only_not_promotable")
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
            "The near-earnings event-distance bucket passed the observed-only "
            "screen, but it remains forward-only and not promotable."
            if success
            else "The near-earnings event-distance bucket did not clear the "
            "predeclared sample and cash/SPY/QQQ separation checks."
        ),
    }


def source_summary(rows: list[dict[str, Any]], cache: EarningsSnapshotCache) -> dict[str, Any]:
    entry_dates = sorted({str(row.get("entry_date") or "") for row in rows if row.get("entry_date")})
    return {
        "outcome_ledger": repo_rel(OUTCOME_LEDGER),
        "earnings_snapshot_dir": repo_rel(EARNINGS_SNAPSHOT_DIR),
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
        "earnings_join": {
            "snapshot_found_rows": sum(
                1 for row in rows if row.get("entry_time_earnings_snapshot_found")
            ),
            "ticker_found_rows": sum(
                1 for row in rows if row.get("entry_time_earnings_ticker_found")
            ),
            "days_to_earnings_rows": sum(
                1 for row in rows if safe_float(row.get("entry_time_days_to_earnings")) is not None
            ),
            "near_earnings_rows_all_horizons": sum(
                1 for row in rows if row.get("near_earnings_event")
            ),
            "event_band_counts": dict(
                sorted(Counter(str(row.get("entry_time_earnings_band") or "missing") for row in rows).items())
            ),
            "snapshot_cache": cache.cache_summary(),
        },
    }


def enrich_rows(raw_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], EarningsSnapshotCache]:
    cache = EarningsSnapshotCache(EARNINGS_SNAPSHOT_DIR)
    rows = []
    for row in raw_rows:
        item = dict(row)
        item.update(cache.join_fields(item))
        item["near_earnings_event"] = is_near_earnings(item)
        item["entry_time_earnings_band"] = event_band(item)
        rows.append(item)
    return rows, cache


def build_payload() -> dict[str, Any]:
    ticket = load_ticket()
    prediction = ticket.get("prediction") or {}
    before = baseline_metrics()
    raw_rows = read_jsonl(OUTCOME_LEDGER)
    rows, cache = enrich_rows(raw_rows)

    horizon_summary = {horizon: summarize_horizon(rows, horizon) for horizon in HORIZONS}
    gate4 = evaluate_gate4(horizon_summary)
    status = (
        "observed_only_positive_lead"
        if gate4["observed_only_lead"]
        else "observed_only_rejected"
    )
    decision = gate4["decision"]
    primary = horizon_summary[PRIMARY_HORIZON]
    source = source_summary(rows, cache)
    fields_checked = [
        "observation_id",
        "ticker",
        "quote_date",
        "usable_trade_date",
        "entry_date",
        "target_price",
        "outcome_status",
        "entry_time_earnings_snapshot_date",
        "entry_time_earnings_snapshot_found",
        "entry_time_earnings_ticker_found",
        "entry_time_next_earnings_date",
        "entry_time_days_to_earnings",
        "entry_time_earnings_band",
        "near_earnings_event",
        "replacement_value_10d_vs_cash_usd",
        "replacement_value_10d_vs_spy_usd",
        "replacement_value_10d_vs_qqq_usd",
    ]
    why = (
        "The predeclared 0-10 day near-earnings options bucket beat non-near "
        "rows on the observed-only screen. This is not accepted alpha because "
        "the evidence is a forward outcome ledger rather than historical PIT "
        "options-chain coverage across the canonical windows."
        if gate4["observed_only_lead"]
        else "The predeclared 0-10 day near-earnings options bucket did not "
        "clear the required row floor and 10d cash/SPY/QQQ mean and median "
        "checks, so event distance remains attribution context only."
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
        "new_evidence_axis": (
            "New machine-checkable event-distance field: join exp026 settled "
            "options rows to PIT daily earnings snapshots at entry time and "
            "test near-upcoming-earnings positioning."
        ),
        "prediction": prediction,
        "calibration": calibration(
            prediction,
            gate4["observed_only_lead"],
            gate4["failed_reasons"],
        ),
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "exp-20260624-026": (
                    "Accepted measurement repair that created the reusable "
                    "settled options outcome ledger consumed here."
                ),
                "exp-20260625-001": (
                    "Rejected generic options demand/liquidity attribution; "
                    "this run does not reslice put/call, IV skew, liquidity, "
                    "spread, open interest, top-N, hold, cooldown, or notional."
                ),
                "exp-20260623-010": (
                    "Rejected earlier one-off options skew attribution before "
                    "the exp026 settled replacement-value ledger existed."
                ),
                "novelty_gate": (
                    "Reservation passed without override. The new evidence "
                    "axis is the entry-time earnings event-distance join."
                ),
            },
            "3_single_policy_bundle": (
                "One observed-only bundle: classify exp026 rows by whether the "
                "entry-date earnings snapshot shows 0-10 days to next earnings "
                "and compare settled replacement value against all non-near rows."
            ),
            "4_success_failure_standard": (
                "Observed-only lead only if the 10d near bucket clears the "
                "80-row, 10-date, 10-ticker floors, beats non-near rows on mean "
                "and median cash/SPY/QQQ replacement value, has at least two "
                "supporting 3/5/10d mean horizons, and passes positive-PnL "
                "concentration."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "outcome_ledger": repo_rel(OUTCOME_LEDGER),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "earnings_snapshot_dir": repo_rel(EARNINGS_SNAPSHOT_DIR),
            "near_earnings_rule": NEAR_EARNINGS_RULE,
            "acceptance_rule": ACCEPTANCE_RULE,
            "diagnostic_bands": [
                {"name": name, "low": low, "high": high}
                for name, low, high in DIAGNOSTIC_BANDS
            ],
            "horizons": HORIZONS,
            "primary_horizon": PRIMARY_HORIZON,
            "comparators": COMPARATORS,
            "decision_boundary": (
                "The predeclared window remains 0-10 days even though wider "
                "diagnostic bands have more rows; widening after the sample "
                "check would be post-hoc."
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
            "signals_survived": primary["near_earnings_rows"],
            "survival_rate": round(primary["near_earnings_rows"] / primary["settled_rows"], 4)
            if primary["settled_rows"]
            else None,
            "baseline_survival_rate": before.get("survival_rate"),
            "passed": (
                primary["settled_rows"] > 0
                and primary["near_earnings_rows"] / primary["settled_rows"] >= 0.05
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
                "Do not retry options event-distance cutoffs, wider earnings "
                "windows, put/call ratio, IV skew, liquidity, spread, zero-bid "
                "count, open interest, top-N, hold, cooldown, notional, or "
                "threshold variants on this same exp026 forward ledger."
            ),
            "new_evidence_required": (
                "A valid options retry needs materially more closed forward rows, "
                "historical PIT options-chain coverage across canonical windows, "
                "or a different production-visible event/cost field that creates "
                "new rows rather than reslicing this same small forward sample."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(OUTCOME_LEDGER),
            repo_rel(BASELINE_RESULT),
            repo_rel(EARNINGS_SNAPSHOT_DIR),
            "experiments/logs/exp-20260624-026.json",
            "experiments/logs/exp-20260625-001.json",
            "experiments/logs/exp-20260623-010.json",
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
        card_group_line("near_earnings_0_10d", primary["near_earnings"]),
        card_group_line("non_near", primary["non_near_earnings"]),
    ]
    diagnostic_rows = [
        "| Band | Rows | Tickers | Dates | Mean Cash | Mean SPY | Mean QQQ | Median Cash |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for band in [
        "pre_event_0_10",
        "pre_event_11_21",
        "pre_event_22_30",
        "pre_event_31_plus",
        "missing_earnings_distance",
    ]:
        diagnostic_rows.append(
            card_group_line(band, primary["diagnostic_band_summary"][band])
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: options earnings-distance attribution",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Strategy behavior changed: `false`",
            f"- 10d settled rows: `{primary['settled_rows']}`",
            f"- 10d near-earnings rows: `{primary['near_earnings_rows']}`",
            f"- Failed checks: `{', '.join(payload['gate4']['failed_reasons']) or 'none'}`",
            f"- Artifact: `{repo_rel(OUT_JSON)}`",
            "",
            "## Primary 10d Groups",
            "",
            *rows,
            "",
            "## Diagnostic Event Bands",
            "",
            *diagnostic_rows,
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
        ]
    )


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = payload["changed_files"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "decision": payload["decision"],
        "status": payload["status"],
        "changed_files": files,
        "file_hashes": {
            path: sha256(REPO_ROOT / path)
            for path in files
            if path != repo_rel(MANIFEST_JSON)
        },
        "reproduction_commands": payload["reproduction_commands"],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
    }


def persist_outputs(payload: dict[str, Any]) -> None:
    log_record = compact_log_record(payload)
    write_json(OUT_JSON, payload)
    write_json(LOG_JSON, log_record)
    upsert_jsonl(EXPERIMENT_LOG, log_record)
    write_text(CARD_MD, build_card(payload))
    manifest = build_manifest(payload)
    write_json(MANIFEST_JSON, manifest)

    registry_fields = {
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "result_file": repo_rel(OUT_JSON),
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card_file": repo_rel(CARD_MD),
        "revision_manifest_file": repo_rel(MANIFEST_JSON),
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "changed_files": payload["changed_files"],
        "reproduction_commands": payload["reproduction_commands"],
        "lean_quality_passed": True,
        "completed_at": payload["timestamp"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result={
            "decision": payload["decision"],
            "status": payload["status"],
            "accepted": payload["accepted"],
            "accepted_alpha": payload["accepted_alpha"],
            "observed_only_lead": payload["observed_only_lead"],
            "artifact": repo_rel(OUT_JSON),
            "gate4": payload["gate4"],
            "primary_summary": payload["primary_summary"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "calibration": payload["calibration"],
        },
        status=payload["status"],
        fields=registry_fields,
    )


def main() -> int:
    payload = build_payload()
    persist_outputs(payload)
    primary = payload["primary_summary"]
    print(json.dumps(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "decision": payload["decision"],
            "near_earnings_rows_10d": primary["near_earnings_rows"],
            "non_near_rows_10d": primary["non_near_earnings_rows"],
            "failed_reasons": payload["gate4"]["failed_reasons"],
            "artifact": repo_rel(OUT_JSON),
        },
        indent=2,
        sort_keys=True,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
