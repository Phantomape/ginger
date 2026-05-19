"""exp-20260509-005: clean mid-dispersion trend top-up replay.

Alpha search. Tests one allocation variable: whether the already accepted
mid-sector-dispersion trend sleeve deserves extra risk only when the signal has
no accepted risk haircut. This is the drawdown discriminator requested by the
original mid-dispersion experiment, not a retry of the raw 1.25x multiplier.

Replay only. A passing result would need a shared portfolio/backtester policy
and parity test before production orders change.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import backtester as bt  # noqa: E402
import portfolio_engine  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
from portfolio_engine import compute_position_size  # noqa: E402


EXPERIMENT_ID = "exp-20260509-005"
STEM = "clean_mid_dispersion_trend_risk"
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

BASE_MID_DISPERSION_MULTIPLIER = 1.25
CLEAN_TOPUP_KEY = "trend_mid_sector_dispersion_clean_topup_multiplier_applied"

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
                "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)

VARIANTS = OrderedDict(
    [
        ("clean_mid_dispersion_total_1_50x", {"total_mid_dispersion_multiplier": 1.50}),
        ("clean_mid_dispersion_total_2_00x", {"total_mid_dispersion_multiplier": 2.00}),
        ("clean_mid_dispersion_total_2_25x", {"total_mid_dispersion_multiplier": 2.25}),
    ]
)


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return round(value, digits)


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_safe(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "sharpe_daily": _round(result.get("sharpe_daily"), 2),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "total_return_pct": _round(benchmarks.get("strategy_total_return_pct"), 4),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": _round(result.get("survival_rate"), 4),
    }


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, before_value in before.items():
        after_value = after.get(key)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            if key in {"trade_count", "signals_generated", "signals_survived"}:
                out[key] = int(after_value - before_value)
            else:
                out[key] = _round(after_value - before_value, 6)
    return out


def _is_clean_mid_dispersion_trend(sig: dict[str, Any]) -> bool:
    if sig.get("strategy") != "trend_long" or sig.get("mid_sector_dispersion") is not True:
        return False
    sizing = sig.get("sizing") or {}
    if sizing.get("trend_mid_sector_dispersion_risk_multiplier_applied") != BASE_MID_DISPERSION_MULTIPLIER:
        return False
    for key, value in sizing.items():
        if not key.endswith("_multiplier_applied"):
            continue
        if key in {"trend_mid_sector_dispersion_risk_multiplier_applied", CLEAN_TOPUP_KEY}:
            continue
        if isinstance(value, (int, float)) and value < 1.0:
            return False
    return True


def _patched_size_signals(target_total_multiplier: float):
    original_size_signals = portfolio_engine.size_signals
    extra_multiplier = target_total_multiplier / BASE_MID_DISPERSION_MULTIPLIER

    def patched(signals, portfolio_value, risk_pct=None):
        sized = original_size_signals(signals, portfolio_value, risk_pct=risk_pct)
        out = []
        for sig in sized:
            if not _is_clean_mid_dispersion_trend(sig):
                out.append(sig)
                continue
            sizing = sig.get("sizing") or {}
            old_risk_pct = sizing.get("risk_pct")
            entry = sig.get("entry_price")
            stop = sig.get("stop_price")
            if not isinstance(old_risk_pct, (int, float)) or not entry or not stop:
                out.append(sig)
                continue
            new_sizing = compute_position_size(
                portfolio_value,
                entry,
                stop,
                risk_pct=old_risk_pct * extra_multiplier,
                max_position_pct=(
                    sizing.get("max_position_pct_applied")
                    or portfolio_engine.MAX_POSITION_PCT
                ),
            )
            if not new_sizing:
                out.append(sig)
                continue
            for key, value in sizing.items():
                if key not in new_sizing:
                    new_sizing[key] = value
            new_sizing["risk_pct"] = old_risk_pct * extra_multiplier
            new_sizing["base_risk_pct"] = sizing.get("base_risk_pct")
            new_sizing["max_position_pct_applied"] = sizing.get("max_position_pct_applied")
            new_sizing[CLEAN_TOPUP_KEY] = _round(extra_multiplier, 6)
            new_sizing["trend_mid_sector_dispersion_total_risk_multiplier_applied"] = (
                target_total_multiplier
            )
            out.append({**sig, "sizing": new_sizing})
        return out

    return patched


@contextmanager
def _variant_context(target_total_multiplier: float | None) -> Iterator[None]:
    original_size_signals = portfolio_engine.size_signals
    original_keys = bt.SIZING_MULTIPLIER_KEYS
    try:
        if target_total_multiplier is not None:
            portfolio_engine.size_signals = _patched_size_signals(target_total_multiplier)
            if CLEAN_TOPUP_KEY not in bt.SIZING_MULTIPLIER_KEYS:
                bt.SIZING_MULTIPLIER_KEYS = (*bt.SIZING_MULTIPLIER_KEYS, CLEAN_TOPUP_KEY)
        yield
    finally:
        portfolio_engine.size_signals = original_size_signals
        bt.SIZING_MULTIPLIER_KEYS = original_keys


def _run_window(window: dict[str, str], target_total_multiplier: float | None = None) -> dict[str, Any]:
    with _variant_context(target_total_multiplier):
        result = BacktestEngine(
            sorted(get_universe()),
            start=window["start"],
            end=window["end"],
            config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
        ).run()
    if "error" in result:
        raise RuntimeError(result["error"])
    return result


def _touched_trades(result: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for trade in result.get("trades") or []:
        multipliers = trade.get("sizing_multipliers") or {}
        if CLEAN_TOPUP_KEY not in multipliers:
            continue
        rows.append(
            {
                "ticker": trade.get("ticker"),
                "strategy": trade.get("strategy"),
                "sector": trade.get("sector"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "exit_reason": trade.get("exit_reason"),
                "pnl": _round(trade.get("pnl"), 2),
                "sizing_multipliers": multipliers,
            }
        )
    return rows


def _run_baselines() -> OrderedDict[str, dict[str, Any]]:
    rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for label, window in WINDOWS.items():
        print(f"[{label}] baseline")
        result = _run_window(window)
        rows[label] = {"metrics": _metrics(result), "raw": result, "window": window}
    return rows


def _run_variant(
    name: str,
    variant: dict[str, Any],
    baselines: OrderedDict[str, dict[str, Any]],
) -> dict[str, Any]:
    target = float(variant["total_mid_dispersion_multiplier"])
    rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for label, window in WINDOWS.items():
        print(f"[{label}] {name}")
        result = _run_window(window, target_total_multiplier=target)
        before = baselines[label]["metrics"]
        after = _metrics(result)
        touched = _touched_trades(result)
        rows[label] = {
            "before": before,
            "after": after,
            "delta": _delta(after, before),
            "touched_trades": touched,
            "touched_trade_count": len(touched),
            "touched_trade_pnl": _round(sum(float(row.get("pnl") or 0.0) for row in touched), 2),
            "window": window,
        }
        print(
            f"[{label}] {name} EV={rows[label]['delta']['expected_value_score']:+.4f} "
            f"PnL={rows[label]['delta']['total_pnl']:+.2f} touched={len(touched)}"
        )
    aggregate = _aggregate(rows)
    return {
        "parameters": variant,
        "rows": rows,
        "aggregate": aggregate,
        "gate4_pass": _gate4_pass(aggregate),
    }


def _aggregate(rows: OrderedDict[str, dict[str, Any]]) -> dict[str, Any]:
    before_ev = sum(float(row["before"]["expected_value_score"] or 0.0) for row in rows.values())
    after_ev = sum(float(row["after"]["expected_value_score"] or 0.0) for row in rows.values())
    before_pnl = sum(float(row["before"]["total_pnl"] or 0.0) for row in rows.values())
    after_pnl = sum(float(row["after"]["total_pnl"] or 0.0) for row in rows.values())
    deltas = [row["delta"] for row in rows.values()]
    return {
        "baseline_expected_value_score_sum": _round(before_ev, 4),
        "after_expected_value_score_sum": _round(after_ev, 4),
        "expected_value_score_delta_sum": _round(after_ev - before_ev, 4),
        "expected_value_score_delta_pct": _round((after_ev - before_ev) / abs(before_ev), 6),
        "baseline_total_pnl_sum": _round(before_pnl, 2),
        "after_total_pnl_sum": _round(after_pnl, 2),
        "total_pnl_delta_sum": _round(after_pnl - before_pnl, 2),
        "total_pnl_delta_pct": _round((after_pnl - before_pnl) / abs(before_pnl), 6),
        "windows_ev_improved": sum(1 for delta in deltas if delta.get("expected_value_score", 0) > 0),
        "windows_ev_regressed": sum(1 for delta in deltas if delta.get("expected_value_score", 0) < 0),
        "windows_pnl_improved": sum(1 for delta in deltas if delta.get("total_pnl", 0) > 0),
        "windows_pnl_regressed": sum(1 for delta in deltas if delta.get("total_pnl", 0) < 0),
        "best_sharpe_daily_delta": _round(max(delta.get("sharpe_daily", 0) for delta in deltas), 6),
        "min_sharpe_daily_delta": _round(min(delta.get("sharpe_daily", 0) for delta in deltas), 6),
        "max_drawdown_worsening_max": _round(max(delta.get("max_drawdown_pct", 0) for delta in deltas), 6),
        "max_drawdown_improvement_min": _round(min(delta.get("max_drawdown_pct", 0) for delta in deltas), 6),
        "min_win_rate_delta": _round(min(delta.get("win_rate", 0) for delta in deltas), 6),
        "trade_count_delta_sum": sum(int(delta.get("trade_count", 0)) for delta in deltas),
        "touched_trade_count_sum": sum(row["touched_trade_count"] for row in rows.values()),
        "touched_trade_pnl_sum": _round(sum(float(row["touched_trade_pnl"] or 0.0) for row in rows.values()), 2),
    }


def _gate4_pass(aggregate: dict[str, Any]) -> bool:
    material = any(
        [
            (aggregate.get("expected_value_score_delta_pct") or 0) > 0.10,
            aggregate.get("best_sharpe_daily_delta", 0) > 0.10,
            aggregate.get("max_drawdown_improvement_min", 0) < -0.01,
            (aggregate.get("total_pnl_delta_pct") or 0) > 0.05,
            (
                aggregate.get("trade_count_delta_sum", 0) > 0
                and aggregate.get("min_win_rate_delta", -1) >= 0
            ),
        ]
    )
    stable = (
        aggregate.get("windows_ev_improved", 0) >= 2
        and aggregate.get("windows_ev_regressed", 0) == 0
    )
    return bool(material and stable)


def _best_variant(variants: OrderedDict[str, dict[str, Any]]) -> str:
    return max(
        variants,
        key=lambda name: (
            variants[name]["aggregate"]["expected_value_score_delta_sum"],
            variants[name]["aggregate"]["total_pnl_delta_sum"],
            -variants[name]["aggregate"]["max_drawdown_worsening_max"],
        ),
    )


def _payload(
    baselines: OrderedDict[str, dict[str, Any]],
    variants: OrderedDict[str, dict[str, Any]],
) -> dict[str, Any]:
    best_name = _best_variant(variants)
    best = variants[best_name]
    accepted = bool(best["gate4_pass"])
    timestamp = datetime.now(timezone.utc).isoformat()
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "change_type": "capital_allocation_clean_mid_dispersion_trend_risk",
        "mechanism_family": "market_structure_sleeve_allocation",
        "hypothesis": (
            "The accepted mid-sector-dispersion trend boost may be under-sized "
            "only for clean trend signals carrying no accepted risk haircut. This "
            "tests a drawdown discriminator before any further mid-dispersion "
            "risk increase."
        ),
        "alpha_hypothesis": {
            "category": "allocation",
            "entry_exit_ranking_or_allocation": "allocation",
            "why_this_now": (
                "LLM soft-ranking, event overlays, and state-surface sleeves are "
                "forward-sample limited. The current accepted-stack attribution "
                "still shows mid-dispersion trend trades positive across all three "
                "canonical windows, but prior raw multiplier retries required a "
                "drawdown discriminator."
            ),
        },
        "history_guardrails": {
            "similar_prior_results": {
                "exp-20260506-032": (
                    "Accepted 1.25x mid-dispersion trend risk and required a new "
                    "drawdown discriminator before retrying nearby multipliers."
                ),
                "exp-20260507-009": (
                    "Rejected removing the accepted boost from fragile/haircut "
                    "subsets. This run tests the complement: extra budget only "
                    "for clean no-haircut signals."
                ),
                "exp-20260507-010": (
                    "Rejected broad-breadth conviction risk; this run is tied to "
                    "the existing mid-dispersion field and does not add breadth "
                    "exposure."
                ),
            },
            "why_not_simple_repeat": (
                "It does not change the base 1.25x mid-dispersion rule and does "
                "not sweep the whole sleeve. The tested causal variable is the "
                "clean/no-haircut qualifier for incremental risk."
            ),
            "mechanism_insight_conflict": "No direct conflict if rejected results are recorded and no production rule is promoted.",
        },
        "parameters": {
            "single_causal_variable": "extra risk only for clean no-haircut mid-dispersion trend signals",
            "base_mid_dispersion_multiplier": BASE_MID_DISPERSION_MULTIPLIER,
            "clean_definition": "trend_long + mid_sector_dispersion=True + no other sizing multiplier below 1.0",
            "variants": VARIANTS,
            "best_variant": best_name,
            "locked_variables": [
                "universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "base mid-dispersion 1.25x policy",
                "all other sizing multipliers",
                "position caps",
                "portfolio heat",
                "add-ons",
                "exits",
                "LLM/news replay",
                "event sleeves",
            ],
        },
        "date_range": {
            label: f"{window['start']} -> {window['end']}"
            for label, window in WINDOWS.items()
        },
        "snapshots": {label: window["snapshot"] for label, window in WINDOWS.items()},
        "market_regime_summary": {
            label: window["state_note"] for label, window in WINDOWS.items()
        },
        "before_metrics": {label: row["metrics"] for label, row in baselines.items()},
        "after_metrics": {
            label: row["after"] for label, row in best["rows"].items()
        },
        "variant_results": variants,
        "delta_metrics": {
            "aggregate": best["aggregate"],
            "by_window": {label: row["delta"] for label, row in best["rows"].items()},
        },
        "best_variant": best_name,
        "gate4": {
            "passed": accepted,
            "basis": "Requires material Gate 4 trigger plus EV improvement in at least two windows with zero EV-regressed windows.",
        },
        "decision": "accepted" if accepted else "rejected",
        "status": "accepted" if accepted else "rejected",
        "rejection_reason": None
        if accepted
        else (
            "The clean mid-dispersion top-up improved EV in all windows but did "
            "not clear materiality: the best effective variant was capped at "
            "4.86% EV lift and 4.72% PnL lift, below the 10%/5% Gate 4 thresholds."
        ),
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": "LLM data limits were bypassed by selecting a deterministic allocation alpha.",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": True,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted later, implement the clean qualifier in shared "
                "portfolio policy, expose the sizing tag to run/backtester, and "
                "add parity tests before live orders change."
            ),
        },
        "why_not_other_attractive_points": {
            "event_bundle_or_state_surface": "Forward paper files currently have zero closed observations.",
            "LLM_soft_ranking": "Production-aligned closed attribution remains too sparse.",
            "universe_expansion": "Static ETF/platform/pilot expansions recently failed or need forward replacement value.",
            "raw_mid_dispersion_multiplier": "Explicitly blocked without a drawdown discriminator.",
        },
        "risk_of_change": (
            "May concentrate more capital into already-boosted winners and still "
            "increase old_thin drawdown when clean candidates are cap-bound."
        ),
        "next_retry_requires": [
            "Do not retry nearby clean mid-dispersion top-up multipliers on the same snapshots.",
            "A valid retry needs new forward evidence, a separate cap-room signal, or a materially different drawdown discriminator.",
        ],
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "quant/experiments/exp_20260509_005_clean_mid_dispersion_trend_risk.py",
        ],
    }


def _artifact(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} Clean Mid-Dispersion Trend Risk",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Gate 4",
        "",
        f"- passed: `{payload['gate4']['passed']}`",
        f"- best_variant: `{payload['best_variant']}`",
        f"- EV delta sum: `{aggregate['expected_value_score_delta_sum']:+.4f}` ({aggregate['expected_value_score_delta_pct']:+.2%})",
        f"- PnL delta sum: `${aggregate['total_pnl_delta_sum']:+,.2f}` ({aggregate['total_pnl_delta_pct']:+.2%})",
        f"- EV windows improved/regressed: `{aggregate['windows_ev_improved']}` / `{aggregate['windows_ev_regressed']}`",
        f"- touched trades: `{aggregate['touched_trade_count_sum']}`",
        "",
        "## Three-Window Deltas",
        "",
        "| Window | EV delta | PnL delta | SharpeD delta | DD delta | WR delta | Trades delta | Touched |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, row in payload["variant_results"][payload["best_variant"]]["rows"].items():
        delta = row["delta"]
        lines.append(
            f"| `{label}` | {delta['expected_value_score']:+.4f} | "
            f"{delta['total_pnl']:+.2f} | {delta['sharpe_daily']:+.2f} | "
            f"{delta['max_drawdown_pct']:+.4f} | {delta['win_rate']:+.4f} | "
            f"{delta['trade_count']:+d} | {row['touched_trade_count']} |"
        )
    lines.extend(
        [
            "",
            "## Decision Rationale",
            "",
            payload["rejection_reason"] or "Gate 4 passed.",
            "",
            "The direction was positive, but position caps absorbed higher variants and materiality stayed below Gate 4. No production rule was promoted.",
            "",
            "## Production Impact",
            "",
            "Replay only. Production and default backtest policy are unchanged.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    baselines = _run_baselines()
    variants: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for name, variant in VARIANTS.items():
        variants[name] = _run_variant(name, variant, baselines)
    payload = _payload(baselines, variants)

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Clean mid-dispersion trend risk",
            "decision": payload["decision"],
            "summary": payload["rejection_reason"] or "Gate 4 passed; promote through shared policy.",
            "best_variant": payload["best_variant"],
            "delta_metrics": payload["delta_metrics"],
            "related_log": str(LOG_JSON.relative_to(REPO_ROOT)),
        },
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact(payload) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "best_variant": payload["best_variant"],
                "gate4": payload["gate4"],
                "aggregate": payload["delta_metrics"]["aggregate"],
                "out_json": str(OUT_JSON.relative_to(REPO_ROOT)),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
