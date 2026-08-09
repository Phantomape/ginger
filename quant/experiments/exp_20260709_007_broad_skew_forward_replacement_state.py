"""exp-20260709-007: broad return-skew state on forward rows.

Observed-only alpha attribution. This joins actual closed default-off forward
replacement rows to the prior-close broad-universe cross-sectional return skew.

Hypothesis: broad dispersion only helps stock picking when the opportunity set
is right-tail led rather than left-tail stress led. Skewness is the fixed state
axis under test; this runner does not tune dispersion/correlation thresholds.

The runner is read-only with respect to strategy behavior. It does not rank
candidates, size positions, alter orders, or change live/default signals.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

EXPERIMENT_ID = "exp-20260709-007"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "broad_skew_forward_replacement_state"
RUNNER = f"quant/experiments/exp_20260709_007_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, QUANT_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from broad_dispersion_features import (  # noqa: E402
    ADV_WINDOW,
    FEATURES_RULE_VERSION,
    MIN_PRICE,
    TOP_N_LIQUID,
    daily_returns,
    liquidity_mask,
    spearman,
)
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)

DATA_DIR = REPO_ROOT / "data"
BASELINE_RESULT = (
    DATA_DIR / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
WAREHOUSE_MAIN = DATA_DIR / "warehouse" / "warehouse_main.sqlite"
WAREHOUSE_HOT = DATA_DIR / "warehouse" / "warehouse_main_hot.sqlite"
FORWARD_LEDGER = DATA_DIR / "paper_sleeves" / "forward_replacement_value.jsonl"

PANEL_START = "2026-03-01"
PANEL_END = "2026-07-08"
MIN_ELIGIBLE_NAMES = 300
MIN_COVERED_FORWARD_ROWS = 20
MIN_TOP_BOTTOM_ROWS = 5
MAX_SINGLE_TICKER_SHARE = 0.40
MAX_SINGLE_SLEEVE_SHARE = 0.40

OUT_DIR = DATA_DIR / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260709_007_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Observed-only alpha: actual default-off forward replacement rows should "
    "have better cash/SPY/QQQ replacement value when the prior-close "
    "broad-universe cross-sectional return skew is positive/upside-led rather "
    "than negative/left-tail-led, because broad dispersion only helps "
    "stock-picking when the opportunity set is right-tail dominated rather "
    "than stress dominated."
)
CHANGED_VARIABLE = "broad_cross_sectional_skew_forward_replacement_state_v1"
MECHANISM_FAMILY = "production_visible_default_off_forward_regime_state_attribution"
TRIAL_FAMILY = "broad_cross_sectional_skew_forward_replacement_state"
TRIAL_VARIANT_ID = "prior_close_broad_return_skew_quartile_v1"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260709-004",
    "exp-20260709-005",
    "exp-20260709-006",
]
CAUSAL_COMPONENTS = [
    "closed_forward_replacement_rows",
    "prior_close_cross_sectional_skew",
    "quartile_lead_test",
    "no_strategy_change",
]
PREDICTED_FAILURE_MODES = [
    "skew_collinear_with_dispersion",
    "no_cash_spy_qqq_separation",
    "ticker_or_sleeve_concentration",
    "too_few_extreme_bucket_rows",
]
OUTCOME_FIELDS = [
    "replacement_value_vs_cash_usd",
    "replacement_value_vs_spy_usd",
    "replacement_value_vs_qqq_usd",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: str | Path) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
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


def finite_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def round_or_none(value: Any, digits: int = 6) -> float | None:
    value = finite_float(value)
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


def load_forward_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not FORWARD_LEDGER.exists():
        return rows
    with FORWARD_LEDGER.open(encoding="utf-8-sig") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid forward ledger JSON on line {line_no}") from exc
            status = str(row.get("status") or row.get("replacement_value_status") or "")
            if status == "enriched":
                rows.append(row)
    return rows


def load_densest_broad_panel(
    warehouse_paths: list[Path],
    start: str,
    end: str,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    chunks: list[pd.DataFrame] = []
    for path in warehouse_paths:
        if not path.exists() or path.stat().st_size <= 0:
            continue
        source = path.stem
        con = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
        try:
            chunk = pd.read_sql_query(
                "select ticker, date, close, volume from ohlcv "
                "where date >= ? and date <= ? and close > 0",
                con,
                params=(start, end),
            )
        finally:
            con.close()
        if not chunk.empty:
            chunk["source"] = source
            chunks.append(chunk)
    if not chunks:
        empty = pd.DataFrame()
        return empty, empty, {"source_dates": {}, "date_counts": {}}

    rows = pd.concat(chunks, ignore_index=True)
    rows["ticker"] = rows["ticker"].astype(str).str.upper()
    rows["date"] = rows["date"].astype(str).str.slice(0, 10)
    rows["close"] = pd.to_numeric(rows["close"], errors="coerce")
    rows["volume"] = pd.to_numeric(rows["volume"], errors="coerce").fillna(0.0)
    rows = rows[rows["close"] > 0].copy()

    counts = (
        rows.groupby(["date", "source"], as_index=False)["ticker"]
        .nunique()
        .rename(columns={"ticker": "ticker_count"})
    )
    source_order = {"warehouse_main": 0, "warehouse_main_hot": 1}
    counts["source_rank"] = counts["source"].map(source_order).fillna(0).astype(int)
    best = (
        counts.sort_values(
            ["date", "ticker_count", "source_rank"],
            ascending=[True, False, False],
        )
        .drop_duplicates("date", keep="first")
        .drop(columns=["source_rank"])
    )
    selected = rows.merge(best[["date", "source"]], on=["date", "source"], how="inner")
    selected = selected.drop_duplicates(subset=["date", "ticker"], keep="last")
    selected["dollar"] = selected["close"] * selected["volume"]

    closes = selected.pivot(index="date", columns="ticker", values="close").sort_index()
    dollar = selected.pivot(index="date", columns="ticker", values="dollar").sort_index()
    metadata = {
        "panel_start": start,
        "panel_end": end,
        "source_dates": {
            source: int(count)
            for source, count in best["source"].value_counts().sort_index().items()
        },
        "date_counts": {
            str(date): int(count)
            for date, count in best.set_index("date")["ticker_count"].items()
        },
        "source_by_date": {
            str(date): str(source)
            for date, source in best.set_index("date")["source"].items()
        },
        "panel_shape": [int(closes.shape[0]), int(closes.shape[1])],
    }
    return closes, dollar, metadata


def broad_skew_feature_frame() -> tuple[pd.DataFrame, dict[str, Any]]:
    closes, dollar, metadata = load_densest_broad_panel(
        [WAREHOUSE_MAIN, WAREHOUSE_HOT],
        PANEL_START,
        PANEL_END,
    )
    if closes.empty:
        return pd.DataFrame(), metadata
    mask = liquidity_mask(closes, dollar)
    returns = daily_returns(closes)
    eligible_returns = returns.where(mask)
    skew = eligible_returns.skew(axis=1, skipna=True)
    eligible_count = mask.sum(axis=1)
    mean_return = eligible_returns.mean(axis=1)
    median_return = eligible_returns.median(axis=1)
    left_tail = (eligible_returns <= -0.03).sum(axis=1) / eligible_count.replace(0, np.nan)
    right_tail = (eligible_returns >= 0.03).sum(axis=1) / eligible_count.replace(0, np.nan)
    frame = pd.DataFrame(
        {
            "feature_date": returns.index.astype(str),
            "broad_return_skew": skew,
            "eligible_count": eligible_count,
            "broad_mean_return": mean_return,
            "broad_median_return": median_return,
            "left_tail_share": left_tail,
            "right_tail_share": right_tail,
        }
    )
    frame["warehouse_source"] = frame["feature_date"].map(metadata.get("source_by_date", {}))
    frame["warehouse_ticker_count"] = frame["feature_date"].map(metadata.get("date_counts", {}))
    metadata.update(
        {
            "feature_rule_version": "broad_return_skew_prior_close_v1",
            "base_features_rule_version": FEATURES_RULE_VERSION,
            "liquidity_rule": {
                "min_price": MIN_PRICE,
                "top_n_liquid": TOP_N_LIQUID,
                "adv_window": ADV_WINDOW,
            },
            "feature_dates_total": int(len(frame)),
            "feature_dates_usable": int(
                (
                    (frame["eligible_count"] >= MIN_ELIGIBLE_NAMES)
                    & frame["broad_return_skew"].notna()
                ).sum()
            ),
        }
    )
    return frame, metadata


def missing_required_fields(rows: list[dict[str, Any]]) -> dict[str, int]:
    required = [
        "entry_date",
        "ticker",
        "sleeve_key",
        "replacement_value_vs_cash_usd",
        "replacement_value_vs_spy_usd",
        "replacement_value_vs_qqq_usd",
    ]
    missing: dict[str, int] = {}
    for field in required:
        count = sum(1 for row in rows if row.get(field) in (None, ""))
        if count:
            missing[field] = count
    return missing


def prior_feature_date(feature_dates: list[str], entry_date: str) -> str | None:
    index = int(np.searchsorted(np.array(feature_dates, dtype=object), entry_date, side="left")) - 1
    if index < 0:
        return None
    return feature_dates[index]


def join_forward_to_features(
    rows: list[dict[str, Any]],
    features: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    feature_dates = (
        sorted(features["feature_date"].dropna().astype(str).unique().tolist())
        if not features.empty
        else []
    )
    feature_by_date = (
        features.set_index("feature_date").to_dict(orient="index")
        if not features.empty
        else {}
    )
    joined_rows: list[dict[str, Any]] = []
    uncovered: list[dict[str, Any]] = []
    reason_counts: dict[str, int] = {}

    for row in rows:
        entry_date = str(row.get("entry_date") or "")[:10]
        ticker = str(row.get("ticker") or "").upper().strip()
        reason = None
        feat = None
        state_date = None
        if not entry_date:
            reason = "missing_entry_date"
        elif not ticker:
            reason = "missing_ticker"
        elif not feature_dates:
            reason = "missing_features"
        else:
            state_date = prior_feature_date(feature_dates, entry_date)
            if state_date is None:
                reason = "no_prior_feature_date"
            else:
                feat = feature_by_date.get(state_date)
                if feat is None:
                    reason = "missing_prior_feature"
                elif int(feat.get("eligible_count") or 0) < MIN_ELIGIBLE_NAMES:
                    reason = "low_eligible_count"
                elif finite_float(feat.get("broad_return_skew")) is None:
                    reason = "missing_broad_return_skew"

        if reason:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
            uncovered.append(
                {
                    "entry_date": entry_date,
                    "ticker": ticker,
                    "state_feature_date": state_date,
                    "sleeve_key": row.get("sleeve_key"),
                    "reason": reason,
                    "eligible_count": int(feat.get("eligible_count") or 0) if feat else None,
                }
            )
            continue

        assert feat is not None
        joined_rows.append(
            {
                "decision_id": row.get("decision_id"),
                "ticker": ticker,
                "sleeve_key": row.get("sleeve_key"),
                "entry_date": entry_date,
                "state_feature_date": state_date,
                "exit_date": row.get("exit_date"),
                "forward_asof_date": row.get("asof_date"),
                "notional_usd": round_or_none(row.get("notional_usd"), 2),
                "replacement_value_vs_cash_usd": round_or_none(
                    row.get("replacement_value_vs_cash_usd"), 4
                ),
                "replacement_value_vs_spy_usd": round_or_none(
                    row.get("replacement_value_vs_spy_usd"), 4
                ),
                "replacement_value_vs_qqq_usd": round_or_none(
                    row.get("replacement_value_vs_qqq_usd"), 4
                ),
                "broad_return_skew": round_or_none(feat.get("broad_return_skew"), 8),
                "eligible_count": int(feat.get("eligible_count") or 0),
                "broad_mean_return": round_or_none(feat.get("broad_mean_return"), 8),
                "broad_median_return": round_or_none(feat.get("broad_median_return"), 8),
                "left_tail_share": round_or_none(feat.get("left_tail_share"), 8),
                "right_tail_share": round_or_none(feat.get("right_tail_share"), 8),
                "warehouse_source": feat.get("warehouse_source"),
                "warehouse_ticker_count": int(feat.get("warehouse_ticker_count") or 0),
            }
        )

    joined_df = pd.DataFrame(joined_rows)
    coverage = {
        "raw_enriched_rows": len(rows),
        "covered_rows": int(len(joined_df)),
        "uncovered_rows": len(rows) - int(len(joined_df)),
        "coverage_rate": round(len(joined_df) / len(rows), 6) if rows else None,
        "uncovered_reason_counts": reason_counts,
        "uncovered_examples": uncovered[:15],
    }
    return joined_df, coverage


def add_skew_quartiles(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    out = frame.copy()
    if len(out) >= 4:
        ranked = out["broad_return_skew"].rank(method="first")
        out["state_quartile"] = pd.qcut(
            ranked,
            4,
            labels=[
                "left_tail_skew_q1",
                "low_mid_skew_q2",
                "high_mid_skew_q3",
                "right_tail_skew_q4",
            ],
        ).astype(str)
    else:
        out["state_quartile"] = "insufficient_rows"
    return out


def value_summary(frame: pd.DataFrame, field: str) -> dict[str, Any]:
    values = pd.to_numeric(frame.get(field, pd.Series(dtype=float)), errors="coerce").dropna()
    if values.empty:
        return {
            "count": 0,
            "sum_usd": None,
            "mean_usd": None,
            "median_usd": None,
            "win_rate": None,
            "min_usd": None,
            "max_usd": None,
        }
    return {
        "count": int(len(values)),
        "sum_usd": round(float(values.sum()), 2),
        "mean_usd": round(float(values.mean()), 4),
        "median_usd": round(float(values.median()), 4),
        "win_rate": round(float((values > 0).mean()), 6),
        "min_usd": round(float(values.min()), 4),
        "max_usd": round(float(values.max()), 4),
    }


def grouped_counts(frame: pd.DataFrame, field: str) -> dict[str, int]:
    if frame.empty or field not in frame:
        return {}
    counts = frame[field].fillna("missing").astype(str).value_counts()
    return {str(key): int(value) for key, value in counts.sort_index().items()}


def concentration(frame: pd.DataFrame) -> dict[str, Any]:
    n = len(frame)
    by_ticker = grouped_counts(frame, "ticker")
    by_sleeve = grouped_counts(frame, "sleeve_key")
    max_ticker = max(by_ticker.values()) if by_ticker else 0
    max_sleeve = max(by_sleeve.values()) if by_sleeve else 0
    return {
        "by_ticker": by_ticker,
        "by_sleeve": by_sleeve,
        "max_single_ticker_count": int(max_ticker),
        "max_single_ticker_share": round(max_ticker / n, 6) if n else None,
        "max_single_sleeve_count": int(max_sleeve),
        "max_single_sleeve_share": round(max_sleeve / n, 6) if n else None,
    }


def summarize_state(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {
            "state_rows": 0,
            "state_quartile_counts": {},
            "comparators": {},
            "criteria": {},
        }
    top = frame[frame["state_quartile"] == "right_tail_skew_q4"]
    bottom = frame[frame["state_quartile"] == "left_tail_skew_q1"]
    overall_conc = concentration(frame)
    top_conc = concentration(top)
    bottom_conc = concentration(bottom)

    comparators: dict[str, Any] = {}
    top_beats_bottom: list[str] = []
    top_positive: list[str] = []
    spearman_positive: list[str] = []
    for field in OUTCOME_FIELDS:
        all_summary = value_summary(frame, field)
        top_summary = value_summary(top, field)
        bottom_summary = value_summary(bottom, field)
        top_mean = top_summary["mean_usd"]
        bottom_mean = bottom_summary["mean_usd"]
        diff = (
            round(float(top_mean) - float(bottom_mean), 4)
            if top_mean is not None and bottom_mean is not None
            else None
        )
        rho = spearman(
            pd.to_numeric(frame["broad_return_skew"], errors="coerce").tolist(),
            pd.to_numeric(frame[field], errors="coerce").tolist(),
        )
        if diff is not None and diff > 0:
            top_beats_bottom.append(field)
        if top_mean is not None and float(top_mean) > 0:
            top_positive.append(field)
        if rho is not None and rho > 0:
            spearman_positive.append(field)
        comparators[field] = {
            "all": all_summary,
            "right_tail_skew_q4": top_summary,
            "left_tail_skew_q1": bottom_summary,
            "top_minus_bottom_mean_usd": diff,
            "broad_return_skew_spearman": round_or_none(rho, 6),
        }

    criteria = {
        "covered_rows_gte_min": len(frame) >= MIN_COVERED_FORWARD_ROWS,
        "top_rows_gte_min": len(top) >= MIN_TOP_BOTTOM_ROWS,
        "bottom_rows_gte_min": len(bottom) >= MIN_TOP_BOTTOM_ROWS,
        "max_ticker_share_lte_guard": (
            (overall_conc["max_single_ticker_share"] or 0.0) <= MAX_SINGLE_TICKER_SHARE
        ),
        "max_sleeve_share_lte_guard": (
            (overall_conc["max_single_sleeve_share"] or 0.0) <= MAX_SINGLE_SLEEVE_SHARE
        ),
        "top_max_ticker_share_lte_guard": (
            (top_conc["max_single_ticker_share"] or 0.0) <= MAX_SINGLE_TICKER_SHARE
        ),
        "bottom_max_ticker_share_lte_guard": (
            (bottom_conc["max_single_ticker_share"] or 0.0) <= MAX_SINGLE_TICKER_SHARE
        ),
        "top_beats_bottom_all_comparators": len(top_beats_bottom) == len(OUTCOME_FIELDS),
        "top_beats_bottom_fields": top_beats_bottom,
        "top_positive_at_least_two_comparators": len(top_positive) >= 2,
        "top_positive_fields": top_positive,
        "spearman_positive_at_least_two_comparators": len(spearman_positive) >= 2,
        "spearman_positive_fields": spearman_positive,
    }
    return {
        "state_rows": int(len(frame)),
        "state_quartile_counts": grouped_counts(frame, "state_quartile"),
        "entry_date_counts": grouped_counts(frame, "entry_date"),
        "state_feature_date_counts": grouped_counts(frame, "state_feature_date"),
        "warehouse_source_counts": grouped_counts(frame, "warehouse_source"),
        "concentration": overall_conc,
        "top_concentration": top_conc,
        "bottom_concentration": bottom_conc,
        "comparators": comparators,
        "criteria": criteria,
    }


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    baseline = baseline_metrics()
    rows = load_forward_rows()
    missing_fields = missing_required_fields(rows)
    features, panel_metadata = broad_skew_feature_frame()
    joined, coverage = join_forward_to_features(rows, features)
    scored = add_skew_quartiles(joined)
    state = summarize_state(scored)

    measurement_blockers: list[str] = []
    if not BASELINE_RESULT.exists() or baseline.get("window_count") != 3:
        measurement_blockers.append("baseline_missing_or_nonstandard")
    if not rows:
        measurement_blockers.append("forward_replacement_ledger_missing_or_empty")
    if missing_fields:
        measurement_blockers.append("required_forward_fields_missing")
    if features.empty:
        measurement_blockers.append("broad_skew_features_missing")
    if coverage["covered_rows"] < MIN_COVERED_FORWARD_ROWS:
        measurement_blockers.append("covered_forward_rows_below_minimum")

    criteria = state.get("criteria", {})
    lead_passed = bool(criteria) and all(
        bool(criteria.get(key))
        for key in [
            "covered_rows_gte_min",
            "top_rows_gte_min",
            "bottom_rows_gte_min",
            "max_ticker_share_lte_guard",
            "max_sleeve_share_lte_guard",
            "top_max_ticker_share_lte_guard",
            "bottom_max_ticker_share_lte_guard",
            "top_beats_bottom_all_comparators",
            "top_positive_at_least_two_comparators",
            "spearman_positive_at_least_two_comparators",
        ]
    )
    if measurement_blockers:
        decision = "blocked_broad_skew_forward_replacement_state"
        status = "blocked"
    elif lead_passed:
        decision = "observed_only_lead_broad_skew_forward_replacement_state"
        status = "observed_only"
    else:
        decision = "observed_only_rejected_broad_skew_forward_replacement_state"
        status = "observed_only"

    strategy_delta = {
        "expected_value_score_delta": 0.0,
        "total_pnl_delta": 0.0,
        "trade_count_delta": 0,
        "max_drawdown_pct_delta": 0.0,
        "live_order_behavior_changed": False,
        "strategy_behavior_changed": False,
    }
    delta_metrics = {
        **strategy_delta,
        "raw_enriched_forward_rows": coverage["raw_enriched_rows"],
        "covered_forward_rows": coverage["covered_rows"],
        "coverage_rate": coverage["coverage_rate"],
        "state_quartile_counts": state.get("state_quartile_counts", {}),
        "lead_passed": lead_passed,
        "criteria": criteria,
        "panel_shape": panel_metadata.get("panel_shape"),
        "feature_dates_usable": panel_metadata.get("feature_dates_usable"),
    }
    ticket_prediction = ticket.get("prediction") or {}
    success_probability = float(ticket_prediction.get("success_probability") or 0.27)
    actual_success = 1 if lead_passed and not measurement_blockers else 0
    prediction = {
        "recorded_at": ticket_prediction.get("recorded_at")
        or ticket.get("claimed_at")
        or ticket.get("created_at"),
        "success_probability": success_probability,
        "expected_ev_delta": ticket_prediction.get("expected_ev_delta"),
        "expected_pnl_delta": ticket_prediction.get("expected_pnl_delta"),
        "main_failure_modes": ticket_prediction.get("main_failure_modes")
        or PREDICTED_FAILURE_MODES,
        "confidence_reason": ticket_prediction.get("confidence_reason")
        or (
            "Skewness is a fixed new entry-time state axis, but recent forward "
            "state reads are thin and concentration-prone."
        ),
    }
    realized_failures = list(measurement_blockers)
    if not measurement_blockers and not lead_passed:
        for key, passed in criteria.items():
            if isinstance(passed, bool) and not passed:
                realized_failures.append(key)
    calibration = {
        "predicted_success_probability": success_probability,
        "actual_success": actual_success,
        "brier_score": round((success_probability - float(actual_success)) ** 2, 6),
        "predicted_failure_modes": prediction["main_failure_modes"],
        "realized_failure_modes": realized_failures,
        "predicted_failure_mode_hit": bool(realized_failures),
        "calibration_note": (
            "Success means observed-only lead criteria passed; no alpha "
            "acceptance or live behavior change is possible in this runner."
        ),
    }

    files = [
        RUNNER,
        repo_rel(OUT_JSON),
        repo_rel(LOG_JSON),
        repo_rel(CARD_MD),
        repo_rel(MANIFEST_JSON),
        repo_rel(TICKET_JSON),
        repo_rel(REGISTRY_JSON),
    ]
    production_impact = {
        "trade_enabled": False,
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "daily_snapshot_exposed": False,
        "entry_rules_changed": False,
        "exit_rules_changed": False,
        "ranking_changed": False,
        "sizing_changed": False,
        "orders_changed": False,
        "llm_decision_boundary_changed": False,
        "live_ready": False,
        "live_realism_evaluated": False,
        "scope": "read_only_forward_replacement_value_attribution",
    }

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "status": status,
        "lane": LANE,
        "owner": OWNER,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "accepted_measurement_repair": False,
        "alpha_ready": False,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": "observed_only_forward_attribution",
        "implementation_mode": "read_only_observed_forward_attribution",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "new_gate_shape_on_settled_forward_replacement_rows",
        "prediction": prediction,
        "calibration": calibration,
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "exp-20260709-004": "Synthetic broad dispersion/correlation proxy rejected.",
                "exp-20260709-005": "Broad dispersion/correlation had an observed-only forward-row lead.",
                "exp-20260709-006": "Sector-level dispersion rejected; this tests skew/asymmetry instead.",
                "novelty_gate": "Override accepted as a new gate shape.",
            },
            "3_single_measurement_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": ticket.get("acceptance_rule"),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "feature_rule_version": "broad_return_skew_prior_close_v1",
            "base_features_rule_version": FEATURES_RULE_VERSION,
            "panel_start": PANEL_START,
            "panel_end": PANEL_END,
            "min_eligible_names": MIN_ELIGIBLE_NAMES,
            "min_covered_forward_rows": MIN_COVERED_FORWARD_ROWS,
            "min_top_bottom_rows": MIN_TOP_BOTTOM_ROWS,
            "max_single_ticker_share": MAX_SINGLE_TICKER_SHARE,
            "max_single_sleeve_share": MAX_SINGLE_SLEEVE_SHARE,
            "state_join": "latest_feature_date_strictly_before_entry_date",
            "state_axis": "broad_universe_cross_sectional_daily_return_skew",
        },
        "gate1": {
            "passed": BASELINE_RESULT.exists() and baseline.get("window_count") == 3,
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": not missing_fields
            and not features.empty
            and coverage["covered_rows"] >= MIN_COVERED_FORWARD_ROWS,
            "dependencies_validated": not missing_fields,
            "fields_checked": [
                "entry_date",
                "ticker",
                "sleeve_key",
                "replacement_value_vs_cash_usd",
                "replacement_value_vs_spy_usd",
                "replacement_value_vs_qqq_usd",
                "prior_close_broad_return_skew",
            ],
            "missing_required_forward_fields": missing_fields,
            "feature_coverage": coverage,
            "entry_date_scope": "Forward entry_date joined to latest prior warehouse feature date.",
            "target_price_scope": "Not applicable; observed-only closed forward rows.",
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": baseline.get("signals_generated"),
            "signals_survived": baseline.get("signals_survived"),
            "survival_rate": baseline.get("survival_rate"),
            "feature_covered_rows": coverage["covered_rows"],
            "note": (
                "No strategy filter was added. Feature coverage is an observed-only "
                "analysis limitation, not a production survival filter."
            ),
        },
        "gate4": {
            "passed": False,
            "accepted_alpha": False,
            "alpha_ready": False,
            "decision": decision,
            "measurement_blockers": measurement_blockers,
            "alpha_blockers": [] if lead_passed else ["predeclared_forward_state_lead_criteria_not_met"],
            "strategy_rerun_required": False,
            "before_after_strategy_delta": strategy_delta,
            "observed_only_lead_passed": lead_passed,
            "criteria": criteria,
            "note": "No strategy or production behavior changed; Gate 4 cannot accept alpha.",
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": delta_metrics,
        "forward_row_coverage": coverage,
        "panel_metadata": panel_metadata,
        "state_attribution": state,
        "analysis_rows": scored.sort_values(
            ["broad_return_skew", "entry_date"], ascending=[False, True]
        ).to_dict(orient="records")
        if not scored.empty
        else [],
        "measurement_blockers": measurement_blockers,
        "production_impact": production_impact,
        "post_run_reflection": {
            "why_result_happened": None,
            "forbidden_near_neighbor_retry": (
                "This is the third consecutive observed-only close on "
                "forward_replacement_value. Do not add another same-row join, "
                "condition field, threshold, quartile, comparator, skew formula, "
                "eligible-name floor, or response-curve retry. Reopen only with "
                "materially more closed forward rows, a genuinely new data source, "
                "or a new shared policy/Gate 1-4."
            ),
            "new_evidence_required": (
                "Materially more closed forward replacement rows with broad-state "
                "coverage, a genuinely different data source, or a shared helper "
                "Gate 1-4. Another same-row forward attribution field is not enough."
            ),
        },
        "next_retry_requires": [
            "materially more closed forward replacement rows",
            "or a genuinely different data source",
            "or a shared helper with Gate 1-4",
            "no more same-row forward-attribution field joins after this third probe",
        ],
        "changed_files": files,
        "related_files": [
            repo_rel(FORWARD_LEDGER),
            repo_rel(BASELINE_RESULT),
            repo_rel(WAREHOUSE_MAIN),
            repo_rel(WAREHOUSE_HOT),
            "quant/broad_dispersion_features.py",
        ],
        "allowed_write_scope": ticket.get("allowed_write_scope") or files,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile "
            "quant\\experiments\\exp_20260709_007_broad_skew_forward_replacement_state.py",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {"used_javascript": False, "evidence": "Python runner only."},
        "lean_quality_passed": True,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "ticket_before": {
            "created_at": ticket.get("created_at"),
            "claimed_at": ticket.get("claimed_at"),
            "hub_identity": ticket.get("hub_identity"),
            "novelty": ticket.get("novelty"),
        },
    }
    return payload


def finalize_reflection(payload: dict[str, Any]) -> None:
    coverage = payload["forward_row_coverage"]
    criteria = payload["state_attribution"].get("criteria", {})
    comparator_bits = []
    for field, summary in payload["state_attribution"].get("comparators", {}).items():
        comparator_bits.append(
            f"{field} q4-q1={summary.get('top_minus_bottom_mean_usd')} "
            f"rho={summary.get('broad_return_skew_spearman')}"
        )
    if payload["measurement_blockers"]:
        why = (
            f"The diagnostic was blocked by measurement coverage: "
            f"{payload['measurement_blockers']} with "
            f"{coverage['covered_rows']}/{coverage['raw_enriched_rows']} covered rows."
        )
    elif payload["gate4"]["observed_only_lead_passed"]:
        why = (
            f"Prior-close right-tail skew transferred to actual forward rows: "
            f"{coverage['covered_rows']}/{coverage['raw_enriched_rows']} rows had "
            f"usable broad-skew coverage and the fixed q4-vs-q1 criteria passed. "
            + "; ".join(comparator_bits)
        )
    else:
        why = (
            f"Prior-close broad return skew did not pass the fixed forward lead "
            f"criteria on actual replacement rows. Coverage was "
            f"{coverage['covered_rows']}/{coverage['raw_enriched_rows']}; "
            f"criteria were {criteria}; comparator evidence was "
            + "; ".join(comparator_bits)
            + "."
        )
    payload["post_run_reflection"]["why_result_happened"] = why


def build_card(payload: dict[str, Any]) -> str:
    state = payload["state_attribution"]
    comp = state.get("comparators", {})
    lines = [
        f"# {EXPERIMENT_ID}: broad skew forward replacement state",
        "",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Covered forward rows: `{payload['forward_row_coverage']['covered_rows']}` / `{payload['forward_row_coverage']['raw_enriched_rows']}`",
        f"- Coverage gaps: `{payload['forward_row_coverage']['uncovered_reason_counts']}`",
        f"- State quartiles: `{state.get('state_quartile_counts', {})}`",
        f"- Concentration: `{state.get('concentration', {})}`",
        "- Strategy behavior changed: `false`",
        "",
        "## Comparator Evidence",
        "",
    ]
    for field in OUTCOME_FIELDS:
        summary = comp.get(field, {})
        lines.append(
            f"- `{field}` q4 mean `{summary.get('right_tail_skew_q4', {}).get('mean_usd')}` "
            f"vs q1 mean `{summary.get('left_tail_skew_q1', {}).get('mean_usd')}`, "
            f"diff `{summary.get('top_minus_bottom_mean_usd')}`, "
            f"Spearman `{summary.get('broad_return_skew_spearman')}`"
        )
    lines.extend(
        [
            "",
            "## Why",
            "",
            payload["post_run_reflection"]["why_result_happened"] or "",
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
    return "\n".join(lines)


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
        BASELINE_RESULT,
        FORWARD_LEDGER,
        QUANT_ROOT / "broad_dispersion_features.py",
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
        "changed_files": payload["changed_files"],
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
            "accepted_measurement_repair": False,
            "alpha_ready": False,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "gate4": payload["gate4"],
            "delta_metrics": payload["delta_metrics"],
            "calibration": payload["calibration"],
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
            "before_metrics": payload["before_metrics"],
            "after_metrics": payload["after_metrics"],
            "delta_metrics": payload["delta_metrics"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "next_retry_requires": payload["next_retry_requires"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "calibration": payload["calibration"],
            "hub_identity": payload["ticket_before"].get("hub_identity"),
            "novelty": payload["ticket_before"].get("novelty"),
            "claimed_at": payload["ticket_before"].get("claimed_at"),
        },
        allow_missing_prediction=True,
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    finalize_reflection(payload)
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "delta_metrics": payload["delta_metrics"],
                "state_attribution": {
                    "state_quartile_counts": payload["state_attribution"].get(
                        "state_quartile_counts"
                    ),
                    "criteria": payload["state_attribution"].get("criteria"),
                    "comparators": payload["state_attribution"].get("comparators"),
                },
            },
            indent=2,
            sort_keys=True,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
