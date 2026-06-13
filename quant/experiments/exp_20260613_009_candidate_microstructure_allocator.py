"""exp-20260613-009: candidate microstructure allocator arbitration.

Alpha search, replay-only. The policy under test is an ex-ante candidate-level
OHLCV quality field for same-day accepted allocator source conflicts. It keeps
the accepted allocator execution envelope fixed and changes only the same-day
candidate arbitration key. No production/shared helper is changed in this
runner.

No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import Counter, OrderedDict
from copy import deepcopy
from pathlib import Path
from typing import Any

import exp_20260611_005_lagged_consensus_shared_allocator_source as accepted
import exp_20260613_006_source_score_percentile_allocator as prior

framework = accepted.framework

REPO_ROOT = accepted.REPO_ROOT
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for entry in (str(REPO_ROOT), str(QUANT_ROOT), str(SCRIPTS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from accepted_helper_source_priority_allocator_paper_sleeve import (  # noqa: E402
    BASE_NOTIONAL_USD,
    RULE_VERSION as ACCEPTED_ALLOCATOR_RULE_VERSION,
    SAME_TICKER_COOLDOWN_DAYS,
    SOURCE_PRIORITY,
    SOURCE_RULE_VERSION as ACCEPTED_ALLOCATOR_SOURCE_RULE_VERSION,
    _allocator_score,
    _build_source_trades,
    _decision_id,
    _float,
    _normalise_source_row,
    select_accepted_helper_source_priority_rows,
)
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260613-009"
STEM = "candidate_microstructure_allocator"
OWNER = "alpha-search-automation"
TRIAL_FAMILY = "accepted_allocator_source_arbitration"
TRIAL_VARIANT_ID = "candidate_microstructure_quality_source_arbitration_v1"
CHANGED_VARIABLE = TRIAL_VARIANT_ID
MICROSTRUCTURE_RULE_VERSION = TRIAL_VARIANT_ID
SLEEVE_NAME = "CANDIDATE_MICROSTRUCTURE_ALLOCATOR_REPLAY_ONLY"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260613_009_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"

MIN_QUALITY_SCORE = 0.58
QUALITY_SWITCH_MARGIN = 0.08
MIN_QUALITY_FIELD_COUNT = 6
MIN_AVG_DOLLAR_VOLUME_20D = 10_000_000.0
MAX_DRAWDOWN_WORSE = 0.005
MIN_CHANGED_SELECTIONS = 9
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

ACCEPTED_ALLOCATOR_COMPARATOR = prior.ACCEPTED_ALLOCATOR_COMPARATOR

PREDICTION = {
    "success_probability": 0.24,
    "expected_ev_delta": 0.25,
    "expected_pnl_delta": 4500.0,
    "main_failure_modes": [
        "OHLCV quality proxy overfits oracle switches",
        "fixed accepted source priority remains stronger",
        "missing fields bias source families",
        "old_thin regression",
    ],
    "confidence_reason": (
        "exp-20260613-003 showed a material same-day source-choice oracle gap. "
        "exp-20260613-004 and exp-20260613-006 ruled out trailing source PnL "
        "maturity and source-score percentile; candidate PIT OHLCV quality is a "
        "distinct ex-ante arbitration field from free data."
    ),
    "recorded_at": "2026-06-13T04:09:02+00:00",
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool/allocation: when accepted default-off paper sources "
        "compete for the same daily allocator slot, a liquid mid-trend "
        "candidate with high close location, confirmed volume, and low short-"
        "term extension may outperform fixed source priority while preserving "
        "the accepted allocator execution envelope."
    ),
    "2_history_check": {
        "exp-20260611-005": (
            "Accepted lagged-consensus shared allocator source and binding "
            "comparator: aggregate EV +2.1849 and PnL +$40,397.21."
        ),
        "exp-20260613-003": (
            "Observed-only same-day source-choice oracle found a material gap, "
            "but used future PnL and required a PIT arbitration field."
        ),
        "exp-20260613-004": (
            "Rejected trailing closed-PnL source maturity allocator; avoid "
            "performance chasing and lookback/min-history retries."
        ),
        "exp-20260613-006": (
            "Rejected source-score percentile allocator; avoid source rank, "
            "source-score percentile, top-N, hold, notional, or cooldown "
            "near-neighbor retunes."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. The variant must "
        "improve aggregate EV and PnL versus the same-run accepted allocator "
        "control, avoid direct EV/PnL regression in every window, retain sample "
        "and survival guards, keep drawdown drift <= 0.5pp, and beat the "
        "accepted exp-20260611-005 comparator. A positive replay result is only "
        "a lead until shared helper and daily parity are implemented."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260613_009_candidate_microstructure_allocator.py"
    ),
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_candidate_microstructure_scout",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "default_off_paper_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "uses_llm": False,
    "uses_free_ohlcv_only": True,
    "uses_free_non_ohlcv": True,
    "live_realism_evaluated": True,
    "live_ready": False,
    "execution_envelope": {
        "base_notional": BASE_NOTIONAL_USD,
        "max_capital_pct": 0.32,
        "max_concurrent": 8,
        "max_displacement": 1,
        "min_dollar_volume": MIN_AVG_DOLLAR_VOLUME_20D,
        "slippage_bps": 5.0,
        "order_semantics": "next_open_paper_only",
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "kill_switch_drawdown_pct": 0.15,
        "notes": (
            "Same accepted-helper allocator execution envelope as exp-"
            "20260611-005. This scout does not change production; positive "
            "evidence would require a shared helper and daily snapshot parity "
            "before retention."
        ),
    },
    "parity_note": (
        "Replay-only candidate microstructure scout. It reuses accepted "
        "allocator source rows and computes uniform PIT OHLCV context through "
        "the signal-day close before next-open paper entry. No source helper, "
        "daily snapshot, report, ranking, sizing, exit, watchlist, LLM/news, or "
        "order surface is changed."
    ),
}


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _round(value: Any, digits: int = 6) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _safe(payload: Any) -> Any:
    return framework._safe(payload)


def _date10(value: Any) -> str:
    return str(value or "")[:10]


def _source_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(str(row.get("source_family") or "unknown") for row in rows))


def _row_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        _date10(row.get("signal_date") or row.get("date")),
        str(row.get("ticker") or "").upper(),
        str(row.get("source_family") or "unknown"),
        _date10(row.get("entry_date")),
    )


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return min(high, max(low, value))


def _num(value: Any) -> float | None:
    rounded = _round(value, 12)
    return rounded


def _linear(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.0
    return _clamp((value - low) / (high - low))


def _band_component(
    value: float | None,
    *,
    low: float,
    best_low: float,
    best_high: float,
    high: float,
) -> float | None:
    if value is None:
        return None
    if value < low or value > high:
        return 0.0
    if best_low <= value <= best_high:
        return 1.0
    if value < best_low:
        return _linear(value, low, best_low)
    return 1.0 - _linear(value, best_high, high)


def _row_index(rows_by_ticker: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, int]]:
    return {
        str(ticker).upper(): {_date10(row.get("date")): idx for idx, row in enumerate(rows)}
        for ticker, rows in rows_by_ticker.items()
    }


def _close(rows: list[dict[str, Any]], idx: int) -> float | None:
    if idx < 0 or idx >= len(rows):
        return None
    return _num(rows[idx].get("close") or rows[idx].get("Close"))


def _ret(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    current = _close(rows, idx)
    prior_close = _close(rows, idx - lookback)
    if current is None or prior_close is None or prior_close <= 0.0:
        return None
    return current / prior_close - 1.0


def _daily_ret(rows: list[dict[str, Any]], idx: int) -> float | None:
    current = _close(rows, idx)
    prior_close = _close(rows, idx - 1)
    if current is None or prior_close is None or prior_close <= 0.0:
        return None
    return current / prior_close - 1.0


def _range_location(row: dict[str, Any]) -> float | None:
    high = _num(row.get("high") or row.get("High"))
    low = _num(row.get("low") or row.get("Low"))
    close = _num(row.get("close") or row.get("Close"))
    if high is None or low is None or close is None or high <= low:
        return None
    return _clamp((close - low) / (high - low))


def _volume_context(rows: list[dict[str, Any]], idx: int) -> tuple[float | None, float | None]:
    if idx <= 0:
        return None, None
    start = max(0, idx - 20)
    prior = rows[start:idx]
    volumes = [
        _num(row.get("volume") or row.get("Volume"))
        for row in prior
        if _num(row.get("volume") or row.get("Volume")) is not None
    ]
    if len(volumes) < 10:
        return None, None
    current_volume = _num(rows[idx].get("volume") or rows[idx].get("Volume"))
    current_close = _close(rows, idx)
    avg_volume = statistics.fmean(volumes)
    if current_volume is None or current_close is None or avg_volume <= 0.0:
        return None, None
    avg_dollar_volume = statistics.fmean(
        [
            float(row.get("volume") or row.get("Volume") or 0.0)
            * float(row.get("close") or row.get("Close") or 0.0)
            for row in prior
            if float(row.get("volume") or row.get("Volume") or 0.0) > 0.0
            and float(row.get("close") or row.get("Close") or 0.0) > 0.0
        ]
    )
    return current_volume / avg_volume, avg_dollar_volume


def _realized_vol(rows: list[dict[str, Any]], idx: int, lookback: int = 20) -> float | None:
    start = max(1, idx - lookback + 1)
    returns = []
    for pos in range(start, idx + 1):
        ret = _daily_ret(rows, pos)
        if ret is not None:
            returns.append(ret)
    if len(returns) < 10:
        return None
    return statistics.pstdev(returns)


def _ohlcv_microstructure_context(
    row: dict[str, Any],
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    date_index: dict[str, dict[str, int]],
) -> dict[str, Any]:
    ticker = str(row.get("ticker") or "").upper()
    signal_date = _date10(row.get("signal_date") or row.get("date"))
    rows = rows_by_ticker.get(ticker) or []
    spy_rows = rows_by_ticker.get("SPY") or []
    idx = date_index.get(ticker, {}).get(signal_date)
    spy_idx = date_index.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None:
        return {"status": "missing_signal_day_ohlcv"}

    ticker_ret5 = _ret(rows, idx, 5)
    ticker_ret20 = _ret(rows, idx, 20)
    ticker_ret60 = _ret(rows, idx, 60)
    spy_ret5 = _ret(spy_rows, spy_idx, 5)
    spy_ret20 = _ret(spy_rows, spy_idx, 20)
    spy_ret60 = _ret(spy_rows, spy_idx, 60)
    ticker_day = _daily_ret(rows, idx)
    spy_day = _daily_ret(spy_rows, spy_idx)
    volume_ratio, avg_dollar_volume = _volume_context(rows, idx)
    return {
        "status": "ok",
        "ret5_excess_spy": (
            None if ticker_ret5 is None or spy_ret5 is None else ticker_ret5 - spy_ret5
        ),
        "ret20_excess_spy": (
            None if ticker_ret20 is None or spy_ret20 is None else ticker_ret20 - spy_ret20
        ),
        "ret60_excess_spy": (
            None if ticker_ret60 is None or spy_ret60 is None else ticker_ret60 - spy_ret60
        ),
        "signal_day_return": ticker_day,
        "signal_relative_vs_spy": (
            None if ticker_day is None or spy_day is None else ticker_day - spy_day
        ),
        "close_location": _range_location(rows[idx]),
        "volume_ratio_20d": volume_ratio,
        "avg_dollar_volume_20d": avg_dollar_volume,
        "realized_vol_20d": _realized_vol(rows, idx),
    }


def _quality_score(context: dict[str, Any]) -> dict[str, Any]:
    if context.get("status") != "ok":
        return {
            "ready": False,
            "score": 0.0,
            "field_count": 0,
            "reason": context.get("status") or "missing_context",
        }
    ret20 = _num(context.get("ret20_excess_spy"))
    ret60 = _num(context.get("ret60_excess_spy"))
    ret5 = _num(context.get("ret5_excess_spy"))
    signal_rel = _num(context.get("signal_relative_vs_spy"))
    close_location = _num(context.get("close_location"))
    volume_ratio = _num(context.get("volume_ratio_20d"))
    realized_vol = _num(context.get("realized_vol_20d"))
    avg_dollar_volume = _num(context.get("avg_dollar_volume_20d"))

    components: OrderedDict[str, float | None] = OrderedDict(
        [
            (
                "mid_term_relative_strength",
                _band_component(ret20, low=-0.08, best_low=0.03, best_high=0.18, high=0.35),
            ),
            (
                "longer_term_trend_confirmation",
                _band_component(ret60, low=-0.08, best_low=0.02, best_high=0.35, high=0.65),
            ),
            (
                "short_term_non_extension",
                _band_component(ret5, low=-0.12, best_low=-0.04, best_high=0.05, high=0.16),
            ),
            ("high_close_location", None if close_location is None else _clamp(close_location)),
            (
                "volume_confirmation",
                None if volume_ratio is None else _clamp((min(volume_ratio, 1.8) - 0.75) / 0.75),
            ),
            (
                "low_realized_volatility",
                None if realized_vol is None else 1.0 - _clamp((realized_vol - 0.012) / 0.045),
            ),
            (
                "signal_day_not_excessive",
                _band_component(signal_rel, low=-0.06, best_low=-0.02, best_high=0.05, high=0.16),
            ),
        ]
    )
    weights: OrderedDict[str, float] = OrderedDict(
        [
            ("mid_term_relative_strength", 0.24),
            ("longer_term_trend_confirmation", 0.16),
            ("short_term_non_extension", 0.16),
            ("high_close_location", 0.18),
            ("volume_confirmation", 0.14),
            ("low_realized_volatility", 0.08),
            ("signal_day_not_excessive", 0.04),
        ]
    )
    usable = {key: value for key, value in components.items() if value is not None}
    weight_sum = sum(weights[key] for key in usable)
    score = (
        0.0
        if weight_sum <= 0.0
        else sum(float(usable[key]) * weights[key] for key in usable) / weight_sum
    )
    ready = (
        len(usable) >= MIN_QUALITY_FIELD_COUNT
        and avg_dollar_volume is not None
        and avg_dollar_volume >= MIN_AVG_DOLLAR_VOLUME_20D
    )
    reason = "ready" if ready else "insufficient_fields_or_liquidity"
    return {
        "ready": ready,
        "score": round(score, 6),
        "field_count": len(usable),
        "reason": reason,
        "components": {key: _round(value, 6) for key, value in components.items()},
        "inputs": {
            "ret5_excess_spy": _round(ret5, 6),
            "ret20_excess_spy": _round(ret20, 6),
            "ret60_excess_spy": _round(ret60, 6),
            "signal_relative_vs_spy": _round(signal_rel, 6),
            "close_location": _round(close_location, 6),
            "volume_ratio_20d": _round(volume_ratio, 6),
            "realized_vol_20d": _round(realized_vol, 6),
            "avg_dollar_volume_20d": _round(avg_dollar_volume, 2),
        },
    }


def _enrich_source_rows(
    source_rows: list[dict[str, Any]],
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    date_index = _row_index(rows_by_ticker)
    enriched: list[dict[str, Any]] = []
    for row in source_rows:
        context = _ohlcv_microstructure_context(
            row,
            rows_by_ticker=rows_by_ticker,
            date_index=date_index,
        )
        quality = _quality_score(context)
        enriched.append(
            {
                **deepcopy(row),
                "candidate_microstructure_context": context,
                "candidate_microstructure_quality": quality,
            }
        )
    return enriched


def _prepared_candidate(
    row: dict[str, Any],
    *,
    selected_by: str,
    accepted_priority_winner: dict[str, Any],
) -> dict[str, Any]:
    source_family = str(row.get("source_family") or "unknown")
    normalised = _normalise_source_row(row, source_family)
    signal_date = _date10(row.get("signal_date") or row.get("date"))
    ticker = str(row.get("ticker") or "").upper()
    out = {
        **deepcopy(row),
        **normalised,
        "source": SLEEVE_NAME,
        "sleeve": SLEEVE_NAME,
        "rule_version": MICROSTRUCTURE_RULE_VERSION,
        "source_rule_version": ACCEPTED_ALLOCATOR_SOURCE_RULE_VERSION,
        "decision_id": (
            f"{SLEEVE_NAME}:{MICROSTRUCTURE_RULE_VERSION}:"
            f"{signal_date}:{ticker}:{source_family}"
        ),
        "accepted_allocator_decision_id": _decision_id(normalised),
        "accepted_priority_winner_key": _row_key(accepted_priority_winner),
        "candidate_score": _allocator_score(normalised),
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "notional_usd": BASE_NOTIONAL_USD,
        "paper_status": "closed",
        "trade_enabled": False,
        "alters_orders": False,
        "candidate_microstructure_selected_by": selected_by,
    }
    return out


def _select_candidate_microstructure_rows(
    *,
    source_rows: list[dict[str, Any]],
    trading_dates: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    candidates = [
        _normalise_source_row(row, str(row.get("source_family") or ""))
        for row in source_rows
        if str(row.get("source_family") or "") in SOURCE_PRIORITY
    ]
    candidates.sort(
        key=lambda row: (
            _date10(row.get("signal_date") or row.get("date")),
            int(row.get("source_priority_rank") or 999),
            -_float(row.get("source_priority_score")),
            str(row.get("ticker") or ""),
        )
    )
    by_date: dict[str, list[dict[str, Any]]] = {}
    for row in candidates:
        signal_date = _date10(row.get("signal_date") or row.get("date"))
        if signal_date:
            by_date.setdefault(signal_date, []).append(row)

    date_position = {date_value: idx for idx, date_value in enumerate(trading_dates)}
    next_allowed_pos_by_ticker: dict[str, int] = {}
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    selected_source_counts: Counter[str] = Counter()
    rejected_reasons: Counter[str] = Counter()
    quality_selected_count = 0
    fallback_selected_count = 0
    changed_source_count = 0
    ready_candidate_count = 0
    quality_samples: list[dict[str, Any]] = []

    for signal_date in sorted(by_date):
        raw_day_rows = by_date[signal_date]
        pos = date_position.get(signal_date)
        if pos is None:
            for row in raw_day_rows:
                rejected.append({**row, "filter_reason": "missing_signal_date_position"})
                rejected_reasons["missing_signal_date_position"] += 1
            continue

        day_rows: list[dict[str, Any]] = []
        for row in raw_day_rows:
            ticker = str(row.get("ticker") or "").upper()
            if pos < next_allowed_pos_by_ticker.get(ticker, -1):
                rejected.append({**row, "filter_reason": "same_ticker_cooldown"})
                rejected_reasons["same_ticker_cooldown"] += 1
                continue
            day_rows.append(row)
            if (row.get("candidate_microstructure_quality") or {}).get("ready"):
                ready_candidate_count += 1

        if not day_rows:
            continue

        accepted_priority_winner = min(
            day_rows,
            key=lambda row: (
                int(row.get("source_priority_rank") or 999),
                -_float(row.get("source_priority_score")),
                str(row.get("ticker") or ""),
            ),
        )
        accepted_quality = accepted_priority_winner.get("candidate_microstructure_quality") or {}
        accepted_quality_score = _float(accepted_quality.get("score"))
        ready_rows = [
            row
            for row in day_rows
            if (row.get("candidate_microstructure_quality") or {}).get("ready")
        ]
        if ready_rows:
            quality_winner = max(
                ready_rows,
                key=lambda row: (
                    _float((row.get("candidate_microstructure_quality") or {}).get("score")),
                    -int(row.get("source_priority_rank") or 999),
                    _float(row.get("source_priority_score")),
                    str(row.get("ticker") or ""),
                ),
            )
            quality_score = _float(
                (quality_winner.get("candidate_microstructure_quality") or {}).get("score")
            )
            can_switch = (
                quality_score >= MIN_QUALITY_SCORE
                and quality_score >= accepted_quality_score + QUALITY_SWITCH_MARGIN
            )
        else:
            quality_winner = accepted_priority_winner
            quality_score = accepted_quality_score
            can_switch = False

        if can_switch:
            winner = quality_winner
            selected_by = "candidate_microstructure_quality"
            quality_selected_count += 1
        else:
            winner = accepted_priority_winner
            selected_by = "accepted_priority_fallback"
            fallback_selected_count += 1

        if _row_key(winner) != _row_key(accepted_priority_winner):
            changed_source_count += 1

        winner_out = _prepared_candidate(
            winner,
            selected_by=selected_by,
            accepted_priority_winner=accepted_priority_winner,
        )
        selected.append(winner_out)
        selected_source_counts[str(winner_out.get("source_family") or "unknown")] += 1
        next_allowed_pos_by_ticker[str(winner_out.get("ticker") or "").upper()] = (
            pos + SAME_TICKER_COOLDOWN_DAYS
        )

        for row in day_rows:
            if _row_key(row) == _row_key(winner):
                continue
            rejected.append(
                {
                    **row,
                    "filter_reason": "daily_top1_candidate_microstructure_limit",
                    "candidate_microstructure_selected_winner": _row_key(winner),
                }
            )
            rejected_reasons["daily_top1_candidate_microstructure_limit"] += 1

        if len(quality_samples) < 40:
            for row in sorted(
                day_rows,
                key=lambda item: (
                    -_float((item.get("candidate_microstructure_quality") or {}).get("score")),
                    int(item.get("source_priority_rank") or 999),
                    str(item.get("ticker") or ""),
                ),
            )[:3]:
                quality_samples.append(
                    {
                        "signal_date": signal_date,
                        "ticker": str(row.get("ticker") or ""),
                        "source_family": str(row.get("source_family") or ""),
                        "source_priority_rank": row.get("source_priority_rank"),
                        "source_priority_score": row.get("source_priority_score"),
                        "candidate_microstructure_quality": row.get(
                            "candidate_microstructure_quality"
                        ),
                        "selected": _row_key(row) == _row_key(winner),
                        "selected_by": selected_by,
                        "accepted_priority_winner": _row_key(accepted_priority_winner),
                    }
                )

    audit = {
        "rule_version": MICROSTRUCTURE_RULE_VERSION,
        "candidate_count": len(candidates),
        "selected_count": len(selected),
        "quality_selected_count": quality_selected_count,
        "fallback_selected_count": fallback_selected_count,
        "ready_candidate_count": ready_candidate_count,
        "changed_source_count_vs_same_day_priority": changed_source_count,
        "selected_source_counts": dict(selected_source_counts),
        "rejected_reasons": dict(rejected_reasons),
        "quality_parameters": {
            "min_quality_score": MIN_QUALITY_SCORE,
            "quality_switch_margin": QUALITY_SWITCH_MARGIN,
            "min_quality_field_count": MIN_QUALITY_FIELD_COUNT,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
        },
        "quality_samples": quality_samples,
        "known_at": (
            "after signal-day close and before next-open paper entry; OHLCV "
            "context uses only prices/volume through the signal-day close and "
            "same-run accepted allocator source rows."
        ),
    }
    return selected, rejected, audit


def _target_summary(rows_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    return framework.sleeve._target_trade_summary(rows_by_window)


def _top5_positive_share(target_summary: dict[str, Any]) -> float | None:
    positive = target_summary.get("positive_by_ticker_pnl") or {}
    total = sum(float(value) for value in positive.values())
    if total <= 0.0:
        return None
    top5 = sum(sorted((float(value) for value in positive.values()), reverse=True)[:5])
    return round(top5 / total, 6)


def _gate4(
    *,
    aggregate_vs_core: dict[str, Any],
    aggregate_vs_accepted: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
    accepted_to_micro_rows: OrderedDict[str, dict[str, Any]],
    changed_selection_count: int,
) -> dict[str, Any]:
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    failed: list[str] = []
    direct_ev = float(aggregate_vs_accepted["expected_value_score_delta_sum"] or 0.0)
    direct_pnl = float(aggregate_vs_accepted["total_pnl_delta_sum"] or 0.0)
    if direct_ev <= 0.0:
        failed.append("direct_ev_vs_accepted_allocator_not_positive")
    if direct_pnl <= 0.0:
        failed.append("direct_pnl_vs_accepted_allocator_not_positive")
    if int(aggregate_vs_accepted["windows_ev_regressed"] or 0) > 0:
        failed.append("direct_window_ev_regression_vs_accepted_allocator")
    if int(aggregate_vs_accepted["windows_pnl_regressed"] or 0) > 0:
        failed.append("direct_window_pnl_regression_vs_accepted_allocator")
    if float(aggregate_vs_accepted["max_drawdown_delta_max"] or 0.0) > MAX_DRAWDOWN_WORSE:
        failed.append("direct_drawdown_drift_too_high")
    if int(target_summary["total_trade_count"] or 0) < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_summary["windows_with_target_trades"]) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if changed_selection_count < MIN_CHANGED_SELECTIONS:
        failed.append("changed_selection_sample_too_small")
    if min_survival < 0.05:
        failed.append("core_survival_rate_below_5pct")
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    if not concentration_passed:
        failed.append("target_concentration_failed")
    if float(aggregate_vs_core["expected_value_score_delta_sum"] or 0.0) <= (
        ACCEPTED_ALLOCATOR_COMPARATOR["aggregate_ev_delta"]
    ):
        failed.append("accepted_allocator_ev_comparator_not_beaten")
    if float(aggregate_vs_core["total_pnl_delta_sum"] or 0.0) <= (
        ACCEPTED_ALLOCATOR_COMPARATOR["aggregate_pnl_delta"]
    ):
        failed.append("accepted_allocator_pnl_comparator_not_beaten")

    comparator_regressions: list[str] = []
    for label, row in accepted_to_micro_rows.items():
        delta = row["delta"]
        if float(delta.get("expected_value_score") or 0.0) < 0.0:
            comparator_regressions.append(f"{label}_direct_ev")
        if float(delta.get("total_pnl") or 0.0) < 0.0:
            comparator_regressions.append(f"{label}_direct_pnl")

    numeric_passed = not failed
    if numeric_passed:
        decision = "positive_replay_lead_not_promoted_candidate_microstructure_allocator"
        failed.append("shared_helper_parity_missing_for_acceptance")
    else:
        decision = "rejected_candidate_microstructure_allocator"
    return {
        "passed": False,
        "numeric_gate4_passed": numeric_passed,
        "decision": decision,
        "failed_reasons": failed,
        "comparator_regressions": comparator_regressions,
        "direct_ev_delta_vs_accepted_allocator": round(direct_ev, 6),
        "direct_pnl_delta_vs_accepted_allocator": round(direct_pnl, 2),
        "aggregate_ev_delta_vs_core": aggregate_vs_core["expected_value_score_delta_sum"],
        "aggregate_pnl_delta_vs_core": aggregate_vs_core["total_pnl_delta_sum"],
        "direct_windows_ev_improved": aggregate_vs_accepted["windows_ev_improved"],
        "direct_windows_ev_regressed": aggregate_vs_accepted["windows_ev_regressed"],
        "direct_windows_pnl_improved": aggregate_vs_accepted["windows_pnl_improved"],
        "direct_windows_pnl_regressed": aggregate_vs_accepted["windows_pnl_regressed"],
        "max_direct_drawdown_worse": aggregate_vs_accepted["max_drawdown_delta_max"],
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "changed_selection_count": changed_selection_count,
        "changed_selection_count_min": MIN_CHANGED_SELECTIONS,
        "target_trade_count": target_summary["total_trade_count"],
        "target_trade_count_min": MIN_TARGET_TRADES,
        "target_windows": target_summary["windows_with_target_trades"],
        "target_window_count_min": MIN_TARGET_WINDOWS,
        "minimum_core_survival_rate": round(min_survival, 6),
        "survival_guard_passed": min_survival >= 0.05,
        "accepted_allocator_comparator": ACCEPTED_ALLOCATOR_COMPARATOR,
        "target_concentration": {
            "passed": concentration_passed,
            "max_single_positive_pnl_share": target_summary[
                "max_single_positive_pnl_share"
            ],
            "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi": target_summary["positive_pnl_hhi"],
            "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
            "top5_positive_share": _top5_positive_share(target_summary),
        },
        "note": (
            "Even if numeric Gate 4 passes, this runner is not accepted alpha "
            "because the shared daily allocator helper was not changed."
        ),
    }


def build_payload() -> dict[str, Any]:
    timestamp = framework._utc_now()
    gate2_open_positions = framework.sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position check failed: {gate2_open_positions}")

    universe = sorted(get_universe())
    sector_entries = framework._load_sector_entries()
    before_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    accepted_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    micro_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    core_to_accepted_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    core_to_micro_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    accepted_to_micro_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    accepted_trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    micro_trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    source_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    accepted_priority_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    micro_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    baseline_results: OrderedDict[str, dict[str, Any]] = OrderedDict()

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] canonical core baseline")
        before_result = framework.shadow._run_baseline(universe, cfg)
        baseline_results[label] = before_result
        before_metrics[label] = framework.overlay_helper._metrics(before_result)

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] candidate-microstructure allocator")
        before_result = baseline_results[label]
        before = before_metrics[label]
        snapshot = prior._load_window_snapshot_deep_readonly(
            cfg=cfg,
            eligible_tickers=set(sector_entries),
        )
        window_sector_entries = {
            ticker: meta for ticker, meta in sector_entries.items() if ticker in snapshot
        }
        candidate_universe = prior._candidate_universe_from_sector_entries(
            window_sector_entries
        )
        core_entries = framework.shadow._baseline_entries(before_result)
        calendar_dates = framework.shadow._trading_dates(snapshot)
        dates = [day for day in calendar_dates if str(cfg["start"]) <= day <= str(cfg["end"])]
        source_trades, source_audit = _build_source_trades(
            rows_by_ticker=snapshot,
            dates=dates,
            window_label=label,
            window=cfg,
            core_entries_by_date=core_entries,
            sector_entries=window_sector_entries,
            candidate_universe=candidate_universe,
            calendar_dates=calendar_dates,
        )
        enriched_source_trades = _enrich_source_rows(
            source_trades,
            rows_by_ticker=snapshot,
        )
        accepted_selected, accepted_filtered, accepted_priority_audit = (
            select_accepted_helper_source_priority_rows(
                source_rows=enriched_source_trades,
                trading_dates=dates,
                config=None,
                create_trades=True,
            )
        )
        micro_selected, micro_filtered, micro_audit = _select_candidate_microstructure_rows(
            source_rows=enriched_source_trades,
            trading_dates=dates,
        )

        accepted_overlay = framework.sleeve._overlay_from_paper_trades(
            before_result,
            accepted_selected,
        )
        micro_overlay = framework.sleeve._overlay_from_paper_trades(
            before_result,
            micro_selected,
        )
        accepted_after = framework.overlay_helper._metrics_with_overlay(
            before_result,
            accepted_overlay,
        )
        micro_after = framework.overlay_helper._metrics_with_overlay(
            before_result,
            micro_overlay,
        )
        accepted_delta = framework.overlay_helper._delta(accepted_after, before)
        micro_delta = framework.overlay_helper._delta(micro_after, before)
        direct_delta = framework.overlay_helper._delta(micro_after, accepted_after)

        accepted_keys = {_row_key(row) for row in accepted_selected}
        micro_keys = {_row_key(row) for row in micro_selected}
        changed_keys = sorted(accepted_keys.symmetric_difference(micro_keys))

        accepted_metrics[label] = accepted_after
        micro_metrics[label] = micro_after
        accepted_trades_by_window[label] = accepted_selected
        micro_trades_by_window[label] = micro_selected
        source_audit_by_window[label] = source_audit
        accepted_priority_audit_by_window[label] = accepted_priority_audit
        micro_audit_by_window[label] = micro_audit
        core_to_accepted_rows[label] = {
            "before": before,
            "after": accepted_after,
            "delta": accepted_delta,
            "target_trade_count": len(accepted_selected),
            "selected_source_counts": _source_counts(accepted_selected),
            "filtered_daily_top1_count": sum(
                1
                for row in accepted_filtered
                if row.get("filter_reason") == "daily_top1_source_priority_limit"
            ),
        }
        core_to_micro_rows[label] = {
            "before": before,
            "after": micro_after,
            "delta": micro_delta,
            "target_trade_count": len(micro_selected),
            "selected_source_counts": _source_counts(micro_selected),
            "quality_selected_count": micro_audit["quality_selected_count"],
            "fallback_selected_count": micro_audit["fallback_selected_count"],
            "changed_selection_count": len(changed_keys) // 2,
            "source_trade_counts": source_audit["source_trade_counts"],
        }
        accepted_to_micro_rows[label] = {
            "before": accepted_after,
            "after": micro_after,
            "delta": direct_delta,
            "target_trade_count": len(micro_selected),
            "changed_selection_count": len(changed_keys) // 2,
            "accepted_selected_source_counts": _source_counts(accepted_selected),
            "micro_selected_source_counts": _source_counts(micro_selected),
            "micro_rejected_count": len(micro_filtered),
        }

    aggregate_core_to_accepted = framework._aggregate_window_rows(core_to_accepted_rows)
    aggregate_core_to_micro = framework._aggregate_window_rows(core_to_micro_rows)
    aggregate_accepted_to_micro = framework._aggregate_window_rows(accepted_to_micro_rows)
    micro_summary = _target_summary(micro_trades_by_window)
    accepted_summary = _target_summary(accepted_trades_by_window)
    changed_selection_count = sum(
        int(row["changed_selection_count"]) for row in accepted_to_micro_rows.values()
    )
    gate4 = _gate4(
        aggregate_vs_core=aggregate_core_to_micro,
        aggregate_vs_accepted=aggregate_accepted_to_micro,
        target_summary=micro_summary,
        before_metrics=before_metrics,
        accepted_to_micro_rows=accepted_to_micro_rows,
        changed_selection_count=changed_selection_count,
    )

    if gate4["numeric_gate4_passed"]:
        status = "positive_replay_lead"
        interpretation = (
            "The candidate microstructure allocator numerically beat the "
            "accepted allocator, but it is not retained because shared helper "
            "and daily snapshot parity were not implemented."
        )
        reflection = (
            "Candidate-level PIT OHLCV quality appears to explain part of the "
            "same-day source-choice gap without future PnL. The result is only "
            "a lead until the same field is implemented in the shared default-"
            "off allocator helper and production snapshot."
        )
    else:
        status = "rejected"
        interpretation = (
            "The candidate microstructure allocator failed the accepted "
            "allocator comparison; no strategy or production behavior is retained."
        )
        reflection = (
            "The microstructure quality proxy did not improve fixed source "
            "priority robustly enough across the canonical windows. This "
            "suggests the exp-20260613-003 oracle gap is not explained by a "
            "simple mid-trend/high-close/volume/low-extension OHLCV bundle, or "
            "the true switch field needs forward replacement evidence rather "
            "than frozen-window candidate quality scoring."
        )

    actual_success = bool(gate4["numeric_gate4_passed"])
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "owner": OWNER,
        "lane": "alpha_search",
        "status": status,
        "decision": gate4["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "change_type": "candidate_pool_allocation",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": (
            "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
        ),
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "uniform PIT OHLCV microstructure for accepted source rows",
        "nearby_prior_experiments": [
            "exp-20260611-005",
            "exp-20260613-003",
            "exp-20260613-004",
            "exp-20260613-006",
        ],
        "prior_trial_count": 3,
        "prediction": PREDICTION,
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_gate4_passed": actual_success,
            "actual_success": int(actual_success),
            "actual_ev_delta_vs_accepted_allocator": gate4[
                "direct_ev_delta_vs_accepted_allocator"
            ],
            "actual_pnl_delta_vs_accepted_allocator": gate4[
                "direct_pnl_delta_vs_accepted_allocator"
            ],
            "brier_score": round(
                (PREDICTION["success_probability"] - (1.0 if actual_success else 0.0))
                ** 2,
                6,
            ),
            "failure_modes_observed": gate4["failed_reasons"],
            "predicted_failure_mode_hit": bool(
                set(PREDICTION["main_failure_modes"])
                & set(gate4["failed_reasons"])
            ),
        },
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "accepted-helper allocator overlay and replay-only candidate "
                "microstructure variant"
            ),
            "windows": framework.WINDOWS,
            "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
            "accepted_allocator_rule_version": ACCEPTED_ALLOCATOR_RULE_VERSION,
            "accepted_allocator_source_rule_version": ACCEPTED_ALLOCATOR_SOURCE_RULE_VERSION,
            "candidate_microstructure_rule_version": MICROSTRUCTURE_RULE_VERSION,
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
        },
        "parameters": {
            "min_quality_score": MIN_QUALITY_SCORE,
            "quality_switch_margin": QUALITY_SWITCH_MARGIN,
            "min_quality_field_count": MIN_QUALITY_FIELD_COUNT,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
            "quality_components": [
                "ret20_excess_spy_mid_term_relative_strength",
                "ret60_excess_spy_trend_confirmation",
                "ret5_excess_spy_short_term_non_extension",
                "signal_day_not_excessive",
                "close_location",
                "volume_ratio_20d",
                "realized_vol_20d",
            ],
            "fallback": (
                "accepted fixed source priority unless the quality winner is "
                "ready, >= min score, and beats the accepted priority winner by "
                "the fixed margin"
            ),
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "daily_entry_slots": 1,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "locked_variables": [
                "source_priority_rank",
                "top1_per_day",
                "notional",
                "hold_days",
                "cooldown",
                "core_strategy",
                "live_orders",
            ],
        },
        "gate1": {
            "passed": True,
            "baseline_metrics": before_metrics,
            "baseline_artifact": (
                "docs/backtesting.md current canonical baseline and same-run "
                "before_metrics inside this artifact"
            ),
        },
        "gate2": {
            "passed": True,
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "warehouse OHLCV Date/Open/High/Low/Close/Volume",
                "accepted allocator source rows signal_date/ticker/source_family",
                "computed PIT microstructure fields through signal-day close",
            ],
            "local_measurement_note": (
                "This runner uses the same immutable read-only SQLite snapshot "
                "loader as exp-20260613-006. Query SQL, date range, fields, and "
                "ticker universe match the canonical allocator replay pattern."
            ),
        },
        "gate3": {
            "passed": min(
                float(row.get("survival_rate") or 0.0) for row in before_metrics.values()
            )
            >= 0.05,
            "new_core_filter_added": False,
            "candidate_pool_changed": True,
            "minimum_core_survival_rate": _round(
                min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values()),
                6,
            ),
            "note": "Default-off paper allocator only; core signals/survival unchanged.",
        },
        "gate4": gate4,
        "before_metrics": before_metrics,
        "accepted_allocator_metrics": accepted_metrics,
        "candidate_microstructure_metrics": micro_metrics,
        "delta_metrics": {
            "core_to_accepted_allocator": {
                "by_window": OrderedDict(
                    (label, row["delta"]) for label, row in core_to_accepted_rows.items()
                ),
                "aggregate": aggregate_core_to_accepted,
            },
            "core_to_candidate_microstructure": {
                "by_window": OrderedDict(
                    (label, row["delta"]) for label, row in core_to_micro_rows.items()
                ),
                "aggregate": aggregate_core_to_micro,
            },
            "accepted_allocator_to_candidate_microstructure": {
                "by_window": OrderedDict(
                    (label, row["delta"]) for label, row in accepted_to_micro_rows.items()
                ),
                "aggregate": aggregate_accepted_to_micro,
            },
        },
        "window_rows": {
            "core_to_accepted_allocator": core_to_accepted_rows,
            "core_to_candidate_microstructure": core_to_micro_rows,
            "accepted_allocator_to_candidate_microstructure": accepted_to_micro_rows,
        },
        "accepted_trade_summary": accepted_summary,
        "candidate_microstructure_trade_summary": micro_summary,
        "accepted_trades_by_window": accepted_trades_by_window,
        "candidate_microstructure_trades_by_window": micro_trades_by_window,
        "source_audit_by_window": source_audit_by_window,
        "accepted_priority_audit_by_window": accepted_priority_audit_by_window,
        "candidate_microstructure_audit_by_window": micro_audit_by_window,
        "production_impact": PRODUCTION_IMPACT,
        "accepted_comparators": {
            "accepted_allocator": ACCEPTED_ALLOCATOR_COMPARATOR,
            "same_run_accepted_allocator_control": aggregate_core_to_accepted,
        },
        "interpretation": interpretation,
        "rejection_reason": None if gate4["numeric_gate4_passed"] else "; ".join(
            gate4["failed_reasons"]
        ),
        "post_run_reflection": {
            "why_result_happened": reflection,
            "negative_reflection": (
                "If rejected, the mid-trend/high-close/volume/low-extension "
                "bundle is too blunt to explain source-choice replacement. If "
                "positive, the result remains non-accepted because shared helper "
                "parity is missing."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry by sweeping quality thresholds, quality weights, "
                "source ranks, allocator top-N, notional, hold days, cooldown, "
                "or fixed state cells on the same frozen windows."
            ),
            "new_evidence_required": (
                "A valid retry needs closed forward source-competition "
                "replacement rows, a materially richer PIT relation field, or a "
                "shared daily helper recording the field before replay promotion."
            ),
        },
        "next_retry_requires": [
            "closed forward source-competition replacement rows",
            "shared helper plus daily parity if any microstructure field is promoted",
            "no frozen-window threshold/weight sweep",
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _window_table(payload: dict[str, Any]) -> list[str]:
    rows = [
        "| Window | Core EV | Accepted EV | Micro EV | Direct dEV | Core PnL | Accepted dPnL | Micro dPnL | Direct dPnL | Changed | Quality selected |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        core = payload["before_metrics"][label]
        accepted_row = payload["window_rows"]["core_to_accepted_allocator"][label]
        micro_row = payload["window_rows"]["core_to_candidate_microstructure"][label]
        direct_row = payload["window_rows"][
            "accepted_allocator_to_candidate_microstructure"
        ][label]
        rows.append(
            "| {label} | {core_ev:.4f} | {accepted_ev:.4f} | {micro_ev:.4f} | {direct_ev:+.4f} | ${core_pnl:,.2f} | ${accepted_dpnl:+,.2f} | ${micro_dpnl:+,.2f} | ${direct_dpnl:+,.2f} | {changed} | {quality_selected} |".format(
                label=label,
                core_ev=core["expected_value_score"],
                accepted_ev=accepted_row["after"]["expected_value_score"],
                micro_ev=micro_row["after"]["expected_value_score"],
                direct_ev=direct_row["delta"]["expected_value_score"],
                core_pnl=core["total_pnl"],
                accepted_dpnl=accepted_row["delta"]["total_pnl"],
                micro_dpnl=micro_row["delta"]["total_pnl"],
                direct_dpnl=direct_row["delta"]["total_pnl"],
                changed=direct_row["changed_selection_count"],
                quality_selected=micro_row["quality_selected_count"],
            )
        )
    return rows


def _build_card(payload: dict[str, Any]) -> str:
    direct = payload["delta_metrics"][
        "accepted_allocator_to_candidate_microstructure"
    ]["aggregate"]
    core_to_micro = payload["delta_metrics"][
        "core_to_candidate_microstructure"
    ]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Candidate Microstructure Allocator",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4 Three-Window Readout",
            "",
            *_window_table(payload),
            "",
            "- Direct EV delta vs accepted allocator: `{:+.4f}`".format(
                direct["expected_value_score_delta_sum"]
            ),
            "- Direct PnL delta vs accepted allocator: `${:+,.2f}`".format(
                direct["total_pnl_delta_sum"]
            ),
            "- Microstructure aggregate EV delta vs core: `{:+.4f}`".format(
                core_to_micro["expected_value_score_delta_sum"]
            ),
            "- Microstructure aggregate PnL delta vs core: `${:+,.2f}`".format(
                core_to_micro["total_pnl_delta_sum"]
            ),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "",
            "## Production Impact",
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    direct = payload["delta_metrics"][
        "accepted_allocator_to_candidate_microstructure"
    ]["aggregate"]
    core_to_micro = payload["delta_metrics"][
        "core_to_candidate_microstructure"
    ]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "production_accepted": False,
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": payload["gate1"]["baseline_artifact"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "direct_expected_value_delta_vs_accepted_allocator": direct[
            "expected_value_score_delta_sum"
        ],
        "direct_pnl_delta_vs_accepted_allocator": direct["total_pnl_delta_sum"],
        "aggregate_expected_value_delta": core_to_micro[
            "expected_value_score_delta_sum"
        ],
        "aggregate_strategy_total_pnl_delta": core_to_micro["total_pnl_delta_sum"],
        "accepted_comparators": payload["accepted_comparators"],
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label][
                    "expected_value_score"
                ],
                "accepted_allocator_expected_value": payload[
                    "accepted_allocator_metrics"
                ][label]["expected_value_score"],
                "candidate_microstructure_expected_value": payload[
                    "candidate_microstructure_metrics"
                ][label]["expected_value_score"],
                "direct_expected_value_delta_vs_accepted": payload["delta_metrics"][
                    "accepted_allocator_to_candidate_microstructure"
                ]["by_window"][label]["expected_value_score"],
                "direct_pnl_delta_vs_accepted": payload["delta_metrics"][
                    "accepted_allocator_to_candidate_microstructure"
                ]["by_window"][label]["total_pnl"],
                "changed_selection_count": payload["window_rows"][
                    "accepted_allocator_to_candidate_microstructure"
                ][label]["changed_selection_count"],
                "quality_selected_count": payload["window_rows"][
                    "core_to_candidate_microstructure"
                ][label]["quality_selected_count"],
                "selected_source_counts": payload["window_rows"][
                    "core_to_candidate_microstructure"
                ][label]["selected_source_counts"],
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _load_json(TICKET_JSON, {})
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "decision": payload["decision"],
            "summary": payload["interpretation"],
            "prediction": PREDICTION,
            "calibration": payload["calibration"],
            "result": {
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "card": _repo_rel(CARD_MD),
                "gate4": payload["gate4"],
                "accepted": False,
                "calibration": payload["calibration"],
                "post_run_reflection": payload["post_run_reflection"],
                "production_impact": PRODUCTION_IMPACT,
            },
        }
    )
    scope = set(ticket.get("allowed_write_scope") or [])
    scope.update(payload["related_files"])
    ticket["allowed_write_scope"] = sorted(scope)
    framework._write_json(TICKET_JSON, ticket)


def _write_manifest(payload: dict[str, Any]) -> None:
    paths = [Path(__file__), OUT_JSON, LOG_JSON, TICKET_JSON, CARD_MD, MANIFEST_JSON]
    file_hashes: dict[str, str] = {}
    for path in paths:
        resolved = path if path.is_absolute() else REPO_ROOT / path
        if resolved.exists():
            file_hashes[_repo_rel(resolved)] = framework._sha256(resolved)
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [_repo_rel(path) for path in paths],
        "file_hashes": file_hashes,
        "global_registry_note": (
            "Reservation/claim touched global registry/log. Closeout artifact, "
            "log, card, ticket, and manifest were written per experiment so "
            "unrelated dirty automation state is not mixed into strategy files."
        ),
    }
    framework._write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, log_record)
    framework._write_text(CARD_MD, _build_card(payload))
    _update_ticket(payload)
    _write_manifest(payload)


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            _safe(_build_log_record(payload)),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
