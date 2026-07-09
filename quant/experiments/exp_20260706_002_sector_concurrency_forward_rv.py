"""exp-20260706-002: sector-concurrency forward RV attribution.

Observed-only alpha attribution. This tests one fixed risk-allocation gate
shape: closed default-off paper rows are labeled "same-sector crowded" when,
on their entry date, active default-off paper exposure in the same sector has at
least three active positions or at least 50% of active paper notional.

No strategy behavior changes here: no entries, exits, ranking, sizing, paper
orders, live orders, prompts, or watchlists are changed.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (QUANT_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from broad_market_sector_map import load_cache, lookup_sector  # noqa: E402
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


EXPERIMENT_ID = "exp-20260706-002"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "sector_concurrency_forward_rv"
RUNNER = f"quant/experiments/exp_20260706_002_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
PAPER_ROOT = REPO_ROOT / "data" / "paper_sleeves"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260706_002_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Observed-only alpha: settled default-off paper rows whose entry date "
    "already has same-sector concurrent paper exposure should show worse "
    "cash/SPY/QQQ replacement value than uncrowded rows, supporting a future "
    "fixed cross-sleeve sector exposure cap."
)
CHANGED_VARIABLE = "default_off_forward_same_sector_concurrency_rv_v1"
MECHANISM_FAMILY = "default_off_forward_risk_allocation"
TRIAL_FAMILY = "same_sector_forward_concurrency_rv"
TRIAL_VARIANT_ID = "sector_concurrency_closed_rows_v1"
NEARBY_PRIORS = ["exp-20260705-009", "exp-20260706-001", "exp-20260705-015"]
NEW_EVIDENCE_AXIS = (
    "New gate shape on settled forward rows: same-sector concurrent paper "
    "exposure at entry date across default-off paper sleeves, distinct from "
    "same-ticker duplicate exposure and from report-only live pilot "
    "concentration; uses existing closed replacement-value rows without "
    "changing thresholds, notional, ranking, exits, or orders."
)
DEFAULT_PREDICTION = {
    "success_probability": 0.24,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "sample_too_thin",
        "sector_labels_inconsistent",
        "crowding_not_worse",
        "concentration_failed",
    ],
    "confidence_reason": (
        "Recent duplicate same-ticker cap failed historical validation, but "
        "exp-20260706-001 found live pilot sector stacking was invisible to "
        "ticker overlap; closed default-off paper rows now carry entry dates, "
        "sectors, and cash/SPY/QQQ replacement fields, so this observed-only "
        "gate shape is machine-checkable while still low prior."
    ),
}

PRIMARY_METRICS = [
    "replacement_value_vs_cash_usd",
    "replacement_value_vs_spy_usd",
    "replacement_value_vs_qqq_usd",
]
CONCURRENCY_RULE = {
    "min_same_sector_active_positions": 3,
    "min_same_sector_active_notional_share": 0.50,
}
ACCEPTANCE_RULE = {
    "min_evaluable_closed_rows": 25,
    "min_crowded_rows": 8,
    "min_uncrowded_rows": 8,
    "require_crowded_mean_worse_all_primary_metrics": True,
    "require_crowded_median_worse_primary_metrics_min": 2,
    "max_single_ticker_negative_crowded_loss_share": 0.40,
}
CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260706_002_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]
RELATED_FILES = [
    "data/paper_sleeves/*/state.json",
    "data/reference/broad_market_sector_map.json",
    "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json",
    "experiments/logs/exp-20260705-009.json",
    "experiments/logs/exp-20260706-001.json",
    "experiments/logs/exp-20260705-015.json",
]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
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


def numeric_value(row: dict[str, Any], key: str) -> float | None:
    value = row.get(key)
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    return converted if math.isfinite(converted) else None


def parse_date(value: Any) -> dt.date | None:
    text = str(value or "")[:10]
    if not text:
        return None
    try:
        return dt.date.fromisoformat(text)
    except ValueError:
        return None


def date_text(value: dt.date | None) -> str | None:
    return value.isoformat() if value else None


def nested_dict(row: dict[str, Any], key: str) -> dict[str, Any]:
    value = row.get(key)
    return value if isinstance(value, dict) else {}


def nested_value(row: dict[str, Any], key: str) -> Any:
    candidate = nested_dict(row, "candidate")
    return candidate.get(key)


def first_value(row: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key.startswith("candidate."):
            value = nested_value(row, key.split(".", 1)[1])
        else:
            value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def load_ticket_prediction() -> dict[str, Any]:
    prediction = dict(DEFAULT_PREDICTION)
    ticket = read_json(TICKET_JSON, {}) or {}
    ticket_prediction = ticket.get("prediction")
    if isinstance(ticket_prediction, dict):
        prediction.update({k: v for k, v in ticket_prediction.items() if v is not None})
    prediction.setdefault("recorded_at", utc_now())
    return prediction


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_PATH, {}) or {}
    windows = list(payload.get("windows") or [])
    generated = sum(int(window.get("signals_generated") or 0) for window in windows)
    survived = sum(int(window.get("signals_survived") or 0) for window in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_PATH),
        "baseline_exists": BASELINE_PATH.exists(),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(window.get("expected_value_score") or 0.0) for window in windows),
            4,
        ),
        "total_pnl": round(
            sum(float(window.get("total_pnl") or 0.0) for window in windows), 2
        ),
        "trade_count": sum(
            int(window.get("trade_count") or window.get("total_trades") or 0)
            for window in windows
        ),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / max(generated, 1), 6),
    }


def ticker_from_decision_id(decision_id: Any) -> str | None:
    text = str(decision_id or "")
    if not text:
        return None
    parts = [part for part in text.split(":") if part]
    if parts:
        ticker = parts[-1].upper().strip()
        if ticker and len(ticker) <= 8 and ticker.replace(".", "").isalnum():
            return ticker
    return None


def normalized_ticker(row: dict[str, Any]) -> str:
    ticker = first_value(row, ["ticker", "candidate.ticker", "debt_ticker"])
    ticker = str(ticker or ticker_from_decision_id(row.get("decision_id")) or "").upper()
    return ticker.strip() or "UNKNOWN"


def normalized_sleeve(row: dict[str, Any], sleeve_dir: str) -> str:
    sleeve = first_value(row, ["sleeve", "candidate.sleeve", "strategy"])
    return str(sleeve or sleeve_dir).strip() or sleeve_dir


def sector_for_row(
    row: dict[str, Any],
    ticker: str,
    sector_cache: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    raw_sector = first_value(row, ["sector", "candidate.sector"])
    sector = str(raw_sector or "").strip()
    lookup = lookup_sector(ticker, sector_cache)
    if not sector or sector.lower() == "unknown":
        sector = str(lookup.get("sector") or "").strip()
    if not sector:
        sector = "Unknown"
    return sector, lookup


def normalized_notional(row: dict[str, Any]) -> float:
    for key in [
        "notional",
        "intended_notional",
        "paper_notional_usd",
        "safe_paper_notional_usd",
        "candidate.intended_notional",
        "candidate.paper_notional_usd",
        "candidate.safe_paper_notional_usd",
        "candidate.baseline_paper_notional_usd",
        "candidate.base_paper_notional_usd",
    ]:
        if key.startswith("candidate."):
            value = nested_value(row, key.split(".", 1)[1])
            source = {key: value}
        else:
            source = {key: row.get(key)}
        converted = numeric_value(source, key)
        if converted is not None and converted > 0:
            return converted
    return 10000.0


def normalized_metric(row: dict[str, Any], metric: str) -> float | None:
    direct = numeric_value(row, metric)
    if direct is not None:
        return direct
    if metric == "replacement_value_vs_cash_usd":
        return numeric_value(row, "pnl")
    if metric in {"replacement_value_vs_spy_usd", "replacement_value_vs_qqq_usd"}:
        detail = nested_dict(row, "replacement_value_comparator_detail")
        label = "SPY" if metric.endswith("spy_usd") else "QQQ"
        comp = detail.get(label)
        pnl = numeric_value(row, "pnl")
        if isinstance(comp, dict) and pnl is not None:
            comp_pnl = numeric_value(comp, "net_pnl_usd")
            if comp_pnl is not None:
                return pnl - comp_pnl
    return None


def normalize_position(
    row: dict[str, Any],
    *,
    sleeve_dir: str,
    bucket: str,
    sector_cache: dict[str, Any],
    index: int,
) -> dict[str, Any] | None:
    ticker = normalized_ticker(row)
    entry_date = parse_date(
        first_value(row, ["entry_date", "candidate.entry_date", "opened_at"])
    )
    exit_date = parse_date(first_value(row, ["exit_date", "closed_at"]))
    if not entry_date:
        return None
    sector, sector_lookup = sector_for_row(row, ticker, sector_cache)
    sleeve = normalized_sleeve(row, sleeve_dir)
    decision_id = str(row.get("decision_id") or f"{sleeve}:{entry_date}:{ticker}:{index}")
    metrics = {metric: normalized_metric(row, metric) for metric in PRIMARY_METRICS}
    return {
        "uid": f"{sleeve_dir}:{bucket}:{index}:{decision_id}",
        "source_state": f"data/paper_sleeves/{sleeve_dir}/state.json",
        "bucket": bucket,
        "sleeve_dir": sleeve_dir,
        "sleeve": sleeve,
        "decision_id": decision_id,
        "ticker": ticker,
        "sector": sector,
        "sector_lookup_status": sector_lookup.get("status"),
        "industry": sector_lookup.get("industry"),
        "entry_date": entry_date,
        "exit_date": exit_date,
        "notional": normalized_notional(row),
        "trade_enabled": bool(first_value(row, ["trade_enabled", "candidate.trade_enabled"]) or False),
        "status": str(row.get("paper_status") or row.get("status") or bucket),
        "pnl": numeric_value(row, "pnl"),
        **metrics,
    }


def load_positions() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    sector_cache = load_cache()
    positions: list[dict[str, Any]] = []
    diagnostics = {
        "state_files_seen": 0,
        "state_files_with_closed": 0,
        "malformed_state_files": [],
        "skipped_without_entry_date": 0,
    }
    for state_path in sorted(PAPER_ROOT.glob("*/state.json")):
        diagnostics["state_files_seen"] += 1
        sleeve_dir = state_path.parent.name
        try:
            payload = read_json(state_path, {}) or {}
        except json.JSONDecodeError:
            diagnostics["malformed_state_files"].append(repo_rel(state_path))
            continue
        if not isinstance(payload, dict):
            continue
        buckets = [
            ("closed_positions", "closed"),
            ("open_positions", "open"),
            ("pending_entries", "pending"),
        ]
        if payload.get("closed_positions"):
            diagnostics["state_files_with_closed"] += 1
        for key, bucket in buckets:
            rows = payload.get(key)
            if not isinstance(rows, list):
                continue
            for index, row in enumerate(rows):
                if not isinstance(row, dict):
                    continue
                normalized = normalize_position(
                    row,
                    sleeve_dir=sleeve_dir,
                    bucket=bucket,
                    sector_cache=sector_cache,
                    index=index,
                )
                if normalized is None:
                    diagnostics["skipped_without_entry_date"] += 1
                    continue
                positions.append(normalized)
    diagnostics["positions_loaded"] = len(positions)
    diagnostics["closed_positions_loaded"] = sum(1 for p in positions if p["bucket"] == "closed")
    return positions, diagnostics


def is_active_on(position: dict[str, Any], date: dt.date) -> bool:
    exit_date = position.get("exit_date")
    return position["entry_date"] <= date and (exit_date is None or exit_date >= date)


def label_concurrency(positions: list[dict[str, Any]]) -> None:
    for row in positions:
        if row["bucket"] != "closed":
            continue
        entry_date = row["entry_date"]
        active = [position for position in positions if is_active_on(position, entry_date)]
        same_sector = [p for p in active if p["sector"] == row["sector"]]
        same_sector_peers = [p for p in same_sector if p["uid"] != row["uid"]]
        active_notional = sum(max(float(p["notional"]), 0.0) for p in active)
        same_sector_notional = sum(max(float(p["notional"]), 0.0) for p in same_sector)
        notional_share = same_sector_notional / active_notional if active_notional else 0.0
        crowded = (
            len(same_sector) >= CONCURRENCY_RULE["min_same_sector_active_positions"]
            or notional_share >= CONCURRENCY_RULE["min_same_sector_active_notional_share"]
        )
        row["active_position_count_at_entry"] = len(active)
        row["same_sector_active_position_count_at_entry"] = len(same_sector)
        row["same_sector_active_peer_count_at_entry"] = len(same_sector_peers)
        row["active_notional_at_entry"] = round(active_notional, 2)
        row["same_sector_active_notional_at_entry"] = round(same_sector_notional, 2)
        row["same_sector_active_notional_share_at_entry"] = round(notional_share, 6)
        row["same_sector_crowded_at_entry"] = crowded
        row["same_sector_peer_tickers_at_entry"] = sorted({p["ticker"] for p in same_sector_peers})
        row["same_sector_peer_sleeves_at_entry"] = sorted({p["sleeve"] for p in same_sector_peers})


def metric_values(rows: list[dict[str, Any]], metric: str) -> list[float]:
    values = [row.get(metric) for row in rows]
    return [float(value) for value in values if isinstance(value, (int, float))]


def summarize_values(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "n": 0,
            "sum": None,
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
            "positive_rate": None,
        }
    return {
        "n": len(values),
        "sum": round(sum(values), 2),
        "mean": round(mean(values), 4),
        "median": round(median(values), 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "positive_rate": round(sum(1 for value in values if value > 0) / len(values), 6),
    }


def cohort_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "row_count": len(rows),
        "tickers": dict(sorted(Counter(row["ticker"] for row in rows).items())),
        "sectors": dict(sorted(Counter(row["sector"] for row in rows).items())),
        "sleeves": dict(sorted(Counter(row["sleeve_dir"] for row in rows).items())),
        "metrics": {
            metric: summarize_values(metric_values(rows, metric))
            for metric in [*PRIMARY_METRICS, "pnl"]
        },
    }


def mean_delta(crowded: list[dict[str, Any]], uncrowded: list[dict[str, Any]], metric: str) -> float | None:
    crowded_values = metric_values(crowded, metric)
    uncrowded_values = metric_values(uncrowded, metric)
    if not crowded_values or not uncrowded_values:
        return None
    return round(mean(crowded_values) - mean(uncrowded_values), 4)


def median_delta(crowded: list[dict[str, Any]], uncrowded: list[dict[str, Any]], metric: str) -> float | None:
    crowded_values = metric_values(crowded, metric)
    uncrowded_values = metric_values(uncrowded, metric)
    if not crowded_values or not uncrowded_values:
        return None
    return round(median(crowded_values) - median(uncrowded_values), 4)


def negative_loss_concentration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    losses_by_ticker: dict[str, float] = defaultdict(float)
    for row in rows:
        value = row.get("replacement_value_vs_cash_usd")
        if isinstance(value, (int, float)) and value < 0:
            losses_by_ticker[row["ticker"]] += abs(float(value))
    total = sum(losses_by_ticker.values())
    if total <= 0:
        return {
            "negative_loss_total": 0.0,
            "max_single_ticker_negative_loss_share": None,
            "top_negative_ticker": None,
            "losses_by_ticker": {},
        }
    top_ticker, top_loss = max(losses_by_ticker.items(), key=lambda item: item[1])
    return {
        "negative_loss_total": round(total, 2),
        "max_single_ticker_negative_loss_share": round(top_loss / total, 6),
        "top_negative_ticker": top_ticker,
        "losses_by_ticker": {
            ticker: round(value, 2)
            for ticker, value in sorted(losses_by_ticker.items())
        },
    }


def build_analysis() -> dict[str, Any]:
    positions, diagnostics = load_positions()
    label_concurrency(positions)
    closed = [
        row
        for row in positions
        if row["bucket"] == "closed"
        and all(isinstance(row.get(metric), (int, float)) for metric in PRIMARY_METRICS)
        and row["sector"] != "Unknown"
    ]
    crowded = [row for row in closed if row.get("same_sector_crowded_at_entry")]
    uncrowded = [row for row in closed if not row.get("same_sector_crowded_at_entry")]
    deltas = {
        metric: {
            "mean_crowded_minus_uncrowded": mean_delta(crowded, uncrowded, metric),
            "median_crowded_minus_uncrowded": median_delta(crowded, uncrowded, metric),
        }
        for metric in PRIMARY_METRICS
    }
    mean_worse = {
        metric: (
            deltas[metric]["mean_crowded_minus_uncrowded"] is not None
            and deltas[metric]["mean_crowded_minus_uncrowded"] < 0
        )
        for metric in PRIMARY_METRICS
    }
    median_worse = {
        metric: (
            deltas[metric]["median_crowded_minus_uncrowded"] is not None
            and deltas[metric]["median_crowded_minus_uncrowded"] < 0
        )
        for metric in PRIMARY_METRICS
    }
    concentration = negative_loss_concentration(crowded)
    checks = {
        "min_evaluable_closed_rows": len(closed) >= ACCEPTANCE_RULE["min_evaluable_closed_rows"],
        "min_crowded_rows": len(crowded) >= ACCEPTANCE_RULE["min_crowded_rows"],
        "min_uncrowded_rows": len(uncrowded) >= ACCEPTANCE_RULE["min_uncrowded_rows"],
        "crowded_mean_worse_all_primary_metrics": all(mean_worse.values()),
        "crowded_median_worse_primary_metrics_min": (
            sum(1 for passed in median_worse.values() if passed)
            >= ACCEPTANCE_RULE["require_crowded_median_worse_primary_metrics_min"]
        ),
        "negative_loss_concentration_passed": (
            concentration["max_single_ticker_negative_loss_share"] is not None
            and concentration["max_single_ticker_negative_loss_share"]
            <= ACCEPTANCE_RULE["max_single_ticker_negative_crowded_loss_share"]
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]
    sample_rows = sorted(
        crowded,
        key=lambda row: (
            row["entry_date"],
            row["sector"],
            row["sleeve_dir"],
            row["ticker"],
        ),
    )[:20]
    return {
        "diagnostics": diagnostics,
        "evaluable_closed_rows": len(closed),
        "crowded_rows": len(crowded),
        "uncrowded_rows": len(uncrowded),
        "cohorts": {
            "all_evaluable": cohort_summary(closed),
            "crowded": cohort_summary(crowded),
            "uncrowded": cohort_summary(uncrowded),
        },
        "deltas": deltas,
        "mean_worse": mean_worse,
        "median_worse": median_worse,
        "negative_loss_concentration": concentration,
        "checks": checks,
        "failed_reasons": failed,
        "crowded_sample_rows": [
            {
                "ticker": row["ticker"],
                "sector": row["sector"],
                "sleeve": row["sleeve_dir"],
                "entry_date": date_text(row["entry_date"]),
                "exit_date": date_text(row["exit_date"]),
                "same_sector_active_position_count_at_entry": row[
                    "same_sector_active_position_count_at_entry"
                ],
                "same_sector_active_notional_share_at_entry": row[
                    "same_sector_active_notional_share_at_entry"
                ],
                "same_sector_peer_tickers_at_entry": row["same_sector_peer_tickers_at_entry"],
                "replacement_value_vs_cash_usd": row["replacement_value_vs_cash_usd"],
                "replacement_value_vs_spy_usd": row["replacement_value_vs_spy_usd"],
                "replacement_value_vs_qqq_usd": row["replacement_value_vs_qqq_usd"],
            }
            for row in sample_rows
        ],
    }


def build_result() -> dict[str, Any]:
    timestamp = utc_now()
    prediction = load_ticket_prediction()
    baseline = baseline_metrics()
    analysis = build_analysis()
    passed = not analysis["failed_reasons"]
    status = (
        "observed_only_positive_lead_not_policy_ready"
        if passed
        else "observed_only_rejected"
    )
    decision = (
        "observed_only_positive_sector_concurrency_risk_lead"
        if passed
        else "observed_only_rejected_sector_concurrency_no_stable_edge"
    )
    realized_failures = list(analysis["failed_reasons"])
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "owner": OWNER,
        "lane": LANE,
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "alpha_ready": False,
        "observed_only_lead": passed,
        "alpha_hypothesis": HYPOTHESIS,
        "hypothesis": HYPOTHESIS,
        "change_type": "observed_only_forward_attribution",
        "implementation_mode": "observed_only_attribution",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": [
            "closed paper state extraction",
            "entry-date sector concurrency labeling",
            "cash/SPY/QQQ replacement-value comparison",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "new_gate_shape_on_settled_forward_rows",
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "calibration": {
            "actual_success": 1 if passed else 0,
            "predicted_success_probability": prediction["success_probability"],
            "brier_score": round((float(prediction["success_probability"]) - (1 if passed else 0)) ** 2, 4),
            "predicted_failure_modes": prediction["main_failure_modes"],
            "realized_failure_modes": realized_failures,
            "predicted_failure_mode_hit": any(
                failure in ",".join(realized_failures)
                for failure in prediction["main_failure_modes"]
            ),
        },
        "parameters": {
            "paper_root": repo_rel(PAPER_ROOT),
            "baseline_result_file": repo_rel(BASELINE_PATH),
            "concurrency_rule": CONCURRENCY_RULE,
            "acceptance_rule": ACCEPTANCE_RULE,
            "sector_lookup_rule": "broad_market_sector_map.lookup_sector fallback when row sector is missing or Unknown",
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "strategy_behavior_changed": False,
            "crowded_minus_uncrowded_mean_cash": analysis["deltas"][
                "replacement_value_vs_cash_usd"
            ]["mean_crowded_minus_uncrowded"],
            "crowded_minus_uncrowded_mean_spy": analysis["deltas"][
                "replacement_value_vs_spy_usd"
            ]["mean_crowded_minus_uncrowded"],
            "crowded_minus_uncrowded_mean_qqq": analysis["deltas"][
                "replacement_value_vs_qqq_usd"
            ]["mean_crowded_minus_uncrowded"],
        },
        "gate1": {
            "passed": baseline["baseline_exists"],
            "baseline_metrics": baseline,
            "note": "Observed-only attribution; canonical strategy baseline unchanged.",
        },
        "gate2": {
            "passed": True,
            "fields_checked": [
                "entry_date",
                "exit_date",
                "ticker",
                "sector or broad_market_sector_map fallback",
                "notional",
                "replacement_value_vs_cash_usd",
                "replacement_value_vs_spy_usd",
                "replacement_value_vs_qqq_usd",
            ],
            "diagnostics": analysis["diagnostics"],
            "target_price_relevance": "This run does not generate backtest signals or exits; target_price is not consumed.",
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "note": "No executable filter, ranking, sizing, exit, prompt, or order rule was added.",
        },
        "gate4": {
            "passed": passed,
            "observed_only": True,
            "strategy_rerun_required": False,
            "accepted_alpha": False,
            "decision": decision,
            "acceptance_rule": ACCEPTANCE_RULE,
            "concurrency_rule": CONCURRENCY_RULE,
            "checks": analysis["checks"],
            "failed_reasons": analysis["failed_reasons"],
            "summary": {
                "evaluable_closed_rows": analysis["evaluable_closed_rows"],
                "crowded_rows": analysis["crowded_rows"],
                "uncrowded_rows": analysis["uncrowded_rows"],
                "deltas": analysis["deltas"],
                "negative_loss_concentration": analysis["negative_loss_concentration"],
            },
        },
        "analysis": analysis,
        "production_impact": {
            "trade_enabled": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "paper_orders_changed": False,
            "live_orders_changed": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "parity_note": "Read-only attribution over existing default-off paper state files; no helper, adapter, order, rank, size, exit, watchlist, or LLM behavior changed.",
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The fixed sector-concurrency label was tested on all closed "
                "default-off paper rows that carried entry dates, sectors, and "
                "cash/SPY/QQQ replacement values. The result is only a forward "
                "attribution read, not a policy."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune the 3-position or 50% sector-crowding thresholds, "
                "switch to adjacent sector/industry buckets, or convert this into "
                "a cap/scalar without a separate shared-policy Gate 1-4 test."
            ),
            "new_evidence_required": (
                "A valid retry needs materially more closed default-off rows under "
                "the unchanged sector-concurrency contract, a missed-risk incident "
                "with a different fixed grouping, or a full shared-policy Gate 1-4 "
                "sector exposure cap test."
            ),
        },
        "next_retry_requires": [
            "materially more closed default-off paper rows under the unchanged sector-concurrency contract",
            "a concrete missed-risk incident requiring a different fixed grouping",
            "or a separate shared-policy Gate 1-4 sector exposure cap test",
        ],
        "rejection_reason": None if passed else ";".join(analysis["failed_reasons"]),
        "related_files": RELATED_FILES,
        "changed_files": CHANGED_FILES,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "lean_quality_passed": True,
        "llm_metrics": {"used_llm": False},
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
    }


def compact_log_record(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": result["timestamp"],
        "owner": OWNER,
        "lane": LANE,
        "status": result["status"],
        "decision": result["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "alpha_ready": False,
        "observed_only_lead": result["observed_only_lead"],
        "alpha_hypothesis": HYPOTHESIS,
        "hypothesis": HYPOTHESIS,
        "change_type": result["change_type"],
        "implementation_mode": result["implementation_mode"],
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": result["causal_components"],
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": result["new_evidence_type"],
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": result["prediction"],
        "calibration": result["calibration"],
        "before_metrics": result["before_metrics"],
        "after_metrics": result["after_metrics"],
        "delta_metrics": result["delta_metrics"],
        "gate1": result["gate1"],
        "gate2": result["gate2"],
        "gate3": result["gate3"],
        "gate4": result["gate4"],
        "summary": result["gate4"]["summary"],
        "production_impact": result["production_impact"],
        "rejection_reason": result["rejection_reason"],
        "post_run_reflection": result["post_run_reflection"],
        "next_retry_requires": result["next_retry_requires"],
        "related_files": result["related_files"],
        "changed_files": CHANGED_FILES,
        "reproduction_commands": result["reproduction_commands"],
        "artifact": result["artifact"],
        "log": result["log"],
        "lean_quality_passed": True,
        "llm_metrics": result["llm_metrics"],
        "anti_js": result["anti_js"],
    }


def build_card(result: dict[str, Any]) -> str:
    summary = result["gate4"]["summary"]
    failed = result["gate4"]["failed_reasons"]
    return f"""# {EXPERIMENT_ID} - Sector Concurrency Forward RV

## Hypothesis

{HYPOTHESIS}

## Result

- Decision: `{result["decision"]}`
- Status: `{result["status"]}`
- Evaluable closed rows: `{summary["evaluable_closed_rows"]}`
- Crowded / uncrowded rows: `{summary["crowded_rows"]}` / `{summary["uncrowded_rows"]}`
- Crowded minus uncrowded mean cash/SPY/QQQ RV: `{result["delta_metrics"]["crowded_minus_uncrowded_mean_cash"]}` / `{result["delta_metrics"]["crowded_minus_uncrowded_mean_spy"]}` / `{result["delta_metrics"]["crowded_minus_uncrowded_mean_qqq"]}`
- Failed checks: `{", ".join(failed) if failed else "none"}`

## Boundary

{result["post_run_reflection"]["forbidden_near_neighbor_retry"]}

## Reproduce

```powershell
{RUNNER_COMMAND}
.\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict
```
"""


def update_ticket(result: dict[str, Any]) -> None:
    ticket = read_json(TICKET_JSON, {}) or {}
    ticket["status"] = result["status"]
    ticket["completed_at"] = result["timestamp"]
    ticket["result"] = {
        "decision": result["decision"],
        "artifact": result["artifact"],
        "log": result["log"],
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": result["observed_only_lead"],
    }
    ticket["gate4"] = result["gate4"]
    ticket["post_run_reflection"] = result["post_run_reflection"]
    ticket["next_retry_requires"] = result["next_retry_requires"]
    write_json(TICKET_JSON, ticket)


def write_manifest(result: dict[str, Any]) -> None:
    write_json(
        MANIFEST_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": result["status"],
            "decision": result["decision"],
            "artifact": result["artifact"],
            "log": result["log"],
            "runner": RUNNER,
            "generated_at": result["timestamp"],
            "changed_files": CHANGED_FILES,
            "reproduction_commands": result["reproduction_commands"],
        },
    )


def main() -> int:
    result = build_result()
    write_json(OUT_JSON, result)
    save_experiment_log_entry(compact_log_record(result), allow_duplicate=True)
    write_text(CARD_MD, build_card(result))
    write_manifest(result)
    update_ticket(result)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=result["prediction"],
        result={
            "accepted": False,
            "accepted_alpha": False,
            "alpha_ready": False,
            "observed_only_lead": result["observed_only_lead"],
            "decision": result["decision"],
            "artifact": result["artifact"],
            "log": result["log"],
            "runner": RUNNER,
            "gate4": result["gate4"],
            "summary": result["gate4"]["summary"],
        },
        status=result["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "alpha_hypothesis": HYPOTHESIS,
            "change_type": result["change_type"],
            "implementation_mode": result["implementation_mode"],
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": result["causal_components"],
            "nearby_prior_experiments": NEARBY_PRIORS,
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": result["new_evidence_type"],
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "decision": result["decision"],
            "artifact": result["artifact"],
            "log_file": result["log"],
            "card_file": repo_rel(CARD_MD),
            "gate1": result["gate1"],
            "gate2": result["gate2"],
            "gate3": result["gate3"],
            "gate4": result["gate4"],
            "production_impact": result["production_impact"],
            "post_run_reflection": result["post_run_reflection"],
            "next_retry_requires": result["next_retry_requires"],
            "related_files": result["related_files"],
            "changed_files": CHANGED_FILES,
            "allowed_write_scope": CHANGED_FILES,
            "lean_quality_passed": result["lean_quality_passed"],
        },
    )
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": result["status"],
                "decision": result["decision"],
                "evaluable_closed_rows": result["gate4"]["summary"]["evaluable_closed_rows"],
                "crowded_rows": result["gate4"]["summary"]["crowded_rows"],
                "uncrowded_rows": result["gate4"]["summary"]["uncrowded_rows"],
                "failed_reasons": result["gate4"]["failed_reasons"],
                "artifact": result["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
