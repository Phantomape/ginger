"""exp-20260606-023: market-state lagged consensus allocation.

Replay-only alpha search. It tests one frozen capital-allocation variable:
increase the accepted lagged free-data consensus paper notional by 1.25x only
when the market state known at the prior close is mixed|balanced|normal.

No production code, shared adapter, watchlist, ranking, core sizing, exits,
orders, LLM/news path, or live/default order behavior is changed. No
JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for import_path in (QUANT_DIR, EXPERIMENTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260604_008_lagged_independent_source_consensus as lagged  # noqa: E402
from regime_engine import classify_market_regime  # noqa: E402
from sentiment_surface import classify_sentiment_surface  # noqa: E402


EXPERIMENT_ID = "exp-20260606-023"
STEM = "market_state_lagged_consensus_allocation"
TRIAL_FAMILY = "market_state_sleeve_router_allocation"
TRIAL_VARIANT_ID = "accepted_lagged_consensus_mixed_balanced_normal_1_25x_v1"
CHANGED_VARIABLE = "accepted_free_data_consensus_mixed_balanced_normal_notional_scalar"

TARGET_STATE = "mixed|balanced|normal"
TARGET_SCALAR = 1.25
BASELINE_COMPARATOR_EXPERIMENT_ID = "exp-20260604-009"
SOURCE_REPLAY_EXPERIMENT_ID = "exp-20260604-008"

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260606_023_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

PREDICTION = {
    "success_probability": 0.31,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "window_regression",
        "drawdown_drift",
        "observed_attribution_overfit",
        "accepted_sleeve_overlap_duplicate_rows",
        "concentration_failed",
    ],
    "confidence_reason": (
        "exp-20260606-022 identified one frozen router-grade cell with 39 rows, "
        "all three windows represented, avg PnL 7.78%, and 5.69pp edge versus "
        "the same sleeve in other states; meta research prioritizes "
        "production-visible default-off paper adapter work."
    ),
    "recorded_at": "2026-06-06T18:04:33Z",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_no_live_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "default_off_paper_only": True,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "parity_note": (
        "This experiment changes no production code. A positive result would "
        "require a shared market-state sleeve-allocation adapter that computes "
        "the same prior-close SPY/QQQ state label in both historical replay and "
        "daily production before any paper ledger, report queue, priority, "
        "notional, watchlist, or order surface could change."
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(value).replace("\\", "/")


def _load_json(path: Path | str) -> Any:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return json.loads(value.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _safe(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {str(key): _safe(value) for key, value in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [_safe(value) for value in payload]
    if isinstance(payload, set):
        return sorted(_safe(value) for value in payload)
    if isinstance(payload, Counter):
        return {str(key): _safe(value) for key, value in payload.items()}
    if isinstance(payload, Path):
        return _repo_rel(payload)
    if isinstance(payload, float):
        if math.isnan(payload) or math.isinf(payload):
            return None
        return round(payload, 10)
    return payload


def _round(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _sha256(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _date(row: dict[str, Any]) -> str:
    return str(row.get("Date") or row.get("date") or "")[:10]


def _value(row: dict[str, Any], key: str) -> float | None:
    try:
        value = row.get(key)
        if value is None:
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _series(snapshot: dict[str, list[dict[str, Any]]], ticker: str) -> list[dict[str, Any]]:
    return sorted(snapshot.get(ticker) or [], key=_date)


def _row_index(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {_date(row): idx for idx, row in enumerate(rows) if _date(row)}


def _trading_dates(snapshot: dict[str, list[dict[str, Any]]]) -> list[str]:
    return [_date(row) for row in _series(snapshot, "SPY") if _date(row)]


def _ret(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < lookback or idx >= len(rows):
        return None
    start = _value(rows[idx - lookback], "Close")
    end = _value(rows[idx], "Close")
    if start is None or end is None or start <= 0:
        return None
    return (end / start) - 1.0


def _sma(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < lookback - 1 or idx >= len(rows):
        return None
    values = [_value(row, "Close") for row in rows[idx - lookback + 1 : idx + 1]]
    if any(value is None for value in values):
        return None
    clean = [float(value) for value in values if value is not None]
    return sum(clean) / len(clean) if clean else None


def _pct_from_sma(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    close = _value(rows[idx], "Close") if 0 <= idx < len(rows) else None
    avg = _sma(rows, idx, lookback)
    if close is None or avg is None or avg <= 0:
        return None
    return (close / avg) - 1.0


def _bucket_market_context(context: dict[str, Any]) -> dict[str, str]:
    spy20 = context.get("spy_20d_return")
    qqq20 = context.get("qqq_20d_return")
    spy10 = context.get("spy_10d_return")
    qqq10 = context.get("qqq_10d_return")
    spy_pct = context.get("spy_pct_from_ma")
    qqq_pct = context.get("qqq_pct_from_ma")
    qqq_rel = context.get("qqq_minus_spy_ret20")

    broad_up = (
        spy20 is not None
        and qqq20 is not None
        and spy20 > 0.03
        and qqq20 > 0.04
        and (spy_pct is None or spy_pct > 0.0)
        and (qqq_pct is None or qqq_pct > 0.0)
    )
    broad_down = (
        (spy20 is not None and spy20 < -0.03)
        or (qqq20 is not None and qqq20 < -0.04)
        or (spy_pct is not None and spy_pct < -0.02)
        or (qqq_pct is not None and qqq_pct < -0.02)
    )
    if broad_up:
        trend_pressure = "broad_up"
    elif broad_down:
        trend_pressure = "broad_down"
    else:
        trend_pressure = "mixed"

    if qqq_rel is None:
        growth_leadership = "unknown"
    elif qqq_rel >= 0.03:
        growth_leadership = "qqq_leads"
    elif qqq_rel <= -0.015:
        growth_leadership = "spy_defensive_leads"
    else:
        growth_leadership = "balanced"

    max_10 = max([value for value in [spy10, qqq10] if value is not None], default=None)
    max_20 = max([value for value in [spy20, qqq20] if value is not None], default=None)
    min_10 = min([value for value in [spy10, qqq10] if value is not None], default=None)
    if (max_10 is not None and max_10 >= 0.05) or (max_20 is not None and max_20 >= 0.08):
        extension = "extended"
    elif min_10 is not None and min_10 <= -0.03:
        extension = "pullback"
    else:
        extension = "normal"

    return {
        "trend_pressure": trend_pressure,
        "growth_leadership": growth_leadership,
        "extension": extension,
        "combined_state": f"{trend_pressure}|{growth_leadership}|{extension}",
    }


def _state_for_entry_date(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    trading_dates: list[str],
    entry_date: str,
) -> dict[str, Any] | None:
    date_pos = {value: idx for idx, value in enumerate(trading_dates)}
    entry_pos = date_pos.get(entry_date)
    if entry_pos is None or entry_pos < 1:
        return None
    state_date = trading_dates[entry_pos - 1]
    spy_rows = _series(snapshot, "SPY")
    qqq_rows = _series(snapshot, "QQQ")
    spy_idx = _row_index(spy_rows).get(state_date)
    qqq_idx = _row_index(qqq_rows).get(state_date)
    if spy_idx is None or qqq_idx is None:
        return None

    context = {
        "spy_pct_from_ma": _pct_from_sma(spy_rows, spy_idx, 200),
        "qqq_pct_from_ma": _pct_from_sma(qqq_rows, qqq_idx, 200),
        "spy_10d_return": _ret(spy_rows, spy_idx, 10),
        "qqq_10d_return": _ret(qqq_rows, qqq_idx, 10),
        "spy_20d_return": _ret(spy_rows, spy_idx, 20),
        "qqq_20d_return": _ret(qqq_rows, qqq_idx, 20),
        "theme_signal_count": 0,
        "breakout_signal_count": 0,
        "ai_signal_count": 0,
        "crypto_signal_count": 0,
        "space_signal_count": 0,
    }
    if context["qqq_20d_return"] is not None and context["spy_20d_return"] is not None:
        context["qqq_minus_spy_ret20"] = (
            float(context["qqq_20d_return"]) - float(context["spy_20d_return"])
        )
    else:
        context["qqq_minus_spy_ret20"] = None

    regime = classify_market_regime(context)
    sentiment = classify_sentiment_surface(context)
    buckets = _bucket_market_context(context)
    return {
        "state_date": state_date,
        "state_known_at": "prior_trading_day_close_before_entry_open",
        "regime": regime.get("regime"),
        "regime_confidence": regime.get("confidence"),
        "sentiment": sentiment.get("sentiment"),
        "sentiment_confidence": sentiment.get("confidence"),
        "sentiment_why": sentiment.get("why") or [],
        **buckets,
        "features": {
            key: _round(value)
            for key, value in context.items()
            if key
            in {
                "spy_pct_from_ma",
                "qqq_pct_from_ma",
                "spy_10d_return",
                "qqq_10d_return",
                "spy_20d_return",
                "qqq_20d_return",
                "qqq_minus_spy_ret20",
            }
        },
    }


def _copy_trade_with_state(
    trade: dict[str, Any],
    state: dict[str, Any] | None,
    *,
    window: str,
) -> dict[str, Any]:
    out = dict(trade)
    out["window"] = window
    out["market_state_available"] = state is not None
    if state is not None:
        out.update({f"market_{key}": value for key, value in state.items()})
        out["combined_state"] = state["combined_state"]
        out["target_state_cell"] = state["combined_state"] == TARGET_STATE
    else:
        out["combined_state"] = None
        out["target_state_cell"] = False
    return out


def _scale_trades(
    state_labeled_trades: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    scaled: list[dict[str, Any]] = []
    incremental: list[dict[str, Any]] = []
    for row in state_labeled_trades:
        pnl = float(row.get("pnl") or 0.0)
        notional = float(row.get("paper_notional_usd") or 0.0)
        scalar = TARGET_SCALAR if row.get("target_state_cell") else 1.0
        scaled_row = dict(row)
        scaled_row["allocation_scalar"] = scalar
        scaled_row["pnl_before_allocation"] = round(pnl, 2)
        scaled_row["paper_notional_before_allocation"] = round(notional, 2)
        scaled_row["pnl"] = round(pnl * scalar, 2)
        if notional > 0:
            scaled_row["paper_notional_usd"] = round(notional * scalar, 2)
        scaled.append(scaled_row)

        if row.get("target_state_cell"):
            inc = dict(row)
            inc["pnl"] = round(pnl * (TARGET_SCALAR - 1.0), 2)
            inc["paper_notional_usd"] = round(notional * (TARGET_SCALAR - 1.0), 2)
            inc["allocation_scalar_delta"] = round(TARGET_SCALAR - 1.0, 6)
            incremental.append(inc)
    return scaled, incremental


def _state_labeled_trades_for_window(
    *,
    label: str,
    cfg: dict[str, str],
    trades: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    snapshot = lagged.same_day.prior.base.shadow._load_snapshot(cfg["snapshot"])
    trading_dates = _trading_dates(snapshot)
    labeled: list[dict[str, Any]] = []
    missing_state = 0
    for trade in trades:
        entry_date = str(trade.get("entry_date") or "")[:10]
        state = _state_for_entry_date(
            snapshot=snapshot,
            trading_dates=trading_dates,
            entry_date=entry_date,
        )
        if state is None:
            missing_state += 1
        labeled.append(_copy_trade_with_state(trade, state, window=label))
    return labeled, {
        "window": label,
        "input_trade_count": len(trades),
        "state_labeled_trade_count": len(trades) - missing_state,
        "missing_state_trade_count": missing_state,
        "target_state_trade_count": sum(1 for row in labeled if row["target_state_cell"]),
    }


def _aggregate_window_rows(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return lagged.same_day.prior.base._aggregate(rows)


def _target_trade_summary(
    target_trades_by_window: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    return lagged.same_day.prior.base._target_trade_summary(target_trades_by_window)


def _duplicate_diagnostics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups: Counter[tuple[str, str, str, str]] = Counter()
    for row in rows:
        groups[
            (
                str(row.get("window") or ""),
                str(row.get("ticker") or ""),
                str(row.get("entry_date") or "")[:10],
                str(row.get("exit_date") or "")[:10],
            )
        ] += 1
    duplicate_rows = sum(count for count in groups.values() if count > 1)
    return {
        "duplicate_ticker_entry_groups": sum(1 for count in groups.values() if count > 1),
        "duplicate_rows": duplicate_rows,
        "duplicate_row_share": round(duplicate_rows / len(rows), 6) if rows else 0.0,
        "max_allowed_duplicate_row_share_for_router": 0.25,
    }


def _preflight_payload() -> dict[str, Any]:
    return {
        "alpha_hypothesis": (
            "Capital allocation: accepted lagged free-data consensus candidates "
            "may deserve a modest higher default-off paper notional when "
            "prior-close SPY/QQQ state is mixed|balanced|normal, because "
            "observed accepted-sleeve attribution found this exact cell had "
            "higher normalized PnL than the same sleeve in other states."
        ),
        "category": "capital allocation",
        "playbook_alignment": (
            "Meta research currently prefers production-visible default-off "
            "paper adapter work, and exp-20260606-022 supplied new router-grade "
            "state/sleeve evidence. This is not an LLM soft-ranking retry."
        ),
        "history_check": {
            "exp-20260606-021": (
                "Observed-only core state attribution was too thin for a router."
            ),
            "exp-20260606-022": (
                "Accepted-sleeve state attribution found the exact target cell: "
                "ACCEPTED_FREE_DATA_CROSS_SOURCE_CONSENSUS_PAPER in "
                "mixed|balanced|normal, 39 rows, all three windows represented."
            ),
            "exp-20260604-009": (
                "Accepted lagged consensus shared adapter evidence. This run "
                "uses it as the before comparator and changes only allocation "
                "inside one prior-close state cell."
            ),
        },
        "single_causal_variable": CHANGED_VARIABLE,
        "acceptance_criteria": {
            "canonical_windows": list(lagged.same_day.prior.base.WINDOWS.keys()),
            "before_comparator": BASELINE_COMPARATOR_EXPERIMENT_ID,
            "target_state": TARGET_STATE,
            "target_scalar": TARGET_SCALAR,
            "aggregate_ev_delta_vs_accepted_lagged_adapter": "> 0",
            "aggregate_pnl_delta_vs_accepted_lagged_adapter": "> 0",
            "per_window_ev_regressions": "0",
            "per_window_pnl_regressions": "0",
            "minimum_target_trades": MIN_TARGET_TRADES,
            "minimum_target_windows": MIN_TARGET_WINDOWS,
            "max_drawdown_drift": MAX_DRAWDOWN_WORSE,
            "survival_rate_floor": 0.05,
            "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi_max": MAX_POSITIVE_HHI,
            "production_retention": (
                "No production retention in this run; any positive result "
                "requires a shared adapter plus parity tests before promotion."
            ),
        },
        "reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260606_023_market_state_lagged_consensus_allocation.py"
        ),
    }


def _gate4(
    *,
    aggregate: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
    target_summary: dict[str, Any],
    state_diagnostics: dict[str, Any],
    duplicate_diagnostics: dict[str, Any],
) -> dict[str, Any]:
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    target_windows = target_summary["windows_with_target_trades"]
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    failed: list[str] = []
    if float(aggregate["expected_value_score_delta_sum"] or 0.0) <= 0.0:
        failed.append("aggregate_ev_not_positive")
    if float(aggregate["total_pnl_delta_sum"] or 0.0) <= 0.0:
        failed.append("aggregate_pnl_not_positive")
    if int(aggregate["windows_ev_regressed"] or 0) > 0:
        failed.append("window_ev_regression")
    if int(aggregate["windows_pnl_regressed"] or 0) > 0:
        failed.append("window_pnl_regression")
    if int(target_summary["total_trade_count"] or 0) < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_windows) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if float(aggregate["max_drawdown_delta_max"] or 0.0) > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if min_survival < 0.05:
        failed.append("accepted_comparator_survival_rate_below_5pct")
    if not concentration_passed:
        failed.append("incremental_target_concentration_failed")
    if int(state_diagnostics["missing_state_trade_count_total"] or 0) > 0:
        failed.append("missing_prior_close_market_state")
    if float(duplicate_diagnostics["duplicate_row_share"] or 0.0) > 0.25:
        failed.append("accepted_sleeve_overlap_duplicate_rows")

    passed = not failed
    if passed:
        decision = "positive_replay_lead_not_promoted_market_state_lagged_consensus_allocation"
        rationale = (
            "The 1.25x target-state top-up improved accepted lagged consensus "
            "EV/PnL without window regression, but it is replay-only and "
            "requires shared adapter parity before any production-visible "
            "allocation can be retained."
        )
    else:
        decision = "rejected_market_state_lagged_consensus_allocation"
        rationale = (
            "The frozen target-state allocation scalar failed Gate 4: "
            f"{', '.join(failed)}. Do not retune this same state/scalar on the "
            "same windows without materially new replacement-value evidence."
        )
    return {
        "passed": passed,
        "decision": decision,
        "failed_reasons": failed,
        "rationale": rationale,
        "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
        "windows_ev_improved": aggregate["windows_ev_improved"],
        "windows_ev_regressed": aggregate["windows_ev_regressed"],
        "windows_pnl_improved": aggregate["windows_pnl_improved"],
        "windows_pnl_regressed": aggregate["windows_pnl_regressed"],
        "target_trade_count": target_summary["total_trade_count"],
        "target_trade_count_min": MIN_TARGET_TRADES,
        "target_windows": target_windows,
        "target_window_count_min": MIN_TARGET_WINDOWS,
        "max_drawdown_worse": aggregate["max_drawdown_delta_max"],
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "minimum_accepted_comparator_survival_rate": round(min_survival, 6),
        "survival_guard_passed": min_survival >= 0.05,
        "target_concentration": {
            "passed": concentration_passed,
            "max_single_positive_pnl_share": target_summary[
                "max_single_positive_pnl_share"
            ],
            "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi": target_summary["positive_pnl_hhi"],
            "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
        },
        "requires_parity_before_promotion": True,
    }


def _build_payload() -> dict[str, Any]:
    timestamp = _utc_now()
    lagged._configure_same_day_modules()
    gate2 = lagged.same_day.prior.base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2}")

    source_rows = lagged.same_day.prior._source_rows_by_window()
    baselines = lagged.same_day.prior._load_baselines()
    accepted_results, accepted_trades_by_window = lagged._run_lagged_windows(
        baselines,
        source_rows,
    )
    accepted_by_label = {row["label"]: row for row in accepted_results}

    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    all_labeled_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    scaled_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    incremental_target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    state_reports_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in lagged.same_day.prior.base.WINDOWS.items():
        print(f"[{label}] accepted lagged consensus target-state allocation replay")
        before_result = baselines[label]["result"]
        before = accepted_by_label[label]["after"]
        original_trades = accepted_trades_by_window[label]
        labeled_trades, state_report = _state_labeled_trades_for_window(
            label=label,
            cfg=cfg,
            trades=original_trades,
        )
        scaled_trades, incremental_trades = _scale_trades(labeled_trades)
        overlay = lagged.same_day.prior.base._overlay_from_paper_trades(
            before_result,
            scaled_trades,
        )
        after = lagged.same_day.prior.base.overlay_helper._metrics_with_overlay(
            before_result,
            overlay,
        )
        delta = lagged.same_day.prior.base.overlay_helper._delta(after, before)

        before_metrics[label] = before
        after_metrics[label] = after
        all_labeled_trades_by_window[label] = labeled_trades
        scaled_trades_by_window[label] = scaled_trades
        incremental_target_trades_by_window[label] = incremental_trades
        state_reports_by_window[label] = state_report
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(incremental_trades),
            "accepted_lagged_trade_count": len(original_trades),
            "accepted_lagged_target_state_trade_count": len(incremental_trades),
            "incremental_target_pnl": round(
                sum(float(row.get("pnl") or 0.0) for row in incremental_trades),
                2,
            ),
            "overlay_total_pnl_after_scaled_allocation": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = _aggregate_window_rows(window_rows)
    target_summary = _target_trade_summary(incremental_target_trades_by_window)
    all_labeled_rows = [
        row for rows in all_labeled_trades_by_window.values() for row in rows
    ]
    state_counts = Counter(str(row.get("combined_state") or "missing") for row in all_labeled_rows)
    duplicate_diagnostics = _duplicate_diagnostics(all_labeled_rows)
    state_diagnostics = {
        "target_state": TARGET_STATE,
        "target_scalar": TARGET_SCALAR,
        "accepted_lagged_trade_count_total": len(all_labeled_rows),
        "state_labeled_trade_count_total": sum(
            int(row["state_labeled_trade_count"]) for row in state_reports_by_window.values()
        ),
        "missing_state_trade_count_total": sum(
            int(row["missing_state_trade_count"]) for row in state_reports_by_window.values()
        ),
        "target_state_trade_count_total": target_summary["total_trade_count"],
        "state_counts": dict(sorted(state_counts.items())),
        "by_window": state_reports_by_window,
    }
    gate4 = _gate4(
        aggregate=aggregate,
        before_metrics=before_metrics,
        target_summary=target_summary,
        state_diagnostics=state_diagnostics,
        duplicate_diagnostics=duplicate_diagnostics,
    )
    status = "accepted" if gate4["passed"] else "rejected"
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2,
            6,
        ),
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": gate4["decision"],
        "hypothesis": (
            "Accepted lagged free-data consensus paper candidates may deserve "
            "higher allocation only when prior-close state is mixed|balanced|"
            "normal. This tests a frozen 1.25x target-state notional top-up "
            "against the current accepted lagged consensus adapter."
        ),
        "change_type": "default_off_paper_allocation",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "nearby_prior_experiments": [
            "exp-20260606-021",
            "exp-20260606-022",
            "exp-20260604-008",
            "exp-20260604-009",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "read_only_router_grade_state_sleeve_attribution",
        "prediction": PREDICTION,
        "calibration": calibration,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three fixed windows; before is "
                "the accepted exp-20260604-009 lagged consensus default-off "
                "paper adapter replay; after recomputes the same paper overlay "
                "with only the target-state notional scalar changed."
            ),
            "windows": lagged.same_day.prior.base.WINDOWS,
            "source_replay_experiment_id": SOURCE_REPLAY_EXPERIMENT_ID,
            "baseline_comparator_experiment_id": BASELINE_COMPARATOR_EXPERIMENT_ID,
            "state_timing": "prior_trading_day_close_before_entry_open",
            "execution_impact": "none_replay_only_default_off",
        },
        "parameters": {
            "target_state": TARGET_STATE,
            "target_scalar": TARGET_SCALAR,
            "base_adapter": "ACCEPTED_FREE_DATA_CROSS_SOURCE_CONSENSUS_PAPER",
            "notional_changed_only_for_target_state": True,
            "all_other_lagged_consensus_rows_scalar": 1.0,
        },
        "gate_questions": {
            "1_alpha_hypothesis": _preflight_payload()["alpha_hypothesis"],
            "2_history_check": _preflight_payload()["history_check"],
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": _preflight_payload()["acceptance_criteria"],
            "5_reproducibility": _preflight_payload()["reproducibility"],
        },
        "preflight": _preflight_payload(),
        "gate1": {
            "before_comparator": BASELINE_COMPARATOR_EXPERIMENT_ID,
            "source_replay": SOURCE_REPLAY_EXPERIMENT_ID,
            "before_metrics": before_metrics,
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2,
            "runtime_fields": [
                "accepted lagged consensus target trade ticker",
                "accepted lagged consensus target trade entry_date",
                "accepted lagged consensus target trade exit_date",
                "accepted lagged consensus target trade pnl",
                "accepted lagged consensus target trade paper_notional_usd",
                "SPY and QQQ daily OHLCV for prior-close market state",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "minimum_accepted_comparator_survival_rate": gate4[
                "minimum_accepted_comparator_survival_rate"
            ],
            "passed": gate4["survival_guard_passed"],
            "note": (
                "No core filter was added. This is a paper allocation replay "
                "within an accepted default-off sleeve; core signals generated "
                "and survived are unchanged."
            ),
        },
        "gate4": gate4,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict((label, row["delta"]) for label, row in window_rows.items()),
            "aggregate": aggregate,
        },
        "window_rows": window_rows,
        "accepted_lagged_source_results": accepted_results,
        "state_diagnostics": state_diagnostics,
        "duplicate_diagnostics": duplicate_diagnostics,
        "target_trade_summary": target_summary,
        "all_labeled_trades_by_window": all_labeled_trades_by_window,
        "scaled_trades_by_window": scaled_trades_by_window,
        "incremental_target_trades_by_window": incremental_target_trades_by_window,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "interpretation": (
            "The target-state allocation top-up cleared replay Gate 4 as a "
            "default-off lead, but no production surface was promoted."
            if gate4["passed"]
            else (
                "The target-state allocation top-up did not clear Gate 4. "
                "Do not retune the same market-state scalar on these windows; "
                "the next attempt needs materially new forward replacement-"
                "value evidence or a non-overlapping displacement audit."
            )
        ),
        "negative_reflection": (
            "If rejected, the likely reason is that observed normalized sleeve "
            "attribution did not translate into equity-curve EV after sizing "
            "and drawdown accounting, or the 39-row cell remained too "
            "concentrated for allocation. That would argue for fresh forward "
            "replacement-value rows rather than scalar retuning."
        ),
        "next_evidence_needed": (
            "A positive replay lead still needs a shared adapter and parity "
            "test using the same prior-close state label before promotion. A "
            "negative result needs materially new replacement-value evidence, "
            "not another scalar sweep on this same cell."
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Target rows |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in lagged.same_day.prior.base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["incremental_target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    return "\n".join(
        [
            "---",
            f'experiment_id: "{EXPERIMENT_ID}"',
            f'status: "{payload["status"]}"',
            'lane: "alpha_search"',
            f'changed_variable: "{CHANGED_VARIABLE}"',
            "---",
            "",
            f"# Experiment Card: {EXPERIMENT_ID}",
            "",
            "## Summary",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4",
            "",
            *rows,
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate PnL delta: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Target state rows: `{}`".format(
                payload["target_trade_summary"]["total_trade_count"]
            ),
            "- Decision: `{}`".format(gate4["decision"]),
            "- Failed reasons: `{}`".format(", ".join(gate4["failed_reasons"]) or "none"),
            "",
            "## Production Impact",
            "",
            (
                "Replay-only and default-off paper only. No shared policy, run "
                "adapter, backtester adapter, production watchlist, order path, "
                "core entry, ranking, sizing, allocation, or exit behavior changed."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["gate4"]["passed"],
        "mechanism_family": "default_off_paper_allocation",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": (
            "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
        ),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_after": payload["after_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label][
                    "total_pnl"
                ],
                "target_trade_count": len(payload["incremental_target_trades_by_window"][label]),
            }
            for label in lagged.same_day.prior.base.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "negative_reflection": payload["negative_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _update_ticket_and_registry(payload: dict[str, Any], log_record: dict[str, Any]) -> None:
    ticket = _load_json(TICKET_JSON) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "decision": payload["decision"],
            "summary": payload["interpretation"],
            "result": {
                "decision": payload["decision"],
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "aggregate_expected_value_delta": payload["expected_value_score_delta"],
                "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
                "accepted": payload["gate4"]["passed"],
                "calibration": payload["calibration"],
                "gate4": payload["gate4"],
            },
        }
    )
    _write_json(TICKET_JSON, ticket)

    registry = _load_json(REGISTRY_JSON) if REGISTRY_JSON.exists() else {
        "schema_version": 1,
        "experiments": [],
    }
    experiments = registry.setdefault("experiments", [])
    found = False
    for row in experiments:
        if row.get("experiment_id") != EXPERIMENT_ID:
            continue
        row.update(
            {
                "status": payload["status"],
                "completed_at": payload["timestamp"],
                "updated_at": payload["timestamp"],
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "decision": payload["decision"],
                "aggregate_expected_value_delta": log_record[
                    "aggregate_expected_value_delta"
                ],
                "aggregate_strategy_total_pnl_delta": log_record[
                    "aggregate_strategy_total_pnl_delta"
                ],
            }
        )
        found = True
        break
    if not found:
        experiments.append(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "lane": "alpha_search",
                "owner": "alpha-search",
                "hypothesis": payload["hypothesis"],
                "ticket_file": _repo_rel(TICKET_JSON),
                "card_file": _repo_rel(CARD_MD),
                "revision_manifest_file": _repo_rel(MANIFEST_JSON),
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "decision": payload["decision"],
                "aggregate_expected_value_delta": log_record[
                    "aggregate_expected_value_delta"
                ],
                "aggregate_strategy_total_pnl_delta": log_record[
                    "aggregate_strategy_total_pnl_delta"
                ],
                "updated_at": payload["timestamp"],
            }
        )
    registry["updated_at"] = payload["timestamp"]
    _write_json(REGISTRY_JSON, registry)


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_revision_manifest",
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "completed_at": payload["timestamp"],
        "generated_at": _utc_now(),
        "anti_js": "No JavaScript was used.",
        "artifacts": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(TICKET_JSON),
        ],
        "file_hashes": {
            _repo_rel(Path(__file__)): _sha256(Path(__file__)),
            _repo_rel(OUT_JSON): _sha256(OUT_JSON),
            _repo_rel(LOG_JSON): _sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): _sha256(TICKET_JSON),
            _repo_rel(CARD_MD): _sha256(CARD_MD),
        },
    }
    _write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, log_record)
    _write_text(CARD_MD, _build_card(payload))
    _upsert_jsonl(EXPERIMENT_LOG, log_record)
    _update_ticket_and_registry(payload, log_record)
    _write_manifest(payload)


def main() -> None:
    payload = _build_payload()
    persist(payload)
    print(json.dumps(_safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
