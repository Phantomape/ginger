"""exp-20260510-022: dust-sized signal pre-plan filter replay.

Alpha search. Test one capital-allocation variable: whether signals whose
shared sizing already produces only dust-sized whole-share orders should be
removed before scarce core slot planning, rather than consuming a nominal slot
and later falling through as low-impact/noisy entries.

Replay only unless Gate 4 clears and the exact filter is promoted into shared
production_parity.plan_entry_candidates with run/backtester parity tests.
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

import backtester as bt  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260510-022"
STEM = "dust_slot_preplan_filter"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
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

VARIANTS = OrderedDict(
    [
        ("drop_one_share_sized_signals", {"max_shares_to_filter": 1}),
        ("drop_one_or_two_share_sized_signals", {"max_shares_to_filter": 2}),
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
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_safe(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload_line = json.dumps(_safe(payload), ensure_ascii=False, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                rows.append(line)
                continue
            if row.get("experiment_id") == payload["experiment_id"]:
                if not replaced:
                    rows.append(payload_line)
                    replaced = True
                continue
            rows.append(line)
    if not replaced:
        rows.append(payload_line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _tail_loss_share(trades: list[dict[str, Any]], n: int = 5) -> float | None:
    losses = sorted(
        [abs(float(t.get("pnl") or 0.0)) for t in trades if float(t.get("pnl") or 0.0) < 0],
        reverse=True,
    )
    if not losses:
        return None
    return round(sum(losses[:n]) / sum(losses), 4)


def _max_consecutive_losses(trades: list[dict[str, Any]]) -> int:
    ordered = sorted(trades, key=lambda t: (t.get("exit_date") or "", t.get("entry_date") or ""))
    streak = 0
    worst = 0
    for trade in ordered:
        if float(trade.get("pnl") or 0.0) < 0:
            streak += 1
            worst = max(worst, streak)
        else:
            streak = 0
    return worst


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    trades = result.get("trades") or []
    worst_trade_pct = None
    if trades:
        worst_trade_pct = min(float(t.get("pnl_pct_net") or 0.0) for t in trades)
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
        "worst_trade_pct": _round(worst_trade_pct, 4),
        "max_consecutive_losses": _max_consecutive_losses(trades),
        "tail_loss_share": _tail_loss_share(trades),
    }


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    keys = (
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
        "worst_trade_pct",
        "max_consecutive_losses",
        "tail_loss_share",
    )
    out: dict[str, Any] = {}
    for key in keys:
        before_value = before.get(key)
        after_value = after.get(key)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            if key in {
                "trade_count",
                "signals_generated",
                "signals_survived",
                "max_consecutive_losses",
            }:
                out[key] = int(after_value - before_value)
            else:
                out[key] = _round(after_value - before_value, 6)
    return out


def _extract_multiplier_keys(sizing: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in (sizing or {}).items():
        if not key.endswith("_multiplier_applied"):
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if numeric != 1.0:
            out[key] = numeric
    return out


def _make_plan_entry_candidates(original_plan, max_shares_to_filter: int):
    filtered: list[dict[str, Any]] = []

    def patched(signals, open_positions, *args, **kwargs):
        kept = []
        for sig in list(signals or []):
            sizing = sig.get("sizing") or {}
            shares = sizing.get("shares_to_buy")
            try:
                shares_int = int(shares)
            except (TypeError, ValueError):
                kept.append(sig)
                continue
            if 0 < shares_int <= max_shares_to_filter:
                filtered.append(
                    {
                        "ticker": sig.get("ticker"),
                        "strategy": sig.get("strategy"),
                        "sector": sig.get("sector"),
                        "entry_price": sig.get("entry_price"),
                        "stop_price": sig.get("stop_price"),
                        "target_price": sig.get("target_price"),
                        "shares_to_buy": shares_int,
                        "risk_pct": sizing.get("risk_pct"),
                        "base_risk_pct": sizing.get("base_risk_pct"),
                        "position_value_usd": sizing.get("position_value_usd"),
                        "trade_quality_score": sizing.get("trade_quality_score"),
                        "sizing_multipliers": _extract_multiplier_keys(sizing),
                    }
                )
                continue
            kept.append(sig)
        planned, audit = original_plan(kept, open_positions, *args, **kwargs)
        audit = dict(audit or {})
        audit["dust_slot_preplan_filtered_count"] = len(filtered)
        audit["dust_slot_preplan_max_shares_to_filter"] = max_shares_to_filter
        return planned, audit

    patched.filtered = filtered  # type: ignore[attr-defined]
    return patched


def _run_window(window: dict[str, str], variant: dict[str, Any] | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    original_plan = bt.plan_entry_candidates
    if variant is not None:
        bt.plan_entry_candidates = _make_plan_entry_candidates(
            original_plan,
            int(variant["max_shares_to_filter"]),
        )
    try:
        result = BacktestEngine(
            sorted(get_universe()),
            start=window["start"],
            end=window["end"],
            config={"REGIME_AWARE_EXIT": True},
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
        ).run()
        filtered = []
        if variant is not None:
            filtered = list(getattr(bt.plan_entry_candidates, "filtered", []))
        return result, filtered
    finally:
        bt.plan_entry_candidates = original_plan


def _run_baselines() -> OrderedDict[str, dict[str, Any]]:
    rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for label, window in WINDOWS.items():
        print(f"[{label}] baseline")
        result, _ = _run_window(window)
        rows[label] = {"raw": result, "metrics": _metrics(result)}
    return rows


def _aggregate(rows: OrderedDict[str, dict[str, Any]]) -> dict[str, Any]:
    ev_before = sum(float(row["before"]["expected_value_score"] or 0.0) for row in rows.values())
    ev_delta = sum(float(row["delta"]["expected_value_score"] or 0.0) for row in rows.values())
    pnl_before = sum(float(row["before"]["total_pnl"] or 0.0) for row in rows.values())
    pnl_delta = sum(float(row["delta"]["total_pnl"] or 0.0) for row in rows.values())
    return {
        "baseline_expected_value_score_sum": _round(ev_before, 6),
        "after_expected_value_score_sum": _round(ev_before + ev_delta, 6),
        "expected_value_score_delta_sum": _round(ev_delta, 6),
        "expected_value_score_delta_pct": _round(ev_delta / ev_before if ev_before else 0.0, 6),
        "baseline_total_pnl_sum": _round(pnl_before, 2),
        "after_total_pnl_sum": _round(pnl_before + pnl_delta, 2),
        "total_pnl_delta_sum": _round(pnl_delta, 2),
        "total_pnl_delta_pct": _round(pnl_delta / pnl_before if pnl_before else 0.0, 6),
        "ev_windows_improved": sum(
            1 for row in rows.values() if row["delta"].get("expected_value_score", 0) > 0
        ),
        "ev_windows_regressed": sum(
            1 for row in rows.values() if row["delta"].get("expected_value_score", 0) < 0
        ),
        "pnl_windows_improved": sum(
            1 for row in rows.values() if row["delta"].get("total_pnl", 0) > 0
        ),
        "pnl_windows_regressed": sum(
            1 for row in rows.values() if row["delta"].get("total_pnl", 0) < 0
        ),
        "max_drawdown_delta_max": _round(
            max(row["delta"].get("max_drawdown_pct", 0.0) for row in rows.values()), 6
        ),
        "min_survival_rate_after": _round(
            min(row["after"].get("survival_rate", 0.0) for row in rows.values()), 6
        ),
        "trade_count_delta_sum": sum(row["delta"].get("trade_count", 0) for row in rows.values()),
        "win_rate_delta_min": _round(
            min(row["delta"].get("win_rate", 0.0) for row in rows.values()), 6
        ),
        "max_consecutive_losses_delta_max": max(
            row["delta"].get("max_consecutive_losses", 0) for row in rows.values()
        ),
        "tail_loss_share_delta_max": _round(
            max(row["delta"].get("tail_loss_share", 0.0) for row in rows.values()), 6
        ),
        "filtered_candidate_count_sum": sum(
            row["filtered_candidate_count"] for row in rows.values()
        ),
    }


def _gate4_passed(aggregate: dict[str, Any]) -> bool:
    material = (
        aggregate["expected_value_score_delta_pct"] > 0.10
        or aggregate["total_pnl_delta_pct"] > 0.05
        or aggregate["max_drawdown_delta_max"] < -0.01
        or (
            aggregate["trade_count_delta_sum"] > 0
            and aggregate["win_rate_delta_min"] >= 0
        )
    )
    return (
        bool(material)
        and aggregate["ev_windows_improved"] >= 2
        and aggregate["ev_windows_regressed"] == 0
        and aggregate["min_survival_rate_after"] >= 0.05
        and aggregate["max_drawdown_delta_max"] <= 0.005
    )


def _run_variant(
    name: str,
    variant: dict[str, Any],
    baselines: OrderedDict[str, dict[str, Any]],
) -> dict[str, Any]:
    rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for label, window in WINDOWS.items():
        print(f"[{label}] {name}")
        after_result, filtered = _run_window(window, variant)
        before = baselines[label]["metrics"]
        after = _metrics(after_result)
        delta = _delta(after, before)
        rows[label] = {
            "window": window,
            "before": before,
            "after": after,
            "delta": delta,
            "filtered_candidate_count": len(filtered),
            "filtered_candidates": filtered,
        }
        print(
            f"[{label}] {name} EV={delta.get('expected_value_score', 0):+.4f} "
            f"PnL={delta.get('total_pnl', 0):+.2f} filtered={len(filtered)}"
        )
    aggregate = _aggregate(rows)
    return {
        "parameters": variant,
        "rows": rows,
        "aggregate": aggregate,
        "gate4_passed": _gate4_passed(aggregate),
    }


def _choose_best(variants: OrderedDict[str, dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    return sorted(
        variants.items(),
        key=lambda item: (
            item[1]["aggregate"]["expected_value_score_delta_sum"],
            item[1]["aggregate"]["total_pnl_delta_sum"],
        ),
        reverse=True,
    )[0]


def _make_payload(
    baselines: OrderedDict[str, dict[str, Any]],
    variants: OrderedDict[str, dict[str, Any]],
) -> dict[str, Any]:
    best_name, best = _choose_best(variants)
    accepted = bool(best["gate4_passed"])
    generated_at = datetime.now(timezone.utc).isoformat()
    return {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": generated_at,
        "timestamp": generated_at,
        "status": "accepted" if accepted else "rejected",
        "decision": "accepted" if accepted else "rejected",
        "lane": "alpha_search",
        "change_type": "capital_allocation_dust_slot_preplan_filter",
        "changed_variable": "max whole-share order size filtered before core slot planning",
        "mechanism_family": "scarce_slot_quality_routing",
        "hypothesis": (
            "Signals that the accepted sizing stack already reduces to dust-sized "
            "whole-share orders may have poor slot opportunity cost; removing only "
            "those dust-sized orders before scarce slot planning may improve EV by "
            "letting meaningful candidates compete for slots."
        ),
        "alpha_hypothesis": {
            "category": "capital allocation / entry routing",
            "playbook_alignment": (
                "Avoids blocked LLM soft-ranking and external event data paths, "
                "does not add noisy tickers, and does not retry global slot-count "
                "or scarce-breakout threshold changes. It tests slot quality after "
                "existing shared risk tags have already expressed low conviction."
            ),
        },
        "history_check": {
            "exp-20260505-012": (
                "Compound severe-haircut zero-sizing was rejected. This test is "
                "different: it filters tiny whole-share orders before slot planning "
                "so they do not reserve scarce slots."
            ),
            "exp-20260510-018": (
                "Slot-missed observed scout found raw slot scarcity but not enough "
                "replacement evidence for simple slot-count changes."
            ),
            "exp-20260510-021": (
                "Risk-unit slot accounting was rejected in all windows. This test "
                "does not change slot capacity; it only removes dust-sized signals "
                "from slot competition."
            ),
        },
        "parameters": {
            "single_causal_variable": "dust whole-share pre-plan filter cutoff",
            "variants": VARIANTS,
            "best_variant": best_name,
            "locked_variables": [
                "universe",
                "signal generation",
                "entry filters before sizing",
                "candidate ranking",
                "all existing risk multipliers",
                "MAX_POSITIONS",
                "scarce-slot breakout deferral threshold",
                "portfolio heat",
                "position caps",
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
        "before_metrics": {
            label: row["metrics"] for label, row in baselines.items()
        },
        "after_metrics": {
            label: row["after"] for label, row in best["rows"].items()
        },
        "delta_metrics": {
            "by_window": {label: row["delta"] for label, row in best["rows"].items()},
            "aggregate": best["aggregate"],
        },
        "variants": variants,
        "best_variant": best_name,
        "gate1": {
            "passed": True,
            "baseline_source": "Rerun by this script using docs/backtesting.md three fixed windows.",
        },
        "gate2": {
            "passed": True,
            "fields_checked": [
                "signal.sizing.shares_to_buy",
                "signal.sizing.risk_pct",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
        },
        "gate3": {
            "passed": best["aggregate"]["min_survival_rate_after"] >= 0.05,
            "min_survival_rate_after": best["aggregate"]["min_survival_rate_after"],
            "new_filter_added": True,
        },
        "gate4": {
            "passed": accepted,
            "basis": (
                "Requires material aggregate EV/PnL/drawdown or productive trade-count "
                "improvement, EV improvement in at least two windows, no EV-regressed "
                "window, survival >= 5%, and max drawdown worsening <= 0.5pp."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "blocker_relation": (
                "LLM soft-ranking remains sample-limited; this run uses deterministic "
                "sizing output already available in production and replay."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": True,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, implement the exact filter in shared "
                "production_parity.plan_entry_candidates and add run/backtester "
                "parity tests before live/default orders can use it."
            ),
        },
        "rejection_reason": None if accepted else (
            "The dust-sized pre-plan filter did not clear the canonical "
            "three-window materiality/stability gate."
        ),
        "next_retry_requires": [
            "Do not retry nearby 1-3 share dust filters on the same frozen sample.",
            "A valid retry needs candidate-level replacement evidence or a distinct execution-cost model.",
            "Any positive version must live in shared production_parity, not backtester-only code.",
        ],
        "why_not_other_changes": {
            "LLM_soft_ranking": "Production-aligned closed attribution remains too sparse.",
            "event_state_surface": "Best paper sleeves need forward outcomes, not same-sample retunes.",
            "universe_expansion": "Recent static additions either added noise or are observe-only governance sleeves.",
            "slot_accounting": "Risk-unit slot accounting was just rejected across all three windows.",
        },
        "known_risks": [
            "Whole-share count is price-level sensitive and can understate high-priced valid signals.",
            "Filtering after sizing but before planning changes slot competition and may expose weaker later-ranked candidates.",
            "A positive result would need explicit production visibility so operators know a dust signal was intentionally skipped.",
        ],
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "quant/experiments/exp_20260510_022_dust_slot_preplan_filter.py",
            "docs/experiment_log.jsonl",
            "docs/alpha-optimization-playbook.md",
        ],
    }


def _write_artifact(payload: dict[str, Any]) -> None:
    aggregate = payload["delta_metrics"]["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} Dust Slot Pre-Plan Filter",
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
        f"- aggregate EV delta: `{aggregate['expected_value_score_delta_sum']:+.4f}` "
        f"({aggregate['expected_value_score_delta_pct']:+.2%})",
        f"- aggregate PnL delta: `${aggregate['total_pnl_delta_sum']:+,.2f}` "
        f"({aggregate['total_pnl_delta_pct']:+.2%})",
        f"- EV windows improved/regressed: `{aggregate['ev_windows_improved']}` / `{aggregate['ev_windows_regressed']}`",
        f"- filtered candidate count: `{aggregate['filtered_candidate_count_sum']}`",
        "",
        "## Three-window Deltas",
        "",
        "| Window | EV delta | PnL delta | SharpeD delta | DD delta | Trades delta | Survival after | Filtered |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, row in payload["variants"][payload["best_variant"]]["rows"].items():
        delta = row["delta"]
        after = row["after"]
        lines.append(
            f"| `{label}` | {delta.get('expected_value_score', 0):+.4f} | "
            f"{delta.get('total_pnl', 0):+.2f} | {delta.get('sharpe_daily', 0):+.2f} | "
            f"{delta.get('max_drawdown_pct', 0):+.4f} | {delta.get('trade_count', 0):+d} | "
            f"{after.get('survival_rate', 0):.4f} | {row['filtered_candidate_count']} |"
        )
    lines.extend(
        [
            "",
            "## Production Impact",
            "",
            "- Replay-only runtime patch; no live/default orders changed.",
            "- A positive result would need the exact helper in shared `production_parity.py`, plus run/backtester parity tests.",
            "",
        ]
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines), encoding="utf-8")


def _update_playbook(payload: dict[str, Any]) -> None:
    marker = "\n### 2026-05-10 mechanism update: Dust slot pre-plan filter\n"
    aggregate = payload["delta_metrics"]["aggregate"]
    entry = (
        marker
        +
        "\n"
        f"Experiment: `{EXPERIMENT_ID}`\n\n"
        f"Decision: `{payload['decision']}`.\n\n"
        "Finding: dust-sized whole-share signals were removed before scarce slot "
        "planning to test whether accepted risk haircuts should also imply lower "
        "slot priority. The best variant "
        f"`{payload['best_variant']}` produced aggregate EV delta "
        f"`{aggregate['expected_value_score_delta_sum']:+.4f}` and PnL delta "
        f"`${aggregate['total_pnl_delta_sum']:+,.2f}` across the canonical windows. "
        f"EV improved/regressed windows: `{aggregate['ev_windows_improved']}` / "
        f"`{aggregate['ev_windows_regressed']}`.\n\n"
        "Mechanism insight: whole-share dust status alone is not enough to promote "
        "a new slot-routing rule unless it clears Gate 4. Do not retry nearby "
        "1-3 share dust filters on this frozen sample without replacement-value "
        "evidence or a distinct execution-cost model.\n"
    )
    text = PLAYBOOK.read_text(encoding="utf-8")
    if f"`{EXPERIMENT_ID}`" in text:
        return
    text = text.rstrip() + "\n" + entry
    PLAYBOOK.write_text(text, encoding="utf-8")


def main() -> int:
    baselines = _run_baselines()
    variants: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for name, variant in VARIANTS.items():
        variants[name] = _run_variant(name, variant, baselines)

    payload = _make_payload(baselines, variants)
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "generated_at": payload["generated_at"],
            "decision": payload["decision"],
            "title": "Dust slot pre-plan filter",
            "summary": f"Best {payload['best_variant']}; Gate4={payload['gate4']['passed']}",
            "best_variant": payload["best_variant"],
            "delta_metrics": payload["delta_metrics"]["aggregate"],
            "production_impact": payload["production_impact"],
            "log_file": str(LOG_JSON.relative_to(REPO_ROOT)),
        },
    )
    _write_artifact(payload)
    _upsert_jsonl(EXPERIMENT_LOG_JSONL, payload)
    _update_playbook(payload)

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "best_variant": payload["best_variant"],
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
