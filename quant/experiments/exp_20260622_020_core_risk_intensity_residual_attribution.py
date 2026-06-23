"""exp-20260622-020: residualized core risk-intensity attribution.

Observed-only alpha attribution. This runner checks whether the positive
exp-20260622-019 risk-intensity/PnL relationship survives after removing
window, ticker, sector, strategy, and applied multiplier-family effects.

It changes no entry, ranking, sizing, exit, live, or paper order behavior.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260622-020"
SLUG = "core_risk_intensity_residual_attribution"
RUNNER = f"quant/experiments/exp_20260622_020_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
OWNER = "alpha-explore"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260622_020_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

AGGREGATE_BASELINE = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
WINDOW_FILES = {
    "late_strong": REPO_ROOT
    / "data"
    / "backtests"
    / "archive"
    / "20260604_ohlcv_warehouse_replay"
    / "backtest_results_warehouse_snapshot_late_strong_20260604.json",
    "mid_weak": REPO_ROOT
    / "data"
    / "backtests"
    / "archive"
    / "20260604_ohlcv_warehouse_replay"
    / "backtest_results_warehouse_snapshot_mid_weak_20260604.json",
    "old_thin": REPO_ROOT
    / "data"
    / "backtests"
    / "archive"
    / "20260604_ohlcv_warehouse_replay"
    / "backtest_results_warehouse_snapshot_old_thin_20260604.json",
}
RELATED_PRIOR_LOGS = [
    "experiments/logs/exp-20260622-019.json",
    "experiments/logs/exp-20260622-017.json",
    "experiments/logs/exp-20260618-008.json",
]

HYPOTHESIS = (
    "Observed-only deconfounding: if current core risk intensity is a real "
    "alpha attribution surface, the positive PnL relation should survive "
    "residualizing by window, ticker, sector, entry strategy, and applied "
    "multiplier-family buckets before any future sizing policy is considered."
)
CHANGED_VARIABLE = "core_risk_intensity_residual_attribution_v1"
CHANGE_TYPE = "observed_only_attribution"
MECHANISM_FAMILY = "risk_allocation_attribution"
TRIAL_FAMILY = "core_risk_intensity_residual_attribution"
TRIAL_VARIANT_ID = "observed_only_residualized_canonical_windows_v1"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260622-019",
    "exp-20260622-017",
    "exp-20260618-008",
]
NEW_EVIDENCE_TYPE = "residualized_accepted_core_closed_trade_risk_intensity_attribution"
NEW_EVIDENCE_AXIS = (
    "Residualized attribution of the positive exp-20260622-019 risk-intensity "
    "lead; no scalar, filter, ranking, entry, exit, or production behavior change."
)
CAUSAL_COMPONENTS = [
    "canonical closed core trades",
    "risk-intensity residualization",
    "no strategy change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260622-020/exp_20260622_020_core_risk_intensity_residual_attribution.json",
    "experiments/logs/exp-20260622-020.json",
    "experiments/cards/exp-20260622-020.md",
    "experiments/manifests/exp-20260622-020.json",
    "experiments/tickets/exp-20260622-020.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]

PREDICTION = {
    "success_probability": 0.24,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "relation_explained_by_ticker_or_window",
        "relation_explained_by_strategy_or_multiplier",
        "thin_group_residuals",
        "non_monotonic_residual_pnl",
        "endogenous_sizing_stack",
    ],
    "confidence_reason": (
        "exp-20260622-019 found strong raw monotonicity, but prior risk "
        "scalar/topup retunes were fragile and the relation may simply identify "
        "existing winning tickers or multiplier labels rather than a new "
        "deployable decision variable."
    ),
    "recorded_at": "2026-06-22T19:03:35+00:00",
}

BASE_DIMENSIONS = ["window", "ticker", "sector", "strategy"]
MULTIPLIER_FAMILY_FIELDS = [
    "family_risk_on",
    "family_spy_relative",
    "family_rs",
    "family_clean_spy",
    "family_signal_day",
    "family_trend",
    "family_slot_topup",
    "family_ticker_specific",
    "family_dte",
    "family_extension",
    "family_sector_specific",
]
COMBINED_DIMENSIONS = [*BASE_DIMENSIONS, *MULTIPLIER_FAMILY_FIELDS]
BUCKET_ORDER = ["low", "mid", "high"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                lines.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                lines.append(json.dumps(record, sort_keys=True))
                replaced = True
            else:
                lines.append(raw)
    if not replaced:
        lines.append(json.dumps(record, sort_keys=True))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    out = [0.0] * len(values)
    cursor = 0
    while cursor < len(order):
        end = cursor + 1
        while end < len(order) and values[order[end]] == values[order[cursor]]:
            end += 1
        avg_rank = (cursor + 1 + end) / 2.0
        for rank_index in range(cursor, end):
            out[order[rank_index]] = avg_rank
        cursor = end
    return out


def spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 4:
        return None
    rx = ranks(xs)
    ry = ranks(ys)
    mean_x = sum(rx) / len(rx)
    mean_y = sum(ry) / len(ry)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(rx, ry))
    den_x = math.sqrt(sum((x - mean_x) ** 2 for x in rx))
    den_y = math.sqrt(sum((y - mean_y) ** 2 for y in ry))
    if den_x == 0 or den_y == 0:
        return None
    return round(numerator / (den_x * den_y), 4)


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 4:
        return None
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
    if den_x == 0 or den_y == 0:
        return None
    return round(numerator / (den_x * den_y), 4)


def load_ticket_prediction() -> dict[str, Any]:
    if not TICKET_JSON.exists():
        return PREDICTION
    ticket = read_json(TICKET_JSON)
    prediction = ticket.get("prediction")
    return prediction if isinstance(prediction, dict) and prediction else PREDICTION


def aggregate_metrics(aggregate: dict[str, Any]) -> dict[str, Any]:
    windows = list(aggregate.get("windows") or [])
    generated = sum(float(window.get("signals_generated") or 0.0) for window in windows)
    survived = sum(float(window.get("signals_survived") or 0.0) for window in windows)
    trade_count = sum(int(window.get("trade_count") or 0) for window in windows)
    total_pnl = sum(float(window.get("total_pnl") or 0.0) for window in windows)
    ev_values = [float(window.get("expected_value_score") or 0.0) for window in windows]
    return {
        "window_count": len(windows),
        "expected_value_score_sum": round(sum(ev_values), 4),
        "expected_value_score_mean": round(sum(ev_values) / len(ev_values), 4)
        if ev_values
        else None,
        "total_pnl": round(total_pnl, 2),
        "trade_count": trade_count,
        "signals_generated": int(generated),
        "signals_survived": int(survived),
        "survival_rate": round(survived / generated, 4) if generated else None,
        "max_drawdown_pct_worst": max(
            float(window.get("max_drawdown_pct") or 0.0) for window in windows
        )
        if windows
        else None,
        "windows": windows,
    }


def multiplier_family_flags(keys: list[str]) -> dict[str, str]:
    key_text = " ".join(keys)
    flags = {
        "family_risk_on": "risk_on_unmodified" in key_text,
        "family_spy_relative": "spy_relative" in key_text,
        "family_rs": "rs20" in key_text or "rs60" in key_text,
        "family_clean_spy": "clean_spy" in key_text,
        "family_signal_day": "signal_day" in key_text,
        "family_trend": "trend_" in key_text,
        "family_slot_topup": "slot_rank" in key_text or "slot_stock_rank" in key_text,
        "family_ticker_specific": "tsm_core" in key_text or "isrg_core" in key_text,
        "family_dte": "_dte_" in key_text,
        "family_extension": "extension" in key_text or "near_high" in key_text,
        "family_sector_specific": (
            "financials" in key_text
            or "commodities" in key_text
            or "tech_" in key_text
            or "healthcare" in key_text
            or "comms" in key_text
        ),
    }
    return {field: "yes" if value else "no" for field, value in flags.items()}


def load_trade_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    field_presence = {
        "entry_date": 0,
        "target_price": 0,
        "base_risk_pct": 0,
        "actual_risk_pct": 0,
        "pnl": 0,
        "sector": 0,
        "strategy": 0,
        "sizing_multipliers": 0,
    }
    total_trades = 0
    for window, path in WINDOW_FILES.items():
        data = read_json(path)
        for index, trade in enumerate(data.get("trades") or []):
            total_trades += 1
            for field in field_presence:
                if trade.get(field) is not None:
                    field_presence[field] += 1
            base_risk = as_float(trade.get("base_risk_pct"))
            actual_risk = as_float(trade.get("actual_risk_pct"))
            pnl = as_float(trade.get("pnl"))
            if base_risk is None or base_risk <= 0 or actual_risk is None or actual_risk <= 0:
                skipped.append(
                    {
                        "window": window,
                        "index": index,
                        "reason": "missing_or_nonpositive_risk_fields",
                    }
                )
                continue
            if pnl is None:
                skipped.append({"window": window, "index": index, "reason": "missing_pnl"})
                continue
            multipliers = trade.get("sizing_multipliers") or {}
            multiplier_keys = sorted(str(key) for key in multipliers)
            risk_multiplier_keys = [
                key for key in multiplier_keys if key.endswith("_risk_multiplier_applied")
            ]
            family_flags = multiplier_family_flags(risk_multiplier_keys)
            row = {
                "window": window,
                "trade_key": trade.get("trade_key") or f"{window}:{index}",
                "ticker": trade.get("ticker") or "unknown",
                "strategy": trade.get("strategy") or "unknown",
                "sector": trade.get("sector") or "unknown",
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "exit_reason": trade.get("exit_reason"),
                "pnl": pnl,
                "pnl_pct_net": as_float(trade.get("pnl_pct_net")),
                "base_risk_pct": base_risk,
                "actual_risk_pct": actual_risk,
                "risk_intensity": actual_risk / base_risk,
                "sizing_multiplier_keys": multiplier_keys,
                "risk_multiplier_keys": risk_multiplier_keys,
                "risk_multiplier_count": len(risk_multiplier_keys),
            }
            row.update(family_flags)
            rows.append(row)
    checks = {
        "total_trades": total_trades,
        "usable_trades": len(rows),
        "skipped_trades": skipped,
        "field_presence": field_presence,
        "dimension_group_counts": dimension_group_counts(rows, COMBINED_DIMENSIONS),
    }
    if field_presence["entry_date"] != total_trades:
        raise ValueError("entry_date missing from one or more baseline trade rows")
    if len(rows) < 9:
        raise ValueError("not enough usable risk-intensity rows for attribution")
    return rows, checks


def dimension_group_counts(rows: list[dict[str, Any]], dimensions: list[str]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for dimension in dimensions:
        counts: dict[str, int] = defaultdict(int)
        for row in rows:
            counts[str(row.get(dimension) or "unknown")] += 1
        sorted_counts = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        output[dimension] = {
            "group_count": len(sorted_counts),
            "singleton_count": sum(1 for _, count in sorted_counts if count == 1),
            "top_groups": [
                {"value": value, "n": count} for value, count in sorted_counts[:12]
            ],
        }
    return output


def residualize(
    rows: list[dict[str, Any]],
    values: list[float],
    dimensions: list[str],
    *,
    iterations: int = 60,
    min_group_size: int = 2,
) -> list[float]:
    """Remove additive fixed effects by repeated within-group demeaning."""
    if not values:
        return []
    global_mean = sum(values) / len(values)
    residuals = [value - global_mean for value in values]
    dimension_groups: list[list[list[int]]] = []
    for dimension in dimensions:
        buckets: dict[str, list[int]] = defaultdict(list)
        for index, row in enumerate(rows):
            buckets[str(row.get(dimension) or "unknown")].append(index)
        dimension_groups.append(
            [indices for indices in buckets.values() if len(indices) >= min_group_size]
        )

    for _ in range(iterations):
        max_adjustment = 0.0
        for groups in dimension_groups:
            for indices in groups:
                mean_residual = sum(residuals[index] for index in indices) / len(indices)
                if mean_residual:
                    for index in indices:
                        residuals[index] -= mean_residual
                    max_adjustment = max(max_adjustment, abs(mean_residual))
        if max_adjustment < 1e-10:
            break
    return residuals


def assign_tertiles(rows: list[dict[str, Any]], field: str, output_field: str) -> None:
    ordered = sorted(
        range(len(rows)),
        key=lambda index: (
            rows[index][field],
            rows[index].get("entry_date") or "",
            rows[index].get("ticker") or "",
            rows[index].get("trade_key") or "",
        ),
    )
    n = len(ordered)
    for rank, row_index in enumerate(ordered):
        if rank < n / 3:
            bucket = "low"
        elif rank < (2 * n) / 3:
            bucket = "mid"
        else:
            bucket = "high"
        rows[row_index][output_field] = bucket


def summarize_rows(rows: list[dict[str, Any]], *, residual: bool) -> dict[str, Any]:
    if not rows:
        return {
            "n": 0,
            "raw_total_pnl": 0.0,
            "raw_mean_pnl": None,
            "raw_median_pnl": None,
            "residual_mean_pnl": None,
            "residual_median_pnl": None,
            "mean_risk_intensity": None,
            "mean_residual_risk_intensity": None,
            "win_rate": None,
        }
    raw_pnls = [float(row["pnl"]) for row in rows]
    risk_values = [float(row["risk_intensity"]) for row in rows]
    output = {
        "n": len(rows),
        "raw_total_pnl": round(sum(raw_pnls), 2),
        "raw_mean_pnl": round(sum(raw_pnls) / len(raw_pnls), 2),
        "raw_median_pnl": round(float(median(raw_pnls)), 2),
        "mean_risk_intensity": round(sum(risk_values) / len(risk_values), 4),
        "win_rate": round(sum(1 for pnl in raw_pnls if pnl > 0) / len(raw_pnls), 4),
    }
    if residual:
        residual_pnls = [float(row["residual_pnl"]) for row in rows]
        residual_risks = [float(row["residual_risk_intensity"]) for row in rows]
        output.update(
            {
                "residual_mean_pnl": round(sum(residual_pnls) / len(residual_pnls), 4),
                "residual_median_pnl": round(float(median(residual_pnls)), 4),
                "mean_residual_risk_intensity": round(
                    sum(residual_risks) / len(residual_risks), 6
                ),
            }
        )
    return output


def bucket_summary(rows: list[dict[str, Any]], bucket_field: str, *, residual: bool) -> dict[str, Any]:
    return {
        bucket: summarize_rows(
            [row for row in rows if row[bucket_field] == bucket],
            residual=residual,
        )
        for bucket in BUCKET_ORDER
    }


def analyze_residualization(
    rows: list[dict[str, Any]],
    dimensions: list[str],
) -> dict[str, Any]:
    risk_residual = residualize(rows, [row["risk_intensity"] for row in rows], dimensions)
    pnl_residual = residualize(rows, [row["pnl"] for row in rows], dimensions)
    analysis_rows: list[dict[str, Any]] = []
    for row, risk_value, pnl_value in zip(rows, risk_residual, pnl_residual):
        analysis_row = dict(row)
        analysis_row["residual_risk_intensity"] = risk_value
        analysis_row["residual_pnl"] = pnl_value
        analysis_rows.append(analysis_row)
    assign_tertiles(
        analysis_rows,
        "residual_risk_intensity",
        "residual_risk_intensity_bucket",
    )
    by_window: dict[str, Any] = {}
    for window in WINDOW_FILES:
        window_rows = [row for row in analysis_rows if row["window"] == window]
        by_window[window] = {
            "n": len(window_rows),
            "spearman_residual_risk_to_residual_pnl": spearman(
                [row["residual_risk_intensity"] for row in window_rows],
                [row["residual_pnl"] for row in window_rows],
            ),
            "pearson_residual_risk_to_residual_pnl": pearson(
                [row["residual_risk_intensity"] for row in window_rows],
                [row["residual_pnl"] for row in window_rows],
            ),
            "bucket_summary": bucket_summary(
                window_rows,
                "residual_risk_intensity_bucket",
                residual=True,
            ),
        }
    return {
        "dimensions": dimensions,
        "dimension_group_counts": dimension_group_counts(rows, dimensions),
        "pooled": {
            "spearman_residual_risk_to_residual_pnl": spearman(
                [row["residual_risk_intensity"] for row in analysis_rows],
                [row["residual_pnl"] for row in analysis_rows],
            ),
            "pearson_residual_risk_to_residual_pnl": pearson(
                [row["residual_risk_intensity"] for row in analysis_rows],
                [row["residual_pnl"] for row in analysis_rows],
            ),
            "bucket_summary": bucket_summary(
                analysis_rows,
                "residual_risk_intensity_bucket",
                residual=True,
            ),
        },
        "by_window": by_window,
        "sample_rows": [
            {
                "window": row["window"],
                "ticker": row["ticker"],
                "entry_date": row["entry_date"],
                "raw_pnl": round(row["pnl"], 2),
                "risk_intensity": round(row["risk_intensity"], 4),
                "residual_pnl": round(row["residual_pnl"], 4),
                "residual_risk_intensity": round(row["residual_risk_intensity"], 6),
                "bucket": row["residual_risk_intensity_bucket"],
                "risk_multiplier_count": row["risk_multiplier_count"],
            }
            for row in sorted(
                analysis_rows,
                key=lambda item: item["residual_risk_intensity"],
                reverse=True,
            )[:15]
        ],
    }


def raw_attribution(rows: list[dict[str, Any]]) -> dict[str, Any]:
    raw_rows = [dict(row) for row in rows]
    assign_tertiles(raw_rows, "risk_intensity", "risk_intensity_bucket")
    return {
        "pooled": {
            "spearman_risk_intensity_to_pnl": spearman(
                [row["risk_intensity"] for row in raw_rows],
                [row["pnl"] for row in raw_rows],
            ),
            "pearson_risk_intensity_to_pnl": pearson(
                [row["risk_intensity"] for row in raw_rows],
                [row["pnl"] for row in raw_rows],
            ),
            "bucket_summary": bucket_summary(raw_rows, "risk_intensity_bucket", residual=False),
        },
        "by_window": {
            window: {
                "n": len([row for row in raw_rows if row["window"] == window]),
                "spearman_risk_intensity_to_pnl": spearman(
                    [row["risk_intensity"] for row in raw_rows if row["window"] == window],
                    [row["pnl"] for row in raw_rows if row["window"] == window],
                ),
            }
            for window in WINDOW_FILES
        },
    }


def single_dimension_diagnostics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    diagnostics: dict[str, Any] = {}
    for dimension in COMBINED_DIMENSIONS:
        analysis = analyze_residualization(rows, [dimension])
        pooled = analysis["pooled"]
        diagnostics[dimension] = {
            "spearman": pooled["spearman_residual_risk_to_residual_pnl"],
            "pearson": pooled["pearson_residual_risk_to_residual_pnl"],
            "group_count": analysis["dimension_group_counts"][dimension]["group_count"],
            "singleton_count": analysis["dimension_group_counts"][dimension][
                "singleton_count"
            ],
        }
    return diagnostics


def acceptance_checks(combined: dict[str, Any]) -> dict[str, Any]:
    pooled = combined["pooled"]
    bucketed = pooled["bucket_summary"]
    low = bucketed["low"]
    high = bucketed["high"]
    window_spearman = {
        window: data["spearman_residual_risk_to_residual_pnl"]
        for window, data in combined["by_window"].items()
    }
    return {
        "pooled_residual_spearman_positive": (
            pooled["spearman_residual_risk_to_residual_pnl"] is not None
            and pooled["spearman_residual_risk_to_residual_pnl"] > 0
        ),
        "window_residual_spearman_positive_count": sum(
            1 for value in window_spearman.values() if value is not None and value > 0
        ),
        "window_residual_spearman_values": window_spearman,
        "high_residual_bucket_mean_beats_low": (
            high["residual_mean_pnl"] is not None
            and low["residual_mean_pnl"] is not None
            and high["residual_mean_pnl"] > low["residual_mean_pnl"]
        ),
        "high_residual_bucket_median_beats_low": (
            high["residual_median_pnl"] is not None
            and low["residual_median_pnl"] is not None
            and high["residual_median_pnl"] > low["residual_median_pnl"]
        ),
        "high_residual_bucket_n": high["n"],
        "low_residual_bucket_n": low["n"],
    }


def failed_reasons(checks: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if not checks["pooled_residual_spearman_positive"]:
        reasons.append("pooled_residual_spearman_not_positive")
    if checks["window_residual_spearman_positive_count"] < 2:
        reasons.append("fewer_than_two_windows_positive_residual_spearman")
    if not checks["high_residual_bucket_mean_beats_low"]:
        reasons.append("high_residual_bucket_mean_not_above_low")
    if not checks["high_residual_bucket_median_beats_low"]:
        reasons.append("high_residual_bucket_median_not_above_low")
    return reasons


def compact_attribution(attribution: dict[str, Any]) -> dict[str, Any]:
    return {
        "n_rows": attribution["n_rows"],
        "raw": attribution["raw"],
        "combined_residual": attribution["combined_residual"],
        "single_dimension_diagnostics": attribution["single_dimension_diagnostics"],
    }


def build_payload() -> dict[str, Any]:
    prediction = load_ticket_prediction()
    aggregate = read_json(AGGREGATE_BASELINE)
    baseline_metrics = aggregate_metrics(aggregate)
    rows, field_checks = load_trade_rows()
    raw = raw_attribution(rows)
    combined = analyze_residualization(rows, COMBINED_DIMENSIONS)
    single_dimension = single_dimension_diagnostics(rows)
    checks = acceptance_checks(combined)
    reasons = failed_reasons(checks)
    observed_only_lead = not reasons
    status = (
        "observed_only_positive_lead"
        if observed_only_lead
        else "observed_only_rejected"
    )
    decision = (
        "observed_only_positive_core_risk_intensity_residual_lead_not_promoted"
        if observed_only_lead
        else "observed_only_rejected_core_risk_intensity_explained_by_confounders"
    )
    now = utc_now()
    attribution = {
        "n_rows": len(rows),
        "residualization_method": (
            "Iterative additive fixed-effect demeaning of both risk_intensity "
            "and PnL. Groups with fewer than two observations are not demeaned "
            "to avoid zeroing singleton ticker trades."
        ),
        "raw": raw,
        "combined_residual": combined,
        "single_dimension_diagnostics": single_dimension,
        "rows": [
            {
                key: row[key]
                for key in (
                    "window",
                    "trade_key",
                    "ticker",
                    "sector",
                    "strategy",
                    "entry_date",
                    "exit_date",
                    "pnl",
                    "base_risk_pct",
                    "actual_risk_pct",
                    "risk_intensity",
                    "risk_multiplier_count",
                    *MULTIPLIER_FAMILY_FIELDS,
                )
            }
            for row in rows
        ],
    }

    why_positive = (
        "Risk intensity retained positive residual association with realized "
        "PnL after additive controls for window, ticker, sector, strategy, and "
        "multiplier-family buckets. This is still observed-only because it is "
        "endogenous to the accepted sizing stack and no after-policy was tested."
    )
    why_rejected = (
        "The raw risk-intensity edge weakened after removing known grouping "
        "effects, so the positive exp-20260622-019 lead is better treated as "
        "an attribution of the current sizing stack than as a standalone "
        "decision variable."
    )

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": status,
        "lane": "alpha_search",
        "owner": OWNER,
        "decision": decision,
        "observed_only_lead": observed_only_lead,
        "accepted": False,
        "accepted_alpha": False,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "observed_only_attribution_runner",
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
        "pre_run_questions": {
            "profit_hypothesis": (
                "If risk intensity is more than a label for winning tickers or "
                "windows, residualized risk intensity should still track "
                "residualized realized PnL."
            ),
            "category": "risk_allocation",
            "past_near_experiments": {
                "novelty_gate": "passed with no strong near-neighbor",
                "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
                "important_boundary": (
                    "This is a deconfounding attribution of exp-20260622-019, "
                    "not a scalar, top-up, rank, entry, or exit retry."
                ),
            },
            "single_policy_bundle": (
                "Accepted core closed trades plus residualized risk-intensity "
                "attribution; no rule, threshold, ranking, entry, exit, or "
                "sizing behavior changed."
            ),
            "success_failure_standard": (
                "Observed-only lead only if residualized risk_intensity has "
                "positive pooled Spearman with residual PnL, at least two of "
                "three window residual Spearman values are positive, and the "
                "high residual-intensity tertile beats low on residual mean "
                "and median PnL."
            ),
            "reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "risk_intensity_formula": "actual_risk_pct / base_risk_pct",
            "base_dimensions": BASE_DIMENSIONS,
            "multiplier_family_fields": MULTIPLIER_FAMILY_FIELDS,
            "combined_residual_dimensions": COMBINED_DIMENSIONS,
            "input_windows": {
                window: repo_rel(path) for window, path in WINDOW_FILES.items()
            },
        },
        "gate1": {
            "baseline_loaded": True,
            "baseline_result_file": repo_rel(AGGREGATE_BASELINE),
            "window_files": {
                window: repo_rel(path) for window, path in WINDOW_FILES.items()
            },
            "baseline_metrics": baseline_metrics,
        },
        "gate2": {
            "dependencies_validated": True,
            "field_presence": field_checks["field_presence"],
            "dimension_group_counts": field_checks["dimension_group_counts"],
            "total_trades": field_checks["total_trades"],
            "usable_trades": field_checks["usable_trades"],
            "skipped_trades": field_checks["skipped_trades"],
            "entry_date": {
                "required": True,
                "present_rows": field_checks["field_presence"]["entry_date"],
            },
            "target_price": {
                "checked": True,
                "present_rows": field_checks["field_presence"]["target_price"],
                "used": False,
                "reason": (
                    "This observed-only closed-trade attribution consumes no "
                    "candidate/order target_price and changes no trading rule."
                ),
            },
            "required_observed_fields": [
                "entry_date",
                "base_risk_pct",
                "actual_risk_pct",
                "pnl",
                "sector",
                "strategy",
                "sizing_multipliers",
            ],
        },
        "gate3": {
            "survival_filter_added": False,
            "survival_rate_floor_checked": True,
            "baseline_survival_rate": baseline_metrics["survival_rate"],
            "signals_generated": baseline_metrics["signals_generated"],
            "signals_survived": baseline_metrics["signals_survived"],
            "observed_rows_survival_rate": 1.0,
            "note": "No new filter was added; this is closed-trade attribution only.",
        },
        "gate4": {
            "strategy_rerun_required": False,
            "reason": "Observed-only residual attribution; before and after policy are identical.",
            "acceptance_checks": checks,
            "failed_reasons": reasons,
            "decision": decision,
            "lead_limitations": [
                "No trading rule was changed.",
                "The field is endogenous to the already accepted sizing stack.",
                "Promotion would require a shared daily/forward attribution surface and closed rows.",
            ],
        },
        "before_metrics": baseline_metrics,
        "after_metrics": baseline_metrics,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "expected_value_score_mean_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "survival_rate_delta": 0.0,
            "max_drawdown_pct_worst_delta": 0.0,
        },
        "attribution": attribution,
        "production_impact": {
            "trade_enabled": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "shared_helper_promoted": False,
            "live_realistic_execution_envelope": (
                "Not evaluated; this is observed-only attribution, not a "
                "live-ready strategy."
            ),
        },
        "calibration": {
            "predicted_success_probability": prediction["success_probability"],
            "predicted_failure_modes": prediction["main_failure_modes"],
            "realized_failure_mode": (
                "none_positive_residual_lead"
                if observed_only_lead
                else ",".join(reasons) or "unknown"
            ),
            "predicted_failure_mode_hit": not observed_only_lead,
            "surprise_note": (
                "The residual relationship survived stronger controls than "
                "expected, but it remains a non-promoted lead."
                if observed_only_lead
                else "The positive raw relation was not robust enough after deconfounding."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": why_positive if observed_only_lead else why_rejected,
            "forbidden_near_neighbor_retry": (
                "Do not convert this result into a historical risk scalar, "
                "top-up, cap, or multiplier sweep on the same windows. A scalar "
                "promotion would be a different policy and would confound "
                "endogenous accepted-stack attribution with new alpha."
            ),
            "new_evidence_required": (
                "A valid promotion path needs a shared default-off daily ledger "
                "or forward attribution surface that records pre-execution "
                "risk-intensity rank, then enough closed rows to test whether "
                "incremental sizing or ranking improves EV without worse "
                "drawdown or concentration."
            ),
        },
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "related_files": [
            RUNNER,
            repo_rel(AGGREGATE_BASELINE),
            *[repo_rel(path) for path in WINDOW_FILES.values()],
            *RELATED_PRIOR_LOGS,
        ],
    }
    return payload


def build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "lane": payload["lane"],
        "owner": payload["owner"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "observed_only_lead": payload["observed_only_lead"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "single_causal_variable": payload["single_causal_variable"],
        "causal_components": payload["causal_components"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "new_evidence_axis": payload["new_evidence_axis"],
        "prediction": payload["prediction"],
        "pre_run_questions": payload["pre_run_questions"],
        "parameters": payload["parameters"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "attribution": compact_attribution(payload["attribution"]),
        "production_impact": payload["production_impact"],
        "calibration": payload["calibration"],
        "post_run_reflection": payload["post_run_reflection"],
        "related_files": payload["related_files"],
        "anti_js": payload["anti_js"],
    }


def build_card(payload: dict[str, Any]) -> str:
    raw_s = payload["attribution"]["raw"]["pooled"]["spearman_risk_intensity_to_pnl"]
    residual = payload["attribution"]["combined_residual"]
    residual_s = residual["pooled"]["spearman_residual_risk_to_residual_pnl"]
    bucketed = residual["pooled"]["bucket_summary"]
    rows = [
        "| Residual Bucket | Trades | Residual Mean PnL | Residual Median PnL | Raw Mean PnL | Raw Total PnL |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for bucket_name in BUCKET_ORDER:
        bucket = bucketed[bucket_name]
        rows.append(
            "| {name} | {n} | {rmean:,.4f} | {rmedian:,.4f} | ${raw_mean:,.2f} | ${raw_total:,.2f} |".format(
                name=bucket_name,
                n=bucket["n"],
                rmean=bucket["residual_mean_pnl"],
                rmedian=bucket["residual_median_pnl"],
                raw_mean=bucket["raw_mean_pnl"],
                raw_total=bucket["raw_total_pnl"],
            )
        )

    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: core risk-intensity residual attribution",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Production orders changed: no",
            "- Shared helper promoted: no",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Residual Attribution",
            "",
            *rows,
            "",
            f"- Raw Spearman(risk_intensity, PnL): `{raw_s}`",
            f"- Residual Spearman(risk_intensity, PnL): `{residual_s}`",
            "- Residual window Spearman values: `{}`".format(
                payload["gate4"]["acceptance_checks"][
                    "window_residual_spearman_values"
                ]
            ),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


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
        "files": {repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)} for path in files},
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = build_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)

    registry_result = {
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": payload["observed_only_lead"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "attribution": {
            "n_rows": payload["attribution"]["n_rows"],
            "raw_spearman": payload["attribution"]["raw"]["pooled"][
                "spearman_risk_intensity_to_pnl"
            ],
            "residual_spearman": payload["attribution"]["combined_residual"]["pooled"][
                "spearman_residual_risk_to_residual_pnl"
            ],
            "residual_bucket_summary": payload["attribution"]["combined_residual"][
                "pooled"
            ]["bucket_summary"],
        },
        "gate4": payload["gate4"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
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
            "change_type": payload["change_type"],
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
            "baseline_result_file": repo_rel(AGGREGATE_BASELINE),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "allowed_write_scope": ALLOWED_WRITE_SCOPE,
            "related_files": payload["related_files"],
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
                "n_rows": payload["attribution"]["n_rows"],
                "raw_spearman": payload["attribution"]["raw"]["pooled"][
                    "spearman_risk_intensity_to_pnl"
                ],
                "residual_spearman": payload["attribution"]["combined_residual"][
                    "pooled"
                ]["spearman_residual_risk_to_residual_pnl"],
                "residual_bucket_summary": payload["attribution"]["combined_residual"][
                    "pooled"
                ]["bucket_summary"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
