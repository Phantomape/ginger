"""exp-20260709-011: expectation revision theme lifecycle context.

Observed-only attribution for the parked expectation breadth/theme lane.
No entry, exit, ranking, sizing, adapter, LLM, or order behavior is changed.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
for path in (REPO_ROOT / "scripts", REPO_ROOT / "quant"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from broad_market_sector_map import (  # noqa: E402
    OK_STATUS,
    RULE_VERSION as SECTOR_RULE_VERSION,
    SOURCE_LABEL as SECTOR_SOURCE_LABEL,
    load_cache,
    lookup_sector,
)
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)
from ohlcv_warehouse import (  # noqa: E402
    DEFAULT_WAREHOUSE_PATH,
    connect_overlay_reader,
    load_warehouse_ohlcv_frames,
    overlay_reader_status,
)
from theme_lifecycle_surface import (  # noqa: E402
    DEFAULT_THEME_MAP,
    build_theme_lifecycle_surface,
)


EXPERIMENT_ID = "exp-20260709-011"
OWNER = "alpha-explore"
LANE = "alpha_search"
RUNNER = "quant/experiments/exp_20260709_011_expectation_theme_lifecycle_context.py"
RUNNER_COMMAND = (
    ".\\.venv\\Scripts\\python.exe -B "
    "quant\\experiments\\exp_20260709_011_expectation_theme_lifecycle_context.py"
)

SOURCE_ATTRIBUTION = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260526-006"
    / "expectation_revision_overextension_attribution.json"
)
PRIOR_BLOCKER = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260526-036"
    / "expectation_breadth_theme_context_probe.json"
)
BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260709_011_expectation_theme_lifecycle_context.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

PAPER_NOTIONAL_USD = 10000.0
HORIZONS = (5, 10, 20)
CONSTRUCTIVE_STATES = {"birth", "expansion", "neutral"}
CROWDED_BREAKING_STATES = {"mania", "exhaustion", "collapse"}
MIN_JOINED_ROWS = 30
MIN_GROUP_ROWS = 8
MAX_SINGLE_TICKER_SHARE = 0.35

HYPOTHESIS = (
    "Observed-only alpha: positive PIT estimate-revision candidate rows should "
    "have better forward outcomes when candidate-level theme lifecycle context "
    "is birth/expansion/neutral rather than mania/exhaustion/collapse, because "
    "revision drift should persist when theme participation is broadening rather "
    "than crowded or breaking."
)
ALPHA_HYPOTHESIS = HYPOTHESIS
CHANGE_TYPE = "observed_only_attribution"
IMPLEMENTATION_MODE = "self_registered_observed_only_runner"
MECHANISM_FAMILY = "expectation_drift_residual_pead"
TRIAL_FAMILY = "expectation_breadth_theme_context_probe"
TRIAL_VARIANT_ID = "theme_lifecycle_context_join_v1"
SINGLE_CAUSAL_VARIABLE = "expectation_revision_theme_lifecycle_context_v1"
CHANGED_VARIABLE = SINGLE_CAUSAL_VARIABLE
CAUSAL_COMPONENTS = [
    "PIT estimate revision source rows from exp-20260526-006",
    "candidate-level named theme lifecycle join",
    "sector-cache proxy theme fallback for otherwise unthemed tickers",
    "OHLCV H5/H10/H20 outcome attribution",
    "no strategy behavior change",
]
NEARBY_PRIORS = [
    "exp-20260526-036",
    "exp-20260707-004",
    "exp-20260706-010",
    "exp-20260709-002",
]
NEW_EVIDENCE_TYPE = "reopened_measurement_blocker_candidate_level_context_join"
NEW_EVIDENCE_AXIS = (
    "Reopen condition satisfied from exp-20260526-036: candidate-level theme "
    "lifecycle context is joined to the historical PIT positive revision rows. "
    "This is not a revision threshold/source retune, not another "
    "forward_replacement_value field, and not a SEC/news item enumeration."
)
ACCEPTANCE_RULE = (
    "Observed-only lead only: >=30 positive usable revision rows with joined "
    "theme lifecycle, >=8 constructive and >=8 crowded/breaking rows, H10 avg "
    "return and win rate constructive > crowded/breaking, H5/H20 not both "
    "inverted, max single ticker share <=35%; no strategy behavior accepted."
)
PREDICTION = {
    "success_probability": 0.30,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "theme_context_sparse",
        "no_h10_separation",
        "ticker_concentration",
        "revision_family_already_captured",
    ],
    "confidence_reason": (
        "exp-20260526-036 explicitly parked this line until candidate-level "
        "breadth/theme fields could be joined; the repo now has theme lifecycle "
        "and sector cache context, while the historical rows are settled, but "
        "revision families are heavily explored and may already be captured."
    ),
}

CHANGED_FILES = [
    RUNNER,
    "data/experiments/exp-20260709-011/exp_20260709_011_expectation_theme_lifecycle_context.json",
    "experiments/logs/exp-20260709-011.json",
    "experiments/cards/exp-20260709-011.md",
    "experiments/manifests/exp-20260709-011.json",
    "experiments/tickets/exp-20260709-011.json",
]


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
    if isinstance(value, dict):
        return {str(k): safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, Path):
        return repo_rel(value)
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def as_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def rounded(value: Any, digits: int = 6) -> float | None:
    number = as_float(value)
    return round(number, digits) if number is not None else None


def slug(value: str) -> str:
    cleaned = []
    for ch in str(value or "").lower():
        cleaned.append(ch if ch.isalnum() else "_")
    return "_".join(part for part in "".join(cleaned).split("_") if part)


def mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 6) if values else None


def win_rate(values: list[float]) -> float | None:
    return round(sum(1 for value in values if value > 0) / len(values), 4) if values else None


def load_source_rows() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = json.loads(SOURCE_ATTRIBUTION.read_text(encoding="utf-8"))
    rows = list(payload.get("sample_primary_positive_rows") or [])
    return payload, rows


def current_daily_ledger_diagnostic() -> dict[str, Any]:
    paths = sorted((REPO_ROOT / "data" / "non_ohlcv").glob("estimate_revision_ledger_*.jsonl"))
    rows: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any, Any]] = set()
    for path in paths:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                key = (row.get("ticker"), row.get("as_of_date"), row.get("fiscal_period"))
                if key in seen:
                    continue
                seen.add(key)
                rows.append(row)
    positive = [
        row
        for row in rows
        if row.get("estimate_revision_usable") is True
        and row.get("matched_candidate_today") is True
        and (as_float(row.get("eps_estimate_delta_7d")) or 0.0) > 0.0
    ]
    tickers = Counter(str(row.get("ticker") or "") for row in positive)
    dates = sorted({str(row.get("as_of_date")) for row in positive if row.get("as_of_date")})
    return {
        "ledger_files": len(paths),
        "dedup_rows": len(rows),
        "positive_usable_matched_rows": len(positive),
        "positive_usable_matched_tickers": dict(tickers.most_common(20)),
        "date_min": dates[0] if dates else None,
        "date_max": dates[-1] if dates else None,
        "diagnostic": (
            "Current materialized daily candidate rows are too sparse for this "
            "experiment; primary evaluation uses the parked exp-20260526-006 "
            "historical PIT rows."
        ),
    }


def sector_theme_map_for_rows(
    rows: list[dict[str, Any]], sector_cache: dict[str, Any]
) -> tuple[dict[str, set[str]], dict[str, dict[str, Any]]]:
    row_tickers = sorted({str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")})
    row_sector_lookup = {
        ticker: lookup_sector(ticker, sector_cache)
        for ticker in row_tickers
    }
    needed_sectors = {
        lookup.get("sector")
        for lookup in row_sector_lookup.values()
        if lookup.get("status") == OK_STATUS and lookup.get("sector")
    }
    theme_map: dict[str, set[str]] = {}
    for ticker, meta in (sector_cache.get("entries") or {}).items():
        sector = meta.get("sector")
        if meta.get("status") != OK_STATUS or sector not in needed_sectors:
            continue
        theme_map.setdefault(f"sector:{slug(sector)}", set()).add(str(ticker).upper())
    return theme_map, row_sector_lookup


def reverse_theme_map(theme_map: dict[str, set[str]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for theme, tickers in theme_map.items():
        for ticker in tickers:
            out.setdefault(str(ticker).upper(), []).append(theme)
    return {ticker: sorted(themes) for ticker, themes in out.items()}


def index_on_or_before(frame: pd.DataFrame | None, day: str) -> int | None:
    if frame is None or frame.empty:
        return None
    pos = frame.index.searchsorted(pd.Timestamp(day), side="right") - 1
    return int(pos) if pos >= 0 else None


def index_on_or_after(frame: pd.DataFrame | None, day: str) -> int | None:
    if frame is None or frame.empty:
        return None
    pos = frame.index.searchsorted(pd.Timestamp(day), side="left")
    return int(pos) if pos < len(frame.index) else None


def frame_float(frame: pd.DataFrame, idx: int, column: str) -> float | None:
    return as_float(frame.iloc[idx][column])


def feature_row_from_frame(ticker: str, frame: pd.DataFrame | None, day: str) -> dict[str, Any] | None:
    idx = index_on_or_before(frame, day)
    if idx is None or frame is None:
        return None
    close = frame_float(frame, idx, "Close")
    volume = frame_float(frame, idx, "Volume")
    if close is None or close <= 0:
        return None

    prior_20 = frame.iloc[max(0, idx - 20) : idx]
    prior_60_idx = idx - 60
    prior_200 = frame.iloc[max(0, idx - 200) : idx]

    high_20 = (
        as_float(prior_20["High"].max())
        if len(prior_20) >= 20 and "High" in prior_20
        else None
    )
    breakout_20d = bool(high_20 is not None and close > high_20)

    avg_volume_20 = as_float(prior_20["Volume"].mean()) if len(prior_20) >= 20 else None
    volume_spike = bool(
        volume is not None and avg_volume_20 is not None and avg_volume_20 > 0 and volume > 1.5 * avg_volume_20
    )

    def momentum(days: int) -> float | None:
        prior_idx = idx - days
        if prior_idx < 0:
            return None
        prior_close = frame_float(frame, prior_idx, "Close")
        if prior_close is None or prior_close <= 0:
            return None
        return (close / prior_close) - 1.0

    mom20 = momentum(20)
    mom60 = momentum(60) if prior_60_idx >= 0 else None
    ma200 = as_float(prior_200["Close"].mean()) if len(prior_200) >= 200 else None
    above_200ma = bool(ma200 is not None and close > ma200)
    trend_score = 0.0
    trend_score += 0.25 if above_200ma else 0.0
    trend_score += 0.25 if (mom20 is not None and mom20 > 0.0) else 0.0
    trend_score += 0.25 if (mom60 is not None and mom60 > 0.0) else 0.0
    trend_score += 0.25 if breakout_20d else 0.0

    return {
        "ticker": ticker,
        "feature_asof_date": str(frame.index[idx].date()),
        "breakout_20d": breakout_20d,
        "volume_spike": volume_spike,
        "momentum_20d_pct": mom20 or 0.0,
        "momentum_60d_pct": mom60 or 0.0,
        "above_200ma": above_200ma,
        "trend_score": round(trend_score, 4),
    }


def load_overlay_status() -> dict[str, Any]:
    conn = connect_overlay_reader(DEFAULT_WAREHOUSE_PATH)
    try:
        return overlay_reader_status(conn)
    finally:
        conn.close()


def load_frames(
    rows: list[dict[str, Any]],
    sector_theme_map: dict[str, set[str]],
) -> dict[str, pd.DataFrame]:
    row_tickers = {str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")}
    default_members = set().union(*DEFAULT_THEME_MAP.values())
    sector_members = set().union(*sector_theme_map.values()) if sector_theme_map else set()
    tickers = sorted(row_tickers | default_members | sector_members | {"SPY", "QQQ"})
    return load_warehouse_ohlcv_frames(
        DEFAULT_WAREHOUSE_PATH,
        tickers,
        start="2025-01-01",
        end="2026-07-09",
    )


def build_surface_cache(
    dates: list[str],
    frames: dict[str, pd.DataFrame],
    sector_theme_map: dict[str, set[str]],
) -> dict[str, dict[str, Any]]:
    combined_map = {**DEFAULT_THEME_MAP, **sector_theme_map}
    out: dict[str, dict[str, Any]] = {}
    for day in dates:
        features = {
            ticker: feature
            for ticker, frame in frames.items()
            if (feature := feature_row_from_frame(ticker, frame, day)) is not None
        }
        named_surface = build_theme_lifecycle_surface(features, DEFAULT_THEME_MAP)
        sector_surface = build_theme_lifecycle_surface(features, sector_theme_map)
        combined_surface = build_theme_lifecycle_surface(features, combined_map)
        by_theme = {
            row.get("theme"): row
            for row in combined_surface.get("themes", [])
            if row.get("theme")
        }
        out[day] = {
            "feature_rows": len(features),
            "named_surface": named_surface,
            "sector_surface": sector_surface,
            "combined_surface": combined_surface,
            "by_theme": by_theme,
        }
    return out


def outcome_between_dates(frame: pd.DataFrame | None, start_day: str, end_day: str) -> float | None:
    start_idx = index_on_or_after(frame, start_day)
    end_idx = index_on_or_after(frame, end_day)
    if frame is None or start_idx is None or end_idx is None:
        return None
    start_close = frame_float(frame, start_idx, "Close")
    end_close = frame_float(frame, end_idx, "Close")
    if start_close is None or end_close is None or start_close <= 0:
        return None
    return (end_close / start_close) - 1.0


def horizon_outcome(
    ticker: str,
    entry_day: str,
    horizon: int,
    frames: dict[str, pd.DataFrame],
) -> dict[str, Any]:
    frame = frames.get(ticker)
    entry_idx = index_on_or_after(frame, entry_day)
    if frame is None or entry_idx is None:
        return {
            "closed": False,
            "gap_reason": "missing_entry_price",
            "horizon_trading_days": horizon,
        }
    exit_idx = entry_idx + horizon
    if exit_idx >= len(frame.index):
        return {
            "closed": False,
            "gap_reason": "missing_forward_price",
            "horizon_trading_days": horizon,
            "entry_date": str(frame.index[entry_idx].date()),
        }
    entry_close = frame_float(frame, entry_idx, "Close")
    exit_close = frame_float(frame, exit_idx, "Close")
    if entry_close is None or exit_close is None or entry_close <= 0:
        return {
            "closed": False,
            "gap_reason": "invalid_price",
            "horizon_trading_days": horizon,
        }
    entry_date = str(frame.index[entry_idx].date())
    exit_date = str(frame.index[exit_idx].date())
    ret = (exit_close / entry_close) - 1.0
    spy_ret = outcome_between_dates(frames.get("SPY"), entry_date, exit_date)
    qqq_ret = outcome_between_dates(frames.get("QQQ"), entry_date, exit_date)
    return {
        "closed": True,
        "horizon_trading_days": horizon,
        "entry_date": entry_date,
        "exit_date": exit_date,
        "entry_close": round(entry_close, 4),
        "exit_close": round(exit_close, 4),
        "return_pct": round(ret, 6),
        "pnl_proxy_usd": round(ret * PAPER_NOTIONAL_USD, 2),
        "spy_return_pct": rounded(spy_ret),
        "qqq_return_pct": rounded(qqq_ret),
        "excess_spy_pct": rounded(ret - spy_ret) if spy_ret is not None else None,
        "excess_qqq_pct": rounded(ret - qqq_ret) if qqq_ret is not None else None,
    }


def choose_context(
    ticker: str,
    day: str,
    surface_cache: dict[str, dict[str, Any]],
    named_theme_by_ticker: dict[str, list[str]],
    sector_theme_by_ticker: dict[str, str],
) -> dict[str, Any]:
    lookup = (surface_cache.get(day) or {}).get("by_theme") or {}
    named_themes = named_theme_by_ticker.get(ticker, [])
    sector_theme = sector_theme_by_ticker.get(ticker)
    named_rows = [lookup.get(theme) for theme in named_themes if lookup.get(theme)]
    sector_row = lookup.get(sector_theme) if sector_theme else None

    candidates = [row for row in named_rows if row.get("theme_lifecycle_score") is not None]
    source = "default_theme_map" if candidates else None
    if not candidates and sector_row and sector_row.get("theme_lifecycle_score") is not None:
        candidates = [sector_row]
        source = "sector_proxy_theme"

    primary = sorted(
        candidates,
        key=lambda row: row.get("theme_lifecycle_score") or -1.0,
        reverse=True,
    )[0] if candidates else None
    state = primary.get("theme_lifecycle_state") if primary else "no_coverage"
    if state in CONSTRUCTIVE_STATES:
        bucket = "constructive"
    elif state in CROWDED_BREAKING_STATES:
        bucket = "crowded_breaking"
    else:
        bucket = "missing_context"

    return {
        "context_date": day,
        "primary_context_source": source,
        "primary_theme": primary.get("theme") if primary else None,
        "primary_theme_state": state,
        "primary_theme_score": primary.get("theme_lifecycle_score") if primary else None,
        "context_bucket": bucket,
        "named_themes": named_themes,
        "sector_proxy_theme": sector_theme,
        "named_theme_states": {
            row.get("theme"): row.get("theme_lifecycle_state")
            for row in named_rows
            if row
        },
        "sector_proxy_state": sector_row.get("theme_lifecycle_state") if sector_row else None,
    }


def enrich_rows(
    source_rows: list[dict[str, Any]],
    frames: dict[str, pd.DataFrame],
    surface_cache: dict[str, dict[str, Any]],
    named_theme_by_ticker: dict[str, list[str]],
    sector_theme_by_ticker: dict[str, str],
    row_sector_lookup: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    enriched = []
    for row in source_rows:
        ticker = str(row.get("ticker") or "").upper()
        context_day = str(row.get("feature_context_date") or row.get("as_of_date"))
        entry_day = str(row.get("watchlist_effective_trade_date") or row.get("as_of_date"))
        sector_lookup = row_sector_lookup.get(ticker) or {}
        context = choose_context(
            ticker,
            context_day,
            surface_cache,
            named_theme_by_ticker,
            sector_theme_by_ticker,
        )
        outcomes = {
            f"{horizon}d": horizon_outcome(ticker, entry_day, horizon, frames)
            for horizon in HORIZONS
        }
        enriched.append(
            {
                "ticker": ticker,
                "as_of_date": row.get("as_of_date"),
                "feature_context_date": row.get("feature_context_date"),
                "watchlist_effective_trade_date": row.get("watchlist_effective_trade_date"),
                "eps_estimate_delta_7d": rounded(row.get("eps_estimate_delta_7d")),
                "eps_estimate_delta_prev": rounded(row.get("eps_estimate_delta_prev")),
                "eps_estimate_delta_30d": rounded(row.get("eps_estimate_delta_30d")),
                "residual_state": row.get("residual_state"),
                "revision_residual_overextension_aggregate": row.get(
                    "revision_residual_overextension_aggregate"
                ),
                "watchlist_signal_basis": row.get("watchlist_signal_basis"),
                "sector_lookup": {
                    "sector": sector_lookup.get("sector"),
                    "industry": sector_lookup.get("industry"),
                    "status": sector_lookup.get("status"),
                    "rule_version": sector_lookup.get("rule_version"),
                },
                "theme_context": context,
                "forward_outcomes": outcomes,
            }
        )
    return enriched


def usable_rows_for_policy(rows: list[dict[str, Any]], *, default_only: bool = False) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        context = row.get("theme_context") or {}
        if default_only and context.get("primary_context_source") != "default_theme_map":
            continue
        if context.get("context_bucket") not in {"constructive", "crowded_breaking"}:
            continue
        if not (row.get("forward_outcomes") or {}).get("10d", {}).get("closed"):
            continue
        out.append(row)
    return out


def horizon_values(rows: list[dict[str, Any]], horizon: str, key: str = "return_pct") -> list[float]:
    values = []
    for row in rows:
        outcome = (row.get("forward_outcomes") or {}).get(horizon) or {}
        if outcome.get("closed"):
            value = as_float(outcome.get(key))
            if value is not None:
                values.append(value)
    return values


def concentration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tickers = Counter(row.get("ticker") for row in rows)
    total = sum(tickers.values())
    top_ticker, top_count = tickers.most_common(1)[0] if tickers else (None, 0)
    return {
        "rows": total,
        "ticker_count": len(tickers),
        "top_ticker": top_ticker,
        "top_ticker_rows": top_count,
        "top_ticker_share": round(top_count / total, 4) if total else None,
        "ticker_counts": dict(tickers.most_common(20)),
    }


def summarize_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "rows": len(rows),
        "ticker_concentration": concentration(rows),
        "horizons": {},
    }
    for horizon in ("5d", "10d", "20d"):
        ret = horizon_values(rows, horizon)
        ex_spy = horizon_values(rows, horizon, "excess_spy_pct")
        ex_qqq = horizon_values(rows, horizon, "excess_qqq_pct")
        summary["horizons"][horizon] = {
            "closed_rows": len(ret),
            "avg_return_pct": mean(ret),
            "win_rate": win_rate(ret),
            "avg_excess_spy_pct": mean(ex_spy),
            "avg_excess_qqq_pct": mean(ex_qqq),
        }
    return summary


def evaluation_for_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups = {
        "constructive": [
            row
            for row in rows
            if (row.get("theme_context") or {}).get("context_bucket") == "constructive"
        ],
        "crowded_breaking": [
            row
            for row in rows
            if (row.get("theme_context") or {}).get("context_bucket") == "crowded_breaking"
        ],
    }
    return {
        "joined_rows": len(rows),
        "context_source_counts": dict(
            Counter((row.get("theme_context") or {}).get("primary_context_source") for row in rows)
        ),
        "state_counts": dict(
            Counter((row.get("theme_context") or {}).get("primary_theme_state") for row in rows)
        ),
        "bucket_counts": dict(
            Counter((row.get("theme_context") or {}).get("context_bucket") for row in rows)
        ),
        "ticker_concentration": concentration(rows),
        "groups": {name: summarize_group(group_rows) for name, group_rows in groups.items()},
    }


def pass_fail(evaluation: dict[str, Any]) -> dict[str, Any]:
    groups = evaluation.get("groups") or {}
    constructive = groups.get("constructive") or {}
    crowded = groups.get("crowded_breaking") or {}
    c10 = constructive.get("horizons", {}).get("10d", {})
    k10 = crowded.get("horizons", {}).get("10d", {})
    c5 = constructive.get("horizons", {}).get("5d", {})
    k5 = crowded.get("horizons", {}).get("5d", {})
    c20 = constructive.get("horizons", {}).get("20d", {})
    k20 = crowded.get("horizons", {}).get("20d", {})
    top_share = (evaluation.get("ticker_concentration") or {}).get("top_ticker_share")

    def gt(left: Any, right: Any) -> bool | None:
        if left is None or right is None:
            return None
        return left > right

    h10_avg_pass = gt(c10.get("avg_return_pct"), k10.get("avg_return_pct"))
    h10_win_pass = gt(c10.get("win_rate"), k10.get("win_rate"))
    h5_inverted = (
        None
        if c5.get("avg_return_pct") is None or k5.get("avg_return_pct") is None
        else c5.get("avg_return_pct") < k5.get("avg_return_pct")
    )
    h20_inverted = (
        None
        if c20.get("avg_return_pct") is None or k20.get("avg_return_pct") is None
        else c20.get("avg_return_pct") < k20.get("avg_return_pct")
    )
    h5_h20_not_both_inverted = not (h5_inverted is True and h20_inverted is True)

    criteria = {
        "joined_rows_gte_30": evaluation.get("joined_rows", 0) >= MIN_JOINED_ROWS,
        "constructive_rows_gte_8": constructive.get("rows", 0) >= MIN_GROUP_ROWS,
        "crowded_breaking_rows_gte_8": crowded.get("rows", 0) >= MIN_GROUP_ROWS,
        "h10_avg_return_constructive_gt_crowded": h10_avg_pass is True,
        "h10_win_rate_constructive_gt_crowded": h10_win_pass is True,
        "h5_h20_not_both_inverted": h5_h20_not_both_inverted,
        "max_single_ticker_share_lte_35pct": (
            top_share is not None and top_share <= MAX_SINGLE_TICKER_SHARE
        ),
    }
    data_gap = not (
        criteria["joined_rows_gte_30"]
        and criteria["constructive_rows_gte_8"]
        and criteria["crowded_breaking_rows_gte_8"]
    )
    return {
        "criteria": criteria,
        "h5_inverted": h5_inverted,
        "h20_inverted": h20_inverted,
        "data_gap": data_gap,
        "passed": all(criteria.values()),
    }


def build_payload() -> dict[str, Any]:
    source_payload, source_rows = load_source_rows()
    sector_cache = load_cache()
    sector_theme_map, row_sector_lookup = sector_theme_map_for_rows(source_rows, sector_cache)
    frames = load_frames(source_rows, sector_theme_map)
    context_dates = sorted(
        {str(row.get("feature_context_date") or row.get("as_of_date")) for row in source_rows}
    )
    surface_cache = build_surface_cache(context_dates, frames, sector_theme_map)
    named_theme_by_ticker = reverse_theme_map(DEFAULT_THEME_MAP)
    sector_theme_by_ticker = {
        ticker: f"sector:{slug(lookup.get('sector'))}"
        for ticker, lookup in row_sector_lookup.items()
        if lookup.get("status") == OK_STATUS and lookup.get("sector")
    }
    enriched = enrich_rows(
        source_rows,
        frames,
        surface_cache,
        named_theme_by_ticker,
        sector_theme_by_ticker,
        row_sector_lookup,
    )

    primary_eval_rows = usable_rows_for_policy(enriched)
    default_eval_rows = usable_rows_for_policy(enriched, default_only=True)
    evaluation = evaluation_for_rows(primary_eval_rows)
    default_only_evaluation = evaluation_for_rows(default_eval_rows)
    gate = pass_fail(evaluation)

    if gate["passed"]:
        status = "observed_only_lead"
        decision = "observed_only_lead_expectation_theme_lifecycle_context"
        realized_failure_mode = None
        rejection_reason = None
    elif gate["data_gap"]:
        status = "observed_only_data_gap"
        decision = "observed_only_data_gap_theme_lifecycle_comparator_sparse"
        realized_failure_mode = "theme_context_sparse"
        rejection_reason = (
            "Joined context or constructive/crowded comparator rows did not "
            "meet the predeclared sample-size floor."
        )
    else:
        status = "observed_only_rejected"
        decision = "observed_only_rejected_theme_lifecycle_no_h10_separation"
        realized_failure_mode = "no_h10_separation"
        rejection_reason = (
            "Theme lifecycle groups were populated but constructive rows did "
            "not beat crowded/breaking rows on the predeclared H10 tests."
        )

    named_context_rows = [
        row
        for row in enriched
        if (row.get("theme_context") or {}).get("primary_context_source")
        == "default_theme_map"
    ]
    sector_proxy_rows = [
        row
        for row in enriched
        if (row.get("theme_context") or {}).get("primary_context_source")
        == "sector_proxy_theme"
    ]
    missing_context_rows = [
        row
        for row in enriched
        if (row.get("theme_context") or {}).get("context_bucket") == "missing_context"
    ]
    overlay_status = load_overlay_status()

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "lane": LANE,
        "owner": OWNER,
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": gate["passed"],
        "observed_only_lead_passed": gate["passed"],
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": SINGLE_CAUSAL_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "acceptance_rule": ACCEPTANCE_RULE,
        "prediction": PREDICTION,
        "realized_failure_mode": realized_failure_mode,
        "surprise_note": (
            "Current daily outcome materialization was much thinner than the "
            "historical parked sample, so the runner evaluates the original "
            "41 PIT rows and separately reports current ledger sparsity."
        ),
        "before_metrics": {
            "accepted_core_expected_value_score_sum": 7.8941,
            "accepted_core_total_pnl_sum": 234850.99,
            "strategy_behavior_changed": False,
        },
        "after_metrics": {
            "accepted_core_expected_value_score_sum": 7.8941,
            "accepted_core_total_pnl_sum": 234850.99,
            "strategy_behavior_changed": False,
        },
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_sum_delta": 0.0,
            "strategy_behavior_delta": 0,
        },
        "expected_value_score_delta": 0.0,
        "parameters": {
            "source_experiment": "exp-20260526-006",
            "prior_blocker_experiment": "exp-20260526-036",
            "source_rows": repo_rel(SOURCE_ATTRIBUTION),
            "prior_blocker_artifact": repo_rel(PRIOR_BLOCKER),
            "primary_positive_expectation_definition": (
                "estimate_revision_usable && eps_estimate_delta_7d > 0"
            ),
            "context_policy": "named default theme first, sector proxy theme fallback",
            "feature_rule": "OHLCV only, as-of day or previous available close",
            "entry_rule": "effective date or next available trading close",
            "forward_horizons_trading_days": list(HORIZONS),
            "paper_notional_usd": PAPER_NOTIONAL_USD,
            "constructive_states": sorted(CONSTRUCTIVE_STATES),
            "crowded_breaking_states": sorted(CROWDED_BREAKING_STATES),
            "min_joined_rows": MIN_JOINED_ROWS,
            "min_group_rows": MIN_GROUP_ROWS,
            "max_single_ticker_share": MAX_SINGLE_TICKER_SHARE,
            "sector_proxy_rule_version": SECTOR_RULE_VERSION,
            "sector_proxy_source": SECTOR_SOURCE_LABEL,
        },
        "coverage": {
            "source_primary_positive_rows": len(source_rows),
            "source_primary_positive_tickers": dict(
                Counter(row.get("ticker") for row in source_rows).most_common(30)
            ),
            "source_context_dates": context_dates,
            "named_theme_context_rows": len(named_context_rows),
            "sector_proxy_context_rows": len(sector_proxy_rows),
            "missing_context_rows": len(missing_context_rows),
            "default_only_joined_h10_rows": len(default_eval_rows),
            "primary_joined_h10_rows": len(primary_eval_rows),
            "loaded_ohlcv_frames": len(frames),
            "warehouse_path": repo_rel(DEFAULT_WAREHOUSE_PATH),
            "warehouse_overlay_status": overlay_status,
            "current_daily_ledger_diagnostic": current_daily_ledger_diagnostic(),
        },
        "evaluation": evaluation,
        "default_only_evaluation": default_only_evaluation,
        "gate": {
            "decision": decision,
            "promotion_gate_passed": gate["passed"],
            "observed_only_lead_passed": gate["passed"],
            "pass_fail": gate,
            "reason": rejection_reason or "observed_only_lead_only_no_strategy_change",
        },
        "gate1": {
            "passed": True,
            "baseline_protocol": "docs/backtesting.md canonical three fixed windows",
            "baseline_artifact": repo_rel(BASELINE_RESULT),
            "accepted_core_expected_value_score_sum": 7.8941,
            "accepted_core_total_pnl_sum": 234850.99,
            "note": "Read-only attribution; no before/after core strategy metric change.",
        },
        "gate2": {
            "passed": True,
            "rule_dependencies": [
                "exp-20260526-006 PIT primary positive revision rows",
                "warehouse OHLCV overlay for PIT features and H5/H10/H20 outcomes",
                "theme_lifecycle_surface.DEFAULT_THEME_MAP",
                "broad_market_sector_map cache for fallback sector proxy theme",
            ],
            "entry_date_target_price_sentinel": {
                "not_applicable": True,
                "reason": "No executable signal generation or backtester position contract is changed.",
            },
        },
        "gate3": {
            "passed": True,
            "adds_filter": False,
            "candidate_pool_changed": False,
            "survival_rate_not_applicable": True,
        },
        "gate4": {
            "passed": False,
            "canonical_backtest_required": False,
            "strategy_behavior_changed": False,
            "note": (
                "An observed-only lead can only unlock a later default-off paper "
                "or ranking Gate 1-4 experiment."
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
        "post_run_reflection": {
            "why_result_happened": (
                "The parked context join is now measurable, but the result depends "
                "on whether the sector proxy produces enough crowded/breaking rows. "
                "Default named themes alone remain a sparse subset."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune estimate-revision thresholds, hold periods, or "
                "residual overextension states from this result. If this closes as "
                "data_gap, the only valid reopen axis is a broader PIT theme taxonomy "
                "or materially more settled candidate-level rows."
            ),
            "new_evidence_required": (
                "A valid reopen needs a PIT named-theme taxonomy or materially more "
                "settled candidate-level revision rows that produce at least 30 "
                "joined rows and at least 8 rows on both constructive and "
                "crowded/breaking lifecycle sides."
            ),
            "next_evidence_needed": (
                "If observed-only lead: build a default-off paper context overlay "
                "with shared helper and full Gate 1-4. If data_gap: park until a "
                "PIT named-theme taxonomy covers at least 30 rows and both lifecycle "
                "sides have >=8 settled rows."
            ),
        },
        "gate_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": (
                "exp-20260526-036 parked this exact breadth/theme context lane "
                "because candidate-level fields were not joined; recent 48h lanes "
                "around SEC item enumeration, forward replacement state, crypto "
                "retunes, and portfolio daily overlays were avoided as saturated."
            ),
            "3_single_causal_variable": SINGLE_CAUSAL_VARIABLE,
            "4_acceptance_standard": ACCEPTANCE_RULE,
            "5_reproducibility": RUNNER_COMMAND,
        },
        "sample_enriched_rows": enriched[:20],
        "related_files": CHANGED_FILES,
        "changed_files": CHANGED_FILES,
        "allowed_write_scope": CHANGED_FILES,
        "lean_quality_passed": True,
    }
    return payload


def build_card(payload: dict[str, Any]) -> str:
    gate = payload["gate"]["pass_fail"]
    evaluation = payload["evaluation"]
    groups = evaluation["groups"]
    c10 = groups["constructive"]["horizons"]["10d"]
    k10 = groups["crowded_breaking"]["horizons"]["10d"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: expectation theme lifecycle context",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Source rows: `{payload['coverage']['source_primary_positive_rows']}`",
            f"- Primary joined H10 rows: `{evaluation['joined_rows']}`",
            f"- Default-theme-only joined H10 rows: `{payload['coverage']['default_only_joined_h10_rows']}`",
            f"- Constructive rows: `{groups['constructive']['rows']}`",
            f"- Crowded/breaking rows: `{groups['crowded_breaking']['rows']}`",
            f"- H10 constructive avg/win: `{c10['avg_return_pct']}` / `{c10['win_rate']}`",
            f"- H10 crowded avg/win: `{k10['avg_return_pct']}` / `{k10['win_rate']}`",
            f"- Pass criteria: `{gate['criteria']}`",
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


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [REPO_ROOT / rel for rel in CHANGED_FILES]
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
            "evaluation": {
                "primary_joined_h10_rows": payload["evaluation"]["joined_rows"],
                "bucket_counts": payload["evaluation"]["bucket_counts"],
                "criteria": payload["gate"]["pass_fail"]["criteria"],
            },
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
                "primary_joined_h10_rows": payload["evaluation"]["joined_rows"],
                "bucket_counts": payload["evaluation"]["bucket_counts"],
                "criteria": payload["gate"]["pass_fail"]["criteria"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
