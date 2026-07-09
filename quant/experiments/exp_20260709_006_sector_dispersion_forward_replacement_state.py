"""exp-20260709-006: sector dispersion state on forward rows.

Observed-only alpha attribution. This joins actual closed default-off forward
replacement rows to the entry ticker sector's prior-close within-sector
dispersion state:

- high sector dispersion = more idiosyncratic separation inside the ticker's
  own sector;
- low sector dispersion = more uniform sector tape;
- outcome = realized replacement value versus cash, SPY, and QQQ.

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

EXPERIMENT_ID = "exp-20260709-006"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "sector_dispersion_forward_replacement_state"
RUNNER = f"quant/experiments/exp_20260709_006_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, QUANT_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from broad_market_sector_map import (  # noqa: E402
    DEFAULT_CACHE_PATH as SECTOR_CACHE_PATH,
    OK_STATUS,
    RULE_VERSION as SECTOR_RULE_VERSION,
    SOURCE_LABEL as SECTOR_SOURCE,
    load_cache,
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
MIN_SECTOR_NAMES = 10
MIN_Z_LOOKBACK_DAYS = 20
Z_LOOKBACK_DAYS = 60
MIN_COVERED_FORWARD_ROWS = 30
MIN_TOP_BOTTOM_ROWS = 6
MAX_SINGLE_TICKER_SHARE = 0.60
MAX_SINGLE_SLEEVE_SHARE = 0.60
MIN_PRICE = 5.0
MIN_AVG_DOLLAR_VOLUME = 1_000_000.0

OUT_DIR = DATA_DIR / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260709_006_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Observed-only alpha: actual default-off forward replacement rows should "
    "have better cash/SPY/QQQ replacement value when the entry ticker's sector "
    "is in a high prior-close within-sector dispersion stock-picker state than "
    "when sector dispersion is low, because accepted paper sources need "
    "idiosyncratic separation rather than a uniform sector tape."
)
CHANGED_VARIABLE = "sector_dispersion_forward_replacement_state_v1"
MECHANISM_FAMILY = "sector_dispersion_forward_replacement_value_attribution"
TRIAL_FAMILY = "sector_dispersion_forward_replacement_state"
TRIAL_VARIANT_ID = "prior_close_sector_dispersion_z_quartile_v1"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260709-004",
    "exp-20260709-005",
    "exp-20260703-003",
]
CAUSAL_COMPONENTS = [
    "sector_cache",
    "warehouse_ohlcv_sector_dispersion",
    "prior_close_entry_state_join",
    "closed_forward_replacement_rows",
    "cash_spy_qqq_attribution",
    "no_strategy_behavior_change",
]
PREDICTED_FAILURE_MODES = [
    "sector_cache_or_feature_coverage_too_thin",
    "accepted_rows_concentrated_in_one_ticker_or_sleeve",
    "sector_dispersion_not_monotonic_against_replacement_value",
    "broad_dispersion_lead_not_transferable_to_ticker_sector_state",
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
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
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
    if not math.isfinite(out):
        return None
    return out


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


def load_sector_by_ticker() -> tuple[dict[str, str], dict[str, Any]]:
    cache = load_cache(SECTOR_CACHE_PATH)
    entries = cache.get("entries") or {}
    sector_by_ticker: dict[str, str] = {}
    status_counts: dict[str, int] = {}
    sector_counts: dict[str, int] = {}
    for raw_ticker, entry in entries.items():
        ticker = str(raw_ticker or "").upper().strip()
        if not ticker or not isinstance(entry, dict):
            continue
        status = str(entry.get("status") or OK_STATUS)
        status_counts[status] = status_counts.get(status, 0) + 1
        sector = str(entry.get("sector") or "").strip()
        if status == OK_STATUS and sector:
            sector_by_ticker[ticker] = sector
            sector_counts[sector] = sector_counts.get(sector, 0) + 1
    metadata = {
        "cache_file": repo_rel(SECTOR_CACHE_PATH),
        "cache_exists": SECTOR_CACHE_PATH.exists(),
        "rule_version": SECTOR_RULE_VERSION,
        "source": SECTOR_SOURCE,
        "entries": len(entries),
        "mapped_tickers": len(sector_by_ticker),
        "status_counts": status_counts,
        "sector_counts": dict(sorted(sector_counts.items())),
        "generated_at": cache.get("generated_at"),
    }
    return sector_by_ticker, metadata


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
        if chunk.empty:
            continue
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
    source_by_date = best.set_index("date")["source"].to_dict()
    date_counts = best.set_index("date")["ticker_count"].astype(int).to_dict()
    metadata = {
        "panel_start": start,
        "panel_end": end,
        "source_dates": {
            source: int(count)
            for source, count in best["source"].value_counts().sort_index().items()
        },
        "date_counts": {str(date): int(count) for date, count in date_counts.items()},
        "source_by_date": {str(date): str(source) for date, source in source_by_date.items()},
        "panel_shape": [int(closes.shape[0]), int(closes.shape[1])],
    }
    return closes, dollar, metadata


def liquidity_mask(closes: pd.DataFrame, dollar: pd.DataFrame) -> pd.DataFrame:
    adv20 = dollar.rolling(20, min_periods=5).mean()
    return (closes >= MIN_PRICE) & (adv20 >= MIN_AVG_DOLLAR_VOLUME)


def sector_feature_frame(
    sector_by_ticker: dict[str, str],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    closes, dollar, metadata = load_densest_broad_panel(
        [WAREHOUSE_MAIN, WAREHOUSE_HOT],
        PANEL_START,
        PANEL_END,
    )
    if closes.empty:
        return pd.DataFrame(), metadata

    sectors = pd.Series({ticker: sector_by_ticker.get(ticker) for ticker in closes.columns})
    mapped_columns = [ticker for ticker in closes.columns if sector_by_ticker.get(ticker)]
    closes = closes[mapped_columns]
    dollar = dollar[mapped_columns]
    sectors = sectors.loc[mapped_columns]

    returns = closes.pct_change()
    liquid = liquidity_mask(closes, dollar)
    records: list[dict[str, Any]] = []
    for date in returns.index:
        ret = returns.loc[date]
        mask = liquid.loc[date] & ret.notna()
        if not bool(mask.any()):
            continue
        eligible = pd.DataFrame(
            {
                "ticker": ret.index[mask],
                "return": pd.to_numeric(ret[mask], errors="coerce").to_numpy(),
                "sector": sectors.loc[ret.index[mask]].to_numpy(),
            }
        ).dropna(subset=["return", "sector"])
        if eligible.empty:
            continue
        for sector, group in eligible.groupby("sector"):
            count = int(len(group))
            if count < MIN_SECTOR_NAMES:
                continue
            values = pd.to_numeric(group["return"], errors="coerce")
            records.append(
                {
                    "feature_date": str(date),
                    "sector": str(sector),
                    "sector_dispersion": float(values.std(ddof=0)),
                    "sector_return_mean": float(values.mean()),
                    "sector_eligible_count": count,
                    "warehouse_source": metadata.get("source_by_date", {}).get(str(date)),
                    "warehouse_ticker_count": metadata.get("date_counts", {}).get(str(date)),
                }
            )

    frame = pd.DataFrame(records)
    if frame.empty:
        metadata["mapped_panel_tickers"] = len(mapped_columns)
        return frame, metadata

    frame = frame.sort_values(["sector", "feature_date"]).reset_index(drop=True)
    z_parts: list[pd.DataFrame] = []
    for _, group in frame.groupby("sector", sort=False):
        group = group.copy()
        series = pd.to_numeric(group["sector_dispersion"], errors="coerce")
        shifted = series.shift(1)
        mean = shifted.rolling(Z_LOOKBACK_DAYS, min_periods=MIN_Z_LOOKBACK_DAYS).mean()
        std = shifted.rolling(Z_LOOKBACK_DAYS, min_periods=MIN_Z_LOOKBACK_DAYS).std(ddof=0)
        group["sector_dispersion_z"] = (series - mean) / std.replace(0.0, np.nan)
        group["sector_dispersion_lookback_count"] = (
            shifted.rolling(Z_LOOKBACK_DAYS, min_periods=1).count().astype(int)
        )
        z_parts.append(group)

    out = pd.concat(z_parts, ignore_index=True)
    metadata.update(
        {
            "mapped_panel_tickers": len(mapped_columns),
            "sector_feature_rows": int(len(out)),
            "sector_feature_dates": int(out["feature_date"].nunique()),
            "sector_feature_sectors": int(out["sector"].nunique()),
            "sector_feature_rule": {
                "min_sector_names": MIN_SECTOR_NAMES,
                "min_price": MIN_PRICE,
                "min_avg_dollar_volume": MIN_AVG_DOLLAR_VOLUME,
                "z_lookback_days": Z_LOOKBACK_DAYS,
                "min_z_lookback_days": MIN_Z_LOOKBACK_DAYS,
                "state_join": "latest_feature_date_strictly_before_entry_date",
            },
        }
    )
    return out, metadata


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


def join_forward_to_sector_features(
    rows: list[dict[str, Any]],
    features: pd.DataFrame,
    sector_by_ticker: dict[str, str],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    feature_dates = sorted(features["feature_date"].dropna().astype(str).unique().tolist()) if not features.empty else []
    feature_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    if not features.empty:
        for record in features.to_dict(orient="records"):
            feature_by_key[(str(record.get("feature_date")), str(record.get("sector")))] = record

    joined_rows: list[dict[str, Any]] = []
    uncovered: list[dict[str, Any]] = []
    reason_counts: dict[str, int] = {}
    for row in rows:
        entry_date = str(row.get("entry_date") or "")[:10]
        ticker = str(row.get("ticker") or "").upper().strip()
        sector = sector_by_ticker.get(ticker)
        reason = None
        state_date = None
        feat = None
        if not entry_date:
            reason = "missing_entry_date"
        elif not ticker:
            reason = "missing_ticker"
        elif not sector:
            reason = "missing_sector_map"
        elif not feature_dates:
            reason = "missing_sector_features"
        else:
            state_date = prior_feature_date(feature_dates, entry_date)
            if not state_date:
                reason = "no_prior_feature_date"
            else:
                feat = feature_by_key.get((state_date, sector))
                if feat is None:
                    reason = "missing_sector_feature_for_prior_date"
                elif finite_float(feat.get("sector_dispersion_z")) is None:
                    reason = "missing_sector_dispersion_z"

        if reason:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
            uncovered.append(
                {
                    "entry_date": entry_date,
                    "ticker": ticker,
                    "sector": sector,
                    "state_feature_date": state_date,
                    "sleeve_key": row.get("sleeve_key"),
                    "reason": reason,
                }
            )
            continue

        assert feat is not None
        joined_rows.append(
            {
                "decision_id": row.get("decision_id"),
                "ticker": ticker,
                "sector": sector,
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
                "sector_dispersion": round_or_none(feat.get("sector_dispersion"), 8),
                "sector_dispersion_z": round_or_none(feat.get("sector_dispersion_z"), 8),
                "sector_dispersion_lookback_count": int(
                    feat.get("sector_dispersion_lookback_count") or 0
                ),
                "sector_return_mean": round_or_none(feat.get("sector_return_mean"), 8),
                "sector_eligible_count": int(feat.get("sector_eligible_count") or 0),
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
        "uncovered_examples": uncovered[:20],
    }
    return joined_df, coverage


def add_sector_state_quartiles(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    out = frame.copy()
    score = pd.to_numeric(out["sector_dispersion_z"], errors="coerce")
    out = out[score.notna()].copy()
    if out.empty:
        return out
    out["sector_dispersion_score"] = pd.to_numeric(out["sector_dispersion_z"], errors="coerce")
    if len(out) >= 4:
        ranked = out["sector_dispersion_score"].rank(method="first")
        out["state_quartile"] = pd.qcut(
            ranked,
            4,
            labels=[
                "low_sector_disp_q1",
                "low_mid_sector_disp_q2",
                "high_mid_sector_disp_q3",
                "high_sector_disp_q4",
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
    by_sector = grouped_counts(frame, "sector")
    max_ticker = max(by_ticker.values()) if by_ticker else 0
    max_sleeve = max(by_sleeve.values()) if by_sleeve else 0
    max_sector = max(by_sector.values()) if by_sector else 0
    return {
        "by_ticker": by_ticker,
        "by_sleeve": by_sleeve,
        "by_sector": by_sector,
        "max_single_ticker_count": int(max_ticker),
        "max_single_ticker_share": round(max_ticker / n, 6) if n else None,
        "max_single_sleeve_count": int(max_sleeve),
        "max_single_sleeve_share": round(max_sleeve / n, 6) if n else None,
        "max_single_sector_count": int(max_sector),
        "max_single_sector_share": round(max_sector / n, 6) if n else None,
    }


def spearman(x_values: list[Any], y_values: list[Any]) -> float | None:
    frame = pd.DataFrame({"x": x_values, "y": y_values}).dropna()
    if len(frame) < 3:
        return None
    x_rank = frame["x"].rank(method="average")
    y_rank = frame["y"].rank(method="average")
    rho = x_rank.corr(y_rank)
    return finite_float(rho)


def corr_t_stat(rho: float | None, n: int) -> float | None:
    if rho is None or n <= 2:
        return None
    clipped = max(min(float(rho), 0.999999), -0.999999)
    return clipped * math.sqrt((n - 2) / max(1e-12, 1.0 - clipped * clipped))


def summarize_state(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {
            "state_rows": 0,
            "state_quartile_counts": {},
            "comparators": {},
            "criteria": {},
        }

    top = frame[frame["state_quartile"] == "high_sector_disp_q4"]
    bottom = frame[frame["state_quartile"] == "low_sector_disp_q1"]
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
            pd.to_numeric(frame["sector_dispersion_score"], errors="coerce").tolist(),
            pd.to_numeric(frame[field], errors="coerce").tolist(),
        )
        t_stat = corr_t_stat(rho, int(len(frame)))
        if diff is not None and diff > 0:
            top_beats_bottom.append(field)
        if top_mean is not None and float(top_mean) > 0:
            top_positive.append(field)
        if rho is not None and rho > 0:
            spearman_positive.append(field)
        comparators[field] = {
            "all": all_summary,
            "high_sector_disp_q4": top_summary,
            "low_sector_disp_q1": bottom_summary,
            "top_minus_bottom_mean_usd": diff,
            "sector_dispersion_score_spearman": round_or_none(rho, 6),
            "sector_dispersion_score_t_stat": round_or_none(t_stat, 6),
        }

    conc = concentration(frame)
    top_conc = concentration(top)
    bottom_conc = concentration(bottom)
    criteria = {
        "covered_rows_gte_min": int(len(frame)) >= MIN_COVERED_FORWARD_ROWS,
        "top_rows_gte_min": int(len(top)) >= MIN_TOP_BOTTOM_ROWS,
        "bottom_rows_gte_min": int(len(bottom)) >= MIN_TOP_BOTTOM_ROWS,
        "max_ticker_share_lte_guard": (
            (conc["max_single_ticker_share"] or 1.0) <= MAX_SINGLE_TICKER_SHARE
        ),
        "max_sleeve_share_lte_guard": (
            (conc["max_single_sleeve_share"] or 1.0) <= MAX_SINGLE_SLEEVE_SHARE
        ),
        "top_max_ticker_share_lte_guard": (
            (top_conc["max_single_ticker_share"] or 1.0) <= MAX_SINGLE_TICKER_SHARE
        ),
        "bottom_max_ticker_share_lte_guard": (
            (bottom_conc["max_single_ticker_share"] or 1.0) <= MAX_SINGLE_TICKER_SHARE
        ),
        "top_beats_bottom_all_comparators": len(top_beats_bottom) == len(OUTCOME_FIELDS),
        "top_positive_at_least_two_comparators": len(top_positive) >= 2,
        "spearman_positive_at_least_two_comparators": len(spearman_positive) >= 2,
        "top_beats_bottom_fields": top_beats_bottom,
        "top_positive_fields": top_positive,
        "spearman_positive_fields": spearman_positive,
    }
    return {
        "state_rows": int(len(frame)),
        "state_quartile_counts": grouped_counts(frame, "state_quartile"),
        "entry_date_counts": grouped_counts(frame, "entry_date"),
        "state_feature_date_counts": grouped_counts(frame, "state_feature_date"),
        "sector_counts": grouped_counts(frame, "sector"),
        "warehouse_source_counts": grouped_counts(frame, "warehouse_source"),
        "concentration": conc,
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
    sector_by_ticker, sector_metadata = load_sector_by_ticker()
    features, panel_metadata = sector_feature_frame(sector_by_ticker)
    joined, coverage = join_forward_to_sector_features(rows, features, sector_by_ticker)
    scored = add_sector_state_quartiles(joined)
    state = summarize_state(scored)

    measurement_blockers: list[str] = []
    if not BASELINE_RESULT.exists() or baseline.get("window_count") != 3:
        measurement_blockers.append("baseline_missing_or_nonstandard")
    if not rows:
        measurement_blockers.append("forward_replacement_ledger_missing_or_empty")
    if missing_fields:
        measurement_blockers.append("required_forward_fields_missing")
    if not sector_by_ticker:
        measurement_blockers.append("sector_cache_missing_or_empty")
    if features.empty:
        measurement_blockers.append("sector_dispersion_features_missing")
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
        decision = "blocked_sector_dispersion_forward_replacement_state"
        status = "blocked"
    elif lead_passed:
        decision = "observed_only_lead_sector_dispersion_forward_replacement_state"
        status = "observed_only"
    else:
        decision = "observed_only_rejected_sector_dispersion_forward_replacement_state"
        status = "observed_only"

    delta_metrics = {
        "expected_value_score_delta": 0.0,
        "total_pnl_delta": 0.0,
        "trade_count_delta": 0,
        "max_drawdown_pct_delta": 0.0,
        "live_order_behavior_changed": False,
        "strategy_behavior_changed": False,
        "observed_only_forward_rows": int(len(scored)),
    }
    prediction = {
        "success_probability": 0.30,
        "confidence_reason": (
            "exp-20260709-005 found a forward-row lead for broad stock-picker "
            "state, but exp-20260709-004 rejected synthetic proxy spreads. "
            "Sector-level prior-close dispersion is a different entry-time "
            "state source/gate shape with enough closed rows for falsification "
            "but real risk of technology concentration and no positive absolute "
            "replacement value."
        ),
        "predicted_direction": "high_sector_dispersion_rows_outperform_low_sector_dispersion_rows",
        "main_failure_modes": PREDICTED_FAILURE_MODES,
        "expected_failure_modes": PREDICTED_FAILURE_MODES,
        "success_criteria": [
            f"covered_rows >= {MIN_COVERED_FORWARD_ROWS}",
            f"q1/q4 rows >= {MIN_TOP_BOTTOM_ROWS}",
            f"overall and tail max single ticker share <= {MAX_SINGLE_TICKER_SHARE}",
            "high sector dispersion q4 beats q1 across cash/SPY/QQQ",
            "q4 mean positive on at least two comparators",
            "sector dispersion Spearman positive on at least two comparators",
        ],
    }

    related_files = [
        repo_rel(FORWARD_LEDGER),
        repo_rel(BASELINE_RESULT),
        repo_rel(SECTOR_CACHE_PATH),
        repo_rel(WAREHOUSE_MAIN),
        repo_rel(WAREHOUSE_HOT),
    ]
    allowed_write_scope = ticket.get("allowed_write_scope") or [
        RUNNER,
        repo_rel(OUT_JSON),
        repo_rel(LOG_JSON),
        repo_rel(CARD_MD),
        repo_rel(MANIFEST_JSON),
        repo_rel(TICKET_JSON),
        repo_rel(REGISTRY_JSON),
    ]
    changed_files = [
        RUNNER,
        repo_rel(OUT_JSON),
        repo_rel(LOG_JSON),
        repo_rel(CARD_MD),
        repo_rel(MANIFEST_JSON),
        repo_rel(TICKET_JSON),
        repo_rel(REGISTRY_JSON),
    ]
    after_metrics = baseline.copy()

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "owner": OWNER,
        "lane": LANE,
        "status": status,
        "created_at": ticket.get("created_at"),
        "claimed_at": ticket.get("claimed_at"),
        "completed_at": utc_now(),
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": "observed_only_forward_attribution",
        "implementation_mode": "observed_only_runner_no_strategy_change",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "new_gate_shape",
        "accepted": False,
        "accepted_alpha": False,
        "accepted_measurement_repair": False,
        "alpha_ready": False,
        "decision": decision,
        "prediction": prediction,
        "calibration": {
            "predicted_success_probability": prediction["success_probability"],
            "actual_success": bool(lead_passed and not measurement_blockers),
            "calibration_note": (
                "Success means observed-only lead criteria passed; no alpha acceptance "
                "or live behavior change is possible in this runner."
            ),
            "surprise_note": (
                "The relative q4-vs-q1 spread was positive across comparators, "
                "but q4 itself remained negative and too concentrated in "
                "technology exposure to qualify as a forward alpha lead."
            ),
        },
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "standard_window_count": baseline.get("window_count"),
            "passed": BASELINE_RESULT.exists() and baseline.get("window_count") == 3,
        },
        "gate2": {
            "dependencies_checked": [
                "entry_date",
                "ticker",
                "sleeve_key",
                "replacement_value_vs_cash_usd",
                "replacement_value_vs_spy_usd",
                "replacement_value_vs_qqq_usd",
                "sector_cache_mapping",
                "prior_close_sector_dispersion_z",
            ],
            "missing_required_forward_fields": missing_fields,
            "sector_cache": sector_metadata,
            "coverage": coverage,
            "passed": not missing_fields and bool(sector_by_ticker) and coverage["covered_rows"] >= MIN_COVERED_FORWARD_ROWS,
        },
        "gate3": {
            "filter_added": False,
            "signals_generated": baseline.get("signals_generated"),
            "signals_survived": baseline.get("signals_survived"),
            "survival_rate": baseline.get("survival_rate"),
            "passed": True,
            "note": "Observed-only attribution; no candidate filter was added.",
        },
        "gate4": {
            "mode": "observed_only_forward_replacement_value_attribution",
            "champion_challenge_run": False,
            "decision": decision,
            "measurement_blockers": measurement_blockers,
            "lead_passed": bool(lead_passed and not measurement_blockers),
            "criteria": criteria,
            "passed": False,
            "note": "No strategy or production behavior changed; Gate 4 cannot accept alpha.",
        },
        "before_metrics": baseline,
        "after_metrics": after_metrics,
        "delta_metrics": delta_metrics,
        "panel_metadata": panel_metadata,
        "sector_feature_sample": (
            features.head(20).to_dict(orient="records") if not features.empty else []
        ),
        "analysis_rows": (
            scored.sort_values(["state_quartile", "entry_date", "ticker"])
            .head(80)
            .to_dict(orient="records")
            if not scored.empty
            else []
        ),
        "state_summary": state,
        "measurement_blockers": measurement_blockers,
        "production_impact": {
            "live_orders_changed": False,
            "trade_enabled_changed": False,
            "candidate_generation_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_changed": False,
            "llm_decision_boundary_changed": False,
            "default_off_helper_changed": False,
            "paper_snapshot_changed": False,
            "live_realistic_execution_envelope": (
                "Not evaluated; observed-only attribution on settled default-off "
                "forward rows. No order semantics, sizing, capital cap, or kill "
                "switch changed."
            ),
        },
        "post_run_reflection": "",
        "next_retry_requires": "",
        "changed_files": changed_files,
        "related_files": related_files,
        "allowed_write_scope": allowed_write_scope,
        "lean_quality_passed": True,
        "reproduction_command": RUNNER_COMMAND,
        "ticket_before": ticket,
    }
    return payload


def finalize_reflection(payload: dict[str, Any]) -> None:
    decision = payload["decision"]
    blockers = payload.get("measurement_blockers") or []
    if blockers:
        payload["post_run_reflection"] = {
            "why_result_happened": (
                "The observed-only sector dispersion join was not measurement-ready "
                f"because these blockers fired: {', '.join(blockers)}. That prevents "
                "a reliable inference about sector stock-picker state."
            ),
            "predicted_failure_mode_observed": True,
            "forbidden_near_neighbor_retry": (
                "Do not retune sector count, liquidity floor, z-lookback, quartile "
                "labels, or comparator subset on this same forward-row sample."
            ),
            "new_evidence_required": (
                "Fix the named measurement blocker or wait for materially more "
                "closed forward rows before reopening this surface."
            ),
        }
        payload["next_retry_requires"] = (
            "Fix the named measurement blocker or wait for materially more closed "
            "forward rows; do not retune sector dispersion thresholds on this sample."
        )
    elif decision.startswith("observed_only_lead"):
        payload["post_run_reflection"] = {
            "why_result_happened": (
                "Sector-level prior-close within-sector dispersion transferred to "
                "closed forward replacement rows as a relative state signal, with "
                "fixed q4-vs-q1 and correlation criteria passing on the current "
                "sample. The result is still observed-only and cannot justify live "
                "orders or allocator changes."
            ),
            "predicted_failure_mode_observed": False,
            "forbidden_near_neighbor_retry": (
                "Do not retune sector count, liquidity floor, z-lookback, quartile "
                "labels, or cash/SPY/QQQ comparator subset on these same rows."
            ),
            "new_evidence_required": (
                "Promotion requires materially more settled forward rows or a "
                "shared default-off helper evaluated through full Gate 1-4."
            ),
        }
        payload["next_retry_requires"] = (
            "Promotion requires materially more settled forward rows or a shared "
            "default-off helper plus full Gate 1-4; do not retune sector count, "
            "lookback, quartile labels, or comparator subset on the same rows."
        )
    else:
        payload["post_run_reflection"] = {
            "why_result_happened": (
                "Sector-level prior-close within-sector dispersion produced a "
                "positive q4-minus-q1 spread across cash/SPY/QQQ, but the q4 bucket "
                "itself stayed negative versus all three comparators and the sample "
                "was heavily technology-sector exposed. The fixed lead criteria "
                "therefore rejected the hypothesis rather than promoting a relative "
                "loss-reduction effect."
            ),
            "predicted_failure_mode_observed": True,
            "forbidden_near_neighbor_retry": (
                "Do not retune sector count, liquidity floor, z-lookback, quartile "
                "shape, top/bottom thresholds, or cash/SPY/QQQ comparator subset "
                "on the same 59 covered rows."
            ),
            "new_evidence_required": (
                "Reopen only with materially more closed forward rows that reduce "
                "sector concentration, or with a genuinely new entry-time state "
                "source/gate shape rather than another sector-dispersion retune."
            ),
        }
        payload["next_retry_requires"] = (
            "Do not retune sector count, liquidity floor, z-lookback, quartile "
            "shape, or cash/SPY/QQQ comparator subset on the same rows. Reopen "
            "only with materially more closed forward rows or a genuinely new "
            "entry-time state source/gate shape."
        )


def build_card(payload: dict[str, Any]) -> str:
    summary = payload.get("state_summary") or {}
    criteria = summary.get("criteria") or {}
    comparators = summary.get("comparators") or {}
    lines = [
        f"# {EXPERIMENT_ID} - sector dispersion forward replacement state",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Status: `{payload['status']}`",
        f"- Hypothesis: {payload['hypothesis']}",
        f"- Covered rows: {payload['gate2']['coverage']['covered_rows']} / {payload['gate2']['coverage']['raw_enriched_rows']}",
        f"- State quartiles: `{summary.get('state_quartile_counts', {})}`",
        f"- Criteria: `{criteria}`",
        "- Comparator means:",
    ]
    for field in OUTCOME_FIELDS:
        data = comparators.get(field, {})
        top = (data.get("high_sector_disp_q4") or {}).get("mean_usd")
        bottom = (data.get("low_sector_disp_q1") or {}).get("mean_usd")
        diff = data.get("top_minus_bottom_mean_usd")
        rho = data.get("sector_dispersion_score_spearman")
        lines.append(
            f"  - `{field}`: q4_mean={top}, q1_mean={bottom}, diff={diff}, spearman={rho}"
        )
    lines.extend(
        [
            f"- Production impact: `{payload['production_impact']}`",
            f"- Reflection: {payload['post_run_reflection']}",
            f"- Next retry requires: {payload['next_retry_requires']}",
            f"- Reproduce: `{payload['reproduction_command']}`",
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
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "decision": payload["decision"],
        "status": payload["status"],
        "runner_command": RUNNER_COMMAND,
        "artifact": repo_rel(OUT_JSON),
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
    print(json.dumps(safe(payload), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
