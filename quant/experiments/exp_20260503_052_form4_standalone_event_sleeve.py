"""Shadow replay for standalone Form 4 purchase event alpha.

This experiment does not change production entries, ranking, sizing, exits, or
universe membership. It tests whether already backfilled PIT-safe Form 4 open
market purchase events look strong enough to justify a future production-ready
event sleeve.
"""

from __future__ import annotations

import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
DOCS_DIR = REPO_ROOT / "docs"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from quant.constants import ROUND_TRIP_COST_PCT

EXP_ID = "exp-20260503-052"
OUT_DIR = DATA_DIR / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / "form4_standalone_event_sleeve.json"
LOG_JSON = DOCS_DIR / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = DOCS_DIR / "experiments" / "tickets" / f"{EXP_ID}.json"
EXPERIMENT_LOG = DOCS_DIR / "experiment_log.jsonl"
AUDIT_MD = DOCS_DIR / "non_ohlcv_data_audit" / "form4_standalone_event_sleeve_20260503.md"

INPUT_EVENTS = DATA_DIR / "non_ohlcv" / "form4_purchase_shadow_outcomes_20241002_20260421.json"
PRIMARY_HORIZON = "10"
EVENT_NOTIONAL = 10_000.0
PORTFOLIO_BASE = 100_000.0

WINDOW_ORDER = ("late_strong", "mid_weak", "old_thin")
WINDOW_RANGES = {
    "late_strong": "2025-10-23 -> 2026-04-21",
    "mid_weak": "2025-04-23 -> 2025-10-22",
    "old_thin": "2024-10-02 -> 2025-04-22",
}
BASELINE_METRICS = {
    "late_strong": {
        "expected_value_score": 3.4191,
        "sharpe_daily": 4.35,
        "total_pnl": 78600.33,
        "total_return_pct": 0.7860,
        "max_drawdown_pct": 0.0541,
        "win_rate": 0.7895,
        "trade_count": 19,
        "survival_rate": 0.8039,
    },
    "mid_weak": {
        "expected_value_score": 1.4415,
        "sharpe_daily": 2.62,
        "total_pnl": 55015.08,
        "total_return_pct": 0.5502,
        "max_drawdown_pct": 0.0879,
        "win_rate": 0.5238,
        "trade_count": 21,
        "survival_rate": 0.7925,
    },
    "old_thin": {
        "expected_value_score": 0.3179,
        "sharpe_daily": 1.29,
        "total_pnl": 24642.07,
        "total_return_pct": 0.2464,
        "max_drawdown_pct": 0.0805,
        "win_rate": 0.4091,
        "trade_count": 22,
        "survival_rate": 0.9167,
    },
}

VARIANTS = {
    "meaningful_ge_0": 0.0,
    "meaningful_ge_100k": 100_000.0,
    "meaningful_ge_250k": 250_000.0,
    "meaningful_ge_500k": 500_000.0,
    "meaningful_ge_1m": 1_000_000.0,
}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(value).replace("\\", "/")


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 6) if values else None


def _median(values: list[float]) -> float | None:
    return round(statistics.median(values), 6) if values else None


def _stdev(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    return statistics.stdev(values)


def _event_sharpe(values_pct: list[float]) -> float | None:
    if len(values_pct) < 2:
        return None
    values = [value / 100.0 for value in values_pct]
    stdev = _stdev(values)
    if not stdev:
        return None
    return round((sum(values) / len(values)) / stdev * (len(values) ** 0.5), 4)


def _outcome_value(event: dict[str, Any], field: str, horizon: str = PRIMARY_HORIZON) -> float | None:
    outcome = (event.get("outcomes") or {}).get(horizon) or {}
    value = outcome.get(field)
    return float(value) if value is not None else None


def _event_matches(event: dict[str, Any], min_purchase_value: float) -> bool:
    if not event.get("meaningful_purchase_v1"):
        return False
    return float(event.get("total_purchase_value") or 0.0) >= min_purchase_value


def _summarize_events(events: list[dict[str, Any]], *, horizon: str = PRIMARY_HORIZON) -> dict[str, Any]:
    valid = [event for event in events if _outcome_value(event, "return_pct", horizon) is not None]
    gross_returns = [_outcome_value(event, "return_pct", horizon) for event in valid]
    excess_returns = [_outcome_value(event, "excess_vs_spy_pct", horizon) for event in valid]
    gross_returns = [value for value in gross_returns if value is not None]
    excess_returns = [value for value in excess_returns if value is not None]
    net_returns = [value - (ROUND_TRIP_COST_PCT * 100.0) for value in gross_returns]
    total_pnl = round(sum(EVENT_NOTIONAL * value / 100.0 for value in net_returns), 2)
    return_on_base = round(total_pnl / PORTFOLIO_BASE, 6)
    return {
        "event_count": len(events),
        "valid_event_count": len(valid),
        "ticker_count": len({str(event.get("ticker") or "").upper() for event in events}),
        "tickers": sorted({str(event.get("ticker") or "").upper() for event in events if event.get("ticker")}),
        "avg_gross_return_pct": _mean(gross_returns),
        "median_gross_return_pct": _median(gross_returns),
        "avg_net_return_pct": _mean(net_returns),
        "median_net_return_pct": _median(net_returns),
        "win_rate_net": round(sum(1 for value in net_returns if value > 0.0) / len(net_returns), 4) if net_returns else None,
        "avg_excess_vs_spy_pct": _mean(excess_returns),
        "median_excess_vs_spy_pct": _median(excess_returns),
        "excess_win_rate": round(sum(1 for value in excess_returns if value > 0.0) / len(excess_returns), 4) if excess_returns else None,
        "event_level_sharpe_proxy": _event_sharpe(net_returns),
        "pnl_per_10k_event_notional": total_pnl,
        "return_on_100k_base": return_on_base,
    }


def _variant_summary(events: list[dict[str, Any]], min_purchase_value: float) -> dict[str, Any]:
    selected = [event for event in events if _event_matches(event, min_purchase_value)]
    by_window = {}
    for window in WINDOW_ORDER:
        by_window[window] = _summarize_events([event for event in selected if event.get("window") == window])
    aggregate = _summarize_events(selected)
    positive_windows = sum(
        1 for row in by_window.values()
        if row["valid_event_count"] > 0 and (row["avg_excess_vs_spy_pct"] or 0.0) > 0.0
    )
    windows_with_valid_events = sum(1 for row in by_window.values() if row["valid_event_count"] > 0)
    aggregate.update({
        "windows_with_valid_events": windows_with_valid_events,
        "positive_excess_windows": positive_windows,
        "all_valid_windows_positive": windows_with_valid_events == len(WINDOW_ORDER) and positive_windows == len(WINDOW_ORDER),
    })
    return {
        "min_total_purchase_value": min_purchase_value,
        "primary_horizon_trading_days": int(PRIMARY_HORIZON),
        "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
        "by_window": by_window,
        "aggregate": aggregate,
        "examples": _examples(selected),
    }


def _examples(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for event in events:
        outcome = (event.get("outcomes") or {}).get(PRIMARY_HORIZON) or {}
        if outcome.get("return_pct") is None:
            continue
        rows.append({
            "window": event.get("window"),
            "ticker": event.get("ticker"),
            "usable_trade_date": event.get("usable_trade_date"),
            "total_purchase_value": event.get("total_purchase_value"),
            "owner_count": event.get("owner_count"),
            "sample_owner_names": event.get("sample_owner_names"),
            "sample_officer_titles": event.get("sample_officer_titles"),
            "return_pct": outcome.get("return_pct"),
            "excess_vs_spy_pct": outcome.get("excess_vs_spy_pct"),
        })
    rows.sort(key=lambda row: (row.get("excess_vs_spy_pct") or 0.0), reverse=True)
    return rows[:20]


def _best_variant(variants: dict[str, dict[str, Any]]) -> str:
    eligible = [
        (name, row)
        for name, row in variants.items()
        if row["aggregate"]["all_valid_windows_positive"]
    ]
    if not eligible:
        return max(
            variants,
            key=lambda name: (
                variants[name]["aggregate"]["positive_excess_windows"],
                variants[name]["aggregate"]["avg_excess_vs_spy_pct"] or -999.0,
                variants[name]["aggregate"]["valid_event_count"],
            ),
        )
    return max(
        (name for name, _ in eligible),
        key=lambda name: (
            variants[name]["aggregate"]["avg_excess_vs_spy_pct"] or -999.0,
            variants[name]["aggregate"]["valid_event_count"],
        ),
    )


def _append_experiment_log(row: dict[str, Any]) -> None:
    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    compact = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
    if EXPERIMENT_LOG.exists():
        lines = EXPERIMENT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        lines = [
            line for line in lines
            if f'"experiment_id":"{EXP_ID}"' not in line and f'"experiment_id": "{EXP_ID}"' not in line
        ]
        lines.append(compact)
        EXPERIMENT_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return
    EXPERIMENT_LOG.write_text(compact + "\n", encoding="utf-8")


def _write_ticket(payload: dict[str, Any]) -> None:
    ticket = {
        "experiment_id": EXP_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": payload["lane"],
        "created_at": payload["timestamp"],
        "completed_at": payload["timestamp"],
        "hypothesis": payload["hypothesis"],
        "allowed_write_scope": [
            "quant/experiments/exp_20260503_052_form4_standalone_event_sleeve.py",
            "quant/test_form4_standalone_event_sleeve.py",
            "data/experiments/exp-20260503-052/form4_standalone_event_sleeve.json",
            "docs/non_ohlcv_data_audit/form4_standalone_event_sleeve_20260503.md",
            "docs/experiments/logs/exp-20260503-052.json",
            "docs/experiments/tickets/exp-20260503-052.json",
            "docs/experiment_log.jsonl",
            "docs/alpha-optimization-playbook.md",
        ],
        "result": {
            "artifact": _repo_rel(OUT_JSON),
            "audit_report": _repo_rel(AUDIT_MD),
            "log": _repo_rel(LOG_JSON),
            "best_variant": payload["best_variant"],
            "best_variant_decision": payload["decision"],
            "production_impact": payload["production_impact"]["production_impact"],
            "next_action": payload["next_action"],
        },
    }
    _write_json(TICKET_JSON, ticket)


def _write_report(payload: dict[str, Any]) -> None:
    lines = [
        "# Form 4 Standalone Event Sleeve Shadow Replay",
        "",
        f"- experiment_id: `{payload['experiment_id']}`",
        f"- timestamp: `{payload['timestamp']}`",
        f"- decision: `{payload['decision']}`",
        f"- production_impact: `{payload['production_impact']['production_impact']}`",
        f"- primary horizon: `{PRIMARY_HORIZON}` trading days",
        "",
        "## Baseline",
        "",
        "| Window | EV | Return | Sharpe daily | Max DD | Win rate | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for window in WINDOW_ORDER:
        row = BASELINE_METRICS[window]
        lines.append(
            f"| {window} | {row['expected_value_score']:.4f} | {row['total_return_pct']:.2%} | "
            f"{row['sharpe_daily']:.2f} | {row['max_drawdown_pct']:.2%} | "
            f"{row['win_rate']:.2%} | {row['trade_count']} |"
        )
    lines.extend([
        "",
        "## Variant Summary",
        "",
        "| Variant | Min buy | Valid events | Avg net return | Avg excess | Positive windows | Decision cue |",
        "|---|---:|---:|---:|---:|---:|---|",
    ])
    for name, row in payload["shadow_variants"].items():
        agg = row["aggregate"]
        cue = "stable-positive" if agg["all_valid_windows_positive"] else "unstable"
        lines.append(
            f"| {name} | ${row['min_total_purchase_value']:,.0f} | {agg['valid_event_count']} | "
            f"{_fmt_pct(agg['avg_net_return_pct'])} | {_fmt_pct(agg['avg_excess_vs_spy_pct'])} | "
            f"{agg['positive_excess_windows']}/{len(WINDOW_ORDER)} | {cue} |"
        )
    best = payload["shadow_variants"][payload["best_variant"]]
    lines.extend([
        "",
        "## Best Shadow Variant",
        "",
        f"- best_variant: `{payload['best_variant']}`",
        f"- min_total_purchase_value: `${best['min_total_purchase_value']:,.0f}`",
        "",
        "| Window | Events | Valid | Avg net return | Avg excess vs SPY | Excess win rate |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for window in WINDOW_ORDER:
        row = best["by_window"][window]
        lines.append(
            f"| {window} | {row['event_count']} | {row['valid_event_count']} | "
            f"{_fmt_pct(row['avg_net_return_pct'])} | {_fmt_pct(row['avg_excess_vs_spy_pct'])} | "
            f"{_fmt_rate(row['excess_win_rate'])} |"
        )
    lines.extend([
        "",
        "## Read",
        "",
        payload["decision_rationale"],
        "",
        "## Next Action",
        "",
        payload["next_action"],
        "",
    ])
    AUDIT_MD.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_MD.write_text("\n".join(lines), encoding="utf-8")


def _fmt_pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}%"


def _fmt_rate(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2%}"


def build_payload() -> dict[str, Any]:
    source = _load_json(INPUT_EVENTS)
    events = [event for event in source.get("events") or [] if isinstance(event, dict)]
    variants = {
        name: _variant_summary(events, min_purchase_value)
        for name, min_purchase_value in VARIANTS.items()
    }
    best = _best_variant(variants)
    best_row = variants[best]
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    shadow_promising = best_row["aggregate"]["all_valid_windows_positive"]
    decision = "shadow_promising_not_promoted" if shadow_promising else "rejected"
    status = "completed"
    return {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "lane": "alpha_search",
        "mechanism_family": "form4_standalone_external_event_source",
        "change_type": "shadow_event_sleeve_replay",
        "hypothesis": (
            "Large PIT-safe Form 4 open-market purchase event-days can seed a standalone "
            "external-event watchlist sleeve with positive short-term excess return, instead "
            "of only serving as a sparse overlay on current A/B entries."
        ),
        "alpha_hypothesis_category": "entry_external_event_source",
        "why_not_llm_soft_ranking": (
            "Production-aligned LLM ranking samples are too thin. This tests a structured "
            "non-OHLCV event source that already has transaction-level backfill."
        ),
        "history_check": {
            "nearby_failed_or_blocked": {
                "exp-20260503-017": "Form 4 was data-blocked before transaction XML backfill existed.",
                "exp-20260503-046": "Form 4 purchase outcomes were shadow-positive and requested joins to candidate sets.",
                "exp-20260503-048": "Near-entry accepted-trade overlap was too sparse.",
                "exp-20260503-049": "Entry-skip oracle overlap was zero and rejected as replacement overlay.",
            },
            "why_not_simple_repeat": (
                "This is not near-entry confirmation or skipped-candidate replacement. It tests "
                "the remaining branch named by exp-20260503-049: standalone external-event source."
            ),
            "mechanism_insight_guardrail": (
                "Does not retry SEC raw reaction thresholds, simple RS/TQS ranking, broad universe "
                "promotion, or nearby SPY-relative leader qualification gates."
            ),
        },
        "parameters": {
            "single_causal_variable": "minimum total purchase value for meaningful Form 4 purchase event-days",
            "cohort_flag": "meaningful_purchase_v1",
            "tested_min_total_purchase_values": VARIANTS,
            "primary_horizon_trading_days": int(PRIMARY_HORIZON),
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "event_notional_for_shadow_pnl": EVENT_NOTIONAL,
            "portfolio_base_for_shadow_return": PORTFOLIO_BASE,
            "locked_variables": [
                "production universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "position sizing",
                "add-ons",
                "exits",
                "LLM/news replay",
                "core backtester behavior",
            ],
        },
        "date_range": {
            "primary": WINDOW_RANGES["late_strong"],
            "secondary": [WINDOW_RANGES["mid_weak"], WINDOW_RANGES["old_thin"]],
        },
        "market_regime_summary": {
            "late_strong": "slow-melt bull / accepted-stack dominant tape",
            "mid_weak": "rotation-heavy bull where strategy makes money but lags indexes",
            "old_thin": "mixed-to-weak older tape with lower win rate",
        },
        "before_metrics": BASELINE_METRICS,
        "after_metrics": BASELINE_METRICS,
        "expected_value_score_delta": 0.0,
        "shadow_variants": variants,
        "best_variant": best,
        "best_variant_gate4": False,
        "gate4_basis": (
            "No production strategy was promoted. Core before/after metrics are unchanged by design; "
            "this shadow replay only decides whether the Form 4 standalone branch deserves forward/pilot work."
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "production_impact": "shadow_only_no_strategy_logic_changed",
            "promotion_requirement": (
                "A positive future promotion must add a shared Form 4 event feature and a production "
                "adapter/reporting path before it can rank, size, or introduce candidates."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
        },
        "decision_rationale": (
            "The >=$500k meaningful-purchase variant is the first stable Form 4 branch in this run: "
            "it has positive 10-day excess return in all three fixed windows. It is still not promoted "
            "because the old_thin sample has only one valid event and no shared production/backtest "
            "event-sleeve policy exists."
        ) if shadow_promising else (
            "No standalone Form 4 threshold produced positive 10-day excess return in all three fixed windows."
        ),
        "rejection_reason": None if shadow_promising else "No tested standalone Form 4 threshold was stable across three windows.",
        "next_action": (
            "Do not add core entries yet. Put >=$500k meaningful Form 4 purchases into a default-off "
            "forward/pilot event queue with frozen same-day alternatives, then require closed outcome "
            "and replacement-value evidence before any shared production/backtest policy promotion."
        ) if shadow_promising else (
            "Stop Form 4 standalone work unless a materially broader transaction archive or different "
            "event discriminator supplies new evidence."
        ),
        "related_files": [
            _repo_rel(INPUT_EVENTS),
            _repo_rel(__file__),
            _repo_rel(OUT_JSON),
            _repo_rel(AUDIT_MD),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
        ],
    }


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_ticket(payload)
    _write_report(payload)
    _append_experiment_log(payload)


def main() -> int:
    payload = build_payload()
    persist(payload)
    best = payload["shadow_variants"][payload["best_variant"]]["aggregate"]
    print(json.dumps({
        "experiment_id": payload["experiment_id"],
        "decision": payload["decision"],
        "best_variant": payload["best_variant"],
        "best_valid_event_count": best["valid_event_count"],
        "best_avg_net_return_pct": best["avg_net_return_pct"],
        "best_avg_excess_vs_spy_pct": best["avg_excess_vs_spy_pct"],
        "best_positive_windows": best["positive_excess_windows"],
        "output": _repo_rel(OUT_JSON),
        "report": _repo_rel(AUDIT_MD),
    }, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
