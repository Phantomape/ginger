"""exp-20260709-016: broad dispersion source-state router validation.

Read-only alpha validation. This is the stricter follow-up to the global
forward-row lead in exp-20260709-005:

1. join closed default-off forward replacement rows to the fixed broad
   dispersion/correlation state at entry time;
2. use only the chronological train segment to select sleeve/source cohorts
   where stock-picker state beats dead-chop state across cash/SPY/QQQ;
3. validate only those preselected source-state cohorts in the later holdout.

No strategy, adapter, ranking, sizing, exits, orders, LLM boundary, or paper
state is changed.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd


EXPERIMENT_ID = "exp-20260709-016"
OWNER = "alpha-explore"
SLUG = "broad_dispersion_source_state_router"
RUNNER = f"quant/experiments/exp_20260709_016_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for path in (QUANT_DIR, SCRIPTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from broad_dispersion_features import (  # noqa: E402
    FEATURES_RULE_VERSION,
    avg_pairwise_correlation,
    cross_sectional_dispersion,
    daily_returns,
    liquidity_mask,
)
from experiment_registry import persist_self_registered_result  # noqa: E402


DATA_DIR = REPO_ROOT / "data"
BASELINE_RESULT = (
    DATA_DIR / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
WAREHOUSE_MAIN = DATA_DIR / "warehouse" / "warehouse_main.sqlite"
WAREHOUSE_HOT = DATA_DIR / "warehouse" / "warehouse_main_hot.sqlite"
FORWARD_LEDGER = DATA_DIR / "paper_sleeves" / "forward_replacement_value.jsonl"

OUT_DIR = DATA_DIR / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260709_016_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Observed-only alpha validation: broad dispersion/correlation stock-picker "
    "state should be deployable only if it identifies default-off sleeve/source "
    "cohorts whose later closed forward replacement value beats dead-chop rows "
    "versus cash, SPY, and QQQ under a fixed chronological source-state router."
)
CHANGE_TYPE = "observed_only_forward_source_state_validation"
IMPLEMENTATION_MODE = "read_only_observed_forward_source_state_validation"
MECHANISM_FAMILY = "production_visible_default_off_forward_regime_state_attribution"
TRIAL_FAMILY = "broad_dispersion_source_state_router_forward_validation"
TRIAL_VARIANT_ID = "source_state_chronological_validation_v1"
CHANGED_VARIABLE = "broad_dispersion_source_state_router_forward_validation_v1"
NEW_EVIDENCE_TYPE = "new_gate_shape"
NEW_EVIDENCE_AXIS = (
    "New gate shape: fixed source-conditioned chronological train/validate "
    "router on closed forward replacement rows, distinct from global state "
    "attribution in exp-20260709-005 and historical core-entry admission in "
    "exp-20260709-013; no threshold or comparator retune."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260709-005",
    "exp-20260709-013",
    "exp-20260708-017",
    "exp-20260708-018",
]
CAUSAL_COMPONENTS = [
    "forward_replacement_value_ledger",
    "broad_dispersion_corr_state_tag",
    "source_conditioned_train_validate_router",
    "no_strategy_behavior_change",
]
OUTCOME_FIELDS = [
    "replacement_value_vs_cash_usd",
    "replacement_value_vs_spy_usd",
    "replacement_value_vs_qqq_usd",
]
PREDICTED_FAILURE_MODES = [
    "training_selects_no_source",
    "validation_sample_too_thin",
    "state_effect_not_source_stable",
    "forward_lead_overfit",
]
CONFIG = {
    "panel_start": "2026-03-01",
    "panel_end": "2026-07-08",
    "min_eligible_names": 300,
    "train_entry_date_before": "2026-06-01",
    "holdout_entry_date_on_or_after": "2026-06-01",
    "min_covered_rows": 20,
    "min_train_rows": 12,
    "min_holdout_rows": 6,
    "min_train_rows_per_source": 3,
    "min_train_top_rows_per_source": 1,
    "min_train_bottom_rows_per_source": 1,
    "min_holdout_selected_rows": 3,
    "min_holdout_selected_top_rows": 1,
    "max_single_ticker_share": 0.60,
    "state_rule": "quartiles of z(broad_dispersion) - z(avg_pairwise_correlation)",
    "source_key": "sleeve_key",
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path | str) -> str:
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


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def rounded(value: Any, digits: int = 6) -> float | None:
    out = as_float(value)
    return round(out, digits) if out is not None else None


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {}) or {}
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    drawdowns = [
        as_float(row.get("max_drawdown_pct"))
        for row in windows
        if as_float(row.get("max_drawdown_pct")) is not None
    ]
    return {
        "available": BASELINE_RESULT.exists(),
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": rounded(
            sum(as_float(row.get("expected_value_score")) or 0.0 for row in windows),
            4,
        ),
        "total_pnl": rounded(
            sum(as_float(row.get("total_pnl")) or 0.0 for row in windows), 2
        ),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": rounded(survived / generated, 6) if generated else None,
        "max_drawdown_pct_worst": rounded(max(drawdowns), 4) if drawdowns else None,
    }


def load_forward_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw: list[dict[str, Any]] = []
    complete: list[dict[str, Any]] = []
    if not FORWARD_LEDGER.exists():
        return raw, complete
    with FORWARD_LEDGER.open(encoding="utf-8-sig") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON in {FORWARD_LEDGER}:{line_no}") from exc
            raw.append(row)
            if str(row.get("status") or "").lower() != "enriched":
                continue
            if not str(row.get("entry_date") or "")[:10]:
                continue
            if not row.get("ticker") or not row.get("sleeve_key"):
                continue
            if all(as_float(row.get(field)) is not None for field in OUTCOME_FIELDS):
                complete.append(row)
    return raw, complete


def load_densest_panel(paths: list[Path]) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    chunks: list[pd.DataFrame] = []
    for path in paths:
        if not path.exists():
            continue
        con = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
        try:
            chunk = pd.read_sql_query(
                "select ticker, date, close, volume from ohlcv "
                "where date >= ? and date <= ? and close > 0",
                con,
                params=(CONFIG["panel_start"], CONFIG["panel_end"]),
            )
        finally:
            con.close()
        if chunk.empty:
            continue
        chunk["source"] = path.stem
        chunks.append(chunk)
    if not chunks:
        empty = pd.DataFrame()
        return empty, empty, {"source_dates": {}, "date_counts": {}, "source_by_date": {}}

    rows = pd.concat(chunks, ignore_index=True)
    rows["ticker"] = rows["ticker"].astype(str).str.upper()
    rows["date"] = rows["date"].astype(str).str.slice(0, 10)
    rows["close"] = pd.to_numeric(rows["close"], errors="coerce")
    rows["volume"] = pd.to_numeric(rows["volume"], errors="coerce").fillna(0.0)
    rows = rows[rows["close"] > 0].copy()
    rows["dollar"] = rows["close"] * rows["volume"]

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
    closes = selected.pivot(index="date", columns="ticker", values="close").sort_index()
    dollar = selected.pivot(index="date", columns="ticker", values="dollar").sort_index()
    metadata = {
        "source_dates": {
            str(source): int(count)
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


def build_features() -> tuple[pd.DataFrame, dict[str, Any]]:
    closes, dollar, metadata = load_densest_panel([WAREHOUSE_MAIN, WAREHOUSE_HOT])
    if closes.empty:
        return pd.DataFrame(), metadata
    mask = liquidity_mask(closes, dollar)
    returns = daily_returns(closes)
    frame = pd.DataFrame(
        {
            "broad_dispersion": cross_sectional_dispersion(returns, mask),
            "avg_pairwise_correlation": avg_pairwise_correlation(returns, mask),
            "eligible_count": mask.sum(axis=1),
        }
    )
    frame["feature_date"] = frame.index.astype(str)
    frame["warehouse_source"] = frame["feature_date"].map(metadata["source_by_date"])
    frame["warehouse_ticker_count"] = frame["feature_date"].map(metadata["date_counts"])
    return frame, metadata


def join_rows_to_features(
    rows: list[dict[str, Any]], features: pd.DataFrame
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if features.empty:
        return pd.DataFrame(), {
            "raw_complete_rows": len(rows),
            "covered_rows": 0,
            "uncovered_reason_counts": {"no_feature_frame": len(rows)},
            "uncovered_examples": [],
        }
    by_date = features.set_index("feature_date")
    joined: list[dict[str, Any]] = []
    uncovered: list[dict[str, Any]] = []
    reason_counts: Counter[str] = Counter()
    for row in rows:
        entry_date = str(row.get("entry_date") or "")[:10]
        reason = None
        feat = None
        if not entry_date:
            reason = "missing_entry_date"
        elif entry_date not in by_date.index:
            reason = "missing_feature_date"
        else:
            feat = by_date.loc[entry_date]
            if int(feat.get("eligible_count") or 0) < int(CONFIG["min_eligible_names"]):
                reason = "low_eligible_count"
            elif as_float(feat.get("broad_dispersion")) is None or as_float(
                feat.get("avg_pairwise_correlation")
            ) is None:
                reason = "missing_dispersion_or_correlation"
        if reason:
            reason_counts[reason] += 1
            if len(uncovered) < 12:
                uncovered.append(
                    {
                        "entry_date": entry_date,
                        "ticker": row.get("ticker"),
                        "sleeve_key": row.get("sleeve_key"),
                        "reason": reason,
                    }
                )
            continue
        assert feat is not None
        joined.append(
            {
                "decision_id": row.get("decision_id"),
                "entry_date": entry_date,
                "exit_date": str(row.get("exit_date") or "")[:10],
                "asof_date": str(row.get("asof_date") or "")[:10],
                "ticker": str(row.get("ticker") or "").upper(),
                "sleeve_key": str(row.get("sleeve_key") or "unknown"),
                "notional_usd": rounded(row.get("notional_usd"), 2),
                "replacement_value_vs_cash_usd": rounded(
                    row.get("replacement_value_vs_cash_usd"), 4
                ),
                "replacement_value_vs_spy_usd": rounded(
                    row.get("replacement_value_vs_spy_usd"), 4
                ),
                "replacement_value_vs_qqq_usd": rounded(
                    row.get("replacement_value_vs_qqq_usd"), 4
                ),
                "broad_dispersion": rounded(feat.get("broad_dispersion"), 8),
                "avg_pairwise_correlation": rounded(
                    feat.get("avg_pairwise_correlation"), 8
                ),
                "eligible_count": int(feat.get("eligible_count") or 0),
                "warehouse_source": feat.get("warehouse_source"),
                "warehouse_ticker_count": int(feat.get("warehouse_ticker_count") or 0),
            }
        )
    frame = pd.DataFrame(joined)
    return frame, {
        "raw_complete_rows": len(rows),
        "covered_rows": int(len(frame)),
        "coverage_rate": rounded(len(frame) / len(rows), 6) if rows else None,
        "uncovered_reason_counts": dict(sorted(reason_counts.items())),
        "uncovered_examples": uncovered,
    }


def add_state(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    out = frame.copy()
    dispersion = pd.to_numeric(out["broad_dispersion"], errors="coerce")
    corr = pd.to_numeric(out["avg_pairwise_correlation"], errors="coerce")
    disp_std = float(dispersion.std(ddof=0) or 0.0)
    corr_std = float(corr.std(ddof=0) or 0.0)
    out["dispersion_z"] = (
        (dispersion - float(dispersion.mean())) / disp_std if disp_std > 0 else 0.0
    )
    out["avg_corr_z"] = (corr - float(corr.mean())) / corr_std if corr_std > 0 else 0.0
    out["stock_picker_score"] = out["dispersion_z"] - out["avg_corr_z"]
    if len(out) >= 4:
        ranked = out["stock_picker_score"].rank(method="first")
        out["state_quartile"] = pd.qcut(
            ranked,
            4,
            labels=["dead_chop_q1", "low_mid_q2", "high_mid_q3", "stock_picker_q4"],
        ).astype(str)
    else:
        out["state_quartile"] = "insufficient_rows"
    return out


def value_summary(frame: pd.DataFrame, field: str) -> dict[str, Any]:
    if frame.empty or field not in frame:
        values = pd.Series(dtype=float)
    else:
        values = pd.to_numeric(frame[field], errors="coerce").dropna()
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
        "sum_usd": rounded(values.sum(), 2),
        "mean_usd": rounded(values.mean(), 4),
        "median_usd": rounded(values.median(), 4),
        "win_rate": rounded(float((values > 0).mean()), 6),
        "min_usd": rounded(values.min(), 4),
        "max_usd": rounded(values.max(), 4),
    }


def outcome_block(frame: pd.DataFrame) -> dict[str, Any]:
    return {field: value_summary(frame, field) for field in OUTCOME_FIELDS}


def max_single_ticker_share(frame: pd.DataFrame) -> float | None:
    if frame.empty:
        return None
    counts = frame["ticker"].fillna("missing").astype(str).value_counts()
    return rounded(float(counts.max() / len(frame)), 6) if len(frame) else None


def source_summary(source: str, frame: pd.DataFrame) -> dict[str, Any]:
    top = frame[frame["state_quartile"] == "stock_picker_q4"]
    bottom = frame[frame["state_quartile"] == "dead_chop_q1"]
    top_outcomes = outcome_block(top)
    bottom_outcomes = outcome_block(bottom)
    diffs: dict[str, Any] = {}
    failures: list[str] = []
    if len(frame) < int(CONFIG["min_train_rows_per_source"]):
        failures.append(
            f"source_rows_below_min:{len(frame)}/{CONFIG['min_train_rows_per_source']}"
        )
    if len(top) < int(CONFIG["min_train_top_rows_per_source"]):
        failures.append(
            f"stock_picker_rows_below_min:{len(top)}/{CONFIG['min_train_top_rows_per_source']}"
        )
    if len(bottom) < int(CONFIG["min_train_bottom_rows_per_source"]):
        failures.append(
            f"dead_chop_rows_below_min:{len(bottom)}/{CONFIG['min_train_bottom_rows_per_source']}"
        )
    share = max_single_ticker_share(frame)
    if share is not None and share > float(CONFIG["max_single_ticker_share"]):
        failures.append(f"single_ticker_share:{share}>{CONFIG['max_single_ticker_share']}")
    for field in OUTCOME_FIELDS:
        top_mean = top_outcomes[field]["mean_usd"]
        bottom_mean = bottom_outcomes[field]["mean_usd"]
        diff = (
            rounded(float(top_mean) - float(bottom_mean), 4)
            if top_mean is not None and bottom_mean is not None
            else None
        )
        diffs[field] = {
            "stock_picker_minus_dead_chop_mean_usd": diff,
            "stock_picker_mean_positive": top_mean is not None and top_mean > 0,
            "stock_picker_beats_dead_chop": diff is not None and diff > 0,
        }
        if diff is None or diff <= 0:
            failures.append(f"{field}_top_not_above_bottom")
        if top_mean is None or top_mean <= 0:
            failures.append(f"{field}_top_not_positive")
    return {
        "source": source,
        "rows": int(len(frame)),
        "stock_picker_rows": int(len(top)),
        "dead_chop_rows": int(len(bottom)),
        "max_single_ticker_share": share,
        "ticker_counts": {
            str(key): int(value)
            for key, value in frame["ticker"].fillna("missing").value_counts().sort_index().items()
        },
        "entry_dates": sorted({str(value) for value in frame["entry_date"].dropna()}),
        "all": outcome_block(frame),
        "stock_picker_q4": top_outcomes,
        "dead_chop_q1": bottom_outcomes,
        "state_diffs": diffs,
        "passes_train_gate": not failures,
        "failed_reasons": failures,
    }


def summarize_sources(frame: pd.DataFrame) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    if frame.empty:
        return summaries
    for source, group in frame.groupby("sleeve_key"):
        summaries.append(source_summary(str(source), group.copy()))
    summaries.sort(
        key=lambda item: (
            not item["passes_train_gate"],
            -(item["stock_picker_q4"]["replacement_value_vs_cash_usd"]["mean_usd"] or -999999),
            item["source"],
        )
    )
    return summaries


def aggregate_frame(label: str, frame: pd.DataFrame) -> dict[str, Any]:
    return {
        "label": label,
        "rows": int(len(frame)),
        "source_counts": {
            str(key): int(value)
            for key, value in frame["sleeve_key"].fillna("missing").value_counts().sort_index().items()
        }
        if not frame.empty
        else {},
        "state_quartile_counts": {
            str(key): int(value)
            for key, value in frame["state_quartile"].fillna("missing").value_counts().sort_index().items()
        }
        if not frame.empty
        else {},
        "ticker_counts": {
            str(key): int(value)
            for key, value in frame["ticker"].fillna("missing").value_counts().sort_index().items()
        }
        if not frame.empty
        else {},
        "max_single_ticker_share": max_single_ticker_share(frame),
        "outcomes": outcome_block(frame),
    }


def build_validation(scored: pd.DataFrame) -> dict[str, Any]:
    if scored.empty:
        return {
            "validation_passed": False,
            "failed_reasons": ["no_scored_rows"],
            "selected_sources_from_train": [],
        }
    train = scored[scored["entry_date"] < CONFIG["train_entry_date_before"]].copy()
    holdout = scored[
        scored["entry_date"] >= CONFIG["holdout_entry_date_on_or_after"]
    ].copy()
    train_sources = summarize_sources(train)
    selected = [row["source"] for row in train_sources if row["passes_train_gate"]]
    selected_set = set(selected)
    holdout_selected = holdout[holdout["sleeve_key"].isin(selected_set)].copy()
    holdout_selected_top = holdout_selected[
        holdout_selected["state_quartile"] == "stock_picker_q4"
    ].copy()
    holdout_selected_bottom = holdout_selected[
        holdout_selected["state_quartile"] == "dead_chop_q1"
    ].copy()

    failures: list[str] = []
    if len(scored) < int(CONFIG["min_covered_rows"]):
        failures.append(f"covered_rows_below_min:{len(scored)}/{CONFIG['min_covered_rows']}")
    if len(train) < int(CONFIG["min_train_rows"]):
        failures.append(f"train_rows_below_min:{len(train)}/{CONFIG['min_train_rows']}")
    if len(holdout) < int(CONFIG["min_holdout_rows"]):
        failures.append(f"holdout_rows_below_min:{len(holdout)}/{CONFIG['min_holdout_rows']}")
    if not selected:
        failures.append("training_selects_no_source")
    if selected and len(holdout_selected) < int(CONFIG["min_holdout_selected_rows"]):
        failures.append(
            "holdout_selected_rows_below_min:"
            f"{len(holdout_selected)}/{CONFIG['min_holdout_selected_rows']}"
        )
    if selected and len(holdout_selected_top) < int(CONFIG["min_holdout_selected_top_rows"]):
        failures.append(
            "holdout_selected_stock_picker_rows_below_min:"
            f"{len(holdout_selected_top)}/{CONFIG['min_holdout_selected_top_rows']}"
        )

    holdout_top_outcomes = outcome_block(holdout_selected_top)
    holdout_bottom_outcomes = outcome_block(holdout_selected_bottom)
    holdout_diffs: dict[str, Any] = {}
    for field in OUTCOME_FIELDS:
        top_mean = holdout_top_outcomes[field]["mean_usd"]
        bottom_mean = holdout_bottom_outcomes[field]["mean_usd"]
        diff = (
            rounded(float(top_mean) - float(bottom_mean), 4)
            if top_mean is not None and bottom_mean is not None
            else None
        )
        holdout_diffs[field] = {
            "stock_picker_minus_dead_chop_mean_usd": diff,
            "stock_picker_mean_positive": top_mean is not None and top_mean > 0,
            "stock_picker_beats_dead_chop": diff is not None and diff > 0,
        }
        if selected:
            if top_mean is None or top_mean <= 0:
                failures.append(f"holdout_{field}_top_not_positive")
            if diff is None or diff <= 0:
                failures.append(f"holdout_{field}_top_not_above_bottom")

    return {
        "validation_passed": not failures,
        "failed_reasons": failures,
        "train": aggregate_frame("train", train),
        "holdout": aggregate_frame("holdout", holdout),
        "train_sources": train_sources,
        "selected_sources_from_train": selected,
        "holdout_selected_sources": aggregate_frame(
            "holdout_selected_sources", holdout_selected
        ),
        "holdout_selected_stock_picker_q4": aggregate_frame(
            "holdout_selected_stock_picker_q4", holdout_selected_top
        ),
        "holdout_selected_dead_chop_q1": aggregate_frame(
            "holdout_selected_dead_chop_q1", holdout_selected_bottom
        ),
        "holdout_state_diffs": holdout_diffs,
    }


def determine_decision(validation: dict[str, Any]) -> tuple[str, str, bool]:
    if validation.get("validation_passed"):
        return (
            "observed_only_positive_source_state_router_lead_not_policy_ready",
            "observed_only",
            True,
        )
    failures = validation.get("failed_reasons") or []
    if "training_selects_no_source" in failures:
        decision = "observed_only_rejected_no_train_selected_source_state_router"
    elif any(str(reason).startswith("holdout_selected_rows_below_min") for reason in failures):
        decision = "observed_only_rejected_selected_sources_no_holdout_support"
    else:
        decision = "observed_only_rejected_source_state_holdout_failed"
    return decision, "observed_only_rejected", False


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {}) or {}
    baseline = baseline_metrics()
    raw_rows, complete_rows = load_forward_rows()
    features, panel_metadata = build_features()
    joined, coverage = join_rows_to_features(complete_rows, features)
    scored = add_state(joined)
    validation = build_validation(scored)
    decision, status, lead_passed = determine_decision(validation)
    success_probability = float(
        (ticket.get("prediction") or {}).get("success_probability") or 0.24
    )
    actual_success = 1 if lead_passed else 0
    failure_modes = validation.get("failed_reasons", [])

    gate2_passed = bool(
        complete_rows
        and coverage["covered_rows"] >= int(CONFIG["min_covered_rows"])
        and not features.empty
    )
    gate4 = {
        "mode": "observed_only_source_conditioned_chronological_router_validation",
        "passed": lead_passed,
        "accepted_alpha": False,
        "observed_only_lead": lead_passed,
        "failed_reasons": failure_modes,
        "selected_sources_from_train": validation.get("selected_sources_from_train", []),
        "binding_acceptance_note": (
            "Observed-only validation only. A source-state router cannot affect "
            "entry, ranking, sizing, orders, or live/paper capital until it is "
            "implemented as a shared production/backtest policy and passes "
            "Gate 1-4 with an execution envelope."
        ),
    }
    if lead_passed:
        why = (
            "The train-selected source-state cohort remained positive in the "
            "later holdout, but this is only forward attribution and not an "
            "accepted policy."
        )
    elif "training_selects_no_source" in failure_modes:
        why = (
            "The global stock-picker forward lead was not source-stable. The "
            "train segment had enough covered rows, but no sleeve/source passed "
            "the fixed requirements of both stock-picker support and dead-chop "
            "contrast across cash, SPY, and QQQ."
        )
    else:
        why = (
            "The train segment selected at least one source, but the later "
            "holdout did not provide enough selected stock-picker rows or did "
            "not preserve positive cash/SPY/QQQ replacement value."
        )

    changed_files = [
        RUNNER,
        repo_rel(OUT_JSON),
        repo_rel(LOG_JSON),
        repo_rel(CARD_MD),
        repo_rel(MANIFEST_JSON),
        repo_rel(TICKET_JSON),
        repo_rel(REGISTRY_JSON),
    ]
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "accepted_measurement_repair": False,
        "observed_only_lead": lead_passed,
        "lane": "alpha_search",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "prior_trial_count": ticket.get("prior_trial_count", 0),
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "parameters": {
            **CONFIG,
            "features_rule_version": FEATURES_RULE_VERSION,
            "outcome_fields": OUTCOME_FIELDS,
        },
        "prediction": {
            "recorded_at": (ticket.get("prediction") or {}).get("recorded_at")
            or ticket.get("claimed_at")
            or ticket.get("created_at"),
            "success_probability": success_probability,
            "expected_ev_delta": (ticket.get("prediction") or {}).get("expected_ev_delta", 0.0),
            "expected_pnl_delta": (ticket.get("prediction") or {}).get(
                "expected_pnl_delta", 0.0
            ),
            "main_failure_modes": (ticket.get("prediction") or {}).get(
                "main_failure_modes", PREDICTED_FAILURE_MODES
            ),
            "confidence_reason": (ticket.get("prediction") or {}).get(
                "confidence_reason"
            )
            or (
                "The global forward-row state lead is plausible, but source-level "
                "chronological validation is stricter and likely sample limited."
            ),
        },
        "calibration": {
            "actual_decision": decision,
            "actual_success": actual_success,
            "predicted_success_probability": success_probability,
            "brier_score": rounded((success_probability - actual_success) ** 2, 6),
            "predicted_failure_modes": PREDICTED_FAILURE_MODES,
            "realized_failure_modes": failure_modes,
            "predicted_failure_mode_hit": bool(
                set(PREDICTED_FAILURE_MODES) & set(failure_modes)
            ),
            "surprise_note": (
                "Low surprise: source-conditioned chronological validation is much "
                "stricter than the global forward-row lead."
            ),
        },
        "gate1": {
            "passed": baseline.get("available") and baseline.get("window_count") == 3,
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": gate2_passed,
            "fields_checked": [
                "entry_date",
                "ticker",
                "sleeve_key",
                *OUTCOME_FIELDS,
                "broad_dispersion",
                "avg_pairwise_correlation",
            ],
            "raw_forward_rows": len(raw_rows),
            "complete_enriched_forward_rows": len(complete_rows),
            "feature_coverage": coverage,
            "panel_metadata": panel_metadata,
            "entry_date_target_price_note": (
                "Observed-only closed forward rows carry entry_date and realized "
                "replacement values. target_price is not an executable signal "
                "dependency for this runner."
            ),
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": len(raw_rows),
            "signals_survived": len(complete_rows),
            "survival_rate": rounded(len(complete_rows) / len(raw_rows), 6)
            if raw_rows
            else None,
            "note": "No executable filter or survival-changing policy was added.",
        },
        "gate4": gate4,
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "strategy_behavior_changed": False,
            "covered_forward_rows": coverage["covered_rows"],
            "train_rows": validation.get("train", {}).get("rows"),
            "holdout_rows": validation.get("holdout", {}).get("rows"),
            "selected_sources_from_train": validation.get(
                "selected_sources_from_train", []
            ),
            "failed_reasons": failure_modes,
        },
        "temporal_validation": validation,
        "analysis_rows": scored.sort_values(
            ["entry_date", "sleeve_key", "stock_picker_score"],
            ascending=[True, True, False],
        ).to_dict(orient="records")
        if not scored.empty
        else [],
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_exposed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "orders_changed": False,
            "paper_state_changed": False,
            "llm_decision_boundary_changed": False,
            "trade_enabled": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "scope": "read_only_forward_replacement_source_state_validation",
        },
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not rerun broad dispersion/correlation source-state validation "
                "on the same forward rows by changing split date, quartile "
                "definition, source key, min rows, concentration, comparator set, "
                "or response curve."
            ),
            "new_evidence_required": (
                "A valid retry needs materially more closed forward replacement "
                "rows with broad-state coverage, or a full shared "
                "production/backtest policy with an independently specified "
                "source-state router and Gate 1-4 evidence."
            ),
            "fingerprint_caveat": (
                "The reservation fingerprint classified the text as "
                "chop_forward_observer because the hypothesis contains dead-chop, "
                "but the actual data surface here is forward_replacement_value. "
                "The log records the real surface explicitly."
            ),
        },
        "rejection_reason": None if lead_passed else ";".join(failure_modes),
        "next_retry_requires": [
            "materially_more_closed_forward_replacement_rows_with_broad_state_coverage",
            "or_shared_policy_gate_1_4_with_independent_source_state_router",
            "no_split_quartile_source_key_min_rows_concentration_comparator_or_response_retune",
        ],
        "related_files": [
            repo_rel(FORWARD_LEDGER),
            repo_rel(BASELINE_RESULT),
            "quant/broad_dispersion_features.py",
            "experiments/logs/exp-20260709-005.json",
            "experiments/logs/exp-20260709-013.json",
            "experiments/logs/exp-20260708-017.json",
            "experiments/logs/exp-20260708-018.json",
        ],
        "changed_files": changed_files,
        "allowed_write_scope": ticket.get("allowed_write_scope", []),
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_broad_dispersion_features.py -q",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card_file": repo_rel(CARD_MD),
        "runner": RUNNER,
        "runner_command": RUNNER_COMMAND,
        "lean_quality_passed": True,
        "ticket_before": ticket,
    }
    return payload


def compact_log(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "accepted_measurement_repair",
        "observed_only_lead",
        "lane",
        "owner",
        "hypothesis",
        "alpha_hypothesis",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "changed_variable",
        "single_causal_variable",
        "causal_components",
        "prior_trial_count",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "parameters",
        "prediction",
        "calibration",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "temporal_validation",
        "production_impact",
        "post_run_reflection",
        "rejection_reason",
        "next_retry_requires",
        "related_files",
        "changed_files",
        "allowed_write_scope",
        "reproduction_commands",
        "lean_quality_passed",
        "artifact",
        "log",
    ]
    return {key: payload[key] for key in keys if key in payload}


def build_card(payload: dict[str, Any]) -> str:
    validation = payload["temporal_validation"]
    lines = [
        f"# {EXPERIMENT_ID}: broad dispersion source-state router",
        "",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Covered forward rows: `{payload['gate2']['feature_coverage']['covered_rows']}`",
        f"- Train / holdout rows: `{validation.get('train', {}).get('rows')}` / `{validation.get('holdout', {}).get('rows')}`",
        f"- Selected sources from train: `{', '.join(validation.get('selected_sources_from_train', [])) or 'none'}`",
        f"- Failed reasons: `{', '.join(validation.get('failed_reasons', [])) or 'none'}`",
        "- Strategy behavior changed: `false`",
        "",
        "## Train Source Gate",
        "",
        "| Source | Rows | Q4 | Q1 | Cash Q4-Q1 | SPY Q4-Q1 | QQQ Q4-Q1 | Pass | Failed |",
        "|---|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in validation.get("train_sources", []):
        diffs = row["state_diffs"]
        lines.append(
            f"| {row['source']} | {row['rows']} | {row['stock_picker_rows']} | "
            f"{row['dead_chop_rows']} | "
            f"{diffs['replacement_value_vs_cash_usd']['stock_picker_minus_dead_chop_mean_usd']} | "
            f"{diffs['replacement_value_vs_spy_usd']['stock_picker_minus_dead_chop_mean_usd']} | "
            f"{diffs['replacement_value_vs_qqq_usd']['stock_picker_minus_dead_chop_mean_usd']} | "
            f"{row['passes_train_gate']} | {'; '.join(row['failed_reasons']) or 'none'} |"
        )
    lines.extend(
        [
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
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
        FORWARD_LEDGER,
        BASELINE_RESULT,
        QUANT_DIR / "broad_dispersion_features.py",
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
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    write_json(LOG_JSON, compact_log(payload))
    write_text(CARD_MD, build_card(payload))
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result={
            "accepted": False,
            "accepted_alpha": False,
            "accepted_measurement_repair": False,
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "alpha_hypothesis": HYPOTHESIS,
            "change_type": CHANGE_TYPE,
            "implementation_mode": IMPLEMENTATION_MODE,
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": "moderate",
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
            "before_metrics": payload["before_metrics"],
            "after_metrics": payload["after_metrics"],
            "delta_metrics": payload["delta_metrics"],
            "temporal_validation_summary": {
                "covered_rows": payload["gate2"]["feature_coverage"]["covered_rows"],
                "train_rows": payload["temporal_validation"].get("train", {}).get("rows"),
                "holdout_rows": payload["temporal_validation"].get("holdout", {}).get("rows"),
                "selected_sources_from_train": payload["temporal_validation"].get(
                    "selected_sources_from_train", []
                ),
                "failed_reasons": payload["temporal_validation"].get(
                    "failed_reasons", []
                ),
            },
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "calibration": payload["calibration"],
            "novelty": (payload["ticket_before"] or {}).get("novelty"),
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
                "selected_sources_from_train": payload["temporal_validation"].get(
                    "selected_sources_from_train", []
                ),
                "failed_reasons": payload["temporal_validation"].get(
                    "failed_reasons", []
                ),
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
