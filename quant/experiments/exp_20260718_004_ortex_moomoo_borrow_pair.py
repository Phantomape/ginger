"""exp-20260718-004: fixed ORTEX/Moomoo market-neutral pair replay.

This runner evaluates the preregistered shared default-off helper without
exposing any policy parameter.  Each canonical window starts an independent
$10,000 candidate sleeve and combines its dated returns with the active
cash-feasible core as ``0.90 * core + 0.10 * candidate``.  It writes one
reproducible evaluation artifact and intentionally does not update experiment
cards, logs, manifests, the registry, or ``quant/run.py``.

Usage:

    python -B quant/experiments/exp_20260718_004_ortex_moomoo_borrow_pair.py evaluate
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd


EXPERIMENT_ID = "exp-20260718-004"
SLUG = "ortex_moomoo_borrow_pair"
REPO_ROOT = Path(__file__).resolve().parents[2]
for import_path in (REPO_ROOT, REPO_ROOT / "quant"):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import ortex_data_sidecar as ortex_sidecar  # noqa: E402
import ortex_moomoo_borrow_pair_paper_sleeve as sleeve  # noqa: E402
from data_paths import atomic_write_json  # noqa: E402
from ohlcv_warehouse import (  # noqa: E402
    DEFAULT_WAREHOUSE_PATH,
    load_warehouse_snapshot_ohlcv_frames,
)
from portfolio_contribution_batch import (  # noqa: E402
    core_calendar_and_returns,
    return_metrics,
)


ACTIVE_BASELINE = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_cash_feasible_20260715.json"
)
ORTEX_ROWS_PATH = (
    REPO_ROOT / "data" / "non_ohlcv" / "ortex" / "cost_to_borrow_new_rows.jsonl"
)
MOOMOO_ROWS_PATH = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / "moomoo_daily_short_volume_broad"
    / "rows.jsonl"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260718_004_{SLUG}.json"

EXPECTED_SOURCE_HASHES = {
    "baseline": "4e9ef413126c947b9712fd0879b83c74160f787898860987d204bfc9d60f7731",
    "ortex_rows": "142c7c3f9608d0b14297f35bf27793405bbc17bd1853d15537d1e6029448efb8",
    "moomoo_rows": "b10c9bbe74647576892c5e26c48664e1739a215638622429074738deee89229b",
}

WINDOWS: dict[str, dict[str, str]] = {
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
        "snapshot_sha256": "8554e47aa1a5d36a21c40052e0d69f062cbc8915600867363f66b31377efb6ee",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
        "snapshot_sha256": "7cae08e8c957a81831f37bc289379644d979d863cdb4fc51a39536822d570379",
    },
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
        "snapshot_sha256": "7f7d018f8a3ea4074fb7f3284be1106387b8fbba5bb98e0f29d8a91afa8468b0",
    },
}

CORE_WEIGHT = 0.90
CANDIDATE_WEIGHT = 0.10
CORE_CAPITAL_USD = 100_000.0
CANDIDATE_INITIAL_NAV_USD = 10_000.0
BASELINE_EV = 6.2057
BASELINE_PNL_USD = 130_992.36
MIN_AFTER_EV = BASELINE_EV * 1.10
MAX_MATERIAL_REGRESSED_WINDOWS = 1
WINDOW_EV_MATERIALITY_FRACTION = 0.01
MAX_DRAWDOWN_WORSE = 0.005
MIN_FUNDED_PAIRS = 20
MIN_FUNDED_WINDOWS = 2
MIN_SURVIVAL_RATE = 0.05
FLOAT_TOLERANCE = 1e-7

HYPOTHESIS = (
    "On each fixed source date, the highest equal-weight ORTEX CTB-new and "
    "Moomoo short-volume top-four intersection name should underperform the "
    "lowest-stress sufficiently correlated peer in its fixed cluster after "
    "costs and borrow, adding value as a cash-collateralized 10% pair sleeve."
)

# Outcome-blind production-readiness preflight supplied by the experiment
# owner.  The raw bulk response and API key were deliberately not persisted,
# and this runner must never repeat the credit-consuming request.
PRODUCTION_READINESS_PREFLIGHT = {
    "source": "official ORTEX bulk index/short_ctb permission and coverage preflight",
    "outcome_blind": True,
    "network_request_repeated_by_runner": False,
    "request_succeeded": True,
    "credits_used": 75.55,
    "credits_left_after_request": 334.25,
    "provider_date": "2026-07-16",
    "returned_row_count": 497,
    "fixed_universe_covered_count": 17,
    "fixed_universe_missing_tickers": ["CRDO", "GOOG", "SNOW"],
    "raw_bulk_payload_persisted": False,
    "api_key_persisted": False,
    "current_daily_observer_max_single_ticker_refreshes": 4,
    "same_day_20_name_cross_section_operational": False,
    "bulk_daily_refresh_sustainable_at_current_credit_budget": False,
}
PRODUCTION_BLOCKERS = [
    "bulk_same_day_fixed20_cross_section_incomplete_17_of_20",
    "daily_max4_single_ticker_refresh_cannot_form_same_day_fixed20_cross_section",
    "bulk_daily_refresh_not_credit_sustainable",
    "broker_locate_and_short_availability_unpopulated",
    "raw_bulk_payload_not_archived_for_replay",
]


class EvaluationContractError(RuntimeError):
    """A frozen input, helper, or measurement contract failed closed."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _repo_rel(path: str | Path) -> str:
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(resolved).replace("\\", "/")


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_sha(payload: Any) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=lambda value: (
            value.isoformat()
            if isinstance(value, (date, datetime, pd.Timestamp))
            else value.item()
            if isinstance(value, np.generic)
            else str(value)
        ),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise EvaluationContractError(f"expected JSON object: {path}")
    return payload


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(
        Path(path).read_text(encoding="utf-8-sig").splitlines(), start=1
    ):
        if not raw.strip():
            continue
        row = json.loads(raw)
        if not isinstance(row, dict):
            raise EvaluationContractError(
                f"non-object JSONL row at {path}:{line_number}"
            )
        rows.append(row)
    return rows


def _finite(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _serializable_metrics(values: Sequence[float], *, capital: float) -> dict[str, Any]:
    """Use dated Gate-4-P metrics and the active backtester display EV contract.

    The active anchor stores window EV as ``round(return, 4) *
    abs(round(sharpe, 2))`` rounded to four decimals.  Full-precision EV is
    retained as a diagnostic, while the display-compatible value is binding
    so before and after use one protocol.
    """
    result = dict(return_metrics(np.asarray(values, dtype=float), capital=capital))
    total_return = float(result["total_return_fraction"])
    sharpe = float(result["sharpe_daily"])
    pnl = float(result["total_pnl"])
    drawdown = float(result["max_drawdown_pct"])
    result["total_pnl_full_precision"] = pnl
    result["total_pnl"] = round(pnl, 2)
    result["sharpe_daily_full_precision"] = sharpe
    result["sharpe_daily"] = round(sharpe, 2)
    result["max_drawdown_full_precision"] = drawdown
    result["max_drawdown_pct"] = round(drawdown, 4)
    result["expected_value_score_full_precision"] = total_return * abs(sharpe)
    result["strategy_total_return_public"] = round(total_return, 4)
    result["expected_value_score"] = round(
        result["strategy_total_return_public"]
        * abs(result["sharpe_daily"]),
        4,
    )
    return {
        key: int(value)
        if isinstance(value, (int, np.integer))
        else float(value)
        if isinstance(value, (float, np.floating))
        else value
        for key, value in result.items()
    }


def _metric_delta(after: Mapping[str, Any], before: Mapping[str, Any]) -> dict[str, float]:
    keys = (
        "total_return_fraction",
        "total_pnl",
        "sharpe_daily",
        "expected_value_score",
        "max_drawdown_pct",
        "expected_shortfall_95",
    )
    return {key: float(after[key]) - float(before[key]) for key in keys}


def _baseline_window_map(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("windows")
    if not isinstance(rows, list):
        raise EvaluationContractError("active baseline has no windows list")
    result = {
        str(row.get("label")): dict(row)
        for row in rows
        if isinstance(row, Mapping) and row.get("label")
    }
    if set(result) != set(WINDOWS):
        raise EvaluationContractError(f"baseline windows drift: {sorted(result)}")
    return result


def _load_inputs() -> dict[str, Any]:
    source_hashes = {
        "baseline": _sha256_file(ACTIVE_BASELINE),
        "ortex_rows": _sha256_file(ORTEX_ROWS_PATH),
        "moomoo_rows": _sha256_file(MOOMOO_ROWS_PATH),
    }
    source_hash_checks = {
        key: source_hashes[key] == expected
        for key, expected in EXPECTED_SOURCE_HASHES.items()
    }
    if not all(source_hash_checks.values()):
        raise EvaluationContractError(f"frozen source hash drift: {source_hash_checks}")

    baseline = _read_json(ACTIVE_BASELINE)
    if baseline.get("experiment_id") != "exp-20260715-010":
        raise EvaluationContractError("active baseline experiment identity drift")
    aggregate = baseline.get("aggregate") or {}
    if not (
        _finite(aggregate.get("expected_value_score_sum")) == BASELINE_EV
        and _finite(aggregate.get("total_pnl_sum")) == BASELINE_PNL_USD
    ):
        raise EvaluationContractError("active baseline aggregate anchor drift")
    baseline_windows = _baseline_window_map(baseline)

    core_artifacts: dict[str, dict[str, Any]] = {}
    core_dates: dict[str, list[date]] = {}
    core_returns: dict[str, np.ndarray] = {}
    baseline_curve_checks: dict[str, Any] = {}
    core_identity: dict[str, Any] = {}
    frame_pieces: defaultdict[str, list[pd.DataFrame]] = defaultdict(list)
    ohlcv_identity: dict[str, Any] = {}
    required_tickers = [*sleeve.FIXED_TICKERS, "SPY"]

    helper_tickers = tuple(sleeve.FIXED_TICKERS)
    source_tickers = tuple(ortex_sidecar.FIXED_RESEARCH_TICKERS)
    if (
        len(helper_tickers) != len(set(helper_tickers))
        or len(source_tickers) != len(set(source_tickers))
        or set(helper_tickers) != set(source_tickers)
    ):
        raise EvaluationContractError("helper fixed universe differs from ORTEX source")

    for label, spec in WINDOWS.items():
        baseline_row = baseline_windows[label]
        if (
            str(baseline_row.get("start")) != spec["start"]
            or str(baseline_row.get("end")) != spec["end"]
            or str(baseline_row.get("source")) != spec["snapshot"]
        ):
            raise EvaluationContractError(f"baseline window identity drift: {label}")
        snapshot_path = REPO_ROOT / spec["snapshot"]
        snapshot_hash = _sha256_file(snapshot_path)
        if snapshot_hash != spec["snapshot_sha256"]:
            raise EvaluationContractError(f"snapshot hash drift: {label}")

        artifact_path = REPO_ROOT / str(baseline_row["path"])
        artifact_hash = _sha256_file(artifact_path)
        if artifact_hash != str(baseline_row.get("artifact_sha256")):
            raise EvaluationContractError(f"core artifact hash drift: {label}")
        artifact = _read_json(artifact_path)
        calendar, returns = core_calendar_and_returns(artifact)
        replay_metrics = _serializable_metrics(returns, capital=CORE_CAPITAL_USD)
        checks = {
            "pnl_within_2c": abs(
                replay_metrics["total_pnl"] - float(baseline_row["total_pnl"])
            )
            <= 0.02,
            "sharpe_roundtrip": round(replay_metrics["sharpe_daily"], 2)
            == float(baseline_row["sharpe_daily"]),
            "ev_roundtrip": round(replay_metrics["expected_value_score"], 4)
            == float(baseline_row["expected_value_score"]),
            "drawdown_roundtrip": round(replay_metrics["max_drawdown_pct"], 4)
            == float(baseline_row["max_drawdown_pct"]),
            "return_hash_declared": (
                artifact.get("sharpe_inference", {}).get("return_series_sha256")
                == baseline_row.get("daily_return_series_sha256")
            ),
        }
        if not all(checks.values()):
            raise EvaluationContractError(f"baseline curve contract drift {label}: {checks}")
        core_artifacts[label] = artifact
        core_dates[label] = calendar
        core_returns[label] = returns
        baseline_curve_checks[label] = checks
        core_identity[label] = {
            "path": _repo_rel(artifact_path),
            "sha256": artifact_hash,
            "daily_return_series_sha256": baseline_row.get(
                "daily_return_series_sha256"
            ),
        }

        frames = load_warehouse_snapshot_ohlcv_frames(
            DEFAULT_WAREHOUSE_PATH,
            spec["snapshot"],
            required_tickers,
            spec["start"],
            spec["end"],
        )
        missing = [ticker for ticker in required_tickers if frames.get(ticker) is None]
        if missing:
            raise EvaluationContractError(f"missing snapshot OHLCV {label}: {missing}")
        for ticker, frame in frames.items():
            if frame is not None and not frame.empty:
                frame_pieces[ticker].append(frame)
        ohlcv_identity[label] = {
            "snapshot": spec["snapshot"],
            "snapshot_sha256": snapshot_hash,
            "warehouse_rowset_sha256": baseline.get("input_identity", {})
            .get("warehouse_windows", {})
            .get(label, {})
            .get("warehouse_rowset_sha256"),
            "rows_by_ticker": {
                ticker: int(len(frames.get(ticker, ()))) for ticker in required_tickers
            },
        }

    ohlcv_by_ticker: dict[str, pd.DataFrame] = {}
    for ticker, pieces in frame_pieces.items():
        frame = pd.concat(pieces).sort_index()
        ohlcv_by_ticker[ticker] = frame.loc[~frame.index.duplicated(keep="first")]

    return {
        "baseline": baseline,
        "baseline_windows": baseline_windows,
        "core_artifacts": core_artifacts,
        "core_dates": core_dates,
        "core_returns": core_returns,
        "ohlcv_by_ticker": ohlcv_by_ticker,
        "ortex_rows": _read_jsonl(ORTEX_ROWS_PATH),
        "moomoo_rows": _read_jsonl(MOOMOO_ROWS_PATH),
        "source_hashes": source_hashes,
        "source_hash_checks": source_hash_checks,
        "baseline_curve_checks": baseline_curve_checks,
        "core_identity": core_identity,
        "ohlcv_identity": ohlcv_identity,
    }


def _dated_returns(
    raw_rows: Any,
    calendar: Sequence[date],
) -> tuple[np.ndarray, list[dict[str, Any]], dict[str, Any]]:
    """Align helper returns by date; never zip unequal session arrays."""
    if not isinstance(raw_rows, list):
        raise EvaluationContractError("helper daily_returns must be a list")
    by_date: dict[str, float] = {}
    duplicate_dates: list[str] = []
    for raw in raw_rows:
        if not isinstance(raw, Mapping):
            raise EvaluationContractError("helper daily return row is not an object")
        day = str(raw.get("date") or "")[:10]
        value = _finite(raw.get("return"))
        if not day or value is None or value <= -1.0:
            raise EvaluationContractError(f"invalid helper daily return row: {raw}")
        if day in by_date:
            duplicate_dates.append(day)
        by_date[day] = value
    if duplicate_dates:
        raise EvaluationContractError(f"duplicate helper return dates: {duplicate_dates}")
    dates = [day.isoformat() for day in calendar]
    # A missing candidate row means no sleeve mutation on that core session;
    # the helper currently supplies every date, but zero-fill keeps alignment
    # fail-safe for an exchange-specific absent observation.
    missing_dates = [day for day in dates if day not in by_date]
    values = np.asarray([by_date.get(day, 0.0) for day in dates], dtype=float)
    rows = [{"date": day, "return": float(value)} for day, value in zip(dates, values)]
    return values, rows, {
        "helper_row_count": len(raw_rows),
        "core_calendar_count": len(dates),
        "missing_candidate_dates_zero_filled": missing_dates,
        "extra_helper_dates_ignored": sorted(set(by_date) - set(dates)),
        "aligned_by_date": True,
    }


def _spy_returns(frame: pd.DataFrame, calendar: Sequence[date]) -> np.ndarray:
    closes = {
        str(index.date()): float(row["Close"])
        for index, row in frame.sort_index().iterrows()
    }
    result: list[float] = []
    ordered = sorted(closes)
    prior_by_day = {current: previous for previous, current in zip(ordered, ordered[1:])}
    for day_value in calendar:
        day = day_value.isoformat()
        prior = prior_by_day.get(day)
        if prior is None or day not in closes:
            raise EvaluationContractError(f"SPY return unavailable for {day}")
        result.append(closes[day] / closes[prior] - 1.0)
    return np.asarray(result, dtype=float)


def _beta_corr(values: np.ndarray, benchmark: np.ndarray) -> dict[str, float | None]:
    if len(values) != len(benchmark) or len(values) < 3:
        return {"beta": None, "correlation": None}
    variance = float(np.var(benchmark, ddof=1))
    beta = (
        float(np.cov(values, benchmark, ddof=1)[0, 1] / variance)
        if variance > 0.0
        else None
    )
    correlation = (
        float(np.corrcoef(values, benchmark)[0, 1])
        if float(np.std(values)) > 0.0 and float(np.std(benchmark)) > 0.0
        else None
    )
    return {"beta": beta, "correlation": correlation}


def _gate2_trades(trades: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    required = (
        "entry_date",
        "target_price",
        "exit_date",
        "long_ticker",
        "short_ticker",
        "long_entry_open",
        "short_entry_open",
        "long_exit_close",
        "short_exit_close",
        "gross_pnl_usd",
        "trade_cost_usd",
        "borrow_cost_usd",
        "net_pnl_usd",
    )
    failures: list[str] = []
    for index, trade in enumerate(trades):
        pair_id = str(trade.get("pair_id") or index)
        missing = [field for field in required if field not in trade]
        if missing:
            failures.append(f"missing_fields:{pair_id}:{','.join(missing)}")
            continue
        if not str(trade.get("entry_date") or ""):
            failures.append(f"empty_entry_date:{pair_id}")
        target = _finite(trade.get("target_price"))
        fixed_exit_sentinel = (
            trade.get("target_price") is None
            and trade.get("target_price_role")
            == "not_applicable_fixed_5_session_exit"
        )
        if not ((target is not None and target > 0.0) or fixed_exit_sentinel):
            failures.append(f"invalid_target_price_contract:{pair_id}")
        for field in (
            "long_entry_open",
            "short_entry_open",
            "long_exit_close",
            "short_exit_close",
        ):
            value = _finite(trade.get(field))
            if value is None or value <= 0.0:
                failures.append(f"invalid_price:{pair_id}:{field}")
        trade_cost = _finite(trade.get("trade_cost_usd"))
        if trade_cost is None or trade_cost < 0.0:
            failures.append(f"invalid_cost:{pair_id}:trade_cost_usd")
        # ORTEX CTB-new may be a legitimate signed rebate.  Preserve it in
        # borrow economics instead of coercing it to zero or failing the row.
        if _finite(trade.get("borrow_cost_usd")) is None:
            failures.append(f"invalid_cost:{pair_id}:borrow_cost_usd")
        if trade.get("trade_enabled") is not False:
            failures.append(f"trade_enabled:{pair_id}")
    return {
        "passed": bool(trades) and not failures,
        "funded_pair_count": len(trades),
        "required_fields": list(required),
        "fixed_exit_target_sentinel_allowed": True,
        "failures": failures,
    }


def _concentration(trades: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    short_counts = Counter(str(row.get("short_ticker") or "UNKNOWN") for row in trades)
    long_counts = Counter(str(row.get("long_ticker") or "UNKNOWN") for row in trades)
    cluster_counts = Counter(str(row.get("cluster") or "UNKNOWN") for row in trades)
    positive_by_short: defaultdict[str, float] = defaultdict(float)
    positive_pair_pnls: list[float] = []
    for row in trades:
        pnl = _finite(row.get("net_pnl_usd")) or 0.0
        if pnl > 0.0:
            positive_by_short[str(row.get("short_ticker") or "UNKNOWN")] += pnl
            positive_pair_pnls.append(pnl)
    count = len(trades)
    short_shares = [value / count for value in short_counts.values()] if count else []
    cluster_shares = [value / count for value in cluster_counts.values()] if count else []
    positive_total = sum(positive_pair_pnls)
    positive_short_shares = (
        [value / positive_total for value in positive_by_short.values()]
        if positive_total > 0.0
        else []
    )
    positive_pair_pnls.sort(reverse=True)
    return {
        "pair_count": count,
        "short_ticker_counts": dict(sorted(short_counts.items())),
        "long_ticker_counts": dict(sorted(long_counts.items())),
        "cluster_counts": dict(sorted(cluster_counts.items())),
        "max_short_ticker_pair_share": max(short_shares, default=None),
        "short_ticker_count_hhi": sum(value * value for value in short_shares),
        "max_cluster_pair_share": max(cluster_shares, default=None),
        "cluster_count_hhi": sum(value * value for value in cluster_shares),
        "positive_net_pnl_usd": positive_total,
        "max_short_ticker_positive_pnl_share": max(
            positive_short_shares, default=None
        ),
        "top_five_positive_pair_pnl_share": (
            sum(positive_pair_pnls[:5]) / positive_total
            if positive_total > 0.0
            else None
        ),
    }


def _policy_bundle() -> dict[str, Any]:
    """Serialize helper constants; do not duplicate selection logic here."""
    return {
        "rule_version": sleeve.RULE_VERSION,
        "fixed_tickers": list(sleeve.FIXED_TICKERS),
        "clusters": {key: list(value) for key, value in sleeve.CLUSTERS.items()},
        "top_n": sleeve.TOP_N,
        "correlation_lookback_sessions": sleeve.CORR_LOOKBACK,
        "correlation_floor": sleeve.CORR_MIN,
        "hold_sessions": sleeve.HOLD_SESSIONS,
        "short_cooldown_sessions": sleeve.SHORT_COOLDOWN_SESSIONS,
        "max_concurrent_pairs": sleeve.MAX_CONCURRENT_PAIRS,
        "leg_notional_usd": sleeve.LEG_NOTIONAL_USD,
        "pair_reserved_capital_usd": sleeve.PAIR_RESERVED_CAPITAL_USD,
        "candidate_initial_nav_usd": CANDIDATE_INITIAL_NAV_USD,
        "round_trip_cost_rate_per_leg": sleeve.ROUND_TRIP_COST_RATE_PER_LEG,
        "borrow_accrual": (
            "observed signed CTB-new annual percent * inclusive calendar days / 360; "
            "negative values are borrow rebates"
        ),
        "short_proceeds_reused": False,
        "core_weight": CORE_WEIGHT,
        "candidate_weight": CANDIDATE_WEIGHT,
        "trade_enabled": False,
        "retunable_cli_parameters": [],
    }


def build_evaluation() -> dict[str, Any]:
    inputs = _load_inputs()
    helper_windows = {
        label: {"start": spec["start"], "end": spec["end"]}
        for label, spec in WINDOWS.items()
    }
    replay = sleeve.replay_ortex_moomoo_borrow_pair_sleeve(
        ortex_rows=inputs["ortex_rows"],
        moomoo_rows=inputs["moomoo_rows"],
        ohlcv_by_ticker=inputs["ohlcv_by_ticker"],
        windows=helper_windows,
        initial_cash_usd=CANDIDATE_INITIAL_NAV_USD,
    )
    if replay.get("trade_enabled") is not False:
        raise EvaluationContractError("shared replay is not default-off")
    if replay.get("rule_version") != sleeve.RULE_VERSION:
        raise EvaluationContractError("shared replay rule-version drift")
    replay_windows = replay.get("windows")
    if not isinstance(replay_windows, Mapping) or set(replay_windows) != set(WINDOWS):
        raise EvaluationContractError("shared replay window surface drift")

    windows_result: dict[str, Any] = {}
    all_trades: list[dict[str, Any]] = []
    material_regressions: list[str] = []
    candidate_alignment_passed = True
    aggregate_generated = 0
    aggregate_survived = 0
    total_cost = 0.0
    total_borrow = 0.0
    capital_failures: list[str] = []
    gate2_failures: list[str] = []
    candidate_return_panel: list[np.ndarray] = []
    combined_return_panel: list[np.ndarray] = []
    spy_return_panel: list[np.ndarray] = []

    for label, spec in WINDOWS.items():
        helper_window = replay_windows[label]
        if not isinstance(helper_window, Mapping):
            raise EvaluationContractError(f"invalid helper window: {label}")
        trades = [dict(row) for row in helper_window.get("trades", [])]
        all_trades.extend(trades)
        gate2 = _gate2_trades(trades)
        gate2_failures.extend(f"{label}:{failure}" for failure in gate2["failures"])

        calendar = inputs["core_dates"][label]
        candidate_returns, candidate_return_rows, alignment = _dated_returns(
            helper_window.get("daily_returns"), calendar
        )
        core_returns = inputs["core_returns"][label]
        if len(candidate_returns) != len(core_returns):
            raise EvaluationContractError(f"return alignment length drift: {label}")
        combined_returns = CORE_WEIGHT * core_returns + CANDIDATE_WEIGHT * candidate_returns
        cash_comparator_returns = CORE_WEIGHT * core_returns

        before_replay = _serializable_metrics(core_returns, capital=CORE_CAPITAL_USD)
        candidate_metrics = _serializable_metrics(
            candidate_returns, capital=CANDIDATE_INITIAL_NAV_USD
        )
        after_metrics = _serializable_metrics(combined_returns, capital=CORE_CAPITAL_USD)
        cash_comparator = _serializable_metrics(
            cash_comparator_returns, capital=CORE_CAPITAL_USD
        )
        baseline_row = inputs["baseline_windows"][label]
        before = {
            **before_replay,
            "expected_value_score": float(baseline_row["expected_value_score"]),
            "total_pnl": float(baseline_row["total_pnl"]),
            "sharpe_daily": float(baseline_row["sharpe_daily"]),
            "sharpe_daily_full_precision": float(
                baseline_row["sharpe_daily_full_precision"]
            ),
            "max_drawdown_pct": float(baseline_row["max_drawdown_pct"]),
            "accepted_anchor_fields_applied": True,
        }
        delta = _metric_delta(after_metrics, before)
        diagnostic_vs_cash = _metric_delta(after_metrics, cash_comparator)
        ev_fraction = (
            abs(delta["expected_value_score"]) / abs(before["expected_value_score"])
            if abs(before["expected_value_score"]) > 1e-15
            else None
        )
        material_regression = bool(
            delta["expected_value_score"] < 0.0
            and delta["total_pnl"] < 0.0
            and (ev_fraction is None or ev_fraction > WINDOW_EV_MATERIALITY_FRACTION)
        )
        if material_regression:
            material_regressions.append(label)

        summary = dict(helper_window.get("summary") or {})
        daily_equity = [
            dict(row)
            for row in helper_window.get("daily_equity", [])
            if isinstance(row, Mapping)
        ]
        cash_values = [_finite(row.get("cash_usd")) for row in daily_equity]
        gross_values = [_finite(row.get("gross_exposure_usd")) for row in daily_equity]
        nav_values = [_finite(row.get("equity_usd")) for row in daily_equity]
        cash_nonnegative = bool(daily_equity) and all(
            value is not None and value >= -FLOAT_TOLERANCE for value in cash_values
        )
        gross_lte_nav = bool(daily_equity) and all(
            gross is not None
            and nav is not None
            and gross <= nav + FLOAT_TOLERANCE
            for gross, nav in zip(gross_values, nav_values)
        )
        max_concurrent = max(
            (int(row.get("open_pair_count") or 0) for row in daily_equity), default=0
        )
        if not cash_nonnegative:
            capital_failures.append(f"negative_or_missing_cash:{label}")
        if not gross_lte_nav:
            capital_failures.append(f"gross_exceeds_nav:{label}")
        if max_concurrent > sleeve.MAX_CONCURRENT_PAIRS:
            capital_failures.append(f"concurrent_pair_cap_exceeded:{label}")

        trade_net_pnl = sum(float(row["net_pnl_usd"]) for row in trades)
        trade_cost = sum(float(row["trade_cost_usd"]) for row in trades)
        borrow_cost = sum(float(row["borrow_cost_usd"]) for row in trades)
        total_cost += trade_cost
        total_borrow += borrow_cost
        pnl_identity_error = candidate_metrics["total_pnl"] - trade_net_pnl
        summary_checks = {
            "trade_count": int(summary.get("trade_count", -1)) == len(trades),
            "trade_pnl_matches_summary": abs(
                trade_net_pnl - float(summary.get("total_pnl_usd", math.inf))
            )
            <= 0.02,
            "daily_curve_matches_trades": abs(pnl_identity_error) <= 0.02,
            "cost_matches_summary": abs(
                trade_cost - float(summary.get("total_trade_cost_usd", math.inf))
            )
            <= 0.02,
            "borrow_matches_summary": abs(
                borrow_cost - float(summary.get("total_borrow_cost_usd", math.inf))
            )
            <= 0.02,
        }
        if not all(summary_checks.values()):
            candidate_alignment_passed = False

        generated = int(helper_window.get("signals_generated") or 0)
        survived = int(helper_window.get("signals_survived") or 0)
        survival_rate = float(helper_window.get("survival_rate") or 0.0)
        aggregate_generated += generated
        aggregate_survived += survived

        spy_returns = _spy_returns(inputs["ohlcv_by_ticker"]["SPY"], calendar)
        candidate_return_panel.append(candidate_returns)
        combined_return_panel.append(combined_returns)
        spy_return_panel.append(spy_returns)
        spy_diagnostics = {
            "candidate": _beta_corr(candidate_returns, spy_returns),
            "combined": _beta_corr(combined_returns, spy_returns),
            "helper_candidate_beta": summary.get("spy_beta"),
            "helper_candidate_correlation": summary.get("spy_correlation"),
        }
        windows_result[label] = {
            "start": spec["start"],
            "end": spec["end"],
            "before": before,
            "candidate": candidate_metrics,
            "after": after_metrics,
            "delta": delta,
            "diagnostic_90_core_10_cash": cash_comparator,
            "diagnostic_delta_vs_90_core_10_cash": diagnostic_vs_cash,
            "material_regression": material_regression,
            "ev_delta_fraction_of_core": ev_fraction,
            "signals_generated": generated,
            "signals_survived": survived,
            "survival_rate": survival_rate,
            "funded_pair_count": len(trades),
            "gate2": gate2,
            "capital": {
                "initial_nav_usd": CANDIDATE_INITIAL_NAV_USD,
                "min_cash_usd": min(
                    (value for value in cash_values if value is not None), default=None
                ),
                "max_gross_exposure_usd": max(
                    (value for value in gross_values if value is not None), default=None
                ),
                "max_concurrent_pairs": max_concurrent,
                "cash_nonnegative": cash_nonnegative,
                "gross_lte_nav_every_day": gross_lte_nav,
                "ending_cash_usd": summary.get("ending_cash_usd"),
                "ending_equity_usd": summary.get("ending_equity_usd"),
            },
            "economics": {
                "gross_pnl_usd": sum(float(row["gross_pnl_usd"]) for row in trades),
                "trade_cost_usd": trade_cost,
                "borrow_cost_usd": borrow_cost,
                "net_pnl_usd": trade_net_pnl,
                "daily_curve_minus_trade_pnl_usd": pnl_identity_error,
                "summary_identity_checks": summary_checks,
            },
            "concentration": _concentration(trades),
            "spy_beta_correlation": spy_diagnostics,
            "return_alignment": alignment,
            "candidate_daily_equity": daily_equity,
            "candidate_daily_returns": candidate_return_rows,
            "combined_daily_returns": [
                {"date": day.isoformat(), "return": float(value)}
                for day, value in zip(calendar, combined_returns)
            ],
            "trades": trades,
            "helper_summary": summary,
            "helper_audit": helper_window.get("audit"),
        }

    aggregate_survival = (
        aggregate_survived / aggregate_generated if aggregate_generated else 0.0
    )
    funded_windows = sum(
        int(windows_result[label]["funded_pair_count"] > 0) for label in WINDOWS
    )
    funded_pairs = len(all_trades)
    aggregate_before_ev = sum(
        float(windows_result[label]["before"]["expected_value_score"])
        for label in WINDOWS
    )
    aggregate_after_ev = sum(
        float(windows_result[label]["after"]["expected_value_score"])
        for label in WINDOWS
    )
    aggregate_candidate_ev = sum(
        float(windows_result[label]["candidate"]["expected_value_score"])
        for label in WINDOWS
    )
    aggregate_before_pnl = sum(
        float(windows_result[label]["before"]["total_pnl"]) for label in WINDOWS
    )
    aggregate_after_pnl = sum(
        float(windows_result[label]["after"]["total_pnl"]) for label in WINDOWS
    )
    aggregate_candidate_pnl = sum(
        float(windows_result[label]["candidate"]["total_pnl"]) for label in WINDOWS
    )
    worst_drawdown_worse = max(
        float(windows_result[label]["delta"]["max_drawdown_pct"])
        for label in WINDOWS
    )

    gate2 = {
        "passed": not gate2_failures and candidate_alignment_passed,
        "entry_date_and_target_price_contract_checked": True,
        "funded_pair_count": funded_pairs,
        "daily_curve_trade_identity_passed": candidate_alignment_passed,
        "failures": gate2_failures,
        "source_join_audit": replay.get("join_audit"),
        "source_join_policy": (
            "exact provider_date/activity_date full-20 cross-section; missing "
            "values fail closed with no zero-fill or carry-forward"
        ),
        "production_readiness_diagnostic": PRODUCTION_READINESS_PREFLIGHT,
        "production_blockers_non_binding_for_historical_gate4": PRODUCTION_BLOCKERS,
    }
    gate3 = {
        "passed": aggregate_generated > 0 and aggregate_survival >= MIN_SURVIVAL_RATE,
        "signals_generated": aggregate_generated,
        "signals_survived": aggregate_survived,
        "survival_rate": aggregate_survival,
        "minimum_survival_rate": MIN_SURVIVAL_RATE,
        "by_window": {
            label: {
                "signals_generated": windows_result[label]["signals_generated"],
                "signals_survived": windows_result[label]["signals_survived"],
                "survival_rate": windows_result[label]["survival_rate"],
            }
            for label in WINDOWS
        },
    }
    checks = {
        "aggregate_ev_gt_110pct_baseline": aggregate_after_ev > MIN_AFTER_EV,
        "aggregate_pnl_gt_baseline": aggregate_after_pnl > BASELINE_PNL_USD,
        "material_window_regressions_lte_one": (
            len(material_regressions) <= MAX_MATERIAL_REGRESSED_WINDOWS
        ),
        "drawdown_worse_lte_0_5pp": worst_drawdown_worse <= MAX_DRAWDOWN_WORSE,
        "funded_pairs_gte_20": funded_pairs >= MIN_FUNDED_PAIRS,
        "funded_windows_gte_2": funded_windows >= MIN_FUNDED_WINDOWS,
        "survival_gte_5pct": gate3["passed"],
        "gate2_signal_contract": gate2["passed"],
        "cash_nonnegative_all_windows": not any(
            failure.startswith("negative_or_missing_cash") for failure in capital_failures
        ),
        "gross_lte_candidate_nav_all_days": not any(
            failure.startswith("gross_exceeds_nav") for failure in capital_failures
        ),
        "max_five_concurrent_pairs": not any(
            failure.startswith("concurrent_pair_cap_exceeded")
            for failure in capital_failures
        ),
        "helper_default_off": replay.get("trade_enabled") is False,
    }
    hard_failures = [name for name, passed in checks.items() if not passed]
    accepted = not hard_failures
    decision = (
        "accepted_default_off_ortex_moomoo_borrow_pair"
        if accepted
        else "rejected_ortex_moomoo_borrow_pair_economics"
    )

    helper_path = REPO_ROOT / "quant" / "ortex_moomoo_borrow_pair_paper_sleeve.py"
    payload = {
        "schema": "ortex_moomoo_borrow_pair_gate4_v1",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": _utc_now(),
        "lane": "alpha_search",
        "status": "accepted_default_off" if accepted else "rejected",
        "decision": decision,
        "accepted_alpha": accepted,
        "live_ready": False,
        "hypothesis": HYPOTHESIS,
        "policy_bundle": _policy_bundle(),
        "measurement_contract": {
            "formal_comparison": "0.90*active_cash_feasible_core + 0.10*candidate versus 1.00*core",
            "candidate_initial_nav_usd_per_window": CANDIDATE_INITIAL_NAV_USD,
            "daily_return_formula": "0.90*core_return + 0.10*candidate_return",
            "candidate_pnl_double_scaled": False,
            "material_regression_definition": (
                "EV and PnL deltas both negative and abs(EV delta) > "
                "1% of abs(core EV)"
            ),
            "outcomes_were_not_used_to_change_policy": True,
        },
        "source_identity": {
            "baseline": {
                "path": _repo_rel(ACTIVE_BASELINE),
                "sha256": inputs["source_hashes"]["baseline"],
                "expected_sha256": EXPECTED_SOURCE_HASHES["baseline"],
            },
            "ortex_rows": {
                "path": _repo_rel(ORTEX_ROWS_PATH),
                "sha256": inputs["source_hashes"]["ortex_rows"],
                "row_count": len(inputs["ortex_rows"]),
            },
            "moomoo_rows": {
                "path": _repo_rel(MOOMOO_ROWS_PATH),
                "sha256": inputs["source_hashes"]["moomoo_rows"],
                "row_count": len(inputs["moomoo_rows"]),
            },
            "ohlcv_warehouse": _repo_rel(DEFAULT_WAREHOUSE_PATH),
            "ohlcv_windows": inputs["ohlcv_identity"],
            "core_window_artifacts": inputs["core_identity"],
            "helper": {"path": _repo_rel(helper_path), "sha256": _sha256_file(helper_path)},
            "runner": {"path": _repo_rel(Path(__file__)), "sha256": _sha256_file(Path(__file__))},
            "source_hash_checks": inputs["source_hash_checks"],
            "baseline_curve_checks": inputs["baseline_curve_checks"],
            "helper_replay_canonical_sha256": _canonical_sha(replay),
        },
        "windows": windows_result,
        "aggregate": {
            "before": {
                "expected_value_score_sum": aggregate_before_ev,
                "total_pnl_sum": aggregate_before_pnl,
                "worst_max_drawdown_pct": max(
                    float(windows_result[label]["before"]["max_drawdown_pct"])
                    for label in WINDOWS
                ),
            },
            "candidate": {
                "expected_value_score_sum": aggregate_candidate_ev,
                "total_pnl_sum": aggregate_candidate_pnl,
                "funded_pair_count": funded_pairs,
                "funded_window_count": funded_windows,
                "signals_generated": aggregate_generated,
                "signals_survived": aggregate_survived,
                "survival_rate": aggregate_survival,
                "gross_pnl_usd": sum(float(row["gross_pnl_usd"]) for row in all_trades),
                "trade_cost_usd": total_cost,
                "borrow_cost_usd": total_borrow,
                "net_trade_pnl_usd": sum(float(row["net_pnl_usd"]) for row in all_trades),
                "concentration": _concentration(all_trades),
                "minimum_cash_usd": min(
                    float(windows_result[label]["capital"]["min_cash_usd"])
                    for label in WINDOWS
                ),
                "maximum_marked_gross_exposure_usd": max(
                    float(
                        windows_result[label]["capital"][
                            "max_gross_exposure_usd"
                        ]
                    )
                    for label in WINDOWS
                ),
                "spy_beta_correlation": _beta_corr(
                    np.concatenate(candidate_return_panel),
                    np.concatenate(spy_return_panel),
                ),
            },
            "after": {
                "expected_value_score_sum": aggregate_after_ev,
                "total_pnl_sum": aggregate_after_pnl,
                "worst_max_drawdown_pct": max(
                    float(windows_result[label]["after"]["max_drawdown_pct"])
                    for label in WINDOWS
                ),
                "spy_beta_correlation": _beta_corr(
                    np.concatenate(combined_return_panel),
                    np.concatenate(spy_return_panel),
                ),
            },
            "delta": {
                "expected_value_score": aggregate_after_ev - aggregate_before_ev,
                "total_pnl": aggregate_after_pnl - aggregate_before_pnl,
                "worst_max_drawdown_worse": worst_drawdown_worse,
                "material_regressed_windows": material_regressions,
                "material_regressed_window_count": len(material_regressions),
            },
        },
        "gate1": {
            "passed": True,
            "active_baseline": _repo_rel(ACTIVE_BASELINE),
            "expected_value_score_sum": BASELINE_EV,
            "total_pnl_sum": BASELINE_PNL_USD,
        },
        "gate2": gate2,
        "gate3": gate3,
        "gate4": {
            "passed": accepted,
            "status": "passed" if accepted else "rejected",
            "checks": checks,
            "hard_failures": hard_failures,
            "capital_failures": capital_failures,
            "thresholds": {
                "aggregate_ev_strictly_greater_than": MIN_AFTER_EV,
                "aggregate_pnl_strictly_greater_than": BASELINE_PNL_USD,
                "max_material_regressed_windows": MAX_MATERIAL_REGRESSED_WINDOWS,
                "window_ev_materiality_fraction": WINDOW_EV_MATERIALITY_FRACTION,
                "max_drawdown_worse": MAX_DRAWDOWN_WORSE,
                "min_funded_pairs": MIN_FUNDED_PAIRS,
                "min_funded_windows": MIN_FUNDED_WINDOWS,
                "min_survival_rate": MIN_SURVIVAL_RATE,
            },
        },
        "helper_join_audit": replay.get("join_audit"),
        "helper_aggregate": replay.get("aggregate"),
        "production_impact": {
            **dict(replay.get("production_impact") or {}),
            "shared_helper_used": True,
            "run_py_changed_by_runner": False,
            "trade_enabled": False,
            "live_locate_or_availability_populated": False,
            "live_ready": False,
            "forward_operational": False,
            "production_readiness_preflight": PRODUCTION_READINESS_PREFLIGHT,
            "production_blockers": PRODUCTION_BLOCKERS,
            "maximum_positive_conclusion": (
                "default_off_not_forward_operational_not_live_ready"
            ),
            "failed_economics_requires_run_wiring_rollback": not accepted,
        },
        "post_run_interpretation": {
            "economic_verdict_is_binding": True,
            "operational_helper_success_cannot_override_gate4_failure": True,
            "retry_policy": (
                "Do not retune top-N, rank sum, clusters, correlation floor, hold, "
                "cooldown, notional, cost, borrow accrual, or 10% weight on these rows."
            ),
        },
        "reproduction_command": (
            ".\\.venv\\Scripts\\python.exe -B "
            "quant\\experiments\\exp_20260718_004_ortex_moomoo_borrow_pair.py evaluate"
        ),
    }
    return payload


def command_evaluate() -> int:
    payload = build_evaluation()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_json(payload, OUT_JSON)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "aggregate": payload["aggregate"],
                "gate2_passed": payload["gate2"]["passed"],
                "gate3_passed": payload["gate3"]["passed"],
                "gate4_passed": payload["gate4"]["passed"],
                "hard_failures": payload["gate4"]["hard_failures"],
                "artifact": _repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    # A rejected alpha is a successfully completed experiment, not a runner error.
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", default="evaluate", choices=("evaluate",))
    args = parser.parse_args()
    if args.command == "evaluate":
        return command_evaluate()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
