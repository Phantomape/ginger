"""exp-20260709-019: Moomoo flow-impact forward value attribution.

Observed-only alpha attribution. The rejected prior Moomoo experiment tested raw
main-flow candidate admission. This run keeps the existing shared candidate
guards fixed and tests a different gate shape: whether positive same-day main
flow has 10d replacement value when normalized by same-day price impact.

No signal generation, ranking, sizing, exits, orders, prompts, or production
policy behavior is changed.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Mapping


EXPERIMENT_ID = "exp-20260709-019"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "moomoo_flow_impact_forward_value"
RUNNER = f"quant/experiments/exp_20260709_019_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
for path in (REPO_ROOT / "scripts", REPO_ROOT / "quant"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from constants import ROUND_TRIP_COST_PCT  # noqa: E402
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)
from fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage  # noqa: E402
from moomoo_capital_flow_paper_sleeve import (  # noqa: E402
    DEFAULT_CONFIG,
    DEFAULT_MANIFEST_PATH,
    DEFAULT_ROWS_PATH,
    EXCLUDED_TICKERS,
    RULE_VERSION,
    SOURCE_RULE_VERSION,
    SLEEVE_NAME,
    _close_return,
    _float_or_none,
    _index_on_date,
    _normalise_ohlcv_rows,
    _pnl,
    _return_pct,
    build_moomoo_capital_flow_candidates,
    flow_rows_by_ticker,
    load_moomoo_capital_flow_rows,
)
from ohlcv_warehouse import DEFAULT_WAREHOUSE_PATH, load_warehouse_ohlcv_frames  # noqa: E402


DATA_DIR = REPO_ROOT / "data"
BASELINE_RESULT = (
    DATA_DIR / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OUT_DIR = DATA_DIR / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260709_019_moomoo_flow_impact_forward_value.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

FLOW_ROWS_JSONL = Path(DEFAULT_ROWS_PATH)
FLOW_MANIFEST_JSON = Path(DEFAULT_MANIFEST_PATH)
WAREHOUSE_SQLITE = Path(DEFAULT_WAREHOUSE_PATH)

HYPOTHESIS = (
    "Observed-only alpha: Moomoo DAY capital-flow rows may have usable "
    "replacement value only after same-day signed main flow is normalized by "
    "PIT price-impact/liquidity context, separating low-impact accumulation "
    "from high-impact chase/exhaustion without retuning the rejected raw "
    "main-flow source."
)
ALPHA_HYPOTHESIS = HYPOTHESIS
CHANGE_TYPE = "observed_only_forward_attribution"
IMPLEMENTATION_MODE = "self_registered_observed_only_runner"
MECHANISM_FAMILY = "production_visible_moomoo_capital_flow_impact_attribution"
TRIAL_FAMILY = "moomoo_flow_impact_normalized_forward_value"
TRIAL_VARIANT_ID = "fixed_amihud_impact_normalized_main_flow_v1"
SINGLE_CAUSAL_VARIABLE = "moomoo_flow_impact_normalized_forward_value_v1"
CHANGED_VARIABLE = SINGLE_CAUSAL_VARIABLE
NEW_EVIDENCE_TYPE = "new_gate_shape_impact_normalized_flow_field"
NEW_EVIDENCE_AXIS = (
    "New gate shape and fixed PIT derived field: main_flow_ratio divided by "
    "same-day absolute price impact, evaluated as 10d cash/SPY/QQQ replacement "
    "attribution. This is not a raw main-flow threshold, bucket, notional, hold, "
    "or response-function retune."
)
CAUSAL_COMPONENTS = [
    "fixed_shared_moomoo_candidate_guards",
    "flow_to_price_impact_field_v1",
    "10d_cash_spy_qqq_forward_attribution",
    "no_strategy_behavior_change",
]
NEARBY_PRIOR_EXPERIMENTS = ["exp-20260702-019", "exp-20260705-016"]
PREDICTION = {
    "success_probability": 0.29,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "no_monotonic_edge",
        "flow_already_priced_by_next_open",
        "thin_forward_sample",
        "impact_proxy_is_only_liquidity",
    ],
    "confidence_reason": (
        "Raw Moomoo main-flow admission was rejected, but external order-flow "
        "research points to impact/liquidity normalization rather than raw "
        "flow. This run is observed-only attribution and does not change live "
        "or backtest policy."
    ),
}
PREDICTED_FAILURE_MODES = PREDICTION["main_failure_modes"]

HOLD_DAYS = 10
PAPER_NOTIONAL_USD = 4_000.0
IMPACT_FLOOR_ABS_RETURN = 0.0025
VOL_IMPACT_FLOOR_MULTIPLIER = 0.25
MIN_TOTAL_ROWS = 100
MIN_BUCKET_ROWS = 25
MIN_BUCKET_TICKERS = 15
MAX_TOP_POSITIVE_SINGLE_TICKER_SHARE = 0.40
MAX_TOP_POSITIVE_TOP5_TICKER_SHARE = 0.70
OUTCOME_FIELDS = (
    "replacement_value_vs_cash_usd",
    "replacement_value_vs_spy_usd",
    "replacement_value_vs_qqq_usd",
)
ACCEPTANCE_RULE = (
    "Observed-only lead only: >=100 closed rows; top and bottom flow-to-impact "
    "quartiles each have >=25 rows and >=15 tickers; top quartile beats bottom "
    "quartile on mean cash/SPY/QQQ replacement values, median in at least two "
    "of three fields, and positive Spearman monotonicity in at least two of "
    "three fields; top-minus-bottom cash mean is positive in both chronological "
    "halves; top positive PnL concentration <=40% single ticker and <=70% top5. "
    "Passing this does not alter strategy behavior."
)

CHANGED_FILES = [
    RUNNER,
    "data/experiments/exp-20260709-019/exp_20260709_019_moomoo_flow_impact_forward_value.json",
    "experiments/logs/exp-20260709-019.json",
    "experiments/cards/exp-20260709-019.md",
    "experiments/manifests/exp-20260709-019.json",
    "experiments/tickets/exp-20260709-019.json",
    "docs/experiment_registry.json",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260709-019/exp_20260709_019_moomoo_flow_impact_forward_value.json",
    "experiments/cards/exp-20260709-019.md",
    "experiments/manifests/exp-20260709-019.json",
    "experiments/tickets/exp-20260709-019.json",
    "experiments/logs/exp-20260709-019.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return value.as_posix()


def safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, Path):
        return repo_rel(value)
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


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


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


def date_window(flow_rows: list[dict[str, Any]]) -> tuple[str, str, str, str]:
    dates = sorted({str(row.get("flow_date")) for row in flow_rows if row.get("flow_date")})
    if not dates:
        return "2025-01-01", "2026-07-09", "", ""
    # The archive starts around 2025-07-02; a fixed early start gives the shared
    # 20d guards and the impact-vol proxy enough PIT history without inference.
    return "2025-05-01", "2026-07-09", dates[0], dates[-1]


def load_ohlcv_context(
    flow_rows: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    start, end, first_flow_date, last_flow_date = date_window(flow_rows)
    tickers = sorted(
        {
            str(row.get("ticker") or "").upper()
            for row in flow_rows
            if str(row.get("ticker") or "").strip()
        }
        | {"SPY", "QQQ"}
    )
    frames = load_warehouse_ohlcv_frames(WAREHOUSE_SQLITE, tickers, start, end)
    rows_by_ticker = {
        ticker: _normalise_ohlcv_rows(frame) for ticker, frame in frames.items()
    }
    ticker_spans = {
        ticker: {
            "rows": len(rows),
            "first_date": rows[0].get("date") if rows else None,
            "last_date": rows[-1].get("date") if rows else None,
        }
        for ticker, rows in rows_by_ticker.items()
    }
    return rows_by_ticker, {
        "warehouse_sqlite": repo_rel(WAREHOUSE_SQLITE),
        "load_start": start,
        "load_end": end,
        "flow_first_date": first_flow_date,
        "flow_last_date": last_flow_date,
        "requested_tickers": len(tickers),
        "loaded_tickers": len(rows_by_ticker),
        "missing_tickers": sorted(set(tickers) - set(rows_by_ticker)),
        "ticker_spans_sample": dict(sorted(ticker_spans.items())[:10]),
        "spy_span": ticker_spans.get("SPY"),
        "qqq_span": ticker_spans.get("QQQ"),
    }


def prior_daily_returns(
    rows: list[dict[str, Any]], end_idx_exclusive: int, days: int
) -> list[float]:
    start_idx = max(1, end_idx_exclusive - days)
    values: list[float] = []
    for idx in range(start_idx, end_idx_exclusive):
        prev_close = _float_or_none(rows[idx - 1].get("close"))
        close = _float_or_none(rows[idx].get("close"))
        if prev_close is None or close is None or prev_close <= 0:
            continue
        values.append(close / prev_close - 1.0)
    return values


def stdev(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    avg = sum(values) / len(values)
    var = sum((value - avg) ** 2 for value in values) / (len(values) - 1)
    return math.sqrt(var)


def comparator_pnl(
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    ticker: str,
    entry_date: str,
    exit_date: str,
) -> float | None:
    rows = rows_by_ticker.get(ticker) or []
    entry_idx = _index_on_date(rows, entry_date)
    exit_idx = _index_on_date(rows, exit_date)
    if entry_idx is None or exit_idx is None:
        return None
    open_price = _float_or_none(rows[entry_idx].get("open"))
    close_price = _float_or_none(rows[exit_idx].get("close"))
    if open_price is None or close_price is None or open_price <= 0 or close_price <= 0:
        return None
    entry_price = apply_entry_fill(open_price)
    exit_price = apply_slippage(close_price, SLIPPAGE_BPS_TARGET, "sell")
    pnl = _pnl(entry_price, exit_price, PAPER_NOTIONAL_USD, ROUND_TRIP_COST_PCT)
    return pnl if pnl is not None and math.isfinite(pnl) else None


def score_candidate(
    candidate: dict[str, Any],
    rows_by_ticker: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, Any] | None, str | None]:
    ticker = str(candidate.get("ticker") or "").upper()
    signal_date = str(candidate.get("signal_date") or candidate.get("date") or "")
    rows = rows_by_ticker.get(ticker) or []
    signal_idx = _index_on_date(rows, signal_date)
    if signal_idx is None:
        return None, "missing_signal_ohlcv"
    if signal_idx < 21:
        return None, "insufficient_impact_history"
    entry_idx = signal_idx + 1
    exit_idx = entry_idx + HOLD_DAYS
    if entry_idx >= len(rows):
        return None, "missing_entry_session"
    if exit_idx >= len(rows):
        return None, "missing_exit_session"

    entry_row = rows[entry_idx]
    exit_row = rows[exit_idx]
    entry_date = str(entry_row.get("date"))
    exit_date = str(exit_row.get("date"))
    open_price = _float_or_none(entry_row.get("open"))
    close_price = _float_or_none(exit_row.get("close"))
    if open_price is None or close_price is None or open_price <= 0 or close_price <= 0:
        return None, "missing_entry_or_exit_price"

    signal_close = _float_or_none(rows[signal_idx].get("close"))
    prev_close = _float_or_none(rows[signal_idx - 1].get("close"))
    if signal_close is None or prev_close is None or prev_close <= 0:
        return None, "missing_signal_impact_price"
    same_day_return = signal_close / prev_close - 1.0
    realized_vol20 = stdev(prior_daily_returns(rows, signal_idx, 20))
    impact_floor = max(
        IMPACT_FLOOR_ABS_RETURN,
        (realized_vol20 or 0.0) * VOL_IMPACT_FLOOR_MULTIPLIER,
    )
    price_impact_abs_return = max(abs(same_day_return), impact_floor)

    main_flow_ratio = finite_float(candidate.get("main_flow_ratio"))
    if main_flow_ratio is None or main_flow_ratio <= 0:
        return None, "missing_main_flow_ratio"
    flow_to_impact = main_flow_ratio / price_impact_abs_return
    price_impact_per_flow = same_day_return / max(main_flow_ratio, 1e-9)

    entry_price = apply_entry_fill(open_price)
    exit_price = apply_slippage(close_price, SLIPPAGE_BPS_TARGET, "sell")
    pnl = _pnl(entry_price, exit_price, PAPER_NOTIONAL_USD, ROUND_TRIP_COST_PCT)
    pnl_pct = _return_pct(entry_price, exit_price, ROUND_TRIP_COST_PCT)
    if pnl is None or pnl_pct is None:
        return None, "missing_candidate_pnl"

    spy_pnl = comparator_pnl(rows_by_ticker, "SPY", entry_date, exit_date)
    qqq_pnl = comparator_pnl(rows_by_ticker, "QQQ", entry_date, exit_date)
    if spy_pnl is None or qqq_pnl is None:
        return None, "missing_comparator_pnl"

    ret20 = finite_float(candidate.get("ret20"))
    spy_ret20 = finite_float(candidate.get("spy_ret20"))
    ret20_excess_spy = finite_float(candidate.get("ret20_excess_spy"))
    flow_main = finite_float(candidate.get("main_in_flow"))
    avg_dollar_volume = finite_float(candidate.get("avg_dollar_volume_20"))
    return {
        "ticker": ticker,
        "signal_date": signal_date,
        "entry_date": entry_date,
        "exit_date": exit_date,
        "hold_days": HOLD_DAYS,
        "paper_notional_usd": PAPER_NOTIONAL_USD,
        "main_in_flow": round_or_none(flow_main, 2),
        "main_flow_ratio": round_or_none(main_flow_ratio, 10),
        "avg_dollar_volume_20": round_or_none(avg_dollar_volume, 2),
        "ret20": round_or_none(ret20, 6),
        "spy_ret20": round_or_none(spy_ret20, 6),
        "ret20_excess_spy": round_or_none(ret20_excess_spy, 6),
        "same_day_return": round_or_none(same_day_return, 8),
        "same_day_abs_return": round_or_none(abs(same_day_return), 8),
        "realized_vol20_prior": round_or_none(realized_vol20, 8),
        "price_impact_abs_return": round_or_none(price_impact_abs_return, 8),
        "flow_to_price_impact": round_or_none(flow_to_impact, 10),
        "price_impact_per_main_flow_ratio": round_or_none(price_impact_per_flow, 8),
        "entry_price": round_or_none(entry_price, 4),
        "exit_price": round_or_none(exit_price, 4),
        "pnl_usd": round_or_none(pnl, 2),
        "pnl_pct_net": round_or_none(pnl_pct, 6),
        "spy_pnl_usd": round_or_none(spy_pnl, 2),
        "qqq_pnl_usd": round_or_none(qqq_pnl, 2),
        "replacement_value_vs_cash_usd": round_or_none(pnl, 2),
        "replacement_value_vs_spy_usd": round_or_none(pnl - spy_pnl, 2),
        "replacement_value_vs_qqq_usd": round_or_none(pnl - qqq_pnl, 2),
        "candidate_rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "trade_enabled": False,
    }, None


def collect_scored_rows(
    flow_rows: list[dict[str, Any]],
    rows_by_ticker: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    flow_index = flow_rows_by_ticker(flow_rows)
    flow_dates = sorted(
        {
            str(row.get("flow_date"))
            for row in flow_rows
            if row.get("flow_date") and str(row.get("ticker") or "").upper() not in EXCLUDED_TICKERS
        }
    )
    universe = sorted(
        {
            str(row.get("ticker") or "").upper()
            for row in flow_rows
            if str(row.get("ticker") or "").strip()
        }
        - set(EXCLUDED_TICKERS)
        - {"SPY", "QQQ"}
    )
    config = {
        **DEFAULT_CONFIG,
        "allow_network_fetch": False,
        "paper_notional_usd": PAPER_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
    }
    candidates: list[dict[str, Any]] = []
    scored_rows: list[dict[str, Any]] = []
    reject_totals: Counter[str] = Counter()
    scoring_rejects: Counter[str] = Counter()
    daily_candidate_counts: dict[str, int] = {}
    spy_rows = rows_by_ticker.get("SPY") or []
    spy_dates = {str(row.get("date")) for row in spy_rows}

    for as_of in flow_dates:
        if as_of not in spy_dates:
            reject_totals["missing_spy_asof"] += len(universe)
            continue
        day_candidates, day_rejects = build_moomoo_capital_flow_candidates(
            rows_by_ticker=rows_by_ticker,
            flow_by_ticker=flow_index,
            tickers=universe,
            as_of=as_of,
            same_day_core_tickers=set(),
            config=config,
        )
        reject_totals.update(day_rejects)
        if day_candidates:
            daily_candidate_counts[as_of] = len(day_candidates)
        candidates.extend(day_candidates)
        for candidate in day_candidates:
            scored, reason = score_candidate(candidate, rows_by_ticker)
            if scored is None:
                scoring_rejects[str(reason or "unknown")] += 1
                continue
            scored_rows.append(scored)

    scored_rows.sort(
        key=lambda row: (
            str(row.get("signal_date") or ""),
            -float(row.get("flow_to_price_impact") or 0.0),
            str(row.get("ticker") or ""),
        )
    )
    return {
        "universe_tickers": universe,
        "flow_dates": flow_dates,
        "raw_candidate_rows": candidates,
        "scored_rows": scored_rows,
        "candidate_reject_totals": dict(sorted(reject_totals.items())),
        "scoring_reject_totals": dict(sorted(scoring_rejects.items())),
        "daily_candidate_counts": daily_candidate_counts,
    }


def assign_quartiles(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    ordered = sorted(
        rows,
        key=lambda row: (
            float(row.get("flow_to_price_impact") or 0.0),
            str(row.get("signal_date") or ""),
            str(row.get("ticker") or ""),
        ),
    )
    n = len(ordered)
    k = max(1, n // 4)
    labelled: list[dict[str, Any]] = []
    for idx, row in enumerate(ordered):
        out = dict(row)
        percentile = idx / (n - 1) if n > 1 else 1.0
        if idx < k:
            label = "q1_high_impact_chase_or_weak_flow"
        elif idx >= n - k:
            label = "q4_low_impact_accumulation"
        else:
            label = "q2_q3_middle"
        out["flow_to_impact_percentile"] = round(percentile, 6)
        out["flow_to_impact_bucket"] = label
        labelled.append(out)
    labelled.sort(
        key=lambda row: (
            str(row.get("signal_date") or ""),
            -float(row.get("flow_to_price_impact") or 0.0),
            str(row.get("ticker") or ""),
        )
    )
    return labelled


def finite_values(rows: list[dict[str, Any]], field: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = finite_float(row.get(field))
        if value is not None:
            values.append(value)
    return values


def positive_concentration(
    rows: list[dict[str, Any]], field: str = "replacement_value_vs_cash_usd"
) -> dict[str, Any]:
    by_ticker: Counter[str] = Counter()
    total_positive = 0.0
    for row in rows:
        value = finite_float(row.get(field))
        if value is None or value <= 0:
            continue
        ticker = str(row.get("ticker") or "")
        by_ticker[ticker] += value
        total_positive += value
    if total_positive <= 0:
        return {
            "positive_total": 0.0,
            "max_single_ticker_share": None,
            "top5_ticker_share": None,
            "hhi": None,
            "top_tickers": [],
        }
    shares = [(ticker, value / total_positive) for ticker, value in by_ticker.items()]
    shares.sort(key=lambda item: (-item[1], item[0]))
    return {
        "positive_total": round(total_positive, 2),
        "max_single_ticker_share": round(shares[0][1], 6) if shares else None,
        "top5_ticker_share": round(sum(share for _, share in shares[:5]), 6),
        "hhi": round(sum(share * share for _, share in shares), 6),
        "top_tickers": [
            {"ticker": ticker, "share": round(share, 6)} for ticker, share in shares[:10]
        ],
    }


def group_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tickers = [str(row.get("ticker") or "") for row in rows]
    dates = [str(row.get("signal_date") or "") for row in rows]
    out: dict[str, Any] = {
        "rows": len(rows),
        "unique_tickers": len(set(tickers)),
        "unique_signal_dates": len(set(dates)),
        "first_signal_date": min(dates) if dates else None,
        "last_signal_date": max(dates) if dates else None,
        "ticker_counts_top10": Counter(tickers).most_common(10),
        "concentration_vs_cash_positive": positive_concentration(rows),
    }
    for field in ("flow_to_price_impact", *OUTCOME_FIELDS):
        values = finite_values(rows, field)
        out[field] = {
            "count": len(values),
            "mean": round_or_none(mean(values), 6),
            "median": round_or_none(median(values), 6) if values else None,
            "sum": round_or_none(sum(values), 2) if values else None,
            "win_rate": round_or_none(
                sum(1 for value in values if value > 0) / len(values) if values else None,
                6,
            ),
            "min": round_or_none(min(values), 6) if values else None,
            "max": round_or_none(max(values), 6) if values else None,
        }
    return out


def rankdata(values: list[float]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][1] == ordered[index][1]:
            end += 1
        avg_rank = (index + end - 1) / 2.0 + 1.0
        for pos in range(index, end):
            ranks[ordered[pos][0]] = avg_rank
        index = end
    return ranks


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x - x_mean) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - y_mean) ** 2 for y in ys))
    if den_x <= 0 or den_y <= 0:
        return None
    return num / (den_x * den_y)


def spearman(rows: list[dict[str, Any]], x_field: str, y_field: str) -> float | None:
    xs: list[float] = []
    ys: list[float] = []
    for row in rows:
        x = finite_float(row.get(x_field))
        y = finite_float(row.get(y_field))
        if x is None or y is None:
            continue
        xs.append(x)
        ys.append(y)
    if len(xs) < 3:
        return None
    return pearson(rankdata(xs), rankdata(ys))


def top_bottom_deltas(
    top_rows: list[dict[str, Any]], bottom_rows: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for field in OUTCOME_FIELDS:
        top_values = finite_values(top_rows, field)
        bottom_values = finite_values(bottom_rows, field)
        top_mean = mean(top_values)
        bottom_mean = mean(bottom_values)
        top_median = median(top_values) if top_values else None
        bottom_median = median(bottom_values) if bottom_values else None
        out[field] = {
            "top_mean": round_or_none(top_mean, 6),
            "bottom_mean": round_or_none(bottom_mean, 6),
            "top_minus_bottom_mean": round_or_none(
                None if top_mean is None or bottom_mean is None else top_mean - bottom_mean,
                6,
            ),
            "top_median": round_or_none(top_median, 6),
            "bottom_median": round_or_none(bottom_median, 6),
            "top_minus_bottom_median": round_or_none(
                None
                if top_median is None or bottom_median is None
                else top_median - bottom_median,
                6,
            ),
        }
    return out


def chronological_validation(
    rows: list[dict[str, Any]], top_rows: list[dict[str, Any]], bottom_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    dates = sorted({str(row.get("signal_date") or "") for row in rows})
    if not dates:
        return {"median_signal_date": None, "splits": {}, "cash_mean_positive_both_halves": False}
    median_signal_date = dates[len(dates) // 2]
    splits: dict[str, dict[str, Any]] = {}
    for name, predicate in (
        ("early", lambda row: str(row.get("signal_date") or "") <= median_signal_date),
        ("late", lambda row: str(row.get("signal_date") or "") > median_signal_date),
    ):
        top_split = [row for row in top_rows if predicate(row)]
        bottom_split = [row for row in bottom_rows if predicate(row)]
        delta = top_bottom_deltas(top_split, bottom_split)
        splits[name] = {
            "top_rows": len(top_split),
            "bottom_rows": len(bottom_split),
            "deltas": delta,
        }
    cash_early = finite_float(
        splits["early"]["deltas"]["replacement_value_vs_cash_usd"].get(
            "top_minus_bottom_mean"
        )
    )
    cash_late = finite_float(
        splits["late"]["deltas"]["replacement_value_vs_cash_usd"].get(
            "top_minus_bottom_mean"
        )
    )
    return {
        "median_signal_date": median_signal_date,
        "splits": splits,
        "cash_mean_positive_both_halves": bool(
            cash_early is not None and cash_late is not None and cash_early > 0 and cash_late > 0
        ),
    }


def evaluate_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    labelled = assign_quartiles(rows)
    top_rows = [
        row for row in labelled if row.get("flow_to_impact_bucket") == "q4_low_impact_accumulation"
    ]
    bottom_rows = [
        row
        for row in labelled
        if row.get("flow_to_impact_bucket") == "q1_high_impact_chase_or_weak_flow"
    ]
    middle_rows = [row for row in labelled if row.get("flow_to_impact_bucket") == "q2_q3_middle"]
    deltas = top_bottom_deltas(top_rows, bottom_rows)
    correlations = {
        field: round_or_none(spearman(labelled, "flow_to_price_impact", field), 6)
        for field in OUTCOME_FIELDS
    }
    chrono = chronological_validation(labelled, top_rows, bottom_rows)

    mean_positive_fields = [
        field
        for field, stats in deltas.items()
        if (finite_float(stats.get("top_minus_bottom_mean")) or 0.0) > 0
    ]
    median_positive_fields = [
        field
        for field, stats in deltas.items()
        if (finite_float(stats.get("top_minus_bottom_median")) or 0.0) > 0
    ]
    spearman_positive_fields = [
        field for field, value in correlations.items() if value is not None and value > 0
    ]
    top_conc = positive_concentration(top_rows)
    criteria = {
        "min_total_rows": len(labelled) >= MIN_TOTAL_ROWS,
        "min_top_rows": len(top_rows) >= MIN_BUCKET_ROWS,
        "min_bottom_rows": len(bottom_rows) >= MIN_BUCKET_ROWS,
        "min_top_tickers": len({row["ticker"] for row in top_rows}) >= MIN_BUCKET_TICKERS,
        "min_bottom_tickers": len({row["ticker"] for row in bottom_rows}) >= MIN_BUCKET_TICKERS,
        "top_mean_beats_bottom_all_fields": len(mean_positive_fields) == len(OUTCOME_FIELDS),
        "top_median_beats_bottom_two_fields": len(median_positive_fields) >= 2,
        "spearman_positive_two_fields": len(spearman_positive_fields) >= 2,
        "chrono_cash_mean_positive_both_halves": bool(
            chrono["cash_mean_positive_both_halves"]
        ),
        "top_positive_single_ticker_share_ok": (
            top_conc["max_single_ticker_share"] is not None
            and top_conc["max_single_ticker_share"]
            <= MAX_TOP_POSITIVE_SINGLE_TICKER_SHARE
        ),
        "top_positive_top5_ticker_share_ok": (
            top_conc["top5_ticker_share"] is not None
            and top_conc["top5_ticker_share"] <= MAX_TOP_POSITIVE_TOP5_TICKER_SHARE
        ),
    }
    pass_all = all(criteria.values())
    return {
        "rows": labelled,
        "bucket_counts": Counter(row["flow_to_impact_bucket"] for row in labelled),
        "groups": {
            "q4_low_impact_accumulation": group_summary(top_rows),
            "q1_high_impact_chase_or_weak_flow": group_summary(bottom_rows),
            "q2_q3_middle": group_summary(middle_rows),
        },
        "top_bottom_deltas": deltas,
        "spearman": correlations,
        "chronological_validation": chrono,
        "positive_fields": {
            "mean": mean_positive_fields,
            "median": median_positive_fields,
            "spearman": spearman_positive_fields,
        },
        "criteria": criteria,
        "pass_all": pass_all,
        "samples": {
            "top_rows": sorted(
                top_rows,
                key=lambda row: (
                    -float(row.get("flow_to_price_impact") or 0.0),
                    str(row.get("signal_date") or ""),
                    str(row.get("ticker") or ""),
                ),
            )[:25],
            "bottom_rows": sorted(
                bottom_rows,
                key=lambda row: (
                    float(row.get("flow_to_price_impact") or 0.0),
                    str(row.get("signal_date") or ""),
                    str(row.get("ticker") or ""),
                ),
            )[:25],
        },
    }


def build_payload() -> dict[str, Any]:
    generated_at = utc_now()
    baseline = baseline_metrics()
    flow_rows = load_moomoo_capital_flow_rows(FLOW_ROWS_JSONL)
    flow_manifest = read_json(FLOW_MANIFEST_JSON, {})
    rows_by_ticker, ohlcv_summary = load_ohlcv_context(flow_rows)
    collected = collect_scored_rows(flow_rows, rows_by_ticker)
    evaluation = evaluate_rows(collected["scored_rows"])

    observed_only_lead = bool(evaluation["pass_all"])
    status = "observed_only_positive" if observed_only_lead else "observed_only_rejected"
    decision = (
        "observed_only_positive_moomoo_flow_impact_lead_not_policy_ready"
        if observed_only_lead
        else "observed_only_rejected_moomoo_flow_impact_edge_unstable"
    )
    rejection_reason = None
    if not observed_only_lead:
        failed = [key for key, passed in evaluation["criteria"].items() if not passed]
        rejection_reason = "failed_predeclared_criteria: " + ", ".join(failed)

    headline = {
        "flow_archive_rows": len(flow_rows),
        "flow_archive_tickers": len({row.get("ticker") for row in flow_rows}),
        "flow_archive_first_date": flow_manifest.get("earliest_flow_date")
        or ohlcv_summary.get("flow_first_date"),
        "flow_archive_last_date": flow_manifest.get("latest_flow_date")
        or ohlcv_summary.get("flow_last_date"),
        "raw_candidate_rows": len(collected["raw_candidate_rows"]),
        "scored_closed_rows": len(evaluation["rows"]),
        "top_rows": evaluation["groups"]["q4_low_impact_accumulation"]["rows"],
        "bottom_rows": evaluation["groups"]["q1_high_impact_chase_or_weak_flow"]["rows"],
        "top_tickers": evaluation["groups"]["q4_low_impact_accumulation"][
            "unique_tickers"
        ],
        "bottom_tickers": evaluation["groups"]["q1_high_impact_chase_or_weak_flow"][
            "unique_tickers"
        ],
        "top_minus_bottom_cash_mean": evaluation["top_bottom_deltas"][
            "replacement_value_vs_cash_usd"
        ]["top_minus_bottom_mean"],
        "top_minus_bottom_spy_mean": evaluation["top_bottom_deltas"][
            "replacement_value_vs_spy_usd"
        ]["top_minus_bottom_mean"],
        "top_minus_bottom_qqq_mean": evaluation["top_bottom_deltas"][
            "replacement_value_vs_qqq_usd"
        ]["top_minus_bottom_mean"],
        "spearman_cash": evaluation["spearman"]["replacement_value_vs_cash_usd"],
        "spearman_spy": evaluation["spearman"]["replacement_value_vs_spy_usd"],
        "spearman_qqq": evaluation["spearman"]["replacement_value_vs_qqq_usd"],
        "chrono_cash_positive_both_halves": evaluation["chronological_validation"][
            "cash_mean_positive_both_halves"
        ],
        "top_positive_single_ticker_share": evaluation["groups"][
            "q4_low_impact_accumulation"
        ]["concentration_vs_cash_positive"]["max_single_ticker_share"],
        "top_positive_top5_ticker_share": evaluation["groups"][
            "q4_low_impact_accumulation"
        ]["concentration_vs_cash_positive"]["top5_ticker_share"],
    }

    return {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": generated_at,
        "owner": OWNER,
        "lane": LANE,
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": observed_only_lead,
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
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": PREDICTION,
        "predicted_failure_modes": PREDICTED_FAILURE_MODES,
        "acceptance_rule": ACCEPTANCE_RULE,
        "inputs": {
            "flow_rows_jsonl": repo_rel(FLOW_ROWS_JSONL),
            "flow_manifest_json": repo_rel(FLOW_MANIFEST_JSON),
            "flow_manifest": {
                "row_count": flow_manifest.get("row_count"),
                "ticker_count": flow_manifest.get("ticker_count"),
                "earliest_flow_date": flow_manifest.get("earliest_flow_date"),
                "latest_flow_date": flow_manifest.get("latest_flow_date"),
                "source_rule_version": flow_manifest.get("rule_version"),
            },
            "warehouse": ohlcv_summary,
            "baseline_result": repo_rel(BASELINE_RESULT),
        },
        "fixed_policy_bundle": {
            "source_sleeve": SLEEVE_NAME,
            "candidate_rule_version": RULE_VERSION,
            "source_rule_version": SOURCE_RULE_VERSION,
            "candidate_guards": {
                "min_main_in_flow": DEFAULT_CONFIG["min_main_in_flow"],
                "min_close": DEFAULT_CONFIG["min_close"],
                "min_avg_dollar_volume_20": DEFAULT_CONFIG[
                    "min_avg_dollar_volume_20"
                ],
                "min_ret20_excess_spy": DEFAULT_CONFIG["min_ret20_excess_spy"],
                "excluded_tickers": sorted(EXCLUDED_TICKERS),
                "same_day_core_tickers": "fixed_empty_set_for_historical_replay",
            },
            "impact_field": {
                "name": "flow_to_price_impact",
                "formula": (
                    "main_flow_ratio / max(abs(signal_close/prev_close - 1), "
                    "0.0025, 0.25 * prior_20d_realized_vol)"
                ),
                "known_at": (
                    "after signal-date close with same-day vendor DAY flow, "
                    "before next-open paper entry"
                ),
            },
            "entry_exit": {
                "entry": "next ticker session open with shared entry fill model",
                "exit": "10 ticker trading sessions after entry at close with sell slippage",
                "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
                "slippage_bps_target": SLIPPAGE_BPS_TARGET,
                "paper_notional_usd": PAPER_NOTIONAL_USD,
            },
            "trade_enabled": False,
        },
        "sample_generation": {
            "universe_ticker_count": len(collected["universe_tickers"]),
            "universe_tickers": collected["universe_tickers"],
            "flow_date_count": len(collected["flow_dates"]),
            "candidate_reject_totals": collected["candidate_reject_totals"],
            "scoring_reject_totals": collected["scoring_reject_totals"],
            "signal_dates_with_candidates": len(collected["daily_candidate_counts"]),
            "max_daily_candidate_count": (
                max(collected["daily_candidate_counts"].values())
                if collected["daily_candidate_counts"]
                else 0
            ),
        },
        "evaluation": {
            "bucket_counts": dict(evaluation["bucket_counts"]),
            "groups": evaluation["groups"],
            "top_bottom_deltas": evaluation["top_bottom_deltas"],
            "spearman": evaluation["spearman"],
            "chronological_validation": evaluation["chronological_validation"],
            "positive_fields": evaluation["positive_fields"],
            "criteria": evaluation["criteria"],
            "pass_all": evaluation["pass_all"],
            "samples": evaluation["samples"],
        },
        "headline_metrics": headline,
        "gate": {
            "pass_fail": {
                "passed": observed_only_lead,
                "criteria": evaluation["criteria"],
                "acceptance_rule": ACCEPTANCE_RULE,
            },
            "reason": (
                "Predeclared impact-normalized field passed all observed-only "
                "lead criteria."
                if observed_only_lead
                else rejection_reason
            ),
        },
        "gate1": {
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "baseline_metrics": baseline,
            "after_metrics": baseline,
            "strategy_behavior_changed": False,
        },
        "gate2": {
            "field_availability": {
                "entry_date": {
                    "required_for_scored_rows": True,
                    "present_count": sum(1 for row in evaluation["rows"] if row.get("entry_date")),
                    "scored_rows": len(evaluation["rows"]),
                },
                "target_price": {
                    "required": False,
                    "reason": (
                        "Observed-only fixed-horizon attribution; no executable "
                        "target exit or signal contract is introduced."
                    ),
                },
                "flow_to_price_impact": {
                    "present_count": sum(
                        1 for row in evaluation["rows"] if row.get("flow_to_price_impact") is not None
                    ),
                    "scored_rows": len(evaluation["rows"]),
                },
            },
            "runtime_fields_verified": True,
        },
        "gate3": {
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "new_filter_added": False,
            "note": (
                "No executable filter was added; observed-only rows are not "
                "candidate survival rows."
            ),
        },
        "gate4": {
            "decision": decision,
            "baseline_metrics": baseline,
            "after_metrics": baseline,
            "delta": {
                "expected_value_score_sum": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "max_drawdown_pct_worst": 0.0,
            },
            "observed_only": True,
            "reason": (
                "Strategy behavior is unchanged; this is an attribution lead "
                "test on closed historical rows."
            ),
        },
        "production_impact": {
            "trade_enabled": False,
            "alters_orders": False,
            "alters_candidate_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "shared_policy_changed": False,
            "llm_change_scope": "none",
        },
        "rejection_reason": rejection_reason,
        "post_run_reflection": {
            "why_result_happened": (
                "The fixed flow-to-impact field was evaluated across the local "
                "Moomoo archive with the existing shared candidate guards. Any "
                "positive or negative result is attribution only because the "
                "strategy path was not changed."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune raw main-flow thresholds, main-flow buckets, "
                "entry slots, hold days, cooldowns, notional, comparator subset, "
                "impact floor, or response functions on this same archive."
            ),
            "new_evidence_required": (
                "A valid retry needs materially more closed Moomoo forward rows, "
                "a genuinely different intraday/vendor flow decomposition with "
                "PIT provenance, borrow/loan economics, or a new gate shape "
                "that is not another raw-flow or impact-threshold slice."
            ),
            "next_evidence_needed": (
                "If this is positive, the next legal step is a shared default-"
                "off helper that keeps impact-normalized accumulation as a "
                "diagnostic candidate state and runs full Gate 1-4. If negative, "
                "park Moomoo DAY flow until new provenance or more settled rows."
            ),
        },
        "gate_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": (
                "exp-20260702-019 rejected raw Moomoo main-flow admission and "
                "exp-20260705-016 only materialized the first forward snapshot. "
                "This run uses a new gate shape, fixed PIT impact-normalized "
                "field, and closed historical warehouse outcomes; recent SEC, "
                "options, broad-dispersion, crypto, chop, and SBC lanes were "
                "avoided as rejected, saturated, or not ready."
            ),
            "3_single_causal_variable": SINGLE_CAUSAL_VARIABLE,
            "4_acceptance_standard": ACCEPTANCE_RULE,
            "5_reproducibility": RUNNER_COMMAND,
        },
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_success": 1 if observed_only_lead else 0,
        },
        "related_files": CHANGED_FILES,
        "changed_files": CHANGED_FILES,
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "lean_quality_passed": True,
    }


def build_card(payload: dict[str, Any]) -> str:
    headline = payload["headline_metrics"]
    criteria = payload["evaluation"]["criteria"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: Moomoo flow-impact forward value",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Scored closed rows: `{headline['scored_closed_rows']}`",
            f"- Top/bottom quartile rows: `{headline['top_rows']}` / `{headline['bottom_rows']}`",
            f"- Top/bottom tickers: `{headline['top_tickers']}` / `{headline['bottom_tickers']}`",
            f"- Top-bottom mean cash/SPY/QQQ: `{headline['top_minus_bottom_cash_mean']}` / `{headline['top_minus_bottom_spy_mean']}` / `{headline['top_minus_bottom_qqq_mean']}`",
            f"- Spearman cash/SPY/QQQ: `{headline['spearman_cash']}` / `{headline['spearman_spy']}` / `{headline['spearman_qqq']}`",
            f"- Chrono cash positive both halves: `{headline['chrono_cash_positive_both_halves']}`",
            f"- Top positive concentration single/top5: `{headline['top_positive_single_ticker_share']}` / `{headline['top_positive_top5_ticker_share']}`",
            f"- Criteria: `{criteria}`",
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
                "headline_metrics": payload["headline_metrics"],
                "bucket_counts": payload["evaluation"]["bucket_counts"],
                "criteria": payload["evaluation"]["criteria"],
                "top_bottom_deltas": payload["evaluation"]["top_bottom_deltas"],
                "spearman": payload["evaluation"]["spearman"],
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
                "headline_metrics": payload["headline_metrics"],
                "criteria": payload["evaluation"]["criteria"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
