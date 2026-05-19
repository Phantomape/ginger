"""Shadow replay for Form 4 owner-role discriminators.

This is an alpha search, not a production rule change.  The prior Form 4
standalone replay found that meaningful open-market purchases above $500k were
shadow-promising but too sparse for promotion.  This experiment tests one
causal variable: whether a simple owner-role discriminator makes that event
source materially cleaner.
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
DOCS_DIR = REPO_ROOT / "docs"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from quant.constants import ROUND_TRIP_COST_PCT


EXP_ID = "exp-20260503-053"
OUT_DIR = DATA_DIR / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / "form4_owner_role_discriminator.json"
AFTER_CORE_BACKTESTS_JSON = OUT_DIR / "after_core_backtests.json"
LOG_JSON = DOCS_DIR / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = DOCS_DIR / "experiments" / "tickets" / f"{EXP_ID}.json"
EXPERIMENT_LOG = DOCS_DIR / "experiment_log.jsonl"
AUDIT_MD = DOCS_DIR / "non_ohlcv_data_audit" / "form4_owner_role_discriminator_20260503.md"
PLAYBOOK = DOCS_DIR / "alpha-optimization-playbook.md"

INPUT_EVENTS = DATA_DIR / "non_ohlcv" / "form4_purchase_shadow_outcomes_20241002_20260421.json"
PRIMARY_HORIZON = "10"
MIN_PURCHASE_VALUE = 500_000.0
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


RolePredicate = Callable[[dict[str, Any]], bool]


ROLE_VARIANTS: "OrderedDict[str, RolePredicate]" = OrderedDict([
    ("baseline_ge500k_any_role", lambda event: True),
    ("ge500k_not_ceo_cfo_or_president", lambda event: not bool(event.get("any_ceo_cfo_or_president"))),
    ("ge500k_director_not_officer", lambda event: bool(event.get("any_director")) and not bool(event.get("any_officer"))),
    ("ge500k_not_officer", lambda event: not bool(event.get("any_officer"))),
    ("ge500k_single_owner", lambda event: int(event.get("owner_count") or 0) == 1),
    ("ge500k_ceo_cfo_or_president", lambda event: bool(event.get("any_ceo_cfo_or_president"))),
    ("ge500k_any_officer", lambda event: bool(event.get("any_officer"))),
    ("ge500k_owner_cluster_2plus", lambda event: int(event.get("owner_count") or 0) >= 2),
])


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


def _event_sharpe(values_pct: list[float]) -> float | None:
    if len(values_pct) < 2:
        return None
    values = [value / 100.0 for value in values_pct]
    stdev = statistics.stdev(values)
    if stdev == 0:
        return None
    return round((sum(values) / len(values)) / stdev * (len(values) ** 0.5), 4)


def _outcome_value(event: dict[str, Any], field: str, horizon: str = PRIMARY_HORIZON) -> float | None:
    value = ((event.get("outcomes") or {}).get(horizon) or {}).get(field)
    return float(value) if value is not None else None


def _base_event_matches(event: dict[str, Any]) -> bool:
    return (
        bool(event.get("meaningful_purchase_v1"))
        and float(event.get("total_purchase_value") or 0.0) >= MIN_PURCHASE_VALUE
    )


def _variant_events(events: list[dict[str, Any]], predicate: RolePredicate) -> list[dict[str, Any]]:
    return [event for event in events if _base_event_matches(event) and predicate(event)]


def _summarize_events(events: list[dict[str, Any]], *, horizon: str = PRIMARY_HORIZON) -> dict[str, Any]:
    valid = [event for event in events if _outcome_value(event, "return_pct", horizon) is not None]
    gross_returns = [_outcome_value(event, "return_pct", horizon) for event in valid]
    excess_returns = [_outcome_value(event, "excess_vs_spy_pct", horizon) for event in valid]
    gross_returns = [value for value in gross_returns if value is not None]
    excess_returns = [value for value in excess_returns if value is not None]
    net_returns = [value - (ROUND_TRIP_COST_PCT * 100.0) for value in gross_returns]
    total_pnl = round(sum(EVENT_NOTIONAL * value / 100.0 for value in net_returns), 2)
    return {
        "event_count": len(events),
        "valid_event_count": len(valid),
        "ticker_count": len({str(event.get("ticker") or "").upper() for event in events if event.get("ticker")}),
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
        "return_on_100k_base": round(total_pnl / PORTFOLIO_BASE, 6),
    }


def _variant_summary(events: list[dict[str, Any]], predicate: RolePredicate) -> dict[str, Any]:
    selected = _variant_events(events, predicate)
    by_window = {
        window: _summarize_events([event for event in selected if event.get("window") == window])
        for window in WINDOW_ORDER
    }
    aggregate = _summarize_events(selected)
    windows_with_valid_events = sum(1 for row in by_window.values() if row["valid_event_count"] > 0)
    positive_windows = sum(
        1
        for row in by_window.values()
        if row["valid_event_count"] > 0 and (row["avg_excess_vs_spy_pct"] or 0.0) > 0.0
    )
    aggregate.update({
        "windows_with_valid_events": windows_with_valid_events,
        "positive_excess_windows": positive_windows,
        "all_valid_windows_positive": (
            windows_with_valid_events == len(WINDOW_ORDER)
            and positive_windows == len(WINDOW_ORDER)
        ),
    })
    return {
        "min_total_purchase_value": MIN_PURCHASE_VALUE,
        "primary_horizon_trading_days": int(PRIMARY_HORIZON),
        "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
        "by_window": by_window,
        "aggregate": aggregate,
    }


def _select_best_role_variant(variants: dict[str, dict[str, Any]]) -> str:
    candidates = [name for name in variants if name != "baseline_ge500k_any_role"]
    return max(
        candidates,
        key=lambda name: (
            variants[name]["aggregate"]["all_valid_windows_positive"],
            variants[name]["aggregate"]["avg_excess_vs_spy_pct"] or -999.0,
            variants[name]["aggregate"]["valid_event_count"],
        ),
    )


def _fmt_pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}%"


def _fmt_rate(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2%}"


def build_payload() -> dict[str, Any]:
    source = _load_json(INPUT_EVENTS)
    events = [event for event in source.get("events") or [] if isinstance(event, dict)]
    variants = {name: _variant_summary(events, predicate) for name, predicate in ROLE_VARIANTS.items()}
    baseline_shadow = variants["baseline_ge500k_any_role"]["aggregate"]
    best_role = _select_best_role_variant(variants)
    best_role_shadow = variants[best_role]["aggregate"]
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    avg_excess_delta = round(
        (best_role_shadow["avg_excess_vs_spy_pct"] or 0.0)
        - (baseline_shadow["avg_excess_vs_spy_pct"] or 0.0),
        6,
    )
    valid_event_delta = best_role_shadow["valid_event_count"] - baseline_shadow["valid_event_count"]
    role_filter_materially_better = (
        avg_excess_delta >= 1.0
        and valid_event_delta >= -2
        and best_role_shadow["all_valid_windows_positive"]
    )
    decision = "accepted_candidate" if role_filter_materially_better else "rejected"
    return {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "status": decision,
        "decision": decision,
        "lane": "alpha_search",
        "mechanism_family": "form4_standalone_external_event_source",
        "change_type": "shadow_event_owner_role_discriminator",
        "hypothesis": (
            "Within PIT-safe meaningful Form 4 purchases above $500k, simple owner-role "
            "filters may identify a cleaner standalone external-event candidate source "
            "than the plain purchase-value threshold."
        ),
        "alpha_hypothesis_category": "entry_external_event_source",
        "why_not_llm_soft_ranking": (
            "Production-aligned LLM ranking samples remain too thin, so this tests a "
            "structured Form 4 event source that is not blocked by LLM replay coverage."
        ),
        "history_check": {
            "recent_related_results": {
                "exp-20260503-048": "Form 4 accepted-trade overlap was too sparse.",
                "exp-20260503-049": "Form 4 skipped-entry overlap was zero.",
                "exp-20260503-052": "Plain >=$500k meaningful purchases were shadow-promising but not promotable.",
            },
            "why_not_simple_repeat": (
                "This locks the prior >=$500k event source and tests only owner-role "
                "discrimination; it does not retry near-entry joins or promote the event sleeve."
            ),
            "mechanism_insight_guardrail": (
                "Avoids recently rejected SEC reaction gates, RS/TQS slot ranking, static universe "
                "promotion, nearby SPY leader gates, and ATR trailing exits."
            ),
        },
        "parameters": {
            "single_causal_variable": "FORM4_OWNER_ROLE_FILTER",
            "baseline_event_filter": "meaningful_purchase_v1 and total_purchase_value >= 500000",
            "tested_role_filters": list(ROLE_VARIANTS.keys()),
            "primary_horizon_trading_days": int(PRIMARY_HORIZON),
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
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
        "delta_metrics": {
            "expected_value_score_delta_sum": 0.0,
            "total_pnl_delta_sum": 0.0,
            "core_trade_count_delta_sum": 0,
            "best_role_variant": best_role,
            "best_role_avg_excess_delta_pct": avg_excess_delta,
            "best_role_valid_event_delta": valid_event_delta,
        },
        "shadow_baseline": variants["baseline_ge500k_any_role"],
        "shadow_variants": variants,
        "best_role_variant": best_role,
        "best_variant_gate4": False,
        "gate4_basis": (
            "No production strategy was promoted. Core before/after fixed-window metrics are unchanged; "
            "the decision is whether role filters dominate the already-known plain >=$500k Form 4 event source."
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "production_impact": "shadow_only_no_strategy_logic_changed",
            "promotion_requirement": (
                "Any future positive Form 4 promotion must use a shared event-sleeve policy plus "
                "production event-queue reporting before it can rank, size, or introduce candidates."
            ),
        },
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "decision_rationale": (
            f"The best role filter was {best_role}, with avg 10d excess delta "
            f"{avg_excess_delta:+.2f} pp versus the plain >=$500k baseline and "
            f"{valid_event_delta:+d} valid events. That is not enough to justify "
            "a new role-gated branch: the apparent lift is small, sample count falls, "
            "and old_thin still has only one valid event."
        ),
        "rejection_reason": None if role_filter_materially_better else (
            "Owner-role filters did not materially dominate the simpler >=$500k meaningful-purchase event source."
        ),
        "next_retry_requires": [
            "Do not retry simple Form 4 owner-role filters without a materially broader archive.",
            "The next valid Form 4 step remains a default-off forward/pilot queue with frozen alternatives.",
            "A promotion needs shared production/backtest event policy, not another shadow-only role threshold.",
        ],
        "related_files": [
            _repo_rel(INPUT_EVENTS),
            _repo_rel(__file__),
            _repo_rel(OUT_JSON),
            _repo_rel(AFTER_CORE_BACKTESTS_JSON),
            _repo_rel(AUDIT_MD),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
        ],
    }


def _append_experiment_log(row: dict[str, Any]) -> None:
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
            "quant/experiments/exp_20260503_053_form4_owner_role_discriminator.py",
            "quant/test_form4_owner_role_discriminator.py",
            "data/experiments/exp-20260503-053/form4_owner_role_discriminator.json",
            "data/experiments/exp-20260503-053/after_core_backtests.json",
            "docs/non_ohlcv_data_audit/form4_owner_role_discriminator_20260503.md",
            "experiments/logs/exp-20260503-053.json",
            "experiments/tickets/exp-20260503-053.json",
            "docs/experiment_log.jsonl",
            "docs/alpha-optimization-playbook.md",
        ],
        "result": {
            "artifact": _repo_rel(OUT_JSON),
            "audit_report": _repo_rel(AUDIT_MD),
            "log": _repo_rel(LOG_JSON),
            "best_role_variant": payload["best_role_variant"],
            "production_impact": payload["production_impact"]["production_impact"],
        },
    }
    _write_json(TICKET_JSON, ticket)


def _write_report(payload: dict[str, Any]) -> None:
    lines = [
        "# Form 4 Owner-Role Discriminator Shadow Replay",
        "",
        f"- experiment_id: `{payload['experiment_id']}`",
        f"- timestamp: `{payload['timestamp']}`",
        f"- decision: `{payload['decision']}`",
        f"- production_impact: `{payload['production_impact']['production_impact']}`",
        f"- base event filter: `{payload['parameters']['baseline_event_filter']}`",
        "",
        "## Core Baseline",
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
        "## Shadow Role Variants",
        "",
        "| Variant | Valid events | Avg net return | Avg excess | Excess win rate | Positive windows |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for name, row in payload["shadow_variants"].items():
        agg = row["aggregate"]
        lines.append(
            f"| {name} | {agg['valid_event_count']} | {_fmt_pct(agg['avg_net_return_pct'])} | "
            f"{_fmt_pct(agg['avg_excess_vs_spy_pct'])} | {_fmt_rate(agg['excess_win_rate'])} | "
            f"{agg['positive_excess_windows']}/{len(WINDOW_ORDER)} |"
        )
    best = payload["shadow_variants"][payload["best_role_variant"]]
    lines.extend([
        "",
        "## Best Role Variant By Shadow Excess",
        "",
        f"- best_role_variant: `{payload['best_role_variant']}`",
        f"- avg_excess_delta_vs_plain_ge500k: `{payload['delta_metrics']['best_role_avg_excess_delta_pct']:+.2f} pp`",
        f"- valid_event_delta_vs_plain_ge500k: `{payload['delta_metrics']['best_role_valid_event_delta']:+d}`",
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
    lines.extend(["", "## Decision", "", payload["decision_rationale"], ""])
    AUDIT_MD.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_MD.write_text("\n".join(lines), encoding="utf-8")


def _update_playbook(payload: dict[str, Any]) -> None:
    marker = "### 2026-05-03 mechanism update: Form 4 owner-role discriminator"
    if PLAYBOOK.exists():
        text = PLAYBOOK.read_text(encoding="utf-8", errors="replace")
        if marker in text:
            return
    else:
        text = ""
    section = f"""

{marker}

Status: rejected.

Core conclusion: `{EXP_ID}` tested whether simple owner-role filters improve the
shadow-promising `meaningful_purchase_v1 >= $500k` Form 4 standalone event
source. They should not be promoted or repeatedly swept.

Evidence: the best role-only variant was `{payload['best_role_variant']}`. It
improved average 10-day excess by only
`{payload['delta_metrics']['best_role_avg_excess_delta_pct']:+.2f} pp` versus
the plain >=$500k branch while cutting valid events by
`{payload['delta_metrics']['best_role_valid_event_delta']}`. The old_thin
window still had only one valid event, so the apparent role lift does not solve
the main sample-stability problem.

Mechanism insight: Form 4 remains more promising as a forward standalone event
queue than as another static role-threshold sweep. The simple distinction
between director, officer, CEO/CFO/president, single-owner, and cluster buying
does not add enough information on top of purchase value.

Do not repeat: simple Form 4 owner-role filters around the `$500k` meaningful
purchase branch without materially broader transaction history or live forward
pilot evidence. A valid next step remains a default-off forward/pilot event
queue with frozen same-day alternatives and shared production/backtest event
policy before promotion.
"""
    PLAYBOOK.write_text(text.rstrip() + section + "\n", encoding="utf-8")


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_ticket(payload)
    _write_report(payload)
    _append_experiment_log(payload)
    _update_playbook(payload)


def main() -> int:
    payload = build_payload()
    persist(payload)
    best = payload["shadow_variants"][payload["best_role_variant"]]["aggregate"]
    print(json.dumps({
        "experiment_id": payload["experiment_id"],
        "decision": payload["decision"],
        "best_role_variant": payload["best_role_variant"],
        "best_valid_event_count": best["valid_event_count"],
        "best_avg_excess_vs_spy_pct": best["avg_excess_vs_spy_pct"],
        "baseline_avg_excess_vs_spy_pct": payload["shadow_baseline"]["aggregate"]["avg_excess_vs_spy_pct"],
        "avg_excess_delta_pct": payload["delta_metrics"]["best_role_avg_excess_delta_pct"],
        "valid_event_delta": payload["delta_metrics"]["best_role_valid_event_delta"],
        "output": _repo_rel(OUT_JSON),
        "report": _repo_rel(AUDIT_MD),
    }, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
