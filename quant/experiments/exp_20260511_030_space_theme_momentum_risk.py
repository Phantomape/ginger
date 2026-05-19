"""exp-20260511-030: Space theme momentum risk sweep.

The accepted default-off Space stack uses an official-catalyst candidate pool,
0.75x base risk, a PL/BKSY breakout haircut, and an RKLB/ASTS trend top-up.
This replay changes one variable: an extra risk scalar when same-theme ETF
momentum is negative. UFO/ARKX are used only as benchmark state inputs and are
not allowed to generate tradable signals.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS_DIR = REPO_ROOT / "quant" / "experiments"
QUANT_DIR = REPO_ROOT / "quant"
for path in (str(EXPERIMENTS_DIR), str(QUANT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from data_layer import get_universe  # noqa: E402
from exp_20260511_002_space_catalyst_static_pool_replay import (  # noqa: E402
    WINDOWS,
    _aggregate,
    _delta,
    _open_position_field_audit,
    _round,
    _snapshot_tickers,
)
from exp_20260511_009_space_static_pool_risk_scalar import (  # noqa: E402
    _run_window,
    _space_trade_attribution,
)
from exp_20260511_010_space_official_catalyst_subpool import (  # noqa: E402
    OFFICIAL_CATALYST_TICKERS,
    _aggregate_space_attr,
    _append_once,
    _write_json,
)
from exp_20260511_018_space_data_vendor_trend_gate import (  # noqa: E402
    DATA_VENDOR_TICKERS,
)


EXPERIMENT_ID = "exp-20260511-030"
STEM = "space_theme_momentum_risk"
BASE_SPACE_RISK_SCALAR = 0.75
DATA_VENDOR_BREAKOUT_RISK_SCALAR = 0.25
LAUNCH_CONNECTIVITY_TICKERS = ("RKLB", "ASTS")
LAUNCH_CONNECTIVITY_TREND_RISK_SCALAR = 1.25
THEME_BENCHMARK_TICKERS = ("UFO", "ARKX")
THEME_MOMENTUM_FIELD = "momentum_20d_pct"
THEME_MOMENTUM_MODE = "max"
THEME_MOMENTUM_NEGATIVE_THRESHOLD = 0.0
THEME_WEAK_RISK_SCALARS = (0.0, 0.25, 0.5, 0.75)
MAX_DRAWDOWN_DAMAGE_VS_CORE = 0.02
MAX_DRAWDOWN_DAMAGE_VS_BEFORE = 0.005

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
CURRENT_STATE_MD = REPO_ROOT / "docs" / "current_state.md"
PLAYBOOK_MD = REPO_ROOT / "docs" / "alpha-optimization-playbook.md"


def _upsert_jsonl_record(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    updated: list[str] = []
    replaced = False
    for line in lines:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            updated.append(line)
            continue
        if row.get("experiment_id") == payload["experiment_id"]:
            if not replaced:
                updated.append(json.dumps(payload, ensure_ascii=False, sort_keys=True))
                replaced = True
            continue
        updated.append(line)
    if not replaced:
        updated.append(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    path.write_text("\n".join(updated) + "\n", encoding="utf-8")


def _upsert_markdown_section(
    path: Path,
    heading: str,
    section_text: str,
    *,
    next_heading_prefix: str,
) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if heading not in existing:
        _append_once(path, heading, section_text)
        return

    start = existing.find(heading)
    line_start = existing.rfind("\n", 0, start)
    section_start = 0 if line_start == -1 else line_start + 1
    search_from = start + len(heading)
    next_marker = f"\n{next_heading_prefix} "
    next_start = existing.find(next_marker, search_from)
    section_end = len(existing) if next_start == -1 else next_start + 1
    replacement = section_text.lstrip("\n")
    updated = existing[:section_start] + replacement + existing[section_end:]
    path.write_text(updated, encoding="utf-8")


def _scale_sizing(
    sizing: dict[str, Any],
    scalar: float,
    portfolio_value: float,
    *,
    marker: str,
) -> None:
    old_shares = int(sizing.get("shares_to_buy") or 0)
    if old_shares <= 0:
        return

    new_shares = int(math.floor(old_shares * scalar))
    ratio = new_shares / old_shares if old_shares else 0.0
    old_risk_pct = float(sizing.get("risk_pct") or 0.0)
    old_risk_amount = float(
        sizing.get("risk_amount_usd") or (old_risk_pct * portfolio_value)
    )
    old_position_value = float(sizing.get("position_value_usd") or 0.0)

    sizing[f"{marker}_scalar_applied"] = scalar
    sizing[f"{marker}_baseline_shares"] = old_shares
    sizing[f"{marker}_scaled_shares"] = new_shares
    sizing[f"{marker}_risk_pct_before_scalar"] = old_risk_pct
    sizing[f"{marker}_risk_amount_before_scalar"] = round(old_risk_amount, 2)
    sizing["shares_to_buy"] = new_shares
    sizing["risk_pct"] = old_risk_pct * ratio
    sizing["risk_amount_usd"] = round(old_risk_amount * ratio, 2)
    sizing["position_value_usd"] = round(old_position_value * ratio, 2)
    sizing["position_pct_of_portfolio"] = (
        round((old_position_value * ratio) / portfolio_value, 4)
        if portfolio_value
        else 0.0
    )


def _theme_momentum(features_dict: dict[str, dict[str, Any]]) -> dict[str, Any]:
    values: dict[str, float] = {}
    for ticker in THEME_BENCHMARK_TICKERS:
        raw_value = (features_dict.get(ticker) or {}).get(THEME_MOMENTUM_FIELD)
        if isinstance(raw_value, (int, float)) and not math.isnan(float(raw_value)):
            values[ticker] = float(raw_value)

    if not values:
        return {
            "value": None,
            "state": "missing",
            "values": {},
        }
    if THEME_MOMENTUM_MODE == "max":
        value = max(values.values())
    else:
        value = sum(values.values()) / len(values)
    state = (
        "weak"
        if value < THEME_MOMENTUM_NEGATIVE_THRESHOLD
        else "confirmed"
    )
    return {
        "value": round(value, 6),
        "state": state,
        "values": {ticker: round(value, 6) for ticker, value in sorted(values.items())},
    }


@contextmanager
def _patched_space_theme_stack(theme_weak_scalar: float):
    import portfolio_engine  # noqa: PLC0415
    import risk_engine  # noqa: PLC0415
    import signal_engine  # noqa: PLC0415

    original_generate_signals = signal_engine.generate_signals
    original_size_signals = portfolio_engine.size_signals
    original_compute_portfolio_heat = portfolio_engine.compute_portfolio_heat
    original_enrich_signals = risk_engine.enrich_signals
    official = {ticker.upper() for ticker in OFFICIAL_CATALYST_TICKERS}
    data_vendors = {ticker.upper() for ticker in DATA_VENDOR_TICKERS}
    launch_connectivity = {ticker.upper() for ticker in LAUNCH_CONNECTIVITY_TICKERS}
    benchmarks = {ticker.upper() for ticker in THEME_BENCHMARK_TICKERS}
    adjustments: list[dict[str, Any]] = []
    signal_state_counts: Counter[str] = Counter()
    theme_day_counts: Counter[str] = Counter()

    def wrapped_generate_signals(features_dict, *args, **kwargs):
        theme = _theme_momentum(features_dict)
        theme_day_counts[theme["state"]] += 1
        tradable_features = {
            ticker: features
            for ticker, features in features_dict.items()
            if str(ticker).upper() not in benchmarks
        }
        signals = original_generate_signals(tradable_features, *args, **kwargs)
        for sig in signals:
            ticker = str(sig.get("ticker") or "").upper()
            if ticker not in official:
                continue
            sig["space_theme_momentum_state"] = theme["state"]
            sig["space_theme_momentum_20d_pct"] = theme["value"]
            sig["space_theme_momentum_values"] = theme["values"]
            sig["space_theme_momentum_benchmark_mode"] = THEME_MOMENTUM_MODE
            signal_state_counts[theme["state"]] += 1
        return signals

    def _without_benchmarks(features_dict):
        if not features_dict:
            return features_dict
        return {
            ticker: features
            for ticker, features in features_dict.items()
            if str(ticker).upper() not in benchmarks
        }

    def wrapped_enrich_signals(signals, features_dict, atr_target_mult=None):
        return original_enrich_signals(
            signals,
            _without_benchmarks(features_dict),
            atr_target_mult=atr_target_mult,
        )

    def wrapped_compute_portfolio_heat(
        open_positions,
        current_prices,
        portfolio_value,
        features_dict=None,
    ):
        return original_compute_portfolio_heat(
            open_positions,
            current_prices,
            portfolio_value,
            features_dict=_without_benchmarks(features_dict),
        )

    def wrapped_size_signals(signals, portfolio_value, risk_pct=None):
        sized = original_size_signals(signals, portfolio_value, risk_pct=risk_pct)
        for sig in sized:
            ticker = str(sig.get("ticker") or "").upper()
            strategy = str(sig.get("strategy") or "").lower()
            sizing = sig.get("sizing")
            if ticker not in official or not sizing:
                continue

            before_shares = int(sizing.get("shares_to_buy") or 0)
            _scale_sizing(
                sizing,
                BASE_SPACE_RISK_SCALAR,
                portfolio_value,
                marker="space_official_base_risk",
            )

            data_vendor_breakout = ticker in data_vendors and strategy == "breakout_long"
            launch_connectivity_trend = (
                ticker in launch_connectivity and strategy == "trend_long"
            )
            if data_vendor_breakout:
                _scale_sizing(
                    sizing,
                    DATA_VENDOR_BREAKOUT_RISK_SCALAR,
                    portfolio_value,
                    marker="space_data_vendor_breakout_risk",
                )
            if launch_connectivity_trend:
                _scale_sizing(
                    sizing,
                    LAUNCH_CONNECTIVITY_TREND_RISK_SCALAR,
                    portfolio_value,
                    marker="space_launch_connectivity_trend_risk",
                )

            theme_state = sig.get("space_theme_momentum_state")
            theme_weak = theme_state == "weak"
            if theme_weak and theme_weak_scalar != 1.0:
                _scale_sizing(
                    sizing,
                    theme_weak_scalar,
                    portfolio_value,
                    marker="space_theme_weak_risk",
                )

            if data_vendor_breakout or launch_connectivity_trend or theme_weak:
                adjustments.append(
                    {
                        "ticker": ticker,
                        "strategy": strategy,
                        "theme_state": theme_state,
                        "theme_momentum_20d_pct": sig.get(
                            "space_theme_momentum_20d_pct"
                        ),
                        "theme_momentum_values": sig.get(
                            "space_theme_momentum_values"
                        ),
                        "theme_weak_risk_scalar": (
                            theme_weak_scalar if theme_weak else None
                        ),
                        "marker": (
                            "theme_weak"
                            if theme_weak
                            else "data_vendor_breakout"
                            if data_vendor_breakout
                            else "launch_connectivity_trend"
                        ),
                        "shares_before_space_scalars": before_shares,
                        "shares_after_space_scalars": int(
                            sizing.get("shares_to_buy") or 0
                        ),
                        "trade_quality_score": _round(
                            sig.get("trade_quality_score"),
                            4,
                        ),
                        "confidence_score": _round(sig.get("confidence_score"), 4),
                    }
                )
        return sized

    signal_engine.generate_signals = wrapped_generate_signals
    risk_engine.enrich_signals = wrapped_enrich_signals
    portfolio_engine.compute_portfolio_heat = wrapped_compute_portfolio_heat
    portfolio_engine.size_signals = wrapped_size_signals
    try:
        yield {
            "adjustments": adjustments,
            "signal_state_counts": signal_state_counts,
            "theme_day_counts": theme_day_counts,
        }
    finally:
        signal_engine.generate_signals = original_generate_signals
        risk_engine.enrich_signals = original_enrich_signals
        portfolio_engine.compute_portfolio_heat = original_compute_portfolio_heat
        portfolio_engine.size_signals = original_size_signals


def _run_space_variant(
    label: str,
    spec: dict[str, str],
    core_universe: list[str],
    included: list[str],
    theme_weak_scalar: float,
) -> dict[str, Any]:
    universe = sorted(
        set(core_universe)
        | set(included)
        | {ticker.upper() for ticker in THEME_BENCHMARK_TICKERS}
    )
    with _patched_space_theme_stack(theme_weak_scalar) as state:
        result = _run_window(label, spec, universe, spec["candidate_snapshot"])
    result["space_stack_adjustments"] = state["adjustments"]
    result["space_theme_signal_state_counts"] = dict(
        sorted(state["signal_state_counts"].items())
    )
    result["space_theme_day_counts"] = dict(sorted(state["theme_day_counts"].items()))
    return result


def _adjustment_summary(adjusted: list[dict[str, Any]]) -> dict[str, Any]:
    theme_rows = [row for row in adjusted if row["marker"] == "theme_weak"]
    return {
        "adjusted_signal_count": len(adjusted),
        "theme_weak_signal_count": len(theme_rows),
        "theme_weak_by_ticker": dict(
            sorted(Counter(row["ticker"] for row in theme_rows).items())
        ),
        "theme_weak_by_strategy": dict(
            sorted(Counter(row["strategy"] for row in theme_rows).items())
        ),
        "adjusted_by_marker": dict(
            sorted(Counter(row["marker"] for row in adjusted).items())
        ),
        "sample_adjusted": adjusted[:18],
    }


def _gate(
    core_agg: dict[str, Any],
    before_agg: dict[str, Any],
    after_agg: dict[str, Any],
    delta_vs_before: dict[str, dict[str, Any]],
    delta_vs_core: dict[str, dict[str, Any]],
    theme_attr: dict[str, Any],
    theme_adjusted_count: int,
) -> dict[str, Any]:
    agg_delta_vs_before = _delta(after_agg, before_agg)
    agg_delta_vs_core = _delta(after_agg, core_agg)
    ev_improved_vs_before = sum(
        1
        for delta in delta_vs_before.values()
        if delta.get("expected_value_score", 0.0) > 0
    )
    ev_regressed_vs_before = sum(
        1
        for delta in delta_vs_before.values()
        if delta.get("expected_value_score", 0.0) < 0
    )
    ev_improved_vs_core = sum(
        1
        for delta in delta_vs_core.values()
        if delta.get("expected_value_score", 0.0) > 0
    )
    max_dd_worsening_vs_core = max(
        delta.get("max_drawdown_pct", 0.0) for delta in delta_vs_core.values()
    )
    max_dd_change_vs_before = max(
        delta.get("max_drawdown_pct", 0.0) for delta in delta_vs_before.values()
    )
    passed = (
        agg_delta_vs_before.get("expected_value_score_sum", 0.0) > 0
        and agg_delta_vs_before.get("total_pnl_sum", 0.0) > 0
        and ev_improved_vs_before >= 2
        and ev_regressed_vs_before == 0
        and ev_improved_vs_core == len(WINDOWS)
        and max_dd_worsening_vs_core <= MAX_DRAWDOWN_DAMAGE_VS_CORE
        and max_dd_change_vs_before <= MAX_DRAWDOWN_DAMAGE_VS_BEFORE
        and after_agg.get("min_survival_rate", 0.0) >= 0.05
        and theme_adjusted_count > 0
        and theme_attr.get("trade_count", 0) > 0
        and (
            theme_attr["single_ticker_positive_share"] is None
            or theme_attr["single_ticker_positive_share"] <= 0.70
        )
    )
    return {
        "passed": passed,
        "aggregate_delta_vs_before": agg_delta_vs_before,
        "aggregate_delta_vs_core": agg_delta_vs_core,
        "windows_ev_improved_vs_before": ev_improved_vs_before,
        "windows_ev_regressed_vs_before": ev_regressed_vs_before,
        "windows_ev_improved_vs_core": ev_improved_vs_core,
        "max_drawdown_worsening_vs_core": _round(max_dd_worsening_vs_core, 4),
        "max_drawdown_change_vs_before": _round(max_dd_change_vs_before, 4),
        "theme_adjusted_signal_count": theme_adjusted_count,
    }


def _build_variant(
    scalar: float,
    core_universe: list[str],
    core_by_window: dict[str, dict[str, Any]],
    before_by_window: dict[str, dict[str, Any]],
    included_by_window: dict[str, list[str]],
    core_agg: dict[str, Any],
    before_agg: dict[str, Any],
) -> dict[str, Any]:
    by_window: dict[str, dict[str, Any]] = {}
    for label, spec in WINDOWS.items():
        included = included_by_window[label]
        after = _run_space_variant(label, spec, core_universe, included, scalar)
        before = before_by_window[label]
        core = core_by_window[label]
        theme_adjustment = _adjustment_summary(after["space_stack_adjustments"])
        by_window[label] = {
            "window": spec,
            "included_space_tickers": included,
            "theme_benchmark_tickers": list(THEME_BENCHMARK_TICKERS),
            "core_metrics": core["metrics"],
            "before_metrics": before["metrics"],
            "after_metrics": after["metrics"],
            "delta_vs_core": _delta(after["metrics"], core["metrics"]),
            "delta_vs_before": _delta(after["metrics"], before["metrics"]),
            "before_space_trade_attribution": _space_trade_attribution(
                before["trades"],
                set(included),
            ),
            "after_space_trade_attribution": _space_trade_attribution(
                after["trades"],
                set(included),
            ),
            "theme_weak_trade_attribution": _space_trade_attribution(
                [
                    trade
                    for trade in after["trades"]
                    if str(trade.get("ticker") or "").upper()
                    in theme_adjustment["theme_weak_by_ticker"]
                ],
                set(theme_adjustment["theme_weak_by_ticker"]),
            ),
            "space_theme_signal_state_counts": after[
                "space_theme_signal_state_counts"
            ],
            "space_theme_day_counts": after["space_theme_day_counts"],
            "space_theme_adjustment": theme_adjustment,
        }

    after_metrics = {label: row["after_metrics"] for label, row in by_window.items()}
    delta_vs_before = {
        label: row["delta_vs_before"] for label, row in by_window.items()
    }
    delta_vs_core = {label: row["delta_vs_core"] for label, row in by_window.items()}
    after_agg = _aggregate(after_metrics)
    theme_attr = _aggregate_space_attr(
        {
            label: {
                "space_trade_attribution": row["theme_weak_trade_attribution"]
            }
            for label, row in by_window.items()
        }
    )
    space_attr = _aggregate_space_attr(
        {
            label: {"space_trade_attribution": row["after_space_trade_attribution"]}
            for label, row in by_window.items()
        }
    )
    theme_adjusted_count = sum(
        row["space_theme_adjustment"]["theme_weak_signal_count"]
        for row in by_window.values()
    )
    gate = _gate(
        core_agg,
        before_agg,
        after_agg,
        delta_vs_before,
        delta_vs_core,
        theme_attr,
        theme_adjusted_count,
    )
    return {
        "theme_weak_risk_scalar": scalar,
        "after_metrics": after_metrics,
        "after_aggregate": after_agg,
        "delta_metrics": {
            "aggregate_vs_before": gate["aggregate_delta_vs_before"],
            "aggregate_vs_core": gate["aggregate_delta_vs_core"],
            "by_window_vs_before": delta_vs_before,
            "by_window_vs_core": delta_vs_core,
        },
        "gate": gate,
        "theme_weak_trade_attribution": theme_attr,
        "space_trade_attribution": space_attr,
        "by_window": by_window,
    }


def run_experiment() -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    core_universe = sorted({str(ticker).upper() for ticker in get_universe()})

    core_by_window: dict[str, dict[str, Any]] = {}
    before_by_window: dict[str, dict[str, Any]] = {}
    included_by_window: dict[str, list[str]] = {}
    benchmark_availability: dict[str, dict[str, bool]] = {}

    for label, spec in WINDOWS.items():
        snapshot_tickers = _snapshot_tickers(REPO_ROOT / spec["candidate_snapshot"])
        included = sorted(set(OFFICIAL_CATALYST_TICKERS) & snapshot_tickers)
        included_by_window[label] = included
        benchmark_availability[label] = {
            ticker: ticker in snapshot_tickers for ticker in THEME_BENCHMARK_TICKERS
        }
        core_by_window[label] = _run_window(
            label,
            spec,
            core_universe,
            spec["baseline_snapshot"],
        )
        before_by_window[label] = _run_space_variant(
            label,
            spec,
            core_universe,
            included,
            theme_weak_scalar=1.0,
        )

    core_metrics = {label: row["metrics"] for label, row in core_by_window.items()}
    before_metrics = {
        label: row["metrics"] for label, row in before_by_window.items()
    }
    core_agg = _aggregate(core_metrics)
    before_agg = _aggregate(before_metrics)

    variants = {
        str(scalar): _build_variant(
            scalar,
            core_universe,
            core_by_window,
            before_by_window,
            included_by_window,
            core_agg,
            before_agg,
        )
        for scalar in THEME_WEAK_RISK_SCALARS
    }
    passing = [row for row in variants.values() if row["gate"]["passed"]]
    if passing:
        best = max(
            passing,
            key=lambda row: (
                row["gate"]["aggregate_delta_vs_before"][
                    "expected_value_score_sum"
                ],
                row["gate"]["aggregate_delta_vs_before"]["total_pnl_sum"],
            ),
        )
    else:
        best = max(
            variants.values(),
            key=lambda row: (
                row["gate"]["aggregate_delta_vs_before"][
                    "expected_value_score_sum"
                ],
                row["gate"]["aggregate_delta_vs_before"]["total_pnl_sum"],
            ),
        )

    if best["gate"]["passed"]:
        decision = "accepted_theme_weak_space_risk_scalar_shadow"
        rejection_reason = None
        interpretation = (
            "Same-theme ETF weakness improved the accepted Space replay stack "
            "under the pre-registered three-window gate. Promotion still requires "
            "moving the state/scalar into a shared policy used by production and "
            "backtest adapters before it can affect live behavior."
        )
    else:
        decision = "rejected_theme_weak_space_risk_scalar"
        rejection_reason = (
            "No tested UFO/ARKX negative 20-day momentum risk scalar cleared the "
            "three-window gate versus the accepted exp-20260511-021 Space stack."
        )
        interpretation = (
            "Do not add a theme ETF momentum risk gate to the Space sleeve. The "
            "accepted Space stack should stay focused on catalyst bucket and "
            "ticker/strategy lifecycle scalars, not theme ETF timing."
        )

    open_position_audit = _open_position_field_audit()
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": generated_at,
        "status": decision,
        "lane": "alpha_search",
        "hypothesis": (
            "risk allocation: official Space-catalyst entries should keep full "
            "accepted-stack risk only when same-theme ETF momentum confirms; "
            "when max(UFO, ARKX) 20-day momentum is negative, de-risk Space "
            "signals instead of adding noisy ticker breadth or using "
            "underpowered LLM soft-ranking."
        ),
        "change_type": "risk_allocation_shadow_sweep",
        "changed_variable": "space_theme_weak_risk_scalar",
        "single_causal_variable": "space_theme_weak_risk_scalar",
        "parameters": {
            "before_hypothesis_source": "exp-20260511-021",
            "official_candidate_pool": list(OFFICIAL_CATALYST_TICKERS),
            "base_space_risk_scalar": BASE_SPACE_RISK_SCALAR,
            "accepted_data_vendor_breakout_risk_scalar": (
                DATA_VENDOR_BREAKOUT_RISK_SCALAR
            ),
            "accepted_launch_connectivity_trend_risk_scalar": (
                LAUNCH_CONNECTIVITY_TREND_RISK_SCALAR
            ),
            "theme_benchmarks": list(THEME_BENCHMARK_TICKERS),
            "theme_momentum_field": THEME_MOMENTUM_FIELD,
            "theme_momentum_mode": THEME_MOMENTUM_MODE,
            "theme_momentum_negative_threshold": (
                THEME_MOMENTUM_NEGATIVE_THRESHOLD
            ),
            "tested_theme_weak_risk_scalars": list(THEME_WEAK_RISK_SCALARS),
            "best_theme_weak_risk_scalar": best["theme_weak_risk_scalar"],
            "benchmark_availability": benchmark_availability,
            "locked_variables": [
                "official-catalyst candidate pool membership",
                "base Space risk scalar 0.75",
                "PL/BKSY breakout 0.25x haircut",
                "RKLB/ASTS trend 1.25x top-up",
                "core production universe",
                "core signal generation",
                "core entry filters",
                "ranking",
                "MAX_POSITIONS",
                "slot routing",
                "exits",
                "add-ons",
                "LLM/news replay",
                "live pilot slots",
            ],
        },
        "date_range": {
            label: f"{spec['start']} -> {spec['end']}"
            for label, spec in WINDOWS.items()
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three-window fixed protocol. Core "
            "baseline uses canonical snapshots; before reproduces the accepted "
            "exp-20260511-021 default-off Space stack; after changes only the "
            "risk scalar for Space official-catalyst signals when max(UFO, ARKX) "
            "20-day momentum is negative. UFO/ARKX are excluded from tradable "
            "signals inside the replay patch."
        ),
        "core_baseline_metrics": core_metrics,
        "before_metrics": before_metrics,
        "after_metrics": best["after_metrics"],
        "delta_metrics": best["delta_metrics"],
        "expected_value_score_delta": best["gate"][
            "aggregate_delta_vs_before"
        ].get("expected_value_score_sum"),
        "core_aggregate": core_agg,
        "before_aggregate": before_agg,
        "after_aggregate": best["after_aggregate"],
        "gate_questions": {
            "alpha_hypothesis": (
                "risk allocation: de-risk official Space signals during "
                "same-theme ETF weakness."
            ),
            "prior_similar_experiments": [
                "exp-20260511-011 accepted official-catalyst Space 0.75x default-off risk.",
                "exp-20260511-019 accepted a PL/BKSY breakout-only 0.25x haircut.",
                "exp-20260511-021 accepted an RKLB/ASTS trend-only 1.25x top-up.",
                "exp-20260511-026 rejected mature satcom breadth.",
                "exp-20260511-028 rejected a separate RKLB/ASTS breakout risk scalar.",
                "No prior Space run isolated UFO/ARKX theme momentum as a risk state.",
            ],
            "single_causal_variable": (
                "extra risk scalar for Space official-catalyst signals when "
                "same-theme ETF 20-day momentum is negative."
            ),
            "acceptance_standard": (
                "Must improve aggregate EV/PnL versus exp021, improve at least "
                "2/3 EV windows without any EV-regressed window versus exp021, "
                "stay EV-positive in all windows versus core, keep drawdown "
                "damage versus core <= 2 pp and versus exp021 <= 0.5 pp, keep "
                "survival >= 5%, adjust at least one weak-theme signal, and "
                "avoid positive contribution concentration > 70%."
            ),
            "reproducibility": (
                "This script reruns core, exp021-equivalent before, and each "
                "theme-weak scalar across the three fixed snapshots."
            ),
        },
        "gate_results": {
            "gate1": {
                "baseline_protocol": "docs/backtesting.md three fixed windows",
                "core_baseline_artifact": "data/backtest_results_*.json plus this experiment payload",
                "before_artifact": str(OUT_JSON.relative_to(REPO_ROOT)),
                "known_bias": (
                    "Space candidate snapshots are frozen historical replay "
                    "copies built from a 2026-05-10 research universe; positive "
                    "results cannot directly promote production eligibility."
                ),
            },
            "gate2": {
                "rule_dependencies": [
                    "ticker",
                    "strategy",
                    "feature_layer.compute_features momentum_20d_pct for UFO/ARKX",
                    "portfolio_engine.size_signals sizing payload",
                    "operator_inputs/open_positions.json entry_date",
                    "operator_inputs/open_positions.json target_price",
                ],
                "benchmark_availability": benchmark_availability,
                "open_position_field_audit": open_position_audit,
                "passed": (
                    open_position_audit.get("passed") is True
                    and all(
                        all(row.values()) for row in benchmark_availability.values()
                    )
                ),
            },
            "gate3": {
                "new_filter_added": False,
                "survival_rate_min_after": best["after_aggregate"][
                    "min_survival_rate"
                ],
                "survival_rate_floor": 0.05,
                "passed": best["after_aggregate"]["min_survival_rate"] >= 0.05,
            },
            "gate4": best["gate"],
        },
        "variants": variants,
        "best_variant": {
            "theme_weak_risk_scalar": best["theme_weak_risk_scalar"],
            "gate": best["gate"],
            "theme_weak_trade_attribution": best[
                "theme_weak_trade_attribution"
            ],
            "space_trade_attribution": best["space_trade_attribution"],
        },
        "by_window": best["by_window"],
        "interpretation": interpretation,
        "decision": decision,
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "If rejected, pivot away from ETF theme timing and test a different "
            "Space alpha variable such as event bucket decay or candidate pool "
            "extension with explicit official-catalyst evidence."
        ),
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm_soft_ranking": (
                "Space LLM/event-state soft ranking has insufficient mature "
                "closed outcomes; this run tests deterministic risk allocation "
                "using existing OHLCV-derived theme benchmarks."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "live_slots_changed": False,
            "live_slots": 0,
        },
        "why_not_other_changes": (
            "LLM soft-ranking is underpowered, mature satcom breadth was "
            "rejected, adjacent ticker expansion risks noise, and RKLB/ASTS "
            "breakout refinement failed. This tests a Space-specific theme "
            "state without changing candidate breadth."
        ),
        "known_risks": [
            "Candidate membership is static and selected after the historical windows.",
            "UFO/ARKX are broad theme ETFs and may lag idiosyncratic official catalysts.",
            "Replay-only positive evidence would still need shared policy promotion and parity tests.",
        ],
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "docs/experiment_log.jsonl",
            "docs/current_state.md",
            "docs/alpha-optimization-playbook.md",
        ],
    }
    return payload


def _write_artifact(payload: dict[str, Any]) -> None:
    best = payload["best_variant"]
    lines = [
        f"# {EXPERIMENT_ID} Space theme momentum risk",
        "",
        f"- decision: {payload['decision']}",
        f"- hypothesis: {payload['hypothesis']}",
        f"- changed_variable: {payload['changed_variable']}",
        "- before_state: exp-20260511-021 accepted Space stack",
        f"- best_theme_weak_risk_scalar: {best['theme_weak_risk_scalar']}",
        f"- expected_value_score_delta_vs_before: {payload['expected_value_score_delta']}",
        f"- rejection_reason: {payload['rejection_reason']}",
        "",
        "## Sweep",
        "",
        "| Scalar | Gate | dEV vs before | dPnL vs before | dDD vs core | EV improved windows | Weak signals |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ]
    for scalar_key, row in payload["variants"].items():
        gate = row["gate"]
        lines.append(
            "| {scalar} | {gate_result} | {dev:+.4f} | {dpnl:+.2f} | "
            "{ddd:+.4f} | {evw}/3 | {weak} |".format(
                scalar=scalar_key,
                gate_result="pass" if gate["passed"] else "fail",
                dev=gate["aggregate_delta_vs_before"].get(
                    "expected_value_score_sum",
                    0.0,
                ),
                dpnl=gate["aggregate_delta_vs_before"].get("total_pnl_sum", 0.0),
                ddd=gate["max_drawdown_worsening_vs_core"],
                evw=gate["windows_ev_improved_vs_before"],
                weak=gate["theme_adjusted_signal_count"],
            )
        )
    lines.extend(
        [
            "",
            "## Best Three-Window Comparison",
            "",
            "| Window | Before EV | After EV | dEV vs before | dEV vs core | Before PnL | After PnL | dPnL | Weak signals | Theme states |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for label, row in payload["by_window"].items():
        lines.append(
            "| {label} | {before_ev:.4f} | {after_ev:.4f} | {dev:+.4f} | "
            "{core_dev:+.4f} | {before_pnl:.2f} | {after_pnl:.2f} | {dpnl:+.2f} | "
            "{weak} | {states} |".format(
                label=label,
                before_ev=row["before_metrics"]["expected_value_score"],
                after_ev=row["after_metrics"]["expected_value_score"],
                dev=row["delta_vs_before"].get("expected_value_score", 0.0),
                core_dev=row["delta_vs_core"].get("expected_value_score", 0.0),
                before_pnl=row["before_metrics"]["total_pnl"],
                after_pnl=row["after_metrics"]["total_pnl"],
                dpnl=row["delta_vs_before"].get("total_pnl", 0.0),
                weak=row["space_theme_adjustment"]["theme_weak_signal_count"],
                states=json.dumps(
                    row["space_theme_signal_state_counts"],
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            )
        )
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            f"- core: {payload['core_aggregate']}",
            f"- before_exp021_stack: {payload['before_aggregate']}",
            f"- after_best: {payload['after_aggregate']}",
            f"- gate: {best['gate']}",
            f"- theme_weak_trade_attribution: {best['theme_weak_trade_attribution']}",
            "",
            "## Production Impact",
            "",
            json.dumps(payload["production_impact"], ensure_ascii=False, sort_keys=True),
            "",
            "## Interpretation",
            "",
            payload["interpretation"],
            "",
        ]
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines), encoding="utf-8")


def _append_records(payload: dict[str, Any]) -> None:
    log_record = {
        "timestamp": payload["timestamp"],
        "experiment_id": EXPERIMENT_ID,
        "lane": "alpha_search",
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "changed_variable": payload["changed_variable"],
        "parameters": payload["parameters"],
        "date_range": payload["date_range"],
        "backtest_protocol": payload["backtest_protocol"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "decision": payload["decision"],
        "rejection_reason": payload["rejection_reason"],
        "next_evidence_needed": payload["next_evidence_needed"],
        "production_impact": payload["production_impact"],
        "artifact": str(OUT_JSON.relative_to(REPO_ROOT)),
    }
    _upsert_jsonl_record(EXPERIMENT_LOG_JSONL, log_record)

    state_text = f"""

## {EXPERIMENT_ID} Space theme momentum risk

- timestamp: {payload['timestamp']}
- lane: alpha_search
- decision: {payload['decision']}
- changed_variable: {payload['changed_variable']}
- best_theme_weak_risk_scalar: {payload['best_variant']['theme_weak_risk_scalar']}
- expected_value_score_delta_vs_before: {payload['expected_value_score_delta']}
- before_aggregate: {payload['before_aggregate']}
- after_aggregate: {payload['after_aggregate']}
- interpretation: {payload['interpretation']}
- production_impact: {payload['production_impact']}
- artifact: `{OUT_JSON.relative_to(REPO_ROOT)}`
"""
    _upsert_markdown_section(
        CURRENT_STATE_MD,
        f"## {EXPERIMENT_ID} Space theme momentum risk",
        state_text,
        next_heading_prefix="##",
    )

    playbook_text = f"""

### {EXPERIMENT_ID} Space theme momentum risk

- Decision: {payload['decision']}.
- Tested variable: `{payload['changed_variable']}` using max(UFO, ARKX) `{THEME_MOMENTUM_FIELD}` < `{THEME_MOMENTUM_NEGATIVE_THRESHOLD}`.
- Best scalar: `{payload['best_variant']['theme_weak_risk_scalar']}`.
- Aggregate EV delta vs exp021 stack: `{payload['expected_value_score_delta']}`.
- Interpretation: {payload['interpretation']}
- If rejected, avoid Space ETF timing gates and move to a different alpha variable such as official-catalyst bucket decay or carefully evidenced pool extension.
"""
    _upsert_markdown_section(
        PLAYBOOK_MD,
        f"### {EXPERIMENT_ID} Space theme momentum risk",
        playbook_text,
        next_heading_prefix="###",
    )


def write_outputs(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["decision"],
        "lane": payload["lane"],
        "hypothesis": payload["hypothesis"],
        "changed_variable": payload["changed_variable"],
        "decision": payload["decision"],
        "best_variant": payload["best_variant"],
        "next_evidence_needed": payload["next_evidence_needed"],
        "created_at": payload["timestamp"],
    }
    _write_json(TICKET_JSON, ticket)
    _write_artifact(payload)
    _append_records(payload)


if __name__ == "__main__":
    result = run_experiment()
    write_outputs(result)
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "decision": result["decision"],
                "expected_value_score_delta": result["expected_value_score_delta"],
                "best_variant": result["best_variant"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
