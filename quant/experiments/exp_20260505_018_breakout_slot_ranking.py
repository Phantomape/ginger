"""exp-20260505-018: breakout slot-ranking replay.

Alpha search. Tests one entry-allocation variable: when Strategy B breakout
candidates compete for finite entry slots, should their shared pre-risk ranking
favor relative strength or confidence instead of the current 52-week-high
proximity order?

This runner is replay-only. A positive result must be promoted through the
shared signal_engine.rank_signals_for_allocation helper so run.py and
backtester.py stay aligned.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
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


EXPERIMENT_ID = "exp-20260505-018"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "breakout_slot_ranking.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_breakout_slot_ranking.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
PLAYBOOK = REPO_ROOT / "docs" / "alpha-optimization-playbook.md"

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
        "state_note": "slow-melt bull / accepted-stack dominant tape",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
        "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "state_note": "mixed-to-weak older tape with lower win rate",
    }),
])

VARIANTS = OrderedDict([
    ("breakout_rank_rs_then_52w", {
        "rank_order": ["rs_vs_spy", "pct_from_52w_high", "confidence_score"],
        "description": "prioritize strongest 10-day relative strength among breakout candidates",
    }),
    ("breakout_rank_confidence_then_rs", {
        "rank_order": ["confidence_score", "rs_vs_spy", "pct_from_52w_high"],
        "description": "prioritize generated signal confidence before relative strength",
    }),
])


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


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    by_strategy = result.get("by_strategy") or {}
    reasons = (result.get("entry_execution_attribution") or {}).get("reason_counts") or {}
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "sharpe": _round(result.get("sharpe"), 2),
        "sharpe_daily": _round(result.get("sharpe_daily"), 2),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "total_return_pct": _round(benchmarks.get("strategy_total_return_pct"), 4),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": _round(result.get("survival_rate"), 4),
        "entered": reasons.get("entered", 0),
        "slot_sliced": reasons.get("slot_sliced", 0),
        "no_shares": reasons.get("no_shares", 0),
        "converged": bool((result.get("convergence") or {}).get("converged")),
        "by_strategy": {
            key: {
                "trade_count": value.get("trade_count"),
                "win_rate": _round(value.get("win_rate"), 4),
                "total_pnl_usd": _round(value.get("total_pnl_usd"), 2),
                "profit_factor": _round(value.get("profit_factor"), 4),
                "avg_R": _round(value.get("avg_R"), 4),
            }
            for key, value in by_strategy.items()
            if isinstance(value, dict)
        },
    }


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "expected_value_score",
        "sharpe",
        "sharpe_daily",
        "total_pnl",
        "total_return_pct",
        "max_drawdown_pct",
        "win_rate",
        "trade_count",
        "signals_generated",
        "signals_survived",
        "survival_rate",
        "entered",
        "slot_sliced",
        "no_shares",
    )
    out: dict[str, Any] = {}
    for field in fields:
        before_value = before.get(field)
        after_value = after.get(field)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            if field in {
                "trade_count",
                "signals_generated",
                "signals_survived",
                "entered",
                "slot_sliced",
                "no_shares",
            }:
                out[field] = int(after_value - before_value)
            else:
                out[field] = _round(after_value - before_value, 6)
    return out


def _field_value(signal: dict[str, Any], field: str) -> float:
    if field == "confidence_score":
        raw = signal.get("confidence_score", 0)
    else:
        raw = (signal.get("conditions_met") or {}).get(field, float("-inf"))
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return float("-inf")
    if not math.isfinite(value):
        return float("-inf")
    return value


def _rank_breakouts(signals: list[dict[str, Any]], rank_order: list[str]) -> list[dict[str, Any]]:
    breakout_signals = [s for s in signals if s.get("strategy") == "breakout_long"]
    if len(breakout_signals) <= 1:
        return list(signals)

    ranked_breakouts = sorted(
        breakout_signals,
        key=lambda signal: tuple(_field_value(signal, field) for field in rank_order),
        reverse=True,
    )
    breakout_iter = iter(ranked_breakouts)
    reranked = []
    for signal in signals:
        if signal.get("strategy") == "breakout_long":
            reranked.append(next(breakout_iter))
        else:
            reranked.append(signal)
    return reranked


class BreakoutRankingPatch:
    def __init__(self, rank_order: list[str]) -> None:
        self.rank_order = rank_order
        self.original: Callable[[Any], list[dict[str, Any]]] | None = None

    def __enter__(self) -> "BreakoutRankingPatch":
        self.original = signal_engine.rank_signals_for_allocation

        def patched_rank(signals):
            return _rank_breakouts(list(signals), self.rank_order)

        signal_engine.rank_signals_for_allocation = patched_rank
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.original is not None:
            signal_engine.rank_signals_for_allocation = self.original


def _run_window(window: dict[str, str], rank_order: list[str] | None = None) -> dict[str, Any]:
    context = BreakoutRankingPatch(rank_order) if rank_order is not None else None
    if context is None:
        result = BacktestEngine(
            sorted(get_universe()),
            start=window["start"],
            end=window["end"],
            config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
        ).run()
    else:
        with context:
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
        raise RuntimeError(str(result["error"]))
    return result


def _breakout_trades(result: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for trade in result.get("trades") or []:
        if trade.get("strategy") != "breakout_long":
            continue
        rows.append({
            "ticker": trade.get("ticker"),
            "entry_date": trade.get("entry_date"),
            "exit_date": trade.get("exit_date"),
            "pnl": _round(trade.get("pnl"), 2),
            "pnl_pct_net": _round(trade.get("pnl_pct_net"), 6),
            "exit_reason": trade.get("exit_reason"),
            "confidence_score": _round(trade.get("confidence_score"), 4),
            "sector": trade.get("sector"),
            "conditions_met": trade.get("conditions_met") or {},
        })
    return rows


def _run_baselines() -> OrderedDict[str, dict[str, Any]]:
    rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for label, window in WINDOWS.items():
        print(f"[{label}] baseline")
        result = _run_window(window)
        rows[label] = {
            "window": window,
            "raw": result,
            "metrics": _metrics(result),
            "breakout_trades": _breakout_trades(result),
        }
    return rows


def _run_variant(
    name: str,
    variant: dict[str, Any],
    baselines: OrderedDict[str, dict[str, Any]],
) -> dict[str, Any]:
    rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    rank_order = list(variant["rank_order"])
    for label, window in WINDOWS.items():
        print(f"[{label}] {name}")
        result = _run_window(window, rank_order=rank_order)
        before = baselines[label]["metrics"]
        after = _metrics(result)
        rows[label] = {
            "window": window,
            "before": before,
            "after": after,
            "delta": _delta(after, before),
            "breakout_trades_before": baselines[label]["breakout_trades"],
            "breakout_trades_after": _breakout_trades(result),
        }
        print(
            f"[{label}] {name} EV={rows[label]['delta']['expected_value_score']:+.4f} "
            f"PnL={rows[label]['delta']['total_pnl']:+.2f} "
            f"trades={rows[label]['delta']['trade_count']:+d}"
        )
    aggregate = _aggregate(rows)
    return {
        "parameters": variant,
        "rows": rows,
        "aggregate": aggregate,
        "gate4_passed": _gate4_passed(aggregate),
    }


def _aggregate(rows: OrderedDict[str, dict[str, Any]]) -> dict[str, Any]:
    before_ev = sum(row["before"]["expected_value_score"] for row in rows.values())
    after_ev = sum(row["after"]["expected_value_score"] for row in rows.values())
    before_pnl = sum(row["before"]["total_pnl"] for row in rows.values())
    after_pnl = sum(row["after"]["total_pnl"] for row in rows.values())
    deltas = [row["delta"] for row in rows.values()]
    return {
        "baseline_expected_value_score_sum": _round(before_ev, 4),
        "after_expected_value_score_sum": _round(after_ev, 4),
        "expected_value_score_delta_sum": _round(after_ev - before_ev, 4),
        "expected_value_score_delta_pct": _round(
            (after_ev - before_ev) / abs(before_ev),
            6,
        ) if before_ev else None,
        "baseline_total_pnl_sum": _round(before_pnl, 2),
        "after_total_pnl_sum": _round(after_pnl, 2),
        "total_pnl_delta_sum": _round(after_pnl - before_pnl, 2),
        "total_pnl_delta_pct": _round(
            (after_pnl - before_pnl) / abs(before_pnl),
            6,
        ) if before_pnl else None,
        "ev_windows_improved": sum(
            1 for delta in deltas if delta.get("expected_value_score", 0) > 0
        ),
        "ev_windows_regressed": sum(
            1 for delta in deltas if delta.get("expected_value_score", 0) < 0
        ),
        "pnl_windows_improved": sum(
            1 for delta in deltas if delta.get("total_pnl", 0) > 0
        ),
        "pnl_windows_regressed": sum(
            1 for delta in deltas if delta.get("total_pnl", 0) < 0
        ),
        "sharpe_delta_max": _round(
            max(delta.get("sharpe_daily", 0) for delta in deltas),
            6,
        ),
        "drawdown_delta_min": _round(
            min(delta.get("max_drawdown_pct", 0) for delta in deltas),
            6,
        ),
        "drawdown_delta_max": _round(
            max(delta.get("max_drawdown_pct", 0) for delta in deltas),
            6,
        ),
        "trade_count_delta_sum": sum(delta.get("trade_count", 0) for delta in deltas),
        "win_rate_delta_min": _round(
            min(delta.get("win_rate", 0) for delta in deltas),
            6,
        ),
        "slot_sliced_delta_sum": sum(delta.get("slot_sliced", 0) for delta in deltas),
    }


def _gate4_passed(aggregate: dict[str, Any]) -> bool:
    material = any([
        (aggregate.get("expected_value_score_delta_pct") or 0) > 0.10,
        aggregate.get("sharpe_delta_max", 0) > 0.10,
        aggregate.get("drawdown_delta_min", 0) < -0.01,
        (aggregate.get("total_pnl_delta_pct") or 0) > 0.05,
        (
            aggregate.get("trade_count_delta_sum", 0) > 0
            and aggregate.get("win_rate_delta_min", -1) >= 0
        ),
    ])
    majority_stable = (
        aggregate.get("ev_windows_improved", 0) >= 2
        and aggregate.get("ev_windows_regressed", 0) == 0
    )
    return bool(material and majority_stable)


def _best_variant(variants: OrderedDict[str, dict[str, Any]]) -> str:
    return max(
        variants,
        key=lambda name: (
            variants[name]["aggregate"]["expected_value_score_delta_sum"],
            variants[name]["aggregate"]["total_pnl_delta_sum"],
            -variants[name]["aggregate"]["drawdown_delta_max"],
        ),
    )


def _make_payload(
    baselines: OrderedDict[str, dict[str, Any]],
    variants: OrderedDict[str, dict[str, Any]],
) -> dict[str, Any]:
    best_name = _best_variant(variants)
    best = variants[best_name]
    accepted = bool(best["gate4_passed"])
    timestamp = datetime.now(timezone.utc).isoformat()
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "generated_at": timestamp,
        "status": "accepted" if accepted else "rejected",
        "decision": "accepted" if accepted else "rejected",
        "lane": "alpha_search",
        "change_type": "entry_candidate_ranking",
        "hypothesis": (
            "When Strategy B breakout candidates compete for finite entry slots, "
            "their pre-risk ordering may be better explained by relative strength "
            "or generated confidence than by 52-week-high proximity alone."
        ),
        "alpha_hypothesis": {
            "category": "entry / ranking",
            "statement": (
                "Breakout slot collisions should prefer the continuation candidate "
                "with stronger immediate RS or broader generated confirmation."
            ),
            "why_now": (
                "LLM soft-ranking and event sleeves are data-limited, broad universe "
                "expansion failed, and recent notes allow only scoped collision-class "
                "ranking tests after global sorting failed."
            ),
        },
        "historical_experiment_check": {
            "similar_prior_results": {
                "exp-20260503-010": (
                    "Global pre-slot TQS/RS sorting was rejected. This run is not a "
                    "simple repeat because it preserves the existing non-breakout "
                    "order and only changes the already-shared breakout subsequence "
                    "ranking helper."
                ),
                "exp-20260505-007": (
                    "Breakout above-200MA hard gate was a no-op/rejected. This run "
                    "does not add a hard filter or change survival rate mechanics."
                ),
            },
            "mechanism_insight_check": (
                "Does not retry broad universe expansion, LLM soft-ranking, event "
                "threshold promotion, sector caps, or nearby Financials/Commodity "
                "risk multipliers."
            ),
        },
        "parameters": {
            "baseline_rank_order": ["pct_from_52w_high", "confidence_score"],
            "tested_variants": {
                name: variant["rank_order"] for name, variant in VARIANTS.items()
            },
        },
        "date_range": {
            label: {
                "start": window["start"],
                "end": window["end"],
                "snapshot": window["snapshot"],
            }
            for label, window in WINDOWS.items()
        },
        "market_regime_summary": {
            label: window["state_note"] for label, window in WINDOWS.items()
        },
        "before_metrics": {
            label: row["metrics"] for label, row in baselines.items()
        },
        "after_metrics": {
            label: best["rows"][label]["after"] for label in WINDOWS
        },
        "deltas": {
            label: best["rows"][label]["delta"] for label in WINDOWS
        },
        "variant_results": variants,
        "aggregate": best["aggregate"],
        "best_variant": best_name,
        "expected_value_score_delta": best["aggregate"]["expected_value_score_delta_sum"],
        "gate4_passed": accepted,
        "acceptance_rule": (
            "Requires a material Gate 4 improvement and EV improvement in at "
            "least two windows with no EV-regressed window."
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_path_if_accepted": (
                "Change quant/signal_engine.py rank_signals_for_allocation and "
                "update quant/test_quant.py; the helper is already called by "
                "backtester.py, run.py, run_quant.py, and run_pipeline.py."
            ),
        },
        "llm_impact": {
            "changed_llm_boundary": False,
            "reason": "Deterministic ranking experiment; LLM soft-ranking remains data-limited.",
        },
        "decision_reason": (
            "Accepted: promote through shared signal_engine ranking helper."
            if accepted
            else (
                "Rejected: best ranking variant failed Gate 4 multi-window "
                "materiality/stability; do not retry nearby breakout RS/confidence "
                "subsequence orders without a new collision audit."
            )
        ),
        "intentionally_unchanged": [
            "Signal generation thresholds",
            "Risk sizing multipliers",
            "Universe membership",
            "LLM/news veto behavior",
            "Exit and add-on policies",
        ],
        "primary_risk": (
            "A ranking variant can replace profitable lower-RS breakouts with "
            "crowded momentum names when slots are scarce."
        ),
    }


def _write_artifact(payload: dict[str, Any]) -> None:
    lines = [
        f"# {EXPERIMENT_ID} breakout slot ranking",
        "",
        f"Decision: **{payload['decision']}**",
        f"Best variant: `{payload['best_variant']}`",
        "",
        "## Aggregate",
        "",
        f"- EV delta sum: {payload['aggregate']['expected_value_score_delta_sum']}",
        f"- EV delta pct: {payload['aggregate']['expected_value_score_delta_pct']}",
        f"- PnL delta sum: {payload['aggregate']['total_pnl_delta_sum']}",
        f"- PnL delta pct: {payload['aggregate']['total_pnl_delta_pct']}",
        f"- EV windows improved/regressed: "
        f"{payload['aggregate']['ev_windows_improved']}/"
        f"{payload['aggregate']['ev_windows_regressed']}",
        f"- Gate 4 passed: {payload['gate4_passed']}",
        "",
        "## Window Deltas",
        "",
    ]
    for label in WINDOWS:
        delta = payload["deltas"][label]
        lines.append(
            f"- {label}: EV {delta.get('expected_value_score'):+.4f}, "
            f"PnL {delta.get('total_pnl'):+.2f}, "
            f"Sharpe daily {delta.get('sharpe_daily'):+.2f}, "
            f"DD {delta.get('max_drawdown_pct'):+.4f}, "
            f"trades {delta.get('trade_count'):+d}"
        )
    lines.extend([
        "",
        "## Repro",
        "",
        "```powershell",
        ".\\.venv\\Scripts\\python.exe quant\\experiments\\exp_20260505_018_breakout_slot_ranking.py",
        "```",
        "",
        "## Production Parity",
        "",
        payload["production_impact"]["promotion_path_if_accepted"],
        "",
    ])
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_playbook_note(payload: dict[str, Any]) -> None:
    marker = f"### {EXPERIMENT_ID} breakout slot ranking"
    note = "\n".join([
        "",
        marker,
        f"- Decision: {payload['decision']}.",
        f"- Best variant: `{payload['best_variant']}`.",
        f"- Aggregate EV delta: {payload['aggregate']['expected_value_score_delta_sum']} "
        f"({payload['aggregate']['expected_value_score_delta_pct']}).",
        f"- Aggregate PnL delta: {payload['aggregate']['total_pnl_delta_sum']} "
        f"({payload['aggregate']['total_pnl_delta_pct']}).",
        "- Mechanism insight: breakout-only collision ranking is allowed only when "
        "it demonstrates multi-window replacement value; nearby RS/confidence "
        "subsequence orders should not be retried without a fresh collision audit.",
        "",
    ])
    PLAYBOOK.parent.mkdir(parents=True, exist_ok=True)
    current = PLAYBOOK.read_text(encoding="utf-8") if PLAYBOOK.exists() else ""
    if marker in current:
        head = current.split(marker)[0].rstrip()
        PLAYBOOK.write_text(head + note, encoding="utf-8")
    else:
        PLAYBOOK.write_text(current.rstrip() + note, encoding="utf-8")


def _write_ticket(payload: dict[str, Any]) -> None:
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "decision": payload["decision"],
        "lane": payload["lane"],
        "title": "Breakout slot ranking replay",
        "summary": payload["decision_reason"],
        "best_variant": payload["best_variant"],
        "aggregate": payload["aggregate"],
        "next_action": (
            "Promote through shared signal_engine helper and add parity tests."
            if payload["decision"] == "accepted"
            else "Do not retry nearby breakout RS/confidence ranking without new collision evidence."
        ),
    }
    _write_json(TICKET_JSON, ticket)


def main() -> None:
    baselines = _run_baselines()
    variants: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for name, variant in VARIANTS.items():
        variants[name] = _run_variant(name, variant, baselines)

    payload = _make_payload(baselines, variants)
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _append_jsonl(EXPERIMENT_LOG_JSONL, payload)
    _write_artifact(payload)
    _write_ticket(payload)
    _write_playbook_note(payload)

    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "decision": payload["decision"],
        "best_variant": payload["best_variant"],
        "aggregate": payload["aggregate"],
        "gate4_passed": payload["gate4_passed"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
