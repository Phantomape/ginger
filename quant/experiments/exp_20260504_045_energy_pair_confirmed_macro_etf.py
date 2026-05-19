"""exp-20260504-045 energy pair-confirmed macro ETF candidate pool.

Alpha-search experiment. exp-20260504-028 showed that ticker-list-only macro
ETF expansion adds late_strong winners but damages the weaker windows. This
run tests the next valid retry condition from the playbook: an explicit
macro-regime discriminator. The discriminator is intentionally narrow and
production-explainable: XLE/USO candidates are only considered when both the
energy equity ETF and crude ETF are above their 200-day averages with positive
10d and 20d momentum.

No production or default backtest strategy logic is changed by this script.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import signal_engine  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260504-045"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "energy_pair_confirmed_macro_etf.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REPORT_MD = (
    REPO_ROOT
    / "docs"
    / "non_ohlcv_data_audit"
    / "energy_pair_confirmed_macro_etf_20260504.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
PLAYBOOK = REPO_ROOT / "docs" / "alpha-optimization-playbook.md"

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

ENERGY_ETFS = {"XLE", "USO"}
VARIANTS = OrderedDict(
    [
        (
            "xle_only_pair_confirmed",
            {
                "extra_tickers": ["XLE", "USO"],
                "tradable_extra_tickers": {"XLE"},
                "description": "Only XLE can trade, but XLE and USO must both confirm.",
            },
        ),
        (
            "xle_uso_pair_confirmed",
            {
                "extra_tickers": ["XLE", "USO"],
                "tradable_extra_tickers": {"XLE", "USO"},
                "description": "Both XLE and USO can trade only when the pair confirms.",
            },
        ),
    ]
)


def _round(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    if not math.isfinite(float(value)):
        return None
    return round(float(value), digits)


def _safe_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _safe_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe_payload(item) for item in value]
    if isinstance(value, set):
        return sorted(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe_payload(payload), indent=2, ensure_ascii=False, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    total_pnl = float(result.get("total_pnl") or 0.0)
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": round(total_pnl, 2),
        "total_return_pct": round(total_pnl / 100_000.0, 4),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "converged": (result.get("convergence") or {}).get("converged"),
    }


def _energy_pair_confirmed(features_dict: dict[str, Any]) -> bool:
    for ticker in sorted(ENERGY_ETFS):
        features = features_dict.get(ticker) or {}
        if not features.get("above_200ma"):
            return False
        if (features.get("momentum_10d_pct") or 0) <= 0:
            return False
        if (features.get("momentum_20d_pct") or 0) <= 0:
            return False
    return True


def _patch_generate_signals(
    *,
    tradable_extra_tickers: set[str],
    stats: dict[str, Any],
) -> Callable[..., list[dict[str, Any]]]:
    original = signal_engine.generate_signals

    def patched_generate_signals(
        features_dict: dict[str, Any],
        market_context: dict[str, Any] | None = None,
        enabled_strategies: Any = None,
        breakout_max_pullback_from_52w_high: float | None = None,
    ) -> list[dict[str, Any]]:
        signals = original(
            features_dict,
            market_context=market_context,
            enabled_strategies=enabled_strategies,
            breakout_max_pullback_from_52w_high=breakout_max_pullback_from_52w_high,
        )
        confirmed = _energy_pair_confirmed(features_dict)
        kept: list[dict[str, Any]] = []
        for signal in signals:
            ticker = str(signal.get("ticker") or "").upper()
            if ticker not in ENERGY_ETFS:
                kept.append(signal)
                continue
            stats["extra_signal_count"] += 1
            stats["extra_signal_tickers"][ticker] += 1
            if ticker not in tradable_extra_tickers:
                stats["filtered_not_tradable_count"] += 1
                continue
            if not confirmed:
                stats["filtered_not_pair_confirmed_count"] += 1
                continue
            stats["pair_confirmed_signal_count"] += 1
            kept.append(signal)
        return kept

    signal_engine.generate_signals = patched_generate_signals
    return original


def _run_window(
    *,
    universe: list[str],
    window: dict[str, str],
    tradable_extra_tickers: set[str] | None = None,
) -> dict[str, Any]:
    stats: dict[str, Any] = {
        "extra_signal_count": 0,
        "pair_confirmed_signal_count": 0,
        "filtered_not_tradable_count": 0,
        "filtered_not_pair_confirmed_count": 0,
        "extra_signal_tickers": Counter(),
    }
    original = None
    if tradable_extra_tickers is not None:
        original = _patch_generate_signals(
            tradable_extra_tickers=tradable_extra_tickers,
            stats=stats,
        )
    try:
        result = BacktestEngine(
            universe,
            start=window["start"],
            end=window["end"],
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=window["snapshot"],
        ).run()
    finally:
        if original is not None:
            signal_engine.generate_signals = original

    extra_trades = [
        {
            "ticker": trade.get("ticker"),
            "strategy": trade.get("strategy"),
            "entry_date": trade.get("entry_date"),
            "exit_date": trade.get("exit_date"),
            "pnl": trade.get("pnl"),
            "exit_reason": trade.get("exit_reason"),
        }
        for trade in result.get("trades", [])
        if str(trade.get("ticker") or "").upper() in ENERGY_ETFS
    ]
    stats["extra_signal_tickers"] = dict(stats["extra_signal_tickers"])
    return {
        "metrics": _metrics(result),
        "extra_trades": extra_trades,
        "extra_trade_count": len(extra_trades),
        "extra_trade_pnl": _round(sum(float(trade.get("pnl") or 0.0) for trade in extra_trades), 2),
        "filter_stats": stats,
    }


def _delta(base: dict[str, Any], variant: dict[str, Any]) -> dict[str, Any]:
    return {
        "expected_value_score": _round(
            (variant.get("expected_value_score") or 0.0)
            - (base.get("expected_value_score") or 0.0),
            4,
        ),
        "sharpe_daily": _round(
            (variant.get("sharpe_daily") or 0.0) - (base.get("sharpe_daily") or 0.0),
            4,
        ),
        "total_pnl": _round(
            (variant.get("total_pnl") or 0.0) - (base.get("total_pnl") or 0.0),
            2,
        ),
        "max_drawdown_pct": _round(
            (variant.get("max_drawdown_pct") or 0.0)
            - (base.get("max_drawdown_pct") or 0.0),
            4,
        ),
        "win_rate": _round((variant.get("win_rate") or 0.0) - (base.get("win_rate") or 0.0), 4),
        "trade_count": (variant.get("trade_count") or 0) - (base.get("trade_count") or 0),
    }


def _gate4(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    ev_before = before.get("expected_value_score") or 0.0
    ev_after = after.get("expected_value_score") or 0.0
    pnl_before = before.get("total_pnl") or 0.0
    pnl_after = after.get("total_pnl") or 0.0
    sharpe_before = before.get("sharpe_daily") or 0.0
    sharpe_after = after.get("sharpe_daily") or 0.0
    dd_before = before.get("max_drawdown_pct") or 0.0
    dd_after = after.get("max_drawdown_pct") or 0.0
    trade_before = before.get("trade_count") or 0
    trade_after = after.get("trade_count") or 0
    win_before = before.get("win_rate") or 0.0
    win_after = after.get("win_rate") or 0.0
    return {
        "passes_material_ev": ev_before > 0 and (ev_after - ev_before) / ev_before > 0.10,
        "passes_sharpe": sharpe_after - sharpe_before > 0.10,
        "passes_drawdown": dd_before - dd_after > 0.01,
        "passes_pnl": pnl_before > 0 and (pnl_after - pnl_before) / pnl_before > 0.05,
        "passes_trade_count": trade_after > trade_before and win_after >= win_before,
    }


def _aggregate_metrics(windows: dict[str, Any]) -> dict[str, Any]:
    metrics = {label: data["metrics"] for label, data in windows.items()}
    return {
        "expected_value_score_sum": _round(
            sum(float(row.get("expected_value_score") or 0.0) for row in metrics.values()),
            4,
        ),
        "total_pnl_sum": _round(
            sum(float(row.get("total_pnl") or 0.0) for row in metrics.values()),
            2,
        ),
        "trade_count_sum": sum(int(row.get("trade_count") or 0) for row in metrics.values()),
    }


def build_payload() -> dict[str, Any]:
    base_universe = sorted(get_universe())
    expanded_universe = sorted(set(base_universe) | ENERGY_ETFS)

    baseline_windows = {
        label: _run_window(universe=base_universe, window=cfg)
        for label, cfg in WINDOWS.items()
    }

    variants: dict[str, Any] = {}
    for variant_name, variant_cfg in VARIANTS.items():
        variant_windows = {
            label: _run_window(
                universe=expanded_universe,
                window=window_cfg,
                tradable_extra_tickers=set(variant_cfg["tradable_extra_tickers"]),
            )
            for label, window_cfg in WINDOWS.items()
        }
        by_window_delta = {
            label: _delta(baseline_windows[label]["metrics"], variant_windows[label]["metrics"])
            for label in WINDOWS
        }
        gate_by_window = {
            label: _gate4(baseline_windows[label]["metrics"], variant_windows[label]["metrics"])
            for label in WINDOWS
        }
        material_windows = sum(1 for row in gate_by_window.values() if any(row.values()))
        ev_improved_windows = sum(
            1 for row in by_window_delta.values() if (row.get("expected_value_score") or 0) > 0
        )
        ev_regressed_windows = sum(
            1 for row in by_window_delta.values() if (row.get("expected_value_score") or 0) < 0
        )
        agg_before = _aggregate_metrics(baseline_windows)
        agg_after = _aggregate_metrics(variant_windows)
        variants[variant_name] = {
            "description": variant_cfg["description"],
            "extra_tickers": variant_cfg["extra_tickers"],
            "tradable_extra_tickers": sorted(variant_cfg["tradable_extra_tickers"]),
            "windows": variant_windows,
            "by_window_delta": by_window_delta,
            "aggregate_before": agg_before,
            "aggregate_after": agg_after,
            "aggregate_delta": {
                "expected_value_score_sum": _round(
                    (agg_after["expected_value_score_sum"] or 0)
                    - (agg_before["expected_value_score_sum"] or 0),
                    4,
                ),
                "expected_value_score_delta_pct": _round(
                    (
                        (agg_after["expected_value_score_sum"] or 0)
                        - (agg_before["expected_value_score_sum"] or 0)
                    )
                    / agg_before["expected_value_score_sum"]
                    if agg_before["expected_value_score_sum"]
                    else None,
                    6,
                ),
                "total_pnl_sum": _round(
                    (agg_after["total_pnl_sum"] or 0) - (agg_before["total_pnl_sum"] or 0),
                    2,
                ),
                "total_pnl_delta_pct": _round(
                    ((agg_after["total_pnl_sum"] or 0) - (agg_before["total_pnl_sum"] or 0))
                    / agg_before["total_pnl_sum"]
                    if agg_before["total_pnl_sum"]
                    else None,
                    6,
                ),
                "ev_improved_windows": ev_improved_windows,
                "ev_regressed_windows": ev_regressed_windows,
            },
            "gate4": {
                "by_window": gate_by_window,
                "material_windows": material_windows,
                "passes_majority": material_windows >= 2 and ev_regressed_windows == 0,
                "rule": (
                    "EV first; material if EV >10%, Sharpe >0.1, DD -1pp, PnL >5%, "
                    "or trade count rises with win rate not down. Promotion also "
                    "requires no EV-regressed window."
                ),
            },
        }

    best_name, best_payload = max(
        variants.items(),
        key=lambda item: (
            item[1]["aggregate_delta"]["expected_value_score_sum"],
            item[1]["aggregate_delta"]["total_pnl_sum"],
        ),
    )
    accepted = bool(best_payload["gate4"]["passes_majority"])
    decision = "accepted_requires_shared_policy" if accepted else "rejected"
    decision_rationale = (
        "Accepted as an experiment only: the pair-confirmed energy ETF discriminator cleared "
        "the majority-window materiality gate, so promotion would require a shared "
        "production/backtest candidate-eligibility policy and parity tests before use."
        if accepted
        else "Rejected. Pair-confirming XLE/USO reduced ticker-list-only noise but did not clear "
        "the three-window materiality gate without EV regression."
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "mechanism_family": "macro_etf_candidate_pool_regime_allocator",
        "change_type": "alpha_search_candidate_pool_discriminator",
        "hypothesis": (
            "Energy macro ETF candidates are only useful when crude and energy equities confirm "
            "the same trend; pair confirmation may preserve late_strong XLE/USO winners while "
            "avoiding mid_weak/old_thin ticker-list noise."
        ),
        "alpha_hypothesis": {
            "category": "candidate_pool_extension_with_macro_regime_discriminator",
            "entry_exit_ranking_or_allocation": "entry candidate eligibility",
            "why_this_now": (
                "LLM soft-ranking is sample-limited, broad ETF expansion was rejected, and the "
                "playbook explicitly requires a macro-regime discriminator before retrying ETF "
                "candidate-pool expansion."
            ),
        },
        "historical_experiment_check": {
            "similar_experiments": {
                "exp-20260428-035": "broad ETF expansion rejected; simple ETF additions were unstable",
                "exp-20260430-005": "defensive ETF expansion rejected",
                "exp-20260504-028": "macro_all and xle_only ticker-list expansion rejected; valid retry requires a macro-regime discriminator",
            },
            "why_not_simple_repeat": (
                "This does not add another ETF list. It locks the prior Energy clue and tests "
                "a single production-explainable pair-confirmation discriminator."
            ),
            "mechanism_insight_guardrails": [
                "No broad macro ETF basket promotion.",
                "No XLE-only ticker-list promotion.",
                "No date/window label is used as a decision input.",
                "No LLM soft-ranking due sparse outcome joins.",
            ],
        },
        "single_causal_variable": "XLE/USO pair-confirmed macro ETF candidate eligibility",
        "parameters": {
            "extra_feature_tickers": sorted(ENERGY_ETFS),
            "pair_confirmation": "XLE and USO both above 200MA with positive 10d and 20d momentum",
            "variants": {
                key: {
                    "tradable_extra_tickers": sorted(value["tradable_extra_tickers"]),
                    "description": value["description"],
                }
                for key, value in VARIANTS.items()
            },
            "locked_variables": [
                "core production universe",
                "signal thresholds",
                "risk multipliers",
                "entry execution cancels",
                "candidate ranking",
                "position sizing",
                "add-ons",
                "exits",
                "LLM/news replay",
            ],
        },
        "date_range": {
            label: f"{cfg['start']} -> {cfg['end']}"
            for label, cfg in WINDOWS.items()
        },
        "market_regime_summary": {
            label: cfg["state_note"]
            for label, cfg in WINDOWS.items()
        },
        "before_metrics": {
            label: data["metrics"]
            for label, data in baseline_windows.items()
        },
        "after_metrics": {
            label: data["metrics"]
            for label, data in best_payload["windows"].items()
        },
        "expected_value_score_delta": {
            label: best_payload["by_window_delta"][label]["expected_value_score"]
            for label in WINDOWS
        },
        "variants": variants,
        "best_variant": best_name,
        "gate4": best_payload["gate4"],
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "production_orders_changed": False,
            "production_signal_path_changed": False,
            "production_impact": "experiment_only_no_live_or_default_backtest_strategy_change",
            "promotion_blocker_if_accepted": (
                "Accepted variant would require shared production/backtest eligibility policy "
                "and parity tests before live/default-backtest use."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": "Production-aligned LLM soft-ranking outcome joins remain too sparse.",
        },
        "decision_rationale": decision_rationale,
        "rejection_reason": None if accepted else decision_rationale,
        "why_not_other_attractive_points": (
            "SEC governance needs forward paper outcomes after exp-20260504-044; Form 4 already "
            "has a default-off queue; leadership-change was sleeve-rejected; Companyfacts simple "
            "quality was non-monotonic; broad macro ETF list expansion was already rejected."
        ),
        "risk_of_change": (
            "If promoted later, this could still consume scarce slots with low-volatility ETF "
            "signals and crowd out higher-conviction single-name A/B winners."
        ),
        "next_action": (
            "Promote only after shared policy/parity implementation."
            if accepted
            else "Do not retry nearby XLE/USO pair-confirmation variants on the same snapshots without new macro evidence."
        ),
        "related_files": [
            "quant/experiments/exp_20260504_045_energy_pair_confirmed_macro_etf.py",
            "data/experiments/exp-20260504-045/energy_pair_confirmed_macro_etf.json",
            "experiments/logs/exp-20260504-045.json",
            "experiments/tickets/exp-20260504-045.json",
            "docs/non_ohlcv_data_audit/energy_pair_confirmed_macro_etf_20260504.md",
            "docs/experiment_log.jsonl",
            "docs/alpha-optimization-playbook.md",
        ],
    }
    return _safe_payload(payload)


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.2f}%"


def _report(payload: dict[str, Any]) -> str:
    best = payload["variants"][payload["best_variant"]]
    lines = [
        "# exp-20260504-045 Energy pair-confirmed macro ETF",
        "",
        f"- decision: `{payload['decision']}`",
        f"- best variant: `{payload['best_variant']}`",
        f"- aggregate EV delta: `{best['aggregate_delta']['expected_value_score_sum']}`",
        f"- aggregate PnL delta: `${best['aggregate_delta']['total_pnl_sum']}`",
        f"- EV improved windows: `{best['aggregate_delta']['ev_improved_windows']}`",
        f"- EV regressed windows: `{best['aggregate_delta']['ev_regressed_windows']}`",
        f"- production impact: `{payload['production_impact']['production_impact']}`",
        "",
        "## Window Summary",
        "",
        "| Window | Before EV | After EV | EV delta | Before PnL | After PnL | PnL delta | Extra trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = best["by_window_delta"][label]
        lines.append(
            f"| {label} | {before['expected_value_score']} | {after['expected_value_score']} | "
            f"{delta['expected_value_score']} | {before['total_pnl']} | {after['total_pnl']} | "
            f"{delta['total_pnl']} | {best['windows'][label]['extra_trade_count']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            payload["decision_rationale"],
            "",
            "This is an experiment-only replay. It does not alter production entries, default "
            "backtests, ranking, sizing, universe membership, or orders.",
        ]
    )
    return "\n".join(lines) + "\n"


def _append_experiment_log(payload: dict[str, Any]) -> None:
    compact = dict(payload)
    compact["variants_summary"] = {
        key: {
            "aggregate_delta": value["aggregate_delta"],
            "gate4": value["gate4"],
            "extra_trades_by_window": {
                label: row["extra_trades"]
                for label, row in value["windows"].items()
            },
        }
        for key, value in payload["variants"].items()
    }
    compact.pop("variants", None)
    existing = (
        EXPERIMENT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        if EXPERIMENT_LOG.exists()
        else []
    )
    kept = [
        line
        for line in existing
        if f'"experiment_id":"{EXPERIMENT_ID}"' not in line
        and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
    ]
    kept.append(json.dumps(_safe_payload(compact), ensure_ascii=False, separators=(",", ":")))
    EXPERIMENT_LOG.write_text("\n".join(kept) + "\n", encoding="utf-8")


def _append_playbook(payload: dict[str, Any]) -> None:
    if not PLAYBOOK.exists():
        return
    marker = f"### 2026-05-04 mechanism update: Energy pair-confirmed macro ETF"
    text = PLAYBOOK.read_text(encoding="utf-8", errors="replace")
    if marker in text:
        return
    best = payload["variants"][payload["best_variant"]]
    addition = f"""

{marker}

Status: {payload['decision']}.

Core conclusion: `exp-20260504-045` tested the valid retry condition left by
`exp-20260504-028`: macro ETF expansion must have a regime discriminator.
Requiring XLE and USO to both be above their 200-day averages with positive
10d/20d momentum did not clear the three-window materiality gate.

Evidence: best variant `{payload['best_variant']}` moved aggregate EV by
`{best['aggregate_delta']['expected_value_score_sum']}` and aggregate PnL by
`${best['aggregate_delta']['total_pnl_sum']}`. EV improved in
`{best['aggregate_delta']['ev_improved_windows']}` windows and regressed in
`{best['aggregate_delta']['ev_regressed_windows']}` windows.

Do not repeat: nearby XLE/USO pair-confirmation thresholds, XLE-only list
promotion, or broad macro ETF baskets on the same frozen snapshots.

Next valid retry requires: new macro/event evidence that explains when energy
ETFs deserve scarce slots, not another ticker-list or local momentum gate.
"""
    PLAYBOOK.write_text(text.rstrip() + addition + "\n", encoding="utf-8")


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "title": "Energy pair-confirmed macro ETF",
        "summary": payload["decision_rationale"],
        "best_variant": payload["best_variant"],
        "aggregate_delta": payload["variants"][payload["best_variant"]]["aggregate_delta"],
        "next_action": payload["next_action"],
    }
    _write_json(TICKET_JSON, ticket)
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(_report(payload), encoding="utf-8")
    _append_experiment_log(payload)
    _append_playbook(payload)


def main() -> int:
    payload = build_payload()
    persist(payload)
    best = payload["variants"][payload["best_variant"]]
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "best_variant": payload["best_variant"],
                "aggregate_delta": best["aggregate_delta"],
                "gate4": best["gate4"],
                "expected_value_score_delta": payload["expected_value_score_delta"],
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
