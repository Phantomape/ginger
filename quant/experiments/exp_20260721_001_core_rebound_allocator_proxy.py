"""exp-20260721-001: retrospective core-rebound allocator proxy scout.

This is intentionally a private, non-production replay.  Moomoo historical
capital-flow rows fetched after their flow dates are accepted only because the
user explicitly allowed a retrospective proxy.  They are not canonical PIT
evidence and this runner must not be used to promote or wire a live policy.

The experiment is deliberately narrow: one fixed complete-case candidate
cohort, two predeclared ranking arms, fixed horizons, and no parameter sweep.
Selections are fully constructed and frozen before any forward outcome is
read from the already-loaded OHLCV frames.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
for import_root in (str(REPO_ROOT), str(QUANT_DIR)):
    if import_root not in sys.path:
        sys.path.insert(0, import_root)

from filter import _BASE_WATCHLIST  # noqa: E402
from ohlcv_warehouse import (  # noqa: E402
    DEFAULT_WAREHOUSE_PATH,
    load_warehouse_ohlcv_frames,
)


EXPERIMENT_ID = "exp-20260721-001"
START_DATE = pd.Timestamp("2026-05-06")
END_DATE = pd.Timestamp("2026-07-20")
HISTORY_START = pd.Timestamp("2025-01-01")
HORIZONS = (1, 3, 5, 10)
PRIMARY_HORIZON = 10
ROUND_TRIP_COST = 0.0035
PAPER_NOTIONAL_USD = 4_000.0
BOOTSTRAP_SEED = 20_260_720
BOOTSTRAP_REPETITIONS = 10_000
COOLDOWN_SESSIONS = 10

ETF_EXCLUSIONS = frozenset({"GLD", "IAU", "IWM", "QQQ", "SLV", "SPY"})
UNIVERSE = tuple(sorted(set(_BASE_WATCHLIST) - ETF_EXCLUSIONS))
BENCHMARKS = ("SPY", "QQQ")

FLOW_PATH = REPO_ROOT / "data" / "non_ohlcv" / "moomoo_capital_flow_day" / "rows.jsonl"
FLOW_MANIFEST_PATH = FLOW_PATH.with_name("manifest.json")
OPTIONS_DIR = REPO_ROOT / "data" / "non_ohlcv"
OPTIONS_QUALITY_PATH = OPTIONS_DIR / "options_forward" / "options_collection_quality_gate.json"
DEFAULT_OUTPUT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / EXPERIMENT_ID
    / "exp_20260721_001_core_rebound_allocator_proxy.json"
)


def _finite_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _pct(value: float | None) -> float | None:
    return None if value is None or not math.isfinite(value) else round(100.0 * value, 8)


def _rounded(value: float | None, digits: int = 10) -> float | None:
    return None if value is None or not math.isfinite(value) else round(value, digits)


def _json_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rsi_wilder(close: pd.Series, period: int = 14) -> pd.Series:
    """Causal Wilder-style RSI, with no future observations in a row."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - 100.0 / (1.0 + rs)
    rsi = rsi.where(avg_loss.ne(0.0), 100.0)
    rsi = rsi.where(avg_gain.ne(0.0) | avg_loss.ne(0.0), 50.0)
    return rsi


def _build_causal_price_features(
    frames: dict[str, pd.DataFrame],
) -> tuple[
    pd.DataFrame,
    dict[tuple[str, pd.Timestamp], int],
    dict[tuple[str, pd.Timestamp], pd.Timestamp],
]:
    """Build signal-day-only features; no forward return is calculated here."""
    rows: list[pd.DataFrame] = []
    position_maps: dict[tuple[str, pd.Timestamp], int] = {}
    next_session_dates: dict[tuple[str, pd.Timestamp], pd.Timestamp] = {}
    for ticker in UNIVERSE:
        frame = frames.get(ticker)
        if frame is None or frame.empty:
            continue
        frame = frame.sort_index().copy()
        close = pd.to_numeric(frame["Close"], errors="coerce")
        volume = pd.to_numeric(frame["Volume"], errors="coerce")
        feature = pd.DataFrame(index=frame.index)
        feature["ticker"] = ticker
        feature["signal_close"] = close
        feature["rsi14"] = _rsi_wilder(close)
        feature["ret20"] = close / close.shift(20) - 1.0
        feature["dd60"] = close / close.rolling(60, min_periods=60).max() - 1.0
        # The signal-day dollar volume is not used in its own denominator.
        feature["prior_adv20_usd"] = (close * volume).shift(1).rolling(20, min_periods=20).mean()
        feature = feature.loc[(feature.index >= START_DATE) & (feature.index <= END_DATE)]
        rows.append(feature.reset_index(names="signal_date"))
        for index_position, day in enumerate(frame.index):
            position_maps[(ticker, pd.Timestamp(day))] = index_position
            if index_position + 1 < len(frame.index):
                next_session_dates[(ticker, pd.Timestamp(day))] = pd.Timestamp(
                    frame.index[index_position + 1]
                )

    if not rows:
        raise RuntimeError("No warehouse OHLCV feature rows were available for the fixed universe.")
    all_features = pd.concat(rows, ignore_index=True)
    all_features["base_candidate"] = (
        all_features["dd60"].le(-0.15)
        & (all_features["rsi14"].le(40.0) | all_features["ret20"].le(-0.15))
    )
    return all_features, position_maps, next_session_dates


def _load_quality_dates() -> tuple[set[pd.Timestamp], list[dict[str, Any]], dict[str, Any]]:
    quality = json.loads(OPTIONS_QUALITY_PATH.read_text(encoding="utf-8"))
    allowed: set[pd.Timestamp] = set()
    excluded: list[dict[str, Any]] = []
    for day_text, state in sorted(quality.get("by_quote_date", {}).items()):
        day = pd.Timestamp(day_text)
        if day < START_DATE or day > END_DATE:
            continue
        if state.get("scoring_allowed") is True:
            allowed.add(day)
        else:
            excluded.append(
                {
                    "quote_date": day_text,
                    "status": state.get("status"),
                    "reasons": state.get("reasons", []),
                }
            )
    return allowed, excluded, quality


def _load_retrospective_flow() -> tuple[dict[tuple[pd.Timestamp, str], dict[str, Any]], dict[str, Any]]:
    """Keep the earliest materialized row per (flow date, ticker), deterministically."""
    chosen: dict[tuple[pd.Timestamp, str], dict[str, Any]] = {}
    duplicates = 0
    conflicting_duplicates = 0
    digest = hashlib.sha256()
    with FLOW_PATH.open("rb") as handle:
        for raw_line in handle:
            digest.update(raw_line)
            if not raw_line.strip():
                continue
            row = json.loads(raw_line)
            ticker = str(row.get("ticker", "")).upper().strip()
            if ticker not in UNIVERSE:
                continue
            try:
                day = pd.Timestamp(row["flow_date"])
            except (KeyError, TypeError, ValueError):
                continue
            if day < START_DATE or day > END_DATE:
                continue
            main_in_flow = _finite_float(row.get("main_in_flow"))
            if main_in_flow is None:
                continue
            candidate = {
                "main_in_flow": main_in_flow,
                "fetched_at": str(row.get("fetched_at") or ""),
            }
            key = (day, ticker)
            prior = chosen.get(key)
            if prior is None:
                chosen[key] = candidate
                continue
            duplicates += 1
            if not math.isclose(prior["main_in_flow"], main_in_flow, rel_tol=0.0, abs_tol=1e-6):
                conflicting_duplicates += 1
            if candidate["fetched_at"] < prior["fetched_at"]:
                chosen[key] = candidate

    fetched_after_flow_date = sum(
        1
        for (day, _), row in chosen.items()
        if row["fetched_at"] and pd.Timestamp(row["fetched_at"]).tz_localize(None).normalize() > day
    )
    return chosen, {
        "path": str(FLOW_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
        "sha256": digest.hexdigest(),
        "selected_unique_date_ticker_rows": len(chosen),
        "duplicate_rows_seen": duplicates,
        "conflicting_duplicate_rows_seen": conflicting_duplicates,
        "rows_fetched_after_flow_date": fetched_after_flow_date,
        "dedupe_rule": "earliest fetched_at per flow_date and ticker",
        "pit_status": "retrospective_non_pit_proxy_explicitly_allowed_by_user",
    }


def _load_option_chain_rows(
    allowed_dates: set[pd.Timestamp],
) -> tuple[dict[tuple[pd.Timestamp, str], dict[str, Any]], dict[str, Any]]:
    """Load only globally quality-allowed forward chain snapshots."""
    aggregates: dict[tuple[pd.Timestamp, str], dict[str, Any]] = defaultdict(
        lambda: {
            "captured_rows": 0,
            "liquid_rows": 0,
            "expiries": set(),
            "put_rows": [],
            "usable_trade_dates": set(),
            "missing_usable_trade_date_rows": 0,
            "invalid_usable_trade_date_rows": 0,
            "retrieved_ats": set(),
            "missing_retrieved_at_rows": 0,
        }
    )
    files_used: list[dict[str, Any]] = []
    combined_digest = hashlib.sha256()
    raw_rows = 0
    retained_universe_rows = 0
    liquid_universe_rows = 0
    missing_usable_trade_date_rows = 0
    invalid_usable_trade_date_rows = 0
    nonforward_usable_trade_date_rows = 0
    missing_retrieved_at_rows = 0
    retrieved_at_values: set[str] = set()
    usable_trade_date_values: set[str] = set()
    quote_to_usable_dates: dict[str, set[str]] = defaultdict(set)

    for path in sorted(OPTIONS_DIR.glob("options_onclickmedia_chain_*.jsonl")):
        suffix = path.stem.rsplit("_", 1)[-1]
        try:
            filename_day = pd.Timestamp(suffix)
        except ValueError:
            continue
        if filename_day not in allowed_dates:
            continue
        file_rows = 0
        file_digest = hashlib.sha256()
        with path.open("rb") as handle:
            for raw_line in handle:
                file_digest.update(raw_line)
                combined_digest.update(raw_line)
                if not raw_line.strip():
                    continue
                raw_rows += 1
                file_rows += 1
                row = json.loads(raw_line)
                ticker = str(row.get("ticker", "")).upper().strip()
                if ticker not in UNIVERSE:
                    continue
                retained_universe_rows += 1
                try:
                    quote_day = pd.Timestamp(row.get("quote_date") or row.get("date"))
                except (TypeError, ValueError):
                    continue
                if quote_day != filename_day or quote_day not in allowed_dates:
                    continue
                key = (quote_day, ticker)
                state = aggregates[key]
                state["captured_rows"] += 1
                expiry = row.get("expiration") or row.get("expiry")
                if expiry:
                    state["expiries"].add(str(expiry))
                retrieved_at = str(row.get("retrieved_at") or "").strip()
                if retrieved_at:
                    state["retrieved_ats"].add(retrieved_at)
                    retrieved_at_values.add(retrieved_at)
                else:
                    state["missing_retrieved_at_rows"] += 1
                    missing_retrieved_at_rows += 1
                usable_text = str(row.get("usable_trade_date") or "").strip()
                if not usable_text:
                    state["missing_usable_trade_date_rows"] += 1
                    missing_usable_trade_date_rows += 1
                else:
                    try:
                        usable_day = pd.Timestamp(usable_text)
                    except ValueError:
                        state["invalid_usable_trade_date_rows"] += 1
                        invalid_usable_trade_date_rows += 1
                    else:
                        usable_day_text = usable_day.strftime("%Y-%m-%d")
                        state["usable_trade_dates"].add(usable_day_text)
                        usable_trade_date_values.add(usable_day_text)
                        quote_to_usable_dates[quote_day.strftime("%Y-%m-%d")].add(
                            usable_day_text
                        )
                        if usable_day <= quote_day:
                            nonforward_usable_trade_date_rows += 1

                if row.get("option_liquidity_pass") is True:
                    liquid_universe_rows += 1
                    state["liquid_rows"] += 1

                # Frozen proxy formula uses every valid captured put-OI row.  The
                # liquidity field is a separate ticker-date eligibility gate.
                if str(row.get("call_put", "")).lower() == "put":
                    strike = _finite_float(row.get("strike"))
                    open_interest = _finite_float(row.get("open_interest"))
                    if strike is not None and open_interest is not None:
                        state["put_rows"].append((strike, max(0.0, open_interest)))
        files_used.append(
            {
                "quote_date": filename_day.strftime("%Y-%m-%d"),
                "path": str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
                "rows": file_rows,
                "sha256": file_digest.hexdigest(),
            }
        )

    return dict(aggregates), {
        "quality_gate_path": str(OPTIONS_QUALITY_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
        "quality_gate_sha256": _json_sha256(OPTIONS_QUALITY_PATH),
        "files_used": files_used,
        "combined_file_content_sha256": combined_digest.hexdigest(),
        "raw_rows": raw_rows,
        "universe_rows": retained_universe_rows,
        "liquid_universe_rows": liquid_universe_rows,
        "missing_retrieved_at_rows": missing_retrieved_at_rows,
        "missing_usable_trade_date_rows": missing_usable_trade_date_rows,
        "invalid_usable_trade_date_rows": invalid_usable_trade_date_rows,
        "usable_trade_date_not_after_quote_date_rows": nonforward_usable_trade_date_rows,
        "unique_retrieved_at_count": len(retrieved_at_values),
        "retrieved_at_min": min(retrieved_at_values) if retrieved_at_values else None,
        "retrieved_at_max": max(retrieved_at_values) if retrieved_at_values else None,
        "unique_usable_trade_date_count": len(usable_trade_date_values),
        "usable_trade_date_min": min(usable_trade_date_values) if usable_trade_date_values else None,
        "usable_trade_date_max": max(usable_trade_date_values) if usable_trade_date_values else None,
        "quote_date_to_stored_usable_trade_dates": {
            day: sorted(values) for day, values in sorted(quote_to_usable_dates.items())
        },
        "pit_status": "forward_collected_next_session_usable",
        "captured_chain_limit": "two expiries and collector-truncated strike window",
    }


def _complete_case_candidates(
    all_features: pd.DataFrame,
    allowed_dates: set[pd.Timestamp],
    flow_rows: dict[tuple[pd.Timestamp, str], dict[str, Any]],
    option_rows: dict[tuple[pd.Timestamp, str], dict[str, Any]],
    next_session_dates: dict[tuple[str, pd.Timestamp], pd.Timestamp],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Join the fixed signals and proxies without looking at any future return."""
    base = all_features.loc[
        all_features["base_candidate"] & all_features["signal_date"].isin(allowed_dates)
    ].copy()
    complete: list[dict[str, Any]] = []
    missing = Counter()
    expiry_counts = Counter()
    usable_date_mismatches: list[dict[str, Any]] = []
    usable_date_unverifiable: list[dict[str, Any]] = []

    for row in base.itertuples(index=False):
        key = (pd.Timestamp(row.signal_date), str(row.ticker))
        flow = flow_rows.get(key)
        if flow is None:
            missing["flow"] += 1
            continue
        prior_adv20 = _finite_float(row.prior_adv20_usd)
        if prior_adv20 is None or prior_adv20 <= 0.0:
            missing["prior_adv20"] += 1
            continue
        chain = option_rows.get(key)
        if chain is None:
            missing["options"] += 1
            continue
        if int(chain["liquid_rows"]) < 10:
            missing["options_lt_10_liquid_rows"] += 1
            continue
        if chain["missing_usable_trade_date_rows"] or chain["invalid_usable_trade_date_rows"]:
            missing["options_missing_or_invalid_usable_trade_date"] += 1
            continue
        if chain["missing_retrieved_at_rows"]:
            missing["options_missing_retrieved_at"] += 1
            continue
        expected_entry_day = next_session_dates.get((str(row.ticker), pd.Timestamp(row.signal_date)))
        expected_entry_text = (
            expected_entry_day.strftime("%Y-%m-%d") if expected_entry_day is not None else None
        )
        stored_usable_dates = sorted(chain["usable_trade_dates"])
        if len(stored_usable_dates) != 1:
            missing["options_usable_trade_date_not_next_session"] += 1
            usable_date_mismatches.append(
                {
                    "signal_date": pd.Timestamp(row.signal_date).strftime("%Y-%m-%d"),
                    "ticker": str(row.ticker),
                    "stored_usable_trade_dates": stored_usable_dates,
                    "warehouse_next_session": expected_entry_text,
                    "reason": "stored usable date is not unique",
                }
            )
            continue
        stored_usable_day = pd.Timestamp(stored_usable_dates[0])
        if expected_entry_day is not None and stored_usable_day > expected_entry_day:
            missing["options_not_usable_by_next_session_entry"] += 1
            usable_date_mismatches.append(
                {
                    "signal_date": pd.Timestamp(row.signal_date).strftime("%Y-%m-%d"),
                    "ticker": str(row.ticker),
                    "stored_usable_trade_dates": stored_usable_dates,
                    "warehouse_next_session": expected_entry_text,
                    "reason": "stored usable date falls after actual next-session entry",
                }
            )
            continue
        if expected_entry_day is not None and stored_usable_day != expected_entry_day:
            usable_date_mismatches.append(
                {
                    "signal_date": pd.Timestamp(row.signal_date).strftime("%Y-%m-%d"),
                    "ticker": str(row.ticker),
                    "stored_usable_trade_dates": stored_usable_dates,
                    "warehouse_next_session": expected_entry_text,
                    "reason": (
                        "stored next-weekday designation precedes the actual exchange session; "
                        "snapshot remains available by entry"
                    ),
                }
            )
        if expected_entry_day is None:
            usable_date_unverifiable.append(
                {
                    "signal_date": pd.Timestamp(row.signal_date).strftime("%Y-%m-%d"),
                    "ticker": str(row.ticker),
                    "stored_usable_trade_dates": stored_usable_dates,
                    "reason": "next session is beyond the fixed OHLCV outcome window",
                }
            )
        expiry_count = len(chain["expiries"])
        expiry_counts[str(expiry_count)] += 1
        if expiry_count != 2:
            missing["options_not_exactly_two_expiries"] += 1
            continue

        spot = float(row.signal_close)
        numerator = sum(
            oi for strike, oi in chain["put_rows"] if 0.94 * spot <= strike <= 1.01 * spot
        )
        denominator = sum(
            oi for strike, oi in chain["put_rows"] if 0.75 * spot <= strike <= 1.01 * spot
        )
        if denominator <= 0.0:
            missing["put_oi_denominator_nonpositive"] += 1
            continue

        complete.append(
            {
                "signal_date": pd.Timestamp(row.signal_date),
                "ticker": str(row.ticker),
                "signal_close": spot,
                "rsi14": float(row.rsi14),
                "ret20": float(row.ret20),
                "dd60": float(row.dd60),
                "prior_adv20_usd": prior_adv20,
                "main_in_flow": float(flow["main_in_flow"]),
                "flow_fetched_at": flow["fetched_at"],
                "flow_strength": float(flow["main_in_flow"]) / prior_adv20,
                "near_put_oi_share_proxy": numerator / denominator,
                "near_put_oi_numerator": numerator,
                "near_put_oi_denominator": denominator,
                "liquid_option_rows": int(chain["liquid_rows"]),
                "captured_option_rows": int(chain["captured_rows"]),
                "option_expiries": sorted(chain["expiries"]),
                "option_usable_trade_date": stored_usable_dates[0],
                "option_retrieved_at_min": min(chain["retrieved_ats"]),
                "option_retrieved_at_max": max(chain["retrieved_ats"]),
            }
        )

    if not complete:
        raise RuntimeError("The fixed complete-case cohort is empty.")
    cohort = pd.DataFrame(complete).sort_values(["signal_date", "ticker"]).reset_index(drop=True)
    cohort["flow_rank_pct"] = cohort.groupby("signal_date")["flow_strength"].rank(
        method="average", pct=True, ascending=True
    )
    cohort["put_rank_pct"] = cohort.groupby("signal_date")["near_put_oi_share_proxy"].rank(
        method="average", pct=True, ascending=True
    )
    cohort["rsi_oversold_rank_pct"] = cohort.groupby("signal_date")["rsi14"].rank(
        method="average", pct=True, ascending=False
    )
    cohort["treatment_score"] = np.sqrt(cohort["flow_rank_pct"] * cohort["put_rank_pct"])

    return cohort, {
        "all_price_feature_rows": int(len(all_features)),
        "base_candidate_rows_on_quality_allowed_dates": int(len(base)),
        "complete_case_rows": int(len(cohort)),
        "complete_case_tickers": int(cohort["ticker"].nunique()),
        "complete_case_dates": int(cohort["signal_date"].nunique()),
        "dates_with_at_least_two_complete_candidates": int(
            (cohort.groupby("signal_date").size() >= 2).sum()
        ),
        "missing_reasons": dict(sorted(missing.items())),
        "usable_trade_date_mismatches": usable_date_mismatches,
        "usable_trade_date_unverifiable_after_window": usable_date_unverifiable,
        "expiry_counts_before_exact_two_expiry_requirement": dict(sorted(expiry_counts.items())),
    }


def _ranked_rows(day_frame: pd.DataFrame, arm: str) -> list[dict[str, Any]]:
    if arm == "control_rsi":
        ranked = day_frame.sort_values(
            ["rsi14", "dd60", "ticker"], ascending=[True, True, True], kind="mergesort"
        )
    elif arm == "treatment_flow_put":
        ranked = day_frame.sort_values(
            ["treatment_score", "dd60", "ticker"],
            ascending=[False, True, True],
            kind="mergesort",
        )
    else:
        raise ValueError(f"Unknown arm: {arm}")
    return ranked.to_dict(orient="records")


def _selection_record(row: dict[str, Any], arm: str, rank_position: int) -> dict[str, Any]:
    return {
        "signal_date": pd.Timestamp(row["signal_date"]),
        "ticker": row["ticker"],
        "arm": arm,
        "rank_position": rank_position,
        "rsi14": float(row["rsi14"]),
        "dd60": float(row["dd60"]),
        "ret20": float(row["ret20"]),
        "flow_strength": float(row["flow_strength"]),
        "near_put_oi_share_proxy": float(row["near_put_oi_share_proxy"]),
        "flow_rank_pct": float(row["flow_rank_pct"]),
        "put_rank_pct": float(row["put_rank_pct"]),
        "treatment_score": float(row["treatment_score"]),
    }


def _lock_primary_selections(cohort: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    selections = {"control_rsi": [], "treatment_flow_put": []}
    for _, day_frame in cohort.groupby("signal_date", sort=True):
        for arm in selections:
            row = _ranked_rows(day_frame, arm)[0]
            selections[arm].append(_selection_record(row, arm, 1))
    return selections


def _lock_cooldown_selections(
    cohort: pd.DataFrame,
    position_maps: dict[tuple[str, pd.Timestamp], int],
) -> dict[str, list[dict[str, Any]]]:
    """Diagnostic only: independently enforce a 10-session ticker cooldown per arm."""
    selections = {"control_rsi": [], "treatment_flow_put": []}
    last_position: dict[str, dict[str, int]] = {arm: {} for arm in selections}
    for day, day_frame in cohort.groupby("signal_date", sort=True):
        day = pd.Timestamp(day)
        for arm in selections:
            for rank_position, row in enumerate(_ranked_rows(day_frame, arm), start=1):
                ticker = str(row["ticker"])
                current_position = position_maps[(ticker, day)]
                prior_position = last_position[arm].get(ticker)
                if prior_position is not None and current_position - prior_position < COOLDOWN_SESSIONS:
                    continue
                selections[arm].append(_selection_record(row, arm, rank_position))
                last_position[arm][ticker] = current_position
                break
    return selections


def _forward_return(
    frame: pd.DataFrame,
    signal_date: pd.Timestamp,
    horizon: int,
) -> dict[str, Any] | None:
    """Read the fixed next-open/inclusive-H close outcome after selection lock."""
    index = frame.index
    try:
        signal_position = int(index.get_loc(signal_date))
    except KeyError:
        return None
    entry_position = signal_position + 1
    exit_position = signal_position + horizon
    if entry_position >= len(frame) or exit_position >= len(frame):
        return None
    entry = _finite_float(frame.iloc[entry_position]["Open"])
    exit_ = _finite_float(frame.iloc[exit_position]["Close"])
    if entry is None or exit_ is None or entry <= 0.0:
        return None
    gross = exit_ / entry - 1.0
    net = gross - ROUND_TRIP_COST
    return {
        "entry_date": pd.Timestamp(index[entry_position]),
        "exit_date": pd.Timestamp(index[exit_position]),
        "entry_open": entry,
        "exit_close": exit_,
        "gross_return": gross,
        "net_return": net,
        "illustrative_pnl_usd": net * PAPER_NOTIONAL_USD,
    }


def _evaluate_selections(
    selections: dict[str, list[dict[str, Any]]],
    frames: dict[str, pd.DataFrame],
) -> dict[int, dict[str, list[dict[str, Any]]]]:
    evaluated: dict[int, dict[str, list[dict[str, Any]]]] = {
        horizon: {arm: [] for arm in selections} for horizon in HORIZONS
    }
    benchmark_cache: dict[tuple[str, pd.Timestamp, int], dict[str, Any] | None] = {}
    for horizon in HORIZONS:
        for arm, arm_selections in selections.items():
            for selection in arm_selections:
                ticker = selection["ticker"]
                day = selection["signal_date"]
                outcome = _forward_return(frames[ticker], day, horizon)
                if outcome is None:
                    continue
                record = {**selection, **outcome}
                for benchmark in BENCHMARKS:
                    cache_key = (benchmark, day, horizon)
                    if cache_key not in benchmark_cache:
                        benchmark_cache[cache_key] = _forward_return(frames[benchmark], day, horizon)
                    benchmark_outcome = benchmark_cache[cache_key]
                    if benchmark_outcome is None:
                        record[f"replacement_value_vs_{benchmark.lower()}"] = None
                    else:
                        record[f"replacement_value_vs_{benchmark.lower()}"] = (
                            record["net_return"] - benchmark_outcome["net_return"]
                        )
                evaluated[horizon][arm].append(record)
    return evaluated


def _arm_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    returns = np.asarray([row["net_return"] for row in records], dtype=float)
    tickers = Counter(row["ticker"] for row in records)
    n = len(records)
    if n == 0:
        return {"count": 0}
    rv_spy = [row["replacement_value_vs_spy"] for row in records]
    rv_qqq = [row["replacement_value_vs_qqq"] for row in records]
    ticker_shares = np.asarray([count / n for count in tickers.values()], dtype=float)
    selection_hhi = float(np.square(ticker_shares).sum())
    return {
        "count": n,
        "mean_net_return_pct": _pct(float(returns.mean())),
        "median_net_return_pct": _pct(float(np.median(returns))),
        "win_rate_pct": _pct(float(np.mean(returns > 0.0))),
        "mean_illustrative_pnl_usd": round(float(returns.mean() * PAPER_NOTIONAL_USD), 4),
        "cumulative_non_compounded_pnl_usd": round(float(returns.sum() * PAPER_NOTIONAL_USD), 4),
        "mean_replacement_value_vs_spy_pct": _pct(float(np.mean(rv_spy))),
        "mean_replacement_value_vs_qqq_pct": _pct(float(np.mean(rv_qqq))),
        "ticker_counts": dict(sorted(tickers.items())),
        "max_ticker_share_pct": _pct(max(tickers.values()) / n),
        "selection_hhi": _rounded(selection_hhi, 8),
        "effective_names": _rounded(1.0 / selection_hhi, 6),
    }


def _moving_block_bootstrap_mean_ci(delta: np.ndarray) -> list[float | None]:
    """Descriptive circular moving-block CI for overlapping event windows."""
    if len(delta) == 0:
        return [None, None]
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    block_length = min(10, len(delta))
    blocks_per_sample = math.ceil(len(delta) / block_length)
    starts = rng.integers(
        0, len(delta), size=(BOOTSTRAP_REPETITIONS, blocks_per_sample, 1)
    )
    offsets = np.arange(block_length).reshape(1, 1, block_length)
    sample_indices = ((starts + offsets) % len(delta)).reshape(BOOTSTRAP_REPETITIONS, -1)
    sample_indices = sample_indices[:, : len(delta)]
    means = delta[sample_indices].mean(axis=1)
    low, high = np.quantile(means, [0.025, 0.975])
    return [_pct(float(low)), _pct(float(high))]


def _restrict_to_common_h10_settled_panel(
    evaluated: dict[int, dict[str, list[dict[str, Any]]]],
) -> tuple[dict[int, dict[str, list[dict[str, Any]]]], list[pd.Timestamp]]:
    """Use one H10-settled paired date panel for every reported horizon."""
    h10_control_dates = {
        row["signal_date"] for row in evaluated[PRIMARY_HORIZON]["control_rsi"]
    }
    h10_treatment_dates = {
        row["signal_date"] for row in evaluated[PRIMARY_HORIZON]["treatment_flow_put"]
    }
    common_dates = sorted(h10_control_dates & h10_treatment_dates)
    common_set = set(common_dates)
    restricted = {
        horizon: {
            arm: [row for row in rows if row["signal_date"] in common_set]
            for arm, rows in by_arm.items()
        }
        for horizon, by_arm in evaluated.items()
    }
    return restricted, common_dates


def _paired_records(
    evaluated: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    control_by_date = {row["signal_date"]: row for row in evaluated["control_rsi"]}
    treatment_by_date = {row["signal_date"]: row for row in evaluated["treatment_flow_put"]}
    rows: list[dict[str, Any]] = []
    for day in sorted(set(control_by_date) & set(treatment_by_date)):
        control = control_by_date[day]
        treatment = treatment_by_date[day]
        rows.append(
            {
                "signal_date": day,
                "control_ticker": control["ticker"],
                "treatment_ticker": treatment["ticker"],
                "agreement": control["ticker"] == treatment["ticker"],
                "control_net_return": control["net_return"],
                "treatment_net_return": treatment["net_return"],
                "paired_delta": treatment["net_return"] - control["net_return"],
                "control_pnl_usd": control["illustrative_pnl_usd"],
                "treatment_pnl_usd": treatment["illustrative_pnl_usd"],
            }
        )
    return rows


def _paired_summary(rows: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    if not rows:
        return {"paired_dates": 0}
    delta = np.asarray([row["paired_delta"] for row in rows], dtype=float)
    disagreement = [row for row in rows if not row["agreement"]]
    disagreement_delta = np.asarray([row["paired_delta"] for row in disagreement], dtype=float)
    split = len(rows) // 2
    first = delta[:split]
    second = delta[split:]
    all_tickers = sorted(
        {row["control_ticker"] for row in rows} | {row["treatment_ticker"] for row in rows}
    )
    leave_one_out: list[dict[str, Any]] = []
    for ticker in all_tickers:
        remaining = np.asarray(
            [
                row["paired_delta"]
                for row in rows
                if ticker not in {row["control_ticker"], row["treatment_ticker"]}
            ],
            dtype=float,
        )
        leave_one_out.append(
            {
                "excluded_ticker": ticker,
                "remaining_pairs": int(len(remaining)),
                "mean_delta_pct": _pct(float(remaining.mean())) if len(remaining) else None,
            }
        )
    valid_loo = [row["mean_delta_pct"] for row in leave_one_out if row["mean_delta_pct"] is not None]
    pair_exposure = Counter()
    for row in rows:
        pair_exposure[row["control_ticker"]] += 1
        pair_exposure[row["treatment_ticker"]] += 1
    pair_shares = np.asarray(
        [count / (2 * len(rows)) for count in pair_exposure.values()], dtype=float
    )
    pair_hhi = float(np.square(pair_shares).sum())

    return {
        "paired_dates": len(rows),
        "date_start": rows[0]["signal_date"].strftime("%Y-%m-%d"),
        "date_end": rows[-1]["signal_date"].strftime("%Y-%m-%d"),
        "mean_treatment_minus_control_pct": _pct(float(delta.mean())),
        "median_treatment_minus_control_pct": _pct(float(np.median(delta))),
        "treatment_positive_delta_rate_all_dates_pct": _pct(float(np.mean(delta > 0.0))),
        "treatment_beat_rate_pct": (
            _pct(float(np.mean(disagreement_delta > 0.0))) if len(disagreement_delta) else None
        ),
        "treatment_beat_rate_denominator": "allocator disagreement dates only",
        "circular_moving_block_bootstrap": {
            "block_length": min(10, len(delta)),
            "repetitions": BOOTSTRAP_REPETITIONS,
            "seed": BOOTSTRAP_SEED,
            "descriptive_95pct_ci_mean_delta_pct": _moving_block_bootstrap_mean_ci(delta),
            "dependence_caveat": (
                "Daily event windows overlap; this descriptive block interval is not an "
                "independent-trade or portfolio-level confidence interval."
            ),
        },
        "chronological_halves": {
            "first": {
                "count": int(len(first)),
                "mean_delta_pct": _pct(float(first.mean())) if len(first) else None,
            },
            "second": {
                "count": int(len(second)),
                "mean_delta_pct": _pct(float(second.mean())) if len(second) else None,
            },
        },
        "agreement": {
            "dates": len(rows) - len(disagreement),
            "rate_pct": _pct((len(rows) - len(disagreement)) / len(rows)),
        },
        "disagreement": {
            "dates": len(disagreement),
            "mean_delta_pct": (
                _pct(float(disagreement_delta.mean())) if len(disagreement_delta) else None
            ),
            "treatment_beat_rate_pct": (
                _pct(float(np.mean(disagreement_delta > 0.0))) if len(disagreement_delta) else None
            ),
        },
        "combined_pair_exposure": {
            "ticker_counts": dict(sorted(pair_exposure.items())),
            "max_ticker_share_pct": _pct(max(pair_exposure.values()) / (2 * len(rows))),
            "selection_hhi": _rounded(pair_hhi, 8),
            "effective_names": _rounded(1.0 / pair_hhi, 6),
        },
        "leave_one_ticker_out": {
            "rows": leave_one_out,
            "min_mean_delta_pct": min(valid_loo) if valid_loo else None,
            "max_mean_delta_pct": max(valid_loo) if valid_loo else None,
            "all_positive": bool(valid_loo) and min(valid_loo) > 0.0,
        },
    }


def _serialize_paired_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "signal_date": row["signal_date"].strftime("%Y-%m-%d"),
            "control_ticker": row["control_ticker"],
            "treatment_ticker": row["treatment_ticker"],
            "agreement": row["agreement"],
            "control_net_return_pct": _pct(row["control_net_return"]),
            "treatment_net_return_pct": _pct(row["treatment_net_return"]),
            "treatment_minus_control_pct": _pct(row["paired_delta"]),
            "control_pnl_usd": round(row["control_pnl_usd"], 4),
            "treatment_pnl_usd": round(row["treatment_pnl_usd"], 4),
        }
        for row in rows
    ]


def _summarize_panel(
    evaluated: dict[int, dict[str, list[dict[str, Any]]]],
) -> tuple[dict[str, Any], dict[int, list[dict[str, Any]]]]:
    summaries: dict[str, Any] = {}
    paired_by_horizon: dict[int, list[dict[str, Any]]] = {}
    for horizon in HORIZONS:
        paired = _paired_records(evaluated[horizon])
        paired_by_horizon[horizon] = paired
        summaries[f"h{horizon}"] = {
            "control_rsi": _arm_summary(evaluated[horizon]["control_rsi"]),
            "treatment_flow_put": _arm_summary(evaluated[horizon]["treatment_flow_put"]),
            "paired": _paired_summary(paired, horizon),
            "paired_records": _serialize_paired_records(paired),
        }
    return summaries, paired_by_horizon


def _selection_audit(
    selections: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    control = {row["signal_date"]: row for row in selections["control_rsi"]}
    treatment = {row["signal_date"]: row for row in selections["treatment_flow_put"]}
    common_dates = sorted(set(control) & set(treatment))
    disagreements = [day for day in common_dates if control[day]["ticker"] != treatment[day]["ticker"]]
    return {
        "control_selection_dates": len(control),
        "treatment_selection_dates": len(treatment),
        "common_selection_dates": len(common_dates),
        "agreement_dates": len(common_dates) - len(disagreements),
        "disagreement_dates": len(disagreements),
        "disagreement_date_list": [day.strftime("%Y-%m-%d") for day in disagreements],
        "locked_selections": {
            arm: [
                {
                    "signal_date": row["signal_date"].strftime("%Y-%m-%d"),
                    "ticker": row["ticker"],
                    "rank_position": row["rank_position"],
                    "rsi14": _rounded(row["rsi14"], 6),
                    "dd60_pct": _pct(row["dd60"]),
                    "ret20_pct": _pct(row["ret20"]),
                    "flow_strength": _rounded(row["flow_strength"], 10),
                    "near_put_oi_share_proxy": _rounded(
                        row["near_put_oi_share_proxy"], 10
                    ),
                    "treatment_score": _rounded(row["treatment_score"], 10),
                }
                for row in arm_rows
            ]
            for arm, arm_rows in selections.items()
        },
    }


def _acceptance_readout(primary: dict[str, Any]) -> dict[str, Any]:
    paired = primary["paired"]
    treatment = primary["treatment_flow_put"]
    conditions = {
        "at_least_20_paired_dates": paired.get("paired_dates", 0) >= 20,
        "mean_delta_positive": (paired.get("mean_treatment_minus_control_pct") or 0.0) > 0.0,
        "treatment_beat_rate_above_50pct": (paired.get("treatment_beat_rate_pct") or 0.0) > 50.0,
        "both_chronological_half_deltas_positive": all(
            (paired.get("chronological_halves", {}).get(name, {}).get("mean_delta_pct") or 0.0)
            > 0.0
            for name in ("first", "second")
        ),
        "treatment_max_ticker_share_at_most_35pct": (
            treatment.get("max_ticker_share_pct") or 100.0
        )
        <= 35.0,
    }
    return {
        "conditions": conditions,
        "private_proxy_lead_rule_passed": all(conditions.values()),
        "interpretation_limit": "A pass is a retrospective lead only, never accepted alpha or a production change.",
    }


def build_artifact() -> dict[str, Any]:
    if len(UNIVERSE) != 37:
        raise RuntimeError(
            f"Universe contract changed: expected 37 common stocks, found {len(UNIVERSE)}."
        )
    required_inputs = (FLOW_PATH, FLOW_MANIFEST_PATH, OPTIONS_QUALITY_PATH, Path(DEFAULT_WAREHOUSE_PATH))
    missing_inputs = [str(path) for path in required_inputs if not path.exists()]
    if missing_inputs:
        raise FileNotFoundError(f"Required inputs are missing: {missing_inputs}")

    # Stage 1: load price history and construct only causal signal-day features.
    frames = load_warehouse_ohlcv_frames(
        DEFAULT_WAREHOUSE_PATH,
        [*UNIVERSE, *BENCHMARKS],
        HISTORY_START,
        END_DATE,
    )
    missing_frames = sorted(set([*UNIVERSE, *BENCHMARKS]) - set(frames))
    if missing_frames:
        raise RuntimeError(f"Warehouse frames missing for: {missing_frames}")
    price_features, position_maps, next_session_dates = _build_causal_price_features(frames)

    # Stage 2: lock quality dates and join the predeclared proxy fields.
    allowed_dates, excluded_quality_dates, quality_document = _load_quality_dates()
    flow_rows, flow_provenance = _load_retrospective_flow()
    option_rows, option_provenance = _load_option_chain_rows(allowed_dates)
    cohort, cohort_quality = _complete_case_candidates(
        price_features, allowed_dates, flow_rows, option_rows, next_session_dates
    )

    # Stage 3: rank and freeze both panels.  No forward outcome has been read yet.
    primary_selections = _lock_primary_selections(cohort)
    cooldown_selections = _lock_cooldown_selections(cohort, position_maps)
    primary_selection_audit = _selection_audit(primary_selections)
    cooldown_selection_audit = _selection_audit(cooldown_selections)

    # Stage 4: only after both selection ledgers are locked do we read future bars.
    primary_evaluated_raw = _evaluate_selections(primary_selections, frames)
    cooldown_evaluated_raw = _evaluate_selections(cooldown_selections, frames)
    primary_evaluated, primary_common_h10_dates = _restrict_to_common_h10_settled_panel(
        primary_evaluated_raw
    )
    cooldown_evaluated, cooldown_common_h10_dates = _restrict_to_common_h10_settled_panel(
        cooldown_evaluated_raw
    )
    primary_results, _ = _summarize_panel(primary_evaluated)
    cooldown_results, _ = _summarize_panel(cooldown_evaluated)
    primary_h10 = primary_results["h10"]

    flow_manifest = json.loads(FLOW_MANIFEST_PATH.read_text(encoding="utf-8"))
    allowed_date_text = sorted(day.strftime("%Y-%m-%d") for day in allowed_dates)
    quality_allowed_in_files = sorted(
        {row["quote_date"] for row in option_provenance["files_used"]}
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "runner": str(Path(__file__).resolve().relative_to(REPO_ROOT)).replace("\\", "/"),
        "classification": "private_retrospective_proxy_scout",
        "evidence_grade": "lead",
        "trade_enabled": False,
        "production_impact": "none",
        "hypothesis": (
            "Within the fixed same-date rebound-qualified complete-case cohort, the top name "
            "ranked by sqrt(flow-strength percentile times captured-chain near-put-OI-share "
            "percentile) has a higher H10 next-open net outcome than the lowest-RSI name."
        ),
        "locked_design": {
            "universe": list(UNIVERSE),
            "etf_exclusions": sorted(ETF_EXCLUSIONS),
            "window": {"start": "2026-05-06", "end": "2026-07-20"},
            "candidate_formula": "DD60 <= -15% and (RSI14 <= 40 or ret20 <= -15%)",
            "rsi_formula": "Wilder-style EWM alpha=1/14, adjust=False, min_periods=14",
            "flow_strength_formula": "main_in_flow / prior-20-session mean(Close * Volume)",
            "put_proxy_formula": (
                "sum captured put OI for strikes [0.94*S,1.01*S] / sum captured put OI for "
                "strikes [0.75*S,1.01*S], across exactly two captured expiries"
            ),
            "option_completeness": (
                "at least 10 liquid option rows as a separate gate; exactly two captured expiries; "
                "denominator > 0; retrieved_at present; stored usable_trade_date is no later than "
                "actual next-session entry (holiday-early designations are flagged; post-window "
                "next sessions are retained as unsettled and unverifiable)"
            ),
            "missing_data": "complete case only; both ranking arms use the identical cohort",
            "control": "lowest RSI14; tie: deeper DD60, then ticker ascending",
            "treatment": (
                "highest sqrt(flow_rank_pct * put_rank_pct); tie: deeper DD60, then ticker ascending"
            ),
            "entry": "next trading session open",
            "exits": "inclusive H1/H3/H5/H10 close (signal index + horizon)",
            "primary_horizon": "H10",
            "round_trip_cost_bps": 35,
            "illustrative_notional_usd": PAPER_NOTIONAL_USD,
            "bootstrap": {
                "method": (
                    "descriptive circular moving-block bootstrap of ordered paired-date mean "
                    "treatment-minus-control; block length min(10,n)"
                ),
                "seed": BOOTSTRAP_SEED,
                "repetitions": BOOTSTRAP_REPETITIONS,
            },
            "sweep_policy": "no threshold, moneyness, ranking, or horizon sweep",
            "price_stabilization_feature": (
                "not included; this is a three-surface allocator proxy, not the full four-factor test"
            ),
        },
        "outcome_blind_selection_lock": {
            "sequence": [
                "causal price features",
                "quality-date and proxy joins",
                "complete-case cohort",
                "daily ranks and deterministic selections",
                "forward outcome reads",
            ],
            "selection_formulas_locked_before_forward_return_reads": True,
        },
        "synthesis_pass": {
            "baseline_universe": list(UNIVERSE),
            "opportunity_cost_winner": None,
            "evidence_surfaces_used": [
                "warehouse OHLCV price/volume",
                "Moomoo daily main capital flow retrospective proxy",
                "OnclickMedia forward-collected options chain snapshots",
            ],
            "evidence_surfaces_missing": [
                "canonical PIT historical Moomoo flow",
                "full untruncated options chain with three or more expiries",
                "event context",
                "independent positioning context",
                "portfolio exposure/capacity context",
            ],
            "hypothesis_candidates": [
                {
                    "name": "flow_options_interaction_allocator",
                    "baseline": "lowest RSI within the same complete-case rebound cohort",
                    "treatment": "top fixed flow-strength x near-put-share interaction rank",
                    "expected_horizon": "H10 primary; H1/H3/H5 diagnostic",
                    "replacement_value": "same-date treatment-minus-RSI net return and SPY/QQQ replacement value",
                    "falsifier": (
                        "non-positive H10 paired delta, beat rate <=50%, either chronological half "
                        "non-positive, fewer than 20 pairs, or treatment ticker concentration >35%"
                    ),
                }
            ],
            "selected_hypothesis": "flow_options_interaction_allocator",
            "economic_mechanism": (
                "After a large drawdown, institutional net buying may indicate absorption while "
                "near-price put OI marks concentrated hedging/capitulation; their interaction may "
                "distinguish supported rebounds from generic oscillator oversold readings."
            ),
            "falsifier": (
                "The predeclared H10 paired proxy criteria fail, or sensitivity is dominated by one ticker."
            ),
            "evidence_grade": "lead",
            "next_machine_action": (
                "If the proxy is promising, freeze the same formula in a default-off observer and "
                "accumulate materially more jointly eligible, settled, canonical forward PIT rows."
            ),
        },
        "data_quality": {
            "warehouse": {
                "path": str(Path(DEFAULT_WAREHOUSE_PATH).resolve().relative_to(REPO_ROOT)).replace(
                    "\\", "/"
                ),
                "history_start": HISTORY_START.strftime("%Y-%m-%d"),
                "latest_permitted_bar": END_DATE.strftime("%Y-%m-%d"),
                "frames_loaded": len(frames),
            },
            "flow": {
                **flow_provenance,
                "manifest_path": str(FLOW_MANIFEST_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
                "manifest_sha256": _json_sha256(FLOW_MANIFEST_PATH),
                "manifest_earliest_flow_date": flow_manifest.get("earliest_flow_date"),
                "manifest_latest_flow_date": flow_manifest.get("latest_flow_date"),
                "manifest_updated_at": flow_manifest.get("updated_at"),
            },
            "options": option_provenance,
            "quality_allowed_quote_dates": allowed_date_text,
            "quality_allowed_dates_with_snapshot_file": quality_allowed_in_files,
            "quality_excluded_quote_dates": excluded_quality_dates,
            "quality_gate_rule_version": quality_document.get("rule_version"),
            "cohort": cohort_quality,
        },
        "caveats": [
            "Moomoo dates before their fetched_at timestamps are retrospective backfill and could not have informed historical decisions.",
            "The options collector retained only two near expiries and a strike-window subset; near_put_oi_share_proxy is not full-chain OI share.",
            "Open interest can have vendor reporting lag even when the chain snapshot itself was forward collected.",
            "This private scout omits event, positioning, portfolio capacity, and live-realistic execution constraints.",
            "No price-stabilization feature is included, so this does not test the original full four-factor hypothesis.",
            "Daily H10 event windows overlap; returns and illustrative PnL are event-study statistics, not simultaneously executable portfolio PnL, Sharpe, or max drawdown.",
            "A positive result is a lead only; it cannot pass Gate 1-4, change ranking, place orders, or establish live readiness.",
        ],
        "primary_no_cooldown": {
            "label": "primary matched daily ranking attribution",
            "common_h10_settled_panel": {
                "rule": "All H1/H3/H5/H10 summaries use the same common H10-settled decision dates.",
                "dates": [day.strftime("%Y-%m-%d") for day in primary_common_h10_dates],
                "count": len(primary_common_h10_dates),
            },
            "selection_audit": primary_selection_audit,
            "results": primary_results,
            "h10_acceptance_readout": _acceptance_readout(primary_h10),
        },
        "cooldown_diagnostic": {
            "label": "diagnostic only; independent same-ticker cooldown by arm",
            "rule": "ticker is eligible when its current OHLCV index is at least 10 sessions after prior selection in that arm",
            "common_h10_settled_panel": {
                "rule": "All H1/H3/H5/H10 summaries use the same diagnostic H10-settled decision dates.",
                "dates": [day.strftime("%Y-%m-%d") for day in cooldown_common_h10_dates],
                "count": len(cooldown_common_h10_dates),
            },
            "selection_audit": cooldown_selection_audit,
            "results": cooldown_results,
        },
    }


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="JSON artifact path (default is the claimed experiment artifact).",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    artifact = build_artifact()
    output = args.output if args.output.is_absolute() else REPO_ROOT / args.output
    _atomic_write_json(output, artifact)
    h10 = artifact["primary_no_cooldown"]["results"]["h10"]
    concise = {
        "experiment_id": EXPERIMENT_ID,
        "artifact": str(output.resolve()),
        "evidence_grade": artifact["evidence_grade"],
        "complete_case_rows": artifact["data_quality"]["cohort"]["complete_case_rows"],
        "selection_disagreement_dates": artifact["primary_no_cooldown"]["selection_audit"][
            "disagreement_dates"
        ],
        "h10_paired_dates": h10["paired"]["paired_dates"],
        "h10_mean_delta_pct": h10["paired"]["mean_treatment_minus_control_pct"],
        "h10_beat_rate_pct": h10["paired"]["treatment_beat_rate_pct"],
        "private_proxy_lead_rule_passed": artifact["primary_no_cooldown"][
            "h10_acceptance_readout"
        ]["private_proxy_lead_rule_passed"],
    }
    print(json.dumps(concise, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
