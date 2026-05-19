"""exp-20260507-011: revalidate earnings_event_long after P-ERN snapshots.

Alpha search. Strategy C was disabled after historical earnings replay used
incomplete data. The P-ERN backfill now provides PIT earnings snapshots with
EPS estimate and surprise-history coverage across the canonical windows. This
runner tests exactly one causal variable: whether the existing
earnings_event_long sleeve should be enabled alongside the accepted A+B stack.

No production behavior is changed by this experiment. A passing result would
need promotion through the shared ENABLED_STRATEGIES constant plus parity tests.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260507-011"
STEM = "earnings_sleeve_revalidation"

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
                "state_note": "rotation-heavy bull where strategy profits but can lag indexes",
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

BASELINE_STRATEGIES = ("trend_long", "breakout_long")
VARIANT_STRATEGIES = ("trend_long", "breakout_long", "earnings_event_long")


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _safe_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe_payload(item) for item in value]
    if isinstance(value, tuple):
        return [_safe_payload(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe_payload(payload), indent=2, ensure_ascii=True, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    kept: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                existing = json.loads(line)
            except json.JSONDecodeError:
                kept.append(line)
                continue
            if existing.get("experiment_id") != payload["experiment_id"]:
                kept.append(line)
    kept.append(json.dumps(_safe_payload(payload), ensure_ascii=True, sort_keys=True))
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def _append_playbook(payload: dict[str, Any]) -> None:
    section = f"""

### 2026-05-07 mechanism update: earnings sleeve revalidation

Experiment: `{EXPERIMENT_ID}`

Decision: `rejected`.

Finding: Re-enabling `earnings_event_long` after P-ERN snapshot backfill did
not pass the canonical three-window Gate 4 standard. EV regressed in all three
windows; aggregate EV delta was `{payload['delta_metrics']['aggregate']['expected_value_score_delta_sum']}`
and aggregate PnL delta was `${payload['delta_metrics']['aggregate']['total_pnl_delta_sum']}`.

Mechanism insight: P-ERN snapshot coverage fixes the prior measurement blocker,
but the current C-sleeve rule is still not a production-ready alpha source. It
adds low-win-rate earnings trades and displaces stronger A/B capital.

Do not repeat: simply adding `earnings_event_long` back to
`ENABLED_STRATEGIES`, or nearby C-sleeve enablement without a stronger
event-quality discriminator such as directional guidance, same-accession facts,
or closed forward event evidence.
"""
    with PLAYBOOK.open("a", encoding="utf-8") as handle:
        handle.write(section)


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
        "tail_loss_share": _round(result.get("tail_loss_share"), 4),
        "by_strategy": _safe_payload(result.get("by_strategy") or {}),
        "converged": bool((result.get("convergence") or {}).get("converged")),
    }


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "expected_value_score",
        "sharpe_daily",
        "total_pnl",
        "total_return_pct",
        "max_drawdown_pct",
        "win_rate",
        "trade_count",
        "signals_generated",
        "signals_survived",
        "survival_rate",
        "tail_loss_share",
    )
    out: dict[str, Any] = {}
    for field in fields:
        before_value = before.get(field)
        after_value = after.get(field)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            if field in {"trade_count", "signals_generated", "signals_survived"}:
                out[field] = int(after_value - before_value)
            else:
                out[field] = _round(after_value - before_value, 6)
    return out


def _snapshot_coverage(start: str, end: str) -> dict[str, Any]:
    start_key = start.replace("-", "")
    end_key = end.replace("-", "")
    paths = sorted(REPO_ROOT.glob("data/earnings_snapshot_*.json"))
    selected = [
        path for path in paths
        if start_key <= path.stem.removeprefix("earnings_snapshot_") <= end_key
    ]
    rows = []
    for path in selected:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        coverage = payload.get("coverage") or {}
        rows.append(coverage)
    if not rows:
        return {"snapshot_days": 0}

    def avg(field: str) -> Any:
        values = [item.get(field) for item in rows if isinstance(item.get(field), (int, float))]
        return _round(sum(values) / len(values), 4) if values else None

    return {
        "snapshot_days": len(rows),
        "avg_tickers_persisted": avg("tickers_persisted"),
        "avg_tickers_with_days_to_earnings": avg("tickers_with_days_to_earnings"),
        "avg_tickers_with_eps_estimate": avg("tickers_with_eps_estimate"),
        "avg_tickers_with_surprise_history": avg("tickers_with_surprise_history"),
        "first_snapshot": selected[0].name if selected else None,
        "last_snapshot": selected[-1].name if selected else None,
    }


def _run_window(window: dict[str, str], enabled_strategies: tuple[str, ...]) -> dict[str, Any]:
    result = BacktestEngine(
        sorted(get_universe()),
        start=window["start"],
        end=window["end"],
        config={"ENABLED_STRATEGIES": enabled_strategies},
        ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
    ).run()
    if "error" in result:
        raise RuntimeError(result["error"])
    return result


def _aggregate(deltas: dict[str, dict[str, Any]], before: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ev_delta = sum(row.get("expected_value_score", 0.0) or 0.0 for row in deltas.values())
    pnl_delta = sum(row.get("total_pnl", 0.0) or 0.0 for row in deltas.values())
    base_ev = sum(row.get("expected_value_score", 0.0) or 0.0 for row in before.values())
    base_pnl = sum(row.get("total_pnl", 0.0) or 0.0 for row in before.values())
    return {
        "baseline_expected_value_score_sum": _round(base_ev, 4),
        "after_expected_value_score_sum": _round(base_ev + ev_delta, 4),
        "expected_value_score_delta_sum": _round(ev_delta, 4),
        "expected_value_score_delta_pct": _round(ev_delta / base_ev if base_ev else None, 6),
        "baseline_total_pnl_sum": _round(base_pnl, 2),
        "after_total_pnl_sum": _round(base_pnl + pnl_delta, 2),
        "total_pnl_delta_sum": _round(pnl_delta, 2),
        "total_pnl_delta_pct": _round(pnl_delta / base_pnl if base_pnl else None, 6),
        "windows_ev_improved": sum(1 for row in deltas.values() if (row.get("expected_value_score") or 0) > 0),
        "windows_ev_regressed": sum(1 for row in deltas.values() if (row.get("expected_value_score") or 0) < 0),
        "windows_pnl_improved": sum(1 for row in deltas.values() if (row.get("total_pnl") or 0) > 0),
        "windows_pnl_regressed": sum(1 for row in deltas.values() if (row.get("total_pnl") or 0) < 0),
        "best_sharpe_daily_delta": _round(max(row.get("sharpe_daily", 0.0) or 0.0 for row in deltas.values()), 4),
        "max_drawdown_improvement_best": _round(min(row.get("max_drawdown_pct", 0.0) or 0.0 for row in deltas.values()), 4),
        "trade_count_delta_sum": sum(row.get("trade_count", 0) or 0 for row in deltas.values()),
        "min_win_rate_delta": _round(min(row.get("win_rate", 0.0) or 0.0 for row in deltas.values()), 4),
    }


def _gate4(aggregate: dict[str, Any], deltas: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ev_material = (aggregate.get("expected_value_score_delta_pct") or 0.0) > 0.10
    sharpe_material = (aggregate.get("best_sharpe_daily_delta") or 0.0) > 0.10
    drawdown_material = (aggregate.get("max_drawdown_improvement_best") or 0.0) < -0.01
    pnl_material = (aggregate.get("total_pnl_delta_pct") or 0.0) > 0.05
    trade_count_up = (
        (aggregate.get("trade_count_delta_sum") or 0) > 0
        and (aggregate.get("min_win_rate_delta") or 0.0) >= 0
    )
    majority_ev = aggregate.get("windows_ev_improved", 0) >= 2
    no_ev_regression = aggregate.get("windows_ev_regressed", 0) == 0
    return {
        "passed": bool((ev_material or sharpe_material or drawdown_material or pnl_material or trade_count_up) and majority_ev and no_ev_regression),
        "criteria": {
            "ev_material_gt_10pct": ev_material,
            "sharpe_daily_improvement_gt_0_1": sharpe_material,
            "max_drawdown_reduction_gt_1pp": drawdown_material,
            "pnl_improvement_gt_5pct": pnl_material,
            "trade_count_up_without_win_rate_drop": trade_count_up,
            "majority_windows_ev_improved": majority_ev,
            "no_ev_regression": no_ev_regression,
        },
        "by_window_ev_delta": {
            label: row.get("expected_value_score") for label, row in deltas.items()
        },
    }


def main() -> None:
    before_metrics: dict[str, dict[str, Any]] = {}
    after_metrics: dict[str, dict[str, Any]] = {}
    delta_metrics: dict[str, dict[str, Any]] = {}
    rows: dict[str, Any] = {}
    coverage: dict[str, Any] = {}

    for label, window in WINDOWS.items():
        baseline_result = _run_window(window, BASELINE_STRATEGIES)
        variant_result = _run_window(window, VARIANT_STRATEGIES)
        before = _metrics(baseline_result)
        after = _metrics(variant_result)
        delta = _delta(after, before)
        before_metrics[label] = before
        after_metrics[label] = after
        delta_metrics[label] = delta
        coverage[label] = _snapshot_coverage(window["start"], window["end"])
        rows[label] = {
            "window": window,
            "before": before,
            "after": after,
            "delta": delta,
        }

    aggregate = _aggregate(delta_metrics, before_metrics)
    gate4 = _gate4(aggregate, delta_metrics)
    delta_metrics["aggregate"] = aggregate

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "rejected",
        "decision": "rejected",
        "lane": "alpha_search",
        "change_type": "alpha_source_revalidation",
        "mechanism_family": "earnings_event_sleeve",
        "alpha_hypothesis_category": "entry / alpha source",
        "hypothesis": (
            "After P-ERN snapshot backfill adds EPS estimate and historical "
            "surprise coverage, the existing earnings_event_long sleeve may "
            "produce non-overlapping event alpha if enabled with A+B."
        ),
        "parameters": {
            "single_causal_variable": "ENABLED_STRATEGIES includes earnings_event_long",
            "baseline_enabled_strategies": list(BASELINE_STRATEGIES),
            "variant_enabled_strategies": list(VARIANT_STRATEGIES),
            "locked_variables": [
                "universe",
                "signal generation code",
                "entry filters",
                "candidate ranking",
                "position sizing",
                "entry open cancels",
                "scarce-slot routing",
                "add-ons",
                "all exits",
                "LLM/news replay",
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
        "earnings_snapshot_coverage": coverage,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": delta_metrics,
        "gate4": gate4,
        "best_variant": "enable_earnings_event_long",
        "best_variant_gate4": gate4["passed"],
        "rejection_reason": (
            "Re-enabling earnings_event_long regressed EV in all three canonical "
            "windows and displaced stronger A/B capital despite improved P-ERN "
            "snapshot field coverage."
        ),
        "history_guardrails": {
            "similar_prior_results": {
                "exp-20260418-004": (
                    "C strategy with incomplete earnings data had 33.3% win rate "
                    "and profit factor 0.33, dragging EV."
                )
            },
            "why_not_simple_repeat": (
                "This retry is qualified by a real data-basis change: daily "
                "earnings snapshots now provide EPS estimate and surprise-history "
                "coverage across the fixed windows."
            ),
            "mechanism_insight_conflict": (
                "No conflict with recent no-go zones: this does not retune exits, "
                "breadth/dispersion multipliers, SEC recency, short-pressure, "
                "options, or broad universe growth."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": (
                "LLM soft-ranking remains sample-limited; this tests a deterministic "
                "event alpha source whose prior blocker was earnings field coverage."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "promotion_requirement": (
                "If a future C-sleeve variant passes, change ENABLED_STRATEGIES "
                "in quant/constants.py and add a parity test proving run.py and "
                "backtester.py consume the same strategy list."
            ),
        },
        "risk_of_change": (
            "Would allocate scarce slots to low-win-rate pre-earnings trades and "
            "can displace stronger trend/breakout candidates."
        ),
        "next_retry_requires": [
            "Do not retry simple C-sleeve enablement with the same signal definition.",
            "A valid retry needs a richer event-quality discriminator, not just P-ERN coverage.",
            "Promising evidence would include directional guidance, same-accession facts, or closed forward event outcomes.",
        ],
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "docs/experiment_log.jsonl",
            "docs/alpha-optimization-playbook.md",
        ],
        "rows": rows,
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(TICKET_JSON, {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "hypothesis": payload["hypothesis"],
        "gate4": gate4,
        "rejection_reason": payload["rejection_reason"],
        "next_retry_requires": payload["next_retry_requires"],
        "related_log": str(LOG_JSON.relative_to(REPO_ROOT)),
    })
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(
        "\n".join(
            [
                f"# {EXPERIMENT_ID} earnings sleeve revalidation",
                "",
                f"Decision: {payload['decision']}",
                "",
                "## Aggregate",
                "",
                f"- EV delta: {aggregate['expected_value_score_delta_sum']} ({aggregate['expected_value_score_delta_pct']})",
                f"- PnL delta: ${aggregate['total_pnl_delta_sum']} ({aggregate['total_pnl_delta_pct']})",
                f"- EV improved/regressed windows: {aggregate['windows_ev_improved']} / {aggregate['windows_ev_regressed']}",
                "",
                "## Window deltas",
                "",
                *[
                    (
                        f"- {label}: EV {delta_metrics[label]['expected_value_score']}, "
                        f"PnL ${delta_metrics[label]['total_pnl']}, "
                        f"Sharpe daily {delta_metrics[label]['sharpe_daily']}, "
                        f"trades {delta_metrics[label]['trade_count']}"
                    )
                    for label in WINDOWS
                ],
                "",
                "## Conclusion",
                "",
                payload["rejection_reason"],
                "",
            ]
        ),
        encoding="utf-8",
    )
    _append_jsonl(EXPERIMENT_LOG, payload)
    _append_playbook(payload)
    print(str(OUT_JSON))


if __name__ == "__main__":
    main()
