"""exp-20260514-021: Space IRDM forward-candidate risk.

Tests one candidate-pool/risk variable on top of the accepted exp-20260514-009
default-off Space stack: whether IRDM deserves a bounded risk budget only when
the base strategy is trend_long after the closed Golden Dome/defense-budget
forward ledger shows positive 10d cash, UFO, and SPY-relative value despite
negative same-theme replacement value.

This deliberately avoids broad satcom breadth, VSAT/GSAT/SATS, LLM soft-ranking, entries, exits, targets, ranking, or live Space slots. It is a replay-only alpha search,
with non-trend IRDM signals forced to zero risk inside the same candidate gate.
"""

from __future__ import annotations

import json
import logging
import sys
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = PROJECT_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for path in (str(QUANT_DIR), str(EXPERIMENTS_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import portfolio_engine
from data_layer import get_universe
import exp_20260513_038_space_source_diversity_risk as source_diversity_exp
import exp_20260514_002_space_forward_replacement_same_theme_strength_risk as same_theme_exp


logging.getLogger("yfinance").setLevel(logging.CRITICAL)
logging.getLogger("portfolio_engine").setLevel(logging.ERROR)

EXPERIMENT_ID = "exp-20260514-021"
STEM = "space_irdm_forward_candidate_risk"
BEFORE_EXPERIMENT_ID = "exp-20260514-009"

ACCEPTED_ATTENTION_OVERLAY_RISK_SCALAR = 1.25
ACCEPTED_SOURCE_DIVERSITY_RISK_SCALAR = 1.075
ACCEPTED_SOURCE_DIVERSITY_PEER_LEADER_RISK_SCALAR = 1.15
ACCEPTED_SOURCE_DIVERSITY_IWM_LEADER_RISK_SCALAR = 1.05
ACCEPTED_SOURCE_DIVERSITY_PEER_IWM_LEADER_RISK_SCALAR = 1.05
ACCEPTED_FORWARD_REPLACEMENT_POSITIVE_RISK_SCALAR = 1.05
ACCEPTED_FORWARD_REPLACEMENT_SAME_THEME_STRENGTH_FLOOR = 500.0
ACCEPTED_FORWARD_REPLACEMENT_SAME_THEME_STRENGTH_RISK_SCALAR = 1.05
ACCEPTED_FORWARD_REPLACEMENT_TREND_STRENGTH_RISK_SCALAR = 1.05

FORWARD_REPLACEMENT_HORIZON = "10d"
IRDM_FORWARD_CANDIDATE_TICKERS = ("IRDM",)
IRDM_FORWARD_CANDIDATE_RISK_SCALARS = (0.25, 0.50, 0.75, 1.00)
MAX_SAME_THEME_REPLACEMENT_VALUE = 0.0
MAX_DRAWDOWN_DAMAGE_VS_BEFORE = 0.005
MIN_SURVIVAL_RATE = 0.05
MIN_TRADE_COUNT = 50
PEER_LEADER_STATE = "leader"
IWM_LEADER_STATE = "smallcap_leader"


def _safe(payload: Any) -> Any:
    return source_diversity_exp._safe(payload)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    source_diversity_exp._write_json(path, payload)


def _as_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: Any, digits: int = 4) -> Any:
    number = _as_float(value)
    if number is None:
        return None
    return round(number, digits)


def _append_jsonl_for_this_experiment(path: Path, entry: dict[str, Any]) -> None:
    lines: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                if json.loads(line).get("experiment_id") == EXPERIMENT_ID:
                    continue
            except json.JSONDecodeError:
                pass
            lines.append(line)
    lines.append(json.dumps(_safe(entry), separators=(",", ":"), sort_keys=True))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _latest_irdm_forward_rows() -> dict[tuple[str, str], dict[str, Any]]:
    path = PROJECT_ROOT / "data" / "space_catalyst_event_state_shadow_ledger.jsonl"
    latest_by_event_ticker: dict[tuple[str, str], dict[str, Any]] = {}
    target_tickers = set(IRDM_FORWARD_CANDIDATE_TICKERS)
    if not path.exists():
        return latest_by_event_ticker

    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        ticker = str(row.get("ticker") or "").upper()
        if ticker not in target_tickers:
            continue
        if row.get("closed_decision") is not True:
            continue
        if row.get("semantic_bucket") != "defense_budget_theme":
            continue
        if row.get("source_type") != "official_government_release":
            continue
        horizon = (row.get("horizons") or {}).get(FORWARD_REPLACEMENT_HORIZON) or {}
        if horizon.get("status") != "mature":
            continue
        required = (
            "cash_relative_pnl",
            "same_theme_replacement_value",
            "spy_relative_value",
            "ufo_relative_value",
        )
        if any(_as_float(horizon.get(field)) is None for field in required):
            continue
        event_id = str(row.get("event_id") or "")
        if not event_id:
            continue
        key = (event_id, ticker)
        prior = latest_by_event_ticker.get(key)
        if prior is None or str(row.get("asof_date") or "") >= str(
            prior.get("asof_date") or ""
        ):
            latest_by_event_ticker[key] = row
    return latest_by_event_ticker


def _irdm_forward_candidate_profile_gate() -> dict[str, Any]:
    rows_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in _latest_irdm_forward_rows().values():
        ticker = str(row.get("ticker") or "").upper()
        horizon = (row.get("horizons") or {}).get(FORWARD_REPLACEMENT_HORIZON) or {}
        rows_by_ticker[ticker].append(
            {
                "event_id": row.get("event_id"),
                "asof_date": row.get("asof_date"),
                "semantic_bucket": row.get("semantic_bucket"),
                "source_type": row.get("source_type"),
                "event_fields": list(row.get("event_fields") or []),
                "theme_segment": row.get("theme_segment"),
                "cash_relative_pnl": _as_float(horizon.get("cash_relative_pnl")),
                "same_theme_replacement_value": _as_float(
                    horizon.get("same_theme_replacement_value")
                ),
                "spy_relative_value": _as_float(horizon.get("spy_relative_value")),
                "qqq_relative_value": _as_float(horizon.get("qqq_relative_value")),
                "ufo_relative_value": _as_float(horizon.get("ufo_relative_value")),
                "arkx_relative_value": _as_float(horizon.get("arkx_relative_value")),
            }
        )

    profiles: dict[str, dict[str, Any]] = {}
    target_tickers: list[str] = []
    for ticker, rows in sorted(rows_by_ticker.items()):
        cash_values = [
            row["cash_relative_pnl"]
            for row in rows
            if row.get("cash_relative_pnl") is not None
        ]
        same_values = [
            row["same_theme_replacement_value"]
            for row in rows
            if row.get("same_theme_replacement_value") is not None
        ]
        spy_values = [
            row["spy_relative_value"]
            for row in rows
            if row.get("spy_relative_value") is not None
        ]
        ufo_values = [
            row["ufo_relative_value"]
            for row in rows
            if row.get("ufo_relative_value") is not None
        ]
        if not cash_values or not same_values or not spy_values or not ufo_values:
            continue
        avg_cash = mean(float(value) for value in cash_values)
        avg_same = mean(float(value) for value in same_values)
        avg_spy = mean(float(value) for value in spy_values)
        avg_ufo = mean(float(value) for value in ufo_values)
        passes = (
            avg_cash > 0.0
            and avg_same <= MAX_SAME_THEME_REPLACEMENT_VALUE
            and avg_spy > 0.0
            and avg_ufo > 0.0
        )
        profiles[ticker] = {
            "horizon": FORWARD_REPLACEMENT_HORIZON,
            "closed_event_count": len(rows),
            "avg_10d_cash_relative_pnl": round(avg_cash, 6),
            "avg_10d_same_theme_replacement_value": round(avg_same, 6),
            "avg_10d_spy_relative_value": round(avg_spy, 6),
            "avg_10d_ufo_relative_value": round(avg_ufo, 6),
            "max_same_theme_replacement_value": MAX_SAME_THEME_REPLACEMENT_VALUE,
            "passes_irdm_forward_candidate_gate": passes,
            "event_ids": sorted(
                {str(row.get("event_id")) for row in rows if row.get("event_id")}
            ),
            "source_types": sorted(
                {str(row.get("source_type")) for row in rows if row.get("source_type")}
            ),
            "semantic_buckets": sorted(
                {str(row.get("semantic_bucket")) for row in rows if row.get("semantic_bucket")}
            ),
            "rows": rows,
        }
        if passes:
            target_tickers.append(ticker)

    return {
        "passed": bool(target_tickers),
        "path": "data/space_catalyst_event_state_shadow_ledger.jsonl",
        "horizon": FORWARD_REPLACEMENT_HORIZON,
        "target_tickers": sorted(target_tickers),
        "profiles": profiles,
        "gate_definition": {
            "ticker_scope": list(IRDM_FORWARD_CANDIDATE_TICKERS),
            "semantic_bucket": "defense_budget_theme",
            "source_type": "official_government_release",
            "cash_relative_pnl": "> 0",
            "same_theme_replacement_value": f"<= {MAX_SAME_THEME_REPLACEMENT_VALUE}",
            "spy_relative_value": "> 0",
            "ufo_relative_value": "> 0",
        },
    }


def _snapshot_irdm_gate() -> dict[str, Any]:
    by_window: dict[str, dict[str, Any]] = {}
    for label, window in source_diversity_exp.WINDOWS.items():
        path = PROJECT_ROOT / window["space_snapshot"]
        present = False
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            metadata = payload.get("metadata") or {}
            augmented = set(metadata.get("space_catalyst_added_tickers") or [])
            present = "IRDM" in augmented or '"IRDM"' in path.read_text(
                encoding="utf-8-sig", errors="replace"
            )
        by_window[label] = {
            "path": window["space_snapshot"],
            "exists": path.exists(),
            "irdm_present": present,
        }
    return {
        "passed": all(row["exists"] and row["irdm_present"] for row in by_window.values()),
        "by_window": by_window,
    }


def _rounded_bucket(bucket: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for key, row in bucket.items():
        out[key] = {**row, "pnl": _round(row.get("pnl"), 2)}
    return out


def _trade_attribution_for(
    result: dict[str, Any],
    tickers: set[str],
    strategies: set[str] | None = None,
) -> dict[str, Any]:
    trades = [
        trade
        for trade in result.get("trades") or []
        if str(trade.get("ticker") or "").upper() in tickers
        and (strategies is None or str(trade.get("strategy") or "") in strategies)
    ]
    by_ticker: dict[str, dict[str, Any]] = {}
    by_strategy: dict[str, dict[str, Any]] = {}
    by_exit_reason: dict[str, dict[str, Any]] = {}
    for trade in trades:
        ticker = str(trade.get("ticker") or "").upper()
        strategy = str(trade.get("strategy") or "unknown")
        exit_reason = str(trade.get("exit_reason") or "unknown")
        pnl = float(trade.get("pnl") or 0.0)
        for bucket, key in (
            (by_ticker, ticker),
            (by_strategy, strategy),
            (by_exit_reason, exit_reason),
        ):
            row = bucket.setdefault(
                key,
                {"trade_count": 0, "wins": 0, "losses": 0, "pnl": 0.0},
            )
            row["trade_count"] += 1
            row["wins"] += int(pnl > 0)
            row["losses"] += int(pnl <= 0)
            row["pnl"] += pnl
    positive = [row["pnl"] for row in by_ticker.values() if row["pnl"] > 0]
    total_positive = sum(positive)
    wins = sum(1 for trade in trades if float(trade.get("pnl") or 0.0) > 0)
    return {
        "trade_count": len(trades),
        "wins": wins,
        "losses": len(trades) - wins,
        "win_rate": _round(wins / len(trades), 4) if trades else None,
        "total_pnl": _round(
            sum(float(trade.get("pnl") or 0.0) for trade in trades),
            2,
        ),
        "single_ticker_positive_share": _round(
            max(positive) / total_positive if total_positive else 0.0,
            4,
        ),
        "by_ticker": _rounded_bucket(by_ticker),
        "by_strategy": _rounded_bucket(by_strategy),
        "by_exit_reason": _rounded_bucket(by_exit_reason),
    }


def _scale_and_count(
    *,
    sizing: dict[str, Any],
    scalar: float,
    portfolio_value: float,
    marker: str,
    counts: Counter[str],
    ticker: str,
) -> tuple[int, int]:
    shares_before = int(sizing.get("shares_to_buy") or 0)
    source_diversity_exp._scale_sizing(sizing, scalar, portfolio_value, marker)
    shares_after = int(sizing.get("shares_to_buy") or 0)
    if shares_after != shares_before:
        counts[f"{marker}_changed_signal"] += 1
        counts[f"{marker}_changed_{ticker}"] += 1
    return shares_before, shares_after


def _run_variant(
    label: str,
    *,
    irdm_candidate_scalar: float,
    include_irdm: bool,
    ten_day_forward_gate: dict[str, Any],
    irdm_gate: dict[str, Any],
    source_diversity_gate: dict[str, Any],
    attention_gate: dict[str, Any],
    single_event_gate: dict[str, Any],
    government_contract_gate: dict[str, Any],
    source_gate: dict[str, Any],
    multi_event_gate: dict[str, Any],
    liquidity_gate: dict[str, Any],
    company_release_gate: dict[str, Any],
    financing_gate: dict[str, Any],
) -> dict[str, Any]:
    universe_seed = set(get_universe()) | set(source_diversity_exp.OFFICIAL_SPACE_TICKERS) | {
        "IWM",
        "SPY",
    }
    if include_irdm:
        universe_seed.update(IRDM_FORWARD_CANDIDATE_TICKERS)
    universe = sorted(universe_seed)
    installed = source_diversity_exp._install_space_policy(
        ACCEPTED_ATTENTION_OVERLAY_RISK_SCALAR,
        attention_gate=attention_gate,
        single_event_gate=single_event_gate,
        government_contract_gate=government_contract_gate,
        source_gate=source_gate,
        multi_event_gate=multi_event_gate,
        liquidity_gate=liquidity_gate,
        company_release_gate=company_release_gate,
        financing_gate=financing_gate,
    )
    accepted_size_signals = portfolio_engine.size_signals
    source_diverse_tickers = set(source_diversity_gate["target_tickers"])
    source_diversity_profiles = source_diversity_gate["profiles"]
    ten_day_forward_tickers = set(ten_day_forward_gate["base_target_tickers"])
    ten_day_forward_profiles = ten_day_forward_gate["profiles"]
    ten_day_strength_tickers = same_theme_exp._target_tickers_for_floor(
        ten_day_forward_gate,
        ACCEPTED_FORWARD_REPLACEMENT_SAME_THEME_STRENGTH_FLOOR,
    )
    irdm_tickers = set(irdm_gate["target_tickers"]) if include_irdm else set()
    irdm_profiles = irdm_gate["profiles"]

    adjustments: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()

    def size_with_irdm_candidate_scalar(
        signals: list[dict[str, Any]],
        portfolio_value: float,
        risk_pct: float | None = None,
    ) -> list[dict[str, Any]]:
        sized = accepted_size_signals(signals, portfolio_value, risk_pct=risk_pct)
        out: list[dict[str, Any]] = []
        for signal in sized:
            ticker = str(signal.get("ticker") or "").upper()
            strategy = str(signal.get("strategy") or "")
            sizing = deepcopy(signal.get("sizing") or {})

            if ticker in source_diverse_tickers and sizing:
                profile = source_diversity_profiles.get(ticker)
                source_diversity_exp._scale_sizing(
                    sizing,
                    ACCEPTED_SOURCE_DIVERSITY_RISK_SCALAR,
                    portfolio_value,
                    "space_source_diversity_risk",
                )
                is_peer_leader = signal.get("space_peer_momentum_state") == PEER_LEADER_STATE
                is_iwm_leader = signal.get("space_iwm_relative_state") == IWM_LEADER_STATE
                if is_peer_leader:
                    source_diversity_exp._scale_sizing(
                        sizing,
                        ACCEPTED_SOURCE_DIVERSITY_PEER_LEADER_RISK_SCALAR,
                        portfolio_value,
                        "space_source_diversity_peer_leader_risk",
                    )
                if is_iwm_leader:
                    source_diversity_exp._scale_sizing(
                        sizing,
                        ACCEPTED_SOURCE_DIVERSITY_IWM_LEADER_RISK_SCALAR,
                        portfolio_value,
                        "space_source_diversity_iwm_leader_risk",
                    )
                if is_peer_leader and is_iwm_leader:
                    source_diversity_exp._scale_sizing(
                        sizing,
                        ACCEPTED_SOURCE_DIVERSITY_PEER_IWM_LEADER_RISK_SCALAR,
                        portfolio_value,
                        "space_source_diversity_peer_iwm_leader_risk",
                    )
                signal = {
                    **signal,
                    "space_source_diversity_eligible": True,
                    "space_source_diversity_profile": profile,
                }

            if ticker in ten_day_forward_tickers and sizing:
                source_diversity_exp._scale_sizing(
                    sizing,
                    ACCEPTED_FORWARD_REPLACEMENT_POSITIVE_RISK_SCALAR,
                    portfolio_value,
                    "space_forward_replacement_positive_risk",
                )
                signal = {
                    **signal,
                    "space_forward_replacement_positive_bucket": True,
                    "space_forward_replacement_positive_scalar": (
                        ACCEPTED_FORWARD_REPLACEMENT_POSITIVE_RISK_SCALAR
                    ),
                    "space_forward_replacement_positive_profile": (
                        ten_day_forward_profiles.get(ticker)
                    ),
                }

            if ticker in ten_day_strength_tickers and sizing:
                source_diversity_exp._scale_sizing(
                    sizing,
                    ACCEPTED_FORWARD_REPLACEMENT_SAME_THEME_STRENGTH_RISK_SCALAR,
                    portfolio_value,
                    "space_forward_replacement_same_theme_strength_risk",
                )
                signal = {
                    **signal,
                    "space_forward_replacement_same_theme_strength_bucket": True,
                    "space_forward_replacement_same_theme_strength_scalar": (
                        ACCEPTED_FORWARD_REPLACEMENT_SAME_THEME_STRENGTH_RISK_SCALAR
                    ),
                    "space_forward_replacement_same_theme_strength_floor": (
                        ACCEPTED_FORWARD_REPLACEMENT_SAME_THEME_STRENGTH_FLOOR
                    ),
                }

            if ticker in ten_day_strength_tickers and strategy == "trend_long" and sizing:
                source_diversity_exp._scale_sizing(
                    sizing,
                    ACCEPTED_FORWARD_REPLACEMENT_TREND_STRENGTH_RISK_SCALAR,
                    portfolio_value,
                    "space_forward_replacement_trend_strength_risk",
                )
                signal = {
                    **signal,
                    "space_forward_replacement_trend_strength_bucket": True,
                    "space_forward_replacement_trend_strength_scalar": (
                        ACCEPTED_FORWARD_REPLACEMENT_TREND_STRENGTH_RISK_SCALAR
                    ),
                }

            if ticker in irdm_tickers and sizing:
                is_trend_candidate = strategy == "trend_long"
                applied_scalar = irdm_candidate_scalar if is_trend_candidate else 0.0
                marker = (
                    "space_irdm_forward_candidate_risk"
                    if is_trend_candidate
                    else "space_irdm_nontrend_forward_candidate_zero_risk"
                )
                counts["eligible_signal"] += 1
                counts[f"eligible_{ticker}"] += 1
                counts[f"eligible_{strategy or 'unknown'}"] += 1
                shares_before, shares_after = _scale_and_count(
                    sizing=sizing,
                    scalar=applied_scalar,
                    portfolio_value=portfolio_value,
                    marker=marker,
                    counts=counts,
                    ticker=ticker,
                )
                profile = irdm_profiles.get(ticker)
                adjustments.append(
                    {
                        "ticker": ticker,
                        "strategy": strategy,
                        "candidate_scalar": irdm_candidate_scalar,
                        "scalar": applied_scalar,
                        "target_strategy": "trend_long",
                        "nontrend_zero_risk": not is_trend_candidate,
                        "shares_before_scalar": shares_before,
                        "shares_after_scalar": shares_after,
                        "irdm_forward_candidate_profile": profile,
                        "space_peer_momentum_state": signal.get("space_peer_momentum_state"),
                        "space_iwm_relative_state": signal.get("space_iwm_relative_state"),
                        "trade_quality_score": signal.get("trade_quality_score"),
                        "confidence_score": signal.get("confidence_score"),
                    }
                )
                signal = {
                    **signal,
                    "space_irdm_trend_forward_candidate_bucket": is_trend_candidate,
                    "space_irdm_nontrend_forward_candidate_zero_risk_bucket": (
                        not is_trend_candidate
                    ),
                    "space_irdm_trend_forward_candidate_scalar": (
                        irdm_candidate_scalar if is_trend_candidate else None
                    ),
                    "space_irdm_nontrend_forward_candidate_scalar": (
                        0.0 if not is_trend_candidate else None
                    ),
                    "space_irdm_forward_candidate_profile": profile,
                }

            if sizing:
                signal = {**signal, "sizing": sizing}
            out.append(signal)
        return out

    portfolio_engine.size_signals = size_with_irdm_candidate_scalar
    try:
        by_window: dict[str, Any] = {}
        for name, window in source_diversity_exp.WINDOWS.items():
            before_adjustments = len(adjustments)
            before_counts = Counter(counts)
            result = source_diversity_exp._run_window(window, universe, "space_snapshot")
            by_window[name] = {
                "metrics": source_diversity_exp._metrics(result),
                "official_space_trade_attribution": (
                    source_diversity_exp._space_trade_attribution(result)
                ),
                "irdm_trade_attribution": _trade_attribution_for(result, {"IRDM"}),
                "irdm_trend_trade_attribution": _trade_attribution_for(
                    result,
                    {"IRDM"},
                    {"trend_long"},
                ),
                "irdm_nontrend_trade_attribution": _trade_attribution_for(
                    result,
                    {"IRDM"},
                    {"breakout_long"},
                ),
                "space_with_irdm_trade_attribution": _trade_attribution_for(
                    result,
                    set(source_diversity_exp.OFFICIAL_SPACE_TICKERS) | {"IRDM"},
                ),
                "irdm_candidate_adjustment": source_diversity_exp._adjustment_summary(
                    adjustments[before_adjustments:]
                ),
                "irdm_candidate_counts": dict(sorted((counts - before_counts).items())),
            }
        metrics_by_window = {name: row["metrics"] for name, row in by_window.items()}
        return {
            "label": label,
            "parameters": {
                "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
                "accepted_forward_replacement_positive_scalar": (
                    ACCEPTED_FORWARD_REPLACEMENT_POSITIVE_RISK_SCALAR
                ),
                "accepted_forward_replacement_same_theme_strength_floor": (
                    ACCEPTED_FORWARD_REPLACEMENT_SAME_THEME_STRENGTH_FLOOR
                ),
                "accepted_forward_replacement_same_theme_strength_scalar": (
                    ACCEPTED_FORWARD_REPLACEMENT_SAME_THEME_STRENGTH_RISK_SCALAR
                ),
                "accepted_forward_replacement_trend_strength_scalar": (
                    ACCEPTED_FORWARD_REPLACEMENT_TREND_STRENGTH_RISK_SCALAR
                ),
                "space_irdm_trend_forward_candidate_scalar": irdm_candidate_scalar,
                "space_irdm_nontrend_forward_candidate_scalar": 0.0,
                "target_irdm_strategy": "trend_long",
                "include_irdm": include_irdm,
                "target_tickers": sorted(irdm_tickers),
                "base_10d_forward_replacement_tickers": (
                    ten_day_forward_gate["base_target_tickers"]
                ),
                "same_theme_strength_target_tickers": sorted(ten_day_strength_tickers),
            },
            "by_window": by_window,
            "aggregate": source_diversity_exp._aggregate(metrics_by_window),
            "irdm_candidate_adjustment_summary": (
                source_diversity_exp._adjustment_summary(adjustments)
            ),
            "irdm_candidate_counts": dict(sorted(counts.items())),
            "irdm_candidate_adjustment_sample": adjustments[:25],
        }
    finally:
        source_diversity_exp._restore_policy(*installed["originals"])


def _aggregate_trade_attr(
    variant: dict[str, Any],
    attribution_key: str,
) -> dict[str, Any]:
    trades = []
    total_pnl = 0.0
    by_ticker: dict[str, dict[str, Any]] = {}
    by_strategy: dict[str, dict[str, Any]] = {}
    for payload in variant.get("by_window", {}).values():
        attr = payload.get(attribution_key) or {}
        total_pnl += float(attr.get("total_pnl") or 0.0)
        for bucket_name, target in (("by_ticker", by_ticker), ("by_strategy", by_strategy)):
            for key, row in (attr.get(bucket_name) or {}).items():
                dest = target.setdefault(
                    key,
                    {"trade_count": 0, "wins": 0, "losses": 0, "pnl": 0.0},
                )
                dest["trade_count"] += int(row.get("trade_count") or 0)
                dest["wins"] += int(row.get("wins") or 0)
                dest["losses"] += int(row.get("losses") or 0)
                dest["pnl"] += float(row.get("pnl") or 0.0)
        trades.extend([None] * int(attr.get("trade_count") or 0))
    wins = sum(int(row.get("wins") or 0) for row in by_ticker.values())
    trade_count = len(trades)
    positive = [row["pnl"] for row in by_ticker.values() if row["pnl"] > 0]
    total_positive = sum(positive)
    return {
        "trade_count": trade_count,
        "wins": wins,
        "losses": trade_count - wins,
        "win_rate": _round(wins / trade_count, 4) if trade_count else None,
        "total_pnl": _round(total_pnl, 2),
        "single_ticker_positive_share": _round(
            max(positive) / total_positive if total_positive else 0.0,
            4,
        ),
        "by_ticker": _rounded_bucket(by_ticker),
        "by_strategy": _rounded_bucket(by_strategy),
    }


def _gate_variant(variant: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    aggregate_delta = source_diversity_exp._aggregate_delta(
        variant["aggregate"],
        before["aggregate"],
    )
    by_window_delta = {
        name: source_diversity_exp._delta(payload["metrics"], before["by_window"][name]["metrics"])
        for name, payload in variant["by_window"].items()
    }
    ev_regressions = {
        name: delta["expected_value_score"]
        for name, delta in by_window_delta.items()
        if delta["expected_value_score"] < -1e-9
    }
    ev_improvements = {
        name: delta["expected_value_score"]
        for name, delta in by_window_delta.items()
        if delta["expected_value_score"] > 1e-9
    }
    changed_trend_count = int(
        variant["irdm_candidate_counts"].get(
            "space_irdm_forward_candidate_risk_changed_signal",
            0,
        )
    )
    changed_nontrend_zero_count = int(
        variant["irdm_candidate_counts"].get(
            "space_irdm_nontrend_forward_candidate_zero_risk_changed_signal",
            0,
        )
    )
    eligible_count = int(variant["irdm_candidate_counts"].get("eligible_signal", 0))
    eligible_trend_count = int(
        variant["irdm_candidate_counts"].get("eligible_trend_long", 0)
    )
    eligible_nontrend_count = eligible_count - eligible_trend_count
    scalar = float(variant["parameters"]["space_irdm_trend_forward_candidate_scalar"])
    irdm_trade_attr = _aggregate_trade_attr(variant, "irdm_trade_attribution")
    trend_trade_attr = _aggregate_trade_attr(variant, "irdm_trend_trade_attribution")
    nontrend_trade_attr = _aggregate_trade_attr(
        variant,
        "irdm_nontrend_trade_attribution",
    )
    return {
        "aggregate_delta_vs_before": aggregate_delta,
        "by_window_delta_vs_before": by_window_delta,
        "ev_improved_windows": ev_improvements,
        "ev_regressed_windows": ev_regressions,
        "eligible_irdm_candidate_signal_count": eligible_count,
        "eligible_irdm_trend_signal_count": eligible_trend_count,
        "eligible_irdm_nontrend_signal_count": eligible_nontrend_count,
        "changed_irdm_trend_candidate_signal_count": changed_trend_count,
        "zeroed_irdm_nontrend_candidate_signal_count": changed_nontrend_zero_count,
        "irdm_trade_attribution": irdm_trade_attr,
        "irdm_trend_trade_attribution": trend_trade_attr,
        "irdm_nontrend_trade_attribution": nontrend_trade_attr,
        "accepted": bool(
            scalar > 0.0
            and eligible_trend_count > 0
            and trend_trade_attr["trade_count"] > 0
            and nontrend_trade_attr["trade_count"] == 0
            and aggregate_delta["expected_value_score_sum"] > 0
            and aggregate_delta["total_pnl_sum"] > 0
            and len(ev_improvements) >= 1
            and not ev_regressions
            and aggregate_delta["max_drawdown_pct_max"] <= MAX_DRAWDOWN_DAMAGE_VS_BEFORE
            and variant["aggregate"]["min_survival_rate"] >= MIN_SURVIVAL_RATE
            and variant["aggregate"]["trade_count_sum"] >= MIN_TRADE_COUNT
        ),
    }


def _gate2_runtime_state(variants: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = 0
    eligible_trend = 0
    eligible_nontrend = 0
    changed_trend = 0
    zeroed_nontrend = 0
    samples = []
    for variant in variants:
        for window_name, payload in variant.get("by_window", {}).items():
            counts = payload.get("irdm_candidate_counts") or {}
            eligible_window = int(counts.get("eligible_signal", 0) or 0)
            eligible_trend_window = int(counts.get("eligible_trend_long", 0) or 0)
            eligible += eligible_window
            eligible_trend += eligible_trend_window
            eligible_nontrend += eligible_window - eligible_trend_window
            changed_trend += int(
                counts.get("space_irdm_forward_candidate_risk_changed_signal", 0)
                or 0
            )
            zeroed_nontrend += int(
                counts.get(
                    "space_irdm_nontrend_forward_candidate_zero_risk_changed_signal",
                    0,
                )
                or 0
            )
            summary = payload.get("irdm_candidate_adjustment") or {}
            for row in summary.get("sample") or []:
                samples.append(
                    {
                        "variant": variant.get("label"),
                        "window": window_name,
                        "ticker": row.get("ticker"),
                        "strategy": row.get("strategy"),
                        "scalar": row.get("scalar"),
                        "candidate_scalar": row.get("candidate_scalar"),
                        "nontrend_zero_risk": row.get("nontrend_zero_risk"),
                        "profile": row.get("irdm_forward_candidate_profile"),
                    }
                )
    return {
        "passed": eligible_trend > 0 and zeroed_nontrend > 0,
        "required_runtime_fields": [
            "data/space_catalyst_event_state_shadow_ledger.jsonl horizons.10d.cash_relative_pnl",
            "data/space_catalyst_event_state_shadow_ledger.jsonl horizons.10d.same_theme_replacement_value",
            "data/space_catalyst_event_state_shadow_ledger.jsonl horizons.10d.ufo_relative_value",
            "data/space_catalyst_event_state_shadow_ledger.jsonl source_type",
            "sizing.shares_to_buy",
            "signal.strategy",
        ],
        "eligible_signal_count_across_tested_variants": eligible,
        "eligible_trend_signal_count_across_tested_variants": eligible_trend,
        "eligible_nontrend_signal_count_across_tested_variants": eligible_nontrend,
        "changed_trend_signal_count_across_tested_variants": changed_trend,
        "zeroed_nontrend_signal_count_across_tested_variants": zeroed_nontrend,
        "sample_rows": samples[:10],
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["best_variant"]
    gate = payload["best_variant_gate"]
    lines = [
        f"# {EXPERIMENT_ID} Space IRDM forward-candidate risk",
        "",
        "## Hypothesis",
        payload["hypothesis"],
        "",
        "## Single Changed Variable",
        (
            "`space_irdm_trend_forward_candidate_scalar`, where the accepted "
            "exp-009 default-off Space stack is unchanged and only IRDM "
            "`trend_long` signals receive bounded risk after passing the closed "
            "official Golden Dome forward replacement profile. Non-trend IRDM "
            "signals are forced to zero risk; broad satcom, VSAT/GSAT/SATS, LLM/news, "
            "entries, exits, ranking, targets, and live Space slots stay fixed."
        ),
        "",
        "## Gate 4 Summary",
        f"- Decision: `{payload['decision']}`",
        (
            "- Best scalar: "
            f"`{best['parameters']['space_irdm_trend_forward_candidate_scalar']}`"
        ),
        (
            "- Aggregate delta vs exp-009: "
            f"EV `{gate['aggregate_delta_vs_before']['expected_value_score_sum']:.6f}`, "
            f"PnL `{gate['aggregate_delta_vs_before']['total_pnl_sum']:.2f}`"
        ),
        (
            "- IRDM trend signals changed / non-trend zeroed: "
            f"`{gate['changed_irdm_trend_candidate_signal_count']}` / "
            f"`{gate['zeroed_irdm_nontrend_candidate_signal_count']}` from "
            f"`{gate['eligible_irdm_candidate_signal_count']}` eligible"
        ),
        (
            "- IRDM trend trades / non-trend trades: "
            f"`{gate['irdm_trend_trade_attribution']['trade_count']}` / "
            f"`{gate['irdm_nontrend_trade_attribution']['trade_count']}`, "
            f"PnL `{gate['irdm_trade_attribution']['total_pnl']}`"
        ),
        "",
        "## Three-Window Deltas vs Exp-009",
        "| window | EV delta | PnL delta | max DD delta | trades | survival | adjusted | IRDM trend trades | IRDM nontrend trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, delta in gate["by_window_delta_vs_before"].items():
        metrics = best["by_window"][name]["metrics"]
        adjusted = best["by_window"][name]["irdm_candidate_adjustment"][
            "adjusted_signal_count"
        ]
        irdm_trend_trades = best["by_window"][name]["irdm_trend_trade_attribution"][
            "trade_count"
        ]
        irdm_nontrend_trades = best["by_window"][name][
            "irdm_nontrend_trade_attribution"
        ]["trade_count"]
        lines.append(
            "| {name} | {ev:.6f} | {pnl:.2f} | {dd:.6f} | {trades} | {survival:.6f} | {adjusted} | {irdm_trend_trades} | {irdm_nontrend_trades} |".format(
                name=name,
                ev=delta["expected_value_score"],
                pnl=delta["total_pnl"],
                dd=delta["max_drawdown_pct"],
                trades=metrics["trade_count"],
                survival=metrics["survival_rate"],
                adjusted=adjusted,
                irdm_trend_trades=irdm_trend_trades,
                irdm_nontrend_trades=irdm_nontrend_trades,
            )
        )
    lines.extend(
        [
            "",
            "## Gate Checks",
            f"- Gate 2 passed: `{payload['gate2_field_checks']['passed']}`",
            f"- Gate 3 survival passed: `{payload['gate3']['passed']}`",
            "",
            "## Production Impact",
            "```text",
            "production_impact:",
            f"  shared_policy_changed: {payload['production_impact']['shared_policy_changed']}",
            f"  backtester_adapter_changed: {payload['production_impact']['backtester_adapter_changed']}",
            f"  run_adapter_changed: {payload['production_impact']['run_adapter_changed']}",
            f"  replay_only: {payload['production_impact']['replay_only']}",
            f"  parity_test_added: {payload['production_impact']['parity_test_added']}",
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def _ticket(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "lane": payload["lane"],
        "status": payload["status"],
        "hypothesis": payload["hypothesis"],
        "changed_variable": payload["changed_variable"],
        "decision": payload["decision"],
        "best_parameters": payload["best_variant"]["parameters"],
        "aggregate_delta_vs_before": payload["best_variant_gate"][
            "aggregate_delta_vs_before"
        ],
        "next_evidence_needed": payload["next_evidence_needed"],
        "production_impact": payload["production_impact"],
    }


def run() -> dict[str, Any]:
    run_started_at = datetime.now(timezone.utc).isoformat()

    core = source_diversity_exp._run_core_baseline()
    attention_gate = source_diversity_exp._field_check_attention_overlay_profile()
    single_event_gate = source_diversity_exp._field_check_single_event_defense_profile()
    government_contract_gate = (
        source_diversity_exp._field_check_government_contract_profile()
    )
    source_gate = source_diversity_exp._event_seed_profiles()
    multi_event_gate = source_diversity_exp._field_check_multi_event_depth()
    liquidity_gate = source_diversity_exp._field_check_watch_liquidity_tier()
    company_release_gate = source_diversity_exp._field_check_company_release_source()
    financing_gate = source_diversity_exp._accepted_financing_profile_gate()
    source_diversity_gate = source_diversity_exp._field_check_source_diversity_profile()
    ten_day_forward_gate = same_theme_exp._forward_replacement_profile_gate()
    irdm_gate = _irdm_forward_candidate_profile_gate()
    snapshot_gate = _snapshot_irdm_gate()

    before = _run_variant(
        "accepted_exp009_no_irdm",
        irdm_candidate_scalar=0.0,
        include_irdm=False,
        ten_day_forward_gate=ten_day_forward_gate,
        irdm_gate=irdm_gate,
        source_diversity_gate=source_diversity_gate,
        attention_gate=attention_gate,
        single_event_gate=single_event_gate,
        government_contract_gate=government_contract_gate,
        source_gate=source_gate,
        multi_event_gate=multi_event_gate,
        liquidity_gate=liquidity_gate,
        company_release_gate=company_release_gate,
        financing_gate=financing_gate,
    )

    variants = [
        _run_variant(
            f"{STEM}_{str(scalar).replace('.', '_')}",
            irdm_candidate_scalar=scalar,
            include_irdm=True,
            ten_day_forward_gate=ten_day_forward_gate,
            irdm_gate=irdm_gate,
            source_diversity_gate=source_diversity_gate,
            attention_gate=attention_gate,
            single_event_gate=single_event_gate,
            government_contract_gate=government_contract_gate,
            source_gate=source_gate,
            multi_event_gate=multi_event_gate,
            liquidity_gate=liquidity_gate,
            company_release_gate=company_release_gate,
            financing_gate=financing_gate,
        )
        for scalar in IRDM_FORWARD_CANDIDATE_RISK_SCALARS
    ]
    for variant in variants:
        variant["gate"] = _gate_variant(variant, before)

    runtime_state_gate = _gate2_runtime_state(variants)
    gate2 = {
        "open_positions": source_diversity_exp._gate2_open_positions(),
        "attention_overlay_profile": attention_gate,
        "single_event_defense_profile": single_event_gate,
        "government_contract_profile": government_contract_gate,
        "official_customer_source_profile": source_gate,
        "multi_event_depth": multi_event_gate,
        "liquidity_tier": liquidity_gate,
        "company_release_source": company_release_gate,
        "financing_dilution_profile": financing_gate,
        "source_diversity_profile": source_diversity_gate,
        "ten_day_forward_replacement_profile": ten_day_forward_gate,
        "irdm_forward_candidate_profile": irdm_gate,
        "irdm_snapshot_presence": snapshot_gate,
        "irdm_candidate_runtime_state": runtime_state_gate,
    }
    gate2["passed"] = all(
        [
            gate2["open_positions"]["passed"],
            attention_gate["passed"],
            single_event_gate["passed"],
            government_contract_gate["passed"],
            source_gate["passed"],
            multi_event_gate["passed"],
            liquidity_gate["passed"],
            company_release_gate["passed"],
            financing_gate["passed"],
            source_diversity_gate["passed"],
            ten_day_forward_gate["passed"],
            irdm_gate["passed"],
            snapshot_gate["passed"],
            runtime_state_gate["passed"],
        ]
    )

    best_variant = max(
        variants,
        key=lambda item: (
            item["gate"]["accepted"],
            item["gate"]["aggregate_delta_vs_before"]["expected_value_score_sum"],
            item["gate"]["aggregate_delta_vs_before"]["total_pnl_sum"],
        ),
    )
    decision = "accepted" if best_variant["gate"]["accepted"] else "rejected"
    rejection_reason = ""
    if decision == "rejected":
        rejection_reason = (
            "No tested IRDM trend-only forward-candidate scalar improved "
            "aggregate EV/PnL across the three windows without a window-level "
            "EV regression, drawdown or survival violation, or zero-trend-trade "
            "result."
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "run_started_at": run_started_at,
        "run_finished_at": datetime.now(timezone.utc).isoformat(),
        "lane": "alpha_search",
        "hypothesis": (
            "Space candidate expansion should be narrow and catalyst-qualified. "
            "IRDM, unlike broad mature satcom breadth or VSAT, now has a closed official "
            "Golden Dome/defense-budget forward profile with positive 10d cash, "
            "SPY-relative, and UFO-relative value despite negative same-theme "
            "replacement value. "
            "Exp-20260514-015 showed broad VSAT admission was damaged by "
            "breakout losses, so trend-only IRDM risk may keep the replacement "
            "alpha while removing the non-trend tail."
        ),
        "change_type": "candidate_pool_risk_allocation_shadow_sweep",
        "changed_variable": "space_irdm_forward_candidate_risk_scalar",
        "single_causal_variable": (
            "admit only IRDM trend_long signals with a bounded risk scalar after "
            "the closed official defense-budget forward profile passes cash, "
            "SPY, and UFO-relative gates while same-theme replacement is <= 0; "
            "force non-trend IRDM "
            "signals to zero risk"
        ),
        "backtest_protocol": {
            "source": "docs/backtesting.md core multi-window protocol plus Space frozen snapshots",
            "windows": source_diversity_exp.WINDOWS,
            "space_snapshots": {
                label: window["space_snapshot"]
                for label, window in source_diversity_exp.WINDOWS.items()
            },
        },
        "gate_questions": {
            "q1_alpha_hypothesis": (
                "candidate pool / risk allocation: add only IRDM trend_long risk "
                "after the official Golden Dome defense-budget forward ledger "
                "shows positive 10d cash, SPY, and UFO-relative evidence while "
                "same-theme replacement is negative."
            ),
            "q2_prior_experiments": [
                "exp-20260511-026 rejected broad mature satcom breadth: only 1/3 windows improved and 2 regressed.",
                "exp-20260512-023 rejected GSAT candidate admission: aggregate EV -1.1993 and PnL -$4,496.98.",
                "exp-20260514-011 rejected 5d confirmation: mid_weak regressed and only old_thin materially improved.",
                "exp-20260514-013 rejected negative forward-profile risk because no tested scalar moved PnL.",
                "exp-20260514-015 rejected broad VSAT admission: aggregate improved but late_strong EV regressed and breakout_long VSAT trades lost money.",
            ],
            "q3_single_causal_variable": (
                "Only the IRDM trend_long forward-candidate risk scalar changes "
                "and IRDM non-trend sizing is forced to zero; accepted exp-009 "
                "stack, entries, exits, ranking, targets, LLM/news, and live "
                "slots stay fixed."
            ),
            "q4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; require positive "
                "aggregate EV/PnL, at least one EV-improved window because this "
                "is a sparse candidate-pool expansion, no EV-regressed window, "
                "max drawdown damage <= 0.5pp, survival >= 5%, >=50 aggregate "
                "trades, actual IRDM trend trades, and zero IRDM non-trend "
                "trades."
            ),
            "q5_reproducibility": (
                f"Run .\\.venv\\Scripts\\python.exe quant\\experiments\\{Path(__file__).name}"
            ),
        },
        "gate1": {
            "core_baseline": core["aggregate"],
            "accepted_before_metrics": before["aggregate"],
            "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
            "known_bias": (
                "Space candidate snapshots are frozen historical replay copies. "
                "The IRDM admission evidence comes from closed 2026 event-state "
                "ledger rows, so any positive result must remain default-off and "
                "be promoted only through shared observe-only Space metadata."
            ),
        },
        "gate2_field_checks": gate2,
        "gate3": {
            "new_filter_added": False,
            "new_risk_scalar_added": True,
            "min_survival_rate_after": best_variant["aggregate"]["min_survival_rate"],
            "passed": best_variant["aggregate"]["min_survival_rate"] >= MIN_SURVIVAL_RATE,
        },
        "parameters": {
            "tested_irdm_trend_forward_candidate_scalars": list(
                IRDM_FORWARD_CANDIDATE_RISK_SCALARS
            ),
            "irdm_nontrend_forward_candidate_scalar": 0.0,
            "target_irdm_strategy": "trend_long",
            "irdm_forward_candidate_tickers": irdm_gate["target_tickers"],
            "ten_day_forward_replacement_tickers": ten_day_forward_gate[
                "base_target_tickers"
            ],
            "same_theme_strength_target_tickers": sorted(
                same_theme_exp._target_tickers_for_floor(
                    ten_day_forward_gate,
                    ACCEPTED_FORWARD_REPLACEMENT_SAME_THEME_STRENGTH_FLOOR,
                )
            ),
            "locked_variables": [
                "accepted official Space candidate pool",
                "accepted exp-113 10d forward replacement-positive scalar",
                "accepted exp-20260514-002 10d same-theme strength scalar",
                "accepted exp-20260514-009 trend strength scalar",
                "accepted exp-110 source-diversity stack",
                "all prior accepted Space risk helpers",
                "Space trend targets",
                "entry filters",
                "candidate ranking",
                "MAX_POSITIONS",
                "add-ons",
                "LLM/news replay",
                "live Space slots",
            ],
            "anti_js": "No JavaScript was used.",
        },
        "core_baseline": core,
        "before": before,
        "variants": variants,
        "best_variant": best_variant,
        "best_variant_gate": best_variant["gate"],
        "decision": decision,
        "status": (
            "accepted_default_off_space_irdm_forward_candidate_risk"
            if decision == "accepted"
            else "rejected_space_irdm_forward_candidate_risk"
        ),
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "Promote only through shared default-off Space metadata/helpers; live "
            "Space slots stay zero until a point-in-time official event gate and "
            "more closed forward rows support production routing."
            if decision == "accepted"
            else (
                "Do not promote IRDM trend-only candidate admission from this "
                "frozen replay. Wait for more closed official forward evidence "
                "or test a different non-noisy candidate-quality axis."
            )
        ),
        "production_impact": {
            "alters_candidate_ranking": False,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_sizing": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "daily_report_metadata_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "live_slots": 0,
            "live_slots_changed": False,
            "promotion_requirement": (
                "A retained positive result must be implemented later through a "
                "shared default-off Space helper used by both replay/backtester "
                "and run adapters before any production behavior changes."
            ),
        },
        "why_not_other_changes": (
            "LLM soft-ranking remains label-thin. Broad satcom and GSAT were "
            "rejected. Rather than adding noisy tickers, this tests the only "
            "mature satcom name with current closed official forward replacement "
            "evidence strong enough to pass a pre-field gate."
        ),
        "known_risks": [
            "The Space sleeve remains default-off and historical Space snapshots are frozen research copies.",
            "IRDM evidence is a single closed official Golden Dome event row and can be event-specific.",
            "Accepted results would still be observation metadata, not live Space slot enablement.",
        ],
    }
    return payload


def persist(payload: dict[str, Any]) -> None:
    exp_dir = PROJECT_ROOT / "data" / "experiments" / EXPERIMENT_ID
    logs_dir = PROJECT_ROOT / "experiments" / "logs"
    tickets_dir = PROJECT_ROOT / "experiments" / "tickets"
    artifacts_dir = PROJECT_ROOT / "experiments" / "artifacts"
    for directory in (exp_dir, logs_dir, tickets_dir, artifacts_dir):
        directory.mkdir(parents=True, exist_ok=True)

    _write_json(exp_dir / f"{STEM}.json", payload)
    _write_json(logs_dir / f"{EXPERIMENT_ID}.json", payload)
    _write_json(tickets_dir / f"{EXPERIMENT_ID}.json", _ticket(payload))
    (artifacts_dir / f"{EXPERIMENT_ID}_{STEM}.md").write_text(
        _artifact_markdown(payload),
        encoding="utf-8",
    )
    _append_jsonl_for_this_experiment(
        PROJECT_ROOT / "docs" / "experiment_log.jsonl",
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": payload["hypothesis"],
            "change_type": payload["change_type"],
            "changed_variable": payload["changed_variable"],
            "single_causal_variable": payload["single_causal_variable"],
            "parameters": payload["best_variant"]["parameters"],
            "date_range": [
                f"{label}:{window['start']}..{window['end']}"
                for label, window in source_diversity_exp.WINDOWS.items()
            ],
            "backtest_protocol": payload["backtest_protocol"],
            "before_metrics": payload["before"]["aggregate"],
            "after_metrics": payload["best_variant"]["aggregate"],
            "expected_value_score_delta": payload["best_variant_gate"][
                "aggregate_delta_vs_before"
            ]["expected_value_score_sum"],
            "decision": payload["status"],
            "rejection_reason": payload["rejection_reason"],
            "next_evidence_needed": payload["next_evidence_needed"],
            "production_impact": payload["production_impact"],
        },
    )


if __name__ == "__main__":
    result = run()
    persist(result)
    summary = {
        "experiment_id": result["experiment_id"],
        "decision": result["status"],
        "best_scalar": result["best_variant"]["parameters"][
            "space_irdm_trend_forward_candidate_scalar"
        ],
        "target_tickers": result["best_variant"]["parameters"]["target_tickers"],
        "aggregate_before": result["before"]["aggregate"],
        "aggregate_after": result["best_variant"]["aggregate"],
        "aggregate_delta_vs_before": result["best_variant_gate"][
            "aggregate_delta_vs_before"
        ],
        "by_window_delta_vs_before": result["best_variant_gate"][
            "by_window_delta_vs_before"
        ],
        "changed_irdm_trend_candidate_signal_count": result["best_variant_gate"][
            "changed_irdm_trend_candidate_signal_count"
        ],
        "zeroed_irdm_nontrend_candidate_signal_count": result["best_variant_gate"][
            "zeroed_irdm_nontrend_candidate_signal_count"
        ],
        "irdm_trade_attribution": result["best_variant_gate"][
            "irdm_trade_attribution"
        ],
        "irdm_trend_trade_attribution": result["best_variant_gate"][
            "irdm_trend_trade_attribution"
        ],
        "irdm_nontrend_trade_attribution": result["best_variant_gate"][
            "irdm_nontrend_trade_attribution"
        ],
        "production_impact": result["production_impact"],
    }
    print(json.dumps(_safe(summary), indent=2, sort_keys=True))




